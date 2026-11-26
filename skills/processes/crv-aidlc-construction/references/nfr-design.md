# NFR design

**Runs when** nfr-requirements ran for this Unit. **Skipped when** it was skipped.

**Reads** as listed by `aidlc_state.py inputs --stage nfr-design --unit <u>`: `nfr-requirements/` (the targets to meet), `functional-design/` (where the logic sits), `contract-summary.md`, `components.md` (boundaries and failure domains).

**Questions:** resilience, scalability, performance, security and observability patterns; logical component boundaries (failure domains, blast radius).

**Steps**
1. Take patterns the HLA, TDD or an ADR fixed as given and cite them.
2. For each category, pick the pattern that meets each `NFR<n>.<m>` and say why.
3. Map logical components: what each owns, what fails with it, what it protects.
4. Keep technology-neutral where the infrastructure stage will decide the product.
5. Trace each `NFR<n>.<m>` to its solution.

**Writes** in `docs/construction/<unit>/nfr-design/`: `nfr-design-questions.md` (only if asked); `resilience-design.md`, `scalability-design.md`, `performance-design.md`, `security-design.md`, `observability-design.md`; `logical-components.md`; `traceability.json`. Each starts with `## Digest`.

**Good:** no `NFR<n>.<m>` is left without a solution or a stated reason.
