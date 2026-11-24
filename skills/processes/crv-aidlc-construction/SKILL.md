---
name: crv-aidlc-construction
description: >-
  Builds a Bolt's Units in code: per-Unit design stages when they apply, an approved checkbox code plan, code in the target repositories, then Build and Test. Use when someone wants to build or implement a Unit or Slice of a Bolt, write its code plan, or run its build and test. Not for ordinary code edits outside a Bolt, nor for routing, inception, HLA, TDD or repo scans (crv-aidlc, -inception, -hla, -tdd, -reverse-engineering).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: balanced
---

# Construction

One Unit at a time, then Build and Test. Code lives in the target repo; plans and records in the Bolt.

## Execution

**Delegate to a subagent. Do not run this in the main session.**

**Model tier: `balanced`.** Design and code need solid reasoning, not the top tier; Build and Test can use the economy tier. State it in one line, then work. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session, then ONLY the reference of the current stage.

## Start of a Unit

For each design stage, decide from the Unit's `kind` and the stage's run condition whether it runs: `aidlc_state.py decide --bolt <p> --stage <id> --unit <u> --decision execute|skip --reason "..."`. The approver can override. Cite what the HLA, TDD or an accepted ADR fixed (`D<n>`, ADR id); never re-ask it. Code Generation always runs.

| Kind | Design stages that normally run |
| --- | --- |
| `service` | all four |
| `ui` | functional-design, nfr-requirements |
| `spec`, `library` | functional-design when rules are new |
| `packaging` | infrastructure-design |

## Stages

In `docs/construction/<unit>/<stage>/`.

| Stage | Reference | Questions | Main artifact |
| --- | --- | --- | --- |
| functional-design | `functional-design.md` | `<stage>-questions.md` | `functional-spec.md` |
| nfr-requirements | `nfr-requirements.md` | `<stage>-questions.md` | `tech-stack-decisions.md` |
| nfr-design | `nfr-design.md` | `<stage>-questions.md` | `logical-components.md` |
| infrastructure-design | `infrastructure-design.md` | `<stage>-questions.md` | `infrastructure-specification.md` |
| code-generation | `code-generation.md` | none | `code-generation-plan.md` |
| build-and-test | `build-and-test.md` | none | `docs/construction/build-and-test/build-and-test-summary.md` |

## Runs

Start with `aidlc_state.py inputs --bolt <p> --stage <id> --unit <u>`; exit 3: name the missing file, stop.

- **Ask:** write the questions, `lint_questions.py --file <f> --allow-open`, `step --stage <id> --unit <u> --to asked`, stop.
- **Analyse, produce:** `lint_questions.py --file <f>`, then `step ... --to analysed` and `--to produced`.
- **Code generation:** `step --to produced` after the plan, stop for approval; then build.
- **Gate:** `gate --bolt <p> --stage <id> --unit <u> ...`, per Unit and stage.

## When a step fails

- `aidlc_state.py`: 1 refusal (read findings), 2 wrong flag, 3 missing file, 4 malformed `state.json`.
- A design contradicts the HLA or an accepted ADR: ask.
