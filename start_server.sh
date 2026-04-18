#!/bin/bash

# Load environment variables from the .env file
if [ -f .env ]; then
  source .env
else
  echo "Error: .env file not found. Please create one with your SUPABASE_DB_URI."
  exit 1
fi

# Start ADK server with the Supabase URI from the environment variable
echo "Starting ADK server with Supabase session memory..."
adk api_server . \
  --host=0.0.0.0 \
  --port=8000 \
  --session_service_uri="$SUPABASE_DB_URI"