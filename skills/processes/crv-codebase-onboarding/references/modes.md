# The four modes

The mode is **detected in Phase 0, never asked.** The repository already holds
the answer, and asking costs a turn to learn something that is on disk.

Report the detected mode and its evidence in one line before continuing. If the
user's explicit request contradicts the detection, the user wins — say that you
are overriding, and why.

## Detection order

Evaluate top to bottom and stop at the first match.

1. The user named a subsystem, path, module, or service → **focus**
2. The user is asking whether existing context is still accurate
   ("is this still right?", "did anything change?") → **verify**
3. `docs/codebase/` exists with at least one stamped file → **refresh**
4. Otherwise → **bootstrap**

A `docs/codebase/` directory that exists but has no stamp is treated as
`bootstrap`. Unstamped files were either hand-written or produced by a run that
did not finish; either way they cannot be trusted as a baseline.

## bootstrap

Nothing usable exists. Run all five phases and write the full set.

- Do not skip Phase 2 because there is no `README.md`. Its absence *is* the
  finding, and it belongs in `CONCERNS.md`.
- If the repository is too small or too unusual to support a real answer, say
  so and write short honest files. Ten confident files about a repository you
  cannot see is the worst possible output — it looks like success.
- Do not invent `DOMAIN.md` to reach ten files. A generic service has no domain
  vocabulary, and inventing one puts fabricated terms into everyone's context.

## refresh

Context exists and the code has moved. Re-verify rather than rewrite.

1. Read the existing stamp SHA. Compare it with HEAD.
2. If the stamp SHA is not an ancestor of HEAD (history was rewritten, or the
   stamp is from another branch), say so and fall back to `bootstrap`.
3. Get the changed paths between the stamp and HEAD, then decide which of the
   ten files each change could invalidate.
4. Re-verify **every** claim in the affected files, not only the ones that look
   related. A change to a build file can invalidate `WORKFLOWS.md` without ever
   touching a path that file mentions.
5. Rewrite only what changed. Restamp every file, including unchanged ones —
   the stamp means "verified at this commit", not "edited at this commit".
6. Record what changed since the last stamp in `README.md`.

Preserve hand-edits you cannot attribute to the generator. A human who
corrected a generated file was correcting something. If a hand-edit now
contradicts the code, report the contradiction rather than silently reverting.

## focus

The user named a scope: one module, one service, one subsystem.

- Run the same phases, restricted to that scope plus its immediate boundaries.
  The boundary is part of the subsystem; a component described with no callers
  and no callees is not described.
- Merge into the existing set rather than creating a parallel one. Add a scoped
  section to each relevant file, marked with the scope it covers.
- If no `docs/codebase/` exists yet, write only the files the scope supports,
  and record in `README.md` that this is a partial set produced in `focus` mode
  and which files are still missing.
- Restamp only the files you touched, and say which those were.

## verify

The cheapest mode. Check whether existing context is still true. **Change
nothing except `CONCERNS.md` and the report.**

1. Extract every checkable claim: paths, commands, component names, flows.
2. Check each one against the working tree.
3. Classify: `still true` · `now false` · `no longer checkable`.
4. Write the false and unverifiable ones into `CONCERNS.md`.
5. Do **not** restamp. The files were not re-verified in full; a stamp that
   says they were would be a lie encoded in the format.
6. Report a count: "N claims checked, M no longer true".

`verify` is the right mode before trusting context you did not generate, and it
is cheap enough to run often. If it reports more than a handful of false
claims, recommend `refresh` — but do not silently escalate into it, because the
user asked a question, not for a rewrite.
