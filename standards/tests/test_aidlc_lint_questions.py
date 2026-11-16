"""``lint_questions.py`` checks the shape and the answers of a stage question file."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts" / "lint_questions.py"

GOOD = """# Questions

## Q1 Storage
The service needs somewhere to keep records.

A) Relational database
B) Object storage
X) Other (describe)

Recommended: A - records are queried by several fields.

[Answer]: A
"""


def lint(tmp_path: Path, text: str, *extra: str) -> tuple[int, dict]:
    path = tmp_path / "questions.md"
    path.write_text(text, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(path), *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done.returncode, json.loads(done.stdout)


def codes(result: dict, key: str = "findings") -> list[str]:
    return [item["code"] for item in result[key]]


def test_clean_file_passes(tmp_path: Path) -> None:
    code, result = lint(tmp_path, GOOD)
    assert code == 0, result
    assert result["questions"] == 1
    assert result["findings"] == []


def test_missing_file_exits_3(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(tmp_path / "nope.md")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 3


def test_no_questions(tmp_path: Path) -> None:
    code, result = lint(tmp_path, "# Nothing here\n")
    assert code == 1
    assert codes(result) == ["no-questions"]


CASES = {
    "no-context": GOOD.replace("The service needs somewhere to keep records.\n", ""),
    "too-few-options": GOOD.replace("B) Object storage\n", ""),
    "too-many-options": GOOD.replace("B) Object storage\n", "B) b\nC) c\nD) d\nE) e\nF) f\n"),
    "no-other-option": GOOD.replace("X) Other (describe)\n", ""),
    "no-recommendation": GOOD.replace(
        "Recommended: A - records are queried by several fields.\n", ""
    ),
    "no-recommendation-reason": GOOD.replace(
        "Recommended: A - records are queried by several fields.", "Recommended: A"
    ),
    "no-answer-line": GOOD.replace("[Answer]: A\n", ""),
    "empty-answer": GOOD.replace("[Answer]: A", "[Answer]:"),
    "answer-not-offered": GOOD.replace("[Answer]: A", "[Answer]: D"),
    "other-without-text": GOOD.replace("[Answer]: A", "[Answer]: X"),
    "multiple-letters": GOOD.replace("[Answer]: A", "[Answer]: A, B"),
}


@pytest.mark.parametrize("expected", sorted(CASES))
def test_each_finding_type(tmp_path: Path, expected: str) -> None:
    code, result = lint(tmp_path, CASES[expected])
    assert code == 1
    assert expected in codes(result)


def test_other_with_text_is_fine(tmp_path: Path) -> None:
    code, _ = lint(tmp_path, GOOD.replace("[Answer]: A", "[Answer]: X - a graph database"))
    assert code == 0


def test_multi_select_question_allows_several_letters(tmp_path: Path) -> None:
    text = GOOD.replace("keep records.", "keep records. Select all that apply.").replace(
        "[Answer]: A", "[Answer]: A, B"
    )
    code, _ = lint(tmp_path, text)
    assert code == 0


def test_allow_open_skips_only_the_empty_answer(tmp_path: Path) -> None:
    empty = GOOD.replace("[Answer]: A", "[Answer]:")
    code, result = lint(tmp_path, empty, "--allow-open")
    assert code == 0, result
    broken = empty.replace("X) Other (describe)\n", "")
    code, result = lint(tmp_path, broken, "--allow-open")
    assert code == 1
    assert codes(result) == ["no-other-option"]


def test_vague_answer_is_a_warning_only(tmp_path: Path) -> None:
    code, result = lint(tmp_path, GOOD.replace("[Answer]: A", "[Answer]: A - depends on load"))
    assert code == 0
    assert codes(result, "warnings") == ["vague-answer"]


def test_findings_name_the_question_and_line(tmp_path: Path) -> None:
    _, result = lint(tmp_path, CASES["answer-not-offered"])
    found = result["findings"][0]
    assert found["question"] == "Q1"
    assert isinstance(found["line"], int)
