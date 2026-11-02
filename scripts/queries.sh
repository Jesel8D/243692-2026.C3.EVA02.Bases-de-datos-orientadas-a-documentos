#!/usr/bin/env bash
set -euo pipefail
# If prerequisite setup fails before Python takes over, emit a machine-readable block.
trap 'rc=$?; if (( rc != 0 )); then printf "{\"status\":\"BLOCKED\",\"field\":\"configuration/containers\",\"possible_cause\":\"See prerequisite diagnostic on stderr; no query was rewritten\"}\n"; exit 2; fi' EXIT
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# >= 1 )) || die 'Uso: queries.sh run|validate|explain|indexes --engine mongo|postgres|both [opciones]'
for arg in "$@"; do
  if [[ "$arg" == --help || "$arg" == -h ]]; then exec python3 "$PROJECT_ROOT/query_tool.py" --help; fi
done
engine=both
args=("$@")
for ((i=0;i<${#args[@]};i++)); do
  if [[ "${args[i]}" == --engine ]]; then
    (( i+1 < ${#args[@]} )) || die 'Falta --engine'
    engine="${args[i+1]}"
  elif [[ "${args[i]}" == --engine=* ]]; then engine="${args[i]#--engine=}"; fi
done
case "$engine" in mongo|postgres|both) ;; *) die 'Engine inválido';; esac
load_config; select_profile; require_credentials; require_docker
export DATA_DATABASE_NAME="$POSTGRES_DB"
if [[ "$engine" == mongo || "$engine" == both ]]; then
  DATA_MONGO_CONTAINER="$(dc ps -q mongodb)"; export DATA_MONGO_CONTAINER
  [[ -n "$DATA_MONGO_CONTAINER" ]] || die 'MongoDB no está ejecutándose'
fi
if [[ "$engine" == postgres || "$engine" == both ]]; then
  DATA_PG_CONTAINER="$(dc ps -q postgres)"; export DATA_PG_CONTAINER
  [[ -n "$DATA_PG_CONTAINER" ]] || die 'PostgreSQL no está ejecutándose'
fi
exec python3 "$PROJECT_ROOT/query_tool.py" "$@"
