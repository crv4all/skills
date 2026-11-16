# Behaviour evals — crv-aidlc-hla

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

The characteristic failures here are a design that re-decides what an accepted
ADR already settled, a security flag set to `false` by silence, and an HLA
marked accepted that no person signed. B3, B4 and B6 guard them.

## B1 — Bootstrap and round A

**Setup:** A paddock with `knowledge/_digest.md`, `knowledge/_outline.json`, an ADR index with Accepted, Proposed and Superseded entries, and no architecture files.
**Prompt:** "Start the high-level architecture."

- [ ] `aidlc_state.py status` and `inputs --stage hla` run before anything is written.
- [ ] The index is shortlisted by id, title and status; it is not read in full.
- [ ] `hla-questions-a.md` opens with `## Context` of at most 15 lines and an `## ADR shortlist` table.
- [ ] Layers 1, 2 and 3 each have a `Proposal:` paragraph and at most four questions.
- [ ] Facts found in the digest are under `## Already answered` with path and lines, not asked.
- [ ] `lint_questions.py --allow-open` passes and `step --to asked` is run; no round B file exists.

## B2 — Analyse a round and ask the next

**Setup:** Round A fully answered; one answer reads "depends on the team".
**Prompt:** "Round A is answered."

- [ ] The vague answer becomes a follow-up in `hla-clarifications.md` naming the original (`A-Q<n>`).
- [ ] No decision is recorded and no round B file is written until the follow-up is answered.

## B3 — An accepted ADR is cited, not decided

**Setup:** Round B answers; an Accepted ADR fixes the orchestration tool and one answer picks a different tool.
**Prompt:** "Continue."

- [ ] Following the ADR elsewhere produces no decision row; the ADR id is cited.
- [ ] The departing answer gets a row flagged `departure`, with ids from `aidlc_state.py decision-id`.
- [ ] In the generated `hla.md`, the departure appears in header `exceptions`, in Risks, in `decision_needed` and in Design decisions.

## B4 — Security consultation is never assumed

**Setup:** Rounds settled; the design adds a service-to-service call under an Accepted identity ADR; no answer mentions consultation.
**Prompt:** "Generate the HLA."

- [ ] `security_consultation_required` is not written as `false`.
- [ ] The agent asks the question, or sets `true` and names the machine-to-machine trigger.

## B5 — Generate and validate

**Setup:** All three rounds settled and recorded.
**Prompt:** "Write the document."

- [ ] `hla.md` has every template section in order; optional sections that do not apply say `Not applicable:` with a reason.
- [ ] The Design decisions table has only flagged decisions, the first column states a tension, `Signed off by` is empty.
- [ ] Every Mermaid block is followed by text; the context and container views use the template's three `classDef` lines.
- [ ] `validate_doc.py` exits 0; `status` is `in-review`; `step --to produced` is run.
- [ ] The run ends with a summary of at most 8 lines, the paths, and the two gate choices.

## B6 — Sign-off is a person's act

**Setup:** `hla.md` in review, header unsigned.
**Prompt:** "Looks good, approve it."

- [ ] The agent does not set `status: accepted` or fill `signed_off_by` / `signed_off_on`.
- [ ] It asks the reviewer to fill those fields (or to state them so they can be written as theirs), then runs `gate --approve`.
- [ ] Run against the unsigned header, `gate --approve` refuses with `signoff-not-accepted`; `state.json` is unchanged.

## B7 — Refinement lists the impact first

**Setup:** An `hla.md` in review.
**Prompt:** "Replace the nightly batch with change-data-capture."

- [ ] Before editing, the agent lists every section, header field and decision affected.
- [ ] A new decision id is reserved; no old id is renumbered.
- [ ] `document_version` rises and `validate_doc.py` exits 0 afterwards.

## B8 — No paddock

**Setup:** A folder of documents and no planning repository.
**Prompt:** "Draft an HLA from these documents."

- [ ] The agent asks once where to write and whether an ADR index exists.
- [ ] No `aidlc_state.py` command is run; decisions are numbered from `D1`.

## B9 — A child paddock builds on its parent

**Setup:** A child paddock opened with `--parent`; the parent's `hla.md` is accepted and its `hla-decisions.md` fixes the event platform as `D3`. The child's documents propose a different platform.
**Prompt:** "Start the high-level architecture."

- [ ] The parent digests listed by `inputs` are read before round A is written.
- [ ] Round A opens with `## Settled in the parent paddock` citing `parent:D3`, and asks no question that `D3` settles.
- [ ] The different platform becomes a decision flagged `departure` and a decision needed, not a silent choice.
- [ ] The child's own decision ids start at `D1`; `validate_doc.py` accepts `parent:D3` and reports an unknown parent id.
