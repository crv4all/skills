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
  add-comment when estimates are bulk-approved, authenticated by the harness. Requires Python 3.9+ for the bundled setup script. Stores no
  credentials.
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

A stated default the user can override beats a question they have to clear
before any work starts. Honour a tier they name in the session or in the
project's agent configuration, and say which one you used.

**Never silently escalate.** If the subagent is out of its depth, stop and say
so rather than re-running on a bigger model.

**A subagent may not inherit the Atlassian MCP server**, and that looks exactly
like a server nobody installed. If the tools are absent here but the spawning
session had them, this is tool inheritance and not setup: say so, create
nothing, and hand back for an inline re-run. Running inline is the sanctioned
fallback, not a rule being broken. Same if the harness has no subagent
mechanism. Wording and reasoning:
[references/jira-setup.md](references/jira-setup.md#absent-in-a-subagent-present-in-the-main-session).

## What this produces

One or more Jira Stories under a named parent Epic, and a report. Specifically:

- Each Story has a markdown description opening with its user story or goal,
  with no heading above it, and carrying the four required sections of
  [assets/story-description.md.template](assets/story-description.md.template),
  complete enough to pick up without the conversation, and written to
  [references/issue-writing.md](references/issue-writing.md).
- Each Story is a child of the named epic, verified by reading it back.
- Each Story carries the team the user named, or none because they said so.
- No Story has a Priority the run chose, and no description a placeholder value.
- Every required field is populated. Story points are set where a number was
  supplied or agreed, and left unset otherwise.
- Every dependency the decomposition asserts exists as a native issue link, not
  only as prose.
- A per-candidate report: created with its key, skipped as a duplicate naming
  the existing key, or refused naming what was missing. Totals come from the
  read-back, not the plan.

Every candidate appears in the report with one of those three outcomes. A
candidate that is silently absent is a bug.

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

   Absent here but present in the spawning session: tool inheritance, so hand
   back for an inline re-run rather than sending the user to setup. Absent
   everywhere: point at [references/jira-setup.md#1-the-atlassian-mcp-server](references/jira-setup.md#1-the-atlassian-mcp-server).
   Present but every call unauthorised: OAuth is incomplete, so point at the
   authentication instructions. Say which of the three it is.

   **JQL search and read-issue are not optional.** Step 3 is the reason this
   skill is safe to invoke twice, and Step 8 is the only thing standing between
   a wrong batch and a report that calls it done. Neither runs without them.

2. **Site and project known?**

   ```bash
   python3 scripts/jira_setup.py --check
   ```

   Exit `0` configured. Exit `1` names the missing keys. Exit `4` the
   configuration file is corrupt, a different problem with a different fix.

   Exit `1` is not automatically a stop. A value is **supplied** if the user named
   it in this session, including inside a board or issue URL they pasted, or if
   the accessible-sites capability returns exactly one site. Use it, say where it
   came from, and give the `--set ... --confirm` command that records it. Anything
   less certain is a **guess**: two candidate sites, no project key anywhere, a
   project name that is not a key. Guesses stop the run.

**On a stop, create nothing** and report which check failed. Do not attempt the
call to see what happens.

## Step 1. Read the parent epic

Every story needs a parent Epic key. If none was given, ask; do not file
orphans, and do not create an epic to hold them. That is `crv-create-jira-epic`,
and it is a decision the user should make knowingly.

Read the epic. It gives you the project to file into, the context the
descriptions should not restate, and confirmation the key exists. A key that
does not resolve is a typo worth catching before eight create calls fail.

## Step 2. Build each candidate

Structured input may be supplied against
[assets/story_input.schema.json](assets/story_input.schema.json), with
[assets/story_input.example.json](assets/story_input.example.json) as a worked
one, and rendered field by field as
[references/structured-input.md](references/structured-input.md) says. Otherwise build candidates conversationally; the rules below apply either
way, since the schema cannot check a conversation. They also apply to a
supplied `description_markdown`, which replaces rendering, not checking.

Render [assets/story-description.md.template](assets/story-description.md.template)
for each. Four headings are required and the rest are optional: drop an optional
heading rather than filling it, and link the epic rather than restating it. A
copy of the epic in eight descriptions is eight copies to go stale. The
description **opens with the user story, with no heading**: Jira already labels
the field, and "As a / I want / So that" names itself. When no real person is in
the sentence, open with a one-sentence goal instead, also unheaded: "As a
developer, I want the service split" is padding shaped like a user story.

**Complete, not padded.** There is no word cap. Say everything the implementer
needs that the code and the epic do not, including the files, contracts and
examples, and nothing else. More than about seven acceptance criteria usually
means two stories: say so and offer the split, but if the user wants one story,
file one and drop no criterion to shorten it.

**Tasks only when the source has steps.** Acceptance criteria say what is true
when the story is done. Tasks say how to get there, as a `- [ ]` checklist the
implementer ticks off. Take them from what the person or the spec actually
listed, and drop the heading when they listed none: a task list the run made up
is a plan nobody agreed to. Delete a task that restates a criterion. A step big
enough to need its own owner or estimate stays in the list but is named in the
report as a likely sub-task, because this skill does not create sub-tasks.

Rewrite every summary to those rules **here**, before Step 3 compares it against
Jira. Titles and prose follow [references/issue-writing.md](references/issue-writing.md),
which names the patterns that make text read as generated and gives the rewrite
for each. The four rules broken most often: a summary over 80 characters, an em
dash anywhere, a description padded with those patterns, and a `TBD` where the
honest answer is "Not yet decided" or an unset field. All four are checked in
Step 4,
before anything is created, because fixing them afterwards is one edit call per
issue and an edit history that suggests the batch was filed carelessly.

Cross-references between candidates use the `[[dep:<n>]]` placeholder, never a
plan-local number like "story 4" and never a guessed key. Why, and how the
placeholders get resolved: [references/dependency-links.md](references/dependency-links.md).

## Step 3. Search for duplicates before creating anything

Search the epic for existing children of **every** issue type, once, before the
first create. A Task with the same summary is as much a duplicate as a Story,
and a candidate filed with a non-Story `issue_type` is invisible to a query that
filters on Story:

```text
parent = <EPIC-KEY>
```

If the search errors, **stop**. Proceeding without duplicate detection
is precisely the failure mode this step exists to prevent.

Compare against the summary **as it will be filed**, after the Step 2 title
rules, and also against the summary as it was given. A re-run brings the raw
120-character title again, and it never equals the 80-character rewrite already
in Jira, so comparing only the raw text files the same story twice. Comparing
only the rewrite misses a story an earlier run filed unrewritten.

Normalise case and whitespace. When either form matches, **skip that candidate** and record the existing key. Do
not update the existing story: the caller asked to create, and rewriting a story
someone has already groomed is a worse surprise than a skip.

Report near-matches rather than acting on them. When a summary is close but not
equal, create it and name the key it resembles. A human can merge two stories in
a minute, but cannot recover one that was never filed.

## Step 4. Validate the batch, before the first create

Per candidate:

- Run the text checklist in
  [issue-writing.md § Checking a batch before it is filed](references/issue-writing.md#checking-a-batch-before-it-is-filed).
  It covers the summary cap, the banned punctuation, the padding patterns, and
  the placeholder and Priority rules. Any hit is a rewrite before the create call,
  not a note in the report.
- Story points, **if supplied**, is an integer of at least 1. Reject `0`,
  negatives, and non-integers, but not values off a Fibonacci ladder. A
  candidate with no estimate is valid.
- Parent key matches `^[A-Z][A-Z0-9_]{1,9}-[1-9][0-9]*$`.
- Every `[[dep:<n>]]` placeholder names a candidate in this batch.

Then validate the dependency graph across the batch: no self-references, no
cycles of any length, and no reference to work outside the batch that names
neither a real key nor a real team. A cycle is a decomposition error, so report
the path and ask which arrow is backwards. Procedure:
[references/dependency-links.md](references/dependency-links.md).

**Estimates are optional and never invented.** Sizing belongs to the team, in
grooming, with the people who will do the work.

- An estimate the user supplied is used as given.
- No estimate: **file the story with the field unset**, and name it in the
  report. Do not block the batch, do not assign a number, and do not write
  "filed unsized" into the description. The empty field is the record, and an
  `is EMPTY` query on it is a grooming list that stays right after grooming. A
  line in the description is wrong the moment someone sizes the story.
- You may offer once, for the whole batch: one table of proposed numbers, one
  approval. On approval, each story gets a comment recording that its number
  was proposed and bulk-approved rather than groomed, in Step 7. On a decline
  or no answer, file unsized.

An unsized story is a five-second fix in grooming. An invented number is
indistinguishable from an agreed one the moment it is in Jira, and it gets summed
into a sprint commitment.

## Step 5. Resolve fields

Read create-metadata once for the project and issue type, and reuse it for the
whole batch. Resolve every field by name. Full procedure and matching rules:
[references/field-resolution.md](references/field-resolution.md).

Four of them decide whether this batch is usable:

- **Epic membership.** Always `parent`, in either project style. Ignore a
  legacy `Epic Link` field if the screen also offers one. If `parent` is not on
  the screen, stop: the wrong field means a batch of orphans that reports as
  success.
- **Team.** `Assigned Team(s)`, `Team`, or `Squad`. **Ask the user, once, for
  the whole batch**, offering the allowed values and the recorded default:

  > `Assigned Team(s)` for this batch: Platform, Empower, Insight. Recorded
  > default is Platform. Reply with one or more, or `none` to leave it unset.

  This is the one field the agent cannot derive, because a spec does not say who
  will do the work, and the one the organisation notices is missing. `none` is a
  valid answer, reported as the user's choice. Why a recorded default does not
  replace the question:
  [field-resolution.md § Team](references/field-resolution.md#team-ask-the-user-do-not-assume).
- **Story Points.** `Story Points`, or `Story point estimate` on some tenants.
  Resolve it only if some candidate has an estimate.
- **Priority: never choose one.** Not from a recorded default and not inferred
  from the spec. Priority is groomed against the whole backlog. Send nothing
  unless the user names a value, validated against the allowed values and
  reported as supplied. Where the project has a Priority default (BAPP's is an
  option named `TBD`), Jira stores it anyway: that is the project's value, not
  the run's, so the read-back expects it and the report names it as the
  default. Required with no default: stop and ask.
  [field-resolution.md § Priority](references/field-resolution.md#fields-that-must-be-resolved-by-name-every-run).

**If epic membership cannot be resolved, stop before creating anything**, and
likewise Story Points when there is an estimate to write. A field Jira accepts
and ignores is worse than a refusal. A field that resolved and has no value to
write is not a stop, it is a line in the report.

`jira_setup.py --show` reports this project's `project_defaults`: values the team
expects on every issue that the create screen does not require. Apply them and
list each as a default. Two carve-outs: the team field is asked rather than
defaulted, and a recorded Priority default is ignored.

## Step 6. Create, pass one

Create the stories one at a time, sending descriptions as **markdown**, never
hand-built ADF. Keep a map of plan-local number to returned key as you go.
Placeholders stay in the text during this pass, because a key cannot be cited
before it is allocated.

If a create call errors, stop the batch, report which stories were created and
which were not, and do not retry blind. An ambiguous timeout may already have
created the issue.

## Step 7. Backfill references and create the links, pass two

1. Replace every `[[dep:<n>]]` placeholder with the real key, one edit call per
   story that has references.
2. Create the native issue links for every dependency the batch asserts. Prose
   under a Dependencies heading drives nothing: blocked-by views, dependency
   reports, roadmap arrows and automation all read native links.
3. Direction is easy to get backwards. For a `Blocks` link the **inward issue
   is the blocker**. Create the first link, read one of the two issues back,
   confirm the rendered relationship says what you meant, then create the rest.
4. For every bulk-approved estimate, add one comment to that story: "3 points
   proposed during filing and approved as part of a batch on 2026-09-29, not
   groomed with the team." A comment is dated history, so it stays true after
   the story is re-sized, where a line in the description would not. If the
   server has no comment capability, say so and carry the provenance in the
   report only.

Link types and what not to link:
[references/dependency-links.md](references/dependency-links.md).

## Step 8. Read the batch back and verify it

The create responses are not evidence. Read back **exactly the keys this run
created**, not the whole epic: the epic may already hold stories other people
filed or this run skipped, and asserting on those fails a correct run.

```text
key in (<every key this run created>) ORDER BY created ASC
```

A search returns a short default set of fields, so name the ones you assert on:
summary, issuetype, parent, priority, description, issuelinks, and the resolved
team and story-point fields. Page through the results when the batch is bigger
than one page. Comments are not in search results: read each story that got a
provenance comment on its own, asking for the comment field.

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

**Quote the read-back values in the report**, not the intended ones. If any
assertion fails the run is not done: go to remediation below, and say what was
wrong before saying what was fixed.

## Step 9. Report

A table, one row per candidate: summary, outcome (`created` / `skipped` /
`refused`), key, note. Then:

- totals from the Step 8 read-back, counting unsized stories separately rather
  than folding them in as zero
- the epic key and URL
- the team applied and where it came from: the user's answer, the recorded
  default, or `none` at their request
- every story filed unsized, so grooming has the list
- every estimate proposed and bulk-approved rather than groomed
- every task that looks like it needs its own owner or estimate, as a likely
  sub-task
- every value inferred, defaulted, or fuzzy-matched rather than supplied
- every link created, with its direction
- anything still outstanding

If any candidate was refused, say what is needed to file it. A report that ends
without naming the remaining work reads as completion.

## When a step fails

Look it up, do not decide. The full table, with the reason behind each row, is
[references/failure-modes.md](references/failure-modes.md). Every failure lands
in one of three outcomes, and they are not interchangeable: **stop** and create
nothing further, **not a failure** so file without the value and say so, or
**ask** one question and continue.

These are the stops, and none of them is negotiable:

- No JQL search, so no duplicate detection and no read-back.
- Epic key does not resolve, or the epic-membership field cannot be resolved.
- Story Points unresolvable while some candidate has an estimate to write.
- Configuration corrupt, or site and project only guessable.
- A create call errored mid-batch. Report created and not-created separately and
  do not retry blind.

**Stop and report, never improvise.** A partial batch that is reported
accurately is recoverable; one that is reported as success is not.

## When the batch succeeded incorrectly

Different problem, different rules. The issues exist and the values are wrong.
Establish what is stored before touching anything, patch in place because the
keys are already in use elsewhere, propose the patch as one table for one
approval, and never delete without explicit authorisation. Procedure:
[references/remediation.md](references/remediation.md).

## Validation

Before reporting done:

- [ ] Preflight passed, or nothing was created.
- [ ] A JQL search ran against the epic before the first create.
- [ ] The issue-writing checklist ran on every candidate: summary cap, no em
      or en dash, no padding pattern, an unheaded opening user story or goal,
      the three required headings, no `TBD`, no `Priority:` line.
- [ ] No acceptance criterion or constraint from the source was dropped to
      shorten a description.
- [ ] Every task came from the source. None was invented, and none restates
      an acceptance criterion.
- [ ] No story has a Priority in the read-back other than one the user named
      or the project default, and the report says which.
- [ ] No estimate was invented, and every unsized story is named in the report.
- [ ] Every bulk-approved estimate carries its provenance comment, or the report
      says the server could not add one.
- [ ] The team field holds what the user gave, or is unset because they said so,
      and the report says which.
- [ ] Every created story is a child of the named epic **according to the Step 8
      read-back**, not according to the create call.
- [ ] The reported point total was summed from the read-back rows.
- [ ] No `[[dep:` placeholder survives in any description.
- [ ] Every asserted dependency has a native link, in a direction that was
      verified once against a read-back.
- [ ] Descriptions were sent as markdown, not ADF.
- [ ] Every candidate appears in the report as created, skipped, or refused.
- [ ] No pre-existing story was modified.

Fix and re-check anything that fails. Never report completion with a known
failure, and never report a check as passed that you did not run. A checklist
item ticked without the query behind it is worse than no checklist, because it
is what made the last wrong batch look right.

## References

- [references/jira-setup.md](references/jira-setup.md): MCP prerequisites, configuration, project defaults, exit codes, troubleshooting
- [references/field-resolution.md](references/field-resolution.md): resolving fields by name, epic membership, verifying the write
- [references/issue-writing.md](references/issue-writing.md): title length, banned punctuation, vocabulary, rewrites
- [references/dependency-links.md](references/dependency-links.md): two-pass creation, cycle validation, native link direction
- [references/structured-input.md](references/structured-input.md): where each structured-input field goes, and what a missing one does
- [references/failure-modes.md](references/failure-modes.md): every failure, what it means, and which of stop, file-anyway or ask it takes
- [references/remediation.md](references/remediation.md): fixing a batch that was created wrongly
- `scripts/jira_setup.py`: records site, project, and per-project field defaults; stores no credentials
- `assets/story-description.md.template`: the description sections
- `assets/story_input.schema.json`: optional structured input, with `assets/story_input.example.json`
