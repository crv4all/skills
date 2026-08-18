#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Scan the repository for credentials before they become public history.

This repository is public. A secret committed here is a secret disclosed the
moment it is pushed, and rewriting history does not un-disclose it -- forks,
mirrors, and code-search indexes have already taken a copy. So this check runs
in CI on every change, and it is deliberately noisy at the boundary: a false
positive costs one allowlist entry, a false negative costs a rotation.

Dependency-free and pinned to Python 3.9 so it can run in a bare container,
in a git hook, or from a checkout with no virtualenv.

The scanner never emits a matched secret value. Findings carry a redacted
fingerprint only, because a CI log is itself a place secrets leak from.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import cli, log

LOGGER = log.get_logger("scan-secrets")

#: Marker an author can put on the same line to accept a match.
ALLOWLIST_MARKER = "crv-allow-secret"

#: Paths never scanned. Kept short on purpose: every entry is a place a real
#: secret could hide unnoticed.
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
}

#: Extensions with no plausible plaintext credential and a high false-positive rate.
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".ico",
    ".woff",
    ".woff2",
    ".zip",
    ".gz",
    ".lock",
}

MAX_BYTES = 2_000_000
MAX_LINE_LENGTH = 4000


@dataclass(frozen=True)
class Rule:
    code: str
    description: str
    pattern: Pattern[str]
    remediation: str


def _compile(pattern: str) -> Pattern[str]:
    return re.compile(pattern)


RULES: tuple[Rule, ...] = (
    Rule(
        "private-key",
        "PEM private key block",
        _compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
        "Remove the key, rotate it, and reference a secret store instead.",
    ),
    Rule(
        "aws-access-key-id",
        "AWS access key id",
        _compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b"),
        "Rotate in IAM, then use a role or an environment variable.",
    ),
    Rule(
        "azure-storage-connection-string",
        "Azure Storage connection string with an inline account key",
        _compile(r"AccountKey=[A-Za-z0-9+/=]{40,}"),
        "Rotate the storage key and switch to Entra ID or a Key Vault reference.",
    ),
    Rule(
        "azure-sas-token",
        "Azure shared access signature",
        _compile(r"[?&]sig=[A-Za-z0-9%+/=]{20,}"),
        "Regenerate the SAS and issue it at request time, not in source.",
    ),
    Rule(
        "github-token",
        "GitHub personal access, OAuth, or app token",
        _compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        "Revoke it at github.com/settings/tokens and use GITHUB_TOKEN in CI.",
    ),
    Rule(
        "slack-token",
        "Slack token",
        _compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
        "Revoke in the Slack app configuration and store it in the CI secret store.",
    ),
    Rule(
        "openai-style-key",
        "OpenAI-style API key",
        _compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "Revoke the key with the issuing provider and read it from the environment.",
    ),
    Rule(
        "anthropic-key",
        "Anthropic API key",
        _compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
        "Revoke it in the Anthropic console and read it from ANTHROPIC_API_KEY.",
    ),
    Rule(
        "google-api-key",
        "Google API key",
        _compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        "Restrict or delete the key in the Google Cloud console.",
    ),
    Rule(
        "jwt",
        "JSON Web Token",
        _compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "Tokens are bearer credentials even when expired; remove and reissue.",
    ),
    Rule(
        "basic-auth-url",
        "Credentials embedded in a URL",
        _compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s:/@]{6,}@[A-Za-z0-9.-]+"),
        "Move the credential out of the URL; most clients log full URLs.",
    ),
    Rule(
        "azure-devops-pat",
        "Azure DevOps personal access token in a header or URL",
        _compile(r"(?i)\b(?:pat|personal[_-]?access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9]{52}\b"),
        "Revoke it in Azure DevOps user settings and use a service connection.",
    ),
    Rule(
        "generic-assignment",
        "Hard-coded secret assignment",
        _compile(
            r"(?i)\b(?:password|passwd|secret|api[_-]?key|apikey|access[_-]?token|client[_-]?secret)"
            r"\s*[:=]\s*['\"][^'\"\s${}<>]{8,}['\"]"
        ),
        "Read it from the environment or a secret store; if it is a placeholder, "
        "use an obvious one such as <REDACTED> or ${VAR}.",
    ),
)

#: Values that look like secrets but are documentation. Matched case-insensitively
#: against the matched text; a match here suppresses the finding.
PLACEHOLDER_SIGNALS = (
    "example",
    "placeholder",
    "redacted",
    "changeme",
    "change-me",
    "your-",
    "xxxx",
    "dummy",
    "sample",
    "fake",
    "notreal",
    "test-token",
    "<",
    "${",
    "{{",
)


@dataclass
class Finding:
    code: str
    description: str
    path: str
    line: int
    fingerprint: str
    match_length: int
    remediation: str

    def as_dict(self) -> dict:
        return {
            "level": "error",
            "code": f"secret.{self.code}",
            "path": self.path,
            "line": self.line,
            "message": (
                f"{self.description} (length {self.match_length}, sha256:{self.fingerprint})"
            ),
            "hint": self.remediation,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scan_secrets.py",
        description=(
            "Scan repository files for credentials. Writes a JSON report to stdout; the "
            "report contains redacted fingerprints, never secret values. Diagnostics go "
            "to stderr."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 standards/scripts/scan_secrets.py\n"
            "  python3 standards/scripts/scan_secrets.py --staged\n"
            "  python3 standards/scripts/scan_secrets.py docs skills --output secrets.json\n\n"
            "allowlisting:\n"
            f"  Put the marker `{ALLOWLIST_MARKER}` in a comment on the same line to accept a\n"
            "  match. Do that only for values that are demonstrably not credentials; the\n"
            "  marker is visible in review, which is the point.\n\n" + cli.EXIT_CODE_HELP
        ),
    )
    parser.add_argument(
        "paths", nargs="*", help="Files or directories to scan. Default: the whole repository."
    )
    parser.add_argument(
        "--root", type=Path, default=None, help="Repository root (default: auto-detected)."
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Scan only files staged in git. Intended for a pre-commit hook.",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Write the JSON report here instead of stdout."
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    parser.add_argument("--quiet", action="store_true", help="Only warnings and errors on stderr.")
    return parser


def repo_root_from(here: Path) -> Path:
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists() or (
            (candidate / "skills").is_dir() and (candidate / "standards").is_dir()
        ):
            return candidate
    return here


def staged_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        LOGGER.error("could not list staged files: %s", exc)
        return []
    return [root / line for line in result.stdout.splitlines() if line.strip()]


def walk(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            if any(part in SKIP_DIRS for part in child.parts):
                continue
            files.append(child)
    return sorted(set(files))


def scannable(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    try:
        if path.stat().st_size > MAX_BYTES:
            LOGGER.debug("skipping %s: larger than %d bytes", path, MAX_BYTES)
            return False
    except OSError:
        return False
    return True


def looks_like_placeholder(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in PLACEHOLDER_SIGNALS)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def scan_file(path: Path, root: Path) -> list[Finding]:
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        LOGGER.debug("skipping %s: not readable as UTF-8 text", path)
        return []

    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = str(path)

    findings: list[Finding] = []
    for number, line in enumerate(content.splitlines(), start=1):
        if len(line) > MAX_LINE_LENGTH:
            line = line[:MAX_LINE_LENGTH]
        if ALLOWLIST_MARKER in line:
            continue
        for rule in RULES:
            match = rule.pattern.search(line)
            if not match:
                continue
            matched = match.group(0)
            if rule.code != "private-key" and looks_like_placeholder(matched):
                LOGGER.debug("%s:%d: %s match treated as a placeholder", rel, number, rule.code)
                continue
            findings.append(
                Finding(
                    code=rule.code,
                    description=rule.description,
                    path=rel,
                    line=number,
                    fingerprint=fingerprint(matched),
                    match_length=len(matched),
                    remediation=rule.remediation,
                )
            )
    return findings


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log.configure(verbose=args.verbose, quiet=args.quiet)

    if args.staged and args.paths:
        LOGGER.error("--staged scans the git index; it cannot be combined with explicit paths")
        return cli.EXIT_USAGE

    root = (args.root or repo_root_from(Path(__file__).resolve())).resolve()

    if args.staged:
        candidates = [p for p in staged_files(root) if p.exists()]
    elif args.paths:
        candidates = []
        for raw in args.paths:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = root / candidate
            if not candidate.exists():
                LOGGER.error("path does not exist: %s", raw)
                return cli.EXIT_INPUT
            candidates.append(candidate)
        candidates = walk(candidates)
    else:
        candidates = walk([root])

    files = [p for p in candidates if scannable(p)]
    LOGGER.debug("scanning %d file(s)", len(files))

    findings: list[Finding] = []
    for path in files:
        findings.extend(scan_file(path, root))

    payload = {
        "tool": "scan_secrets",
        "root": str(root),
        "files_scanned": len(files),
        "rules": len(RULES),
        "summary": {"errors": len(findings), "warnings": 0},
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
        LOGGER.error(
            "%s:%d: [secret.%s] %s", finding.path, finding.line, finding.code, finding.description
        )
        LOGGER.error("    %s", finding.remediation)

    if findings:
        LOGGER.error(
            "%d potential secret(s) in %d file(s). If a value is genuinely not a credential, "
            "add the marker `%s` on that line.",
            len(findings),
            len({f.path for f in findings}),
            ALLOWLIST_MARKER,
        )
        return cli.EXIT_FINDINGS

    LOGGER.info("%d file(s) scanned, no secrets found", len(files))
    return cli.EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(cli.EXIT_INTERNAL)
