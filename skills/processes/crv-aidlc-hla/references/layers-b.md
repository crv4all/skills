# Group B: layers 4 to 8

Group B turns the purpose and domain from group A into a structure. Open the file with the group A decisions that constrain it. The common failure here is choosing technology before the responsibilities are clear; propose responsibilities first, then the technology for each, citing the ADR that settles it.

Same headings per layer as in group A: **Settles**, **Reads**, **Ask from**, **Bound by**, **Good**.

## Layer 4: Proposed architecture

**Settles:** the system context (people, the system, external systems); the containers, meaning each deployable unit and data store; one responsibility and one owner per container; the end-to-end flow that matters most; the technology of each container with its basis; the deployment boundary (cloud, region, network zone); which existing components are reused or extended.

**Reads:** current components and their technology in code knowledge; reference designs in the digest; hosting, API, orchestration and messaging ADRs.

**Ask from:**

- One deployable unit or several, and what justifies each split?
- Extend an existing component, or build a new one?
- Calls or events between these two containers?
- Where does the business logic of the central entity live?
- Which hosting option, and does an accepted ADR already decide it?

**Bound by:** hosting and platform, API layer technology, workflow orchestration, messaging backbone, application frameworks.

**Good:** every container has one responsibility sentence and one owner, and every technology choice cites an ADR id or a decision id. Nothing exists only "for later".

## Layer 5: Data and integration

**Settles:** new or changed data stores (type, owner, reason); the model of new or changed entities; every interface with producer, consumer, kind (API, event, file), format, contract location and versioning rule; data quality dimensions checked and where; retention and deletion rules with their basis; lineage; backfill or migration of existing data; whether personal data is involved.

**Reads:** schemas, jobs and integrations in code knowledge; data contracts and retention rules in the digest; serving-layer, ingestion, streaming, data-sharing and tagging ADRs.

**Ask from:**

- Which store, and what makes it fit the access pattern?
- Is the contract written first, and where does it live?
- How do consumers survive a contract change (versioning, deprecation period)?
- Which quality checks (completeness, validity, timeliness, uniqueness, consistency) run, and where?
- How long is each kind of data kept, why, and what deletes it?
- How is existing data brought across, and how is it reconciled?

**Bound by:** serving databases, ingestion frameworks, streaming and messaging, data sharing, catalog and workspace layout, replication, data tagging.

**Good:** only new or changed data appears. Each interface names producer, consumer, format and contract location, and each retention rule has a period and a trigger.

## Layer 6: Non-functional requirements

**Settles:** availability and how it is measured; latency at P95 and P99 for the flows from group A; throughput and data volume now and in two to three years; freshness for data products; recovery point and recovery time; observability (the few metrics that prove health and the outcome, tracing, what alerts); a cost guardrail; compliance obligations.

**Reads:** current volumes and incidents in code knowledge; service levels and budgets in the digest; performance and service-level ADRs.

**Ask from:**

- What does an hour of unavailability cost, and when does it hurt most?
- Peak versus average load, and the expected growth?
- How old may data be when someone reads it?
- How much data may be lost, and how fast must service return?
- Which metric shows the Layer 1 outcome is being met?
- What monthly or per-unit cost would make this a bad deal?

Offer numbers as options (for example 99.5, 99.9, 99.95) with the cost of each.

**Bound by:** service-level and performance decisions, observability standards, cost-management decisions.

**Good:** every target has a unit and a measurement point and comes from user impact, not habit. At least one metric ties back to the business outcome.

## Layer 7: Security and privacy

**Settles:** authentication for people and for services; the authorization model (roles, groups, scopes) and where it is enforced; secrets and key management; encryption in transit and at rest; personal and sensitive data (what, minimisation, masking, residency); audit events and their retention; the main threats and their mitigations; `data_classification`; `security_consultation_required`.

**Reads:** current identity and access setup in code knowledge; policies in the digest; identity, security-posture, network and least-privilege ADRs, including recorded exceptions.

**Ask from:**

- Which identity provider for people; which mechanism between services?
- Which roles exist, who grants them, and where is the check made?
- Where does personal data flow, and must it stay in a region?
- Which events are audited, for how long, and who can read the audit?
- Which threats matter most here (spoofing, tampering, disclosure, denial, privilege escalation), and what stops each?

**Consultation flag:** never assume it. It is true whenever the design touches authentication, authorization, roles, groups or machine-to-machine access, even when an ADR is followed. If the answers do not settle it, ask it as its own question, and base the recommendation on that trigger list, naming the trigger found, never on the absence of an identity discussion.

**Bound by:** identity and security posture, least-privilege exceptions, secrets management, network connectivity.

**Good:** every actor from Layer 3 has an authentication method and a permission set. Every flow that carries classified data states its encryption and audit.

## Layer 8: Developer experience

**Settles:** repositories and layout; local development and test environments; the test strategy per container (unit, contract, integration, data tests); build, release and rollback; environments and configuration; feature flags; generated clients or SDKs; onboarding documentation.

**Reads:** build files, pipelines and test layout in code knowledge; engineering standards in the digest; test-data, infrastructure-as-code and pipeline ADRs.

**Ask from:**

- New repository or an existing one, and why?
- How does a developer run and test this on a laptop?
- Which contract tests protect the interfaces from Layer 5?
- Which release mechanism, and how is a release rolled back?
- Where does test data come from, and is it safe to use?

**Bound by:** test data management, infrastructure as code, delivery pipelines, repository conventions.

**Good:** a new developer could find the code, run it and ship a change from this section alone. The release and rollback path is named.
