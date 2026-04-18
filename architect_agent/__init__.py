from .agent import root_agent

# Register custom LLM-as-a-Judge eval metrics with ADK's evaluator registry.
# Runs at import time so metrics appear in the adk web Eval tab on startup.
from .eval_metrics import register_custom_metrics
register_custom_metrics()