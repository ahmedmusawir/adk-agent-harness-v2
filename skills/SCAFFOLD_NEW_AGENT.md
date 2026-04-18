# SCAFFOLD_NEW_AGENT.md

---

## 1. Skill Metadata

| Field | Value |
|-------|-------|
| **Skill Name** | SCAFFOLD_NEW_AGENT |
| **Version** | 1.0 |
| **Date Created** | 2026-03-03 |
| **Purpose** | Create a correctly structured, ADK-discoverable agent folder in this repo from scratch. |

---

## 2. Trigger

Activate this skill when the user says any of the following (or similar):
- "Create a new agent"
- "Add an agent called X"
- "Scaffold an agent"
- "I need a new agent for [purpose]"
- "Build the [name] agent"

Do NOT activate for: modifying an existing agent, adding a tool to an existing agent, or creating a test file.

---

## 3. Prerequisites

All of the following must be true before executing this skill:

1. **`utils/gcs_utils.py` exists** and exports `fetch_instructions(agent_name: str) -> str`. This function fetches from GCS at: `ADK_Agent_Bundle_1/{agent_name}/{agent_name}_instructions.txt` in bucket `adk-agent-context-ninth-potion-455712-g9`. Confirm it exists before proceeding.

2. **The new agent name is confirmed** — a `snake_case` name that describes the agent's purpose. If the user hasn't provided one, ask before proceeding. Example valid names: `rico_baseline`, `skills_agent`, `jarvis_rag`. Example invalid: `MyAgent`, `agent2`, `new-agent`.

3. **The GCS instruction file is planned** — the skill does NOT create it, but note to the user that `ADK_Agent_Bundle_1/{agent_name}/{agent_name}_instructions.txt` must exist in the GCS bucket before the agent will run correctly.

4. **No folder collision** — confirm `{agent_name}/` does not already exist at the repo root.

---

## 4. Steps

Execute in this exact order.

---

### Step 1 — Confirm the agent name

Verify the name is `snake_case`, all lowercase, no hyphens, no spaces. It will be used for:
- The folder name: `{agent_name}/`
- The Python `Agent(name="{agent_name}", ...)` parameter
- The GCS instruction key: `fetch_instructions("{agent_name}")`

All three must match exactly. This is the single most common scaffolding error — they diverge.

> **Reference inconsistency to avoid:** `product_agent_rico_1/agent.py` calls `fetch_instructions("product_agent")` but the folder is `product_agent_rico_1`. These should match. Do not repeat this pattern.

---

### Step 2 — Create the agent folder

Create the directory `{agent_name}/` at the **repo root** (not inside `agents/` or any subdirectory — this repo does not use an `agents/` top-level directory).

Existing agent folders at repo root for reference: `product_agent_rico_1/`, `jarvis_agent/`, `ghl_mcp_agent/`

---

### Step 3 — Create `{agent_name}/__init__.py`

Content is always exactly this — no more, no less:

```python
from .agent import root_agent
```

This is the ADK discovery contract. The variable must be named `root_agent`. Any other name and `adk web` will not find the agent.

Reference: `product_agent_rico_1/__init__.py`, `jarvis_agent/__init__.py`, `ghl_mcp_agent/__init__.py` — all identical.

---

### Step 4 — Create `{agent_name}/agent.py`

Choose the appropriate boilerplate based on what tool type the agent needs. When in doubt, use **Pattern A** (standard GCS agent).

---

**Pattern A — Standard GCS Agent (most common)**

Use when: the agent fetches instructions from GCS and either has no tools, uses `FunctionTool`, or uses `utils/context_utils.py`.

```python
# {agent_name}/agent.py
from google.adk.agents import Agent
from utils.gcs_utils import fetch_instructions


def get_live_instructions(ctx) -> str:
    return fetch_instructions("{agent_name}")


root_agent = Agent(
    name="{agent_name}",
    model="gemini-2.5-flash",
    description="{one sentence describing what this agent does}",
    instruction=get_live_instructions,
    tools=[],
)
```

Reference: `jarvis_agent/agent.py` (cleanest example of this pattern).

> **Critical:** `instruction=get_live_instructions` — pass the function reference, NOT `get_live_instructions()`. The `()` version calls the function at import time (static). Without `()`, ADK calls it on every request (hot-reload from GCS).

---

**Pattern A+ — Standard GCS Agent with Context Tool**

Use when: the agent also needs to read GCS data files (product lists, knowledge bases, etc.) via `utils/context_utils.py`.

Add these to Pattern A:

```python
from google.adk.tools import FunctionTool
from utils.context_utils import fetch_context

product_context_tool = FunctionTool(func=fetch_context)

# Then in Agent definition:
root_agent = Agent(
    ...
    tools=[product_context_tool],
)
```

Reference: `product_agent_rico_1/agent.py`.

---

**Pattern B — Agent with Environment Variable Credentials**

Use when: the agent needs API keys or credentials from `.env` (e.g., third-party service integrations).

Add `import os` at the top and load credentials using `os.getenv()` at module level, before the Agent definition. `adk web` loads the root `.env` automatically.

```python
# {agent_name}/agent.py
import os
from google.adk.agents import Agent
from utils.gcs_utils import fetch_instructions

MY_API_KEY = os.getenv("MY_API_KEY", "placeholder")


def get_live_instructions(ctx) -> str:
    return fetch_instructions("{agent_name}")


root_agent = Agent(
    name="{agent_name}",
    model="gemini-2.5-flash",
    description="{description}",
    instruction=get_live_instructions,
    tools=[],
)
```

Reference: `ghl_mcp_agent/agent.py` (though that agent has additional MCP complexity — for basic env var usage, just the `import os` + `os.getenv()` pattern is needed).

---

**Pattern C — Grounding Tool Agent (Google Search)**

Use when: the agent uses `google_search`.

```python
from google.adk.agents import Agent
from google.adk.tools import google_search
from utils.gcs_utils import fetch_instructions


def get_live_instructions(ctx) -> str:
    return fetch_instructions("{agent_name}")


root_agent = Agent(
    name="{agent_name}",
    model="gemini-2.5-flash",
    description="{description}",
    instruction=get_live_instructions,
    tools=[google_search],
)
```

Reference: `jarvis_agent/agent.py`.

> **Warning:** Do NOT put `google_search` and `FunctionTool` in the same agent's `tools=[]`. ADK throws `400 INVALID_ARGUMENT`. If you need both, wrap the search agent in `AgentTool`. See `docs/APP_BRIEFS/PHASE_1_OVERVIEW.md` Pattern 5.

---

### Step 5 — Note the required GCS instruction file

This skill does NOT create the GCS file. Inform the user that before the agent will run successfully, this file must exist:

```
Bucket:  adk-agent-context-ninth-potion-455712-g9
Path:    ADK_Agent_Bundle_1/{agent_name}/{agent_name}_instructions.txt
```

The file content is the agent's system prompt. Upload it via the GCS console or `gsutil`:

```bash
gsutil cp {agent_name}_instructions.txt \
  gs://adk-agent-context-ninth-potion-455712-g9/ADK_Agent_Bundle_1/{agent_name}/{agent_name}_instructions.txt
```

Until this file exists, the agent will return: `"Error: Could not load instructions for {agent_name}."` — it will not crash, but it will behave unpredictably.

---

## 5. Validation Checklist

Run through this after scaffolding. Every box must be checked before the scaffold is considered done.

**Naming**
- [ ] Folder name is `snake_case`, all lowercase, no hyphens
- [ ] `Agent(name="{agent_name}")` exactly matches the folder name
- [ ] `fetch_instructions("{agent_name}")` key exactly matches the folder name
- [ ] All three of the above are identical strings

**File Structure**
- [ ] `{agent_name}/` exists at the repo root (not in a subdirectory)
- [ ] `{agent_name}/__init__.py` exists
- [ ] `{agent_name}/agent.py` exists

**`__init__.py` content**
- [ ] Contains exactly one line: `from .agent import root_agent`
- [ ] No other imports, no other code

**`agent.py` content**
- [ ] A variable named exactly `root_agent` is defined at module level
- [ ] `instruction=get_live_instructions` (function reference, not call)
- [ ] `model` is set (default: `"gemini-2.5-flash"`)
- [ ] `description` is set (non-empty string)

**ADK Discovery**
- [ ] Running `adk web .` from the repo root shows the agent by name in the UI
- [ ] The agent responds to a test message (even if instructions aren't uploaded yet, it should respond with the fallback error message — not fail to load entirely)

**GCS**
- [ ] Inform the user that the instruction file at `ADK_Agent_Bundle_1/{agent_name}/{agent_name}_instructions.txt` needs to be created

---

## 6. What This Skill Does NOT Do

This skill scaffolds the folder structure only. It does not:

- **Write agent business logic** — the `tools=[]` list is intentionally empty; add tools in a separate step
- **Create tool implementations** — no `tools.py` file is created
- **Write or upload the GCS instruction file** — system prompt content is the developer's responsibility
- **Create tests** — no `tests/` subfolder, no `test_tools.py`, no `eval_cases.json`
- **Configure token tracking or run receipts** — `utils/token_calculator.py` and `utils/run_receipt.py` wiring is done when those utilities are implemented (Phase 1A)
- **Set up Cloud Run deployment** — no Dockerfile modifications, no deploy.sh changes
- **Handle MCP toolsets** — MCPToolset configuration is an advanced pattern; use `ghl_mcp_agent/agent.py` as reference when needed
- **Register the agent anywhere** — ADK discovers agents automatically by scanning for `root_agent` exports; no registry or config file needs updating

---

*Generated by Claude Code — Cyberize Engineering AI Factory*
*Version: 1.0 | Date: 2026-03-03*
*Repo: adk-harness-starter-v1*
