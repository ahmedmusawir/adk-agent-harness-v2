# REPO_AUDIT_REPORT.md

## ADK Agent Harness v1 — Clone of the Start Kit

**Date:** 2026-03-27
**Auditor:** Claude Code (Sonnet 4.6)
**Branch audited:** `kit-handbook-v1`
**Commit:** `9d119f1`
**Audience:** Architecture team

---

## 1. Repo Structure Map

```
adk-harness-starter-v1/
│
├── product_agent_rico_1/            # ACTIVE AGENT — Rico product assistant
│   ├── agent.py                     # Agent definition + GCS callable instruction + FunctionTool
│   └── __init__.py                  # from .agent import root_agent
│
├── jarvis_agent/                    # ACTIVE AGENT — Google Search agent
│   ├── agent.py                     # Agent definition + google_search Grounding tool
│   └── __init__.py                  # from .agent import root_agent
│
├── ghl_mcp_agent/                   # REFERENCE AGENT — GoHighLevel CRM via MCP (not active Phase 1)
│   ├── agent.py                     # Agent + MCPToolset → services.leadconnectorhq.com/mcp/
│   ├── __init__.py                  # from .agent import root_agent
│   └── .env                         # Agent-local env file (not gitignored at this level — see Risk 15)
│
├── utils/                           # Shared utilities
│   ├── gcs_utils.py                 # fetch_instructions() — GCS hot-reload pattern (WORKING)
│   ├── context_utils.py             # fetch_context(), fetch_document() — GCS knowledge base (WORKING)
│   ├── token_calculator.py          # STUB — not yet implemented (Phase 1A deliverable)
│   ├── run_receipt.py               # STUB — not yet implemented (Phase 1A deliverable)
│   ├── session_writer.py            # STUB — not yet implemented (Phase 1A/Agent 3 deliverable)
│   └── session_reader.py            # STUB — not yet implemented (Phase 1A/Agent 3 deliverable)
│
├── docs/
│   ├── NAMING_CONVENTIONS.md        # v1.0, March 3 2026 — naming rules for all artifacts
│   ├── APP_BRIEFS/
│   │   ├── MASTER_BRIEF_v1.2.md     # v1.2, March 3 2026 — 4-phase roadmap
│   │   ├── PHASE_1_OVERVIEW.md      # v1.0, Feb 27 2026 — shared Phase 1 patterns
│   │   ├── PHASE_1_TESTING_STRATEGY.md  # v1.0, Feb 28 2026 — pytest + adk eval framework
│   │   ├── STARTER_KIT_SPEC.md      # v1.0, Feb 28 2026 — repo cleanup spec from bundle
│   │   └── PHASE_1A_AGENT_SET_1_RICO_CACHING.md  # v2.1, Feb 28 2026 — Rico A+B build spec
│   └── PYTHON_ADK_PLAYBOOKS/        # 9 reference playbooks (no version info in filenames)
│       ├── adk-agents-fundamentals.md    # Agent lifecycle, session, runner, gotchas
│       ├── adk-advanced-patterns.md      # Multi-agent, MCPToolset, output_key, GCS hot-reload
│       ├── cloud-run-deployment.md       # deploy.sh, Dockerfile, Secret Manager, flags
│       ├── fastapi-adk-gateway.md        # /run_agent wrapper pattern, session recovery
│       ├── mcp-server-typescript.md      # TypeScript MCP server patterns
│       ├── multi-runtime-docker.md       # Supervisor + Nginx multi-process container
│       ├── rag-pipelines.md              # Managed RAG (File Search API) + DIY (Chroma)
│       ├── streamlit-patterns.md         # Streamlit UI patterns, auth, session bookmarks
│       └── vertex-ai-integrations.md     # Gemini, Imagen, TTS, STT, context caching
│
├── CLAUDE.md                        # Claude Code constitution (AI agent instructions)
├── README.md                        # Minimal — 2 lines only ("repeatable ADK harness starter kit v1")
├── Dockerfile                       # python:3.11-slim, adk api_server with $PORT + $DB_URI
├── deploy.sh                        # gcloud run deploy --source . (source-based)
├── store_secrets.sh                 # Reads .env, pushes to GCP Secret Manager
├── grant_permissions.sh             # Service account IAM setup (one-time)
├── start_server.sh                  # Local dev: adk api_server with --session_service_uri
├── requirements.txt                 # Fully pinned, 134 packages
├── .env_example                     # Env var template (has critical bug — see Section 7)
├── .env                             # Local dev env (gitignored — contains actual secrets)
├── .gcloudignore                    # Cloud Build exclusion list
├── .gitignore                       # Git exclusion list (standard Python + project-specific)
├── .python-version                  # 3.12.3
├── cyberize-vertex-api.json         # Service account key (gitignored, local dev only)
└── session_2026-03-02.md            # Claude Code session file (created today)
```

**Total agent folders:** 3
**Total working utility files:** 2 (gcs_utils.py, context_utils.py)
**Total stub utility files:** 4 (token_calculator.py, run_receipt.py, session_writer.py, session_reader.py)
**Total doc files:** 15 (5 APP_BRIEFS + 9 PLAYBOOKS + 1 NAMING_CONVENTIONS)
**Total test files:** 0

---

## 2. Documentation Inventory

### APP_BRIEFS

| File                                   | Version           | Covers                                                                                             | Issues                                                                                                                                                                                                                                  |
| -------------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MASTER_BRIEF_v1.2.md`                 | v1.2, Mar 3 2026  | 4-phase roadmap, model strategy (Gemini-only Phases 1-3, Claude in Phase 4), rules of engagement   | References 4 agent brief docs that do NOT exist in repo                                                                                                                                                                                 |
| `PHASE_1_OVERVIEW.md`                  | v1.0, Feb 27 2026 | Shared patterns for all Phase 1 agents, starter kit structure, GCS layout, build order             | Describes `agents/` + `shared/` directory structure that contradicts the actual flat repo layout and STARTER_KIT_SPEC                                                                                                                   |
| `PHASE_1_TESTING_STRATEGY.md`          | v1.0, Feb 28 2026 | pytest + adk eval framework, per-agent test specs, Rico A vs B comparison protocol                 | References `shared/` module path that doesn't exist; references `scripts/compare_ricos.py` that doesn't exist                                                                                                                           |
| `STARTER_KIT_SPEC.md`                  | v1.0, Feb 28 2026 | Repo cleanup from google-adk-n8n-hybrid-v2 bundle, stubs to create, target file structure          | References 5 `docs/` files (overview.md, architecture.md, patterns.md, decisions.md, api-info.md) that are NOT in the repo; uses `utils/` (not `shared/`); target structure shows `product_agent/` folder (not `product_agent_rico_1/`) |
| `PHASE_1A_AGENT_SET_1_RICO_CACHING.md` | v2.1, Feb 28 2026 | Rico A (baseline + token tracking) + Rico B (Vertex context caching) build spec, comparison script | References docs/patterns.md, docs/architecture.md, docs/decisions.md — none exist; calls shared modules `token_calculator.py` but elsewhere calls them `token_tracker.py`                                                               |

### PYTHON_ADK_PLAYBOOKS

| File                         | What It Covers                                                                                           |
| ---------------------------- | -------------------------------------------------------------------------------------------------------- |
| `adk-agents-fundamentals.md` | Agent anatomy, session amnesia fix, asyncio, event loop, module structure, `adk web` vs `adk api_server` |
| `adk-advanced-patterns.md`   | Sequential/Parallel agents, AgentTool, MCPToolset, output_key, GCS callable instructions, LiteLlm        |
| `cloud-run-deployment.md`    | deploy.sh template, Dockerfile, Secret Manager, key flags (`--no-cpu-throttling`, `--min-instances=1`)   |
| `fastapi-adk-gateway.md`     | FastAPI `/run_agent` wrapper, session 404 recovery, history endpoint, multi-agent config                 |
| `mcp-server-typescript.md`   | TypeScript MCP server with Streamable HTTP transport, Zod schemas, error-as-response pattern             |
| `multi-runtime-docker.md`    | Supervisor + Nginx multi-process Docker container for ADK + TypeScript MCP in one container              |
| `rag-pipelines.md`           | Google Managed RAG (File Search API) full lifecycle; DIY RAG (crawl4ai + LangChain + Chroma)             |
| `streamlit-patterns.md`      | Auth gate, session bookmarks, chat UI, undo stack, live HTML preview, Mission Control admin panel        |
| `supabase-integration.md`    | Supabase auth gate, per-user session bookmarks, RLS, connection pooling for Cloud Run                    |
| `vertex-ai-integrations.md`  | Gemini generation, Imagen, TTS chunking, STT, multimodal inputs, context caching, Files API              |

### Missing Documentation (Referenced But Not Present)

The following files are cited in the APP_BRIEFS as required reading or dependencies. They do not exist:

| Missing File                       | Where Referenced                                | Impact                                                                                      |
| ---------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `docs/overview.md`                 | STARTER_KIT_SPEC.md ("Documentation" keep list) | Agent briefs expect it                                                                      |
| `docs/architecture.md`             | STARTER_KIT_SPEC.md, PHASE_1A brief             | Phase 1A brief says "see architecture.md" for GCS bucket layout                             |
| `docs/patterns.md`                 | STARTER_KIT_SPEC.md, PHASE_1A brief             | Phase 1A brief says "see patterns.md Pattern 1, Pattern 2"                                  |
| `docs/decisions.md`                | STARTER_KIT_SPEC.md, PHASE_1A brief             | Phase 1A brief says "see decisions.md Decision 6, Decision 7"                               |
| `docs/api-info.md`                 | STARTER_KIT_SPEC.md                             | API reference — undefined impact                                                            |
| `PHASE_1A_AGENT_3_SKILLS.md`       | MASTER_BRIEF doc hierarchy                      | Skills agent + session memory cannot be built without this                                  |
| `PHASE_1B_AGENT_2_JARVIS_RAG.md`   | MASTER_BRIEF doc hierarchy                      | RAG agent cannot be built without this                                                      |
| `PHASE_1B_AGENT_4_LIVE_CONTEXT.md` | MASTER_BRIEF doc hierarchy                      | Live context agent cannot be built without this                                             |
| `PHASE_1B_AGENT_5_MCP_TOOLS.md`    | MASTER_BRIEF doc hierarchy                      | MCP tools agent cannot be built without this                                                |
| `CHANGELOG.md`                     | CLAUDE.md (Changelog Protocol)                  | Every Claude Code session that touches docs should update it — protocol is broken           |
| `STARTER_KIT_DISCOVERY.md`         | PHASE_1_OVERVIEW Step 0                         | "Do NOT build anything until the existing agents are documented" — not created yet          |
| `DISCOVERY_NOTES.md`               | PHASE_1A_AGENT_SET_1_RICO_CACHING.md            | Required before building Rico B ("Document findings in DISCOVERY_NOTES.md before building") |

### Doc Conflicts

**Conflict 1 — GCS Path Schema (Critical)**
Three documents define contradictory GCS path structures:

- **Existing code** (`gcs_utils.py`, `context_utils.py`): `ADK_Agent_Bundle_1/{agent_name}/{agent_name}_instructions.txt` and `ADK_Agent_Bundle_1/context_store/{file}`
- **STARTER_KIT_SPEC.md**: `ADK_Agent_Bundle_1/{agent_name}/sessions/` and `ADK_Agent_Bundle_1/run_receipts/`
- **PHASE_1_OVERVIEW.md**: `agents/{agent_name}/sessions/`, `agents/{agent_name}/receipts/`
- **NAMING_CONVENTIONS.md**: `agents/{agent_name}/context/`, `agents/{agent_name}/sessions/`, `agents/{agent_name}/run_receipts/`

The naming convention schema (the most recently written doc, March 3 2026) conflicts with all the existing code and two earlier planning docs. Any new code written to the convention spec will point to GCS paths that don't contain the actual data.

**Conflict 2 — `shared/` vs `utils/` (Critical)**

- `PHASE_1_OVERVIEW.md` calls the shared module directory `shared/` with files: `token_tracker.py`, `run_receipt.py`, `session_writer.py`, `gcs_utils.py`
- `STARTER_KIT_SPEC.md` uses `utils/` with files: `token_calculator.py`, `run_receipt.py`, `session_writer.py`, `session_reader.py`, `gcs_utils.py`, `context_utils.py`
- Actual repo: `utils/` directory with `gcs_utils.py` and `context_utils.py` (working) + 4 stubs

The module named `token_tracker.py` in PHASE_1_OVERVIEW is the same thing as `token_calculator.py` in STARTER_KIT_SPEC and PHASE_1A brief — different names for the same concept.

**Conflict 3 — Repo Name**

- `MASTER_BRIEF_v1.2.md`: `Repo: adk-harness-modules-workshop-v1`
- `README.md` and actual repo: `adk-harness-starter-v1`

**Conflict 4 — Repo Directory Layout**

- `PHASE_1_OVERVIEW.md`: Expects `agents/product_agent_rico/`, `agents/ghl_agent_rico/`, `agents/jarvis_agent/`, `agents/math_agent/` under an `agents/` top-level directory, plus `shared/`
- `STARTER_KIT_SPEC.md` and actual repo: Agents at root level (`product_agent_rico_1/`, `jarvis_agent/`, `ghl_mcp_agent/`), no `agents/` directory

**Conflict 5 — Token Module Name**
MASTER_BRIEF says `shared/token_tracker.py`. STARTER_KIT_SPEC stub and PHASE_1A implementation spec both say `utils/token_calculator.py`. Must be resolved before Phase 1A begins or the wrong file will be created.

---

## 3. Agent Inventory

### Agent 1: `product_agent_rico_1` (Rico — Product Specialist)

| Property               | Value                                                                                                                                                                             |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Folder**             | `product_agent_rico_1/`                                                                                                                                                           |
| **Agent name (code)**  | `"product_agent"` — MISMATCH with folder name                                                                                                                                     |
| **Description**        | "Product Specialist agent"                                                                                                                                                        |
| **Model**              | `gemini-2.5-flash`                                                                                                                                                                |
| **Tools**              | `FunctionTool(func=fetch_context)` — fetches any file from `ADK_Agent_Bundle_1/context_store/`                                                                                    |
| **Instruction source** | Callable: `fetch_instructions("product_agent")` → GCS: `ADK_Agent_Bundle_1/product_agent/product_agent_instructions.txt` (~31k tokens per PHASE_1A brief)                         |
| **System prompt**      | GCS hot-reload via callable (correct pattern)                                                                                                                                     |
| **Session management** | None defined in agent — relies on ADK web runner                                                                                                                                  |
| **Runner**             | Not defined in agent file — ADK discovery handles it                                                                                                                              |
| **Env vars**           | Not set in file — relies on shell/env                                                                                                                                             |
| **Status**             | **Working** — tested per commit "2mar2026 - first commit tested"                                                                                                                  |
| **Notes**              | Folder `product_agent_rico_1` doesn't match `name="product_agent"` in code. PHASE_1A brief refers to it as `product_agent/`. The discrepancy will cause confusion in build steps. |

### Agent 2: `jarvis_agent` (Jarvis — Google Search)

| Property               | Value                                                                                                                                                                                                                                                                                           |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Folder**             | `jarvis_agent/`                                                                                                                                                                                                                                                                                 |
| **Agent name (code)**  | `"jarvis_agent"` — matches folder                                                                                                                                                                                                                                                               |
| **Description**        | "Jarvis agent"                                                                                                                                                                                                                                                                                  |
| **Model**              | `gemini-2.5-flash`                                                                                                                                                                                                                                                                              |
| **Tools**              | `google_search` (built-in Grounding tool)                                                                                                                                                                                                                                                       |
| **Instruction source** | Callable: `fetch_instructions("jarvis_agent")` → GCS                                                                                                                                                                                                                                            |
| **System prompt**      | GCS hot-reload via callable (correct pattern)                                                                                                                                                                                                                                                   |
| **Session management** | None defined in agent                                                                                                                                                                                                                                                                           |
| **Runner**             | Not defined in agent file                                                                                                                                                                                                                                                                       |
| **Env vars**           | Not set in file — relies on shell/env                                                                                                                                                                                                                                                           |
| **Status**             | **Working** — tested per commit                                                                                                                                                                                                                                                                 |
| **Bugs**               | `from google import genai` imported but never used                                                                                                                                                                                                                                              |
| **Landmine**           | Uses `google_search` (Grounding tool). Per playbooks: cannot mix Grounding tools with `FunctionTool` in same agent. When Phase 1A adds token tracking callback, if it requires adding a `FunctionTool`, the agent will break with `400 INVALID_ARGUMENT`. Must use `AgentTool` wrapper pattern. |

### Agent 3: `ghl_mcp_agent` (GHL CRM — MCP Reference)

| Property               | Value                                                                                                                                                                                                                                                                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Folder**             | `ghl_mcp_agent/`                                                                                                                                                                                                                                                                                                                           |
| **Agent name (code)**  | `"ghl_mcp_agent"` — matches folder                                                                                                                                                                                                                                                                                                         |
| **Description**        | "Rico - Your friendly GHL-connected assistant powered by Vertex"                                                                                                                                                                                                                                                                           |
| **Model**              | `gemini-2.5-flash`                                                                                                                                                                                                                                                                                                                         |
| **Tools**              | `MCPToolset(StreamableHTTPConnectionParams(url="https://services.leadconnectorhq.com/mcp/"))`                                                                                                                                                                                                                                              |
| **Instruction source** | Hardcoded string in Python function `get_rico_instructions()` — NOT from GCS (inconsistent with other agents)                                                                                                                                                                                                                              |
| **Session management** | None defined in agent                                                                                                                                                                                                                                                                                                                      |
| **Runner**             | Not defined in agent file                                                                                                                                                                                                                                                                                                                  |
| **Credentials**        | `GHL_API_TOKEN`, `GHL_LOCATION_ID` from env vars                                                                                                                                                                                                                                                                                           |
| **Status**             | **Reference only** — per STARTER_KIT_SPEC: "CODE REFERENCE ONLY — not active in Phase 1." Will not function without valid GHL credentials                                                                                                                                                                                                  |
| **Bugs**               | File header comment reads `# /calc_agent/agent.py` — stale copy-paste from source bundle. Tool filter commented out. Missing "Execute tools ONE AT A TIME" sequential execution instruction — this is documented as causing MCP session corruption in production (see `adk-advanced-patterns.md` Pattern 9 and `mcp-server-typescript.md`) |

---

## 4. Naming Convention Compliance

Per `docs/NAMING_CONVENTIONS.md` v1.0 (March 3 2026).

| Location                         | Current Name                                                        | Rule Violated                                                                                                     | Suggested Fix                                                                                                                                                              |
| -------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent folder                     | `product_agent_rico_1/`                                             | Agent folders: `snake_case`, should match `name` field                                                            | Rename to `product_agent/` OR update `name` field to match folder — must be decided                                                                                        |
| Agent name field                 | `name="product_agent"` in `product_agent_rico_1/agent.py`           | Agent instance names should match folder name + `_agent` suffix OR folder should match name                       | Align folder and name field — currently `product_agent_rico_1` ≠ `product_agent`                                                                                           |
| `ghl_mcp_agent/agent.py` line 1  | `# /calc_agent/agent.py`                                            | File comment is wrong (leftover from source bundle)                                                               | Change to `# ghl_mcp_agent/agent.py`                                                                                                                                       |
| `.env_example` value             | `GOOGLE_GENAI_USE_VERTEXAI=FALSE`                                   | Env vars: `SCREAMING_SNAKE_CASE` value is wrong — should be `1` or `TRUE`                                         | Change to `GOOGLE_GENAI_USE_VERTEXAI=1`                                                                                                                                    |
| Current git branch               | `kit-handbook-v1`                                                   | Branches: `feat/`, `fix/`, `chore/`, `docs/` prefix required                                                      | `chore/starter-kit-setup` or `docs/kit-handbook`                                                                                                                           |
| `cyberize-vertex-api.json`       | kebab-case filename                                                 | Files: `snake_case` convention                                                                                    | `cyberize_vertex_api.json` — though this is a credential file and renaming may affect other tooling                                                                        |
| `jarvis_agent/agent.py`          | `from google import genai` (unused import)                          | Code quality — dead import                                                                                        | Remove unused import                                                                                                                                                       |
| GCS path in `gcs_utils.py`       | `ADK_Agent_Bundle_1/{agent_name}/{agent_name}_instructions.txt`     | NAMING_CONVENTIONS: `agents/{agent_name}/context/{file}`                                                          | Either update conventions to match code OR migrate GCS paths — must be decided                                                                                             |
| GCS path in `context_utils.py`   | `ADK_Agent_Bundle_1/context_store/{file}`                           | NAMING_CONVENTIONS: `agents/{agent_name}/context/{file}`                                                          | Same as above                                                                                                                                                              |
| Stub module name                 | `utils/token_calculator.py` (stub exists)                           | MASTER_BRIEF/PHASE_1_OVERVIEW call it `token_tracker.py`; STARTER_KIT_SPEC/PHASE_1A call it `token_calculator.py` | Decide on one name. Recommendation: `token_calculator.py` per NAMING_CONVENTIONS (most recently written doc)                                                               |
| Module location                  | `utils/` directory                                                  | PHASE_1_OVERVIEW expects `shared/` directory                                                                      | Decide: `utils/` or `shared/` before Phase 1A                                                                                                                              |
| `ghl_mcp_agent/.env`             | Agent-local .env file                                               | No convention violation, but not covered by root `.gitignore`. Verify it's not tracked                            | Confirm file is gitignored or add to `.gitignore`                                                                                                                          |
| `docs/PYTHON_ADK_PLAYBOOKS/*.md` | lowercase kebab-case filenames (e.g., `adk-agents-fundamentals.md`) | NAMING_CONVENTIONS: docs should be `SCREAMING_SNAKE_CASE.md`                                                      | Per convention should be `ADK_AGENTS_FUNDAMENTALS.md` — though this convention may only apply to APP_BRIEFS, which are written in SCREAMING_SNAKE. Clarify scope with Tony |

**Compliant items (no violation):**

- All `__init__.py` files: correct pattern `from .agent import root_agent`
- All function names in `utils/`: `snake_case` ✓
- All constants in `utils/`: `SCREAMING_SNAKE_CASE` ✓
- All APP_BRIEF filenames: `SCREAMING_SNAKE_CASE.md` ✓
- Agent `name` fields in `jarvis_agent` and `ghl_mcp_agent`: match folder names ✓

---

## 5. Playbook vs Reality Gap Analysis

| Expected (per docs)                                                                                     | Status          | Notes                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `utils/token_calculator.py` implemented                                                                 | **STUB**        | Exists with function signatures and `# TODO` comments only. Returns zeroes. Required before Phase 1A can measure anything.                                                                                                                                                                 |
| `utils/run_receipt.py` implemented                                                                      | **STUB**        | Exists with function signature and `pass`. Required before Phase 1A can log telemetry.                                                                                                                                                                                                     |
| `utils/session_writer.py` implemented                                                                   | **STUB**        | Exists with function signature and `pass`. Required for Agent 3 (Skills Agent).                                                                                                                                                                                                            |
| `utils/session_reader.py` implemented                                                                   | **STUB**        | Exists with function signature and returns `""`. Required for Agent 3.                                                                                                                                                                                                                     |
| `docs/overview.md`, `docs/architecture.md`, `docs/patterns.md`, `docs/decisions.md`, `docs/api-info.md` | **NOT FOUND**   | Listed in STARTER_KIT_SPEC as "keep" from original bundle. Either never existed in this repo or were not migrated. PHASE_1A brief directly references `docs/patterns.md` Pattern 1, 2, 3 and `docs/decisions.md` Decision 6, 7. Claude will fail to find them during Phase 1A build.       |
| `CHANGELOG.md`                                                                                          | **NOT FOUND**   | Required by CLAUDE.md Changelog Protocol. Every documentation change should log an entry. Protocol is silently broken.                                                                                                                                                                     |
| `STARTER_KIT_DISCOVERY.md`                                                                              | **NOT FOUND**   | PHASE_1_OVERVIEW mandates Step 0: "Do NOT build anything until the existing agents are documented." This discovery doc was never created. Building Phase 1A without it skips a required prerequisite.                                                                                      |
| `DISCOVERY_NOTES.md`                                                                                    | **NOT FOUND**   | PHASE_1A brief says "Document findings in DISCOVERY_NOTES.md before building Rico B." Required before the caching implementation.                                                                                                                                                          |
| `tests/` directory                                                                                      | **NOT FOUND**   | Zero test files exist anywhere in the repo. The entire PHASE_1_TESTING_STRATEGY.md is unimplemented.                                                                                                                                                                                       |
| `pytest.ini` or `pyproject.toml`                                                                        | **NOT FOUND**   | Required to define pytest markers (`unit`, `integration`, `slow`). Tests cannot be run with proper filtering without it.                                                                                                                                                                   |
| `tests/fixtures/` directory                                                                             | **NOT FOUND**   | PHASE_1_TESTING_STRATEGY requires fixture files: `sample_product_list.txt`, `sample_receipt.json`, etc.                                                                                                                                                                                    |
| `rico_b/` agent folder                                                                                  | **NOT FOUND**   | Phase 1A deliverable. The cached version of Rico. Not yet built.                                                                                                                                                                                                                           |
| `compare_ricos.py`                                                                                      | **NOT FOUND**   | Phase 1A comparison script. Required to produce `comparison_results.md`.                                                                                                                                                                                                                   |
| `comparison_results.md`                                                                                 | **NOT FOUND**   | Phase 1A output document. Not yet generated.                                                                                                                                                                                                                                               |
| `agents/` top-level directory                                                                           | **NOT FOUND**   | PHASE_1_OVERVIEW expects agents under `agents/`. Contradicted by STARTER_KIT_SPEC (flat layout). Not present.                                                                                                                                                                              |
| `shared/` directory                                                                                     | **NOT FOUND**   | PHASE_1_OVERVIEW expects shared modules in `shared/`. STARTER_KIT_SPEC uses `utils/`. Not present.                                                                                                                                                                                         |
| Math Agent (`math_agent/`)                                                                              | **NOT FOUND**   | PHASE_1_OVERVIEW lists "Math Agent" as an existing agent in the starter kit ("performs calculations using a custom tool"). Not present in this repo. Either was never migrated or was deleted without documentation.                                                                       |
| `Runner` + `InMemorySessionService` in agents                                                           | **NOT PRESENT** | The playbooks require module-level `Runner` and `InMemorySessionService`. None of the 3 agents define them. They work under `adk web` because ADK handles the runner. But Phase 1A's `after_model_callback` for token tracking requires direct runner access — this will need to be added. |
| Env var setup before ADK imports                                                                        | **MISSING**     | PHASE_1_OVERVIEW Pattern 1 and `adk-agents-fundamentals.md` require `os.environ.setdefault(...)` at the top of every agent file before `from google.adk` imports. None of the 3 agents do this. They rely on env vars being pre-set in the shell. Works in practice but is fragile.        |
| GCS `sessions/` subfolder per agent                                                                     | **UNVERIFIED**  | STARTER_KIT_SPEC describes creating session subfolders in GCS. Cannot verify GCS contents from this audit.                                                                                                                                                                                 |
| GCS `run_receipts/` folder                                                                              | **UNVERIFIED**  | Same as above — cannot verify GCS bucket contents.                                                                                                                                                                                                                                         |
| `PHASE_1A_AGENT_3_SKILLS.md`                                                                            | **NOT FOUND**   | Skills Agent build spec. 4 of the 9 documents in MASTER_BRIEF's doc hierarchy are missing.                                                                                                                                                                                                 |
| `PHASE_1B_AGENT_2_JARVIS_RAG.md`                                                                        | **NOT FOUND**   | RAG Agent build spec. Cannot build Agent 2 without it.                                                                                                                                                                                                                                     |
| `PHASE_1B_AGENT_4_LIVE_CONTEXT.md`                                                                      | **NOT FOUND**   | Live Context Agent build spec. Cannot build Agent 4 without it.                                                                                                                                                                                                                            |
| `PHASE_1B_AGENT_5_MCP_TOOLS.md`                                                                         | **NOT FOUND**   | MCP Tools Agent build spec. Cannot build Agent 5 without it.                                                                                                                                                                                                                               |
| `ghl_mcp_agent` instruction from GCS                                                                    | **VIOLATED**    | PHASE_1_OVERVIEW and playbooks specify GCS callable instructions for hot-reload. `ghl_mcp_agent` has hardcoded string instructions in Python. Not a blocking issue (it's reference-only) but inconsistent.                                                                                 |
| Sequential MCP execution instruction                                                                    | **MISSING**     | `adk-advanced-patterns.md` Pattern 9 and `mcp-server-typescript.md` gotcha #3 both warn that MCP agents MUST include "Execute tools ONE AT A TIME" in the system prompt to prevent session poisoning. `ghl_mcp_agent` does not include this.                                               |

---

## 6. Deployment & Infrastructure Files

| File                   | Current State                                                                                     | Issues                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Dockerfile`           | python:3.11-slim, shell-form CMD, `adk api_server --port=${PORT} --session_service_uri=${DB_URI}` | **Python version mismatch:** Dockerfile uses 3.11, `.python-version` specifies 3.12.3. `cloud-run-deployment.md` playbook recommends `python:3.12-slim`.                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `deploy.sh`            | Source-based deploy (`--source .`). Sets env vars + 3 secrets.                                    | **Unfilled placeholder:** `GCS_BUCKET_NAME="your-agent-instructions-bucket-name"` — this env var is passed but has a placeholder value. **Missing Cloud Run flags** recommended by playbook: no `--no-cpu-throttling`, no `--cpu-boost`, no `--min-instances 1`, no `--memory`, no `--cpu`. Without `--no-cpu-throttling`, ADK streaming will timeout mid-stream. Without `--min-instances 1`, cold starts will cause session management race conditions. **Note:** Uses `--source .` but the repo has a `Dockerfile` — two deployment paths with no documentation explaining which to use when. |
| `store_secrets.sh`     | Reads `.env`, pushes to Secret Manager. Handles create vs update correctly.                       | Well-implemented. Minor: hardcodes `PROJECT_ID` — should read from env.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `grant_permissions.sh` | Grants `roles/aiplatform.user` and `roles/storage.objectViewer`                                   | **Missing `roles/secretmanager.secretAccessor`**: The `deploy.sh` uses `--set-secrets`. Cloud Run will crash at startup if the service account cannot read secrets. This script as written will produce a service that cannot access Secret Manager at runtime.                                                                                                                                                                                                                                                                                                                                  |
| `start_server.sh`      | Loads `.env`, starts `adk api_server` with Supabase session URI                                   | Good for multi-instance local testing. Minor: will fail clearly if `.env` missing.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `.gcloudignore`        | Excludes `.venv`, `__pycache__`, `.git`, `.env`, `*.json`                                         | **`*.json` is a broad wildcard.** Excludes ALL `.json` files from Cloud Build upload. Intentional for `cyberize-vertex-api.json` but may exclude other JSON files if any are added at root. `cloud-run-deployment.md` recommends naming specific files rather than wildcard JSON exclusion.                                                                                                                                                                                                                                                                                                      |
| `.gitignore`           | Standard Python + project-specific (`cyberize-vertex-api.json`, `adk_sessions.db`)                | **`ghl_mcp_agent/.env`** is not explicitly listed. The root `.env` is gitignored, but the nested `ghl_mcp_agent/.env` may or may not be covered depending on gitignore precedence rules. Should be verified.                                                                                                                                                                                                                                                                                                                                                                                     |
| `requirements.txt`     | Fully pinned, 134 packages                                                                        | **Massively over-specified for 3 agents.** Includes: `yfinance`, `pandas`, `huggingface-hub`, `litellm` (not used in any agent), `beautifulsoup4`, `shapely`, `hf-xet`, `crawl4ai`-adjacent packages. These are artifacts from the `google-adk-n8n-hybrid-v2` bundle that were not pruned during starter kit creation. Estimated Docker build overhead: significant — every Cloud Run deploy installs all 134 packages.                                                                                                                                                                          |
| `.python-version`      | `3.12.3`                                                                                          | Correct per playbook recommendations. Conflicts with Dockerfile's `python:3.11-slim`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |

---

## 7. Risks & Gaps

**Risk 1 — GCS Path Schema Conflict (BLOCKING)**
The `NAMING_CONVENTIONS.md` (the authoritative doc) specifies `agents/{agent}/context/` and `agents/{agent}/sessions/` paths. The existing `gcs_utils.py` and `context_utils.py` use `ADK_Agent_Bundle_1/` paths pointing to a real GCS bucket with real data. If any developer writes new code following the naming convention, it will point to the wrong GCS paths and return empty/error results. This will be invisible until runtime. Must be resolved before Phase 1A begins.

**Risk 2 — `.env_example` Has Wrong Vertex AI Setting (BLOCKING)**
`GOOGLE_GENAI_USE_VERTEXAI=FALSE` disables Vertex AI routing. Any developer who runs `cp .env_example .env` will have a broken ADK configuration — agents will attempt to use the public Gemini API instead of Vertex AI, which fails without a `GOOGLE_API_KEY`. This is the first thing a new developer does when setting up the project.

**Risk 3 — No Tests Exist (HIGH)**
Zero test files. The entire `PHASE_1_TESTING_STRATEGY.md` is a plan with no implementation. Any code written now has no regression protection. If Phase 1A adds token tracking to an existing agent and breaks it, there is no test to catch it.

**Risk 4 — Utility Stubs Return Silent Placeholders (HIGH)**
`token_calculator.py` returns `{"input_tokens": 0, "output_tokens": 0, ...}`. `run_receipt.py` returns `pass`. `session_reader.py` returns `""`. If any agent accidentally imports and calls these before they're implemented, it will appear to work (no exceptions) but produce garbage data. The token tracking will show all-zero counts with no error.

**Risk 5 — grant_permissions.sh Missing Secret Manager Role (HIGH)**
Running `grant_permissions.sh` and then deploying with `deploy.sh` (`--set-secrets`) will result in a Cloud Run service that starts up and then crashes when it tries to read the secrets injected via `--set-secrets`. The crash happens at runtime, not at deploy time, making it harder to diagnose.

**Risk 6 — Python Version Mismatch in Dockerfile (MEDIUM)**
`.python-version = 3.12.3` but `Dockerfile FROM python:3.11-slim`. The venv runs Python 3.12 locally; Cloud Run runs Python 3.11. Any behavior difference between versions (type annotations, syntax features, library version compatibility) will only surface in production.

**Risk 7 — Missing Prerequisite Docs for Phase 1A (MEDIUM)**
`docs/patterns.md`, `docs/architecture.md`, and `docs/decisions.md` are explicitly referenced in `PHASE_1A_AGENT_SET_1_RICO_CACHING.md` ("see docs/patterns.md Pattern 1, 2, 3"). These files don't exist. An AI coding agent executing the Phase 1A brief will fail to find them and either proceed on wrong assumptions or halt.

**Risk 8 — Jarvis Agent Grounding Tool Landmine (MEDIUM)**
`jarvis_agent` uses `google_search` (Grounding tool). Per `adk-advanced-patterns.md`: mixing Grounding tools with `FunctionTool` in the same agent causes `400 INVALID_ARGUMENT`. Phase 1A adds token tracking to all agents, which likely requires a callback or FunctionTool. If anyone adds a FunctionTool alongside `google_search`, Jarvis breaks. The `AgentTool` wrapper pattern is required but not obvious.

**Risk 9 — `product_agent_rico_1` Folder Name Mismatch (MEDIUM)**
The folder is named `product_agent_rico_1` but the agent's `name` field is `"product_agent"`. The PHASE_1A brief (the primary build document) calls it `product_agent/`. An agent following the brief will try to create or modify `product_agent/` and not find it. This will cause build confusion.

**Risk 10 — GCS Instructions Files Not Verified to Exist (MEDIUM)**
Both `product_agent` and `jarvis_agent` use callable instructions fetching from GCS paths. If these files don't exist in the bucket (or bucket access fails), `fetch_instructions()` returns an error string `"Error: Could not load instructions for {agent_name}."` — and this string becomes the agent's system prompt. The agent will silently run with a broken instruction set and respond nonsensically.

**Risk 11 — Bloated `requirements.txt` in Production (MEDIUM)**
134 packages including `yfinance`, `pandas`, `huggingface-hub`, `litellm` (the MCP agent uses direct MCPToolset, not LiteLlm). This inflates Docker images and Cloud Run cold start times. `litellm` alone is large. If this was not intentionally kept, it should be pruned before deploying to production.

**Risk 12 — `shared/` vs `utils/` Decision Not Made (MEDIUM)**
PHASE_1_OVERVIEW says `shared/`. STARTER_KIT_SPEC says `utils/`. The stubs currently live in `utils/`. The PHASE_1A brief uses `utils/`. But MASTER_BRIEF's "Starter Kit Foundation" table says `shared/token_tracker.py` and `shared/run_receipt.py`. Whichever is built during Phase 1A, the other doc will be wrong. Agents built later following the wrong doc will import from the wrong path.

**Risk 13 — `ghl_mcp_agent` Missing Sequential Tool Instruction (LOW for now, HIGH when activated)**
Per `adk-advanced-patterns.md` Pattern 9: "MCP agents MUST include 'Execute tools ONE AT A TIME' in the system prompt." The `ghl_mcp_agent` instruction does not include this. With 200+ GHL tools available, the agent may attempt parallel calls. This is reference-only now, but if activated it will cause session corruption.

**Risk 14 — `deploy.sh` GCS Bucket Placeholder (LOW — won't deploy correctly)**
`GCS_BUCKET_NAME="your-agent-instructions-bucket-name"` is a placeholder. If `deploy.sh` is run as-is, the agents will have the wrong bucket env var and GCS reads will fail.

**Risk 15 — `ghl_mcp_agent/.env` May Contain Live Credentials**
The file `ghl_mcp_agent/.env` exists. The root `.gitignore` gitignores `.env` at the root level. Nested `.env` files may or may not be covered depending on gitignore rules. If this file contains live GHL credentials (`GHL_API_TOKEN`, `GHL_LOCATION_ID`) and is accidentally committed, those credentials are exposed.

---

## 8. Recommendations (Observe Only — Do Not Implement)

Prioritized by blocking potential on Phase 1A work. All are pre-Phase-1A unless noted.

### P0 — Must Fix Before Any Phase 1A Code Is Written

1. **Decide GCS path schema.** Choose one: preserve `ADK_Agent_Bundle_1/` paths (update NAMING_CONVENTIONS.md), or migrate to `agents/` paths (update gcs_utils.py and context_utils.py). This decision affects every new agent, every test, and every GCS path in the codebase.

2. **Decide `shared/` vs `utils/`.** One name for the shared module directory. Update all docs to match. Recommendation: keep `utils/` (code already exists there) and update PHASE_1_OVERVIEW to say `utils/`.

3. **Decide `token_calculator.py` vs `token_tracker.py`.** One name. Update the non-canonical doc. Recommendation: `token_calculator.py` per STARTER_KIT_SPEC stub that already exists.

4. **Resolve `product_agent_rico_1/` folder name.** Either rename folder to `product_agent/` (matches the `name` field and all docs) or update the Phase 1A brief to reference the correct folder name.

5. **Fix `.env_example`.** Change `GOOGLE_GENAI_USE_VERTEXAI=FALSE` to `GOOGLE_GENAI_USE_VERTEXAI=1`. This is a developer-experience landmine.

### P1 — Fix Before First Deployment

6. **Add `roles/secretmanager.secretAccessor` to `grant_permissions.sh`.** Without this, Cloud Run cannot access secrets injected via `--set-secrets` and will crash at startup.

7. **Fix `deploy.sh` placeholder.** Replace `GCS_BUCKET_NAME="your-agent-instructions-bucket-name"` with the actual bucket name `adk-agent-context-ninth-potion-455712-g9`.

8. **Add missing Cloud Run flags to `deploy.sh`.** Per `cloud-run-deployment.md` playbook: add `--no-cpu-throttling`, `--cpu-boost`, `--min-instances 1`, `--memory 2Gi`, `--cpu 2`. Without these, ADK streaming will timeout and cold starts will cause session race conditions.

9. **Fix `Dockerfile` Python version.** Change `FROM python:3.11-slim` to `FROM python:3.12-slim` to match `.python-version` and local development environment.

### P2 — Fix Before Phase 1A Build Begins

10. **Create `CHANGELOG.md`.** Required by `CLAUDE.md` Changelog Protocol. Every Claude Code documentation change requires a log entry. Protocol is currently broken — no log exists.

11. **Create `STARTER_KIT_DISCOVERY.md`.** `PHASE_1_OVERVIEW` Step 0 is a hard prerequisite: "Do NOT build anything until the existing agents are documented." Phase 1A begins with this step.

12. **Create or remove references to `docs/patterns.md`, `docs/architecture.md`, `docs/decisions.md`.** Either create these files (can be stubs summarizing what's in the playbooks) or update the PHASE_1A brief to point to the actual playbook files that contain the same content.

13. **Prune `requirements.txt`.** Remove packages not needed for the 3-agent starter kit (`yfinance`, `pandas`, `huggingface-hub`, `litellm`, etc.). Generate a fresh requirements file from only what the agents actually import. Reduces Docker build times and image size significantly.

14. **Verify `ghl_mcp_agent/.env` is gitignored.** Confirm the nested `.env` file is not tracked by git. If it contains live credentials, add explicit gitignore rule.

### P3 — Fix During Phase 1A Build

15. **Add `os.environ.setdefault()` to each agent file** before ADK imports. Low urgency for `adk web` usage, but required for correctness and for any standalone script usage.

16. **Fix `jarvis_agent` unused import.** Remove `from google import genai`.

17. **Fix `ghl_mcp_agent` stale file comment.** Change `# /calc_agent/agent.py` to `# ghl_mcp_agent/agent.py`.

18. **Create `pytest.ini`** with markers `unit`, `integration`, `slow` before writing any tests. This is a one-time 10-line config that enables `pytest -m unit` filtering.

### P4 — Before Phase 1B Agent Briefs Are Needed

19. **Create missing agent brief docs.** Per MASTER_BRIEF hierarchy: `PHASE_1A_AGENT_3_SKILLS.md`, `PHASE_1B_AGENT_2_JARVIS_RAG.md`, `PHASE_1B_AGENT_4_LIVE_CONTEXT.md`, `PHASE_1B_AGENT_5_MCP_TOOLS.md`. Without these, Phase 1B agents cannot be built by Claude Code.

---

## Appendix A: Confirmed Working (Do Not Break)

The following components are confirmed working per the "2mar2026 - first commit tested" commit and should not be modified without explicit purpose:

- `product_agent_rico_1/agent.py` — Agent definition and callable instruction
- `product_agent_rico_1/__init__.py` — ADK discovery export
- `jarvis_agent/agent.py` — Agent definition and callable instruction
- `jarvis_agent/__init__.py` — ADK discovery export
- `utils/gcs_utils.py` — `fetch_instructions()` — GCS instruction fetcher
- `utils/context_utils.py` — `fetch_context()`, `fetch_document()` — GCS knowledge base tools

## Appendix B: Dependency Audit — Packages in requirements.txt Without Obvious Usage

The following packages in `requirements.txt` have no corresponding import in any current source file. They appear to be artifacts from the original `google-adk-n8n-hybrid-v2` bundle:

- `yfinance` — stock data (no agent uses this)
- `pandas` — dataframes (no agent uses this)
- `huggingface-hub` — Hugging Face models (no agent uses this)
- `litellm` — multi-provider LLM proxy (no agent uses this directly; google-adk may use it internally for LiteLlm model support but not required for Gemini-only setup)
- `beautifulsoup4` — HTML parsing (gcs_utils.py does not use it; may have been used in original bundle's greeting_agent or calc_agent)
- `shapely` — geometric operations (no agent uses this)
- `hf-xet` — Hugging Face transfer (no agent uses this)
- `multitasking` — (no agent uses this)
- `absolufy-imports` — dev tool (should not be in production requirements)

---

_Generated by Claude Code (claude-sonnet-4-6)_
_Branch: kit-handbook-v1 | Commit: 9d119f1_
_Audit date: 2026-03-02_
