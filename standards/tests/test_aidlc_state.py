"""``aidlc_state.py`` opens, advances, gates and closes a bolt.

Progress is only trustworthy if the script refuses what should be refused, so
most of these tests assert a refusal and that nothing changed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "processes" / "crv-aidlc"
SCRIPT = SKILL / "scripts" / "aidlc_state.py"

QUESTIONS = """## Q1 Scope
Context line.

A) One
B) Two
X) Other (describe)

Recommended: A - simplest.

Answer: A
"""


class Bolt:
    def __init__(self, root: Path, path: Path) -> None:
        self.root = root
        self.path = path

    def run(self, command: str, *args: str) -> tuple[int, dict[str, Any], str]:
        done = subprocess.run(
            [sys.executable, str(SCRIPT), command, "--bolt", str(self.path), *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return (
            done.returncode,
            (json.loads(done.stdout) if done.stdout.strip().startswith("{") else {}),
            done.stdout,
        )

    @property
    def state(self) -> dict[str, Any]:
        return json.loads((self.path / "state.json").read_text(encoding="utf-8"))

    def write(self, rel: str, text: str) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def log_lines(self) -> list[str]:
        return (self.path / "log.md").read_text(encoding="utf-8").splitlines()


def open_bolt(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "open", "--root", str(root), "--slug", "demo", "--title", "Demo",
         "--intent", "Try it", "--date", "2026-01-05", *args],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def digest(lines: int = 2) -> str:
    return (
        "# Title\n\n## Digest\n"
        + "".join(f"- point {i}\n" for i in range(lines))
        + "\n## Body\ntext\n"
    )


def verdict_doc(line: str = "Verdict: pass") -> str:
    return f"{line}\n\n" + digest()


def reach_produced(p: Bolt, stage: str = "requirements-analysis") -> None:
    """Take the early stages out of the way so ``stage`` is the one in play."""
    for name in ("workspace-detection",):
        assert p.run("gate", "--stage", name, "--approve", "--by", "Boss")[0] == 0
    for name in ("document-knowledge", "reverse-engineering", "hla", "tdd"):
        p.run("decide", "--stage", name, "--decision", "skip", "--reason", "test")
    assert p.run("step", "--stage", stage, "--to", "produced")[0] == 0


def ra_files(p: Bolt, questions: str = QUESTIONS, doc: str = "") -> None:
    base = "docs/inception/requirements-analysis/"
    p.write(base + "requirements.md", doc or digest())
    p.write(base + "traceability.json", "{}")
    p.write(base + "requirements-analysis-questions.md", questions)


# --- open --------------------------------------------------------------------


def test_open_creates_the_bolt(bolt: Bolt) -> None:
    state = bolt.state
    assert state["id"] == "2026-01-05-demo" and state["status"] == "open"
    assert state["scope"] == "classic" and state["depth"] == "standard"
    for folder in (
        "inputs",
        "knowledge/extracted",
        "architecture",
        "docs/inception",
        "docs/construction",
    ):
        assert (bolt.path / folder).is_dir()
    assert state["stages"]["requirements-analysis"]["decision"] == "execute"
    assert state["stages"]["workspace-detection"]["step"] == "produced"
    assert "open" in bolt.log_lines()[0]


def test_open_refuses_an_existing_bolt(tmp_path: Path, bolt: Bolt) -> None:
    before = bolt.state
    done = open_bolt(tmp_path)
    assert done.returncode == 1
    assert bolt.state == before


def test_open_rejects_a_bad_slug(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "open", "--root", str(tmp_path), "--slug", "Bad Slug",
         "--title", "t", "--intent", "i"], capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert done.returncode == 2


def test_open_classifies_targets_and_records_the_rule(tmp_path: Path) -> None:
    green = tmp_path / "green"
    green.mkdir()
    (green / "README.md").write_text("hi", encoding="utf-8")
    brown = tmp_path / "brown"
    brown.mkdir()
    (brown / "app.py").write_text("x = 1\n", encoding="utf-8")
    done = open_bolt(tmp_path, "--target", f"g={green}", "--target", f"b={brown}")
    assert done.returncode == 0, done.stderr
    p = Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))
    kinds = {t["repo"]: t["kind"] for t in p.state["targets"]}
    assert kinds == {"g": "greenfield", "b": "brownfield"}
    assert p.state["stages"]["reverse-engineering"]["decision"] == "execute"
    assert any("| classify |" in line and "b: brownfield (1 " in line for line in p.log_lines())


def test_open_without_brownfield_skips_reverse_engineering(bolt: Bolt) -> None:
    record = bolt.state["stages"]["reverse-engineering"]
    assert record["decision"] == "skip" and record["reason"]


def test_open_missing_target_exits_3(tmp_path: Path) -> None:
    assert open_bolt(tmp_path, "--target", f"x={tmp_path / 'nope'}").returncode == 3


def test_open_records_the_architecture_commit(tmp_path: Path) -> None:
    registry = tmp_path / "reg"
    registry.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@e.com", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(tmp_path)}  # fmt: skip
    (registry / "a.md").write_text("a", encoding="utf-8")
    for cmd in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "x"]):
        subprocess.run(["git", "-C", str(registry), *cmd], check=True, env=env, capture_output=True)
    done = open_bolt(tmp_path, "--architecture-ref", str(registry))
    commit = json.loads(done.stdout)["architecture_ref"]["commit"]
    assert re.fullmatch(r"[0-9a-f]{40}", commit)


def test_bugfix_scope_gets_a_default_unit(tmp_path: Path) -> None:
    done = open_bolt(tmp_path, "--scope", "bugfix")
    p = Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))
    assert [u["id"] for u in p.state["units"]] == ["u1"]
    assert p.state["stages"]["hla"]["decision"] == "skip"
    assert p.state["units"][0]["stages"]["code-generation"]["decision"] == "execute"


# --- status and next ---------------------------------------------------------


def test_status_text_is_short(bolt: Bolt) -> None:
    code, _, out = bolt.run("status", "--format", "text")
    assert code == 0 and len(out.splitlines()) <= 20
    assert "Demo" in out and "Next:" in out


def test_status_json_carries_the_same_facts(bolt: Bolt) -> None:
    code, data, _ = bolt.run("status")
    assert code == 0
    assert data["title"] == "Demo" and set(data["phases"]) == {
        "discovery",
        "inception",
        "construction",
        "operation",
    }


def test_status_shows_the_parked_note_and_stays_short(bolt: Bolt) -> None:
    bolt.run("park", "--note", "waiting for access\n" * 50)
    _, _, out = bolt.run("status", "--format", "text")
    assert "Parked: waiting for access" in out and len(out.splitlines()) <= 20


def test_next_starts_at_workspace_detection_then_follows_the_order(bolt: Bolt) -> None:
    _, data, _ = bolt.run("next")
    assert (data["stage"], data["action"]) == ("workspace-detection", "gate")
    bolt.run("gate", "--stage", "workspace-detection", "--approve", "--by", "Boss")
    _, data, _ = bolt.run("next")
    assert data["stage"] == "document-knowledge" and data["action"] == "produce"
    assert bolt.state["current"]["stage"] == "document-knowledge"
    assert "document-knowledge" in bolt.state["next_action"]


def test_next_after_changes_requested_says_revise(bolt: Bolt) -> None:
    reach_produced(bolt)
    bolt.run("gate", "--stage", "requirements-analysis", "--request-changes", "--note", "again")
    _, data, _ = bolt.run("next")
    assert data["stage"] == "requirements-analysis" and data["action"] == "revise"


def test_next_after_skips_reports_skill(bolt: Bolt) -> None:
    for name in ("workspace-detection",):
        bolt.run("gate", "--stage", name, "--approve", "--by", "B")
    for name in ("document-knowledge", "hla", "tdd"):
        bolt.run("decide", "--stage", name, "--decision", "skip", "--reason", "n/a")
    _, data, _ = bolt.run("next")
    assert (data["stage"], data["skill"], data["reference"]) == (
        "requirements-analysis",
        "crv-aidlc-inception",
        "references/requirements-analysis.md",
    )
    assert data["action"] == "ask"


# --- inputs ------------------------------------------------------------------


def test_inputs_with_a_missing_input_exits_3_and_names_the_producer(bolt: Bolt) -> None:
    code, data, _ = bolt.run("inputs", "--stage", "user-stories")
    assert code == 3
    assert data["missing"] == [
        {
            "path": "docs/inception/requirements-analysis/requirements.md",
            "produced_by": "requirements-analysis",
        }
    ]


def test_inputs_lists_existing_files_with_modes(bolt: Bolt) -> None:
    ra_files(bolt)
    code, data, _ = bolt.run("inputs", "--stage", "user-stories")
    assert code == 0 and data["inputs"][0]["exists"] and data["inputs"][0]["mode"] == "full"


def test_inputs_treats_a_skipped_producer_as_satisfied(bolt: Bolt) -> None:
    ra_files(bolt)
    bolt.run("decide", "--stage", "hla", "--decision", "skip", "--reason", "n/a")
    bolt.run("decide", "--stage", "tdd", "--decision", "skip", "--reason", "n/a")
    bolt.run("decide", "--stage", "document-knowledge", "--decision", "skip", "--reason", "n/a")
    code, data, _ = bolt.run("inputs", "--stage", "requirements-analysis")
    assert code == 0
    assert all(row["skipped"] for row in data["inputs"] if not row["optional"])


def test_inputs_unknown_stage_exits_2(bolt: Bolt) -> None:
    assert bolt.run("inputs", "--stage", "nonsense")[0] == 2


def test_inputs_per_unit_stage_needs_a_unit(bolt: Bolt) -> None:
    assert bolt.run("inputs", "--stage", "functional-design")[0] == 2


# --- decide and step ---------------------------------------------------------


def test_decide_skip_needs_a_reason(bolt: Bolt) -> None:
    assert bolt.run("decide", "--stage", "hla", "--decision", "skip", "--reason", "  ")[0] == 2
    assert (
        bolt.run("decide", "--stage", "hla", "--decision", "skip", "--reason", "covered elsewhere")[
            0
        ]
        == 0
    )
    assert bolt.state["stages"]["hla"] == {
        "decision": "skip",
        "reason": "covered elsewhere",
        "step": "todo",
        "approved_at": None,
        "approved_by": None,
    }


def test_step_only_moves_forward(bolt: Bolt) -> None:
    stage = ("--stage", "requirements-analysis")
    assert bolt.run("step", *stage, "--to", "asked")[0] == 0
    assert bolt.run("step", *stage, "--to", "asked")[0] == 1
    assert bolt.run("step", *stage, "--to", "analysed")[0] == 0
    assert bolt.run("step", *stage, "--to", "asked")[0] == 1
    assert bolt.state["stages"]["requirements-analysis"]["step"] == "analysed"


def test_step_refused_for_a_skipped_stage(bolt: Bolt) -> None:
    assert bolt.run("step", "--stage", "reverse-engineering", "--to", "asked")[0] == 1


# --- gate --------------------------------------------------------------------


def test_gate_refuses_when_not_produced(bolt: Bolt) -> None:
    ra_files(bolt)
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")
    assert code == 1 and "wrong-step" in [f["code"] for f in data["findings"]]


def test_gate_refuses_a_missing_artifact(bolt: Bolt) -> None:
    reach_produced(bolt)
    base = "docs/inception/requirements-analysis/"
    bolt.write(base + "requirements-analysis-questions.md", QUESTIONS)
    bolt.write(base + "traceability.json", "{}")
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")
    assert code == 1 and [f["code"] for f in data["findings"]] == ["artifact-missing"]
    assert data["findings"][0]["path"] == base + "requirements.md"
    assert bolt.state["stages"]["requirements-analysis"]["step"] == "produced"


def test_gate_refuses_a_missing_digest(bolt: Bolt) -> None:
    reach_produced(bolt)
    ra_files(bolt, doc="# Title\nNo digest here.\n")
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")
    assert code == 1 and [f["code"] for f in data["findings"]] == ["digest-missing"]


def test_gate_refuses_a_digest_over_ten_lines(bolt: Bolt) -> None:
    reach_produced(bolt)
    ra_files(bolt, doc=digest(11))
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")
    assert code == 1 and [f["code"] for f in data["findings"]] == ["digest-too-long"]


def test_gate_accepts_a_digest_of_exactly_ten_lines(bolt: Bolt) -> None:
    reach_produced(bolt)
    ra_files(bolt, doc=digest(10))
    assert bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")[0] == 0


def test_gate_refuses_an_unanswered_question(bolt: Bolt) -> None:
    reach_produced(bolt)
    ra_files(bolt, questions=QUESTIONS.replace("Answer: A", "Answer:"))
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")
    assert code == 1 and [f["code"] for f in data["findings"]] == ["questions-empty-answer"]


def test_gate_approve_marks_approved_and_advances(bolt: Bolt) -> None:
    reach_produced(bolt)
    ra_files(bolt)
    code, data, _ = bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "Ada")
    assert code == 0, data
    record = bolt.state["stages"]["requirements-analysis"]
    assert record["step"] == "approved" and record["approved_by"] == "Ada"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["approved_at"])
    assert bolt.state["current"]["stage"] == "user-stories"
    assert "fresh session" in data["suggestion"]
    assert "gate-approve" in bolt.log_lines()[-1]


def test_request_changes_needs_a_note(bolt: Bolt) -> None:
    assert bolt.run("gate", "--stage", "hla", "--request-changes")[0] == 2


def test_request_changes_sets_the_step_and_logs_the_note(bolt: Bolt) -> None:
    reach_produced(bolt)
    ra_files(bolt)
    code, _, _ = bolt.run(
        "gate", "--stage", "requirements-analysis", "--request-changes", "--note", "add NFRs"
    )
    assert code == 0
    assert bolt.state["stages"]["requirements-analysis"]["step"] == "changes-requested"
    assert bolt.log_lines()[-1].endswith("| add NFRs")
    assert bolt.run("step", "--stage", "requirements-analysis", "--to", "produced")[0] == 0


def test_gate_refuses_a_missing_repo_artifact_per_target(tmp_path: Path) -> None:
    repo = tmp_path / "svc"
    repo.mkdir()
    (repo / "main.py").write_text("x = 1\n", encoding="utf-8")
    p = Bolt(
        tmp_path,
        Path(json.loads(open_bolt(tmp_path, "--target", f"svc={repo}").stdout)["bolt"]),
    )
    p.run("gate", "--stage", "workspace-detection", "--approve", "--by", "B")
    p.run("decide", "--stage", "document-knowledge", "--decision", "skip", "--reason", "none")
    p.run("step", "--stage", "reverse-engineering", "--to", "produced")
    code, data, _ = p.run("gate", "--stage", "reverse-engineering", "--approve", "--by", "B")
    assert code == 1 and data["findings"][0]["path"] == "root:codekb/svc/overview.md"


# --- several question files, scoped clarifications, sign-off -----------------

SIGNED = """# HLA

```yaml
status: accepted  # set by the reviewer
signed_off_by: "Rae Viewer"
signed_off_on: "2026-11-20"
```

## Digest
- point
"""


def hla_produced(p: Bolt, header: str = SIGNED) -> None:
    """Bring the HLA stage to `produced` with every file it gates on present."""
    assert p.run("gate", "--stage", "workspace-detection", "--approve", "--by", "B")[0] == 0
    p.run("decide", "--stage", "document-knowledge", "--decision", "skip", "--reason", "none")
    for round_id in "abc":
        p.write(f"architecture/hla-questions-{round_id}.md", QUESTIONS)
    p.write("architecture/hla.md", header)
    p.write("architecture/hla-decisions.md", digest())
    assert p.run("step", "--stage", "hla", "--to", "produced")[0] == 0


def test_gate_needs_every_question_file_of_the_stage(bolt: Bolt) -> None:
    hla_produced(bolt)
    (bolt.path / "architecture/hla-questions-b.md").unlink()
    code, data, _ = bolt.run("gate", "--stage", "hla", "--approve", "--by", "Rae Viewer")
    assert code == 1
    assert [(f["code"], f["path"]) for f in data["findings"]] == [
        ("questions-missing", "architecture/hla-questions-b.md")
    ]


def test_gate_lints_each_question_file(bolt: Bolt) -> None:
    hla_produced(bolt)
    bolt.write("architecture/hla-questions-c.md", QUESTIONS.replace("Answer: A", "Answer:"))
    code, data, _ = bolt.run("gate", "--stage", "hla", "--approve", "--by", "Rae Viewer")
    assert code == 1 and [f["path"] for f in data["findings"]] == [
        "architecture/hla-questions-c.md"
    ]


def test_clarifications_are_scoped_to_their_stage(bolt: Bolt) -> None:
    hla_produced(bolt)
    open_question = QUESTIONS.replace("Answer: A", "Answer:")
    bolt.write("architecture/tdd-clarifications.md", open_question)
    assert bolt.run("gate", "--stage", "hla", "--approve", "--by", "Rae Viewer")[0] == 0


def test_own_clarifications_are_linted(bolt: Bolt) -> None:
    hla_produced(bolt)
    bolt.write("architecture/hla-clarifications.md", QUESTIONS.replace("Answer: A", "Answer:"))
    code, data, _ = bolt.run("gate", "--stage", "hla", "--approve", "--by", "Rae Viewer")
    assert code == 1 and data["findings"][0]["path"] == "architecture/hla-clarifications.md"


def test_an_unsigned_document_never_conditions_the_gate(bolt: Bolt) -> None:
    unsigned = SIGNED.replace("status: accepted", "status: in-review").replace('"Rae Viewer"', '""')
    hla_produced(bolt, unsigned)
    code, data, _ = bolt.run("gate", "--stage", "hla", "--approve")
    assert code == 0, data
    assert data["review"] == {
        "path": "architecture/hla.md",
        "status": "in-review",
        "signed_off_by": None,
    }
    assert bolt.state["stages"]["hla"]["step"] == "approved"


def test_a_document_without_a_header_passes_with_an_empty_review(bolt: Bolt) -> None:
    hla_produced(bolt, digest())
    code, data, _ = bolt.run("gate", "--stage", "hla", "--approve")
    assert code == 0, data
    assert data["review"] == {"path": "architecture/hla.md", "status": None, "signed_off_by": None}


def test_a_stage_without_a_review_document_has_no_review_field(bolt: Bolt) -> None:
    data = bolt.run("gate", "--stage", "workspace-detection", "--approve")[1]
    assert "review" not in data


def test_gate_reports_the_review_of_a_signed_document(bolt: Bolt) -> None:
    hla_produced(bolt)
    code, data, _ = bolt.run("gate", "--stage", "hla", "--approve", "--by", "Rae Viewer")
    assert code == 0, data
    assert data["review"]["status"] == "accepted"
    assert data["review"]["signed_off_by"] == "Rae Viewer"
    assert bolt.state["stages"]["hla"]["approved_by"] == "Rae Viewer"
    assert bolt.state["current"]["stage"] == "tdd"


def test_request_changes_does_not_need_a_signature(bolt: Bolt) -> None:
    hla_produced(bolt, SIGNED.replace("status: accepted", "status: changes-requested"))
    code, _, _ = bolt.run("gate", "--stage", "hla", "--request-changes", "--note", "rework cutover")
    assert code == 0 and bolt.state["stages"]["hla"]["step"] == "changes-requested"


def test_optional_input_never_counts_as_missing(bolt: Bolt) -> None:
    bolt.run("decide", "--stage", "document-knowledge", "--decision", "skip", "--reason", "none")
    code, data, _ = bolt.run("inputs", "--stage", "hla")
    assert code == 0, data
    index = [row for row in data["inputs"] if row["path"].endswith("architecture-index.json")]
    assert index and index[0]["optional"] and not index[0]["exists"]


def test_tdd_inputs_name_the_hla_as_producer(bolt: Bolt) -> None:
    code, data, _ = bolt.run("inputs", "--stage", "tdd")
    assert code == 3
    assert {"path": "architecture/hla.md", "produced_by": "hla"} in data["missing"]


# --- units, ids, park, close, log --------------------------------------------


def test_units_load_and_drive_per_unit_stages(bolt: Bolt) -> None:
    spec = bolt.root / "units.json"
    spec.write_text(json.dumps({"units": [{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}],
                                "slices": [{"id": "s1", "units": ["u1", "u2"]}]}), encoding="utf-8")  # fmt: skip
    assert bolt.run("units", "--set", str(spec))[0] == 0
    state = bolt.state
    assert [u["slice"] for u in state["units"]] == ["s1", "s1"]
    assert state["units"][0]["stages"]["functional-design"]["decision"] == "pending"
    assert state["units"][0]["stages"]["code-generation"]["decision"] == "execute"
    code, data, _ = bolt.run("inputs", "--stage", "functional-design", "--unit", "u1")
    assert code == 3 and data["missing"][0]["produced_by"] == "units-generation"


def test_units_rejects_a_slice_with_an_unknown_unit(bolt: Bolt) -> None:
    spec = bolt.root / "units.json"
    spec.write_text(
        json.dumps({"units": [{"id": "u1"}], "slices": [{"id": "s1", "units": ["u9"]}]}),
        encoding="utf-8",
    )
    assert bolt.run("units", "--set", str(spec))[0] == 4
    assert bolt.state["units"] == []


def test_decision_ids_continue_the_sequence(bolt: Bolt) -> None:
    assert bolt.run("decision-id", "--count", "2")[1]["ids"] == ["D1", "D2"]
    assert bolt.run("decision-id")[1]["ids"] == ["D3"]
    assert bolt.state["decision_seq"] == 3


def test_park_and_unpark(bolt: Bolt) -> None:
    bolt.run("park", "--note", "waiting on access")
    assert bolt.state["parked"]["note"] == "waiting on access"
    bolt.run("unpark")
    assert bolt.state["parked"] is None


def test_close_complete_is_refused_while_executed_stages_are_unapproved(bolt: Bolt) -> None:
    code, data, _ = bolt.run("close", "--status", "complete")
    assert code == 1 and data["findings"]
    assert bolt.state["status"] == "open"


def test_close_archived_and_superseded_are_allowed_and_final(bolt: Bolt) -> None:
    assert bolt.run("close", "--status", "superseded", "--successor", "2026-02-01-next")[0] == 0
    assert bolt.state["status"] == "superseded" and bolt.state["successor"] == "2026-02-01-next"
    assert bolt.run("park", "--note", "x")[0] == 1


def test_close_complete_after_everything_is_approved(tmp_path: Path) -> None:
    p = Bolt(tmp_path, Path(json.loads(open_bolt(tmp_path, "--scope", "bugfix").stdout)["bolt"]))
    p.run("gate", "--stage", "workspace-detection", "--approve", "--by", "B")
    assert p.run("jira", "--unit", "u1", "--story", "ABC-7")[0] == 0
    ra = "docs/inception/requirements-analysis/"
    p.write(ra + "requirements.md", digest())
    p.write(ra + "traceability.json", "{}")
    p.write(ra + "requirements-analysis-questions.md", QUESTIONS)
    p.run("step", "--stage", "requirements-analysis", "--to", "produced")
    assert p.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")[0] == 0
    cg = "docs/construction/u1/code-generation/"
    for name in ("code-generation-plan.md", "unit-test-instructions.md"):
        p.write(cg + name, digest())
    p.write(cg + "code-summary.md", verdict_doc())
    p.write(cg + "source-manifest.json", "{}")
    p.write(cg + "traceability.json", "{}")
    p.run("step", "--stage", "code-generation", "--unit", "u1", "--to", "produced")
    assert (
        p.run("gate", "--stage", "code-generation", "--unit", "u1", "--approve", "--by", "B")[0]
        == 0
    )
    for name in (
        "build-instructions.md",
        "build-and-test-summary.md",
        "cross-unit-traceability.md",
    ):
        p.write("docs/construction/build-and-test/" + name, digest())
    p.write("docs/construction/build-and-test/test-results.md", verdict_doc())
    p.run("step", "--stage", "build-and-test", "--to", "produced")
    assert p.run("gate", "--stage", "build-and-test", "--approve", "--by", "B")[0] == 0
    code, data, _ = p.run("close", "--status", "complete")
    assert code == 1 and data["findings"][0]["code"] == "story-not-done"
    assert "u1" in data["findings"][0]["message"]
    assert p.run("jira", "--unit", "u1", "--done", "--pr", "https://example.test/pr/1")[0] == 0
    code, data, _ = p.run("close", "--status", "complete")
    assert code == 0, data
    assert p.state["status"] == "complete"


def test_every_write_appends_one_well_formed_log_line(bolt: Bolt) -> None:
    before = len(bolt.log_lines())
    bolt.run("decide", "--stage", "hla", "--decision", "skip", "--reason", "a | b\nc")
    bolt.run("step", "--stage", "requirements-analysis", "--to", "asked")
    lines = bolt.log_lines()
    assert len(lines) == before + 2
    pattern = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ \| [^|]+ \| [^|]+ \| [^|]+ \| [^|]+$")
    assert all(pattern.match(line) for line in lines), lines
    assert lines[-2].split(" | ")[1:3] == ["decide", "hla"]


def test_reads_do_not_write(bolt: Bolt) -> None:
    before = (bolt.path / "state.json").read_bytes(), bolt.log_lines()
    bolt.run("status")
    bolt.run("next")
    bolt.run("inputs", "--stage", "requirements-analysis")
    assert ((bolt.path / "state.json").read_bytes(), bolt.log_lines()) == before


def test_writes_update_the_timestamp_atomically(bolt: Bolt) -> None:
    bolt.run("park", "--note", "n")
    assert not list(bolt.path.glob("*.tmp")) and not list(bolt.path.glob(".*.tmp"))
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", bolt.state["updated"])


def test_missing_and_malformed_state(tmp_path: Path) -> None:
    done = subprocess.run([sys.executable, str(SCRIPT), "status", "--bolt", str(tmp_path / "none")],
                          capture_output=True, text=True, timeout=60)  # fmt: skip
    assert done.returncode == 3
    (tmp_path / "state.json").write_text("{oops", encoding="utf-8")
    done = subprocess.run([sys.executable, str(SCRIPT), "status", "--bolt", str(tmp_path)],
                          capture_output=True, text=True, timeout=60)  # fmt: skip
    assert done.returncode == 4


# --- operation stages ----------------------------------------------------------

OPERATION = ("deployment-pipeline", "deployment-execution")


def test_operation_stages_follow_build_and_test_in_the_catalogue() -> None:
    catalog = json.loads((SKILL / "assets" / "stages.json").read_text(encoding="utf-8"))["stages"]
    order = {item["id"]: item["order"] for item in catalog}
    assert order["build-and-test"] < order["deployment-pipeline"] < order["deployment-execution"]
    for stage in OPERATION:
        item = next(i for i in catalog if i["id"] == stage)
        assert item["phase"] == "operation" and item["skill"] == "crv-aidlc-operation"
        assert item["scopes"] == ["classic"] and item["conditional"] is True
        assert not item["per_unit"]


def test_operation_stages_are_decided_in_classic_and_skipped_elsewhere(tmp_path: Path) -> None:
    p = Bolt(tmp_path, Path(json.loads(open_bolt(tmp_path).stdout)["bolt"]))
    assert (p.path / "docs" / "operation").is_dir()
    assert all(p.state["stages"][s]["decision"] == "pending" for s in OPERATION)
    other = tmp_path / "b"
    other.mkdir()
    q = Bolt(other, Path(json.loads(open_bolt(other, "--scope", "bugfix").stdout)["bolt"]))
    assert all(q.state["stages"][s]["decision"] == "skip" for s in OPERATION)


def test_operation_stages_work_with_every_command(bolt: Bolt) -> None:
    assert bolt.run("decide", "--stage", "deployment-pipeline", "--decision", "skip",
                       "--reason", "pipeline releases on merge")[0] == 0  # fmt: skip
    assert bolt.run("inputs", "--stage", "deployment-execution")[0] in (0, 3)
    assert bolt.run("step", "--stage", "deployment-execution", "--to", "asked")[0] in (0, 1)
    assert "Operation:" in bolt.run("status", "--format", "text")[2]


def test_gate_refuses_an_operation_stage_with_a_missing_artifact(bolt: Bolt) -> None:
    stage = "deployment-pipeline"
    base = "docs/operation/deployment-pipeline/"
    bolt.write(base + "release-plan.md", digest())
    bolt.write(base + "deployment-pipeline-questions.md", QUESTIONS)
    assert bolt.run("decide", "--stage", stage, "--decision", "execute", "--reason", "x")[0] == 0
    assert bolt.run("step", "--stage", stage, "--to", "produced")[0] == 0
    code, data, _ = bolt.run("gate", "--stage", stage, "--approve", "--by", "Boss")
    assert code == 1
    assert any("runbook.md" in json.dumps(f) for f in data["findings"])
    assert bolt.state["stages"][stage]["step"] == "produced"


def test_a_state_written_before_the_operation_stages_keeps_working(bolt: Bolt) -> None:
    state = bolt.state
    for stage in OPERATION:
        del state["stages"][stage]
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    for command in (("status",), ("next",), ("codekb-status",), ("workspace",)):
        assert bolt.run(*command)[0] == 0, command
    assert bolt.run("inputs", "--stage", "deployment-execution")[0] in (0, 3)
    assert "deployment-pipeline" not in bolt.state["stages"]  # reads do not write
    code, _, _ = bolt.run("decide", "--stage", "deployment-pipeline", "--decision", "skip",
                             "--reason", "old bolt")  # fmt: skip
    assert code == 0 and bolt.state["stages"]["deployment-pipeline"]["decision"] == "skip"
    assert bolt.state["stages"]["deployment-execution"]["decision"] == "pending"
    assert bolt.run("close", "--status", "archived")[0] == 0


# --- jira ----------------------------------------------------------------------


@pytest.fixture
def bugfix(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path, "--scope", "bugfix")
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def test_a_new_bolt_has_jira_unset(bugfix: Bolt) -> None:
    assert bugfix.state["jira"] == {"mode": None, "reason": "", "epic": None}
    assert bugfix.state["units"][0]["story"] is None
    assert "Jira: not set" in bugfix.run("status", "--format", "text")[2]


def test_jira_forms_record_and_log(bugfix: Bolt) -> None:
    assert bugfix.run("jira", "--epic", "ABC-1")[0] == 0
    assert bugfix.state["jira"]["epic"] == "ABC-1" and bugfix.state["jira"]["mode"] == "on"
    assert bugfix.run("jira", "--unit", "u1", "--story", "ABC-2")[0] == 0
    assert bugfix.state["units"][0]["story"] == "ABC-2"
    assert (
        "Jira: epic ABC-1, stories 1/1 filed, 0 done" in bugfix.run("status", "--format", "text")[2]
    )
    assert bugfix.run("jira", "--unit", "u1", "--done", "--pr", "https://x.test/1")[0] == 0
    done = bugfix.state["units"][0]["story_done"]
    assert done["pr"] == "https://x.test/1" and done["at"].endswith("Z")
    assert "1 done" in bugfix.run("status", "--format", "text")[2]
    assert sum(1 for line in bugfix.log_lines() if " | jira | " in line) == 3


def test_jira_off_needs_a_reason_and_on_reverses_it(bugfix: Bolt) -> None:
    assert bugfix.run("jira", "--off")[0] == 2
    assert bugfix.run("jira", "--off", "--reason", "no Jira here")[0] == 0
    assert "Jira: off (no Jira here)" in bugfix.run("status", "--format", "text")[2]
    assert bugfix.run("jira", "--on")[0] == 0 and bugfix.state["jira"]["mode"] == "on"


@pytest.mark.parametrize(
    "args",
    [
        ("--epic", "abc-1"),
        ("--epic", "ABC1"),
        ("--unit", "u1", "--story", "nope"),
        ("--unit", "zz", "--story", "ABC-1"),
        ("--story", "ABC-1"),
        ("--unit", "u1"),
        ("--epic", "ABC-1", "--on"),
    ],
)
def test_jira_rejects_bad_input(bugfix: Bolt, args: tuple[str, ...]) -> None:
    before = bugfix.state
    assert bugfix.run("jira", *args)[0] == 2
    assert bugfix.state["jira"] == before["jira"]


def test_done_needs_a_recorded_story(bugfix: Bolt) -> None:
    code, data, _ = bugfix.run("jira", "--unit", "u1", "--done")
    assert code == 1 and "--story" in data["error"]


def test_construction_is_refused_without_a_story(bugfix: Bolt) -> None:
    for command in ("decide", "step"):
        extra = (
            ("--decision", "execute", "--reason", "x")
            if command == "decide"
            else ("--to", "produced")
        )
        code, data, _ = bugfix.run(command, "--stage", "code-generation", "--unit", "u1", *extra)
        assert code == 1 and data["findings"][0]["code"] == "jira-story-missing"
        message = data["findings"][0]["message"]
        assert "--unit u1 --story KEY" in message and "--off --reason" in message
    nxt = bugfix.run("next")[1]
    assert nxt["stage"] != "code-generation" or "jira" in nxt


def test_construction_proceeds_after_a_story_or_with_jira_off(bugfix: Bolt) -> None:
    args = ("step", "--stage", "code-generation", "--unit", "u1", "--to", "produced")
    assert bugfix.run(*args)[0] == 1
    assert bugfix.run("jira", "--unit", "u1", "--story", "ABC-2")[0] == 0
    assert bugfix.run(*args)[0] == 0


def test_construction_proceeds_with_jira_off(bugfix: Bolt) -> None:
    bugfix.run("jira", "--off", "--reason", "no ticket system")
    code = bugfix.run("step", "--stage", "code-generation", "--unit", "u1", "--to", "produced")[0]
    assert code == 0


def test_next_hints_at_the_missing_story(bugfix: Bolt) -> None:
    bugfix.run("gate", "--stage", "workspace-detection", "--approve", "--by", "B")
    ra = "docs/inception/requirements-analysis/"
    bugfix.write(ra + "requirements.md", digest())
    bugfix.write(ra + "traceability.json", "{}")
    bugfix.write(ra + "requirements-analysis-questions.md", QUESTIONS)
    bugfix.run("step", "--stage", "requirements-analysis", "--to", "produced")
    bugfix.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "B")
    nxt = bugfix.run("next")[1]
    assert nxt["stage"] == "code-generation" and "jira --unit u1 --story KEY" in nxt["jira"]


def test_close_other_statuses_ignore_open_stories(bugfix: Bolt) -> None:
    bugfix.run("jira", "--unit", "u1", "--story", "ABC-2")
    assert bugfix.run("close", "--status", "archived")[0] == 0


def test_a_state_without_jira_keys_keeps_working(bugfix: Bolt) -> None:
    state = bugfix.state
    del state["jira"]
    for unit in state["units"]:
        del unit["story"]
        del unit["story_done"]
    (bugfix.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    for command in (("status",), ("next",), ("codekb-status",)):
        assert bugfix.run(*command)[0] == 0, command
    assert "Jira: not set" in bugfix.run("status", "--format", "text")[2]
    assert (
        bugfix.run("step", "--stage", "code-generation", "--unit", "u1", "--to", "produced")[0] == 1
    )
    assert bugfix.run("jira", "--unit", "u1", "--story", "ABC-9")[0] == 0
    assert (
        bugfix.run("step", "--stage", "code-generation", "--unit", "u1", "--to", "produced")[0] == 0
    )


def test_inputs_lists_the_presets_file_when_it_exists_and_is_silent_when_not(
    bolt: Bolt,
) -> None:
    bolt.run("decide", "--stage", "document-knowledge", "--decision", "skip", "--reason", "n")
    code, data, _ = bolt.run("inputs", "--stage", "hla")
    assert code == 0 and not any(
        r["path"].endswith("presets.md") for r in data["inputs"] if r["exists"]
    )
    row = next(r for r in data["inputs"] if r["path"].endswith("presets.md"))
    assert row["optional"] and not row["exists"]
    presets = bolt.root / "docs" / "presets.md"
    presets.parent.mkdir(parents=True)
    presets.write_text("# Presets\n", encoding="utf-8")
    code, data, _ = bolt.run("inputs", "--stage", "hla")
    row = next(r for r in data["inputs"] if r["path"].endswith("presets.md"))
    assert code == 0 and row["exists"] and row["mode"] == "full"


# --- who did it, and the framework version -----------------------------------


def test_the_engineer_says_proceed_is_one_command_and_one_log_line(
    bolt: Bolt, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIDLC_ACTOR", "Ada  Lovelace")
    before = len(bolt.log_lines())
    code, data, _ = bolt.run(
        "gate", "--stage", "workspace-detection", "--approve",
        "--note", "go with option A, it keeps compatibility",
    )  # fmt: skip
    assert code == 0, data
    record = bolt.state["stages"]["workspace-detection"]
    assert record["approved_by"] == "Ada Lovelace" and record["approved_at"]
    assert "recorded_by" not in record and "channel" not in record
    added = bolt.log_lines()[before:]
    assert len(added) == 1
    assert "gate-approve" in added[0] and "Ada Lovelace" in added[0]
    assert added[0].endswith("go with option A, it keeps compatibility")


def test_by_still_names_someone_else_and_needs_no_channel(
    bolt: Bolt, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AIDLC_ACTOR", "Ada Lovelace")
    code, _, _ = bolt.run("gate", "--stage", "workspace-detection", "--approve", "--by", "Grace")
    assert code == 0
    assert bolt.state["stages"]["workspace-detection"]["approved_by"] == "Grace"


def test_the_removed_flags_are_refused(bolt: Bolt) -> None:
    gate = ("gate", "--stage", "workspace-detection", "--approve")
    for flag in ("--channel", "--ack-context"):
        assert bolt.run(*gate, flag, "x")[0] == 2
    assert open_bolt(bolt.root / "other", "--approver", "x").returncode == 2


def test_an_old_state_loses_the_approval_records_at_the_next_write(bolt: Bolt) -> None:
    state = bolt.state
    state["approver"] = "Old Approver"
    record = state["stages"]["workspace-detection"]
    record["recorded_by"], record["channel"] = "Ada", "email"
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert bolt.run("status")[0] == 0  # loads
    assert bolt.run("park", "--note", "n")[0] == 0
    after = bolt.state
    assert "approver" not in after
    assert "recorded_by" not in after["stages"]["workspace-detection"]
    assert "channel" not in after["stages"]["workspace-detection"]


def test_a_newer_framework_is_refused_and_a_missing_one_is_added(bolt: Bolt) -> None:
    state = bolt.state
    del state["framework"]
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    assert bolt.run("status")[0] == 0
    assert bolt.run("park", "--note", "n")[0] == 0 and bolt.state["framework"] == 4
    state["framework"] = 5
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    code, data, _ = bolt.run("status")
    assert code == 4 and "framework 5, installed 4" in data["error"]


# --- unit owners, waiting, changed context and the brief ---------------------


def load_units(p: Bolt, units: list[dict[str, Any]]) -> tuple[int, dict[str, Any], str]:
    spec = p.root / "units.json"
    spec.write_text(json.dumps({"units": units}), encoding="utf-8")
    return p.run("units", "--set", str(spec))


def skip_unit_stages(p: Bolt, unit: str) -> None:
    for stage in ("functional-design", "nfr-requirements", "nfr-design", "infrastructure-design"):
        p.run("decide", "--stage", stage, "--unit", unit, "--decision", "skip", "--reason", "t")
    p.run("decide", "--stage", "code-generation", "--unit", unit, "--decision", "skip", "--reason", "t")  # fmt: skip


def skip_inception(p: Bolt) -> None:
    assert p.run("gate", "--stage", "workspace-detection", "--approve", "--by", "B")[0] == 0
    for stage in json.loads((SKILL / "assets" / "stages.json").read_text())["stages"]:
        if not stage["per_unit"] and 2 <= stage["order"] <= 11:
            p.run("decide", "--stage", stage["id"], "--decision", "skip", "--reason", "t")
    assert p.run("jira", "--off", "--reason", "t")[0] == 0


def test_units_refuse_a_cycle_and_an_unknown_repository(bolt: Bolt) -> None:
    cycle = [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": [{"unit": "a"}]}]
    code, data, _ = load_units(bolt, cycle)
    assert code == 4 and "a -> b -> a" in data["error"]
    state = bolt.state
    state["targets"] = [{"repo": "svc", "kind": "greenfield", "codekb_commit": None}]
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    code, data, _ = load_units(bolt, [{"id": "a", "repo": "other"}])
    assert code == 4 and "svc" in data["error"]
    code, data, _ = load_units(bolt, [{"id": "a", "repo": "svc", "depends_on": ["z"]}])
    assert code == 4 and "unknown unit" in data["error"]
    assert load_units(bolt, [{"id": "a", "repo": "svc"}, {"id": "b", "depends_on": ["a"]}])[0] == 0
    assert bolt.state["units"][1]["depends_on"] == [{"unit": "a", "on": "done"}]


def test_next_unit_reports_what_it_waits_for(bolt: Bolt) -> None:
    skip_inception(bolt)
    deps = [{"unit": "u1", "on": "done"}, {"unit": "u1", "on": "contract"}]
    assert load_units(bolt, [{"id": "u1"}, {"id": "u2", "depends_on": deps}])[0] == 0
    code, data, _ = bolt.run("next", "--unit", "u2")
    assert code == 0 and [w["on"] for w in data["blocked_by"]] == ["done"]  # contract is skipped
    assert data["blocked"] == "waits for u1 (done)" and data["unit"] == "u2"
    skip_unit_stages(bolt, "u1")
    assert bolt.run("next", "--unit", "u2")[1]["blocked_by"] == []
    assert bolt.run("next", "--unit", "nope")[0] == 2


def test_next_unit_names_an_open_inception_stage(bolt: Bolt) -> None:
    assert load_units(bolt, [{"id": "u1"}])[0] == 0
    data = bolt.run("next", "--unit", "u1")[1]
    assert data["blocked"].startswith("inception is not finished: ")
    assert data["stage"] == data["blocked"].rsplit(": ", 1)[1]


def test_next_mine_lists_only_the_actors_units(bolt: Bolt, monkeypatch: pytest.MonkeyPatch) -> None:
    skip_inception(bolt)
    load_units(bolt, [{"id": "u1", "owner": "Ada Lovelace"}, {"id": "u2", "owner": "Grace"}])
    monkeypatch.setenv("AIDLC_ACTOR", "ada  lovelace")
    data = bolt.run("next", "--mine")[1]
    assert data["actor"] == "ada lovelace" and [u["unit"] for u in data["units"]] == ["u1"]
    monkeypatch.setenv("AIDLC_ACTOR", "")
    assert bolt.run("next", "--mine")[0] == 1


def test_a_changed_input_is_reported_by_the_gate_and_never_refuses(bolt: Bolt) -> None:
    bolt.write("knowledge/_digest.md", digest())
    reach_produced(bolt)
    ra_files(bolt)
    stage = "requirements-analysis"
    assert list(bolt.state["stages"][stage]["relied_on"]) == ["knowledge/_digest.md"]
    assert "context_changed" not in bolt.run("next")[1]
    bolt.write("knowledge/_digest.md", digest(3))
    assert bolt.run("next")[1]["context_changed"] == ["knowledge/_digest.md"]
    assert bolt.run("status")[1]["stale"][0]["stage"] == stage
    code, data, _ = bolt.run("gate", "--stage", stage, "--approve", "--by", "Ada")
    assert code == 0 and data["context"] == ["knowledge/_digest.md"]
    assert bolt.run("status")[1]["stale"] == []


def test_a_record_without_relied_on_is_never_flagged(bolt: Bolt) -> None:
    bolt.write("knowledge/_digest.md", digest())
    reach_produced(bolt)
    ra_files(bolt)
    state = bolt.state
    del state["stages"]["requirements-analysis"]["relied_on"]
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    bolt.write("knowledge/_digest.md", digest(3))
    assert "context_changed" not in bolt.run("next")[1]
    assert bolt.run("gate", "--stage", "requirements-analysis", "--approve", "--by", "Ada")[0] == 0


def test_brief_has_five_sections_and_can_be_written(bolt: Bolt) -> None:
    skip_inception(bolt)
    load_units(bolt, [{"id": "u1", "name": "Billing", "owner": "Ada", "repo": "svc"}])
    code, data, _ = bolt.run("brief", "--unit", "u1")
    assert code == 0 and not (bolt.path / "docs/construction/u1/brief.md").exists()
    headings = [line for line in data["markdown"].splitlines() if line.startswith("#")]
    assert headings == ["# Unit u1: Billing", "## Waits for", "## Read first",
                        "## Changed since you last produced", "## Next"]  # fmt: skip
    assert "aidlc_refs.py show --bolt" in data["markdown"] and "| Owner | Ada |" in data["markdown"]
    code, data, _ = bolt.run("brief", "--unit", "u1", "--write")
    written = bolt.path / "docs" / "construction" / "u1" / "brief.md"
    assert code == 0 and written.read_text(encoding="utf-8") == data["markdown"]


def test_assign_changes_the_owner_and_logs_it(bolt: Bolt) -> None:
    load_units(bolt, [{"id": "u1", "owner": "Ada"}])
    assert bolt.run("assign", "--unit", "u1", "--owner", "Grace")[0] == 0
    assert bolt.state["units"][0]["owner"] == "Grace"
    last = bolt.log_lines()[-1]
    assert "| assign |" in last and last.endswith("[u1] Ada -> Grace")
    assert bolt.run("assign", "--unit", "zz", "--owner", "X")[0] == 2
    assert load_units(bolt, [{"id": "u1"}])[0] == 0 and bolt.state["units"][0]["owner"] == "Grace"


# --- units that persist on their own, and the guards around them ---------------


def split_bolt(tmp_path: Path) -> Bolt:
    root = tmp_path / "split"
    root.mkdir()
    done = open_bolt(root, "--units", "split")
    assert done.returncode == 0, done.stderr
    return Bolt(root, Path(json.loads(done.stdout)["bolt"]))


def test_a_split_bolt_moves_one_unit_without_touching_the_shared_files(tmp_path: Path) -> None:
    p = split_bolt(tmp_path)
    skip_inception(p)
    assert load_units(p, [{"id": "u1"}, {"id": "u2"}])[0] == 0
    assert (p.path / "units" / "u2" / "state.json").is_file()
    assert "stages" not in p.state["units"][0] and "current" not in p.state
    shared = {name: (p.path / name).read_bytes() for name in ("state.json", "log.md")}
    u1 = (p.path / "units" / "u1" / "state.json").read_bytes()
    code, data, _ = p.run("decide", "--stage", "functional-design", "--unit", "u2",
                          "--decision", "skip", "--reason", "t")  # fmt: skip
    assert code == 0, data
    assert {n: (p.path / n).read_bytes() for n in shared} == shared
    assert (p.path / "units" / "u1" / "state.json").read_bytes() == u1
    own = json.loads((p.path / "units" / "u2" / "state.json").read_text(encoding="utf-8"))
    assert own["stages"]["functional-design"]["decision"] == "skip"
    assert "| decide |" in (p.path / "units" / "u2" / "log.md").read_text(encoding="utf-8")
    assert "current" in p.run("status")[1]  # computed in memory after load


def test_next_in_a_split_bolt_lists_every_unit_in_progress(tmp_path: Path) -> None:
    p = split_bolt(tmp_path)
    skip_inception(p)
    load_units(p, [{"id": "u1"}, {"id": "u2", "depends_on": ["u1"]}])
    data = p.run("next")[1]
    assert data["action"] == "units" and [u["unit"] for u in data["units"]] == ["u1", "u2"]
    assert p.run("status")[1]["next_action"] == (
        "units in progress: u1 functional-design, u2 waits for u1"
    )


def test_a_command_holds_the_checkout_lock_and_leaves_no_file_behind(
    bolt: Bolt, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Outside git the lock sits at the planning root; a held lock stops a changing command."""
    lock = bolt.root / ".aidlc.lock"
    assert bolt.run("park", "--note", "n")[0] == 0 and not lock.exists()
    assert not (bolt.path / ".aidlc.lock").exists()  # the per-Bolt lock is gone
    if sys.platform == "win32":  # pragma: no cover
        pytest.skip("flock is not available")
    import fcntl

    monkeypatch.setenv("AIDLC_LOCK_WAIT", "0.5")
    with lock.open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        code, data, _ = bolt.run("park", "--note", "n")
        assert code == 1 and "another session in this checkout" in data["error"]
        assert str(lock) in data["error"]
        assert bolt.run("status")[0] == 0  # a read takes no lock
    assert bolt.run("park", "--note", "n")[0] == 0


def test_a_step_on_someone_elses_unit_runs_and_warns(
    bolt: Bolt, monkeypatch: pytest.MonkeyPatch
) -> None:
    skip_inception(bolt)
    load_units(bolt, [{"id": "u1", "owner": "Ada Lovelace"}])
    step = ("step", "--stage", "code-generation", "--unit", "u1", "--to", "asked")
    monkeypatch.setenv("AIDLC_ACTOR", "Grace Hopper")
    code, data, _ = bolt.run(*step)
    assert code == 0, data
    assert data["warnings"] == ["unit u1 is owned by Ada Lovelace; you are Grace Hopper"]
    assert "owned by Ada Lovelace" in bolt.log_lines()[-1]
    assert bolt.state["units"][0]["stages"]["code-generation"]["step"] == "asked"
    monkeypatch.setenv("AIDLC_ACTOR", "ada  lovelace")
    code, data, _ = bolt.run(
        "step", "--stage", "code-generation", "--unit", "u1", "--to", "analysed"
    )
    assert code == 0 and "warnings" not in data


def test_the_owner_warning_covers_decide_decision_id_and_jira(
    bolt: Bolt, monkeypatch: pytest.MonkeyPatch
) -> None:
    skip_inception(bolt)
    load_units(bolt, [{"id": "u1", "owner": "Ada Lovelace"}])
    monkeypatch.setenv("AIDLC_ACTOR", "Grace Hopper")
    for args in (
        ("decide", "--stage", "nfr-requirements", "--unit", "u1", "--decision", "skip",
         "--reason", "none"),
        ("decision-id", "--unit", "u1"),
        ("jira", "--unit", "u1", "--story", "AB-1"),
    ):  # fmt: skip
        code, data, _ = bolt.run(*args)
        assert code == 0 and len(data["warnings"]) == 1, (args, data)
    assert bolt.run("assign", "--unit", "u1", "--owner", "Grace Hopper")[0] == 0


def test_the_takeover_flag_is_gone(bolt: Bolt) -> None:
    skip_inception(bolt)
    load_units(bolt, [{"id": "u1"}])
    step = ("step", "--stage", "code-generation", "--unit", "u1", "--to", "asked")
    assert bolt.run(*step, "--takeover", "x")[0] == 2


def test_decision_ids_are_numbered_per_unit(bolt: Bolt) -> None:
    load_units(bolt, [{"id": "u1"}, {"id": "u2"}])
    data = bolt.run("decision-id", "--unit", "u1", "--count", "2")[1]
    assert data["ids"] == ["D1", "D2"] and data["cite_as"] == ["u1:D1", "u1:D2"]
    assert bolt.run("decision-id", "--unit", "u2")[1]["cite_as"] == ["u2:D1"]
    assert bolt.run("decision-id", "--unit", "u1")[1]["ids"] == ["D3"]
    assert bolt.state["decision_seq"] == 0
    assert bolt.run("decision-id")[1]["ids"] == ["D1"]
    assert bolt.run("decision-id", "--unit", "zz")[0] == 2


def decision_table(*ids: str) -> str:
    rows = "\n".join(f"| {i} | Choice {i} | accepted |" for i in ids)
    return f"# Decisions\n\n| ID | Decision | Status |\n|----|----------|--------|\n{rows}\n"


def set_counter(bolt: Bolt, value: int) -> None:
    state = bolt.state
    state["decision_seq"] = value
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_a_decision_id_starts_above_the_counter_and_the_records(bolt: Bolt) -> None:
    """The record holds D75 but the counter says 73: D76 is next, and the counter follows."""
    bolt.write("architecture/hla-decisions.md", decision_table("D1", "D74", "D75"))
    set_counter(bolt, 73)
    data = bolt.run("decision-id", "--count", "2")[1]
    assert data["ids"] == ["D76", "D77"] and bolt.state["decision_seq"] == 77
    assert bolt.run("decision-id")[1]["ids"] == ["D78"]


def test_a_decision_id_counts_the_technical_design_record_too(bolt: Bolt) -> None:
    bolt.write("architecture/hla-decisions.md", decision_table("D3"))
    bolt.write("architecture/tdd-decisions.md", decision_table("D9", "D12"))
    assert bolt.run("decision-id")[1]["ids"] == ["D13"]
    set_counter(bolt, 40)  # a counter above every record still wins
    assert bolt.run("decision-id")[1]["ids"] == ["D41"]


def test_a_unit_counter_ignores_the_bolt_records(bolt: Bolt) -> None:
    load_units(bolt, [{"id": "u1"}])
    bolt.write("architecture/hla-decisions.md", decision_table("D75"))
    assert bolt.run("decision-id", "--unit", "u1")[1]["ids"] == ["D1"]


def test_the_provisional_flag_is_gone(bolt: Bolt) -> None:
    code, _, _ = bolt.run("decision-id", "--provisional")
    assert code == 2 and bolt.state["decision_seq"] == 0
    assert "provisional" not in bolt.run("decision-id")[1]


# --- overview and decision status ----------------------


def open_named(root: Path, slug: str, date: str, *args: str) -> Bolt:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "open", "--root", str(root), "--slug", slug, "--title", slug,
         "--intent", "Try it", "--date", date, *args],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    return Bolt(root, Path(json.loads(done.stdout)["bolt"]))


def overview(root: Path, *args: str) -> tuple[int, dict[str, Any]]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "overview", "--root", str(root), *args],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    return done.returncode, (json.loads(done.stdout) if done.stdout.startswith("{") else {})


def test_overview_is_flat_and_reports_unit_problems(tmp_path: Path) -> None:
    open_named(tmp_path, "programme", "2026-01-05")
    second = open_named(tmp_path, "phase", "2026-01-06", "--units", "split")
    skip_inception(second)
    load_units(second, [{"id": "u1"}, {"id": "u2", "owner": "Ada", "depends_on": ["u1"]}])
    code, data = overview(tmp_path)
    assert code == 0
    rows = {r["id"]: r for r in data["bolts"]}
    assert list(rows) == ["2026-01-05-programme", "2026-01-06-phase"]
    assert all({"parent", "children", "kind"}.isdisjoint(row) for row in rows.values())
    found = {(p["code"], p["where"]) for p in rows["2026-01-06-phase"]["problems"]}
    assert {("unowned-unit", "u1"), ("waiting-unit", "u2")} <= found
    assert not [c for c, _ in found if c.startswith("parent")]
    assert [u["id"] for u in rows["2026-01-06-phase"]["units"]] == ["u1", "u2"]
    text = subprocess.run([sys.executable, str(SCRIPT), "overview", "--root", str(tmp_path),
                           "--format", "text"], capture_output=True, text=True).stdout  # fmt: skip
    lines = text.splitlines()
    assert "2026-01-05-programme [open] programme" in lines
    assert "2026-01-06-phase [open] phase" in lines  # no indentation: nothing nests
    assert "  unit u2 | Ada | " in text


def test_overview_goes_on_past_an_unreadable_bolt_and_lists_the_last_log_lines(
    tmp_path: Path,
) -> None:
    p = open_named(tmp_path, "good", "2026-01-05", "--units", "split")
    skip_inception(p)
    load_units(p, [{"id": "u1"}, {"id": "u2"}])
    for unit in ("u1", "u2", "u1"):
        p.run("decide", "--stage", "functional-design", "--unit", unit, "--decision", "skip",
              "--reason", "t")  # fmt: skip
    broken = tmp_path / "bolts" / "2026-01-06-broken"
    broken.mkdir()
    (broken / "state.json").write_text("{", encoding="utf-8")
    newer = tmp_path / "bolts" / "2026-01-07-newer"
    newer.mkdir()
    (newer / "state.json").write_text('{"schema": 1, "framework": 99}', encoding="utf-8")
    code, data = overview(tmp_path, "--log", "3")
    assert code == 0 and data["bolts"][0]["id"] == "2026-01-05-good"
    errors = {r["id"]: r["error"] for r in data["bolts"] if "error" in r}
    assert set(errors) == {"2026-01-06-broken", "2026-01-07-newer"}
    assert "newer skills" in errors["2026-01-07-newer"]
    times = [e["time"] for e in data["log"]]
    assert len(times) == 3 and times == sorted(times)
    assert {e["unit"] for e in data["log"]} <= {"", "u1", "u2"}
    assert data["bolts"][0]["last"]["event"] == "decide"


def test_decision_status_words_are_checked_only_when_the_column_exists(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("aidlc_state_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["aidlc_state_under_test"] = module  # dataclasses look the module up by name
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    stage = next(s for s in module.load_catalog() if s["id"] == "hla")
    base = {"targets": [], "units": []}
    record = tmp_path / "architecture" / "hla-decisions.md"
    record.parent.mkdir()
    plain = "| Id | Layer | Decision | Reason | Source | Flag |\n|---|---|---|---|---|---|\n"
    record.write_text(plain + "| D1 | 1 | x | y | A-Q1 | - |\n", encoding="utf-8")
    assert module.decision_status_findings(tmp_path, base, stage, None) == []
    rich = plain.replace("| Flag |", "| Flag | Status | Owner |").replace(
        "---|\n", "---|---|---|\n"
    )
    record.write_text(
        rich
        + "| D1 | 1 | x | y | A-Q1 | - | accepted | Ada |\n| D2 | 1 | x | y | A-Q2 | - | maybe | - |\n",
        encoding="utf-8",
    )
    found = module.decision_status_findings(tmp_path, base, stage, None)
    assert [f["code"] for f in found] == ["decision-status-unknown"] and "D2" in found[0]["message"]


# --- one Bolt: no parent, no child, no frame kind -----------------------------


def test_open_rejects_parent_and_kind_and_the_kind_command_is_gone(tmp_path: Path) -> None:
    base = ["open", "--root", str(tmp_path), "--slug", "x", "--title", "X", "--intent", "Try"]
    for extra in (["--parent", "2026-01-05-other"], ["--kind", "frame"]):
        done = subprocess.run(
            [sys.executable, str(SCRIPT), *base, *extra],
            capture_output=True, text=True, timeout=60,
        )  # fmt: skip
        assert done.returncode == 2 and "unrecognized arguments" in done.stderr
    assert not (tmp_path / "bolts").exists()
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "kind", "--bolt", str(tmp_path), "--set", "frame"],
        capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert done.returncode == 2


def test_a_new_bolt_carries_no_kind_and_no_parent_anywhere(tmp_path: Path) -> None:
    bolt = open_named(tmp_path, "solo", "2026-01-05")
    assert "kind" not in bolt.state and "parent" not in bolt.state
    code, data, _ = bolt.run("status")
    assert code == 0 and "kind" not in data and "parent" not in data
    text = bolt.run("status", "--format", "text")[2]
    assert "Kind:" not in text and "Parent" not in text
    assert bolt.state["stages"]["requirements-analysis"]["decision"] == "execute"
    stages = open_named(tmp_path, "fix", "2026-01-06", "--scope", "bugfix").state
    assert {r["decision"] for r in stages["units"][0]["stages"].values()} != {"skip"}


def test_an_old_state_with_a_frame_kind_and_a_parent_loads_and_loses_the_keys(
    tmp_path: Path,
) -> None:
    bolt = open_named(tmp_path, "old", "2026-01-05")
    state = bolt.state
    state["kind"] = "frame"
    state["parent"] = {"id": "2026-01-01-gone", "path": "bolts/2026-01-01-gone"}
    (bolt.path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    code, data, _ = bolt.run("status")
    assert code == 0 and "kind" not in data
    nxt = bolt.run("next")[1]
    assert nxt["stage"] == "workspace-detection" and not nxt["done"]
    data = bolt.run("inputs", "--stage", "hla")[1]  # exit 3: this Bolt has no knowledge yet
    assert data["inputs"] and not [r for r in data["inputs"] if r["path"].startswith("parent:")]
    assert "kind" in json.loads((bolt.path / "state.json").read_text(encoding="utf-8"))
    assert bolt.run("park", "--note", "n")[0] == 0
    assert "kind" not in bolt.state and "parent" not in bolt.state
    assert bolt.state["stages"]["requirements-analysis"]["decision"] == "execute"


# --- verdicts: a failed verification is never stored as passed ----------------

BAT = "docs/construction/build-and-test/"


def build_and_test_produced(p: Bolt, results: str) -> None:
    """Skip everything before Build and Test, then write its files with ``results``."""
    skip_inception(p)
    load_units(p, [{"id": "u1"}])
    for stage in ("functional-design", "nfr-requirements", "nfr-design", "infrastructure-design"):
        p.run("decide", "--stage", stage, "--unit", "u1", "--decision", "skip", "--reason", "t")
    p.run("decide", "--stage", "code-generation", "--unit", "u1", "--decision", "skip",
          "--reason", "t")  # fmt: skip
    for name in (
        "build-instructions.md",
        "build-and-test-summary.md",
        "cross-unit-traceability.md",
    ):
        p.write(BAT + name, digest())
    p.write(BAT + "test-results.md", results)
    assert p.run("step", "--stage", "build-and-test", "--to", "produced")[0] == 0


GATE = ("gate", "--stage", "build-and-test", "--approve")


def verdict_codes(data: dict[str, Any]) -> list[str]:
    return [f["code"] for f in data["findings"]]


@pytest.mark.parametrize(
    "text",
    [
        digest(),  # no line
        verdict_doc("Verdict: pass\nVerdict: pass"),  # two lines
        verdict_doc("Verdict: passed"),  # another word
        verdict_doc("Verdict:"),  # empty
        verdict_doc("Verdict: pass - all green"),  # pass takes no reason
        verdict_doc("  Verdict: pass"),  # not at the start of a line
    ],
)
def test_a_missing_or_malformed_verdict_refuses_the_gate(bolt: Bolt, text: str) -> None:
    build_and_test_produced(bolt, text)
    code, data, _ = bolt.run(*GATE, "--note", "go on")
    assert code == 1 and verdict_codes(data) == ["verdict-missing"]
    assert bolt.state["stages"]["build-and-test"]["step"] == "produced"


@pytest.mark.parametrize(
    "line",
    ["Verdict: fail", "verdict: FAIL", "Verdict: fail - 3 tests red", "Verdict: fail: flaky"],
)
def test_a_fail_verdict_cannot_be_passed_with_any_flags(bolt: Bolt, line: str) -> None:
    build_and_test_produced(bolt, verdict_doc(line))
    for extra in ((), ("--note", "proceed anyway"), ("--by", "Boss", "--note", "I decide")):
        code, data, _ = bolt.run(*GATE, *extra)
        assert code == 1 and verdict_codes(data) == ["verdict-fail"], extra
        assert "stays open" in data["findings"][0]["message"]
    record = bolt.state["stages"]["build-and-test"]
    assert record["step"] == "produced" and "verdict" not in record
    assert bolt.run("gate", "--stage", "build-and-test", "--approve", "--channel", "x")[0] == 2


def test_a_not_run_verdict_passes_only_with_a_note_and_is_stored(bolt: Bolt) -> None:
    build_and_test_produced(bolt, verdict_doc("Verdict: not-run - no test database"))
    code, data, _ = bolt.run(*GATE)
    assert code == 1 and verdict_codes(data) == ["verdict-not-run"]
    code, data, _ = bolt.run(*GATE, "--note", "nothing to test in this change")
    assert code == 0 and data["verdict"] == "not-run"
    assert bolt.state["stages"]["build-and-test"]["verdict"] == "not-run"


def test_a_pass_verdict_is_stored(bolt: Bolt) -> None:
    build_and_test_produced(bolt, verdict_doc("verdict: Pass"))
    code, data, _ = bolt.run(*GATE)
    assert code == 0 and data["verdict"] == "pass"
    assert bolt.state["stages"]["build-and-test"]["verdict"] == "pass"
    assert "not_verified" in bolt.run("status")[1]
    assert bolt.run("status")[1]["not_verified"] == []


def test_a_not_run_stage_is_shown_as_not_verified(bolt: Bolt) -> None:
    build_and_test_produced(bolt, verdict_doc("Verdict: not-run"))
    assert bolt.run(*GATE, "--note", "accepted unverified")[0] == 0
    assert bolt.run("status")[1]["not_verified"] == [{"stage": "build-and-test", "unit": None}]
    assert (
        "Not verified (verdict not-run): build-and-test"
        in bolt.run("status", "--format", "text")[2]
    )
    overview = subprocess.run(
        [sys.executable, str(SCRIPT), "overview", "--root", str(bolt.root), "--format", "text"],
        capture_output=True, text=True, timeout=60,
    ).stdout  # fmt: skip
    assert "not verified: build-and-test" in overview


def unit_stage_ready(p: Bolt, results: str) -> None:
    skip_inception(p)
    load_units(p, [{"id": "u1"}])
    for stage in ("functional-design", "nfr-requirements", "nfr-design", "infrastructure-design"):
        p.run("decide", "--stage", stage, "--unit", "u1", "--decision", "skip", "--reason", "t")
    cg = "docs/construction/u1/code-generation/"
    for name in ("code-generation-plan.md", "unit-test-instructions.md"):
        p.write(cg + name, digest())
    p.write(cg + "code-summary.md", results)
    p.write(cg + "source-manifest.json", "{}")
    p.write(cg + "traceability.json", "{}")
    p.run("step", "--stage", "code-generation", "--unit", "u1", "--to", "produced")


def test_code_generation_checks_the_units_own_verdict(bolt: Bolt) -> None:
    unit_stage_ready(bolt, digest())
    gate = ("gate", "--stage", "code-generation", "--unit", "u1", "--approve")
    code, data, _ = bolt.run(*gate, "--note", "x")
    assert code == 1 and verdict_codes(data) == ["verdict-missing"]
    bolt.write("docs/construction/u1/code-generation/code-summary.md", verdict_doc("Verdict: fail"))
    code, data, _ = bolt.run(*gate, "--note", "x")
    assert code == 1 and verdict_codes(data) == ["verdict-fail"]
    bolt.write("docs/construction/u1/code-generation/code-summary.md", verdict_doc())
    assert bolt.run(*gate)[0] == 0
    assert bolt.state["units"][0]["stages"]["code-generation"]["verdict"] == "pass"


def test_only_stages_with_a_verdict_key_check_one(bolt: Bolt) -> None:
    code, data, _ = bolt.run("gate", "--stage", "workspace-detection", "--approve")
    assert code == 0 and "verdict" not in data
    assert "verdict" not in bolt.state["stages"]["workspace-detection"]
