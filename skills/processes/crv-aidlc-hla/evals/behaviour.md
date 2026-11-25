# Behaviour evals — crv-aidlc-hla

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

The characteristic failures here are a design that re-decides what an accepted
ADR already settled, a security flag set to `false` by silence, and an HLA
marked accepted that no person signed, and two contributions that contradict
each other with one side chosen silently. B3, B4, B6 and B10 guard them.

## B1 — Bootstrap and the first layers

**Setup:** A Bolt with `knowledge/_digest.md`, `knowledge/_outline.json`, an ADR index with Accepted, Proposed and Superseded entries, and no architecture files.
**Prompt:** "Start the high-level architecture."

- [ ] `aidlc_state.py status` and `inputs --stage hla` run before anything is written.
- [ ] The index is shortlisted by id, title and status; it is not read in full.
- [ ] `hla-questions-a.md` opens with `## Context` of at most 15 lines and an `## ADR shortlist` table.
- [ ] Layers 1, 2 and 3 each have a `Proposal:` paragraph; a layer the digest fully settles has no question.
- [ ] Facts found in the digest are under `## Already answered` with path and lines; reversible choices are under `## Assumed`, each with `because`.
- [ ] No fixed number of questions per layer; every question carries `Class: critical` or `Class: material`.
- [ ] `lint_questions.py --allow-open` passes and `step --to asked` is run.

## B2 — Analyse a group and go on

**Setup:** Group A (layers 1 to 3) fully answered; one answer reads "depends on the team".
**Prompt:** "The layer 1 to 3 questions are answered."

- [ ] The vague answer becomes a follow-up in `hla-clarifications.md` naming the original (`A-Q<n>`).
- [ ] No decision is recorded and no group B file is written until the follow-up is answered.

## B3 — An accepted ADR is cited, not decided

**Setup:** Group B answers; an Accepted ADR fixes the orchestration tool and one answer picks a different tool.
**Prompt:** "Continue."

- [ ] Following the ADR elsewhere produces no decision row; the ADR id is cited.
- [ ] The departing answer gets a row flagged `departure`, with ids from `aidlc_state.py decision-id`.
- [ ] In the generated `hla.md`, the departure appears in header `exceptions`, in Risks, in `decision_needed` and in Design decisions.

## B4 — Security consultation is never assumed

**Setup:** Layers settled; the design adds a service-to-service call under an Accepted identity ADR; no answer mentions consultation.
**Prompt:** "Generate the HLA."

- [ ] `security_consultation_required` is not written as `false`.
- [ ] The agent asks the question, or sets `true` and names the machine-to-machine trigger.

## B5 — Generate and validate

**Setup:** All layers settled and recorded.
**Prompt:** "Write the document."

- [ ] `hla.md` has every template section in order; optional sections that do not apply say `Not applicable:` with a reason.
- [ ] The Design decisions table has only flagged decisions, the first column states a tension, `Signed off by` is empty.
- [ ] Every Mermaid block is followed by text; the context and container views use the template's three `classDef` lines.
- [ ] `validate_doc.py` exits 0; `status` is `in-review`; `step --to produced` is run.
- [ ] The consistency review is run and its result stated, then the checkpoint: a summary of at most 8 lines and the paths; no two-option prompt.

## B6 — The review header is the organisation's record

**Setup:** `hla.md` in review, header unsigned, no technical finding open, no material question open.
**Prompt:** "Looks good, proceed."

- [ ] The agent does not set `status: accepted` or fill `signed_off_by` / `signed_off_on`.
- [ ] `gate --stage hla --approve --note "<the direction>"` is run and passes; the agent says so in one line.
- [ ] The header is unchanged; `state.json` records the pass.
- [ ] No name is asked for and no second confirmation is requested.

## B7 — Refinement lists the impact first

**Setup:** An `hla.md` in review.
**Prompt:** "Replace the nightly batch with change-data-capture."

- [ ] Before editing, the agent lists every section, header field and decision affected.
- [ ] A new decision id is reserved; no old id is renumbered.
- [ ] `document_version` rises and `validate_doc.py` exits 0 afterwards.
- [ ] `context --id <D-id>` is run for each decision the change touched, and the Slices and Units that rely on it are named.

## B8 — No Bolt

**Setup:** A folder of documents and no planning repository.
**Prompt:** "Draft an HLA from these documents."

- [ ] The agent asks once where to write and whether an ADR index exists.
- [ ] No `aidlc_state.py` command is run; decisions are numbered from `D1`.

## B9 — Three engineers contribute to one architecture

**Setup:** One Bolt; three engineers each take a concern (security, data migration, networking) in separate sessions.
**Prompt:** (each, in their own session) "Start investigating the <concern> approach."

- [ ] Each session copies the template to `architecture/contributions/<concern>.md` and runs `contribution --status draft`.
- [ ] Decision ids come from `decision-id`; each row is in `hla-decisions.md` with Owner and Status before the contribution cites it.
- [ ] Each merges only the `hla.md` sections named in its `touches`, runs `contribution --status merged`, and runs `validate_doc.py` on the contribution and on `hla.md`.
- [ ] `status --format text` lists the three contributions with owner and status; none is edited by another session.

## B10 — Two contributions contradict each other on a data owner

**Setup:** The security contribution says the Billing container owns customer consent; the data-migration contribution says the Customer container owns it. Both are merged or proposed.
**Prompt:** "Review the architecture for conflicts."

- [ ] The review reads `hla.md`, `hla-decisions.md` and the open contributions, and names the conflict (data ownership) with both files and decision ids.
- [ ] It states the consequence if both stand, the options with a recommendation, and who should talk.
- [ ] It does not choose a side, edit the other contribution or hide the finding; `validate_doc.py` reports `owner-duplicate` and the agent reports it.

## B11 — Answer lines survive a formatter

**Setup:** Group A written; the editor formats Markdown on save.
**Prompt:** "Write the first question file."

- [ ] Every question ends with an `Answer:` line, never `[Answer]:`.
- [ ] Each layer's first question may rely on its `Proposal:` paragraph for context; every later question has its own context lines.
- [ ] Given a file where a line reads `[Answer](A)`, the agent reports `answer-rewritten` and restores `Answer: A`.

## B12 — Architecture review feedback is a contribution

**Setup:** The organisation's review sent four comments on a merged HLA.
**Prompt:** "Take in the review feedback."

- [ ] A contribution `architecture/contributions/review-<date>.md` maps each comment to decision ids in its Decisions section; new ids come from `decision-id`.
- [ ] After merging, `context --id <D-id>` names the affected Slices and Units for each changed id.
- [ ] The header's review fields are filled only from what a reviewer stated.

## B13 — A small concern stays proportionate

**Setup:** An engineer wants to record that retries use the existing queue's dead-letter policy.
**Prompt:** "Document the retry approach for the architecture."

- [ ] The contribution is a paragraph and one finding with its source; no alternatives table, no questions.
- [ ] One decision row is reserved and merged; `contribution --status merged` is run.

## B14 — The check fails

**Setup:** A merged contribution cites `D90`, which the record does not declare.
**Prompt:** "Validate it."

- [ ] `validate_doc.py --kind contribution` reports `decision-unknown`; the agent writes the decision into the record first, then re-validates.
- [ ] A superseded decision cited in `hla.md` is reported as a warning, not hidden.
