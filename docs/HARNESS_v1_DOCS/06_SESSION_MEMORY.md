# 06 — Session Memory

**ADK Agent Harness v1**

---

## What Session Memory Is

Session memory is `architect_agent`'s ability to remember work done in previous conversations. It is not ADK's built-in session service (which only holds the current conversation's turn history). It is a separate, persistent system built on top of GCS.

**ADK session service** = conversation turn history, lives in RAM during a session, gone when `adk web` restarts.

**GCS session memory** = dated markdown files, persists indefinitely, readable across sessions, conversations, and restarts.

These are two different things. GCS session memory is what gives the agent continuity across days.

---

## How It Works

At the start of a session, the agent calls `read_session_memory` to pull in recent work. During and at the end of a session, it calls `write_session_memory` to record what happened.

```
New session starts
       ↓
Agent calls read_session_memory(days=7)
       ↓
GCS returns content of session-2026-04-14.md,
session-2026-04-03.md, session-2026-04-02.md, ...
(newest first, up to 7 days back)
       ↓
Agent now knows: what was worked on, what was broken,
what comes next, what tools exist, key decisions made
       ↓
Work happens...
       ↓
Agent calls write_session_memory(content)
       ↓
Content appended to today's GCS session file
with a UTC timestamp header
```

---

## GCS Session File Structure

**Path:** `{BASE}/{agent_name}/sessions/session-YYYY-MM-DD.md`

**Example:** `ADK_Agent_Bundle_1/architect_agent/sessions/session-2026-04-14.md`

**File format:** Standard markdown. Each `write_session_memory` call appends a section:

```markdown
## 2026-04-14 14:32 UTC
[whatever the agent wrote here]

## 2026-04-14 15:10 UTC
[next update]
```

The file accumulates entries throughout the day. All entries for a given UTC date land in the same file.

---

## write_session_memory — Behavior Detail

```python
write_session_memory(content: str) -> str
```

1. Determines today's UTC date → filename: `session-YYYY-MM-DD.md`
2. Constructs the full GCS path: `{BASE}/architect_agent/sessions/session-YYYY-MM-DD.md`
3. Reads existing file content (empty string if file doesn't exist)
4. Appends `\n## {timestamp}\n{content}\n`
5. Writes the full updated content back to GCS
6. Returns a confirmation string with the GCS path

**Key behavior:** This is append-only from the agent's perspective. It reads the full existing content and writes it back with the new entry added. The GCS blob is always overwritten with the complete accumulated content.

**Side effects:** One GCS read + one GCS write per call. Prints path to stdout.

---

## read_session_memory — Behavior Detail

```python
read_session_memory(days: int = 7) -> str
```

1. Constructs the sessions prefix: `{BASE}/architect_agent/sessions/`
2. Lists all blobs under that prefix
3. Filters to blobs matching `session-YYYY-MM-DD.md` pattern
4. Filters to files where date >= (today - `days` days)
5. Sorts matched files newest-first
6. Downloads each file and concatenates content
7. Returns all sections joined by `\n\n---\n\n`, each labeled `# Session: YYYY-MM-DD`

**What it returns when nothing is found:** `"No session files found for the last {days} days."`

**Side effects:** Multiple GCS reads (list + download per file). Read-only — no writes.

---

## The Local Session Files vs. GCS Session Files

There are two types of session logs in this project — don't confuse them:

| Type | Location | Written by | Read by |
|------|----------|-----------|---------|
| Local session log | `session_YYYY-MM-DD.md` in repo root | Claude Code (human-readable notes) | Human (Tony, Claude Code at start of session) |
| GCS session memory | `{BASE}/architect_agent/sessions/session-YYYY-MM-DD.md` | `architect_agent` via `write_session_memory` | `architect_agent` via `read_session_memory` |

The local files in the repo root are Claude Code's working notes — they are not part of the agent system. The GCS files are what the agent reads and writes during its operation.

---

## Session Memory in the Agent's Preamble

`architect_agent`'s system prompt instructs it to call `read_session_memory` at the start of most sessions. This is a preamble step — it runs before the agent responds to the user's actual question.

This preamble is a known source of non-determinism in evals: sometimes the agent also calls `write_session_memory` early (if it detects a new day), and sometimes it skips the preamble for simple questions. Manual testing is the right way to verify this behavior — see `08_TESTING_AND_EVALS.md`.

---

## Context Limit Consideration

`read_session_memory` returns raw text from GCS files. Long-running projects accumulate large session files. The 7-day window caps the volume, but individual files can grow large.

If session files become too large:
- The agent's context fills up with history
- Tool call latency increases
- Consider reducing `days` or summarizing old session entries

This is not a current problem, but worth knowing for longer-running projects.

---

## Debugging Session Memory

**Agent answers "I don't know" about recent work:**
→ Check `read_session_memory` appears in the Trace tab
→ Check GCS session files exist at the expected path
→ Confirm `GCS_BUCKET_NAME` and `GCS_BASE_FOLDER` env vars are set

**Session writes not persisting:**
→ Check `write_session_memory` appears in the Trace tab
→ Confirm IAM permissions on the GCS bucket allow writes
→ Check the terminal for GCS error output

**Receipt file says `architect_agent.jsonl` has entries but no session file:**
→ Receipts are written locally on every run; session memory is only written when the agent calls the tool
→ The agent may not have called `write_session_memory` for that run — check the Trace tab

---

*See `07_PROMPTS.md` for the prompt architecture.*
