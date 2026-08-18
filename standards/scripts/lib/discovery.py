"""Locate skills on disk.

Every validator agrees on what a skill *is* by importing from here, so that a
skill cannot be valid to one check and invisible to another.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Union

#: The four capability layers, in the order they are presented to readers.
#: See skills/README.md for what each one means.
LAYERS: tuple[str, ...] = ("utilities", "knowledge", "patterns", "processes")

SKILL_FILENAME = "SKILL.md"
SKILLS_DIRNAME = "skills"

#: Directories under a skill that carry loadable content, in the order the
#: Agent Skills specification lists them.
CONVENTIONAL_SUBDIRS: tuple[str, ...] = ("scripts", "references", "assets")


@dataclass(frozen=True)
class Skill:
    """A single skill directory that contains a SKILL.md."""

    #: Directory name, which must equal the frontmatter ``name``.
    name: str
    #: Parent directory name, which must equal ``metadata.layer``.
    layer: str
    #: Absolute path to the skill directory.
    path: Path
    #: Absolute path to the SKILL.md.
    skill_md: Path
    #: Repository root the skill was discovered from.
    root: Path

    @property
    def rel_path(self) -> str:
        """Repo-relative POSIX path of the skill directory."""
        return self.path.relative_to(self.root).as_posix()

    @property
    def rel_skill_md(self) -> str:
        """Repo-relative POSIX path of the SKILL.md."""
        return self.skill_md.relative_to(self.root).as_posix()

    def reference_files(self) -> list[Path]:
        """Markdown files under ``references/``, sorted for stable output."""
        references = self.path / "references"
        if not references.is_dir():
            return []
        return sorted(p for p in references.rglob("*.md") if p.is_file())


@dataclass(frozen=True)
class Stray:
    """Something under ``skills/`` that looks like a skill but is not one.

    Reported rather than ignored: a directory holding a lowercase ``skill.md``,
    or a skill nested one level too deep, is invisible to every harness while
    looking perfectly fine in a file tree.
    """

    path: Path
    reason: str


def repo_root(start: Union[Path, None] = None) -> Path:
    """Find the repository root.

    Walks up from ``start`` (default: this file) looking for a directory that
    holds both ``skills/`` and ``standards/``. Falls back to the known layout
    of this file, ``standards/scripts/lib/discovery.py``, so the scripts work
    when copied into a checkout without git metadata.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / SKILLS_DIRNAME).is_dir() and (candidate / "standards").is_dir():
            return candidate
    return Path(__file__).resolve().parents[3]


def discover(
    root: Path, layers: Union[Iterable[str], None] = None
) -> tuple[list[Skill], list[Stray]]:
    """Return every skill under ``root/skills``, plus anything suspicious.

    Args:
        root: repository root.
        layers: restrict to these layer names. ``None`` means all four.

    Returns:
        ``(skills, strays)``, both sorted by path.
    """
    wanted = tuple(layers) if layers is not None else LAYERS
    skills: list[Skill] = []
    strays: list[Stray] = []

    skills_dir = root / SKILLS_DIRNAME
    if not skills_dir.is_dir():
        return skills, strays

    for entry in sorted(skills_dir.iterdir()):
        if entry.is_file():
            continue
        if entry.name.startswith("."):
            continue
        if entry.name not in LAYERS:
            strays.append(
                Stray(
                    entry,
                    f"{entry.name!r} is not one of the four layers "
                    f"({', '.join(LAYERS)}); nothing under it will be discovered",
                )
            )
            continue
        if entry.name not in wanted:
            continue

        for child in sorted(entry.iterdir()):
            if child.is_file():
                continue
            if child.name.startswith("."):
                continue
            skill_md = child / SKILL_FILENAME
            # Case-exact on purpose. macOS and Windows filesystems are
            # case-insensitive, so `skill_md.is_file()` happily matches
            # `skill.md` -- and then Linux CI, and every Linux agent runtime,
            # does not see the skill at all. Compare against the real entry
            # names so discovery gives the same answer everywhere.
            if skill_md.is_file() and _has_exact_entry(child, SKILL_FILENAME):
                skills.append(
                    Skill(
                        name=child.name,
                        layer=entry.name,
                        path=child,
                        skill_md=skill_md,
                        root=root,
                    )
                )
                continue
            strays.append(Stray(child, _explain_missing_skill_md(child)))

    return skills, strays


def _has_exact_entry(directory: Path, filename: str) -> bool:
    """True only when ``filename`` matches an entry byte for byte."""
    try:
        return any(entry.name == filename for entry in directory.iterdir())
    except OSError:
        return False


def _explain_missing_skill_md(directory: Path) -> str:
    """Say *why* a directory under a layer is not a skill, specifically."""
    miscased = [p.name for p in directory.iterdir() if p.name.lower() == "skill.md"]
    if miscased:
        return (
            f"contains {miscased[0]!r} but the filename must be exactly {SKILL_FILENAME!r}; "
            "the match is case-sensitive on Linux CI even when it works on macOS"
        )
    nested = sorted(p for p in directory.glob("*/" + SKILL_FILENAME) if p.is_file())
    if nested:
        relative = nested[0].parent.name
        return (
            f"has no {SKILL_FILENAME} of its own but {relative}/ below it does; skills live at "
            "skills/<layer>/<name>/, exactly two levels under skills/"
        )
    return f"has no {SKILL_FILENAME}; either add one or remove the directory"


def resolve_targets(root: Path, targets: Iterable[str]) -> tuple[list[Skill], list[str]]:
    """Map user-supplied paths to skills.

    Accepts a skill directory or a path to a SKILL.md, so that a pre-commit
    hook can pass whichever it has. Returns ``(skills, unresolved)``.
    """
    all_skills, _ = discover(root)
    by_path = {skill.path.resolve(): skill for skill in all_skills}

    selected: list[Skill] = []
    unresolved: list[str] = []
    for target in targets:
        candidate = Path(target)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        if candidate.name == SKILL_FILENAME:
            candidate = candidate.parent
        skill = by_path.get(candidate)
        if skill is None:
            unresolved.append(target)
        elif skill not in selected:
            selected.append(skill)
    return selected, unresolved
