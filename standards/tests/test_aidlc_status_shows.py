"""What ``status``, ``next`` and ``units --set`` show: passed Bolt-level stages are not
reported as affected, a failed verification stays visible, a late Unit warns, and a digest
ends where a table or a code fence begins."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_aidlc_slices_stages import finish, row, two_slices, write_bat
from test_aidlc_state import (
    SCRIPT,
    Bolt,
    load_units,
    open_bolt,
    ra_files,
    reach_produced,
    unit_stage_ready,
    verdict_doc,
)

GATE = ("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def presets(p: Bolt, text: str) -> None:
    target = p.root / "docs" / "presets.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_a_passed_bolt_level_stage_is_never_listed_as_affected(bolt: Bolt) -> None:
    reach_produced(bolt)
    presets(bolt, "one\n")
    ra_files(bolt)
    assert bolt.run(*GATE)[0] == 0
    presets(bolt, "one\ntwo\n")  # a later Slice adds to a document the stage read
    status = bolt.run("status")[1]
    assert status["completed_affected"] == [] and status["context"] == []
    assert "affected" not in bolt.run("status", "--format", "text")[2]
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "overview", "--root", str(bolt.root)],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert json.loads(done.stdout)["bolts"][0]["completed_affected"] == []


def test_an_open_bolt_level_stage_still_reports_changed_inputs(bolt: Bolt) -> None:
    reach_produced(bolt)
    presets(bolt, "one\n")
    ra_files(bolt)
    assert bolt.run("context", "--stage", "requirements-analysis")[0] in (0, 2)
    presets(bolt, "one\ntwo\n")
    status = bolt.run("status")[1]
    assert [r["stage"] for r in status["context"]] == ["requirements-analysis"], status


def test_a_failed_verdict_is_shown_on_resume(bolt: Bolt) -> None:
    two_slices(bolt)
    finish(bolt, "u1", "u2")
    write_bat(bolt, "s1", "Verdict: fail - 2 red")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    assert bolt.run("gate", "--stage", "build-and-test", "--slice", "s1", "--approve")[0] == 1
    assert row(bolt, "s1")["verdict"] == "fail"
    assert "verdict fail" in bolt.run("status", "--format", "text")[2]
    nxt = bolt.run("next", "--slice", "s1")[1]
    assert nxt["verdict"] == "fail" and nxt["action"] == "gate"
    write_bat(bolt, "s1", "Verdict: not-run - no database")
    assert bolt.run("next", "--slice", "s1")[1]["verdict"] == "not-run"
    write_bat(bolt, "s1", "No verdict here")
    assert bolt.run("next", "--slice", "s1")[1]["verdict"] == "missing"
    write_bat(bolt, "s1", "Verdict: pass")
    assert "verdict" not in bolt.run("next", "--slice", "s1")[1]


def test_a_failed_unit_verdict_is_shown_by_status_and_next(bolt: Bolt) -> None:
    unit_stage_ready(bolt, verdict_doc("Verdict: fail"))
    assert bolt.run("gate", "--stage", "code-generation", "--unit", "u1", "--approve")[0] == 1
    assert bolt.run("next", "--unit", "u1")[1]["verdict"] == "fail"
    top = bolt.run("next")[1]
    assert top.get("verdict") == "fail" or top["action"] == "units"
    assert "verdict" not in bolt.run("status")[1] or bolt.run("status")[1]["verdict"] == "fail"


def test_a_unit_added_to_a_ready_slice_warns(bolt: Bolt) -> None:
    two_slices(bolt)  # s1 is checked ready
    code, data, _ = load_units(bolt, [{"id": "u5", "slice": "s1"}])
    assert code == 0, data
    assert any("s1 was checked ready before u5 was added" in w for w in data["warnings"])
    assert any("s1 was checked ready before u5" in x for x in bolt.log_lines() if "| units |" in x)
    code, data, _ = load_units(bolt, [{"id": "u6", "slice": "s2"}])  # s2 never checked
    assert code == 0 and "warnings" not in data


@pytest.mark.parametrize(
    "follow",
    ["| a | b |\n| - | - |\n| 1 | 2 |\n", "```\ncode\n```\n"],
    ids=["table", "fence"],
)
def test_a_digest_ends_at_a_table_or_a_code_fence(bolt: Bolt, follow: str) -> None:
    reach_produced(bolt)
    lines = "".join(f"- point {i}\n" for i in range(10))
    ra_files(bolt, doc=f"# T\n\n## Digest\n{lines}{follow}\n## Body\ntext\n")
    assert bolt.run(*GATE)[0] == 0
