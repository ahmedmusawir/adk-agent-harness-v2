import pytest
from unittest.mock import MagicMock, patch

from utils.gcs_utils import fetch_dual_instructions, DUAL_INSTRUCTION_DELIMITER


GLOBAL_CONTENT = "You are a general-purpose AI agent with these shared rules."
IDENTITY_CONTENT = "You are the Architect Agent. Your role is system design."


def _make_mock_client(global_text=GLOBAL_CONTENT, identity_text=IDENTITY_CONTENT,
                      global_raises=None, identity_raises=None):
    """Helper: returns a mock storage.Client() that serves controlled blob content."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    def blob_side_effect(path):
        mock_blob = MagicMock()
        if "globals/global_agent_system_prompt" in path:
            if global_raises:
                mock_blob.download_as_text.side_effect = global_raises
            else:
                mock_blob.download_as_text.return_value = global_text
        else:
            if identity_raises:
                mock_blob.download_as_text.side_effect = identity_raises
            else:
                mock_blob.download_as_text.return_value = identity_text
        return mock_blob

    mock_bucket.blob.side_effect = blob_side_effect
    return mock_client


# ---------------------------------------------------------------------------
# Unit tests — no real GCS calls
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dual_loader_combines_both_files(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GCS_BASE_FOLDER", "test-folder")

    with patch("utils.gcs_utils.storage.Client", return_value=_make_mock_client()):
        result = fetch_dual_instructions("architect_agent")

    assert GLOBAL_CONTENT in result
    assert IDENTITY_CONTENT in result


@pytest.mark.unit
def test_dual_loader_delimiter_present(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GCS_BASE_FOLDER", "test-folder")

    with patch("utils.gcs_utils.storage.Client", return_value=_make_mock_client()):
        result = fetch_dual_instructions("architect_agent")

    assert DUAL_INSTRUCTION_DELIMITER in result
    assert result.index(GLOBAL_CONTENT) < result.index(IDENTITY_CONTENT)


@pytest.mark.unit
def test_dual_loader_fallback_on_global_failure(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GCS_BASE_FOLDER", "test-folder")

    mock_client = _make_mock_client(global_raises=Exception("GCS 404"))

    with patch("utils.gcs_utils.storage.Client", return_value=mock_client):
        result = fetch_dual_instructions("architect_agent")

    assert IDENTITY_CONTENT in result
    assert DUAL_INSTRUCTION_DELIMITER not in result
    assert GLOBAL_CONTENT not in result


@pytest.mark.unit
def test_dual_loader_identity_failure_returns_error(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GCS_BASE_FOLDER", "test-folder")

    mock_client = _make_mock_client(identity_raises=Exception("GCS 404"))

    with patch("utils.gcs_utils.storage.Client", return_value=mock_client):
        result = fetch_dual_instructions("architect_agent")

    assert result.startswith("Error:")
    assert "architect_agent" in result
