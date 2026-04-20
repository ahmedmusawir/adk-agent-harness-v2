# Vertex AI Memory Bank — End-to-End POC

**What this doc is:** a complete walk-through of how we went from zero to a working Vertex AI Memory Bank integration for an ADK agent, in one session. Built as both a YouTube-video script and a future reference I can come back to when I forget stuff.

**Date of the run:** 2026-04-19 to 2026-04-20
**Project:** `ninth-potion-455712-g9`
**Region:** `us-central1`
**Agent:** Jarvis (from the ADK Harness v2 repo)

---

## Table of Contents

1. [What is Vertex AI Memory Bank (and why care)](#1-what-is-vertex-ai-memory-bank-and-why-care)
2. [Prerequisites](#2-prerequisites)
3. [Set up the discovery sandbox](#3-set-up-the-discovery-sandbox)
4. [Test 1 — Provision the Agent Engine](#4-test-1--provision-the-agent-engine)
5. [Test 2 — Direct memory write](#5-test-2--direct-memory-write)
6. [Test 3 — Three read paths (list / get / retrieve)](#6-test-3--three-read-paths-list--get--retrieve)
7. [Test 4 — Session-based memory generation](#7-test-4--session-based-memory-generation)
8. [Test 5 — Multi-tenant isolation](#8-test-5--multi-tenant-isolation)
9. [Test 6 — Consolidation and contradiction](#9-test-6--consolidation-and-contradiction)
10. [Test 7a — Wire Memory Bank into the Jarvis agent](#10-test-7a--wire-memory-bank-into-the-jarvis-agent)
11. [Summary of findings](#11-summary-of-findings)
12. [Gotchas — things that bit us](#12-gotchas--things-that-bit-us)
13. [Future work](#13-future-work)

---

## 1. What is Vertex AI Memory Bank (and why care)

**Memory Bank** is a managed service inside Vertex AI's Agent Engine that stores *long-term user facts* for conversational agents. Not session state, not RAG documents — **durable facts about the user** that survive across sessions and accumulate coherently.

Why this matters: if you're building agents with ADK, you already have short-term session state and you probably have RAG for documents. The missing piece has been persistent user context — "the user prefers Python," "the user's timezone is Pacific," "the user is allergic to shellfish." Memory Bank is Google's answer to that gap.

What makes it different from a plain key-value store:
- A **Gemini model** runs server-side and extracts memories from conversation transcripts.
- Writes are **consolidated** — when a new fact contradicts an existing one, the service rewrites the memory in place and preserves the historical context.
- Memories are **scope-isolated** — one `user_id` never sees another `user_id`'s memories.
- Retrieval is **semantic** — you query with a natural-language string and get back relevant memories via embedding similarity.

The goal of this POC: verify all of this works as advertised and figure out how to wire it into a real ADK agent (Jarvis).

---

## 2. Prerequisites

Before you start:

- **GCP project** with Vertex AI API enabled.
- **Application Default Credentials** configured locally: `gcloud auth application-default login`.
- **Python 3.12**, virtualenv active.
- **Packages:** `google-cloud-aiplatform` (1.111.0 or newer), `google-adk` (1.13.0 or newer), `python-dotenv`.
- **Project ID + region** decided in advance. For this run:
  - Project: `ninth-potion-455712-g9`
  - Region: `us-central1`

Verify package versions:

```bash
pip show google-cloud-aiplatform google-adk | grep -E "^(Name|Version)"
```

Expected output:

```
Name: google-cloud-aiplatform
Version: 1.111.0
Name: google-adk
Version: 1.13.0
```

---

## 3. Set up the discovery sandbox

The whole point of a discovery phase is to poke at a new API in an isolated folder so a failed experiment can't break the main app.

**Sandbox layout:**

```
memory_bank_discovery/
├── docs/
│   ├── DISCOVERY_BRIEF.md      # the game plan
│   └── FINDINGS.md             # what we learned per test
├── scripts/
│   ├── test_write_memory.py
│   ├── test_read_memory.py
│   ├── test_generate_memories.py
│   ├── test_memory_isolation.py
│   ├── test_consolidation.py
│   ├── seed_jarvis_memory.py   # (added later in Test 7a)
│   └── run_jarvis_web.sh       # (added later in Test 7a)
├── .env                        # holds GCP_PROJECT_ID, GCP_REGION, AGENT_ENGINE_ID
├── README.md
├── setup_agent_engine.py       # one-time provisioning
└── list_agent_engines.py       # recovery helper
```

Critically: **no `__init__.py` and no `agent.py`** in this folder. That means `adk web` ignores it entirely — it won't show up as a loadable agent. This folder is a scratchpad, not a deployment target.

`memory_bank_discovery/.env` starts like this:

```
GCP_PROJECT_ID=ninth-potion-455712-g9
GCP_REGION=us-central1
AGENT_ENGINE_ID=
```

We'll fill in `AGENT_ENGINE_ID` after Test 1. The root `.gitignore` already ignores `.env` everywhere, so the nested file is automatically kept out of commits.

---

## 4. Test 1 — Provision the Agent Engine

### Why this test

Every Memory Bank sits inside an **Agent Engine** (Google's name; the underlying resource is called a `ReasoningEngine`). You can't write memories without one. Step 1 is provisioning.

### The script: `setup_agent_engine.py`

Minimal: instantiates a Vertex AI client and calls `client.agent_engines.create()` with no arguments. Google assigns defaults for the generation LLM and embedding model.

### Run it

```bash
python memory_bank_discovery/setup_agent_engine.py
```

### What happened on our first try — a real gotcha

The create call succeeded. The print statement afterward crashed:

```
Agent Engine created!
Traceback (most recent call last):
  ...
  File ".../setup_agent_engine.py", line 27, in main
    print(f"Resource name: {agent_engine.name}")
AttributeError: 'AgentEngine' object has no attribute 'name'
```

**What's going on:** the `AgentEngine` object returned from `create()` is a wrapper. The actual GCP resource (a `ReasoningEngine`) hangs off it as `.api_resource`. The resource name lives at `agent_engine.api_resource.name`, not `agent_engine.name`.

Confirmed by reading the SDK directly — `vertexai/_genai/types.py` defines `AgentEngine` with `api_resource: Optional[ReasoningEngine]` and its own `__repr__` uses `api_resource.name`. So the fix is a one-line attribute change, not a package upgrade.

### The fix

Patched `setup_agent_engine.py`:

```python
# Before (broken)
print(f"Resource name: {agent_engine.name}")

# After (works)
resource_name = agent_engine.api_resource.name
print(f"Resource name: {resource_name}")
```

### Recovering the already-provisioned engine (without creating a duplicate)

The first crash happened AFTER the engine was provisioned. Re-running `setup_agent_engine.py` would have created a second engine — wasteful and confusing. Instead, we wrote a tiny `list_agent_engines.py` helper to enumerate existing engines via `client.agent_engines.list()`:

```bash
python memory_bank_discovery/list_agent_engines.py
```

Output included this line (truncated):

```
[1] Resource name: projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976
```

**Observation — resource names are weird-looking but standard GCP:**

```
projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976
```

- `projects/952978338090` — the **project number** (not the human-readable ID `ninth-potion-455712-g9`). GCP uses numbers in fully-qualified resource names.
- `locations/us-central1` — the region.
- `reasoningEngines/6954288450136702976` — the engine ID.

You paste the **whole thing, verbatim, with every slash** into `.env`:

```
AGENT_ENGINE_ID=projects/952978338090/locations/us-central1/reasoningEngines/6954288450136702976
```

No quotes, no trimming.

### What we learned in Test 1

- `AgentEngine` wrapper has no `.name` — use `.api_resource.name`.
- Before re-running `create()` after a failure, use `list_agent_engines.py` to see if the engine already exists.
- Resource names use the numeric project number, not the human-readable project ID.

---

## 5. Test 2 — Direct memory write

### Why this test

Prove we can push a single fact into the bank using the direct-write API. No LLM, no extraction — just a synchronous store.

### The script: `test_write_memory.py`

Calls `client.agent_engines.memories.create(...)` with three required args: `name` (engine resource name), `fact` (string), and `scope` (dict).

The transcript we sent:

```python
client.agent_engines.memories.create(
    name=AGENT_ENGINE_ID,
    fact="Tony prefers Python for backend development",
    scope={"user_id": "tony_stark"},
)
```

### Run it

```bash
python memory_bank_discovery/scripts/test_write_memory.py
```

### Expected output (trimmed to the interesting parts)

```
TEST 2 - Direct Memory Write
======================================================================
Scope:      {'user_id': 'tony_stark'}
Fact:       Tony prefers Python for backend development
----------------------------------------------------------------------
Calling client.agent_engines.memories.create() ...
/.../test_write_memory.py:51: ExperimentalWarning: The Vertex SDK GenAI agent engines module is experimental, and may change in future versions.
  operation = client.agent_engines.memories.create(
----------------------------------------------------------------------
SUCCESS - memories.create() returned without raising.
----------------------------------------------------------------------
operation.name:     projects/.../reasoningEngines/6954288450136702976/memories/3072711962535133184/operations/6701462528788004864
operation.done:     True
operation.error:    None
operation.response: Memory(
  create_time=datetime.datetime(2026, 4, 19, 7, 19, 40, 586266, tzinfo=TzInfo(UTC)),
  fact='Tony prefers Python for backend development',
  name='projects/.../reasoningEngines/6954288450136702976/memories/3072711962535133184',
  scope={'user_id': 'tony_stark'},
  update_time=datetime.datetime(2026, 4, 19, 7, 19, 40, 586266, tzinfo=TzInfo(UTC))
)
```

### What to notice

- **Two `ExperimentalWarning`s.** These fire on EVERY call to `agent_engines.memories.*`. They're safe to ignore — don't treat them as errors.
- **`operation.done = True`** — the SDK defaults `wait_for_completion=True`, which polls internally until the server-side operation finishes. No separate `.get()` call needed.
- **`operation.response`** is a fully-hydrated `Memory` object — it has `name`, `fact`, `scope`, `create_time`, `update_time` all populated. This is the "happy path" return shape.
- **Memory resource name shape:** `{engine}/memories/{memory_id}`. Memory IDs are 19-digit integers, same shape as engine IDs.
- **Operation resource name** is nested under the memory: `.../memories/{id}/operations/{op_id}`. That nesting means "this operation belongs to this memory."

### What we learned in Test 2

- `memories.create()` returns a hydrated `Memory` inside `operation.response`.
- `wait_for_completion=True` is the default and makes life easy — it blocks until done.
- Timestamps are UTC with microsecond precision.
- On a fresh write, `create_time == update_time`.

---

## 6. Test 3 — Three read paths (list / get / retrieve)

### Why this test

There are three different read APIs and they behave differently. Understanding when to use which matters.

### The three paths

| API | Input | Returns | Purpose |
|---|---|---|---|
| `memories.list(name=ENGINE)` | engine resource name | `Pager[Memory]` | Full enumeration across all scopes — admin view |
| `memories.get(name=MEMORY)` | full memory resource name | `Memory` | Direct fetch by memory ID |
| `memories.retrieve(name=ENGINE, scope=...)` | engine + scope dict | `Iterator[RetrieveMemoriesResponseRetrievedMemory]` | Scope-filtered query — agent runtime pattern |

### The script: `test_read_memory.py`

Exercises all three in one run. First does `list()` to get any memory name, then `get()`s that name, then `retrieve()`s by scope.

### Run it

```bash
python memory_bank_discovery/scripts/test_read_memory.py
```

### Expected output (trimmed)

```
[1/3] memories.list(name=ENGINE)
Returned 1 memory record(s).
  name:        projects/.../memories/3072711962535133184
  fact:        Tony prefers Python for backend development
  scope:       {'user_id': 'tony_stark'}

[2/3] memories.get(name=MEMORY_RESOURCE_NAME)
Fetching: projects/.../memories/3072711962535133184
Returned Memory: (same shape as list item)

[3/3] memories.retrieve(name=ENGINE, scope=...)
Returned 1 retrieved-memory record(s).
--- Retrieved [1/1] ---
  memory: Memory(...)
  distance: None

SUMMARY
  list       PASS
  get        PASS
  retrieve   PASS
```

### What to notice

- **All three return byte-identical `Memory` objects** for the same record. No read-path discrepancies.
- **`retrieve` returns a wrapper** — `RetrieveMemoriesResponseRetrievedMemory` with `.memory` (the actual `Memory`) and `.distance` (similarity score).
- **`distance=None`** because we didn't pass `similarity_search_params`. Distance scoring only activates with explicit similarity params.
- **`retrieve(scope=...)` is the agent-runtime pattern** — agents query by the current user/session scope, not by a specific memory ID.

### What we learned in Test 3

- `list` returns a lazy `Pager` — materialize with `list(...)` if you want a count.
- `get` is synchronous and returns `Memory` directly (not wrapped in an operation like create).
- `retrieve` without similarity params is a pure scope filter; with similarity params it ranks by distance.

---

## 7. Test 4 — Session-based memory generation

### Why this test

This is the headline feature. We hand Memory Bank a chat transcript and it extracts memories automatically using a server-side Gemini model.

### The script: `test_generate_memories.py`

Builds a three-turn transcript with `google.genai.types.Content` objects, then calls `client.agent_engines.memories.generate(...)`:

```python
TRANSCRIPT = [
    ("user",  "My favorite coffee shop is Stark Brewery on 5th avenue."),
    ("model", "Noted."),
    ("user",  "I usually order a flat white with oat milk."),
]

operation = client.agent_engines.memories.generate(
    name=AGENT_ENGINE_ID,
    direct_contents_source={"events": events},
    scope={"user_id": "tony_stark"},
    # config defaults: wait_for_completion=True, disable_consolidation=None (ON)
)
```

Three possible source types for generate:
- `vertex_session_source` — needs a pre-existing Session resource.
- `direct_contents_source` — hand over a transcript directly. **We use this.**
- `direct_memories_source` — bulk upload of pre-written facts.

### Run it

```bash
python memory_bank_discovery/scripts/test_generate_memories.py
```

### What came back — first surprise

```
SUCCESS - generate() returned in 16.70s.
operation.name:     projects/.../reasoningEngines/.../operations/5861066209260208128
operation.done:     True
operation.error:    None

generated_memories: 1 item(s)

--- Generated [1/1] ---
  action:       GenerateMemoriesResponseGeneratedMemoryAction.CREATED
  memory.name:        projects/.../memories/2993336019102728192
  memory.fact:        None
  memory.scope:       None
  memory.create_time: None
  memory.update_time: None
```

**Wait — the fact is None?** The service said `CREATED` and gave us a memory name, but the `Memory` object inside is missing every other field.

### The gotcha — skeletal response

`generate()` returns a **skeletal** `Memory` on the response. Only `.name` is populated. To see the actual extracted fact, you have to call `memories.get(name=...)` afterward.

This is asymmetric with `create()`, which returns a fully-hydrated `Memory`. Not a bug — just an API inconsistency to know about.

### Hydrating the generated memory

Easiest way: re-run `test_read_memory.py`. The `list` step will show both memories, fully hydrated.

```bash
python memory_bank_discovery/scripts/test_read_memory.py
```

Now we see:

```
Returned 2 memory record(s).

--- Memory [1/2] ---
  name:  projects/.../memories/2993336019102728192
  fact:  I usually order a flat white with oat milk.
  scope: {'user_id': 'tony_stark'}

--- Memory [2/2] ---
  name:  projects/.../memories/3072711962535133184
  fact:  Tony prefers Python for backend development
  scope: {'user_id': 'tony_stark'}
```

### What to notice

We gave the service TWO user facts in the transcript:

| User said | Extracted? |
|---|---|
| "My favorite coffee shop is Stark Brewery on 5th avenue." | No — dropped |
| "I usually order a flat white with oat milk." | Yes |

**Only one was captured.** The coffee shop fact was silently dropped.

Even more interesting — the extracted fact is **verbatim, first-person**:

- Stored fact: `"I usually order a flat white with oat milk."`
- Note the `I` pronoun — it's not rewritten to "Tony usually orders...".

Compare with the manual Test 2 write, which stored `"Tony prefers Python for backend development"` (third-person). The generation pipeline preserves the speaker's voice, keeping first-person pronouns.

### What we learned in Test 4

- `generate()` response is **skeletal** — only `memory.name` is populated; must `get()` to hydrate.
- Extraction is **selective, not exhaustive**. Don't assume every user statement becomes a memory.
- Extracted facts are **first-person, verbatim** from the user turn.
- Server-side extraction took ~3.25s (metadata delta). Total wall-clock ~16.7s — the rest was client-side polling.
- Operation resource name is **engine-level** (`.../reasoningEngines/.../operations/...`), not nested under any memory (because generate can produce multiple memories).

---

## 8. Test 5 — Multi-tenant isolation

### Why this test

If I'm running an agent that serves multiple users, I need to know their memories are isolated. A leak would be a privacy disaster. This test proves `retrieve()` respects scope boundaries.

### The script: `test_memory_isolation.py`

Four steps plus three assertions:

1. Write a memory under a NEW user: `scope={"user_id": "peter_parker"}`, fact = `"Peter prefers Rust for systems programming"`.
2. `list(name=ENGINE)` — returns everything (admin view).
3. `retrieve()` three times: as tony, as peter, as nobody.
4. Assert:
   - **A1** (critical): `tony_set ∩ peter_set == ∅` (no overlap)
   - **A2**: `nobody_set == ∅` (unknown scope returns empty, not wildcard)
   - **A3**: Peter's new memory is in `peter_set`

### Run it

```bash
python memory_bank_discovery/scripts/test_memory_isolation.py
```

### Expected output (the key bits)

```
[2/4] list(name=ENGINE) - unscoped
Total memories on engine: 3

  scope={'user_id': 'peter_parker'}:
    - Peter prefers Rust for systems programming

  scope={'user_id': 'tony_stark'}:
    - I usually order a flat white with oat milk.
    - Tony prefers Python for backend development

[3/4] retrieve(scope=...) x 3
  scope {'user_id': 'tony_stark'} -> 2 memory(ies)
  scope {'user_id': 'peter_parker'} -> 1 memory(ies)
  scope {'user_id': 'nobody_exists'} -> 0 memory(ies)

[4/4] ASSERTIONS
A1 PASS: tony_set and peter_set are disjoint (no cross-user leak).
A2 PASS: retrieve(nobody_exists) returned 0 memories.
A3 PASS: newly-written Peter memory is retrievable under Peter's scope.
```

### What to notice

- **`list()` with no scope is an admin view** — returns memories from every `user_id`. Don't use this in agent-runtime code where tenant isolation matters.
- **`retrieve()` is exact-match strict** — unknown scope returns empty iterator, not a wildcard match. So you can't "accidentally" return someone else's memories by misspelling a scope key.
- **No per-user provisioning step.** The first time you `create()` under a new `user_id`, the service just accepts it. There's no "register user" call.

### What we learned in Test 5

- Memory Bank is **multi-tenant safe** when scoped by `user_id`.
- `retrieve()` is exact-match on scope, not prefix/wildcard.
- A single Agent Engine can serve many users — no per-user setup needed.

---

## 9. Test 6 — Consolidation and contradiction

### Why this test

The "wow moment" of this POC. When a new fact contradicts an existing memory, what does Memory Bank actually do? Delete the old one? Create a new one alongside? Or something smarter?

### The script: `test_consolidation.py`

A four-phase script:

1. **BEFORE** — snapshot tony's memories via `retrieve()`
2. **GENERATE** — send a contradicting transcript
3. **AFTER** — snapshot tony's memories again
4. **DIFF** — compute disappeared / appeared / changed sets, cross-check against the actions the service reported

The contradicting transcript:

```
user:  "Actually I've ditched Python - I'm using Go for all my backend work now."
model: "Got it, Go for backend."
```

This directly contradicts M1 (`"Tony prefers Python for backend development"`).

### Run it

```bash
python memory_bank_discovery/scripts/test_consolidation.py
```

### The result — strong consolidation

```
BEFORE: 2 memory(ies)
  [3072711962535133184] Tony prefers Python for backend development
  [2993336019102728192] I usually order a flat white with oat milk.

generate() returned in 12.57s.
Service reported 1 action(s):
  [1] action=GenerateMemoriesResponseGeneratedMemoryAction.UPDATED  memory=[3072711962535133184]

AFTER: 2 memory(ies)
  [3072711962535133184] I now use Go for all my backend work; previously, I preferred Python for backend development.
  [2993336019102728192] I usually order a flat white with oat milk.

Disappeared: 0
Appeared: 0
Changed: 1
  [3072711962535133184]
    BEFORE: 'Tony prefers Python for backend development'
    AFTER:  'I now use Go for all my backend work; previously, I preferred Python for backend development.'

OUTCOME classification:
  -> STRONG CONSOLIDATION: an existing memory was DELETED or UPDATED.
```

### What just happened — four things worth calling out

1. **`UPDATED` action on the same memory ID.** The service mutated M1 in place instead of deleting and re-creating. The resource name `3072711962535133184` stays stable — downstream consumers tracking memory IDs don't break.

2. **The rewritten fact preserves BOTH states**:
   - Current: *"I now use Go for all my backend work"*
   - Historical: *"previously, I preferred Python for backend development"*
   - Joined by a semicolon.

3. **Voice was normalized to first-person.** The original fact was third-person ("Tony prefers..."). The updated fact is first-person ("I now use..."). So voice normalization is **one-way** — any write that goes through `generate()` (including UPDATE) ends up first-person, regardless of what the prior text looked like.

4. **The unrelated coffee memory was untouched.** Consolidation is topic-scoped, not user-scoped. The service only reconciled the memory that was actually relevant to the new fact.

### Why this is huge for agent integration

You don't need to write dedup logic. You don't need contradiction detection. You don't need conflict resolution. Just feed transcripts to `generate()` and the service keeps user context coherent, deduplicated, and history-aware.

### What we learned in Test 6

- Consolidation is **STRONG and IN-PLACE**. Memory IDs are stable across updates.
- Both the current AND historical state are preserved in the updated fact, semicolon-separated.
- Voice normalization on UPDATE is one-way (always first-person).
- Topically-unrelated memories in the same scope are not touched.
- No client-side dedup logic needed.

---

## 10. Test 7a — Wire Memory Bank into the Jarvis agent

### Why this test

Up to now, everything has been direct SDK calls. The real goal is an ADK agent that reads from and writes to Memory Bank automatically. This is where rubber meets the road.

### What ADK provides (verified in the installed source)

Three pieces already live in `google.adk`:

- **`VertexAiMemoryBankService`** at `google/adk/memory/vertex_ai_memory_bank_service.py` — the first-party connector. Wraps `memories:generate` (write) and `memories:retrieve` (read).
- **`preload_memory_tool`** — runs SILENTLY before every LLM request. Uses the current user message as a search query, injects matching memories into the system prompt as `<PAST_CONVERSATIONS>`. No model-side tool calls.
- **`load_memory_tool`** — the explicit, model-decided alternative. Model chooses when to search by calling a tool.

For discovery we pick `preload_memory_tool`: every user message triggers a retrieval automatically, making the behavior deterministic and easy to verify.

### Two critical findings before wiring

**1. Scope mismatch with our existing memories.**

ADK's service writes with `scope={"app_name": session.app_name, "user_id": session.user_id}` — TWO keys. Our Tests 2–6 memories use single-key `scope={"user_id": "..."}`. Since retrieve is exact-match (Test 5), Jarvis will NOT see any of the old memories. It starts with a clean slate.

**2. ADK does NOT auto-write sessions to memory.**

Grep confirms: `adk web` and `adk api_server` wire up the read path but never call `add_session_to_memory`. Writing a conversation to memory requires either a custom runner script OR a post-session hook. **For Test 7a we only wire the read side.** Writing is a follow-up (Test 7b).

### Step 1 — Seed a Jarvis-scoped memory

Because Jarvis can't see the old memories, we pre-seed one with the correct scope. Fact is deliberately fictional and unique so we can tell when Jarvis retrieves it vs. hallucinates.

File: `memory_bank_discovery/scripts/seed_jarvis_memory.py`

Scope: `{"app_name": "jarvis_agent", "user_id": "tony_stark"}`
Fact: `"Tony's workshop mainframe runs a custom Linux distribution called 'StarkOS-17'."`

**Run it:**

```bash
python memory_bank_discovery/scripts/seed_jarvis_memory.py
```

Expected output:

```
Seeding Jarvis-scoped memory
Project:  ninth-potion-455712-g9
Location: us-central1
Engine:   projects/.../reasoningEngines/6954288450136702976
Scope:    {'app_name': 'jarvis_agent', 'user_id': 'tony_stark'}
Fact:     Tony's workshop mainframe runs a custom Linux distribution called 'StarkOS-17'.

Seeded.
  memory.name:  projects/.../memories/<new_id>
  memory.fact:  Tony's workshop mainframe runs a custom Linux distribution called 'StarkOS-17'.
  memory.scope: {'app_name': 'jarvis_agent', 'user_id': 'tony_stark'}
```

### Step 2 — Add `preload_memory_tool` to Jarvis

Only change in `jarvis_agent/agent.py`: import the tool and add it to the `tools` list. Everything else (model, instruction callable, receipt callbacks) stays exactly the same.

```python
from google.adk.tools.preload_memory_tool import preload_memory_tool

root_agent = Agent(
    name="jarvis_agent",
    model="gemini-2.5-flash",
    description="Jarvis agent",
    instruction=get_live_instructions,
    tools=[google_search, preload_memory_tool],   # <-- preload added
    before_model_callback=get_start_time_callback(),
    after_model_callback=get_receipt_callback(...),
)
```

### Step 3 — Start `adk web` with the memory service URI

ADK accepts the memory service as a CLI flag:

```
--memory_service_uri=agentengine://<agent_engine_id>
```

Both short-form ID and full resource name work. We wrote a shell script so we don't have to remember it every time.

File: `memory_bank_discovery/scripts/run_jarvis_web.sh`

Key line:

```bash
exec adk web --memory_service_uri="agentengine://$AGENT_ENGINE_ID" .
```

**Run it:**

```bash
bash memory_bank_discovery/scripts/run_jarvis_web.sh
```

Expected startup logs include:

```
Starting adk web with Memory Bank wired in.
  Engine: projects/.../reasoningEngines/6954288450136702976
```

...followed by the normal ADK web server logs and a URL to open in the browser.

### Step 4 — Verify retrieval works

In the ADK web UI:

1. Select **jarvis_agent**.
2. **Set the user_id to `tony_stark`** — this is critical. The seed was scoped to `user_id=tony_stark`; if ADK's default user_id (often `user`) doesn't match, retrieval will miss.
3. Paste this message:

```
What OS is my workshop mainframe running?
```

**Expect:** Jarvis responds with "StarkOS-17" somewhere in the answer. If it says "I don't know" or invents a different name, memory retrieval didn't fire — check the user_id and confirm `adk web` was started via `run_jarvis_web.sh` (not plain `adk web`).

### What just happened under the hood

1. Tony typed the question.
2. `preload_memory_tool` intercepted the LLM request.
3. It called `memory_service.search_memory(app_name="jarvis_agent", user_id="tony_stark", query="What OS is my workshop mainframe running?")`.
4. `VertexAiMemoryBankService` translated that into `memories:retrieve` with `similarity_search_params.search_query` = the question.
5. The embedding model (default: `text-embedding-005`) found the seeded memory as a semantic match.
6. The memory's fact was injected into the LLM system prompt inside a `<PAST_CONVERSATIONS>` block.
7. Jarvis saw the fact and used it in its answer.

### What we learned in Test 7a

- ADK's `preload_memory_tool` + `--memory_service_uri` flag is the low-ceremony way to wire Memory Bank in.
- **Scope must match.** ADK writes/reads with two keys (`app_name` + `user_id`). Seed memories with the same scope shape, or you'll miss them.
- **user_id is set in the ADK web UI** — don't assume the default is your test user.
- ADK does NOT auto-write sessions to memory. That's Test 7b (not done yet).

---

## 11. Summary of findings

The 10 key takeaways from this POC, in one place:

1. **`AgentEngine` wrapper is not the GCP resource.** Resource name lives at `.api_resource.name`, not `.name`.
2. **Project NUMBER, not project ID, appears in resource names.** Same project, just different surface.
3. **Experimental warnings on every call are benign.** Don't treat as errors.
4. **`wait_for_completion=True` is the default** and makes create/generate synchronous from the caller's perspective.
5. **`create()` returns a hydrated `Memory`; `generate()` returns a skeletal one** (name-only). For `generate()`, follow up with `get()` to see facts.
6. **Extraction is selective, not exhaustive.** The generation model silently drops facts it doesn't consider salient. Don't assume every user statement becomes a memory.
7. **Generated/updated facts are always first-person, verbatim.** Voice normalization is one-way.
8. **Memories are scope-isolated and exact-match strict.** Multi-tenant safe. Unknown scopes return empty iterators.
9. **Consolidation is STRONG and IN-PLACE.** Contradictions become `UPDATED` actions on the same memory ID. The new fact captures both current AND historical state.
10. **ADK ships a first-party connector** (`VertexAiMemoryBankService`). Wire it via `adk web --memory_service_uri=agentengine://<engine_id>`. But you still have to manually trigger writes — no auto-write at session close.

---

## 12. Gotchas — things that bit us

| # | Gotcha | How to avoid |
|---|---|---|
| 1 | `agent_engine.name` is not a thing | Use `agent_engine.api_resource.name` |
| 2 | First run of `setup_agent_engine.py` can create an engine even if the print crashes | Check `list_agent_engines.py` before re-running `create()` |
| 3 | `generate()` response has `fact=None`, `scope=None` on the returned `Memory` | Call `get()` or `list()` afterward to hydrate |
| 4 | 1 of 2 user facts silently dropped by default generation model | Don't assume exhaustive extraction — write important facts via `create()` directly if they must persist |
| 5 | Generated facts are first-person ("I...") — does not match manual third-person writes ("Tony...") | Either accept mixed voice or post-process agent prompts to handle it |
| 6 | ADK writes memories with `{app_name, user_id}` but our direct-SDK tests used `{user_id}` only | Seed agent-facing memories with both keys |
| 7 | `adk web` / `adk api_server` do NOT auto-write sessions to memory | Need a custom runner or post-session hook (Test 7b) |
| 8 | ADK web's default user_id may not be `tony_stark` or whatever you seeded | Set user_id explicitly in the web UI before chatting |
| 9 | `retrieve()` with unknown scope returns 0, not an error | Don't use "did it error?" as a scope-match check — check the iterator length |
| 10 | Nested `.env` files aren't gitignored by default if the top-level `.gitignore` uses a narrow pattern | Our repo's `.gitignore` includes `.env`, so nested ones are covered — but verify with `git check-ignore` before committing |

---

## 13. Future work

### Test 7b — Write-side integration (not yet done)

ADK doesn't auto-call `add_session_to_memory`. We need either:
- A custom Python runner script that invokes Jarvis, then calls `memory_service.add_session_to_memory(session)` after the turn.
- A post-session callback wired at the agent level.

This closes the loop: Tony chats → agent reads existing memories → agent responds → agent writes new memories from the conversation.

### Other open questions worth probing

- **`disable_consolidation=True`** — does it actually skip the merge, letting contradictions pile up as separate memories?
- **`similarity_search_params`** on `retrieve()` — what does `.distance` look like when populated? What are the `search_query` / `top_k` knobs?
- **Multi-key scope matching** — if I retrieve with `{"user_id": "tony_stark"}` but the memories are stored with `{"app_name": "jarvis_agent", "user_id": "tony_stark"}`, does retrieve do exact-match on the whole dict, or is there subset-match behavior anywhere?
- **Multiple contradicting facts in one transcript** — does the service chain consolidations or merge all into one action?
- **`DELETED` action** — does it ever actually fire? Would require a user to explicitly retract a fact.
- **Generation model control** — set `context_spec.memory_bank_config.generation_config.model` when provisioning to pick Gemini Flash vs. Pro. Does extraction quality change?
- **TTL / automatic memory expiry** — `context_spec.memory_bank_config.ttl_config` is a thing but untested.

---

## Appendix: File index

Everything created during this POC:

```
memory_bank_discovery/
├── .env                                        GCP_PROJECT_ID / GCP_REGION / AGENT_ENGINE_ID
├── README.md
├── setup_agent_engine.py                       one-time Agent Engine provisioning
├── list_agent_engines.py                       recovery helper
├── docs/
│   ├── DISCOVERY_BRIEF.md
│   └── FINDINGS.md                             detailed per-test findings
└── scripts/
    ├── test_write_memory.py                    Test 2: direct write
    ├── test_read_memory.py                     Test 3: list / get / retrieve
    ├── test_generate_memories.py               Test 4: session-based generation
    ├── test_memory_isolation.py                Test 5: multi-tenant scoping
    ├── test_consolidation.py                   Test 6: contradiction handling
    ├── seed_jarvis_memory.py                   Test 7a: pre-seed Jarvis memory
    └── run_jarvis_web.sh                       Test 7a: start adk web with memory URI
```

Agent-side change:

```
jarvis_agent/agent.py                           added preload_memory_tool to tools list
```

Commands in the order they were run:

```bash
# Prep
pip show google-cloud-aiplatform google-adk | grep -E "^(Name|Version)"

# Test 1: provision
python memory_bank_discovery/setup_agent_engine.py         # first attempt — failed mid-print
python memory_bank_discovery/list_agent_engines.py         # recovery — grab the engine name
# (paste resource name into memory_bank_discovery/.env)

# Test 2: write
python memory_bank_discovery/scripts/test_write_memory.py

# Test 3: read (all three paths)
python memory_bank_discovery/scripts/test_read_memory.py

# Test 4: generate
python memory_bank_discovery/scripts/test_generate_memories.py
python memory_bank_discovery/scripts/test_read_memory.py   # re-run to hydrate generate() output

# Test 5: isolation
python memory_bank_discovery/scripts/test_memory_isolation.py

# Test 6: consolidation
python memory_bank_discovery/scripts/test_consolidation.py

# Test 7a: Jarvis integration
python memory_bank_discovery/scripts/seed_jarvis_memory.py
bash memory_bank_discovery/scripts/run_jarvis_web.sh
# (then chat via the ADK web UI as user_id=tony_stark)
```

---

*End of walk-through. If you're watching this on YouTube — hit subscribe. If you're reading it as a future-Tony reference: the answer you're looking for is probably in Section 12.*
