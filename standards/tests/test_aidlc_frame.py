"""Frame paddocks in ``aidlc_state.py``: programme-level design that ends at the HLA gate.

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
FRAME_REASON = "frame paddock: designs no component"

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


def open_paddock(root: Path, *args: str) -> Path:
    code, data = run(
        "open", "--root", str(root), "--slug", "programme", "--title", "Programme",
        "--intent", "Frame it", "--date", "2026-01-05", *args,
    )  # fmt: skip
    assert code == 0, data
    return Path(data["paddock"])


def state(paddock: Path) -> dict[str, Any]:
    return json.loads((paddock / "state.json").read_text(encoding="utf-8"))


def approve_hla(paddock: Path) -> None:
    p = str(paddock)
    assert run("gate", "--paddock", p, "--stage", "workspace-detection", "--approve", "--by", "B")[0] == 0  # fmt: skip
    run("decide", "--paddock", p, "--stage", "document-knowledge", "--decision", "skip", "--reason", "none")  # fmt: skip
    for round_id in "abc":
        (paddock / f"architecture/hla-questions-{round_id}.md").write_text(QUESTIONS, "utf-8")
    (paddock / "architecture/hla.md").write_text(SIGNED, encoding="utf-8")
    (paddock / "architecture/hla-decisions.md").write_text("# D\n\n## Digest\n- a\n", "utf-8")
    assert run("step", "--paddock", p, "--stage", "hla", "--to", "produced")[0] == 0
    code, data = run("gate", "--paddock", p, "--stage", "hla", "--approve", "--by", "Rae Viewer")
    assert code == 0, data


def test_open_frame_skips_every_stage_after_the_hla(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path, "--kind", "frame")
    stages = state(paddock)["stages"]
    assert state(paddock)["kind"] == "frame"
    assert LATE and all(
        (stages[s]["decision"], stages[s]["reason"]) == ("skip", FRAME_REASON) for s in LATE
    )
    assert stages["hla"]["decision"] == "execute"
    assert stages["reverse-engineering"]["reason"] == "no brownfield target"


def test_the_default_kind_is_delivery(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path)
    assert state(paddock)["kind"] == "delivery"
    assert state(paddock)["stages"]["requirements-analysis"]["decision"] == "execute"


def test_a_frame_is_done_at_the_hla_gate_and_closes_complete(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path, "--kind", "frame")
    approve_hla(paddock)
    code, data = run("next", "--paddock", str(paddock))
    assert code == 0 and data["done"] and data["action"] == "close"
    code, data = run("close", "--paddock", str(paddock), "--status", "complete")
    assert code == 0, data
    assert state(paddock)["status"] == "complete"


def test_status_shows_the_kind(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path, "--kind", "frame")
    code, data = run("status", "--paddock", str(paddock))
    assert code == 0 and data["kind"] == "frame"
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "status", "--paddock", str(paddock), "--format", "text"],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert "Kind: frame" in done.stdout


def test_a_frame_in_a_unit_scope_skips_its_unit_stages(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path, "--kind", "frame", "--scope", "express", "--depth", "standard")
    unit_stages = state(paddock)["units"][0]["stages"]
    assert all(rec["decision"] == "skip" for rec in unit_stages.values())


def test_kind_converts_a_delivery_paddock_and_back(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path)
    before = state(paddock)["stages"]
    code, data = run("kind", "--paddock", str(paddock), "--set", "frame")
    assert code == 0 and (data["previous"], data["kind"]) == ("delivery", "frame")
    assert all(state(paddock)["stages"][s]["reason"] == FRAME_REASON for s in LATE)
    assert "| kind |" in (paddock / "log.md").read_text(encoding="utf-8").splitlines()[-1]
    assert run("kind", "--paddock", str(paddock), "--set", "delivery")[0] == 0
    after = state(paddock)["stages"]
    assert {s: after[s]["decision"] for s in LATE} == {s: before[s]["decision"] for s in LATE}
    assert after["user-stories"]["decision"] == "pending"


def test_kind_is_refused_once_a_later_stage_has_started(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path)
    p = str(paddock)
    assert run("step", "--paddock", p, "--stage", "requirements-analysis", "--to", "asked")[0] == 0
    before = state(paddock)
    code, data = run("kind", "--paddock", p, "--set", "frame")
    assert code == 1
    assert [(f["code"], f["stage"]) for f in data["findings"]] == [
        ("stage-started", "requirements-analysis")
    ]
    assert state(paddock) == before


def test_kind_checks_unit_stages_too(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path, "--scope", "bugfix")
    p = str(paddock)
    run("step", "--paddock", p, "--stage", "code-generation", "--unit", "u1", "--to", "produced")
    code, data = run("kind", "--paddock", p, "--set", "frame")
    assert code == 1 and data["findings"][0]["unit"] == "u1"


def test_a_frame_can_have_a_parent(tmp_path: Path) -> None:
    paddock = open_paddock(tmp_path, "--kind", "frame")
    code, data = run(
        "open", "--root", str(tmp_path), "--slug", "sub", "--title", "Sub", "--intent", "Nest",
        "--date", "2026-01-06", "--kind", "frame", "--parent", paddock.name,
    )  # fmt: skip
    assert code == 0, data


def test_a_frame_skips_the_operation_stages_and_an_old_frame_state_still_works(
    tmp_path: Path,
) -> None:
    paddock = open_paddock(tmp_path, "--kind", "frame")
    data = state(paddock)
    for stage in ("deployment-pipeline", "deployment-execution"):
        assert data["stages"][stage]["reason"] == FRAME_REASON
        del data["stages"][stage]
    (paddock / "state.json").write_text(json.dumps(data), encoding="utf-8")
    approve_hla(paddock)
    code, out = run("next", "--paddock", str(paddock))
    assert code == 0 and out["done"], out
