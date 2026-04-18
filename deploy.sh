#!/bin/bash
set -e

# --- Configuration ---
SERVICE_NAME="adk-bundle-prod-v2"
REGION="us-east1"
PROJECT_ID="ninth-potion-455712-g9"
GCS_BUCKET_NAME="your-agent-instructions-bucket-name" 
SERVICE_ACCOUNT_EMAIL="stark-vertex-ai@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🚀 Deploying service: $SERVICE_NAME with explicit Vertex AI config..."

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --allow-unauthenticated \
  --service-account="$SERVICE_ACCOUNT_EMAIL" \
  --set-secrets="DB_URI=adk-db-uri:latest,GHL_API_TOKEN=ghl-api-key:latest,GHL_LOCATION_ID=ghl-location-id:latest" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GCS_BUCKET_NAME=${GCS_BUCKET_NAME},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE"

echo "--------------------------------------------------"
echo "✅ Deployment complete!"
echo "📡 Service URL:"
gcloud run services describe "$SERVICE_NAME" --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)"