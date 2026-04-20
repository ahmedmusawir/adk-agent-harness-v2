"""Test 2 — Direct memory write to Vertex AI Memory Bank.

Writes a single fact scoped to a user_id via client.agent_engines.memories.create(...).
Prints the raw operation/response so we can learn the API shape. On failure, prints
the full traceback and re-raises so the exit code reflects the error.

If the call hangs, Ctrl-C it — wait_for_completion=True polls inside the SDK and
has no outer timeout in this script.
"""

import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"
USER_ID = "tony_stark"
FACT = "Tony prefers Python for backend development"


def main() -> None:
    # .env lives one level up from scripts/
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    agent_engine_id = os.getenv("AGENT_ENGINE_ID")
    if not agent_engine_id:
        raise RuntimeError(
            f"AGENT_ENGINE_ID not found in {env_path}. "
            "Run setup_agent_engine.py (or list_agent_engines.py) first."
        )

    print("=" * 70)
    print("TEST 2 - Direct Memory Write")
    print("=" * 70)
    print(f"Project:    {PROJECT_ID}")
    print(f"Location:   {LOCATION}")
    print(f"Engine:     {agent_engine_id}")
    print(f"Scope:      {{'user_id': '{USER_ID}'}}")
    print(f"Fact:       {FACT}")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    print("Calling client.agent_engines.memories.create() ...")
    try:
        operation = client.agent_engines.memories.create(
            name=agent_engine_id,
            fact=FACT,
            scope={"user_id": USER_ID},
        )
    except Exception as e:
        print("-" * 70)
        print(f"FAILURE: {type(e).__name__}: {e}")
        print("-" * 70)
        print("Full traceback:")
        print(traceback.format_exc())
        raise

    print("-" * 70)
    print("SUCCESS - memories.create() returned without raising.")
    print("-" * 70)

    # Structured field access - individual fields, so None values are obvious.
    print(f"operation.name:     {getattr(operation, 'name', '<no attr>')}")
    print(f"operation.done:     {getattr(operation, 'done', '<no attr>')}")
    print(f"operation.error:    {getattr(operation, 'error', '<no attr>')}")

    response = getattr(operation, "response", None)
    print(f"operation.response: {response!r}")
    if response is not None:
        print(f"  response.name:   {getattr(response, 'name', '<no attr>')}")
        print(f"  response.fact:   {getattr(response, 'fact', '<no attr>')}")
        print(f"  response.scope:  {getattr(response, 'scope', '<no attr>')}")

    # Raw repr - belt-and-suspenders so we learn the full shape even if fields above missed something.
    print("-" * 70)
    print("Raw repr(operation):")
    print(repr(operation))
    print("=" * 70)


if __name__ == "__main__":
    main()
