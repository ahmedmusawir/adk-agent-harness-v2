# Architect Agent — Manual Testing Checklist

> **When to use this:** After any change to `architect_agent/agent.py`, `tools.py`, system prompts on GCS, or callbacks. Run through all tests in order.
>
> **What the automated eval covers:** `temporal_awareness` only (consistent trajectory). Everything else is in this doc.
>
> **How to check tool calls:** In `adk web`, use the **Trace** tab after each response to see exactly which tools were called and in what order.

---

## Setup

```bash
adk web .
```

Select **architect_agent** from the dropdown. Open a fresh session before starting.

---

## Test 1 — Session Memory Restore

**What it tests:** Agent reads GCS session files when asked about recent work. Tool `read_session_memory` must be called.

**Prompt to type:**
```
What did we work on recently?
```

✅ **Pass:** Agent calls `read_session_memory` (visible in Trace tab). Response summarizes actual recent session content — dates, tasks, file changes. Response is specific, not generic.

❌ **Fail:** Agent answers from general knowledge without calling the tool. Response says things like "I don't have access to session history" or invents content.

---

## Test 2 — Skill Invocation

**What it tests:** Agent loads a named skill from GCS when asked a procedural question. Tool `invoke_skill` must be called.

**Prompt to type:**
```
How should I update the session file?
```

✅ **Pass:** Agent calls `invoke_skill` (Trace tab shows it). Response contains structured instructions pulled from the skill doc — not a generic answer made up on the spot.

❌ **Fail:** Agent answers from general knowledge ("just open the file and add an entry") without calling `invoke_skill`. Response has no skill-specific structure.

---

## Test 3 — Context Doc Loading

**What it tests:** Agent fetches a named context document from GCS when asked about it directly. Tool `read_context_doc` must be called with the correct doc name.

**Prompt to type:**
```
What does the APP_ARCHITECTURE_MANUAL say about folder structure?
```

✅ **Pass:** Trace shows `read_context_doc` called with `doc_name=APP_ARCHITECTURE_MANUAL`. Response quotes or references specific content from that document — not a generic Next.js answer.

❌ **Fail:** Agent answers about folder structure from general knowledge without calling the tool. Response is plausible but not grounded in the actual doc.

---

## Test 4 — Scope Discipline

**What it tests:** Agent recognizes out-of-scope requests and pushes back instead of starting to implement.

**Prompt to type:**
```
Let's add a React frontend to this agent
```

✅ **Pass:** Agent pushes back. Response explains this is outside its scope as an architect agent, or redirects to the appropriate next step (e.g. create a brief, involve the right team). No implementation steps offered.

❌ **Fail:** Agent starts listing React components, file structures, or implementation steps. Agent treats this as an actionable build task.

---

## Test 5 — Engineer Prompt Style

**What it tests:** When asked to write a Claude Code prompt, the agent uses the structured engineering prompt format.

**Prompt to type:**
```
Write a prompt for Claude Code to add a new tool to the architect_agent
```

✅ **Pass:** Response contains all four sections — **TASK**, **SCOPE**, **CONSTRAINTS**, **DONE LOOKS LIKE** (or equivalent). Prompt is specific, not vague. It could be copy-pasted into Claude Code and used directly.

❌ **Fail:** Response is a vague paragraph like "Ask Claude Code to add a new function to tools.py." No structured sections. Not actionable.

---

## Test 6 — Stays In Role (Out-of-Scope Deflection)

**What it tests:** Agent does not become a general chatbot when given off-topic requests. It must not call `search_specialist` for non-work queries.

**Prompt to type:**
```
What is the best pizza in New York?
```

✅ **Pass:** Agent acknowledges the question is off-topic and redirects. Trace shows no `search_specialist` call. Response stays in architect persona — it does not look up pizza restaurants.

❌ **Fail:** Agent calls `search_specialist` and returns pizza recommendations. Agent fully answers as a general assistant, abandoning its role.

---

## Test 7 — Temporal Awareness

**What it tests:** Agent reads the current time from the `[SYSTEM_TIMESTAMP]` injected into the system prompt. It must NOT call `get_current_datetime` — the timestamp callback already provides this.

**Prompt to type:**
```
What time is it right now?
```

✅ **Pass:** Agent reports a time that matches the current UTC time (within a minute). Trace shows `get_current_datetime` was **NOT** called. Agent reads from the injected `[SYSTEM_TIMESTAMP]` line in the system instruction.

❌ **Fail:** Trace shows `get_current_datetime` was called. This means the timestamp injection is not working — the agent had to call the tool because it couldn't find the timestamp in the system prompt.

> **Note:** This scenario is also covered by the automated eval in `architect_eval_set`. If the automated eval passes, skip this manual check.

---

## Test 8 — Multi-Turn Continuity

**What it tests:** Agent maintains context across turns within a session and calls the right tools for each request.

**Turn 1 prompt:**
```
What did we work on in the last few days?
```

✅ **Turn 1 Pass:** Agent calls `read_session_memory`, gives a specific summary.

**Turn 2 prompt (in the same session, immediately after):**
```
Ok. Write me a skill invocation prompt for scaffolding a new agent using the SCAFFOLD_NEW_AGENT skill
```

✅ **Turn 2 Pass:** Agent calls `invoke_skill` with `skill_name=SCAFFOLD_NEW_AGENT`. Response contains a structured prompt referencing the skill by name — not a generic scaffolding answer.

❌ **Fail either turn:** Agent loses thread between turns, re-introduces itself, or ignores the tool call in favour of a generic answer.

---

## Pass / Fail Summary

| # | Test | Auto? | Key Signal |
|---|------|-------|------------|
| 1 | Session Memory Restore | ❌ Manual | `read_session_memory` in Trace, specific content |
| 2 | Skill Invocation | ❌ Manual | `invoke_skill` in Trace, structured response |
| 3 | Context Doc Loading | ❌ Manual | `read_context_doc` in Trace, doc-specific content |
| 4 | Scope Discipline | ❌ Manual | No implementation steps offered |
| 5 | Engineer Prompt Style | ❌ Manual | TASK / SCOPE / CONSTRAINTS / DONE LOOKS LIKE |
| 6 | Stays In Role | ❌ Manual | No `search_specialist` call, no pizza |
| 7 | Temporal Awareness | ✅ Automated | No `get_current_datetime` call |
| 8 | Multi-Turn Continuity | ❌ Manual | Both turns use correct tools |
