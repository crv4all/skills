"""The story input schema pins the rules that matter before Jira is called.

The schema is optional -- a caller may describe stories in prose instead -- but
when it is used it must enforce exactly what ``crv-create-jira-story`` enforces
conversationally. The rule worth testing is the estimate: an un-estimated story
is the failure the skill exists to prevent, and a story-point value that is
merely unusual is not the same thing as an invalid one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "processes" / "crv-create-jira-story"
SCHEMA_PATH = SKILL / "assets" / "story_input.schema.json"
EXAMPLE_PATH = SKILL / "assets" / "story_input.example.json"


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def minimal(**overrides: Any) -> dict[str, Any]:
    story: dict[str, Any] = {
        "summary": "Reject expired tokens at the ingest endpoint",
        "parent": "ABC-123",
        "story_points": 3,
    }
    story.update(overrides)
    return story


def test_minimal_is_valid(validator: Draft202012Validator) -> None:
    validator.validate(minimal())


def test_shipped_example_matches_its_own_schema(validator: Draft202012Validator) -> None:
    """Guards drift between the example and the schema it demonstrates."""
    validator.validate(json.loads(EXAMPLE_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("field", ["summary", "parent", "story_points"])
def test_each_required_field_is_required(validator: Draft202012Validator, field: str) -> None:
    story = minimal()
    del story[field]
    with pytest.raises(ValidationError) as excinfo:
        validator.validate(story)
    assert excinfo.value.validator == "required"
    assert field in excinfo.value.message


def test_empty_object_is_invalid(validator: Draft202012Validator) -> None:
    with pytest.raises(ValidationError):
        validator.validate({})


@pytest.mark.parametrize("points", [1, 2, 3, 13, 55, 100, 137])
def test_story_points_are_not_restricted_to_a_ladder(
    validator: Draft202012Validator, points: int
) -> None:
    """Teams use their own scales, and a roll-up lands on no ladder at all.

    ``100`` and ``137`` are on no Fibonacci sequence and must still validate.
    This is the regression guard: a well-meaning tightening of the schema to an
    enum would reject exactly the estimates that arise from combining several
    stories into one.
    """
    validator.validate(minimal(story_points=points))


@pytest.mark.parametrize("points", [0, -3])
def test_non_positive_story_points_are_invalid(
    validator: Draft202012Validator, points: int
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validator.validate(minimal(story_points=points))
    assert excinfo.value.validator == "minimum"


@pytest.mark.parametrize("points", [1.5, "3", None])
def test_non_integer_story_points_are_invalid(validator: Draft202012Validator, points: Any) -> None:
    with pytest.raises(ValidationError):
        validator.validate(minimal(story_points=points))


def test_summary_over_jira_limit_is_invalid(validator: Draft202012Validator) -> None:
    """Jira rejects summaries over 255 characters; catch it before the call."""
    with pytest.raises(ValidationError):
        validator.validate(minimal(summary="x" * 256))


@pytest.mark.parametrize("parent", ["abc-123", "ABC123", "ABC-0", "ABC-", "TOOLONGAKEY-1"])
def test_malformed_parent_keys_are_invalid(validator: Draft202012Validator, parent: str) -> None:
    with pytest.raises(ValidationError):
        validator.validate(minimal(parent=parent))


def test_unknown_top_level_field_is_rejected(validator: Draft202012Validator) -> None:
    """``additional_fields`` is the escape hatch; the top level stays closed.

    An unrecognised top-level key is far more likely to be a typo than an
    intentional extension, and silently dropping it is how a value the caller
    believed they had supplied never reaches Jira.
    """
    with pytest.raises(ValidationError):
        validator.validate(minimal(storypoints=3))


def test_additional_fields_are_keyed_by_name(validator: Draft202012Validator) -> None:
    validator.validate(minimal(additional_fields={"Product Area": {"value": "API"}}))
