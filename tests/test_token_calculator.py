import pytest
from utils.token_calculator import count_tokens, estimate_cost, get_model_pricing


# ---------------------------------------------------------------------------
# Unit tests — pure logic, no Vertex AI calls
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_estimate_cost_input():
    cost = estimate_cost(1_000_000, model="gemini-2.5-flash", direction="input")
    assert abs(cost - 0.15) < 0.0001


@pytest.mark.unit
def test_estimate_cost_output():
    cost = estimate_cost(1_000_000, model="gemini-2.5-flash", direction="output")
    assert abs(cost - 0.60) < 0.0001


@pytest.mark.unit
def test_estimate_cost_invalid_direction():
    with pytest.raises(ValueError, match="direction"):
        estimate_cost(1000, model="gemini-2.5-flash", direction="sideways")


@pytest.mark.unit
def test_estimate_cost_unknown_model():
    with pytest.raises(ValueError, match="Unknown model"):
        estimate_cost(1000, model="gpt-4")


@pytest.mark.unit
def test_get_model_pricing_returns_dict():
    pricing = get_model_pricing("gemini-2.5-flash")
    assert isinstance(pricing, dict)
    assert "input_per_1m" in pricing
    assert "output_per_1m" in pricing
    assert "context_window" in pricing


@pytest.mark.unit
def test_get_model_pricing_unknown_model():
    with pytest.raises(ValueError, match="Unknown model"):
        get_model_pricing("gpt-4")


@pytest.mark.unit
def test_estimate_cost_gemini_20_flash_lite():
    """Confirmed rate: $0.075 input / $0.30 output per 1M tokens."""
    cost = estimate_cost(1_000_000, model="gemini-2.0-flash-lite", direction="input")
    assert abs(cost - 0.075) < 0.0001


@pytest.mark.unit
def test_estimate_cost_gemini_3_flash_preview():
    """Preview model uses flash-tier estimate: $0.15 input per 1M tokens."""
    cost = estimate_cost(1_000_000, model="gemini-3-flash-preview", direction="input")
    assert abs(cost - 0.15) < 0.0001


@pytest.mark.unit
def test_all_pricing_models_have_required_keys():
    """Every entry in _PRICING must have the three required keys."""
    from utils.token_calculator import _PRICING
    required_keys = {"input_per_1m", "output_per_1m", "context_window"}
    for model_name, data in _PRICING.items():
        assert required_keys.issubset(data.keys()), (
            f"Model '{model_name}' missing keys: {required_keys - data.keys()}"
        )


@pytest.mark.unit
def test_count_tokens_empty_string_raises():
    with pytest.raises(ValueError):
        count_tokens("")


# ---------------------------------------------------------------------------
# Integration tests — call Vertex AI (require credentials, cost tokens)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_count_tokens_returns_positive():
    count = count_tokens("Hello, how can I help you today?")
    assert count > 0


@pytest.mark.integration
def test_count_tokens_default_model():
    count = count_tokens("What products do you sell?")
    assert isinstance(count, int)
    assert count > 0


@pytest.mark.integration
def test_count_tokens_explicit_model():
    count = count_tokens("What products do you sell?", model="gemini-2.5-pro")
    assert isinstance(count, int)
    assert count > 0
