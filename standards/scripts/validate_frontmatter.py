#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.23", "pyyaml>=6.0.2"]
# ///
"""Validate SKILL.md frontmatter against the spec and CRV governance rules.

Repo tooling, not a skill-bundled script: it may use dependencies, and it is
run with ``uv run``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import cli, log  # noqa: E402
from lib.discovery import LAYERS, Skill, discover, repo_root, resolve_targets  # noqa: E402
from lib.frontmatter import FrontmatterError, parse_file  # noqa: E402

LOGGER = log.get_logger("validate-frontmatter")

DEFAULT_SCHEMA = Path("standards/schemas/skill-frontmatter-v1.schema.json")

#: Fields the Agent Skills specification defines. The set is closed.
SPEC_FIELDS = ("name", "description", "license", "compatibility", "metadata", "allowed-tools")

#: Keys we expect people to reach for, with the reason they are wrong here.
KNOWN_BAD_FIELDS = {
    "version": (
        "`version` is not a frontmatter field. Move it under `metadata:` and quote it "
        '(metadata.version: "1.0.0").'
    ),
    "author": "Put `author` under `metadata:`, or use `metadata.owner` for the accountable team.",
    "tags": "Put `tags` under `metadata:` as a comma-separated string.",
    "owner": "Put `owner` under `metadata:`.",
    "model": "There is no `model` field in the Agent Skills specification.",
    "tools": "The field is `allowed-tools`, a single space-separated string.",
    "allowed_tools": "The field is spelled `allowed-tools`, with a hyphen.",
    "disable-model-invocation": (
        "Forbidden in v1. It is not a specification field, and Claude Code rejects "
        "unexpected frontmatter keys when packaging a skill. If a skill should not be "
        "auto-selected, say so in the description instead."
    ),
    "argument-hint": "Not a specification field; that is Claude Code slash-command frontmatter.",
    "when-to-use": "Fold this into `description`, which is what harnesses actually read.",
}

TRIGGER_HINTS = ("use when", "use this when", "invoke when", "apply when", "when the user")

MIN_USEFUL_DESCRIPTION = 60

# Anchored so that a repo-relative path such as `standards/scripts/foo.py` is not
# mistaken for a bundled `scripts/foo.py` inside the skill directory.
REFERENCE_PATTERN = r"(?<![A-Za-z0-9._/-])(?:scripts|references|assets|evals)/[A-Za-z0-9._\-/]+"


@dataclass
class Finding:
    """One problem, addressed to whoever has to fix it."""

    level: str  # "error" | "warning"
    code: str
    path: str
    message: str
    line: Union[int, None] = None
    hint: Union[str, None] = None

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
        prog="validate_frontmatter.py",
        description=(
            "Validate every SKILL.md against standards/schemas/skill-frontmatter-v1.schema.json "
            "and against the filesystem rules the schema cannot express (name must equal the "
            "directory, metadata.layer must equal the parent directory, referenced files must "
            "exist). Writes a JSON report to stdout; all diagnostics go to stderr."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  # validate everything\n"
            "  uv run standards/scripts/validate_frontmatter.py\n\n"
            "  # validate one skill, by directory or by SKILL.md path\n"
            "  uv run standards/scripts/validate_frontmatter.py skills/processes/crv-create-skill\n\n"
            "  # only the processes layer, warnings promoted to errors\n"
            "  uv run standards/scripts/validate_frontmatter.py --layer processes --strict\n\n"
            "  # write the report to a file instead of stdout\n"
            "  uv run standards/scripts/validate_frontmatter.py --output report.json\n\n"
            + cli.EXIT_CODE_HELP
        ),
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Skill directories or SKILL.md paths. Default: every skill in the repository.",
    )
    parser.add_argument("--root", type=Path, default=None, help="Repository root (default: auto-detected).")
    parser.add_argument(
        "--layer",
        action="append",
        choices=list(LAYERS),
        help="Restrict to a layer. Repeatable.",
    )
    parser.add_argument("--schema", type=Path, default=None, help=f"Schema path (default: {DEFAULT_SCHEMA}).")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    parser.add_argument("--output", type=Path, default=None, help="Write the JSON report here instead of stdout.")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    parser.add_argument("--quiet", action="store_true", help="Only warnings and errors on stderr.")
    return parser


def load_schema(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(_fail(cli.EXIT_INPUT, f"schema not found: {path}")) from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(_fail(cli.EXIT_MALFORMED, f"schema is not valid JSON: {path}: {exc}")) from exc


def _fail(code: int, message: str) -> int:
    LOGGER.error(message)
    return code


def _schema_path_label(error: Any) -> str:
    parts = [str(p) for p in error.absolute_path]
    return ".".join(parts) if parts else "(root)"


def check_schema(skill: Skill, data: dict[str, Any], schema: dict[str, Any], report: Report) -> None:
    """Run JSON Schema validation, then re-explain the errors in author terms."""
    import jsonschema

    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        location = _schema_path_label(error)
        if error.validator == "additionalProperties" and not error.absolute_path:
            for key in sorted(set(data) - set(SPEC_FIELDS)):
                report.error(
                    code="frontmatter.unknown-field",
                    path=skill.rel_skill_md,
                    message=(
                        f"unknown frontmatter field {key!r}. The Agent Skills field set is "
                        f"closed: {', '.join(SPEC_FIELDS)}."
                    ),
                    hint=KNOWN_BAD_FIELDS.get(key),
                )
            continue
        report.error(
            code="frontmatter.schema",
            path=skill.rel_skill_md,
            message=f"{location}: {error.message}",
            hint=error.schema.get("description") if isinstance(error.schema, dict) else None,
        )


def check_filesystem_agreement(skill: Skill, data: dict[str, Any], report: Report) -> None:
    """The two rules that a schema cannot see: name and layer must match the path."""
    name = data.get("name")
    if isinstance(name, str) and name != skill.name:
        report.error(
            code="frontmatter.name-directory-mismatch",
            path=skill.rel_skill_md,
            message=f"name is {name!r} but the directory is {skill.name!r}; the spec requires them to be equal",
            hint=f"Either rename the directory to {name!r} or set name to {skill.name!r}.",
        )

    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        layer = metadata.get("layer")
        if isinstance(layer, str) and layer != skill.layer:
            report.error(
                code="frontmatter.layer-directory-mismatch",
                path=skill.rel_skill_md,
                message=(
                    f"metadata.layer is {layer!r} but the skill lives under skills/{skill.layer}/"
                ),
                hint=(
                    f"Either move the skill to skills/{layer}/ or set metadata.layer to "
                    f"{skill.layer!r}. See skills/README.md for what each layer means."
                ),
            )


def check_description_quality(skill: Skill, data: dict[str, Any], report: Report) -> None:
    """Heuristics on the one string that decides whether the skill is ever used."""
    description = data.get("description")
    if not isinstance(description, str):
        return
    lowered = description.lower()

    if len(description) < MIN_USEFUL_DESCRIPTION:
        report.warn(
            code="description.too-short",
            path=skill.rel_skill_md,
            message=(
                f"description is {len(description)} characters; short descriptions lose "
                "selection races against more specific skills"
            ),
            hint="State what it does and the concrete situations that should trigger it.",
        )

    if not any(hint in lowered for hint in TRIGGER_HINTS):
        report.warn(
            code="description.no-trigger",
            path=skill.rel_skill_md,
            message="description does not say when to use the skill",
            hint="Add an explicit trigger clause, e.g. 'Use when ...'.",
        )

    if lowered.startswith(("this skill", "a skill", "the skill")):
        report.warn(
            code="description.self-referential",
            path=skill.rel_skill_md,
            message="description opens by describing itself as a skill, which spends the "
            "most valuable words saying nothing",
            hint="Open with the verb: 'Extracts ...', 'Produces ...', 'Validates ...'.",
        )


def check_repo_conventions(skill: Skill, data: dict[str, Any], report: Report) -> None:
    if "license" not in data:
        report.warn(
            code="convention.missing-license",
            path=skill.rel_skill_md,
            message="no license field; skills are copied out of this repository and lose their context",
            hint="Add `license: Apache-2.0`.",
        )
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and metadata.get("maturity") == "deprecated":
        body = (skill.skill_md.read_text(encoding="utf-8")).lower()
        if "deprecat" not in body.split("---", 2)[-1]:
            report.warn(
                code="convention.deprecated-without-notice",
                path=skill.rel_skill_md,
                message="maturity is deprecated but the body never says so",
                hint="Open the body with a deprecation notice naming the replacement.",
            )


def check_references(skill: Skill, body: str, body_start_line: int, report: Report) -> None:
    """Every bundled path the body mentions must exist, and must be shallow."""
    import re

    seen: set[str] = set()
    for match in re.finditer(REFERENCE_PATTERN, body):
        raw = match.group(0).rstrip(".,;:)`\"'")
        if raw in seen:
            continue
        seen.add(raw)
        line = body_start_line + body[: match.start()].count("\n")
        target = skill.path / raw
        if not target.exists():
            report.error(
                code="reference.missing",
                path=skill.rel_skill_md,
                line=line,
                message=f"referenced path {raw!r} does not exist in the skill directory",
                hint="Create the file, or remove the reference. A dangling pointer costs the "
                "agent a failed tool call and then an improvisation.",
            )
            continue
        depth = len(Path(raw).parts)
        if depth > 2 and target.is_file():
            report.warn(
                code="reference.too-deep",
                path=skill.rel_skill_md,
                line=line,
                message=f"{raw!r} is {depth} levels deep; the spec asks for references one level from SKILL.md",
                hint="Flatten it, or point at the directory and let the agent list it.",
            )


def check_reference_chains(skill: Skill, report: Report) -> None:
    """A reference that references another reference is a chain the agent will not follow."""
    import re

    for reference in skill.reference_files():
        text = reference.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"references/[A-Za-z0-9._\-/]+\.md", text):
            report.warn(
                code="reference.chained",
                path=reference.relative_to(skill.root).as_posix(),
                line=text[: match.start()].count("\n") + 1,
                message=f"reference file points at another reference file ({match.group(0)})",
                hint="Link from SKILL.md instead. Chained references get loaded late or not at all.",
            )
            break


def validate_skill(skill: Skill, schema: dict[str, Any], report: Report) -> None:
    LOGGER.debug("validating %s", skill.rel_skill_md)
    try:
        parsed = parse_file(skill.skill_md)
    except FrontmatterError as exc:
        report.error(
            code="frontmatter.unparseable",
            path=skill.rel_skill_md,
            line=exc.line,
            message=str(exc).split(": ", 1)[-1],
            hint="Frontmatter is a YAML mapping between two `---` lines, at the very top of the file.",
        )
        return

    check_schema(skill, parsed.data, schema, report)
    check_filesystem_agreement(skill, parsed.data, report)
    check_description_quality(skill, parsed.data, report)
    check_repo_conventions(skill, parsed.data, report)
    check_references(skill, parsed.body, parsed.body_start_line, report)
    check_reference_chains(skill, report)

    if not parsed.body.strip():
        report.error(
            code="body.empty",
            path=skill.rel_skill_md,
            message="the body is empty; frontmatter alone tells the agent nothing to do",
        )


def main(argv: Union[list[str], None] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log.configure(verbose=args.verbose, quiet=args.quiet)

    root = (args.root or repo_root()).resolve()
    if not (root / "skills").is_dir():
        return _fail(cli.EXIT_INPUT, f"no skills/ directory under {root}")

    schema_path = args.schema or (root / DEFAULT_SCHEMA)
    schema = load_schema(schema_path)

    report = Report()

    if args.targets:
        skills, unresolved = resolve_targets(root, args.targets)
        for target in unresolved:
            return _fail(
                cli.EXIT_INPUT,
                f"{target!r} is not a skill directory containing a SKILL.md under skills/<layer>/",
            )
        strays = []
    else:
        skills, strays = discover(root, layers=args.layer)

    for stray in strays:
        report.error(
            code="layout.stray",
            path=stray.path.relative_to(root).as_posix(),
            message=stray.reason,
        )

    for skill in skills:
        validate_skill(skill, schema, report)

    if args.strict:
        for finding in report.findings:
            finding.level = "error"

    payload = {
        "tool": "validate_frontmatter",
        "schema": schema_path.relative_to(root).as_posix()
        if schema_path.is_relative_to(root)
        else str(schema_path),
        "root": str(root),
        "skills_checked": len(skills),
        "summary": {
            "errors": len(report.errors),
            "warnings": len(report.warnings),
        },
        "findings": [f.as_dict() for f in report.findings],
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        LOGGER.info("report written to %s", args.output)
    else:
        cli.emit(payload)

    for finding in report.findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        line = f"{location}: [{finding.code}] {finding.message}"
        if finding.level == "error":
            LOGGER.error(line)
        else:
            LOGGER.warning(line)

    LOGGER.info(
        "%d skill(s) checked, %d error(s), %d warning(s)",
        len(skills),
        len(report.errors),
        len(report.warnings),
    )
    return cli.EXIT_FINDINGS if report.errors else cli.EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(cli.EXIT_INTERNAL)
