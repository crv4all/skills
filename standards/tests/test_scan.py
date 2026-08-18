"""Behavioural tests for the onboarding scanner, against the fixtures.

These assert on what the scanner *finds*, and just as importantly on what it
refuses to do: no network, no project script execution, no secret values, no
modification of the target.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills" / "processes" / "crv-codebase-onboarding" / "scripts" / "scan.py"
)


@pytest.fixture
def scan(run_script, fixtures_dir):
    def _scan(fixture: str, *args: str):
        return run_script(SCRIPT, ["--root", str(fixtures_dir / fixture), "--quiet", *args])

    return _scan


def names(items):
    return [item["name"] for item in items]


# ---------------------------------------------------------------- java


def test_java_detects_maven(scan):
    payload = scan("java-spring-maven").json
    assert "maven" in names(payload["ecosystems"])
    maven = next(e for e in payload["ecosystems"] if e["name"] == "maven")
    assert maven["declared_at_root"] is True


def test_java_reads_the_module_list(scan):
    manifests = scan("java-spring-maven").json["manifests"]["maven"]
    parent = next(m for m in manifests if m["path"] == "pom.xml")
    assert sorted(parent["modules"]) == ["common", "order-api"]


def test_java_finds_the_spring_entry_point(scan):
    entry_points = scan("java-spring-maven").json["entry_points"]
    assert any(e["path"].endswith("OrderApiApplication.java") for e in entry_points)


def test_java_detects_kafka_and_postgres(scan):
    payload = scan("java-spring-maven").json
    assert "Kafka" in names(payload["messaging"])
    assert "PostgreSQL" in names(payload["datastores"])


def test_java_detects_flyway_migration_convention(scan):
    migrations = scan("java-spring-maven").json["migrations"]
    assert "flyway-naming-convention" in migrations["tools_detected"]
    assert any("db/migration" in d for d in migrations["directories"])


# ------------------------------------------------- environment variables


def test_environment_variables_are_named_never_valued(scan):
    """The whole point: the name is useful, the value is a disclosure."""
    environment = scan("java-spring-maven").json["environment"]
    variables = {v["name"]: v for v in environment["variables"]}
    assert "DATABASE_PASSWORD" in variables
    assert variables["DATABASE_PASSWORD"]["secret_like"] is True
    assert variables["DB_HOST"]["secret_like"] is False
    for variable in environment["variables"]:
        assert variable["value_captured"] is False
        assert "value" not in variable
    assert environment["policy"].startswith("names and reference sites only")


def test_environment_variables_carry_reference_sites(scan):
    variables = {v["name"]: v for v in scan("java-spring-maven").json["environment"]["variables"]}
    references = variables["DATABASE_PASSWORD"]["references"]
    assert references
    assert all(":" in reference for reference in references)


def test_terraform_secret_variables_are_flagged(scan):
    environment = scan("terraform-azure").json["environment"]
    flagged = {v["name"] for v in environment["variables"] if v["secret_like"]}
    assert "ARM_CLIENT_SECRET" in flagged
    assert "TFSTATE_ACCESS_KEY" in flagged


# ---------------------------------------------------------------- others


def test_typescript_detects_the_workspace_tooling(scan):
    payload = scan("typescript-nx-monorepo").json
    detected = names(payload["ecosystems"])
    for expected in ("node", "nx", "pnpm"):
        assert expected in detected


def test_typescript_reports_both_lockfiles(scan):
    """Two lockfiles is a real problem; the scan must surface both."""
    detected = names(scan("typescript-nx-monorepo").json["ecosystems"])
    assert "pnpm" in detected and "npm" in detected


def test_typescript_reads_package_scripts(scan):
    manifests = scan("typescript-nx-monorepo").json["manifests"]["node"]
    root = next(m for m in manifests if m["path"] == "package.json")
    assert set(root["scripts"]) == {"build", "test", "lint"}
    assert root["package_manager"].startswith("pnpm@")


def test_dbt_project_is_detected(scan):
    payload = scan("python-dbt-databricks").json
    assert "dbt" in names(payload["ecosystems"])
    dbt = payload["manifests"]["dbt"][0]
    assert dbt["project_name"] == "herd_analytics"


def test_azure_pipelines_is_detected(scan):
    systems = [s["system"] for s in scan("python-dbt-databricks").json["ci"]["systems"]]
    assert "Azure Pipelines" in systems


def test_terraform_modules_are_listed(scan):
    iac = scan("terraform-azure").json["iac"]
    assert iac["terraform_file_count"] >= 4
    assert "modules/storage" in iac["terraform_modules"]


# ---------------------------------------------------- honest degradation


def test_minimal_repository_reports_what_is_missing(scan):
    payload = scan("minimal-unknown").json
    assert payload["ecosystems"] == []
    notes = " ".join(payload["notes"])
    assert "No build-system marker" in notes
    assert "No CI configuration" in notes


def test_notes_are_present_on_every_fixture(scan, fixtures_dir):
    for fixture in sorted(p.name for p in fixtures_dir.iterdir() if p.is_dir()):
        payload = scan(fixture).json
        assert isinstance(payload["notes"], list)


# ------------------------------------------------------------ guarantees


def test_guarantees_are_declared(scan):
    guarantees = scan("java-spring-maven").json["guarantees"]
    assert guarantees == {
        "network_access": False,
        "project_scripts_executed": False,
        "secret_values_emitted": False,
        "target_modified": False,
    }


def test_target_is_not_modified(scan, fixtures_dir):
    target = fixtures_dir / "java-spring-maven"
    before = {p: p.stat().st_mtime_ns for p in sorted(target.rglob("*")) if p.is_file()}
    scan("java-spring-maven")
    after = {p: p.stat().st_mtime_ns for p in sorted(target.rglob("*")) if p.is_file()}
    assert before == after


def test_only_git_is_ever_subprocessed():
    """Static guard: the scanner must not learn to run project scripts."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    commands = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        name = getattr(target, "attr", getattr(target, "id", None))
        if name not in {"run", "call", "check_call", "check_output", "Popen", "system", "popen"}:
            continue
        assert node.args, "a subprocess call with no visible argv"
        first = node.args[0]
        assert isinstance(first, ast.List), "subprocess argv must be a literal list"
        head = first.elts[0]
        assert isinstance(head, ast.Constant), "the executable must be a literal"
        commands.append(head.value)
    assert commands == ["git"], f"unexpected subprocess executables: {commands}"


def test_no_network_imports():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"urllib", "http", "socket", "requests", "httpx", "ftplib", "smtplib", "telnetlib"}
    assert not (imported & forbidden), imported & forbidden


def test_no_git_flag_disables_git(scan):
    payload = scan("java-spring-maven", "--no-git").json
    assert payload["git"] == {"available": False, "reason": "disabled with --no-git"}


def test_output_flag_keeps_stdout_empty(run_script, fixtures_dir, tmp_path):
    target = tmp_path / "scan.json"
    run = run_script(
        SCRIPT,
        ["--root", str(fixtures_dir / "minimal-unknown"), "--output", str(target), "--quiet"],
    )
    assert run.returncode == 0
    assert run.stdout == ""
    assert target.is_file()


def test_missing_root_exits_input_error(run_script):
    assert run_script(SCRIPT, ["--root", "/nonexistent"]).returncode == 3


def test_bad_max_items_exits_usage(run_script, fixtures_dir):
    run = run_script(SCRIPT, ["--root", str(fixtures_dir / "minimal-unknown"), "--max-items", "0"])
    assert run.returncode == 2


def test_stdout_is_only_json_even_when_verbose(run_script, fixtures_dir):
    run = run_script(SCRIPT, ["--root", str(fixtures_dir / "java-spring-maven"), "--verbose"])
    run.json
    assert run.stderr.strip()
