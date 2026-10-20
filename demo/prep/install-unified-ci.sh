#!/usr/bin/env bash
# Demo state for the install-unified-ci episode, on top of demo/setup.sh.
# Usage: demo/prep/install-unified-ci.sh <home>   (capture runs it after building <home>/mi-servicio)
#
# A repo that still carries its own CI: two small custom workflows (test and lint), committed
# on main, so the episode's `real` steps have something to list. Nothing here deploys, pushes
# or talks to the network; the workflows are plain files that are never executed.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: install-unified-ci.sh <home>" >&2; exit 2; }
T="$(cd "$1" && pwd)"
cd "$T/mi-servicio"

export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null
export GIT_AUTHOR_NAME=Demo GIT_AUTHOR_EMAIL=demo@example.com
export GIT_COMMITTER_NAME=Demo GIT_COMMITTER_EMAIL=demo@example.com
export GIT_AUTHOR_DATE="2026-10-17T11:00:00+00:00" GIT_COMMITTER_DATE="2026-10-17T11:00:00+00:00"

mkdir -p .github/workflows
cat > .github/workflows/test.yml <<'P'
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd api && python3 -m unittest
P
cat > .github/workflows/lint.yml <<'P'
name: lint
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 -m compileall api
P
git add -A && git -c commit.gpgsign=false commit -q -m "ci: custom test and lint workflows"
