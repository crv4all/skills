#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Build a compact index of an ADR registry so agents cite decisions by id.

Reading forty ADRs to find the three that bind a design costs far more than
reading one index. The index keeps each ADR's id, title, status, date and the
opening of its decision, plus the registry commit it was built from, so a later
reader can tell whether the index is stale. The registry is only read.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EPILOG = """examples:
  python3 build_adr_index.py --registry ../adr-registry --out architecture-index.json

Accepted ADRs are binding, Proposed are directional, Superseded and Deprecated
are listed but flagged.

exit codes:
  0  index written
  1  index written, but a manifest entry has no readable ADR file
  2  usage error
  3  the registry or its adr-manifest.json does not exist
  4  adr-manifest.json is not valid JSON of the expected shape
  5  internal error
"""

LOG = logging.getLogger("build_adr_index")

STATUSES = {
    "accepted": "Accepted",
    "proposed": "Proposed",
    "superseded": "Superseded",
    "deprecated": "Deprecated",
}
BINDING = {
    "Accepted": ("binding", False),
    "Proposed": ("directional", False),
    "Superseded": ("flagged", True),
    "Deprecated": ("flagged", True),
}
SEARCH_DIRS = ("", "architecture/adrs", "adrs")
ID_IN_TITLE = re.compile(r"^\s*(ADR-[A-Za-z]*\d+)\b", re.IGNORECASE)
ID_IN_NAME = re.compile(r"^adr-([a-z]*\d+)", re.IGNORECASE)
STATUS_LINE = re.compile(r"^\*{0,2}Status:?\*{0,2}\s*(.*)$", re.IGNORECASE)
DATE_LINE = re.compile(r"^\*{0,2}Date:?\*{0,2}\s*(\d{4}-\d{2}-\d{2})")
EXCLUDED = ("outcome", "related", "driver")


def normalise_status(raw: str) -> Optional[str]:
    word = re.sub(r"[^A-Za-z ]", " ", raw).split()
    if len(word) >= 1 and raw.strip().startswith("[") and "|" in raw:
        return None  # an unfilled template placeholder
    return STATUSES.get(word[0].lower()) if word else None


def decision_text(lines: list[str]) -> str:
    """First 300 characters of the Decision section, whitespace collapsed."""
    start = None
    for index, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        heading = line[3:].strip().lower()
        if heading.startswith("proposed solution") or (
            "decision" in heading and not any(word in heading for word in EXCLUDED)
        ):
            start = index + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return " ".join(" ".join(body).split())[:300]


def read_adr(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), "")
    status: Optional[str] = None
    date: Optional[str] = None
    for line in lines[:30]:
        match = STATUS_LINE.match(line.strip())
        if match and status is None and not line.lower().lstrip("* ").startswith("status ("):
            status = normalise_status(match.group(1))
        dated = DATE_LINE.match(line.strip())
        if dated and date is None:
            date = dated.group(1)
    return {"title": title, "status": status, "date": date, "decision": decision_text(lines)}


def find_file(registry: Path, rel: str) -> Optional[Path]:
    for folder in SEARCH_DIRS:
        candidate = registry / folder / rel
        if candidate.is_file():
            return candidate
    return None


def adr_id(title: str, rel: str) -> str:
    match = ID_IN_TITLE.match(title)
    if match:
        return match.group(1).upper()
    named = ID_IN_NAME.match(Path(rel).name)
    return f"ADR-{named.group(1).upper()}" if named else Path(rel).stem


def registry_commit(registry: Path) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", "-C", str(registry), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=60, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a JSON index of an ADR registry.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--registry", required=True, help="ADR registry checkout (read only).")
    parser.add_argument("--out", required=True, help="Index file to write.")
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    registry = Path(args.registry).expanduser()
    manifest_path = registry / "adr-manifest.json"
    if not manifest_path.is_file():
        LOG.error(
            "%s: adr-manifest.json not found. Pass the registry root with --registry.",
            manifest_path,
        )
        return EXIT_INPUT
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOG.error("%s: invalid JSON at line %s: %s", manifest_path, exc.lineno, exc.msg)
        return EXIT_MALFORMED
    if not isinstance(manifest, list) or not all(
        isinstance(e, dict) and "path" in e for e in manifest
    ):
        LOG.error("%s: expected a list of objects that each have a 'path'.", manifest_path)
        return EXIT_MALFORMED

    adrs: list[dict[str, Any]] = []
    problems = 0
    for entry in manifest:
        rel = str(entry["path"])
        found = find_file(registry, rel)
        if found is None:
            LOG.error("%s: listed in the manifest but no file was found under %s.", rel, registry)
            problems += 1
            continue
        info = read_adr(found)
        title = info["title"] or str(entry.get("title", ""))
        status = info["status"] or normalise_status(str(entry.get("status", ""))) or "Unknown"
        manifest_status = normalise_status(str(entry.get("status", "")))
        if manifest_status and manifest_status != status:
            LOG.warning(
                "%s: file says %s, manifest says %s; using the file.", rel, status, manifest_status
            )
        binding, flagged = BINDING.get(status, ("unknown", True))
        adrs.append(
            {
                "id": adr_id(title, rel),
                "title": title,
                "status": status,
                "binding": binding,
                "flagged": flagged,
                "date": info["date"],
                "decision": info["decision"],
                "path": found.relative_to(registry).as_posix(),
            }
        )
    adrs.sort(key=lambda item: item["id"])
    counts: dict[str, int] = {}
    for item in adrs:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    commit = registry_commit(registry)
    if commit is None:
        LOG.warning("%s is not a git checkout; the commit is recorded as null.", registry)
    index = {
        "schema": 1,
        "registry": registry.resolve().name,
        "registry_commit": commit,
        "counts": counts,
        "adrs": adrs,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out)
    sys.stdout.write(
        json.dumps(
            {
                "ok": problems == 0,
                "out": str(out),
                "adrs": len(adrs),
                "registry_commit": commit,
                "counts": counts,
            },
            indent=2,
        )
        + "\n"
    )
    return EXIT_FINDINGS if problems else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        LOG.exception("internal error")
        sys.exit(EXIT_INTERNAL)
