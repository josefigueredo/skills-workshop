// Presenter control. The logic is a pure reducer; the DOM layer at the end is thin.
//
// Control.init(episodes) -> state
// Control.reduce(state, input) -> {state, outbox}   (never mutates `state`)
//   inputs: {kind:"key", key, shift}         key = KeyboardEvent.key (←/PageUp, →/PageDown, space, b)
//           {kind:"message", msg, now}       a message from the stage window; `now` is the
//                                            arrival time (Date.now()), not the last tick
//           {kind:"tick", now}               clock (ms); drives pings, lost and timers
//           {kind:"select-episode", id}  {kind:"select-chapter", i}  {kind:"speed", value}
//           {kind:"stage-opened", now}       the «Abrir escenario» / «Reabrir» click opened it
//           {kind:"stage-closed"}            the DOM layer saw the stage window closed
//   outbox: {to:"stage", msg}                content messages go only while the stage is
//                                            live (opened, ready, not lost); pings go while
//                                            it is opened, lost or not
// Finishing first: → while the stage still animates the current step (no done-animating for it yet)
// shows that same step finished instead of moving on; the next → advances. A resend shows the step
// finished too, so a stage that was down or reloaded never holds → back.
// Playback: space toggles `playing`. While playing, each done-animating for the current
// index asks Animate.autoplay; if it does not stop, the control sends the stage
// {type:"wait", delay, seq} and the STAGE times the delay (its window is visible, so its
// timers are not throttled), then answers {type:"advance", seq}. The control advances
// only if still playing and `seq` is unchanged (every show and every pause bumps it).
// Liveness: every stage message counts. A ping goes every PING_MS; the stage is lost when
// the oldest unanswered ping is LOST_MS old. A tick after a gap of LOST_MS or more (the
// control's timers were throttled) only sends a fresh ping and judges on later ticks.
// While lost the control keeps pinging; any stage message clears lost and resends the
// current show.
// Clock: it starts with the first move of the episode (→, space, ⇧ jumps, chapter pick)
// and runs until another episode is picked, paused or not (narration counts): see
// clockRuns. Each tick adds its time to the current chapter.
var Control = (function () {
  var PING_MS = 2000;
  var LOST_MS = 5000;
  var SPEEDS = [0.5, 1, 1.5, 2];

  function assign(a, b) { return Object.assign({}, a, b); }
  function none(s) { return {state: s, outbox: []}; }
  function stageFile(series) { return "serie-" + series + ".html"; }
  function findEpisode(eps, id) {
    for (var i = 0; i < eps.length; i++) if (eps[i].id === id) return eps[i];
    return null;
  }
  function episodeOf(s) { return findEpisode(s.episodes, s.episodeId); }
  function lastIndex(ep) { return Math.max(Nav.flatten(ep).length - 1, 0); }
  function zeros(ep) { return (ep.chapters || []).map(function () { return 0; }); }

  function init(episodes) {
    var eps = episodes || [];
    var ep = eps[0] || {id: null, series: "cursor", chapters: []};
    return {
      episodes: eps, episodeId: ep.id, index: 0, speed: 1, playing: false, blackout: false, animating: false,
      seq: 0, stageFile: stageFile(ep.series), stageSeries: null,
      needsOpen: true, stageLost: false, ready: false, stageIndex: null,
      now: 0, lastPing: 0, lastHeard: 0, pingPendingSince: null, lastTick: null,
      started: false, elapsed: 0, chapterMs: zeros(ep)
    };
  }

  function isLive(s) { return !s.needsOpen && !s.stageLost && s.ready; }
  function clockRuns(s) { return s.started; }
  function toStage(s, msg) { return isLive(s) ? [{to: "stage", msg: msg}] : []; }
  function showMsg(s, animate) {
    return {type: "show", episode: s.episodeId, index: s.index, animate: animate, speed: s.speed};
  }
  // Everything a freshly loaded stage needs: blackout first, so nothing flashes.
  function resend(s) {
    return (s.blackout ? toStage(s, {type: "blackout", on: true}) : []).concat(toStage(s, showMsg(s, false)));
  }
  // Stop playback; bumping seq voids any wait the stage still has pending.
  function pause(s) { return s.playing ? assign(s, {playing: false, seq: s.seq + 1}) : s; }

  function go(s, index, animate, patch) {
    var n = assign(s, assign({index: index, seq: s.seq + 1, started: true}, patch || {}));
    n = assign(n, {animating: !!animate && isLive(n)});
    return {state: n, outbox: toStage(n, showMsg(n, animate))};
  }

  function normalizeKey(key) { return Nav.keyAction(key); }

  function onKey(s, key, shift) {
    var ep = episodeOf(s);
    if (!ep) return none(s);
    var k = normalizeKey(key), last = lastIndex(ep), target;
    if (k === "right" && shift) {
      target = Nav.nextChapter(ep, s.index);
      return target === s.index ? none(s) : go(s, target, false, {playing: false});
    }
    if (k === "left" && shift) {
      target = Nav.prevChapter(ep, s.index);
      return target === s.index ? none(s) : go(s, target, false, {playing: false});
    }
    if (k === "right" && s.animating && isLive(s)) return go(s, s.index, false);
    if (k === "right") return s.index >= last ? none(s) : go(s, s.index + 1, true);
    if (k === "left") return s.index <= 0 ? none(s) : go(s, s.index - 1, false, {playing: false});
    if (k === "space") {
      if (s.playing) {
        var p = pause(s);
        return {state: p, outbox: toStage(p, {type: "wait-cancel"})};
      }
      return s.index >= last ? none(s) : go(s, s.index + 1, true, {playing: true});
    }
    if (k === "b") {
      var n = assign(s, {blackout: !s.blackout});
      return {state: n, outbox: toStage(n, {type: "blackout", on: n.blackout})};
    }
    return none(s);
  }

  // Any message proves the stage is there: it clears lost and, if the stage was down
  // (lost, or not ready yet), the current state is resent before the message is handled.
  function onMessage(s, msg, now) {
    if (!msg || typeof msg !== "object" || s.needsOpen) return none(s);
    if (now === undefined) now = s.now;
    var wasDown = s.stageLost || !s.ready;
    var n = assign(s, {ready: true, stageLost: false, lastHeard: now, pingPendingSince: null});
    var out = (wasDown || msg.type === "ready") ? resend(n) : [];
    if (out.length) n = assign(n, {animating: false});
    var r = handleMessage(n, msg);
    return {state: r.state, outbox: out.concat(r.outbox)};
  }

  function handleMessage(s, msg) {
    if (msg.type === "shown") return none(assign(s, {stageIndex: msg.index}));
    if (msg.type === "key") return onKey(s, msg.key, msg.shift);
    if (msg.type === "done-animating") {
      if (msg.index === s.index && s.animating) s = assign(s, {animating: false});
      if (!s.playing || msg.index !== s.index) return none(s);
      var a = Animate.autoplay(episodeOf(s), s.index, s.speed);
      if (a.stop) return none(pause(s));
      return {state: s, outbox: toStage(s, {type: "wait", delay: a.delay, seq: s.seq})};
    }
    if (msg.type === "advance") {
      var ep = episodeOf(s);
      if (!s.playing || msg.seq !== s.seq || !ep) return none(s);
      if (s.index >= lastIndex(ep)) return none(pause(s));
      return go(s, s.index + 1, true);
    }
    return none(s);  // ready, pong: liveness only
  }

  function ping(s, now) {
    var n = assign(s, {lastPing: now, pingPendingSince: s.pingPendingSince === null ? now : s.pingPendingSince});
    return {state: n, outbox: [{to: "stage", msg: {type: "ping"}}]};
  }

  function onTick(s, now) {
    var patch = {now: now, lastTick: now};
    var gap = s.lastTick === null ? 0 : now - s.lastTick;
    if (clockRuns(s) && gap > 0) {
      var ch = Nav.position(episodeOf(s), s.index).chapter;
      var ms = s.chapterMs.slice();
      ms[ch] = (ms[ch] || 0) + gap;
      patch.elapsed = s.elapsed + gap;
      patch.chapterMs = ms;
    }
    var n = assign(s, patch);
    if (n.needsOpen) return none(n);
    // Our own timers were asleep: whatever is pending cannot be judged; ask again.
    if (gap >= LOST_MS) return ping(assign(n, {pingPendingSince: null}), now);
    if (!n.stageLost && n.pingPendingSince !== null && now - n.pingPendingSince >= LOST_MS) {
      n = pause(assign(n, {stageLost: true}));
    }
    if (now - n.lastPing >= PING_MS) return ping(n, now);
    return none(n);
  }

  function reduce(s, input) {
    if (!input) return none(s);
    var ep = episodeOf(s), n, target;
    switch (input.kind) {
      case "key": return onKey(s, input.key, input.shift);
      case "message": return onMessage(s, input.msg, input.now);
      case "tick": return onTick(s, input.now);
      case "speed":
        if (SPEEDS.indexOf(input.value) < 0) return none(s);
        return none(assign(s, {speed: input.value}));
      case "select-chapter":
        if (!ep) return none(s);
        target = -1;
        Nav.flatten(ep).forEach(function (e, i) { if (target < 0 && e.chapter === input.i && e.step === -1) target = i; });
        if (target < 0) return none(s);
        return go(s, target, false, {playing: false});
      case "select-episode":
        var next = findEpisode(s.episodes, input.id);
        if (!next || next.id === s.episodeId) return none(s);
        var needsOpen = s.needsOpen || next.series !== s.stageSeries;
        n = assign(s, {episodeId: next.id, stageFile: stageFile(next.series), needsOpen: needsOpen,
                       ready: needsOpen ? false : s.ready, chapterMs: zeros(next), elapsed: 0});
        return go(n, 0, false, {playing: false, started: false});
      case "stage-opened":
        var now = input.now === undefined ? s.now : input.now;
        return none(assign(s, {needsOpen: false, stageLost: false, ready: false,
                               stageSeries: ep ? ep.series : null, now: now,
                               lastPing: now, lastHeard: now, pingPendingSince: null}));
      case "stage-closed":
        if (s.needsOpen || s.stageLost) return none(s);
        return none(pause(assign(s, {stageLost: true})));
    }
    return none(s);
  }

  // ---- panels (pure) ----
  function trim(text, max) {
    text = String(text || "").replace(/\s+/g, " ").trim();
    return text.length > max ? text.slice(0, max - 1) + "…" : text;
  }
  function stepLabel(st) {
    if (!st) return "";
    if (st.type === "ask") return trim(st.text, 80);
    if (st.type === "term") return trim(st.cmd, 80) || "(prompt vacío)";
    if (st.type === "tool") return trim(st.label, 80);
    if (st.type === "approve") return trim(st.title, 80);
    if (st.type === "page") return "Página · " + trim(st.title, 70);
    if (st.type === "worked") return "Trabajó " + st.seconds + " s";
    if (st.type === "say") {
      var line = String(st.md || "").split("\n").filter(function (l) { return l.trim(); })[0] || "";
      return trim(line.replace(/^#### |^- /, "").replace(/\*\*|`/g, ""), 80) || "(texto vacío)";
    }
    return st.type;
  }
  function upNext(ep, index) {
    var flat = Nav.flatten(ep);
    var i = Nav.clamp(ep, index);
    if (i >= flat.length - 1) return "Fin del episodio";
    var e = flat[i + 1];
    var ch = ep.chapters[e.chapter];
    if (e.step === -1) return "Placa · «" + ch.title + "»";
    return stepLabel(ch.steps[e.step]);
  }
  function notes(ep, index) {
    var e = Nav.flatten(ep)[Nav.clamp(ep, index)] || {chapter: 0, step: -1};
    var ch = (ep.chapters || [])[e.chapter] || {};
    var st = e.step >= 0 ? ch.steps[e.step] : null;
    var skill = ep.skill || {};
    return {notes: (st && st.notes) || "", source: st ? st.source : null,
            commit: skill.commit || "", date: skill.date || "", faq: ch.faq || []};
  }

  // ======================= DOM layer (control.html only) =======================
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
  function clock(ms) {
    var t = Math.round(ms / 1000);
    var m = Math.floor(t / 60), sec = t % 60;
    return m + ":" + (sec < 10 ? "0" : "") + sec;
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
  function $(id) { return document.getElementById(id); }

  function boot() {
    if (!$("ws-control")) return;
    var state = init(readEpisodes());
    var stageWin = null, durations = {}, previewKey = null, viewKey = null, chapterTimes = [];

    function dispatch(input) {
      var r = reduce(state, input);
      state = r.state;
      r.outbox.forEach(perform);
      update();
    }
    function perform(o) {
      if (o.to === "stage" && stageWin && !stageWin.closed) stageWin.postMessage(o.msg, "*");
    }
    // `closed` is the exact signal that the presenter closed the stage window.
    function checkClosed() {
      if (stageWin && stageWin.closed) dispatch({kind: "stage-closed"});
    }
    // Rebuild the panels only when what they show changes; ticks just refresh the times,
    // so clicks and text selection in the panels survive.
    function update() {
      var k = [state.episodeId, state.index, state.playing, state.blackout, state.stageLost,
               state.needsOpen, state.ready, state.speed].join("|");
      if (k !== viewKey) { viewKey = k; render(); } else renderTimes();
    }

    // The only place that opens the stage window (also serves «Reabrir»).
    function onOpenStageClick() {
      var win = window.open(state.stageFile, "ws-stage");
      if (!win) {
        $("banner-text").textContent = "El navegador bloqueó la ventana: permití ventanas emergentes para este archivo.";
        return;
      }
      stageWin = win;
      dispatch({kind: "stage-opened", now: Date.now()});
    }

    function duration(ep) {
      var k = ep.id + "@" + state.speed;
      if (!durations[k]) durations[k] = Animate.episodeDuration(ep, state.speed);
      return durations[k];
    }

    function renderSelectors(ep) {
      var sel = $("episode-select");
      if (!sel.options.length) {
        var groups = {};
        state.episodes.forEach(function (e) {
          if (!groups[e.series]) {
            groups[e.series] = document.createElement("optgroup");
            groups[e.series].label = e.series === "claude-code" ? "Serie Claude Code" : "Serie Cursor";
            sel.appendChild(groups[e.series]);
          }
          var o = el("option", null, e.order + " · " + e.title);
          o.value = e.id;
          groups[e.series].appendChild(o);
        });
      }
      sel.value = state.episodeId;
      var csel = $("chapter-select");
      if (csel.getAttribute("data-ep") !== ep.id) {
        clear(csel);
        ep.chapters.forEach(function (ch, i) {
          var o = el("option", null, (i + 1) + " · " + ch.title);
          o.value = String(i);
          csel.appendChild(o);
        });
        csel.setAttribute("data-ep", ep.id);
      }
      csel.value = String(Nav.position(ep, state.index).chapter);
    }

    function chapterTime(ep, i) {
      var spent = state.chapterMs[i] || 0;
      var when = "~" + clock(duration(ep).chapters[i].ms);
      if (i === Nav.position(ep, state.index).chapter && state.started) return "en curso " + clock(spent) + " / " + when;
      return spent > 0 ? clock(spent) + " / " + when : when;
    }
    function renderTimes() {
      var ep = episodeOf(state);
      if (!ep) return;
      chapterTimes.forEach(function (small, i) { small.textContent = chapterTime(ep, i); });
      $("clock").textContent = "⏱ " + clock(state.elapsed) + " en el episodio";
    }

    function renderChapters(ep, pos) {
      var list = clear($("chapters"));
      var est = duration(ep);
      chapterTimes = [];
      $("episode-label").textContent = "Episodio " + ep.order + " · " + ep.title;
      ep.chapters.forEach(function (ch, i) {
        var cls = "ch" + (i === pos.chapter ? " on" : i < pos.chapter ? " done" : "");
        var row = el("div", cls, (i + 1) + " · " + ch.title);
        var small = el("small", null, chapterTime(ep, i));
        chapterTimes.push(small);
        row.appendChild(small);
        row.addEventListener("click", function () { dispatch({kind: "select-chapter", i: i}); });
        list.appendChild(row);
        if (i !== pos.chapter) return;
        (ch.steps || []).forEach(function (st, j) {
          list.appendChild(el("div", "stp" + (j === pos.step ? " on" : ""), stepLabel(st)));
        });
      });
      $("estimate").textContent = "Estimado ~" + clock(est.total) + " a " + state.speed + "×";
    }

    function renderPreview(ep) {
      var box = $("mini"), canvas = $("mini-canvas");
      var k = ep.id + "#" + state.index;
      if (previewKey !== k) { Render.step(canvas, ep, state.index); previewKey = k; }
      canvas.style.transform = "scale(" + (box.clientWidth / 1600) + ")";
      $("mini-black").hidden = !state.blackout;
      var flat = Nav.flatten(ep);
      var status = state.needsOpen ? "sin escenario" : state.stageLost ? "escenario perdido"
        : "● en vivo · paso " + (state.index + 1) + " de " + flat.length;
      $("live").textContent = status;
      $("live").className = isLive(state) ? "live" : "off";
      $("next").textContent = upNext(ep, state.index);
    }

    function renderNotes(ep) {
      var n = notes(ep, state.index);
      $("notes-text").textContent = n.notes || (n.source === null ? "Placa del capítulo." : "Sin notas para este paso.");
      var src = $("notes-source");
      src.textContent = n.source || "placa";
      src.className = "pill src-" + (n.source || "card");
      $("notes-skill").textContent = "Skill en " + (n.commit || "?") + " · " + (n.date || "?");
      var faq = clear($("faq"));
      if (!n.faq.length) faq.appendChild(el("div", "q", "Sin preguntas cargadas para este capítulo."));
      n.faq.forEach(function (item) {
        var q = el("div", "q");
        q.appendChild(el("b", null, "«" + item.q + "»"));
        q.appendChild(el("div", null, item.a));
        faq.appendChild(q);
      });
    }

    function renderBanner() {
      var banner = $("banner");
      banner.hidden = !(state.needsOpen || state.stageLost);
      $("reopen-stage").hidden = !state.stageLost;
      if (state.stageLost) $("banner-text").textContent = "El escenario se cerró";
      else if (state.needsOpen) $("banner-text").textContent = "Abrí el escenario (" + state.stageFile + ") con «Abrir escenario».";
    }

    function render() {
      var ep = episodeOf(state);
      if (!ep) { $("banner").hidden = false; $("banner-text").textContent = "No hay episodios en este archivo."; return; }
      var pos = Nav.position(ep, state.index);
      renderSelectors(ep);
      renderChapters(ep, pos);
      renderPreview(ep);
      renderNotes(ep);
      renderBanner();
      $("play").classList.toggle("on", state.playing);
      $("blackout").classList.toggle("on", state.blackout);
      renderTimes();
      $("speed-select").value = String(state.speed);
    }

    $("open-stage").addEventListener("click", onOpenStageClick);
    $("reopen-stage").addEventListener("click", onOpenStageClick);
    Array.prototype.forEach.call(document.querySelectorAll("[data-key]"), function (b) {
      b.addEventListener("click", function () {
        dispatch({kind: "key", key: b.getAttribute("data-key"), shift: b.hasAttribute("data-shift")});
        b.blur();
      });
    });
    $("episode-select").addEventListener("change", function (ev) {
      dispatch({kind: "select-episode", id: ev.target.value});
      ev.target.blur();
    });
    $("chapter-select").addEventListener("change", function (ev) {
      dispatch({kind: "select-chapter", i: Number(ev.target.value)});
      ev.target.blur();
    });
    $("speed-select").addEventListener("change", function (ev) {
      dispatch({kind: "speed", value: Number(ev.target.value)});
      ev.target.blur();
    });
    document.addEventListener("keydown", function (ev) {
      var tag = ev.target && ev.target.tagName;
      if (tag === "SELECT" || tag === "INPUT" || tag === "TEXTAREA") return;
      if (!normalizeKey(ev.key) || ev.repeat || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      ev.preventDefault();
      dispatch({kind: "key", key: ev.key, shift: ev.shiftKey});
    });
    window.addEventListener("message", function (ev) {
      if (!stageWin || ev.source !== stageWin) return;
      dispatch({kind: "message", msg: ev.data, now: Date.now()});
    });
    window.addEventListener("resize", render);
    document.addEventListener("visibilitychange", checkClosed);
    setInterval(function () { checkClosed(); dispatch({kind: "tick", now: Date.now()}); }, 250);
    dispatch({kind: "tick", now: Date.now()});
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  return {init: init, reduce: reduce, notes: notes, upNext: upNext, stepLabel: stepLabel,
          stageFile: stageFile, normalizeKey: normalizeKey,
          SPEEDS: SPEEDS, PING_MS: PING_MS, LOST_MS: LOST_MS};
})();
