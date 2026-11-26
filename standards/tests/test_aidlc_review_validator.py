"""Validator fixes from the independent review (``validate_doc.py``, group H4 and item 24)."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_aidlc_contributions import check as check_contribution
from test_aidlc_contributions import codes as contribution_codes
from test_aidlc_contributions import contribution
from test_aidlc_hla_consistency import document, interface, run
from test_aidlc_validate_doc import build, codes, validate

BOLD_RECORD = (
    "| Id | Layer | Decision | Status |\n| --- | --- | --- | --- |\n"
    "| **D1** | 1 | One | accepted |\n| `D2` | 1 | Two | accepted |\n| _D3_ | 1 | Three | accepted |\n"
)


def cites(*ids: str) -> str:
    return document(("Decisions", "Chosen because of " + " and ".join(ids) + "."))


def test_a_bold_or_quoted_id_cell_is_a_declared_decision(tmp_path: Path) -> None:
    found, warned = run(tmp_path, cites("D1", "D2", "D3"), BOLD_RECORD)
    assert found == {} and warned == {}


def test_a_record_with_no_parseable_row_warns_once_and_skips_the_id_checks(
    tmp_path: Path,
) -> None:
    record = "Decisions so far:\n\n- one: pay by card\n- two: use queues\n"
    found, warned = run(tmp_path, cites("D5", "D6", "D7"), record)
    assert found == {}
    assert [w["code"] for w in warned["decision-record-unreadable"]] == [
        "decision-record-unreadable"
    ]


def test_a_record_that_is_missing_is_still_silent(tmp_path: Path) -> None:
    assert run(tmp_path, cites("D5"), None) == ({}, {})


@pytest.mark.parametrize("dropped", ["Alternatives and trade-offs", "Decisions"])
def test_a_contribution_may_leave_out_its_optional_sections(tmp_path: Path, dropped: str) -> None:
    code, data = check_contribution(tmp_path, contribution(drop=dropped))
    assert code == 0, data["findings"]


def test_a_contribution_without_its_open_questions_is_valid(tmp_path: Path) -> None:
    code, data = check_contribution(
        tmp_path, contribution(drop="Open questions for other contributors")
    )
    assert code == 0, data["findings"]


def test_a_contribution_still_needs_its_required_sections(tmp_path: Path) -> None:
    for required in ("Question", "Findings and evidence", "Proposal"):
        code, data = check_contribution(tmp_path, contribution(drop=required))
        assert code == 1 and contribution_codes(data) == ["section-missing"], required


def test_an_hla_still_needs_all_its_sections(tmp_path: Path) -> None:
    text = build().replace("## Conceptual design", "## Conceptual designs")
    code, data = validate(tmp_path, text, "hla")
    assert code == 1 and "section-missing" in codes(data)


@pytest.mark.parametrize("party", ["Housing", "Breeding", "Housing service v2", "app"])
def test_an_interface_party_must_match_a_whole_container_name(tmp_path: Path, party: str) -> None:
    _, warned = run(tmp_path, interface(f"| Commands | Breeding app | {party} |\n"))
    assert [w["code"] for w in warned["interface-party-unknown"]] == ["interface-party-unknown"]


def test_whole_names_match_after_trimming_and_case_folding(tmp_path: Path) -> None:
    rows = "| Commands | `Breeding App` | **housing service** |\n| Facts |  Housing   Service  | BREEDING APP |\n"
    assert run(tmp_path, interface(rows)) == ({}, {})
