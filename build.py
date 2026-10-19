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


def cmd_check(args) -> int:
    from ws import privacy

    root = Path(args.root)
    try:
        hits = privacy.scan([root / d for d in ("episodes", "demo", "dist")])
    except ValueError as exc:
        sys.stderr.write("check: %s\n" % exc)
        return 2
    for h in hits:
        print(h)
    if hits:
        print("%d privacy hit(s)" % len(hits))
        return 1
    print("ok: no privacy hits")
    return 0


def cmd_build(args) -> int:
    from ws import bundle, privacy, schema

    root = Path(args.root)
    problems = schema.check_tree(root)
    if problems:
        for p in problems:
            print(p)
        print("%d problem(s): nothing written" % len(problems))
        return 1
    try:
        rendered = bundle.render(root)
        hits = privacy.scan([root / "episodes", root / "demo"])
        for name, text in rendered.items():
            hits.extend(privacy.scan_text(text, "dist/" + name))
    except bundle.BundleError as exc:
        print("build: %s" % exc)
        return 1
    except ValueError as exc:
        sys.stderr.write("build: %s\n" % exc)
        return 2
    for h in hits:
        print(h)
    if hits:
        print("%d privacy hit(s): nothing written" % len(hits))
        return 1
    paths = bundle.write(root, rendered)
    print("ok: wrote %s" % ", ".join(p.name for p in paths))
    return 0


def cmd_capture(args) -> int:
    from ws import capture, schema

    root = Path(args.root)
    problems = schema.check_tree(root)
    if problems:
        for p in problems:
            print(p)
        print("%d problem(s): fix them before capturing" % len(problems))
        return 1
    return capture.capture_tree(root, args.episode)


def make_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="build.py", description="Workshop engine: validate, check, capture, build.")
    parser.add_argument("--root", default=str(HERE), help="repo root (default: this repo)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate episode scripts").set_defaults(func=cmd_validate)
    sub.add_parser("check", help="privacy scan of episodes/, demo/, dist/").set_defaults(func=cmd_check)
    sub.add_parser("build", help="validate, bundle into dist/, privacy-check; writes only if all pass") \
        .set_defaults(func=cmd_build)
    cap = sub.add_parser("capture", help="re-run `real` terminal steps in a fake HOME")
    cap.add_argument("--episode", metavar="ID", help="capture only this episode id")
    cap.set_defaults(func=cmd_capture)
    return parser


def main(argv=None) -> int:
    args = make_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
