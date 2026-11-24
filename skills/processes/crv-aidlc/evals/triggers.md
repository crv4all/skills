# Trigger evals — crv-aidlc

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

Install the other `crv-aidlc-*` skills alongside for these runs: half of what is
tested is whether the entry skill and the stage skills separate cleanly.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "Start a Bolt for migrating the billing service." | Names the Bolt directly. |
| T2 | "Resume the Bolt from last week and tell me what is next." | Resume plus the "what is next" routing question. |
| T3 | "I want AI-DLC applied to this new feature, structured and gated." | Names the method and asks for gates. |
| T4 | "Close the reporting Bolt, it is done." | Closing is the skill's job, and the close refusal is the point. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "Write the high-level architecture for this Bolt." | The stage work itself. | `crv-aidlc-hla` |
| N2 | "Write the technical design document from the accepted HLA." | The stage work itself. | `crv-aidlc-tdd` |
| N3 | "Reverse-engineer the checkout repo into the codebase knowledge folder." | The stage work itself. | `crv-aidlc-reverse-engineering` |
| N4 | "File these stories under ABC-123." | Jira filing, no Bolt involved. | `crv-create-jira-story` |
| N5 | "Rename this variable across the repo." | A small change with no staged process. | nothing |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "Do the requirements analysis for the billing Bolt." | Fire, then hand over | The entry skill finds the Bolt and runs `next`, then routes to `crv-aidlc-inception`. Doing the analysis itself is a failure. |
| B2 | "Plan this feature properly." | Fire, then ask | "Properly" suggests a staged process, but the user may want only a plan. Ask whether to open a Bolt before creating one. |
| B3 | "Is the architecture stage approved yet?" | Fire for `status` only | A read-only question about a Bolt; answer from `status` and change nothing. |
