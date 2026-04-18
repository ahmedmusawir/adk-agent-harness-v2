# callbacks/receipt_callback.py
import os
import time
import datetime

from utils.run_receipt import create_receipt, format_receipt, save_receipt_to_file

_RECEIPT_DIR = "logs/receipts"


def _extract_text(content) -> str:
    """Extract plain text from a types.Content object, skipping non-text parts."""
    if content is None:
        return ""
    return " ".join(
        part.text
        for part in (content.parts or [])
        if getattr(part, "text", None)
    )


def get_timestamp_inject_callback():
    """Returns a before_model_callback that injects the current UTC timestamp
    into the system instruction on every model invocation.

    Uses direct assignment (not append_instructions) to REPLACE any previous
    timestamp — append accumulates across turns, causing the agent to see a
    growing list of old timestamps and read the first (stale) one.

    Format injected: [SYSTEM_TIMESTAMP: 2026-04-02T14:30:00Z]
    """

    def _inject_timestamp(callback_context, llm_request):
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ts_line = f"[SYSTEM_TIMESTAMP: {ts}]"

        # Print for debug visibility — confirm each turn gets a fresh timestamp
        print(f"[timestamp_callback] {ts_line}")

        # Strip any previous SYSTEM_TIMESTAMP line, then prepend the fresh one.
        # This replaces rather than accumulates — avoids stale timestamps across turns.
        existing = llm_request.config.system_instruction or ""
        clean = "\n".join(
            line for line in existing.split("\n")
            if not line.startswith("[SYSTEM_TIMESTAMP:")
        ).strip()
        llm_request.config.system_instruction = f"{ts_line}\n\n{clean}" if clean else ts_line
        return None

    return _inject_timestamp


def get_start_time_callback():
    """Returns a before_model_callback that records the run start time in session state."""

    def _before(callback_context, llm_request):
        callback_context.state["_run_start_time"] = time.time()
        return None

    return _before


def get_receipt_callback(agent_name: str, model: str):
    """Returns an after_model_callback that logs a run receipt.

    The callback:
    1. Skips partial (streaming chunk) responses.
    2. Reads latency from session state set by get_start_time_callback().
    3. Extracts input text from callback_context.user_content.
    4. Extracts output text from llm_response.content.
    5. Calls create_receipt() → format_receipt() → save_receipt_to_file().
    6. On any error, prints a warning and lets the agent continue normally.
    """

    def _after(callback_context, llm_response):
        # Skip intermediate streaming chunks — only log the final response.
        if llm_response.partial is True:
            return None

        start_time = callback_context.state.get("_run_start_time") or time.time()
        latency_ms = (time.time() - start_time) * 1000

        input_text = _extract_text(callback_context.user_content) or "N/A"
        output_text = _extract_text(llm_response.content) or "N/A"

        try:
            receipt = create_receipt(
                agent_name=agent_name,
                model=model,
                input_text=input_text,
                output_text=output_text,
                latency_ms=latency_ms,
            )
            print(format_receipt(receipt))
            os.makedirs(_RECEIPT_DIR, exist_ok=True)
            filepath = os.path.join(_RECEIPT_DIR, f"{agent_name}.jsonl")
            save_receipt_to_file(receipt, filepath)
        except Exception as e:
            print(f"[receipt_callback] Warning: failed to save receipt: {e}")

        return None

    return _after
