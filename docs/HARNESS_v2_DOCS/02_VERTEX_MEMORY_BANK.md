# 02 — Vertex AI Memory Bank

**ADK Agent Harness v2**

---

## What Memory Bank is

A managed service inside Vertex AI Agent Engine that stores **long-term user facts** — preferences, constraints, decisions, identities — that persist across sessions.

Not session state (that's GCS files, still v1). Not RAG documents (that's separate). **Durable, consolidated, scope-isolated user facts.**

What makes it different from a KV store:

- **Server-side extraction** — a Gemini model runs server-side and pulls facts out of raw conversation content.
- **Consolidation** — new facts that contradict existing ones become in-place `UPDATED` actions; the merged fact preserves both states ("I now use Go; previously, I preferred Python").
- **Scope isolation** — exact-match scope boundaries; zero cross-user leakage.
- **Semantic retrieval** — queries are natural-language strings; matches ranked by embedding similarity.

---

## The engine

Our Agent Engine resource:

```
projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976
```

(Project number `952978338090` corresponds to project ID `ninth-potion-455712-g9`. GCP uses the number in resource names.)

Provisioned via `memory_bank_discovery/setup_agent_engine.py`, tuned via `memory_bank_discovery/scripts/update_engine_config.py`. See [03_ENGINE_TUNING.md](03_ENGINE_TUNING.md) for the tuning details.

---

## Architecture — read path

**Goal:** every user turn gets relevant past memories injected into the system prompt as ambient context.

```
User message
      │
      ▼
PreloadMemoryTopK tool  (runs before every LLM request)
      │   scope = {app_name, user_id} from session
      │   top_k  = from memory_config.json (default 10)
      │
      ▼
client.agent_engines.memories.retrieve(
    name=AGENT_ENGINE_ID,
    scope=scope,
    similarity_search_params={
        "search_query": user_message,
        "top_k": 10,
    },
)
      │
      ▼
<PAST_CONVERSATIONS>
- fact 1
- fact 2
- ...
</PAST_CONVERSATIONS>
      │
      ▼
Injected into system prompt → LLM sees relevant memories
```

We use a **custom tool** rather than ADK's shipped `preload_memory_tool` because the shipped one hardcodes `top_k` to the server default of 3. See [06_GOTCHAS_AND_LIMITATIONS.md](06_GOTCHAS_AND_LIMITATIONS.md) for why.

---

## Architecture — write path

**Goal:** conversations get distilled into durable facts without the user having to explicitly save anything.

```
Turn N ends (agent finished responding)
      │
      ▼
after_agent_callback = persist_session_to_memory_callback
      │   increments session.state["memory_turn_count"]
      │   if turn_count % EXTRACT_EVERY_N_TURNS != 0 → skip
      │
      ▼
memory_service.add_session_to_memory(session)
      │
      ▼
VertexAiMemoryBankService.add_session_to_memory
      │   converts session.events → direct_contents_source.events
      │   calls memories:generate with scope={app_name, user_id}
      │
      ▼
Server-side Gemini extraction
      │   uses engine's context_spec:
      │     - 4 managed topics + 4 custom topics
      │     - 3 few-shot examples
      │   consolidates against existing memories (UPDATE in place)
      │
      ▼
New/updated memories persisted in the bank
```

The gate (`EXTRACT_EVERY_N_TURNS = 2`) exists because each `generate()` call takes ~13-17s and costs real $. Server-side consolidation (Test 6 finding) makes re-extraction across gated windows safe — redundant extractions produce `UPDATED` actions, not duplicates.

---

## Scope shape

The scope dict identifies WHICH user/app a memory belongs to. Exact-match only — no prefix matching, no wildcards.

| Context | Scope |
|---|---|
| Jarvis reads/writes (via ADK session service) | `{"app_name": "jarvis_agent", "user_id": "<session.user_id>"}` |
| Discovery scripts (historical) | `{"user_id": "<name>"}` — single-key, not compatible with the Jarvis ADK path |
| v3 OpenBrain MCP (planned) | `{"user_id": "<name>"}` — single-key shared across all agents |

The mismatch between v2 Jarvis (two-key) and discovery scripts (single-key) means legacy discovery memories are invisible to Jarvis. This is intentional — the discovery data was for testing, not production use.

---

## What Memory Bank is NOT

- **Not ephemeral session state.** Use GCS session files (v1) for per-session conversational state.
- **Not RAG.** Memory Bank is for facts distilled from conversation. RAG is for document ingestion + retrieval. They can coexist but solve different problems.
- **Not a vector database you control.** The server owns storage, embedding, extraction, and consolidation. You configure policy (topics, TTL, model); you don't run the index.
- **Not instant.** `generate()` is 13-17s per call because of the server-side extraction step. Plan for gated writes.

---

## Client SDK and version

- `google-cloud-aiplatform == 1.111.0` (Memory Bank customization features require ≥ 1.104.0)
- `google-adk == 1.13.0` (ships `VertexAiMemoryBankService` + `preload_memory_tool`)

Direct API access:
```python
import vertexai
client = vertexai.Client(project="ninth-potion-455712-g9", location="us-central1")
client.agent_engines.memories.create(...)
client.agent_engines.memories.retrieve(...)
client.agent_engines.memories.generate(...)
client.agent_engines.memories.list(...)
client.agent_engines.memories.get(...)
client.agent_engines.memories.delete(...)
client.agent_engines.update(...)   # for context_spec changes
client.agent_engines.get(...)      # for inspection
```

All of these are exercised by scripts in `memory_bank_discovery/` — see [05_MEMORY_TOOLKIT.md](05_MEMORY_TOOLKIT.md).
