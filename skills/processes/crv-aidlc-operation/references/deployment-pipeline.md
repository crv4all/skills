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
- data migration or backfill steps;
- verification: smoke checks, reconciliation checks, and the tolerance (from the HLA or TDD; ask if neither sets one);
- rollback triggers and who decides;
- the point of no return;
- retirement and clean-up after verification;
- which read-only checks the agent may run, per environment.

**Steps**
1. Ask, analyse, then write the artifacts. Cite `D<n>` or ADR ids; never re-ask what they fixed.
2. A step with no named person is not ready: ask.

**Writes** in `docs/operation/deployment-pipeline/`. Each starts with `## Digest`.
- `release-plan.md`: environments in order; per repository the existing release mechanism; the order; windows; who is informed.
- `runbook.md`: a preconditions table `| Check | Owner | How verified |`, then numbered checkbox steps. Each step has: environment, who, the exact action (command or UI action), expected result, evidence to capture, and `Stop if:`. Mark the point of no return exactly once, or state that there is none.
- `rollback-runbook.md`: triggers as thresholds a person can watch, citing the HLA or TDD decision ids; steps; until when rollback is possible; who decides.
- `verification-checks.md`: `| VC-n | Kind (smoke, reconciliation) | What | Query or command | Expected | Tolerance | Environment |`. Ids are never renumbered.

**Good:** a person who did not write it can run every step and knows when to stop.
