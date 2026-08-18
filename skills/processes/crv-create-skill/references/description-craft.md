# Writing the description

The `name` and `description` of every installed skill are loaded at startup.
That pair is the entire basis on which an agent decides whether to load your
skill. A perfect body behind a vague description never runs.

Budget real effort here. It is the highest-leverage text in the whole skill,
and the part authors underinvest in most.

## The shape

Two clauses, in this order:

1. **What it does** — open with the verb, and name the output.
2. **When to use it** — explicit trigger language, in the words a user would
   actually type.

Then, when there is a near neighbour, a third:

3. **When not to** — name the neighbour and where those requests should go.

## Rules

**Open with the verb.** "Extracts…", "Produces…", "Validates…", "Takes X to
Y…". Never "This skill helps with…" or "A skill for…" — the opening words are
the most valuable characters in the string, and self-description spends them on
nothing. The validator warns about this.

**Say "Use when…" literally.** Descriptions that only say what a skill does
consistently under-trigger. The validator warns when no trigger clause is
present.

**Use the user's vocabulary, not yours.** People type "get me up to speed", not
"produce codebase context". A description written in the author's words and
tested with the author's words passes an eval it should have failed.

**Name concrete triggers.** File names (`dbt_project.yml`), tool names, error
strings, and real phrasings. These are what the agent matches against.

**Name the exclusions.** If there is an adjacent skill, say which requests
belong to it. Disambiguation is worth the characters — an ambiguous pair means
either both fire or neither does.

**Use the space.** The limit is 1024 characters. A 60-character description
loses selection races against more specific skills. Do not pad, but do not be
terse for its own sake either: this is not the place the budget is tight.

## Before and after

**Before:** `Helps with data pipelines.`

Nothing to match on. Fires for everything and for nothing.

**After:**

> Builds and reviews dbt models against CRV data-platform conventions —
> staging/intermediate/mart layering, naming, tests, and incremental strategy.
> Use when working in a repository containing `dbt_project.yml`, when adding or
> changing a dbt model, or when a review flags model structure. Not for
> Databricks job orchestration or for raw ingestion pipelines.

Named artifact, named conventions, three concrete triggers, two exclusions.

---

**Before:** `This skill is used for onboarding to codebases. It reads the
repository and writes documentation.`

Self-referential opening, passive trigger, and "writes documentation" collides
with every documentation request in the session.

**After:** see the description of `crv-codebase-onboarding` — verb first, the
output named as a specific directory, six trigger phrasings drawn from how
people actually ask, and three explicit exclusions.

## How to test it

Show the description **alone** — no body, no context — to someone who has not
seen the skill. Give them three tasks: one that should trigger it, one that
should not, one borderline. Ask which they would route to it.

If a person with full attention and only three options cannot route correctly,
an agent with fifty descriptions in context will not either.

Then write the same cases into `evals/triggers.md` and run them in a fresh
session. See [../../../../docs/testing-skills.md](../../../../docs/testing-skills.md).

## Reading a failure

| Symptom | Cause | Fix |
| --- | --- | --- |
| Never fires | No trigger clause, or the wrong vocabulary | Add "Use when…" in the user's words |
| Fires constantly | Claims territory it does not own | Narrow the verb, add exclusions |
| Loses to another skill | Less specific than its competitor | Add the concrete markers: file names, tool names |
| Fires for the neighbour's requests | No disambiguation | Name the neighbour and redirect |
| Fires only when named explicitly | Description reads as a title, not a trigger | Rewrite the second clause as situations, not as a topic |

## YAML mechanics

Use a block scalar for anything multi-line:

```yaml
description: >-
  First clause about what it does. Use when <situations>. Not for <neighbour>.
```

`>-` folds newlines into spaces and strips the trailing newline, so the stored
value is one clean line regardless of how you wrapped it in the file. Avoid
quoting gymnastics with colons and apostrophes — a block scalar sidesteps both.
