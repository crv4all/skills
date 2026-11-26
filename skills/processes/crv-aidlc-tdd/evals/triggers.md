# Trigger evals — crv-aidlc-tdd

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

Install `crv-aidlc`, `crv-aidlc-hla` and `crv-aidlc-inception` alongside. The
acronym also collides with test-driven development, which is tested below.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "The HLA is accepted; write the technical design document." | Names the TDD after an accepted HLA. |
| T2 | "Do we need a TDD for the billing Bolt?" | The applicability decision is this skill's first step. |
| T3 | "The TDD questions are answered, write it up." | Resuming the round. |
| T4 | "Reviewers asked for a detailed design of the ingestion part." | A review request for detailed design. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "Let's do TDD on this parser: write the failing test first." | Test-driven development, not a design document. | nothing |
| N2 | "Write the high-level architecture for this Bolt." | The HLA comes first. | `crv-aidlc-hla` |
| N3 | "Change the HLA so the API is event-driven." | An HLA change. | `crv-aidlc-hla` |
| N4 | "Break the accepted design into units of work." | Inception work. | `crv-aidlc-inception` |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "Write the TDD now; the HLA is still in review." | Fire | The HLA review is the organisation's own and never conditions the TDD; the skill mentions it once and continues. |
| B2 | "Add more detail on retries to the design." | Fire if a TDD exists | Refinement of an existing TDD; if only an HLA exists, it is an HLA refinement. |
