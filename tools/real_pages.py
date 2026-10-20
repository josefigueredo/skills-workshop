"""Regenerate episodes/pages/*.html: the real pages the tools show (jtk's create preview and the approval windows of
jtk, ctk and pbmcp), rendered offline by each tool's own code with the episode's data. Nothing calls Jira, Confluence
or Product Brain.

    python3 tools/real_pages.py [--harness ~/CurrentCode/SPECKIT/Harness]

Each tool's checkout must sit at the commit its episode pins (skill.commit), so the page matches what the episode
teaches. ctk and pbmcp need Python 3.11+ and pbmcp needs its dependencies: each tool runs with the Python of its own
.venv when there is one. Prints the width and height each window gets, for the episode's approve step."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "episodes" / "pages"
# tool -> (checkout folder under the Harness, the episode that pins its commit)
TOOLS = {
    "jtk": ("jira-kanban", "cursor/02-jira-team-kit.json"),
    "ctk": ("confluence-team-kit", "cursor/03-confluence-team-kit.json"),
    "pbmcp": ("product-brain-mcp", "cursor/04-product-brain-mcp.json"),
}
ME = "Persona del equipo"  # the person in every episode

# The epic the jira-team-kit episode drafts from the chat «Tope al descuento en pedidos» (NUEVO-1 to NUEVO-4).
JTK_SPEC = {
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
JTK_UNOWNED = [("PLAT-131", "Ordenar por fecha en el listado"), ("PLAT-134", "Mensaje de error del cupón"),
               ("PLAT-140", "Paginar el historial")]
BROWSE = "https://example.atlassian.net/browse/"


def jtk(repo: Path) -> list:
    from jkan import approval, cli, plan, preview, spec, sync

    conv = json.loads((repo / "conventions.json").read_text(encoding="utf-8"))
    conv["project"] = "PLAT"
    # The dry run: what `jtk create --spec … --html` writes, before anyone chose who gets the open issues.
    ops = spec.plan(JTK_SPEC, conv)
    sync.assignment(ops, None, bool(conv.get("assign_to_me")))
    out = [("jira-team-kit-vista.html", preview.render(ops, conv), None)]
    # The approval of `jtk create … --apply --assign-open` (cli.py, create): the person said «asignámelas a mí».
    ops = spec.plan(JTK_SPEC, conv)
    sync.assignment(ops, True, bool(conv.get("assign_to_me")))
    moves = sum(1 for op in ops if op.get("done") or op.get("started"))
    rows, badges = cli._create_rows(ops, conv, ME)
    summary = approval.Summary("", f"Crear en {conv['project']}", rows, kinds=[op["kind"] for op in ops],
                               transitions=moves, badges=badges)
    out.append(("jira-team-kit-crear.html", approval.render_html(summary, len(ops)),
                (520, approval.window_height(summary))))
    # The approval of `jtk apply 3f9a1c07b2de`: assign the three unowned issues of the view plataforma.
    saved = {"id": "3f9a1c07b2de", "kind": "assign", "view": "plataforma", "skipped": [],
             "items": [{"key": k, "title": t, "from": None, "to": {"name": ME}} for k, t in JTK_UNOWNED]}
    summary = plan.summary(saved, browse=lambda key: BROWSE + key)
    out.append(("jira-team-kit-aplicar.html", approval.render_html(summary, len(saved["items"])),
                (520, approval.window_height(summary))))
    return out


def ctk(repo: Path) -> list:
    from ctk.plan import Action, Kind, Plan
    from ctk.window import WINDOW_TITLE, render_html, summary_for_plan, window_height

    assert WINDOW_TITLE == "ctk · Confluence", WINDOW_TITLE
    # The plan of the confluence-team-kit episode: one page changed, four unchanged (its `ctk diff` and `ctk apply`).
    actions = [Action(Kind.UNCHANGED, 0, "docs/arquitectura/index.md", "Arquitectura del servicio", page_id="5010"),
               Action(Kind.UNCHANGED, 0, "docs/arquitectura/componentes.md", "Componentes", page_id="5011"),
               Action(Kind.UNCHANGED, 0, "docs/arquitectura/decisiones", "Decisiones", page_id="5012"),
               Action(Kind.UNCHANGED, 0, "docs/arquitectura/decisiones/adr-001.md", "ADR 001: usar colas",
                      page_id="5013"),
               Action(Kind.UPDATE, 0, "docs/runbook.md", "Runbook de despliegue", page_id="5014")]
    saved = Plan("mi-equipo/mi-servicio", "PLAT", actions)
    summary = summary_for_plan(saved, {"5014": "Runbook de despliegue"}, base_url="https://example.atlassian.net")
    n = len(saved.writes())
    return [("confluence-team-kit-publicar.html", render_html(summary, n), (520, window_height(summary)))]


class _Shown(Exception):
    """Stops a pbmcp tool right after it asked for the approval: nothing past it runs."""


def pbmcp(repo: Path, scratch: Path) -> list:
    import dataclasses

    from pbmcp import approval
    from pbmcp.render import render_html
    from pbmcp.services import Services
    from pbmcp.tools import document, jira, project

    shown = []

    class Capture:
        def approve(self, title, plan, details=None):
            shown.append((title, plan))
            raise _Shown()

    class Client:  # answers only what the two tools read before their approval
        def __init__(self, routes):
            self.routes = routes

        def get(self, path, params=None):
            return self.routes[("GET", path)]

        def post(self, path, body=None):
            return self.routes[("POST", path)]

    allowed = scratch / "allowed"
    allowed.write_text("p-devoluciones\n", encoding="utf-8")

    def run(fn, routes):
        try:
            fn(Services(Client(routes), Capture(), allowed_path=allowed))
        except _Shown:
            return shown[-1]
        raise RuntimeError("the tool never asked for the approval")

    # The footer AlertApprover.approve adds to every page (approval.py), with no details file.
    footer = (f"Aprobás con un clic en Aprobar. Escape o Cancelar no escriben nada. "
              f"Se cancela sola a los {approval.ALERT_TIMEOUT} s.")
    out = []
    title, plan = run(lambda s: project.run(s, "create", name="Autogestión de devoluciones",
                                            description="Las devoluciones se resuelven a mano en soporte y tardan "
                                                        "9 días; la meta es 3 días para el 01/03."), {})
    out.append(("product-brain-mcp-proyecto.html", title, render_html(plan, footer=footer), plan))
    # Creating the PRD from the edited draft starts the workflow (document._from_draft and _create_in_step): the plan
    # is _confirmation's, with the title _create_in_step gives it. The draft's one edit is the episode's.
    original = "Objetivo de la primera entrega: {{pendiente}}\nEntregas: 15/01 y 27/02\n"
    edited = "Objetivo de la primera entrega: web en la 1.ª entrega, app en la 2.ª\nEntregas: 15/01 y 27/02\n"
    expected = document._expected_text({"percentage": 88, "incomplete": {"riesgos": "partial",
                                                                          "dependencias": "partial"}})
    plan = document._confirmation("Crear «Autogestión de devoluciones»",
                                  "Proyecto p-devoluciones · Tipo PRD · tus cambios: +1 −1 líneas",
                                  original, edited, expected)
    plan = dataclasses.replace(plan, title="Arrancar el workflow «Autogestión de devoluciones» y crear "
                                           "«Autogestión de devoluciones»")
    out.append(("product-brain-mcp-documento.html", "Product Brain (pbmcp)", render_html(plan, footer=footer), plan))
    issues = [{"type": "Epic", "summary": "Portal de devoluciones"},
              {"type": "Story", "summary": "Iniciar una devolución desde la web"},
              {"type": "Story", "summary": "Seguir el estado de la devolución"},
              {"type": "Story", "summary": "Iniciar una devolución desde la app"}]
    routes = {("GET", "/documents/d-portal"): {"id": "d-portal", "project_id": "p-devoluciones",
                                               "title": "Portal de devoluciones"},
              ("POST", "/documents/d-portal/export/jira/preview"): issues}
    title, plan = run(lambda s: jira.run(s, "export", document_id="d-portal", project_key="PLAT"), routes)
    out.append(("product-brain-mcp-exportar.html", title, render_html(plan, footer=footer), plan))
    return [(name, html, (600, approval.window_height(plan)), title) for name, title, html, plan in out]


def _check_pin(name: str, repo: Path) -> None:
    episode = json.loads((ROOT / "episodes" / TOOLS[name][1]).read_text(encoding="utf-8"))
    pin = episode["skill"]["commit"]
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=7", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    if head != pin:
        raise SystemExit("%s checkout %s is at %s, its episode pins %s" % (name, repo, head, pin))


def _one(name: str, repo: Path, scratch: Path) -> None:
    """Run inside the tool's own Python: write its pages and print one JSON line per page."""
    sys.path.insert(0, str(repo / "src") if (repo / "src").is_dir() else str(repo))
    pages = {"jtk": lambda: jtk(repo), "ctk": lambda: ctk(repo), "pbmcp": lambda: pbmcp(repo, scratch)}[name]()
    for page in pages:
        file, html, size = page[:3]
        (PAGES / file).write_text(html, encoding="utf-8")
        window = page[3] if len(page) > 3 else {"jtk": "jtk · Jira", "ctk": "ctk · Confluence"}.get(name)
        print(json.dumps({"page": file, "window": window if size else None,
                          "width": size[0] if size else None, "height": size[1] if size else None},
                         ensure_ascii=False))


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harness", default=str(ROOT.parent), help="folder holding the three tool checkouts")
    ap.add_argument("--only", choices=sorted(TOOLS), help=argparse.SUPPRESS)  # one tool, in its own Python
    ap.add_argument("--scratch", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    harness = Path(args.harness).expanduser().resolve()
    if args.only:
        _one(args.only, harness / TOOLS[args.only][0], Path(args.scratch))
        return 0
    PAGES.mkdir(parents=True, exist_ok=True)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="ws-real-pages-") as scratch:
        for name, (folder, _episode) in TOOLS.items():
            repo = harness / folder
            _check_pin(name, repo)
            venv = repo / ".venv" / "bin" / "python"
            python = str(venv) if venv.exists() else sys.executable
            subprocess.run([python, str(Path(__file__).resolve()), "--harness", str(harness), "--only", name,
                            "--scratch", scratch], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
