"""``aidlc_state.py`` commits and pushes a shared planning repo.

Each test builds a bare remote and one or two clones in a temporary folder, with
a fixed git identity set through the environment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts" / "aidlc_state.py"
PADDOCK_ID = "2026-01-05-demo"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


@pytest.fixture(autouse=True)
def identity(monkeypatch: pytest.MonkeyPatch) -> None:
    for who in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{who}_NAME", "Test Person")
        monkeypatch.setenv(f"GIT_{who}_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("AIDLC_GIT", raising=False)


def git(path: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True, timeout=60
    )
    return done.stdout.strip()


def script(*args: str) -> tuple[int, dict[str, Any], str]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=120
    )
    out = done.stdout
    return done.returncode, (json.loads(out) if out.strip().startswith("{") else {}), out


def open_demo(root: Path, *extra: str) -> tuple[int, dict[str, Any], str]:
    return script(
        "open", "--root", str(root), "--slug", "demo", "--title", "Demo", "--intent", "Try it",
        "--date", "2026-01-05", *extra,
    )  # fmt: skip


def paddock_of(root: Path) -> Path:
    return root / "paddocks" / PADDOCK_ID


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class Repos:
    def __init__(self, base: Path) -> None:
        self.remote = base / "remote.git"
        self.a = base / "a"
        self.b = base / "b"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.a)], check=True)
        git(self.a, "remote", "add", "origin", str(self.remote))
        write(self.a / "README.md", "planning repo\n")
        git(self.a, "add", "-A")
        git(self.a, "commit", "-q", "-m", "start")
        git(self.a, "push", "-q", "-u", "origin", "main")
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.b)], check=True)

    def remote_log(self) -> list[str]:
        return git(self.remote, "log", "--format=%s", "main").splitlines()


@pytest.fixture
def repos(tmp_path: Path) -> Repos:
    return Repos(tmp_path)


def test_state_change_commits_and_pushes(repos: Repos) -> None:
    code, out, _ = open_demo(repos.a)
    assert code == 0, out
    assert out["git"]["pushed"] is True and out["git"]["commit"]
    assert git(repos.a, "log", "-1", "--format=%s") == "docs(demo): open the paddock"
    assert git(repos.a, "log", "-1", "--format=%b") == ""
    assert repos.remote_log()[0] == "docs(demo): open the paddock"
    assert git(repos.a, "status", "--porcelain") == ""

    code, out, _ = script(
        "decide", "--paddock", str(paddock_of(repos.a)), "--stage", "hla",
        "--decision", "skip", "--reason", "not needed",
    )  # fmt: skip
    assert code == 0
    assert repos.remote_log()[0] == "docs(demo): decide hla: skip"


def test_team_work_is_rebased_under_the_local_commit(repos: Repos) -> None:
    assert open_demo(repos.a)[0] == 0
    git(repos.b, "pull", "-q")
    write(repos.b / "codekb" / "team.md", "from the team\n")
    git(repos.b, "add", "-A")
    git(repos.b, "commit", "-q", "-m", "team work")
    git(repos.b, "push", "-q")

    code, out, _ = script("decision-id", "--paddock", str(paddock_of(repos.a)), "--count", "3")
    assert code == 0 and out["git"]["pushed"] is True
    log = repos.remote_log()
    assert log[0] == "docs(demo): reserve decision ids D1-D3"
    assert "team work" in log
    assert (repos.a / "codekb" / "team.md").is_file()
    assert git(repos.a, "rev-list", "--merges", "--count", "HEAD") == "0"


def test_conflicting_artifact_stops_with_exit_6(repos: Repos) -> None:
    assert open_demo(repos.a)[0] == 0
    git(repos.b, "pull", "-q")
    rel = f"paddocks/{PADDOCK_ID}/architecture/hla.md"
    write(repos.b / rel, "their version\n")
    git(repos.b, "add", "-A")
    git(repos.b, "commit", "-q", "-m", "team hla")
    git(repos.b, "push", "-q")

    write(repos.a / rel, "my version\n")
    code, out, text = script("sync", "--paddock", str(paddock_of(repos.a)), "-m", "write the hla")
    assert code == 6
    assert (repos.a / ".git" / "rebase-merge").exists()
    finding = out["findings"][0]
    assert finding["path"] == rel and "keep both" in finding["message"]
    assert "'ours' is the team's version" in text

    # while the rebase is open, every changing command stops and changes nothing
    code, _, _ = script("park", "--paddock", str(paddock_of(repos.a)), "--note", "x")
    assert code == 6
    assert json.loads((paddock_of(repos.a) / "state.json").read_text())["parked"] is None


def test_index_conflict_resolves_itself(repos: Repos) -> None:
    write(repos.a / "architecture-index.json", '{"v": 0}\n')
    assert script("sync", "--root", str(repos.a), "-m", "add the index")[0] == 0
    git(repos.b, "pull", "-q")
    write(repos.b / "architecture-index.json", '{"v": "team"}\n')
    git(repos.b, "commit", "-qam", "team index")
    git(repos.b, "push", "-q")

    write(repos.a / "architecture-index.json", '{"v": "mine"}\n')
    code, out, _ = script("sync", "--root", str(repos.a), "-m", "change the index")
    assert code == 0, out
    assert out["git"]["rebuild_adr_index"] is True
    assert not (repos.a / ".git" / "rebase-merge").exists()
    assert (repos.a / "architecture-index.json").read_text() == '{"v": "team"}\n'
    assert out["git"]["pushed"] is False  # my commit became empty; nothing to push


def test_no_remote_keeps_the_commit_and_warns(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    code, out, _ = open_demo(tmp_path)
    assert code == 0
    assert out["git"]["commit"] and out["git"]["pushed"] is False
    assert any("push: skipped" in w for w in out["git"]["warnings"])
    assert git(tmp_path, "log", "-1", "--format=%s") == "docs(demo): open the paddock"


def test_planted_secret_stops_without_a_commit(repos: Repos) -> None:
    assert open_demo(repos.a)[0] == 0
    head = git(repos.a, "rev-parse", "HEAD")
    rel = f"paddocks/{PADDOCK_ID}/inputs/notes.md"
    write(repos.a / rel, "intro\npassword=hunter2hunter2\n")
    code, out, text = script("sync", "--paddock", str(paddock_of(repos.a)))
    assert code == 6
    assert out["findings"][0]["path"] == f"{rel}:2"
    assert "hunter2" not in text
    assert git(repos.a, "rev-parse", "HEAD") == head
    assert git(repos.a, "diff", "--cached", "--name-only") == ""


def test_path_outside_the_scope_is_left_uncommitted(repos: Repos) -> None:
    assert open_demo(repos.a)[0] == 0
    write(repos.a / "notes.txt", "private\n")
    write(paddock_of(repos.a) / "inputs" / "a.md", "a\n")
    write(repos.a / "codekb" / "x.md", "x\n")
    code, out, _ = script("sync", "--paddock", str(paddock_of(repos.a)))
    assert code == 0
    assert out["git"]["uncommitted"] == ["notes.txt"]
    files = git(repos.a, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert "notes.txt" not in files and "codekb/x.md" in files
    assert git(repos.a, "status", "--porcelain") == "?? notes.txt"
    assert out["git"]["message"] == "docs(demo): save work in progress"


def test_git_off_and_non_git_folder_do_nothing(
    repos: Repos, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIDLC_GIT", "off")
    code, out, _ = open_demo(repos.a)
    assert code == 0 and "git" not in out
    assert git(repos.a, "log", "-1", "--format=%s") == "start"
    code, out, _ = script("sync", "--paddock", str(paddock_of(repos.a)))
    assert code == 0 and out["git"]["enabled"] is False
    monkeypatch.delenv("AIDLC_GIT")

    plain = tmp_path / "plain"
    plain.mkdir()
    code, out, _ = open_demo(plain)
    assert code == 0 and "git" not in out
    code, out, _ = script("sync", "--paddock", str(paddock_of(plain)))
    assert code == 0 and out["git"]["enabled"] is False

    code, out, _ = open_demo(repos.b, "--no-git")
    assert code == 0 and "git" not in out


def test_status_shows_the_git_block(repos: Repos) -> None:
    assert open_demo(repos.a)[0] == 0
    p = str(paddock_of(repos.a))
    write(paddock_of(repos.a) / "inputs" / "a.md", "a\n")
    code, out, _ = script("status", "--paddock", p)
    assert code == 0
    assert out["git"]["branch"] == "main" and out["git"]["uncommitted"] == 1
    assert out["git"]["ahead"] == 0 and out["git"]["behind"] == 0
    code, _, text = script("status", "--paddock", p, "--format", "text")
    assert "Git: main, ahead 0, behind 0, 1 uncommitted" in text
    assert git(repos.a, "log", "-1", "--format=%s") == "docs(demo): open the paddock"


def test_configured_branch_must_be_the_current_one(repos: Repos) -> None:
    write(repos.a / "aidlc.json", json.dumps({"git": {"branch": "construction"}}))
    code, out, _ = open_demo(repos.a)
    assert code == 1
    assert "git switch construction" in out["error"]
    assert not paddock_of(repos.a).exists()
