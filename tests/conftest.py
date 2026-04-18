import pytest


@pytest.fixture
def sample_input_text():
    return "What products do you have in stock?"


@pytest.fixture
def sample_output_text():
    return "We have the following products: Widget A ($10), Widget B ($20), and Widget C ($30)."


@pytest.fixture
def sample_receipt():
    """A pre-built receipt for tests that don't need to call the API."""
    return {
        "timestamp": "2026-03-03T14:30:00Z",
        "agent_name": "test_agent",
        "model": "gemini-2.5-flash",
        "input_tokens": 10,
        "output_tokens": 25,
        "total_tokens": 35,
        "input_cost_usd": 0.0000015,
        "output_cost_usd": 0.000015,
        "total_cost_usd": 0.0000165,
        "latency_ms": 1234.5,
        "metadata": {},
    }
