# Code generation

**Runs** always, per Unit; one default Unit in `bugfix`. Questions: none, plan approval is the question.

**Reads** as listed by `aidlc_state.py inputs --stage code-generation --unit <u>`: the Unit's design folders, `unit-of-work.md` and story map, `contract-summary.md`, `requirements.md`, `codekb/<repo>/code-structure.md` (the inventory of existing files, so nothing is duplicated).

## Part 1: the plan

`code-generation-plan.md`, approved before any code, in every scope including `express`.
1. Numbered checkbox steps; each names the files it creates or changes and what it serves (`US<g>.<s>`, `FR<n>`, `AC<g>.<s>.<c>`).
2. Tests come before the code they cover.
3. Brownfield: a `## Safeguards` block: what depends on the changed code, the recorded test baseline, the impact, the rollback plan.
4. `bugfix`: a regression test that fails before the fix and passes after.
5. `## Summary` (builds, touches, tests) and `## Assumptions`; write `unit-test-instructions.md` with a command for this Unit.

## Part 2: execution

1. Take the first unticked step.
2. Edit existing files in the target repo, in place; never `_new` copies. No code in the paddock.
3. Tick the step in the same turn.
4. If the plan is wrong, stop and change it first.

**Writes** in `docs/construction/<unit>/code-generation/`: `code-generation-plan.md`; `unit-test-instructions.md`; `code-summary.md` (files, decisions, tests not run and why, deviations); `source-manifest.json`; `traceability.json`. Each starts with `## Digest`.

**Good:** every ticked step names real files, and every story has a test.
