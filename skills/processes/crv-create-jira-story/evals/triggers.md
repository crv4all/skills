# Trigger evals — crv-create-jira-story

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

`crv-create-jira-epic` should be installed alongside for these runs. Half of
what is being tested is whether the two skills separate cleanly, and that cannot
be observed when only one of them exists.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "File a Jira story under ABC-123 for rejecting expired tokens." | The plainest phrasing, with an explicit parent. |
| T2 | "Raise a ticket for this under the ingest epic." | "Ticket" rather than "story", epic named in prose. Tests the vocabulary people actually use. |
| T3 | "Break this spec into stories and put them under ABC-123." | Bulk decomposition, the case where duplicate detection earns its keep. |
| T4 | "Add these three items to the epic as stories, 3 points each." | Estimates supplied inline; names no tool at all. |

## Should not fire

These matter more. A description that fires for everything is as useless as one
that fires for nothing, and it is harder to notice.

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "Create an epic for the ingest rewrite." | The parent itself, not its children. | `crv-create-jira-epic` |
| N2 | "Close ABC-456 now that the PR merged." | Transitioning an existing issue. This skill only creates. | nothing |
| N3 | "Re-estimate ABC-456 at 5 points." | Editing an existing issue. | nothing |
| N4 | "How should we split this work up?" | A decomposition conversation. Filing stories would ratify a split nobody agreed to. | nothing |
| N5 | "Write user stories in the README so the team can review them." | Stories as a document, not as Jira issues. | nothing |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "File these stories." (no parent named) | Fire, then ask | Firing is right — the intent is unambiguous. The skill must then ask for the parent epic rather than filing orphans or inventing an epic. Filing anything without a parent is a failure of this case, not a pass. |
| B2 | "Create the epic and its stories." | Do not fire first | Both are in scope, but the epic must exist before a story can name a parent. `crv-create-jira-epic` fires first and hands off. This skill firing first is a failure. |
| B3 | "Add a subtask to ABC-456." | Do not fire | A subtask under a story is a different issue type and a different parent relationship. The skill files stories under epics. Firing here would file the wrong thing at the wrong level, which is worse than declining. |
