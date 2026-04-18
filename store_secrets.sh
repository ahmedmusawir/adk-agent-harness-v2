#!/bin/bash
set -e

# --- Configuration ---
PROJECT_ID="ninth-potion-455712-g9"
ENV_FILE=".env"

# List of variables from your .env file to store as secrets
# Format: "VARIABLE_IN_DOTENV/SECRET_NAME_IN_GCP"
SECRETS_MAP=(
  "SUPABASE_DB_URI/adk-db-uri"
  "GHL_API_TOKEN/ghl-api-key"
  "GHL_LOCATION_ID/ghl-location-id"
)

echo "🔐 Storing secrets in Google Secret Manager for project: $PROJECT_ID"
echo "--------------------------------------------------"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: $ENV_FILE not found!"
    exit 1
fi

for mapping in "${SECRETS_MAP[@]}"; do
  # Split the mapping into the .env variable name and the GCP secret name
  ENV_VAR_NAME="${mapping%%/*}"
  SECRET_NAME="${mapping##*/}"

  # Extract the value from the .env file, ignoring commented lines
  VALUE=$(grep -v '^#' "$ENV_FILE" | grep "$ENV_VAR_NAME" | cut -d '=' -f2-)

  if [ -z "$VALUE" ]; then
    echo "⚠️ Warning: Variable '$ENV_VAR_NAME' not found in $ENV_FILE. Skipping."
    continue
  fi

  echo "Storing '$ENV_VAR_NAME' as secret '$SECRET_NAME'..."

  # Check if the secret exists, create it if it doesn't
  if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
    echo "  -> Secret '$SECRET_NAME' does not exist. Creating it now..."
    gcloud secrets create "$SECRET_NAME" --replication-policy="automatic" --project="$PROJECT_ID"
  fi

  # Add the new value as the latest version of the secret
  echo -n "$VALUE" | gcloud secrets versions add "$SECRET_NAME" --data-file=- --project="$PROJECT_ID"
  echo "  -> ✅ Success."
done

echo "--------------------------------------------------"
echo "All secrets have been stored successfully."