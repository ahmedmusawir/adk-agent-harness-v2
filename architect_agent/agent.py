# 1. Import the necessary base library and ADK components.
from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from utils.gcs_utils import fetch_dual_instructions
from callbacks.receipt_callback import get_receipt_callback, get_start_time_callback, get_timestamp_inject_callback
from architect_agent.tools import write_session_memory_tool, read_session_memory_tool, invoke_skill_tool, get_current_datetime_tool, read_context_doc_tool

# --- Search specialist sub-agent ---
# ADK v1.13.0: google_search (built-in) cannot mix with custom FunctionTools in the same agent.
# Solution: wrap google_search in a dedicated sub-agent, then expose it via AgentTool.
search_specialist = Agent(
    name="search_specialist",
    model="gemini-2.5-flash",
    description="Performs web searches using Google Search.",
    tools=[google_search],
)

# Wrap the sub-agent so it can be used as a tool by the architect agent
search_specialist_tool = AgentTool(agent=search_specialist)


# --- Get Instruction Set from GCS (called on every request — hot reload) ---
def get_live_instructions(ctx) -> str:
    return fetch_dual_instructions("architect_agent")


# --- Architect Agent ---
root_agent = Agent(
    name="architect_agent",
    # model="gemini-2.5-flash",
    # model="gemini-2.5-pro",
    model="gemini-3-flash-preview",
    description="Jarvis agent",
    instruction=get_live_instructions,
    tools=[
        search_specialist_tool,
        write_session_memory_tool,
        read_session_memory_tool,
        invoke_skill_tool,
        get_current_datetime_tool,
        read_context_doc_tool,
    ],
    # ADK supports a list of before_model_callbacks — they run in order.
    # 1. get_start_time_callback: records run start time for receipt latency tracking
    # 2. get_timestamp_inject_callback: injects [SYSTEM_TIMESTAMP] into system instruction
    before_model_callback=[
        get_start_time_callback(),
        get_timestamp_inject_callback(),
    ],
    after_model_callback=get_receipt_callback(
        agent_name="architect_agent",
        model="gemini-3-flash-preview",
    ),
)