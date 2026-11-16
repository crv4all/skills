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
