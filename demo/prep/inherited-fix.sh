#!/usr/bin/env bash
# Demo state for the inherited-fix episode, on top of demo/setup.sh and demo/prep/inherited-audit.sh.
# Usage: demo/prep/inherited-fix.sh <home>   (capture runs it after cloning the skill into <home>/skills)
#
# What the inherited-audit episode leaves behind, so the fix episode starts where that one ends: the run at
# ~/auditorias/mi-servicio with C-01 confirmed by its red test, and the red branch "published". There is no
# network in a capture, so "published" is only local state: an origin with a GitHub-style URL that is never
# contacted, and remote-tracking refs that point at the same commits as the local branches. It goes in before
# `ia.py init`, which records each repo's remote.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: inherited-fix.sh <home>" >&2; exit 2; }
T="$(cd "$1" && pwd)"
bash "$(dirname "$0")/inherited-audit.sh" "$T"

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=Demo GIT_AUTHOR_EMAIL=demo@example.com
export GIT_COMMITTER_NAME=Demo GIT_COMMITTER_EMAIL=demo@example.com
ia() { python3 "$T/skills/inherited-audit/skill/ia.py" "$@"; }
R="$T/mi-servicio"
B=fix/c-01-descuento-sin-tope

git -C "$R" remote add origin git@github.com:demo-org/mi-servicio.git
for b in main "$B"; do
  git -C "$R" update-ref "refs/remotes/origin/$b" "$(git -C "$R" rev-parse "$b")"
done
git -C "$R" branch -q --set-upstream-to="origin/$B" "$B"

cd "$T/auditorias"
ia init --system mi-servicio --repo "API=$R:api" --host cursor --out "$T/auditorias/mi-servicio" >/dev/null
ia detect --run mi-servicio >/dev/null
ia baseline --run mi-servicio >/dev/null
ia finding add --run mi-servicio candidatos/c-01.json >/dev/null
git -C "$R" worktree add -q "$T/auditorias/wt-c-01" "$B"
(cd "$T/auditorias/wt-c-01/api" && python3 -m unittest tests.test_discount_cap >"$T/auditorias/mi-servicio/outputs/C-01-red.txt" 2>&1 || true)
git -C "$R" worktree remove "$T/auditorias/wt-c-01"
ia finding set --run mi-servicio C-01 verdict=confirmed confidence=execution "branch=$B" \
  "sha_test=$(git -C "$R" rev-parse "$B")" 'prod_files=["mi_servicio/orders.py"]' \
  'tests=[{"path":"api/tests/test_discount_cap.py","red":"1 of 1 fail","green":"","note":""}]' \
  'red_reason=order_total() da -50.0 con 150% de descuento' 'fix_summary=Limitar el descuento entre 0 y 100.' \
  outputs.red=outputs/C-01-red.txt 'contrast.model=Sonnet 5.5 High' contrast.same_family=false \
  contrast.verdict=agree 'contrast.note=El test rojo reproduce el total negativo.' >/dev/null

