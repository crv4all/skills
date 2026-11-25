---
name: crv-aidlc
description: >-
  Opens, resumes and closes a Bolt (the folder for one piece of work in a planning repo), routes to the next AI-DLC stage and runs the checkpoints with deterministic scripts, so an engineer works in plain requests and never needs a command. Use when someone wants to start, open, resume or close a Bolt, asks what is next, what is blocking a Unit, what changed under their work or what has happened in a Bolt, mentions AI-DLC, asks whether they are ready to use AI-DLC or how to get started, or wants a structured, staged delivery of a feature, migration or bug fix. Not for the stage work itself: crv-aidlc-reverse-engineering, crv-aidlc-hla, crv-aidlc-tdd, crv-aidlc-inception, crv-aidlc-construction and crv-aidlc-operation own that, and the crv-create-jira-* skills file tickets.
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# AI-DLC entry point

Opens, resumes and closes a Bolt, then hands each stage to the skill that owns it. A Bolt is one initiative: one shared architecture, Slices added over time, Units inside Slices. Progress changes only through `scripts/aidlc_state.py`; never edit `state.json` or `log.md` by hand.

The engineer speaks in plain requests. You run the commands, read the output and answer in plain words. Never ask the engineer for a flag, a state field or an id rule, and never show a command line unless they ask.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Opening, resuming and checkpoints produce script output and bookkeeping the user does not want left in their conversation.

**Model tier: `economy`**: the cheapest model that can follow instructions and call tools. State it, do not ask about it. One line, then start work:

> Running `crv-aidlc` in a subagent on the economy tier.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session, before the first stage action. All scripts live in `scripts/`; run them from the skill folder with `python3`.

## What this produces

A Bolt `bolts/<date>-<slug>/` in the planning repo, a `state.json` that is true, and a one-line answer to "what is next". Stage artifacts are written by the stage skills, not here.

## When to use this

Opening, resuming or closing a Bolt; "what is next"; any request in the table below; and "am I ready to use AI-DLC" or "how do I get started" (run the prerequisites check, then point to `docs/getting-started.md` in the planning repo).

## When not to use this

- Doing the stage itself: `crv-aidlc-reverse-engineering`, `crv-aidlc-hla`, `crv-aidlc-tdd`, `crv-aidlc-inception`, `crv-aidlc-construction`, `crv-aidlc-operation`. This skill only routes to them.
- Filing Jira epics or stories: `crv-create-jira-epic`, `crv-create-jira-story`.
- A small change with no staged process asked for: just do it.

## What the engineer says, what you run

`<p>` is the Bolt folder. Say the result in a few plain lines.

| The engineer says | You run | You tell them |
|---|---|---|
| "What is the current architecture?" | `status --bolt <p> --format text`, then read the `## Digest` of `architecture/hla.md` | The architecture in a few lines, and any contribution still `draft` or `proposed` (not yet in `hla.md`). |
| "Start investigating the data migration approach." | Hand over to `crv-aidlc-hla`: it opens `architecture/contributions/<concern>.md` and records `contribution ... --status draft` | Which file holds the investigation, and what it will settle. |
| "Show me the relevant decisions for this Slice." | `context --bolt <p> --slice <s>`; its `relies_on` lists the decision ids with a one-line gloss | The decisions the Slice relies on, in plain words, and anything that changed since work started. |
| "Continue my Unit." | `next --bolt <p> --mine`, then `context --bolt <p> --unit <u>`; hand the stage to its skill | What the Unit is doing, the next step, what changed under it. |
| "What is blocking this implementation?" | `next --bolt <p> --unit <u>` (what it waits for), `status --bolt <p> --format text` (open gaps, Slices waiting, "Not verified") | Each blocker, who or what it waits for, and what would clear it. |
| "The integration contract has changed. Evaluate whether my work is affected." | `context --bolt <p> --unit <u>`; for the contract's id `context --bolt <p> --id <id>` | Who relies on the contract, what in the Unit is likely affected, whether to revise. Then record the conclusion with `context ... --unit <u> --note "<conclusion>"`. |
| "Proceed with your recommended approach." | `gate --bolt <p> --stage <s> [--unit <u>\|--slice <sl>] --approve --note "<the direction>"`, or `slice --bolt <p> --ready <sl> --note "<the direction>"` for a Slice with open gaps | One line: what was recorded and what runs next. No second question. |
| "Show me what has happened in this Bolt." | `overview --root <planning repo> --format text --log 20`, and `status --bolt <p> --format text` | The stages passed, the Slices and their state, the last directions and conclusions from the log. |
| "Plan the next Slice." | Hand over to `crv-aidlc-inception`: it adds the Slice, merges its Units, then runs `slice --bolt <p> --ready <sl>` | The Slice, its Units, and any readiness gap with its consequence and a recommendation. |

## Open a Bolt

1. Run `check_prerequisites.py --if-stale --root <planning repo>` (add `--jira` when the Bolt will use Jira). On exit 1 show the failing lines with their fix commands and stop; do not open the Bolt. A warning is reported, not a stop. One warning to expect: the planning repo's `.gitattributes` needs two lines so two engineers' log lines never conflict: `bolts/*/log.md merge=union` and `bolts/*/units/*/log.md merge=union`. In the same message say whether subagents and the three model tiers are available in this session: a script cannot know. A new machine is set up with `python3 onboard.py` from the skills checkout: SSH key for Azure DevOps, the three clones, the skills, then this check.
2. Ask for what is missing, in one message: title, one-sentence intent, target repositories (`name=path`), scope (default `classic`: every stage; `express`: requirements, code, build and test, with one default unit; `bugfix`: the same at minimal depth, with a mandatory regression test), depth (`minimal`, `standard`, `comprehensive`; default `standard`, `minimal` for `bugfix`), the ADR registry path if one applies. Recommend a scope: a small, low-risk change takes `express` or `bugfix`, not the whole process.
3. Run `aidlc_state.py open --root <planning repo> --slug <kebab-case> --title ... --intent ... [--scope ..] [--depth ..] [--target name=path]... [--architecture-ref <path>]`. It refuses when the folder exists: resume instead. Repository paths are per machine, kept in `.aidlc-local.json` at the planning root (never committed); a target defaults to the folder of that name next to the planning repo. `--units split` (or `"units": "split"` in `aidlc.json`) gives each Unit its own state file and log, so engineers building different Units do not collide. A `express` or `bugfix` Bolt starts with Slice `s1` already ready.
4. Tell the user which target was classified brownfield or greenfield and the rule that matched (in `log.md`). If a person disagrees, say so at the Workspace Detection checkpoint.
5. Raw documents the user hands in go to `inputs/`, untouched. When there are any, run `index_inputs.py --bolt <p>`, then give the outline to economy-tier workers, one section each, to write `knowledge/_digest.md`: at most 5 lines per section, each with source path and line range.
6. For each brownfield target, `open` reports the shared code knowledge (`codekb/<repo>/` at the planning repo root) as missing, fresh or stale. Re-run it any time with `aidlc_state.py codekb-status --bolt <p>`; a stale store comes with the changed files and `rescan: focused|full` for the reverse-engineering stage.
7. Organisation-wide presets (default answers, so a question they answer is not asked) live in `docs/presets.md` at the planning repo root, written by people (template: `assets/presets-template.md`); `lint_questions.py --presets <file>` checks it.
8. If the ADR registry applies, run `build_adr_index.py --registry <path> --out <planning repo>/architecture-index.json --refresh`. It fetches the registry, fast-forwards a clean checkout and prints the ADRs added or changed in status. If it warns that the checkout is behind and was left alone, tell the user.
9. Give the user the `workspace.file` from `open` (a multi-root workspace for the editor) and its `claude_command` for the terminal, and report any checkout marked `stale` before a stage reads code. The file holds machine-specific paths: `*.code-workspace` belongs in the planning repo's `.gitignore`. Change targets later with `target --add name=path | --remove name`; other folders with `workspace --extra name=path`.

## Resume

Run `aidlc_state.py status --bolt <p> --format text`, then `aidlc_state.py next --bolt <p>`. Say in at most 5 lines where the Bolt stands and what the next step is, and mention any "saved here, not shared yet" line. Read nothing else from the Bolt. If `parked` has a note, show it first. A resume after weeks is the same: the state is the memory, not the old conversation. Before a stage that reads code, run `workspace --bolt <p>` and name any `stale` checkout. An engineer resumes their own work with `next --mine` or `next --unit <u>`, which also say what the Unit waits for; `brief --unit <u> --write` gives its starting page. Read the `context` field of the result: if it is not empty, follow "Changed inputs" in the core rules.

## Route to the stage

`next` returns the stage, Unit or Slice, step, action, skill and reference. Hand over the Bolt path, the stage id, the Unit or Slice and the reference file. In a split Bolt, action `units` lists one entry per Unit still open and `slices` one per Slice: hand each its own stage, or work the one the person owns. Run `inputs` before the stage starts; exit 3 means an earlier stage has not produced a file, so report which and stop.

| Stage | Skill |
|---|---|
| workspace-detection, document-knowledge | this skill |
| reverse-engineering | `crv-aidlc-reverse-engineering` |
| hla | `crv-aidlc-hla` |
| tdd | `crv-aidlc-tdd` |
| requirements-analysis, user-stories, domain-design, units-generation, contract-design, delivery-planning | `crv-aidlc-inception` |
| functional-design, nfr-requirements, nfr-design, infrastructure-design, code-generation (per Unit); build-and-test (per Slice) | `crv-aidlc-construction` |
| deployment-pipeline, deployment-execution (per Slice) | `crv-aidlc-operation` |

Build and Test and the two Operation stages belong to a Slice: use `next --slice <s>`, and pass `--slice <s>` to `decide`, `step`, `gate` and `inputs` (a Bolt with one Slice needs no flag). Their files are under `docs/slices/<slice>/`. They are not Bolt-level.

Action `decide`: recommend EXECUTE or SKIP with a reason (`next` shows `runs_when` and, per Unit, the Unit's `kind`); if the engineer has no objection, record it with `decide`. A per-Unit design stage is decided when that Unit's construction starts. Action `load-units`: Units (each with `kind`: `service`, `spec`, `ui`, `packaging` or `library`) come from Units Generation, Slices from Delivery Planning; `crv-aidlc-inception` writes them with `units --set`. `hla` and `tdd` run in `classic` only unless forced with `decide`. The stage skill moves steps with `step --to asked|analysed|produced`.

Question classes, `## Assumed` and "no quota" are in the core rules.

## Checkpoint

1. At the end of a stage, run `aidlc_state.py gate --bolt <p> --stage <s> [--unit <u> | --slice <sl>] --approve`.
2. Nothing technical open and no material question: it passes. Say so in one line and go on. A material choice is open: ask once, with your recommendation and the alternatives; on "proceed", run it again with `--note "<the direction>"`. Do not ask twice. To send a passed Unit or Slice stage back: `gate ... --request-changes --note "<why>"`.
3. A refusal (exit 1) lists findings: missing artifact, no or over-long `## Digest`, open questions, a missing `Verdict:` line, a failed verdict, ids that `check_traceability.py` reports as untraced. Report each as it is and fix it in the stage's own files. A `Verdict: fail` is never passed: fix, run again, write `pass`. `Verdict: not-run` passes only when the engineer says unverified is acceptable; pass their words in `--note`. Never work around a finding.
4. After a pass the output may carry a suggestion. Pass it on in one line: a fresh session per stage is cheapest, but optional.

## Jira

- One Epic per Bolt, one Story per Unit. A user story (`US-n`) never becomes a Jira issue.
- File them after the Delivery Planning checkpoint, before the first Unit's Construction, with `crv-create-jira-epic` and `crv-create-jira-story` (`crv-aidlc-inception/references/jira-handoff.md`). A Slice added later files its Units' stories the same way.
- Record keys only through the script: `jira --epic KEY`, `jira --unit <u> --story KEY`, `jira --unit <u> --done [--pr URL]`, `jira --off --reason "<why>"`, `jira --on`.
- `decide` and `step` on a Unit's Construction stage are refused until the Unit has a story, unless Jira is off.
- When a Unit's change is merged, its Story is moved to Done by a person, or by the session when it has Jira access. Then record `jira --unit <u> --done`. `close --status complete` is refused while a filed Story is not recorded as done.

## Saving and sharing

The planning repo is shared and everyone works on one branch, named in `aidlc.json`. Every command that changes a Bolt waits its turn if another session is changing the checkout, brings in the team's work, commits the Bolt and pushes it. Do not commit Bolt files by hand. After file changes with no state change, run `aidlc_state.py sync --bolt <p> -m "<what changed>"`, and never end a turn with uncommitted Bolt work (`status` shows the count). The script never commits in a target repository.

When a result says the work is saved in this clone and not shared yet (`not_shared`, or a "not shared yet" line in `status`), tell the engineer plainly and say what to fix (usually the connection), then run `sync`. When the result says the Bolt changed while you were working and the command ran again, say so in one line and check the outcome is still what the engineer asked for. When a result has `undone` or the warning "they were undone: repeat them" (in `git` or `git_before`), say in plain words that the team changed the same state while those commands were saved here and not shared, so they were undone and are not in the Bolt; list them and offer to run them again, one at a time. Artifacts saved meanwhile are kept.

## Close

`aidlc_state.py close --bolt <p> --status complete|superseded|archived [--successor <id>]`. `complete` is refused while an executed stage is not passed, a Slice stage is open, or the Bolt has no Slice; report the list instead of forcing it. To pause, `park --note "<hand-over>"`; `unpark` clears it.

## When a step fails

- Exit 2: a flag is wrong; read the message and fix the command.
- Exit 3: something is missing; name it and the stage that produces it.
- Exit 4: a file is malformed; report its path, do not repair `state.json` by hand.
- Exit 6: git needs you. The output names each file and its rule. A leftover `*.tmp` is never committed. A file with conflict markers stops the commit: resolve the markers, then `sync`. A possible secret stops it too: remove or mask it, then `sync`. For a Bolt's `state.json` never take one side: the output tells you to drop your last commit, pull and run the command again. "Your change was NOT applied; run the command again": run it again.
- Exit 5 or anything unexpected: stop and report the command and the error.
