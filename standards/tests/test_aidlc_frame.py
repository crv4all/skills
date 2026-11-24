"""Frame bolts in ``aidlc_state.py``: programme-level design that ends at the HLA gate.

A frame designs no component, so every stage after the HLA is skipped with a
reason, ``next`` is done once the HLA gate is approved, and ``close --status
complete`` succeeds without anyone deciding Inception and Construction by hand.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts" / "aidlc_state.py"
CATALOG = json.loads((SCRIPT.parent.parent / "assets" / "stages.json").read_text(encoding="utf-8"))[
    "stages"
]
HLA_ORDER = next(s["order"] for s in CATALOG if s["id"] == "hla")
LATE = [s["id"] for s in CATALOG if s["order"] > HLA_ORDER and not s["per_unit"]]
FRAME_REASON = "frame bolt: designs no component"

QUESTIONS = (
    "## Q1 Scope\nContext.\n\nA) One\nB) Two\nX) Other (describe)\n\n"
    "Recommended: A - simple.\n\nAnswer: A\n"
)
SIGNED = (
    '# HLA\n\n```yaml\nstatus: accepted\nsigned_off_by: "Rae Viewer"\n'
    'signed_off_on: "2026-11-20"\n```\n\n## Digest\n- point\n'
)


def run(*args: str) -> tuple[int, dict[str, Any]]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60
    )
    return done.returncode, (json.loads(done.stdout) if done.stdout.startswith("{") else {})


def open_bolt(root: Path, *args: str) -> Path:
    code, data = run(
        "open", "--root", str(root), "--slug", "programme", "--title", "Programme",
        "--intent", "Frame it", "--date", "2026-01-05", *args,
    )  # fmt: skip
    assert code == 0, data
    return Path(data["bolt"])


def state(bolt: Path) -> dict[str, Any]:
    return json.loads((bolt / "state.json").read_text(encoding="utf-8"))


def approve_hla(bolt: Path) -> None:
    p = str(bolt)
    assert run("gate", "--bolt", p, "--stage", "workspace-detection", "--approve", "--by", "B")[0] == 0  # fmt: skip
    run("decide", "--bolt", p, "--stage", "document-knowledge", "--decision", "skip", "--reason", "none")  # fmt: skip
    for round_id in "abc":
        (bolt / f"architecture/hla-questions-{round_id}.md").write_text(QUESTIONS, "utf-8")
    (bolt / "architecture/hla.md").write_text(SIGNED, encoding="utf-8")
    (bolt / "architecture/hla-decisions.md").write_text("# D\n\n## Digest\n- a\n", "utf-8")
    assert run("step", "--bolt", p, "--stage", "hla", "--to", "produced")[0] == 0
    code, data = run("gate", "--bolt", p, "--stage", "hla", "--approve", "--by", "Rae Viewer")
    assert code == 0, data


def test_open_frame_skips_every_stage_after_the_hla(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path, "--kind", "frame")
    stages = state(bolt)["stages"]
    assert state(bolt)["kind"] == "frame"
    assert LATE and all(
        (stages[s]["decision"], stages[s]["reason"]) == ("skip", FRAME_REASON) for s in LATE
    )
    assert stages["hla"]["decision"] == "execute"
    assert stages["reverse-engineering"]["reason"] == "no brownfield target"


def test_the_default_kind_is_delivery(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path)
    assert state(bolt)["kind"] == "delivery"
    assert state(bolt)["stages"]["requirements-analysis"]["decision"] == "execute"


def test_a_frame_is_done_at_the_hla_gate_and_closes_complete(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path, "--kind", "frame")
    approve_hla(bolt)
    code, data = run("next", "--bolt", str(bolt))
    assert code == 0 and data["done"] and data["action"] == "close"
    code, data = run("close", "--bolt", str(bolt), "--status", "complete")
    assert code == 0, data
    assert state(bolt)["status"] == "complete"


def test_status_shows_the_kind(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path, "--kind", "frame")
    code, data = run("status", "--bolt", str(bolt))
    assert code == 0 and data["kind"] == "frame"
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "status", "--bolt", str(bolt), "--format", "text"],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert "Kind: frame" in done.stdout


def test_a_frame_in_a_unit_scope_skips_its_unit_stages(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path, "--kind", "frame", "--scope", "express", "--depth", "standard")
    unit_stages = state(bolt)["units"][0]["stages"]
    assert all(rec["decision"] == "skip" for rec in unit_stages.values())


def test_kind_converts_a_delivery_bolt_and_back(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path)
    before = state(bolt)["stages"]
    code, data = run("kind", "--bolt", str(bolt), "--set", "frame")
    assert code == 0 and (data["previous"], data["kind"]) == ("delivery", "frame")
    assert all(state(bolt)["stages"][s]["reason"] == FRAME_REASON for s in LATE)
    assert "| kind |" in (bolt / "log.md").read_text(encoding="utf-8").splitlines()[-1]
    assert run("kind", "--bolt", str(bolt), "--set", "delivery")[0] == 0
    after = state(bolt)["stages"]
    assert {s: after[s]["decision"] for s in LATE} == {s: before[s]["decision"] for s in LATE}
    assert after["user-stories"]["decision"] == "pending"


def test_kind_is_refused_once_a_later_stage_has_started(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path)
    p = str(bolt)
    assert run("step", "--bolt", p, "--stage", "requirements-analysis", "--to", "asked")[0] == 0
    before = state(bolt)
    code, data = run("kind", "--bolt", p, "--set", "frame")
    assert code == 1
    assert [(f["code"], f["stage"]) for f in data["findings"]] == [
        ("stage-started", "requirements-analysis")
    ]
    assert state(bolt) == before


def test_kind_checks_unit_stages_too(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path, "--scope", "bugfix")
    p = str(bolt)
    run("jira", "--bolt", p, "--off", "--reason", "test")
    run("step", "--bolt", p, "--stage", "code-generation", "--unit", "u1", "--to", "produced")
    code, data = run("kind", "--bolt", p, "--set", "frame")
    assert code == 1 and data["findings"][0]["unit"] == "u1"


def test_a_frame_can_have_a_parent(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path, "--kind", "frame")
    code, data = run(
        "open", "--root", str(tmp_path), "--slug", "sub", "--title", "Sub", "--intent", "Nest",
        "--date", "2026-01-06", "--kind", "frame", "--parent", bolt.name,
    )  # fmt: skip
    assert code == 0, data


def test_a_frame_skips_the_operation_stages_and_an_old_frame_state_still_works(
    tmp_path: Path,
) -> None:
    bolt = open_bolt(tmp_path, "--kind", "frame")
    data = state(bolt)
    for stage in ("deployment-pipeline", "deployment-execution"):
        assert data["stages"][stage]["reason"] == FRAME_REASON
        del data["stages"][stage]
    (bolt / "state.json").write_text(json.dumps(data), encoding="utf-8")
    approve_hla(bolt)
    code, out = run("next", "--bolt", str(bolt))
    assert code == 0 and out["done"], out


def test_a_frame_has_no_units_to_refuse_and_may_record_an_epic(tmp_path: Path) -> None:
    bolt = open_bolt(tmp_path, "--kind", "frame")
    p = str(bolt)
    assert state(bolt)["units"] == []
    assert run("jira", "--bolt", p, "--epic", "ABC-1")[0] == 0
    approve_hla(bolt)
    assert run("close", "--bolt", p, "--status", "complete")[0] == 0
