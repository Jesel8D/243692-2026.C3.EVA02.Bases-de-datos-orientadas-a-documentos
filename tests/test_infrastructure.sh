#!/usr/bin/env bash
# Static/config tests only: never creates containers or contacts a database.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
for script in "$ROOT"/scripts/*.sh "$ROOT"/tests/*.sh; do bash -n "$script"; done
printf 'PASS Bash syntax\n'
grep -q '^  mem_swappiness: 0$' "$ROOT/docker-compose.yml"
command -v docker >/dev/null || { printf 'SKIP Compose config: falta CLI\n'; exit 2; }
docker compose version >/dev/null || { printf 'SKIP Compose config: falta Plugin\n'; exit 2; }
TEST_DIR="$(mktemp -d)"
trap 'rm -f -- "$TEST_DIR/config.env" "$TEST_DIR/empty.env"; rmdir -- "$TEST_DIR"' EXIT
cp "$ROOT/.env.example" "$TEST_DIR/config.env"
# Non-secret fixtures for parsing only; not container credentials.
sed -i 's/^MONGO_PASSWORD=$/MONGO_PASSWORD=fixture_only/;s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=fixture_only/' "$TEST_DIR/config.env"
export ENV_FILE="$TEST_DIR/config.env"
source "$ROOT/scripts/common.sh"
load_config; require_credentials
for profile in baseline medium severe; do
  select_profile "$profile"
  dc config --quiet
  dc config --format json | python3 -c '
import json,sys,os
c=json.load(sys.stdin)
assert set(c["services"])=={"mongodb","postgres"}
for name,s in c["services"].items():
 assert s["cpu_quota"]==int(os.environ["CPU_QUOTA_US"])
 assert s["cpu_period"]==100000
 assert int(s["mem_limit"])==int(os.environ["MEMORY_BYTES"])
 assert int(s["memswap_limit"])==int(s["mem_limit"])
 assert s.get("mem_swappiness",0)==0
 assert s["labels"]["academic.profile"]==os.environ["PROFILE_ID"]
 assert "ports" not in s
 assert ":latest" not in s["image"] and "@sha256:" in s["image"]
 assert s["healthcheck"]["test"]
 assert not s.get("privileged",False)
assert c["networks"]["database"]["internal"]
assert len(c["volumes"])==3
'
  printf 'PASS Compose profile %s\n' "$profile"
done
expect_failure() { if ( "$@" ) >/dev/null 2>&1; then die 'Se aceptó configuración inválida'; fi; }
expect_failure select_profile unknown
RESOURCE_CPUS=3; expect_failure select_profile baseline; RESOURCE_CPUS=auto
RESOURCE_MEMORY_MB=512; expect_failure select_profile severe; RESOURCE_MEMORY_MB=auto
PUBLISH_PORTS=true; select_profile baseline
dc config --format json | python3 -c 'import json,sys; c=json.load(sys.stdin); assert all(p["host_ip"]=="127.0.0.1" for s in c["services"].values() for p in s["ports"])'
cp "$ROOT/.env.example" "$TEST_DIR/empty.env"
expect_failure env ENV_FILE="$TEST_DIR/empty.env" bash -c 'source "$1/scripts/common.sh"; load_config; require_credentials' _ "$ROOT"
printf 'MONGO_PASSWORD=$(touch /never_execute)\n' > "$TEST_DIR/empty.env"
expect_failure env ENV_FILE="$TEST_DIR/empty.env" bash -c 'source "$1/scripts/common.sh"; load_config' _ "$ROOT"
printf 'MONGO_IMAGE=mongo:latest\n' > "$TEST_DIR/empty.env"
expect_failure env ENV_FILE="$TEST_DIR/empty.env" bash -c 'source "$1/scripts/common.sh"; load_config' _ "$ROOT"
printf 'MONGO_PORT=99999\n' > "$TEST_DIR/empty.env"
expect_failure env ENV_FILE="$TEST_DIR/empty.env" bash -c 'source "$1/scripts/common.sh"; load_config' _ "$ROOT"
expect_failure env ENV_FILE="$TEST_DIR/config.env" bash "$ROOT/scripts/start_services.sh" severe extra
# Explicit start must not accept missing opt-in; all previous tests are daemon-independent.
if dk info >/dev/null 2>&1; then
  expect_failure env ENV_FILE="$TEST_DIR/config.env" bash "$ROOT/scripts/start_services.sh" severe
fi
# Verify opt-in gate independently of daemon availability.
[[ "$ACCEPT_NO_SWAP_ADAPTATION" == false ]] || die 'Fixture debe empezar sin aceptar adaptación'
printf 'PASS variables requeridas, perfiles inválidos, recursos incompatibles, puertos loopback, imagen flotante y .env no ejecutable\n'
