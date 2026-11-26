#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Check that Inception ids trace from requirements to stories to units.

A requirement nobody builds and a story nobody can test both look finished in a
review and fail in delivery. This reads the Inception documents of a bolt
and lists the gaps, so the last Inception gate can refuse while they exist.

An id is declared where it starts a Markdown heading or the first cell of a
table row; any other occurrence is a reference. A reference links the id to the
declaration it sits under: the row's own id in a table, otherwise the nearest
heading that declares an id. Ids: FR-n, NFR-n, US-n, AC-n.m, U-n.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EPILOG = """examples:
  python3 check_traceability.py --bolt bolts/2026-01-05-billing

findings (exit 1): requirement-uncovered (an FR or NFR no story or unit references),
  story-no-unit, unit-orphan (no story or requirement), story-no-ac,
  undeclared-id (referenced but never declared)

Declare an id as the start of a heading or the first cell of a table row. Write
acceptance criteria that way too: a table row or heading per AC-n.m under US-n.

exit codes:
  0  no gaps
  1  gaps found (JSON findings on stdout)
  2  usage error
  3  the bolt or its docs/inception folder is missing
  4  a document is not valid UTF-8 text
  5  internal error
"""

LOG = logging.getLogger("check_traceability")

ID = r"(?:AC-\d+\.\d+|(?:NFR|FR|US|U)-\d+)"
ID_RE = re.compile(rf"(?<![\w-])({ID})(?![\w-])")
START_RE = re.compile(rf"^[\s*_`\[(]*({ID})(?![\w-])")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SEPARATOR_RE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
SKIPPED_NAMES = ("questions", "clarifications")
REQUIREMENT = ("FR", "NFR")


def kind(ident: str) -> str:
    return ident.split("-", 1)[0]


def is_scanned(path: Path) -> bool:
    return path.suffix == ".md" and not any(word in path.name for word in SKIPPED_NAMES)


class Graph:
    def __init__(self) -> None:
        self.declared: set[str] = set()
        self.referenced: dict[str, set[str]] = {}
        self.links: dict[str, set[str]] = {}
        self.files: dict[str, set[str]] = {}

    def declare(self, ident: str, file: str) -> None:
        self.declared.add(ident)
        self.files.setdefault(ident, set()).add(file)

    def refer(self, ident: str, subject: Optional[str], file: str) -> None:
        self.referenced.setdefault(ident, set()).add(file)
        if subject and subject != ident:
            self.links.setdefault(subject, set()).add(ident)
            self.links.setdefault(ident, set()).add(subject)


def starting_id(text: str, offset: int = 0) -> Optional[tuple[str, int]]:
    """The id that starts ``text`` (after markup), with its position in the line."""
    found = START_RE.match(text)
    return (found.group(1), offset + found.start(1)) if found else None


def scan_text(text: str, file: str, graph: Graph) -> None:
    stack: list[tuple[int, str]] = []  # (heading level, id it declares)
    in_fence = False
    in_block = False
    for line in text.splitlines():
        # The block aidlc_refs.py link generates repeats ids; it is not a reference.
        if line.startswith("<!-- aidlc-refs:begin"):
            in_block = True
        if in_block:
            in_block = "aidlc-refs:end" not in line
            continue
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        declared: Optional[tuple[str, int]] = None
        subject = stack[-1][1] if stack else None
        heading = None if in_fence else HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            declared = starting_id(heading.group(2), heading.start(2))
            if declared:
                stack.append((level, declared[0]))
            subject = stack[-1][1] if stack else None
        elif not in_fence and line.lstrip().startswith("|") and not SEPARATOR_RE.match(line):
            cell = line.split("|", 2)[1] if line.count("|") >= 2 else ""
            declared = starting_id(cell, line.index("|") + 1)
            if declared:
                subject = declared[0]
        if declared:
            graph.declare(declared[0], file)
        skip = declared[1] if declared else -1
        for found in ID_RE.finditer(line):
            if found.start(1) != skip:
                graph.refer(found.group(1), subject, file)


def scan(bolt: Path) -> Graph:
    base = bolt / "docs" / "inception"
    graph = Graph()
    for path in sorted(base.rglob("*.md")):
        if not is_scanned(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path}: not valid UTF-8 text ({exc.reason})") from exc
        scan_text(text, str(path.relative_to(bolt)), graph)
    return graph


def sort_key(ident: str) -> tuple[str, list[int]]:
    return kind(ident), [int(n) for n in re.findall(r"\d+", ident)]


def findings_for(graph: Graph) -> list[dict[str, Any]]:
    def linked(ident: str, kinds: tuple[str, ...]) -> bool:
        return any(kind(other) in kinds for other in graph.links.get(ident, ()))

    out: list[dict[str, Any]] = []

    def add(code: str, ident: str, message: str) -> None:
        out.append(
            {
                "code": code,
                "id": ident,
                "message": message,
                "files": sorted(graph.files.get(ident, ())),
            }
        )

    for ident in sorted(graph.declared, key=sort_key):
        k = kind(ident)
        if k in REQUIREMENT and not linked(ident, ("US", "U")):
            add("requirement-uncovered", ident, f"{ident} is not referenced by any story or unit")
        elif k == "US":
            number = ident.split("-", 1)[1]
            if not linked(ident, ("U",)):
                add("story-no-unit", ident, f"{ident} is not assigned to any unit")
            if not any(d.startswith(f"AC-{number}.") for d in graph.declared):
                add("story-no-ac", ident, f"{ident} has no acceptance criteria (AC-{number}.m)")
        elif k == "U" and not linked(ident, ("US", "FR", "NFR")):
            add("unit-orphan", ident, f"{ident} serves no story or requirement")
    for ident in sorted(set(graph.referenced) - graph.declared, key=sort_key):
        out.append(
            {
                "code": "undeclared-id",
                "id": ident,
                "message": f"{ident} is referenced but never declared",
                "files": sorted(graph.referenced[ident]),
            }
        )
    return out


def check(bolt: Path) -> dict[str, Any]:
    """Scan ``bolt/docs/inception`` and return ``{ok, declared, findings}``."""
    graph = scan(bolt)
    findings = findings_for(graph)
    counts: dict[str, int] = {}
    for ident in graph.declared:
        counts[kind(ident)] = counts.get(kind(ident), 0) + 1
    return {
        "ok": not findings,
        "bolt": str(bolt),
        "declared": dict(sorted(counts.items())),
        "findings": findings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report requirements, stories and units that are not traced to each other.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--bolt", required=True, help="Bolt folder.")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    bolt = Path(args.bolt)
    if not (bolt / "docs" / "inception").is_dir():
        LOG.error("%s: docs/inception not found.", bolt)
        return EXIT_INPUT
    try:
        result = check(bolt)
    except ValueError as exc:
        LOG.error("%s", exc)
        return EXIT_MALFORMED
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    for item in result["findings"]:
        LOG.error("%s: %s", item["code"], item["message"])
    return EXIT_OK if result["ok"] else EXIT_FINDINGS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        LOG.exception("internal error")
        sys.exit(EXIT_INTERNAL)
