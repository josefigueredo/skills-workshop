// Forward animation of ONE step, plus the playback policy as pure functions.
//
// Animate.run(container, episode, index, opts) -> {cancel(), done: Promise}
//   Renders the finished state with Render.step(container, episode, index), hides the
//   current step's hooks (see render.js header) and reveals them in document order on
//   the injected scheduler, so it looks like the step at `index` playing on top of
//   Render.step(index - 1). Both completion and cancel() end with a fresh
//   Render.step(container, episode, index): the final DOM is identical by construction.
//   `done` resolves in both cases (never rejects). A new run on the same container
//   cancels the previous one first, and a reveal that throws ends the run in the final
//   state too. A page or approve step is the exception: its window holds an iframe that a
//   fresh render would rebuild (blank until it loads again), so when it completes on its
//   own the run only clears the inline styles it set, which leaves the same DOM.
// Animate.stop(container): cancels the active run on `container` without rendering
//   (call it before a static Render.step, e.g. on a back-step).
//   opts: {speed = 1 (clamped to >= 0.1), schedule(fn, ms) -> id = setTimeout,
//          unschedule(id) = clearTimeout, now() = Date.now (accepted, not used: every
//          wait goes through schedule)}.
//
// Timing (every value is divided by speed):
//   type  28 ms per character (code points), the text grows one character per tick
//   line  120 ms per line / say block
//   node  250 ms, then the node appears whole (tool, worked, chips)
//   fade  250 ms for a card, an approve window and a page: opacity 0 until the tick.
//         A page right after a page (or an approve right after an approve) keeps the window
//         on screen and only waits: the browser does not blink between them (continuesWindow).
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

  // True when the step at `index` is a page or approve right after another of the same type
  // in its chapter: the window was already on screen, so it does not fade in again.
  function continuesWindow(ep, index) {
    var flat = Nav.flatten(ep);
    var e = flat[Nav.clamp(ep, index)];
    if (!e || e.step < 1 || (e.kind !== "page" && e.kind !== "approve")) return false;
    return ep.chapters[e.chapter].steps[e.step - 1].type === e.kind;
  }

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
    // The idle prompt lives in the zsh panel (cursor-full) and on the terminal screen: hide
    // it only when this step plays in that same flow, not for a chat-placed agent command.
    // On claude-code, `in: "zsh"` is the person's `!` line and there is no idle prompt, so
    // the lookup below finds nothing.
    if (step.type === "term" && (step["in"] === "zsh" || ep.chapters[e.chapter].screen === "terminal")) {
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
      } else if (kind === "node" && (step.type === "approve" || step.type === "page") && n === root) {
        if (continuesWindow(ep, index)) {
          plan.push({ms: FADE_MS / speed, fn: function () {}});
        } else {
          n.style.opacity = "0";
          plan.push({ms: FADE_MS / speed, fn: function () { n.style.opacity = ""; }});
        }
      } else if (kind === "node") {
        hide(n);
        plan.push({ms: NODE_MS / speed, fn: function () { show(n); }});
      }
    });
    if (step.type === "approve" || step.type === "page") {
      plan.finish = function () {
        hooks.forEach(function (n) { if (n.getAttribute("style") === "") n.removeAttribute("style"); });
      };
    }
    return plan;
  }

  // One active run per container: a new run (or stop) cancels the previous one first.
  var active = typeof WeakMap === "function" ? new WeakMap() : null;
  function getActive(c) { return active ? active.get(c) : c.__wsAnimRun; }
  function setActive(c, r) { if (active) active.set(c, r); else c.__wsAnimRun = r; }
  function clearActive(c, r) {
    if (getActive(c) !== r) return;
    if (active) active.delete(c); else delete c.__wsAnimRun;
  }

  // Cancel any active run on `container` without rendering (its `done` resolves).
  function stop(container) {
    var r = getActive(container);
    if (r) r.abort();
  }

  function run(container, ep, index, opts) {
    opts = opts || {};
    stop(container);
    var speed = speedOf(opts.speed === undefined ? 1 : opts.speed);
    var schedule = opts.schedule || function (fn, ms) { return setTimeout(fn, ms); };
    var unschedule = opts.unschedule || function (id) { clearTimeout(id); };
    var finished = false, timer = null, resolveDone;
    var done = new Promise(function (resolve) { resolveDone = resolve; });
    var handle = {cancel: function () { end(true); }, done: done, abort: function () { end(false); }};
    setActive(container, handle);
    var plan = prepare(container, ep, index, speed);

    function end(render) {
      if (finished) return;
      finished = true;
      if (timer !== null) { unschedule(timer); timer = null; }
      clearActive(container, handle);
      if (render) Render.step(container, ep, index);
      resolveDone();
    }
    function next(k) {
      if (finished) return;
      if (k >= plan.length) {
        if (plan.finish) { plan.finish(); end(false); } else end(true);
        return;
      }
      timer = schedule(function () {
        timer = null;
        if (finished) return;
        try {
          plan[k].fn();
        } catch (err) {
          // A broken reveal must not stall playback: jump to the final state.
          if (typeof console !== "undefined") console.error("Animate: reveal failed", err);
          end(true);
          return;
        }
        next(k + 1);
      }, plan[k].ms);
    }
    next(0);
    return {cancel: handle.cancel, done: done};
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

  return {run: run, stop: stop, continuesWindow: continuesWindow, stepDuration: stepDuration, autoplay: autoplay, episodeDuration: episodeDuration,
          CHAR_MS: CHAR_MS, LINE_MS: LINE_MS, NODE_MS: NODE_MS, FADE_MS: FADE_MS, AUTOPLAY_MS: AUTOPLAY_MS};
})();
