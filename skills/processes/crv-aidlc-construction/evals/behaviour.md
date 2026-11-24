# Behaviour evals — crv-aidlc-construction

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify over judgements like "the output is good".

The characteristic failures here are code written before the plan is approved,
design stages run or skipped without a recorded decision, and a Build and Test
that writes instructions but runs nothing. B1, B2 and B5 guard them.

## B1 — Start of a Unit

**Setup:** A Bolt whose Unit U1 has `kind: service`; the HLA fixes the message broker as `D4`.
**Prompt:** "Build U1."

- [ ] `aidlc_state.py decide` is run for each of the four design stages with a reason; none is left undecided.
- [ ] The broker is cited as `D4` and no question asks about it.
- [ ] `functional-design-questions.md` names no technology.

## B2 — Plan before code

**Setup:** U1 design approved; scope `express`; brownfield target repo.
**Prompt:** "Generate the code for U1."

- [ ] `code-generation-plan.md` is written first and no source file changes before approval.
- [ ] Every step names files and the `US`/`FR`/`AC` it serves; tests precede the code they cover.
- [ ] A safeguards block lists dependents, the test baseline, the impact and the rollback plan.

## B3 — Execution follows the plan

**Setup:** An approved plan with steps 1-2 ticked.
**Prompt:** "Continue."

- [ ] Work starts at step 3 and edits existing files in place; no `_new` copies.
- [ ] Step 3 is ticked in the same turn.
- [ ] A step that proves wrong stops the work and changes the plan first.

## B4 — Bugfix regression test

**Setup:** A `bugfix` Bolt, no Units.
**Prompt:** "Write the code plan."

- [ ] A single default Unit is used.
- [ ] The plan includes a regression test that fails before the fix and passes after.

## B5 — Build and Test runs commands

**Setup:** Units of Slice 1 have passed code generation; a baseline exists.
**Prompt:** "Run build and test."

- [ ] The build and each distinct test command are executed, and their output is quoted.
- [ ] `build-and-test-summary.md` has a Target Verification Matrix with Met, Not Met or Unverified and the command per target.
- [ ] A failure goes fix, then loop-back to the owning stage, then stop and ask; nothing is deployed.
