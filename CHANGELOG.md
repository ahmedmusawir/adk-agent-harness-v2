# CHANGELOG.md — ADK Harness Starter v1

---

## 2026-03-23 — [CC] Claude Code — SK-6 Eval Runner + usage report file output

- **Created:** `evals/eval_cases.json` — 5 deterministic test cases for product_agent_rico_1
- **Created:** `scripts/run_evals.py` — async CLI eval runner through ADK harness; substring grading; saves `evals/reports/eval_YYYY-MM-DD_HHMMSS.txt`
- **Created:** `tests/test_eval_runner.py` — 10 unit tests, all mocked, 52/52 total green
- **Updated:** `scripts/usage_report.py` — now saves report to `reports/usage_reports/` on every run
- **Updated:** `README.md` — added eval runner and usage report sections
- **Updated:** `.gitignore` — added `reports/` and `evals/reports/`
- **Reason:** SK-6 completes the Starter Kit V1 plumbing. Kit is now locked.

---

## 2026-03-04 — [CC] Claude Code — Receipt callbacks wired to all agents

- **Updated:** `jarvis_agent/agent.py` — added `before_model_callback` + `after_model_callback`. No other changes.
- **Updated:** `ghl_mcp_agent/agent.py` — added `before_model_callback` + `after_model_callback`. No other changes.
- Receipts for all three agents now log to `logs/receipts/{agent_name}.jsonl`.

---

## 2026-03-04 — [CC] Claude Code — SK-INT Integration Wiring & Usage Reporting

- **Created:** `callbacks/__init__.py` — package marker.
- **Created:** `callbacks/receipt_callback.py` — ADK callback factory. `get_start_time_callback()` → before_model_callback that stamps `_run_start_time` in session state. `get_receipt_callback(agent_name, model)` → after_model_callback that skips streaming chunks, reads latency from state, calls `create_receipt()` → `format_receipt()` → `save_receipt_to_file()`. Errors are caught and printed as warnings so the agent continues normally.
- **Updated:** `product_agent_rico_1/agent.py` — wired `before_model_callback` + `after_model_callback`. No other changes to agent logic, tools, or system prompt.
- **Created:** `scripts/usage_report.py` — CLI usage report. Reads `logs/receipts/*.jsonl`, filters by `--date` (defaults to today UTC), aggregates per agent, prints aligned ASCII table. Handles missing dir gracefully.
- **Created:** `tests/test_receipt_callback.py` — 6 unit tests (all mocked, no API calls). All green.
- **Updated:** `.gitignore` — added `logs/` to prevent runtime receipts from being committed.

---

## 2026-03-03 — [CC] Claude Code — SK-4 Context Cache

- **Created:** `utils/context_cache.py` — Vertex AI context caching utility. Public API: `create_cache()`, `get_cache()`, `delete_cache()`, `list_caches()`, `estimate_cache_savings()`. Cached token rate = 10% of input price (90% discount). `create_cache()` accepts optional `tools` parameter — tools must be baked into the cache, not passed at generation time (see Architectural Decision below).
- **Created:** `tests/test_context_cache.py` — 13 tests (10 integration, 3 unit). All green.

---

## 2026-03-03 — [CC] Claude Code — Architectural Decision: Vertex Caching + Tools

### Vertex AI Context Caching — Tools Constraint

**Finding (live-tested 2026-03-03):** When using `cached_content` in a `generate_content` call, the Vertex AI API **rejects** any request that also sets `tools`, `tool_config`, or `system_instruction` in the `GenerateContentConfig`. Error: `400 INVALID_ARGUMENT: "Tool config, tools and system instruction should not be set in the request when using cached content."`

**Workaround (confirmed working):** Tools CAN be baked into the cache itself via `CreateCachedContentConfig(tools=[...])`. When the agent calls `generate_content`, it passes only `cached_content=cache.name` — no separate `tools` argument. The cached tools are used automatically.

**Impact on Phase 1A — Rico B:**
- Rico B's `create_cache()` call must include any ADK tools in `CreateCachedContentConfig.tools`
- The ADK `Agent()` `tools=` parameter is **incompatible** with `cached_content` unless those tools are pre-baked into the cache
- `utils/context_cache.py` `create_cache()` accepts an optional `tools` parameter for this pattern

---

## 2026-03-03 — [CC] Claude Code — SK-2 Run Receipt

- **Created:** `utils/run_receipt.py` — Run receipt utility. Public API: `create_receipt()`, `format_receipt()`, `save_receipt_to_file()`. `create_receipt()` calls `count_tokens()` + `estimate_cost()` from SK-1 internally; caller passes raw text only.
- **Created:** `tests/test_run_receipt.py` — 13 tests (8 integration, 5 unit). All green.
- **Created:** `tests/conftest.py` — shared fixtures: `sample_input_text`, `sample_output_text`, `sample_receipt`.

---

## 2026-03-03 — [CC] Claude Code — SK-1 Token Calculator

- **Created:** `utils/token_calculator.py` — Token counting utility using Vertex AI `client.models.count_tokens()`. Public API: `count_tokens()`, `estimate_cost()`, `get_model_pricing()`. Hardcoded pricing for gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash.
- **Created:** `tests/test_token_calculator.py` — 10 tests (7 unit, 3 integration). All green.
- **Created:** `tests/__init__.py` — makes tests a package.
- **Created:** `pytest.ini` — minimal marker registration for `unit` and `integration`.

---

## 2026-03-03 — [CC] Claude Code — SCAFFOLD_NEW_AGENT Skill

- **Created:** `skills/SCAFFOLD_NEW_AGENT.md` — Skill file defining how to scaffold a new ADK agent. Covers folder structure, `__init__.py`, `agent.py` boilerplate (4 patterns), GCS instruction file path, and a validation checklist. Grounded in actual repo patterns from the 3 existing agents.
- **Created:** `skills/` directory at repo root.

---

## 2026-03-02 — [CC] Claude Code — Pre-Phase-1A Cleanup

### Infrastructure Fixes

- **Updated:** `.env_example` — Changed `GOOGLE_GENAI_USE_VERTEXAI=FALSE` to `GOOGLE_GENAI_USE_VERTEXAI=1`. The old value disabled Vertex AI entirely, which would cause silent auth failures.
- **Updated:** `Dockerfile` — Changed base image from `python:3.11-slim` to `python:3.12-slim`. Aligns with `.python-version` file and project requirements.
- **Updated:** `grant_permissions.sh` — Added `roles/secretmanager.secretAccessor` IAM grant. Without this, Cloud Run crashes at startup when loading secrets via `--set-secrets`.

### Agent Code Fixes

- **Updated:** `ghl_mcp_agent/agent.py` — Fixed stale file header comment (`# /calc_agent/agent.py` → `# ghl_mcp_agent/agent.py`).
- **Updated:** `jarvis_agent/agent.py` — Removed unused `from google import genai` import.

### Git / Security

- **Updated:** `.gitignore` — Added explicit `ghl_mcp_agent/.env` entry to ensure agent-scoped env files are never committed.

### Documentation Fixes

- **Updated:** `docs/NAMING_CONVENTIONS.md` — Updated GCS Paths section to reflect actual bucket path schema used in code (`ADK_Agent_Bundle_1/{agent_name}/` prefix, not the planned `agents/{agent_name}/` prefix).
- **Updated:** `docs/APP_BRIEFS/MASTER_BRIEF_v1.2.md` — Fixed repo name (`adk-harness-modules-workshop-v1` → `adk-harness-starter-v1`). Replaced `shared/` references with `utils/` for token_calculator and run_receipt stubs.
- **Updated:** `docs/APP_BRIEFS/PHASE_1_OVERVIEW.md` — Replaced all `shared/` references with `utils/`, all `token_tracker.py` references with `token_calculator.py`, and repo name. Updated title.
- **Updated:** `docs/APP_BRIEFS/PHASE_1_TESTING_STRATEGY.md` — Replaced all `shared/` references with `utils/`, all `token_tracker` module references with `token_calculator`. Updated title.
- **Updated:** `docs/APP_BRIEFS/STARTER_KIT_SPEC.md` — Fixed repo name in target file structure diagram.
- **Updated:** `docs/APP_BRIEFS/PHASE_1A_AGENT_SET_1_RICO_CACHING.md` — Fixed repo name in both file structure diagrams (lines 42, 383).

### Noted for Future Fix (Not In This Batch)

- `docs/APP_BRIEFS/PHASE_1_TESTING_STRATEGY.md` — Test function names `test_token_tracker_captures_metrics` / `test_token_tracker_fields_are_numeric` still use old module name. Cosmetic only; rename when writing actual tests.
- `deploy.sh` — Missing `--no-cpu-throttling`, `--cpu-boost`, `--min-instances 1` flags required for ADK streaming workloads. Placeholder `GCS_BUCKET_NAME="your-agent-instructions-bucket-name"` not filled in.
- `requirements.txt` — ~134 packages installed, many unused (yfinance, pandas, huggingface-hub, litellm, etc.). Prune before Phase 1A build.
- `docs/APP_BRIEFS/PHASE_1_OVERVIEW.md` + `PHASE_1A` brief — GCS Bucket Structure section still shows planned `agents/{agent}/` paths; actual code uses `ADK_Agent_Bundle_1/` prefix. Architectural decision needed before Phase 1A.

---

*[CC] = Claude Code change | [TS] = Tony Stark manual edit*
