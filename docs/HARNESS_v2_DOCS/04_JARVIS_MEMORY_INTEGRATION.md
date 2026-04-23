# 04 — Jarvis Memory Integration

**ADK Agent Harness v2**

---

## What changed in `jarvis_agent/`

v1 Jarvis was: `google_search` + two callbacks (receipt start-timer + receipt logger). That's it.

v2 Jarvis adds:
- **Custom `PreloadMemoryTopK` tool** for memory reads (replaces ADK's stock `preload_memory_tool`)
- **`after_agent_callback`** for gated memory writes
- **`memory_config.json`** — single control file for retrieval settings
- **Appended system-prompt addendum** describing the memory behavior (currently implicit; explicit memory-tool instruction was dropped when we went callback-only)

The existing receipt callbacks are untouched.

---

## File inventory

| File | Role |
|---|---|
| `jarvis_agent/agent.py` | Modified — imports custom tool, wires callback, keeps receipt hooks |
| `jarvis_agent/preload_memory_topk.py` | **NEW** — custom read tool |
| `jarvis_agent/memory_config.json` | **NEW** — `top_k`, `project_id`, `location` |

Nothing else in the agent folder changed.

---

## The read path — `PreloadMemoryTopK`

**Problem it solves:** ADK's stock `preload_memory_tool` calls `VertexAiMemoryBankService.search_memory`, which hardcodes `similarity_search_params={"search_query": query}` with **no `top_k`**. The server defaults to 3 results. Three isn't enough once the bank grows — relevant memories rank out of the top 3 and the agent looks amnesiac.

**Our fix:** bypass ADK's service layer for reads. The custom tool calls `memories.retrieve()` directly with an explicit `top_k` from config.

### How it works at turn time

1. ADK fires `PreloadMemoryTopK.process_llm_request(tool_context, llm_request)` before every LLM call.
2. Tool extracts the current user message from `tool_context.user_content`.
3. Builds scope from the session: `{"app_name": session.app_name, "user_id": session.user_id}`.
4. Reads `AGENT_ENGINE_ID` from `os.environ` (set by `run_jarvis_web.sh`).
5. Calls `client.agent_engines.memories.retrieve(...)` with `similarity_search_params={"search_query": query, "top_k": TOP_K}`.
6. Formats matching facts into a `<PAST_CONVERSATIONS>` block.
7. Calls `llm_request.append_instructions([block])` — the memory lands in the system prompt.

### Error handling
Wraps the retrieval and assembly in `try/except`. On any error: **fail silent, skip the injection, don't crash the turn.** Matches ADK's own preload pattern.

### Why it's a `BaseTool` and not a `FunctionTool`
`process_llm_request` is a hook that mutates the LLM request, not a model-invoked function. ADK's stock tool follows the same pattern. Consequence: **no tool-use event in the web UI trace** — invisible to the end user. See [06_GOTCHAS_AND_LIMITATIONS.md](06_GOTCHAS_AND_LIMITATIONS.md).

---

## The write path — `after_agent_callback`

**Problem it solves:** ADK does NOT auto-call `add_session_to_memory` at session end (verified by grep across the ADK package). There's no session-end hook. Writes must be triggered explicitly.

**Our fix:** an `after_agent_callback` that fires per turn, gated by a session-scoped turn counter.

### How it works

```python
EXTRACT_EVERY_N_TURNS = 2

async def persist_session_to_memory_callback(callback_context):
    state = callback_context.state              # delta-aware wrapper — critical
    turn = state.get("memory_turn_count", 0) + 1
    state["memory_turn_count"] = turn
    if turn % EXTRACT_EVERY_N_TURNS != 0:
        return
    ctx = callback_context._invocation_context
    if ctx.memory_service is None:
        return
    await ctx.memory_service.add_session_to_memory(ctx.session)
```

At turns 2, 4, 6, 8, … the callback fires `add_session_to_memory`, which internally calls `memories.generate()` with the full session content. Server-side Gemini does the extraction per our tuned topics + few-shots.

### The state-persistence trap
We initially mutated `ctx.session.state` (raw dict). Turn counter never persisted across turns → gate never tripped. Fix: mutate via `callback_context.state` — the delta-aware `State` wrapper. Only its writes get committed through the `state_delta` → `Event` → session-service flow.

### Cost/latency tradeoff
- Each gated write costs ~13-17s server-side + real $.
- Gate size of 2 means max 1 turn of tail loss if user walks away before an even turn.
- Consolidation (Test 6 finding) makes re-extraction safe — same facts across turns become `UPDATED` actions, not duplicates.

---

## `memory_config.json` — the knob

Single source of truth for retrieval-side settings:

```json
{
  "top_k": 10,
  "project_id": "ninth-potion-455712-g9",
  "location": "us-central1"
}
```

Read once at `preload_memory_topk.py` import time. To change `top_k` or other values: edit JSON, restart `adk web`.

Why a JSON file and not Python constants? Keeps the knob editable without needing to re-read the tool's Python code, and makes it obvious there IS a knob.

---

## How to start Jarvis with memory wired in

```
bash memory_bank_discovery/scripts/run_jarvis_web.sh
```

This script:
1. Sources `memory_bank_discovery/.env` → populates `AGENT_ENGINE_ID` in the environment.
2. Runs `adk web --memory_service_uri=agentengine://$AGENT_ENGINE_ID .`.
3. That CLI flag wires ADK's `VertexAiMemoryBankService` into the runner — required for the write-path callback (`add_session_to_memory`) to find a memory service.

**Do NOT start Jarvis via plain `adk web`** — the callback would fail to find `memory_service` and write-back would silently skip. Read-side would still work (our custom tool bypasses the runner's service), but the loop wouldn't close.

---

## Pre-seeding memories (for testing)

After a clean-up, Jarvis has nothing to retrieve. To seed a known memory for demo/testing:

```
python memory_bank_discovery/scripts/seed_jarvis_memory.py
```

Edit constants in that file to pick the scope and fact. Default writes `{"app_name": "jarvis_agent", "user_id": "user"}` — matches ADK web's bundled UI default, which hardcodes `userId="user"` in its JavaScript.

---

## What happens when the user chats

1. User types `"What OS is my workshop mainframe running?"`
2. Before LLM call: `PreloadMemoryTopK` runs → calls `memories.retrieve()` with that query → gets top 10 matching memories → injects them as `<PAST_CONVERSATIONS>`.
3. LLM sees the memories in its system prompt, generates a response using them.
4. After agent finishes: receipt callback logs tokens/cost, then `persist_session_to_memory_callback` bumps the turn counter. If turn % 2 == 0, extraction fires.
5. Next turn, same flow — memories may have been updated by the previous extraction.

---

## `agent.py` — current key excerpts

**Imports:**
```python
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import google_search
from jarvis_agent.preload_memory_topk import preload_memory_topk_tool
from utils.gcs_utils import fetch_instructions
from callbacks.receipt_callback import get_receipt_callback, get_start_time_callback
```

**Agent construction:**
```python
root_agent = Agent(
    name="jarvis_agent",
    model="gemini-2.5-flash",
    description="Jarvis agent",
    instruction=get_live_instructions,
    tools=[google_search, preload_memory_topk_tool],
    before_model_callback=get_start_time_callback(),
    after_model_callback=get_receipt_callback(...),
    after_agent_callback=persist_session_to_memory_callback,
)
```

Receipt callbacks untouched. `tools` swapped ADK's preload for ours.
