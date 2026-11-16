# TDD question round, section by section

One question file, `architecture/tdd-questions.md`, organised by TDD section. The TDD adds detail the delivery team needs to build and run the system; it does not reopen what the HLA decided.

## Before asking

- Read `hla.md` in full and `hla-decisions.md`. For each section below, list the HLA decisions that bind it.
- Read the knowledge digest and code-knowledge digests only for detail the HLA did not carry (field names, volumes, current settings).
- A question the HLA, an accepted ADR or the inputs already settle is not asked.

## File shape

```text
# TDD questions
## Carried from the HLA      section -> HLA decision ids and ADR ids that bind it (cited, not asked)
## Section: <name>           a Proposal: paragraph (at most four lines), then ## Q<n> questions
...
## Already answered          question: answer (source)
```

Two to four questions for a section that needs them, none for a section the HLA settles. Skip a section that does not apply with one line under `## Already answered` saying why (for example: no interface changes in this delivery). Cite answers as `T-Q3` and clarifications as `TC-Q1`.

If the delivery has parts that differ substantially (separate services, owners or release dates), ask once whether to split into `tdd-<part>.md` files, recommending one file unless the parts share almost nothing.

## Sections and what to ask

**Overview and scope.** Settles the delivery's boundary and the HLA decisions it implements. Ask only when the HLA's first release slice is ambiguous: which journeys ship in this delivery, what is deferred.

**Detailed architecture.** Settles component responsibilities for this delivery and at most two critical flows. Ask: which existing component changes and how; where a new responsibility sits when the HLA names only the container; the failure path of each critical flow. A new container is an HLA change, not a TDD answer.

**Interfaces and contracts.** Settles the schema location and version of each API, event or file; compatibility and deprecation; error model; retries and backoff; idempotency. Ask: contract-first or code-first; how long an old version is served; which operations must be idempotent and by which key; what a consumer sees on a partial failure; whether ordering matters.

**Data design.** Settles new or changed schemas, keys and indexes, partitioning, lifecycle, lineage and owner. Ask: which queries the indexes serve; partition key and expected skew; how deletion and archival run; how a schema change is rolled out without downtime; who owns the data once live.

**Security design.** Settles threats with mitigations for what this delivery adds, roles and scopes, secrets, encryption, audit events. Ask: the permissions each role needs and nothing more; where secrets live and how they rotate; which events are audited; any threat the HLA listed that needs a concrete control here.

**Reliability and operations.** Settles service levels, capacity limits, resilience settings with values, backup and restore with a test cadence, runbooks and the operating team. Ask: timeout and retry values per dependency; what happens under overload (shed, queue, slow down); restore test frequency; who is called when it breaks.

**Observability.** Settles metrics, log fields and correlation id, traced spans and sampling, alert versus ticket. Ask: which metric shows the HLA outcome; which condition wakes a person and which can wait for working hours; sampling rate under peak load.

**Performance and cost.** Settles load assumptions, targets at P50, P95 and P99, how they are tested, cost drivers and a guardrail. Ask: peak shape (steady, daily spike, month end); the pass mark of the performance test and where it runs; the cost line that would trigger a redesign.

**Testing and validation.** Settles test types with scope and pass criteria. Ask: which contract tests guard each interface; which failure scenarios are exercised before release; data-quality checks and their thresholds; security scanning in the pipeline.

**Release readiness.** Settles preconditions, what is watched during release, rollback triggers and steps, and roles. Ask: feature flag or deploy-based release; the measured value that triggers rollback; who approves the release and who may roll back.

**Post-release validation.** Settles what is checked after release, by whom, when, and the result that triggers rollback or a fix-forward. Ask: which checks run at one hour, one day and one week; who signs that the release is healthy; when the old path can be switched off.

**Risks and mitigations.** Settles delivery risks with owner and whether each blocks release. Ask: which risk would stop the release; who owns each mitigation.

**AI input block.** Usually derived, not asked: the task list, constraints, definition of done and post-release checks restate the answers above. Ask only to confirm task boundaries when two readings are possible.

## Analysing answers

Besides the core-rules checks, compare each answer with the HLA decisions listed under `## Carried from the HLA`. A contradiction stops the round: it is an HLA change, not a TDD decision. An answer that only adds detail inside an HLA decision is recorded with that decision's id as part of its source (for example `T-Q4; refines D6`).
