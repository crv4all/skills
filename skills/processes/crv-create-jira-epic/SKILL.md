---
name: crv-create-jira-epic
description: >-
  Files a Jira Epic through the Atlassian MCP, resolving the required fields of
  the target project at run time instead of assuming custom-field IDs from any
  particular tenant, rendering the description as markdown from a section
  template, asking which team the work belongs to, and reading the created epic
  back to prove what was stored. Use when someone wants to create, file, or
  raise an epic in Jira, including "create a Jira epic", "open an epic for this
  work", or turning an approved spec into an epic. For the stories that live
  under an epic, use crv-create-jira-story instead. Not for editing, commenting
  on, or transitioning an issue that already exists.
license: Apache-2.0
compatibility: >-
  Requires an Atlassian MCP server with create-issue, read-issue, edit-issue,
  JQL search, and project create-metadata capabilities, authenticated by the
  harness. Requires
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
project requires, and creating it padded and carrying values nobody chose. The first two look like success in the transcript and become someone
else's problem later. The third tells the team nobody owned the ticket.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Gathering the
epic content, reading create-metadata, and negotiating missing fields fills a
conversation with material the user does not need once the epic exists.

**Model tier: `economy`**, the cheapest model that can follow instructions and
call tools. **State it, do not ask about it.** One line, then start work:

> Running `crv-create-jira-epic` in a subagent on the economy tier.

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

One Jira Epic, and a report naming it. Specifically:

- An Epic in the target project, with a markdown description carrying the five
  required sections of
  [assets/epic-description.md.template](assets/epic-description.md.template) in
  order and written to [references/issue-writing.md](references/issue-writing.md).
- The team the user named, or none because they said so.
- No Priority the run chose: the user's named value, or the project's own
  default, reported as such. No placeholder value in the text.
- Every field the project marks required on the create screen, and every recorded
  organisation default, populated.
- A report giving the issue key, its browse URL, the project and issue type used,
  the values read back from the created epic, and any field whose value was
  inferred rather than supplied.

Or: nothing created because the epic already exists, and a report naming its
key. Or: nothing created, and a report saying exactly what was missing. Those
are the only three outcomes. There is no partial success.

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
   capability, not on name. Needed here: create, read and edit an issue, search
   by JQL, read project create-metadata, list visible projects. Edit is for the
   one case where the read-back contradicts the write, and the fix is a patch
   in place: without it, a wrong epic can only be reported, not corrected.

   If MCP tools are **absent and the spawning session had them**: tool
   inheritance. Hand back for an inline re-run, not to setup.

   If MCP tools are **absent everywhere**: the server is not installed or not
   enabled. Say so and point to [references/jira-setup.md#1-the-atlassian-mcp-server](references/jira-setup.md#1-the-atlassian-mcp-server).

   If MCP tools are **present but every call returns unauthorised**: OAuth is not
   complete. Say so explicitly and point to the authentication instructions.

   Read-issue and JQL search are required, not optional. Step 3 searches for an
   existing epic before creating one, and without that a re-run files a second
   copy. Step 4 verifies the epic by reading it back, and a create call that
   cannot be verified is a create call whose result is unknown.

2. **Site and project known?**

   ```bash
   python3 <this skill's directory>/scripts/jira_setup.py --check
   ```

   The path is relative to this skill, not to the user's repository, which is
   where the shell usually is. Run from there as `scripts/jira_setup.py`, it
   fails with Python's exit `2`, which reads as a usage error rather than a
   missing file. Every `jira_setup.py` command in this skill and its references
   takes the same prefix.

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

You need a summary and enough for the five required sections. Dependencies,
Technical notes and Links are optional: drop an optional heading rather than
filling it. A required section with nothing to say gets "None known" or "Not yet
decided" in words. Never delete a required heading to hide that it was
unanswered, and never write `TBD` in it: the first destroys the signal that the
question was asked, the second reads as an oversight nobody comes back to.

**No word cap, and no padding.** An epic is read to decide whether work belongs
in it. Give that decision the outcome and the boundary in full, and leave out
the narrative around them.

The summary is a noun phrase naming the outcome, at most 80 characters and 12
words. Prose and title rules, the patterns that mark generated text, and the
rewrite for each: [references/issue-writing.md](references/issue-writing.md).

Three things never go in an epic description:

- **A count of its children.** "The 29 Phase-1 stories" is wrong the moment a
  story is added or split, and nobody re-reads the epic to fix it. The child
  links are the source of truth and they maintain themselves.
- **Invented success criteria or dependencies.** A fabricated criterion is one
  nobody agreed to and everybody later cites. Leaving it open is the honest
  state, and the template has words for it.
- **A `Priority:` line.** It duplicates a real Jira field, and the two then
  disagree.

## Step 2. Resolve the project and its fields

Determine the project: an explicit instruction wins, otherwise the recorded
default from `jira_setup.py --show`. State which one you used. A default that is
never mentioned is a default nobody notices is wrong.

Then read create-metadata for that project and the Epic issue type, and resolve
every field by name. Also apply the `project_defaults` recorded for this project,
which are the fields the organisation expects on every issue even when the create
screen does not require them. Full procedure, matching rules, and what counts as
unresolved: [references/field-resolution.md](references/field-resolution.md).

Two fields need naming here:

- **Team.** `Assigned Team(s)`, `Team`, or `Squad`. **Ask**, offering the
  allowed values from create-metadata and the recorded default, in the same
  batch of questions as anything else missing. A spec does not say who will do
  the work, so this is the one field that cannot be derived. `none` is a valid
  answer and gets reported as the user's choice.
  [field-resolution.md § Team](references/field-resolution.md#team-ask-the-user-do-not-assume).
- **Priority: never choose one.** Not from a recorded default and not inferred
  from the spec. Priority is groomed against the whole backlog. Send nothing
  unless the user names a value, validated against the allowed values and
  reported as supplied. Where the project has a Priority default (BAPP's is an
  option named `TBD`), Jira stores it anyway: that is the project's value, not
  the run's, so the read-back expects it and the report names it as the
  default. Required with no default: stop and ask.
  [field-resolution.md § Priority](references/field-resolution.md#fields-that-must-be-resolved-by-name-every-run).

**If a required field cannot be filled, stop and say which one.** Do not create
the epic and mention the gap afterwards.

## Step 3. Search, then create

**Search before you create, every time.** A re-run of the same request, or a
teammate who filed the epic yesterday, otherwise leaves two epics splitting the
same stories between them. One query, before the create call, across every
status:

```text
project = <KEY> AND issuetype = Epic AND summary ~ "<two or three distinctive words>"
```

`~` is a text search and matches loosely, so compare the results yourself,
normalising case and whitespace:

- **Exact match: create nothing.** Report the existing key, its status, and
  that nothing was created. Do not update it: the user asked to create, and
  rewriting an epic someone has already groomed is a worse surprise than a skip.
- **Near match**, the same outcome in different words: ask whether it is the
  same epic, in one question, before creating. Asking about one epic is cheap.
  Two epics that each hold half the stories are not.
- **No match:** create.

Then call the create-issue capability with the resolved field identifiers, sending the
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
| Every required heading is present in the stored description | A truncated or blank render |
| The description has no `TBD` or `Priority:` line | Placeholders that survived |
| The team field holds the user's answer, or nothing if they said `none` | A team field Jira accepted and dropped |
| Priority is the user's named value, or the project default, or unset where there is no default | A recorded default or a guess that got sent |
| Every applied default holds the value sent | A field identifier Jira ignored |

Then report: the issue key, the browse URL built from the recorded site, the
project and issue type **as read back**, every field whose value you inferred or
defaulted rather than were given, and anything left as "Not yet decided".

Then say what to do next: stories under this epic are `crv-create-jira-story`.

## When a step fails

| Failure | What it means | Do |
| --- | --- | --- |
| No Jira tools here, but the spawning session had them | Tool inheritance, not setup | Stop. Hand back for an inline re-run, not to setup. |
| No Jira tools anywhere | Server not installed or not enabled | Stop. Point at [jira-setup.md § 1](references/jira-setup.md#1-the-atlassian-mcp-server). |
| Jira tools present, every call returns unauthorised | OAuth flow incomplete or grant expired | Stop. Point at [jira-setup.md § Troubleshooting](references/jira-setup.md#troubleshooting) to re-run server authentication. |
| `jira_setup.py --check` exits `1` | Site or project not recorded | Derive only from a value the user supplied, or a single accessible site. Otherwise stop and give the exact `--set … --confirm` command. |
| `jira_setup.py --check` exits `4` | Configuration file corrupt | Stop. Name the path; it needs inspection, not re-running setup. |
| Project not visible | Wrong key, or no permission | Stop. List the visible projects. |
| Required field unresolvable | Screen expects something not supplied | Stop. Name the field and the available field names. |
| No team field on the project | Not every project has one | Not a failure. Say so and file without it. |
| Team answer not among the allowed values | Typo, or a renamed team | List the allowed values and ask again. Do not send it. |
| Priority required on the create screen, with no default | The only case the run must ask about | Stop. Ask which value, then send the answer. |
| An epic with the same summary exists | A re-run, or someone filed it first | Not a failure. Create nothing, and report the existing key and its status. |
| An epic with a similar summary exists | Possibly the same work in other words | Ask once whether it is the same epic, then create or stop on the answer. |
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
- [ ] The description carries every required heading, in order, and says so from
      the read-back rather than from the payload.
- [ ] A JQL search for an existing epic ran before the create call.
- [ ] Every field the project marks required has a value.
- [ ] The issue-writing checklist ran: summary at most 80 characters, no em or
      en dash, no padding pattern, no `TBD`, no `Priority:` line.
- [ ] The epic's Priority in the read-back is the user's named value or the
      project default, and the report says which.
- [ ] The team field holds what the user gave, or is unset because they said so,
      and the report says which.
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
