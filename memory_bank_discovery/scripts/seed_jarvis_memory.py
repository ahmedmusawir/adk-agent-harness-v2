"""One-off pre-seed: writes a Jarvis-scoped memory for Test 7a verification.

Our prior discovery memories (Tests 2-6) used scope={"user_id": "..."} only,
but ADK's VertexAiMemoryBankService writes with scope={"app_name": "...",
"user_id": "..."} (two keys). Retrieve is exact-match (Test 5), so the old
memories are invisible to Jarvis. This script writes ONE memory with the
Jarvis-correct scope so we have something for preload_memory_tool to find
on the first chat.

Seeded fact is deliberately fictional and unique so we can tell when Jarvis
retrieved it vs. hallucinated something plausible:

    fact:  "Tony's workshop mainframe runs a custom Linux distribution called 'StarkOS-17'."

Test question ideas (ask Jarvis after starting adk web):
    - "What OS is my workshop mainframe running?"
    - "What's the name of my custom Linux distro?"

A model with NO memory cannot guess "StarkOS-17". A model with memory should
reproduce the exact name.

Safe to re-run - each call creates a new memory (consolidation may merge
duplicates into the existing one per Test 6).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"

# ADK session scope for Jarvis. app_name defaults to the agent directory name.
# user_id "user" matches what the bundled adk web UI sends by default (hardcoded
# in its JS bundle). Change if you're running through a custom frontend that
# sets a real user_id.
APP_NAME = "jarvis_agent"
USER_ID = "user"

FACT = (
    "Tony's workshop mainframe runs a custom Linux distribution called 'StarkOS-17'."
)


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
    print("Seeding Jarvis-scoped memory")
    print("=" * 70)
    print(f"Project:  {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print(f"Engine:   {agent_engine_id}")
    print(f"Scope:    {{'app_name': '{APP_NAME}', 'user_id': '{USER_ID}'}}")
    print(f"Fact:     {FACT}")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    operation = client.agent_engines.memories.create(
        name=agent_engine_id,
        fact=FACT,
        scope={"app_name": APP_NAME, "user_id": USER_ID},
    )

    mem = operation.response
    print("Seeded.")
    print(f"  memory.name:  {mem.name}")
    print(f"  memory.fact:  {mem.fact}")
    print(f"  memory.scope: {mem.scope}")


if __name__ == "__main__":
    main()
