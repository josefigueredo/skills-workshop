#!/usr/bin/env bash
# Builds the demo system: a small git repo "mi-servicio" (api + web + docs) with seeded bugs.
# Usage: demo/setup.sh <target-dir>      -> creates <target-dir>/mi-servicio (must not exist)
# Episode-specific state goes in demo/prep/<episode-id>.sh, which capture runs afterwards.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: setup.sh <target-dir>" >&2; exit 2; }
mkdir -p "$1"
T="$(cd "$1" && pwd)"
D="$T/mi-servicio"
[ ! -e "$D" ] || { echo "refusing: $D already exists" >&2; exit 1; }
mkdir -p "$D/api/mi_servicio" "$D/api/tests" "$D/web" "$D/docs"

# Fixed identity, isolated from the person's git config.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=Demo GIT_AUTHOR_EMAIL=demo@example.com
export GIT_COMMITTER_NAME=Demo GIT_COMMITTER_EMAIL=demo@example.com
commit() {  # commit <iso-date> <message>
  export GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1"
  git add -A && git -c commit.gpgsign=false commit -q -m "$2"
}

cd "$D"
git init -q -b main
printf '__pycache__/\n*.pyc\n' > .gitignore

# --- commit 1: api skeleton ---
: > api/mi_servicio/__init__.py
: > api/tests/__init__.py
cat > api/mi_servicio/orders.py <<'P'
"""Order handling for mi-servicio."""

ORDERS = {}


def create_order(order_id, items):
    """Store an order; items is a list of (unit_price, quantity)."""
    ORDERS[order_id] = {"items": list(items), "status": "new"}
    return ORDERS[order_id]


def order_total(order_id, discount_pct=0):
    """Total of an order after a percentage discount."""
    order = ORDERS[order_id]
    gross = sum(price * qty for price, qty in order["items"])
    return gross - gross * discount_pct / 100
P
cat > api/tests/test_orders.py <<'P'
import unittest

from mi_servicio import orders


class OrderTotalTest(unittest.TestCase):
    def setUp(self):
        orders.ORDERS.clear()

    def test_total_sums_items(self):
        orders.create_order("A1", [(10, 2), (5, 1)])
        self.assertEqual(orders.order_total("A1"), 25)

    def test_ten_percent_discount(self):
        orders.create_order("A2", [(100, 1)])
        self.assertEqual(orders.order_total("A2", discount_pct=10), 90)
P
cat > README.md <<'P'
# mi-servicio

Servicio de pedidos de ejemplo: una API en Python (`api/`), un frontend
estático mínimo (`web/`) y notas (`docs/`).

Tests de la API: `cd api && python3 -m unittest`
P
commit 2026-10-12T10:00:00+00:00 "feat: orders module with totals"

# --- commit 2: stats, pagination, counter ---
cat > api/mi_servicio/stats.py <<'P'
"""Small helpers used by the dashboard."""


def average(values):
    """Mean of a list of numbers."""
    return sum(values) / len(values)


def paginate(items, page, size):
    """Return the items of a 1-based page."""
    start = page * size
    return items[start:start + size]
P
cat > api/mi_servicio/counter.py <<'P'
"""Shared request counter."""
import time

_count = 0


def hit():
    """Register one request and return the new total."""
    global _count
    current = _count
    time.sleep(0)  # yields the thread: another hit can run between read and write
    _count = current + 1
    return _count


def total():
    return _count


def reset():
    global _count
    _count = 0
P
cat > api/tests/test_stats.py <<'P'
import unittest

from mi_servicio import counter, stats


class StatsTest(unittest.TestCase):
    def test_average(self):
        self.assertEqual(stats.average([2, 4, 6]), 4)

    def test_first_page(self):
        self.assertEqual(stats.paginate([1, 2, 3, 4], 0, 2), [1, 2])


class CounterTest(unittest.TestCase):
    def test_sequential_hits(self):
        counter.reset()
        counter.hit()
        counter.hit()
        self.assertEqual(counter.total(), 2)
P
commit 2026-10-14T15:30:00+00:00 "feat: stats helpers and request counter"

# --- commit 3: handler, web, docs ---
cat > api/mi_servicio/handlers.py <<'P'
"""Request handlers: plain functions from a dict request to a dict response."""
from mi_servicio import counter, orders


def get_order(request):
    counter.hit()
    order = orders.ORDERS.get(request["id"])
    if order is None:
        return {"status": 404, "body": "not found"}
    return {"status": 200, "body": order}
P
cat > api/tests/test_handlers.py <<'P'
import unittest

from mi_servicio import handlers, orders


class GetOrderTest(unittest.TestCase):
    def setUp(self):
        orders.ORDERS.clear()

    def test_found(self):
        orders.create_order("B1", [(1, 1)])
        self.assertEqual(handlers.get_order({"id": "B1"})["status"], 200)

    def test_missing(self):
        self.assertEqual(handlers.get_order({"id": "nope"})["status"], 404)
P
cat > web/index.html <<'P'
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>mi-servicio</title></head>
<body>
  <h1>Pedidos</h1>
  <ul id="orders"></ul>
  <script src="app.js"></script>
</body>
</html>
P
cat > web/app.js <<'P'
// Renders the order list returned by the API.
fetch("/orders")
  .then((r) => r.json())
  .then((list) => {
    document.getElementById("orders").innerHTML = list
      .map((o) => "<li>" + o.id + ": " + o.note + "</li>")
      .join("");
  });
P
cat > docs/arquitectura.md <<'P'
# Arquitectura

- `api/`: módulos de Python sin dependencias externas (`orders`, `stats`, `counter`, `handlers`).
- `web/`: página estática que consume `/orders`.
- El contador de pedidos (`counter.py`) es global del proceso.
P
commit 2026-10-16T09:15:00+00:00 "feat: order handler, static web and docs"
