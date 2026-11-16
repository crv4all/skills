---
name: crv-aidlc-hla
description: >-
  Produces the High-Level Architecture (HLA) for a paddock before Inception: three file-based question rounds over twelve design layers, opinionated proposals that cite the ADRs they follow, a decision record with paddock-wide ids, an hla.md with a review header that a validator checks, and sign-off recorded in the file. Use when someone wants to write, draft, refine or sign off a high-level architecture, solution architecture or architecture document for a paddock or from a set of input documents, or asks which ADRs bind a design. Not for the Technical Design Document that follows an accepted HLA (crv-aidlc-tdd), not for opening, resuming or routing a paddock (crv-aidlc), and not for requirements, stories or units (crv-aidlc-inception).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: frontier
---

# High-level architecture

Runs the HLA as three question rounds in files, then writes `hla.md` from the template. Proposals come first, questions only for what the inputs and accepted ADRs leave open, and every decision lands in a record with an id.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Each step reads the knowledge digest, the ADR index and the round files; that context belongs in an agent that exits when the step is done.

**Model tier: `frontier`.** The HLA fixes decisions every later stage inherits, so reasoning quality dominates cost. State it, do not ask about it. One line, then start work:

> Running `crv-aidlc-hla` (step: round B) in a subagent on the frontier tier.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session. Then read only the files the step table names. Scripts live in `scripts/`; run them with `python3`.

## What this produces

In `<paddock>/architecture/`:

- `hla-questions-a.md`, `-b.md`, `-c.md`: one per round, every answer filled.
- `hla-clarifications.md`: follow-ups, only when answers needed them.
- `hla-decisions.md`: a `## Digest`, then one row per decision: `| Id | Layer | Decision | Reason | Source | Flag |`.
- `hla.md`: the template's sections in order, a valid header, `validate_doc.py` exit 0, and `status: in-review` until a person signs.

## When not to use this

- The Technical Design Document after an accepted HLA: `crv-aidlc-tdd`.
- Opening, resuming or routing a paddock: `crv-aidlc`.
- Requirements, stories, domain design or units: `crv-aidlc-inception`. It reads the accepted HLA.
- Writing an ADR: that belongs in the ADR registry, not here.

## Steps

Each row is one run; stop after it. Find the step from `aidlc_state.py next --paddock <p>` and the files present: the last round file, whether its answers are complete (`lint_questions.py`), and whether its layers have rows in `hla-decisions.md`.

| Step | Read besides core rules | Writes | Ends with |
| --- | --- | --- | --- |
| Bootstrap and ask A | `references/layers-a.md` | `hla-questions-a.md` | `step --to asked` |
| Analyse A, ask B | `layers-a.md`, `layers-b.md` | decisions, `hla-questions-b.md` | stop |
| Analyse B, ask C | `layers-b.md`, `layers-c.md` | decisions, `hla-questions-c.md` | stop |
| Analyse C | `layers-c.md` | decisions | `step --to analysed` |
| Generate | `references/generation-rules.md`, `assets/hla-template.md` | `hla.md` | `step --to produced`, gate summary |
| Refine or sign off | `generation-rules.md` | changed sections | validate, gate |

### Bootstrap (in the round A run)

1. `aidlc_state.py status --paddock <p> --format text`, then `inputs --paddock <p> --stage hla`. Exit 3: name the missing file and the stage that produces it, and stop.
2. Read `knowledge/_digest.md`. Use `knowledge/_outline.json` to open a raw section by line range only when a layer needs it. Read only the `## Digest` of each `codekb/<repo>/overview.md` (shared store at the planning repo root; `inputs` resolves it).
3. Shortlist ADRs without reading the whole index: `grep -E '"(id|title|status)"' <architecture-index.json>`, then read the decision line of the candidates only. Accepted binds, Proposed is directional, Superseded and Deprecated are not used.
4. Open the round A file with `## Context`, at most 15 lines: business driver, current state, constraints, stakeholders, solution type, applicable ADRs, documents that could not be read. Then `## ADR shortlist`: `| Layer | ADR | Status | What it settles |`.

### Round files

Per layer: a `## Layer <n>: <name>` heading, a `Proposal:` paragraph of at most six lines (the design you would choose, why, and the ADR ids it follows), then two to four `## Q<n>` questions in the core-rules format, numbered per file. Scale the count to the paddock depth. Anything the digest, code knowledge or an accepted ADR settles is not asked: it goes under `## Already answered` at the end of the file, with its source. Rounds B and C open with `## Settled in earlier rounds`: only the decision ids that constrain them. Answers are cited as `A-Q3`, `B-Q1`, `CL-Q2`.

Before stopping, run `lint_questions.py --file <file> --allow-open` and fix every finding. Tell the user which file to answer.

### Analyse a round

1. `lint_questions.py --file <file>`. Open answers: list them and stop.
2. Analyse per the core rules. Follow-ups go to `hla-clarifications.md`, numbered on from the last question there, each heading naming the original (`## Q4 Retention period (B-Q2)`). Stop until they are answered.
3. Reserve ids with `aidlc_state.py decision-id --paddock <p> --count <n>` and add the rows. Source is an answer id, an ADR id or a document path. Flag is `-`, `departure`, `proposed-adr`, `novel`, `cross-team` or `contested`. Following an Accepted ADR is cited, not decided: no row. Keep the record's Digest current.
4. An answer that departs from an Accepted ADR gets the `departure` flag; generation turns it into a header exception, a risk and a decision needed.
5. Write the next round file. After round C, `aidlc_state.py step --paddock <p> --stage hla --to analysed`.

### Generate

Follow `references/generation-rules.md`. Validate with `scripts/validate_doc.py` until it exits 0, run `step --to produced`, set `status: in-review`, and end as the core rules' gate says. Sign-off and refinement follow the same reference. Never set `accepted` yourself.

## Without a paddock

When the user has documents but no paddock, ask once where to write and where the ADR index is (or that there is none, giving `adr_registry_commit: none`). Skip every `aidlc_state.py` call, number decisions from `D1` in `hla-decisions.md`, and keep sign-off in the header only. The rounds, record and validator are unchanged.

## When a step fails

- `aidlc_state.py`: exit 1 is a refusal (read the findings), 2 a wrong flag, 3 a missing file or paddock, 4 a malformed `state.json` (report it; never edit it by hand).
- `lint_questions.py`: exit 1 lists questions to fix or answers still open.
- `validate_doc.py`: exit 1 lists findings with line numbers; 3 or 4 means the template, schema or index is missing or broken: report it, do not work around it.
- An input contradicts an accepted ADR, or two inputs contradict each other: ask, never pick silently.
