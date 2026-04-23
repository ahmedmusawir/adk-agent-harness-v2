# 01 — v2 Overview

**ADK Agent Harness v2**

---

## What v2 is

v2 adds **Vertex AI Memory Bank** as a long-term memory layer on top of the v1 foundation. v1 already had GCS-backed session files for per-session context; v2 adds durable facts that survive across sessions, consolidate on contradiction, and can be queried semantically.

Everything else from v1 — GCS-hosted prompts, skills, session memory files, receipts, evals, deployment — is unchanged.

---

## What's new in v2

1. **Vertex AI Memory Bank integration**
   - A tuned Agent Engine (`projects/.../reasoningEngines/6954288450136702976`) holds user facts.
   - Custom extraction topics + few-shot examples so the server-side Gemini pulls out domain-relevant facts.
   - Granular TTL policy: 1y for manual writes, 30d for auto-extracted, 90d for consolidation updates.

2. **Custom `PreloadMemoryTopK` tool** (`jarvis_agent/preload_memory_topk.py`)
   - Drop-in replacement for ADK's `preload_memory_tool`.
   - Fixes the hardcoded `top_k=3` ceiling by calling `memories.retrieve()` directly.
   - Knob lives in `jarvis_agent/memory_config.json` — edit JSON, restart `adk web`, done.

3. **`after_agent_callback` write path** in Jarvis
   - Per-turn callback with a turn-count gate fires `memory_service.add_session_to_memory()` every N turns (currently 2).
   - Server-side consolidation makes repeated extraction safe — no duplicates.

4. **Memory toolkit** (`memory_bank_discovery/scripts/`)
   - `list_scopes.py`, `list_memories_by_scope.py`, `add_memory_for_scope.py`, `cleanup_memories_by_scope.py`.
   - Also: `inspect_engine_config.py`, `update_engine_config.py`, `test_tuned_generate.py` for engine ops.

5. **Memory Bank Discovery Lab**
   - 7 tests + Pass 1 inspection + Pass 2 tuning run, all documented.
   - Findings, handoff report, and engine-tuning inspection live in `memory_bank_discovery/docs/`.

---

## What stays v1 (use v1 docs as reference)

- **File structure and repo layout** — see `../HARNESS_v1_DOCS/02_FILE_STRUCTURE.md`.
- **Agent definition basics** — Agent class, root_agent export, GCS-hosted instructions — see `../HARNESS_v1_DOCS/03_AGENTS.md`.
- **Existing tools** — `google_search` (now via AgentTool wrapper in Jarvis to avoid Gemini's native-search conflict), function tools, skill loaders — see `../HARNESS_v1_DOCS/04_TOOLS.md`.
- **Skills and context docs** — all still GCS-hosted — see `../HARNESS_v1_DOCS/05_SKILLS_AND_CONTEXT.md`.
- **GCS session memory** — still the primary per-session state mechanism — see `../HARNESS_v1_DOCS/06_SESSION_MEMORY.md`. Memory Bank is a complement, not a replacement.
- **Prompts** — still GCS-hosted with hot-reload — see `../HARNESS_v1_DOCS/07_PROMPTS.md`.
- **Evals** — Vertex AI Evaluation Service, `TrajectorySingleToolUse`, custom `PointwiseMetric` — see `../HARNESS_v1_DOCS/08_TESTING_AND_EVALS.md`.
- **Operations / deployment** — Cloud Run, `adk api_server`, service accounts — see `../HARNESS_v1_DOCS/09_OPERATIONS.md`.

---

## Who v2 docs are for

- **The current author re-entering the repo after time away.** These docs exist to rebuild context quickly.
- **A new engineer joining the project.** Start here, drop into v1 docs as needed.
- **The v3 phase.** The handoff report in `memory_bank_discovery/docs/HANDOFF_REPORT.md` lists what's deferred.

---

## Versioning convention

- `v1` = original harness: multi-agent ADK scaffold, GCS session memory, receipts, evals.
- `v2` = v1 + Memory Bank integration (this phase).
- `v3` = planned: OpenBrain MCP server with shared-scope memory across all harness agents; memory-specific eval suite; Architect agent integration.

The on-disk project directory is named `adk-agent-harness-v2` to match. v3 will likely be a new repo or a major structural change within this one.
