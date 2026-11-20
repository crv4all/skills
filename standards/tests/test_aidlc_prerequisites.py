"""``check_prerequisites.py`` names what is missing before a first paddock.

Everything runs against a fake skills directory, a fake planning repo and an
isolated git configuration, so the result never depends on the developer's machine.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from test_shared_aidlc_files import SHARED

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts"
SKILLS = (
    "crv-aidlc",
    "crv-aidlc-reverse-engineering",
    "crv-aidlc-hla",
    "crv-aidlc-tdd",
    "crv-aidlc-inception",
    "crv-aidlc-construction",
    "crv-aidlc-operation",
)
JIRA = ("crv-create-jira-epic", "crv-create-jira-story")
FIXED = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.test"}


def fake_bin(folder: Path) -> Path:
    """A PATH folder whose ssh never touches a real key or the network."""
    folder.mkdir()
    ssh = folder / "ssh"
    ssh.write_text(
        '#!/bin/sh\nif [ "$FAKE_SSH" = ok ]; then\n'
        '  echo "remote: Shell access is not supported." >&2; exit 1\nfi\n'
        'echo "Permission denied (publickey)." >&2; exit 255\n',
        encoding="utf-8",
    )
    keygen = folder / "ssh-keygen"
    keygen.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for tool in (ssh, keygen):
        tool.chmod(0o755)
    return folder


class Env:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.skills = tmp / "skills"
        self.root = tmp / "planning"
        self.marker = tmp / "marker"
        self.env = {
            "PATH": f"{fake_bin(tmp / 'bin')}{os.pathsep}{os.environ['PATH']}",
            "FAKE_SSH": "ok",
            "HOME": str(tmp / "home"),
            "GIT_CONFIG_GLOBAL": str(tmp / "gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "XDG_CONFIG_HOME": str(tmp / "xdg"),
            **FIXED,
            "GIT_COMMITTER_NAME": "T",
            "GIT_COMMITTER_EMAIL": "t@example.test",
        }
        (tmp / "home").mkdir()
        (tmp / "gitconfig").write_text("[user]\n\tname = T\n\temail = t@example.test\n")
        self.script = self.skills / "crv-aidlc" / "scripts" / "check_prerequisites.py"

    def git(self, path: Path, *args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True, text=True, env=self.env
        )
        assert done.returncode == 0, done.stderr
        return done.stdout.strip()

    def run(self, *args: str, root: bool = True) -> tuple[int, str]:
        extra = ["--root", str(self.root)] if root else []
        done = subprocess.run(
            [sys.executable, str(self.script), *extra, "--marker-dir", str(self.marker), *args],
            capture_output=True,
            text=True,
            env=self.env,
            cwd=self.tmp,
            timeout=60,
        )
        return done.returncode, done.stdout

    def data(self, *args: str, root: bool = True) -> tuple[int, dict[str, Any]]:
        code, out = self.run("--format", "json", *args, root=root)
        return code, json.loads(out)


def status(data: dict[str, Any], cid: str) -> str:
    return next(c["status"] for c in data["checks"] if c["id"] == cid)


@pytest.fixture
def env(tmp_path: Path) -> Env:
    e = Env(tmp_path)
    for name in SKILLS + JIRA:
        (e.skills / name).mkdir(parents=True)
        (e.skills / name / "SKILL.md").write_text("x", encoding="utf-8")
    for rel, canonical, copies in SHARED:
        for name in (canonical, *copies):
            target = e.skills / name / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"shared {rel}\n", encoding="utf-8")
    scripts = e.skills / "crv-aidlc" / "scripts"
    shutil.copy(REAL / "check_prerequisites.py", scripts)
    for rel in ("scripts/lint_questions.py", "assets/stages.json"):  # the linter reads both
        for name in SKILLS:
            shutil.copy(REAL.parent / rel, e.skills / name / rel)
    (e.root / "paddocks").mkdir(parents=True)
    (e.root / "codekb").mkdir()
    (e.root / "docs").mkdir()
    (e.root / "docs" / "process.md").write_text("# p\n", encoding="utf-8")
    e.git(e.root, "init", "-q")
    return e


def test_all_required_checks_pass(env: Env) -> None:
    code, data = env.data()
    assert code == 0 and data["ok"], data
    assert [status(data, c) for c in ("R1", "R2", "R3", "R4", "R5")] == ["ok"] * 5
    assert [status(data, c) for c in ("R6", "R7", "R8")] == ["ok"] * 3
    assert status(data, "R9") == "skipped"
    assert [status(data, c) for c in ("C1", "C2", "C3", "C4")] == ["skipped"] * 4


def test_text_output_is_short_and_ends_with_a_verdict(env: Env) -> None:
    code, out = env.run()
    assert code == 0 and len(out.splitlines()) <= 25
    assert out.splitlines()[-1] == "Verdict: ok"
    shutil.rmtree(env.skills / "crv-aidlc-tdd")
    code, out = env.run()
    assert code == 1 and len(out.splitlines()) <= 25
    assert "MISSING" in out and "  fix: " in out and out.splitlines()[-1] == "Verdict: not ready"


def test_a_missing_skill_is_named_with_the_install_command(env: Env) -> None:
    shutil.rmtree(env.skills / "crv-aidlc-tdd")
    code, data = env.data()
    check = next(c for c in data["checks"] if c["id"] == "R3")
    assert code == 1 and check["status"] == "missing" and "crv-aidlc-tdd" in check["detail"]
    assert "./install.sh" in check["fix"]


def test_a_stale_shared_file_is_outdated_and_names_the_skill(env: Env) -> None:
    (env.skills / "crv-aidlc-hla" / "assets" / "stages.json").write_text("old", encoding="utf-8")
    code, data = env.data()
    check = next(c for c in data["checks"] if c["id"] == "R4")
    assert code == 1 and check["status"] == "outdated" and "crv-aidlc-hla" in check["detail"]


def test_no_git_identity_fails(env: Env) -> None:
    (env.tmp / "gitconfig").write_text("", encoding="utf-8")
    code, data = env.data()
    check = next(c for c in data["checks"] if c["id"] == "R2")
    assert code == 1 and check["status"] == "missing" and "user.name" in check["detail"]
    assert check["fix"].startswith("git config --global user.name")


def test_no_planning_repo_fails_with_the_root_hint(env: Env) -> None:
    code, data = env.data(root=False)
    check = next(c for c in data["checks"] if c["id"] == "R5")
    assert code == 1 and check["status"] == "missing" and "--root" in check["fix"]


def test_a_planning_repo_is_found_by_walking_up(env: Env) -> None:
    (env.root / "sub").mkdir()
    done = subprocess.run(
        [sys.executable, str(env.script), "--format", "json", "--marker-dir", str(env.marker)],
        capture_output=True, text=True, env=env.env, cwd=env.root / "sub", timeout=60,
    )  # fmt: skip
    assert status(json.loads(done.stdout), "R5") == "ok"


def test_a_planning_repo_without_git_or_folders_fails(env: Env) -> None:
    shutil.rmtree(env.root / "codekb")
    code, data = env.data()
    check = next(c for c in data["checks"] if c["id"] == "R5")
    assert code == 1 and "codekb" in check["detail"]


def make_registry(env: Env) -> Path:
    registry = env.tmp / "registry"
    registry.mkdir()
    env.git(registry, "init", "-q")
    (registry / "a.md").write_text("a", encoding="utf-8")
    env.git(registry, "add", ".")
    env.git(registry, "commit", "-q", "-m", "one")
    return registry


def test_the_adr_index_behind_the_registry_is_outdated(env: Env) -> None:
    registry = make_registry(env)
    index = {
        "schema": 1,
        "registry": "registry",
        "registry_commit": env.git(registry, "rev-parse", "HEAD"),
    }
    (env.root / "architecture-index.json").write_text(json.dumps(index), encoding="utf-8")
    code, data = env.data("--architecture-ref", str(registry))
    assert code == 0 and status(data, "C1") == "ok"
    (registry / "b.md").write_text("b", encoding="utf-8")
    env.git(registry, "add", ".")
    env.git(registry, "commit", "-q", "-m", "two")
    code, data = env.data("--architecture-ref", str(registry))
    check = next(c for c in data["checks"] if c["id"] == "C1")
    assert code == 0 and check["status"] == "outdated" and "build_adr_index.py" in check["fix"]
    assert data["verdict"] == "ok, with warnings"


def test_an_adr_ref_that_is_not_a_git_repository_is_reported(env: Env) -> None:
    plain = env.tmp / "plain"
    plain.mkdir()
    code, data = env.data("--architecture-ref", str(plain))
    assert code == 0 and status(data, "C1") == "missing"


def test_jira_is_skipped_without_the_flag_and_missing_with_it(env: Env) -> None:
    code, data = env.data()
    assert status(data, "C2") == "skipped"
    code, data = env.data("--jira")
    check = next(c for c in data["checks"] if c["id"] == "C2")
    assert code == 0 and check["status"] == "missing" and "jira_setup.py" in check["fix"]
    assert any("Jira tools" in note for note in data["notes"])
    config = env.tmp / "xdg" / "crv-agent-skills" / "jira.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"site": "https://x.atlassian.net", "project_key": "ABC"}))
    assert status(env.data("--jira")[1], "C2") == "ok"
    shutil.rmtree(env.skills / "crv-create-jira-story")
    assert status(env.data("--jira")[1], "C2") == "missing"


def test_an_invalid_presets_file_is_outdated(env: Env) -> None:
    (env.root / "docs" / "presets.md").write_text("## P-1 Topic\nAnswer: x\n", encoding="utf-8")
    code, data = env.data()
    check = next(c for c in data["checks"] if c["id"] == "C3")
    assert code == 0 and check["status"] == "outdated" and "lint_questions.py" in check["fix"]
    (env.root / "docs" / "presets.md").write_text("# Presets\n", encoding="utf-8")
    assert status(env.data()[1], "C3") == "ok"


def test_a_wrong_flag_exits_2(env: Env) -> None:
    assert env.run("--nope")[0] == 2


def test_the_marker_is_written_and_honoured_until_a_shared_file_changes(env: Env) -> None:
    assert env.run()[0] == 0
    marker = json.loads((env.marker / "prerequisites.json").read_text(encoding="utf-8"))
    assert marker["verdict"] == "ok" and re.match(r"\d{4}-\d{2}-\d{2}$", marker["date"])
    shutil.rmtree(env.root / "codekb")  # would fail R5 if the checks ran
    code, out = env.run("--if-stale")
    assert code == 0 and out == f"ok, checked {marker['date']}\n"
    (env.skills / "crv-aidlc-hla" / "assets" / "stages.json").write_text("new", encoding="utf-8")
    code, out = env.run("--if-stale")
    assert code == 1 and "Verdict" in out


def test_a_failed_run_is_not_remembered_as_ok(env: Env) -> None:
    shutil.rmtree(env.root / "codekb")
    assert env.run()[0] == 1
    assert env.run("--if-stale")[0] == 1


def test_an_unwritable_marker_is_only_a_warning(env: Env) -> None:
    env.marker.write_text("a file, not a folder", encoding="utf-8")
    code, data = env.data()
    assert code == 0 and "warning" in data


def test_the_script_matches_the_repository_lists() -> None:
    text = (REAL / "check_prerequisites.py").read_text(encoding="utf-8")
    namespace: dict[str, Any] = {}
    start = text.index("SKILLS = (")
    end = text.index("JIRA_SKILLS")
    exec(text[start:end], namespace)
    assert tuple(namespace["SKILLS"]) == SKILLS
    assert {(r, c, tuple(cs)) for r, c, cs in namespace["SHARED"]} == {
        (r, c, tuple(cs)) for r, c, cs in SHARED
    }
    header = (REAL / "aidlc_state.py").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.9"' in header and "PYTHON_FLOOR = (3, 9)" in text


# --- SSH, remotes, branch, network-aware checks, freshness ---------------------------------

AZURE_HTTPS = "https://crv4all@dev.azure.com/crv4all/Cloudforce%20Team%20Data/_git/adr-registry"
AZURE_SSH = "git@ssh.dev.azure.com:v3/crv4all/Cloudforce%20Team%20Data/adr-registry"


def check_of(data: dict[str, Any], cid: str) -> dict[str, str]:
    return next(c for c in data["checks"] if c["id"] == cid)


def commit_file(env: Env, repo: Path, name: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    env.git(repo, "add", ".")
    env.git(repo, "commit", "-q", "-m", name)
    return env.git(repo, "rev-parse", "HEAD")


def registry_with_origin(env: Env) -> tuple[Path, Path, Path]:
    """(clone used as the registry, bare origin, second clone used to push)."""
    seed = env.tmp / "seed"
    seed.mkdir()
    env.git(seed, "init", "-q", "-b", "main")
    commit_file(env, seed, "a.md")
    bare = env.tmp / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(bare)], env=env.env, check=True)
    clone = env.tmp / "registry"
    other = env.tmp / "other"
    for target in (clone, other):
        subprocess.run(["git", "clone", "-q", str(bare), str(target)], env=env.env, check=True)
    return clone, bare, other


def write_index(env: Env, commit: str) -> None:
    index = {"schema": 1, "registry": "registry", "registry_commit": commit}
    (env.root / "architecture-index.json").write_text(json.dumps(index), encoding="utf-8")


def test_ssh_tools_missing_is_required(env: Env) -> None:
    only_git = env.tmp / "onlygit"
    only_git.mkdir()
    (only_git / "git").symlink_to(shutil.which("git") or "git")
    env.env["PATH"] = str(only_git)
    code, data = env.data()
    check = check_of(data, "R6")
    assert code == 1 and check["status"] == "missing" and "ssh" in check["detail"]
    assert check_of(data, "R7")["status"] == "skipped"


def test_azure_ssh_failing_is_required_and_points_to_onboard(env: Env) -> None:
    env.env["FAKE_SSH"] = "no"
    code, data = env.data()
    check = check_of(data, "R7")
    assert code == 1 and check["status"] == "missing" and "onboard.py" in check["fix"]


def test_offline_skips_the_network_and_says_so(env: Env) -> None:
    env.env["FAKE_SSH"] = "no"
    code, data = env.data("--offline")
    assert code == 0 and "--offline" in check_of(data, "R7")["detail"]
    assert any("Offline" in note for note in data["notes"])
    assert "Offline" in env.run("--offline")[1]
    # an offline run is never remembered as a good result
    assert json.loads((env.marker / "prerequisites.json").read_text())["verdict"] == "failed"


def test_https_remotes_fail_with_the_exact_fix(env: Env) -> None:
    registry = make_registry(env)
    env.git(registry, "remote", "add", "origin", AZURE_HTTPS)
    env.git(env.root, "remote", "add", "origin", "git@ssh.dev.azure.com:v3/crv4all/DevOps/p")
    code, data = env.data("--architecture-ref", str(registry), "--offline")
    check = check_of(data, "R8")
    assert code == 1 and check["status"] == "outdated" and "ADR registry" in check["detail"]
    assert check["fix"] == f"git -C {registry} remote set-url origin {AZURE_SSH}"
    env.git(registry, "remote", "set-url", "origin", AZURE_SSH)
    assert status(env.data("--architecture-ref", str(registry), "--offline")[1], "R8") == "ok"


def test_the_planning_repo_must_be_on_the_branch_aidlc_json_names(env: Env) -> None:
    (env.root / "aidlc.json").write_text('{"git": {"branch": "work"}}', encoding="utf-8")
    code, data = env.data()
    check = check_of(data, "R9")
    assert code == 1 and check["status"] == "outdated" and check["fix"].endswith("switch work")
    env.git(env.root, "switch", "-q", "-c", "work")
    assert status(env.data()[1], "R9") == "ok"


def test_c1_compares_the_index_with_the_remote_not_only_local_head(env: Env) -> None:
    clone, _bare, other = registry_with_origin(env)
    write_index(env, env.git(clone, "rev-parse", "HEAD"))
    assert status(env.data("--architecture-ref", str(clone))[1], "C1") == "ok"
    commit_file(env, other, "b.md")
    env.git(other, "push", "-q", "origin", "main")
    _code, data = env.data("--architecture-ref", str(clone))
    check = check_of(data, "C1")
    assert check["status"] == "outdated" and "remote" in check["detail"]
    assert check["fix"].endswith("--refresh")
    # offline: the local checkout still matches, and the table says it used the checkout
    check = check_of(env.data("--architecture-ref", str(clone), "--offline")[1], "C1")
    assert check["status"] == "warning" and "local checkout" in check["detail"]


def test_c1_without_network_is_a_warning_not_a_failure(env: Env) -> None:
    clone, bare, _other = registry_with_origin(env)
    write_index(env, env.git(clone, "rev-parse", "HEAD"))
    bare.rename(env.tmp / "gone.git")
    code, data = env.data("--architecture-ref", str(clone))
    check = check_of(data, "C1")
    assert code == 0 and check["status"] == "warning" and "local checkout" in check["detail"]
    assert data["verdict"] == "ok, with warnings"


def stamp(env: Env, skill: str, commit: str) -> None:
    folder = env.tmp / "home" / ".claude" / "skills" / skill
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".crv-install").write_text(f"source=x\ncommit={commit}\n", encoding="utf-8")


def test_installed_skills_behind_the_checkout_warn_with_the_update_command(env: Env) -> None:
    clone, _bare, other = registry_with_origin(env)  # any git checkout with a remote will do
    head = env.git(clone, "rev-parse", "HEAD")
    stamp(env, "crv-aidlc", head)
    code, data = env.data("--skills-checkout", str(clone))
    assert check_of(data, "C4")["status"] == "ok"
    new = commit_file(env, other, "c.md")
    env.git(other, "push", "-q", "origin", "main")
    check = check_of(env.data("--skills-checkout", str(clone))[1], "C4")
    assert check["status"] == "outdated" and "behind its remote" in check["detail"]
    assert "onboard.py" in check["fix"] and "install.sh" in check["fix"]
    env.git(clone, "pull", "-q", "--ff-only")
    check = check_of(env.data("--skills-checkout", str(clone))[1], "C4")
    assert new != head and check["status"] == "outdated" and "older checkout" in check["detail"]
    code, data = env.data("--skills-checkout", str(clone))
    assert code == 0 and data["verdict"] == "ok, with warnings"


def test_manual_items_are_listed_and_never_counted(env: Env) -> None:
    code, data = env.data()
    assert code == 0 and len(data["manual"]) == 4
    out = env.run()[1]
    assert out.count("MANUAL") == 4 and out.splitlines()[-1] == "Verdict: ok"


def test_if_stale_does_not_trust_a_marker_older_than_24_hours(env: Env) -> None:
    assert env.run()[0] == 0
    path = env.marker / "prerequisites.json"
    marker = json.loads(path.read_text(encoding="utf-8"))
    shutil.rmtree(env.root / "codekb")  # would fail R5 if the checks ran
    marker["checked_at"] -= 23 * 3600
    path.write_text(json.dumps(marker), encoding="utf-8")
    assert env.run("--if-stale")[0] == 0  # 23 hours: still trusted
    marker["checked_at"] -= 2 * 3600
    path.write_text(json.dumps(marker), encoding="utf-8")
    assert env.run("--if-stale")[0] == 1  # 25 hours: checked again
    del marker["checked_at"]
    path.write_text(json.dumps(marker), encoding="utf-8")
    assert env.run("--if-stale")[0] == 1  # no timestamp: not trusted


AZURE_URLS = [
    (AZURE_HTTPS, AZURE_SSH),
    (
        "https://dev.azure.com/crv4all/Cloudforce Team Data/_git/adr-registry",
        AZURE_SSH,
    ),
    (
        "https://dev.azure.com/crv4all/_git/solo",
        "git@ssh.dev.azure.com:v3/crv4all/solo/solo",
    ),
    ("https://github.com/crv4all/skills.git", "git@github.com:crv4all/skills.git"),
    ("git@github.com:crv4all/skills.git", None),
    (AZURE_SSH, None),
]


@pytest.mark.parametrize("script", ["check_prerequisites.py", "build_adr_index.py"])
def test_https_to_ssh_rewriting(script: str) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(script[:-3], REAL / script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader: Any = spec.loader
    loader.exec_module(module)
    for url, want in AZURE_URLS:
        assert module.to_ssh_url(url) == want, url
