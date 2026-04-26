#!/bin/sh
set -e
# One-time / rare: set RUN_DB_SEED=1 on the service (e.g. via Terraform) so geography seed runs
# before uvicorn. Seed is idempotent. Turn RUN_DB_SEED off after the first successful deploy.
if [ -n "${RUN_DB_SEED:-}" ] && [ "${RUN_DB_SEED}" != "0" ]; then
  echo "docker-entrypoint: RUN_DB_SEED is set — running python -m app.db.seed"
  python -m app.db.seed
fi
# Allow: docker compose run --entrypoint '' api python -m app.db.seed  OR  --entrypoint python api -m app.db.seed
if [ "$#" -gt 0 ]; then
  exec "$@"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
