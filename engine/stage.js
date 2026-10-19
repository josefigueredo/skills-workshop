// Stage page: what the audience sees. It holds (episode, index), renders or animates on
// `show` and answers the control. Messages (see the episode format):
//   in : {type:"show", episode, index, animate, speed} | {type:"blackout", on} | {type:"ping"}
//        {type:"wait", delay, seq} | {type:"wait-cancel"}
//   out: {type:"ready"} on load, {type:"shown", episode, index}, then
//        {type:"done-animating", index} (only for the latest show), {type:"pong"},
//        {type:"advance", seq} when a wait ends,
//        {type:"key", key, shift} for the presenter's keys pressed while the stage has focus.
// The stage times the autoplay delay (`wait`) because its window is the visible one:
// the control's timers may be throttled while the stage has focus. A new show, a new wait
// or wait-cancel drops the pending wait.
// A `show` animates only when animate is true and index == current + 1 in the same
// episode; anything else cancels the running animation and renders the finished state.
// The stage never shows notes, sources or the skill commit: it only calls Render.step.
//
// Stage.create(opts) -> {handle(msg) -> Promise, current()} is the testable core:
//   opts: {canvas (Render container), blackout (element toggled with .hidden), episodes,
//          post(msg), schedule?, unschedule? (passed to Animate.run)}.
// Stage.tickClock(canvas) sets the idle prompt's time text (.ws-time inside
//   [data-anim="idle"]) to Render.now(); it touches nothing else, so it never re-renders
//   a step or disturbs a running animation. The page calls it every second.
// Stage.localMove(ep, index, key, shift) -> {index, animate} | null: where the presenter
//   keys go when no control drives the page (opened from its link). → / PageDown / space
//   step forward animated, ← / PageUp step back finished, shift jumps chapters; null at
//   the ends or for any other key. Stage.hashFor(id, index) is the "#id/N" parseHash reads.
// The DOM bootstrap at the end runs only on the page with #ws-stage-root. The page is
// driven when the control opened it (window "ws-stage" with an opener); otherwise it
// navigates by itself and keeps the step in the hash, so a reload stays put.
var Stage = (function () {
  var FADE = "ws-fade-in";

  function create(opts) {
    var canvas = opts.canvas, blackout = opts.blackout;
    var post = opts.post || function () {};
    var byId = {};
    (opts.episodes || []).forEach(function (ep) { if (ep && ep.id) byId[ep.id] = ep; });
    var cur = null;   // {episode, index} of the latest show
    var seq = 0;      // id of the latest show; older runs stay silent
    var schedule = opts.schedule || function (fn, ms) { return setTimeout(fn, ms); };
    var unschedule = opts.unschedule || function (id) { clearTimeout(id); };
    var waiting = null;  // timer id of the pending wait
    function cancelWait() {
      if (waiting !== null) { unschedule(waiting); waiting = null; }
    }
    function onWait(msg) {
      cancelWait();
      var delay = Math.max(Number(msg.delay) || 0, 0);
      waiting = schedule(function () {
        waiting = null;
        post({type: "advance", seq: msg.seq});
      }, delay);
    }
    if (blackout) blackout.hidden = true;

    function fades(ep, index) {
      var e = Nav.flatten(ep)[index];
      return !!e && (e.kind === "card" || e.kind === "approve");
    }

    function onShow(msg) {
      var ep = byId[msg.episode];
      if (!ep) return Promise.resolve();
      var index = Nav.clamp(ep, msg.index);
      var id = ++seq;
      cancelWait();
      var animate = msg.animate === true && cur !== null && cur.episode === ep.id && index === cur.index + 1;
      cur = {episode: ep.id, index: index};
      canvas.classList.remove(FADE);
      if (!animate) {
        Animate.stop(canvas);
        Render.step(canvas, ep, index);
        post({type: "shown", episode: ep.id, index: index});
        post({type: "done-animating", index: index});
        return Promise.resolve();
      }
      var speed = Math.max(Number(msg.speed) || 1, 0.1);
      if (fades(ep, index)) {
        canvas.style.setProperty("--ws-fade-ms", Math.round(Animate.FADE_MS / speed) + "ms");
        canvas.classList.add(FADE);
      }
      var run = Animate.run(canvas, ep, index, {speed: speed, schedule: schedule, unschedule: unschedule});
      post({type: "shown", episode: ep.id, index: index});
      return run.done.then(function () {
        if (id !== seq) return;
        // Same task as Animate's final render: the fresh node never starts the fade.
        canvas.classList.remove(FADE);
        post({type: "done-animating", index: index});
      });
    }

    function handle(msg) {
      if (!msg || typeof msg !== "object") return Promise.resolve();
      if (msg.type === "show") return onShow(msg);
      if (msg.type === "blackout") { if (blackout) blackout.hidden = !msg.on; }
      else if (msg.type === "ping") post({type: "pong"});
      else if (msg.type === "wait") onWait(msg);
      else if (msg.type === "wait-cancel") cancelWait();
      return Promise.resolve();
    }

    return {handle: handle, current: function () { return cur; }};
  }

  // Refresh only the idle prompt's clock text; returns how many were updated.
  function tickClock(canvas) {
    var text = Render.clockText(Render.now());
    var spans = canvas.querySelectorAll('[data-anim="idle"] .ws-time');
    for (var i = 0; i < spans.length; i++) {
      if (spans[i].textContent !== text) spans[i].textContent = text;
    }
    return spans.length;
  }

  // The keydown the stage forwards to the control, or null.
  function keyMessage(ev) {
    if (!ev || !Nav.keyAction(ev.key) || ev.repeat || ev.metaKey || ev.ctrlKey || ev.altKey) return null;
    return {type: "key", key: ev.key, shift: !!ev.shiftKey};
  }

  // Static preview hook: "#<episode-id>/<step>" -> {episode, index}, or null. The step is
  // 1-based, like the "paso N de M" on the control: #id/1 is index 0 (#id/0 is rejected).
  function parseHash(hash) {
    var m = /^#([A-Za-z0-9._-]+)\/(\d+)$/.exec(typeof hash === "string" ? hash : "");
    var n = m ? parseInt(m[2], 10) : 0;
    return n >= 1 ? {episode: m[1], index: n - 1} : null;
  }

  function localMove(ep, index, key, shift) {
    var k = Nav.keyAction(key), last = Nav.flatten(ep).length - 1, target;
    if ((k === "right" || k === "left") && shift) {
      target = k === "right" ? Nav.nextChapter(ep, index) : Nav.prevChapter(ep, index);
      return target === index ? null : {index: target, animate: false};
    }
    if (k === "right" || k === "space") return index >= last ? null : {index: index + 1, animate: true};
    if (k === "left") return index <= 0 ? null : {index: index - 1, animate: false};
    return null;
  }

  function hashFor(id, index) { return "#" + id + "/" + (index + 1); }

  function readEpisodes() {
    var node = document.getElementById("episodes");
    if (!node) return [];
    try {
      var data = JSON.parse(node.textContent);
      return Array.isArray(data) ? data : [];
    } catch (e) {
      return [];
    }
  }

  // Scale the 1600x900 frame to fit the window, letterboxed on black.
  function fit(frame) {
    var s = Math.min(window.innerWidth / 1600, window.innerHeight / 900);
    frame.style.transform = "translate(-50%, -50%) scale(" + s + ")";
  }

  function boot() {
    if (!document.getElementById("ws-stage-root")) return;
    var frame = document.getElementById("ws-frame");
    var opener = window.name === "ws-stage" ? window.opener : null;
    function post(msg) { if (opener && !opener.closed) opener.postMessage(msg, "*"); }
    var canvas = document.getElementById("ws-canvas");
    var blackout = document.getElementById("ws-blackout");
    var episodes = readEpisodes();
    var stage = create({canvas: canvas, blackout: blackout, episodes: episodes, post: post});
    window.addEventListener("message", function (ev) {
      if (!opener || ev.source !== opener) return;
      stage.handle(ev.data);
    });
    document.addEventListener("keydown", function (ev) {
      var msg = keyMessage(ev);
      if (!msg) return;
      ev.preventDefault();
      if (opener) post(msg);
      else moveAlone(msg);
    });
    function moveAlone(msg) {
      if (Nav.keyAction(msg.key) === "b") { blackout.hidden = !blackout.hidden; return; }
      var cur = stage.current(), ep = null;
      episodes.forEach(function (e) { if (cur && e.id === cur.episode) ep = e; });
      var to = ep && localMove(ep, cur.index, msg.key, msg.shift);
      if (!to) return;
      history.replaceState(null, "", hashFor(ep.id, to.index));
      stage.handle({type: "show", episode: ep.id, index: to.index, animate: to.animate, speed: 1});
    }
    setInterval(function () { tickClock(canvas); }, 1000);
    fit(frame);
    window.addEventListener("resize", function () { fit(frame); });
    if (!opener) {
      // No control driving this page: the hash picks the finished step to show (the first one
      // without a hash) and the presenter keys move from there (moveAlone).
      var preview = function () {
        var h = parseHash(location.hash) || (episodes[0] ? {episode: episodes[0].id, index: 0} : null);
        if (h) stage.handle({type: "show", episode: h.episode, index: h.index, animate: false});
      };
      window.addEventListener("hashchange", preview);
      preview();
    }
    post({type: "ready"});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  return {create: create, keyMessage: keyMessage, parseHash: parseHash, tickClock: tickClock,
          localMove: localMove, hashFor: hashFor};
})();
