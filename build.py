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
    problems = schema.check_tree(root, capturing=True)
    if problems:
        for p in problems:
            print(p)
        print("%d problem(s): fix them before capturing" % len(problems))
        return 1
    return capture.capture_tree(root, args.episode)


def cmd_new(args) -> int:
    from ws import scaffold

    try:
        text = args.minutes
        if text is None and sys.stdin.isatty():
            text = input("¿Cuánto tiene que durar el episodio? Minutos MIN-MAX [6-12]: ").strip() or None
        minutes = scaffold.parse_minutes(text) if text is not None else scaffold.DEFAULT_MINUTES
        path = scaffold.create(Path(args.root), args.skill_repo, args.series, args.order, id=args.id,
                               minutes=minutes)
    except scaffold.ScaffoldError as exc:
        print("new: %s" % exc)
        return 1
    print("ok: wrote %s/%s" % (path.parent.name, path.name))
    print("minutes: %d-%d%s" % (minutes + ("" if text is not None else
                                           " (default; pass --minutes MIN-MAX to set another range)",)))
    print("next: fill every COMPLETAR (validate and build refuse them), then capture and build")
    return 0


def cmd_duration(args) -> int:
    from ws import duration

    return duration.report(Path(args.root), args.episode)


def cmd_sync(args) -> int:
    from ws import sync

    return sync.run(Path(args.root), args.repo, args.check)


def make_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="build.py", description="Workshop engine: validate, check, capture, build, new, duration, sync.")
    parser.add_argument("--root", default=str(HERE), help="repo root (default: this repo)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate episode scripts").set_defaults(func=cmd_validate)
    sub.add_parser("check", help="privacy scan of episodes/, demo/, dist/").set_defaults(func=cmd_check)
    sub.add_parser("build", help="validate, bundle into dist/, privacy-check; writes only if all pass") \
        .set_defaults(func=cmd_build)
    new = sub.add_parser("new", help="write an episode skeleton for a skill (every text is COMPLETAR)")
    new.add_argument("skill_repo", help="skill repo name; also the episode id unless --id is given")
    new.add_argument("--id", metavar="ID", help="episode id (default: the repo name); for a monorepo with several skills")
    new.add_argument("--series", choices=("cursor", "claude-code"), default="cursor")
    new.add_argument("--order", type=int, metavar="N", help="position in the series (default: next free)")
    new.add_argument("--minutes", metavar="MIN-MAX",
                     help="how long the episode should last, in minutes (asked on a terminal; default 6-12)")
    new.set_defaults(func=cmd_new)
    cap = sub.add_parser("capture", help="re-run `real` terminal steps in a fake HOME")
    cap.add_argument("--episode", metavar="ID", help="capture only this episode id")
    cap.set_defaults(func=cmd_capture)
    dur = sub.add_parser("duration", help="screen + narration time per episode and chapter (needs Chrome)")
    dur.add_argument("--episode", metavar="ID", help="only this episode id")
    dur.set_defaults(func=cmd_duration)
    syn = sub.add_parser("sync", help="copy each skill's workshop/episodes into episodes/ (the mirror)")
    syn.add_argument("--repo", action="append", metavar="REPO",
                     help="only this skill repo (repeatable; default: every repo of the mirror)")
    syn.add_argument("--check", action="store_true", help="report drift without writing; exit 1 if any")
    syn.set_defaults(func=cmd_sync)
    return parser


def main(argv=None) -> int:
    args = make_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
