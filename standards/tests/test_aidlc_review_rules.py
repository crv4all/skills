"""A stage never needs a question it does not have; the HLA review never conditions a TDD.

(Review fixes, group H6.) The gate no longer asks for a question file, the question lint
accepts a file with no question, and the shared rules and the skills that carry them say
the same thing the scripts do.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_aidlc_state import Bolt, digest, open_bolt, reach_produced

PROCESSES = Path(__file__).resolve().parents[2] / "skills" / "processes"
RA = "docs/inception/requirements-analysis/"


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def write_artifacts(p: Bolt) -> None:
    p.write(RA + "requirements.md", digest())
    p.write(RA + "traceability.json", "{}")


def test_a_stage_passes_its_checkpoint_with_no_question_file(bolt: Bolt) -> None:
    reach_produced(bolt)
    write_artifacts(bolt)
    assert not (bolt.path / RA / "requirements-analysis-questions.md").exists()
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "A")
    assert code == 0, data


def test_a_question_file_with_only_assumed_choices_passes_the_checkpoint(bolt: Bolt) -> None:
    reach_produced(bolt)
    write_artifacts(bolt)
    bolt.write(
        RA + "requirements-analysis-questions.md",
        "# Questions\n\n## Assumed\n- Dates are UTC because the repo stores UTC.\n",
    )
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "A")
    assert code == 0, data


def test_an_asked_question_is_still_checked_in_full(bolt: Bolt) -> None:
    reach_produced(bolt)
    write_artifacts(bolt)
    bolt.write(RA + "requirements-analysis-questions.md", "# Questions\n\n## Q1 Scope\nWhich?\n")
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "A")
    assert code == 1 and data["findings"]


def test_no_shared_rule_or_skill_still_forces_a_question() -> None:
    forced = ("must exist at the checkpoint", "ask the single one", "holds the one question")
    texts = list(PROCESSES.glob("crv-aidlc*/SKILL.md")) + list(
        PROCESSES.glob("crv-aidlc*/references/*.md")
    )
    for path in texts:
        text = path.read_text(encoding="utf-8")
        assert not [phrase for phrase in forced if phrase in text], path
    rules = (PROCESSES / "crv-aidlc/references/core-rules.md").read_text(encoding="utf-8")
    assert "no forced question" in rules and "`## Assumed`" in rules


def test_the_tdd_skill_does_not_wait_for_the_hla_review() -> None:
    skill = (PROCESSES / "crv-aidlc-tdd/SKILL.md").read_text(encoding="utf-8")
    assert "never conditions the TDD" in skill and "recommend waiting" not in skill
    for name in ("triggers.md", "behaviour.md"):
        text = (PROCESSES / "crv-aidlc-tdd/evals" / name).read_text(encoding="utf-8")
        assert "recommends waiting" not in text and "recommend waiting" not in text
