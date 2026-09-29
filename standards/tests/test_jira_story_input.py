"""The story input schema pins the rules that matter before Jira is called.

The schema is optional -- a caller may describe stories in prose instead -- but
when it is used it must enforce exactly what ``crv-create-jira-story`` enforces
conversationally. Two rules are worth pinning. An estimate is optional, because
sizing belongs to the team in grooming and a number invented at filing time is
indistinguishable from an agreed one, but a value that is *present* and invalid
is still invalid, and a value that is merely unusual is not. And Priority is
refused outright, since it is the field that produced a broken icon on the board
the last time something chose one.
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
    }
    story.update(overrides)
    return story


def test_minimal_is_valid(validator: Draft202012Validator) -> None:
    validator.validate(minimal())


def test_shipped_example_matches_its_own_schema(validator: Draft202012Validator) -> None:
    """Guards drift between the example and the schema it demonstrates."""
    validator.validate(json.loads(EXAMPLE_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("field", ["summary", "parent"])
def test_each_required_field_is_required(validator: Draft202012Validator, field: str) -> None:
    story = minimal()
    del story[field]
    with pytest.raises(ValidationError) as excinfo:
        validator.validate(story)
    assert excinfo.value.validator == "required"
    assert field in excinfo.value.message


def test_story_points_are_optional(validator: Draft202012Validator) -> None:
    """A story with no estimate is valid, and is the normal case.

    Requiring an estimate forced the skill to either block the batch or invent a
    number. Blocking means re-running the whole decomposition over a value that
    takes five seconds to set in grooming; inventing means a number that is
    summed into a sprint commitment and cannot be told apart from an agreed one.
    """
    story = minimal()
    assert "story_points" not in story
    validator.validate(story)


def test_unsized_provenance_rejects_a_number_beside_it(
    validator: Draft202012Validator,
) -> None:
    """A story cannot claim it was filed unsized and carry an estimate.

    Both together would put a provenance on the issue that contradicts the field
    next to it, which is worse than either alone: the reader cannot tell which
    of the two is the mistake.
    """
    validator.validate(minimal(estimate_source="unsized"))
    with pytest.raises(ValidationError):
        validator.validate(minimal(estimate_source="unsized", story_points=3))


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


@pytest.mark.parametrize("key", ["Priority", "priority"])
def test_priority_cannot_be_smuggled_through_additional_fields(
    validator: Draft202012Validator, key: str
) -> None:
    """Priority has its own key, so the generic escape hatch must refuse it.

    The skill never picks a priority: grooming decides it against the whole
    backlog, and a value invented at filing time cannot be told apart from an
    agreed one. A priority a *person* chose is legitimate, which is why the
    top-level ``priority`` key exists. Routing one through ``additional_fields``
    instead is how a recorded default or a guess arrives looking supplied, so
    that path stays closed and setting a priority stays a deliberate act.
    """
    with pytest.raises(ValidationError):
        validator.validate(minimal(additional_fields={key: {"name": "High"}}))


def test_a_person_chosen_priority_has_a_home(validator: Draft202012Validator) -> None:
    validator.validate(minimal(priority="High"))


@pytest.mark.parametrize("source", ["supplied", "proposed-and-approved", "unsized"])
def test_estimate_provenance_is_recordable(validator: Draft202012Validator, source: str) -> None:
    """A bulk-approved estimate must be distinguishable from a groomed one.

    Asking twenty-nine times does not scale, so the skill is allowed to propose a
    table of estimates and take one approval. The cost of that concession is that
    the provenance has to survive onto the issue, which it cannot do if the input
    format has nowhere to put it.
    """
    validator.validate(minimal(estimate_source=source))


def test_unknown_estimate_provenance_is_invalid(validator: Draft202012Validator) -> None:
    with pytest.raises(ValidationError):
        validator.validate(minimal(estimate_source="guessed"))


def test_a_goal_can_replace_the_user_story(validator: Draft202012Validator) -> None:
    """Technical work has no real person to put in "As a ... I want".

    Forcing one produces "As a developer, I want the service split", which is the
    filler the writing reference bans, so a goal is a first-class alternative.
    """
    validator.validate(minimal(goal="OrderService is split so pricing deploys alone"))


def test_a_story_cannot_carry_both_a_goal_and_a_user_story(
    validator: Draft202012Validator,
) -> None:
    story = minimal(
        goal="OrderService is split so pricing deploys alone",
        user_story={"role": "operator", "capability": "a split service", "benefit": "less risk"},
    )
    with pytest.raises(ValidationError):
        validator.validate(story)


def test_dependencies_can_be_machine_readable(validator: Draft202012Validator) -> None:
    """Native issue links need edges, not prose.

    Plan-local ids are accepted alongside real keys because a batch describes
    dependencies between stories that do not have keys yet.
    """
    validator.validate(minimal(id=2, blocked_by=[1, "ABC-9"], blocks=["3"]))


def test_edge_lists_reject_structured_items(validator: Draft202012Validator) -> None:
    """An edge is an id or a key. Anything else is a prose dependency."""
    with pytest.raises(ValidationError):
        validator.validate(minimal(blocked_by=[{"key": "ABC-9"}]))
