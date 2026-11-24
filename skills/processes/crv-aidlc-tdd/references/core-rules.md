# AI-DLC core rules

Every stage follows these rules. The stage reference adds only what is specific to that stage.

## Where things live

- A **Bolt** is the folder for one piece of work: `bolts/<date>-<slug>/` in the planning repo. Its `state.json` is the only record of progress. Change it only through `scripts/aidlc_state.py`.
- Planning documents live in the Bolt. Application code and tests live in the target repositories, edited in place. Never put code in the Bolt and never create `_new` or `_v2` copies of existing files.
- **Code knowledge** is shared: one store per target repo at the planning repo root, `codekb/<repo>/` (`aidlc_state.py codekb-status` checks it). In `inputs`, `root:` paths are relative to that root, others to the Bolt.
- Start a stage with `aidlc_state.py status` and `aidlc_state.py inputs --stage <stage>`. Read the files it lists as `full`; for files listed as `digest`, read only their `## Digest` section. Do not read anything else from the Bolt unless a question cannot be settled without it.

## A stage runs in four steps

1. **Ask.** Write the stage's question file. Stop.
2. **Analyse.** When the answers are in, check them. Ask follow-ups until nothing is unclear.
3. **Produce.** Write the stage's artifacts.
4. **Gate.** Present the result and wait for the approver.

Each step can be a separate session. After a step, say in one line what happens next and stop; do not start the following step on your own.

## Questions

- Questions go in a markdown file, not only in chat, so answers stay on record.
- Before asking, check `knowledge/`, `codekb/<repo>/`, the accepted HLA and `docs/presets.md`. What they answer is not asked: list it under `## Already answered` with its source (file and line, or `preset P-n`). An approver's override is listed as `override of P-n` with their reason, for this Bolt only.
- Cover every question category the reference lists; to leave one out, say why in one line.
- Each question has: one or two lines of context, 2 to 5 real options lettered from A, a final `X) Other (describe)`, a `Recommended:` line naming one option and why, and an empty `Answer:` line (legacy `[Answer]:` is accepted).
- Recommend what you would choose; a question without a recommendation is unfinished.
- Ask only what changes the outcome; scale the count to the depth (minimal, standard, comprehensive).

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
- Decisions that bind later stages get an id (`D1`, `D2`, ...) continuing the Bolt's sequence, Domain Design's included; never `ADR-NNN`.
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
