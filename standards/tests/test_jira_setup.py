"""``jira_setup.py`` records what the create screen does not enforce.

A Jira create screen enforces what an administrator marked required. It does not
enforce what the organisation expects on every issue, so a field like
``Assigned Team(s)`` is silently absent from a batch that satisfied the screen,
and is then asked for afterwards at the cost of one edit per issue.

These tests cover the recording of those defaults, and the two properties that
make them safe to rely on: names are stored rather than tenant-specific
identifiers, and re-running the same command does not accumulate values.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills" / "processes" / "crv-create-jira-story" / "scripts" / "jira_setup.py"


@pytest.fixture
def run(tmp_path: Path):
    """Invoke the script against a throwaway configuration directory."""

    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            timeout=60,
            env={"XDG_CONFIG_HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
        )

    return _run


@pytest.fixture
def configured(run):
    """A machine with a site and a default project already recorded."""
    result = run(
        "--set",
        "--site",
        "https://example.atlassian.net",
        "--project",
        "ABC",
        "--confirm",
    )
    assert result.returncode == 0, result.stderr
    return run


def defaults_of(run, project: str) -> dict[str, object]:
    result = run("--show")
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)["config"]
    return config.get("project_defaults", {}).get(project, {})


def test_a_single_value_is_stored_as_a_scalar(configured) -> None:
    result = configured("--set", "--field-default", "Assigned Team(s)=Platform", "--confirm")
    assert result.returncode == 0, result.stderr
    assert defaults_of(configured, "ABC") == {"Assigned Team(s)": "Platform"}


def test_a_repeated_name_becomes_a_list(configured) -> None:
    """A multi-value field needs a list, and the caller says so by repeating."""
    result = configured(
        "--set",
        "--field-default",
        "Assigned Team(s)=Platform",
        "--field-default",
        "Assigned Team(s)=Empower",
        "--confirm",
    )
    assert result.returncode == 0, result.stderr
    assert defaults_of(configured, "ABC") == {"Assigned Team(s)": ["Platform", "Empower"]}


def test_re_running_replaces_rather_than_appends(configured) -> None:
    """The agent will re-run this. Growing the list every time is not idempotent."""
    for _ in range(3):
        assert configured("--set", "--field-default", "Team=Platform", "--confirm").returncode == 0
    assert defaults_of(configured, "ABC") == {"Team": "Platform"}


def test_defaults_are_scoped_per_project(configured) -> None:
    configured("--set", "--field-default", "Team=Platform", "--confirm")
    configured(
        "--set", "--defaults-project", "CHO", "--field-default", "Team=COWabunga", "--confirm"
    )
    assert defaults_of(configured, "ABC") == {"Team": "Platform"}
    assert defaults_of(configured, "CHO") == {"Team": "COWabunga"}


def test_a_second_project_does_not_move_the_default_project(configured) -> None:
    configured(
        "--set", "--defaults-project", "CHO", "--field-default", "Team=COWabunga", "--confirm"
    )
    config = json.loads(configured("--show").stdout)["config"]
    assert config["project_key"] == "ABC"


def test_clearing_removes_only_the_scoped_project(configured) -> None:
    configured("--set", "--field-default", "Team=Platform", "--confirm")
    configured(
        "--set", "--defaults-project", "CHO", "--field-default", "Team=COWabunga", "--confirm"
    )
    cleared = configured(
        "--set", "--defaults-project", "CHO", "--clear-field-defaults", "--confirm"
    )
    assert cleared.returncode == 0, cleared.stderr
    assert defaults_of(configured, "CHO") == {}
    assert defaults_of(configured, "ABC") == {"Team": "Platform"}


def test_custom_field_identifiers_are_refused(configured) -> None:
    """An identifier recorded here is wrong on the next tenant, and silently so."""
    result = configured("--set", "--field-default", "customfield_10008=ABC-1", "--confirm")
    assert result.returncode == 2
    assert "customfield" in result.stderr
    assert defaults_of(configured, "ABC") == {}


@pytest.mark.parametrize("argument", ["Team", "=Platform", "Team="])
def test_malformed_field_defaults_are_usage_errors(configured, argument: str) -> None:
    result = configured("--set", "--field-default", argument, "--confirm")
    assert result.returncode == 2
    assert defaults_of(configured, "ABC") == {}


def test_a_default_needs_a_project_to_belong_to(run) -> None:
    """With nothing recorded and no scope given, there is no project to attach to."""
    result = run("--set", "--field-default", "Team=Platform", "--confirm")
    assert result.returncode == 2
    assert "project" in result.stderr


def test_dry_run_writes_nothing(configured) -> None:
    result = configured("--set", "--field-default", "Team=Platform")
    assert result.returncode == 0
    assert json.loads(result.stdout)["written"] is False
    assert defaults_of(configured, "ABC") == {}


def test_defaults_flags_are_refused_outside_set(configured) -> None:
    result = configured("--show", "--field-default", "Team=Platform")
    assert result.returncode == 2


def test_a_structurally_wrong_defaults_block_is_malformed_not_absent(
    configured, tmp_path: Path
) -> None:
    """A hand-edited file needs inspection, not a re-run of setup."""
    path = tmp_path / "crv-agent-skills" / "jira.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["project_defaults"] = ["Assigned Team(s)"]
    path.write_text(json.dumps(config), encoding="utf-8")

    result = configured("--set", "--field-default", "Team=Platform", "--confirm")
    assert result.returncode == 4
    assert "project_defaults" in result.stderr
