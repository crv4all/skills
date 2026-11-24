---
name: crv-aidlc
description: >-
  Opens, resumes and closes a Bolt (the folder for one piece of work in a planning repo), routes to the next AI-DLC stage and enforces approval gates with deterministic scripts. Use when someone wants to start, open, resume or close a Bolt, asks what is next, mentions AI-DLC, asks whether they are ready to use AI-DLC or how to get started, or wants a structured, staged delivery of a feature, migration or bug fix. Not for the stage work itself: crv-aidlc-reverse-engineering, crv-aidlc-hla, crv-aidlc-tdd, crv-aidlc-inception, crv-aidlc-construction and crv-aidlc-operation own that, and the crv-create-jira-* skills file tickets.
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: economy
---

# AI-DLC entry point

Opens, resumes and closes a Bolt, then hands each stage to the skill that owns it. Progress changes only through `scripts/aidlc_state.py`; never edit `state.json` or `log.md` by hand.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Opening, resuming and gating produce script output and bookkeeping the user does not want left in their conversation.

**Model tier: `economy`**: the cheapest model that can follow instructions and call tools. State it, do not ask about it. One line, then start work:

> Running `crv-aidlc` in a subagent on the economy tier.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session, before the first stage action. All scripts live in `scripts/`; run them from the skill folder with `python3`.

## What this produces

A Bolt `bolts/<date>-<slug>/` in the planning repo, a `state.json` that is true, and a one-line answer to "what is next". Stage artifacts are written by the stage skills, not here.

## When to use this

Opening, resuming or closing a Bolt; "what is next"; and "am I ready to use AI-DLC" or "how do I get started" (run the prerequisites check, then point to `docs/getting-started.md` in the planning repo).

## When not to use this

- Doing the stage itself: `crv-aidlc-reverse-engineering`, `crv-aidlc-hla`, `crv-aidlc-tdd`, `crv-aidlc-inception`, `crv-aidlc-construction`, `crv-aidlc-operation`. This skill only routes to them.
- Filing Jira epics or stories: `crv-create-jira-epic`, `crv-create-jira-story`.
- A small change with no staged process asked for: just do it.

## Open a Bolt

1. Run `check_prerequisites.py --if-stale --root <planning repo>` (add `--jira` when the Bolt will use Jira). On exit 1 show the failing lines with their fix commands and stop; do not open the Bolt. In the same line say whether subagents and the three model tiers are available in this session: a script cannot know. A new machine is set up with `python3 onboard.py` from the skills checkout: SSH key for Azure DevOps, the three clones, the skills, then this check.
2. Ask for what is missing, in one message: title, one-sentence intent, target repositories (`name=path`), scope (default `classic`: every stage; `express`: requirements, code, build and test, with one default unit; `bugfix`: the same at minimal depth, with a mandatory regression test; the names are AWS v2.11.4's), depth (`minimal`, `standard`, `comprehensive`; default `standard`, `minimal` for `bugfix`), the ADR registry path if one applies.
3. Run `aidlc_state.py open --root <planning repo> --slug <kebab-case> --title ... --intent ... [--scope ..] [--depth ..] [--target name=path]... [--architecture-ref <path>] [--parent <bolt id>] [--kind frame|delivery]`. It refuses when the folder exists: resume instead. `--parent` makes this Bolt a child whose HLA builds on the parent's. Use `--kind frame` for programme-level design whose phases become child Bolts: it ends at the HLA gate, every later stage is skipped, and `kind --set` converts a Bolt before those stages start. Repository paths are per machine, kept in `.aidlc-local.json` at the planning root (never committed); a target defaults to the folder of that name next to the planning repo. `--units split` (or `"units": "split"` in `aidlc.json`) gives each unit its own state file and log, so engineers building different units of one Bolt do not collide; changing a unit that someone else owns needs `--takeover "<why>"`.
4. Tell the user which target was classified brownfield or greenfield and the rule that matched (in `log.md`). If a person disagrees, say so at the Workspace Detection gate.
5. Raw documents the user hands in go to `inputs/`, untouched. When there are any, run `index_inputs.py --bolt <p>`, then give the outline to economy-tier workers, one section each, to write `knowledge/_digest.md`: at most 5 lines per section, each with source path and line range.
6. For each brownfield target, `open` reports the shared code knowledge (`codekb/<repo>/` at the planning repo root) as missing, fresh or stale. Re-run it any time with `aidlc_state.py codekb-status --bolt <p>`; a stale store comes with the changed files and `rescan: focused|full` for the reverse-engineering stage.
7. Organisation-wide presets (default answers, so a question they answer is not asked) live in `docs/presets.md` at the planning repo root, written by people (template: `assets/presets-template.md`); `lint_questions.py --presets <file>` checks it.
8. If the ADR registry applies, run `build_adr_index.py --registry <path> --out <planning repo>/architecture-index.json --refresh`. It fetches the registry, fast-forwards a clean checkout and prints the ADRs added or changed in status. If it warns that the checkout is behind and was left alone, tell the user.
9. Give the user the `workspace.file` from `open` (a multi-root workspace for the editor) and its `claude_command` for the terminal, and report any checkout marked `stale` before a stage reads code. The file holds machine-specific paths: `*.code-workspace` belongs in the planning repo's `.gitignore`. Change targets later with `target --add name=path | --remove name`; other folders with `workspace --extra name=path`.

## Resume

Run `aidlc_state.py status --bolt <p> --format text`, then `aidlc_state.py next --bolt <p>`. Say in at most 5 lines where the Bolt stands and what the next step is. Read nothing else from the Bolt. If `parked` has a note, show it first. Before a stage that reads code, run `workspace --bolt <p>` and name any `stale` checkout. An engineer resumes their own work with `next --mine` or `next --unit <u>`, which also say what the unit waits for; `brief --unit <u> --write` gives its starting page. A stage whose inputs changed after it was produced shows `context_changed`, and its gate needs `--ack-context "<what you checked>"`.

## Route to the stage

`next` returns the stage, unit, step, action, skill and reference. Hand over the Bolt path, the stage id, the unit and the reference file. In a split Bolt, action `units` lists one entry per unit still open: hand each its own stage, or work the one the person owns. Run `inputs` before the stage starts; exit 3 means an earlier stage has not produced a file, so report which and stop.

| Stage | Skill |
|---|---|
| workspace-detection, document-knowledge | this skill |
| reverse-engineering | `crv-aidlc-reverse-engineering` |
| hla | `crv-aidlc-hla` |
| tdd | `crv-aidlc-tdd` |
| requirements-analysis, user-stories, domain-design, units-generation, contract-design, delivery-planning | `crv-aidlc-inception` |
| functional-design, nfr-requirements, nfr-design, infrastructure-design, code-generation, build-and-test | `crv-aidlc-construction` |
| deployment-pipeline, deployment-execution | `crv-aidlc-operation` |

Action `decide`: ask the approver for EXECUTE or SKIP with a reason (`next` shows `runs_when` and, per unit, the unit's `kind`), then `decide`. A per-unit design stage is decided when that unit's construction starts. Action `load-units`: units (each with `kind`: `service`, `spec`, `ui`, `packaging` or `library`) come from Units Generation, slices from Delivery Planning; write them to a JSON file and run `units --set`. `hla` and `tdd` run in `classic` only unless forced with `decide`. The stage skill moves steps with `step --to asked|analysed|produced`.

Class each question. Critical (security, compliance, irreversible, data loss) and material (business meaning, public contracts, architecture, other units' work) are asked, with a Class: line. Reversible and trivial choices are decided from conventions and listed under ## Assumed with the reason; the approver can overturn them at the gate.

## Gate

1. The stage skill ends with a summary of at most 8 lines, the paths to review and two choices: Request changes or Continue.
2. On Continue: `aidlc_state.py gate --bolt <p> --stage <s> [--unit <u>] --approve --by "<name>"`. On Request changes: `gate ... --request-changes --note "<what to change>"`. When the person who approved is not the one running the script, add `--channel "<how they said so, e.g. email 2026-11-24>"`: the script refuses without it and records who entered the approval.
3. A refusal (exit 1) lists findings: missing artifact, no or over-long `## Digest`, open questions, a design document (HLA, TDD) whose header a person has not signed as accepted, or, at the last Inception gate, ids that `check_traceability.py` reports as untraced. Fix each in the stage's own files, then gate again. Never work around a refusal and never mark a stage approved yourself.
4. After an approval the output carries a suggestion. Pass it on in one line: a fresh session per stage is cheapest, but optional.

## Jira

- One Epic per Bolt, one Story per unit of work. A user story (`US-n`) never becomes a Jira issue.
- File them after the Delivery Planning gate, before the first unit's Construction, with `crv-create-jira-epic` and `crv-create-jira-story` (`crv-aidlc-inception/references/jira-handoff.md`). Those two skills do not edit or transition existing issues.
- Record keys only through the script: `jira --epic KEY`, `jira --unit <u> --story KEY`, `jira --unit <u> --done [--pr URL]`, `jira --off --reason "<why>"`, `jira --on`.
- `decide` and `step` on a unit's Construction stage are refused until the unit has a story, unless Jira is off.
- When a unit's change is merged, its Story is moved to Done by a person, or by the session when it has Jira access. Then record `jira --unit <u> --done`. `close --status complete` is refused while a filed Story is not recorded as done.

## Git

The planning repo is shared and everyone works on one branch, named in `aidlc.json` at its root. Every command that changes a Bolt first brings in the team's work, then commits the Bolt and pushes it; do not commit Bolt files by hand. After file changes with no state change, run `aidlc_state.py sync --bolt <p> -m "<what changed>"`, and never end a turn with uncommitted Bolt work (`status` shows the count). The script never commits in a target repository.

## Close

`aidlc_state.py close --bolt <p> --status complete|superseded|archived [--successor <id>]`. `complete` is refused while any executed stage is unapproved; report the list instead of forcing it. To pause, `park --note "<hand-over>"`; `unpark` clears it.

## When a step fails

- Exit 2: a flag is wrong; read the message and fix the command.
- Exit 3: something is missing; name it and the stage that produces it.
- Exit 4: a file is malformed; report its path, do not repair `state.json` by hand.
- Exit 6: git needs you. The output names each file and its rule. Resolve it yourself, then run the command or `sync` again; a merge conflict is never a question for the user. A possible secret in the commit is the one stop: remove or mask it, then `sync` again.
- Exit 5 or anything unexpected: stop and report the command and the error.
