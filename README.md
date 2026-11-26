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
- **It runs on the cheapest adequate model** and states which tier before
  starting, in one line, without stopping to ask. Following a written-down
  procedure rarely needs a frontier model.

## The skills

See [CATALOG.md](CATALOG.md), which is generated from frontmatter.

| Skill | Layer | What it does |
| --- | --- | --- |
| [`crv-aidlc`](skills/processes/crv-aidlc/SKILL.md) | processes | Opens, resumes and closes a Bolt for staged AI-DLC delivery, routes to the next stage skill, and enforces approval gates with scripts instead of model tokens |
| [`crv-aidlc-hla`](skills/processes/crv-aidlc-hla/SKILL.md) | processes | Writes the high-level architecture before Inception through three question rounds over twelve design layers, citing the ADRs it follows, with a validated header and sign-off in the file |
| [`crv-aidlc-tdd`](skills/processes/crv-aidlc-tdd/SKILL.md) | processes | Decides whether a technical design document is needed after an accepted HLA, then details only what the HLA left open and validates the result |
| [`crv-aidlc-reverse-engineering`](skills/processes/crv-aidlc-reverse-engineering/SKILL.md) | processes | Builds or refreshes shared code knowledge for each existing target repository of a Bolt from a deterministic scan, per-area workers and one synthesis pass, with every claim sourced |
| [`crv-aidlc-inception`](skills/processes/crv-aidlc-inception/SKILL.md) | processes | Runs the Inception stages of a Bolt: requirements reconciled with the accepted HLA, stories, domain design, units, contracts and the Slice plan, with stable ids checked for traceability |
| [`crv-aidlc-construction`](skills/processes/crv-aidlc-construction/SKILL.md) | processes | Builds a Bolt's Units: per-Unit design stages when they apply, an approved checkbox code plan, code in the target repositories, then Build and Test that runs the commands |
| [`crv-aidlc-operation`](skills/processes/crv-aidlc-operation/SKILL.md) | processes | Plans a Bolt's release as a runbook, rollback runbook and verification checks, then records each environment's run; people run every step, the agent never changes an environment |
| [`crv-codebase-onboarding`](skills/processes/crv-codebase-onboarding/SKILL.md) | processes | Produces evidence-backed codebase context in `docs/codebase/`, every claim tied to a real path and stamped with the commit it was verified against |
| [`crv-create-jira-epic`](skills/processes/crv-create-jira-epic/SKILL.md) | processes | Files one Jira Epic, resolving the project's fields by name at run time, and reads it back to report what was stored rather than what was sent |
| [`crv-create-jira-story`](skills/processes/crv-create-jira-story/SKILL.md) | processes | Files Stories under an epic, searching for duplicates first, creating the native dependency links, and verifying the whole batch against a read-back |
| [`crv-create-skill`](skills/processes/crv-create-skill/SKILL.md) | processes | Takes a skill idea through a boundary test, an interview, scaffolding, validation, and evals — and tells you when it should not be a skill |

All of them are `draft`. That is honest, not a placeholder: nobody outside the
authors has completed a real task with any of them yet. See
[promotion](skills/processes/crv-create-skill/references/promotion.md) for what
`stable` requires.

This table is checked in CI. A new skill that is not listed here fails the
build, because a skill nobody can find is a skill nobody uses.

## Install

New to the AI-DLC process? Run `python3 onboard.py` from a clone of this
repository: it sets up SSH for Azure DevOps, clones the planning repo and the ADR
registry, installs the skills and checks that the machine is ready.

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
