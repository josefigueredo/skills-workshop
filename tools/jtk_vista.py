"""Regenerate episodes/pages/jira-team-kit-vista.html: the real `jtk create --html` preview of the
jira-team-kit episode's epic, rendered offline by jtk's own code (no Jira call).

    python3 tools/jtk_vista.py ~/CurrentCode/SPECKIT/Harness/jira-kanban

The checkout must be at the commit the episode pins (skill.commit), so the page matches it."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODE = ROOT / "episodes" / "cursor" / "02-jira-team-kit.json"
OUT = ROOT / "episodes" / "pages" / "jira-team-kit-vista.html"

# The epic the episode drafts from the chat «Tope al descuento en pedidos»: same titles, states and
# assignees as its dry run (NUEVO-1 to NUEVO-4).
SPEC = {
    "epic": {
        "summary": "Tope de descuento",
        "why": "Un pedido con varios cupones puede terminar con un descuento mayor que su total: el cálculo suma "
               "los descuentos sin un tope, y el pedido queda con un total negativo.",
        "what": "Acotar el descuento de un pedido para que nunca supere su subtotal, cubrirlo con un test y "
                "documentar la regla para quien arma promociones.",
        "done_when": "Ningún pedido puede quedar con un total menor que cero, y la regla está escrita en el README "
                     "del servicio.",
    },
    "items": [
        {"type": "task", "area": "BE", "summary": "Acotar el descuento", "started": True,
         "why": "El descuento total se calcula sumando cada cupón, sin compararlo con el subtotal del pedido.",
         "what": "Limitar el descuento acumulado al subtotal del pedido en el cálculo del total.",
         "done_when": "Un pedido de 100 con cupones por 150 queda con descuento 100 y total 0.",
         "subtasks": [
             {"summary": "Test del tope",
              "why": "Sin un test, el tope se puede perder en el próximo cambio al cálculo.",
              "what": "Un test con cupones que superan el subtotal y otro con cupones que no llegan.",
              "done_when": "Los dos tests pasan y fallan si se quita el tope."}]},
        {"type": "task", "area": "BE", "summary": "Documentar el tope",
         "why": "Quien arma promociones no sabe que el descuento tiene un techo.",
         "what": "Explicar la regla del tope, con un ejemplo, en el README del servicio.",
         "done_when": "El README dice qué pasa cuando los cupones superan el subtotal."},
    ],
}


def main(argv) -> int:
    if len(argv) != 1:
        sys.stderr.write(__doc__)
        return 2
    jtk = Path(argv[0]).expanduser().resolve()
    pin = json.loads(EPISODE.read_text(encoding="utf-8"))["skill"]["commit"]
    head = subprocess.run(["git", "-C", str(jtk), "rev-parse", "--short=7", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    if head != pin:
        sys.stderr.write("jtk checkout is at %s, the episode pins %s\n" % (head, pin))
        return 1
    sys.path.insert(0, str(jtk))
    from jkan import preview, spec, sync  # noqa: E402  (from the checkout given)

    conv = json.loads((jtk / "conventions.json").read_text(encoding="utf-8"))
    conv["project"] = "PLAT"
    ops = spec.plan(SPEC, conv)
    sync.assignment(ops, None, bool(conv.get("assign_to_me")))  # what `jtk create` does before the preview
    OUT.write_text(preview.render(ops, conv), encoding="utf-8")
    print("wrote %s" % OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
