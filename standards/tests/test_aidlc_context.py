"""What a Unit or Slice relies on: ids it cites, a baseline taken when work starts, a report.

A change to a shared document is told only to the work that cites what changed, directly or
through the declarations it cites (two hops). Nothing waits for an acknowledgement and the
checkpoint never refuses on it. The documents here are small tables with ids, as Inception
writes them.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from test_aidlc_state import (
    SCRIPT,
    Bolt,
    load_units,
    open_bolt,
    passed_unit_stage,
    skip_inception,
    unit_stage_ready,
    verdict_doc,
)

INCEPTION = "docs/inception/"
UOW = INCEPTION + "units-generation/unit-of-work.md"
REQS = INCEPTION + "requirements-analysis/requirements.md"
CONTRACTS = INCEPTION + "contract-design/contract-summary.md"
DECISIONS = "architecture/hla-decisions.md"
STAGE = "functional-design"


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def table(*rows: str, head: str = "| Id | Name |\n| --- | --- |") -> str:
    return "# Doc\n\n## Digest\n- one\n- two\n\n## Body\n\n" + head + "\n" + "\n".join(rows) + "\n"


def write_docs(p: Bolt, **over: str) -> None:
    """U-1 cites FR-1 and D10; U-2 cites FR-2; u1's own file cites CT-1."""
    docs = {
        UOW: table("| U-1 | First, needs FR-1 under D10 |", "| U-2 | Second, needs FR-2 |"),
        REQS: table("| FR-1 | Pay by card |", "| FR-2 | Send a receipt |"),
        CONTRACTS: table("| CT-1 | Card API |"),
        DECISIONS: table(
            "| D10 | Use queues | accepted |",
            "| D11 | Use retries | accepted |",
            head="| Id | Decision | Status |\n| --- | --- | --- |",
        ),
        "docs/construction/u1/functional-design/functional-spec.md": "# Spec\n\nPays through CT-1.\n",
    }
    for rel, text in {**docs, **over}.items():
        p.write(rel, text)


def start(p: Bolt, *units: str) -> None:
    """Three Units in the Bolt; the given ones have started the first per-Unit stage."""
    skip_inception(p)
    load_units(p, [{"id": "u1"}, {"id": "u2"}, {"id": "u3"}])
    for unit in units:
        code, data, _ = p.run("decide", "--stage", STAGE, "--unit", unit, "--decision", "execute",
                              "--reason", "t")  # fmt: skip
        assert code == 0, data


def report(p: Bolt, unit: str) -> dict[str, Any]:
    code, data, _ = p.run("context", "--unit", unit)
    assert code == 0, data
    assert [r["stage"] for r in data["reports"]] in ([], [STAGE]), data
    found = next(iter(data["reports"]), {})
    return {k: v for k, v in found.items() if k != "stage"}


def changed(rep: dict[str, Any]) -> dict[str, str]:
    return {c["id"]: c["what"] for c in rep.get("changed", [])}


def rewrite(p: Bolt, rel: str, old: str, new: str) -> None:
    text = (p.path / rel).read_text(encoding="utf-8")
    assert old in text
    p.write(rel, text.replace(old, new))


def append(p: Bolt, rel: str, *rows: str) -> None:
    text = (p.path / rel).read_text(encoding="utf-8")
    p.write(rel, text + "\n".join(rows) + "\n")


def record(p: Bolt, unit: str, stage: str = STAGE) -> dict[str, Any]:
    owner = next(u for u in p.state["units"] if u["id"] == unit)
    return owner["stages"][stage]


# --- the baseline ---------------------------------------------------------------


def test_the_baseline_exists_as_soon_as_work_starts_and_holds_no_text(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1")
    base = record(bolt, "u1")["relied_on"]
    assert set(base["ids"]) == {"U-1", "FR-1", "D10", "CT-1"}
    assert base["decisions_upto"] == 11 and set(base) == {
        "at",
        "files",
        "ids",
        "decisions_upto",
        "deps",
    }
    assert all(len(h) == 12 for h in base["ids"].values())
    assert base["files"]["root:docs/presets.md"] is None  # a file that may appear later
    raw = (bolt.path / "state.json").read_text(encoding="utf-8")
    assert "Pay by card" not in raw and "First" not in raw
    assert "relied_on" not in record(bolt, "u2")  # it has not started


def test_a_first_step_takes_the_baseline_of_a_stage_that_needed_no_decision(bolt: Bolt) -> None:
    write_docs(bolt)
    skip_inception(bolt)
    load_units(bolt, [{"id": "u1"}])
    assert bolt.run("step", "--stage", "code-generation", "--unit", "u1", "--to", "asked")[0] == 0
    assert "ids" in record(bolt, "u1", "code-generation")["relied_on"]


# --- what is reported -------------------------------------------------------------


def test_an_addition_that_touches_nothing_cited_reports_nothing(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1", "u2")
    append(bolt, UOW, "| U-9 | Another Unit, needs FR-9 |")
    append(bolt, REQS, "| FR-9 | A brand new need |")
    append(bolt, DECISIONS, "| D12 | Use caching | accepted |")
    assert report(bolt, "u1") == {} and report(bolt, "u2") == {}
    code, data, _ = bolt.run("next", "--unit", "u1")
    assert code == 0 and "context" not in data
    assert bolt.run("status")[1]["context"] == []


def test_a_changed_requirement_is_reported_by_id_to_the_unit_that_cites_it(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1", "u2")
    rewrite(bolt, REQS, "Pay by card", "Pay by card or transfer")
    rep = report(bolt, "u1")
    assert changed(rep) == {"FR-1": "changed"} and "dependencies" not in rep
    assert rep["changed"][0]["file"] == REQS and rep["changed"][0]["line"] > 0
    assert report(bolt, "u2") == {}
    assert bolt.run("next", "--unit", "u1")[1]["context"]["changed"][0]["id"] == "FR-1"


def test_a_changed_contract_cited_by_the_units_own_files_is_reported(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1", "u2")
    rewrite(bolt, CONTRACTS, "Card API", "Card API v2")
    assert changed(report(bolt, "u1")) == {"CT-1": "changed"}
    assert report(bolt, "u2") == {}


def test_a_decision_reached_through_the_units_declaration_is_reported(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1", "u2")
    rewrite(bolt, DECISIONS, "Use queues", "Use streams")
    assert changed(report(bolt, "u1")) == {"D10": "changed"}
    assert report(bolt, "u2") == {}


def test_a_superseded_decision_is_reported_as_superseded_and_a_deleted_one_as_removed(
    bolt: Bolt,
) -> None:
    write_docs(bolt)
    start(bolt, "u1")
    rewrite(bolt, DECISIONS, "Use queues | accepted", "Use queues | superseded")
    assert changed(report(bolt, "u1")) == {"D10": "superseded"}
    rewrite(bolt, REQS, "| FR-1 | Pay by card |\n", "")
    assert changed(report(bolt, "u1")) == {"D10": "superseded", "FR-1": "removed"}


def test_a_new_decision_that_cites_a_relied_on_decision_is_reported(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1", "u2")
    append(bolt, DECISIONS, "| D12 | Amends D10 with streams | accepted |")
    rep = report(bolt, "u1")
    assert [d["id"] for d in rep["new_related"]] == ["D12"] and rep["new_related"][0]["cites"] == [
        "D10"
    ]
    assert "changed" not in rep and "new_constraints" not in rep
    assert report(bolt, "u2") == {}  # D12 cites nothing u2 relies on


def test_a_new_constraint_reaches_every_open_unit_even_without_a_citation(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1", "u2")
    append(bolt, DECISIONS, "| D12 | No card data at rest | constraint |")
    for unit in ("u1", "u2"):
        assert [c["id"] for c in report(bolt, unit)["new_constraints"]] == ["D12"]
    assert [c["id"] for c in bolt.run("next", "--unit", "u2")[1]["context"]["new_constraints"]] == [
        "D12"
    ]


def test_an_input_that_appears_or_vanishes_is_reported(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1")
    presets = bolt.root / "docs" / "presets.md"
    presets.parent.mkdir(parents=True, exist_ok=True)
    presets.write_text("one rule\n", encoding="utf-8")
    assert report(bolt, "u1")["inputs"] == [{"path": "root:docs/presets.md", "what": "appeared"}]


def test_a_changed_dependency_list_is_reported(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1")
    load_units(bolt, [{"id": "u1", "depends_on": ["u2"]}])
    assert report(bolt, "u1") == {"dependencies": True}


def test_work_with_no_baseline_is_reported_as_missing_never_as_fresh(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1")
    assert bolt.run("step", "--stage", STAGE, "--unit", "u1", "--to", "asked")[0] == 0
    state = bolt.state
    del state["units"][0]["stages"][STAGE]["relied_on"]
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert report(bolt, "u1") == {"baseline": "missing"}
    assert bolt.run("status")[1]["context"][0]["baseline"] == "missing"


def test_the_old_flat_baseline_still_loads_and_compares_files_only(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1")
    rewrite(bolt, REQS, "Pay by card", "Pay by cash")
    state = bolt.state
    state["units"][0]["stages"][STAGE]["relied_on"] = {"root:docs/presets.md": "0123456789abcdef"}
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert report(bolt, "u1") == {"inputs": [{"path": "root:docs/presets.md", "what": "vanished"}]}


# --- recording a conclusion, the checkpoint, completed work -------------------------


def test_the_checkpoint_reports_changed_context_and_never_refuses(bolt: Bolt) -> None:
    write_docs(bolt)
    unit_stage_ready(bolt, verdict_doc())
    rewrite(bolt, DECISIONS, "Use queues", "Use streams")
    assert changed(stage_report(bolt, "u1", "code-generation")) == {"D10": "changed"}
    code, data, _ = bolt.run("gate", "--stage", "code-generation", "--unit", "u1", "--approve")
    assert code == 0 and not data.get("findings")
    assert changed(data["context"]) == {"D10": "changed"}
    assert stage_report(bolt, "u1", "code-generation") == {}  # passing it took a fresh baseline


def stage_report(p: Bolt, unit: str, stage: str) -> dict[str, Any]:
    code, data, _ = p.run("context", "--unit", unit, "--stage", stage)
    assert code == 0, data
    found = next(iter(data["reports"]), {})
    return {k: v for k, v in found.items() if k != "stage"}


def test_a_passed_unit_that_relied_on_a_changed_decision_is_listed_as_completed_work(
    bolt: Bolt,
) -> None:
    write_docs(bolt)
    passed_unit_stage(bolt)
    status = bolt.run("status")[1]
    assert status["context"] == [] and status["completed_affected"] == []
    rewrite(bolt, DECISIONS, "Use queues", "Use streams")
    status = bolt.run("status")[1]
    assert status["context"] == []  # nothing open is affected
    row = status["completed_affected"][0]
    assert (row["stage"], row["unit"]) == ("code-generation", "u1")
    assert changed(row) == {"D10": "changed"}
    text = bolt.run("status", "--format", "text")[2]
    assert "Completed work affected, code-generation [u1]: D10 changed" in text


# --- who relies on an id --------------------------------------------------------------


def test_who_relies_on_an_id_names_the_units_and_counts_the_rest(bolt: Bolt) -> None:
    write_docs(bolt)
    skip_inception(bolt)
    spec = bolt.root / "units.json"
    spec.write_text(
        json.dumps(
            {
                "slices": [{"id": "s1"}, {"id": "s2"}],
                "units": [
                    {"id": "u1", "slice": "s1", "owner": "Ana"},
                    {"id": "u2", "slice": "s1", "owner": "Ben"},
                    {"id": "u3", "slice": "s2"},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert bolt.run("units", "--set", str(spec))[0] == 0
    code, data, _ = bolt.run("context", "--id", "D10")
    assert code == 0, data
    assert data["units"] == [{"id": "u1", "slice": "s1", "owner": "Ana"}]
    assert data["slices"] == ["s1"] and data["units_not_relying"] == 2
    assert UOW in data["cited_in"] and data["file"] == DECISIONS and data["line"] > 0
    assert bolt.run("context", "--id", "D99")[0] == 1
    assert bolt.run("context", "--id", "D10", "--unit", "u1")[0] == 2


def test_a_slice_relies_on_what_its_units_rely_on(bolt: Bolt) -> None:
    write_docs(bolt, **{INCEPTION + "delivery-planning/slice-plan.md": table("| SL-1 | First |")})
    skip_inception(bolt)
    spec = bolt.root / "units.json"
    spec.write_text(
        json.dumps(
            {
                "slices": [{"id": "s1"}, {"id": "s2"}],
                "units": [{"id": "u1", "slice": "s1"}, {"id": "u3", "slice": "s2"}],
            }
        ),
        encoding="utf-8",
    )
    assert bolt.run("units", "--set", str(spec))[0] == 0
    for sid in ("s1", "s2"):
        args = (
            "--stage",
            "build-and-test",
            "--slice",
            sid,
            "--decision",
            "execute",
            "--reason",
            "t",
        )
        assert bolt.run("decide", *args)[0] == 0
    rewrite(bolt, DECISIONS, "Use queues", "Use streams")
    code, data, _ = bolt.run("context", "--slice", "s1")
    assert code == 0 and changed(data["reports"][0]) == {"D10": "changed"}
    assert [r["id"] for r in data["relies_on"]] == ["D10"]
    assert bolt.run("context", "--slice", "s2")[1]["reports"] == []
    assert bolt.run("next", "--slice", "s1")[1]["context"]["changed"][0]["id"] == "D10"


def test_context_shows_what_a_unit_relies_on_without_copying_a_document(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1")
    data = bolt.run("context", "--unit", "u1")[1]
    assert [r["id"] for r in data["relies_on"]] == ["CT-1", "D10", "FR-1", "U-1"]
    assert data["relies_on"][2] == {"id": "FR-1", "file": REQS, "line": 11, "gloss": "Pay by card"}
    assert bolt.run("context", "--unit", "nope")[0] == 2
    assert bolt.run("context")[0] == 2


# --- cost ----------------------------------------------------------------------------


def test_the_documents_are_parsed_once_per_command(
    bolt: Bolt, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_docs(bolt)
    start(bolt, "u1", "u2", "u3")
    spec = importlib.util.spec_from_file_location("aidlc_state_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)  # dataclasses look it up here
    cast(Any, spec.loader).exec_module(module)
    refs = module.load_refs_module()
    calls: list[int] = []
    original = refs.Bolt.load

    def counted(self: Any) -> None:
        calls.append(1)
        original(self)

    monkeypatch.setattr(refs.Bolt, "load", counted)
    for command in ("status", "next"):
        calls.clear()
        assert module.main([command, "--bolt", str(bolt.path)]) == 0
        assert len(calls) == 1, command
    capsys.readouterr()
