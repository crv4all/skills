"""Every skill on disk is listed in the documents that advertise it.

``CATALOG.md`` is generated, so drift there is already caught by
``build_catalog.py --check``. The hand-written places are not, and they are the
ones a reader actually starts from: the README table is the first list of skills
anybody sees, and a skill missing from it is a skill nobody knows exists.

Two Jira skills shipped and sat unlisted in the README for four commits, which
is what this test exists to prevent. It is deliberately mechanical: the rule
"update the documentation too" is worth nothing if the only thing enforcing it
is whether the author remembered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills"
README = REPO_ROOT / "README.md"
CATALOG = REPO_ROOT / "CATALOG.md"

LAYERS = ("utilities", "knowledge", "patterns", "processes")


def discover_skills() -> list[tuple[str, str]]:
    """Return ``(layer, name)`` for every skill directory holding a SKILL.md."""
    found: list[tuple[str, str]] = []
    for layer in LAYERS:
        layer_dir = SKILLS_ROOT / layer
        if not layer_dir.is_dir():
            continue
        for candidate in sorted(layer_dir.iterdir()):
            if (candidate / "SKILL.md").is_file():
                found.append((layer, candidate.name))
    return found


SKILLS = discover_skills()


def test_at_least_one_skill_was_discovered() -> None:
    """Guards the guard: a broken walk would make every test below vacuous."""
    assert SKILLS, f"no skills found under {SKILLS_ROOT.relative_to(REPO_ROOT)}"


@pytest.mark.parametrize(("layer", "name"), SKILLS, ids=[n for _, n in SKILLS])
def test_skill_is_listed_in_readme(layer: str, name: str) -> None:
    readme = README.read_text(encoding="utf-8")
    link = f"skills/{layer}/{name}/SKILL.md"
    assert link in readme, (
        f"{name} is not linked from README.md. Add a row to the skills table "
        f"linking {link}. See AGENTS.md, 'Documentation is part of the change'."
    )
    assert f"`{name}`" in readme, (
        f"README.md links {name} but does not name it in backticks. The table "
        "rows use ``[`crv-name`](path)`` so the name is greppable."
    )


@pytest.mark.parametrize(("layer", "name"), SKILLS, ids=[n for _, n in SKILLS])
def test_skill_is_listed_in_catalog(layer: str, name: str) -> None:
    """Redundant with ``build_catalog.py --check``, and cheap enough to keep.

    The catalogue check fails on drift between frontmatter and the generated
    file. This fails if the generator itself stopped emitting a skill, which the
    drift check cannot see because it compares the generator against itself.
    """
    catalog = CATALOG.read_text(encoding="utf-8")
    assert f"`{name}`" in catalog, (
        f"{name} is absent from CATALOG.md. Regenerate it with "
        "`uv run standards/scripts/build_catalog.py --write` and commit the result."
    )
