"""A result says what is true: a failed reservation leaves nothing behind, and the first
write of an older Bolt says what it dropped."""

from __future__ import annotations

import json
from pathlib import Path

import test_aidlc_state_git as base
from test_aidlc_state_git import Repos, bolt_of, git, script

identity = base.identity
repos = base.repos


def snapshot(bolt: Path) -> dict[str, str]:
    return {
        str(p.relative_to(bolt)): p.read_text(encoding="utf-8")
        for p in sorted(bolt.rglob("*"))
        if p.is_file() and p.name in ("state.json", "log.md")
    }


def test_a_failed_reservation_is_undone_so_its_message_is_true(repos: Repos) -> None:
    bolt = base.split_demo(repos)
    before = snapshot(bolt)
    head = git(repos.a, "rev-parse", "HEAD")
    hook = repos.a / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    code, out, _ = script("decision-id", "--bolt", str(bolt), "--unit", "u1", "--count", "2")
    assert code == 6 and "the ids were not reserved" in out["error"], out
    assert git(repos.a, "rev-parse", "HEAD") == head  # its own commit is gone
    assert snapshot(bolt) == before  # counter and log are as before
    assert git(repos.a, "status", "--porcelain") == ""
    hook.unlink()
    code, out, _ = script("decision-id", "--bolt", str(bolt), "--unit", "u1", "--count", "2")
    assert code == 0 and out["ids"] == ["D1", "D2"]  # what the failed run would have given


def test_a_reservation_that_cannot_be_undone_says_where_the_ids_are(repos: Repos) -> None:
    bolt = base.split_demo(repos)
    hook = repos.a / ".git" / "hooks" / "pre-push"
    # the push fails and, meanwhile, the commit is moved on so it is no longer the tip
    hook.write_text("#!/bin/sh\ngit commit -q --allow-empty -m other\nexit 1\n")
    hook.chmod(0o755)
    code, out, _ = script("decision-id", "--bolt", str(bolt), "--unit", "u1")
    assert code == 6 and "saved in this clone and not shared" in out["error"], out
    assert "D1" in out["error"] and "were not reserved" not in out["error"]


def framework3_bolt(repos: Repos) -> Path:
    assert base.open_demo(repos.a)[0] == 0
    bolt = bolt_of(repos.a)
    path = bolt / "state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["framework"] = 3
    state["approver"] = "Ana (technical); Bo (business)"
    state["kind"] = "delivery"
    state["stages"]["build-and-test"] = {
        "decision": "execute", "reason": "", "step": "todo",
        "approved_at": None, "approved_by": None,
    }  # fmt: skip
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return bolt


def test_the_first_write_of_a_framework_3_bolt_logs_and_warns_what_it_dropped(
    repos: Repos,
) -> None:
    bolt = framework3_bolt(repos)
    code, out, _ = script("park", "--bolt", str(bolt), "--note", "x", "--no-git")
    assert code == 0, out
    lines = [
        x for x in (bolt / "log.md").read_text(encoding="utf-8").splitlines() if "| migrate |" in x
    ]
    assert len(lines) == 1
    for text in (
        'approver was "Ana (technical); Bo (business)"',
        'kind was "delivery"',
        "framework 3 to 4",
        "build-and-test",
        "recorded per Slice",
    ):
        assert text in lines[0], lines[0]
        assert any(text in w for w in out["warnings"]), out
    code, out, _ = script("unpark", "--bolt", str(bolt), "--no-git")  # exactly once
    log = (bolt / "log.md").read_text(encoding="utf-8")
    assert log.count("| migrate |") == 1
    assert not any("framework 3" in w for w in out.get("warnings", []))


def test_a_bolt_with_nothing_to_drop_gets_no_migrate_line(repos: Repos) -> None:
    assert base.open_demo(repos.a)[0] == 0
    bolt = bolt_of(repos.a)
    path = bolt / "state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["framework"] = 3
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    assert script("park", "--bolt", str(bolt), "--note", "x", "--no-git")[0] == 0
    assert "| migrate |" not in (bolt / "log.md").read_text(encoding="utf-8")


def test_a_context_report_first_brings_in_the_teams_work(repos: Repos) -> None:
    bolt = base.split_demo(repos)  # b has pulled; now a changes the Bolt and shares it
    assert script("park", "--bolt", str(bolt), "--note", "from a")[0] == 0
    theirs = git(repos.a, "rev-parse", "HEAD")
    mine = bolt_of(repos.b)
    code, out, _ = script("context", "--unit", "u1", "--bolt", str(mine), "--no-git")
    assert code == 0 and git(repos.b, "rev-parse", "HEAD") != theirs  # --no-git skips it
    code, out, _ = script("context", "--unit", "u1", "--bolt", str(mine))
    assert code == 0, out
    assert git(repos.b, "rev-parse", "HEAD") == theirs  # fetched and nothing new committed
    assert "last successful fetch" not in json.dumps(out)


def test_a_context_report_says_so_when_the_remote_cannot_be_reached(repos: Repos) -> None:
    base.split_demo(repos)
    git(repos.b, "remote", "set-url", "origin", str(repos.b.parent / "gone.git"))
    head = git(repos.b, "rev-parse", "HEAD")
    code, out, _ = script("context", "--unit", "u1", "--bolt", str(bolt_of(repos.b)))
    assert code == 0 and "reports" in out, out
    assert any("last successful fetch" in w for w in out["warnings"])
    assert git(repos.b, "rev-parse", "HEAD") == head
