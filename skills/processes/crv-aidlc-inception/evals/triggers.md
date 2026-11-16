# Trigger evals — crv-aidlc-inception

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

Install `crv-aidlc`, `crv-aidlc-hla`, `crv-aidlc-tdd`, `crv-aidlc-construction` and `crv-create-jira-story` alongside: the neighbours are what this description has to separate from.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "The HLA is accepted. Write the requirements for the billing paddock." | Requirements analysis after the HLA. |
| T2 | "Turn these requirements into user stories with acceptance criteria." | User stories stage. |
| T3 | "Split the paddock into units of work and show their dependencies." | Units generation. |
| T4 | "The units talk to each other over events; define the contracts before we build." | Contract design. |
| T5 | "Plan the Bolts for this paddock and what each one has to prove." | Delivery planning. |
| T6 | "The requirements questions are answered, carry on." | Resuming an Inception stage. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "Open a paddock for the export feature." | Opening is the entry skill's job. | `crv-aidlc` |
| N2 | "Write the high-level architecture from these documents." | Precedes Inception. | `crv-aidlc-hla` |
| N3 | "Write the technical design document for the accepted HLA." | Follows the HLA, not Inception. | `crv-aidlc-tdd` |
| N4 | "Scan the repository and document how it works." | Code knowledge. | `crv-aidlc-reverse-engineering` |
| N5 | "Build unit U-2 from its design." | Construction. | `crv-aidlc-construction` |
| N6 | "Create Jira stories under epic PAY-12 from this list." | Filing tickets. | `crv-create-jira-story` |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "What is next for the billing paddock?" | Do not fire | A routing question; `crv-aidlc` answers it and then hands over. |
| B2 | "Write user stories for a ticket description I pasted, no paddock." | Do not fire | No paddock and no process asked for; ordinary drafting or `crv-create-jira-story`. |
| B3 | "The new requirement contradicts the HLA's choice of queue." | Fire | The skill raises it as an HLA change to the approver; it does not decide or edit the HLA. |
