# /product_agent/agent.py
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from utils.gcs_utils import fetch_instructions
from utils.context_utils import fetch_context
from callbacks.receipt_callback import get_receipt_callback, get_start_time_callback

# --- Tool and Instruction logic ---
product_context_tool = FunctionTool(func=fetch_context)

def get_live_instructions(ctx) -> str:
    return fetch_instructions("product_agent")

# 3. Update the Agent to use the new Vertex
root_agent = Agent(
    name="product_agent_rico_1",
    model="gemini-2.5-flash",
    # model="gemini-3-flash-preview",
    description="Product Specialist agent",
    instruction=get_live_instructions,
    tools=[product_context_tool],
    before_model_callback=get_start_time_callback(),
    after_model_callback=get_receipt_callback(
        agent_name="product_agent_rico_1",
        model="gemini-2.5-flash",
    ),
)
