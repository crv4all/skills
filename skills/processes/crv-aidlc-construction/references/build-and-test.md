# Build and test

**Runs** once after the Units of a Bolt (or of the paddock). Never skipped. It runs the commands; writing instructions alone is not enough. It never deploys. Unit tests belong to Code Generation: this stage covers integration between Units and what the requirements or NFRs demand.

**Reads** as listed by `aidlc_state.py inputs --stage build-and-test`: every `code-generation/` folder (manifests, test commands), the `nfr-requirements/` and `nfr-design/` targets, and the recorded test baseline.

**Questions:** none. A failure you cannot fix is a stop-and-ask.

**Steps**
1. List the targets: requirements, NFRs and cross-Unit integrations.
2. Run the build in each target repo, each distinct test command once, and coverage once per repo.
3. Compare with the baseline; new failures are regressions.
4. Record each target as Met, Not Met or Unverified, with the command and its result.
5. On failure: fix, then loop back to the stage that owns the defect, then stop and ask.
6. Check cross-Unit traceability.

**Writes** in `docs/construction/build-and-test/`: `build-instructions.md`; `build-and-test-summary.md` (`## Target Verification Matrix`); `test-results.md` (`## Loop-Back Log`); `cross-unit-traceability.md`; integration, performance or security instructions when needed. Each starts with `## Digest`.

**Good:** every target has a verdict backed by a command that was run.
