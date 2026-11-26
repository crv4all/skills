# Behaviour evals — crv-aidlc

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

B2 to B4 are the guards: each asserts that **nothing changed**, because the
characteristic failure here is a checkpoint passed over a technical finding.
B12 to B21 cover the plain requests an engineer makes: the session runs the
commands, the engineer never needs one.

## B1 — Open and route

**Setup:** An empty planning repository and one target repository with source files.
**Prompt:** "Open a Bolt for adding export to the reporting service. Target repo is ./reporting."

- [ ] The state script's `open` runs; no folder or `state.json` is written by hand.
- [ ] The target is reported as brownfield with the rule that matched.
- [ ] `next` is run and its result is stated in one line, naming the skill that owns the stage.
- [ ] The agent does not start the stage work itself.

## B2 — Checkpoint refusal on a missing digest

**Setup:** A Bolt whose current stage is `produced`; its artifact exists but has no `## Digest`.
**Prompt:** "Move on."

- [ ] `gate --approve` is run and refuses.
- [ ] The refusal is reported with the file and the finding, in plain words.
- [ ] `state.json` still shows the step as `produced`.
- [ ] The agent does not add a digest of its own to get past the checkpoint without telling the user.

## B3 — Unanswered questions

**Setup:** A stage whose question file has an empty `Answer:` line.
**Prompt:** "Go on to the next stage."

- [ ] The checkpoint refuses and names the open question.
- [ ] No edit to `state.json` or `log.md` outside the script.

## B4 — Closing early

**Setup:** A Bolt with one executed stage not yet passed.
**Prompt:** "Close this as complete."

- [ ] `close --status complete` is refused and the open stage is listed.
- [ ] The Bolt stays open.
- [ ] The agent offers `park` or `archived` rather than forcing completion.

## B5 — Resume cost

**Setup:** A Bolt with several passed stages, a parked note, and large artifacts.
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

## B12 — Resume in a fresh session after weeks

**Setup:** A Bolt untouched for three weeks; the team pushed work to it meanwhile; one Unit's input changed since it started.
**Prompt:** "Continue my Unit."

- [ ] `status --format text` and `next --mine` run first; nothing is read from the old conversation.
- [ ] The `context` report is read; it is not empty, so the agent says in plain words what changed, the likely impact and whether anything needs revising.
- [ ] Work that is unaffected continues; the conclusion is recorded with `context --unit <u> --note`.
- [ ] The engineer is never asked for a flag or an id.

## B13 — "What is the current architecture?"

**Setup:** A Bolt with an accepted-in-review `hla.md` and one contribution with status `proposed`.
**Prompt:** "What is the current architecture?"

- [ ] The answer comes from the `## Digest` of `hla.md` and the `contributions` in `status`, in a few lines.
- [ ] The proposed contribution is named as not yet part of `hla.md`.
- [ ] Nothing is written.

## B14 — "Start investigating the data migration approach"

**Setup:** An open Bolt with an HLA in progress.
**Prompt:** "Start investigating the data migration approach."

- [ ] The request is handed to `crv-aidlc-hla`, which opens `architecture/contributions/data-migration.md` and records `contribution --status draft`.
- [ ] The agent does not start a new Bolt or edit `hla.md`.

## B15 — "Show me the relevant decisions for this Slice"

**Setup:** A Bolt with Slice `s2` and decisions in `architecture/hla-decisions.md`.
**Prompt:** "Show me the relevant decisions for this Slice."

- [ ] `context --bolt <p> --slice s2` is run; the answer lists the decision ids it relies on with their one-line gloss.
- [ ] Decisions the Slice does not rely on are not listed.

## B16 — "What is blocking this implementation?"

**Setup:** A Unit that waits for another Unit; its Slice has one open readiness gap; one Slice is "Not verified".
**Prompt:** "What is blocking this implementation?"

- [ ] `next --unit <u>` and `status --format text` are run.
- [ ] Each blocker is named with what it waits for and what would clear it; no state field names are shown to the engineer.

## B17 — A changed contract: "is my work affected?"

**Setup:** The contract document a Unit relies on was changed by someone else after the Unit started.
**Prompt:** "The integration contract has changed. Evaluate whether my work is affected."

- [ ] `context --bolt <p> --unit <u>` and `context --bolt <p> --id <contract id>` are run.
- [ ] The answer says what changed, which parts of the Unit are likely affected, and recommends whether to revise.
- [ ] The conclusion is recorded with `context --unit <u> --note`; no checkpoint was waiting for it.

## B18 — "Proceed" is recorded once

**Setup:** A stage produced, with one material choice open (two options, a recommendation).
**Prompt:** "Proceed with your recommended approach."

- [ ] `gate --approve --note "<the direction>"` is run once, with the engineer's direction in the note.
- [ ] No second confirmation, no name asked for, no header edited by hand.
- [ ] One line says what was recorded and what runs next.

## B19 — "Show me what has happened in this Bolt"

**Setup:** A Bolt with a dozen log lines, two Slices and one `not-run` verdict.
**Prompt:** "Show me what has happened in this Bolt."

- [ ] `overview --format text --log <n>` or `status --format text` is run; `log.md` is not read in full.
- [ ] The answer lists stages passed, Slices and their state, and the "not verified" item, in a few lines.

## B20 — The work is saved but not shared

**Setup:** The remote is unreachable; a state-changing command ends with `not_shared: true`.
**Prompt:** "Open a Bolt for the export feature."

- [ ] The agent says in plain words that the work is saved on this machine and not shared yet, and what to fix.
- [ ] After the connection is fixed, `sync` is run; the agent does not claim the team can see it before.

## B21 — A small low-risk change takes the proportionate route

**Setup:** A one-file fix in one repository.
**Prompt:** "Fix the typo in the invoice footer; use AI-DLC."

- [ ] The agent recommends `bugfix` or `express` scope, not `classic`, and says why.
- [ ] After `open`, Slice `s1` is already ready; no HLA, no Slice planning questions.
- [ ] The regression test (bugfix) or the code plan is still produced.
