# Round C: layers 9 to 12 and the review header

Round C decides how the change reaches production safely, shows that alternatives were weighed, names what could go wrong, and hands Inception a machine-readable summary. Open the file with the decisions from rounds A and B that constrain it. Most of Layer 12 and much of the header can be derived; ask only what cannot.

Same headings per layer as in the earlier rounds: **Settles**, **Reads**, **Ask from**, **Bound by**, **Good**.

## Layer 9: Modernization

**Settles:** the strategy (strangler, parallel run, phased by tenant or region, single cutover) and why; the transition state, meaning what runs side by side and for how long; data migration and how old and new are reconciled, with a tolerance; cutover criteria and steps; rollback triggers as thresholds and the rollback steps; the point of no return; what is retired, on what condition, when, and who decides; other teams that must move off the old system.

**Skip:** for greenfield work, put one line under `## Already answered` saying no system is replaced. Brownfield work that replaces nothing may also skip, with the reason.

**Reads:** the current system in code knowledge; migration constraints and dates in the digest; retirement, strangler, handover and temporary-exception ADRs.

**Ask from:**

- Which strategy, given the risk and the date?
- How long do old and new run together, and who watches the difference?
- What difference between old and new output is acceptable?
- Which measured value triggers a rollback, and who calls it?
- After which step is rollback no longer possible?
- What retires the old system: a date, a usage threshold, or a sign-off?

**Bound by:** retirement and sunset decisions, migration patterns, temporary exceptions.

**Good:** rollback triggers are values someone can watch on a dashboard, and the point of no return is named. Every legacy component has a retirement condition.

## Layer 10: Architecture options considered

**Settles:** two or three real alternatives, including extending what exists where that is credible; the criteria they are judged on, drawn from Layers 1, 6 and 7 (outcome, service levels, security, cost, team skills, lock-in, time to deliver); why the chosen design wins; what would reopen the choice.

**Skip:** when no credible alternative exists, say why under `## Already answered`.

**Ask from:**

- Are these the alternatives a reviewer would raise? Which is missing?
- Which criterion weighs most here?
- What would make you revisit the choice in a year?

**Good:** each rejected option lost for a specific, stated reason; there are no straw men. The revisit condition is concrete.

## Layer 11: Risks

**Settles:** the top five risks (technical, delivery, operational, security, organisational), ranked by likelihood and impact; a mitigation and an owning role for each; every departure from an accepted ADR, which is always a risk; the decisions the reviewers must make (`decision_needed`) and by when (`decision_deadline`).

**Ask from:**

- Is this the right top five, in the right order?
- Is the mitigation acceptable, or only a hope?
- Which of these needs a reviewer's decision rather than the team's?
- By what date must the reviewers decide?

**Good:** each mitigation changes likelihood or impact; "monitor" alone is not one. Each decision needed is phrased so reviewers can answer with a choice.

## Layer 12: AI input block

**Settles:** the hand-off to Inception, restating decisions as data: MUST and SHOULD constraints, each citing a decision or ADR id; interfaces (name, kind, producer, consumer, contract); acceptance criteria, testable and tied to the outcome and journeys; test expectations (load, security, recovery, data quality, contract) with thresholds; open items Inception must settle.

**Ask from:** usually only confirmation. "Is any MUST really a SHOULD?" "Is this threshold the pass mark?" New content here means an earlier layer was skipped: go back to it instead.

**Good:** every MUST traces to a decision or ADR, every criterion can fail a test, and nothing appears here that is not decided elsewhere.

## Review header

Derive what you can and show the derivation; ask the rest.

| Field | Source |
| --- | --- |
| `architecture_owner`, `reviewers` | Ask. Never invent a name; if unknown, leave the placeholder and say so. |
| `system`, `domains`, `capabilities`, `solution_type` | Layer 1 decisions |
| `impact_flags` | Derived: new store (5), public exposure (4, 7), new messaging (5), cutover (9), personal data (7), contract with another team (5), new technology (4); `none` only alone |
| `data_classification` | Layer 7 |
| `security_consultation_required` | Layer 7; ask if not settled |
| `review_level` | `pattern-check` only when flags are `none`, no exceptions, and a reference pattern is followed; otherwise `full` |
| `exceptions` | Derived from departures from accepted ADRs |
| `decision_needed`, `decision_deadline` | Layer 11 |
| `target_production_date`, `reference_pattern`, `repositories` | Ask, or from the digest |
| `adr_registry_commit` | The index's `registry_commit`, or `none` |
