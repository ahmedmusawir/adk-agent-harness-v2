# utils/run_receipt.py
import json
from datetime import datetime, timezone

from utils.token_calculator import count_tokens, estimate_cost

_REQUIRED_KEYS = {
    "timestamp", "agent_name", "model",
    "input_tokens", "output_tokens", "total_tokens",
    "input_cost_usd", "output_cost_usd", "total_cost_usd",
    "latency_ms", "metadata",
}


def create_receipt(
    agent_name: str,
    model: str,
    input_text: str,
    output_text: str,
    latency_ms: float,
    metadata: dict | None = None,
) -> dict:
    """Create a run receipt capturing all metrics for a single agent run.

    Args:
        agent_name: Name of the agent (e.g., "product_agent_rico_1").
        model: Model used (e.g., "gemini-2.5-flash").
        input_text: The user's input / prompt text.
        output_text: The agent's response text.
        latency_ms: Round-trip time in milliseconds.
        metadata: Optional dict for extra info (session_id, user, etc.).

    Returns:
        Receipt dict with 11 keys: timestamp, agent_name, model,
        input_tokens, output_tokens, total_tokens, input_cost_usd,
        output_cost_usd, total_cost_usd, latency_ms, metadata.

    Raises:
        ValueError: If agent_name or model is empty.
    """
    if not agent_name:
        raise ValueError("agent_name must not be empty")
    if not model:
        raise ValueError("model must not be empty")

    input_tokens = count_tokens(input_text, model=model)
    output_tokens = count_tokens(output_text, model=model)
    input_cost = estimate_cost(input_tokens, model=model, direction="input")
    output_cost = estimate_cost(output_tokens, model=model, direction="output")

    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent_name": agent_name,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": input_cost + output_cost,
        "latency_ms": latency_ms,
        "metadata": metadata if metadata is not None else {},
    }


def format_receipt(receipt: dict) -> str:
    """Format a receipt as a human-readable string for logging.

    Returns:
        Multi-line string summary of the receipt.
    """
    total = receipt.get("total_cost_usd", 0)
    return (
        f"─── Run Receipt ───\n"
        f"Agent:   {receipt.get('agent_name', '')}\n"
        f"Model:   {receipt.get('model', '')}\n"
        f"Tokens:  {receipt.get('input_tokens', 0)} in / "
        f"{receipt.get('output_tokens', 0)} out / "
        f"{receipt.get('total_tokens', 0)} total\n"
        f"Cost:    ${total:.6f}\n"
        f"Latency: {receipt.get('latency_ms', 0):.0f}ms\n"
        f"Time:    {receipt.get('timestamp', '')}\n"
        f"────────────────────"
    )


def save_receipt_to_file(receipt: dict, filepath: str) -> None:
    """Append a receipt as a JSON line to a local JSONL file.

    Args:
        receipt: Receipt dict from create_receipt().
        filepath: Path to .jsonl file (created if doesn't exist, appended if exists).

    Raises:
        ValueError: If receipt is missing required keys.
    """
    missing = _REQUIRED_KEYS - set(receipt.keys())
    if missing:
        raise ValueError(f"Receipt missing required keys: {missing}")

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt) + "\n")
