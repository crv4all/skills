# Behaviour evals — crv-aidlc-tdd

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

The characteristic failures here are a TDD that nobody needed, a TDD written
against an HLA nobody accepted, and a TDD that quietly re-decides the HLA. B1,
B2 and B4 guard them.

## B1 — Not required

**Setup:** An accepted HLA with `impact_flags: [cross-team-contract]` and no review condition asking for a TDD.
**Prompt:** "Write the TDD."

- [ ] The agent says a TDD is not required and names the flags and conditions it checked.
- [ ] `aidlc_state.py decide --stage tdd --decision skip` runs with that reason.
- [ ] No question file or `tdd.md` is written.

## B2 — HLA not accepted

**Setup:** An HLA with `status: in-review` and `impact_flags: [new-data-store]`.
**Prompt:** "Start the technical design."

- [ ] The agent stops and says the TDD waits for the HLA sign-off.
- [ ] Nothing is written; `state.json` is unchanged.

## B3 — Ask by section

**Setup:** An accepted HLA with `impact_flags: [new-data-store, major-cutover]` and a decision record up to `D14`.
**Prompt:** "Start the technical design."

- [ ] `tdd-questions.md` opens with `## Carried from the HLA`, listing HLA decision ids per section.
- [ ] No question re-asks something an HLA decision settles.
- [ ] Questions are grouped under `## Section:` headings; sections with nothing open have a line under `## Already answered`.
- [ ] `lint_questions.py --allow-open` passes and `step --to asked` runs.

## B4 — An answer contradicts the HLA

**Setup:** Answers in; one chooses a store other than the one HLA decision `D7` fixed.
**Prompt:** "The questions are answered."

- [ ] The agent stops, names `D7`, and sends the change to HLA refinement.
- [ ] No TDD decision is recorded for it; no `tdd.md` is written.

## B5 — Produce and validate

**Setup:** Answers settled; decisions recorded as `D15` to `D18`.
**Prompt:** "Write the TDD."

- [ ] `tdd.md` has every template section in order; `hla_link` resolves to the accepted HLA.
- [ ] Content the HLA already holds is cited (`HLA D6`), not restated.
- [ ] Post-release validation has its own checks (who, when, expected result, action), not a copy of release readiness.
- [ ] Performance targets give P50, P95 and P99.
- [ ] `validate_doc.py --kind tdd` exits 0; `status` is `in-review`.

## B6 — Reused decision id

**Setup:** A draft `tdd.md` whose Design decisions table uses `D9`, while the HLA record reaches `D14`.
**Prompt:** "Validate the TDD."

- [ ] `validate_doc.py` reports `decision-not-new` for `D9`.
- [ ] The fix reserves a new id with `aidlc_state.py decision-id` rather than picking a number by hand.
