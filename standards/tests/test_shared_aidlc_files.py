"""The AI-DLC skills carry byte-identical copies of their shared files.

``install.sh`` installs one skill at a time, so a stage skill cannot reach the
entry skill's scripts or rules; each ships its own copy. The canonical copy of
the process files is the one in ``crv-aidlc``; ``validate_doc.py`` is shared by
the HLA and TDD skills and the HLA copy is canonical.

A fix applied to one copy and forgotten in another is invisible to every other
check, and the drift shows up only when a gate or a validator behaves
differently depending on which skill ran it. Skills that do not exist yet are
skipped, so the guard tightens as each skill lands.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSES = REPO_ROOT / "skills" / "processes"

STAGE_SKILLS = (
    "crv-aidlc-reverse-engineering",
    "crv-aidlc-hla",
    "crv-aidlc-tdd",
    "crv-aidlc-inception",
    "crv-aidlc-construction",
    "crv-aidlc-operation",
)

#: (relative path, canonical skill, skills that must carry an identical copy)
SHARED = (
    ("references/core-rules.md", "crv-aidlc", STAGE_SKILLS),
    ("scripts/aidlc_state.py", "crv-aidlc", STAGE_SKILLS),
    ("assets/stages.json", "crv-aidlc", STAGE_SKILLS),
    (
        "scripts/lint_questions.py",
        "crv-aidlc",
        (
            "crv-aidlc-reverse-engineering",
            "crv-aidlc-hla",
            "crv-aidlc-tdd",
            "crv-aidlc-inception",
            "crv-aidlc-construction",
            "crv-aidlc-operation",
        ),
    ),
    # The last Inception gate runs this check, so the skill that gates Inception carries it.
    ("scripts/check_traceability.py", "crv-aidlc", ("crv-aidlc-inception",)),
    ("scripts/validate_doc.py", "crv-aidlc-hla", ("crv-aidlc-tdd",)),
)

CASES = [(rel, canonical, copy) for rel, canonical, copies in SHARED for copy in copies]


def exists(skill: str) -> bool:
    return (PROCESSES / skill / "SKILL.md").is_file()


@pytest.mark.parametrize(
    ("relative", "canonical", "copy"), CASES, ids=[f"{c}:{r}" for r, _, c in CASES]
)
def test_shared_file_is_identical(relative: str, canonical: str, copy: str) -> None:
    if not exists(canonical) or not exists(copy):
        pytest.skip(f"{canonical} or {copy} does not exist yet")
    source = PROCESSES / canonical / relative
    target = PROCESSES / copy / relative
    assert source.is_file(), f"{source.relative_to(REPO_ROOT)} is missing"
    assert target.is_file(), f"{target.relative_to(REPO_ROOT)} is missing"
    assert source.read_bytes() == target.read_bytes(), (
        f"{target.relative_to(REPO_ROOT)} has drifted from "
        f"{source.relative_to(REPO_ROOT)}. These files are duplicated on purpose so each "
        "skill installs standalone; copy the canonical file over the stale one."
    )


def test_the_guard_covers_at_least_one_pair() -> None:
    """Guards the guard: with every pair skipped, the identity test would prove nothing."""
    assert any(exists(canonical) and exists(copy) for _, canonical, copy in CASES)
