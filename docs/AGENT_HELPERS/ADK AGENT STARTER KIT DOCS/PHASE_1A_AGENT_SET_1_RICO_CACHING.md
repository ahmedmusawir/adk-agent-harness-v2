# PHASE_1A_AGENT_SET_1_RICO_CACHING.md
# Agent Set 1 — Rico A (Baseline) + Rico B (Cached)
**Version:** 2.1
**Date:** 2026-02-28
**Prerequisite:** STARTER_KIT_SPEC.md must be executed first (repo cleaned up, stubs in place)
**References:** MASTER_BRIEF.md, PHASE_1_OVERVIEW.md, PHASE_1_TESTING_STRATEGY.md, STARTER_KIT_SPEC.md

---

## CRITICAL RULE — Git Workflow

**Claude does NOT commit code. Ever.**

When a build step is complete:

1. Run `pytest` on all relevant tests
2. Run `pytest tests/ -v` for full regression (all existing agent tests must still pass)
3. If ALL tests pass → tell Tony: "All tests passing. Ready for your review and commit."
4. If ANY test fails → fix it first, re-run, do NOT present broken code
5. **Tony reviews the code and commits.** Claude never runs `git add`, `git commit`, or `git push`.

This is non-negotiable. Tony is the driver. Claude is the engineer presenting work for approval.

---

## Purpose

Build two versions of the same agent to measure the impact of Vertex AI Context Caching:

- **Rico A** — The existing `product_agent` with a token tracker bolted on. No caching. This is the baseline.
- **Rico B** — A clone of Rico A with Vertex AI Context Caching enabled. Same prompt, same tools, same questions.

The deliverable is a **side-by-side comparison table** showing token usage and cost difference.

---

## Starting Point — What Already Exists

After STARTER_KIT_SPEC.md is executed, the repo has:

```
adk-harness-starter-v1/
│
├── product_agent/                  # Rico A lives HERE — DO NOT MOVE
│   ├── agent.py                    # Existing agent definition
│   └── __init__.py                 # from .agent import root_agent
│
├── utils/
│   ├── gcs_utils.py               # fetch_instructions() — GCS hot-reload (WORKING, DO NOT MODIFY)
│   ├── context_utils.py            # fetch_context() — GCS knowledge base tool (WORKING, DO NOT MODIFY)
│   ├── token_calculator.py         # STUB — implement in this brief
│   ├── run_receipt.py              # STUB — implement in this brief
│   ├── session_writer.py           # STUB — implement later (Agent 3)
│   └── session_reader.py           # STUB — implement later (Agent 3)
│
├── jarvis_agent/                   # Keep — future RAG agent (Phase 1B)
├── ghl_mcp_agent/                  # Keep — MCP pattern reference only
│
├── docs/
│   ├── overview.md
│   ├── architecture.md
│   ├── patterns.md
│   ├── decisions.md
│   └── api-info.md
│
├── Dockerfile
├── deploy.sh
├── store_secrets.sh
├── grant_permissions.sh
├── start_server.sh
├── requirements.txt
├── .env_example
├── CLAUDE.md
├── MASTER_BRIEF.md
├── PHASE_1_OVERVIEW.md
├── PHASE_1_TESTING_STRATEGY.md
└── STARTER_KIT_SPEC.md
```

---

## GCS Bucket Structure (Existing)

```
Bucket: adk-agent-context-ninth-potion-455712-g9
└── ADK_Agent_Bundle_1/
    ├── product_agent/
    │   └── product_agent_instructions.txt    ← Rico's system prompt (~31k tokens)
    ├── jarvis_agent/
    │   └── jarvis_agent_instructions.txt
    ├── context_store/
    │   ├── PRODUCTS.md                       ← DockBloxx product knowledge base
    │   └── moose_resume.txt
    ├── sessions/                             ← NEW: session files go here
    │   └── {agent_name}/
    │       └── {user_id}_{session_id}.json
    └── run_receipts/                         ← NEW: telemetry logs go here
        └── {YYYY-MM-DD}.jsonl
```

---

## How Rico Works Today

Rico is a DockBloxx product support agent. He knows 33 products.
His instructions (~31k tokens) live in GCS and are fetched at request time using the callable instruction pattern.

```python
# product_agent/agent.py (current — simplified)
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from utils.gcs_utils import fetch_instructions
from utils.context_utils import fetch_context

def get_live_instructions(ctx) -> str:
    return fetch_instructions("product_agent")

product_context_tool = FunctionTool(func=fetch_context)

root_agent = Agent(
    name="product_agent",
    model="gemini-2.5-flash",
    description="DockBloxx product specialist",
    instruction=get_live_instructions,
    tools=[product_context_tool]
)
```

**Key pattern:** `instruction=get_live_instructions` — callable, not string. ADK calls it fresh on every run. See `docs/patterns.md` Pattern 1 and Pattern 2.

---

## BUILD ORDER

### Step 1: Implement `utils/token_calculator.py`

Replace the stub with a working token tracker.

**What it does:**
- Wraps `google.genai` to count tokens for a given text + model
- Returns a dict with `input_tokens`, `cached_tokens`, `output_tokens`, `total_tokens`
- Uses `client.models.count_tokens()` from the Vertex AI SDK

**Implementation approach:**

```python
# utils/token_calculator.py
import os
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")

from google import genai

client = genai.Client()

def count_tokens(text: str, model: str = "gemini-2.5-flash") -> dict:
    """
    Count tokens for a given text using Vertex AI.

    Returns:
        dict with 'total_tokens' (int)
    """
    response = client.models.count_tokens(
        model=model,
        contents=text,
    )
    return {
        "total_tokens": response.total_tokens,
    }


def count_instruction_tokens(agent_name: str, model: str = "gemini-2.5-flash") -> dict:
    """
    Fetch an agent's GCS instructions and count their tokens.
    Convenience wrapper: fetch + count in one call.
    """
    from utils.gcs_utils import fetch_instructions
    instructions = fetch_instructions(agent_name)
    token_count = count_tokens(instructions, model)
    token_count["agent_name"] = agent_name
    token_count["instruction_char_length"] = len(instructions)
    return token_count
```

**Test:** `pytest tests/test_token_calculator.py -v`

---

### Step 2: Implement `utils/run_receipt.py`

Replace the stub with a working JSONL logger.

**What it does:**
- Logs every agent run as a single JSON line to a local file
- One file per day: `run_receipts/{YYYY-MM-DD}.jsonl`
- Each line captures: `run_id`, `agent_name`, `timestamp`, `model`, `input_tokens`, `output_tokens`, `cached_tokens`, `total_tokens`, `latency_ms`, `status` (success/error), `error_message` (if any)

**Implementation approach:**

```python
# utils/run_receipt.py
import json
import os
import uuid
from datetime import datetime, timezone

RECEIPT_DIR = "run_receipts"


def log_run(
    agent_name: str,
    model: str = "gemini-2.5-flash",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    latency_ms: float = 0.0,
    status: str = "success",
    error_message: str = None,
) -> dict:
    """Log a single agent run to daily JSONL file. Returns the receipt dict."""
    os.makedirs(RECEIPT_DIR, exist_ok=True)

    receipt = {
        "run_id": str(uuid.uuid4()),
        "agent_name": agent_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": input_tokens + output_tokens,
        "latency_ms": latency_ms,
        "status": status,
        "error_message": error_message,
    }

    filename = f"{RECEIPT_DIR}/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    with open(filename, "a") as f:
        f.write(json.dumps(receipt) + "\n")

    return receipt
```

**Note:** Phase 1 logs locally. GCS upload of receipts is a Phase 2 enhancement.

**Test:** `pytest tests/test_run_receipt.py -v`

---

### Step 3: Build Rico A (Baseline + Token Tracking)

**What changes from current Rico:** Nothing in the agent logic. We ADD token tracking around it.

**Approach:**
- Keep `product_agent/agent.py` exactly as-is
- Add a wrapper/callback that:
  1. Counts instruction tokens BEFORE the agent runs (using `count_instruction_tokens`)
  2. Captures response token usage AFTER the agent runs (from response metadata)
  3. Logs a run receipt via `log_run()`

**Where to add tracking:**
- Option A: ADK `after_model_callback` on the agent (preferred — cleanest)
- Option B: Wrapper in the agent.py that intercepts the response

**Discovery task:** Research how ADK exposes token usage in the response/callback. Check `adk-agents-fundamentals.md` and `adk-advanced-patterns.md` for callback patterns. Document findings in `DISCOVERY_NOTES.md`.

**Rico A success criteria:**
- Agent responds to product questions exactly as before (no behavior change)
- Every run produces a JSONL receipt with real token counts
- `count_instruction_tokens('product_agent')` returns the baseline token count

**Test:** `pytest tests/test_rico_a.py -v`

---

### Step 4: Build Rico B (Cached + Token Tracking)

**What Rico B adds:** Vertex AI Context Caching for the system prompt.

**How context caching works** (from `vertex-ai-integrations.md`):

```python
# Reference pattern — Vertex Context Caching
import os
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"

from google import genai
from google.genai import types
import datetime

client = genai.Client()

# Create a cache (do this ONCE, not per request)
cache = client.caches.create(
    model="gemini-2.5-flash",
    contents=[
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=large_document)]
        )
    ],
    system_instruction="You are an expert...",
    ttl=datetime.timedelta(hours=1),
)

# Use cache for queries (do this PER request)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=question,
    config=types.GenerateContentConfig(cached_content=cache.name),
)
```

**Rico B implementation plan:**

1. Create `rico_b/` folder (new agent alongside `product_agent/`)
2. Create `rico_b/cache_manager.py`:
   - `create_or_get_cache()` — creates a Vertex cache from Rico's GCS instructions
   - `get_cache_name()` — returns the active cache name (or None)
   - `invalidate_cache()` — deletes the cache (for testing/refresh)
   - Cache TTL: 1 hour (configurable)
3. Create `rico_b/agent.py`:
   - Same agent definition as Rico A
   - BUT uses `cached_content=cache_name` in the generation config
   - Same tools, same GCS knowledge base
4. Token tracking via same `run_receipt.py` — but now `cached_tokens` field will be non-zero

**Key discovery question:** How does ADK's `Agent()` accept a `cached_content` config? Options:
- Does `Agent()` have a `generate_content_config` parameter?
- Do we need to use `before_model_callback` to inject the cache?
- Or do we bypass ADK's Agent and call `client.models.generate_content()` directly in a tool?

**Document findings in `DISCOVERY_NOTES.md` before building.**

**Rico B success criteria:**
- Agent responds to product questions identically to Rico A
- Run receipts show `cached_tokens > 0`
- Run receipts show `input_tokens` significantly lower than Rico A for same queries

**Test:** `pytest tests/test_rico_b.py -v`

---

### Step 5: Comparison Script

Create `compare_ricos.py` in the repo root.

**What it does:**
1. Defines a list of 5-10 standard product questions
2. Runs each question through Rico A → logs receipt
3. Runs each question through Rico B → logs receipt
4. Reads both sets of receipts
5. Outputs a markdown comparison table:

```
| Question | Rico A Input Tokens | Rico B Input Tokens | Rico B Cached | Savings % |
|----------|--------------------|--------------------|---------------|-----------|
| What is...| 31,240             | 1,240              | 30,000        | 96%       |
```

6. Saves the table to `comparison_results.md`

**Test:** Run manually — this is a script, not a unit test.

---

### Step 6: Present for Review

When all steps are complete:

1. Run full regression: `pytest tests/ -v`
2. Confirm ALL tests pass (Rico A, Rico B, shared modules, AND any existing agent tests)
3. Run `compare_ricos.py` → generate `comparison_results.md`
4. Write `DISCOVERY_NOTES.md` with all findings (caching integration, token tracking, any gotchas)
5. **Tell Tony:** "All tests passing. Comparison table generated. Ready for your review and commit."

**DO NOT run git commands. Tony commits.**

---

## File Structure After Completion

```
adk-harness-starter-v1/
│
├── product_agent/                  # Rico A (baseline + token tracking)
│   ├── agent.py                    # Original agent — minimal changes (tracking only)
│   ├── __init__.py
│   └── tests/
│       └── test_rico_a.py
│
├── rico_b/                         # Rico B (cached)
│   ├── agent.py                    # Same as Rico A but with caching config
│   ├── cache_manager.py            # Cache lifecycle (create/get/invalidate)
│   ├── __init__.py
│   └── tests/
│       └── test_rico_b.py
│
├── utils/
│   ├── gcs_utils.py               # UNCHANGED
│   ├── context_utils.py            # UNCHANGED
│   ├── token_calculator.py         # IMPLEMENTED (Step 1)
│   ├── run_receipt.py              # IMPLEMENTED (Step 2)
│   ├── session_writer.py           # Still stub
│   └── session_reader.py           # Still stub
│
├── tests/
│   ├── test_token_calculator.py    # Unit tests for token calculator
│   ├── test_run_receipt.py         # Unit tests for run receipt logger
│   └── test_shared_modules.py      # Integration tests for shared utils
│
├── run_receipts/                   # Auto-created by run_receipt.py
│   └── {YYYY-MM-DD}.jsonl
│
├── compare_ricos.py                # Comparison script
├── comparison_results.md           # Generated comparison table
├── DISCOVERY_NOTES.md              # Findings from building Rico A + B
│
├── jarvis_agent/                   # Untouched
├── ghl_mcp_agent/                  # Untouched
├── docs/                           # Untouched
│
├── CLAUDE.md
├── MASTER_BRIEF.md
├── PHASE_1_OVERVIEW.md
├── PHASE_1_TESTING_STRATEGY.md
├── PHASE_1A_AGENT_SET_1_RICO_CACHING.md  ← THIS DOC
└── STARTER_KIT_SPEC.md
```

---

## Completion Checklist

```
[ ] utils/token_calculator.py — implemented, tested
[ ] utils/run_receipt.py — implemented, tested
[ ] product_agent/agent.py — Rico A with token tracking, tested in adk web
[ ] rico_b/cache_manager.py — cache lifecycle, tested
[ ] rico_b/agent.py — Rico B with caching + token tracking, tested in adk web
[ ] compare_ricos.py — comparison script, produces table
[ ] All unit tests passing: pytest tests/ -v
[ ] Full regression passing: pytest tests/ -v (includes ALL agents)
[ ] comparison_results.md — generated and reviewed
[ ] DISCOVERY_NOTES.md — findings documented
[ ] Presented to Tony for review and commit
```

---

## References

- `MASTER_BRIEF.md` — Project-wide rules and conventions
- `PHASE_1_OVERVIEW.md` — Phase 1 structure and agent list
- `PHASE_1_TESTING_STRATEGY.md` — Testing conventions and fixtures
- `STARTER_KIT_SPEC.md` — Repo cleanup and starter kit structure
- `docs/patterns.md` — Pattern 1 (agent definition), Pattern 2 (GCS hot-reload), Pattern 3 (GCS knowledge base)
- `docs/architecture.md` — GCS bucket structure, deployment architecture
- `docs/decisions.md` — Decision 6 (all Vertex), Decision 7 (GCS callable instructions)
- `vertex-ai-integrations.md` — Context Caching code patterns (reference doc)
- `adk-agents-fundamentals.md` — Agent structure, runner, event loop (reference doc)
- `adk-advanced-patterns.md` — Callbacks, state management (reference doc)

---

*Generated by JARVIS — Cyberize Engineering AI Factory*
*Version: 2.1 | Date: February 28, 2026*