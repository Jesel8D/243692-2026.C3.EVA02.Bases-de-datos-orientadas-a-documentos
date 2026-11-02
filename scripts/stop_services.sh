#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# == 0 )) || die 'Uso: stop_services.sh'
load_config; select_profile; require_docker
# No down: keep containers, network and all volumes. Safe to repeat.
dc stop --timeout 60 mongodb postgres
note 'Servicios detenidos; datos y contenedores conservados.'
