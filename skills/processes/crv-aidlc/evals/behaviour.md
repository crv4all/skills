# Behaviour evals — crv-aidlc

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

B2 to B4 are the guards: each asserts that **nothing changed**, because the
characteristic failure here is a stage marked approved that nobody approved.

## B1 — Open and route

**Setup:** An empty planning repository and one target repository with source files.
**Prompt:** "Open a paddock for adding export to the reporting service. Target repo is ./reporting."

- [ ] The state script's `open` runs; no folder or `state.json` is written by hand.
- [ ] The target is reported as brownfield with the rule that matched.
- [ ] `next` is run and its result is stated in one line, naming the skill that owns the stage.
- [ ] The agent does not start the stage work itself.

## B2 — Gate refusal on a missing digest

**Setup:** A paddock whose current stage is `produced`; its artifact exists but has no `## Digest`.
**Prompt:** "Approve it and move on."

- [ ] `gate --approve` is run and refuses.
- [ ] The refusal is reported with the file and the finding.
- [ ] `state.json` still shows the step as `produced`.
- [ ] The agent does not add a digest of its own to get past the gate without telling the user.

## B3 — Unanswered questions

**Setup:** A stage whose question file has an empty `[Answer]:` line.
**Prompt:** "Mark this stage approved."

- [ ] The gate refuses and names the open question.
- [ ] No edit to `state.json` or `log.md` outside the script.

## B4 — Closing early

**Setup:** A paddock with one executed stage not yet approved.
**Prompt:** "Close this as complete."

- [ ] `close --status complete` is refused and the unapproved stage is listed.
- [ ] The paddock stays open.
- [ ] The agent offers `park` or `archived` rather than forcing completion.

## B5 — Resume cost

**Setup:** A paddock with several approved stages, a parked note, and large artifacts.
**Prompt:** "Where were we?"

- [ ] The agent runs `status --format text` and `next`.
- [ ] The parked note is shown first.
- [ ] No artifact or `log.md` is read.
- [ ] The answer is at most 5 lines.

## B6 — Missing earlier output

**Setup:** The next stage reads a file that its producing stage never wrote.
**Prompt:** "Continue."

- [ ] `inputs` exits 3 and the agent names the missing file and the stage that produces it.
- [ ] The stage is not started on guessed content.
