// Render tests. Structural only: the harness loads no CSS, so nothing here
// depends on computed visibility.
// Fixed prompt clock: every Render.step in this suite shows the same time.
var FIXED_NOW = new Date(2026, 9, 19, 9, 5, 7);
Render.now = function () { return FIXED_NOW; };
function fixtureEpisode() {
  return {
    id: "demo", series: "cursor", order: 1, title: "demo-skill",
    pitch: {ask: "Auditá este sistema antes de empezar", does: "Fija la base y entrega dos reportes."},
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
         {type: "term", cmd: "python3 ia.py status", out: ["baseline: done"], source: "inferido", in: "zsh"},
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

test("the first card shows the pitch; other cards and pitchless episodes do not", function () {
  var c = render(0);
  var p = c.querySelector(".ws-card-pitch");
  assert(p, "no pitch on the first card");
  var t = p.textContent;
  assert(t.indexOf("Le decís al agente…") >= 0 && t.indexOf("Y la skill…") >= 0, "labels: " + t);
  assert(t.indexOf("Auditá este sistema antes de empezar") >= 0, "ask missing");
  assert(t.indexOf("Fija la base y entrega dos reportes.") >= 0, "does missing");
  assert(c.querySelector(".ws-card-title").textContent === "Instalar", "title still there");
  assertEqual(stepIds(c), []);
  assert(!render(3).querySelector(".ws-card-pitch"), "pitch on a later card");
  var ep = fixtureEpisode();
  delete ep.pitch;
  assert(!render(0, ep).querySelector(".ws-card-pitch"), "pitch without data");
});

test("the episode's first card shows the arrow keys that move between screens; later cards do not", function () {
  var keys = render(0).querySelector(".ws-card-keys");
  assert(keys, "no arrow keys hint on the first card");
  var caps = Array.prototype.map.call(keys.querySelectorAll(".ws-key"), function (k) { return k.textContent; });
  assertEqual(caps, ["←", "→"]);
  assert(keys.textContent.indexOf("teclado") >= 0, "hint text: " + keys.textContent);
  assertEqual(stepIds(render(0)), []);
  assert(!render(3).querySelector(".ws-card-keys"), "hint on a later card");
});

test("term on cursor-full without 'in' is the agent's: a Ran chip in the conversation", function () {
  var ep = fixtureEpisode();
  delete ep.chapters[1].steps[3].in;
  var c = render(7, ep);
  var zsh = c.querySelector(".ws-zsh"), conv = c.querySelector(".ws-conv");
  assert(zsh, "cursor-full keeps its zsh panel");
  assert(zsh.textContent.indexOf("python3 ia.py status") < 0, "agent cmd leaked into zsh");
  var st = conv.querySelector('[data-step="3"]');
  assert(st, "step not in the conversation");
  assert(st.textContent.indexOf("▸ Ran · python3 ia.py status") >= 0, "chip: " + st.textContent);
  assert(st.querySelector('[data-anim="node"]').textContent.indexOf("python3 ia.py status") >= 0, "chip hook");
  assert(st.querySelector('[data-anim="line"]').textContent.indexOf("baseline: done") >= 0, "output hook");
  assertEqual(c.querySelectorAll('[data-anim="idle"]').length, 1, "zsh idle prompt stays");
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

test("say markdown renders ## and ### headings and a pipe table with its header row", function () {
  var ep = fixtureEpisode();
  ep.chapters[1].steps[4].md = "## Estado\n**7 abiertos**\n\n### Por board\n| Board | Abiertos |\n| ----- | -------- |\n" +
    "| PLAT  | **7**    |\n| DESK  | 2        |\nDespués.";
  var say = render(8, ep).querySelector('[data-step="4"]');
  assertEqual(Array.prototype.map.call(say.querySelectorAll("h4"), function (h) { return h.textContent; }),
              ["Estado", "Por board"]);
  var table = say.querySelector("table");
  assert(table, "no table");
  assertEqual(Array.prototype.map.call(table.querySelectorAll("thead th"), function (t) { return t.textContent; }),
              ["Board", "Abiertos"]);
  var rows = table.querySelectorAll("tbody tr");
  assertEqual(rows.length, 2, "the separator row is not a body row");
  assertEqual(Array.prototype.map.call(rows[1].querySelectorAll("td"), function (t) { return t.textContent; }),
              ["DESK", "2"]);
  assertEqual(rows[0].querySelector("td strong").textContent, "7");
  assertEqual(rows[0].getAttribute("data-anim"), "line");
  assertEqual(say.lastChild.textContent, "Después.");
  assert(say.textContent.indexOf("|") < 0 && say.textContent.indexOf("#") < 0, "markup left: " + say.textContent);
});

test("a page step is a browser window over the screen with the page in a sandboxed frame", function () {
  var ep = fixtureEpisode();
  ep.chapters[1].steps.splice(6, 0, {type: "page", title: "vista.html", html: "<p>Vista</p>", source: "real"});
  var c = render(10, ep);
  var ov = c.querySelector(".ws-page");
  assert(ov && !ov.hasAttribute("hidden"), "current page must show");
  assertEqual(ov.getAttribute("data-step"), "6");
  assertEqual(ov.querySelector(".ws-page-url").textContent, "vista.html");
  var frame = ov.querySelector("iframe");
  assertEqual(frame.getAttribute("sandbox"), "allow-scripts");
  assertEqual(frame.getAttribute("srcdoc"), "<p>Vista</p>");
  assert(c.querySelector(".ws-page p") === null, "the page is never parsed into the stage");
  assert(render(11, ep).querySelector(".ws-page").hasAttribute("hidden"), "a past page stays hidden");
});

test("an approve step with a page is the tool's own window: title bar, the page and two native buttons", function () {
  var ep = fixtureEpisode();
  var st = ep.chapters[1].steps[5];
  delete st.lines;
  st.html = "<h1>Crear en PLAT</h1>";
  st.window = "jtk · Jira";
  st.width = 520;
  st.height = 300;
  var ov = render(9, ep).querySelector(".ws-approve");
  assert(ov && !ov.hasAttribute("hidden"), "current approve must show");
  var win = ov.querySelector(".ws-approve-win.ws-approve-real");
  assert(win, "no real window");
  assertEqual(win.querySelector(".ws-approve-bar-title").textContent, "jtk · Jira");
  assertEqual(win.style.width, "520px");
  var frame = win.querySelector("iframe");
  assertEqual(frame.getAttribute("sandbox"), "");
  assertEqual(frame.getAttribute("srcdoc"), "<h1>Crear en PLAT</h1>");
  assertEqual(frame.style.height, "300px");
  assertEqual(Array.prototype.map.call(win.querySelectorAll(".ws-btn"), function (b) { return b.textContent; }),
              ["Cancelar", "Apruebo 2"]);
  assert(win.querySelector(".ws-approve-lines") === null && ov.querySelector("h1") === null, "no invented box");
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

test("an episode can name the model its chat shows", function () {
  var ep = fixtureEpisode();
  ep.workspace.model = "GPT-5.6 Terra";
  [4, 10, 12].forEach(function (i) {
    var c = render(i, ep);
    assert(c.textContent.indexOf("GPT-5.6 Terra") >= 0, "model missing at " + i);
    assert(c.textContent.indexOf("Sonnet 5.5") < 0, "default model still shown at " + i);
  });
});

test("claude-code uses the transcript layout", function () {
  var c = render(15);
  var root = c.querySelector(".ws-claude-code");
  assert(root, "not claude-code");
  var t = root.textContent;
  assert(t.indexOf("› Hola") >= 0, "ask line");
  assert(t.indexOf("⏺ Bash(ls)") >= 0, "bash line");
  assert(t.indexOf("⎿ a") >= 0, "output line");
  assert(t.indexOf("⏺ Listo") >= 0 || root.querySelector('[data-step="2"]').textContent.indexOf("⏺") >= 0, "say");
  assert(t.indexOf("✻ Worked for 3s") >= 0, "worked line");
});

test("claude-code shows a command the person types with ! as bash mode", function () {
  var ep = fixtureEpisode();
  ep.chapters[2].steps[1]["in"] = "zsh";
  var c = render(15, ep);
  var st = c.querySelector('[data-step="1"]');
  assert(st.classList.contains("ws-cc-bang"), "bang class: " + st.className);
  assert(st.textContent.indexOf("! ls") >= 0, "bang line: " + st.textContent);
  assert(st.textContent.indexOf("Bash(") < 0, "not the agent's Bash call");
  assertEqual(st.querySelector('[data-anim="type"]').textContent, "ls");
  assert(st.querySelector('[data-anim="line"]').textContent.indexOf("⎿ a") >= 0, "output under ⎿");
});

test("claude-code shows a Skill tool as loaded, like Claude Code", function () {
  var ep = fixtureEpisode();
  ep.chapters[2].steps.splice(1, 0, {type: "tool", label: "Skill(demo-skill)", source: "inferido"},
                              {type: "tool", label: "Ran · x", source: "inferido"});
  var c = render(17, ep);
  var st = c.querySelector('[data-step="1"]');
  assert(st.textContent.indexOf("⏺ Skill(demo-skill)") >= 0, "skill line: " + st.textContent);
  assert(st.textContent.indexOf("Successfully loaded skill") >= 0, "loaded line: " + st.textContent);
  assertEqual(st.getAttribute("data-anim"), "node", "the wrapper carries the hook");
  assertEqual(st.querySelectorAll("[data-anim]").length, 0, "no inner hook");
  assertEqual(st.querySelectorAll("[data-step]").length, 0, "no inner step");
  var other = c.querySelector('[data-step="2"]');
  assert(other.textContent.indexOf("Ran · x") >= 0, "the other tool: " + other.textContent);
  assert(other.textContent.indexOf("Successfully loaded skill") < 0, "only Skill tools");
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
    if (screen === "cursor-agent") {
      assert(q(3, ' [data-anim="node"]').textContent.indexOf("python3 ia.py status") >= 0, screen + " term node");
    } else {
      assertEqual(q(3, ' [data-anim="type"]').textContent, "python3 ia.py status", screen + " term cmd");
    }
    assert(c.querySelectorAll('[data-step="4"] [data-anim="line"]').length >= 3, screen + " say lines");
    var ov = q(5, "");
    assert(ov.getAttribute("data-anim") === "node" && !ov.hasAttribute("hidden"), screen + " approve");
    var idle = c.querySelectorAll('[data-anim="idle"]');
    if (screen === "terminal" || screen === "cursor-full") {
      assertEqual(idle.length, 1, screen + " idle prompt count");
      assert(!idle[0].hasAttribute("data-step"), screen + " idle is not a step");
      assert(idle[0].querySelector(".ws-prompt") && idle[0].textContent.indexOf("❯") >= 0, screen + " idle content");
      var flow = idle[0].parentNode;
      assert(flow.lastChild === idle[0], screen + " idle is last");
    } else {
      assertEqual(idle.length, 0, screen + " has no idle prompt");
    }
  });
});

test("the prompt carries the folder, house and clock icons as inline SVG", function () {
  var c = render(1);
  var p = c.querySelector('[data-step="0"] .ws-prompt');
  var SVG = "http://www.w3.org/2000/svg";
  [["folder", ".ws-seg-path"], ["house", ".ws-seg-sys"], ["clock", ".ws-seg-time"]].forEach(function (x) {
    var ico = p.querySelector(x[1] + " svg.ws-ico-" + x[0]);
    assert(ico, x[0] + " icon missing in " + x[1]);
    assertEqual(ico.namespaceURI, SVG, x[0] + " namespace");
    assert(ico.querySelector("path, circle"), x[0] + " has no shape");
  });
  assertEqual(p.querySelectorAll("svg").length, 3, "exactly three icons");
  assert(p.textContent.indexOf("▭") < 0 && p.textContent.indexOf("⌂") < 0 && p.textContent.indexOf("◷") < 0,
         "no text glyph stand-ins left");
});

test("the prompt time is HH:MM:SS from the injected clock", function () {
  var c = render(1);
  var times = c.querySelectorAll(".ws-seg-time .ws-time");
  assertEqual(times.length, 2, "step prompt and idle prompt");
  for (var i = 0; i < times.length; i++) assertEqual(times[i].textContent, "09:05:07");
  assertEqual(c.querySelector(".ws-seg-time").textContent, "at 09:05:07");
  var saved = Render.now;
  Render.now = function () { return new Date(2026, 0, 2, 23, 59, 3); };
  try {
    assertEqual(render(1).querySelector(".ws-time").textContent, "23:59:03");
  } finally {
    Render.now = saved;
  }
  assertEqual(Render.clockText(new Date(2026, 0, 1, 0, 0, 0)), "00:00:00");
});

test("the last path component of the prompt is bold", function () {
  var ep = fixtureEpisode();
  ep.chapters[0].steps[0].cwd = "~/CurrentCode/PRISM";
  var seg = render(1, ep).querySelector('[data-step="0"] .ws-seg-path');
  assertEqual(seg.textContent, "~/CurrentCode/PRISM");
  var b = seg.querySelectorAll("b");
  assertEqual(b.length, 1, "one bold run");
  assertEqual(b[0].textContent, "PRISM");
  ep.chapters[0].steps[0].cwd = "~";
  seg = render(1, ep).querySelector('[data-step="0"] .ws-seg-path');
  assertEqual(seg.querySelector("b").textContent, "~", "a bare ~ is its own last component");
});

// ---- callouts: visual cues on the current step ----
function calloutEpisode() {
  var ep = fixtureEpisode();
  var caso = ep.chapters[1].steps;
  caso[3].callouts = [{kind: "box", match: "baseline: done", text: "el paso 0 cerró"}];   // zsh term, index 7
  caso[4].callouts = [{kind: "note", text: "Fijate en **la base**"},                       // say, index 8
                      {kind: "underline", match: "a1b2c3d"}];
  ep.chapters[0].steps[0].callouts = [{kind: "underline", match: "listo"}];               // terminal term, index 1
  ep.chapters[2].steps[1].callouts = [{kind: "box", match: "b"}];                          // claude-code term, index 13
  return ep;
}

test("a note callout shows its text on the current step only", function () {
  var ep = calloutEpisode();
  var c = render(8, ep);
  var note = c.querySelector('[data-step="4"] .ws-co-note');
  assert(note, "no note on the current say");
  assert(note.textContent.indexOf("Fijate en la base") >= 0, "note text: " + note.textContent);
  assert(note.querySelector("strong"), "note keeps inline markdown");
  var later = render(9, ep);
  assertEqual(later.querySelectorAll(".ws-co-note").length, 0);
});

test("box and underline wrap exactly the matched text of the current step", function () {
  var ep = calloutEpisode();
  var c = render(8, ep);
  var u = c.querySelector('[data-step="4"] .ws-co-underline');
  assert(u, "no underline");
  assertEqual(u.textContent, "a1b2c3d");
  var b = render(7, ep).querySelector('[data-step="3"] .ws-co-box');
  assert(b, "no box on the zsh term");
  assertEqual(b.textContent, "baseline: done");
  var tag = render(7, ep).querySelector('[data-step="3"] .ws-co-tag');
  assert(tag && tag.textContent.indexOf("el paso 0 cerró") >= 0, "box text shows as a tag");
  assertEqual(render(8, ep).querySelectorAll(".ws-co-box").length, 0);
});

test("callouts work on the terminal and claude-code screens", function () {
  var ep = calloutEpisode();
  var t = render(1, ep).querySelector('[data-step="0"] .ws-co-underline');
  assert(t && t.textContent === "listo", "terminal underline");
  var cc = render(13, ep).querySelector('[data-step="1"] .ws-co-box');
  assert(cc && cc.textContent === "b", "claude-code box");
});

test("a callout whose match is missing renders nothing and does not throw", function () {
  var ep = fixtureEpisode();
  ep.chapters[1].steps[4].callouts = [{kind: "box", match: "no está"}];
  var c = render(8, ep);
  assertEqual(c.querySelectorAll(".ws-co-box").length, 0);
  assert(c.querySelector('[data-step="4"]').textContent.indexOf("a1b2c3d") >= 0, "say intact");
});

test("worked shows minutes and hours once a step runs that long", function () {
  var ep = fixtureEpisode();
  var steps = ep.chapters[1].steps;
  steps[1].seconds = 802;
  assert(render(5, ep).textContent.indexOf("Worked for 13m 22s") >= 0, "minutes: " + render(5, ep).textContent);
  steps[1].seconds = 6620;
  assert(render(5, ep).textContent.indexOf("Worked for 1h 50m 20s") >= 0, "hours");
  steps[1].seconds = 42;
  assert(render(5, ep).textContent.indexOf("Worked for 42s") >= 0, "seconds stay as they were");
});

// ---- colour: SGR codes captured from a `color: true` term step ----
function colorEpisode(out, callouts) {
  var ep = fixtureEpisode();
  var st = ep.chapters[0].steps[0];
  st.color = true;
  st.out = out;
  if (callouts) st.callouts = callouts;
  return ep;
}

test("SGR codes in term output render as coloured runs, never as escape text", function () {
  var ep = colorEpisode(["Disponible \x1b[1;38;2;62;152;255m$115.15\x1b[0m de $200"]);
  var line = render(1, ep).querySelector('[data-step="0"] .ws-out');
  assertEqual(line.textContent, "Disponible $115.15 de $200");
  var spans = line.querySelectorAll("span");
  assertEqual(spans.length, 1);
  assertEqual(spans[0].textContent, "$115.15");
  assertEqual(spans[0].style.color, "rgb(62, 152, 255)");
  assertEqual(spans[0].style.fontWeight, "700");
});

test("16, 256 and background colours, and resets", function () {
  var ep = colorEpisode(["\x1b[31ma\x1b[39m b \x1b[38;5;196mc\x1b[0m \x1b[48;2;1;2;3md\x1b[49m e \x1b[38;5;244mf\x1b[m"]);
  var line = render(1, ep).querySelector('[data-step="0"] .ws-out');
  assertEqual(line.textContent, "a b c d e f");
  var s = line.querySelectorAll("span");
  assertEqual(s.length, 4);
  assert(s[0].style.color, "basic red has a colour");
  assertEqual(s[1].style.color, "rgb(255, 0, 0)");
  assertEqual(s[2].style.backgroundColor, "rgb(1, 2, 3)");
  assertEqual(s[3].style.color, "rgb(128, 128, 128)");
});

test("a plain output line stays one text node", function () {
  var line = render(1, fixtureEpisode()).querySelector('[data-step="0"] .ws-out');
  assertEqual(line.childNodes.length, 1);
  assertEqual(line.firstChild.nodeType, 3);
});

test("a callout matches inside a coloured run", function () {
  var ep = colorEpisode(["Disponible \x1b[32m$115.15\x1b[0m de $200"], [{kind: "underline", match: "$115.15"}]);
  var u = render(1, ep).querySelector('[data-step="0"] .ws-co-underline');
  assert(u, "no underline");
  assertEqual(u.textContent, "$115.15");
});

test("colour also renders in the agent's Ran block and in Claude Code", function () {
  var ep = fixtureEpisode();
  ep.chapters[2].steps[1].out = ["\x1b[32mok\x1b[0m"];
  var cc = render(13, ep).querySelector('[data-step="1"]');
  assertEqual(cc.textContent.indexOf("\x1b"), -1);
  assert(cc.querySelector("span[style]"), "claude-code output has a coloured run");
});
