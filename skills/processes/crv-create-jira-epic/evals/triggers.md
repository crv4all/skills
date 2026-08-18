# Trigger evals — crv-create-jira-epic

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date. Never report a result you did
not produce.

`crv-create-jira-story` should be installed alongside for these runs. Half of
what is being tested is whether the two skills separate cleanly, and that cannot
be observed when only one of them exists.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "Create a Jira epic for the token expiry work." | The plainest phrasing of the task. |
| T2 | "We need an epic in Jira to hold the ingest rewrite — can you raise one?" | Same intent, different verb ("raise"), epic named indirectly. |
| T3 | "Turn this approved spec into an epic and file it." | Spec-to-epic, the second common entry point. Names no tool, so it tests whether the description carries the association. |
| T4 | "Open an ABC epic for the Q3 migration." | Names a project key rather than the word Jira. Should still fire. |

## Should not fire

These matter more. A description that fires for everything is as useless as one
that fires for nothing, and it is harder to notice.

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "File three stories under ABC-123." | Stories under an existing epic. | `crv-create-jira-story` |
| N2 | "Move ABC-123 to Done and add a comment saying the PR merged." | Transitioning and commenting on an existing issue. This skill only creates. | nothing |
| N3 | "What is in epic ABC-123?" | A read. Nothing is being created. | nothing |
| N4 | "Should we do the ingest rewrite this quarter?" | A prioritisation conversation. Filing an epic would quietly foreclose the decision being asked about. | nothing |
| N5 | "Write a skill for filing epics." | Authoring a skill, not using one. | `crv-create-skill` |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "Break this spec into an epic and its stories, and file everything." | Fire, then hand off | Both skills are in scope and the order is forced: the epic must exist before stories can name a parent. This skill should fire first and its report should point at `crv-create-jira-story`. Firing both at once, or the story skill first, is a failure. |
| B2 | "Set up Jira for me." | Do not fire | Ambiguous between configuring the MCP server and filing something. Nothing is being created, so the right move is to ask — and if it turns out to mean configuration, that is `references/jira-setup.md`, not an epic. |
| B3 | "Add an epic to the board." | Fire | "Board" rather than "Jira" is thin evidence, but "add an epic" is unambiguous about the deliverable. If this does not fire, the description is over-indexed on the word Jira. |
