// Nav tests. Fixture: 3 chapters with 2, 0 and 3 steps -> flattened length 3 + 5 = 8.
function fixtureEpisode() {
  function steps(n) {
    var out = [];
    for (var k = 0; k < n; k++) out.push({type: "ask", text: "s" + k, source: "inferido"});
    return out;
  }
  return {chapters: [
    {id: "a", title: "Alpha", steps: steps(2)},
    {id: "b", title: "Beta", steps: steps(0)},
    {id: "c", title: "Gamma", steps: steps(3)}
  ]};
}
// Flattened: 0 card a, 1 a0, 2 a1, 3 card b, 4 card c, 5 c0, 6 c1, 7 c2

test("flatten counts cards plus steps", function () {
  var flat = Nav.flatten(fixtureEpisode());
  assertEqual(flat.length, 8);
  assertEqual(flat[0], {chapter: 0, step: -1, kind: "card"});
  assertEqual(flat[2], {chapter: 0, step: 1, kind: "ask"});
  assertEqual(flat[3], {chapter: 1, step: -1, kind: "card"});
  assertEqual(flat[7], {chapter: 2, step: 2, kind: "ask"});
});

test("flatten of an episode without chapters is empty", function () {
  assertEqual(Nav.flatten({chapters: []}), []);
});

test("clamp bounds the index", function () {
  var ep = fixtureEpisode();
  assertEqual(Nav.clamp(ep, -5), 0);
  assertEqual(Nav.clamp(ep, 0), 0);
  assertEqual(Nav.clamp(ep, 4), 4);
  assertEqual(Nav.clamp(ep, 7), 7);
  assertEqual(Nav.clamp(ep, 99), 7);
});

test("prevChapter from mid-chapter goes to that chapter's card", function () {
  var ep = fixtureEpisode();
  assertEqual(Nav.prevChapter(ep, 2), 0);
  assertEqual(Nav.prevChapter(ep, 7), 4);
});

test("prevChapter from a card goes to the previous card", function () {
  var ep = fixtureEpisode();
  assertEqual(Nav.prevChapter(ep, 4), 3);
  assertEqual(Nav.prevChapter(ep, 3), 0);
});

test("prevChapter from the first card stays", function () {
  assertEqual(Nav.prevChapter(fixtureEpisode(), 0), 0);
});

test("nextChapter jumps to the next card", function () {
  var ep = fixtureEpisode();
  assertEqual(Nav.nextChapter(ep, 0), 3);
  assertEqual(Nav.nextChapter(ep, 2), 3);
  assertEqual(Nav.nextChapter(ep, 3), 4);
});

test("nextChapter from the last chapter stays at the last index", function () {
  var ep = fixtureEpisode();
  assertEqual(Nav.nextChapter(ep, 4), 7);
  assertEqual(Nav.nextChapter(ep, 7), 7);
});

test("position reports chapter, step, total and title", function () {
  var ep = fixtureEpisode();
  assertEqual(Nav.position(ep, 0), {chapter: 0, step: -1, total: 8, chapterTitle: "Alpha"});
  assertEqual(Nav.position(ep, 6), {chapter: 2, step: 1, total: 8, chapterTitle: "Gamma"});
});
