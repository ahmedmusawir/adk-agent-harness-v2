# tests/test_eval_runner.py
"""Unit tests for scripts/run_evals.py — all mocked, no live ADK/network calls."""
import asyncio
import json
import sys
import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# run_evals.py lives in scripts/, not a package — add to path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from run_evals import load_cases, load_config, run_case, generate_report, save_report


# ---------------------------------------------------------------------------
# Test 0: Config loading
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_load_config_valid(tmp_path):
    """load_config returns a dict with all required fields."""
    config = {
        "agent": "product_agent_rico_1",
        "project": "ADK Agent Bundle 1",
        "description": "Rico smoke tests",
        "default_dataset": "evals/eval_cases.json",
    }
    f = tmp_path / "eval_config.json"
    f.write_text(json.dumps(config), encoding="utf-8")

    loaded = load_config(str(f))

    assert loaded["agent"] == "product_agent_rico_1"
    assert loaded["project"] == "ADK Agent Bundle 1"
    assert loaded["default_dataset"] == "evals/eval_cases.json"


@pytest.mark.unit
def test_load_config_missing_field_raises(tmp_path):
    """load_config raises ValueError if a required field is missing."""
    config = {
        "agent": "product_agent_rico_1",
        "project": "ADK Agent Bundle 1",
        # missing description and default_dataset
    }
    f = tmp_path / "bad_config.json"
    f.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="description"):
        load_config(str(f))


# ---------------------------------------------------------------------------
# Test 1: JSON parsing — verifies the contract
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_load_cases_valid(tmp_path):
    """load_cases returns a list of dicts with all required fields."""
    cases = [
        {"id": "t1", "input_prompt": "Say hello", "expected_substring": "hello"},
        {"id": "t2", "input_prompt": "Say yes", "expected_substring": "yes"},
    ]
    f = tmp_path / "cases.json"
    f.write_text(json.dumps(cases), encoding="utf-8")

    loaded = load_cases(str(f))

    assert len(loaded) == 2
    assert loaded[0]["id"] == "t1"
    assert loaded[1]["expected_substring"] == "yes"


@pytest.mark.unit
def test_load_cases_missing_field_raises(tmp_path):
    """load_cases raises ValueError if a case is missing a required field."""
    cases = [{"id": "t1", "input_prompt": "Say hello"}]  # missing expected_substring
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(cases), encoding="utf-8")

    with pytest.raises(ValueError, match="expected_substring"):
        load_cases(str(f))


# ---------------------------------------------------------------------------
# Test 2: Mocked eval execution — verifies agent is called + substring checked
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_case_pass():
    """run_case returns PASS when expected substring is found in response."""
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content.parts = [MagicMock(text="The answer is 10")]

    mock_runner = MagicMock()
    mock_runner.run_async = MagicMock(return_value=_async_iter([mock_event]))

    mock_session = MagicMock()
    mock_session.id = "sess-1"
    mock_session_service = MagicMock()
    mock_session_service.create_session = AsyncMock(return_value=mock_session)

    case = {"id": "test_math", "input_prompt": "What is 5+5?", "expected_substring": "10"}
    result = asyncio.run(run_case(mock_runner, mock_session_service, "test_app", case))

    assert result["result"] == "PASS"
    assert result["id"] == "test_math"
    assert result["error"] is None


@pytest.mark.unit
def test_run_case_fail():
    """run_case returns FAIL when expected substring is NOT in response."""
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content.parts = [MagicMock(text="I don't know")]

    mock_runner = MagicMock()
    mock_runner.run_async = MagicMock(return_value=_async_iter([mock_event]))

    mock_session = MagicMock()
    mock_session.id = "sess-2"
    mock_session_service = MagicMock()
    mock_session_service.create_session = AsyncMock(return_value=mock_session)

    case = {"id": "test_math", "input_prompt": "What is 5+5?", "expected_substring": "10"}
    result = asyncio.run(run_case(mock_runner, mock_session_service, "test_app", case))

    assert result["result"] == "FAIL"


@pytest.mark.unit
def test_run_case_substring_check_is_case_insensitive():
    """Substring check must be case-insensitive."""
    mock_event = MagicMock()
    mock_event.is_final_response.return_value = True
    mock_event.content.parts = [MagicMock(text="HELLO there")]

    mock_runner = MagicMock()
    mock_runner.run_async = MagicMock(return_value=_async_iter([mock_event]))

    mock_session = MagicMock()
    mock_session.id = "sess-3"
    mock_session_service = MagicMock()
    mock_session_service.create_session = AsyncMock(return_value=mock_session)

    case = {"id": "test_greet", "input_prompt": "Say hello", "expected_substring": "hello"}
    result = asyncio.run(run_case(mock_runner, mock_session_service, "test_app", case))

    assert result["result"] == "PASS"


@pytest.mark.unit
def test_run_case_error():
    """run_case returns ERROR when the runner raises an exception."""
    mock_runner = MagicMock()
    mock_runner.run_async = MagicMock(return_value=_async_iter_raises(RuntimeError("boom")))

    mock_session = MagicMock()
    mock_session.id = "sess-4"
    mock_session_service = MagicMock()
    mock_session_service.create_session = AsyncMock(return_value=mock_session)

    case = {"id": "test_err", "input_prompt": "Cause an error", "expected_substring": "x"}
    result = asyncio.run(run_case(mock_runner, mock_session_service, "test_app", case))

    assert result["result"] == "ERROR"
    assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# Test 3: Report generation — verifies ASCII summary is formatted + written
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_report_structure():
    """generate_report output contains all required sections."""
    results = [
        {"id": "test_a", "expected_substring": "hello", "result": "PASS", "latency_s": 1.2, "error": None},
        {"id": "test_b", "expected_substring": "yes",   "result": "FAIL", "latency_s": 0.9, "error": None},
    ]
    report = generate_report(results, "product_agent_rico_1")

    assert "Stark Eval v1" in report
    assert "product_agent_rico_1" in report
    assert "test_a" in report
    assert "test_b" in report
    assert "PASS" in report
    assert "FAIL" in report
    assert "Total Cases: 2" in report
    assert "Pass Rate: 50.0%" in report
    assert "Errors: 0" in report


@pytest.mark.unit
def test_generate_report_all_pass():
    """Pass rate is 100% when all cases pass."""
    results = [
        {"id": "t1", "expected_substring": "hi", "result": "PASS", "latency_s": 1.0, "error": None},
        {"id": "t2", "expected_substring": "ok", "result": "PASS", "latency_s": 1.0, "error": None},
    ]
    report = generate_report(results, "test_agent")
    assert "Pass Rate: 100.0%" in report
    assert "Errors: 0" in report


@pytest.mark.unit
def test_save_report_writes_file(tmp_path):
    """save_report creates the directory and writes the correct content."""
    output_dir = str(tmp_path / "evals" / "reports")
    report_text = "# Stark Eval v1\nTotal Cases: 1"

    report_file = save_report(report_text, output_dir)

    assert report_file.exists()
    assert report_file.read_text(encoding="utf-8") == report_text


@pytest.mark.unit
def test_save_report_filename_format(tmp_path):
    """save_report filenames follow eval_YYYY-MM-DD_HHMMSS.txt pattern."""
    import re
    output_dir = str(tmp_path / "reports")
    report_file = save_report("content", output_dir)

    assert re.match(r"eval_\d{4}-\d{2}-\d{2}_\d{6}\.txt", report_file.name)


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

async def _async_iter(items):
    for item in items:
        yield item


async def _async_iter_raises(exc):
    raise exc
    yield  # make it an async generator
