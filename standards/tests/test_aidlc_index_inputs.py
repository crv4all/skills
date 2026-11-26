"""``index_inputs.py`` outlines the documents handed into a bolt."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts" / "index_inputs.py"

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
P = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


@pytest.fixture
def bolt(tmp_path: Path) -> Path:
    root = tmp_path / "bolt"
    (root / "inputs").mkdir(parents=True)
    return root


def run(bolt: Path) -> tuple[int, dict]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--bolt", str(bolt)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done.returncode, json.loads(done.stdout) if done.stdout else {}


def outline(bolt: Path) -> dict[str, dict]:
    data = json.loads((bolt / "knowledge" / "_outline.json").read_text(encoding="utf-8"))
    return {item["path"]: item for item in data["files"]}


def write_zip(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_markdown_outline_has_line_ranges_and_sizes(bolt: Path) -> None:
    text = "intro line\n# One\nbody\n```\n# not a heading\n```\n## Two\nmore\nmore\n"
    (bolt / "inputs" / "spec.md").write_text(text, encoding="utf-8")
    code, _ = run(bolt)
    assert code == 0
    sections = outline(bolt)["inputs/spec.md"]["outline"]
    assert [(s["title"], s["start_line"], s["end_line"]) for s in sections] == [
        ("(preamble)", 1, 1),
        ("One", 2, 6),
        ("Two", 7, 9),
    ]
    assert all(s["bytes"] > 0 for s in sections)


def test_text_without_headings_is_one_section(bolt: Path) -> None:
    (bolt / "inputs" / "notes.txt").write_text("a\nb\n", encoding="utf-8")
    run(bolt)
    sections = outline(bolt)["inputs/notes.txt"]["outline"]
    assert sections[0]["title"] == "(whole file)" and sections[0]["end_line"] == 2


def test_docx_headings_come_from_styles(bolt: Path) -> None:
    body = (
        f"<w:document {W}><w:body>"
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Scope</w:t></w:r></w:p>'
        "<w:p><w:r><w:t>Plain text.</w:t></w:r></w:p>"
        '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Detail</w:t></w:r></w:p>'
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>k</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>v</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        "</w:body></w:document>"
    )
    write_zip(bolt / "inputs" / "brief.docx", {"word/document.xml": body})
    code, _ = run(bolt)
    assert code == 0
    entry = outline(bolt)["inputs/brief.docx"]
    assert entry["status"] == "extracted"
    extracted = (bolt / entry["extracted"]).read_text(encoding="utf-8")
    assert "# Scope" in extracted and "## Detail" in extracted and "| k | v |" in extracted
    assert [s["title"] for s in entry["outline"]] == ["Scope", "Detail"]


def test_pptx_has_one_section_per_slide(bolt: Path) -> None:
    def slide(title: str, bullet: str) -> str:
        return (
            f"<p:sld {P} {A}><p:cSld><p:spTree>"
            '<p:sp><p:nvSpPr><p:cNvPr id="1" name="t"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
            f"<p:txBody><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>"
            '<p:sp><p:nvSpPr><p:cNvPr id="2" name="b"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f"<p:txBody><a:p><a:r><a:t>{bullet}</a:t></a:r></a:p></p:txBody></p:sp>"
            "</p:spTree></p:cSld></p:sld>"
        )

    write_zip(
        bolt / "inputs" / "deck.pptx",
        {
            "ppt/slides/slide2.xml": slide("Second", "two"),
            "ppt/slides/slide1.xml": slide("First", "one"),
        },
    )
    run(bolt)
    entry = outline(bolt)["inputs/deck.pptx"]
    assert [s["title"] for s in entry["outline"]] == ["Slide 1: First", "Slide 2: Second"]
    assert "- one" in (bolt / entry["extracted"]).read_text(encoding="utf-8")


def test_xlsx_has_one_section_per_sheet(bolt: Path) -> None:
    members = {
        "xl/workbook.xml": f'<workbook {S} {R}><sheets><sheet name="Costs" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/sharedStrings.xml": f"<sst {S}><si><t>Item</t></si><si><t>Price</t></si></sst>",
        "xl/worksheets/sheet1.xml": (
            f"<worksheet {S}><sheetData>"
            '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1" t="s"><v>1</v></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>pen</t></is></c><c r="C2"><v>3</v></c></row>'
            "</sheetData></worksheet>"
        ),
    }
    write_zip(bolt / "inputs" / "costs.xlsx", members)
    run(bolt)
    entry = outline(bolt)["inputs/costs.xlsx"]
    assert [s["title"] for s in entry["outline"]] == ["Costs"]
    text = (bolt / entry["extracted"]).read_text(encoding="utf-8")
    assert "| Item |  | Price |" in text and "| pen |  | 3 |" in text


def test_data_and_large_files_are_listed_and_skipped(bolt: Path) -> None:
    (bolt / "inputs" / "rows.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (bolt / "inputs" / "blob.bin").write_bytes(b"\0" * 1_100_000)
    (bolt / "inputs" / "small.bin").write_bytes(b"\0" * 10)
    run(bolt)
    data = outline(bolt)
    assert (
        data["inputs/rows.csv"]["status"] == "skipped"
        and data["inputs/rows.csv"]["reason"] == "data file"
    )
    assert data["inputs/blob.bin"]["reason"] == "over 1 MB and not a document"
    assert data["inputs/small.bin"]["status"] == "skipped"


def test_corrupt_document_is_reported_and_exit_is_1(bolt: Path) -> None:
    (bolt / "inputs" / "bad.docx").write_bytes(b"not a zip")
    (bolt / "inputs" / "ok.md").write_text("# fine\n", encoding="utf-8")
    code, summary = run(bolt)
    assert code == 1 and summary["counts"]["failed"] == 1
    assert outline(bolt)["inputs/ok.md"]["status"] == "outlined"


def test_inputs_are_never_modified(bolt: Path) -> None:
    (bolt / "inputs" / "a.md").write_text("# A\n", encoding="utf-8")
    write_zip(
        bolt / "inputs" / "b.docx",
        {"word/document.xml": f"<w:document {W}><w:body/></w:document>"},
    )

    def digest() -> dict[str, str]:
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (bolt / "inputs").iterdir()
        }

    before = digest()
    run(bolt)
    run(bolt)
    assert digest() == before
    assert sorted(p.name for p in (bolt / "inputs").iterdir()) == ["a.md", "b.docx"]


def test_missing_inputs_folder_exits_3(tmp_path: Path) -> None:
    assert run(tmp_path)[0] == 3
