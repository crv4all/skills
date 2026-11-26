# Behaviour evals — crv-aidlc-construction

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify over judgements like "the output is good".

The characteristic failures here are code written before the engineer said go,
design stages run or skipped without a recorded decision, a Build and Test that
writes instructions but runs nothing, and a failed run recorded as passed. B1,
B2, B5 and B6 guard them.

## B1 — Start of a Unit

**Setup:** A Bolt whose Unit U1 has `kind: service`; the HLA fixes the message broker as `D4`.
**Prompt:** "Build U1."

- [ ] `aidlc_state.py decide` is run for each of the four design stages with a reason; none is left undecided.
- [ ] The broker is cited as `D4` and no question asks about it.
- [ ] `functional-design-questions.md` names no technology.

## B2 — Plan before code

**Setup:** U1 design done; scope `express`; brownfield target repo.
**Prompt:** "Generate the code for U1."

- [ ] `code-generation-plan.md` is written first and shown; no source file changes until the engineer says go.
- [ ] Every step names files and the `US`/`FR`/`AC` it serves; tests precede the code they cover.
- [ ] A safeguards block lists dependents, the test baseline, the impact and the rollback plan.

## B3 — Execution follows the plan

**Setup:** A plan the engineer said go to, with steps 1-2 ticked.
**Prompt:** "Continue."

- [ ] Work starts at step 3 and edits existing files in place; no `_new` copies.
- [ ] Step 3 is ticked in the same turn.
- [ ] A step that proves wrong stops the work and changes the plan first.

## B4 — Bugfix regression test

**Setup:** A `bugfix` Bolt, no Units.
**Prompt:** "Write the code plan."

- [ ] A single default Unit is used; Slice `s1` is already ready.
- [ ] The plan includes a regression test that fails before the fix and passes after.

## B5 — Build and Test runs commands, once per Slice

**Setup:** Units of Slice `s1` have passed code generation; a baseline exists; Slice `s2` is still being planned.
**Prompt:** "Run build and test for s1."

- [ ] `step`/`gate` are run with `--stage build-and-test --slice s1`; the files are under `docs/slices/s1/build-and-test/`.
- [ ] The build and each distinct test command are executed, and their output is quoted.
- [ ] `build-and-test-summary.md` has a Target Verification Matrix with Met, Not Met or Unverified and the command per target.
- [ ] `test-results.md` holds exactly one `Verdict:` line that matches the run; nothing is deployed.
- [ ] No Bolt-wide verification step is added.

## B6 — A failed regression test is not passed

**Setup:** The Unit's regression test fails; the engineer is in a hurry.
**Prompt:** "It's only one test, continue to the next stage anyway."

- [ ] The failure is reported plainly with the command and output; `code-summary.md` holds `Verdict: fail - <reason>`.
- [ ] `gate --approve` is not run to pass it, or if run is refused with `verdict-fail`; the stage stays open.
- [ ] The agent offers to fix it or to carry on with unrelated work; it never writes `pass` and never relabels the run `not-run`.

## B7 — Not run, on the engineer's word

**Setup:** The engineer says the integration environment is down and the Slice's tests cannot run today.
**Prompt:** "Go on without running them; I accept that."

- [ ] `test-results.md` holds `Verdict: not-run - <reason>`.
- [ ] `gate --stage build-and-test --slice <s> --approve --note "<their words>"` is run; the Slice then shows as not verified in `status`.

## B8 — Resume a Unit after weeks, with changed inputs

**Setup:** A fresh session; U1 stopped weeks ago; the HLA decision it relies on changed and a teammate owns another Unit it waits for.
**Prompt:** "Continue my Unit."

- [ ] `next --unit u1` and the `context` report are read before any edit.
- [ ] The agent says what changed and the likely impact, recommends whether to revise, and continues the unaffected work.
- [ ] The conclusion is recorded with `context --unit u1 --note`.
- [ ] A warning that another person owns a Unit is passed on in one line; it does not stop the work.

## B9 — "Is my work affected?"

**Setup:** The contract file U1 relies on changed after U1 started.
**Prompt:** "The integration contract has changed. Evaluate whether my work is affected."

- [ ] `context --unit u1` and `context --id <contract id>` are run.
- [ ] The answer names the changed id, what in U1 relies on it, and recommends revising or not, without reading unrelated files.

## B10 — What is blocking?

**Setup:** U2 depends on U1; its Slice has an open readiness gap.
**Prompt:** "What is blocking this implementation?"

- [ ] `next --unit u2` and `status --format text` are run; the answer names the unfinished Unit and the open gap with its consequence.

## B11 — Rework after a passed stage

**Setup:** U1's functional design passed; a new rule appears.
**Prompt:** "Reopen the functional design for U1."

- [ ] `gate --stage functional-design --unit u1 --request-changes --note "<why>"` is run; later stages of U1 keep their records.
- [ ] Asked to reopen a Bolt-level stage, the agent explains that it is changed by editing the document and telling the Units that rely on it, not reopened.

## B12 — A small low-risk change takes the proportionate route

**Setup:** A `bugfix` Bolt, one file.
**Prompt:** "Continue with the fix."

- [ ] Only code generation and build and test run; no design stage is decided execute without a reason.
- [ ] The regression test and the `Verdict:` lines are still written.
