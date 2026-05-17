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
  --set-env-vars="MONGO_URI=mongodb+srv://database_admin:8ppleS8uce21\!@cluster0.rdcyyj5.mongodb.net/?appName=Cluster0,GEMINI_API_KEY=AIzaSyDrFw3dFgUIlD0t1hWm8eYF4775CN4Qszk,GCP_PROJECT_ID=622472185650,DATA_STORE_ID=demandsync-policy-store,DATA_STORE_LOCATION=global"

echo "Deployment complete."
