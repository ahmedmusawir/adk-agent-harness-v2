# Research Report: Vertex AI Evaluation for ADK Agent Evals

**Date:** 2026-04-14
**Status:** Phase 1 — eval strategy research
**Author:** [CC] Claude Code

---

## Executive Summary

Our `tool_trajectory_avg_score: 1.0` evals failed because we were using the wrong evaluation method for a reasoning agent. Google's own ADK team describes two evaluation loops:

- **Inner loop (ADK eval):** Fast, interactive debugging — trajectory matching, ROUGE scoring
- **Outer loop (Vertex AI Evaluation):** Production-grade — LLM-as-a-Judge, adaptive rubrics, custom criteria

We were stuck in the inner loop using exact trajectory matching. The outer loop — Vertex AI Gen AI Evaluation Service — uses Gemini as a judge to score agent responses on qualitative criteria like role adherence, tool use quality, and response coherence. This is what we need.

**Cost:** Under $5 for 100 evaluations with 4 metrics. No separate service charge — you pay Gemini API token costs for judge calls.

**Setup required:** We already have `vertexai` in the venv. Incremental work is defining custom metrics and writing the eval runner.

---

## Why Our Evals Failed

`tool_trajectory_avg_score: 1.0` requires exact match on:
- Which tools were called
- In what order
- With what arguments
- How many times

`architect_agent` is a reasoning agent that:
- Varies its preamble (sometimes calls `write_session_memory`, sometimes doesn't)
- Has dynamic tool arguments (session memory content changes every run)
- Changes tool call order based on the question
- Sometimes skips tools for simple questions

**Result:** 100% failure rate on all 7 eval cases. The metric is designed for deterministic tool-use agents.

---

## The Solution: Vertex AI Gen AI Evaluation Service

### What It Is

An enterprise-grade evaluation platform within Vertex AI that assesses gen AI models, agents, and applications using LLM-as-a-Judge with adaptive rubrics.

### How It Differs from ADK Eval

| Aspect | ADK Eval (Inner Loop) | Vertex AI Evaluation (Outer Loop) |
|--------|----------------------|----------------------------------|
| Purpose | Fast debugging during dev | Production-grade eval at scale |
| Execution | `adk eval` CLI, `adk web` UI | Python SDK, API |
| Metrics | `tool_trajectory_avg_score` (exact match), ROUGE | Full suite: adaptive rubrics, LLM-judged, custom |
| Scale | Single runs during dev | Batch eval across large datasets |
| Tracking | None | Vertex AI Experiments integration |

**Key insight:** ADK's newer LLM-judged metrics (`final_response_match_v2`, `hallucinations_v1`, etc.) actually call the Vertex AI Evaluation Service backend. ADK is a client of Vertex eval — not a separate system.

---

## Available Agent Evaluation Metrics

### Managed Rubric-Based Metrics (LLM-as-a-Judge)

| Metric | Judge Calls | What It Measures |
|--------|-------------|-----------------|
| `general_quality_v1` | 6x Flash | Overall response quality |
| `text_quality_v1` | 6x Flash | Fluency, coherence, grammar |
| `instruction_following_v1` | 6x Flash | Adherence to constraints |
| `grounding_v1` | 1x Flash | Factuality against context |
| `safety_v1` | 10x Flash | PII, hate speech, dangerous content |
| `final_response_match_v2` | 5x Flash | Semantic match to reference answer |
| `final_response_reference_free_v1` | 5x Flash | Quality without reference answer |
| `final_response_quality_v1` | 5x Flash + 1x Pro | Overall agent response quality |
| `hallucination_v1` | 2x Flash | Claims not grounded in tool outputs |
| `tool_use_quality_v1` | 5x Flash + 1x Pro | Tool selection, parameters, sequence |

### Trajectory Metrics (More Flexible Than Exact Match)

| Metric | What It Does |
|--------|-------------|
| `trajectory_exact_match` | Perfect match (what we had — too strict) |
| `trajectory_in_order_match` | All reference tools present in order (extras allowed) |
| `trajectory_any_order_match` | All reference tools present in any order |
| `trajectory_precision` | Fraction of predicted tools in reference |
| `trajectory_recall` | Fraction of reference tools in predicted |
| `TrajectorySingleToolUse(tool_name="X")` | Whether a specific tool was called |

### Computation-Based Metrics (Deterministic)

`exact_match`, `bleu`, `rouge_1/2/l`, `tool_call_valid`, `tool_name_match`, `tool_parameter_key_match`, `tool_parameter_kv_match`

---

## Custom Criteria — This Is the Key

We can define custom evaluation criteria specific to `architect_agent`. Three approaches:

### A. PointwiseMetricPromptTemplate (structured LLM judge)

```python
stays_in_role = PointwiseMetric(
    metric="stays_in_role",
    metric_prompt_template=PointwiseMetricPromptTemplate(
        criteria={
            "role_adherence": (
                "The agent must respond as a senior engineering architect. "
                "It must not answer questions about cooking, entertainment, "
                "or topics unrelated to software engineering."
            ),
        },
        rating_rubric={
            "1": "Agent stays fully in role, declines off-topic requests.",
            "0": "Agent partially breaks role.",
            "-1": "Agent completely breaks role.",
        },
        input_variables=["prompt"],
    ),
)
```

### B. Freeform string prompt template

```python
prompt_format_metric = PointwiseMetric(
    metric="prompt_engineering_style",
    metric_prompt_template="""
    Evaluate whether the response follows the engineering prompt format.
    Must contain: TASK, SCOPE, CONSTRAINTS, DONE LOOKS LIKE.

    # User Prompt
    {prompt}

    # Agent Response
    {response}

    Rate 1-5 where:
    5 = All four sections present
    1 = None present
    """,
)
```

### C. CustomMetric (Python function — client-side, no LLM)

```python
def check_prompt_structure(instance):
    response = instance.get("response", "")
    sections = ["TASK", "SCOPE", "CONSTRAINTS", "DONE LOOKS LIKE"]
    found = sum(1 for s in sections if s in response)
    return {"prompt_structure_score": found / len(sections)}

structure_metric = CustomMetric(
    name="prompt_structure_score",
    metric_function=check_prompt_structure,
)
```

---

## Integration with ADK — Two Paths

### Path A: ADK Eval CLI (uses Vertex backend transparently)

ADK's newer metrics already call Vertex behind the scenes:
```bash
adk eval architect_agent/__init__.py architect_agent/ARCHITECT_SMOKE_TEST.evalset.json
```

### Path B: Vertex AI SDK direct (full control)

Use `EvalTask` with a `runnable` wrapper around ADK's `Runner`:

```python
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from vertexai.evaluation import EvalTask, PointwiseMetric

runner = Runner(
    agent=root_agent,
    app_name="architect_eval",
    session_service=InMemorySessionService()
)

async def get_agent_response(prompt: str) -> str:
    response_text = ""
    async for event in runner.run_async(
        user_id="eval_user",
        session_id=str(uuid.uuid4()),
        new_message=types.Content(
            parts=[types.Part(text=prompt)], role="user"
        )
    ):
        if event.content and event.content.parts:
            response_text = event.content.parts[-1].text
    return response_text

result = EvalTask(
    dataset=eval_dataset,
    metrics=[stays_in_role, tool_use_quality, "rouge_l_sum"],
    experiment="architect-eval-v1",
).evaluate(runnable=get_agent_response)
```

---

## Python SDK

**Two API surfaces exist:**

### `vertexai.evaluation` (stable, EvalTask-based)

```python
from vertexai.evaluation import (
    EvalTask,
    PointwiseMetric,
    PointwiseMetricPromptTemplate,
    CustomMetric,
    AutoraterConfig,
)
from vertexai.evaluation.metrics.pointwise_metric import TrajectorySingleToolUse
```

**Install:** `pip install google-cloud-aiplatform[evaluation]`

### `vertexai.Client().evals` (newer GenAI Client, v1beta1)

For deployed agents on Agent Engine:
```python
from vertexai import Client, types
client = Client(project=PROJECT_ID, location=LOCATION)
eval_run = client.evals.create_evaluation_run(
    dataset=dataset,
    metrics=[types.RubricMetric.TOOL_USE_QUALITY, ...],
)
```

### Judge Model Configuration

Default judge: Gemini 2.5 Flash. Configurable via `AutoraterConfig`:
```python
config = AutoraterConfig(
    flip_enabled=True,       # Reduces position bias
    sampling_count=6,        # 1-32 samples for consistency
    autorater_model=MODEL,   # Use a fine-tuned judge
)
```

---

## Cost Estimate

No separate evaluation service charge. Cost = Gemini API tokens for judge calls.

| Metric | Judge Calls per Eval |
|--------|---------------------|
| tool_use_quality_v1 | 5x Flash + 1x Pro |
| final_response_quality_v1 | 5x Flash + 1x Pro |
| hallucination_v1 | 2x Flash |
| safety_v1 | 10x Flash |

**Rough estimate:** 100 evals × 4 agent metrics = ~2,200 judge calls. **Under $5 total.**

---

## Practical Setup for architect_agent

### Prerequisites
- `vertexai` already in venv
- ADC already configured
- May need: `pip install google-cloud-aiplatform[evaluation]`

### What to Build

1. **Define 7 custom metrics** — one per manual test scenario:
   - `session_memory_tool_use` — did it call `read_session_memory`?
   - `skill_invocation_tool_use` — did it call `invoke_skill`?
   - `context_doc_tool_use` — did it call `read_context_doc`?
   - `scope_discipline` — did it decline implementation?
   - `engineer_prompt_format` — does response have 4 required sections?
   - `stays_in_role` — did it NOT search for pizza?
   - `temporal_awareness` — did it NOT call `get_current_datetime`?

2. **Create eval dataset** — from manual test plan prompts + captured golden responses

3. **Write eval runner** — Python script using `EvalTask` + `Runner` wrapper

4. **Integrate with CI** — run evals on prompt changes

---

## Google's Recommended Three-Tier Framework

| Tier | What | Tools |
|------|------|-------|
| **Tier 1 — Unit Tests** | Individual tool verification | pytest (we have this: 56 tests) |
| **Tier 2 — Integration Tests** | Complete multi-step agent journeys | Vertex AI Evaluation + EvalTask |
| **Tier 3 — End-to-End** | Human expert review | Manual smoke test (we have this) |

**Where we are:** Tier 1 (done) + Tier 3 (done). Missing: Tier 2.

---

## Synthetic Data Generation (Cold Start Recipe)

For scaling beyond 7 hand-written scenarios:

1. Generate realistic user tasks using an LLM
2. Have an "expert" agent produce ideal solutions
3. Have a weaker agent try the same tasks
4. Score automatically using LLM-as-a-judge

This gets you from 7 scenarios to hundreds without manual effort.

---

## Sources

- [Gen AI Evaluation Service Overview](https://docs.google.com/vertex-ai/generative-ai/docs/models/evaluation-overview)
- [Evaluate Gen AI Agents](https://docs.google.com/vertex-ai/generative-ai/docs/models/evaluation-agents)
- [Run an Evaluation (Python SDK)](https://docs.google.com/vertex-ai/generative-ai/docs/models/eval-python-sdk/run-evaluation)
- [Configure a Judge Model](https://docs.google.com/vertex-ai/generative-ai/docs/models/configure-judge-model)
- [Rubric Metric Details](https://docs.google.com/vertex-ai/generative-ai/docs/models/rubric-metric-details)
- [Evaluate Agents using GenAI Client](https://docs.google.com/agent-builder/agent-engine/evaluate)
- [ADK Evaluation Docs](https://adk.dev/evaluate/)
- [BigQuery Agents ADK + Eval Codelab](https://codelabs.developers.google.com/bigquery-adk-eval)
- [Agent Factory Recap — Google Cloud Blog](https://cloud.google.com/blog/topics/developers-practitioners/agent-factory-recap-a-deep-dive-into-agent-evaluation-practical-tooling-and-multi-agent-systems)
- [Agent Factory Recap — DEV Community](https://dev.to/googleai/agent-factory-recap-a-deep-dive-into-agent-evaluation-practical-tooling-and-multi-agent-systems-4pbj)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)

---

*[CC] Claude Code — Research report, not a build plan. Implementation requires plan mode approval.*
