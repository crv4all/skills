# Deployment pipeline

**Runs when** people must release or cut over the change: a data migration, a cut-over, a switch of write master, a retirement, or a release across several repositories. **Skipped, with the reason, when** each target repository's own pipeline releases on merge and nothing else has to happen. This stage plans; it designs no pipeline and runs nothing.

**Reads** as listed by `aidlc_state.py inputs --stage deployment-pipeline`: the Build and Test summary (what is verified), the Bolt plan and dependency graph (order), the HLA and TDD when they exist (tolerances, decision ids), and `technology-stack.md` per repo (how it releases today).

**Questions** (answer from the inputs first; ask only what is open):
- environments and their order;
- release mechanism per repository (confirm what the code knowledge shows);
- order across repositories and units;
- who runs each kind of step (names or roles);
- windows, freezes, and who is informed;
- preconditions;
- preparation before the first step: baselines to capture, a live check of anything the inputs mark `unverified`, instrumentation to add;
- data migration or backfill steps;
- verification: smoke checks, reconciliation checks, and the tolerance (from the HLA or TDD; ask if neither sets one);
- rollback triggers and who decides;
- the points of no return, per component or wave;
- what must not be removed or changed, and which neighbours' checks must still pass (shared artefacts, retained systems on the same pipeline);
- how consumers nobody listed are found, and the quiet period that must pass before a piece is removed;
- retirement and clean-up after verification, and the support window after it (how long, who watches, what ends it);
- which read-only checks the agent may run, per environment.

**Steps**
1. Ask, analyse, then write the artifacts. Cite `D<n>` or ADR ids; never re-ask what they fixed.
2. A step with no named person is not ready: ask.

**Writes** in `docs/operation/deployment-pipeline/`. Each starts with `## Digest`.
- `release-plan.md`: environments in order; per repository the existing release mechanism; the order; windows; who is told and when (advance notice to owners outside the team); the support window.
- `runbook.md`: a preconditions table `| Check | Owner | How verified |`, then numbered checkbox steps, preparation steps first. Each step has: environment, who, the exact action (command or UI action), expected result, evidence to capture, and `Stop if:`. Mark each point of no return and name its component; when there is none, say so. End with `## Do not remove`: the shared artefacts the answers named.
- `rollback-runbook.md`: triggers as thresholds a person can watch, citing the HLA or TDD decision ids; steps; what rollback means before and after each point of no return (for example a switch back, then a redeploy of the old version, then nothing); until when it is possible; who decides.
- `verification-checks.md`: `| VC-n | Kind | What | Query or command | Expected | Tolerance | Environment |`. Kind is `smoke`, `reconciliation`, `neighbour` or `quiet period`; a quiet-period check names the signal (calls, reads, messages), the threshold and the length of the period. Ids are never renumbered.

**Good:** a person who did not write it can run every step and knows when to stop.
