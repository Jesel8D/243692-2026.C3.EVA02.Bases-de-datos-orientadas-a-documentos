#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# <= 1 )) || die 'Uso: verify_resources.sh [baseline|medium|severe]'
load_config; select_profile "${1:-$RESOURCE_PROFILE}"; require_credentials; require_docker
[[ "$(dk info --format '{{.CgroupVersion}}')" == 2 ]] || die 'Verificador requiere cgroups v2.'
failed=0
compare() {
  if [[ "$2" == "$3" ]]; then note "OK $1: $3"; else note "FAIL $1: esperado=$2 observado=$3"; failed=1; fi
}
note "Esperado $PROFILE_ID quota=$CPU_QUOTA_US period=$CPU_PERIOD_US memory.max=$MEMORY_BYTES memory.swap.max=0"
dk info --format 'Docker={{.ServerVersion}} cgroups={{.CgroupVersion}} driver={{.CgroupDriver}}'
for service in mongodb postgres; do
  cid="$(dc ps -a -q "$service")"
  if [[ -z "$cid" ]]; then note "FAIL $service ausente"; failed=1; continue; fi
  note "--- $service id=$cid ---"
  if [[ "$(dk inspect --format '{{.State.Running}}' "$cid")" != true ]]; then note 'FAIL contenedor detenido'; failed=1; continue; fi
  # Select only non-sensitive inspect fields; never dump Env.
  dk inspect --format 'image={{.Config.Image}} image_id={{.Image}} quota={{.HostConfig.CpuQuota}} period={{.HostConfig.CpuPeriod}} memory={{.HostConfig.Memory}} memorySwap={{.HostConfig.MemorySwap}} swappiness={{json .HostConfig.MemorySwappiness}} cgroupns={{.HostConfig.CgroupnsMode}}' "$cid"
  compare "$service profile label" "$PROFILE_ID" "$(dk inspect --format '{{index .Config.Labels "academic.profile"}}' "$cid")"
  compare "$service inspect quota" "$CPU_QUOTA_US" "$(dk inspect --format '{{.HostConfig.CpuQuota}}' "$cid")"
  compare "$service inspect period" "$CPU_PERIOD_US" "$(dk inspect --format '{{.HostConfig.CpuPeriod}}' "$cid")"
  compare "$service inspect memory" "$MEMORY_BYTES" "$(dk inspect --format '{{.HostConfig.Memory}}' "$cid")"
  compare "$service inspect memory+swap" "$MEMORY_BYTES" "$(dk inspect --format '{{.HostConfig.MemorySwap}}' "$cid")"
  if ! cpu="$(dk exec "$cid" cat /sys/fs/cgroup/cpu.max)" || ! mem="$(dk exec "$cid" cat /sys/fs/cgroup/memory.max)" || ! swap="$(dk exec "$cid" cat /sys/fs/cgroup/memory.swap.max)"; then
    note 'FAIL no se leen controles reales: no se declara perfil aplicado'; failed=1; continue
  fi
  compare "$service cpu.max" "$CPU_QUOTA_US $CPU_PERIOD_US" "$cpu"
  compare "$service memory.max" "$MEMORY_BYTES" "$mem"
  compare "$service memory.swap.max" 0 "$swap"
  dk exec "$cid" cat /sys/fs/cgroup/memory.swap.current
  note 'ADAPTACIÓN: no existe memory.swappiness por cgroup v2; null en inspect significa propiedad descartada, nunca cumplimiento literal.'
  [[ "$ACCEPT_NO_SWAP_ADAPTATION" == true ]] || { note 'FAIL adaptación no aceptada'; failed=1; }
  # On native Linux, inspect host ancestors as well: a leaf cannot override parent ceilings.
  pid="$(dk inspect --format '{{.State.Pid}}' "$cid")"
  if [[ -r "/proc/$pid/cgroup" ]]; then
    rel="$(awk -F: '$1==0 {print $3}' "/proc/$pid/cgroup")"
    cg="$(realpath -m -- "/sys/fs/cgroup$rel")"
    if [[ "$cg" == /sys/fs/cgroup/* && -d "$cg" ]]; then
      while [[ "$cg" != /sys/fs/cgroup ]]; do
        cg="$(dirname -- "$cg")"
        if [[ -r "$cg/cpu.max" ]]; then
          read -r q p < "$cg/cpu.max"; note "Padre $cg cpu.max=$q $p"
          if [[ "$q" != max ]] && (( q * CPU_PERIOD_US < CPU_QUOTA_US * p )); then note 'FAIL cuota padre inferior al perfil'; failed=1; fi
        fi
        if [[ -r "$cg/memory.max" ]]; then
          m="$(cat "$cg/memory.max")"; note "Padre $cg memory.max=$m"
          if [[ "$m" != max ]] && (( m < MEMORY_BYTES )); then note 'FAIL memoria padre inferior al perfil'; failed=1; fi
        fi
      done
    else note 'FAIL no se puede resolver cgroup de host; validación de ancestros incompleta'; failed=1; fi
  else note 'FAIL PID no visible en host local; no se verifican ancestros'; failed=1; fi
 done
(( failed == 0 )) || exit 1
note 'OK límites de hojas/ancestros visibles, con adaptación sin swap aceptada. No prueba rendimiento ni cumplimiento literal de swappiness.'
