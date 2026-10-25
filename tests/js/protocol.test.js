// Protocol tests: the control's pure reducer (Control.reduce) and the stage's message
// handler (Stage.create). No windows, no real timers: the stage gets a fake scheduler
// and the control gets explicit {kind:"tick", now} inputs.
// Fixed prompt clock: every Render.step in this suite shows the same time.
var FIXED_NOW = new Date(2026, 9, 19, 9, 5, 7);
Render.now = function () { return FIXED_NOW; };
function protoEpisodes() {
  return [
    {id: "uno", series: "cursor", order: 1, title: "uno-skill",
     skill: {repo: "uno-skill", commit: "c0ffee1", date: "2026-10-19"},
     workspace: {repo: "mi-servicio", files: ["api"], chats: []},
     chapters: [
       {id: "intro", title: "Qué resuelve", subtitle: "En un minuto", screen: "terminal",
        faq: [{q: "¿Y si no tengo Docker?", a: "Sigue sin e2e."}],
        steps: [
          {type: "term", cmd: "ls", out: ["a"], source: "real", cwd: "~", notes: "NOTA-SECRETA uno"},
          {type: "say", md: "Listo **ya**", source: "inferido", pause: true},
          {type: "tool", label: "Ran · ia.py baseline", source: "inferido"}
        ]},
       {id: "caso", title: "Caso principal", screen: "cursor-full",
        steps: [
          {type: "ask", text: "Auditá esto", source: "inferido", notes: "NOTA-SECRETA dos"},
          {type: "approve", title: "Crear tickets", lines: ["X-1"], button: "Apruebo 1", source: "inferido"}
        ]}
     ]},
    {id: "dos", series: "cursor", order: 2, title: "dos-skill",
     skill: {repo: "dos-skill", commit: "abc1234", date: "2026-10-18"},
     workspace: {repo: "mi-servicio", files: ["api"], chats: []},
     chapters: [{id: "a", title: "A", screen: "terminal",
                 steps: [{type: "term", cmd: "pwd", out: ["~"], source: "inferido"}]}]},
    {id: "tres", series: "claude-code", order: 1, title: "tres-skill",
     skill: {repo: "tres-skill", commit: "def5678", date: "2026-10-17"},
     workspace: {repo: "mi-servicio", files: ["api"], chats: []},
     chapters: [{id: "a", title: "A", screen: "claude-code",
                 steps: [{type: "ask", text: "Hola", source: "inferido"}]}]}
  ];
}
// "uno" flattened: 0 card intro, 1 term, 2 say(pause), 3 tool, 4 card caso, 5 ask, 6 approve.

function feed(state, inputs) {
  var out = [];
  inputs.forEach(function (inp) {
    var r = Control.reduce(state, inp);
    state = r.state;
    out = out.concat(r.outbox);
  });
  return {state: state, outbox: out};
}
function stageMsgs(outbox) {
  return outbox.filter(function (o) { return o.to === "stage"; }).map(function (o) { return o.msg; });
}
function effects(outbox) { return outbox.filter(function (o) { return o.effect; }); }
// A control with the stage open and ready (at time 0).
function live(eps) {
  return feed(Control.init(eps || protoEpisodes()),
              [{kind: "stage-opened", now: 0}, {kind: "message", msg: {type: "ready"}}]).state;
}
function key(k, shift) { return {kind: "key", key: k, shift: !!shift}; }
// The stage's answer once the animation of step i ends: until then → finishes the step instead of moving on.
function done(i) { return {kind: "message", msg: {type: "done-animating", index: i}}; }
function show(index, animate, speed, episode) {
  return {type: "show", episode: episode || "uno", index: index, animate: animate, speed: speed || 1};
}

// ---------------- control: opening the stage ----------------

test("init: first episode, index 0, stage not open yet", function () {
  var s = Control.init(protoEpisodes());
  assertEqual(s.episodeId, "uno");
  assertEqual(s.index, 0);
  assertEqual(s.needsOpen, true);
  assertEqual(s.stageFile, "serie-cursor.html");
  assertEqual(s.playing, false);
});

test("before the stage is open, keys move the index but send nothing", function () {
  var r = feed(Control.init(protoEpisodes()), [key("ArrowRight")]);
  assertEqual(r.state.index, 1);
  assertEqual(stageMsgs(r.outbox), []);
});

test("stage-opened then ready sends the current show (static)", function () {
  var r = feed(Control.init(protoEpisodes()), [key("ArrowRight"), {kind: "stage-opened", now: 0}]);
  assertEqual(r.state.needsOpen, false);
  assertEqual(r.state.stageSeries, "cursor");
  r = feed(r.state, [{kind: "message", msg: {type: "ready"}}]);
  assertEqual(stageMsgs(r.outbox), [show(1, false)]);
});

test("ready resends blackout before show", function () {
  var s = feed(live(), [key("b")]).state;
  var r = feed(s, [{kind: "message", msg: {type: "ready"}}]);
  assertEqual(stageMsgs(r.outbox), [{type: "blackout", on: true}, show(0, false)]);
});

// ---------------- control: keys ----------------

test("→ from a card emits show animate:true", function () {
  var r = feed(live(), [key("ArrowRight")]);
  assertEqual(r.state.index, 1);
  assertEqual(stageMsgs(r.outbox), [show(1, true)]);
});

test("← emits show animate:false", function () {
  var r = feed(live(), [key("ArrowRight"), done(1), key("ArrowRight"), key("ArrowLeft")]);
  assertEqual(r.state.index, 1);
  assertEqual(stageMsgs(r.outbox).pop(), show(1, false));
});

test("← at the start and → at the end send nothing", function () {
  var r = feed(live(), [key("ArrowLeft")]);
  assertEqual(r.outbox, []);
  var s = feed(live(), [{kind: "select-chapter", i: 1}, key("ArrowRight"), done(5), key("ArrowRight"), done(6)]).state;
  assertEqual(s.index, 6);
  r = feed(s, [key("ArrowRight")]);
  assertEqual(r.outbox, []);
  assertEqual(r.state.index, 6);
});

test("⇧→ and ⇧← jump with Nav (static)", function () {
  var ep = protoEpisodes()[0];
  var r = feed(live(), [key("ArrowRight"), key("ArrowRight", true)]);
  assertEqual(r.state.index, Nav.nextChapter(ep, 1));
  assertEqual(stageMsgs(r.outbox).pop(), show(4, false));
  r = feed(r.state, [key("ArrowRight"), key("ArrowLeft", true)]);
  assertEqual(r.state.index, Nav.prevChapter(ep, 5));
  assertEqual(stageMsgs(r.outbox).pop(), show(4, false));
});

test("B toggles blackout", function () {
  var r = feed(live(), [key("b")]);
  assertEqual(r.state.blackout, true);
  assertEqual(stageMsgs(r.outbox), [{type: "blackout", on: true}]);
  r = feed(r.state, [key("B", true)]);
  assertEqual(r.state.blackout, false);
  assertEqual(stageMsgs(r.outbox), [{type: "blackout", on: false}]);
});

test("a key message from the stage acts like a local key", function () {
  var r = feed(live(), [{kind: "message", msg: {type: "key", key: "ArrowRight", shift: false}}]);
  assertEqual(r.state.index, 1);
  assertEqual(stageMsgs(r.outbox), [show(1, true)]);
});

test("unknown keys do nothing", function () {
  var s = live();
  var r = Control.reduce(s, key("x"));
  assertEqual(r.outbox, []);
  assertEqual(r.state.index, 0);
});

// ---------------- control: playback ----------------

test("space starts playing and advances one animated step", function () {
  var r = feed(live(), [key(" ")]);
  assertEqual(r.state.playing, true);
  assertEqual(stageMsgs(r.outbox), [show(1, true)]);
});

test("while playing, done-animating asks the stage to wait, then advance shows the next", function () {
  var ep = protoEpisodes()[0];
  var r = feed(feed(live(), [key(" ")]).state, [{kind: "message", msg: {type: "done-animating", index: 1}}]);
  assertEqual(stageMsgs(r.outbox), [{type: "wait", delay: Animate.autoplay(ep, 1, 1).delay, seq: r.state.seq}]);
  assertEqual(effects(r.outbox), []);
  r = feed(r.state, [{kind: "message", msg: {type: "advance", seq: r.state.seq}}]);
  assertEqual(stageMsgs(r.outbox), [show(2, true)]);
});

test("autoplay stop (pause step) turns playing off", function () {
  var r = feed(feed(live(), [key("ArrowRight"), done(1), key(" ")]).state,
               [{kind: "message", msg: {type: "done-animating", index: 2}}]);
  assertEqual(r.state.index, 2);
  assertEqual(r.state.playing, false);
  assertEqual(stageMsgs(r.outbox), []);
});

test("space pauses (wait-cancel); a later advance is ignored", function () {
  var r = feed(live(), [key(" "), {kind: "message", msg: {type: "done-animating", index: 1}}]);
  var seq = stageMsgs(r.outbox)[0].seq;
  r = feed(r.state, [key(" ")]);
  assertEqual(stageMsgs(r.outbox), [{type: "wait-cancel"}]);
  r = feed(r.state, [{kind: "message", msg: {type: "advance", seq: seq}}]);
  assertEqual(r.state.playing, false);
  assertEqual(r.state.index, 1);
  assertEqual(stageMsgs(r.outbox), []);
});

test("a manual → during autoplay invalidates the pending advance", function () {
  var r = feed(live(), [key(" "), {kind: "message", msg: {type: "done-animating", index: 1}}]);
  var seq = stageMsgs(r.outbox)[0].seq;
  r = feed(r.state, [key("ArrowRight"), {kind: "message", msg: {type: "advance", seq: seq}}]);
  assertEqual(r.state.index, 2);
  assertEqual(stageMsgs(r.outbox), [show(2, true)]);
});

test("→ while the step still animates finishes it in place; the next → advances", function () {
  var r = feed(live(), [key("ArrowRight")]);
  assertEqual(r.state.animating, true);
  r = feed(r.state, [key("ArrowRight")]);
  assertEqual(r.state.index, 1);
  assertEqual(r.state.animating, false);
  assertEqual(stageMsgs(r.outbox), [show(1, false)]);
  r = feed(r.state, [key("ArrowRight")]);
  assertEqual(r.state.index, 2);
  assertEqual(stageMsgs(r.outbox), [show(2, true)]);
});

test("space while the step still animates finishes it and starts playing from there", function () {
  var ep = protoEpisodes()[0];
  var r = feed(live(), [key("ArrowRight"), key(" ")]);
  assertEqual(r.state.index, 1);
  assertEqual(r.state.playing, true);
  assertEqual(stageMsgs(r.outbox).pop(), show(1, false));
  r = feed(r.state, [done(1)]);
  assertEqual(stageMsgs(r.outbox), [{type: "wait", delay: Animate.autoplay(ep, 1, 1).delay, seq: r.state.seq}]);
});

test("after done-animating, → advances right away", function () {
  var r = feed(live(), [key("ArrowRight"), {kind: "message", msg: {type: "done-animating", index: 1}}]);
  assertEqual(r.state.animating, false);
  r = feed(r.state, [key("ArrowRight")]);
  assertEqual(stageMsgs(r.outbox), [show(2, true)]);
});

test("a stage that is not live never traps → on an unfinished step", function () {
  var r = feed(live(), [key("ArrowRight"), {kind: "stage-closed"}, key("ArrowRight")]);
  assertEqual(r.state.index, 2);
  r = feed(live(), [key("ArrowRight"), {kind: "message", msg: {type: "ready"}}, key("ArrowRight")]);
  assertEqual(r.state.index, 2, "a resend shows the step finished, so → moves on");
});

test("done-animating for another index is ignored", function () {
  var r = feed(feed(live(), [key(" ")]).state, [{kind: "message", msg: {type: "done-animating", index: 0}}]);
  assertEqual(stageMsgs(r.outbox), []);
  assertEqual(r.state.playing, true);
});

test("space at the last index does not start playing", function () {
  var s = feed(live(), [{kind: "select-chapter", i: 1}, key("ArrowRight"), done(5), key("ArrowRight"), done(6)]).state;
  var r = feed(s, [key(" ")]);
  assertEqual(r.state.playing, false);
  assertEqual(r.outbox, []);
});

// ---------------- control: speed, episodes, chapters ----------------

test("speed goes with the next show; unknown values are ignored", function () {
  var r = feed(live(), [{kind: "speed", value: 1.5}, key("ArrowRight")]);
  assertEqual(stageMsgs(r.outbox), [show(1, true, 1.5)]);
  r = feed(r.state, [{kind: "speed", value: 3}]);
  assertEqual(r.state.speed, 1.5);
  assertEqual(Control.SPEEDS, [0.5, 1, 1.5, 2]);
});

test("select-chapter shows that chapter's card (static) and pauses", function () {
  var r = feed(live(), [key(" "), {kind: "select-chapter", i: 1}]);
  assertEqual(r.state.index, 4);
  assertEqual(r.state.playing, false);
  assertEqual(stageMsgs(r.outbox).pop(), show(4, false));
});

test("select-episode in the same series shows index 0 of it", function () {
  var r = feed(live(), [key("ArrowRight"), {kind: "select-episode", id: "dos"}]);
  assertEqual(r.state.episodeId, "dos");
  assertEqual(r.state.index, 0);
  assertEqual(r.state.needsOpen, false);
  assertEqual(stageMsgs(r.outbox).pop(), show(0, false, 1, "dos"));
});

test("switching episode across series changes the stage file and asks to open it", function () {
  var r = feed(live(), [{kind: "select-episode", id: "tres"}]);
  assertEqual(r.state.stageFile, "serie-claude-code.html");
  assertEqual(r.state.needsOpen, true);
  assertEqual(stageMsgs(r.outbox), []);
  r = feed(r.state, [{kind: "stage-opened", now: 0}, {kind: "message", msg: {type: "ready"}}]);
  assertEqual(r.state.stageSeries, "claude-code");
  assertEqual(stageMsgs(r.outbox), [show(0, false, 1, "tres")]);
});

test("re-selecting the current episode is a no-op", function () {
  var s = feed(live(), [key("ArrowRight"), {kind: "tick", now: 500}, {kind: "tick", now: 900}]).state;
  var r = Control.reduce(s, {kind: "select-episode", id: "uno"});
  assertEqual(r.outbox, []);
  assertEqual(r.state.index, 1);
  assertEqual(r.state.elapsed, 400);
});

test("select-episode with an unknown id does nothing", function () {
  var s = live();
  var r = Control.reduce(s, {kind: "select-episode", id: "nope"});
  assertEqual(r.state.episodeId, "uno");
  assertEqual(r.outbox, []);
});

// ---------------- control: ping / lost / reopen ----------------

test("pings every 2 s while the stage is live", function () {
  var s = live();
  var r = feed(s, [{kind: "tick", now: 1999}]);
  assertEqual(stageMsgs(r.outbox), []);
  r = feed(r.state, [{kind: "tick", now: 2000}]);
  assertEqual(stageMsgs(r.outbox), [{type: "ping"}]);
  r = feed(r.state, [{kind: "tick", now: 3000}]);
  assertEqual(stageMsgs(r.outbox), []);
  r = feed(r.state, [{kind: "tick", now: 4000}]);
  assertEqual(stageMsgs(r.outbox), [{type: "ping"}]);
});

test("an unanswered ping for 5 s sets stageLost and stops playing", function () {
  var s = feed(live(), [key(" ")]).state;
  var r = feed(s, [{kind: "tick", now: 2000}, {kind: "tick", now: 4000}, {kind: "tick", now: 6000},
                   {kind: "tick", now: 6999}]);
  assertEqual(r.state.stageLost, false);
  r = feed(r.state, [{kind: "tick", now: 7000}]);
  assertEqual(r.state.stageLost, true);
  assertEqual(r.state.playing, false);
  r = feed(r.state, [{kind: "tick", now: 8000}]);
  assertEqual(stageMsgs(r.outbox), [{type: "ping"}], "keeps pinging while lost");
  r = feed(r.state, [key("b")]);
  assertEqual(stageMsgs(r.outbox), [], "no content while lost");
});

test("a pong answers the pending ping", function () {
  var r = feed(live(), [{kind: "tick", now: 2000}, {kind: "message", msg: {type: "pong"}, now: 3000},
                        {kind: "tick", now: 4000}, {kind: "tick", now: 6000}, {kind: "tick", now: 8999}]);
  assertEqual(r.state.stageLost, false);
  r = feed(r.state, [{kind: "tick", now: 9000}]);
  assertEqual(r.state.stageLost, true);
});

test("a late tick (+60 s, throttled control) with a live stage stays not lost", function () {
  var s = live(), r;
  for (var t = 250; t <= 10000; t += 250) {
    r = feed(s, [{kind: "tick", now: t}]);
    s = r.state;
    if (stageMsgs(r.outbox).length) s = feed(s, [{kind: "message", msg: {type: "pong"}, now: t + 5}]).state;
  }
  r = feed(s, [{kind: "tick", now: 70000}]);
  assertEqual(r.state.stageLost, false);
  assertEqual(stageMsgs(r.outbox), [{type: "ping"}], "pings first after a gap");
  r = feed(r.state, [{kind: "tick", now: 70250}]);
  assertEqual(r.state.stageLost, false);
});

test("a late tick after a gap does not judge a ping sent before it", function () {
  var r = feed(live(), [{kind: "tick", now: 2000}, {kind: "tick", now: 60000}]);
  assertEqual(r.state.stageLost, false);
  r = feed(r.state, [{kind: "message", msg: {type: "pong"}, now: 60010}, {kind: "tick", now: 64000}]);
  assertEqual(r.state.stageLost, false);
});

function lostAt(index) {
  var s = live();
  for (var i = 0; i < index; i++) s = feed(s, [key("ArrowRight"), done(i + 1)]).state;
  s = feed(s, [{kind: "tick", now: 2000}, {kind: "tick", now: 4000}, {kind: "tick", now: 7000}]).state;
  assertEqual(s.stageLost, true);
  return s;
}

test("a pong while lost recovers and resends the current show", function () {
  var r = feed(lostAt(2), [{kind: "message", msg: {type: "pong"}, now: 7100}]);
  assertEqual(r.state.stageLost, false);
  assertEqual(stageMsgs(r.outbox), [show(2, false)]);
});

test("a forwarded key counts as liveness", function () {
  var r = feed(lostAt(0), [{kind: "message", msg: {type: "key", key: "ArrowRight", shift: false}, now: 7100}]);
  assertEqual(r.state.stageLost, false);
  assertEqual(r.state.index, 1);
  assertEqual(stageMsgs(r.outbox), [show(0, false), show(1, true)]);
});

test("the stage window closed sets stageLost and stops playing", function () {
  var r = feed(live(), [key(" "), {kind: "stage-closed"}]);
  assertEqual(r.state.stageLost, true);
  assertEqual(r.state.playing, false);
});

test("reopen after lost resends the current show", function () {
  var s = lostAt(2);
  var r = feed(s, [{kind: "stage-opened", now: 8000}]);
  assertEqual(r.state.stageLost, false);
  r = feed(r.state, [{kind: "message", msg: {type: "ready"}}]);
  assertEqual(stageMsgs(r.outbox), [show(2, false)]);
});

// ---------------- control: clock and panels ----------------

test("the clock runs once the episode started and splits time per chapter", function () {
  var r = feed(live(), [{kind: "tick", now: 1000}]);
  assertEqual(r.state.elapsed, 0);
  r = feed(r.state, [key("ArrowRight"), {kind: "tick", now: 1500}, {kind: "tick", now: 2500},
                     {kind: "select-chapter", i: 1}, {kind: "tick", now: 3000}]);
  assertEqual(r.state.elapsed, 2000);
  assertEqual(r.state.chapterMs, [1500, 500]);
  r = feed(r.state, [{kind: "select-episode", id: "dos"}]);
  assertEqual(r.state.elapsed, 0);
  assertEqual(r.state.chapterMs, [0]);
});

test("notes panel: step notes, source and the skill commit and date", function () {
  var ep = protoEpisodes()[0];
  assertEqual(Control.notes(ep, 1), {notes: "NOTA-SECRETA uno", source: "real",
                                     commit: "c0ffee1", date: "2026-10-19",
                                     faq: [{q: "¿Y si no tengo Docker?", a: "Sigue sin e2e."}]});
  var card = Control.notes(ep, 4);
  assertEqual(card.source, null);
  assertEqual(card.notes, "");
  assertEqual(card.faq, []);
  assertEqual(Control.notes(ep, 2).source, "inferido");
});

test("Lo que viene: next card title or next step label", function () {
  var ep = protoEpisodes()[0];
  assertEqual(Control.upNext(ep, 0), "ls");
  assertEqual(Control.upNext(ep, 2), "Ran · ia.py baseline");
  assertEqual(Control.upNext(ep, 3), "Placa · «Caso principal»");
  assertEqual(Control.upNext(ep, 4), "Auditá esto");
  assertEqual(Control.upNext(ep, 5), "Crear tickets");
  assertEqual(Control.upNext(ep, 6), "Fin del episodio");
  assertEqual(Control.stepLabel({type: "say", md: "#### Hecho\nUno"}), "Hecho");
  assertEqual(Control.stepLabel({type: "worked", seconds: 42}), "Trabajó 42 s");
});

// ---------------- stage ----------------

function fakeClock() {
  var q = [], next = 0;
  return {
    schedule: function (fn, ms) { next++; q.push({id: next, fn: fn, ms: ms}); return next; },
    unschedule: function (id) { q = q.filter(function (t) { return t.id !== id; }); },
    pending: function () { return q.map(function (t) { return t.ms; }); },
    drain: function () { var n = 0; while (q.length && n < 10000) { q.shift().fn(); n++; } }
  };
}
function makeStage(episodes) {
  var canvas = document.createElement("div");
  var blackout = document.createElement("div");
  var posted = [];
  var clock = fakeClock();
  var st = Stage.create({canvas: canvas, blackout: blackout, episodes: episodes || protoEpisodes(),
                         post: function (m) { posted.push(m); },
                         schedule: clock.schedule, unschedule: clock.unschedule});
  return {stage: st, canvas: canvas, blackout: blackout, posted: posted, clock: clock};
}
function rendered(ep, i) {
  var c = document.createElement("div");
  Render.step(c, ep, i);
  return c.innerHTML;
}

test("stage: tickClock updates only the idle prompt's time text", function () {
  var t = makeStage();
  return t.stage.handle(show(1, false)).then(function () {
    var before = t.canvas.innerHTML;
    var saved = Render.now;
    Render.now = function () { return new Date(2026, 9, 19, 15, 5, 14); };
    try {
      assertEqual(Stage.tickClock(t.canvas), 1, "one idle prompt");
    } finally {
      Render.now = saved;
    }
    assertEqual(t.canvas.querySelector('[data-anim="idle"] .ws-time').textContent, "15:05:14");
    var steps = t.canvas.querySelectorAll('[data-step] .ws-time');
    assert(steps.length >= 1, "step prompts have a time");
    for (var i = 0; i < steps.length; i++) assertEqual(steps[i].textContent, "09:05:07", "step time untouched");
    var back = t.canvas.querySelector('[data-anim="idle"] .ws-time');
    back.textContent = "09:05:07";
    assertEqual(t.canvas.innerHTML, before, "nothing else changed");
  });
});

test("stage: tickClock during a running animation leaves the animation intact", function () {
  var t = makeStage();
  return t.stage.handle(show(0, false)).then(function () {
    var p = t.stage.handle(show(1, true));
    var typed = t.canvas.querySelector('[data-anim="type"]');
    var idle = t.canvas.querySelector('[data-anim="idle"]');
    var hidden = idle.style.display;
    var saved = Render.now;
    Render.now = function () { return new Date(2026, 9, 19, 15, 5, 14); };
    try {
      Stage.tickClock(t.canvas);
    } finally {
      Render.now = saved;
    }
    assertEqual(idle.querySelector(".ws-time").textContent, "15:05:14", "idle clock ticked");
    assertEqual(typed.textContent, "", "typing state untouched");
    assertEqual(idle.style.display, hidden, "idle visibility untouched");
    assert(t.canvas.querySelector('[data-anim="type"]') === typed, "same nodes, no re-render");
    t.clock.drain();
    return p;
  }).then(function () {
    assertEqual(t.canvas.innerHTML, rendered(protoEpisodes()[0], 1));
  });
});

test("stage: black and empty before the first show", function () {
  var t = makeStage();
  assertEqual(t.canvas.childNodes.length, 0);
  assertEqual(t.blackout.hidden, true);
});

test("stage: ping answers pong", function () {
  var t = makeStage();
  return t.stage.handle({type: "ping"}).then(function () {
    assertEqual(t.posted, [{type: "pong"}]);
  });
});

test("stage: static show replies shown then done-animating", function () {
  var t = makeStage();
  return t.stage.handle(show(3, false)).then(function () {
    assertEqual(t.posted, [{type: "shown", episode: "uno", index: 3}, {type: "done-animating", index: 3}]);
    assertEqual(t.canvas.innerHTML, rendered(protoEpisodes()[0], 3));
  });
});

test("stage: show animate at current+1 runs the animation", function () {
  var t = makeStage();
  return t.stage.handle(show(0, false)).then(function () {
    t.posted.length = 0;
    var p = t.stage.handle(show(1, true));
    assertEqual(t.posted, [{type: "shown", episode: "uno", index: 1}]);
    assertEqual(t.canvas.querySelector('[data-anim="type"]').textContent, "", "typing starts empty");
    t.clock.drain();
    return p;
  }).then(function () {
    assertEqual(t.posted, [{type: "shown", episode: "uno", index: 1}, {type: "done-animating", index: 1}]);
    assertEqual(t.canvas.innerHTML, rendered(protoEpisodes()[0], 1));
  });
});

test("stage: show animate not at current+1 renders the finished state", function () {
  var t = makeStage();
  return t.stage.handle(show(5, true)).then(function () {
    assertEqual(t.posted, [{type: "shown", episode: "uno", index: 5}, {type: "done-animating", index: 5}]);
    assertEqual(t.canvas.innerHTML, rendered(protoEpisodes()[0], 5));
  });
});

test("stage: a superseded run sends no done-animating", function () {
  var t = makeStage();
  return t.stage.handle(show(0, false)).then(function () {
    t.posted.length = 0;
    var first = t.stage.handle(show(1, true));
    var second = t.stage.handle(show(0, false));
    return Promise.all([first, second]);
  }).then(function () {
    assertEqual(t.posted, [{type: "shown", episode: "uno", index: 1}, {type: "shown", episode: "uno", index: 0},
                           {type: "done-animating", index: 0}]);
    assertEqual(t.canvas.innerHTML, rendered(protoEpisodes()[0], 0));
  });
});

test("stage: fade class only while an animated card or approve runs", function () {
  var t = makeStage();
  return t.stage.handle(show(3, false)).then(function () {
    assert(!t.canvas.classList.contains("ws-fade-in"), "static render has no fade");
    var p = t.stage.handle(show(4, true));
    assert(t.canvas.classList.contains("ws-fade-in"), "animated card fades");
    t.clock.drain();
    return p;
  }).then(function () {
    assert(!t.canvas.classList.contains("ws-fade-in"), "fade class removed at the end");
    var p = t.stage.handle(show(5, true));
    assert(!t.canvas.classList.contains("ws-fade-in"), "an ask does not fade");
    t.clock.drain();
    return p;
  });
});

test("stage: a page right after another page does not fade", function () {
  var ep = {id: "web", series: "cursor", order: 1, title: "web", skill: {repo: "web", commit: "abc1234", date: "2026-10-19"},
            workspace: {repo: "r", files: [], chats: []},
            chapters: [{id: "w", title: "Web", screen: "cursor-full", steps: [
              {type: "page", title: "a.com", html: "<p>a</p>", source: "real"},
              {type: "page", title: "b.com", html: "<p>b</p>", source: "real"}]}]};
  var t = makeStage([ep]);
  return t.stage.handle({type: "show", episode: "web", index: 0, animate: false}).then(function () {
    var p = t.stage.handle({type: "show", episode: "web", index: 1, animate: true});
    assert(t.canvas.classList.contains("ws-fade-in"), "the first page fades");
    t.clock.drain();
    return p;
  }).then(function () {
    var p = t.stage.handle({type: "show", episode: "web", index: 2, animate: true});
    assert(!t.canvas.classList.contains("ws-fade-in"), "the second page fades the browser out and in");
    t.clock.drain();
    return p;
  });
});

test("stage: blackout toggles the black layer", function () {
  var t = makeStage();
  return t.stage.handle({type: "blackout", on: true}).then(function () {
    assertEqual(t.blackout.hidden, false);
    return t.stage.handle({type: "blackout", on: false});
  }).then(function () {
    assertEqual(t.blackout.hidden, true);
    assertEqual(t.posted, []);
  });
});

test("stage: a show for an episode it does not have is ignored", function () {
  var t = makeStage();
  return t.stage.handle(show(0, false, 1, "otra")).then(function () {
    assertEqual(t.posted, []);
    assertEqual(t.canvas.childNodes.length, 0);
  });
});

test("stage: wait times the delay, then sends advance with its seq", function () {
  var t = makeStage();
  return t.stage.handle({type: "wait", delay: 900, seq: 7}).then(function () {
    assertEqual(t.clock.pending(), [900]);
    assertEqual(t.posted, []);
    t.clock.drain();
    assertEqual(t.posted, [{type: "advance", seq: 7}]);
  });
});

test("stage: a show or wait-cancel drops the pending wait", function () {
  var t = makeStage();
  return t.stage.handle({type: "wait", delay: 900, seq: 7}).then(function () {
    return t.stage.handle(show(3, false));
  }).then(function () {
    assertEqual(t.clock.pending(), []);
    return t.stage.handle({type: "wait", delay: 900, seq: 8});
  }).then(function () {
    return t.stage.handle({type: "wait-cancel"});
  }).then(function () {
    t.clock.drain();
    assert(!t.posted.some(function (m) { return m.type === "advance"; }), "no advance after cancel");
  });
});

test("stage: key repeats and modified keys are not forwarded", function () {
  assertEqual(Stage.keyMessage({key: "ArrowRight", repeat: true}), null);
  assertEqual(Stage.keyMessage({key: "ArrowRight", metaKey: true}), null);
  assertEqual(Stage.keyMessage({key: "b", ctrlKey: true}), null);
  assertEqual(Stage.keyMessage({key: " ", altKey: true}), null);
});

test("stage: control keys are forwarded as key messages", function () {
  assertEqual(Stage.keyMessage({key: "ArrowRight", shiftKey: true}), {type: "key", key: "ArrowRight", shift: true});
  assertEqual(Stage.keyMessage({key: " ", shiftKey: false}), {type: "key", key: " ", shift: false});
  assertEqual(Stage.keyMessage({key: "b", shiftKey: false}), {type: "key", key: "b", shift: false});
  assertEqual(Stage.keyMessage({key: "x", shiftKey: false}), null);
});

test("control: PageDown and PageUp move like the arrows (presenter clickers)", function () {
  var r = feed(live(), [key("PageDown"), done(1), key("PageDown"), key("PageUp")]);
  assertEqual(r.state.index, 1);
  var shows = r.outbox.filter(function (o) { return o.msg.type === "show"; });
  assertEqual(shows.map(function (o) { return [o.msg.index, o.msg.animate]; }), [[1, true], [2, true], [1, false]]);
});

test("stage: PageDown and PageUp are forwarded too", function () {
  assertEqual(Stage.keyMessage({key: "PageDown"}), {type: "key", key: "PageDown", shift: false});
  assertEqual(Stage.keyMessage({key: "PageUp", shiftKey: true}), {type: "key", key: "PageUp", shift: true});
});

test("stage alone: localMove steps forward animated and back finished", function () {
  var ep = protoEpisodes()[0];  // 7 entries: card, 3 steps, card, 2 steps
  assertEqual(Stage.localMove(ep, 0, "ArrowRight", false), {index: 1, animate: true});
  assertEqual(Stage.localMove(ep, 0, "PageDown", false), {index: 1, animate: true});
  assertEqual(Stage.localMove(ep, 0, " ", false), {index: 1, animate: true});
  assertEqual(Stage.localMove(ep, 2, "ArrowLeft", false), {index: 1, animate: false});
  assertEqual(Stage.localMove(ep, 2, "PageUp", false), {index: 1, animate: false});
});

test("stage alone: → or space while the step animates finishes it; ← and ⇧ jumps still move", function () {
  var ep = protoEpisodes()[0];
  assertEqual(Stage.localMove(ep, 1, "ArrowRight", false, true), {index: 1, animate: false});
  assertEqual(Stage.localMove(ep, 1, " ", false, true), {index: 1, animate: false});
  assertEqual(Stage.localMove(ep, 6, "ArrowRight", false, true), {index: 6, animate: false});
  assertEqual(Stage.localMove(ep, 2, "ArrowLeft", false, true), {index: 1, animate: false});
  assertEqual(Stage.localMove(ep, 1, "ArrowRight", true, true), {index: 4, animate: false});
  assertEqual(Stage.localMove(ep, 1, "ArrowRight", false, false), {index: 2, animate: true});
});

test("stage: animating() is true only while an animation runs", function () {
  var t = makeStage();
  return t.stage.handle(show(0, false)).then(function () {
    assertEqual(t.stage.animating(), false);
    var p = t.stage.handle(show(1, true));
    assertEqual(t.stage.animating(), true);
    t.clock.drain();
    return p;
  }).then(function () {
    assertEqual(t.stage.animating(), false);
    t.stage.handle(show(2, true));
    assertEqual(t.stage.animating(), true);
    return t.stage.handle(show(2, false));
  }).then(function () {
    assertEqual(t.stage.animating(), false, "a finished show stops it");
  });
});

test("stage alone: localMove jumps chapters with shift and stops at the ends", function () {
  var ep = protoEpisodes()[0];
  assertEqual(Stage.localMove(ep, 1, "ArrowRight", true), {index: 4, animate: false});
  assertEqual(Stage.localMove(ep, 5, "ArrowLeft", true), {index: 4, animate: false});
  assertEqual(Stage.localMove(ep, 6, "ArrowRight", false), null);
  assertEqual(Stage.localMove(ep, 0, "ArrowLeft", false), null);
  assertEqual(Stage.localMove(ep, 6, "ArrowRight", true), null);
  assertEqual(Stage.localMove(ep, 0, "b", false), null);
  assertEqual(Stage.localMove(ep, 0, "x", false), null);
});

test("stage alone: hashFor writes the 1-based step parseHash reads", function () {
  assertEqual(Stage.hashFor("uno", 0), "#uno/1");
  assertEqual(Stage.parseHash(Stage.hashFor("inherited-audit", 6)), {episode: "inherited-audit", index: 6});
});

test("stage never shows notes, source or the skill commit", function () {
  var t = makeStage();
  var ep = protoEpisodes()[0];
  var chain = Promise.resolve();
  Nav.flatten(ep).forEach(function (_, i) {
    chain = chain.then(function () { return t.stage.handle(show(i, false)); }).then(function () {
      var text = t.canvas.textContent;
      assert(text.indexOf("NOTA-SECRETA") < 0, "notes on stage at " + i);
      assert(text.indexOf("c0ffee1") < 0, "commit on stage at " + i);
      assert(text.indexOf("inferido") < 0, "source on stage at " + i);
    });
  });
  return chain;
});

test("stage: parseHash reads #<episode>/<step>, 1-based", function () {
  assertEqual(Stage.parseHash("#inherited-audit/3"), {episode: "inherited-audit", index: 2});
  assertEqual(Stage.parseHash("#antes.de-empezar_0/1"), {episode: "antes.de-empezar_0", index: 0});
});

test("stage: parseHash rejects anything else", function () {
  ["", "#", "#uno", "#uno/", "#uno/0", "#uno/-1", "#uno/1.5", "#uno/x", "#/3", "uno/3", "#uno/3/4", "#a b/3", null, undefined]
    .forEach(function (h) { assertEqual(Stage.parseHash(h), null, String(h)); });
});
