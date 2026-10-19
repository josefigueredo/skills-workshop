import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build
from tests.helpers import ROOT, TempTree, minimal_episode
from ws import capture, privacy

GIT_ENV = {
    "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}


def git(cwd, *args):
    env = dict(os.environ, **GIT_ENV)
    return subprocess.run(["git", "-C", str(cwd)] + list(args), env=env, check=True,
                          stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()


def make_skill_repo(skills_root, name):
    """A tiny git repo with two commits; returns (first_sha, second_sha)."""
    d = Path(skills_root) / name
    d.mkdir(parents=True)
    git(d, "init", "-q", "-b", "main")
    (d / "SKILL.md").write_text("one\n")
    git(d, "add", "-A")
    git(d, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "one")
    first = git(d, "rev-parse", "HEAD")
    (d / "SKILL.md").write_text("two\n")
    git(d, "add", "-A")
    git(d, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "two")
    return first, git(d, "rev-parse", "HEAD")


def ep_with(steps, **over):
    ep = minimal_episode(**over)
    ep["chapters"][0]["steps"] = steps
    return ep


def real(cmd, out=None, cwd="~", **extra):
    step = {"type": "term", "cmd": cmd, "out": out if out is not None else ["old"],
            "source": "real", "cwd": cwd}
    step.update(extra)
    return step


class RunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()

    def out_of(self, cmd, cwd="~", **kw):
        ep = capture.run(ep_with([real(cmd, cwd=cwd)]), self.home, **kw)
        return ep["chapters"][0]["steps"][0]["out"]

    def test_home_is_normalised_to_tilde(self):
        self.assertEqual(self.out_of("echo $HOME/x"), ["~/x"])

    def test_cwd_is_resolved_under_fake_home_and_pwd_is_normalised(self):
        (self.home / "sub").mkdir()
        self.assertEqual(self.out_of("pwd", cwd="~/sub"), ["~/sub"])
        self.assertEqual(self.out_of("pwd"), ["~"])

    def test_temp_root_is_normalised(self):
        self.assertEqual(self.out_of("echo %s" % self.home.parent), ["~"])

    def test_ansi_is_stripped(self):
        self.assertEqual(self.out_of(r"printf '\033[31mred\033[0m ok\n\033]0;title\007done\n'"),
                         ["red ok", "done"])

    def test_stderr_is_merged_and_exit_code_kept(self):
        self.assertEqual(self.out_of("echo hi; echo oops >&2; exit 3"), ["hi", "oops", "# exit 3"])

    def test_non_real_steps_are_untouched_and_not_run(self):
        steps = [{"type": "term", "cmd": "touch marker", "out": ["keep"], "source": "inferido"},
                 {"type": "ask", "text": "x", "source": "real"}]
        ep = ep_with(steps)
        new = capture.run(ep, self.home)
        self.assertEqual(new["chapters"], ep["chapters"])
        self.assertFalse((self.home / "marker").exists())

    def test_capture_only_steps_run_in_order_and_keep_their_flag(self):
        # They advance the state the visible steps read; the bundle drops them, capture never does.
        ep = ep_with([real("echo state > marker && echo set", capture_only=True),
                      real("cat marker")])
        new = capture.run(ep, self.home)
        hidden, shown = new["chapters"][0]["steps"]
        self.assertEqual(hidden["out"], ["set"])
        self.assertIs(hidden["capture_only"], True)
        self.assertEqual(shown["out"], ["state"])

    def test_input_episode_is_not_mutated(self):
        ep = ep_with([real("echo new")])
        before = copy.deepcopy(ep)
        capture.run(ep, self.home)
        self.assertEqual(ep, before)

    def test_env_is_isolated(self):
        out = self.out_of('echo "$NO_COLOR|$LANG|$USER|$LOGNAME|$GIT_AUTHOR_NAME <$GIT_AUTHOR_EMAIL>'
                          '|$GIT_COMMITTER_NAME|$GIT_CONFIG_GLOBAL"')
        self.assertEqual(out, ["1|C.UTF-8|persona|persona|Demo <demo@example.com>|Demo|/dev/null"])

    def test_parent_environment_does_not_leak(self):
        planted = {"WS_FAKE_SECRET": "planted-value", "TMPDIR": "/planted/tmpdir"}
        with mock.patch.dict(os.environ, planted):
            out = self.out_of("env")
        text = "\n".join(out)
        self.assertNotIn("WS_FAKE_SECRET", text)
        self.assertNotIn("planted", text)
        self.assertNotIn("TMPDIR", text)
        names = {line.split("=", 1)[0] for line in out if "=" in line}
        self.assertLessEqual(names, {"PATH", "HOME", "NO_COLOR", "LANG", "TERM", "USER", "LOGNAME",
                                     "PYTHONDONTWRITEBYTECODE", "PWD", "SHLVL", "_", "OLDPWD",
                                     "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                                     "GIT_COMMITTER_EMAIL", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
                                     "GIT_CONFIG_NOSYSTEM", "GIT_TERMINAL_PROMPT"})

    def test_path_is_explicit_and_never_under_real_home(self):
        real_home = os.path.realpath(os.path.expanduser("~"))
        for d in capture._path().split(os.pathsep):
            self.assertTrue(os.path.isabs(d), d)
            if real_home not in ("/", ""):
                self.assertFalse(os.path.realpath(d).startswith(real_home + "/"), d)

    def test_no_profile_is_read(self):
        (self.home / ".bash_profile").write_text("echo PROFILE\n")
        (self.home / ".bashrc").write_text("echo RC\n")
        self.assertEqual(self.out_of("echo x"), ["x"])

    def test_real_login_name_and_home_do_not_leak(self):
        with mock.patch("ws.capture.getpass.getuser", return_value="zelda"):
            real_home = os.path.expanduser("~")
            out = self.out_of('echo "zelda %s/proj"' % real_home)
        self.assertEqual(out, ["persona ~/proj"])

    def test_privacy_scan_is_clean_on_captured_result(self):
        real_home = os.path.expanduser("~")
        with mock.patch("ws.capture.getpass.getuser", return_value="zelda"):
            ep = capture.run(ep_with([real('echo "$HOME zelda $PWD %s/x"; whoami' % real_home)]),
                             self.home)
        step = ep["chapters"][0]["steps"][0]
        step["cmd"] = "show"  # the scan covers the captured output, not the command text
        p = self.home.parent / "ep.json"
        p.write_text(json.dumps(ep), encoding="utf-8")
        self.assertEqual(privacy.scan([p]), [])
        self.assertIn("persona", step["out"][0])

    def test_timeout_adds_marker_line(self):
        self.assertEqual(self.out_of("echo start; sleep 5", timeout=0.4), ["start", "# timeout"])

    def test_missing_cwd_raises_clear_error(self):
        with self.assertRaises(capture.CaptureError) as cm:
            capture.run(ep_with([real("ls", cwd="~/nope")]), self.home)
        self.assertIn("~/nope", str(cm.exception))

    def test_cwd_escaping_home_is_refused(self):
        with self.assertRaises(capture.CaptureError):
            capture.run(ep_with([real("ls", cwd="~/../x")]), self.home)


class NormaliseTests(unittest.TestCase):
    def test_home_prefix_respects_boundary(self):
        with mock.patch("ws.capture.os.path.expanduser", return_value="/Users/x"):
            out = capture.normalise("/Users/x/a /Users/xavier/b", Path("/nowhere/h"), user="zz")
        self.assertEqual(out, "~/a /Users/xavier/b")

    def test_both_login_names_are_replaced(self):
        with mock.patch("ws.capture.getpass.getuser", return_value="alice"), \
                mock.patch("ws.capture.pwd.getpwuid") as pw:
            pw.return_value.pw_name = "bob"
            out = capture.normalise("alice bob alicia", Path("/nowhere/h"))
        self.assertEqual(out, "persona persona alicia")

    def test_hostname_and_short_form_are_replaced(self):
        with mock.patch("ws.capture.socket.gethostname", return_value="box.local"):
            out = capture.normalise("box.local box boxes", Path("/nowhere/h"), user="zz")
        self.assertEqual(out, "mi-mac mi-mac boxes")


class DemoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name) / "t"

    def build(self):
        return subprocess.run(["bash", str(ROOT / "demo" / "setup.sh"), str(self.target)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True)

    def test_setup_builds_repo_whose_tests_pass(self):
        r = self.build()
        self.assertEqual(r.returncode, 0, r.stdout)
        repo = self.target / "mi-servicio"
        for name in ("api", "web", "docs", "README.md", ".git"):
            self.assertTrue((repo / name).exists(), name)
        t = subprocess.run(["python3", "-m", "unittest"], cwd=str(repo / "api"),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertEqual(t.returncode, 0, t.stdout)
        self.assertEqual(git(repo, "status", "--porcelain"), "")

    def test_history_is_fixed_and_deterministic(self):
        self.build()
        repo = self.target / "mi-servicio"
        log = git(repo, "log", "--format=%an <%ae>|%cn <%ce>|%aI|%cI")
        lines = log.splitlines()
        self.assertGreaterEqual(len(lines), 3)
        for line in lines:
            a, c, ad, cd = line.split("|")
            self.assertEqual(a, "Demo <demo@example.com>")
            self.assertEqual(c, "Demo <demo@example.com>")
            self.assertEqual(ad, cd)
            self.assertTrue(ad.startswith("2026-10-"), ad)
        first = self.target.parent / "t2"
        subprocess.run(["bash", str(ROOT / "demo" / "setup.sh"), str(first)], check=True)
        self.assertEqual(git(first / "mi-servicio", "rev-parse", "HEAD"), git(repo, "rev-parse", "HEAD"))

    def test_setup_refuses_existing_target(self):
        self.build()
        r = self.build()
        self.assertEqual(r.returncode, 1)
        self.assertIn("already exists", r.stdout)

    def test_setup_builds_only_the_generic_demo(self):
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ["mi-servicio"])
        self.assertEqual(git(self.target / "mi-servicio", "branch", "--format=%(refname:short)"), "main")

    def test_inherited_audit_prep_seeds_the_worker_output(self):
        # The pilot's real steps consume what the audit's workers would leave: candidate
        # files outside the repo and one local branch with a test-only red commit.
        self.assertEqual(self.build().returncode, 0)
        r = subprocess.run(["bash", str(ROOT / "demo" / "prep" / "inherited-audit.sh"), str(self.target)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        repo = self.target / "mi-servicio"
        main_before = git(repo, "rev-parse", "main")
        cands = self.target / "auditorias" / "candidatos"
        names = sorted(p.name for p in cands.iterdir())
        self.assertEqual(names, ["c-01.json", "c-02.json", "q-01.json"])
        for p in cands.iterdir():
            self.assertIn(json.loads(p.read_text(encoding="utf-8"))["report"],
                          ("correctness", "quality"))
        branch = "fix/c-01-descuento-sin-tope"
        self.assertEqual(git(repo, "rev-parse", "--abbrev-ref", "HEAD"), "main")
        self.assertEqual(git(repo, "rev-parse", branch + "~1"), main_before)
        self.assertEqual(git(repo, "diff", "--name-only", "main", branch),
                         "api/tests/test_discount_cap.py")
        self.assertEqual(git(repo, "status", "--porcelain"), "")
        log = git(repo, "log", "-1", "--format=%an <%ae>|%aI", branch)
        self.assertTrue(log.startswith("Demo <demo@example.com>|2026-10-17T11:00:00"), log)
        git(repo, "switch", "-q", branch)
        t = subprocess.run(["python3", "-m", "unittest", "tests.test_discount_cap"],
                           cwd=str(repo / "api"), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertNotEqual(t.returncode, 0)
        self.assertIn("AssertionError: -50.0 not greater than or equal to 0", t.stdout)

    def test_demo_carries_no_nested_git_in_the_workshop_repo(self):
        self.assertFalse((ROOT / "demo" / "mi-servicio").exists())


class PrepareHomeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.skills = self.tmp / "skills-root"
        self.skills.mkdir()
        self.home = self.tmp / "home"
        self.home.mkdir()

    def prepare(self, episode):
        with mock.patch.dict(os.environ, {"WS_SKILLS_ROOT": str(self.skills)}):
            capture.prepare_home(ROOT, episode, self.home)

    def test_builds_demo_and_checks_out_skill_commit(self):
        first, second = make_skill_repo(self.skills, "demo-skill")
        self.prepare(minimal_episode(skill={"repo": "demo-skill", "commit": first, "date": "x"}))
        self.assertTrue((self.home / "mi-servicio" / "api").is_dir())
        dest = self.home / "skills" / "demo-skill"
        self.assertEqual(git(dest, "rev-parse", "HEAD"), first)
        self.assertEqual((dest / "SKILL.md").read_text(), "one\n")

    def test_missing_skill_repo_names_repo_and_commit(self):
        with self.assertRaises(capture.CaptureError) as cm:
            self.prepare(minimal_episode(skill={"repo": "ghost", "commit": "abc1234", "date": "x"}))
        self.assertIn("ghost", str(cm.exception))
        self.assertIn("abc1234", str(cm.exception))

    def test_missing_commit_names_repo_and_commit(self):
        make_skill_repo(self.skills, "demo-skill")
        with self.assertRaises(capture.CaptureError) as cm:
            self.prepare(minimal_episode(skill={"repo": "demo-skill", "commit": "deadbee", "date": "x"}))
        self.assertIn("demo-skill", str(cm.exception))
        self.assertIn("deadbee", str(cm.exception))

    def test_origin_is_removed_when_source_has_none(self):
        first, _ = make_skill_repo(self.skills, "demo-skill")
        self.prepare(minimal_episode(skill={"repo": "demo-skill", "commit": first, "date": "x"}))
        self.assertEqual(git(self.home / "skills" / "demo-skill", "remote"), "")

    def test_origin_is_copied_from_source_origin(self):
        first, _ = make_skill_repo(self.skills, "demo-skill")
        git(self.skills / "demo-skill", "remote", "add", "origin", "https://example.com/org/demo-skill.git")
        self.prepare(minimal_episode(skill={"repo": "demo-skill", "commit": first, "date": "x"}))
        dest = self.home / "skills" / "demo-skill"
        self.assertEqual(git(dest, "remote", "get-url", "origin"), "https://example.com/org/demo-skill.git")

    def test_clone_does_not_see_parent_environment(self):
        first, _ = make_skill_repo(self.skills, "demo-skill")
        with mock.patch.dict(os.environ, {"GIT_DIR": "/planted/nowhere", "GIT_WORK_TREE": "/planted"}):
            self.prepare(minimal_episode(skill={"repo": "demo-skill", "commit": first, "date": "x"}))
        self.assertEqual(git(self.home / "skills" / "demo-skill", "rev-parse", "HEAD"), first)

    def _tree_with_prep(self, script):
        tree = TempTree()
        self.addCleanup(tree.__exit__, None, None, None)
        (tree.root / "demo" / "prep").mkdir(parents=True)
        shutil.copy(str(ROOT / "demo" / "setup.sh"), str(tree.root / "demo" / "setup.sh"))
        if script is not None:
            (tree.root / "demo" / "prep" / "demo.sh").write_text(script, encoding="utf-8")
        return tree.root

    def test_episode_prep_script_runs_after_demo_and_skill(self):
        first, _ = make_skill_repo(self.skills, "demo-skill")
        root = self._tree_with_prep(
            'set -e\n[ -d "$1/mi-servicio/.git" ] && [ -d "$1/skills/demo-skill" ]\n'
            'echo "$HOME" > "$1/prep-ran"\n')
        with mock.patch.dict(os.environ, {"WS_SKILLS_ROOT": str(self.skills)}):
            capture.prepare_home(root, minimal_episode(
                skill={"repo": "demo-skill", "commit": first, "date": "x"}), self.home)
        self.assertEqual((self.home / "prep-ran").read_text().strip(), str(self.home))

    def test_no_prep_script_is_fine_and_failing_one_is_reported(self):
        first, _ = make_skill_repo(self.skills, "demo-skill")
        ep = minimal_episode(skill={"repo": "demo-skill", "commit": first, "date": "x"})
        with mock.patch.dict(os.environ, {"WS_SKILLS_ROOT": str(self.skills)}):
            capture.prepare_home(self._tree_with_prep(None), ep, self.home)
            other = self.tmp / "home2"
            other.mkdir()
            with self.assertRaises(capture.CaptureError) as cm:
                capture.prepare_home(self._tree_with_prep("echo nope; exit 3\n"), ep, other)
        self.assertIn("demo/prep/demo.sh", str(cm.exception))

    def test_default_skill_source_is_next_to_the_workshop(self):
        env = {k: v for k, v in os.environ.items() if k != "WS_SKILLS_ROOT"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(capture.skill_source(Path("/a/b/ws"), "x"), Path("/a/b/x"))

    def test_skill_source_picks_the_first_root_holding_the_repo(self):
        one, two = self.tmp / "one", self.tmp / "two"
        make_skill_repo(two, "only-second")
        make_skill_repo(one, "both")
        make_skill_repo(two, "both")
        roots = os.pathsep.join([str(one), str(two)])
        with mock.patch.dict(os.environ, {"WS_SKILLS_ROOT": roots}):
            self.assertEqual(capture.skill_source(Path("/a/b/ws"), "only-second"), two / "only-second")
            self.assertEqual(capture.skill_source(Path("/a/b/ws"), "both"), one / "both")

    def test_skill_source_without_a_hit_falls_back_to_the_default(self):
        with mock.patch.dict(os.environ, {"WS_SKILLS_ROOT": str(self.tmp / "nope")}):
            self.assertEqual(capture.skill_source(Path("/a/b/ws"), "x"), Path("/a/b/x"))

    def test_prepare_home_error_lists_every_root_tried(self):
        one, two = self.tmp / "one", self.tmp / "two"
        one.mkdir()
        two.mkdir()
        root = self._tree_with_prep(None)
        ep = minimal_episode(skill={"repo": "ghost", "commit": "abc1234", "date": "x"})
        with mock.patch.dict(os.environ, {"WS_SKILLS_ROOT": os.pathsep.join([str(one), str(two)])}):
            with self.assertRaises(capture.CaptureError) as cm:
                capture.prepare_home(root, ep, self.home)
        self.assertIn(str(one / "ghost"), str(cm.exception))
        self.assertIn(str(two / "ghost"), str(cm.exception))


class CaptureCommandTests(unittest.TestCase):
    def setUp(self):
        self.tree = TempTree()
        self.addCleanup(self.tree.__exit__, None, None, None)
        (self.tree.root / "demo").mkdir()
        shutil.copy(str(ROOT / "demo" / "setup.sh"), str(self.tree.root / "demo" / "setup.sh"))
        self.skills = self.tree.root / "skills-root"
        self.skills.mkdir()
        self.first, _ = make_skill_repo(self.skills, "demo-skill")
        os_patch = mock.patch.dict(os.environ, {"WS_SKILLS_ROOT": str(self.skills)})
        os_patch.start()
        self.addCleanup(os_patch.stop)

    def episode(self, id_, order, cmd, repo="demo-skill"):
        return minimal_episode(
            id=id_, order=order,
            skill={"repo": repo, "commit": self.first, "date": "2026-10-19"},
            chapters=[{"id": "c", "title": "C", "screen": "terminal", "steps": [
                real(cmd, cwd="~/mi-servicio"),
                {"type": "ask", "text": "hola", "source": "inferido"}]}])

    def run_cli(self, *args):
        with mock.patch("sys.stdout") as out:
            code = build.main(["--root", str(self.tree.root), "capture"] + list(args))
        return code, "".join(c.args[0] for c in out.write.call_args_list)

    def test_capture_rewrites_file_keeping_order_and_format(self):
        p = self.tree.write("cursor", "01-a.json", self.episode("a", 1, "git log --format=%an -1; cat ~/skills/demo-skill/SKILL.md"))
        code, out = self.run_cli()
        self.assertEqual(code, 0, out)
        text = p.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("}\n"))
        data = json.loads(text)
        self.assertEqual(list(data), list(self.episode("a", 1, "x")))
        self.assertEqual(data["chapters"][0]["steps"][0]["out"], ["Demo", "one"])
        self.assertEqual(text, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        self.assertIn("a chapter c step 0", out)

    def test_invalid_tree_exits_1_and_runs_nothing(self):
        bad = self.episode("a", 1, "echo new")
        bad["chapters"][0]["steps"][0]["cwd"] = "~/../x"
        p = self.tree.write("cursor", "01-a.json", bad)
        before = p.read_text()
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(p.read_text(), before)

    def test_one_failure_does_not_stop_others_but_exits_1(self):
        ok = self.tree.write("cursor", "01-a.json", self.episode("a", 1, "echo fine"))
        bad = self.tree.write("cursor", "02-b.json", self.episode("b", 2, "echo x", repo="ghost"))
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(ok.read_text())["chapters"][0]["steps"][0]["out"], ["fine"])
        self.assertIn("ghost", out + "")
        self.assertEqual(json.loads(bad.read_text())["chapters"][0]["steps"][0]["out"], ["old"])

    def test_privacy_hit_fails_capture_and_leaves_file_untouched(self):
        p = self.tree.write("cursor", "01-a.json", self.episode("a", 1, "echo write to leaky@corp.org"))
        before = p.read_text()
        code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(p.read_text(), before)
        self.assertIn("email", out)
        self.assertNotIn("leaky@corp.org", out)
        self.assertIn("privacy hit", out)

    def test_leak_terms_file_gates_capture(self):
        terms = self.tree.root / "terms.txt"
        terms.write_text("forbiddenword\n")
        p = self.tree.write("cursor", "01-a.json", self.episode("a", 1, "echo a forbiddenword b"))
        before = p.read_text()
        with mock.patch.dict(os.environ, {"WS_LEAK_TERMS": str(terms)}):
            code, out = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(p.read_text(), before)

    def test_episode_filter(self):
        a = self.tree.write("cursor", "01-a.json", self.episode("a", 1, "echo A"))
        b = self.tree.write("cursor", "02-b.json", self.episode("b", 2, "echo B"))
        code, _ = self.run_cli("--episode", "b")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(a.read_text())["chapters"][0]["steps"][0]["out"], ["old"])
        self.assertEqual(json.loads(b.read_text())["chapters"][0]["steps"][0]["out"], ["B"])
        code, _ = self.run_cli("--episode", "nope")
        self.assertEqual(code, 2)

    def test_episode_without_real_steps_needs_no_skill(self):
        ep = self.episode("a", 1, "echo x", repo="ghost")
        ep["chapters"][0]["steps"][0]["source"] = "inferido"
        self.tree.write("cursor", "01-a.json", ep)
        code, _ = self.run_cli()
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
