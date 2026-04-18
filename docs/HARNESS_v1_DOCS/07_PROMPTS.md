# 07 — Prompts

**ADK Agent Harness v1**

---

## Prompt Architecture Overview

`architect_agent` uses a **dual prompt system**: two separate markdown files stored in GCS are merged at runtime into a single instruction string before every model invocation.

```
GCS: globals/global_agent_system_prompt.md
             +  (separated by delimiter)
GCS: architect_agent/architect_agent_system_prompt.md
             ↓
     fetch_dual_instructions("architect_agent")
             ↓
     single combined instruction string
             ↓
     [SYSTEM_TIMESTAMP: ...] prepended by callback
             ↓
     Gemini model receives full instruction
```

---

## The Two Prompts

### Global System Prompt

**GCS path:** `{BASE}/globals/global_agent_system_prompt.md`

**Scope:** Applies to all agents. Contains shared standards and behavior defaults that every agent in the harness should follow.

**What it typically covers:**
- General behavior rules and tone
- How to use tools (when to call them, when not to)
- Format conventions
- Out-of-scope handling
- How to use session memory
- How to use skills
- How to respond to engineer prompt requests

**Important:** This prompt is shared. Changes here affect every agent that uses `fetch_dual_instructions()`. Be intentional about what goes here vs. in the identity prompt.

---

### Identity Prompt

**GCS path:** `{BASE}/{agent_name}/{agent_name}_system_prompt.md`

For `architect_agent`: `{BASE}/architect_agent/architect_agent_system_prompt.md`

**Scope:** Agent-specific. Defines who this agent is, what it knows, what its scope is, and what makes it different from other agents.

**What it typically covers:**
- Agent name and persona
- Domain expertise and role definition
- Scope boundaries (what to help with, what to decline)
- Agent-specific tool guidance (when to call `read_context_doc`, which context docs exist)
- Project-specific knowledge
- Engineer prompt format this agent uses

---

## Dual Instruction Delimiter

The two prompts are joined with a fixed delimiter:

```
\n\n---\n# AGENT IDENTITY\n---\n\n
```

In the combined instruction string, the global prompt comes first, then this separator, then the identity prompt. This gives the model clear visual structure separating shared rules from agent-specific identity.

**Constant defined in `utils/gcs_utils.py`:**
```python
DUAL_INSTRUCTION_DELIMITER = "\n\n---\n# AGENT IDENTITY\n---\n\n"
```

---

## Hot-Reload: Callable Instructions

The agent's `instruction` parameter is a callable, not a string:

```python
def get_live_instructions(ctx) -> str:
    return fetch_dual_instructions("architect_agent")

root_agent = Agent(
    instruction=get_live_instructions,  # callable — called on every request
    ...
)
```

When ADK receives a user message, it calls `get_live_instructions(ctx)` before invoking the model. This means:

- **Prompt edits in GCS take effect on the next message** — no restart, no redeploy
- Every turn pays ~50-100ms for two GCS reads (acceptable latency for a dev agent)
- There is no prompt caching by default — every request fetches fresh

This pattern is intentional. In a production deployment, `ContextCacheConfig` could cache the static portions of the prompt to reduce latency and cost — but that is a Phase 2 concern.

---

## Timestamp Injection

On every model invocation, `get_timestamp_inject_callback()` prepends a timestamp line to the system instruction:

```
[SYSTEM_TIMESTAMP: 2026-04-14T12:30:00Z]

{rest of combined instruction}
```

**Why:** The model's training data has a knowledge cutoff. Injecting the current UTC time lets the agent know what day it is without needing to call `get_current_datetime`. If the timestamp callback is working correctly, the agent reads time from this injected line — not from a tool call.

**Technical detail:** The callback strips any previous `[SYSTEM_TIMESTAMP:]` line before prepending a new one. This prevents accumulation across turns — without the strip, the agent would see a growing list of timestamps and might read the oldest (stale) one.

**Debug signal:** Every turn should print `[timestamp_callback] [SYSTEM_TIMESTAMP: ...]` to the terminal. If this line is missing, the callback is not running — check `before_model_callback` wiring in `agent.py`.

---

## Prompt Update Workflow

To update a prompt:

1. Open the file in GCS (Cloud Console, gsutil, or a GCS editor)
2. Edit and save
3. Send any message to the agent — the new prompt takes effect immediately

No restart, no redeploy, no code change required.

**To verify the update landed:** Ask the agent something that directly exercises the changed instruction. Watch the Trace tab to confirm the tool calls (or absence of them) match your expectation.

---

## Older Agents: Single Prompt

`jarvis_agent` and `product_agent_rico_1` use the older `fetch_instructions()` function, which loads only the identity prompt (no global prompt merge):

```python
def get_live_instructions(ctx) -> str:
    return fetch_instructions("jarvis_agent")
```

GCS path for these: `{BASE}/{agent_name}/{agent_name}_instructions.txt`

Note the `.txt` extension — older convention. New agents should use the dual prompt system with `.md` files.

---

## `ghl_mcp_agent`: Inline Prompt

`ghl_mcp_agent` does not load from GCS. Its instructions are defined inline as a Python function:

```python
def get_rico_instructions(ctx) -> str:
    return f"""
    Your name is Rico! ...
    IMPORTANT: Your locationId is already set — it is {GHL_LOCATION_ID}.
    ...
    """
```

This is appropriate for a standalone integration agent where the prompt is short, stable, and needs to embed environment variables (the location ID) at runtime. No hot-reload is needed for this agent.

---

## Prompt-to-Behavior Traceability

The manual test plan (`MANUAL_TEST_PLAN.md`) is the best way to verify that prompts are working as intended. Each scenario exercises a specific behavior driven by the system prompt:

| Test scenario | Prompt section being tested |
|---------------|---------------------------|
| Session Memory Restore | Global prompt — session memory preamble |
| Skill Invocation | Global prompt — when to use skills |
| Context Doc Loading | Identity prompt — context doc guidance |
| Scope Discipline | Identity prompt — scope boundaries |
| Engineer Prompt Style | Identity prompt or global — prompt format |
| Stays in Role | Identity prompt — persona + search discipline |
| Temporal Awareness | Callback injection + global prompt — time awareness |

If a scenario fails, the root cause is almost always in the relevant prompt section — not in the code.

---

*See `08_TESTING_AND_EVALS.md` for the testing and eval strategy.*
