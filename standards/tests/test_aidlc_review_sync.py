"""Work that was saved but not shared never becomes a manual conflict (review fixes, H3).

Real clones and a bare remote. A clone goes offline (its remote points nowhere), runs
commands, and meanwhile the team changes the same state file. The next command or `sync`
must set the clashing commands aside and say which, keep everything else, and never
`reset --hard`.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any, cast

import test_aidlc_state_git as base
from test_aidlc_state_git import SCRIPT, Repos, bolt_of, git, open_demo, script, split_demo, write

identity = base.identity  # the fixtures of the git tests, reused as they are
repos = base.repos

NOTES = "architecture/notes.md"


def state_of(clone: Path) -> dict[str, Any]:
    return json.loads((bolt_of(clone) / "state.json").read_text(encoding="utf-8"))


def go_offline(repos: Repos) -> None:
    git(repos.a, "remote", "set-url", "origin", str(repos.a.parent / "gone.git"))


def come_back(repos: Repos) -> None:
    git(repos.a, "remote", "set-url", "origin", str(repos.remote))


def decide(clone: Path, stage: str, *flags: str) -> tuple[int, dict[str, Any], str]:
    return script(
        "decide", "--bolt", str(bolt_of(clone)), "--stage", stage, "--decision", "skip",
        "--reason", f"{stage} not needed", *flags,
    )  # fmt: skip


def team_decides(repos: Repos, stage: str) -> None:
    git(repos.b, "pull", "-q")
    assert decide(repos.b, stage)[0] == 0


def three_offline_commands(repos: Repos) -> None:
    """Open and share a Bolt, then three commands and one artifact, none of it shared."""
    assert open_demo(repos.a)[0] == 0
    git(repos.b, "pull", "-q")
    go_offline(repos)
    assert decide(repos.a, "hla")[0] == 0
    write(bolt_of(repos.a) / NOTES, "my notes\n")
    assert decide(repos.a, "tdd")[0] == 0  # its "before" sync saves the notes in a commit
    assert script("park", "--bolt", str(bolt_of(repos.a)), "--note", "n")[0] == 0
    assert git(repos.a, "rev-list", "--count", "origin/main..HEAD") != "0"


def test_unshared_commands_the_team_clashed_with_are_undone_and_listed(repos: Repos) -> None:
    three_offline_commands(repos)
    team_decides(repos, "requirements-analysis")
    write(repos.a / "README.md", "an uncommitted edit\n")  # work in progress must survive
    come_back(repos)
    code, out, text = decide(repos.a, "domain-design")
    assert code == 0, text
    before = out["git_before"]
    assert before["undone"] == [
        "docs(demo): decide hla: skip",
        "docs(demo): decide tdd: skip",
        "docs(demo): park the bolt",
    ]
    assert any("repeat them" in w and "decide hla: skip" in w for w in before["warnings"])
    state = state_of(repos.a)
    assert state["stages"]["hla"]["decision"] != "skip"  # none of the three is left
    assert state["stages"]["tdd"]["decision"] != "skip" and state["parked"] is None
    assert state["stages"]["requirements-analysis"]["decision"] == "skip"  # the team's
    assert state["stages"]["domain-design"]["decision"] == "skip"  # the command that ran
    log = (bolt_of(repos.a) / "log.md").read_text(encoding="utf-8")
    assert "| park |" not in log and "decide | hla" not in log.replace("  ", " ")
    assert (bolt_of(repos.a) / NOTES).read_text() == "my notes\n"  # the artifact commit stayed
    assert out["git"]["pushed"] is True and out["git"]["not_shared"] is False
    assert git(repos.a, "rev-parse", "HEAD") == git(repos.remote, "rev-parse", "main")
    assert git(repos.a, "rev-list", "--merges", "--count", "HEAD") == "0"
    assert (repos.a / "README.md").read_text() == "an uncommitted edit\n"
    assert "save work before decide tdd" in " ".join(repos.remote_log())
    assert not (repos.a / ".git" / "rebase-merge").exists()


def test_sync_does_the_same_without_a_command(repos: Repos) -> None:
    three_offline_commands(repos)
    team_decides(repos, "requirements-analysis")
    come_back(repos)
    code, out, text = script("sync", "--bolt", str(bolt_of(repos.a)))
    assert code == 0, text
    assert len(out["git"]["undone"]) == 3 and out["git"]["pushed"] is True
    assert state_of(repos.a)["stages"]["hla"]["decision"] != "skip"
    assert git(repos.a, "rev-parse", "HEAD") == git(repos.remote, "rev-parse", "main")


def test_an_offline_command_on_a_units_own_file_is_still_rebased_and_kept(repos: Repos) -> None:
    split_demo(repos)
    go_offline(repos)
    code, out, text = base.decide_unit(repos.a, "u1", "mine")
    assert code == 0, text
    git(repos.b, "pull", "-q")
    assert script("park", "--bolt", str(bolt_of(repos.b)), "--note", "team")[0] == 0
    come_back(repos)
    code, out, text = script("sync", "--bolt", str(bolt_of(repos.a)))
    assert code == 0, text
    assert "undone" not in out["git"] and out["git"]["pushed"] is True
    unit = json.loads(git(repos.remote, "show", f"main:bolts/{base.BOLT_ID}/units/u1/state.json"))
    assert unit["stages"]["functional-design"]["decision"] == "skip"
    assert state_of(repos.a)["parked"]["note"] == "team"


def test_a_commit_that_mixes_a_clashing_state_file_with_others_stops_and_changes_nothing(
    repos: Repos,
) -> None:
    assert open_demo(repos.a)[0] == 0
    git(repos.b, "pull", "-q")
    bolt = bolt_of(repos.a)
    state = state_of(repos.a)
    state["parked"] = {"note": "mixed", "at": "2026-01-05T00:00:00Z"}
    (bolt / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    write(bolt / NOTES, "mine\n")
    git(repos.a, "add", "-A")
    git(repos.a, "commit", "-q", "-m", "state and notes together")
    team_decides(repos, "hla")
    head = git(repos.a, "rev-parse", "HEAD")
    write(repos.a / "README.md", "keep me\n")
    code, out, _ = script("sync", "--bolt", str(bolt))
    assert code == 6 and "state and notes together" in out["error"]
    assert git(repos.a, "rev-parse", "HEAD") == head and (bolt / NOTES).is_file()
    assert (repos.a / "README.md").read_text() == "keep me\n"
    assert not (repos.a / ".git" / "rebase-merge").exists()


def test_a_kept_commit_that_does_not_apply_restores_the_branch_exactly(repos: Repos) -> None:
    assert open_demo(repos.a)[0] == 0
    git(repos.b, "pull", "-q")
    bolt = bolt_of(repos.a)
    write(bolt / "architecture/hla.md", "mine\n")
    git(repos.a, "add", "-A")
    git(repos.a, "commit", "-q", "-m", "my hla")  # kept: not a state commit
    go_offline(repos)
    assert decide(repos.a, "tdd")[0] == 0  # a state commit the team will clash with
    git(repos.b, "pull", "-q")
    write(bolt_of(repos.b) / "architecture/hla.md", "theirs\n")
    git(repos.b, "add", "-A")
    git(repos.b, "commit", "-q", "-m", "team hla")
    assert decide(repos.b, "hla")[0] == 0
    git(repos.b, "push", "-q")
    come_back(repos)
    head = git(repos.a, "rev-parse", "HEAD")
    write(repos.a / "README.md", "keep me\n")
    code, out, _ = script("sync", "--bolt", str(bolt))
    assert code == 6 and "my hla" in out["error"], out
    assert git(repos.a, "rev-parse", "HEAD") == head
    assert (bolt / "architecture/hla.md").read_text() == "mine\n"
    assert state_of(repos.a)["stages"]["tdd"]["decision"] == "skip"  # exactly as it was
    assert (repos.a / "README.md").read_text() == "keep me\n"
    assert not (repos.a / ".git" / "CHERRY_PICK_HEAD").exists()
    assert not (repos.a / ".git" / "rebase-merge").exists()


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("aidlc_state_h3", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    cast(Any, spec.loader).exec_module(module)
    return module


def test_the_race_check_recognises_the_commands_own_commit_by_its_hash(repos: Repos) -> None:
    module = load_module()
    assert open_demo(repos.a)[0] == 0
    git(repos.b, "pull", "-q")
    bolt = bolt_of(repos.a)
    subject = "docs(demo): park the bolt"
    for note in ("first", "second"):  # two commits with the same subject; only the tip is ours
        state = state_of(repos.a)
        state["parked"] = {"note": note, "at": "2026-01-05T00:00:00Z"}
        (bolt / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        git(repos.a, "commit", "-q", "-am", subject)
    first = git(repos.a, "rev-parse", "--short", "HEAD~1")
    team_decides(repos, "hla")
    git(repos.a, "fetch", "-q", "origin", "main")
    ctx = module.GitCtx(top=repos.a, prefix="")
    ref = "refs/remotes/origin/main"
    own = {"commit": git(repos.a, "rev-parse", "--short", "HEAD"), "message": subject}
    assert module.state_race(ctx, ref, f"bolts/{base.BOLT_ID}", dict(own)) != []
    other = {"commit": first, "message": subject}  # same subject, not the tip
    assert module.state_race(ctx, ref, f"bolts/{base.BOLT_ID}", other) == []


def test_the_lock_waits_longer_than_a_git_step_and_says_why() -> None:
    module = load_module()
    assert module.LOCK_WAIT >= 200 > module.GIT_TIMEOUT * 2 - 1
    message = module.lock_busy(Path("/x/.git/aidlc.lock"), 200).message
    assert "waiting for the network" in message


def test_the_lock_lives_in_the_git_directory_even_with_git_writes_off(
    repos: Repos, monkeypatch: Any
) -> None:
    module = load_module()
    assert open_demo(repos.a)[0] == 0
    args = Namespace(command="park", bolt=str(bolt_of(repos.a)), no_git=True)
    path = module.lock_location(args)
    assert path == repos.a.resolve() / ".git" / "aidlc.lock"
    monkeypatch.setenv("AIDLC_GIT", "off")
    args = Namespace(command="park", bolt=str(bolt_of(repos.a)), no_git=False)
    assert module.lock_location(args) == repos.a.resolve() / ".git" / "aidlc.lock"


def test_only_the_scripts_own_temp_files_are_left_out_of_a_commit(repos: Repos) -> None:
    assert open_demo(repos.a)[0] == 0
    bolt = bolt_of(repos.a)
    write(bolt / "notes.tmp", "a real file of mine\n")
    write(bolt / ".state.json.4242.tmp", "{}\n")
    assert script("park", "--bolt", str(bolt), "--note", "n")[0] == 0
    tracked = git(repos.a, "ls-files").splitlines()
    assert f"bolts/{base.BOLT_ID}/notes.tmp" in tracked
    assert not [t for t in tracked if t.endswith(".4242.tmp")]
    assert subprocess.run(["git", "-C", str(repos.a), "status", "--porcelain"], capture_output=True,
                          text=True).stdout.strip() == f"?? bolts/{base.BOLT_ID}/.state.json.4242.tmp"  # fmt: skip
