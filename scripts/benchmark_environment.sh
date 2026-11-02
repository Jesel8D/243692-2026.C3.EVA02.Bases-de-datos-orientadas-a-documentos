#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# == 3 )) || die 'Internal interface: activate|isolate|verify|snapshot profile engine'
action="$1";profile="$2";engine="$3"
load_config;select_profile "$profile";require_credentials;require_docker
case "$engine" in mongo) service=mongodb;other=postgres;; postgres) service=postgres;other=mongodb;; *) die 'Invalid engine';; esac
case "$action" in
 activate)
  "$PROJECT_ROOT/scripts/start_services.sh" "$profile" >&2
  "$PROJECT_ROOT/scripts/verify_resources.sh" "$profile" >&2
  ;;
 isolate) dc stop --timeout 60 "$other" >&2 ;;
 verify) "$PROJECT_ROOT/scripts/verify_resources.sh" "$profile" >&2 ;;
 snapshot)
  cid="$(dc ps -q "$service")";[[ -n "$cid" ]] || die 'Selected engine unavailable'
  # No inspect.Env output. Credentials are never included in the snapshot.
  inspected="$(dk inspect --format '{"id":{{json .Id}},"image":{{json .Config.Image}},"image_id":{{json .Image}},"pid":{{.State.Pid}},"running":{{.State.Running}},"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}"none"{{end}},"quota":{{.HostConfig.CpuQuota}},"period":{{.HostConfig.CpuPeriod}},"memory":{{.HostConfig.Memory}},"swap":{{.HostConfig.MemorySwap}},"swappiness":{{json .HostConfig.MemorySwappiness}},"label":{{json (index .Config.Labels "academic.profile")}},"networks":{{json .NetworkSettings.Networks}},"oom_killed":{{.State.OOMKilled}}}' "$cid")"
  cpu="$(dk exec "$cid" cat /sys/fs/cgroup/cpu.max)"
  memory="$(dk exec "$cid" cat /sys/fs/cgroup/memory.max)"
  swap="$(dk exec "$cid" cat /sys/fs/cgroup/memory.swap.max)"
  printf '%s\n%s\n%s\n%s\n' "$inspected" "$cpu" "$memory" "$swap" | python3 -c 'import json,sys; d=json.loads(sys.stdin.readline());d["cpu_max"]=sys.stdin.readline().strip();d["memory_max"]=sys.stdin.readline().strip();d["swap_max"]=sys.stdin.readline().strip();d["networks"]={k:{"IPAddress":v["IPAddress"]} for k,v in d["networks"].items()};print(json.dumps(d))'
  ;;
 *) die 'Invalid environment action';;
esac
