# What to do when a step fails

Look the failure up rather than deciding what to do about it. Improvisation on a
failed batch is the thing this skill exists to prevent, and the difference
between the rows below is often the difference between a two-minute fix and a
day of untangling.

Three outcomes appear in the right column, and they are not interchangeable:

- **Stop.** Create nothing further, report what blocked, and wait. A partial
  batch reported accurately is recoverable; one reported as success is not.
- **Not a failure.** File without the value and say so in the report. A field
  that resolved fine and has nothing to write is not an error.
- **Ask.** One question, then continue. Never a guess in place of the question.

## Preflight and configuration

| Failure | What it means | Do |
| --- | --- | --- |
| No Jira tools here, but the spawning session had them | Tool inheritance, not setup. MCP servers are granted per agent. | Stop. Hand back for an inline re-run. Do **not** point at the setup reference: nothing there fixes it. |
| No Jira tools anywhere | Server not installed or not enabled for this harness | Stop. Point at the setup reference, section 1, on installing and enabling the server. |
| Tools present, every call unauthorised | OAuth incomplete or the grant expired | Stop. Point at the setup reference's troubleshooting section, on re-running server authentication. An agent cannot complete a browser consent screen. |
| `jira_setup.py --check` exits `1` | Site or project not recorded | Derive only from a value the user supplied, or a single accessible site. Otherwise stop and give the `--set … --confirm` command. |
| `jira_setup.py --check` exits `4` | Configuration file corrupt | Stop. Name the path. It needs inspection, not re-running setup. |
| JQL search unavailable or errors | No duplicate detection and no read-back | Stop. Create nothing. Both of the safeguards that make this skill re-runnable depend on it. |
| Epic key does not resolve | Typo, or no permission on that project | Stop. Ask for the correct key. Do not create an epic to hold the stories. |

## Fields

| Failure | What it means | Do |
| --- | --- | --- |
| `parent` not on the Story create screen | Epic membership cannot be written | Stop. Do not fall back to `Epic Link`. Name the field and list the available names. A batch of orphans reports as success and is expensive to find. |
| Story Points unresolvable, and some candidate has an estimate | The number would be accepted and silently dropped | Stop. Name the field and list the available names. |
| Story Points unresolvable, and nobody estimated | Nothing to write | Not a failure. File without it and say so. |
| Missing estimate on a candidate | Nothing to write, and nothing to invent | File the story unsized and name it in the report. The empty field is the record. Never block the batch, never assign a number. |
| No team field on the project | Not every project has one | Not a failure. Say so and file without it. Do not substitute a label. |
| Team answer not among the allowed values | A typo, or a team that was renamed | List the allowed values and ask again. Do not send it: Jira accepts the payload and drops the value. |
| Priority marked required on the create screen, with no default | One of only two cases where a Priority is sent, the other being one the user named | Stop and ask which value, then send the answer. Never choose one to get past the screen. With a default, it is not a stop: Jira fills it. |
| Read-back Priority is the project default, such as BAPP's `TBD` | Jira applied the project's default because nothing was sent | Not a failure. Report it as the project default, not as set by the run. |
| A supplied option value is not among the allowed values | Same class of problem as the team answer | Stop and list the allowed values. |

## The batch itself

| Failure | What it means | Do |
| --- | --- | --- |
| A summary is over its cap, or the text carries banned punctuation, a padding pattern, or a placeholder | The text is not ready to file | Rewrite before the first create call. One edit per issue afterwards costs 30 calls and an edit history that reads as careless. |
| Dependency cycle, or a reference to a candidate not in the batch | A decomposition error, not a link error | Report the whole path and ask which arrow is backwards. The stories may be created; the links may not. |
| Create errors mid-batch | Varies, and an ambiguous timeout may already have created the issue | Stop the batch. Report created and not-created separately. Do not retry blind. |
| A leftover `[[dep:` in a created description | Pass two did not finish | Report it as an unfinished run, not as a note. Then finish pass two. |
| Read-back contradicts the writes | The batch is wrong and is about to be reported as right | Do not report done. Go to the remediation procedure, which SKILL.md links. |
