"""lib.frontmatter refuses everything a harness would silently reject."""

from __future__ import annotations

from pathlib import Path

import pytest
from lib.frontmatter import FrontmatterError, parse_text


def parse(text: str):
    return parse_text(text, Path("SKILL.md"))


def test_parses_valid_frontmatter():
    parsed = parse("---\nname: crv-x\ndescription: d\n---\n\n# Body\n\ntext\n")
    assert parsed.data == {"name": "crv-x", "description": "d"}
    assert parsed.body.strip().startswith("# Body")
    assert parsed.body_start_line == 5


def test_rejects_missing_opening_fence():
    with pytest.raises(FrontmatterError, match="missing opening"):
        parse("# No frontmatter\n")


def test_rejects_unclosed_fence():
    with pytest.raises(FrontmatterError, match="never closed"):
        parse("---\nname: crv-x\n")


def test_rejects_bom():
    """A BOM is invisible in an editor and makes the fence not the first bytes."""
    with pytest.raises(FrontmatterError, match="BOM"):
        parse("﻿---\nname: crv-x\n---\n")


def test_rejects_duplicate_keys():
    """Stock YAML keeps the last value silently; the author never sees the other one."""
    with pytest.raises(FrontmatterError, match="duplicate key"):
        parse("---\nname: crv-x\ndescription: one\ndescription: two\n---\n")


def test_rejects_non_mapping():
    with pytest.raises(FrontmatterError, match="must be a mapping"):
        parse("---\n- one\n- two\n---\n")


def test_rejects_empty_block():
    with pytest.raises(FrontmatterError, match="empty"):
        parse("---\n---\n\nbody\n")


def test_reports_a_line_number_for_bad_yaml():
    with pytest.raises(FrontmatterError) as excinfo:
        parse("---\nname: crv-x\n  bad: indent\n---\n")
    assert excinfo.value.line is not None


def test_body_line_count_ignores_trailing_newline():
    parsed = parse("---\nname: crv-x\ndescription: d\n---\nline1\nline2\n\n\n")
    assert parsed.body_line_count == 2
