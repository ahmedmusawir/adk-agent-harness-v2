"""Lists all unique scopes present in the Memory Bank, with memory counts.

Closest equivalent to "list all users" - but remember: Memory Bank has no
first-class user resource. Users are just values inside the scope dict.
This script derives the list of scopes by enumerating every memory and
aggregating unique scope dicts.

No constants to edit. Safe to run anytime - read-only.

Output is sorted by memory count descending (most populated scope first),
which is usually what you want when debugging "where did all my junk data go".
"""

import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"


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
    print("Unique scopes in Memory Bank")
    print("=" * 70)
    print(f"Project:  {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"Engine:   {agent_engine_id}")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    all_memories = list(client.agent_engines.memories.list(name=agent_engine_id))
    total = len(all_memories)
    print(f"Total memories on engine: {total}")

    if total == 0:
        print("No memories in bank. Exiting.")
        return

    # Counter needs a hashable key - serialize the scope dict to a
    # sorted-tuple-of-items representation. Preserves content, makes it hashable.
    scope_counter: Counter[tuple] = Counter()
    scope_display: dict[tuple, dict[str, str]] = {}
    for mem in all_memories:
        key = tuple(sorted((mem.scope or {}).items()))
        scope_counter[key] += 1
        scope_display[key] = mem.scope or {}

    print(f"Unique scopes: {len(scope_counter)}")
    print("-" * 70)

    # Sort by count desc, then by scope-repr for stable ordering.
    ranked = sorted(
        scope_counter.items(),
        key=lambda kv: (-kv[1], str(scope_display[kv[0]])),
    )
    for i, (key, count) in enumerate(ranked, start=1):
        print(f"  [{i}] {count:>4} memory(ies) under {scope_display[key]}")


if __name__ == "__main__":
    main()
