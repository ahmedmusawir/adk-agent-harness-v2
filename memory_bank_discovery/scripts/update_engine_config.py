"""Updates the live Agent Engine's context_spec with tuned Memory Bank config.

What this sets:
  - Generation model: gemini-2.5-pro (full publisher path per SDK docstring)
  - 4 managed memory topics + 4 custom memory topics
  - 3 few-shot extraction examples
  - TTL policy (90d default, 30d for auto-generated, 1y for manual writes)
  - Engine display_name + description

Does NOT:
  - Delete existing memories (they stay under old defaults)
  - Affect past extractions — only new generate() calls see the new config

Requires confirmation at the CLI before the API call fires.
"""

import json
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"

# --- Engine metadata ---------------------------------------------------------
DISPLAY_NAME = "Stark Industries Memory Engine"
DESCRIPTION = "Memory Bank engine for ADK agent harness v2"

# --- Generation model --------------------------------------------------------
# Full publisher path per SDK docstring at vertexai/_genai/types.py:3520.
# NO client-side validation exists — only server-side. If gemini-2.5-pro is
# rejected, fall back to gemini-2.5-flash (short name is also known to work
# per Google's Sep 3 2025 customization announcement example).
GENERATION_MODEL = (
    f"projects/{PROJECT_ID}/locations/{LOCATION}"
    f"/publishers/google/models/gemini-2.5-pro"
)

# --- Managed topics (all 4 built-ins) ----------------------------------------
MANAGED_TOPICS = [
    "USER_PERSONAL_INFO",
    "USER_PREFERENCES",
    "KEY_CONVERSATION_DETAILS",
    "EXPLICIT_INSTRUCTIONS",
]

# --- Custom topics (domain-specific extraction hints) ------------------------
CUSTOM_TOPICS = [
    {
        "label": "architectural_decisions",
        "description": (
            "Technical architecture decisions including technology choices, "
            "framework selections, infrastructure design, hosting decisions, "
            "database choices, and the reasoning behind each decision."
        ),
    },
    {
        "label": "project_constraints",
        "description": (
            "Hard constraints on projects including compliance requirements, "
            "budget limits, deadline commitments, client expectations, and "
            "non-negotiable technical requirements."
        ),
    },
    {
        "label": "lessons_learned",
        "description": (
            "Lessons learned from building, testing, debugging, and deploying. "
            "Includes what worked, what failed, what was harder than expected, "
            "and what should be done differently next time."
        ),
    },
    {
        "label": "technology_stack",
        "description": (
            "Current technology choices and tool preferences including "
            "programming languages, frameworks, cloud services, AI models, "
            "development tools, and why they were chosen over alternatives."
        ),
    },
]


# --- Few-shot examples (guide the extraction model) --------------------------
def _user_event(text: str) -> dict:
    """Build a single user-turn event in the shape the API expects."""
    return {"content": {"role": "user", "parts": [{"text": text}]}}


FEW_SHOT_EXAMPLES = [
    # Example 1: architecture decision
    {
        "conversation_source": {
            "events": [
                _user_event(
                    "We decided to go with Vercel Pro with the HIPAA add-on "
                    "for Project Mothership hosting instead of GCP Cloud Run. "
                    "The main reason was Coach's credibility with Frank — he "
                    "needs to show a polished deployment, not a raw cloud "
                    "setup. We can still use GCP for our own skill-building "
                    "projects separately."
                ),
            ],
        },
        "generated_memories": [
            {"fact": (
                "Project Mothership hosting decision: Vercel Pro with HIPAA "
                "add-on, chosen over GCP Cloud Run to prioritize Coach's "
                "credibility with the client Frank."
            )},
            {"fact": (
                "GCP Cloud Run reserved for internal skill-building projects, "
                "not client-facing deployments."
            )},
            {"fact": (
                "Project Mothership requires full HIPAA compliance including "
                "the HIPAA add-on for hosting."
            )},
        ],
    },
    # Example 2: technical finding / eval system
    {
        "conversation_source": {
            "events": [
                _user_event(
                    "We tested the ADK eval system and found that "
                    "tool_trajectory_avg_score with exact matching is "
                    "fundamentally broken for stateful reasoning agents. Any "
                    "discretionary tool call causes automatic failure. The "
                    "Vertex AI Evaluation Service with TrajectorySingleToolUse "
                    "and custom PointwiseMetric is the right approach instead."
                ),
            ],
        },
        "generated_memories": [
            {"fact": (
                "ADK eval finding: tool_trajectory_avg_score with exact "
                "matching is incompatible with stateful reasoning agents — "
                "discretionary tool calls cause automatic failure."
            )},
            {"fact": (
                "Correct eval approach for ADK agents: Vertex AI Evaluation "
                "Service using TrajectorySingleToolUse and custom "
                "PointwiseMetric."
            )},
        ],
    },
    # Example 3: code conventions / preferences
    {
        "conversation_source": {
            "events": [
                _user_event(
                    "I want the agent to use the /types folder for all "
                    "interfaces, never /models. And always use Zustand for "
                    "state management. Also, never use dangerouslySetInnerHTML "
                    "— use html-react-parser instead."
                ),
            ],
        },
        "generated_memories": [
            {"fact": (
                "Code convention: TypeScript interfaces go in /types folder, "
                "never /models."
            )},
            {"fact": "State management preference: always use Zustand."},
            {"fact": (
                "HTML rendering rule: never use dangerouslySetInnerHTML, use "
                "html-react-parser instead."
            )},
        ],
    },
]

# --- TTL policy --------------------------------------------------------------
# Protobuf Duration strings (seconds + "s" suffix).
# ttl_config is a protobuf `oneof`: set EITHER default_ttl OR
# granular_ttl_config, never both. Granular covers every write path so we use
# it alone.
TTL_CONFIG = {
    "granular_ttl_config": {
        "create_ttl":            "31536000s",  # 1 year — manual writes
        "generate_created_ttl":   "2592000s",  # 30 days — auto-extracted
        "generate_updated_ttl":   "7776000s",  # 90 days — consolidation updates
    },
}


def build_context_spec() -> dict:
    """Assemble the full context_spec payload as a nested dict."""
    memory_topics = [
        {"managed_memory_topic": {"managed_topic_enum": t}} for t in MANAGED_TOPICS
    ] + [
        {"custom_memory_topic": ct} for ct in CUSTOM_TOPICS
    ]

    return {
        "memory_bank_config": {
            "generation_config": {"model": GENERATION_MODEL},
            "customization_configs": [
                {
                    # Empty scope_keys = default config for every scope.
                    "scope_keys": [],
                    "memory_topics": memory_topics,
                    "generate_memories_examples": FEW_SHOT_EXAMPLES,
                }
            ],
            "ttl_config": TTL_CONFIG,
        },
    }


def main() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    agent_engine_id = os.getenv("AGENT_ENGINE_ID")
    if not agent_engine_id:
        raise RuntimeError(
            f"AGENT_ENGINE_ID not found in {env_path}. "
            "Run setup_agent_engine.py or list_agent_engines.py first."
        )

    config_payload = {
        "display_name": DISPLAY_NAME,
        "description":  DESCRIPTION,
        "context_spec": build_context_spec(),
    }

    print("=" * 70)
    print("ENGINE UPDATE — PREVIEW (nothing sent yet)")
    print("=" * 70)
    print(f"Project:  {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"Engine:   {agent_engine_id}")
    print("-" * 70)
    print(f"display_name:        {DISPLAY_NAME}")
    print(f"description:         {DESCRIPTION}")
    print(f"generation model:    {GENERATION_MODEL}")
    print(f"managed topics:      {len(MANAGED_TOPICS)}  ({', '.join(MANAGED_TOPICS)})")
    print(f"custom topics:       {len(CUSTOM_TOPICS)}  "
          f"({', '.join(t['label'] for t in CUSTOM_TOPICS)})")
    print(f"few-shot examples:   {len(FEW_SHOT_EXAMPLES)}")
    print(f"granular TTLs:       create={TTL_CONFIG['granular_ttl_config']['create_ttl']}, "
          f"generate_created={TTL_CONFIG['granular_ttl_config']['generate_created_ttl']}, "
          f"generate_updated={TTL_CONFIG['granular_ttl_config']['generate_updated_ttl']}")
    print("-" * 70)
    print("Full AgentEngineConfig payload (JSON):")
    print(json.dumps(config_payload, indent=2))
    print("-" * 70)

    try:
        input("About to update engine. Press Enter to continue or Ctrl-C to abort.")
    except KeyboardInterrupt:
        print("\nAborted by user — nothing sent.")
        return

    print("\nSending update ...")
    try:
        client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
        client.agent_engines.update(
            name=agent_engine_id,
            config=config_payload,
        )
        print("Update call completed.")
    except Exception as e:
        print(f"\nUPDATE FAILED: {type(e).__name__}: {e}")
        print("-" * 70)
        print("Full traceback:")
        print(traceback.format_exc())
        raise

    print("\n" + "=" * 70)
    print("VERIFY — reading back current engine state")
    print("=" * 70)
    try:
        verified = client.agent_engines.get(name=agent_engine_id).api_resource
        print(json.dumps(
            verified.model_dump(exclude_none=False),
            indent=2,
            default=str,
        ))
    except Exception as e:
        print(f"Verification read failed (update may still have succeeded): "
              f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
