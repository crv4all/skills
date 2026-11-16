"""``aidlc_state.py workspace`` and ``target``: one place to open every folder of a paddock.

A paddock's work spans the planning repository, the ADR registry and several
target repositories, and a stale checkout read by a stage goes unnoticed. These
tests build real throwaway git repositories with an origin, because "behind
origin" is a statement about git refs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts" / "aidlc_state.py"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@e.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@e.com",
    "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
}


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**GIT_ENV, "HOME": str(cwd)},
    )
    return done.stdout.strip()


def origin_and_clone(base: Path, name: str) -> tuple[Path, Path]:
    """A bare origin on ``main`` with one commit, and a clone of it."""
    seed = base / f"{name}-seed"
    seed.mkdir(parents=True)
    git(seed, "init", "-q", "-b", "main")
    (seed / "app.py").write_text("x = 1\n", encoding="utf-8")
    git(seed, "add", ".")
    git(seed, "commit", "-q", "-m", "first")
    origin = base / f"{name}.git"
    git(base, "clone", "-q", "--bare", str(seed), str(origin))
    clone = base / name
    git(base, "clone", "-q", str(origin), str(clone))
    return origin, clone


def push_one_more(base: Path, origin: Path) -> None:
    other = base / "other-clone"
    git(base, "clone", "-q", str(origin), str(other))
    (other / "more.py").write_text("y = 2\n", encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-q", "-m", "second")
    git(other, "push", "-q", "origin", "main")


def run(*args: str) -> tuple[int, dict[str, Any]]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=120
    )
    return done.returncode, (json.loads(done.stdout) if done.stdout.startswith("{") else {})


def open_paddock(root: Path, *args: str) -> tuple[Path, dict[str, Any]]:
    code, data = run(
        "open", "--root", str(root), "--slug", "demo", "--title", "Demo",
        "--intent", "Try", "--date", "2026-01-05", *args,
    )  # fmt: skip
    assert code == 0, data
    return Path(data["paddock"]), data


def state(paddock: Path) -> dict[str, Any]:
    return json.loads((paddock / "state.json").read_text(encoding="utf-8"))


def log_lines(paddock: Path) -> list[str]:
    return (paddock / "log.md").read_text(encoding="utf-8").splitlines()


def checkout(data: dict[str, Any], name: str) -> dict[str, Any]:
    return next(row for row in data["checkouts"] if row["name"] == name)


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / "plan"
    root.mkdir()
    registry = tmp_path / "registry"
    registry.mkdir()
    origin, clone = origin_and_clone(tmp_path, "svc")
    return {"base": tmp_path, "root": root, "registry": registry, "origin": origin, "svc": clone}


# --- the workspace file ------------------------------------------------------


def test_open_writes_the_workspace_file_in_order(world: dict[str, Path]) -> None:
    paddock, data = open_paddock(
        world["root"],
        "--target",
        f"svc={world['svc']}",
        "--architecture-ref",
        str(world["registry"]),
    )
    file = paddock / "2026-01-05-demo.code-workspace"
    assert data["workspace"]["file"] == str(file.resolve())
    folders = json.loads(file.read_text(encoding="utf-8"))["folders"]
    assert [f["name"] for f in folders] == [
        "paddock: demo",
        "planning repo",
        "adr registry",
        "target: svc",
    ]
    assert all(Path(f["path"]).is_absolute() for f in folders)
    assert folders[1]["path"] == str(world["root"].resolve())


def test_claude_command_skips_only_the_planning_root(world: dict[str, Path]) -> None:
    paddock, data = open_paddock(world["root"], "--target", f"svc={world['svc']}")
    command = data["workspace"]["claude_command"]
    assert command.startswith("claude --add-dir ")
    assert f'--add-dir "{paddock.resolve()}"' in command
    assert f'--add-dir "{world["svc"].resolve()}"' in command
    assert f'"{world["root"].resolve()}"' not in command


def test_out_writes_the_file_elsewhere(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"])
    out = world["base"] / "mine.code-workspace"
    code, data = run("workspace", "--paddock", str(paddock), "--out", str(out))
    assert code == 0 and data["file"] == str(out.resolve())
    assert json.loads(out.read_text(encoding="utf-8"))["folders"][0]["name"] == "paddock: demo"
    missing = world["base"] / "nope" / "x.code-workspace"
    assert run("workspace", "--paddock", str(paddock), "--out", str(missing))[0] == 3


def test_extras_are_kept_and_removed(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"])
    docs = world["base"] / "docs"
    docs.mkdir()
    p = str(paddock)
    assert run("workspace", "--paddock", p, "--extra", f"docs={docs}")[0] == 0
    assert state(paddock)["workspace"]["extra"] == [{"name": "docs", "path": str(docs.resolve())}]
    assert "| workspace |" in log_lines(paddock)[-1]
    code, data = run("workspace", "--paddock", p)
    assert code == 0 and data["folders"][-1] == {"name": "docs", "path": str(docs.resolve())}
    assert data["checkouts"] == []  # an extra that is not a git repository is not a checkout
    assert run("workspace", "--paddock", p, "--extra", "docs=")[0] == 0
    assert state(paddock)["workspace"]["extra"] == []
    assert run("workspace", "--paddock", p, "--extra", "docs=")[0] == 3


def test_extra_refusals_change_nothing(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"])
    before = state(paddock)
    p = str(paddock)
    assert run("workspace", "--paddock", p, "--extra", f"x={world['base'] / 'none'}")[0] == 3
    assert run("workspace", "--paddock", p, "--extra", "no-equals-sign")[0] == 2
    assert state(paddock) == before


def test_extra_git_repository_is_a_checkout(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"])
    _, lib = origin_and_clone(world["base"], "lib")
    code, data = run("workspace", "--paddock", str(paddock), "--extra", f"lib={lib}")
    assert code == 0 and checkout(data, "lib")["role"] == "extra"


# --- checkouts ---------------------------------------------------------------


def test_a_current_checkout_is_not_stale(world: dict[str, Path]) -> None:
    _, data = open_paddock(world["root"], "--target", f"svc={world['svc']}")
    row = checkout(data["workspace"], "svc")
    assert row["is_git"] and row["exists"] and not row["fetched"]
    assert (row["branch"], row["default_branch"]) == ("main", "main")
    assert (row["behind"], row["ahead"], row["dirty"], row["stale"]) == (0, 0, 0, False)
    assert len(row["head"]["commit"]) >= 7 and row["head"]["date"].startswith("20")


def test_behind_origin_shows_only_after_a_fetch(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"], "--target", f"svc={world['svc']}")
    push_one_more(world["base"], world["origin"])
    code, data = run("workspace", "--paddock", str(paddock))
    assert code == 0 and checkout(data, "svc")["behind"] == 0  # no network without --fetch
    code, data = run("workspace", "--paddock", str(paddock), "--fetch")
    row = checkout(data, "svc")
    assert code == 0 and row["fetched"] and row["behind"] == 1 and row["stale"]
    assert data["stale"] == ["svc"]


def test_another_branch_and_local_edits_are_reported(world: dict[str, Path]) -> None:
    svc = world["svc"]
    git(svc, "switch", "-q", "-c", "feature")
    (svc / "app.py").write_text("x = 2\n", encoding="utf-8")
    (svc / "new.py").write_text("z = 3\n", encoding="utf-8")
    _, data = open_paddock(world["root"], "--target", f"svc={svc}")
    row = checkout(data["workspace"], "svc")
    assert row["branch"] == "feature" and row["stale"] and row["dirty"] == 2


def test_a_failed_fetch_is_data_not_a_crash(world: dict[str, Path]) -> None:
    git(world["svc"], "remote", "set-url", "origin", str(world["base"] / "gone.git"))
    paddock, _ = open_paddock(world["root"], "--target", f"svc={world['svc']}")
    code, data = run("workspace", "--paddock", str(paddock), "--fetch")
    row = checkout(data, "svc")
    assert code == 0 and not row["fetched"] and row["fetch_error"]


def test_a_folder_that_is_not_git_is_reported_not_judged(world: dict[str, Path]) -> None:
    plain = world["base"] / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("a = 1\n", encoding="utf-8")
    _, data = open_paddock(world["root"], "--target", f"plain={plain}")
    row = checkout(data["workspace"], "plain")
    assert row["exists"] and not row["is_git"] and not row["stale"]


def test_workspace_never_changes_a_target(world: dict[str, Path]) -> None:
    svc = world["svc"]
    (svc / "app.py").write_text("x = 9\n", encoding="utf-8")
    paddock, _ = open_paddock(world["root"], "--target", f"svc={svc}")
    push_one_more(world["base"], world["origin"])

    def snapshot() -> tuple[str, str, str, bytes]:
        return (
            git(svc, "rev-parse", "HEAD"),
            git(svc, "branch", "--show-current"),
            git(svc, "status", "--porcelain"),
            (svc / "app.py").read_bytes(),
        )

    before = snapshot()
    assert run("workspace", "--paddock", str(paddock), "--fetch")[0] == 0
    assert snapshot() == before


# --- target ------------------------------------------------------------------


def test_target_add_classifies_and_turns_on_reverse_engineering(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"])
    assert state(paddock)["stages"]["reverse-engineering"]["decision"] == "skip"
    code, data = run("target", "--paddock", str(paddock), "--add", f"svc={world['svc']}")
    assert code == 0, data
    assert [(t["repo"], t["kind"]) for t in state(paddock)["targets"]] == [("svc", "brownfield")]
    assert state(paddock)["stages"]["reverse-engineering"]["decision"] == "execute"
    assert [f["name"] for f in data["workspace"]["folders"]][-1] == "target: svc"
    assert "| target |" in log_lines(paddock)[-1] and "brownfield" in log_lines(paddock)[-1]


def test_target_remove_restores_the_skip(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"], "--target", f"svc={world['svc']}")
    code, data = run("target", "--paddock", str(paddock), "--remove", "svc")
    assert code == 0 and state(paddock)["targets"] == []
    record = state(paddock)["stages"]["reverse-engineering"]
    assert (record["decision"], record["reason"]) == ("skip", "no brownfield target")
    assert data["workspace"]["checkouts"] == []


def test_target_keeps_a_decision_made_by_a_person(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"])
    p = str(paddock)
    run("decide", "--paddock", p, "--stage", "reverse-engineering", "--decision", "skip",
        "--reason", "store is fresh enough")  # fmt: skip
    code, data = run("target", "--paddock", p, "--add", f"svc={world['svc']}")
    assert code == 0 and data["reverse_engineering"].startswith("left as skip")
    assert state(paddock)["stages"]["reverse-engineering"]["reason"] == "store is fresh enough"


def test_target_refusals(world: dict[str, Path]) -> None:
    paddock, _ = open_paddock(world["root"])
    p = str(paddock)
    before = state(paddock)
    assert run("target", "--paddock", p, "--remove", "nope")[0] == 3
    assert run("target", "--paddock", p, "--add", f"x={world['base'] / 'none'}")[0] == 3
    assert run("target", "--paddock", p, "--add", "x")[0] == 2
    assert run("target", "--paddock", p)[0] == 2
    assert state(paddock) == before
    run("close", "--paddock", p, "--status", "archived")
    assert run("target", "--paddock", p, "--add", f"svc={world['svc']}")[0] == 1
