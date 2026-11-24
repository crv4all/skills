---
name: crv-aidlc-reverse-engineering
description: >-
  Builds or refreshes the code knowledge for each existing (brownfield) target repository of a Bolt before the architecture is written: a deterministic repository inventory, one economy-tier worker per area, and a single synthesis into nine sourced artifacts in a store shared across Bolts (codekb/<repo>/), with a freshness check, focused rescans of what changed, and a list of later artifacts to update when findings arrive late. Use when someone wants to research, understand, reverse-engineer or map an existing codebase for a Bolt, refresh code knowledge, or asks whether the code knowledge is stale or can be reused. Not for opening, resuming or routing a Bolt (crv-aidlc), the architecture document (crv-aidlc-hla), requirements, stories or units (crv-aidlc-inception), building the units (crv-aidlc-construction), or documenting a repository inside itself for onboarding (crv-codebase-onboarding).
license: Apache-2.0
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
  execution: subagent
  model-tier: balanced
---

# Reverse engineering

Builds the code knowledge of each existing target repository: what it does, how it is built, what it exposes, how it is tested, and which files exist. The architecture and every later stage read it instead of reading the code again, so it has to be accurate, sourced and cheap to consume.

## Execution

**Delegate to a subagent. Do not run this in the main session.** Scans and worker reports are large; that context belongs in an agent that exits when the step is done.

**Model tier: `balanced`.** Synthesis must be accurate across many findings, but the reading is routine and is handed to economy-tier workers. State it, do not ask about it. One line, then start work:

> Running `crv-aidlc-reverse-engineering` (step: workers) in a subagent on the balanced tier, with economy-tier workers.

Honour a tier the user names, and say which one you used. Never silently escalate. If this model tier or subagents are not available, say so in one line and run on the session's model.

Read `references/core-rules.md` once per session. Then read only the files the step table names. Scripts live in `scripts/`; run them with `python3`.

## What this produces

Per target repository, in `codekb/<repo>/` at the planning repo root (shared by every Bolt):

- `overview.md`: a `## Digest` of at most 10 lines for the whole repository, then one line per artifact saying what it holds. Later stages read only this file unless they need more.
- Nine artifacts: `business-overview.md`, `architecture.md`, `code-structure.md`, `api-documentation.md`, `component-inventory.md`, `technology-stack.md`, `dependencies.md`, `code-quality-assessment.md`, `reverse-engineering-timestamp.md`. Each starts with a `## Digest`; every claim has a `path:line` source or is marked `unverified`.
- `_meta.json`: `{repo, path, commit, built, artifacts}`; freshness is judged from it.
- In the Bolt, only when needed: `docs/inception/reverse-engineering/reverse-engineering-questions.md` (something only a person can settle) and `propagation.md` (late findings).

Greenfield target: nothing to do. Say so in one line and stop.

## When not to use this

- Opening, resuming or routing a Bolt: `crv-aidlc`.
- The architecture document: `crv-aidlc-hla`. It reads this stage's digests.
- Requirements, stories, domain design or units: `crv-aidlc-inception`.
- Changing the code: `crv-aidlc-construction`.
- Documenting a repository inside itself for people joining it: `crv-codebase-onboarding`.

## Steps

Each row is one run; stop after it. Find the step from `aidlc_state.py next --bolt <p>` and the freshness verdict.

| Step | Read besides core rules | Writes | Ends with |
| --- | --- | --- | --- |
| Check freshness and scan | none | inventory JSON per repo, outside the planning repo | questions file and stop, or go on |
| Workers | `references/worker-brief.md` | nothing (reports kept in memory) | go on |
| Synthesise | `references/reverse-engineering.md` | `codekb/<repo>/*` | go on |
| Gate | none | nothing | `gate --stage reverse-engineering` |
| Focused rescan | `reverse-engineering.md`, `worker-brief.md` | changed artifacts, `_meta.json` | go on to gate |
| Propagation | `reverse-engineering.md` | `propagation.md` | stop until every box is ticked |

### Check freshness and scan

1. `aidlc_state.py status --bolt <p> --format text`, then `inputs --bolt <p> --stage reverse-engineering`. A greenfield target ends here.
2. `aidlc_state.py workspace --bolt <p> --fetch`. If any target checkout is `stale` (behind origin, or not on its default branch), list each with branch and `behind`, and stop unless the approver says to scan as is. A `fetch_error` is reported, not ignored. The commit you read is the one `_meta.json` records.
3. `aidlc_state.py codekb-status --bolt <p>`. Per target it returns `missing`, `fresh` or `stale`, with the changed files and `rescan: focused|full`.
   - `fresh`: reuse. Confirm in one line, do nothing else for that repository.
   - `stale` with `rescan: focused`: use the Focused rescan row.
   - `missing`, or `rescan: full`: the full pipeline below.
4. `python3 scripts/scan_repo.py --repo <path> --out <scratch>/<repo>-scan.json`, where `<scratch>` is any scratch folder outside the planning repo. Read the JSON, not the repository.
5. If the scan shows something only a person can settle, write the question file in the core-rules format and stop.

### Workers

One economy-tier worker per area in the inventory (at most eight), in parallel, each given the brief in `references/worker-brief.md` filled for its area. Collect the reports. Send back once any finding that has no `path:line`.

### Synthesise

One balanced pass writes the nine artifacts and `_meta.json` from the inventory and the reports, following `references/reverse-engineering.md`. Open source files only to verify a specific claim. The existing-files inventory, the test baseline and the brownfield safeguards are required content.

### Gate

Summarise per repository in at most 8 lines: reused, rescanned or rebuilt, coverage, and anything `unverified`. The approver confirms the brownfield or greenfield classification and the artifacts. End as the core rules say, and record the choice with `aidlc_state.py gate --bolt <p> --stage reverse-engineering`. Run `lint_questions.py` first when a question file exists.

### Focused rescan

Only for a `stale` verdict with `rescan: focused`. Re-run the scan, run workers only for the areas holding changed files, update only the affected artifacts and their digests, then continue at the gate. Details are in `references/reverse-engineering.md`.

### Propagation

When HLA, requirements, stories or units already exist and findings are new or changed, write `docs/inception/reverse-engineering/propagation.md`: each affected artifact with a checkbox and what must change. The stage is not complete until every box is ticked and those artifacts are re-approved.

## When a step fails

- `scan_repo.py`: exit 1 means the repository has no tracked files, so check the path and report; 2 a wrong flag; 3 a missing path, not a git repository, or git absent (ask the person for the right path); 4 git could not list files (report it); 5 internal error (report it, do not work around it).
- `aidlc_state.py`: exit 1 is a refusal (read the findings), 2 a wrong flag, 3 a missing file or Bolt, 4 a malformed `state.json` (report it; never edit it by hand).
- `lint_questions.py`: exit 1 lists questions to fix or answers still open.
- A worker returns nothing, or an area is too large to read: split the area, never guess. Record what stayed unread in the scope of analysis.
- The checkout is not at the commit the store records and the person says it should be: report both commits and ask which to use.
