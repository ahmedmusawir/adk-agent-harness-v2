# 07 — Discovery Lab Reference

**ADK Agent Harness v2**

---

## What the Discovery Lab was

Between 2026-04-19 and 2026-04-23, we ran a structured POC of Vertex AI Memory Bank in an isolated sandbox (`memory_bank_discovery/`). Seven tests + a 2-pass engine-tuning cycle + a Jarvis integration pass. The output was the v2 architecture documented in 01–06 of this folder.

The lab is complete. Scripts and findings remain on disk as reference material. **This file is just a map to them** — the authoritative content lives under `memory_bank_discovery/docs/`.

---

## The three discovery-lab docs

### `memory_bank_discovery/docs/FINDINGS.md`
Per-test findings from all seven tests, plus a final Summary.

| Test | Scope |
|---|---|
| Test 1 | Agent Engine creation + resource-name gotcha |
| Test 2 | Direct write via `memories.create()` |
| Test 3 | Three read paths: `list`, `get`, `retrieve` |
| Test 4 | Session-based extraction via `memories.generate()` — headline feature |
| Test 5 | Multi-tenant isolation (scope boundaries) |
| Test 6 | Consolidation + contradiction (the STRONG CONSOLIDATION finding) |
| Test 7 | Jarvis agent integration (read path + write callback + custom top_k fork) |

The Summary at the bottom captures the 10 most important findings distilled.

**Read this when:** you want evidence for any v2 architectural claim. Every behavior in this doc folder traces back to a specific test or SDK source reference in FINDINGS.

### `memory_bank_discovery/docs/ENGINE_TUNING_INSPECTION.md`
Two major sections:

1. **Pass 1 inspection** (pre-tuning) — full engine config dump showing every field was NULL. Plus SDK research answering: can we update `context_spec` in place? what models are supported? what's the few-shot schema? is `preload_memory_tool.top_k` configurable? etc. Every answer backed by a file:line citation from the installed SDK.

2. **Pass 2 tuning results** — the config we applied, the `test_tuned_generate.py` audit result (6/6 checks passed), before/after extraction-quality comparison, and the TTL `oneof` issue we hit + resolved.

**Read this when:** you're about to re-tune the engine and want to understand the surface area, or when you need to cite a specific SDK source line to justify an architectural decision.

### `memory_bank_discovery/docs/HANDOFF_REPORT.md`
Concise handoff for v3. Sections:

- What was built (every script, tool, config file with one-line description)
- Current architecture (read side / write side / engine)
- 10 key findings (terse)
- Known limitations
- Deferred to v3 (OpenBrain MCP, memory evals, Architect integration, recall_memories MCP tool)
- How to run (every script with its command)
- GCP resources (engine ID, project, region, memory count)

**Read this when:** starting v3 work. This is the bridge.

### `memory_bank_discovery/docs/DISCOVERY_BRIEF.md`
Scratchpad from the start of the lab — very short, mostly a plan sketch. Not authoritative.

---

## Related walk-through

`docs/VERTEX_MEM_BANK_TEST_FOR_YOUTUBE.md` (at the `docs/` root, not in v2 folder) — a narrative walk-through covering every test in order with verbatim commands and expected output. Built as a YouTube script and future-self reference.

Useful if you want to replay the entire lab from scratch or teach someone else what we did.

---

## Scripts from the lab (still on disk)

All in `memory_bank_discovery/` or `memory_bank_discovery/scripts/`. See [05_MEMORY_TOOLKIT.md](05_MEMORY_TOOLKIT.md) for the full inventory.

Short version — the operational ones (still used):
- `setup_agent_engine.py` — one-time engine provisioning
- `list_agent_engines.py` — recovery helper
- `scripts/inspect_engine_config.py` — read-only engine dump
- `scripts/update_engine_config.py` — apply tuning
- `scripts/test_tuned_generate.py` — validate extraction quality
- `scripts/list_scopes.py`, `list_memories_by_scope.py`, `add_memory_for_scope.py`, `cleanup_memories_by_scope.py` — the CRUD-by-scope toolkit
- `scripts/seed_jarvis_memory.py` — pre-seed for demo/testing
- `scripts/run_jarvis_web.sh` — `adk web` launcher with memory URI

The older per-test scripts (`test_write_memory.py`, `test_read_memory.py`, `test_generate_memories.py`, `test_memory_isolation.py`, `test_consolidation.py`) remain as historical reference. They're not needed for day-to-day ops but document how each Memory Bank API surface behaves.

---

## When to not use lab artifacts

- **Per-test scripts (`test_*.py` in scripts/)** — just reference. Don't run them against production data; most write to test scopes like `{"user_id": "tony_stark"}` that are isolated from Jarvis's real scope anyway.
- **`memory_bank_discovery/.env`** — holds `AGENT_ENGINE_ID` used by every toolkit script. It's gitignored; don't commit.

---

## What's NOT in the lab

- Memory-specific eval suite — deferred to v3.
- OpenBrain MCP server — deferred to v3.
- Multi-agent memory sharing — deferred to v3 (current architecture siloes per-agent via `app_name` in the scope).
- Custom embedding model experiments — we left `text-embedding-005` at server default.
- `simple_retrieval_params` exploration (pagination for non-similarity listing) — untested.
- `disable_consolidation=True` behavior — untested.

All listed in `memory_bank_discovery/docs/HANDOFF_REPORT.md` → "Deferred to v3."
