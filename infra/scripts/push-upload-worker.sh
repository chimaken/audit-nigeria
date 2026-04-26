#!/usr/bin/env bash
# Build backend/Dockerfile.lambda and push to ECR.
# Usage (from repo root):
#   cd infra/terraform && ../scripts/push-upload-worker.sh "$(terraform output -raw upload_worker_ecr_url)" manual-1 eu-west-1
set -euo pipefail
repo_url="${1:?usage: $0 <ecr-repo-url-no-tag> [tag] [region]}"
tag="${2:-latest}"
region="${3:-eu-west-1}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
registry="${repo_url%%/*}"
remote="${repo_url}:${tag}"
cd "$root"
# Lambda rejects BuildKit manifest lists / attestations; force single linux/amd64 image.
docker build --platform linux/amd64 --provenance=false --sbom=false \
  -f backend/Dockerfile.lambda -t upload-worker:local .
aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "$registry"
docker tag upload-worker:local "$remote"
docker push "$remote"
echo "Pushed $remote"
