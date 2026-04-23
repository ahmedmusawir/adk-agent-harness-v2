"""Custom preload-memory tool with configurable top_k.

Why this file exists:
  Google's stock `google.adk.tools.preload_memory_tool.preload_memory_tool`
  goes through `VertexAiMemoryBankService.search_memory`, which hardcodes
  `similarity_search_params={"search_query": query}` with NO top_k — so the
  server falls back to its default of 3. Three memories isn't enough when
  the bank has many entries; the relevant fact often doesn't rank into the
  top 3 and Jarvis goes amnesiac on known details.

  This module is a minimal fork: same <PAST_CONVERSATIONS> injection shape,
  but calls `memories.retrieve()` directly with top_k pulled from
  `memory_config.json`. That gives us a single-file knob to bump retrieval
  breadth without code changes.

  Settings live in `jarvis_agent/memory_config.json` and are read ONCE at
  module import. Edit that file + restart adk web to change top_k.
"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import vertexai

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from typing_extensions import override

if TYPE_CHECKING:
    from google.adk.models import LlmRequest


# Load config at import. Fail loud if it's missing or malformed — that's a
# dev bug, not something to silently paper over.
_CONFIG_PATH = Path(__file__).parent / "memory_config.json"
with _CONFIG_PATH.open("r", encoding="utf-8") as _f:
    _CONFIG = json.load(_f)

TOP_K = int(_CONFIG["top_k"])
PROJECT_ID = str(_CONFIG["project_id"])
LOCATION = str(_CONFIG["location"])


class PreloadMemoryTopK(BaseTool):
    """Silent context-injector tool (same shape as ADK's preload_memory_tool).

    Runs before every LLM request. Uses the current user message as a
    semantic search query against Memory Bank, then injects any matching
    facts into the system prompt inside a <PAST_CONVERSATIONS> block.

    Unlike ADK's stock preload_memory_tool, this one passes an explicit
    top_k in similarity_search_params (value from memory_config.json).
    """

    def __init__(self) -> None:
        # Name/description aren't shown to the model (no FunctionDeclaration)
        # but ADK uses 'name' for tool identity internally.
        super().__init__(name="preload_memory", description="preload_memory")

    @override
    async def process_llm_request(
        self,
        *,
        tool_context: ToolContext,
        llm_request: "LlmRequest",
    ) -> None:
        user_content = tool_context.user_content
        if (
            not user_content
            or not user_content.parts
            or not user_content.parts[0].text
        ):
            return
        query = user_content.parts[0].text

        agent_engine_id = os.environ.get("AGENT_ENGINE_ID")
        if not agent_engine_id:
            # Server started without --memory_service_uri / run_jarvis_web.sh.
            # Silently skip so Jarvis still works in non-memory mode.
            return

        session = tool_context._invocation_context.session
        scope = {
            "app_name": session.app_name or "jarvis_agent",
            "user_id":  session.user_id  or "user",
        }

        try:
            client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
            results = list(client.agent_engines.memories.retrieve(
                name=agent_engine_id,
                scope=scope,
                similarity_search_params={
                    "search_query": query,
                    "top_k": TOP_K,
                },
            ))
        except Exception:
            # Match ADK preload behavior: drop context silently rather than
            # crash the turn. Real errors surface in Cloud Logs.
            return

        facts = [
            item.memory.fact
            for item in results
            if getattr(item.memory, "fact", None)
        ]
        if not facts:
            return

        body = "\n".join(f"- {f}" for f in facts)
        si = (
            "The following content is from your previous conversations with the user.\n"
            "They may be useful for answering the user's current query.\n"
            "<PAST_CONVERSATIONS>\n"
            f"{body}\n"
            "</PAST_CONVERSATIONS>\n"
        )
        llm_request.append_instructions([si])


# Module-level singleton — drop-in replacement for ADK's preload_memory_tool.
preload_memory_topk_tool = PreloadMemoryTopK()
