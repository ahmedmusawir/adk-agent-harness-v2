import pytest
from unittest.mock import MagicMock, patch


def _patch_env(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GCS_BASE_FOLDER", "test-folder")


# ---------------------------------------------------------------------------
# Unit tests — no real GCS calls
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_read_context_doc_returns_content(monkeypatch):
    """Returns the full text of a known context document from GCS."""
    _patch_env(monkeypatch)

    doc_content = "# APP_ARCHITECTURE_MANUAL\nLayer 0: Environment\nLayer 1: Agent Core"

    mock_blob = MagicMock()
    mock_blob.download_as_text.return_value = doc_content
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client):
        from architect_agent.tools import read_context_doc
        result = read_context_doc("APP_ARCHITECTURE_MANUAL")

    assert result == doc_content


@pytest.mark.unit
def test_read_context_doc_missing_file(monkeypatch):
    """Returns a clear error message (not an exception) when doc does not exist."""
    _patch_env(monkeypatch)

    mock_blob = MagicMock()
    mock_blob.download_as_text.side_effect = Exception("404 Not Found")
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client):
        from architect_agent.tools import read_context_doc
        result = read_context_doc("FAKE_DOC")

    assert "FAKE_DOC" in result
    assert "not found" in result
    assert isinstance(result, str)


@pytest.mark.unit
def test_read_context_doc_index_readable(monkeypatch):
    """CONTEXT_INDEX can be loaded successfully."""
    _patch_env(monkeypatch)

    index_content = "# CONTEXT INDEX\n- APP_ARCHITECTURE_MANUAL\n- ENGINEER_PLAYBOOK"

    mock_blob = MagicMock()
    mock_blob.download_as_text.return_value = index_content
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client):
        from architect_agent.tools import read_context_doc
        result = read_context_doc("CONTEXT_INDEX")

    assert result == index_content


@pytest.mark.unit
def test_read_context_doc_path_construction(monkeypatch):
    """GCS path is constructed as {BASE_FOLDER}/architect_agent/context/{doc_name}.md"""
    _patch_env(monkeypatch)

    mock_blob = MagicMock()
    mock_blob.download_as_text.return_value = "content"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client):
        from architect_agent.tools import read_context_doc
        read_context_doc("APP_ARCHITECTURE_MANUAL")

    mock_bucket.blob.assert_called_once_with(
        "test-folder/architect_agent/context/APP_ARCHITECTURE_MANUAL.md"
    )
