# Behaviour evals — crv-aidlc-inception

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

The characteristic failures here are re-asking what the accepted HLA settled,
stories with no way to fail, ids that nothing traces, and a later Slice that
rewrites what the first one built on. B1, B3, B6 and B9 guard them.

## B1 — Requirements reconcile the HLA

**Setup:** A Bolt with an accepted HLA (`hla-decisions.md` fixes the queue and the database), a digest that states a latency target, and no inception files.
**Prompt:** "Start the requirements."

- [ ] `status` and `inputs --stage requirements-analysis` run before anything is written.
- [ ] Nothing the HLA decided is asked; it is under `## Already answered` or a Constraints row citing `D<n>`.
- [ ] The digest's latency target appears as a pre-answered question with a path and a quote.
- [ ] A category with nothing open has no question and a one-line note under `## Already answered`; there is no fixed question count. With nothing to ask at all, no question file is written and the stage goes on to produce, with its assumed choices in the artifact.
- [ ] Reversible choices are under `## Assumed`, each with `because`.
- [ ] `lint_questions.py --allow-open` passes and `step --to asked` is run; no `requirements.md` exists.

## B2 — Vague answers become follow-ups

**Setup:** Requirements questions answered; one answer reads "fast enough".
**Prompt:** "Answers are in."

- [ ] A follow-up goes to the clarifications file; no `requirements.md` is written yet.

## B3 — An HLA conflict is raised, not decided

**Setup:** An answer requires a synchronous call where an HLA decision `D4` chose events.
**Prompt:** "Continue."

- [ ] The agent shows both sides, cites `D4`, and asks the engineer once, with a recommendation, whether to change the HLA.
- [ ] `requirements.md` has an `## HLA reconciliation` row marked as a conflict; `hla.md` is not edited.

## B4 — Bugfix scope stays minimal

**Setup:** A `bugfix` Bolt.
**Prompt:** "Start the requirements."

- [ ] Questions cover only reproduction, expected versus actual, impact and the regression test that must fail first.
- [ ] No stories, units or Slice plan are proposed.

## B5 — Domain design uses the Bolt sequence

**Setup:** Requirements and stories done; a technology fixed by an accepted ADR.
**Prompt:** "Do the domain design."

- [ ] The ADR's technology is cited, not asked.
- [ ] `decisions.md` ids come from `aidlc_state.py decision-id` and read `D<n>`; none reads `ADR-NNN`.
- [ ] `components.md` has a `yaml` catalogue with no dependency cycle and one owner per entity.

## B6 — Units, traceability and the last gate

**Setup:** Stories approved; one story has no criteria and one `FR-n` is covered by no unit.
**Prompt:** "Finish Inception."

- [ ] Every Unit has a kind and the graph has no cycle; `units --set` runs after the checkpoint and adds Units without touching others.
- [ ] The agent runs `check_traceability.py` before the checkpoint of the last stage and reports both gaps.
- [ ] It does not run `gate --approve` while the script reports gaps.

## B7 — Delivery planning plans Slices only

**Setup:** Units done with a dependency graph.
**Prompt:** "Plan the delivery."

- [ ] "Slice" is glossed in the first question; each Slice lists units, definition of done, owner and confidence.
- [ ] No Construction stage is marked execute or skip.
- [ ] The verification command is shown with a recommendation and recorded once the engineer says go.
- [ ] The Slices are loaded with `units --set` (`slices` entries and each Unit's `slice`), then `slice --ready s1` is run.

## B8 — Skipped and conditional stages

**Setup:** One unit, no inter-unit calls, no external API.
**Prompt:** "What is next?"

- [ ] Contract design is skipped with a one-line reason, not silently omitted.

## B9 — A second Slice while the first is built

**Setup:** Slice `s1` is being built (Units `u1`, `u2` in Construction). A new requirement arrives.
**Prompt:** "Plan the next Slice."

- [ ] `sync` runs first; new requirement, story, Unit and contract entries get new ids that continue the sequence, in the existing documents.
- [ ] Existing entries are cited by id and not rewritten; `u1` and `u2` and their records are untouched.
- [ ] `slice --add s2`, `units --set` with only the new Units (and their `slice`), then `slice --ready s2` run in that order.
- [ ] No Bolt-level Inception stage is run again.

## B10 — Readiness gaps are explained, then recorded on direction

**Setup:** `slice --ready s2` lists a traceability gap and one open question.
**Prompt:** "Just proceed with s2 as it is."

- [ ] Each gap is explained in plain words with its consequence and a recommendation; no gap code is read out as the answer.
- [ ] On the engineer's direction, `slice --ready s2 --note "<the direction>"` is run; the gaps are reported as recorded open gaps.

## B11 — Change a Unit that exists

**Setup:** `u3` is in Construction; it must now be split into two.
**Prompt:** "Split u3 into an importer and a reporter."

- [ ] `units --cancel u3 --reason "..." --superseded-by u7,u8` and `units --set` for `u7`, `u8` are run; `u3` keeps its files and history.
- [ ] A changed owner goes through `assign`, never through `units --set`.

## B12 — Two engineers plan two Slices at once

**Setup:** Two sessions each added new `FR-` entries and edited the same `requirements.md`; `sync` stops with conflict markers named.
**Prompt:** "Sync and carry on."

- [ ] The agent shows the conflicting entries and keeps both people's work.
- [ ] A duplicated id is renumbered by the later session with its citations; no material disagreement is resolved by choosing a side.

## B13 — A small low-risk change takes the lighter route

**Setup:** An `express` Bolt for a one-repository change.
**Prompt:** "What do we need to do in Inception?"

- [ ] Only requirements, units and delivery planning run; no stories and no HLA are proposed.
- [ ] Slice `s1` is already ready (single-Slice Bolt); `slice --ready` is not needed.

## B14 — Questions only if needed for a later Slice

**Setup:** The new Slice reuses an existing contract and nothing is open.
**Prompt:** "Plan the next Slice."

- [ ] No question file is written; `slice --ready` runs without an `inception-questions.md`.
- [ ] A material open point goes to `docs/slices/<slice>/inception-questions.md` in the question format.
