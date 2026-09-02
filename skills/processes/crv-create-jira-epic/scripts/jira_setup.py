#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Record which Jira site and project this machine files issues into.

The values live outside any repository, in the user configuration directory, so
that a site URL and a project key never reach version control. Credentials are
deliberately out of scope: authentication belongs to the Atlassian MCP server
that the agent already talks to, and a second copy of a token on disk is a
second thing to leak.

Custom-field identifiers are also out of scope. They differ per tenant and
change when a Jira administrator edits a screen, so the skills resolve them from
project create-metadata at run time rather than trusting a cached copy.

Per-project field defaults are in scope, keyed by human-readable field name. A
Jira create screen enforces what an administrator marked required, not what the
organisation expects on every issue, so a field like "Assigned Team(s)" is left
unset by a run that only satisfies the screen and then asked for afterwards, one
edit per issue. Recording the expectation once is cheaper than that.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EXIT_CODE_HELP = """exit codes:
  0  success (configuration is complete, or a write succeeded)
  1  configuration is absent or incomplete -- run --set
  2  usage error, including any attempt to pass a credential
  3  a required input was missing or unreadable
  4  the configuration file exists but is not valid JSON
  5  internal error
"""

#: Keys a complete configuration must carry. ``cloud_id`` is deliberately not
#: here: most Atlassian MCP deployments resolve it from the site, and demanding
#: it up front would block setup on a value the user cannot easily find.
REQUIRED_KEYS = ("site", "project_key")
OPTIONAL_KEYS = ("cloud_id", "project_defaults")

#: Key holding per-project field defaults: ``{project_key: {field_name: value}}``.
DEFAULTS_KEY = "project_defaults"

CONFIG_DIR_NAME = "crv-agent-skills"
CONFIG_FILE_NAME = "jira.json"

SITE_PATTERN = re.compile(r"^https://[A-Za-z0-9.-]+\.atlassian\.net$")
PROJECT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,9}$")
CLOUD_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{8,64}$")
CUSTOM_FIELD_PATTERN = re.compile(r"^customfield_[0-9]+$", re.IGNORECASE)

#: Argument names that would mean a credential is being handed to this script.
#: They are registered so that the refusal is an explicit, readable message
#: rather than argparse's generic "unrecognized arguments".
CREDENTIAL_FLAGS = (
    "--token",
    "--api-token",
    "--password",
    "--secret",
    "--pat",
    "--bearer",
)

LOG = logging.getLogger("jira_setup")


def config_path() -> Path:
    """Return the configuration file path, honouring ``XDG_CONFIG_HOME``."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def load_config(path: Path) -> Optional[dict[str, Any]]:
    """Read the configuration file.

    Returns ``None`` when the file does not exist, which is an ordinary state on
    a machine that has not been set up yet. Raises :class:`ValueError` when the
    file exists but cannot be parsed -- a corrupt file must never be mistaken
    for an absent one, because the remedies differ.
    """
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem-dependent
        raise ValueError(f"{path}: unreadable: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON at line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{path}: expected a JSON object, found {type(parsed).__name__}")
    return parsed


def missing_keys(config: Optional[dict[str, Any]]) -> list[str]:
    """Return the required keys that are absent or blank."""
    if config is None:
        return list(REQUIRED_KEYS)
    return [key for key in REQUIRED_KEYS if not str(config.get(key, "")).strip()]


def validate_site(value: str) -> str:
    """Normalise and check a Jira site URL."""
    site = value.strip().rstrip("/")
    if not SITE_PATTERN.match(site):
        raise ValueError(
            f"--site {value!r} is not a Jira Cloud site URL. "
            "Expected the form https://<name>.atlassian.net with no path and no trailing slash."
        )
    return site


def validate_project_key(value: str) -> str:
    """Normalise and check a Jira project key."""
    key = value.strip().upper()
    if not PROJECT_KEY_PATTERN.match(key):
        raise ValueError(
            f"--project {value!r} is not a Jira project key. "
            "Expected 2-10 characters, starting with a letter, upper case, "
            "for example the ABC in ABC-123."
        )
    return key


def validate_cloud_id(value: str) -> str:
    """Check an Atlassian cloud identifier."""
    cloud_id = value.strip()
    if not CLOUD_ID_PATTERN.match(cloud_id):
        raise ValueError(f"--cloud-id {value!r} is not an Atlassian cloud identifier.")
    return cloud_id


def parse_field_default(raw: str) -> tuple[str, str]:
    """Split a ``NAME=VALUE`` field default, refusing custom-field identifiers.

    Names rather than identifiers, on purpose: ``customfield_10001`` recorded on
    this machine is wrong the day an administrator edits a screen, and wrong on
    every other tenant. A name is resolved from create-metadata at run time and
    fails loudly when it stops existing.
    """
    name, separator, value = raw.partition("=")
    name = name.strip()
    value = value.strip()
    if not separator:
        raise ValueError(
            f"--field-default {raw!r} is not NAME=VALUE. "
            'Example: --field-default "Assigned Team(s)=Platform"'
        )
    if not name:
        raise ValueError(f"--field-default {raw!r} has an empty field name.")
    if not value:
        raise ValueError(
            f"--field-default {raw!r} has an empty value. To remove defaults, "
            "use --clear-field-defaults."
        )
    if CUSTOM_FIELD_PATTERN.match(name):
        raise ValueError(
            f"--field-default {raw!r} names a custom-field identifier. Use the "
            "human-readable field name instead: identifiers differ per tenant and "
            "change when an administrator edits a screen, so the skills resolve "
            "names at run time."
        )
    return name, value


def collect_field_defaults(raw_values: list[str]) -> dict[str, Any]:
    """Fold ``NAME=VALUE`` arguments into a mapping.

    A name given once stores a scalar; a name repeated in the same invocation
    stores a list, which is what a multi-value field needs. Repeating across
    invocations replaces rather than appends, so re-running the same command is
    idempotent instead of growing the list every time.
    """
    collected: dict[str, list[str]] = {}
    for raw in raw_values:
        name, value = parse_field_default(raw)
        collected.setdefault(name, []).append(value)
    return {name: (values[0] if len(values) == 1 else values) for name, values in collected.items()}


def read_project_defaults(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the recorded defaults, rejecting a structurally wrong file.

    A hand-edited file whose ``project_defaults`` is a list or a string is
    malformed in the same way invalid JSON is: the remedy is inspection, not
    re-running setup.
    """
    stored = config.get(DEFAULTS_KEY)
    if stored is None:
        return {}
    if not isinstance(stored, dict) or any(
        not isinstance(value, dict) for value in stored.values()
    ):
        raise ValueError(
            f"{DEFAULTS_KEY} must be an object of project key to field mapping, "
            f"found {type(stored).__name__}"
        )
    return {str(key): dict(value) for key, value in stored.items()}


def write_config(path: Path, config: dict[str, Any]) -> None:
    """Write the configuration with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def emit(payload: Any, output: Optional[Path] = None) -> None:
    """Write ``payload`` as a single JSON document, to stdout or to ``output``.

    ``sys.stdout.write`` rather than ``print`` so the repository-wide no-print
    rule stays absolute and has no exceptions to reason about.
    """
    document = json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(document, encoding="utf-8")
        return
    sys.stdout.write(document)
    sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jira_setup.py",
        description=(
            "Record the Jira site and project this machine files issues into. "
            "Stores no credentials: authentication belongs to the Atlassian MCP server."
        ),
        epilog=(
            "examples:\n"
            "  # is this machine configured?\n"
            "  python3 jira_setup.py --check\n\n"
            "  # see the plan, write nothing (the default)\n"
            "  python3 jira_setup.py --set --site https://example.atlassian.net --project ABC\n\n"
            "  # actually write it\n"
            "  python3 jira_setup.py --set --site https://example.atlassian.net "
            "--project ABC --confirm\n\n"
            "  # record fields the organisation expects on every ABC issue\n"
            "  python3 jira_setup.py --set --defaults-project ABC \\\n"
            '    --field-default "Assigned Team(s)=Platform" --confirm\n\n'
            "  # show what is recorded\n"
            "  python3 jira_setup.py --show\n\n" + EXIT_CODE_HELP
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="Report whether configuration is complete."
    )
    mode.add_argument("--show", action="store_true", help="Print the recorded configuration.")
    mode.add_argument("--set", action="store_true", help="Record site, project key, and cloud id.")

    parser.add_argument("--site", help="Jira Cloud site URL, https://<name>.atlassian.net")
    parser.add_argument("--project", help="Default Jira project key, for example ABC.")
    parser.add_argument(
        "--cloud-id", help="Atlassian cloud identifier, if the MCP server needs it."
    )
    parser.add_argument(
        "--field-default",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="With --set: a field the organisation expects on every issue in a project, "
        "named as it appears on the create screen. Repeat the same NAME to store a list. "
        "Scoped by --defaults-project, else --project, else the recorded default project.",
    )
    parser.add_argument(
        "--defaults-project",
        help="Project key the --field-default values belong to, when it is not the "
        "default project being recorded.",
    )
    parser.add_argument(
        "--clear-field-defaults",
        action="store_true",
        help="With --set: remove every recorded field default for the scoped project.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually write. Without it, --set only prints the plan.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly request a dry run. Already the default; the flag exists so a "
        "command line a human reads can state the intent.",
    )
    parser.add_argument(
        "--output",
        help="Write the JSON report here instead of stdout. Does not change where the "
        "configuration itself is stored.",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    parser.add_argument("--quiet", action="store_true", help="Only warnings and errors on stderr.")

    for flag in CREDENTIAL_FLAGS:
        parser.add_argument(flag, help=argparse.SUPPRESS)
    return parser


def refuse_credentials(args: argparse.Namespace) -> Optional[str]:
    """Return the offending flag when a credential was supplied."""
    for flag in CREDENTIAL_FLAGS:
        attribute = flag.lstrip("-").replace("-", "_")
        if getattr(args, attribute, None):
            return flag
    return None


def run_check(path: Path, output: Optional[Path]) -> int:
    try:
        config = load_config(path)
    except ValueError as exc:
        LOG.error("%s", exc)
        emit(
            {"config_path": str(path), "status": "malformed", "missing": list(REQUIRED_KEYS)},
            output,
        )
        return EXIT_MALFORMED
    absent = missing_keys(config)
    status = "complete" if not absent else ("absent" if config is None else "incomplete")
    emit(
        {
            "config_path": str(path),
            "status": status,
            "present": config is not None,
            "missing": absent,
            "remediation": None
            if not absent
            else "run jira_setup.py --set --site ... --project ... --confirm",
        },
        output,
    )
    if absent:
        LOG.warning("Jira configuration %s: missing %s", status, ", ".join(absent))
        return EXIT_FINDINGS
    return EXIT_OK


def run_show(path: Path, output: Optional[Path]) -> int:
    try:
        config = load_config(path)
    except ValueError as exc:
        LOG.error("%s", exc)
        return EXIT_MALFORMED
    if config is None:
        LOG.error("No Jira configuration at %s. Run --set first.", path)
        return EXIT_INPUT
    emit({"config_path": str(path), "config": config}, output)
    return EXIT_OK


def run_set(path: Path, args: argparse.Namespace, output: Optional[Path]) -> int:
    try:
        existing = load_config(path)
    except ValueError as exc:
        LOG.error("%s", exc)
        LOG.error("Refusing to overwrite a file this script cannot parse. Inspect or delete it.")
        return EXIT_MALFORMED

    config: dict[str, Any] = dict(existing) if existing else {}
    try:
        defaults = read_project_defaults(config)
    except ValueError as exc:
        LOG.error("%s: %s", path, exc)
        LOG.error("Refusing to rewrite a structure this script did not write. Inspect it.")
        return EXIT_MALFORMED

    try:
        if args.site:
            config["site"] = validate_site(args.site)
        if args.project:
            config["project_key"] = validate_project_key(args.project)
        if args.cloud_id:
            config["cloud_id"] = validate_cloud_id(args.cloud_id)
        touches_defaults = bool(args.field_default) or args.clear_field_defaults
        if touches_defaults:
            scope_raw = args.defaults_project or args.project or config.get("project_key")
            if not scope_raw:
                raise ValueError(
                    "a field default needs a project. Pass --defaults-project ABC, or "
                    "record a default project first with --set --project ABC --confirm."
                )
            scope = validate_project_key(str(scope_raw))
            if args.clear_field_defaults:
                defaults.pop(scope, None)
            if args.field_default:
                scoped = dict(defaults.get(scope, {}))
                scoped.update(collect_field_defaults(args.field_default))
                defaults[scope] = scoped
            if defaults:
                config[DEFAULTS_KEY] = defaults
            else:
                config.pop(DEFAULTS_KEY, None)
    except ValueError as exc:
        LOG.error("%s", exc)
        return EXIT_USAGE

    if not any(
        [args.site, args.project, args.cloud_id, args.field_default, args.clear_field_defaults]
    ):
        LOG.error(
            "--set needs at least one of --site, --project, --cloud-id, "
            "--field-default, --clear-field-defaults."
        )
        return EXIT_USAGE

    absent = missing_keys(config)
    result = {
        "config_path": str(path),
        "would_write": config,
        "written": False,
        "missing_after_write": absent,
    }
    if not args.confirm:
        result["note"] = "dry run: nothing written. Re-run with --confirm."
        emit(result, output)
        LOG.info("Dry run. Re-run with --confirm to write %s", path)
        return EXIT_OK

    try:
        write_config(path, config)
    except OSError as exc:
        LOG.error("Could not write %s: %s", path, exc)
        return EXIT_INTERNAL

    result["written"] = True
    result.pop("note", None)
    emit(result, output)
    LOG.info("Wrote %s", path)
    if absent:
        LOG.warning("Still incomplete: missing %s", ", ".join(absent))
        return EXIT_FINDINGS
    return EXIT_OK


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose else (logging.WARNING if args.quiet else logging.INFO),
        format="%(levelname)s: %(message)s",
    )

    offending = refuse_credentials(args)
    if offending:
        LOG.error(
            "%s is not accepted. This script stores no credentials: authentication is "
            "handled by the Atlassian MCP server, and a token on disk here would be a "
            "second copy to leak. Configure the MCP server instead.",
            offending,
        )
        return EXIT_USAGE

    if not args.set and (args.field_default or args.clear_field_defaults or args.defaults_project):
        LOG.error(
            "--field-default, --clear-field-defaults and --defaults-project only apply "
            "to --set. Use --show to read what is recorded."
        )
        return EXIT_USAGE

    path = config_path()
    output = Path(args.output) if args.output else None

    if args.check:
        return run_check(path, output)
    if args.show:
        return run_show(path, output)
    return run_set(path, args, output)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        sys.exit(EXIT_INTERNAL)
