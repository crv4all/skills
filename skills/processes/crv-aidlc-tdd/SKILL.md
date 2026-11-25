---
name: crv-aidlc-tdd
description: >-
  Produces the Technical Design Document (TDD), the detailed design that follows a reviewed high-level architecture in a Bolt. Decides first whether a TDD is required at all (a review request or a high-risk impact flag), checks the HLA header says the organisation reviewed it, asks only what the HLA left open and carries its decisions forward instead of asking them again, and writes a validated tdd.md. Use when someone wants to write, refine or hand over a technical design document, detailed design or TDD after an HLA, or asks whether a TDD is needed. Not test-driven development or writing tests first. Not for the HLA itself (crv-aidlc-hla), opening or routing a Bolt (crv-aidlc), or requirements, stories and units (crv-aidlc-inception).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: balanced
---

# Technical design document

Decides whether a TDD is needed, then details only what the HLA left open. HLA decisions are cited, never asked again; an answer that contradicts the HLA stops the TDD and goes back to the HLA.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Each step reads the HLA, its decision record and the question file; that context belongs in an agent that exits when the step is done.

**Model tier: `balanced`.** The big decisions are already made in the HLA, so this needs judgement about detail, not frontier reasoning; economy models tend to re-decide the HLA or lose the thread across sections. State it, do not ask about it. One line, then start work:

> Running `crv-aidlc-tdd` (step: ask) in a subagent on the balanced tier.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session. Then read only the files the step table names. Scripts live in `scripts/`; run them with `python3`.

## What this produces

Either a recorded SKIP with its reason, or, in `<bolt>/architecture/`:

- `tdd-questions.md` (and `tdd-clarifications.md` when needed).
- `tdd-decisions.md`: a `## Digest`, then `| Id | Section | Decision | Reason | Source | Flag |`, ids continuing the Bolt sequence.
- `tdd.md`: the template's sections in order, `hla_link` pointing at the HLA, `validate_doc.py` exit 0, `status: in-review` while the organisation's review is open. Optionally `tdd-<part>.md` files when parts differ substantially.

## When not to use this

- Test-driven development: this skill writes a design document, not tests.
- The HLA, or any change to an HLA decision: `crv-aidlc-hla`.
- Opening, resuming or routing a Bolt: `crv-aidlc`.
- Requirements, stories or units: `crv-aidlc-inception`. It reads the TDD's digest.

## Steps

Each row is one run. Find the step from `aidlc_state.py next --bolt <p>` and the files present.

| Step | Read besides core rules | Writes | Ends with |
| --- | --- | --- | --- |
| Applicability and ask | `references/sections.md` | SKIP, or `tdd-questions.md` | `decide` or `step --to asked` |
| Analyse | `references/sections.md` | `tdd-decisions.md` | `step --to analysed` |
| Produce | `references/writing.md`, `assets/tdd-template.md` | `tdd.md` | `step --to produced`, checkpoint |
| Refine | `references/writing.md` | changed sections | validate, checkpoint |

### 1. Applicability

1. `aidlc_state.py status --bolt <p> --format text`, then `inputs --bolt <p> --stage tdd`. Exit 3: report the missing file and its stage; stop.
2. Read the header of `architecture/hla.md`. The TDD validator needs `status: accepted` there: that field is the organisation's own review of the HLA. If it is not `accepted`, tell the engineer in one line that the TDD can be drafted but will not validate until that review is recorded, recommend waiting, and let them decide. Never edit the header yourself.
3. A TDD is required when (a) `review_conditions` or `decision_needed` asks for one, or (b) `impact_flags` include `new-data-store`, `new-public-exposure`, `major-cutover` or `new-domain-messaging`.
4. Neither: say a TDD is not required and why, then `aidlc_state.py decide --bolt <p> --stage tdd --decision skip --reason "<flags and conditions checked>"`. If the engineer overrides with a reason, record it with `decide --decision execute --reason "override: <reason>"` and use trigger `override`.

### 2. Ask

Investigate first (HLA, its decisions, code, tests, configuration). Write `tdd-questions.md` as `references/sections.md` describes, with only what is open. Lint it with `lint_questions.py --file <file> --allow-open`, fix every finding, run `step --to asked`, and tell the engineer which file to answer.

### 3. Analyse

1. `lint_questions.py --file <file>`. Open answers: list them and stop.
2. Analyse per the core rules; follow-ups go to `tdd-clarifications.md`. Stop until answered.
3. An answer that contradicts an HLA decision is not a TDD decision. Stop, name the HLA decision id, and send the change to `crv-aidlc-hla` refinement. Resume only after the HLA is updated.
4. Reserve ids with `aidlc_state.py decision-id --bolt <p> --count <n>`; write the rows (flags as in the HLA record: `-`, `departure`, `proposed-adr`, `novel`, `cross-team`, `contested`) and the Digest. Run `step --to analysed`.

### 4. Produce and refine

Follow `references/writing.md`: write `tdd.md`, validate with `scripts/validate_doc.py --kind tdd` until it exits 0, run `step --to produced`, set `status: in-review`, and run the checkpoint as the core rules say. The header's review fields are the organisation's record: never fill them to proceed.

## Without a Bolt

Ask once for the HLA's path and the ADR index (or none). Apply the same applicability checks by reading the HLA header, skip every `aidlc_state.py` call, and number decisions after the highest id in the HLA and its record.

## When a step fails

- `aidlc_state.py`: exit 1 is a refusal (read the findings), 2 a wrong flag, 3 a missing file or Bolt, 4 a malformed `state.json` (report it; never edit it by hand).
- `validate_doc.py`: `hla-not-accepted` means the HLA header does not say accepted; report it and let the engineer decide. `decision-not-new` means an id was reused; reserve a new one. Exit 3 or 4: an input is missing or broken; report it.
- The HLA leaves something the TDD needs undecided at the HLA's level (a new container, a new store): that is an HLA gap; raise it rather than deciding it here.
