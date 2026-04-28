#!/usr/bin/env bash
# Deploy IVIVE: FastAPI backend -> Cloud Run, static frontend -> Firebase Hosting.
#
# Prerequisites (one-time):
#   1. brew install --cask google-cloud-sdk           # or use the official installer
#   2. npm install -g firebase-tools
#   3. gcloud auth login && gcloud auth application-default login
#   4. firebase login
#   5. gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
#        artifactregistry.googleapis.com --project=ivive-2273c
#
# Usage:
#   ./deploy.sh              # deploy backend + hosting
#   ./deploy.sh hosting      # deploy hosting only
#   ./deploy.sh backend      # deploy backend (Cloud Run) only

set -euo pipefail

PROJECT_ID="ivive-2273c"
SERVICE_ID="ivive-api"
REGION="us-central1"

deploy_backend() {
  echo ">>> Deploying FastAPI backend to Cloud Run ($SERVICE_ID @ $REGION)..."
  gcloud run deploy "$SERVICE_ID" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --source=. \
    --platform=managed \
    --allow-unauthenticated \
    --port=8080 \
    --memory=512Mi \
    --cpu=1 \
    --max-instances=5
  echo ">>> Backend deployed."
}

deploy_hosting() {
  echo ">>> Deploying static frontend to Firebase Hosting (project $PROJECT_ID)..."
  firebase deploy --only hosting --project "$PROJECT_ID"
  echo ">>> Hosting deployed."
}

target="${1:-all}"
case "$target" in
  backend)  deploy_backend ;;
  hosting)  deploy_hosting ;;
  all)      deploy_backend && deploy_hosting ;;
  *)        echo "Unknown target: $target. Use 'backend', 'hosting', or 'all'." >&2; exit 1 ;;
esac

echo ""
echo "Done. Live URL: https://${PROJECT_ID}.web.app"
