# 03 — Agents

**ADK Agent Harness v1**

---

## Overview

Four agents exist in the repo. `architect_agent` is the primary fully-featured agent. The others are earlier builds or specialized integrations kept for reference and reuse.

| Agent | Model | Instructions | Tools | Status |
|-------|-------|-------------|-------|--------|
| `architect_agent` | gemini-3-flash-preview | Dual (global + identity from GCS) | 6 custom + search sub-agent | Primary — full feature set |
| `jarvis_agent` | gemini-2.5-flash | Single (identity from GCS) | `google_search` | Earlier build — web search only |
| `ghl_mcp_agent` | gemini-2.5-flash | Inline (hardcoded in Python) | MCP toolset (GoHighLevel CRM) | Specialized — CRM integration |
| `product_agent_rico_1` | gemini-2.5-flash | Single (identity from GCS) | `fetch_context` FunctionTool | Earlier build — product context |

---

## architect_agent

**The primary agent.** Fully instrumented with dual prompts, session memory, skills, context docs, timestamp injection, and token receipts.

### Identity
- **Name:** `architect_agent`
- **Model:** `gemini-3-flash-preview`
- **Role:** Software architect — reviews architecture decisions, writes Claude Code prompts, loads project context, remembers prior sessions

### Instructions
Loaded via `fetch_dual_instructions("architect_agent")` on every request. Combines:
1. `globals/global_agent_system_prompt.md` — shared standards
2. `architect_agent/architect_agent_system_prompt.md` — persona and role definition

### Tools

| Tool | FunctionTool name | Purpose |
|------|-------------------|---------|
| `write_session_memory` | `write_session_memory_tool` | Appends timestamped update to today's GCS session file |
| `read_session_memory` | `read_session_memory_tool` | Reads recent session files from GCS (default: 7 days) |
| `invoke_skill` | `invoke_skill_tool` | Loads a named skill's SKILL.md from GCS |
| `get_current_datetime` | `get_current_datetime_tool` | Returns current UTC time as ISO 8601 string |
| `read_context_doc` | `read_context_doc_tool` | Loads a named context doc from the agent's GCS context/ folder |
| `search_specialist` | `search_specialist_tool` (AgentTool) | Delegates web search to a google_search sub-agent |

### Callbacks

| Callback | Type | Purpose |
|----------|------|---------|
| `get_start_time_callback()` | before_model #1 | Records `_run_start_time` in session state for latency tracking |
| `get_timestamp_inject_callback()` | before_model #2 | Prepends `[SYSTEM_TIMESTAMP:]` to system instruction (replaces prior) |
| `get_receipt_callback(agent_name, model)` | after_model | Logs token count, cost, latency to `logs/receipts/architect_agent.jsonl` |

### File locations
```
architect_agent/
├── agent.py      ← Agent definition
├── tools.py      ← FunctionTool implementations
└── __init__.py   ← exports root_agent
```

### `.env` required keys
```bash
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GCS_BUCKET_NAME=adk-agent-context-ninth-potion-455712-g9
GCS_BASE_FOLDER=ADK_Agent_Bundle_1
```

---

## jarvis_agent

An earlier general-purpose agent with web search. Kept as a clean reference for a minimal ADK agent setup.

### Identity
- **Name:** `jarvis_agent`
- **Model:** `gemini-2.5-flash`
- **Role:** General assistant with access to Google Search

### Instructions
Loaded via `fetch_instructions("jarvis_agent")` — single identity prompt only (no global prompt merge). GCS path: `{BASE}/jarvis_agent/jarvis_agent_instructions.txt`

### Tools
- `google_search` — built-in ADK tool (no custom FunctionTools, so no sub-agent wrapping needed here)

### Callbacks
- `get_start_time_callback()` — before_model (latency tracking)
- `get_receipt_callback(agent_name="jarvis_agent", model="gemini-2.5-flash")` — after_model

### Notes
- Uses the older `fetch_instructions()` function (single prompt), not `fetch_dual_instructions()`
- No session memory, no skills, no context docs — minimal agent
- Useful as a starting template for a simple single-purpose agent

---

## ghl_mcp_agent

A GoHighLevel CRM agent named Rico. Uses the MCP protocol to connect to the GoHighLevel API via `MCPToolset`.

### Identity
- **Name:** `ghl_mcp_agent`
- **Model:** `gemini-2.5-flash`
- **Role:** CRM assistant for GoHighLevel — contacts, conversations, calendars, opportunities, payments

### Instructions
Inline — defined as a Python function in `agent.py`, not loaded from GCS. The instruction includes the `GHL_LOCATION_ID` injected at runtime so the agent always uses the correct CRM location.

### Tools
- `MCPToolset` — connects to `https://services.leadconnectorhq.com/mcp/` with Bearer auth. Provides access to all GoHighLevel CRM endpoints.

### Required environment variables
```bash
GHL_API_TOKEN=<your-ghl-private-integration-token>
GHL_LOCATION_ID=<your-ghl-location-id>
GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

### Callbacks
- `get_start_time_callback()` — before_model
- `get_receipt_callback(agent_name="ghl_mcp_agent", model="gemini-2.5-flash")` — after_model

### Notes
- No GCS dependency for instructions — standalone agent
- MCP toolset provides all CRM tools dynamically — no individual FunctionTool definitions needed
- `tool_filter` in the MCPToolset is commented out — all available GHL tools are exposed

---

## product_agent_rico_1

A product specialist agent that loads product context via a FunctionTool.

### Identity
- **Name:** `product_agent_rico_1`
- **Model:** `gemini-2.5-flash`
- **Role:** Product specialist — answers questions about product catalog using fetched context

### Instructions
Loaded via `fetch_instructions("product_agent")` — single GCS prompt.

### Tools
- `product_context_tool` — wraps `fetch_context` from `utils/context_utils.py`. Fetches product-specific context on demand.

### Callbacks
- `get_start_time_callback()` — before_model
- `get_receipt_callback(agent_name="product_agent_rico_1", model="gemini-2.5-flash")` — after_model

### Notes
- `utils/context_utils.py` is not present in the main utils (separate utility specific to this agent)
- Earlier build — predates the skills/context-doc pattern used in architect_agent

---

## How to Add a New Agent

1. Create a new folder: `my_agent/`
2. Create `my_agent/__init__.py` with `from .agent import root_agent`
3. Create `my_agent/agent.py` with an `Agent` definition, using the harness callbacks
4. Create `my_agent/.env` with `GOOGLE_GENAI_USE_VERTEXAI=TRUE` and GCS vars if needed
5. Upload the identity prompt to GCS: `{BASE}/my_agent/my_agent_system_prompt.md`
6. Run `adk web .` — the new agent appears in the dropdown

See `docs/AGENT_HELPERS/ADK AGENT STARTER KIT DOCS/STARTER_KIT_SPEC.md` for a full new-agent checklist.

---

*See `04_TOOLS.md` for tool signatures and implementation details.*
