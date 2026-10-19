#!/usr/bin/env bash
# Demo state for the inherited-audit episode, on top of demo/setup.sh.
# Usage: demo/prep/inherited-audit.sh <home>   (capture runs it after building <home>/mi-servicio)
#
# What the audit's workers would leave behind, so the episode's `real` CLI steps have
# something to load: one local branch with a test-only red commit (the proof pass) and
# the candidate findings, outside the repo (the agent saves them before `ia.py finding add`).
# `main` stays checked out, clean and at the same HEAD.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: inherited-audit.sh <home>" >&2; exit 2; }
T="$(cd "$1" && pwd)"
cd "$T/mi-servicio"

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=Demo GIT_AUTHOR_EMAIL=demo@example.com
export GIT_COMMITTER_NAME=Demo GIT_COMMITTER_EMAIL=demo@example.com
commit() {  # commit <iso-date> <message>
  export GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1"
  git add -A && git -c commit.gpgsign=false commit -q -m "$2"
}

git checkout -q -b fix/c-01-descuento-sin-tope
cat > api/tests/test_discount_cap.py <<'P'
import unittest

from mi_servicio import orders


class DiscountCapTest(unittest.TestCase):
    def setUp(self):
        orders.ORDERS.clear()

    def test_a_discount_over_100_never_makes_the_total_negative(self):
        orders.create_order("C1", [(100, 1)])
        self.assertGreaterEqual(orders.order_total("C1", discount_pct=150), 0)
P
commit 2026-10-17T11:00:00+00:00 "test: un descuento de más del 100% deja el total negativo"
git checkout -q main

C="$T/auditorias/candidatos"
mkdir -p "$C"
cat > "$C/c-01.json" <<'P'
{"report": "correctness", "category": "pedidos", "dimension": "bug",
 "title": "Un descuento de más del 100% deja el total negativo",
 "verdict": "candidate", "severity": "medium", "confidence": "execution", "source": "/review-bugbot",
 "what_happens": "order_total() resta el porcentaje sin tope: con un descuento de 150% un pedido de 100 da -50.",
 "evidence": [{"cite": "API/mi_servicio/orders.py", "from": 12, "to": 16, "note": "no hay tope en discount_pct"}]}
P
cat > "$C/c-02.json" <<'P'
{"report": "correctness", "category": "contador", "dimension": "race",
 "title": "Dos pedidos a la vez pueden contarse como uno",
 "verdict": "candidate", "severity": "low", "confidence": "unverified", "source": "races-distributed",
 "what_happens": "Inferencia: hit() lee el contador y lo escribe en dos pasos; dos hilos pueden pisarse. No se reprodujo con un test.",
 "evidence": [{"cite": "API/mi_servicio/counter.py", "from": 7, "to": 13, "note": "lectura y escritura separadas"}]}
P
cat > "$C/q-01.json" <<'P'
{"report": "quality", "category": "estadisticas", "dimension": "docs",
 "title": "La paginación dice empezar en 1 pero empieza en 0",
 "verdict": "confirmed", "severity": "low", "confidence": "docs", "source": "quality-lenses",
 "what_happens": "El docstring de paginate() habla de páginas desde 1, pero el cálculo toma la página 0 como la primera.",
 "evidence": [{"cite": "API/mi_servicio/stats.py", "from": 9, "to": 12, "note": "page * size: la primera página es la 0"}],
 "suggestion": "Decidir si la primera página es la 0 o la 1, corregir el docstring o el cálculo y sumar un test de la página 1.",
 "effort": "S"}
P
