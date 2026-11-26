# Reverse engineering: artifact contracts and synthesis rules

Read this for the synthesise, focused-rescan and propagation steps.

## The store

One store per target repository, at the planning repo root, shared by every Bolt: `codekb/<repo>/`. `<repo>` is the checkout's directory name. Bolts read it and never keep a private copy.

`_meta.json`, written last:

```json
{"repo": "billing-service", "path": "../billing-service", "commit": "<40-hex HEAD at scan time>", "built": "2026-11-16", "artifacts": ["business-overview.md", "..."]}
```

`commit` is the HEAD the scan ran against; `aidlc_state.py codekb-status` compares it with the checkout. `artifacts` lists every markdown file in the store. For a focused rescan, `commit` moves to the new HEAD and `built` to today.

## Rules for every markdown artifact

- Starts with `## Digest`, at most 10 lines: what the artifact says, the numbers that matter, what later stages must respect. Later stages read only this block, so it must stand alone.
- Every claim carries a source as `path:line` (or `path:start-end`). A claim you could not check is marked `unverified`, never softened.
- Diagrams are Mermaid, followed by a paragraph that says in words what the diagram shows.
- Findings from the workers keep their evidence. Open a source file only to settle a specific claim that is vague, contradicted, or load-bearing.
- Depth changes the detail, never the set of artifacts. All nine always exist.
- No code is copied into artifacts beyond a signature or a line of config needed as evidence.
- State what is, not what should be. Opinions about quality go only in `code-quality-assessment.md`, each with evidence.

## The nine artifacts

| File | Required sections after the digest |
| --- | --- |
| `overview.md` | Written last. No sections beyond the digest (what the repository is, its main components, stack, interfaces, and the risks a change must respect) and an index: one line per artifact below |
| `business-overview.md` | Purpose and users; Business capabilities (what the repo does for the business, each with its entry path); Key business rules found in code; Glossary of domain terms used in code |
| `architecture.md` | System overview (Mermaid + description); Components and their relationships; Interaction diagrams (one per main business transaction, as Mermaid sequence diagrams across components, each followed by text); Data stores and data flow; Deployment and runtime shape; Architectural patterns observed |
| `code-structure.md` | Directory layout and purpose of each area; Module and package organisation; Naming and layering conventions; **Existing files inventory**; Code patterns to follow |
| `api-documentation.md` | Interfaces exposed (endpoints, commands, events, tables or files other systems read), each with method or name, input, output, auth as found, and `path:line`; Interfaces consumed (upstream services, queues, external APIs); Internal module contracts that cross area boundaries |
| `component-inventory.md` | One row per component: `| Component | Responsibility | Area | Depends on | Depended on by | Source |` |
| `technology-stack.md` | Languages with versions; Frameworks and libraries with versions; Build and packaging; Runtime and hosting; Tooling (lint, format, type check) |
| `dependencies.md` | External dependencies (name, version, purpose, where used); Internal dependencies between components or packages; Dependency risks seen (unpinned, deprecated, vulnerable per the manifest, duplicated) |
| `code-quality-assessment.md` | **Test baseline**; Test coverage and layout; Lint, format and type checks; CI and release pipeline; Documentation quality; Technical debt, each with evidence; Oddities and unused-looking code, marked `unverified` unless proven |
| `reverse-engineering-timestamp.md` | `## Run Record` (date, commit, scan depth, tool versions as found); `## Scope of Analysis` (areas read deeply, skimmed, not opened; the rescan kind `full` or `focused` and why); `## Brownfield safeguards` |

### Existing files inventory (in `code-structure.md`)

This is what Code Generation relies on so that nothing is recreated or duplicated. A table: `| Path | Role | Owner area | Changed by convention how |`. List every source file that implements behaviour, every module entry point, every shared helper, every config file that varies behaviour, and every test file group. Group files only when they are uniform (for example generated clients, one row for the folder). End with a list of files that look generated or vendored, so no one edits them by hand. For a large repo, list files by directory with counts, and name every file in the areas the workers marked as the most reused.

### Test baseline (in `code-quality-assessment.md`)

State how tests are run: the exact command, working directory, prerequisites (services, environment variables, credentials by name only), and runtime. State that **the result must be recorded before any change** and who records it: Construction, in its first Code Generation step. If the scan could not run the tests (it never does unless a person asked), say `not run` and give the command. Never invent a result.

### Brownfield safeguards (in `reverse-engineering-timestamp.md`)

Three short lists Construction uses, each tied to this repo:

- **Blast radius.** The shared modules, interfaces and config whose change reaches many callers, with the number of dependents found. Rating guide: low (isolated), medium (two or three dependents), high (cross-cutting).
- **Impact.** The interfaces and data stores other systems depend on, and what would break for them.
- **Rollback.** How a change to this repo is undone today (revert and redeploy, migration down-scripts, feature flag), as found in the pipeline files, or `unverified`.

## Synthesis procedure

1. Read the inventory JSON and every worker findings block. Do not open the repository first.
2. Merge worker findings by theme. The same component reported by two workers becomes one row; keep both sources.
3. Resolve conflicts between workers by opening the cited lines. If it stays unclear, mark it `unverified` and list it for the questions check.
4. Write the artifacts in this order: `technology-stack`, `dependencies`, `component-inventory`, `code-structure`, `api-documentation`, `architecture`, `business-overview`, `code-quality-assessment`, `reverse-engineering-timestamp`. Each later one may cite the earlier.
5. Check: every file starts with `## Digest` of at most 10 lines; no section is missing; every claim has a source or `unverified`.
6. Write `_meta.json` last, so an interrupted run leaves a store that reads as stale, never as fresh.

## Questions only a person can settle

Write a question file only when the scan finds something no file settles, for example two services that both look unused and one is probably live, or two build paths that disagree. Use the question format in the core rules, at `docs/inception/reverse-engineering/reverse-engineering-questions.md` in the Bolt. Do not ask what the code or `codekb/` answers. Stop after writing it; resume when `lint_questions.py` is clean.

## Focused rescan

Input: the `stale` verdict with the changed files. Steps:

1. Map each changed file to the area that contains it, using the stored `Scope of Analysis` and the area names in the current inventory. Run `scan_repo.py` again for the inventory.
2. Run workers only for those areas.
3. Update only the artifacts the findings touch: edit the affected rows and sections, keep text about untouched areas as it was, and refresh the `## Digest` of every file you edit.
4. Areas you did not re-read stay as `read deeply` in the scope only if no changed file lies in them; anything you could not re-check is demoted to `skimmed`.
5. Update the run record and `_meta.json`. If coverage is narrower than before, say so in the checkpoint summary.

A `rescan: full` verdict (a manifest or the layout changed, or too many files moved) always runs the full pipeline and replaces all nine artifacts.

## Propagation (late findings)

When this stage runs or reruns after HLA, requirements, stories or units exist, write `docs/inception/reverse-engineering/propagation.md` in the Bolt. Start with `## Digest`. Then one entry per affected artifact:

```markdown
- [ ] architecture/hla.md: section "Containers" says the export job is stateless; `jobs/export.py:44` writes a local cache. Change: add the cache to the container view and open a decision.
```

Find affected artifacts by comparing the changed or new findings with what each later artifact states about the repo (components, interfaces, data stores, versions, test setup). Name the section and the reason, never just the file. The stage is not complete until every box is ticked. Update the listed artifacts in dependency order (HLA, requirements, stories, domain design, units), by adding entries with new ids or a new decision; Bolt-level stages are not reopened. For each changed id run `aidlc_state.py context --bolt <p> --id <id>` and tell the engineer which Units and Slices rely on it.
