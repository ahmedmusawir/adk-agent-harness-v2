# 03 — Engine Tuning

**ADK Agent Harness v2**

---

## Why tune

A fresh Agent Engine ships with NO `context_spec` — every setting is on server-side default. That means:

- Default extraction topics (good general coverage but misses domain specifics)
- Default generation model (we don't even know which one Google picks)
- No few-shot examples (extractor has to guess your extraction style)
- No TTL (memories live forever)

Out-of-the-box behavior worked but was lossy. Pass 2 tuning transformed extraction from ~50% capture on technical content to 100%. Concrete numbers are in `memory_bank_discovery/docs/ENGINE_TUNING_INSPECTION.md`.

---

## What we tuned

The full `context_spec` applied to our engine:

### Generation model
Full publisher path, not short name:
```
projects/ninth-potion-455712-g9/locations/us-central1/publishers/google/models/gemini-2.5-pro
```
Pro over Flash for extraction quality. Pass 2 extraction ran in ~16.5s — similar to Flash latency, so no visible cost.

### Managed topics (all 4)
- `USER_PERSONAL_INFO` — names, relationships, hobbies, dates
- `USER_PREFERENCES` — likes, dislikes, patterns
- `KEY_CONVERSATION_DETAILS` — milestones, conclusions
- `EXPLICIT_INSTRUCTIONS` — user says "remember X" or "forget Y"

### Custom topics (4, domain-specific)
- `architectural_decisions` — technology choices, framework selections, infrastructure design, reasoning
- `project_constraints` — compliance requirements, deadlines, non-negotiables
- `lessons_learned` — what worked, what failed, what was harder than expected
- `technology_stack` — current tools + rationale

Each custom topic has a natural-language `description` that gets injected into the server-side extraction prompt.

### Few-shot examples (3)
Each example pairs a sample user turn with the expected extracted memories:
1. **Architecture decision** — "Vercel Pro with HIPAA add-on for Project Mothership…" → 3 expected memories
2. **Technical finding** — "ADK eval finding: tool_trajectory_avg_score incompatible…" → 2 expected memories
3. **Code conventions** — "/types folder, Zustand, html-react-parser…" → 3 expected memories

Few-shots are the most effective lever for controlling extraction style and depth.

### TTL — granular only
```python
granular_ttl_config = {
    "create_ttl":            "31536000s",  # 1 year  — manual writes
    "generate_created_ttl":   "2592000s",  # 30 days — auto-extracted new
    "generate_updated_ttl":   "7776000s",  # 90 days — consolidation updates
}
```
**Important:** TTL is a protobuf `oneof`. Set EITHER `default_ttl` OR `granular_ttl_config`, never both. Sending both returns a 400. The SDK pydantic class doesn't enforce this — discipline required.

### Engine metadata
- `display_name`: "Stark Industries Memory Engine"
- `description`: "Memory Bank engine for ADK agent harness v2"

---

## How to re-tune

Tuning is **update-in-place** — we do NOT re-provision the engine. Existing memories survive; tuning affects future `generate()` calls only.

### Step 1 — Inspect current state
```
python memory_bank_discovery/scripts/inspect_engine_config.py
```

### Step 2 — Edit the tuning script
Open `memory_bank_discovery/scripts/update_engine_config.py`. Edit the module-level constants:
- `GENERATION_MODEL` — full publisher path
- `MANAGED_TOPICS` — list of enum strings
- `CUSTOM_TOPICS` — list of `{"label": ..., "description": ...}` dicts
- `FEW_SHOT_EXAMPLES` — list using `_user_event()` helper
- `TTL_CONFIG` — granular only

### Step 3 — Preview and apply
```
python memory_bank_discovery/scripts/update_engine_config.py
```
Script prints the full payload, waits for Enter, then applies. After apply, it reads back the engine to verify.

### Step 4 — Validate extraction quality
```
python memory_bank_discovery/scripts/test_tuned_generate.py
```
Runs a 6-turn technical conversation through `generate()` and audits what comes out.

---

## Scope-specific tuning

`MemoryBankCustomizationConfig` has a `scope_keys` field. If set to `[]` (empty), the config is the default for all scopes. If set to specific keys, the config only applies when a request's scope matches.

Currently we use one default config (`scope_keys=[]`). Future: could have different topics/few-shots for different user types (e.g., Tony vs. anonymous). That'd live in the `customization_configs` list as multiple entries.

---

## What's NOT configurable

- **Embedding model (left at default)** — `text-embedding-005`. Changeable via `similarity_search_config.embedding_model` if we need multilingual or a different model.
- **Extraction prompt itself** — only indirectly controllable via topics + few-shots. No way to fully override the server-side prompt.
- **Per-call overrides** — `context_spec` is engine-level. You cannot change model or topics for a single `generate()` call.

---

## Where findings live

- **Current config snapshot:** `memory_bank_discovery/scripts/inspect_engine_config.py` output
- **Pass 1 inspection + Pass 2 tuning results:** `memory_bank_discovery/docs/ENGINE_TUNING_INSPECTION.md`
- **SDK reference for all config classes:** `vertexai/_genai/types.py` — the pydantic classes prefixed with `ReasoningEngineContextSpecMemoryBankConfig` and `MemoryBankCustomizationConfig`

---

## Gotcha checklist when re-tuning

- [ ] Full publisher model path (not short name)
- [ ] `granular_ttl_config` XOR `default_ttl` — never both
- [ ] Enum strings (not enum instances) for managed topics
- [ ] Custom topic `description` is a full sentence explaining what to extract
- [ ] Few-shots use the same content shape as `test_generate_memories.py`
- [ ] Run `test_tuned_generate.py` after every update to catch regressions
