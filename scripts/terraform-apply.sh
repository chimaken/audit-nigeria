#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/infra/terraform"
if [[ -f tfplan ]]; then
  terraform apply tfplan "$@"
else
  terraform apply "$@"
fi
