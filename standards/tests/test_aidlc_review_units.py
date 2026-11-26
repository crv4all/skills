"""Units and Slices that are cancelled, missing a Slice or malformed (review fixes, H3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_aidlc_slices_stages import finish, row, two_slices
from test_aidlc_state import Bolt, open_bolt, skip_inception


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def put(p: Bolt, data: Any) -> tuple[int, dict[str, Any], str]:
    spec = p.root / "units.json"
    spec.write_text(json.dumps(data), encoding="utf-8")
    return p.run("units", "--set", str(spec))


# --- all Units cancelled -------------------------------------------------------------


def test_a_bolt_whose_units_are_all_cancelled_can_be_closed(bolt: Bolt) -> None:
    skip_inception(bolt)
    assert put(bolt, {"slices": [{"id": "s1"}], "units": [{"id": "u1", "slice": "s1"}]})[0] == 0
    assert bolt.run("units", "--cancel", "u1", "--reason", "dropped")[0] == 0
    nxt = bolt.run("next")[1]
    assert nxt["stage"] != "build-and-test" and nxt["action"] != "load-units"
    assert row(bolt, "s1")["status"] == "cancelled"
    assert bolt.run("close", "--status", "complete")[0] == 0


def test_a_slice_with_only_cancelled_units_adds_no_work_and_does_not_hold_others(
    bolt: Bolt,
) -> None:
    two_slices(bolt)
    bolt.run("units", "--cancel", "u3", "--reason", "dropped")
    assert row(bolt, "s2")["status"] == "cancelled"
    finish(bolt, "u1", "u2")
    code, data, _ = bolt.run("close", "--status", "complete")
    stages = {(f["stage"], f.get("slice")) for f in data.get("findings", [])}
    assert ("build-and-test", "s2") not in stages and ("build-and-test", "s1") in stages
    assert row(bolt, "s1")["waits"] == [] and code == 1


def test_a_bolt_with_no_units_at_all_still_shows_the_placeholder(bolt: Bolt) -> None:
    skip_inception(bolt)
    code, data, _ = bolt.run("close", "--status", "complete")
    assert code == 1 and any(f["code"] == "units-not-loaded" for f in data["findings"])


# --- a new Unit needs a Slice when the Bolt has Slices -----------------------------------


def test_a_new_unit_without_a_slice_is_refused_when_the_bolt_has_slices(bolt: Bolt) -> None:
    two_slices(bolt)
    before = bolt.state
    code, data, _ = put(bolt, {"units": [{"id": "u9"}]})
    assert code == 1 and "u9" in data["error"] and "s1, s2" in data["error"]
    assert bolt.state["units"] == before["units"]
    assert put(bolt, {"units": [{"id": "u9", "slice": "s2"}]})[0] == 0
    assert put(bolt, {"units": [{"id": "u1"}]})[0] == 0  # an existing Unit keeps its Slice


def test_a_unit_without_a_slice_is_fine_while_the_bolt_has_no_slices(bolt: Bolt) -> None:
    assert put(bolt, {"units": [{"id": "u1"}]})[0] == 0


# --- malformed files fail with the malformed-input exit code ----------------------------


@pytest.mark.parametrize(
    ("data", "needle"),
    [
        ({"units": [{"id": "u1", "slice": ["s1"]}]}, "unit u1 slice must be a string"),
        ({"units": [{"id": "u1", "name": ["x"]}]}, "unit u1 name must be a string"),
        ({"slices": [{"id": "s1", "units": 3}]}, "slice s1 units must be a list"),
        ({"slices": [{"id": "s1", "units": "u1"}]}, "slice s1 units must be a list"),
        ({"slices": [{"id": "s1", "name": ["x"]}]}, "slice s1 name must be a string"),
        ({"slices": [{"id": "s1", "owner": 4}]}, "slice s1 owner must be a string"),
        ({"slices": [{"id": "s1", "depends_on": 4}]}, "slice s1 depends_on"),
    ],
)
def test_malformed_entries_are_refused_without_a_traceback(
    bolt: Bolt, data: dict[str, Any], needle: str
) -> None:
    before = bolt.state
    code, out, text = put(bolt, data)
    assert code == 4 and needle in out["error"], text
    assert "Traceback" not in text and bolt.state["units"] == before["units"]
