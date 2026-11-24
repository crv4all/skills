# Delivery planning

Plans the sequence of Slices. A Slice is a planned group of one or more dependency-linked units that Construction builds together. This stage plans grouping, order and proof; it does not choose which Construction stages run, which is decided per unit when its construction starts.

## Runs when / skipped when

Runs whenever Units Generation ran; skipped in `bugfix`. It is the last Inception stage, so it also runs the traceability check before its gate.

## Reads

As listed by `aidlc_state.py inputs --stage delivery-planning`:

- `docs/inception/units-generation/` files: the units, graph and story map that order the Slices;
- `contract-summary.md`: contracts that block or enable a Slice;
- `requirements.md` and `stories.md`: value, risk and what each Slice must prove;
- `components.md`: the components inside each unit.

## Question categories

Gloss "Slice" in a clause the first time it appears in the question file.

- **What first**: risk, value, a thin end-to-end slice, or a mix. "Should the first Slice prove the riskiest unit or deliver the thinnest working path?"
- **Scoring**: a model such as value over size with weights. "Which weighs more here, value, urgency or risk reduction?"
- **Slice size**: "How many units or weeks should one Slice hold?"
- **Parallel or serial**: "Can two Slices run at once, and who would build each?"
- **External dependencies**: owner, lead time, which Slice each blocks, fallback. "What do you need from another team before Slice 2, and by when?"
- **Biggest worry**: "What is most likely to make this plan wrong?"
- **Per Slice**: its units; whether it is the walking skeleton (the thin first slice through every layer); the definition of done; what shipping it proves; who builds it. "What must a reviewer see to call this Slice done?"
- **Verification command**: the one command that checks the inception artifacts and later each Slice. "Which command should prove the Slice works?"

## Settles

Which units form each Slice, their order and why, definition of done, confidence per Slice, owners, external dependencies and the verification command.

## Steps

1. Ask and analyse.
2. Order the Slices by the dependency graph; justify every departure from it in the rationale.
3. State each Slice's confidence as a hypothesis: what must be true, and how early to know.
4. Write the artifacts.
5. Run the traceability check (see the main skill) and fix every gap it reports; refuse to gate while any remains.
6. Show the verification command to the approver and get it approved explicitly before the gate. Load the Slices into state as the entry skill describes.
7. After the gate, load the Slices: write `{"slices": [{"id": "s1", "units": ["u-1", "u-2"]}]}` to a file and run `aidlc_state.py units --bolt <p> --set <file.json>`.

## Writes

In `docs/inception/delivery-planning/`:

- `delivery-planning-questions.md` (and clarifications).
- `slice-plan.md`, starting with `## Digest`; per Slice `### Slice <n> <name>` with units (`U-n`), walking-skeleton marker, definition of done, confidence hypothesis, owner, and what the demo proves.
- `team-allocation.md`: who builds which Slice.
- `risk-and-sequencing-rationale.md`: why this order, and every departure from the graph.
- `external-dependency-map.md`: `| Dependency | Owner | Lead time | Blocks | Fallback |`.
- `docs/verification/phase-check-inception.md`: the approved command and the traceability result, pass or fail.

## After the gate

After the gate, file the epic and the unit stories as the Jira handoff in `SKILL.md` says.

## Good

Every unit is in exactly one Slice, each Slice ends in something a person can inspect, and the first Slice answers the biggest worry. A blocker has an owner, a date and a fallback.

## Common failure

A schedule dressed up as a plan: Slices with no definition of done, or an order that ignores the dependency graph.
