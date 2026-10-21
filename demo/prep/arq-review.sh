#!/usr/bin/env bash
# Demo state for the arq-review episode, on top of demo/setup.sh.
# Usage: demo/prep/arq-review.sh <home>   (capture runs it after building <home>/mi-servicio)
#
# The team's reviews repo stand-in: ~/arq-reviews, an empty git repo. The invented project request
# (PRY-2026-0042) arrives as a screenshot of the PRY platform form; ~/pedido-PRY-2026-0042.md is the
# agent's literal transcription of it, outside the reviews repo, for the episode's `real` `arq new`.
# Its fields follow the platform form of a real request. `arq init` and every arq command run from
# the episode itself. Nothing here reaches Jira or the network.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: arq-review.sh <home>" >&2; exit 2; }
T="$(cd "$1" && pwd)"
D="$T/arq-reviews"
[ ! -e "$D" ] || { echo "refusing: $D already exists" >&2; exit 1; }
mkdir -p "$D"
cd "$D"

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=Demo GIT_AUTHOR_EMAIL=demo@example.com
export GIT_COMMITTER_NAME=Demo GIT_COMMITTER_EMAIL=demo@example.com
export GIT_AUTHOR_DATE="2026-10-19T09:00:00+00:00" GIT_COMMITTER_DATE="2026-10-19T09:00:00+00:00"

git init -q -b main
cat > "$T/pedido-PRY-2026-0042.md" <<'P'
- Tipo: Interno Producto
- Nombre: Migración del servicio de reportes
- Descripción: Pasar el servicio de reportes de la cuenta de Producto a la cuenta de Datos
- Empresa / área: Producto
- Tipo de trabajo: Migración
- Fecha deseada: 2026-11-30 (No, no es negociable)
- Justificación fecha: El corte es el 30 de noviembre, comprometido con el cliente
- Impacto: Si no se llega, el cliente no recibe los reportes de facturación del cierre de mes
- Equipos involucrados: Sí, Finanzas y Soporte consumen los reportes
- Documentación: Google Doc (link)
- ¿Quién valida?: El head del área
- Entregable esperado: El servicio de reportes, su base y los trabajos nocturnos corriendo en la cuenta de Datos
- Requisitos al cierre: Requiere documentación
- Problema / mejora: Mover la base de reportes y los trabajos nocturnos a la cuenta de Datos; incluye facturación de clientes
- Es cross: No
P
printf '# Reviews de Arquitectura\n' > README.md
git add -A && git -c commit.gpgsign=false commit -q -m "chore: reviews repo stand-in"
