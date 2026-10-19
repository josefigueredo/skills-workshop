// Stage page: what the audience sees. It holds (episode, index), renders or animates on
// `show` and answers the control. Messages (see the episode format):
//   in : {type:"show", episode, index, animate, speed} | {type:"blackout", on} | {type:"ping"}
//   out: {type:"ready"} on load, {type:"shown", episode, index}, then
//        {type:"done-animating", index} (only for the latest show), {type:"pong"},
//        {type:"key", key, shift} for the presenter's keys pressed while the stage has focus.
// A `show` animates only when animate is true and index == current + 1 in the same
// episode; anything else cancels the running animation and renders the finished state.
// The stage never shows notes, sources or the skill commit: it only calls Render.step.
//
// Stage.create(opts) -> {handle(msg) -> Promise, current()} is the testable core:
//   opts: {canvas (Render container), blackout (element toggled with .hidden), episodes,
//          post(msg), schedule?, unschedule? (passed to Animate.run)}.
// The DOM bootstrap at the end runs only on the page with #ws-stage-root.
var Stage = (function () {
  var FADE = "ws-fade-in";
  var KEYS = ["ArrowLeft", "ArrowRight", " ", "Spacebar", "b", "B"];

  function create(opts) {
    var canvas = opts.canvas, blackout = opts.blackout;
    var post = opts.post || function () {};
    var byId = {};
    (opts.episodes || []).forEach(function (ep) { if (ep && ep.id) byId[ep.id] = ep; });
    var cur = null;   // {episode, index} of the latest show
    var seq = 0;      // id of the latest show; older runs stay silent
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
      var run = Animate.run(canvas, ep, index, {speed: speed, schedule: opts.schedule, unschedule: opts.unschedule});
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
      return Promise.resolve();
    }

    return {handle: handle, current: function () { return cur; }};
  }

  // The keydown the stage forwards to the control, or null.
  function keyMessage(ev) {
    if (!ev || KEYS.indexOf(ev.key) < 0) return null;
    return {type: "key", key: ev.key, shift: !!ev.shiftKey};
  }

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
    var opener = window.opener;
    function post(msg) { if (opener && !opener.closed) opener.postMessage(msg, "*"); }
    var stage = create({canvas: document.getElementById("ws-canvas"),
                        blackout: document.getElementById("ws-blackout"),
                        episodes: readEpisodes(), post: post});
    window.addEventListener("message", function (ev) {
      if (!opener || ev.source !== opener) return;
      stage.handle(ev.data);
    });
    document.addEventListener("keydown", function (ev) {
      var msg = keyMessage(ev);
      if (!msg) return;
      ev.preventDefault();
      post(msg);
    });
    fit(frame);
    window.addEventListener("resize", function () { fit(frame); });
    post({type: "ready"});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  return {create: create, keyMessage: keyMessage};
})();
