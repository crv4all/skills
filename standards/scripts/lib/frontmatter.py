"""Parse the YAML frontmatter of a ``SKILL.md``.

Deliberately strict. A permissive parser here would let a file through that a
harness later rejects -- and the harness will reject it silently, by simply not
offering the skill, which is the hardest failure mode to diagnose. Everything
this module refuses, it refuses with a line number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

import yaml

FENCE = "---"


class FrontmatterError(Exception):
    """Raised when a file has no usable frontmatter.

    Attributes:
        path: the file the problem was found in.
        line: 1-based line number, or ``None`` when the problem is the file as
            a whole.
    """

    def __init__(self, message: str, path: Path, line: Union[int, None] = None) -> None:
        self.path = path
        self.line = line
        location = f"{path}:{line}" if line is not None else str(path)
        super().__init__(f"{location}: {message}")


class _NoDuplicateKeyLoader(yaml.SafeLoader):
    """A SafeLoader that refuses duplicate mapping keys.

    Stock YAML silently keeps the last value. In frontmatter that means a file
    with two ``description`` keys validates against one value and ships the
    other, and the author has no way to see it.
    """


def _construct_mapping(loader: _NoDuplicateKeyLoader, node: yaml.MappingNode, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = key_node.start_mark
            raise yaml.MarkedYAMLError(
                context="while parsing frontmatter",
                problem=f"duplicate key {key!r}",
                problem_mark=mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_NoDuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


@dataclass(frozen=True)
class ParsedMarkdown:
    """A markdown file split into frontmatter and body."""

    path: Path
    data: dict[str, Any]
    body: str
    #: 1-based line number of the first body line, used to report body offsets
    #: in terms the author sees in their editor.
    body_start_line: int
    raw: str

    @property
    def body_line_count(self) -> int:
        """Number of body lines, ignoring a single trailing newline."""
        if not self.body:
            return 0
        return len(self.body.rstrip("\n").splitlines())


def split(text: str, path: Path) -> tuple[str, str, int]:
    """Split ``text`` into (frontmatter YAML, body, 1-based body start line)."""
    if text.startswith("﻿"):
        raise FrontmatterError(
            "file starts with a UTF-8 BOM; frontmatter must be the very first bytes. "
            "Re-save the file as UTF-8 without BOM.",
            path,
            1,
        )

    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        raise FrontmatterError(
            f"missing opening {FENCE!r} fence; a SKILL.md must begin with YAML frontmatter",
            path,
            1,
        )

    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == FENCE:
            closing_index = index
            break

    if closing_index is None:
        raise FrontmatterError(
            f"opening {FENCE!r} fence is never closed; add a {FENCE!r} line after the "
            "last frontmatter field",
            path,
            1,
        )

    front = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :])
    return front, body, closing_index + 2


def parse_text(text: str, path: Path) -> ParsedMarkdown:
    """Parse frontmatter out of ``text``. See :func:`parse_file`."""
    front, body, body_start_line = split(text, path)

    try:
        loaded = yaml.load(front, Loader=_NoDuplicateKeyLoader)  # noqa: S506 - custom SafeLoader
    except yaml.MarkedYAMLError as exc:
        # Marks are relative to the frontmatter block; +1 for the opening fence.
        line = (exc.problem_mark.line + 2) if exc.problem_mark else None
        raise FrontmatterError(f"invalid YAML: {exc.problem or exc}", path, line) from exc
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid YAML: {exc}", path) from exc

    if loaded is None:
        raise FrontmatterError("frontmatter block is empty", path, 1)
    if not isinstance(loaded, dict):
        raise FrontmatterError(
            f"frontmatter must be a mapping of fields, got {type(loaded).__name__}", path, 1
        )

    non_string_keys = [key for key in loaded if not isinstance(key, str)]
    if non_string_keys:
        raise FrontmatterError(
            f"frontmatter keys must be strings, got {non_string_keys!r}", path, 1
        )

    return ParsedMarkdown(
        path=path, data=loaded, body=body, body_start_line=body_start_line, raw=text
    )


def parse_file(path: Path) -> ParsedMarkdown:
    """Read and parse ``path``.

    Raises:
        FrontmatterError: if the file cannot be read or has no valid
            frontmatter mapping.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FrontmatterError("file does not exist", path) from exc
    except UnicodeDecodeError as exc:
        raise FrontmatterError(f"file is not valid UTF-8: {exc}", path) from exc
    return parse_text(text, path)
