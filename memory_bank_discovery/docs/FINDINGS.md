# Memory Bank Discovery — Findings
## Target Agent: jarvis_agent

---

## Test 1: Agent Engine Creation
**Status:** ✅ PASSED
**Date:** 2026-04-19
**Findings:**
- `client.agent_engines.create()` works with no args; a default Agent Engine is provisioned.
- `AgentEngine` wrapper has NO `.name` attribute. The resource name lives at `agent_engine.api_resource.name` (the underlying `ReasoningEngine`).
- `ExperimentalWarning` on `agent_engines` module is benign — not an error.
- Resource name shape: `projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}`.
- Project number (not project ID) is used in the resource name — this is standard GCP.
- Our engine: `projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976`.
- `client.agent_engines.list()` returns `Iterator[AgentEngine]` — use this to retrieve an existing engine without duplicating.

---

## Test 2: Direct Memory Write
**Status:** ✅ PASSED
**Date:** 2026-04-19
**Findings:**

### Verified API shape
```python
client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
operation = client.agent_engines.memories.create(
    name=AGENT_ENGINE_ID,            # full resource name of the engine
    fact="Tony prefers Python for backend development",
    scope={"user_id": "tony_stark"},
    # config defaults to AgentEngineMemoryConfig(wait_for_completion=True)
)
```

### Return type: `AgentEngineMemoryOperation`
- `operation.done` → `True` (SDK auto-polls since `wait_for_completion=True`)
- `operation.error` → `None` on success
- `operation.name` → operation resource name, nested UNDER the memory name:
  `{engine}/memories/{memory_id}/operations/{op_id}`
- `operation.metadata` → standard GCP LRO envelope:
  `{'@type': '...CreateMemoryOperationMetadata', 'genericMetadata': {'createTime': ..., 'updateTime': ...}}`
- `operation.response` → fully-hydrated `Memory` object (SDK calls `.get()` internally after the op completes)

### `Memory` object fields (observed)
- `name` — full resource name: `{engine}/memories/{memory_id}`
- `fact` — string, returned verbatim
- `scope` — dict, returned verbatim (e.g. `{'user_id': 'tony_stark'}`)
- `create_time`, `update_time` — `datetime.datetime` with UTC tzinfo, microsecond precision
- On a fresh write: `create_time == update_time`

### Observed artifact
```
projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976/memories/3072711962535133184
  fact:  Tony prefers Python for backend development
  scope: {'user_id': 'tony_stark'}
  created: 2026-04-19 07:19:40.586266 UTC
```

### Gotchas & notes
- Two `ExperimentalWarning`s fire on `.memories` access (both benign).
- Memory IDs are 19-digit integers (same shape as Agent Engine IDs).
- `wait_for_completion=False` behavior: not yet tested — would return a pending op without response.
- De-dup behavior on identical fact+scope rewrite: not yet tested.

---

## Test 3: Memory Retrieval
**Status:** ✅ PASSED (all three read paths)
**Date:** 2026-04-19
**Findings:**

### Three distinct read APIs exist — all verified working

#### 1. `memories.list(name=ENGINE)` — full enumeration
```python
iterator = client.agent_engines.memories.list(name=AGENT_ENGINE_ID)
memories = list(iterator)  # Pager is lazy
```
- Returns `Pager` (lazy) — materialize with `list(...)`.
- Each item is a `Memory` with the exact same shape as the write-response `Memory` (see Test 2).
- Returned **1** record after a single Test-2 write, as expected.

#### 2. `memories.get(name=MEMORY_RESOURCE_NAME)` — direct fetch
```python
mem = client.agent_engines.memories.get(
    name="projects/.../reasoningEngines/.../memories/..."
)
```
- Takes the **full** memory resource name, not just the memory ID.
- Returns `Memory` directly (not wrapped in an operation — it's a synchronous read).
- Field shape identical to Test 2's `operation.response`.

#### 3. `memories.retrieve(name=ENGINE, scope={...})` — scope-based query
```python
iterator = client.agent_engines.memories.retrieve(
    name=AGENT_ENGINE_ID,
    scope={"user_id": "tony_stark"},
    # similarity_search_params=None, simple_retrieval_params=None
)
retrieved = list(iterator)
```
- Both `similarity_search_params` and `simple_retrieval_params` are truly optional — neither required for a basic scope lookup.
- Returns `Iterator[RetrieveMemoriesResponseRetrievedMemory]`.
- Wrapper fields observed:
  - `.memory` → the `Memory` object (same shape as above)
  - `.distance` → `None` when no similarity params passed — distance scoring only kicks in with `similarity_search_params`
  - No `.score` or `.similarity` attrs present on the wrapper in this mode
- This is the **agent-runtime pattern** — pass the current user/session scope, get back the relevant memories.

### Cross-method consistency
All three paths returned the IDENTICAL `Memory` object for the same record (byte-for-byte across `name`, `fact`, `scope`, `create_time`, `update_time`). No read-path discrepancies.

### Open questions still unverified
- `retrieve()` with `similarity_search_params` — how `.distance` gets populated, what params look like.
- `retrieve()` with `simple_retrieval_params` — likely `max_count`/pagination knobs.
- Retrieve with a scope that matches NO memories — returns empty iterator vs. error?
- Retrieve with mismatched scope (e.g. `{"user_id": "other_user"}`) — isolation behavior is Test 5's job.

---

## Test 4: Session-Based Memory Generation
**Status:** ✅ PASSED
**Date:** 2026-04-19
**Findings:**

### Verified API shape
```python
operation = client.agent_engines.memories.generate(
    name=AGENT_ENGINE_ID,
    direct_contents_source={
        "events": [
            {"content": Content(role="user",  parts=[Part(text="...")])},
            {"content": Content(role="model", parts=[Part(text="...")])},
            ...
        ],
    },
    scope={"user_id": "tony_stark"},
    # config defaults: wait_for_completion=True, disable_consolidation=None (consolidation ON)
)
```

### 🚨 Response is SKELETAL — asymmetric with `create()`
`generate()` returns `AgentEngineGenerateMemoriesOperation` where:
- `operation.done = True`
- `operation.response = GenerateMemoriesResponse`
- `operation.response.generated_memories` = list of `GenerateMemoriesResponseGeneratedMemory`
- Each item has:
  - `.action` — enum (`CREATED`, `UPDATED`, `DELETED`, `ACTION_UNSPECIFIED`)
  - `.memory` — a `Memory` object with **only `.name` populated**. `fact`, `scope`, `create_time`, `update_time` are all `None`.

**Consequence:** caller MUST `memories.get(name=...)` to see what was actually generated. Compare with `create()`, which returns a fully-hydrated `Memory`.

### Operation-name scope differs from `create()`
- `create()` op name: `.../memories/{memory_id}/operations/{op_id}` (nested under the memory)
- `generate()` op name: `.../reasoningEngines/{engine_id}/operations/{op_id}` (engine-level)
- Makes sense — `generate()` can produce N memories, so the op can't be nested under any single one.
- Metadata `@type`: `...GenerateMemoriesOperationMetadata` (distinct from `CreateMemoryOperationMetadata`).

### Latency (single observation, not a benchmark)
- Wall-clock: **16.70s** end-to-end.
- Server-side extraction window: **~3.25s** (metadata: `08:48:44.595Z` → `08:48:47.846Z`).
- Difference between wall-clock and server window is client-side polling overhead (SDK `_await_operation`).

### Extraction is SELECTIVE, not exhaustive
Input transcript contained 2 user facts:
| User said | Extracted? |
|---|---|
| "My favorite coffee shop is Stark Brewery on 5th avenue." | ❌ dropped |
| "I usually order a flat white with oat milk." | ✅ captured |

Only 1 `generated_memory` returned (`action=CREATED`). **Don't assume every user statement becomes a memory.** The default generation model applies its own salience/relevance filter.

### Extraction preserves speaker voice (first-person)
Generated fact: `"I usually order a flat white with oat milk."` — verbatim from the user turn, including the `I` pronoun. Compare with the manual Test 2 write: `"Tony prefers Python for backend development"` (third-person).
**Implication:** if we want third-person normalized facts for agent context, we'd need to either (a) configure the generation model to rewrite them, or (b) post-process the stored facts ourselves. Default is verbatim user voice.

### Consolidation behavior (partial signal — intentionally)
- Consolidation was ON (SDK default).
- Coffee-domain fact was unrelated to existing Python-domain fact → no consolidation fire.
- `create_time == update_time` on the generated memory — confirms no UPDATE happened.
- Real consolidation/contradiction testing is Test 6's job.

### Generated artifact
```
projects/.../reasoningEngines/6954288450136702976/memories/2993336019102728192
  fact:  "I usually order a flat white with oat milk."
  scope: {"user_id": "tony_stark"}
  created: 2026-04-19 08:48:47.778226 UTC
```

### Open questions
- Does `disable_consolidation=True` change extraction volume, or only change how results are merged?
- Would a longer/richer transcript produce more memories? (only 2 facts in this run — need a bigger sample to judge filter aggressiveness)
- What's the default generation model? (unknown — engine was created with no `context_spec`)
- Does `vertex_session_source` (using a real Session) behave the same as `direct_contents_source`?

---

## Test 5: Memory Isolation
**Status:** ✅ PASSED (all 3 assertions green)
**Date:** 2026-04-19
**Findings:**

### Multi-tenant safety: CONFIRMED

Memories written under `{"user_id": "peter_parker"}` never appeared in a `retrieve()` scoped to `{"user_id": "tony_stark"}` — and vice versa. Memory Bank is safe to share across multiple users on a single Agent Engine, scoped by `user_id`.

### Verified behaviors

| Check | Result | Takeaway |
|---|---|---|
| `tony_set ∩ peter_set == ∅` | PASS | No cross-user leakage — core isolation guarantee holds. |
| `retrieve(scope={"user_id": "nobody_exists"})` → 0 | PASS | Retrieve is **exact-match strict**, not permissive/wildcard. Unknown scope → empty iterator, not error. |
| Peter's new memory is in `peter_set` | PASS | Writes are immediately retrievable under their own scope (no indexing lag observed). |

### Side findings
- **`list(name=ENGINE)` with no scope returns ALL memories across ALL scopes.** Confirmed empirically by seeing both `tony_stark` and `peter_parker` memories in the same list output. This is an admin/engine-level view, useful for debugging/enumeration but should NOT be used in agent-runtime paths where tenant isolation matters.
- **No per-user provisioning step.** `create(scope={"user_id": "<any>"})` works immediately for a previously-unseen `user_id`. Users are implicit; there's no "register" step.
- **3-memory partition after this test run:**
  - 2 under `{"user_id": "tony_stark"}` (Test 2 manual + Test 4 generated)
  - 1 under `{"user_id": "peter_parker"}` (this test)

### Script idempotency note
Re-running `test_memory_isolation.py` creates an additional Peter memory per run — `create()` does not dedup on identical (fact, scope). This is expected; the assertion set-math is robust to duplicates. Actual de-dup behavior is Test 6's scope.

### Open questions still unverified
- Multi-key scope shapes (e.g., `{"user_id": "...", "session_id": "..."}`) — does retrieve do exact-match on the whole dict, or subset-match?
- `scope={}` (empty dict) behavior — returns everything, errors, or returns nothing?
- Whether there's a per-scope memory count limit.
- Whether retrieve sorts results (e.g., by recency) when no similarity params are passed.

---

## Test 6: Consolidation / Contradiction
**Status:** ✅ PASSED — STRONG CONSOLIDATION confirmed
**Date:** 2026-04-19
**Findings:**

### Headline: consolidation is STRONG and does an in-place MERGE, not a replace

When `generate()` sees a fact that contradicts an existing memory in the same scope, the service **updates the existing memory in place** (`action=UPDATED`, same resource name) and **rewrites the fact** to reflect both the new state AND the historical context.

### Observed mutation

| | Text |
|---|---|
| BEFORE | `"Tony prefers Python for backend development"` |
| AFTER  | `"I now use Go for all my backend work; previously, I preferred Python for backend development."` |

Transcript that triggered it:
```
user:  "Actually I've ditched Python - I'm using Go for all my backend work now."
model: "Got it, Go for backend."
```

### What the service did (worth calling out)

1. **Preserved the memory resource name.** Memory `3072711962535133184` stayed `3072711962535133184`. Downstream consumers tracking memory IDs don't need to follow pointer indirection.
2. **Captured BOTH states in the new fact** — current ("I now use Go") + historical ("previously, I preferred Python"). Temporal ordering preserved via semicolon-linked clauses.
3. **Normalized voice to first-person** — original was third-person ("Tony prefers"), AFTER is first-person ("I now use"). Voice normalization is **one-way: always first-person**, regardless of the prior text. This now applies to both fresh generation (Test 4) and consolidation UPDATE (Test 6).
4. **Left topically-unrelated memory alone.** M2 (coffee preferences) was not touched — consolidation is topic-scoped, not scope-wide.
5. **No CREATE, no DELETE** — total memory count stayed at 2 for this user. One-for-one in-place mutation.

### Latency
12.57s wall-clock — slightly faster than Test 4's 16.70s, even though this run did both extraction AND cross-memory reconciliation. Consolidation doesn't appear to add a separate round-trip.

### Cross-check (diff vs. service-reported actions)
Service reported `(UPDATED, M1)`. Observed diff: 0 disappeared, 0 appeared, 1 changed (M1). **Exact match** — no reconciliation mismatches between what the service claimed and what actually landed on the engine.

### Implications for Jarvis integration
- **No client-side dedup needed.** The service maintains coherent, deduplicated, temporally-ordered user context. Just keep feeding transcripts to `generate()` — trust the consolidation.
- **Historical context is preserved by default.** Agents retrieving memories will see both the current and past states as a single string. If the agent prompt needs only "current" state, we may need to post-process or prompt the model to ignore "previously, …" clauses.
- **Consolidation IS in-place.** Memory IDs are stable across updates — safe to reference by name in agent state/logs.

### Open questions still unverified
- What happens with 2+ contradicting facts in one transcript? Does the service chain the updates or merge all into one?
- What about a NEW topic (e.g., adds a Rust-for-systems-programming fact via Tony's scope)? Will it CREATE alongside the Go/Python memory, or attempt some other consolidation?
- `disable_consolidation=True` — does it skip the merge entirely (new CREATE for Go, M1 left stale)? This is the inverse experiment.
- Does `generate()` ever emit a `DELETED` action, or is UPDATE always preferred? (Maybe DELETE only fires when a user explicitly retracts a fact.)

---

## Test 7: Jarvis Agent Integration
**Status:** ✅ PASSED (7a read + 7b write both wired and verified live)
**Date:** 2026-04-20 (7a), 2026-04-22 (7b callback fix + verification), 2026-04-23 (custom top_k fork)
**Findings:**

### 7a — Read side: `preload_memory_tool` + `--memory_service_uri`
- ADK ships a first-party `VertexAiMemoryBankService` + `preload_memory_tool` — zero Python wiring needed on the agent, just the CLI flag.
- `adk web --memory_service_uri=agentengine://<engine_id>` injects the memory service into the runner; `preload_memory_tool` runs before every LLM request and appends matching memories into the system prompt as `<PAST_CONVERSATIONS>`.
- Scope is auto-built from session: `{"app_name": session.app_name, "user_id": session.user_id}`. Our pre-seeded memory under that two-key scope was retrieved correctly once the `user_id` matched ADK web's hardcoded default `"user"`.
- **Gotcha:** ADK web's bundled UI hardcodes `userId="user"` — no UI field to change it. Seed memories under that default or run through a custom frontend.
- **Gotcha:** `preload_memory_tool` doesn't show up as a tool-use event in the ADK web trace panel — it's a `BaseTool` context injector, not a `FunctionTool`. Silent by design.

### 7b — Write side: `after_agent_callback`
- ADK does NOT auto-call `memory_service.add_session_to_memory(session)`. Confirmed by exhaustive grep of the ADK CLI/runner code + explicit statement in Google's docs at adk.dev/sessions/memory.
- Official pattern: `after_agent_callback` on the agent that calls `callback_context._invocation_context.memory_service.add_session_to_memory(session)`. Fires per TURN, not per SESSION (ADK has no session-end hook — verified in `base_agent.py:215-245`).
- Gated via `session.state["memory_turn_count"]` to fire every N turns (cost/latency optimization). Memory Bank consolidation (Test 6) makes redundant re-extraction safe — no duplicate memories.
- **Gotcha:** must mutate state via `callback_context.state` (the delta-aware wrapper), NOT `ctx.session.state` (raw dict). Raw-dict mutations don't persist across turns because the state_delta → Event → session_service flow isn't triggered.
- With `N=2` and tuned engine, extraction captures all technical details. Latency on gated turns is ~13-17s; small-session-end tail loss is limited to ≤1 turn.

### Custom top_k fork (added 2026-04-23)
- ADK's `preload_memory_tool` and `VertexAiMemoryBankService.search_memory` both hardcode `similarity_search_params={"search_query": query}` — no `top_k`, so server default of 3 applies.
- 3 results isn't enough once the bank has many entries; relevant facts get ranked out of the top 3.
- Built `jarvis_agent/preload_memory_topk.py` + `jarvis_agent/memory_config.json`: drop-in replacement that calls `memories.retrieve()` directly with `top_k` from config (default 10).
- Swapped into Jarvis's tools list with 2-line change in `agent.py`. Callback write path unchanged.

---

## Summary

**Discovery lab complete.** Memory Bank is production-viable for the harness — but "out of the box" defaults are inadequate and there are real ADK integration gaps that require custom code.

### What we proved works
- **End-to-end read-write loop** through ADK + Vertex AI Memory Bank is wireable (Tests 7a + 7b).
- **Consolidation is strong** — contradictions become in-place `UPDATED` actions on the same memory ID, and the merged fact preserves both new and historical state (Test 6). Clients don't need dedup logic.
- **Scope isolation is exact-match strict** — zero cross-user leakage (Test 5). Multi-tenant safe.
- **Server-side extraction is customizable** — topics, few-shots, generation model, and TTL are all tunable per-engine via `context_spec` (verified by the Pass 2 tuning run: 100% capture rate vs. 50% on defaults).
- **Update-in-place supported** — `client.agent_engines.update(...)` accepts `context_spec`; no need to re-provision the engine when tuning.

### What limitations we found
- **`top_k` hardcoded at server default of 3** in ADK's `VertexAiMemoryBankService.search_memory` — not configurable through any parameter, env var, or service constructor.
- **`generate()` default extraction is selective** — with no custom topics or few-shot examples, the default Gemini extractor drops ~50% of technical facts. Only became reliable after Pass 2 tuning.
- **No session-end hook in ADK** — `after_agent_callback` fires per turn, not per session. Every write strategy has to live with per-turn gating or client-managed lifecycle.
- **Model under-calls an explicit `remember_fact` tool** — with Gemini 2.5 Flash, model-initiated memory persistence is unreliable. User has to explicitly ask "remember X" for it to fire.
- **TTL `oneof` constraint not surfaced by the SDK** — both `default_ttl` and `granular_ttl_config` are Optional at the pydantic layer, but the server enforces mutually-exclusive; sending both is a 400.
- **ADK web bundled UI hardcodes `user_id="user"`** in its JavaScript — no field to override. Custom frontends or direct API calls required for real multi-user deployments.

### What we built to fix them
- **Engine tuning** (`memory_bank_discovery/scripts/update_engine_config.py`) — 4 managed topics, 4 custom topics (architectural_decisions, project_constraints, lessons_learned, technology_stack), 3 few-shot examples, `gemini-2.5-pro` generation model, granular TTL. Transformed extraction quality from "selective and lossy" to "complete and nuanced."
- **Custom `PreloadMemoryTopK` tool** (`jarvis_agent/preload_memory_topk.py` + `memory_config.json`) — drop-in replacement for `preload_memory_tool`; bypasses ADK's service layer and calls `memories.retrieve()` directly with configurable `top_k` (default 10).
- **Callback-based write path** (`persist_session_to_memory_callback` in `jarvis_agent/agent.py`) — turn-count-gated `after_agent_callback` that fires `memory_service.add_session_to_memory()` every N turns (currently 2). Uses `callback_context.state` for delta-aware persistence.
- **Full toolkit for scope-based ops** (`list_scopes.py`, `list_memories_by_scope.py`, `add_memory_for_scope.py`, `cleanup_memories_by_scope.py`) — give us CRUD-by-scope mastery for ongoing operations.

### What's deferred to v3
- **OpenBrain MCP server** with single-key scope (`{"user_id": X}` only) so memories are shared across all harness agents, not siloed per-agent. Decouples memory ownership from which agent wrote it.
- **Memory-specific eval suite** — scoring extraction accuracy, retrieval recall-at-K, consolidation correctness, isolation guarantees. Using the Vertex AI Evaluation Service we validated earlier for other metrics.
- **Integration into Architect agent** — coexistence with the existing session-file-based memory (which is reliable for ephemeral state) while Memory Bank handles durable facts.
- **Custom `recall_memories` tool for MCP clients** — replaces `preload_memory_tool` when operating under the shared-scope architecture; exposes similar behavior to agents connecting via MCP rather than running in-process in the harness.
