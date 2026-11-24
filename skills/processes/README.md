# Layer: processes

**End-to-end workflows — what we deliver.** A process skill owns a whole unit of
work: it takes an ambiguous request, runs a defined sequence of phases, and
produces a named deliverable that can be checked against a contract.

## A skill belongs here when

- There is a deliverable someone would review, and it can be described
  precisely enough to validate.
- The work has phases whose order matters, and skipping a phase produces
  plausible-looking but wrong output.
- It benefits from stopping to gather evidence before it decides anything.

## A skill does not belong here when

- It is one step of somebody else's workflow → `patterns/`
- It has no reviewable output → `knowledge/` or `utilities/`

## Expectations for this layer

- **State the output contract up front**, in the SKILL.md body, as a checkable
  list. Not "produce documentation" but "these files exist, each has these
  sections, every claim carries evidence".
- **Separate evidence gathering from interpretation.** Where the evidence can be
  gathered deterministically, gather it with a script that decides nothing, then
  interpret it in a later phase.
- **Validate before declaring done**, and loop on failure rather than reporting
  a partial result as complete.
- **Never claim a step ran that did not run.** If a check was skipped, the
  skill says which one and why.

## Skills in this layer

| Skill | Purpose |
| --- | --- |
| [`crv-aidlc`](crv-aidlc/SKILL.md) | Open, resume, route and close a Bolt, with approval gates enforced by script |
| [`crv-aidlc-hla`](crv-aidlc-hla/SKILL.md) | Write and sign off the high-level architecture of a Bolt in three question rounds |
| [`crv-aidlc-tdd`](crv-aidlc-tdd/SKILL.md) | Decide whether a technical design document is needed, then write it from the accepted HLA |
| [`crv-aidlc-reverse-engineering`](crv-aidlc-reverse-engineering/SKILL.md) | Build or refresh the shared code knowledge of an existing repository before the architecture is written |
| [`crv-aidlc-inception`](crv-aidlc-inception/SKILL.md) | Turn the accepted HLA into requirements, stories, a domain design, units, contracts and a Slice plan |
| [`crv-aidlc-construction`](crv-aidlc-construction/SKILL.md) | Build each Unit from an approved code plan, then run build and test |
| [`crv-codebase-onboarding`](crv-codebase-onboarding/SKILL.md) | Produce durable, evidence-backed codebase context in `docs/codebase/` |
| [`crv-create-skill`](crv-create-skill/SKILL.md) | Take a skill idea through boundary test, interview, scaffold, validation, and evals |
