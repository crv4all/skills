# Choosing a layer, and splitting when two fit

The layer is a signal for humans. Agents never see the path — they select on
the description alone. Layers exist so a reviewer can tell at a glance whether
a change alters organizational fact, house style, or a shipped deliverable, and
apply the matching scrutiny.

## The decision

Ask what the skill's **output** is.

| Output | Layer |
| --- | --- |
| A command result or a transformed file | `utilities` |
| An answer, or a corrected assumption | `knowledge` |
| A diff to an existing project | `patterns` |
| A named, reviewable deliverable | `processes` |

Two useful cross-checks:

**Who reviews the output?** Nobody reviews a command result (`utilities`). A
domain expert reviews a fact (`knowledge`). A code reviewer reviews a diff
(`patterns`). A stakeholder reviews a deliverable (`processes`).

**What does failure look like?** A utility fails loudly, with an exit code.
Knowledge fails silently and confidently. A pattern fails as code that works but
does not fit. A process fails as a deliverable that is incomplete or wrong.

## Layer by layer

### utilities

The hard part is invoking something correctly: the flags, the exit codes, the
failure modes. Applies to any repository, any team, any language.

Most of the body is "when to reach for this, how to invoke it, how to read the
output, what to do when it fails". If your draft is mostly explaining *what to
build*, it is not a utility.

### knowledge

The value is in the facts. A well-informed person knowing those facts would
need no further instruction.

Two rules that make the difference between useful and dangerous:

- **State the fact, then the consequence.** A fact without its consequence gets
  read as trivia and ignored.
- **Date and source anything volatile.** Facts that cannot be re-verified
  cannot be trusted, and cannot be fixed by someone who is not the author.

This repository is public. Facts that cannot be public live in an internal
repository and are referenced by URL, never copied.

### patterns

Applied inside a task the agent is already doing. Shapes one part of it; does
not own it.

- **Show the shape, not a copy-paste blob.** A pattern that is one large code
  block gets pasted where it does not fit.
- **State the rejected alternative.** Without a "not this, because", a pattern
  is indistinguishable from a preference and gets discarded under pressure from
  the surrounding code.
- **Say when it does not apply**, and what to do when the target repository
  already does it another way. The answer is usually "surface the divergence",
  not "rewrite silently".

### processes

Owns a whole unit of work. Takes an ambiguous request, runs phases in an order
that matters, produces something checkable.

- State the output contract up front, as a list a reader can check.
- Separate evidence gathering from interpretation. Where evidence can be
  gathered deterministically, gather it with a script that decides nothing.
- Validate before declaring done, and loop on failure.
- Never claim a step ran that did not.

## When two layers fit

That is the signal to split, not to choose. A skill spanning two layers will
trigger for the wrong requests and load the wrong context for both jobs.

| Symptom | Split into |
| --- | --- |
| "Explains X and then builds Y" | `knowledge` for X, `patterns` for Y |
| "Runs a tool and interprets the results against our standards" | `utilities` for the tool, `knowledge` for the standards |
| "Documents the system and then changes it" | `processes` for the documentation, `patterns` for the change |
| Its description needs the word "and" between two different verbs | Two skills, one per verb |

The last row is the cheapest test available: read your own description. If it
needs "and" to join two unrelated verbs, you have two skills.

### How to split

1. Name each half by its output.
2. Give each its own trigger. If you cannot, they may genuinely be one skill —
   or one of them may not pass the boundary test at all.
3. Put the shared facts in the `knowledge` half.
4. Have the other half reference it explicitly by name, so a reader following
   the chain lands somewhere real.
5. Cross-reference in both descriptions: "…for the X part, see crv-y".

Two small skills with clean triggers beat one large skill with a fuzzy one,
every time. The large one loses selection races against more specific skills
and then fires on requests it should have declined.

## Naming

`crv-<verb>-<noun>` reads best: `crv-create-skill`, `crv-codebase-onboarding`.

- The `crv-` prefix is mandatory. Cursor ships a built-in `create-skill`, and
  Codex does not merge same-named skills — it shows both and makes the user
  guess.
- Do not encode the layer in the name. The path already says it, and a skill
  that moves layers should not need renaming.
- Short enough to type as a slash command. The directory name is what most
  harnesses turn into the command.
