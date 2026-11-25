"""What a Unit relies on, with documents written the way the Inception references prescribe.

The earlier context tests cite requirements and decisions from the Unit's own row, which the
Inception documents never do: there the story map and the stories carry the link to the Unit,
and the Unit's section cites components and contracts only. These tests use that format.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_aidlc_context import (
    REQS as REQS_OLD,
)
from test_aidlc_context import (
    UOW,
    append,
    changed,
    record,
    report,
    rewrite,
    start,
    write_docs,
)
from test_aidlc_state import SCRIPT, Bolt, load_units, open_bolt, passed_unit_stage, skip_inception

REQS = REQS_OLD  # the same file: requirements-analysis/requirements.md
INC = "docs/inception/"
STORIES = INC + "user-stories/stories.md"
STORY_MAP = INC + "units-generation/unit-of-work-story-map.md"
COMPONENTS = INC + "domain-design/components.md"
CONTRACTS = INC + "contract-design/contract-summary.md"
DECISIONS = "architecture/hla-decisions.md"

DOCS = {
    # units-generation.md: `### U-n <name>` per unit; components and contracts, no stories
    UOW: (
        "# Units\n\n## Digest\n- two units\n- one each\n\n"
        "## Units\n\n"
        "### U-1 Billing\nKind service. Holds the invoice component, provides contract 1.\n\n"
        "### U-2 Receipts\nKind service. Holds the receipt component, provides contract 2.\n"
    ),
    # `| Item | Unit |` with the story id in the first cell, the Unit as U-n
    STORY_MAP: (
        "# Story map\n\n## Digest\n- two stories\n- two units\n\n"
        "| Item | Unit |\n| --- | --- |\n| US-1 | U-1 |\n| US-2 | U-2 |\n"
    ),
    # user-stories.md: `### US-n <title>` with Covers (FR-n)
    STORIES: (
        "# Stories\n\n## Digest\n- two stories\n- each covers one requirement\n\n"
        "### US-1 Pay an invoice\nAs a payer I want to pay so that I am done.\n"
        "Covers FR-1. Priority high.\n\n"
        "| AC-1.1 | Given an invoice, when I pay, then it is closed |\n\n"
        "### US-2 Get a receipt\nAs a payer I want a receipt so that I can file it.\n"
        "Covers FR-2. Priority medium.\n\n"
        "| AC-2.1 | Given a payment, when it clears, then a receipt is sent |\n"
    ),
    # requirements-analysis.md: `### FR-n <title>` with a source (`D<n>`)
    REQS: (
        "# Requirements\n\n## Digest\n- two needs\n- two sources\n\n"
        "## Functional requirements\n\n"
        "### FR-1 Pay by card\nSource: D10. The payer pays by card.\n\n"
        "### FR-2 Send a receipt\nSource: D11. A receipt goes out by mail.\n"
    ),
    COMPONENTS: (
        "# Components\n\n## Digest\n- invoice\n- receipt\n\n## Component summary\n\n"
        "| Id | Name |\n| --- | --- |\n| C-1 | Invoice |\n| C-2 | Receipt |\n"
    ),
    CONTRACTS: (
        "# Contracts\n\n## Digest\n- two\n- two more\n\n## Contracts\n\n"
        "| # | Provider Unit | Consumer | Mechanism | Owner |\n| --- | --- | --- | --- | --- |\n"
        "| CT-1 | U-1 | web | REST | Ana |\n| CT-2 | U-2 | web | REST | Ben |\n"
    ),
    DECISIONS: (
        "# Decisions\n\n## Digest\n- two\n- two more\n\n"
        "| Id | Decision | Status |\n| --- | --- | --- |\n"
        "| D10 | Pay through queues | accepted |\n| D11 | Mail the receipts | accepted |\n"
        "| D12 | Unrelated | accepted |\n"
    ),
}


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def inception_bolt(p: Bolt, *units: str) -> None:
    for rel, text in DOCS.items():
        p.write(rel, text)
    start(p, *units)


def test_a_unit_relies_on_its_stories_requirements_and_their_decisions(bolt: Bolt) -> None:
    inception_bolt(bolt, "u1", "u2")
    ids = set(record(bolt, "u1")["relied_on"]["ids"])
    assert {"U-1", "US-1", "FR-1", "D10"} <= ids
    assert not ids & {"US-2", "FR-2", "D11"}


def test_a_changed_story_requirement_or_decision_reaches_only_its_units(bolt: Bolt) -> None:
    inception_bolt(bolt, "u1", "u2")
    rewrite(bolt, STORIES, "so that I am done", "so that I am finished")
    assert changed(report(bolt, "u1")) == {"US-1": "changed"}
    assert report(bolt, "u2") == {}
    rewrite(bolt, REQS, "The payer pays by card.", "The payer pays by card or transfer.")
    assert changed(report(bolt, "u1")) == {"US-1": "changed", "FR-1": "changed"}
    assert report(bolt, "u2") == {}
    rewrite(bolt, DECISIONS, "Pay through queues", "Pay through a broker")
    assert changed(report(bolt, "u1")) == {
        "US-1": "changed",
        "FR-1": "changed",
        "D10": "changed",
    }
    assert report(bolt, "u2") == {}


def test_a_story_assigned_to_another_unit_moves_the_reliance(bolt: Bolt) -> None:
    inception_bolt(bolt, "u1")
    rewrite(bolt, STORY_MAP, "| US-2 | U-2 |", "| US-2 | U-1 |")
    again = bolt.run("context", "--unit", "u1")[1]
    assert {"US-2", "FR-2"} <= {r["id"] for r in again["relies_on"]}


def test_a_decision_added_that_cites_a_story_of_the_unit_is_new_related(bolt: Bolt) -> None:
    inception_bolt(bolt, "u1", "u2")
    append(bolt, DECISIONS, "| D13 | Cap the payment at 10k, see US-1 | accepted |")
    mine = report(bolt, "u1")
    assert [d["id"] for d in mine["new_related"]] == ["D13"]
    assert "new_related" not in report(bolt, "u2")


def test_the_closure_does_not_follow_a_neighbouring_units_section(bolt: Bolt) -> None:
    """A section of another Unit that merely names this Unit is not about this Unit."""
    inception_bolt(bolt, "u1", "u2")
    rewrite(bolt, UOW, "Holds the receipt component", "Waits for U-1. Holds the receipt component")
    ids = set(record(bolt, "u1")["relied_on"]["ids"])
    assert "U-2" not in ids and "FR-2" not in ids


def test_a_started_unit_that_relies_on_nothing_says_so(bolt: Bolt) -> None:
    """Unit ids that do not look like U-n have no declaration to start from."""
    for rel, text in DOCS.items():
        bolt.write(rel, text)
    skip_inception(bolt)
    load_units(bolt, [{"id": "billing"}])
    bolt.run("decide", "--stage", "functional-design", "--unit", "billing", "--decision",
             "execute", "--reason", "t")  # fmt: skip
    line = "billing relies on no recorded requirement or decision; change detection cannot help it"
    data = bolt.run("context", "--unit", "billing")[1]
    assert data["note"] == line
    assert line in bolt.run("status", "--format", "text")[2]
    row = bolt.run("status")[1]["unit_details"][0]
    assert row["context_note"] == line


def test_a_unit_that_relies_on_requirements_but_no_decision_says_so(bolt: Bolt) -> None:
    inception_bolt(bolt, "u1")
    rewrite(bolt, REQS, "Source: D10. ", "Source: the interview. ")
    data = bolt.run("context", "--unit", "u1")[1]
    assert data["note"] == "u1 relies on no recorded decision; change detection cannot help it"


def test_a_unit_with_requirements_and_decisions_gets_no_note(bolt: Bolt) -> None:
    inception_bolt(bolt, "u1")
    assert "note" not in bolt.run("context", "--unit", "u1")[1]
    assert bolt.run("status")[1]["unit_details"][0]["context_note"] is None


def test_an_unstarted_unit_gets_no_note(bolt: Bolt) -> None:
    for rel, text in DOCS.items():
        bolt.write(rel, text)
    start(bolt)
    assert "note" not in bolt.run("context", "--unit", "u3")[1]


# --- the report itself --------------------------------------------------------------------


def started(p: Bolt, *units: str) -> None:
    inception_bolt(p, *units)
    assert set(record(p, units[0])["relied_on"]["ids"])


def test_a_non_utf8_markdown_file_is_skipped_and_named_and_nothing_is_lost(bolt: Bolt) -> None:
    started(bolt, "u1")
    before = dict(record(bolt, "u1")["relied_on"]["ids"])
    (bolt.path / "docs/notes.md").write_bytes(b"caf\xe9 \xff\xfe not utf-8\n")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "context", "--bolt", str(bolt.path), "--unit", "u1"],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert done.returncode == 0 and json.loads(done.stdout)["reports"] == []
    assert "docs/notes.md" in done.stderr
    assert bolt.run("context", "--unit", "u1", "--note", "fine")[0] == 0
    assert record(bolt, "u1")["relied_on"]["ids"] == before


def test_an_unreadable_file_that_held_a_relied_on_id_is_not_called_removed(bolt: Bolt) -> None:
    started(bolt, "u1")
    (bolt.path / REQS).write_bytes(b"\xff\xfe\x00 broken")
    rep = report(bolt, "u1")
    assert "changed" not in rep and rep["unreadable"] == [REQS]


def test_an_index_that_cannot_be_built_reports_unavailable_and_keeps_the_baseline(
    bolt: Bolt,
) -> None:
    started(bolt, "u1")
    before = dict(record(bolt, "u1")["relied_on"]["ids"])
    bolt.write("aidlc-refs.json", "{ not json")
    rep = report(bolt, "u1")
    assert rep == {"index": "unavailable"}  # nothing is removed, nothing is new
    assert bolt.run("context", "--unit", "u1", "--note", "go on")[0] == 0
    assert record(bolt, "u1")["relied_on"]["ids"] == before
    assert bolt.run("step", "--stage", STAGE_NAME, "--unit", "u1", "--to", "produced")[0] == 0
    assert record(bolt, "u1")["relied_on"]["ids"] == before
    bolt.write("aidlc-refs.json", "{}")
    assert report(bolt, "u1") == {}


STAGE_NAME = "functional-design"


def test_step_to_produced_tells_what_changed_before_it_refreshes_the_baseline(bolt: Bolt) -> None:
    started(bolt, "u1")
    rewrite(bolt, REQS, "The payer pays by card.", "The payer pays by card or cash.")
    code, data, _ = bolt.run("step", "--stage", STAGE_NAME, "--unit", "u1", "--to", "produced")
    assert code == 0 and [c["id"] for c in data["context"]["changed"]] == ["FR-1"]
    lines = [x for x in bolt.log_lines() if " | context | " in x]
    assert len(lines) == 1 and "FR-1 changed" in lines[0] and "[u1]" in lines[0]
    assert report(bolt, "u1") == {}  # taken in


def test_a_step_that_changes_nothing_adds_no_context_and_no_log_line(bolt: Bolt) -> None:
    started(bolt, "u1")
    data = bolt.run("step", "--stage", STAGE_NAME, "--unit", "u1", "--to", "produced")[1]
    assert "context" not in data
    assert not [x for x in bolt.log_lines() if " | context | " in x]


def test_a_decision_reserved_early_and_written_late_is_new(bolt: Bolt) -> None:
    for rel, text in DOCS.items():
        bolt.write(rel, text.replace("| D12 | Unrelated | accepted |\n", ""))
    append(bolt, DECISIONS, "| D13 | Retry twice | accepted |")
    start(bolt, "u1")
    assert record(bolt, "u1")["relied_on"]["decisions"] == "10-11,13"
    append(bolt, DECISIONS, "| D12 | Cap FR-1 at one payment | accepted |")
    assert [d["id"] for d in report(bolt, "u1")["new_related"]] == ["D12"]


def test_spacing_and_column_padding_are_not_a_change(bolt: Bolt) -> None:
    write_docs(bolt)
    start(bolt, "u1")
    rewrite(bolt, REQS_OLD, "| FR-1 | Pay by card |", "|   FR-1   |    Pay  by   card |")
    rewrite(
        bolt,
        UOW,
        "| U-1 | First, needs FR-1 under D10 |",
        "| U-1  |  First, needs FR-1 under  D10 |",
    )
    assert report(bolt, "u1") == {}
    rewrite(bolt, REQS_OLD, "Pay  by   card", "Pay by cash")
    assert changed(report(bolt, "u1")) == {"FR-1": "changed"}


def test_an_edit_deep_in_a_long_section_is_seen(bolt: Bolt) -> None:
    long_body = "".join(f"Line {i} of the requirement.\n" for i in range(60))
    for rel, text in DOCS.items():
        bolt.write(rel, text)
    bolt.write(REQS, DOCS[REQS].replace("The payer pays by card.\n", long_body + "Source: D10.\n"))
    start(bolt, "u1")
    rewrite(bolt, REQS, "Line 55 of the requirement.", "Line 55 of the requirement, changed.")
    assert changed(report(bolt, "u1")) == {"FR-1": "changed"}


def test_a_completed_unit_stage_with_no_baseline_is_silent(bolt: Bolt) -> None:
    passed_unit_stage(bolt)
    state = bolt.state
    del state["units"][0]["stages"]["code-generation"]["relied_on"]
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    data = bolt.run("status")[1]
    assert data["completed_affected"] == [] and data["context"] == []


def test_a_hla_or_tdd_change_does_not_flag_a_started_slice(bolt: Bolt) -> None:
    skip_inception(bolt)
    spec = bolt.root / "u.json"
    spec.write_text(json.dumps({"slices": [{"id": "s1"}], "units": [{"id": "u1", "slice": "s1"}]}))
    assert bolt.run("units", "--set", str(spec))[0] == 0
    bolt.write("architecture/hla.md", "# HLA\n\n## Digest\n- a\n- b\n")
    bolt.write("architecture/tdd.md", "# TDD\n\n## Digest\n- a\n- b\n")
    pipe = ("--stage", "deployment-pipeline", "--slice", "s1")
    assert bolt.run("decide", *pipe, "--decision", "execute", "--reason", "t")[0] == 0
    assert bolt.run("step", *pipe, "--to", "asked")[0] == 0
    files = bolt.state["slices"][0]["stages"]["deployment-pipeline"]["relied_on"]["files"]
    assert "architecture/hla.md" not in files and "architecture/tdd.md" not in files
    bolt.write("architecture/hla.md", "# HLA\n\n## Digest\n- a\n- b\n- changed by a contribution\n")
    data = bolt.run("context", "--slice", "s1")[1]
    assert data["reports"] == []
    rows = bolt.run("inputs", "--stage", "deployment-pipeline", "--slice", "s1")[1]["inputs"]
    tracks = {r["path"]: r["track"] for r in rows}
    assert (
        tracks["architecture/hla.md"] == "none" and tracks["architecture/hla-decisions.md"] == "ids"
    )
