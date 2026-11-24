---
name: crv-aidlc-operation
description: >-
  Prepares and records the release of a Bolt's change: a release plan, a runbook with named people, a rollback runbook and verification checks, then an environment-by-environment execution log in which people run every step and the agent records the evidence. Use when someone wants to plan or run a release, a data migration, a cut-over, a switch of write master or a retirement for a Bolt, or resume its deploy log. Never runs a deployment itself. Not for routing a Bolt (crv-aidlc), building or testing units (crv-aidlc-construction), the design (crv-aidlc-hla, crv-aidlc-tdd), requirements and units (crv-aidlc-inception), or repo scans (crv-aidlc-reverse-engineering).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: balanced
---

# Operation

Two stages after Build and Test: plan the release, then record it being done. Plans and records live in the Bolt; every change to an environment is made by a person.

## Execution

**Delegate to a subagent. Do not run this in the main session.**

**Model tier: `balanced`.** A release plan and its rollback need solid reasoning; recording evidence in Deployment Execution can use the economy tier. State it in one line, then work. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session, then ONLY the reference of the current stage.

## The agent never changes an environment

- Never run a deployment, migration, switch of write master, retirement or any command that changes an environment. Reason: a mistake there cannot be undone from a chat.
- Every such step is a **HUMAN TASK** for a named person. The agent prepares the runbook, checks preconditions on paper and records the evidence the person gives.
- The agent may run a read-only check itself (a query that only selects, an HTTP GET on a health endpoint), and only for environments the approver allowed in the question file.
- No new CI or CD pipeline is designed. The plan reuses each repository's existing release mechanism, as found in `codekb/<repo>/`.

## Stages

| Stage | Reference | Questions | Main artifact |
| --- | --- | --- | --- |
| deployment-pipeline | `deployment-pipeline.md` | `deployment-pipeline-questions.md` | `release-plan.md` |
| deployment-execution | `deployment-execution.md` | none | `deploy-log.md` |

In `docs/operation/<stage>/`. Both stages are conditional: `decide` first. Deployment Execution runs only when Deployment Pipeline ran.

## Runs

Start with `aidlc_state.py inputs --bolt <p> --stage <id>`; exit 3: name the missing file, stop.

- **Ask:** write the questions, `lint_questions.py --file <f> --allow-open`, `step --stage <id> --to asked`, stop.
- **Analyse, produce:** `lint_questions.py --file <f>`, then `step ... --to analysed` and `--to produced`.
- **Execute:** follow the reference; `step --to produced` after the last environment's verification.
- **Gate:** `gate --bolt <p> --stage <id> ...`.

## When a step fails

- `aidlc_state.py`: 1 refusal (read findings), 2 wrong flag, 3 missing file, 4 malformed `state.json`.
- A runbook step fails or a `Stop if:` condition holds: stop, state the rollback option, record the person's decision.
- The plan contradicts the HLA, the TDD or an accepted ADR: ask.
- The existing release mechanism is not in `codekb/<repo>/`: ask the person; never invent a pipeline.
