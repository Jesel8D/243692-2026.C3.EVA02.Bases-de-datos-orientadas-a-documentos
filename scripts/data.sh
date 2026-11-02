#!/usr/bin/env bash
# Phase 2 operations inside existing containers; reuses Phase 1 configuration.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# >= 1 )) || die 'Uso: data.sh import-mongo|import-postgres|counts|compare [opciones]'
operation="$1"; shift
case "$operation" in import-mongo|import-postgres|counts|compare) ;; *) die 'Operación de datos inválida';; esac
# Help requires neither credentials nor Docker.
for arg in "$@"; do
  if [[ "$arg" == --help || "$arg" == -h ]]; then exec python3 "$PROJECT_ROOT/dataset_tool.py" "$operation" --help; fi
done
load_config; select_profile; require_credentials; require_docker
engine=both
if [[ "$operation" == import-mongo ]]; then engine=mongo; fi
if [[ "$operation" == import-postgres ]]; then engine=postgres; fi
# Only determine which containers must exist. Python validates the full interface.
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ "${args[i]}" == --engine ]]; then
    (( i+1 < ${#args[@]} )) || die 'Falta valor --engine'
    [[ "$operation" == counts || "$operation" == compare ]] || die '--engine solo para counts/compare'
    engine="${args[i+1]}"
  elif [[ "${args[i]}" == --engine=* ]]; then
    [[ "$operation" == counts || "$operation" == compare ]] || die '--engine solo para counts/compare'
    engine="${args[i]#--engine=}"
  fi
done
case "$engine" in mongo|postgres|both) ;; *) die '--engine debe ser mongo, postgres o both';; esac
export DATA_DATABASE_NAME="$POSTGRES_DB"
if [[ "$engine" == mongo || "$engine" == both ]]; then
  DATA_MONGO_CONTAINER="$(dc ps -q mongodb)"
  [[ -n "$DATA_MONGO_CONTAINER" ]] || die 'MongoDB no está ejecutándose; no se inicia automáticamente'
  export DATA_MONGO_CONTAINER
fi
if [[ "$engine" == postgres || "$engine" == both ]]; then
  DATA_PG_CONTAINER="$(dc ps -q postgres)"
  [[ -n "$DATA_PG_CONTAINER" ]] || die 'PostgreSQL no está ejecutándose; no se inicia automáticamente'
  export DATA_PG_CONTAINER
fi
# Databases authenticate with their own container initialization environment.
# Never forward passwords on argv or include them in reports.
exec python3 "$PROJECT_ROOT/dataset_tool.py" "$operation" "$@"
