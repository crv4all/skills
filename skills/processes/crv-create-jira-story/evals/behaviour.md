# Behaviour evals — crv-create-jira-story

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

B2 is the case this skill exists for. B3 to B6 are the no-silent-failure guards,
and each asserts that **nothing was created** — the characteristic failure here
is not an error, it is a batch of stories that exist and should not.

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
