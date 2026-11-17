"""Shared code knowledge, scopes and unit kinds in ``aidlc_state.py``.

The code knowledge store lives once per target repository at the planning repo
root; a paddock only records which commit it relied on. These tests build real
throwaway git repositories, because the freshness verdict is a statement about
git history.
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
QUESTIONS = "## Q1 Scope\nContext.\n\nA) One\nB) Two\nX) Other (describe)\n\nRecommended: A - simple.\n\nAnswer: A\n"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**GIT_ENV, "HOME": str(repo)},
    )
    return done.stdout.strip()


def make_repo(path: Path, files: int = 10) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q")
    for n in range(files):
        (path / f"mod{n}.py").write_text(f"x = {n}\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "first")
    return path


def run(*args: str) -> tuple[int, dict[str, Any]]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60
    )
    return done.returncode, (json.loads(done.stdout) if done.stdout.startswith("{") else {})


def open_paddock(root: Path, *args: str) -> Path:
    code, data = run(
        "open", "--root", str(root), "--slug", "demo", "--title", "Demo",
        "--intent", "Try", "--date", "2026-01-05", *args,
    )  # fmt: skip
    assert code == 0, data
    return Path(data["paddock"])


def write_store(root: Path, repo: str, commit: str, overview: bool = True) -> Path:
    store = root / "codekb" / repo
    store.mkdir(parents=True, exist_ok=True)
    meta = {"repo": repo, "path": "x", "commit": commit, "built": "2026-01-05", "artifacts": ["a"]}
    (store / "_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if overview:
        (store / "overview.md").write_text("# O\n\n## Digest\n- one\n", encoding="utf-8")
    return store


@pytest.fixture
def world(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "plan"
    root.mkdir()
    target = make_repo(tmp_path / "svc")
    return root, target, open_paddock(root, "--target", f"svc={target}")


def targets(paddock: Path) -> list[dict[str, Any]]:
    return run("codekb-status", "--paddock", str(paddock))[1]["targets"]


# --- codekb-status -----------------------------------------------------------


def test_open_does_not_create_a_paddock_level_codekb(world: tuple[Path, Path, Path]) -> None:
    _, _, paddock = world
    assert not (paddock / "codekb").exists()


def test_open_reports_the_code_knowledge_verdict(tmp_path: Path) -> None:
    root = tmp_path / "plan"
    root.mkdir()
    target = make_repo(tmp_path / "svc")
    code, data = run(
        "open", "--root", str(root), "--slug", "demo", "--title", "D", "--intent", "i",
        "--target", f"svc={target}",
    )  # fmt: skip
    assert code == 0 and data["codekb"][0]["status"] == "missing"


def test_missing_then_fresh_then_stale_focused(world: tuple[Path, Path, Path]) -> None:
    root, target, paddock = world
    assert targets(paddock)[0]["status"] == "missing"
    head = git(target, "rev-parse", "HEAD")
    write_store(root, "svc", head)
    row = targets(paddock)[0]
    assert row["status"] == "fresh" and row["head"] == head
    (target / "mod0.py").write_text("x = 'changed'\n", encoding="utf-8")
    git(target, "commit", "-qam", "change")
    row = targets(paddock)[0]
    assert row["status"] == "stale" and row["rescan"] == "focused"
    assert row["changed_count"] == 1 and row["changed_files"] == ["mod0.py"]
    assert row["meta_commit"] == head


def test_many_changes_ask_for_a_full_rescan_and_the_list_is_capped(tmp_path: Path) -> None:
    root = tmp_path / "plan"
    root.mkdir()
    target = make_repo(tmp_path / "big", files=60)
    paddock = open_paddock(root, "--target", f"big={target}")
    write_store(root, "big", git(target, "rev-parse", "HEAD"))
    for n in range(60):
        (target / f"mod{n}.py").write_text("y = 1\n", encoding="utf-8")
    git(target, "commit", "-qam", "everything")
    row = targets(paddock)[0]
    assert row["rescan"] == "full" and row["changed_count"] == 60
    assert len(row["changed_files"]) == 50 and row["truncated"] is True


def test_a_meta_commit_the_repo_does_not_know_asks_for_a_full_rescan(
    world: tuple[Path, Path, Path],
) -> None:
    root, _, paddock = world
    write_store(root, "svc", "0" * 40)
    row = targets(paddock)[0]
    assert row["status"] == "stale" and row["rescan"] == "full"


def test_greenfield_targets_have_no_verdict(tmp_path: Path) -> None:
    root = tmp_path / "plan"
    root.mkdir()
    green = tmp_path / "green"
    green.mkdir()
    (green / "README.md").write_text("hi", encoding="utf-8")
    paddock = open_paddock(root, "--target", f"green={green}")
    assert targets(paddock)[0]["status"] == "n/a"


def test_a_malformed_meta_exits_4(world: tuple[Path, Path, Path]) -> None:
    root, _, paddock = world
    store = write_store(root, "svc", "abc")
    (store / "_meta.json").write_text("{oops", encoding="utf-8")
    assert run("codekb-status", "--paddock", str(paddock))[0] == 4


# --- root: paths -------------------------------------------------------------


def test_inputs_resolve_root_paths_to_the_planning_repo(world: tuple[Path, Path, Path]) -> None:
    root, target, paddock = world
    write_store(root, "svc", git(target, "rev-parse", "HEAD"))
    run("decide", "--paddock", str(paddock), "--stage", "document-knowledge", "--decision", "skip", "--reason", "none")  # fmt: skip
    code, data = run("inputs", "--paddock", str(paddock), "--stage", "hla")
    assert code == 0, data
    row = next(r for r in data["inputs"] if r["path"] == "root:codekb/svc/overview.md")
    assert row["exists"] and row["mode"] == "digest"
    assert Path(row["file"]) == (root / "codekb" / "svc" / "overview.md").resolve()


def test_a_missing_store_input_names_the_reverse_engineering_stage(
    world: tuple[Path, Path, Path],
) -> None:
    _, _, paddock = world
    run("decide", "--paddock", str(paddock), "--stage", "document-knowledge", "--decision", "skip", "--reason", "none")  # fmt: skip
    code, data = run("inputs", "--paddock", str(paddock), "--stage", "hla")
    assert code == 3
    assert {"path": "root:codekb/svc/overview.md", "produced_by": "reverse-engineering"} in data["missing"]  # fmt: skip


# --- the reverse-engineering gate -------------------------------------------


def produce_re(root: Path, paddock: Path, meta_commit: str, repo: str = "svc") -> None:
    store = write_store(root, repo, meta_commit)
    names = [
        "business-overview", "architecture", "code-structure", "api-documentation",
        "component-inventory", "technology-stack", "dependencies", "code-quality-assessment",
        "reverse-engineering-timestamp",
    ]  # fmt: skip
    for name in names:
        (store / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")  # no digest on purpose
    base = paddock / "docs" / "inception" / "reverse-engineering"
    base.mkdir(parents=True, exist_ok=True)
    (base / f"developer-scan-{repo}.md").write_text(
        "# Scan\n\n## Digest\n- read\n", encoding="utf-8"
    )
    (base / "reverse-engineering-questions.md").write_text(QUESTIONS, encoding="utf-8")
    p = str(paddock)
    run("gate", "--paddock", p, "--stage", "workspace-detection", "--approve", "--by", "B")
    run("decide", "--paddock", p, "--stage", "document-knowledge", "--decision", "skip", "--reason", "none")  # fmt: skip
    run("step", "--paddock", p, "--stage", "reverse-engineering", "--to", "produced")


def test_the_gate_records_the_commit_the_paddock_relied_on(world: tuple[Path, Path, Path]) -> None:
    root, target, paddock = world
    head = git(target, "rev-parse", "HEAD")
    produce_re(root, paddock, head)
    code, data = run("gate", "--paddock", str(paddock), "--stage", "reverse-engineering", "--approve", "--by", "B")  # fmt: skip
    assert code == 0, data
    state = json.loads((paddock / "state.json").read_text(encoding="utf-8"))
    assert state["targets"][0]["codekb_commit"] == head
    assert targets(paddock)[0]["recorded_commit"] == head


def test_the_gate_refuses_an_incomplete_meta(world: tuple[Path, Path, Path]) -> None:
    root, _, paddock = world
    produce_re(root, paddock, "")
    code, data = run("gate", "--paddock", str(paddock), "--stage", "reverse-engineering", "--approve", "--by", "B")  # fmt: skip
    assert code == 1 and [f["code"] for f in data["findings"]] == ["meta-incomplete"]
    state = json.loads((paddock / "state.json").read_text(encoding="utf-8"))
    assert state["targets"][0]["codekb_commit"] is None


# --- scopes ------------------------------------------------------------------


def decisions(paddock: Path) -> dict[str, str]:
    state = json.loads((paddock / "state.json").read_text(encoding="utf-8"))
    return {k: v["decision"] for k, v in state["stages"].items()}


@pytest.mark.parametrize(
    ("scope", "running"),
    [
        (
            "express",
            {"workspace-detection", "document-knowledge", "requirements-analysis",
             "code-generation", "build-and-test"},
        ),
        (
            "bugfix",
            {"workspace-detection", "requirements-analysis", "code-generation", "build-and-test"},
        ),
    ],
)  # fmt: skip
def test_express_and_bugfix_stage_sets(tmp_path: Path, scope: str, running: set[str]) -> None:
    paddock = open_paddock(tmp_path, "--scope", scope)
    state = json.loads((paddock / "state.json").read_text(encoding="utf-8"))
    live = {k for k, v in decisions(paddock).items() if v != "skip"}
    unit = state["units"][0]
    live |= {k for k, v in unit["stages"].items() if v["decision"] != "skip"}
    assert live == running
    assert [u["id"] for u in state["units"]] == ["u1"]
    assert state["bolts"] == [{"id": "b1", "units": ["u1"], "status": "todo"}]
    assert state["stages"]["units-generation"]["decision"] == "skip"
    assert state["stages"]["delivery-planning"]["decision"] == "skip"


def test_express_asks_about_document_knowledge_and_bugfix_defaults_to_minimal(
    tmp_path: Path,
) -> None:
    express = open_paddock(tmp_path, "--scope", "express")
    assert decisions(express)["document-knowledge"] == "pending"
    other = tmp_path / "b"
    other.mkdir()
    bugfix = json.loads((open_paddock(other, "--scope", "bugfix") / "state.json").read_text(encoding="utf-8"))  # fmt: skip
    assert bugfix["depth"] == "minimal"
    third = tmp_path / "c"
    third.mkdir()
    forced = open_paddock(third, "--scope", "bugfix", "--depth", "standard")
    assert json.loads((forced / "state.json").read_text(encoding="utf-8"))["depth"] == "standard"


def test_hla_and_tdd_can_be_forced_into_any_scope(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path, "--scope", "express")
    assert decisions(paddock)["hla"] == "skip"
    p = str(paddock)
    assert run("decide", "--paddock", p, "--stage", "hla", "--decision", "execute", "--reason", "high risk")[0] == 0  # fmt: skip
    assert decisions(paddock)["hla"] == "execute"


def test_code_generation_keeps_the_approved_plan_in_every_scope() -> None:
    catalog = json.loads(
        (SCRIPT.parent.parent / "assets" / "stages.json").read_text(encoding="utf-8")
    )["stages"]
    by_id = {s["id"]: s for s in catalog}
    cg = by_id["code-generation"]
    assert cg["scopes"] == ["classic", "express", "bugfix"]
    assert "plan stays on" in cg["runs_when"] and "regression test" in cg["runs_when"]
    assert "regression test" in by_id["build-and-test"]["runs_when"]


def test_the_design_stages_are_decided_per_unit_with_the_unit_kind(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path)
    spec = tmp_path / "units.json"
    spec.write_text(
        json.dumps({"units": [{"id": "u1", "name": "A", "kind": "ui"}, {"id": "u2", "name": "B"}],
                    "bolts": [{"id": "b1", "units": ["u1", "u2"]}]}),
        encoding="utf-8",
    )  # fmt: skip
    code, data = run("units", "--paddock", str(paddock), "--set", str(spec))
    assert code == 0 and data["missing_kind"] == ["u2"]
    state = json.loads((paddock / "state.json").read_text(encoding="utf-8"))
    assert [u["kind"] for u in state["units"]] == ["ui", None]
    assert state["units"][0]["stages"]["functional-design"]["decision"] == "pending"
    # the decision is recorded per unit, with a reason
    p = str(paddock)
    assert run("decide", "--paddock", p, "--stage", "functional-design", "--unit", "u1", "--decision", "skip", "--reason", "ui only wraps an API")[0] == 0  # fmt: skip
    state = json.loads((paddock / "state.json").read_text(encoding="utf-8"))
    assert state["units"][0]["stages"]["functional-design"]["decision"] == "skip"
    assert state["units"][1]["stages"]["functional-design"]["decision"] == "pending"


def test_units_reject_an_unknown_kind_and_keep_the_old_units(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path)
    spec = tmp_path / "units.json"
    spec.write_text(json.dumps({"units": [{"id": "u1", "kind": "microservice"}]}), encoding="utf-8")
    assert run("units", "--paddock", str(paddock), "--set", str(spec))[0] == 4
    assert json.loads((paddock / "state.json").read_text(encoding="utf-8"))["units"] == []


def test_a_kind_survives_a_reload_that_omits_it(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path)
    spec = tmp_path / "units.json"
    spec.write_text(json.dumps({"units": [{"id": "u1", "kind": "library"}]}), encoding="utf-8")
    run("units", "--paddock", str(paddock), "--set", str(spec))
    spec.write_text(json.dumps({"units": [{"id": "u1", "name": "renamed"}]}), encoding="utf-8")
    run("units", "--paddock", str(paddock), "--set", str(spec))
    state = json.loads((paddock / "state.json").read_text(encoding="utf-8"))
    assert state["units"][0]["kind"] == "library"
