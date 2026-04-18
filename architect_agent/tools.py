import os
from datetime import datetime, timezone, timedelta

from google.adk.tools import FunctionTool
from google.cloud import storage as gcs

from utils.gcs_utils import write_gcs_file, list_gcs_files

# agent_name is hardcoded here — these tools live inside architect_agent
_AGENT_NAME = "architect_agent"


def _get_gcs_config() -> tuple[str, str]:
    """Returns (bucket_name, base_folder) from environment. Raises ValueError if missing."""
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    base_folder = os.environ.get("GCS_BASE_FOLDER")
    if not bucket_name:
        raise ValueError("GCS_BUCKET_NAME environment variable is not set.")
    if not base_folder:
        raise ValueError("GCS_BASE_FOLDER environment variable is not set.")
    return bucket_name, base_folder


def write_session_memory(content: str) -> str:
    """
    Appends a timestamped entry to today's session file in GCS.

    If today's session file already exists, the new content is appended.
    If it does not exist, a new file is created.

    Args:
        content: The session update text to write.

    Returns:
        Confirmation message with the GCS path written to.
    """
    try:
        bucket_name, base_folder = _get_gcs_config()
    except ValueError as e:
        return f"Error: {e}"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_path = f"{base_folder}/{_AGENT_NAME}/sessions/session-{today}.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Read existing content if file already exists
    storage_client = gcs.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_path)

    existing_content = ""
    if blob.exists():
        existing_content = blob.download_as_text(encoding="utf-8")

    new_entry = f"\n## {timestamp}\n{content}\n"
    updated_content = existing_content + new_entry

    write_gcs_file(bucket_name, file_path, updated_content)
    print(f"Session memory written to: {file_path}")
    return f"Session update written to: gs://{bucket_name}/{file_path}"


def read_session_memory(days: int = 7) -> str:
    """
    Reads recent session files from GCS to restore context from prior sessions.

    Lists all session files in the architect_agent sessions folder, filters to
    files within the given date window, and returns their content newest-first.

    Args:
        days: How many days back to read (default 7).

    Returns:
        Concatenated content of session files within the window, newest first.
        Returns an informative message if no files are found.
    """
    try:
        bucket_name, base_folder = _get_gcs_config()
    except ValueError as e:
        return f"Error: {e}"

    prefix = f"{base_folder}/{_AGENT_NAME}/sessions/"
    all_files = list_gcs_files(bucket_name, prefix)

    # Filter to session-YYYY-MM-DD.md files within the date window
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    matched = []
    for file_name in all_files:
        # blob name is the full path; extract just the filename part
        basename = file_name.split("/")[-1]
        if not basename.startswith("session-") or not basename.endswith(".md"):
            continue
        try:
            file_date_str = basename[len("session-"):-len(".md")]
            file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date >= cutoff:
            matched.append((file_date, file_name))

    if not matched:
        return f"No session files found for the last {days} days."

    # Sort newest first
    matched.sort(key=lambda x: x[0], reverse=True)

    storage_client = gcs.Client()
    bucket = storage_client.bucket(bucket_name)

    sections = []
    for file_date, file_path in matched:
        blob = bucket.blob(file_path)
        file_content = blob.download_as_text(encoding="utf-8")
        sections.append(f"# Session: {file_date}\n\n{file_content}")

    return "\n\n---\n\n".join(sections)


def get_current_datetime() -> str:
    """
    Returns the current UTC date and time as an ISO 8601 string.

    Use this when you need to know the current date/time for calculations,
    comparisons, or when constructing dated references in your responses.

    Returns:
        UTC timestamp string in ISO 8601 format (e.g. "2026-04-02T14:30:00Z").
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def invoke_skill(skill_name: str) -> str:
    """
    Loads a skill instruction file from the shared skills library in GCS.

    Skill files contain workflow instructions the agent should follow.
    They are stored in GCS so they can be updated without redeployment.

    Args:
        skill_name: Name of the skill to load, without the .md extension.
                    Use SCREAMING_SNAKE_CASE (e.g. "SESSION_UPDATE_SKILL").

    Returns:
        Full content of the skill markdown file, or an error message if not found.
    """
    try:
        bucket_name, base_folder = _get_gcs_config()
    except ValueError as e:
        return f"Error: {e}"

    # SKILL_INDEX stays flat; all other skills live in a subfolder named after them
    if skill_name == "SKILL_INDEX":
        file_path = f"{base_folder}/globals/skills/SKILL_INDEX.md"
    else:
        file_path = f"{base_folder}/globals/skills/{skill_name}/SKILL.md"

    try:
        storage_client = gcs.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        content = blob.download_as_text(encoding="utf-8")
        print(f"Loaded skill '{skill_name}' ({len(content)} chars) from GCS.")
        return content
    except Exception:
        return f"Skill '{skill_name}' not found in globals/skills."


def read_context_doc(doc_name: str) -> str:
    """
    Loads a context document from the agent's context library in GCS.

    Context documents include manuals, playbooks, transcripts, and reference
    materials. Use CONTEXT_INDEX to see what documents are available.

    Args:
        doc_name: Name of the document without the .md extension.
                  Use SCREAMING_SNAKE_CASE (e.g. "APP_ARCHITECTURE_MANUAL").

    Returns:
        Full content of the document, or an error message if not found.
    """
    try:
        bucket_name, base_folder = _get_gcs_config()
    except ValueError as e:
        return f"Error: {e}"

    # All context docs (including CONTEXT_INDEX) live in the agent's context/ folder
    file_path = f"{base_folder}/{_AGENT_NAME}/context/{doc_name}.md"

    try:
        storage_client = gcs.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        content = blob.download_as_text(encoding="utf-8")
        print(f"Loaded context doc '{doc_name}' ({len(content)} chars) from GCS.")
        return content
    except Exception:
        return f"Context document '{doc_name}' not found in architect_agent/context/"


# ADK FunctionTool instances
write_session_memory_tool = FunctionTool(func=write_session_memory)
read_session_memory_tool = FunctionTool(func=read_session_memory)
invoke_skill_tool = FunctionTool(func=invoke_skill)
get_current_datetime_tool = FunctionTool(func=get_current_datetime)
read_context_doc_tool = FunctionTool(func=read_context_doc)
