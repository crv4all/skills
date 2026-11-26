# Contract design

Defines the agreements at unit boundaries and at the system's edge before anything is built: who provides, who consumes, in what shape, under which change rules.

## Runs when / skipped when

Runs when units talk to each other, or to outside consumers, through an API, an event or a file. Skipped for one self-contained unit; write one line saying so. Runs once per Bolt.

## Reads

As listed by `aidlc_state.py inputs --stage contract-design`:

- `unit-of-work.md` and `unit-of-work-dependency.md`: every edge of the graph is a candidate contract;
- `components.md`: the interactions already decided and their kind;
- `requirements.md`: non-functional targets that bound the contract (latency, size, delivery guarantees);
- `architecture/hla.md` and `hla-decisions.md`: contract formats, versioning rules and technology already decided.

## Question categories

Cover the categories where something material is open; a category the digest, the HLA or earlier answers settle gets no question, and is listed under `## Already answered`. No fixed count; depth scales how much detail the answers need.

- **External API surface**: what outsiders see. "Which operations must an outside consumer be able to call?"
- **Mechanism per boundary**: REST, events, shared schema, file, RPC. "Is this a request that needs an answer now, or a fact others react to?" Cite an HLA decision when it fixes the mechanism.
- **Ownership**: who writes and changes the contract. "Does the provider or the consumer have the final say on a change?"
- **Versioning and breaking changes**: "How long must an old version keep working after a new one ships?"
- **Errors, timeouts and retries**: "What does the caller do on a timeout, and is retrying safe?"
- **Delivery guarantees** (events and files): ordering, duplicates, replay. "May a consumer see the same event twice?"
- **Security and data**: authentication, personal data in the payload. "Which fields must never leave the boundary?"

## Settles

The contract for each unit edge and external surface: provider, consumer, mechanism, owner, change rules, error behaviour, and what is still open.

## Steps

1. Walk the dependency graph and list one candidate per edge, plus each external surface; drop an edge that is an in-process call.
2. Ask and analyse.
3. Write each contract in the spec language that fits (OpenAPI, AsyncAPI, a schema), sufficient to build and mock from; not a prose description.
4. Check each `FR-n` that crosses a boundary appears in a contract.
5. Record open questions with the contract and unit they block.

## Writes

In `docs/inception/contract-design/`:

- `contract-design-questions.md` (and clarifications).
- `contract-summary.md`, starting with `## Digest`, then `## Contracts`: `| # | Provider Unit | Consumer | Mechanism | Owner |` (provider as `U-n`, first cell the contract number); a `### Contract <#>` section with a fenced spec for each; `## Ownership rules`; `## Open questions`: `| Contract | Question | Blocks |`. Each contract names the `FR-n` it serves.

## Good

A consumer team could build against each spec with only this file. Every unit edge is either a contract or listed as deliberately not one.

## Common failure

Describing an interface in prose ("sends the order") with no fields, types, errors or version rule.
