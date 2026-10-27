#!/usr/bin/env bash
# Rebuild and redeploy the intranet compose stack (project almrag-intranet).
# Usage: tools/deploy_intranet.sh [-w|--with-worker] [-y|--yes] [-n|--dry-run]
#   default: api + frontend only (worker and qdrant are left untouched).
#   -w: also recreate the worker; refused while a job is RUNNING unless -y is given.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ALMRAG_ENV_FILE:-$ROOT/.env.intranet}"
PROJECT="almrag-intranet"
WORKER_CONTAINER="${PROJECT}-worker-1"
SERVICES=(api frontend)
WITH_WORKER=0 YES=0 DRY=0

for arg in "$@"; do
  case "$arg" in
    -w|--with-worker) WITH_WORKER=1 ;;
    -y|--yes) YES=1 ;;
    -n|--dry-run) DRY=1 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

[[ -f "$ENV_FILE" ]] || { echo "missing env file: $ENV_FILE" >&2; exit 1; }
COMPOSE=(docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$ROOT/deploy/compose.intranet.yaml")
run() { echo "+ $*"; [[ $DRY -eq 1 ]] || "$@"; }

if [[ $WITH_WORKER -eq 1 ]]; then
  SERVICES+=(worker)
  running=$(docker exec -i "$WORKER_CONTAINER" python - <<'EOF' 2>/dev/null || echo unknown
import sqlite3
c = sqlite3.connect('file:/app/data/alm.sqlite?mode=ro', uri=True)
print(c.execute("select count(*) from jobs where state='RUNNING'").fetchone()[0])
EOF
)
  if [[ "$running" != "0" && $YES -ne 1 ]]; then
    echo "RUNNING jobs: $running. Recreating the worker interrupts them; rerun with -y to proceed." >&2
    exit 1
  fi
fi

run "${COMPOSE[@]}" build "${SERVICES[@]}"
run "${COMPOSE[@]}" up -d --no-deps "${SERVICES[@]}"
[[ $DRY -eq 1 ]] || { sleep 10; "${COMPOSE[@]}" ps; }
