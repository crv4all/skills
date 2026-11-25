#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Check a high-level architecture (HLA), technical design (TDD) or architecture contribution.

Reviewers read these documents to make decisions, and later stages read them to
build. A missing section, a header field nobody filled in, an ADR id that does
not exist or a TDD written against an HLA nobody accepted all look fine to a
reader skimming the page; each one is a mechanical fact a script can check for
free. Judgement about the design stays with people.

The header is a fenced ``yaml`` block in a restricted subset (scalars, lists of
scalars, one level of nested maps) read by a small parser here, and validated
against the kind's JSON schema using a subset of JSON Schema.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, NoReturn, Optional

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EPILOG = """examples:
  python3 validate_doc.py --file architecture/hla.md --kind hla \\
      --adr-index ../../architecture-index.json
  python3 validate_doc.py --file architecture/tdd.md --kind tdd
  python3 validate_doc.py --file architecture/contributions/security.md --kind contribution

checks (each failure is a finding, exit 1):
  header      first ```yaml block parses and matches assets/<kind>-header.schema.json;
              placeholder and empty values are reported as such
  sections    every ## heading of assets/<kind>-template.md is present, in order and
              not empty; "Not applicable: <reason>" only where the template says Optional
  placeholders  no <...> markers, TODO, TBD or FIXME outside HTML comments
  decisions   ids in the Design decisions table are unique and ascending; a TDD's
              ids come after every id in the HLA and its decision record
  adrs        cited ADR ids exist in --adr-index (non-accepted status is a warning)
  diagrams    every mermaid fence is non-empty and followed by text
  consistency (hla) every cited D<n> is declared in hla-decisions.md next to the document
              (decision-unknown; a superseded one is a warning); no term or container has two
              owners; producers and consumers of interface tables are containers (warning).
              Appendices, code fences and unit-scoped ids (u3:D2) are ignored
  hla link    (tdd) hla_link resolves to a document whose header status is accepted
  contribution  (contribution) the header concern equals the file name, and every D<n> cited
              exists in the decision record next to hla.md (decision-unknown); the twelve
              layers do not apply

exit codes:
  0  valid (warnings allowed)
  1  findings
  2  usage error
  3  missing input: the document, template, schema or ADR index does not exist
  4  malformed input: not UTF-8, or the template, schema or index cannot be used
  5  internal error
"""

LOG = logging.getLogger("validate_doc")
ASSETS = Path(__file__).resolve().parent.parent / "assets"

PLACEHOLDER = re.compile(
    r"(?<!<)<(?!/?(?:br|sub|sup|b|i|em|strong|details|summary|kbd|code|p|a|img|span|div"
    r"|ul|ol|li|u|s|hr|table|tr|td|th)\b|https?://|mailto:)[A-Za-z][^<>\n]{0,100}>(?!>)"
    r"|\b(?:TODO|TBD|FIXME)\b|\[ASK USER\]"
)
ADR_ID = re.compile(r"\bADR-[A-Z]*\d+\b")
DECISION_ID = re.compile(r"\bD(\d+)\b")
RECORD_ROW_ID = re.compile(r"^\s*\|\s*[*_`]*D(\d+)[*_`]*\s*\|", re.MULTILINE)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([\w-]*)")
H2 = re.compile(r"^##\s+(.+?)\s*#*\s*$")
NOT_APPLICABLE = re.compile(r"^Not applicable:(.*)$", re.DOTALL)
OPTIONAL_MARK = re.compile(r"^\s*<!--\s*Optional\b", re.IGNORECASE)
CITED_DECISION = re.compile(r"(?<![\w:-])(?<!WP )D(\d+)\b")
RECORDS = ("hla-decisions.md", "tdd-decisions.md")
DECISIONS_SECTION = "design decisions"
MODERNIZATION_SECTION = "modernization plan"


class Fail(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def die(code: int, message: str) -> NoReturn:
    raise Fail(code, message)


# --- restricted YAML ---------------------------------------------------------


class HeaderError(Exception):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(message)
        self.line = line
        self.message = message


KEY_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z_][\w-]*):(?:\s+(?P<value>.*?))?\s*$")
ITEM_LINE = re.compile(r"^(?P<indent> *)-(?:\s+(?P<value>.*?))?\s*$")
INT = re.compile(r"^[-+]?\d+$")
FLOAT = re.compile(r"^[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?$")


def strip_comment(text: str) -> str:
    quote = ""
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or text[index - 1] in " \t"):
            return text[:index]
    return text


def split_inline(text: str, line: int) -> list[str]:
    parts: list[str] = []
    current = ""
    quote = ""
    for char in text:
        if quote:
            current += char
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            current += char
        elif char == ",":
            parts.append(current.strip())
            current = ""
        elif char in "[]{}":
            raise HeaderError(line, "nested lists and maps inside [...] are not supported")
        else:
            current += char
    if quote:
        raise HeaderError(line, "unclosed quote inside [...]")
    if current.strip() or parts:
        parts.append(current.strip())
    return parts


def parse_scalar(text: str, line: int, inline: bool = True) -> Any:
    text = text.strip()
    if text.startswith('"'):
        if len(text) < 2 or not text.endswith('"'):
            raise HeaderError(line, f"unclosed double quote: {text}")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise HeaderError(line, f"bad double-quoted string: {exc.msg}") from None
    if text.startswith("'"):
        if len(text) < 2 or not text.endswith("'"):
            raise HeaderError(line, f"unclosed single quote: {text}")
        return text[1:-1].replace("''", "'")
    if text.startswith("["):
        if not inline:
            raise HeaderError(line, "a list item cannot itself be a list")
        if not text.endswith("]"):
            raise HeaderError(line, f"unclosed '[': {text}")
        return [parse_scalar(part, line, inline=False) for part in split_inline(text[1:-1], line)]
    if text[:1] in {"{", "|", ">", "&", "*", "!", "%", "@", "`"}:
        raise HeaderError(line, f"'{text[0]}' starts a YAML feature this header does not support")
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "~"}:
        return None
    if INT.match(text):
        return int(text)
    if FLOAT.match(text):
        return float(text)
    if ": " in text or text.endswith(":"):
        raise HeaderError(line, f"quote values that contain ': ' -> {text}")
    return text


def parse_header(lines: list[str], first_line: int) -> dict[str, Any]:
    """Parse the restricted YAML subset; ``first_line`` is the 1-based line of ``lines[0]``."""
    result: dict[str, Any] = {}
    cleaned = [strip_comment(raw).rstrip() for raw in lines]
    for index, raw in enumerate(lines):
        lead = raw[: len(raw) - len(raw.lstrip())]
        if "\t" in lead:
            raise HeaderError(first_line + index, "tabs are not allowed for indentation")
    index = 0
    while index < len(cleaned):
        text = cleaned[index]
        number = first_line + index
        if not text.strip():
            index += 1
            continue
        match = KEY_LINE.match(text)
        if not match or match.group("indent"):
            raise HeaderError(number, f"expected a top-level 'key: value', got: {text.strip()}")
        key = match.group("key")
        if key in result:
            raise HeaderError(number, f"duplicate key '{key}'")
        index += 1
        if match.group("value"):
            result[key] = parse_scalar(match.group("value"), number)
            continue
        children: list[tuple[int, str]] = []
        while index < len(cleaned):
            child = cleaned[index]
            if child.strip():
                if not child.startswith(" "):
                    break
                children.append((first_line + index, child))
            index += 1
        result[key] = parse_block(key, children, number)
    return result


def parse_block(key: str, children: list[tuple[int, str]], number: int) -> Any:
    if not children:
        return None
    indent = len(children[0][1]) - len(children[0][1].lstrip(" "))
    for line, child in children:
        if len(child) - len(child.lstrip(" ")) != indent:
            raise HeaderError(line, f"'{key}': only one level of nesting is supported")
    if children[0][1].lstrip().startswith("-"):
        items: list[Any] = []
        for line, child in children:
            match = ITEM_LINE.match(child)
            if not match or not match.group("value"):
                raise HeaderError(line, f"'{key}': expected '- value' list items")
            items.append(parse_scalar(match.group("value"), line, inline=False))
        return items
    mapping: dict[str, Any] = {}
    for line, child in children:
        match = KEY_LINE.match(child)
        if not match:
            raise HeaderError(line, f"'{key}': expected 'key: value' lines")
        sub = match.group("key")
        if sub in mapping:
            raise HeaderError(line, f"'{key}': duplicate key '{sub}'")
        value = match.group("value")
        mapping[sub] = parse_scalar(value, line) if value else None
    return mapping


# --- JSON Schema subset ------------------------------------------------------

KEYWORDS = {"type", "required", "properties", "items", "enum", "pattern", "minItems", "if", "then"}
KEYWORDS_IN_IF = {"properties", "required"}
ANNOTATIONS = {"$schema", "$id", "$comment", "title", "description", "examples", "default"}
TYPES = {"string", "integer", "number", "boolean", "array", "object", "null"}


def check_schema(schema: Any, where: str = "#", in_if: bool = False) -> None:
    """Refuse a schema that uses anything this subset does not implement."""
    if not isinstance(schema, dict):
        die(EXIT_MALFORMED, f"schema {where}: expected an object")
    for key, value in schema.items():
        if key in ANNOTATIONS:
            continue
        if in_if:
            if key not in KEYWORDS_IN_IF:
                die(EXIT_MALFORMED, f"schema {where}: 'if' supports only properties with const")
            if key == "properties":
                for name, sub in value.items():
                    if not isinstance(sub, dict) or set(sub) != {"const"}:
                        die(EXIT_MALFORMED, f"schema {where}/{name}: 'if' needs {{const: ...}}")
            continue
        if key not in KEYWORDS:
            die(EXIT_MALFORMED, f"schema {where}: unsupported keyword '{key}'")
        if key == "type":
            names = [value] if isinstance(value, str) else value
            if not isinstance(names, list) or not set(names) <= TYPES:
                die(EXIT_MALFORMED, f"schema {where}: bad type {value!r}")
        elif key == "properties":
            for name, sub in value.items():
                check_schema(sub, f"{where}/properties/{name}")
        elif key in {"items", "then"}:
            check_schema(value, f"{where}/{key}")
        elif key == "if":
            check_schema(value, f"{where}/if", in_if=True)
            if "then" not in schema:
                die(EXIT_MALFORMED, f"schema {where}: 'if' without 'then'")


def type_ok(value: Any, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    return isinstance(value, dict)


def describe(value: Any) -> str:
    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return f"the number {value} (quote it to make it a string)"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a map"
    return f"'{value}'"


def validate(value: Any, schema: dict[str, Any], path: str, out: list[tuple[str, str]]) -> None:
    kind = schema.get("type")
    if kind is not None:
        names = [kind] if isinstance(kind, str) else list(kind)
        if not any(type_ok(value, name) for name in names):
            out.append((path, f"expected {' or '.join(names)}, got {describe(value)}"))
            return
    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(str(item) for item in schema["enum"])
        out.append((path, f"{describe(value)} is not one of: {allowed}"))
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        out.append((path, f"{describe(value)} does not match {schema['pattern']}"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append((path, f"needs at least {schema['minItems']} item(s)"))
        if "items" in schema:
            for index, item in enumerate(value):
                validate(item, schema["items"], f"{path}[{index}]", out)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                out.append((f"{path}.{key}", "required field is missing"))
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                validate(value[key], sub, f"{path}.{key}", out)
        condition = schema.get("if")
        if condition is not None and condition_holds(value, condition):
            validate(value, schema["then"], path, out)


def condition_holds(value: dict[str, Any], condition: dict[str, Any]) -> bool:
    for key in condition.get("required", []):
        if key not in value:
            return False
    for key, sub in condition.get("properties", {}).items():
        if key in value and value[key] != sub["const"]:
            return False
        if key not in value:
            return False
    return True


# --- document model ----------------------------------------------------------


def strip_comments(text: str) -> str:
    """Blank out HTML comments, keeping every newline so line numbers hold."""
    return re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


BLOCK = re.compile(r"^<!-- aidlc-refs:begin.*?^<!-- aidlc-refs:end -->[ \t]*$", re.M | re.S)
TOOL_COMMENT = re.compile(r"<!--\s*aidlc-(?:refs|lines):.*?-->", re.S)


def strip_block(text: str) -> str:
    """Blank the block aidlc_refs.py generates (it is not document content), keeping lines."""
    return BLOCK.sub(lambda m: re.sub(r"[^\n]", "", m.group(0)), text)


class Doc:
    def __init__(self, raw: str) -> None:
        raw = strip_block(raw)
        self.raw_lines = raw.splitlines()
        self.lines = strip_comments(raw).splitlines()
        self.fences: list[dict[str, Any]] = []
        self.in_fence: set[int] = set()
        open_fence: Optional[dict[str, Any]] = None
        for index, line in enumerate(self.lines):
            match = FENCE.match(line)
            if open_fence is None:
                if match:
                    open_fence = {"start": index, "end": None, "lang": match.group(2).lower()}
                    open_fence["marker"] = match.group(1)
                continue
            self.in_fence.add(index)
            marker = open_fence["marker"]
            stripped = line.strip()
            if len(stripped) >= len(marker) and set(stripped) == {marker[0]}:
                open_fence["end"] = index
                self.fences.append(open_fence)
                open_fence = None
        if open_fence is not None:
            self.fences.append(open_fence)
            self.in_fence.update(range(open_fence["start"] + 1, len(self.lines)))
        for fence in self.fences:
            self.in_fence.add(fence["start"])
        self.sections: list[dict[str, Any]] = []
        for index, line in enumerate(self.lines):
            match = H2.match(line)
            if match and index not in self.in_fence:
                self.sections.append({"title": match.group(1), "line": index})
        for position, section in enumerate(self.sections):
            end = (
                self.sections[position + 1]["line"]
                if position + 1 < len(self.sections)
                else len(self.lines)
            )
            section["end"] = end
            section["body"] = "\n".join(self.lines[section["line"] + 1 : end]).strip()
            raw_body = self.raw_lines[section["line"] + 1 : end]
            first = next((r for r in raw_body if r.strip()), "")
            section["optional"] = bool(OPTIONAL_MARK.match(first))

    def header_fence(self) -> Optional[dict[str, Any]]:
        limit = self.sections[0]["line"] if self.sections else len(self.lines)
        for fence in self.fences:
            if fence["start"] < limit and fence["lang"] == "yaml":
                return fence
        return None

    def section(self, title: str) -> Optional[dict[str, Any]]:
        for section in self.sections:
            if norm(section["title"]) == title:
                return section
        return None


def norm(title: str) -> str:
    return " ".join(title.lower().split())


def is_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return bool(PLACEHOLDER.search(value))
    if isinstance(value, list):
        return any(is_placeholder(item) for item in value)
    return False


def is_empty(value: Any) -> bool:
    return value is None or value == [] or (isinstance(value, str) and not value.strip())


def read_header(doc: Doc) -> tuple[Optional[dict[str, Any]], Optional[HeaderError]]:
    fence = doc.header_fence()
    if fence is None:
        return None, None
    end = fence["end"] if fence["end"] is not None else len(doc.raw_lines)
    try:
        return parse_header(doc.raw_lines[fence["start"] + 1 : end], fence["start"] + 2), None
    except HeaderError as exc:
        return None, exc


# --- checks ------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []

    def add(self, code: str, line: int, message: str) -> None:
        self.findings.append({"code": code, "line": line, "message": message})

    def warn(self, code: str, line: int, message: str) -> None:
        self.warnings.append({"code": code, "line": line, "message": message})


def triage(
    header: dict[str, Any], schema: dict[str, Any], prefix: str, report: Report, line: int
) -> tuple[dict[str, Any], set[str], set[str]]:
    """Drop placeholder and empty values before schema validation, reporting placeholders."""
    clean: dict[str, Any] = {}
    placeholders: set[str] = set()
    empties: set[str] = set()
    properties = schema.get("properties", {})
    for key, value in header.items():
        path = f"{prefix}.{key}"
        if is_placeholder(value):
            report.add("placeholder", line, f"header {path[2:]} still holds a placeholder")
            placeholders.add(path)
        elif is_empty(value):
            empties.add(path)
        elif isinstance(value, dict) and isinstance(properties.get(key), dict):
            sub, more_placeholders, more_empties = triage(
                value, properties[key], path, report, line
            )
            clean[key] = sub
            placeholders |= more_placeholders
            empties |= more_empties
        else:
            clean[key] = value
    return clean, placeholders, empties


def check_header(doc: Doc, schema: dict[str, Any], report: Report) -> dict[str, Any]:
    header, error = read_header(doc)
    fence = doc.header_fence()
    if fence is None:
        report.add("header-missing", 1, "no ```yaml header block before the first ## section")
        return {}
    line = fence["start"] + 1
    if error is not None:
        report.add("header-malformed", error.line, error.message)
        return {}
    assert header is not None
    known = set(schema.get("properties", {}))
    for key in header:
        if known and key not in known:
            report.add("header-unknown-key", line, f"'{key}' is not a field of this header")
    clean, placeholders, empties = triage(header, schema, "$", report, line)
    errors: list[tuple[str, str]] = []
    validate(clean, schema, "$", errors)
    for path, message in errors:
        if path in placeholders:
            continue
        label = path[2:] or "header"
        if path in empties and message == "required field is missing":
            report.add("empty-value", line, f"header {label} is empty")
        else:
            report.add("schema", line, f"header {label}: {message}")
    return header


def template_sections(template: Path) -> list[dict[str, Any]]:
    try:
        text = template.read_text(encoding="utf-8")
    except FileNotFoundError:
        die(EXIT_INPUT, f"{template}: template not found")
    except UnicodeDecodeError:
        die(EXIT_MALFORMED, f"{template}: template is not UTF-8")
    sections = Doc(text).sections
    if not sections:
        die(EXIT_MALFORMED, f"{template}: template has no ## sections")
    return sections


def check_sections(
    doc: Doc, expected: list[dict[str, Any]], report: Report, optional_may_be_missing: bool = False
) -> None:
    seen: dict[str, int] = {}
    for section in doc.sections:
        key = norm(section["title"])
        if key in seen:
            report.add("section-duplicate", section["line"] + 1, f"'{section['title']}' twice")
        seen.setdefault(key, section["line"])
    wanted = {norm(s["title"]) for s in expected}
    for section in doc.sections:
        if norm(section["title"]) not in wanted:
            report.warn(
                "section-extra", section["line"] + 1, f"'{section['title']}' is not in the template"
            )
    last = -1
    for item in expected:
        key = norm(item["title"])
        section = doc.section(key)
        if section is None:
            if not (optional_may_be_missing and item["optional"]):  # a contribution's extras
                report.add("section-missing", 1, f"section '{item['title']}' is missing")
            continue
        number = section["line"] + 1
        if section["line"] < last:
            report.add("section-order", number, f"'{item['title']}' is out of template order")
        last = max(last, section["line"])
        body = section["body"]
        if not body:
            report.add("section-empty", number, f"'{item['title']}' is empty")
            continue
        match = NOT_APPLICABLE.match(body)
        if match is None:
            continue
        reason = match.group(1).strip()
        if not item["optional"]:
            report.add(
                "not-applicable-not-allowed",
                number,
                f"'{item['title']}' is required; it cannot be marked not applicable",
            )
        elif not reason or is_placeholder(reason):
            report.add("not-applicable-no-reason", number, f"'{item['title']}' gives no reason")


def check_placeholders(doc: Doc, report: Report) -> None:
    fence = doc.header_fence()
    skip: set[int] = set()
    if fence is not None:
        end = fence["end"] if fence["end"] is not None else len(doc.lines)
        skip = set(range(fence["start"], end + 1))
    for index, line in enumerate(doc.lines):
        if index in skip:
            continue
        markers = sorted({m.group(0) for m in PLACEHOLDER.finditer(line)})
        if markers:
            report.add("placeholder", index + 1, "left in the text: " + ", ".join(markers))
    for index, raw in enumerate(doc.raw_lines):
        if "<!--" in TOOL_COMMENT.sub("", raw) and index not in doc.in_fence:
            report.warn("guidance-comment", index + 1, "template guidance comment left in")
            break


def table_ids(doc: Doc, section: dict[str, Any], report: Report) -> list[tuple[int, int]]:
    """``(line, id)`` for each row of the decisions table, read from its ``Id`` column."""
    rows = [
        (index, doc.lines[index])
        for index in range(section["line"] + 1, section["end"])
        if doc.lines[index].strip().startswith("|")
    ]
    if not rows:
        return []
    cells = [c.strip().lower() for c in rows[0][1].strip().strip("|").split("|")]
    if "id" not in cells:
        report.add("decision-table", rows[0][0] + 1, "the decisions table has no 'Id' column")
        return []
    column = cells.index("id")
    found: list[tuple[int, int]] = []
    for index, text in rows[1:]:
        values = [c.strip() for c in text.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", v) for v in values if v):
            continue
        if PLACEHOLDER.search(text):
            continue
        match = DECISION_ID.fullmatch(values[column]) if column < len(values) else None
        if match is None:
            report.add("decision-no-id", index + 1, "a decision row has no D<n> id in 'Id'")
            continue
        found.append((index + 1, int(match.group(1))))
    return found


def check_decisions(doc: Doc, report: Report, floor: int) -> list[str]:
    section = doc.section(DECISIONS_SECTION)
    if section is None or NOT_APPLICABLE.match(section["body"]):
        return []
    ids = table_ids(doc, section, report)
    seen: set[int] = set()
    previous = 0
    for line, number in ids:
        if number in seen:
            report.add("decision-duplicate", line, f"D{number} appears twice")
        elif number < previous:
            report.add("decision-order", line, f"D{number} comes after D{previous}")
        if number <= floor:
            report.add(
                "decision-not-new",
                line,
                f"D{number} is not new: the HLA record already reaches D{floor}",
            )
        seen.add(number)
        previous = max(previous, number)
    return [f"D{n}" for _, n in ids]


def load_index(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(EXIT_INPUT, f"{path}: ADR index not found. Build it with build_adr_index.py.")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        die(EXIT_MALFORMED, f"{path}: ADR index is not valid JSON: {exc}")
    adrs = data.get("adrs") if isinstance(data, dict) else None
    if not isinstance(adrs, list):
        die(EXIT_MALFORMED, f"{path}: ADR index has no 'adrs' list")
    return data


def check_adrs(
    doc: Doc, header: dict[str, Any], index: Optional[dict[str, Any]], report: Report
) -> list[str]:
    cited: dict[str, int] = {}
    for number, line in enumerate(doc.lines):
        for match in ADR_ID.finditer(line):
            cited.setdefault(match.group(0), number + 1)
    if not cited:
        return []
    if index is None:
        report.warn("adr-unchecked", min(cited.values()), "ADRs are cited but no --adr-index given")
        return sorted(cited)
    known = {str(a.get("id", "")).upper(): a for a in index["adrs"] if isinstance(a, dict)}
    for adr, line in sorted(cited.items(), key=lambda item: item[1]):
        entry = known.get(adr.upper())
        if entry is None:
            report.add("adr-unknown", line, f"{adr} is not in the ADR index")
        elif str(entry.get("status", "")).lower() != "accepted":
            report.warn("adr-not-accepted", line, f"{adr} is {entry.get('status')}, not Accepted")
    commit = header.get("adr_registry_commit")
    built = index.get("registry_commit")
    stale = (
        isinstance(commit, str)
        and commit not in {"", "none"}
        and isinstance(built, str)
        and not built.startswith(commit)
        and not commit.startswith(built)
    )
    if stale:
        report.warn(
            "adr-commit-mismatch",
            1,
            f"header names registry commit {commit}; the index was built from {str(built)[:12]}",
        )
    return sorted(cited)


def check_diagrams(doc: Doc, report: Report) -> None:
    for fence in doc.fences:
        line = fence["start"] + 1
        if fence["end"] is None:
            report.add("fence-unclosed", line, "a code fence is never closed")
            continue
        if fence["lang"] != "mermaid":
            continue
        body = doc.lines[fence["start"] + 1 : fence["end"]]
        if not any(text.strip() for text in body):
            report.add("diagram-empty", line, "the mermaid diagram is empty")
            continue
        after = next((t for t in doc.lines[fence["end"] + 1 :] if t.strip()), "")
        if not after or after.lstrip().startswith(("#", "```", "~~~", "|")):
            report.add("diagram-no-text", line, "a diagram must be followed by a text description")


def read_doc(path: Path) -> Doc:
    try:
        return Doc(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(EXIT_INPUT, f"{path}: document not found")
    except UnicodeDecodeError:
        die(EXIT_MALFORMED, f"{path}: not valid UTF-8; re-save it as UTF-8")


def check_hla_link(path: Path, header: dict[str, Any], report: Report) -> int:
    """Return the highest decision id recorded for the linked HLA (0 when unknown)."""
    link = header.get("hla_link")
    if not isinstance(link, str) or not link.strip() or is_placeholder(link):
        return 0
    target = Path(link).expanduser()
    if not target.is_absolute():
        target = path.parent / target
    if not target.is_file():
        report.add("hla-link-unresolved", 1, f"hla_link '{link}' does not resolve to a file")
        return 0
    hla = read_doc(target)
    hla_header, error = read_header(hla)
    status = (hla_header or {}).get("status")
    if error is not None or hla_header is None:
        report.add("hla-not-accepted", 1, f"{link}: its header cannot be read")
    elif status != "accepted":
        report.add("hla-not-accepted", 1, f"{link}: header status is '{status}', not accepted")
    texts = ["\n".join(hla.lines)]
    record = target.parent / "hla-decisions.md"
    if record.is_file():
        texts.append(strip_block(record.read_text(encoding="utf-8", errors="replace")))
    numbers = [int(n) for text in texts for n in DECISION_ID.findall(text)]
    return max(numbers, default=0)


def cell_texts(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").replace("\\|", "\0").split("|")]


def read_record(
    folder: Path, names: tuple[str, ...], report: Optional[Report] = None
) -> Optional[dict[int, str]]:
    """Ids declared in the decision record(s) next to a document, with their Status words.

    ``None`` when no record exists, so a check can stay silent instead of calling every id
    unknown. A row declares an id in its first cell, bold or quoted ones included; the Status
    column is optional. A record with no row it can read gives an empty result and, with a
    ``report``, one warning: every cited id would otherwise be called unknown."""
    declared: dict[int, str] = {}
    found = False
    for name in names:
        record = folder / name
        if not record.is_file():
            continue
        found = True
        status_column = -1
        for line in strip_block(record.read_text(encoding="utf-8", errors="replace")).splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [c.lower() for c in cell_texts(line)]
            if cells and cells[0] == "id":
                status_column = cells.index("status") if "status" in cells else -1
                continue
            match = RECORD_ROW_ID.match(line)
            if match:
                values = cell_texts(line)
                status = values[status_column] if 0 <= status_column < len(values) else ""
                declared[int(match.group(1))] = status.lower()
    if found and not declared and report is not None:
        report.warn(
            "decision-record-unreadable",
            1,
            "the decision record has no row this check can read (| D<n> | ... |); "
            "decision ids are not checked",
        )
    return declared if found else None


def appendix_lines(doc: Doc) -> set[int]:
    """Lines of every top-level section whose title starts with "Appendix" (history lives there)."""
    skip: set[int] = set()
    for section in doc.sections:
        if norm(section["title"]).startswith("appendix"):
            skip.update(range(section["line"], section["end"]))
    return skip


def cited_decisions(doc: Doc, skip: set[int]) -> dict[int, int]:
    """First line of each bare ``D<n>`` in prose; code fences, appendices and ``u3:D2`` are not."""
    cited: dict[int, int] = {}
    for index, line in enumerate(doc.lines):
        if index in doc.in_fence or index in skip:
            continue
        for match in CITED_DECISION.finditer(line):
            cited.setdefault(int(match.group(1)), index + 1)
    return cited


def check_cited_decisions(doc: Doc, declared: Optional[dict[int, str]], report: Report) -> None:
    """Every cited D<n> must be in the record; a superseded one is a warning."""
    if not declared:  # no record, or one that could not be read: nothing to compare with
        return
    for number, line in sorted(cited_decisions(doc, appendix_lines(doc)).items()):
        if number not in declared:
            report.add("decision-unknown", line, f"D{number} is not in the decision record")
        elif declared[number] == "superseded":
            report.warn("decision-superseded", line, f"D{number} is superseded in the record")


def check_contribution(path: Path, doc: Doc, header: dict[str, Any], report: Report) -> None:
    concern = header.get("concern")
    if isinstance(concern, str) and concern.strip() and concern != path.stem:
        report.add(
            "concern-name",
            1,
            f"header concern '{concern}' must equal the file name '{path.stem}'",
        )
    declared = read_record(path.parent.parent, RECORDS, report)
    if declared is None and cited_decisions(doc, set()):
        report.warn("decision-record-missing", 1, "decisions are cited but no record was found")
    check_cited_decisions(doc, declared, report)


def tables(doc: Doc, skip: set[int]) -> list[dict[str, Any]]:
    """Markdown tables outside code fences and ``skip`` lines: lower-case header, rows by line."""
    found: list[dict[str, Any]] = []
    index = 0
    while index < len(doc.lines):
        if index in doc.in_fence or index in skip or not doc.lines[index].strip().startswith("|"):
            index += 1
            continue
        start = index
        while (
            index < len(doc.lines)
            and index not in doc.in_fence
            and index not in skip
            and doc.lines[index].strip().startswith("|")
        ):
            index += 1
        block = doc.lines[start:index]
        separator = cell_texts(block[1]) if len(block) > 1 else []
        if not separator or not all(re.fullmatch(r":?-{3,}:?", c) for c in separator if c):
            continue
        found.append(
            {
                "header": [c.lower() for c in cell_texts(block[0])],
                "rows": [(start + n + 1, cell_texts(t)) for n, t in enumerate(block) if n > 1],
            }
        )
    return found


def name_key(text: str) -> str:
    return " ".join(text.replace("`", "").replace("*", "").lower().split())


def column(header: list[str], *names: str) -> int:
    for position, cell in enumerate(header):
        if cell in names or any(cell.startswith(n + " ") for n in names):
            return position
    return -1


def check_owners(found: list[dict[str, Any]], report: Report) -> None:
    """One owner per term and per container; a table without an owner column is skipped."""
    seen: dict[tuple[str, str], list[tuple[str, str, int]]] = {}
    for table in found:
        owner = column(table["header"], "owning context", "owner")
        for kind in ("term", "container"):
            name = column(table["header"], kind)
            if name < 0 or owner < 0:
                continue
            for line, cells in table["rows"]:
                if max(name, owner) < len(cells) and cells[name] and cells[owner]:
                    entry = (name_key(cells[owner]), cells[owner], line)
                    seen.setdefault((kind, name_key(cells[name])), []).append(entry)
    for (kind, key), entries in sorted(seen.items(), key=lambda item: item[1][0][2]):
        owners = {entry[0] for entry in entries}
        if len(owners) > 1:
            first = entries[0]
            other = next(entry for entry in entries if entry[0] != first[0])
            report.add(
                "owner-duplicate",
                other[2],
                f"{kind} '{key}' has two owners: '{first[1]}' (line {first[2]}) "
                f"and '{other[1]}' (line {other[2]})",
            )


def check_interface_parties(found: list[dict[str, Any]], report: Report) -> None:
    """Producers and consumers in interface tables should be containers the document names."""
    containers: set[str] = set()
    for table in found:
        name = column(table["header"], "container")
        if name >= 0:
            containers |= {
                name_key(cells[name]) for _, cells in table["rows"] if name < len(cells)
            } - {""}
    if not containers:
        return
    reported: set[str] = set()
    for table in found:
        if "producer" not in table["header"] or "consumer" not in table["header"]:
            continue  # e.g. hand-overs between teams name a provider and phases, not containers
        columns = [table["header"].index("producer"), table["header"].index("consumer")]
        for line, cells in table["rows"]:
            for position in (c for c in columns if c < len(cells)):
                for part in re.split(r"<br\s*/?>|[,;]", cells[position]):
                    party = name_key(part)
                    if party in reported or party in {"", "-", "none", "n/a"}:
                        continue
                    if party in containers:  # a whole name, not a part of one
                        continue
                    reported.add(party)
                    report.warn(
                        "interface-party-unknown",
                        line,
                        f"'{part.strip()}' in an interface table is not a container named here",
                    )


def check_consistency(path: Path, doc: Doc, report: Report) -> None:
    """HLA checks that need no judgement: the decision record and the tables agree with the text."""
    check_cited_decisions(doc, read_record(path.parent, RECORDS[:1], report), report)
    found = tables(doc, appendix_lines(doc))
    check_owners(found, report)
    check_interface_parties(found, report)


def kind_rules(path: Path, doc: Doc, kind: str, header: dict[str, Any], report: Report) -> None:
    if kind == "contribution":
        check_contribution(path, doc, header, report)
    if kind != "hla":
        return
    check_consistency(path, doc, report)
    flags = header.get("impact_flags")
    if isinstance(flags, list) and "none" in flags and len(flags) > 1:
        report.add("impact-flags", 1, "impact_flags lists 'none' together with other flags")
    section = doc.section(MODERNIZATION_SECTION)
    if (
        header.get("solution_type") == "modernization"
        and section is not None
        and NOT_APPLICABLE.match(section["body"])
    ):
        report.add(
            "modernization-required",
            section["line"] + 1,
            "solution_type is modernization, so the modernization plan cannot be skipped",
        )


def run(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.file)
    template = Path(args.template) if args.template else ASSETS / f"{args.kind}-template.md"
    schema_path = Path(args.schema) if args.schema else ASSETS / f"{args.kind}-header.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(EXIT_INPUT, f"{schema_path}: header schema not found for kind '{args.kind}'")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        die(EXIT_MALFORMED, f"{schema_path}: not valid JSON: {exc}")
    check_schema(schema)
    expected = template_sections(template)
    index = load_index(Path(args.adr_index)) if args.adr_index else None
    doc = read_doc(path)

    report = Report()
    header = check_header(doc, schema, report)
    check_sections(doc, expected, report, args.kind == "contribution")
    check_placeholders(doc, report)
    floor = check_hla_link(path, header, report) if args.kind == "tdd" else 0
    decisions = check_decisions(doc, report, floor)
    adrs = check_adrs(doc, header, index, report)
    check_diagrams(doc, report)
    kind_rules(path, doc, args.kind, header, report)
    report.findings.sort(key=lambda item: item["line"])
    return {
        "ok": not report.findings,
        "file": str(path),
        "kind": args.kind,
        "findings": report.findings,
        "warnings": report.warnings,
        "decisions": decisions,
        "adrs": adrs,
        "status": header.get("status"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate an HLA, TDD or contribution against its template and header schema.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", required=True, help="The document to check.")
    parser.add_argument("--kind", required=True, choices=["hla", "tdd", "contribution"])
    parser.add_argument("--adr-index", help="architecture-index.json built by build_adr_index.py.")
    parser.add_argument("--template", help="Override the template (default: assets/).")
    parser.add_argument("--schema", help="Override the header schema (default: assets/).")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        result = run(args)
    except Fail as exc:
        LOG.error("%s", exc.message)
        sys.stdout.write(json.dumps({"ok": False, "error": exc.message}, indent=2) + "\n")
        return exc.code
    for item in result["findings"]:
        LOG.error("%s:%s %s: %s", args.file, item["line"], item["code"], item["message"])
    for item in result["warnings"]:
        LOG.warning("%s:%s %s: %s", args.file, item["line"], item["code"], item["message"])
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return EXIT_FINDINGS if result["findings"] else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        LOG.exception("internal error")
        sys.exit(EXIT_INTERNAL)
