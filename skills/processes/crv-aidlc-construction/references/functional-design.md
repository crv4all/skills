# Functional design

**Runs when** the Unit adds a data model, complex logic or business rules. **Skipped when** the change is simple. Technology-free: no frameworks, stores or protocols.

**Reads** as listed by `aidlc_state.py inputs --stage functional-design --unit <u>`: the Unit's entry and story-map rows with their `AC`s (what to cover), `requirements.md`, `components.md`, `contract-summary.md` (boundaries to respect).

**Questions:** workflows and algorithms; domain model; rules and validation; data flow; integration points; errors and edge cases; frontend components (UI only); scenarios (happy, unhappy, concurrent).

**Steps**
1. Answer from the HLA, requirements and `codekb/` first; ask only what is open.
2. Model entities with types, constraints and relationships.
3. Write each rule with an id `BR<g>.<s>`: category, trigger, IF/THEN, behaviour on violation, source.
4. Describe workflows and state machines; snippets of at most 15 lines of pseudocode.
5. Trace every `AC` to the rules that satisfy it.

**Writes** in `docs/construction/<unit>/functional-design/`: `functional-design-questions.md` (only if asked); `entities.md` (YAML); `rules.md` (YAML); `functional-spec.md` (workflows, state machines, ER and rules views); `frontend-components.md` (UI only); `traceability.json` (`AC` to `BR`). Each starts with `## Digest`.

**Good:** every `AC` maps to a rule, and nothing names a technology.
