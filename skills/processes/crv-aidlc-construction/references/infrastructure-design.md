# Infrastructure design

**Runs when** the Unit needs services, deployment or cloud resources designed. **Skipped when** it runs on existing infrastructure unchanged.

**Reads** as listed by `aidlc_state.py inputs --stage infrastructure-design --unit <u>`: `nfr-design/` and `nfr-requirements/` (what the resources must deliver), `functional-design/`, `components.md` (what is deployed), `contract-summary.md` (endpoints and events).

**Questions:** deployment; compute, storage and network; monitoring; CI/CD and rollback; secrets; scaling and cost.

**Steps**
1. Reuse what the HLA, TDD or an accepted ADR fixed; cite it.
2. Map each logical component to a resource; mark shared and existing ones.
3. Give sizes, scaling rules and a cost note per resource.
4. Define monitoring, alerts, pipeline stages and the rollback path.
5. Name where each secret lives; never write one.

**Writes** in `docs/construction/<unit>/infrastructure-design/`: `infrastructure-design-questions.md` (only if asked); `infrastructure-specification.md` (Deployment, Infrastructure Services and Shared Infrastructure tables); `monitoring-design.md`; `cicd-pipeline.md`; `traceability.json`. Each starts with `## Digest`. The IaC itself is written in Code Generation.

**Good:** every logical component lands on a named resource, in tables.
