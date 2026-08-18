# CRV Agent Skills

Organization-wide [Agent Skills](https://agentskills.io/specification) for CRV.
Vendor-neutral, evidence-driven, and governed by schema-validated frontmatter.

> **Status: maturing, not published.** No marketplace, no install URL. Clone the
> repository and install from the clone. We will add a distribution channel when
> `install.sh` stops being enough — not before, because machinery written before
> anyone has installed a skill is machinery nobody has tested.

## What a skill is here

A directory with a `SKILL.md`. The agent sees only `name` and `description` at
startup, and loads the rest once it decides the skill is relevant. Everything
about this repository follows from that: descriptions are validated for trigger
quality, bodies are budget-capped, and detail lives in `references/` that load
on demand.

Two rules apply to every CRV skill, enforced in CI:

- **It runs in a subagent, not the main session.** Skill work accumulates
  context the user does not want left in their conversation.
- **It runs on the cheapest adequate model**, states which tier before starting,
  and offers to change it. Following a written-down procedure rarely needs a
  frontier model.

## The skills

See [CATALOG.md](CATALOG.md), which is generated from frontmatter.

| Skill | Layer | What it does |
| --- | --- | --- |
| [`crv-codebase-onboarding`](skills/processes/crv-codebase-onboarding/SKILL.md) | processes | Produces evidence-backed codebase context in `docs/codebase/`, every claim tied to a real path and stamped with the commit it was verified against |
| [`crv-create-skill`](skills/processes/crv-create-skill/SKILL.md) | processes | Takes a skill idea through a boundary test, an interview, scaffolding, validation, and evals — and tells you when it should not be a skill |

Both are `draft`. That is honest, not a placeholder: nobody outside the authors
has completed a real task with either one yet. See
[promotion](skills/processes/crv-create-skill/references/promotion.md) for what
`stable` requires.

## Install

```bash
git clone <this-repo> ~/src/agent-skills
cd ~/src/agent-skills
./install.sh --list
./install.sh --skill crv-codebase-onboarding
```

POSIX shell, no dependencies beyond `git`. Always supports `--dry-run`, and
refuses to overwrite a skill you have edited without `--force`. Per-harness
paths for Claude Code, Cursor, Copilot and Codex are in
[docs/installing.md](docs/installing.md).

## Layout

```text
skills/<layer>/crv-<name>/SKILL.md
```

Four layers, described in [skills/README.md](skills/README.md):

| Layer | The output is |
| --- | --- |
| `utilities` | A command result or a transformed file |
| `knowledge` | An answer, or a corrected assumption |
| `patterns` | A diff to an existing project |
| `processes` | A named, reviewable deliverable |

A skill that fits two layers is two skills.

The `crv-` prefix is mandatory. Cursor ships a built-in skill named
`create-skill`, and Codex does not merge same-named skills — it shows both and
makes the user guess.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md), then
[docs/authoring-skills.md](docs/authoring-skills.md). Or use `crv-create-skill`,
which is that document made executable.

```bash
uv sync --all-groups
uv run pytest
uv run standards/scripts/validate_frontmatter.py --strict
```

Everything CI runs, you can run locally with the same command. If CI fails and
you cannot reproduce it, that is a bug in
[the workflow](.github/workflows/ci.yml).

## Documentation

| Document | For |
| --- | --- |
| [docs/design-principles.md](docs/design-principles.md) | Why the repository is shaped this way, decision by decision |
| [docs/authoring-skills.md](docs/authoring-skills.md) | How to write a skill that belongs here |
| [docs/testing-skills.md](docs/testing-skills.md) | Trigger evals, behaviour evals, and what CI cannot check |
| [docs/architecture.md](docs/architecture.md) | What is in the repository and what is generated |
| [docs/installing.md](docs/installing.md) | Per-harness install paths |

## Security

This repository is held to public-safe rules from the first commit, whether or
not it is ever published: no credentials, no customer or farmer data, no
unpublished commercial terms. `scan_secrets.py` runs in CI and reports redacted
fingerprints rather than matched values, because a CI log is itself a place
secrets leak from.

Found something that should not be here? Do not open a public issue. Contact the
owner in [.github/CODEOWNERS](.github/CODEOWNERS).

## Licence

[Apache-2.0](LICENSE). Attribution policy is in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
