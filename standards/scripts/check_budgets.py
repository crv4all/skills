#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.23", "pyyaml>=6.0.2", "tiktoken>=0.8"]
# ///
"""Enforce context budgets on SKILL.md and reference files.

The budget is not about disk space. A SKILL.md is loaded in full the moment the
skill activates, and it competes for context with the user's actual task. A
skill that costs 12,000 tokens to consider is a skill that makes every other
skill in the session worse.

Severity depends on maturity: a draft warns, so authoring is never blocked by a
budget before the content exists; a stable skill fails, because other people
depend on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import cli, log
from lib.discovery import LAYERS, Skill, discover, repo_root, resolve_targets
from lib.frontmatter import FrontmatterError, parse_file

LOGGER = log.get_logger("check-budgets")

DEFAULT_CONFIG = Path("standards/configs/budgets.json")
DEFAULT_CONFIG_SCHEMA = Path("standards/schemas/budgets-config-v1.schema.json")


@dataclass
class Measurement:
    lines: int
    characters: int
    tokens: Union[int, None]
    tokens_estimated: bool


@dataclass
class Finding:
    level: str
    code: str
    path: str
    message: str
    hint: Union[str, None] = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "level": self.level,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }
        if self.hint:
            payload["hint"] = self.hint
        return payload


class Tokenizer:
    """Counts tokens, or explains honestly why it could not.

    ``cl100k_base`` is a yardstick, not a measurement: no harness publishes the
    tokenizer it actually uses in production. The number is comparable across
    our own skills over time, which is the only property a budget needs.
    """

    def __init__(self, encoding_name: str, on_unavailable: str, chars_per_token: int) -> None:
        self.encoding_name = encoding_name
        self.on_unavailable = on_unavailable
        self.chars_per_token = chars_per_token
        self._encoding: Any = None
        self.unavailable_reason: Union[str, None] = None
        try:
            import tiktoken

            self._encoding = tiktoken.get_encoding(encoding_name)
        except Exception as exc:
            self.unavailable_reason = f"{type(exc).__name__}: {exc}"
            LOGGER.warning(
                "tokenizer %s unavailable (%s); policy on-unavailable=%s",
                encoding_name,
                self.unavailable_reason,
                on_unavailable,
            )

    @property
    def available(self) -> bool:
        return self._encoding is not None

    def count(self, text: str) -> tuple[Union[int, None], bool]:
        """Return ``(tokens, estimated)``. ``(None, False)`` means not counted."""
        if self._encoding is not None:
            return len(self._encoding.encode(text, disallowed_special=())), False
        if self.on_unavailable == "estimate":
            return max(1, round(len(text) / self.chars_per_token)), True
        return None, False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_budgets.py",
        description=(
            "Measure every SKILL.md against the line, character, and token budgets in "
            "standards/configs/budgets.json, and every references/*.md against the soft "
            "line budget. Writes a JSON report to stdout; diagnostics go to stderr."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  uv run standards/scripts/check_budgets.py\n"
            "  uv run standards/scripts/check_budgets.py skills/processes/crv-create-skill\n"
            "  uv run standards/scripts/check_budgets.py --strict --output budgets.json\n\n"
            "notes:\n"
            "  Token counts use cl100k_base as a stable offline yardstick. They approximate\n"
            "  what a harness will charge, and are never presented as exact.\n\n"
            + cli.EXIT_CODE_HELP
        ),
    )
    parser.add_argument(
        "targets", nargs="*", help="Skill directories or SKILL.md paths. Default: all skills."
    )
    parser.add_argument(
        "--root", type=Path, default=None, help="Repository root (default: auto-detected)."
    )
    parser.add_argument(
        "--layer", action="append", choices=list(LAYERS), help="Restrict to a layer. Repeatable."
    )
    parser.add_argument(
        "--config", type=Path, default=None, help=f"Budget config (default: {DEFAULT_CONFIG})."
    )
    parser.add_argument("--strict", action="store_true", help="Treat every warning as an error.")
    parser.add_argument(
        "--output", type=Path, default=None, help="Write the JSON report here instead of stdout."
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    parser.add_argument("--quiet", action="store_true", help="Only warnings and errors on stderr.")
    return parser


def load_config(config_path: Path, schema_path: Path) -> dict[str, Any]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(_fail(cli.EXIT_INPUT, f"budget config not found: {config_path}")) from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            _fail(cli.EXIT_MALFORMED, f"budget config is not valid JSON: {exc}")
        ) from exc

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(_fail(cli.EXIT_INPUT, f"budget schema not found: {schema_path}")) from exc

    import jsonschema.validators

    validator_cls = jsonschema.validators.validator_for(schema)
    errors = sorted(validator_cls(schema).iter_errors(config), key=lambda e: list(e.absolute_path))
    if errors:
        for error in errors:
            location = ".".join(str(p) for p in error.absolute_path) or "(root)"
            LOGGER.error("%s: %s: %s", config_path, location, error.message)
        raise SystemExit(
            _fail(cli.EXIT_MALFORMED, "budget config does not satisfy its schema; refusing to run")
        )
    return config


def _fail(code: int, message: str) -> int:
    LOGGER.error(message)
    return code


def measure(path: Path, tokenizer: Tokenizer) -> Measurement:
    text = path.read_text(encoding="utf-8")
    tokens, estimated = tokenizer.count(text)
    return Measurement(
        lines=len(text.splitlines()),
        characters=len(text),
        tokens=tokens,
        tokens_estimated=estimated,
    )


def maturity_of(skill: Skill) -> str:
    """Read maturity, defaulting to the strictest interpretation we can justify.

    An unreadable or absent maturity is treated as ``draft`` rather than
    ``stable``: validate_frontmatter.py already fails the build for that, and
    reporting the same broken file twice with a scarier severity helps nobody.
    """
    try:
        parsed = parse_file(skill.skill_md)
    except FrontmatterError:
        return "draft"
    metadata = parsed.data.get("metadata")
    if isinstance(metadata, dict):
        maturity = metadata.get("maturity")
        if isinstance(maturity, str):
            return maturity
    return "draft"


def exempt(exemptions: list[dict[str, str]], rel_path: str, budget: str) -> Union[str, None]:
    for entry in exemptions:
        if entry["path"] == rel_path and entry["budget"] == budget:
            return entry["reason"]
    return None


def check_skill(
    skill: Skill,
    config: dict[str, Any],
    tokenizer: Tokenizer,
    findings: list[Finding],
) -> dict[str, Any]:
    budgets = config["skill-md"]
    severity = config["enforcement"].get(maturity_of(skill), "warn")
    exemptions = config.get("exemptions", [])
    rel = skill.rel_skill_md

    m = measure(skill.skill_md, tokenizer)
    checks = [
        ("max-lines", m.lines, budgets["max-lines"], "lines"),
        ("max-characters", m.characters, budgets["max-characters"], "characters"),
    ]
    if m.tokens is not None:
        checks.append(("max-tokens", m.tokens, budgets["max-tokens"], "tokens"))

    for budget_name, actual, limit, unit in checks:
        if actual <= limit:
            continue
        reason = exempt(exemptions, rel, budget_name)
        if reason:
            LOGGER.info("%s: %s exempt (%s)", rel, budget_name, reason)
            continue
        qualifier = " (estimated)" if unit == "tokens" and m.tokens_estimated else ""
        over = actual - limit
        findings.append(
            Finding(
                level="error" if severity == "error" else "warning",
                code=f"budget.skill-md.{budget_name}",
                path=rel,
                message=(
                    f"{actual}{qualifier} {unit}, budget is {limit} "
                    f"({over} over, maturity={maturity_of(skill)})"
                ),
                hint=(
                    "Move detail into references/. The body should carry the decisions and the "
                    "control flow; everything a reader consults only sometimes belongs in a file "
                    "loaded only sometimes."
                ),
            )
        )

    reference_report = []
    warn_lines = config["reference-files"]["warn-lines"]
    for reference in skill.reference_files():
        rel_reference = reference.relative_to(skill.root).as_posix()
        rm = measure(reference, tokenizer)
        reference_report.append(
            {
                "path": rel_reference,
                "lines": rm.lines,
                "characters": rm.characters,
                "tokens": rm.tokens,
            }
        )
        if rm.lines > warn_lines and not exempt(exemptions, rel_reference, "warn-lines"):
            findings.append(
                Finding(
                    level="warning",
                    code="budget.reference.warn-lines",
                    path=rel_reference,
                    message=f"{rm.lines} lines, soft budget is {warn_lines}",
                    hint="Split by topic. A reference file is loaded whole, on demand.",
                )
            )

    return {
        "skill": skill.name,
        "layer": skill.layer,
        "maturity": maturity_of(skill),
        "severity": severity,
        "skill_md": {
            "path": rel,
            "lines": m.lines,
            "characters": m.characters,
            "tokens": m.tokens,
            "tokens_estimated": m.tokens_estimated,
        },
        "references": reference_report,
    }


def main(argv: Union[list[str], None] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log.configure(verbose=args.verbose, quiet=args.quiet)

    root = (args.root or repo_root()).resolve()
    config_path = args.config or (root / DEFAULT_CONFIG)
    config = load_config(config_path, root / DEFAULT_CONFIG_SCHEMA)

    tokenizer_config = config["tokenizer"]
    tokenizer = Tokenizer(
        encoding_name=tokenizer_config["encoding"],
        on_unavailable=tokenizer_config["on-unavailable"],
        chars_per_token=tokenizer_config.get("estimate-characters-per-token", 4),
    )
    if not tokenizer.available and tokenizer_config["on-unavailable"] == "error":
        return _fail(
            cli.EXIT_INTERNAL,
            f"tokenizer {tokenizer.encoding_name} unavailable and policy is 'error': "
            f"{tokenizer.unavailable_reason}",
        )

    if args.targets:
        skills, unresolved = resolve_targets(root, args.targets)
        if unresolved:
            return _fail(cli.EXIT_INPUT, f"not a skill directory: {unresolved[0]!r}")
    else:
        skills, _ = discover(root, layers=args.layer)

    findings: list[Finding] = []
    measurements = [check_skill(skill, config, tokenizer, findings) for skill in skills]

    if args.strict:
        for finding in findings:
            finding.level = "error"

    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]

    payload = {
        "tool": "check_budgets",
        "config": config_path.relative_to(root).as_posix()
        if config_path.is_relative_to(root)
        else str(config_path),
        "tokenizer": {
            "encoding": tokenizer.encoding_name,
            "available": tokenizer.available,
            "policy_on_unavailable": tokenizer.on_unavailable,
            "unavailable_reason": tokenizer.unavailable_reason,
        },
        "skills_checked": len(skills),
        "summary": {"errors": len(errors), "warnings": len(warnings)},
        "measurements": measurements,
        "findings": [f.as_dict() for f in findings],
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        LOGGER.info("report written to %s", args.output)
    else:
        cli.emit(payload)

    for finding in findings:
        message = f"{finding.path}: [{finding.code}] {finding.message}"
        if finding.level == "error":
            LOGGER.error(message)
        else:
            LOGGER.warning(message)

    LOGGER.info(
        "%d skill(s) measured, %d error(s), %d warning(s)", len(skills), len(errors), len(warnings)
    )
    return cli.EXIT_FINDINGS if errors else cli.EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(cli.EXIT_INTERNAL)
