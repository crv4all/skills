#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Take a read-only inventory of a git repository as compact JSON.

Reverse engineering starts from facts a script can get for free: which files
exist, in what languages, how they are built, tested and deployed, and where
the natural seams between areas are. Collecting them here means the workers
that read the code do not each rediscover the layout, and the same inputs give
the same inventory, so two runs can be compared.

The scan lists files with `git ls-files`, so `.gitignore` is respected and
build output never appears. It never opens file contents and never runs
project code.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import logging
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Optional

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EPILOG = """examples:
  python3 scan_repo.py --repo ../billing-service
  python3 scan_repo.py --repo . --depth 2 --out /tmp/billing-scan.json

exit codes:
  0  inventory written
  1  the repository has no tracked files, so there is nothing to inventory
  2  usage error
  3  the path does not exist, is not a git repository, or git is not installed
  4  git could not list the files (damaged repository)
  5  internal error
"""

LOG = logging.getLogger("scan_repo")

MAX_AREAS = 8
CAPS = {
    "manifests": 60,
    "entry_points": 30,
    "config_files": 40,
    "test_dirs": 20,
    "ci_files": 20,
    "docs": 30,
    "tree": 120,
    "languages": 15,
    "largest": 20,
}

LANGUAGES = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".fs": "F#",
    ".vb": "Visual Basic",
    ".c": "C",
    ".h": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".jl": "Julia",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".clj": "Clojure",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".tf": "Terraform",
    ".tfvars": "Terraform",
    ".bicep": "Bicep",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".less": "CSS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".proto": "Protocol Buffers",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".ipynb": "Jupyter Notebook",
}
SPECIAL_LANGUAGE_NAMES = {"dockerfile": "Dockerfile", "makefile": "Makefile"}

MANIFEST_NAMES = {
    "package.json": "npm",
    "pnpm-workspace.yaml": "pnpm",
    "lerna.json": "lerna",
    "nx.json": "nx",
    "turbo.json": "turborepo",
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "pipfile": "python",
    "tox.ini": "python",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "settings.gradle": "gradle",
    "settings.gradle.kts": "gradle",
    "build.sbt": "sbt",
    "go.mod": "go",
    "cargo.toml": "cargo",
    "gemfile": "bundler",
    "composer.json": "composer",
    "mix.exs": "mix",
    "pubspec.yaml": "dart",
    "dbt_project.yml": "dbt",
    "packages.yml": "dbt",
    "dockerfile": "docker",
    "makefile": "make",
    "justfile": "just",
    "taskfile.yml": "task",
    "cmakelists.txt": "cmake",
    "chart.yaml": "helm",
    "kustomization.yaml": "kustomize",
    "serverless.yml": "serverless",
    "template.yaml": "sam",
    "cdk.json": "cdk",
    "databricks.yml": "databricks-bundle",
    "global.json": "dotnet",
    "directory.build.props": "dotnet",
    "nuget.config": "dotnet",
    "packages.config": "dotnet",
}
MANIFEST_GLOBS = [
    ("requirements*.txt", "python"),
    ("*.csproj", "dotnet"),
    ("*.fsproj", "dotnet"),
    ("*.vbproj", "dotnet"),
    ("*.sln", "dotnet"),
    ("dockerfile.*", "docker"),
    ("*.dockerfile", "docker"),
    ("docker-compose*.y*ml", "docker-compose"),
    ("compose*.y*ml", "docker-compose"),
    ("*.tf", "terraform"),
    ("*.bicep", "bicep"),
    ("*.pkr.hcl", "packer"),
]
LOCK_FILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "pipfile.lock",
    "cargo.lock",
    "go.sum",
    "gemfile.lock",
    "composer.lock",
    "packages.lock.json",
    "gradle.lockfile",
    "mix.lock",
    "pubspec.lock",
}

ENTRY_NAMES = {
    "main.py",
    "__main__.py",
    "app.py",
    "wsgi.py",
    "asgi.py",
    "manage.py",
    "cli.py",
    "server.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
    "main.js",
    "main.ts",
    "main.go",
    "main.rs",
    "main.java",
    "application.java",
    "program.cs",
    "startup.cs",
    "main.kt",
    "main.c",
    "main.cpp",
    "index.html",
    "handler.py",
    "lambda_function.py",
    "handler.js",
    "handler.ts",
}
ENTRY_GLOBS = ["*application.java", "*application.kt", "bin/*", "cmd/*/main.go", "*/main.go"]
CONFIG_NAMES = {
    "application.properties",
    "application.yml",
    "application.yaml",
    "appsettings.json",
    "web.config",
    "app.config",
    "settings.py",
    "config.py",
    "config.yml",
    "config.yaml",
    "config.json",
    "tsconfig.json",
    "jest.config.js",
    "jest.config.ts",
    "vite.config.ts",
    "vite.config.js",
    "webpack.config.js",
    "next.config.js",
    "next.config.mjs",
    "babel.config.js",
    ".babelrc",
    ".eslintrc",
    ".eslintrc.json",
    ".prettierrc",
    "ruff.toml",
    ".flake8",
    "mypy.ini",
    "pytest.ini",
    "conftest.py",
    "sonar-project.properties",
    "profiles.yml",
    "sources.yml",
    "schema.yml",
    "openapi.yaml",
    "openapi.json",
    "swagger.yaml",
    "swagger.json",
    ".env.example",
    ".env.sample",
    "env.example",
    "values.yaml",
    "samconfig.toml",
    "serverless.yml",
    "logback.xml",
    "log4j2.xml",
    ".pre-commit-config.yaml",
    ".editorconfig",
    "codeowners",
}
CONFIG_GLOBS = ["config/*", "configs/*", "conf/*", "*.env.example", "appsettings.*.json"]

TEST_DIR_NAMES = {
    "test",
    "tests",
    "__tests__",
    "spec",
    "specs",
    "e2e",
    "integration",
    "integration_tests",
    "unit_tests",
    "testing",
    "cypress",
    "playwright",
}
TEST_FILE_GLOBS = [
    "test_*.py",
    "*_test.py",
    "*.test.ts",
    "*.test.tsx",
    "*.test.js",
    "*.test.jsx",
    "*.spec.ts",
    "*.spec.tsx",
    "*.spec.js",
    "*.spec.jsx",
    "*_test.go",
    "*test.java",
    "*tests.java",
    "*tests.cs",
    "*test.cs",
    "*_spec.rb",
    "*_test.rb",
    "*test.php",
    "*_test.rs",
    "*.tests.ps1",
    "*test.kt",
    "*test.scala",
]
CI_GLOBS = [
    ".github/workflows/*",
    ".gitlab-ci.yml",
    "jenkinsfile",
    "azure-pipelines*.yml",
    ".azure-pipelines/*",
    ".circleci/*",
    "bitbucket-pipelines.yml",
    ".buildkite/*",
    "cloudbuild.y*ml",
    ".travis.yml",
    "appveyor.yml",
    ".drone.yml",
    "buildspec*.yml",
    ".github/dependabot.yml",
    "renovate.json",
    ".gitlab/*",
    "codefresh.yml",
]
DOC_NAMES = {
    "readme.md",
    "readme",
    "readme.rst",
    "readme.txt",
    "contributing.md",
    "changelog.md",
    "architecture.md",
    "agents.md",
    "claude.md",
    "security.md",
    "license",
    "codeowners",
}
DOC_DIRS = {"docs", "doc", "documentation", "adr", "adrs", "decisions", "wiki"}


def _match(rel: str, name: str, patterns: list[str]) -> bool:
    low_rel, low_name = rel.lower(), name.lower()
    return any(
        fnmatch.fnmatchcase(low_rel, p) or fnmatch.fnmatchcase(low_name, p) for p in patterns
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=120)


def list_files(repo: Path) -> tuple[list[str], Optional[str]]:
    """Return tracked paths relative to ``repo`` and the HEAD commit (or None)."""
    try:
        top = git(repo, "rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        raise SystemExit(_fail(EXIT_INPUT, "git is not installed or not on PATH")) from None
    if top.returncode != 0 or top.stdout.strip() != b"true":
        raise SystemExit(_fail(EXIT_INPUT, f"not a git repository: {repo}"))
    listed = git(repo, "ls-files", "-z")
    if listed.returncode != 0:
        raise SystemExit(
            _fail(
                EXIT_MALFORMED,
                "git ls-files failed: " + listed.stderr.decode("utf-8", "replace").strip(),
            )
        )
    files = [p for p in listed.stdout.decode("utf-8", "replace").split("\0") if p]
    head = git(repo, "rev-parse", "HEAD")
    commit = head.stdout.decode().strip() if head.returncode == 0 else None
    return sorted(set(files)), commit


def _fail(code: int, message: str) -> int:
    LOG.error(message)
    return code


def language_of(name: str) -> Optional[str]:
    low = name.lower()
    if low in SPECIAL_LANGUAGE_NAMES:
        return SPECIAL_LANGUAGE_NAMES[low]
    return LANGUAGES.get(PurePosixPath(low).suffix)


def manifest_kind(rel: str) -> Optional[str]:
    name = PurePosixPath(rel).name.lower()
    if name in MANIFEST_NAMES:
        return MANIFEST_NAMES[name]
    for pattern, kind in MANIFEST_GLOBS:
        if fnmatch.fnmatchcase(name, pattern):
            return kind
    return None


def by_depth(paths: list[str]) -> list[str]:
    return sorted(paths, key=lambda p: (p.count("/"), p))


def capped(paths: list[str], key: str) -> dict[str, Any]:
    ordered = by_depth(paths)
    cap = CAPS[key]
    return {"count": len(ordered), "items": ordered[:cap], "truncated": len(ordered) > cap}


def build_areas(files: list[str], sizes: dict[str, int]) -> list[dict[str, Any]]:
    """Group files into at most MAX_AREAS areas, by top-level directory.

    One directory holding most of the files is split one level further so the
    workers get comparable slices. Small groups merge into `other`.
    """
    total = len(files)
    groups: dict[str, list[str]] = {}
    for rel in files:
        parts = rel.split("/")
        groups.setdefault(parts[0] if len(parts) > 1 else "(root files)", []).append(rel)

    def split(prefix: str, members: list[str]) -> Optional[dict[str, list[str]]]:
        depth = prefix.count("/") + 2
        children: dict[str, list[str]] = {}
        for rel in members:
            parts = rel.split("/")
            children.setdefault(
                "/".join(parts[:depth]) if len(parts) > depth else prefix + "/(files)", []
            ).append(rel)
        return children if len(children) >= 2 else None

    while len(groups) < MAX_AREAS:
        name = max(groups, key=lambda k: len(groups[k]))
        members = groups[name]
        if len(members) <= total * 0.5 or name == "(root files)" or name.endswith("/(files)"):
            break
        children = split(name, members)
        if children is None or len(groups) - 1 + len(children) > MAX_AREAS * 2:
            break
        del groups[name]
        groups.update(children)

    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    keep: list[tuple[str, list[str]]] = []
    other: list[tuple[str, list[str]]] = []
    floor = max(2, int(total * 0.02))
    for index, (name, members) in enumerate(ordered):
        if index < MAX_AREAS - 1 and len(members) >= floor:
            keep.append((name, members))
        else:
            other.append((name, members))
    if len(other) == 1 and len(keep) < MAX_AREAS:
        keep.append(other.pop())

    def describe(name: str, parts: list[tuple[str, list[str]]]) -> dict[str, Any]:
        members = [rel for _, group in parts for rel in group]
        langs = Counter(language_of(PurePosixPath(rel).name) or "other" for rel in members)
        paths = [p for p, _ in parts]
        return {
            "name": name,
            "paths": paths[:25],
            "files": len(members),
            "bytes": sum(sizes.get(rel, 0) for rel in members),
            "top_languages": [lang for lang, _ in langs.most_common(3)],
        }

    areas = [describe(name, [(name, members)]) for name, members in keep]
    if other:
        areas.append(describe("other", other))
    return areas


def scan(repo: Path, depth: int) -> Optional[dict[str, Any]]:
    files, commit = list_files(repo)
    if not files:
        return None
    sizes: dict[str, int] = {}
    for rel in files:
        try:
            sizes[rel] = (repo / rel).stat().st_size
        except OSError:
            sizes[rel] = 0

    lang_files: Counter = Counter()
    lang_bytes: Counter = Counter()
    manifests: list[str] = []
    manifest_kinds: dict[str, str] = {}
    entries: list[str] = []
    configs: list[str] = []
    test_files: list[str] = []
    test_dirs: set[str] = set()
    ci: list[str] = []
    docs: list[str] = []
    dir_total: Counter = Counter()
    dir_direct: Counter = Counter()

    for rel in files:
        pure = PurePosixPath(rel)
        name = pure.name
        low = name.lower()
        lang = language_of(name) or "(other)"
        lang_files[lang] += 1
        lang_bytes[lang] += sizes[rel]

        kind = manifest_kind(rel)
        if kind:
            manifests.append(rel)
            manifest_kinds[rel] = kind
        if low in ENTRY_NAMES or (_match(rel, name, ENTRY_GLOBS) and language_of(name)):
            entries.append(rel)
        if low in CONFIG_NAMES or _match(rel, name, CONFIG_GLOBS):
            configs.append(rel)
        parent_names = [part.lower() for part in pure.parts[:-1]]
        in_test_dir = [i for i, part in enumerate(parent_names) if part in TEST_DIR_NAMES]
        if in_test_dir or _match(rel, name, TEST_FILE_GLOBS):
            test_files.append(rel)
            if in_test_dir:
                test_dirs.add("/".join(pure.parts[: in_test_dir[0] + 1]))
            else:
                test_dirs.add(str(pure.parent) if str(pure.parent) != "." else "(root)")
        if _match(rel, name, CI_GLOBS):
            ci.append(rel)
        if low in DOC_NAMES or (
            parent_names and parent_names[0] in DOC_DIRS and low.endswith((".md", ".rst", ".txt"))
        ):
            docs.append(rel)

        parents = pure.parts[:-1]
        dir_direct["/".join(parents) or "."] += 1
        for level in range(0, len(parents) + 1):
            dir_total["/".join(parents[:level]) or "."] += 1

    tree = [
        {"path": path, "files": dir_total[path], "direct": dir_direct.get(path, 0)}
        for path in dir_total
        if path == "." or path.count("/") + 1 <= depth
    ]
    tree_cut = len(tree) > CAPS["tree"]
    if tree_cut:
        top = sorted(tree, key=lambda t: (-t["files"], t["path"]))[: CAPS["tree"]]
        tree = top
    tree.sort(key=lambda t: t["path"])

    languages = [
        {"language": lang, "files": count, "bytes": lang_bytes[lang]}
        for lang, count in sorted(lang_files.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    biggest = sorted(
        (rel for rel in files if PurePosixPath(rel).name.lower() not in LOCK_FILES),
        key=lambda rel: (-sizes[rel], rel),
    )[: CAPS["largest"]]

    manifest_view = capped(manifests, "manifests")
    manifest_view["items"] = [
        {"path": p, "kind": manifest_kinds[p]} for p in manifest_view["items"]
    ]
    test_dir_view = capped(sorted(test_dirs), "test_dirs")

    return {
        "repo": repo.name,
        "head_commit": commit,
        "totals": {
            "files": len(files),
            "bytes": sum(sizes.values()),
            "directories": len(dir_total),
        },
        "languages": {
            "items": languages[: CAPS["languages"]],
            "truncated": len(languages) > CAPS["languages"],
        },
        "manifests": manifest_view,
        "entry_points": capped(entries, "entry_points"),
        "config_files": capped(configs, "config_files"),
        "tree": {"depth": depth, "truncated": tree_cut, "directories": tree},
        "tests": {"file_count": len(test_files), "directories": test_dir_view},
        "ci_files": capped(ci, "ci_files"),
        "largest_files": [{"path": rel, "bytes": sizes[rel]} for rel in biggest],
        "docs": capped(docs, "docs"),
        "areas": build_areas(files, sizes),
    }


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        LOG.error(message)
        raise SystemExit(EXIT_USAGE)


def main(argv: Optional[list[str]] = None) -> int:
    parser = Parser(
        description=__doc__.split("\n\n")[0] if __doc__ else None,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--repo", required=True, help="path to the repository checkout")
    parser.add_argument("--depth", type=int, default=3, help="directory tree depth (default 3)")
    parser.add_argument("--out", help="write the JSON to this file instead of stdout")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    if args.depth < 1:
        return _fail(EXIT_USAGE, "--depth must be at least 1")

    repo = Path(args.repo).expanduser()
    if not repo.is_dir():
        return _fail(EXIT_INPUT, f"no such directory: {repo}")
    try:
        result = scan(repo.resolve(), args.depth)
    except SystemExit as stop:
        return int(stop.code) if isinstance(stop.code, int) else EXIT_INTERNAL
    except Exception as error:
        LOG.exception("internal error: %s", error)
        return EXIT_INTERNAL
    if result is None:
        return _fail(EXIT_FINDINGS, "the repository has no tracked files")
    text = json.dumps(result, separators=(",", ":"), ensure_ascii=False) + "\n"
    if args.out:
        try:
            Path(args.out).write_text(text, encoding="utf-8")
        except OSError as error:
            return _fail(EXIT_INPUT, f"cannot write {args.out}: {error}")
        sys.stdout.write(json.dumps({"out": args.out, "bytes": len(text.encode("utf-8"))}) + "\n")
    else:
        sys.stdout.write(text)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
