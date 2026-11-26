# Code generation

**Runs** always, per Unit (one default Unit in `bugfix`). No questions: the plan is the question.

**Reads** per `aidlc_state.py inputs --stage code-generation --unit <u>`: the Unit's design folders, `unit-of-work.md`, story map, `contract-summary.md`, `requirements.md`, `codekb/<repo>/code-structure.md`.

## Part 1: the plan

`code-generation-plan.md`, shown first; the engineer says go before any code, in every scope.
1. Numbered checkbox steps, each naming its files and what it serves (`US<g>.<s>`, `FR<n>`, `AC<g>.<s>.<c>`).
2. Tests come before the code they cover.
3. Brownfield: a `## Safeguards` block: dependents, test baseline, impact, rollback plan.
4. `bugfix`: a regression test that fails before the fix and passes after.
5. `## Summary` and `## Assumptions`; `unit-test-instructions.md` with a test command for the Unit.

## Part 2: execution

Take the first unticked step; edit existing files in the target repo (no `_new` copies, no code in the Bolt); tick it in the same turn. If the plan is wrong, change it first.

**Writes** in `docs/construction/<unit>/code-generation/`: the plan; `unit-test-instructions.md`; `code-summary.md` (files, decisions, tests not run, deviations); `source-manifest.json`; `traceability.json`. Each has a `## Digest`. `code-summary.md` holds one `Verdict:` line (see `SKILL.md`), written after the Unit's tests ran.

**Good:** every ticked step names real files; every story has a test.
