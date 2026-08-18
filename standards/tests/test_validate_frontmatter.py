"""The frontmatter validator rejects what harnesses reject, plus governance."""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_frontmatter.py"

VALID = (
    "name: crv-example\n"
    "description: Does the example thing and produces an example result. "
    "Use when the tests need a valid skill.\n"
    "license: Apache-2.0\n"
    "metadata:\n"
    "  owner: test-team\n"
    "  layer: processes\n"
    "  maturity: draft\n"
    "  execution: subagent\n"
    "  model-tier: economy\n"
)

BODY = "# Example\n\n## Execution\n\nSubagent, economy tier.\n\nDo the thing.\n"


@pytest.fixture
def validate(run_script, skill_repo):
    def _validate(*args: str):
        return run_script(SCRIPT, ["--root", str(skill_repo), *args])

    return _validate


def test_valid_skill_passes(make_skill, validate):
    make_skill()
    run = validate()
    assert run.returncode == 0, run.stderr
    assert run.json["summary"] == {"errors": 0, "warnings": 0}


def test_rejects_top_level_version(make_skill, validate):
    """`version` is the field authors reach for most, and it is not a field."""
    make_skill(frontmatter=VALID + 'version: "1.0.0"\n')
    run = validate()
    assert run.returncode == 1
    assert "frontmatter.unknown-field" in run.codes()
    hint = next(f for f in run.json["findings"] if f["code"] == "frontmatter.unknown-field")["hint"]
    assert "metadata" in hint


def test_rejects_disable_model_invocation(make_skill, validate):
    """Forbidden in v1: Claude Code rejects unexpected keys when packaging."""
    make_skill(frontmatter=VALID + "disable-model-invocation: true\n")
    run = validate()
    assert run.returncode == 1
    assert "frontmatter.unknown-field" in run.codes()


def test_rejects_unquoted_numeric_metadata(make_skill, validate):
    """`version: 1.0` is a YAML float, and the spec allows only strings."""
    frontmatter = VALID.replace("  maturity: draft\n", "  maturity: draft\n  version: 1.0\n")
    make_skill(frontmatter=frontmatter)
    run = validate()
    assert run.returncode == 1
    assert "frontmatter.schema" in run.codes()


def test_requires_crv_prefix(make_skill, validate):
    make_skill(name="example", frontmatter=VALID.replace("crv-example", "example"))
    run = validate()
    assert run.returncode == 1
    assert "frontmatter.schema" in run.codes()


def test_name_must_equal_directory(make_skill, validate):
    make_skill(directory="crv-other")
    run = validate()
    assert run.returncode == 1
    assert "frontmatter.name-directory-mismatch" in run.codes()


def test_layer_must_equal_parent_directory(make_skill, validate):
    make_skill(layer="patterns", frontmatter=VALID)  # frontmatter says processes
    run = validate()
    assert run.returncode == 1
    assert "frontmatter.layer-directory-mismatch" in run.codes()


def test_stable_requires_governance_fields(make_skill, validate):
    make_skill(frontmatter=VALID.replace("maturity: draft", "maturity: stable"))
    run = validate()
    assert run.returncode == 1
    messages = " ".join(f["message"] for f in run.json["findings"])
    for required in ("version", "tags", "review-cadence"):
        assert required in messages


def test_stable_with_governance_fields_passes(make_skill, validate):
    frontmatter = VALID.replace(
        "  maturity: draft\n",
        '  maturity: stable\n  version: "1.0.0"\n  tags: onboarding,context\n'
        "  review-cadence: quarterly\n",
    )
    make_skill(frontmatter=frontmatter)
    run = validate()
    assert run.returncode == 0, run.stderr


def test_dangling_reference_is_an_error(make_skill, validate):
    make_skill(body=BODY + "\nRun scripts/missing.py for details.\n")
    run = validate()
    assert run.returncode == 1
    assert "reference.missing" in run.codes()


def test_existing_reference_is_accepted(make_skill, validate):
    skill = make_skill(body=BODY + "\nSee references/detail.md.\n")
    (skill / "references").mkdir()
    (skill / "references" / "detail.md").write_text("# Detail\n", encoding="utf-8")
    run = validate()
    assert run.returncode == 0, run.stderr


def test_repo_relative_paths_are_not_mistaken_for_bundled_ones(make_skill, validate):
    """`standards/scripts/x.py` is not a bundled `scripts/x.py`."""
    make_skill(body=BODY + "\nRun standards/scripts/check_budgets.py first.\n")
    run = validate()
    assert "reference.missing" not in run.codes()


def test_chained_reference_warns(make_skill, validate):
    skill = make_skill(body=BODY + "\nSee references/a.md.\n")
    (skill / "references").mkdir()
    (skill / "references" / "a.md").write_text("See references/b.md\n", encoding="utf-8")
    (skill / "references" / "b.md").write_text("# B\n", encoding="utf-8")
    run = validate()
    assert "reference.chained" in run.codes()


def test_description_without_trigger_warns(make_skill, validate):
    frontmatter = VALID.replace(
        "description: Does the example thing and produces an example result. "
        "Use when the tests need a valid skill.\n",
        "description: Does the example thing and produces an example result for callers.\n",
    )
    make_skill(frontmatter=frontmatter)
    run = validate()
    assert "description.no-trigger" in run.codes()
    assert run.returncode == 0  # a warning, not an error


def test_self_referential_description_warns(make_skill, validate):
    frontmatter = VALID.replace(
        "description: Does the example thing and produces an example result. "
        "Use when the tests need a valid skill.\n",
        "description: This skill does the example thing. Use when testing.\n",
    )
    make_skill(frontmatter=frontmatter)
    assert "description.self-referential" in validate().codes()


def test_strict_promotes_warnings_to_errors(make_skill, validate):
    frontmatter = VALID.replace(
        "description: Does the example thing and produces an example result. "
        "Use when the tests need a valid skill.\n",
        "description: Does the example thing and produces an example result for callers.\n",
    )
    make_skill(frontmatter=frontmatter)
    assert validate().returncode == 0
    assert validate("--strict").returncode == 1


def test_unparseable_frontmatter_is_reported_not_crashed(skill_repo, validate):
    directory = skill_repo / "skills" / "processes" / "crv-broken"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text("# no frontmatter at all\n", encoding="utf-8")
    run = validate()
    assert run.returncode == 1
    assert "frontmatter.unparseable" in run.codes()


def test_empty_body_is_an_error(make_skill, validate):
    make_skill(body="")
    assert "body.empty" in validate().codes()


def test_stdout_is_only_json(make_skill, validate):
    make_skill(body=BODY + "\nRun scripts/missing.py.\n")
    run = validate("--verbose")
    run.json  # would raise if a diagnostic leaked into stdout
    assert "error:" in run.stderr


def test_output_flag_keeps_stdout_empty(make_skill, validate, tmp_path):
    make_skill()
    target = tmp_path / "report.json"
    run = validate("--output", str(target))
    assert run.stdout == ""
    assert target.is_file()


def test_missing_schema_exits_input_error(make_skill, validate):
    make_skill()
    assert validate("--schema", "/nonexistent/schema.json").returncode == 3


def test_unknown_target_exits_input_error(make_skill, validate):
    make_skill()
    assert validate("skills/processes/nope").returncode == 3


# ------------------------------------------------------ execution contract


def test_execution_metadata_is_required(make_skill, validate):
    frontmatter = VALID.replace("  execution: subagent\n", "")
    make_skill(frontmatter=frontmatter)
    run = validate()
    assert run.returncode == 1
    assert "'execution' is a required property" in " ".join(
        f["message"] for f in run.json["findings"]
    )


def test_model_tier_is_required(make_skill, validate):
    frontmatter = VALID.replace("  model-tier: economy\n", "")
    make_skill(frontmatter=frontmatter)
    assert validate().returncode == 1


def test_execution_section_is_required_in_the_body(make_skill, validate):
    """Metadata nobody acts on is decoration."""
    make_skill(body="# Example\n\nDo the thing.\n")
    run = validate()
    assert run.returncode == 1
    assert "execution.missing-section" in run.codes()


def test_inline_execution_warns(make_skill, validate):
    make_skill(frontmatter=VALID.replace("execution: subagent", "execution: inline"))
    run = validate()
    assert "execution.inline" in run.codes()
    assert run.returncode == 0  # allowed, but it has to be visible


def test_escalated_tier_warns(make_skill, validate):
    make_skill(frontmatter=VALID.replace("model-tier: economy", "model-tier: frontier"))
    run = validate()
    assert "execution.escalated-tier" in run.codes()
    assert run.returncode == 0


def test_unknown_tier_is_rejected(make_skill, validate):
    make_skill(frontmatter=VALID.replace("model-tier: economy", "model-tier: cheapest"))
    assert validate().returncode == 1


def test_shipped_skills_default_to_subagent_and_economy(repo_root):
    """The rule is only real if the skills we ship actually follow it."""
    import yaml

    for skill_md in sorted((repo_root / "skills").rglob("SKILL.md")):
        front = skill_md.read_text(encoding="utf-8").split("---")[1]
        metadata = yaml.safe_load(front)["metadata"]
        assert metadata["execution"] == "subagent", skill_md
        assert metadata["model-tier"] == "economy", skill_md
        assert "## Execution" in skill_md.read_text(encoding="utf-8"), skill_md
