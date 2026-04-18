# PHASE_1_TESTING_STRATEGY.md — ADK Harness Starter v1
## Testing Framework, Conventions & Eval Patterns

---

## Purpose of This Document

This is the third document Claude reads after MASTER_BRIEF.md and PHASE_1_OVERVIEW.md.
It defines HOW to test every agent in Phase 1. Two testing layers exist:

1. **pytest** — Deterministic logic (tools work, state mutates, errors handled)
2. **adk eval** — LLM quality (response accuracy, retrieval relevance, instruction compliance)

Every agent ships with BOTH layers. No exceptions.

---

## Testing Philosophy

### What We Test

| Layer | What It Proves | Tool |
|-------|---------------|------|
| **Unit** | Individual tools return correct data | pytest |
| **Integration** | Agent calls the right tools in the right order | pytest + mocks |
| **Behavioral** | Agent responds correctly to user queries | adk eval |
| **Regression** | New agents don't break existing agents | pytest (full suite) |
| **Metrics** | Token usage, latency, cost tracked per run | run receipts + assertions |

### What We Do NOT Test in Phase 1

- End-to-end UI flows (no custom frontend)
- Load testing / concurrency
- Multi-agent orchestration (that's Phase 2)
- Deployment pipelines (Cloud Run testing is Phase 2)

---

## Layer 1: pytest — Deterministic Tests

### File Structure Per Agent

```
agents/rico_baseline/
├── __init__.py
├── agent.py
├── tools.py
└── tests/
    ├── __init__.py
    ├── test_tools.py          # Unit tests for tool functions
    ├── test_agent.py           # Integration tests (agent + tools)
    ├── test_shared_modules.py  # Token tracker, run receipt, session writer
    └── conftest.py             # Shared fixtures for this agent
```

### Running Tests

```bash
# Run all tests
pytest agents/ -v

# Run tests for one agent
pytest agents/rico_baseline/tests/ -v

# Run with coverage
pytest agents/ --cov=agents --cov=utils --cov-report=term-missing

# Run only unit tests (fast)
pytest agents/ -v -m unit

# Run only integration tests (slower, may call LLM)
pytest agents/ -v -m integration
```

### Markers

Define in `pyproject.toml` or `pytest.ini`:

```ini
[tool:pytest]
markers =
    unit: Pure logic tests, no LLM calls, no GCS calls
    integration: Tests that call real GCS or LLM (slower, may cost tokens)
    slow: Tests that take > 10 seconds
```

### What to Test Per Agent

#### Agent 1A — Rico Baseline

| Test | Type | What It Asserts |
|------|------|----------------|
| `test_gcs_reader_returns_data` | unit | GCS reader tool returns non-empty string from known file |
| `test_gcs_reader_missing_file` | unit | GCS reader returns error dict (not exception) for missing file |
| `test_token_tracker_captures_metrics` | unit | `track_usage()` wrapper returns dict with all 6 required fields |
| `test_token_tracker_fields_are_numeric` | unit | input_tokens, output_tokens, etc. are int/float, not None |
| `test_run_receipt_written` | integration | After agent run, receipt JSON exists in expected GCS path |
| `test_run_receipt_schema` | unit | Receipt JSON contains all 10 required fields |
| `test_agent_responds_to_product_query` | integration | Agent returns non-empty response for "What products do you have?" |

#### Agent 1B — Rico Cached

| Test | Type | What It Asserts |
|------|------|----------------|
| `test_context_cache_created` | integration | Vertex context cache is created successfully |
| `test_cached_tokens_greater_than_zero` | integration | `cached_tokens > 0` in token tracker output |
| `test_input_tokens_reduced_vs_baseline` | integration | Rico B input_tokens < Rico A input_tokens for same query |
| `test_latency_within_bounds` | integration | Response latency < 2x Rico A latency (cache shouldn't be slower) |
| `test_cache_reuse_across_turns` | integration | Second query in same session still shows cached_tokens > 0 |

#### Agent 3 — Skills Agent

| Test | Type | What It Asserts |
|------|------|----------------|
| `test_skill_file_readable` | unit | GCS reader can fetch skill file content |
| `test_session_file_written` | integration | After "write session memory" skill, GCS file exists with today's date |
| `test_session_file_content_not_empty` | integration | Written session file contains actual conversation summary |
| `test_session_file_rolling_7_day` | unit | Files older than 7 days are cleaned up (or not created) |
| `test_skill_modifies_state` | integration | After skill execution, `session.state` contains expected flags |
| `test_skill_does_not_persist_beyond_scope` | integration | Turn-scoped skill flags are cleared on next turn |

#### Agent 2 — Jarvis RAG

| Test | Type | What It Asserts |
|------|------|----------------|
| `test_rag_corpus_exists` | integration | Vertex RAG corpus is accessible and contains documents |
| `test_rag_retrieval_returns_chunks` | integration | Query returns non-empty retrieval results |
| `test_rag_retrieval_relevance` | integration | Top chunk for known query contains expected keyword |
| `test_agent_cites_source` | integration | Agent response includes reference to source document |

#### Agent 4 — Live Context Agent

| Test | Type | What It Asserts |
|------|------|----------------|
| `test_file_upload_pdf` | integration | Agent can ingest a test PDF via Files API |
| `test_file_upload_image` | integration | Agent can describe a test image |
| `test_comprehension_accuracy` | integration | Agent answers factual question about uploaded doc correctly |
| `test_file_token_count_reported` | integration | Token tracker captures file ingestion tokens |

#### Agent 5 — MCP Tools Agent

| Test | Type | What It Asserts |
|------|------|----------------|
| `test_mcp_connection` | integration | MCPToolset connects to running MCP server |
| `test_tool_filter_limits_tools` | unit | Filtered toolset only exposes specified tool names |
| `test_sequential_execution` | integration | Agent calls tools one at a time (no parallel calls) |
| `test_multiple_mcp_servers` | integration | Agent can use tools from 2 different MCP servers |

---

### Shared Module Tests

These live in `utils/tests/` and run with every agent build.

```
utils/
├── __init__.py
├── token_calculator.py
├── run_receipt.py
├── session_writer.py
├── gcs_utils.py
└── tests/
    ├── __init__.py
    ├── test_token_calculator.py
    ├── test_run_receipt.py
    ├── test_session_writer.py
    └── test_gcs_utils.py
```

| Module | Test | What It Asserts |
|--------|------|----------------|
| token_calculator | `test_returns_all_six_fields` | Dict has input_tokens, output_tokens, cached_tokens, total_tokens, latency_ms, cost_estimate_usd |
| token_calculator | `test_handles_missing_usage_metadata` | Returns zeroes (not crash) if model response lacks usage_metadata |
| run_receipt | `test_receipt_schema_valid` | JSON matches the 10-field schema from MASTER_BRIEF |
| run_receipt | `test_receipt_writes_to_gcs` | File appears at expected GCS path |
| run_receipt | `test_receipt_run_id_unique` | Two consecutive receipts have different run_ids |
| session_writer | `test_writes_dated_file` | File created at `sessions/session-{YYYY-MM-DD}.md` |
| session_writer | `test_appends_to_existing` | Second write on same day appends, doesn't overwrite |
| session_writer | `test_cleanup_old_files` | Files older than 7 days are removed |
| gcs_utils | `test_read_existing_file` | Returns string content for known file |
| gcs_utils | `test_read_missing_file` | Returns None or empty string (not exception) |
| gcs_utils | `test_write_and_read_roundtrip` | Write then read returns same content |

---

### Mocking Strategy

For **unit tests** (no real GCS, no real LLM):

```python
# conftest.py — shared fixtures
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_gcs_client():
    """Mock GCS client that returns predictable data."""
    with patch('google.cloud.storage.Client') as mock_client:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = "Product 1: Widget\nProduct 2: Gadget"
        mock_bucket.blob.return_value = mock_blob
        mock_client.return_value.bucket.return_value = mock_bucket
        yield mock_client


@pytest.fixture
def mock_usage_metadata():
    """Mock Gemini response with usage_metadata."""
    return {
        "prompt_token_count": 150,
        "candidates_token_count": 50,
        "cached_content_token_count": 100,
        "total_token_count": 200,
    }


@pytest.fixture
def sample_run_receipt():
    """Valid run receipt for schema testing."""
    return {
        "run_id": "test-uuid-1234",
        "agent_name": "rico_baseline",
        "timestamp": "2026-02-27T10:00:00Z",
        "skills_used": [],
        "tools_used": ["read_gcs_file"],
        "token_metrics": {
            "input_tokens": 150,
            "output_tokens": 50,
            "cached_tokens": 0,
            "total_tokens": 200,
            "latency_ms": 1200,
            "cost_estimate_usd": 0.0003
        },
        "latency_ms": 1200,
        "status": "success",
        "artifacts_created": []
    }
```

For **integration tests** (real GCS, real LLM):

- Use a dedicated test bucket or test prefix: `gs://{bucket}/test/`
- Mark with `@pytest.mark.integration`
- These cost tokens. Run intentionally, not on every save.
- CI runs unit tests always, integration tests on PR only.

---

## Layer 2: adk eval — Behavioral Tests

### What adk eval Does

`adk eval` sends predefined queries to the agent and evaluates responses against expected criteria.
It's the LLM-quality layer — not "did the tool work" but "did the agent give a good answer."

### Eval File Structure

```
agents/rico_baseline/
└── tests/
    └── eval_cases.json
```

### Eval Case Format

```json
{
  "eval_cases": [
    {
      "name": "product_list_query",
      "input": "What products do you have?",
      "expected_tool_calls": ["read_gcs_file"],
      "expected_response_contains": ["Widget", "Gadget"],
      "expected_response_not_contains": ["I don't know", "I cannot"],
      "criteria": "Agent should list all products from the GCS product file."
    },
    {
      "name": "unknown_product_query",
      "input": "Tell me about the XYZ-9000 product.",
      "expected_tool_calls": ["read_gcs_file"],
      "expected_response_contains": ["not found", "don't have"],
      "criteria": "Agent should indicate the product is not in the catalog, not hallucinate."
    },
    {
      "name": "follow_up_memory",
      "input": ["What products do you have?", "Tell me more about the first one."],
      "criteria": "Agent should remember the first query and provide details about the first product listed."
    }
  ]
}
```

### Running Evals

```bash
# Run eval for one agent
adk eval agents/rico_baseline/tests/eval_cases.json --agent agents/rico_baseline

# Run all evals
adk eval agents/*/tests/eval_cases.json
```

**Note:** The exact `adk eval` CLI syntax may vary. During Step 0 (Starter Kit Discovery), Claude should verify the current `adk eval` interface and document it. If `adk eval` doesn't support this exact format, adapt the eval runner to match what ADK provides. The eval CASES (the JSON) are the important part — the runner is just plumbing.

### Eval Cases Per Agent

#### Agent 1A — Rico Baseline

| Case | Input | Success Criteria |
|------|-------|-----------------|
| Product list | "What products do you have?" | Lists products from GCS file |
| Specific product | "Tell me about [known product]" | Returns accurate details |
| Unknown product | "Tell me about XYZ-9000" | Says not found, doesn't hallucinate |
| Follow-up | ["List products", "More about the first one"] | Remembers context |
| Off-topic | "What's the weather?" | Stays in scope, redirects to products |

#### Agent 1B — Rico Cached

Same eval cases as 1A (identical queries). The point is to compare:
- Same quality of answers (caching shouldn't degrade response quality)
- Lower token usage (the whole point of caching)

#### Agent 3 — Skills Agent

| Case | Input | Success Criteria |
|------|-------|-----------------|
| Trigger session write | "Save this conversation" | Writes session file to GCS |
| Trigger summarize | "Summarize our conversation" | Returns coherent summary |
| No false trigger | "Tell me about skills" | Does NOT execute a skill, just answers |
| Multi-turn memory | ["My name is Tony", "What's my name?"] | Recalls from session context |

#### Agent 2 — Jarvis RAG

| Case | Input | Success Criteria |
|------|-------|-----------------|
| Known doc query | "What is the folder structure convention?" | Retrieves from playbook, cites source |
| Cross-doc query | "How do skills relate to session memory?" | Synthesizes from multiple docs |
| Unknown topic | "What is quantum computing?" | Says not in docs, doesn't hallucinate from training data |
| Specificity | "What model should I use for agents?" | Returns "gemini-2.5-flash" from docs |

#### Agent 4 — Live Context Agent

| Case | Input | Success Criteria |
|------|-------|-----------------|
| PDF comprehension | [upload test.pdf] "What is this about?" | Accurate summary of PDF content |
| Image description | [upload test.png] "Describe this image" | Accurate visual description |
| Factual extraction | [upload test.pdf] "What is the main conclusion?" | Extracts specific fact from doc |

#### Agent 5 — MCP Tools Agent

| Case | Input | Success Criteria |
|------|-------|-----------------|
| Single tool call | "Calculate 42 * 17" | Calls calculator tool, returns 714 |
| Sequential tools | "Search for X then summarize" | Calls search, waits, then summarizes |
| Tool not available | "Delete the database" | Refuses, tool not in filtered set |

---

## Regression Testing

### The Rule

**When building Agent N, all tests for Agents 1 through N-1 must still pass.**

### How to Enforce

```bash
# Before starting Agent 3, verify Agents 1A, 1B still pass:
pytest agents/rico_baseline/tests/ agents/rico_cached/tests/ -v

# Before merging any PR:
pytest agents/ utils/ -v
```

### Run Receipt Regression

Run receipts enable regression detection in Phase 2:

1. **Baseline receipts** — After Agent 1A passes all tests, save its run receipts as baseline
2. **Comparison** — When Agent 2 is built, re-run Agent 1A tests and compare receipts
3. **Red flags:**
   - `input_tokens` increased by > 20% (something changed in context)
   - `latency_ms` increased by > 50% (performance regression)
   - `status` changed from `success` to `failure` (broken)
   - New `tools_used` that weren't there before (unexpected behavior)

Phase 1 approach: **manual comparison**. Phase 2: automated receipt diffing.

---

## The Rico A vs Rico B Comparison Protocol

This is the most important test in Phase 1A. It proves whether context caching works and how much it saves.

### Protocol

1. Define 10 test queries (mix of simple, complex, follow-up)
2. Run all 10 against Rico A (baseline) — collect run receipts
3. Run same 10 against Rico B (cached) — collect run receipts
4. Compare side-by-side:

| Metric | Rico A (Baseline) | Rico B (Cached) | Delta | Pass? |
|--------|------------------|----------------|-------|-------|
| avg input_tokens | X | Y | Y-X | Y < X |
| avg cached_tokens | 0 | Z | Z | Z > 0 |
| avg latency_ms | A | B | B-A | B ≤ 1.5×A |
| avg cost_estimate_usd | C | D | D-C | D < C |
| response quality | pass/fail per eval | pass/fail per eval | — | Same or better |

### Success Criteria

Rico B passes if ALL of these are true:
- `cached_tokens > 0` (cache is actually being used)
- `input_tokens` reduced vs Rico A (fewer cold-read tokens)
- `latency_ms` not worse than 1.5x Rico A (cache shouldn't slow things down)
- `cost_estimate_usd` reduced vs Rico A (the whole point)
- All eval cases pass with same quality as Rico A

### Comparison Script

Build a simple Python script: `scripts/compare_ricos.py`

```python
# scripts/compare_ricos.py
"""
Compare run receipts between Rico A and Rico B.
Reads receipts from GCS, computes averages, prints comparison table.
"""
import json
from utils.gcs_utils import list_files, read_file


def load_receipts(agent_name: str) -> list[dict]:
    """Load all run receipts for an agent from GCS."""
    prefix = f"agents/{agent_name}/receipts/"
    files = list_files(prefix)
    return [json.loads(read_file(f)) for f in files]


def average_metrics(receipts: list[dict]) -> dict:
    """Compute average token metrics across all receipts."""
    if not receipts:
        return {}
    metrics = [r["token_metrics"] for r in receipts]
    keys = ["input_tokens", "output_tokens", "cached_tokens",
            "total_tokens", "latency_ms", "cost_estimate_usd"]
    return {k: sum(m[k] for m in metrics) / len(metrics) for k in keys}


def compare():
    a = average_metrics(load_receipts("rico_baseline"))
    b = average_metrics(load_receipts("rico_cached"))

    print(f"{'Metric':<25} {'Rico A':<15} {'Rico B':<15} {'Delta':<15} {'Pass?':<10}")
    print("-" * 80)
    for key in a:
        delta = b[key] - a[key]
        passed = "✅" if b[key] <= a[key] else "❌"
        if key == "cached_tokens":
            passed = "✅" if b[key] > 0 else "❌"
        print(f"{key:<25} {a[key]:<15.2f} {b[key]:<15.2f} {delta:<15.2f} {passed}")


if __name__ == "__main__":
    compare()
```

---

## Test Naming Conventions

```
test_{what}_{expected_outcome}

Examples:
  test_gcs_reader_returns_data
  test_gcs_reader_missing_file_returns_error
  test_token_calculator_captures_all_fields
  test_cached_tokens_greater_than_zero
  test_skill_does_not_persist_beyond_scope
```

---

## CI Integration (Phase 1 — Minimal)

Phase 1 does NOT require a full CI pipeline. But establish the habit:

```bash
# Pre-commit check (run manually before every PR)
pytest agents/ utils/ -v -m 'not slow'
```

Phase 2 will add GitHub Actions with:
- Unit tests on every push
- Integration tests on PR to main
- Eval runs on PR to main (with cost budget)

---

## Test Data

### Test Fixtures Location

```
tests/
└── fixtures/
    ├── sample_product_list.txt    # Known product data for Rico tests
    ├── sample_skill_file.md       # Known skill file for Skills Agent tests
    ├── sample_session_file.md     # Known session file for session writer tests
    ├── test_document.pdf           # Small PDF for Live Context tests
    ├── test_image.png              # Small image for Live Context tests
    └── sample_receipt.json         # Valid run receipt for schema tests
```

### GCS Test Prefix

All integration tests that write to GCS use the prefix:
```
gs://{bucket}/test/agents/{agent_name}/...
```

Tests clean up after themselves. Every integration test that writes to GCS should delete what it created in teardown.

---

## Coverage Targets

Phase 1 targets (realistic, not aspirational):

| Component | Target |
|-----------|--------|
| Shared modules (token_calculator, run_receipt, session_writer, gcs_utils) | 90%+ |
| Agent tools (tools.py per agent) | 80%+ |
| Agent integration (agent.py) | 60%+ (LLM responses are non-deterministic) |

Don't chase 100%. The LLM layer is inherently non-deterministic. That's what evals are for.

---

## Quick Reference — Test Checklist Per Agent

Before marking any agent as DONE:

- [ ] `tests/test_tools.py` — All tool functions have unit tests
- [ ] `tests/test_agent.py` — Agent responds to basic queries (integration)
- [ ] `tests/test_shared_modules.py` — Token tracker + run receipt work for this agent
- [ ] `tests/eval_cases.json` — At least 5 eval cases defined
- [ ] `pytest agents/{agent_name}/tests/ -v` — All pass
- [ ] `pytest agents/ utils/ -v` — Full regression suite passes
- [ ] Run receipt generated and saved to GCS

---

## What Claude Reads Next

After this document:

1. **PHASE_1A_AGENT_SET_1_RICO_CACHING.md** — First agent to build (Rico A + Rico B)
2. Then follow the build order from PHASE_1_OVERVIEW.md

---

*Generated by JARVIS — Cyberize Engineering AI Factory*
*Version: 1.0 | Date: February 28, 2026*