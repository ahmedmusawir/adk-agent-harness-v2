# 1. Import the necessary base library and ADK components.
from google.adk.agents import Agent
from google.adk.tools import google_search
from utils.gcs_utils import fetch_instructions
from callbacks.receipt_callback import get_receipt_callback, get_start_time_callback

# --- Get Instruction Set from gcs bucket ---
def get_live_instructions(ctx) -> str:
    """This function is passed to the Agent and called on every run."""
    return fetch_instructions("jarvis_agent")


# 3. Update the Agent to use the new LiteLLM client
root_agent = Agent(
    name="jarvis_agent",
    model="gemini-2.5-flash",
    # model="gemini-3-flash-preview",
    description="Jarvis agent",
    instruction=get_live_instructions,
    tools=[google_search],
    before_model_callback=get_start_time_callback(),
    after_model_callback=get_receipt_callback(
        agent_name="jarvis_agent",
        model="gemini-2.5-flash",
    ),
)