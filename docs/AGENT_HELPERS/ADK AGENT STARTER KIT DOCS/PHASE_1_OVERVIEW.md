# PHASE_1_OVERVIEW.md — ADK Harness Starter v1
## Shared Patterns, Conventions & Starter Kit

---

## Purpose of This Document

This is the second document Claude reads after MASTER_BRIEF.md. It covers everything shared across ALL Phase 1 agents: the starter kit structure, common patterns, GCS conventions, environment setup, and the shared modules that every agent will use.

**Read this BEFORE any individual agent brief.**

---

## The Starter Kit — What Already Exists

The repo starts with a working ADK bundle containing 4 functional agents. These are the foundation. Do NOT delete or break them. New agents are added alongside them.

### Existing Agents

| Agent | What It Does | Tools | Status |
|-------|-------------|-------|--------|
| Product Agent Rico | Reads product list from GCS, answers product questions | GCS file reader (FunctionTool) | Working |
| GHL Agent Rico | Connects to GoHighLevel CRM via MCP server | MCPToolset (250+ tools, filtered) | Working (local MCP) |
| Jarvis Agent | Answers questions using Google Search | google_search (built-in) | Working |
| Math Agent | Performs calculations using a custom tool | FunctionTool (calculator) | Working |

### Current Repo Structure (Expected)

```
adk-harness-starter-v1/
├── agents/
│   ├── product_agent_rico/
│   │   ├── __init__.py          # from .agent import root_agent
│   │   ├── agent.py             # Agent definition + GCS reader tool
│   │   └── tools.py             # GCS file reader implementation
│   ├── ghl_agent_rico/
│   │   ├── __init__.py
│   │   ├── agent.py             # Agent + MCPToolset with tool_filter
│   │   └── tools.py
│   ├── jarvis_agent/
│   │   ├── __init__.py
│   │   ├── agent.py             # Agent + google_search built-in
│   │   └── tools.py
│   └── math_agent/
│       ├── __init__.py
│       ├── agent.py             # Agent + calculator FunctionTool
│       └── tools.py
├── utils/                       # Shared modules go here
│   ├── __init__.py
│   ├── token_calculator.py      # Token calculator (built with Agent 1A)
│   ├── run_receipt.py           # Run receipt logger (built with Agent 1A)
│   ├── session_writer.py        # Session file writer (built with Agent 3)
│   └── gcs_utils.py             # Common GCS read/write helpers
├── briefs/                      # All planning docs
│   ├── MASTER_BRIEF.md
│   ├── PHASE_1_OVERVIEW.md      # YOU ARE HERE
│   └── ...
├── requirements.txt
├── CLAUDE.md                    # Claude Code constitution
├── CHANGELOG.md
└── README.md
```

### First Task — Starter Kit Discovery

Before building any new agent, Claude's FIRST task is to:

1. **Read every file** in the existing agents directory
2. **Run each agent** via `adk web` to confirm they work
3. **Document findings** in `STARTER_KIT_DISCOVERY.md`
4. **Identify patterns** — what is consistent, what is inconsistent, what needs cleanup

This discovery doc becomes the reference for all future agents. If the starter kit has inconsistencies (e.g., one agent sets env vars differently), fix them BEFORE building new agents.

**Do NOT skip this step. Do NOT assume the starter kit is perfect.**

---

## Shared Modules — The Reusable Engine

These modules are built once and imported by every agent. They live in `utils/`.

### 1. Token Calculator (utils/token_calculator.py)

**Built with:** Agent 1A (Rico Baseline)
**Full spec:** See MASTER_BRIEF v1.1 — Token Calculator Micro-Spec

Wraps model calls to capture:
- input_tokens, output_tokens, cached_tokens, total_tokens
- latency_ms, cost_estimate_usd

```python
# Usage in any agent
from utils.token_calculator import tracked_generate

result = tracked_generate(model, contents, config)
response = result["response"]
metrics = result["metrics"]  # dict with all 6 fields
```

**Implementation note:** This is a wrapper function, not an ADK callback. It wraps the model call directly because usage_metadata lives on the response object, not in ADK event stream.

### 2. Run Receipt Logger (utils/run_receipt.py)

**Built with:** Agent 1A (Rico Baseline)
**Full spec:** See MASTER_BRIEF v1.1 — Run Receipt Standard

Writes a JSON receipt to GCS after every agent interaction.

```python
# Usage in any agent
from utils.run_receipt import log_receipt

log_receipt(
    agent_name="rico_baseline",
    model="gemini-2.5-flash",
    token_metrics=metrics,
    tools_used=["gcs_reader"],
    skills_used=[],
    artifacts_created=[],
    success=True,
)
```

**Storage:** `gs://{bucket}/agents/{agent_name}/receipts/{run_id}.json`

### 3. Session File Writer (utils/session_writer.py)

**Built with:** Agent 3 (Skills Agent)
**Full spec:** See PHASE_1A_AGENT_3_SKILLS.md

Writes and reads dated session context files in GCS.

```python
# Usage in any agent
from utils.session_writer import write_session, read_session

# Write today's session context
write_session(
    agent_name="rico_baseline",
    content="User asked about product X. Provided pricing details.",
)

# Read session (returns last 7 days of context)
context = read_session(agent_name="rico_baseline", days=7)
```

**Storage:** `gs://{bucket}/agents/{agent_name}/sessions/session-{YYYY-MM-DD}.md`
**Retention:** 7-day rolling window. Files older than 7 days are ignored (not deleted — deletion is a Phase 2 consideration).

### 4. GCS Utilities (utils/gcs_utils.py)

Common GCS operations used by multiple modules.

```python
from utils.gcs_utils import read_gcs_file, write_gcs_file, list_gcs_files

content = read_gcs_file("agents/rico/instructions/system_prompt.md")
write_gcs_file("agents/rico/sessions/session-2026-02-27.md", content)
files = list_gcs_files("agents/rico/sessions/")
```

---

## ADK Patterns — Required Knowledge

These patterns are confirmed from the ADK playbooks and must be followed by every agent.

### Pattern 1: Environment Variables BEFORE Imports

```python
import os
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "your-project-id")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

# ONLY after env vars are set:
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
```

**Why:** The google.adk package reads env vars at import time. Setting them after import has no effect.

### Pattern 2: Module-Level Session Service (The Amnesia Fix)

```python
# agent.py — top level, outside any function
session_service = InMemorySessionService()  # Module-level global

runner = Runner(
    agent=root_agent,
    app_name="my_app",
    session_service=session_service,
)
```

**Why:** If InMemorySessionService() is created inside a function, ADK loses conversation history on every request. This is the number one ADK bug.

### Pattern 3: root_agent Export

```python
# __init__.py — exactly this, nothing more
from .agent import root_agent
```

**Why:** ADK discovery mechanism (adk web, adk api_server) looks for a variable named exactly `root_agent`. Any other name and the agent will not be found.

### Pattern 4: Callable Instructions (GCS Hot-Reload)

```python
from google.cloud import storage

def get_instruction() -> str:
    client = storage.Client()
    bucket = client.bucket("your-bucket")
    blob = bucket.blob("agents/rico/instructions/system_prompt.md")
    return blob.download_as_text()

root_agent = Agent(
    instruction=get_instruction,  # function reference, NOT get_instruction()
)
```

**Why:** `instruction=fn` is called on every request (hot-reload). `instruction=fn()` is called once at import time (static). We want hot-reload so we can edit prompts in GCS without redeploying.

### Pattern 5: Cannot Mix Grounding Tools + FunctionTool

```python
# WILL FAIL — 400 INVALID_ARGUMENT
root_agent = Agent(
    tools=[google_search, FunctionTool(func=my_tool)],
)

# FIX — Wrap grounding agent in AgentTool
from google.adk.tools import AgentTool

search_agent = Agent(
    name="searcher",
    tools=[google_search],
)

root_agent = Agent(
    tools=[AgentTool(agent=search_agent), FunctionTool(func=my_tool)],
)
```

**Why:** google_search is a Grounding tool. ADK does not allow mixing Grounding tools with FunctionTool in the same agent. The AgentTool wrapper runs the search in a sub-session.

### Pattern 6: Sequential MCP Tool Execution

Add this to any MCP agent's system prompt:

```
CRITICAL: Always execute tools ONE AT A TIME.
Never call multiple tools simultaneously.
Wait for each tool result before making the next tool call.
```

**Why:** MCP servers get corrupted sessions from parallel tool calls. Always enforce sequential execution via system prompt.

---

## GCS Bucket Structure

All agents share one GCS bucket. Organized by agent name.

```
gs://{bucket}/
├── agents/
│   ├── rico_baseline/
│   │   ├── instructions/
│   │   │   └── system_prompt.md
│   │   ├── data/
│   │   │   └── products.json
│   │   ├── sessions/
│   │   │   ├── session-2026-02-27.md
│   │   │   └── session-2026-02-26.md
│   │   ├── receipts/
│   │   │   └── {run_id}.json
│   │   └── skills/
│   │       ├── session_memory_write.md
│   │       └── summarize_conversation.md
│   ├── rico_cached/
│   │   ├── instructions/
│   │   ├── data/
│   │   ├── sessions/
│   │   └── receipts/
│   ├── jarvis_rag/
│   │   ├── instructions/
│   │   ├── sessions/
│   │   └── receipts/
│   ├── skills_agent/
│   │   ├── instructions/
│   │   ├── sessions/
│   │   ├── receipts/
│   │   └── skills/
│   ├── live_context_agent/
│   │   ├── instructions/
│   │   ├── sessions/
│   │   └── receipts/
│   └── mcp_tools_agent/
│       ├── instructions/
│       ├── sessions/
│       └── receipts/
└── utils/
    └── config/
        └── model_pricing.json
```

---

## Model Selection

| Use Case | Model | Reason |
|----------|-------|--------|
| Default for all Phase 1 agents | gemini-2.5-flash | Fast, cheap, good quality. Standard. |
| Complex reasoning (Phase 2+) | gemini-2.5-pro | ~5x more expensive. Only when flash is not enough. |
| Context caching (Agent 1B) | gemini-2.5-flash | Caching works with flash. No need for pro. |

**Do NOT use gemini-2.0-flash.** It is legacy. Always use 2.5 unless there is a specific reason.

---

## Testing Conventions

Full testing strategy is in PHASE_1_TESTING_STRATEGY.md. Here is the summary:

### Every Agent Ships With:

1. **tests/test_tools.py** — pytest for each custom tool
   - Does the GCS reader return data?
   - Does the calculator compute correctly?
   - Does the tool handle errors gracefully?

2. **tests/test_agent.py** — pytest for agent behavior
   - Does the agent respond to a basic query?
   - Does the agent use the expected tools?
   - Does session state persist across turns?

3. **tests/eval_cases.json** — adk eval test cases
   - Input/expected output pairs for LLM quality
   - Retrieval accuracy for RAG agents
   - Skill execution accuracy for skills agents

### Running Tests

```bash
# Unit tests for one agent
pytest agents/rico_baseline/tests/ -v

# All tests
pytest --tb=short

# ADK evals (when configured)
adk eval agents/rico_baseline/
```

---

## Build Order — Phase 1A then Phase 1B

### Phase 1A — Core Engine (Build First)

```
Step 0: Starter Kit Discovery
  Read existing agents, document in STARTER_KIT_DISCOVERY.md
  Fix inconsistencies if found

Step 1: Agent 1A — Rico Baseline + Token Calculator + Run Receipt
  Add token_calculator.py to utils/
  Add run_receipt.py to utils/
  Add gcs_utils.py to utils/
  Wrap Rico model calls with token tracking
  Log run receipts after each interaction
  Write tests
  Establish baseline metrics

Step 2: Agent 1B — Rico Cached
  Clone Rico Baseline
  Add Vertex Context Caching for product data
  Same token tracking + run receipts
  Write tests
  Compare metrics against Rico A baseline

Step 3: Agent 3 — Skills Agent + Session Writer
  Add session_writer.py to utils/
  Build agent with 3 skills: session memory write, summarize, mode switch
  Write skill files to GCS
  Write tests for skill execution
  Verify session files persist in GCS
```

### Phase 1B — External Integrations (Build Second)

```
Step 4: Agent 2 — Jarvis RAG
  Set up Google Managed RAG (Vertex RAG Engine)
  Ingest playbook docs into RAG store
  Build agent that queries RAG for answers
  Write tests for retrieval accuracy
  Add token tracking + run receipts

Step 5: Agent 4 — Live Context Agent
  Implement Gemini Files API for uploads
  Test PDF, DOCX, TXT, image comprehension
  Determine caching threshold (>32k tokens + multi-turn = cache)
  Write tests for comprehension accuracy
  Add token tracking + run receipts

Step 6: Agent 5 — MCP Tools Agent
  Deploy at least 2 MCP servers to Cloud Run
  Connect agent to multiple MCPToolsets
  Test tool composition and filtering
  Write tests for tool execution
  Add token tracking + run receipts
```

### After All Agents

```
Step 7: Integration Verification
  Run ALL tests: pytest + adk eval
  Verify all agents work via adk web
  Compare run receipts across agents
  Document findings in PHASE_1_RESULTS.md
```

---

## Environment Setup — Getting Started

### Prerequisites

- Python 3.12+
- Google Cloud SDK (gcloud) authenticated
- GCP project with Vertex AI API enabled
- GCS bucket created
- `pip install google-adk google-cloud-storage`

### Local Development

```bash
# Clone repo
git clone <repo-url>
cd adk-harness-starter-v1

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_GENAI_USE_VERTEXAI=1
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export GCS_BUCKET=your-bucket-name

# Run all agents in browser
adk web .

# Run specific agent
adk web agents/product_agent_rico/
```

### requirements.txt (Phase 1)

```
google-adk>=0.1.0
google-cloud-storage
google-cloud-aiplatform
pytest
```

**That is it.** No Poetry. No uv. No pyproject.toml. Add dependencies only when a specific agent needs them.

---

## Naming Conventions — Quick Reference

| Thing | Convention | Example |
|-------|-----------|---------|
| Agent folder | snake_case | rico_baseline/ |
| Agent name (in code) | snake_case | name="rico_baseline" |
| Agent variable | root_agent | Always root_agent |
| GCS instruction path | agents/{name}/instructions/ | agents/rico_baseline/instructions/system_prompt.md |
| GCS session path | agents/{name}/sessions/ | agents/rico_baseline/sessions/session-2026-02-27.md |
| GCS receipt path | agents/{name}/receipts/ | agents/rico_baseline/receipts/{uuid}.json |
| GCS skill path | agents/{name}/skills/ | agents/skills_agent/skills/session_memory_write.md |
| Test files | test_*.py | test_tools.py, test_agent.py |
| Eval cases | eval_cases.json | agents/rico_baseline/tests/eval_cases.json |
| Branch name | feat/agent-{n}-{name} | feat/agent-1a-rico-baseline |
| Utility modules | utils/{module}.py | utils/token_calculator.py |

---

## What Claude Reads Next

After this document, Claude reads the individual agent briefs in order:

1. PHASE_1_TESTING_STRATEGY.md — How to write tests (pytest + adk eval)
2. PHASE_1A_AGENT_SET_1_RICO_CACHING.md — Rico A + Rico B (first build)
3. PHASE_1A_AGENT_3_SKILLS.md — Skills + session memory
4. PHASE_1B_AGENT_2_JARVIS_RAG.md — Managed RAG
5. PHASE_1B_AGENT_4_LIVE_CONTEXT.md — Files API
6. PHASE_1B_AGENT_5_MCP_TOOLS.md — MCP servers

**But first:** Run Starter Kit Discovery (Step 0). Do not build anything until the existing agents are documented.

---

*Generated by JARVIS — Cyberize Engineering AI Factory*
*Version: 1.0 | Date: February 27, 2026*