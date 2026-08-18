# Testing skills

A skill can fail in two independent ways, and they need different tests.

1. **Selection failure.** The skill never runs when it should, or runs when it
   should not. This is entirely a property of `name` + `description`, because
   that pair is all the agent sees when deciding.
2. **Behaviour failure.** The skill runs, and the output is wrong, incomplete,
   or unverifiable.

Most skills that "don't work" are selection failures, and most authors test
only for behaviour.

## What CI can and cannot check

CI runs deterministic checks: schema validation, budgets, catalog drift, the
secret scan, and pytest over `standards/`. Those catch structural mistakes.

CI does **not** run a language model, so it cannot check whether a description
actually triggers. Eval cases in `evals/` are executable *by an agent*, not by
GitHub Actions. Running them is a human-initiated step, and the result is
recorded honestly or not at all.

This is the single most important rule in this document: **never claim an eval
ran that did not run.** A fabricated pass is worse than a missing test, because
it removes the reason to run the real one.

## Layout

```text
skills/<layer>/crv-<name>/evals/
├── triggers.md      # should-fire and should-not-fire prompts
├── behaviour.md     # end-to-end cases with expected output contracts
└── results.md       # dated record of actual runs (optional, but the only proof)
```

Plain markdown on purpose. The cases are read by a human deciding what to run,
and by an agent asked to run them; neither benefits from a bespoke format.

## Trigger evals

Write at least three prompts that **should** select the skill, three that
**should not**, and at least one borderline case with the correct answer
argued.

```markdown
## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "Get me up to speed on this repo." | Direct request for codebase context. |
| T2 | "I just joined this team, where do I start?" | Same intent, no shared vocabulary. |
| T3 | "Our docs/codebase notes are stale." | Refresh mode, names the artifact. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "Explain what this function does." | Single-symbol question, no deliverable. | nothing |
| N2 | "Write a README for this library." | Public-facing doc, different audience. | nothing |
| N3 | "Create a skill for our deployment runbook." | Skill authoring. | crv-create-skill |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "Document the payment module." | Do not fire | Scoped to one module and to prose docs, not the ten-file contract. Fire only if the user asks for the codebase context set. |
```

The should-not cases matter more than the should cases. A description that
fires for everything is as useless as one that fires for nothing, and it is
harder to notice, because the failures look like the agent being unhelpful
rather than the skill being absent.

**How to run them.** In a fresh session with the skill installed and no other
context, give the prompt verbatim, and observe whether the agent selects the
skill *before* you say anything else. A session where you have already
mentioned the skill proves nothing.

**Reading a failure.** A missed should-fire usually means the description lacks
the user's actual vocabulary — people say "get me up to speed", not "produce
codebase context". A false should-not-fire usually means the description claims
territory it does not own; narrow it, or add an explicit exclusion.

## Behaviour evals

For each case, state the setup, the prompt, and the output contract as
checkable assertions.

```markdown
### B1 — bootstrap on a repository with no prior context

**Setup:** tests/fixtures/java-spring-maven, no docs/codebase/, no AGENTS.md.
**Prompt:** "Get me up to speed on this codebase."

**Contract:**
- [ ] Mode reported as `bootstrap`, and not asked about.
- [ ] All ten required files exist under docs/codebase/.
- [ ] Every file carries a `verified against <sha> on <date>` stamp.
- [ ] ARCHITECTURE.md traces one end-to-end flow with real file paths.
- [ ] No path named in any output is missing from the repository.
- [ ] No secret values appear anywhere in the output.
- [ ] Divergences between README claims and code are reported, not smoothed over.
```

Prefer contracts a reader can check by looking, over judgements like "the
summary is good". If a criterion cannot be checked, it cannot fail, and a test
that cannot fail is decoration.

## Fixtures

`tests/fixtures/` holds five synthetic repositories used by both the pytest
suite and the behaviour evals:

| Fixture | Exercises |
| --- | --- |
| `java-spring-maven` | Multi-module Maven, Spring Boot, Flyway migrations, Kafka |
| `typescript-nx-monorepo` | Nx workspace, multiple apps and libs, pnpm |
| `python-dbt-databricks` | dbt project, Databricks jobs, Python packaging |
| `terraform-azure` | Terraform modules, Azure Pipelines, environment layering |
| `minimal-unknown` | Almost nothing — checks the skill degrades honestly |

They are deliberately small and deliberately imperfect. Each contains at least
one trap: a README that describes a structure the code no longer has, a
secret-looking environment variable name with no value, a dependency declared
but unused. A skill that reports a clean, confident picture of these fixtures
is a skill that is not looking.

`minimal-unknown` is the most informative of the five. The correct behaviour on
a repository with no signal is to say so — not to produce ten confident files
about a project it cannot see.

## Deterministic tests

```bash
uv run pytest                                              # standards/tests
uv run standards/scripts/validate_frontmatter.py --strict  # frontmatter + layout
uv run standards/scripts/check_budgets.py                  # context budgets
uv run standards/scripts/build_catalog.py --check          # generated-file drift
uv run standards/scripts/scan_secrets.py                   # credentials
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pymarkdown --config standards/configs/pymarkdown.json scan docs skills  # and the root docs
```

The pytest suite covers the validators themselves, plus behavioural assertions
about the bundled scripts against the fixtures — for example, that the scanner
reports the *name* of a secret-looking environment variable and never its
value, and that it never executes anything in the target repository.

Bundled skill scripts are additionally tested against the real floor:

```bash
/usr/bin/python3 skills/processes/crv-codebase-onboarding/scripts/scan.py --help
```

macOS ships Python 3.9.6. A script that only runs under the repo's 3.12
virtualenv is a script that fails on the machine of the person who needed it.

## Before promoting to stable

- [ ] Trigger evals run in a fresh session, results recorded with a date.
- [ ] Behaviour evals run against at least two fixtures, including `minimal-unknown`.
- [ ] Deterministic checks green.
- [ ] Bundled scripts exercised under `/usr/bin/python3`.
- [ ] Someone other than the author completed a real task with the skill.
- [ ] No `[TODO]` or `[ASK USER]` markers remain.
