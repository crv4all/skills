---
name: crv-aidlc-hla
description: >-
  Produces the High-Level Architecture (HLA) for a Bolt before Inception, shared by every engineer on it: one hla.md and one decision record, a contribution file per concern that several people investigate at once, proposals over twelve design layers that cite the ADRs they follow, questions only where something material is open, a consistency review across contributors, and a validated document. Use when someone wants to write, refine or review a high-level or solution architecture for a Bolt or from input documents, investigate one concern of it (security, data migration), take in architecture-review feedback, or asks which ADRs bind a design. Not for the Technical Design Document (crv-aidlc-tdd), opening or routing a Bolt (crv-aidlc), or requirements, stories and units (crv-aidlc-inception).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: frontier
---

# High-level architecture

One architecture per Bolt: one `architecture/hla.md` and one decision record, written by several engineers over time. Proposals come first, questions only where something material is open, every decision lands in the shared record with an id, and a concern investigated in parallel lives in its own contribution file until its conclusion is merged.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Each step reads the digest, the ADR index and the architecture files; that context belongs in an agent that exits when the step is done.

**Model tier: `frontier`.** The HLA fixes decisions every later stage inherits, and the consistency review needs the best reasoning, so quality dominates cost. State it, do not ask. One line, then start work:

> Running `crv-aidlc-hla` (step: contribution) in a subagent on the frontier tier.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session. Then read only the files the step table names. Scripts live in `scripts/`; run them with `python3`.

## What this produces

In `<bolt>/architecture/`:

- `hla.md`: the template's sections in order, a valid header, `validate_doc.py` exit 0.
- `hla-decisions.md`: a `## Digest`, then one row per decision: `| Id | Layer | Decision | Reason | Source | Flag |`, optionally `Status` and `Owner`. One record for the whole Bolt.
- `contributions/<concern>.md`: one per concern investigated apart (`assets/contribution-template.md`).
- `hla-questions-a.md`, `-b.md`, `-c.md` (layers 1 to 3, 4 to 8, 9 to 12) and `hla-clarifications.md`: only what needed asking.

## When not to use this

- The Technical Design Document after an accepted HLA: `crv-aidlc-tdd`.
- Opening, resuming or routing a Bolt: `crv-aidlc`.
- Requirements, stories, domain design or units: `crv-aidlc-inception`. It reads the HLA.
- Writing an ADR: that belongs in the ADR registry, not here.

## Steps

Find the step from the engineer's request, `aidlc_state.py next --bolt <p>` and `status --bolt <p> --format text` (it lists each contribution, owner and status). Each step is one run.

| Step | Read besides core rules | Writes |
| --- | --- | --- |
| Bootstrap and first layers | `layers-a.md` | `hla-questions-a.md`, decisions; `step --to asked` |
| Next layers | `layers-b.md`, `layers-c.md` | question files, decisions; `step --to analysed` after the last |
| Contribution | `assets/contribution-template.md` | the contribution, `hla.md` sections |
| Generate, refine, review feedback | `references/generation-rules.md`, `assets/hla-template.md` | `hla.md`; `step --to produced` |

### Bootstrap

1. `aidlc_state.py status --bolt <p> --format text`, then `inputs --bolt <p> --stage hla`. Exit 3: name the missing file and the stage that produces it, and stop.
2. Read `knowledge/_digest.md`. Use `knowledge/_outline.json` to open a raw section by line range only when a layer needs it. Read only the `## Digest` of each `codekb/<repo>/overview.md`.
3. Refresh the ADR index so the shortlist uses the latest registry: `python3 ../crv-aidlc/scripts/build_adr_index.py --registry <registry path> --out <planning repo>/architecture-index.json --refresh`, then `aidlc_state.py sync --bolt <p> -m "refresh the ADR index"`. Name the ADRs it reports as added or changed. Shortlist without reading the whole index: `grep -E '"(id|title|status)"' <architecture-index.json>`, then read the decision line of the candidates only. Accepted binds, Proposed is directional, Superseded and Deprecated are not used.
4. The first question file opens with `## Context`, at most 15 lines (business driver, current state, constraints, stakeholders, solution type, applicable ADRs, documents that could not be read), then `## ADR shortlist`: `| Layer | ADR | Status | What it settles |`.

### The layers

Work the twelve layers in three groups: A is layers 1 to 3, B is 4 to 8, C is 9 to 12, in `hla-questions-<a|b|c>.md`. Per layer: a `## Layer <n>: <name>` heading and a `Proposal:` paragraph of at most six lines (the design you would choose, why, the ADR ids it follows). Investigate first: the digest, code knowledge, accepted ADRs and earlier answers settle most of it (`## Already answered`, with sources). Ask only what is critical or material and still open; decide reversible and trivial choices under `## Assumed`, each `because ...`. A layer with nothing open gets a proposal and no question. A group with no question needs no question file; its proposals and assumed choices go in `hla.md` or the file that exists. Number questions per file; cite answers as `A-Q3`, `B-Q1`, `CL-Q2`.

Before stopping run `lint_questions.py --file <file> --allow-open` and fix every finding; tell the engineer which file to answer. With answers in: `lint_questions.py --file <file>`; open answers are listed and you stop; vague ones become follow-ups in `hla-clarifications.md` (heading names the original, `## Q4 Retention period (B-Q2)`).

Record decisions in the shared record: `aidlc_state.py decision-id --bolt <p> --count <n>` reserves ids; add rows (Source is an answer id, ADR id or path; Flag is `-`, `departure`, `proposed-adr`, `novel`, `cross-team` or `contested`). Following an Accepted ADR is cited, not decided. An answer that departs from one gets `departure`; generation turns it into a header exception, a risk and a decision needed. If `decision-id` says the ids were not reserved, tell the engineer to fix the connection and run it again; never invent an id. After group C: `step --to analysed`.

## Contributions: several engineers, one architecture

A contribution is how one engineer investigates one concern (security, data migration, networking) without touching what others edit. It has no stage. Its owner merges the conclusion into `hla.md`; the reasoning stays in the file.

1. **Open it.** Copy `assets/contribution-template.md` to `architecture/contributions/<concern>.md` (kebab-case; the file name is the `concern`). Fill the header (`concern`, `owner`, `status: draft`, `touches` = the `hla.md` section titles it will change, `affects`). Run `aidlc_state.py contribution --bolt <p> --concern <concern> --status draft --note "<one line>"`.
2. **Keep it proportionate.** A paragraph and a table can be enough. Investigate first (code, tests, configuration, documents, decisions); findings carry sources; the proposal is words its owner can merge. Ask only what is critical or material; assume the rest and say why.
3. **Reserve decisions.** `decision-id --count <n>`; write each row in `hla-decisions.md` first, with Owner and Status (`proposed`, then `constraint` or `accepted`). A Status changes only on the engineer's stated direction (an answer in a question file or their word in the conversation); silence never accepts, and a new session never assumes what the engineer saw in an earlier one. Then cite the ids under Decisions; never restate a decision there.
4. **Merge** the conclusion into the `hla.md` sections named in `touches`, plus the line that names the decision range when new decisions were recorded; nothing else. Set the header to `proposed` while others must react, `merged` once it is in `hla.md`; run `contribution ... --status proposed|merged` with the same word.
5. **Validate both:** `python3 scripts/validate_doc.py --file architecture/contributions/<concern>.md --kind contribution` and `--kind hla` on `hla.md`. Fix findings.
6. **Review consistency** as soon as a contribution is merged.

Two engineers on two concerns edit two files and different sections, so their work merges without a manual step. When both need one section, say so before editing and agree who writes it.

## Consistency review

Do this when a contribution is merged and again at the HLA checkpoint. `validate_doc.py` catches unknown decision ids, a term with two owners and unknown interface parties; it cannot see the rest. Read `hla.md`, `hla-decisions.md` and every open contribution for: conflicting responsibilities, data ownership (two owners, or none), contract assumptions, migration assumptions, security boundaries, quality attributes pulling against each other, legacy behaviour to preserve, operations and recovery.

For each contradiction state: what conflicts and where (file, section, decision ids), the consequence if both stand, the options with your recommendation, and who should talk. Never pick one contributor's side silently, edit another's contribution, or hide a warning. With no conflict, say so in one line.

## Organisation review feedback

Take the organisation's architecture-review feedback in as a contribution `review-<date>`: each point in its Decisions section maps to the decision ids it changes or adds (new ids from `decision-id`). Merge, record `contribution`, then for each changed id run `aidlc_state.py context --bolt <p> --id <D<n>>` and tell the engineer which Slices and Units rely on it. Fill the header's `status`, `signed_off_by`, `signed_off_on` only from what a reviewer states; it is their record and never conditions a stage.

## Generate, refine and checkpoint

Follow `references/generation-rules.md`: validate until `validate_doc.py` exits 0, run `step --to produced`, run the consistency review, then the checkpoint as the core rules say. Report warnings; fix findings. A later change to `hla.md` gets new decision ids; `context` tells the Units that rely on the old ones.

## Without a Bolt

When the user has documents but no Bolt, ask once where to write and where the ADR index is (or that there is none, giving `adr_registry_commit: none`). Skip every `aidlc_state.py` call, number decisions from `D1` in `hla-decisions.md`. The layers, record and validator are unchanged.

## When a step fails

- `aidlc_state.py`: exit 1 is a refusal (read the findings), 2 a wrong flag, 3 a missing file or Bolt (for `contribution`, the contribution file or its header is missing), 4 a malformed `state.json` (report it; never edit it by hand).
- `lint_questions.py`: exit 1 lists questions to fix or answers still open.
- `validate_doc.py`: exit 1 lists findings with line numbers; 3 or 4 means the template, schema or index is missing or broken: report it, do not work around it.
- An input contradicts an accepted ADR, or two inputs contradict each other: ask, never pick silently.
