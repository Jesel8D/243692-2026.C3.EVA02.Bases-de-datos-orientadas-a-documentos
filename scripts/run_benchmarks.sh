#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
(( $# >= 1 )) || { printf 'Select plan, run or consolidate explicitly; nothing starts by default.\n' >&2; exit 2; }
case "$1" in plan|consolidate|--help|-h) exec "${BENCHMARK_PYTHON:-python3}" "$ROOT/benchmark_runner" "$@";; run) ;; *) printf 'Invalid action\n' >&2;exit 2;; esac
source "$ROOT/scripts/common.sh"
[[ "$(uname -s)" == Linux ]] || die 'Linux required'
load_config;select_profile;require_credentials;require_docker
export DATA_DATABASE_NAME="$POSTGRES_DB"
DATA_MONGO_CONTAINER="$(dc ps -a -q mongodb)";export DATA_MONGO_CONTAINER
DATA_PG_CONTAINER="$(dc ps -a -q postgres)";export DATA_PG_CONTAINER
exec "${BENCHMARK_PYTHON:-python3}" "$ROOT/benchmark_runner" "$@"
