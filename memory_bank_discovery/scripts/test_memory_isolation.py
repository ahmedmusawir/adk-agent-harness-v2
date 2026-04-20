"""Test 5 - Memory isolation across user scopes.

Verifies that memories written under one user_id never leak into retrieve()
calls scoped to a different user_id. This is THE multi-tenant safety test -
if it fails, Memory Bank cannot be trusted to hold per-user context for
multiple users sharing the same agent engine.

Plan:
  1. Write a new memory under scope={"user_id": "peter_parker"} via create().
  2. list() the engine - confirms list is unscoped (admin-view).
  3. retrieve() three times:
        - scope tony_stark   -> tony_set
        - scope peter_parker -> peter_set
        - scope nobody_exists -> nobody_set
  4. Assert:
        A1 (critical): tony_set intersect peter_set is empty.
        A2:           nobody_set is empty (retrieve is exact-match, not wildcard).
        A3:           peter_set contains the memory we just wrote.

Idempotency note: running this script N times accumulates N Peter memories
(dedup behavior is Test 6's question). All assertions still hold regardless.
"""

import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"

TONY_USER = "tony_stark"
PETER_USER = "peter_parker"
NOBODY_USER = "nobody_exists"

PETER_FACT = "Peter prefers Rust for systems programming"


def _section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _names(memory_iter) -> set[str]:
    """Materialize an iterator of Memory (or wrapper) objects into a set of names."""
    names: set[str] = set()
    for item in memory_iter:
        # retrieve() returns RetrieveMemoriesResponseRetrievedMemory wrappers
        # with .memory; list() returns Memory objects directly.
        mem = getattr(item, "memory", item)
        name = getattr(mem, "name", None)
        if name:
            names.add(name)
    return names


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
    print("TEST 5 - Memory Isolation")
    print("=" * 70)
    print(f"Project:    {PROJECT_ID}")
    print(f"Location:   {LOCATION}")
    print(f"Engine:     {agent_engine_id}")
    print(f"Test users: tony={TONY_USER}, peter={PETER_USER}, nobody={NOBODY_USER}")

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
    results: dict[str, bool] = {}

    # -----------------------------------------------------------------
    # Step 1: WRITE a Peter memory via create()
    # -----------------------------------------------------------------
    _section(f"[1/4] create(scope={{'user_id': '{PETER_USER}'}})")
    peter_memory_name: str | None = None
    try:
        op = client.agent_engines.memories.create(
            name=agent_engine_id,
            fact=PETER_FACT,
            scope={"user_id": PETER_USER},
        )
        peter_memory_name = op.response.name
        print(f"Wrote Peter memory: {peter_memory_name}")
        print(f"  fact:  {op.response.fact}")
        print(f"  scope: {op.response.scope}")
        results["create_peter"] = True
    except Exception as e:
        print(f"FAILURE: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        results["create_peter"] = False

    # -----------------------------------------------------------------
    # Step 2: LIST all memories (no scope arg) - confirms unscoped view
    # -----------------------------------------------------------------
    _section("[2/4] list(name=ENGINE) - unscoped")
    all_names: set[str] = set()
    try:
        all_memories = list(client.agent_engines.memories.list(name=agent_engine_id))
        print(f"Total memories on engine: {len(all_memories)}")
        # Group by scope for easy visual audit.
        by_scope: dict[str, list[str]] = {}
        for mem in all_memories:
            key = str(mem.scope)
            by_scope.setdefault(key, []).append(mem.fact or "<no fact>")
        for scope_key, facts in by_scope.items():
            print(f"\n  scope={scope_key}:")
            for f in facts:
                print(f"    - {f}")
        all_names = {m.name for m in all_memories}
        results["list_unscoped"] = True
    except Exception as e:
        print(f"FAILURE: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        results["list_unscoped"] = False

    # -----------------------------------------------------------------
    # Step 3: RETRIEVE under three different scopes
    # -----------------------------------------------------------------
    def retrieve(user_id: str) -> set[str] | None:
        try:
            iterator = client.agent_engines.memories.retrieve(
                name=agent_engine_id,
                scope={"user_id": user_id},
            )
            names = _names(iterator)
            print(f"  scope {{'user_id': '{user_id}'}} -> {len(names)} memory(ies)")
            for n in sorted(names):
                print(f"    {n}")
            return names
        except Exception as e:
            print(f"FAILURE retrieving {user_id}: {type(e).__name__}: {e}")
            print(traceback.format_exc())
            return None

    _section("[3/4] retrieve(scope=...) x 3")
    tony_set = retrieve(TONY_USER)
    peter_set = retrieve(PETER_USER)
    nobody_set = retrieve(NOBODY_USER)
    results["retrieve_tony"] = tony_set is not None
    results["retrieve_peter"] = peter_set is not None
    results["retrieve_nobody"] = nobody_set is not None

    # -----------------------------------------------------------------
    # Step 4: ASSERTIONS
    # -----------------------------------------------------------------
    _section("[4/4] ASSERTIONS")

    # A1 - critical: no cross-user leakage
    if tony_set is not None and peter_set is not None:
        leaked = tony_set & peter_set
        if leaked:
            print(f"A1 FAIL: {len(leaked)} memory(ies) leaked across scopes:")
            for n in sorted(leaked):
                print(f"    {n}")
            results["A1_isolation"] = False
        else:
            print("A1 PASS: tony_set and peter_set are disjoint (no cross-user leak).")
            results["A1_isolation"] = True
    else:
        print("A1 SKIP: one of the retrieve calls failed; cannot evaluate.")
        results["A1_isolation"] = False

    # A2 - retrieve with nonexistent user returns empty (not error, not wildcard)
    if nobody_set is not None:
        if len(nobody_set) == 0:
            print("A2 PASS: retrieve(nobody_exists) returned 0 memories.")
            results["A2_empty"] = True
        else:
            print(f"A2 FAIL: retrieve(nobody_exists) returned {len(nobody_set)} memories - retrieve is not strict about scope.")
            results["A2_empty"] = False
    else:
        print("A2 SKIP: retrieve(nobody_exists) failed; cannot evaluate.")
        results["A2_empty"] = False

    # A3 - Peter write is retrievable by Peter
    if peter_set is not None and peter_memory_name is not None:
        if peter_memory_name in peter_set:
            print("A3 PASS: newly-written Peter memory is retrievable under Peter's scope.")
            results["A3_peter_retrievable"] = True
        else:
            print(f"A3 FAIL: {peter_memory_name} not found in peter_set.")
            print(f"    peter_set: {peter_set}")
            results["A3_peter_retrievable"] = False
    else:
        print("A3 SKIP: upstream failure prevents evaluation.")
        results["A3_peter_retrievable"] = False

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    _section("SUMMARY")
    for label, ok in results.items():
        print(f"  {label:<25} {'PASS' if ok else 'FAIL'}")

    if not all(results.values()):
        raise RuntimeError("One or more isolation checks failed - see above.")


if __name__ == "__main__":
    main()
