# utils/context_cache.py
import os
from typing import Optional

from google import genai
from google.genai.errors import ClientError
from google.genai.types import CreateCachedContentConfig

from utils.token_calculator import _PRICING

# Cached token rate = 10% of regular input price (90% discount)
_CACHE_DISCOUNT = 0.10


def _client() -> genai.Client:
    return genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )


def create_cache(
    model: str,
    system_instruction: str,
    ttl_seconds: int = 3600,
    tools: Optional[list] = None,
) -> str:
    """Create a Vertex AI context cache. Returns the cache resource name.

    Args:
        model: Gemini model name (e.g., "gemini-2.5-flash").
        system_instruction: Text to cache as the system instruction.
        ttl_seconds: Cache time-to-live in seconds (default: 3600 = 1 hour).
        tools: Optional list of Tool objects to bake into the cache.
               IMPORTANT: Do NOT also pass tools in generate_content() config
               when using cached_content — the API rejects that combination.
               Bake tools here instead.

    Returns:
        Cache resource name string (e.g., "projects/.../cachedContents/...").

    Raises:
        ValueError: If model or system_instruction is empty.
        RuntimeError: If cache creation fails.
    """
    if not model:
        raise ValueError("model must not be empty")
    if not system_instruction:
        raise ValueError("system_instruction must not be empty")

    config = CreateCachedContentConfig(
        system_instruction=system_instruction,
        ttl=f"{ttl_seconds}s",
        tools=tools,
    )

    try:
        cache = _client().caches.create(model=model, config=config)
        return cache.name
    except Exception as e:
        raise RuntimeError(f"Cache creation failed: {e}") from e


def get_cache(cache_name: str):
    """Return a CachedContent object by resource name, or None if not found.

    Args:
        cache_name: Full resource name returned by create_cache().

    Returns:
        CachedContent object, or None if the cache does not exist.
    """
    try:
        return _client().caches.get(name=cache_name)
    except ClientError:
        return None


def delete_cache(cache_name: str) -> bool:
    """Delete a cache by resource name.

    Args:
        cache_name: Full resource name returned by create_cache().

    Returns:
        True if deleted, False if the cache was not found.
    """
    try:
        _client().caches.delete(name=cache_name)
        return True
    except ClientError:
        return False


def list_caches(model_filter: Optional[str] = None) -> list:
    """List all active context caches, optionally filtered by model.

    Args:
        model_filter: If provided, only return caches for this model name.
                      The API does not support server-side model filtering —
                      this is done client-side.

    Returns:
        List of CachedContent objects.
    """
    try:
        pager = _client().caches.list()
        caches = list(pager)
    except Exception as e:
        raise RuntimeError(f"Cache list failed: {e}") from e

    if model_filter is None:
        return caches

    return [c for c in caches if model_filter in (c.model or "")]


def estimate_cache_savings(
    token_count: int,
    model: str = "gemini-2.5-flash",
) -> dict:
    """Estimate cost savings from caching a token count vs. paying full price.

    Cached tokens are billed at 10% of the regular input rate (90% discount).

    Args:
        token_count: Number of tokens that would be cached.
        model: Gemini model name.

    Returns:
        Dict with keys:
            regular_cost_usd: Cost at full input price.
            cached_cost_usd:  Cost at cached rate (10% of regular).
            savings_usd:      Absolute saving.
            savings_pct:      Percentage saved (e.g., 90.0).

    Raises:
        ValueError: If model is not in the pricing table.
    """
    if model not in _PRICING:
        raise ValueError(f"Unknown model '{model}'. Known models: {list(_PRICING.keys())}")

    input_rate = _PRICING[model]["input_per_1m"]
    regular_cost = (token_count / 1_000_000) * input_rate
    cached_cost = regular_cost * _CACHE_DISCOUNT
    savings = regular_cost - cached_cost

    return {
        "regular_cost_usd": regular_cost,
        "cached_cost_usd": cached_cost,
        "savings_usd": savings,
        "savings_pct": round((savings / regular_cost) * 100, 2) if regular_cost > 0 else 0.0,
    }
