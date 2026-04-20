"""Test 3 - Memory retrieval from Vertex AI Memory Bank.

Exercises all three read paths in a single run so we learn the full read surface:

    1. memories.list(name=ENGINE)                    - enumerate every memory on the engine
    2. memories.get(name=MEMORY_RESOURCE_NAME)       - direct fetch by memory resource name
    3. memories.retrieve(name=ENGINE, scope={...})   - scope-based lookup (agent-runtime pattern)

Each section is independent: a failure in one prints the full traceback and moves on
to the next, because discovery > short-circuiting. The final exit code is non-zero
if ANY section failed.
"""

import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"
TARGET_SCOPE = {"user_id": "tony_stark"}


def _section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _exercise(label: str, fn) -> bool:
    """Run a single read-path test. Return True on success, False on failure."""
    print(f"Calling {label} ...")
    try:
        fn()
    except Exception as e:
        print("-" * 70)
        print(f"FAILURE in {label}: {type(e).__name__}: {e}")
        print("-" * 70)
        print("Full traceback:")
        print(traceback.format_exc())
        return False
    return True


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
    print("TEST 3 - Memory Retrieval (list / get / retrieve)")
    print("=" * 70)
    print(f"Project:    {PROJECT_ID}")
    print(f"Location:   {LOCATION}")
    print(f"Engine:     {agent_engine_id}")
    print(f"Scope:      {TARGET_SCOPE}")

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    # We need at least one memory name for section 2 (get). The cleanest way to
    # get one without hardcoding the Test 2 memory ID is to grab the first item
    # from section 1's list.
    first_memory_name: str | None = None
    results: dict[str, bool] = {}

    # -----------------------------------------------------------------
    # Section 1: LIST - enumerate every memory on the engine
    # -----------------------------------------------------------------
    _section("[1/3] memories.list(name=ENGINE)")

    def run_list() -> None:
        nonlocal first_memory_name
        iterator = client.agent_engines.memories.list(name=agent_engine_id)
        # Pager is lazy; force materialization so we learn the shape and count.
        memories = list(iterator)
        print(f"Returned {len(memories)} memory record(s).")
        for i, mem in enumerate(memories, start=1):
            print(f"\n--- Memory [{i}/{len(memories)}] ---")
            print(f"  name:        {getattr(mem, 'name', '<no attr>')}")
            print(f"  fact:        {getattr(mem, 'fact', '<no attr>')}")
            print(f"  scope:       {getattr(mem, 'scope', '<no attr>')}")
            print(f"  create_time: {getattr(mem, 'create_time', '<no attr>')}")
            print(f"  update_time: {getattr(mem, 'update_time', '<no attr>')}")
        if memories:
            first_memory_name = memories[0].name
        else:
            print("No memories on engine - sections [2/3] will be skipped.")

    results["list"] = _exercise("memories.list", run_list)

    # -----------------------------------------------------------------
    # Section 2: GET - direct fetch by memory resource name
    # -----------------------------------------------------------------
    _section("[2/3] memories.get(name=MEMORY_RESOURCE_NAME)")

    if first_memory_name is None:
        print("Skipped: no memory name available from section 1.")
        results["get"] = True  # nothing to fail
    else:

        def run_get() -> None:
            print(f"Fetching: {first_memory_name}")
            mem = client.agent_engines.memories.get(name=first_memory_name)
            print("-" * 70)
            print("Returned Memory:")
            print(f"  name:        {getattr(mem, 'name', '<no attr>')}")
            print(f"  fact:        {getattr(mem, 'fact', '<no attr>')}")
            print(f"  scope:       {getattr(mem, 'scope', '<no attr>')}")
            print(f"  create_time: {getattr(mem, 'create_time', '<no attr>')}")
            print(f"  update_time: {getattr(mem, 'update_time', '<no attr>')}")
            print("-" * 70)
            print("Raw repr(memory):")
            print(repr(mem))

        results["get"] = _exercise("memories.get", run_get)

    # -----------------------------------------------------------------
    # Section 3: RETRIEVE - scope-based lookup (how agents query at runtime)
    # -----------------------------------------------------------------
    _section("[3/3] memories.retrieve(name=ENGINE, scope=...)")

    def run_retrieve() -> None:
        # No similarity_search_params or simple_retrieval_params passed.
        # Both are Optional per the SDK signature; we want to learn the default behavior.
        iterator = client.agent_engines.memories.retrieve(
            name=agent_engine_id,
            scope=TARGET_SCOPE,
        )
        retrieved = list(iterator)
        print(f"Returned {len(retrieved)} retrieved-memory record(s).")
        for i, item in enumerate(retrieved, start=1):
            print(f"\n--- Retrieved [{i}/{len(retrieved)}] ---")
            print(f"  raw repr: {item!r}")
            # The item is a RetrieveMemoriesResponseRetrievedMemory wrapper -
            # print its attributes defensively so we learn the shape.
            for attr in ("memory", "distance", "score", "similarity"):
                if hasattr(item, attr):
                    print(f"  {attr}: {getattr(item, attr)!r}")

    results["retrieve"] = _exercise("memories.retrieve", run_retrieve)

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    _section("SUMMARY")
    for label, ok in results.items():
        print(f"  {label:<10} {'PASS' if ok else 'FAIL'}")

    if not all(results.values()):
        raise RuntimeError("One or more read paths failed - see tracebacks above.")


if __name__ == "__main__":
    main()
