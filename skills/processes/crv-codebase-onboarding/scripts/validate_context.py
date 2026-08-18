#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Check generated docs/codebase/ output against the contract.

The validation loop in SKILL.md lists checks that are mechanical: does the file
exist, does the stamp match, does that path resolve, is there template text
left. Mechanical checks belong in a script -- an agent asked to verify forty
paths by eye will verify some of them and report all of them as verified.

Path verification is the reason this exists. Fabricated file paths are the
characteristic failure of codebase documentation: each one is individually
plausible, and a reader who finds one stops trusting the whole document.

Read-only. Stdlib only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger("crv.validate-context")

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EXIT_CODE_HELP = """exit codes:
  0  contract satisfied
  1  contract violations found
  2  usage error
  3  docs/codebase/ not found
  4  a required file could not be read
  5  internal error
"""

REQUIRED_FILES = (
    "README.md",
    "ARCHITECTURE.md",
    "STACK.md",
    "CONVENTIONS.md",
    "WORKFLOWS.md",
    "DATA.md",
    "INTEGRATIONS.md",
    "TESTING.md",
)
CONDITIONAL_FILES = ("DOMAIN.md", "CONCERNS.md")

STAMP_PATTERN = re.compile(
    r"^>\s*verified against\s+([0-9a-f]{7,40})\s+on\s+(\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)

#: Text that only appears if a template was copied and not filled in.
TEMPLATE_SIGNALS = (
    "<!-- EXAMPLE",
    "<full-40-char-sha>",
    "<YYYY-MM-DD>",
    "<one line>",
    "<placeholder>",
    "Replace every",
    "delete every EXAMPLE",
)

PLACEHOLDER_PATTERN = re.compile(r"<[a-z][a-z0-9 /|._-]{2,40}>")

#: Inline-code spans that look like repository paths.
PATH_PATTERN = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./\-]*\.[A-Za-z0-9]{1,10}(?::\d+(?:-\d+)?)?)`")

#: Markdown links to files inside the repository.
LINK_PATTERN = re.compile(r"\]\(([^)#\s]+)\)")

MARKER_PATTERN = re.compile(r"\[(TODO|ASK USER)\]([^\n]*)")

SECRET_PATTERN = re.compile(
    r"(?i)\b(?:password|secret|api[_-]?key|token|client[_-]?secret|connection[_-]?string)"
    r"\s*[:=]\s*[\"']?[^\s\"'<${}|]{8,}"
)

MERMAID_FENCE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
MERMAID_TYPES = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "journey",
    "gantt",
    "C4Context",
    "C4Container",
    "mindmap",
    "timeline",
    "block-beta",
)

#: Words that look like file paths in prose but are not repository files.
PATH_IGNORE_PREFIXES = ("http://", "https://", "mailto:", "e.g.", "i.e.")


@dataclass
class Finding:
    level: str
    code: str
    path: str
    message: str
    line: Optional[int] = None
    hint: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "level": self.level,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }
        if self.line is not None:
            payload["line"] = self.line
        if self.hint:
            payload["hint"] = self.hint
        return payload


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    markers: list[dict[str, str]] = field(default_factory=list)
    stamps: dict[str, Optional[str]] = field(default_factory=dict)
    paths_checked: int = 0

    def error(self, **kwargs: Any) -> None:
        self.findings.append(Finding(level="error", **kwargs))

    def warn(self, **kwargs: Any) -> None:
        self.findings.append(Finding(level="warning", **kwargs))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "warning"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_context.py",
        description=(
            "Validate generated codebase context against the crv-codebase-onboarding "
            "output contract: required files, consistent stamps, resolvable paths, no "
            "leftover template text, no secret values, parseable Mermaid. JSON on "
            "stdout, diagnostics on stderr. Read-only."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 validate_context.py --root .\n"
            "  python3 validate_context.py --root ../service --expect-sha 4f9c2a1e\n"
            "  python3 validate_context.py --root . --output contract.json\n\n"
            "notes:\n"
            "  A conditional file (DOMAIN.md, CONCERNS.md) that is absent is fine only if\n"
            "  README.md explains the omission. Silence is treated as a forgotten step.\n\n"
            + EXIT_CODE_HELP
        ),
    )
    parser.add_argument(
        "--root", type=Path, default=Path(), help="Repository root (default: current directory)."
    )
    parser.add_argument(
        "--context-dir",
        type=Path,
        default=None,
        help="Context directory (default: <root>/docs/codebase).",
    )
    parser.add_argument(
        "--expect-sha",
        default=None,
        help="Require every stamp to name this commit. Accepts a prefix.",
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    parser.add_argument(
        "--output", type=Path, default=None, help="Write the JSON report here instead of stdout."
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    parser.add_argument("--quiet", action="store_true", help="Only warnings and errors on stderr.")
    return parser


def configure_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    LOGGER.handlers = [handler]
    LOGGER.setLevel(level)
    LOGGER.propagate = False


def check_stamp(name: str, text: str, expect_sha: Optional[str], report: Report) -> None:
    match = STAMP_PATTERN.search(text)
    if not match:
        report.error(
            code="stamp.missing",
            path=name,
            message="no `> verified against <sha> on <date>` line",
            hint=(
                "Context that cannot be dated cannot be distinguished from context that "
                "has gone stale."
            ),
        )
        report.stamps[name] = None
        return

    sha, date = match.group(1), match.group(2)
    report.stamps[name] = sha
    if len(sha) < 40:
        report.warn(
            code="stamp.short-sha",
            path=name,
            message=f"stamp uses a {len(sha)}-character SHA; the contract asks for the full 40",
            hint=(
                "Short SHAs collide as history grows, and a stamp that no longer "
                "resolves is worthless."
            ),
        )
    if expect_sha and not sha.startswith(expect_sha) and not expect_sha.startswith(sha):
        report.error(
            code="stamp.wrong-sha",
            path=name,
            message=f"stamp names {sha} but --expect-sha is {expect_sha}",
        )
    if not re.match(r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$", date):
        report.error(code="stamp.bad-date", path=name, message=f"{date!r} is not a valid ISO date")


def check_template_residue(name: str, text: str, report: Report) -> None:
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        for signal in TEMPLATE_SIGNALS:
            if signal in line:
                report.error(
                    code="template.residue",
                    path=name,
                    line=index,
                    message=f"leftover template text: {signal!r}",
                    hint="Nothing from assets/templates/ may survive into the written file.",
                )
                break
        else:
            placeholder = PLACEHOLDER_PATTERN.search(line)
            if placeholder and not line.lstrip().startswith(("<!--", "-->")):
                report.warn(
                    code="template.placeholder",
                    path=name,
                    line=index,
                    message=f"unfilled placeholder {placeholder.group(0)!r}",
                )


def check_paths(name: str, text: str, root: Path, report: Report) -> None:
    """Every repository path the document names must exist."""
    seen: set[str] = set()

    def verify(raw: str, line: int, kind: str) -> None:
        candidate = raw.split(":", 1)[0].strip()
        if not candidate or candidate in seen:
            return
        if candidate.startswith(PATH_IGNORE_PREFIXES):
            return
        seen.add(candidate)
        report.paths_checked += 1
        if (root / candidate).exists():
            return
        report.error(
            code=f"path.missing.{kind}",
            path=name,
            line=line,
            message=f"{candidate!r} does not exist in the repository",
            hint="A plausible path that does not exist is worse than no path: it will be followed.",
        )

    for index, line in enumerate(text.splitlines(), start=1):
        for match in PATH_PATTERN.finditer(line):
            verify(match.group(1), index, "citation")
        for match in LINK_PATTERN.finditer(line):
            target = match.group(1)
            if target.startswith(PATH_IGNORE_PREFIXES) or target.startswith("<"):
                continue
            # Links inside docs/codebase/ are relative to that directory.
            local = root / "docs" / "codebase" / target
            if local.exists() or (root / target).exists():
                report.paths_checked += 1
                continue
            report.error(
                code="path.missing.link",
                path=name,
                line=index,
                message=f"link target {target!r} does not resolve",
            )


def check_secrets(name: str, text: str, report: Report) -> None:
    for index, line in enumerate(text.splitlines(), start=1):
        match = SECRET_PATTERN.search(line)
        if match:
            report.error(
                code="secret.value",
                path=name,
                line=index,
                message="a credential-shaped assignment appears in generated context",
                hint="Report environment variable names and reference sites only, never values.",
            )


def check_mermaid(name: str, text: str, report: Report) -> None:
    for match in MERMAID_FENCE.finditer(text):
        line = text[: match.start()].count("\n") + 1
        body = match.group(1).strip()
        if not body:
            report.error(code="mermaid.empty", path=name, line=line, message="empty mermaid block")
            continue
        first = body.splitlines()[0].strip()
        if not first.startswith(MERMAID_TYPES):
            report.error(
                code="mermaid.unknown-type",
                path=name,
                line=line,
                message=f"mermaid block starts with {first!r}, which is not a diagram type",
                hint=f"Expected one of: {', '.join(MERMAID_TYPES[:6])}, ...",
            )
            continue
        opens = body.count("[") + body.count("(") + body.count("{")
        closes = body.count("]") + body.count(")") + body.count("}")
        if opens != closes:
            report.error(
                code="mermaid.unbalanced",
                path=name,
                line=line,
                message=f"unbalanced brackets in mermaid block ({opens} opening, {closes} closing)",
            )


def collect_markers(name: str, text: str, report: Report) -> None:
    for index, line in enumerate(text.splitlines(), start=1):
        for match in MARKER_PATTERN.finditer(line):
            report.markers.append(
                {
                    "marker": match.group(1),
                    "path": name,
                    "line": str(index),
                    "text": match.group(2).strip(),
                }
            )


def check_conditionals(context_dir: Path, readme_text: str, report: Report) -> None:
    for name in CONDITIONAL_FILES:
        if (context_dir / name).exists():
            continue
        if name in readme_text:
            continue
        report.error(
            code="contract.unexplained-omission",
            path="README.md",
            message=f"{name} was not written and README.md never mentions it",
            hint="A missing file nobody explains is indistinguishable from a forgotten step.",
        )


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose, args.quiet)

    root = args.root.expanduser()
    if not root.is_dir():
        LOGGER.error("root does not exist or is not a directory: %s", root)
        return EXIT_INPUT
    root = root.resolve()

    context_dir = (args.context_dir or (root / "docs" / "codebase")).resolve()
    if not context_dir.is_dir():
        LOGGER.error(
            "no context directory at %s; run the onboarding skill before validating", context_dir
        )
        return EXIT_INPUT

    report = Report()
    present: list[str] = []

    for name in REQUIRED_FILES + CONDITIONAL_FILES:
        path = context_dir / name
        if not path.is_file():
            if name in REQUIRED_FILES:
                report.error(
                    code="contract.missing-file",
                    path=name,
                    message="required file is missing from docs/codebase/",
                )
            continue
        present.append(name)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            LOGGER.error("cannot read %s: %s", path, exc)
            return EXIT_MALFORMED

        check_stamp(name, text, args.expect_sha, report)
        check_template_residue(name, text, report)
        check_paths(name, text, root, report)
        check_secrets(name, text, report)
        check_mermaid(name, text, report)
        collect_markers(name, text, report)

    readme = context_dir / "README.md"
    if readme.is_file():
        check_conditionals(context_dir, readme.read_text(encoding="utf-8"), report)

    distinct_stamps = {sha for sha in report.stamps.values() if sha}
    if len(distinct_stamps) > 1:
        report.error(
            code="stamp.inconsistent",
            path="docs/codebase/",
            message=(
                f"files are stamped with {len(distinct_stamps)} different SHAs: "
                f"{sorted(distinct_stamps)}"
            ),
            hint="Every file in the set is verified at one commit. Restamp them all.",
        )

    if args.strict:
        for finding in report.findings:
            finding.level = "error"

    payload = {
        "tool": "crv-validate-context",
        "root": str(root),
        "context_dir": str(context_dir),
        "files_present": present,
        "files_missing": [n for n in REQUIRED_FILES if n not in present],
        "stamp_sha": sorted(distinct_stamps)[0] if len(distinct_stamps) == 1 else None,
        "paths_checked": report.paths_checked,
        "markers": report.markers,
        "summary": {"errors": len(report.errors), "warnings": len(report.warnings)},
        "findings": [f.as_dict() for f in report.findings],
    }

    document = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
        LOGGER.info("report written to %s", args.output)
    else:
        sys.stdout.write(document)
        sys.stdout.flush()

    for finding in report.findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        message = f"{location}: [{finding.code}] {finding.message}"
        if finding.level == "error":
            LOGGER.error(message)
        else:
            LOGGER.warning(message)

    for marker in report.markers:
        LOGGER.info(
            "[%s] %s:%s %s", marker["marker"], marker["path"], marker["line"], marker["text"]
        )

    LOGGER.info(
        "%d file(s), %d path(s) checked, %d error(s), %d warning(s)",
        len(present),
        report.paths_checked,
        len(report.errors),
        len(report.warnings),
    )
    return EXIT_FINDINGS if report.errors else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(EXIT_INTERNAL)
