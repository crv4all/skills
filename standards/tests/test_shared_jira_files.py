"""The Jira skills carry byte-identical copies of their shared files.

``crv-create-jira-epic`` and ``crv-create-jira-story`` each ship their own copy
of the setup script and the two shared reference files. That duplication is
deliberate: ``install.sh`` installs and flattens one skill at a time, so a skill
that reached for a sibling's files would be broken on every machine that
installed only one of them -- and broken silently, since nothing would notice
the absence until a run failed.

The cost of that choice is drift. A fix applied to one copy and forgotten in the
other is invisible to every other check in this repository, which is what this
test exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSES = REPO_ROOT / "skills" / "processes"

SKILLS = ("crv-create-jira-epic", "crv-create-jira-story")

#: Paths relative to a skill root that must be identical across both skills.
SHARED = (
    "scripts/jira_setup.py",
    "references/jira-setup.md",
    "references/field-resolution.md",
)


@pytest.mark.parametrize("relative", SHARED)
def test_shared_file_is_identical_across_skills(relative: str) -> None:
    paths = [PROCESSES / skill / relative for skill in SKILLS]

    for path in paths:
        assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"

    first, second = (path.read_bytes() for path in paths)
    assert first == second, (
        f"{paths[0].relative_to(REPO_ROOT)} and {paths[1].relative_to(REPO_ROOT)} "
        "have drifted. These files are duplicated on purpose so each skill installs "
        "standalone; a change to one must be copied to the other."
    )
