#!/usr/bin/env bash
# Read-only assistant: prints instructions, never runs installation commands.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
(( $# == 0 )) || die 'Uso: setup_kubuntu.sh (solo diagnóstico e instrucciones)'
source /etc/os-release
note "Distribución detectada: ${PRETTY_NAME:-unknown}"
note "Base/codename: ${UBUNTU_CODENAME:-${VERSION_CODENAME:-unknown}}; versión: ${VERSION_ID:-unknown}"
note 'Referencia: https://docs.docker.com/engine/install/ubuntu/'
if command -v docker >/dev/null; then
  docker --version
  dk compose version || true
  note 'Instalación existente detectada. No se sobrescribe, desinstala ni actualiza. Revisar procedencia y daemon local manualmente.'
  exit 0
fi
if command -v dpkg-query >/dev/null; then
  note 'Paquetes potencialmente existentes (solo lectura):'
  dpkg-query -W -f='${binary:Package} ${Version}\n' docker.io docker-ce docker-compose-plugin podman-docker containerd containerd.io runc 2>/dev/null || true
fi
case "${ID:-} ${ID_LIKE:-}" in
  *ubuntu*) ;;
  *) die 'No se detecta base Ubuntu; consulte documentación de su distribución. No se propone repositorio Ubuntu para otro sistema.' ;;
esac
cat <<'STEPS'
Acción manual requerida; no se ejecutó ninguna instalación:
1. Confirmar versión/codename Ubuntu de /etc/os-release y soporte oficial actual.
2. Inventariar paquetes y datos existentes. Si hay conflictos, resolver manualmente; este asistente no desinstala nada.
3. En la guía oficial, revisar y ejecutar manualmente los pasos de instalación por repositorio apt:
   - Instalar ca-certificates y curl.
   - Incorporar la clave GPG oficial y verificar el repositorio/arquitectura/codename.
   - Instalar docker-ce, docker-ce-cli, containerd.io, docker-buildx-plugin y docker-compose-plugin.
4. Verificar daemon local y docker compose version. No instalar Docker Desktop ni el compose Python legado.
5. Registrar versiones exactas de paquetes, kernel y Kubuntu. Revisar implicaciones de acceso al socket Docker (equivalente a root).
6. Ejecutar scripts/check_environment.sh. No cambiar GRUB, particiones, kernel ni grupos automáticamente.
Instrucciones detalladas y preparación: docs/09-instalacion-kubuntu.md.
STEPS
