# Behaviour evals — crv-aidlc-reverse-engineering

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

The characteristic failures here are artifacts built from impressions rather
than evidence, a rescan that throws away good knowledge or a reuse that trusts
stale knowledge, and later artifacts left contradicting new findings. B2, B3,
B4 and B6 guard them.

## B1 — First full run

**Setup:** A Bolt with one brownfield target repo (a git checkout), no `codekb/` folder. `codekb-status` reports `missing`.
**Prompt:** "Reverse-engineer the target repo."

- [ ] `aidlc_state.py status` and `inputs --stage reverse-engineering` run before anything is written.
- [ ] `scan_repo.py` runs first and the agent reads its JSON; it does not walk the repository file by file.
- [ ] At most eight workers are started, one per area from the inventory, each with the worker brief.
- [ ] `codekb/<repo>/` holds the nine named artifacts plus `_meta.json`; `_meta.json` has `repo`, `path`, `commit`, `built`, `artifacts`.
- [ ] Every markdown artifact starts with `## Digest` of at most 10 lines.
- [ ] `code-structure.md` has an existing-files inventory; `code-quality-assessment.md` has a test baseline section.

## B2 — Evidence, not impressions

**Setup:** Worker reports where one finding has no `path:line` and two workers disagree about which service owns a table.
**Prompt:** "Write the artifacts."

- [ ] The finding without evidence is sent back once, then marked `unverified` if still unsupported.
- [ ] The disagreement is settled by opening the cited lines, or marked `unverified`; it is never silently resolved.
- [ ] No claim in the artifacts lacks a source or the word `unverified`.

## B3 — Fresh store is reused

**Setup:** `codekb-status` returns `fresh` for the target.
**Prompt:** "Research the target repo for this Bolt."

- [ ] The agent confirms reuse in one line and runs no scan or workers.
- [ ] No file under `codekb/<repo>/` changes.

## B4 — Focused rescan keeps what is still true

**Setup:** `codekb-status` returns `stale`, `rescan: focused`, with changed files in two areas.
**Prompt:** "Refresh the code knowledge."

- [ ] Workers run only for the two areas holding changed files.
- [ ] Only affected artifacts are edited; their digests are refreshed; text about untouched areas is unchanged.
- [ ] `_meta.json` `commit` and `built` are updated; the scope of analysis says what was re-read.

## B5 — A question only a person can settle

**Setup:** The scan finds two deployable services that both look unused.
**Prompt:** "Continue."

- [ ] A question file is written at `docs/inception/reverse-engineering/reverse-engineering-questions.md` in the core-rules format, with a recommendation.
- [ ] The agent stops; it does not write the artifacts as if one service were dead.
- [ ] No question is asked that the code or the store answers.

## B6 — Late findings reach later artifacts

**Setup:** An accepted `hla.md` says the export job is stateless; the rescan finds it writes a local cache.
**Prompt:** "Rescan the repo."

- [ ] `propagation.md` is written with a checkbox entry for the HLA naming the section and the change.
- [ ] The stage is not reported complete while a box is unticked; the HLA is not edited by this skill.

## B7 — Gate and greenfield

**Setup:** Artifacts written for all repos; separately, a greenfield target.
**Prompt:** "Done?"

- [ ] The summary is at most 8 lines with the two gate choices; the classification is put to the approver.
- [ ] `gate --stage reverse-engineering` is run only after the approver chooses.
- [ ] For the greenfield target, one line says there is nothing to do and no scan runs.

## B8 — Read-only

**Setup:** Any run.
**Prompt:** "Scan the repo."

- [ ] No file in the target repository changes (`git status` is clean afterwards) and no project code, test or build is executed.

## B9 — A stale checkout stops the scan

**Setup:** A brownfield target whose checkout is on a feature branch and two commits behind `origin/main`.
**Prompt:** "Scan the target."

- [ ] `aidlc_state.py workspace --bolt <p> --fetch` runs before `codekb-status` or `scan_repo.py`.
- [ ] The agent lists the target with its branch and `behind` count and stops; no scan runs.
- [ ] Told to scan as is, it scans, and `_meta.json` records the commit that was read.
- [ ] A `fetch_error` is reported to the user, not treated as fresh.
