"""``aidlc_refs.py``: resolve, link and index the ids of a paddock.

The tests build small paddocks in ``tmp_path``, run the script as a subprocess
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
def paddock(tmp_path: Path) -> Path:
    write(tmp_path, "architecture/hla-decisions.md", DECISIONS)
    write(tmp_path, "architecture/hla-questions-a.md", ANSWERS)
    return tmp_path


@pytest.fixture
def refs(run_script):
    def _refs(*args: str):
        return run_script(REFS, list(args))

    return _refs


def show(refs, paddock: Path, *ids: str, extra: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    done = refs("show", "--paddock", str(paddock), *extra, *ids)
    return json.loads(done.stdout)


def link(refs, paddock: Path, *extra: str) -> dict[str, Any]:
    done = refs("link", "--paddock", str(paddock), *extra)
    assert done.returncode == 0, done.stderr
    return done.json


def cite(paddock: Path, text: str, name: str = "cites.md") -> Path:
    return write(paddock, f"architecture/{name}", text)


# -- declarations and glosses -------------------------------------------------


def test_heading_gloss_drops_markup_and_the_id(refs, paddock: Path) -> None:
    write(paddock, "architecture/h.md", "## FR-2: **Export** a `report`\n")
    (entry,) = show(refs, paddock, "FR-2")
    assert entry["kind"] == "heading" and entry["gloss"] == "Export a report"
    assert entry["line"] == 1 and entry["file"] == "architecture/h.md"


def test_row_gloss_uses_the_decision_column_and_cleans_it(refs, paddock: Path) -> None:
    (entry,) = show(refs, paddock, "D11")
    assert entry["kind"] == "row"
    assert entry["gloss"] == "Use Delta for all storage."


def test_row_gloss_prefers_title_over_decision(refs, paddock: Path) -> None:
    write(
        paddock,
        "t.md",
        "| Id | Decision | Title |\n|---|---|---|\n| D20 | long text here now | The title |\n",
    )
    assert show(refs, paddock, "D20")[0]["gloss"] == "The title"


def test_row_gloss_without_known_column_takes_first_cell_of_three_words(
    refs, paddock: Path
) -> None:
    write(
        paddock, "t.md", "| Id | Owner | Notes |\n|---|---|---|\n| D21 | Ann | Keep the old API |\n"
    )
    assert show(refs, paddock, "D21")[0]["gloss"] == "Keep the old API"


def test_leading_parenthetical_is_dropped_from_a_row_gloss(refs, paddock: Path) -> None:
    write(paddock, "t.md", "| Id | Statement |\n|---|---|\n| D22 | (draft) Ship it on Friday |\n")
    assert show(refs, paddock, "D22")[0]["gloss"] == "Ship it on Friday"


def test_gloss_is_cut_at_a_word_boundary(refs, paddock: Path) -> None:
    words = " ".join(["alpha"] * 30)
    write(paddock, "t.md", f"## D23 {words}\n")
    gloss = show(refs, paddock, "D23")[0]["gloss"]
    assert gloss.endswith("…") and len(gloss) <= 90 and "alph…" not in gloss


def test_the_heading_wins_over_a_row_and_the_other_is_kept_as_also(refs, paddock: Path) -> None:
    write(paddock, "a.md", "| Id | Title |\n|---|---|\n| D30 | From the row |\n")
    write(paddock, "z.md", "## D30 From the heading\n")
    (entry,) = show(refs, paddock, "D30")
    assert entry["kind"] == "heading" and entry["file"] == "z.md"
    assert entry["also"] == [{"file": "a.md", "line": 3, "kind": "row"}]
    assert link(refs, paddock, "--dry-run")["duplicates"][0]["id"] == "D30"


def test_declarations_inside_fences_and_header_rows_are_ignored(refs, paddock: Path) -> None:
    write(
        paddock, "f.md", "```\n## D40 hidden\n```\n\n| D41 | x |\n|---|---|\n| D42 | y one two |\n"
    )
    found = show(refs, paddock, "D40", "D41", "D42")
    assert [e["found"] for e in found] == [False, False, True]


def test_folders_that_are_not_paddock_text_are_not_scanned(refs, paddock: Path) -> None:
    for rel in ("knowledge/k.md", "inputs/i.md", "docs/export/e.md", ".hidden/h.md"):
        write(paddock, rel, "## D50 hidden\n")
    assert show(refs, paddock, "D50")[0]["found"] is False


def test_a_file_that_is_not_utf8_exits_4(refs, paddock: Path) -> None:
    (paddock / "bad.md").write_bytes(b"## D1 \xff\xfe\n")
    assert refs("show", "--paddock", str(paddock), "D1").returncode == 4


def test_a_missing_paddock_exits_3(refs, tmp_path: Path) -> None:
    assert refs("link", "--paddock", str(tmp_path / "nope")).returncode == 3


# -- what is never a reference -------------------------------------------------


def linked(refs, paddock: Path, text: str) -> str:
    path = cite(paddock, text)
    link(refs, paddock)
    return path.read_text(encoding="utf-8")


def test_a_plain_reference_is_linked_and_the_block_is_written(refs, paddock: Path) -> None:
    out = linked(refs, paddock, "# Cites\n\nSee D10 and D11.\n")
    assert "[D10]: hla-decisions.md#L3\n" in out and '"' not in out.split("begin")[1]
    cite(paddock, "# Cites\n\nSee D10 and D11.\n")
    link(refs, paddock, "--titles")
    out = (paddock / "architecture/cites.md").read_text(encoding="utf-8")
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
def test_text_that_is_not_a_reference_is_left_untouched(refs, paddock: Path, text: str) -> None:
    path = cite(paddock, text)
    link(refs, paddock)
    assert path.read_text(encoding="utf-8") == text


def test_qualified_ids_are_reported_not_linked(refs, paddock: Path) -> None:
    path = cite(paddock, "WP D10 and D11.\n")
    result = link(refs, paddock)
    assert "WP D10 and [D11]." in path.read_text(encoding="utf-8")
    assert result["skipped_qualified"] == [
        {"id": "D10", "file": "architecture/cites.md", "line": 1, "qualifier": "WP"}
    ]


def test_a_row_does_not_cite_its_own_id_but_cites_others(refs, paddock: Path) -> None:
    path = cite(paddock, "| Id | Decision |\n|---|---|\n| D60 | Depends on D10 and D60 |\n")
    link(refs, paddock)
    assert "| D60 | Depends on [D10] and D60 |" in path.read_text(encoding="utf-8")


def test_an_undeclared_id_with_a_known_prefix_is_reported(refs, paddock: Path) -> None:
    cite(paddock, "See D99 and SHA256.\n")
    result = link(refs, paddock)
    assert [u["id"] for u in result["unresolved"]] == ["D99"]
    assert result["unresolved"][0]["line"] == 1


# -- answer ids ------------------------------------------------------------------


def test_answer_ids_resolve_to_the_question_heading_by_prefix(refs, paddock: Path) -> None:
    (entry,) = show(refs, paddock, "A-Q2")
    assert entry["file"] == "architecture/hla-questions-a.md" and entry["line"] == 7
    assert entry["gloss"] == "What size?"
    path = cite(paddock, "Per A-Q2 we chose.\n")
    link(refs, paddock, "--titles")
    assert "Per [A-Q2] we chose." in path.read_text(encoding="utf-8")
    assert '[A-Q2]: hla-questions-a.md#L7 "What size?"' in path.read_text(encoding="utf-8")


def test_unknown_prefix_and_missing_question_are_unresolved(refs, paddock: Path) -> None:
    cite(paddock, "X-Q1 and A-Q9.\n")
    reasons = [u["reason"] for u in link(refs, paddock, "--dry-run")["unresolved"]]
    assert any("unknown answer prefix" in r for r in reasons)
    assert any("no heading Q9" in r for r in reasons)


def test_tdd_prefixes_resolve_to_the_tdd_files(refs, paddock: Path) -> None:
    write(paddock, "docs/tdd-questions.md", "## Q4 Which queue?\n")
    write(paddock, "docs/tdd-clarifications.md", "## Q1 Which topic?\n")
    found = show(refs, paddock, "T-Q4", "TC-Q1")
    assert [e["gloss"] for e in found] == ["Which queue?", "Which topic?"]


def test_bare_q_is_file_local(refs, paddock: Path) -> None:
    write(paddock, "architecture/hla-questions-b.md", "## Q1 Another one\n")
    many = show(refs, paddock, "Q1")
    assert sorted(e["file"] for e in many) == [
        "architecture/hla-questions-a.md",
        "architecture/hla-questions-b.md",
    ]
    (one,) = show(refs, paddock, "Q1", extra=("--file", "architecture/hla-questions-b.md"))
    assert one["gloss"] == "Another one"


# -- line refs -----------------------------------------------------------------


def outline(paddock: Path, *paths: str) -> None:
    for rel in paths:
        write(paddock, rel, "\n".join(f"source line {n}" for n in range(1, 41)) + "\n")
    data = {"files": [{"path": p} for p in paths]}
    write(paddock, "knowledge/_outline.json", json.dumps(data))


def test_line_refs_resolve_against_the_single_outline_source(refs, paddock: Path) -> None:
    outline(paddock, "inputs/spec.md")
    text = "L5 and L10-L12 and L20-25 and L30\u2013L31.\n"
    path = cite(paddock, text)
    link(refs, paddock)
    assert path.read_text(encoding="utf-8") == text
    link(refs, paddock, "--lines")
    out = path.read_text(encoding="utf-8")
    for token in ("L5", "L10-L12", "L20-25", "L30\u2013L31"):
        assert f"[{token}]" in out
    assert "[L10-L12]: ../inputs/spec.md#L10\n" in out


def test_the_lines_comment_wins_over_the_outline(refs, paddock: Path) -> None:
    outline(paddock, "inputs/one.md", "inputs/two.md")
    path = cite(paddock, "<!-- aidlc-lines: inputs/two.md -->\nSee L7.\n")
    link(refs, paddock, "--lines")
    assert "[L7]: ../inputs/two.md#L7" in path.read_text(encoding="utf-8")
    (entry,) = show(refs, paddock, "L7", extra=("--file", "architecture/cites.md"))
    assert entry["file"] == "inputs/two.md" and entry["text"] == "source line 7"


def test_two_sources_without_a_comment_are_unresolved(refs, paddock: Path) -> None:
    outline(paddock, "inputs/one.md", "inputs/two.md")
    path = cite(paddock, "See L7.\n")
    result = link(refs, paddock, "--lines")
    assert path.read_text(encoding="utf-8") == "See L7.\n"
    assert "several line sources" in result["unresolved"][0]["reason"]


def test_a_line_ref_next_to_a_file_name_cites_another_document(refs, paddock: Path) -> None:
    outline(paddock, "inputs/spec.md")
    path = cite(paddock, "README.md L5 says so.\nAnd L6 too.\n")
    link(refs, paddock, "--lines")
    assert path.read_text(encoding="utf-8").startswith("README.md L5 says so.\nAnd [L6] too.")


# -- link behaviour ------------------------------------------------------------


def test_link_is_idempotent(refs, paddock: Path) -> None:
    path = cite(paddock, "See D10, D11 and A-Q1.\n")
    first = link(refs, paddock)
    once = path.read_bytes()
    second = link(refs, paddock)
    assert path.read_bytes() == once
    assert second["totals"]["files_changed"] == 0 and second["totals"]["links_added"] == 0
    assert first["files"]["architecture/cites.md"]["definitions"] == 3


def test_definitions_are_sorted_by_prefix_then_number(refs, paddock: Path) -> None:
    write(paddock, "architecture/more.md", "## B2 two\n## B10 ten\n")
    path = cite(paddock, "B10 B2 D11 D10\n")
    link(refs, paddock)
    labels = [
        ln.split("]")[0] for ln in path.read_text(encoding="utf-8").splitlines() if "]: " in ln
    ]
    assert labels == ["[B2", "[B10", "[D10", "[D11"]


def test_link_refreshes_line_numbers_and_drops_stale_definitions(refs, paddock: Path) -> None:
    path = cite(paddock, "See D10 and D11.\n")
    link(refs, paddock)
    target = paddock / "architecture" / "hla-decisions.md"
    target.write_text("\n\n" + target.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(path.read_text(encoding="utf-8").replace(" and [D11]", ""), encoding="utf-8")
    link(refs, paddock)
    out = path.read_text(encoding="utf-8")
    assert "[D10]: hla-decisions.md#L5" in out and "D11]:" not in out


def test_remove_restores_the_original_bytes(refs, paddock: Path) -> None:
    original = (
        "# Cites\n\nSee D10, `D11`, and A-Q1 twice: D10.\n\n| Id | X |\n|---|---|\n| D70 | D11 |\n"
    )
    path = cite(paddock, original)
    link(refs, paddock)
    assert path.read_text(encoding="utf-8") != original
    result = link(refs, paddock, "--remove")
    assert path.read_bytes() == original.encode("utf-8")
    assert result["totals"]["definitions"] == 0


def test_dry_run_writes_nothing_and_diff_out_holds_the_change(
    refs, paddock: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    path = cite(paddock, "See D10.\n")
    diff = tmp_path_factory.mktemp("diff") / "out.diff"
    result = link(refs, paddock, "--dry-run", "--diff-out", str(diff))
    assert path.read_text(encoding="utf-8") == "See D10.\n"
    assert result["dry_run"] is True and result["totals"]["links_added"] == 1
    text = diff.read_text(encoding="utf-8")
    assert "+++ b/architecture/cites.md" in text and "+See [D10]." in text
    assert not (paddock / "refs.md").exists()


def test_paths_with_spaces_are_percent_encoded(refs, paddock: Path) -> None:
    write(paddock, "my docs/hla decisions.md", "## D80 Spaced out\n")
    path = write(paddock, "other dir/cites.md", "See D80.\n")
    link(refs, paddock, "--titles")
    assert '[D80]: ../my%20docs/hla%20decisions.md#L1 "Spaced out"' in path.read_text(
        encoding="utf-8"
    )


def test_quotes_in_a_gloss_are_escaped_in_the_title(refs, paddock: Path) -> None:
    write(paddock, "q.md", '## D81 Say "hello" now\n')
    path = cite(paddock, "See D81.\n")
    link(refs, paddock, "--titles")
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
        trace = run_script(TRACE, ["--paddock", str(tmp_path)])
        lint = run_script(LINT, ["--file", str(inception / "stories-questions.md")])
        return trace.stdout, lint.stdout, f"{trace.returncode}{lint.returncode}"

    before = results()
    done = link(refs, tmp_path)
    assert done["totals"]["links_added"] > 0
    assert results() == before


# -- show -------------------------------------------------------------------------


def test_show_text_is_one_line_per_id_with_citations(refs, paddock: Path) -> None:
    cite(paddock, "D10 here.\n")
    cite(paddock, "D10 and D10 again.\n", name="two.md")
    done = refs("show", "--paddock", str(paddock), "--format", "text", "D10")
    assert done.returncode == 0
    assert done.stdout.splitlines() == [
        "D10 | architecture/hla-decisions.md:3 | Breeding app is the target | cited 3x in 2 files"
    ]


def test_show_text_prints_a_line_ref_with_its_source_text(refs, paddock: Path) -> None:
    outline(paddock, "inputs/spec.md")
    done = refs("show", "--paddock", str(paddock), "--format", "text", "L9")
    assert done.stdout.strip() == "L9 | inputs/spec.md:9 | source line 9"


def test_show_full_adds_the_row_or_the_section(refs, paddock: Path) -> None:
    rows = show(refs, paddock, "D11", extra=("--full",))
    assert rows[0]["full"].startswith("| D11 | Use `Delta`")
    sect = show(refs, paddock, "D10", extra=("--full",))[0]["full"]
    assert sect.startswith("## D10") and "More." in sect and "| D11" in sect
    write(paddock, "long.md", "## D90 Long\n" + "line\n" * 60)
    assert len(show(refs, paddock, "D90", extra=("--full",))[0]["full"].splitlines()) == 40


def test_an_unknown_id_exits_1_with_the_message(refs, paddock: Path) -> None:
    done = refs("show", "--paddock", str(paddock), "--format", "text", "D10", "D99")
    assert done.returncode == 1
    assert done.stdout.splitlines()[-1] == "D99 | not declared in this paddock"
    assert refs("show", "--paddock", str(paddock), "D99").returncode == 1


# -- index ------------------------------------------------------------------------


def test_index_writes_one_table_per_prefix(refs, paddock: Path) -> None:
    cite(paddock, "D10, D10, D11 and A-Q1.\n")
    done = refs("index", "--paddock", str(paddock))
    assert done.returncode == 0 and done.json["ids"] == 3
    text = (paddock / "refs.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0].startswith("<!--") and "generated" in lines[0]
    assert "## D" in lines and "| Id | What | Declared in | Cited in |" in lines
    assert (
        "| D10 | Breeding app is the target"
        " | [architecture/hla-decisions.md:3](architecture/hla-decisions.md#L3) |"
        " 2 (architecture/cites.md) |"
    ) in lines
    assert "L" not in {ln.split()[1] for ln in lines if ln.startswith("## ")}


def test_index_is_not_scanned_and_honours_out(refs, paddock: Path, tmp_path_factory) -> None:
    refs("index", "--paddock", str(paddock))
    assert show(refs, paddock, "D10")[0]["cited"]["count"] == 0
    out = tmp_path_factory.mktemp("o") / "ids.md"
    assert refs("index", "--paddock", str(paddock), "--out", str(out)).returncode == 0
    assert "(" in out.read_text(encoding="utf-8")


# -- ranking, globs, titles, opt-out, source, noise ---------------------------------


def test_the_id_table_row_beats_a_row_that_only_starts_with_the_id(refs, paddock: Path) -> None:
    write(
        paddock,
        "architecture/hla-decisions.md",
        "| Old | New |\n|---|---|\n| D36 purpose and main line | D52 |\n| C-7 freeze | closed |\n\n"
        "| Id | Decision |\n|---|---|\n| D36 | The real one in the Id table |\n"
        "| C-7 | Mandate catalog has three targets |\n",
    )
    write(
        paddock, "other.md", "| Name | Text |\n|---|---|\n| D36 | Exact row, other table here |\n"
    )
    d36, c7 = show(refs, paddock, "D36", "C-7")
    assert (d36["file"], d36["line"]) == ("architecture/hla-decisions.md", 8)
    assert c7["gloss"].startswith("Mandate catalog") and c7["line"] == 9
    write(
        paddock, "other.md", "| Name | Text |\n|---|---|\n| D36 | Exact row, other table here |\n"
    )
    (only,) = show(refs, paddock, "D36")
    assert only["also"]


def test_an_exact_row_of_another_table_beats_a_prefix_row(refs, paddock: Path) -> None:
    write(paddock, "a.md", "| X | Y |\n|---|---|\n| D37 purpose | D52 |\n")
    write(paddock, "b.md", "| Name | Text |\n|---|---|\n| D37 | exact row of a plain table |\n")
    assert show(refs, paddock, "D37")[0]["file"] == "b.md"


def test_answer_prefixes_search_every_file_that_matches_the_glob(refs, paddock: Path) -> None:
    write(paddock, "architecture/hla-clarifications.md", "## Q1 One\n")
    write(paddock, "architecture/hla-clarifications-merge-v06.md", "## Q7 Seven\n")
    one, seven = show(refs, paddock, "CL-Q1", "CL-Q7")
    assert one["gloss"] == "One" and seven["file"].endswith("merge-v06.md")


def test_a_question_in_several_files_prefers_the_plain_name_else_is_unresolved(
    refs, paddock: Path
) -> None:
    write(paddock, "hla-clarifications.md", "## Q3 Plain\n")
    write(paddock, "hla-clarifications-more.md", "## Q3 Suffixed\n## Q4 Only here\n")
    write(paddock, "hla-clarifications-other.md", "## Q4 Also here\n")
    assert show(refs, paddock, "CL-Q3")[0]["gloss"] == "Plain"
    (bad,) = show(refs, paddock, "CL-Q4")
    assert not bad["found"] and "hla-clarifications-more.md" in bad["message"]


def test_titles_are_opt_in_and_switching_mode_cleans_up(refs, paddock: Path) -> None:
    path = cite(paddock, "See D10.\n")
    link(refs, paddock)
    plain = path.read_text(encoding="utf-8")
    assert "[D10]: hla-decisions.md#L3\n" in plain
    link(refs, paddock, "--titles")
    titled = path.read_text(encoding="utf-8")
    assert '[D10]: hla-decisions.md#L3 "Breeding app is the target"' in titled
    assert titled.count("[D10]") == 2
    link(refs, paddock)
    assert path.read_text(encoding="utf-8") == plain
    link(refs, paddock, "--remove")
    assert path.read_text(encoding="utf-8") == "See D10.\n"


def test_an_opted_out_file_is_scanned_but_never_rewritten(refs, paddock: Path) -> None:
    text = "<!-- aidlc-refs: off -->\n## D95 Declared here\nHis D10 is not ours.\n"
    path = cite(paddock, text)
    result = link(refs, paddock)
    assert path.read_bytes() == text.encode()
    assert result["opted_out"] == ["architecture/cites.md"]
    assert show(refs, paddock, "D95")[0]["found"]
    path.write_text(
        "<!-- aidlc-refs: off -->\nSee [D10].\n\n"
        "<!-- aidlc-refs:begin x -->\n[D10]: a.md#L1\n<!-- aidlc-refs:end -->\n",
        encoding="utf-8",
    )
    link(refs, paddock)
    assert path.read_text(encoding="utf-8") == "<!-- aidlc-refs: off -->\nSee D10.\n"


def test_the_root_log_is_not_scanned(refs, paddock: Path) -> None:
    log = write(paddock, "log.md", "2026 | decision-id | D1,D2,D10\n")
    result = link(refs, paddock)
    assert log.read_text(encoding="utf-8") == "2026 | decision-id | D1,D2,D10\n"
    assert "log.md" not in result["files"]


def test_show_source_reads_a_line_ref_among_several_sources(refs, paddock: Path) -> None:
    outline(paddock, "inputs/one.md", "inputs/two.md")
    done = refs("show", "--paddock", str(paddock), "--source", "inputs/two.md", "L4")
    assert done.returncode == 0 and done.json[0]["file"] == "inputs/two.md"
    assert refs("show", "--paddock", str(paddock), "L4").returncode == 1
    bad = refs("show", "--paddock", str(paddock), "--source", "inputs/none.md", "L4")
    assert bad.returncode == 3


def test_unresolved_needs_the_same_prefix_and_hyphenation(refs, paddock: Path) -> None:
    write(paddock, "c.md", "## C-7 Seven\n")
    cite(paddock, "C08 and C-12 and D99.\n")
    ids = [u["id"] for u in link(refs, paddock, "--dry-run")["unresolved"]]
    assert sorted(ids) == ["C-12", "D99"]


# -- paddock config: line source aliases and foreign words ----------------------------


def config(paddock: Path, **data: Any) -> None:
    write(paddock, "aidlc-refs.json", json.dumps(data))


def sources(paddock: Path, *names: str) -> None:
    for rel in names:
        write(paddock, rel, "\n".join(f"{rel} line {n}" for n in range(1, 41)) + "\n")


def test_no_config_leaves_behaviour_unchanged(refs, paddock: Path) -> None:
    sources(paddock, "inputs/spec.md")
    cite(paddock, "spec L5 and ours D10.\n")
    result = link(refs, paddock, "--dry-run")
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


def test_an_alias_before_a_line_ref_names_its_source(refs, paddock: Path) -> None:
    sources(paddock, "inputs/spec.md", "inputs/john/v47.md")
    config(paddock, line_sources={"spec": "inputs/spec.md", "v4.7": "inputs/john/v47.md"})
    path = cite(paddock, "spec L5, (v4.7 L29) and `spec` L7-L9.\n")
    result = link(refs, paddock, "--lines")
    out = path.read_text(encoding="utf-8")
    assert result["config"] is True and result["unresolved"] == []
    assert "[L5]: ../inputs/spec.md#L5\n" in out
    assert "[L29]: ../inputs/john/v47.md#L29\n" in out
    assert "[L7-L9]: ../inputs/spec.md#L7\n" in out


def test_a_wildcard_alias_substitutes_the_slug(refs, paddock: Path) -> None:
    sources(paddock, "knowledge/repos/sirematch1.md")
    config(paddock, line_sources={"card *": "knowledge/repos/*.md"})
    path = cite(paddock, "card sirematch1 L5-L9 and card gone L3.\n")
    result = link(refs, paddock, "--lines")
    assert "[L5-L9]: ../knowledge/repos/sirematch1.md#L5\n" in path.read_text(encoding="utf-8")
    assert [u["reason"] for u in result["unresolved"]] == [
        "source file missing: knowledge/repos/gone.md"
    ]


def test_an_alias_wins_over_the_file_token_and_qualifier_skips(refs, paddock: Path) -> None:
    sources(paddock, "inputs/spec.md")
    config(paddock, line_sources={"spec": "inputs/spec.md", "README": "inputs/spec.md"})
    path = cite(paddock, "See notes.md spec L5 and README L6.\n")
    link(refs, paddock, "--lines")
    out = path.read_text(encoding="utf-8")
    assert "spec [L5] and README [L6]." in out


def test_a_missing_alias_file_is_unresolved_with_the_path(refs, paddock: Path) -> None:
    config(paddock, line_sources={"spec": "inputs/nope.md"})
    cite(paddock, "spec L5.\n")
    (item,) = link(refs, paddock, "--dry-run", "--lines")["unresolved"]
    assert item["reason"] == "source file missing: inputs/nope.md"


def test_a_line_ref_inherits_the_source_through_glue_and_ids(refs, paddock: Path) -> None:
    sources(paddock, "inputs/spec.md")
    write(paddock, "c.md", "## R07 Rule\n")
    config(paddock, line_sources={"spec": "inputs/spec.md"})
    path = cite(
        paddock, "spec L5-L9 (steps), L12 and spec L20, L21, R07 L22; spec L3 to L4 & L2.\n"
    )
    result = link(refs, paddock, "--lines")
    out = path.read_text(encoding="utf-8")
    for token in ("L5-L9", "L12", "L20", "L21", "L22", "L3", "L4", "L2"):
        assert f"[{token}]: ../inputs/spec.md" in out
    assert result["unresolved"] == []


def test_inheritance_stops_at_a_word_that_is_not_an_id(refs, paddock: Path) -> None:
    sources(paddock, "inputs/spec.md", "inputs/v06.md")
    config(paddock, line_sources={"v0.6": "inputs/v06.md"})
    path = cite(paddock, "v0.6 L12, README L5 and also L6.\n")
    result = link(refs, paddock, "--lines")
    out = path.read_text(encoding="utf-8")
    assert "[L12]: ../inputs/v06.md#L12" in out
    assert "README L5" in out and "[L5]" not in out
    assert "[L6]" not in out and result["unresolved"] == []


def test_the_lines_comment_may_name_an_alias(refs, paddock: Path) -> None:
    sources(paddock, "inputs/one.md", "inputs/two.md")
    outline(paddock, "inputs/one.md", "inputs/two.md")
    config(paddock, line_sources={"two": "inputs/two.md"})
    path = cite(paddock, "<!-- aidlc-lines: two -->\nSee L7 and one L8.\n")
    link(refs, paddock, "--lines")
    assert "[L7]: ../inputs/two.md#L7" in path.read_text(encoding="utf-8")


def test_foreign_words_hide_an_id_and_its_list(refs, paddock: Path) -> None:
    write(paddock, "c.md", "## C-7 Seven\n## C-8 Eight\n## D37 x\n## D38 y\n## D43 z\n")
    config(paddock, foreign_words=["ours", "Ours"])
    text = "Ours D36 to D43, ours C-7 and C-8; ours D37, D38; but D10 is ours.\n"
    path = cite(paddock, text)
    result = link(refs, paddock)
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


def test_a_list_does_not_continue_past_other_words(refs, paddock: Path) -> None:
    write(paddock, "c.md", "## D37 x\n## D38 y\n")
    config(paddock, foreign_words=["ours"])
    path = cite(paddock, "ours D37 and then D38.\n")
    link(refs, paddock)
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
def test_an_invalid_config_exits_4(refs, paddock: Path, body: str) -> None:
    write(paddock, "aidlc-refs.json", body)
    done = refs("link", "--paddock", str(paddock), "--dry-run")
    assert done.returncode == 4 and "aidlc-refs.json" in done.stderr


def test_show_source_takes_an_alias_and_the_config_serves_file_context(refs, paddock: Path) -> None:
    sources(paddock, "inputs/spec.md", "inputs/other.md")
    outline(paddock, "inputs/spec.md", "inputs/other.md")
    config(paddock, line_sources={"spec": "inputs/spec.md", "card *": "inputs/*.md"})
    for alias in ("spec", "card other"):
        done = refs("show", "--paddock", str(paddock), "--source", alias, "L4")
        assert done.returncode == 0 and done.json[0]["file"].startswith("inputs/")
    cite(paddock, "<!-- aidlc-lines: spec -->\n")
    (entry,) = show(refs, paddock, "L4", extra=("--file", "architecture/cites.md"))
    assert entry["file"] == "inputs/spec.md"
    assert refs("show", "--paddock", str(paddock), "--source", "card zzz", "L4").returncode == 3


def test_index_reports_whether_the_config_was_read(refs, paddock: Path) -> None:
    assert refs("index", "--paddock", str(paddock)).json["config"] is False
    config(paddock)
    assert refs("index", "--paddock", str(paddock)).json["config"] is True


# -- one label, two targets; wildcard lists ---------------------------------------------


def two_sources(paddock: Path) -> None:
    sources(paddock, "inputs/readme.md", "inputs/v47.md")
    config(paddock, line_sources={"README": "inputs/readme.md", "v4.7": "inputs/v47.md"})


def test_one_line_number_from_two_sources_gets_a_second_label(refs, paddock: Path) -> None:
    two_sources(paddock)
    path = cite(paddock, "README L8 and (v4.7 L8) and README L8 again, v4.7 L9.\n")
    link(refs, paddock, "--lines")
    out = path.read_text(encoding="utf-8")
    assert out.startswith("README [L8] and (v4.7 [L8][L8@v4.7]) and README [L8] again, v4.7 [L9].")
    assert "[L8]: ../inputs/readme.md#L8\n" in out
    assert "[L8@v4.7]: ../inputs/v47.md#L8\n" in out
    assert "[L9]: ../inputs/v47.md#L9\n" in out


def test_the_two_target_form_is_idempotent_and_removable(refs, paddock: Path) -> None:
    two_sources(paddock)
    original = "README L8 and (v4.7 L8). See D10.\n"
    path = cite(paddock, original)
    link(refs, paddock, "--lines")
    once = path.read_bytes()
    second = link(refs, paddock, "--lines")
    assert path.read_bytes() == once and second["totals"]["files_changed"] == 0
    link(refs, paddock, "--lines", "--titles")
    assert b'[D10]: hla-decisions.md#L3 "' in path.read_bytes()
    assert b"[L8][L8@v4.7]" in path.read_bytes()
    link(refs, paddock, "--lines")
    assert path.read_bytes() == once
    link(refs, paddock)
    assert path.read_text(encoding="utf-8").startswith("README L8 and (v4.7 L8). See [D10].")
    link(refs, paddock, "--lines")
    link(refs, paddock, "--remove")
    assert path.read_bytes() == original.encode()


def test_relinking_after_one_source_is_gone_goes_back_to_the_plain_form(
    refs, paddock: Path
) -> None:
    two_sources(paddock)
    path = cite(paddock, "README L8 and (v4.7 L8).\n")
    link(refs, paddock, "--lines")
    path.write_text(
        path.read_text(encoding="utf-8").replace("README [L8] and ", ""), encoding="utf-8"
    )
    link(refs, paddock, "--lines")
    out = path.read_text(encoding="utf-8")
    assert out.startswith("(v4.7 [L8]).") and "@" not in out
    assert "[L8]: ../inputs/v47.md#L8" in out


def test_without_an_alias_the_suffix_is_the_source_basename(refs, paddock: Path) -> None:
    sources(paddock, "inputs/a.md", "inputs/b.md")
    config(paddock, line_sources={"a": "inputs/a.md", "b": "inputs/b.md"})
    path = cite(paddock, "<!-- aidlc-lines: inputs/a.md -->\nL3 and b L3.\n")
    link(refs, paddock, "--lines")
    assert "L3 and b [L3][L3@b]." not in path.read_text(encoding="utf-8")
    assert "[L3] and b [L3][L3@b]." in path.read_text(encoding="utf-8")


def test_a_wildcard_list_resolves_a_bare_slug_through_the_same_pattern(refs, paddock: Path) -> None:
    sources(paddock, "knowledge/repos/one.md", "knowledge/repos/two-x.md")
    config(paddock, line_sources={"cards *": "knowledge/repos/*.md"})
    path = cite(paddock, "(cards one L5, two-x L10-L11 and one L6)\n")
    result = link(refs, paddock, "--lines")
    out = path.read_text(encoding="utf-8")
    assert "[L10-L11]: ../knowledge/repos/two-x.md#L10" in out
    assert "[L5][L5@one]" not in out and "[L6]: ../knowledge/repos/one.md#L6" in out
    assert result["unresolved"] == []


def test_a_wildcard_list_slug_without_a_file_is_unresolved(refs, paddock: Path) -> None:
    sources(paddock, "knowledge/repos/one.md")
    config(paddock, line_sources={"cards *": "knowledge/repos/*.md"})
    cite(paddock, "(cards one L5, gone L10)\n")
    (item,) = link(refs, paddock, "--lines", "--dry-run")["unresolved"]
    assert item["id"] == "L10"
    assert item["reason"] == "source file missing: knowledge/repos/gone.md"


def test_a_bare_line_ref_after_prose_stays_unresolved_with_the_right_line(
    refs, paddock: Path
) -> None:
    sources(paddock, "inputs/readme.md", "inputs/v47.md")
    config(paddock, line_sources={"v4.7": "inputs/v47.md"})
    outline(paddock, "inputs/readme.md", "inputs/v47.md")
    cite(
        paddock,
        "Intro\n\nBody (v4.7 L5). The body also says both that it stays synchronised with the other side (L5).\n",
    )
    (item,) = link(refs, paddock, "--lines", "--dry-run")["unresolved"]
    assert (item["id"], item["line"]) == ("L5", 3)
