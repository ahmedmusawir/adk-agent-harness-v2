# 08 — Testing and Evals

**ADK Agent Harness v1**

---

## Testing Strategy — Three Layers

| Layer | What it covers | How to run | Cost |
|-------|---------------|-----------|------|
| **Unit tests** | Python utility functions, callbacks, tools, evaluators | `pytest -m unit` | Free |
| **Stark Eval Runner (deterministic)** | Tool trajectory checks, response format checks | `python scripts/run_stark_evals.py --metrics <deterministic>` | Free |
| **Stark Eval Runner (LLM judge)** | Qualitative behavior — role adherence, scope discipline | `python scripts/run_stark_evals.py --metrics stays_in_role,scope_discipline` | ~$0.05/run |
| **Manual smoke tests** | End-to-end in `adk web` — golden case capture | Follow `MANUAL_TEST_PLAN.md` | Free |

---

## Unit Tests

**Location:** `tests/` (shared) and `architect_agent/tests/` (agent-specific)

**Framework:** pytest with marks

**Count:** 81 tests, all green as of 2026-04-16

```bash
pytest -m unit          # run all unit tests
pytest -m unit -s       # with print output
pytest -m unit -v       # verbose
```

### Test Files

| File | What it tests |
|------|-------------|
| `tests/test_token_calculator.py` | `count_tokens`, `estimate_cost`, `get_model_pricing`, all 9 models in `_PRICING` |
| `tests/test_run_receipt.py` | `create_receipt`, `format_receipt`, `save_receipt_to_file` |
| `tests/test_receipt_callback.py` | `get_timestamp_inject_callback`, `get_receipt_callback` |
| `tests/test_context_cache.py` | Context cache utilities |
| `tests/test_eval_runner.py` | Eval runner utilities |
| `tests/test_stark_eval_runner.py` | Stark Eval Runner: metrics discovery, file generation, baseline deltas, flags, report format, all deterministic evaluators |
| `architect_agent/tests/test_receipt_callback.py` | Timestamp injection, replace-not-accumulate behavior |
| `architect_agent/tests/test_run_receipt.py` | Agent-level receipt behavior |

### Key Test Patterns

**Mock target for GCS tools:** Patch `architect_agent.tools.list_gcs_files` directly — not `storage.Client`. Patching `storage.Client` causes mock collision with the second GCS call in the same function.

---

## Stark Eval Runner

The custom eval system that replaced ADK's failing trajectory matching. See `10_EVAL_RUN_MANUAL.md` for the full run guide.

### Why It Exists

ADK's built-in `tool_trajectory_avg_score: 1.0` requires exact match on tool names, order, arguments, and count. This is incompatible with reasoning agents like `architect_agent` that vary their tool usage per turn. Every automated ADK eval failed 100%.

The Stark Eval Runner uses two approaches:
1. **Deterministic metrics** — check for presence/absence of specific tools, or check response content
2. **LLM-as-a-Judge metrics** — Gemini judges qualitative behavior (role adherence, scope discipline)

### Architecture

```
architect_agent/ARCHITECT_SMOKE_TEST.evalset.json  ← golden cases (captured via adk web)
                    ↓
architect_agent/eval_metrics.py                    ← 7 custom evaluators
                    ↓
scripts/run_stark_evals.py                         ← runner (reads cases, runs metrics, generates reports)
                    ↓
evals/reports/eval_YYYY-MM-DD_HHMMSS_*.json        ← structured results
evals/reports/eval_YYYY-MM-DD_HHMMSS_*.md          ← human-readable report
```

### The 7 Custom Metrics

| Metric | Type | What it checks |
|--------|------|---------------|
| `session_memory_tool_use` | Deterministic | `read_session_memory` was called |
| `skill_invocation_tool_use` | Deterministic | `invoke_skill` was called |
| `context_doc_tool_use` | Deterministic | `read_context_doc` was called |
| `temporal_awareness` | Deterministic (negative) | `get_current_datetime` was NOT called |
| `engineer_prompt_format` | Deterministic | Response contains TASK / SCOPE / CONSTRAINTS / DONE LOOKS LIKE |
| `stays_in_role` | LLM-as-Judge | Agent declines off-topic requests and stays in architect persona |
| `scope_discipline` | LLM-as-Judge | Agent pushes back on out-of-scope implementation requests |

### How Metrics Work

**Deterministic metrics** inspect the tool trajectory or response text from captured eval cases. No API calls, no cost, instant results.

**LLM-as-Judge metrics** send the user prompt + agent response to a Gemini judge model (`gemini-2.5-flash`) with a rubric prompt. The judge scores the response. Each evaluation uses 5 samples with majority voting to reduce noise. Cost: ~$0.01 per case per metric.

### How Metrics Register

All 7 metrics are defined in `architect_agent/eval_metrics.py` and registered with ADK's `MetricEvaluatorRegistry` at import time via `architect_agent/__init__.py`. The runner discovers them from the registry — no hardcoded metric list.

### ADK Web UI Limitation

The ADK web UI Eval tab hardcodes only 2 metrics (`tool_trajectory_avg_score`, `response_match_score`) in its compiled Angular frontend. The backend `/metrics-info` endpoint correctly returns all registered metrics, but the frontend ignores it. Custom metrics only work via the Stark Eval Runner CLI — not the UI. This is an ADK v1.13.0 limitation.

---

## ADK Trajectory Eval — Why It Failed (Historical)

The ADK eval system (`adk eval` CLI + `adk web` Eval tab) was fully explored and calibrated. Key findings:

### What `tool_trajectory_avg_score: 1.0` Requires

Exact match on: which tools were called, in what order, with what arguments, how many times.

### Why It Fails for Reasoning Agents

- Agent varies its preamble (sometimes calls `write_session_memory` early, sometimes doesn't)
- Tool arguments include dynamic content (session memory writes vary every run)
- Tool call order varies based on the question
- Agent sometimes skips tools for simple questions

### Calibration Results

After two full calibration runs with 7 eval cases: 100% failure rate. Even the sole remaining case (`temporal_awareness`) failed due to unpredictable `write_session_memory` calls.

**Decision:** ADK trajectory evals abandoned. Replaced by Stark Eval Runner with LLM-as-a-Judge and deterministic tool-presence checks.

---

## Golden Case Capture (adk web)

Golden cases are captured from `adk web` into `ARCHITECT_SMOKE_TEST.evalset.json`. These are real agent responses — not aspirational test data.

### 7 Scenarios

| # | Name | Case Name | Prompt |
|---|------|-----------|--------|
| 1 | Session Memory Restore | `session_memory_restore` | What did we work on recently? |
| 2 | Skill Invocation | `skill_invocation` | How should I update the session file? |
| 3 | Context Doc Loading | `Context Doc Loading` | What does the APP_ARCHITECTURE_MANUAL say about folder structure? |
| 4 | Scope Discipline | `Scope Discipline` | Let's implement a React Frontend |
| 5 | Engineer Prompt Style | `Engineer Prompt Style` | Write a prompt for Claude Code to add a new tool to the harness |
| 6 | Stays In Role | `stays_in_role` | What is the best pizza in New York? |
| 7 | Temporal Awareness | `temporal_awareness` | What time is it right now? |

### Capture Rule

**One question per session.** Before each scenario:
1. Click "New Session"
2. Ask the one test question
3. Check Trace tab
4. Click "+ Add current session" → select `ARCHITECT_SMOKE_TEST` → enter case name → Save
5. Click "New Session" before the next scenario

---

## Baseline Results (2026-04-16)

First full 7-case × 7-metric run:

| Metric | Avg Score | Notes |
|--------|-----------|-------|
| `stays_in_role` | 0.714 | Pizza case correctly scored 0.0. False positive on temporal case. |
| `session_memory_tool_use` | 0.857 | 6/7 — expected |
| `skill_invocation_tool_use` | 0.857 | 6/7 — expected |
| `context_doc_tool_use` | 0.571 | 4/7 — not all cases require context docs |
| `temporal_awareness` | 0.857 | 6/7 — Engineer Prompt Style case called get_current_datetime |
| `engineer_prompt_format` | 0.357 | Only Engineer Prompt Style case has all 4 sections |
| `scope_discipline` | 0.857 | 6/7 — good |

### Known Issues

- `stays_in_role` judge prompt flags "What time is it?" as off-topic — false positive. Needs carve-out for utility questions.
- Agent breaks character on pizza questions — GCS system prompt needs role discipline reinforcement.
- `engineer_prompt_format` runs against all cases but is only relevant to engineer prompt requests.

---

## Running the Full Test Suite

```bash
# Unit tests (81 tests)
pytest -m unit

# Stark Eval — deterministic only (free, instant)
python scripts/run_stark_evals.py --metrics session_memory_tool_use,skill_invocation_tool_use,context_doc_tool_use,engineer_prompt_format,temporal_awareness

# Stark Eval — LLM judges only (~$0.05)
python scripts/run_stark_evals.py --metrics stays_in_role,scope_discipline

# Stark Eval — all 7 metrics
python scripts/run_stark_evals.py

# Stark Eval — specific agent
python scripts/run_stark_evals.py --agent architect_agent --eval-set ARCHITECT_SMOKE_TEST
```

---

## Phase 1 Exit Criteria

Before proceeding to Phase 2:

- [x] 7/7 golden cases captured in `ARCHITECT_SMOKE_TEST.evalset.json`
- [x] Stark Eval Runner running all 7 metrics with 0 errors
- [x] 81/81 unit tests green
- [ ] Agent behavior bugs fixed: `stays_in_role` (pizza), `temporal_awareness` (Engineer Prompt Style case)
- [ ] `stays_in_role` judge prompt tuned to exclude utility questions
- [ ] All metrics scoring as expected after prompt fixes

---

*See `10_EVAL_RUN_MANUAL.md` for the step-by-step eval run guide.*
