#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Scaffold a new skill directory in the CRV agent-skills repository.

Creates the directory, renders the templates in ``assets/skill-template/``, and
stops. It does not write the body -- that is the part that requires judgement,
and a generated body is filler in the most expensive file in the skill.

Deliberately conservative about writing: the default is a dry run, an existing
file is never overwritten without ``--force``, and re-running is safe. An agent
that has to guess whether a scaffold step already ran will run it again, so
running it again has to be harmless.

Stdlib only, Python 3.9+, so it runs as ``python3 scaffold.py`` on stock macOS.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger("crv.scaffold")

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EXIT_CODE_HELP = """exit codes:
  0  success (including a dry run that would succeed)
  1  refused: a target file exists and --force was not given
  2  usage error (bad name, unknown layer, missing required argument)
  3  the repository or the template directory could not be found
  4  a template file is unreadable
  5  internal error
"""

LAYERS = ("utilities", "knowledge", "patterns", "processes")

#: Mirrors standards/schemas/skill-frontmatter-v1.schema.json. Kept as a literal
#: rather than read from the schema so the script works from a copied skill
#: directory with no repository around it.
NAME_PATTERN = re.compile(r"^crv-[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,98}[A-Za-z0-9]$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scaffold.py",
        description=(
            "Create the directory and starting files for a new CRV skill. Prints a JSON "
            "plan to stdout and diagnostics to stderr. Writes nothing unless --confirm "
            "is given."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  # see the plan, write nothing (the default)\n"
            "  python3 scaffold.py --repo ~/src/agent-skills --name crv-dbt-model \\\n"
            "      --layer patterns --owner cloudforce-team-data \\\n"
            "      --description 'Builds dbt models to CRV conventions. Use when ...'\n\n"
            "  # actually write it\n"
            "  python3 scaffold.py ... --confirm\n\n"
            "  # add a scripts/ directory too\n"
            "  python3 scaffold.py ... --with-scripts --confirm\n\n"
            "after scaffolding:\n"
            "  uv run standards/scripts/validate_frontmatter.py skills/<layer>/<name>\n"
            "  uv run standards/scripts/check_budgets.py skills/<layer>/<name>\n"
            "  uv run standards/scripts/build_catalog.py --write\n\n" + EXIT_CODE_HELP
        ),
    )
    parser.add_argument(
        "--repo", type=Path, required=True, help="Path to the agent-skills repository root."
    )
    parser.add_argument(
        "--name", required=True, help="Skill name, including the mandatory crv- prefix."
    )
    parser.add_argument("--layer", required=True, choices=list(LAYERS), help="Capability layer.")
    parser.add_argument(
        "--owner", required=True, help="Accountable team, written to metadata.owner."
    )
    parser.add_argument(
        "--description",
        required=True,
        help="Frontmatter description. Say what it does AND when to use it.",
    )
    parser.add_argument(
        "--title", default=None, help="H1 for the body (default: derived from --name)."
    )
    parser.add_argument(
        "--templates",
        type=Path,
        default=None,
        help="Template directory (default: ../assets/skill-template next to this script).",
    )
    parser.add_argument(
        "--with-scripts", action="store_true", help="Also create scripts/ with a .gitkeep."
    )
    parser.add_argument(
        "--with-assets", action="store_true", help="Also create assets/ with a .gitkeep."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually write. Without it, the script only prints the plan.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly request a dry run. This is already the default; the flag exists so "
        "the intent can be stated in a command line that a human will read.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite files that already exist.")
    parser.add_argument(
        "--output", type=Path, default=None, help="Write the JSON plan here instead of stdout."
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


def validate_arguments(args: argparse.Namespace) -> Optional[str]:
    """Return an error message, or None. Fail before touching the filesystem."""
    if args.confirm and args.dry_run:
        return "--confirm and --dry-run contradict each other; pick one"
    if len(args.name) > MAX_NAME:
        return f"--name is {len(args.name)} characters; the specification allows {MAX_NAME}"
    if not NAME_PATTERN.match(args.name):
        return (
            f"--name {args.name!r} is not valid. It must start with 'crv-', then lowercase "
            "letters, digits, and single hyphens: crv-create-skill, crv-dbt-model. The "
            "crv- prefix is mandatory because harnesses ship built-in skills with generic "
            "names and do not merge collisions."
        )
    if len(args.description) > MAX_DESCRIPTION:
        return (
            f"--description is {len(args.description)} characters; the specification "
            f"allows {MAX_DESCRIPTION}"
        )
    if not args.description.strip():
        return "--description must not be empty"
    if not OWNER_PATTERN.match(args.owner):
        return f"--owner {args.owner!r} should be a team or list name, 2-100 characters"
    return None


def title_from_name(name: str) -> str:
    return name[len("crv-") :].replace("-", " ").capitalize()


def render(text: str, substitutions: dict[str, str]) -> str:
    for key, value in substitutions.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def plan_files(
    templates: Path, skill_dir: Path, substitutions: dict[str, str], args: argparse.Namespace
) -> list[tuple[Path, Optional[Path]]]:
    """Return (destination, template-or-None) pairs. None means an empty file."""
    files: list[tuple[Path, Optional[Path]]] = [
        (skill_dir / "SKILL.md", templates / "SKILL.md.template"),
        (skill_dir / "references" / "README.md", templates / "references" / "README.md.template"),
        (skill_dir / "evals" / "triggers.md", templates / "evals" / "triggers.md.template"),
        (skill_dir / "evals" / "behaviour.md", templates / "evals" / "behaviour.md.template"),
        (skill_dir / "evals" / "results.md", templates / "evals" / "results.md.template"),
    ]
    if args.with_scripts:
        files.append((skill_dir / "scripts" / ".gitkeep", None))
    if args.with_assets:
        files.append((skill_dir / "assets" / ".gitkeep", None))
    return files


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose, args.quiet)

    problem = validate_arguments(args)
    if problem:
        LOGGER.error("%s", problem)
        return EXIT_USAGE

    repo = args.repo.expanduser()
    if not repo.is_dir():
        LOGGER.error("repository not found: %s", repo)
        return EXIT_INPUT
    repo = repo.resolve()
    if not (repo / "skills").is_dir():
        LOGGER.error("%s has no skills/ directory; is this the agent-skills repository?", repo)
        return EXIT_INPUT

    templates = (
        args.templates or (Path(__file__).resolve().parent.parent / "assets" / "skill-template")
    ).resolve()
    if not templates.is_dir():
        LOGGER.error("template directory not found: %s", templates)
        return EXIT_INPUT

    skill_dir = repo / "skills" / args.layer / args.name
    substitutions = {
        "NAME": args.name,
        "LAYER": args.layer,
        "OWNER": args.owner,
        "DESCRIPTION": " ".join(args.description.split()),
        "TITLE": args.title or title_from_name(args.name),
    }

    planned = plan_files(templates, skill_dir, substitutions, args)

    actions: list[dict[str, str]] = []
    conflicts: list[str] = []
    for destination, template in planned:
        rel = destination.relative_to(repo).as_posix()
        if destination.exists() and not args.force:
            conflicts.append(rel)
            actions.append(
                {"path": rel, "action": "skip", "reason": "exists; pass --force to overwrite"}
            )
            continue
        if template is not None and not template.is_file():
            LOGGER.error("template missing: %s", template)
            return EXIT_MALFORMED
        actions.append(
            {
                "path": rel,
                "action": "overwrite" if destination.exists() else "create",
                "from": template.name if template else "(empty file)",
            }
        )

    existing_elsewhere = [
        layer
        for layer in LAYERS
        if layer != args.layer and (repo / "skills" / layer / args.name).is_dir()
    ]

    written: list[str] = []
    if args.confirm and not (conflicts and not args.force):
        for destination, template in planned:
            if destination.exists() and not args.force:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if template is None:
                destination.write_text("", encoding="utf-8")
            else:
                try:
                    body = template.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    LOGGER.error("cannot read template %s: %s", template, exc)
                    return EXIT_MALFORMED
                destination.write_text(render(body, substitutions), encoding="utf-8")
            written.append(destination.relative_to(repo).as_posix())

    payload = {
        "tool": "crv-scaffold-skill",
        "mode": "write" if args.confirm else "dry-run",
        "repo": str(repo),
        "skill_dir": skill_dir.relative_to(repo).as_posix(),
        "name": args.name,
        "layer": args.layer,
        "owner": args.owner,
        "actions": actions,
        "written": written,
        "conflicts": conflicts,
        "same_name_in_other_layers": existing_elsewhere,
        "next_steps": [
            "Write the SKILL.md body: output contract, when not to use, procedure, validation.",
            "Replace every <placeholder> and delete every HTML comment from the template.",
            f"uv run standards/scripts/validate_frontmatter.py skills/{args.layer}/{args.name}",
            f"uv run standards/scripts/check_budgets.py skills/{args.layer}/{args.name}",
            "uv run standards/scripts/build_catalog.py --write",
        ],
    }

    document = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
        LOGGER.info("plan written to %s", args.output)
    else:
        sys.stdout.write(document)
        sys.stdout.flush()

    if existing_elsewhere:
        LOGGER.warning(
            "a skill named %s already exists in layer(s) %s; two skills with the same "
            "directory name resolve by precedence and the loser is invisible",
            args.name,
            ", ".join(existing_elsewhere),
        )

    if conflicts and not args.force:
        for rel in conflicts:
            LOGGER.error("refusing to overwrite existing file: %s", rel)
        LOGGER.error("nothing was written. Re-run with --force to overwrite.")
        return EXIT_FINDINGS

    if args.confirm:
        LOGGER.info("wrote %d file(s) under %s", len(written), skill_dir)
    else:
        LOGGER.info(
            "dry run: %d file(s) would be created under %s. Re-run with --confirm to write.",
            len([a for a in actions if a["action"] != "skip"]),
            skill_dir,
        )
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(EXIT_INTERNAL)
