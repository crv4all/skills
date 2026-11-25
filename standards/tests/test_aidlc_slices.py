"""A Slice is a small record with one readiness checkpoint; its status is derived.

Units belong to a Slice through their own ``slice`` key, so a Slice never stores its
members, and planning a new Slice adds records without touching existing ones.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from test_aidlc_state import (
    QUESTIONS,
    SCRIPT,
    Bolt,
    open_bolt,
    skip_inception,
    skip_unit_stages,
)


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def put(p: Bolt, data: dict[str, Any]) -> tuple[int, dict[str, Any], str]:
    spec = p.root / "units.json"
    spec.write_text(json.dumps(data), encoding="utf-8")
    return p.run("units", "--set", str(spec))


def two_slices(p: Bolt) -> None:
    """s1 holds u1 and u2, s2 holds u3; all three are loaded and owned."""
    code, data, _ = put(
        p,
        {
            "slices": [{"id": "s1", "name": "First"}, {"id": "s2", "name": "Second"}],
            "units": [
                {"id": "u1", "slice": "s1", "owner": "Ana"},
                {"id": "u2", "slice": "s1", "owner": "Ben"},
                {"id": "u3", "slice": "s2", "owner": "Cleo"},
            ],
        },
    )
    assert code == 0, data


def slice_of(p: Bolt, sid: str) -> dict[str, Any]:
    return next(s for s in p.state["slices"] if s["id"] == sid)


def row(p: Bolt, sid: str) -> dict[str, Any]:
    return next(r for r in p.run("status")[1]["slice_details"] if r["id"] == sid)


# --- the record ------------------------------------------------------------------


def test_a_slice_record_is_small_and_never_lists_its_units(bolt: Bolt) -> None:
    two_slices(bolt)
    record = slice_of(bolt, "s1")
    assert set(record) == {"id", "name", "owner", "depends_on", "ready", "stages"}
    assert record["name"] == "First" and record["ready"] is None and record["depends_on"] == []
    assert [u["slice"] for u in bolt.state["units"]] == ["s1", "s1", "s2"]


def test_the_older_slice_shape_is_accepted_and_dropped_at_the_next_write(bolt: Bolt) -> None:
    code, _, _ = put(
        bolt, {"units": [{"id": "u1"}, {"id": "u2"}], "slices": [{"id": "s1", "units": ["u1"]}]}
    )
    assert code == 0 and "units" not in slice_of(bolt, "s1")
    assert [u.get("slice") for u in bolt.state["units"]] == ["s1", None]
    state = bolt.state
    state["slices"] = [{"id": "s1", "units": ["u1", "u2"], "status": "todo"}]
    state["units"][1]["slice"] = None
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert bolt.run("park", "--note", "n")[0] == 0
    record = slice_of(bolt, "s1")
    assert "units" not in record and "status" not in record
    assert [u["slice"] for u in bolt.state["units"]] == ["s1", "s1"]  # the listed Unit got its key


def test_slices_in_a_file_are_merged_by_id(bolt: Bolt) -> None:
    two_slices(bolt)
    bolt.run("slice", "--ready", "s1", "--note", "go")
    before = slice_of(bolt, "s1")
    assert put(bolt, {"slices": [{"id": "s2", "name": "Renamed"}, {"id": "s3"}]})[0] == 0
    assert slice_of(bolt, "s1") == before
    assert slice_of(bolt, "s2")["name"] == "Renamed" and slice_of(bolt, "s3")["ready"] is None
    code, data, _ = put(bolt, {"slices": [{"id": "s1", "owner": "Dan"}]})
    assert code == 1 and "assign --slice" in data["error"]


def test_slice_add_assign_and_dependencies(bolt: Bolt) -> None:
    code = bolt.run("slice", "--add", "s1", "--name", "One", "--owner", "Ana")[0]
    assert code == 0 and slice_of(bolt, "s1")["owner"] == "Ana"
    assert bolt.run("slice", "--add", "s1")[0] == 1
    assert bolt.run("slice", "--add", "s2", "--depends-on", "s1")[0] == 0
    assert slice_of(bolt, "s2")["depends_on"] == ["s1"]
    assert bolt.run("slice", "--add", "s3", "--depends-on", "nope")[0] == 4
    assert bolt.run("slice", "--add", "s4", "--depends-on", "s4")[0] == 4
    assert [s["id"] for s in bolt.state["slices"]] == ["s1", "s2"]
    assert bolt.run("assign", "--slice", "s2", "--owner", "Cleo")[0] == 0
    assert slice_of(bolt, "s2")["owner"] == "Cleo"
    assert bolt.run("assign", "--slice", "s2", "--unit", "u1", "--owner", "X")[0] == 2
    assert bolt.run("assign", "--owner", "X")[0] == 2
    assert bolt.run("assign", "--slice", "none", "--owner", "X")[0] == 2


def test_a_slice_dependency_cycle_is_refused_in_a_file(bolt: Bolt) -> None:
    cycle = {"slices": [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]}
    code, data, _ = put(bolt, cycle)
    assert code == 4 and "a -> b -> a" in data["error"] and bolt.state["slices"] == []


def test_a_single_slice_bolt_is_ready_from_the_start(tmp_path: Path) -> None:
    done = open_bolt(tmp_path, "--scope", "bugfix")
    p = Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))
    ready = slice_of(p, "s1")["ready"]
    assert ready["note"] == "single-Slice Bolt" and ready["gaps"] == []
    assert row(p, "s1")["status"] == "ready"


# --- derived status ----------------------------------------------------------------


def test_the_status_of_a_slice_is_derived_from_what_happened(bolt: Bolt) -> None:
    skip_inception(bolt)
    put(bolt, {"slices": [{"id": "s1"}], "units": [{"id": "u1", "slice": "s1"}]})
    assert row(bolt, "s1")["status"] == "planning"
    assert bolt.run("slice", "--ready", "s1")[0] == 0
    assert row(bolt, "s1")["status"] == "ready"
    bolt.run("decide", "--stage", "functional-design", "--unit", "u1", "--decision", "skip",
             "--reason", "t")  # fmt: skip
    assert row(bolt, "s1")["status"] == "ready"  # a decision is not work
    bolt.run("decide", "--stage", "code-generation", "--unit", "u1", "--decision", "execute",
             "--reason", "t")  # fmt: skip
    bolt.run("step", "--stage", "code-generation", "--unit", "u1", "--to", "asked")
    assert row(bolt, "s1")["status"] == "building"
    skip_unit_stages(bolt, "u1")
    assert row(bolt, "s1")["status"] == "built"


def test_a_slice_with_no_units_is_planning(bolt: Bolt) -> None:
    bolt.run("slice", "--add", "s1")
    assert row(bolt, "s1")["status"] == "planning" and row(bolt, "s1")["units_total"] == 0


# --- the readiness checkpoint --------------------------------------------------------


def test_ready_refuses_structural_problems(bolt: Bolt) -> None:
    assert bolt.run("slice", "--ready", "nope")[0] == 1  # unknown
    bolt.run("slice", "--add", "s1")
    code, data, _ = bolt.run("slice", "--ready", "s1", "--note", "go")
    assert code == 1 and "no Units" in data["error"] and slice_of(bolt, "s1")["ready"] is None
    put(bolt, {"units": [{"id": "u1", "slice": "s1"}]})
    state = bolt.state
    state["slices"][0]["depends_on"] = ["ghost"]
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    code, data, _ = bolt.run("slice", "--ready", "s1", "--note", "go")
    assert code == 1 and "ghost" in data["error"]
    state["slices"][0]["depends_on"] = ["s1"]
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert bolt.run("slice", "--ready", "s1", "--note", "go")[0] == 1


def test_ready_without_gaps_is_recorded_and_logged(bolt: Bolt) -> None:
    skip_inception(bolt)
    two_slices(bolt)
    code, data, _ = bolt.run("slice", "--ready", "s2")
    assert code == 0 and data["ready"]["gaps"] == []
    assert slice_of(bolt, "s2")["ready"]["at"]
    assert any(" | slice-ready | " in line and "s2" in line for line in bolt.log_lines())
    assert row(bolt, "s2")["open_gaps"] == 0


def test_ready_lists_gaps_and_needs_a_note_to_go_on(bolt: Bolt) -> None:
    two_slices(bolt)  # Inception is not done
    code, data, _ = bolt.run("slice", "--ready", "s2")
    assert code == 1 and slice_of(bolt, "s2")["ready"] is None
    first = data["findings"][0]
    assert first["code"] == "stage-open:hla" or first["code"].startswith("stage-open:")
    assert "consequence" in first["message"].lower()
    code, data, _ = bolt.run("slice", "--ready", "s2", "--note", "start the spike first")
    assert code == 0 and data["ready"]["gaps"] and data["ready"]["note"] == "start the spike first"
    assert any("start the spike first" in line for line in bolt.log_lines())
    summary = row(bolt, "s2")
    assert summary["status"] == "ready" and summary["open_gaps"] == len(data["ready"]["gaps"])
    assert f"ready, {summary['open_gaps']} open gap(s)" in bolt.run("status", "--format", "text")[2]
    skip_inception(bolt)  # the gaps clear and running it again refreshes them
    assert bolt.run("slice", "--ready", "s2")[0] == 0
    assert slice_of(bolt, "s2")["ready"]["gaps"] == []


def test_a_bad_increment_question_file_is_a_gap(bolt: Bolt) -> None:
    skip_inception(bolt)
    two_slices(bolt)
    bolt.write("docs/slices/s2/inception-questions.md", "## Q1 Scope\nno options here\n")
    code, data, _ = bolt.run("slice", "--ready", "s2")
    assert code == 1 and any(f["code"].startswith("questions-") for f in data["findings"])
    bolt.write("docs/slices/s2/inception-questions.md", QUESTIONS)
    assert bolt.run("slice", "--ready", "s2")[0] == 0


def test_a_bad_decision_status_word_is_a_gap(bolt: Bolt) -> None:
    skip_inception(bolt)
    two_slices(bolt)
    bolt.write(
        "architecture/hla-decisions.md",
        "| ID | Decision | Status |\n| --- | --- | --- |\n| D1 | use a queue | maybe |\n",
    )
    code, data, _ = bolt.run("slice", "--ready", "s2")
    assert code == 1 and [f["code"] for f in data["findings"]] == ["decision-status-unknown:D1"]


def test_traceability_findings_are_attributed_to_the_slice_by_unit_id(bolt: Bolt) -> None:
    skip_inception(bolt)
    two_slices(bolt)  # u1,u2 in s1 and u3 in s2
    bolt.write(
        "docs/inception/units-generation/unit-of-work.md",
        "### U-1 First\n\n### U-3 Third\n\n### U-9 Stray\n",
    )
    code, data, _ = bolt.run("slice", "--ready", "s2")
    assert code == 1
    codes = {f["code"] for f in data["findings"]}
    assert codes == {"traceability-unit-orphan:U-3", "traceability-unit-orphan:U-9"}  # not U-1
    code, data, _ = bolt.run("slice", "--ready", "s2", "--note", "stories follow")
    assert code == 0 and data["informational"] == ["traceability-unit-orphan:U-1"]
    assert slice_of(bolt, "s2")["ready"]["gaps"] == sorted(codes)


def test_a_finding_without_a_unit_id_is_always_a_gap(bolt: Bolt) -> None:
    skip_inception(bolt)
    two_slices(bolt)
    bolt.write("docs/inception/requirements-analysis/requirements.md", "### FR-1 Lonely\n")
    code, data, _ = bolt.run("slice", "--ready", "s1")
    assert code == 1 and [f["code"] for f in data["findings"]] == [
        "traceability-requirement-uncovered:FR-1"
    ]


def test_unit_ids_with_a_hyphen_match_their_inception_form(bolt: Bolt) -> None:
    skip_inception(bolt)
    put(
        bolt,
        {
            "slices": [{"id": "s1"}, {"id": "s2"}],
            "units": [{"id": "u-1", "slice": "s1"}, {"id": "u-2", "slice": "s2"}],
        },
    )
    bolt.write("docs/inception/units-generation/unit-of-work.md", "### U-1 A\n\n### U-2 B\n")
    data = bolt.run("slice", "--ready", "s2")[1]
    assert [f["code"] for f in data["findings"]] == ["traceability-unit-orphan:U-2"]


def test_bugfix_scope_has_nothing_to_trace(tmp_path: Path) -> None:
    done = open_bolt(tmp_path, "--scope", "bugfix")
    p = Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))
    p.write("docs/inception/units-generation/unit-of-work.md", "### U-5 Stray\n")
    assert (
        p.run("slice", "--ready", "s1")[0] == 0
        or "traceability" not in p.run("slice", "--ready", "s1")[2]
    )


def test_slice_help_lists_the_command() -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "slice", "--help"], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0 and "--ready" in done.stdout and "--add" in done.stdout
