#!/usr/bin/env bash
# Build backend/Dockerfile and push to App Runner ECR.
# Usage:
#   cd infra/terraform && ../scripts/push-api.sh "$(terraform output -raw ecr_repository_url)" manual-1 eu-west-1
set -euo pipefail
repo_url="${1:?usage: $0 <ecr-repo-url-no-tag> [tag] [region]}"
tag="${2:-latest}"
region="${3:-eu-west-1}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
registry="${repo_url%%/*}"
remote="${repo_url}:${tag}"
cd "$root"
docker build --platform linux/amd64 --provenance=false --sbom=false \
  -f backend/Dockerfile -t audit-nigeria-api:local .
aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "$registry"
docker tag audit-nigeria-api:local "$remote"
docker push "$remote"
echo "Pushed $remote"
echo "If auto_deployments_enabled is false, bump apprunner_image_tag and terraform apply or deploy from App Runner console."
