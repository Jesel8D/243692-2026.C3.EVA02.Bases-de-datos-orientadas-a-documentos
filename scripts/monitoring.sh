#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/common.sh"
cd "$ROOT"
action="${1:-help}"; (( $# == 0 )) || shift
case "$action" in help|--help|-h) exec "${BENCHMARK_PYTHON:-python3}" -m observability.cli --help;; esac
settings_text="$(python3 -m observability.config)"
while IFS='=' read -r key value; do export "$key=$value"; done <<< "$settings_text"
require_docker
args=(-p "$MONITORING_PROJECT_NAME" -f "$ROOT/config/monitoring/compose.monitoring.yml")
case "$action" in
 config) dk compose "${args[@]}" config --quiet;;
 validate)
  dk compose "${args[@]}" config --quiet
  if [[ -n "${MONITORING_PROMTOOL:-}" ]]; then "$MONITORING_PROMTOOL" check config "$ROOT/config/monitoring/prometheus.yml"
  else dk compose "${args[@]}" run --no-deps --rm --entrypoint /bin/promtool prometheus check config /etc/prometheus/prometheus.yml; fi;;
 start)
  (( $# == 0 )) || die 'start accepts no arguments; configure .env.monitoring explicitly'
  [[ "$MONITORING_ACCEPT_HOST_ACCESS" == true ]] || die 'Read docs/13: rootfs/proc/sys and Docker socket access. Set MONITORING_ACCEPT_HOST_ACCESS=true explicitly; no privileged container is used.'
  [[ "$(dk info --format '{{.CgroupVersion}}')" == 2 ]] || die 'cgroups v2 required'
  [[ "$(dk info --format '{{.DockerRootDir}}')" == "$MONITORING_DOCKER_ROOT" ]] || die 'Configure MONITORING_DOCKER_ROOT to actual local Docker root'
  python3 -m observability.cli storage
  dk compose "${args[@]}" up -d --wait --wait-timeout 90
  exec "${BENCHMARK_PYTHON:-python3}" -m observability.cli health;;
 stop) (( $# == 0 )) || die 'stop takes no arguments'; dk compose "${args[@]}" stop --timeout 30 prometheus cadvisor node-exporter;;
 health|targets|query|diagnose|export|storage) exec "${BENCHMARK_PYTHON:-python3}" -m observability.cli "$action" "$@";;
 *) die 'Unknown monitoring command';;
esac
