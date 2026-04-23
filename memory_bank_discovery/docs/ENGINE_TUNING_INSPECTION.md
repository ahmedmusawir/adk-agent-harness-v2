# Engine Tuning Inspection Report

**Scope:** read-only inspection of the current Agent Engine and SDK surface to inform Pass 2 tuning decisions. No engine/memory/code changes made.

**Engine under inspection:** `projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976`

**SDK version:** `google-cloud-aiplatform == 1.111.0` (confirmed via `pip show`)

---

## Current Engine Config

Output from `memory_bank_discovery/scripts/inspect_engine_config.py`:

```
======================================================================
Engine config inspection
======================================================================
Project:  ninth-potion-455712-g9
Location: us-central1
Engine:   projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976
----------------------------------------------------------------------

[Section 1] Top-level ReasoningEngine fields (what's SET vs NOT SET)
----------------------------------------------------------------------
  name: SET
  display_name: NOT SET
  description: NOT SET
  create_time: SET
  update_time: SET
  etag: NOT SET
  spec: SET
  context_spec: NOT SET

[Section 2] context_spec contents
----------------------------------------------------------------------
  context_spec is NOT SET on this engine.
  → Engine is using SERVER-SIDE DEFAULTS for everything.

[Section 3] Full ReasoningEngine object (JSON dump, None preserved)
----------------------------------------------------------------------
{
  "context_spec": null,
  "create_time": "2026-04-19 06:35:07.991571+00:00",
  "description": null,
  "display_name": null,
  "encryption_spec": null,
  "etag": null,
  "name": "projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976",
  "spec": {
    "agent_framework": null,
    "class_methods": null,
    "deployment_spec": null,
    "package_spec": null,
    "service_account": null
  },
  "update_time": "2026-04-19 06:35:24.602122+00:00"
}

[Section 4] Raw repr (fallback fidelity)
----------------------------------------------------------------------
ReasoningEngine(
  create_time=datetime.datetime(2026, 4, 19, 6, 35, 7, 991571, tzinfo=TzInfo(UTC)),
  name='projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976',
  spec=ReasoningEngineSpec(),
  update_time=datetime.datetime(2026, 4, 19, 6, 35, 24, 602122, tzinfo=TzInfo(UTC))
)
```

**Key takeaway:** every nested config field is null/unset. No custom memory topics, no few-shot examples, no generation-model choice, no embedding-model choice, no TTL. Memory Bank is running on pure server-side defaults.

---

## Update Capability

- **Can update `context_spec` on existing engine: YES.**
- **Evidence:** `client.agent_engines.update()` at `.venv/lib/python3.12/site-packages/vertexai/_genai/agent_engines.py:1418-1525` — the method explicitly accepts a `config: AgentEngineConfig` parameter, extracts `config.context_spec`, serializes it via `model_dump()`, and passes it to the internal `_create_config(mode="update", ..., context_spec=context_spec, ...)`.
  - Line 1473-1476:
    ```python
    context_spec = config.context_spec
    if context_spec is not None:
        # Conversion to a dict for _create_config
        context_spec = context_spec.model_dump()
    ```
  - `AgentEngineConfig` definition at `types.py:8729` includes `context_spec: Optional[ReasoningEngineContextSpec]` as a declared field (line 8776).
- **Means:** we do NOT need a new engine. We can mutate the live engine's `context_spec` with `client.agent_engines.update(name=AGENT_ENGINE_ID, config=AgentEngineConfig(context_spec=...))`.
- **Caveat:** existing memories already written against server defaults will NOT be retroactively re-extracted. Tuning affects future writes only.

---

## Supported Generation Models

- **Verified models: NONE explicitly validated in SDK.**
- **gemini-2.5-pro supported: UNVERIFIED in SDK.** Format path must be `projects/{project}/locations/{location}/publishers/google/models/{model}`. Any valid Vertex AI publisher-model path is accepted by the SDK client; server-side validation is what actually decides.
- **Evidence:** `types.py:3518-3521`:
  ```python
  model: Optional[str] = Field(
      default=None,
      description="""Required. The model used to generate memories. Format: `projects/{project}/locations/{location}/publishers/google/models/{model}`.""",
  )
  ```
  No regex, no enum, no allowlist. The SDK's `evals_common.py:450` has a related message about model name format ("gemini-2.5-pro") but that's a separate validation path (evals, not memory bank).
- **Corroborating evidence from Google's [Sep 3, 2025 customization announcement](https://discuss.google.dev/t/announcing-customization-features-for-vertex-ai-memory-bank/261941):**
  ```python
  generation_config=GenerationConfig(model="gemini-2.5-flash")
  ```
  That's the only example — `gemini-2.5-flash` was demonstrated. `gemini-2.5-pro` is plausible but not officially demonstrated in that post.
- **Recommendation for Pass 2:** start with `"projects/ninth-potion-455712-g9/locations/us-central1/publishers/google/models/gemini-2.5-flash"` (known-good), then test `-pro` by actually attempting to update the engine and seeing if the server accepts it.

---

## Few-Shot Example Schema

### Top-level: `MemoryBankCustomizationConfigGenerateMemoriesExample`

**Class:** `MemoryBankCustomizationConfigGenerateMemoriesExample` (at `types.py:3748`)

**Required fields:** none at the top level are hard-required (both are `Optional`), but the docstring makes `conversation_source` functionally required for the example to be useful.

**Fields:**
- `conversation_source`: `MemoryBankCustomizationConfigGenerateMemoriesExampleConversationSource` — the input transcript
- `generated_memories`: `list[MemoryBankCustomizationConfigGenerateMemoriesExampleGeneratedMemory]` — the facts expected to be extracted. Empty list = "nothing should be extracted from this input" (useful for negative examples).

**Full class definition:**
```python
class MemoryBankCustomizationConfigGenerateMemoriesExample(_common.BaseModel):
    """An example of how to generate memories for a particular scope."""

    conversation_source: Optional[
        MemoryBankCustomizationConfigGenerateMemoriesExampleConversationSource
    ] = Field(default=None, description="""A conversation source for the example.""")
    generated_memories: Optional[
        list[MemoryBankCustomizationConfigGenerateMemoriesExampleGeneratedMemory]
    ] = Field(
        default=None,
        description="""Optional. The memories that are expected to be generated from the input conversation. An empty list indicates that no memories are expected to be generated for the input conversation.""",
    )
```

### `conversation_source` format

**Class:** `MemoryBankCustomizationConfigGenerateMemoriesExampleConversationSource` (at `types.py:3682`)

Contains a `list[event]` where each event has a `content` field of type `google.genai.types.Content`. That's the **standard Gemini Content object** — with `role` (`"user"` | `"model"`) and `parts` (list of `Part(text=...)`). Same shape we've been building in `test_generate_memories.py`.

```python
class MemoryBankCustomizationConfigGenerateMemoriesExampleConversationSource(
    _common.BaseModel
):
    """A conversation source for the example.

    This is similar to `DirectContentsSource`.
    """

    events: Optional[
        list[
            MemoryBankCustomizationConfigGenerateMemoriesExampleConversationSourceEvent
        ]
    ] = Field(
        default=None,
        description="""Optional. The input conversation events for the example.""",
    )


class MemoryBankCustomizationConfigGenerateMemoriesExampleConversationSourceEvent(
    _common.BaseModel
):
    """The conversation source event for generating memories."""

    content: Optional[genai_types.Content] = Field(
        default=None, description="""Required. The content of the event."""
    )
```

### `generated_memories` format

**Class:** `MemoryBankCustomizationConfigGenerateMemoriesExampleGeneratedMemory` (at `types.py:3722`)

Just a string `fact`. NOT a full Memory object — no scope, no timestamps, no resource name.

```python
class MemoryBankCustomizationConfigGenerateMemoriesExampleGeneratedMemory(
    _common.BaseModel
):
    """A memory generated by the operation."""

    fact: Optional[str] = Field(
        default=None,
        description="""Required. The fact to generate a memory from.""",
    )
```

### Summary for Pass 2

- Build few-shot examples as lists of `{"conversation_source": {"events": [{"content": Content(...)}, ...]}, "generated_memories": [{"fact": "..."}, ...]}` dicts.
- Conversation format mirrors what `test_generate_memories.py` already builds — no new content-building skill needed.
- Generated-memories are bare strings wrapped in `{"fact": "..."}`, one per expected extraction.

---

## PreloadMemoryTool top_k

- **Configurable: NO (in the ADK-shipped preload_memory_tool).**
- **Current value: whatever the server default is — which is 3.**
- **Evidence:**
  - `google/adk/tools/preload_memory_tool.py:59` — the tool calls:
    ```python
    response = await tool_context.search_memory(user_query)
    ```
    Just the query string. No config, no params.
  - `tool_context.search_memory(query)` at `google/adk/tools/tool_context.py:76`:
    ```python
    return await self._invocation_context.memory_service.search_memory(...)
    ```
    Passes query along. No top_k surface.
  - `VertexAiMemoryBankService.search_memory` at `google/adk/memory/vertex_ai_memory_bank_service.py:97-112`:
    ```python
    api_response = await api_client.async_request(
        http_method='POST',
        path=f'reasoningEngines/{self._agent_engine_id}/memories:retrieve',
        request_dict={
            'scope': {
                'app_name': app_name,
                'user_id': user_id,
            },
            'similarity_search_params': {
                'search_query': query,
            },
        },
    )
    ```
    **`similarity_search_params` is hardcoded to `{"search_query": query}` with NO top_k.**
  - Server-side default for top_k from `types.py:5617-5620`:
    ```python
    top_k: Optional[int] = Field(
        default=None,
        description="""Optional. The maximum number of memories to return. The service may return fewer than this value. If unspecified, at most 3 memories will be returned. The maximum value is 100; values above 100 will be coerced to 100.""",
    )
    ```
- **Confirms earlier hypothesis:** Jarvis is retrieving only 3 memories via preload. For users with many memories, the relevant one may not rank into the top 3.
- **Remediation options for Pass 2:**
  - (a) Swap to `load_memory_tool` (model-invoked) and wrap it in a custom FunctionTool that passes `top_k=10` — requires forking ADK's tool.
  - (b) Write a custom preload-style tool that calls `memories.retrieve()` directly with configurable `top_k`. Skip `VertexAiMemoryBankService` entirely for reads.
  - (c) Leave preload as-is, accept the 3-memory cap.

---

## Custom Memory Topic Schema

### Top-level: `MemoryBankCustomizationConfigMemoryTopic`

**Class:** `MemoryBankCustomizationConfigMemoryTopic` (at `types.py:3618`)

Exactly ONE of `custom_memory_topic` OR `managed_memory_topic` should be set per instance (it's a oneof pattern but not enforced in pydantic — discipline required).

```python
class MemoryBankCustomizationConfigMemoryTopic(_common.BaseModel):
    """A topic of information that should be extracted from conversations and stored as memories."""

    custom_memory_topic: Optional[
        MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic
    ] = Field(
        default=None,
        description="""A custom memory topic defined by the developer.""",
    )
    managed_memory_topic: Optional[
        MemoryBankCustomizationConfigMemoryTopicManagedMemoryTopic
    ] = Field(
        default=None,
        description="""A managed memory topic defined by Memory Bank.""",
    )
```

### Custom topic fields

**Class:** `MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic` (at `types.py:3565`)

Two fields — both documented as Required, both declared as Optional in the pydantic model. Server-side validation is what enforces "Required."

```python
class MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic(_common.BaseModel):
    """A custom memory topic defined by the developer."""

    label: Optional[str] = Field(
        default=None, description="""Required. The label of the topic."""
    )
    description: Optional[str] = Field(
        default=None,
        description="""Required. Description of the memory topic. This should explain what information should be extracted for this topic.""",
    )
```

- `label`: short identifier for the topic (e.g., `"work_context"`, `"family_info"`)
- `description`: natural-language explanation of what should be extracted. Injected into the server-side extraction prompt.

### Managed topic fields

**Class:** `MemoryBankCustomizationConfigMemoryTopicManagedMemoryTopic` (at `types.py:3595`)

Single field — an enum from `ManagedTopicEnum`.

```python
class MemoryBankCustomizationConfigMemoryTopicManagedMemoryTopic(_common.BaseModel):
    """A managed memory topic defined by the system."""

    managed_topic_enum: Optional[ManagedTopicEnum] = Field(
        default=None, description="""Required. The managed topic."""
    )
```

### `ManagedTopicEnum` — the four built-ins

From `types.py:218-230`:

```python
class ManagedTopicEnum(_common.CaseInSensitiveEnum):
    """Required. The managed topic."""

    MANAGED_TOPIC_ENUM_UNSPECIFIED = "MANAGED_TOPIC_ENUM_UNSPECIFIED"
    """Unspecified topic. This value should not be used."""
    USER_PERSONAL_INFO = "USER_PERSONAL_INFO"
    """Significant personal information about the User like first names, relationships, hobbies, important dates."""
    USER_PREFERENCES = "USER_PREFERENCES"
    """Stated or implied likes, dislikes, preferred styles, or patterns."""
    KEY_CONVERSATION_DETAILS = "KEY_CONVERSATION_DETAILS"
    """Important milestones or conclusions within the dialogue."""
    EXPLICIT_INSTRUCTIONS = "EXPLICIT_INSTRUCTIONS"
    """Information that the user explicitly requested to remember or forget."""
```

### Max topics

**NO LIMIT documented in SDK.** Grep of `types.py` returns no cap on `list[MemoryBankCustomizationConfigMemoryTopic]` length. Server may enforce one — unverified. Reasonable assumption: keep to <20 for performance/prompt-size concerns.

### Container: `MemoryBankCustomizationConfig`

Full shape of the parent config, at `types.py:3782`:

```python
class MemoryBankCustomizationConfig(_common.BaseModel):
    """Configuration for organizing memories for a particular scope."""

    scope_keys: Optional[list[str]] = Field(
        default=None,
        description="""Optional. The scope keys (i.e. 'user_id') for which to use this config. A request's scope must include all of the provided keys for the config to be used (order does not matter). If empty, then the config will be used for all requests that do not have a more specific config. Only one default config is allowed per Memory Bank.""",
    )
    memory_topics: Optional[list[MemoryBankCustomizationConfigMemoryTopic]] = Field(
        default=None,
        description="""Optional. Topics of information that should be extracted from conversations and stored as memories. If not set, then Memory Bank's default topics will be used.""",
    )
    generate_memories_examples: Optional[
        list[MemoryBankCustomizationConfigGenerateMemoriesExample]
    ] = Field(
        default=None,
        description="""Optional. Examples of how to generate memories for a particular scope.""",
    )
```

**Important nuance — `scope_keys` is a scoping selector, not a filter.** A request's scope must include all listed keys (order-agnostic) for this config to apply. If `scope_keys=[]` (empty), the config becomes the default-for-all. Only one default is allowed per engine. **This means we can have per-scope customizations** — different topics/examples for different user types.

---

## TTL Schema

### Top-level: `ReasoningEngineContextSpecMemoryBankConfigTtlConfig`

At `types.py:3861`:

```python
class ReasoningEngineContextSpecMemoryBankConfigTtlConfig(_common.BaseModel):
    """Configuration for automatically setting the TTL ("time-to-live") of the memories in the Memory Bank."""

    default_ttl: Optional[str] = Field(
        default=None,
        description="""Optional. The default TTL duration of the memories in the Memory Bank. This applies to all operations that create or update a memory.""",
    )
    granular_ttl_config: Optional[
        ReasoningEngineContextSpecMemoryBankConfigTtlConfigGranularTtlConfig
    ] = Field(
        default=None,
        description="""Optional. The granular TTL configuration of the memories in the Memory Bank.""",
    )
```

### Granular TTL config

At `types.py:3821`:

```python
class ReasoningEngineContextSpecMemoryBankConfigTtlConfigGranularTtlConfig(
    _common.BaseModel
):
    """Configuration for TTL of the memories in the Memory Bank based on the action that created or updated the memory."""

    create_ttl: Optional[str] = Field(
        default=None,
        description="""Optional. The TTL duration for memories uploaded via CreateMemory.""",
    )
    generate_created_ttl: Optional[str] = Field(
        default=None,
        description="""Optional. The TTL duration for memories newly generated via GenerateMemories (GenerateMemoriesResponse.GeneratedMemory.Action.CREATED).""",
    )
    generate_updated_ttl: Optional[str] = Field(
        default=None,
        description="""Optional. The TTL duration for memories updated via GenerateMemories (GenerateMemoriesResponse.GeneratedMemory.Action.UPDATED). In the case of an UPDATE action, the `expire_time` of the existing memory will be updated to the new value (now + TTL).""",
    )
```

### Format

TTL values are **Google protobuf Duration strings** — seconds followed by `s`, e.g. `"2592000s"` = 30 days. Confirmed by the [Sep 3 2025 announcement](https://discuss.google.dev/t/announcing-customization-features-for-vertex-ai-memory-bank/261941) example:
```python
ttl_config=TtlConfig(default_ttl="2592000s")  # 30 days
```

### Defaults

**Default if `ttl_config` is not set: memories NEVER expire.** The description on `ttl_config` (in `types.py:3913`) says: *"Optional. Configuration for automatic TTL ("time-to-live") of the memories in the Memory Bank. If not set, TTL will not be applied automatically. The TTL can be explicitly set by modifying the `expire_time` of each Memory resource."*

Current state of our engine: **no TTL → all memories persist forever** unless manually deleted via `cleanup_memories_by_scope.py`.

---

## Blockers or Surprises

### 1. No blockers to Pass 2 tuning
- ✅ Update-in-place is supported (`client.agent_engines.update(...)` accepts `context_spec`).
- ✅ SDK v1.111.0 is past the v1.104.0 threshold for customization features.
- ✅ All three major levers (custom topics, few-shot examples, model selection) are available.

### 2. Surprise #1 — `preload_memory_tool` top_k is hardcoded to default (3)
Not just "not exposed by ADK" — the service layer (`VertexAiMemoryBankService.search_memory`) also doesn't pass top_k. We'd need to either fork that service, write a custom recall tool, or accept the 3-memory ceiling. **This is likely the #1 reason Jarvis's retrieval feels amnesiac.**

### 3. Surprise #2 — Model string has no client-side validation
Any path-formatted string works. If we set `model="gemini-99-imaginary"`, the SDK accepts it; server-side will reject at first `generate()` call. **Implication:** test the model change on the engine immediately after updating, not later.

### 4. Surprise #3 — Customization is scope-scoped, not engine-global
`MemoryBankCustomizationConfig.scope_keys` lets you have different topics/examples per user-scope shape. One "default" config (scope_keys empty) applies when nothing more specific matches. **Means we can have, e.g., different extraction rules for Tony vs. anonymous users on the same engine.**

### 5. Surprise #4 — Existing memories are NOT retroactively re-extracted
Tuning `context_spec` affects future `generate()` calls only. Our current 9+ memories stay as-is. If we want a clean slate with new rules, we'd clean up existing memories first. Not a blocker, just a planning note.

### 6. Surprise #5 — Our engine has no `display_name` or `description`
Cosmetic, but worth setting now while we're at it — makes the engine easier to identify in the Cloud Console. Pass 2 candidate, not blocker.

---

## Deliverables completed

- `memory_bank_discovery/scripts/inspect_engine_config.py` — created + ran successfully.
- `memory_bank_discovery/docs/ENGINE_TUNING_INSPECTION.md` — this file.
- No engine config modified. No memories touched. No agent code changed.

Ready for architect review before Pass 2.

---

## Pass 2 — Engine Tuning Results

**Date:** 2026-04-23

**Config applied** (via `memory_bank_discovery/scripts/update_engine_config.py`):
- **Engine metadata:** `display_name` = "Stark Industries Memory Engine", `description` = "Memory Bank engine for ADK agent harness v2"
- **Generation model:** `projects/ninth-potion-455712-g9/locations/us-central1/publishers/google/models/gemini-2.5-pro`
- **Managed topics (all 4):** `USER_PERSONAL_INFO`, `USER_PREFERENCES`, `KEY_CONVERSATION_DETAILS`, `EXPLICIT_INSTRUCTIONS`
- **Custom topics (4):** `architectural_decisions`, `project_constraints`, `lessons_learned`, `technology_stack`
- **Few-shot examples (3):** Vercel/HIPAA hosting decision, ADK eval-system finding, code conventions (Zustand / html-react-parser / /types)
- **TTL policy** (granular only, per the `oneof` fix):
  - `create_ttl`: `31536000s` (1 year — manual writes via `memories.create()`)
  - `generate_created_ttl`: `2592000s` (30 days — auto-extracted new memories)
  - `generate_updated_ttl`: `7776000s` (90 days — consolidation updates)

**Generation model test:** **PASS**
- `client.agent_engines.update(...)` with `generation_config.model="gemini-2.5-pro"` accepted without error.
- Subsequent `memories.generate()` call succeeded. Latency ~16.55s — similar to pre-tuning Flash latency, so we can't definitively confirm Pro was used for extraction (Google doesn't surface the actual model used in responses), but the server accepted the config and extraction ran successfully.
- If we want to prove Pro vs Flash, we'd need Cloud Audit Logs on the engine.

**Extraction test results** (via `memory_bank_discovery/scripts/test_tuned_generate.py`):

- **Total memories extracted:** 5 (from 5 technical user turns + 1 small-talk turn)
- **Technical details captured:** YES — all 5
  1. ✓ Supabase Team plan + HIPAA add-on as Mothership database layer
  2. ✓ VS Code → Cursor editor switch
  3. ✓ Eval-runner lesson: ADK web UI has frontend/backend sync gaps; standalone runners bypass
  4. ✓ Frank GCP discovery-first constraint (named client correctly as "Frank", captured "no rip-and-replace" rule)
  5. ✓ ADK + Gemini 2.5 Flash runtime / Claude architect split
- **Small talk filtered:** YES — "Hey Jarvis, how's it going today?" / "Doing well, sir" correctly not extracted as a memory.
- **Extraction quality vs baseline:** **BETTER** — substantially.
  - Baseline (Test 4, pre-tuning): 1 fact extracted from 2 user facts in a 3-turn transcript (50% capture, no customization).
  - Tuned (this test): 5 facts extracted from 5 technical user turns in a 12-event transcript (100% capture, correct small-talk filter).
  - Facts now include nuance ("frontend/backend synchronization gaps," "no rip-and-replace") rather than paraphrased summaries.

**Issues found**

1. **TTL `oneof` constraint not surfaced by SDK.** The `ReasoningEngineContextSpecMemoryBankConfigTtlConfig` class exposes `default_ttl` AND `granular_ttl_config` as independently-Optional fields in pydantic. The server-side protobuf treats them as a `oneof` (mutually exclusive). Sending both returns:
   > `400 INVALID_ARGUMENT: Invalid value at 'reasoning_engine.context_spec.memory_bank_config.ttl_config' (oneof), oneof field 'ttl' is already set. Cannot set 'granular_ttl_config'`
   
   **Resolution applied:** dropped `default_ttl`, kept `granular_ttl_config` alone. Granular already covers every write path.
   
   **Documentation note for future devs:** even though the Python SDK lets you construct a dict with both fields, pick ONE. The `oneof` constraint isn't client-side enforced.

2. **SDK still shows `default_ttl: null` in the read-back.** The verification `get()` after update returns `ttl_config.default_ttl = null` and the granular fields populated. Confirms only one of the `oneof` variants is actually set.

3. **Existing pre-tuning memories not affected.** Confirmed: the old 13 memories (mostly under `{"user_id": "tony_stark"}` and `{"app_name": "jarvis_agent", "user_id": "user"}` scopes) still exist unchanged. Tuning only affects new `generate()` calls.

4. **Test-scope contamination.** `test_tuned_generate.py` wrote 5 memories under `{"user_id": "test_tuning"}`. Future cleanup via `cleanup_memories_by_scope.py` with `TARGET_SCOPE = {"user_id": "test_tuning"}` when needed.

**Pass 2 complete. Ready for the cleanup step and Jarvis-side integration.**
