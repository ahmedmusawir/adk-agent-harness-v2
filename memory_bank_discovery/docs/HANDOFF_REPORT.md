# Memory Bank Discovery — Handoff Report

**Project:** ADK Agent Harness v2 (current phase)
**Lab dates:** 2026-04-19 through 2026-04-23
**Status:** Complete. Read-write loop through Vertex AI Memory Bank is live in the Jarvis agent, engine is tuned, custom top_k fork is in place.

---

## What Was Built

### New Python scripts — `memory_bank_discovery/scripts/`

| File | Purpose |
|---|---|
| `test_write_memory.py` | Test 2 — direct `memories.create()` with `{"user_id": "tony_stark"}` scope |
| `test_read_memory.py` | Test 3 — exercises `list` / `get` / `retrieve` in one run |
| `test_generate_memories.py` | Test 4 — session-based extraction via `memories.generate()` + `direct_contents_source` |
| `test_memory_isolation.py` | Test 5 — multi-tenant scope isolation assertions (A1/A2/A3) |
| `test_consolidation.py` | Test 6 — BEFORE/GENERATE/AFTER/DIFF script proving in-place UPDATE on contradictions |
| `seed_jarvis_memory.py` | Test 7a — one-off pre-seed of a Jarvis-scoped memory |
| `run_jarvis_web.sh` | Test 7a — shell launcher for `adk web --memory_service_uri=agentengine://<id>` |
| `list_scopes.py` | Toolkit — enumerate unique scope dicts with memory counts (closest thing to "list users") |
| `list_memories_by_scope.py` | Toolkit — print every memory matching `TARGET_SCOPE` (exact-match) |
| `add_memory_for_scope.py` | Toolkit — write a fact to an arbitrary scope; implicitly "creates" a user on first write |
| `cleanup_memories_by_scope.py` | Toolkit — DRY_RUN-gated bulk delete by exact scope match |
| `inspect_engine_config.py` | Pass 1 — read-only dump of the engine's full `context_spec` tree |
| `update_engine_config.py` | Pass 2 — applies tuned `context_spec`: custom topics, few-shots, model, granular TTL |
| `test_tuned_generate.py` | Pass 2 — 6-turn content-coverage audit validating post-tuning extraction quality |

### New Python scripts — `memory_bank_discovery/` (root)

| File | Purpose |
|---|---|
| `setup_agent_engine.py` | One-time Agent Engine provisioning (fixed after `.name` bug) |
| `list_agent_engines.py` | Recovery helper — list existing engines without duplicating |

### Jarvis integration — `jarvis_agent/`

| File | Purpose |
|---|---|
| `preload_memory_topk.py` | **Custom read tool.** Drop-in replacement for ADK's `preload_memory_tool` — calls `memories.retrieve()` directly with `top_k` from config. Fixes the hardcoded-3 ceiling. |
| `memory_config.json` | Single control file for retrieval settings: `top_k`, `project_id`, `location`. Read once at import. |
| `agent.py` | Modified: imports/uses `preload_memory_topk_tool`; `after_agent_callback` fires `persist_session_to_memory_callback` every `EXTRACT_EVERY_N_TURNS` turns. |

### Documentation — `memory_bank_discovery/docs/`

| File | Purpose |
|---|---|
| `DISCOVERY_BRIEF.md` | Scratchpad stub from the start of the lab. |
| `FINDINGS.md` | Per-test findings (Tests 1-7) + final Summary section. Load-bearing reference. |
| `ENGINE_TUNING_INSPECTION.md` | Pass 1 inspection + Pass 2 tuning results. SDK source citations. |
| `HANDOFF_REPORT.md` | This file. |

### Documentation — `docs/` (repo-root)

| File | Purpose |
|---|---|
| `VERTEX_MEM_BANK_TEST_FOR_YOUTUBE.md` | Narrative walk-through covering every test in order, with verbatim commands. Future-self reference and YouTube script. |

### Other configuration

| File | Purpose |
|---|---|
| `memory_bank_discovery/.env` | `GCP_PROJECT_ID`, `GCP_REGION`, `AGENT_ENGINE_ID`. Gitignored by root `.gitignore`. |

---

## Current Architecture

- **Read side — custom `PreloadMemoryTopK` tool** (`top_k=10`, configurable via `jarvis_agent/memory_config.json`):
  - Runs silently before every LLM request.
  - Calls `client.agent_engines.memories.retrieve()` directly, bypassing ADK's `VertexAiMemoryBankService.search_memory` (which hardcodes top_k to the server default of 3).
  - Injects matching memories as `<PAST_CONVERSATIONS>` into the system prompt.
  - Scope auto-derived from session: `{"app_name": session.app_name, "user_id": session.user_id}`.

- **Write side — `after_agent_callback` with turn-count gate**:
  - Fires `memory_service.add_session_to_memory(session)` every `EXTRACT_EVERY_N_TURNS` turns (currently 2).
  - Uses `callback_context.state` (delta-aware) for the turn counter — critical; raw-dict mutation doesn't persist.
  - Gate is a cost optimization, not a correctness guarantee — Memory Bank's in-place consolidation makes re-extraction across turns safe.

- **Engine — tuned `context_spec`**:
  - **Generation model:** `projects/ninth-potion-455712-g9/locations/us-central1/publishers/google/models/gemini-2.5-pro`
  - **4 managed topics:** `USER_PERSONAL_INFO`, `USER_PREFERENCES`, `KEY_CONVERSATION_DETAILS`, `EXPLICIT_INSTRUCTIONS`
  - **4 custom topics:** `architectural_decisions`, `project_constraints`, `lessons_learned`, `technology_stack`
  - **3 few-shot examples** showing desired extraction depth (Vercel/HIPAA hosting decision; ADK eval finding; code conventions).
  - **Granular TTL:** `create_ttl=1y`, `generate_created_ttl=30d`, `generate_updated_ttl=90d`. (Note: TTL is a protobuf `oneof` — cannot combine `default_ttl` with `granular_ttl_config`. Granular alone covers every write path.)

---

## Key Findings

1. **`AgentEngine` is a wrapper, not the resource.** Resource name lives at `.api_resource.name`, not `.name`.
2. **`memories.create()` returns a hydrated `Memory`** (full fields populated). **`memories.generate()` returns a SKELETAL `Memory`** (name-only) — caller must `get(name=...)` to see the extracted fact.
3. **Default extraction is selective.** Without tuning, ~50% of technical facts dropped. With tuning (custom topics + few-shots), capture rate → 100% on representative conversations.
4. **Consolidation is STRONG and IN-PLACE.** Contradictions become `UPDATED` actions on the same memory ID; merged fact preserves historical context in first-person voice ("I now use Go; previously, I preferred Python").
5. **Scope isolation is exact-match strict.** Retrieve under one `user_id` never returns memories written under a different `user_id`. Unknown scope → empty iterator, not wildcard.
6. **`top_k` on retrieve defaults to 3** server-side. ADK's service layer doesn't pass it. Fixable only via fork.
7. **ADK has no session-end hook.** `after_agent_callback` fires per turn. All write strategies gate by turn count or rely on explicit user trigger.
8. **Model under-calls explicit `remember_fact` tool.** Gemini 2.5 Flash treats ambient persistence tools as optional; unreliable for unprompted capture. Callback is more reliable.
9. **Engine can be updated in place.** `client.agent_engines.update(...)` accepts `context_spec` — no re-provisioning required when tuning.
10. **`ExperimentalWarning` on `agent_engines.memories.*` is benign.** Fires on every call; ignore.

---

## Known Limitations

- `preload_memory_tool` from ADK cannot be configured for `top_k`; fork required (done, in `preload_memory_topk.py`).
- `VertexAiMemoryBankService.search_memory` doesn't expose `top_k`; same fix path.
- `adk web` UI hardcodes `userId="user"` in its JavaScript bundle. No UI field to change it; custom frontend or direct API calls required for real multi-user testing.
- ADK does not auto-call `add_session_to_memory` at session end (there is no session-end hook). Write lifecycle must be wired by the dev.
- Per-turn gated writes trade tail loss (≤N turns lost if session ends mid-window) against cost (extraction runs every N turns).
- TTL `oneof` constraint not surfaced client-side by the SDK — sending both `default_ttl` and `granular_ttl_config` returns 400.
- Generation model string has no client-side validation; typos fail at first `generate()` call.
- Default embedding model (`text-embedding-005`) not changed; multilingual scenarios untested.

---

## Deferred to v3

- **OpenBrain MCP server** with single-key scope (`{"user_id": X}` only). Shared memory across every harness agent, not siloed per-agent. Architect writes, Jarvis reads — same user, same memory.
- **Memory-specific eval suite.** Extraction accuracy, retrieval recall-at-K, consolidation correctness, isolation verification. Built on the Vertex AI Evaluation Service pattern we validated earlier.
- **Integration into Architect agent.** Coexistence with the session-file-based memory that Architect already uses reliably; Memory Bank for durable facts, session file for ephemeral state.
- **Custom `recall_memories` tool for MCP clients.** Replaces `preload_memory_tool` when operating under shared-scope architecture; exposes equivalent behavior to agents connecting via MCP rather than running in-process.
- **Similarity-search tuning knobs.** Explore `simple_retrieval_params` (pagination, page_size) for non-semantic enumeration; experiment with alternative embedding models.
- **`disable_consolidation=True` exploration.** Unverified how skipping the merge step affects memory growth and retrieval noise.

---

## How to Run

### Start Jarvis with Memory Bank wired in
```
bash memory_bank_discovery/scripts/run_jarvis_web.sh
```

### Inspect current engine config
```
python memory_bank_discovery/scripts/inspect_engine_config.py
```

### List every unique scope in the bank (who has memories?)
```
python memory_bank_discovery/scripts/list_scopes.py
```

### List memories under a specific scope
Edit `TARGET_SCOPE` at top of the script, then:
```
python memory_bank_discovery/scripts/list_memories_by_scope.py
```

### Add a memory to an arbitrary scope
Edit `TARGET_SCOPE` and `FACT` at top of the script, then:
```
python memory_bank_discovery/scripts/add_memory_for_scope.py
```

### Clean up memories by scope (dry-run safety gate)
Edit `TARGET_SCOPE` in the script. First run with `DRY_RUN = True` (default) to preview, then flip to `DRY_RUN = False` and re-run to actually delete.
```
python memory_bank_discovery/scripts/cleanup_memories_by_scope.py
```

### Update engine config (tuning round)
Edit constants at top of `update_engine_config.py`, then:
```
python memory_bank_discovery/scripts/update_engine_config.py
```

### Validate tuned extraction quality
```
python memory_bank_discovery/scripts/test_tuned_generate.py
```

### Tune `top_k` for reads
Edit `jarvis_agent/memory_config.json`, then restart adk web.

---

## GCP Resources

- **Agent Engine ID** (from `memory_bank_discovery/.env`):
  `projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976`
- **GCP Project:** `ninth-potion-455712-g9`
- **Region:** `us-central1`
- **Engine display name:** Stark Industries Memory Engine
- **Engine description:** Memory Bank engine for ADK agent harness v2
- **Current memory count:** ~18 (varies — use `list_scopes.py` for live count). Includes pre-tuning discovery memories, Pass 2 test memories, Jarvis write-back memories, and a handful of legacy single-key scopes from early Tests 2-5.
- **Cleanup scopes to consider** before v3 kickoff (all contain test data, none load-bearing):
  - `{"user_id": "tony_stark"}` — Tests 2-6 legacy
  - `{"user_id": "peter_parker"}` — Test 5 isolation
  - `{"user_id": "test_tuning"}` — Pass 2 validation
  - `{"user_id": "pepper_bibo"}` — interactive experimentation
