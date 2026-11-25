"""What a Unit or Slice relies on: the ids it cites, and what those declarations cite.

The documents here are small tables with ids, as Inception writes them. A Unit relies on its
own declaration and what its files cite, then on what those cite, two hops out, limited to the
ids declared in the documents its stages track by id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_aidlc_state import Bolt, load_units, open_bolt, skip_inception

INCEPTION = "docs/inception/"
UOW = INCEPTION + "units-generation/unit-of-work.md"
REQS = INCEPTION + "requirements-analysis/requirements.md"
CONTRACTS = INCEPTION + "contract-design/contract-summary.md"
DECISIONS = "architecture/hla-decisions.md"


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


def start(p: Bolt) -> None:
    """Three Units in the Bolt, with the Inception already out of the way."""
    skip_inception(p)
    load_units(p, [{"id": "u1"}, {"id": "u2"}, {"id": "u3"}])


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
    code, data, _ = bolt.run("context", "--slice", "s1")
    assert code == 0 and [r["id"] for r in data["relies_on"]] == ["D10"]
    assert bolt.run("context", "--slice", "s2")[1]["relies_on"] == []


def test_context_shows_what_a_unit_relies_on_without_copying_a_document(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt)
    data = bolt.run("context", "--unit", "u1")[1]
    assert [r["id"] for r in data["relies_on"]] == ["CT-1", "D10", "FR-1", "U-1"]
    assert data["relies_on"][2] == {"id": "FR-1", "file": REQS, "line": 11, "gloss": "Pay by card"}
    assert bolt.run("context", "--unit", "nope")[0] == 2
    assert bolt.run("context")[0] == 2
