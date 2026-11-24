"""Parent and child bolts in ``aidlc_state.py``.

A programme has one bolt whose HLA fixes principles and phases, and one
bolt per phase whose HLA builds on it. The child must read the parent's
settled decisions rather than ask them again, so ``inputs`` lists them and
``status`` says whether the parent's HLA is accepted yet.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts" / "aidlc_state.py"

HLA = "# HLA\n\n```yaml\nstatus: {status}\n```\n\n## Digest\n- point\n"
DIGEST = "# T\n\n## Digest\n- point\n"


def run(*args: str) -> tuple[int, dict[str, Any], str]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60
    )
    data = json.loads(done.stdout) if done.stdout.startswith("{") else {}
    return done.returncode, data, done.stdout


def open_bolt(root: Path, slug: str, *args: str) -> tuple[int, dict[str, Any]]:
    code, data, _ = run(
        "open", "--root", str(root), "--slug", slug, "--title", slug.title(),
        "--intent", "Try", "--date", "2026-01-05", *args,
    )  # fmt: skip
    return code, data


def state(bolt: Path) -> dict[str, Any]:
    return json.loads((bolt / "state.json").read_text(encoding="utf-8"))


def frame_and_child(root: Path, *child_args: str) -> tuple[Path, Path]:
    code, frame = open_bolt(root, "programme")
    assert code == 0, frame
    code, child = open_bolt(root, "phase-one", "--parent", frame["id"], *child_args)
    assert code == 0, child
    return Path(frame["bolt"]), Path(child["bolt"])


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_open_records_the_parent_by_id(tmp_path: Path) -> None:
    frame, child = frame_and_child(tmp_path)
    assert state(child)["parent"] == {
        "id": "2026-01-05-programme",
        "path": "bolts/2026-01-05-programme",
    }
    log = (child / "log.md").read_text(encoding="utf-8")
    assert "| parent |" in log and "2026-01-05-programme" in log
    assert "parent" not in state(frame)


def test_open_accepts_the_parent_as_a_path(tmp_path: Path) -> None:
    _, frame = open_bolt(tmp_path, "programme")
    code, data = open_bolt(tmp_path, "phase-one", "--parent", frame["bolt"])
    assert code == 0 and data["parent"]["id"] == "2026-01-05-programme"


def test_open_refuses_a_parent_that_does_not_exist(tmp_path: Path) -> None:
    code, _ = open_bolt(tmp_path, "phase-one", "--parent", "2026-01-05-nothing")
    assert code == 3
    assert not (tmp_path / "bolts" / "2026-01-05-phase-one").exists()


def test_open_refuses_a_parent_under_another_root(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _, frame = open_bolt(other, "programme")
    plan = tmp_path / "plan"
    plan.mkdir()
    code, _ = open_bolt(plan, "phase-one", "--parent", frame["bolt"])
    assert code == 2


def test_status_shows_the_parent_and_its_hla_status(tmp_path: Path) -> None:
    frame, child = frame_and_child(tmp_path)
    code, data, _ = run("status", "--bolt", str(child))
    assert code == 0 and data["parent"]["id"] == "2026-01-05-programme"
    assert data["parent_hla_status"] == "missing"
    write(frame / "architecture" / "hla.md", HLA.format(status="in-review"))
    _, _, text = run("status", "--bolt", str(child), "--format", "text")
    assert "Parent: 2026-01-05-programme (HLA in-review)" in text
    assert len(text.splitlines()) <= 20


def test_child_hla_inputs_read_the_parent(tmp_path: Path) -> None:
    frame, child = frame_and_child(tmp_path)
    run("decide", "--bolt", str(child), "--stage", "document-knowledge", "--decision", "skip",
        "--reason", "no documents")  # fmt: skip
    code, data, _ = run("inputs", "--bolt", str(child), "--stage", "hla")
    assert code == 3
    assert {"path": "parent:architecture/hla.md", "produced_by": "parent:hla"} in data["missing"]
    write(frame / "architecture" / "hla.md", HLA.format(status="accepted"))
    write(frame / "architecture" / "hla-decisions.md", DIGEST)
    code, data, _ = run("inputs", "--bolt", str(child), "--stage", "hla")
    assert code == 0, data
    rows = {row["path"]: row for row in data["inputs"]}
    assert rows["parent:architecture/hla.md"]["mode"] == "digest"
    assert rows["parent:architecture/hla.md"]["file"] == str(
        (frame / "architecture" / "hla.md").resolve()
    )
    assert rows["parent:knowledge/_digest.md"]["optional"]
    assert data["parent_hla_status"] == "accepted" and data["warnings"] == []


def test_a_parent_hla_in_review_is_a_warning_not_a_refusal(tmp_path: Path) -> None:
    frame, child = frame_and_child(tmp_path)
    run("decide", "--bolt", str(child), "--stage", "document-knowledge", "--decision", "skip",
        "--reason", "no documents")  # fmt: skip
    write(frame / "architecture" / "hla.md", HLA.format(status="in-review"))
    write(frame / "architecture" / "hla-decisions.md", DIGEST)
    code, data, _ = run("inputs", "--bolt", str(child), "--stage", "hla")
    assert code == 0
    assert data["parent_hla_status"] == "in-review"
    assert [w["code"] for w in data["warnings"]] == ["parent-hla-not-accepted"]


def test_a_bolt_without_a_parent_lists_no_parent_inputs(tmp_path: Path) -> None:
    code, data = open_bolt(tmp_path, "solo")
    run("decide", "--bolt", data["bolt"], "--stage", "document-knowledge", "--decision",
        "skip", "--reason", "none")  # fmt: skip
    code, data, _ = run("inputs", "--bolt", data["bolt"], "--stage", "hla")
    assert code == 0
    assert not [row for row in data["inputs"] if row["path"].startswith("parent:")]
    assert "parent_hla_status" not in data


def test_reverse_engineering_reads_a_scope_card_only_when_it_exists(tmp_path: Path) -> None:
    svc = tmp_path / "svc"
    svc.mkdir()
    (svc / "app.py").write_text("x = 1\n", encoding="utf-8")
    web = tmp_path / "web"
    web.mkdir()
    frame, child = frame_and_child(tmp_path, "--target", f"svc={svc}", "--target", f"web={web}")
    write(frame / "knowledge" / "repos" / "svc.md", "# svc scope\n")
    run("decide", "--bolt", str(child), "--stage", "document-knowledge", "--decision", "skip",
        "--reason", "no documents")  # fmt: skip
    code, data, _ = run("inputs", "--bolt", str(child), "--stage", "reverse-engineering")
    assert code == 0, data
    paths = [row["path"] for row in data["inputs"]]
    assert "parent:knowledge/repos/svc.md" in paths
    assert "parent:knowledge/repos/web.md" not in paths
    row = next(r for r in data["inputs"] if r["path"] == "parent:knowledge/repos/svc.md")
    assert row["mode"] == "full" and row["exists"]


def test_the_workspace_lists_the_parent_after_the_planning_repo(tmp_path: Path) -> None:
    frame, child = frame_and_child(tmp_path)
    code, data, _ = run("workspace", "--bolt", str(child))
    assert code == 0
    assert [f["name"] for f in data["folders"]][:3] == [
        "bolt: phase-one",
        "planning repo",
        "parent: programme",
    ]
    assert data["folders"][2]["path"] == str(frame.resolve())


def test_child_decision_ids_start_at_d1(tmp_path: Path) -> None:
    frame, child = frame_and_child(tmp_path)
    run("decision-id", "--bolt", str(frame), "--count", "4")
    _, data, _ = run("decision-id", "--bolt", str(child))
    assert data["ids"] == ["D1"]
