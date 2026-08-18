#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Gather deterministic evidence about a repository. Decide nothing.

This script is the evidence half of crv-codebase-onboarding. It answers
questions with one correct answer -- what build systems are declared, where the
entry points are, which environment variables are referenced, what the git
history says -- so that the interpretation done afterwards rests on facts
rather than on recall.

It deliberately does not conclude. There is no "architecture" key in the
output, no "primary language" verdict, no quality score. Every observation
carries the path it came from, and anything ambiguous goes into ``notes``
rather than being resolved by a heuristic nobody can audit.

Safety properties, which hold for any repository you point it at:

* **No network access.** Nothing is fetched, resolved, or reported outward.
* **No project script execution.** Manifests are read, never run. The only
  subprocess is read-only ``git``, and ``--no-git`` disables even that.
* **No secret values.** Environment variables are reported by name and
  reference site only. Values are never read, never inferred, never emitted.
* **No modification.** The target repository is opened read-only.

Stdlib only, Python 3.9+, so it runs as ``python3 scan.py`` on stock macOS.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger("crv.scan")

SCHEMA_VERSION = "1"

EXIT_OK = 0
EXIT_FINDINGS = 1  # unused here: the scanner reports, it does not judge
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EXIT_CODE_HELP = """exit codes:
  0  scan completed
  2  usage error (bad or contradictory arguments)
  3  the target path does not exist or is not a directory
  4  the target exists but could not be read
  5  internal error
"""

#: Directories never descended into. Vendored and generated trees dominate file
#: counts and teach nothing about how the project is built.
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".vs",
    "node_modules",
    "bower_components",
    "vendor",
    "third_party",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    ".env.d",
    "target",
    "build",
    "dist",
    "out",
    "bin",
    "obj",
    ".gradle",
    ".m2",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".angular",
    ".parcel-cache",
    ".turbo",
    ".nx",
    "coverage",
    "htmlcov",
    ".coverage",
    ".terraform",
    ".serverless",
    ".aws-sam",
    "site-packages",
    ".dart_tool",
    "Pods",
    "DerivedData",
}

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".webp",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".jar",
    ".war",
    ".ear",
    ".class",
    ".dll",
    ".so",
    ".dylib",
    ".exe",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".wav",
    ".pyc",
    ".pyo",
    ".o",
    ".a",
    ".bin",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".avro",
    ".pkl",
    ".h5",
    ".onnx",
}

MAX_READ_BYTES = 1_000_000
DEFAULT_MAX_FILES = 40_000
DEFAULT_MAX_ITEMS = 50

# --------------------------------------------------------------------------
# Ecosystem signals. A marker file is evidence that a build system is declared;
# it is not evidence that it is the primary one, which is why confidence is
# reported and the verdict is left to a human.
# --------------------------------------------------------------------------

ECOSYSTEM_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("maven", "pom.xml", "Maven project object model"),
    ("gradle", "build.gradle", "Gradle build script (Groovy DSL)"),
    ("gradle", "build.gradle.kts", "Gradle build script (Kotlin DSL)"),
    ("gradle", "settings.gradle", "Gradle multi-project settings"),
    ("gradle", "settings.gradle.kts", "Gradle multi-project settings"),
    ("node", "package.json", "Node package manifest"),
    ("pnpm", "pnpm-workspace.yaml", "pnpm workspace"),
    ("pnpm", "pnpm-lock.yaml", "pnpm lockfile"),
    ("yarn", "yarn.lock", "Yarn lockfile"),
    ("npm", "package-lock.json", "npm lockfile"),
    ("nx", "nx.json", "Nx workspace configuration"),
    ("turborepo", "turbo.json", "Turborepo configuration"),
    ("lerna", "lerna.json", "Lerna monorepo configuration"),
    ("typescript", "tsconfig.json", "TypeScript compiler configuration"),
    ("python", "pyproject.toml", "PEP 621 / build-system metadata"),
    ("python", "setup.py", "setuptools build script"),
    ("python", "setup.cfg", "setuptools configuration"),
    ("python", "requirements.txt", "pip requirements"),
    ("poetry", "poetry.lock", "Poetry lockfile"),
    ("pipenv", "Pipfile", "Pipenv manifest"),
    ("uv", "uv.lock", "uv lockfile"),
    ("conda", "environment.yml", "conda environment"),
    ("dbt", "dbt_project.yml", "dbt project"),
    ("airflow", "airflow.cfg", "Airflow configuration"),
    ("go", "go.mod", "Go module"),
    ("rust", "Cargo.toml", "Cargo manifest"),
    ("dotnet", "global.json", "pinned .NET SDK version"),
    ("ruby", "Gemfile", "Bundler manifest"),
    ("php", "composer.json", "Composer manifest"),
    ("terraform", "main.tf", "Terraform root configuration"),
    ("terraform", "versions.tf", "Terraform provider constraints"),
    ("terragrunt", "terragrunt.hcl", "Terragrunt configuration"),
    ("bicep", "main.bicep", "Azure Bicep template"),
    ("helm", "Chart.yaml", "Helm chart"),
    ("docker", "Dockerfile", "Container image definition"),
    ("docker-compose", "docker-compose.yml", "Compose stack"),
    ("docker-compose", "docker-compose.yaml", "Compose stack"),
    ("docker-compose", "compose.yaml", "Compose stack"),
    ("kubernetes", "kustomization.yaml", "Kustomize overlay"),
    ("make", "Makefile", "Make targets"),
    ("task", "Taskfile.yml", "Task runner definition"),
    ("databricks", "databricks.yml", "Databricks asset bundle"),
    ("databricks", "databricks.yaml", "Databricks asset bundle"),
)

GLOB_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("dotnet", "*.csproj", "C# project"),
    ("dotnet", "*.fsproj", "F# project"),
    ("dotnet", "*.sln", "Visual Studio solution"),
    ("terraform", "*.tf", "Terraform configuration"),
    ("bicep", "*.bicep", "Azure Bicep template"),
    ("docker", "Dockerfile.*", "Container image definition"),
)

CI_MARKERS: tuple[tuple[str, str], ...] = (
    (".github/workflows", "GitHub Actions"),
    ("azure-pipelines.yml", "Azure Pipelines"),
    ("azure-pipelines.yaml", "Azure Pipelines"),
    (".azuredevops", "Azure DevOps configuration"),
    (".azure-pipelines", "Azure Pipelines templates"),
    (".gitlab-ci.yml", "GitLab CI"),
    ("Jenkinsfile", "Jenkins"),
    (".circleci/config.yml", "CircleCI"),
    ("bitbucket-pipelines.yml", "Bitbucket Pipelines"),
    (".teamcity", "TeamCity"),
)

CONTEXT_MARKERS: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "agents_md"),
    ("CLAUDE.md", "claude_md"),
    ("GEMINI.md", "other_agent_context"),
    (".github/copilot-instructions.md", "copilot_instructions"),
    (".cursorrules", "cursor_rules"),
    ("README.md", "readme"),
    ("README.rst", "readme"),
    ("CONTRIBUTING.md", "contributing"),
    ("ARCHITECTURE.md", "architecture_doc"),
    ("CODEOWNERS", "codeowners"),
    (".github/CODEOWNERS", "codeowners"),
)

ADR_DIRS = ("docs/adr", "docs/adrs", "docs/decisions", "architecture/decisions", "doc/adr")

ENTRY_POINT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?:^|/)main\.py$", "Python module entry point"),
    (r"(?:^|/)__main__\.py$", "Python package entry point"),
    (r"(?:^|/)manage\.py$", "Django management entry point"),
    (r"(?:^|/)wsgi\.py$", "WSGI application"),
    (r"(?:^|/)asgi\.py$", "ASGI application"),
    (r"(?:^|/)app\.py$", "Python application module"),
    (r"(?:^|/)main\.go$", "Go entry point"),
    (r"(?:^|/)main\.rs$", "Rust entry point"),
    (r"(?:^|/)Program\.cs$", ".NET entry point"),
    (r"(?:^|/)Startup\.cs$", ".NET startup configuration"),
    (r".*Application\.java$", "Spring Boot application class"),
    (r".*Application\.kt$", "Spring Boot application class"),
    (r"(?:^|/)index\.(?:ts|js|mjs|tsx)$", "JavaScript/TypeScript entry point"),
    (r"(?:^|/)main\.(?:ts|js|mjs|tsx)$", "JavaScript/TypeScript entry point"),
    (r"(?:^|/)server\.(?:ts|js|mjs)$", "Node server entry point"),
)

#: Environment variable reference sites. Names only -- the value side of an
#: assignment is never captured, in any of these patterns.
ENV_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"os\.environ\[[\"']([A-Z][A-Z0-9_]{2,})[\"']\]", "python"),
    (r"os\.environ\.get\(\s*[\"']([A-Z][A-Z0-9_]{2,})[\"']", "python"),
    (r"os\.getenv\(\s*[\"']([A-Z][A-Z0-9_]{2,})[\"']", "python"),
    (r"process\.env\.([A-Z][A-Z0-9_]{2,})", "node"),
    (r"process\.env\[[\"']([A-Z][A-Z0-9_]{2,})[\"']\]", "node"),
    (r"System\.getenv\(\s*\"([A-Z][A-Z0-9_]{2,})\"", "java"),
    (r"Environment\.GetEnvironmentVariable\(\s*\"([A-Z][A-Z0-9_]{2,})\"", "dotnet"),
    (r"os\.Getenv\(\s*\"([A-Z][A-Z0-9_]{2,})\"", "go"),
    (r"\$\{([A-Z][A-Z0-9_]{2,})(?::-[^}]*)?\}", "shell-or-compose"),
    (r"\$\{\{\s*secrets\.([A-Z][A-Z0-9_]{2,})\s*\}\}", "github-actions-secret"),
    (r"\$\(([A-Z][A-Z0-9_]{2,})\)", "azure-pipelines-variable"),
)

SECRET_NAME_HINTS = (
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "APIKEY",
    "API_KEY",
    "PRIVATE_KEY",
    "CREDENTIAL",
    "CONNECTION_STRING",
    "CONNSTR",
    "CLIENT_SECRET",
    "ACCESS_KEY",
    "SAS",
    "PAT",
    "CERT",
    "SIGNING_KEY",
    "ENCRYPTION_KEY",
)

DATASTORE_HINTS: tuple[tuple[str, str], ...] = (
    (r"\bpostgres(?:ql)?\b", "PostgreSQL"),
    (r"\bmysql\b", "MySQL"),
    (r"\bmariadb\b", "MariaDB"),
    (r"\bsqlserver\b|\bmssql\b|Data Source=.*Initial Catalog=", "SQL Server"),
    (r"\boracle\b|\bojdbc\b", "Oracle"),
    (r"\bmongodb\b|\bmongo\b", "MongoDB"),
    (r"\bredis\b", "Redis"),
    (r"\belasticsearch\b|\bopensearch\b", "Elasticsearch/OpenSearch"),
    (r"\bcassandra\b", "Cassandra"),
    (r"\bsnowflake\b", "Snowflake"),
    (r"\bdatabricks\b|\bdelta\b", "Databricks / Delta Lake"),
    (r"\bbigquery\b", "BigQuery"),
    (r"\bcosmos(?:db)?\b", "Azure Cosmos DB"),
    (r"\bblob\.core\.windows\.net\b|\bazure(?:-|\.)storage\b", "Azure Storage"),
    (r"\bs3\b|\baws-sdk.*s3\b", "S3"),
    (r"\bsqlite\b", "SQLite"),
)

MESSAGING_HINTS: tuple[tuple[str, str], ...] = (
    (r"\bkafka\b", "Kafka"),
    (r"\brabbitmq\b|\bamqp\b", "RabbitMQ / AMQP"),
    (r"\bservicebus\b|\bservice[_-]?bus\b", "Azure Service Bus"),
    (r"\beventhub\b|\bevent[_-]?hubs?\b", "Azure Event Hubs"),
    (r"\bsqs\b", "AWS SQS"),
    (r"\bpubsub\b|\bpub[_-]sub\b", "Pub/Sub"),
    (r"\bnats\b", "NATS"),
    (r"\bmqtt\b", "MQTT"),
)

MIGRATION_DIR_HINTS = (
    "migrations",
    "migration",
    "db/migrate",
    "flyway",
    "liquibase",
    "alembic",
    "changelog",
    "sql/migrations",
)

TEST_DIR_HINTS = ("test", "tests", "spec", "specs", "__tests__", "it", "e2e", "integration-test")

TEST_FILE_PATTERN = re.compile(
    r"(?:^|/)(?:test_[^/]+\.py|[^/]+_test\.py|[^/]+Test\.java|[^/]+Tests\.java|"
    r"[^/]+IT\.java|[^/]+_test\.go|[^/]+\.test\.[jt]sx?|[^/]+\.spec\.[jt]sx?|"
    r"[^/]+Tests?\.cs|[^/]+_spec\.rb)$"
)


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------


class Inventory:
    """Every file the scan is allowed to look at, gathered once."""

    def __init__(self, root: Path, extra_skips: Iterable[str], max_files: int) -> None:
        self.root = root
        self.skip_dirs = SKIP_DIRS | {s.strip() for s in extra_skips if s.strip()}
        self.max_files = max_files
        self.paths: list[Path] = []
        self.truncated = False
        self.skipped_dirs: list[str] = []
        self._walk()
        self.rel_paths: list[str] = [p.relative_to(root).as_posix() for p in self.paths]
        self.by_name: dict[str, list[str]] = defaultdict(list)
        for rel in self.rel_paths:
            self.by_name[Path(rel).name].append(rel)

    def _walk(self) -> None:
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=False):
            pruned = [
                d
                for d in dirnames
                if d in self.skip_dirs or (d.startswith(".") and d in self.skip_dirs)
            ]
            for name in pruned:
                dirnames.remove(name)
                self.skipped_dirs.append((Path(dirpath) / name).relative_to(self.root).as_posix())
            for filename in filenames:
                if len(self.paths) >= self.max_files:
                    self.truncated = True
                    LOGGER.warning(
                        "file limit of %d reached; the inventory is incomplete. "
                        "Re-run with --max-files to raise it.",
                        self.max_files,
                    )
                    return
                self.paths.append(Path(dirpath) / filename)

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def find_name(self, name: str) -> list[str]:
        return sorted(self.by_name.get(name, []))

    def find_glob(self, pattern: str) -> list[str]:
        regex = re.compile(
            "^" + re.escape(pattern).replace(r"\*", "[^/]*").replace(r"\?", "[^/]") + "$"
        )
        return sorted(rel for rel in self.rel_paths if regex.match(Path(rel).name))


def read_text(path: Path) -> Optional[str]:
    """Read a file as UTF-8, or return None. Never raises for a bad file."""
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return None


def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


# --------------------------------------------------------------------------
# Collectors. Each returns plain data and appends to `notes` when it sees
# something it cannot classify.
# --------------------------------------------------------------------------


def collect_git(root: Path, enabled: bool, notes: list[str]) -> dict[str, Any]:
    """Read-only git facts. The head SHA is what stamps the generated context."""
    if not enabled:
        return {"available": False, "reason": "disabled with --no-git"}
    if not (root / ".git").exists():
        notes.append("No .git directory: generated context cannot be stamped with a commit SHA.")
        return {"available": False, "reason": "no .git directory"}

    def git(*args: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", "--no-pager", *args],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            LOGGER.debug("git %s failed: %s", " ".join(args), exc)
            return None
        if result.returncode != 0:
            LOGGER.debug(
                "git %s exited %d: %s", " ".join(args), result.returncode, result.stderr.strip()
            )
            return None
        return result.stdout.strip()

    head = git("rev-parse", "HEAD")
    if head is None:
        notes.append("git is present but HEAD could not be read (empty repository?).")
        return {"available": False, "reason": "could not read HEAD"}

    status = git("status", "--porcelain")
    log_recent = git("log", "-n", "20", "--date=short", "--format=%h|%ad|%s") or ""
    churn = git("log", "-n", "500", "--name-only", "--format=") or ""
    churn_counter = Counter(line for line in churn.splitlines() if line.strip())

    return {
        "available": True,
        "head_sha": head,
        "head_short": head[:12],
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "remotes": [line for line in (git("remote", "-v") or "").splitlines()],
        "commit_count": git("rev-list", "--count", "HEAD"),
        "first_commit_date": git("log", "--reverse", "--date=short", "--format=%ad", "-n", "1"),
        "last_commit_date": git("log", "-n", "1", "--date=short", "--format=%ad"),
        "working_tree_dirty": bool(status),
        "recent_commits": [
            dict(zip(("sha", "date", "subject"), line.split("|", 2)))
            for line in log_recent.splitlines()
            if line.count("|") >= 2
        ],
        "most_changed_files": [
            {"path": path, "changes_in_last_500_commits": count}
            for path, count in churn_counter.most_common(20)
        ],
    }


def collect_size(inventory: Inventory, max_items: int) -> dict[str, Any]:
    by_extension: Counter = Counter()
    lines_by_extension: Counter = Counter()
    sizes: list[tuple[int, str]] = []

    for path, rel in zip(inventory.paths, inventory.rel_paths):
        suffix = path.suffix.lower() or "(none)"
        by_extension[suffix] += 1
        if suffix in BINARY_SUFFIXES:
            continue
        lines = count_lines(path)
        lines_by_extension[suffix] += lines
        sizes.append((lines, rel))

    sizes.sort(reverse=True)
    return {
        "files_total": len(inventory.paths),
        "files_by_extension": dict(by_extension.most_common(max_items)),
        "lines_by_extension": dict(lines_by_extension.most_common(max_items)),
        "largest_files_by_lines": [
            {"path": rel, "lines": lines} for lines, rel in sizes[:max_items]
        ],
        "inventory_truncated": inventory.truncated,
    }


def collect_existing_context(inventory: Inventory, root: Path) -> dict[str, Any]:
    """What the repository already tells an agent. This decides the mode."""
    found: dict[str, list[str]] = defaultdict(list)
    for name, key in CONTEXT_MARKERS:
        if "/" in name:
            if inventory.exists(name):
                found[key].append(name)
        else:
            found[key].extend(inventory.find_name(name))

    cursor_rules = sorted(rel for rel in inventory.rel_paths if rel.startswith(".cursor/rules/"))
    if cursor_rules:
        found["cursor_rules"].extend(cursor_rules)

    adrs: list[str] = []
    for directory in ADR_DIRS:
        adrs.extend(sorted(rel for rel in inventory.rel_paths if rel.startswith(directory + "/")))

    codebase_dir = root / "docs" / "codebase"
    codebase: dict[str, Any] = {"present": codebase_dir.is_dir()}
    if codebase.get("present"):
        files = sorted(p.name for p in codebase_dir.glob("*.md"))
        codebase["files"] = files
        codebase["stamps"] = []
        for name in files:
            text = read_text(codebase_dir / name) or ""
            match = re.search(
                r"verified against\s+([0-9a-f]{7,40})\s+on\s+(\d{4}-\d{2}-\d{2})", text
            )
            codebase["stamps"].append(
                {
                    "file": name,
                    "sha": match.group(1) if match else None,
                    "date": match.group(2) if match else None,
                }
            )

    return {
        "markers": {key: sorted(set(value)) for key, value in sorted(found.items())},
        "adr_files": adrs[:100],
        "docs_codebase": codebase,
    }


def collect_ecosystems(inventory: Inventory, max_items: int) -> list[dict[str, Any]]:
    evidence: dict[str, list[dict[str, str]]] = defaultdict(list)

    for ecosystem, marker, reason in ECOSYSTEM_MARKERS:
        for rel in inventory.find_name(marker)[:max_items]:
            evidence[ecosystem].append({"path": rel, "reason": reason})

    for ecosystem, pattern, reason in GLOB_MARKERS:
        for rel in inventory.find_glob(pattern)[:max_items]:
            evidence[ecosystem].append({"path": rel, "reason": reason})

    result = []
    for ecosystem in sorted(evidence):
        hits = evidence[ecosystem]
        root_level = any("/" not in hit["path"] for hit in hits)
        result.append(
            {
                "name": ecosystem,
                "marker_count": len(hits),
                # A root-level marker means the whole repository is built this
                # way; markers only in subdirectories usually mean a module.
                "confidence": "high" if root_level else "medium",
                "declared_at_root": root_level,
                "evidence": hits[:max_items],
            }
        )
    return result


def _parse_pom(text: str) -> dict[str, Any]:
    import xml.etree.ElementTree as ET

    try:
        tree = ET.fromstring(text)
    except ET.ParseError as exc:
        return {"parse_error": str(exc)}
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}

    def find(tag: str) -> Optional[str]:
        node = tree.find(f"m:{tag}", ns)
        if node is None:
            node = tree.find(tag)
        return node.text.strip() if node is not None and node.text else None

    modules = [
        node.text.strip()
        for node in tree.findall("m:modules/m:module", ns) + tree.findall("modules/module")
        if node.text
    ]
    parent = tree.find("m:parent/m:artifactId", ns)
    return {
        "artifact_id": find("artifactId"),
        "packaging": find("packaging"),
        "parent_artifact_id": parent.text.strip() if parent is not None and parent.text else None,
        "modules": modules,
    }


def _parse_package_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"parse_error": str(exc)}
    if not isinstance(data, dict):
        return {"parse_error": "package.json is not an object"}
    return {
        "name": data.get("name"),
        "private": data.get("private"),
        "package_manager": data.get("packageManager"),
        "workspaces": data.get("workspaces"),
        "scripts": sorted(data.get("scripts", {})) if isinstance(data.get("scripts"), dict) else [],
        "dependency_count": len(data.get("dependencies") or {}),
        "dev_dependency_count": len(data.get("devDependencies") or {}),
        "engines": data.get("engines"),
    }


def _parse_pyproject(text: str) -> dict[str, Any]:
    """Extract the few fields that matter without a TOML parser.

    Python 3.9 has no ``tomllib``, and the two-tier policy forbids a dependency
    in a skill script. These regexes are deliberately shallow; anything they
    cannot see is left for a human to read, which is why the source path is
    always reported alongside.
    """

    def scalar(key: str) -> Optional[str]:
        match = re.search(rf"^\s*{key}\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
        return match.group(1) if match else None

    return {
        "name": scalar("name"),
        "requires_python": scalar("requires-python"),
        "build_backend": scalar("build-backend"),
        "has_poetry_section": "[tool.poetry]" in text,
        "has_ruff_section": "[tool.ruff]" in text,
        "has_pytest_section": "[tool.pytest.ini_options]" in text,
        "parsed_with": "regex (no TOML parser on Python 3.9)",
    }


def collect_manifests(inventory: Inventory, root: Path, max_items: int) -> dict[str, Any]:
    manifests: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for rel in inventory.find_name("pom.xml")[:max_items]:
        text = read_text(root / rel)
        manifests["maven"].append(
            {"path": rel, **(_parse_pom(text) if text else {"unreadable": True})}
        )

    for rel in inventory.find_name("package.json")[:max_items]:
        text = read_text(root / rel)
        manifests["node"].append(
            {"path": rel, **(_parse_package_json(text) if text else {"unreadable": True})}
        )

    for rel in inventory.find_name("pyproject.toml")[:max_items]:
        text = read_text(root / rel)
        manifests["python"].append(
            {"path": rel, **(_parse_pyproject(text) if text else {"unreadable": True})}
        )

    for rel in inventory.find_name("go.mod")[:max_items]:
        text = read_text(root / rel) or ""
        module = re.search(r"^module\s+(\S+)", text, re.MULTILINE)
        go_version = re.search(r"^go\s+(\S+)", text, re.MULTILINE)
        manifests["go"].append(
            {
                "path": rel,
                "module": module.group(1) if module else None,
                "go_version": go_version.group(1) if go_version else None,
            }
        )

    for rel in inventory.find_name("dbt_project.yml")[:max_items]:
        text = read_text(root / rel) or ""
        name = re.search(r"^name:\s*['\"]?([A-Za-z0-9_\-]+)", text, re.MULTILINE)
        profile = re.search(r"^profile:\s*['\"]?([A-Za-z0-9_\-]+)", text, re.MULTILINE)
        manifests["dbt"].append(
            {
                "path": rel,
                "project_name": name.group(1) if name else None,
                "profile": profile.group(1) if profile else None,
            }
        )

    return dict(manifests)


def collect_entry_points(inventory: Inventory, max_items: int) -> list[dict[str, str]]:
    compiled = [(re.compile(pattern), reason) for pattern, reason in ENTRY_POINT_PATTERNS]
    found = []
    for rel in inventory.rel_paths:
        for regex, reason in compiled:
            if regex.search(rel):
                found.append({"path": rel, "reason": reason})
                break
    found.sort(key=lambda item: (item["path"].count("/"), item["path"]))
    return found[:max_items]


def collect_environment(inventory: Inventory, root: Path, max_items: int) -> dict[str, Any]:
    """Environment variable *names* and where they are referenced.

    Values are never captured. The regexes anchor on the name side of each
    reference form, and no capture group in ENV_PATTERNS spans a value.
    """
    compiled = [(re.compile(pattern), kind) for pattern, kind in ENV_PATTERNS]
    references: dict[str, list[str]] = defaultdict(list)
    kinds: dict[str, set] = defaultdict(set)

    for path, rel in zip(inventory.paths, inventory.rel_paths):
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        text = read_text(path)
        if not text:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            for regex, kind in compiled:
                for match in regex.finditer(line):
                    name = match.group(1)
                    if len(references[name]) < 5:
                        references[name].append(f"{rel}:{index}")
                    kinds[name].add(kind)

    dotenv_examples = [
        rel
        for rel in inventory.rel_paths
        if Path(rel).name in {".env.example", ".env.sample", ".env.template", ".env.dist"}
    ]
    for rel in dotenv_examples:
        text = read_text(root / rel) or ""
        for index, line in enumerate(text.splitlines(), start=1):
            match = re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]{2,})\s*=", line)
            if match:
                name = match.group(1)
                if len(references[name]) < 5:
                    references[name].append(f"{rel}:{index}")
                kinds[name].add("dotenv-example")

    variables = []
    for name in sorted(references):
        variables.append(
            {
                "name": name,
                "secret_like": any(hint in name for hint in SECRET_NAME_HINTS),
                "reference_kinds": sorted(kinds[name]),
                "references": references[name],
                "value_captured": False,
            }
        )

    committed_dotenv = [
        rel
        for rel in inventory.rel_paths
        if Path(rel).name == ".env" or Path(rel).name.startswith(".env.")
        if Path(rel).name not in {".env.example", ".env.sample", ".env.template", ".env.dist"}
    ]

    return {
        "variables": variables[: max_items * 4],
        "variable_count": len(variables),
        "secret_like_count": sum(1 for v in variables if v["secret_like"]),
        "dotenv_examples": dotenv_examples,
        "committed_dotenv_files": committed_dotenv,
        "policy": "names and reference sites only; no value is ever read or emitted",
    }


def _hint_scan(
    inventory: Inventory,
    hints: tuple[tuple[str, str], ...],
    max_items: int,
    filename_filter: Optional[tuple[str, ...]] = None,
) -> list[dict[str, Any]]:
    compiled = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in hints]
    evidence: dict[str, list[str]] = defaultdict(list)

    for path, rel in zip(inventory.paths, inventory.rel_paths):
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        if filename_filter and not rel.lower().endswith(filename_filter):
            continue
        text = read_text(path)
        if not text:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            for regex, label in compiled:
                if len(evidence[label]) >= 8:
                    continue
                if regex.search(line):
                    evidence[label].append(f"{rel}:{index}")

    return [
        {"name": label, "evidence": sites} for label, sites in sorted(evidence.items()) if sites
    ][:max_items]


def collect_migrations(inventory: Inventory, max_items: int) -> dict[str, Any]:
    directories = sorted(
        {
            str(Path(rel).parent)
            for rel in inventory.rel_paths
            if any(hint in rel.lower() for hint in MIGRATION_DIR_HINTS)
        }
    )
    tools = []
    if inventory.find_name("alembic.ini"):
        tools.append("alembic")
    if any("flyway" in rel.lower() for rel in inventory.rel_paths):
        tools.append("flyway")
    if any("liquibase" in rel.lower() or "changelog" in rel.lower() for rel in inventory.rel_paths):
        tools.append("liquibase")
    if any(re.search(r"/V\d+__", rel) for rel in inventory.rel_paths):
        tools.append("flyway-naming-convention")

    sql_files = [rel for rel in inventory.rel_paths if rel.lower().endswith(".sql")]
    return {
        "directories": directories[:max_items],
        "tools_detected": sorted(set(tools)),
        "sql_file_count": len(sql_files),
        "sample_sql_files": sorted(sql_files)[:max_items],
    }


def collect_ci(inventory: Inventory, root: Path, max_items: int) -> dict[str, Any]:
    systems = []
    for marker, label in CI_MARKERS:
        if inventory.exists(marker):
            files = []
            target = root / marker
            if target.is_dir():
                files = sorted(
                    p.relative_to(root).as_posix() for p in target.rglob("*") if p.is_file()
                )[:max_items]
            else:
                files = [marker]
            systems.append({"system": label, "marker": marker, "files": files})
    return {"systems": systems}


def collect_tests(inventory: Inventory, max_items: int) -> dict[str, Any]:
    test_files = [rel for rel in inventory.rel_paths if TEST_FILE_PATTERN.search(rel)]
    test_dirs = sorted(
        {
            part_path
            for rel in inventory.rel_paths
            for part_path in [
                "/".join(Path(rel).parts[: index + 1])
                for index, part in enumerate(Path(rel).parts[:-1])
                if part.lower() in TEST_DIR_HINTS
            ]
        }
    )
    frameworks = []
    for name, label in (
        ("pytest.ini", "pytest"),
        ("conftest.py", "pytest"),
        ("tox.ini", "tox"),
        ("jest.config.js", "jest"),
        ("jest.config.ts", "jest"),
        ("vitest.config.ts", "vitest"),
        ("playwright.config.ts", "playwright"),
        ("karma.conf.js", "karma"),
        ("cypress.config.ts", "cypress"),
        ("testng.xml", "testng"),
    ):
        if inventory.find_name(name):
            frameworks.append(label)
    return {
        "test_file_count": len(test_files),
        "test_directories": test_dirs[:max_items],
        "frameworks_detected": sorted(set(frameworks)),
        "sample_test_files": sorted(test_files)[:max_items],
    }


def collect_containers(inventory: Inventory, root: Path, max_items: int) -> dict[str, Any]:
    dockerfiles = sorted(
        rel
        for rel in inventory.rel_paths
        if Path(rel).name == "Dockerfile" or Path(rel).name.startswith("Dockerfile.")
    )
    base_images = []
    for rel in dockerfiles[:max_items]:
        text = read_text(root / rel) or ""
        for match in re.finditer(r"^\s*FROM\s+(\S+)", text, re.MULTILINE | re.IGNORECASE):
            base_images.append({"path": rel, "image": match.group(1)})

    k8s = sorted(
        rel
        for rel in inventory.rel_paths
        if rel.endswith((".yaml", ".yml"))
        and re.search(r"(?:^|/)(k8s|kubernetes|manifests|deploy)/", rel)
    )
    return {
        "dockerfiles": dockerfiles[:max_items],
        "base_images": base_images[: max_items * 2],
        "compose_files": sorted(
            rel
            for rel in inventory.rel_paths
            if Path(rel).name
            in {"docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml"}
        ),
        "helm_charts": inventory.find_name("Chart.yaml")[:max_items],
        "kubernetes_like_manifests": k8s[:max_items],
    }


def collect_iac(inventory: Inventory, max_items: int) -> dict[str, Any]:
    tf = sorted(rel for rel in inventory.rel_paths if rel.endswith(".tf"))
    return {
        "terraform_files": tf[:max_items],
        "terraform_file_count": len(tf),
        "terraform_modules": sorted({str(Path(rel).parent) for rel in tf})[:max_items],
        "bicep_files": sorted(rel for rel in inventory.rel_paths if rel.endswith(".bicep"))[
            :max_items
        ],
        "arm_templates": sorted(
            rel for rel in inventory.rel_paths if Path(rel).name == "azuredeploy.json"
        )[:max_items],
    }


def collect_config_files(inventory: Inventory, max_items: int) -> list[str]:
    interesting = (
        "application.properties",
        "application.yml",
        "application.yaml",
        "appsettings.json",
        "web.config",
        "config.yaml",
        "config.yml",
        ".editorconfig",
        ".eslintrc.json",
        ".eslintrc.js",
        "eslint.config.js",
        ".prettierrc",
        "checkstyle.xml",
        "spotbugs.xml",
        ".flake8",
        "ruff.toml",
        "mypy.ini",
        ".pylintrc",
        "sonar-project.properties",
    )
    found = [rel for rel in inventory.rel_paths if Path(rel).name in interesting]
    found += [
        rel
        for rel in inventory.rel_paths
        if re.match(r"^application-[a-z0-9]+\.(properties|ya?ml)$", Path(rel).name)
    ]
    return sorted(set(found))[:max_items]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scan.py",
        description=(
            "Gather deterministic evidence about a repository for "
            "crv-codebase-onboarding. Emits JSON on stdout and diagnostics on stderr. "
            "Read-only: no network, no project script execution, no secret values, "
            "no modification of the target."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 scan.py                              # scan the current directory\n"
            "  python3 scan.py --root ../service --output scan.json\n"
            "  python3 scan.py --no-git                     # skip git entirely\n"
            "  python3 scan.py --exclude generated,legacy   # prune extra directories\n"
            "  python3 scan.py --max-items 20               # shorter lists\n\n"
            "output:\n"
            "  A single JSON object. Keys of note: `notes` lists everything the scanner\n"
            "  saw but could not classify, and `limits` reports any truncation. Read both\n"
            "  before drawing conclusions -- the scanner reports evidence and decides\n"
            "  nothing.\n\n" + EXIT_CODE_HELP
        ),
    )
    parser.add_argument(
        "--root", type=Path, default=Path(), help="Repository root (default: current directory)."
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Write JSON here instead of stdout."
    )
    parser.add_argument("--no-git", action="store_true", help="Do not invoke git, even read-only.")
    parser.add_argument(
        "--exclude",
        default="",
        help="Comma-separated extra directory names to prune, in addition to the built-in list.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=DEFAULT_MAX_ITEMS,
        help=f"Cap on the length of each list in the output (default: {DEFAULT_MAX_ITEMS}).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=DEFAULT_MAX_FILES,
        help=f"Stop inventorying after this many files (default: {DEFAULT_MAX_FILES}).",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    parser.add_argument("--quiet", action="store_true", help="Only warnings and errors on stderr.")
    return parser


def configure_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    LOGGER.handlers = [handler]
    LOGGER.setLevel(level)
    LOGGER.propagate = False


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose, args.quiet)

    if args.max_items < 1 or args.max_files < 1:
        LOGGER.error("--max-items and --max-files must be at least 1")
        return EXIT_USAGE

    root = args.root.expanduser()
    if not root.exists():
        LOGGER.error("target does not exist: %s", root)
        return EXIT_INPUT
    if not root.is_dir():
        LOGGER.error("target is not a directory: %s", root)
        return EXIT_INPUT
    root = root.resolve()

    try:
        LOGGER.info("scanning %s", root)
        notes: list[str] = []
        inventory = Inventory(root, args.exclude.split(","), args.max_files)
        LOGGER.info("inventoried %d file(s)", len(inventory.paths))

        if not inventory.paths:
            notes.append("The tree contains no files outside the skip list; nothing to report.")

        payload: dict[str, Any] = {
            "tool": "crv-codebase-scan",
            "schema_version": SCHEMA_VERSION,
            "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "root": str(root),
            "git": collect_git(root, not args.no_git, notes),
            "size": collect_size(inventory, args.max_items),
            "existing_context": collect_existing_context(inventory, root),
            "ecosystems": collect_ecosystems(inventory, args.max_items),
            "manifests": collect_manifests(inventory, root, args.max_items),
            "entry_points": collect_entry_points(inventory, args.max_items),
            "config_files": collect_config_files(inventory, args.max_items),
            "environment": collect_environment(inventory, root, args.max_items),
            "datastores": _hint_scan(inventory, DATASTORE_HINTS, args.max_items),
            "messaging": _hint_scan(inventory, MESSAGING_HINTS, args.max_items),
            "migrations": collect_migrations(inventory, args.max_items),
            "containers": collect_containers(inventory, root, args.max_items),
            "ci": collect_ci(inventory, root, args.max_items),
            "iac": collect_iac(inventory, args.max_items),
            "tests": collect_tests(inventory, args.max_items),
        }

        if not payload["ecosystems"]:
            notes.append(
                "No build-system marker was found. Either this is not a buildable project, "
                "or it uses a convention this scanner does not know. Say so rather than guessing."
            )
        if payload["environment"]["committed_dotenv_files"]:
            notes.append(
                "A .env-style file is committed. Its contents were NOT read. Flag it as a "
                "concern and check whether it holds real credentials."
            )
        if not payload["ci"]["systems"]:
            notes.append(
                "No CI configuration found; how this project is built and released is unverified."
            )
        if not payload["tests"]["test_file_count"]:
            notes.append("No files matched the test-file naming conventions this scanner knows.")

        payload["notes"] = notes
        payload["limits"] = {
            "max_items": args.max_items,
            "max_files": args.max_files,
            "inventory_truncated": inventory.truncated,
            "max_read_bytes_per_file": MAX_READ_BYTES,
            "skipped_directory_count": len(inventory.skipped_dirs),
            "skipped_directories_sample": sorted(inventory.skipped_dirs)[: args.max_items],
        }
        payload["guarantees"] = {
            "network_access": False,
            "project_scripts_executed": False,
            "secret_values_emitted": False,
            "target_modified": False,
        }

        document = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(document, encoding="utf-8")
            LOGGER.info("wrote %s (%d bytes)", args.output, len(document))
        else:
            sys.stdout.write(document)
            sys.stdout.flush()

        for note in notes:
            LOGGER.warning("note: %s", note)
        return EXIT_OK

    except PermissionError as exc:
        LOGGER.error("cannot read the target: %s", exc)
        return EXIT_MALFORMED
    except OSError as exc:
        LOGGER.error("filesystem error: %s", exc)
        return EXIT_MALFORMED


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(EXIT_INTERNAL)
