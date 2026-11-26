"""``check_traceability.py`` and the last Inception gate that relies on it.

A declaration is an id at the start of a heading or the first cell of a table
row; anything else is a reference. The tests write small Inception folders and
assert the exact gap reported, so a check that silently passes would fail here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "processes" / "crv-aidlc"
CHECK = SKILL / "scripts" / "check_traceability.py"
STATE = SKILL / "scripts" / "aidlc_state.py"

REQUIREMENTS = """# Requirements

## FR-1 Export a report
Users export a report.

## NFR-1 Speed
Export finishes in 5 s.
"""
STORIES = """# Stories

### US-1 Export
Covers FR-1 and NFR-1.

| ID | Criterion |
|---|---|
| AC-1.1 | Given data, when exported, then a file is produced |
"""
UNITS = """# Units

## U-1 Exporter
Serves US-1.
"""


def write(bolt: Path, rel: str, text: str) -> None:
    path = bolt / "docs" / "inception" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check(bolt: Path) -> tuple[int, dict[str, Any]]:
    done = subprocess.run(
        [sys.executable, str(CHECK), "--bolt", str(bolt)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done.returncode, (json.loads(done.stdout) if done.stdout.startswith("{") else {})


def codes(data: dict[str, Any]) -> list[tuple[str, str]]:
    return [(f["code"], f["id"]) for f in data["findings"]]


@pytest.fixture
def bolt(tmp_path: Path) -> Path:
    write(tmp_path, "requirements-analysis/requirements.md", REQUIREMENTS)
    write(tmp_path, "user-stories/stories.md", STORIES)
    write(tmp_path, "units-generation/unit-of-work.md", UNITS)
    return tmp_path


def test_a_fully_traced_bolt_passes(bolt: Path) -> None:
    code, data = check(bolt)
    assert code == 0 and data["ok"] and data["findings"] == []
    assert data["declared"] == {"AC": 1, "FR": 1, "NFR": 1, "U": 1, "US": 1}


def test_a_requirement_nobody_references_is_reported(bolt: Path) -> None:
    write(
        bolt,
        "requirements-analysis/requirements.md",
        REQUIREMENTS + "\n## FR-2 Schedule\nLater.\n",
    )
    code, data = check(bolt)
    assert code == 1 and codes(data) == [("requirement-uncovered", "FR-2")]


def test_a_requirement_covered_by_a_unit_is_enough(bolt: Path) -> None:
    write(
        bolt,
        "requirements-analysis/requirements.md",
        REQUIREMENTS + "\n## FR-2 Schedule\nLater.\n",
    )
    write(bolt, "units-generation/unit-of-work.md", UNITS + "\nAlso builds FR-2.\n")
    assert check(bolt)[0] == 0


def test_a_story_map_table_links_a_requirement_to_a_unit(bolt: Path) -> None:
    write(
        bolt,
        "requirements-analysis/requirements.md",
        REQUIREMENTS + "\n## FR-2 Schedule\nLater.\n",
    )
    write(
        bolt,
        "units-generation/unit-of-work-story-map.md",
        "| Item | Unit |\n|---|---|\n| FR-2 | U-1 |\n",
    )
    assert check(bolt)[0] == 0


def test_a_story_without_a_unit_is_reported(bolt: Path) -> None:
    write(bolt, "units-generation/unit-of-work.md", "# Units\n\n## U-1 Exporter\nNothing yet.\n")
    code, data = check(bolt)
    assert ("story-no-unit", "US-1") in codes(data) and ("unit-orphan", "U-1") in codes(data)
    assert code == 1


def test_a_unit_without_story_or_requirement_is_reported(bolt: Path) -> None:
    write(bolt, "units-generation/unit-of-work.md", UNITS + "\n## U-2 Spare\nNothing.\n")
    code, data = check(bolt)
    assert code == 1 and codes(data) == [("unit-orphan", "U-2")]


def test_a_story_without_acceptance_criteria_is_reported(bolt: Path) -> None:
    write(bolt, "user-stories/stories.md", "# Stories\n\n### US-1 Export\nCovers FR-1 and NFR-1.\n")
    code, data = check(bolt)
    assert code == 1 and codes(data) == [("story-no-ac", "US-1")]


def test_an_ac_written_as_a_plain_bullet_is_a_reference_not_a_declaration(bolt: Path) -> None:
    write(
        bolt,
        "user-stories/stories.md",
        "# S\n\n### US-1 Export\nCovers FR-1, NFR-1.\n\n- AC-1.1 does it\n",
    )
    code, data = check(bolt)
    assert code == 1
    assert ("undeclared-id", "AC-1.1") in codes(data) and ("story-no-ac", "US-1") in codes(data)


def test_an_id_referenced_but_never_declared_is_reported(bolt: Path) -> None:
    write(bolt, "units-generation/unit-of-work.md", UNITS + "\nDepends on FR-9.\n")
    code, data = check(bolt)
    assert code == 1 and codes(data) == [("undeclared-id", "FR-9")]
    assert data["findings"][0]["files"] == ["docs/inception/units-generation/unit-of-work.md"]


def test_question_files_and_code_fences_do_not_declare(bolt: Path) -> None:
    write(bolt, "user-stories/user-stories-questions.md", "## US-77 not a story\nFR-1?\n")
    write(
        bolt,
        "units-generation/unit-of-work-dependency.md",
        "```yaml\n# U-1 comment\nunits:\n  - name: U-1\n```\n",
    )
    code, data = check(bolt)
    assert code == 0, data


def test_ids_are_not_found_inside_longer_words(bolt: Path) -> None:
    write(bolt, "units-generation/unit-of-work.md", UNITS + "\nSee ANFR-1, FR-1a and U-1-x.\n")
    assert check(bolt)[0] == 0


def test_a_missing_inception_folder_exits_3(tmp_path: Path) -> None:
    assert check(tmp_path)[0] == 3


def test_a_file_that_is_not_text_exits_4(bolt: Path) -> None:
    (bolt / "docs" / "inception" / "bad.md").write_bytes(b"\xff\xfe\x00bad")
    assert check(bolt)[0] == 4


# --- the gate ----------------------------------------------------------------

QUESTIONS = "## Q1 Scope\nContext.\n\nA) One\nB) Two\nX) Other (describe)\n\nRecommended: A - simple.\n\nAnswer: A\n"
DIGESTED = "# T\n\n## Digest\n- point\n"


def state_run(bolt: Path, command: str, *args: str) -> tuple[int, dict[str, Any]]:
    done = subprocess.run(
        [sys.executable, str(STATE), command, "--bolt", str(bolt), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done.returncode, (json.loads(done.stdout) if done.stdout.startswith("{") else {})


def open_classic(root: Path, scope: str = "classic") -> Path:
    done = subprocess.run(
        [sys.executable, str(STATE), "open", "--root", str(root), "--slug", "d", "--title", "D",
         "--intent", "i", "--scope", scope],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    return Path(json.loads(done.stdout)["bolt"])


def produce_delivery_planning(bolt: Path) -> None:
    base = "delivery-planning/"
    for name in (
        "slice-plan",
        "team-allocation",
        "risk-and-sequencing-rationale",
        "external-dependency-map",
    ):
        write(bolt, f"{base}{name}.md", DIGESTED)
    write(bolt, base + "delivery-planning-questions.md", QUESTIONS)
    (bolt / "docs" / "verification").mkdir(parents=True, exist_ok=True)
    (bolt / "docs" / "verification" / "phase-check-inception.md").write_text(
        DIGESTED, encoding="utf-8"
    )
    assert state_run(bolt, "step", "--stage", "delivery-planning", "--to", "produced")[0] == 0


def test_the_last_inception_gate_refuses_while_ids_are_untraced(tmp_path: Path) -> None:
    bolt = open_classic(tmp_path)
    write(bolt, "requirements-analysis/requirements.md", REQUIREMENTS)
    write(bolt, "user-stories/stories.md", STORIES)
    produce_delivery_planning(bolt)
    code, data = state_run(bolt, "gate", "--stage", "delivery-planning", "--approve", "--by", "B")
    assert code == 1
    assert {f["code"] for f in data["findings"]} == {"traceability-story-no-unit"}
    state = json.loads((bolt / "state.json").read_text(encoding="utf-8"))
    assert state["stages"]["delivery-planning"]["step"] == "produced"


def test_the_last_inception_gate_passes_once_traced(tmp_path: Path) -> None:
    bolt = open_classic(tmp_path)
    write(bolt, "requirements-analysis/requirements.md", REQUIREMENTS)
    write(bolt, "user-stories/stories.md", STORIES)
    write(bolt, "units-generation/unit-of-work.md", UNITS)
    produce_delivery_planning(bolt)
    code, data = state_run(bolt, "gate", "--stage", "delivery-planning", "--approve", "--by", "B")
    assert code == 0, data


def test_earlier_inception_gates_do_not_run_the_check(tmp_path: Path) -> None:
    bolt = open_classic(tmp_path)
    write(bolt, "requirements-analysis/requirements.md", REQUIREMENTS)  # untraced on purpose
    write(bolt, "requirements-analysis/traceability.json", "{}")
    write(bolt, "requirements-analysis/requirements-analysis-questions.md", QUESTIONS)
    state_run(bolt, "step", "--stage", "requirements-analysis", "--to", "produced")
    code, data = state_run(
        bolt, "gate", "--stage", "requirements-analysis", "--approve", "--by", "B"
    )
    assert code == 1 and [f["code"] for f in data["findings"]] == ["digest-missing"]


@pytest.mark.parametrize("scope", ["bugfix", "express"])
def test_scopes_without_stories_or_units_skip_the_check(tmp_path: Path, scope: str) -> None:
    bolt = open_classic(tmp_path, scope)
    write(bolt, "requirements-analysis/requirements.md", "# R\n\n## Digest\n- x\n\n## FR-1 Fix\n")
    write(bolt, "requirements-analysis/traceability.json", "{}")
    write(bolt, "requirements-analysis/requirements-analysis-questions.md", QUESTIONS)
    state_run(bolt, "step", "--stage", "requirements-analysis", "--to", "produced")
    code, data = state_run(
        bolt, "gate", "--stage", "requirements-analysis", "--approve", "--by", "B"
    )
    assert code == 0, data
