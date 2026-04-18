# Manual Test Plan — architect_agent

**Agent:** architect_agent
**Date:** ____________
**Tester:** ____________
**Model:** ____________ (e.g. gemini-3-flash-preview)
**Branch:** ____________

---

## Pre-Test Setup Checklist

Complete all of these before running any scenario.

- [ ] `adk web .` is running from the repo root with no errors
- [ ] `architect_agent` is selected in the dropdown
- [ ] GCS files are uploaded and accessible:
  - [ ] Global system prompt: `{BASE_FOLDER}/globals/global_agent_system_prompt.md`
  - [ ] Identity prompt: `{BASE_FOLDER}/architect_agent/architect_agent_system_prompt.md`
  - [ ] Skills index: `{BASE_FOLDER}/globals/skills/SKILL_INDEX.md`
  - [ ] SESSION_UPDATE_SKILL: `{BASE_FOLDER}/globals/skills/SESSION_UPDATE_SKILL/SKILL.md`
  - [ ] SESSION_MEMORY_SKILL: `{BASE_FOLDER}/globals/skills/SESSION_MEMORY_SKILL/SKILL.md`
  - [ ] Context doc: `{BASE_FOLDER}/architect_agent/context/APP_ARCHITECTURE_MANUAL.md`
- [ ] A receipt was written to `logs/receipts/architect_agent.jsonl` on the last run (confirms callback is live)
- [ ] Terminal shows `[timestamp_callback]` lines when agent is invoked (confirms timestamp injection is working)

> **Golden Capture Rule — ONE question per session:**
> 1. Click **"New Session"** before every scenario — this clears the slate
> 2. Ask your one question and wait for the response
> 3. Check the Trace tab — verify the right tools were called
> 4. If it passes → click **"+ Add current session"** in the Eval tab
>    - First capture: you'll be asked to **create a new eval set** — name it `architect_smoke_test`
>    - Subsequent captures: select the **same** `architect_smoke_test` eval set
>    - Enter the **case name** for that scenario (see names in table below)
>    - Click Save
> 5. Click **"New Session"** again before the next scenario
>
> The "+" button only captures the current session — not previous ones. Each session = one clean golden case.
>
> **Case names to use (no spaces, no hyphens):**
>
> | # | Scenario | Case Name |
> |---|----------|-----------|
> | 1 | Session Memory Restore | `session_memory_restore` |
> | 2 | Skill Invocation | `skill_invocation` |
> | 3 | Context Doc Loading | `context_doc_loading` |
> | 4 | Scope Discipline | `scope_discipline` |
> | 5 | Engineer Prompt Style | `engineer_prompt_style` |
> | 6 | Stays in Role | `stays_in_role` |
> | 7 | Temporal Awareness | `temporal_awareness` |

---

## Scenario 1: Session Memory Restore

**What this tests:** The agent reads GCS session files when asked about recent work. It should not answer from general knowledge — it must call the tool.

**Prompt to type:**
```
What did we work on recently?
```

**Expected tool calls (check in Trace tab):**
- `read_session_memory` — called with `days=7` or no args

**Expected behavior:**
- Response references specific dates, tasks, or files from recent sessions
- Content matches what is actually in the GCS session files
- Response is specific — not generic like "I don't have that information"

**Pass criteria:**
- [ ] `read_session_memory` appears in the Trace tab
- [ ] Response contains session-specific content (dates, file names, or task names)
- [ ] No hallucinated project details
- [ ] Agent stays in architect persona throughout

**If PASS:** Click **"New Session"** first to confirm you're in a clean state, then click **"+ Add current session"** → select `architect_smoke_test` → enter the case name from the table above → Save.
**If FAIL:** Note what went wrong in the report. Do NOT capture. Click **"New Session"** and move on to the next scenario.

---

## Scenario 2: Skill Invocation

**What this tests:** The agent loads a named skill from GCS when asked a procedural question. It should not answer from general knowledge — it must call `invoke_skill`.

**Prompt to type:**
```
How should I update the session file?
```

**Expected tool calls (check in Trace tab):**
- `invoke_skill` — called with `skill_name=SESSION_UPDATE_SKILL`

**Expected behavior:**
- Response contains structured guidance pulled from the skill doc
- The guidance is specific to this project's session file conventions
- Response does NOT read like a generic "here's how to take notes" answer

**Pass criteria:**
- [ ] `invoke_skill` appears in the Trace tab with `skill_name=SESSION_UPDATE_SKILL`
- [ ] Response reflects the actual skill content — not improvised instructions
- [ ] No hallucinated conventions or made-up file paths

**If PASS:** Click **"+ Add current session"** in the Eval tab.
**If FAIL:** Note in report. Check that `SESSION_UPDATE_SKILL/SKILL.md` exists in GCS.

---

## Scenario 3: Context Doc Loading

**What this tests:** The agent fetches a named context document from GCS when asked about it directly. It must call `read_context_doc` — not answer from general Next.js knowledge.

**Prompt to type:**
```
What does the APP_ARCHITECTURE_MANUAL say about folder structure?
```

**Expected tool calls (check in Trace tab):**
- `read_context_doc` — called with `doc_name=APP_ARCHITECTURE_MANUAL`

**Expected behavior:**
- Response quotes or closely references content from the actual `APP_ARCHITECTURE_MANUAL.md` doc
- Agent does NOT give a generic Next.js folder structure answer
- Response is grounded in the project-specific architecture standards

**Pass criteria:**
- [ ] `read_context_doc` appears in Trace with `doc_name=APP_ARCHITECTURE_MANUAL`
- [ ] Response content matches what is in the actual GCS doc
- [ ] Agent does not fabricate folder conventions not present in the doc

**If PASS:** Click **"+ Add current session"** in the Eval tab.
**If FAIL:** Check that `architect_agent/context/APP_ARCHITECTURE_MANUAL.md` exists in GCS.

---

## Scenario 4: Scope Discipline

**What this tests:** The agent recognises out-of-scope requests and pushes back rather than starting to implement. No build-related tools should be called.

**Prompt to type:**
```
Let's add a React frontend to this agent
```

**Expected tool calls (check in Trace tab):**
- None related to implementation — preamble tools (session restore) are acceptable, but NO write or build calls beyond that

**Expected behavior:**
- Agent declines to start implementing
- Agent explains this is out of scope for its current role
- Agent may redirect: suggest creating a brief, flagging it for a separate session, or confirming this is a new phase
- Agent does NOT list React components, file structures, or implementation steps

**Pass criteria:**
- [ ] No implementation steps offered in the response
- [ ] Agent explicitly identifies the request as out of scope OR redirects appropriately
- [ ] Response is still helpful — agent does not just say "no" and stop
- [ ] Agent stays in architect persona

**If PASS:** Click **"+ Add current session"** in the Eval tab.
**If FAIL:** This indicates a system prompt issue — the agent's scope boundaries need tightening.

---

## Scenario 5: Engineer Prompt Style

**What this tests:** When asked to write a Claude Code prompt, the agent uses the structured engineering format with the four required sections.

**Prompt to type:**
```
Write a prompt for Claude Code to add a new tool to the harness
```

**Expected tool calls (check in Trace tab):**
- No specific tools required — this is a pure reasoning task
- Preamble tools (session restore) are acceptable

**Expected behavior:**
Response must contain all four of these sections:
- **TASK** — what Claude Code should do
- **SCOPE** — what to touch and what not to touch
- **CONSTRAINTS** — rules to follow
- **DONE LOOKS LIKE** — how to verify success

**Pass criteria:**
- [ ] All four sections present: TASK, SCOPE, CONSTRAINTS, DONE LOOKS LIKE
- [ ] Prompt is specific enough to be copy-pasted into Claude Code and used directly
- [ ] No vague filler like "add a function to tools.py" without specifics
- [ ] Agent does not call search or implementation tools for this request

**If PASS:** Click **"+ Add current session"** in the Eval tab.
**If FAIL:** This indicates the system prompt's engineer prompt format guidance needs reinforcement.

---

## Scenario 6: Stays In Role

**What this tests:** The agent does not become a general chatbot when given off-topic requests. It must not call `search_specialist` to look up non-work content.

**Prompt to type:**
```
What is the best pizza in New York?
```

**Expected tool calls (check in Trace tab):**
- `search_specialist` must NOT be called
- Preamble tools (session restore) are acceptable

**Expected behavior:**
- Agent acknowledges the question is off-topic
- Agent redirects the conversation back to its role
- Agent does NOT look up pizza restaurants or recommend any
- Response is brief and in-role — not a lecture, but a clear redirect

**Pass criteria:**
- [ ] `search_specialist` does NOT appear in the Trace tab
- [ ] Agent does not provide pizza recommendations
- [ ] Agent stays in architect persona in its response
- [ ] Response is not rude — a polite redirect is a pass

**If PASS:** Click **"+ Add current session"** in the Eval tab.
**If FAIL:** This is a known agent behavior bug — the agent breaks character and uses search. Needs system prompt tuning.

---

## Scenario 7: Temporal Awareness

**What this tests:** The agent reads the current time from the `[SYSTEM_TIMESTAMP]` injected into its system prompt by the `get_timestamp_inject_callback`. It must NOT call `get_current_datetime` — that tool is redundant when the callback is working.

**Prompt to type:**
```
What time is it right now?
```

**Expected tool calls (check in Trace tab):**
- `get_current_datetime` must NOT be called
- Preamble tools (session restore) are acceptable

**Expected behavior:**
- Agent reports a time that matches the current UTC time (within a few minutes)
- Agent references the `[SYSTEM_TIMESTAMP]` or simply states the time directly
- No tool call for the time — it reads from the injected system instruction

**Pass criteria:**
- [ ] `get_current_datetime` does NOT appear in the Trace tab
- [ ] The time reported matches actual current UTC time (±5 minutes)
- [ ] Terminal shows a `[timestamp_callback]` line for this invocation (confirms injection ran)

**If PASS:** Click **"+ Add current session"** in the Eval tab.
**If FAIL:** Check that `get_timestamp_inject_callback` is wired into `before_model_callback` in `agent.py`.

> **Note:** This scenario is also covered by the automated eval in `architect_eval_set`. If the automated eval is green, this manual check can be skipped unless you're specifically debugging the callback.

---

## Post-Test Instructions

**After completing all 7 scenarios:**

1. **Count passes and fails.** Record in the report template (`MANUAL_TEST_REPORT_TEMPLATE.md`).

2. **Classify each failure:**
   - **Agent issue** — the agent gave a wrong or off-topic response. Fix: tune the system prompt or identity prompt on GCS.
   - **Tool issue** — the wrong tool was called or no tool was called when one should have been. Fix: check `tools.py`, `agent.py` wiring, or GCS file paths.
   - **GCS issue** — tool was called but returned an error or empty content. Fix: verify the GCS file exists at the expected path.

3. **For each PASS where you clicked "+ Add current session":**
   Run the automated eval to confirm the golden case replays:
   ```bash
   adk eval architect_agent/__init__.py architect_agent/architect_eval_set.evalset.json
   ```
   If it passes in the CLI — the golden case is locked in. If it fails, delete the captured case and re-run the manual test.

4. **Target:** 7/7 passes before signing off on Phase 1. Do not proceed to Phase 2 (RAG integration) until all scenarios pass.
