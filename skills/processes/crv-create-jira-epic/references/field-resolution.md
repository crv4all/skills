# Resolving Jira fields at run time

Every Jira tenant numbers its custom fields independently. `customfield_10102`
is Story Points on one site and Sprint on another, and an administrator editing
a screen can change which fields a project requires without telling anyone. A
skill that ships hard-coded field identifiers is therefore wrong on every tenant
but the one it was written against, and silently wrong on that one the day the
screen changes.

So: resolve by **field name**, per project, per run.

## The procedure

1. **Read create-metadata for the target project and issue type.** Use the
   create-metadata capability listed in the setup reference. The response
   describes every field available on the create screen: its identifier, its
   human-readable name, whether it is required, its schema type, and — for
   option fields — the allowed values.
2. **Match the fields you need by name**, case-insensitively, trimming
   whitespace. Match on the exact name first. Only if that finds nothing, fall
   back to a case-insensitive contains-match, and say in the report that you did
   so — a fuzzy match that nobody was told about is how a value ends up in the
   wrong field.
3. **Collect the required fields the input does not supply.** Anything marked
   required on the create screen that has no value and no default is a blocker,
   not a warning.
4. **Stop if anything is unresolved.** See below.
5. **Build the create payload** using the resolved identifiers, never the names.

## When a field cannot be resolved: stop

If a field named in the input does not appear in create-metadata, or a required
field has no value, **do not create the issue**. Report:

- the field name that could not be resolved,
- the project key and issue type it was looked up against,
- the field names that *are* available, so the caller can see the near miss,
- and that nothing was created.

Creating the issue anyway is the expensive failure. A missing Story Points value
is invisible in the transcript — the issue was created, the run looks successful
— and surfaces days later as a story nobody can plan against. A refusal is
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

## Description format

Send the description as markdown, using whatever content-format parameter the
create capability exposes for it — Atlassian's server takes
`contentFormat: "markdown"`. Do not hand-build Atlassian Document Format. ADF is
verbose, easy to get subtly wrong, and a malformed node produces an issue whose
description renders blank rather than an error that says what happened.

## Caching

Do not cache resolved identifiers between runs. Create-metadata is one call, and
the whole point of resolving at run time is that the answer can change. A cache
reintroduces exactly the staleness this procedure exists to avoid.

Caching within a single run is fine and worth doing: filing eight stories into
one project should read create-metadata once, not eight times.
