---
name: crv-create-jira-story
description: >-
  Files Jira Stories under a parent Epic through the Atlassian MCP, searching
  for duplicates by JQL before creating anything, requiring a story-point
  estimate on every story, and resolving the Story Points field from the target
  project at run time. Use when someone wants to create, file, or raise a story
  or ticket in Jira under an existing epic — including "file a Jira story",
  "raise a ticket for this", or breaking a spec into stories. To create the
  parent epic itself, use crv-create-jira-epic. Not for editing, commenting on,
  or transitioning an issue that already exists.
license: Apache-2.0
compatibility: >-
  Requires an Atlassian MCP server with create-issue, read-issue, JQL search,
  and project create-metadata capabilities, authenticated by the harness.
  Requires Python 3.9+ for the bundled setup script. Stores no credentials.
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# Create a Jira story

Filing stories in bulk is where a well-meaning agent does real damage. Re-run a
request that created eight stories and you have sixteen, half of them subtly
different, and no way to tell which set the team has already groomed. Deleting
them is manual. So: **search before you create, every time.**

## Execution

**Delegate to a subagent. Do not run this in the main session.** Splitting a
spec into stories, reading create-metadata, and checking each candidate against
the epic accumulates a large amount of intermediate reasoning the user does not
need once the stories exist.

**Model tier: `economy`** — the cheapest model that can follow instructions and
call tools. Before spawning the subagent, ask once:

> Running `crv-create-jira-story` in a subagent on the **economy** tier. Reply
> `balanced` or `frontier` to run it on a stronger model, or continue to accept
> the default.

Ask once per invocation, before any work starts. Skip the question only when the
user has already stated a tier preference in this session or in the project's
agent configuration.

**Never silently escalate.** If the subagent is out of its depth, stop and say
so rather than re-running on a bigger model.

If the harness has no subagent mechanism, say so plainly and run inline.

## What this produces

One or more Jira Stories under a named parent Epic, and a report. Specifically:

- Each Story has a markdown description carrying the required sections of
  [assets/story-description.md.template](assets/story-description.md.template).
- Each Story has a story-point estimate. No exceptions.
- Every field the project marks required is populated.
- A per-candidate report: created with its key, or skipped as a duplicate naming
  the existing key, or refused naming what was missing.

Every candidate appears in the report with one of those three outcomes. A
candidate that is silently absent is a bug.

## When not to use this

- Creating the parent epic → `crv-create-jira-epic`.
- Editing, commenting on, or transitioning an existing issue → do it directly;
  this skill only creates.
- Deciding how to split the work → do that first, with the people who own it.
  This skill files a decomposition; it does not sanction one.

## Step 0 — Preflight, and stop if it fails

Before gathering anything, because discovering at create time that the tenant is
unreachable wastes the whole decomposition.

1. **Atlassian MCP tools present?** Enumerate available tools and match on
   capability, not name. Needed here: create an issue, read an issue, search by
   JQL, read project create-metadata.
2. **Machine configured?**

   ```bash
   python3 scripts/jira_setup.py --check
   ```

   Exit `0` configured · `1` names the missing keys · `4` the configuration file
   is corrupt, a different problem with a different fix.

**If either fails, stop.** Report what is missing, point at
[references/jira-setup.md](references/jira-setup.md), and create nothing. Do not
fall back to a guessed project, and do not attempt the call to see what happens.

**JQL search is not optional.** If the search capability is unavailable, stop —
without it Step 3 cannot run, and Step 3 is the reason this skill is safe to
invoke twice.

## Step 1 — Read the parent epic

Every story needs a parent Epic key. If none was given, ask; do not file
orphans, and do not create an epic to hold them — that is
`crv-create-jira-epic`, and it is a decision the user should make knowingly.

Read the epic. It gives you the project to file into, the context the
descriptions should not restate, and confirmation the key exists. An epic key
that does not resolve is a typo worth catching now rather than after eight
create calls fail.

## Step 2 — Build each candidate

Structured input may be supplied against
[assets/story_input.schema.json](assets/story_input.schema.json) — see
[assets/story_input.example.json](assets/story_input.example.json) for a worked
one. Otherwise build candidates conversationally; the rules below apply either
way, since the schema cannot check a conversation.

Render [assets/story-description.md.template](assets/story-description.md.template)
for each. Link the epic rather than restating it: a copy of the epic in eight
descriptions is eight copies to go stale.

## Step 3 — Search for duplicates before creating anything

Search the epic for existing children, once, before the first create:

```text
parent = <EPIC-KEY> AND issuetype = Story
```

If `parent` is unsupported on this tenant, fall back to `"Epic Link" =
<EPIC-KEY>`. If neither works, **stop** — proceeding without duplicate detection
is precisely the failure mode this step exists to prevent.

Compare each candidate summary against the existing ones, normalising case and
surrounding whitespace. On a match, **skip that candidate** and record the
existing key. Do not update the existing story: the caller asked to create, and
silently rewriting a story someone has already groomed is a worse surprise than
a skip.

Report near-matches rather than acting on them. When a summary is close but not
equal, create it and say in the report which existing key it resembles — a human
can merge two stories in a minute, but cannot recover one that was never filed.

## Step 4 — Validate each candidate

Check before creating, so a bad candidate does not leave a half-filed batch:

- Summary is non-empty and at most 255 characters. Jira rejects longer ones.
- Story points is an integer of at least 1. **Required.** Reject `0`, negatives,
  and non-integers.
- Do not reject values that are off a Fibonacci ladder. Teams use their own
  scales, and a roll-up of several items lands on no ladder at all.
- Parent key matches `^[A-Z][A-Z0-9_]{1,9}-[1-9][0-9]*$`.

A story with no estimate is the failure this skill exists to prevent: it looks
complete on the board and cannot be planned against. If an estimate is missing,
ask for it. Do not assign one — an invented estimate is indistinguishable from an
agreed one once it is in Jira.

## Step 5 — Resolve fields, then create

Read create-metadata once for the project and issue type, and reuse it for the
whole batch. Resolve every field by name, Story Points included — it is
`Story Points` on most tenants and `Story point estimate` on some. Procedure and
matching rules: [references/field-resolution.md](references/field-resolution.md).

**If Story Points cannot be resolved, stop before creating anything.** Creating
the batch without estimates produces stories that look fine and are unplannable.

Create the stories one at a time, sending descriptions as **markdown**, never
hand-built ADF. If a create call errors, stop the batch, report which stories
were created and which were not, and do not retry blind — an ambiguous timeout
may already have created the issue.

## Step 6 — Report

A table, one row per candidate: summary · outcome (`created` / `skipped` /
`refused`) · key · note. Then the totals, the epic key and URL, and any field
value that was inferred rather than supplied.

If any candidate was refused, say what is needed to file it. A report that ends
without naming the remaining work reads as completion.

## When a step fails

| Failure | What it means | Do |
| --- | --- | --- |
| No Jira tools available | MCP absent or unauthenticated | Stop. Point at `references/jira-setup.md`. |
| `jira_setup.py --check` exits `1` | Never configured | Stop. Give the exact `--set … --confirm` command. |
| `jira_setup.py --check` exits `4` | Configuration corrupt | Stop. Name the path; it needs inspection, not re-running setup. |
| JQL search unavailable or errors | Duplicate detection impossible | Stop. Create nothing. |
| Epic key does not resolve | Typo, or no permission | Stop. Ask for the correct key. |
| Story Points unresolvable | Field absent under both names | Stop. Name the field and the available field names. |
| Missing estimate | Candidate incomplete | Refuse that candidate, keep the rest, report it. |
| Create errors mid-batch | Varies | Stop the batch. Report created and not-created separately. Do not retry blind. |

The common thread: **stop and report, never improvise.** A partial batch that is
reported accurately is recoverable; one that is reported as success is not.

## Validation

Before reporting done:

- [ ] Preflight passed, or nothing was created.
- [ ] A JQL search ran against the epic before the first create.
- [ ] Every created story has an integer estimate of at least 1.
- [ ] Every created story is a child of the named epic.
- [ ] Descriptions were sent as markdown, not ADF.
- [ ] Every candidate appears in the report as created, skipped, or refused.
- [ ] No existing story was modified.

If a check fails, fix it and re-check. Never report completion with a known
failure, and never report a check as passed that you did not run.

## References

- [references/jira-setup.md](references/jira-setup.md) — MCP prerequisites, first-run configuration, exit codes, troubleshooting
- [references/field-resolution.md](references/field-resolution.md) — resolving field identifiers by name, and why stopping beats guessing
- `scripts/jira_setup.py` — records site and project outside any repository; stores no credentials
- `assets/story-description.md.template` — the description sections
- `assets/story_input.schema.json` — optional structured input, with `assets/story_input.example.json`
