# 1. Import the necessary base library and ADK components.
import os

import vertexai

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.preload_memory_tool import preload_memory_tool
from google.adk.tools.tool_context import ToolContext

from utils.gcs_utils import fetch_instructions
from callbacks.receipt_callback import get_receipt_callback, get_start_time_callback


# Memory Bank targeting — same project/region as our discovery sandbox.
# AGENT_ENGINE_ID comes from os.environ; run_jarvis_web.sh sources
# memory_bank_discovery/.env before starting adk web.
PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"


# Appended to the GCS-hosted system prompt so the model knows what tools
# it has and when to use each.
MEMORY_TOOL_INSTRUCTION = (
    "You have a remember_fact tool for long-term memory. "
    "Use it when the user shares a personal preference, a hard constraint, "
    "corrects something you previously believed, or explicitly asks you to "
    "remember something. Do not use it for small talk or transient details. "
    "When you use it, briefly confirm to the user what you saved. "
    "You also have a search_agent tool for web search — delegate to it when "
    "the user asks about current events or facts you don't already know."
)


# Search sub-agent: exists solely to isolate google_search (a native Gemini
# search tool) from Jarvis's tool list. Gemini forbids mixing native search
# with function tools in the same LLM call, so we wrap google_search in its
# own agent and expose it to Jarvis via AgentTool (which is a function tool
# from Jarvis's POV).
search_agent = Agent(
    name="search_agent",
    model="gemini-2.5-flash",
    description="Performs web searches using Google Search grounding.",
    instruction=(
        "You are a search specialist. Given a query, use Google Search "
        "to find relevant current information and return a concise, "
        "factual summary. Cite specifics when possible."
    ),
    tools=[google_search],
)

# AgentTool makes the search sub-agent callable as a tool from Jarvis.
search_agent_tool = AgentTool(agent=search_agent)


# --- Get Instruction Set from gcs bucket ---
def get_live_instructions(ctx) -> str:
    """This function is passed to the Agent and called on every run."""
    return fetch_instructions("jarvis_agent") + "\n\n" + MEMORY_TOOL_INSTRUCTION


# preload_memory_tool runs silently before every LLM request: it uses the
# current user message as a semantic search query against the wired memory
# service (Vertex AI Memory Bank) and injects matching memories into the
# system prompt as <PAST_CONVERSATIONS>. Requires adk web/api_server to be
# started with --memory_service_uri=agentengine://<engine_id> — otherwise
# the tool errors at turn time. See memory_bank_discovery/scripts/run_jarvis_web.sh.


def remember_fact(fact: str, tool_context: ToolContext) -> str:
    """Saves an important fact to long-term memory. Use this when the user
    states a personal preference, a firm constraint, a correction to
    something previously known, or explicitly asks you to remember
    something. Do not use for greetings, small talk, or transient details.
    """
    agent_engine_id = os.environ.get("AGENT_ENGINE_ID")
    if not agent_engine_id:
        return "Failed to remember fact: AGENT_ENGINE_ID not set in environment."
    try:
        # Two-key scope so memories are retrievable by preload_memory_tool,
        # which reads with {app_name, user_id} via VertexAiMemoryBankService.
        session = tool_context._invocation_context.session
        scope = {
            "app_name": session.app_name or "jarvis_agent",
            "user_id":  session.user_id  or "user",
        }
        client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
        client.agent_engines.memories.create(
            name=agent_engine_id,
            fact=fact,
            scope=scope,
        )
        return f"Remembered: {fact}"
    except Exception as e:
        return f"Failed to remember fact: {type(e).__name__}: {e}"


# 3. Update the Agent to use the new LiteLLM client
root_agent = Agent(
    name="jarvis_agent",
    model="gemini-2.5-flash",
    # model="gemini-3-flash-preview",
    description="Jarvis agent",
    instruction=get_live_instructions,
    tools=[preload_memory_tool, remember_fact, search_agent_tool],
    before_model_callback=get_start_time_callback(),
    after_model_callback=get_receipt_callback(
        agent_name="jarvis_agent",
        model="gemini-2.5-flash",
    ),
)
