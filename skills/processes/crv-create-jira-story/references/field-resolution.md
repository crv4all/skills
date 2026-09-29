# Resolving Jira fields at run time

Every Jira tenant numbers its custom fields independently. `customfield_10102`
is Story Points on one site and Sprint on another, and an administrator editing
a screen can change which fields a project requires without telling anyone. A
skill that ships hard-coded field identifiers is therefore wrong on every tenant
but the one it was written against, and silently wrong on that one the day the
screen changes.

So: resolve by **field name**, per project, per run.

## Fields that must be resolved by name every run

| Field | Why it varies |
| --- | --- |
| Story Points | `Story Points` on most tenants, `Story point estimate` on others. |
| Epic membership | Always `parent`, even where the screen also offers the legacy `Epic Link`. See below. |
| Team | `Team`, `Assigned Team(s)`, `Squad`, or absent. Asked, never assumed. See below. |
| Sprint | Numbered per tenant, and rejected outright on some boards. |
| Any option field | The allowed values are per project, not per tenant. |

One field is deliberately absent from that table. **Never choose a Priority.**
Neither skill picks one, whether or not the create screen offers it and whether
or not it has a recorded default. Reasons, in order:

- Priority is a scheduling decision the team makes in grooming, against
  everything else in the backlog. A value chosen at filing time by something
  that has not seen the backlog is a guess, and once it is in Jira it is
  indistinguishable from an agreed one.
- It is an option field, so an invented value is rejected or silently ignored.
- A `Priority: TBD` line in the description duplicates the real field, and the
  two then disagree.

**Many projects fill Priority themselves.** When create-metadata reports
`hasDefaultValue: true` for Priority, Jira stores its `defaultValue` on every
issue created without one. On BAPP that default is an option literally named
`TBD`, with an icon hosted off-site that renders broken. That value is the
project's, not the run's: it is what an issue filed by hand gets too. So:

- Read the default from create-metadata along with the allowed values.
- Send nothing, and expect the default in the read-back. A stored value equal to
  the default is a pass, reported as "the project default, not set by this run".
- Name it in the checkpoint question, so the user can set a real one: "Priority:
  the project default is TBD. Name one, or leave it." No answer leaves it.

Without a default, an unset Priority is honest, searchable, and one bulk edit
away from being set by the person entitled to set it.

Two exceptions, and both turn on the value coming from a person rather than from
the run:

- **The user names a priority explicitly**, in the request or in answer to a
  question. That is a supplied value, so send it. Validate it against the
  allowed values from create-metadata first, because Jira accepts an
  unrecognised option by ignoring it, and report it as supplied.
- **The create screen marks Priority required and has no default.** Stop and
  ask which value, then send the answer. Do not choose one to get past the
  screen. A required Priority with a default is not a stop: Jira fills it, as
  above.

What is forbidden is the run deciding. A priority inferred from the tone of a
spec, copied from a sibling issue, taken from a recorded default, or written as
a placeholder is a value nobody chose.

## The procedure

1. **Read create-metadata for the target project and issue type.** Use the
   create-metadata capability listed in the setup reference. The response
   describes every field available on the create screen: its identifier, its
   human-readable name, whether it is required, its schema type, and, for option
   fields, the allowed values.
2. **Match the fields you need by name**, case-insensitively, trimming
   whitespace. Match on the exact name first. Only if that finds nothing, fall
   back to a case-insensitive contains-match, and say in the report that you did
   so. A fuzzy match nobody was told about is how a value ends up in the wrong
   field.
3. **Collect the required fields the input does not supply.** Anything marked
   required on the create screen that has no value and no default is a blocker,
   not a warning.
4. **Apply the recorded project defaults.** `jira_setup.py --show` reports a
   `project_defaults` map, keyed by project key, of field names the organisation
   expects on every issue whether or not the create screen requires them. Resolve
   those names the same way, apply the values at create time, and list each one
   in the report as a default rather than a supplied value. A list field the
   input also sets, such as Labels, gets both: the default and the supplied
   values merged, never one replacing the other.
5. **Stop if anything is unresolved.** See below.
6. **Build the create payload** using the resolved identifiers, never the names.

## Team: ask the user, do not assume

The team field is the one field the organisation cares about that the create
screen usually does not enforce, so it gets left empty and patched one issue at
a time afterwards. It is also the one field the agent cannot derive: the work
described in a spec does not say who is going to do it.

So **ask**, once, before the first create call:

1. Resolve the field by name. Try `Assigned Team(s)`, `Team`, `Squad`, in that
   order. If none appears in create-metadata, the project does not have one.
   Say so and move on; do not invent a labels-based substitute.
2. Read its allowed values from create-metadata. It is an option field on most
   tenants, and often multi-value, which is why the CRV name is plural.
3. Ask the user, offering those values and the recorded default:

   > `Assigned Team(s)` for this project: Platform, Empower, Insight. Recorded
   > default is Platform. Reply with one or more, or `none` to leave it unset.

   One question for the whole batch, not one per story. Include it in the same
   batch of questions as anything else that is missing.
4. If the user answers, use it. If the user says `none`, leave the field unset
   and say so in the report. If the user does not answer at all and a recorded
   default exists, use the default and report it **as a default**, naming it.
5. Validate the answer against the allowed values before sending. A team name
   that is not among them is a typo or a renamed team, and Jira will accept the
   payload and drop the value. List the allowed values and ask again.

The recorded default from `jira_setup.py --show` is a starting point for that
question, not a replacement for it. A default that is never surfaced is a
default nobody notices is wrong, and team assignments change faster than anyone
re-runs setup.

If the create screen marks the team field required, an unanswered question is a
stop, not a default.

## Sprint, components and fix versions: only when named

None of these is required on most screens, and none can be derived from a spec.
Ask about each at the checkpoint only when the project has it, and components
and fix versions only when create-metadata lists allowed values for them. No
answer leaves the field unset: a story in the backlog is where grooming expects
to find it.

- **Sprint** takes a sprint id, and create-metadata lists none. When the user
  names one ("the current sprint", "Sprint 42"), find it on an issue already in
  it: search `project = <KEY> AND sprint in openSprints()`, read the Sprint
  field of a result, and match the name. No match, or two open sprints and the
  user said "current": say so, list the names found, and leave it unset.
- **Components and fix versions** are option lists. Validate a named value
  against the allowed values, as for any option field.

## Epic membership: always `parent`

Getting this wrong produces the most expensive failure in either skill: a batch
of stories that exist, look correct, and belong to no epic. Nothing in the create
response says so, because the field was simply not set.

**A story's epic is its `parent`**, sent as `{"parent": {"key": "ABC-123"}}`.
That holds in company-managed projects too: Jira Cloud moved epic membership
onto `parent` for both project styles. A company-managed create screen may still
offer a legacy `Epic Link` custom field beside it. Ignore it. Sending both is two
writes of one relationship that can disagree, and a skill that picks `Epic Link`
because the project is company-managed is following a rule Jira retired.

Rules:

- Confirm `parent` appears in create-metadata for the Story issue type. If it
  does not, **stop** and list the fields that do appear. Do not fall back to
  `Epic Link`, and do not create the stories planning to link them afterwards: a
  batch of orphans is harder to find than a refusal.
- Search and read back with `parent = <EPIC-KEY>`. It works on both project
  styles.
- Verify by reading the issues back after creating them. The create response is
  not evidence that membership was set.

## When a field cannot be resolved: stop

If a field named in the input does not appear in create-metadata, or a required
field has no value, **do not create the issue**. Report:

- the field name that could not be resolved,
- the project key and issue type it was looked up against,
- the field names that *are* available, so the caller can see the near miss,
- and that nothing was created.

Creating the issue anyway is the expensive failure. A field identifier Jira
ignored is invisible in the transcript, the issue was created, the run looks
successful, and it surfaces days later as a story nobody can plan against. A
refusal is noticed in seconds. Prefer the failure that gets noticed.

The distinction to keep hold of: a field that **cannot be resolved** is a stop,
because the run does not know what it is about to write. A field that resolved
fine and has **no value to write** is not a stop. It is left unset and named in
the report.

The same applies to option fields: if a supplied value is not among the allowed
values for that field, stop and list the allowed values. Jira will often accept
an unrecognised option by silently ignoring it.

## Story Points specifically

The most common name is `Story Points`; some tenants use `Story point estimate`.
Try both before concluding it is absent. It is normally a number field, so send
a JSON number, not a string.

Do not restrict the value to a Fibonacci sequence. Teams use their own scales,
and a story-point total rolled up from several smaller items lands on no ladder
at all. Reject only what is genuinely invalid: zero, negatives, and non-integers.

**An estimate is optional and never invented.** Sizing is the team's job and it
happens in grooming, with the people who will do the work. Three rules follow:

- No estimate supplied, and none agreed: omit the field and file the story. Say
  so in the report. Do not also say it in the description: the empty field is
  the record, and a sentence saying so goes stale the moment grooming sizes it.
- Never write a number the user did not agree to. Once a number is in Jira an
  invented estimate is indistinguishable from a groomed one, and it gets summed
  into a sprint commitment.
- Never block a batch on a missing estimate. An unsized story in the backlog is
  a five-second fix in grooming. A refusal to file is a re-run of the whole
  decomposition.

The field must still **resolve** if a value was supplied. Supplying an estimate
that Jira silently drops is the failure this section exists to prevent, and it
is a different thing from having no estimate to supply.

## Verifying, rather than trusting, the write

A create call that returns `201` proves an issue exists. It proves nothing about
what is in it. Jira accepts a payload containing a field identifier it does not
recognise on that screen by ignoring it, and returns success.

So for every field that matters, read the issue back after writing and compare
the stored value with the intended one. At minimum: epic membership, story
points, and any organisation default that was applied. Quote the values that came
back, not the values that were sent.

## Description format

Send the description as markdown, using whatever content-format parameter the
create capability exposes for it. Atlassian's server takes
`contentFormat: "markdown"`. Do not hand-build Atlassian Document Format. ADF is
verbose, easy to get subtly wrong, and a malformed node produces an issue whose
description renders blank rather than an error that says what happened.

## Caching

Do not cache resolved identifiers between runs. Create-metadata is one call, and
the whole point of resolving at run time is that the answer can change. A cache
reintroduces exactly the staleness this procedure exists to avoid.

Caching within a single run is fine and worth doing: filing eight stories into
one project should read create-metadata once, not eight times.
