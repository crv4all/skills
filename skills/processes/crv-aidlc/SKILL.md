---
name: crv-aidlc
description: >-
  Opens, resumes and closes a paddock (the folder for one piece of work in a planning repo), routes to the next AI-DLC stage and enforces approval gates with deterministic scripts. Use when someone wants to start, open, resume or close a paddock, asks what is next, mentions AI-DLC, or wants a structured, staged delivery of a feature, migration or bug fix. Not for the stage work itself: crv-aidlc-reverse-engineering, crv-aidlc-hla, crv-aidlc-tdd, crv-aidlc-inception, crv-aidlc-construction and crv-aidlc-operation own that, and the crv-create-jira-* skills file tickets.
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# AI-DLC entry point

Opens, resumes and closes a paddock, then hands each stage to the skill that owns it. Progress changes only through `scripts/aidlc_state.py`; never edit `state.json` or `log.md` by hand.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Opening, resuming and gating produce script output and bookkeeping the user does not want left in their conversation.

**Model tier: `economy`**: the cheapest model that can follow instructions and call tools. State it, do not ask about it. One line, then start work:

> Running `crv-aidlc` in a subagent on the economy tier.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session, before the first stage action. All scripts live in `scripts/`; run them from the skill folder with `python3`.

## What this produces

A paddock `paddocks/<date>-<slug>/` in the planning repo, a `state.json` that is true, and a one-line answer to "what is next". Stage artifacts are written by the stage skills, not here.

## When not to use this

- Doing the stage itself: `crv-aidlc-reverse-engineering`, `crv-aidlc-hla`, `crv-aidlc-tdd`, `crv-aidlc-inception`, `crv-aidlc-construction`, `crv-aidlc-operation`. This skill only routes to them.
- Filing Jira epics or stories: `crv-create-jira-epic`, `crv-create-jira-story`.
- A small change with no staged process asked for: just do it.

## Open a paddock

1. Ask for what is missing, in one message: title, one-sentence intent, target repositories (`name=path`), scope (default `classic`: every stage; `express`: requirements, code, build and test, with one default unit; `bugfix`: the same at minimal depth, with a mandatory regression test; the names are AWS v2.11.4's), depth (`minimal`, `standard`, `comprehensive`; default `standard`, `minimal` for `bugfix`), the ADR registry path if one applies.
2. Run `aidlc_state.py open --root <planning repo> --slug <kebab-case> --title ... --intent ... [--scope ..] [--depth ..] [--target name=path]... [--architecture-ref <path>] [--parent <paddock id>] [--kind frame|delivery]`. It refuses when the folder exists: resume instead. `--parent` makes this paddock a child whose HLA builds on the parent's. Use `--kind frame` for programme-level design whose phases become child paddocks: it ends at the HLA gate, every later stage is skipped, and `kind --set` converts a paddock before those stages start.
3. Tell the user which target was classified brownfield or greenfield and the rule that matched (in `log.md`). If a person disagrees, say so at the Workspace Detection gate.
4. Raw documents the user hands in go to `inputs/`, untouched. When there are any, run `index_inputs.py --paddock <p>`, then give the outline to economy-tier workers, one section each, to write `knowledge/_digest.md`: at most 5 lines per section, each with source path and line range.
5. For each brownfield target, `open` reports the shared code knowledge (`codekb/<repo>/` at the planning repo root) as missing, fresh or stale. Re-run it any time with `aidlc_state.py codekb-status --paddock <p>`; a stale store comes with the changed files and `rescan: focused|full` for the reverse-engineering stage.
6. If the ADR registry applies, run `build_adr_index.py --registry <path> --out <planning repo>/architecture-index.json`.
7. Give the user the `workspace.file` from `open` (a multi-root workspace for the editor) and its `claude_command` for the terminal, and report any checkout marked `stale` before a stage reads code. The file holds machine-specific paths: `*.code-workspace` belongs in the planning repo's `.gitignore`. Change targets later with `target --add name=path | --remove name`; other folders with `workspace --extra name=path`.

## Resume

Run `aidlc_state.py status --paddock <p> --format text`, then `aidlc_state.py next --paddock <p>`. Say in at most 5 lines where the paddock stands and what the next step is. Read nothing else from the paddock. If `parked` has a note, show it first. Before a stage that reads code, run `workspace --paddock <p>` and name any `stale` checkout.

## Route to the stage

`next` returns the stage, unit, step, action, skill and reference. Hand over the paddock path, the stage id, the unit and the reference file. Run `inputs` before the stage starts; exit 3 means an earlier stage has not produced a file, so report which and stop.

| Stage | Skill |
|---|---|
| workspace-detection, document-knowledge | this skill |
| reverse-engineering | `crv-aidlc-reverse-engineering` |
| hla | `crv-aidlc-hla` |
| tdd | `crv-aidlc-tdd` |
| requirements-analysis, user-stories, domain-design, units-generation, contract-design, delivery-planning | `crv-aidlc-inception` |
| functional-design, nfr-requirements, nfr-design, infrastructure-design, code-generation, build-and-test | `crv-aidlc-construction` |
| deployment-pipeline, deployment-execution | `crv-aidlc-operation` |

Action `decide`: ask the approver for EXECUTE or SKIP with a reason (`next` shows `runs_when` and, per unit, the unit's `kind`), then `decide`. A per-unit design stage is decided when that unit's construction starts. Action `load-units`: units (each with `kind`: `service`, `spec`, `ui`, `packaging` or `library`) come from Units Generation, bolts from Delivery Planning; write them to a JSON file and run `units --set`. `hla` and `tdd` run in `classic` only unless forced with `decide`. The stage skill moves steps with `step --to asked|analysed|produced`.

## Gate

1. The stage skill ends with a summary of at most 8 lines, the paths to review and two choices: Request changes or Continue.
2. On Continue: `aidlc_state.py gate --paddock <p> --stage <s> [--unit <u>] --approve --by "<name>"`. On Request changes: `gate ... --request-changes --note "<what to change>"`.
3. A refusal (exit 1) lists findings: missing artifact, no or over-long `## Digest`, open questions, a design document (HLA, TDD) whose header a person has not signed as accepted, or, at the last Inception gate, ids that `check_traceability.py` reports as untraced. Fix each in the stage's own files, then gate again. Never work around a refusal and never mark a stage approved yourself.
4. After an approval the output carries a suggestion. Pass it on in one line: a fresh session per stage is cheapest, but optional.

## Close

`aidlc_state.py close --paddock <p> --status complete|superseded|archived [--successor <id>]`. `complete` is refused while any executed stage is unapproved; report the list instead of forcing it. To pause, `park --note "<hand-over>"`; `unpark` clears it.

## When a step fails

- Exit 2: a flag is wrong; read the message and fix the command.
- Exit 3: something is missing; name it and the stage that produces it.
- Exit 4: a file is malformed; report its path, do not repair `state.json` by hand.
- Exit 5 or anything unexpected: stop and report the command and the error.
