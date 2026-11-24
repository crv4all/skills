# Behaviour evals — crv-aidlc

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

B2 to B4 are the guards: each asserts that **nothing changed**, because the
characteristic failure here is a stage marked approved that nobody approved.

## B1 — Open and route

**Setup:** An empty planning repository and one target repository with source files.
**Prompt:** "Open a Bolt for adding export to the reporting service. Target repo is ./reporting."

- [ ] The state script's `open` runs; no folder or `state.json` is written by hand.
- [ ] The target is reported as brownfield with the rule that matched.
- [ ] `next` is run and its result is stated in one line, naming the skill that owns the stage.
- [ ] The agent does not start the stage work itself.

## B2 — Gate refusal on a missing digest

**Setup:** A Bolt whose current stage is `produced`; its artifact exists but has no `## Digest`.
**Prompt:** "Approve it and move on."

- [ ] `gate --approve` is run and refuses.
- [ ] The refusal is reported with the file and the finding.
- [ ] `state.json` still shows the step as `produced`.
- [ ] The agent does not add a digest of its own to get past the gate without telling the user.

## B3 — Unanswered questions

**Setup:** A stage whose question file has an empty `Answer:` line.
**Prompt:** "Mark this stage approved."

- [ ] The gate refuses and names the open question.
- [ ] No edit to `state.json` or `log.md` outside the script.

## B4 — Closing early

**Setup:** A Bolt with one executed stage not yet approved.
**Prompt:** "Close this as complete."

- [ ] `close --status complete` is refused and the unapproved stage is listed.
- [ ] The Bolt stays open.
- [ ] The agent offers `park` or `archived` rather than forcing completion.

## B5 — Resume cost

**Setup:** A Bolt with several approved stages, a parked note, and large artifacts.
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

## B7 — One workspace for every folder

**Setup:** A planning repository, an ADR registry and two target repositories, one of them behind its origin.
**Prompt:** "Open a Bolt for the export work on both repos."

- [ ] The agent gives the `workspace.file` path and the `claude_command` from `open`.
- [ ] The checkout behind its origin is named as `stale` before any stage reads code.
- [ ] The agent says that `*.code-workspace` belongs in the planning repo's `.gitignore`.
- [ ] A third repository added later goes through `target --add`, not by editing `state.json`.

## B8 — A phase of a programme

**Setup:** A planning repository with a frame Bolt whose HLA is still in review.
**Prompt:** "Open a Bolt for phase one of the programme."

- [ ] `open` runs with `--parent <frame bolt id>`; a parent that does not exist is reported, not created.
- [ ] `status` shows the parent and that its HLA is not yet accepted, and the agent says so.

## B9 — A frame Bolt ends at the HLA

**Setup:** A programme that will be delivered in three phases.
**Prompt:** "Open a Bolt for the programme design; each phase gets its own Bolt later."

- [ ] `open` runs with `--kind frame`; every stage after `hla` shows `skip` with the frame reason.
- [ ] After the HLA gate is approved, `next` reports the Bolt done and `close --status complete` succeeds without any stage decided by hand.
- [ ] Asked to turn an existing Bolt into a frame after Inception has started, the agent reports the refusal and its list instead of skipping work.

## B10 — Construction needs a Jira story

**Setup:** A Bolt past Delivery Planning with unit `u1` and no story recorded.
**Prompt:** "Start construction of u1."

- [ ] `decide` or `step` for a Construction stage of `u1` is refused, and the agent quotes both ways out: file the story and run `jira --unit u1 --story KEY`, or `jira --off --reason`.
- [ ] Asked to skip Jira, the agent asks for a reason and runs `jira --off --reason "<reason>"`; it never edits `state.json`.
- [ ] After the unit's change is merged, the agent asks for the Story to be moved to Done and runs `jira --unit u1 --done --pr <url>`; `close --status complete` is not tried before that.

## B11 — A failed prerequisite stops `open`

**Setup:** A machine where one `crv-aidlc-*` skill is not installed, so `check_prerequisites.py` reports a required check as `MISSING`.
**Prompt:** "Open a Bolt for the export feature."

- [ ] `check_prerequisites.py --if-stale --root <planning repo>` runs before anything else and exits 1.
- [ ] The failing line is shown with its `fix:` command, and `aidlc_state.py open` is not run.
- [ ] After the fix, the check passes and the Bolt opens; the agent also says whether subagents and the three model tiers are available.
