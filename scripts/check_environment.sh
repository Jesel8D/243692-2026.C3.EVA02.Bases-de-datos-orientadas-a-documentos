#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# == 0 )) || die 'Uso: check_environment.sh'
failed=0
ok() { note "OK: $*"; }
fail() { note "FAIL: $*"; failed=1; }
[[ -r /etc/os-release ]] || die 'Falta /etc/os-release.'
# Trusted OS metadata, never user config.
source /etc/os-release
note "Distribución: ${PRETTY_NAME:-unknown}; base Ubuntu: ${UBUNTU_CODENAME:-${VERSION_CODENAME:-unknown}}"
note "Kernel: $(uname -r); arquitectura: $(uname -m)"
[[ "$(uname -s)" == Linux ]] && ok Linux || fail 'Se requiere Linux'
[[ "$(uname -m)" == x86_64 ]] && ok x86_64 || fail 'Se requiere x86_64 para esta configuración'
case "${ID:-} ${ID_LIKE:-}" in *ubuntu*) ok 'Base Ubuntu detectada (versión local aún debe registrarse)' ;; *) note 'AVISO: no es Kubuntu/Ubuntu; solo validación Cloud u otra distribución.' ;; esac
cpus="$(nproc)"
available_kb="$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo)"
note "CPU disponibles (afinidad/cgroup): $cpus; MemAvailable host: $available_kb KiB"
(( cpus >= 4 )) && ok 'Al menos 4 CPU visibles' || fail 'Menos de 4 CPU visibles; baseline no validable'
(( available_kb >= 6*1024*1024 )) && ok 'Memoria disponible >= 6 GiB (un baseline + margen)' || fail 'Memoria disponible insuficiente para baseline con margen'
if [[ -r /sys/fs/cgroup/cgroup.controllers ]]; then
  ok 'Jerarquía cgroups v2 visible'
  controllers=" $(cat /sys/fs/cgroup/cgroup.controllers) "
  for ctl in cpu memory; do
    [[ "$controllers" == *" $ctl "* ]] && ok "Controlador $ctl visible" || fail "Controlador $ctl ausente"
  done
  # Namespace root may itself have stricter inherited limits (Cloud).
  if [[ -r /sys/fs/cgroup/cpu.max ]]; then
    read -r quota period < /sys/fs/cgroup/cpu.max
    note "cpu.max raíz visible: $quota $period"
    if [[ "$quota" != max ]] && (( quota < 4*period )); then fail 'Cuota padre visible menor que baseline (4 CPU)'; fi
  fi
  if [[ -r /sys/fs/cgroup/memory.max ]]; then
    mem="$(cat /sys/fs/cgroup/memory.max)"; note "memory.max raíz visible: $mem"
    if [[ "$mem" != max ]] && (( mem < 6*1024*1024*1024 )); then fail 'Límite padre de memoria insuficiente para baseline con margen'; fi
  fi
else fail 'Jerarquía cgroups v2 no visible'; fi
if command -v docker >/dev/null; then
  docker --version
  if dk info --format 'Docker={{.ServerVersion}} OS={{.OSType}} cgroups={{.CgroupVersion}} driver={{.CgroupDriver}} CPU={{.NCPU}} RAM={{.MemTotal}}' ; then
    [[ "$(dk info --format '{{.CgroupVersion}}')" == 2 ]] && ok 'Daemon usa cgroups v2' || fail 'Daemon no usa cgroups v2'
    dk info --format '{{json .Warnings}}'
  else fail 'Daemon local inaccesible (no se modifica)'; fi
  if dk compose version; then ok 'Compose Plugin disponible'; else fail 'Falta Compose Plugin'; fi
else fail 'Docker Engine CLI no instalado'; fi
note 'Swappiness por cgroup no disponible en v2 de Docker 28.4; alternativa sin swap requiere aceptación explícita y memory.swap.max=0 verificado.'
note 'Controladores visibles no prueban delegación ni límites efectivos: ejecutar verify_resources.sh después de iniciar.'
(( failed == 0 )) || exit 1
