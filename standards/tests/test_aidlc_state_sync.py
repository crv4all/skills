"""``aidlc_state.py`` never merges a state file: it runs the command again instead.

Two engineers, one bare remote. The race is forced with a ``post-commit`` hook in
the second clone: the moment that clone commits its command, the hook runs the
rival's command in a third clone, which pushes. So the upstream has moved
between the command and its push, and each test asserts that it did.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import test_aidlc_state_git as base
from test_aidlc_state_git import BOLT_ID, SCRIPT, Repos, bolt_of, git, open_demo, script, write

identity = base.identity  # the fixtures of the git tests, reused as they are
repos = base.repos

UNION = "bolts/*/log.md merge=union\nbolts/*/units/*/log.md merge=union\n"


class Race:
    """A Bolt shared by clone ``b`` (the one that runs) and a ``rival`` clone."""

    def __init__(self, repos: Repos, tmp_path: Path, union: bool = False) -> None:
        self.repos = repos
        self.rival = tmp_path / "rival"
        self.marker = tmp_path / "rival.fired"
        self.out = tmp_path / "rival.out"
        if union:
            write(repos.a / ".gitattributes", UNION)
            git(repos.a, "add", ".gitattributes")
            git(repos.a, "commit", "-q", "-m", "union logs")
            git(repos.a, "push", "-q")
        assert open_demo(repos.a)[0] == 0
        git(repos.b, "pull", "-q")
        subprocess.run(["git", "clone", "-q", str(repos.remote), str(self.rival)], check=True)

    @property
    def b(self) -> Path:
        return self.repos.b

    def rival_does(self, subject: str, *command: str, after: str = "") -> None:
        """Run ``command`` (aidlc_state.py arguments) in the rival clone, once, as soon as
        clone ``b`` commits a commit whose subject is ``subject``."""
        cmd = " ".join(f"'{part}'" for part in (sys.executable, str(SCRIPT), *command))
        hook = self.b / ".git" / "hooks" / "post-commit"
        hook.write_text(
            "#!/bin/sh\n"
            "unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE\n"
            f'[ "$(git log -1 --format=%s)" = "{subject}" ] || exit 0\n'
            f"[ -e '{self.marker}' ] && exit 0\n"
            f"touch '{self.marker}'\n"
            f"cd '{self.rival}' && AIDLC_ACTOR=rival {cmd} > '{self.out}' 2>&1\n" + after
        )
        hook.chmod(0o755)

    def rival_result(self) -> dict[str, Any]:
        assert self.marker.exists(), "the rival never ran: the race did not happen"
        return json.loads(self.out.read_text(encoding="utf-8"))

    def remote_state(self) -> dict[str, Any]:
        return json.loads(git(self.repos.remote, "show", f"main:bolts/{BOLT_ID}/state.json"))

    def remote_log(self) -> list[str]:
        return git(self.repos.remote, "show", f"main:bolts/{BOLT_ID}/log.md").splitlines()

    def reflog(self) -> str:
        return git(self.b, "reflog", "--format=%gs")

    def assert_in_step(self) -> None:
        """Nothing is unpushed, nothing is left open, and the clone equals the remote."""
        assert git(self.b, "rev-parse", "HEAD") == git(self.repos.remote, "rev-parse", "main")
        assert not (self.b / ".git" / "rebase-merge").exists()
        assert git(self.b, "status", "--porcelain", "--", f"bolts/{BOLT_ID}") == ""


def decide(clone: Path, stage: str, *flags: str) -> tuple[int, dict[str, Any], str]:
    return script(
        "decide", "--bolt", str(bolt_of(clone)), "--stage", stage, "--decision", "skip",
        "--reason", f"{stage} not needed", *flags,
    )  # fmt: skip


def count(lines: list[str], needle: str) -> int:
    return sum(1 for line in lines if needle in line)


def test_two_engineers_deciding_two_stages_both_land_without_a_manual_step(
    repos: Repos, tmp_path: Path
) -> None:
    race = Race(repos, tmp_path)
    race.rival_does(
        "docs(demo): decide hla: skip",
        "decide", "--bolt", str(bolt_of(race.rival)), "--stage", "requirements-analysis",
        "--decision", "skip", "--reason", "rival",
    )  # fmt: skip
    code, out, _ = decide(race.b, "hla")
    assert code == 0, out
    assert race.rival_result()["ok"] is True  # the upstream moved between our commit and push
    assert out["git"]["pushed"] is True and out["git"]["reruns"] == 1
    assert "reset: moving to HEAD~1" in race.reflog()  # our first commit was dropped, not merged
    state = race.remote_state()
    assert state["stages"]["hla"]["decision"] == "skip"
    assert state["stages"]["requirements-analysis"]["decision"] == "skip"
    log = race.remote_log()
    assert count(log, "| decide | hla |") == 1
    assert count(log, "| decide | requirements-analysis |") == 1
    assert git(race.b, "rev-list", "--merges", "--count", "HEAD") == "0"
    race.assert_in_step()
    assert any("changed while you were working" in w for w in out["git"]["warnings"])


@pytest.mark.parametrize("union", [True, False], ids=["union-logs", "plain-logs"])
def test_a_decision_id_race_gives_two_actors_two_different_ids(
    repos: Repos, tmp_path: Path, union: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    race = Race(repos, tmp_path, union=union)
    monkeypatch.setenv("AIDLC_ACTOR", "bee")
    race.rival_does(
        "docs(demo): reserve decision id D1",
        "decision-id", "--bolt", str(bolt_of(race.rival)),
    )  # fmt: skip
    code, out, _ = script("decision-id", "--bolt", str(bolt_of(race.b)))
    assert code == 0, out
    assert race.rival_result()["ids"] == ["D1"]
    assert out["ids"] == ["D2"] and out["git"]["pushed"] is True
    assert race.remote_state()["decision_seq"] == 2
    lines = [x for x in race.remote_log() if "| decision-id |" in x]
    assert len(lines) == 2
    who = [(x.split(" | ")[3], x.split(" | ")[4]) for x in lines]
    assert who == [("agent:rival", "D1"), ("agent:bee", "D2")]
    race.assert_in_step()


def test_a_rerun_whose_precondition_fails_leaves_a_clean_clone(
    repos: Repos, tmp_path: Path
) -> None:
    race = Race(repos, tmp_path)
    race.rival_does(
        "docs(demo): park the bolt",
        "close", "--bolt", str(bolt_of(race.rival)), "--status", "archived",
    )  # fmt: skip
    code, out, _ = script("park", "--bolt", str(bolt_of(race.b)), "--note", "mine")
    assert code == 1
    assert race.rival_result()["ok"] is True
    assert out["error"].startswith("the Bolt changed while you were working")
    assert "archived" in out["error"]
    assert race.remote_state()["status"] == "archived"
    assert json.loads((bolt_of(race.b) / "state.json").read_text())["parked"] is None
    assert count(race.remote_log(), "| park |") == 0
    assert count((bolt_of(race.b) / "log.md").read_text().splitlines(), "| park |") == 0
    race.assert_in_step()  # equal to the remote, nothing unpushed, nothing half-applied


def test_an_uncommitted_edit_made_during_the_race_survives_the_rerun(
    repos: Repos, tmp_path: Path
) -> None:
    race = Race(repos, tmp_path)
    notes = bolt_of(race.b) / "inputs" / "notes.md"
    write(notes, "first\n")
    assert script("sync", "--bolt", str(bolt_of(race.b)), "-m", "notes")[0] == 0
    git(race.b, "pull", "-q", "--rebase")
    mine = race.b / "outside.txt"
    race.rival_does(
        "docs(demo): decide hla: skip",
        "decide", "--bolt", str(bolt_of(race.rival)), "--stage", "tdd",
        "--decision", "skip", "--reason", "rival",
        after=f"echo edited-during-the-race > '{notes}'\necho mine > '{mine}'\n",
    )  # fmt: skip
    code, out, _ = decide(race.b, "hla")
    assert code == 0, out
    assert out["git"]["reruns"] == 1
    assert "edited-during-the-race" in notes.read_text()  # a tracked artifact edit
    assert mine.read_text() == "mine\n"  # and a file outside the Bolt
    state = race.remote_state()
    assert state["stages"]["hla"]["decision"] == state["stages"]["tdd"]["decision"] == "skip"
    assert git(race.b, "status", "--porcelain").count("outside.txt") == 1


def test_an_unpushed_artifact_commit_from_the_first_sync_is_not_lost(
    repos: Repos, tmp_path: Path
) -> None:
    race = Race(repos, tmp_path)
    hla = bolt_of(race.b) / "architecture" / "hla.md"
    write(hla, "my draft\n")  # committed by the sync before the command ...
    refuse = tmp_path / "refused.once"
    pre_push = race.b / ".git" / "hooks" / "pre-push"
    pre_push.write_text(f"#!/bin/sh\n[ -e '{refuse}' ] && exit 0\ntouch '{refuse}'\nexit 1\n")
    pre_push.chmod(0o755)  # ... whose first push is refused, so it stays unpushed
    race.rival_does(
        "docs(demo): decide hla: skip",
        "decide", "--bolt", str(bolt_of(race.rival)), "--stage", "tdd",
        "--decision", "skip", "--reason", "rival",
    )  # fmt: skip
    code, out, _ = decide(race.b, "hla")
    assert code == 0, out
    assert out["git_before"]["commit"] and out["git_before"]["not_shared"] is True
    assert out["git"]["reruns"] == 1 and out["git"]["pushed"] is True
    assert hla.read_text() == "my draft\n"
    assert git(race.repos.remote, "show", f"main:bolts/{BOLT_ID}/architecture/hla.md") == "my draft"
    state = race.remote_state()
    assert state["stages"]["hla"]["decision"] == state["stages"]["tdd"]["decision"] == "skip"
    subjects = git(race.repos.remote, "log", "--format=%s", "main").splitlines()
    assert "docs(demo): save work before decide hla: skip" in subjects
    race.assert_in_step()


def test_a_command_that_is_not_safe_to_rerun_keeps_the_old_flow_and_a_new_rule(
    repos: Repos, tmp_path: Path
) -> None:
    race = Race(repos, tmp_path)
    race.rival_does(
        "docs(demo): close the bolt as archived",
        "park", "--bolt", str(bolt_of(race.rival)), "--note", "rival",
    )  # fmt: skip
    code, out, _ = script("close", "--bolt", str(bolt_of(race.b)), "--status", "archived")
    assert code == 6, out  # the rebase stops on state.json: close is never run twice
    assert race.rival_result()["ok"] is True
    rules = [f["message"] for f in out["findings"] if f["path"].endswith("/state.json")]
    assert rules and all("git reset --keep HEAD~1" in r for r in rules)
    assert all("--ours" not in r and "take the team" not in r for r in rules)
    assert "reruns" not in out.get("git", {})


def test_a_rival_that_wins_every_round_ends_with_nothing_applied(
    repos: Repos, tmp_path: Path
) -> None:
    race = Race(repos, tmp_path)
    counter = tmp_path / "rounds"
    rival = " ".join(f"'{p}'" for p in (sys.executable, str(SCRIPT), "park", "--bolt"))
    hook = race.b / ".git" / "hooks" / "post-commit"
    hook.write_text(
        "#!/bin/sh\nunset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE\n"
        '[ "$(git log -1 --format=%s)" = "docs(demo): park the bolt" ] || exit 0\n'
        f"N=$(($(cat '{counter}' 2>/dev/null || echo 0) + 1)); echo $N > '{counter}'\n"
        f"cd '{race.rival}' && AIDLC_ACTOR=rival {rival} '{bolt_of(race.rival)}' "
        '--note "rival $N" >/dev/null 2>&1\n'
    )
    hook.chmod(0o755)
    code, out, _ = script("park", "--bolt", str(bolt_of(race.b)), "--note", "mine")
    assert code == 6, out
    assert "NOT applied" in out["error"] and "run the command again" in out["error"]
    assert counter.read_text().strip() == "4"  # the first run and three re-runs, all beaten
    assert race.remote_state()["parked"]["note"] == "rival 4"
    assert count(race.remote_log(), "| park | - | agent:rival") == 4
    assert "mine" not in (bolt_of(race.b) / "log.md").read_text()
    race.assert_in_step()


def test_a_push_that_did_not_happen_says_so_and_status_counts_it(
    repos: Repos, tmp_path: Path
) -> None:
    assert open_demo(repos.a)[0] == 0
    git(repos.a, "remote", "set-url", "origin", str(tmp_path / "gone.git"))  # unreachable
    code, out, _ = script("park", "--bolt", str(bolt_of(repos.a)), "--note", "n")
    assert code == 0, out
    assert out["git"]["pushed"] is False and out["git"]["not_shared"] is True
    assert any("saved in this clone, not shared yet" in w for w in out["git"]["warnings"])
    text = script("status", "--bolt", str(bolt_of(repos.a)), "--format", "text")[2]
    assert "1 change(s) saved here, not shared yet" in text
    assert script("status", "--bolt", str(bolt_of(repos.a)))[1]["git"]["unshared"] == 1
    text = script("overview", "--root", str(repos.a), "--format", "text")[2]
    assert text.splitlines()[0] == "1 change(s) saved here, not shared yet"
    assert script("overview", "--root", str(repos.a))[1]["unshared"] == 1
    git(repos.a, "remote", "set-url", "origin", str(repos.remote))
    code, out, _ = script("sync", "--bolt", str(bolt_of(repos.a)))
    assert out["git"]["pushed"] is True and out["git"]["not_shared"] is False
    assert (
        "saved here" not in script("status", "--bolt", str(bolt_of(repos.a)), "--format", "text")[2]
    )


def test_without_an_upstream_nothing_is_said_about_unshared_work(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    assert open_demo(tmp_path)[0] == 0
    text = script("status", "--bolt", str(bolt_of(tmp_path)), "--format", "text")[2]
    assert "saved here" not in text and "not shared" not in text
    assert script("status", "--bolt", str(bolt_of(tmp_path)))[1]["git"]["unshared"] is None
    text = script("overview", "--root", str(tmp_path), "--format", "text")[2]
    assert "saved here" not in text
    assert script("overview", "--root", str(tmp_path))[1]["unshared"] is None


def test_an_unconfirmed_decision_reservation_hands_out_no_ids(repos: Repos) -> None:
    """Shared counter or a unit's own: when the sync fails, the caller gets no ids."""
    bolt = base.split_demo(repos)
    git(repos.a, "remote", "set-url", "origin", str(repos.a.parent / "gone.git"))
    head = git(repos.a, "rev-parse", "HEAD")
    code, out, _ = script("decision-id", "--bolt", str(bolt))  # shared: refused before it runs
    assert code == 6 and "cannot confirm the shared decision counter" in out["error"]
    assert "ids" not in out and git(repos.a, "rev-parse", "HEAD") == head
    assert "--provisional" not in out["error"]
    code, out, _ = script("decision-id", "--bolt", str(bolt), "--unit", "u1")  # a unit's own
    assert code == 6 and "the ids were not reserved" in out["error"]
    assert "ids" not in out and "cite_as" not in out
    assert "ids" not in out["result"] and "cite_as" not in out["result"]
    assert out["git"]["not_shared"] is True
    git(repos.a, "remote", "set-url", "origin", str(repos.remote))
    code, out, _ = script("decision-id", "--bolt", str(bolt), "--unit", "u1")
    assert code == 0 and out["ids"] == ["D2"]  # the unconfirmed D1 was never handed out
