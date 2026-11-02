#!/usr/bin/env bash
# Shared functions only; never source a user-controlled .env as shell code.
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
note() { printf '%s\n' "$*"; }
dk() {
  env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY \
    -u DOCKER_CERT_PATH -u COMPOSE_FILE -u COMPOSE_PROFILES \
    docker --host=unix:///var/run/docker.sock "$@"
}
require_docker() {
  command -v docker >/dev/null || die 'Docker Engine CLI no disponible.'
  dk info >/dev/null || die 'Daemon local no accesible; no se inicia ni modifica automáticamente.'
  dk compose version >/dev/null || die 'Falta Docker Compose Plugin.'
}
load_config() {
  ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
  [[ -f "$ENV_FILE" ]] || die 'Falta .env; copie .env.example y configure credenciales locales.'
  local line key value
  unset PROJECT_NAME RESOURCE_PROFILE MONGO_IMAGE POSTGRES_IMAGE MONGO_USERNAME MONGO_PASSWORD POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB PUBLISH_PORTS MONGO_PORT POSTGRES_PORT HEALTH_TIMEOUT_SECONDS ACCEPT_NO_SWAP_ADAPTATION RESOURCE_CPUS RESOURCE_MEMORY_MB CPU_PERIOD_US
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" =~ ^([A-Z][A-Z0-9_]*)=(.*)$ ]] || die 'Formato .env inválido: use KEY=value sin comillas.'
    key="${BASH_REMATCH[1]}"; value="${BASH_REMATCH[2]}"
    case "$key" in
      PROJECT_NAME|RESOURCE_PROFILE|MONGO_IMAGE|POSTGRES_IMAGE|MONGO_USERNAME|MONGO_PASSWORD|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB|PUBLISH_PORTS|MONGO_PORT|POSTGRES_PORT|HEALTH_TIMEOUT_SECONDS|ACCEPT_NO_SWAP_ADAPTATION|RESOURCE_CPUS|RESOURCE_MEMORY_MB|CPU_PERIOD_US) ;;
      *) die "Variable .env no admitida: $key" ;;
    esac
    [[ "$value" =~ ^[a-zA-Z0-9_./:@%+=,!~-]*$ ]] || die "Valor .env incompatible en $key (sin espacios, comillas, # ni expansión)."
    # Explicit file is authoritative; avoids accidental inherited credential/resource overrides.
    export "$key=$value"
  done < "$ENV_FILE"
  : "${PROJECT_NAME:=jsonbench}" "${RESOURCE_PROFILE:=baseline}" "${CPU_PERIOD_US:=100000}"
  : "${MONGO_IMAGE:=mongo:9.0.4-resolute@sha256:714cc3db1e396e5a464b8443ccde50e53283368809401f53f1997b684ddb5be0}" "${POSTGRES_IMAGE:=postgres:18.6-bookworm@sha256:5c4783a8cc3f0074912164f94dfa1be4e043438f0f707cf968d7af9a0d31a2c8}"
  : "${PUBLISH_PORTS:=false}" "${MONGO_PORT:=27017}" "${POSTGRES_PORT:=5432}"
  : "${POSTGRES_DB:=jsonbench}" "${HEALTH_TIMEOUT_SECONDS:=240}"
  : "${RESOURCE_CPUS:=auto}" "${RESOURCE_MEMORY_MB:=auto}" "${ACCEPT_NO_SWAP_ADAPTATION:=false}"
  [[ "$PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die 'PROJECT_NAME inválido.'
  [[ "$MONGO_IMAGE" =~ ^mongo:[0-9]+\.[0-9]+\.[0-9]+-[a-z0-9.-]+(@sha256:[a-f0-9]{64})?$ ]] || die 'MONGO_IMAGE debe ser oficial, versión patch y variante explícitas.'
  [[ "$POSTGRES_IMAGE" =~ ^postgres:[0-9]+\.[0-9]+-[a-z0-9.-]+(@sha256:[a-f0-9]{64})?$ ]] || die 'POSTGRES_IMAGE debe ser oficial con patch y variante explícitas.'
  [[ "$PUBLISH_PORTS" == true || "$PUBLISH_PORTS" == false ]] || die 'PUBLISH_PORTS debe ser true/false.'
  [[ "$ACCEPT_NO_SWAP_ADAPTATION" == true || "$ACCEPT_NO_SWAP_ADAPTATION" == false ]] || die 'ACCEPT_NO_SWAP_ADAPTATION debe ser true/false.'
  [[ "$CPU_PERIOD_US" == 100000 ]] || die 'Periodo CPU debe ser 100000 us para estos perfiles.'
  for key in MONGO_PORT POSTGRES_PORT; do
    value="${!key}"
    [[ "$value" =~ ^[1-9][0-9]{0,4}$ ]] && (( 10#$value <= 65535 )) || die "Puerto inválido: $key"
  done
  [[ "$HEALTH_TIMEOUT_SECONDS" =~ ^[1-9][0-9]{0,3}$ ]] || die 'HEALTH_TIMEOUT_SECONDS inválido.'
  export PROJECT_NAME RESOURCE_PROFILE CPU_PERIOD_US MONGO_IMAGE POSTGRES_IMAGE POSTGRES_DB
  export PUBLISH_PORTS MONGO_PORT POSTGRES_PORT HEALTH_TIMEOUT_SECONDS ACCEPT_NO_SWAP_ADAPTATION
}
select_profile() {
  local selected="${1:-$RESOURCE_PROFILE}" expected_id cpus mem key value
  case "$selected" in
    baseline) expected_id=PROFILE_A_BASELINE; cpus=4; mem=4096 ;;
    medium) expected_id=PROFILE_B_MEDIUM; cpus=2; mem=2048 ;;
    severe) expected_id=PROFILE_C_SEVERE; cpus=1; mem=1024 ;;
    *) die 'Perfil inválido; use baseline, medium o severe.' ;;
  esac
  PROFILE_ID=''; PROFILE_CPUS=''; PROFILE_MEMORY_MB=''
  while IFS='=' read -r key value; do
    case "$key" in
      PROFILE_ID) PROFILE_ID="$value" ;;
      PROFILE_CPUS) PROFILE_CPUS="$value" ;;
      PROFILE_MEMORY_MB) PROFILE_MEMORY_MB="$value" ;;
      *) die 'Archivo de perfil inválido.' ;;
    esac
  done < "$PROJECT_ROOT/config/profiles/$selected.env"
  [[ "$PROFILE_ID" == "$expected_id" && "$PROFILE_CPUS" == "$cpus" && "$PROFILE_MEMORY_MB" == "$mem" ]] || die 'Perfil modificado fuera del manual.'
  [[ "$RESOURCE_CPUS" == auto || "$RESOURCE_CPUS" == "$cpus" ]] || die 'RESOURCE_CPUS no coincide con perfil oficial.'
  [[ "$RESOURCE_MEMORY_MB" == auto || "$RESOURCE_MEMORY_MB" == "$mem" ]] || die 'RESOURCE_MEMORY_MB no coincide con perfil oficial.'
  export PROFILE_ID PROFILE_CPUS PROFILE_MEMORY_MB
  export CPU_QUOTA_US=$((cpus * CPU_PERIOD_US)) MEMORY_BYTES=$((mem * 1024 * 1024))
  COMPOSE_ARGS=(--project-directory "$PROJECT_ROOT" --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$PROJECT_ROOT/docker-compose.yml")
  if [[ "$PUBLISH_PORTS" == true ]]; then COMPOSE_ARGS+=(-f "$PROJECT_ROOT/config/ports.local.yml"); fi
}
require_credentials() {
  local key value
  for key in MONGO_USERNAME MONGO_PASSWORD POSTGRES_USER POSTGRES_PASSWORD; do
    value="${!key:-}"; [[ -n "$value" ]] || die "Falta $key en configuración local."
  done
  [[ "$MONGO_USERNAME" =~ ^[a-zA-Z][a-zA-Z0-9_]*$ && "$POSTGRES_USER" =~ ^[a-zA-Z][a-zA-Z0-9_]*$ && "$POSTGRES_DB" =~ ^[a-zA-Z][a-zA-Z0-9_]*$ ]] || die 'Usuario/base: use identificadores alfanuméricos simples.'
}
dc() { dk compose "${COMPOSE_ARGS[@]}" "$@"; }
