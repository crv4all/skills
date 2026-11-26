# Group A: layers 1 to 3

Group A fixes what the system is for and what it is about. Every later layer is judged against it, so a vague outcome here produces a design that cannot be reviewed. Spend the questions on what the documents leave open; the digest usually answers more than it seems.

For each layer below: **Settles** is what must be decided by the end of the group. **Reads** is where answers are usually found already. **Ask from** are prompts to draw questions from, not a script: ask only what changes the design. **Bound by** names the ADR topics that typically constrain the layer. **Good** is the bar the layer must clear.

## Layer 1: Business context and scope

**Settles:** the problem in the business's own terms and who has it; what it costs today; the outcome as a measurable change with a date; what forces the timing; deliverables in scope for the first release and later; what is explicitly out; assumptions that would change the design if false; `solution_type`; `system`, `domains` and `capabilities` for the header.

**Reads:** goals, pain points, road maps and contracts in the knowledge digest; current-state facts in code knowledge; strategy, consolidation and retirement ADRs.

**Ask from:**

- Which metric shows success, and what value by when?
- What forces the date: a contract, end of support, a cost ceiling, a regulation?
- Which capabilities must be in the first release, and which can follow?
- Which neighbouring systems are deliberately left unchanged?
- What is assumed about identity, regions, tenancy and volume? What breaks if wrong?
- Does this replace something (modernization), extend something (brownfield), or neither (greenfield)?

**Bound by:** platform strategy, retirement and sunset decisions, central-system-of-record decisions, build-versus-buy.

**Good:** the outcome is a number with a date and a source. Scope lists things a reviewer could check were delivered, and every assumption can be proved false.

## Layer 2: Domain model

**Settles:** the core concepts and their relationships; the aggregates and the invariants each protects; bounded contexts and which team or system owns each; the source of truth for every key entity; terms used differently by different groups, and the meaning adopted; identity of the main entities (natural or generated key); the lifecycle states of the central entity.

**Reads:** glossaries and ubiquitous-language documents in the digest; data and domain findings in code knowledge; ADRs on systems of record and data ownership.

**Ask from:**

- Which system is the source of truth for each key entity, and does that change?
- Is this concept part of an existing context, or a context of its own?
- Which rule must never be broken (for example, two active records for one subject)?
- Is an entity identified by a business key or a generated one, and who issues it?
- Which term means different things to different teams, and whose meaning wins?
- What states does the central entity pass through, and who moves it?

**Bound by:** system-of-record, master-data and data-ownership decisions; any published glossary.

**Good:** one picture in which every box is a noun the business uses and every concept has exactly one owner. A newcomer reading the term table would use the words the same way the experts do.

## Layer 3: Users, journeys and flows

**Settles:** the actors, people and systems; the three to five journeys or data flows that matter, each from trigger to result; which steps are synchronous and which asynchronous; what the user sees when a step fails; manual steps that remain; the order in which journeys ship (the first release slice).

**Reads:** process descriptions and user research in the digest; existing entry points and jobs in code knowledge; integration-style and messaging ADRs.

**Ask from:**

- Who or what starts each flow, and how often?
- Which step must answer while the user waits, and which can finish later?
- When a downstream step fails: retry, compensate, or tell the user?
- Request and response, events, or scheduled batches for each hand-off?
- Which journey ships first, and what is the smallest version that proves the outcome?
- Which manual steps stay manual in the first release?

**Bound by:** integration-style decisions (push versus batch, events versus calls), messaging platform choices, user-interface framework decisions.

**Good:** each flow is named trigger to outcome, every step has an owning system, and the failure path is written down. The first release slice is named and tied to the Layer 1 outcome.

## Group A file notes

- The context summary and the ADR shortlist go at the top of this file only; groups B and C reuse them.
- A pure data or batch system with no human users still answers Layer 3 as data flows; do not skip it.
- If Layer 1 cannot name an outcome, stop after this group and say so: the rest of the design has nothing to be measured against.
