# Domain design

Decides the components of the new system, what each owns and how they interact. Replaces the older application design: a component catalogue and a decision log, no method-level detail.

## Runs when / skipped when

Runs when new components or new ownership boundaries are needed. Skipped when only existing components change; then say which components and why no boundary moves.

## Reads

As listed by `aidlc_state.py inputs --stage domain-design`:

- `requirements.md` and `stories.md`: what the components must support;
- `architecture/hla.md` and `hla-decisions.md`: the containers, technology and domain model already decided;
- `codekb/<repo>/` architecture, component inventory, dependencies: what exists and may be reused.

## Question categories

Cover all; scale to depth.

- **Component boundaries**: where to cut and why. "Should billing rules sit with orders or in their own component?"
- **Entity ownership**: exactly one owner per entity. "Which component is the source of truth for a customer account?"
- **Responsibilities**: what each does and does not do. "Who validates the incoming file, the receiver or the processor?"
- **Interactions**: who calls whom, sync, async or event, and why. "Must the caller wait for the result?"
- **Integration with existing components**: reuse, extend or replace. "Extend the existing importer or build a new one?"
- **UI structure**: screens or components per persona, when a UI exists. "Is this one application or several entry points?"
- **Decomposition choice**: when more than one split works, ask which, showing pros, cons and how hard each is to reverse.

Technology already decided by the HLA or an accepted ADR is not asked; cite it.

## Settles

The component catalogue; entity ownership; dependencies and their direction; reuse versus new; every decision this stage makes, with its reason.

## Steps

1. Ask and analyse. Anything the HLA fixed is cited as `D<n>` or ADR id.
2. Write the catalogue first, then derive the diagram and tables from it so they cannot disagree.
3. For any contested split, show the alternatives with pros, cons and reversibility and a recommendation.
4. Check: the dependency graph has no cycles, every dependency has its inverse as a dependent, one owner per entity, infrastructure is not a component.
5. Record decisions with ids from `aidlc_state.py decision-id`.

This stage does not choose topology, stack or non-functional patterns; those are the HLA's, or a unit's.

## Writes

In `docs/inception/domain-design/`:

- `domain-design-questions.md` (and clarifications).
- `components.md`, starting with `## Digest`, then a fenced `yaml` catalogue (per component: `name`, `summary`, `behaviour`, `responsibilities`, `depends_on` with kind sync/async/event, `dependents`, `external_dependencies`, `entities` with identifier, attributes and references), then `## Component diagram` (Mermaid and text), `## Component summary`, `## Entity ownership`, `## External dependencies`, `## Rationale` with alternatives rejected. Each component also covers the requirements it serves (`FR-n`).
- `decisions.md`: a `## Digest`, then `### D<n> <title>` per decision with Context, Decision, Consequences, Alternatives rejected. Use the paddock `D<n>` sequence; never `ADR-NNN`, which belongs to the ADR registry.

## Good

Every entity has one owner and every requirement is served by a named component. A reviewer can find the reason for each boundary in a decision that cites its sources.

## Common failure

Re-deciding the HLA's containers or technology under a new name, or recording decisions as `ADR-NNN`.
