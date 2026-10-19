"""tools/requisitos.sh against a fake PATH of stubs, and episode 0 kept in sync with it."""
from __future__ import annotations

import os
import shlex
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ROOT
from ws import schema

SCRIPT = ROOT / "tools" / "requisitos.sh"
EPISODE = ROOT / "episodes" / "cursor" / "00-antes-de-empezar.json"
BASH = "/bin/bash"  # attendees run it with the stock macOS bash 3.2

# name -> stub body (after the line that records the call)
STUBS = {
    "brew": 'echo "Homebrew 4.0.0"',
    "git": 'case "$1" in --version) echo "git version 2.40.0";; '
           'ls-remote) echo "0000000000000000000000000000000000000000\trefs/heads/main";; esac',
    "python3": 'echo "(3, 12)"',
    "uv": 'echo "uv 0.5.0"',
    "tmux": 'echo "tmux 3.4"',
    "jq": 'echo "jq-1.7"',
    # Real GitHub: greeting on stderr, exit 1.
    "ssh": 'echo "Hi persona! You\'ve successfully authenticated, but GitHub does not provide '
           'shell access." >&2; exit 1',
}


class Sandbox:
    """A temp dir with stub executables, a fake HOME and a fake /Applications."""

    def __init__(self, without=(), cursor=True):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.bin = base / "bin"
        self.home = base / "home"
        self.apps = base / "Applications"
        self.calls = base / "calls.log"
        self.brew_dir = base / "homebrew-bin"  # where an off-PATH brew would live
        for d in (self.bin, self.home, self.apps, self.brew_dir):
            d.mkdir()
        self.calls.write_text("", encoding="utf-8")
        if cursor:
            (self.apps / "Cursor.app").mkdir()
        for name, body in STUBS.items():
            if name in without:
                continue
            p = self.bin / name
            p.write_text('#!/bin/sh\necho "%s $*" >> "%s"\n%s\n' % (name, self.calls, body),
                         encoding="utf-8")
            p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def run(self, *args):
        env = {"PATH": "%s:/usr/bin:/bin" % self.bin, "HOME": str(self.home),
               "REQ_APPS_DIR": str(self.apps),
               "REQ_BREW_DIRS": str(self.brew_dir), "LANG": "en_US.UTF-8"}
        r = subprocess.run([BASH, str(SCRIPT)] + list(args), env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")

    def recorded(self):
        return self.calls.read_text(encoding="utf-8").splitlines()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()


def lines(text):
    return text.rstrip("\n").split("\n")


class CheckerTest(unittest.TestCase):
    REPO = "mi-org/mi-repo"

    def test_all_present_prints_all_ok_and_exits_0(self):
        with Sandbox() as sb:
            code, out, err = sb.run("--repo", self.REPO)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(err, "")
        got = lines(out)
        self.assertEqual(got[-1], "Todo listo.")
        checks = [l for l in got if l and l != "Todo listo."]
        self.assertEqual(len(checks), 9, got)
        self.assertTrue(all(l.startswith("✓ ") for l in checks), got)
        self.assertIn("✓ Acceso al repo mi-org/mi-repo", got)

    def test_missing_uv_prints_one_fix_and_exits_1(self):
        with Sandbox(without=("uv",)) as sb:
            code, out, _ = sb.run("--repo", self.REPO)
        self.assertEqual(code, 1)
        got = lines(out)
        bad = [l for l in got if l.startswith("✗ ")]
        self.assertEqual(bad, ["✗ uv — Corré: brew install uv"])
        self.assertEqual(got[-1], "Falta 1 cosa.")

    def test_two_missing_pluralises(self):
        with Sandbox(without=("uv", "tmux")) as sb:
            code, out, _ = sb.run("--offline")
        self.assertEqual(code, 1)
        self.assertEqual(lines(out)[-1], "Faltan 2 cosas.")

    def test_offline_never_calls_ssh_or_ls_remote(self):
        with Sandbox() as sb:
            code, out, _ = sb.run("--offline", "--repo", self.REPO)
            calls = sb.recorded()
        self.assertEqual(code, 0, out)
        self.assertFalse([c for c in calls if c.startswith("ssh") or "ls-remote" in c], calls)
        self.assertIn("– Clave SSH cargada en GitHub (sin conexión, no se revisó)", lines(out))
        self.assertIn("– Acceso al repo mi-org/mi-repo (sin conexión, no se revisó)", lines(out))

    def test_online_uses_batch_ssh_and_ls_remote(self):
        with Sandbox() as sb:
            sb.run("--repo", self.REPO)
            calls = sb.recorded()
        self.assertIn("ssh -T -o BatchMode=yes -o ConnectTimeout=5 git@github.com", calls)
        self.assertIn("git ls-remote --heads git@github.com:mi-org/mi-repo.git", calls)

    def test_without_repo_skips_repo_check(self):
        with Sandbox() as sb:
            code, out, _ = sb.run()
            calls = sb.recorded()
        self.assertEqual(code, 0)
        self.assertIn("– Acceso al repo de la org (no se pasó --repo)", lines(out))
        self.assertFalse([c for c in calls if "ls-remote" in c])

    def test_ssh_rejected_is_a_failure(self):
        with Sandbox(without=("ssh",)) as sb:
            p = sb.bin / "ssh"
            p.write_text('#!/bin/sh\necho "git@github.com: Permission denied (publickey)." >&2\nexit 255\n',
                         encoding="utf-8")
            p.chmod(0o755)
            code, out, _ = sb.run()
        self.assertEqual(code, 1)
        self.assertTrue(any(l.startswith("✗ Clave SSH cargada en GitHub — Cargá tu clave SSH en GitHub")
                            for l in lines(out)), out)

    def _replace_stub(self, sb, name, body):
        p = sb.bin / name
        p.write_text('#!/bin/sh\necho "%s $*" >> "%s"\n%s\n' % (name, sb.calls, body), encoding="utf-8")
        p.chmod(0o755)

    def test_unknown_host_key_gets_its_own_fix(self):
        # First connection on a fresh Mac: BatchMode cannot answer the host-key question.
        with Sandbox() as sb:
            self._replace_stub(sb, "ssh", 'echo "Host key verification failed." >&2; exit 255')
            code, out, _ = sb.run()
        self.assertEqual(code, 1)
        self.assertIn("✗ Clave SSH cargada en GitHub — Corré una vez: ssh -T git@github.com y respondé yes",
                      lines(out))

    def test_ssh_failure_skips_repo_instead_of_blaming_access(self):
        with Sandbox() as sb:
            self._replace_stub(sb, "ssh", 'echo "git@github.com: Permission denied (publickey)." >&2; exit 255')
            code, out, _ = sb.run("--repo", self.REPO)
            calls = sb.recorded()
        got = lines(out)
        self.assertEqual(code, 1)
        self.assertEqual(len([l for l in got if l.startswith("✗ ")]), 1, got)
        self.assertIn("– Acceso al repo mi-org/mi-repo (primero arreglá la clave SSH)", got)
        self.assertEqual(got[-1], "Falta 1 cosa.")
        self.assertFalse([c for c in calls if "ls-remote" in c], calls)

    def test_broken_git_skips_repo(self):
        # /usr/bin/git can be a Command Line Tools shim that exists but fails.
        with Sandbox() as sb:
            self._replace_stub(sb, "git", "exit 1")
            code, out, _ = sb.run("--repo", self.REPO)
        got = lines(out)
        self.assertEqual(code, 1)
        self.assertIn("✗ git — Corré: xcode-select --install", got)
        self.assertIn("– Acceso al repo mi-org/mi-repo (primero instalá git)", got)
        self.assertEqual(got[-1], "Falta 1 cosa.")

    def test_missing_brew_cascades_into_each_brew_fix(self):
        with Sandbox(without=("brew", "uv", "tmux")) as sb:
            code, out, _ = sb.run("--offline")
        got = lines(out)
        self.assertEqual(code, 1)
        self.assertIn("✗ Homebrew (brew) — Instalalo con el comando de brew.sh (copiar, pegar en la terminal, Enter)",
                      got)
        self.assertIn("✗ uv — primero instalá Homebrew (arriba), después: brew install uv", got)
        self.assertIn("✗ tmux — primero instalá Homebrew (arriba), después: brew install tmux", got)
        self.assertEqual(got[-1], "Faltan 3 cosas.")

    def test_brew_installed_off_path_gets_shellenv_fix(self):
        with Sandbox(without=("brew", "uv")) as sb:
            p = sb.brew_dir / "brew"
            p.write_text("#!/bin/sh\n", encoding="utf-8")
            p.chmod(0o755)
            code, out, _ = sb.run("--offline")
            d = str(sb.brew_dir)
        got = lines(out)
        self.assertEqual(code, 1)
        i = got.index("✗ Homebrew (brew) — Está instalado pero la terminal no lo encuentra. "
                      'Corré: eval "$(%s/brew shellenv)"' % d)
        self.assertEqual(got[i + 1], "  Para que quede siempre: echo 'eval \"$(%s/brew shellenv)\"' >> ~/.zprofile" % d)
        self.assertIn("✗ uv — primero arreglá Homebrew (arriba) y volvé a correr esto; si sigue, brew install uv",
                      got)
        self.assertEqual(got[-1], "Faltan 2 cosas.")

    def test_network_failure_asks_to_check_connection(self):
        for msg in ("ssh: Could not resolve hostname github.com: nodename nor servname provided",
                    "ssh: connect to host github.com port 22: Operation timed out",
                    "ssh: connect to host github.com port 22: Network is unreachable",
                    "ssh: connect to host github.com port 22: Connection refused"):
            with Sandbox() as sb:
                self._replace_stub(sb, "ssh", 'echo "%s" >&2; exit 255' % msg)
                code, out, _ = sb.run("--repo", self.REPO)
            got = lines(out)
            self.assertEqual(code, 1, msg)
            self.assertIn("✗ Clave SSH cargada en GitHub — No se pudo llegar a GitHub. "
                          "Revisá tu conexión a internet y volvé a correr", got, msg)
            self.assertIn("– Acceso al repo mi-org/mi-repo (primero resolvé la conexión)", got, msg)

    def test_publickey_denied_points_to_key_guide_and_help(self):
        with Sandbox() as sb:
            self._replace_stub(sb, "ssh", 'echo "git@github.com: Permission denied (publickey)." >&2; exit 255')
            code, out, _ = sb.run()
        self.assertEqual(code, 1)
        self.assertIn("✗ Clave SSH cargada en GitHub — Cargá tu clave SSH en GitHub: "
                      "docs.github.com/es/authentication/connecting-to-github-with-ssh; "
                      "si no sabés cómo, pedí ayuda antes del curso", lines(out))

    def test_unrecognised_ssh_error_falls_back_to_key_guide(self):
        with Sandbox() as sb:
            self._replace_stub(sb, "ssh", 'echo "something odd" >&2; exit 255')
            code, out, _ = sb.run()
        self.assertEqual(code, 1)
        self.assertIn("✗ Clave SSH cargada en GitHub — Cargá tu clave SSH en GitHub: "
                      "docs.github.com/es/authentication/connecting-to-github-with-ssh", lines(out))

    def test_old_python_is_a_failure(self):
        with Sandbox(without=("python3",)) as sb:
            p = sb.bin / "python3"
            p.write_text('#!/bin/sh\necho "(3, 8)"\n', encoding="utf-8")
            p.chmod(0o755)
            code, out, _ = sb.run("--offline")
        self.assertEqual(code, 1)
        self.assertIn("✗ Python 3.9 o más (python3) — Tenés Python 3.8. Corré: brew install python",
                      lines(out))

    def test_cursor_on_path_counts_without_app(self):
        with Sandbox(cursor=False) as sb:
            code, out, _ = sb.run("--offline")
            self.assertIn("✗ Cursor — Instalá Cursor desde cursor.com", lines(out))
            self.assertEqual(code, 1)
            p = sb.bin / "cursor"
            p.write_text("#!/bin/sh\n", encoding="utf-8")
            p.chmod(0o755)
            code, out, _ = sb.run("--offline")
        self.assertEqual(code, 0, out)
        self.assertIn("✓ Cursor", lines(out))

    def test_help_is_spanish_and_exits_0(self):
        with Sandbox() as sb:
            code, out, _ = sb.run("--help")
            calls = sb.recorded()
        self.assertEqual(code, 0)
        self.assertIn("Uso: bash requisitos.sh", out)
        self.assertEqual(calls, [])

    def test_bad_arguments_exit_2(self):
        with Sandbox() as sb:
            self.assertEqual(sb.run("--nope")[0], 2)
            self.assertEqual(sb.run("--repo")[0], 2)
            self.assertEqual(sb.run("--repo", "not a repo")[0], 2)


class EpisodeZeroTest(unittest.TestCase):
    """The checker steps are `inferido` (ruling R5): they must equal the real checker run on stubs."""

    @classmethod
    def setUpClass(cls):
        cls.ep = schema.load(EPISODE)
        cls.chapters = {c["id"]: c for c in cls.ep["chapters"]}

    def checker_args(self, step):
        argv = shlex.split(step["cmd"])
        self.assertEqual(argv[:2], ["bash", "~/Downloads/requisitos.sh"], step["cmd"])
        return argv[2:]

    def checker_steps(self, chapter_id):
        return [s for s in self.chapters[chapter_id]["steps"]
                if s["type"] == "term" and "requisitos.sh" in s["cmd"]]

    def test_episode_validates(self):
        self.assertEqual(schema.validate(self.ep, EPISODE.name), [])
        self.assertEqual(self.ep["id"], "antes-de-empezar")
        self.assertEqual(self.ep["order"], 0)
        self.assertEqual(list(self.chapters), ["que-necesitas", "verificarlo", "si-falta-algo", "cierre"])

    def test_every_step_has_notes_and_chapters_have_faq(self):
        for ch in self.ep["chapters"]:
            self.assertTrue(2 <= len(ch.get("faq", [])) <= 4, ch["id"])
            for st in ch["steps"]:
                self.assertTrue(st.get("notes", "").strip(), (ch["id"], st))

    def test_checker_steps_are_inferido(self):
        for cid in ("verificarlo", "si-falta-algo"):
            for st in self.checker_steps(cid):
                self.assertEqual(st["source"], "inferido")

    def test_verificarlo_output_equals_checker(self):
        (step,) = self.checker_steps("verificarlo")
        with Sandbox() as sb:
            code, out, _ = sb.run(*self.checker_args(step))
        self.assertEqual(code, 0)
        self.assertEqual(step["out"], lines(out))

    def test_si_falta_algo_outputs_equal_checker(self):
        missing, rerun = self.checker_steps("si-falta-algo")
        with Sandbox(without=("uv",)) as sb:
            code, out, _ = sb.run(*self.checker_args(missing))
        self.assertEqual(code, 1)
        self.assertEqual(missing["out"], lines(out))
        with Sandbox() as sb:
            code, out, _ = sb.run(*self.checker_args(rerun))
        self.assertEqual(code, 0)
        self.assertEqual(rerun["out"], lines(out))
        fix = [s for s in self.chapters["si-falta-algo"]["steps"] if s["type"] == "term"
               and s["cmd"] == "brew install uv"]
        self.assertEqual(len(fix), 1)

    def test_invitation_in_last_notes_has_requirements_and_command(self):
        notes = self.ep["chapters"][-1]["steps"][-1]["notes"]
        (step,) = self.checker_steps("verificarlo")
        self.assertIn(step["cmd"], notes)
        for item in ("brew", "git", "Python", "uv", "tmux", "jq", "Cursor", "SSH"):
            self.assertIn(item, notes)


if __name__ == "__main__":
    unittest.main()
