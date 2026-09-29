# Cross-references, dependencies, and native issue links

A decomposition arrives with the stories numbered by the plan: story 4 depends
on story 2, stories 18 to 23 land after the schema change. Jira has none of those
numbers. It has keys, and it does not have them until the issues exist.

That is an ordering problem, not a wording problem, and it has one honest
solution: create first, then write the references.

## Two passes, always

**Pass 1: create.** File every story with its description complete except for
references to sibling stories. Where a reference belongs, leave a placeholder
that is impossible to mistake for prose and impossible to leave behind:

```text
Blocked by: [[dep:2]]
```

Keep a table in working memory or in a scratch file mapping each plan-local
number to the key that came back: `2 -> CHO-3331`.

**Pass 2: backfill.** Replace every placeholder with the real key, then create
the native links. One edit per story that has references, not one per reference.

Rules that keep this from going wrong:

- **Never ship plan-local numbering.** "See story 4", "stories 18 to 23" and
  "part 2 of the phase 1 batch" are meaningless to the person reading CHO-3344 in
  six weeks. They are also unsearchable.
- **Never guess a key.** Keys are allocated by Jira and are not contiguous,
  because another team may file into the same project mid-batch. `CHO-3344` for
  the fourteenth story of the batch is a coin flip.
- **Fail loudly on a leftover placeholder.** Grep the created issues for `[[dep:`
  after pass 2 and report any hit as an unfinished run, not as a note.

## Validate the dependency graph before writing anything

Do this in pass 0, on the candidate list, before the first create call. Every one
of these is cheap to check on a list and expensive to find in Jira.

| Check | Failure it catches |
| --- | --- |
| Every referenced number exists in the batch | A reference to a story that was dropped during splitting. |
| No self-reference | A story that blocks itself, usually a copy-paste. |
| No cycles, of any length | A blocks B and B blocks A. Neither can start, and no board view can order them. |
| Direction is stated, not implied | "Related to story 7" hides whether story 7 is a blocker. |
| A dependency on work outside the batch names a real key or a real team | "Waits on the platform work" is not actionable. |
| A real key named as a dependency exists | A typo that becomes a link to nothing. Read each one; one that does not resolve goes to the checkpoint and gets no link until answered. |

Cycle detection on a list this size is a walk of the graph: for each node, follow
its blockers depth first, and if the walk reaches the node it started from, the
cycle is the path. Report the whole path, not just the pair, because a three-node
cycle usually means one of the three arrows is simply backwards.

**A cycle is a decomposition error, not a link error.** Do not resolve it by
dropping one of the links. Report the cycle, say which arrow you believe is
backwards and why, and ask. The stories can be created while the question is
open; the links cannot.

## Native links, not a prose section

A "Dependencies" heading in a description is invisible to Jira. Blocked-by
columns, dependency reports, roadmap arrows and automation rules all read native
issue links and nothing else. Prose dependencies are for the human reading the
ticket; the link is for every other tool the team uses. Create both.

Use the create-issue-link capability, and read the available link types first
rather than assuming a name. The types most tenants ship are `Blocks`,
`Relates`, `Duplicate` and `Cloners`.

**If there is no `Blocks` type**, create the stories and no dependency links.
Do not substitute `Relates`, for the reason below. Report every dependency as
prose-only, so someone with admin rights can add the type and the links.

### Direction

For a `Blocks` link, the payload has an inward and an outward issue, and the
semantics are the part everyone gets wrong:

```json
{
  "type": { "name": "Blocks" },
  "inwardIssue":  { "key": "CHO-3331" },
  "outwardIssue": { "key": "CHO-3344" }
}
```

**The inward issue is the blocker.** Read that as "CHO-3331 blocks CHO-3344", so
CHO-3344 shows "is blocked by CHO-3331" on its own page.

Do not take that on trust. Create the first link of the batch, read one of the
two issues back, and check that the rendered relationship says what you meant.
If it is reversed, every remaining link is reversed the same way, and you have
found it after one call instead of thirty. Report which direction you verified.

`Relates` is symmetric, so direction does not matter for it. That makes it the
tempting default, and the wrong one: a `Relates` link where a `Blocks` link
belongs looks tidy and drives nothing.

### What to link and what not to

- Link every dependency the decomposition actually asserts. One link per asserted
  edge, no duplicates in the opposite direction.
- Do not link a story to its own epic. Epic membership is a field, and a link as
  well as the field produces two relationships that can disagree.
- Do not invent links to tidy the graph. An edge nobody asserted becomes a
  blocked-by badge that stops work.

## Reporting

The report says, per story, which links were created and in which direction, and
lists any dependency that could not be linked because the other side is not in
Jira yet. A dependency mentioned in a description with no link behind it is the
default failure of this step, and it is only visible if the report says so.
