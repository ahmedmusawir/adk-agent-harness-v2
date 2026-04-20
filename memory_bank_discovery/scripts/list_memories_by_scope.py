"""Lists every memory matching TARGET_SCOPE.

Answers "what does this user know?". Uses memories.retrieve(scope=...) which
is exact-match strict (Test 5 finding) - a memory scoped to
{"app_name": "jarvis_agent", "user_id": "user"} will NOT match a TARGET_SCOPE
of {"user_id": "user"}. If you want admin-level enumeration across all
scopes, use list_scopes.py instead.

Read-only. No dry-run gate. Safe to run anytime.

Edit TARGET_SCOPE below before running.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"

# --- EDIT THIS BEFORE RUNNING ----------------------------------------------
# The exact scope dict whose memories you want to see. Must match byte-for-byte.
TARGET_SCOPE = {"app_name": "jarvis_agent", "user_id": "user"}
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
    print("Memories matching TARGET_SCOPE")
    print("=" * 70)
    print(f"Project:      {PROJECT_ID}")
    print(f"Location:     {LOCATION}")
    print(f"Engine:       {agent_engine_id}")
    print(f"TARGET_SCOPE: {TARGET_SCOPE}")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    iterator = client.agent_engines.memories.retrieve(
        name=agent_engine_id,
        scope=TARGET_SCOPE,
    )
    retrieved = list(iterator)

    if not retrieved:
        print("No memories match TARGET_SCOPE.")
        print("Tip: run list_scopes.py to see what scopes actually exist in the bank.")
        return

    print(f"Found {len(retrieved)} memory(ies).")
    print("-" * 70)
    for i, item in enumerate(retrieved, start=1):
        mem = item.memory
        short = mem.name.split("/memories/")[-1]
        print(f"\n--- Memory [{i}/{len(retrieved)}] ---")
        print(f"  id:          {short}")
        print(f"  fact:        {mem.fact!r}")
        print(f"  scope:       {mem.scope}")
        print(f"  create_time: {mem.create_time}")
        print(f"  update_time: {mem.update_time}")


if __name__ == "__main__":
    main()
