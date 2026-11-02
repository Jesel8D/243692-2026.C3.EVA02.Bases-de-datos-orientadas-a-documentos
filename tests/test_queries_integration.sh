#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ "${1:-}" == --run && $# -le 2 ]] || { printf 'Uso: test_queries_integration.sh --run [both|postgres|mongo]\n' >&2; exit 1; }
source "$ROOT/scripts/common.sh"
load_config; select_profile; require_credentials; require_docker
engine="${2:-both}"
case "$engine" in mongo|postgres|both) ;; *) die 'Engine inválido';; esac
export DATA_DATABASE_NAME="$POSTGRES_DB" DATA_TEST_ENGINE="$engine" RUN_QUERY_INTEGRATION=1
if [[ "$engine" == mongo || "$engine" == both ]]; then
  DATA_MONGO_CONTAINER="$(dc ps -q mongodb)"; export DATA_MONGO_CONTAINER
  [[ -n "$DATA_MONGO_CONTAINER" ]] || die 'MongoDB debe estar ejecutándose'
fi
if [[ "$engine" == postgres || "$engine" == both ]]; then
  DATA_PG_CONTAINER="$(dc ps -q postgres)"; export DATA_PG_CONTAINER
  [[ -n "$DATA_PG_CONTAINER" ]] || die 'PostgreSQL debe estar ejecutándose'
fi
cd "$ROOT"
exec python3 -m unittest discover -s tests -p test_queries_integration.py -v
