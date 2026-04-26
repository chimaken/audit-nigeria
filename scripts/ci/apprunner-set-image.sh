#!/usr/bin/env bash
# Point the App Runner service at a new ECR image tag (same repo URI as in Terraform).
# Env: APPRUNNER_SERVICE_ARN (optional — if unset, exits 0), ECR_REPOSITORY_URI, IMAGE_TAG
set -euo pipefail

if [ -z "${APPRUNNER_SERVICE_ARN:-}" ]; then
  echo "APPRUNNER_SERVICE_ARN not set — skip App Runner update (add repo secret to enable roll on push)."
  exit 0
fi

: "${ECR_REPOSITORY_URI:?Set ECR_REPOSITORY_URI (no :tag) same as GitHub secret}"
: "${IMAGE_TAG:?Set IMAGE_TAG (e.g. github.sha)}"

NEW_IMAGE="${ECR_REPOSITORY_URI}:${IMAGE_TAG}"
echo "Updating App Runner to image: ${NEW_IMAGE}"

CFG="$(aws apprunner describe-service --service-arn "$APPRUNNER_SERVICE_ARN" --query "Service.SourceConfiguration" --output json)"
UPDATED="$(echo "$CFG" | jq --arg img "$NEW_IMAGE" '.ImageRepository.ImageIdentifier = $img')"
aws apprunner update-service --service-arn "$APPRUNNER_SERVICE_ARN" --source-configuration "$UPDATED" --no-cli-pager
echo "App Runner update started."
