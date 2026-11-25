# AI-DLC core rules

The engineer talks in plain requests. You run the commands and never ask for a flag, a state field or an id rule. The stage reference adds only what is specific to the stage.

## Where things live

- A **Bolt** (`bolts/<date>-<slug>/`) is one initiative: one architecture, Slices over time, Units inside Slices. Change `state.json` only through `scripts/aidlc_state.py`.
- Documents live in the Bolt; code and tests in the target repositories, edited in place, never copied to `_new`. Shared code knowledge is `codekb/<repo>/` at the planning repo root (`root:` paths in `inputs`).
- Start with `status` and `inputs --stage <stage>`. Read `full` files; of `digest` files only the `## Digest`. Read nothing else unless a question needs it.

## A stage runs in four steps

Ask, Analyse, Produce, Checkpoint. Each can be its own session; end a step with one line on what comes next.

## Questions

- Investigate first: code, tests, configuration, documents, `codekb/`, decisions, the HLA, `docs/presets.md`, earlier answers. What they settle is not asked: list it under `## Already answered` with its source (file and line, or `preset P-n`).
- Class what remains. **Critical** (security, compliance, irreversible, data loss) and **material** (business meaning, public contracts, architecture, other people's work) are asked, with a `Class:` line. **Reversible** and **trivial** choices are decided from conventions and listed under `## Assumed`, each with `because ...`; the engineer can overturn them.
- No quota. A layer, category or stage with nothing open gets no question. A listed question file must exist at the checkpoint and hold at least one question: if nothing is open, ask the single one the stage depends on most. Never add more to fill it.
- A question has: one or two lines of context, 2 to 5 options lettered from A, a last `X) Other (describe)`, a `Recommended:` line with the reason, and an empty `Answer:` line. Questions live in the file, not only in chat.
- Analyse answers: run `lint_questions.py`; look for blanks, vague words ("depends", "probably"), contradictions with each other, the HLA or an ADR, merged options, undefined terms. Follow up in `<stage>-clarifications.md`. Never fill a gap with a guess.

## Artifacts

- Start with `## Digest`, at most 10 lines. Facts carry a source (path, answer id, ADR id); mark unchecked ones `unverified`. Diagrams are Mermaid with a paragraph under them. Depth changes detail, not which artifacts exist.
- Decision ids (`D<n>`) come from `aidlc_state.py decision-id`; if it says the ids were not reserved, tell the engineer to fix the connection and run it again. Other ids never change: `FR-n`, `NFR-n`, `US-n`, `AC-n.m`, `U-n`, `BR-n`; declare one at the start of a heading or table row.
- Code work starts from a plan of numbered checkbox steps naming what each serves. Show it and wait for the engineer's go. Execute as written; if it is wrong, change the plan first. Tick a step in the turn it is done.

## Checkpoint

Run `aidlc_state.py gate --stage <s> [--unit <u> | --slice <sl>] --approve`.

- A finding (missing artifact or digest, open question, missing or failed `Verdict:`) is a fact. Report it, fix the files, never pass it. A failed run keeps the stage open.
- Nothing technical open and no material question: it passes. Say so in one line and go on.
- A material choice is open: ask once with your recommendation and the alternatives. On "proceed", run it with `--note "<the direction>"`. No second question, no name to collect.
- HLA and TDD headers record the organisation's own review. It never conditions a stage; never edit `status` or `signed_off_*` to proceed.

## Changed inputs and rework

- On resume and before a checkpoint read the `context` report (in `next`, `brief` and the gate result; in full: `context --bolt <p> --unit <u>` or `--slice <sl>`). Empty: carry on. Otherwise explain what changed and the likely impact, recommend whether to revise, continue what is unaffected, and record the conclusion with `context ... --note "<conclusion>"`. `context --id D63` says who relies on an id.
- A passed Unit stage (or Slice stage) is reopened with `gate ... --request-changes --note "<why>"`. A Bolt-level stage is not: change the document with new ids and `context` tells the Units that rely on it.

## Saving

The log is engineering context: record directions and conclusions in notes, do not narrate. Commands save and share the work and queue behind other sessions. If a result says it is saved here and not shared yet, say so plainly. Supported: macOS, Linux, WSL; native Windows has a weaker lock and is not verified.

## Brownfield and people

Before changing existing code know what depends on it, record the test baseline, state the impact, and put the rollback plan in the Unit's code plan. If a step needs a person (access, a decision, a meeting), write **HUMAN TASK** with what and from whom, and stop.
