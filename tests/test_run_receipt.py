import json
import pytest

from utils.run_receipt import create_receipt, format_receipt, save_receipt_to_file

_REQUIRED_KEYS = {
    "timestamp", "agent_name", "model",
    "input_tokens", "output_tokens", "total_tokens",
    "input_cost_usd", "output_cost_usd", "total_cost_usd",
    "latency_ms", "metadata",
}


# ---------------------------------------------------------------------------
# Integration tests — create_receipt() calls count_tokens (hits Vertex AI)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_create_receipt_returns_all_keys(sample_input_text, sample_output_text):
    receipt = create_receipt(
        agent_name="test_agent",
        model="gemini-2.5-flash",
        input_text=sample_input_text,
        output_text=sample_output_text,
        latency_ms=500.0,
    )
    assert set(receipt.keys()) == _REQUIRED_KEYS


@pytest.mark.integration
def test_create_receipt_empty_agent_name_raises(sample_input_text, sample_output_text):
    with pytest.raises(ValueError, match="agent_name"):
        create_receipt(
            agent_name="",
            model="gemini-2.5-flash",
            input_text=sample_input_text,
            output_text=sample_output_text,
            latency_ms=500.0,
        )


@pytest.mark.integration
def test_create_receipt_empty_model_raises(sample_input_text, sample_output_text):
    with pytest.raises(ValueError, match="model"):
        create_receipt(
            agent_name="test_agent",
            model="",
            input_text=sample_input_text,
            output_text=sample_output_text,
            latency_ms=500.0,
        )


@pytest.mark.integration
def test_create_receipt_token_counts_positive(sample_input_text, sample_output_text):
    receipt = create_receipt(
        agent_name="test_agent",
        model="gemini-2.5-flash",
        input_text=sample_input_text,
        output_text=sample_output_text,
        latency_ms=500.0,
    )
    assert receipt["input_tokens"] > 0
    assert receipt["output_tokens"] > 0


@pytest.mark.integration
def test_create_receipt_total_tokens_is_sum(sample_input_text, sample_output_text):
    receipt = create_receipt(
        agent_name="test_agent",
        model="gemini-2.5-flash",
        input_text=sample_input_text,
        output_text=sample_output_text,
        latency_ms=500.0,
    )
    assert receipt["total_tokens"] == receipt["input_tokens"] + receipt["output_tokens"]


@pytest.mark.integration
def test_create_receipt_cost_positive(sample_input_text, sample_output_text):
    receipt = create_receipt(
        agent_name="test_agent",
        model="gemini-2.5-flash",
        input_text=sample_input_text,
        output_text=sample_output_text,
        latency_ms=500.0,
    )
    assert receipt["total_cost_usd"] > 0


@pytest.mark.integration
def test_create_receipt_metadata_default(sample_input_text, sample_output_text):
    receipt = create_receipt(
        agent_name="test_agent",
        model="gemini-2.5-flash",
        input_text=sample_input_text,
        output_text=sample_output_text,
        latency_ms=500.0,
        metadata=None,
    )
    assert receipt["metadata"] == {}


@pytest.mark.integration
def test_create_receipt_metadata_passthrough(sample_input_text, sample_output_text):
    meta = {"session_id": "abc123", "user": "tony"}
    receipt = create_receipt(
        agent_name="test_agent",
        model="gemini-2.5-flash",
        input_text=sample_input_text,
        output_text=sample_output_text,
        latency_ms=500.0,
        metadata=meta,
    )
    assert receipt["metadata"] == meta


# ---------------------------------------------------------------------------
# Unit tests — format_receipt uses pre-built fixture, no API calls
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_format_receipt_contains_agent_name(sample_receipt):
    formatted = format_receipt(sample_receipt)
    assert "test_agent" in formatted


@pytest.mark.unit
def test_format_receipt_contains_cost(sample_receipt):
    formatted = format_receipt(sample_receipt)
    assert "$" in formatted


# ---------------------------------------------------------------------------
# Unit tests — save_receipt_to_file (file I/O only, no API calls)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_save_receipt_creates_file(tmp_path, sample_receipt):
    filepath = str(tmp_path / "receipts.jsonl")
    save_receipt_to_file(sample_receipt, filepath)
    lines = open(filepath).readlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["agent_name"] == "test_agent"


@pytest.mark.unit
def test_save_receipt_appends(tmp_path, sample_receipt):
    filepath = str(tmp_path / "receipts.jsonl")
    save_receipt_to_file(sample_receipt, filepath)
    save_receipt_to_file(sample_receipt, filepath)
    lines = open(filepath).readlines()
    assert len(lines) == 2


@pytest.mark.unit
def test_save_receipt_invalid_receipt_raises(tmp_path):
    filepath = str(tmp_path / "receipts.jsonl")
    incomplete = {"agent_name": "test_agent"}  # missing 10 required keys
    with pytest.raises(ValueError, match="missing required keys"):
        save_receipt_to_file(incomplete, filepath)
