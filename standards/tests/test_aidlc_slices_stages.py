"""Build and Test and Operation run once per Slice, each Slice at its own pace.

Their records live in the Slice, their files under ``docs/slices/<slice>/``, and what one
Slice does never moves another Slice or any Unit of another Slice.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import test_aidlc_state_git as gitbase
from test_aidlc_state import SCRIPT, Bolt, digest, open_bolt, skip_inception, skip_unit_stages
from test_aidlc_state_git import Repos, bolt_of, git, script, write

identity = gitbase.identity  # the fixtures of the git tests, reused as they are
repos = gitbase.repos

UNIT_STAGES = ("functional-design", "nfr-requirements", "nfr-design", "infrastructure-design")
BAT_FILES = ("build-instructions.md", "build-and-test-summary.md", "cross-unit-traceability.md")


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


@pytest.fixture
def split(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path, "--units", "split")
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def put(p: Bolt, data: dict[str, Any]) -> tuple[int, dict[str, Any], str]:
    spec = p.root / "units.json"
    spec.write_text(json.dumps(data), encoding="utf-8")
    return p.run("units", "--set", str(spec))


def two_slices(p: Bolt) -> None:
    """s1 holds u1 (Ana) and u2 (Ben); s2 holds u3 (Cleo) and waits for s1."""
    skip_inception(p)
    code, data, _ = put(
        p,
        {
            "slices": [{"id": "s1", "owner": "Ana"}, {"id": "s2", "depends_on": ["s1"]}],
            "units": [
                {"id": "u1", "slice": "s1", "owner": "Ana"},
                {"id": "u2", "slice": "s1", "owner": "Ben"},
                {"id": "u3", "slice": "s2", "owner": "Cleo"},
            ],
        },
    )
    assert code == 0, data
    assert p.run("slice", "--ready", "s1")[0] == 0


def finish(p: Bolt, *units: str) -> None:
    for unit in units:
        skip_unit_stages(p, unit)


def write_bat(p: Bolt, sid: str, verdict: str = "Verdict: pass") -> None:
    base = f"docs/slices/{sid}/build-and-test/"
    for name in BAT_FILES:
        p.write(base + name, digest())
    p.write(base + "test-results.md", verdict + "\n\n" + digest())


def row(p: Bolt, sid: str) -> dict[str, Any]:
    return next(r for r in p.run("status")[1]["slice_details"] if r["id"] == sid)


def slice_record(p: Bolt, sid: str) -> dict[str, Any]:
    return next(s for s in p.state["slices"] if s["id"] == sid)


# --- where things live -----------------------------------------------------------


def test_slice_stage_files_live_under_the_slice(bolt: Bolt) -> None:
    two_slices(bolt)
    rows = bolt.run("inputs", "--stage", "build-and-test", "--slice", "s1")[1]
    paths = [r["path"] for r in rows.get("missing", [])] or [
        r["path"]
        for r in bolt.run("inputs", "--stage", "build-and-test", "--slice", "s1")[1]["inputs"]
    ]
    assert paths and "docs/construction/u3/code-generation/code-summary.md" not in paths
    assert "docs/construction/u1/code-generation/code-summary.md" in paths
    assert "docs/construction/u2/code-generation/code-summary.md" in paths
    assert rows["slice"] == "s1" and rows["unit"] is None
    pipeline = bolt.run("inputs", "--stage", "deployment-execution", "--slice", "s2")[1]
    assert {r["path"] for r in pipeline["missing"]} == {
        f"docs/slices/s2/deployment-pipeline/{name}.md"
        for name in ("release-plan", "runbook", "rollback-runbook", "verification-checks")
    }


def test_a_cancelled_unit_is_left_out_of_the_slice_inputs(bolt: Bolt) -> None:
    two_slices(bolt)
    bolt.run("units", "--cancel", "u2", "--reason", "dropped")
    out = bolt.run("inputs", "--stage", "build-and-test", "--slice", "s1")[1]
    assert not [r for r in out["inputs"] if "/u2/" in r["path"]]


# --- naming the Slice --------------------------------------------------------------


def test_one_slice_needs_no_flag_several_need_it(bolt: Bolt) -> None:
    skip_inception(bolt)
    put(bolt, {"slices": [{"id": "s1"}], "units": [{"id": "u1", "slice": "s1"}]})
    code, data, _ = bolt.run("decide", "--stage", "deployment-pipeline", "--decision", "skip",
                             "--reason", "no release")  # fmt: skip
    assert code == 0 and data["slice"] == "s1" and data["unit"] is None
    put(bolt, {"slices": [{"id": "s2"}]})
    code, data, _ = bolt.run("decide", "--stage", "deployment-execution", "--decision", "skip",
                               "--reason", "no release")  # fmt: skip
    assert code == 2 and "--slice" in data["error"] and "s1, s2" in data["error"]
    assert bolt.run("inputs", "--stage", "build-and-test")[0] == 2
    assert bolt.run("step", "--stage", "build-and-test", "--to", "asked")[0] == 2
    assert bolt.run("gate", "--stage", "build-and-test", "--approve")[0] == 2


def test_the_slice_and_unit_flags_are_not_mixed_up(bolt: Bolt) -> None:
    two_slices(bolt)
    assert bolt.run("inputs", "--stage", "build-and-test", "--unit", "u1")[0] == 2
    assert bolt.run("inputs", "--stage", "code-generation", "--slice", "s1")[0] == 2
    assert bolt.run("inputs", "--stage", "build-and-test", "--slice", "nope")[0] == 2
    assert bolt.run("inputs", "--stage", "requirements-analysis", "--slice", "s1")[0] == 2


def test_no_slice_yet_is_a_usage_error_naming_the_fix(bolt: Bolt) -> None:
    code, data, _ = bolt.run("decide", "--stage", "build-and-test", "--decision", "skip",
                             "--reason", "x")  # fmt: skip
    assert code == 2 and "slice --add" in data["error"]
    skip_inception(bolt)
    put(bolt, {"units": [{"id": "u1"}]})  # a Unit, but no Slice to run Build and Test for
    finish(bolt, "u1")
    nxt = bolt.run("next")[1]
    assert nxt["stage"] == "build-and-test" and "no Slice yet" in nxt["blocked"]


# --- routing ----------------------------------------------------------------------


def test_a_slice_reaches_build_and_test_regardless_of_the_others(bolt: Bolt) -> None:
    two_slices(bolt)
    bolt.run("slice", "--ready", "s2")
    nxt = bolt.run("next", "--slice", "s1")[1]
    assert nxt["stage"] == "build-and-test" and nxt["slice"] == "s1"
    assert nxt["blocked_by"] == ["units not finished: u1, u2"]
    finish(bolt, "u1", "u2")  # s2's Unit u3 has not started
    nxt = bolt.run("next", "--slice", "s1")[1]
    assert "blocked" not in nxt
    assert nxt["stage"] == "build-and-test" and nxt["blocked_by"] == []
    assert row(bolt, "s1")["status"] == "built" and row(bolt, "s2")["status"] == "ready"


def test_a_slice_that_depends_on_another_reports_the_wait(bolt: Bolt) -> None:
    two_slices(bolt)
    bolt.run("slice", "--ready", "s2")
    finish(bolt, "u3")
    nxt = bolt.run("next", "--slice", "s2")[1]
    assert nxt["blocked_by"] == ["waits for slice s1 (verified)"]
    assert nxt["blocked"] == "waits for slice s1 (verified)"
    assert row(bolt, "s2")["waits"] == ["waits for slice s1 (verified)"]
    finish(bolt, "u1", "u2")
    write_bat(bolt, "s1")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    assert bolt.run("gate", "--stage", "build-and-test", "--slice", "s1", "--approve")[0] == 0
    assert bolt.run("next", "--slice", "s2")[1]["blocked_by"] == []
    assert row(bolt, "s2")["waits"] == []


def test_a_unit_of_a_slice_that_is_not_ready_says_so_and_is_not_refused(bolt: Bolt) -> None:
    two_slices(bolt)
    nxt = bolt.run("next", "--unit", "u3")[1]
    assert nxt["blocked"] == "slice s2 is not ready"
    code, data, _ = bolt.run("decide", "--stage", "functional-design", "--unit", "u3",
                             "--decision", "skip", "--reason", "t")  # fmt: skip
    assert code == 0 and "warnings" not in data
    assert "blocked" not in bolt.run("next", "--unit", "u1")[1]


def test_planning_a_new_slice_changes_nothing_for_another_slices_unit(bolt: Bolt) -> None:
    two_slices(bolt)
    before = bolt.run("next", "--unit", "u1")[1]
    put(bolt, {"slices": [{"id": "s3", "name": "Later"}], "units": [{"id": "u4", "slice": "s3"}]})
    bolt.run("slice", "--ready", "s3", "--note", "go")
    after = bolt.run("next", "--unit", "u1")[1]
    assert after == before and "inception is not finished" not in json.dumps(after)
    assert bolt.run("next", "--unit", "u4")[1]["stage"] == "functional-design"


def test_next_lists_units_and_slices_in_progress_in_a_split_bolt(split: Bolt) -> None:
    two_slices(split)
    split.run("slice", "--ready", "s2")
    out = split.run("next")[1]
    assert out["action"] == "units" and [r["unit"] for r in out["units"]] == ["u1", "u2", "u3"]
    assert [r["slice"] for r in out["slices"]] == ["s1", "s2"]
    assert "slices in progress" in split.run("status")[1]["next_action"]
    finish(split, "u1", "u2", "u3")
    out = split.run("next")[1]
    assert out["units"] == [] and [r["stage"] for r in out["slices"]] == ["build-and-test"] * 2


def test_next_mine_includes_the_slices_the_actor_owns(
    bolt: Bolt, monkeypatch: pytest.MonkeyPatch
) -> None:
    two_slices(bolt)
    monkeypatch.setenv("AIDLC_ACTOR", "ana")
    out = bolt.run("next", "--mine")[1]
    assert [u["unit"] for u in out["units"]] == ["u1"]
    assert [s["slice"] for s in out["slices"]] == ["s1"]
    monkeypatch.setenv("AIDLC_ACTOR", "cleo")
    assert bolt.run("next", "--mine")[1]["slices"] == []


def test_status_and_overview_show_one_line_per_slice(bolt: Bolt) -> None:
    two_slices(bolt)
    skip_unit_stages(bolt, "u1")
    bolt.run("decide", "--stage", "code-generation", "--unit", "u2", "--decision", "execute",
             "--reason", "t")  # fmt: skip
    bolt.run("step", "--stage", "code-generation", "--unit", "u2", "--to", "asked")
    text = bolt.run("status", "--format", "text")[2]
    lines = [line for line in text.splitlines() if line.startswith("  slice ")]
    assert lines[0] == "  slice s1 | - | Ana | building | 1/2 units"
    assert lines[1] == "  slice s2 | - | - | planning | 0/1 units | waits for slice s1 (verified)"
    overview = subprocess.run(
        [sys.executable, str(SCRIPT), "overview", "--root", str(bolt.root), "--format", "text"],
        capture_output=True, text=True, timeout=60,
    ).stdout  # fmt: skip
    assert "  slice s1 | - | Ana | building | 1/2 units" in overview
    raw = subprocess.run(
        [sys.executable, str(SCRIPT), "overview", "--root", str(bolt.root)],
        capture_output=True, text=True, timeout=60,
    ).stdout  # fmt: skip
    data = json.loads(raw)
    assert [s["id"] for s in data["bolts"][0]["slices"]] == ["s1", "s2"]


# --- passing, reopening, closing ----------------------------------------------------


def test_a_slice_passes_build_and_test_and_is_then_verified_and_released(bolt: Bolt) -> None:
    two_slices(bolt)
    finish(bolt, "u1", "u2")
    write_bat(bolt, "s1")
    assert (
        bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")[0] == 0
    )
    code, data, _ = bolt.run("gate", "--stage", "build-and-test", "--slice", "s1", "--approve")
    assert code == 0 and data["slice"] == "s1" and data["verdict"] == "pass"
    assert row(bolt, "s1")["status"] == "verified" and row(bolt, "s1")["verdict"] == "pass"
    assert slice_record(bolt, "s2")["stages"]["build-and-test"]["step"] == "todo"  # untouched
    for stage in ("deployment-pipeline", "deployment-execution"):
        bolt.run("decide", "--stage", stage, "--slice", "s1", "--decision", "skip", "--reason", "n")
    assert row(bolt, "s1")["status"] == "verified"  # nothing was executed
    bolt.run("decide", "--stage", "deployment-execution", "--slice", "s1", "--decision",
             "execute", "--reason", "go")  # fmt: skip
    state = bolt.state
    state["slices"][0]["stages"]["deployment-execution"]["step"] = "approved"
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert row(bolt, "s1")["status"] == "released"
    assert row(bolt, "s2")["status"] == "planning"
    assert (
        "[slice s1]" not in bolt.run("status", "--format", "text")[2]
    )  # nothing stale or unverified


def test_a_fail_verdict_stays_open_for_the_slice(bolt: Bolt) -> None:
    two_slices(bolt)
    finish(bolt, "u1", "u2")
    write_bat(bolt, "s1", "Verdict: fail - 2 red")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    code, data, _ = bolt.run("gate", "--stage", "build-and-test", "--slice", "s1", "--approve",
                             "--note", "go on anyway")  # fmt: skip
    assert code == 1 and [f["code"] for f in data["findings"]] == ["verdict-fail"]
    assert data["findings"][0]["path"] == "docs/slices/s1/build-and-test/test-results.md"


def test_a_passed_slice_stage_can_be_reopened(bolt: Bolt) -> None:
    two_slices(bolt)
    finish(bolt, "u1", "u2")
    write_bat(bolt, "s1")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    bolt.run("gate", "--stage", "build-and-test", "--slice", "s1", "--approve")
    code, data, _ = bolt.run("gate", "--stage", "build-and-test", "--slice", "s1",
                             "--request-changes", "--note", "flaky suite")  # fmt: skip
    assert code == 0 and data["step"] == "changes-requested" and data["slice"] == "s1"
    record = slice_record(bolt, "s1")["stages"]["build-and-test"]
    assert record["approved_at"] is None and "verdict" not in record
    assert bolt.run("next", "--slice", "s1")[1]["stage"] == "build-and-test"
    assert any(
        "gate-request-changes" in line and "flaky suite" in line for line in bolt.log_lines()
    )


def test_close_needs_every_slice_and_every_live_unit_done(tmp_path: Path) -> None:
    done = open_bolt(tmp_path, "--scope", "bugfix")
    p = Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))
    code, data, _ = p.run("close", "--status", "complete")
    assert code == 1
    stages = {(f["code"], f.get("stage"), f.get("slice")) for f in data["findings"]}
    assert ("stage-not-approved", "build-and-test", "s1") in stages
    assert ("stage-not-approved", "code-generation", None) in stages


def test_a_cancelled_unit_does_not_hold_the_close_back(bolt: Bolt) -> None:
    two_slices(bolt)
    bolt.run("units", "--cancel", "u3", "--reason", "dropped")
    finding = bolt.run("close", "--status", "complete")[1]["findings"]
    assert not [f for f in finding if f.get("unit") == "u3"]


def test_a_bolt_with_no_slice_cannot_close_complete(bolt: Bolt) -> None:
    code, data, _ = bolt.run("close", "--status", "complete")
    assert code == 1
    assert any(
        f["code"] == "units-not-loaded" and "Slice" in f["message"] for f in data["findings"]
    )


# --- git ----------------------------------------------------------------------------


def test_a_change_to_a_passed_slice_artifact_warns_and_names_the_slice(repos: Repos) -> None:
    assert gitbase.open_demo(repos.a, "--scope", "bugfix")[0] == 0
    bolt = bolt_of(repos.a)
    for stage in ("workspace-detection",):
        script("gate", "--bolt", str(bolt), "--stage", stage, "--approve", "--by", "Ada")
    base = bolt / "docs" / "slices" / "s1" / "build-and-test"
    for name in BAT_FILES:
        write(base / name, digest())
    write(base / "test-results.md", "Verdict: pass\n\n" + digest())
    skip = ("--decision", "skip", "--reason", "t")
    for stage in (*UNIT_STAGES, "code-generation"):
        script("decide", "--bolt", str(bolt), "--stage", stage, "--unit", "u1", *skip)
    common = ["--bolt", str(bolt), "--stage", "build-and-test"]
    assert script("step", *common, "--to", "produced")[0] == 0
    code, out, _ = script("gate", *common, "--approve", "--by", "Ada")
    assert code == 0, out
    write(base / "test-results.md", "Verdict: pass\n\n" + digest() + "more\n")
    code, out, _ = script("sync", "--bolt", str(bolt), "-m", "edit the results")
    assert code == 0, out
    warnings = [w for w in out["git"]["warnings"] if w.startswith("changed after the checkpoint")]
    assert warnings == [
        "changed after the checkpoint: docs/slices/s1/build-and-test/test-results.md "
        "(stage build-and-test is passed; reopen it with gate --request-changes --slice s1 "
        '--note "<why>")'
    ]
    assert git(repos.a, "status", "--porcelain") == ""


def verify_s1(p: Bolt) -> None:
    two_slices(p)
    finish(p, "u1", "u2")
    write_bat(p, "s1")
    p.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    assert p.run("gate", "--stage", "build-and-test", "--slice", "s1", "--approve")[0] == 0
    assert row(p, "s1")["status"] == "verified"


def test_a_unit_added_to_a_verified_slice_reopens_its_verification(bolt: Bolt) -> None:
    verify_s1(bolt)
    code, data, _ = put(bolt, {"units": [{"id": "u9", "slice": "s1", "owner": "Ana"}]})
    assert code == 0 and any("must run again" in w for w in data["warnings"]), data
    now = row(bolt, "s1")
    assert now["status"] != "verified" and now["verdict"] is None and now["units_total"] == 3
    assert slice_record(bolt, "s1")["stages"]["build-and-test"]["step"] == "changes-requested"
    assert bolt.run("next", "--slice", "s1")[1]["stage"] == "build-and-test"
    assert row(bolt, "s2")["waits"] == ["waits for slice s1 (verified)"]  # s2 waits again


def test_a_reopened_unit_of_a_verified_slice_reopens_its_verification(bolt: Bolt) -> None:
    two_slices(bolt)
    for unit in ("u1", "u2"):
        bolt.run("decide", "--stage", "functional-design", "--unit", unit, "--decision", "skip",
                 "--reason", "n")  # fmt: skip
        bolt.run("decide", "--stage", "code-generation", "--unit", unit, "--decision", "execute",
                 "--reason", "n")  # fmt: skip
    skip_unit_stages(bolt, "u1")
    skip_unit_stages(bolt, "u2")
    # a Unit stage that really ran can be reopened; reuse the state file to mark one approved
    state = bolt.state
    for u in state["units"]:
        if u["id"] == "u1":
            rec = u["stages"]["code-generation"]
            rec["decision"], rec["step"] = "execute", "approved"
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    write_bat(bolt, "s1")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    assert bolt.run("gate", "--stage", "build-and-test", "--slice", "s1", "--approve")[0] == 0
    code, data, _ = bolt.run("gate", "--stage", "code-generation", "--unit", "u1",
                             "--request-changes", "--note", "redo")  # fmt: skip
    assert code == 0 and any("must run again" in w for w in data["warnings"]), data
    assert row(bolt, "s1")["status"] != "verified"


def test_a_unit_added_to_a_released_slice_reopens_its_release(bolt: Bolt) -> None:
    verify_s1(bolt)
    bolt.run("decide", "--stage", "deployment-pipeline", "--slice", "s1", "--decision", "skip",
             "--reason", "n")  # fmt: skip
    bolt.run("decide", "--stage", "deployment-execution", "--slice", "s1", "--decision",
             "execute", "--reason", "go")  # fmt: skip
    state = bolt.state
    state["slices"][0]["stages"]["deployment-execution"]["step"] = "approved"
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert row(bolt, "s1")["status"] == "released"
    code, data, _ = put(bolt, {"units": [{"id": "u9", "slice": "s1", "owner": "Ana"}]})
    assert code == 0, data
    assert any("was released" in w and "deployment-execution" in w for w in data["warnings"])
    stages = slice_record(bolt, "s1")["stages"]
    assert stages["deployment-execution"]["step"] == "changes-requested"
    assert stages["deployment-pipeline"]["decision"] == "skip"  # a skipped stage is left alone
    assert row(bolt, "s1")["status"] not in ("verified", "released")
    finish(bolt, "u9")
    write_bat(bolt, "s1")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    assert bolt.run("gate", "--stage", "build-and-test", "--slice", "s1", "--approve")[0] == 0
    assert row(bolt, "s1")["status"] == "verified"  # tested again; the release is still owed
    assert bolt.run("next", "--slice", "s1")[1]["stage"] == "deployment-execution"
