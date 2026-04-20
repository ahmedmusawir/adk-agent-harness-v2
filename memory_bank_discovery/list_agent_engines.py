"""Lists existing Vertex AI Agent Engine instances in the project/location.

Use this to retrieve the resource name of an Agent Engine that was already created
(e.g., if setup_agent_engine.py failed after create() but before printing the name).
"""

from pathlib import Path

from dotenv import load_dotenv

import vertexai

PROJECT_ID = "ninth-potion-455712-g9"
LOCATION = "us-central1"


def main() -> None:
    load_dotenv(Path(__file__).parent / ".env")

    print(f"Listing Agent Engines in project={PROJECT_ID}, location={LOCATION} ...")

    client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

    engines = list(client.agent_engines.list())

    if not engines:
        print("No Agent Engines found.")
        return

    print(f"Found {len(engines)} Agent Engine(s):\n")
    for i, engine in enumerate(engines, start=1):
        resource = engine.api_resource
        print(f"[{i}] Resource name: {resource.name}")
        # display_name and create_time are useful for disambiguating duplicates.
        if getattr(resource, "display_name", None):
            print(f"    Display name:  {resource.display_name}")
        if getattr(resource, "create_time", None):
            print(f"    Created:       {resource.create_time}")
        print()


if __name__ == "__main__":
    main()
