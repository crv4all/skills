# Trigger evals — crv-aidlc-reverse-engineering

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

Install `crv-aidlc`, `crv-aidlc-hla`, `crv-aidlc-inception`,
`crv-aidlc-construction` and `crv-codebase-onboarding` alongside: the
neighbours are what this description has to separate from.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "Reverse-engineer the billing-service repo for the export paddock before we write the architecture." | Names the activity, a repo and a paddock. |
| T2 | "Understand the existing codebase this paddock changes and map it for the team." | Research of an existing codebase for a paddock. |
| T3 | "Is the code knowledge for the catalog repo stale?" | A freshness question about the shared store. |
| T4 | "The catalog repo moved on since last month. Refresh its code knowledge." | Refresh, probably a focused rescan. |
| T5 | "Scan the three target repos so the HLA can cite what is already there." | Code research that the architecture relies on. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "Open a paddock for the export feature." | Opening is the entry skill's job. | `crv-aidlc` |
| N2 | "Write the high-level architecture for the export paddock." | The architecture document, not the code research. | `crv-aidlc-hla` |
| N3 | "Turn the accepted HLA into stories and units." | Inception work. | `crv-aidlc-inception` |
| N4 | "Implement unit u2 in the billing-service repo." | Building, not researching. | `crv-aidlc-construction` |
| N5 | "I just joined this team. Write onboarding docs for this repository in its docs folder." | Documents a repository inside itself. | `crv-codebase-onboarding` |
| N6 | "Explain what this one function does." | No paddock, no repository mapping. | nothing |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "What is next for the export paddock?" | Do not fire | A routing question for `crv-aidlc`; it may then hand over here. |
| B2 | "Get me up to speed on the legacy importer before I change it." | Fire only when a paddock is in play | In a paddock it is this stage; with no paddock the onboarding skill is the right one. |
| B3 | "The new target repo is empty. Run reverse engineering on it." | Fire, then stop in one line | Greenfield: the skill confirms there is nothing to do. |
