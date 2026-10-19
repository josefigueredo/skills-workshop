// Deliberately failing suite: proves the harness reports failures.
test("passes", function () { assertEqual(1 + 1, 2); });
test("fails on purpose", function () { assertEqual(1 + 1, 3); });
