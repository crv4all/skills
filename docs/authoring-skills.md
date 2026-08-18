# Authoring skills

How to write a skill that belongs in this repository. The reasoning behind
these rules is in [design-principles.md](design-principles.md); this file is
the working procedure.

If you have access to an agent with `crv-create-skill` installed, use it — it
runs the boundary test, the interview, and the scaffolding for you. This
document is what that skill encodes, written for humans.

## Step 0: the boundary test

Before writing anything, answer these. If any answer is "no", stop.

1. **Would a capable agent get this wrong without the skill?** If a competent
   engineer with web access would already do it correctly, a skill adds context
   cost and buys nothing.
2. **Is there a recognizable trigger?** You must be able to write a description
   that distinguishes the situations where this applies from the ones where it
   does not. "Sometimes useful" is not a trigger.
3. **Is it stable enough to be worth maintaining?** If the underlying facts
   change monthly and nobody owns re-verifying them, the skill will be wrong
   within a quarter and confidently so.
4. **Is it one job?** If it spans two layers, it is two skills.

A skill that fails the test is usually better as a paragraph in the target
repository's `AGENTS.md`, a lint rule, or a script with a good `--help`.

## Step 1: choose the layer

| Layer | The skill's output is | Example shape |
| --- | --- | --- |
| `utilities` | A command result or a transformed file | "run this tool correctly" |
| `knowledge` | An answer, or a corrected assumption | "here is what is true at CRV" |
| `patterns` | A diff to an existing project | "here is how we build this part" |
| `processes` | A named, reviewable deliverable | "here is the whole workflow" |

Two answers means two skills. See [skills/README.md](../skills/README.md).

## Step 2: create the directory

```text
skills/<layer>/crv-<name>/
├── SKILL.md          # required
├── references/       # optional: loaded on demand
├── scripts/          # optional: deterministic work
├── assets/           # optional: templates and static resources
└── evals/            # optional but expected: trigger and behaviour cases
```

The `crv-` prefix is not optional. Cursor ships a built-in skill literally
named `create-skill`, and Codex does not merge same-named skills — it shows
both, and the user has to guess. The prefix is how our skills stay
identifiable.

The directory name, the frontmatter `name`, and `metadata.layer` must agree
with the path. `validate_frontmatter.py` enforces all three.

## Step 3: write the frontmatter

```yaml
---
name: crv-example-skill
description: >-
  Does the specific thing, producing the specific output. Use when the user
  asks about X, when a repository contains Y, or when a task requires Z.
license: Apache-2.0
metadata:
  owner: your-team
  layer: processes
  maturity: draft
---
```

Six fields exist and the set is closed. `version`, `author`, `tags`, and
`model` are **not** frontmatter fields; the first three belong under
`metadata`, and the fourth does not exist. `disable-model-invocation` is
forbidden.

### Governance metadata

| Key | Required | Notes |
| --- | --- | --- |
| `owner` | always | A team or distribution list. A person's name is a stopgap; skills outlive team assignments. |
| `layer` | always | Must equal the parent directory. |
| `maturity` | always | `draft` · `stable` · `deprecated`. |
| `version` | at `stable`/`deprecated` | Quoted semver, e.g. `"1.0.0"`. Informational. |
| `tags` | at `stable`/`deprecated` | Comma-separated string, no spaces. A string because the spec only allows strings. |
| `review-cadence` | at `stable`/`deprecated` | `monthly` · `quarterly` · `semiannual` · `annual`. Chosen from how fast the facts move, not from how important the skill feels. |

Quote every numeric-looking value. `version: 1.0` parses as a float and fails.

### Writing the description

This one string decides whether the skill is ever used. Budget real effort on
it.

- **Open with the verb.** "Extracts…", "Produces…", "Validates…". Not "This
  skill helps with…", which spends the most valuable words on nothing.
- **Say what it does *and* when to use it.** Include the second clause
  explicitly: "Use when…". The validator warns if it is missing.
- **Name the concrete triggers** — the file types, tool names, error strings,
  and phrasings that should fire it. These are what the agent matches against.
- **Say when it does not apply**, if there is a near neighbour it could be
  confused with. Disambiguation is worth the characters.

Test it the honest way: show the description alone to someone who has not read
the skill, describe three tasks — one that should trigger it, one that should
not, one borderline — and see whether they route correctly.

## Step 4: write the body

Target well under the budget. Structure that works:

1. **What this produces** — the output contract, stated as something checkable.
2. **When to use it / when not to** — including the near neighbours.
3. **The procedure** — numbered, with the ordering constraints made explicit.
   Say *why* an order matters where it does; an agent under pressure will
   reorder steps whose purpose it cannot see.
4. **Validation** — how the agent checks its own output before reporting done.
5. **Pointers** — one level deep, into `references/`.

Write in the imperative, to the agent. Prefer a rule plus its rationale over a
rule alone: a rule with a reason survives contact with a codebase that
disagrees with it.

Say what to do when a step fails. An unhandled failure is where an agent starts
improvising, and improvisation is exactly what a skill exists to prevent.

### Budgets

| Target | Budget | Enforcement |
| --- | --- | --- |
| `SKILL.md` lines | 500 | warn at `draft`, fail at `stable` |
| `SKILL.md` characters | 25,000 | warn at `draft`, fail at `stable` |
| `SKILL.md` tokens (`cl100k_base`) | 5,000 | warn at `draft`, fail at `stable` |
| `references/*.md` lines | 400 | warning only |

```bash
uv run standards/scripts/check_budgets.py skills/<layer>/crv-<name>
```

Over budget? Move material into `references/`, and link to it from `SKILL.md`.
Do not link `references/a.md` → `references/b.md`; chained references get
loaded late or not at all, and the validator warns about it.

## Step 5: bundle scripts, if the work is deterministic

Anything with one correct answer — parsing a manifest, counting files, checking
a contract — belongs in a script, not in prose the agent re-derives every run.

**Skill-bundled scripts are stdlib-only.** They must run as
`python3 scripts/thing.py` on stock macOS, which ships Python 3.9.6.

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""One line on what this does, then why it exists."""

from __future__ import annotations
```

Then obey the script contract, in full:

- Structured JSON to stdout via `sys.stdout.write()`.
- Every diagnostic to stderr via `logging`. Never `print()` — lint enforces it.
- **Never prompt.** No `input()`, no interactive confirmation, no pager, no
  `getpass`. An agent shell has nobody at the keyboard, so a prompt is an
  unbounded hang the agent cannot distinguish from slow work.
- `--help` documenting flags, examples, and exit codes.
- Distinct exit codes: `0` ok, `1` findings, `2` usage, `3` missing input,
  `4` malformed input, `5` internal error.
- Errors that name the file, the line, and the fix.
- Idempotent: re-running after a partial failure is safe.
- `--dry-run` and an explicit `--confirm` for anything destructive.
- `--output` or pagination when output can get large.
- `pathlib`, not `os.path`.

Scripts that inspect a user's repository additionally must not reach the
network, must not execute project scripts, must not emit secret values, and
must not modify source.

Verify the floor before you commit:

```bash
/usr/bin/python3 skills/<layer>/crv-<name>/scripts/thing.py --help
```

## Step 6: write evals

See [testing-skills.md](testing-skills.md). At minimum: three trigger cases
that should fire the skill, three that should not, and one behavioural case
that checks the output contract.

Never report an eval result you did not produce.

## Step 7: validate

```bash
uv run standards/scripts/validate_frontmatter.py skills/<layer>/crv-<name>
uv run standards/scripts/check_budgets.py skills/<layer>/crv-<name>
uv run standards/scripts/build_catalog.py --write
uv run standards/scripts/scan_secrets.py
```

`build_catalog.py --write` regenerates `CATALOG.md` and both marketplace
manifests. Commit the result; CI fails on drift.

## Step 8: promote from draft when it has earned it

`draft` → `stable` requires: `version`, `tags`, and `review-cadence` present;
budgets passing as hard errors; evals written and actually run; no `[TODO]` or
`[ASK USER]` markers left; and at least one real task completed with the skill
by someone other than its author.

`stable` → `deprecated` requires the body to open with a deprecation notice
naming the replacement. Deprecated skills stay shipped so existing references
resolve.

## Anti-patterns

| Anti-pattern | Why it fails |
| --- | --- |
| A skill that restates general good practice | Costs context, changes nothing. The agent already knows. |
| A description without a trigger | Never selected, or selected constantly. |
| One giant `SKILL.md` with everything inline | Every activation pays for the rare case. |
| Copy-pasteable mega code-block | Gets pasted where it does not fit. Give the shape and the decision points. |
| A rule with no rationale | Discarded the moment the surrounding code disagrees. |
| A script that prompts | Hangs the agent forever. |
| A script that mixes logs into stdout | Breaks the caller's parser. |
| Facts with no date and no source | Cannot be re-verified, so cannot be trusted or fixed. |
| Two jobs in one skill | Wrong triggers, wrong context, both jobs done worse. |
