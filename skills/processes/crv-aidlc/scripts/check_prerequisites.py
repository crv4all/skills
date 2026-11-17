#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Check what must be in place before a first paddock.

A skill added to the repository is not on the machine until ``install.sh`` runs
again, and a stage then fails in a way that looks like a process bug. This script
turns that into a named, fixable finding before any work starts. It only reads;
the one thing it writes is a small marker so a later run can skip the checks.

Access to Jira itself cannot be checked here: the session must confirm it has
Jira tools.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

EPILOG = """examples:
  python3 check_prerequisites.py --root ~/planning
  python3 check_prerequisites.py --if-stale --root ~/planning --jira

exit codes:
  0  every required check is ok (conditional failures are shown as warnings)
  1  a required check failed
  2  usage error
"""

LOG = logging.getLogger("check_prerequisites")

#: The floor every skill script declares in its PEP 723 header.
PYTHON_FLOOR = (3, 9)
SKILLS = (
    "crv-aidlc",
    "crv-aidlc-reverse-engineering",
    "crv-aidlc-hla",
    "crv-aidlc-tdd",
    "crv-aidlc-inception",
    "crv-aidlc-construction",
    "crv-aidlc-operation",
)
STAGE_SKILLS = SKILLS[1:]
#: Same list as standards/tests/test_shared_aidlc_files.py: (path, canonical, copies).
SHARED = (
    ("references/core-rules.md", "crv-aidlc", STAGE_SKILLS),
    ("scripts/aidlc_state.py", "crv-aidlc", STAGE_SKILLS),
    ("assets/stages.json", "crv-aidlc", STAGE_SKILLS),
    ("scripts/lint_questions.py", "crv-aidlc", STAGE_SKILLS),
    ("scripts/check_traceability.py", "crv-aidlc", ("crv-aidlc-inception",)),
    ("scripts/validate_doc.py", "crv-aidlc-hla", ("crv-aidlc-tdd",)),
)
JIRA_SKILLS = ("crv-create-jira-epic", "crv-create-jira-story")
INSTALL_FIX = "from your clone of the skills repository run: ./install.sh --all"
MARKER_NAME = "prerequisites.json"
THIS = Path(__file__)


def check(
    cid: str, name: str, level: str, status: str, detail: str, fix: str = ""
) -> dict[str, str]:
    return {"id": cid, "name": name, "level": level, "status": status, "detail": detail, "fix": fix}


def skill_dirs() -> dict[str, Path]:
    """Where each installed ``crv-aidlc*`` skill is, looking beside this skill's install
    directory first and beside its resolved (symlink-free) location second."""
    skill = THIS.parent.parent
    bases = [skill.parent]
    real = THIS.resolve().parent.parent.parent
    if real not in bases:
        bases.append(real)
    found: dict[str, Path] = {}
    for name in SKILLS + JIRA_SKILLS:
        for base in bases:
            if (base / name / "SKILL.md").is_file():
                found[name] = base / name
                break
    return found


def git_value(*args: str) -> Optional[str]:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def find_root(explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        return Path(explicit).expanduser().resolve()
    here = Path.cwd().resolve()
    for folder in [here, *here.parents]:
        if (folder / "paddocks").is_dir() and (folder / "docs" / "process.md").is_file():
            return folder
    return None


def r1_python() -> dict[str, str]:
    have = sys.version_info[:2]
    want = ".".join(map(str, PYTHON_FLOOR))
    if have >= PYTHON_FLOOR:
        return check("R1", "Python", "required", "ok", f"{have[0]}.{have[1]} (floor {want})")
    return check(
        "R1", "Python", "required", "outdated", f"{have[0]}.{have[1]}, need {want} or newer",
        f"install Python {want} or newer and run the scripts with it",
    )  # fmt: skip


def r2_git() -> dict[str, str]:
    if git_value("--version") is None:
        return check("R2", "Git", "required", "missing", "git is not on PATH", "install git")
    name, email = git_value("config", "user.name"), git_value("config", "user.email")
    missing = [k for k, v in (("user.name", name), ("user.email", email)) if not v]
    if missing:
        key = missing[0]
        return check(
            "R2", "Git", "required", "missing", f"not set: {', '.join(missing)}",
            f'git config --global {key} "<your {key.split(".")[1]}>"',
        )  # fmt: skip
    return check("R2", "Git", "required", "ok", "installed, identity set")


def r3_installed(found: dict[str, Path]) -> dict[str, str]:
    missing = [n for n in SKILLS if n not in found]
    if missing:
        return check(
            "R3", "Skills installed", "required", "missing", "missing: " + ", ".join(missing),
            INSTALL_FIX,
        )  # fmt: skip
    return check("R3", "Skills installed", "required", "ok", f"all {len(SKILLS)} found")


def shared_pairs(found: dict[str, Path]) -> list[tuple[str, str, Path, Path]]:
    pairs = []
    for rel, canonical, copies in SHARED:
        for copy in copies:
            if canonical in found and copy in found:
                pairs.append((rel, copy, found[canonical] / rel, found[copy] / rel))
    return pairs


def r4_consistent(found: dict[str, Path]) -> dict[str, str]:
    stale: list[str] = []
    for _rel, copy, source, target in shared_pairs(found):
        try:
            same = source.read_bytes() == target.read_bytes()
        except OSError:
            same = False
        if not same and copy not in stale:
            stale.append(copy)
    if stale:
        return check(
            "R4", "Skills consistent", "required", "outdated", "differs: " + ", ".join(stale),
            INSTALL_FIX,
        )  # fmt: skip
    return check("R4", "Skills consistent", "required", "ok", "shared files identical")


def r5_planning(root: Optional[Path]) -> dict[str, str]:
    name = "Planning repo"
    if root is None:
        return check(
            "R5", name, "required", "missing", "none found above the current directory",
            "pass --root <planning repo>, or ask the process owner where the planning repo lives",
        )  # fmt: skip
    absent = [p for p in ("paddocks", "codekb", "docs/process.md") if not (root / p).exists()]
    if not (root / ".git").exists():
        absent.insert(0, "a git repository")
    if absent:
        return check(
            "R5", name, "required", "missing", f"{root}: lacks " + ", ".join(absent),
            "pass --root <planning repo>, or ask the process owner where the planning repo lives",
        )  # fmt: skip
    return check("R5", name, "required", "ok", str(root))


def c1_adr(root: Optional[Path], ref: Optional[str], found: dict[str, Path]) -> dict[str, str]:
    name = "ADR registry"
    index = root / "architecture-index.json" if root else None
    if not ref and not (index and index.is_file()):
        return check("C1", name, "conditional", "skipped", "no --architecture-ref and no index")
    recorded: Optional[str] = None
    registry_name: Optional[str] = None
    if index and index.is_file():
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
            recorded, registry_name = data.get("registry_commit"), data.get("registry")
        except (OSError, ValueError):
            return check(
                "C1", name, "conditional", "outdated", f"{index} is not valid JSON",
                "rebuild it with build_adr_index.py",
            )  # fmt: skip
    path: Optional[Path] = Path(ref).expanduser() if ref else None
    if path is None and root and registry_name:
        sibling = root.parent / registry_name
        path = sibling if sibling.is_dir() else None
    if path is None:
        return check(
            "C1", name, "conditional", "skipped", "registry path unknown",
            "pass --architecture-ref <registry path>",
        )  # fmt: skip
    script = (found.get("crv-aidlc") or THIS.parent.parent) / "scripts" / "build_adr_index.py"
    out = (root / "architecture-index.json") if root else Path("architecture-index.json")
    fix = f"python3 {script} --registry {path} --out {out}"
    if not path.is_dir() or git_value("-C", str(path), "rev-parse", "--git-dir") is None:
        return check(
            "C1", name, "conditional", "missing", f"{path} is not a git repository",
            "clone the ADR registry, then pass --architecture-ref <path>",
        )  # fmt: skip
    head = git_value("-C", str(path), "rev-parse", "HEAD")
    if recorded is None:
        return check("C1", name, "conditional", "ok", "registry found; no index to compare")
    if head != recorded:
        return check(
            "C1", name, "conditional", "outdated", "the index is behind the registry's HEAD", fix
        )
    return check("C1", name, "conditional", "ok", "index matches the registry's HEAD")


def jira_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "crv-agent-skills" / "jira.json"


def c2_jira(want: bool, found: dict[str, Path]) -> dict[str, str]:
    name = "Jira"
    if not want:
        return check("C2", name, "conditional", "skipped", "--jira not given")
    missing = [n for n in JIRA_SKILLS if n not in found]
    if missing:
        return check(
            "C2", name, "conditional", "missing", "skills missing: " + ", ".join(missing),
            INSTALL_FIX,
        )  # fmt: skip
    setup = found[JIRA_SKILLS[0]] / "scripts" / "jira_setup.py"
    fix = f"python3 {setup} --set --site https://<name>.atlassian.net --project <KEY> --confirm"
    path = jira_config_path()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return check("C2", name, "conditional", "missing", f"no setup at {path}", fix)
    except (OSError, ValueError):
        return check("C2", name, "conditional", "missing", f"{path} is not readable JSON", fix)
    absent = [
        k for k in ("site", "project_key") if not (isinstance(config, dict) and config.get(k))
    ]
    if absent:
        return check("C2", name, "conditional", "missing", "setup lacks " + ", ".join(absent), fix)
    return check("C2", name, "conditional", "ok", "skills installed, setup recorded")


def c3_presets(root: Optional[Path]) -> dict[str, str]:
    name = "Presets"
    path = root / "docs" / "presets.md" if root else None
    if path is None or not path.is_file():
        return check("C3", name, "conditional", "skipped", "no docs/presets.md")
    lint = THIS.parent / "lint_questions.py"
    done = subprocess.run(
        [sys.executable, str(lint), "--presets", str(path)],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    if done.returncode == 0:
        return check("C3", name, "conditional", "ok", "docs/presets.md is valid")
    try:
        first = json.loads(done.stdout)["findings"][0]
        detail = f"line {first['line']}: {first['message']}"
    except (ValueError, KeyError, IndexError):
        detail = "docs/presets.md does not pass the linter"
    return check("C3", name, "conditional", "outdated", detail, f"python3 {lint} --presets {path}")


def fingerprint(found: dict[str, Path]) -> str:
    digest = hashlib.sha256()
    for _rel, _copy, source, target in sorted(shared_pairs(found), key=lambda p: (p[0], p[1])):
        for path in (source, target):
            try:
                digest.update(path.read_bytes())
            except OSError:
                digest.update(b"-")
    digest.update(THIS.read_bytes())
    return digest.hexdigest()


def read_marker(directory: Path) -> Optional[dict[str, Any]]:
    try:
        data = json.loads((directory / MARKER_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_marker(directory: Path, verdict: str, print_value: str) -> Optional[str]:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "date": dt.date.today().isoformat(),
            "verdict": verdict,
            "fingerprint": print_value,
        }
        (directory / MARKER_NAME).write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
    except OSError as exc:
        return f"marker not written: {exc}"
    return None


LABEL = {"ok": "OK", "missing": "MISSING", "outdated": "OUTDATED", "skipped": "SKIPPED"}


def render(checks: list[dict[str, str]], verdict: str, notes: list[str]) -> str:
    lines = []
    for item in checks:
        lines.append(f"{LABEL[item['status']]:<8} {item['name']}: {item['detail']}")
        if item["status"] in ("missing", "outdated") and item["fix"]:
            lines.append(f"  fix: {item['fix']}")
    lines.extend(notes)
    lines.append(f"Verdict: {verdict}")
    return "\n".join(lines[:25]) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check the prerequisites for a first paddock.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", help="Planning repository (default: search upward).")
    parser.add_argument("--architecture-ref", help="ADR registry checkout.")
    parser.add_argument("--jira", action="store_true", help="Also check the Jira items.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--if-stale", action="store_true", help="Skip when a marker says ok.")
    parser.add_argument(
        "--marker-dir",
        default="~/.config/crv-aidlc",
        help="Where the marker is kept (default: %(default)s).",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    marker_dir = Path(args.marker_dir).expanduser()
    found = skill_dirs()
    current = fingerprint(found)
    if args.if_stale:
        marker = read_marker(marker_dir)
        if marker and marker.get("verdict") == "ok" and marker.get("fingerprint") == current:
            if args.format == "json":
                sys.stdout.write(json.dumps({"ok": True, "skipped": True, **marker}) + "\n")
            else:
                sys.stdout.write(f"ok, checked {marker.get('date')}\n")
            return EXIT_OK
    root = find_root(args.root)
    checks = [
        r1_python(), r2_git(), r3_installed(found), r4_consistent(found), r5_planning(root),
        c1_adr(root, args.architecture_ref, found), c2_jira(args.jira, found), c3_presets(root),
    ]  # fmt: skip
    required_ok = all(c["status"] == "ok" for c in checks if c["level"] == "required")
    warned = any(c["status"] in ("missing", "outdated") for c in checks if c["level"] != "required")
    verdict = "ok" if required_ok else "not ready"
    if required_ok and warned:
        verdict = "ok, with warnings"
    notes = []
    if args.jira:
        notes.append(
            "Jira access cannot be checked here: the session must confirm it has Jira tools."
        )
    warning = write_marker(marker_dir, "ok" if required_ok else "failed", current)
    if warning:
        LOG.warning("%s", warning)
    if args.format == "json":
        payload = {"ok": required_ok, "verdict": verdict, "checks": checks, "notes": notes}
        if warning:
            payload["warning"] = warning
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        sys.stdout.write(render(checks, verdict, notes))
    return EXIT_OK if required_ok else EXIT_FINDINGS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        LOG.exception("internal error")
        sys.exit(5)
