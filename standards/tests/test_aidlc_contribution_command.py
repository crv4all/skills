"""``aidlc_state.py contribution`` records where an architecture contribution stands.

A contribution is a file the engineer owns (``architecture/contributions/<concern>.md``);
the command only checks its header and appends one log line. Nothing is stored in
state.json: ``status`` and ``overview`` read the headers, so a merge of two engineers'
work needs no special rule.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import test_aidlc_slices_three_clones as three
import test_aidlc_state_git as gitbase
from test_aidlc_state import Bolt, open_bolt
from test_aidlc_state_git import BOLT_ID, git, script, write

identity = gitbase.identity


def header(concern: str, status: str = "draft", owner: str = "Ana", touches: str = "Scope") -> str:
    return (
        f"# Contribution: {concern}\n\n```yaml\nconcern: {concern}\nowner: {owner}\n"
        f"status: {status}\ntouches:\n  - {touches}\naffects: []\n```\n\n## Question\n\nWhy?\n"
    )


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def put(p: Bolt, concern: str, **fields: str) -> None:
    p.write(f"architecture/contributions/{concern}.md", header(concern, **fields))


def test_it_appends_one_log_line_and_edits_nothing(bolt: Bolt) -> None:
    put(bolt, "security", status="proposed")
    before = (bolt.path / "architecture/contributions/security.md").read_bytes()
    state_before = (bolt.path / "state.json").read_bytes()
    code, out, raw = bolt.run(
        "contribution", "--concern", "security", "--status", "proposed", "--note", "ready to read"
    )
    assert code == 0, raw
    assert out["concern"] == "security" and out["status"] == "proposed"
    assert (bolt.path / "architecture/contributions/security.md").read_bytes() == before
    assert (bolt.path / "state.json").read_bytes() == state_before
    fields = bolt.log_lines()[-1].split(" | ")
    assert fields[1] == "contribution" and fields[4] == "security: proposed - ready to read"


def test_the_note_is_optional(bolt: Bolt) -> None:
    put(bolt, "security")
    assert bolt.run("contribution", "--concern", "security", "--status", "draft")[0] == 0
    assert bolt.log_lines()[-1].split(" | ")[4] == "security: draft"


@pytest.mark.parametrize(
    ("setup", "args", "code", "needle"),
    [
        ("none", ("--concern", "security", "--status", "draft"), 3, "does not exist"),
        ("draft", ("--concern", "Security", "--status", "draft"), 2, "concern"),
        ("draft", ("--concern", "security", "--status", "proposed"), 1, "says 'draft'"),
        ("no-owner", ("--concern", "security", "--status", "draft"), 1, "owner"),
        ("no-status", ("--concern", "security", "--status", "draft"), 1, "status"),
        ("no-header", ("--concern", "security", "--status", "draft"), 1, "header"),
    ],
)
def test_refusals_leave_the_log_alone(
    bolt: Bolt, setup: str, args: tuple[str, ...], code: int, needle: str
) -> None:
    text = {
        "draft": header("security"),
        "no-owner": header("security").replace("owner: Ana\n", ""),
        "no-status": header("security").replace("status: draft\n", ""),
        "no-header": "# Contribution: security\n\n## Question\n\nWhy?\n",
    }.get(setup)
    if text is not None:
        bolt.write("architecture/contributions/security.md", text)
    lines = bolt.log_lines()
    got, out, raw = bolt.run("contribution", *args)
    assert got == code and needle in raw + json.dumps(out), raw
    assert bolt.log_lines() == lines


def test_a_bad_status_is_a_usage_error(bolt: Bolt) -> None:
    put(bolt, "security")
    assert bolt.run("contribution", "--concern", "security", "--status", "done")[0] == 2


def test_a_closed_bolt_refuses(bolt: Bolt) -> None:
    put(bolt, "security")
    assert bolt.run("close", "--status", "archived")[0] == 0
    assert bolt.run("contribution", "--concern", "security", "--status", "draft")[0] == 1


def rows(p: Bolt) -> list[dict[str, object]]:
    return p.run("status")[1]["contributions"]


def test_status_and_overview_list_the_contributions_from_their_headers(bolt: Bolt) -> None:
    assert rows(bolt) == []
    put(bolt, "security", status="proposed", owner="Ana", touches="Security and privacy")
    put(bolt, "networking", status="draft", owner="Ben")
    put(bolt, "data", status="merged", owner="Cleo")
    bolt.write("architecture/contributions/broken.md", "no header here\n")
    got = {r["concern"]: r for r in rows(bolt)}
    assert set(got) == {"security", "networking", "data", "broken"}
    assert got["security"] == {
        "concern": "security",
        "owner": "Ana",
        "status": "proposed",
        "touches": ["Security and privacy"],
        "open": True,
    }
    assert got["networking"]["open"] is False and got["data"]["open"] is False
    assert got["broken"]["status"] is None and got["broken"]["owner"] is None

    text = bolt.run("status", "--format", "text")[2]
    assert "security | Ana | proposed (open)" in text and "Security and privacy" in text
    assert "networking | Ben | draft" in text and "data | Cleo | merged" in text

    done = script("overview", "--root", str(bolt.root), "--format", "text")
    assert "contribution security | Ana | proposed (open)" in done[2]
    as_json = script("overview", "--root", str(bolt.root))[1]["bolts"][0]["contributions"]
    assert {r["concern"] for r in as_json} == {"security", "networking", "data", "broken"}
    assert json.loads((bolt.path / "state.json").read_text()).get("contributions") is None


def test_the_header_may_use_inline_lists_and_quotes(bolt: Bolt) -> None:
    bolt.write(
        "architecture/contributions/security.md",
        '```yaml\nconcern: security\nowner: "Ann Owner"  # lead\nstatus: proposed\n'
        'touches: ["Security and privacy", Scope]\n```\n',
    )
    row = rows(bolt)[0]
    assert row["owner"] == "Ann Owner" and row["touches"] == ["Security and privacy", "Scope"]


# --- two engineers, one remote -----------------------------------------------------------

HLA = "# HLA\n\n## Alpha\n\nalpha text\n\n" + "filler\n\n" * 8 + "## Beta\n\nbeta text\n"


def test_two_engineers_contribute_and_edit_different_sections_without_a_manual_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = three.Team(tmp_path, monkeypatch)
    ana = team.clones["Ana"]
    monkeypatch.setenv("AIDLC_ACTOR", "Ana")
    assert script("open", "--root", str(ana), "--slug", "demo", "--title", "Demo",
                  "--intent", "Try it", "--date", "2026-01-05")[0] == 0  # fmt: skip
    write(ana / "bolts" / BOLT_ID / "architecture/hla.md", HLA)
    assert script("sync", "--bolt", str(team.bolt("Ana")), "-m", "start the HLA")[0] == 0
    team.pull("Ben")

    def contribute(who: str, concern: str, section: str, new: str) -> None:
        monkeypatch.setenv("AIDLC_ACTOR", who)
        bolt = team.bolt(who)
        write(bolt / f"architecture/contributions/{concern}.md",
              header(concern, "proposed", who, section))  # fmt: skip
        hla = bolt / "architecture/hla.md"
        hla.write_text(hla.read_text().replace(f"{section.lower()} text", new), encoding="utf-8")
        code, out, raw = script("contribution", "--bolt", str(bolt), "--concern", concern,
                                "--status", "proposed")  # fmt: skip
        assert code == 0, raw
        assert out["git"]["pushed"] is True and not out["git"].get("not_shared"), out["git"]

    contribute("Ana", "security", "Alpha", "alpha, with the security conclusion")
    contribute("Ben", "networking", "Beta", "beta, with the networking conclusion")  # stale base

    git(ana, "pull", "-q")
    bolt = team.bolt("Ana")
    assert {p.name for p in (bolt / "architecture/contributions").iterdir()} == {
        "security.md",
        "networking.md",
    }
    hla_text = (bolt / "architecture/hla.md").read_text()
    assert "alpha, with the security conclusion" in hla_text
    assert "beta, with the networking conclusion" in hla_text
    log = (bolt / "log.md").read_text()
    assert "security: proposed" in log and "networking: proposed" in log
    assert git(ana, "status", "--porcelain") == ""
    assert git(ana, "rev-parse", "HEAD") == git(team.remote, "rev-parse", "main")
