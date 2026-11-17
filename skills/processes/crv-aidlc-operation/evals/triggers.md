# Trigger evals — crv-aidlc-operation

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

Install `crv-aidlc`, `crv-aidlc-construction`, `crv-aidlc-inception`,
`crv-aidlc-hla`, `crv-aidlc-tdd` and `crv-aidlc-reverse-engineering` alongside:
the neighbours are what this description has to separate from.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "Plan the release of the billing paddock: migration first, then the cut-over." | A release plan for a paddock. |
| T2 | "Write the runbook and the rollback runbook for the write-master switch." | Runbook artifacts are this skill's output. |
| T3 | "Run the deployment of the paddock through staging and prod and keep the log." | Execution record; people run the steps. |
| T4 | "Resume the deploy log of the export paddock." | Resume point of Deployment Execution. |
| T5 | "Which verification checks must pass before we retire the old table?" | Verification checks and retirement. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- |
| N1 | "Open a paddock for the export feature." | Opening is the entry skill's job. | `crv-aidlc` |
| N2 | "Run build and test for the paddock." | Build and Test never deploys. | `crv-aidlc-construction` |
| N3 | "Write the high-level architecture." | Design before Inception. | `crv-aidlc-hla` |
| N4 | "Add a GitHub Actions workflow to deploy this service." | Designing a pipeline is not this skill's work. | nothing |
| N5 | "Scan the repo and document its structure." | Reverse engineering. | `crv-aidlc-reverse-engineering` |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "What is next for the billing paddock?" | Do not fire | A routing question for `crv-aidlc`, which may then hand over here. |
| B2 | "Deploy the service to prod now." | Do not fire | Outside a paddock; and this skill never deploys, it only records a person's run. |
| B3 | "Build and test passed; how do we release the paddock?" | Fire | The next step after Build and Test is the release plan. |
