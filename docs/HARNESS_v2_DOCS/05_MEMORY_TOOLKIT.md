# 05 — Memory Toolkit

**ADK Agent Harness v2**

---

## What this is

A set of small, single-purpose scripts for CRUD-by-scope operations on Memory Bank. Lives in `memory_bank_discovery/scripts/`. All share the same patterns:

- Constants at top of file (no argparse) — edit and run.
- Read `AGENT_ENGINE_ID` from `memory_bank_discovery/.env`.
- Same project/region constants (`ninth-potion-455712-g9` / `us-central1`).
- Destructive operations gated by a `DRY_RUN` constant.

---

## Mental model — "users are implicit"

Memory Bank has **no first-class user resource.** Users exist only as values in `scope` dicts. There's no "create user" API, no user list endpoint.

| What you want | What actually exists |
|---|---|
| Create a user | Write a memory under a new scope — user "exists" on first write |
| List users | Enumerate all memories, aggregate unique scopes |
| Delete a user | Delete all memories matching that user's scope |

The toolkit scripts operationalize this mental model.

---

## Daily-use scripts

### `list_scopes.py` — who has memories?
Zero args. Enumerates every memory on the engine, aggregates unique `scope` dicts, prints sorted by memory count (biggest first).

```
python memory_bank_discovery/scripts/list_scopes.py
```

Typical output:
```
Total memories on engine: 18
Unique scopes: 4
  [1]   9 memory(ies) under {'app_name': 'jarvis_agent', 'user_id': 'user'}
  [2]   3 memory(ies) under {'user_id': 'tony_stark'}
  [3]   2 memory(ies) under {'user_id': 'test_tuning'}
  [4]   1 memory(ies) under {'user_id': 'peter_parker'}
```

### `list_memories_by_scope.py` — what does this user know?
Edit `TARGET_SCOPE` at top of file (must match byte-for-byte — retrieve is exact-match strict). Prints every memory matching, with full fact text + timestamps.

```
python memory_bank_discovery/scripts/list_memories_by_scope.py
```

### `add_memory_for_scope.py` — give this user a new fact
Edit `TARGET_SCOPE` and `FACT`. Calls `memories.create()` directly — verbatim storage, no extraction, no consolidation on the write side.

```
python memory_bank_discovery/scripts/add_memory_for_scope.py
```

First run under a new scope implicitly "creates" the user.

### `cleanup_memories_by_scope.py` — nuke this user's memories
Two-stage safety:

1. Edit `TARGET_SCOPE`. Leave `DRY_RUN = True` (default).
2. Run — it prints every memory that WOULD be deleted and exits. Nothing is touched.
3. When the preview is right, change `DRY_RUN = False` and re-run. Deletes land.
4. Set `DRY_RUN = True` again to re-arm the safety for next time.

```
python memory_bank_discovery/scripts/cleanup_memories_by_scope.py
```

Uses `client.agent_engines.memories.delete(name=<full_memory_resource_name>)`. One call per memory; no batch delete.

---

## Engine-level scripts

### `inspect_engine_config.py` — what's the engine configured with?
Zero args. Reads `client.agent_engines.get(name=AGENT_ENGINE_ID)` and dumps the full `ReasoningEngine` object (JSON + repr). Annotates each field `SET` or `NOT SET` so missing config is obvious.

```
python memory_bank_discovery/scripts/inspect_engine_config.py
```

### `update_engine_config.py` — apply tuning
Edit constants at top (`GENERATION_MODEL`, `MANAGED_TOPICS`, `CUSTOM_TOPICS`, `FEW_SHOT_EXAMPLES`, `TTL_CONFIG`, `DISPLAY_NAME`, `DESCRIPTION`). Script:

1. Prints a full JSON preview of what it's about to send.
2. Waits for Enter.
3. Calls `client.agent_engines.update(name=AGENT_ENGINE_ID, config=...)`.
4. Reads back the engine and dumps the updated state.

```
python memory_bank_discovery/scripts/update_engine_config.py
```

See [03_ENGINE_TUNING.md](03_ENGINE_TUNING.md) for what each constant does.

### `test_tuned_generate.py` — did the tuning work?
Sends a 6-exchange technical conversation through `memories.generate()` under isolated scope `{"user_id": "test_tuning"}` and runs a content-coverage audit (did each expected fact get captured? did small talk get filtered?).

```
python memory_bank_discovery/scripts/test_tuned_generate.py
```

Re-runs accumulate under the test scope — clean up with `cleanup_memories_by_scope.py` when noisy.

---

## Test / POC scripts (historical reference)

These were built during the Discovery Lab (Tests 1–7) and remain as reference. Not needed for ongoing ops.

| File | What it tested |
|---|---|
| `test_write_memory.py` | Test 2 — direct `memories.create()` |
| `test_read_memory.py` | Test 3 — list / get / retrieve |
| `test_generate_memories.py` | Test 4 — session-based extraction |
| `test_memory_isolation.py` | Test 5 — multi-tenant scope assertions |
| `test_consolidation.py` | Test 6 — contradiction → UPDATE flow |
| `seed_jarvis_memory.py` | Test 7a — one-off pre-seed for Jarvis |
| `run_jarvis_web.sh` | Test 7a — launches `adk web` with memory URI |

See `memory_bank_discovery/docs/FINDINGS.md` for the test findings these correspond to.

---

## Patterns and conventions

### Exact-match scope
All retrieve + cleanup operations match scope as a byte-identical dict. A memory under `{"app_name": "jarvis_agent", "user_id": "user"}` is NOT matched by `TARGET_SCOPE = {"user_id": "user"}` — different shape.

### DRY_RUN on destructive ops
Only `cleanup_memories_by_scope.py` can delete. Read scripts have no destructive paths.

### No argparse
Every toolkit script has constants at top of file. To change behavior: edit the file. Rationale: easier to show on video, fewer typos in long scope dicts, config is versioned in git.

### Fail-loud on config, fail-silent in agent runtime
Scripts crash loudly on missing `.env` or bad input — they're dev tools. The Jarvis tool (`preload_memory_topk.py`) fails silent on retrieval errors — it's in the request path.
