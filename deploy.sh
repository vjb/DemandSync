#!/bin/bash
set -e

PROJECT_ID="622472185650"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/demandsync-agent"

echo "Building Docker image..."
docker build -t $IMAGE_NAME .

echo "Pushing to Artifact Registry..."
docker push $IMAGE_NAME

echo "Deploying to Cloud Run..."
gcloud run deploy demandsync-agent \
  --image $IMAGE_NAME \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=622472185650,DATA_STORE_ID=demandsync-policy-store,DATA_STORE_LOCATION=global" \
  --update-secrets="GEMINI_API_KEY=GEMINI_API_KEY_SECRET:latest,MONGO_URI=MONGO_URI_SECRET:latest"

echo "Deployment complete."
