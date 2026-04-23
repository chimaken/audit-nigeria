#!/usr/bin/env bash
# Initialize Terraform (from repo root or any cwd).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/infra/terraform"
terraform init "$@"
