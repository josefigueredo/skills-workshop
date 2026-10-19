// Pure navigation over an episode: the global index is the flattened list of
// (chapter card + its steps). No DOM, no state.
var Nav = (function () {
  function flatten(ep) {
    var out = [];
    (ep.chapters || []).forEach(function (ch, i) {
      out.push({chapter: i, step: -1, kind: "card"});
      (ch.steps || []).forEach(function (st, j) {
        out.push({chapter: i, step: j, kind: st.type});
      });
    });
    return out;
  }

  function clamp(ep, i) {
    var last = flatten(ep).length - 1;
    return Math.max(0, Math.min(Math.floor(i) || 0, Math.max(last, 0)));
  }

  function nextChapter(ep, i) {
    var flat = flatten(ep);
    i = clamp(ep, i);
    for (var k = i + 1; k < flat.length; k++) {
      if (flat[k].step === -1) return k;
    }
    return Math.max(flat.length - 1, 0);
  }

  function prevChapter(ep, i) {
    var flat = flatten(ep);
    i = clamp(ep, i);
    var cur = i;
    while (cur > 0 && flat[cur].step !== -1) cur--;
    if (cur < i) return cur;
    for (var k = i - 1; k >= 0; k--) {
      if (flat[k].step === -1) return k;
    }
    return 0;
  }

  function position(ep, i) {
    var flat = flatten(ep);
    i = clamp(ep, i);
    var e = flat[i] || {chapter: 0, step: -1};
    var ch = (ep.chapters || [])[e.chapter] || {};
    return {chapter: e.chapter, step: e.step, total: flat.length, chapterTitle: ch.title};
  }

  return {flatten: flatten, clamp: clamp, nextChapter: nextChapter,
          prevChapter: prevChapter, position: position};
})();
