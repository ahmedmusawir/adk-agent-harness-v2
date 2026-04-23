# ADK Agent Harness v2 — Documentation Index

**v2 focus:** Vertex AI Memory Bank integration for long-term durable user context across sessions.

This folder documents what's NEW or CHANGED in v2. For anything not covered here — file structure, agent basics, skills, GCS session memory, general testing/eval patterns, operations — the authoritative reference remains **[../HARNESS_v1_DOCS/](../HARNESS_v1_DOCS/)**.

Treat v2 docs as a delta overlay on v1.

---

## What changed in v2 — at a glance

| Area | v1 status | v2 status |
|---|---|---|
| Agents | 3 (architect, jarvis, product_agent_rico_1, ghl_mcp) | Same agents. **Jarvis updated** for Memory Bank. |
| Session memory | GCS-backed session files | GCS session files **+ Vertex AI Memory Bank** for durable long-term facts |
| Tools | `google_search`, function tools, GCS-loaded skills | Same, plus custom `PreloadMemoryTopK` tool for configurable memory retrieval |
| Agent lifecycle hooks | `before_model_callback` + `after_model_callback` for receipts | Same, plus `after_agent_callback` for turn-gated memory writes |
| Eval system | Vertex AI Evaluation Service (v1) | Unchanged in v2; memory-specific evals deferred to v3 |
| Deployment | Cloud Run + `adk api_server` | Unchanged |

---

## v2 Docs Index

| # | File | What it covers |
|---|---|---|
| — | `README.md` | This file — index + what-changed summary |
| 01 | [01_V2_OVERVIEW.md](01_V2_OVERVIEW.md) | v2 scope, what's new, what stays v1 |
| 02 | [02_VERTEX_MEMORY_BANK.md](02_VERTEX_MEMORY_BANK.md) | What Memory Bank is, architecture, read + write paths |
| 03 | [03_ENGINE_TUNING.md](03_ENGINE_TUNING.md) | Engine `context_spec` config — topics, few-shots, generation model, TTL |
| 04 | [04_JARVIS_MEMORY_INTEGRATION.md](04_JARVIS_MEMORY_INTEGRATION.md) | How Jarvis wires in: custom tool, callback, agent.py changes |
| 05 | [05_MEMORY_TOOLKIT.md](05_MEMORY_TOOLKIT.md) | Scope-based ops scripts (list/add/cleanup) |
| 06 | [06_GOTCHAS_AND_LIMITATIONS.md](06_GOTCHAS_AND_LIMITATIONS.md) | Known issues and why they exist |
| 07 | [07_DISCOVERY_LAB_REFERENCE.md](07_DISCOVERY_LAB_REFERENCE.md) | Pointer to the discovery-lab docs (FINDINGS, HANDOFF_REPORT, ENGINE_TUNING_INSPECTION) |

### Related — discovery-lab docs (outside this folder)

These live in `memory_bank_discovery/docs/` and contain the per-test findings from the POC phase:

- `memory_bank_discovery/docs/FINDINGS.md` — per-test findings (Tests 1-7) + final Summary
- `memory_bank_discovery/docs/ENGINE_TUNING_INSPECTION.md` — Pass 1 inspection + Pass 2 tuning results with SDK source citations
- `memory_bank_discovery/docs/HANDOFF_REPORT.md` — handoff report for v3

### Related — YouTube walk-through

- [../VERTEX_MEM_BANK_TEST_FOR_YOUTUBE.md](../VERTEX_MEM_BANK_TEST_FOR_YOUTUBE.md) — narrative end-to-end walk-through of the whole Memory Bank POC with verbatim commands.

---

## Where to start

- **New to the harness entirely:** read [../HARNESS_v1_DOCS/01_ARCHITECTURE.md](../HARNESS_v1_DOCS/01_ARCHITECTURE.md) first.
- **New to v2 specifically:** start with [01_V2_OVERVIEW.md](01_V2_OVERVIEW.md).
- **Want to understand Memory Bank:** read [02_VERTEX_MEMORY_BANK.md](02_VERTEX_MEMORY_BANK.md) → [03_ENGINE_TUNING.md](03_ENGINE_TUNING.md).
- **Operating the memory day-to-day:** [05_MEMORY_TOOLKIT.md](05_MEMORY_TOOLKIT.md).
- **Hit a weird behavior:** check [06_GOTCHAS_AND_LIMITATIONS.md](06_GOTCHAS_AND_LIMITATIONS.md) first.
