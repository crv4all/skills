---
name: crv-aidlc-construction
description: >-
  Builds a Bolt's Units in code: per-Unit design stages when they apply, a checkbox code plan, code in the target repositories with a recorded Verdict, then Build and Test per Slice. Use when someone wants to build, implement or continue a Unit or Slice, write its code plan, run build and test, ask what blocks it, or whether a changed contract affects their work. Not for code edits outside a Bolt, nor routing, inception, HLA, TDD or repo scans (crv-aidlc, -inception, -hla, -tdd, -reverse-engineering).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: balanced
---

# Construction

One Unit at a time, then Build and Test per Slice. Code lives in the target repo, records in the Bolt.

## Execution

**Delegate to a subagent. Do not run this in the main session.**

**Model tier: `balanced`.** Design and code need solid reasoning, not the top tier; Build and Test can use economy. State it, then work; if it or subagents are unavailable, say so and use the session's model.

Read `references/core-rules.md` once per session, then ONLY the current stage's reference.

## Start or resume a Unit

1. `aidlc_state.py next --bolt <p> --unit <u>`: stage and what it waits for. Slice not ready: `slice --bolt <p> --ready <slice>`, explain its gaps. Someone else owns the Unit: say so in one line, carry on.
2. Read its `context` before editing.
3. Per design stage, recommend from the Unit's `kind` and the stage's run condition: `decide --bolt <p> --stage <id> --unit <u> --decision execute|skip --reason "..."`. Cite what the HLA, TDD or an ADR fixed (`D<n>`) in each design, never re-ask: that citation carries a later change of the decision to this Unit. Unit ids: `decision-id --unit <u>` (`<u>:D<n>`).

| Kind | Design stages that normally run |
| --- | --- |
| `service` | all four |
| `ui` | functional-design, nfr-requirements |
| `spec`, `library` | functional-design when rules are new |
| `packaging` | infrastructure-design |

## Stages

Per Unit in `docs/construction/<unit>/<stage>/`: functional-design, nfr-requirements, nfr-design, infrastructure-design, code-generation, each with `references/<stage>.md`. Per Slice, `docs/slices/<slice>/build-and-test/`: build-and-test.

## Runs

`aidlc_state.py inputs --bolt <p> --stage <id> --unit <u>` first (exit 3: name the missing file, stop). Build and Test takes `--slice <s>` instead (one Slice: no flag).

- **Ask:** a question file only if a question matters (else `## Assumed` in the artifact, then produce); lint `--allow-open`; `step --stage <id> --unit <u> --to asked`; stop.
- **Analyse, produce:** `step ... --to analysed`, `--to produced`.
- **Code:** show the plan; on go, build; write the summary; `step --to produced`.
- **Checkpoint:** `gate --bolt <p> --stage <id> --unit <u> --approve`.

## Verdict

`code-summary.md` (Unit) and `test-results.md` (Slice) hold one line: `Verdict: pass`, `Verdict: fail - <why>` or `Verdict: not-run - <why>`. Run the tests first; never write `pass` for a red or unrun run. `fail` is never passed: fix, rerun; never relabel it `not-run`. `not-run` only on the engineer's word, as the gate `--note`; it shows as not verified. A started verification is finished by a passing run or reopened (`gate --request-changes`), never skipped; skipped before it starts it shows as `verification skipped`.

## When a step fails

`aidlc_state.py` exit 1 is a refusal (report the findings), 2 a wrong flag, 3 a missing file, 4 a malformed `state.json`. A design that contradicts the HLA or an ADR: ask.
