# Build and test

**Runs** once per Slice, after its Units are done (`next --bolt <p> --slice <s>`). Never skipped, never deploys. It runs the commands; instructions alone are not enough. Unit tests belong to Code Generation; this covers integration between the Slice's Units and what the requirements or NFRs demand.

**Reads** via `aidlc_state.py inputs --stage build-and-test --slice <s>`: each Unit's `code-generation/` folder, the NFR targets, the Slice plan, the baseline.

**Questions:** none.

**Steps**
1. List the targets: requirements, NFRs, cross-Unit integrations.
2. Run the build per repo, each distinct test command once, coverage once per repo.
3. Compare with the baseline; new failures are regressions.
4. Record each target as Met, Not Met or Unverified, with command and result.
5. On failure: report it, fix, loop back to the owning stage. The stage stays open until a run passes.
6. Check cross-Unit traceability.

**Writes** in `docs/slices/<slice>/build-and-test/`, each starting with `## Digest`: `build-instructions.md`; `build-and-test-summary.md` (`## Target Verification Matrix`); `test-results.md` (`## Loop-Back Log` and the `Verdict:` line); `cross-unit-traceability.md`. `step`, `gate` take `--slice <s>`.

**Good:** every target has a verdict backed by a command that ran.
