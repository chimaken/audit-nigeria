#!/usr/bin/env bash
# Build backend image and push to ECR. Requires: AWS CLI auth, ECR_REPOSITORY_URI (no tag).
# Usage: ECR_REPOSITORY_URI=123....amazonaws.com/org/env/api ./scripts/docker-push-api.sh [extra-docker-tags]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URI="${ECR_REPOSITORY_URI:?Set ECR_REPOSITORY_URI to terraform output ecr_repository_url}"
TAG="${IMAGE_TAG:-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo latest)}"
IMAGE="${URI}:${TAG}"
REGISTRY="${URI%%/*}"
if [[ "$REGISTRY" =~ \.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com$ ]]; then
  AWS_ECR_REGION="${BASH_REMATCH[1]}"
else
  AWS_ECR_REGION="${AWS_REGION:-$(aws configure get region)}"
fi

echo "Building ${IMAGE}"
docker build -f "${ROOT}/backend/Dockerfile" -t "${IMAGE}" "${ROOT}"

echo "Logging in to ECR (aws ecr get-login-password, region ${AWS_ECR_REGION})"
aws ecr get-login-password --region "${AWS_ECR_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}"

docker push "${IMAGE}"
echo "Pushed ${IMAGE}"
