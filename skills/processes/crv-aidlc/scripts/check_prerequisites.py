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
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, unquote, urlparse

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

EPILOG = """examples:
  python3 check_prerequisites.py --root ~/planning
  python3 check_prerequisites.py --if-stale --root ~/planning --jira
  python3 check_prerequisites.py --root ~/planning --offline

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
    ("scripts/aidlc_refs.py", "crv-aidlc", STAGE_SKILLS),
    ("scripts/check_traceability.py", "crv-aidlc", ("crv-aidlc-inception",)),
    ("scripts/validate_doc.py", "crv-aidlc-hla", ("crv-aidlc-tdd",)),
)
JIRA_SKILLS = ("crv-create-jira-epic", "crv-create-jira-story")
AZURE_SSH_HOST = "ssh.dev.azure.com"
#: Results that depend on the network or on git state are not trusted for longer than this.
MAX_AGE_SECONDS = 24 * 60 * 60
STAMP_NAME = ".crv-install"
#: Same list as ``MANUAL_ITEMS`` in onboard.py: things only a person can arrange.
MANUAL_ITEMS = (
    "Access to the target repositories of your paddock (ask the repository owner).",
    "The Jira and Confluence connector, when your paddock uses Jira.",
    "Databricks access, when a stage reads data.",
    "az login, only if you list repositories.",
)
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


def git_value(*args: str, timeout: int = 20, network: bool = False) -> Optional[str]:
    env = None
    if network:  # never wait for a prompt: a missing key must fail fast
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=10")
    try:
        done = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=timeout, env=env,
            stdin=subprocess.DEVNULL,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def to_ssh_url(url: str) -> Optional[str]:
    """The SSH form of an https remote on Azure DevOps or GitHub, or None."""
    parts = urlparse(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    segments = [unquote(seg) for seg in parts.path.split("/") if seg]
    if host == "github.com" and len(segments) >= 2:
        repo = segments[1][:-4] if segments[1].endswith(".git") else segments[1]
        return f"git@github.com:{segments[0]}/{repo}.git"
    if host == "dev.azure.com" and "_git" in segments:
        at = segments.index("_git")
        if at >= 1 and len(segments) > at + 1:
            org, repo = segments[0], segments[at + 1]
            project = segments[1] if at >= 2 else repo
            return f"git@{AZURE_SSH_HOST}:v3/{org}/{quote(project, safe='')}/{quote(repo, safe='')}"
    if host.endswith(".visualstudio.com") and "_git" in segments:
        org = host.split(".")[0]
        rest = [seg for seg in segments if seg != "DefaultCollection"]
        at = rest.index("_git")
        if len(rest) > at + 1:
            project = rest[0] if at >= 1 else rest[at + 1]
            repo = rest[at + 1]
            return f"git@{AZURE_SSH_HOST}:v3/{org}/{quote(project, safe='')}/{quote(repo, safe='')}"
    return None


def find_checkout(explicit: Optional[str]) -> Optional[Path]:
    """The skills checkout this script runs from (it may be reached through a symlink)."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    for folder in THIS.resolve().parents:
        if (folder / ".git").exists() and (folder / "install.sh").is_file():
            return folder
    return None


def onboard_command(checkout: Optional[Path]) -> str:
    if checkout and (checkout / "onboard.py").is_file():
        return f"python3 {checkout / 'onboard.py'}"
    return "python3 onboard.py (from your clone of the skills repository)"


def ssh_reaches_azure() -> bool:
    """Batch-mode test. A working key prints 'Shell access is not supported.'"""
    target = f"git@{AZURE_SSH_HOST}"
    try:
        done = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-T", target],
            capture_output=True, text=True, timeout=25, stdin=subprocess.DEVNULL,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return False
    return "Shell access is not supported" in (done.stdout + done.stderr)


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


def r6_ssh_tools() -> dict[str, str]:
    absent = [t for t in ("ssh", "ssh-keygen") if shutil.which(t) is None]
    if absent:
        return check(
            "R6", "SSH tools", "required", "missing", "not on PATH: " + ", ".join(absent),
            "install OpenSSH (macOS: built in; Windows: winget install Microsoft.OpenSSH.Beta; "
            "Linux: apt install openssh-client)",
        )  # fmt: skip
    return check("R6", "SSH tools", "required", "ok", "ssh and ssh-keygen found")


def r7_azure(offline: bool, checkout: Optional[Path]) -> dict[str, str]:
    name = "Azure DevOps over SSH"
    if offline:
        return check("R7", name, "required", "skipped", "not tested (--offline)")
    if shutil.which("ssh") is None:
        return check("R7", name, "required", "skipped", "ssh is missing, see the SSH tools check")
    if ssh_reaches_azure():
        return check("R7", name, "required", "ok", f"git@{AZURE_SSH_HOST} accepts your key")
    return check(
        "R7", name, "required", "missing", f"git@{AZURE_SSH_HOST} did not accept your key",
        onboard_command(checkout),
    )  # fmt: skip


def registry_path(root: Optional[Path], ref: Optional[str], name: Optional[str]) -> Optional[Path]:
    if ref:
        return Path(ref).expanduser()
    if root:
        for sibling in (name, "adr-registry"):
            if sibling and (root.parent / sibling).is_dir():
                return root.parent / sibling
    return None


def r8_remotes(root: Optional[Path], registry: Optional[Path]) -> dict[str, str]:
    name = "Git remotes use SSH"
    bad: list[str] = []
    fixes: list[str] = []
    for label, path in (("planning repo", root), ("ADR registry", registry)):
        if path is None or not path.is_dir():
            continue
        url = git_value("-C", str(path), "remote", "get-url", "origin")
        if not url or not url.lower().startswith(("http://", "https://")):
            continue
        bad.append(label)
        ssh = to_ssh_url(url)
        fixes.append(
            f"git -C {path} remote set-url origin {ssh}" if ssh
            else f"git -C {path} remote set-url origin <the SSH url of {label}>"
        )  # fmt: skip
    if bad:
        return check(
            "R8", name, "required", "outdated", "https remote: " + ", ".join(bad), "; ".join(fixes)
        )
    return check("R8", name, "required", "ok", "no https remotes")


def branch_wanted(root: Optional[Path]) -> Optional[str]:
    if root is None:
        return None
    try:
        data = json.loads((root / "aidlc.json").read_text(encoding="utf-8"))
        branch = data["git"]["branch"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return branch if isinstance(branch, str) and branch else None


def r9_branch(root: Optional[Path]) -> dict[str, str]:
    name = "Planning branch"
    wanted = branch_wanted(root)
    if wanted is None or root is None:
        return check("R9", name, "required", "skipped", "aidlc.json names no branch")
    current = git_value("-C", str(root), "symbolic-ref", "--short", "HEAD")
    if current == wanted:
        return check("R9", name, "required", "ok", f"on {wanted}")
    return check(
        "R9", name, "required", "outdated",
        f"on {current or 'no branch'}, aidlc.json wants {wanted}",
        f"git -C {root} switch {wanted}",
    )  # fmt: skip


def read_stamp(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def c4_current(found: dict[str, Path], checkout: Optional[Path], offline: bool) -> dict[str, str]:
    name = "Skills current"
    homes = [Path.home() / ".claude" / "skills", Path.home() / ".cursor" / "skills"]
    stamps: dict[str, dict[str, str]] = {}
    for skill in SKILLS:
        places = [found[skill]] if skill in found else []
        for place in [*places, *(home / skill for home in homes)]:
            if (place / STAMP_NAME).is_file():
                stamps[f"{skill} ({place.parent})"] = read_stamp(place / STAMP_NAME)
    if not stamps:
        return check("C4", name, "conditional", "skipped", "no install stamps (not an install)")
    fix = f"{onboard_command(checkout)}  (or ./install.sh --all)"
    if checkout is None:
        return check("C4", name, "conditional", "skipped", "no skills checkout to compare with")
    head = git_value("-C", str(checkout), "rev-parse", "HEAD")
    issues: list[str] = []
    old = [n for n, st in stamps.items() if not st.get("commit") or st.get("commit") != head]
    if old:
        issues.append(
            "installed from an older checkout: "
            + ", ".join(sorted({n.split(" (")[0] for n in old}))
        )
    note = ""
    if offline:
        note = " (remote not checked: --offline)"
    elif git_value("-C", str(checkout), "fetch", "--quiet", timeout=60, network=True) is None:
        note = " (remote not reached: compared with the local checkout)"
    else:
        counts = git_value("-C", str(checkout), "rev-list", "--count", "HEAD..@{u}")
        if counts and counts.isdigit() and int(counts) > 0:
            issues.append(f"the checkout is {counts} commits behind its remote")
    if issues:
        return check("C4", name, "conditional", "outdated", "; ".join(issues), fix)
    if note:
        return check(
            "C4", name, "conditional", "warning", "installed skills match the checkout" + note
        )
    return check("C4", name, "conditional", "ok", "installed skills match the checkout")


def c1_adr(
    root: Optional[Path], ref: Optional[str], found: dict[str, Path], offline: bool = False
) -> dict[str, str]:
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
    path = registry_path(root, ref, registry_name) if (ref or registry_name) else None
    if path is None:
        return check(
            "C1", name, "conditional", "skipped", "registry path unknown",
            "pass --architecture-ref <registry path>",
        )  # fmt: skip
    script = (found.get("crv-aidlc") or THIS.parent.parent) / "scripts" / "build_adr_index.py"
    out = (root / "architecture-index.json") if root else Path("architecture-index.json")
    fix = f"python3 {script} --registry {path} --out {out} --refresh"
    if not path.is_dir() or git_value("-C", str(path), "rev-parse", "--git-dir") is None:
        return check(
            "C1", name, "conditional", "missing", f"{path} is not a git repository",
            "clone the ADR registry, then pass --architecture-ref <path>",
        )  # fmt: skip
    head = git_value("-C", str(path), "rev-parse", "HEAD")
    target, where, note = head, "HEAD", ""
    if git_value("-C", str(path), "remote"):  # there is a remote to compare with
        if offline:
            note = "offline: compared with the local checkout"
        elif git_value("-C", str(path), "fetch", "--quiet", timeout=60, network=True) is None:
            note = "no network: compared with the local checkout"
        else:
            for spec in ("origin/HEAD", "@{u}"):
                remote_head = git_value("-C", str(path), "rev-parse", spec)
                if remote_head:
                    target, where = remote_head, "remote"
                    break
    suffix = f" ({note})" if note else ""
    if recorded is None:
        return check(
            "C1", name, "conditional", "ok", "registry found; no index to compare" + suffix
        )
    if target != recorded:
        return check(
            "C1", name, "conditional", "outdated",
            f"the index is behind the registry's {where}" + suffix, fix,
        )  # fmt: skip
    status = "warning" if note else "ok"
    return check(
        "C1", name, "conditional", status, f"index matches the registry's {where}" + suffix
    )


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
            "checked_at": int(time.time()),
            "verdict": verdict,
            "fingerprint": print_value,
        }
        (directory / MARKER_NAME).write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
    except OSError as exc:
        return f"marker not written: {exc}"
    return None


def marker_is_fresh(marker: dict[str, Any], now: Optional[float] = None) -> bool:
    """Network and git results are only trusted for 24 hours."""
    stamped = marker.get("checked_at")
    if not isinstance(stamped, (int, float)):
        return False
    age = (time.time() if now is None else now) - stamped
    return 0 <= age < MAX_AGE_SECONDS


LABEL = {
    "ok": "OK",
    "missing": "MISSING",
    "outdated": "OUTDATED",
    "skipped": "SKIPPED",
    "warning": "WARNING",
}


def render(checks: list[dict[str, str]], verdict: str, notes: list[str]) -> str:
    lines = []
    for item in checks:
        lines.append(f"{LABEL[item['status']]:<8} {item['name']}: {item['detail']}")
        if item["status"] in ("missing", "outdated") and item["fix"]:
            lines.append(f"  fix: {item['fix']}")
    lines.extend(notes)
    lines.append("Only you can arrange these (not counted as failures):")
    lines.extend(f"  MANUAL {item}" for item in MANUAL_ITEMS)
    return "\n".join([*lines[:40], f"Verdict: {verdict}"]) + "\n"


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
    parser.add_argument(
        "--if-stale",
        action="store_true",
        help="Skip when a marker says ok. The marker is not trusted for more than 24 hours.",
    )
    parser.add_argument(
        "--offline", action="store_true", help="Make no network call; say so in the table."
    )
    parser.add_argument("--skills-checkout", help="The skills checkout (default: where this runs).")
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
        if (
            marker
            and marker.get("verdict") == "ok"
            and marker.get("fingerprint") == current
            and marker_is_fresh(marker)
        ):
            if args.format == "json":
                sys.stdout.write(json.dumps({"ok": True, "skipped": True, **marker}) + "\n")
            else:
                sys.stdout.write(f"ok, checked {marker.get('date')}\n")
            return EXIT_OK
    root = find_root(args.root)
    checkout = find_checkout(args.skills_checkout)
    registry = registry_path(root, args.architecture_ref, None)
    checks = [
        r1_python(), r2_git(), r3_installed(found), r4_consistent(found), r5_planning(root),
        r6_ssh_tools(), r7_azure(args.offline, checkout), r8_remotes(root, registry),
        r9_branch(root),
        c1_adr(root, args.architecture_ref, found, args.offline), c2_jira(args.jira, found),
        c3_presets(root), c4_current(found, checkout, args.offline),
    ]  # fmt: skip
    required_ok = all(c["status"] in ("ok", "skipped") for c in checks if c["level"] == "required")
    warned = any(
        c["status"] in ("missing", "outdated", "warning")
        for c in checks
        if c["level"] != "required"
    )
    verdict = "ok" if required_ok else "not ready"
    if required_ok and warned:
        verdict = "ok, with warnings"
    notes = []
    if args.offline:
        notes.append("Offline: no network call was made; SSH and remote checks used local data.")
    if args.jira:
        notes.append(
            "Jira access cannot be checked here: the session must confirm it has Jira tools."
        )
    remembered = "ok" if required_ok and not args.offline else "failed"
    warning = write_marker(marker_dir, remembered, current)
    if warning:
        LOG.warning("%s", warning)
    if args.format == "json":
        payload = {
            "ok": required_ok,
            "verdict": verdict,
            "checks": checks,
            "notes": notes,
            "manual": list(MANUAL_ITEMS),
        }
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
