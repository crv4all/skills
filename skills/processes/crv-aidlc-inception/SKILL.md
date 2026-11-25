---
name: crv-aidlc-inception
description: >-
  Runs the AI-DLC Inception stages for a Bolt: requirements that reconcile the HLA, user stories, a domain design, units of work, contracts between units and a Slice delivery plan, with questions only where something material is open, stable traceable ids and a traceability check before the last checkpoint; and adds a later Slice to a running Bolt as an increment, with readiness gaps explained. Use when someone wants requirements, user stories, a domain design or component catalogue, units of work, API or event contracts, or a Slice or delivery plan for a Bolt, wants to plan the next Slice, change or split a Unit, or resumes one of those stages. Not for opening, resuming or routing a Bolt (crv-aidlc), the HLA (crv-aidlc-hla), the Technical Design Document (crv-aidlc-tdd), scanning existing code (crv-aidlc-reverse-engineering), building units (crv-aidlc-construction), or filing tickets (crv-create-jira-story, crv-create-jira-epic).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: balanced
---

# Inception

Turns the HLA, document knowledge and code knowledge into requirements, stories, a domain design, Units, contracts and a Slice plan. Each stage investigates first, asks only what is open, then writes artifacts whose ids can be traced from requirement to Unit. These stages run once for the Bolt. A later Slice is an increment on them (see Later Slices).

## Execution

**Delegate to a subagent. Do not run this in the main session.** Each stage reads the digests, the HLA and the previous stage's artifacts; that context belongs in an agent that exits when the step is done.

**Model tier: `balanced`.** The questions and the traceable artifacts need sound judgement, but they follow a fixed method and do not need the deepest reasoning. State it, do not ask about it. One line, then start work:

> Running `crv-aidlc-inception` (stage: user-stories, step: ask) in a subagent on the balanced tier.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session. Then read ONLY the reference of the current stage. Scripts live in `scripts/`; run them with `python3`.

## Stages

Find the stage and step with `aidlc_state.py next --bolt <p>`. Paths are relative to the Bolt.

| Stage | Reference | Question file | Main artifact |
| --- | --- | --- | --- |
| `requirements-analysis` | `references/requirements-analysis.md` | `docs/inception/requirements-analysis/requirements-analysis-questions.md` | `requirements.md` |
| `user-stories` | `references/user-stories.md` | `docs/inception/user-stories/user-stories-questions.md` | `stories.md` |
| `domain-design` | `references/domain-design.md` | `docs/inception/domain-design/domain-design-questions.md` | `components.md` |
| `units-generation` | `references/units-generation.md` | `docs/inception/units-generation/units-generation-questions.md` | `unit-of-work.md` |
| `contract-design` | `references/contract-design.md` | `docs/inception/contract-design/contract-design-questions.md` | `contract-summary.md` |
| `delivery-planning` | `references/delivery-planning.md` | `docs/inception/delivery-planning/delivery-planning-questions.md` | `slice-plan.md` |

Artifacts sit beside their question file. Stages can be skipped or conditional; `next` says which run. The scope changes the set: `express` runs requirements, units and delivery planning only (no stories); `bugfix` runs requirements only, at minimal depth. A small, low-risk change takes that lighter route, not the whole set.

## Ids

Reserve decision ids with `aidlc_state.py decision-id --bolt <p> --count <n>`. All other ids are numbered by you within the Bolt and never renumbered. Run `sync` first so you see the ids the team already took.

| Kind | Id |
| --- | --- |
| Requirements | `FR-n`, `NFR-n` |
| Stories, criteria | `US-n`, `AC-n.m` (story n) |
| Units | `U-n` |
| Business rules | `BR-n` |
| Decisions | `D<n>`, the Bolt sequence shared with the HLA |

An id is DECLARED when it starts a heading or the first cell of a table row. It is REFERENCED anywhere else. Declare each id once; cite it everywhere it is used.

## The four runs of a stage

Each run ends with one line saying what comes next.

1. **Ask.**
   - `aidlc_state.py status --bolt <p> --format text`, then `aidlc_state.py inputs --bolt <p> --stage <id>`. Exit 3: name the missing file and the stage that produces it, and stop.
   - Read the files `inputs` lists, as the stage reference says. Investigate before asking. Write the question file: `## Already answered`, `## Assumed` (each `because ...`), then only the questions that are critical or material. A category with nothing open gets none.
   - `lint_questions.py --file <question file> --allow-open`; fix every finding.
   - `aidlc_state.py step --bolt <p> --stage <id> --to asked`. Tell the engineer which file to answer.
2. **Analyse.**
   - `lint_questions.py --file <question file>`. Open answers: list them and stop.
   - Analyse per the core rules. Follow-ups go to `<stage>-clarifications.md` beside the question file.
   - `aidlc_state.py step --bolt <p> --stage <id> --to analysed`.
3. **Produce.**
   - Write the artifacts the reference lists, with their `## Digest` and the sections it requires.
   - Before writing, tell the engineer any HLA conflict the answers expose; it is an HLA change, not a stage decision.
   - `aidlc_state.py step --bolt <p> --stage <id> --to produced`.
4. **Checkpoint.**
   - Before the checkpoint of the last Inception stage that runs (usually `delivery-planning`), run `python3 <crv-aidlc>/scripts/check_traceability.py --bolt <p>`. Fix every gap it reports in the artifacts; do not run the checkpoint while it reports any.
   - Run `aidlc_state.py gate --bolt <p> --stage <id> --approve`; its rules (pass in one line, ask once on a material choice, `--note` for the direction) are in the core rules.
   - After `units-generation` passes, load the Units; after `delivery-planning`, the Slices (see Loading Units and Slices).
   - After the `delivery-planning` checkpoint, and only then, read `references/jira-handoff.md` and file the epic and one story per Unit.

## Loading Units and Slices

Write a JSON file and run `aidlc_state.py units --bolt <p> --set <file.json>`. It merges: new ids are added, an existing Unit or Slice changes only in the keys the file gives, everything else is untouched.

- A Unit: `{"id": "u-1", "name": "...", "kind": "service|spec|ui|packaging|library", "repo": "...", "depends_on": ["u-2", {"unit": "u-3", "on": "contract"}], "slice": "s1"}`. The id is the lower-case form of `U-n`; it names the Unit's construction folder.
- A Slice: `{"id": "s1", "name": "...", "depends_on": ["s0"], "owner": "..."}`. Set a Unit's owner with `assign --bolt <p> --unit <u> --owner <name>`, a Slice's with `assign --bolt <p> --slice <s> --owner <name>`; `--set` refuses to change an existing owner.
- Add one Slice alone: `slice --bolt <p> --add <id> [--name N] [--owner O] [--depends-on s1,s2]`.
- A refusal lists the findings; fix the file.

## Slice readiness

Before a Slice's Units start, run `aidlc_state.py slice --bolt <p> --ready <slice>`. It is a readiness check. It refuses outright for an unknown Slice, a Slice with no Units, or an unknown or cyclic Slice dependency. Otherwise, with gaps and no `--note`, it exits 1 and lists each gap with its consequence: an Inception stage neither done nor skipped, open or malformed questions in the Slice's question file, traceability gaps, a decision whose status is unknown. For each gap, explain in plain words what it would cost if ignored and recommend closing it or going on. Close what the engineer wants closed, then run it again. When the engineer says to go on with gaps open, run it with `--note "<the direction>"`: the Slice becomes ready and the gaps stay recorded as open. Gaps on Units of another Slice are shown as information, not as gaps.

## Later Slices

The Bolt-level stages above run once. Planning the next Slice (for example while the first is being built) is additive, and never rewrites what exists:

1. `sync`, then read the existing requirements, stories, components, Units and contracts through their digests. Run `status` to see what is built and what is waiting.
2. Add new requirement, story, Unit and contract entries with new ids that continue the sequence, in the existing documents. Cite existing entries by id; do not rewrite them. If the new work contradicts an existing entry, show the contradiction with both ids and ask once; never resolve a material disagreement by choosing one side.
3. Investigate before asking. Questions only if something material is open, in `docs/slices/<slice>/inception-questions.md` (same format; `lint_questions.py` checks it, and `slice --ready` reads it).
4. `slice --add`, then `units --set` with only the new or changed Units and their `slice`, then `slice --ready <slice>`.
5. Changing an existing Unit: `units --set` with only the changed keys (a different owner goes through `assign`). Replacing one: `units --cancel <u> --reason "<why>" [--superseded-by u7,u8]` and add the new Units with `units --set`. A cancelled Unit keeps its record and files and is left out of progress.
6. File the new Units' Jira stories as `references/jira-handoff.md` says.

Two engineers planning two Slices at once edit the same documents. After `sync`, if the documents conflict, the commit stops and the files are named: show the conflicting entries, keep both people's work and ask who renumbers; never pick a side. If both took the same new id, the later one takes the next free id and fixes its citations.

## Cross-stage rules

- Read the HLA's `## Digest` and `architecture/hla-decisions.md`. Never re-ask what a decision settles; cite it as `D<n>`. Anything the requirements need that departs from the HLA is raised as an HLA change to the engineer.
- Technology choices fixed by the HLA or an accepted ADR are cited, never re-decided.
- This skill chooses no Construction stages. That is decided per Unit when its construction starts.
- A document that was not read is named in the question file under `## Already answered`, with the reason.

## When a step fails

- `aidlc_state.py`: exit 1 is a refusal (read the findings and fix them in the files), 2 a wrong flag, 3 a missing file or Bolt, 4 a malformed `state.json` or units file (report it; never edit `state.json` by hand).
- `lint_questions.py`: exit 1 lists questions to fix or answers still open.
- `check_traceability.py`: exit 1 lists gaps by id and file; fix the artifacts, run again. Any other exit means the script or an artifact path is broken: report it, do not work around it.
- Two inputs contradict each other, or an answer contradicts the HLA or an accepted ADR: ask, never pick silently.
