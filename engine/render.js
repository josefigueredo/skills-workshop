// Static render of the stage: Render.step(container, episode, index) replaces the
// container's content with the FINISHED state of global index `index` (see nav.js).
// Pure function of (episode, index): nothing is kept between calls.
//
// Screens are laid out for a fixed 1600x900 canvas (.ws-screen); the stage scales it.
// All episode text goes through textContent / createTextNode; `say` markdown is parsed
// into DOM nodes, never assigned as HTML.
//
// Animation hooks (for animate.js, which renders the finished state, hides, reveals):
//   data-step="<j>"      on the root node of every applied step (j = index of the step
//                        inside its chapter). Nothing else carries data-step. Steps may
//                        live in different areas (a cursor-full term with `in: "zsh"`
//                        sits in the zsh panel, approve is an overlay at the end of the
//                        screen root), so document order is not step order: select by value.
//   data-anim="type"     the element holding exactly the text that gets typed
//                        (ask text, term command).
//   data-anim="line"     an output line, a say paragraph / heading / list item; revealed
//                        one at a time.
//   data-anim="node"     tool, worked and approve nodes (and the "▸ Ran · cmd" chip and
//                        the "⏺ Bash(cmd)" line); revealed whole.
//   hidden               an approve step that is not the current index keeps its node
//                        (so the step count holds) but is hidden: the window closed.
//   data-anim="idle"     the wrapper of the waiting prompt (prompt line + "❯ █") at the
//                        end of the terminal and of the cursor-full zsh panel. It is not
//                        a step: hide it while a term step animates, show it at the end.
//
// Prompt clock: every prompt shows Render.now() as HH:MM:SS (local time) in a
// .ws-time span. Render.now defaults to `new Date()`; tests and render-preview replace it
// with a fixed date so the output stays deterministic. The stage refreshes only the idle
// prompt's .ws-time every second (Stage.tickClock); steps are never re-rendered for it.
// Prompt icons (folder, house, clock) are inline SVG built with createElementNS.
// Unmarked descendants of a step root appear with the root; hooks inside one root are
// revealed in document order. Chapter cards carry no hooks and appear whole.
//
// Term placement on cursor-full: by default a term step is the agent's command and
// renders in the conversation exactly as on cursor-agent ("▸ Ran · cmd" chip + output
// block). With `in: "zsh"` it is a command the person types and renders in the
// integrated zsh (prompt, typed command, output lines).
// The first chapter card also shows the episode pitch («Le decís al agente…» /
// «Y la skill…») under its title; it is part of the card, not a separate index.
var Render = (function () {
  var USER = "Persona del equipo";
  var TEAM = "Equipo";
  var MODEL = "Sonnet 5.5";
  var BRANCH = "main";

  // ---- DOM helpers (text only) ----
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function add(parent) {
    for (var i = 1; i < arguments.length; i++) {
      if (arguments[i]) parent.appendChild(arguments[i]);
    }
    return parent;
  }
  function stepNode(tag, cls, j, anim) {
    var n = el(tag, cls);
    n.setAttribute("data-step", String(j));
    if (anim) n.setAttribute("data-anim", anim);
    return n;
  }
  function anim(node, kind) { node.setAttribute("data-anim", kind); return node; }
  function dots() {
    return add(el("div", "ws-dots"), el("i", "ws-dot ws-dot-r"), el("i", "ws-dot ws-dot-y"),
               el("i", "ws-dot ws-dot-g"));
  }
  // A bottom-anchored area: short content sits on top, long content shows its newest part.
  function scroller(cls) {
    var outer = el("div", "ws-scroll " + cls);
    var flow = el("div", "ws-flow");
    outer.appendChild(flow);
    return {outer: outer, flow: flow};
  }

  // ---- tiny markdown: **b**, `code`, "- " lists, "#### " heading, blank line = paragraph ----
  function inline(parent, text) {
    String(text).split(/(\*\*[^*]+?\*\*|`[^`]+`)/).forEach(function (part) {
      if (!part) return;
      if (/^\*\*[^*]+?\*\*$/.test(part)) parent.appendChild(el("strong", null, part.slice(2, -2)));
      else if (/^`[^`]+`$/.test(part)) parent.appendChild(el("code", null, part.slice(1, -1)));
      else parent.appendChild(document.createTextNode(part));
    });
    return parent;
  }
  function markdown(md) {
    var frag = document.createDocumentFragment();
    var para = [], list = null;
    function flushPara() {
      if (para.length) frag.appendChild(anim(inline(el("p"), para.join(" ")), "line"));
      para = [];
    }
    String(md || "").split("\n").forEach(function (raw) {
      var line = raw.replace(/\s+$/, "");
      if (/^- /.test(line)) {
        flushPara();
        if (!list) { list = el("ul"); frag.appendChild(list); }
        list.appendChild(anim(inline(el("li"), line.slice(2)), "line"));
        return;
      }
      list = null;
      if (/^#### /.test(line)) {
        flushPara();
        frag.appendChild(anim(inline(el("h4"), line.slice(5)), "line"));
      } else if (!line) {
        flushPara();
      } else {
        para.push(line);
      }
    });
    flushPara();
    return frag;
  }

  // ---- shared pieces ----
  function workedText(st) { return "Worked for " + (st.seconds || 0) + "s"; }
  function inRepo(cwd, repo) {
    var home = "~/" + repo;
    return cwd === home || cwd.indexOf(home + "/") === 0;
  }
  // ---- prompt clock and icons ----
  function pad2(n) { return (n < 10 ? "0" : "") + n; }
  function clockText(d) {
    return pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
  }
  function nowText() { return clockText(api.now()); }
  var SVG_NS = "http://www.w3.org/2000/svg";
  // Each icon: list of [tag, attributes] on a 16x16 viewBox; colour comes from currentColor.
  var ICONS = {
    folder: [["path", {d: "M1.5 3.5a1 1 0 0 1 1-1H6l1.5 1.5h6a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z",
                        fill: "currentColor"}]],
    house: [["path", {d: "M8 1.5 15 7.5h-2V14H9.5v-4h-3v4H3V7.5H1z", fill: "currentColor"}]],
    clock: [["circle", {cx: "8", cy: "8", r: "6.25", fill: "none", stroke: "currentColor", "stroke-width": "1.5"}],
            ["path", {d: "M8 4.5V8l2.5 1.5", fill: "none", stroke: "currentColor", "stroke-width": "1.5",
                      "stroke-linecap": "round", "stroke-linejoin": "round"}]]
  };
  function icon(name) {
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", "ws-ico ws-ico-" + name);
    svg.setAttribute("viewBox", "0 0 16 16");
    svg.setAttribute("aria-hidden", "true");
    ICONS[name].forEach(function (spec) {
      var n = document.createElementNS(SVG_NS, spec[0]);
      Object.keys(spec[1]).forEach(function (k) { n.setAttribute(k, spec[1][k]); });
      svg.appendChild(n);
    });
    return svg;
  }
  // "~/a/b" -> "~/a/" + <b>b</b>: the last path component in bold, like the real prompt.
  function pathText(seg, cwd) {
    var s = String(cwd), cut = s.lastIndexOf("/") + 1;
    if (cut > 0 && cut === s.length) cut = s.lastIndexOf("/", s.length - 2) + 1;
    if (cut > 0) seg.appendChild(document.createTextNode(s.slice(0, cut)));
    seg.appendChild(el("b", "ws-path-last", s.slice(cut)));
    return seg;
  }
  // Two-line zsh prompt, first line: apple, folder, branch, dotted fill, system, time.
  function promptLine(cwd, repo) {
    var p = el("div", "ws-prompt");
    add(p, el("span", "ws-seg ws-seg-apple", ""),
        pathText(add(el("span", "ws-seg ws-seg-path"), icon("folder")), cwd));
    if (inRepo(cwd, repo)) p.appendChild(el("span", "ws-seg ws-seg-git", "on ⑂ " + BRANCH));
    add(p, el("span", "ws-seg-fill"),
        add(el("span", "ws-seg ws-seg-sys", "system"), icon("house")),
        add(el("span", "ws-seg ws-seg-time", "at "), el("span", "ws-time", nowText()), icon("clock")));
    return p;
  }
  function cmdLine(cmd) {
    var l = el("div", "ws-cmdline");
    add(l, el("span", "ws-caret-prompt", "❯ "), anim(el("span", "ws-cmd", cmd), "type"));
    return l;
  }
  function idlePrompt(flow, cwd, repo) {
    var l = el("div", "ws-cmdline");
    add(l, el("span", "ws-caret-prompt", "❯ "), el("span", "ws-caret", " "));
    flow.appendChild(add(anim(el("div", "ws-idle"), "idle"), promptLine(cwd, repo), l));
  }
  // A shell term step: prompt, typed command, output lines.
  function shellStep(st, j, cwd, repo) {
    var n = stepNode("div", "ws-shell-step", j);
    add(n, promptLine(cwd, repo), cmdLine(st.cmd));
    (st.out || []).forEach(function (o) { n.appendChild(anim(el("div", "ws-out", o), "line")); });
    return n;
  }
  function approveOverlay(st, j, current) {
    var ov = stepNode("div", "ws-approve", j, "node");
    if (j !== current) ov.setAttribute("hidden", "");
    var win = el("div", "ws-approve-win");
    add(win, el("div", "ws-approve-icon"), el("div", "ws-approve-title", st.title));
    var body = el("div", "ws-approve-lines");
    (st.lines || []).forEach(function (l) { body.appendChild(el("div", "ws-approve-line", l)); });
    var btns = add(el("div", "ws-approve-btns"), el("button", "ws-btn ws-btn-cancel", "Cancelar"),
                   el("button", "ws-btn ws-btn-ok", st.button));
    add(win, body, btns);
    ov.appendChild(win);
    return ov;
  }
  function chapterSteps(ch, last) { return (ch.steps || []).slice(0, last + 1); }

  // ---- card ----
  function card(ep, ci) {
    var ch = ep.chapters[ci];
    var root = el("div", "ws-screen ws-card");
    var inner = el("div", "ws-card-inner");
    add(inner, el("div", "ws-card-kicker", cardSkill(ep) + " · " + (ci + 1) + " de " + ep.chapters.length),
        el("h1", "ws-card-title", ch.title),
        ch.subtitle ? el("p", "ws-card-sub", ch.subtitle) : null,
        ci === 0 ? pitch(ep) : null);
    root.appendChild(inner);
    return root;
  }
  function pitch(ep) {
    var p = ep.pitch;
    if (!p || (!p.ask && !p.does)) return null;
    var box = el("div", "ws-card-pitch");
    if (p.ask) add(box, el("div", "ws-card-pitch-k", "Le decís al agente…"), el("div", "ws-card-pitch-ask", p.ask));
    if (p.does) add(box, el("div", "ws-card-pitch-k", "Y la skill…"), el("div", "ws-card-pitch-does", p.does));
    return box;
  }
  // Kicker name: the episode title (equals skill.repo for skill episodes; episode 0 has
  // its own title).
  function cardSkill(ep) { return ep.title || (ep.skill && ep.skill.repo) || ""; }

  // ---- Cursor (full and agent-only) ----
  function cursorSidebar(ep, ch) {
    var ws = ep.workspace || {};
    var sb = el("div", "ws-sb");
    sb.appendChild(dots());
    ["✎ New Chat", "⌕ Search", "◷ Automations", "⚙ Customize"].forEach(function (t) {
      sb.appendChild(el("div", "ws-sb-nav", t));
    });
    add(sb, el("div", "ws-sb-sec", "Repositories"), el("div", "ws-sb-repo", "▭ " + (ws.repo || "")));
    var cur = add(el("div", "ws-sb-chat ws-on"), el("span", "ws-sb-chat-t", ch.title), el("b", null, "now"));
    sb.appendChild(cur);
    (ws.chats || []).forEach(function (c) {
      sb.appendChild(add(el("div", "ws-sb-chat"), el("span", "ws-sb-chat-t", c.title), el("b", null, c.age)));
    });
    var me = add(el("div", "ws-me"), el("div", "ws-avatar"),
                 add(el("div", "ws-me-t"), el("div", null, USER), el("div", "ws-mut", TEAM)));
    sb.appendChild(me);
    return sb;
  }
  function modelRow() {
    return add(el("div", "ws-ask-row"), el("span", null, "＋"), el("span", null, MODEL + " ⌄"),
               el("span", "ws-send", "↑"));
  }
  function cursorMain(ch) {
    var main = el("div", "ws-main");
    var top = add(el("div", "ws-top"), el("span", null, ch.title), el("span", "ws-top-r", "IDE ↗  ···"));
    var conv = scroller("ws-conv");
    var fu = add(el("div", "ws-followup"), el("span", null, "＋  Send follow-up"),
                 el("span", "ws-followup-m", MODEL + " ⌄"));
    var foot = add(el("div", "ws-foot"), el("span", null, "⑂ " + BRANCH + " ⌄"), el("span", null, "▭ This Mac ⌄"));
    add(main, top, conv.outer, fu, foot);
    return {main: main, flow: conv.flow};
  }
  function cursorRight(ep) {
    var ws = ep.workspace || {};
    var rp = el("div", "ws-rp");
    var tabs = add(el("div", "ws-rp-tabs"), el("span", "ws-tab ws-on", "README.md"), el("span", "ws-tab", "± Changes"),
                   el("span", "ws-tab", "⊕ Browser"), el("span", "ws-tab", "✎ Canvas"), el("span", "ws-tab", "＋"));
    var sub = add(el("div", "ws-rp-sub"), el("span", null, "←  →  README.md"),
                  add(el("span", "ws-rp-sub-r"), el("span", "ws-pill", "Preview"), el("span", null, "Source")));
    var files = el("div", "ws-rp-files");
    var tree = add(el("div", "ws-tree"), el("div", "ws-tree-h", ws.repo || ""));
    (ws.files || []).forEach(function (f) {
      var isDir = String(f).indexOf(".") < 0;
      tree.appendChild(el("div", "ws-tree-i" + (isDir ? " ws-dir" : ""), (isDir ? "▭ " : "◫ ") + f));
    });
    add(files, add(el("div", "ws-preview"), el("h1", null, ws.repo || "")), tree);
    var zsh = el("div", "ws-zsh");
    var zt = add(el("div", "ws-zsh-tabs"), el("span", "ws-pill", "▣ zsh"), el("span", null, "＋"));
    var body = scroller("ws-zsh-body");
    add(zsh, zt, el("div", "ws-zsh-title", "zsh"), body.outer);
    add(rp, tabs, sub, files, zsh);
    return {rp: rp, flow: body.flow};
  }
  function openTabs(ep) {
    var repo = (ep.workspace || {}).repo || "";
    var col = el("div", "ws-opentabs");
    add(col, el("div", "ws-ot-h", "Open Tabs"));
    ["◫ README.md", "⊕ Browser", "✎ Canvas", "▣ zsh"].forEach(function (t) { col.appendChild(el("div", "ws-ot-i", t)); });
    col.appendChild(el("div", "ws-ot-h", "On " + repo));
    col.appendChild(add(el("div", "ws-ot-i"), document.createTextNode("± Changes "), el("span", "ws-plus", "+0")));
    ["⊕ Browser", "▣ 1 Terminal", "◫ Files"].forEach(function (t) { col.appendChild(el("div", "ws-ot-i", t)); });
    return col;
  }
  function cursorScreen(ep, ch, last, full) {
    var repo = (ep.workspace || {}).repo || "";
    var root = el("div", "ws-screen ws-cursor " + (full ? "ws-cursor-full" : "ws-cursor-agent"));
    var m = cursorMain(ch);
    var right = full ? cursorRight(ep) : null;
    add(root, cursorSidebar(ep, ch), m.main, full ? right.rp : openTabs(ep));
    var cwd = "~/" + repo, overlays = [];
    chapterSteps(ch, last).forEach(function (st, j) {
      if (st.type === "ask") {
        var a = stepNode("div", "ws-ask", j);
        add(a, anim(el("div", "ws-ask-text", st.text), "type"), modelRow());
        m.flow.appendChild(a);
      } else if (st.type === "worked") {
        m.flow.appendChild(add(stepNode("div", "ws-worked", j, "node"), document.createTextNode(workedText(st))));
      } else if (st.type === "tool") {
        m.flow.appendChild(add(stepNode("div", "ws-tool", j, "node"), document.createTextNode("▸ " + st.label)));
      } else if (st.type === "say") {
        m.flow.appendChild(add(stepNode("div", "ws-say", j), markdown(st.md)));
      } else if (st.type === "term" && full && st["in"] === "zsh") {
        if (st.cwd) cwd = st.cwd;
        right.flow.appendChild(shellStep(st, j, cwd, repo));
      } else if (st.type === "term") {
        var r = stepNode("div", "ws-ran", j);
        r.appendChild(anim(el("div", "ws-tool", "▸ Ran · " + st.cmd), "node"));
        var out = el("div", "ws-ran-out");
        (st.out || []).forEach(function (o) { out.appendChild(anim(el("div", "ws-out", o), "line")); });
        if (out.firstChild) r.appendChild(out);
        m.flow.appendChild(r);
      } else if (st.type === "approve") {
        overlays.push(approveOverlay(st, j, last));
      }
    });
    if (full) idlePrompt(right.flow, cwd, repo);
    overlays.forEach(function (o) { root.appendChild(o); });
    return root;
  }

  // ---- personal terminal ----
  function termBar(title) {
    return add(el("div", "ws-tbar"), dots(), el("span", "ws-tbar-t", title));
  }
  function terminalScreen(ep, ch, last) {
    var repo = (ep.workspace || {}).repo || "";
    var steps = chapterSteps(ch, last);
    var cwd = "~", overlays = [];
    steps.forEach(function (st) { if (st.type === "term" && st.cwd) cwd = st.cwd; });
    var root = el("div", "ws-screen ws-term-theme ws-terminal");
    var body = scroller("ws-term-body");
    add(root, termBar("▭ " + cwd), body.outer);
    cwd = "~";
    steps.forEach(function (st, j) {
      if (st.type === "term") {
        if (st.cwd) cwd = st.cwd;
        body.flow.appendChild(shellStep(st, j, cwd, repo));
      } else if (st.type === "ask") {
        body.flow.appendChild(add(stepNode("div", "ws-out ws-plain", j), anim(el("span", null, st.text), "type")));
      } else if (st.type === "tool") {
        body.flow.appendChild(add(stepNode("div", "ws-out ws-plain", j, "node"), document.createTextNode(st.label)));
      } else if (st.type === "worked") {
        body.flow.appendChild(add(stepNode("div", "ws-out ws-plain", j, "node"), document.createTextNode(workedText(st))));
      } else if (st.type === "say") {
        body.flow.appendChild(add(stepNode("div", "ws-plain-say", j), markdown(st.md)));
      } else if (st.type === "approve") {
        overlays.push(approveOverlay(st, j, last));
      }
    });
    idlePrompt(body.flow, cwd, repo);
    overlays.forEach(function (o) { root.appendChild(o); });
    return root;
  }

  // ---- Claude Code tab (terminal theme, transcript layout) ----
  function ccLine(gutter, cls) {
    return add(el("div", "ws-cc-line " + (cls || "")), el("span", "ws-cc-g", gutter));
  }
  function claudeCodeScreen(ep, ch, last) {
    var repo = (ep.workspace || {}).repo || "";
    var root = el("div", "ws-screen ws-term-theme ws-claude-code");
    var head = add(el("div", "ws-cc-head"), el("div", "ws-cc-brand", "✻ Claude Code"),
                   el("div", "ws-mut", MODEL + " · ~/" + repo));
    var body = scroller("ws-cc-body");
    body.flow.appendChild(head);
    var input = add(el("div", "ws-cc-input"), el("span", "ws-cc-g", "› "), el("span", "ws-caret", " "));
    add(root, termBar("▭ ~/" + repo + " — claude"), body.outer, input);
    var overlays = [];
    chapterSteps(ch, last).forEach(function (st, j) {
      var n;
      if (st.type === "ask") {
        n = add(stepNode("div", "ws-cc-line ws-cc-ask", j), el("span", "ws-cc-g", "› "), anim(el("span", null, st.text), "type"));
      } else if (st.type === "term" && st["in"] === "zsh") {
        // The person's own `!` command (bash mode): typed by them, not an agent Bash call.
        n = stepNode("div", "ws-cc-block ws-cc-bang", j);
        n.appendChild(add(ccLine("! ", "ws-cc-bang-cmd"), anim(el("span", null, st.cmd), "type")));
        (st.out || []).forEach(function (o, k) {
          n.appendChild(anim(add(ccLine(k === 0 ? "⎿ " : "", "ws-cc-out"), document.createTextNode(o)), "line"));
        });
      } else if (st.type === "term") {
        n = stepNode("div", "ws-cc-block", j);
        n.appendChild(anim(add(ccLine("⏺ ", "ws-cc-tool"), document.createTextNode("Bash(" + st.cmd + ")")), "node"));
        (st.out || []).forEach(function (o, k) {
          n.appendChild(anim(add(ccLine(k === 0 ? "⎿ " : "", "ws-cc-out"), document.createTextNode(o)), "line"));
        });
      } else if (st.type === "tool") {
        n = add(stepNode("div", "ws-cc-line ws-cc-tool", j, "node"), el("span", "ws-cc-g", "⏺ "), document.createTextNode(st.label));
        if (/^Skill\(/.test(st.label)) {  // Claude Code confirms every skill it loads
          var tool = n;
          n = add(stepNode("div", "ws-cc-block", j, "node"), tool);
          tool.removeAttribute("data-step");
          tool.removeAttribute("data-anim");
          n.appendChild(add(ccLine("⎿ ", "ws-cc-out"), document.createTextNode("Successfully loaded skill")));
        }
      } else if (st.type === "say") {
        n = add(stepNode("div", "ws-cc-line ws-cc-say", j), el("span", "ws-cc-g", "⏺ "),
                add(el("div", "ws-cc-md"), markdown(st.md)));
      } else if (st.type === "worked") {
        n = add(stepNode("div", "ws-cc-line ws-cc-worked", j, "node"), el("span", "ws-cc-g", "✻ "),
                document.createTextNode(workedText(st)));
      } else if (st.type === "approve") {
        overlays.push(approveOverlay(st, j, last));
      }
      if (n) body.flow.appendChild(n);
    });
    overlays.forEach(function (o) { root.appendChild(o); });
    return root;
  }

  function build(ep, index) {
    var flat = Nav.flatten(ep);
    if (!flat.length) return el("div", "ws-screen ws-empty");
    var e = flat[Nav.clamp(ep, index)];
    if (e.step === -1) return card(ep, e.chapter);
    var ch = ep.chapters[e.chapter];
    if (ch.screen === "cursor-full") return cursorScreen(ep, ch, e.step, true);
    if (ch.screen === "cursor-agent") return cursorScreen(ep, ch, e.step, false);
    if (ch.screen === "claude-code") return claudeCodeScreen(ep, ch, e.step);
    return terminalScreen(ep, ch, e.step);
  }

  function step(container, ep, index) {
    while (container.firstChild) container.removeChild(container.firstChild);
    container.appendChild(build(ep, index));
    return container.firstChild;
  }

  var api = {step: step, markdown: markdown, clockText: clockText,
             now: function () { return new Date(); }};
  return api;
})();
