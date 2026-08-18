"""Shared fixtures for the standards test suite."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Run:
    """The result of invoking a script as a subprocess."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def json(self) -> Any:
        """Parse stdout as JSON.

        Fails loudly rather than skipping, because "stdout is a single valid
        JSON document" is itself one of the contracts under test.
        """
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - failure path
            raise AssertionError(
                f"stdout is not valid JSON ({exc}). A diagnostic leaked into the "
                f"payload channel.\n--- stdout ---\n{self.stdout[:2000]}"
            ) from exc

    def codes(self) -> list[str]:
        return [finding["code"] for finding in self.json.get("findings", [])]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def run_script():
    """Invoke a repository script and capture both channels separately."""

    def _run(script: Path, args: Sequence[str], cwd: Optional[Path] = None) -> Run:
        result = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=str(cwd or REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        return Run(result.returncode, result.stdout, result.stderr)

    return _run


@pytest.fixture
def skill_repo(tmp_path: Path) -> Path:
    """A minimal repository skeleton with the schemas and config copied in."""
    root = tmp_path / "repo"
    for layer in ("utilities", "knowledge", "patterns", "processes"):
        (root / "skills" / layer).mkdir(parents=True)
    (root / "standards" / "schemas").mkdir(parents=True)
    (root / "standards" / "configs").mkdir(parents=True)
    for name in ("skill-frontmatter-v1.schema.json", "budgets-config-v1.schema.json"):
        (root / "standards" / "schemas" / name).write_text(
            (REPO_ROOT / "standards" / "schemas" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (root / "standards" / "configs" / "budgets.json").write_text(
        (REPO_ROOT / "standards" / "configs" / "budgets.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def make_skill(skill_repo: Path):
    """Write a skill into the temporary repository and return its directory."""

    def _make(
        name: str = "crv-example",
        layer: str = "processes",
        frontmatter: Optional[str] = None,
        body: str = "# Example\n\nDo the thing.\n",
        directory: Optional[str] = None,
    ) -> Path:
        if frontmatter is None:
            frontmatter = (
                f"name: {name}\n"
                "description: Does the example thing and produces an example result. "
                "Use when the tests need a valid skill.\n"
                "license: Apache-2.0\n"
                "metadata:\n"
                "  owner: test-team\n"
                f"  layer: {layer}\n"
                "  maturity: draft\n"
            )
        skill_dir = skill_repo / "skills" / layer / (directory or name)
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
        return skill_dir

    return _make
