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
from collections.abc import Iterator
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
  open        create a bolt           --root R --slug S --title T --intent I [--parent P]
                                         [--kind frame|delivery]
  status      show progress              --bolt P [--format text]
  overview    every Bolt at a glance     --root R [--format text] [--log N]
  next        the next stage and step    --bolt P
  inputs      files a stage reads        --bolt P --stage S [--unit U]
  decide      execute or skip a stage    --bolt P --stage S --decision D --reason R
  step        move a stage forward       --bolt P --stage S --to asked|analysed|produced
  gate        approve or send back       --bolt P --stage S --approve --by NAME [--channel C]
  units       load units and slices       --bolt P --set file.json
  assign      set a unit's owner         --bolt P --unit U --owner NAME
  brief       a unit's starting page     --bolt P --unit U [--write]
  decision-id reserve decision ids       --bolt P [--count n]
  codekb-status is the code knowledge fresh --bolt P
  workspace   workspace file, checkouts  --bolt P [--extra name=path]... [--fetch] [--out F]
  target      add or drop a target       --bolt P --add name=path | --remove NAME
  kind        frame or delivery bolt  --bolt P --set frame|delivery
  jira        record Jira keys           --bolt P --epic K | --unit U --story K | --unit U --done
                                         [--pr URL] | --off --reason R | --on
  park/unpark hand-over note             --bolt P --note N
  close       close the bolt          --bolt P --status complete|superseded|archived
  sync        commit and push your work  --bolt P [-m "what changed"] | --root R

Git: a command that changes a bolt first brings in the team's work, then commits the
bolt and pushes it. `aidlc.json` at the planning root may hold
{"git": {"branch": "..", "remote": "origin", "commit": true, "push": true}}.
AIDLC_GIT=off or --no-git turns git writes off; a folder outside git is skipped. A leftover
`*.tmp` file is never committed, and neither is a file that still holds git conflict markers
(exit 6, the files are named).

Lock: a command that changes a bolt (and `sync`) holds one lock per planning checkout for
its whole run, git steps included, so two sessions in one checkout queue instead of
colliding. It waits up to 60 s, then stops and names the lock file. The lock is freed by
the operating system if the session dies. Reads (status, next, overview) never wait.

examples:
  python3 aidlc_state.py open --root . --slug billing --title "Billing" --intent "Move billing"
  python3 aidlc_state.py next --bolt bolts/2026-01-05-billing
  python3 aidlc_state.py workspace --bolt bolts/2026-01-05-billing --fetch
  python3 aidlc_state.py gate --bolt bolts/2026-01-05-billing --stage requirements-analysis \\
      --approve --by "A. Approver"

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

FRAMEWORK = 3  # bumped when a change to state.json would break an older copy of the skills
LOCAL_FILE = ".aidlc-local.json"  # per machine, never committed; sits at the planning root
LOCK_NAME = ".aidlc.lock"
LOCK_WAIT = 60.0  # seconds a command waits for another session of the same checkout
LOCK_POLL = 0.2
LOCK_WAIT_ENV = "AIDLC_LOCK_WAIT"  # test only: seconds to wait instead of LOCK_WAIT
LOCK_STALE = 120  # fallback lock only: seconds after which a lock left by a crash is taken over
INDEX_KEYS = ("id", "name", "kind", "slice", "owner", "repo", "depends_on")
UNIT_MODES = ["split", "inline"]
DECISION_STATUS = (
    "constraint", "accepted", "proposed", "assumption", "open", "needs-evidence", "superseded"
)  # fmt: skip
UNSETTLED = ("open", "assumption", "needs-evidence")
DECISION_FILES = ("hla-decisions.md", "tdd-decisions.md")
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
KINDS = ["delivery", "frame"]
FRAME_STOP = "hla"  # a frame bolt ends at this gate
FRAME_REASON = "frame bolt: designs no component"
DEPTHS = ["minimal", "standard", "comprehensive"]
DEFAULT_DEPTH = {"classic": "standard", "express": "standard", "bugfix": "minimal"}
DEFAULT_UNIT_SCOPES = {"express", "bugfix"}
UNIT_KINDS = ["service", "spec", "ui", "packaging", "library"]
DEPENDENCY_ON = ["done", "contract"]
ROOT_PREFIX = "root:"
PARENT_PREFIX = "parent:"
FOCUSED_RESCAN_MAX = 0.30
CHANGED_FILES_CAP = 50
PHASES = ["discovery", "inception", "construction", "operation"]
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs", ".rb", ".cs",
    ".sql", ".scala", ".sh", ".php", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp",
}  # fmt: skip
SCAFFOLD_NAMES = {"__init__.py", "setup.py", "conftest.py"}
DIGEST_MAX_LINES = 10
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
            unit["stages"] = unit_stage_records(catalog, state["scope"], kind=bolt_kind(state))
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
    brownfield = any(t.get("kind") == "brownfield" for t in state.get("targets", []))
    after = frame_after(catalog, bolt_kind(state))
    for item in catalog:
        if item["per_unit"] or item["id"] in stages:
            continue
        if state.get("status") != "open":
            stages[item["id"]] = new_record("skip", "added after this bolt closed")
            continue
        decision, reason = initial_decision(item, state.get("scope", "classic"), brownfield, after)
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
    written = state.get("framework")
    state["framework"] = max(written if isinstance(written, int) else 0, FRAMEWORK)
    moved = normalise_portable(bolt, state)
    if is_split(state):
        write_split(bolt, state)
    else:
        write_json_atomic(state_path(bolt), state)
    if moved:
        log_event(bolt, "portable", "", "", "machine paths moved to .aidlc-local.json")


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
        "recorded_by": None,
        "channel": None,
    }


def bolt_kind(state: dict[str, Any]) -> str:
    return str(state.get("kind") or "delivery")


def frame_after(catalog: list[dict[str, Any]], kind: str) -> Optional[int]:
    """The order after which a frame bolt skips every stage; ``None`` for delivery."""
    if kind != "frame":
        return None
    return next(int(item["order"]) for item in catalog if item["id"] == FRAME_STOP)


def initial_decision(
    stage: dict[str, Any], scope: str, brownfield: bool, after: Optional[int] = None
) -> tuple[str, str]:
    """The decision ``open`` gives a stage; ``after`` is :func:`frame_after`."""
    if stage["id"] == "workspace-detection":
        return "execute", ""
    if after is not None and stage["order"] > after:
        return "skip", FRAME_REASON
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
    kind: str = "delivery",
) -> dict[str, Any]:
    records: dict[str, Any] = dict(existing or {})
    after = frame_after(catalog, kind)
    for item in catalog:
        if item["per_unit"] and item["id"] not in records:
            decision, reason = initial_decision(item, scope, True, after)
            records[item["id"]] = new_record(decision, reason)
    return records


def find_unit(state: dict[str, Any], unit: str) -> dict[str, Any]:
    for item in state["units"]:
        if item["id"] == unit:
            return item
    known = ", ".join(u["id"] for u in state["units"]) or "none loaded"
    die(EXIT_USAGE, f"unknown unit '{unit}' (units: {known}). Load them with `units --set`.")


def get_record(state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]) -> dict[str, Any]:
    if stage["per_unit"]:
        if unit is None:
            die(EXIT_USAGE, f"stage '{stage['id']}' runs once per unit; pass --unit.")
        records = find_unit(state, unit).setdefault("stages", {})
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
    """Every (stage, unit) in working order; per-unit stages run unit by unit."""
    result: list[Slot] = []
    expanded = False
    per_unit = [item for item in catalog if item["per_unit"]]
    for item in catalog:
        if not item["per_unit"]:
            result.append((item, None))
        elif not expanded:
            expanded = True
            if not state["units"] and bolt_kind(state) != "frame":
                result.append((per_unit[0], None))  # a frame bolt never loads units
            for unit in state["units"]:
                for sub in per_unit:
                    result.append((sub, unit["id"]))
    return result


def slot_record(
    state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]
) -> Optional[dict[str, Any]]:
    if stage["per_unit"]:
        if unit is None:
            return None
        return find_unit(state, unit).get("stages", {}).get(stage["id"])
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
    """What to do for one not-done slot."""
    base: dict[str, Any] = {
        "done": False,
        "stage": item["id"],
        "unit": unit,
        "skill": item["skill"],
        "reference": item["reference"],
        "tier": item.get("tier"),
    }
    if record is None:
        return {
            **base,
            "step": None,
            "action": "load-units",
            "blocked": ("units are not loaded; run `units --set` before per-unit stages"),
        }
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
        if is_split(state) and item["per_unit"] and unit is not None:
            rows = [
                next_for_unit(bolt, state, catalog, u["id"])
                for u in state["units"]
                if unit_slot(state, catalog, u["id"]) is not None
            ]
            return {"done": False, "stage": None, "unit": None, "action": "units", "units": rows}
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
        if on == "contract":
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


def next_for_unit(
    bolt: Optional[Path], state: dict[str, Any], catalog: list[dict[str, Any]], unit_id: str
) -> dict[str, Any]:
    """``next`` for one unit: its own first open stage, with what it waits for."""
    find_unit(state, unit_id)
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
    if waiting:
        result["blocked"] = waits_sentence(waiting)
    return with_context(bolt, state, catalog, result)


def cmd_next(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    if args.unit:
        return {"ok": True, **next_for_unit(bolt, state, catalog, args.unit)}
    if args.mine:
        who = actor(planning_root(bolt))
        if not who:
            raise Fail(EXIT_FINDINGS, "the git user name is not set; run `git config user.name`.")
        mine = [u["id"] for u in state["units"] if same_person(u.get("owner") or "", who)]
        rows = [next_for_unit(bolt, state, catalog, uid) for uid in mine]
        return {"ok": True, "actor": who, "units": rows}
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
    parent = (state.get("parent") or {}).get("id") or "-"
    facts = [
        ("Bolt", f"{state['id']}: {state['title']}"), ("Parent Bolt", parent),
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
        f"- {sub['id']}: {', '.join(paths)}"
        for sub in catalog
        if sub["per_unit"] and (paths := context_changed(bolt, state, catalog, sub, uid))
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


def guard_owner(bolt: Path, state: dict[str, Any], unit_id: Optional[str], takeover: Any) -> str:
    """Refuse to change a unit someone else owns; return the log suffix for a takeover."""
    if unit_id is None:
        return ""
    owner = find_unit(state, unit_id).get("owner")
    who = actor(planning_root(bolt))
    if not owner or not who or same_person(owner, who):
        return ""
    why = " ".join(str(takeover or "").split())
    if not why:
        raise Fail(
            EXIT_FINDINGS,
            f"unit {unit_id} belongs to {owner} and you are {who}. "
            'Ask them, or pass --takeover "<why>"',
        )
    return f" takeover by {who}: {why}"


def cmd_assign(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    owner = " ".join((args.owner or "").split())
    if not owner:
        die(EXIT_USAGE, "--owner must not be blank.")
    unit = find_unit(state, args.unit)
    old = unit.get("owner") or "-"
    unit["owner"] = owner
    nxt = commit(bolt, state, catalog)
    log_event(bolt, "assign", "", "", f"[{args.unit}] {old} -> {owner}", args.unit)
    previous = None if old == "-" else old
    return {"ok": True, "unit": args.unit, "owner": owner, "previous": previous, "next": nxt}


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
        return "units in progress: " + ", ".join(parts)
    where = nxt["stage"] + (f" [{nxt['unit']}]" if nxt["unit"] else "")
    if nxt["action"] == "load-units":
        return f"load units before {where}"
    return f"{nxt['action']}: {where} (skill {nxt['skill']})"


def refresh(state: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    nxt = compute_next(state, catalog)
    state["current"] = {"stage": nxt["stage"], "unit": nxt["unit"]}
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


def resolve_parent(root: Path, spec: str) -> dict[str, str]:
    """``{"id", "path"}`` of an existing bolt under ``root``; ``path`` is relative to it."""
    given = Path(spec).expanduser()
    candidates = [given] if given.is_absolute() else [given, root / "bolts" / spec]
    found = next((c.resolve() for c in candidates if state_path(c).is_file()), None)
    if found is None:
        die(EXIT_INPUT, f"--parent '{spec}': no bolt with a state.json at {candidates[-1]}.")
    if found.parent.name != "bolts" or found.parent.parent != root.resolve():
        die(EXIT_USAGE, f"--parent '{spec}': {found} is not a bolt under {root.resolve()}.")
    parent_state = load_state(found)
    return {"id": str(parent_state["id"]), "path": found.relative_to(root.resolve()).as_posix()}


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
    parent = resolve_parent(root, args.parent) if args.parent else None
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
    after = frame_after(catalog, args.kind)
    stages: dict[str, Any] = {}
    for item in catalog:
        if item["per_unit"]:
            continue
        decision, reason = initial_decision(item, args.scope, brownfield, after)
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
                "stages": unit_stage_records(catalog, args.scope, kind=args.kind),
                "story": None,
                "story_done": None,
            }
        ]
        slices = [{"id": "s1", "units": ["u1"], "status": "todo"}]

    state: dict[str, Any] = {
        "schema": 1,
        "id": bolt_id,
        "title": args.title,
        "intent": args.intent,
        "status": "open",
        "scope": args.scope,
        "kind": args.kind,
        "depth": args.depth or DEFAULT_DEPTH[args.scope],
        "owner": args.owner or "",
        "approver": args.approver or "",
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
    if parent is not None:
        state["parent"] = parent
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
        "docs/operation",
    ]
    for folder in folders:
        (bolt / folder).mkdir(parents=True, exist_ok=True)
        (bolt / folder / ".gitkeep").touch()
    (bolt / "log.md").touch()
    nxt = commit(bolt, state, catalog)
    log_event(bolt, "open", "", "", f"scope={args.scope} depth={state['depth']} kind={args.kind}")
    if parent is not None:
        log_event(bolt, "parent", "", "", f"{parent['id']} at {parent['path']}")
    for rule in rules:
        log_event(bolt, "classify", "workspace-detection", "", rule)
    return {
        "ok": True,
        "bolt": str(bolt),
        "id": bolt_id,
        "targets": targets,
        "architecture_ref": architecture,
        "parent": parent,
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
    parent = state.get("parent")
    if parent:
        name = f"parent: {DATE_PREFIX.sub('', parent['id'])}"
        folders.append({"name": name, "path": str(root / parent["path"])})
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
        "kind": bolt_kind(state),
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
    details = [unit_detail(bolt, state, catalog, u["id"]) for u in state["units"]]
    stale = stale_rows(bolt, state, catalog)
    facts["unit_details"] = details
    facts["stale"] = stale
    parent = state.get("parent")
    if parent:
        facts["parent"] = parent
        facts["parent_hla_status"] = parent_hla_status(bolt, state)
    git_block = git_status_block(bolt)
    if git_block is not None:
        facts["git"] = git_block
    if fmt == "json":
        return facts
    lines = [
        f"{state['title'] or state['id']} ({state['id']})",
        f"Status: {state['status']} | Scope: {state['scope']} | Depth: {state['depth']}"
        f" | Kind: {bolt_kind(state)}",
        f"Intent: {state['intent'][:160]}",
    ]
    if parent:
        lines.append(f"Parent: {parent['id']} (HLA {facts['parent_hla_status']})")
    for phase in PHASES:
        entry = progress[phase]
        note = f", {entry['skipped']} skipped" if entry["skipped"] else ""
        lines.append(f"{phase.capitalize()}: {entry['done']}/{entry['total']} done{note}")
    lines.append(f"Units: {len(state['units'])} | Slices: {len(state['slices'])}")
    for row in details:
        step = f"{row['stage']} {row['action']}" if row["stage"] else "done"
        waits = f" | {waits_sentence(row['blocked_by'])}" if row["blocked_by"] else ""
        lines.append(f"  {row['id']} | {row['owner'] or '-'} | {step}{waits}")
    for row in stale:
        where = row["stage"] + (f" [{row['unit']}]" if row["unit"] else "")
        lines.append(f"Context changed for {where}: {', '.join(row['changed'])}")
    lines.append(jira_line(state))
    if git_block is not None:
        lines.append(git_status_line(git_block))
    if nxt["done"]:
        lines.append("Current: none")
    elif nxt["action"] == "units":
        lines.append("Current: per-unit stages (see the units above)")
    else:
        where = nxt["stage"] + (f" [{nxt['unit']}]" if nxt["unit"] else "")
        lines.append(f"Current: {where}, step {nxt['step']}")
    lines.append(f"Next: {state['next_action']}")
    if state["parked"]:
        note = str(state["parked"].get("note", "")).replace("\n", " ")
        lines.append(f"Parked: {note[:300]}")
    return {"text": "\n".join(lines[: 20 + len(details) + len(stale)]) + "\n"}


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
    parent = (state.get("parent") or {}).get("id")
    if parent and parent_hla_status(bolt, state) != "accepted":
        problems.append(
            {
                "code": "parent-not-accepted",
                "where": parent,
                "message": "the parent's HLA is not accepted",
            }
        )
    stale = stale_rows(bolt, state, catalog)
    for row in stale:
        where = row["stage"] + (f" [{row['unit']}]" if row["unit"] else "")
        problems.append(
            {"code": "stale-context", "where": where, "message": ", ".join(row["changed"])}
        )
    for unit in state["units"]:
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
        "kind": bolt_kind(state),
        "status": state["status"],
        "scope": state.get("scope"),
        "owner": state.get("owner") or None,
        "parent": parent,
        "next": describe_next(compute_next(state, catalog, bolt)),
        "children": [],
        "units": units,
        "stale": stale,
        "last": last,
        "problems": problems,
    }


def overview_text(rows: list[dict[str, Any]]) -> str:
    by_id = {r["id"]: r for r in rows}
    lines: list[str] = []

    def show(row: dict[str, Any], depth: int) -> None:
        pad = "  " * depth
        if "error" in row:
            lines.append(f"{pad}{row['id']}: unreadable: {row['error']}")
            return
        owner = f", owner {row['owner']}" if row["owner"] else ""
        lines.append(f"{pad}{row['id']} [{row['status']}] {row['title']}{owner}")
        lines.append(f"{pad}  next: {row['next']}")
        for unit in row["units"]:
            waits = f" | {waits_sentence(unit['blocked_by'])}" if unit["blocked_by"] else ""
            lines.append(
                f"{pad}  unit {unit['id']} | {unit['owner'] or '-'} | {unit['next']}{waits}"
            )
        for problem in row["problems"]:
            lines.append(f"{pad}  ! {problem['code']} {problem['where']}: {problem['message']}")
        for child in row["children"]:
            show(by_id[child], depth + 1)

    for row in rows:
        if not row.get("parent") or row["parent"] not in by_id:
            show(row, 0)
    return "\n".join(lines) + "\n"


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
    known = {r["id"]: r for r in rows}
    for row in rows:
        parent = known.get(row.get("parent") or "")
        if parent is not None and "children" in parent:
            parent["children"].append(row["id"])
    result: dict[str, Any] = {"ok": True, "root": str(root.resolve()), "bolts": rows}
    if args.log:
        result["log"] = sorted(logs, key=lambda r: r["time"])[-args.log :]
    if args.format == "text":
        text = overview_text(rows)
        for entry in result.get("log", []):
            unit = f" [{entry['unit']}]" if entry["unit"] else ""
            text += f"{entry['time']} {entry['bolt']}{unit} {entry['event']} {entry['stage']}\n"
        return {"text": text}
    return result


def planning_root(bolt: Path) -> Path:
    """The planning repository root: bolts live in ``<root>/bolts/<id>``."""
    return bolt.resolve().parent.parent


def parent_dir(bolt: Path, state: dict[str, Any]) -> Optional[Path]:
    parent = state.get("parent")
    return planning_root(bolt) / parent["path"] if parent else None


def parent_hla_status(bolt: Path, state: dict[str, Any]) -> str:
    """The ``status:`` of the parent's ``hla.md`` header, or ``missing`` without a file."""
    folder = parent_dir(bolt, state)
    hla = folder / "architecture" / "hla.md" if folder else None
    if hla is None or not hla.is_file():
        return "missing"
    header = header_fields(hla.read_text(encoding="utf-8", errors="replace"))
    return (header or {}).get("status") or "unknown"


def locate(bolt: Path, rel: str, state: Optional[dict[str, Any]] = None) -> Path:
    """Resolve a stages.json path: ``root:`` hangs off the planning root, ``parent:``
    off the parent bolt; anything else off this bolt."""
    if rel.startswith(ROOT_PREFIX):
        return planning_root(bolt) / rel[len(ROOT_PREFIX) :]
    folder = parent_dir(bolt, state) if state else None
    if rel.startswith(PARENT_PREFIX) and folder is not None:
        return folder / rel[len(PARENT_PREFIX) :]
    return bolt / rel


def glob_paths(bolt: Path, rel: str) -> list[Path]:
    if rel.startswith(ROOT_PREFIX):
        return sorted(planning_root(bolt).glob(rel[len(ROOT_PREFIX) :]))
    return sorted(bolt.glob(rel))


def brownfield_repos(state: dict[str, Any]) -> list[str]:
    return [t["repo"] for t in state["targets"] if t["kind"] == "brownfield"]


def unit_ids(state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]) -> list[str]:
    """The units a stage's ``<unit>`` paths cover: its own unit, or every unit."""
    if stage["per_unit"]:
        return [unit] if unit else []
    return [u["id"] for u in state["units"]]


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
    folder = parent_dir(bolt, state)
    parent_state: Optional[dict[str, Any]] = None
    if folder is not None and state_path(folder).is_file():
        parent_state = load_state(folder)
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    slug = DATE_PREFIX.sub("", str(state["id"]))
    for entry in stage["inputs"]:
        template = entry["path"].replace("<bolt>", slug)
        from_parent = template.startswith(PARENT_PREFIX)
        if from_parent and folder is None:
            continue  # parent inputs exist only for a child bolt
        own = template[len(PARENT_PREFIX) :] if from_parent else template
        producer = producer_of(catalog, own)
        optional = bool(entry.get("optional"))
        for rel, row_unit in expand_pairs(template, repos, units, targets):
            skipped = False
            source = parent_state if from_parent else state
            if producer is not None and source is not None:
                producer_unit = row_unit if producer["per_unit"] else None
                rec = slot_record(source, producer, producer_unit)
                skipped = bool(rec and rec["decision"] == "skip")
            file = locate(bolt, rel, state)
            exists = file.is_file()
            if entry.get("if_exists") and not exists:
                continue
            produced_by = producer["id"] if producer else None
            if from_parent and produced_by:
                produced_by = PARENT_PREFIX + produced_by
            row = {
                "path": rel,
                "file": str(file.resolve()),
                "mode": entry["mode"],
                "exists": exists,
                "produced_by": produced_by,
                "skipped": skipped and not exists,
                "optional": optional,
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
) -> dict[str, Any]:
    stage = stage_def(catalog, stage_id)
    get_record(state, stage, unit)
    rows, missing = input_rows(bolt, state, catalog, stage, unit)
    folder = parent_dir(bolt, state)
    payload: dict[str, Any] = {
        "ok": not missing,
        "stage": stage_id,
        "unit": unit,
        "root": str(planning_root(bolt)),
        "inputs": rows,
        "missing": missing,
    }
    if folder is not None:
        status = parent_hla_status(bolt, state)
        payload.update({"parent": state["parent"], "parent_hla_status": status, "warnings": []})
        if status != "accepted":
            message = f"the parent's hla.md is {status}, not accepted; its decisions may change"
            payload["warnings"].append({"code": "parent-hla-not-accepted", "message": message})
            LOG.warning("%s", message)
    if missing:
        names = ", ".join(f"{m['path']} (stage {m['produced_by'] or 'unknown'})" for m in missing)
        raise Fail(
            EXIT_INPUT, f"stage '{stage_id}' is missing required input: {names}", extra=payload
        )
    return payload


# --- context a stage relied on ------------------------------------------------


def fingerprint(row: dict[str, Any]) -> str:
    """16 hex characters of a sha256: the file, or only its ``## Digest`` in digest mode."""
    raw = Path(row["file"]).read_bytes()
    if row["mode"] == "digest":
        found = digest_section(raw.decode("utf-8", errors="replace"))
        if found is not None:
            raw = "\n".join(found).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def relied_on(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    unit: Optional[str],
) -> dict[str, str]:
    rows, _ = input_rows(bolt, state, catalog, stage, unit)
    return {row["path"]: fingerprint(row) for row in rows if row["exists"]}


def context_changed(
    bolt: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    unit: Optional[str],
) -> list[str]:
    """Inputs that differ from, or vanished since, the record's ``relied_on``."""
    record = slot_record(state, stage, unit)
    stored = (record or {}).get("relied_on")
    if not stored:
        return []
    now_hashes = relied_on(bolt, state, catalog, stage, unit)
    return [path for path, digest in stored.items() if now_hashes.get(path) != digest]


def with_context(
    bolt: Optional[Path],
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Add ``context_changed`` to a ``next`` result for its slot, when not empty."""
    if result.get("stage") and bolt is not None:
        stage = stage_def(catalog, result["stage"])
        changed = context_changed(bolt, state, catalog, stage, result.get("unit"))
        if changed:
            result["context_changed"] = changed
    return result


def stale_rows(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item, unit in slots(state, catalog):
        changed = context_changed(bolt, state, catalog, item, unit)
        if changed:
            rows.append({"stage": item["id"], "unit": unit, "changed": changed})
    return rows


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
    for template in as_list(stage.get("signoff")):
        for rel in expand(template, repos, units):
            path = locate(bolt, rel)
            if not path.is_file():
                continue
            header = header_fields(path.read_text(encoding="utf-8", errors="replace"))
            if header is None:
                findings.append(
                    {"code": "signoff-no-header", "path": rel, "message": "no ```yaml header"}
                )
                continue
            status = header.get("status", "")
            if status != "accepted":
                findings.append(
                    {
                        "code": "signoff-not-accepted",
                        "path": rel,
                        "message": f"header status is '{status or 'missing'}'; "
                        "a person must set it to accepted",
                    }
                )
            unsigned = [key for key in ("signed_off_by", "signed_off_on") if not header.get(key)]
            if unsigned:
                findings.append(
                    {
                        "code": "signoff-unsigned",
                        "path": rel,
                        "message": "empty in the header: " + ", ".join(unsigned),
                    }
                )
    if stage["id"] == "reverse-engineering":
        findings.extend(meta_findings(bolt, state))
    return findings


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


def decision_status_findings(
    bolt: Path, state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]
) -> list[dict[str, Any]]:
    """A decision table may carry a ``Status`` column; its words come from one list."""
    found: list[dict[str, Any]] = []
    for template in stage["artifacts"]:
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
    who = actor(planning_root(bolt))
    channel = (getattr(args, "channel", None) or "").strip() or None
    if (args.by or "").strip() and who and channel is None and not same_person(args.by, who):
        raise Fail(
            EXIT_FINDINGS,
            f"{who} is running this, but the decision is {args.by.strip()}'s: an approval "
            "given by someone else must be recorded with --channel (for example "
            "'email 2026-11-24').",
        )
    via = (f" recorded by {who} via {channel}" if who else f" via {channel}") if channel else ""
    if args.request_changes:
        if not (args.note or "").strip():
            die(EXIT_USAGE, "--request-changes needs --note.")
        if record["step"] == "approved":
            raise Fail(EXIT_FINDINGS, f"stage '{label}' is already approved.")
        record["step"] = "changes-requested"
        record["approved_at"] = None
        record["approved_by"] = None
        record["recorded_by"] = None
        record["channel"] = None
        nxt = commit(bolt, state, catalog)
        log_event(bolt, "gate-request-changes", label, args.by or "", args.note + via, unit or "")
        return {"ok": True, "stage": label, "unit": unit, "step": record["step"], "next": nxt}
    if not (args.by or "").strip():
        die(EXIT_USAGE, "--approve needs --by NAME.")
    findings = gate_findings(bolt, state, stage, unit, record)
    findings.extend(traceability_findings(bolt, state, catalog, stage))
    findings.extend(decision_status_findings(bolt, state, stage, unit))
    ack = (getattr(args, "ack_context", None) or "").strip()
    if not ack:
        for path in context_changed(bolt, state, catalog, stage, unit):
            findings.append(
                {
                    "code": "context-changed",
                    "path": path,
                    "message": "changed after this stage was produced; re-check the artifact, "
                    'then approve with --ack-context "<what you checked>"',
                }
            )
    if findings:
        raise Fail(
            EXIT_FINDINGS,
            f"gate refused for '{label}': {len(findings)} finding(s).",
            findings=findings,
        )
    record["step"] = "approved"
    record["approved_at"] = now()
    record["approved_by"] = args.by.strip()
    record["recorded_by"] = who or None
    record["channel"] = channel
    record["relied_on"] = relied_on(bolt, state, catalog, stage, unit)
    if stage["id"] == "reverse-engineering":
        record_codekb_commits(bolt, state)
    if not state.get("approver"):
        state["approver"] = args.by.strip()
    nxt = commit(bolt, state, catalog)
    log_event(
        bolt,
        "gate-approve",
        label,
        args.by,
        (unit or "") + via + (f" context acknowledged: {ack}" if ack else ""),
        unit or "",
    )
    suggestion = (
        "A fresh session for the next stage is cheapest but optional. "
        f"Next: {state['next_action']}."
    )
    return {
        "ok": True,
        "stage": label,
        "unit": unit,
        "step": "approved",
        "next": nxt,
        "suggestion": suggestion,
    }


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


def cmd_units(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], file: Path
) -> dict[str, Any]:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(EXIT_INPUT, f"{file}: units file not found.")
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{file}: invalid JSON at line {exc.lineno}: {exc.msg}")
    if not isinstance(data, dict) or not ("units" in data or "slices" in data):
        die(EXIT_MALFORMED, f'{file}: expected an object with "units" and/or "slices".')

    old = {u["id"]: u for u in state["units"]}
    units = data.get("units", state["units"])
    slices = data.get("slices", state["slices"])
    if not isinstance(units, list) or not isinstance(slices, list):
        die(EXIT_MALFORMED, f'{file}: "units" and "slices" must be lists.')
    seen: set[str] = set()
    for unit in units:
        uid = unit.get("id") if isinstance(unit, dict) else None
        if not isinstance(uid, str) or not ID_PATTERN.match(uid) or uid in seen:
            die(EXIT_MALFORMED, f"{file}: each unit needs a unique lower-case id; saw {uid!r}.")
        seen.add(uid)
        for key in ("owner", "repo"):
            if unit.get(key) is not None and not isinstance(unit[key], str):
                die(EXIT_MALFORMED, f"{file}: unit {uid} {key} must be a string.")
        kind = unit.get("kind")
        if kind is not None and kind not in UNIT_KINDS:
            die(
                EXIT_MALFORMED,
                f"{file}: unit {uid} has kind {kind!r}; use one of {', '.join(UNIT_KINDS)}.",
            )
    seen_slices: set[str] = set()
    for entry in slices:
        sid = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(sid, str) or sid in seen_slices:
            die(EXIT_MALFORMED, f"{file}: each slice needs a unique id; saw {sid!r}.")
        seen_slices.add(sid)
        for member in entry.get("units", []):
            if member not in seen:
                die(EXIT_MALFORMED, f"{file}: slice {sid} names unknown unit {member!r}.")
        entry.setdefault("status", "todo")
    owner_of = {m: b["id"] for b in slices for m in b.get("units", [])}
    known_repos = [t["repo"] for t in state["targets"]]
    deps: dict[str, list[dict[str, str]]] = {}
    for unit in units:
        previous = old.get(unit["id"], {})
        repo = unit.get("repo", previous.get("repo"))
        if repo and known_repos and repo not in known_repos:
            die(
                EXIT_MALFORMED,
                f"{file}: unit {unit['id']} has repo {repo!r}; "
                f"this bolt's repositories are {', '.join(known_repos)}.",
            )
        deps[unit["id"]] = normalise_deps(
            file, unit["id"], unit.get("depends_on", previous.get("depends_on")), seen
        )
    check_cycles(file, deps)
    result: list[dict[str, Any]] = []
    for unit in units:
        previous = old.get(unit["id"], {})
        result.append(
            {
                "id": unit["id"],
                "name": unit.get("name", ""),
                "kind": unit.get("kind", previous.get("kind")),
                "owner": unit.get("owner", previous.get("owner")),
                "repo": unit.get("repo", previous.get("repo")),
                "depends_on": deps[unit["id"]],
                "slice": owner_of.get(unit["id"], unit.get("slice")),
                "stages": unit_stage_records(
                    catalog, state["scope"], previous.get("stages"), bolt_kind(state)
                ),
                "story": previous.get("story"),
                "story_done": previous.get("story_done"),
            }
        )
    state["units"] = result
    state["slices"] = slices
    nxt = commit(bolt, state, catalog)
    log_event(bolt, "units", "", "", f"{len(result)} unit(s), {len(slices)} slice(s)")
    return {
        "ok": True,
        "units": [u["id"] for u in result],
        "slices": [b["id"] for b in slices],
        "missing_kind": [u["id"] for u in result if not u["kind"]],
        "missing_owner": [u["id"] for u in result if not u["owner"]],
        "missing_repo": [u["id"] for u in result if not u["repo"]],
        "next": nxt,
    }


def cmd_kind(
    bolt: Path, state: dict[str, Any], catalog: list[dict[str, Any]], kind: str
) -> dict[str, Any]:
    """Re-decide every stage after the HLA as ``open`` would for ``kind``.

    Refused once any of those stages has left ``todo``: work already done there
    would be skipped, or skipped work would silently come back.
    """
    stop = frame_after(catalog, "frame")
    late = [item for item in catalog if stop is not None and item["order"] > stop]
    records: list[tuple[dict[str, Any], Optional[str], dict[str, Any]]] = []
    for item in late:
        if item["per_unit"]:
            for unit in state["units"]:
                rec = unit.setdefault("stages", {}).get(item["id"])
                records.append((item, unit["id"], rec or new_record("pending", "")))
        elif item["id"] in state["stages"]:
            records.append((item, None, state["stages"][item["id"]]))
    started = [
        {
            "code": "stage-started",
            "stage": item["id"],
            "unit": unit,
            "message": f"step is {rec['step']}",
        }
        for item, unit, rec in records
        if rec["step"] != "todo"
    ]
    if started:
        raise Fail(
            EXIT_FINDINGS,
            f"cannot make this a {kind} bolt: {len(started)} stage(s) after "
            f"{FRAME_STOP} have started.",
            findings=started,
        )
    previous = bolt_kind(state)
    brownfield = any(t["kind"] == "brownfield" for t in state["targets"])
    after = frame_after(catalog, kind)
    for item, unit, _ in records:
        decision, reason = initial_decision(item, state["scope"], brownfield, after)
        record = new_record(decision, reason)
        if unit is None:
            state["stages"][item["id"]] = record
        else:
            find_unit(state, unit)["stages"][item["id"]] = record
    state["kind"] = kind
    nxt = commit(bolt, state, catalog)
    log_event(bolt, "kind", "", "", f"{previous} -> {kind}")
    return {
        "ok": True,
        "kind": kind,
        "previous": previous,
        "redecided": sorted({item["id"] for item, _, _ in records}),
        "next": nxt,
    }


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
    suffix = guard_owner(bolt, state, args.unit, getattr(args, "takeover", None))
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
    return {"ok": True, "jira": jira_facts(state), "next": nxt}


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
                findings.append(
                    {"code": "units-not-loaded", "message": "per-unit stages have no units"}
                )
            elif record["decision"] == "pending":
                findings.append(
                    {
                        "code": "decision-pending",
                        "stage": item["id"],
                        "unit": unit,
                        "message": "no decision recorded",
                    }
                )
            elif record["decision"] == "execute" and record["step"] != "approved":
                findings.append(
                    {
                        "code": "stage-not-approved",
                        "stage": item["id"],
                        "unit": unit,
                        "message": f"step is {record['step']}",
                    }
                )
        open_stories = [
            u["id"] for u in state["units"] if u.get("story") and not u.get("story_done")
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
    if rel.endswith(".tmp"):
        return False  # a temp file left by a killed write is never committed
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


def head_step(ctx: GitCtx, bolt_rel: str, stage: str, unit: Optional[str]) -> Optional[str]:
    """The step a stage had in the last commit, or ``None`` when HEAD does not say."""
    base = f"{ctx.prefix}{bolt_rel}"
    names = [f"{base}/state.json"] + ([f"{base}/units/{unit}/state.json"] if unit else [])
    for name in reversed(names):
        shown = run_git(ctx.top, "show", f"HEAD:{name}")
        if shown.returncode != 0:
            continue
        try:
            data = json.loads(shown.stdout)
        except json.JSONDecodeError:
            return None
        if unit and "stages" not in data:  # a unit kept inline in the Bolt's file
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
    watched: dict[str, tuple[str, Optional[str]]] = {}
    for item, unit in slots(state, catalog):
        record = slot_record(state, item, unit)
        if record and record.get("step") == "approved":
            for template in item["artifacts"]:
                for rel in expand(template, brownfield_repos(state), unit_ids(state, item, unit)):
                    watched.setdefault(rel, (item["id"], unit))
    logged = False
    for path in changed:
        found = watched.get(path[len(head) :]) if path.startswith(head) else None
        if found is None or head_step(ctx, bolt_rel, found[0], found[1]) != "approved":
            continue
        rel = path[len(head) :]
        text = f"approved artifact changed: {rel} (stage {found[0]} is approved; "
        result["warnings"].append(text + "reopen it with gate --request-changes)")
        log_event(bolt, "approved-change", found[0], "", rel, found[1] or "")
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
            "take the team's version (`git checkout --ours -- <file>`, then `git add <file>`), "
            "finish the rebase with `git rebase --continue`, then run your command again."
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
        f"{why} {len(files)} file(s) conflict. This is not a question for the user: resolve "
        "each one by its rule, `git add` it, run `git rebase --continue`, then run `sync` "
        f"again. {SIDES}",
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


def count_commits(ctx: GitCtx, spec: str) -> Optional[int]:
    done = run_git(ctx.top, "rev-list", "--count", spec)
    return int(done.stdout.strip()) if done.returncode == 0 else None


def push_branch(ctx: GitCtx, branch: Optional[str], result: dict[str, Any]) -> None:
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
    failed = "push: failed, retried at the next event"
    try:
        for _round in range(PUSH_ROUNDS):
            fetch = run_git(
                ctx.top, "fetch", ctx.remote, branch, timeout=FETCH_TIMEOUT, env=FETCH_ENV
            )
            remote_has = fetch.returncode == 0
            if not remote_has and "find remote ref" not in fetch.stderr:
                warnings.append(failed)
                return
            if remote_has:
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
                warnings.append(failed)
                return
        warnings.append(failed)
    except SoftGitError:
        warnings.append(failed)


def sync_git(ctx: GitCtx, bolt_rel: Optional[str], slug: str, event: str) -> dict[str, Any]:
    """Bring in the team's work, commit this bolt's changes and push them."""
    result: dict[str, Any] = {
        "enabled": True,
        "branch": None,
        "commit": None,
        "pushed": False,
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
        push_branch(ctx, ctx.branch or current, result)
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
        return "load the units"
    if cmd == "assign":
        return f"assign unit {args.unit} to {args.owner}"
    if cmd == "brief":
        return f"write the brief of unit {args.unit}"
    if cmd == "kind":
        return f"make the bolt a {args.set} bolt"
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
    return args.command in {
        "open", "decide", "step", "gate", "units", "decision-id", "kind", "park", "unpark",
        "jira", "target", "close", "assign",
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
    target = ctx.branch or branch
    if target:
        ref = f"refs/remotes/{ctx.remote}/{target}"
        if run_git(ctx.top, "rev-parse", "--verify", "-q", ref).returncode == 0:
            block["ahead"] = count_commits(ctx, f"{ref}..HEAD")
            block["behind"] = count_commits(ctx, f"HEAD..{ref}")
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
    sp.add_argument(
        "--kind",
        choices=KINDS,
        default="delivery",
        help="frame: programme-level design that ends at the HLA gate; phases are child bolts.",
    )
    sp.add_argument("--depth", choices=DEPTHS, help="Default: standard, or minimal for bugfix.")
    sp.add_argument(
        "--target", action="append", metavar="name=path", help="Target repository; repeatable."
    )
    sp.add_argument("--architecture-ref", help="ADR registry checkout; its commit is recorded.")
    sp.add_argument("--owner", help="Bolt owner (optional).")
    sp.add_argument("--approver", help="Default approver (optional).")
    sp.add_argument("--date", help="Override the date part of the id, YYYY-MM-DD.")
    sp.add_argument(
        "--units",
        choices=UNIT_MODES,
        help="split: one state file and log per unit, so engineers do not collide "
        '(default: "units" in aidlc.json, else inline).',
    )
    sp.add_argument(
        "--parent", help="Parent bolt id or path under the same root; its HLA frames this one."
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
    group.add_argument("--mine", action="store_true", help="Every unit you own, as --unit does.")

    sp = add("inputs", "List the files a stage reads.")
    sp.add_argument("--stage", required=True)
    sp.add_argument("--unit")

    def takeover(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--takeover", help="Why you change a unit that someone else owns (it is logged)."
        )

    sp = add("decide", "Record EXECUTE or SKIP for a stage.")
    takeover(sp)
    sp.add_argument("--stage", required=True)
    sp.add_argument("--decision", required=True, choices=["execute", "skip"])
    sp.add_argument("--reason", required=True)
    sp.add_argument("--unit")

    sp = add("step", "Move a stage forward.")
    takeover(sp)
    sp.add_argument("--stage", required=True)
    sp.add_argument("--to", required=True, choices=["asked", "analysed", "produced"])
    sp.add_argument("--unit")

    sp = add("gate", "Approve a stage or send it back.")
    sp.add_argument("--stage", required=True)
    sp.add_argument("--unit")
    group = sp.add_mutually_exclusive_group(required=True)
    group.add_argument("--approve", action="store_true")
    group.add_argument("--request-changes", action="store_true")
    sp.add_argument("--by", help="Approver name (required with --approve).")
    sp.add_argument("--note", help="What to change (required with --request-changes).")
    sp.add_argument("--ack-context", help="What you re-checked after an input changed.")
    sp.add_argument(
        "--channel",
        help="How someone else gave the decision, e.g. 'email 2026-11-24'; "
        "required when --by is not the person running the script.",
    )

    sp = add("assign", "Set the owner of a unit.")
    sp.add_argument("--unit", required=True)
    sp.add_argument("--owner", required=True, help="A person's name, as in their git user.name.")

    sp = add("brief", "A unit's starting page, from state only; --write saves it in the bolt.")
    sp.add_argument("--unit", required=True)
    sp.add_argument("--write", action="store_true", help="Write docs/construction/<unit>/brief.md.")

    sp = add("units", "Load units and slices from a JSON file.")
    sp.add_argument(
        "--set",
        required=True,
        dest="file",
        help='JSON with "units" (id, name, kind) and/or "slices"; kind: ' + "|".join(UNIT_KINDS),
    )

    sp = add("decision-id", "Reserve the next decision ids.")
    takeover(sp)
    sp.add_argument("--count", type=int, default=1)
    sp.add_argument("--unit", help="Number from this unit's own counter; cite as <unit>:D<n>.")
    sp.add_argument(
        "--provisional",
        action="store_true",
        help="Reserve even when the shared counter cannot be confirmed (the ids may clash).",
    )

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

    sp = add("kind", "Make the bolt a frame or a delivery bolt before later stages start.")
    sp.add_argument("--set", required=True, choices=KINDS)

    sp = add("park", "Leave a hand-over note.")
    sp.add_argument("--note", required=True)
    add("unpark", "Clear the hand-over note.")

    sp = add("jira", "Record Jira keys: one epic per bolt, one story per unit.")
    takeover(sp)
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
    shared_counter = args.command == "decision-id" and not args.unit
    provisional = False
    if shared_counter and any(w.startswith("push: failed") for w in before["warnings"]):
        if not args.provisional:
            raise Fail(
                EXIT_GIT,
                "cannot confirm the shared decision counter; fix the connection or pass "
                "--provisional",
                extra={"git": before},
            )
        provisional = True
    result = run_locked(args)
    if provisional:
        result["provisional"] = True
    if args.command == "open":
        _root, rel, slug = git_scope(Path(result["bolt"]))
    not_reserved = "the ids were not reserved: resolve the conflict, then run decision-id again"
    try:
        after = sync_git(ctx, rel, slug, git_event(args, result))
    except Fail as exc:
        if shared_counter:
            result = {k: v for k, v in result.items() if k != "ids"}
            exc.message = f"{not_reserved}. {exc.message}"
        exc.extra.setdefault("result", result)
        raise
    if (
        shared_counter
        and not provisional
        and any(w.startswith("push: failed") for w in after["warnings"])
    ):
        raise Fail(
            EXIT_GIT,
            not_reserved,
            extra={"git": after, "result": {k: v for k, v in result.items() if k != "ids"}},
        )
    result["git"] = after
    if before["commit"] or before["rebuild_adr_index"] or before["warnings"]:
        result["git_before"] = before
    return result


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
        f"{path}). Let it finish, then run the command again.",
    )


def lock_location(args: argparse.Namespace) -> Optional[Path]:
    """The checkout-wide lock file of a command, or ``None`` when there is nothing to lock.

    Inside the git directory of the planning checkout, so it is never a work-tree file; at
    the planning root when git is off or the root is not a git repository."""
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
    git_off = getattr(args, "no_git", False) or os.environ.get("AIDLC_GIT", "").lower() == "off"
    if not git_off:
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
    if cmd == "inputs":
        return cmd_inputs(bolt, state, catalog, args.stage, args.unit)
    if cmd == "workspace":
        return cmd_workspace(bolt, state, args)

    require_open(state)
    if cmd == "target":
        return cmd_target(bolt, state, catalog, args)
    if cmd == "jira":
        return cmd_jira(bolt, state, catalog, args)
    if cmd == "kind":
        return cmd_kind(bolt, state, catalog, args.set)
    if cmd == "assign":
        return cmd_assign(bolt, state, catalog, args)
    if cmd in {"decide", "step", "gate"}:
        stage = stage_def(catalog, args.stage)
        suffix = ""
        if cmd == "gate":
            return cmd_gate(bolt, state, catalog, stage, args.unit, args)
        if cmd in {"decide", "step"}:
            require_story(state, stage, args.unit)
            suffix = guard_owner(bolt, state, args.unit, args.takeover)
        if cmd == "decide":
            cmd_decide(state, stage, args.unit, args.decision, args.reason)
            event, note = "decide", f"{args.decision}: {args.reason}"
        else:
            cmd_step(state, stage, args.unit, args.to)
            if args.to == "produced":
                record = get_record(state, stage, args.unit)
                record["relied_on"] = relied_on(bolt, state, catalog, stage, args.unit)
            event, note = "step", f"to {args.to}"
        nxt = commit(bolt, state, catalog)
        prefix = f"[{args.unit}] " if args.unit else ""
        log_event(bolt, event, stage["id"], "", prefix + note + suffix, args.unit or "")
        return {"ok": True, "stage": stage["id"], "unit": args.unit, "next": nxt}
    if cmd == "units":
        return cmd_units(bolt, state, catalog, Path(args.file))
    if cmd == "decision-id":
        if args.count < 1:
            die(EXIT_USAGE, "--count must be at least 1.")
        suffix = guard_owner(bolt, state, args.unit, args.takeover)
        holder = find_unit(state, args.unit) if args.unit else state
        start = int(holder.get("decision_seq") or 0)
        ids = [f"D{start + i}" for i in range(1, args.count + 1)]
        holder["decision_seq"] = start + args.count
        write_state(bolt, state)
        log_event(bolt, "decision-id", "", "", ",".join(ids) + suffix, args.unit or "")
        result: dict[str, Any] = {"ok": True, "ids": ids}
        if args.unit:
            result["cite_as"] = [f"{args.unit}:{i}" for i in ids]
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
