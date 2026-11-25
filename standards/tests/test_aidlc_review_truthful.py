"""A failed or skipped verification is never shown as verified (review fixes, group H1)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from test_aidlc_slices_stages import finish, row, two_slices, write_bat
from test_aidlc_state import (
    SCRIPT,
    SKILL,
    Bolt,
    build_and_test_produced,
    load_units,
    open_bolt,
    skip_inception,
    unit_stage_ready,
    verdict_doc,
)

GATE_SLICE = ("gate", "--stage", "build-and-test", "--slice", "s1")


@pytest.fixture
def bolt(tmp_path: Path) -> Bolt:
    done = open_bolt(tmp_path)
    assert done.returncode == 0, done.stderr
    return Bolt(tmp_path, Path(json.loads(done.stdout)["bolt"]))


def read_verdict(text: str) -> Any:
    spec = importlib.util.spec_from_file_location("aidlc_state_h1", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    cast(Any, spec.loader).exec_module(module)
    return module.read_verdict(text)


def test_a_failed_verdict_cannot_be_skipped_into_done(bolt: Bolt) -> None:
    two_slices(bolt)
    finish(bolt, "u1", "u2")
    write_bat(bolt, "s1", "Verdict: fail - 2 red")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    assert bolt.run(*GATE_SLICE, "--approve")[0] == 1  # verdict-fail
    code, data, _ = bolt.run("decide", "--stage", "build-and-test", "--slice", "s1",
                             "--decision", "skip", "--reason", "give up")  # fmt: skip
    assert code == 1 and "not skipped" in data["error"]
    assert bolt.run("close", "--status", "complete")[0] == 1
    assert row(bolt, "s1")["status"] != "verified"


def test_a_failed_code_verdict_cannot_be_skipped_for_a_unit(bolt: Bolt) -> None:
    unit_stage_ready(bolt, verdict_doc("Verdict: fail"))
    gate = ("gate", "--stage", "code-generation", "--unit", "u1", "--approve")
    assert bolt.run(*gate)[0] == 1
    code, data, _ = bolt.run("decide", "--stage", "code-generation", "--unit", "u1",
                             "--decision", "skip", "--reason", "x")  # fmt: skip
    assert code == 1 and "not skipped" in data["error"]
    assert bolt.state["units"][0]["stages"]["code-generation"]["decision"] == "execute"


def test_skipping_before_it_starts_is_allowed_but_never_called_verified(bolt: Bolt) -> None:
    two_slices(bolt)
    finish(bolt, "u1", "u2")
    code, _, _ = bolt.run("decide", "--stage", "build-and-test", "--slice", "s1",
                          "--decision", "skip", "--reason", "docs only")  # fmt: skip
    assert code == 0
    current = row(bolt, "s1")
    assert current["status"] == "built" and current["verification_skipped"] is True
    assert "verification skipped" in bolt.run("status", "--format", "text")[2]
    # a Slice waiting for it is not held back forever by an explicit skip
    assert row(bolt, "s2")["waits"] == []


def test_a_unit_whose_code_verdict_was_skipped_carries_the_marker(bolt: Bolt) -> None:
    skip_inception(bolt)
    load_units(bolt, [{"id": "u1"}])
    for stage in ("functional-design", "nfr-requirements", "nfr-design", "infrastructure-design"):
        bolt.run("decide", "--stage", stage, "--unit", "u1", "--decision", "skip", "--reason", "t")
    bolt.run("decide", "--stage", "code-generation", "--unit", "u1", "--decision", "skip",
             "--reason", "t")  # fmt: skip
    detail = bolt.run("status")[1]["unit_details"][0]
    assert detail["verification_skipped"] is True
    assert "verification skipped" in bolt.run("status", "--format", "text")[2]


def test_verified_needs_a_passing_stored_verdict(bolt: Bolt) -> None:
    two_slices(bolt)
    finish(bolt, "u1", "u2")
    write_bat(bolt, "s1", "Verdict: not-run")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    assert bolt.run(*GATE_SLICE, "--approve", "--note", "accepted")[0] == 0
    assert row(bolt, "s1")["status"] == "built"
    bolt.run(*GATE_SLICE, "--request-changes", "--note", "again")
    write_bat(bolt, "s1")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    assert bolt.run(*GATE_SLICE, "--approve")[0] == 0
    assert row(bolt, "s1")["status"] == "verified"


@pytest.mark.parametrize(
    ("text", "word"),
    [
        ("```\nVerdict: fail\n```\nVerdict: pass\n", "pass"),  # fenced lines do not count
        ("~~~\nVerdict: pass\nVerdict: fail\n~~~\nVerdict: fail\n", "fail"),
        ("﻿Verdict: pass\n", "pass"),
        ("  Verdict: pass\n", "pass"),
        ("**Verdict**: fail\n", "fail"),
        ("**Verdict: fail**\n", "fail"),
        ("> Verdict: not-run - no database\n", "not-run"),
        ("# Verdict: pass\n", "pass"),
        ("- _Verdict_: pass\n", "pass"),
        ("**Verdict: fail**\nVerdict: pass\n", None),  # two lines of any decoration
        ("> Verdict: fail\nVerdict: pass\n", None),
        ("﻿Verdict: fail\nVerdict: pass\n", None),
        ("Verdict: pass\n\nThe verdict is clear.\n", "pass"),  # prose is not a verdict line
    ],
)
def test_the_verdict_parser_sees_every_decorated_line(text: str, word: str | None) -> None:
    assert read_verdict(text) == word


def test_a_decorated_fail_beside_a_plain_pass_refuses_the_gate(bolt: Bolt) -> None:
    build_and_test_produced(bolt, verdict_doc("**Verdict: fail**\nVerdict: pass"))
    code, data, _ = bolt.run("gate", "--stage", "build-and-test", "--approve")
    assert code == 1 and [f["code"] for f in data["findings"]] == ["verdict-missing"]


def test_a_gate_on_someone_elses_unit_or_slice_warns(
    bolt: Bolt, monkeypatch: pytest.MonkeyPatch
) -> None:
    two_slices(bolt)
    finish(bolt, "u1", "u2")
    write_bat(bolt, "s1")
    monkeypatch.setenv("AIDLC_ACTOR", "Grace Hopper")
    bolt.run("step", "--stage", "build-and-test", "--slice", "s1", "--to", "produced")
    code, data, _ = bolt.run(*GATE_SLICE, "--approve")
    assert code == 0 and data["warnings"] == ["slice s1 is owned by Ana; you are Grace Hopper"]
    code, data, _ = bolt.run(*GATE_SLICE, "--request-changes", "--note", "more")
    assert code == 0 and data["warnings"] == ["slice s1 is owned by Ana; you are Grace Hopper"]
    # a Unit stage too
    unit_gate = ("gate", "--stage", "code-generation", "--unit", "u2", "--request-changes")
    bolt.run("decide", "--stage", "code-generation", "--unit", "u2", "--decision", "execute",
             "--reason", "x")  # fmt: skip
    code, data, _ = bolt.run(*unit_gate, "--note", "again")
    assert code == 0 and data["warnings"] == ["unit u2 is owned by Ben; you are Grace Hopper"]


def test_no_stage_text_names_an_approver() -> None:
    text = (SKILL / "assets" / "stages.json").read_text(encoding="utf-8")
    assert "approver" not in text
