#!/usr/bin/env bash
# Update the async upload worker Lambda to a new container image tag.
# Env: UPLOAD_WORKER_LAMBDA_ARN (or function name), UPLOAD_WORKER_ECR_URL (no :tag), IMAGE_TAG
set -euo pipefail

: "${IMAGE_TAG:?}"

if [ -z "${UPLOAD_WORKER_LAMBDA_ARN:-}" ] || [ -z "${UPLOAD_WORKER_ECR_URL:-}" ]; then
  echo "UPLOAD_WORKER_LAMBDA_ARN or UPLOAD_WORKER_ECR_URL not set — skip Lambda update."
  exit 0
fi

IMAGE_URI="${UPLOAD_WORKER_ECR_URL}:${IMAGE_TAG}"
echo "Updating Lambda ${UPLOAD_WORKER_LAMBDA_ARN} to ${IMAGE_URI}"
aws lambda update-function-code --function-name "$UPLOAD_WORKER_LAMBDA_ARN" --image-uri "$IMAGE_URI" --no-cli-pager
echo "Lambda update started."
