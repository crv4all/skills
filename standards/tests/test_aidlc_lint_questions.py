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

Answer: A
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
    "no-answer-line": GOOD.replace("Answer: A\n", ""),
    "empty-answer": GOOD.replace("Answer: A", "Answer:"),
    "answer-not-offered": GOOD.replace("Answer: A", "Answer: D"),
    "other-without-text": GOOD.replace("Answer: A", "Answer: X"),
    "multiple-letters": GOOD.replace("Answer: A", "Answer: A, B"),
}


@pytest.mark.parametrize("expected", sorted(CASES))
def test_each_finding_type(tmp_path: Path, expected: str) -> None:
    code, result = lint(tmp_path, CASES[expected])
    assert code == 1
    assert expected in codes(result)


def test_other_with_text_is_fine(tmp_path: Path) -> None:
    code, _ = lint(tmp_path, GOOD.replace("Answer: A", "Answer: X - a graph database"))
    assert code == 0


def test_multi_select_question_allows_several_letters(tmp_path: Path) -> None:
    text = GOOD.replace("keep records.", "keep records. Select all that apply.").replace(
        "Answer: A", "Answer: A, B"
    )
    code, _ = lint(tmp_path, text)
    assert code == 0


def test_allow_open_skips_only_the_empty_answer(tmp_path: Path) -> None:
    empty = GOOD.replace("Answer: A", "Answer:")
    code, result = lint(tmp_path, empty, "--allow-open")
    assert code == 0, result
    broken = empty.replace("X) Other (describe)\n", "")
    code, result = lint(tmp_path, broken, "--allow-open")
    assert code == 1
    assert codes(result) == ["no-other-option"]


def test_vague_answer_is_a_warning_only(tmp_path: Path) -> None:
    code, result = lint(tmp_path, GOOD.replace("Answer: A", "Answer: A - depends on load"))
    assert code == 0
    assert codes(result, "warnings") == ["vague-answer"]


def test_findings_name_the_question_and_line(tmp_path: Path) -> None:
    _, result = lint(tmp_path, CASES["answer-not-offered"])
    found = result["findings"][0]
    assert found["question"] == "Q1"
    assert isinstance(found["line"], int)


# --- the answer marker -------------------------------------------------------


def test_the_legacy_marker_is_read_with_the_same_rules(tmp_path: Path) -> None:
    legacy = GOOD.replace("Answer: A", "[Answer]: A")
    assert lint(tmp_path, legacy)[0] == 0
    code, result = lint(tmp_path, legacy.replace("[Answer]: A", "[Answer]: D"))
    assert code == 1 and codes(result) == ["answer-not-offered"]
    code, result = lint(tmp_path, legacy.replace("[Answer]: A", "[Answer]:"))
    assert code == 1 and codes(result) == ["empty-answer"]


def test_a_rewritten_answer_line_names_the_fix(tmp_path: Path) -> None:
    damaged = GOOD.replace("Answer: A", "[Answer](A)")
    code, result = lint(tmp_path, damaged)
    assert code == 1 and codes(result) == ["answer-rewritten"]
    assert "Answer: <letter>" in result["findings"][0]["message"]
    assert result["findings"][0]["line"] == damaged.splitlines().index("[Answer](A)") + 1


def test_an_answer_line_beside_a_rewritten_one_is_still_checked(tmp_path: Path) -> None:
    text = GOOD.replace("Answer: A", "[Answer](A)\nAnswer: D")
    code, result = lint(tmp_path, text)
    assert code == 1 and sorted(codes(result)) == ["answer-not-offered", "answer-rewritten"]


# --- a layer proposal is the first question's context -------------------------

LAYERED = """# Round A

## Layer 1: Business context

Proposal: keep exports in the reporting service; it already owns the data.

## Q1 Storage

A) Relational database
B) Object storage
X) Other (describe)

Recommended: A - records are queried by several fields.

Answer: A

## Q2 Retention

A) One year
B) Seven years
X) Other (describe)

Recommended: B - the audit rule asks for seven.

Answer: B
"""


def test_a_proposal_gives_only_the_first_question_its_context(tmp_path: Path) -> None:
    code, result = lint(tmp_path, LAYERED)
    assert code == 1
    assert [(f["code"], f["question"]) for f in result["findings"]] == [("no-context", "Q2")]


def test_a_layer_without_a_proposal_gives_no_context(tmp_path: Path) -> None:
    text = LAYERED.replace("Proposal: keep exports", "Keep exports")
    _, result = lint(tmp_path, text)
    assert [f["question"] for f in result["findings"] if f["code"] == "no-context"] == [
        "Q1",
        "Q2",
    ]


def test_a_proposal_does_not_reach_past_another_section(tmp_path: Path) -> None:
    text = LAYERED.replace("## Q1 Storage", "## Already answered\n\n- none\n\n## Q1 Storage")
    _, result = lint(tmp_path, text)
    assert "Q1" in [f["question"] for f in result["findings"] if f["code"] == "no-context"]
