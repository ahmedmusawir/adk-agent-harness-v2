# MASTER_BRIEF.md — ADK Harness Modules Workshop v1
## The Big Picture: 4-Phase Plan

---

## Project Identity

- **Repo:** `adk-harness-starter-v1`
- **Owner:** Tony Stark — Cyberize Engineering
- **Engineering Agent:** Claude Code (with CLAUDE.md constitution)
- **Architect/Planner:** Gemini (JARVIS)
- **Runtime:** Google ADK (Agent Development Kit) on Python
- **Model (Phases 1-3):** Gemini only (Vertex AI) — no Anthropic models until Phase 4
- **Infrastructure:** GCP (Vertex AI, GCS, Cloud Run), DigitalOcean (staging)
- **UI:** `adk web` default interface (no custom frontend in Phase 1)

---

## Mission

Build a battle-tested, modular agent harness by learning each ADK capability in isolation, then combining them into production-grade agents.

**The principle:** Build small. Test each piece. Combine only what works. Never move forward with broken features.

---

## Model Strategy

**Phases 1-3: Gemini Only.**

All agents use `gemini-2.5-flash` (or `gemini-2.5-pro` where needed) via Vertex AI. This is intentional:

- One SDK. One auth system. One caching mechanism. Zero provider abstraction complexity.
- Google infrastructure benefits: managed RAG, GCS integration, context caching, Cloud Run deployment.
- Clean measurement: all token/cost/latency data is apples-to-apples.

**Phase 4: Multi-Provider Harness.**

Claude (Anthropic) integration happens here — after the harness is proven, the patterns are stable, and we have real production data to compare against. Phase 4 adds provider abstraction, Claude SDK integration, and cross-model benchmarking.

**Why not earlier?** Adding a second model provider while learning ADK fundamentals splits focus. We'd be debugging provider differences instead of learning agent patterns. Phase 4 is the controlled experiment — change ONE variable (the model), measure the delta.

---

## Phase 1 — POC Modules (Current Phase)

**Goal:** Build small, single-feature agents that each prove ONE ADK capability works.

**Duration:** 2-4 weeks

### Phase 1A — Core Engine Modules

These are the foundational pieces. Everything else depends on them.

| # | Agent Name | Capability Being Tested | Key Question Answered |
|---|-----------|------------------------|----------------------|
| 1A | Rico (Baseline) | GCS file reader + token calculator + run receipts | How many tokens does a cold read cost per turn? |
| 1B | Rico Cached | Vertex Context Caching + token calculator | How much does caching save vs cold reads? |
| 3 | Skills Agent | GCS-based skill files + session memory | Can an agent reliably trigger and execute skill instructions? |

**Why these first:** Token tracking gives us measurement. Caching gives us optimization. Skills + session memory give us behavioral control.

### Phase 1B — Integration Modules

These add external capabilities on top of the core engine.

| # | Agent Name | Capability Being Tested | Key Question Answered |
|---|-----------|------------------------|----------------------|
| 2 | Jarvis RAG | Google Managed RAG with playbook docs | Can RAG retrieve accurate answers from our documentation? |
| 4 | Live Context Agent | Gemini Files API for user uploads | Can the agent comprehend PDFs, images, and docs uploaded mid-conversation? |
| 5 | MCP Tools Agent | MCP servers + tool composition | Can we host tools as MCPs on Cloud Run and combine multiple MCPs? |

### Starter Kit Foundation (Built Before Any Agent)

Every agent inherits these from the starter kit:

| Utility | File | Purpose |
|---------|------|---------|
| Token Calculator | `utils/token_calculator.py` | Count tokens for any content against any Gemini model |
| Run Receipt | `utils/run_receipt.py` | Log every agent run: tokens, cost, latency, model, timestamp |
| Test Harness | `pytest.ini` + test fixtures | pytest config, regression rule, eval case structure |

**These are NOT optional.** They ship with the starter kit. Every cloned agent has them from birth.

---

## Phase 2 — Architect Agent (Full Composite Agent)

**Goal:** Combine all proven Phase 1 modules into the first production-grade agent.

**The Architect Agent will have:**
- GCS file reader (from Rico)
- Context caching (from Rico B)
- Managed RAG (from Jarvis)
- Skills + session memory (from Skills Agent)
- Live context via Files API (from Agent 4)
- Skill-gated Google Search (research mode)
- Token tracking + run receipts (from starter kit)

**This is where composition is tested.** Can all these modules work together without conflicts?

---

## Phase 3 — Advanced Harness (State Enforcement + Plan Mode)

**Goal:** Implement the Claude brain drain insights as mechanical enforcement.

**Key features:**
- `before_model_callback` / `after_model_callback` for state-based tool filtering
- Conditional tool availability based on `session.state["mode"]`
- Plan Mode protocol: research → plan → approve → execute
- Skill-gated behaviors with state machine enforcement

**This is where ADK's harness becomes more than a wrapper.** It becomes an enforcement layer.

---

## Phase 4 — Multi-Provider Harness (Claude Integration)

**Goal:** Add Anthropic Claude as a second model provider. Build provider abstraction.

**Key features:**
- Claude SDK integration alongside Vertex AI
- Provider-agnostic agent interface (same agent, swappable model)
- Cross-model benchmarking: Gemini vs Claude on identical tasks
- Claude-specific caching (breakpoint markers, 5-min TTL management)
- Cost comparison: Gemini context caching vs Claude prompt caching

**Why Phase 4:** By now we have stable patterns, real production data, and a proven harness. Adding Claude is a controlled variable — one change, measured delta. No contamination of Phases 1-3.

---

## Document Hierarchy

```
MASTER_BRIEF.md (this file — read first)
├── NAMING_CONVENTIONS.md                    ← Naming rules for everything
├── PHASE_1_OVERVIEW.md                      ← Shared patterns, starter kit, conventions
├── PHASE_1_TESTING_STRATEGY.md              ← pytest + adk eval framework
├── STARTER_KIT_SPEC.md                      ← How to prep the repo from the existing bundle
├── PHASE_1A_AGENT_SET_1_RICO_CACHING.md     ← Rico A + Rico B (first build)
├── PHASE_1A_AGENT_3_SKILLS.md               ← Skills + session memory
├── PHASE_1B_AGENT_2_JARVIS_RAG.md           ← Managed RAG with playbook docs
├── PHASE_1B_AGENT_4_LIVE_CONTEXT.md         ← Files API for uploads
└── PHASE_1B_AGENT_5_MCP_TOOLS.md            ← MCP servers + tool composition
```

**Workflow:** Claude reads MASTER_BRIEF first → NAMING_CONVENTIONS → PHASE_1_OVERVIEW → TESTING_STRATEGY → STARTER_KIT_SPEC → Phase 1A agent briefs → Phase 1B agent briefs. Build one agent, test it, move to next.

---

## Rules of Engagement

1. **ENTER PLAN MODE** before building any agent. Read the brief, research the codebase, present a plan, wait for approval.
2. **Never break working code.** If Agent 1 works and you're building Agent 2, Agent 1's tests must still pass.
3. **Token calculator is modular.** Built into the starter kit, reused everywhere.
4. **Run receipts are modular.** Built into the starter kit, reused everywhere.
5. **Session memory is modular.** Build it once with Agent 3, reuse everywhere.
6. **Every agent ships with tests.** No "I'll add tests later."
7. **One agent at a time.** Don't parallelize. Sequential builds, sequential testing.
8. **Ask when confused.** Surface assumptions. Push back on bad ideas. But never silently change working code.
9. **Phase 1A before Phase 1B.** Core engine modules must be stable before external integrations.
10. **Gemini only (Phases 1-3).** Do not introduce Anthropic SDK, Claude models, or any non-Google model provider. Phase 4 handles multi-provider.
11. **Follow NAMING_CONVENTIONS.md.** Every file, folder, class, variable, GCS path, and state key follows the naming doc. No exceptions.

---

*Generated by JARVIS — Cyberize Engineering AI Factory*
*Version: 1.2 | Date: March 3, 2026*
*Changes from v1.1: Added Phase 4 (Claude/Multi-Provider). Gemini-only mandate for Phases 1-3. Added starter kit foundation table. Added NAMING_CONVENTIONS.md to doc hierarchy. Updated Rules of Engagement.*
