# Units generation

Divides the work into units that can be planned, built and verified separately, each with a kind, a place in a dependency graph and the stories and requirements it delivers.

## Runs when / skipped when

Runs in `classic` and `express` scopes (in `express` from requirements, since there are no components). Skipped in `bugfix`. The plan is shown mid-stage; the checkpoint follows at the end.

## Reads

As listed by `aidlc_state.py inputs --stage units-generation`:

- `components.md` and `decisions.md`: the boundaries units normally follow;
- `requirements.md` and `stories.md`: what each unit must cover;
- `architecture/hla.md` `## Digest`: deployment boundaries and the technology each unit uses.

## Question categories

Cover the categories where something material is open; the rest is settled from the inputs or assumed with a reason. No fixed count.

- **Boundary strategy**: unit per service, feature, domain or deployment target. "Is a unit one deployable, or one team's slice of several?"
- **Granularity**: how big a unit may be. "Should a unit fit within a few weeks of one team?"
- **Dependency ordering**: strict order, or in parallel where the graph allows. "Can the importer and the report start together?"
- **Integration points**: where units meet. "Which unit owns the shared table?"
- **Deployment model**: independent release or together. "Do these two ship in the same release?"
- **Story grouping**: which stories stay together. "Should all stories of one persona land in one unit?"
- **Team alignment and code organisation**: who owns each unit and where its code lives. "Which repository does each unit change?" Also ask what each unit waits for: another unit being done, or only its contract being agreed (`on: contract`).

## Settles

The units and their kinds, the dependency graph, which unit delivers every story and requirement, the integration points, and the deployment model of each unit.

## Steps

1. Ask and analyse.
2. Present the plan: strategy, unit count, dependency shape, kinds, with your recommendation. When the engineer says go, or has no objection, write the artifacts; otherwise revise it.
3. Assign each unit a kind: `service`, `spec`, `ui`, `packaging` or `library`. The kind decides which Construction artifacts it owes later, so ask when it is not obvious.
4. Write units, graph and story map. The graph must have no cycles; break a cycle by moving the shared part into a unit of its own.
5. Give no build order or critical path here; that is Delivery Planning's.
6. After the checkpoint, load the Units: write `{"units": [{"id": "u-1", "name": ..., "kind": ..., "repo": ..., "depends_on": ["u-2", {"unit": "u-3", "on": "contract"}]}]}` to a file (the id is the lower-case form of `U-n`; it names the Unit's construction folder) and run `aidlc_state.py units --bolt <p> --set <file.json>`. It adds new Units and updates only the keys the file gives; Units it does not mention are untouched. Set owners with `assign --unit <u> --owner <name>`. To split or replace a Unit later: `units --cancel <u> --reason "<why>" --superseded-by <new ids>`, then add the new ones. A refusal lists the findings.

## Writes

In `docs/inception/units-generation/`:

- `units-generation-questions.md` (and clarifications).
- `unit-of-work.md`, starting with `## Digest`; per unit `### U-n <name>` with kind, responsibilities, deployment model, size (S to XL), the repository it changes and the components it holds.
- `unit-of-work-dependency.md`: the graph in prose, integration points, parallel sets, and a fenced `yaml` block `units:` with `name`, `kind`, `depends_on` per unit.
- `unit-of-work-story-map.md`: a table `| Item | Unit |` with one row per `US-n` (or per `FR-n` when there are no stories), the id in the first cell, the unit as `U-n`. Every `FR-n` appears in a story row or its own row.

## Good

Every story and requirement lands in exactly one unit, every unit has a reason to exist, and the graph reads as a build order without being one. Kinds are chosen on purpose, not defaulted.

## Common failure

A unit that is a layer (all the databases) instead of a slice, producing cycles and stories split across units.
