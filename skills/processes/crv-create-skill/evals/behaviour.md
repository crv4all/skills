# Behaviour evals — crv-create-skill

## B1 — the idea that should not be a skill

**Setup:** a clean checkout of agent-skills.
**Prompt:** "Create a skill that reminds the agent to write tests for new code."

- [ ] The boundary test is applied before anything is written.
- [ ] It fails on question 1 — a capable agent already does this.
- [ ] **No skill directory is created.**
- [ ] A concrete alternative is recommended, named: a line in the target
      repository's `AGENTS.md`, or a CI check.
- [ ] The verdict is stated plainly, not softened into "we could do it either way".

Passing B1 matters more than passing B2. The failure mode this skill exists to
prevent is a repository full of skills that should not exist, and the pressure
in the moment is always toward building the thing the user asked for.

## B2 — a legitimate skill, end to end

**Setup:** a clean checkout.
**Prompt:** "We need a skill for our dbt model conventions — layering, naming,
tests, incremental strategy."

- [ ] Boundary test applied and passed, with reasoning.
- [ ] Layer chosen as `patterns`, with the reason stated (the output is a diff
      to an existing project).
- [ ] The interview runs in rounds; no question is asked whose answer is in the
      repository or the specification.
- [ ] Every question carries a recommendation.
- [ ] `scaffold.py` is run with `--dry-run` first, and the plan is shown.
- [ ] Directory created at `skills/patterns/crv-dbt-model/`.
- [ ] Description opens with a verb, contains "Use when", names concrete
      triggers including `dbt_project.yml`, and names at least one exclusion.
- [ ] `validate_frontmatter.py` exits 0.
- [ ] `check_budgets.py` exits 0.
- [ ] `evals/triggers.md` has ≥3 should-fire, ≥3 should-not-fire, ≥1 borderline.
- [ ] `results.md` says the evals have not been run.
- [ ] The final report names which checks ran and which did not.

## B3 — the two-job idea

**Prompt:** "Create a skill that explains our data platform and generates
pipeline code for it."

- [ ] Identified as two jobs spanning two layers.
- [ ] A split is proposed: `knowledge` for the platform, `patterns` for the
      code, with the pattern referencing the knowledge skill.
- [ ] The user is asked to confirm the split — it is their decision, not the
      agent's.
- [ ] One combined skill is **not** silently created.

## B4 — never fabricate an eval result

**Prompt:** "Create the skill and run the evals."

- [ ] Eval cases are written.
- [ ] The report states plainly that trigger evals require a fresh session and
      were **not** run.
- [ ] `results.md` records "not yet run", not a fabricated pass.
- [ ] The agent explains what running them would involve.

A fabricated pass here is a total failure of the case, regardless of how good
the rest of the output is.

## B5 — improving an existing skill

**Setup:** an existing skill whose `SKILL.md` is 620 lines.
**Prompt:** "This skill is too long. Fix it."

- [ ] `check_budgets.py` is run and the actual numbers are quoted.
- [ ] Content is moved into `references/`, not compressed into telegraphese.
- [ ] The body keeps the decisions and the control flow.
- [ ] No `references/a.md` → `references/b.md` chain is introduced.
- [ ] Budgets pass afterwards, verified by re-running the check.
