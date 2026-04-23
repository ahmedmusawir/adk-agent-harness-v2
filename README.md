# ADK Agent Harness v2

A shared scaffold layered around Google ADK agents, built on the principle: **put everything that changes in GCS, keep everything that doesn't change in code.**

System prompts, session memory, skills, and context docs live in Cloud Storage and hot-reload without redeploy. Token costs and latency get logged locally as JSONL receipts. Every agent in the repo shares the same `utils/`, `callbacks/`, and GCS path conventions.

**v2 adds Vertex AI Memory Bank** as a long-term memory layer for durable user facts across sessions (on top of v1's per-session GCS files).

---

## Documentation

Docs are split into two version-scoped folders:

### 📘 [`docs/HARNESS_v1_DOCS/`](docs/HARNESS_v1_DOCS/) — v1 baseline reference

The foundational harness — authoritative for everything that didn't change in v2.

| # | Doc | Covers |
|---|---|---|
| 01 | [01_ARCHITECTURE.md](docs/HARNESS_v1_DOCS/01_ARCHITECTURE.md) | Harness philosophy, ADK basics, repo layout |
| 02 | [02_FILE_STRUCTURE.md](docs/HARNESS_v1_DOCS/02_FILE_STRUCTURE.md) | Directory conventions, what goes where |
| 03 | [03_AGENTS.md](docs/HARNESS_v1_DOCS/03_AGENTS.md) | Agent definition, `root_agent` export, sub-agents |
| 04 | [04_TOOLS.md](docs/HARNESS_v1_DOCS/04_TOOLS.md) | Tool patterns, AgentTool wrapper, google_search conflict |
| 05 | [05_SKILLS_AND_CONTEXT.md](docs/HARNESS_v1_DOCS/05_SKILLS_AND_CONTEXT.md) | GCS-hosted skills and context docs |
| 06 | [06_SESSION_MEMORY.md](docs/HARNESS_v1_DOCS/06_SESSION_MEMORY.md) | GCS session files, per-session state |
| 07 | [07_PROMPTS.md](docs/HARNESS_v1_DOCS/07_PROMPTS.md) | GCS-hosted system prompts, hot-reload |
| 08 | [08_TESTING_AND_EVALS.md](docs/HARNESS_v1_DOCS/08_TESTING_AND_EVALS.md) | Vertex AI Evaluation Service, TrajectorySingleToolUse |
| 09 | [09_OPERATIONS.md](docs/HARNESS_v1_DOCS/09_OPERATIONS.md) | Cloud Run deploy, adk api_server, service accounts |
| 10 | [10_EVAL_RUN_MANUAL.md](docs/HARNESS_v1_DOCS/10_EVAL_RUN_MANUAL.md) | How to run an eval cycle |
| — | [REPO_AUDIT_REPORT.md](docs/HARNESS_v1_DOCS/REPO_AUDIT_REPORT.md) | Snapshot audit of the v1 codebase |

### 📗 [`docs/HARNESS_v2_DOCS/`](docs/HARNESS_v2_DOCS/) — v2 delta (Memory Bank)

What's NEW and CHANGED in v2. Everything else → v1 docs.

| # | Doc | Covers |
|---|---|---|
| — | [README.md](docs/HARNESS_v2_DOCS/README.md) | v2 doc index + what-changed-vs-v1 table |
| 01 | [01_V2_OVERVIEW.md](docs/HARNESS_v2_DOCS/01_V2_OVERVIEW.md) | v2 scope summary |
| 02 | [02_VERTEX_MEMORY_BANK.md](docs/HARNESS_v2_DOCS/02_VERTEX_MEMORY_BANK.md) | What Memory Bank is, read + write architecture |
| 03 | [03_ENGINE_TUNING.md](docs/HARNESS_v2_DOCS/03_ENGINE_TUNING.md) | `context_spec`, topics, few-shots, TTL, how to re-tune |
| 04 | [04_JARVIS_MEMORY_INTEGRATION.md](docs/HARNESS_v2_DOCS/04_JARVIS_MEMORY_INTEGRATION.md) | Custom tool + callback, `memory_config.json` knob |
| 05 | [05_MEMORY_TOOLKIT.md](docs/HARNESS_v2_DOCS/05_MEMORY_TOOLKIT.md) | Scope-based ops scripts (list / add / cleanup / inspect / update) |
| 06 | [06_GOTCHAS_AND_LIMITATIONS.md](docs/HARNESS_v2_DOCS/06_GOTCHAS_AND_LIMITATIONS.md) | Known issues — top_k hardcoded, TTL oneof, session-end hook missing, etc. |
| 07 | [07_DISCOVERY_LAB_REFERENCE.md](docs/HARNESS_v2_DOCS/07_DISCOVERY_LAB_REFERENCE.md) | Pointer to the POC lab (FINDINGS, HANDOFF_REPORT, ENGINE_TUNING_INSPECTION) |

### Related

- [`docs/VERTEX_MEM_BANK_TEST_FOR_YOUTUBE.md`](docs/VERTEX_MEM_BANK_TEST_FOR_YOUTUBE.md) — narrative end-to-end walk-through of the Memory Bank POC (YouTube-script + future-self reference).
- [`memory_bank_discovery/`](memory_bank_discovery/) — the POC sandbox. Scripts, per-test findings, handoff report.

---

## Quick start

### Run Jarvis with Memory Bank (v2 default)
```bash
bash memory_bank_discovery/scripts/run_jarvis_web.sh
```

### Run other agents (no memory wiring needed)
```bash
adk web .
```

### Inspect the memory engine
```bash
python memory_bank_discovery/scripts/inspect_engine_config.py
```

### See what's in the memory bank right now
```bash
python memory_bank_discovery/scripts/list_scopes.py
```

Full command reference: [`docs/HARNESS_v2_DOCS/05_MEMORY_TOOLKIT.md`](docs/HARNESS_v2_DOCS/05_MEMORY_TOOLKIT.md).

---

## Repo state

- Python 3.12 + venv at `.venv/`
- Main deps: `google-cloud-aiplatform==1.111.0`, `google-adk==1.13.0`
- GCP project: `ninth-potion-455712-g9` (region: `us-central1`)
- Agents in the harness: `jarvis_agent/`, `architect_agent/`, `product_agent_rico_1/`, `ghl_mcp_agent/`
- Change log: [`CHANGELOG.md`](CHANGELOG.md)

---

## What's next

**v3** is planned: OpenBrain MCP server with shared-scope memory across all harness agents, memory-specific eval suite, Architect agent integration. See `memory_bank_discovery/docs/HANDOFF_REPORT.md` for the handoff.
