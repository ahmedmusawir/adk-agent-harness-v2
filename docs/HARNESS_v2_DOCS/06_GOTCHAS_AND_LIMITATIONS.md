# 06 — Gotchas and Limitations

**ADK Agent Harness v2**

Real issues we hit during v2. Check here first when something behaves unexpectedly.

---

## SDK / API gotchas

### 1. `AgentEngine` has no `.name` attribute
The Python object returned by `client.agent_engines.create()` / `.get()` is a wrapper. The actual GCP resource (a `ReasoningEngine`) hangs off it. Resource name lives at `.api_resource.name`.

```python
# Wrong — AttributeError
engine.name

# Right
engine.api_resource.name
```

The SDK's own `__repr__` on `AgentEngine` uses `.api_resource.name`. Took us one crashed setup script to spot this.

### 2. Resource names use project NUMBER, not project ID
```
projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976
```

`952978338090` is the project NUMBER corresponding to project ID `ninth-potion-455712-g9`. GCP's fully-qualified resource name format uses the number. You paste the whole string into `.env` verbatim — every slash, every digit.

### 3. `generate()` returns a SKELETAL `Memory`
`memories.create()` returns a fully-hydrated `Memory` (name, fact, scope, timestamps all populated).

`memories.generate()` returns a `Memory` with ONLY the `name` populated — `fact`, `scope`, `create_time`, `update_time` are all `None`.

To see what was extracted, you must call `memories.get(name=...)` afterward. Asymmetric; easy to miss.

### 4. TTL config is a protobuf `oneof`
The `TtlConfig` pydantic class exposes BOTH `default_ttl` and `granular_ttl_config` as independently-Optional fields. **Server treats them as mutually exclusive** — sending both returns a 400:

```
INVALID_ARGUMENT: Invalid value at 'reasoning_engine.context_spec.memory_bank_config.ttl_config'
(oneof), oneof field 'ttl' is already set. Cannot set 'granular_ttl_config'
```

Pick ONE. We use `granular_ttl_config` alone because it covers every write path (`create`, `generate_created`, `generate_updated`).

### 5. Generation model string has no client-side validation
Format per the SDK docstring: `projects/{p}/locations/{l}/publishers/google/models/{model}`.

No enum, no allowlist, no regex. A typo (e.g., `gemini-2.5-prr`) passes client validation and fails at first `generate()` with a 400. Test extraction immediately after updating model config.

### 6. `ExperimentalWarning` on `agent_engines.memories.*` is benign
Fires on every `memories.create()`, `.retrieve()`, `.generate()`, etc. It's noise from the SDK calling itself experimental. Not an error. Don't filter it — the SDK may promote features out of experimental later and we want to know.

---

## ADK integration gotchas

### 7. `top_k` for retrieval is hardcoded to server default (3) in ADK
`VertexAiMemoryBankService.search_memory` constructs `similarity_search_params={"search_query": query}` inline — no `top_k`, no config, no subclass hook. Server defaults to 3.

Three isn't enough once the bank has many entries. ADK's stock `preload_memory_tool` is therefore inadequate for any real bank.

**Fix:** fork the tool. `jarvis_agent/preload_memory_topk.py` bypasses ADK's service layer and calls `memories.retrieve()` directly. Config in `jarvis_agent/memory_config.json`. See [04_JARVIS_MEMORY_INTEGRATION.md](04_JARVIS_MEMORY_INTEGRATION.md).

### 8. No session-end hook in ADK
`after_agent_callback` fires **per turn**, not per session. Confirmed by reading `google/adk/agents/base_agent.py:215-245` — the callback runs at the end of each `agent.run_async(ctx)` call, which happens once per user turn.

Grep across the whole ADK package for `on_session_end`, `session_close`, `after_session`: **zero hits.** There's no session-end surface.

Consequence: write lifecycle is "every turn + gate" or "on explicit trigger." We chose the gate (see `EXTRACT_EVERY_N_TURNS` in `jarvis_agent/agent.py`). Google's docs acknowledge this explicitly.

### 9. ADK does NOT auto-call `add_session_to_memory`
grep ADK's entire codebase for `add_session_to_memory` callers: ZERO hits. The service is wired into the runner; it's never invoked. Writes must be explicitly triggered by the developer.

Google's ADK docs confirm: *"ADK does not automatically call add_session_to_memory at session end… you can automate this via a callback."*

### 10. `session.state` must be mutated via `callback_context.state`, not the raw dict
Looks like this works but doesn't:

```python
ctx = callback_context._invocation_context
state = ctx.session.state                 # raw dict
state["turn_count"] = 1                   # mutation LOST across turns
```

Fix: use the delta-aware wrapper:

```python
state = callback_context.state             # State wrapper
state["turn_count"] = 1                    # persists via state_delta → Event → session_service
```

The `State` wrapper records changes in a `state_delta`, which ADK emits as an Event, which the session service commits to storage. Raw-dict writes bypass all of that and get lost when the session service reloads the session next turn.

Cost us two wasted 8-turn test sessions. Now documented.

### 11. `preload_memory_tool` does NOT appear in the ADK web trace panel
Because `PreloadMemoryTool` is a `BaseTool` that only overrides `process_llm_request` — it never declares a `FunctionDeclaration` to the model. The model never "calls" it; it just silently mutates the LLM request. No tool-use event to log.

Our `PreloadMemoryTopK` follows the same pattern → same (in)visibility. That's by design. If you need visible memory events in the trace, use a `FunctionTool`-based `load_memory` pattern (model-invoked) instead. We tried the explicit-tool approach (`remember_fact`); model under-called it, leading us back to the callback-based write path.

### 12. ADK web UI hardcodes `userId="user"` in its bundled JavaScript
There's NO UI field in `adk web` to set a real user_id. The bundled frontend ships with `userId="user"` as a string literal in `main-*.js`.

Consequence: our initial seed under `user_id="tony_stark"` was invisible to Jarvis running through the web UI. Switched the seed to `user_id="user"` to match. For real multi-user deployments, you need a custom frontend or direct API calls.

---

## Behavior gotchas

### 13. Default extraction is selective — misses technical details
With a fresh engine (no `context_spec`), Memory Bank's server-side extractor drops ~50% of technical facts. We saw it silently drop "Stark Brewery on 5th Avenue" while keeping "flat white with oat milk" from the same transcript.

**Fix:** tune the engine. Custom topics + few-shot examples push capture rate to 100% on technical content. See [03_ENGINE_TUNING.md](03_ENGINE_TUNING.md) + `memory_bank_discovery/docs/ENGINE_TUNING_INSPECTION.md`.

### 14. Generated facts are always first-person, verbatim from user voice
The extractor preserves the user's phrasing and pronouns. So memories look like:
```
"I have two children named Nihad and Nimat."
```
NOT:
```
"Tony has two children named Nihad and Nimat."
```

Manual writes via `memories.create()` store whatever text you pass, verbatim. If you want third-person form for consistency, you're normalizing client-side.

### 15. Model under-calls explicit `remember_fact`-style tools
We built a `FunctionTool` called `remember_fact(fact: str)` and told Gemini 2.5 Flash via system instructions to call it "when the user states a preference, constraint, or asks you to remember something."

Model used it maybe 20% of the time in practice. For unprompted ambient memory capture, tools are unreliable. The callback-based write path is the fallback that works.

### 16. Per-turn gated writes have a tail-loss window
With `EXTRACT_EVERY_N_TURNS = 2`, turns 1, 3, 5, 7… don't trigger extraction. If the user walks away after turn 7, turn 7's content never makes it to Memory Bank. Worst case: N-1 turns lost.

Smaller N = less tail loss but more cost (extraction fires more often). We picked N=2 as a balance.

### 17. Consolidation merges but doesn't always shorten
When a new fact contradicts an old one, the service rewrites to capture both states:
```
BEFORE: "Tony prefers Python for backend development"
AFTER:  "I now use Go for all my backend work; previously, I preferred Python for backend development."
```

The merged fact preserves history — good for context, but memory length grows over time. Not a bug; a design choice worth knowing.

---

## Where to go when you hit a new gotcha

1. Check this file first.
2. If it's an SDK-level question, grep the installed SDK: `.venv/lib/python3.12/site-packages/vertexai/_genai/types.py` has every config class with docstrings.
3. If it's an ADK integration question, grep `.venv/lib/python3.12/site-packages/google/adk/`.
4. Google's docs at [adk.dev/sessions/memory](https://adk.dev/sessions/memory/) are authoritative for ADK memory patterns.
5. Google's docs at `cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/` are authoritative for Memory Bank features.
6. Our own `memory_bank_discovery/docs/FINDINGS.md` has per-test verified behavior for the 7 tests we ran.
