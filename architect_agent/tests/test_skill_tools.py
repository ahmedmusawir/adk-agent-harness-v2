import pytest
from unittest.mock import MagicMock, patch


def _patch_env(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GCS_BASE_FOLDER", "test-folder")


# ---------------------------------------------------------------------------
# Unit tests — no real GCS calls
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_invoke_skill_returns_content(monkeypatch):
    """Returns the full text of a known skill file from GCS."""
    _patch_env(monkeypatch)

    skill_content = "# SESSION_UPDATE_SKILL\nWrite a session update after every major action."

    mock_blob = MagicMock()
    mock_blob.download_as_text.return_value = skill_content
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client):
        from architect_agent.tools import invoke_skill
        result = invoke_skill("SESSION_UPDATE_SKILL")

    assert result == skill_content
    # Confirm the correct GCS path was constructed (subfolder structure)
    mock_bucket.blob.assert_called_once_with("test-folder/globals/skills/SESSION_UPDATE_SKILL/SKILL.md")


@pytest.mark.unit
def test_invoke_skill_missing_file(monkeypatch):
    """Returns a clear error message (not an exception) when skill file does not exist."""
    _patch_env(monkeypatch)

    mock_blob = MagicMock()
    mock_blob.download_as_text.side_effect = Exception("404 Not Found")
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client):
        from architect_agent.tools import invoke_skill
        result = invoke_skill("NONEXISTENT_SKILL")

    assert result.startswith("Skill 'NONEXISTENT_SKILL' not found")
    assert isinstance(result, str)


@pytest.mark.unit
def test_invoke_skill_index_readable(monkeypatch):
    """SKILL_INDEX.md can be loaded successfully."""
    _patch_env(monkeypatch)

    index_content = "# SKILL INDEX\n- SESSION_UPDATE_SKILL\n- SESSION_MEMORY_SKILL\n- WEB_SEARCH_SKILL"

    mock_blob = MagicMock()
    mock_blob.download_as_text.return_value = index_content
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("architect_agent.tools.gcs.Client", return_value=mock_client):
        from architect_agent.tools import invoke_skill
        result = invoke_skill("SKILL_INDEX")

    assert "SKILL_INDEX" in result or "SKILL" in result
    # SKILL_INDEX stays at flat path — no subfolder
    mock_bucket.blob.assert_called_once_with("test-folder/globals/skills/SKILL_INDEX.md")
