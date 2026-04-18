# 09 — Operations

**ADK Agent Harness v1**

---

## Starting the Dev UI

```bash
# From the repo root
source .venv/bin/activate
adk web .
```

- Opens at `http://localhost:8000`
- Select an agent from the dropdown
- The `.env` file in that agent's folder is loaded automatically
- Changes to GCS prompts take effect on the next message — no restart needed

**What to watch for in the terminal on startup:**
```
INFO: Started server process [...]
INFO: Application startup complete.
```

**What to watch for on each agent invocation:**
```
[timestamp_callback] [SYSTEM_TIMESTAMP: 2026-04-14T12:30:00Z]
Loaded global prompt (2451 chars) for architect_agent.
Loaded identity prompt (3102 chars) for architect_agent.
Session memory written to: gs://...
─── Run Receipt ───
Agent:   architect_agent
Model:   gemini-3-flash-preview
Tokens:  1842 in / 412 out / 2254 total
Cost:    $0.000338
Latency: 3241ms
Time:    2026-04-14T12:30:05Z
────────────────────
```

If `[timestamp_callback]` is missing → callback is not running. Check `before_model_callback` in `agent.py`.
If receipt is missing → `get_receipt_callback` is not running. Check `after_model_callback` in `agent.py`.

---

## Environment Setup

### Local Development (ADC)

```bash
# One-time setup
gcloud auth application-default login
gcloud config set project ninth-potion-455712-g9

# Verify
gcloud auth application-default print-access-token
```

### Per-Agent `.env` File

Each agent has its own `.env` file in its folder. For `architect_agent`:

```bash
# architect_agent/.env

GOOGLE_GENAI_USE_VERTEXAI=TRUE          # Required — routes to Vertex AI
GCS_BUCKET_NAME=adk-agent-context-ninth-potion-455712-g9
GCS_BASE_FOLDER=ADK_Agent_Bundle_1
```

`GOOGLE_GENAI_USE_VERTEXAI=TRUE` must be set before any ADK imports. `adk web .` handles this automatically when loading the `.env`.

---

## GCS File Management

### Viewing and Editing GCS Files

Use the GCS Cloud Console or `gsutil`:

```bash
# List files in the agent's GCS folder
gsutil ls gs://adk-agent-context-ninth-potion-455712-g9/ADK_Agent_Bundle_1/architect_agent/

# Download a prompt for editing
gsutil cp gs://adk-agent-context-ninth-potion-455712-g9/ADK_Agent_Bundle_1/globals/global_agent_system_prompt.md .

# Upload an edited prompt
gsutil cp global_agent_system_prompt.md gs://adk-agent-context-ninth-potion-455712-g9/ADK_Agent_Bundle_1/globals/global_agent_system_prompt.md

# Upload a new context doc
gsutil cp MY_NEW_DOC.md gs://adk-agent-context-ninth-potion-455712-g9/ADK_Agent_Bundle_1/architect_agent/context/MY_NEW_DOC.md
```

### Adding a New Skill

1. Create the skill document locally
2. Upload to GCS: `gsutil cp SKILL.md gs://{bucket}/{base}/globals/skills/{SKILL_NAME}/SKILL.md`
3. Update `SKILL_INDEX.md` in GCS: add one line for the new skill
4. The agent can use it immediately — no code change, no restart

### Adding a New Context Doc

1. Create the document locally as markdown
2. Upload to GCS: `gsutil cp MY_DOC.md gs://{bucket}/{base}/architect_agent/context/MY_DOC.md`
3. If a `CONTEXT_INDEX.md` exists, add an entry
4. The agent can use it immediately

---

## Usage Reporting

```bash
# Today's usage (defaults to current UTC date)
python scripts/usage_report.py

# Specific date
python scripts/usage_report.py --date 2026-04-14
```

**Output:**
```
=== DAILY USAGE REPORT: 2026-04-14 ===

AGENT                      RUNS    IN TOKENS   OUT TOKENS   TOTAL COST
------------------------------------------------------------------------
architect_agent               4        7,234        1,628   $0.002054
------------------------------------------------------------------------
TOTAL                         4        7,234        1,628   $0.002054

Report saved → reports/usage_reports/usage_report_2026-04-14_12-30-45.txt
```

**How it works:** Reads all `.jsonl` files in `logs/receipts/`, filters receipts by date, aggregates by agent name. Reports are also saved to `reports/usage_reports/`.

**Important:** Receipts are only written when an agent is invoked. If you run `usage_report.py` before making any agent calls today, you'll see "No usage data found for today" — this is expected behavior, not a bug.

---

## Reading Receipts

Raw receipt data is in `logs/receipts/{agent_name}.jsonl`. One JSON object per line:

```json
{
  "timestamp": "2026-04-14T12:30:05Z",
  "agent_name": "architect_agent",
  "model": "gemini-3-flash-preview",
  "input_tokens": 1842,
  "output_tokens": 412,
  "total_tokens": 2254,
  "input_cost_usd": 0.000276,
  "output_cost_usd": 0.000247,
  "total_cost_usd": 0.000338,
  "latency_ms": 3241.0,
  "metadata": {}
}
```

To inspect the last few entries:
```bash
tail -5 logs/receipts/architect_agent.jsonl | python -m json.tool
```

---

## Running Tests

```bash
# Unit tests only
pytest -m unit

# All tests (including integration — requires live GCS)
pytest

# Specific file with verbose output
pytest tests/test_token_calculator.py -v

# Show print output
pytest -m unit -s
```

---

## Session File Maintenance (Local)

Claude Code session files in the repo root (`session_YYYY-MM-DD.md`) accumulate over time. These are working notes — not GCS files. Periodically check them and update "End of Session State" and "Next Steps" sections if Claude Code left them as TBD.

To find sessions with incomplete end state:
```bash
grep -l "TBD" session_*.md
```

---

## Changelog Protocol

After any significant change — feature, fix, refactor, prompt update — add an entry:

**In `CHANGELOG.md` (repo root):**
```markdown
## YYYY-MM-DD HH:MM UTC — [CC] Claude Code
- **Updated:** `filename.md` — what changed and why
- **Reason:** what triggered this update
```

**In `docs/change_logs/change_log_YYYY-MM-DD_HHMM.md`:**
For major releases or end-of-session summaries, create a dated file with a full changelog entry. See `docs/change_logs/change_log_2026-04-14_0000.md` as the reference format.

Use `[CC]` for Claude Code changes, `[TS]` for Tony Stark manual edits.

---

## Deploying to Cloud Run

```bash
# Build and deploy
./deploy.sh

# Or manually
gcloud run deploy architect-agent \
  --source . \
  --region us-central1 \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GCS_BUCKET_NAME=...,GCS_BASE_FOLDER=...
```

The `Dockerfile` uses shell-form CMD for `$PORT` expansion. Service account auth replaces ADC in production — attach the service account to the Cloud Run service via `cyberize-vertex-api.json`.

---

## Common Issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| "GCS_BUCKET_NAME not set" | `.env` not loaded | Confirm `.env` is in the agent folder, not repo root |
| "Unknown model" in receipt | Model not in `_PRICING` | Add to `utils/token_calculator.py` |
| Agent reads stale timestamp | Old `append_instructions` pattern | Confirm `get_timestamp_inject_callback` is in `before_model_callback` list |
| No `[timestamp_callback]` line | Callback not wired | Check `before_model_callback=[get_start_time_callback(), get_timestamp_inject_callback()]` |
| `adk web` can't find agent | `root_agent` not exported | Check `__init__.py` has `from .agent import root_agent` |
| Eval always fails | `tool_trajectory_avg_score: 1.0` + reasoning agent | Use golden capture via "Add current session" instead of hand-written trajectories |
| "Eval module not installed" | `google-adk[eval]` missing | `pip install "google-adk[eval]"` |

---

*This document covers day-to-day operations. See `01_ARCHITECTURE.md` for system design context.*
