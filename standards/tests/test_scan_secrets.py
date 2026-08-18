"""The secret scanner finds credentials and never repeats them."""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scan_secrets.py"

FAKE_AWS_KEY = "AKIA" + "Q" * 16
FAKE_GITHUB_TOKEN = "ghp_" + "b" * 36
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"  # crv-allow-secret
# Synthetic values live in short named constants so the allowlist marker stays on
# the same line as the value. Inline in a call, the formatter wraps the line and
# the marker drifts away from what it was marking.
FAKE_PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n"  # crv-allow-secret
FAKE_BASIC_AUTH_URL = "postgres://admin:hunter2xyz@db.internal:5432/app"  # crv-allow-secret
FAKE_PASSWORD = "s3cretVal4e!"  # crv-allow-secret


@pytest.fixture
def scan(run_script, tmp_path):
    def _scan(content: str, name: str = "config.yml", *args: str):
        (tmp_path / name).write_text(content, encoding="utf-8")
        return run_script(SCRIPT, ["--root", str(tmp_path), str(tmp_path), *args])

    return _scan


def test_clean_tree_passes(scan):
    run = scan("host: localhost\nport: 5432\n")
    assert run.returncode == 0
    assert run.json["findings"] == []


def test_detects_private_key(scan):
    run = scan(FAKE_PRIVATE_KEY, "id_rsa")
    assert run.returncode == 1
    assert run.json["findings"][0]["code"] == "secret.private-key"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (f"aws_key = {FAKE_AWS_KEY}\n", "secret.aws-access-key-id"),
        (f"token: {FAKE_GITHUB_TOKEN}\n", "secret.github-token"),
        (f"auth: {FAKE_JWT}\n", "secret.jwt"),
        (f"url: {FAKE_BASIC_AUTH_URL}\n", "secret.basic-auth-url"),
    ],
)
def test_detects_credential_shapes(scan, content, code):
    run = scan(content)
    assert run.returncode == 1
    assert code in run.codes()


def test_never_emits_the_matched_value(scan):
    run = scan(f"aws_key = {FAKE_AWS_KEY}\n")
    assert FAKE_AWS_KEY not in run.stdout
    assert FAKE_AWS_KEY not in run.stderr
    assert "sha256:" in run.json["findings"][0]["message"]


def test_placeholders_are_not_flagged(scan):
    run = scan(
        'password: "${DB_PASSWORD}"\n'
        'api_key: "your-api-key-here"\n'
        'client_secret: "<REDACTED>"\n'
        'token: "example-token-value"\n'
    )
    assert run.returncode == 0, run.stderr


def test_hardcoded_assignment_is_flagged(scan):
    run = scan(f'password: "{FAKE_PASSWORD}"\n')
    assert run.returncode == 1
    assert "secret.generic-assignment" in run.codes()


def test_allowlist_marker_suppresses(scan):
    run = scan(f'password: "{FAKE_PASSWORD}"  # crv-allow-secret: fixture only\n')
    assert run.returncode == 0, run.stderr


def test_binary_suffixes_are_skipped(scan, tmp_path):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n" + FAKE_AWS_KEY.encode())
    run = scan("clean: true\n")
    assert run.returncode == 0


def test_missing_path_exits_input_error(run_script, tmp_path):
    run = run_script(SCRIPT, ["--root", str(tmp_path), "does-not-exist"])
    assert run.returncode == 3


def test_staged_and_paths_conflict_exits_usage(run_script, tmp_path):
    run = run_script(SCRIPT, ["--root", str(tmp_path), "--staged", "somewhere"])
    assert run.returncode == 2


def test_repository_itself_is_clean(run_script, repo_root):
    """This repository is public. The scan must be green on every commit."""
    run = run_script(SCRIPT, ["--root", str(repo_root)])
    assert run.returncode == 0, run.stderr
