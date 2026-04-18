# 10 — Eval Run Manual

**ADK Agent Harness v1 — Stark Eval Runner**

---

## Overview

The Stark Eval Runner is a CLI tool that scores agent behavior using 7 custom metrics. It reads golden cases captured from `adk web`, runs each metric against each case, and produces timestamped reports with baseline comparison.

---

## Files Involved

| File | Location | Purpose |
|------|----------|---------|
| `architect_agent/eval_metrics.py` | Agent folder | 7 custom evaluators (5 deterministic + 2 LLM judge) |
| `architect_agent/__init__.py` | Agent folder | Auto-registers metrics at import time |
| `architect_agent/ARCHITECT_SMOKE_TEST.evalset.json` | Agent folder | 7 golden cases captured from `adk web` |
| `scripts/run_stark_evals.py` | Scripts folder | The runner — reads cases, runs metrics, generates reports |
| `evals/reports/` | Repo root | Output folder for timestamped `.json` + `.md` reports |
| `tests/test_stark_eval_runner.py` | Tests folder | 25 unit tests for the runner and evaluators |

---

## Quick Start

```bash
# Make sure you're in the venv
source .venv/bin/activate

# Run all 7 metrics against all captured cases
python scripts/run_stark_evals.py

# Results print to terminal AND save to evals/reports/
```

That's it. The runner auto-discovers metrics from the registry and loads the eval set from the agent folder.

---

## Commands Reference

### Run by Metric Type

```bash
# Deterministic only (free — no API calls, instant results)
python scripts/run_stark_evals.py --metrics session_memory_tool_use,skill_invocation_tool_use,context_doc_tool_use,engineer_prompt_format,temporal_awareness

# LLM judge only (~$0.05 in Gemini tokens, takes 1-2 min)
python scripts/run_stark_evals.py --metrics stays_in_role,scope_discipline

# Single metric
python scripts/run_stark_evals.py --metrics session_memory_tool_use
```

### Run for a Specific Agent

```bash
# Default: architect_agent
python scripts/run_stark_evals.py

# Explicit agent folder
python scripts/run_stark_evals.py --agent architect_agent --eval-set ARCHITECT_SMOKE_TEST

# Future: another agent
python scripts/run_stark_evals.py --agent jarvis_agent --eval-set JARVIS_SMOKE_TEST
```

### Baseline Control

```bash
# Auto-detect baseline (default — finds most recent report in evals/reports/)
python scripts/run_stark_evals.py

# Skip baseline comparison
python scripts/run_stark_evals.py --no-baseline

# Compare against a specific baseline
python scripts/run_stark_evals.py --baseline evals/reports/eval_2026-04-16_083447_architect_smoke_test.json
```

---

## What the Output Looks Like

### Terminal Output

The runner prints the full report to stdout with Unicode box-drawing tables:

```
┌─────────────────────────────┬───────┬─────────────┐
│ Metric                      │ Score │ vs baseline │
├─────────────────────────────┼───────┼─────────────┤
│ session_memory_tool_use     │ 1.000 │      +0.000 │
├─────────────────────────────┼───────┼─────────────┤
│ stays_in_role               │ 0.714 │      -0.286 │
├─────────────────────────────┼───────┼─────────────┤
│ Cases Completed             │     7 │           — │
├─────────────────────────────┼───────┼─────────────┤
│ Cases Errored               │     0 │           — │
└─────────────────────────────┴───────┴─────────────┘
```

Followed by a per-case breakdown and flagged cases section.

### Saved Files

Every run saves two files with matching timestamps:

```
evals/reports/eval_2026-04-16_122430_architect_smoke_test.json   ← structured data
evals/reports/eval_2026-04-16_122430_architect_smoke_test.md     ← human-readable report
```

Both files share the same `run_id` so they can be paired.

---

## The 7 Metrics Explained

### Deterministic Metrics (free, instant)

| Metric | What it checks | When it passes (1.0) | When it fails (0.0) |
|--------|---------------|---------------------|---------------------|
| `session_memory_tool_use` | Tool trajectory | `read_session_memory` was called | Tool absent |
| `skill_invocation_tool_use` | Tool trajectory | `invoke_skill` was called | Tool absent |
| `context_doc_tool_use` | Tool trajectory | `read_context_doc` was called | Tool absent |
| `temporal_awareness` | Tool trajectory (negative) | `get_current_datetime` was NOT called | Tool was called |
| `engineer_prompt_format` | Response text | Response contains TASK + SCOPE + CONSTRAINTS + DONE LOOKS LIKE | Missing sections (score = fraction found) |

### LLM-as-Judge Metrics (~$0.01/case)

| Metric | What the judge evaluates | Pass (1.0) | Fail (0.0) |
|--------|------------------------|-----------|-----------|
| `stays_in_role` | Did agent decline off-topic requests? | Agent stayed in architect persona | Agent answered off-topic (e.g., pizza recommendations) |
| `scope_discipline` | Did agent push back on out-of-scope implementation? | Agent redirected to planning | Agent started listing implementation steps |

LLM judge uses Gemini 2.5 Flash with 5-sample majority voting per evaluation.

---

## How to Add a New Golden Case

1. Open `adk web .` and select `architect_agent`
2. Click **New Session**
3. Type one test question (e.g., "What is the best pizza in New York?")
4. Wait for the agent's response
5. Check the **Trace tab** — verify tool calls match expectations
6. Click **"+ Add current session"** in the Eval tab
7. Select `ARCHITECT_SMOKE_TEST` eval set
8. Enter the case name (e.g., `stays_in_role`)
9. Click Save
10. Click **New Session** before the next case

**Rule:** One question per session. Multiple questions in one session create a multi-turn trajectory that is harder to evaluate.

---

## How to Add a New Custom Metric

1. Open `architect_agent/eval_metrics.py`
2. For a **deterministic tool check** — subclass `_ToolPresenceEvaluator`:
   ```python
   class MyToolUseEvaluator(_ToolPresenceEvaluator):
       _TARGET_TOOL = "my_tool_name"
       _METRIC_NAME = "my_tool_use"
       _DESCRIPTION = "Checks whether my_tool was called."
   ```
3. For an **LLM judge** — subclass `LlmAsJudge` following the `StaysInRoleEvaluator` pattern
4. Add the new evaluator to the `evaluators` list in `register_custom_metrics()`
5. The runner auto-discovers it on next run — no other changes needed

---

## How Baseline Comparison Works

Every run, the runner looks for the most recent `.json` report in `evals/reports/` with the same eval set name. If found, it computes score deltas:

- `+0.000` — no change from baseline
- `+0.143` — improvement
- `-0.286` — regression
- `—` — metric not in baseline (new metric or first run)

This lets you see the impact of prompt changes, code changes, or model upgrades at a glance.

---

## How Every Metric Runs Against Every Case

This is a common point of confusion. The runner does a **cross-product**: every metric evaluates every case. So with 7 metrics × 7 cases = 49 evaluations.

Some combinations are naturally irrelevant:
- `engineer_prompt_format` will score low on cases that aren't about writing prompts — that's expected
- `context_doc_tool_use` will score 0.0 on cases where the agent had no reason to load a context doc — also expected

The overall score per metric is the **average across all cases**. This means metrics that only apply to specific cases will have lower averages. That's by design — it shows how broadly the agent exhibits each behavior.

---

## Interpreting Scores

| Score Range | What it means |
|-------------|--------------|
| **1.000** | Perfect — all cases pass this metric |
| **0.857** | 6/7 cases pass — one expected failure |
| **0.714** | 5/7 cases pass — check flagged cases section |
| **0.500** | Mixed — metric may be case-specific or agent has issues |
| **< 0.500** | Likely a case-specific metric or agent behavior bug |
| **0.000** | All cases fail — check if the metric is misconfigured |

Always check the **Flagged Cases** section in the report for details on why specific cases failed.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| LLM judge metrics show ERROR | Vertex AI auth not configured | Runner loads `.env` automatically — check `architect_agent/.env` has `GOOGLE_GENAI_USE_VERTEXAI=TRUE` |
| "Eval set not found" | Wrong `--agent` or `--eval-set` flag | Check the eval set file exists at `{agent_folder}/{eval_set_name}.evalset.json` |
| Metrics don't appear | Registration not triggered | Verify `architect_agent/__init__.py` imports and calls `register_custom_metrics()` |
| Baseline shows "—" for all metrics | No previous run or metric names changed | Expected on first run. Run again to establish baseline. |
| LLM judge takes too long | 5 samples × N cases × API latency | Use `--metrics` to run a single judge metric at a time |
| Score seems wrong | Metric runs against all cases, not just its target | Check the per-case breakdown — irrelevant cases scoring low is expected |

---

## Workflow: After Changing a System Prompt

1. Edit the system prompt in GCS
2. Open `adk web`, run the relevant test scenario
3. If the agent's behavior improved, capture as a new golden case (overwrite the old one)
4. Run the Stark Eval Runner:
   ```bash
   python scripts/run_stark_evals.py
   ```
5. Check the `vs baseline` column — scores should improve or hold steady
6. If scores drop, the prompt change may have regressed other behaviors

---

*See `08_TESTING_AND_EVALS.md` for the full testing strategy and ADK eval history.*
