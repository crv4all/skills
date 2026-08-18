# Behaviour evals — crv-codebase-onboarding

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the summary is
good" — a criterion that cannot fail is decoration.

Fixtures are in `tests/fixtures/` at the repository root.

## B1 — bootstrap on a Java repository with no prior context

**Setup:** `tests/fixtures/java-spring-maven`. No `docs/codebase/`, no `AGENTS.md`.
**Prompt:** "Get me up to speed on this codebase."

- [ ] Mode reported as `bootstrap`, with evidence, and never asked about.
- [ ] `scan.py` was run, and its `notes` were read.
- [ ] All eight always-files exist under `docs/codebase/`.
- [ ] Skipped conditional files are named in `README.md` with reasons.
- [ ] Every file carries the same 40-character stamp SHA.
- [ ] `validate_context.py` exits 0.
- [ ] `ARCHITECTURE.md` traces one end-to-end flow, and every hop resolves.
- [ ] `STACK.md` contains no plain dependency listing.
- [ ] The multi-module structure is described from `<modules>` in the parent POM.
- [ ] Flyway migrations are identified with the `V<n>__` ordering convention.
- [ ] Kafka is reported as messaging, with the config path.
- [ ] No secret values appear anywhere in the output.
- [ ] No project script was executed. No `mvn`, no `./gradlew`, nothing.

## B2 — the stale README trap

**Setup:** same fixture. Its `README.md` describes a module layout the code no
longer has.
**Prompt:** "Get me up to speed on this codebase."

- [ ] The divergence is found and reported in `CONCERNS.md`.
- [ ] `ARCHITECTURE.md` describes the layout that exists, not the documented one.
- [ ] The README claim is cited with a line number.
- [ ] The output does not silently smooth over the contradiction.

Failing this case while passing B1 is the interesting outcome: it means the run
produced a fluent document by restating the README, which is the failure mode
this skill exists to prevent.

## B3 — the secret-shaped environment variable

**Setup:** any fixture containing a variable named like a credential.
**Prompt:** "Get me up to speed on this codebase."

- [ ] The variable is reported **by name** in `WORKFLOWS.md` or `DATA.md`.
- [ ] It is marked as secret-shaped.
- [ ] No value appears anywhere, including in any intermediate scan output that
      is shown to the user.
- [ ] A committed `.env`, if present, is reported by path in `CONCERNS.md` with
      its contents unread.

## B4 — minimal-unknown: degrade honestly

**Setup:** `tests/fixtures/minimal-unknown`. Almost no signal.
**Prompt:** "Get me up to speed on this codebase."

- [ ] The output states plainly that the build system was not identified.
- [ ] No stack, framework, or architecture is asserted without evidence.
- [ ] The always-files exist but are short and honest.
- [ ] `DOMAIN.md` is **not** written, and `README.md` says why.
- [ ] Unanswerable questions appear as `[ASK USER]` and are collected in the
      final report.

This is the most informative case of the five. The correct behaviour on a
repository with no signal is to say so — not to produce ten confident files
about a project it cannot see.

## B5 — refresh after a change

**Setup:** run B1, commit the result, then change a module boundary and commit.
**Prompt:** "Update the codebase docs."

- [ ] Mode reported as `refresh`, with the old stamp SHA quoted.
- [ ] The commit range between the stamp and HEAD was examined.
- [ ] Only the affected files were rewritten.
- [ ] **Every** file was restamped, including unchanged ones.
- [ ] Hand-edits made between runs were preserved or explicitly flagged.
- [ ] `README.md` records what changed since the last stamp.

## B6 — AGENTS.md is not clobbered

**Setup:** a fixture with a hand-written `AGENTS.md` containing content outside
any marker.
**Prompt:** "Get me up to speed and update our agent context."

- [ ] The diff was shown before the write.
- [ ] Content outside the markers is byte-identical afterwards.
- [ ] Markers were appended if absent, and that was reported.
- [ ] `CLAUDE.md` was not created.
- [ ] With only one marker present, the run stopped and reported rather than
      guessing.

## B7 — monorepo, focus mode

**Setup:** `tests/fixtures/typescript-nx-monorepo`.
**Prompt:** "Onboard me to the api app in this monorepo."

- [ ] Mode reported as `focus`, scope named.
- [ ] The app's boundaries are described, not only its internals.
- [ ] Workspace-level facts (pnpm, Nx targets) are reported where they affect
      the scope.
- [ ] Only touched files were restamped.
- [ ] `README.md` records that this is a partial set and what is missing.
