#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# == 0 )) || die 'Uso: healthcheck.sh'
load_config; select_profile; require_credentials; require_docker
failed=0
for service in mongodb postgres; do
  cid="$(dc ps -a -q "$service")"
  if [[ -z "$cid" ]]; then note "FAIL $service: no existe"; failed=1; continue; fi
  state="$(dk inspect --format '{{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}' "$cid")"
  note "$service: $state"
  if [[ "$state" != 'running health=healthy '* ]]; then failed=1; fi
  if [[ "$service" == mongodb ]]; then
    if ! dc exec -T mongodb mongosh --quiet --eval 'const c=new Mongo("mongodb://127.0.0.1:27017");const a=c.getDB("admin");if(!a.auth(process.env.MONGO_INITDB_ROOT_USERNAME,process.env.MONGO_INITDB_ROOT_PASSWORD))quit(1);if(a.runCommand({ping:1}).ok!==1)quit(1);' >/dev/null; then failed=1; note 'FAIL MongoDB: ping autenticado'; fi
  else
    if ! dc exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tAc "SELECT 1"' | grep -qx 1; then failed=1; note 'FAIL PostgreSQL: SELECT 1 autenticado'; fi
  fi
  if (( failed )); then note "Diagnóstico local (puede contener datos): docker compose logs --tail 50 $service. No publique logs sin revisar."; fi
 done
(( failed == 0 )) || exit 1
note 'OK: contenedores saludables y conectividad autenticada local dentro de cada contenedor.'
