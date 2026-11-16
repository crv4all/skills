"""``validate_doc.py`` checks an HLA or TDD against its template, schema and ADR index.

Most cases build a valid document, break one thing, and assert that exactly the
matching finding appears, so each check is shown both failing and passing. The
shipped templates are checked too: they must fail on placeholders and empty
values only, which proves their structure is itself valid.
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
TDD_SKILL = REPO_ROOT / "skills" / "processes" / "crv-aidlc-tdd"
SCRIPT = HLA_SKILL / "scripts" / "validate_doc.py"
TDD_SCRIPT = TDD_SKILL / "scripts" / "validate_doc.py"

_spec = importlib.util.spec_from_file_location("validate_doc", SCRIPT)
assert _spec is not None and _spec.loader is not None
vd: Any = importlib.util.module_from_spec(_spec)
cast(Any, _spec.loader).exec_module(vd)


# --- builders ----------------------------------------------------------------

HLA_HEADER = {
    "architecture_owner": '"Ann Owner"',
    "document_version": '"1.0"',
    "date": '"2026-11-16"',
    "status": "in-review",
    "reviewers": ["Rae Viewer"],
    "signed_off_by": '""',
    "signed_off_on": '""',
    "system": '"Reporting"',
    "domains": "[reporting]",
    "capabilities": ["Export"],
    "review_level": "full",
    "impact_flags": ["new-data-store"],
    "data_classification": "internal",
    "security_consultation_required": "true",
    "solution_type": "brownfield",
    "decision_needed": ["Accept a second store for exports?"],
    "exceptions": {"required": "false"},
    "adr_registry_commit": '"abc1234"',
}

TDD_HEADER = {
    "architecture_owner": '"Ann Owner"',
    "document_version": '"1.0"',
    "date": '"2026-11-16"',
    "status": "draft",
    "reviewers": ["Rae Viewer"],
    "service_name": '"export-service"',
    "hla_link": "hla.md",
    "trigger": ["new-data-store"],
}


def render_header(fields: dict[str, Any]) -> str:
    lines = ["```yaml"]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f'  - "{item}"' for item in value)
        elif isinstance(value, dict):
            lines.append(f"{key}:")
            lines.extend(f"  {sub}: {item}" for sub, item in value.items())
        else:
            lines.append(f"{key}: {value}")
    lines.append("```")
    return "\n".join(lines)


def template_titles(skill: Path, kind: str) -> list[str]:
    text = (skill / "assets" / f"{kind}-template.md").read_text(encoding="utf-8")
    return [section["title"] for section in vd.Doc(text).sections]


def section_body(title: str, ids: str) -> str:
    if title.lower() == "design decisions":
        rows = "".join(
            f"| Speed versus cost {n} | Chose speed because the deadline is fixed | {n} | |\n"
            for n in ids.split()
        )
        return (
            "| Tension | Decision and reason | Id | Signed off by |\n| --- | --- | --- | --- |\n"
            + rows
        )
    if title.lower() == "conceptual design":
        return (
            '```mermaid\nflowchart LR\n  a["Order"] --> b["Invoice"]\n```\n\n'
            "An order produces one invoice; billing owns invoices."
        )
    return f"Settled content for {title.lower()}, from answer A-Q1."


def build(
    kind: str = "hla",
    header: Optional[dict[str, Any]] = None,
    sections: Optional[dict[str, str]] = None,
    order: Optional[list[str]] = None,
    ids: str = "D2 D5",
) -> str:
    skill = HLA_SKILL if kind == "hla" else TDD_SKILL
    fields = dict(HLA_HEADER if kind == "hla" else TDD_HEADER)
    fields.update(header or {})
    titles = order or template_titles(skill, kind)
    parts = [f"# Document for {kind}", "", render_header(fields), ""]
    for title in titles:
        body = (sections or {}).get(title, section_body(title, ids))
        parts += [f"## {title}", "", body, ""]
    return "\n".join(parts)


def validate(
    tmp_path: Path, text: str, kind: str = "hla", *extra: str, name: str = ""
) -> tuple[int, dict[str, Any]]:
    path = tmp_path / (name or f"{kind}.md")
    path.write_text(text, encoding="utf-8")
    script = SCRIPT if kind == "hla" else TDD_SCRIPT
    done = subprocess.run(
        [sys.executable, str(script), "--file", str(path), "--kind", kind, *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )
    data = json.loads(done.stdout) if done.stdout.strip().startswith("{") else {}
    return done.returncode, data


def codes(data: dict[str, Any], key: str = "findings") -> list[str]:
    return [item["code"] for item in data.get(key, [])]


def index_file(tmp_path: Path, commit: str = "abc1234def") -> Path:
    path = tmp_path / "architecture-index.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "registry_commit": commit,
                "adrs": [
                    {"id": "ADR-G001", "status": "Accepted"},
                    {"id": "ADR-G002", "status": "Proposed"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def accepted_hla(tmp_path: Path, status: str = "accepted") -> None:
    signed = {"signed_off_by": '"Rae Viewer"', "signed_off_on": '"2026-11-20"'}
    text = build("hla", header={"status": status, **signed}, ids="D2 D5")
    (tmp_path / "hla.md").write_text(text, encoding="utf-8")


# --- restricted YAML ---------------------------------------------------------


def parse(text: str) -> dict[str, Any]:
    return vd.parse_header(text.splitlines(), 1)


def test_yaml_scalars() -> None:
    data = parse(
        "a: \"x \\\" y\"\nb: 'it''s'\nc: true\nd: False\ne: null\nf: ~\ng: 3\nh: 1.5\n"
        'i: plain words\nj: "has # hash"  # comment\n# full line comment\nk: 2026-11-16\n'
    )
    assert data == {
        "a": 'x " y',
        "b": "it's",
        "c": True,
        "d": False,
        "e": None,
        "f": None,
        "g": 3,
        "h": 1.5,
        "i": "plain words",
        "j": "has # hash",
        "k": "2026-11-16",
    }


def test_yaml_lists_maps_and_empty_values() -> None:
    data = parse(
        'inline: [a, "b, c", 3]\nnone: []\nblock:\n  - one\n  - "two"\nmap:\n  required: true\n'
        "  link_or_reason:\nempty:\n"
    )
    assert data == {
        "inline": ["a", "b, c", 3],
        "none": [],
        "block": ["one", "two"],
        "map": {"required": True, "link_or_reason": None},
        "empty": None,
    }


@pytest.mark.parametrize(
    "text",
    [
        "a: 1\na: 2\n",
        "a:\n\t- x\n",
        "a:\n  b:\n    c: 1\n",
        "a: |\n  text\n",
        'a: "open\n',
        "a: key: value\n",
        "a:\n  - b: c\n",
        "a: {b: c}\n",
        "a: [x, [y]]\n",
        "  a: 1\n",
    ],
    ids=[
        "duplicate",
        "tab",
        "two-levels",
        "block-scalar",
        "unclosed-quote",
        "bare-colon",
        "map-in-list",
        "inline-map",
        "nested-inline",
        "indented-top",
    ],
)
def test_yaml_rejects_what_the_subset_does_not_support(text: str) -> None:
    with pytest.raises(vd.HeaderError):
        parse(text)


# --- schema subset -----------------------------------------------------------


def errors(value: Any, schema: dict[str, Any]) -> list[str]:
    out: list[tuple[str, str]] = []
    vd.validate(value, schema, "$", out)
    return [message for _, message in out]


def test_schema_type_including_type_lists() -> None:
    assert errors("x", {"type": "string"}) == []
    assert errors(3, {"type": "string"})
    assert errors(None, {"type": ["string", "null"]}) == []
    assert errors(True, {"type": "integer"})
    assert errors(2, {"type": "number"}) == []


def test_schema_required_and_properties() -> None:
    schema = {"type": "object", "required": ["a"], "properties": {"b": {"type": "boolean"}}}
    assert errors({"a": 1, "b": True}, schema) == []
    assert errors({"b": True}, schema) == ["required field is missing"]
    assert errors({"a": 1, "b": "no"}, schema)


def test_schema_items_enum_pattern_min_items() -> None:
    schema = {"type": "array", "minItems": 1, "items": {"enum": ["x", "y"]}}
    assert errors(["x"], schema) == []
    assert errors([], schema) == ["needs at least 1 item(s)"]
    assert errors(["z"], schema)
    assert errors("2026-01-01", {"pattern": r"^\d{4}-\d{2}-\d{2}$"}) == []
    assert errors("soon", {"pattern": r"^\d{4}-\d{2}-\d{2}$"})


def test_schema_if_then_on_a_const() -> None:
    schema = {
        "type": "object",
        "if": {"properties": {"status": {"const": "accepted"}}},
        "then": {"required": ["by"]},
    }
    assert errors({"status": "draft"}, schema) == []
    assert errors({"status": "accepted"}, schema) == ["required field is missing"]
    assert errors({"status": "accepted", "by": "Rae"}, schema) == []


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "additionalProperties": False},
        {"type": "object", "if": {"properties": {"a": {"enum": [1]}}}, "then": {}},
        {"type": "object", "if": {"properties": {"a": {"const": 1}}}},
        {"type": "text"},
    ],
    ids=["unsupported-keyword", "if-without-const", "if-without-then", "bad-type"],
)
def test_schema_outside_the_subset_is_refused(schema: dict[str, Any]) -> None:
    with pytest.raises(vd.Fail) as caught:
        vd.check_schema(schema)
    assert caught.value.code == 4


def test_shipped_schemas_stay_inside_the_subset() -> None:
    for path in (
        HLA_SKILL / "assets" / "hla-header.schema.json",
        TDD_SKILL / "assets" / "tdd-header.schema.json",
    ):
        vd.check_schema(json.loads(path.read_text(encoding="utf-8")))


# --- whole documents ---------------------------------------------------------


def test_a_complete_hla_is_valid(tmp_path: Path) -> None:
    code, data = validate(tmp_path, build(), "hla", "--adr-index", str(index_file(tmp_path)))
    assert code == 0, data["findings"]
    assert data["decisions"] == ["D2", "D5"]


def test_a_complete_tdd_against_an_accepted_hla_is_valid(tmp_path: Path) -> None:
    accepted_hla(tmp_path)
    code, data = validate(tmp_path, build("tdd", ids="D6 D7"), "tdd")
    assert code == 0, data["findings"]


def test_tdd_is_refused_when_the_hla_is_not_accepted(tmp_path: Path) -> None:
    accepted_hla(tmp_path, status="in-review")
    code, data = validate(tmp_path, build("tdd", ids="D6"), "tdd")
    assert code == 1 and codes(data) == ["hla-not-accepted"]


def test_tdd_with_an_unresolved_hla_link(tmp_path: Path) -> None:
    code, data = validate(tmp_path, build("tdd", ids="D6"), "tdd")
    assert code == 1 and codes(data) == ["hla-link-unresolved"]


def test_tdd_decision_ids_must_come_after_the_hla_record(tmp_path: Path) -> None:
    accepted_hla(tmp_path)
    (tmp_path / "hla-decisions.md").write_text("| D9 | 4 | x | y | A-Q1 | - |\n", "utf-8")
    code, data = validate(tmp_path, build("tdd", ids="D8 D10"), "tdd")
    assert code == 1 and codes(data) == ["decision-not-new"]


@pytest.mark.parametrize(("skill", "kind"), [(HLA_SKILL, "hla"), (TDD_SKILL, "tdd")])
def test_shipped_templates_fail_only_on_placeholders_and_empty_values(
    tmp_path: Path, skill: Path, kind: str
) -> None:
    template = (skill / "assets" / f"{kind}-template.md").read_text(encoding="utf-8")
    code, data = validate(tmp_path, template, kind)
    assert code == 1
    assert set(codes(data)) <= {"placeholder", "empty-value"}, data["findings"]
    assert "placeholder" in codes(data)


# --- header ------------------------------------------------------------------


def test_header_missing(tmp_path: Path) -> None:
    text = build().replace("```yaml", "```text", 1)
    assert "header-missing" in codes(validate(tmp_path, text)[1])


def test_header_malformed(tmp_path: Path) -> None:
    text = build(header={"system": "Reporting: export"})
    assert codes(validate(tmp_path, text)[1]) == ["header-malformed"]


def test_header_unknown_key(tmp_path: Path) -> None:
    assert codes(validate(tmp_path, build(header={"colour": "blue"}))[1]) == ["header-unknown-key"]


def test_header_schema_violation(tmp_path: Path) -> None:
    assert codes(validate(tmp_path, build(header={"review_level": "light"}))[1]) == ["schema"]


def test_header_unquoted_version_is_a_schema_finding(tmp_path: Path) -> None:
    data = validate(tmp_path, build(header={"document_version": "1.0"}))[1]
    assert codes(data) == ["schema"] and "quote it" in data["findings"][0]["message"]


def test_header_required_value_left_empty(tmp_path: Path) -> None:
    assert codes(validate(tmp_path, build(header={"system": '""'}))[1]) == ["empty-value"]


def test_header_placeholder(tmp_path: Path) -> None:
    text = build(header={"security_consultation_required": "<true-or-false>"})
    assert codes(validate(tmp_path, text)[1]) == ["placeholder"]


def test_accepted_needs_a_signature(tmp_path: Path) -> None:
    assert set(codes(validate(tmp_path, build(header={"status": "accepted"}))[1])) == {
        "empty-value"
    }
    signed = {"status": "accepted", "signed_off_by": '"Rae"', "signed_off_on": '"2026-11-20"'}
    assert validate(tmp_path, build(header=signed))[0] == 0


def test_exception_needs_a_reason(tmp_path: Path) -> None:
    text = build(header={"exceptions": {"required": "true"}})
    assert codes(validate(tmp_path, text)[1]) == ["schema"]
    text = build(
        header={"exceptions": {"required": "true", "link_or_reason": '"ADR-G001 departure"'}}
    )
    assert validate(tmp_path, text)[0] == 0


def test_impact_flag_none_stands_alone(tmp_path: Path) -> None:
    text = build(header={"impact_flags": ["none", "personal-data"]})
    assert codes(validate(tmp_path, text)[1]) == ["impact-flags"]


# --- sections ----------------------------------------------------------------


def test_section_missing(tmp_path: Path) -> None:
    titles = [t for t in template_titles(HLA_SKILL, "hla") if t != "Scope"]
    assert codes(validate(tmp_path, build(order=titles))[1]) == ["section-missing"]


def test_section_out_of_order(tmp_path: Path) -> None:
    titles = template_titles(HLA_SKILL, "hla")
    titles[1], titles[2] = titles[2], titles[1]
    assert "section-order" in codes(validate(tmp_path, build(order=titles))[1])


def test_section_empty(tmp_path: Path) -> None:
    text = build(sections={"Scope": "<!-- guidance only -->"})
    assert codes(validate(tmp_path, text)[1]) == ["section-empty"]


def test_not_applicable_allowed_only_where_optional(tmp_path: Path) -> None:
    ok = build(sections={"Developer experience": "Not applicable: no code is written."})
    assert validate(tmp_path, ok)[0] == 0
    bad = build(sections={"Scope": "Not applicable: obvious."})
    assert codes(validate(tmp_path, bad)[1]) == ["not-applicable-not-allowed"]
    bare = build(sections={"Developer experience": "Not applicable:"})
    assert codes(validate(tmp_path, bare)[1]) == ["not-applicable-no-reason"]


def test_modernization_cannot_be_skipped_for_a_modernization(tmp_path: Path) -> None:
    text = build(
        header={"solution_type": "modernization"},
        sections={"Modernization plan": "Not applicable: nothing replaced."},
    )
    assert codes(validate(tmp_path, text)[1]) == ["modernization-required"]


def test_extra_section_is_only_a_warning(tmp_path: Path) -> None:
    titles = [*template_titles(HLA_SKILL, "hla"), "Glossary"]
    code, data = validate(tmp_path, build(order=titles))
    assert code == 0 and "section-extra" in codes(data, "warnings")


# --- placeholders ------------------------------------------------------------


@pytest.mark.parametrize("marker", ["<owner name>", "TODO", "TBD", "[ASK USER]"])
def test_placeholder_in_text(tmp_path: Path, marker: str) -> None:
    text = build(sections={"Scope": f"In scope: export. Owner: {marker}."})
    assert codes(validate(tmp_path, text)[1]) == ["placeholder"]


def test_markup_that_is_not_a_placeholder(tmp_path: Path) -> None:
    body = "In scope:<br/>export<br>import. See <https://example.org>. <!-- <hidden> TODO -->"
    code, data = validate(tmp_path, build(sections={"Scope": body}))
    assert code == 0, data["findings"]


# --- decisions ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("ids", "expected"),
    [("D2 D2", "decision-duplicate"), ("D5 D2", "decision-order"), ("D2 X", "decision-no-id")],
)
def test_decision_ids(tmp_path: Path, ids: str, expected: str) -> None:
    assert codes(validate(tmp_path, build(ids=ids))[1]) == [expected]


def test_decision_table_without_an_id_column(tmp_path: Path) -> None:
    table = "| Tension | Decision |\n| --- | --- |\n| a versus b | b |"
    assert codes(validate(tmp_path, build(sections={"Design decisions": table}))[1]) == [
        "decision-table"
    ]


# --- ADRs --------------------------------------------------------------------


def test_adr_ids_are_checked_against_the_index(tmp_path: Path) -> None:
    index = str(index_file(tmp_path))
    ok = build(sections={"Scope": "Follows ADR-G001."})
    assert validate(tmp_path, ok, "hla", "--adr-index", index)[0] == 0
    unknown = build(sections={"Scope": "Follows ADR-G404."})
    assert codes(validate(tmp_path, unknown, "hla", "--adr-index", index)[1]) == ["adr-unknown"]


def test_non_accepted_adr_is_a_warning(tmp_path: Path) -> None:
    text = build(sections={"Scope": "Uses ADR-G002."})
    code, data = validate(tmp_path, text, "hla", "--adr-index", str(index_file(tmp_path)))
    assert code == 0 and codes(data, "warnings").count("adr-not-accepted") == 1


def test_adrs_without_an_index_warn(tmp_path: Path) -> None:
    code, data = validate(tmp_path, build(sections={"Scope": "Uses ADR-G001."}))
    assert code == 0 and "adr-unchecked" in codes(data, "warnings")


def test_stale_index_commit_warns(tmp_path: Path) -> None:
    text = build(sections={"Scope": "Uses ADR-G001."})
    index = str(index_file(tmp_path, commit="9999999"))
    code, data = validate(tmp_path, text, "hla", "--adr-index", index)
    assert code == 0 and "adr-commit-mismatch" in codes(data, "warnings")


# --- diagrams ----------------------------------------------------------------


def test_diagram_followed_by_text_passes(tmp_path: Path) -> None:
    assert validate(tmp_path, build())[0] == 0


def test_diagram_empty(tmp_path: Path) -> None:
    body = "```mermaid\n\n```\n\nNothing drawn."
    assert codes(validate(tmp_path, build(sections={"Conceptual design": body}))[1]) == [
        "diagram-empty"
    ]


def test_diagram_without_text(tmp_path: Path) -> None:
    body = "```mermaid\nflowchart LR\n  a --> b\n```"
    assert codes(validate(tmp_path, build(sections={"Conceptual design": body}))[1]) == [
        "diagram-no-text"
    ]


def test_unclosed_fence(tmp_path: Path) -> None:
    text = build() + "\n```mermaid\nflowchart LR\n"
    assert "fence-unclosed" in codes(validate(tmp_path, text)[1])


# --- command line ------------------------------------------------------------


def test_missing_document_exits_3(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(tmp_path / "nope.md"), "--kind", "hla"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 3


def test_broken_index_exits_4(tmp_path: Path) -> None:
    bad = tmp_path / "index.json"
    bad.write_text("{not json", encoding="utf-8")
    assert validate(tmp_path, build(), "hla", "--adr-index", str(bad))[0] == 4


def test_kind_without_its_template_exits_3(tmp_path: Path) -> None:
    """The TDD skill ships no HLA template, so it cannot validate an HLA."""
    path = tmp_path / "hla.md"
    path.write_text(build(), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(TDD_SCRIPT), "--file", str(path), "--kind", "hla"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 3


def test_unknown_kind_exits_2(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", "x.md", "--kind", "adr"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 2


# --- parent paddock citations ------------------------------------------------


def child_paddock(tmp_path: Path, parent: bool = True, record: bool = True) -> str:
    """A child paddock under ``tmp_path``; returns the HLA's name relative to it."""
    child = tmp_path / "paddocks" / "2026-01-06-phase"
    (child / "architecture").mkdir(parents=True)
    state: dict[str, Any] = {"schema": 1, "id": "2026-01-06-phase"}
    if parent:
        state["parent"] = {"id": "2026-01-05-frame", "path": "paddocks/2026-01-05-frame"}
    (child / "state.json").write_text(json.dumps(state), encoding="utf-8")
    frame = tmp_path / "paddocks" / "2026-01-05-frame" / "architecture"
    frame.mkdir(parents=True)
    if record:
        (frame / "hla-decisions.md").write_text(
            "## Digest\n- two decisions\n\n| Id | Layer | Decision | Reason | Source | Flag |\n"
            "| --- | --- | --- | --- | --- | --- |\n| D1 | 1 | a | b | A-Q1 | - |\n"
            "| D3 | 4 | c | d | A-Q2 | - |\n",
            encoding="utf-8",
        )
    return "paddocks/2026-01-06-phase/architecture/hla.md"


def citing(*ids: str) -> str:
    cited = ", ".join(f"parent:{i}" for i in ids)
    return build(sections={"Scope": f"Phase one only, as the frame settles ({cited})."})


def test_a_known_parent_decision_is_accepted(tmp_path: Path) -> None:
    name = child_paddock(tmp_path)
    code, data = validate(tmp_path, citing("D1", "D3"), "hla", name=name)
    assert code == 0, data["findings"]
    assert data["parent_decisions"] == ["parent:D1", "parent:D3"]
    assert data["decisions"] == ["D2", "D5"]


def test_an_unknown_parent_decision_is_a_finding(tmp_path: Path) -> None:
    name = child_paddock(tmp_path)
    code, data = validate(tmp_path, citing("D2"), "hla", name=name)
    assert code == 1 and codes(data) == ["parent-decision-unknown"]


def test_parent_citations_without_a_parent_are_a_finding(tmp_path: Path) -> None:
    name = child_paddock(tmp_path, parent=False)
    code, data = validate(tmp_path, citing("D1"), "hla", name=name)
    assert code == 1 and codes(data) == ["parent-decision-no-parent"]


def test_a_missing_parent_record_is_a_finding(tmp_path: Path) -> None:
    name = child_paddock(tmp_path, record=False)
    code, data = validate(tmp_path, citing("D1"), "hla", name=name)
    assert code == 1 and codes(data) == ["parent-decision-unresolved"]


def test_parent_citations_outside_a_paddock_only_warn(tmp_path: Path) -> None:
    code, data = validate(tmp_path, citing("D1"), "hla")
    assert code == 0 and codes(data, "warnings") == ["parent-decision-unchecked"]


def test_parent_ids_do_not_raise_the_floor_for_a_tdd(tmp_path: Path) -> None:
    accepted_hla(tmp_path)
    (tmp_path / "hla-decisions.md").write_text(
        "| D5 | 4 | x | y | parent:D40 | - |\n", encoding="utf-8"
    )
    code, data = validate(tmp_path, build("tdd", ids="D6 D7"), "tdd")
    assert code == 0, data["findings"]
