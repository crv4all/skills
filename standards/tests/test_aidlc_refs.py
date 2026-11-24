"""``aidlc_refs.py``: resolve, link and index the ids of a bolt.

The tests build small bolts in ``tmp_path``, run the script as a subprocess
and assert the exact text it leaves behind, because a linker that rewrites
something it should have left alone corrupts an approved artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / "skills" / "processes" / "crv-aidlc"
REFS = SKILL / "scripts" / "aidlc_refs.py"
TRACE = SKILL / "scripts" / "check_traceability.py"
LINT = SKILL / "scripts" / "lint_questions.py"

DECISIONS = """# Decisions

## D10 Breeding app is the target
(Superseded wording) The Breeding app is the target for the functions SireMatch 1 users have today. More.

| Id | Decision | Why |
|---|---|---|
| D11 | Use `Delta` for **all** [storage](x.md). Second sentence. | speed |
| D12 | short | the reason for choosing this option |
"""
ANSWERS = """# Questions A

## Q1 Which region?

Answer: A

## Q2 What size?

Answer: B
"""


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def bolt(tmp_path: Path) -> Path:
    write(tmp_path, "architecture/hla-decisions.md", DECISIONS)
    write(tmp_path, "architecture/hla-questions-a.md", ANSWERS)
    return tmp_path


@pytest.fixture
def refs(run_script):
    def _refs(*args: str):
        return run_script(REFS, list(args))

    return _refs


def show(refs, bolt: Path, *ids: str, extra: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    done = refs("show", "--bolt", str(bolt), *extra, *ids)
    return json.loads(done.stdout)


def link(refs, bolt: Path, *extra: str) -> dict[str, Any]:
    done = refs("link", "--bolt", str(bolt), *extra)
    assert done.returncode == 0, done.stderr
    return done.json


def cite(bolt: Path, text: str, name: str = "cites.md") -> Path:
    return write(bolt, f"architecture/{name}", text)


# -- declarations and glosses -------------------------------------------------


def test_heading_gloss_drops_markup_and_the_id(refs, bolt: Path) -> None:
    write(bolt, "architecture/h.md", "## FR-2: **Export** a `report`\n")
    (entry,) = show(refs, bolt, "FR-2")
    assert entry["kind"] == "heading" and entry["gloss"] == "Export a report"
    assert entry["line"] == 1 and entry["file"] == "architecture/h.md"


def test_row_gloss_uses_the_decision_column_and_cleans_it(refs, bolt: Path) -> None:
    (entry,) = show(refs, bolt, "D11")
    assert entry["kind"] == "row"
    assert entry["gloss"] == "Use Delta for all storage."


def test_row_gloss_prefers_title_over_decision(refs, bolt: Path) -> None:
    write(
        bolt,
        "t.md",
        "| Id | Decision | Title |\n|---|---|---|\n| D20 | long text here now | The title |\n",
    )
    assert show(refs, bolt, "D20")[0]["gloss"] == "The title"


def test_row_gloss_without_known_column_takes_first_cell_of_three_words(refs, bolt: Path) -> None:
    write(bolt, "t.md", "| Id | Owner | Notes |\n|---|---|---|\n| D21 | Ann | Keep the old API |\n")
    assert show(refs, bolt, "D21")[0]["gloss"] == "Keep the old API"


def test_leading_parenthetical_is_dropped_from_a_row_gloss(refs, bolt: Path) -> None:
    write(bolt, "t.md", "| Id | Statement |\n|---|---|\n| D22 | (draft) Ship it on Friday |\n")
    assert show(refs, bolt, "D22")[0]["gloss"] == "Ship it on Friday"


def test_gloss_is_cut_at_a_word_boundary(refs, bolt: Path) -> None:
    words = " ".join(["alpha"] * 30)
    write(bolt, "t.md", f"## D23 {words}\n")
    gloss = show(refs, bolt, "D23")[0]["gloss"]
    assert gloss.endswith("…") and len(gloss) <= 90 and "alph…" not in gloss


def test_the_heading_wins_over_a_row_and_the_other_is_kept_as_also(refs, bolt: Path) -> None:
    write(bolt, "a.md", "| Id | Title |\n|---|---|\n| D30 | From the row |\n")
    write(bolt, "z.md", "## D30 From the heading\n")
    (entry,) = show(refs, bolt, "D30")
    assert entry["kind"] == "heading" and entry["file"] == "z.md"
    assert entry["also"] == [{"file": "a.md", "line": 3, "kind": "row"}]
    assert link(refs, bolt, "--dry-run")["duplicates"][0]["id"] == "D30"


def test_declarations_inside_fences_and_header_rows_are_ignored(refs, bolt: Path) -> None:
    write(bolt, "f.md", "```\n## D40 hidden\n```\n\n| D41 | x |\n|---|---|\n| D42 | y one two |\n")
    found = show(refs, bolt, "D40", "D41", "D42")
    assert [e["found"] for e in found] == [False, False, True]


def test_folders_that_are_not_bolt_text_are_not_scanned(refs, bolt: Path) -> None:
    for rel in ("knowledge/k.md", "inputs/i.md", "docs/export/e.md", ".hidden/h.md"):
        write(bolt, rel, "## D50 hidden\n")
    assert show(refs, bolt, "D50")[0]["found"] is False


def test_a_file_that_is_not_utf8_exits_4(refs, bolt: Path) -> None:
    (bolt / "bad.md").write_bytes(b"## D1 \xff\xfe\n")
    assert refs("show", "--bolt", str(bolt), "D1").returncode == 4


def test_a_missing_bolt_exits_3(refs, tmp_path: Path) -> None:
    assert refs("link", "--bolt", str(tmp_path / "nope")).returncode == 3


# -- what is never a reference -------------------------------------------------


def linked(refs, bolt: Path, text: str) -> str:
    path = cite(bolt, text)
    link(refs, bolt)
    return path.read_text(encoding="utf-8")


def test_a_plain_reference_is_linked_and_the_block_is_written(refs, bolt: Path) -> None:
    out = linked(refs, bolt, "# Cites\n\nSee D10 and D11.\n")
    assert "[D10]: hla-decisions.md#L3\n" in out and '"' not in out.split("begin")[1]
    cite(bolt, "# Cites\n\nSee D10 and D11.\n")
    link(refs, bolt, "--titles")
    out = (bolt / "architecture/cites.md").read_text(encoding="utf-8")
    assert out.startswith("# Cites\n\nSee [D10] and [D11].\n\n<!-- aidlc-refs:begin")
    assert '[D10]: hla-decisions.md#L3 "Breeding app is the target"' in out
    assert '[D11]: hla-decisions.md#L8 "Use Delta for all storage."' in out
    assert out.endswith("<!-- aidlc-refs:end -->\n")


@pytest.mark.parametrize(
    "text",
    [
        "parent:D10 stays.\n",
        "WP D10 is a source id.\n",
        "D10: at the start of a line.\n",
        "A code span `D10` stays.\n",
        "```\nD10\n```\n",
        "---\nrefs: D10\n---\nbody\n",
        "<!-- D10 -->\n",
        "<!--\nD10\n-->\n",
        "[D10](hla-decisions.md) is linked.\n",
        "[the target][D10] by reference.\n",
        "[D10]: hla-decisions.md\n",
        "<https://x.test/D10> and https://x.test/D10\n",
        "[D10] was bracketed by hand.\n",
        "D10(see) and D10[x] and D10] stay.\n",
        "path/D10 and #D10.\n",
        "# D10 in a heading\n",
        "Q1 2027 is a quarter, and A-Q9 has no heading.\n",
    ],
)
def test_text_that_is_not_a_reference_is_left_untouched(refs, bolt: Path, text: str) -> None:
    path = cite(bolt, text)
    link(refs, bolt)
    assert path.read_text(encoding="utf-8") == text


def test_qualified_ids_are_reported_not_linked(refs, bolt: Path) -> None:
    path = cite(bolt, "WP D10 and D11.\n")
    result = link(refs, bolt)
    assert "WP D10 and [D11]." in path.read_text(encoding="utf-8")
    assert result["skipped_qualified"] == [
        {"id": "D10", "file": "architecture/cites.md", "line": 1, "qualifier": "WP"}
    ]


def test_a_row_does_not_cite_its_own_id_but_cites_others(refs, bolt: Path) -> None:
    path = cite(bolt, "| Id | Decision |\n|---|---|\n| D60 | Depends on D10 and D60 |\n")
    link(refs, bolt)
    assert "| D60 | Depends on [D10] and D60 |" in path.read_text(encoding="utf-8")


def test_an_undeclared_id_with_a_known_prefix_is_reported(refs, bolt: Path) -> None:
    cite(bolt, "See D99 and SHA256.\n")
    result = link(refs, bolt)
    assert [u["id"] for u in result["unresolved"]] == ["D99"]
    assert result["unresolved"][0]["line"] == 1


# -- answer ids ------------------------------------------------------------------


def test_answer_ids_resolve_to_the_question_heading_by_prefix(refs, bolt: Path) -> None:
    (entry,) = show(refs, bolt, "A-Q2")
    assert entry["file"] == "architecture/hla-questions-a.md" and entry["line"] == 7
    assert entry["gloss"] == "What size?"
    path = cite(bolt, "Per A-Q2 we chose.\n")
    link(refs, bolt, "--titles")
    assert "Per [A-Q2] we chose." in path.read_text(encoding="utf-8")
    assert '[A-Q2]: hla-questions-a.md#L7 "What size?"' in path.read_text(encoding="utf-8")


def test_unknown_prefix_and_missing_question_are_unresolved(refs, bolt: Path) -> None:
    cite(bolt, "X-Q1 and A-Q9.\n")
    reasons = [u["reason"] for u in link(refs, bolt, "--dry-run")["unresolved"]]
    assert any("unknown answer prefix" in r for r in reasons)
    assert any("no heading Q9" in r for r in reasons)


def test_tdd_prefixes_resolve_to_the_tdd_files(refs, bolt: Path) -> None:
    write(bolt, "docs/tdd-questions.md", "## Q4 Which queue?\n")
    write(bolt, "docs/tdd-clarifications.md", "## Q1 Which topic?\n")
    found = show(refs, bolt, "T-Q4", "TC-Q1")
    assert [e["gloss"] for e in found] == ["Which queue?", "Which topic?"]


def test_bare_q_is_file_local(refs, bolt: Path) -> None:
    write(bolt, "architecture/hla-questions-b.md", "## Q1 Another one\n")
    many = show(refs, bolt, "Q1")
    assert sorted(e["file"] for e in many) == [
        "architecture/hla-questions-a.md",
        "architecture/hla-questions-b.md",
    ]
    (one,) = show(refs, bolt, "Q1", extra=("--file", "architecture/hla-questions-b.md"))
    assert one["gloss"] == "Another one"


# -- line refs -----------------------------------------------------------------


def outline(bolt: Path, *paths: str) -> None:
    for rel in paths:
        write(bolt, rel, "\n".join(f"source line {n}" for n in range(1, 41)) + "\n")
    data = {"files": [{"path": p} for p in paths]}
    write(bolt, "knowledge/_outline.json", json.dumps(data))


def test_line_refs_resolve_against_the_single_outline_source(refs, bolt: Path) -> None:
    outline(bolt, "inputs/spec.md")
    text = "L5 and L10-L12 and L20-25 and L30\u2013L31.\n"
    path = cite(bolt, text)
    link(refs, bolt)
    assert path.read_text(encoding="utf-8") == text
    link(refs, bolt, "--lines")
    out = path.read_text(encoding="utf-8")
    for token in ("L5", "L10-L12", "L20-25", "L30\u2013L31"):
        assert f"[{token}]" in out
    assert "[L10-L12]: ../inputs/spec.md#L10\n" in out


def test_the_lines_comment_wins_over_the_outline(refs, bolt: Path) -> None:
    outline(bolt, "inputs/one.md", "inputs/two.md")
    path = cite(bolt, "<!-- aidlc-lines: inputs/two.md -->\nSee L7.\n")
    link(refs, bolt, "--lines")
    assert "[L7]: ../inputs/two.md#L7" in path.read_text(encoding="utf-8")
    (entry,) = show(refs, bolt, "L7", extra=("--file", "architecture/cites.md"))
    assert entry["file"] == "inputs/two.md" and entry["text"] == "source line 7"


def test_two_sources_without_a_comment_are_unresolved(refs, bolt: Path) -> None:
    outline(bolt, "inputs/one.md", "inputs/two.md")
    path = cite(bolt, "See L7.\n")
    result = link(refs, bolt, "--lines")
    assert path.read_text(encoding="utf-8") == "See L7.\n"
    assert "several line sources" in result["unresolved"][0]["reason"]


def test_a_line_ref_next_to_a_file_name_cites_another_document(refs, bolt: Path) -> None:
    outline(bolt, "inputs/spec.md")
    path = cite(bolt, "README.md L5 says so.\nAnd L6 too.\n")
    link(refs, bolt, "--lines")
    assert path.read_text(encoding="utf-8").startswith("README.md L5 says so.\nAnd [L6] too.")


# -- link behaviour ------------------------------------------------------------


def test_link_is_idempotent(refs, bolt: Path) -> None:
    path = cite(bolt, "See D10, D11 and A-Q1.\n")
    first = link(refs, bolt)
    once = path.read_bytes()
    second = link(refs, bolt)
    assert path.read_bytes() == once
    assert second["totals"]["files_changed"] == 0 and second["totals"]["links_added"] == 0
    assert first["files"]["architecture/cites.md"]["definitions"] == 3


def test_definitions_are_sorted_by_prefix_then_number(refs, bolt: Path) -> None:
    write(bolt, "architecture/more.md", "## B2 two\n## B10 ten\n")
    path = cite(bolt, "B10 B2 D11 D10\n")
    link(refs, bolt)
    labels = [
        ln.split("]")[0] for ln in path.read_text(encoding="utf-8").splitlines() if "]: " in ln
    ]
    assert labels == ["[B2", "[B10", "[D10", "[D11"]


def test_link_refreshes_line_numbers_and_drops_stale_definitions(refs, bolt: Path) -> None:
    path = cite(bolt, "See D10 and D11.\n")
    link(refs, bolt)
    target = bolt / "architecture" / "hla-decisions.md"
    target.write_text("\n\n" + target.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(path.read_text(encoding="utf-8").replace(" and [D11]", ""), encoding="utf-8")
    link(refs, bolt)
    out = path.read_text(encoding="utf-8")
    assert "[D10]: hla-decisions.md#L5" in out and "D11]:" not in out


def test_remove_restores_the_original_bytes(refs, bolt: Path) -> None:
    original = (
        "# Cites\n\nSee D10, `D11`, and A-Q1 twice: D10.\n\n| Id | X |\n|---|---|\n| D70 | D11 |\n"
    )
    path = cite(bolt, original)
    link(refs, bolt)
    assert path.read_text(encoding="utf-8") != original
    result = link(refs, bolt, "--remove")
    assert path.read_bytes() == original.encode("utf-8")
    assert result["totals"]["definitions"] == 0


def test_dry_run_writes_nothing_and_diff_out_holds_the_change(
    refs, bolt: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    path = cite(bolt, "See D10.\n")
    diff = tmp_path_factory.mktemp("diff") / "out.diff"
    result = link(refs, bolt, "--dry-run", "--diff-out", str(diff))
    assert path.read_text(encoding="utf-8") == "See D10.\n"
    assert result["dry_run"] is True and result["totals"]["links_added"] == 1
    text = diff.read_text(encoding="utf-8")
    assert "+++ b/architecture/cites.md" in text and "+See [D10]." in text
    assert not (bolt / "refs.md").exists()


def test_paths_with_spaces_are_percent_encoded(refs, bolt: Path) -> None:
    write(bolt, "my docs/hla decisions.md", "## D80 Spaced out\n")
    path = write(bolt, "other dir/cites.md", "See D80.\n")
    link(refs, bolt, "--titles")
    assert '[D80]: ../my%20docs/hla%20decisions.md#L1 "Spaced out"' in path.read_text(
        encoding="utf-8"
    )


def test_quotes_in_a_gloss_are_escaped_in_the_title(refs, bolt: Path) -> None:
    write(bolt, "q.md", '## D81 Say "hello" now\n')
    path = cite(bolt, "See D81.\n")
    link(refs, bolt, "--titles")
    assert '"Say \\"hello\\" now"' in path.read_text(encoding="utf-8")


def test_inception_checks_give_the_same_result_before_and_after_link(
    refs, run_script, tmp_path: Path
) -> None:
    inception = tmp_path / "docs" / "inception"
    write(inception, "requirements.md", "## FR-1 Export\nUsers export.\n\n## FR-2 Later\nLater.\n")
    write(
        inception,
        "stories.md",
        "### US-1 Export\nCovers FR-1.\n\n| ID | Criterion |\n|---|---|\n| AC-1.1 | Given data then a file |\n",
    )
    write(inception, "units.md", "## U-1 Exporter\nServes US-1.\n")
    write(
        inception,
        "stories-questions.md",
        "## Q1 Which?\n\nA) One\nB) Two\nX) Other\n\nRecommended: A, per FR-1.\n\nAnswer: A\n",
    )

    def results() -> tuple[str, str, str]:
        trace = run_script(TRACE, ["--bolt", str(tmp_path)])
        lint = run_script(LINT, ["--file", str(inception / "stories-questions.md")])
        return trace.stdout, lint.stdout, f"{trace.returncode}{lint.returncode}"

    before = results()
    done = link(refs, tmp_path)
    assert done["totals"]["links_added"] > 0
    assert results() == before


# -- show -------------------------------------------------------------------------


def test_show_text_is_one_line_per_id_with_citations(refs, bolt: Path) -> None:
    cite(bolt, "D10 here.\n")
    cite(bolt, "D10 and D10 again.\n", name="two.md")
    done = refs("show", "--bolt", str(bolt), "--format", "text", "D10")
    assert done.returncode == 0
    assert done.stdout.splitlines() == [
        "D10 | architecture/hla-decisions.md:3 | Breeding app is the target | cited 3x in 2 files"
    ]


def test_show_text_prints_a_line_ref_with_its_source_text(refs, bolt: Path) -> None:
    outline(bolt, "inputs/spec.md")
    done = refs("show", "--bolt", str(bolt), "--format", "text", "L9")
    assert done.stdout.strip() == "L9 | inputs/spec.md:9 | source line 9"


def test_show_full_adds_the_row_or_the_section(refs, bolt: Path) -> None:
    rows = show(refs, bolt, "D11", extra=("--full",))
    assert rows[0]["full"].startswith("| D11 | Use `Delta`")
    sect = show(refs, bolt, "D10", extra=("--full",))[0]["full"]
    assert sect.startswith("## D10") and "More." in sect and "| D11" in sect
    write(bolt, "long.md", "## D90 Long\n" + "line\n" * 60)
    assert len(show(refs, bolt, "D90", extra=("--full",))[0]["full"].splitlines()) == 40


def test_an_unknown_id_exits_1_with_the_message(refs, bolt: Path) -> None:
    done = refs("show", "--bolt", str(bolt), "--format", "text", "D10", "D99")
    assert done.returncode == 1
    assert done.stdout.splitlines()[-1] == "D99 | not declared in this bolt"
    assert refs("show", "--bolt", str(bolt), "D99").returncode == 1


# -- index ------------------------------------------------------------------------


def test_index_writes_one_table_per_prefix(refs, bolt: Path) -> None:
    cite(bolt, "D10, D10, D11 and A-Q1.\n")
    done = refs("index", "--bolt", str(bolt))
    assert done.returncode == 0 and done.json["ids"] == 3
    text = (bolt / "refs.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("<!--") and "generated" in lines[0]
    assert "## D" in lines and "| Id | What | Declared in | Cited in |" in lines
    assert (
        "| D10 | Breeding app is the target"
        " | [architecture/hla-decisions.md:3](architecture/hla-decisions.md#L3) |"
        " 2 (architecture/cites.md) |"
    ) in lines
    assert "L" not in {ln.split()[1] for ln in lines if ln.startswith("## ")}


def test_index_is_not_scanned_and_honours_out(refs, bolt: Path, tmp_path_factory) -> None:
    refs("index", "--bolt", str(bolt))
    assert show(refs, bolt, "D10")[0]["cited"]["count"] == 0
    out = tmp_path_factory.mktemp("o") / "ids.md"
    assert refs("index", "--bolt", str(bolt), "--out", str(out)).returncode == 0
    assert "(" in out.read_text(encoding="utf-8")


# -- ranking, globs, titles, opt-out, source, noise ---------------------------------


def test_the_id_table_row_beats_a_row_that_only_starts_with_the_id(refs, bolt: Path) -> None:
    write(
        bolt,
        "architecture/hla-decisions.md",
        "| Old | New |\n|---|---|\n| D36 purpose and main line | D52 |\n| C-7 freeze | closed |\n\n"
        "| Id | Decision |\n|---|---|\n| D36 | The real one in the Id table |\n"
        "| C-7 | Mandate catalog has three targets |\n",
    )
    write(bolt, "other.md", "| Name | Text |\n|---|---|\n| D36 | Exact row, other table here |\n")
    d36, c7 = show(refs, bolt, "D36", "C-7")
    assert (d36["file"], d36["line"]) == ("architecture/hla-decisions.md", 8)
    assert c7["gloss"].startswith("Mandate catalog") and c7["line"] == 9
    write(bolt, "other.md", "| Name | Text |\n|---|---|\n| D36 | Exact row, other table here |\n")
    (only,) = show(refs, bolt, "D36")
    assert only["also"]


def test_an_exact_row_of_another_table_beats_a_prefix_row(refs, bolt: Path) -> None:
    write(bolt, "a.md", "| X | Y |\n|---|---|\n| D37 purpose | D52 |\n")
    write(bolt, "b.md", "| Name | Text |\n|---|---|\n| D37 | exact row of a plain table |\n")
    assert show(refs, bolt, "D37")[0]["file"] == "b.md"


def test_answer_prefixes_search_every_file_that_matches_the_glob(refs, bolt: Path) -> None:
    write(bolt, "architecture/hla-clarifications.md", "## Q1 One\n")
    write(bolt, "architecture/hla-clarifications-merge-v06.md", "## Q7 Seven\n")
    one, seven = show(refs, bolt, "CL-Q1", "CL-Q7")
    assert one["gloss"] == "One" and seven["file"].endswith("merge-v06.md")


def test_a_question_in_several_files_prefers_the_plain_name_else_is_unresolved(
    refs, bolt: Path
) -> None:
    write(bolt, "hla-clarifications.md", "## Q3 Plain\n")
    write(bolt, "hla-clarifications-more.md", "## Q3 Suffixed\n## Q4 Only here\n")
    write(bolt, "hla-clarifications-other.md", "## Q4 Also here\n")
    assert show(refs, bolt, "CL-Q3")[0]["gloss"] == "Plain"
    (bad,) = show(refs, bolt, "CL-Q4")
    assert not bad["found"] and "hla-clarifications-more.md" in bad["message"]


def test_titles_are_opt_in_and_switching_mode_cleans_up(refs, bolt: Path) -> None:
    path = cite(bolt, "See D10.\n")
    link(refs, bolt)
    plain = path.read_text(encoding="utf-8")
    assert "[D10]: hla-decisions.md#L3\n" in plain
    link(refs, bolt, "--titles")
    titled = path.read_text(encoding="utf-8")
    assert '[D10]: hla-decisions.md#L3 "Breeding app is the target"' in titled
    assert titled.count("[D10]") == 2
    link(refs, bolt)
    assert path.read_text(encoding="utf-8") == plain
    link(refs, bolt, "--remove")
    assert path.read_text(encoding="utf-8") == "See D10.\n"


def test_an_opted_out_file_is_scanned_but_never_rewritten(refs, bolt: Path) -> None:
    text = "<!-- aidlc-refs: off -->\n## D95 Declared here\nHis D10 is not ours.\n"
    path = cite(bolt, text)
    result = link(refs, bolt)
    assert path.read_bytes() == text.encode()
    assert result["opted_out"] == ["architecture/cites.md"]
    assert show(refs, bolt, "D95")[0]["found"]
    path.write_text(
        "<!-- aidlc-refs: off -->\nSee [D10].\n\n"
        "<!-- aidlc-refs:begin x -->\n[D10]: a.md#L1\n<!-- aidlc-refs:end -->\n",
        encoding="utf-8",
    )
    link(refs, bolt)
    assert path.read_text(encoding="utf-8") == "<!-- aidlc-refs: off -->\nSee D10.\n"


def test_the_root_log_is_not_scanned(refs, bolt: Path) -> None:
    log = write(bolt, "log.md", "2026 | decision-id | D1,D2,D10\n")
    result = link(refs, bolt)
    assert log.read_text(encoding="utf-8") == "2026 | decision-id | D1,D2,D10\n"
    assert "log.md" not in result["files"]


def test_show_source_reads_a_line_ref_among_several_sources(refs, bolt: Path) -> None:
    outline(bolt, "inputs/one.md", "inputs/two.md")
    done = refs("show", "--bolt", str(bolt), "--source", "inputs/two.md", "L4")
    assert done.returncode == 0 and done.json[0]["file"] == "inputs/two.md"
    assert refs("show", "--bolt", str(bolt), "L4").returncode == 1
    bad = refs("show", "--bolt", str(bolt), "--source", "inputs/none.md", "L4")
    assert bad.returncode == 3


def test_unresolved_needs_the_same_prefix_and_hyphenation(refs, bolt: Path) -> None:
    write(bolt, "c.md", "## C-7 Seven\n")
    cite(bolt, "C08 and C-12 and D99.\n")
    ids = [u["id"] for u in link(refs, bolt, "--dry-run")["unresolved"]]
    assert sorted(ids) == ["C-12", "D99"]


# -- bolt config: line source aliases and foreign words ----------------------------


def config(bolt: Path, **data: Any) -> None:
    write(bolt, "aidlc-refs.json", json.dumps(data))


def sources(bolt: Path, *names: str) -> None:
    for rel in names:
        write(bolt, rel, "\n".join(f"{rel} line {n}" for n in range(1, 41)) + "\n")


def test_no_config_leaves_behaviour_unchanged(refs, bolt: Path) -> None:
    sources(bolt, "inputs/spec.md")
    cite(bolt, "spec L5 and ours D10.\n")
    result = link(refs, bolt, "--dry-run")
    assert result["config"] is False
    assert result["unresolved"] == [
        {
            "id": "L5",
            "file": "architecture/cites.md",
            "line": 1,
            "reason": "no line source (knowledge/_outline.json lists no .md file)",
        }
    ]
    assert result["skipped_qualified"] == []


def test_an_alias_before_a_line_ref_names_its_source(refs, bolt: Path) -> None:
    sources(bolt, "inputs/spec.md", "inputs/john/v47.md")
    config(bolt, line_sources={"spec": "inputs/spec.md", "v4.7": "inputs/john/v47.md"})
    path = cite(bolt, "spec L5, (v4.7 L29) and `spec` L7-L9.\n")
    result = link(refs, bolt, "--lines")
    out = path.read_text(encoding="utf-8")
    assert result["config"] is True and result["unresolved"] == []
    assert "[L5]: ../inputs/spec.md#L5\n" in out
    assert "[L29]: ../inputs/john/v47.md#L29\n" in out
    assert "[L7-L9]: ../inputs/spec.md#L7\n" in out


def test_a_wildcard_alias_substitutes_the_slug(refs, bolt: Path) -> None:
    sources(bolt, "knowledge/repos/sirematch1.md")
    config(bolt, line_sources={"card *": "knowledge/repos/*.md"})
    path = cite(bolt, "card sirematch1 L5-L9 and card gone L3.\n")
    result = link(refs, bolt, "--lines")
    assert "[L5-L9]: ../knowledge/repos/sirematch1.md#L5\n" in path.read_text(encoding="utf-8")
    assert [u["reason"] for u in result["unresolved"]] == [
        "source file missing: knowledge/repos/gone.md"
    ]


def test_an_alias_wins_over_the_file_token_and_qualifier_skips(refs, bolt: Path) -> None:
    sources(bolt, "inputs/spec.md")
    config(bolt, line_sources={"spec": "inputs/spec.md", "README": "inputs/spec.md"})
    path = cite(bolt, "See notes.md spec L5 and README L6.\n")
    link(refs, bolt, "--lines")
    out = path.read_text(encoding="utf-8")
    assert "spec [L5] and README [L6]." in out


def test_a_missing_alias_file_is_unresolved_with_the_path(refs, bolt: Path) -> None:
    config(bolt, line_sources={"spec": "inputs/nope.md"})
    cite(bolt, "spec L5.\n")
    (item,) = link(refs, bolt, "--dry-run", "--lines")["unresolved"]
    assert item["reason"] == "source file missing: inputs/nope.md"


def test_a_line_ref_inherits_the_source_through_glue_and_ids(refs, bolt: Path) -> None:
    sources(bolt, "inputs/spec.md")
    write(bolt, "c.md", "## R07 Rule\n")
    config(bolt, line_sources={"spec": "inputs/spec.md"})
    path = cite(bolt, "spec L5-L9 (steps), L12 and spec L20, L21, R07 L22; spec L3 to L4 & L2.\n")
    result = link(refs, bolt, "--lines")
    out = path.read_text(encoding="utf-8")
    for token in ("L5-L9", "L12", "L20", "L21", "L22", "L3", "L4", "L2"):
        assert f"[{token}]: ../inputs/spec.md" in out
    assert result["unresolved"] == []


def test_inheritance_stops_at_a_word_that_is_not_an_id(refs, bolt: Path) -> None:
    sources(bolt, "inputs/spec.md", "inputs/v06.md")
    config(bolt, line_sources={"v0.6": "inputs/v06.md"})
    path = cite(bolt, "v0.6 L12, README L5 and also L6.\n")
    result = link(refs, bolt, "--lines")
    out = path.read_text(encoding="utf-8")
    assert "[L12]: ../inputs/v06.md#L12" in out
    assert "README L5" in out and "[L5]" not in out
    assert "[L6]" not in out and result["unresolved"] == []


def test_the_lines_comment_may_name_an_alias(refs, bolt: Path) -> None:
    sources(bolt, "inputs/one.md", "inputs/two.md")
    outline(bolt, "inputs/one.md", "inputs/two.md")
    config(bolt, line_sources={"two": "inputs/two.md"})
    path = cite(bolt, "<!-- aidlc-lines: two -->\nSee L7 and one L8.\n")
    link(refs, bolt, "--lines")
    assert "[L7]: ../inputs/two.md#L7" in path.read_text(encoding="utf-8")


def test_foreign_words_hide_an_id_and_its_list(refs, bolt: Path) -> None:
    write(bolt, "c.md", "## C-7 Seven\n## C-8 Eight\n## D37 x\n## D38 y\n## D43 z\n")
    config(bolt, foreign_words=["ours", "Ours"])
    text = "Ours D36 to D43, ours C-7 and C-8; ours D37, D38; but D10 is ours.\n"
    path = cite(bolt, text)
    result = link(refs, bolt)
    out = path.read_text(encoding="utf-8")
    assert out.startswith("Ours D36 to D43, ours C-7 and C-8; ours D37, D38; but [D10] is ours.")
    assert {(s["id"], s["qualifier"]) for s in result["skipped_qualified"]} == {
        ("D36", "Ours"),
        ("D43", "Ours"),
        ("C-7", "ours"),
        ("C-8", "ours"),
        ("D37", "ours"),
        ("D38", "ours"),
    }


def test_a_list_does_not_continue_past_other_words(refs, bolt: Path) -> None:
    write(bolt, "c.md", "## D37 x\n## D38 y\n")
    config(bolt, foreign_words=["ours"])
    path = cite(bolt, "ours D37 and then D38.\n")
    link(refs, bolt)
    assert path.read_text(encoding="utf-8").startswith("ours D37 and then [D38].")


@pytest.mark.parametrize(
    "body",
    [
        "{not json",
        "[]",
        '{"line_sources": []}',
        '{"line_sources": {"a": 1}}',
        '{"foreign_words": "ours"}',
        '{"line_sources": {"a * b": "x"}}',
    ],
)
def test_an_invalid_config_exits_4(refs, bolt: Path, body: str) -> None:
    write(bolt, "aidlc-refs.json", body)
    done = refs("link", "--bolt", str(bolt), "--dry-run")
    assert done.returncode == 4 and "aidlc-refs.json" in done.stderr


def test_show_source_takes_an_alias_and_the_config_serves_file_context(refs, bolt: Path) -> None:
    sources(bolt, "inputs/spec.md", "inputs/other.md")
    outline(bolt, "inputs/spec.md", "inputs/other.md")
    config(bolt, line_sources={"spec": "inputs/spec.md", "card *": "inputs/*.md"})
    for alias in ("spec", "card other"):
        done = refs("show", "--bolt", str(bolt), "--source", alias, "L4")
        assert done.returncode == 0 and done.json[0]["file"].startswith("inputs/")
    cite(bolt, "<!-- aidlc-lines: spec -->\n")
    (entry,) = show(refs, bolt, "L4", extra=("--file", "architecture/cites.md"))
    assert entry["file"] == "inputs/spec.md"
    assert refs("show", "--bolt", str(bolt), "--source", "card zzz", "L4").returncode == 3


def test_index_reports_whether_the_config_was_read(refs, bolt: Path) -> None:
    assert refs("index", "--bolt", str(bolt)).json["config"] is False
    config(bolt)
    assert refs("index", "--bolt", str(bolt)).json["config"] is True


# -- one label, two targets; wildcard lists ---------------------------------------------


def two_sources(bolt: Path) -> None:
    sources(bolt, "inputs/readme.md", "inputs/v47.md")
    config(bolt, line_sources={"README": "inputs/readme.md", "v4.7": "inputs/v47.md"})


def test_one_line_number_from_two_sources_gets_a_second_label(refs, bolt: Path) -> None:
    two_sources(bolt)
    path = cite(bolt, "README L8 and (v4.7 L8) and README L8 again, v4.7 L9.\n")
    link(refs, bolt, "--lines")
    out = path.read_text(encoding="utf-8")
    assert out.startswith("README [L8] and (v4.7 [L8][L8@v4.7]) and README [L8] again, v4.7 [L9].")
    assert "[L8]: ../inputs/readme.md#L8\n" in out
    assert "[L8@v4.7]: ../inputs/v47.md#L8\n" in out
    assert "[L9]: ../inputs/v47.md#L9\n" in out


def test_the_two_target_form_is_idempotent_and_removable(refs, bolt: Path) -> None:
    two_sources(bolt)
    original = "README L8 and (v4.7 L8). See D10.\n"
    path = cite(bolt, original)
    link(refs, bolt, "--lines")
    once = path.read_bytes()
    second = link(refs, bolt, "--lines")
    assert path.read_bytes() == once and second["totals"]["files_changed"] == 0
    link(refs, bolt, "--lines", "--titles")
    assert b'[D10]: hla-decisions.md#L3 "' in path.read_bytes()
    assert b"[L8][L8@v4.7]" in path.read_bytes()
    link(refs, bolt, "--lines")
    assert path.read_bytes() == once
    link(refs, bolt)
    assert path.read_text(encoding="utf-8").startswith("README L8 and (v4.7 L8). See [D10].")
    link(refs, bolt, "--lines")
    link(refs, bolt, "--remove")
    assert path.read_bytes() == original.encode()


def test_relinking_after_one_source_is_gone_goes_back_to_the_plain_form(refs, bolt: Path) -> None:
    two_sources(bolt)
    path = cite(bolt, "README L8 and (v4.7 L8).\n")
    link(refs, bolt, "--lines")
    path.write_text(
        path.read_text(encoding="utf-8").replace("README [L8] and ", ""), encoding="utf-8"
    )
    link(refs, bolt, "--lines")
    out = path.read_text(encoding="utf-8")
    assert out.startswith("(v4.7 [L8]).") and "@" not in out
    assert "[L8]: ../inputs/v47.md#L8" in out


def test_without_an_alias_the_suffix_is_the_source_basename(refs, bolt: Path) -> None:
    sources(bolt, "inputs/a.md", "inputs/b.md")
    config(bolt, line_sources={"a": "inputs/a.md", "b": "inputs/b.md"})
    path = cite(bolt, "<!-- aidlc-lines: inputs/a.md -->\nL3 and b L3.\n")
    link(refs, bolt, "--lines")
    assert "L3 and b [L3][L3@b]." not in path.read_text(encoding="utf-8")
    assert "[L3] and b [L3][L3@b]." in path.read_text(encoding="utf-8")


def test_a_wildcard_list_resolves_a_bare_slug_through_the_same_pattern(refs, bolt: Path) -> None:
    sources(bolt, "knowledge/repos/one.md", "knowledge/repos/two-x.md")
    config(bolt, line_sources={"cards *": "knowledge/repos/*.md"})
    path = cite(bolt, "(cards one L5, two-x L10-L11 and one L6)\n")
    result = link(refs, bolt, "--lines")
    out = path.read_text(encoding="utf-8")
    assert "[L10-L11]: ../knowledge/repos/two-x.md#L10" in out
    assert "[L5][L5@one]" not in out and "[L6]: ../knowledge/repos/one.md#L6" in out
    assert result["unresolved"] == []


def test_a_wildcard_list_slug_without_a_file_is_unresolved(refs, bolt: Path) -> None:
    sources(bolt, "knowledge/repos/one.md")
    config(bolt, line_sources={"cards *": "knowledge/repos/*.md"})
    cite(bolt, "(cards one L5, gone L10)\n")
    (item,) = link(refs, bolt, "--lines", "--dry-run")["unresolved"]
    assert item["id"] == "L10"
    assert item["reason"] == "source file missing: knowledge/repos/gone.md"


def test_a_bare_line_ref_after_prose_stays_unresolved_with_the_right_line(refs, bolt: Path) -> None:
    sources(bolt, "inputs/readme.md", "inputs/v47.md")
    config(bolt, line_sources={"v4.7": "inputs/v47.md"})
    outline(bolt, "inputs/readme.md", "inputs/v47.md")
    cite(
        bolt,
        "Intro\n\nBody (v4.7 L5). The body also says both that it stays synchronised with the other side (L5).\n",
    )
    (item,) = link(refs, bolt, "--lines", "--dry-run")["unresolved"]
    assert (item["id"], item["line"]) == ("L5", 3)


def test_a_split_bolts_unit_decisions_are_cited_as_unit_colon_id(refs, bolt: Path) -> None:
    before = show(refs, bolt, "D10", "D11")
    write(bolt, "state.json", json.dumps({"unit_state": "split", "units": [{"id": "u1"}]}))
    write(bolt, "docs/construction/u1/decisions.md", "# Unit\n\n## D10 Unit wording\nSee D10.\n")
    cite(bolt, "The unit chose u1:D10, the Bolt chose D10.\n")
    after = show(refs, bolt, "D10", "D11")  # the Bolt's own ids stay where they were
    assert [(e["file"], e["line"], e["gloss"]) for e in after] == [
        (e["file"], e["line"], e["gloss"]) for e in before
    ]
    assert after[0]["cited"]["files"] == ["architecture/cites.md"]
    entry = show(refs, bolt, "u1:D10")[0]
    assert entry["found"] and entry["file"] == "docs/construction/u1/decisions.md"
    assert entry["cited"]["count"] == 2  # the qualified citation and the bare one in the unit
    assert (
        show(refs, bolt, "D10", extra=("--file", "docs/construction/u1/decisions.md"))[0]["id"]
        == "u1:D10"
    )
    assert refs("index", "--bolt", str(bolt)).json["ids"] == 4
    assert "| u1:D10 |" in (bolt / "refs.md").read_text(encoding="utf-8")
    assert refs("link", "--bolt", str(bolt)).json["duplicates"] == []
