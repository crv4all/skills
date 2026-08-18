# Updating AGENTS.md safely

`AGENTS.md` is usually hand-written, often carefully, and frequently the only
file in a repository that a person has tuned for agents. Overwriting it
destroys work that is expensive to recreate and that nobody will notice is
missing until an agent starts behaving differently.

So: **only the marked block is ever written, and the diff is shown first.**

## The managed block

```markdown
<!-- crv-codebase-context:start -->
## Codebase context

Detailed context lives in `docs/codebase/`, verified against
`4f9c2a1e8b3d` on 2026-08-18:

- [Architecture and the order flow](docs/codebase/ARCHITECTURE.md)
- [Stack divergences](docs/codebase/STACK.md)
- [Conventions](docs/codebase/CONVENTIONS.md)
- [Build, test, deploy](docs/codebase/WORKFLOWS.md)
- [Data and migrations](docs/codebase/DATA.md)
- [External integrations](docs/codebase/INTEGRATIONS.md)
- [Testing](docs/codebase/TESTING.md)
- [Domain language](docs/codebase/DOMAIN.md)
- [Known concerns](docs/codebase/CONCERNS.md)

Regenerate with the crv-codebase-onboarding skill when this stamp falls behind
HEAD.
<!-- crv-codebase-context:end -->
```

Pointers, not content. Duplicated content diverges, and the copy in `AGENTS.md`
is the one that gets read and the one that goes stale first.

Keep the block short. `AGENTS.md` is loaded on every session in most harnesses,
so it is the most expensive context in the repository.

## Procedure

1. **Read** the existing `AGENTS.md` in full.
2. **Locate** the markers.
   - Both present, in order → replace what is between them.
   - Neither present → append the block at the end, and say you appended it.
   - Only one present, or `end` before `start` → **stop.** Report it and leave
     the file alone. A half-marker means a previous edit was interrupted or a
     human edited around the markers, and guessing produces a corrupt file.
   - More than one pair → stop and report. Do not pick one.
3. **Show the diff** before writing. Not a summary of the diff — the diff.
4. **Write** only the block. Preserve everything else byte for byte, including
   trailing whitespace and line endings you did not introduce.
5. **Verify** the markers still pair up after writing, and that the content
   outside them is unchanged.

## The no-clobber rules

- **Never write `CLAUDE.md` when `AGENTS.md` exists.** Two files with the same
  purpose diverge, and the harness that reads the wrong one gets the stale one.
- **Never write `CLAUDE.md` at all in this skill.** If a repository has only
  `CLAUDE.md`, add the managed block to it using the same marker procedure, and
  suggest — do not perform — a rename to `AGENTS.md`.
- **Never touch `.github/copilot-instructions.md` or `.cursor/rules/`.** Those
  are separately maintained. Report that they exist and whether they contradict
  what you found.
- **Never remove content you did not add**, including content inside the
  markers that you did not put there. If the block contains something
  unexpected, show it and ask before replacing.
- **Never create `AGENTS.md` in `focus` or `verify` mode.** Those modes have
  not looked at enough of the repository to justify a top-level claim.

## Nested AGENTS.md

Monorepos often have an `AGENTS.md` per package, and most harnesses load the
nearest one — sometimes in addition to the root, sometimes instead of it.

- Update the **root** one by default.
- Update a nested one only in `focus` mode scoped to that package, and only if
  it already exists.
- Never create a nested `AGENTS.md`. That is an ownership decision belonging to
  whoever owns the package.

## When there is no AGENTS.md

Creating one is reasonable in `bootstrap` mode. Create it minimal: a one-line
statement of what the repository is, then the managed block. Nothing else — the
rest is for a human who knows what agents keep getting wrong here, and a
generated guess at that would be filler in the most expensive file in the
repository.

Say clearly in the report that you created it.
