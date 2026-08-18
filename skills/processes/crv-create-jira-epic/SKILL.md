---
name: crv-create-jira-epic
description: >-
  Files a Jira Epic through the Atlassian MCP, resolving the required fields of
  the target project at run time instead of assuming custom-field IDs from any
  particular tenant, and rendering the description as markdown from a section
  template. Use when someone wants to create, file, or raise an epic in Jira —
  including "create a Jira epic", "open an epic for this work", or turning an
  approved spec into an epic. For the stories that live under an epic, use
  crv-create-jira-story instead. Not for editing, commenting on, or
  transitioning an issue that already exists.
license: Apache-2.0
compatibility: >-
  Requires an Atlassian MCP server with create-issue and project create-metadata
  capabilities, authenticated by the harness. Requires Python 3.9+ for the
  bundled setup script. Stores no credentials.
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# Create a Jira epic

Filing an epic is easy to do and easy to do wrong. The two failures that matter
are creating it in a tenant the skill guessed at, and creating it missing a
field the project requires — both of which look like success in the transcript
and become someone else's problem later.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Gathering the
epic content, reading create-metadata, and negotiating missing fields fills a
conversation with material the user does not need once the epic exists.

**Model tier: `economy`** — the cheapest model that can follow instructions and
call tools. Before spawning the subagent, ask once:

> Running `crv-create-jira-epic` in a subagent on the **economy** tier. Reply
> `balanced` or `frontier` to run it on a stronger model, or continue to accept
> the default.

Ask once per invocation, before any work starts. Skip the question only when the
user has already stated a tier preference in this session or in the project's
agent configuration.

**Never silently escalate.** If the subagent is out of its depth, stop and say
so rather than re-running on a bigger model.

If the harness has no subagent mechanism, say so plainly and run inline.

## What this produces

One Jira Epic, and a report naming it. Specifically:

- An Epic in the target project, with a markdown description carrying every
  section of [assets/epic-description.md.template](assets/epic-description.md.template)
  in that order.
- Every field the project marks required on the create screen, populated.
- A report giving the issue key, its browse URL, the project and issue type used,
  and any field whose value was inferred rather than supplied.

Or: nothing created, and a report saying exactly what was missing. Those are the
only two outcomes. There is no partial success.

## When not to use this

- Stories under an epic → `crv-create-jira-story`.
- Editing, commenting on, or transitioning an issue that already exists → do it
  directly; this skill only creates.
- A single ticket with no epic above it → file it directly rather than inventing
  an epic to hold it.
- Deciding *whether* the work is worth doing → that is a conversation, not a
  ticket, and filing the epic first quietly forecloses it.

## Step 0 — Preflight, and stop if it fails

Both checks run before any content is gathered, because discovering at create
time that the tenant is unreachable wastes the whole interview.

1. **Atlassian MCP tools present?** Enumerate the available tools and match on
   capability, not on name. Needed here: create an issue, read project
   create-metadata, list visible projects.
2. **Machine configured?**

   ```bash
   python3 scripts/jira_setup.py --check
   ```

   Exit `0` means configured. Exit `1` names the missing keys. Exit `4` means the
   configuration file is corrupt, which is a different problem with a different
   fix.

**If either check fails, stop.** Report what is missing, point at
[references/jira-setup.md](references/jira-setup.md), and create nothing. Do not
proceed on a default project key, do not guess a site, and do not try the call to
see what happens. An epic filed into the wrong project is far more expensive than
a refusal, and much harder to notice.

## Step 1 — Gather the content

Render [assets/epic-description.md.template](assets/epic-description.md.template).
Ask for what is missing, in one batch rather than one question at a time.

You need a summary — one line, under 255 characters, naming the outcome rather
than the activity — and enough for each section of the template. A section with
nothing to say gets "None known" or "Not yet decided" explicitly. Never delete a
heading to hide that it was unanswered: the empty section is the signal that the
question was asked, and deleting it destroys that signal.

Do not invent success criteria or dependencies. Inventing them is worse than
leaving them open, because a fabricated criterion is one nobody agreed to and
everybody later cites.

## Step 2 — Resolve the project and its fields

Determine the project: an explicit instruction wins; otherwise the recorded
default from `jira_setup.py --show`. State which one you used — a default that is
never mentioned is a default nobody notices is wrong.

Then read create-metadata for that project and the Epic issue type, and resolve
every field by name. Full procedure, including the matching rules and what counts
as unresolved: [references/field-resolution.md](references/field-resolution.md).

**If a required field cannot be filled, stop and say which one.** Do not create
the epic and mention the gap afterwards.

## Step 3 — Create

Call the create-issue capability with the resolved field identifiers, sending the
description as **markdown**, using whatever content-format parameter the server
exposes. Do not hand-build Atlassian Document Format: a subtly malformed node
yields an epic whose description renders blank, which is a failure that reports
itself as success.

Create exactly once. If the call errors, do not retry blind — an ambiguous
timeout may already have created the issue, and a retry is how a project ends up
with two epics nobody meant to file. Search for the summary first, and only
create again if it is genuinely absent.

## Step 4 — Report

Give the issue key, the browse URL built from the recorded site, the project and
issue type, and every field whose value you inferred rather than were given.

Then say what to do next: stories under this epic are `crv-create-jira-story`.

## When a step fails

| Failure | What it means | Do |
| --- | --- | --- |
| No Jira tools available | MCP server absent or unauthenticated | Stop. Point at `references/jira-setup.md`. |
| `jira_setup.py --check` exits `1` | Machine never configured | Stop. Give the exact `--set … --confirm` command. |
| `jira_setup.py --check` exits `4` | Configuration file corrupt | Stop. Name the path; it needs inspection, not re-running setup. |
| Project not visible | Wrong key, or no permission | Stop. List the visible projects. |
| Required field unresolvable | Screen expects something not supplied | Stop. Name the field and the available field names. |
| Create call errors | Varies | Search for the summary before any retry. Report the error text verbatim. |

The common thread: **stop and report, never improvise.** Improvisation is what
this skill exists to prevent, and a half-created epic is the one outcome nobody
can act on.

## Validation

Before reporting done:

- [ ] Preflight passed, or nothing was created.
- [ ] The description carries every template heading, in order.
- [ ] Every field the project marks required has a value.
- [ ] The description was sent as markdown, not ADF.
- [ ] Exactly one epic exists for this request — verified, not assumed, if any
      call errored.
- [ ] The report names the issue key, the URL, and every inferred value.

If a check fails, fix it and re-check. Never report completion with a known
failure, and never report a check as passed that you did not run.

## References

- [references/jira-setup.md](references/jira-setup.md) — MCP prerequisites, first-run configuration, exit codes, troubleshooting
- [references/field-resolution.md](references/field-resolution.md) — resolving field identifiers by name, and why stopping beats guessing
- `scripts/jira_setup.py` — records site and project outside any repository; stores no credentials
- `assets/epic-description.md.template` — the description sections, in order
