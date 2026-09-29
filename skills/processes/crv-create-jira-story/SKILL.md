---
name: crv-create-jira-story
description: >-
  Files Jira Stories under a parent Epic through the Atlassian MCP, searching
  for duplicates by JQL before creating anything, writing descriptions that
  carry what the implementer needs and do not read as generated text, asking who the work is assigned to,
  resolving the epic-membership and Story Points fields from the target project
  at run time, creating the native dependency links, and reading every created
  story back to prove what was stored. Use when someone wants to create, file,
  or raise a story or ticket in Jira under an existing epic, including "file a
  Jira story", "raise a ticket for this", or breaking a spec into stories. To
  create the parent epic itself, use crv-create-jira-epic. Not for editing,
  commenting on, or transitioning an issue that already exists.
license: Apache-2.0
compatibility: >-
  Requires an Atlassian MCP server with create-issue, read-issue, edit-issue,
  JQL search, issue-link, and project create-metadata capabilities, plus
  add-comment when estimates are bulk-approved, authenticated by the harness.
  Requires Python 3.9+ for the bundled setup script. Stores no credentials.
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# Create a Jira story

Filing stories in bulk is where a well-meaning agent does real damage, in three
ways.

The loud way: re-run a request that created eight stories and you have sixteen,
half of them subtly different, and no way to tell which set the team has already
groomed. So **search before you create, every time.**

The quiet way is worse. Twenty-nine stories are created, every call returns
success, and none of them is attached to the epic. Nothing in the transcript says
so. So **read every write back and report what was stored, never what was sent.**

The third way is the one the team notices first. Every story is padded with the
shapes that mark generated text, and carries a Priority nobody chose and an
estimate nobody agreed to. It reads as though no person owned the ticket,
because none did. So **cut the padding, not the content, and invent no
values.**

## Execution

**Delegate to a subagent. Do not run this in the main session.** Splitting a
spec, reading create-metadata, and checking each candidate against the epic
accumulates intermediate reasoning the user does not need once the stories
exist.

**Model tier: `economy`**, the cheapest model that can follow instructions and
call tools. **State it, do not ask about it.** One line, then start work:

> Running `crv-create-jira-story` in a subagent on the economy tier.

Honour a tier the user names in the session or in the project's agent
configuration, and say which one you used.

**Never silently escalate.** If the subagent is out of its depth, stop and say
so rather than re-running on a bigger model.

**Pass the subagent what it cannot see:** the spec or notes, and every epic key,
browse URL, or epic filed earlier in this session that the conversation
mentions. It proposes one of those rather than asking cold.

**It hands back exactly once before creating anything**, with the drafted batch
and every question at once, and resumes with the answers. The main session shows
that message to the user and passes the answers back, never answering for them.
[references/checkpoint.md](references/checkpoint.md).

**A subagent may not inherit the Atlassian MCP server**, which looks exactly
like one nobody installed. Tools absent here but present in the spawning
session: say it is tool inheritance, create nothing, and hand back for an
inline re-run, the sanctioned fallback. Same with no subagent mechanism:
[references/jira-setup.md](references/jira-setup.md#absent-in-a-subagent-present-in-the-main-session).

## What this produces

One or more Jira Stories under a named parent Epic, and a report. Specifically:

- Each Story is a child of the named epic, with a markdown description built
  from [assets/story-description.md.template](assets/story-description.md.template)
  and written to [references/issue-writing.md](references/issue-writing.md),
  complete enough to pick up without the conversation.
- The team, Priority and estimate a person chose, or the documented default,
  and no value the run invented. Every dependency as a native link.
- A report with every candidate as created, skipped as a duplicate, or refused
  naming what was missing, quoted from the read-back. A candidate silently
  absent from it is a bug.

## When not to use this

- Creating the parent epic, use `crv-create-jira-epic`.
- Editing, commenting on, or transitioning an existing issue: do it directly.
  This skill only creates, and repairs what it created.
- Deciding how to split the work: do that first, with the people who own it.
  This skill files a decomposition; it does not sanction one.

## Step 0. Preflight, and stop if it fails

Before gathering anything, because discovering at create time that the tenant is
unreachable wastes the whole decomposition.

1. **Atlassian MCP server available?** Enumerate available tools and match on
   capability, not name. Needed here: create, read and edit an issue, search by
   JQL, read project create-metadata, list and create issue links. Adding a
   comment is needed only if estimates are bulk-approved, in Step 7.

   Say which of three it is: absent here but present in the spawning session
   (tool inheritance: hand back for an inline re-run), absent everywhere
   ([jira-setup.md § 1](references/jira-setup.md#1-the-atlassian-mcp-server)),
   or present with every call unauthorised (OAuth incomplete). **JQL search and
   read-issue are not optional**: Steps 3 and 8 are what make a re-run safe and
   a report true.

2. **Site and project known?**

   ```bash
   python3 <this skill's directory>/scripts/jira_setup.py --check
   ```

   The path is the skill's, not the user's repository's: from there a bare
   `scripts/jira_setup.py` exits `2`, which reads as a usage error. Every
   `jira_setup.py` command here takes the same prefix. Exit `0` configured,
   `1` names the missing keys, `4` the file is corrupt, a different fix.

   Exit `1` is a stop only for a **guess**: two candidate sites, no project key
   anywhere, a project name that is not a key. A value is **supplied** if the
   user named it in this session, including in a pasted URL or issue key, or if
   exactly one site is accessible. Use it, say where it came from, and give the
   `--set ... --confirm` command that records it.

**On a stop, create nothing** and report which check failed. Do not attempt the
call to see what happens.

## Step 1. Read the parent epic

Every story needs a parent Epic key. If the request names none, look for one the
conversation mentioned: a key, a browse URL, or an epic filed earlier in this
session. Read it and propose it at the checkpoint, with its summary and status.
If there is none, the checkpoint asks for the key. Never file orphans, and never
create an epic to hold them: that is `crv-create-jira-epic`, and a decision the
user makes knowingly.

Read the epic. It gives you the project to file into, the context the
descriptions should not restate, and confirmation the key exists. A key that
does not resolve is a typo worth catching before eight create calls fail.

## Step 2. Build each candidate

Input may be structured, against
[assets/story_input.schema.json](assets/story_input.schema.json) and rendered as
[references/structured-input.md](references/structured-input.md) says, or
conversational. The rules below apply either way, including to a supplied
`description_markdown`, which replaces rendering, not checking.

Render [assets/story-description.md.template](assets/story-description.md.template)
for each. Four sections are required: an unheaded opening, then the Acceptance
criteria, Test plan and Dependencies headings. Drop an optional heading rather
than filling it, and link the epic rather than restating it. The description
**opens with the user story, with no heading**: Jira already labels the field.
With no real person in the sentence, open with a one-sentence goal instead:
"As a developer, I want the service split" is padding shaped like a story.

**Complete, not padded.** There is no word cap. Say everything the implementer
needs that the code and the epic do not, including the files, contracts and
examples, and nothing else. More than about seven acceptance criteria usually
means two stories: say so and offer the split, but if the user wants one story,
file one and drop no criterion to shorten it.

**Tasks only when the source has steps.** Criteria say what is true when the
story is done; tasks say how to get there. Take them from what the person or the
spec listed, never generate them, and drop the heading when there are none. A
step that needs its own owner stays, and is named in the report as a likely
sub-task.

Rewrite every summary to the title rules **here**, before Step 3 compares it
against Jira. Titles and prose follow [references/issue-writing.md](references/issue-writing.md),
which names the patterns that read as generated and the rewrite for each. They
are checked in Step 4, before anything is created, because fixing them
afterwards is one edit call per issue.

Cross-references between candidates use the `[[dep:<n>]]` placeholder, never a
plan-local number or a guessed key:
[references/dependency-links.md](references/dependency-links.md).

## Step 3. Search for duplicates before creating anything

Search the epic for existing children of **every** issue type, since a Task
with the same summary is as much a duplicate as a Story:

```text
parent = <EPIC-KEY>
```

If the search errors, **stop**: proceeding without duplicate detection is the
failure this step exists to prevent.

Compare both the summary **as it will be filed** and the summary as given,
normalising case and whitespace. A re-run's raw long title never equals the
80-character rewrite already in Jira, and an older story may be unrewritten.
When either form matches, **skip that candidate** and record the existing key.
Do not update the existing story: the caller asked to create, and rewriting a story
someone has already groomed is a worse surprise than a skip.

A summary close but not equal is a near-match: create it, and name the key it
resembles. Merging two stories takes a minute; recovering one never filed does
not.

## Step 4. Validate the batch, before the first create

Per candidate:

- Run the text checklist in
  [issue-writing.md § Checking a batch before it is filed](references/issue-writing.md#checking-a-batch-before-it-is-filed).
  Any hit is a rewrite before the create call, not a note in the report.
- Story points, **if supplied**, is an integer of at least 1. Reject `0`,
  negatives, and non-integers, but not values off a Fibonacci ladder. A
  candidate with no estimate is valid.
- Parent key matches `^[A-Z][A-Z0-9_]{1,9}-[1-9][0-9]*$`.
- Every `[[dep:<n>]]` placeholder names a candidate in this batch.

Then validate the dependency graph across the batch: no self-references, no
cycles of any length, and no reference to work outside the batch that names
neither a real key nor a real team. A cycle is a decomposition error: the
checkpoint shows its path and asks which arrow is backwards. Procedure:
[references/dependency-links.md](references/dependency-links.md).

**Story points are never required, asked for, or invented.** Sizing belongs
to the team, in grooming. An estimate the user supplied is used as given. With
none, the field stays empty and nothing mentions it: not a question at the
checkpoint, not a list in the report, not a line in the description. Only if
the user asks for proposed estimates does the checkpoint show a table of them;
an approved number then gets a provenance comment in Step 7.

## Step 5. Resolve fields

Read create-metadata once for the project and issue type, and reuse it for the
whole batch. Resolve every field by name. Full procedure and matching rules:
[references/field-resolution.md](references/field-resolution.md).

Four of them decide whether this batch is usable:

- **Epic membership.** Always `parent`, in either project style. Ignore a
  legacy `Epic Link` field if the screen also offers one. If `parent` is not on
  the screen, stop: the wrong field means a batch of orphans that reports as
  success.
- **Team.** `Assigned Team(s)`, `Team`, or `Squad`, with its allowed values.
  Asked at the checkpoint, once for the whole batch: a spec does not say who
  will do the work, and a recorded default does not replace the question.
  [field-resolution.md § Team](references/field-resolution.md#team-ask-the-user-do-not-assume).
- **Story Points.** `Story Points`, or `Story point estimate` on some tenants.
  Resolve it whenever it exists, since the read-back checks that no story got a
  number nobody gave. Its absence stops the run only when there is an estimate
  to write.
- **Priority: never choose one.** Send nothing unless the user names a value.
  Read the project default, if any: Jira stores it anyway (on BAPP, an option
  named `TBD`), so the read-back expects it and the report names it as the
  project's. Required with no default: ask at the checkpoint.
  [field-resolution.md § Priority](references/field-resolution.md#fields-that-must-be-resolved-by-name-every-run).

A field Jira accepts and ignores is worse than a refusal, so an unresolvable
field with a value to write is a stop. A resolved field with nothing to write is
a line in the report. Apply the recorded `project_defaults` from
`jira_setup.py --show` and list each as a default, except the team, which is
asked, and Priority, which is ignored.

## Step 6. Check in once, then create (pass one)

Hand back the checkpoint: the draft table and every question that applies, each
with its default. Nothing is created before the answers come back. What goes in
it, the default for each unanswered question, and how to resume:
[references/checkpoint.md](references/checkpoint.md). On resuming, re-run the
Step 3 search immediately before the first create.

Then create the stories one at a time, sending descriptions as **markdown**, never
hand-built ADF. Keep a map of plan-local number to returned key as you go.
Placeholders stay in the text during this pass, because a key cannot be cited
before it is allocated.

If a create call errors, stop creating, and do not retry blind: an ambiguous
timeout may already have created the issue. Still run pass two **among the
stories that were created**, and report the run as unfinished. A re-run may
backfill a placeholder an earlier run left, the one exception to leaving
existing stories alone. Details:
[references/failure-modes.md](references/failure-modes.md#the-batch-itself).

## Step 7. Backfill references and create the links, pass two

1. Replace every `[[dep:<n>]]` placeholder with the real key, one edit call per
   story that has references.
2. Create the native issue links for every dependency the batch asserts. Prose
   under a Dependencies heading drives nothing: blocked-by views, dependency
   reports, roadmap arrows and automation all read native links.
3. Direction is easy to get backwards. For a `Blocks` link the **inward issue
   is the blocker**. Create the first link, read one of the two issues back,
   confirm the rendered relationship says what you meant, then create the rest.
4. For every bulk-approved estimate, add one comment: "<n> points proposed
   during filing and approved as part of a batch on <today, YYYY-MM-DD>, not
   groomed with the team." A comment is dated history, so it stays true after
   re-sizing. No comment capability: say so, and the report carries it.

Link types and what not to link:
[references/dependency-links.md](references/dependency-links.md).

## Step 8. Read the batch back and verify it

The create responses are not evidence. Read back **exactly the keys this run
created**, not the whole epic, which may hold stories other people filed.

```text
key in (<every key this run created>) ORDER BY created ASC
```

Name the fields you assert on, since a search returns a short default set:
summary, issuetype, parent, priority, description, issuelinks, and the resolved
team and story-point fields. Page through a large batch. Comments need a read of
each story that got one, asking for the comment field.

Then check:

| Assertion | Failure it catches |
| --- | --- |
| Every created key comes back | A create that reported success and stored nothing |
| Every row's `parent` is `<EPIC-KEY>` | The batch of orphans this step exists to catch |
| Every estimated row holds its number, and no other row has one | A field Jira accepted and ignored, or a number nobody agreed to |
| Every row holds the team the user named, or none if they said `none` | A team field Jira accepted and dropped |
| Priority is the user's named value, or the project default, or unset where there is no default. No `Priority:` line | A value the run chose, or a recorded default that got sent |
| Every applied organisation default is present | Same, for the other recorded defaults |
| Point total summed from these rows, over the ones that have a number | A total reported from the plan is arithmetic nobody checked |
| Every bulk-approved estimate has its provenance comment | A proposed number that now looks groomed |
| No `[[dep:` remains in any description | An unfinished pass two |
| Each asserted dependency has a link, in the right direction | A dependency that exists only as prose |

**Quote the read-back values in the report**, not the intended ones. A failed
assertion means the run is not done: remediate, and say what was wrong before
what was fixed.

## Step 9. Report

A table, one row per candidate: summary, outcome (`created` / `skipped` /
`refused`), key, note. Then:

- when any story has points, the total summed from the Step 8 read-back
- the epic key and URL
- the team applied and where it came from: the user's answer, the recorded
  default, or `none` at their request
- every estimate proposed and bulk-approved rather than groomed, if the user
  asked for proposals
- every task that looks like it needs its own owner or estimate, as a likely
  sub-task
- every value inferred, defaulted, or fuzzy-matched rather than supplied,
  including each checkpoint question that took its default
- every link created, with its direction
- anything still outstanding

If any candidate was refused, say what is needed to file it. A report that ends
without naming the remaining work reads as completion.

## When a step fails

Look it up, do not decide:
[references/failure-modes.md](references/failure-modes.md). Every failure is one
of **stop** and create nothing further, **not a failure** so file without the
value and say so, or **ask** at the checkpoint. **Stop and report, never
improvise.** A partial batch reported accurately is recoverable; one reported
as success is not.

## When the batch succeeded incorrectly

The issues exist and the values are wrong. Read what is stored first, patch in
place because the keys are already in use, propose the patch as one table for
one approval, and never delete without explicit authorisation:
[references/remediation.md](references/remediation.md).

## Validation

Before reporting done:

- [ ] Preflight passed, or nothing was created.
- [ ] The checkpoint was handed back, and answered, before the first create.
- [ ] A duplicate search ran against the epic before the first create, and
      again on resuming.
- [ ] The issue-writing checklist ran on every candidate: summary cap, no em
      or en dash, no padding pattern, an unheaded opening user story or goal,
      the three required headings, no `TBD`, no `Priority:` line.
- [ ] No acceptance criterion or constraint from the source was dropped, no
      task was invented, and no estimate was invented.
- [ ] Every Step 8 assertion held, **quoted from the read-back**, not from the
      create calls.
- [ ] Every candidate appears in the report as created, skipped, or refused.
- [ ] No pre-existing story was modified, except to backfill a `[[dep:`
      placeholder an earlier run of this skill left behind.

Fix and re-check anything that fails. Never report completion with a known
failure, and never report a check as passed that you did not run: a box ticked
without the query behind it is what made the last wrong batch look right.

## References

- [references/jira-setup.md](references/jira-setup.md): prerequisites, configuration, troubleshooting
- [references/field-resolution.md](references/field-resolution.md): fields by name, epic, Priority, team
- [references/issue-writing.md](references/issue-writing.md): titles, padding patterns, rewrites
- [references/dependency-links.md](references/dependency-links.md): two passes, cycles, link direction
- [references/checkpoint.md](references/checkpoint.md): the one hand-back, defaults, resuming
- [references/structured-input.md](references/structured-input.md): where each input field goes
- [references/failure-modes.md](references/failure-modes.md): stop, file anyway, or ask
- [references/remediation.md](references/remediation.md): fixing a batch created wrongly
- `scripts/jira_setup.py`: site, project and field defaults; no credentials
- `assets/`: the description template, and the optional input schema with an example
