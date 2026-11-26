"""``units --set`` adds and updates Units; it never reloads them. ``units --cancel`` retires one.

The rule behind every test: planning new work must not rewrite the state of work that is
already under way, so what a file does not mention is left exactly as it was.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_aidlc_state import Bolt, open_bolt, skip_inception, skip_unit_stages


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def put(p: Bolt, data: dict[str, Any]) -> tuple[int, dict[str, Any], str]:
    spec = p.root / "units.json"
    spec.write_text(json.dumps(data), encoding="utf-8")
    return p.run("units", "--set", str(spec))


def unit(p: Bolt, uid: str) -> dict[str, Any]:
    return next(u for u in p.state["units"] if u["id"] == uid)


def test_a_new_unit_is_added_and_the_others_are_untouched(bolt: Bolt) -> None:
    assert put(bolt, {"units": [{"id": "u1", "name": "A", "owner": "Ana"}]})[0] == 0
    assert bolt.run("decision-id", "--unit", "u1")[1]["ids"] == ["D1"]
    bolt.run("jira", "--unit", "u1", "--story", "ABC-1")
    before = unit(bolt, "u1")
    code, data, _ = put(bolt, {"units": [{"id": "u2", "name": "B", "owner": "Ben"}]})
    assert code == 0 and data["added"] == ["u2"] and data["units"] == ["u1", "u2"]
    assert unit(bolt, "u1") == before
    assert unit(bolt, "u2")["stages"]["code-generation"]["decision"] == "execute"
    assert bolt.run("decision-id", "--unit", "u1")[1]["ids"] == ["D2"]  # the counter continues


def test_an_existing_unit_changes_only_the_keys_the_file_gives(bolt: Bolt) -> None:
    put(bolt, {"units": [{"id": "u1", "name": "A", "kind": "service", "owner": "Ana"}]})
    bolt.run("jira", "--unit", "u1", "--story", "ABC-1")
    skip_inception(bolt)
    skip_unit_stages(bolt, "u1")
    before = unit(bolt, "u1")
    assert put(bolt, {"units": [{"id": "u1", "name": "Renamed", "repo": None}]})[0] == 0
    after = unit(bolt, "u1")
    assert after["name"] == "Renamed" and after["kind"] == "service"
    assert {k: v for k, v in after.items() if k != "name"} == {
        k: v for k, v in before.items() if k != "name"
    }
    assert after["stages"] == before["stages"] and after["story"] == "ABC-1"


def test_a_file_that_names_no_existing_unit_leaves_them_all(bolt: Bolt) -> None:
    put(bolt, {"units": [{"id": "u1", "owner": "Ana"}, {"id": "u2"}]})
    before = bolt.state["units"]
    assert put(bolt, {"units": [{"id": "u3"}]})[0] == 0
    assert bolt.state["units"][:2] == before


def test_a_different_owner_in_the_file_is_refused_and_points_to_assign(bolt: Bolt) -> None:
    put(bolt, {"units": [{"id": "u1", "owner": "Ana"}, {"id": "u2"}]})
    before = bolt.state
    code, data, _ = put(bolt, {"units": [{"id": "u3"}, {"id": "u1", "owner": "Cleo"}]})
    assert code == 1 and "assign" in data["error"] and "Ana" in data["error"]
    assert bolt.state == before  # nothing of the file was applied, not even the new Unit
    assert put(bolt, {"units": [{"id": "u2", "owner": "Ben"}]})[0] == 1  # nobody -> Ben too
    assert put(bolt, {"units": [{"id": "u1", "owner": " ana "}]})[0] == 0  # the same person
    assert unit(bolt, "u1")["owner"] == "Ana"
    assert bolt.run("assign", "--unit", "u2", "--owner", "Ben")[0] == 0


def test_dependencies_are_checked_over_the_merged_set(bolt: Bolt) -> None:
    put(bolt, {"units": [{"id": "a"}, {"id": "b", "depends_on": ["a"]}]})
    before = bolt.state
    code, data, _ = put(bolt, {"units": [{"id": "a", "depends_on": ["b"]}]})
    assert code == 4 and "a -> b -> a" in data["error"] and bolt.state == before
    code, data, _ = put(bolt, {"units": [{"id": "c", "depends_on": ["a", "b"]}]})
    assert code == 0 and unit(bolt, "c")["depends_on"] == [
        {"unit": "a", "on": "done"},
        {"unit": "b", "on": "done"},
    ]
    assert put(bolt, {"units": [{"id": "d", "depends_on": ["zz"]}]})[0] == 4


def test_a_split_bolt_writes_only_the_state_file_that_changed(tmp_path: Path) -> None:
    done = open_bolt(tmp_path, "--units", "split")
    p = Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))
    put(p, {"units": [{"id": "u1", "owner": "Ana"}, {"id": "u2", "owner": "Ben"}]})
    p.run("decision-id", "--unit", "u1")
    files = {u: p.path / "units" / u / "state.json" for u in ("u1", "u2")}
    before = {u: f.read_bytes() for u, f in files.items()}
    assert put(p, {"units": [{"id": "u3", "owner": "Cleo"}, {"id": "u2", "name": "B"}]})[0] == 0
    assert files["u1"].read_bytes() == before["u1"]  # never rewritten, not even `updated`
    assert files["u2"].read_bytes() == before["u2"]  # its name lives in the shared index
    assert unit(p, "u2")["name"] == "B"
    assert (p.path / "units" / "u3" / "state.json").is_file()
    assert p.run("decision-id", "--unit", "u1")[1]["ids"] == ["D2"]


def test_cancelling_a_unit_of_a_split_bolt_leaves_its_state_file_alone(tmp_path: Path) -> None:
    done = open_bolt(tmp_path, "--units", "split")
    p = Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))
    put(p, {"units": [{"id": "u1", "owner": "Ana"}]})
    p.run("decision-id", "--unit", "u1")
    own = p.path / "units" / "u1" / "state.json"
    before = own.read_bytes()
    assert p.run("units", "--cancel", "u1", "--reason", "gone")[0] == 0
    assert own.read_bytes() == before  # the cancellation is recorded in the shared index
    assert (
        json.loads((p.path / "state.json").read_text())["units"][0]["cancelled"]["reason"] == "gone"
    )
    assert unit(p, "u1")["cancelled"]["reason"] == "gone"


def test_cancel_keeps_the_unit_and_takes_it_out_of_the_work(bolt: Bolt) -> None:
    put(bolt, {"units": [{"id": "u1"}, {"id": "u2", "depends_on": ["u1"]}, {"id": "u3"}]})
    skip_inception(bolt)
    skip_unit_stages(bolt, "u3")
    code, data, _ = bolt.run("units", "--cancel", "u1", "--reason", "too big",
                             "--superseded-by", "u4,u5")  # fmt: skip
    assert code == 2  # u4 and u5 are not Units yet
    put(bolt, {"units": [{"id": "u4"}, {"id": "u5"}]})
    code, data, _ = bolt.run("units", "--cancel", "u1", "--reason", "too big",
                             "--superseded-by", "u4,u5")  # fmt: skip
    assert code == 0 and data["cancelled"]["superseded_by"] == ["u4", "u5"]
    cancelled = unit(bolt, "u1")["cancelled"]
    assert cancelled["reason"] == "too big" and cancelled["at"]
    assert "stages" in unit(bolt, "u1")  # the record stays
    status = bolt.run("status")[1]
    assert [row["id"] for row in status["unit_details"]] == ["u2", "u3", "u4", "u5"]
    assert bolt.run("next", "--unit", "u1")[1]["action"] == "cancelled"
    assert any("cancelled u1: too big" in line for line in bolt.log_lines())
    assert bolt.run("units", "--cancel", "u1", "--reason", "again")[0] == 1
    assert bolt.run("units", "--cancel", "u2")[0] == 2  # a reason is needed


def test_a_cancelled_unit_no_longer_blocks_or_counts(bolt: Bolt) -> None:
    put(bolt, {"units": [{"id": "u1"}, {"id": "u2"}]})
    skip_inception(bolt)
    skip_unit_stages(bolt, "u1")
    total = bolt.run("status")[1]["phases"]["construction"]["total"]
    bolt.run("units", "--cancel", "u2", "--reason", "dropped")
    nxt = bolt.run("next")[1]
    assert nxt["stage"] != "code-generation" or nxt["unit"] != "u2"
    assert all(item["unit"] != "u2" for item in bolt.run("next", "--mine")[1].get("units", []))
    assert bolt.run("status")[1]["phases"]["construction"]["total"] == total - 5  # u2's stages


def test_a_unit_that_depends_on_a_cancelled_unit_shows_a_problem(bolt: Bolt) -> None:
    put(bolt, {"units": [{"id": "u1"}, {"id": "u2", "depends_on": ["u1"]}]})
    bolt.run("units", "--cancel", "u1", "--reason", "gone")
    waits = bolt.run("next", "--unit", "u2")[1]["blocked_by"]
    assert len(waits) == 1 and "cancelled" in waits[0]["reason"]
    assert put(bolt, {"units": [{"id": "u2", "depends_on": []}]})[0] == 0
    assert bolt.run("next", "--unit", "u2")[1]["blocked_by"] == []
