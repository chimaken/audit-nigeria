#!/usr/bin/env bash
# Build Next static export and sync to S3 + CloudFront invalidation.
# Env: FRONTEND_S3_BUCKET, CLOUDFRONT_DISTRIBUTION_ID, NEXT_PUBLIC_API_URL, REPO_ROOT (optional, default: cwd for GHA = workspace root)
set -euo pipefail

: "${FRONTEND_S3_BUCKET:?}"
: "${CLOUDFRONT_DISTRIBUTION_ID:?}"
: "${NEXT_PUBLIC_API_URL:?}"

ROOT="${REPO_ROOT:-${GITHUB_WORKSPACE:-}}"
if [ -z "$ROOT" ] || [ ! -d "$ROOT/frontend" ]; then
  ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi

export STATIC_EXPORT=1
export NEXT_PUBLIC_API_URL
cd "$ROOT/frontend"
npm ci
npm run build:static
aws s3 sync out/ "s3://${FRONTEND_S3_BUCKET}/" --delete
aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths "/*" --no-cli-pager
echo "Frontend deployed to s3://${FRONTEND_S3_BUCKET}/ and invalidation created."
