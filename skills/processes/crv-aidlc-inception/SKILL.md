---
name: crv-aidlc-inception
description: >-
  Runs the AI-DLC Inception stages for a Bolt: requirements that reconcile the accepted HLA, user stories, a domain design, units of work, contracts between units and a Slice delivery plan, each as file-based questions with answers analysed before artifacts are written, stable traceable ids, and a traceability check before the last gate. Use when someone wants requirements, user stories, a domain design or component catalogue, units of work, API or event contracts, or a Slice or delivery plan for a Bolt, or resumes one of those stages. Not for opening, resuming or routing a Bolt (crv-aidlc), the HLA (crv-aidlc-hla), the Technical Design Document (crv-aidlc-tdd), scanning existing code (crv-aidlc-reverse-engineering), building units (crv-aidlc-construction), or filing tickets (crv-create-jira-story, crv-create-jira-epic).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: balanced
---

# Inception

Turns the accepted HLA, document knowledge and code knowledge into requirements, stories, a domain design, units, contracts and a Slice plan. Each stage asks first, analyses the answers, then writes artifacts whose ids can be traced from requirement to unit.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Each stage reads the digests, the HLA and the previous stage's artifacts; that context belongs in an agent that exits when the step is done.

**Model tier: `balanced`.** The questions and the traceable artifacts need sound judgement, but they follow a fixed method and do not need the deepest reasoning. State it, do not ask about it. One line, then start work:

> Running `crv-aidlc-inception` (stage: user-stories, step: ask) in a subagent on the balanced tier.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session. Then read ONLY the reference of the current stage. Scripts live in `scripts/`; run them with `python3`.

## Stages

Find the stage and step with `aidlc_state.py next --bolt <p>`. Paths are relative to the Bolt.

| Stage | Reference | Question file | Main artifact |
| --- | --- | --- | --- |
| `requirements-analysis` | `references/requirements-analysis.md` | `docs/inception/requirements-analysis/requirements-analysis-questions.md` | `requirements.md` |
| `user-stories` | `references/user-stories.md` | `docs/inception/user-stories/user-stories-questions.md` | `stories.md` |
| `domain-design` | `references/domain-design.md` | `docs/inception/domain-design/domain-design-questions.md` | `components.md` |
| `units-generation` | `references/units-generation.md` | `docs/inception/units-generation/units-generation-questions.md` | `unit-of-work.md` |
| `contract-design` | `references/contract-design.md` | `docs/inception/contract-design/contract-design-questions.md` | `contract-summary.md` |
| `delivery-planning` | `references/delivery-planning.md` | `docs/inception/delivery-planning/delivery-planning-questions.md` | `slice-plan.md` |

Artifacts sit beside their question file. Stages can be skipped or conditional; `next` says which run. The scope changes the set: `express` runs requirements, units and delivery planning only (no stories); `bugfix` runs requirements only, at minimal depth.

## Ids

Reserve decision ids with `aidlc_state.py decision-id --bolt <p> --count <n>`. All other ids are numbered by you within the Bolt and never renumbered.

| Kind | Id |
| --- | --- |
| Requirements | `FR-n`, `NFR-n` |
| Stories, criteria | `US-n`, `AC-n.m` (story n) |
| Units | `U-n` |
| Business rules | `BR-n` |
| Decisions | `D<n>`, the Bolt sequence shared with the HLA |

An id is DECLARED when it starts a heading or the first cell of a table row. It is REFERENCED anywhere else. Declare each id once; cite it everywhere it is used.

## The four runs of a stage

Each run ends with one line saying what comes next. Stop after it.

1. **Ask.**
   - `aidlc_state.py status --bolt <p> --format text`, then `aidlc_state.py inputs --bolt <p> --stage <id>`. Exit 3: name the missing file and the stage that produces it, and stop.
   - Read the files `inputs` lists, as the stage reference says. Write the question file: first `## Already answered`, then one question group per category of the reference.
   - `lint_questions.py --file <question file> --allow-open`; fix every finding.
   - `aidlc_state.py step --bolt <p> --stage <id> --to asked`. Tell the user which file to answer.
2. **Analyse.**
   - `lint_questions.py --file <question file>`. Open answers: list them and stop.
   - Analyse per the core rules. Follow-ups go to `<stage>-clarifications.md` beside the question file. Stop until answered.
   - `aidlc_state.py step --bolt <p> --stage <id> --to analysed`.
3. **Produce.**
   - Write the artifacts the reference lists, with their `## Digest` and the sections it requires.
   - Before writing, tell the approver any HLA conflict the answers expose; it is an HLA change, not a stage decision.
   - `aidlc_state.py step --bolt <p> --stage <id> --to produced`.
4. **Gate.**
   - `python3 <crv-aidlc>/scripts/check_traceability.py --bolt <p>` before the gate of the last Inception stage that runs (usually `delivery-planning`). Fix every gap it reports in the artifacts; do not gate while it reports any.
   - End as the core rules say: summary of at most 8 lines, the paths, two choices. On the choice, `aidlc_state.py gate --bolt <p> --stage <id> --approve --by "<name>"` or `--request-changes --note "<what>"`. Never approve yourself.
   - After the `delivery-planning` gate, and only then, read `references/jira-handoff.md` and file the epic and one story per unit.
   - After `units-generation` is approved, load the units: write them to a JSON file and run `aidlc_state.py units --bolt <p> --set <file.json>`. Do the same for the Slices after `delivery-planning`.

## Cross-stage rules

- Read the accepted HLA's `## Digest` and `architecture/hla-decisions.md`. Never re-ask what a decision settles; cite it as `D<n>`. Anything the requirements need that departs from the HLA is raised as an HLA change to the approver.
- Technology choices fixed by the HLA or an accepted ADR are cited, never re-decided.
- This skill chooses no Construction stages. That is decided per unit when its construction starts.
- A document that was not read is named in the question file under `## Already answered`, with the reason.

## When a step fails

- `aidlc_state.py`: exit 1 is a refusal (read the findings and fix them in the files), 2 a wrong flag, 3 a missing file or Bolt, 4 a malformed `state.json` (report it; never edit it by hand).
- `lint_questions.py`: exit 1 lists questions to fix or answers still open.
- `check_traceability.py`: exit 1 lists gaps by id and file; fix the artifacts, run again. Any other exit means the script or an artifact path is broken: report it, do not work around it.
- Two inputs contradict each other, or an answer contradicts the HLA or an accepted ADR: ask, never pick silently.
