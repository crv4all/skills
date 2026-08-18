---
name: crv-codebase-onboarding
description: >-
  Produces durable, evidence-backed codebase context in docs/codebase/ —
  architecture, stack divergences, conventions, workflows, data, integrations,
  testing, and domain language — with every claim traceable to a real file path
  and stamped with the commit it was verified against. Use when someone asks to
  get up to speed on a repository, onboard to a codebase, understand how a
  system fits together, refresh stale codebase notes, or check whether existing
  context still matches the code, and before a large change in an unfamiliar
  repository. Not for writing a public README, explaining a single function, or
  authoring a new agent skill.
license: Apache-2.0
compatibility: Requires Python 3.9+ and read access to the target repository. No network access needed.
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# Codebase onboarding

Turn an unfamiliar repository into context that survives the session.

The output is written to `docs/codebase/` in the target repository, committed,
and stamped so that a future reader can tell whether it is still true. That
stamp is the point: documentation nobody can date is documentation nobody can
trust.

## What this produces

Ten files in `docs/codebase/`. Eight are always written; two are conditional.

| File | Contents | Condition |
| --- | --- | --- |
| `README.md` | Index, how to use this set, how to tell when it is stale | always |
| `ARCHITECTURE.md` | Components, boundaries, and one traced end-to-end flow | always |
| `STACK.md` | Non-obvious stack facts and divergences only — **not** a dependency inventory | always |
| `CONVENTIONS.md` | Configured / observed / organization-required, kept apart | always |
| `WORKFLOWS.md` | Build, test, run locally, deploy — the commands that actually work | always |
| `DATA.md` | Stores, schemas, migrations, ownership of state | always |
| `INTEGRATIONS.md` | External systems, protocols, failure behaviour | always |
| `TESTING.md` | What is tested, how it runs, where the gaps are | always |
| `DOMAIN.md` | Business vocabulary, with the code symbols that carry it | only if the repository has domain language a newcomer would misread |
| `CONCERNS.md` | Risks, traps, and stale documentation found along the way | only if there is something concrete to report |

Every file opens with the stamp line:

```markdown
> verified against <full-sha> on <YYYY-MM-DD>
```

A conditional file that is not written is **named in `README.md` with the
reason it was skipped.** A missing file that nobody explains is
indistinguishable from a step that was forgotten.

## When not to use this

- A single function, class, or bug → just read the code.
- A public-facing README → different audience, different document.
- Creating a new agent skill → `crv-create-skill`.
- A repository you have already onboarded and have not changed → the
  `verify` mode below is cheap, but do not re-run `bootstrap`.

## Execution

**Delegate to a subagent. Do not run this in the main session.** This skill reads a large fraction of a repository. That context belongs in an agent that exits when it is done, not in the conversation the user has to keep using afterwards.

**Model tier: `economy`** — the cheapest model that can follow instructions and
call tools. Before spawning the subagent, ask once:

> Running `crv-codebase-onboarding` in a subagent on the **economy** tier. Reply
> `balanced` or `frontier` to run it on a stronger model, or continue to
> accept the default.

Ask once per invocation, before any work starts. Skip the question only when
the user has already stated a tier preference in this session or in the
project's agent configuration.

**Never silently escalate.** If the subagent turns out to be out of its depth,
stop and say so. Re-running on a bigger model without asking charges the user
twice and hides the fact that the cheap tier was not enough — which is exactly
the signal that should reach them.

If the harness has no subagent mechanism, say so plainly and run inline. Still
state the tier; the user can change the model even when they cannot change
where it runs.

## Operating rules

These hold in every phase. They are what make the output checkable.

1. **Evidence before interpretation.** Never state a claim you cannot attach a
   path to. `src/api/OrderController.java:42` is evidence; "the API layer
   handles orders" alone is a guess with good grammar.
2. **Never run the project's scripts.** Reading `package.json` is inspection;
   running `npm run build` is a side effect on someone else's machine. Read-only
   `git` commands are allowed. Nothing else executes.
3. **No network access.** Everything comes from the working tree.
4. **Never emit a secret value.** Naming `DATABASE_PASSWORD` as a required
   variable is useful. Printing what it is set to is a disclosure that survives
   in git history.
5. **Never modify source.** Output goes to `docs/codebase/`, plus the marked
   block in `AGENTS.md`. Nothing else is touched.
6. **Report what you could not determine.** A named gap is a finding. Silence
   reads as "there was nothing there".
7. **Prefer a divergence over a summary.** The valuable output is where the
   README, the config, and the code disagree. Anyone can restate a README.

See [references/evidence-policy.md](references/evidence-policy.md) for the full
policy, including how to handle vendored code and generated files.

## Phase 0 — Detect the mode

**Detect. Do not ask.** The repository already answers this, and a question
here costs a turn to learn what is on disk.

Look for: `docs/codebase/` and its stamp · `AGENTS.md` at the root and nested ·
`CLAUDE.md` · `.github/copilot-instructions.md` · `.cursor/rules/`,
`.cursorrules` · `README.md` · `CONTRIBUTING.md` · any ADR directory
(`docs/adr/`, `docs/decisions/`, `architecture/decisions/`).

| Situation | Mode |
| --- | --- |
| No `docs/codebase/` | `bootstrap` — the full five phases |
| `docs/codebase/` exists, stamp SHA is an ancestor of HEAD and differs | `refresh` — re-verify, rewrite only what changed |
| The user named a subsystem, path, or module | `focus` — the same phases, scoped, merged into the existing set |
| `docs/codebase/` exists and the user is asking whether it is still true | `verify` — check claims, change nothing but `CONCERNS.md` |

Report the detected mode and the evidence for it in one line before continuing.
If the user's request contradicts the detection, the user wins.

Mode-specific behaviour is in [references/modes.md](references/modes.md).

## Phase 1 — Gather evidence

Run the scanner. It is deterministic, it decides nothing, and it exists so that
the interpretation you do later rests on facts you did not invent.

```bash
python3 scripts/scan.py --root <repo> --output scan.json
```

It emits JSON on stdout (or to `--output`) and diagnostics on stderr. It never
executes project scripts, never reaches the network, and never captures the
value of an environment variable — only its name and where it is referenced.

Read the whole `notes` array. Those are the things the scanner saw but could
not classify, and they are where the interesting parts of a codebase usually
hide.

Then read, in this order, what the scanner pointed at: build manifests, entry
points, configuration, CI definitions, and the largest source files by line
count. Large files are where the load-bearing logic accumulates.

`--help` documents every flag and the exit codes.

## Phase 2 — Read the stated intent, before interpreting the implementation

Read `README.md`, `CONTRIBUTING.md`, ADRs, and any existing `AGENTS.md` **now**,
after the scan and before forming an architectural opinion.

The order matters in both directions. Reading them first makes you interpret
the code through claims that may be years old. Reading them never leaves you
unable to spot the divergences, which are the highest-value output of the whole
process.

For each significant claim in the stated intent, record one of:

- **Confirmed** — the code does this, at `<path>`.
- **Diverged** — the code does something else, at `<path>`. This goes in
  `CONCERNS.md`.
- **Unverifiable** — no evidence either way. Say so; do not repeat the claim as
  fact.

## Phase 3 — Architecture, and one flow traced end to end

Describe components and boundaries: what runs as a unit, what talks to what,
where state lives, what is deployed together.

Then trace **one representative end-to-end flow** with real file paths at every
hop — entry point, through the layers, to the store or the external call, and
back. Pick the flow the repository exists to serve, not the simplest one.

```text
POST /api/orders
  → src/api/OrderController.java:34        (validation, auth)
  → src/domain/OrderService.java:88        (business rules)
  → src/infra/OrderRepository.java:51      (persistence)
  → db/migrations/V12__orders.sql          (schema)
  → emits orders.created → src/infra/KafkaPublisher.java:22
```

One traced flow teaches more about a codebase than a complete component
inventory, because it shows the seams the inventory hides. **Every path in the
trace must exist.** A plausible path that does not exist is worse than no trace
at all — it will be followed.

Include a Mermaid diagram only when it shows something the prose cannot. It must
parse, and it must be a component or sequence diagram, not a redrawn directory
tree.

## Phase 4 — Domain language and conventions

**Domain language.** Collect terms that carry meaning a newcomer would get
wrong, and bind each to the symbol that implements it. Write `DOMAIN.md` only if
such terms exist; a generic CRUD service does not have a domain vocabulary, and
inventing one is noise. At CRV, breeding and genetics vocabulary — animal
identifiers, evaluation runs, indexes, herds, lactations — is exactly the kind
of term whose everyday meaning is wrong.

**Conventions**, kept in three separate groups, because they carry different
authority:

| Group | Source | If code disagrees |
| --- | --- | --- |
| Configured | Linter, formatter, editorconfig, compiler settings | The tool wins; a violation is a bug |
| Observed | The dominant pattern in the code, with a count | Report the split, name the majority, do not invent a rule |
| Organization-required | CRV standards from outside this repository | Note the gap; do not silently rewrite the codebase to match |

Never present an observed pattern as a rule. "23 of 27 controllers return
`ResponseEntity`" is useful and honest. "Controllers return `ResponseEntity`" is
neither, and it will be cited as policy.

See [references/organization-standards.md](references/organization-standards.md)
for what counts as organization-required.

## Validation loop

Write the files, then run the contract checker. It does the mechanical half —
required files, stamp consistency, path resolution, leftover template text,
credential-shaped strings, Mermaid parsing, marker collection — because an
agent asked to verify forty paths by eye will verify some of them and report
all of them as verified.

```bash
python3 scripts/validate_context.py --root <repo> --expect-sha <head-sha>
```

Exit 0 means the contract holds. Exit 1 lists what to fix. Fix, re-run, repeat.
Do not report completion while it still exits 1.

Then check by hand what the script cannot:

- [ ] Line references point at what the text says they point at. The script
      checks that the file exists, not that line 42 is the line you meant.
- [ ] `STACK.md` contains no plain dependency listing.
- [ ] The end-to-end flow in `ARCHITECTURE.md` reads as one continuous path,
      not a set of unrelated hops that happen to exist.
- [ ] Every claim of substance carries evidence, not just the ones with paths.
- [ ] Every `[ASK USER]` the script collected appears in your final report.
- [ ] Nothing in the output is a summary of the README rather than a finding
      about the code.

## Updating AGENTS.md

Update `AGENTS.md` only inside the managed block, and show the diff before
writing it.

```markdown
<!-- crv-codebase-context:start -->
...generated pointer block...
<!-- crv-codebase-context:end -->
```

Content outside the markers is never touched — it is somebody's hand-written
instructions. If no markers exist, append the block at the end and say so.
Never write `CLAUDE.md` when `AGENTS.md` exists, and never overwrite either
wholesale. Full rules: [references/agents-md-merge.md](references/agents-md-merge.md).

## Reporting

Close with: the detected mode and why · files written, updated, and skipped
with reasons · the divergences found · every `[ASK USER]` item · and what you
could not determine.

Say plainly which validation checks you ran. If you skipped one, name it and
say why. Never report a check as passed that you did not perform.

## References

- [references/modes.md](references/modes.md) — the four modes in detail
- [references/evidence-policy.md](references/evidence-policy.md) — what counts as evidence, and the safety rules
- [references/inquiry-checkpoints.md](references/inquiry-checkpoints.md) — the questions each phase must answer
- [references/stack-detection.md](references/stack-detection.md) — ecosystem signals and what they imply
- [references/context-writing.md](references/context-writing.md) — section contract for each of the ten files
- [references/organization-standards.md](references/organization-standards.md) — CRV context
- [references/agents-md-merge.md](references/agents-md-merge.md) — the managed-marker merge
- `scripts/scan.py` — deterministic evidence gathering
- `scripts/validate_context.py` — output-contract checker
- `assets/templates/` — one template per output file
