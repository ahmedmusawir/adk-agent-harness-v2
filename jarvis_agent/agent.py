# 1. Import the necessary base library and ADK components.
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import google_search
from google.adk.tools.preload_memory_tool import preload_memory_tool
from utils.gcs_utils import fetch_instructions
from callbacks.receipt_callback import get_receipt_callback, get_start_time_callback

# --- Get Instruction Set from gcs bucket ---
def get_live_instructions(ctx) -> str:
    """This function is passed to the Agent and called on every run."""
    return fetch_instructions("jarvis_agent")


# preload_memory_tool runs silently before every LLM request: it uses the
# current user message as a semantic search query against the wired memory
# service (Vertex AI Memory Bank) and injects matching memories into the
# system prompt as <PAST_CONVERSATIONS>. Requires adk web/api_server to be
# started with --memory_service_uri=agentengine://<engine_id> - otherwise
# the tool errors at turn time. See memory_bank_discovery/scripts/run_jarvis_web.sh.


# --- Memory write-back callback (Test 7b) ---
# Writes the current session to Vertex AI Memory Bank every
# EXTRACT_EVERY_N_TURNS turns. ADK has no true session-end hook
# (verified in base_agent.py — after_agent_callback fires per TURN,
# not per session), so we gate the expensive add_session_to_memory
# call with a session-state turn counter. Consolidation verified in
# Test 6 means re-extracting across gated windows emits UPDATED
# actions rather than creating duplicates — gate is a cost
# optimization, not a correctness requirement.
EXTRACT_EVERY_N_TURNS = 2


async def persist_session_to_memory_callback(callback_context: CallbackContext) -> None:
    # IMPORTANT: mutate state via callback_context.state (the delta-aware wrapper),
    # NOT via ctx.session.state (raw dict). Only the wrapper's writes get committed
    # to the session store via the state_delta → Event → session_service flow. Raw
    # dict mutations are lost across turns.
    state = callback_context.state
    turn = state.get("memory_turn_count", 0) + 1
    state["memory_turn_count"] = turn
    print(f"[persist_session_to_memory_callback] turn={turn} (gate every {EXTRACT_EVERY_N_TURNS})")
    if turn % EXTRACT_EVERY_N_TURNS != 0:
        return

    # _invocation_context is the documented access path for memory_service per
    # google's ADK docs (adk.dev/sessions/memory).
    ctx = callback_context._invocation_context
    if ctx.memory_service is None:
        # No memory service wired (e.g., adk started without --memory_service_uri).
        # Silently skip so Jarvis still works in non-memory mode.
        print("[persist_session_to_memory_callback] no memory_service wired — skipping")
        return
    print(f"[persist_session_to_memory_callback] WRITING session to memory at turn {turn}...")
    await ctx.memory_service.add_session_to_memory(ctx.session)
    print("[persist_session_to_memory_callback] write complete")


# 3. Update the Agent to use the new LiteLLM client
root_agent = Agent(
    name="jarvis_agent",
    model="gemini-3.1-pro-preview",
    # model="gemini-2.5-flash",
    # model="gemini-3-flash-preview",
    description="Jarvis agent",
    instruction=get_live_instructions,
    tools=[google_search, preload_memory_tool],
    before_model_callback=get_start_time_callback(),
    after_model_callback=get_receipt_callback(
        agent_name="jarvis_agent",
        model="gemini-3.1-pro-preview",
        # model="gemini-2.5-flash",
    ),
    after_agent_callback=persist_session_to_memory_callback,
)