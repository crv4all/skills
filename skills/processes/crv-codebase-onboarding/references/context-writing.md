# Writing the context files

The section contract for each of the ten files. Templates are in
`assets/templates/`; this file says what belongs in each section and, more
importantly, what does not.

## Rules that apply to every file

**Stamp line first.** Immediately after the H1:

```markdown
> verified against 4f9c2a1e8b3d7c6f5a4b3c2d1e0f9a8b7c6d5e4f on 2026-08-18
```

Full 40-character SHA, ISO date, identical across every file in the set.

**Evidence, not assertion.** Every claim of substance carries a path. A
paragraph with no paths in it should be short, or should not be there.

**Short over complete.** These files are read by people and agents who are
about to do something else. A file that is thorough and unread has failed.
Prefer eight useful lines to eighty exhaustive ones.

**Say what you do not know**, inline, where the reader would otherwise assume
you checked.

**No template text survives.** Every `<placeholder>`, every example row, every
"Describe the…" instruction from the template is gone or replaced. Leftover
template text is the most visible possible sign that nobody read the output.

## README.md

The index and the trust signal. Read first, often read alone.

- One-paragraph statement of what this repository is, in plain terms.
- The file table: name, one line each, and for skipped conditional files, the
  reason they were skipped.
- The stamp, and how to tell when this set has gone stale.
- Which mode produced it, and what that mode did not cover.
- How to refresh it.

## ARCHITECTURE.md

- **Components** — what runs as a unit, what is deployed together, what is a
  library rather than a service.
- **Boundaries** — what crosses each one, in what direction, over what
  protocol, synchronously or not.
- **State** — where it lives and who owns it.
- **One traced end-to-end flow**, hop by hop, with a real path at every hop.
  Pick the flow the system exists to serve.
- **Failure behaviour** at each boundary: retry, queue, drop, propagate.
- A Mermaid diagram only if it shows something the prose cannot. It must parse.
  A component or sequence diagram — never a redrawn directory tree.

The traced flow is the most valuable part of this file. An inventory of
components can be reconstructed from the directory listing; the flow cannot.

## STACK.md

**Non-obvious facts and divergences only.** Never a dependency inventory.

- Versions that constrain something, with the constraint.
- Deliberate divergences from the framework's default, and why.
- Libraries used for something other than their usual purpose.
- End-of-life or pinned-for-a-reason components.
- What a newcomer would get wrong.

If there is nothing non-obvious, the file says exactly that in two lines. That
is a legitimate and useful result.

## CONVENTIONS.md

Three sections, kept apart because they carry different authority.

1. **Configured** — enforced by a tool. Name the tool and the config file. A
   violation is a bug.
2. **Observed** — the dominant pattern, always with a count and the exceptions.
   Never phrased as a rule.
3. **Organization-required** — CRV standards from outside this repository, with
   whether this repository follows them. Do not rewrite code to match; note the
   gap.

Also record where the code violates its own configured rules. That is a finding.

## WORKFLOWS.md

The commands that actually work, sourced from CI rather than from the README —
CI is executable and therefore true, and the README is neither.

- Build · test · run locally · lint · deploy.
- Prerequisites: tool versions, required environment variables **by name**,
  required access.
- Where each command came from (`.github/workflows/ci.yml:22`).
- What is *not* determinable from this repository, said plainly.

You have not run these commands, and the file must not imply you did. Say where
each came from and let the reader draw the conclusion.

## DATA.md

- Stores: type, what lives there, who owns it.
- Schema location and how it is defined.
- Migrations: tool, directory, ordering convention, and how they are applied.
- Data flow in and out: batch, stream, API.
- Retention or privacy handling, if visible in code or config.

Environment variable **names** for connection details. Never values, never
hostnames from a committed config that looks like production.

## INTEGRATIONS.md

For each external system:

- What it is and what we use it for.
- Protocol and direction.
- Where the client code lives.
- How configuration is supplied, by variable name.
- Failure behaviour: what happens when it is down.
- Whether it is in a test double, and where.

An integration with no visible failure handling is worth calling out in
`CONCERNS.md`.

## TESTING.md

- What kinds of tests exist, where, and how many.
- How each kind is run, and where that came from.
- What is well covered, based on evidence rather than a coverage number.
- What is not covered — named, not implied.
- Fixtures, factories, and test data.
- What the tests require: containers, a database, network.

"Coverage is 78%" is not useful. "The payment flow has no test that exercises
the retry path; `PaymentRetryHandler.java` has no corresponding test file" is.

## DOMAIN.md (conditional)

Write only if the repository has business vocabulary a newcomer would misread.
Skip it for a generic CRUD service, and say in `README.md` that you skipped it.

For each term: what it means in the business, which code symbol carries it,
where it is defined, and what it is **not** — the wrong reading you are
pre-empting.

Record inconsistent naming as a finding. If half the code says `animal` and
half says `cow`, that is worth knowing and is not yours to fix.

## CONCERNS.md (conditional)

Write only when there is something concrete. An empty concerns file is noise;
a fabricated one is worse.

Each entry: what it is, the evidence path, why it matters, and how confident
you are.

- Documentation that contradicts the code.
- Committed files that should not be committed.
- Dependencies past end-of-life, with the blocker if visible.
- Half-finished migrations — two patterns for the same job, with counts.
- Code with no tests around a risky path.
- Anything the scan flagged and you could not resolve.

Order by consequence, not by how easy each is to fix. Do not editorialize about
code quality; report facts and their consequences.
