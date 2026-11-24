# Trigger evals — crv-aidlc-construction

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

Install `crv-aidlc`, `crv-aidlc-inception`, `crv-aidlc-hla`, `crv-aidlc-tdd` and
`crv-aidlc-reverse-engineering` alongside: the neighbours are what this
description has to separate from.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "Start construction on unit U2 of the billing Bolt." | Names a Unit and a Bolt. |
| T2 | "Write the code plan for the export unit before we touch any code." | The checkbox plan is this skill's core output. |
| T3 | "Generate the code for U1 now that the plan is approved." | Execution of an approved plan. |
| T4 | "Run build and test for the whole Bolt and tell me what is Met." | Build and Test for a Bolt. |
| T5 | "Slice 2 covers U3 and U4. Build it." | A Slice of a Bolt. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "Open a Bolt for the export feature." | Opening is the entry skill's job. | `crv-aidlc` |
| N2 | "Turn the requirements into units of work." | Units are Inception output. | `crv-aidlc-inception` |
| N3 | "Write the high-level architecture." | Design before Inception. | `crv-aidlc-hla` |
| N4 | "Rename this function across the repo." | An ordinary code edit, no Bolt. | nothing |
| N5 | "Scan the repo and document its structure." | Reverse engineering. | `crv-aidlc-reverse-engineering` |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "What is next for the billing Bolt?" | Do not fire | A routing question for `crv-aidlc`, which may then hand over here. |
| B2 | "Fix this failing test in the orders service." | Do not fire | One-off code work unless the user ties it to a Bolt bugfix. |
| B3 | "The Bolt is a bugfix; write the fix and its test." | Fire | Bolt work in the `bugfix` scope; Code Generation applies. |
