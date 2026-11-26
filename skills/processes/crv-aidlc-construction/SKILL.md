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

One Unit at a time, then Build and Test per Slice. Code is in the target repo, records in the Bolt.

## Execution

**Delegate to a subagent, never the main session.**

**Model tier: `balanced`.** Design and code need solid reasoning; Build and Test may use economy. State it; if unavailable, say so and use this model.

Read `references/core-rules.md` once per session, then the current stage's reference only.

## Start or resume a Unit

1. After a break, `aidlc_state.py sync --bolt <p>`, then `aidlc_state.py next --bolt <p> --unit <u>`: stage and waits. Slice not ready: `slice --bolt <p> --ready <slice>`, explain the gaps. Another owner: say so, carry on.
2. Read its `context` before editing.
3. Per design stage, recommend from the Unit's `kind` and run condition: `decide --bolt <p> --stage <id> --unit <u> --decision execute|skip --reason "..."`. Cite what the HLA, TDD or an ADR fixed (`D<n>`) in each design, never re-ask: the citation carries a later change to this Unit. Unit ids: `decision-id --unit <u>` (`<u>:D<n>`).

| Kind | Design stages that normally run |
| --- | --- |
| `service` | all four |
| `ui` | functional-design, nfr-requirements |
| `spec`, `library` | functional-design when rules are new |
| `packaging` | infrastructure-design |

## Stages

Per Unit in `docs/construction/<unit>/<stage>/`: functional-design, nfr-requirements, nfr-design, infrastructure-design, code-generation (`references/<stage>.md` each). Per Slice, `docs/slices/<slice>/build-and-test/`.

## Runs

`aidlc_state.py inputs --bolt <p> --stage <id> --unit <u>` first (exit 3: name the missing file, stop). Build and Test takes `--slice <s>` instead (one Slice: no flag).

- **Ask:** a question file only if a question matters (else `## Assumed` in the artifact, then produce); lint `--allow-open`; `step --stage <id> --unit <u> --to asked`; stop.
- **Analyse, produce:** `step ... --to analysed`, then `produced`.
- **Code:** show the plan; on go, build; write the summary; `step --to produced`.
- **Checkpoint:** `gate --bolt <p> --stage <id> --unit <u> --approve`.

## Verdict

`code-summary.md` (Unit) and `test-results.md` (Slice) hold one line: `Verdict: pass`, `fail - <why>` or `not-run - <why>`. Run the tests first. On a failed run write `Verdict: fail - <why>`, report the command and output, leave the stage open, offer a fix or unrelated work; fix on the engineer's word. Never write `pass` for a failed or unrun run, nor relabel `fail` `not-run`. `not-run` only on the engineer's word, as the gate `--note`; it shows as not verified. A started verification ends in a passing run or is reopened (`gate --request-changes`), never skipped; skipped before it starts, it shows as `verification skipped`.

## When a step fails

`aidlc_state.py` exit 1 is a refusal (report the findings), 2 a wrong flag, 3 a missing file, 4 a malformed `state.json`. A design that contradicts the HLA or an ADR: ask.
