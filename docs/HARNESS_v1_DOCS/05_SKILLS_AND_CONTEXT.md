# 05 — Skills and Context

**ADK Agent Harness v1**

---

## Two GCS-Backed Libraries

`architect_agent` has access to two on-demand knowledge systems stored in GCS:

| System | Tool | Scope | Path pattern |
|--------|------|-------|-------------|
| **Skills** | `invoke_skill` | Global — shared across agents | `globals/skills/{SKILL_NAME}/SKILL.md` |
| **Context docs** | `read_context_doc` | Per-agent — specific to one agent | `{agent_name}/context/{DOC_NAME}.md` |

Both work the same way: the agent calls a tool with a name, the tool fetches the relevant GCS file, and the content is returned as a string the agent reads and acts on. Neither system caches — every call is a live GCS read.

---

## Skills System

### What a Skill Is

A skill is a structured workflow instruction document. It tells the agent exactly how to perform a specific repeatable task — step by step, with context about why each step matters.

Skills are not tools that do things. They are instruction documents that guide what the agent says or does next. The agent reads the skill content and follows it.

### Why Skills Exist in GCS

- Skills can be updated without redeploying code
- Skills are shared across agents (global scope)
- Skills can be versioned, iterated, and improved independently
- The agent only loads what it needs, when it needs it (no upfront context bloat)

### GCS Layout

```
globals/skills/
├── SKILL_INDEX.md                    ← Flat index listing all available skills
├── SESSION_UPDATE_SKILL/
│   └── SKILL.md                      ← How to write a session update
└── SESSION_MEMORY_SKILL/
    └── SKILL.md                      ← How to read and use session memory
```

**Important:** `SKILL_INDEX` is the only skill stored flat (no subfolder). All other skills live in a subfolder named after them. This is enforced in the `invoke_skill` function:

```python
if skill_name == "SKILL_INDEX":
    file_path = f"{base_folder}/globals/skills/SKILL_INDEX.md"
else:
    file_path = f"{base_folder}/globals/skills/{skill_name}/SKILL.md"
```

### Naming Convention

Skill names use `SCREAMING_SNAKE_CASE`. The agent passes the name to `invoke_skill` exactly as it appears in the index.

Examples:
- `SESSION_UPDATE_SKILL`
- `SESSION_MEMORY_SKILL`
- (future) `ENGINEER_PROMPT_SKILL`

### How the Agent Uses Skills

The agent follows this pattern:

1. User asks a procedural question (e.g., "How should I update the session file?")
2. Agent calls `invoke_skill("SKILL_INDEX")` to see what's available
3. Agent identifies the relevant skill name
4. Agent calls `invoke_skill("SESSION_UPDATE_SKILL")`
5. Agent reads the returned SKILL.md content
6. Agent follows the instructions in its response

If the agent skips step 4 and answers from general knowledge — that is a behavior bug. The manual test scenario `skill_invocation` catches this.

### Adding a New Skill

1. Create the folder and file in GCS: `globals/skills/{YOUR_SKILL_NAME}/SKILL.md`
2. Add an entry to `globals/skills/SKILL_INDEX.md`
3. No code changes required — the agent can use it immediately

---

## Context Library

### What a Context Doc Is

A context document is a project-specific reference file — a manual, playbook, transcript, architecture doc, or any reference material the agent needs to answer accurately about this specific project.

Unlike skills (which define workflows), context docs define facts and project-specific knowledge.

### Why Context Docs Exist in GCS

- They are too large to include in the system prompt on every turn
- They change as the project evolves — GCS updates are instant
- The agent loads only the doc it needs for the current question
- Different agents can have different context libraries

### GCS Layout

```
architect_agent/context/
├── CONTEXT_INDEX.md                  ← Index of available context docs (if exists)
└── APP_ARCHITECTURE_MANUAL.md        ← Project architecture reference
```

### Naming Convention

Context doc names use `SCREAMING_SNAKE_CASE`. The agent passes the name to `read_context_doc` without the `.md` extension.

Examples:
- `APP_ARCHITECTURE_MANUAL`
- `CONTEXT_INDEX`
- (future) `API_INTEGRATION_GUIDE`

### How the Agent Uses Context Docs

1. User asks about a specific project topic (e.g., "What does the APP_ARCHITECTURE_MANUAL say about folder structure?")
2. Agent calls `read_context_doc("APP_ARCHITECTURE_MANUAL")`
3. Agent reads the returned content
4. Agent answers based on the actual doc — not from general knowledge

If the agent answers from general Next.js knowledge instead of calling `read_context_doc` — that is a behavior bug. The manual test scenario `context_doc_loading` catches this.

### Adding a New Context Doc

1. Upload the markdown file to GCS: `{BASE}/{agent_name}/context/{YOUR_DOC_NAME}.md`
2. Add an entry to `CONTEXT_INDEX.md` in the same folder (if an index exists)
3. No code changes required

---

## Skills vs. Context: When to Use Which

| Use Skills when... | Use Context when... |
|--------------------|---------------------|
| The agent needs to follow a procedure | The agent needs to reference facts |
| The content is a workflow ("how to do X") | The content is a reference ("what is X") |
| Multiple agents might need it | It is specific to one agent's domain |
| The content defines steps and rules | The content describes architecture or data |

**Example:** How to write a session update → `SESSION_UPDATE_SKILL`
**Example:** What the folder structure looks like → `APP_ARCHITECTURE_MANUAL`

---

## Error Handling

Both tools return error strings (not exceptions) when GCS reads fail:

```python
# invoke_skill failure:
"Skill 'MISSING_SKILL' not found in globals/skills."

# read_context_doc failure:
"Context document 'MISSING_DOC' not found in architect_agent/context/"
```

The agent should surface these errors in its response rather than hallucinating content. If a tool returns an error, the GCS file needs to be uploaded — no code fix is required.

---

*See `06_SESSION_MEMORY.md` for the session memory system.*
