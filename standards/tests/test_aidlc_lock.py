"""The checkout-level lock of ``aidlc_state.py``.

One state-changing command at a time per planning checkout, for its whole run: the
sync before, the command, the sync after. The lock is an ``flock`` that the operating
system frees when the holder dies, so there is no stale lock and no expiry.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest
import test_aidlc_state_git as base
from test_aidlc_state_git import SCRIPT, Repos, bolt_of, git, open_demo, script

identity = base.identity  # the fixtures of the git tests, reused as they are
repos = base.repos

needs_flock = pytest.mark.skipif(sys.platform == "win32", reason="flock is not available")

HOLD = (
    "import fcntl, sys, time\n"
    "fd = open(sys.argv[1], 'a')\n"
    "fcntl.flock(fd, fcntl.LOCK_EX)\n"
    "sys.stdout.write('held\\n'); sys.stdout.flush()\n"
    "time.sleep(120)\n"
)


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("aidlc_state_lock_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    cast(Any, spec.loader).exec_module(module)
    return module


def hold_lock(path: Path) -> subprocess.Popen[str]:
    proc = subprocess.Popen(
        [sys.executable, "-c", HOLD, str(path)], stdout=subprocess.PIPE, text=True
    )
    assert proc.stdout and proc.stdout.readline().strip() == "held"
    return proc


@needs_flock
def test_two_sessions_on_two_bolts_in_one_checkout_all_succeed(repos: Repos) -> None:
    assert open_demo(repos.a)[0] == 0
    code, out, _ = script(
        "open", "--root", str(repos.a), "--slug", "other", "--title", "Other",
        "--intent", "Second", "--date", "2026-01-06",
    )  # fmt: skip
    assert code == 0, out
    bolts = [bolt_of(repos.a), repos.a / "bolts" / "2026-01-06-other"]
    codes: dict[str, list[int]] = {}
    rounds = 6

    def work(bolt: Path) -> None:
        codes[bolt.name] = [
            script("park", "--bolt", str(bolt), "--note", f"{bolt.name} {n}")[0]
            for n in range(rounds)
        ]

    threads = [threading.Thread(target=work, args=(b,)) for b in bolts]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert codes == {b.name: [0] * rounds for b in bolts}
    for bolt in bolts:
        lines = [x for x in (bolt / "log.md").read_text().splitlines() if "| park |" in x]
        state = json.loads((bolt / "state.json").read_text())
        assert len(lines) == rounds
        assert lines[-1].endswith(f"{bolt.name} {rounds - 1}")
        assert state["parked"]["note"] == f"{bolt.name} {rounds - 1}"
    assert git(repos.a, "status", "--porcelain") == ""
    assert not (repos.a / ".git" / "rebase-merge").exists()
    assert git(repos.a, "rev-parse", "HEAD") == git(repos.remote, "rev-parse", "main")


@needs_flock
def test_the_lock_lives_in_the_git_directory_and_times_out_with_a_clear_message(
    repos: Repos, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert open_demo(repos.a)[0] == 0
    lock = repos.a / ".git" / "aidlc.lock"
    assert lock.is_file()
    assert not (repos.a / ".aidlc.lock").exists()
    monkeypatch.setenv("AIDLC_LOCK_WAIT", "0.6")
    holder = hold_lock(lock)
    try:
        started = time.monotonic()
        code, out, _ = script("park", "--bolt", str(bolt_of(repos.a)), "--note", "x")
        assert code == 1 and time.monotonic() - started < 10
        assert "another session in this checkout is still working" in out["error"]
        assert str(lock) in out["error"]
        assert script("status", "--bolt", str(bolt_of(repos.a)))[0] == 0  # reads take no lock
        assert script("sync", "--bolt", str(bolt_of(repos.a)))[0] == 1  # sync does
    finally:
        holder.kill()
        holder.wait()
    assert script("park", "--bolt", str(bolt_of(repos.a)), "--note", "x")[0] == 0


@needs_flock
def test_a_holder_killed_with_sigkill_does_not_delay_the_next_command(
    repos: Repos, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert open_demo(repos.a)[0] == 0
    holder = hold_lock(repos.a / ".git" / "aidlc.lock")
    os.kill(holder.pid, signal.SIGKILL)
    holder.wait()
    monkeypatch.setenv("AIDLC_LOCK_WAIT", "5")  # a stale lock would burn all of it
    started = time.monotonic()
    code, out, _ = script("park", "--bolt", str(bolt_of(repos.a)), "--note", "x")
    assert code == 0, out
    assert time.monotonic() - started < 4.5


@needs_flock
def test_without_git_the_lock_sits_at_the_planning_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert open_demo(tmp_path, "--no-git")[0] == 0
    monkeypatch.setenv("AIDLC_LOCK_WAIT", "0.5")
    holder = hold_lock(tmp_path / ".aidlc.lock")
    try:
        code, out, _ = script("park", "--bolt", str(bolt_of(tmp_path)), "--note", "x")
        assert code == 1 and str(tmp_path / ".aidlc.lock") in out["error"]
    finally:
        holder.kill()
        holder.wait()
    assert script("park", "--bolt", str(bolt_of(tmp_path)), "--note", "x")[0] == 0
    assert not (tmp_path / ".aidlc.lock").exists()  # removed after use: it never shows in git


def test_the_fallback_lock_takes_leaves_and_takes_over(tmp_path: Path) -> None:
    mod = load_module()
    path = tmp_path / "x.lock"
    with mod.fallback_lock(path, 1.0):
        assert path.is_file()
        with pytest.raises(mod.Fail) as busy, mod.fallback_lock(path, 0.3):
            pass
        assert "another session in this checkout" in busy.value.message
    assert not path.exists()
    path.write_text("left by a crash", encoding="utf-8")
    old = time.time() - 600
    os.utime(path, (old, old))
    with mod.fallback_lock(path, 1.0):
        assert path.is_file()
    assert not path.exists()


def test_the_checkout_lock_uses_the_fallback_without_fcntl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = load_module()
    monkeypatch.setattr(mod, "_fcntl", None)
    path = tmp_path / "y.lock"
    with mod.checkout_lock(path):
        assert path.is_file()
    assert not path.exists()
