#!/usr/bin/env bash
# Demo state for the wayofwork episode, on top of demo/setup.sh.
# Usage: demo/prep/wayofwork.sh <home>   (capture runs it after building <home>/mi-servicio)
#
# Turns ~/mi-servicio into a WayOfWork project halfway through an invented initiative («Devoluciones en
# línea»): context pack with one owner decision still open, a plan with two epics whose readiness is
# approved, E1 already exported to Jira as PLAT-123 (invented key) with its Product Brain chats audited,
# and Spec-Kit's feature for PLAT-123 clarified and planned, with no tasks yet. E2 has no packet and no chat.
# Everything is local files: no Jira credentials, GitHub links disabled, nothing reaches the network.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: wayofwork.sh <home>" >&2; exit 2; }
T="$(cd "$1" && pwd)"
P="$T/mi-servicio"
[ -d "$P/.git" ] || { echo "missing $P (run demo/setup.sh first)" >&2; exit 1; }
[ ! -e "$P/wow" ] || { echo "refusing: $P/wow already exists" >&2; exit 1; }
cd "$P"

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=Demo GIT_AUTHOR_EMAIL=demo@example.com
export GIT_COMMITTER_NAME=Demo GIT_COMMITTER_EMAIL=demo@example.com
export GIT_AUTHOR_DATE="2026-10-19T09:00:00+00:00" GIT_COMMITTER_DATE="2026-10-19T09:00:00+00:00"

mkdir -p .wow wow/context-pack wow/plan wow/pb/chats .spec-kit/discovery specs/001-devoluciones

# GitHub links off: `wow snapshot` would otherwise call `gh pr list`.
printf '{\n  "github": {"enabled": false}\n}\n' > .wow/config.json

cat > wow/context-pack/facts.md <<'F'
# Hechos

- C1: Las órdenes se guardan con su total calculado al crearlas [MEDIDO] (fuente: api/mi_servicio/orders.py:1)
- C2: La web es estática y no tiene login propio [MEDIDO] (fuente: web/index.html:1)
F
cat > wow/context-pack/pending-owner.md <<'O'
# Decisiones del owner

- [x] Plazo para pedir una devolución: 30 días
- [ ] ¿Avisamos por mail cuando sale el reintegro?
O

cat > .spec-kit/discovery/architecture.md <<'A'
# Arquitectura

API de órdenes en Python, web estática y documentación en docs/.
A

cat > wow/plan/PLAN.md <<'B'
# Devoluciones en línea

## Brief
- Goal: que quien compró pida una devolución desde la web sin escribir a soporte
- Problem: hoy cada devolución entra por mail y soporte la carga a mano
- Constraints: el reintegro usa el mismo medio de pago de la orden
- Non-goals: devoluciones parciales
- Open questions: aviso por mail del reintegro (decisión del owner)

## Contexto
mi-servicio ya guarda las órdenes con su total; falta el circuito de devolución y reintegro.
B

cat > wow/plan/manifest.json <<'M'
{
  "schema_version": 1,
  "plan": {
    "id": "0001-devoluciones",
    "title": "Devoluciones en línea",
    "created": "2026-10-13",
    "mode": "brownfield",
    "readiness": {"verdict": "approved", "rounds": 1},
    "export": {"frozen": true, "at": "2026-10-16T15:00:00Z", "epics": {"E1": "PLAT-123"}}
  },
  "epics": [
    {
      "id": "E1",
      "title": "Pedir una devolución",
      "done_when": ["E1.C1: quien compró pide la devolución de una orden y ve su estado"],
      "tasks": [
        {"id": "1.1", "title": "Modelo de devolución",
         "acceptance": ["AC1: Dado una orden pagada Cuando se pide la devolución Entonces queda ligada a esa orden"],
         "depends_on": [], "subtasks": ["definir el modelo"], "estimate": 3, "priority": "high", "labels": ["backend"],
         "component": "BE",
         "story": {"user_story_text": "Como persona que compró quiero pedir una devolución para no escribir a soporte"}},
        {"id": "1.2", "title": "Endpoint para pedirla",
         "acceptance": ["AC1: Dado una orden pagada Cuando llega POST /returns Entonces responde 201"],
         "depends_on": ["1.1"], "subtasks": ["exponer el endpoint"], "estimate": 5, "priority": "high", "labels": ["backend"],
         "component": "BE",
         "story": {"user_story_text": "Como persona que compró quiero pedirla desde la web para ver su estado"}}
      ]
    },
    {
      "id": "E2",
      "title": "Reintegro del pago",
      "done_when": ["E2.C1: el reintegro sale solo cuando la devolución se aprueba"],
      "product": {
        "objective": "Reintegrar el pago de una devolución aprobada",
        "problem": "Hoy soporte carga cada reintegro a mano",
        "strategic_objective": "Eficiencia operativa",
        "expected_impact": "Menos tickets de soporte por devoluciones",
        "out_of_scope": "Devoluciones parciales",
        "insights": ["Soporte carga los reintegros a mano [ESTIMACIÓN]"],
        "assumptions": ["El medio de pago acepta reintegros"],
        "dependencies": ["E1 terminada"],
        "related_documents": ["PRD de la iniciativa"],
        "start_date": "2026-11-02", "end_date_estimated": "2026-11-27", "quarter": "Q4/2026",
        "criticality": "Media", "priority": "Media", "big_move": false,
        "owner": "Owner de producto", "vertical": "Pagos",
        "technical_context": "API de órdenes en Python", "notes": "Sin notas adicionales"
      },
      "tasks": [
        {"id": "2.1", "title": "Disparar el reintegro",
         "acceptance": ["AC1: Dado una devolución aprobada Cuando se confirma Entonces sale un reintegro por el total"],
         "depends_on": [], "estimate": 5, "priority": "medium", "labels": ["backend"],
         "subtasks": [{"title": "[BE] llamar al reintegro", "purpose": "devolver el pago", "how_to": "desde la API de órdenes", "component": "BE"}],
         "component": "BE",
         "story": {"user_story_text": "Como persona que compró quiero recibir el reintegro para no reclamar a soporte",
                   "context_and_need": "Hoy soporte carga cada reintegro a mano",
                   "scope": "Reintegro total al mismo medio de pago", "out_of_scope": "Reintegros parciales",
                   "technical_info": "Se dispara desde la API de órdenes",
                   "assumptions": ["La devolución ya está aprobada"], "business_rules": ["Solo devoluciones aprobadas"],
                   "edge_cases": ["Reintegro rechazado por el medio de pago"], "assets": ["Contrato de la API"]}}
      ]
    }
  ]
}
M

# E1's Product Brain chats, already closed and audited (copies the person pasted from Product Brain).
for name in prd rfc epic-E1; do
  printf 'Copia local del chat de Product Brain (%s): llega al 100%%.\n' "$name" > "wow/pb/chats/$name.md"
  printf '{"verdict": "approved"}\n' > "wow/pb/chats/$name.audit.json"
done

# Spec-Kit's feature for PLAT-123: synced, clarified and planned; tasks not ratified yet.
cat > specs/001-devoluciones/spec.md <<'S'
# Pedir una devolución

**Jira Epic:** PLAT-123

## Clarifications

### Session 2026-10-17
- Plazo para pedir la devolución: 30 días desde la compra.
S
printf '# Plan\n\nModelo de devolución y endpoint POST /returns.\n' > specs/001-devoluciones/plan.md

git add -A && git -c commit.gpgsign=false commit -q -m "chore: devoluciones en curso"
