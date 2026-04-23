"""Inspects the current Vertex AI Agent Engine config — READ-ONLY.

Prints the full config tree (context_spec, memory_bank_config, TTL,
generation model, topics, etc.) so we can see what's set vs. defaults.
Any None/missing field is explicitly annotated 'NOT SET' for clarity.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"


def _dump(obj):
    """Best-effort pretty JSON dump. Falls back gracefully on non-serializable."""
    try:
        return json.dumps(obj.model_dump(exclude_none=False), indent=2, default=str)
    except Exception as e:
        return f"<failed to JSON-dump: {type(e).__name__}: {e}>\nrepr:\n{obj!r}"


def _note_unset(label, value):
    if value is None:
        print(f"  {label}: NOT SET")
    else:
        print(f"  {label}: SET")


def main() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    agent_engine_id = os.getenv("AGENT_ENGINE_ID")
    if not agent_engine_id:
        raise RuntimeError(
            f"AGENT_ENGINE_ID not found in {env_path}. "
            "Run list_agent_engines.py first."
        )

    print("=" * 70)
    print("Engine config inspection")
    print("=" * 70)
    print(f"Project:  {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"Engine:   {agent_engine_id}")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
    ae = client.agent_engines.get(name=agent_engine_id)

    resource = ae.api_resource
    print("\n[Section 1] Top-level ReasoningEngine fields (what's SET vs NOT SET)")
    print("-" * 70)
    for field in (
        "name",
        "display_name",
        "description",
        "create_time",
        "update_time",
        "etag",
        "spec",
        "context_spec",
    ):
        _note_unset(field, getattr(resource, field, None))

    print("\n[Section 2] context_spec contents")
    print("-" * 70)
    ctx_spec = getattr(resource, "context_spec", None)
    if ctx_spec is None:
        print("  context_spec is NOT SET on this engine.")
        print("  → Engine is using SERVER-SIDE DEFAULTS for everything.")
    else:
        mb = getattr(ctx_spec, "memory_bank_config", None)
        _note_unset("memory_bank_config", mb)
        if mb is not None:
            _note_unset("  generation_config", getattr(mb, "generation_config", None))
            _note_unset("  similarity_search_config", getattr(mb, "similarity_search_config", None))
            _note_unset("  customization_configs", getattr(mb, "customization_configs", None))
            _note_unset("  ttl_config", getattr(mb, "ttl_config", None))

    print("\n[Section 3] Full ReasoningEngine object (JSON dump, None preserved)")
    print("-" * 70)
    print(_dump(resource))

    print("\n[Section 4] Raw repr (fallback fidelity)")
    print("-" * 70)
    print(repr(resource))


if __name__ == "__main__":
    main()
