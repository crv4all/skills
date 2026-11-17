#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Check that a stage question file is well formed and fully answered.

A question file is the written record of what the approver decided. A question
with no recommendation, no way out of the listed options, or an answer that is
not one of the options leaves the record unusable, and the cost surfaces three
stages later. Checking the shape here is free; checking it by reading is not.

The format follows the AWS AI-DLC question format (lettered options, a final
"Other", an answer line). The ``Recommended:`` line, with its reason, is a
CRV addition: upstream questions carry no recommendation.

The answer line is ``Answer:`` at the start of a line. The older ``[Answer]:``
is still read, with the same rules, but followed by text it is Markdown
link-reference syntax: a formatter deletes it or rewrites it as ``[Answer](...)``.
That damaged form gets its own finding, so the fix is named instead of every
question failing for no visible reason.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_MALFORMED = 4
EXIT_INTERNAL = 5

EPILOG = """examples:
  python3 lint_questions.py --file docs/inception/user-stories/user-stories-questions.md
  python3 lint_questions.py --file questions.md --allow-open   # right after the Ask step
  python3 lint_questions.py --presets docs/presets.md          # the organisation's presets
  python3 lint_questions.py --file q.md --presets docs/presets.md  # also checks cited preset ids

findings (exit 1): no-questions, no-context, too-few-options, too-many-options,
  no-other-option, no-recommendation, no-recommendation-reason, no-answer-line,
  empty-answer, answer-not-offered, other-without-text, multiple-letters,
  answer-rewritten (a formatter turned the answer line into a link)
presets findings (exit 1): preset-field-missing, preset-field-empty, preset-duplicate-id,
  preset-unknown-stage, preset-bad-date, preset-unknown-id (cited in a question file)
warnings (never change the exit code): vague-answer

exit codes:
  0  clean (warnings allowed)
  1  findings
  2  usage error
  3  the file does not exist or cannot be read
  4  the file is not valid UTF-8 text
  5  internal error
"""

LOG = logging.getLogger("lint_questions")

HEADING = re.compile(r"^##\s+Q(\d+)\b")
ANY_H2 = re.compile(r"^##\s+")
OPTION = re.compile(r"^\s*(?:[-*]\s*)?([A-Z])\)\s*(.*)$")
RECOMMENDED = re.compile(r"^\s*(?:[-*]\s*)?\**Recommended\**\s*:?\**\s*(.*)$", re.IGNORECASE)
ANSWER = re.compile(r"^\s*(?:Answer|\[Answer\])\s*:\s*(.*)$")
REWRITTEN = re.compile(r"^\s*\[Answer\]\(")
LAYER = re.compile(r"^##\s+Layer\b")
PROPOSAL = re.compile(r"^\s*\**Proposal\**\s*:")
LETTERS = re.compile(
    r"^\(?([A-Za-z](?:\s*(?:,|/|&|\+|\band\b)\s*[A-Za-z]\b)*)\)?(?:[\s).:\-\u2013\u2014]+(.*))?$",
    re.DOTALL,
)
REC_LETTER = re.compile(r"^\(?([A-Za-z])\)?\b[\s).:\-\u2013\u2014]*(.*)$", re.DOTALL)
MULTI_HINT = re.compile(r"select all|multiple|multi-select|choose all", re.IGNORECASE)
VAGUE = re.compile(
    r"\b(depends|mix of|standard|typical|as needed|probably|maybe|tbd|not sure|whatever)\b",
    re.IGNORECASE,
)


def finding(code: str, qid: str, line: int, message: str) -> dict[str, Any]:
    return {"code": code, "question": qid, "line": line, "message": message}


Block = tuple[str, int, list[tuple[int, str]], bool]


def split_blocks(lines: list[str]) -> list[Block]:
    """Return ``(id, heading_line, body_lines, proposal)`` for each ``## Q<n>`` block.

    ``proposal`` is true only for the first question after a ``## Layer`` section
    that holds a ``Proposal:`` paragraph: that paragraph is its context.
    """
    blocks: list[Block] = []
    current: Optional[Block] = None
    in_layer = False
    proposal = False
    for number, text in enumerate(lines, start=1):
        match = HEADING.match(text)
        if match:
            current = (f"Q{match.group(1)}", number, [], proposal)
            blocks.append(current)
            in_layer = proposal = False
        elif ANY_H2.match(text):
            current = None
            in_layer = bool(LAYER.match(text))
            proposal = False
        elif current is not None:
            current[2].append((number, text))
        elif in_layer and PROPOSAL.match(text):
            proposal = True
    return blocks


def check_block(
    qid: str,
    heading_line: int,
    body: list[tuple[int, str]],
    allow_open: bool,
    proposal: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    options: dict[str, str] = {}
    context: list[str] = []
    recommended: Optional[tuple[int, str]] = None
    answer: Optional[tuple[int, str]] = None
    rewritten: Optional[int] = None
    seen_structure = False

    for number, text in body:
        if REWRITTEN.match(text):
            rewritten = number
            seen_structure = True
            continue
        option = OPTION.match(text)
        rec = RECOMMENDED.match(text)
        ans = ANSWER.match(text)
        if ans:
            answer = (number, ans.group(1).strip())
            seen_structure = True
        elif rec:
            recommended = (number, rec.group(1).strip())
            seen_structure = True
        elif option:
            options[option.group(1)] = option.group(2).strip()
            seen_structure = True
        elif not seen_structure and text.strip():
            context.append(text.strip())

    if not context and not proposal:
        findings.append(
            finding("no-context", qid, heading_line, "No context lines before the options.")
        )

    real = [letter for letter in options if letter != "X"]
    if len(real) < 2:
        findings.append(
            finding("too-few-options", qid, heading_line, f"{len(real)} option(s); need 2 to 5.")
        )
    if len(real) > 5:
        findings.append(
            finding("too-many-options", qid, heading_line, f"{len(real)} options; need 2 to 5.")
        )
    if "X" not in options:
        findings.append(
            finding("no-other-option", qid, heading_line, "Missing the final `X) Other` option.")
        )

    if recommended is None:
        findings.append(
            finding("no-recommendation", qid, heading_line, "Missing a `Recommended:` line.")
        )
    else:
        rec_line, rec_text = recommended
        parsed = REC_LETTER.match(rec_text)
        if not parsed:
            findings.append(
                finding(
                    "no-recommendation", qid, rec_line, "`Recommended:` names no option letter."
                )
            )
        elif len(parsed.group(2).strip()) < 3:
            findings.append(
                finding(
                    "no-recommendation-reason",
                    qid,
                    rec_line,
                    "`Recommended:` gives a letter but no reason.",
                )
            )

    if rewritten is not None:
        findings.append(
            finding(
                "answer-rewritten",
                qid,
                rewritten,
                "A Markdown formatter rewrote the answer line as a link; "
                "write it as `Answer: <letter>`.",
            )
        )
        if answer is None:
            return findings, warnings
    if answer is None:
        findings.append(finding("no-answer-line", qid, heading_line, "Missing an `Answer:` line."))
        return findings, warnings

    ans_line, ans_text = answer
    if not ans_text:
        if not allow_open:
            findings.append(finding("empty-answer", qid, ans_line, "The answer is empty."))
        return findings, warnings

    parsed_answer = LETTERS.match(ans_text)
    if not parsed_answer:
        findings.append(
            finding("answer-not-offered", qid, ans_line, "The answer does not start with a letter.")
        )
        return findings, warnings

    letters = [c.upper() for c in re.findall(r"[A-Za-z]", parsed_answer.group(1))]
    rest = (parsed_answer.group(2) or "").strip()
    offered = set(options)
    for letter in letters:
        if letter not in offered:
            findings.append(
                finding("answer-not-offered", qid, ans_line, f"Option {letter} is not offered.")
            )
    if "X" in letters and not rest:
        findings.append(
            finding(
                "other-without-text", qid, ans_line, "`X` was chosen but nothing was described."
            )
        )
    multi = MULTI_HINT.search(" ".join(context)) is not None
    if len(set(letters)) > 1 and not multi:
        findings.append(
            finding(
                "multiple-letters",
                qid,
                ans_line,
                "More than one letter chosen for a single-choice question.",
            )
        )
    vague = VAGUE.search(ans_text)
    if vague:
        warnings.append(
            finding(
                "vague-answer", qid, ans_line, f"Vague wording in the answer: '{vague.group(1)}'."
            )
        )
    return findings, warnings


def lint_text(text: str, allow_open: bool = False) -> dict[str, Any]:
    """Lint question-file text; the shared entry point used by ``aidlc_state.py``."""
    lines = text.splitlines()
    blocks = split_blocks(lines)
    findings: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not blocks:
        findings.append(finding("no-questions", "-", 1, "No `## Q<n>` question blocks found."))
    for qid, heading_line, body, proposal in blocks:
        block_findings, block_warnings = check_block(qid, heading_line, body, allow_open, proposal)
        findings.extend(block_findings)
        warnings.extend(block_warnings)
    return {"questions": len(blocks), "findings": findings, "warnings": warnings}


PRESET_HEADING = re.compile(r"^##\s+(P-\d+)\b")
PRESET_FIELDS = ("Applies to", "Answer", "Reason", "Set by")
FENCE = re.compile(r"^\s*(```|~~~)")
DATE_END = re.compile(r",\s*(\d{4}-\d{2}-\d{2})\s*$")
PRESET_CITE = re.compile(r"(?:preset|override of)\s+(P-\d+)", re.IGNORECASE)


def stage_ids() -> Optional[set[str]]:
    """Stage ids of the stages.json next to this skill's scripts; ``None`` when absent."""
    path = Path(__file__).resolve().parent.parent / "assets" / "stages.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(item["id"]) for item in data["stages"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def preset_finding(code: str, pid: str, line: int, message: str) -> dict[str, Any]:
    return {"code": code, "preset": pid, "line": line, "message": message}


def lint_presets(text: str, known_stages: Optional[set[str]] = None) -> dict[str, Any]:
    """Validate a presets file: entries are ``## P-n`` blocks; fenced code is ignored."""
    entries: list[tuple[str, int, dict[str, tuple[int, str]]]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        head = PRESET_HEADING.match(line)
        if head:
            entries.append((head.group(1), number, {}))
        elif ANY_H2.match(line):
            entries.append(("", number, {}))  # another section ends the entry
        elif entries and entries[-1][0]:
            field = re.match(r"^\s*\**(Applies to|Answer|Reason|Set by)\**\s*:\s*(.*)$", line)
            if field and field.group(1) not in entries[-1][2]:
                entries[-1][2][field.group(1)] = (number, field.group(2).strip())
    findings: list[dict[str, Any]] = []
    seen: set[str] = set()
    ids: list[str] = []
    for pid, line, fields in (e for e in entries if e[0]):
        ids.append(pid)
        if pid in seen:
            findings.append(preset_finding("preset-duplicate-id", pid, line, f"{pid} is reused."))
        seen.add(pid)
        for name in PRESET_FIELDS:
            if name not in fields:
                findings.append(
                    preset_finding("preset-field-missing", pid, line, f"Missing `{name}:`.")
                )
            elif not fields[name][1]:
                findings.append(
                    preset_finding(
                        "preset-field-empty", pid, fields[name][0], f"`{name}:` is empty."
                    )
                )
        if fields.get("Applies to", (0, ""))[1]:
            number, value = fields["Applies to"]
            names = [n.strip() for n in value.split(",") if n.strip()]
            if "all" in names and len(names) > 1:
                findings.append(
                    preset_finding("preset-unknown-stage", pid, number, "`all` stands alone.")
                )
            elif known_stages is not None:
                for name in names:
                    if name != "all" and name not in known_stages:
                        findings.append(
                            preset_finding(
                                "preset-unknown-stage", pid, number, f"'{name}' is not a stage id."
                            )
                        )
        if fields.get("Set by", (0, ""))[1]:
            number, value = fields["Set by"]
            match = DATE_END.search(value)
            valid = False
            if match:
                try:
                    dt.date.fromisoformat(match.group(1))
                    valid = True
                except ValueError:
                    valid = False
            if not valid:
                findings.append(
                    preset_finding(
                        "preset-bad-date", pid, number, "`Set by:` must end in `, YYYY-MM-DD`."
                    )
                )
    return {"presets": len(ids), "ids": ids, "findings": findings}


def cited_presets(text: str) -> list[tuple[str, int]]:
    """Preset ids a question file cites as ``preset P-n`` or ``override of P-n``."""
    cites: list[tuple[str, int]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in PRESET_CITE.finditer(line):
            cites.append((match.group(1), number))
    return cites


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lint a stage question file for shape and answers.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", help="Question file to check.")
    parser.add_argument(
        "--presets",
        help="Presets file to validate; with --file, also checks the preset ids it cites.",
    )
    parser.add_argument(
        "--allow-open",
        action="store_true",
        help="Do not report empty answers (use right after the Ask step).",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose diagnostics on stderr.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    if not args.file and not args.presets:
        LOG.error("give --file, --presets or both.")
        return EXIT_USAGE
    result: dict[str, Any] = {"findings": [], "warnings": []}
    question_text: Optional[str] = None
    if args.file:
        path = Path(args.file)
        text = read_text(path)
        if isinstance(text, int):
            return text
        question_text = text
        result = lint_text(text, allow_open=args.allow_open)
        result["file"] = str(path)
        for item in result["findings"]:
            LOG.error(
                "%s:%s %s %s: %s",
                path,
                item["line"],
                item["question"],
                item["code"],
                item["message"],
            )
    if args.presets:
        ppath = Path(args.presets)
        ptext = read_text(ppath)
        if isinstance(ptext, int):
            return ptext
        known = stage_ids()
        report = lint_presets(ptext, known)
        if known is None:
            result["warnings"].append(
                {"code": "stages-unknown", "message": "no stages.json; stage ids not checked."}
            )
        for number_id, number in cited_presets(question_text or ""):
            if number_id not in report["ids"]:
                report["findings"].append(
                    preset_finding(
                        "preset-unknown-id",
                        number_id,
                        number,
                        f"{number_id} is cited in the question file but not in the presets file.",
                    )
                )
        result["presets_file"] = str(ppath)
        result["presets"] = report["presets"]
        result["findings"].extend(report["findings"])
        for item in report["findings"]:
            LOG.error("%s:%s %s: %s", ppath, item["line"], item["code"], item["message"])
    result["ok"] = not result["findings"]
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return EXIT_FINDINGS if result["findings"] else EXIT_OK


def read_text(path: Path) -> Any:
    """The file's text, or the exit code to return after logging why it cannot be read."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        LOG.error("%s: file not found. Write the file first.", path)
        return EXIT_INPUT
    except UnicodeDecodeError as exc:
        LOG.error("%s: not valid UTF-8 (%s). Re-save the file as UTF-8.", path, exc.reason)
        return EXIT_MALFORMED
    except OSError as exc:
        LOG.error("%s: unreadable: %s", path, exc)
        return EXIT_INPUT


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        LOG.exception("internal error")
        sys.exit(EXIT_INTERNAL)
