import os
from google.cloud import storage

# --- Configuration ---
# The name of your GCS bucket, as we defined it.
BUCKET_NAME = "adk-agent-context-ninth-potion-455712-g9"
# The main folder for this agent bundle.
BASE_FOLDER = "ADK_Agent_Bundle_1"

def fetch_instructions(agent_name: str) -> str:
    """
    Fetches agent instructions from Google Cloud Storage.

    Args:
        agent_name: The name of the agent (e.g., 'calc_agent').

    Returns:
        The instruction text as a string.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)

        # Construct the full path to the instruction file
        # e.g., ADK_Agent_Bundle_1/calc_agent/calc_agent_instructions.txt
        file_path = f"{BASE_FOLDER}/{agent_name}/{agent_name}_instructions.txt"
        
        blob = bucket.blob(file_path)
        instructions = blob.download_as_text(encoding='utf-8')
        
        print(f"Successfully fetched instructions for '{agent_name}' from GCS.")
        return instructions

    except Exception as e:
        print(f"ERROR: Could not fetch instructions for '{agent_name}'. Error: {e}")
        # Return a fallback instruction in case of an error
        return f"Error: Could not load instructions for {agent_name}."


DUAL_INSTRUCTION_DELIMITER = "\n\n---\n# AGENT IDENTITY\n---\n\n"


def fetch_dual_instructions(agent_name: str) -> str:
    """
    Fetches and combines a global system prompt and an agent-specific identity
    prompt from GCS. Reads GCS_BUCKET_NAME and GCS_BASE_FOLDER from environment.

    Load order: global prompt first, then agent identity prompt, separated by
    DUAL_INSTRUCTION_DELIMITER. Falls back to identity-only if global fails.
    Returns an error string if the identity prompt cannot be loaded.

    Args:
        agent_name: The name of the agent (e.g., 'architect_agent').

    Returns:
        Combined instruction string, or an error string on identity failure.
    """
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    base_folder = os.environ.get("GCS_BASE_FOLDER")

    if not bucket_name:
        print("ERROR: GCS_BUCKET_NAME environment variable is not set.")
        return "Error: GCS_BUCKET_NAME is not configured."
    if not base_folder:
        print("ERROR: GCS_BASE_FOLDER environment variable is not set.")
        return "Error: GCS_BASE_FOLDER is not configured."

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    # --- Load global system prompt ---
    global_path = f"{base_folder}/globals/global_agent_system_prompt.md"
    global_content = None
    try:
        global_blob = bucket.blob(global_path)
        global_content = global_blob.download_as_text(encoding="utf-8")
        print(f"Loaded global prompt ({len(global_content)} chars) for {agent_name}.")
    except Exception as e:
        print(f"WARNING: Could not load global prompt from '{global_path}'. Falling back to identity-only. Error: {e}")

    # --- Load agent identity prompt ---
    identity_path = f"{base_folder}/{agent_name}/{agent_name}_system_prompt.md"
    try:
        identity_blob = bucket.blob(identity_path)
        identity_content = identity_blob.download_as_text(encoding="utf-8")
        print(f"Loaded identity prompt ({len(identity_content)} chars) for {agent_name}.")
    except Exception as e:
        print(f"ERROR: Could not load identity prompt from '{identity_path}'. Error: {e}")
        return f"Error: Could not load identity instructions for {agent_name}."

    # --- Combine ---
    if global_content:
        combined = global_content + DUAL_INSTRUCTION_DELIMITER + identity_content
        print(f"Loaded global prompt ({len(global_content)} chars) + identity prompt ({len(identity_content)} chars) for {agent_name}.")
    else:
        combined = identity_content

    return combined


def write_gcs_file(bucket_name: str, file_path: str, content: str) -> None:
    """Writes (creates or overwrites) a text file in GCS."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    blob.upload_from_string(content, content_type="text/plain; charset=utf-8")


def list_gcs_files(bucket_name: str, prefix: str) -> list[str]:
    """Returns a list of blob names under the given GCS prefix."""
    storage_client = storage.Client()
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
    return [blob.name for blob in blobs]