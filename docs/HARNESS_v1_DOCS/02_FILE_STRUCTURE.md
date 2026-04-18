# 02 — File Structure

**ADK Agent Harness v1**

---

## Repo Layout (Annotated)

```
adk-agent-harness-v1/
│
├── architect_agent/                    ← PRIMARY AGENT — fully built out
│   ├── __init__.py                     ← exports root_agent (required by ADK discovery)
│   ├── agent.py                        ← Agent definition: model, tools, callbacks, instructions
│   ├── tools.py                        ← All FunctionTool definitions for this agent
│   ├── test_config.json                ← adk eval CLI config (tool_trajectory_avg_score: 1.0)
│   ├── ARCHITECT_SMOKE_TEST.evalset.json ← Golden eval cases captured via adk web UI
│   ├── MANUAL_TEST_PLAN.md             ← 7-scenario manual smoke test (exact prompts + criteria)
│   ├── MANUAL_TEST_REPORT_TEMPLATE.md  ← Fillable report for each test run
│   └── tests/                         ← Agent-specific unit tests
│       ├── test_receipt_callback.py
│       └── test_run_receipt.py
│
├── jarvis_agent/                       ← Web search agent (earlier build)
│   ├── __init__.py
│   └── agent.py
│
├── ghl_mcp_agent/                      ← GoHighLevel CRM agent via MCP
│   ├── __init__.py
│   └── agent.py
│
├── product_agent_rico_1/               ← Product specialist agent
│   ├── __init__.py
│   └── agent.py
│
├── callbacks/
│   └── receipt_callback.py             ← Timestamp injection + token receipt logging
│
├── utils/
│   ├── gcs_utils.py                    ← GCS read/write, fetch_dual_instructions, fetch_instructions
│   ├── token_calculator.py             ← Vertex AI token counting + cost estimation
│   └── run_receipt.py                  ← Receipt struct: create, format, save to JSONL
│
├── scripts/
│   ├── usage_report.py                 ← Daily usage table from logs/receipts/*.jsonl
│   └── run_evals.py                    ← Eval runner helper
│
├── tests/                              ← Shared unit tests (56 total)
│   ├── conftest.py
│   ├── test_context_cache.py
│   ├── test_eval_runner.py
│   ├── test_receipt_callback.py
│   ├── test_run_receipt.py
│   └── test_token_calculator.py
│
├── logs/
│   └── receipts/                       ← Per-agent JSONL receipt files (gitignored)
│       └── architect_agent.jsonl       ← Created on first agent invocation
│
├── reports/
│   └── usage_reports/                  ← Saved usage report text files (gitignored)
│
├── evals/                              ← Eval artifacts directory
│
├── docs/
│   ├── AGENT_HELPERS/                  ← Reference docs, playbooks, briefs (pre-existing)
│   │   ├── MASTER_BRIEF_FINAL_HARNESS_v1.md
│   │   ├── NAMING_CONVENTIONS.md
│   │   ├── ARCHITECT_AGENT_TESTING_MANUAL.md
│   │   ├── EVAL_TESTING_MANUAL.txt
│   │   ├── REPO_AUDIT_REPORT.md
│   │   ├── ADK AGENT STARTER KIT DOCS/
│   │   └── PYTHON_ADK_PLAYBOOKS/
│   ├── change_logs/                    ← Dated change log entries
│   │   └── change_log_2026-04-14_0000.md
│   └── HARNESS_v1_DOCS/                ← This documentation set
│       ├── 01_ARCHITECTURE.md
│       ├── 02_FILE_STRUCTURE.md
│       ├── 03_AGENTS.md
│       ├── 04_TOOLS.md
│       ├── 05_SKILLS_AND_CONTEXT.md
│       ├── 06_SESSION_MEMORY.md
│       ├── 07_PROMPTS.md
│       ├── 08_TESTING_AND_EVALS.md
│       └── 09_OPERATIONS.md
│
├── skills/                             ← Local skills reference (GCS is the live source)
│
├── session_YYYY-MM-DD.md               ← Claude Code session logs (one per work session)
│
├── architect_agent/.env                ← Per-agent env file (not committed — template below)
├── CLAUDE.md                           ← Claude Code configuration and working rules
├── CHANGELOG.md                        ← Project-level changelog
├── Dockerfile                          ← Cloud Run deployment
├── deploy.sh                           ← Cloud Run deploy script
├── requirements.txt                    ← Python dependencies
└── pytest.ini                          ← Pytest configuration
```

---

## Key File Roles

### `agent.py` (per agent)
The agent definition. Sets the model, wires tools, assigns callbacks, and points to the instruction loader. This is the only file that changes meaningfully between agents.

### `__init__.py` (per agent)
One line: `from .agent import root_agent`. ADK's discovery mechanism requires `root_agent` to be importable from the agent package. Without this, `adk web .` will not find the agent.

### `tools.py` (architect_agent)
All `FunctionTool` definitions for `architect_agent`. Each tool is defined as a Python function, then wrapped: `some_tool = FunctionTool(func=some_function)`. Named variables are always used — inline instantiation inside arrays is prohibited (readability rule).

### `callbacks/receipt_callback.py`
Three factory functions that return callbacks. Factories are used so each agent gets its own closure with correct `agent_name` and `model` parameters. See `04_TOOLS.md` → Callbacks for detail.

### `utils/gcs_utils.py`
The GCS interface. Reads `GCS_BUCKET_NAME` and `GCS_BASE_FOLDER` from environment. Exposes `fetch_dual_instructions()`, `fetch_instructions()`, `write_gcs_file()`, `list_gcs_files()`.

### `.env` (per agent)
Each agent has its own `.env` in its folder. `adk web .` loads this automatically when the agent is selected. **Not committed to git.** Template:

```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GCS_BUCKET_NAME=adk-agent-context-ninth-potion-455712-g9
GCS_BASE_FOLDER=ADK_Agent_Bundle_1
```

---

## GCS Bucket Layout

```
gs://adk-agent-context-ninth-potion-455712-g9/
└── ADK_Agent_Bundle_1/                              ← GCS_BASE_FOLDER
    │
    ├── globals/
    │   ├── global_agent_system_prompt.md            ← Shared system prompt (all agents)
    │   └── skills/
    │       ├── SKILL_INDEX.md                       ← Flat index of all available skills
    │       ├── SESSION_UPDATE_SKILL/
    │       │   └── SKILL.md
    │       └── SESSION_MEMORY_SKILL/
    │           └── SKILL.md
    │
    └── architect_agent/
        ├── architect_agent_system_prompt.md         ← Identity prompt
        ├── sessions/
        │   ├── session-2026-04-02.md
        │   ├── session-2026-04-03.md
        │   └── session-2026-04-14.md
        └── context/
            └── APP_ARCHITECTURE_MANUAL.md
```

### GCS Path Conventions

| Resource | Path pattern |
|----------|-------------|
| Global prompt | `{BASE}/globals/global_agent_system_prompt.md` |
| Agent identity prompt | `{BASE}/{agent_name}/{agent_name}_system_prompt.md` |
| Session file | `{BASE}/{agent_name}/sessions/session-YYYY-MM-DD.md` |
| Skills index | `{BASE}/globals/skills/SKILL_INDEX.md` |
| Named skill | `{BASE}/globals/skills/{SKILL_NAME}/SKILL.md` |
| Context doc | `{BASE}/{agent_name}/context/{DOC_NAME}.md` |

All names use `SCREAMING_SNAKE_CASE` for skills and context docs. Session files use the `session-YYYY-MM-DD.md` date format.

---

## What's Not in Git

| Path | Reason |
|------|--------|
| `logs/receipts/` | Runtime data, grows unbounded |
| `reports/usage_reports/` | Generated output |
| `.env` files | Contains credentials |
| `__pycache__/` | Build artifacts |
| `.venv/` | Virtual environment |

---

*See `03_AGENTS.md` for per-agent detail.*
