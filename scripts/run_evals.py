#!/usr/bin/env python3
# scripts/run_evals.py
"""SK-6 Eval Runner — runs eval cases through an ADK agent and writes a report.

Usage:
    python scripts/run_evals.py
    python scripts/run_evals.py --config evals/eval_config.json
    python scripts/run_evals.py --config evals/eval_config.json --dataset evals/eval_cases.json
    python scripts/run_evals.py --config evals/eval_config.json --agent product_agent_rico_1
"""
import argparse
import asyncio
import importlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Must be set before ANY google/ADK imports.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")

# Ensure project root is on sys.path so agent modules can be imported.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

REPORTS_DIR = "evals/reports"
DEFAULT_CASES = "evals/eval_cases.json"
DEFAULT_AGENT = "product_agent_rico_1"


# ---------------------------------------------------------------------------
# Core functions (extracted for testability)
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    """Load and validate eval config from a JSON file."""
    with open(path, encoding="utf-8") as f:
        config = json.load(f)
    for field in ("agent", "project", "description", "default_dataset"):
        if field not in config:
            raise ValueError(f"Config missing required field '{field}'")
    return config


def load_cases(path: str) -> list[dict]:
    """Load and validate eval cases from a JSON file."""
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    for case in cases:
        for field in ("id", "input_prompt", "expected_substring"):
            if field not in case:
                raise ValueError(f"Case missing required field '{field}': {case}")
    return cases


async def run_case(runner: Runner, session_service: InMemorySessionService,
                   app_name: str, case: dict) -> dict:
    """Run a single eval case through the ADK runner. Returns a result dict."""
    session = await session_service.create_session(app_name=app_name, user_id="eval_runner")
    message = types.Content(
        role="user",
        parts=[types.Part(text=case["input_prompt"])],
    )

    response_text = ""
    error = None
    start = time.monotonic()

    try:
        async for event in runner.run_async(
            user_id="eval_runner",
            session_id=session.id,
            new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                response_text = " ".join(
                    p.text for p in event.content.parts if getattr(p, "text", None)
                )
    except Exception as e:
        error = str(e)

    latency = time.monotonic() - start
    expected = case["expected_substring"]
    passed = not error and expected.lower() in response_text.lower()

    return {
        "id": case["id"],
        "expected_substring": expected,
        "result": "PASS" if passed else ("ERROR" if error else "FAIL"),
        "latency_s": round(latency, 2),
        "error": error,
        "response": response_text,
    }


def generate_report(results: list[dict], agent_name: str,
                    project: str = "", description: str = "") -> str:
    """Render the ASCII eval report string."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    col_id = max(len("Case ID"), max(len(r["id"]) for r in results)) + 2
    col_sub = max(len("Expected Substring"), max(len(r["expected_substring"]) for r in results)) + 2
    col_res = len("Result") + 2
    col_lat = len("Latency (s)") + 2

    def row(case_id, substring, result, latency):
        return (
            f"| {case_id:<{col_id - 1}}"
            f"| {substring:<{col_sub - 1}}"
            f"| {result:<{col_res - 1}}"
            f"| {latency:<{col_lat - 1}}|"
        )

    sep = f"|{'-' * col_id}|{'-' * col_sub}|{'-' * col_res}|{'-' * col_lat}|"
    header = row("Case ID", "Expected Substring", "Result", "Latency (s)")
    data_rows = [
        row(r["id"], r["expected_substring"], r["result"], str(r["latency_s"]))
        for r in results
    ]

    total = len(results)
    passes = sum(1 for r in results if r["result"] == "PASS")
    errors = sum(1 for r in results if r["result"] == "ERROR")
    pass_rate = (passes / total * 100) if total else 0.0

    header_lines = ["# Stark Eval v1 - Starter Kit Plumbing"]
    if project:
        header_lines.append(f"Project: {project}")
    if description:
        header_lines.append(f"Dataset: {description}")
    header_lines.append(f"Generated: {now}  |  Target Agent: {agent_name}")

    lines = [
        *header_lines,
        "",
        header,
        sep,
        *data_rows,
        "",
        "-" * 50,
        f"Total Cases: {total}",
        f"Pass Rate: {pass_rate:.1f}%",
        f"Errors: {errors}",
    ]
    return "\n".join(lines)


def save_report(report_text: str, output_dir: str) -> Path:
    """Write report to a timestamped .txt file. Returns the path."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report_file = path / f"eval_{timestamp}.txt"
    report_file.write_text(report_text, encoding="utf-8")
    return report_file


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run(cases_path: str, agent_module: str,
               project: str = "", description: str = "") -> None:
    cases = load_cases(cases_path)

    mod = importlib.import_module(agent_module)
    root_agent = mod.root_agent

    app_name = agent_module
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name=app_name, session_service=session_service)

    print(f"\nRunning {len(cases)} eval case(s) against [{agent_module}]...\n")
    results = []
    for case in cases:
        print(f"  → {case['id']} ... ", end="", flush=True)
        result = await run_case(runner, session_service, app_name, case)
        results.append(result)
        print(result["result"])
        if result["error"]:
            print(f"    ↳ {result['error']}")

    report = generate_report(results, agent_module, project=project, description=description)
    print("\n" + report)

    report_file = save_report(report, REPORTS_DIR)
    print(f"\nReport saved → {report_file}")


def main():
    parser = argparse.ArgumentParser(description="SK-6 Eval Runner")
    parser.add_argument("--config",   default=None,         help="Path to eval_config.json")
    parser.add_argument("--dataset",  default=None,         help="Override dataset path from config")
    parser.add_argument("--agent",    default=None,         help="Override agent module from config")
    args = parser.parse_args()

    # Resolve config values, with CLI flags taking precedence.
    project = ""
    description = ""
    cases_path = DEFAULT_CASES
    agent_module = DEFAULT_AGENT

    if args.config:
        config = load_config(args.config)
        agent_module = config["agent"]
        cases_path = config["default_dataset"]
        project = config["project"]
        description = config["description"]

    if args.dataset:
        cases_path = args.dataset
    if args.agent:
        agent_module = args.agent

    asyncio.run(_run(cases_path, agent_module, project=project, description=description))


if __name__ == "__main__":
    main()
