"""Acceptance scenario of the additive-Slice change: three engineers, one bare remote.

Ana and Ben build the Units of Slice s1 while Cleo plans Slice s2 from a clone that is
behind theirs. Planning must add records and touch nothing that already exists: no
Bolt-level stage, no state file of a Unit under way, no owner, no decision counter. Then
each Slice goes through Build and Test and Operation on its own.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import test_aidlc_state_git as gitbase
from test_aidlc_state_git import BOLT_ID, SCRIPT, git, script, write

identity = gitbase.identity  # the fixtures of the git tests, reused as they are

CHANGING = {"open", "decide", "step", "gate", "units", "slice", "assign", "decision-id", "jira"}
QUESTIONS = (
    "## Q1 Scope\nContext line.\n\nA) One\nB) Two\nX) Other (describe)\n\n"
    "Recommended: A - simplest.\n\nAnswer: A\n"
)
UNIT_STAGES = ("functional-design", "nfr-requirements", "nfr-design", "infrastructure-design")
BAT_FILES = ("build-instructions.md", "build-and-test-summary.md", "cross-unit-traceability.md")
RELEASE_FILES = ("release-plan.md", "runbook.md", "rollback-runbook.md", "verification-checks.md")


def digest(verdict: str = "") -> str:
    return (verdict + "\n\n" if verdict else "") + "# Title\n\n## Digest\n- one\n- two\n\n## Body\n"


class Team:
    """Clones of one bare remote, one per engineer, and a way to act as each of them."""

    def __init__(self, base_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch
        remote = base_dir / "remote.git"
        seed = base_dir / "seed"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
        git(seed, "remote", "add", "origin", str(remote))
        write(seed / "README.md", "planning repo\n")
        write(
            seed / ".gitattributes",
            "bolts/*/log.md merge=union\nbolts/*/units/*/log.md merge=union\n",
        )
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "start")
        git(seed, "push", "-q", "-u", "origin", "main")
        self.clones = {who: base_dir / who.lower() for who in ("Ana", "Ben", "Cleo")}
        for clone in self.clones.values():
            subprocess.run(["git", "clone", "-q", str(remote), str(clone)], check=True)
        self.remote = remote

    def bolt(self, who: str) -> Path:
        return self.clones[who] / "bolts" / BOLT_ID

    def pull(self, *people: str) -> None:
        for who in people or tuple(self.clones):
            git(self.clones[who], "pull", "-q")

    def run(self, who: str, command: str, *args: str, code: int = 0) -> dict[str, Any]:
        self.monkeypatch.setenv("AIDLC_ACTOR", who)
        got, out, raw = script(command, "--bolt", str(self.bolt(who)), *args)
        assert got == code, raw
        if command in CHANGING:  # every change is shared without a manual step
            assert out["git"]["pushed"] is True and not out["git"].get("not_shared"), out["git"]
        return out

    def state(self, who: str) -> dict[str, Any]:
        return json.loads((self.bolt(who) / "state.json").read_text(encoding="utf-8"))

    def unit_file(self, who: str, unit: str) -> bytes:
        return (self.bolt(who) / "units" / unit / "state.json").read_bytes()

    def put(self, who: str, data: dict[str, Any]) -> dict[str, Any]:
        spec = self.clones[who] / "units.json"
        spec.write_text(json.dumps(data), encoding="utf-8")
        try:
            return self.run(who, "units", "--set", str(spec))
        finally:
            spec.unlink()

    def files(self, who: str, rel: str, names: tuple[str, ...], verdict_in: str = "") -> None:
        for name in names:
            text = digest("Verdict: pass" if name == verdict_in else "")
            write(self.bolt(who) / rel / name, text)

    def skip_unit_stages(self, who: str, unit: str, stages: tuple[str, ...]) -> None:
        for stage in stages:
            self.run(who, "decide", "--stage", stage, "--unit", unit, "--decision", "skip",
                     "--reason", "scenario")  # fmt: skip

    def pass_stage(self, who: str, stage: str, sid: str) -> None:
        self.run(who, "step", "--stage", stage, "--slice", sid, "--to", "produced")
        self.run(who, "gate", "--stage", stage, "--slice", sid, "--approve")

    def build_and_test(self, who: str, sid: str) -> None:
        rel = f"docs/slices/{sid}/build-and-test"
        self.files(who, rel, (*BAT_FILES, "test-results.md"), "test-results.md")
        self.pass_stage(who, "build-and-test", sid)

    def slices(self, who: str) -> dict[str, dict[str, Any]]:
        return {r["id"]: r for r in self.run(who, "status")["slice_details"]}


def test_three_engineers_add_a_slice_while_two_others_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = Team(tmp_path, monkeypatch)
    monkeypatch.setenv("AIDLC_ACTOR", "Ana")
    code, _, raw = script("open", "--root", str(team.clones["Ana"]), "--slug", "demo",
                          "--title", "Demo", "--intent", "Try it", "--date", "2026-01-05",
                          "--units", "split")  # fmt: skip
    assert code == 0, raw

    # 1. Inception is done; s1 is ready with u1 (Ana) and u2 (Ben), both in Construction.
    team.run("Ana", "gate", "--stage", "workspace-detection", "--approve", "--by", "Ana")
    catalog = json.loads((SCRIPT.parent.parent / "assets" / "stages.json").read_text())["stages"]
    for item in catalog:
        if item["phase"] in ("discovery", "inception") and item["id"] != "workspace-detection":
            team.run("Ana", "decide", "--stage", item["id"], "--decision", "skip",
                     "--reason", "scenario")  # fmt: skip
    team.run("Ana", "jira", "--off", "--reason", "scenario")
    team.put(
        "Ana",
        {
            "slices": [{"id": "s1", "name": "First"}],
            "units": [
                {"id": "u1", "name": "A", "owner": "Ana", "slice": "s1"},
                {"id": "u2", "name": "B", "owner": "Ben", "slice": "s1"},
            ],
        },
    )
    team.run("Ana", "slice", "--ready", "s1")
    team.pull("Ben")
    for who, unit in (("Ana", "u1"), ("Ben", "u2")):
        team.skip_unit_stages(who, unit, ("functional-design",))
        team.run(who, "decide", "--stage", "code-generation", "--unit", unit,
                 "--decision", "execute", "--reason", "scenario")  # fmt: skip
        team.run(who, "step", "--stage", "code-generation", "--unit", unit, "--to", "asked")
    assert team.run("Ana", "decision-id", "--unit", "u1")["ids"] == ["D1"]
    team.pull()
    cleo_mark = git(team.clones["Cleo"], "rev-parse", "HEAD")

    # 2. Ana and Ben move on while Cleo, whose clone is now behind, plans s2.
    team.run("Ana", "step", "--stage", "code-generation", "--unit", "u1", "--to", "analysed")
    team.run("Ben", "step", "--stage", "code-generation", "--unit", "u2", "--to", "analysed")
    stages_before = team.state("Ana")["stages"]
    next_before = team.run("Ana", "next", "--unit", "u1")
    ana_file = team.unit_file("Ana", "u1")
    team.put(
        "Cleo",
        {
            "slices": [{"id": "s2", "name": "Second", "depends_on": ["s1"]}],
            "units": [
                {"id": "u3", "name": "C", "owner": "Cleo", "slice": "s2"},
                {"id": "u4", "name": "D", "owner": "Cleo", "slice": "s2"},
            ],
        },
    )
    team.run("Ben", "step", "--stage", "code-generation", "--unit", "u2", "--to", "produced")
    ben_file = team.unit_file("Ben", "u2")
    team.run("Cleo", "slice", "--ready", "s2")

    # 3. Nothing that existed was touched, and everything is shared.
    team.pull()
    state = team.state("Cleo")
    assert state["stages"] == stages_before  # no Bolt-level stage changed
    assert team.run("Cleo", "next", "--unit", "u1") == next_before
    assert team.unit_file("Cleo", "u1") == ana_file  # as their owners last wrote them
    assert team.unit_file("Cleo", "u2") == ben_file
    log = git(team.clones["Cleo"], "log", "--format=%H %s", f"{cleo_mark}..HEAD").splitlines()
    planned = [row.split()[0] for row in log if row.endswith(("load the units", "s2 ready"))]
    assert len(planned) == 2  # Cleo's two commands
    for sha in planned:
        touched = git(team.clones["Cleo"], "show", "--name-only", "--format=", sha)
        assert "units/u1/" not in touched and "units/u2/" not in touched, touched
    assert {u["id"]: u["owner"] for u in state["units"]} == {
        "u1": "Ana", "u2": "Ben", "u3": "Cleo", "u4": "Cleo",
    }  # fmt: skip
    assert team.run("Ana", "decision-id", "--unit", "u1")["ids"] == ["D2"]  # the counter goes on
    assert [s["id"] for s in state["slices"]] == ["s1", "s2"]

    # 4. s1 finishes and passes Build and Test while s2 is still building.
    team.pull()
    for who, unit in (("Ana", "u1"), ("Ben", "u2")):
        rel = f"docs/construction/{unit}/code-generation"
        names = ("code-generation-plan.md", "unit-test-instructions.md", "code-summary.md")
        team.files(who, rel, names, "code-summary.md")
        if unit == "u1":  # Ben produced u2 above; Ana is a step behind
            team.run(who, "step", "--stage", "code-generation", "--unit", unit, "--to", "produced")
        write(team.bolt(who) / rel / "source-manifest.json", "{}")
        write(team.bolt(who) / rel / "traceability.json", "{}")
        team.run(who, "gate", "--stage", "code-generation", "--unit", unit, "--approve")
        team.skip_unit_stages(who, unit, UNIT_STAGES[1:])
    team.pull()
    assert team.run("Ana", "next", "--slice", "s1")["blocked_by"] == []
    s2_waits = team.run("Cleo", "next", "--slice", "s2")["blocked_by"]
    assert "waits for slice s1 (verified)" in s2_waits
    team.build_and_test("Ana", "s1")
    rows = team.slices("Ana")
    assert rows["s1"]["status"] == "verified" and rows["s1"]["verdict"] == "pass"
    assert rows["s2"]["status"] == "ready"
    team.pull()
    team.skip_unit_stages("Cleo", "u3", (*UNIT_STAGES, "code-generation"))
    team.skip_unit_stages("Cleo", "u4", (*UNIT_STAGES, "code-generation"))
    assert team.run("Cleo", "next", "--slice", "s2")["blocked_by"] == []
    team.build_and_test("Cleo", "s2")
    assert team.slices("Cleo")["s2"]["status"] == "verified"

    # ... and Operation is recorded for s1 alone.
    team.pull()
    base = "docs/slices/s1/deployment-pipeline"
    team.run("Ana", "decide", "--stage", "deployment-pipeline", "--slice", "s1",
             "--decision", "execute", "--reason", "release s1")  # fmt: skip
    write(team.bolt("Ana") / base / "deployment-pipeline-questions.md", QUESTIONS)
    team.files("Ana", base, RELEASE_FILES)
    team.pass_stage("Ana", "deployment-pipeline", "s1")
    team.run("Ana", "decide", "--stage", "deployment-execution", "--slice", "s1",
             "--decision", "execute", "--reason", "release s1")  # fmt: skip
    team.files(
        "Ana", "docs/slices/s1/deployment-execution", ("deploy-log.md", "verification-results.md")
    )
    team.pass_stage("Ana", "deployment-execution", "s1")
    team.pull()
    final = team.slices("Cleo")
    assert final["s1"]["status"] == "released" and final["s2"]["status"] == "verified"
    s2 = next(s for s in team.state("Cleo")["slices"] if s["id"] == "s2")
    assert s2["stages"]["deployment-pipeline"]["step"] == "todo"

    # 5. A Unit of s2 is cancelled and replaced by two new ones; nothing of it is deleted.
    team.put("Cleo", {"units": [{"id": "u5", "slice": "s2", "owner": "Cleo"},
                                {"id": "u6", "slice": "s2", "owner": "Cleo"}]})  # fmt: skip
    team.run("Cleo", "units", "--cancel", "u4", "--reason", "too large",
             "--superseded-by", "u5,u6")  # fmt: skip
    team.pull()
    final_state = team.state("Ana")
    cancelled = next(u for u in final_state["units"] if u["id"] == "u4")
    assert cancelled["cancelled"]["superseded_by"] == ["u5", "u6"]
    assert (team.bolt("Ana") / "units" / "u4" / "state.json").is_file()
    assert {u["id"] for u in final_state["units"]} == {"u1", "u2", "u3", "u4", "u5", "u6"}
    assert team.run("Ana", "next", "--unit", "u4")["action"] == "cancelled"
    assert team.slices("Ana")["s2"]["units_total"] == 3  # u3, u5, u6
    heads = {git(clone, "rev-parse", "HEAD") for clone in team.clones.values()}
    assert heads == {git(team.remote, "rev-parse", "main")}
