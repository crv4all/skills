"""An architecture contribution is a small owned file, checked by ``validate_doc.py``.

``--kind contribution`` reads the file's header against its schema, refuses leftover
placeholders and checks that every decision id it cites is in the record next to hla.md.
The twelve layers of the HLA do not apply to it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HLA_SKILL = REPO_ROOT / "skills" / "processes" / "crv-aidlc-hla"
SCRIPT = HLA_SKILL / "scripts" / "validate_doc.py"

_spec = importlib.util.spec_from_file_location("validate_doc", SCRIPT)
assert _spec is not None and _spec.loader is not None
vd: Any = importlib.util.module_from_spec(_spec)
cast(Any, _spec.loader).exec_module(vd)

HEADER = (
    "concern: security\n"
    'owner: "Ann Owner"\n'
    "status: draft\n"
    "touches:\n"
    '  - "Security and privacy"\n'
    "affects: []\n"
)
RECORD = (
    "| Id | Layer | Decision | Reason | Source | Flag | Status |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
    "| D1 | 1 | One | r | A-Q1 | - | accepted |\n"
    "| D2 | 1 | Two | r | A-Q1 | - | superseded |\n"
)


def titles() -> list[str]:
    text = (HLA_SKILL / "assets" / "contribution-template.md").read_text(encoding="utf-8")
    return [section["title"] for section in vd.Doc(text).sections]


def contribution(
    header: str = HEADER,
    bodies: Optional[dict[str, str]] = None,
    drop: Optional[str] = None,
) -> str:
    parts = ["# Contribution: security", "", f"```yaml\n{header}```", ""]
    for title in titles():
        if title == drop:
            continue
        body = (bodies or {}).get(title, f"Settled content for {title.lower()}, from A-Q1.")
        parts += [f"## {title}", "", body, ""]
    return "\n".join(parts)


def check(
    tmp_path: Path, text: str, name: str = "security", record: Optional[str] = RECORD
) -> tuple[int, dict[str, Any]]:
    folder = tmp_path / "architecture" / "contributions"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    if record is not None:
        (tmp_path / "architecture" / "hla-decisions.md").write_text(record, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(path), "--kind", "contribution"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    data = json.loads(done.stdout) if done.stdout.strip().startswith("{") else {}
    return done.returncode, data


def codes(data: dict[str, Any], key: str = "findings") -> list[str]:
    return [item["code"] for item in data.get(key, [])]


def test_the_template_headings_are_the_agreed_ones() -> None:
    assert titles() == [
        "Question",
        "Findings and evidence",
        "Proposal",
        "Alternatives and trade-offs",
        "Decisions",
        "Open questions for other contributors",
    ]


def test_a_complete_contribution_is_valid(tmp_path: Path) -> None:
    code, data = check(tmp_path, contribution())
    assert code == 0, data["findings"]
    assert data["status"] == "draft"


def test_the_shipped_template_fails_only_on_placeholders(tmp_path: Path) -> None:
    template = (HLA_SKILL / "assets" / "contribution-template.md").read_text(encoding="utf-8")
    code, data = check(tmp_path, template)
    assert code == 1
    assert set(codes(data)) <= {"placeholder", "empty-value", "concern-name"}, data["findings"]
    assert "placeholder" in codes(data)


def test_the_shipped_schema_stays_inside_the_subset() -> None:
    schema = json.loads((HLA_SKILL / "assets" / "contribution-header.schema.json").read_text())
    vd.check_schema(schema)


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("status: draft", "status: finished", ["schema"]),
        ("concern: security", "concern: Security Team", ["schema", "concern-name"]),
        ('owner: "Ann Owner"\n', "", ["schema"]),
        ('  - "Security and privacy"\n', "", ["empty-value"]),
        ("affects: []\n", "affects: []\nextra: 1\n", ["header-unknown-key"]),
    ],
)
def test_header_problems(tmp_path: Path, old: str, new: str, expected: list[str]) -> None:
    code, data = check(tmp_path, contribution(HEADER.replace(old, new)))
    assert code == 1
    assert sorted(set(codes(data))) == sorted(expected), data["findings"]


def test_the_header_may_omit_affects(tmp_path: Path) -> None:
    code, data = check(tmp_path, contribution(HEADER.replace("affects: []\n", "")))
    assert code == 0, data["findings"]


def test_the_concern_must_equal_the_file_name(tmp_path: Path) -> None:
    code, data = check(tmp_path, contribution(), name="networking")
    assert code == 1 and codes(data) == ["concern-name"]


def test_a_missing_section_is_a_finding(tmp_path: Path) -> None:
    code, data = check(tmp_path, contribution(drop="Proposal"))
    assert code == 1 and codes(data) == ["section-missing"]


def test_optional_sections_may_say_not_applicable(tmp_path: Path) -> None:
    bodies = {t: "Not applicable: nothing to add." for t in titles()[3:]}
    code, data = check(tmp_path, contribution(bodies=bodies))
    assert code == 0, data["findings"]
    code, data = check(tmp_path, contribution(bodies={"Question": "Not applicable: none"}))
    assert codes(data) == ["not-applicable-not-allowed"]


def test_a_leftover_placeholder_is_a_finding(tmp_path: Path) -> None:
    code, data = check(tmp_path, contribution(bodies={"Proposal": "Use <the chosen option>."}))
    assert code == 1 and codes(data) == ["placeholder"]


def test_cited_decisions_must_exist_in_the_record(tmp_path: Path) -> None:
    ok = contribution(bodies={"Decisions": "- D1"})
    assert check(tmp_path, ok)[0] == 0
    code, data = check(tmp_path, contribution(bodies={"Decisions": "- D1\n- D9"}))
    assert code == 1 and codes(data) == ["decision-unknown"]
    assert "D9" in data["findings"][0]["message"]


def test_a_superseded_decision_is_a_warning(tmp_path: Path) -> None:
    code, data = check(tmp_path, contribution(bodies={"Decisions": "- D2"}))
    assert code == 0 and codes(data, "warnings") == ["decision-superseded"]


def test_a_unit_scoped_id_and_a_code_fence_are_not_citations(tmp_path: Path) -> None:
    body = "See u3:D9 in the unit.\n\n```\nD8 is an example\n```"
    code, data = check(tmp_path, contribution(bodies={"Findings and evidence": body}))
    assert code == 0, data["findings"]


def test_without_a_record_citations_warn_and_do_not_fail(tmp_path: Path) -> None:
    code, data = check(tmp_path, contribution(bodies={"Decisions": "- D1"}), record=None)
    assert code == 0 and codes(data, "warnings") == ["decision-record-missing"]


def test_the_tdd_copy_is_byte_identical() -> None:
    other = REPO_ROOT / "skills" / "processes" / "crv-aidlc-tdd" / "scripts" / "validate_doc.py"
    assert other.read_bytes() == SCRIPT.read_bytes()
