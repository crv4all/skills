#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Outline the raw documents handed into a paddock so agents read ranges, not files.

A model asked to read a 200-page specification reads all of it, every session.
An outline with line ranges and sizes lets the Document Knowledge stage send a
cheap worker to one section at a time. Word, PowerPoint and Excel files are
unzipped and their text written to ``knowledge/extracted/`` first; nothing in
``inputs/`` is ever modified, and nothing leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree as ET

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EPILOG = """examples:
  python3 index_inputs.py --paddock paddocks/2026-01-05-billing

Writes knowledge/_outline.json and knowledge/extracted/<file>.md.
Per file: outlined (markdown, text), extracted (docx, pptx, xlsx, and pdf when
pdftotext is installed), not-extracted (pdf without pdftotext), skipped (data
files, files over 1 MB that are not documents, unsupported types), failed.

exit codes:
  0  every file was handled or deliberately skipped
  1  at least one file failed to extract
  2  usage error
  3  the paddock or its inputs/ folder does not exist
  4  the paddock is malformed
  5  internal error
"""

LOG = logging.getLogger("index_inputs")

MAX_PLAIN_BYTES = 1_000_000
MAX_ZIP_MEMBER = 100_000_000
MAX_SHEET_ROWS = 5000
TEXT_SUFFIXES = {".md", ".markdown", ".txt"}
DATA_SUFFIXES = {
    ".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet", ".avro", ".xml", ".yaml", ".yml",
    ".sql", ".db", ".sqlite", ".zip", ".gz", ".tar", ".log",
}  # fmt: skip
FENCE = re.compile(r"^\s*(```|~~~)")
ATX = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def outline(text: str) -> list[dict[str, Any]]:
    """Sections of ``text`` by Markdown heading, with 1-based inclusive line ranges."""
    lines = text.splitlines()
    heads: list[tuple[int, int, str]] = []
    fenced = False
    for number, line in enumerate(lines, start=1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else ATX.match(line)
        if match:
            heads.append((number, len(match.group(1)), match.group(2)))

    def size(first: int, last: int) -> int:
        return sum(len(line.encode("utf-8")) + 1 for line in lines[first - 1 : last])

    sections: list[dict[str, Any]] = []
    if not lines:
        return sections
    first_head = heads[0][0] if heads else len(lines) + 1
    if any(line.strip() for line in lines[: first_head - 1]):
        title = "(whole file)" if not heads else "(preamble)"
        sections.append(
            {"title": title, "level": 0, "start_line": 1, "end_line": first_head - 1,
             "bytes": size(1, first_head - 1)}
        )  # fmt: skip
    for index, (number, level, title) in enumerate(heads):
        end = heads[index + 1][0] - 1 if index + 1 < len(heads) else len(lines)
        sections.append(
            {"title": title, "level": level, "start_line": number, "end_line": end,
             "bytes": size(number, end)}
        )  # fmt: skip
    return sections


def read_member(archive: zipfile.ZipFile, name: str) -> ET.Element:
    info = archive.getinfo(name)
    if info.file_size > MAX_ZIP_MEMBER:
        raise ValueError(f"{name} is {info.file_size} bytes unpacked; refusing to read it")
    return ET.fromstring(archive.read(name))


def cell_row(cells: list[str]) -> str:
    return "| " + " | ".join(c.replace("|", "/").replace("\n", " ") for c in cells) + " |"


def docx_to_markdown(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = read_member(archive, "word/document.xml")
    body = root.find(f"{W}body")
    out: list[str] = []

    def para_text(para: ET.Element) -> str:
        parts: list[str] = []
        for node in para.iter():
            if node.tag == f"{W}t" and node.text:
                parts.append(node.text)
            elif node.tag in (f"{W}tab", f"{W}br"):
                parts.append(" ")
        return "".join(parts).strip()

    def level_of(para: ET.Element) -> int:
        style = para.find(f"{W}pPr/{W}pStyle")
        value = style.get(f"{W}val", "") if style is not None else ""
        if value.lower() == "title":
            return 1
        match = re.match(r"(?i)^heading\s*(\d)$", value)
        return min(int(match.group(1)), 6) if match else 0

    for child in list(body) if body is not None else []:
        if child.tag == f"{W}p":
            text = para_text(child)
            if not text:
                continue
            level = level_of(child)
            out.append(f"{'#' * level} {text}" if level else text)
            out.append("")
        elif child.tag == f"{W}tbl":
            for row in child.iter(f"{W}tr"):
                cells = [
                    " ".join(para_text(p) for p in cell.iter(f"{W}p")).strip()
                    for cell in row.findall(f"{W}tc")
                ]
                out.append(cell_row(cells))
            out.append("")
    return "\n".join(out)


def pptx_to_markdown(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)]
        names.sort(key=lambda n: int(re.findall(r"\d+", n)[-1]))
        out: list[str] = []
        for index, name in enumerate(names, start=1):
            root = read_member(archive, name)
            title = ""
            paragraphs: list[str] = []
            for shape in root.iter(f"{P}sp"):
                ph = shape.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
                is_title = ph is not None and ph.get("type") in ("title", "ctrTitle")
                for para in shape.iter(f"{A}p"):
                    text = "".join(t.text or "" for t in para.iter(f"{A}t")).strip()
                    if not text:
                        continue
                    if is_title and not title:
                        title = text
                    else:
                        paragraphs.append(text)
            out.append(f"## Slide {index}" + (f": {title}" if title else ""))
            out.append("")
            out.extend(f"- {text}" for text in paragraphs)
            out.append("")
    return "\n".join(out)


def column_index(ref: str) -> int:
    letters = re.match(r"^[A-Z]+", ref)
    value = 0
    for char in letters.group(0) if letters else "A":
        value = value * 26 + (ord(char) - 64)
    return value - 1


def xlsx_to_markdown(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            for item in read_member(archive, "xl/sharedStrings.xml").iter(f"{S}si"):
                shared.append("".join(t.text or "" for t in item.iter(f"{S}t")))
        workbook = read_member(archive, "xl/workbook.xml")
        rels = read_member(archive, "xl/_rels/workbook.xml.rels")
        targets = {
            rel.get("Id", ""): rel.get("Target", "") for rel in rels.iter(f"{PKG_REL}Relationship")
        }
        out: list[str] = []
        for sheet in workbook.iter(f"{S}sheet"):
            target = targets.get(sheet.get(f"{R}id", ""), "")
            member = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            out.append(f"## {sheet.get('name', 'Sheet')}")
            out.append("")
            if member not in names:
                out.append("(sheet part not found)")
                out.append("")
                continue
            rows = 0
            for row in read_member(archive, member).iter(f"{S}row"):
                if rows >= MAX_SHEET_ROWS:
                    out.append(f"(truncated after {MAX_SHEET_ROWS} rows)")
                    break
                cells: list[str] = []
                for cell in row.findall(f"{S}c"):
                    index = column_index(cell.get("r", "A1"))
                    cells.extend([""] * (index - len(cells)))
                    kind = cell.get("t")
                    if kind == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(f"{S}t"))
                    else:
                        node = cell.find(f"{S}v")
                        value = (node.text or "") if node is not None else ""
                        if kind == "s" and value.isdigit() and int(value) < len(shared):
                            value = shared[int(value)]
                    cells.append(value)
                if any(cells):
                    out.append(cell_row(cells))
                    rows += 1
            out.append("")
    return "\n".join(out)


def pdf_to_markdown(path: Path) -> Optional[str]:
    tool = shutil.which("pdftotext")
    if tool is None:
        return None
    done = subprocess.run(
        [tool, "-layout", str(path), "-"], capture_output=True, text=True, timeout=120, check=False
    )
    if done.returncode != 0:
        raise ValueError(f"pdftotext exited {done.returncode}: {done.stderr.strip()[:200]}")
    pages = done.stdout.split("\f")
    out: list[str] = []
    for number, page in enumerate(pages, start=1):
        if page.strip():
            out.extend([f"## Page {number}", "", page.rstrip(), ""])
    return "\n".join(out)


def process(paddock: Path, file: Path) -> dict[str, Any]:
    rel = file.relative_to(paddock).as_posix()
    suffix = file.suffix.lower()
    size = file.stat().st_size
    entry: dict[str, Any] = {"path": rel, "bytes": size, "kind": suffix.lstrip(".") or "none"}

    def skipped(reason: str) -> dict[str, Any]:
        return {**entry, "status": "skipped", "reason": reason, "outline": []}

    if suffix in TEXT_SUFFIXES:
        text = file.read_text(encoding="utf-8", errors="replace")
        return {**entry, "status": "outlined", "outline": outline(text)}
    if suffix in DATA_SUFFIXES:
        return skipped("data file")
    converters = {".docx": docx_to_markdown, ".pptx": pptx_to_markdown, ".xlsx": xlsx_to_markdown}
    if suffix in converters or suffix == ".pdf":
        try:
            text = pdf_to_markdown(file) if suffix == ".pdf" else converters[suffix](file)
        except (
            zipfile.BadZipFile,
            KeyError,
            ET.ParseError,
            ValueError,
            subprocess.SubprocessError,
        ) as exc:
            return {
                **entry,
                "status": "failed",
                "reason": str(exc) or type(exc).__name__,
                "outline": [],
            }
        if text is None:
            return {
                **entry,
                "status": "not-extracted",
                "reason": "pdftotext is not on the path",
                "outline": [],
            }
        out_name = "__".join(Path(rel).relative_to("inputs").parts) + ".md"
        out_path = paddock / "knowledge" / "extracted" / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        return {
            **entry,
            "status": "extracted",
            "extracted": out_path.relative_to(paddock).as_posix(),
            "outline": outline(text),
        }
    if size > MAX_PLAIN_BYTES:
        return skipped("over 1 MB and not a document")
    return skipped("unsupported type")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Outline the documents in a paddock's inputs/ folder.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--paddock", required=True, help="Paddock folder.")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    paddock = Path(args.paddock)
    inputs = paddock / "inputs"
    if not inputs.is_dir():
        LOG.error("%s: inputs/ not found. Is this a paddock?", inputs)
        return EXIT_INPUT
    (paddock / "knowledge").mkdir(exist_ok=True)

    files = sorted(
        p
        for p in inputs.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(inputs).parts)
    )
    entries = [process(paddock, file) for file in files]
    for item in entries:
        if item["status"] == "failed":
            LOG.error("%s: %s", item["path"], item["reason"])
    out_path = paddock / "knowledge" / "_outline.json"
    out_path.write_text(
        json.dumps({"schema": 1, "files": entries}, indent=2) + "\n", encoding="utf-8"
    )

    counts: dict[str, int] = {}
    for item in entries:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    failed = counts.get("failed", 0)
    sys.stdout.write(
        json.dumps(
            {
                "ok": failed == 0,
                "outline": out_path.relative_to(paddock).as_posix(),
                "files": len(entries),
                "counts": counts,
            },
            indent=2,
        )
        + "\n"
    )
    return EXIT_FINDINGS if failed else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        LOG.exception("internal error")
        sys.exit(EXIT_INTERNAL)
