"""The AI-DLC skills must stay cheap to load: rule tokens per stage session are budgeted.

Tokens are estimated as bytes divided by four. The limits come from the budget
table in the process specification; a skill that does not exist yet is skipped,
not failed, so the table can be enforced as each skill lands.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSES = REPO_ROOT / "skills" / "processes"
STATE = PROCESSES / "crv-aidlc" / "scripts" / "aidlc_state.py"

RESUME_DIGEST_LIMIT = 500
CONSTRUCTION_LIMIT = 2_500
DISCOVERY_AND_INCEPTION_LIMIT = 6_000
HLA_LIMIT = 8_000


def tokens(*paths: Path) -> int:
    return sum(path.stat().st_size for path in paths) // 4


def skill_or_skip(name: str) -> Path:
    path = PROCESSES / name
    if not (path / "SKILL.md").is_file():
        pytest.skip(f"{name} does not exist yet")
    return path


def stage_references(skill: Path) -> list[Path]:
    refs = sorted((skill / "references").glob("*.md"))
    return [r for r in refs if r.name not in {"core-rules.md", "README.md"}]


def test_entry_skill_fits_the_inception_budget() -> None:
    skill = skill_or_skip("crv-aidlc")
    total = tokens(skill / "SKILL.md", skill / "references" / "core-rules.md")
    assert total <= DISCOVERY_AND_INCEPTION_LIMIT, f"{total} tokens"


def test_resume_digest_is_within_budget(tmp_path: Path) -> None:
    skill_or_skip("crv-aidlc")
    args = ["--root", str(tmp_path), "--slug", "budget", "--title", "T" * 80, "--intent", "I" * 160]
    done = subprocess.run(
        [sys.executable, str(STATE), "open", *args], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr
    bolt = json.loads(done.stdout)["bolt"]
    shown = subprocess.run(
        [sys.executable, str(STATE), "status", "--bolt", bolt, "--format", "text"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert len(shown.stdout.encode("utf-8")) // 4 <= RESUME_DIGEST_LIMIT
    assert len(shown.stdout.splitlines()) <= 20


@pytest.mark.parametrize("name", ["crv-aidlc-construction"])
def test_construction_stage_sessions(name: str) -> None:
    skill = skill_or_skip(name)
    for ref in stage_references(skill):
        total = tokens(skill / "SKILL.md", skill / "references" / "core-rules.md", ref)
        assert total <= CONSTRUCTION_LIMIT, f"{name}/{ref.name}: {total} tokens"


@pytest.mark.parametrize(
    "name", ["crv-aidlc-inception", "crv-aidlc-reverse-engineering", "crv-aidlc-operation"]
)
def test_discovery_and_inception_stage_sessions(name: str) -> None:
    skill = skill_or_skip(name)
    for ref in stage_references(skill):
        total = tokens(skill / "SKILL.md", skill / "references" / "core-rules.md", ref)
        assert total <= DISCOVERY_AND_INCEPTION_LIMIT, f"{name}/{ref.name}: {total} tokens"


#: What one run of each step loads besides SKILL.md and core-rules.md, as the
#: step tables in the two SKILL.md files say. A reference no step names would
#: escape the budget, so test_every_reference_is_loaded_by_a_step checks that too.
STEP_LOADS = {
    "crv-aidlc-hla": (
        HLA_LIMIT,
        {
            "bootstrap and ask A": ["references/layers-a.md"],
            "analyse A, ask B": ["references/layers-a.md", "references/layers-b.md"],
            "analyse B, ask C": ["references/layers-b.md", "references/layers-c.md"],
            "analyse C": ["references/layers-c.md"],
            "generate": ["references/generation-rules.md", "assets/hla-template.md"],
            "refine or sign off": ["references/generation-rules.md"],
        },
    ),
    "crv-aidlc-tdd": (
        DISCOVERY_AND_INCEPTION_LIMIT,
        {
            "applicability and ask": ["references/sections.md"],
            "analyse": ["references/sections.md"],
            "produce": ["references/writing.md", "assets/tdd-template.md"],
            "refine or sign off": ["references/writing.md"],
        },
    ),
}

STEP_CASES = [
    (name, step, files, limit)
    for name, (limit, steps) in STEP_LOADS.items()
    for step, files in steps.items()
]


@pytest.mark.parametrize(
    ("name", "step", "files", "limit"), STEP_CASES, ids=[f"{n}:{s}" for n, s, _, _ in STEP_CASES]
)
def test_design_skill_steps(name: str, step: str, files: list[str], limit: int) -> None:
    skill = skill_or_skip(name)
    paths = [skill / "SKILL.md", skill / "references" / "core-rules.md"]
    paths += [skill / rel for rel in files]
    total = tokens(*paths)
    assert total <= limit, f"{name} step '{step}': {total} tokens, limit {limit}"


@pytest.mark.parametrize("name", list(STEP_LOADS))
def test_every_reference_is_loaded_by_a_step(name: str) -> None:
    skill = skill_or_skip(name)
    loaded = {rel for files in STEP_LOADS[name][1].values() for rel in files}
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    for ref in stage_references(skill):
        rel = f"references/{ref.name}"
        assert rel in loaded, f"{name}: {rel} is not in any step's budget"
        assert ref.name in text, f"{name}: SKILL.md never names {ref.name}"


def test_always_on_agents_file() -> None:
    """The planning repository's AGENTS.md is not part of this repository."""
    pytest.skip("AGENTS.md of the planning repository is checked where that repository lives")
