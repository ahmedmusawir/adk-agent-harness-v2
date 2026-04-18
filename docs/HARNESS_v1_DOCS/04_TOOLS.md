# 04 — Tools

**ADK Agent Harness v1**

---

## Overview

Tools are how agents take action. In ADK, tools are either `FunctionTool` instances (Python functions), `AgentTool` instances (sub-agents), or `MCPToolset` instances (MCP-connected tool collections).

This document covers:
1. `architect_agent` FunctionTools (in `architect_agent/tools.py`)
2. The `search_specialist` AgentTool
3. Utility functions used by tools (`utils/gcs_utils.py`, `utils/token_calculator.py`, `utils/run_receipt.py`)
4. Callbacks (not tools, but tightly coupled to the agent lifecycle)

---

## architect_agent FunctionTools

All defined in `architect_agent/tools.py`.

---

### `write_session_memory`

**Purpose:** Appends a timestamped entry to today's session file in GCS. Creates the file if it doesn't exist.

**Signature:**
```python
def write_session_memory(content: str) -> str
```

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `content` | `str` | The session update text to write |

**Returns:** Confirmation string with the GCS path written to.
Example: `"Session update written to: gs://bucket/ADK_Agent_Bundle_1/architect_agent/sessions/session-2026-04-14.md"`

**GCS path:** `{BASE}/{agent_name}/sessions/session-YYYY-MM-DD.md` (today's UTC date)

**Behavior:**
- Reads existing file content if it exists
- Appends `\n## {timestamp}\n{content}\n` to existing content
- Writes back the combined content
- Uses UTC for both the date (filename) and timestamp (entry header)

**Side effects:** Creates or modifies a GCS file. Prints the path to stdout.

**FunctionTool variable:** `write_session_memory_tool`

---

### `read_session_memory`

**Purpose:** Reads recent session files from GCS to restore context from prior sessions.

**Signature:**
```python
def read_session_memory(days: int = 7) -> str
```

**Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | `int` | `7` | How many days back to read |

**Returns:** Concatenated content of matching session files, newest first, separated by `---`. Returns an informative message if no files are found.

**GCS prefix:** `{BASE}/{agent_name}/sessions/`

**Behavior:**
- Lists all blobs under the sessions prefix
- Filters to files matching `session-YYYY-MM-DD.md` within the date window
- Sorts newest first
- Downloads and concatenates content
- Each section is labeled `# Session: YYYY-MM-DD`

**Side effects:** None (read-only).

**FunctionTool variable:** `read_session_memory_tool`

---

### `invoke_skill`

**Purpose:** Loads a named skill's instruction file from the shared skills library in GCS.

**Signature:**
```python
def invoke_skill(skill_name: str) -> str
```

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `skill_name` | `str` | SCREAMING_SNAKE_CASE skill name, without .md extension (e.g. `"SESSION_UPDATE_SKILL"`) |

**Returns:** Full content of the skill's `SKILL.md` file, or an error message if not found.

**GCS path logic:**
- `SKILL_INDEX` → `{BASE}/globals/skills/SKILL_INDEX.md` (flat file, no subfolder)
- All other skills → `{BASE}/globals/skills/{SKILL_NAME}/SKILL.md`

**Side effects:** Prints `Loaded skill '{skill_name}' ({n} chars) from GCS.` to stdout.

**FunctionTool variable:** `invoke_skill_tool`

---

### `get_current_datetime`

**Purpose:** Returns the current UTC date and time as an ISO 8601 string.

**Signature:**
```python
def get_current_datetime() -> str
```

**Parameters:** None

**Returns:** UTC timestamp string. Example: `"2026-04-14T12:30:00Z"`

**When to use:** This tool exists as a fallback. In normal operation, the agent reads time from the `[SYSTEM_TIMESTAMP:]` injected by `get_timestamp_inject_callback()`. This tool should NOT be called if the callback is working — that is one of the manual test pass criteria.

**Side effects:** None.

**FunctionTool variable:** `get_current_datetime_tool`

---

### `read_context_doc`

**Purpose:** Loads a named context document from the agent's context library in GCS.

**Signature:**
```python
def read_context_doc(doc_name: str) -> str
```

**Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `doc_name` | `str` | SCREAMING_SNAKE_CASE doc name, without .md extension (e.g. `"APP_ARCHITECTURE_MANUAL"`) |

**Returns:** Full content of the context document, or an error message if not found.

**GCS path:** `{BASE}/{agent_name}/context/{doc_name}.md`

**Note:** Unlike skills (which are global), context docs are per-agent. `CONTEXT_INDEX` (if it exists) is also in the same `context/` folder.

**Side effects:** Prints `Loaded context doc '{doc_name}' ({n} chars) from GCS.` to stdout.

**FunctionTool variable:** `read_context_doc_tool`

---

## search_specialist (AgentTool)

**Purpose:** Performs Google web searches. Exposed to `architect_agent` as an AgentTool wrapping a dedicated sub-agent.

**Why a sub-agent:** ADK v1.13.0 does not allow `google_search` (built-in) to coexist with custom `FunctionTool` instances in the same agent. The sub-agent pattern is the required workaround.

**Sub-agent definition:**
```python
search_specialist = Agent(
    name="search_specialist",
    model="gemini-2.5-flash",
    description="Performs web searches using Google Search.",
    tools=[google_search],
)
search_specialist_tool = AgentTool(agent=search_specialist)
```

**How the parent calls it:** The parent agent (`architect_agent`) sends a natural-language query. `search_specialist` runs its own Gemini turn with `google_search`, then returns the result to the parent.

**Scope discipline note:** `search_specialist` must NOT be called for off-topic requests. One of the manual test scenarios (`stays_in_role`) verifies this.

---

## Utility Functions

### `utils/gcs_utils.py`

**`fetch_dual_instructions(agent_name: str) -> str`**
Fetches global + identity prompts from GCS, merges them with `DUAL_INSTRUCTION_DELIMITER`. Reads `GCS_BUCKET_NAME` and `GCS_BASE_FOLDER` from environment. Falls back to identity-only if global load fails. Returns error string if identity load fails.

**`fetch_instructions(agent_name: str) -> str`**
Fetches a single identity prompt from GCS. Older pattern used by `jarvis_agent` and `product_agent_rico_1`. GCS path: `{BASE}/{agent_name}/{agent_name}_instructions.txt`

**`write_gcs_file(bucket_name: str, file_path: str, content: str) -> None`**
Creates or overwrites a text file in GCS. Used by `write_session_memory`.

**`list_gcs_files(bucket_name: str, prefix: str) -> list[str]`**
Returns a list of blob names under a GCS prefix. Used by `read_session_memory`.

---

### `utils/token_calculator.py`

**`count_tokens(content: str, model: str = "gemini-2.5-flash") -> int`**
Counts tokens for a string using the Vertex AI token counting API. Requires `GOOGLE_CLOUD_PROJECT` env var. Raises `RuntimeError` on API failure.

**`estimate_cost(token_count: int, model: str, direction: str) -> float`**
Returns cost in USD. `direction` must be `"input"` or `"output"`. Raises `ValueError` for unknown models.

**`get_model_pricing(model: str) -> dict`**
Returns `{"input_per_1m": float, "output_per_1m": float, "context_window": int}` for a model.

**Supported models (9 total):**

| Model | Input $/1M | Output $/1M | Note |
|-------|-----------|------------|------|
| gemini-2.0-flash | $0.10 | $0.40 | Confirmed |
| gemini-2.0-flash-lite | $0.075 | $0.30 | Confirmed |
| gemini-2.5-flash | $0.15 | $0.60 | Confirmed |
| gemini-2.5-flash-lite | $0.075 | $0.30 | ESTIMATE |
| gemini-2.5-pro | $1.25 | $10.00 | Confirmed |
| gemini-3-flash-preview | $0.15 | $0.60 | ESTIMATE |
| gemini-3-pro-preview | $1.25 | $10.00 | ESTIMATE |
| gemini-3.1-pro-preview | $1.25 | $10.00 | ESTIMATE |
| gemini-3.1-flash-lite-preview | $0.075 | $0.30 | ESTIMATE |

ESTIMATE entries use the closest confirmed tier. Update when Google publishes official pricing.

---

### `utils/run_receipt.py`

**`create_receipt(agent_name, model, input_text, output_text, latency_ms, metadata=None) -> dict`**
Creates a receipt dict with 11 keys: timestamp, agent_name, model, input_tokens, output_tokens, total_tokens, input_cost_usd, output_cost_usd, total_cost_usd, latency_ms, metadata.

**`format_receipt(receipt: dict) -> str`**
Returns a human-readable multi-line string for terminal printing.

**`save_receipt_to_file(receipt: dict, filepath: str) -> None`**
Appends the receipt as a JSON line to a `.jsonl` file. Creates the file if it doesn't exist.

---

## Callbacks

Not FunctionTools, but part of the agent lifecycle. Defined in `callbacks/receipt_callback.py`.

**`get_start_time_callback() -> callable`**
Returns a `before_model_callback` that records `time.time()` in `callback_context.state["_run_start_time"]`. Must run before `get_receipt_callback` to provide the start time for latency calculation.

**`get_timestamp_inject_callback() -> callable`**
Returns a `before_model_callback` that:
1. Strips any existing `[SYSTEM_TIMESTAMP:]` line from the system instruction
2. Prepends a fresh `[SYSTEM_TIMESTAMP: {utc_iso}]` line

Prints `[timestamp_callback] [SYSTEM_TIMESTAMP: ...]` to terminal on every invocation. Watch for this line to confirm the callback is running.

**`get_receipt_callback(agent_name: str, model: str) -> callable`**
Returns an `after_model_callback` that:
1. Skips partial (streaming chunk) responses
2. Reads `_run_start_time` from session state
3. Extracts input/output text from callback context
4. Calls `create_receipt()` → `format_receipt()` → `save_receipt_to_file()`
5. On any error, prints a warning and continues without crashing the agent

---

*See `05_SKILLS_AND_CONTEXT.md` for the skills and context doc systems.*
