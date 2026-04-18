import pytest

from utils.context_cache import (
    create_cache,
    delete_cache,
    estimate_cache_savings,
    get_cache,
    list_caches,
)

# ---------------------------------------------------------------------------
# Shared instruction fixture — must exceed 4,500 tokens for Gemini 2.5 cache
# minimum (350 repetitions ≈ 5,600 tokens, well above the 2,048+ threshold).
# ---------------------------------------------------------------------------

_BIG_INSTRUCTION = (
    "You are a helpful assistant. "
    + "This is filler content for context caching integration tests. " * 350
)

_MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Integration tests — hit Vertex AI (create/get/delete/list real caches)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_cache_name():
    """Create one cache for the test module, tear it down after all tests."""
    name = create_cache(
        model=_MODEL,
        system_instruction=_BIG_INSTRUCTION,
        ttl_seconds=300,
    )
    yield name
    delete_cache(name)


@pytest.mark.integration
def test_create_cache_returns_name():
    name = create_cache(
        model=_MODEL,
        system_instruction=_BIG_INSTRUCTION,
        ttl_seconds=300,
    )
    assert isinstance(name, str)
    assert "cachedContents" in name
    delete_cache(name)


@pytest.mark.integration
def test_create_cache_with_tools():
    from google.genai.types import Tool, GoogleSearch
    name = create_cache(
        model=_MODEL,
        system_instruction=_BIG_INSTRUCTION,
        ttl_seconds=300,
        tools=[Tool(google_search=GoogleSearch())],
    )
    assert isinstance(name, str)
    assert "cachedContents" in name
    delete_cache(name)


@pytest.mark.integration
def test_create_cache_empty_model_raises():
    with pytest.raises(ValueError, match="model"):
        create_cache(model="", system_instruction=_BIG_INSTRUCTION)


@pytest.mark.integration
def test_create_cache_empty_instruction_raises():
    with pytest.raises(ValueError, match="system_instruction"):
        create_cache(model=_MODEL, system_instruction="")


@pytest.mark.integration
def test_get_cache_returns_cached_content(live_cache_name):
    result = get_cache(live_cache_name)
    assert result is not None
    assert result.name == live_cache_name


@pytest.mark.integration
def test_get_cache_not_found_returns_none():
    result = get_cache("projects/000/locations/us-central1/cachedContents/does-not-exist")
    assert result is None


@pytest.mark.integration
def test_delete_cache_returns_true():
    name = create_cache(
        model=_MODEL,
        system_instruction=_BIG_INSTRUCTION,
        ttl_seconds=300,
    )
    assert delete_cache(name) is True


@pytest.mark.integration
def test_delete_cache_not_found_returns_false():
    result = delete_cache("projects/000/locations/us-central1/cachedContents/does-not-exist")
    assert result is False


@pytest.mark.integration
def test_list_caches_returns_list(live_cache_name):
    result = list_caches()
    assert isinstance(result, list)


@pytest.mark.integration
def test_list_caches_model_filter(live_cache_name):
    filtered = list_caches(model_filter=_MODEL)
    assert isinstance(filtered, list)
    for cache in filtered:
        assert _MODEL in (cache.model or "")


# ---------------------------------------------------------------------------
# Unit tests — no API calls
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_estimate_cache_savings_flash_90pct():
    result = estimate_cache_savings(1_000_000, model="gemini-2.5-flash")
    assert result["savings_pct"] == pytest.approx(90.0)


@pytest.mark.unit
def test_estimate_cache_savings_cached_cost_is_10pct_of_regular():
    result = estimate_cache_savings(500_000, model="gemini-2.5-flash")
    assert result["cached_cost_usd"] == pytest.approx(result["regular_cost_usd"] * 0.10)


@pytest.mark.unit
def test_estimate_cache_savings_unknown_model_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        estimate_cache_savings(1000, model="gemini-99-ultramax")
