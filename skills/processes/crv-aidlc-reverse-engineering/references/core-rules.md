# AI-DLC core rules

Every stage follows these rules. The stage reference adds only what is specific to that stage.

## Where things live

- A **paddock** is the folder for one piece of work: `paddocks/<date>-<slug>/` in the planning repo. Its `state.json` is the only record of progress. Change it only through `scripts/aidlc_state.py`.
- Planning documents live in the paddock. Application code and tests live in the target repositories, edited in place. Never put code in the paddock and never create `_new` or `_v2` copies of existing files.
- **Code knowledge** is shared: one store per target repo at the planning repo root, `codekb/<repo>/` (`aidlc_state.py codekb-status` checks it). In `inputs`, `root:` paths are relative to that root, others to the paddock.
- Start a stage with `aidlc_state.py status` and `aidlc_state.py inputs --stage <stage>`. Read the files it lists as `full`; for files listed as `digest`, read only their `## Digest` section. Do not read anything else from the paddock unless a question cannot be settled without it.

## A stage runs in four steps

1. **Ask.** Write the stage's question file. Stop.
2. **Analyse.** When the answers are in, check them. Ask follow-ups until nothing is unclear.
3. **Produce.** Write the stage's artifacts.
4. **Gate.** Present the result and wait for the approver.

Each step can be a separate session. After a step, say in one line what happens next and stop; do not start the following step on your own.

## Questions

- Questions go in a markdown file, never only in chat, so the answers stay on record.
- Before asking, check `knowledge/`, `codekb/<repo>/` and the accepted HLA. If they already answer a question, do not ask it; list it under `## Already answered` with the source file and line.
- Cover every question category the stage reference lists. To leave one out, write one line saying why it does not apply.
- Each question has: one or two lines of context, 2 to 5 real options lettered from A, a final `X) Other (describe)`, a `Recommended:` line naming one option with the reason (a CRV addition to the AWS question format), and an empty `[Answer]:` line.
- Recommend what you would choose given everything you have read. A question without a recommendation is unfinished.
- Ask only what changes the outcome. Scale the number of questions to the paddock's depth: minimal, standard or comprehensive.

## Analysing answers

Run `scripts/lint_questions.py` first. Then read every answer for:

- blanks, or a letter that is not an option;
- vague wording: "depends", "mix of", "standard", "typical", "as needed", "probably";
- answers that contradict each other, the HLA, or an accepted ADR;
- two options merged into one answer;
- terms nobody has defined.

For each problem, add a follow-up question to `<stage>-clarifications.md` in the same format. Repeat until the answers are clear or the approver writes that you should proceed with a stated assumption; record that assumption in the artifact.

Never fill a gap with a guess. If something needed is missing, say what and which earlier stage produces it.

## Artifacts

- Every artifact starts with a `## Digest` of at most 10 lines: what was decided, the numbers that matter, and what later stages must respect.
- State facts with their source: a file path, an answer id, an ADR id. Mark anything not checked as `unverified`.
- Diagrams are Mermaid with a one-paragraph text description underneath.
- Depth changes how much detail an artifact holds, never which artifacts are produced.
- Decisions that bind later stages get an id (`D1`, `D2`, ...) continuing the paddock's sequence, Domain Design's included; never `ADR-NNN`.
- Ids never change: `FR-n`, `NFR-n`, `US-n`, `AC-n.m`, `U-n`, `BR-n`. Declare one at the start of a heading or a table row.

## Plans and checkboxes

- Work that changes code, or that produces many artifacts, starts from a plan: numbered checkbox steps, each naming what it produces and which stories or requirements it serves.
- The plan is approved before any of it is executed. Execute it exactly as written. If it turns out wrong, stop and change the plan first.
- Tick a step in the same turn the work is done. To resume, continue from the first unticked step.

## Gate

End the stage with: a factual summary of at most 8 lines, the paths to review, and exactly two choices, **Request changes** or **Continue**. Record the choice with `aidlc_state.py gate`. The script refuses when an artifact is missing, has no digest, or a question file still has open answers. Never mark a stage approved yourself.

## Changes after approval

When an approved artifact has to change, list the later artifacts that depend on it, get the approver's agreement, update them in order, and re-open their gates.

## Brownfield

Before changing existing code: know what depends on it, record the current test results as the baseline, state the impact, and put the rollback plan in the unit's Code Generation plan. Follow the conventions found in `codekb/<repo>/`.

## Human tasks

If a step needs something only a person can do (access, a decision, a meeting), write it as **HUMAN TASK** with what is needed and from whom, and stop.
