#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Open, advance, gate and close a paddock, the folder for one piece of work.

Progress lives in one ``state.json`` per paddock and changes only through this
script. A model that edits progress by hand will, sooner or later, mark a stage
approved that nobody approved; a script that checks the artifacts first cannot.
Everything here is deterministic, so it costs no model tokens.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn, Optional, cast

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EPILOG = """commands:
  open        create a paddock           --root R --slug S --title T --intent I
  status      show progress              --paddock P [--format text]
  next        the next stage and step    --paddock P
  inputs      files a stage reads        --paddock P --stage S [--unit U]
  decide      execute or skip a stage    --paddock P --stage S --decision D --reason R
  step        move a stage forward       --paddock P --stage S --to asked|analysed|produced
  gate        approve or send back       --paddock P --stage S --approve --by NAME
  units       load units and bolts       --paddock P --set file.json
  decision-id reserve decision ids       --paddock P [--count n]
  codekb-status is the code knowledge fresh --paddock P
  park/unpark hand-over note             --paddock P --note N
  close       close the paddock          --paddock P --status complete|superseded|archived

examples:
  python3 aidlc_state.py open --root . --slug billing --title "Billing" --intent "Move billing"
  python3 aidlc_state.py next --paddock paddocks/2026-01-05-billing
  python3 aidlc_state.py gate --paddock paddocks/2026-01-05-billing --stage requirements-analysis \\
      --approve --by "A. Approver"

exit codes:
  0  ok
  1  findings: a gate or close was refused, or the paddock already exists
  2  usage error
  3  missing input: no paddock, no state.json, or a stage input is absent
  4  malformed input: state.json, stages.json or a units file cannot be parsed
  5  internal error
"""

LOG = logging.getLogger("aidlc_state")

STAGES_PATH = Path(__file__).resolve().parent.parent / "assets" / "stages.json"
STEP_ORDER = ["todo", "asked", "analysed", "produced"]
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
META_KEYS = ["repo", "path", "commit", "built", "artifacts"]
NO_TRACEABILITY_SCOPES = {"bugfix", "express"}  # no stories or units to trace
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SCOPES = ["classic", "express", "bugfix"]
DEPTHS = ["minimal", "standard", "comprehensive"]
DEFAULT_DEPTH = {"classic": "standard", "express": "standard", "bugfix": "minimal"}
DEFAULT_UNIT_SCOPES = {"express", "bugfix"}
UNIT_KINDS = ["service", "spec", "ui", "packaging", "library"]
ROOT_PREFIX = "root:"
FOCUSED_RESCAN_MAX = 0.30
CHANGED_FILES_CAP = 50
PHASES = ["discovery", "inception", "construction"]
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs", ".rb", ".cs",
    ".sql", ".scala", ".sh", ".php", ".swift", ".c", ".cc", ".cpp", ".h", ".hpp",
}  # fmt: skip
SCAFFOLD_NAMES = {"__init__.py", "setup.py", "conftest.py"}
DIGEST_MAX_LINES = 10
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


# --- paddock files -----------------------------------------------------------


def state_path(paddock: Path) -> Path:
    return paddock / "state.json"


def load_state(paddock: Path) -> dict[str, Any]:
    path = state_path(paddock)
    if not paddock.is_dir():
        die(EXIT_INPUT, f"{paddock}: paddock folder not found. Open one with `open`.")
    if not path.is_file():
        die(EXIT_INPUT, f"{path}: state.json not found.")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{path}: invalid JSON at line {exc.lineno}: {exc.msg}")
    if not isinstance(state, dict) or state.get("schema") != 1:
        die(EXIT_MALFORMED, f'{path}: expected an object with "schema": 1.')
    return state


def write_state(paddock: Path, state: dict[str, Any]) -> None:
    """Write state.json atomically: a crash leaves the old file, never half a new one."""
    state["updated"] = now()
    path = state_path(paddock)
    tmp = path.with_name(".state.json.tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def log_event(paddock: Path, event: str, stage: str = "", by: str = "", note: str = "") -> None:
    def clean(value: str) -> str:
        text = " ".join(value.replace("|", "/").split())
        return text or "-"

    line = " | ".join([now(), clean(event), clean(stage), clean(by or "agent"), clean(note)])
    with (paddock / "log.md").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def require_open(state: dict[str, Any]) -> None:
    if state.get("status") != "open":
        raise Fail(
            EXIT_FINDINGS, f"paddock is {state.get('status')}; it no longer accepts changes."
        )


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
    catalog: list[dict[str, Any]], scope: str, existing: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    records: dict[str, Any] = dict(existing or {})
    for item in catalog:
        if item["per_unit"] and item["id"] not in records:
            decision, reason = initial_decision(item, scope, True)
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
            if not state["units"]:
                result.append((per_unit[0], None))
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


def compute_next(state: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    for item, unit in slots(state, catalog):
        record = slot_record(state, item, unit)
        if is_done(record):
            continue
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
        return {**base, "action": action}
    return {"done": True, "stage": None, "unit": None, "action": "close"}


def describe_next(nxt: dict[str, Any]) -> str:
    if nxt["done"]:
        return "all stages done; close the paddock"
    where = nxt["stage"] + (f" [{nxt['unit']}]" if nxt["unit"] else "")
    if nxt["action"] == "load-units":
        return f"load units before {where}"
    return f"{nxt['action']}: {where} (skill {nxt['skill']})"


def refresh(state: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    nxt = compute_next(state, catalog)
    state["current"] = {"stage": nxt["stage"], "unit": nxt["unit"]}
    state["next_action"] = describe_next(nxt)
    return nxt


def commit(paddock: Path, state: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    nxt = refresh(state, catalog)
    write_state(paddock, state)
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


def cmd_open(args: argparse.Namespace, catalog: list[dict[str, Any]]) -> dict[str, Any]:
    if not SLUG.match(args.slug):
        die(EXIT_USAGE, "--slug must be lower-case letters, digits and hyphens.")
    date = args.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    if not DATE.match(date):
        die(EXIT_USAGE, "--date must be YYYY-MM-DD.")
    root = Path(args.root)
    if not root.is_dir():
        die(EXIT_INPUT, f"{root}: --root is not a directory.")
    paddock_id = f"{date}-{args.slug}"
    paddock = root / "paddocks" / paddock_id
    if paddock.exists():
        raise Fail(EXIT_FINDINGS, f"{paddock}: paddock already exists. Resume it with `status`.")

    targets: list[dict[str, Any]] = []
    rules: list[str] = []
    for spec in args.target or []:
        name, sep, raw = spec.partition("=")
        if not sep or not name or not raw:
            die(EXIT_USAGE, f"--target '{spec}' must look like name=path.")
        target_path = Path(raw).expanduser().resolve()
        if not target_path.is_dir():
            die(EXIT_INPUT, f"{target_path}: target for '{name}' is not a directory.")
        kind, rule = classify(target_path)
        targets.append(
            {"repo": name, "path": str(target_path), "kind": kind, "codekb_commit": None}
        )
        rules.append(f"{name}: {kind} ({rule})")

    architecture: Optional[dict[str, Any]] = None
    if args.architecture_ref:
        ref = Path(args.architecture_ref).expanduser().resolve()
        if not ref.is_dir():
            die(EXIT_INPUT, f"{ref}: --architecture-ref is not a directory.")
        sha = git(ref, "rev-parse", "HEAD")
        architecture = {"path": str(ref), "commit": sha.strip() if sha else None}
        if sha is None:
            LOG.warning("%s: not a git checkout; the registry commit is recorded as null.", ref)

    brownfield = any(t["kind"] == "brownfield" for t in targets)
    stages: dict[str, Any] = {}
    for item in catalog:
        if item["per_unit"]:
            continue
        decision, reason = initial_decision(item, args.scope, brownfield)
        step = "produced" if item["id"] == "workspace-detection" else "todo"
        stages[item["id"]] = new_record(decision, reason, step)

    units: list[dict[str, Any]] = []
    bolts: list[dict[str, Any]] = []
    if args.scope in DEFAULT_UNIT_SCOPES:
        units = [
            {
                "id": "u1",
                "name": args.title,
                "kind": None,
                "bolt": "b1",
                "stages": unit_stage_records(catalog, args.scope),
            }
        ]
        bolts = [{"id": "b1", "units": ["u1"], "status": "todo"}]

    state: dict[str, Any] = {
        "schema": 1,
        "id": paddock_id,
        "title": args.title,
        "intent": args.intent,
        "status": "open",
        "scope": args.scope,
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
        "bolts": bolts,
        "current": {"stage": None, "unit": None},
        "next_action": "",
        "parked": None,
    }

    folders = [
        "inputs",
        "knowledge/extracted",
        "architecture",
        "docs/inception",
        "docs/construction",
    ]
    for folder in folders:
        (paddock / folder).mkdir(parents=True, exist_ok=True)
        (paddock / folder / ".gitkeep").touch()
    (paddock / "log.md").touch()
    nxt = commit(paddock, state, catalog)
    log_event(paddock, "open", "", "", f"scope={args.scope} depth={state['depth']}")
    for rule in rules:
        log_event(paddock, "classify", "workspace-detection", "", rule)
    return {
        "ok": True,
        "paddock": str(paddock),
        "id": paddock_id,
        "targets": targets,
        "architecture_ref": architecture,
        "codekb": codekb_status(root.resolve(), targets),
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


def cmd_status(state: dict[str, Any], catalog: list[dict[str, Any]], fmt: str) -> dict[str, Any]:
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
        "bolts": len(state["bolts"]),
        "current": state["current"],
        "step": nxt.get("step"),
        "action": nxt["action"],
        "next_action": state["next_action"],
        "parked": state["parked"],
    }
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
    lines.append(f"Units: {len(state['units'])} | Bolts: {len(state['bolts'])}")
    if nxt["done"]:
        lines.append("Current: none")
    else:
        where = nxt["stage"] + (f" [{nxt['unit']}]" if nxt["unit"] else "")
        lines.append(f"Current: {where}, step {nxt['step']}")
    lines.append(f"Next: {state['next_action']}")
    if state["parked"]:
        note = str(state["parked"].get("note", "")).replace("\n", " ")
        lines.append(f"Parked: {note[:300]}")
    return {"text": "\n".join(lines[:20]) + "\n"}


def planning_root(paddock: Path) -> Path:
    """The planning repository root: paddocks live in ``<root>/paddocks/<id>``."""
    return paddock.resolve().parent.parent


def locate(paddock: Path, rel: str) -> Path:
    """Resolve a stages.json path: ``root:`` paths hang off the planning root."""
    if rel.startswith(ROOT_PREFIX):
        return planning_root(paddock) / rel[len(ROOT_PREFIX) :]
    return paddock / rel


def glob_paths(paddock: Path, rel: str) -> list[Path]:
    if rel.startswith(ROOT_PREFIX):
        return sorted(planning_root(paddock).glob(rel[len(ROOT_PREFIX) :]))
    return sorted(paddock.glob(rel))


def brownfield_repos(state: dict[str, Any]) -> list[str]:
    return [t["repo"] for t in state["targets"] if t["kind"] == "brownfield"]


def unit_ids(state: dict[str, Any], stage: dict[str, Any], unit: Optional[str]) -> list[str]:
    """The units a stage's ``<unit>`` paths cover: its own unit, or every unit."""
    if stage["per_unit"]:
        return [unit] if unit else []
    return [u["id"] for u in state["units"]]


def expand_pairs(
    template: str, repos: list[str], units: list[str]
) -> list[tuple[str, Optional[str]]]:
    """Expand ``<repo>`` over brownfield targets and ``<unit>`` over ``units``."""
    pairs: list[tuple[str, Optional[str]]] = [(template, None)]
    if "<unit>" in template:
        pairs = [(template.replace("<unit>", u), u) for u in units]
    if "<repo>" in template:
        pairs = [(rel.replace("<repo>", repo), u) for rel, u in pairs for repo in repos]
    return pairs


def expand(template: str, repos: list[str], units: list[str]) -> list[str]:
    return [rel for rel, _ in expand_pairs(template, repos, units)]


def producer_of(catalog: list[dict[str, Any]], template: str) -> Optional[dict[str, Any]]:
    for item in catalog:
        if template in item["artifacts"]:
            return item
    return None


def cmd_inputs(
    paddock: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage_id: str,
    unit: Optional[str],
) -> dict[str, Any]:
    stage = stage_def(catalog, stage_id)
    get_record(state, stage, unit)
    repos = brownfield_repos(state)
    units = unit_ids(state, stage, unit)
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for entry in stage["inputs"]:
        producer = producer_of(catalog, entry["path"])
        optional = bool(entry.get("optional"))
        for rel, row_unit in expand_pairs(entry["path"], repos, units):
            skipped = False
            if producer is not None:
                producer_unit = row_unit if producer["per_unit"] else None
                rec = slot_record(state, producer, producer_unit)
                skipped = bool(rec and rec["decision"] == "skip")
            file = locate(paddock, rel)
            exists = file.is_file()
            row = {
                "path": rel,
                "file": str(file.resolve()),
                "mode": entry["mode"],
                "exists": exists,
                "produced_by": producer["id"] if producer else None,
                "skipped": skipped and not exists,
                "optional": optional,
            }
            rows.append(row)
            if not exists and not skipped and not optional:
                missing.append({"path": rel, "produced_by": row["produced_by"]})
    payload = {
        "ok": not missing,
        "stage": stage_id,
        "unit": unit,
        "root": str(planning_root(paddock)),
        "inputs": rows,
        "missing": missing,
    }
    if missing:
        names = ", ".join(f"{m['path']} (stage {m['produced_by'] or 'unknown'})" for m in missing)
        raise Fail(
            EXIT_INPUT, f"stage '{stage_id}' is missing required input: {names}", extra=payload
        )
    return payload


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
    path = Path(target["path"])
    head = (git(path, "rev-parse", "HEAD") or "").strip()
    row.update({"meta_commit": commit or None, "head": head or None})
    if head and commit == head:
        return {**row, "status": "fresh"}
    known = bool(commit) and git(path, "cat-file", "-e", f"{commit}^{{commit}}") is not None
    if not head or not known:
        why = "target is not a git checkout" if not head else "meta commit is unknown to the repo"
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


def digest_lines(text: str) -> Optional[int]:
    """Non-blank lines under ``## Digest``, or ``None`` when the heading is absent."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^##\s+Digest\s*$", line):
            count = 0
            for follow in lines[index + 1 :]:
                if re.match(r"^#{1,6}\s", follow):
                    break
                if follow.strip():
                    count += 1
            return count
    return None


def gate_findings(
    paddock: Path,
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
            path = locate(paddock, rel)
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
            path = locate(paddock, rel)
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
                clarifications.extend(glob_paths(paddock, rel))
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
                        "path": str(item.relative_to(paddock)),
                        "message": f"{found['question']} line {found['line']}: {found['message']}",
                    }
                )
    for template in as_list(stage.get("signoff")):
        for rel in expand(template, repos, units):
            path = locate(paddock, rel)
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
        findings.extend(meta_findings(paddock, state))
    return findings


def meta_findings(paddock: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Each brownfield target's ``_meta.json`` must carry the fields the freshness check reads."""
    findings: list[dict[str, Any]] = []
    root = planning_root(paddock)
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
    """The last Inception stage of the paddock's scope that is not skipped."""
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
    paddock: Path, state: dict[str, Any], catalog: list[dict[str, Any]], stage: dict[str, Any]
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
    result = module.check(paddock)
    return [
        {
            "code": "traceability-" + item["code"],
            "path": item.get("id", ""),
            "message": item["message"],
        }
        for item in result["findings"]
    ]


def record_codekb_commits(paddock: Path, state: dict[str, Any]) -> None:
    """Remember which commit of each target's code knowledge this paddock relied on."""
    root = planning_root(paddock)
    for target in state["targets"]:
        meta = read_meta(root, target["repo"]) if target["kind"] == "brownfield" else None
        if meta is not None:
            target["codekb_commit"] = meta.get("commit")


def cmd_gate(
    paddock: Path,
    state: dict[str, Any],
    catalog: list[dict[str, Any]],
    stage: dict[str, Any],
    unit: Optional[str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    record = get_record(state, stage, unit)
    label = stage["id"]
    if args.request_changes:
        if not (args.note or "").strip():
            die(EXIT_USAGE, "--request-changes needs --note.")
        if record["step"] == "approved":
            raise Fail(EXIT_FINDINGS, f"stage '{label}' is already approved.")
        record["step"] = "changes-requested"
        record["approved_at"] = None
        record["approved_by"] = None
        nxt = commit(paddock, state, catalog)
        log_event(paddock, "gate-request-changes", label, args.by or "", args.note)
        return {"ok": True, "stage": label, "unit": unit, "step": record["step"], "next": nxt}
    if not (args.by or "").strip():
        die(EXIT_USAGE, "--approve needs --by NAME.")
    findings = gate_findings(paddock, state, stage, unit, record)
    findings.extend(traceability_findings(paddock, state, catalog, stage))
    if findings:
        raise Fail(
            EXIT_FINDINGS,
            f"gate refused for '{label}': {len(findings)} finding(s).",
            findings=findings,
        )
    record["step"] = "approved"
    record["approved_at"] = now()
    record["approved_by"] = args.by.strip()
    if stage["id"] == "reverse-engineering":
        record_codekb_commits(paddock, state)
    if not state.get("approver"):
        state["approver"] = args.by.strip()
    nxt = commit(paddock, state, catalog)
    log_event(paddock, "gate-approve", label, args.by, unit or "")
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


def cmd_units(
    paddock: Path, state: dict[str, Any], catalog: list[dict[str, Any]], file: Path
) -> dict[str, Any]:
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(EXIT_INPUT, f"{file}: units file not found.")
    except json.JSONDecodeError as exc:
        die(EXIT_MALFORMED, f"{file}: invalid JSON at line {exc.lineno}: {exc.msg}")
    if not isinstance(data, dict) or not ("units" in data or "bolts" in data):
        die(EXIT_MALFORMED, f'{file}: expected an object with "units" and/or "bolts".')

    old = {u["id"]: u for u in state["units"]}
    units = data.get("units", state["units"])
    bolts = data.get("bolts", state["bolts"])
    if not isinstance(units, list) or not isinstance(bolts, list):
        die(EXIT_MALFORMED, f'{file}: "units" and "bolts" must be lists.')
    seen: set[str] = set()
    for unit in units:
        uid = unit.get("id") if isinstance(unit, dict) else None
        if not isinstance(uid, str) or not ID_PATTERN.match(uid) or uid in seen:
            die(EXIT_MALFORMED, f"{file}: each unit needs a unique lower-case id; saw {uid!r}.")
        seen.add(uid)
        kind = unit.get("kind")
        if kind is not None and kind not in UNIT_KINDS:
            die(
                EXIT_MALFORMED,
                f"{file}: unit {uid} has kind {kind!r}; use one of {', '.join(UNIT_KINDS)}.",
            )
    seen_bolts: set[str] = set()
    for bolt in bolts:
        bid = bolt.get("id") if isinstance(bolt, dict) else None
        if not isinstance(bid, str) or bid in seen_bolts:
            die(EXIT_MALFORMED, f"{file}: each bolt needs a unique id; saw {bid!r}.")
        seen_bolts.add(bid)
        for member in bolt.get("units", []):
            if member not in seen:
                die(EXIT_MALFORMED, f"{file}: bolt {bid} names unknown unit {member!r}.")
        bolt.setdefault("status", "todo")
    owner_of = {m: b["id"] for b in bolts for m in b.get("units", [])}
    result: list[dict[str, Any]] = []
    for unit in units:
        previous = old.get(unit["id"], {})
        result.append(
            {
                "id": unit["id"],
                "name": unit.get("name", ""),
                "kind": unit.get("kind", previous.get("kind")),
                "bolt": owner_of.get(unit["id"], unit.get("bolt")),
                "stages": unit_stage_records(catalog, state["scope"], previous.get("stages")),
            }
        )
    state["units"] = result
    state["bolts"] = bolts
    nxt = commit(paddock, state, catalog)
    log_event(paddock, "units", "", "", f"{len(result)} unit(s), {len(bolts)} bolt(s)")
    return {
        "ok": True,
        "units": [u["id"] for u in result],
        "bolts": [b["id"] for b in bolts],
        "missing_kind": [u["id"] for u in result if not u["kind"]],
        "next": nxt,
    }


def cmd_close(
    paddock: Path,
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
    write_state(paddock, state)
    log_event(paddock, "close", "", "", status + (f" successor={successor}" if successor else ""))
    return {"ok": True, "status": status, "successor": successor}


# --- command line ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open, advance, gate and close an AI-DLC paddock.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    def add(name: str, help_text: str, paddock: bool = True) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text, description=help_text)
        if paddock:
            sp.add_argument("--paddock", required=True, help="Paddock folder.")
        return sp

    sp = add("open", "Create a paddock.", paddock=False)
    sp.add_argument("--root", required=True, help="Planning repository root (contains paddocks/).")
    sp.add_argument("--slug", required=True)
    sp.add_argument("--title", required=True)
    sp.add_argument("--intent", required=True, help="One sentence.")
    sp.add_argument("--scope", choices=SCOPES, default="classic")
    sp.add_argument("--depth", choices=DEPTHS, help="Default: standard, or minimal for bugfix.")
    sp.add_argument(
        "--target", action="append", metavar="name=path", help="Target repository; repeatable."
    )
    sp.add_argument("--architecture-ref", help="ADR registry checkout; its commit is recorded.")
    sp.add_argument("--owner", help="Paddock owner (optional).")
    sp.add_argument("--approver", help="Default approver (optional).")
    sp.add_argument("--date", help="Override the date part of the id, YYYY-MM-DD.")

    sp = add("status", "Show progress.")
    sp.add_argument("--format", choices=["json", "text"], default="json")

    add("next", "Show the next stage and step.")

    sp = add("inputs", "List the files a stage reads.")
    sp.add_argument("--stage", required=True)
    sp.add_argument("--unit")

    sp = add("decide", "Record EXECUTE or SKIP for a stage.")
    sp.add_argument("--stage", required=True)
    sp.add_argument("--decision", required=True, choices=["execute", "skip"])
    sp.add_argument("--reason", required=True)
    sp.add_argument("--unit")

    sp = add("step", "Move a stage forward.")
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

    sp = add("units", "Load units and bolts from a JSON file.")
    sp.add_argument(
        "--set",
        required=True,
        dest="file",
        help='JSON with "units" (id, name, kind) and/or "bolts"; kind: ' + "|".join(UNIT_KINDS),
    )

    sp = add("decision-id", "Reserve the next decision ids.")
    sp.add_argument("--count", type=int, default=1)

    add("codekb-status", "Is each target's shared code knowledge fresh, stale or missing.")

    sp = add("park", "Leave a hand-over note.")
    sp.add_argument("--note", required=True)
    add("unpark", "Clear the hand-over note.")

    sp = add("close", "Close the paddock.")
    sp.add_argument("--status", required=True, choices=["complete", "superseded", "archived"])
    sp.add_argument("--successor", help="Id of the paddock that replaces this one.")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    catalog = load_catalog()
    if args.command == "open":
        return cmd_open(args, catalog)

    paddock = Path(args.paddock)
    state = load_state(paddock)
    cmd = args.command
    if cmd == "codekb-status":
        return {
            "ok": True,
            "root": str(planning_root(paddock)),
            "targets": codekb_status(planning_root(paddock), state["targets"]),
        }
    if cmd == "status":
        return cmd_status(state, catalog, args.format)
    if cmd == "next":
        return {"ok": True, **compute_next(state, catalog)}
    if cmd == "inputs":
        return cmd_inputs(paddock, state, catalog, args.stage, args.unit)

    require_open(state)
    if cmd in {"decide", "step", "gate"}:
        stage = stage_def(catalog, args.stage)
        if cmd == "gate":
            return cmd_gate(paddock, state, catalog, stage, args.unit, args)
        if cmd == "decide":
            cmd_decide(state, stage, args.unit, args.decision, args.reason)
            event, note = "decide", f"{args.decision}: {args.reason}"
        else:
            cmd_step(state, stage, args.unit, args.to)
            event, note = "step", f"to {args.to}"
        nxt = commit(paddock, state, catalog)
        log_event(paddock, event, stage["id"], "", (f"[{args.unit}] " if args.unit else "") + note)
        return {"ok": True, "stage": stage["id"], "unit": args.unit, "next": nxt}
    if cmd == "units":
        return cmd_units(paddock, state, catalog, Path(args.file))
    if cmd == "decision-id":
        if args.count < 1:
            die(EXIT_USAGE, "--count must be at least 1.")
        start = int(state["decision_seq"])
        ids = [f"D{start + i}" for i in range(1, args.count + 1)]
        state["decision_seq"] = start + args.count
        write_state(paddock, state)
        log_event(paddock, "decision-id", "", "", ",".join(ids))
        return {"ok": True, "ids": ids}
    if cmd == "park":
        state["parked"] = {"note": args.note, "at": now()}
        write_state(paddock, state)
        log_event(paddock, "park", "", "", args.note)
        return {"ok": True, "parked": state["parked"]}
    if cmd == "unpark":
        state["parked"] = None
        write_state(paddock, state)
        log_event(paddock, "unpark")
        return {"ok": True, "parked": None}
    if cmd == "close":
        return cmd_close(paddock, state, catalog, args.status, args.successor)
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
