# Research Report: Vertex AI Memory Bank + RAG Engine

**Date:** 2026-04-14
**Status:** Phase 2 planning — research only
**Author:** [CC] Claude Code

---

## Executive Summary

Three memory solutions for agent continuity — each serves a different purpose:

| Solution | Purpose | Status | Phase |
|----------|---------|--------|-------|
| **Vertex Memory Bank** | Remember users — preferences, history, personalization | GA since late 2025 | Phase 2 |
| **Vertex RAG Engine** | Ground agents in knowledge — docs, manuals, product data | GA (most regions) | Phase 2 |
| **GCS Session Files** | Raw session dumps — what we have now | Working | Keep as-is |

**Memory Bank and RAG Engine are complementary, not competing.** Memory Bank = "remember the user." RAG Engine = "ground in knowledge." An agent can use both.

**The Open Brain concept maps to:** Memory Bank for agent-written facts + RAG Engine for shared knowledge. MCP portability is possible via a community MCP server (early stage).

---

## Vertex AI Memory Bank

### What It Is

A managed service within Vertex AI Agent Engine that dynamically generates long-term memories from agent conversations. Uses Gemini to extract meaningful facts, consolidate them with existing memories, and retrieve them via semantic search.

**Solves:** Agent amnesia between sessions. Every new session no longer starts from zero.

### How It Works — Three Stages

```
Conversation happens
        ↓
[1] EXTRACTION — Gemini analyzes conversation, extracts facts
    "User prefers dark mode"
    "Project uses Next.js 15"
        ↓
[2] CONSOLIDATION — Merges with existing memories
    Deduplication + contradiction resolution (automatic, LLM-powered)
        ↓
[3] RETRIEVAL — Semantic search scoped to user/agent identity
    Agent gets relevant memories injected into context
```

Memory generation is **asynchronous** — the agent doesn't block waiting for extraction.

### Memory Structure

Each memory is a scoped fact:
```json
{
  "scope": {
    "agent_name": "architect_agent",
    "user": "tony_stark"
  },
  "fact": "User prefers Next.js App Router, Zustand for state, no Redux."
}
```

### Built-in Memory Topics

| Topic | What It Captures |
|-------|-----------------|
| `USER_PERSONAL_INFO` | Personal details, relationships, hobbies |
| `USER_PREFERENCES` | Likes, dislikes, preferred styles |
| `KEY_CONVERSATION_DETAILS` | Important milestones, task outcomes |
| `EXPLICIT_INSTRUCTIONS` | User's "remember this" / "forget that" requests |

Custom topics are also supported (you define label + description).

### Memory Write Methods

1. **Auto-generated from sessions** — Gemini extracts facts from conversation history
2. **Pre-extracted facts** — You supply facts, Memory Bank handles consolidation
3. **Direct create** — Bypass extraction, write a fact directly via API

### Scope Management

Memories are scoped per identity — no cross-user leakage:

```python
scope = {"user_id": "tony_stark"}                    # Per-user
scope = {"agent_name": "architect_agent"}             # Per-agent
scope = {"user_id": "tony", "app_name": "harness"}   # Per-user-per-app
```

**Per-user memory:** Yes
**Per-agent memory:** Yes
**Shared across agents for same user:** Yes (use same `user_id` scope)
**Shared across all users (global knowledge):** No — use RAG Engine for that

---

## ADK Integration — First-Class Support

Memory Bank has direct ADK integration via `VertexAiMemoryBankService`.

### Memory Service

```python
from google.adk.memory import VertexAiMemoryBankService

memory_service = VertexAiMemoryBankService(
    project="PROJECT_ID",
    location="us-central1",
    agent_engine_id="AGENT_ENGINE_ID"
)

runner = adk.Runner(
    agent=agent,
    app_name="APP_NAME",
    session_service=session_service,
    memory_service=memory_service     # ← plug in here
)
```

### Two Built-in Memory Tools

| Tool | Behavior | When to Use |
|------|----------|-------------|
| `PreloadMemoryTool` | Auto-retrieves memories at start of every turn, injects into system instruction | When you always want user context |
| `LoadMemoryTool` | Agent calls it when it decides memory would help | When you want selective retrieval (cheaper) |

```python
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.load_memory_tool import LoadMemoryTool

tools = [PreloadMemoryTool(), LoadMemoryTool(), ...other_tools...]
```

### Auto-Save Callback

```python
async def generate_memories_callback(callback_context):
    await callback_context.add_events_to_memory(
        events=callback_context.session.events[-5:-1]
    )
    return None

agent = adk.Agent(
    after_agent_callback=generate_memories_callback,
    ...
)
```

### CLI Integration

```bash
adk web path/to/agents --memory_service_uri="agentengine://[agent_engine_id]"
```

### InMemoryMemoryService (for local dev)

For local prototyping without Cloud dependencies:
- Basic keyword matching (not semantic)
- No persistence (lost on restart)
- Zero configuration needed

---

## Vertex AI RAG Engine

### What It Is

A managed RAG pipeline that grounds agent responses in your documents. Supports GCS, Drive, Slack, Jira, SharePoint as data sources.

### Can Agents Write to It at Runtime?

**Yes:**
- `UploadRagFile` — upload individual files with chunking config
- `ImportRagFiles` — batch import from various sources
- `CreateCorpus` — create new corpora programmatically
- Full CRUD on files, metadata, and corpora

### ADK Integration

```python
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag

rag_tool = VertexAiRagRetrieval(
    name="retrieve_docs",
    description="Retrieve documentation from the knowledge base",
    rag_resources=[rag.RagResource(rag_corpus="projects/.../ragCorpora/...")]
)
```

**Limitation:** `VertexAiRagRetrieval` can only be used by itself within an agent instance — cannot be combined with certain other ADK tool types in the same agent (same sub-agent workaround as `google_search` may apply).

---

## Comparison Matrix

### Memory Bank vs. Supabase Chat History

| Dimension | Memory Bank | Supabase |
|-----------|------------|----------|
| Setup | Managed, ~10 lines of config | Schema design, migrations, connection pooling |
| Memory extraction | Automatic via Gemini | Manual — you write the logic |
| Consolidation | Automatic dedup/contradiction | Manual |
| Semantic search | Built-in | Requires pgvector + embeddings |
| Cost control | Per-retrieval pricing | Predictable DB cost |
| Flexibility | Limited to Memory Bank's model | Full SQL, any schema |
| Vendor lock-in | Google Cloud | Portable |
| Local dev | InMemoryMemoryService (basic) | Full local Supabase |

### Memory Bank vs. RAG Engine

| Dimension | Memory Bank | RAG Engine |
|-----------|------------|------------|
| Purpose | Dynamic per-user memory | Static knowledge base grounding |
| Data source | Conversations, agent-generated facts | Documents (GCS, Drive, Slack, Jira) |
| Writes at runtime | Core feature | Yes (UploadRagFile API) |
| Evolves over time | Automatic consolidation | Only on re-import |
| Scope | Per-user/per-agent | Per-corpus (shared) |
| Best for | "Remember the user" | "Ground in knowledge" |

### Memory Bank vs. Current GCS Session Files

| Dimension | Memory Bank | GCS Session Files |
|-----------|------------|-------------------|
| Intelligence | LLM-powered extraction/consolidation | Raw file storage |
| Search | Semantic similarity | Load and parse entire file |
| Deduplication | Automatic | Manual |
| Cost | $0.25/1K memories/month + retrieval | GCS storage (~$0.02/GB/month) |
| Setup | Agent Engine + config | Just GCS buckets |
| Latency | API call overhead | Direct file read |

---

## MCP Portability (Open Brain → Pocket)

**No official Google MCP server for Memory Bank yet.**

Community MCP server exists:
- **Repo:** `github.com/inardini/vertex-memory-bank-mcp` (Ivan Nardini, Google Dev Advocate — personal project)
- **Status:** Early stage (12 stars, Apache 2.0)
- **Tools exposed:** `initialize_memory_bank`, `generate_memories`, `retrieve_memories`, `create_memory`, `delete_memory`, `list_memories`

**ADK supports MCP natively** — so building a custom MCP server around Memory Bank is architecturally supported. The Open Brain concept (agent writes → Memory Bank stores → MCP server exposes → Claude CLI/co-work consumes) is achievable.

---

## Cost

| Component | Price | Notes |
|-----------|-------|-------|
| Memory storage | $0.25 / 1,000 memories/month | Stored memories |
| Memory retrieval | $0.50 / 1,000 retrievals | First 1,000/month FREE |
| Memory generation | Gemini token cost only | ~$0.0003–$0.001 per call |

**Estimated per active user (50 turns/day):** ~$8/month
- Storage: ~$0.25
- Retrieval: ~$7.00 (dominates if using PreloadMemoryTool every turn)
- Generation: ~$0.50

**Cost optimization:** Use `LoadMemoryTool` (agent decides when to retrieve) instead of `PreloadMemoryTool` (every turn) to cut retrieval costs by 50–80%.

---

## Maturity and Availability

| Attribute | Status |
|-----------|--------|
| Maturity | **GA (Generally Available)** |
| Billing active since | February 11, 2026 |
| SDK requirement | `google-cloud-aiplatform >= 1.111.0` |
| Regions | 20 regions including us-central1 |

### Known Limitations
- Requires an Agent Engine instance (cannot use standalone)
- Memory poisoning is a security concern (mitigate with Model Armor)
- No official MCP server (community project only)
- TTL and metadata support available for lifecycle management

---

## What Integration Would Look Like in Our Harness

### Prerequisites
1. `pip install google-cloud-aiplatform>=1.111.0`
2. Create an Agent Engine instance (one-time setup)
3. ADC auth (already have)

### Steps

**1. Create Agent Engine instance:**
```python
agent_engine = client.agent_engines.create(config={
    "context_spec": {
        "memory_bank_config": {
            "generation_config": {
                "model": "projects/.../models/gemini-2.5-flash"
            },
            "similarity_search_config": {
                "embedding_model": "projects/.../models/text-embedding-005"
            }
        }
    }
})
```

**2. Wire into agent (in agent.py):**
```python
from google.adk.memory import VertexAiMemoryBankService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

memory_service = VertexAiMemoryBankService(
    project=PROJECT_ID, location=LOCATION,
    agent_engine_id=AGENT_ENGINE_ID
)

# Add PreloadMemoryTool or LoadMemoryTool to agent tools
# Add after_agent_callback for auto-save
```

**3. Wire into Runner (in deployment code):**
```python
runner = adk.Runner(
    agent=root_agent,
    session_service=session_service,
    memory_service=memory_service
)
```

### What This Replaces
- Custom `read_session_memory` / `write_session_memory` tools (partially — may keep for raw dumps)
- Manual session file management overhead

### What This Does NOT Replace
- GCS-based system prompts (hot-reload is separate from memory)
- GCS-based skills and context docs (these are reference material, not user memory)
- Token receipt system (local logging)

---

## Mapping to Tony's Three-Layer Vision

| Layer | Tony's Vision | Technology |
|-------|--------------|-----------|
| Conversation continuity | Replace Supabase chat history | **Memory Bank** (auto-extraction, managed, semantic search) |
| Open Brain (shared knowledge) | Agents write structured data to shared store | **Memory Bank** (per-user scope shared across agents) + **RAG Engine** (for document-grounded shared knowledge) |
| MCP portability | User carries brain in pocket | **Memory Bank MCP server** (community project, or build custom) |

---

## Recommendation (for discussion — not a build decision)

**Phase 2 sequencing:**

1. **First:** Prototype Memory Bank with `architect_agent` — replace `read/write_session_memory` with `VertexAiMemoryBankService` + `LoadMemoryTool`. Keep GCS session files as raw backup.

2. **Second:** Wire in RAG Engine for the Open Brain shared knowledge store. This is where agents write structured knowledge that persists and is searchable.

3. **Third:** Build or adapt the community MCP server to expose Memory Bank + RAG data to external clients (Claude CLI, co-work, etc.).

**Keep intact:** GCS-based system prompts, skills, context docs. These serve a different purpose (hot-reload reference material) and should not be migrated to Memory Bank.

---

## Sources

- [Memory Bank Overview](https://docs.google.com/agent-builder/agent-engine/memory-bank/overview)
- [Memory Bank Quickstart (ADK)](https://docs.google.com/agent-builder/agent-engine/memory-bank/quickstart-adk)
- [Memory Bank Quickstart (API)](https://docs.google.com/agent-builder/agent-engine/memory-bank/quickstart-api)
- [Generate Memories](https://docs.google.com/agent-builder/agent-engine/memory-bank/generate-memories)
- [Set Up Memory Bank](https://docs.google.com/agent-builder/agent-engine/memory-bank/set-up)
- [Memory Bank Blog](https://cloud.google.com/blog/products/ai-machine-learning/vertex-ai-memory-bank-in-public-preview)
- [ADK Memory Documentation](https://adk.dev/sessions/memory/)
- [Using Long-term Memory in ADK (Medium)](https://medium.com/google-cloud/using-long-term-memory-in-agent-adk-vertex-ai-memory-bank-2d1e979b6197)
- [RAG Engine Overview](https://docs.google.com/vertex-ai/generative-ai/docs/rag-engine/rag-overview)
- [ADK RAG Engine Integration](https://google.github.io/adk-docs/integrations/vertex-ai-rag-engine/)
- [Build RAG Agent with ADK (Medium)](https://medium.com/google-cloud/build-a-rag-agent-using-google-adk-and-vertex-ai-rag-engine-bb1e6b1ee09d)
- [Community MCP Server](https://github.com/inardini/vertex-memory-bank-mcp)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)

---

*[CC] Claude Code — Research report, not a build plan. Implementation requires plan mode approval.*
