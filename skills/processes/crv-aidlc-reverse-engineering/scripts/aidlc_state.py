#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Open, advance, gate and close a bolt, the folder for one piece of work.

Progress lives in one ``state.json`` per bolt and changes only through this
script. A model that edits progress by hand will, sooner or later, mark a stage
approved that nobody approved; a script that checks the artifacts first cannot.
Everything here is deterministic, so it costs no model tokens.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, Optional, cast

_fcntl: Any
try:
    import fcntl as _fcntl
except ImportError:  # native Windows: the lock falls back to an exclusive-create file
    _fcntl = None

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5
EXIT_GIT = 6

EPILOG = """commands:
  open        create a bolt           --root R --slug S --title T --intent I
  status      show progress              --bolt P [--format text]
  overview    every Bolt at a glance     --root R [--format text] [--log N]
  next        the next stage and step    --bolt P [--unit U | --slice S | --mine]
  inputs      files a stage reads        --bolt P --stage S [--unit U | --slice S]
  decide      execute or skip a stage    --bolt P --stage S --decision D --reason R [--slice S]
  step        move a stage forward       --bolt P --stage S --to asked|analysed|produced [--slice S]
  gate        pass a checkpoint or reopen --bolt P --stage S [--slice S] --approve
                                         [--note "decision"] | --request-changes --note "why"
  units       add or update units, slices --bolt P --set file.json
                                         | --cancel U --reason R [--superseded-by u7,u8]
  assign      set an owner               --bolt P --unit U --owner NAME | --slice S --owner NAME
  slice       add a slice, check ready   --bolt P --add S [--name N] [--owner O] [--depends-on a,b]
                                         | --ready S [--note "direction"]
  brief       a unit's starting page     --bolt P --unit U [--write]
  context     what changed under a unit  --bolt P --unit U | --slice S [--stage X]
              or slice, what it relies   [--note "conclusion"] | --id D63
              on, who relies on an id
  decision-id reserve decision ids       --bolt P [--count n]
  contribution record where an architecture contribution stands
              --bolt P --concern C --status draft|proposed|merged [--note "one line"]
  codekb-status is the code knowledge fresh --bolt P
  workspace   workspace file, checkouts  --bolt P [--extra name=path]... [--fetch] [--out F]
  target      add or drop a target       --bolt P --add name=path | --remove NAME
  jira        record Jira keys           --bolt P --epic K | --unit U --story K | --unit U --done
                                         [--pr URL] | --off --reason R | --on
  park/unpark hand-over note             --bolt P --note N
  close       close the bolt          --bolt P --status complete|superseded|archived
  sync        commit and push your work  --bolt P [-m "what changed"] | --root R

Contributions: architecture/contributions/<concern>.md is a file its owner edits; its yaml
header holds concern, owner, status (draft, proposed, merged) and touches. `contribution`
checks that header and appends one log line; it edits no file and runs no validator.
`status` and `overview` list the contributions from their headers (a proposed one is open
work for the team); nothing about them is stored in state.json.

Slices: build-and-test, deployment-pipeline and deployment-execution run once per Slice,
keep their records in the Slice and their files under docs/slices/<slice>/. Pass --slice S
for them; a Bolt with exactly one Slice needs no flag, with several it is a usage error
that lists them. A Slice's Build and Test is next when its own Units are done, whatever the
other Slices do. A new Slice adds records; it never reopens or rewrites anything that exists.

Git: a command that changes a bolt first brings in the team's work, then commits the
bolt and pushes it. `aidlc.json` at the planning root may hold
{"git": {"branch": "..", "remote": "origin", "commit": true, "push": true}}.
AIDLC_GIT=off or --no-git turns git writes off; a folder outside git is skipped. A temp
file this script left behind (`.state.json.<pid>.tmp`) is never committed, and neither is a
file that still holds git conflict markers (exit 6, the files are named).

State is never merged: when the team pushed a change to a state.json that your command
also changed, your command's commit is dropped (`git reset --keep`), your clone is brought
up to date and the command runs again on the new state, up to 3 times (the result says
`reruns`). `open` and `close` are not run twice on their own; a conflict on a Bolt's
state file then tells you to drop your command's commit and run `sync`. When a push did
not happen the result has `not_shared: true`, and `status` and `overview` say how many
changes are saved here but not shared yet. If the team then changed the Bolt's own
state.json (not a Unit's) that those unshared commits also changed, the next command (or
`sync`) does not rebase them: it sets those commits aside, keeps every other unshared
commit, and the result lists the undone commands in `undone` and in a warning; repeat
them. If that cannot be done cleanly it stops with exit 6 and the branch exactly as it was.

Lock: a command that changes a bolt (and `sync`) holds one lock per planning checkout for
its whole run, git steps included, so two sessions in one checkout queue instead of
colliding. It waits up to 200 s (a git step may take 120 s), then stops and names the lock
file; the lock is in the git directory even with --no-git. The lock is freed by
the operating system if the session dies. Reads (status, next, overview) never wait.

examples:
  python3 aidlc_state.py open --root . --slug billing --title "Billing" --intent "Move billing"
  python3 aidlc_state.py next --bolt bolts/2026-01-05-billing
  python3 aidlc_state.py workspace --bolt bolts/2026-01-05-billing --fetch
  python3 aidlc_state.py gate --bolt bolts/2026-01-05-billing --stage requirements-analysis \\
      --approve --note "go with option A"

exit codes:
  0  ok
  1  findings: a gate or close was refused, or the bolt already exists
  2  usage error
  3  missing input: no bolt, no state.json, a stage input, a folder or a named target is absent
  4  malformed input: state.json, stages.json or a units file cannot be parsed
  5  internal error
  6  git needs you: a rebase or merge conflict, or a possible secret in the commit
"""

LOG = logging.getLogger("aidlc_state")

FRAMEWORK = 4  # bumped when a change to state.json would break an older copy of the skills
LOCAL_FILE = ".aidlc-local.json"  # per machine, never committed; sits at the planning root
LOCK_NAME = ".aidlc.lock"
LOCK_WAIT = 200.0  # longer than the longest git step (120 s) the holder can be inside
LOCK_POLL = 0.2
LOCK_WAIT_ENV = "AIDLC_LOCK_WAIT"  # test only: seconds to wait instead of LOCK_WAIT
LOCK_STALE = 120  # fallback lock only: seconds after which a lock left by a crash is taken over
INDEX_KEYS = ("id", "name", "kind", "slice", "owner", "repo", "depends_on", "cancelled")
UNIT_MODES = ["split", "inline"]
DECISION_STATUS = (
    "constraint", "accepted", "proposed", "assumption", "open", "needs-evidence", "superseded"
)  # fmt: skip
UNSETTLED = ("open", "assumption", "needs-evidence")
DECISION_FILES = ("hla-decisions.md", "tdd-decisions.md")
DECISION_RECORDS = (  # where a Bolt-level D<n> is declared
    "architecture/hla-decisions.md",
    "architecture/tdd-decisions.md",
    "docs/inception/domain-design/decisions.md",
)
PATH_HINT = "set it in .aidlc-local.json or clone it next to the planning repo"

STAGES_PATH = Path(__file__).resolve().parent.parent / "assets" / "stages.json"
STEP_ORDER = ["todo", "asked", "analysed", "produced"]
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
META_KEYS = ["repo", "path", "commit", "built", "artifacts"]
NO_TRACEABILITY_SCOPES = {"bugfix", "express"}  # no stories or units to trace
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
JIRA_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
SCOPES = ["classic", "express", "bugfix"]
DEPTHS = ["minimal", "standard", "comprehensive"]
DEFAULT_DEPTH = {"classic": "standard", "express": "standard", "bugfix": "minimal"}
DEFAULT_UNIT_SCOPES = {"express", "bugfix"}
UNIT_KINDS = ["service", "spec", "ui", "packaging", "library"]
DEPENDENCY_ON = ["done", "contract"]
ROOT_PREFIX = "root:"
FOCUSED_RESCAN_MAX = 0.30
CHANGED_FILES_CAP = 50
PHASES = ["discovery", "inception", "construction", "operation"]
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs", ".rb", ".cs",
    ".sql", ".scala", ".sh", ".php", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp",
}  # fmt: skip
SCAFFOLD_NAMES = {"__init__.py", "setup.py", "conftest.py"}
DIGEST_MAX_LINES = 10
VERDICT_WORDS = ("pass", "fail", "not-run")
# Any decoration (indent, quote, bold, heading, list dash) still makes it a verdict line.
VERDICT_LINE = re.compile(r"^[\s>*_#-]*verdict[\s*_]*:", re.IGNORECASE)
VERDICT_VALUE = re.compile(r"^\s*([A-Za-z-]+)\s*(?:(?:-|:)\s*(.*\S))?\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")
WORKSPACE_SUFFIX = ".code-workspace"
FETCH_TIMEOUT = 20
# A fetch must never wait for a passphrase or a password: nobody is at the keyboard.
FETCH_ENV = {
    "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=15",
    "GIT_TERMINAL_PROMPT": "0",
}
ORIGIN_REFS = "refs/remotes/origin/"
ACTIONS = {
    "todo": "ask",
    "asked": "analyse",
    "analysed": "produce",
    "produced": "gate",
    "changes-requested": "revise",
}


class Fail(Exception):
    """An expected refusal carrying its exit code and optional findings."""

    def __init__(
        self,
        code: int,
        message: str,
        findings: Optional[list[dict[str, Any]]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.findings = findings or []
        self.extra = extra or {}


def die(code: int, message: str) -> NoReturn:
    raise Fail(code, message)


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- catalogue ---------------------------------------------------------------


def load_catalog() -> list[dict[str, Any]]:
    try:
        data = json.loads(STAGES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(EXIT_INPUT, f"{STAGES_PATH}: stages.json not found next to the skill's scripts.")
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{STAGES_PATH}: invalid JSON at line {exc.lineno}: {exc.msg}")
    stages = data.get("stages") if isinstance(data, dict) else None
    if not isinstance(stages, list) or not stages:
        die(EXIT_MALFORMED, f"{STAGES_PATH}: expected a non-empty 'stages' list.")
    return sorted(stages, key=lambda item: item["order"])


def stage_def(catalog: list[dict[str, Any]], stage: str) -> dict[str, Any]:
    for item in catalog:
        if item["id"] == stage:
            return item
    ids = ", ".join(item["id"] for item in catalog)
    die(EXIT_USAGE, f"unknown stage '{stage}'. Valid stages: {ids}")


# --- bolt files -----------------------------------------------------------


def state_path(bolt: Path) -> Path:
    return bolt / "state.json"


def load_state(bolt: Path) -> dict[str, Any]:
    path = state_path(bolt)
    if not bolt.is_dir():
        die(EXIT_INPUT, f"{bolt}: bolt folder not found. Open one with `open`.")
    if not path.is_file():
        die(EXIT_INPUT, f"{path}: state.json not found.")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}")
    if not isinstance(state, dict) or state.get("schema") != 1:
        die(EXIT_MALFORMED, f'{path}: expected an object with "schema": 1.')
    written = state.get("framework")
    if isinstance(written, int) and written > FRAMEWORK:
        die(
            EXIT_MALFORMED,
            f"this Bolt was last written by newer skills (framework {written}, installed "
            f"{FRAMEWORK}); update the skills and run the command again",
        )
    if is_split(state):
        merge_units(bolt, state)
    return state


def is_split(state: dict[str, Any]) -> bool:
    """True for a Bolt that keeps one state file and one log per unit."""
    return state.get("unit_state") == "split"


def unit_dir(bolt: Path, unit: str) -> Path:
    return bolt / "units" / unit


def merge_units(bolt: Path, state: dict[str, Any]) -> None:
    """Put each unit's own file back into its entry, so commands see one shape."""
    catalog: Optional[list[dict[str, Any]]] = None
    for unit in state.get("units", []):
        path = unit_dir(bolt, unit["id"]) / "state.json"
        data: Any = None
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                die(EXIT_MALFORMED, f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}")
            if not isinstance(data, dict):
                die(EXIT_MALFORMED, f"{path}: expected an object.")
            data.pop("updated", None)
            unit.update(data)
        if "stages" not in unit:  # no unit file yet: a unit with no progress
            catalog = catalog or load_catalog()
            unit["stages"] = unit_stage_records(catalog, state["scope"])
            unit.setdefault("story", None)
            unit.setdefault("story_done", None)


def backfill_stages(state: dict[str, Any], catalog: list[dict[str, Any]]) -> None:
    """Give a stage added to the catalogue after this bolt opened a record, in memory.

    Without it a ``state.json`` written earlier would crash or need a hand edit. The
    record is saved with the next write. A closed bolt gets a skip, so it stays done.
    """
    stages = state.setdefault("stages", {})
    state.setdefault("jira", {"mode": None, "reason": "", "epic": None})
    for unit in state.get("units", []):
        unit.setdefault("story", None)
        unit.setdefault("story_done", None)
    for entry in state.get("slices", []):  # older shape: a stored member list and a status
        for member in entry.pop("units", []):
            for unit in state["units"]:
                if unit["id"] == member and not unit.get("slice"):
                    unit["slice"] = entry["id"]
        entry.pop("status", None)
        entry.update({k: v for k, v in new_slice(entry["id"]).items() if k not in entry})
    scope = state.get("scope", "classic")
    brownfield = any(t.get("kind") == "brownfield" for t in state.get("targets", []))
    for item in catalog:  # Build and Test and Operation moved from the Bolt into its Slices
        old = stages.pop(item["id"], None) if is_slice_stage(item) else None
        if old and old.get("step") != "todo" and state.get("slices"):
            first = state["slices"][0]
            first.setdefault("stages", {})[item["id"]] = old
            state["_migrated"] = f"{item['id']} moved from the Bolt into slice {first['id']}"
    for entry in state.get("slices", []):
        have = entry.setdefault("stages", {})
        for item in catalog:
            if is_slice_stage(item) and item["id"] not in have:
                if state.get("status") != "open":
                    have[item["id"]] = new_record("skip", "added after this bolt closed")
                else:
                    have[item["id"]] = new_record(*initial_decision(item, scope, False))
    for item in catalog:
        if item["per_unit"] or is_slice_stage(item) or item["id"] in stages:
            continue
        if state.get("status") != "open":
            stages[item["id"]] = new_record("skip", "added after this bolt closed")
            continue
        decision, reason = initial_decision(item, scope, brownfield)
        stages[item["id"]] = new_record(decision, reason)


# --- per-machine paths -------------------------------------------------------


def sibling(root: Path, name: str) -> Path:
    """Where a repository is expected by default: next to the planning repository."""
    return root.parent / name


def read_local(root: Path) -> dict[str, Any]:
    """The per-machine ``.aidlc-local.json``; a missing or empty file reads as empty."""
    path = root / LOCAL_FILE
    data: Any = {}
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if text.strip():
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                die(EXIT_MALFORMED, f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}")
    if not isinstance(data, dict):
        die(EXIT_MALFORMED, f"{path}: expected an object.")
    for key in ("paths", "extra"):
        if not isinstance(data.get(key), dict):
            data[key] = {}
    return data


def write_local(root: Path, data: dict[str, Any]) -> None:
    """Write the local file atomically; nothing else ever stages or commits it."""
    path = root / LOCAL_FILE
    tmp = path.with_name(LOCAL_FILE + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def resolve_repo(root: Path, name: str, legacy: Optional[str] = None) -> Optional[Path]:
    """The folder of repository ``name`` on this machine, or ``None``.

    Order: the local file, a sibling of the planning root, then ``legacy``, the absolute
    path an older state.json stored.
    """
    local = read_local(root)["paths"].get(name)
    for candidate in (local, sibling(root, name), legacy):
        if candidate and Path(str(candidate)).is_dir():
            return Path(str(candidate)).resolve()
    return None


def repo_dir(root: Path, name: str, legacy: Optional[str] = None) -> Path:
    """:func:`resolve_repo`, or the sibling folder it should be in, so a report can name it."""
    return resolve_repo(root, name, legacy) or sibling(root, name)


def note_path(local: dict[str, Any], root: Path, name: str, path: Path, keep: bool) -> bool:
    """Record ``path`` in ``local`` unless the sibling rule already finds it; True if changed.

    ``keep`` leaves an existing entry for ``name`` alone (an older state's path loses to it).
    """
    paths = local["paths"]
    near = sibling(root, name)
    if near.is_dir() and near.resolve() == path.resolve():
        return not keep and paths.pop(name, None) is not None
    if keep and name in paths:
        return False
    changed = paths.get(name) != str(path)
    paths[name] = str(path)
    return changed


def remember_repo(root: Path, name: str, path: Path) -> None:
    local = read_local(root)
    if note_path(local, root, name, path, keep=False):
        write_local(root, local)


def drop_extra(state: dict[str, Any]) -> Any:
    """Remove ``workspace.extra`` (an older state's copy) and return what it held."""
    workspace = state.get("workspace")
    if not isinstance(workspace, dict):
        return None
    held = workspace.pop("extra", None)
    if not workspace:
        state.pop("workspace", None)
    return held


def normalise_portable(bolt: Path, state: dict[str, Any]) -> bool:
    """Move the machine paths an older state.json stored into the local file.

    Called by :func:`write_state`, so it runs on the next change and only when there is
    something to move. Returns True when it moved paths.
    """
    root = planning_root(bolt)
    old_targets = [t for t in state.get("targets") or [] if "path" in t]
    ref = state.get("architecture_ref")
    old_ref = isinstance(ref, dict) and "path" in ref
    held = drop_extra(state)
    if not (old_targets or old_ref or held):
        return False
    local = read_local(root)
    for target in old_targets:
        path = target.pop("path")
        if path:
            note_path(local, root, target["repo"], Path(path), keep=True)
    if isinstance(ref, dict) and old_ref:
        path = ref.pop("path")
        if path:
            ref["repo"] = ref.get("repo") or Path(path).name
            note_path(local, root, ref["repo"], Path(path), keep=True)
        state["architecture_ref"] = {"repo": ref.get("repo"), "commit": ref.get("commit")}
    if held:
        mine = local["extra"].setdefault(str(state["id"]), [])
        names = {item["name"] for item in mine}
        mine.extend(item for item in held if item["name"] not in names)
    write_local(root, local)
    return True


def write_json_atomic(path: Path, content: dict[str, Any]) -> None:
    """Write JSON through a temp file named for this process, so a crash leaves the old file
    (and at most one ``*.tmp`` that is never committed) and two writers never share a name."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def save_if_changed(path: Path, content: dict[str, Any], touch: bool) -> None:
    """Write ``content`` atomically unless the file already holds it (``updated`` aside)."""
    if path.is_file():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = None
        if isinstance(old, dict):
            old.pop("updated", None)
            if old == {k: v for k, v in content.items() if k != "updated"}:
                return
    if touch:
        content = {**content, "updated": now()}
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, content)


def write_split(bolt: Path, state: dict[str, Any]) -> None:
    """Persist a split Bolt: the shared index, and each unit's own file if it changed."""
    shared = {k: v for k, v in state.items() if k not in ("current", "next_action")}
    shared["units"] = [{k: u[k] for k in INDEX_KEYS if k in u} for u in state["units"]]
    save_if_changed(state_path(bolt), shared, touch=False)
    for unit in state["units"]:
        own = {k: v for k, v in unit.items() if k not in INDEX_KEYS}
        save_if_changed(unit_dir(bolt, unit["id"]) / "state.json", own, touch=True)


def write_state(bolt: Path, state: dict[str, Any]) -> None:
    """Write state.json atomically: a crash leaves the old file, never half a new one."""
    state["updated"] = now()
    migrated = state.pop("_migrated", None)
    for gone in ("kind", "parent", "approver"):  # keys of Bolts written by older skills
        state.pop(gone, None)
    drop_retired_fields(state)
    written = state.get("framework")
    state["framework"] = max(written if isinstance(written, int) else 0, FRAMEWORK)
    moved = normalise_portable(bolt, state)
    if is_split(state):
        write_split(bolt, state)
    else:
        write_json_atomic(state_path(bolt), state)
    if moved:
        log_event(bolt, "portable", "", "", "machine paths moved to .aidlc-local.json")
    if migrated:
        log_event(bolt, "migrate", "", "", migrated)


def drop_retired_fields(state: dict[str, Any]) -> None:
    """Forget who recorded a checkpoint and by which channel: no longer kept."""
    holders = [state, *state.get("units", []), *state.get("slices", [])]
    for holder in holders:
        for record in (holder.get("stages") or {}).values():
            if isinstance(record, dict):
                record.pop("recorded_by", None)
                record.pop("channel", None)


_ACTORS: dict[str, str] = {}


def actor(root: Path) -> str:
    """Who is running the script: ``AIDLC_ACTOR``, else the git ``user.name`` of the
    planning repository, else empty. Not switched off by ``--no-git`` or ``AIDLC_GIT=off``,
    which only stop commits and pushes."""
    if "AIDLC_ACTOR" in os.environ:
        return " ".join(os.environ["AIDLC_ACTOR"].split())
    key = str(root)
    if key not in _ACTORS:
        name = ""
        if root.is_dir():
            inside = run_git(root, "rev-parse", "--is-inside-work-tree")
            if inside.returncode == 0 and inside.stdout.strip() == "true":
                name = " ".join(run_git(root, "config", "user.name").stdout.split())
        _ACTORS[key] = name
    return _ACTORS[key]


def log_event(
    bolt: Path, event: str, stage: str = "", by: str = "", note: str = "", unit: str = ""
) -> None:
    def clean(value: str) -> str:
        text = " ".join(value.replace("|", "/").split())
        return text or "-"

    if not by and not event.startswith("gate-"):
        who = actor(planning_root(bolt))
        by = f"agent:{who}" if who else ""
    line = " | ".join([now(), clean(event), clean(stage), clean(by or "agent"), clean(note)])
    folder = unit_dir(bolt, unit) if unit else bolt
    with (folder / "log.md" if folder.is_dir() else bolt / "log.md").open(
        "a", encoding="utf-8"
    ) as handle:
        handle.write(line + "\n")


def require_open(state: dict[str, Any]) -> None:
    if state.get("status") != "open":
        raise Fail(EXIT_FINDINGS, f"bolt is {state.get('status')}; it no longer accepts changes.")


# --- stage records -----------------------------------------------------------


def new_record(decision: str, reason: str, step: str = "todo") -> dict[str, Any]:
    return {
        "decision": decision,
        "reason": reason,
        "step": step,
        "approved_at": None,
        "approved_by": None,
    }


def initial_decision(stage: dict[str, Any], scope: str, brownfield: bool) -> tuple[str, str]:
    """The decision ``open`` gives a stage, from the scope and the targets only."""
    if stage["id"] == "workspace-detection":
        return "execute", ""
    if scope not in stage["scopes"]:
        return "skip", f"outside the {scope} scope"
    if stage["id"] == "reverse-engineering" and not brownfield:
        return "skip", "no brownfield target"
    conditional = stage["conditional"]
    if conditional is True or (isinstance(conditional, list) and scope in conditional):
        return "pending", ""
    return "execute", ""


def unit_stage_records(
    catalog: list[dict[str, Any]],
    scope: str,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    records: dict[str, Any] = dict(existing or {})
    for item in catalog:
        if item["per_unit"] and item["id"] not in records:
            decision, reason = initial_decision(item, scope, True)
            records[item["id"]] = new_record(decision, reason)
    return records


def new_slice(
    sid: str,
    name: str = "",
    owner: Optional[str] = None,
    depends_on: Optional[list[str]] = None,
) -> dict[str, Any]:
    """A Slice record: who it is, what it waits for and whether it is ready."""
    return {
        "id": sid,
        "name": name,
        "owner": owner,
        "depends_on": depends_on or [],
        "ready": None,
        "stages": {},
    }


def single_slice_ready() -> dict[str, Any]:
    return {"at": now(), "note": "single-Slice Bolt", "gaps": []}


def find_unit(state: dict[str, Any], unit: str) -> dict[str, Any]:
    for item in state["units"]:
        if item["id"] == unit:
            return item
    known = ", ".join(u["id"] for u in state["units"]) or "none loaded"
    die(EXIT_USAGE, f"unknown unit '{unit}' (units: {known}). Load them with `units --set`.")


def get_record(state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]) -> dict[str, Any]:
    """The record of a stage; ``unit`` is the Unit id, or the Slice id for a per-Slice stage."""
    if stage["per_unit"] or is_slice_stage(stage):
        if unit is None:
            die(EXIT_USAGE, f"stage '{stage['id']}' runs once per unit; pass --unit.")
        holder = find_slice(state, unit) if is_slice_stage(stage) else find_unit(state, unit)
        records = holder.setdefault("stages", {})
        if stage["id"] not in records:
            records[stage["id"]] = new_record("pending", "")
        return records[stage["id"]]
    if unit is not None:
        die(EXIT_USAGE, f"stage '{stage['id']}' is not per unit; drop --unit.")
    try:
        return state["stages"][stage["id"]]
    except KeyError:
        die(EXIT_MALFORMED, f"state.json has no record for stage '{stage['id']}'.")


Slot = tuple[dict[str, Any], Optional[str]]


def slots(state: dict[str, Any], catalog: list[dict[str, Any]]) -> list[Slot]:
    """Every (stage, unit or slice) in working order; per-unit stages run unit by unit and
    per-Slice stages Slice by Slice."""
    result: list[Slot] = []
    expanded: set[str] = set()
    for item in catalog:
        kind = "per_unit" if item["per_unit"] else "per_slice" if is_slice_stage(item) else ""
        if not kind:
            result.append((item, None))
        elif kind not in expanded:
            expanded.add(kind)
            group = [sub for sub in catalog if sub.get(kind)]
            if kind == "per_unit":
                owners, empty = live_units(state), not state["units"]
            else:  # a Slice whose Units are all cancelled has nothing left to build or test
                owners = [s for s in state["slices"] if not slice_cancelled(state, s["id"])]
                empty = not state["slices"]
            if not owners and empty:  # the "no Units yet" placeholder: only when none exist
                result.append((group[0], None))
            for owner in owners:
                for sub in group:
                    result.append((sub, owner["id"]))
    return result


def slot_record(
    state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]
) -> Optional[dict[str, Any]]:
    if stage["per_unit"] or is_slice_stage(stage):
        if unit is None:
            return None
        holder = find_slice(state, unit) if is_slice_stage(stage) else find_unit(state, unit)
        return holder.get("stages", {}).get(stage["id"])
    return state["stages"].get(stage["id"])


def is_done(record: Optional[dict[str, Any]]) -> bool:
    return record is not None and (record["decision"] == "skip" or record["step"] == "approved")


def is_construction_unit_stage(stage: dict[str, Any]) -> bool:
    return bool(stage["per_unit"] and stage["phase"] == "construction")


def story_missing(state: dict[str, Any], unit: str) -> bool:
    if state["jira"]["mode"] == "off":
        return False
    return not find_unit(state, unit).get("story")


def slot_next(
    state: dict[str, Any],
    item: dict[str, Any],
    unit: Optional[str],
    record: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """What to do for one not-done slot; for a per-Slice stage ``unit`` is the Slice id."""
    base: dict[str, Any] = {
        "done": False,
        "stage": item["id"],
        **subject(item, unit),
        "skill": item["skill"],
        "reference": item["reference"],
        "tier": item.get("tier"),
    }
    if is_slice_stage(item):
        unit = None
    if record is None:
        blocked = "units are not loaded; run `units --set` before per-unit stages"
        if is_slice_stage(item):
            blocked = "there is no Slice yet; add one with `slice --add`"
        return {**base, "step": None, "action": "load-units", "blocked": blocked}
    base["step"] = record["step"]
    if record["decision"] == "pending":
        hint: dict[str, Any] = {"runs_when": item.get("runs_when", "")}
        if unit:
            hint["unit_kind"] = find_unit(state, unit).get("kind")
        return {**base, "action": "decide", **hint}
    action = ACTIONS[record["step"]]
    if action == "ask" and not item["questions"]:
        action = "produce"
    result = {**base, "action": action}
    if unit and is_construction_unit_stage(item) and story_missing(state, unit):
        result["jira"] = (
            f"unit {unit} has no Jira story: file it, then `jira --unit {unit} --story KEY`, "
            "or `jira --off --reason`."
        )
    return result


def compute_next(
    state: dict[str, Any], catalog: list[dict[str, Any]], bolt: Optional[Path] = None
) -> dict[str, Any]:
    for item, unit in slots(state, catalog):
        record = slot_record(state, item, unit)
        if is_done(record):
            continue
        if is_split(state) and (item["per_unit"] or is_slice_stage(item)) and unit is not None:
            rows = [
                next_for_unit(bolt, state, catalog, u["id"])
                for u in live_units(state)
                if unit_slot(state, catalog, u["id"]) is not None
            ]
            slice_rows_ = [
                next_for_slice(bolt, state, catalog, s["id"])
                for s in state["slices"]
                if slice_slot(state, catalog, s["id"]) is not None
            ]
            return {
                "done": False,
                "stage": None,
                "unit": None,
                "action": "units",
                "units": rows,
                "slices": slice_rows_,
            }
        return slot_next(state, item, unit, record)
    return {"done": True, "stage": None, "unit": None, "action": "close"}


# --- units: owners, waiting and unit-scoped routing ----------------------------


def blocked_by(
    state: dict[str, Any], catalog: list[dict[str, Any]], unit_id: str
) -> list[dict[str, Any]]:
    """The dependencies of a unit that are not satisfied yet."""
    waiting: list[dict[str, Any]] = []
    known = {u["id"] for u in state["units"]}
    for dep in find_unit(state, unit_id).get("depends_on") or []:
        other, on = dep["unit"], dep.get("on", "done")
        reason = ""
        if other in known and is_cancelled(find_unit(state, other)):
            reason = f"unit {other} is cancelled; update depends_on"
        elif on == "contract":
            has_stage = any(i["id"] == "contract-design" for i in catalog)
            if has_stage and not is_done(state["stages"].get("contract-design")):
                reason = "contract-design is not done"
        elif other not in known:
            reason = f"unit {other} is not loaded"
        else:
            for item in catalog:
                if item["per_unit"] and not is_done(slot_record(state, item, other)):
                    reason = f"{other} has not finished {item['id']}"
                    break
        if reason:
            waiting.append({"unit": other, "on": on, "reason": reason})
    return waiting


def waits_sentence(waiting: list[dict[str, Any]]) -> str:
    return "waits for " + ", ".join(f"{w['unit']} ({w['on']})" for w in waiting)


def unit_slot(
    state: dict[str, Any], catalog: list[dict[str, Any]], unit_id: str
) -> Optional[dict[str, Any]]:
    """The first per-unit stage of ``unit_id`` that is not done."""
    for item in catalog:
        if item["per_unit"] and not is_done(slot_record(state, item, unit_id)):
            return item
    return None


def slice_slot(
    state: dict[str, Any], catalog: list[dict[str, Any]], sid: str
) -> Optional[dict[str, Any]]:
    """The first per-Slice stage of ``sid`` that is not done."""
    for item in catalog:
        if is_slice_stage(item) and not is_done(slot_record(state, item, sid)):
            return item
    return None


def verification_skipped(
    catalog: list[dict[str, Any]], stages: Optional[dict[str, Any]], per_slice: bool
) -> bool:
    """True when a stage that checks a verdict was skipped: the work is done, never verified."""
    return any(
        bool(item.get("verdict"))
        and bool(item.get("per_slice")) == per_slice
        and (stages or {}).get(item["id"], {}).get("decision") == "skip"
        for item in catalog
    )


def slice_dep_waits(state: dict[str, Any], catalog: list[dict[str, Any]], sid: str) -> list[str]:
    """The Slices ``sid`` depends on that are not verified yet."""
    return [
        f"waits for slice {dep} (verified)"
        for dep in find_slice(state, sid).get("depends_on") or []
        if slice_status(state, catalog, dep) not in ("verified", "released", "cancelled")
        and not verification_skipped(catalog, find_slice(state, dep).get("stages"), True)
    ]


def slice_waits(state: dict[str, Any], catalog: list[dict[str, Any]], sid: str) -> list[str]:
    """What keeps the Slice's own stages from starting. Report only: nothing is refused."""
    waits: list[str] = []
    if not find_slice(state, sid).get("ready"):
        waits.append(f"slice {sid} is not ready")
    open_units = [
        u["id"] for u in slice_units(state, sid) if unit_slot(state, catalog, u["id"]) is not None
    ]
    if open_units:
        waits.append("units not finished: " + ", ".join(open_units))
    return waits + slice_dep_waits(state, catalog, sid)


def next_for_slice(
    bolt: Optional[Path], state: dict[str, Any], catalog: list[dict[str, Any]], sid: str
) -> dict[str, Any]:
    """``next`` for one Slice: its first open stage and what it waits for."""
    find_slice(state, sid)
    item = slice_slot(state, catalog, sid)
    if slice_cancelled(state, sid):
        item = None  # nothing is left to do for it
    if item is None:
        return {
            "done": True,
            "stage": None,
            "unit": None,
            "slice": sid,
            "action": "none",
            "blocked_by": [],
        }
    result = slot_next(state, item, sid, slot_record(state, item, sid))
    result["blocked_by"] = slice_waits(state, catalog, sid)
    if result["blocked_by"]:
        result["blocked"] = "; ".join(result["blocked_by"])
    return with_context(bolt, state, catalog, result)


def next_for_unit(
    bolt: Optional[Path], state: dict[str, Any], catalog: list[dict[str, Any]], unit_id: str
) -> dict[str, Any]:
    """``next`` for one unit: its own first open stage, with what it waits for."""
    if is_cancelled(find_unit(state, unit_id)):
        return {
            "done": True,
            "stage": None,
            "unit": unit_id,
            "action": "cancelled",
            "blocked_by": [],
        }
    waiting = blocked_by(state, catalog, unit_id)
    first = min((i["order"] for i in catalog if i["per_unit"]), default=0)
    for item in catalog:
        record = state["stages"].get(item["id"])
        if not item["per_unit"] and item["order"] < first and not is_done(record):
            result = slot_next(state, item, None, record)
            result.update({"unit": unit_id, "blocked_by": waiting})
            result["blocked"] = f"inception is not finished: {item['id']}"
            return with_context(bolt, state, catalog, result)
    item = unit_slot(state, catalog, unit_id)
    if item is None:
        return {"done": True, "stage": None, "unit": unit_id, "action": "none", "blocked_by": []}
    result = slot_next(state, item, unit_id, slot_record(state, item, unit_id))
    result["blocked_by"] = waiting
    mine = next(
        (s for s in state["slices"] if s["id"] == find_unit(state, unit_id).get("slice")), None
    )
    if waiting:
        result["blocked"] = waits_sentence(waiting)
    elif mine is not None and not mine.get("ready"):
        result["blocked"] = f"slice {mine['id']} is not ready"
    return with_context(bolt, state, catalog, result)


def cmd_next(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    if args.unit:
        return {"ok": True, **next_for_unit(bolt, state, catalog, args.unit)}
    if args.slice:
        return {"ok": True, **next_for_slice(bolt, state, catalog, args.slice)}
    if args.mine:
        who = actor(planning_root(bolt))
        if not who:
            raise Fail(EXIT_FINDINGS, "the git user name is not set; run `git config user.name`.")
        mine = [u["id"] for u in live_units(state) if same_person(u.get("owner") or "", who)]
        rows = [next_for_unit(bolt, state, catalog, uid) for uid in mine]
        owned = [s["id"] for s in state["slices"] if same_person(s.get("owner") or "", who)]
        slice_rows_ = [next_for_slice(bolt, state, catalog, sid) for sid in owned]
        return {"ok": True, "actor": who, "units": rows, "slices": slice_rows_}
    nxt = compute_next(state, catalog, bolt)
    return {"ok": True, **with_context(bolt, state, catalog, nxt)}


def cmd_brief(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    """A unit's starting page. It points at files; it never copies their text."""
    uid = args.unit
    unit = find_unit(state, uid)
    nxt = next_for_unit(bolt, state, catalog, uid)
    waiting = {(w["unit"], w["on"]) for w in nxt["blocked_by"]}
    facts = [
        ("Bolt", f"{state['id']}: {state['title']}"),
        ("Kind", unit.get("kind") or "-"), ("Owner", unit.get("owner") or "-"),
        ("Repository", unit.get("repo") or "-"), ("Slice", unit.get("slice") or "-"),
        ("Jira story", unit.get("story") or "-"),
    ]  # fmt: skip
    out = [f"# Unit {uid}: {unit['name']}", "", "| Fact | Value |", "| --- | --- |"]
    out += [f"| {key} | {value} |" for key, value in facts]
    out += ["", "## Waits for", ""]
    deps = unit.get("depends_on") or []
    out += [
        f"- {d['unit']} ({d['on']}): "
        + ("waiting" if (d["unit"], d["on"]) in waiting else "satisfied")
        for d in deps
    ] or ["nothing"]
    item = unit_slot(state, catalog, uid)
    rows = input_rows(bolt, state, catalog, item, uid)[0] if item else []
    out += ["", "## Read first", ""]
    out += [f"- `{row['path']}` ({row['mode']})" for row in rows] or ["nothing"]
    out += ["", f"Resolve any id with `aidlc_refs.py show --bolt {bolt} <id>`", ""]
    out += ["## Changed since you last produced", ""]
    changed = [
        f"- {sub['id']}: {report_text(report)}"
        for sub in catalog
        if sub["per_unit"] and (report := context_report(bolt, state, catalog, sub, uid))
    ]
    out += changed or ["nothing"]
    out += ["", "## Next", ""]
    if nxt["stage"]:
        out += [
            f"- Stage: {nxt['stage']}",
            f"- Action: {nxt['action']}",
            f"- Skill: {nxt['skill']}",
        ]
        if nxt.get("blocked"):
            out.append(f"- Blocked: {nxt['blocked']}")
    else:
        out.append("Every stage of this unit is done.")
    markdown = "\n".join(out) + "\n"
    result: dict[str, Any] = {"ok": True, "unit": uid, "markdown": markdown}
    if args.write:
        file = bolt / "docs" / "construction" / uid / "brief.md"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(markdown, encoding="utf-8")
        result["path"] = str(file)
    return result


def owner_warning(
    state: dict[str, Any], unit_id: Optional[str], who: str, slice_id: Optional[str] = None
) -> str:
    """One line when the Unit (or Slice) belongs to someone else; empty otherwise. It never
    refuses: the engineer may well be the right person to move it on, so the owner is told."""
    if unit_id is not None:
        what, holder = f"unit {unit_id}", find_unit(state, unit_id)
    elif slice_id is not None:
        what, holder = f"slice {slice_id}", find_slice(state, slice_id)
    else:
        return ""
    owner = holder.get("owner")
    if not owner or not who or same_person(owner, who):
        return ""
    return f"{what} is owned by {owner}; you are {who}"


def guard_owner(
    bolt: Path, state: dict[str, Any], unit_id: Optional[str], slice_id: Optional[str] = None
) -> tuple[str, list[str]]:
    """The log suffix and the ``warnings`` for a step on a Unit or Slice owned by someone else."""
    text = owner_warning(state, unit_id, actor(planning_root(bolt)), slice_id)
    return (f" ({text})", [text]) if text else ("", [])


def stage_owner(
    bolt: Path, state: dict[str, Any], stage: dict[str, Any], key: Optional[str]
) -> tuple[str, list[str]]:
    """``guard_owner`` for the Unit or the Slice a stage command is about."""
    on_slice = is_slice_stage(stage)
    return guard_owner(bolt, state, None if on_slice else key, key if on_slice else None)


def cmd_assign(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    owner = " ".join((args.owner or "").split())
    if not owner:
        die(EXIT_USAGE, "--owner must not be blank.")
    if bool(args.unit) == bool(args.slice):
        die(EXIT_USAGE, "give --unit or --slice, not both and not neither.")
    key = args.unit or args.slice
    holder = find_unit(state, key) if args.unit else find_slice(state, key)
    old = holder.get("owner") or "-"
    holder["owner"] = owner
    nxt = commit(bolt, state, catalog)
    log_event(bolt, "assign", "", "", f"[{key}] {old} -> {owner}", args.unit or "")
    previous = None if old == "-" else old
    return {
        "ok": True,
        "unit" if args.unit else "slice": key,
        "owner": owner,
        "previous": previous,
        "next": nxt,
    }


def describe_next(nxt: dict[str, Any]) -> str:
    if nxt["done"]:
        return "all stages done; close the bolt"
    if nxt["action"] == "units":
        parts = [
            f"{r['unit']} "
            + (
                "waits for " + ", ".join(w["unit"] for w in r["blocked_by"])
                if r["blocked_by"]
                else r["stage"]
            )
            for r in nxt["units"]
        ]
        kinds = [("units", parts)]
        kinds.append(
            (
                "slices",
                [
                    f"slice {r['slice']}: " + ("waiting" if r["blocked_by"] else r["stage"])
                    for r in nxt["slices"]
                ],
            )
        )
        return "; ".join(f"{name} in progress: " + ", ".join(rows) for name, rows in kinds if rows)
    where = where_text(nxt)
    if nxt["action"] == "load-units":
        return f"load units before {where}"
    return f"{nxt['action']}: {where} (skill {nxt['skill']})"


def refresh(state: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    nxt = compute_next(state, catalog)
    state["current"] = {"stage": nxt["stage"], "unit": nxt["unit"]}
    if nxt.get("slice"):
        state["current"]["slice"] = nxt["slice"]
    state["next_action"] = describe_next(nxt)
    return nxt


def commit(bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    nxt = refresh(state, catalog)
    write_state(bolt, state)
    return nxt


# --- open --------------------------------------------------------------------


def git(path: Path, *args: str) -> Optional[str]:
    try:
        done = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def classify(path: Path) -> tuple[str, str]:
    """Return ``(kind, rule)``: brownfield when tracked source goes beyond scaffolding."""
    tracked = git(path, "ls-files")
    if tracked is not None:
        names = [Path(line) for line in tracked.splitlines() if line]
        origin = "tracked"
    else:
        names = [
            p.relative_to(path)
            for p in path.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(path).parts
        ]
        origin = "found (not a git checkout)"
    source = [
        n for n in names if n.suffix.lower() in SOURCE_SUFFIXES and n.name not in SCAFFOLD_NAMES
    ]
    if source:
        return "brownfield", f"{len(source)} {origin} source file(s) beyond scaffolding"
    return "greenfield", f"no {origin} source files beyond scaffolding"


def parse_pair(spec: str, flag: str, allow_empty: bool = False) -> tuple[str, str]:
    """Split ``name=path``; an empty path is allowed only where it means "remove"."""
    name, sep, raw = spec.partition("=")
    if not sep or not name.strip() or (not raw and not allow_empty):
        die(EXIT_USAGE, f"{flag} '{spec}' must look like name=path.")
    return name.strip(), raw


def existing_dir(raw: str, what: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        die(EXIT_INPUT, f"{path}: {what} is not a directory.")
    return path


def make_target(spec: str, flag: str) -> tuple[dict[str, Any], str, Path]:
    """A classified target record from ``name=path``, the rule that matched and the path.

    The record holds no path: where the repository lives is per machine.
    """
    name, raw = parse_pair(spec, flag)
    path = existing_dir(raw, f"target for '{name}'")
    kind, rule = classify(path)
    record = {"repo": name, "kind": kind, "codekb_commit": None}
    return record, f"{name}: {kind} ({rule})", path


def cmd_open(args: argparse.Namespace, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    if not SLUG.match(args.slug):
        die(EXIT_USAGE, "--slug must be lower-case letters, digits and hyphens.")
    date = args.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    if not DATE.match(date):
        die(EXIT_USAGE, "--date must be YYYY-MM-DD.")
    root = Path(args.root)
    if not root.is_dir():
        die(EXIT_INPUT, f"{root}: --root is not a directory.")
    bolt_id = f"{date}-{args.slug}"
    bolt = root / "bolts" / bolt_id
    if bolt.exists():
        raise Fail(EXIT_FINDINGS, f"{bolt}: bolt already exists. Resume it with `status`.")
    mode = args.units or units_mode(root)

    base = root.resolve()
    targets: list[dict[str, Any]] = []
    rules: list[str] = []
    places: list[tuple[str, Path]] = []
    for spec in args.target or []:
        record, rule, path = make_target(spec, "--target")
        targets.append(record)
        rules.append(rule)
        places.append((record["repo"], path))

    architecture: Optional[dict[str, Any]] = None
    if args.architecture_ref:
        ref = Path(args.architecture_ref).expanduser().resolve()
        if not ref.is_dir():
            die(EXIT_INPUT, f"{ref}: --architecture-ref is not a directory.")
        sha = git(ref, "rev-parse", "HEAD")
        architecture = {"repo": ref.name, "commit": sha.strip() if sha else None}
        places.append((ref.name, ref))
        if sha is None:
            LOG.warning("%s: not a git checkout; the registry commit is recorded as null.", ref)

    brownfield = any(t["kind"] == "brownfield" for t in targets)
    stages: dict[str, Any] = {}
    for item in catalog:
        if item["per_unit"] or is_slice_stage(item):
            continue
        decision, reason = initial_decision(item, args.scope, brownfield)
        step = "produced" if item["id"] == "workspace-detection" else "todo"
        stages[item["id"]] = new_record(decision, reason, step)

    units: list[dict[str, Any]] = []
    slices: list[dict[str, Any]] = []
    if args.scope in DEFAULT_UNIT_SCOPES:
        units = [
            {
                "id": "u1",
                "name": args.title,
                "kind": None,
                "slice": "s1",
                "stages": unit_stage_records(catalog, args.scope),
                "story": None,
                "story_done": None,
            }
        ]
        slices = [{**new_slice("s1", args.title), "ready": single_slice_ready()}]

    state: dict[str, Any] = {
        "schema": 1,
        "id": bolt_id,
        "title": args.title,
        "intent": args.intent,
        "status": "open",
        "scope": args.scope,
        "depth": args.depth or DEFAULT_DEPTH[args.scope],
        "owner": args.owner or "",
        "created": date,
        "updated": now(),
        "targets": targets,
        "architecture_ref": architecture,
        "decision_seq": 0,
        "stages": stages,
        "units": units,
        "slices": slices,
        "current": {"stage": None, "unit": None},
        "next_action": "",
        "parked": None,
        "jira": {"mode": None, "reason": "", "epic": None},
    }
    if mode == "split":
        state["unit_state"] = "split"

    for name, path in places:
        remember_repo(base, name, path)
    folders = [
        "inputs",
        "knowledge/extracted",
        "architecture",
        "docs/inception",
        "docs/construction",
        "docs/slices",
    ]
    for folder in folders:
        (bolt / folder).mkdir(parents=True, exist_ok=True)
        (bolt / folder / ".gitkeep").touch()
    (bolt / "log.md").touch()
    backfill_stages(state, catalog)  # seeds the default Slice's stages
    nxt = commit(bolt, state, catalog)
    log_event(bolt, "open", "", "", f"scope={args.scope} depth={state['depth']}")
    for rule in rules:
        log_event(bolt, "classify", "workspace-detection", "", rule)
    return {
        "ok": True,
        "bolt": str(bolt),
        "id": bolt_id,
        "targets": targets,
        "architecture_ref": architecture,
        "codekb": codekb_status(root.resolve(), targets),
        "workspace": write_workspace(bolt, state, None, fetch=False),
        "next": nxt,
    }


# --- workspace and checkouts -------------------------------------------------


def extras(bolt: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    """Extra folders of this bolt: the local file's, then any an older state still holds."""
    mine = list(read_local(planning_root(bolt))["extra"].get(str(state["id"])) or [])
    names = {item["name"] for item in mine}
    held = (state.get("workspace") or {}).get("extra") or []
    return mine + [item for item in held if item["name"] not in names]


def workspace_folders(bolt: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    """Every folder a person works in for this bolt, in a fixed order."""
    root = planning_root(bolt)
    folders = [
        {"name": f"bolt: {DATE_PREFIX.sub('', state['id'])}", "path": str(bolt.resolve())},
        {"name": "planning repo", "path": str(root)},
    ]
    ref = state.get("architecture_ref") or {}
    ref_name = ref.get("repo") or (Path(ref["path"]).name if ref.get("path") else "")
    if ref_name:
        folders.append(
            {"name": "adr registry", "path": str(repo_dir(root, ref_name, ref.get("path")))}
        )
    for target in state["targets"]:
        where = repo_dir(root, target["repo"], target.get("path"))
        folders.append({"name": f"target: {target['repo']}", "path": str(where)})
    for extra in extras(bolt, state):
        folders.append({"name": extra["name"], "path": extra["path"]})
    return folders


def quote_arg(text: str) -> str:
    """Double-quote for a POSIX shell: escape the four characters that stay special."""
    return '"' + re.sub(r'(["\\$`])', r"\\\1", text) + '"'


def claude_command(folders: list[dict[str, str]], root: Path) -> str:
    dirs = [item["path"] for item in folders if item["path"] != str(root)]
    return " ".join(["claude", *(f"--add-dir {quote_arg(path)}" for path in dirs)])


def git_fetch(path: Path) -> Optional[str]:
    """Fetch origin without any prompt; return the error as text, or ``None``."""
    try:
        done = subprocess.run(
            ["git", "-C", str(path), "fetch", "--quiet", "origin"],
            capture_output=True,
            text=True,
            timeout=FETCH_TIMEOUT,
            check=False,
            stdin=subprocess.DEVNULL,
            env={**os.environ, **FETCH_ENV},
        )
    except subprocess.TimeoutExpired:
        return f"git fetch timed out after {FETCH_TIMEOUT} s"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"git fetch could not run: {exc}"
    if done.returncode == 0:
        return None
    lines = [line.strip() for line in done.stderr.splitlines() if line.strip()]
    return (lines[-1] if lines else f"git fetch exited {done.returncode}")[:300]


def default_branch(path: Path) -> Optional[str]:
    ref = (git(path, "symbolic-ref", "--quiet", ORIGIN_REFS + "HEAD") or "").strip()
    if ref.startswith(ORIGIN_REFS):
        return ref[len(ORIGIN_REFS) :]
    for name in ("main", "master"):
        if git(path, "rev-parse", "--verify", "--quiet", ORIGIN_REFS + name) is not None:
            return name
    return None


def inspect_checkout(name: str, role: str, raw: str, fetch: bool) -> dict[str, Any]:
    """How far a checkout is from its origin's default branch, from local refs only.

    Nothing here changes the working tree, the index or a branch: ``status`` runs
    without optional locks, and ``--fetch`` only updates remote-tracking refs.
    """
    path = Path(raw)
    row: dict[str, Any] = {
        "name": name,
        "role": role,
        "path": raw,
        "exists": path.is_dir(),
        "is_git": False,
        "fetched": False,
        "stale": False,
    }
    if not row["exists"]:
        return {**row, "note": f"the folder does not exist; {PATH_HINT}"}
    if (git(path, "rev-parse", "--is-inside-work-tree") or "").strip() != "true":
        return {**row, "note": "not a git repository"}
    row["is_git"] = True
    if fetch:
        error = git_fetch(path)
        row["fetched"] = error is None
        if error:
            row["fetch_error"] = error
    branch = (git(path, "symbolic-ref", "--quiet", "--short", "HEAD") or "").strip() or None
    base = default_branch(path)
    behind: Optional[int] = None
    ahead: Optional[int] = None
    if base:
        spread = f"{ORIGIN_REFS}{base}...HEAD"
        counts = (git(path, "rev-list", "--left-right", "--count", spread) or "").split()
        if len(counts) == 2:
            behind, ahead = int(counts[0]), int(counts[1])
    porcelain = git(path, "--no-optional-locks", "status", "--porcelain")
    head_line = (git(path, "log", "-1", "--format=%h%x09%cI", "HEAD") or "").strip()
    short, _, date = head_line.partition("\t")
    row.update(
        {
            "branch": branch,
            "default_branch": base,
            "behind": behind,
            "ahead": ahead,
            "dirty": None if porcelain is None else len(porcelain.splitlines()),
            "head": {"commit": short, "date": date} if short else None,
            "stale": base is not None and ((behind or 0) > 0 or branch != base),
        }
    )
    if base is None:
        row["note"] = "no origin default branch found; freshness unknown"
    return row


def write_workspace(
    bolt: Path, state: dict[str, Any], out: Optional[Path], fetch: bool
) -> dict[str, Any]:
    """Write the multi-root workspace file and report each checkout; targets stay untouched."""
    folders = workspace_folders(bolt, state)
    file = out if out is not None else bolt / f"{state['id']}{WORKSPACE_SUFFIX}"
    if not file.parent.is_dir():
        die(EXIT_INPUT, f"{file.parent}: folder for --out does not exist.")
    file.write_text(json.dumps({"folders": folders}, indent=2) + "\n", encoding="utf-8")
    root = planning_root(bolt)
    checkouts = [
        inspect_checkout(t["repo"], "target", str(repo_dir(root, t["repo"], t.get("path"))), fetch)
        for t in state["targets"]
    ]
    for extra in extras(bolt, state):
        row = inspect_checkout(extra["name"], "extra", extra["path"], fetch)
        if row["is_git"]:
            checkouts.append(row)
    return {
        "file": str(file.resolve()),
        "folders": folders,
        "claude_command": claude_command(folders, planning_root(bolt)),
        "checkouts": checkouts,
        "stale": [row["name"] for row in checkouts if row["stale"]],
    }


def cmd_workspace(bolt: Path, state: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if args.extra:
        require_open(state)
        current = extras(bolt, state)
        drop_extra(state)  # an older state's copy; the local file now holds the list
        changes: list[str] = []
        for spec in args.extra:
            name, raw = parse_pair(spec, "--extra", allow_empty=True)
            names = [item["name"] for item in current]
            if not raw:
                if name not in names:
                    known = ", ".join(names) or "none"
                    die(EXIT_INPUT, f"no extra folder named '{name}' (extras: {known}).")
                current = [item for item in current if item["name"] != name]
                changes.append(f"removed {name}")
                continue
            entry = {"name": name, "path": str(existing_dir(raw, f"extra folder '{name}'"))}
            if name in names:
                current[names.index(name)] = entry
            else:
                current.append(entry)
            changes.append(f"{name}={entry['path']}")
        local = read_local(planning_root(bolt))
        if current:
            local["extra"][str(state["id"])] = current
        else:
            local["extra"].pop(str(state["id"]), None)
        write_local(planning_root(bolt), local)
        write_state(bolt, state)
        log_event(bolt, "workspace", "", "", "; ".join(changes))
    out = Path(args.out).expanduser() if args.out else None
    return {"ok": True, **write_workspace(bolt, state, out, fetch=args.fetch)}


def sync_reverse_engineering(
    state: dict[str, Any], catalog: list[dict[str, Any]], before: bool, after: bool
) -> str:
    """Re-apply open's brownfield rule, unless a person decided or the stage has started."""
    stage = stage_def(catalog, "reverse-engineering")
    record = state["stages"].get(stage["id"])
    if record is None:
        return "no record"
    old = initial_decision(stage, state["scope"], before)
    new = initial_decision(stage, state["scope"], after)
    if old == new:
        return f"unchanged ({record['decision']})"
    if record["step"] != "todo" or (record["decision"], record["reason"]) != old:
        return f"left as {record['decision']}: decided by hand or already started"
    record["decision"], record["reason"] = new
    return f"now {new[0]}"


def cmd_target(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    targets = list(state["targets"])
    before = any(t["kind"] == "brownfield" for t in targets)
    root = planning_root(bolt)
    if args.add:
        record, rule, path = make_target(args.add, "--add")
        old = next((t for t in targets if t["repo"] == record["repo"]), None)
        if old is not None:
            if resolve_repo(root, old["repo"], old.get("path")) == path:
                record["codekb_commit"] = old.get("codekb_commit")
            targets = [record if t["repo"] == record["repo"] else t for t in targets]
        else:
            targets.append(record)
        remember_repo(root, record["repo"], path)
        note = f"add {rule}"
    else:
        names = [t["repo"] for t in targets]
        if args.remove not in names:
            known = ", ".join(names) or "none"
            die(EXIT_INPUT, f"no target named '{args.remove}' (targets: {known}).")
        targets = [t for t in targets if t["repo"] != args.remove]
        note = f"remove {args.remove}"
    state["targets"] = targets
    after = any(t["kind"] == "brownfield" for t in targets)
    verdict = sync_reverse_engineering(state, catalog, before, after)
    nxt = commit(bolt, state, catalog)
    log_event(bolt, "target", "workspace-detection", "", f"{note}; reverse-engineering {verdict}")
    return {
        "ok": True,
        "targets": targets,
        "change": note,
        "reverse_engineering": verdict,
        "codekb": codekb_status(root, targets),
        "workspace": write_workspace(bolt, state, None, fetch=False),
        "next": nxt,
    }


# --- read-only commands ------------------------------------------------------


def phase_progress(state: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    progress = {phase: {"done": 0, "total": 0, "skipped": 0} for phase in PHASES}
    for item, unit in slots(state, catalog):
        record = slot_record(state, item, unit)
        if record is None:
            continue
        entry = progress[item["phase"]]
        entry["total"] += 1
        if record["decision"] == "skip":
            entry["skipped"] += 1
        if is_done(record):
            entry["done"] += 1
    return progress


def jira_facts(state: dict[str, Any]) -> dict[str, Any]:
    units = state["units"]
    return {
        **state["jira"],
        "stories_filed": sum(1 for u in units if u.get("story")),
        "stories_done": sum(1 for u in units if u.get("story_done")),
        "units": len(units),
    }


def jira_line(state: dict[str, Any]) -> str:
    jira = jira_facts(state)
    if jira["mode"] == "off":
        return f"Jira: off ({str(jira['reason'])[:80]})"
    if jira["mode"] is None and not jira["epic"]:
        return "Jira: not set"
    return (
        f"Jira: epic {jira['epic'] or 'none'}, stories {jira['stories_filed']}/{jira['units']}"
        f" filed, {jira['stories_done']} done"
    )


def unit_detail(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], unit_id: str
) -> dict[str, Any]:
    unit = find_unit(state, unit_id)
    nxt = next_for_unit(bolt, state, catalog, unit_id)
    return {
        "id": unit_id,
        "owner": unit.get("owner"),
        "repo": unit.get("repo"),
        "blocked_by": nxt["blocked_by"],
        "stage": nxt["stage"],
        "action": nxt["action"],
        "verification_skipped": verification_skipped(catalog, unit.get("stages"), False),
        "context_note": reliance_note(bolt, state, catalog, unit_id),
    }


def cmd_status(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], fmt: str
) -> dict[str, Any]:
    nxt = compute_next(state, catalog)
    progress = phase_progress(state, catalog)
    facts = {
        "id": state["id"],
        "title": state["title"],
        "intent": state["intent"],
        "status": state["status"],
        "scope": state["scope"],
        "depth": state["depth"],
        "phases": progress,
        "units": len(state["units"]),
        "slices": len(state["slices"]),
        "current": state["current"],
        "step": nxt.get("step"),
        "action": nxt["action"],
        "next_action": state["next_action"],
        "parked": state["parked"],
        "jira": jira_facts(state),
    }
    details = [unit_detail(bolt, state, catalog, u["id"]) for u in live_units(state)]
    changes, completed = context_rows(bolt, state, catalog)
    facts["unit_details"] = details
    slice_rows = [slice_row(state, catalog, s["id"]) for s in state["slices"]]
    facts["slice_details"] = slice_rows
    contributions = contribution_rows(bolt)
    facts["contributions"] = contributions
    facts["context"] = changes
    facts["completed_affected"] = completed
    unverified = not_verified(state, catalog)
    facts["not_verified"] = unverified
    git_block = git_status_block(bolt)
    if git_block is not None:
        facts["git"] = git_block
    if fmt == "json":
        return facts
    lines = [
        f"{state['title'] or state['id']} ({state['id']})",
        f"Status: {state['status']} | Scope: {state['scope']} | Depth: {state['depth']}",
        f"Intent: {state['intent'][:160]}",
    ]
    for phase in PHASES:
        entry = progress[phase]
        note = f", {entry['skipped']} skipped" if entry["skipped"] else ""
        lines.append(f"{phase.capitalize()}: {entry['done']}/{entry['total']} done{note}")
    lines.append(f"Units: {len(state['units'])} | Slices: {len(state['slices'])}")
    for row in details:
        step = f"{row['stage']} {row['action']}" if row["stage"] else "done"
        if row["verification_skipped"]:
            step += " (verification skipped)"
        waits = f" | {waits_sentence(row['blocked_by'])}" if row["blocked_by"] else ""
        lines.append(f"  {row['id']} | {row['owner'] or '-'} | {step}{waits}")
        if row["context_note"]:
            lines.append(f"    {row['context_note']}")
    lines.extend(slice_line(row) for row in slice_rows)
    lines.extend(f"Contribution {contribution_line(row)}" for row in contributions)
    for row in changes:
        lines.append(f"Context changed for {where_text(row)}: {report_text(row)}")
    for row in completed:
        lines.append(f"Completed work affected, {where_text(row)}: {report_text(row)}")
    if unverified:
        names = [where_text(r) for r in unverified]
        lines.append(f"Not verified (verdict not-run): {', '.join(names)}")
    lines.append(jira_line(state))
    if git_block is not None:
        lines.append(git_status_line(git_block))
    if nxt["done"]:
        lines.append("Current: none")
    elif nxt["action"] == "units":
        lines.append("Current: per-unit stages (see the units above)")
    else:
        lines.append(f"Current: {where_text(nxt)}, step {nxt['step']}")
    lines.append(f"Next: {state['next_action']}")
    if state["parked"]:
        note = str(state["parked"].get("note", "")).replace("\n", " ")
        lines.append(f"Parked: {note[:300]}")
    return {
        "text": "\n".join(
            lines[
                : 21
                + len(details)
                + sum(1 for row in details if row["context_note"])
                + len(changes)
                + len(completed)
                + len(slice_rows)
                + len(contributions)
            ]
        )
        + "\n"
    }


def log_rows(bolt: Path) -> list[dict[str, str]]:
    """Every line of a Bolt's log and its units' logs, with the unit it came from."""
    rows: list[dict[str, str]] = []
    files = [(bolt / "log.md", "")] + [
        (path, path.parent.name) for path in sorted(bolt.glob("units/*/log.md"))
    ]
    for path, unit in files:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = [p.strip() for p in line.split(" | ")]
            if len(parts) >= 5:
                keys = ("time", "event", "stage", "by", "note")
                rows.append({**dict(zip(keys, parts[:5])), "bolt": bolt.name, "unit": unit})
    return rows


CONTRIBUTION_DIR = "architecture/contributions"
CONTRIBUTION_STATUS = ("draft", "proposed", "merged")


def header_values(path: Path) -> dict[str, Any]:
    """The first fenced ``yaml`` block of a file as flat keys: scalars and lists of scalars.

    Deliberately small: the state script must not depend on the validator, and a listing
    must survive a header the validator would refuse. An unreadable header gives ``{}``."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    values: dict[str, Any] = {}
    inside, key = False, ""
    for line in lines:
        if not inside:
            if re.match(r"^ {0,3}```\s*yaml\s*$", line):
                inside = True
            elif re.match(r"^ {0,3}(```|~~~)", line) or line.startswith("## "):
                break
            continue
        if re.match(r"^ {0,3}```\s*$", line):
            break
        text = re.sub(r"(^|\s)#.*$", "", line).rstrip()
        item = re.match(r"^\s+-\s+(.*)$", text)
        pair = re.match(r"^([A-Za-z_][\w-]*):(?:\s+(.*))?$", text)
        if item and key and isinstance(values.get(key), list):
            values[key].append(unquote(item.group(1)))
        elif pair:
            key, raw = pair.group(1), (pair.group(2) or "").strip()
            if raw.startswith("[") and raw.endswith("]"):
                inner = raw[1:-1].strip()
                values[key] = [unquote(p) for p in inner.split(",")] if inner else []
            else:
                values[key] = unquote(raw) if raw else []
    return values


def unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def contribution_rows(bolt: Path) -> list[dict[str, Any]]:
    """The Bolt's contributions, read from their headers; a proposed one is open work."""
    rows: list[dict[str, Any]] = []
    for path in sorted((bolt / CONTRIBUTION_DIR).glob("*.md")):
        found = header_values(path)
        owner, status = found.get("owner"), found.get("status")
        touches = found.get("touches")
        rows.append(
            {
                "concern": path.stem,
                "owner": owner if isinstance(owner, str) and owner else None,
                "status": status if isinstance(status, str) and status else None,
                "touches": touches if isinstance(touches, list) else [],
                "open": status == "proposed",
            }
        )
    return rows


def contribution_line(row: dict[str, Any]) -> str:
    touches = f" | touches: {', '.join(row['touches'])}" if row["touches"] else ""
    flag = " (open)" if row["open"] else ""
    return (
        f"{row['concern']} | {row['owner'] or '-'} | {row['status'] or 'no header'}{flag}{touches}"
    )


def cmd_contribution(bolt: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Log where a contribution stands, after checking its header says so; edits no file."""
    if not ID_PATTERN.fullmatch(args.concern):
        die(EXIT_USAGE, f"--concern '{args.concern}' must match {ID_PATTERN.pattern}.")
    rel = f"{CONTRIBUTION_DIR}/{args.concern}.md"
    path = bolt / rel
    if not path.is_file():
        die(EXIT_INPUT, f"{rel} does not exist in this Bolt; create it from the template first.")
    found = header_values(path)
    if not found:
        die(EXIT_FINDINGS, f"{rel} has no yaml header block at the top.")
    owner = found.get("owner")
    if not isinstance(owner, str) or not owner.strip():
        die(EXIT_FINDINGS, f"{rel}: the header has no owner.")
    status = found.get("status")
    if not isinstance(status, str) or not status:
        die(EXIT_FINDINGS, f"{rel}: the header has no status.")
    if status != args.status:
        die(
            EXIT_FINDINGS,
            f"{rel}: the header says '{status}', not '{args.status}'. "
            "Edit the header first, then record it.",
        )
    note = f"{args.concern}: {args.status}" + (f" - {args.note}" if args.note else "")
    log_event(bolt, "contribution", "", "", note)
    return {"ok": True, "concern": args.concern, "status": args.status, "owner": owner, "file": rel}


def decision_problems(bolt: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    record = bolt / "architecture" / "hla-decisions.md"
    if not record.is_file():
        return []
    settled = (state.get("stages", {}).get("hla") or {}).get("step") == "approved"
    found: list[dict[str, str]] = []
    for row in decision_rows(record.read_text(encoding="utf-8", errors="replace")):
        if "contested" in (row["flag"] or "").lower():
            found.append({"code": "contested", "where": row["id"], "message": "flagged contested"})
        if settled and (row["status"] or "").lower() in UNSETTLED:
            message = f"{row['status']} although the HLA is approved"
            found.append({"code": "unsettled-decision", "where": row["id"], "message": message})
    return found


def overview_row(bolt: Path, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    state = load_state(bolt)
    backfill_stages(state, catalog)
    first = min((i["order"] for i in catalog if i["per_unit"]), default=0)
    reached = all(
        is_done(state["stages"].get(i["id"]))
        for i in catalog
        if not i["per_unit"] and i["order"] < first
    )
    units: list[dict[str, Any]] = []
    problems: list[dict[str, str]] = []
    changes, completed = context_rows(bolt, state, catalog)
    for code, found in (("context-changed", changes), ("completed-work-affected", completed)):
        for row in found:
            problems.append({"code": code, "where": where_text(row), "message": report_text(row)})
    for unit in live_units(state):
        nxt = next_for_unit(bolt, state, catalog, unit["id"])
        open_unit = not nxt["done"]
        units.append(
            {
                "id": unit["id"],
                "owner": unit.get("owner"),
                "repo": unit.get("repo"),
                "next": f"{nxt['stage']} {nxt['action']}" if open_unit else "done",
                "blocked_by": nxt["blocked_by"],
                "story": unit.get("story"),
                "pr": (unit.get("story_done") or {}).get("pr"),
            }
        )
        if state["status"] == "open" and reached and open_unit and not unit.get("owner"):
            problems.append({"code": "unowned-unit", "where": unit["id"], "message": "no owner"})
        if nxt["blocked_by"]:
            problems.append(
                {
                    "code": "waiting-unit",
                    "where": unit["id"],
                    "message": waits_sentence(nxt["blocked_by"]),
                }
            )
    problems.extend(decision_problems(bolt, state))
    lines = sorted(log_rows(bolt), key=lambda r: r["time"])
    last = {k: lines[-1][k] for k in ("time", "event", "stage", "by")} if lines else None
    return {
        "id": state["id"],
        "title": state.get("title", ""),
        "status": state["status"],
        "scope": state.get("scope"),
        "owner": state.get("owner") or None,
        "next": describe_next(compute_next(state, catalog, bolt)),
        "units": units,
        "slices": [slice_row(state, catalog, s["id"]) for s in state["slices"]],
        "context": changes,
        "completed_affected": completed,
        "contributions": contribution_rows(bolt),
        "not_verified": not_verified(state, catalog),
        "last": last,
        "problems": problems,
    }


def overview_text(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for row in rows:
        if "error" in row:
            lines.append(f"{row['id']}: unreadable: {row['error']}")
            continue
        owner = f", owner {row['owner']}" if row["owner"] else ""
        lines.append(f"{row['id']} [{row['status']}] {row['title']}{owner}")
        lines.append(f"  next: {row['next']}")
        for unit in row["units"]:
            waits = f" | {waits_sentence(unit['blocked_by'])}" if unit["blocked_by"] else ""
            lines.append(f"  unit {unit['id']} | {unit['owner'] or '-'} | {unit['next']}{waits}")
        lines.extend(slice_line(entry) for entry in row["slices"])
        lines.extend(f"  contribution {contribution_line(c)}" for c in row["contributions"])
        for item in row["not_verified"]:
            lines.append(f"  not verified: {where_text(item)}")
        for problem in row["problems"]:
            lines.append(f"  ! {problem['code']} {problem['where']}: {problem['message']}")
    return "\n".join(lines) + "\n"


def unshared_commits(root: Path) -> Optional[int]:
    """Local commits not yet on the upstream; ``None`` without git or an upstream."""
    try:
        ctx, _why = open_git(root.resolve())
    except Fail:
        return None
    ref = upstream_ref(ctx) if ctx else None
    return count_commits(ctx, f"{ref}..HEAD") if ctx and ref else None


def cmd_overview(args: argparse.Namespace, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    """Every Bolt of a planning repository in one read-only roll-up."""
    root = Path(args.root)
    if not root.is_dir():
        die(EXIT_INPUT, f"{root}: --root is not a directory.")
    rows: list[dict[str, Any]] = []
    logs: list[dict[str, str]] = []
    for state_file in sorted(root.glob("bolts/*/state.json")):
        bolt = state_file.parent
        try:
            rows.append(overview_row(bolt, catalog))
        except Fail as exc:
            rows.append({"id": bolt.name, "error": exc.message})
        except Exception as exc:  # one unreadable Bolt must not hide the others
            rows.append({"id": bolt.name, "error": f"{type(exc).__name__}: {exc}"})
        logs.extend(log_rows(bolt))
    result: dict[str, Any] = {"ok": True, "root": str(root.resolve()), "bolts": rows}
    result["unshared"] = unshared_commits(root)
    if args.log:
        result["log"] = sorted(logs, key=lambda r: r["time"])[-args.log :]
    if args.format == "text":
        text = overview_text(rows)
        if unshared_line(result["unshared"]):
            text = f"{unshared_line(result['unshared'])}\n" + text
        for entry in result.get("log", []):
            unit = f" [{entry['unit']}]" if entry["unit"] else ""
            text += f"{entry['time']} {entry['bolt']}{unit} {entry['event']} {entry['stage']}\n"
        return {"text": text}
    return result


def planning_root(bolt: Path) -> Path:
    """The planning repository root: bolts live in ``<root>/bolts/<id>``."""
    return bolt.resolve().parent.parent


def locate(bolt: Path, rel: str) -> Path:
    """Resolve a stages.json path: ``root:`` hangs off the planning root; anything else
    off this bolt."""
    if rel.startswith(ROOT_PREFIX):
        return planning_root(bolt) / rel[len(ROOT_PREFIX) :]
    return bolt / rel


def glob_paths(bolt: Path, rel: str) -> list[Path]:
    if rel.startswith(ROOT_PREFIX):
        return sorted(planning_root(bolt).glob(rel[len(ROOT_PREFIX) :]))
    return sorted(bolt.glob(rel))


def brownfield_repos(state: dict[str, Any]) -> list[str]:
    return [t["repo"] for t in state["targets"] if t["kind"] == "brownfield"]


def unit_ids(state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]) -> list[str]:
    """The units a stage's ``<unit>`` paths cover: its own unit, the Units of its Slice, or
    every unit."""
    if stage["per_unit"]:
        return [unit] if unit else []
    if is_slice_stage(stage):
        return [u["id"] for u in slice_units(state, unit)] if unit else []
    return [u["id"] for u in live_units(state)]


def expand_pairs(
    template: str, repos: list[str], units: list[str], targets: Optional[list[str]] = None
) -> list[tuple[str, Optional[str]]]:
    """Expand ``<repo>`` over brownfield targets, ``<target>`` over every target and
    ``<unit>`` over ``units``."""
    pairs: list[tuple[str, Optional[str]]] = [(template, None)]
    if "<unit>" in template:
        pairs = [(template.replace("<unit>", u), u) for u in units]
    if "<repo>" in template:
        pairs = [(rel.replace("<repo>", repo), u) for rel, u in pairs for repo in repos]
    if "<target>" in template:
        pairs = [(rel.replace("<target>", t), u) for rel, u in pairs for t in targets or []]
    return pairs


def expand(template: str, repos: list[str], units: list[str]) -> list[str]:
    return [rel for rel, _ in expand_pairs(template, repos, units)]


def producer_of(catalog: list[dict[str, Any]], template: str) -> Optional[dict[str, Any]]:
    for item in catalog:
        if template in item["artifacts"]:
            return item
    return None


def input_rows(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    unit: Optional[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The input rows of a stage (and unit) and the required ones that are missing."""
    repos = brownfield_repos(state)
    targets = [t["repo"] for t in state["targets"]]
    units = unit_ids(state, stage, unit)
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    slug = DATE_PREFIX.sub("", str(state["id"]))
    for entry in stage["inputs"]:
        template = entry["path"].replace("<bolt>", slug)
        producer = producer_of(catalog, template)
        optional = bool(entry.get("optional"))
        bound = template.replace("<slice>", unit) if is_slice_stage(stage) and unit else template
        for rel, row_unit in expand_pairs(bound, repos, units, targets):
            skipped = False
            if producer is not None:
                producer_unit = row_unit if producer["per_unit"] else None
                if is_slice_stage(producer):
                    producer_unit = unit
                rec = slot_record(state, producer, producer_unit)
                skipped = bool(rec and rec["decision"] == "skip")
            file = locate(bolt, rel)
            exists = file.is_file()
            if entry.get("if_exists") and not exists:
                continue
            produced_by = producer["id"] if producer else None
            row = {
                "path": rel,
                "file": str(file.resolve()),
                "mode": entry["mode"],
                "exists": exists,
                "produced_by": produced_by,
                "skipped": skipped and not exists,
                "optional": optional,
                "track": entry.get("track", "file"),
            }
            rows.append(row)
            if not exists and not skipped and not optional:
                missing.append({"path": rel, "produced_by": row["produced_by"]})
    return rows, missing


def cmd_inputs(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage_id: str,
    unit: Optional[str],
    slice_id: Optional[str] = None,
) -> dict[str, Any]:
    stage = stage_def(catalog, stage_id)
    unit = scope_key(state, stage, unit, slice_id)
    get_record(state, stage, unit)
    rows, missing = input_rows(bolt, state, catalog, stage, unit)
    payload: dict[str, Any] = {
        "ok": not missing,
        "stage": stage_id,
        **subject(stage, unit),
        "root": str(planning_root(bolt)),
        "inputs": rows,
        "missing": missing,
    }
    if missing:
        names = ", ".join(f"{m['path']} (stage {m['produced_by'] or 'unknown'})" for m in missing)
        raise Fail(
            EXIT_INPUT, f"stage '{stage_id}' is missing required input: {names}", extra=payload
        )
    return payload


# --- context a stage relied on ------------------------------------------------
#
# What a Unit (or Slice) relies on is the ids it cites, and what those cite, two hops out,
# restricted to the ids its stage reads from documents tracked by ``id``. The baseline keeps
# hashes and ids only; the report says what changed since, and who is affected.


def fingerprint(row: dict[str, Any]) -> str:
    """16 hex characters of a sha256: the file, or only its ``## Digest`` in digest mode."""
    raw = Path(row["file"]).read_bytes()
    if row["mode"] == "digest":
        found = digest_section(raw.decode("utf-8", errors="replace"))
        if found is not None:
            raw = "\n".join(found).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def load_refs_module() -> Any:
    if "aidlc_state_refs" in sys.modules:
        return sys.modules["aidlc_state_refs"]
    path = Path(__file__).resolve().parent / "aidlc_refs.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("aidlc_state_refs", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["aidlc_state_refs"] = module  # dataclasses look their module up here
    cast(Any, spec.loader).exec_module(module)
    return module


def unit_key(ident: str) -> str:
    """The form in which an Inception id (``U-3``) and a state Unit id (``u3``) are equal."""
    return ident.lower().replace("-", "")


class RefIndex:
    """The ids of one Bolt, parsed once per command: declarations, citations, closures."""

    def __init__(self, bolt: Path) -> None:
        self.refs = load_refs_module()
        self.bolt = self.refs.Bolt(bolt) if self.refs else None
        self.unavailable = self.bolt is None  # no index: nothing may be reported as removed
        self.unreadable: list[str] = []  # Markdown files left out because they are not UTF-8
        if self.bolt is not None:
            try:
                self.bolt.load(skip_unreadable=True)
                self.unreadable = list(self.bolt.unreadable)
            except (ValueError, OSError) as exc:
                LOG.warning("ids are not tracked: %s", exc)
                self.bolt = self.refs.Bolt(bolt)
                self.unavailable = True
        self.hashes: dict[str, str] = {}
        self.closures: dict[str, set[str]] = {}
        self._decisions: Optional[list[tuple[int, Any]]] = None

    def decl(self, ident: str) -> Any:
        return self.bolt.winners.get(ident) if self.bolt is not None else None

    def digest(self, ident: str) -> Optional[str]:
        if ident not in self.hashes and (found := self.decl(ident)) is not None:
            text = self.refs.section(self.bolt, found, True)  # the whole section, not the gloss
            self.hashes[ident] = short_hash(" ".join(text.split()))  # spacing is not a change
        return self.hashes.get(ident)

    def decisions(self) -> list[tuple[int, Any]]:
        """The Bolt-level ``D<n>`` declared in the decision records, with their numbers."""
        if self._decisions is None:
            self._decisions = []
            for ident, found in self.bolt.winners.items() if self.bolt is not None else []:
                if found.file in DECISION_RECORDS and re.fullmatch(r"D\d+", ident):
                    self._decisions.append((int(ident[1:]), found))
        return self._decisions

    def citing(self, ident: str, own: set[str]) -> set[str]:
        """The declarations that cite ``ident`` (a story-map row, a story, a contract): the
        innermost declaration around each citation. Another Unit's own section that merely
        names this Unit is not about it."""
        found: set[str] = set()
        bolt = self.bolt
        if bolt is None:
            return found
        for ref in bolt.refs.get(ident, []):
            scan = bolt.files.get(ref.file)
            around = [
                d
                for d in (scan.decls if scan else [])
                if d.line <= ref.line <= self.refs.section_end(bolt, d, True)
            ]
            top = max((d.line for d in around), default=0)
            for decl in around:
                other_unit = Path(decl.file).name == "unit-of-work.md" and decl.ident not in own
                if decl.line == top and not other_unit:
                    found.add(decl.ident)
        return found

    def closure(self, unit: str) -> set[str]:
        """Ids a Unit relies on, from three seeds: its own declaration, every declaration that
        cites its id (the story map, the stories, the contracts) and what its own files cite;
        then what those declarations cite, and what those cite (two hops)."""
        if unit in self.closures or self.bolt is None:
            return self.closures.setdefault(unit, set())
        own = {
            ident
            for ident, found in self.bolt.winners.items()
            if Path(found.file).name == "unit-of-work.md" and unit_key(ident) == unit_key(unit)
        }
        seeds = set(own)
        for ident in own:
            seeds |= self.citing(ident, own)
        prefix = f"docs/construction/{unit}/"
        for rel, cited in self.bolt.file_refs.items():
            if rel.startswith(prefix):
                for ref in cited:
                    target = self.bolt.winner(ref.ident, rel) if ref.kind == "id" else None
                    if target is not None:
                        seeds.add(target.ident)
        reached, frontier = set(seeds), seeds
        for _ in range(2):
            frontier = {
                cited
                for ident in frontier
                if (found := self.bolt.winners.get(ident)) is not None
                for cited in self.refs.cited_in(self.bolt, found)
            } - reached
            reached |= frontier
        self.closures[unit] = reached
        return reached


_INDEXES: dict[str, RefIndex] = {}


def ref_index(bolt: Path) -> RefIndex:
    key = str(bolt.resolve())
    if key not in _INDEXES:
        _INDEXES[key] = RefIndex(bolt)
    return _INDEXES[key]


def slot_units(state: dict[str, Any], stage: dict[str, Any], key: Optional[str]) -> list[str]:
    """The Units whose reliance a slot shares: its own, or those of its Slice."""
    if key is None or not (stage["per_unit"] or is_slice_stage(stage)):
        return []
    return [key] if stage["per_unit"] else [u["id"] for u in slice_units(state, key)]


def relied_ids(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    key: Optional[str],
    rows: Optional[list[dict[str, Any]]] = None,
) -> set[str]:
    """The ids a slot relies on, restricted to the ids declared in its ``track: ids`` inputs."""
    rows = input_rows(bolt, state, catalog, stage, key)[0] if rows is None else rows
    tracked = {row["path"] for row in rows if row["track"] == "ids" and row["exists"]}
    units = slot_units(state, stage, key)
    if not tracked or not units:
        return set()
    index = ref_index(bolt)
    wanted: set[str] = set()
    for unit in units:
        wanted |= index.closure(unit)
    return {i for i in wanted if (found := index.decl(i)) is not None and found.file in tracked}


def deps_hash(state: dict[str, Any], stage: dict[str, Any], key: Optional[str]) -> str:
    if stage["per_unit"]:
        deps: Any = find_unit(state, cast(str, key)).get("depends_on") or []
    else:
        deps = [find_slice(state, cast(str, key)).get("depends_on") or []] + [
            [u["id"], u.get("depends_on") or []] for u in slice_units(state, cast(str, key))
        ]
    return short_hash(json.dumps(deps, sort_keys=True))


def file_hashes(rows: list[dict[str, Any]]) -> dict[str, Optional[str]]:
    """Fingerprints of the files a slot tracks as whole files (not by id, not at all)."""
    return {
        r["path"]: fingerprint(r) if r["exists"] else None for r in rows if r["track"] == "file"
    }


def compact_numbers(numbers: Iterable[int]) -> str:
    """``{1,2,3,5}`` as ``"1-3,5"``: the decision numbers a baseline has seen, kept short."""
    parts: list[str] = []
    ordered = sorted(set(numbers))
    start = 0
    while start < len(ordered):
        end = start
        while end + 1 < len(ordered) and ordered[end + 1] == ordered[end] + 1:
            end += 1
        first, last = ordered[start], ordered[end]
        parts.append(str(first) if first == last else f"{first}-{last}")
        start = end + 1
    return ",".join(parts)


def parse_numbers(text: str) -> set[int]:
    found: set[int] = set()
    for part in str(text or "").split(","):
        low, dash, high = part.strip().partition("-")
        if low.isdigit() and (not dash or high.isdigit()):
            found.update(range(int(low), int(high or low) + 1))
    return found


def baseline(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    key: Optional[str],
) -> dict[str, Any]:
    """What the slot relies on now: hashes and ids, never text."""
    rows = input_rows(bolt, state, catalog, stage, key)[0]
    taken: dict[str, Any] = {"at": now(), "files": file_hashes(rows)}
    if stage["per_unit"] or is_slice_stage(stage):
        index = ref_index(bolt)
        taken["deps"] = deps_hash(state, stage, key)
        if index.unavailable:  # never replace what was recorded with an empty index
            kept = (slot_record(state, stage, key) or {}).get("relied_on") or {}
            taken.update({k: kept[k] for k in ("ids", "decisions") if k in kept})
            return taken
        ids = relied_ids(bolt, state, catalog, stage, key, rows)
        taken["ids"] = {i: index.digest(i) for i in sorted(ids)}
        taken["decisions"] = compact_numbers(n for n, _ in index.decisions())
    return taken


def start_baseline(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    key: Optional[str],
) -> None:
    """Take the baseline when work on a slot starts, unless it has one."""
    record = get_record(state, stage, key)
    if record["decision"] == "execute" and not record.get("relied_on"):
        record["relied_on"] = baseline(bolt, state, catalog, stage, key)


def described(index: RefIndex, ident: str) -> dict[str, Any]:
    found = index.decl(ident)
    if found is None:
        return {"id": ident}
    return {"id": ident, "file": found.file, "line": found.line, "gloss": found.gloss}


def context_report(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    key: Optional[str],
) -> dict[str, Any]:
    """What changed under a slot since its baseline; empty when nothing it relies on did.

    Keys, present only when not empty: ``changed`` (relied-on ids that changed, were
    superseded or removed), ``new_related`` (later decisions that cite a relied-on id),
    ``new_constraints`` (later Bolt-wide constraints, for work still open), ``inputs`` (files
    that changed, appeared or vanished), ``dependencies`` and ``baseline`` (``missing``)."""
    record = slot_record(state, stage, key)
    if record is None or record["decision"] != "execute":
        return {}
    stored = record.get("relied_on")
    per_slot = bool(stage["per_unit"] or is_slice_stage(stage))
    if not stored or not isinstance(stored.get("files"), dict):
        # only open per-Unit and per-Slice work needs a baseline; Bolt-level stages ran before
        # baselines existed or had one taken at their checkpoint, and nothing can clear a gap
        open_slot = per_slot and record["step"] != "todo" and not is_done(record)
        return {"baseline": "missing"} if open_slot else {}
    then_files = stored["files"]
    rows = input_rows(bolt, state, catalog, stage, key)[0]
    now_files = file_hashes(rows)
    report: dict[str, Any] = {}
    inputs: list[dict[str, str]] = []
    for path in sorted(set(then_files) | set(now_files)):
        before, after = then_files.get(path), now_files.get(path)
        if before == after:
            continue
        what = "appeared" if before is None else "vanished" if after is None else "changed"
        inputs.append({"path": path, "what": what})
    if inputs:
        report["inputs"] = inputs
    if not per_slot:
        return report
    index = ref_index(bolt)
    if index.unavailable:
        report["index"] = "unavailable"  # nothing below can be told without it
        return report
    changed: list[dict[str, Any]] = []
    for ident, before_hash in sorted((stored.get("ids") or {}).items()):
        found = index.decl(ident)
        if found is None and index.unreadable:
            report["unreadable"] = index.unreadable  # it may be declared in a file not read
        elif found is None:
            changed.append({"id": ident, "what": "removed"})
        elif index.digest(ident) != before_hash:
            status = (found.cells.get("status") or "").lower()
            what = "superseded" if status == "superseded" else "changed"
            changed.append({**described(index, ident), "what": what})
    if changed:
        report["changed"] = changed
    if stored.get("deps") != deps_hash(state, stage, key):
        report["dependencies"] = True
    seen = parse_numbers(stored.get("decisions", "")) if "decisions" in stored else None
    later = [
        (n, found)
        for n, found in sorted(index.decisions(), key=lambda p: p[0])
        if seen is not None and n not in seen  # a number reserved early and written late is new
    ]
    if later:
        mine = set(stored.get("ids") or {}) | relied_ids(bolt, state, catalog, stage, key, rows)
        related = []
        for _n, found in later:
            cites = [c for c in index.refs.cited_in(index.bolt, found) if c in mine]
            if cites:
                related.append({**described(index, found.ident), "cites": cites})
        if related:
            report["new_related"] = related
        if not is_done(record):
            constraints = [
                described(index, found.ident)
                for _n, found in later
                if (found.cells.get("status") or "").lower() == "constraint"
            ]
            if constraints:
                report["new_constraints"] = constraints
    return report


def report_text(report: dict[str, Any]) -> str:
    """One line for a report, for logs and text output."""
    parts: list[str] = []
    if report.get("baseline"):
        parts.append("no baseline recorded")
    if report.get("index"):
        parts.append("index: unavailable (ids cannot be checked)")
    if report.get("unreadable"):
        parts.append("not read: " + ", ".join(report["unreadable"]))
    if report.get("changed"):
        parts.append("; ".join(f"{c['id']} {c['what']}" for c in report["changed"]))
    if report.get("new_related"):
        parts.append("later decisions on it: " + ", ".join(c["id"] for c in report["new_related"]))
    if report.get("new_constraints"):
        parts.append("new constraints: " + ", ".join(c["id"] for c in report["new_constraints"]))
    if report.get("inputs"):
        parts.append("; ".join(f"{i['path']} {i['what']}" for i in report["inputs"]))
    if report.get("dependencies"):
        parts.append("dependencies changed")
    return "; ".join(parts)


def with_context(
    bolt: Optional[Path],
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Add the context report of a ``next`` result's slot as ``context``, when not empty."""
    if result.get("stage") and bolt is not None:
        stage = stage_def(catalog, result["stage"])
        key = result.get("slice") if is_slice_stage(stage) else result.get("unit")
        report = context_report(bolt, state, catalog, stage, key)
        if report:
            result["context"] = report
    return result


def context_rows(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The slots with something to report: ``(open work, completed work)``."""
    open_rows: list[dict[str, Any]] = []
    done_rows: list[dict[str, Any]] = []
    for item, key in slots(state, catalog):
        report = context_report(bolt, state, catalog, item, key)
        if report:
            row = {"stage": item["id"], **subject(item, key), **report}
            (done_rows if is_done(slot_record(state, item, key)) else open_rows).append(row)
    return open_rows, done_rows


def relies_on_rows(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], group: list[Slot]
) -> list[dict[str, Any]]:
    """The ids the given slots rely on, with where each is declared."""
    found: set[str] = set()
    for item, key in group:
        record = slot_record(state, item, key)
        if record is not None and record["decision"] != "skip":
            found |= relied_ids(bolt, state, catalog, item, key)
    index = ref_index(bolt)
    ordered = sorted(found, key=index.refs.sort_key) if index.refs else []
    return [described(index, ident) for ident in ordered]


def context_of_id(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], ident: str
) -> dict[str, Any]:
    """Who relies on an id: Units, Slices and the files that cite it, and how many do not."""
    index = ref_index(bolt)
    if index.unavailable:
        raise Fail(EXIT_FINDINGS, "index: unavailable; the Bolt's ids could not be read.")
    found = index.decl(ident)
    if found is None:
        raise Fail(EXIT_FINDINGS, f"{ident} is not declared in this Bolt.")
    units = live_units(state)
    stages = [i for i in catalog if i["per_unit"]]
    relying = [
        u
        for u in units
        if any(
            ident in relied_ids(bolt, state, catalog, i, u["id"])
            for i in stages
            if (slot_record(state, i, u["id"]) or {}).get("decision") != "skip"
        )
    ]
    slice_stages = [i for i in catalog if is_slice_stage(i)]
    slices = [
        s["id"]
        for s in state["slices"]
        if any(ident in relied_ids(bolt, state, catalog, i, s["id"]) for i in slice_stages)
    ]
    cited = sorted({ref.file for ref in index.bolt.refs.get(ident, [])}) if index.bolt else []
    return {
        "ok": True,
        **described(index, ident),
        "units": [
            {"id": u["id"], "slice": u.get("slice"), "owner": u.get("owner")} for u in relying
        ],
        "slices": slices,
        "cited_in": cited,
        "units_not_relying": len(units) - len(relying),
    }


def reliance_note(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], unit: str
) -> Optional[str]:
    """One line when a started Unit relies on no requirement or decision, or on no decision:
    an empty report would look reassuring, but change detection has nothing to watch."""
    started = [
        item
        for item in catalog
        if item["per_unit"]
        and (rec := slot_record(state, item, unit)) is not None
        and rec["decision"] == "execute"
        and (rec["step"] != "todo" or rec.get("relied_on"))  # work on it has begun
    ]
    index = ref_index(bolt)
    if not started or index.unavailable:
        return None
    relied: set[str] = set()
    for item in started:
        relied |= relied_ids(bolt, state, catalog, item, unit)
    has_req = any(re.search(r"(?:^|:)N?FR-\d+$", i) for i in relied)
    has_dec = any(re.search(r"(?:^|:)D\d+$", i) for i in relied)
    tail = "; change detection cannot help it"
    if not has_req and not has_dec:
        return f"{unit} relies on no recorded requirement or decision{tail}"
    if not has_dec and index.decisions():
        return f"{unit} relies on no recorded decision{tail}"
    return None


def cmd_context(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    """What changed under a Unit or Slice, and what it relies on; ``--note`` records the
    conclusion and refreshes the baseline. ``--id`` says who relies on one id."""
    if args.id:
        if args.unit or args.slice or args.stage or args.note:
            die(EXIT_USAGE, "--id stands alone: drop --unit, --slice, --stage and --note.")
        return context_of_id(bolt, state, catalog, args.id)
    if bool(args.unit) == bool(args.slice):
        die(EXIT_USAGE, "give --unit or --slice (or --id ID).")
    key = args.unit or args.slice
    if args.unit:
        find_unit(state, key)
    else:
        find_slice(state, key)
    group = [(i, key) for i in catalog if (i["per_unit"] if args.unit else is_slice_stage(i))]
    if args.stage:
        stage = stage_def(catalog, args.stage)
        group = [(i, k) for i, k in group if i["id"] == stage["id"]]
        if not group:
            die(
                EXIT_USAGE,
                f"stage '{stage['id']}' is not run per {'unit' if args.unit else 'slice'}.",
            )
    reports = []
    for item, k in group:
        report = context_report(bolt, state, catalog, item, k)
        if report:
            reports.append({"stage": item["id"], **report})
    result: dict[str, Any] = {
        "ok": True,
        "unit" if args.unit else "slice": key,
        "reports": reports,
        "relies_on": relies_on_rows(bolt, state, catalog, group),
    }
    if args.unit and (line := reliance_note(bolt, state, catalog, key)):
        result["note"] = line
    if args.note is None:
        return result
    note = " ".join(args.note.split())
    if not note:
        die(EXIT_USAGE, "--note must not be blank.")
    suffix, warnings = guard_owner(bolt, state, args.unit)
    for row in reports:
        item = stage_def(catalog, row["stage"])
        get_record(state, item, key)["relied_on"] = baseline(bolt, state, catalog, item, key)
    commit(bolt, state, catalog)
    seen = "; ".join(f"{r['stage']}: {report_text(r)}" for r in reports) or "nothing reported"
    log_event(
        bolt,
        "context",
        args.stage or "",
        "",
        f"[{key}] {note} (reported: {seen}){suffix}",
        args.unit or "",
    )
    result["noted"] = True
    if warnings:
        result["warnings"] = warnings
    return result


# --- code knowledge ----------------------------------------------------------


def codekb_dir(root: Path, repo: str) -> Path:
    return root / "codekb" / repo


def read_meta(root: Path, repo: str) -> Optional[dict[str, Any]]:
    """The store's ``_meta.json``, or ``None`` when the repo has no store yet."""
    path = codekb_dir(root, repo) / "_meta.json"
    if not path.is_file():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}")
    if not isinstance(meta, dict):
        die(EXIT_MALFORMED, f"{path}: expected an object.")
    return meta


def codekb_target(root: Path, target: dict[str, Any]) -> dict[str, Any]:
    """Freshness of one target's shared code knowledge against the target's HEAD."""
    repo = target["repo"]
    row: dict[str, Any] = {"repo": repo, "recorded_commit": target.get("codekb_commit")}
    if target["kind"] != "brownfield":
        return {**row, "status": "n/a", "note": "greenfield target"}
    meta = read_meta(root, repo)
    if meta is None:
        return {**row, "status": "missing", "rescan": "full"}
    commit = str(meta.get("commit") or "")
    found = resolve_repo(root, repo, target.get("path"))
    path = found or sibling(root, repo)
    head = (git(path, "rev-parse", "HEAD") or "").strip()
    row.update({"meta_commit": commit or None, "head": head or None})
    if head and commit == head:
        return {**row, "status": "fresh"}
    known = bool(commit) and git(path, "cat-file", "-e", f"{commit}^{{commit}}") is not None
    if not head or not known:
        why = "meta commit is unknown to the repo"
        if not head:
            why = "target is not a git checkout"
            if found is None:
                why = f"target repository not found; {PATH_HINT}"
        return {**row, "status": "stale", "rescan": "full", "note": why}
    changed = [
        line for line in (git(path, "diff", "--name-only", f"{commit}..HEAD") or "").splitlines()
        if line
    ]  # fmt: skip
    total = len([line for line in (git(path, "ls-files") or "").splitlines() if line])
    full = total > 0 and len(changed) / total > FOCUSED_RESCAN_MAX
    return {
        **row,
        "status": "stale",
        "changed_count": len(changed),
        "changed_files": changed[:CHANGED_FILES_CAP],
        "truncated": len(changed) > CHANGED_FILES_CAP,
        "rescan": "full" if full else "focused",
    }


def codekb_status(root: Path, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [codekb_target(root, t) for t in targets]


# --- writing commands --------------------------------------------------------


def cmd_decide(
    state: dict[str, Any], stage: dict[str, Any], unit: Optional[str], decision: str, reason: str
) -> None:
    if not reason.strip():
        die(EXIT_USAGE, "--reason is required and must not be blank.")
    record = get_record(state, stage, unit)
    if record["step"] == "approved":
        raise Fail(EXIT_FINDINGS, f"stage '{stage['id']}' is already approved.")
    if decision == "skip" and stage.get("verdict") and record["step"] != "todo":
        raise Fail(
            EXIT_FINDINGS,
            f"stage '{stage['id']}' has started: a started verification is finished by a "
            "passing run or reopened (`gate --request-changes`), not skipped.",
        )
    record["decision"] = decision
    record["reason"] = reason.strip()


def cmd_step(state: dict[str, Any], stage: dict[str, Any], unit: Optional[str], to: str) -> None:
    record = get_record(state, stage, unit)
    if record["decision"] != "execute":
        raise Fail(
            EXIT_FINDINGS,
            f"stage '{stage['id']}' decision is {record['decision']}; decide `execute` first.",
        )
    if record["step"] == "approved":
        raise Fail(EXIT_FINDINGS, f"stage '{stage['id']}' is already approved.")
    current = STEP_ORDER.index(record["step"]) if record["step"] in STEP_ORDER else 0
    if STEP_ORDER.index(to) <= current and record["step"] != "changes-requested":
        raise Fail(
            EXIT_FINDINGS,
            f"cannot move '{stage['id']}' from {record['step']} to {to}; steps only move forward.",
        )
    record["step"] = to


def as_list(value: Any) -> list[str]:
    """A stages.json field that holds one path or a list of paths."""
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def header_fields(text: str) -> Optional[dict[str, str]]:
    """Top-level ``key: value`` pairs of the first fenced ``yaml`` block, or ``None``.

    Only what the sign-off check needs: scalar values, quotes and trailing
    comments stripped. The full header is validated by ``validate_doc.py``.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "```yaml"), None)
    if start is None:
        return None
    fields: dict[str, str] = {}
    for line in lines[start + 1 :]:
        if line.strip().startswith("```"):
            return fields
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if value[:1] in {'"', "'"}:
            end = value.find(value[0], 1)
            value = value[1:end] if end > 0 else value[1:]
        else:
            value = value.split(" #", 1)[0].strip()
        fields[match.group(1)] = value
    return None


def load_lint_module() -> Any:
    path = Path(__file__).resolve().parent / "lint_questions.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("aidlc_lint_questions", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    cast(Any, spec.loader).exec_module(module)
    return module


def digest_section(text: str) -> Optional[list[str]]:
    """Non-blank lines under ``## Digest``, or ``None`` when the heading is absent."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^##\s+Digest\s*$", line):
            found: list[str] = []
            for follow in lines[index + 1 :]:
                if re.match(r"^#{1,6}\s", follow):
                    break
                if follow.strip():
                    found.append(follow)
            return found
    return None


def digest_lines(text: str) -> Optional[int]:
    """The number of non-blank lines under ``## Digest``, or ``None`` without the heading."""
    found = digest_section(text)
    return None if found is None else len(found)


def gate_findings(
    bolt: Path,
    state: dict[str, Any],
    stage: dict[str, Any],
    unit: Optional[str],
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    stage = bind_slice(stage, unit)
    findings: list[dict[str, Any]] = []
    if record["decision"] != "execute":
        findings.append(
            {"code": "decision-not-execute", "message": f"decision is {record['decision']}"}
        )
    if record["step"] != "produced":
        findings.append(
            {"code": "wrong-step", "message": f"step is {record['step']}; it must be produced"}
        )
    repos = brownfield_repos(state)
    units = unit_ids(state, stage, unit)
    exempt = {
        rel
        for template in as_list(stage.get("no_digest"))
        for rel in expand(template, repos, units)
    }
    for template in stage["artifacts"]:
        for rel in expand(template, repos, units):
            path = locate(bolt, rel)
            if not path.is_file():
                findings.append(
                    {"code": "artifact-missing", "path": rel, "message": "artifact does not exist"}
                )
                continue
            if path.suffix != ".md" or path.name.startswith("_") or rel in exempt:
                continue
            count = digest_lines(path.read_text(encoding="utf-8", errors="replace"))
            if count is None:
                findings.append(
                    {"code": "digest-missing", "path": rel, "message": "no `## Digest` section"}
                )
            elif count > DIGEST_MAX_LINES:
                findings.append(
                    {
                        "code": "digest-too-long",
                        "path": rel,
                        "message": f"digest has {count} lines; the limit is {DIGEST_MAX_LINES}",
                    }
                )
    questions: list[Path] = []
    for template in as_list(stage.get("questions")):
        for rel in expand(template, repos, units):
            path = locate(bolt, rel)
            if path.is_file():
                questions.append(path)
            else:
                findings.append(
                    {
                        "code": "questions-missing",
                        "path": rel,
                        "message": "question file does not exist",
                    }
                )
    # Stages that share a folder name their own clarification files; otherwise
    # every clarification file beside a question file belongs to the stage.
    clarifications: list[Path] = []
    patterns = as_list(stage.get("clarifications"))
    if patterns:
        for pattern in patterns:
            for rel in expand(pattern, repos, units):
                clarifications.extend(glob_paths(bolt, rel))
    else:
        for parent in dict.fromkeys(path.parent for path in questions):
            clarifications.extend(sorted(parent.glob("*clarifications*.md")))
    to_lint = list(dict.fromkeys([*questions, *clarifications]))
    lint = load_lint_module() if to_lint else None
    if to_lint and lint is None:
        LOG.warning("lint_questions.py is not installed beside this script; skipping.")
    if lint is not None:
        for item in to_lint:
            result = lint.lint_text(item.read_text(encoding="utf-8", errors="replace"))
            for found in result["findings"]:
                findings.append(
                    {
                        "code": "questions-" + found["code"],
                        "path": str(item.relative_to(bolt)),
                        "message": f"{found['question']} line {found['line']}: {found['message']}",
                    }
                )
    if stage["id"] == "reverse-engineering":
        findings.extend(meta_findings(bolt, state))
    return findings


def read_verdict(text: str) -> Optional[str]:
    """The word of the one ``Verdict:`` line, or ``None`` when there is not exactly one
    valid line. Fenced lines do not count; any decoration around a line does, so a bold
    ``fail`` cannot hide behind a plain ``pass``. ``pass`` takes no reason."""
    lines: list[str] = []
    fenced = False
    for line in text.lstrip("\ufeff").splitlines():
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and VERDICT_LINE.match(line):
            lines.append(line)
    if len(lines) != 1:
        return None
    head = VERDICT_LINE.match(lines[0])
    assert head is not None
    match = VERDICT_VALUE.match(re.sub(r"[*_`]", "", lines[0][head.end() :]))
    if match is None:
        return None
    word = match.group(1).lower()
    if word not in VERDICT_WORDS or (word == "pass" and match.group(2)):
        return None
    return word


def stage_verdict(
    bolt: Path, state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]
) -> tuple[Optional[str], list[dict[str, Any]]]:
    """The verdict a stage's ``verdict`` file records and the findings about it.

    Without a verdict key there is nothing to check. A missing file is the artifact
    finding's business, not this one's."""
    template = bind_slice(stage, unit).get("verdict")
    if not template:
        return None, []
    found: list[dict[str, Any]] = []
    words: list[str] = []
    for rel in expand(template, brownfield_repos(state), unit_ids(state, stage, unit)):
        path = locate(bolt, rel)
        if not path.is_file():
            continue
        word = read_verdict(path.read_text(encoding="utf-8", errors="replace"))
        if word is None:
            found.append(
                {
                    "code": "verdict-missing",
                    "path": rel,
                    "message": "the file needs exactly one line `Verdict: pass`, "
                    "`Verdict: fail` or `Verdict: not-run`",
                }
            )
        else:
            words.append(word)
            if word == "fail":
                found.append(
                    {
                        "code": "verdict-fail",
                        "path": rel,
                        "message": "the recorded verdict is fail; the stage stays open "
                        "until a run passes",
                    }
                )
    if found or not words:
        return None, found
    return ("not-run" if "not-run" in words else "pass"), found


def not_verified(state: dict[str, Any], catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Passed stages whose verdict is ``not-run``: done, but never shown to work."""
    rows: list[dict[str, Any]] = []
    for item, unit in slots(state, catalog):
        record = slot_record(state, item, unit)
        if record and record.get("step") == "approved" and record.get("verdict") == "not-run":
            rows.append({"stage": item["id"], **subject(item, unit)})
    return rows


def review_info(
    bolt: Path, state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]
) -> Optional[dict[str, Any]]:
    """The review header of the stage's HLA or TDD, for information only: it never
    conditions a stage, because it records the organisation's own review."""
    for template in as_list(bind_slice(stage, unit).get("signoff")):
        for rel in expand(template, brownfield_repos(state), unit_ids(state, stage, unit)):
            path = locate(bolt, rel)
            if not path.is_file():
                continue
            header = header_fields(path.read_text(encoding="utf-8", errors="replace")) or {}
            return {
                "path": rel,
                "status": header.get("status") or None,
                "signed_off_by": header.get("signed_off_by") or None,
            }
    return None


def meta_findings(bolt: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Each brownfield target's ``_meta.json`` must carry the fields the freshness check reads."""
    findings: list[dict[str, Any]] = []
    root = planning_root(bolt)
    for repo in brownfield_repos(state):
        meta = read_meta(root, repo)
        if meta is None:
            continue  # the missing-artifact finding already names it
        absent = [key for key in META_KEYS if not meta.get(key)]
        if absent:
            findings.append(
                {
                    "code": "meta-incomplete",
                    "path": f"{ROOT_PREFIX}codekb/{repo}/_meta.json",
                    "message": "empty or missing: " + ", ".join(absent),
                }
            )
    return findings


def last_inception_stage(state: dict[str, Any], catalog: list[dict[str, Any]]) -> Optional[str]:
    """The last Inception stage of the bolt's scope that is not skipped."""
    last: Optional[str] = None
    for item in catalog:
        if item["phase"] != "inception" or state["scope"] not in item["scopes"]:
            continue
        record = state["stages"].get(item["id"])
        if record is None or record["decision"] == "skip":
            continue
        last = item["id"]
    return last


def load_traceability_module() -> Any:
    path = Path(__file__).resolve().parent / "check_traceability.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("aidlc_check_traceability", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    cast(Any, spec.loader).exec_module(module)
    return module


def traceability_findings(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], stage: dict[str, Any]
) -> list[dict[str, Any]]:
    """Refuse the last Inception gate while ids are not traced; bugfix has nothing to trace."""
    if state["scope"] in NO_TRACEABILITY_SCOPES:
        return []
    if stage["id"] != last_inception_stage(state, catalog):
        return []
    module = load_traceability_module()
    if module is None:
        LOG.warning("check_traceability.py is not installed beside this script; skipping.")
        return []
    result = module.check(bolt)
    return [
        {
            "code": "traceability-" + item["code"],
            "path": item.get("id", ""),
            "message": item["message"],
        }
        for item in result["findings"]
    ]


def record_codekb_commits(bolt: Path, state: dict[str, Any]) -> None:
    """Remember which commit of each target's code knowledge this bolt relied on."""
    root = planning_root(bolt)
    for target in state["targets"]:
        meta = read_meta(root, target["repo"]) if target["kind"] == "brownfield" else None
        if meta is not None:
            target["codekb_commit"] = meta.get("commit")


def same_person(left: str, right: str) -> bool:
    """Names compare equal ignoring case and spacing (used for unit owners)."""
    return " ".join(left.split()).casefold() == " ".join(right.split()).casefold()


def decision_rows(text: str) -> list[dict[str, Any]]:
    """Rows of a decision table: ``id``, ``flag``, ``status``, ``owner`` (``None`` when the
    table has no such column) and ``line``. Only the columns it has are read."""
    rows: list[dict[str, Any]] = []
    columns: Optional[dict[str, int]] = None
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip().startswith("|"):
            columns = None
            continue
        cells = [re.sub(r"[*`_]", "", c).strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if columns is None:
            lowered = [c.lower() for c in cells]
            columns = (
                {name: lowered.index(name) for name in lowered if name} if "id" in lowered else {}
            )
            continue
        if not columns or not re.fullmatch(
            r"D\d+", cells[columns["id"]] if columns["id"] < len(cells) else ""
        ):
            continue

        def cell(name: str, cells: list[str] = cells, columns: dict[str, int] = columns) -> Any:
            index = columns.get(name)
            return cells[index] if index is not None and index < len(cells) else None

        rows.append(
            {
                "id": cells[columns["id"]],
                "flag": cell("flag"),
                "status": cell("status"),
                "owner": cell("owner"),
                "line": number,
            }
        )
    return rows


def highest_declared_decision(bolt: Path) -> int:
    """The highest ``D<n>`` in the Bolt's decision records (0 when there are none)."""
    highest = 0
    for name in DECISION_FILES:
        path = bolt / "architecture" / name
        if not path.is_file():
            continue
        for row in decision_rows(path.read_text(encoding="utf-8", errors="replace")):
            highest = max(highest, int(row["id"][1:]))
    return highest


def decision_status_findings(
    bolt: Path, state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]
) -> list[dict[str, Any]]:
    """A decision table may carry a ``Status`` column; its words come from one list."""
    found: list[dict[str, Any]] = []
    for template in bind_slice(stage, unit)["artifacts"]:
        for rel in expand(template, brownfield_repos(state), unit_ids(state, stage, unit)):
            path = locate(bolt, rel)
            if Path(rel).name not in DECISION_FILES or not path.is_file():
                continue
            for row in decision_rows(path.read_text(encoding="utf-8", errors="replace")):
                value = (row["status"] or "").lower()
                if value not in ("", "-", *DECISION_STATUS):
                    message = f"{row['id']}: status '{row['status']}' is not one of "
                    found.append(
                        {
                            "code": "decision-status-unknown",
                            "path": rel,
                            "message": message + ", ".join(DECISION_STATUS),
                        }
                    )
    return found


BOLT_LEVEL_RULE = (
    "Bolt-level stages are not reopened: change the document (the edit is logged as a change "
    "to a passed checkpoint) and the Units that rely on it are told"
)


def is_bolt_level(stage: dict[str, Any]) -> bool:
    """True for a stage that belongs to the whole Bolt. Rework on a per-Unit or per-Slice
    stage is real, so it can be reopened."""
    return not stage["per_unit"] and not is_slice_stage(stage)


def cmd_gate(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    unit: Optional[str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    record = get_record(state, stage, unit)
    label = stage["id"]
    unit_log = "" if is_slice_stage(stage) else (unit or "")
    who = actor(planning_root(bolt))
    note = " ".join((args.note or "").split())
    suffix, warnings = stage_owner(bolt, state, stage, unit)
    if args.request_changes:
        if not note:
            die(EXIT_USAGE, "--request-changes needs --note.")
        if record["step"] == "approved" and is_bolt_level(stage):
            raise Fail(EXIT_FINDINGS, f"stage '{label}' is already passed. {BOLT_LEVEL_RULE}.")
        record["step"] = "changes-requested"
        record["approved_at"] = None
        record["approved_by"] = None
        record.pop("verdict", None)
        nxt = commit(bolt, state, catalog)
        log_event(bolt, "gate-request-changes", label, who, note + suffix, unit_log)
        changed: dict[str, Any] = {
            "ok": True,
            "stage": label,
            **subject(stage, unit),
            "step": record["step"],
            "next": nxt,
        }
        if warnings:
            changed["warnings"] = warnings
        return changed
    findings = gate_findings(bolt, state, stage, unit, record)
    findings.extend(traceability_findings(bolt, state, catalog, stage))
    findings.extend(decision_status_findings(bolt, state, stage, unit))
    verdict, verdict_found = stage_verdict(bolt, state, stage, unit)
    findings.extend(verdict_found)
    if verdict == "not-run" and not note:
        findings.append(
            {
                "code": "verdict-not-run",
                "path": str(stage.get("verdict") or ""),
                "message": "the recorded verdict is not-run; pass --note with the reason "
                "the engineer accepts it unverified",
            }
        )
    if findings:
        raise Fail(
            EXIT_FINDINGS,
            f"gate refused for '{label}': {len(findings)} finding(s).",
            findings=findings,
        )
    context = context_report(bolt, state, catalog, stage, unit)
    review = review_info(bolt, state, stage, unit)
    passed_by = " ".join((args.by or "").split()) or who
    record["step"] = "approved"
    record["approved_at"] = now()
    record["approved_by"] = passed_by or None
    if verdict:
        record["verdict"] = verdict
    else:
        record.pop("verdict", None)
    record["relied_on"] = baseline(bolt, state, catalog, stage, unit)
    if stage["id"] == "reverse-engineering":
        record_codekb_commits(bolt, state)
    nxt = commit(bolt, state, catalog)
    log_event(
        bolt,
        "gate-approve",
        label,
        passed_by,
        ((unit or "") + " " + note).strip() + suffix,
        unit_log,
    )
    suggestion = (
        "A fresh session for the next stage is cheapest but optional. "
        f"Next: {state['next_action']}."
    )
    result: dict[str, Any] = {
        "ok": True,
        "stage": label,
        **subject(stage, unit),
        "step": "approved",
        "next": nxt,
        "suggestion": suggestion,
    }
    if context:
        result["context"] = context
    if review:
        result["review"] = review
    if verdict:
        result["verdict"] = verdict
    if warnings:
        result["warnings"] = warnings
    return result


def normalise_deps(file: Path, uid: str, raw: Any, known: set[str]) -> list[dict[str, str]]:
    """``depends_on`` as ``[{"unit", "on"}]``; a bare id means ``on: done``."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        die(EXIT_MALFORMED, f"{file}: unit {uid} depends_on must be a list.")
    result: list[dict[str, str]] = []
    for item in raw:
        dep = {"unit": item, "on": "done"} if isinstance(item, str) else item
        other = dep.get("unit") if isinstance(dep, dict) else None
        on = dep.get("on", "done") if isinstance(dep, dict) else None
        if not isinstance(other, str) or other not in known:
            die(EXIT_MALFORMED, f"{file}: unit {uid} depends on unknown unit {other!r}.")
        if other == uid:
            die(EXIT_MALFORMED, f"{file}: unit {uid} depends on itself.")
        if on not in DEPENDENCY_ON:
            die(
                EXIT_MALFORMED,
                f"{file}: unit {uid} depends on {other} with on={on!r}; use done or contract.",
            )
        result.append({"unit": other, "on": on})
    return result


def check_cycles(file: Path, deps: dict[str, list[dict[str, str]]]) -> None:
    """Refuse a dependency cycle and name its units in order."""
    done: set[str] = set()

    def visit(uid: str, path: list[str]) -> None:
        if uid in path:
            cycle = [*path[path.index(uid) :], uid]
            die(EXIT_MALFORMED, f"{file}: dependency cycle {' -> '.join(cycle)}.")
        if uid in done:
            return
        for dep in deps[uid]:
            visit(dep["unit"], [*path, uid])
        done.add(uid)

    for uid in deps:
        visit(uid, [])


def is_cancelled(unit: dict[str, Any]) -> bool:
    return bool(unit.get("cancelled"))


def live_units(state: dict[str, Any]) -> list[dict[str, Any]]:
    """The Units that still take part in routing, progress and the "all done" tests."""
    return [u for u in state["units"] if not is_cancelled(u)]


def is_slice_stage(stage: dict[str, Any]) -> bool:
    """True for a stage that runs once per Slice (Build and Test, Operation)."""
    return bool(stage.get("per_slice"))


def subject(stage: dict[str, Any], key: Optional[str]) -> dict[str, Any]:
    """The fields that say whom a stage slot belongs to: a Unit, or a Slice."""
    return {"unit": None, "slice": key} if is_slice_stage(stage) else {"unit": key}


def where_text(row: dict[str, Any]) -> str:
    """``stage [unit]`` or ``stage [slice s1]`` for a row that names a stage slot."""
    if row.get("unit"):
        return f"{row['stage']} [{row['unit']}]"
    return f"{row['stage']} [slice {row['slice']}]" if row.get("slice") else str(row["stage"])


def scope_key(
    state: dict[str, Any], stage: dict[str, Any], unit: Optional[str], slice_id: Optional[str]
) -> Optional[str]:
    """The Unit, or the Slice, a command on ``stage`` is about. A per-Slice stage with no
    ``--slice`` means the only Slice; with several it is a usage error naming them."""
    if not is_slice_stage(stage):
        if slice_id:
            die(EXIT_USAGE, f"stage '{stage['id']}' is not per Slice; drop --slice.")
        return unit
    if unit:
        die(EXIT_USAGE, f"stage '{stage['id']}' runs once per Slice; use --slice, not --unit.")
    ids = [s["id"] for s in state["slices"]]
    if slice_id:
        find_slice(state, slice_id)
        return slice_id
    if len(ids) == 1:
        return ids[0]
    where = f"slices: {', '.join(ids)}" if ids else "there is no Slice yet; `slice --add` one"
    die(EXIT_USAGE, f"stage '{stage['id']}' runs once per Slice; pass --slice ({where}).")


def bind_slice(stage: dict[str, Any], key: Optional[str]) -> dict[str, Any]:
    """The stage with ``<slice>`` filled in, so its paths expand like any other."""
    if not is_slice_stage(stage) or key is None:
        return stage
    return cast(dict[str, Any], json.loads(json.dumps(stage).replace("<slice>", key)))


def find_slice(state: dict[str, Any], sid: str) -> dict[str, Any]:
    for item in state["slices"]:
        if item["id"] == sid:
            return item
    known = ", ".join(s["id"] for s in state["slices"]) or "none yet"
    die(EXIT_USAGE, f"unknown slice '{sid}' (slices: {known}). Add one with `slice --add`.")


def slice_cancelled(state: dict[str, Any], sid: str) -> bool:
    """True for a Slice that had Units and has none left alive."""
    members = [u for u in state["units"] if u.get("slice") == sid]
    return bool(members) and all(is_cancelled(u) for u in members)


def slice_units(state: dict[str, Any], sid: str) -> list[dict[str, Any]]:
    """The Units that are in this Slice and not cancelled: the Unit's own ``slice`` key is
    the only record of membership."""
    return [u for u in live_units(state) if u.get("slice") == sid]


def check_unit_entry(file: Path, unit: Any, seen: set[str]) -> str:
    uid = unit.get("id") if isinstance(unit, dict) else None
    if not isinstance(uid, str) or not ID_PATTERN.match(uid) or uid in seen:
        die(EXIT_MALFORMED, f"{file}: each unit needs a unique lower-case id; saw {uid!r}.")
    for key in ("owner", "repo", "name", "slice"):
        if unit.get(key) is not None and not isinstance(unit[key], str):
            die(EXIT_MALFORMED, f"{file}: unit {uid} {key} must be a string.")
    kind = unit.get("kind")
    if kind is not None and kind not in UNIT_KINDS:
        die(
            EXIT_MALFORMED,
            f"{file}: unit {uid} has kind {kind!r}; use one of {', '.join(UNIT_KINDS)}.",
        )
    return uid


def refuse_owner_change(what: str, ident: str, given: Any, stored: Any, cmd: str) -> None:
    """Ownership changes through ``assign`` only, never as a side effect of loading."""
    if given is not None and (not stored or not same_person(str(given), str(stored))):
        raise Fail(
            EXIT_FINDINGS,
            f"{what} {ident} is owned by {stored or 'nobody'}; the file says {given}. "
            f"Ownership changes only with `{cmd}`. Nothing was changed.",
        )


def cmd_units(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], file: Path
) -> dict[str, Any]:
    """Merge units and slices into the Bolt: add the new, update only the keys the file
    gives, leave everything else alone. Nothing is applied unless the whole file is valid."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(EXIT_INPUT, f"{file}: units file not found.")
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{file}: invalid JSON at line {exc.lineno}: {exc.msg}")
    if not isinstance(data, dict) or not ("units" in data or "slices" in data):
        die(EXIT_MALFORMED, f'{file}: expected an object with "units" and/or "slices".')
    units_in, slices_in = data.get("units", []), data.get("slices", [])
    if not isinstance(units_in, list) or not isinstance(slices_in, list):
        die(EXIT_MALFORMED, f'{file}: "units" and "slices" must be lists.')

    seen: set[str] = set()
    for unit in units_in:
        seen.add(check_unit_entry(file, unit, seen))
    old = {u["id"]: u for u in state["units"]}
    old_slices = {s["id"]: s for s in state["slices"]}
    seen_slices: set[str] = set()
    for entry in slices_in:
        sid = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(sid, str) or not ID_PATTERN.match(sid) or sid in seen_slices:
            die(EXIT_MALFORMED, f"{file}: each slice needs a unique id; saw {sid!r}.")
        seen_slices.add(sid)
        for key in ("name", "owner"):
            if entry.get(key) is not None and not isinstance(entry[key], str):
                die(EXIT_MALFORMED, f"{file}: slice {sid} {key} must be a string.")
        listed = entry.get("units", [])
        if not isinstance(listed, list) or not all(isinstance(m, str) for m in listed):
            die(EXIT_MALFORMED, f"{file}: slice {sid} units must be a list of unit ids.")
        for member in listed:  # the older shape: a slice that lists its units
            if member not in seen and member not in old:
                die(EXIT_MALFORMED, f"{file}: slice {sid} names unknown unit {member!r}.")
    known_slices = set(old_slices) | seen_slices
    known_units = set(old) | seen
    known_repos = [t["repo"] for t in state["targets"]]
    membership = {m: e["id"] for e in slices_in for m in e.get("units", [])}

    merged: dict[str, dict[str, Any]] = {}
    for unit in units_in:
        uid = unit["id"]
        previous = old.get(uid)
        if previous is not None:
            refuse_owner_change(
                "unit", uid, unit.get("owner"), previous.get("owner"), "assign --unit"
            )
        updates = {k: unit[k] for k in ("name", "kind", "repo", "slice") if k in unit}
        if "slice" not in updates and uid in membership:
            updates["slice"] = membership[uid]
        if "depends_on" in unit:
            updates["depends_on"] = normalise_deps(file, uid, unit["depends_on"], known_units)
        repo = updates.get("repo")
        if repo and known_repos and repo not in known_repos:
            die(
                EXIT_MALFORMED,
                f"{file}: unit {uid} has repo {repo!r}; "
                f"this bolt's repositories are {', '.join(known_repos)}.",
            )
        if previous is None and not updates.get("slice") and known_slices:
            raise Fail(
                EXIT_FINDINGS,
                f"{file}: new unit {uid} has no slice, and this Bolt has slices "
                f"({', '.join(sorted(known_slices))}): no Slice's Build and Test would cover it. "
                'Add "slice" to the entry. Nothing was changed.',
            )
        if previous is None:
            merged[uid] = {
                "id": uid, "name": "", "kind": None, "repo": None, "slice": None,
                "owner": unit.get("owner"), "depends_on": [],
                "stages": unit_stage_records(catalog, state["scope"]),
                "story": None, "story_done": None,
                **updates,
            }  # fmt: skip
        else:
            merged[uid] = {**previous, **updates}
    for uid, unit in {**{u["id"]: u for u in state["units"]}, **merged}.items():
        owner_slice = unit.get("slice")
        if owner_slice is not None and owner_slice not in known_slices:
            die(EXIT_MALFORMED, f"{file}: unit {uid} is in unknown slice {owner_slice!r}.")
    combined: dict[str, dict[str, Any]] = {u["id"]: u for u in state["units"]}
    combined.update(merged)
    check_cycles(file, {uid: unit.get("depends_on") or [] for uid, unit in combined.items()})

    slice_updates = merge_slices(file, state, slices_in)
    state["units"] = list(combined.values())  # existing order first, new Units after
    state["slices"] = slice_updates
    backfill_stages(state, catalog)  # the stage records of a new Slice
    nxt = commit(bolt, state, catalog)
    added = [uid for uid in merged if uid not in old]
    log_event(
        bolt, "units", "", "",
        f"{len(added)} unit(s) added, {len(merged) - len(added)} updated; "
        f"{len(state['slices'])} slice(s)",
    )  # fmt: skip
    live = live_units(state)
    return {
        "ok": True,
        "units": [u["id"] for u in state["units"]],
        "added": added,
        "slices": [b["id"] for b in state["slices"]],
        "missing_kind": [u["id"] for u in live if not u["kind"]],
        "missing_owner": [u["id"] for u in live if not u["owner"]],
        "missing_repo": [u["id"] for u in live if not u["repo"]],
        "next": nxt,
    }


def check_slice_deps(file: Path, slices: dict[str, dict[str, Any]]) -> None:
    """Every Slice dependency names a known Slice, and the Slices form no cycle."""
    for sid, record in slices.items():
        deps = record.get("depends_on")
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            die(EXIT_MALFORMED, f"{file}: slice {sid} depends_on must be a list of slice ids.")
        for dep in deps:
            if dep not in slices:
                die(EXIT_MALFORMED, f"{file}: slice {sid} depends on unknown slice {dep!r}.")
    check_cycles(file, {sid: [{"unit": d} for d in r["depends_on"]] for sid, r in slices.items()})


def merge_slices(
    file: Path, state: dict[str, Any], entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Slices by id: add the new, update ``name`` and ``depends_on`` where given, keep every
    other Slice as it is. The owner of an existing Slice changes with ``assign`` only."""
    result = {s["id"]: s for s in state["slices"]}
    for entry in entries:
        sid, current = entry["id"], result.get(entry["id"])
        if current is None:
            result[sid] = new_slice(sid, entry.get("name", ""), entry.get("owner"))
            current = result[sid]
        else:
            refuse_owner_change(
                "slice", sid, entry.get("owner"), current.get("owner"), "assign --slice"
            )
        current.update({k: entry[k] for k in ("name", "depends_on") if k in entry})
    check_slice_deps(file, result)
    return list(result.values())


def slice_status(state: dict[str, Any], catalog: list[dict[str, Any]], sid: str) -> str:
    """planning, ready, building, built, verified, released or cancelled: derived, never stored."""
    record = find_slice(state, sid)
    units = slice_units(state, sid)
    if slice_cancelled(state, sid):
        return "cancelled"
    if not units or not record.get("ready"):
        return "planning"
    stages = record.get("stages") or {}
    bat = stages.get("build-and-test")
    if is_done(bat):
        ran = [
            stages.get(i["id"])
            for i in catalog
            if i.get("per_slice") and i["phase"] == "operation"
            and (stages.get(i["id"]) or {}).get("decision") == "execute"
        ]  # fmt: skip
        if ran and is_done(ran[-1]):
            return "released"
        if bat and bat.get("verdict") == "pass":
            return "verified"  # a skipped or unverified test run never counts as verified
    if all(unit_slot(state, catalog, u["id"]) is None for u in units):
        return "built"
    started = any(r.get("step") != "todo" for u in units for r in (u.get("stages") or {}).values())
    return "building" if started else "ready"


def slice_row(state: dict[str, Any], catalog: list[dict[str, Any]], sid: str) -> dict[str, Any]:
    """One line of facts about a Slice for ``status`` and ``overview``."""
    record = find_slice(state, sid)
    units = slice_units(state, sid)
    return {
        "id": sid,
        "name": record.get("name") or "",
        "owner": record.get("owner"),
        "status": slice_status(state, catalog, sid),
        "units_done": sum(1 for u in units if unit_slot(state, catalog, u["id"]) is None),
        "units_total": len(units),
        "open_gaps": len((record.get("ready") or {}).get("gaps") or []),
        "waits": slice_dep_waits(state, catalog, sid),
        "verification_skipped": verification_skipped(catalog, record.get("stages"), True),
        "verdict": ((record.get("stages") or {}).get("build-and-test") or {}).get("verdict"),
    }


def slice_line(row: dict[str, Any]) -> str:
    status = row["status"] + (f", {row['open_gaps']} open gap(s)" if row["open_gaps"] else "")
    parts = [f"slice {row['id']}", row["name"] or "-", row["owner"] or "-", status]
    parts.append(f"{row['units_done']}/{row['units_total']} units")
    parts.extend(row["waits"])
    if row["verdict"]:
        parts.append(f"verdict {row['verdict']}")
    if row["verification_skipped"]:
        parts.append("verification skipped")
    return "  " + " | ".join(parts)


# --- slices: the readiness checkpoint -----------------------------------------


CONSEQUENCE = {
    "stage": "the Units would build on documents that can still change",
    "questions": "the Slice's scope is not settled, so its Units may build the wrong thing",
    "traceability": "a requirement or story may never be built or tested",
    "decision": "a decision with an unknown status cannot be relied on",
}


def consequence(code: str) -> str:
    return CONSEQUENCE[re.split(r"[-:]", code)[0]]


def unit_for_doc_id(state: dict[str, Any], ident: str) -> Optional[dict[str, Any]]:
    """The Unit of the state that an Inception id (``U-3``) names. Inception writes ``U-n``
    and the Unit id in the state is its lower-case form, with or without the hyphen."""
    return next((u for u in state["units"] if unit_key(u["id"]) == unit_key(ident)), None)


def readiness_gaps(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], sid: str
) -> tuple[list[dict[str, str]], list[str]]:
    """What is missing before this Slice's Units start, and the findings that concern only
    Units of other Slices. Built from the checks that already exist."""
    gaps: list[dict[str, str]] = []

    def add(code: str, message: str) -> None:
        gaps.append({"code": code, "message": message})

    for item in catalog:
        open_stage = item["phase"] in ("discovery", "inception") and not item["per_unit"]
        if open_stage and not is_done(state["stages"].get(item["id"])):
            add(f"stage-open:{item['id']}", f"stage {item['id']} is not done or skipped")
    lint = load_lint_module()
    questions = bolt / "docs" / "slices" / sid / "inception-questions.md"
    if lint is not None and questions.is_file():
        for found in lint.lint_text(questions.read_text(encoding="utf-8", errors="replace"))[
            "findings"
        ]:
            add(f"questions-{found['code']}:{found['question']}", found["message"])
    informational: list[str] = []
    module = None if state["scope"] in NO_TRACEABILITY_SCOPES else load_traceability_module()
    for item in module.check(bolt)["findings"] if module else []:
        code = f"traceability-{item['code']}:{item.get('id', '')}"
        unit = (
            unit_for_doc_id(state, item.get("id", "")) if item.get("id", "")[:2] == "U-" else None
        )
        if unit is not None and unit.get("slice") != sid:
            informational.append(code)
        else:
            add(code, item["message"])
    for item in catalog:
        if any(Path(a).name in DECISION_FILES for a in item["artifacts"]):
            for found in decision_status_findings(bolt, state, item, None):
                add(f"decision-status-unknown:{found['message'].split(':')[0]}", found["message"])
    return gaps, informational


def cmd_slice(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    if args.add:
        if not ID_PATTERN.match(args.add):
            die(EXIT_USAGE, "a slice id is lower-case letters, digits and hyphens.")
        if any(s["id"] == args.add for s in state["slices"]):
            raise Fail(
                EXIT_FINDINGS, f"slice {args.add} already exists; update it with `units --set`."
            )
        owner = " ".join((args.owner or "").split()) or None
        deps = [d for d in (args.depends_on or "").split(",") if d]
        state["slices"] = [*state["slices"], new_slice(args.add, args.name or "", owner, deps)]
        check_slice_deps(Path(args.bolt), {s["id"]: s for s in state["slices"]})
        backfill_stages(state, catalog)
        nxt = commit(bolt, state, catalog)
        log_event(bolt, "slice", "", "", f"added {args.add}")
        return {"ok": True, "slice": args.add, "next": nxt}
    sid = args.ready
    record = next((s for s in state["slices"] if s["id"] == sid), None)
    if record is None:
        raise Fail(EXIT_FINDINGS, f"unknown slice '{sid}'.")
    if not slice_units(state, sid):
        raise Fail(EXIT_FINDINGS, f"slice {sid} has no Units; add them with `units --set`.")
    try:
        check_slice_deps(Path(args.bolt), {s["id"]: s for s in state["slices"]})
    except Fail as exc:
        raise Fail(EXIT_FINDINGS, exc.message) from None
    gaps, informational = readiness_gaps(bolt, state, catalog, sid)
    note = " ".join((args.note or "").split())
    if gaps and not note:
        raise Fail(
            EXIT_FINDINGS,
            f"slice {sid} has {len(gaps)} open gap(s). Close them, or run again with "
            '--note "<direction>" to go on with the gaps open.',
            findings=[
                {
                    "code": g["code"],
                    "message": f"{g['message']}. Consequence: {consequence(g['code'])}.",
                }
                for g in gaps
            ],
        )
    record["ready"] = {"at": now(), "note": note, "gaps": sorted(g["code"] for g in gaps)}
    nxt = commit(bolt, state, catalog)
    text = f"[{sid}] {len(gaps)} open gap(s)" + (f": {note}" if note else "")
    log_event(bolt, "slice-ready", "", "", text)
    return {
        "ok": True,
        "slice": sid,
        "ready": record["ready"],
        "informational": informational,
        "next": nxt,
    }


def cmd_cancel(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    """Take a Unit out of the work without deleting anything it has produced."""
    reason = " ".join((args.reason or "").split())
    if not reason:
        die(EXIT_USAGE, "--cancel needs --reason.")
    unit = find_unit(state, args.cancel)
    if is_cancelled(unit):
        raise Fail(EXIT_FINDINGS, f"unit {args.cancel} is already cancelled.")
    successors = [s for s in (args.superseded_by or "").split(",") if s]
    for other in successors:
        find_unit(state, other)
        if other == args.cancel:
            die(EXIT_USAGE, "--superseded-by cannot name the cancelled unit itself.")
    unit["cancelled"] = {"at": now(), "reason": reason, "superseded_by": successors}
    nxt = commit(bolt, state, catalog)
    by = f" (superseded by {', '.join(successors)})" if successors else ""
    log_event(bolt, "units", "", "", f"cancelled {args.cancel}: {reason}{by}")
    return {"ok": True, "unit": args.cancel, "cancelled": unit["cancelled"], "next": nxt}


def cmd_jira(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    jira = state["jira"]
    forms = [
        args.epic is not None,
        args.story is not None,
        args.done,
        args.off,
        args.on,
    ]
    unit_id = cast(str, args.unit)
    if args.story is not None or args.done:
        if args.unit is None:
            die(EXIT_USAGE, "--story and --done need --unit.")
    elif args.unit is not None:
        die(EXIT_USAGE, "--unit goes with --story or --done.")
    if args.story is not None and args.done:
        die(EXIT_USAGE, "use --story or --done, not both.")
    if sum(forms[:1]) + sum(forms[3:]) + (1 if forms[1] or forms[2] else 0) != 1:
        die(EXIT_USAGE, "give exactly one of --epic, --unit with --story or --done, --off, --on.")
    if args.pr and not args.done:
        die(EXIT_USAGE, "--pr goes with --done.")
    for key in (args.epic, args.story):
        if key is not None and not JIRA_KEY.match(key):
            die(EXIT_USAGE, f"'{key}' is not a Jira key (expected PROJ-123).")
    suffix, warnings = guard_owner(bolt, state, args.unit)
    if args.epic is not None:
        jira["epic"], jira["mode"] = args.epic, "on"
        note = f"epic {args.epic}"
    elif args.story is not None:
        find_unit(state, unit_id)["story"] = args.story
        note = f"[{args.unit}] story {args.story}"
    elif args.done:
        unit = find_unit(state, unit_id)
        if not unit.get("story"):
            raise Fail(
                EXIT_FINDINGS,
                f"unit {args.unit} has no story; record it with `jira --unit {args.unit} "
                "--story KEY` first.",
            )
        unit["story_done"] = {"at": now(), "pr": args.pr}
        note = f"[{args.unit}] done {unit['story']}" + (f" pr {args.pr}" if args.pr else "")
    elif args.off:
        if not (args.reason or "").strip():
            die(EXIT_USAGE, "--off needs --reason.")
        jira["mode"], jira["reason"] = "off", args.reason.strip()
        note = f"off: {jira['reason']}"
    else:
        jira["mode"], jira["reason"] = "on", ""
        note = "on"
    nxt = commit(bolt, state, catalog)
    log_event(bolt, "jira", "", "", note + suffix, args.unit or "")
    result: dict[str, Any] = {"ok": True, "jira": jira_facts(state), "next": nxt}
    if warnings:
        result["warnings"] = warnings
    return result


def require_story(state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]) -> None:
    """Refuse Construction for a unit with no Jira story, unless Jira is off."""
    if unit is None or not is_construction_unit_stage(stage) or not story_missing(state, unit):
        return
    raise Fail(
        EXIT_FINDINGS,
        f"unit {unit} has no Jira story; Construction cannot start.",
        findings=[
            {
                "code": "jira-story-missing",
                "stage": stage["id"],
                "unit": unit,
                "message": (
                    f"file the story with crv-create-jira-story and run `jira --bolt <p> "
                    f"--unit {unit} --story KEY`, or run `jira --bolt <p> --off --reason "
                    '"<why>"`.'
                ),
            }
        ],
    )


def cmd_close(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    status: str,
    successor: Optional[str],
) -> dict[str, Any]:
    require_open(state)
    if status == "complete":
        findings = []
        for item, unit in slots(state, catalog):
            record = slot_record(state, item, unit)
            if record is None:
                message = "per-unit stages have no units"
                if is_slice_stage(item):
                    message = "there is no Slice yet, so Build and Test and Operation have none"
                findings.append({"code": "units-not-loaded", "message": message})
            elif record["decision"] == "pending":
                findings.append(
                    {
                        "code": "decision-pending",
                        "stage": item["id"],
                        **subject(item, unit),
                        "message": "no decision recorded",
                    }
                )
            elif record["decision"] == "execute" and record["step"] != "approved":
                findings.append(
                    {
                        "code": "stage-not-approved",
                        "stage": item["id"],
                        **subject(item, unit),
                        "message": f"step is {record['step']}",
                    }
                )
        open_stories = [
            u["id"] for u in live_units(state) if u.get("story") and not u.get("story_done")
        ]
        if open_stories:
            findings.append(
                {
                    "code": "story-not-done",
                    "message": "stories filed but not recorded as done for units: "
                    + ", ".join(open_stories)
                    + ". Run `jira --unit <u> --done [--pr URL]` after the Story is Done.",
                }
            )
        if findings:
            raise Fail(
                EXIT_FINDINGS,
                f"cannot close as complete: {len(findings)} executed stage(s) are not approved.",
                findings=findings,
            )
    state["status"] = status
    if successor:
        state["successor"] = successor
    state["current"] = {"stage": None, "unit": None}
    state["next_action"] = f"closed as {status}"
    write_state(bolt, state)
    log_event(bolt, "close", "", "", status + (f" successor={successor}" if successor else ""))
    return {"ok": True, "status": status, "successor": successor}


# --- git: commit and push for a shared planning repo ---------------------------

GIT_TIMEOUT = 60
PUSH_ROUNDS = 3
CHANGED_NOTE = "the Bolt changed while you were working"
RERUN_ROUNDS = 3  # times a command is run again on the team's newer state before it gives up
NO_RERUN = {"open", "close"}  # create a Bolt or end one: never run twice on their own
STATE_FILE = re.compile(r"(?:units/[^/]+/)?state\.json")
OWN_TEMP = re.compile(r"\.[\w.-]+\.\d+\.tmp")  # ``.state.json.<pid>.tmp`` of write_json_atomic
STATE_PATH = re.compile(r"bolts/[^/]+/state\.json")  # a Unit's own file keeps its own rule
STATE_AND_LOG = re.compile(r"bolts/[^/]+/(?:units/[^/]+/)?(?:state\.json|log\.md)")
REBASE_STEPS = 50
UNCOMMITTED_CAP = 50
SHARED_FILES = ("architecture-index.json", "aidlc.json")
SHARED_DIRS = ("codekb/",)
INDEX_FILE = "architecture-index.json"
SIDES = (
    "During a rebase 'ours' is the team's version from the remote and 'theirs' is your own commit."
)
SECRET_PATTERNS = [
    ("private key header", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY")),
    (
        "password, secret or token assignment",
        re.compile(r"\b(?:password|passwd|secret|token)\s*=\s*[\"']?[^\s\"'<>{}$*]{8,}", re.I),
    ),
    (
        "connection string with credentials",
        re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]{3,}@", re.I),
    ),
    ("long bearer token", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{40,}", re.I)),
    ("SAS signature", re.compile(r"[?&]sig=[A-Za-z0-9%+/=]{30,}")),
]


@dataclass
class GitCtx:
    top: Path
    prefix: str  # path of the planning root inside the repo, "" or "sub/"
    remote: str = "origin"
    branch: Optional[str] = None  # None: no branch enforced
    commit: bool = True
    push: bool = True


class SoftGitError(Exception):
    """A push-side problem that keeps the local commit and only warns."""


class StateRace(Exception):
    """The team changed a state file this command also changed: run the command again."""


def run_git(
    top: Path,
    *args: str,
    timeout: int = GIT_TIMEOUT,
    env: Optional[dict[str, str]] = None,
    stdin: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, **env} if env else None
    cmd = ["git", "-C", str(top), "-c", "core.quotepath=off", *args]
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            input=stdin,
            env=full_env,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timed out")
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def units_mode(root: Path) -> str:
    """``units`` in the planning repo's aidlc.json: ``split`` or ``inline`` (default)."""
    path = root / "aidlc.json"
    if not path.is_file():
        return "inline"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}")
    mode = data.get("units", "inline") if isinstance(data, dict) else "inline"
    if mode not in UNIT_MODES:
        die(EXIT_MALFORMED, f'{path}: "units" must be one of {", ".join(UNIT_MODES)}.')
    return str(mode)


def load_git_config(root: Path) -> dict[str, Any]:
    path = root / "aidlc.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}")
    section = data.get("git", {}) if isinstance(data, dict) else None
    if not isinstance(section, dict):
        die(EXIT_MALFORMED, f'{path}: "git" must be an object.')
    for key, kind in (("branch", str), ("remote", str), ("commit", bool), ("push", bool)):
        if key in section and not isinstance(section[key], kind):
            die(EXIT_MALFORMED, f"{path}: git.{key} must be a {kind.__name__}.")
    return section


def open_git(root: Path, no_git: bool = False) -> tuple[Optional[GitCtx], str]:
    """The git context of a planning root, or ``None`` and why git is skipped."""
    if no_git:
        return None, "--no-git"
    if os.environ.get("AIDLC_GIT", "").strip().lower() == "off":
        return None, "AIDLC_GIT=off"
    if not root.is_dir():
        return None, "not a folder"
    inside = run_git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return None, "not inside a git work tree"
    top = run_git(root, "rev-parse", "--show-toplevel").stdout.strip()
    prefix = run_git(root, "rev-parse", "--show-prefix").stdout.strip()
    section = load_git_config(root)
    ctx = GitCtx(
        top=Path(top),
        prefix=prefix,
        remote=section.get("remote") or "origin",
        branch=section.get("branch") or None,
        commit=section.get("commit", True),
        push=section.get("push", True),
    )
    return ctx, ""


def current_branch(ctx: GitCtx) -> Optional[str]:
    done = run_git(ctx.top, "symbolic-ref", "--short", "-q", "HEAD")
    return done.stdout.strip() or None if done.returncode == 0 else None


def in_progress(ctx: GitCtx) -> Optional[str]:
    for name, label in (
        ("rebase-merge", "rebase"),
        ("rebase-apply", "rebase"),
        ("MERGE_HEAD", "merge"),
    ):
        done = run_git(ctx.top, "rev-parse", "--git-path", name)
        found = Path(done.stdout.strip())
        if not found.is_absolute():
            found = ctx.top / found
        if done.returncode == 0 and found.exists():
            return label
    return None


def scope_match(ctx: GitCtx, path: str, bolt_rel: Optional[str]) -> bool:
    if not path.startswith(ctx.prefix):
        return False
    rel = path[len(ctx.prefix) :]
    if rel.rsplit("/", 1)[-1] == LOCK_NAME:
        return False  # a session's lock is local; it is never committed
    if OWN_TEMP.fullmatch(rel.rsplit("/", 1)[-1]):
        return False  # a temp file this script left behind when killed is never committed
    if bolt_rel and rel.startswith(bolt_rel.rstrip("/") + "/"):
        return True
    return rel in SHARED_FILES or any(rel.startswith(d) for d in SHARED_DIRS)


def changed_paths(ctx: GitCtx) -> list[str]:
    """Every changed path of the repository, relative to its top; ignored files are absent."""
    done = run_git(ctx.top, "status", "--porcelain=v1", "-z", "-uall", "--no-renames")
    return [item[3:] for item in done.stdout.split("\0") if len(item) > 3]


def pathspec(paths: list[str]) -> str:
    return "".join(f":(literal){p}\0" for p in paths)


def git_paths(ctx: GitCtx, *args: str, paths: list[str]) -> subprocess.CompletedProcess[str]:
    return run_git(
        ctx.top, *args, "--pathspec-from-file=-", "--pathspec-file-nul", stdin=pathspec(paths)
    )


def staged_paths(ctx: GitCtx) -> list[str]:
    done = run_git(ctx.top, "diff", "--cached", "--name-only", "-z", "--no-renames")
    return [p for p in done.stdout.split("\0") if p]


def scan_staged(ctx: GitCtx, scope: set[str]) -> list[tuple[str, int, str]]:
    """``(file, line, pattern name)`` for each likely secret on an added line."""
    done = run_git(
        ctx.top, "diff", "--cached", "--unified=0", "--no-color", "--no-ext-diff", "--no-renames"
    )
    hits: list[tuple[str, int, str]] = []
    name: Optional[str] = None
    line_no = 0
    in_hunk = False
    for raw in done.stdout.split("\n"):
        if raw.startswith("diff --git "):
            name, in_hunk = None, False
        elif not in_hunk and raw.startswith("+++ "):
            target = raw[4:].rstrip("\t")
            name = target[2:] if target.startswith("b/") else None
        elif raw.startswith("@@"):
            in_hunk = True
            found = re.search(r"\+(\d+)", raw)
            line_no = int(found.group(1)) if found else 0
        elif in_hunk and raw.startswith("+"):
            if name in scope:
                for label, pattern in SECRET_PATTERNS:
                    if pattern.search(raw[1:5000]):
                        hits.append((name, line_no, label))
                        break
            line_no += 1
    return hits


def conflict_marker_files(ctx: GitCtx, staged: list[str]) -> list[str]:
    """Staged files that hold a whole git conflict (`<<<<<<< `, `=======`, `>>>>>>> `)."""
    found: list[str] = []
    for name in staged:
        shown = run_git(ctx.top, "show", f":{name}")
        if shown.returncode != 0:
            continue  # deleted, or not text
        stage = 0
        for line in shown.stdout.splitlines():
            if stage == 0 and line.startswith("<<<<<<< "):
                stage = 1
            elif stage == 1 and line.startswith("======="):
                stage = 2
            elif stage == 2 and line.startswith(">>>>>>> "):
                found.append(name)
                break
    return found


def short_head(ctx: GitCtx) -> Optional[str]:
    done = run_git(ctx.top, "rev-parse", "--short", "HEAD")
    return done.stdout.strip() if done.returncode == 0 else None


def head_step(
    ctx: GitCtx, bolt_rel: str, stage: str, unit: Optional[str], per_slice: bool = False
) -> Optional[str]:
    """The step a stage had in the last commit, or ``None`` when HEAD does not say. A
    per-Slice stage's record is in the Bolt's own file; ``unit`` is then the Slice id."""
    base = f"{ctx.prefix}{bolt_rel}"
    own = [f"{base}/units/{unit}/state.json"] if unit and not per_slice else []
    names = [f"{base}/state.json", *own]
    for name in reversed(names):
        shown = run_git(ctx.top, "show", f"HEAD:{name}")
        if shown.returncode != 0:
            continue
        try:
            data = json.loads(shown.stdout)
        except json.JSONDecodeError:
            return None
        if per_slice:
            data = next((s for s in data.get("slices", []) if s.get("id") == unit), {})
        elif unit and "stages" not in data:  # a unit kept inline in the Bolt's file
            data = next((u for u in data.get("units", []) if u.get("id") == unit), {})
        record = (data.get("stages") or {}).get(stage)
        if record is not None or not unit:
            return str((record or {}).get("step")) if record else None
    return None


def warn_approved_changes(
    ctx: GitCtx, bolt_rel: str, changed: list[str], result: dict[str, Any]
) -> bool:
    """Warn, and log once, for each changed artifact of an approved stage; True if logged.

    The commit that records the approval itself is not a change after approval."""
    bolt = ctx.top / ctx.prefix / bolt_rel
    try:
        state = load_state(bolt)
        catalog = load_catalog()
    except Fail:
        return False
    head = f"{ctx.prefix}{bolt_rel}/"
    watched: dict[str, tuple[dict[str, Any], Optional[str]]] = {}
    for item, unit in slots(state, catalog):
        record = slot_record(state, item, unit)
        if record and record.get("step") == "approved":
            for template in bind_slice(item, unit)["artifacts"]:
                for rel in expand(template, brownfield_repos(state), unit_ids(state, item, unit)):
                    watched.setdefault(rel, (item, unit))
    logged = False
    for path in changed:
        found = watched.get(path[len(head) :]) if path.startswith(head) else None
        if found is None:
            continue
        if (
            head_step(ctx, bolt_rel, found[0]["id"], found[1], is_slice_stage(found[0]))
            != "approved"
        ):
            continue
        rel = path[len(head) :]
        stage_id, unit = found[0]["id"], found[1]
        text = f"changed after the checkpoint: {rel} (stage {stage_id} is passed; "
        if is_bolt_level(found[0]):
            text += "Bolt-level stages are not reopened, so tell the Units that rely on it)"
        else:
            flag = f"--slice {unit}" if is_slice_stage(found[0]) else f"--unit {unit}"
            text += f'reopen it with gate --request-changes {flag} --note "<why>")'
        result["warnings"].append(text)
        log_event(
            bolt,
            "approved-change",
            stage_id,
            "",
            rel,
            "" if is_slice_stage(found[0]) else unit or "",
        )
        logged = True
    return logged


def commit_scope(
    ctx: GitCtx, bolt_rel: Optional[str], message: str, result: dict[str, Any]
) -> None:
    changed = changed_paths(ctx)
    if bolt_rel and warn_approved_changes(ctx, bolt_rel, changed, result):
        changed = changed_paths(ctx)  # the log line is new
    scoped = [p for p in changed if scope_match(ctx, p, bolt_rel)]
    others = [p[len(ctx.prefix) :] if p.startswith(ctx.prefix) else p for p in changed]
    others = [o for o, p in zip(others, changed) if not scope_match(ctx, p, bolt_rel)]
    result["uncommitted"] = others[:UNCOMMITTED_CAP]
    result["uncommitted_count"] = len(others)
    if scoped:
        added = git_paths(ctx, "add", "-A", paths=scoped)
        if added.returncode != 0:
            raise Fail(EXIT_GIT, f"git add failed: {added.stderr.strip()[:300]}")
    staged = [p for p in staged_paths(ctx) if scope_match(ctx, p, bolt_rel)]
    if not staged:
        return
    marked = conflict_marker_files(ctx, staged)
    if marked:
        git_paths(ctx, "reset", "-q", paths=staged)
        raise Fail(
            EXIT_GIT,
            f"{len(marked)} file(s) still hold git conflict markers; nothing was committed. "
            "Resolve each one (keep both people's content, remove the `<<<<<<<`, `=======` and "
            "`>>>>>>>` lines), then run `sync` again.",
            findings=[
                {"code": "conflict-markers", "path": n, "message": "unresolved conflict markers"}
                for n in marked
            ],
            extra={"git": result},
        )
    hits = scan_staged(ctx, set(staged))
    if hits:
        git_paths(ctx, "reset", "-q", paths=staged)
        raise Fail(
            EXIT_GIT,
            f"possible secret in {len(hits)} added line(s); nothing was committed. "
            "Remove or mask it, then run `sync` again.",
            findings=[
                {"code": "possible-secret", "path": f"{n}:{ln}", "message": label}
                for n, ln, label in hits
            ],
            extra={"git": result},
        )
    done = git_paths(ctx, "commit", "-q", "-m", message, paths=staged)
    if done.returncode != 0:
        text = (done.stderr or done.stdout).strip()
        raise Fail(
            EXIT_GIT,
            f"git commit failed: {text[:400]}. Fix the cause (identity, hook), then run `sync`.",
            extra={"git": result},
        )
    result["commit"] = short_head(ctx)
    result["message"] = message


def unmerged(ctx: GitCtx) -> list[str]:
    done = run_git(ctx.top, "diff", "--name-only", "--diff-filter=U", "-z")
    return [p for p in done.stdout.split("\0") if p]


def conflict_rule(ctx: GitCtx, path: str) -> str:
    rel = path[len(ctx.prefix) :] if path.startswith(ctx.prefix) else path
    name = rel.rsplit("/", 1)[-1]
    if re.fullmatch(r"bolts/[^/]+/units/[^/]+/state\.json", rel):
        return (
            "two sessions changed the same unit. Do not take a side automatically: compare "
            "both versions, keep the stage steps that match the artifacts that exist, ask the "
            "unit's owner when unsure, then `git add <file>` and `git rebase --continue`, and "
            "run your command again."
        )
    if name == "state.json" and rel.startswith("bolts/"):
        return (
            "a Bolt's state file is never merged and never settled by taking one side. Abort the "
            "rebase (`git rebase --abort`), drop your command's commit with "
            "`git reset --keep HEAD~1`, run `sync` (it sets aside older unshared commits that "
            "changed the file and lists them), then run your command again."
        )
    if name == "log.md" and rel.startswith("bolts/"):
        return (
            "keep every line from both sides, in time order (each line starts with a UTC "
            "time); remove the conflict markers, then `git add <file>`."
        )
    return (
        "keep both people's content and never drop the other person's lines; where two "
        "people answered the same question or decision differently, keep both and mark the "
        "line `contested` for the gate; then run the stage's lint or validator and "
        "`git add <file>`. Say in one line of your summary what you merged."
    )


def conflict_stop(ctx: GitCtx, files: list[str], result: dict[str, Any], why: str) -> Fail:
    return Fail(
        EXIT_GIT,
        f"{why} {len(files)} file(s) conflict. This is not a question for the user: follow the "
        "rule given for each file; where it says to resolve one, `git add` it and run "
        f"`git rebase --continue`, then run `sync` again. {SIDES}",
        findings=[{"code": "conflict", "path": f, "message": conflict_rule(ctx, f)} for f in files],
        extra={"git": result, "sides": SIDES},
    )


def rebase_onto(ctx: GitCtx, ref: str, result: dict[str, Any]) -> None:
    """Rebase the local branch onto ``ref``; settle the index file, stop on other conflicts."""
    env = {"GIT_EDITOR": "true"}
    done = run_git(ctx.top, "rebase", "--autostash", ref, env=env, timeout=120)
    index_path = ctx.prefix + INDEX_FILE
    for _ in range(REBASE_STEPS):
        if done.returncode == 0:
            break
        if in_progress(ctx) is None:
            raise SoftGitError((done.stderr or done.stdout).strip()[:200])
        files = unmerged(ctx)
        if not files:
            run_git(ctx.top, "rebase", "--abort")
            raise SoftGitError("the rebase stopped without conflicts")
        for path in [f for f in files if f == index_path]:
            if run_git(ctx.top, "checkout", "--ours", "--", path).returncode != 0:
                run_git(ctx.top, "rm", "-q", "--", path)
            run_git(ctx.top, "add", "--", path)
            result["rebuild_adr_index"] = True
        rest = [f for f in files if f != index_path]
        if rest:
            raise conflict_stop(ctx, rest, result, "The rebase stopped:")
        done = run_git(ctx.top, "rebase", "--continue", env=env, timeout=120)
    else:
        raise SoftGitError("the rebase did not finish")
    leftover = unmerged(ctx)
    if leftover:
        raise conflict_stop(
            ctx,
            leftover,
            result,
            "Your uncommitted changes (kept in `git stash`, drop it when done) clash with the "
            "team's work:",
        )
    if result.get("commit"):
        result["commit"] = short_head(ctx)  # the commit was rewritten onto the team's work


def count_commits(ctx: GitCtx, spec: str) -> Optional[int]:
    done = run_git(ctx.top, "rev-list", "--count", spec)
    return int(done.stdout.strip()) if done.returncode == 0 else None


def state_race(ctx: GitCtx, ref: str, bolt_rel: str, result: dict[str, Any]) -> list[str]:
    """The ``state.json`` paths of this Bolt that the tip (command) commit and the upstream
    both changed since they diverged; a state file is never merged, so any hit means rerun."""
    if not result.get("commit") or short_head(ctx) != result.get("commit"):
        return []  # the tip is not this command's commit
    mine = run_git(
        ctx.top, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", "HEAD"
    )
    base = f"{ctx.prefix}{bolt_rel}/"
    names = [
        p
        for p in mine.stdout.split("\0")
        if p.startswith(base) and STATE_FILE.fullmatch(p[len(base) :])
    ]
    if not names:
        return []
    theirs = run_git(
        ctx.top, "diff", "--name-only", "-z", "--no-renames", f"HEAD...{ref}", "--", *names
    )
    return [p for p in theirs.stdout.split("\0") if p in names]


def commit_paths(ctx: GitCtx, sha: str) -> list[str]:
    done = run_git(
        ctx.top, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z",
        "--no-renames", sha,
    )  # fmt: skip
    return [p for p in done.stdout.split("\0") if p]


def under_root(ctx: GitCtx, path: str) -> str:
    """``path`` relative to the planning root, or ``""`` when it is outside it."""
    return path[len(ctx.prefix) :] if path.startswith(ctx.prefix) else ""


def unshared_stop(ctx: GitCtx, result: dict[str, Any], paths: list[str], why: str) -> Fail:
    return Fail(
        EXIT_GIT,
        f"{why} Nothing was changed: your branch is exactly as it was. Save the files you "
        "want to keep, then run `sync` again or ask the engineer who changed the same state.",
        findings=[{"code": "conflict", "path": p, "message": conflict_rule(ctx, p)} for p in paths],
        extra={"git": result},
    )


def settle_unshared(
    ctx: GitCtx, ref: str, result: dict[str, Any], own_tip: bool = False
) -> list[str]:
    """Do not rebase unshared commands onto state the team changed meanwhile.

    A command saved while offline (or after three rejected pushes) is a local commit on a
    state file. If the team changed that file too, rebasing it conflicts in ``state.json``
    and ``log.md`` and only a person could settle it. So the commits that touch such a file
    are left out: the branch is rebuilt on ``ref`` and every other unshared commit
    (artifacts, a Unit's own file) is applied again, in order. Never ``reset --hard``:
    uncommitted work stays, and any surprise puts the branch back and stops. Returns the
    subjects of the undone commits and warns with them. ``own_tip`` marks the tip as the
    commit of the command that just ran: that one is never set aside (the command would
    report a change that is not there), so the ordinary rebase stops on it as before."""
    base = run_git(ctx.top, "merge-base", "HEAD", ref).stdout.strip()
    listing = run_git(ctx.top, "rev-list", "--reverse", "--parents", f"{base}..HEAD")
    commits = [line.split() for line in listing.stdout.splitlines()] if base else []
    if not commits or any(len(c) != 2 for c in commits):
        return []  # nothing unshared, or a merge among it: the ordinary rebase decides
    theirs = run_git(ctx.top, "diff", "--name-only", "-z", "--no-renames", base, ref)
    changed = set(theirs.stdout.split("\0"))
    plan = []
    for sha, _parent in commits:
        paths = commit_paths(ctx, sha)
        clash = [p for p in paths if STATE_PATH.fullmatch(under_root(ctx, p)) and p in changed]
        plan.append((sha, paths, clash))
    undone = [item for item in plan if item[2]]
    if not undone or (own_tip and plan[-1][2] and short_head(ctx) == result.get("commit")):
        return []
    for sha, paths, clash in undone:
        if not all(STATE_AND_LOG.fullmatch(under_root(ctx, p)) for p in paths):
            subject = run_git(ctx.top, "log", "-1", "--format=%s", sha).stdout.strip()
            raise unshared_stop(
                ctx, result, clash,
                f"The commit '{subject}' changed a state file the team changed too, together "
                "with other files, so it cannot be set aside on its own.",
            )  # fmt: skip
    origin = run_git(ctx.top, "rev-parse", "HEAD").stdout.strip()
    moved = run_git(ctx.top, "reset", "--keep", ref)
    if moved.returncode != 0:
        raise unshared_stop(
            ctx, result, [],
            "Your uncommitted changes would be overwritten by the team's work "
            f"({(moved.stderr or moved.stdout).strip()[:200]}).",
        )  # fmt: skip
    env = {"GIT_EDITOR": "true"}
    for sha, _paths, clash in plan:
        if clash:
            continue
        picked = run_git(ctx.top, "cherry-pick", sha, env=env)
        if picked.returncode == 0:
            continue
        files = unmerged(ctx)
        if not files and "empty" in (picked.stderr + picked.stdout):
            run_git(ctx.top, "cherry-pick", "--skip", env=env)  # the team already has it
            continue
        run_git(ctx.top, "cherry-pick", "--abort", env=env)
        back = run_git(ctx.top, "reset", "--keep", origin)
        subject = run_git(ctx.top, "log", "-1", "--format=%s", sha).stdout.strip()
        note = "" if back.returncode == 0 else f" Put it back with `git reset --keep {origin}`."
        raise unshared_stop(
            ctx, result, files,
            f"The unshared commit '{subject}' does not apply on the team's work.{note}",
        )  # fmt: skip
    subjects = [
        run_git(ctx.top, "log", "-1", "--format=%s", sha).stdout.strip() for sha, *_ in undone
    ]
    result["undone"] = subjects
    if result.get("commit"):  # the tip was applied again under a new hash, or set aside
        result["commit"] = None if plan[-1][2] else short_head(ctx)
    result["warnings"].append(
        "these changes were made while not shared and the team changed the same state since; "
        "they were undone: repeat them: " + "; ".join(subjects)
    )
    return subjects


def push_branch(
    ctx: GitCtx,
    branch: Optional[str],
    result: dict[str, Any],
    race_bolt: Optional[str] = None,
    own_tip: bool = False,
) -> None:
    """Fetch, rebase onto the team's work and push; ``race_bolt`` names the Bolt whose
    state a just-committed command changed, so the command can be run again instead of
    rebasing its state file (raises ``StateRace``)."""
    warnings: list[str] = result["warnings"]
    if branch is None:
        warnings.append("push: skipped, HEAD is detached")
        return
    remotes = run_git(ctx.top, "remote").stdout.split()
    if ctx.remote not in remotes:
        warnings.append(f"push: skipped, no remote '{ctx.remote}'")
        return
    if run_git(ctx.top, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        return  # nothing committed yet
    ref = f"refs/remotes/{ctx.remote}/{branch}"
    failed = "push: failed, retried at the next event (saved in this clone, not shared yet)"

    def give_up() -> None:
        result["not_shared"] = True
        warnings.append(failed)

    try:
        for _round in range(PUSH_ROUNDS):
            fetch = run_git(
                ctx.top, "fetch", ctx.remote, branch, timeout=FETCH_TIMEOUT, env=FETCH_ENV
            )
            remote_has = fetch.returncode == 0
            if not remote_has and "find remote ref" not in fetch.stderr:
                give_up()
                return
            if remote_has:
                if (count_commits(ctx, f"HEAD..{ref}") or 0) > 0:
                    if race_bolt is not None and state_race(ctx, ref, race_bolt, result):
                        raise StateRace
                    settle_unshared(ctx, ref, result, own_tip)
                    if (count_commits(ctx, f"HEAD..{ref}") or 0) > 0:
                        rebase_onto(ctx, ref, result)
                if count_commits(ctx, f"{ref}..HEAD") == 0:
                    return  # nothing to push
            args = ["push"]
            if run_git(ctx.top, "rev-parse", "--abbrev-ref", "@{u}").returncode != 0:
                args.append("-u")
            pushed = run_git(ctx.top, *args, ctx.remote, f"HEAD:{branch}", env=FETCH_ENV)
            if pushed.returncode == 0:
                result["pushed"] = True
                return
            lost = any(w in pushed.stderr for w in ("rejected", "fetch first", "non-fast-forward"))
            if not lost:
                give_up()
                return
        give_up()
    except SoftGitError:
        give_up()


def sync_git(
    ctx: GitCtx,
    bolt_rel: Optional[str],
    slug: str,
    event: str,
    rerunnable: bool = False,
    after_command: bool = False,
) -> dict[str, Any]:
    """Bring in the team's work, commit this bolt's changes and push them.

    With ``rerunnable`` the commit is a command's own: if the team changed a state file
    of the Bolt meanwhile, ``StateRace`` is raised before anything is rebased or pushed."""
    result: dict[str, Any] = {
        "enabled": True,
        "branch": None,
        "commit": None,
        "pushed": False,
        "not_shared": False,
        "warnings": [],
        "uncommitted": [],
        "uncommitted_count": 0,
        "rebuild_adr_index": False,
    }
    pending = in_progress(ctx)
    if pending:
        files = unmerged(ctx)
        text = (
            f"a {pending} is in progress. Finish it: resolve the conflicted files, `git add` "
            f"them, run `git {pending} --continue`, then run `sync` again. {SIDES}"
        )
        raise Fail(
            EXIT_GIT,
            text,
            findings=[
                {"code": "conflict", "path": f, "message": conflict_rule(ctx, f)} for f in files
            ],
            extra={"git": result, "sides": SIDES},
        )
    current = current_branch(ctx)
    result["branch"] = current
    if ctx.branch and current != ctx.branch:
        raise Fail(
            EXIT_FINDINGS,
            f"the planning repo is on '{current or 'a detached HEAD'}' but aidlc.json expects "
            f"'{ctx.branch}'. Run: git switch {ctx.branch}",
        )
    event = " ".join(event.split())
    message = f"docs({slug}): {event}" if slug else f"docs: {event}"
    if ctx.commit:
        commit_scope(ctx, bolt_rel, message, result)
    if ctx.push:
        push_branch(
            ctx, ctx.branch or current, result, bolt_rel if rerunnable else None, after_command
        )
    for text in result["warnings"]:
        LOG.warning("%s", text)
    return result


def git_scope(bolt: Path) -> tuple[Path, str, str]:
    """``(planning root, bolt path inside it, slug)`` of a bolt folder."""
    resolved = bolt.resolve()
    root = planning_root(bolt)
    return root, resolved.relative_to(root).as_posix(), DATE_PREFIX.sub("", resolved.name)


def git_event(args: argparse.Namespace, result: Optional[dict[str, Any]] = None) -> str:
    """The plain-English name of what a changing command does."""
    cmd = args.command
    if cmd == "open":
        return "open the bolt"
    if cmd == "decide":
        return f"decide {args.stage}: {args.decision}"
    if cmd == "step":
        return f"move {args.stage} to {args.to}"
    if cmd == "gate":
        if args.approve:
            return f"approve the {args.stage} gate"
        return f"request changes on {args.stage}"
    if cmd == "decision-id":
        ids = (result or {}).get("ids") or []
        if len(ids) > 1:
            return f"reserve decision ids {ids[0]}-{ids[-1]}"
        return f"reserve decision id {ids[0]}" if ids else "reserve decision ids"
    if cmd == "units":
        return f"cancel unit {args.cancel}" if args.cancel else "load the units"
    if cmd == "assign":
        what = f"unit {args.unit}" if args.unit else f"slice {args.slice}"
        return f"assign {what} to {args.owner}"
    if cmd == "slice":
        return f"add slice {args.add}" if args.add else f"mark slice {args.ready} ready"
    if cmd == "brief":
        return f"write the brief of unit {args.unit}"
    if cmd == "context":
        what = f"unit {args.unit}" if args.unit else f"slice {args.slice}"
        return f"record a context conclusion on {what}"
    if cmd == "contribution":
        return f"record contribution {args.concern}: {args.status}"
    if cmd == "park":
        return "park the bolt"
    if cmd == "unpark":
        return "unpark the bolt"
    if cmd == "jira":
        return "record Jira keys"
    if cmd == "target":
        if args.add:
            return f"add target {args.add.partition('=')[0]}"
        return f"remove target {args.remove}"
    if cmd == "close":
        return f"close the bolt as {args.status}"
    return "update the workspace folders"


def changes_state(args: argparse.Namespace) -> bool:
    if args.command == "workspace":
        return bool(args.extra)
    if args.command == "brief":
        return bool(args.write)
    if args.command == "context":
        return args.note is not None
    return args.command in {
        "open", "decide", "step", "gate", "units", "decision-id", "park", "unpark",
        "jira", "target", "close", "assign", "slice", "contribution",
    }  # fmt: skip


def cmd_sync(args: argparse.Namespace) -> dict[str, Any]:
    if bool(args.bolt) == bool(args.root):
        die(EXIT_USAGE, "give --bolt or --root, not both and not neither.")
    if args.bolt:
        bolt = Path(args.bolt)
        if not bolt.is_dir():
            die(EXIT_INPUT, f"{bolt}: bolt folder not found.")
        root, rel, slug = git_scope(bolt)
        bolt_rel: Optional[str] = rel
    else:
        root, bolt_rel, slug = Path(args.root), None, ""
        if not root.is_dir():
            die(EXIT_INPUT, f"{root}: --root is not a directory.")
    ctx, why = open_git(root.resolve())
    if ctx is None:
        return {"ok": True, "git": {"enabled": False, "reason": why}}
    return {"ok": True, "git": sync_git(ctx, bolt_rel, slug, args.message)}


def upstream_ref(ctx: GitCtx) -> Optional[str]:
    """The fetched remote branch this checkout publishes to, or ``None`` when there is none."""
    target = ctx.branch or current_branch(ctx)
    if not target:
        return None
    ref = f"refs/remotes/{ctx.remote}/{target}"
    return ref if run_git(ctx.top, "rev-parse", "--verify", "-q", ref).returncode == 0 else None


def unshared_line(count: Optional[int]) -> str:
    """One line for the local commits the team does not have yet; empty when there is none."""
    return f"{count} change(s) saved here, not shared yet" if count else ""


def git_status_block(bolt: Path) -> Optional[dict[str, Any]]:
    """Branch, ahead and behind, and uncommitted paths. Reads only; never fetches."""
    root, rel, _ = git_scope(bolt)
    try:
        ctx, _why = open_git(root)
    except Fail:
        return None
    if ctx is None:
        return None
    branch = current_branch(ctx)
    block: dict[str, Any] = {
        "branch": branch,
        "expected_branch": ctx.branch,
        "remote": ctx.remote,
        "ahead": None,
        "behind": None,
    }
    ref = upstream_ref(ctx)
    if ref:
        block["ahead"] = count_commits(ctx, f"{ref}..HEAD")
        block["behind"] = count_commits(ctx, f"HEAD..{ref}")
    block["unshared"] = block["ahead"]
    mine = ctx.prefix + rel + "/"
    block["uncommitted"] = sum(1 for p in changed_paths(ctx) if p.startswith(mine))
    if block["uncommitted"]:
        block["hint"] = 'commit them now: sync --bolt <p> -m "<what changed>"'
    return block


def git_status_line(block: dict[str, Any]) -> str:
    where = block["branch"] or "detached HEAD"
    if block["expected_branch"] and block["expected_branch"] != block["branch"]:
        where += f" (expected {block['expected_branch']})"
    sync = (
        f"ahead {block['ahead']}, behind {block['behind']}"
        if block["ahead"] is not None
        else "no fetched remote branch"
    )
    line = f"Git: {where}, {sync}, {block['uncommitted']} uncommitted in this bolt"
    if block["uncommitted"]:
        line += '; commit them now with `sync --bolt <p> -m "<what changed>"`'
    if unshared_line(block.get("unshared")):
        line += f"\n{unshared_line(block['unshared'])}"
    return line


# --- command line ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open, advance, gate and close an AI-DLC bolt.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    read_only = {"status", "next", "inputs", "codekb-status", "overview"}

    def add(name: str, help_text: str, bolt: bool = True) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text, description=help_text)
        if bolt:
            sp.add_argument("--bolt", required=True, help="Bolt folder.")
        if name not in read_only:
            sp.add_argument(
                "--no-git", action="store_true", help="Do not commit or push this change."
            )
        return sp

    sp = add("open", "Create a bolt.", bolt=False)
    sp.add_argument("--root", required=True, help="Planning repository root (contains bolts/).")
    sp.add_argument("--slug", required=True)
    sp.add_argument("--title", required=True)
    sp.add_argument("--intent", required=True, help="One sentence.")
    sp.add_argument("--scope", choices=SCOPES, default="classic")
    sp.add_argument("--depth", choices=DEPTHS, help="Default: standard, or minimal for bugfix.")
    sp.add_argument(
        "--target", action="append", metavar="name=path", help="Target repository; repeatable."
    )
    sp.add_argument("--architecture-ref", help="ADR registry checkout; its commit is recorded.")
    sp.add_argument("--owner", help="Bolt owner (optional).")
    sp.add_argument("--date", help="Override the date part of the id, YYYY-MM-DD.")
    sp.add_argument(
        "--units",
        choices=UNIT_MODES,
        help="split: one state file and log per unit, so engineers do not collide "
        '(default: "units" in aidlc.json, else inline).',
    )

    sp = add("overview", "Roll up every Bolt of a planning repository; writes nothing.", bolt=False)
    sp.add_argument("--root", required=True, help="Planning repository root (contains bolts/).")
    sp.add_argument("--format", choices=["json", "text"], default="json")
    sp.add_argument("--log", type=int, metavar="N", help="Add the last N log lines of all Bolts.")

    sp = add("status", "Show progress.")
    sp.add_argument("--format", choices=["json", "text"], default="json")

    sp = add("next", "Show the next stage and step.")
    group = sp.add_mutually_exclusive_group()
    group.add_argument("--unit", help="Only this unit: its next stage and what it waits for.")
    group.add_argument("--slice", help="Only this slice: its next stage and what it waits for.")
    group.add_argument(
        "--mine", action="store_true", help="Every unit and slice you own, as --unit does."
    )

    sp = add("inputs", "List the files a stage reads.")
    sp.add_argument("--stage", required=True)
    sp.add_argument("--unit")
    sp.add_argument("--slice", help="For a per-Slice stage (Build and Test, Operation): the slice.")

    sp = add("decide", "Record EXECUTE or SKIP for a stage.")
    sp.add_argument("--stage", required=True)
    sp.add_argument("--decision", required=True, choices=["execute", "skip"])
    sp.add_argument("--reason", required=True)
    sp.add_argument("--unit")
    sp.add_argument("--slice", help="For a per-Slice stage (Build and Test, Operation): the slice.")

    sp = add("step", "Move a stage forward.")
    sp.add_argument("--stage", required=True)
    sp.add_argument("--to", required=True, choices=["asked", "analysed", "produced"])
    sp.add_argument("--unit")
    sp.add_argument("--slice", help="For a per-Slice stage (Build and Test, Operation): the slice.")

    sp = add("gate", "Approve a stage or send it back.")
    sp.add_argument("--stage", required=True)
    sp.add_argument("--unit")
    sp.add_argument("--slice", help="For a per-Slice stage (Build and Test, Operation): the slice.")
    group = sp.add_mutually_exclusive_group(required=True)
    group.add_argument("--approve", action="store_true")
    group.add_argument("--request-changes", action="store_true")
    sp.add_argument("--by", help="Who passes the checkpoint (default: you, as git user.name).")
    sp.add_argument(
        "--note",
        help="With --approve: the direction or decision in one line, logged. "
        "With --request-changes: why (required).",
    )

    sp = add("assign", "Set the owner of a unit or a slice.")
    sp.add_argument("--unit")
    sp.add_argument("--slice", help="Set the owner of this slice instead.")
    sp.add_argument("--owner", required=True, help="A person's name, as in their git user.name.")

    sp = add("slice", "Add a slice, or check that one is ready for its units to start.")
    group = sp.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", metavar="ID", help="Add a slice.")
    group.add_argument("--ready", metavar="ID", help="The readiness checkpoint of a slice.")
    sp.add_argument("--name", help="With --add: the slice's name.")
    sp.add_argument("--owner", help="With --add: who owns the slice.")
    sp.add_argument("--depends-on", help="With --add: slice ids it waits for, s1,s2.")
    sp.add_argument(
        "--note", help="With --ready: the direction, needed to go on while gaps are open."
    )

    sp = add("context", "What changed under a unit or slice, and what it relies on.")
    sp.add_argument("--unit")
    sp.add_argument("--slice")
    sp.add_argument("--stage", help="Only this stage of the unit or slice.")
    sp.add_argument("--id", help="Instead: who relies on this id (a unit, slice and file list).")
    sp.add_argument(
        "--note", help="Record your conclusion in the log; it refreshes what was reported."
    )

    sp = add("brief", "A unit's starting page, from state only; --write saves it in the bolt.")
    sp.add_argument("--unit", required=True)
    sp.add_argument("--write", action="store_true", help="Write docs/construction/<unit>/brief.md.")

    sp = add("units", "Add or update units and slices from a JSON file, or cancel a unit.")
    group = sp.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--set",
        dest="file",
        help='JSON with "units" (id, name, kind, repo, depends_on, slice) and/or "slices"; '
        "new ids are added, given keys of existing ones updated, the rest untouched; kind: "
        + "|".join(UNIT_KINDS),
    )
    group.add_argument("--cancel", metavar="UNIT", help="Take a unit out of the work.")
    sp.add_argument("--reason", help="With --cancel: why.")
    sp.add_argument("--superseded-by", help="With --cancel: the unit ids that replace it, a,b.")

    sp = add("decision-id", "Reserve the next decision ids.")
    sp.add_argument("--count", type=int, default=1)
    sp.add_argument("--unit", help="Number from this unit's own counter; cite as <unit>:D<n>.")

    add("codekb-status", "Is each target's shared code knowledge fresh, stale or missing.")

    sp = add("workspace", "Write the multi-root workspace file and report each checkout.")
    sp.add_argument(
        "--extra",
        action="append",
        metavar="name=path",
        help="Extra folder, kept in .aidlc-local.json; repeatable. name= with no path removes it.",
    )
    sp.add_argument(
        "--fetch",
        action="store_true",
        help=f"git fetch origin per repository first ({FETCH_TIMEOUT} s each, no prompts).",
    )
    sp.add_argument("--out", help="Workspace file (default: <bolt>/<id>.code-workspace).")

    sp = add("target", "Add or remove a target repository; it is classified as at open.")
    group = sp.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", metavar="name=path", help="Add or replace a target.")
    group.add_argument("--remove", metavar="NAME", help="Remove a target by name.")

    sp = add("contribution", "Record where an architecture contribution stands.")
    sp.add_argument("--concern", required=True, help="File name of the contribution, no .md.")
    sp.add_argument("--status", required=True, choices=list(CONTRIBUTION_STATUS))
    sp.add_argument("--note", help="One line for the log.")

    sp = add("park", "Leave a hand-over note.")
    sp.add_argument("--note", required=True)
    add("unpark", "Clear the hand-over note.")

    sp = add("jira", "Record Jira keys: one epic per bolt, one story per unit.")
    sp.add_argument("--epic", help="The bolt's Epic key; turns Jira on.")
    sp.add_argument("--unit", help="With --story or --done.")
    sp.add_argument("--story", help="The unit's Story key.")
    sp.add_argument("--done", action="store_true", help="The unit's Story is Done.")
    sp.add_argument("--pr", help="With --done: the merged pull request URL.")
    sp.add_argument("--off", action="store_true", help="Turn Jira off; needs --reason.")
    sp.add_argument("--reason", help="Why Jira is off.")
    sp.add_argument("--on", action="store_true", help="Turn Jira on.")

    sp = sub.add_parser(
        "sync",
        help="Commit and push work that changed files but no state.",
        description="Bring in the team's work, commit the bolt (or only the shared paths "
        "with --root) and push.",
    )
    sp.add_argument("--bolt", help="Bolt folder.")
    sp.add_argument("--root", help="Planning repository root: commit only the shared paths.")
    sp.add_argument("-m", "--message", default="save work in progress", help="What changed.")

    sp = add("close", "Close the bolt.")
    sp.add_argument("--status", required=True, choices=["complete", "superseded", "archived"])
    sp.add_argument("--successor", help="Id of the bolt that replaces this one.")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Run a command. One that changes a Bolt (or syncs) holds the checkout lock for its
    whole run, git syncs included; a read takes no lock."""
    if args.command != "sync" and not changes_state(args):
        return run_locked(args)
    with checkout_lock(lock_location(args)):
        return run_changing(args)


def run_changing(args: argparse.Namespace) -> dict[str, Any]:
    """A command that changes a bolt is wrapped in two git syncs."""
    if args.command == "sync":
        return cmd_sync(args)
    if getattr(args, "no_git", False):
        return run_locked(args)
    if args.command == "open":
        root, rel, slug = Path(args.root), None, ""
    else:
        load_state(Path(args.bolt))  # report a missing or broken bolt before any git work
        root, rel, slug = git_scope(Path(args.bolt))
    ctx, _why = open_git(root.resolve())
    if ctx is None:
        return run_locked(args)
    event = git_event(args)
    before = sync_git(ctx, rel, slug, f"save work before {event}")
    reserving = args.command == "decision-id"
    if reserving and not args.unit and before["not_shared"]:
        raise Fail(
            EXIT_GIT,
            "cannot confirm the shared decision counter with the remote; fix the connection, "
            "then run decision-id again",
            extra={"git": before},
        )
    not_reserved = (
        "the ids were not reserved (they could not be shared with the team): fix the cause, "
        "then run decision-id again"
    )
    can_rerun = args.command not in NO_RERUN
    carry: dict[str, Any] = {"warnings": [], "rebuild_adr_index": False}
    reruns = 0
    while True:
        try:
            result = run_locked(args)
        except Fail as exc:
            if reruns:  # its precondition changed under it: leave nothing half-applied
                restore_bolt_files(ctx, rel)
                exc.message = f"{CHANGED_NOTE}: {exc.message}"
            raise
        if args.command == "open":
            _root, rel, slug = git_scope(Path(result["bolt"]))
        try:
            after = sync_git(
                ctx, rel, slug, git_event(args, result), rerunnable=can_rerun, after_command=True
            )
            break
        except StateRace:
            drop_and_catch_up(ctx, carry)
            if reruns >= RERUN_ROUNDS:
                raise Fail(
                    EXIT_GIT,
                    f"the team changed this Bolt {RERUN_ROUNDS + 1} times while the command "
                    "was running. Your change was NOT applied; run the command again.",
                ) from None
            reruns += 1
        except Fail as exc:
            if reserving:
                result = {k: v for k, v in result.items() if k not in ("ids", "cite_as")}
                exc.message = f"{not_reserved}. {exc.message}"
            exc.extra.setdefault("result", result)
            raise
    if reruns:
        after["reruns"] = reruns
        after["warnings"].append(f"{CHANGED_NOTE}; the command ran again on the new state")
    if carry["rebuild_adr_index"]:
        after["rebuild_adr_index"] = True
    if carry.get("undone"):
        after["undone"] = [*after.get("undone", []), *carry["undone"]]
    after["warnings"].extend(carry["warnings"])
    if reserving and after["not_shared"]:
        raise Fail(
            EXIT_GIT,
            not_reserved,
            extra={
                "git": after,
                "result": {k: v for k, v in result.items() if k not in ("ids", "cite_as")},
            },
        )
    result["git"] = after
    if before["commit"] or before["rebuild_adr_index"] or before["warnings"]:
        result["git_before"] = before
    return result


def restore_bolt_files(ctx: GitCtx, bolt_rel: Optional[str]) -> None:
    """Put the Bolt's state and log files back as committed, after a command that failed on
    a re-run. Only tracked files change; ``git checkout`` of paths, never ``reset --hard``."""
    if bolt_rel is None:
        return
    done = run_git(ctx.top, "diff", "--name-only", "-z", "--no-renames", "HEAD")
    base = f"{ctx.prefix}{bolt_rel}/"
    names = [
        p
        for p in done.stdout.split("\0")
        if p.startswith(base) and p.rsplit("/", 1)[-1] in ("state.json", "log.md")
    ]
    if names:
        git_paths(ctx, "checkout", "-q", "HEAD", paths=names)


def drop_and_catch_up(ctx: GitCtx, carry: dict[str, Any]) -> None:
    """Drop the command's commit (the tip) and bring the clone up to the team's work.

    ``git reset --keep`` moves only that commit away and refuses, rather than overwrite,
    a file with local edits. Any other unpushed commit is rebased in the normal way."""
    stuck = (
        "The team changed the same state file while your command ran, and your last local "
        "commit could not be dropped"
    )
    dropped = run_git(ctx.top, "reset", "--keep", "HEAD~1")
    if dropped.returncode != 0:
        raise Fail(
            EXIT_GIT,
            f"{stuck} ({(dropped.stderr or dropped.stdout).strip()[:200]}). Nothing was shared. "
            "Save or commit the files git names, run `git reset --keep HEAD~1`, then "
            "`git pull --rebase`, and run the command again.",
        )
    branch = ctx.branch or current_branch(ctx)
    ref = f"refs/remotes/{ctx.remote}/{branch}"
    try:
        if branch and (count_commits(ctx, f"HEAD..{ref}") or 0) > 0:
            settle_unshared(ctx, ref, carry)
            if (count_commits(ctx, f"HEAD..{ref}") or 0) > 0:
                rebase_onto(ctx, ref, carry)
    except SoftGitError as exc:
        raise Fail(
            EXIT_GIT,
            f"Your change was NOT applied (the team's work clashed with it and it was dropped); "
            f"the clone could not be brought up to date: {exc}. Run `git pull --rebase`, then "
            "run the command again.",
        ) from None
    except Fail as exc:
        exc.message = (
            f"Your change was NOT applied; run the command again once this is done. {exc.message}"
        )
        raise


def lock_wait() -> float:
    """Seconds to wait for the checkout lock; ``AIDLC_LOCK_WAIT`` is for tests only."""
    raw = os.environ.get(LOCK_WAIT_ENV, "")
    try:
        return float(raw) if raw else LOCK_WAIT
    except ValueError:
        return LOCK_WAIT


def lock_busy(path: Path, waited: float) -> Fail:
    return Fail(
        EXIT_FINDINGS,
        f"another session in this checkout is still working (waited {int(waited)} s for "
        f"{path}); it may be waiting for the network. Let it finish, then run the command again.",
    )


def lock_location(args: argparse.Namespace) -> Optional[Path]:
    """The checkout-wide lock file of a command, or ``None`` when there is nothing to lock.

    Inside the git directory of the planning checkout, so it is never a work-tree file; at
    the planning root only when the root is not inside a git repository."""
    if args.command == "open" or (args.command == "sync" and args.root):
        root = Path(args.root)
    elif getattr(args, "bolt", None):
        bolt = Path(args.bolt)
        if not bolt.is_dir():
            return None  # the command reports the missing Bolt
        root = planning_root(bolt)
    else:
        return None
    if not root.is_dir():
        return None
    root = root.resolve()
    # With --no-git or AIDLC_GIT=off nothing is committed, but the lock is still the git
    # directory's, so a session that commits and one that does not exclude each other.
    inside = run_git(root, "rev-parse", "--is-inside-work-tree")
    found = run_git(root, "rev-parse", "--git-path", "aidlc.lock")
    if inside.stdout.strip() == "true" and found.returncode == 0:
        path = Path(found.stdout.strip())
        return path if path.is_absolute() else root / path
    return root / LOCK_NAME


def flock_open(path: Path, deadline: float, started: float) -> int:
    """Open ``path`` and take its ``flock``; return the descriptor that holds it.

    A holder may delete the file when it is done (see ``flock_lock``). Once we own the
    lock we check that the path still names the file we hold, else we start again."""
    while True:
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
        while True:
            try:
                _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    raise lock_busy(path, time.monotonic() - started) from None
                time.sleep(LOCK_POLL)
        try:
            same = path.stat().st_ino == os.fstat(fd).st_ino
        except FileNotFoundError:
            same = False
        if same:
            return fd
        os.close(fd)


@contextlib.contextmanager
def flock_lock(path: Path, wait: float) -> Iterator[None]:
    """Hold an exclusive ``flock`` on ``path``; the operating system frees it when we die.

    A lock file in the work tree is deleted on the way out so it never shows in
    ``git status``; one inside the git directory stays."""
    started = time.monotonic()
    fd = flock_open(path, started + wait, started)
    try:
        try:  # the file is a note for people; the lock is the flock
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()} {now()}\n".encode())
        except OSError:
            pass
        yield
    finally:
        if path.name == LOCK_NAME:
            path.unlink(missing_ok=True)  # while we still hold it
        os.close(fd)  # releases the lock


@contextlib.contextmanager
def fallback_lock(path: Path, wait: float) -> Iterator[None]:
    """Where ``fcntl`` is missing (native Windows): an exclusive-create file.

    Not exercised on Windows. After a crash it is only freed by age (``LOCK_STALE``), so
    it gives weaker guarantees than ``flock_lock``."""
    deadline = time.monotonic() + wait
    started = time.monotonic()
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue  # released a moment ago: try again
            if age >= LOCK_STALE:
                LOG.warning("took over a lock left %d s ago by a session that stopped", age)
                path.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise lock_busy(path, time.monotonic() - started) from None
            time.sleep(LOCK_POLL)
            continue
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(f"{os.getpid()} {now()}\n")
        break
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


@contextlib.contextmanager
def checkout_lock(path: Optional[Path]) -> Iterator[None]:
    """One exclusive lock per planning checkout for a whole state-changing command."""
    if path is None:
        yield
        return
    wait = lock_wait()
    with flock_lock(path, wait) if _fcntl else fallback_lock(path, wait):
        yield


def run_locked(args: argparse.Namespace) -> dict[str, Any]:
    _INDEXES.clear()  # ids are parsed once per command, never carried over to the next
    catalog = load_catalog()
    if args.command == "open":
        return cmd_open(args, catalog)

    if args.command == "overview":
        return cmd_overview(args, catalog)
    bolt = Path(args.bolt)
    state = load_state(bolt)
    backfill_stages(state, catalog)
    if is_split(state):
        refresh(state, catalog)  # current and next_action are not stored in a split Bolt
    cmd = args.command
    if cmd == "codekb-status":
        return {
            "ok": True,
            "root": str(planning_root(bolt)),
            "targets": codekb_status(planning_root(bolt), state["targets"]),
        }
    if cmd == "status":
        return cmd_status(bolt, state, catalog, args.format)
    if cmd == "next":
        return cmd_next(bolt, state, catalog, args)
    if cmd == "brief":
        return cmd_brief(bolt, state, catalog, args)
    if cmd == "context" and (args.id or args.note is None):
        return cmd_context(bolt, state, catalog, args)
    if cmd == "inputs":
        return cmd_inputs(bolt, state, catalog, args.stage, args.unit, args.slice)
    if cmd == "workspace":
        return cmd_workspace(bolt, state, args)

    require_open(state)
    if cmd == "target":
        return cmd_target(bolt, state, catalog, args)
    if cmd == "jira":
        return cmd_jira(bolt, state, catalog, args)
    if cmd == "assign":
        return cmd_assign(bolt, state, catalog, args)
    if cmd == "slice":
        return cmd_slice(bolt, state, catalog, args)
    if cmd == "contribution":
        return cmd_contribution(bolt, args)
    if cmd == "context":
        return cmd_context(bolt, state, catalog, args)
    if cmd in {"decide", "step", "gate"}:
        stage = stage_def(catalog, args.stage)
        key = scope_key(state, stage, args.unit, args.slice)
        if cmd == "gate":
            return cmd_gate(bolt, state, catalog, stage, key, args)
        require_story(state, stage, args.unit)
        suffix, warnings = stage_owner(bolt, state, stage, key)
        changed_since: dict[str, Any] = {}
        if cmd == "decide":
            cmd_decide(state, stage, key, args.decision, args.reason)
            event, note = "decide", f"{args.decision}: {args.reason}"
        else:
            cmd_step(state, stage, key, args.to)
            if args.to == "produced":  # tell what moved before the baseline takes it in
                changed_since = context_report(bolt, state, catalog, stage, key)
                changed_since.pop("baseline", None)
                get_record(state, stage, key)["relied_on"] = baseline(
                    bolt, state, catalog, stage, key
                )
            event, note = "step", f"to {args.to}"
        start_baseline(bolt, state, catalog, stage, key)  # work has started
        nxt = commit(bolt, state, catalog)
        prefix = f"[{key}] " if key else ""
        log_event(bolt, event, stage["id"], "", prefix + note + suffix, args.unit or "")
        done: dict[str, Any] = {
            "ok": True,
            "stage": stage["id"],
            **subject(stage, key),
            "next": nxt,
        }
        if changed_since:
            done["context"] = changed_since
            log_event(
                bolt,
                "context",
                stage["id"],
                "",
                f"{prefix}changed before produced: {report_text(changed_since)}",
                args.unit or "",
            )
        if warnings:
            done["warnings"] = warnings
        return done
    if cmd == "units":
        if args.cancel:
            return cmd_cancel(bolt, state, catalog, args)
        return cmd_units(bolt, state, catalog, Path(args.file))
    if cmd == "decision-id":
        if args.count < 1:
            die(EXIT_USAGE, "--count must be at least 1.")
        suffix, warnings = guard_owner(bolt, state, args.unit)
        holder = find_unit(state, args.unit) if args.unit else state
        start = int(holder.get("decision_seq") or 0)
        if not args.unit:  # never hand out an id the Bolt's decision records already hold
            start = max(start, highest_declared_decision(bolt))
        ids = [f"D{start + i}" for i in range(1, args.count + 1)]
        holder["decision_seq"] = start + args.count
        write_state(bolt, state)
        log_event(bolt, "decision-id", "", "", ",".join(ids) + suffix, args.unit or "")
        result: dict[str, Any] = {"ok": True, "ids": ids}
        if args.unit:
            result["cite_as"] = [f"{args.unit}:{i}" for i in ids]
        if warnings:
            result["warnings"] = warnings
        return result
    if cmd == "park":
        state["parked"] = {"note": args.note, "at": now()}
        write_state(bolt, state)
        log_event(bolt, "park", "", "", args.note)
        return {"ok": True, "parked": state["parked"]}
    if cmd == "unpark":
        state["parked"] = None
        write_state(bolt, state)
        log_event(bolt, "unpark")
        return {"ok": True, "parked": None}
    if cmd == "close":
        return cmd_close(bolt, state, catalog, args.status, args.successor)
    die(EXIT_USAGE, f"unknown command {cmd}")


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        result = run(args)
    except Fail as exc:
        LOG.error("%s", exc.message)
        for item in exc.findings:
            LOG.error(
                "  %s: %s %s",
                item["code"],
                item.get("path", item.get("stage", "")),
                item["message"],
            )
        payload = {"ok": False, "error": exc.message, "findings": exc.findings}
        payload.update(exc.extra)
        emit(payload)
        return exc.code
    if "text" in result:
        sys.stdout.write(result["text"])
    else:
        emit(result)
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        LOG.exception("internal error")
        sys.exit(EXIT_INTERNAL)
