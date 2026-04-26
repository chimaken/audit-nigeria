#!/usr/bin/env bash
# Single entry: infra (terraform), API image (ECR), and/or static frontend.
# Usage:
#   ./scripts/deploy/deploy.sh --mode infra|backend|frontend|app [options]
# Modes:
#   infra    — terraform init + apply (needs infra/terraform/terraform.tfvars)
#   backend  — docker build/push; optional --apply-terraform
#   frontend — npm build:static + terraform apply
#   app      — backend then frontend (default)
# Options:
#   --apply-terraform          set apprunner_image_tag after push (backend/app)
#   --skip-push                build only (backend/app)
#   --skip-frontend-terraform  build out/ only (frontend/app)
#   --infra-init-only          with infra: init only
#   --tag TAG                  image tag (default: short git SHA)
#   --api-url URL              NEXT_PUBLIC_API_URL for frontend
#   -h, --help

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/infra/terraform"
TFVARS="$TF_DIR/terraform.tfvars"
FRONTEND="$REPO_ROOT/frontend"

MODE="app"
APPLY_TF=0
SKIP_PUSH=0
SKIP_FE_TF=0
INFRA_INIT_ONLY=0
TAG_ARG=""
API_URL=""

usage() {
  sed -n '1,25p' "$0" | tail -n +2
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --mode)
      MODE=$(echo "$2" | tr '[:upper:]' '[:lower:]')
      shift 2
      ;;
    --apply-terraform) APPLY_TF=1; shift ;;
    --skip-push) SKIP_PUSH=1; shift ;;
    --skip-frontend-terraform) SKIP_FE_TF=1; shift ;;
    --infra-init-only) INFRA_INIT_ONLY=1; shift ;;
    --tag) TAG_ARG="$2"; shift 2 ;;
    --api-url) API_URL="$2"; shift 2 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 1 ;;
  esac
done

case "$MODE" in
  infra|backend|frontend|app) ;;
  *) echo "Invalid --mode (use infra, backend, frontend, app)" >&2; exit 1 ;;
esac

run_infra() {
  if [[ ! -f "$TFVARS" ]]; then
    echo "Missing $TFVARS — copy terraform.tfvars.example and edit." >&2
    exit 1
  fi
  echo "terraform init ..."
  terraform -chdir="$TF_DIR" init
  if [[ "$INFRA_INIT_ONLY" -eq 1 ]]; then
    echo "Infra init only: apply when ready."
    return
  fi
  echo "terraform apply -auto-approve ..."
  terraform -chdir="$TF_DIR" apply -auto-approve
  echo "Infra apply finished."
}

run_backend() {
  if [[ -z "$TAG_ARG" ]]; then
    TAG_ARG="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo "manual-$(date +%Y%m%d%H%M%S)")"
  fi
  ECR_URI="${ECR_REPOSITORY_URI:-}"
  if [[ -z "$ECR_URI" ]]; then
    ECR_URI="$(terraform -chdir="$TF_DIR" output -raw ecr_repository_url)"
  fi
  REGISTRY="${ECR_URI%%/*}"
  # get-login-password must match the repository region; wrong AWS_REGION → Docker 400 on login.
  if [[ "$REGISTRY" =~ \.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com$ ]]; then
    REGION="${BASH_REMATCH[1]}"
  else
    REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-eu-west-1}}"
  fi

  echo "Building ${ECR_URI}:${TAG_ARG} ..."
  docker build -f "$REPO_ROOT/backend/Dockerfile" -t "${ECR_URI}:${TAG_ARG}" "$REPO_ROOT"

  if [[ "$SKIP_PUSH" -eq 0 ]]; then
    aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
    docker push "${ECR_URI}:${TAG_ARG}"
    echo "Pushed OK."
  fi

  if [[ "$APPLY_TF" -eq 1 ]]; then
    terraform -chdir="$TF_DIR" apply -auto-approve -var "apprunner_image_tag=$TAG_ARG"
    echo "Terraform apply (App Runner tag) finished."
  else
    echo "Tip: $0 --mode backend --tag $TAG_ARG --apply-terraform"
  fi
}

run_frontend() {
  if [[ -z "$API_URL" ]]; then
    API_URL="$(terraform -chdir="$TF_DIR" output -raw apprunner_public_url 2>/dev/null || true)"
  fi
  API_URL="${API_URL%/}"
  if [[ -z "$API_URL" || "$API_URL" == "null" ]]; then
    echo "Set --api-url or enable App Runner for apprunner_public_url." >&2
    exit 1
  fi

  echo "Building static frontend (NEXT_PUBLIC_API_URL=$API_URL) ..."
  export STATIC_EXPORT=1
  export NEXT_PUBLIC_API_URL="$API_URL"
  ( cd "$FRONTEND" && npm run build:static )

  if [[ ! -f "$FRONTEND/out/index.html" ]]; then
    echo "Missing frontend/out/index.html after build." >&2
    exit 1
  fi

  if [[ "$SKIP_FE_TF" -eq 0 ]]; then
    terraform -chdir="$TF_DIR" apply -auto-approve
    echo "Frontend deploy finished."
  else
    echo "Skip terraform: run terraform -chdir=$TF_DIR apply"
  fi
}

case "$MODE" in
  infra) run_infra ;;
  backend) run_backend ;;
  frontend) run_frontend ;;
  app)
    run_backend
    run_frontend
    ;;
esac

echo "deploy.sh --mode $MODE done."
