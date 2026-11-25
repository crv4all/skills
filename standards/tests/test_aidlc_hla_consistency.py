"""``validate_doc.py`` checks an HLA for contradictions a script can find without judgement.

Decision ids cited but not in the record, a superseded decision still cited, a term or
container with two owners, and an interface party that is no container. Each check stays
silent when the document or the record has nothing to compare, and tolerates the shapes
real documents use (appendices that list history, unit-scoped ids, code fences).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-aidlc-hla" / "scripts" / "validate_doc.py"

CHECKS = {"decision-unknown", "decision-superseded", "owner-duplicate", "interface-party-unknown"}
RECORD = (
    "| Id | Layer | Decision | Reason | Source | Flag | Status |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
    "| D1 | 1 | One | r | A-Q1 | - | accepted |\n"
    "| D2 | 1 | Two | r | A-Q1 | - | superseded |\n"
    "| D3 | 1 | Three | r | A-Q1 | - | |\n"
)
PLAIN_RECORD = "| Id | Decision |\n| --- | --- |\n| D1 | One |\n| D2 | Two |\n"


def document(*sections: tuple[str, str]) -> str:
    head = "# HLA\n\n```yaml\narchitecture_owner: x\n```\n"
    return head + "".join(f"\n## {title}\n\n{body}\n" for title, body in sections)


def run(
    tmp_path: Path, text: str, record: Optional[str] = RECORD
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Return the new findings and the new warnings, by code."""
    path = tmp_path / "hla.md"
    path.write_text(text, encoding="utf-8")
    if record is not None:
        (tmp_path / "hla-decisions.md").write_text(record, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(path), "--kind", "hla"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    data = json.loads(done.stdout)
    found: dict[str, list[dict[str, Any]]] = {}
    warned: dict[str, list[dict[str, Any]]] = {}
    for key, target in (("findings", found), ("warnings", warned)):
        for item in data[key]:
            if item["code"] in CHECKS:
                target.setdefault(item["code"], []).append(item)
    return found, warned


# --- decision-unknown -------------------------------------------------------------


def test_a_cited_decision_that_the_record_declares_is_fine(tmp_path: Path) -> None:
    found, warned = run(tmp_path, document(("Scope", "Follows [D1] and (D3).")))
    assert found == {} and warned == {}


def test_a_cited_decision_missing_from_the_record_is_a_finding(tmp_path: Path) -> None:
    found, _ = run(tmp_path, document(("Scope", "Line one.\nFollows [D1] and D9, again D9.")))
    assert list(found) == ["decision-unknown"]
    assert [f["line"] for f in found["decision-unknown"]] == [10]
    assert "D9" in found["decision-unknown"][0]["message"]


def test_unit_scoped_ids_code_fences_and_work_packages_are_not_citations(tmp_path: Path) -> None:
    body = "See u3:D9 and parent:D8 and WP D7 and ADR-D6 and D-T1.\n\n```\nD5 in code\n```"
    found, warned = run(tmp_path, document(("Scope", body)))
    assert found == {} and warned == {}


def test_an_appendix_may_list_historical_ids(tmp_path: Path) -> None:
    text = document(
        ("Scope", "Follows D1."), ("Appendix: history", "Old D9.\n\n### Sub\n\nOld D8.")
    )
    found, _ = run(tmp_path, text)
    assert found == {}
    found, _ = run(tmp_path, text.replace("Appendix: history", "History"))
    assert [f["code"] for f in found["decision-unknown"]] == ["decision-unknown"] * 2


def test_the_header_and_comments_are_not_searched(tmp_path: Path) -> None:
    text = document(("Scope", "<!-- D9 is only guidance -->\nFollows D1."))
    text = text.replace("architecture_owner: x", "architecture_owner: x\nnote: D9")
    assert run(tmp_path, text) == ({}, {})


def test_without_a_record_nothing_is_checked(tmp_path: Path) -> None:
    assert run(tmp_path, document(("Scope", "Follows D9.")), record=None) == ({}, {})


# --- decision-superseded ----------------------------------------------------------


def test_a_superseded_decision_is_a_warning_not_a_finding(tmp_path: Path) -> None:
    found, warned = run(tmp_path, document(("Scope", "Follows D2.")))
    assert found == {}
    assert list(warned) == ["decision-superseded"]
    assert "D2" in warned["decision-superseded"][0]["message"]


def test_a_record_without_a_status_column_never_warns(tmp_path: Path) -> None:
    assert run(tmp_path, document(("Scope", "Follows D2.")), record=PLAIN_RECORD) == ({}, {})


# --- owner-duplicate --------------------------------------------------------------

TERMS = "| Term | Meaning | Owning context | Source of truth |\n| --- | --- | --- | --- |\n"


def test_a_term_with_two_owners_is_a_finding(tmp_path: Path) -> None:
    table = (
        TERMS + "| Animal | a | Identity | x |\n| Party | p | Party | x |\n"
        "|  animal  | a | Housing | x |\n"
    )
    found, _ = run(tmp_path, document(("Conceptual design", table)))
    assert list(found) == ["owner-duplicate"]
    assert "Identity" in found["owner-duplicate"][0]["message"]
    assert "Housing" in found["owner-duplicate"][0]["message"]


def test_the_same_owner_twice_or_different_terms_are_fine(tmp_path: Path) -> None:
    table = (
        TERMS
        + "| Animal | a | Identity | x |\n| animal | a | IDENTITY | x |\n| Barn | b | H | x |\n"
    )
    assert run(tmp_path, document(("Conceptual design", table))) == ({}, {})


def test_a_container_with_two_owners_is_a_finding(tmp_path: Path) -> None:
    table = "| Container | Owner | Technology |\n| --- | --- | --- |\n| API | Team A | x |\n| api | Team B | x |\n"
    found, _ = run(tmp_path, document(("Proposed architecture", table)))
    assert list(found) == ["owner-duplicate"]


def test_a_container_table_without_an_owner_column_is_skipped(tmp_path: Path) -> None:
    table = "| Container | Responsibility |\n| --- | --- |\n| API | one |\n| API | two |\n"
    assert run(tmp_path, document(("Proposed architecture", table))) == ({}, {})


def test_an_appendix_table_does_not_count(tmp_path: Path) -> None:
    table = TERMS + "| Animal | a | Identity | x |\n"
    old = TERMS + "| Animal | a | Housing | x |\n"
    text = document(("Conceptual design", table), ("Appendix: old", old))
    assert run(tmp_path, text) == ({}, {})


# --- interface-party-unknown -----------------------------------------------------------

CONTAINERS = (
    "| Container | Responsibility |\n| --- | --- |\n| Housing service | h |\n| Breeding app | b |\n"
)
INTERFACES = "| Interface | Producer | Consumer |\n| --- | --- | --- |\n"


def interface(rows: str) -> str:
    return document(
        ("Proposed architecture", CONTAINERS), ("Data and integration", INTERFACES + rows)
    )


def test_parties_that_are_containers_are_fine(tmp_path: Path) -> None:
    rows = "| Commands | Breeding app | housing service |\n| Facts | Housing service | Breeding app<br/>Housing service |\n"
    assert run(tmp_path, interface(rows)) == ({}, {})


def test_an_unknown_party_is_a_warning(tmp_path: Path) -> None:
    _, warned = run(tmp_path, interface("| Commands | Breeding app | Billing |\n"))
    assert list(warned) == ["interface-party-unknown"]
    assert "Billing" in warned["interface-party-unknown"][0]["message"]


def test_without_a_container_table_or_interface_table_nothing_is_checked(tmp_path: Path) -> None:
    rows = "| Commands | Breeding app | Billing |\n"
    text = document(("Data and integration", INTERFACES + rows))
    assert run(tmp_path, text) == ({}, {})
    assert run(tmp_path, document(("Proposed architecture", CONTAINERS))) == ({}, {})


def test_a_table_with_a_consumer_but_no_producer_column_is_skipped(tmp_path: Path) -> None:
    handover = "| Contract | Provider (owner) | Consumer |\n| --- | --- | --- |\n| Pedigree | Data team | P3a |\n"
    text = document(("Proposed architecture", CONTAINERS), ("Data and integration", handover))
    assert run(tmp_path, text) == ({}, {})
