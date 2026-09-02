---
name: crv-create-jira-epic
description: >-
  Files a Jira Epic through the Atlassian MCP, resolving the required fields of
  the target project at run time instead of assuming custom-field IDs from any
  particular tenant, rendering the description as markdown from a section
  template, and reading the created epic back to prove what was stored. Use when
  someone wants to create, file, or raise an epic in Jira, including "create a
  Jira epic", "open an epic for this work", or turning an approved spec into an
  epic. For the stories that live under an epic, use crv-create-jira-story
  instead. Not for editing, commenting on, or transitioning an issue that already
  exists.
license: Apache-2.0
compatibility: >-
  Requires an Atlassian MCP server with create-issue, read-issue, JQL search, and
  project create-metadata capabilities, authenticated by the harness. Requires
  Python 3.9+ for the bundled setup script. Stores no credentials.
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# Create a Jira epic

Filing an epic is easy to do and easy to do wrong. Three failures matter:
creating it in a tenant the skill guessed at, creating it missing a field the
project requires, and creating it with a description that reads as generated
text. The first two look like success in the transcript and become someone
else's problem later. The third tells the team nobody owned the ticket.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Gathering the
epic content, reading create-metadata, and negotiating missing fields fills a
conversation with material the user does not need once the epic exists.

**Model tier: `economy`**, the cheapest model that can follow instructions and
call tools.

**The tier question belongs to whoever is about to spawn.** Establish which role
you are in first:

- **Orchestrator**, invoked by the user, no subagent spawned yet. Ask once,
  before any work starts:

  > Running `crv-create-jira-epic` in a subagent on the **economy** tier. Reply
  > `balanced` or `frontier` to run it on a stronger model, or continue to accept
  > the default.

  Then spawn, stating the agreed tier in the prompt you hand over.
- **Executor**, already running as the spawned subagent, or invoked with a tier
  already stated in the session or in the project's agent configuration. The
  question has been answered. **Do not ask it again.** Start at Step 0.

**Never silently escalate.** If the subagent is out of its depth, stop and say
so rather than re-running on a bigger model.

If the harness has no subagent mechanism, say so plainly and run inline.

## What this produces

One Jira Epic, and a report naming it. Specifically:

- An Epic in the target project, with a markdown description carrying every
  section of [assets/epic-description.md.template](assets/epic-description.md.template)
  in that order, written to the rules in
  [references/issue-writing.md](references/issue-writing.md).
- Every field the project marks required on the create screen, and every recorded
  organisation default, populated.
- A report giving the issue key, its browse URL, the project and issue type used,
  the values read back from the created epic, and any field whose value was
  inferred rather than supplied.

Or: nothing created, and a report saying exactly what was missing. Those are the
only two outcomes. There is no partial success.

## When not to use this

- Stories under an epic, use `crv-create-jira-story`.
- Editing, commenting on, or transitioning an issue that already exists: do it
  directly. This skill only creates.
- A single ticket with no epic above it: file it directly rather than inventing
  an epic to hold it.
- Deciding *whether* the work is worth doing: that is a conversation, not a
  ticket, and filing the epic first quietly forecloses it.

## Step 0. Preflight, and stop if it fails

Both checks run before any content is gathered, because discovering at create
time that the tenant is unreachable wastes the whole interview. They fail
differently and are fixed differently, so check them in order and report what is
actually blocking.

1. **Atlassian MCP server available?** Enumerate the available tools and match on
   capability, not on name. Needed here: create an issue, read an issue, search by
   JQL, read project create-metadata, list visible projects.

   If MCP tools are **absent**: the server is not installed or not enabled. Say so
   explicitly and point to [references/jira-setup.md#1-the-atlassian-mcp-server](references/jira-setup.md#1-the-atlassian-mcp-server).

   If MCP tools are **present but every call returns unauthorised**: OAuth is not
   complete. Say so explicitly and point to the authentication instructions.

   Read-issue is required, not optional: Step 4 verifies the epic by reading it
   back, and a create call that cannot be verified is a create call whose result
   is unknown.

2. **Site and project known?**

   ```bash
   python3 scripts/jira_setup.py --check
   ```

   Exit `0` means configured. Exit `1` names the missing keys. Exit `4` means the
   configuration file is corrupt, which is a different problem with a different
   fix. Point at [references/jira-setup.md#2-machine-configuration](references/jira-setup.md#2-machine-configuration).

   Exit `1` is not automatically a stop. A value is **supplied** if the user named
   it in this session, including inside a board or issue URL they pasted, or if
   the accessible-sites capability returns exactly one site. Use it, say where it
   came from, and give the `--set ... --confirm` command that records it for next
   time. Anything less certain is a **guess**: two candidate sites, no project key
   anywhere, a project name rather than a key. Guesses stop the run.

**On a stop, create nothing.** Do not proceed on a default project key you were
not given, and do not try the call to see what happens. An epic filed into the
wrong project is far more expensive than a refusal, and much harder to notice.

## Step 1. Gather the content

Render [assets/epic-description.md.template](assets/epic-description.md.template).
Ask for what is missing, in one batch rather than one question at a time.

You need a summary and enough for each section of the template. A section with
nothing to say gets "None known" or "Not yet decided" explicitly. Never delete a
heading to hide that it was unanswered: the empty section is the signal that the
question was asked, and deleting it destroys that signal.

The summary is a noun phrase naming the outcome, at most 80 characters and 12
words. Prose and title rules, including the punctuation this house does not use:
[references/issue-writing.md](references/issue-writing.md).

Two things never go in an epic description:

- **A count of its children.** "The 29 Phase-1 stories" is wrong the moment a
  story is added or split, and nobody re-reads the epic to fix it. The child
  links are the source of truth and they maintain themselves.
- **Invented success criteria or dependencies.** A fabricated criterion is one
  nobody agreed to and everybody later cites. Leaving it open is the honest
  state, and the template has words for it.

## Step 2. Resolve the project and its fields

Determine the project: an explicit instruction wins, otherwise the recorded
default from `jira_setup.py --show`. State which one you used. A default that is
never mentioned is a default nobody notices is wrong.

Then read create-metadata for that project and the Epic issue type, and resolve
every field by name. Also apply the `project_defaults` recorded for this project,
which are the fields the organisation expects on every issue even when the create
screen does not require them. Full procedure, matching rules, and what counts as
unresolved: [references/field-resolution.md](references/field-resolution.md).

**If a required field cannot be filled, stop and say which one.** Do not create
the epic and mention the gap afterwards.

## Step 3. Create

Call the create-issue capability with the resolved field identifiers, sending the
description as **markdown**, using whatever content-format parameter the server
exposes. Do not hand-build Atlassian Document Format: a subtly malformed node
yields an epic whose description renders blank, which is a failure that reports
itself as success.

Create exactly once. If the call errors, do not retry blind. An ambiguous timeout
may already have created the issue, and a retry is how a project ends up with two
epics nobody meant to file. Search for the summary first, and only create again if
it is genuinely absent.

## Step 4. Read it back, then report

The create response proves an issue exists. It proves nothing about what is in
it: Jira accepts a field identifier it does not recognise on that screen by
ignoring it, and returns success. So read the epic back and check the stored
values before reporting anything.

| Assertion | Failure it catches |
| --- | --- |
| The key exists and is of the Epic issue type | A create that landed as the wrong type |
| It is in the intended project | A default project nobody stated |
| Every template heading is present in the stored description | A truncated or blank render |
| Every applied default holds the value sent | A field identifier Jira ignored |

Then report: the issue key, the browse URL built from the recorded site, the
project and issue type **as read back**, every field whose value you inferred or
defaulted rather than were given, and anything left as "Not yet decided".

Then say what to do next: stories under this epic are `crv-create-jira-story`.

## When a step fails

| Failure | What it means | Do |
| --- | --- | --- |
| No Jira tools in tool list | MCP server not installed or not enabled for this harness | Stop. Point at [jira-setup.md § 1](references/jira-setup.md#1-the-atlassian-mcp-server) for installation and enablement. |
| Jira tools present, every call returns unauthorised | OAuth flow incomplete or grant expired | Stop. Point at [jira-setup.md § Troubleshooting](references/jira-setup.md#troubleshooting) to re-run server authentication. |
| `jira_setup.py --check` exits `1` | Site or project not recorded | Derive only from a value the user supplied, or a single accessible site. Otherwise stop and give the exact `--set … --confirm` command. |
| `jira_setup.py --check` exits `4` | Configuration file corrupt | Stop. Name the path; it needs inspection, not re-running setup. |
| Project not visible | Wrong key, or no permission | Stop. List the visible projects. |
| Required field unresolvable | Screen expects something not supplied | Stop. Name the field and the available field names. |
| Create call errors | Varies | Search for the summary before any retry. Report the error text verbatim. |
| Read-back contradicts the write | The epic exists and is wrong | Do not report done. Patch in place and verify again. |

**Stop and report, never improvise.** Improvisation is what this skill exists to
prevent, and a half-created epic is the one outcome nobody can act on.

If the epic was created and is wrong, that is a different situation from a
failure: establish what is actually stored, patch in place rather than refiling,
and never delete without explicit authorisation.
[references/remediation.md](references/remediation.md) has the procedure.

## Validation

Before reporting done:

- [ ] Preflight passed, or nothing was created.
- [ ] The description carries every template heading, in order, and says so from
      the read-back rather than from the payload.
- [ ] Every field the project marks required has a value.
- [ ] The summary is at most 80 characters, and neither summary nor description
      contains an em dash or an en dash.
- [ ] The description states no count of child stories.
- [ ] The description was sent as markdown, not ADF.
- [ ] Exactly one epic exists for this request, verified rather than assumed if
      any call errored.
- [ ] The report names the issue key, the URL, and every inferred or defaulted
      value.

If a check fails, fix it and re-check. Never report completion with a known
failure, and never report a check as passed that you did not run.

## References

- [references/jira-setup.md](references/jira-setup.md): MCP prerequisites, configuration, project defaults, exit codes, troubleshooting
- [references/field-resolution.md](references/field-resolution.md): resolving fields by name, and verifying the write
- [references/issue-writing.md](references/issue-writing.md): title length, banned punctuation, vocabulary, rewrites
- [references/remediation.md](references/remediation.md): fixing an issue that was created wrongly
- `scripts/jira_setup.py`: records site, project, and per-project field defaults; stores no credentials
- `assets/epic-description.md.template`: the description sections, in order
