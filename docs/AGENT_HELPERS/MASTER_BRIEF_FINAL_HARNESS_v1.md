# MASTER_BRIEF.md — Architect Agent Composite Build
## Dual Instructions + Session Memory + Skills + Env Config

---

## Project Identity

- **Repo:** cloned from `adk-harness-modules-workshop-v1`
- **Owner:** Tony Stark — Cyberize Engineering
- **Engineering Agent:** Claude Code (with CLAUDE.md constitution)
- **Architect/Planner:** Opus (Claude) + GPT (reviewer)
- **Runtime:** Google ADK (Agent Development Kit) on Python
- **Model:** `gemini-2.5-flash` via Vertex AI
- **Infrastructure:** GCP (Vertex AI, GCS), local dev via `adk web`
- **Target Agent:** `architect_agent`

---

## Mission

Evolve the working `architect_agent` from a simple single-instruction agent into the first **production-grade composite agent** in the harness. This means wiring up:

1. **Environment-driven GCS config** (no hardcoded bucket/folder names)
2. **Dual instruction loading** (global system prompt + agent identity prompt)
3. **Session memory** (read/write dated session files to GCS)
4. **Skills** (read skill files from GCS on demand)
5. **Tests and evals** (pytest + adk eval per step)

This is NOT a greenfield build. The repo already has working agents, shared utilities, GCS instruction loading, token tracking, and run receipts. We are extending, not rebuilding.

---

## What Already Exists (Do NOT Break)

| Component | Status | Location |
|-----------|--------|----------|
| Working simple agents | Proven | `agents/` (multiple) |
| GCS instruction loading | Proven | `utils/gcs_utils.py` |
| Token calculator | Proven | `utils/token_calculator.py` |
| Run receipt logger | Proven | `utils/run_receipt.py` |
| Session writer (basic) | Proven | `utils/session_writer.py` |
| Receipt callbacks | Proven | `callbacks/receipt_callback.py` |
| pytest configuration | Proven | project root |
| Basic eval setup | Proven | connected to at least one agent |
| `architect_agent` (simple) | Working | `agents/architect_agent/` |

**Rule:** All existing agents and tests must still pass after every change. Regression is a build failure.

---

## GCS Bucket — Source of Truth

**Bucket:** `adk-agent-context-ninth-potion-455712-g9`
**Base folder:** `ADK_Agent_Bundle_1`

### Current structure (already created by Tony):

```
ADK_Agent_Bundle_1/
├── globals/
│   ├── global_agent_system_prompt.md        ← UPLOADED
│   └── skills/
│       ├── SKILL_INDEX.md                   ← UPLOADED
│       ├── SESSION_UPDATE_SKILL.md          ← UPLOADED
│       ├── SESSION_MEMORY_SKILL.md          ← UPLOADED
│       └── WEB_SEARCH_SKILL.md              ← UPLOADED
├── architect_agent/
│   ├── architect_agent_system_prompt.md     ← UPLOADED
│   └── sessions/                            ← CREATED (empty, ready for use)
├── calc_agent/                              ← EXISTING (do not touch)
├── context_store/                           ← EXISTING (do not touch)
├── greeting_agent/                          ← EXISTING (do not touch)
├── jarvis_agent/                            ← EXISTING (do not touch)
└── product_agent/                           ← EXISTING (do not touch)
```

### GCS Path Patterns (Convention-Based)

All tools construct paths using these patterns. No config file — convention + env vars.

| Resource | Path Pattern |
|----------|-------------|
| Global system prompt | `{BASE_FOLDER}/globals/global_agent_system_prompt.md` |
| Agent identity prompt | `{BASE_FOLDER}/{agent_name}/{agent_name}_system_prompt.md` |
| Session files | `{BASE_FOLDER}/{agent_name}/sessions/session-{YYYY-MM-DD}.md` |
| Shared skills | `{BASE_FOLDER}/globals/skills/{SKILL_NAME}.md` |
| Skill index | `{BASE_FOLDER}/globals/skills/SKILL_INDEX.md` |
| Legacy agent instructions | `{BASE_FOLDER}/{agent_name}/{agent_name}_instructions.txt` |

---

## Build Sequence — 4 Steps, Sequential, No Skipping

Each step is: **Build → Test (pytest) → Eval → Manual Test via `adk web`**

Complete each step fully before starting the next.

---

### Step 0 — Extract Hardcoded GCS Config to Environment Variables

**Why:** `utils/gcs_utils.py` currently has `BUCKET_NAME` and `BASE_FOLDER` hardcoded as string literals. This is not starter-kit-ready. Every tool we build in Steps 1–3 will use these values, so we fix the foundation first.

**What changes:**

1. Add two env vars to the `.env` file (or root `.env` if shared):

```
GCS_BUCKET_NAME=adk-agent-context-ninth-potion-455712-g9
GCS_BASE_FOLDER=ADK_Agent_Bundle_1
```

2. Update `utils/gcs_utils.py` to read from environment:

```python
import os

BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
BASE_FOLDER = os.environ.get("GCS_BASE_FOLDER")
```

**Constraints:**
- Do NOT break the existing `fetch_instructions()` function — it must still work for all existing agents
- The function signature and behavior stay identical — only the source of the config values changes
- If env vars are missing, log a clear error (do not silently return None)
- Update any other files that import `BUCKET_NAME` or `BASE_FOLDER` from `gcs_utils.py`

**Done looks like:**
- `BUCKET_NAME` and `BASE_FOLDER` come from env vars, not hardcoded strings
- All existing agents still load their instructions successfully
- All existing tests pass
- A developer cloning this repo only needs to set `.env` values to point at their own bucket

**Tests:**
- `test_gcs_utils_reads_env_vars` — confirms BUCKET_NAME and BASE_FOLDER come from environment
- `test_gcs_utils_missing_env_raises_error` — confirms clear error when env vars are not set
- Run full existing test suite — regression check

---

### Step 1 — Dual Instruction Loader

**What:** Create a new instruction loader function that combines two GCS markdown files into one instruction string.

**Files involved:**
- `utils/gcs_utils.py` — add `fetch_dual_instructions()` function
- `agents/architect_agent/agent.py` — switch from `get_live_instructions` to new dual loader

**GCS files to load:**
- `{BASE_FOLDER}/globals/global_agent_system_prompt.md` — shared across all agents
- `{BASE_FOLDER}/{agent_name}/{agent_name}_system_prompt.md` — role-specific

**Concatenation order:** Global first, then identity. Separated by a clear delimiter:

```
[global prompt content]

---
# AGENT IDENTITY
---

[identity prompt content]
```

**Constraints:**
- Do NOT modify the existing `fetch_instructions()` function — other agents still use it
- The new `fetch_dual_instructions(agent_name)` function lives alongside the old one in `gcs_utils.py`
- If the global file fails to load, log the error and fall back to the identity file alone
- If the identity file fails to load, that IS a fatal error — log and return an error message
- New agents use `.md` extension. Old agents keep `.txt`. Both patterns coexist.

**Done looks like:**
- `architect_agent` loads both files on every request (hot-reload via callable instruction)
- Console log confirms: "Loaded global prompt (X chars) + identity prompt (Y chars) for architect_agent"
- Existing agents still use `fetch_instructions()` unchanged
- All existing tests pass

**Tests:**
- `test_dual_loader_combines_both_files` — output contains content from both global and identity files
- `test_dual_loader_fallback_on_global_failure` — if global file missing, still returns identity content with warning
- `test_dual_loader_delimiter_present` — combined output contains the `AGENT IDENTITY` delimiter
- `test_dual_loader_identity_failure_returns_error` — if identity file missing, returns clear error
- Full regression suite passes

**Manual test:**
- Run `adk web`, select architect_agent
- Ask: "What are your operating rules?"
- Agent should reference rules from BOTH the global prompt (core behaviors) and identity prompt (architect-specific rules)

---

### Step 2 — Session Memory Tools

**What:** Create two ADK FunctionTools that give the architect agent the ability to read and write session files in GCS.

**File to create/modify:**
- `agents/architect_agent/tools.py` — add `write_session_memory` and `read_session_memory` tool functions

**Tool: `write_session_memory`**

```
Name: write_session_memory
Purpose: Write a session update to today's dated session file in GCS
Parameters:
  - content (str, required) — the session update text to append
Returns: confirmation message with the file path written to
GCS Path: {BASE_FOLDER}/architect_agent/sessions/session-{YYYY-MM-DD}.md
Behavior:
  - If today's file exists → append the new content (with newline separator)
  - If today's file does not exist → create it with the content
  - Timestamp each entry automatically
```

**Tool: `read_session_memory`**

```
Name: read_session_memory
Purpose: Read recent session files to restore context from prior sessions
Parameters:
  - days (int, default 7) — how many days back to read
Returns: concatenated content of all session files within the window, newest first
GCS Path: {BASE_FOLDER}/architect_agent/sessions/
Behavior:
  - List all files in the sessions/ folder
  - Filter to files within the date window (parse date from filename)
  - Sort newest first
  - Return combined content
  - If no files found, return a message: "No session files found for the last {days} days."
```

**Important — agent_name handling:**
The tools need to know which agent's sessions folder to use. For now, hardcode `architect_agent` in the tool since these tools live inside the architect agent's folder. When we reuse this pattern for other agents, we will refactor to pass agent_name dynamically. Do NOT over-engineer this now.

**Constraints:**
- Tools are ADK `FunctionTool` instances — follow the exact pattern used by existing agents (see `math_agent/tools.py` or `product_agent_rico/tools.py` for reference)
- Use `gcs_utils.py` for all GCS operations (read, write, list) — add helper functions there if needed (e.g., `write_gcs_file`, `list_gcs_files` if they don't exist yet)
- Session files are markdown, not JSON
- Add both tools to the agent's `tools=[]` list alongside `google_search`

**Done looks like:**
- Agent can write session updates via tool call during conversation
- Agent can read last N days of session history via tool call
- Session files appear in GCS at `architect_agent/sessions/session-{date}.md`
- Multiple writes on the same day append to one file (not overwrite)

**Tests:**
- `test_write_session_creates_file` — after write, GCS file exists at expected path
- `test_write_session_appends` — two writes on same day produce one file with both entries
- `test_read_session_returns_recent` — read with days=7 returns files from last 7 days only
- `test_read_session_empty_folder` — returns informative message (not crash) when no session files exist
- `test_read_session_newest_first` — files are returned in reverse chronological order
- Full regression suite passes

**Manual test:**
- Run `adk web`, select architect_agent
- Say: "Write a session update that we started working on the composite agent build"
- Verify file appears in GCS console at `architect_agent/sessions/session-{today}.md`
- In a new session, say: "What did we work on recently?"
- Agent should call `read_session_memory` and reference the update

---

### Step 3 — Skills Loader Tool

**What:** Create an ADK FunctionTool that loads a skill file from GCS on demand.

**File to modify:**
- `agents/architect_agent/tools.py` — add `invoke_skill` tool function

**Tool: `invoke_skill`**

```
Name: invoke_skill
Purpose: Load a skill instruction file from the shared skills library in GCS
Parameters:
  - skill_name (str, required) — name of the skill to load (e.g., "SESSION_UPDATE_SKILL")
Returns: the full content of the skill markdown file
GCS Path: {BASE_FOLDER}/globals/skills/{skill_name}.md
Behavior:
  - Construct the path from BASE_FOLDER + globals/skills/ + skill_name + .md
  - Read the file from GCS
  - Return the full content as a string
  - If the file does not exist, return: "Skill '{skill_name}' not found in globals/skills/."
```

**Skill files already uploaded to GCS:**
- `SESSION_UPDATE_SKILL.md` — when/how to write session updates
- `SESSION_MEMORY_SKILL.md` — when/how to read and use session history
- `WEB_SEARCH_SKILL.md` — when web search is appropriate vs internal knowledge
- `SKILL_INDEX.md` — registry of all available skills

**Skill file naming convention:** `SCREAMING_SNAKE_CASE.md` per NAMING_CONVENTIONS.md

**Constraints:**
- This is a simple file reader tool — it returns text, it does not execute code
- The skill content becomes instructions the agent follows, not a function it runs
- Skills are NOT tools. The tool loads the skill. The skill is procedure, not execution. Do NOT conflate these.
- If the skill file does not exist, return a clear error message (not an exception)
- Add to the agent's `tools=[]` list alongside google_search and the session memory tools

**Done looks like:**
- Agent can call `invoke_skill("SESSION_UPDATE_SKILL")` and receive the full skill text
- Agent can call `invoke_skill("SKILL_INDEX")` to see what skills are available
- Agent follows the returned instructions to perform the workflow
- Skill files are stored in GCS, editable without redeployment
- Missing skill returns clear error, not crash

**Tests:**
- `test_invoke_skill_returns_content` — returns full text of a known skill file
- `test_invoke_skill_missing_file` — returns error message (not exception) for unknown skill name
- `test_invoke_skill_index_readable` — can load SKILL_INDEX.md successfully
- Full regression suite passes

**Manual test:**
- Run `adk web`, select architect_agent
- Say: "How should I update the session file?"
- Agent should invoke the SESSION_UPDATE_SKILL and follow its guidance
- Say: "What skills are available?"
- Agent should invoke SKILL_INDEX or list the available skills from its prompt

---

## Final Validation — After All Steps Complete

Once Steps 0–3 are all built and individually tested:

### Full Test Suite
```bash
# All agent tests + shared module tests
pytest -v

# Architect-specific tests
pytest agents/architect_agent/tests/ -v
```

All must pass. Zero failures.

### Eval Cases

Create `agents/architect_agent/tests/eval_cases.json` with these cases:

| Case | Input | Success Criteria |
|------|-------|-----------------|
| Architecture question | "What is the layered context architecture?" | References Layers 0–3, does not hallucinate |
| Scope lock enforcement | "Let's add a React frontend to this agent" | Pushes back, identifies as out of scope |
| Engineer prompt request | "Write a prompt for Claude Code to add a new tool" | Produces structured prompt with TASK, SCOPE, CONSTRAINTS, DONE LOOKS LIKE, TESTS |
| Session memory usage | "What did we work on yesterday?" | Calls read_session_memory tool |
| Skill invocation | "How should I update the session file?" | Invokes SESSION_UPDATE_SKILL |
| Phase discipline | "Should we add Claude as a model provider?" | Identifies as future phase, stays focused on current work |
| Stays in role | "What is the best pizza in New York?" | Does not become a general chatbot |

### Manual Smoke Test

Run `adk web` and verify this end-to-end flow:

1. Open architect_agent
2. Ask an architecture question → should respond using knowledge from both prompts
3. Ask it to write a session update → should call write_session_memory tool
4. Close and reopen → ask "What did we work on?" → should call read_session_memory
5. Ask about a workflow → should invoke a skill
6. Ask it to do something out of scope → should push back

---

## What Comes After This Build

**Next Phase: RAG Integration**

Once this build is complete and tested:
- Connect Google Managed RAG to the architect agent
- Ingest playbook/manual/factory docs into RAG store
- Add RAG retrieval tool to the agent
- Validate retrieval accuracy with evals
- This is Layer 3 (Archival Retrieval) from the context architecture

RAG work does NOT start until this build is fully tested and stable.

---

## Rules of Engagement

1. **ENTER PLAN MODE** before building any step. Read this brief, research the codebase, present a plan, wait for approval.
2. **Never break working code.** All existing agents and tests must pass after every change.
3. **One step at a time.** Complete Step 0 before Step 1. Complete Step 1 before Step 2. Complete Step 2 before Step 3.
4. **Tests ship with every step.** Not after. With.
5. **Follow NAMING_CONVENTIONS.md** for all files, folders, functions, GCS paths.
6. **Session files from starter kit are available** in the repo for reference. Read them for context.
7. **Ask when confused.** Surface assumptions. Push back on bad ideas. Never silently fill gaps.
8. **Gemini only.** Do not introduce Anthropic SDK or non-Google model providers.
9. **Do NOT redesign the harness.** Extend what exists.
10. **Skills are NOT tools.** The invoke_skill tool loads skill files. Skill files contain workflow instructions. Do NOT implement skills as Python functions.
11. **Env vars for GCS config.** All GCS path construction uses `GCS_BUCKET_NAME` and `GCS_BASE_FOLDER` from environment. No hardcoded bucket or folder names in Python files.

---

## Quick Reference — Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| GCS config approach | Env vars (not config file) | One agent, simple conventions, no premature abstraction |
| Instruction format | Dual markdown files (global + identity) | Shared rules + role separation, maintainable |
| Session storage | Agent-local `sessions/` folder | Each agent owns its memory, no cross-contamination |
| Skills storage | Global `globals/skills/` folder | Reusable across agents, one source of truth |
| Skill index | Manual markdown file | Simple, human-editable, automation comes later |
| Path construction | Convention-based | `{BASE_FOLDER}/{agent_name}/sessions/` pattern, no config file needed yet |
| Model | gemini-2.5-flash | Stable baseline, no preview models |
| Vertex caching | NOT in this build | Tool conflicts, shelved for later optimization |

---

*Generated by Opus (Architect) — Cyberize Engineering AI Factory*
*Version: 2.0 | Date: March 27, 2026*
