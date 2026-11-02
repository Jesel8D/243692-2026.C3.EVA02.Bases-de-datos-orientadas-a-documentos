#!/usr/bin/env bash
# Explicit integration test: creates a NEW project with tiny persistence markers.
# Leaves stopped containers/volumes, never deletes existing database contents.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ "${1:-}" == --run && $# == 1 ]] || { printf 'Uso: tests/test_containers.sh --run (crea proyecto aislado; acepta adaptación sin swap para pruebas)\n' >&2; exit 1; }
source "$ROOT/scripts/common.sh"
require_docker
TEST_DIR="$(mktemp -d)"
export ENV_FILE="$TEST_DIR/config.env"
# Random credentials stay in private temporary storage and never in reports/ZIP.
cp "$ROOT/.env.example" "$ENV_FILE"
project="jsonbenchtest$(date +%s)${RANDOM}"
secret="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
sed -i "s/^PROJECT_NAME=.*/PROJECT_NAME=$project/;s/^MONGO_PASSWORD=$/MONGO_PASSWORD=$secret/;s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$secret/;s/^ACCEPT_NO_SWAP_ADAPTATION=.*/ACCEPT_NO_SWAP_ADAPTATION=true/;s/^RESOURCE_PROFILE=.*/RESOURCE_PROFILE=severe/" "$ENV_FILE"
unset secret
load_config; select_profile severe; require_credentials
[[ -z "$(dk ps -a -q --filter "label=com.docker.compose.project=$project")" ]] || die 'El proyecto ya existe; no se usa'
cleanup() {
  # Only stop this test project. Do not remove any containers, networks or volumes.
  dc stop --timeout 60 mongodb postgres >/dev/null 2>&1 || true
  rm -f -- "$ENV_FILE"
  rmdir -- "$TEST_DIR"
}
trap cleanup EXIT
note "Proyecto aislado de prueba: $project (volúmenes se conservan)"
"$ROOT/scripts/start_services.sh" severe
"$ROOT/scripts/healthcheck.sh"
# Check JSONB functionality without creating orders, dataset or Q1/Q2.
dc exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' <<'SQL'
CREATE TABLE infra_persistence_probe (id integer PRIMARY KEY, payload jsonb NOT NULL);
INSERT INTO infra_persistence_probe VALUES (1, '{"marker":"phase1"}');
SQL
dc exec -T mongodb mongosh --quiet --eval 'const c=new Mongo("mongodb://127.0.0.1:27017");if(!c.getDB("admin").auth(process.env.MONGO_INITDB_ROOT_USERNAME,process.env.MONGO_INITDB_ROOT_PASSWORD))quit(1);const d=c.getDB("infra_probe");d.marker.insertOne({_id:"phase1",ok:true});'
"$ROOT/scripts/stop_services.sh"
dc up -d --force-recreate --wait --wait-timeout "$HEALTH_TIMEOUT_SECONDS"
"$ROOT/scripts/healthcheck.sh"
dc exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tAc "SELECT payload->> '\''marker'\'' FROM infra_persistence_probe WHERE id=1"' | grep -qx phase1
dc exec -T mongodb mongosh --quiet --eval 'const c=new Mongo("mongodb://127.0.0.1:27017");if(!c.getDB("admin").auth(process.env.MONGO_INITDB_ROOT_USERNAME,process.env.MONGO_INITDB_ROOT_PASSWORD))quit(1);if(c.getDB("infra_probe").marker.countDocuments({_id:"phase1",ok:true})!==1)quit(1);'
note 'PASS healthchecks autenticados, JSONB y persistencia tras recrear contenedores'
"$ROOT/scripts/verify_resources.sh" severe
note 'PASS recursos efectivos severe (sujeto a jerarquía y entorno observado)'
