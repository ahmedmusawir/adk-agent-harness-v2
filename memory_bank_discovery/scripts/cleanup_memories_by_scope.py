"""Safe scope-targeted cleanup utility for Vertex AI Memory Bank.

Deletes every memory on the engine whose scope EXACTLY matches TARGET_SCOPE.
Useful when a user_id has accumulated test-junk data and you want a fresh start.

Two-stage safety:
  - DRY_RUN = True (default): lists matching memories, prints what would be
    deleted, DOES NOTHING. Run first to verify your TARGET_SCOPE is correct.
  - DRY_RUN = False: actually deletes. Edit this constant in the file before
    the destructive run - a deliberate code change, not a runtime prompt.

Match semantics:
  - Exact dict equality on the scope field. A memory with
    scope={"app_name": "jarvis_agent", "user_id": "user"} is NOT matched by
    TARGET_SCOPE={"user_id": "user"} (different shape). Prevents accidentally
    deleting memories from apps that share a user_id.

CAUTION: deletes are irreversible. Dry-run first. Read the printed fact list
before flipping DRY_RUN to False.
"""

import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"

# --- EDIT THESE BEFORE RUNNING ---------------------------------------------
# The exact scope dict to delete. Must match byte-for-byte (key order doesn't
# matter for dict equality, but spelling and values do).
TARGET_SCOPE = {"app_name": "jarvis_agent", "user_id": "user"}

# Keep True for a safe list-only run. Flip to False when you've verified the
# output and actually want to delete.
DRY_RUN = True
# ---------------------------------------------------------------------------


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
    print("Scope-targeted memory cleanup")
    print("=" * 70)
    print(f"Project:      {PROJECT_ID}")
    print(f"Location:     {LOCATION}")
    print(f"Engine:       {agent_engine_id}")
    print(f"TARGET_SCOPE: {TARGET_SCOPE}")
    print(f"DRY_RUN:      {DRY_RUN}  ({'no deletions will happen' if DRY_RUN else 'WILL DELETE matched memories'})")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    # Enumerate all memories on the engine, filter by exact scope match.
    all_memories = list(client.agent_engines.memories.list(name=agent_engine_id))
    print(f"Engine holds {len(all_memories)} total memory(ies).")

    matches = [m for m in all_memories if m.scope == TARGET_SCOPE]
    print(f"Matching TARGET_SCOPE: {len(matches)} memory(ies).")

    if not matches:
        print("Nothing to delete. Exiting.")
        return

    print("-" * 70)
    print("Matched memories:")
    for i, mem in enumerate(matches, start=1):
        short = mem.name.split("/memories/")[-1]
        print(f"  [{i}] [{short}] {mem.fact!r}")

    print("-" * 70)

    if DRY_RUN:
        print(f"DRY_RUN is True - NO deletions performed.")
        print(f"If the list above is correct, edit DRY_RUN = False in this file and re-run.")
        return

    # Actual delete pass.
    print(f"Deleting {len(matches)} memory(ies)...")
    deleted = 0
    errors: list[tuple[str, str]] = []
    for i, mem in enumerate(matches, start=1):
        short = mem.name.split("/memories/")[-1]
        print(f"  [{i}/{len(matches)}] deleting [{short}] ...", end=" ", flush=True)
        try:
            client.agent_engines.memories.delete(name=mem.name)
            print("OK")
            deleted += 1
        except Exception as e:
            print(f"FAILED ({type(e).__name__}: {e})")
            errors.append((mem.name, f"{type(e).__name__}: {e}"))
            # Don't raise mid-loop - try the rest, report at the end.

    print("-" * 70)
    print(f"Summary: deleted {deleted}/{len(matches)}, errors: {len(errors)}.")
    if errors:
        print("Errors:")
        for name, err in errors:
            print(f"  {name.split('/memories/')[-1]}: {err}")
        raise RuntimeError("One or more deletes failed. See above.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
        raise
