"""Tests for the Stark Eval Runner (scripts/run_stark_evals.py)."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure repo root on path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_stark_evals import (
    compute_delta,
    compute_flags,
    find_latest_baseline,
    format_md_report,
    get_custom_metric_names,
    save_reports,
)

from google.genai import types as genai_types
from google.adk.evaluation.eval_case import IntermediateData, Invocation
from google.adk.evaluation.eval_metrics import EvalMetric
from google.adk.evaluation.evaluator import EvalStatus
from architect_agent.eval_metrics import (
    SkillInvocationToolUseEvaluator,
    ContextDocToolUseEvaluator,
    TemporalAwarenessEvaluator,
    EngineerPromptFormatEvaluator,
)


@pytest.mark.unit
class TestRunnerFindsRegisteredMetrics:
    """Verifies the runner discovers custom metrics from the registry."""

    def test_runner_finds_registered_metrics(self):
        """Custom metrics are discoverable via get_custom_metric_names."""
        names = get_custom_metric_names()
        assert "session_memory_tool_use" in names
        assert "stays_in_role" in names
        # Built-in metrics must NOT appear
        assert "tool_trajectory_avg_score" not in names
        assert "response_match_score" not in names


@pytest.mark.unit
class TestRunnerGeneratesBothFiles:
    """Verifies the runner produces .json and .md report files."""

    def test_runner_generates_both_files(self):
        """save_reports creates both .json and .md with matching run_id."""
        results = {
            "run_id": "eval_2026-04-16_120000_test",
            "timestamp_utc": "2026-04-16T12:00:00Z",
            "eval_set": "TEST_SET",
            "judge_model": "gemini-2.5-flash",
            "baseline_run_id": None,
            "metrics_summary": {
                "session_memory_tool_use": {
                    "avg_score": 1.0,
                    "cases_run": 1,
                    "vs_baseline": "—",
                }
            },
            "cases_completed": 1,
            "cases_errored": 0,
            "per_case_results": [],
        }
        md_report = "# Test Report\nContent here"

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)
            json_path, md_path = save_reports(results, md_report, reports_dir)

            # Both files exist
            assert json_path.exists()
            assert md_path.exists()

            # Same run_id in filenames
            assert "eval_2026-04-16_120000_test" in json_path.name
            assert "eval_2026-04-16_120000_test" in md_path.name

            # JSON is valid and matches
            with open(json_path) as f:
                loaded = json.load(f)
            assert loaded["run_id"] == "eval_2026-04-16_120000_test"
            assert loaded["eval_set"] == "TEST_SET"

            # MD content matches
            assert md_path.read_text() == md_report


@pytest.mark.unit
class TestBaselineComparison:
    """Verifies baseline delta computation."""

    def test_baseline_comparison_with_prior_run(self):
        """Delta is computed correctly when a baseline exists."""
        baseline = {
            "run_id": "eval_2026-04-15_100000_test",
            "metrics_summary": {
                "session_memory_tool_use": {"avg_score": 0.8, "cases_run": 1},
            },
        }
        # Current score 1.0 vs baseline 0.8 → delta +0.200
        delta = compute_delta(1.0, baseline, "session_memory_tool_use")
        assert delta == "+0.200"

        # Current score 0.5 vs baseline 0.8 → delta -0.300
        delta = compute_delta(0.5, baseline, "session_memory_tool_use")
        assert delta == "-0.300"

    def test_baseline_comparison_no_prior_run(self):
        """First run handles missing baseline gracefully."""
        delta = compute_delta(1.0, None, "session_memory_tool_use")
        assert delta == "—"

    def test_baseline_missing_metric(self):
        """Baseline exists but doesn't have this metric."""
        baseline = {
            "run_id": "eval_2026-04-15_100000_test",
            "metrics_summary": {},
        }
        delta = compute_delta(1.0, baseline, "new_metric")
        assert delta == "—"

    def test_find_latest_baseline(self):
        """find_latest_baseline picks the most recent file by name sort."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)

            # Create two baseline files
            older = {"run_id": "eval_2026-04-14_100000_test_set", "metrics_summary": {}}
            newer = {"run_id": "eval_2026-04-15_100000_test_set", "metrics_summary": {}}

            (reports_dir / "eval_2026-04-14_100000_test_set.json").write_text(json.dumps(older))
            (reports_dir / "eval_2026-04-15_100000_test_set.json").write_text(json.dumps(newer))

            result = find_latest_baseline("test_set", reports_dir)
            assert result is not None
            assert result["run_id"] == "eval_2026-04-15_100000_test_set"

    def test_find_latest_baseline_no_files(self):
        """No baseline files returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = find_latest_baseline("nonexistent", Path(tmpdir))
            assert result is None


@pytest.mark.unit
class TestErrorCaseHandling:
    """Verifies that errors in one evaluator don't crash the runner."""

    def test_compute_flags_tool_not_called(self):
        """Tool-use metric with score 0 produces tool_not_called flag."""
        flags = compute_flags("session_memory_tool_use", 0.0)
        assert "tool_not_called" in flags

    def test_compute_flags_role_break(self):
        """Rubric metric with low score produces correct flag."""
        flags = compute_flags("stays_in_role", 0.0)
        assert "role_break" in flags

    def test_compute_flags_passing(self):
        """Perfect score produces no flags."""
        flags = compute_flags("session_memory_tool_use", 1.0)
        assert flags == []
        flags = compute_flags("stays_in_role", 1.0)
        assert flags == []


@pytest.mark.unit
class TestMdReportFormat:
    """Verifies the .md report uses box-drawing characters."""

    def test_report_has_box_drawing_chars(self):
        """Report uses Unicode box-drawing, not pipe tables."""
        results = {
            "run_id": "eval_2026-04-16_120000_test",
            "timestamp_utc": "2026-04-16T12:00:00Z",
            "eval_set": "TEST_SET",
            "judge_model": "gemini-2.5-flash",
            "baseline_run_id": None,
            "metrics_summary": {
                "session_memory_tool_use": {
                    "avg_score": 1.0,
                    "cases_run": 1,
                    "vs_baseline": "—",
                }
            },
            "cases_completed": 1,
            "cases_errored": 0,
            "per_case_results": [
                {
                    "case_id": "test_case",
                    "case_prompt": "What did we work on?",
                    "metric_scores": {
                        "session_memory_tool_use": {
                            "score": 1.0,
                            "status": "PASS",
                            "flags": [],
                            "reasoning": "",
                        }
                    },
                }
            ],
        }
        md = format_md_report(results)

        # Box-drawing characters present
        assert "┌" in md
        assert "┐" in md
        assert "└" in md
        assert "┘" in md
        assert "├" in md
        assert "┤" in md
        assert "┼" in md
        assert "─" in md
        assert "│" in md

        # Header content
        assert "Stark Eval" in md
        assert "TEST_SET" in md

    def test_report_has_flagged_section_when_failures_exist(self):
        """Flagged Cases section appears when scores are below 1.0."""
        results = {
            "run_id": "eval_2026-04-16_120000_test",
            "timestamp_utc": "2026-04-16T12:00:00Z",
            "eval_set": "TEST_SET",
            "judge_model": "gemini-2.5-flash",
            "baseline_run_id": None,
            "metrics_summary": {
                "stays_in_role": {
                    "avg_score": 0.0,
                    "cases_run": 1,
                    "vs_baseline": "—",
                }
            },
            "cases_completed": 1,
            "cases_errored": 0,
            "per_case_results": [
                {
                    "case_id": "pizza_test",
                    "case_prompt": "What is the best pizza?",
                    "metric_scores": {
                        "stays_in_role": {
                            "score": 0.0,
                            "status": "FAIL",
                            "flags": ["role_break"],
                            "reasoning": "Agent recommended pizza.",
                        }
                    },
                }
            ],
        }
        md = format_md_report(results)
        assert "## Flagged Cases" in md
        assert "pizza_test" in md
        assert "role_break" in md
        assert "Agent recommended pizza." in md


# ── Helpers for building mock invocations ──

def _make_invocation(
    user_text: str = "test prompt",
    response_text: str = "test response",
    tool_names: list[str] | None = None,
) -> Invocation:
    """Build a minimal Invocation for testing."""
    tool_uses = []
    if tool_names:
        tool_uses = [
            genai_types.FunctionCall(name=name, args={})
            for name in tool_names
        ]
    return Invocation(
        user_content=genai_types.Content(
            parts=[genai_types.Part(text=user_text)],
            role="user",
        ),
        final_response=genai_types.Content(
            parts=[genai_types.Part(text=response_text)],
            role="model",
        ),
        intermediate_data=IntermediateData(tool_uses=tool_uses),
    )


def _run_evaluator(evaluator_cls, invocation):
    """Run a deterministic evaluator against a single invocation."""
    eval_metric = EvalMetric(metric_name="test", threshold=0.5)
    evaluator = evaluator_cls(eval_metric=eval_metric)
    result = evaluator.evaluate_invocations([invocation], [invocation])
    return result


# ── Phase B: Deterministic evaluator tests ──

@pytest.mark.unit
class TestSkillInvocationToolUse:
    """Tests for SkillInvocationToolUseEvaluator."""

    def test_passes_when_invoke_skill_called(self):
        inv = _make_invocation(tool_names=["invoke_skill", "read_session_memory"])
        result = _run_evaluator(SkillInvocationToolUseEvaluator, inv)
        assert result.overall_score == 1.0
        assert result.overall_eval_status == EvalStatus.PASSED

    def test_fails_when_invoke_skill_not_called(self):
        inv = _make_invocation(tool_names=["read_session_memory"])
        result = _run_evaluator(SkillInvocationToolUseEvaluator, inv)
        assert result.overall_score == 0.0
        assert result.overall_eval_status == EvalStatus.FAILED

    def test_fails_when_no_tools_called(self):
        inv = _make_invocation(tool_names=[])
        result = _run_evaluator(SkillInvocationToolUseEvaluator, inv)
        assert result.overall_score == 0.0


@pytest.mark.unit
class TestContextDocToolUse:
    """Tests for ContextDocToolUseEvaluator."""

    def test_passes_when_read_context_doc_called(self):
        inv = _make_invocation(tool_names=["invoke_skill", "read_context_doc"])
        result = _run_evaluator(ContextDocToolUseEvaluator, inv)
        assert result.overall_score == 1.0

    def test_fails_when_read_context_doc_not_called(self):
        inv = _make_invocation(tool_names=["invoke_skill", "invoke_skill"])
        result = _run_evaluator(ContextDocToolUseEvaluator, inv)
        assert result.overall_score == 0.0


@pytest.mark.unit
class TestTemporalAwareness:
    """Tests for TemporalAwarenessEvaluator (NEGATIVE check)."""

    def test_passes_when_get_current_datetime_not_called(self):
        inv = _make_invocation(tool_names=["invoke_skill", "read_session_memory"])
        result = _run_evaluator(TemporalAwarenessEvaluator, inv)
        assert result.overall_score == 1.0
        assert result.overall_eval_status == EvalStatus.PASSED

    def test_fails_when_get_current_datetime_called(self):
        inv = _make_invocation(tool_names=["get_current_datetime", "invoke_skill"])
        result = _run_evaluator(TemporalAwarenessEvaluator, inv)
        assert result.overall_score == 0.0
        assert result.overall_eval_status == EvalStatus.FAILED

    def test_passes_when_no_tools_called(self):
        inv = _make_invocation(tool_names=[])
        result = _run_evaluator(TemporalAwarenessEvaluator, inv)
        assert result.overall_score == 1.0


@pytest.mark.unit
class TestEngineerPromptFormat:
    """Tests for EngineerPromptFormatEvaluator."""

    def test_passes_with_all_four_sections(self):
        response = """
        ## TASK
        Add a new tool to the harness.

        ## SCOPE
        Only architect_agent/tools.py.

        ## CONSTRAINTS
        Do not modify callbacks.

        ## DONE LOOKS LIKE
        All tests pass.
        """
        inv = _make_invocation(response_text=response)
        result = _run_evaluator(EngineerPromptFormatEvaluator, inv)
        assert result.overall_score == 1.0

    def test_partial_score_with_two_sections(self):
        response = """
        ## TASK
        Add a new tool.

        ## SCOPE
        Only tools.py.
        """
        inv = _make_invocation(response_text=response)
        result = _run_evaluator(EngineerPromptFormatEvaluator, inv)
        assert result.overall_score == 0.5

    def test_fails_with_no_sections(self):
        response = "Here is how to add a tool: just edit tools.py and add a function."
        inv = _make_invocation(response_text=response)
        result = _run_evaluator(EngineerPromptFormatEvaluator, inv)
        assert result.overall_score == 0.0

    def test_case_insensitive_matching(self):
        response = "task: do thing\nscope: here\nconstraints: none\ndone looks like: works"
        inv = _make_invocation(response_text=response)
        result = _run_evaluator(EngineerPromptFormatEvaluator, inv)
        assert result.overall_score == 1.0


@pytest.mark.unit
class TestAllSevenMetricsRegistered:
    """Verifies all 7 custom metrics are in the registry."""

    def test_seven_custom_metrics_registered(self):
        names = get_custom_metric_names()
        expected = {
            "stays_in_role",
            "session_memory_tool_use",
            "skill_invocation_tool_use",
            "context_doc_tool_use",
            "temporal_awareness",
            "engineer_prompt_format",
            "scope_discipline",
        }
        assert expected == set(names)
