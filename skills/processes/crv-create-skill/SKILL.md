---
name: crv-create-skill
description: >-
  Takes a skill idea from "we should have a skill for this" to a validated
  skill in the CRV agent-skills repository: applies a boundary test to decide
  whether a skill is the right artifact at all, runs a round-based interview
  that asks only the decisions a person actually has to make, scaffolds into
  the correct capability layer, validates frontmatter and context budgets, and
  writes trigger evals. Use when someone wants to create, author, scaffold,
  split, or improve an agent skill or SKILL.md, when a skill needs review
  before merge, or when a repeated instruction should become reusable. Not for
  invoking an existing skill, and not for documenting a codebase — that is
  crv-codebase-onboarding.
license: Apache-2.0
compatibility: Requires Python 3.9+. Full validation additionally requires a checkout of crv4all/agent-skills and uv.
metadata:
  owner: cloudforce-team-data
  layer: processes
  maturity: draft
---

# Create a skill

Most skill ideas should not become skills. The first job is to find out which
kind this is, and to say so before anyone has written a `SKILL.md`.

## What this produces

A skill directory that passes every repository check, plus an honest account of
what was and was not verified.

```text
skills/<layer>/crv-<name>/
├── SKILL.md          # frontmatter + body, within budget
├── references/       # detail loaded on demand
├── scripts/          # deterministic work, if any
├── assets/           # templates and static resources, if any
└── evals/            # triggers.md, behaviour.md, results.md
```

Plus: `validate_frontmatter.py` and `check_budgets.py` passing, `CATALOG.md`
regenerated, and a report naming every check that ran and every check that did
not.

## When not to use this

- Using a skill that already exists → just use it.
- Documenting a codebase → `crv-codebase-onboarding`.
- A one-off instruction for the current task → say it in the prompt.
- A rule that a linter could enforce → write the lint rule. It runs every time,
  and it cannot be talked out of its opinion.

## Step 1 — The boundary test

Answer all four before writing anything. **Any "no" ends the process**, with a
recommendation instead of a skill.

1. **Would a capable agent get this wrong without it?** If a competent engineer
   with web access would already do it correctly, the skill costs context and
   buys nothing.
2. **Is there a recognizable trigger?** You must be able to name the situations
   where this applies and, just as importantly, the near neighbours where it
   does not. "Sometimes useful" is not a trigger.
3. **Is it stable enough to maintain?** If the facts change monthly and nobody
   owns re-verifying them, the skill will be confidently wrong within a
   quarter. Confidently wrong is worse than absent.
4. **Is it one job?** If it spans two layers, it is two skills.

Say the verdict out loud. When it fails, name the better artifact — a paragraph
in the target repository's `AGENTS.md`, a lint rule, a script with a good
`--help`, or a page in existing documentation.

Detail and worked examples: [references/boundary-test.md](references/boundary-test.md).

## Step 2 — The interview

**Facts are your job. Decisions are the user's.** Never ask what the
filesystem, git, the repository's own docs, or the Agent Skills specification
can answer — look it up. Every question you ask should be one where a
reasonable person could answer either way and the outcome would differ.

Run it in **rounds over the frontier of settled decisions.** In each round:

1. Research everything the current round needs that is a fact.
2. Identify the decisions that are now unblocked — the ones whose inputs are
   settled and whose answers change what comes next.
3. Ask those, batched, in one turn. Give a recommendation with each.
4. Record what was settled. Move the frontier.

The frontier matters because skill decisions are dependent. Asking about
reference-file structure before the scope is settled produces an answer that
has to be thrown away, and it spends the user's patience on a question that was
not yet real.

Typical rounds:

| Round | Settles | Blocked until |
| --- | --- | --- |
| 1 | Purpose, and the near neighbours it must not be confused with | — |
| 2 | Layer, and therefore the shape of the output | Round 1 |
| 3 | Scope: what is in, what is explicitly out, what gets split off | Round 2 |
| 4 | Triggers, in the user's own vocabulary | Round 3 |
| 5 | Scripts: what is deterministic enough to be code | Round 3 |
| 6 | Ownership, maturity, review cadence | Round 2 |

Stop when the frontier is empty. Do not ask questions to look thorough; every
question spends attention the user could be spending on the answers that
matter. Method and question banks: [references/interview.md](references/interview.md).

## Step 3 — Choose the layer

| Layer | The output is | Ask |
| --- | --- | --- |
| `utilities` | A command result or a transformed file | Is the hard part invoking something correctly? |
| `knowledge` | An answer, or a corrected assumption | Would a well-informed person need no further instruction? |
| `patterns` | A diff to an existing project | Is this applied inside someone else's task? |
| `processes` | A named, reviewable deliverable | Is there something a person would review? |

Two answers means two skills. Split, and have the `processes` skill reference
the `knowledge` skill. Splitting is the most common correct outcome of this
step, and the one authors resist most.

See [references/layer-selection.md](references/layer-selection.md).

## Step 4 — Scaffold

```bash
python3 scripts/scaffold.py \
  --repo <path-to-agent-skills> \
  --name crv-<name> --layer <layer> --owner <team> \
  --description "<the description>" \
  --dry-run
```

`--dry-run` prints the plan and writes nothing. Re-run with `--confirm` to
write. It never overwrites an existing file without `--force`, and re-running
it is safe.

Then write the body. Structure that works:

1. **What this produces** — the output contract, checkable.
2. **When to use it, and when not** — including near neighbours by name.
3. **The procedure** — numbered, with ordering constraints and the reason each
   order matters. An agent under pressure reorders steps whose purpose it
   cannot see.
4. **Validation** — how the skill checks its own output before reporting done.
5. **Pointers** — one level deep, into `references/`.

Write to an agent that is already competent. A skill exists to correct what a
capable agent gets *wrong*, not to teach it the basics.

Pair every rule with its reason. A rule with no rationale is discarded the
moment the surrounding code disagrees with it.

## Step 5 — The description

This one string decides whether the skill is ever used. It deserves more effort
than any paragraph in the body, and it is the thing authors underinvest in.

- Open with the verb: "Extracts…", "Produces…", "Validates…". Never "This skill
  helps with…", which spends the most valuable words on nothing.
- Say what it does **and** when to use it, explicitly: "Use when…".
- Name concrete triggers — file types, tool names, error strings, and the
  phrasings a user would actually type.
- Name the near neighbours it should *not* fire for, and where they should go
  instead. Disambiguation is worth the characters.

Craft, worked before-and-after examples, and the failure modes:
[references/description-craft.md](references/description-craft.md).

## Step 6 — Validate

```bash
uv run standards/scripts/validate_frontmatter.py skills/<layer>/crv-<name>
uv run standards/scripts/check_budgets.py skills/<layer>/crv-<name>
uv run standards/scripts/build_catalog.py --write
uv run standards/scripts/scan_secrets.py
```

Bundled scripts must additionally run under the floor, because a script that
only works inside this repository's virtualenv fails on the machine of the
person who needed it:

```bash
/usr/bin/python3 skills/<layer>/crv-<name>/scripts/<script>.py --help
```

Over budget? Move detail into `references/`. Do not compress prose into
telegraphese — the budget is about what the agent must load, not about how
tersely it is phrased, and unreadable instructions get ignored rather than
followed.

## Step 7 — Trigger evals

Write `evals/triggers.md`: at least three prompts that should fire the skill,
three that should not with the skill that should fire instead, and one
borderline case with the correct answer argued.

The should-not cases matter more. A description that fires for everything is as
useless as one that fires for nothing, and it is harder to notice, because the
failures look like the agent being unhelpful rather than the skill being wrong.

Draw the should-fire prompts from how the *user* talks, not from the skill's
own vocabulary. A description written in the author's words and tested with the
author's words passes an eval it should have failed.

**Never report an eval as run when it was not.** You can write the cases; you
generally cannot run them, because running them means a fresh session with the
skill installed. Write them, say plainly that they are unrun, and record real
results in `evals/results.md` when someone runs them.

That rule is not a formality. A fabricated pass is worse than a missing test,
because it removes the reason to run the real one.

## Step 8 — Iterate

Read the finished `SKILL.md` as if you had never seen the conversation. The
context that made it feel complete is not available to the agent that will load
it.

- Is the trigger obvious from the description alone?
- Does the body assume something only this conversation established?
- Is any section restating what a capable agent already knows? Cut it.
- Does every rule have a reason?
- Does it say what to do when a step fails? Unhandled failure is where an agent
  starts improvising, and improvisation is what the skill exists to prevent.

Then reduce. The most common defect in a first draft is length, and the second
is a description that describes the skill to its author rather than to a
stranger.

## Reporting

Close with: the boundary-test verdict · the layer and why · what was created ·
which checks ran and their results · which checks did **not** run and why ·
every open `[TODO]` and `[ASK USER]`.

Promotion from `draft` to `stable` has its own bar:
[references/promotion.md](references/promotion.md).

## References

- [references/boundary-test.md](references/boundary-test.md) — should this be a skill at all
- [references/interview.md](references/interview.md) — the round-based method and question banks
- [references/layer-selection.md](references/layer-selection.md) — choosing and splitting
- [references/description-craft.md](references/description-craft.md) — the string that decides everything
- [references/script-contract.md](references/script-contract.md) — the rules for bundled scripts
- [references/promotion.md](references/promotion.md) — draft to stable to deprecated
- `scripts/scaffold.py` — idempotent directory scaffolding
- `assets/skill-template/` — the starting files
