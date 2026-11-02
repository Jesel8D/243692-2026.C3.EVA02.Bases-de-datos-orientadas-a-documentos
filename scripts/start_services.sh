#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# <= 1 )) || die 'Uso: start_services.sh [baseline|medium|severe]'
load_config; select_profile "${1:-$RESOURCE_PROFILE}"; require_credentials; require_docker
[[ "$(dk info --format '{{.CgroupVersion}}')" == 2 ]] || die 'Se requiere Docker con cgroups v2.'
[[ "$ACCEPT_NO_SWAP_ADAPTATION" == true ]] || die 'Lea docs/09 y acepte explícitamente ACCEPT_NO_SWAP_ADAPTATION=true; no se afirma equivalencia literal con swappiness.'
note "Inicio $PROFILE_ID: $PROFILE_CPUS CPU, ${PROFILE_MEMORY_MB}m; adaptación sin swap aceptada. Volúmenes conservados."
dc config --quiet
if ! dc up -d --wait --wait-timeout "$HEALTH_TIMEOUT_SECONDS"; then
  note 'Arranque fallido; no se borran contenedores ni volúmenes. Ejecute healthcheck.sh y revise logs localmente.' >&2
  exit 1
fi
# Resource verification remains explicit: a healthy database does not prove resource equivalence.
note 'Salud inicial OK. Ejecute verify_resources.sh con el mismo perfil para comprobar límites efectivos.'
