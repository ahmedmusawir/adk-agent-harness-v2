# 01 — Architecture

**ADK Agent Harness v1**

---

## What the Harness Is

The harness is a shared scaffold layered around Google ADK agents. The core idea: **put everything that changes in GCS, keep everything that doesn't change in code.**

- System prompts → GCS (hot-reloadable, no redeploy needed)
- Session memory → GCS (persists across sessions)
- Skills and context docs → GCS (updateable without touching code)
- Token costs, latency → local JSONL (observable, reportable)

All agents in the repo share the same `utils/`, `callbacks/`, and GCS path conventions. Adding a new agent means wiring those shared components in — not rebuilding them.

---

## ADK Framework Basics

Every agent is a Python `Agent` object from `google.adk.agents`. ADK handles:

- Routing user messages to the agent
- Managing the conversation loop
- Calling tools (FunctionTools, AgentTools, MCPToolsets)
- Running before/after model callbacks
- The `adk web .` development UI

**The required export:** Every agent folder must have an `__init__.py` that exports `root_agent`. That is how `adk web .` discovers agents.

```python
# architect_agent/__init__.py
from .agent import root_agent
```

**ADK v1.13.0 constraint:** `google_search` (built-in) cannot be mixed with custom `FunctionTool` instances in the same agent. Workaround: wrap `google_search` in a dedicated sub-agent and expose it via `AgentTool`. See `architect_agent/agent.py`.

---

## Dual Instructions Pattern

`architect_agent` uses the **dual instructions pattern**: two prompts merged at runtime, loaded from GCS.

```
GCS: globals/global_agent_system_prompt.md
                    +
GCS: architect_agent/architect_agent_system_prompt.md
                    ↓
         fetch_dual_instructions()
                    ↓
      combined instruction string passed to Agent
```

**Load order:**
1. Global prompt — applies to all agents (shared standards, format rules, behavior defaults)
2. Delimiter: `\n\n---\n# AGENT IDENTITY\n---\n\n`
3. Identity prompt — defines this specific agent's persona, role, tools, and scope

**Fallback behavior:**
- If global prompt fails to load → falls back to identity-only (logs a warning)
- If identity prompt fails to load → returns an error string (agent will not function correctly)

**Why this matters:** You can update shared behavior for all agents by editing one file in GCS. You can tune a specific agent's persona without touching the global prompt.

---

## Hot-Reload Instructions

Instructions are fetched on every request, not at startup:

```python
def get_live_instructions(ctx) -> str:
    return fetch_dual_instructions("architect_agent")

root_agent = Agent(
    instruction=get_live_instructions,  # callable, not a string
    ...
)
```

When `instruction` is a callable, ADK calls it before each model invocation. This means:

- Editing a prompt in GCS takes effect on the next message — no restart needed
- No caching of stale prompts across sessions
- Each turn pays the latency cost of a GCS read (typically <100ms)

---

## Callback Chain

`architect_agent` runs three callbacks per turn:

```
User message arrives
        ↓
[before_model_callback #1] get_start_time_callback()
  → records time.time() in session state as _run_start_time
        ↓
[before_model_callback #2] get_timestamp_inject_callback()
  → strips any prior [SYSTEM_TIMESTAMP:] line from system instruction
  → prepends [SYSTEM_TIMESTAMP: 2026-04-14T12:00:00Z] to system instruction
  → prints [timestamp_callback] line to terminal for debug visibility
        ↓
Model runs (Gemini)
        ↓
[after_model_callback] get_receipt_callback()
  → skips streaming chunks (partial=True)
  → computes latency_ms from _run_start_time
  → counts tokens via Vertex AI API
  → estimates cost from pricing table
  → writes receipt to logs/receipts/architect_agent.jsonl
        ↓
Response delivered to user
```

**Why replace instead of append for the timestamp:** ADK's `append_instructions()` accumulates across turns in a session. If the first turn's timestamp is never removed, the agent reads the oldest (stale) timestamp on every subsequent turn. The callback strips the previous line and prepends a fresh one.

---

## GCS as the Source of Truth

Everything dynamic lives in GCS under a single base folder:

```
{GCS_BASE_FOLDER}/
├── globals/
│   ├── global_agent_system_prompt.md        ← shared system prompt
│   └── skills/
│       ├── SKILL_INDEX.md                   ← flat index file
│       └── SESSION_UPDATE_SKILL/
│           └── SKILL.md                     ← skill instructions
└── architect_agent/
    ├── architect_agent_system_prompt.md     ← identity prompt
    ├── sessions/
    │   └── session-2026-04-14.md            ← session memory files
    └── context/
        └── APP_ARCHITECTURE_MANUAL.md       ← context doc
```

Two environment variables point the code at the right location:

```bash
GCS_BUCKET_NAME=adk-agent-context-ninth-potion-455712-g9
GCS_BASE_FOLDER=ADK_Agent_Bundle_1
```

All tool functions and `gcs_utils.py` read these at runtime. No GCS paths are hardcoded in application logic.

---

## Search Sub-Agent Pattern

`google_search` is a built-in ADK tool that cannot coexist with custom `FunctionTool` instances in the same agent (ADK v1.13.0 limitation). The workaround:

```python
# 1. Create a dedicated sub-agent with only google_search
search_specialist = Agent(
    name="search_specialist",
    model="gemini-2.5-flash",
    tools=[google_search],
)

# 2. Wrap it so it looks like a tool to the parent agent
search_specialist_tool = AgentTool(agent=search_specialist)

# 3. Add it to the parent alongside custom tools
root_agent = Agent(
    tools=[
        search_specialist_tool,   # ← AgentTool wrapping the sub-agent
        write_session_memory_tool,
        read_session_memory_tool,
        # ...
    ]
)
```

When `architect_agent` calls `search_specialist`, ADK routes the query to the sub-agent, which runs its own Gemini call with `google_search`, then returns the result to the parent agent.

---

## What Makes This a "Harness"

The harness components that apply to any agent:

| Component | File | What it provides |
|-----------|------|-----------------|
| GCS instruction loader | `utils/gcs_utils.py` | `fetch_dual_instructions()`, `fetch_instructions()` |
| Token counting | `utils/token_calculator.py` | `count_tokens()`, `estimate_cost()` |
| Receipt creation | `utils/run_receipt.py` | `create_receipt()`, `save_receipt_to_file()` |
| Callback chain | `callbacks/receipt_callback.py` | `get_start_time_callback()`, `get_timestamp_inject_callback()`, `get_receipt_callback()` |
| Usage reporting | `scripts/usage_report.py` | Daily cost/token table from JSONL |

A new agent wires these in and defines its own tools and GCS path. The shared infrastructure is already tested and working.

---

*See `02_FILE_STRUCTURE.md` for the full repo and GCS layout.*
