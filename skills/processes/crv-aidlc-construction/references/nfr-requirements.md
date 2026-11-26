# NFR requirements

**Runs when** the Unit needs quality targets or stack choices beyond what the HLA, TDD and requirements already fix. **Skipped when** they cover it; the skip reason cites them.

**Reads** as listed by `aidlc_state.py inputs --stage nfr-requirements --unit <u>`: `functional-design/` (the load and data to size), the NFR section of `requirements.md` (targets already set), `contract-summary.md` (interface limits), `codekb/<repo>/technology-stack.md` (current stack).

**Questions:** performance, security, scalability, reliability, observability, technology stack. Ask for numbers, never adjectives.

**Steps**
1. List the targets already fixed and cite them (`NFR<n>`, `D<n>`, ADR id).
2. Assess the five categories; ask only where a number or choice is missing.
3. Turn each answer into an item with a measurable target and an id `NFR<n>.<m>`.
4. Record stack choices with the reason and the alternative given up.
5. Keep brownfield stacks unless an answer or ADR changes them.

**Writes** in `docs/construction/<unit>/nfr-requirements/`: `nfr-requirements-questions.md` (only if asked); `performance-requirements.md`, `security-requirements.md`, `scalability-requirements.md`, `reliability-requirements.md`, `observability-requirements.md`; `tech-stack-decisions.md`; `traceability.json`. Each starts with `## Digest`.

**Good:** every item has a number and a source; none contradicts the HLA.
