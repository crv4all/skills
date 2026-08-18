"""CATALOG.md is reproducible, and drift fails."""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_catalog.py"

GENERATED = ("CATALOG.md",)


@pytest.fixture
def catalog(run_script, skill_repo):
    def _catalog(*args: str):
        return run_script(SCRIPT, ["--root", str(skill_repo), *args])

    return _catalog


def test_write_creates_the_catalog(make_skill, catalog, skill_repo):
    make_skill(name="crv-alpha", layer="patterns")
    run = catalog("--write")
    assert run.returncode == 0, run.stderr
    for rel in GENERATED:
        assert (skill_repo / rel).is_file(), rel


def test_write_then_check_is_clean(make_skill, catalog):
    make_skill(name="crv-alpha", layer="patterns")
    catalog("--write")
    assert catalog("--check").returncode == 0


def test_check_detects_a_hand_edit(make_skill, catalog, skill_repo):
    make_skill(name="crv-alpha", layer="patterns")
    catalog("--write")
    target = skill_repo / "CATALOG.md"
    target.write_text(target.read_text(encoding="utf-8") + "\nhand edit\n", encoding="utf-8")
    run = catalog("--check")
    assert run.returncode == 1
    assert "CATALOG.md" in run.stderr


def test_check_detects_a_new_skill(make_skill, catalog):
    make_skill(name="crv-alpha", layer="patterns")
    catalog("--write")
    make_skill(name="crv-beta", layer="knowledge")
    assert catalog("--check").returncode == 1


def test_write_and_check_are_mutually_exclusive(catalog):
    run = catalog("--write", "--check")
    assert run.returncode == 2
    assert "mutually exclusive" in run.stderr


def test_generation_is_deterministic(make_skill, catalog, skill_repo):
    make_skill(name="crv-alpha", layer="patterns")
    make_skill(name="crv-beta", layer="knowledge")
    catalog("--write")
    first = {rel: (skill_repo / rel).read_text(encoding="utf-8") for rel in GENERATED}
    catalog("--write")
    for rel, content in first.items():
        assert (skill_repo / rel).read_text(encoding="utf-8") == content, rel


def test_refuses_to_generate_from_a_broken_skill(skill_repo, catalog):
    directory = skill_repo / "skills" / "processes" / "crv-broken"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text("no frontmatter\n", encoding="utf-8")
    run = catalog("--write")
    assert run.returncode == 4
    assert "validate_frontmatter" in run.stderr


def test_catalog_carries_the_generated_banner(make_skill, catalog, skill_repo):
    make_skill(name="crv-alpha", layer="patterns")
    catalog("--write")
    assert "Do not edit by hand" in (skill_repo / "CATALOG.md").read_text(encoding="utf-8")


def test_repository_generated_files_are_current(run_script, repo_root):
    run = run_script(SCRIPT, ["--root", str(repo_root), "--check"])
    assert run.returncode == 0, run.stderr
