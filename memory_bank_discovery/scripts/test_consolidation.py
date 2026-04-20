"""Test 6 - Consolidation / Contradiction.

Question: when generate() sees a fact that contradicts an existing memory,
does Memory Bank's consolidation actually UPDATE or DELETE the old memory?
Or does it just CREATE a new one and leave the stale fact alongside it?

Existing tony memory M1 says: "Tony prefers Python for backend development".
We send a transcript where Tony says he's switched from Python to Go.
Consolidation is left ON (SDK default).

Three possible outcomes - all informative:
  1. Strong consolidation: (UPDATED, M1) or (DELETED, M1) + (CREATED, new).
  2. Weak consolidation:   (CREATED, new) only; M1 stays as stale contradiction.
  3. Silent drop:          0 memories returned; extraction didn't fire.

Method:
  BEFORE -> snapshot tony's (name, fact) pairs via retrieve()
  GENERATE -> send contradicting transcript
  AFTER  -> snapshot again
  DIFF   -> compute disappeared / appeared / changed sets
  CROSS-CHECK -> compare diff to actions the service returned

Destructive note: this test may DELETE or UPDATE M1. Acceptable for the
discovery sandbox - can be re-written via test_write_memory.py if needed.
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

# Contradicting transcript: direct, first-person, preference-flavored so
# extraction is likely to fire (see Test 4 finding: extraction is selective).
TRANSCRIPT = [
    ("user",  "Actually I've ditched Python - I'm using Go for all my backend work now."),
    ("model", "Got it, Go for backend."),
]


def _section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _snapshot_tony(client, engine_id: str) -> dict[str, str]:
    """Return {memory_name: fact} for all tony-scoped memories."""
    iterator = client.agent_engines.memories.retrieve(
        name=engine_id,
        scope={"user_id": USER_ID},
    )
    snap: dict[str, str] = {}
    for item in iterator:
        mem = item.memory
        snap[mem.name] = mem.fact or "<no fact>"
    return snap


def _print_snapshot(label: str, snap: dict[str, str]) -> None:
    print(f"{label}: {len(snap)} memory(ies)")
    for name, fact in snap.items():
        short = name.split("/memories/")[-1]
        print(f"  [{short}] {fact}")


def _build_events() -> list[dict]:
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
    print("TEST 6 - Consolidation / Contradiction")
    print("=" * 70)
    print(f"Project:    {PROJECT_ID}")
    print(f"Location:   {LOCATION}")
    print(f"Engine:     {agent_engine_id}")
    print(f"Scope:      {{'user_id': '{USER_ID}'}}")
    print(f"Transcript turns: {len(TRANSCRIPT)}")
    for i, (role, text) in enumerate(TRANSCRIPT, start=1):
        print(f"  [{i}] {role}: {text}")

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)
    results: dict[str, bool] = {}

    # ----------------------------------------------------------------
    # BEFORE
    # ----------------------------------------------------------------
    _section("[1/4] BEFORE - snapshot tony's memories")
    try:
        before = _snapshot_tony(client, agent_engine_id)
        _print_snapshot("BEFORE", before)
        results["before_snapshot"] = True
    except Exception as e:
        print(f"FAILURE: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        results["before_snapshot"] = False
        before = {}

    # ----------------------------------------------------------------
    # GENERATE with contradicting transcript
    # ----------------------------------------------------------------
    _section("[2/4] GENERATE - send contradicting transcript (consolidation ON)")
    actions_reported: list[tuple[str, str]] = []  # (action, memory_name)
    try:
        t_start = time.monotonic()
        operation = client.agent_engines.memories.generate(
            name=agent_engine_id,
            direct_contents_source={"events": _build_events()},
            scope={"user_id": USER_ID},
            # config defaults: wait_for_completion=True, disable_consolidation=None (ON)
        )
        elapsed = time.monotonic() - t_start

        print(f"generate() returned in {elapsed:.2f}s.")
        print(f"operation.done:  {operation.done}")
        print(f"operation.error: {operation.error}")

        response = getattr(operation, "response", None)
        generated = getattr(response, "generated_memories", None) if response else None
        if not generated:
            print("No generated_memories in response - extraction produced nothing.")
        else:
            print(f"Service reported {len(generated)} action(s):")
            for i, item in enumerate(generated, start=1):
                action = str(getattr(item, "action", "<none>"))
                mem = getattr(item, "memory", None)
                name = getattr(mem, "name", "<no name>") if mem else "<no memory>"
                short = name.split("/memories/")[-1]
                print(f"  [{i}] action={action}  memory=[{short}]")
                actions_reported.append((action, name))
        results["generate_call"] = True
    except Exception as e:
        print(f"FAILURE: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        results["generate_call"] = False

    # ----------------------------------------------------------------
    # AFTER
    # ----------------------------------------------------------------
    _section("[3/4] AFTER - snapshot tony's memories")
    try:
        after = _snapshot_tony(client, agent_engine_id)
        _print_snapshot("AFTER", after)
        results["after_snapshot"] = True
    except Exception as e:
        print(f"FAILURE: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        results["after_snapshot"] = False
        after = {}

    # ----------------------------------------------------------------
    # DIFF + CROSS-CHECK
    # ----------------------------------------------------------------
    _section("[4/4] DIFF + CROSS-CHECK")

    before_names = set(before.keys())
    after_names = set(after.keys())

    disappeared = before_names - after_names
    appeared = after_names - before_names
    common = before_names & after_names
    changed = {n for n in common if before[n] != after[n]}

    print(f"Disappeared (name in BEFORE not AFTER - suggests DELETED): {len(disappeared)}")
    for n in sorted(disappeared):
        short = n.split("/memories/")[-1]
        print(f"  [{short}] had fact: {before[n]!r}")

    print(f"\nAppeared (name in AFTER not BEFORE - suggests CREATED): {len(appeared)}")
    for n in sorted(appeared):
        short = n.split("/memories/")[-1]
        print(f"  [{short}] now has fact: {after[n]!r}")

    print(f"\nChanged (same name, different fact - suggests UPDATED): {len(changed)}")
    for n in sorted(changed):
        short = n.split("/memories/")[-1]
        print(f"  [{short}]")
        print(f"    BEFORE: {before[n]!r}")
        print(f"    AFTER:  {after[n]!r}")

    # Cross-check: do the reported actions line up with the observed diff?
    print("\nCross-check - actions reported by service vs. observed diff:")
    action_names = {name for _, name in actions_reported}
    print(f"  Service returned {len(actions_reported)} action(s) referencing {len(action_names)} unique memory(ies).")

    expected_touched = disappeared | appeared | changed
    mismatch_service_only = action_names - expected_touched
    mismatch_diff_only = expected_touched - action_names

    if not mismatch_service_only and not mismatch_diff_only:
        print("  Service-reported actions match observed diff exactly.")
    else:
        if mismatch_service_only:
            print(f"  Service mentioned {len(mismatch_service_only)} memory(ies) not reflected in diff:")
            for n in sorted(mismatch_service_only):
                print(f"    {n.split('/memories/')[-1]}")
        if mismatch_diff_only:
            print(f"  Observed diff touched {len(mismatch_diff_only)} memory(ies) the service didn't mention:")
            for n in sorted(mismatch_diff_only):
                print(f"    {n.split('/memories/')[-1]}")

    # Classify the outcome
    print("\nOUTCOME classification:")
    if not actions_reported and not (disappeared or appeared or changed):
        print("  -> SILENT DROP: extraction produced nothing; M1 untouched.")
    elif disappeared or changed:
        print("  -> STRONG CONSOLIDATION: an existing memory was DELETED or UPDATED.")
    elif appeared and not (disappeared or changed):
        print("  -> WEAK CONSOLIDATION: new memory CREATED alongside the contradicting one.")
    else:
        print("  -> UNCLASSIFIED: see diff above for details.")

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    _section("SUMMARY")
    for label, ok in results.items():
        print(f"  {label:<25} {'PASS' if ok else 'FAIL'}")

    if not all(results.values()):
        raise RuntimeError("One or more steps failed - see above.")


if __name__ == "__main__":
    main()
