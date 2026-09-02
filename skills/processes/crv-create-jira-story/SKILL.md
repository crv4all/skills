---
name: crv-create-jira-story
description: >-
  Files Jira Stories under a parent Epic through the Atlassian MCP, searching
  for duplicates by JQL before creating anything, requiring a story-point
  estimate on every story, resolving the Story Points and epic-membership fields
  from the target project at run time, creating the native dependency links, and
  reading every created story back to prove what was stored. Use when someone
  wants to create, file, or raise a story or ticket in Jira under an existing
  epic, including "file a Jira story", "raise a ticket for this", or breaking a
  spec into stories. To create the parent epic itself, use crv-create-jira-epic.
  Not for editing, commenting on, or transitioning an issue that already exists.
license: Apache-2.0
compatibility: >-
  Requires an Atlassian MCP server with create-issue, read-issue, edit-issue,
  JQL search, issue-link, and project create-metadata capabilities, authenticated
  by the harness. Requires Python 3.9+ for the bundled setup script. Stores no
  credentials.
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# Create a Jira story

Filing stories in bulk is where a well-meaning agent does real damage, in two
ways.

The loud way: re-run a request that created eight stories and you have sixteen,
half of them subtly different, and no way to tell which set the team has already
groomed. So **search before you create, every time.**

The quiet way is worse. Twenty-nine stories are created, every call returns
success, and none of them is attached to the epic. Nothing in the transcript says
so. So **read every write back and report what was stored, never what was sent.**

## Execution

**Delegate to a subagent. Do not run this in the main session.** Splitting a
spec into stories, reading create-metadata, and checking each candidate against
the epic accumulates a large amount of intermediate reasoning the user does not
need once the stories exist.

**Model tier: `economy`**, the cheapest model that can follow instructions and
call tools.

**The tier question belongs to whoever is about to spawn.** Work out which of the
two roles you are in before asking anything:

- **Orchestrator**, invoked by the user, no subagent spawned yet. Ask once,
  before any work starts:

  > Running `crv-create-jira-story` in a subagent on the **economy** tier. Reply
  > `balanced` or `frontier` to run it on a stronger model, or continue to accept
  > the default.

  Then spawn, and state the agreed tier in the prompt you hand over.
- **Executor**, already running as the spawned subagent, or invoked with a tier
  already stated in the session or in the project's agent configuration. The
  question has been answered. **Do not ask it again.** Start at Step 0.

Asking twice costs two round trips and teaches the user that the prompt is noise.

**Never silently escalate.** If the subagent is out of its depth, stop and say
so rather than re-running on a bigger model.

If the harness has no subagent mechanism, say so plainly and run inline.

## What this produces

One or more Jira Stories under a named parent Epic, and a report. Specifically:

- Each Story has a markdown description carrying the required sections of
  [assets/story-description.md.template](assets/story-description.md.template),
  written to the rules in [references/issue-writing.md](references/issue-writing.md).
- Each Story is a child of the named epic, verified by reading it back.
- Each Story has a story-point estimate. No exceptions.
- Every field the project marks required, and every recorded organisation
  default, is populated.
- Every dependency the decomposition asserts exists as a native issue link, not
  only as prose.
- A per-candidate report: created with its key, or skipped as a duplicate naming
  the existing key, or refused naming what was missing. Totals are summed from
  the read-back, not from the plan.

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
   capability, not name. Needed here: create an issue, read an issue, edit an
   issue, search by JQL, read project create-metadata, list and create issue
   links.

   If MCP tools are **absent**: the server is not installed or not enabled. Say
   so explicitly and point to [references/jira-setup.md#1-the-atlassian-mcp-server](references/jira-setup.md#1-the-atlassian-mcp-server).

   If MCP tools are **present but every call returns unauthorised**: OAuth is not
   complete. Say so explicitly and point to the authentication instructions.

   **JQL search and read-issue are not optional.** Without search, Step 3 cannot
   run, and Step 3 is the reason this skill is safe to invoke twice. Without
   read-issue, Step 8 cannot run, and Step 8 is the only thing standing between a
   wrong batch and a report that calls it done.

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
descriptions should not restate, and confirmation the key exists. An epic key
that does not resolve is a typo worth catching now rather than after eight
create calls fail.

## Step 2. Build each candidate

Structured input may be supplied against
[assets/story_input.schema.json](assets/story_input.schema.json), with
[assets/story_input.example.json](assets/story_input.example.json) as a worked
one. Otherwise build candidates conversationally; the rules below apply either
way, since the schema cannot check a conversation.

Render [assets/story-description.md.template](assets/story-description.md.template)
for each. Link the epic rather than restating it: a copy of the epic in eight
descriptions is eight copies to go stale.

Titles and prose follow [references/issue-writing.md](references/issue-writing.md).
The two rules broken most often: a summary over 80 characters, and an em dash
anywhere in the text. Both are checked in Step 4, before anything is created,
because fixing them afterwards is one edit call per issue and an edit history
that suggests the batch was filed carelessly.

Cross-references between candidates use the `[[dep:<n>]]` placeholder, never a
plan-local number like "story 4" and never a guessed key. Why, and how the
placeholders get resolved: [references/dependency-links.md](references/dependency-links.md).

## Step 3. Search for duplicates before creating anything

Search the epic for existing children, once, before the first create:

```text
parent = <EPIC-KEY> AND issuetype = Story
```

If `parent` is unsupported on this tenant, fall back to `"Epic Link" =
<EPIC-KEY>`. If neither works, **stop**. Proceeding without duplicate detection
is precisely the failure mode this step exists to prevent.

Compare each candidate summary against the existing ones, normalising case and
surrounding whitespace. On a match, **skip that candidate** and record the
existing key. Do not update the existing story: the caller asked to create, and
silently rewriting a story someone has already groomed is a worse surprise than
a skip.

Report near-matches rather than acting on them. When a summary is close but not
equal, create it and say in the report which existing key it resembles. A human
can merge two stories in a minute, but cannot recover one that was never filed.

## Step 4. Validate the batch, before the first create

Per candidate:

- Summary non-empty, at most 255 characters for Jira, at most 80 characters and
  12 words by house rule. A title that cannot be shortened without losing
  meaning is usually two stories.
- Summary and description contain no em dash, en dash, or arrow, and no `#`
  followed by a digit used as a reference to another candidate.
- Story points is an integer of at least 1. **Required.** Reject `0`, negatives,
  and non-integers. Do not reject values that are off a Fibonacci ladder: teams
  use their own scales, and a roll-up of several items lands on no ladder at all.
- Parent key matches `^[A-Z][A-Z0-9_]{1,9}-[1-9][0-9]*$`.
- Every `[[dep:<n>]]` placeholder names a candidate that is in this batch.

Then, across the whole batch, validate the dependency graph: no self-references,
no cycles of any length, and no reference to work outside the batch that names
neither a real key nor a real team. A cycle is a decomposition error, so report
the path and ask which arrow is backwards. Procedure:
[references/dependency-links.md](references/dependency-links.md).

**Estimates.** If an estimate is missing, ask. Do not silently assign one: an
invented estimate is indistinguishable from an agreed one once it is in Jira.
For a batch, asking per story does not scale, so use the sanctioned path instead:
propose every estimate in one table, take one approval for the table, and record
on each story that the number was proposed and bulk-approved rather than groomed.
The template's "Estimate note" section exists for exactly that, and the report
repeats it. An unrecorded provenance is the part that does the damage later.

## Step 5. Resolve fields

Read create-metadata once for the project and issue type, and reuse it for the
whole batch. Resolve every field by name. Full procedure and matching rules:
[references/field-resolution.md](references/field-resolution.md).

Three of them decide whether this batch is usable:

- **Epic membership.** `parent` in a team-managed project, an `Epic Link` custom
  field in a company-managed one. Read create-metadata to see which exists;
  never assume a `customfield_` number. Wrong field means a batch of orphans that
  reports as success.
- **Story Points.** `Story Points` on most tenants, `Story point estimate` on
  some.
- **Organisation defaults.** `python3 scripts/jira_setup.py --show` reports
  `project_defaults` for this project: fields the team expects on every issue
  even though the create screen does not require them, such as a team field.
  Apply them at create time and list them in the report as defaults. Not doing
  this is what turns into one patch call per issue afterwards.

**If epic membership or Story Points cannot be resolved, stop before creating
anything.** Both produce stories that look fine and cannot be planned against.

## Step 6. Create, pass one

Create the stories one at a time, sending descriptions as **markdown**, never
hand-built ADF. Keep a map of plan-local number to returned key as you go.

Placeholders stay in the text during this pass. That is deliberate: a key cannot
be cited before it is allocated.

If a create call errors, stop the batch, report which stories were created and
which were not, and do not retry blind. An ambiguous timeout may already have
created the issue.

## Step 7. Backfill references and create the links, pass two

1. Replace every `[[dep:<n>]]` placeholder with the real key, one edit call per
   story that has references.
2. Create the native issue links for every dependency the batch asserts. Prose
   under a Dependencies heading drives nothing: blocked-by views, dependency
   reports, roadmap arrows and automation all read native links.
3. Direction matters and is easy to get backwards. For a `Blocks` link the
   **inward issue is the blocker**. Create the first link, read one of the two
   issues back, confirm the rendered relationship says what you meant, and only
   then create the rest.

Details, including link types and what not to link:
[references/dependency-links.md](references/dependency-links.md).

## Step 8. Read the batch back and verify it

The create responses are not evidence. Run one JQL query and assert against what
comes back:

```text
parent = <EPIC-KEY> AND issuetype = Story ORDER BY created ASC
```

Use the `"Epic Link" = <EPIC-KEY>` form on a company-managed project. Then check:

| Assertion | Failure it catches |
| --- | --- |
| Row count equals the number created | A create that reported success and stored nothing |
| Every created key is in the result | The batch of orphans this step exists to catch |
| Every row has a story-point value | A field identifier Jira accepted and ignored |
| Every applied organisation default is present | Same, for the team field |
| Point total is summed from these rows | A total reported from the plan is arithmetic nobody checked |
| No `[[dep:` remains in any description | An unfinished pass two |
| Each asserted dependency has a link, in the right direction | A dependency that exists only as prose |

**Quote the read-back values in the report.** Not the intended ones. If any
assertion fails, the run is not done: go to the remediation procedure below and
say plainly what was wrong before saying what was fixed.

## Step 9. Report

A table, one row per candidate: summary, outcome (`created` / `skipped` /
`refused`), key, note. Then:

- totals, summed from the Step 8 read-back
- the epic key and URL
- every value that was inferred, defaulted, or fuzzy-matched rather than supplied
- every estimate that was proposed and bulk-approved rather than groomed
- every link created, with its direction
- anything still outstanding

If any candidate was refused, say what is needed to file it. A report that ends
without naming the remaining work reads as completion.

## When a step fails

| Failure | What it means | Do |
| --- | --- | --- |
| No Jira tools in tool list | MCP server not installed or not enabled for this harness | Stop. Point at [jira-setup.md § 1](references/jira-setup.md#1-the-atlassian-mcp-server). |
| Jira tools present, every call returns unauthorised | OAuth flow incomplete or grant expired | Stop. Point at [jira-setup.md § Troubleshooting](references/jira-setup.md#troubleshooting). |
| `jira_setup.py --check` exits `1` | Site or project not recorded | Derive only from a value the user supplied, or a single accessible site. Otherwise stop and give the `--set … --confirm` command. |
| `jira_setup.py --check` exits `4` | Configuration corrupt | Stop. Name the path; it needs inspection, not re-running setup. |
| JQL search unavailable or errors | Duplicate detection and read-back impossible | Stop. Create nothing. |
| Epic key does not resolve | Typo, or no permission | Stop. Ask for the correct key. |
| Story Points or epic-membership field unresolvable | Field absent under every known name | Stop. Name the field and the available field names. |
| Missing estimate | Candidate incomplete | Ask. For a batch, propose a table and take one approval. |
| Dependency cycle or unknown reference | Decomposition error | Report the path, ask which arrow is backwards. Stories may be created; links may not. |
| Create errors mid-batch | Varies | Stop the batch. Report created and not-created separately. Do not retry blind. |
| Read-back contradicts the writes | The batch is wrong and reported as right | Do not report done. Go to remediation. |

**Stop and report, never improvise** on a failure. A partial batch that is
reported accurately is recoverable; one that is reported as success is not.

## When the batch succeeded incorrectly

Different problem, different rules. The issues exist, the calls returned success,
and the values are wrong. Establish what is actually stored before touching
anything, patch in place by default because the keys are already in use
elsewhere, propose the whole patch as one table for one approval, and never
delete without explicit authorisation. Full procedure:
[references/remediation.md](references/remediation.md).

## Validation

Before reporting done:

- [ ] Preflight passed, or nothing was created.
- [ ] A JQL search ran against the epic before the first create.
- [ ] Every summary is at most 80 characters, and no summary or description
      contains an em dash or an en dash.
- [ ] Every created story has an integer estimate of at least 1, and every
      bulk-approved estimate says so on the issue.
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
- [references/remediation.md](references/remediation.md): fixing a batch that was created wrongly
- `scripts/jira_setup.py`: records site, project, and per-project field defaults; stores no credentials
- `assets/story-description.md.template`: the description sections
- `assets/story_input.schema.json`: optional structured input, with `assets/story_input.example.json`
