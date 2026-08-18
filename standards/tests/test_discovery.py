"""Discovery agrees with the layout rules, and reports what it cannot see."""

from __future__ import annotations

from lib.discovery import LAYERS, discover, resolve_targets


def test_finds_a_skill(skill_repo, make_skill):
    make_skill(name="crv-alpha", layer="patterns")
    skills, strays = discover(skill_repo)
    assert [s.name for s in skills] == ["crv-alpha"]
    assert skills[0].layer == "patterns"
    assert skills[0].rel_skill_md == "skills/patterns/crv-alpha/SKILL.md"
    assert strays == []


def test_reports_miscased_skill_file(skill_repo):
    """Works on macOS, invisible on Linux CI. Worth an explicit message."""
    directory = skill_repo / "skills" / "processes" / "crv-oops"
    directory.mkdir(parents=True)
    (directory / "skill.md").write_text("---\nname: crv-oops\n---\n", encoding="utf-8")
    skills, strays = discover(skill_repo)
    assert skills == []
    assert len(strays) == 1
    assert "case-sensitive" in strays[0].reason


def test_reports_skill_nested_too_deep(skill_repo):
    nested = skill_repo / "skills" / "processes" / "group" / "crv-deep"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\nname: crv-deep\n---\n", encoding="utf-8")
    skills, strays = discover(skill_repo)
    assert skills == []
    assert any("exactly two levels" in stray.reason for stray in strays)


def test_reports_unknown_layer_directory(skill_repo):
    (skill_repo / "skills" / "misc" / "crv-x").mkdir(parents=True)
    _, strays = discover(skill_repo)
    assert any("not one of the four layers" in stray.reason for stray in strays)


def test_layer_filter(skill_repo, make_skill):
    make_skill(name="crv-a", layer="patterns")
    make_skill(name="crv-b", layer="processes")
    skills, _ = discover(skill_repo, layers=["processes"])
    assert [s.name for s in skills] == ["crv-b"]


def test_resolve_targets_accepts_directory_or_skill_md(skill_repo, make_skill):
    make_skill(name="crv-a", layer="patterns")
    by_dir, unresolved = resolve_targets(skill_repo, ["skills/patterns/crv-a"])
    by_file, _ = resolve_targets(skill_repo, ["skills/patterns/crv-a/SKILL.md"])
    assert unresolved == []
    assert by_dir == by_file


def test_resolve_targets_reports_unknown(skill_repo):
    _, unresolved = resolve_targets(skill_repo, ["skills/patterns/nope"])
    assert unresolved == ["skills/patterns/nope"]


def test_reference_files_sorted(skill_repo, make_skill):
    skill = make_skill(name="crv-a", layer="patterns")
    (skill / "references").mkdir()
    for name in ("b.md", "a.md"):
        (skill / "references" / name).write_text("x\n", encoding="utf-8")
    skills, _ = discover(skill_repo)
    assert [p.name for p in skills[0].reference_files()] == ["a.md", "b.md"]


def test_layers_are_the_four_documented_ones():
    assert LAYERS == ("utilities", "knowledge", "patterns", "processes")
