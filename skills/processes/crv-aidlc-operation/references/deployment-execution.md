# Deployment execution

**Runs when** Deployment Pipeline ran for this Slice. Nobody but a named person changes an environment: this stage hands out steps and records what comes back.

**Reads** all four Deployment Pipeline artifacts in full, through `aidlc_state.py inputs --stage deployment-execution --slice <s>`.

**Questions:** none. A failure is a stop, not a question.

**Steps**
1. Take the environments strictly in the release plan's order.
2. For each, confirm the preconditions table, then take the first unticked runbook step.
3. Hand it to the named person as a **HUMAN TASK** and wait for the result.
4. Record it in `deploy-log.md`, then tick the step in `runbook.md` in the same turn.
5. Never record a step as done without evidence from the person: pasted output, a link or a query result.
6. A failed check or a `Stop if:` condition stops the run. State the rollback option from `rollback-runbook.md` and record the person's decision.
7. After the last step of an environment, run its verification checks. Run one yourself only when it is read-only and the engineer allowed it for that environment; otherwise hand it over as a HUMAN TASK.
8. Do not hand out a step that removes or retires something until its quiet-period check is Met. After every change, run that environment's neighbour checks.
9. Do not start the next environment while any check of the previous one is Not met.
10. Suggest `park` between environments: the log is the resume point. To resume, continue from the first unticked step.

**Writes** in `docs/slices/<slice>/deployment-execution/`. Each starts with `## Digest`.
- `deploy-log.md`: `| Step | Environment | Run by | When (UTC) | Result | Evidence |`.
- `verification-results.md`: `| VC-n | Environment | Expected | Actual | Verdict (Met, Not met, Explained) | Signed by |`. An Explained difference needs a named person in `Signed by`.

The **checkpoint** (`gate --stage deployment-execution --slice <s> --approve`) comes after the last environment's verification. The summary lists every check that is Not met or Explained, and says whether the support window has started and when it ends.

**Good:** every ticked step has evidence in the log, and every check has a verdict.
