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
"Other", an ``[Answer]:`` line). The ``Recommended:`` line, with its reason, is a
CRV addition: upstream questions carry no recommendation.
"""

from __future__ import annotations

import argparse
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

findings (exit 1): no-questions, no-context, too-few-options, too-many-options,
  no-other-option, no-recommendation, no-recommendation-reason, no-answer-line,
  empty-answer, answer-not-offered, other-without-text, multiple-letters
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
ANSWER = re.compile(r"^\s*\[Answer\]\s*:\s*(.*)$")
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


def split_blocks(lines: list[str]) -> list[tuple[str, int, list[tuple[int, str]]]]:
    """Return ``(id, heading_line, body_lines)`` for each ``## Q<n>`` block."""
    blocks: list[tuple[str, int, list[tuple[int, str]]]] = []
    current: Optional[tuple[str, int, list[tuple[int, str]]]] = None
    for number, text in enumerate(lines, start=1):
        match = HEADING.match(text)
        if match:
            current = (f"Q{match.group(1)}", number, [])
            blocks.append(current)
        elif ANY_H2.match(text):
            current = None
        elif current is not None:
            current[2].append((number, text))
    return blocks


def check_block(
    qid: str,
    heading_line: int,
    body: list[tuple[int, str]],
    allow_open: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    options: dict[str, str] = {}
    context: list[str] = []
    recommended: Optional[tuple[int, str]] = None
    answer: Optional[tuple[int, str]] = None
    seen_structure = False

    for number, text in body:
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

    if not context:
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

    if answer is None:
        findings.append(finding("no-answer-line", qid, heading_line, "Missing a `[Answer]:` line."))
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
    for qid, heading_line, body in blocks:
        block_findings, block_warnings = check_block(qid, heading_line, body, allow_open)
        findings.extend(block_findings)
        warnings.extend(block_warnings)
    return {"questions": len(blocks), "findings": findings, "warnings": warnings}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lint a stage question file for shape and answers.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", required=True, help="Question file to check.")
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
    path = Path(args.file)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        LOG.error("%s: file not found. Write the question file first.", path)
        return EXIT_INPUT
    except UnicodeDecodeError as exc:
        LOG.error("%s: not valid UTF-8 (%s). Re-save the file as UTF-8.", path, exc.reason)
        return EXIT_MALFORMED
    except OSError as exc:
        LOG.error("%s: unreadable: %s", path, exc)
        return EXIT_INPUT

    result = lint_text(text, allow_open=args.allow_open)
    result["file"] = str(path)
    result["ok"] = not result["findings"]
    for item in result["findings"]:
        LOG.error(
            "%s:%s %s %s: %s", path, item["line"], item["question"], item["code"], item["message"]
        )
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return EXIT_FINDINGS if result["findings"] else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        LOG.exception("internal error")
        sys.exit(EXIT_INTERNAL)
