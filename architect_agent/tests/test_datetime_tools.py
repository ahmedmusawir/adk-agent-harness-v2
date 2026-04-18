import pytest
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Unit tests — no GCS calls, no mocking needed
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_current_datetime_returns_valid_iso():
    """Tool returns a parseable ISO 8601 UTC string."""
    from architect_agent.tools import get_current_datetime

    result = get_current_datetime()

    # Must be parseable as a datetime
    parsed = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed is not None


@pytest.mark.unit
def test_get_current_datetime_is_utc():
    """Timestamp is current UTC — within 5 seconds of now."""
    from architect_agent.tools import get_current_datetime

    # Truncate to seconds — tool has second-level precision, not microsecond
    before = datetime.now(timezone.utc).replace(microsecond=0)
    result = get_current_datetime()
    after = datetime.now(timezone.utc).replace(microsecond=0)

    parsed = datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    assert before <= parsed <= after
