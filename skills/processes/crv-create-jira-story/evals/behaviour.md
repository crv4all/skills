# Behaviour evals — crv-create-jira-story

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

B2 is the case this skill exists for. B3 to B5 are the no-silent-failure guards,
and each asserts that **nothing was created** — the characteristic failure here
is not an error, it is a batch of stories that exist and should not.

B6 is the counterweight, and it is easy to get backwards. A missing estimate is
not a guard: it files. The distinction the guards turn on is whether the run
knows what it is about to write, not whether it has everything it might want.

B9 onwards were written from a real run that filed 31 issues into a
company-managed project. Every one of them is a failure that happened, reported
itself as success, and cost rework. They are the cases most worth running.

B18 to B21 come from the same run's second review, where the issues were correct
and unusable: padded with the shapes that mark generated text, and carrying a
Priority nobody chose. That review first produced a word cap. B20 and B22 now
assert the opposite of a cap, because the cap cut real content along with the
padding: what is cut is the padding, and no content from the source is dropped
to make a story shorter.

## B1 — The main path

**Setup:** Atlassian MCP configured and authenticated. `jira_setup.py --check`
exits `0`. Epic `ABC-123` exists with no children.
**Prompt:** "Break this spec into stories and file them under ABC-123, 3 points each." (with a three-item spec)

- [ ] Preflight runs before the spec is read.
- [ ] The epic is read before any story is built.
- [ ] A JQL search against `ABC-123` runs before the first create call.
- [ ] Three stories are created, each a child of `ABC-123`.
- [ ] Each carries a story-point value of `3` as a number, not a string.
- [ ] Each description contains the four required headings from `assets/story-description.md.template` and renders as markdown in Jira.
- [ ] Every acceptance criterion in the spec appears in a created story. None is dropped to shorten a description.
- [ ] No description carries an optional heading with nothing under it.
- [ ] **No story has a Priority value**, and no description contains a `Priority:` line.
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

## B5 — Guard: Story Points unresolvable while an estimate was supplied

**Setup:** Everything configured. The project has no field named `Story Points`
or `Story point estimate`.
**Prompt:** "File three stories under ABC-123, 3 points each."

- [ ] Both field names are tried before concluding it is absent.
- [ ] The skill stops and lists the available field names.
- [ ] **No stories are created.** A number the user gave that Jira would accept and drop is the failure here, so filing without it is not the fallback.

Then repeat with the same project and **no estimate in the prompt**:

- [ ] The skill does **not** stop. Three stories are created with no estimate.
- [ ] The report says the project has no story-point field.

## B6 — A candidate with no estimate is filed, not refused

**Setup:** Everything configured. `ABC-123` empty. Three candidates supplied,
one with no story points.
**Prompt:** "File these three stories under ABC-123."

- [ ] **All three stories are created.** None is reported `refused` for want of an estimate.
- [ ] The unsized story has **no** value in the story-point field, confirmed by read-back. Not `0`, not null-as-zero.
- [ ] **No estimate is invented**, including by copying a sibling's value or averaging.
- [ ] Its description says nothing about being unsized. The empty field is the record.
- [ ] The report names it as unsized so grooming has the list.
- [ ] The reported point total covers the two estimated stories and does not silently count the third as zero.

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
- [ ] On approval, each created story carries a comment recording that its estimate was proposed and bulk-approved rather than groomed, and its description does not.
- [ ] The report repeats which estimates were proposed rather than supplied.
- [ ] Then decline the table: **all twelve are still created**, every one unsized, and the report lists them as unsized. Declining an estimate is not declining the batch.
- [ ] Then ignore the offer entirely: same outcome. The run does not stall waiting for an answer it does not need.

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

## B17 — The tier is stated, not asked

**Setup:** Everything configured. Harness supports subagents.
**Prompt:** "File these three stories under ABC-123."

- [ ] The run states the tier in one line and continues.
- [ ] **No question about the tier is asked**, and no round trip is spent waiting for one.
- [ ] Work starts in the same turn.
- [ ] Repeat with "use the balanced tier for this" in the prompt: the stated tier is honoured and named in the report.

## B18 — The team field is asked, once, for the whole batch

**Setup:** Everything configured. The project carries `Assigned Team(s)` with
allowed values Platform, Empower, Insight. A recorded default of Platform
exists. Five candidates.
**Prompt:** "File these five stories under ABC-123."

- [ ] The user is asked which team, **once**, not once per story.
- [ ] The question lists the allowed values read from create-metadata, and names the recorded default.
- [ ] The recorded default alone does not suppress the question.
- [ ] Answer "Empower": all five carry Empower, confirmed by read-back, and the report says the value came from the user.
- [ ] Answer "none": all five have the field unset, and the report says so as the user's choice rather than as an omission.
- [ ] Answer "Platfrom" (misspelt): the value is **not** sent. The allowed values are listed and the question is asked again.

## B19 — Priority is never set

**Setup:** Everything configured. The Story create screen offers Priority,
optional, with a default of Medium. `jira_setup.py --show` also records a
`project_defaults` entry setting Priority to High.
**Prompt:** "File these three stories under ABC-123."

- [ ] **No create payload contains a Priority field.**
- [ ] The recorded Priority default is ignored, and the report says it was ignored rather than applied.
- [ ] No description contains a `Priority:` line or the text `TBD`.
- [ ] The read-back confirms no story has a Priority value.
- [ ] Then prompt "file these three under ABC-123, all high priority": Priority **is** set to High, because the user chose it. It is validated against the allowed values first and reported as supplied, not as a default.
- [ ] Then prompt with a priority that is not an allowed value: it is not sent, and the allowed values are listed.
- [ ] Then make Priority **required** on the create screen with no priority in the prompt: the skill stops and asks which value, rather than choosing one or sending `TBD`.

## B20 — Descriptions keep the content and drop the padding

**Setup:** Everything configured. A long, discursive spec of roughly 2,000 words
for three stories, mixing motivation and history with concrete constraints: two
endpoint names, a sample payload, and a rate limit.
**Prompt:** "Break this into three stories under ABC-123 and file them."

- [ ] Every concrete constraint in the spec, including both endpoint names, the sample payload and the rate limit, appears in the story it belongs to.
- [ ] No description is shortened by dropping a constraint or an acceptance criterion. The skill applies no word count.
- [ ] Motivation and history the epic already carries are linked, not copied, and a story whose epic covers the context has no Context section at all.
- [ ] No description contains an em dash, an en dash, an arrow, or an emoji.
- [ ] No description opens by announcing what follows, and none closes with a sentence that summarises the paragraph above it.
- [ ] No bullet begins with a bold mini-heading and a colon.
- [ ] No heading is restated by its own first sentence.
- [ ] Spot-check against the pattern tables in `references/issue-writing.md`: pick five patterns and confirm none appears.

## B21 — A subagent with no Atlassian tools

**Setup:** Harness supports subagents, and the spawned subagent is granted no
Atlassian MCP server. The main session has one, authenticated.
**Prompt:** "File these three stories under ABC-123."

- [ ] The run distinguishes this from a server that was never installed.
- [ ] It says the tools exist in the main session and that this is tool inheritance.
- [ ] It does **not** send the user to the setup reference or to `claude mcp`.
- [ ] **No stories are created.**
- [ ] It hands back for an inline re-run, and the inline re-run completes normally and says it ran inline.

## B22 — Many acceptance criteria prompt a split, not a cut

**Setup:** Everything configured. `ABC-123` empty. One candidate with nine
acceptance criteria covering two separable behaviours.
**Prompt:** "File this story under ABC-123."

- [ ] Before creating, the skill says the criteria look like two stories and offers the split.
- [ ] Accept the split: two stories are created, and every one of the nine criteria appears in exactly one of them.
- [ ] Decline it: one story is created carrying **all nine** criteria. None is dropped, merged away, or shortened to fit.
- [ ] The skill does not refuse the story or report it as over a limit.

## B23 — Technical work opens with a goal, not a contrived user story

**Setup:** Everything configured. `ABC-123` empty. One candidate: split
`OrderService` into pricing and persistence, with no end user affected.
**Prompt:** "File this under ABC-123."

- [ ] The description opens with a `Goal` heading, not `User story`.
- [ ] No description contains "As a developer" or "As a system".
- [ ] The goal states what is true afterwards and why, in one sentence.
- [ ] The other three required headings are present as usual.
- [ ] Then file a candidate with a real user in it: it opens with `User story`, as before.
