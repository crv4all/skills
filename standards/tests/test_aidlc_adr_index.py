"""``build_adr_index.py`` turns an ADR registry into a compact index."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts" / "build_adr_index.py"


def adr(number: str, status: str, decision: str = "Use the thing.") -> str:
    return (
        f"# ADR-G{number}: Title {number}\n\n**Status:** {status}\n**Date:** 2025-04-10\n\n---\n\n"
        "## Context\n\nBackground.\n\n"
        f"## Proposed Solution / Decision\n\n{decision}\n\n"
        "## Decision Outcome\n\nNot this.\n"
    )


def make_registry(root: Path, with_git: bool = True) -> Path:
    registry = root / "registry"
    folder = registry / "architecture" / "adrs"
    folder.mkdir(parents=True)
    entries = []
    for number, status in (("001", "Accepted"), ("002", "Proposed"), ("003", "Superseded")):
        name = f"adr-g{number}-title.md"
        (folder / name).write_text(adr(number, status, "Use it. " + "x" * 400), encoding="utf-8")
        entries.append({"path": name, "title": f"ADR-G{number}: Title", "status": status})
    (registry / "adr-manifest.json").write_text(json.dumps(entries), encoding="utf-8")
    if with_git:
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
               "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(root)}  # fmt: skip
        for cmd in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "x"]):
            subprocess.run(
                ["git", "-C", str(registry), *cmd], check=True, env=env, capture_output=True
            )
    return registry


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60
    )


def test_index_has_one_entry_per_adr(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    out = tmp_path / "out" / "index.json"
    done = run("--registry", str(registry), "--out", str(out))
    assert done.returncode == 0, done.stderr
    index = json.loads(out.read_text(encoding="utf-8"))
    assert [a["id"] for a in index["adrs"]] == ["ADR-G001", "ADR-G002", "ADR-G003"]
    first = index["adrs"][0]
    assert first["status"] == "Accepted" and first["binding"] == "binding"
    assert first["date"] == "2025-04-10"
    assert first["path"] == "architecture/adrs/adr-g001-title.md"


def test_decision_is_the_decision_section_cut_at_300_characters(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    out = tmp_path / "index.json"
    run("--registry", str(registry), "--out", str(out))
    decision = json.loads(out.read_text(encoding="utf-8"))["adrs"][0]["decision"]
    assert decision.startswith("Use it.")
    assert len(decision) == 300
    assert "Not this" not in decision


def test_statuses_are_flagged(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    out = tmp_path / "index.json"
    run("--registry", str(registry), "--out", str(out))
    by_id = {a["id"]: a for a in json.loads(out.read_text(encoding="utf-8"))["adrs"]}
    assert by_id["ADR-G002"]["binding"] == "directional" and not by_id["ADR-G002"]["flagged"]
    assert by_id["ADR-G003"]["binding"] == "flagged" and by_id["ADR-G003"]["flagged"]


def test_registry_commit_is_recorded(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    out = tmp_path / "index.json"
    run("--registry", str(registry), "--out", str(out))
    commit = json.loads(out.read_text(encoding="utf-8"))["registry_commit"]
    assert isinstance(commit, str) and len(commit) == 40


def test_registry_is_not_modified(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    before = sorted(
        (p.name, p.read_bytes())
        for p in registry.rglob("*")
        if p.is_file() and ".git" not in p.parts
    )
    run("--registry", str(registry), "--out", str(tmp_path / "index.json"))
    after = sorted(
        (p.name, p.read_bytes())
        for p in registry.rglob("*")
        if p.is_file() and ".git" not in p.parts
    )
    assert before == after


def test_missing_manifest_exits_3(tmp_path: Path) -> None:
    done = run("--registry", str(tmp_path), "--out", str(tmp_path / "i.json"))
    assert done.returncode == 3


def test_malformed_manifest_exits_4(tmp_path: Path) -> None:
    registry = make_registry(tmp_path, with_git=False)
    (registry / "adr-manifest.json").write_text("{not json", encoding="utf-8")
    assert run("--registry", str(registry), "--out", str(tmp_path / "i.json")).returncode == 4


def test_listed_but_missing_file_is_a_finding(tmp_path: Path) -> None:
    registry = make_registry(tmp_path, with_git=False)
    manifest = json.loads((registry / "adr-manifest.json").read_text(encoding="utf-8"))
    manifest.append({"path": "adr-g099-gone.md", "title": "ADR-G099", "status": "Accepted"})
    (registry / "adr-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "i.json"
    done = run("--registry", str(registry), "--out", str(out))
    assert done.returncode == 1
    assert len(json.loads(out.read_text(encoding="utf-8"))["adrs"]) == 3


# --- --refresh -------------------------------------------------------------------------

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def g(path: Path, *args: str) -> str:
    import os

    done = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True, text=True, env={**os.environ, **GIT_ENV}, check=True,
    )  # fmt: skip
    return done.stdout.strip()


def remote_setup(tmp: Path) -> tuple[Path, Path]:
    """(registry clone with an origin, a second clone used to push upstream changes)."""
    seed = make_registry(tmp)
    seed.rename(tmp / "seed")
    seed = tmp / "seed"
    g(seed, "branch", "-M", "main")
    bare = tmp / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(bare)], check=True)
    for name in ("reg", "other"):
        subprocess.run(["git", "clone", "-q", str(bare), str(tmp / name)], check=True)
    return tmp / "reg", tmp / "other"


def push_change(other: Path) -> None:
    """Upstream accepts ADR-G002 and adds ADR-G004."""
    folder = other / "architecture" / "adrs"
    two = folder / "adr-g002-title.md"
    two.write_text(two.read_text().replace("Proposed", "Accepted"), encoding="utf-8")
    (folder / "adr-g004-title.md").write_text(adr("004", "Proposed"), encoding="utf-8")
    manifest = other / "adr-manifest.json"
    entries = json.loads(manifest.read_text())
    entries.append({"path": "adr-g004-title.md", "title": "ADR-G004: Title", "status": "Proposed"})
    manifest.write_text(json.dumps(entries), encoding="utf-8")
    g(other, "add", ".")
    g(other, "commit", "-q", "-m", "change")
    g(other, "push", "-q", "origin", "main")


def test_refresh_fast_forwards_a_clean_registry_and_reports_what_moved(tmp_path: Path) -> None:
    reg, other = remote_setup(tmp_path)
    out = tmp_path / "index.json"
    assert run("--registry", str(reg), "--out", str(out)).returncode == 0
    old = json.loads(out.read_text())["registry_commit"]
    push_change(other)
    done = run("--registry", str(reg), "--out", str(out), "--refresh")
    refresh = json.loads(done.stdout)["refresh"]
    new = g(reg, "rev-parse", "HEAD")
    assert refresh["fast_forwarded"] and refresh["old_registry_commit"] == old
    assert refresh["new_registry_commit"] == new == json.loads(out.read_text())["registry_commit"]
    assert refresh["added"] == ["ADR-G004"]
    assert refresh["status_changed"] == ["ADR-G002: Proposed -> Accepted"]
    assert old in done.stderr and new in done.stderr and "ADR-G004" in done.stderr


def test_refresh_leaves_a_dirty_registry_alone_and_says_how_far_behind(tmp_path: Path) -> None:
    reg, other = remote_setup(tmp_path)
    push_change(other)
    (reg / "scratch.txt").write_text("mine", encoding="utf-8")
    before = g(reg, "rev-parse", "HEAD")
    done = run("--registry", str(reg), "--out", str(tmp_path / "i.json"), "--refresh")
    refresh = json.loads(done.stdout)["refresh"]
    assert g(reg, "rev-parse", "HEAD") == before and not refresh["fast_forwarded"]
    assert refresh["behind"] == 1 and "1 commits behind" in done.stderr
    assert (reg / "scratch.txt").read_text() == "mine"


def test_refresh_does_not_touch_a_diverged_registry(tmp_path: Path) -> None:
    reg, other = remote_setup(tmp_path)
    push_change(other)
    (reg / "local.md").write_text("local", encoding="utf-8")
    g(reg, "add", ".")
    g(reg, "commit", "-q", "-m", "local")
    before = g(reg, "rev-parse", "HEAD")
    done = run("--registry", str(reg), "--out", str(tmp_path / "i.json"), "--refresh")
    assert g(reg, "rev-parse", "HEAD") == before
    assert "diverged" in done.stderr and "commits behind" in done.stderr


def test_refresh_on_a_registry_that_is_up_to_date_changes_nothing(tmp_path: Path) -> None:
    reg, _other = remote_setup(tmp_path)
    done = run("--registry", str(reg), "--out", str(tmp_path / "i.json"), "--refresh")
    refresh = json.loads(done.stdout)["refresh"]
    assert done.returncode == 0 and refresh["behind"] == 0 and not refresh["fast_forwarded"]
    assert refresh["status_changed"] == []


def test_without_refresh_the_output_is_unchanged_and_nothing_is_fetched(tmp_path: Path) -> None:
    reg, other = remote_setup(tmp_path)
    push_change(other)
    before = g(reg, "rev-parse", "HEAD")
    done = run("--registry", str(reg), "--out", str(tmp_path / "i.json"))
    assert "refresh" not in json.loads(done.stdout) and g(reg, "rev-parse", "HEAD") == before


def test_an_https_registry_remote_gets_the_set_url_fix(tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    url = "https://crv4all@dev.azure.com/crv4all/Cloudforce%20Team%20Data/_git/adr-registry"
    g(registry, "remote", "add", "origin", url)
    ssh = "git@ssh.dev.azure.com:v3/crv4all/Cloudforce%20Team%20Data/adr-registry"
    done = run("--registry", str(registry), "--out", str(tmp_path / "i.json"))
    assert f"remote set-url origin {ssh}" in done.stderr
