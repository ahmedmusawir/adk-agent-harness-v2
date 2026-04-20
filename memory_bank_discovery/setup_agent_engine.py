"""One-time setup: creates a Vertex AI Agent Engine instance for Memory Bank discovery."""

from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"


def main() -> None:
    load_dotenv(Path(__file__).parent / ".env")

    print(f"Creating Agent Engine in project={PROJECT_ID}, location={LOCATION} ...")

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    try:
        agent_engine = client.agent_engines.create()
    except Exception as e:
        print(f"ERROR: Agent Engine creation failed: {type(e).__name__}: {e}")
        raise

    print("Agent Engine created!")
    # AgentEngine wraps a ReasoningEngine at .api_resource; the resource name lives there, not on the wrapper.
    resource_name = agent_engine.api_resource.name
    print(f"Resource name: {resource_name}")
    print(f"\u2192 Paste into .env: AGENT_ENGINE_ID={resource_name}")


if __name__ == "__main__":
    main()
