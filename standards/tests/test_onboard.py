"""``onboard.py`` takes a new person to ready. Everything here uses fakes and a temporary HOME."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "skills" / "processes" / "crv-aidlc" / "scripts"
AZURE_HTTPS = "https://crv4all@dev.azure.com/crv4all/Cloudforce%20Team%20Data/_git/adr-registry"
AZURE_SSH = "git@ssh.dev.azure.com:v3/crv4all/Cloudforce%20Team%20Data/adr-registry"
RSA_PUB = "ssh-rsa AAAAB3Nza test@example.com\n"


def load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    loader: Any = spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


@pytest.fixture
def ob(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    module = load(REPO_ROOT / "onboard.py", "onboard_under_test")
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setattr(module, "home", lambda: fake_home)
    monkeypatch.setattr(module, "open_page", lambda url: True)

    def no_prompt(*_a: Any, **_k: Any) -> str:
        raise AssertionError("the script prompted")

    monkeypatch.setattr(module, "ask", no_prompt)
    return module


class Fake:
    """Records every command and answers from scripted (substring, result) rules."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.rules: list[tuple[str, tuple[int, str]]] = []
        self.inputs: list[Optional[str]] = []

    def on(self, text: str, code: int = 0, output: str = "") -> None:
        self.rules.append((text, (code, output)))

    def __call__(self, args: list[str], **kwargs: Any) -> tuple[int, str]:
        self.calls.append(list(args))
        self.inputs.append(kwargs.get("input_text"))
        line = " ".join(args)
        for text, result in self.rules:
            if text in line:
                return result
        return 0, ""

    def ran(self, text: str) -> bool:
        return any(text in " ".join(call) for call in self.calls)


@pytest.fixture
def fake(ob: Any, monkeypatch: pytest.MonkeyPatch) -> Fake:
    f = Fake()
    monkeypatch.setattr(ob, "run", f)
    return f


def options(ob: Any, *argv: str) -> Any:
    return ob.Options(ob.build_parser().parse_args(list(argv)))


def ssh_dir(ob: Any) -> Path:
    return ob.ssh_dir()


# --- key detection and the decision to generate ---------------------------------------


def test_no_key_means_none_is_found(ob: Any) -> None:
    assert ob.find_rsa_key() is None
    (ssh_dir(ob)).mkdir()
    (ssh_dir(ob) / "id_ed25519.pub").write_text("ssh-ed25519 AAAA x\n")
    assert ob.find_rsa_key() is None  # Azure DevOps does not take ed25519


def test_the_default_rsa_key_is_found(ob: Any) -> None:
    ssh_dir(ob).mkdir()
    (ssh_dir(ob) / "id_rsa.pub").write_text(RSA_PUB)
    assert ob.find_rsa_key() == ssh_dir(ob) / "id_rsa"


def test_a_key_named_in_the_azure_block_wins(ob: Any) -> None:
    ssh_dir(ob).mkdir()
    (ssh_dir(ob) / "id_rsa.pub").write_text(RSA_PUB)
    (ssh_dir(ob) / "work_key.pub").write_text(RSA_PUB)
    (ssh_dir(ob) / "config").write_text(
        "Host ssh.dev.azure.com\n  IdentityFile ~/.ssh/work_key\n  IdentitiesOnly yes\n"
    )
    assert ob.find_rsa_key() == ssh_dir(ob) / "work_key"


def test_the_block_is_needed_only_for_a_non_default_or_crowded_setup(ob: Any) -> None:
    ssh_dir(ob).mkdir()
    default = ssh_dir(ob) / "id_rsa"
    assert not ob.needs_config_block(default)
    (ssh_dir(ob) / "id_ed25519").write_text("x")
    assert ob.needs_config_block(default)
    assert ob.needs_config_block(ssh_dir(ob) / ob.KEY_NAME)


# --- the ssh config block --------------------------------------------------------------


def test_the_config_block_is_added_once(ob: Any) -> None:
    key = ssh_dir(ob) / ob.KEY_NAME
    assert ob.add_config_block(key) == "added"
    first = (ssh_dir(ob) / "config").read_text()
    assert "Host ssh.dev.azure.com" in first and "IdentitiesOnly yes" in first
    assert f"IdentityFile ~/.ssh/{ob.KEY_NAME}" in first
    assert ob.add_config_block(key) == "same"
    assert (ssh_dir(ob) / "config").read_text() == first
    if os.name != "nt":
        assert (ssh_dir(ob) / "config").stat().st_mode & 0o077 == 0


def test_an_existing_block_for_the_host_is_left_alone(ob: Any) -> None:
    ssh_dir(ob).mkdir()
    original = "Host ssh.dev.azure.com\n  IdentityFile ~/.ssh/other\n\nHost x\n  User y\n"
    (ssh_dir(ob) / "config").write_text(original)
    assert ob.add_config_block(ssh_dir(ob) / ob.KEY_NAME) == "exists"
    assert (ssh_dir(ob) / "config").read_text() == original


def test_other_config_content_is_kept(ob: Any) -> None:
    ssh_dir(ob).mkdir()
    (ssh_dir(ob) / "config").write_text("Host github.com\n  User git")
    ob.add_config_block(ssh_dir(ob) / ob.KEY_NAME)
    text = (ssh_dir(ob) / "config").read_text()
    assert text.startswith("Host github.com\n  User git\n") and "ssh.dev.azure.com" in text


# --- url rewriting ---------------------------------------------------------------------


def test_https_to_ssh_for_azure_devops(ob: Any) -> None:
    assert ob.to_ssh_url(AZURE_HTTPS) == AZURE_SSH  # org@ form with %20
    raw = "https://dev.azure.com/crv4all/Cloudforce Team Data/_git/adr-registry"
    assert ob.to_ssh_url(raw) == AZURE_SSH
    assert ob.to_ssh_url("https://dev.azure.com/crv4all/DevOps/_git/ai-dlc-monorepo") == (
        "git@ssh.dev.azure.com:v3/crv4all/DevOps/ai-dlc-monorepo"
    )
    assert ob.to_ssh_url(AZURE_SSH) is None
    assert (
        ob.to_ssh_url("https://github.com/crv4all/skills.git")
        == "git@github.com:crv4all/skills.git"
    )


def test_the_url_helpers_agree_across_the_three_scripts(ob: Any) -> None:
    others = [
        load(SCRIPTS / "check_prerequisites.py", "cp_agree"),
        load(SCRIPTS / "build_adr_index.py", "bai_agree"),
    ]
    for url in (AZURE_HTTPS, "https://github.com/crv4all/skills", AZURE_SSH, "nonsense"):
        assert {m.to_ssh_url(url) for m in (ob, *others)} == {ob.to_ssh_url(url)}
    assert tuple(others[0].MANUAL_ITEMS) == tuple(ob.MANUAL_ITEMS)


def test_the_planning_repo_default_and_overrides(ob: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    default = "git@ssh.dev.azure.com:v3/crv4all/DevOps/ai-dlc-monorepo"
    assert default == ob.PLANNING_REPO_URL
    assert options(ob).planning_url == default
    assert options(ob, "--planning-url", "git@x:y/z").planning_url == "git@x:y/z"
    monkeypatch.setenv("CRV_PLANNING_REPO_URL", "git@env:a/b")
    assert options(ob).planning_url == "git@env:a/b"


# --- clipboard and browser fallbacks ---------------------------------------------------


@pytest.mark.parametrize(
    ("tool", "expected"),
    [("pbcopy", ["pbcopy"]), ("clip", ["clip"]), ("wl-copy", ["wl-copy"]),
     ("xclip", ["xclip", "-selection", "clipboard"])],
)  # fmt: skip
def test_clipboard_tools(
    ob: Any, monkeypatch: pytest.MonkeyPatch, tool: str, expected: list[str]
) -> None:
    monkeypatch.setattr(ob.shutil, "which", lambda name: f"/bin/{name}" if name == tool else None)
    assert ob.clipboard_command() == expected


def prepare_key(ob: Any) -> Path:
    ssh_dir(ob).mkdir()
    (ssh_dir(ob) / "id_rsa.pub").write_text(RSA_PUB)
    return ssh_dir(ob) / "id_rsa"


def test_without_a_clipboard_the_public_key_is_printed(
    ob: Any, fake: Fake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ob.shutil, "which", lambda name: None)
    ob.register_key(prepare_key(ob), options(ob, "--yes"))
    text = capsys.readouterr().out
    assert RSA_PUB.strip() in text and "New Key" in text and "Save" in text


def test_with_a_clipboard_the_key_is_copied_not_printed(
    ob: Any, fake: Fake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        ob.shutil, "which", lambda name: "/bin/pbcopy" if name == "pbcopy" else None
    )
    ob.register_key(prepare_key(ob), options(ob, "--yes"))
    assert fake.inputs[0] == RSA_PUB.strip() and RSA_PUB.strip() not in capsys.readouterr().out


def test_without_a_browser_the_page_address_is_printed(
    ob: Any, fake: Fake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ob.shutil, "which", lambda name: None)
    monkeypatch.setattr(ob, "open_page", lambda url: False)
    ob.register_key(prepare_key(ob), options(ob, "--yes"))
    assert ob.KEYS_URL in capsys.readouterr().out


def test_a_browser_that_raises_is_not_fatal(ob: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    real = load(REPO_ROOT / "onboard.py", "onboard_browser")

    def boom(_url: str) -> bool:
        raise RuntimeError("no browser")

    monkeypatch.setattr(real.webbrowser, "open", boom)
    assert real.open_page("https://example.test") is False


# --- generating a key ------------------------------------------------------------------


def make_keygen(ob: Any, fake: Fake) -> Callable[[list[str]], None]:
    def after(args: list[str]) -> None:
        if args[0] == "ssh-keygen":
            target = Path(args[args.index("-f") + 1])
            target.write_text("PRIVATE")
            target.with_name(target.name + ".pub").write_text(RSA_PUB)

    return after


def test_yes_alone_never_generates_a_key(ob: Any, fake: Fake) -> None:
    fake.on("ssh -o BatchMode", 255, "Permission denied (publickey).")
    report = ob.Report()
    assert ob.step_ssh(report, options(ob, "--yes")) is False
    assert not fake.ran("ssh-keygen") and "--generate-key" in report.rows[-1][3]
    assert not (ssh_dir(ob) / "config").exists()


def test_generate_key_creates_an_rsa_key_and_the_block(
    ob: Any, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake.on("ssh -o BatchMode", 255, "Permission denied (publickey).")
    fake.on("user.email", 0, "me@example.com\n")
    after = make_keygen(ob, fake)
    original = ob.run

    def run_and_create(args: list[str], **kwargs: Any) -> tuple[int, str]:
        result = original(args, **kwargs)
        after(args)
        return result

    monkeypatch.setattr(ob, "run", run_and_create)
    report = ob.Report()
    assert ob.step_ssh(report, options(ob, "--yes", "--generate-key")) is False  # not registered
    keygen = next(c for c in fake.calls if c[0] == "ssh-keygen")
    assert keygen[1:7] == ["-t", "rsa", "-b", "4096", "-C", "me@example.com"]
    assert keygen[-1] == str(ssh_dir(ob) / ob.KEY_NAME)
    assert "IdentitiesOnly yes" in (ssh_dir(ob) / "config").read_text()
    assert "PRIVATE" not in "".join(str(c) for c in fake.calls)


def test_an_existing_key_file_is_never_overwritten(ob: Any, fake: Fake) -> None:
    fake.on("ssh -o BatchMode", 255, "Permission denied (publickey).")
    ssh_dir(ob).mkdir()
    (ssh_dir(ob) / ob.KEY_NAME).write_text("MINE")
    report = ob.Report()
    assert ob.step_ssh(report, options(ob, "--yes", "--generate-key")) is False
    assert not fake.ran("ssh-keygen") and (ssh_dir(ob) / ob.KEY_NAME).read_text() == "MINE"


def test_a_working_connection_is_ok_and_touches_nothing(ob: Any, fake: Fake) -> None:
    fake.on("ssh -o BatchMode", 1, "remote: Shell access is not supported.")
    report = ob.Report()
    assert ob.step_ssh(report, options(ob)) is True and report.rows[-1][2] == "OK"
    assert not ssh_dir(ob).exists()


# --- --check changes nothing -----------------------------------------------------------


def test_check_changes_nothing_and_exits_1(
    ob: Any, fake: Fake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ob.shutil, "which", lambda name: f"/bin/{name}")
    fake.on("ssh -o BatchMode", 255, "Permission denied (publickey).")
    workspace = tmp_path / "ws"
    code = ob.main(["--check", "--dir", str(workspace)])
    assert code == 1
    assert not workspace.exists() and not ssh_dir(ob).exists()
    forbidden = (
        "clone",
        "ssh-keygen",
        "set-url",
        "merge",
        "switch",
        "fetch",
        "config --global user",
    )
    assert not any(fake.ran(word) for word in forbidden), fake.calls


def test_check_exits_0_when_everything_is_in_place(
    ob: Any, fake: Fake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ob.shutil, "which", lambda name: f"/bin/{name}")
    fake.on("ssh -o BatchMode", 1, "remote: Shell access is not supported.")
    fake.on("config --global --get user.name", 0, "Me\n")
    fake.on("config --global --get user.email", 0, "me@example.com\n")
    workspace = tmp_path / "ws"
    for name in ("adr-registry", "ai-dlc-monorepo", "skills"):
        (workspace / name / ".git").mkdir(parents=True)
    monkeypatch.setattr(ob, "__file__", str(workspace / "skills" / "onboard.py"))
    code = ob.main(["--check", "--dir", str(workspace), "--skip-install"])
    assert code == 0 and not fake.ran("clone")


# --- --yes never prompts ---------------------------------------------------------------


def test_yes_reports_a_missing_identity_instead_of_asking(ob: Any, fake: Fake) -> None:
    report = ob.Report()
    ob.step_identity(report, options(ob, "--yes"))
    assert (
        report.rows[-1][2] == "ACTION NEEDED"
        and "git config --global user.name" in report.rows[-1][3]
    )


def test_a_missing_identity_is_asked_and_set(
    ob: Any, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ob, "ask", lambda question, default="": "Ana")
    report = ob.Report()
    ob.step_identity(report, options(ob))
    assert report.rows[-1][2] == "FIXED" and fake.ran("config --global user.name Ana")


# --- clone or update, over SSH ---------------------------------------------------------


def checkout(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    (path / ".git").mkdir(parents=True)
    return path


def test_an_https_azure_remote_is_rewritten_to_ssh(ob: Any, fake: Fake, tmp_path: Path) -> None:
    path = checkout(tmp_path)
    fake.on("remote get-url origin", 0, AZURE_HTTPS)
    fake.on("rev-list --count", 0, "0")
    status, detail = ob.clone_or_update("ADR registry", AZURE_SSH, path, options(ob, "--yes"), "x")
    assert fake.ran(f"remote set-url origin {AZURE_SSH}")
    assert status == "FIXED" and "https to SSH" in detail


def test_an_update_fast_forwards_only_a_clean_tree(ob: Any, fake: Fake, tmp_path: Path) -> None:
    path = checkout(tmp_path)
    fake.on("remote get-url origin", 0, AZURE_SSH)
    fake.on("rev-list --count", 0, "2")
    status, _ = ob.clone_or_update("r", AZURE_SSH, path, options(ob, "--yes"), "x")
    assert status == "FIXED" and fake.ran("merge --ff-only")


def test_a_dirty_tree_is_reported_and_left(ob: Any, fake: Fake, tmp_path: Path) -> None:
    path = checkout(tmp_path)
    fake.on("remote get-url origin", 0, AZURE_SSH)
    fake.on("rev-list --count", 0, "2")
    fake.on("status --porcelain", 0, " M file.md")
    status, detail = ob.clone_or_update("r", AZURE_SSH, path, options(ob, "--yes"), "x")
    assert status == "ACTION NEEDED" and "local changes" in detail and not fake.ran("merge")


def test_a_repository_without_access_is_action_needed_and_names_who_to_ask(
    ob: Any, fake: Fake, tmp_path: Path
) -> None:
    fake.on("clone", 128, "ERROR: Repository not found.")
    status, detail = ob.clone_or_update(
        "planning repo",
        ob.PLANNING_REPO_URL,
        tmp_path / "new",
        options(ob, "--yes"),
        "the process owner",
    )
    assert status == "ACTION NEEDED" and "process owner" in detail and "not found" in detail


def test_skills_use_https_only_when_github_ssh_does_not_work(
    ob: Any, fake: Fake, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.on("git@github.com", 1, "Permission denied (publickey).")
    ob.skills_repo(options(ob, "--yes"), tmp_path / "skills")
    assert fake.ran(f"clone {ob.SKILLS_HTTPS_URL}") and "read-only" in capsys.readouterr().out
    fake.calls.clear()
    fake.rules.clear()
    fake.on("git@github.com", 1, "Hi someone! You've successfully authenticated, but GitHub...")
    ob.skills_repo(options(ob, "--yes"), tmp_path / "skills2")
    assert fake.ran(f"clone {ob.SKILLS_SSH_URL}")


# --- the planning repo branch (real local git) -----------------------------------------


@pytest.fixture
def planning(ob: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for key, value in {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
    }.items():  # fmt: skip
        monkeypatch.setenv(key, value)

    def g(path: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)

    seed = tmp_path / "seed"
    seed.mkdir()
    g(seed, "init", "-q", "-b", "main")
    (seed / "aidlc.json").write_text('{"git": {"branch": "work"}}')
    g(seed, "add", ".")
    g(seed, "commit", "-q", "-m", "one")
    g(seed, "branch", "work")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(bare)], check=True)
    clone = tmp_path / "planning"
    subprocess.run(["git", "clone", "-q", str(bare), str(clone)], check=True)
    return clone


def test_the_branch_that_exists_only_on_the_remote_is_created_tracking_it(
    ob: Any, planning: Path
) -> None:
    report = ob.Report()
    ob.step_branch(report, options(ob, "--yes"), planning)
    assert report.rows[-1][2] == "FIXED"
    branch = subprocess.run(
        ["git", "-C", str(planning), "rev-parse", "--abbrev-ref", "@{u}"],
        capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip
    assert branch == "origin/work"
    ob.step_branch(report, options(ob, "--yes"), planning)
    assert report.rows[-1][2] == "OK"


def test_a_dirty_planning_repo_stays_on_its_branch(ob: Any, planning: Path) -> None:
    (planning / "aidlc.json").write_text('{"git": {"branch": "work"}} ')
    report = ob.Report()
    ob.step_branch(report, options(ob, "--yes"), planning)
    assert report.rows[-1][2] == "ACTION NEEDED"
    current = subprocess.run(
        ["git", "-C", str(planning), "symbolic-ref", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip
    assert current == "main"


def test_check_does_not_switch_the_branch(ob: Any, planning: Path) -> None:
    report = ob.Report()
    ob.step_branch(report, options(ob, "--check"), planning)
    assert report.rows[-1][2] == "ACTION NEEDED"
    assert "git -C" in report.rows[-1][3] and "switch work" in report.rows[-1][3]


# --- tools -----------------------------------------------------------------------------


def test_missing_tools_print_the_install_command_and_stop(
    ob: Any, fake: Fake, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ob.shutil, "which", lambda name: None if name == "git" else "/bin/x")
    monkeypatch.setattr(ob, "system_name", lambda: "Darwin")
    assert ob.main(["--yes"]) == 1
    text = capsys.readouterr().out
    assert "brew install git" in text and "[3/9]" not in text and not fake.calls
