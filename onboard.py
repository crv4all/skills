#!/usr/bin/env python3
"""Take a new person from nothing to ready to use CRV's AI-DLC skills.

Run it with ``python3 onboard.py`` (Windows: ``py onboard.py``). It is safe to run
again: a second run is the way to update everything.

It never installs software for you, never prints a private key or a passphrase,
and talks to git only over SSH. The one exception is reading the public skills
repository anonymously over https when you have no GitHub SSH access.

Flags:
  --check          change nothing, only report; exit 1 when something needs action
  --yes            take the defaults and never prompt; never create a key without
                   --generate-key
  --generate-key   allow creating an SSH key (needed together with --yes)
  --dir PATH       where the repositories go
  --planning-url   SSH url of the planning repository
  --skip-install   do not install the skills
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlparse

# --- Where things live. Change them here, or with the flag and environment variable. ---
AZURE_ORG = "crv4all"
AZURE_SSH_HOST = "ssh.dev.azure.com"
KEYS_URL = "https://dev.azure.com/crv4all/_usersSettings/keys"
ADR_REGISTRY_URL = "git@ssh.dev.azure.com:v3/crv4all/Cloudforce%20Team%20Data/adr-registry"
#: Override with the CRV_PLANNING_REPO_URL variable or the --planning-url flag.
PLANNING_REPO_URL = "git@ssh.dev.azure.com:v3/crv4all/DevOps/ai-dlc-monorepo"
SKILLS_SSH_URL = "git@github.com:crv4all/skills.git"
SKILLS_HTTPS_URL = "https://github.com/crv4all/skills.git"
KEY_NAME = "id_rsa_crv_azure"
SUCCESS_TEXT = "Shell access is not supported"
GITHUB_SUCCESS_TEXT = "successfully authenticated"
PYTHON_FLOOR = (3, 9)
TOTAL = 9
ROUNDS = 3
CHECK_SCRIPT = Path("skills") / "processes" / "crv-aidlc" / "scripts" / "check_prerequisites.py"

#: Same list as ``MANUAL_ITEMS`` in check_prerequisites.py.
MANUAL_ITEMS = (
    "Access to the target repositories of your paddock (ask the repository owner).",
    "The Jira and Confluence connector, when your paddock uses Jira.",
    "Databricks access, when a stage reads data.",
    "az login, only if you list repositories.",
)

OK, FIXED, ACTION, SKIPPED = "OK", "FIXED", "ACTION NEEDED", "SKIPPED"


# --------------------------------------------------------------------------
# Small helpers. Tests replace run(), ask() and the browser with fakes.
# --------------------------------------------------------------------------


def out(text: str = "") -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def run(
    args: list[str],
    timeout: Optional[int] = 60,
    attached: bool = False,
    input_text: Optional[str] = None,
    batch: bool = False,
) -> tuple[int, str]:
    """Run a command (an argument list, never a shell). Returns (exit code, output).

    ``attached`` leaves the terminal connected so the person can answer prompts.
    """
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if batch:
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=10")
    try:
        if attached:
            return subprocess.run(args, timeout=timeout, env=env).returncode, ""
        done = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, env=env, input=input_text,
            stdin=None if input_text is not None else subprocess.DEVNULL,
        )  # fmt: skip
    except FileNotFoundError:
        return 127, f"{args[0]} was not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except OSError as exc:
        return 126, str(exc)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def git(path: Path, *args: str, timeout: int = 120, batch: bool = False) -> tuple[int, str]:
    code, text = run(["git", "-C", str(path), *args], timeout=timeout, batch=batch)
    return code, text.strip()


def ask(question: str, default: str = "") -> str:
    shown = f" [{default}]" if default else ""
    try:
        answer = input(f"{question}{shown}: ").strip()
    except EOFError:
        return default
    return answer or default


def open_page(url: str) -> bool:
    try:
        return bool(webbrowser.open(url))
    except Exception:  # a browser that cannot start must not stop the run
        return False


def home() -> Path:
    return Path.home()


def to_ssh_url(url: str) -> Optional[str]:
    """The SSH form of an https remote on Azure DevOps or GitHub, or None."""
    parts = urlparse(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    segments = [unquote(seg) for seg in parts.path.split("/") if seg]
    if host == "github.com" and len(segments) >= 2:
        repo = segments[1][:-4] if segments[1].endswith(".git") else segments[1]
        return f"git@github.com:{segments[0]}/{repo}.git"
    if host == "dev.azure.com" and "_git" in segments:
        at = segments.index("_git")
        if at >= 1 and len(segments) > at + 1:
            org, repo = segments[0], segments[at + 1]
            project = segments[1] if at >= 2 else repo
            return f"git@{AZURE_SSH_HOST}:v3/{org}/{quote(project, safe='')}/{quote(repo, safe='')}"
    if host.endswith(".visualstudio.com") and "_git" in segments:
        org = host.split(".")[0]
        rest = [seg for seg in segments if seg != "DefaultCollection"]
        at = rest.index("_git")
        if len(rest) > at + 1:
            project = rest[0] if at >= 1 else rest[at + 1]
            repo = rest[at + 1]
            return f"git@{AZURE_SSH_HOST}:v3/{org}/{quote(project, safe='')}/{quote(repo, safe='')}"
    return None


def repo_name(url: str) -> str:
    last = url.rstrip("/").replace(":", "/").split("/")[-1]
    return unquote(last[:-4] if last.endswith(".git") else last)


def system_name() -> str:
    return platform.system()


def install_hint(tool: str) -> str:
    system = system_name()
    if system == "Darwin":
        return {
            "git": "brew install git",
            "ssh": "OpenSSH is part of macOS; check your PATH",
            "ssh-keygen": "OpenSSH is part of macOS; check your PATH",
        }.get(tool, "brew install python")
    if system == "Windows":
        return {
            "git": "winget install --id Git.Git -e",
            "ssh": "winget install --id Git.Git -e  (Git for Windows includes ssh)",
            "ssh-keygen": "winget install --id Git.Git -e  (Git for Windows includes ssh-keygen)",
        }.get(tool, "winget install --id Python.Python.3.12 -e")
    manager = "sudo apt install" if shutil.which("apt") else "sudo dnf install"
    package = {"git": "git", "ssh": "openssh-client", "ssh-keygen": "openssh-client"}
    return f"{manager} {package.get(tool, 'python3')}"


# --------------------------------------------------------------------------
# SSH: tests, key detection, config
# --------------------------------------------------------------------------


def azure_ssh_works() -> bool:
    """Batch-mode test: a working key prints 'Shell access is not supported.'"""
    args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-T", f"git@{AZURE_SSH_HOST}"]
    return SUCCESS_TEXT in run(args, timeout=25)[1]


def github_ssh_works() -> bool:
    args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-T", "git@github.com"]
    return GITHUB_SUCCESS_TEXT in run(args, timeout=25)[1]


def ssh_dir() -> Path:
    return home() / ".ssh"


def azure_block_identities(text: str) -> Optional[list[str]]:
    """IdentityFile values of the ``Host ssh.dev.azure.com`` block, or None when no such block."""
    inside = False
    found = False
    values: list[str] = []
    for raw in text.splitlines():
        words = raw.split("#")[0].split()
        if not words:
            continue
        key = words[0].lower()
        if key in ("host", "match"):
            inside = key == "host" and AZURE_SSH_HOST in words[1:]
            found = found or inside
        elif inside and key == "identityfile" and len(words) > 1:
            values.append(words[1].strip('"'))
    return values if found else None


def expand(path: str) -> Path:
    if path.startswith("~"):
        return home() / path[1:].lstrip("/\\")
    return Path(path)


def read_config() -> str:
    try:
        return (ssh_dir() / "config").read_text(encoding="utf-8")
    except OSError:
        return ""


def is_rsa_public(path: Path) -> bool:
    try:
        return path.read_text(encoding="utf-8").startswith("ssh-rsa ")
    except OSError:
        return False


def find_rsa_key() -> Optional[Path]:
    """Private key path of an existing RSA key: the one named in the config first."""
    named = azure_block_identities(read_config()) or []
    candidates = [expand(v) for v in named] + [ssh_dir() / "id_rsa", ssh_dir() / KEY_NAME]
    for private in candidates:
        if is_rsa_public(private.with_name(private.name + ".pub")):
            return private
    return None


def other_keys(key: Path) -> list[Path]:
    try:
        names = sorted(p for p in ssh_dir().iterdir() if p.name.startswith("id_"))
    except OSError:
        return []
    return [p for p in names if p.suffix != ".pub" and p.name != key.name]


def needs_config_block(key: Path) -> bool:
    """Azure DevOps takes only the first key offered, so a non-default or crowded setup needs it."""
    return key != ssh_dir() / "id_rsa" or bool(other_keys(key))


def add_config_block(key: Path) -> str:
    """Add the Host block once. Returns 'added', 'exists' (left alone) or 'same' (already ours)."""
    existing = read_config()
    identities = azure_block_identities(existing)
    if identities is not None:
        mine = [expand(v) for v in identities]
        return "same" if key in mine else "exists"
    folder = ssh_dir()
    folder.mkdir(parents=True, exist_ok=True)
    block = (
        f"Host {AZURE_SSH_HOST}\n"
        f"  IdentityFile ~/.ssh/{key.name}\n"
        "  IdentitiesOnly yes\n"
    )  # fmt: skip
    path = folder / "config"
    new = not path.exists()
    prefix = (
        ""
        if not existing or existing.endswith("\n\n")
        else ("\n" if existing.endswith("\n") else "\n\n")
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(prefix + block)
    if new:
        restrict(path)
    return "added"


def restrict(path: Path) -> None:
    """Owner-only permissions where the system supports them."""
    if os.name != "nt":
        with contextlib.suppress(OSError):
            path.chmod(0o700 if path.is_dir() else 0o600)


def clipboard_command() -> Optional[list[str]]:
    for tool, args in (
        ("pbcopy", ["pbcopy"]),
        ("clip", ["clip"]),
        ("wl-copy", ["wl-copy"]),
        ("xclip", ["xclip", "-selection", "clipboard"]),
    ):
        if shutil.which(tool):
            return args
    return None


def copy_to_clipboard(text: str) -> bool:
    command = clipboard_command()
    return command is not None and run(command, input_text=text)[0] == 0


# --------------------------------------------------------------------------
# Result bookkeeping
# --------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[int, str, str, str]] = []
        self.titles: dict[int, str] = {}

    def begin(self, n: int, title: str) -> None:
        self.titles[n] = title
        out(f"[{n}/{TOTAL}] {title}")

    def done(self, n: int, status: str, detail: str) -> None:
        self.rows.append((n, self.titles.get(n, ""), status, detail))
        out(f"  {status}: {detail}")

    def needs_action(self) -> bool:
        return any(status == ACTION for _n, _t, status, _d in self.rows)


class Options:
    def __init__(self, args: argparse.Namespace) -> None:
        self.check: bool = args.check
        self.yes: bool = args.yes
        self.generate_key: bool = args.generate_key
        self.dir: Optional[str] = args.dir
        self.planning_url: str = args.planning_url
        self.skip_install: bool = args.skip_install

    @property
    def interactive(self) -> bool:
        return not (self.yes or self.check)


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------


def step_tools(report: Report) -> bool:
    report.begin(1, "Tools: Python, git, ssh, ssh-keygen")
    missing = [t for t in ("git", "ssh", "ssh-keygen") if shutil.which(t) is None]
    old = sys.version_info[:2] < PYTHON_FLOOR
    want = ".".join(map(str, PYTHON_FLOOR))
    if old:
        out(f"  Python {sys.version_info[0]}.{sys.version_info[1]} is too old, need {want}: "
            f"{install_hint('python')}")  # fmt: skip
    for tool in missing:
        out(f"  {tool} is missing. Install it with: {install_hint(tool)}")
    if missing or old:
        report.done(1, ACTION, "install what is listed above, then run this script again")
        return False
    report.done(1, OK, f"Python {sys.version_info[0]}.{sys.version_info[1]}, git, ssh, ssh-keygen")
    return True


def step_identity(report: Report, opts: Options) -> None:
    report.begin(2, "Git identity")
    values: dict[str, str] = {}
    for key in ("user.name", "user.email"):
        values[key] = run(["git", "config", "--global", "--get", key])[1].strip()
    absent = [k for k, v in values.items() if not v]
    if not absent:
        report.done(2, OK, f"{values['user.name']} <{values['user.email']}>")
        return
    if not opts.interactive:
        cmds = "; ".join(f'git config --global {k} "<your {k.split(".")[1]}>"' for k in absent)
        report.done(2, ACTION, f"not set: {', '.join(absent)}. Run: {cmds}")
        return
    for key in absent:
        value = ask(f"Your {key.split('.')[1]} for git commits")
        if not value:
            report.done(2, ACTION, f'{key} is empty. Run: git config --global {key} "<value>"')
            return
        run(["git", "config", "--global", key, value])
    report.done(2, FIXED, "git identity set")


def git_email() -> str:
    return run(["git", "config", "--global", "--get", "user.email"])[1].strip()


def step_ssh(report: Report, opts: Options) -> bool:
    report.begin(3, "SSH to Azure DevOps")
    if azure_ssh_works():
        report.done(3, OK, f"git@{AZURE_SSH_HOST} accepts your key")
        return True
    if opts.check:
        report.done(3, ACTION, "Azure DevOps does not accept your SSH key. Run: python3 onboard.py")
        return False
    for attempt in range(1, ROUNDS + 1):
        out(f"  Setting up your key (round {attempt} of {ROUNDS})")
        key = find_rsa_key()
        if key is None:
            if opts.yes and not opts.generate_key:
                report.done(3, ACTION, "no RSA key found. Run: python3 onboard.py --yes "
                            "--generate-key  (or run it without --yes)")  # fmt: skip
                return False
            key = generate_key(report, opts)
            if key is None:
                return False
        if needs_config_block(key):
            result = add_config_block(key)
            if result == "added":
                out(f"  Added a Host {AZURE_SSH_HOST} block to ~/.ssh/config (key {key.name}).")
            elif result == "exists":
                out(f"  ~/.ssh/config already has a Host {AZURE_SSH_HOST} block. It was left "
                    f"unchanged. Check it names {key} and has IdentitiesOnly yes.")  # fmt: skip
        if not register_key(key, opts):
            report.done(3, ACTION, f"register {key.name}.pub at {KEYS_URL}, then run this again")
            return False
        out("  Testing the connection. If ssh asks to trust the host, compare the fingerprint it")
        out(f"  shows with the one on {KEYS_URL}, and answer yes only if they match.")
        run(["ssh", "-T", f"git@{AZURE_SSH_HOST}"], timeout=300, attached=True)
        if azure_ssh_works():
            report.done(3, FIXED, f"git@{AZURE_SSH_HOST} accepts {key.name}")
            return True
        if attempt < ROUNDS:
            out("  Still not accepted. Check that you saved the key (not just pasted it).")
            ask("Press Enter to try again")
    report.done(3, ACTION, "Azure DevOps still refuses the key. Check: the wrong key is offered "
                "(ssh -v), the key expired, or you have no access to the organisation "
                f"{AZURE_ORG}. A key with a passphrase needs ssh-add.")  # fmt: skip
    return False


def generate_key(report: Report, opts: Options) -> Optional[Path]:
    key = ssh_dir() / KEY_NAME
    if key.exists() or key.with_name(key.name + ".pub").exists():
        report.done(3, ACTION, f"{key} already exists but is not a usable RSA key pair. "
                    "Move it away and run this again.")  # fmt: skip
        return None
    if opts.interactive and ask("No RSA key found. Create one now? (y/n)", "y").lower() != "y":
        report.done(3, ACTION, "an RSA key is needed. Azure DevOps does not accept ed25519")
        return None
    email = git_email() or "crv"
    ssh_dir().mkdir(parents=True, exist_ok=True)
    restrict(ssh_dir())
    out("  Creating the key. ssh-keygen will ask for a passphrase: choose one you can remember.")
    args = ["ssh-keygen", "-t", "rsa", "-b", "4096", "-C", email, "-f", str(key)]
    run(args, timeout=600, attached=True)
    if not is_rsa_public(key.with_name(key.name + ".pub")):
        report.done(3, ACTION, "the key was not created. Run: " + " ".join(args))
        return None
    return key


def register_key(key: Path, opts: Options) -> bool:
    """Show the public key, open the page, wait. False when the person must come back later."""
    pub = key.with_name(key.name + ".pub")
    try:
        text = pub.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if copy_to_clipboard(text):
        out("  Your public key is copied to the clipboard.")
    else:
        out("  Copy this public key (it is safe to share):")
        out(text)
    if not open_page(KEYS_URL):
        out(f"  Open this page in your browser: {KEYS_URL}")
    out("  On that page: sign in, click New Key (or Add key), paste the key, then click Save.")
    if not opts.interactive:
        return False
    ask("Press Enter when the key is saved")
    return True


def default_workspace() -> Path:
    here = Path(__file__).resolve().parent
    if (here / ".git").exists():
        return here.parent
    return home() / "crv"


def step_workspace(report: Report, opts: Options) -> Path:
    report.begin(4, "Workspace folder")
    default = Path(opts.dir).expanduser() if opts.dir else default_workspace()
    chosen = default
    if opts.interactive and not opts.dir:
        chosen = Path(ask("Where should the repositories go?", str(default))).expanduser()
    chosen = chosen.resolve()
    if chosen.is_dir():
        report.done(4, OK, str(chosen))
    elif opts.check:
        report.done(4, ACTION, f"{chosen} does not exist. Run: python3 onboard.py")
    else:
        chosen.mkdir(parents=True, exist_ok=True)
        report.done(4, FIXED, f"created {chosen}")
    return chosen


def clone_or_update(name: str, url: str, path: Path, opts: Options, who: str) -> tuple[str, str]:
    """Clone or update one repository over SSH. Returns (status, detail)."""
    if not path.exists() or not any(path.iterdir()):
        if opts.check:
            return ACTION, f"{name}: not cloned yet. Run: python3 onboard.py"
        code, text = run(["git", "clone", url, str(path)], timeout=600, batch=opts.yes)
        if code != 0:
            return ACTION, (
                f"{name}: could not clone {url}. The repository may not exist yet or you may "
                f"have no access. Ask {who}. ({last_line(text)})"
            )
        return FIXED, f"{name}: cloned"
    if not (path / ".git").exists():
        return ACTION, f"{name}: {path} exists but is not a git checkout. Move it away"
    notes: list[str] = []
    remote = git(path, "remote", "get-url", "origin")[1]
    ssh = to_ssh_url(remote) if remote else None
    if ssh and "dev.azure.com" in remote.lower():
        if opts.check:
            return (
                ACTION,
                f"{name}: remote uses https. Run: git -C {path} remote set-url origin {ssh}",
            )
        git(path, "remote", "set-url", "origin", ssh)
        notes.append("remote changed from https to SSH")
    if opts.check:
        return OK, f"{name}: present"
    code, text = git(path, "fetch", "--quiet", timeout=300, batch=opts.yes)
    if code != 0:
        return ACTION, (
            f"{name}: could not fetch. Check your access, or ask {who}. ({last_line(text)})"
        )
    behind = git(path, "rev-list", "--count", "HEAD..@{u}")
    count = int(behind[1]) if behind[0] == 0 and behind[1].isdigit() else 0
    if count == 0:
        return (FIXED if notes else OK), "; ".join([f"{name}: up to date", *notes])
    if git(path, "status", "--porcelain")[1]:
        notes.append(f"has local changes, so it was left {count} commits behind")
        return ACTION, f"{name}: " + "; ".join(notes)
    if git(path, "merge", "--ff-only", "@{u}")[0] != 0:
        return ACTION, f"{name}: cannot fast-forward (it has local commits). Left as it is"
    return FIXED, "; ".join([f"{name}: updated by {count} commits", *notes])


def last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else "no detail"


def step_repos(
    report: Report, opts: Options, workspace: Path, azure_ok: bool
) -> tuple[Path, Path, Path]:
    report.begin(5, "Clone or update: ADR registry, planning repo, skills")
    registry = workspace / repo_name(ADR_REGISTRY_URL)
    planning = workspace / repo_name(opts.planning_url)
    here = Path(__file__).resolve().parent
    skills = here if (here / "install.sh").is_file() and (here / ".git").exists() else (
        workspace / "skills"
    )  # fmt: skip
    results: list[tuple[str, str]] = []
    for name, url, path, who in (
        (
            "ADR registry",
            ADR_REGISTRY_URL,
            registry,
            "the owner of the Cloudforce Team Data project",
        ),
        ("planning repo", opts.planning_url, planning, "the AI-DLC process owner"),
    ):
        if not azure_ok:
            results.append((ACTION, f"{name}: skipped, SSH to Azure DevOps is not working yet"))
        else:
            results.append(clone_or_update(name, url, path, opts, who))
    results.append(skills_repo(opts, skills))
    for status, detail in results:
        out(f"  {status}: {detail}")
    worst = ACTION if any(s == ACTION for s, _ in results) else (
        FIXED if any(s == FIXED for s, _ in results) else OK
    )  # fmt: skip
    report.done(5, worst, "; ".join(d for _s, d in results))
    return registry, planning, skills


def skills_repo(opts: Options, path: Path) -> tuple[str, str]:
    if (path / ".git").exists():
        return clone_or_update("skills", SKILLS_SSH_URL, path, opts, "the AI-DLC process owner")
    if github_ssh_works():
        url, why = SKILLS_SSH_URL, "GitHub accepted your SSH key"
    else:
        url, why = (
            SKILLS_HTTPS_URL,
            "GitHub SSH is not set up, so the public repository is read-only",
        )
    out(f"  Skills source: {url} ({why})")
    return clone_or_update("skills", url, path, opts, "the AI-DLC process owner")


def planning_branch(planning: Path) -> Optional[str]:
    try:
        data = json.loads((planning / "aidlc.json").read_text(encoding="utf-8"))
        branch = data["git"]["branch"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return branch if isinstance(branch, str) and branch else None


def step_branch(report: Report, opts: Options, planning: Path) -> None:
    report.begin(6, "Planning repo branch")
    if not (planning / ".git").exists():
        report.done(6, SKIPPED, "the planning repo is not cloned")
        return
    wanted = planning_branch(planning)
    if wanted is None:
        report.done(6, OK, "aidlc.json names no branch")
        return
    current = git(planning, "symbolic-ref", "--short", "HEAD")[1]
    if current == wanted:
        report.done(6, OK, f"on {wanted}")
        return
    if opts.check:
        report.done(6, ACTION, f"on {current or 'no branch'}, wanted {wanted}. "
                    f"Run: git -C {planning} switch {wanted}")  # fmt: skip
        return
    if git(planning, "status", "--porcelain")[1]:
        report.done(6, ACTION, f"has local changes, so it stayed on {current}. "
                    f"Set them aside, then: git -C {planning} switch {wanted}")  # fmt: skip
        return
    local = git(planning, "rev-parse", "--verify", "--quiet", f"refs/heads/{wanted}")[0] == 0
    if local:
        code, text = git(planning, "switch", wanted)
    else:
        code, text = git(planning, "switch", "--track", "-c", wanted, f"origin/{wanted}")
    if code != 0:
        report.done(6, ACTION, f"could not switch to {wanted} ({last_line(text)})")
        return
    report.done(6, FIXED, f"switched to {wanted}")


def find_bash() -> Optional[str]:
    if os.name != "nt":
        return shutil.which("bash") or shutil.which("sh")
    git_exe = shutil.which("git")
    if git_exe:
        base = Path(git_exe).resolve().parent.parent
        for candidate in (base / "bin" / "bash.exe", base / "usr" / "bin" / "bash.exe"):
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash")


def harnesses_found() -> list[str]:
    found = []
    for name in ("claude", "cursor"):
        if shutil.which(name) or (home() / f".{name}").is_dir():
            found.append(name)
    return found


def step_install(report: Report, opts: Options, skills: Path) -> None:
    report.begin(7, "Install the skills (Claude Code and Cursor)")
    if opts.skip_install:
        report.done(7, SKIPPED, "--skip-install")
        return
    if opts.check:
        report.done(7, SKIPPED, "--check changes nothing; step 8 shows whether they are current")
        return
    script = skills / "install.sh"
    if not script.is_file():
        report.done(7, ACTION, f"{script} not found: the skills repository is not cloned")
        return
    tools = harnesses_found()
    if not tools:
        report.done(7, ACTION, "neither Claude Code nor Cursor was found. Install one, "
                    "then run this again")  # fmt: skip
        return
    command = f"sh {script} --all --harness {','.join(tools)}"
    bash = find_bash()
    if bash is None:
        report.done(7, ACTION, "no bash found. Install Git for Windows, or run in Git Bash: "
                    f"{command}")  # fmt: skip
        return
    args = [bash, script.as_posix(), "--all", "--harness", ",".join(tools),
            "--source", skills.as_posix()]  # fmt: skip
    code, text = run(args, timeout=600)
    if code == 0:
        report.done(7, OK, f"installed for {', '.join(tools)}")
    elif code == 1:
        report.done(7, ACTION, "some skills have local changes and were skipped. To replace "
                    f"them, run: {command} --force")  # fmt: skip
    else:
        report.done(7, ACTION, f"install.sh failed ({last_line(text)}). Run by hand: {command}")


def step_prerequisites(report: Report, opts: Options, skills: Path, planning: Path) -> None:
    report.begin(8, "Readiness check")
    script = skills / CHECK_SCRIPT
    if not script.is_file():
        report.done(8, SKIPPED, "the skills repository is not cloned")
        return
    args = [sys.executable, str(script), "--root", str(planning), "--skills-checkout", str(skills)]
    scratch = None
    if opts.check:  # the checker remembers its verdict in a small file; --check writes nothing
        scratch = tempfile.mkdtemp(prefix="crv-aidlc-")
        args += ["--marker-dir", scratch]
    try:
        code, text = run(args, timeout=240)
    finally:
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
    out(text.rstrip())
    if code == 0:
        report.done(8, OK, "all required checks pass")
    else:
        report.done(8, ACTION, "a required check failed, see the table above")


def finish(report: Report, planning: Path) -> int:
    out()
    out("Summary")
    for n, title, status, detail in report.rows:
        out(f"  [{n}/{TOTAL}] {status:<13} {title}")
        if status == ACTION:
            out(f"      {detail}")
    out()
    report.begin(9, "Done")
    if report.needs_action():
        report.done(9, ACTION, "fix the ACTION NEEDED items above, then run this again")
    else:
        report.done(9, OK, f"Next: open {planning} in your editor and ask "
                    '"am I ready to use AI-DLC?"')  # fmt: skip
    out()
    out("Only you can arrange these:")
    for item in MANUAL_ITEMS:
        out(f"  MANUAL: {item}")
    return 1 if report.needs_action() else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Take a new person from nothing to ready to use CRV's AI-DLC skills.",
        epilog="Safe to run again: a second run updates everything.",
    )
    parser.add_argument(
        "--check", action="store_true", help="Change nothing; exit 1 if action needed."
    )
    parser.add_argument("--yes", action="store_true", help="Take defaults, never prompt.")
    parser.add_argument(
        "--generate-key", action="store_true", help="With --yes, allow creating a key."
    )
    parser.add_argument("--dir", help="Where the repositories go.")
    parser.add_argument(
        "--planning-url",
        default=os.environ.get("CRV_PLANNING_REPO_URL") or PLANNING_REPO_URL,
        help="SSH url of the planning repository (env: CRV_PLANNING_REPO_URL).",
    )
    parser.add_argument("--skip-install", action="store_true", help="Do not install the skills.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    opts = Options(build_parser().parse_args(argv))
    report = Report()
    if not step_tools(report):
        return finish(report, Path("<planning repo>"))
    step_identity(report, opts)
    azure_ok = step_ssh(report, opts)
    workspace = step_workspace(report, opts)
    _registry, planning, skills = step_repos(report, opts, workspace, azure_ok)
    step_branch(report, opts, planning)
    step_install(report, opts, skills)
    step_prerequisites(report, opts, skills, planning)
    return finish(report, planning)


if __name__ == "__main__":
    sys.exit(main())
