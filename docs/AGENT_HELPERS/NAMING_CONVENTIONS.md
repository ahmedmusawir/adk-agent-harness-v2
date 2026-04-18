# NAMING_CONVENTIONS.md — ADK Harness Modules Workshop v1
## Naming Rules for Files, Folders, Classes, Variables, and Infrastructure

---

## Purpose

This document defines naming conventions for EVERYTHING in the project. Claude must read this before writing any code. Consistency across agents, utilities, tests, GCS paths, and documentation is non-negotiable.

**Rule:** If it's not in this doc, ask Tony before inventing a convention.

---

## Python Code

### Files & Modules

| Type | Convention | Example |
|------|-----------|---------|
| Agent folders | `snake_case` | `product_agent/`, `skills_agent/` |
| Python files | `snake_case.py` | `agent.py`, `tools.py`, `prompt.py` |
| Utility files | `snake_case.py` | `token_calculator.py`, `run_receipt.py` |
| Test files | `test_<module>.py` | `test_tools.py`, `test_agent.py`, `test_token_calculator.py` |
| Init files | `__init__.py` | Always present in every package |

### Classes & Functions

| Type | Convention | Example |
|------|-----------|---------|
| Agent classes | `PascalCase` + `Agent` suffix | `ProductAgent`, `SkillsAgent`, `JarvisRagAgent` |
| Dataclasses | `PascalCase` | `RunReceipt`, `TokenCount`, `SessionEntry` |
| Functions | `snake_case` | `count_tokens()`, `create_receipt()`, `read_gcs_file()` |
| Tool functions | `snake_case` + descriptive verb | `get_product_list()`, `search_documents()`, `write_session()` |
| Constants | `SCREAMING_SNAKE_CASE` | `DEFAULT_MODEL`, `GCS_BUCKET_NAME`, `MAX_SESSION_AGE_DAYS` |
| Private functions | `_snake_case` | `_parse_response()`, `_validate_input()` |

### Variables

| Type | Convention | Example |
|------|-----------|---------|
| Local variables | `snake_case` | `token_count`, `agent_name`, `receipt_data` |
| Function parameters | `snake_case` | `model_name: str`, `content: str` |
| Boolean variables | `is_` or `has_` prefix | `is_cached`, `has_session`, `is_valid` |

---

## ADK-Specific Naming

### Agent Registration (root `__init__.py`)

Agents are registered in the root `__init__.py` for `adk web` discovery. The key is the agent's folder name:

```python
from agents.product_agent.agent import product_agent
from agents.rico_cached.agent import rico_cached_agent
```

### Agent Instance Names

The agent instance variable should match the folder name with `_agent` suffix:

| Folder | Instance Variable | Display Name (in adk web) |
|--------|------------------|--------------------------|
| `product_agent/` | `product_agent` | `product_agent` |
| `rico_cached/` | `rico_cached_agent` | `rico_cached` |
| `skills_agent/` | `skills_agent` | `skills_agent` |
| `jarvis_rag/` | `jarvis_rag_agent` | `jarvis_rag` |

### Session State Keys

| Convention | Example |
|-----------|---------|
| `dot.notation` for nested concepts | `session.state["mode"]`, `session.state["token_count"]` |
| `snake_case` for simple keys | `session.state["last_skill"]`, `session.state["turn_count"]` |
| Prefix with domain for clarity | `session.state["cache.is_active"]`, `session.state["skill.current"]` |

---

## GCS Paths

### Bucket Structure

All paths follow: `{bucket}/ADK_Agent_Bundle_1/{agent_name}/{type}/{filename}`

| Type | Path Pattern | Example |
|------|-------------|---------|
| Context files | `ADK_Agent_Bundle_1/{agent}/context/{file}` | `ADK_Agent_Bundle_1/rico/context/system_prompt.md` |
| Instructions | `ADK_Agent_Bundle_1/{agent}/{agent}_instructions.txt` | `ADK_Agent_Bundle_1/jarvis_agent/jarvis_agent_instructions.txt` |
| Session files | `ADK_Agent_Bundle_1/{agent}/sessions/{file}` | `ADK_Agent_Bundle_1/rico/sessions/tony_2026-03-03.json` |
| Run receipts | `ADK_Agent_Bundle_1/{agent}/run_receipts/{file}` | `ADK_Agent_Bundle_1/rico/run_receipts/2026-03-03.jsonl` |
| Skill files | `skills/{skill_name}.md` | `skills/write_session_memory.md` |
| Playbooks | `playbooks/{file}` | `playbooks/ENGINEER_PLAYBOOK_v1.1.md` |

### File Naming in GCS

| Type | Convention | Example |
|------|-----------|---------|
| Session files | `{user}_{YYYY-MM-DD}.json` | `tony_2026-03-03.json` |
| Run receipt files | `{YYYY-MM-DD}.jsonl` | `2026-03-03.jsonl` |
| Context files | `descriptive_snake_case.{ext}` | `system_prompt.md`, `product_list.txt` |
| Cached context | `{agent}_cached_context.json` | `rico_cached_context.json` |

---

## Documentation & Skill Files

### Documentation Files

| Type | Convention | Example |
|------|-----------|---------|
| Playbooks & Briefs | `SCREAMING_SNAKE_CASE.md` | `MASTER_BRIEF.md`, `PHASE_1_OVERVIEW.md` |
| Versioned docs | `{NAME}_v{X.Y}.md` | `MASTER_BRIEF_v1.2.md` |
| Agent briefs | `PHASE_{N}{sub}_AGENT_{SET}_{NAME}.md` | `PHASE_1A_AGENT_SET_1_RICO_CACHING.md` |
| README files | `README.md` | Always PascalCase |

### Skill Files

| Convention | Example |
|-----------|---------|
| `SCREAMING_SNAKE_CASE.md` | `WRITE_SESSION_MEMORY.md`, `SCAFFOLD_NEW_AGENT.md` |
| Stored in `skills/` (local) or `skills/` (GCS) | `skills/SWITCH_MODE.md` |

---

## Git & Branching

| Type | Convention | Example |
|------|-----------|---------|
| Feature branches | `feat/agent-{n}-{name}` | `feat/agent-1a-rico-baseline` |
| Fix branches | `fix/{description}` | `fix/token-calculator-error-handling` |
| Chore branches | `chore/{description}` | `chore/starter-kit-cleanup` |
| Commit messages | `{type}: {description}` | `feat: add token calculator with tests` |

**Commit types:** `feat`, `fix`, `chore`, `docs`, `test`, `refactor`

---

## Environment Variables

| Convention | Example |
|-----------|---------|
| `SCREAMING_SNAKE_CASE` | `GCP_PROJECT_ID`, `GCS_BUCKET_NAME` |
| Prefix with service name for clarity | `VERTEX_LOCATION`, `DEFAULT_MODEL` |
| Boolean env vars | `ENABLE_CACHING=true`, `DEBUG_MODE=false` |

---

## Test Naming

| Type | Convention | Example |
|------|-----------|---------|
| Test files | `test_{module}.py` | `test_tools.py`, `test_agent.py` |
| Test functions | `test_{what}_{expected}` | `test_count_tokens_returns_positive()` |
| Test classes (if grouped) | `Test{Feature}` | `TestTokenCalculator`, `TestRunReceipt` |
| Eval case files | `eval_cases.json` | Always this name, per agent |
| Fixtures | `{descriptive_name}` | `mock_gcs_client`, `sample_receipt` |

---

## Anti-Patterns — DO NOT

| ❌ Don't | ✅ Do Instead |
|----------|--------------|
| `myAgent`, `MyAgent_v2` | `my_agent/`, `MyAgent` class |
| `utils.py` (generic) | `token_calculator.py` (specific) |
| `data/`, `stuff/`, `misc/` | `context/`, `sessions/`, `run_receipts/` |
| `test1.py`, `test_new.py` | `test_tools.py`, `test_agent.py` |
| `SKILL1.md`, `skill_v2.md` | `WRITE_SESSION_MEMORY.md` |
| Mixed case in GCS paths | Always `snake_case` for GCS paths |
| Spaces in any filename | Always underscores or hyphens |

---

## Quick Reference Card

```
Files/Folders:     snake_case          → product_agent/, token_calculator.py
Classes:           PascalCase          → ProductAgent, RunReceipt
Functions:         snake_case          → count_tokens(), create_receipt()
Constants:         SCREAMING_SNAKE     → DEFAULT_MODEL, GCS_BUCKET_NAME
State Keys:        snake_case/dot      → session.state["mode"]
GCS Paths:         snake_case          → agents/rico/sessions/
Docs:              SCREAMING_SNAKE.md  → MASTER_BRIEF.md
Skills:            SCREAMING_SNAKE.md  → WRITE_SESSION_MEMORY.md
Tests:             test_<module>.py    → test_tools.py
Branches:          kebab-case          → feat/agent-1a-rico-baseline
Env Vars:          SCREAMING_SNAKE     → GCP_PROJECT_ID
```

---

*Generated by JARVIS — Cyberize Engineering AI Factory*
*Version: 1.0 | Date: March 3, 2026*
