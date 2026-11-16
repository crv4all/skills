# Behaviour evals — crv-aidlc-inception

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

The characteristic failures here are re-asking what the accepted HLA settled,
stories with no way to fail, and ids that nothing traces. B1, B3 and B6 guard
them.

## B1 — Requirements reconcile the HLA

**Setup:** A paddock with an accepted HLA (`hla-decisions.md` fixes the queue and the database), a digest that states a latency target, and no inception files.
**Prompt:** "Start the requirements."

- [ ] `status` and `inputs --stage requirements-analysis` run before anything is written.
- [ ] Nothing the HLA decided is asked; it is under `## Already answered` or a Constraints row citing `D<n>`.
- [ ] The digest's latency target appears as a pre-answered question with a path and a quote.
- [ ] Every category in the reference is covered or skipped with a one-line reason.
- [ ] `lint_questions.py --allow-open` passes and `step --to asked` is run; no `requirements.md` exists.

## B2 — Vague answers become follow-ups

**Setup:** Requirements questions answered; one answer reads "fast enough".
**Prompt:** "Answers are in."

- [ ] A follow-up goes to the clarifications file; no `requirements.md` is written yet.

## B3 — An HLA conflict is raised, not decided

**Setup:** An answer requires a synchronous call where an HLA decision `D4` chose events.
**Prompt:** "Continue."

- [ ] The agent shows both sides, cites `D4`, and asks the approver whether to change the HLA.
- [ ] `requirements.md` has an `## HLA reconciliation` row marked as a conflict; `hla.md` is not edited.

## B4 — Bugfix scope stays minimal

**Setup:** A `bugfix` paddock.
**Prompt:** "Start the requirements."

- [ ] Questions cover only reproduction, expected versus actual, impact and the regression test that must fail first.
- [ ] No stories, units or Bolt plan are proposed.

## B5 — Domain design uses the paddock sequence

**Setup:** Requirements and stories approved; a technology fixed by an accepted ADR.
**Prompt:** "Do the domain design."

- [ ] The ADR's technology is cited, not asked.
- [ ] `decisions.md` ids come from `aidlc_state.py decision-id` and read `D<n>`; none reads `ADR-NNN`.
- [ ] `components.md` has a `yaml` catalogue with no dependency cycle and one owner per entity.

## B6 — Units, traceability and the last gate

**Setup:** Stories approved; one story has no criteria and one `FR-n` is covered by no unit.
**Prompt:** "Finish Inception."

- [ ] Every unit has a kind and the graph has no cycle; `units --set` runs after approval.
- [ ] The agent runs `check_traceability.py` before the gate of the last stage and reports both gaps.
- [ ] It does not run `gate --approve` while the script reports gaps.

## B7 — Delivery planning plans Bolts only

**Setup:** Units approved with a dependency graph.
**Prompt:** "Plan the delivery."

- [ ] "Bolt" is glossed in the first question; each Bolt lists units, definition of done, owner and confidence.
- [ ] No Construction stage is marked execute or skip.
- [ ] The verification command is shown for explicit approval before the gate.

## B8 — Skipped and conditional stages

**Setup:** One unit, no inter-unit calls, no external API.
**Prompt:** "What is next?"

- [ ] Contract design is skipped with a one-line reason, not silently omitted.
