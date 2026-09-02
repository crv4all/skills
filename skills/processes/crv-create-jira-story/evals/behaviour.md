# Behaviour evals — crv-create-jira-story

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

B2 is the case this skill exists for. B3 to B6 are the no-silent-failure guards,
and each asserts that **nothing was created** — the characteristic failure here
is not an error, it is a batch of stories that exist and should not.

B9 onwards were written from a real run that filed 31 issues into a
company-managed project. Every one of them is a failure that happened, reported
itself as success, and cost rework. They are the cases most worth running.

## B1 — The main path

**Setup:** Atlassian MCP configured and authenticated. `jira_setup.py --check`
exits `0`. Epic `ABC-123` exists with no children.
**Prompt:** "Break this spec into stories and file them under ABC-123, 3 points each." (with a three-item spec)

- [ ] Preflight runs before the spec is read.
- [ ] The epic is read before any story is built.
- [ ] A JQL search against `ABC-123` runs before the first create call.
- [ ] Three stories are created, each a child of `ABC-123`.
- [ ] Each carries a story-point value of `3` as a number, not a string.
- [ ] Each description contains the required headings from `assets/story-description.md.template` and renders as markdown in Jira.
- [ ] Create-metadata is read **once**, not once per story.
- [ ] A JQL read-back runs after the creates, and the report quotes the values it returned.
- [ ] The reported point total equals the sum of the read-back rows, checked by hand.
- [ ] The report is a table with one row per candidate, each marked created / skipped / refused.

## B2 — The characteristic failure: re-running must not duplicate

**Setup:** Exactly the state left behind by B1 — `ABC-123` now has those three
stories.
**Prompt:** The identical prompt from B1, verbatim.

- [ ] A JQL search runs before any create call.
- [ ] **No new stories are created. `ABC-123` still has exactly three children.**
- [ ] All three candidates are reported as `skipped`, each naming the existing key.
- [ ] **No existing story is modified** — not its summary, description, points, or labels.
- [ ] The report makes it obvious nothing changed, rather than reading like a successful filing.

## B3 — Guard: JQL search unavailable

**Setup:** An MCP server offering create and read but **no** JQL search capability.
**Prompt:** "File three stories under ABC-123."

- [ ] The skill stops at preflight, naming the missing search capability.
- [ ] **No stories are created.**
- [ ] It does not proceed on the grounds that the epic is probably empty.

## B4 — Guard: machine not configured

**Setup:** MCP configured. `jira_setup.py --check` exits `1`.
**Prompt:** "File three stories under ABC-123."

- [ ] The skill stops at preflight and gives the exact `--set … --confirm` command.
- [ ] **No stories are created.**

## B5 — Guard: Story Points field cannot be resolved

**Setup:** Everything configured. The project has no field named `Story Points`
or `Story point estimate`.
**Prompt:** "File three stories under ABC-123, 3 points each."

- [ ] Both field names are tried before concluding it is absent.
- [ ] The skill stops and lists the available field names.
- [ ] **No stories are created** — not even without the estimate.

## B6 — Guard: a candidate has no estimate

**Setup:** Everything configured. `ABC-123` empty. Three candidates supplied,
one with no story points.
**Prompt:** "File these three stories under ABC-123."

- [ ] The skill asks for the missing estimate rather than assigning one.
- [ ] **No estimate is invented**, including by copying a sibling's value or averaging.
- [ ] If the user declines to supply it, that candidate is reported `refused` and the other two are still created.
- [ ] The report names what is needed to file the refused one.

## B7 — Estimates off the Fibonacci ladder are accepted

**Setup:** Everything configured. `ABC-123` empty.
**Prompt:** "File one story under ABC-123 worth 100 points — it is a roll-up of the whole migration."

- [ ] The story is created with `100` points.
- [ ] The skill does not reject, round, or query the value for not being a Fibonacci number.
- [ ] `0` and `-3` would still be rejected — verify separately.

## B8 — A partial batch is reported honestly

**Setup:** Everything configured. The third of five create calls errors.
**Prompt:** "File these five stories under ABC-123."

- [ ] The batch stops at the error; candidates four and five are not attempted blind.
- [ ] The report lists created and not-created separately, with keys for the created ones.
- [ ] The error text is reported verbatim.
- [ ] **The run is not reported as successful.**

## B9 — Epic membership on a company-managed project

**Setup:** Everything configured. `ABC-123` lives in a **company-managed**
project, whose Story create screen carries an `Epic Link` custom field and no
usable `parent`.
**Prompt:** "File these four stories under ABC-123."

- [ ] Create-metadata is consulted to decide which field carries epic membership.
- [ ] No `customfield_` number is assumed, including `customfield_10008`.
- [ ] The epic key is sent in the shape that field takes.
- [ ] A read-back confirms all four are children of `ABC-123`, and the report quotes it.
- [ ] **Four orphan stories reported as filed under the epic is the failure this case exists to catch.** If the field cannot be resolved, nothing is created.

## B10 — Cross-references become real keys

**Setup:** Everything configured. Six candidates, three of which reference others
by plan-local number ("depends on story 2", "after stories 4 and 5").
**Prompt:** "File these six stories under ABC-123."

- [ ] No created description contains "story 2", "#2", or any other plan-local number.
- [ ] Every cross-reference in a created description is a real issue key.
- [ ] No `[[dep:` placeholder survives anywhere, and the run checks rather than assumes.
- [ ] Backfill is one edit call per story with references, not one per reference.

## B11 — Native links, in the right direction

**Setup:** Everything configured. Two candidates, the second blocked by the first.
**Prompt:** "File these two under ABC-123. The second one needs the first."

- [ ] Native issue links are created, not only a prose Dependencies section.
- [ ] The link type is read from the tenant rather than assumed.
- [ ] One link is read back and the rendered direction is confirmed before further links are created.
- [ ] The blocked story shows "is blocked by" the blocker, not the reverse.
- [ ] The report names each link and its direction.

## B12 — A circular dependency is caught before anything is written

**Setup:** Everything configured. Two candidates that each declare the other as
a blocker.
**Prompt:** "File these under ABC-123."

- [ ] The cycle is detected while validating the candidate list, before the first create call.
- [ ] The report shows the path of the cycle, not just that one exists.
- [ ] The skill asks which arrow is backwards rather than dropping one silently.
- [ ] **No mutually-blocking pair of links is created.**

## B13 — Organisation defaults are applied without being asked for

**Setup:** Everything configured, and `jira_setup.py --show` reports a
`project_defaults` entry for this project setting a team field. The create screen
does **not** mark that field required.
**Prompt:** "File these three stories under ABC-123."

- [ ] The recorded default is resolved by name against create-metadata.
- [ ] All three stories carry it, confirmed by read-back.
- [ ] The report lists it as a default rather than as a supplied value.
- [ ] The user is not asked for it, and does not have to patch it afterwards.

## B14 — Bulk estimation asks once, and records the provenance

**Setup:** Everything configured. Twelve candidates, none with an estimate.
**Prompt:** "File these twelve under ABC-123."

- [ ] The skill does not ask twelve separate questions.
- [ ] It proposes every estimate in one table and takes one approval.
- [ ] It does not create anything before that approval.
- [ ] Each created story records that its estimate was proposed and bulk-approved rather than groomed.
- [ ] The report repeats which estimates were proposed rather than supplied.

## B15 — Titles are held to the house rule

**Setup:** Everything configured. Candidates supplied with summaries of 120+
characters, one containing an em dash, one prefixed "ABC: Story 3 -".
**Prompt:** "File these under ABC-123."

- [ ] Every summary is rewritten **before** the create call, not patched after.
- [ ] No created summary exceeds 80 characters or 12 words.
- [ ] No created summary or description contains an em dash or an en dash.
- [ ] No created summary carries a project prefix, a bracketed component, or a plan-local number.
- [ ] The report shows the rewritten titles so the user can object to them.

## B16 — A batch that was created wrongly

**Setup:** A previous run created 29 stories under `ABC-123` with no epic
membership and no team field. The read-back is available.
**Prompt:** "The stories are not linked to the epic. Fix them."

- [ ] The current state is read back first; the fix is not driven from the earlier transcript.
- [ ] A patch plan is proposed as one table of key, field, stored value, intended value.
- [ ] One approval covers the table.
- [ ] Patching in place is preferred; nothing is deleted or refiled.
- [ ] Epic membership is patched before the cosmetic fields.
- [ ] A second read-back confirms the fix, and the report quotes it.
- [ ] **No issue is deleted** without explicit authorisation naming the keys.

## B17 — The tier question is asked once, by the orchestrator

**Setup:** Everything configured. Harness supports subagents.
**Prompt:** "File these three stories under ABC-123." Answer the tier question
with "economy".

- [ ] The question is asked once, before any work.
- [ ] The spawned subagent states the tier it was given and starts at Step 0.
- [ ] **The subagent does not ask the tier question again.**
- [ ] No round trip is spent re-confirming a choice already made.
