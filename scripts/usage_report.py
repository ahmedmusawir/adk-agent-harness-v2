#!/usr/bin/env python3
# scripts/usage_report.py
"""Daily usage report — reads logs/receipts/*.jsonl and prints an ASCII table.

Usage:
    python scripts/usage_report.py
    python scripts/usage_report.py --date 2026-03-03
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

REPORTS_DIR = "reports/usage_reports"

RECEIPT_DIR = "logs/receipts"

_COL_AGENT = 24
_COL_RUNS = 6
_COL_IN = 11
_COL_OUT = 12
_COL_COST = 12
_SEP_WIDTH = _COL_AGENT + 1 + _COL_RUNS + 1 + _COL_IN + 1 + _COL_OUT + 1 + _COL_COST


def _header() -> str:
    return (
        f"{'AGENT':<{_COL_AGENT}} "
        f"{'RUNS':>{_COL_RUNS}} "
        f"{'IN TOKENS':>{_COL_IN}} "
        f"{'OUT TOKENS':>{_COL_OUT}} "
        f"{'TOTAL COST':>{_COL_COST}}"
    )


def _row(name: str, runs: int, in_tok: int, out_tok: int, cost: float) -> str:
    return (
        f"{name:<{_COL_AGENT}} "
        f"{runs:>{_COL_RUNS},} "
        f"{in_tok:>{_COL_IN},} "
        f"{out_tok:>{_COL_OUT},} "
        f"{'$' + f'{cost:.6f}':>{_COL_COST}}"
    )


def main():
    parser = argparse.ArgumentParser(description="Daily agent usage report")
    parser.add_argument(
        "--date",
        default=None,
        help="Date to report on (YYYY-MM-DD). Defaults to today UTC.",
    )
    args = parser.parse_args()
    target_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    receipt_path = Path(RECEIPT_DIR)
    if not receipt_path.exists():
        print(f"No usage data found for {target_date}")
        return

    # Read and filter all JSONL receipts matching the target date.
    receipts = []
    for jsonl_file in sorted(receipt_path.glob("*.jsonl")):
        try:
            with open(jsonl_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        if r.get("timestamp", "").startswith(target_date):
                            receipts.append(r)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue

    if not receipts:
        print(f"No usage data found for {target_date}")
        return

    # Aggregate by agent name.
    agents: dict[str, dict] = {}
    for r in receipts:
        name = r.get("agent_name", "unknown")
        if name not in agents:
            agents[name] = {"runs": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
        agents[name]["runs"] += 1
        agents[name]["input_tokens"] += r.get("input_tokens", 0)
        agents[name]["output_tokens"] += r.get("output_tokens", 0)
        agents[name]["cost"] += r.get("total_cost_usd", 0.0)

    # Build the table into a buffer (print to terminal + save to file).
    sep = "-" * _SEP_WIDTH
    buf = StringIO()
    buf.write(f"\n=== DAILY USAGE REPORT: {target_date} ===\n\n")
    buf.write(_header() + "\n")
    buf.write(sep + "\n")

    total_runs = total_in = total_out = 0
    total_cost = 0.0

    for name in sorted(agents):
        d = agents[name]
        buf.write(_row(name, d["runs"], d["input_tokens"], d["output_tokens"], d["cost"]) + "\n")
        total_runs += d["runs"]
        total_in += d["input_tokens"]
        total_out += d["output_tokens"]
        total_cost += d["cost"]

    buf.write(sep + "\n")
    buf.write(_row("TOTAL", total_runs, total_in, total_out, total_cost) + "\n")

    output = buf.getvalue()

    # Print to terminal.
    print(output)

    # Save to reports/usage_reports/usage_report_YYYY-MM-DD_HH-MM-SS.txt
    reports_path = Path(REPORTS_DIR)
    reports_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_file = reports_path / f"usage_report_{timestamp}.txt"
    report_file.write_text(output, encoding="utf-8")
    print(f"Report saved → {report_file}")


if __name__ == "__main__":
    main()
