// Forward animation of ONE step, plus the playback policy as pure functions.
//
// Animate.run(container, episode, index, opts) -> {cancel(), done: Promise}
//   Renders the finished state with Render.step(container, episode, index), hides the
//   current step's hooks (see render.js header) and reveals them in document order on
//   the injected scheduler, so it looks like the step at `index` playing on top of
//   Render.step(index - 1). Both completion and cancel() end with a fresh
//   Render.step(container, episode, index): the final DOM is identical by construction.
//   `done` resolves in both cases (never rejects). A caller must cancel() the previous
//   run before starting a new one on the same container.
//   opts: {speed = 1 (clamped to >= 0.1), schedule(fn, ms) -> id = setTimeout,
//          unschedule(id) = clearTimeout, now() = Date.now (accepted, not used: every
//          wait goes through schedule)}.
//
// Timing (every value is divided by speed):
//   type  28 ms per character (code points), the text grows one character per tick
//   line  120 ms per line / say block
//   node  250 ms, then the node appears whole (tool, worked, chips)
//   fade  250 ms for a card and an approve window: opacity 0 until the tick
//   autoplay delay between steps 900 ms
// Animate.stepDuration walks the same plan the animation schedules, so the estimate
// and the playback cannot drift apart.
var Animate = (function () {
  var CHAR_MS = 28;
  var LINE_MS = 120;
  var NODE_MS = 250;
  var FADE_MS = 250;
  var AUTOPLAY_MS = 900;
  var MIN_SPEED = 0.1;

  function speedOf(s) {
    s = Number(s);
    if (!(s > 0)) s = MIN_SPEED;
    return Math.max(s, MIN_SPEED);
  }
  function chars(text) { return Array.from(String(text || "")); }
  function hide(n) { n.style.display = "none"; }
  function show(n) { n.style.display = ""; }

  // Render the finished state into `container`, hide what the step at `index` adds and
  // return the reveal plan: [{ms, fn}] in order (ms already divided by speed).
  function prepare(container, ep, index, speed) {
    Render.step(container, ep, index);
    var flat = Nav.flatten(ep);
    if (!flat.length) return [];
    var e = flat[Nav.clamp(ep, index)];
    var plan = [];
    var screen = container.firstChild;
    if (e.step === -1) {
      screen.style.opacity = "0";
      plan.push({ms: FADE_MS / speed, fn: function () { screen.style.opacity = "1"; }});
      return plan;
    }
    var root = container.querySelector('[data-step="' + e.step + '"]');
    if (!root) return plan;
    var step = ep.chapters[e.chapter].steps[e.step];
    if (step.type === "term") {
      var idle = container.querySelector('[data-anim="idle"]');
      if (idle) hide(idle);
    }
    var hooks = [];
    if (root.hasAttribute("data-anim")) hooks.push(root);
    Array.prototype.forEach.call(root.querySelectorAll("[data-anim]"), function (n) { hooks.push(n); });
    hooks.forEach(function (n) {
      var kind = n.getAttribute("data-anim");
      if (kind === "type") {
        var cs = chars(n.textContent);
        n.textContent = "";
        cs.forEach(function (_, k) {
          plan.push({ms: CHAR_MS / speed, fn: function () { n.textContent = cs.slice(0, k + 1).join(""); }});
        });
      } else if (kind === "line") {
        hide(n);
        plan.push({ms: LINE_MS / speed, fn: function () { show(n); }});
      } else if (kind === "node" && step.type === "approve" && n === root) {
        n.style.opacity = "0";
        plan.push({ms: FADE_MS / speed, fn: function () { n.style.opacity = "1"; }});
      } else if (kind === "node") {
        hide(n);
        plan.push({ms: NODE_MS / speed, fn: function () { show(n); }});
      }
    });
    return plan;
  }

  function run(container, ep, index, opts) {
    opts = opts || {};
    var speed = speedOf(opts.speed === undefined ? 1 : opts.speed);
    var schedule = opts.schedule || function (fn, ms) { return setTimeout(fn, ms); };
    var unschedule = opts.unschedule || function (id) { clearTimeout(id); };
    var plan = prepare(container, ep, index, speed);
    var finished = false, timer = null, resolveDone;
    var done = new Promise(function (resolve) { resolveDone = resolve; });

    function finish() {
      if (finished) return;
      finished = true;
      if (timer !== null) { unschedule(timer); timer = null; }
      Render.step(container, ep, index);
      resolveDone();
    }
    function next(k) {
      if (finished) return;
      if (k >= plan.length) { finish(); return; }
      timer = schedule(function () {
        timer = null;
        if (finished) return;
        plan[k].fn();
        next(k + 1);
      }, plan[k].ms);
    }
    next(0);
    return {cancel: finish, done: done};
  }

  // Sum of the ms the animation of `index` schedules (same plan, detached container).
  function stepDuration(ep, index, speed) {
    var plan = prepare(document.createElement("div"), ep, index, speedOf(speed));
    return plan.reduce(function (s, a) { return s + a.ms; }, 0);
  }

  // What autoplay does after `index` finished animating.
  function autoplay(ep, index, speed) {
    var flat = Nav.flatten(ep);
    var i = Nav.clamp(ep, index);
    if (!flat.length || i >= flat.length - 1) return {stop: true, delay: 0};
    var e = flat[i];
    var steps = ep.chapters[e.chapter].steps || [];
    if (e.step === steps.length - 1) return {stop: true, delay: 0};  // also an empty chapter's card
    if (e.step >= 0 && steps[e.step].pause) return {stop: true, delay: 0};
    return {stop: false, delay: AUTOPLAY_MS / speedOf(speed)};
  }

  // Estimated length: step animations plus autoplay delays (none after a stop).
  function episodeDuration(ep, speed) {
    var flat = Nav.flatten(ep);
    var chapters = (ep.chapters || []).map(function (ch) { return {id: ch.id, ms: 0}; });
    var total = 0;
    flat.forEach(function (e, i) {
      var a = autoplay(ep, i, speed);
      var ms = stepDuration(ep, i, speed) + (a.stop ? 0 : a.delay);
      chapters[e.chapter].ms += ms;
      total += ms;
    });
    return {total: total, chapters: chapters};
  }

  return {run: run, stepDuration: stepDuration, autoplay: autoplay, episodeDuration: episodeDuration,
          CHAR_MS: CHAR_MS, LINE_MS: LINE_MS, NODE_MS: NODE_MS, FADE_MS: FADE_MS, AUTOPLAY_MS: AUTOPLAY_MS};
})();
