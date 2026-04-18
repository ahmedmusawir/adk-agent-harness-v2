# utils/token_calculator.py
import os
from google import genai

# --- Pricing Table (USD per 1M tokens) ---
# Confirmed rates from Google AI pricing page.
# Entries marked # ESTIMATE use the closest tier equivalent — update when official pricing published.
_PRICING = {
    # --- Gemini 2.0 ---
    "gemini-2.0-flash": {
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
        "context_window": 1_048_576,
    },
    "gemini-2.0-flash-lite": {
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
        "context_window": 1_048_576,
    },
    # --- Gemini 2.5 ---
    "gemini-2.5-flash": {
        "input_per_1m": 0.15,
        "output_per_1m": 0.60,
        "context_window": 1_048_576,
    },
    "gemini-2.5-flash-lite": {  # ESTIMATE — update when official pricing published
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
        "context_window": 1_048_576,
    },
    "gemini-2.5-pro": {
        "input_per_1m": 1.25,
        "output_per_1m": 10.00,
        "context_window": 1_048_576,
    },
    # --- Gemini 3 previews (estimates — no official pricing yet) ---
    "gemini-3-flash-preview": {  # ESTIMATE — update when official pricing published
        "input_per_1m": 0.15,
        "output_per_1m": 0.60,
        "context_window": 1_048_576,
    },
    "gemini-3-pro-preview": {  # ESTIMATE — update when official pricing published
        "input_per_1m": 1.25,
        "output_per_1m": 10.00,
        "context_window": 1_048_576,
    },
    "gemini-3.1-pro-preview": {  # ESTIMATE — update when official pricing published
        "input_per_1m": 1.25,
        "output_per_1m": 10.00,
        "context_window": 1_048_576,
    },
    "gemini-3.1-flash-lite-preview": {  # ESTIMATE — update when official pricing published
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
        "context_window": 1_048_576,
    },
}


def count_tokens(content: str, model: str = "gemini-2.5-flash") -> int:
    """Count tokens for a string using Vertex AI's token counting API.

    Args:
        content: The text to count tokens for.
        model: Gemini model name to count against (default: gemini-2.5-flash).

    Returns:
        Token count as integer.

    Raises:
        ValueError: If content is empty.
        RuntimeError: If Vertex AI token counting fails.
    """
    if not content:
        raise ValueError("content must not be empty")

    try:
        client = genai.Client(
            vertexai=True,
            project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
        result = client.models.count_tokens(model=model, contents=content)
        return result.total_tokens or 0
    except Exception as e:
        raise RuntimeError(f"Vertex AI token counting failed: {e}") from e


def estimate_cost(
    token_count: int,
    model: str = "gemini-2.5-flash",
    direction: str = "input",
) -> float:
    """Estimate cost in USD for a given token count.

    Args:
        token_count: Number of tokens.
        model: Gemini model name.
        direction: "input" or "output".

    Returns:
        Estimated cost in USD as float.

    Raises:
        ValueError: If direction is not "input" or "output".
        ValueError: If model is not in the pricing table.
    """
    if direction not in ("input", "output"):
        raise ValueError(f"direction must be 'input' or 'output', got '{direction}'")
    if model not in _PRICING:
        raise ValueError(f"Unknown model '{model}'. Known models: {list(_PRICING.keys())}")

    rate = _PRICING[model][f"{direction}_per_1m"]
    return (token_count / 1_000_000) * rate


def get_model_pricing(model: str = "gemini-2.5-flash") -> dict:
    """Return pricing info for a model.

    Args:
        model: Gemini model name.

    Returns:
        {"input_per_1m": float, "output_per_1m": float, "context_window": int}

    Raises:
        ValueError: If model is not in the pricing table.
    """
    if model not in _PRICING:
        raise ValueError(f"Unknown model '{model}'. Known models: {list(_PRICING.keys())}")
    return _PRICING[model].copy()
