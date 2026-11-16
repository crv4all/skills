"""``scan_repo.py`` takes a deterministic, read-only inventory of a git repository."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO_ROOT
    / "skills"
    / "processes"
    / "crv-aidlc-reverse-engineering"
    / "scripts"
    / "scan_repo.py"
)


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_repo(root: Path, files: dict[str, str], commit: bool = True) -> Path:
    repo = root / "target"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test")
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    run_git(repo, "add", "-A")
    if commit:
        run_git(repo, "commit", "-q", "-m", "fixture")
    return repo


def scan(repo: Path, *extra: str) -> tuple[int, dict]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return done.returncode, json.loads(done.stdout) if done.stdout.strip() else {}


FIXTURE = {
    "README.md": "# Target\n",
    "pyproject.toml": "[project]\nname='x'\n",
    "requirements-dev.txt": "pytest\n",
    "Dockerfile": "FROM python:3.11\n",
    "src/app/main.py": "print('x')\n",
    "src/app/util.py": "x = 1\n",
    "src/web/index.ts": "export {}\n",
    "src/web/package.json": "{}\n",
    "tests/test_util.py": "def test_x(): pass\n",
    "tests/unit/test_more.py": "def test_y(): pass\n",
    ".github/workflows/ci.yml": "on: push\n",
    "docs/guide.md": "# guide\n",
    "deploy/main.tf": "terraform {}\n",
}


def test_inventory_of_a_mixed_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, FIXTURE)
    code, result = scan(repo)
    assert code == 0
    assert len(result["head_commit"]) == 40
    assert result["totals"]["files"] == len(FIXTURE)
    langs = {item["language"]: item["files"] for item in result["languages"]["items"]}
    assert langs["Python"] == 4
    assert langs["TypeScript"] == 1
    assert langs["Terraform"] == 1
    manifests = {item["path"]: item["kind"] for item in result["manifests"]["items"]}
    assert manifests["pyproject.toml"] == "python"
    assert manifests["requirements-dev.txt"] == "python"
    assert manifests["Dockerfile"] == "docker"
    assert manifests["src/web/package.json"] == "npm"
    assert manifests["deploy/main.tf"] == "terraform"
    assert "src/app/main.py" in result["entry_points"]["items"]
    assert result["ci_files"]["items"] == [".github/workflows/ci.yml"]
    assert "README.md" in result["docs"]["items"]
    assert "docs/guide.md" in result["docs"]["items"]


def test_test_layout(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, FIXTURE)
    _, result = scan(repo)
    assert result["tests"]["file_count"] == 2
    assert result["tests"]["directories"]["items"] == ["tests"]


def test_tree_respects_depth(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"a/b/c/d/deep.py": "x=1\n", "a/top.py": "x=1\n"})
    _, shallow = scan(repo, "--depth", "2")
    paths = {d["path"]: d for d in shallow["tree"]["directories"]}
    assert "a/b" in paths and "a/b/c" not in paths
    assert paths["a"]["files"] == 2 and paths["a"]["direct"] == 1
    _, deep = scan(repo, "--depth", "4")
    assert "a/b/c/d" in {d["path"] for d in deep["tree"]["directories"]}


def test_ignored_files_are_excluded(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {".gitignore": "build/\n*.log\n", "src/a.py": "x=1\n"}, commit=False)
    (repo / "build").mkdir()
    (repo / "build" / "out.js").write_text("x", encoding="utf-8")
    (repo / "debug.log").write_text("x", encoding="utf-8")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "fixture")
    _, result = scan(repo)
    assert result["totals"]["files"] == 2
    languages = {item["language"] for item in result["languages"]["items"]}
    assert "JavaScript" not in languages


def test_areas_are_capped_at_eight(tmp_path: Path) -> None:
    files = {f"mod{i}/file{j}.py": "x=1\n" for i in range(14) for j in range(6)}
    repo = make_repo(tmp_path, files)
    _, result = scan(repo)
    areas = result["areas"]
    assert 2 <= len(areas) <= 8
    assert sum(a["files"] for a in areas) == len(files)
    assert any(a["name"] == "other" for a in areas)


def test_single_big_directory_is_split(tmp_path: Path) -> None:
    files = {f"src/pkg{i}/m{j}.py": "x=1\n" for i in range(4) for j in range(10)}
    files["docs/a.md"] = "x\n"
    repo = make_repo(tmp_path, files)
    _, result = scan(repo)
    names = {a["name"] for a in result["areas"]}
    assert "src/pkg0" in names


def test_non_git_directory_exits_3(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    (tmp_path / "plain" / "a.py").write_text("x=1\n", encoding="utf-8")
    code, _ = scan(tmp_path / "plain")
    assert code == 3


def test_missing_directory_exits_3(tmp_path: Path) -> None:
    code, _ = scan(tmp_path / "nope")
    assert code == 3


def test_repo_without_tracked_files_exits_1(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {}, commit=False)
    code, _ = scan(repo)
    assert code == 1


def test_bad_flags_exit_2(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"a.py": "x=1\n"})
    code, _ = scan(repo, "--depth", "0")
    assert code == 2
    done = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert done.returncode == 2


def test_help_exits_0() -> None:
    done = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert done.returncode == 0
    assert "--repo" in done.stdout and "exit codes" in done.stdout


def test_output_is_small_and_deterministic(tmp_path: Path) -> None:
    files = {
        f"svc{i}/pkg{j}/mod{k}.py": "x=1\n" for i in range(10) for j in range(6) for k in range(8)
    }
    files.update({f"svc{i}/tests/test_{i}.py": "x=1\n" for i in range(10)})
    repo = make_repo(tmp_path, files)
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo)], capture_output=True, text=True
    )
    again = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo)], capture_output=True, text=True
    )
    assert done.stdout == again.stdout
    assert len(done.stdout.encode()) < 30_000


def test_out_file_is_written(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"a.py": "x=1\n"})
    target = tmp_path / "scan.json"
    code, summary = scan(repo, "--out", str(target))
    assert code == 0
    assert json.loads(target.read_text(encoding="utf-8"))["totals"]["files"] == 1
    assert summary["out"] == str(target)


def test_scan_does_not_change_the_repository(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, FIXTURE)
    scan(repo)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    )
    assert status.stdout == ""
