# In utils/context_utils.py

from google.cloud import storage
from google.cloud.exceptions import NotFound

# --- Configuration from your screenshot ---
BUCKET_NAME = "adk-agent-context-ninth-potion-455712-g9"
FOLDER_NAME = "ADK_Agent_Bundle_1/context_store"

# --- THIS IS THE NEW AND DYNAMIC FETCH CONTEXT FUNCTION FOR .MD FILES ---
def fetch_context(file_name: str) -> str:
    """
    Reads the full text of a specified context file from the knowledge base.
    
    Use this to answer any questions about DockBloxx products by passing
    'PRODUCTS.md' as the file_name.

    Args:
        file_name: The name of the context file to fetch (e.g., "PRODUCTS.md").

    Returns:
        The content of the file as a string, or an error message if not found.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_path = f"{FOLDER_NAME}/{file_name}"
        blob = bucket.blob(blob_path)

        print(f"--- FETCHING CONTEXT: {blob_path} from GCS ---")

        content = blob.download_as_text()
        return content

    except NotFound:
        error_message = f"ERROR: Context file '{file_name}' not found in the knowledge base."
        print(error_message)
        return error_message
    
    except Exception as e:
        error_message = f"An unexpected error occurred while fetching context file '{file_name}': {e}"
        print(error_message)
        return error_message
    

# --- THIS ONE WORKS WITH GREETING AGENT ONLY ... FIRST TEST ---
def fetch_document(file_name: str) -> str:
    """
    Reads the full text of a specified document from the knowledge base.
    
    Use this to answer any questions about the user's resume by passing
    'moose_resume.txt' as the file_name.

    Args:
        file_name: The name of the file to fetch (e.g., "tony_stark_resume.txt").

    Returns:
        The content of the file as a string, or an error message if not found.
    """
    try:
        # Initialize the client. This will use your default gcloud credentials.
        storage_client = storage.Client()

        # Get the bucket object.
        bucket = storage_client.bucket(BUCKET_NAME)

        # Construct the full path to the file within the folder.
        blob_path = f"{FOLDER_NAME}/{file_name}"

        # Get the blob (file) object.
        blob = bucket.blob(blob_path)

        print(f"--- FETCHING DOCUMENT: {blob_path} from GCS ---")

        # Download the file's content as a string.
        content = blob.download_as_text()
        
        return content

    except NotFound:
        error_message = f"ERROR: Document '{file_name}' not found in the knowledge base."
        print(error_message)
        return error_message
    
    except Exception as e:
        error_message = f"An unexpected error occurred while fetching document '{file_name}': {e}"
        print(error_message)
        return error_message