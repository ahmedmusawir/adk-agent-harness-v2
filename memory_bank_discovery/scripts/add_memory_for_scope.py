"""Adds a single fact to Memory Bank under TARGET_SCOPE.

Uses memories.create() - direct write, no extraction, no consolidation on the
input side (but consolidation may apply later if someone runs generate() over
a transcript that touches the same topic).

--- ABOUT "CREATING USERS" ------------------------------------------------
Memory Bank has NO first-class user resource and NO "create user" API. Users
are implicit: they exist as soon as you write a memory under a new scope.
So this script doubles as a user-creation tool:
  - First time you run it with a never-before-seen TARGET_SCOPE -> that user
    effectively "exists" now (will show up in list_scopes.py afterward).
  - Subsequent runs with the same TARGET_SCOPE just add more memories to
    that user.
---------------------------------------------------------------------------

Edit TARGET_SCOPE and FACT below before running.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"

# --- EDIT THESE BEFORE RUNNING ---------------------------------------------
# The scope this memory belongs to. For ADK-agent-facing memories, use both
# app_name and user_id (ADK writes with both). For direct-SDK use, user_id
# alone is fine.
TARGET_SCOPE = {"app_name": "jarvis_agent", "user_id": "pepper_bibo"}

# The fact to store. Write it in whatever voice you want - create() stores
# it verbatim. (Compare with generate() which normalizes to first-person.)
FACT = "Tony's favorite test codename is 'Project Odyssey'."
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
    print("Adding memory to Memory Bank")
    print("=" * 70)
    print(f"Project:      {PROJECT_ID}")
    print(f"Location:     {LOCATION}")
    print(f"Engine:       {agent_engine_id}")
    print(f"TARGET_SCOPE: {TARGET_SCOPE}")
    print(f"FACT:         {FACT}")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    operation = client.agent_engines.memories.create(
        name=agent_engine_id,
        fact=FACT,
        scope=TARGET_SCOPE,
    )

    mem = operation.response
    print("Added.")
    print(f"  memory.name:        {mem.name}")
    print(f"  memory.fact:        {mem.fact}")
    print(f"  memory.scope:       {mem.scope}")
    print(f"  memory.create_time: {mem.create_time}")
    print(f"  memory.update_time: {mem.update_time}")


if __name__ == "__main__":
    main()
