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
| Epic membership | `parent` in a team-managed project, an `Epic Link` custom field in a company-managed one. See below. |
| Team | `Team`, `Assigned Team(s)`, `Squad`, or absent. Often not required by the screen but expected by the organisation. |
| Sprint | Numbered per tenant, and rejected outright on some boards. |
| Any option field | The allowed values are per project, not per tenant. |

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
   in the report as a default rather than a supplied value.
5. **Stop if anything is unresolved.** See below.
6. **Build the create payload** using the resolved identifiers, never the names.

## Epic membership: `parent` or `Epic Link`

Getting this wrong produces the most expensive failure in either skill: a batch
of stories that exist, look correct, and belong to no epic. Nothing in the create
response says so, because the field was simply not set.

Which mechanism a project uses depends on how the project was created, and both
are current:

| Project style | Field | Payload |
| --- | --- | --- |
| Team-managed (next-gen) | `parent` | `{"parent": {"key": "ABC-123"}}` |
| Company-managed (classic) | `Epic Link`, a custom field | `{"customfield_NNNNN": "ABC-123"}`, the key as a bare string |

How to tell, without guessing: read create-metadata and look at which of the two
appears. A company-managed project's Story create screen carries a field named
`Epic Link` and its `parent` field, when present at all, is for a different
relationship. A team-managed project carries `parent` and has no `Epic Link`.

Rules:

- Resolve `Epic Link` by name exactly as any other custom field. Never assume
  `customfield_10008` or any other number, even though that is the common value.
- Send the epic key as a string for `Epic Link`, and as `{"key": ...}` for
  `parent`. The two shapes are not interchangeable and the wrong one is rejected
  or, worse, accepted and dropped.
- If neither field can be resolved, **stop**. Do not create the stories and plan
  to link them afterwards. A batch of orphans is harder to find than a refusal.
- Verify by reading the issues back after creating them. The create response is
  not evidence that membership was set.

Some tenants also reject `Epic Link` on the create call but accept it on an
edit. If create fails on that field alone, creating and then patching is
acceptable, provided the patch is verified by a read-back and the report says
that is what happened.

## When a field cannot be resolved: stop

If a field named in the input does not appear in create-metadata, or a required
field has no value, **do not create the issue**. Report:

- the field name that could not be resolved,
- the project key and issue type it was looked up against,
- the field names that *are* available, so the caller can see the near miss,
- and that nothing was created.

Creating the issue anyway is the expensive failure. A missing Story Points value
is invisible in the transcript, the issue was created, the run looks successful,
and it surfaces days later as a story nobody can plan against. A refusal is
noticed in seconds. Prefer the failure that gets noticed.

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
