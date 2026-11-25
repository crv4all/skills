# Trigger evals — crv-aidlc-hla

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

Install `crv-aidlc`, `crv-aidlc-tdd` and `crv-aidlc-inception` alongside: the
neighbours are what this description has to separate from.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "Write the high-level architecture for the billing Bolt." | Names the HLA and a Bolt. |
| T2 | "Here are the discovery documents. Draft a solution architecture we can take to review." | An architecture document from input documents, no Bolt named. |
| T3 | "The layer 4 to 8 questions are answered, carry on with the architecture." | Resuming the layers. |
| T4 | "Reviewers want the cutover moved to a parallel run; update the HLA." | Refinement of an existing HLA. |
| T5 | "Which ADRs constrain the design for the reporting migration?" | ADR binding for a design is part of bootstrap. |
| T6 | "Start investigating the data migration approach for the architecture." | A contribution for one concern. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "The HLA is accepted. Write the technical design document." | The TDD follows the HLA. | `crv-aidlc-tdd` |
| N2 | "Open a Bolt for the export feature." | Opening is the entry skill's job. | `crv-aidlc` |
| N3 | "Turn the accepted HLA into user stories." | Inception work. | `crv-aidlc-inception` |
| N4 | "Write an ADR choosing the message broker." | An ADR, not a design document. | nothing |
| N5 | "Draw a quick diagram of how these two services talk." | No design process asked for. | nothing |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "What is next for the billing Bolt?" | Do not fire | A routing question; `crv-aidlc` answers it and may then hand over to this skill. |
| B2 | "Looks good, proceed with the HLA." | Fire for the checkpoint | The skill records the direction through the checkpoint; the header's review fields are the organisation's record and are never filled to proceed. |
| B3 | "Do we need a TDD for this design?" | Do not fire | The applicability decision belongs to `crv-aidlc-tdd`. |
