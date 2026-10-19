#!/usr/bin/env python3
"""Workshop engine CLI. Thin: every command delegates to ws/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # usage errors exit 2, argparse default, made explicit
        self.print_usage(sys.stderr)
        sys.stderr.write("%s: error: %s\n" % (self.prog, message))
        raise SystemExit(2)


def cmd_validate(args) -> int:
    from ws import schema

    problems = schema.check_tree(Path(args.root))
    for p in problems:
        print(p)
    if problems:
        print("%d problem(s)" % len(problems))
        return 1
    print("ok: %d episode(s)" % len(schema.load_all(Path(args.root))))
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="build.py", description="Workshop engine: validate, check, capture, build.")
    parser.add_argument("--root", default=str(HERE), help="repo root (default: this repo)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate episode scripts").set_defaults(func=cmd_validate)
    return parser


def main(argv=None) -> int:
    args = make_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
