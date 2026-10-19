// Render tests. Structural only: the harness loads no CSS, so nothing here
// depends on computed visibility.
function fixtureEpisode() {
  return {
    id: "demo", series: "cursor", order: 1, title: "demo-skill",
    skill: {repo: "demo-skill", commit: "abc1234", date: "2026-10-19"},
    workspace: {repo: "mi-servicio", files: ["api", "web", "README.md"],
                chats: [{title: "Agregar endpoint de pagos", age: "2d"}]},
    chapters: [
      {id: "instalar", title: "Instalar", subtitle: "Una vez por máquina", screen: "terminal",
       steps: [
         {type: "term", cmd: "./install.sh", out: ["listo"], source: "real", cwd: "~"},
         {type: "say", md: "Texto suelto", source: "inferido"}
       ]},
      {id: "caso", title: "Caso principal", subtitle: "Una auditoría", screen: "cursor-full",
       steps: [
         {type: "ask", text: "Auditá este sistema", source: "inferido"},
         {type: "worked", seconds: 42, source: "inferido"},
         {type: "tool", label: "Ran · ia.py init", source: "inferido"},
         {type: "term", cmd: "python3 ia.py status", out: ["baseline: done"], source: "inferido"},
         {type: "say", md: "#### Hecho\nLa base es **a1b2c3d** con `npm ci`.\n- uno\n- dos", source: "inferido"},
         {type: "approve", title: "Crear 2 tickets", lines: ["PROJ-1", "PROJ-2"], button: "Apruebo 2",
          source: "inferido"},
         {type: "ask", text: "Seguí", source: "inferido"}
       ]},
      {id: "cc", title: "En Claude Code", screen: "claude-code",
       steps: [
         {type: "ask", text: "Hola", source: "inferido"},
         {type: "term", cmd: "ls", out: ["a", "b"], source: "inferido"},
         {type: "say", md: "Listo", source: "inferido"},
         {type: "worked", seconds: 3, source: "inferido"}
       ]}
    ]
  };
}
// Flattened: 0 card instalar, 1 term, 2 say, 3 card caso, 4 ask, 5 worked, 6 tool,
// 7 term, 8 say, 9 approve, 10 ask, 11 card cc, 12 ask, 13 term, 14 say, 15 worked

function box() { return document.createElement("div"); }
function render(i, ep) { var c = box(); Render.step(c, ep || fixtureEpisode(), i); return c; }
function stepIds(c) {
  return Array.prototype.map.call(c.querySelectorAll("[data-step]"),
    function (n) { return n.getAttribute("data-step"); });
}

test("a card shows the chapter title, subtitle and n de total", function () {
  var c = render(3);
  var card = c.querySelector(".ws-card");
  assert(card, "no card");
  assert(card.textContent.indexOf("Caso principal") >= 0, "title missing");
  assert(card.textContent.indexOf("Una auditoría") >= 0, "subtitle missing");
  assert(card.textContent.indexOf("demo-skill · 2 de 3") >= 0, "kicker missing: " + card.textContent);
  assertEqual(stepIds(c), []);
});

test("cursor-full at its 3rd step shows exactly 3 step nodes in order", function () {
  var c = render(6);
  assert(c.querySelector(".ws-cursor-full"), "not cursor-full");
  assertEqual(stepIds(c), ["0", "1", "2"]);
});

test("going back leaves no residue", function () {
  var c = box(), ep = fixtureEpisode();
  Render.step(c, ep, 10);
  Render.step(c, ep, 8);
  // term (3) lives in the zsh panel, so compare as a set, not in document order.
  assertEqual(stepIds(c).sort(), ["0", "1", "2", "3", "4"]);
  assertEqual(c.children.length, 1);
  assert(!c.querySelector(".ws-approve:not([hidden])"), "approve overlay left behind");
});

test("term on cursor-full is in the integrated zsh, not in the conversation", function () {
  var c = render(7);
  var zsh = c.querySelector(".ws-zsh"), conv = c.querySelector(".ws-conv");
  assert(zsh.textContent.indexOf("python3 ia.py status") >= 0, "cmd not in zsh");
  assert(zsh.textContent.indexOf("baseline: done") >= 0, "output not in zsh");
  assert(conv.textContent.indexOf("python3 ia.py status") < 0, "cmd leaked into conversation");
});

test("term on terminal is in the main area", function () {
  var c = render(1);
  var main = c.querySelector(".ws-terminal .ws-term-body");
  assert(main, "no terminal body");
  assert(main.textContent.indexOf("./install.sh") >= 0, "cmd missing");
  assert(main.textContent.indexOf("listo") >= 0, "output missing");
  assert(!c.querySelector(".ws-zsh"), "terminal has no integrated zsh");
});

test("approve renders an overlay with Cancelar and the step's button", function () {
  var c = render(9);
  var ov = c.querySelector(".ws-approve:not([hidden])");
  assert(ov, "no visible overlay");
  assert(c.firstChild.contains(ov), "overlay outside the screen root");
  var labels = Array.prototype.map.call(ov.querySelectorAll("button"), function (b) { return b.textContent; });
  assertEqual(labels, ["Cancelar", "Apruebo 2"]);
  assert(ov.textContent.indexOf("Crear 2 tickets") >= 0 && ov.textContent.indexOf("PROJ-2") >= 0);
});

test("a past approve keeps its node hidden", function () {
  var c = render(10);
  var ov = c.querySelector(".ws-approve");
  assert(ov && ov.hasAttribute("hidden"), "past approve must stay hidden");
  assertEqual(stepIds(c).length, 7);
});

test("say markdown renders strong, code, list items and a heading", function () {
  var c = render(8);
  var say = c.querySelector('[data-step="4"]');
  assertEqual(say.querySelector("strong").textContent, "a1b2c3d");
  assertEqual(say.querySelector("code").textContent, "npm ci");
  assertEqual(Array.prototype.map.call(say.querySelectorAll("li"), function (l) { return l.textContent; }),
              ["uno", "dos"]);
  assertEqual(say.querySelector("h4").textContent, "Hecho");
});

test("episode text is inserted as text, never as markup", function () {
  var ep = fixtureEpisode();
  ep.chapters[1].steps[0].text = "<script>window.pwned=1</script>";
  ep.chapters[1].steps[4].md = "**<img src=x onerror=alert(1)>** y `<b>no</b>`";
  ep.chapters[1].title = "<u>t</u>";
  var c = render(8, ep);
  assert(c.querySelector("script") === null, "script element created");
  assert(c.querySelector("img") === null, "img element created");
  assert(c.querySelector("u") === null && c.querySelector("code b") === null, "markup created");
  assert(c.textContent.indexOf("<u>t</u>") >= 0, "literal title missing");
  assert(c.textContent.indexOf("<script>window.pwned=1</script>") >= 0, "literal text missing");
  assert(c.textContent.indexOf("<img src=x onerror=alert(1)>") >= 0, "literal md text missing");
});

test("the user label and model are the generic ones", function () {
  var c = render(4);
  assert(c.textContent.indexOf("Persona del equipo") >= 0, "user label missing");
  assert(c.textContent.indexOf("Sonnet 5.5") >= 0, "model missing");
  assert(c.textContent.indexOf("Caso principal") >= 0, "chat titled after the chapter");
  assert(c.textContent.indexOf("Agregar endpoint de pagos") >= 0, "workspace chat missing");
});

test("claude-code uses the transcript layout", function () {
  var c = render(15);
  var root = c.querySelector(".ws-claude-code");
  assert(root, "not claude-code");
  var t = root.textContent;
  assert(t.indexOf("> Hola") >= 0, "ask line");
  assert(t.indexOf("⏺ Bash(ls)") >= 0, "bash line");
  assert(t.indexOf("⎿ a") >= 0, "output line");
  assert(t.indexOf("⏺ Listo") >= 0 || root.querySelector('[data-step="2"]').textContent.indexOf("⏺") >= 0, "say");
  assert(t.indexOf("✻ Worked for 3s") >= 0, "worked line");
});

test("cursor-agent shows a term as a Ran chip and has Open Tabs", function () {
  var ep = fixtureEpisode();
  ep.chapters[1].screen = "cursor-agent";
  var c = render(7, ep);
  assert(c.querySelector(".ws-cursor-agent"), "not cursor-agent");
  assert(!c.querySelector(".ws-zsh"), "no zsh panel on cursor-agent");
  assert(c.querySelector(".ws-opentabs"), "no Open Tabs column");
  var st = c.querySelector('[data-step="3"]');
  assert(st.textContent.indexOf("▸ Ran · python3 ia.py status") >= 0, "chip: " + st.textContent);
  assert(st.textContent.indexOf("baseline: done") >= 0, "chip output");
});

test("animation hooks mark typed text, lines and nodes", function () {
  var c = render(8);
  assertEqual(c.querySelector('[data-step="0"] [data-anim="type"]').textContent, "Auditá este sistema");
  assert(c.querySelector('[data-step="1"]').getAttribute("data-anim") === "node", "worked node");
  assert(c.querySelector('[data-step="2"]').getAttribute("data-anim") === "node", "tool node");
  assertEqual(c.querySelector('[data-step="3"] [data-anim="type"]').textContent, "python3 ia.py status");
  assert(c.querySelector('[data-step="3"] [data-anim="line"]').textContent.indexOf("baseline: done") >= 0);
  assert(c.querySelectorAll('[data-step="4"] [data-anim="line"]').length >= 3, "say lines");
});

test("minimal workspace, empty episode and out-of-range index do not throw", function () {
  var ep = fixtureEpisode();
  ep.workspace = {repo: "x"};
  var c = render(99, ep);
  assert(c.querySelector(".ws-claude-code"), "clamped to the last step");
  var e = box();
  Render.step(e, {chapters: [], workspace: {repo: "x"}}, 0);
  assertEqual(e.children.length, 1);
  Render.step(e, ep, -3);
  assert(e.querySelector(".ws-card"), "clamped to the first card");
});

test("hooks hold on every screen", function () {
  ["terminal", "cursor-full", "cursor-agent", "claude-code"].forEach(function (screen) {
    var ep = fixtureEpisode();
    ep.chapters[1].screen = screen;
    ep.chapters[1].steps.pop();  // end on the approve step: the overlay is current
    var c = render(9, ep);
    assertEqual(stepIds(c).sort(), ["0", "1", "2", "3", "4", "5"], screen);
    function q(j, sel) { return c.querySelector('[data-step="' + j + '"]' + sel); }
    assertEqual(q(0, ' [data-anim="type"]').textContent, "Auditá este sistema", screen + " ask");
    assertEqual(q(1, "").getAttribute("data-anim"), "node", screen + " worked");
    assertEqual(q(2, "").getAttribute("data-anim"), "node", screen + " tool");
    assert(q(3, ' [data-anim="line"]').textContent.indexOf("baseline: done") >= 0, screen + " term out");
    if (screen === "cursor-agent" || screen === "claude-code") {
      assert(q(3, ' [data-anim="node"]').textContent.indexOf("python3 ia.py status") >= 0, screen + " term node");
    } else {
      assertEqual(q(3, ' [data-anim="type"]').textContent, "python3 ia.py status", screen + " term cmd");
    }
    assert(c.querySelectorAll('[data-step="4"] [data-anim="line"]').length >= 3, screen + " say lines");
    var ov = q(5, "");
    assert(ov.getAttribute("data-anim") === "node" && !ov.hasAttribute("hidden"), screen + " approve");
  });
});
