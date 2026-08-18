"""Budgets warn for drafts and fail for stable skills."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_budgets.py"

VALID = (
    "name: crv-example\n"
    "description: Does the example thing. Use when the tests need a valid skill.\n"
    "metadata:\n"
    "  owner: test-team\n"
    "  layer: processes\n"
    "  maturity: {maturity}\n"
    "  execution: subagent\n"
    "  model-tier: economy\n"
)

STABLE_EXTRA = '  version: "1.0.0"\n  tags: test\n  review-cadence: annual\n'


@pytest.fixture
def budgets(run_script, skill_repo):
    def _budgets(*args: str):
        return run_script(SCRIPT, ["--root", str(skill_repo), *args])

    return _budgets


def oversized_body(lines: int = 700) -> str:
    return "# Example\n\n" + "\n".join(f"Line {n} of filler prose." for n in range(lines)) + "\n"


def test_small_skill_passes(make_skill, budgets):
    make_skill(frontmatter=VALID.format(maturity="draft"))
    run = budgets()
    assert run.returncode == 0, run.stderr
    assert run.json["summary"] == {"errors": 0, "warnings": 0}


def test_measurements_are_reported(make_skill, budgets):
    make_skill(frontmatter=VALID.format(maturity="draft"))
    measurement = budgets().json["measurements"][0]
    assert measurement["skill_md"]["lines"] > 0
    assert measurement["skill_md"]["characters"] > 0
    assert measurement["skill_md"]["tokens"] is not None


def test_draft_over_budget_warns_but_does_not_fail(make_skill, budgets):
    make_skill(frontmatter=VALID.format(maturity="draft"), body=oversized_body())
    run = budgets()
    assert run.returncode == 0
    assert "budget.skill-md.max-lines" in run.codes()
    assert all(f["level"] == "warning" for f in run.json["findings"])


def test_stable_over_budget_fails(make_skill, budgets):
    make_skill(
        frontmatter=VALID.format(maturity="stable") + STABLE_EXTRA,
        body=oversized_body(),
    )
    run = budgets()
    assert run.returncode == 1
    assert any(f["level"] == "error" for f in run.json["findings"])


def test_strict_promotes_draft_warnings(make_skill, budgets):
    make_skill(frontmatter=VALID.format(maturity="draft"), body=oversized_body())
    assert budgets().returncode == 0
    assert budgets("--strict").returncode == 1


def test_long_reference_file_warns(make_skill, budgets):
    skill = make_skill(frontmatter=VALID.format(maturity="draft"))
    (skill / "references").mkdir()
    (skill / "references" / "long.md").write_text(
        "\n".join(f"line {n}" for n in range(500)), encoding="utf-8"
    )
    run = budgets()
    assert "budget.reference.warn-lines" in run.codes()
    assert run.returncode == 0  # soft budget


def test_exemption_suppresses_a_finding(make_skill, budgets, skill_repo):
    make_skill(frontmatter=VALID.format(maturity="stable") + STABLE_EXTRA, body=oversized_body())
    config_path = skill_repo / "standards" / "configs" / "budgets.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["exemptions"] = [
        {
            "path": "skills/processes/crv-example/SKILL.md",
            "budget": "max-lines",
            "reason": "Exempt in tests to prove the escape hatch works end to end.",
        }
    ]
    config_path.write_text(json.dumps(config), encoding="utf-8")
    assert "budget.skill-md.max-lines" not in budgets().codes()


def test_malformed_config_refuses_to_run(make_skill, budgets, skill_repo):
    """A typo must fail loudly, not silently stop enforcing a budget."""
    make_skill(frontmatter=VALID.format(maturity="draft"))
    config_path = skill_repo / "standards" / "configs" / "budgets.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["skill-md"]["max_lines"] = config["skill-md"].pop("max-lines")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    run = budgets()
    assert run.returncode == 4
    assert "schema" in run.stderr


def test_missing_config_exits_input_error(make_skill, budgets):
    make_skill(frontmatter=VALID.format(maturity="draft"))
    assert budgets("--config", "/nonexistent/budgets.json").returncode == 3


def test_tokenizer_reported_honestly(make_skill, budgets):
    make_skill(frontmatter=VALID.format(maturity="draft"))
    tokenizer = budgets().json["tokenizer"]
    assert tokenizer["encoding"] == "cl100k_base"
    assert isinstance(tokenizer["available"], bool)
    if not tokenizer["available"]:
        assert tokenizer["unavailable_reason"]


def test_stdout_is_only_json(make_skill, budgets):
    make_skill(frontmatter=VALID.format(maturity="draft"), body=oversized_body())
    budgets("--verbose").json
