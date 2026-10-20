#!/usr/bin/env bash
# Demo state for the arq-review episode, on top of demo/setup.sh.
# Usage: demo/prep/arq-review.sh <home>   (capture runs it after building <home>/mi-servicio)
#
# The team's reviews repo stand-in: ~/arq-reviews, an empty git repo with one invented project
# request (pedido.txt, PRY-2026-0042) for the episode's `real` steps to register. `arq init` and
# every arq command run from the episode itself. Nothing here reaches Jira or the network.
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
cat > pedido.txt <<'P'
Pedido de proyecto PRY-2026-0042
Nombre: Migración del servicio de reportes
Problema: el servicio de reportes corre en la cuenta de Producto y tiene que pasar a la cuenta de Datos.
Alcance: mover la base de reportes y los trabajos nocturnos. Finanzas y Soporte consumen los reportes.
Fecha: el corte es el 30 de noviembre, comprometido con el cliente.
Datos: incluye facturación de clientes.
Duración: queda productivo, sin fecha de baja.
P
printf '# Reviews de Arquitectura\n' > README.md
git add -A && git -c commit.gpgsign=false commit -q -m "chore: reviews repo stand-in"
