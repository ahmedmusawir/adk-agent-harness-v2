"""Validates that the tuned Memory Bank engine extracts memories correctly.

Sends a 6-exchange technical conversation through memories.generate() under
an isolated test scope (user_id="test_tuning") and hydrates every extracted
memory to show the actual fact text. Then runs a content-coverage audit:
each expected technical detail + the small-talk line are checked for
capture/filter correctness.

Run AFTER update_engine_config.py. Running BEFORE the update yields the old
baseline behavior — useful as a control, but not the main purpose of this
script.

Re-runs accumulate memories under user_id="test_tuning". Consolidation
(Test 6 behavior) will merge duplicates. Clean up via
cleanup_memories_by_scope.py with TARGET_SCOPE={"user_id": "test_tuning"}
if the scope gets noisy.
"""

import os
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"

TEST_SCOPE = {"user_id": "test_tuning"}

# Conversation: 6 user turns + 6 model acks = 12 events.
# Covers architecture decision, tool preference, lesson learned, constraint,
# technology choice, and small talk (which should NOT be extracted).
CONVERSATION = [
    ("user",
     "We're using Supabase Team plan with HIPAA add-on as the database layer "
     "for Mothership."),
    ("model",
     "Noted — Supabase Team with HIPAA add-on for the Mothership database."),

    ("user",
     "I switched from VS Code to Cursor for daily development."),
    ("model",
     "Got it — Cursor is your new primary editor."),

    ("user",
     "Building the eval runner taught us that ADK's web UI has frontend/"
     "backend sync gaps — standalone runners bypass those limitations."),
    ("model",
     "Understood — standalone runners over the web UI for eval work."),

    ("user",
     "Frank's existing GCP infrastructure must be fully inventoried before "
     "we replace anything — discovery-first, no rip-and-replace."),
    ("model",
     "Discovery-first on Frank's GCP. No rip-and-replace until the inventory "
     "is complete."),

    ("user",
     "Using Google ADK with Gemini 2.5 Flash for the agent runtime, but "
     "keeping Claude as the architect role."),
    ("model",
     "ADK + Gemini 2.5 Flash for runtime, Claude for architect. Logged."),

    ("user",
     "Hey Jarvis, how's it going today?"),
    ("model",
     "Doing well, sir. Ready for the next task."),
]

# Content-coverage audit — keyword presence test against extracted facts.
# Each entry: (label, keywords_any_of_these_indicates_capture, should_be_captured).
COVERAGE_CHECKS = [
    ("Supabase Mothership DB decision",
     ["supabase", "mothership"], True),
    ("VS Code -> Cursor switch",
     ["cursor"], True),
    ("Eval runner / standalone lesson",
     ["eval", "standalone", "sync gap"], True),
    ("Frank GCP discovery-first constraint",
     ["frank", "discovery", "inventor"], True),
    ("ADK + Gemini 2.5 Flash / Claude architect stack",
     ["adk", "gemini 2.5 flash", "claude"], True),
    ("Small-talk ('how's it going') should be FILTERED",
     ["how's it going", "doing well"], False),
]


def _build_events() -> list[dict]:
    return [
        {"content": {"role": role, "parts": [{"text": text}]}}
        for role, text in CONVERSATION
    ]


def _check_any(keywords: list[str], haystack: str) -> bool:
    h = haystack.lower()
    return any(kw.lower() in h for kw in keywords)


def main() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    agent_engine_id = os.getenv("AGENT_ENGINE_ID")
    if not agent_engine_id:
        raise RuntimeError(
            f"AGENT_ENGINE_ID not found in {env_path}. "
            "Run setup_agent_engine.py or list_agent_engines.py first."
        )

    print("=" * 70)
    print("TEST — Tuned extraction validation")
    print("=" * 70)
    print(f"Project:   {PROJECT_ID}")
    print(f"Location:  {LOCATION}")
    print(f"Engine:    {agent_engine_id}")
    print(f"Scope:     {TEST_SCOPE}")
    print(f"Turns:     {len(CONVERSATION)}")
    print("-" * 70)
    print("Conversation:")
    for i, (role, text) in enumerate(CONVERSATION, start=1):
        print(f"  [{i:>2}] {role:>5}: {text}")
    print("-" * 70)

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    print("Calling memories.generate() ...")
    t_start = time.monotonic()
    try:
        operation = client.agent_engines.memories.generate(
            name=agent_engine_id,
            direct_contents_source={"events": _build_events()},
            scope=TEST_SCOPE,
            # config defaults: wait_for_completion=True, disable_consolidation=None
        )
    except Exception as e:
        print(f"\nGENERATE FAILED: {type(e).__name__}: {e}")
        print("-" * 70)
        print(traceback.format_exc())
        raise
    elapsed = time.monotonic() - t_start
    print(f"generate() returned in {elapsed:.2f}s.")
    print(f"operation.done:  {operation.done}")
    print(f"operation.error: {operation.error}")
    print("-" * 70)

    response = getattr(operation, "response", None)
    skeletal = getattr(response, "generated_memories", None) if response else None
    if not skeletal:
        print("No generated_memories in response — extraction produced nothing.")
        print("Nothing to hydrate. Exiting.")
        return

    # Hydrate each skeletal memory (name-only) via get().
    print(f"Hydrating {len(skeletal)} extracted memory(ies) ...")
    print("-" * 70)
    facts: list[str] = []
    for i, item in enumerate(skeletal, start=1):
        action = str(getattr(item, "action", "<no-action>"))
        mem_name = getattr(getattr(item, "memory", None), "name", None)
        if not mem_name:
            print(f"  [{i}] <no name>  action={action}")
            continue
        short_id = mem_name.split("/memories/")[-1]
        try:
            full = client.agent_engines.memories.get(name=mem_name)
            fact = full.fact or "<no fact>"
        except Exception as e:
            fact = f"<get failed: {type(e).__name__}: {e}>"
        facts.append(fact)
        print(f"  [{i}] {action:<32}  id={short_id}")
        print(f"       fact: {fact}")
    print("-" * 70)

    # Coverage audit.
    all_facts_blob = " || ".join(facts)
    print("Content coverage audit:")
    audit_rows = []
    for label, keywords, should_capture in COVERAGE_CHECKS:
        found = _check_any(keywords, all_facts_blob)
        # Correctness: captured ↔ should_capture
        ok = found == should_capture
        status = "PASS" if ok else "FAIL"
        verdict = (
            "captured (expected)"     if (found and should_capture)     else
            "filtered (expected)"     if (not found and not should_capture) else
            "captured (UNEXPECTED)"   if (found and not should_capture) else
            "missing (UNEXPECTED)"
        )
        audit_rows.append((status, label, verdict))
        print(f"  [{status}] {label}")
        print(f"         → {verdict}")
    print("-" * 70)

    # Summary line.
    passed = sum(1 for r in audit_rows if r[0] == "PASS")
    total = len(audit_rows)
    print(f"Extraction audit: {passed}/{total} checks passed.")
    print(f"Total memories extracted: {len(skeletal)}")
    print(f"Elapsed generate() time:  {elapsed:.2f}s")

    if passed < total:
        raise RuntimeError(
            f"Extraction audit failed: {total - passed} of {total} checks did "
            "not match expectations. See rows marked FAIL above."
        )


if __name__ == "__main__":
    main()
