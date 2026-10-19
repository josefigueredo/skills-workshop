// Animate tests. A fake scheduler collects (fn, ms); tests run the queue in order and
// sum the ms, so no real time passes. The harness loads no CSS: visibility is checked
// through the inline styles animate.js sets.
function animEpisode() {
  return {
    id: "demo", series: "cursor", order: 1, title: "demo-skill",
    skill: {repo: "demo-skill", commit: "abc1234", date: "2026-10-19"},
    workspace: {repo: "mi-servicio", files: ["api", "README.md"], chats: []},
    chapters: [
      {id: "instalar", title: "Instalar", screen: "terminal",
       steps: [
         {type: "term", cmd: "./install.sh", out: ["listo"], source: "real", cwd: "~"},
         {type: "say", md: "Texto suelto", source: "inferido", pause: true},
         {type: "term", cmd: "", out: [], source: "inferido"}
       ]},
      {id: "caso", title: "Caso principal", screen: "cursor-full",
       steps: [
         {type: "ask", text: "Auditá", source: "inferido"},
         {type: "worked", seconds: 42, source: "inferido"},
         {type: "tool", label: "Ran · ia.py init", source: "inferido"},
         {type: "term", cmd: "ia status", out: ["a", "b", "c"], source: "inferido", in: "zsh"},
         {type: "say", md: "#### Hecho\nUno **dos**.\n- a\n- b", source: "inferido"},
         {type: "approve", title: "Crear", lines: ["X-1"], button: "Apruebo 1", source: "inferido"},
         {type: "say", md: "", source: "inferido"}
       ]},
      {id: "agente", title: "Agente", screen: "cursor-agent",
       steps: [
         {type: "term", cmd: "ls", out: ["x", "y"], source: "inferido"}
       ]},
      {id: "cc", title: "En Claude Code", screen: "claude-code",
       steps: [
         {type: "ask", text: "Hola", source: "inferido"},
         {type: "term", cmd: "ls", out: ["a", "b"], source: "inferido"},
         {type: "say", md: "Listo", source: "inferido"}
       ]}
    ]
  };
}
// Flattened: 0 card instalar, 1 term, 2 say(pause), 3 empty term, 4 card caso, 5 ask,
// 6 worked, 7 tool, 8 term, 9 say, 10 approve, 11 empty say, 12 card agente, 13 term,
// 14 card cc, 15 ask, 16 term, 17 say
var LAST = 17;

function fakeClock() {
  var q = [], nextId = 1, clock = {total: 0, calls: 0, cancelled: 0};
  clock.schedule = function (fn, ms) { var id = nextId++; q.push({id: id, fn: fn, ms: ms}); return id; };
  clock.unschedule = function (id) {
    for (var k = 0; k < q.length; k++) if (q[k].id === id) { q.splice(k, 1); clock.cancelled++; return; }
  };
  clock.pending = function () { return q.length; };
  clock.tick = function () {
    var t = q.shift();
    if (!t) return false;
    clock.total += t.ms; clock.calls++;
    t.fn();
    return true;
  };
  clock.ticks = function (n) { for (var k = 0; k < n; k++) clock.tick(); };
  clock.flush = function () { var guard = 0; while (clock.tick()) { if (++guard > 10000) throw new Error("runaway"); } };
  clock.opts = function (speed) {
    return {speed: speed, schedule: clock.schedule, unschedule: clock.unschedule, now: function () { return 0; }};
  };
  return clock;
}

function finalHTML(ep, i) { var c = document.createElement("div"); Render.step(c, ep, i); return c.innerHTML; }
function play(i, speed) {
  var ep = animEpisode(), c = document.createElement("div"), clock = fakeClock();
  var run = Animate.run(c, ep, i, clock.opts(speed || 1));
  return {ep: ep, c: c, clock: clock, run: run};
}
function shown(n) { return n.style.display !== "none" && n.style.opacity !== "0"; }
function q(c, sel) { return c.querySelector(sel); }
function all(c, sel) { return Array.prototype.slice.call(c.querySelectorAll(sel)); }

test("after every tick the DOM equals Render.step(index), for every index", function () {
  var ep = animEpisode();
  for (var i = 0; i <= LAST; i++) {
    var p = play(i);
    p.clock.flush();
    assertEqual(p.c.innerHTML, finalHTML(ep, i), "index " + i);
  }
});

test("done resolves after the last tick", function () {
  var p = play(1);
  var resolved = false;
  p.run.done.then(function () { resolved = true; });
  p.clock.flush();
  return p.run.done.then(function () { assert(resolved, "done did not resolve"); });
});

test("cancel midway yields the final DOM, clears the timer and ignores stale callbacks", function () {
  var ep = animEpisode();
  [1, 5, 8, 9, 13, 16].forEach(function (i) {
    var p = play(i);
    p.clock.ticks(2);
    assert(p.c.innerHTML !== finalHTML(ep, i), "index " + i + " already final after 2 ticks");
    var before = p.clock.pending();
    p.run.cancel();
    assertEqual(p.c.innerHTML, finalHTML(ep, i), "after cancel " + i);
    assert(p.clock.cancelled === before, "pending timer not unscheduled at " + i);
    p.clock.flush();
    assertEqual(p.c.innerHTML, finalHTML(ep, i), "after stale flush " + i);
  });
  var last = play(8);
  last.run.cancel();
  return last.run.done;
});

test("terminal term types the command char by char, then shows lines one by one", function () {
  var p = play(1);
  var cmd = q(p.c, '[data-step="0"] [data-anim="type"]');
  var line = q(p.c, '[data-step="0"] [data-anim="line"]');
  assertEqual(cmd.textContent, "");
  assert(!shown(line), "output visible before typing");
  p.clock.ticks(3);
  assertEqual(cmd.textContent, "./i");
  assertEqual(p.clock.total, 3 * 28);
  p.clock.ticks(9);
  assertEqual(cmd.textContent, "./install.sh");
  assert(!shown(line), "output visible right after typing");
  p.clock.tick();
  assert(shown(line), "output line not shown");
});

test("a chat-placed term on cursor-full leaves the zsh idle prompt visible throughout", function () {
  var ep = animEpisode();
  ep.chapters[1].steps.push({type: "term", cmd: "ia status", out: ["a", "b"], source: "inferido"});
  // chapter card index 4, steps 5..11, the new chat-placed term is step 7 -> index 12 shifts later chapters
  var idx = Nav.flatten(ep).findIndex(function (e) { return e.chapter === 1 && e.step === 7; });
  var c = document.createElement("div"), clock = fakeClock();
  Animate.run(c, ep, idx, clock.opts(1));
  assert(q(c, '[data-anim="idle"]'), "no idle prompt rendered on cursor-full");
  assert(shown(q(c, '[data-anim="idle"]')), "idle hidden at start");
  while (clock.pending()) {
    clock.tick();
    assert(shown(q(c, '[data-anim="idle"]')), "idle hidden mid-run");
  }
  assert(shown(q(c, '[data-anim="idle"]')), "idle hidden at the end");
});

test("the idle prompt is hidden while a term step animates and back at the end", function () {
  var p = play(1);
  assert(!shown(q(p.c, '[data-anim="idle"]')), "idle visible during term");
  p.clock.flush();
  assert(shown(q(p.c, '[data-anim="idle"]')), "idle missing at the end");
  var a = play(5);
  assert(shown(q(a.c, '[data-anim="idle"]')), "a non-term step must not hide idle");
});

test("previous steps stay visible; only the current step's hooks are hidden", function () {
  var p = play(9);
  all(p.c, '[data-step]:not([data-step="4"]) [data-anim]').forEach(function (n) {
    assert(shown(n), "an earlier step lost a part: " + n.textContent);
  });
  all(p.c, '[data-step]:not([data-step="4"])').forEach(function (n) { assert(shown(n), "earlier root hidden"); });
  var lines = all(p.c, '[data-step="4"] [data-anim="line"]');
  assertEqual(lines.length, 4);
  lines.forEach(function (n) { assert(!shown(n), "say line visible before its tick"); });
  p.clock.ticks(2);
  assertEqual(lines.map(shown), [true, true, false, false]);
});

test("tool and worked appear whole after 250 ms (root is the hook)", function () {
  [6, 7].forEach(function (i) {
    var p = play(i);
    var root = q(p.c, '[data-step="' + (i - 5) + '"]');
    assert(!shown(root), "root visible at start for " + i);
    p.clock.tick();
    assertEqual(p.clock.total, 250);
    assert(shown(root), "root not shown after one tick for " + i);
    assertEqual(p.clock.pending(), 0);
  });
});

test("approve fades in through opacity on the scheduler", function () {
  var p = play(10);
  var ov = q(p.c, '[data-step="5"]');
  assertEqual(ov.style.opacity, "0");
  p.clock.tick();
  assert(ov.style.opacity !== "0", "approve still transparent");
  assertEqual(p.clock.total, 250);
});

test("a card fades in with a single scheduled reveal and no typing", function () {
  var p = play(4);
  var card = q(p.c, ".ws-card");
  assertEqual(card.style.opacity, "0");
  assertEqual(p.clock.pending(), 1);
  p.clock.flush();
  assertEqual(p.clock.calls, 1);
  assertEqual(p.clock.total, 250);
  assert(q(p.c, ".ws-card").style.opacity !== "0", "card still transparent");
});

test("an agent term on cursor-full plays as a Ran chip plus its lines", function () {
  var ep = animEpisode();
  delete ep.chapters[1].steps[3].in;
  var c = document.createElement("div"), clock = fakeClock();
  Animate.run(c, ep, 8, clock.opts(1));
  clock.flush();
  assertEqual(clock.total, 250 + 3 * 120);
  assertEqual(clock.calls, 4);
  assertEqual(Animate.stepDuration(ep, 8, 1), 250 + 3 * 120);
});

test("exact durations and call counts per screen", function () {
  var cases = [
    [1, 12 * 28 + 120, 13],      // terminal term: 12 chars + 1 line
    [2, 120, 1],                 // terminal say: 1 paragraph
    [5, 6 * 28, 6],              // cursor ask "Auditá"
    [8, 9 * 28 + 3 * 120, 12],   // cursor-full term in zsh
    [9, 4 * 120, 4],             // say: heading, paragraph, 2 list items
    [13, 250 + 2 * 120, 3],      // cursor-agent term: Ran chip + 2 lines
    [15, 4 * 28, 4],             // claude-code ask "Hola"
    [16, 250 + 2 * 120, 3],      // claude-code Bash(ls) + 2 lines
    [17, 120, 1]
  ];
  cases.forEach(function (k) {
    var p = play(k[0]);
    p.clock.flush();
    assertEqual(p.clock.total, k[1], "ms at " + k[0]);
    assertEqual(p.clock.calls, k[2], "calls at " + k[0]);
  });
});

test("a step with no hooks schedules nothing, renders final and resolves", function () {
  var ep = animEpisode();
  [3, 11].forEach(function (i) {
    var p = play(i);
    assertEqual(p.clock.pending(), 0);
    assertEqual(p.c.innerHTML, finalHTML(ep, i));
    assertEqual(Animate.stepDuration(ep, i, 1), 0);
  });
  return play(3).run.done;
});

test("characters are counted by code point", function () {
  var ep = animEpisode();
  ep.chapters[3].steps[0].text = "a😀b";
  var c = document.createElement("div"), clock = fakeClock();
  Animate.run(c, ep, 15, clock.opts(1));
  clock.ticks(2);
  assertEqual(q(c, '[data-anim="type"]').textContent, "a😀");
  clock.flush();
  assertEqual(clock.total, 3 * 28);
  assertEqual(Animate.stepDuration(ep, 15, 1), 3 * 28);
});

test("speed 2 halves the scheduled ms", function () {
  for (var i = 0; i <= LAST; i++) {
    var one = play(i, 1), two = play(i, 2);
    one.clock.flush(); two.clock.flush();
    assertEqual(two.clock.total, one.clock.total / 2, "index " + i);
    assertEqual(two.clock.calls, one.clock.calls, "calls at " + i);
  }
});

test("speed is clamped to a positive minimum", function () {
  var ep = animEpisode();
  assertEqual(Animate.stepDuration(ep, 6, 0), 250 / 0.1);
  assertEqual(Animate.stepDuration(ep, 6, -3), 250 / 0.1);
  assertEqual(Animate.autoplay(ep, 5, 0).delay, 900 / 0.1);
});

test("stepDuration equals the ms the scheduler saw, for every index and speed", function () {
  var ep = animEpisode();
  [1, 2, 0.5].forEach(function (s) {
    for (var i = 0; i <= LAST; i++) {
      var p = play(i, s);
      p.clock.flush();
      assertEqual(Animate.stepDuration(ep, i, s), p.clock.total, "index " + i + " speed " + s);
    }
  });
});

test("autoplay stops at chapter end, after pause and at the episode end", function () {
  var ep = animEpisode();
  assertEqual(Animate.autoplay(ep, 0, 1), {stop: false, delay: 900}, "card followed by steps");
  assertEqual(Animate.autoplay(ep, 1, 1), {stop: false, delay: 900});
  assertEqual(Animate.autoplay(ep, 2, 1).stop, true, "pause");
  assertEqual(Animate.autoplay(ep, 3, 1).stop, true, "chapter end");
  assertEqual(Animate.autoplay(ep, 11, 1).stop, true, "chapter end");
  assertEqual(Animate.autoplay(ep, 13, 1).stop, true, "single-step chapter end");
  assertEqual(Animate.autoplay(ep, LAST, 1).stop, true, "episode end");
  assertEqual(Animate.autoplay(ep, 5, 2), {stop: false, delay: 450});
  var empty = animEpisode();
  empty.chapters[2].steps = [];
  assertEqual(Animate.autoplay(empty, 12, 1).stop, true, "card of an empty chapter");
});

test("episodeDuration sums step durations plus delays, none after a stop", function () {
  var ep = animEpisode();
  var d = Animate.episodeDuration(ep, 1);
  assertEqual(d.chapters.map(function (c) { return c.id; }), ["instalar", "caso", "agente", "cc"]);
  var ranges = [[0, 3], [4, 11], [12, 13], [14, 17]];
  var total = 0;
  ranges.forEach(function (r, k) {
    var ms = 0;
    for (var i = r[0]; i <= r[1]; i++) {
      ms += Animate.stepDuration(ep, i, 1);
      var a = Animate.autoplay(ep, i, 1);
      if (!a.stop) ms += a.delay;
    }
    assertEqual(d.chapters[k].ms, ms, "chapter " + k);
    total += ms;
  });
  assertEqual(d.total, total);
  // chapter "agente": card 250 + delay 900 + term 490, no delay after the last step.
  assertEqual(d.chapters[2].ms, 250 + 900 + 490);
  assertEqual(Animate.episodeDuration(ep, 2).total, total / 2);
});

test("a second run on the same container cancels the first and ends in its own final state", function () {
  var ep = animEpisode(), c = document.createElement("div");
  var ca = fakeClock(), cb = fakeClock();
  var a = Animate.run(c, ep, 1, ca.opts(1));
  ca.ticks(2);
  var b = Animate.run(c, ep, 16, cb.opts(1));
  assertEqual(ca.pending(), 0, "first run's timer still pending");
  ca.flush(); cb.flush();
  assertEqual(c.innerHTML, finalHTML(ep, 16));
  return Promise.all([a.done, b.done]);
});

test("the first run's leftover callbacks leave the second run's partial state untouched", function () {
  var ep = animEpisode(), c = document.createElement("div");
  var ca = fakeClock(), cb = fakeClock(), stale = [];
  // Record every callback the first run hands its scheduler, unscheduled or not.
  Animate.run(c, ep, 1, {speed: 1, unschedule: ca.unschedule,
                         schedule: function (fn, ms) { stale.push(fn); return ca.schedule(fn, ms); }});
  ca.ticks(2);
  Animate.run(c, ep, 16, cb.opts(1));
  cb.ticks(2);
  var partial = c.innerHTML;
  assert(partial !== finalHTML(ep, 16), "second run already final");
  stale.forEach(function (fn) { fn(); });
  ca.flush();
  assertEqual(c.innerHTML, partial);
  cb.flush();
  assertEqual(c.innerHTML, finalHTML(ep, 16));
});

test("Animate.stop cancels without rendering and no callback mutates the container after it", function () {
  var ep = animEpisode(), c = document.createElement("div"), clock = fakeClock(), fired = [];
  var r = Animate.run(c, ep, 9, {speed: 1, unschedule: clock.unschedule,
                                 schedule: function (fn, ms) { fired.push(fn); return clock.schedule(fn, ms); }});
  clock.ticks(1);
  Animate.stop(c);
  var snap = c.innerHTML;
  assert(snap !== finalHTML(ep, 9), "stop rendered the final state");
  assertEqual(clock.pending(), 0);
  fired.forEach(function (fn) { fn(); });
  assertEqual(c.innerHTML, snap);
  Animate.stop(c);  // idempotent, nothing active
  return r.done;
});

test("a reveal that throws still ends in the final state and resolves done", function () {
  var ep = animEpisode(), c = document.createElement("div"), clock = fakeClock();
  var r = Animate.run(c, ep, 1, clock.opts(1));
  var typed = q(c, '[data-anim="type"]');
  Object.defineProperty(typed, "textContent", {set: function () { throw new Error("boom"); }, get: function () { return ""; }});
  var origError = console.error;
  console.error = function () {};
  try { clock.tick(); } finally { console.error = origError; }
  assertEqual(clock.pending(), 0);
  assertEqual(c.innerHTML, finalHTML(ep, 1));
  return r.done;
});
