import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_blob(name: str, content: str, exists: bool = True) -> MagicMock:
    blob = MagicMock()
    blob.name = name
    blob.exists.return_value = exists
    blob.download_as_text.return_value = content
    return blob


def _patch_env(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GCS_BASE_FOLDER", "test-folder")


# ---------------------------------------------------------------------------
# write_session_memory tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_write_session_creates_file(monkeypatch):
    """When no session file exists today, write_session_memory creates it."""
    _patch_env(monkeypatch)

    mock_blob = _make_blob("test-folder/architect_agent/sessions/session-2026-03-27.md", "", exists=False)
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client), \
         patch("utils.gcs_utils.storage.Client", return_value=mock_client):
        from architect_agent.tools import write_session_memory
        result = write_session_memory("Started composite agent build today.")

    assert "session-" in result
    assert "architect_agent" in result
    mock_blob.upload_from_string.assert_called_once()
    uploaded_content = mock_blob.upload_from_string.call_args[0][0]
    assert "Started composite agent build today." in uploaded_content


@pytest.mark.unit
def test_write_session_appends(monkeypatch):
    """Two writes on the same day produce one file with both entries."""
    _patch_env(monkeypatch)

    existing = "## 2026-03-27 10:00 UTC\nFirst entry.\n"
    mock_blob = _make_blob("test-folder/architect_agent/sessions/session-2026-03-27.md", existing, exists=True)
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client), \
         patch("utils.gcs_utils.storage.Client", return_value=mock_client):
        from architect_agent.tools import write_session_memory
        write_session_memory("Second entry.")

    uploaded_content = mock_blob.upload_from_string.call_args[0][0]
    assert "First entry." in uploaded_content
    assert "Second entry." in uploaded_content


# ---------------------------------------------------------------------------
# read_session_memory tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_read_session_empty_folder(monkeypatch):
    """Returns informative message when no session files exist."""
    _patch_env(monkeypatch)

    mock_client = MagicMock()
    mock_client.list_blobs.return_value = []

    with patch("utils.gcs_utils.storage.Client", return_value=mock_client):
        from architect_agent.tools import read_session_memory
        result = read_session_memory(days=7)

    assert "No session files found" in result
    assert "7" in result


@pytest.mark.unit
def test_read_session_returns_recent(monkeypatch):
    """read_session_memory returns files within the day window and excludes older ones."""
    _patch_env(monkeypatch)

    today = datetime.now(timezone.utc).date()
    recent_date = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    old_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")

    recent_blob_name = f"test-folder/architect_agent/sessions/session-{recent_date}.md"
    old_blob_name = f"test-folder/architect_agent/sessions/session-{old_date}.md"

    # Patch list_gcs_files directly — avoids collision with gcs.Client patch
    mock_list = MagicMock(return_value=[recent_blob_name, old_blob_name])

    read_blob = _make_blob(recent_blob_name, "Recent session content.")
    read_bucket = MagicMock()
    read_bucket.blob.return_value = read_blob
    read_mock_client = MagicMock()
    read_mock_client.bucket.return_value = read_bucket

    with patch("architect_agent.tools.list_gcs_files", mock_list), \
         patch("architect_agent.tools.gcs.Client", return_value=read_mock_client):
        from architect_agent.tools import read_session_memory
        result = read_session_memory(days=7)

    assert "Recent session content." in result
    assert old_date not in result


@pytest.mark.unit
def test_read_session_newest_first(monkeypatch):
    """Session files are returned in reverse chronological order (newest first)."""
    _patch_env(monkeypatch)

    today = datetime.now(timezone.utc).date()
    date_1 = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_2 = (today - timedelta(days=5)).strftime("%Y-%m-%d")

    name_1 = f"test-folder/architect_agent/sessions/session-{date_1}.md"
    name_2 = f"test-folder/architect_agent/sessions/session-{date_2}.md"

    # Return older one first — test verifies output is newest-first regardless
    mock_list = MagicMock(return_value=[name_2, name_1])

    read_bucket = MagicMock()
    def read_blob_side_effect(path):
        b = MagicMock()
        b.download_as_text.return_value = f"Content of {path.split('/')[-1]}"
        return b
    read_bucket.blob.side_effect = read_blob_side_effect
    read_mock_client = MagicMock()
    read_mock_client.bucket.return_value = read_bucket

    with patch("architect_agent.tools.list_gcs_files", mock_list), \
         patch("architect_agent.tools.gcs.Client", return_value=read_mock_client):
        from architect_agent.tools import read_session_memory
        result = read_session_memory(days=7)

    # Newer date (date_1) should appear before older date (date_2) in the output
    assert result.index(date_1) < result.index(date_2)
