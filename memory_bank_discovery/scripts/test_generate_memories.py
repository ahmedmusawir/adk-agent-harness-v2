"""Test 4 - Session-based memory generation via direct_contents_source.

Hands a small synthetic transcript to the Memory Bank service and asks it to
extract memories. This is the headline Memory Bank feature - not a plain write,
but a generation step that runs server-side extraction over chat content.

Source type chosen: direct_contents_source.
    - vertex_session_source needs a real Session resource (not yet provisioned).
    - direct_memories_source is basically bulk-create; doesn't exercise extraction.
    - direct_contents_source = hand over a transcript, watch what comes back.

Consolidation is left ENABLED (SDK default) so we see how the service treats
these new facts alongside the existing "Tony prefers Python..." memory. Facts
chosen are deliberately unrelated to Python so the consolidation/contradiction
signal stays out of Test 4 and is saved for Test 6.

If the call hangs, Ctrl-C it - wait_for_completion=True polls inside the SDK
and has no outer timeout.
"""

import os
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

from google.genai import types as genai_types

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"
USER_ID = "tony_stark"

# Three-turn synthetic transcript. Two user facts to extract, one model ack.
TRANSCRIPT = [
    ("user",  "My favorite coffee shop is Stark Brewery on 5th avenue."),
    ("model", "Noted."),
    ("user",  "I usually order a flat white with oat milk."),
]


def _build_events() -> list[dict]:
    """Convert (role, text) tuples into the dict shape the SDK accepts.

    Shape: [{"content": Content(role=..., parts=[Part(text=...)])}, ...]
    Passing wrappers as dicts where convenient; genai_types.Content/Part
    are used for the bits that benefit from explicit typing.
    """
    events = []
    for role, text in TRANSCRIPT:
        content = genai_types.Content(
            role=role,
            parts=[genai_types.Part(text=text)],
        )
        events.append({"content": content})
    return events


def main() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    agent_engine_id = os.getenv("AGENT_ENGINE_ID")
    if not agent_engine_id:
        raise RuntimeError(
            f"AGENT_ENGINE_ID not found in {env_path}. "
            "Run setup_agent_engine.py (or list_agent_engines.py) first."
        )

    print("=" * 70)
    print("TEST 4 - Session-Based Memory Generation")
    print("=" * 70)
    print(f"Project:    {PROJECT_ID}")
    print(f"Location:   {LOCATION}")
    print(f"Engine:     {agent_engine_id}")
    print(f"Scope:      {{'user_id': '{USER_ID}'}}")
    print(f"Transcript turns: {len(TRANSCRIPT)}")
    for i, (role, text) in enumerate(TRANSCRIPT, start=1):
        print(f"  [{i}] {role}: {text}")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    events = _build_events()
    direct_contents_source = {"events": events}

    print("Calling client.agent_engines.memories.generate() ...")
    t_start = time.monotonic()
    try:
        operation = client.agent_engines.memories.generate(
            name=agent_engine_id,
            direct_contents_source=direct_contents_source,
            scope={"user_id": USER_ID},
            # config defaults: wait_for_completion=True, disable_consolidation=None (ON).
        )
    except Exception as e:
        print("-" * 70)
        print(f"FAILURE: {type(e).__name__}: {e}")
        print("-" * 70)
        print("Full traceback:")
        print(traceback.format_exc())
        raise
    elapsed = time.monotonic() - t_start

    print("-" * 70)
    print(f"SUCCESS - generate() returned in {elapsed:.2f}s.")
    print("-" * 70)

    print(f"operation.name:     {getattr(operation, 'name', '<no attr>')}")
    print(f"operation.done:     {getattr(operation, 'done', '<no attr>')}")
    print(f"operation.error:    {getattr(operation, 'error', '<no attr>')}")

    response = getattr(operation, "response", None)
    print(f"operation.response: {response!r}")
    print("-" * 70)

    generated = getattr(response, "generated_memories", None) if response else None
    if generated is None:
        print("No generated_memories field on response.")
    else:
        print(f"generated_memories: {len(generated)} item(s)")
        for i, item in enumerate(generated, start=1):
            action = getattr(item, "action", "<no attr>")
            mem = getattr(item, "memory", None)
            print(f"\n--- Generated [{i}/{len(generated)}] ---")
            print(f"  action:       {action}")
            if mem is None:
                print("  memory:       <None>")
                continue
            print(f"  memory.name:        {getattr(mem, 'name', '<no attr>')}")
            print(f"  memory.fact:        {getattr(mem, 'fact', '<no attr>')}")
            print(f"  memory.scope:       {getattr(mem, 'scope', '<no attr>')}")
            print(f"  memory.create_time: {getattr(mem, 'create_time', '<no attr>')}")
            print(f"  memory.update_time: {getattr(mem, 'update_time', '<no attr>')}")

    print("-" * 70)
    print("Raw repr(operation):")
    print(repr(operation))
    print("=" * 70)


if __name__ == "__main__":
    main()
