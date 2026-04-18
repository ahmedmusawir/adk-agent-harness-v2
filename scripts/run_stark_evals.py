#!/usr/bin/env python3
# scripts/run_stark_evals.py
"""Stark Eval Runner — runs custom LLM-as-a-Judge and deterministic metrics
against captured ADK eval cases and produces timestamped reports.

Usage:
    python scripts/run_stark_evals.py
    python scripts/run_stark_evals.py --agent architect_agent --eval-set ARCHITECT_SMOKE_TEST
    python scripts/run_stark_evals.py --agent jarvis_agent --eval-set JARVIS_SMOKE_TEST
    python scripts/run_stark_evals.py --metrics session_memory_tool_use
    python scripts/run_stark_evals.py --metrics session_memory_tool_use,stays_in_role
    python scripts/run_stark_evals.py --no-baseline
    python scripts/run_stark_evals.py --baseline evals/reports/eval_2026-04-14_101500_architect_smoke_test.json
"""
import argparse
import asyncio
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- Ensure repo root is on sys.path so imports work ---
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load agent .env before any ADK/Vertex imports — adk web does this
# automatically, but standalone scripts need to do it manually.
from dotenv import load_dotenv


def _load_agent_env(agent_name: str = "architect_agent"):
    """Load the agent's .env file so Vertex AI auth is configured."""
    env_path = REPO_ROOT / agent_name / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_agent_env()

# Register custom metrics (triggers architect_agent/__init__.py import)
import architect_agent  # noqa: F401 — side effect: registers custom metrics

from google.adk.evaluation.eval_metrics import EvalMetric, JudgeModelOptions
from google.adk.evaluation.metric_evaluator_registry import (
    DEFAULT_METRIC_EVALUATOR_REGISTRY,
)
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.eval_case import Invocation
from google.adk.evaluation.evaluator import EvalStatus
from google.adk.evaluation.llm_as_judge_utils import get_text_from_content

# --- Constants ---
REPORTS_DIR = REPO_ROOT / "evals" / "reports"
DEFAULT_AGENT = "architect_agent"
DEFAULT_EVAL_SET = "ARCHITECT_SMOKE_TEST"
JUDGE_MODEL = "gemini-2.5-flash"

# Built-in metric names we skip by default (only run our custom ones)
BUILTIN_METRICS = {
    "tool_trajectory_avg_score",
    "response_evaluation_score",
    "response_match_score",
    "safety_v1",
    "final_response_match_v2",
}


# ──────────────────────────────────────────────────────────────────────
# Core eval logic
# ──────────────────────────────────────────────────────────────────────

def load_eval_set(evalset_path: Path) -> EvalSet:
    """Load and parse an .evalset.json file into an EvalSet model."""
    with open(evalset_path, encoding="utf-8") as f:
        data = json.load(f)
    return EvalSet.model_validate(data)


def get_custom_metric_names() -> list[str]:
    """Return names of all registered metrics excluding built-ins."""
    all_metrics = DEFAULT_METRIC_EVALUATOR_REGISTRY.get_registered_metrics()
    return [m.metric_name for m in all_metrics if m.metric_name not in BUILTIN_METRICS]


def get_user_prompt_text(invocation: Invocation) -> str:
    """Extract the user prompt text from an invocation."""
    text = get_text_from_content(invocation.user_content)
    return text or "(no prompt text)"


def get_response_text(invocation: Invocation) -> str:
    """Extract the agent response text from an invocation."""
    text = get_text_from_content(invocation.final_response)
    return text or "(no response text)"


def get_tool_names(invocation: Invocation) -> list[str]:
    """Extract tool call names from an invocation."""
    if not invocation.intermediate_data or not invocation.intermediate_data.tool_uses:
        return []
    return [tc.name for tc in invocation.intermediate_data.tool_uses if tc.name]


def compute_flags(metric_name: str, score: float) -> list[str]:
    """Compute flags for a given metric score."""
    if score >= 1.0:
        return []
    # Tool-use metrics
    if "tool_use" in metric_name:
        return ["tool_not_called"] if score == 0.0 else []
    # Rubric / LLM-judged metrics
    flag_map = {
        "stays_in_role": "role_break",
        "scope_discipline": "scope_violation",
        "engineer_prompt_format": "format_missing",
        "temporal_awareness": "wrong_time_source",
        "skill_invocation_tool_use": "tool_not_called",
        "context_doc_tool_use": "tool_not_called",
    }
    if score < 0.5:
        return [flag_map.get(metric_name, "below_threshold")]
    return []


async def run_evaluator(metric_name: str, invocations: list[Invocation], threshold: float = 0.5):
    """Run a single evaluator against a list of invocations.

    Returns EvaluationResult or raises on error.
    """
    # Build the EvalMetric — LLM-judged metrics need judge_model_options
    eval_metric = EvalMetric(
        metric_name=metric_name,
        threshold=threshold,
        judge_model_options=JudgeModelOptions(
            judge_model=JUDGE_MODEL,
            num_samples=5,
        ),
    )

    evaluator = DEFAULT_METRIC_EVALUATOR_REGISTRY.get_evaluator(eval_metric)

    # Handle sync vs async evaluators (same pattern as LocalEvalService)
    if inspect.iscoroutinefunction(evaluator.evaluate_invocations):
        return await evaluator.evaluate_invocations(invocations, invocations)
    else:
        return evaluator.evaluate_invocations(invocations, invocations)


# ──────────────────────────────────────────────────────────────────────
# Baseline comparison
# ──────────────────────────────────────────────────────────────────────

def find_latest_baseline(eval_set_name: str, reports_dir: Path) -> dict | None:
    """Find the most recent JSON report for the given eval set."""
    pattern = f"eval_*_{eval_set_name.lower()}.json"
    matches = sorted(reports_dir.glob(pattern))
    if not matches:
        return None
    with open(matches[-1], encoding="utf-8") as f:
        return json.load(f)


def compute_delta(current: float, baseline_data: dict | None, metric_name: str) -> str:
    """Compute score delta string vs baseline."""
    if baseline_data is None:
        return "—"
    baseline_metrics = baseline_data.get("metrics_summary", {})
    if metric_name not in baseline_metrics:
        return "—"
    baseline_score = baseline_metrics[metric_name].get("avg_score", 0.0)
    delta = current - baseline_score
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.3f}"


# ──────────────────────────────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────────────────────────────

def format_md_report(results: dict) -> str:
    """Generate the human-readable .md report with box-drawing characters."""
    lines = []

    # Header
    baseline_label = results["baseline_run_id"] or "none (first run)"
    lines.append(f"# Stark Eval — {results['eval_set']}")
    lines.append(f"**Generated:** {results['timestamp_utc']}  |  **Judge:** {results['judge_model']}")
    lines.append(f"**Baseline:** {baseline_label}")
    lines.append("")

    # ── Summary table ──
    col_metric = 29
    col_score = 7
    col_delta = 13

    def pad(text, width):
        return text + " " * max(0, width - len(text))

    def rpad(text, width):
        return " " * max(0, width - len(text)) + text

    top    = f"┌{'─' * col_metric}┬{'─' * col_score}┬{'─' * col_delta}┐"
    mid    = f"├{'─' * col_metric}┼{'─' * col_score}┼{'─' * col_delta}┤"
    bottom = f"└{'─' * col_metric}┴{'─' * col_score}┴{'─' * col_delta}┘"

    def row(c1, c2, c3):
        return f"│{pad(c1, col_metric)}│{rpad(c2, col_score)}│{rpad(c3, col_delta)}│"

    lines.append(top)
    lines.append(row(" Metric", "Score ", " vs baseline "))
    lines.append(mid)

    for metric_name, data in results["metrics_summary"].items():
        score_str = f"{data['avg_score']:.3f} "
        delta_str = f"{data['vs_baseline']} "
        lines.append(row(f" {metric_name}", score_str, delta_str))
        lines.append(mid)

    # Cases completed / errored rows
    lines.append(row(" Cases Completed", f"{results['cases_completed']} ", "— "))
    lines.append(mid)
    lines.append(row(" Cases Errored", f"{results['cases_errored']} ", "— "))
    lines.append(bottom)

    lines.append("")
    lines.append("> **How to read these scores:** All scores are 0.0–1.0. Higher is always better.")
    lines.append("> Tool-use metrics check whether specific tools were called.")
    lines.append("> Rubric metrics use an LLM judge to score qualitative behavior.")
    lines.append("")

    # ── Per-Case Breakdown ──
    lines.append("## Per-Case Breakdown")
    lines.append("")

    col_case = 26
    col_pmetric = 25
    col_pscore = 7
    col_pstatus = 16

    ptop    = f"┌{'─' * col_case}┬{'─' * col_pmetric}┬{'─' * col_pscore}┬{'─' * col_pstatus}┐"
    pmid    = f"├{'─' * col_case}┼{'─' * col_pmetric}┼{'─' * col_pscore}┼{'─' * col_pstatus}┤"
    pbottom = f"└{'─' * col_case}┴{'─' * col_pmetric}┴{'─' * col_pscore}┴{'─' * col_pstatus}┘"

    def prow(c1, c2, c3, c4):
        return f"│{pad(c1, col_case)}│{pad(c2, col_pmetric)}│{rpad(c3, col_pscore)}│{pad(c4, col_pstatus)}│"

    lines.append(ptop)
    lines.append(prow(" Case ID", " Metric", "Score ", " Status"))
    lines.append(pmid)

    for case_result in results["per_case_results"]:
        case_id = case_result["case_id"]
        for metric_name, metric_data in case_result["metric_scores"].items():
            score = metric_data["score"]
            status = metric_data["status"]
            flags = metric_data.get("flags", [])

            score_str = f"{score:.3f} " if score is not None else "ERROR "

            if status == "PASS" and not flags:
                status_display = " PASS"
            elif status == "ERROR":
                status_display = " ERROR"
            elif flags:
                status_display = f" {flags[0]}"
            else:
                status_display = f" FAIL"

            lines.append(prow(f" {case_id[:col_case - 2]}", f" {metric_name[:col_pmetric - 2]}", score_str, status_display))
            lines.append(pmid)

    # Replace last pmid with pbottom
    if lines and lines[-1] == pmid:
        lines[-1] = pbottom

    lines.append("")

    # ── Flagged Cases ──
    flagged = []
    for case_result in results["per_case_results"]:
        for metric_name, metric_data in case_result["metric_scores"].items():
            score = metric_data.get("score")
            if score is not None and score < 1.0:
                flagged.append({
                    "case_id": case_result["case_id"],
                    "case_prompt": case_result["case_prompt"],
                    "metric_name": metric_name,
                    "score": score,
                    "flags": metric_data.get("flags", []),
                    "reasoning": metric_data.get("reasoning", ""),
                })

    if flagged:
        lines.append("## Flagged Cases")
        lines.append("")
        for f in flagged:
            lines.append(f"**{f['case_id']}** — \"{f['case_prompt'][:80]}\"")
            lines.append(f"- Metric: {f['metric_name']}")
            lines.append(f"- Score: {f['score']:.3f}")
            if f["reasoning"]:
                lines.append(f"- Issue: {f['reasoning']}")
            if f["flags"]:
                lines.append(f"- Flags: {', '.join(f['flags'])}")
            lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# File I/O
# ──────────────────────────────────────────────────────────────────────

def save_reports(results: dict, md_report: str, reports_dir: Path) -> tuple[Path, Path]:
    """Save both .json and .md reports. Returns (json_path, md_path)."""
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Timestamp for filename from run_id
    run_id = results["run_id"]
    json_path = reports_dir / f"{run_id}.json"
    md_path = reports_dir / f"{run_id}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)

    return json_path, md_path


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Stark Eval Runner")
    parser.add_argument(
        "--agent",
        default=DEFAULT_AGENT,
        help=f"Agent folder name (default: {DEFAULT_AGENT})",
    )
    parser.add_argument(
        "--eval-set",
        default=DEFAULT_EVAL_SET,
        help=f"Eval set name (default: {DEFAULT_EVAL_SET})",
    )
    parser.add_argument(
        "--metrics",
        default=None,
        help="Comma-separated metric names (default: all registered custom metrics)",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Specific baseline .json file to compare against",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip baseline comparison",
    )
    args = parser.parse_args()

    # Resolve eval set path and load agent env
    agent_name = args.agent
    _load_agent_env(agent_name)
    eval_set_name = args.eval_set
    evalset_path = REPO_ROOT / agent_name / f"{eval_set_name}.evalset.json"
    if not evalset_path.exists():
        print(f"ERROR: Eval set not found: {evalset_path}")
        sys.exit(1)

    # Load eval set
    eval_set = load_eval_set(evalset_path)
    print(f"Loaded {len(eval_set.eval_cases)} cases from {eval_set_name}")

    # Resolve metrics
    if args.metrics:
        metric_names = [m.strip() for m in args.metrics.split(",")]
    else:
        metric_names = get_custom_metric_names()

    if not metric_names:
        print("ERROR: No custom metrics registered.")
        sys.exit(1)

    print(f"Running metrics: {', '.join(metric_names)}")

    # Resolve baseline
    baseline_data = None
    if not args.no_baseline:
        if args.baseline:
            baseline_path = Path(args.baseline)
            if baseline_path.exists():
                with open(baseline_path, encoding="utf-8") as f:
                    baseline_data = json.load(f)
        else:
            baseline_data = find_latest_baseline(eval_set_name, REPORTS_DIR)

    if baseline_data:
        print(f"Baseline: {baseline_data.get('run_id', 'unknown')}")
    else:
        print("Baseline: none (first run)")

    # Generate run ID and timestamp
    now = datetime.now(timezone.utc)
    timestamp_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id_ts = now.strftime("%Y-%m-%d_%H%M%S")
    run_id = f"eval_{run_id_ts}_{eval_set_name.lower()}"

    # Run evaluations
    print(f"\nRunning evaluations...")
    print("─" * 60)

    # Use a single event loop for async evaluators
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        results = loop.run_until_complete(
            _async_build_results(eval_set, metric_names, baseline_data, run_id, timestamp_str)
        )
    finally:
        loop.close()

    # Generate reports
    md_report = format_md_report(results)

    # Save files
    json_path, md_path = save_reports(results, md_report, REPORTS_DIR)

    # Print to stdout
    print(md_report)
    print("─" * 60)
    print(f"JSON report: {json_path}")
    print(f"  MD report: {md_path}")


async def _async_build_results(
    eval_set: EvalSet,
    metric_names: list[str],
    baseline_data: dict | None,
    run_id: str,
    timestamp_str: str,
) -> dict:
    """Async wrapper that runs all metrics against all cases."""
    results = {
        "run_id": run_id,
        "timestamp_utc": timestamp_str,
        "eval_set": eval_set.eval_set_id,
        "judge_model": JUDGE_MODEL,
        "baseline_run_id": baseline_data.get("run_id") if baseline_data else None,
        "metrics_summary": {},
        "cases_completed": 0,
        "cases_errored": 0,
        "per_case_results": [],
    }

    for case in eval_set.eval_cases:
        case_result = {
            "case_id": case.eval_id.strip(),
            "case_prompt": get_user_prompt_text(case.conversation[0]) if case.conversation else "",
            "metric_scores": {},
        }
        case_errored = False

        for metric_name in metric_names:
            try:
                eval_result = await run_evaluator(metric_name, case.conversation)
                score = eval_result.overall_score if eval_result.overall_score is not None else 0.0
                status = "PASS" if eval_result.overall_eval_status == EvalStatus.PASSED else "FAIL"
                flags = compute_flags(metric_name, score)

                reasoning = ""
                if score < 1.0:
                    if "tool_use" in metric_name:
                        tools = get_tool_names(case.conversation[0]) if case.conversation else []
                        if tools:
                            reasoning = f"Tools called: {', '.join(tools)}. Target tool not found."
                        else:
                            reasoning = "No tools were called."
                    else:
                        response_text = get_response_text(case.conversation[0]) if case.conversation else ""
                        reasoning = response_text[:200] + "..." if len(response_text) > 200 else response_text

                case_result["metric_scores"][metric_name] = {
                    "score": score,
                    "status": status,
                    "flags": flags,
                    "reasoning": reasoning,
                }

                if metric_name not in results["metrics_summary"]:
                    results["metrics_summary"][metric_name] = {"scores": [], "cases_run": 0}
                results["metrics_summary"][metric_name]["scores"].append(score)
                results["metrics_summary"][metric_name]["cases_run"] += 1

            except Exception as e:
                case_errored = True
                case_result["metric_scores"][metric_name] = {
                    "score": None,
                    "status": "ERROR",
                    "flags": ["evaluator_error"],
                    "reasoning": str(e),
                }

        if case_errored:
            results["cases_errored"] += 1
        else:
            results["cases_completed"] += 1

        results["per_case_results"].append(case_result)

    # Finalize summary
    for metric_name, data in results["metrics_summary"].items():
        scores = data.pop("scores")
        data["avg_score"] = sum(scores) / len(scores) if scores else 0.0
        data["vs_baseline"] = compute_delta(data["avg_score"], baseline_data, metric_name)

    return results


if __name__ == "__main__":
    main()
