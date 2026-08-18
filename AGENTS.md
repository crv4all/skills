# Working in this repository

Instructions for an agent editing **this** repository. For skills that help you
work in *other* repositories, see [CATALOG.md](CATALOG.md).

## What this is

A repository of Agent Skills plus the tooling that keeps them honest. The
product is `skills/`; everything under `standards/` exists to stop a skill
shipping broken.

## Before you change a skill

Read [docs/design-principles.md](docs/design-principles.md). Every rule here has
a reason recorded there, and a change that contradicts a reason should argue
with the reason rather than route around it.

## Rules you will otherwise get wrong

**The frontmatter field set is closed.** Exactly six fields exist: `name`,
`description`, `license`, `compatibility`, `metadata`, `allowed-tools`.
`version` is **not** one of them — it goes inside `metadata`, quoted, because
`version: 1.0` is a YAML float. `disable-model-invocation` is forbidden.

**Every metadata value is a string.** Quote anything numeric.

**Every skill declares `execution: subagent` and `model-tier: economy`**, and
the body must carry a `## Execution` section that acts on them. Both are
enforced; metadata nobody acts on is decoration.

**Two tiers of Python.** Scripts under `skills/**/scripts/` are stdlib-only,
carry a PEP 723 header with `requires-python = ">=3.9"`, and must run as
`python3 script.py` on stock macOS. Tooling under `standards/` uses uv and real
dependencies. Do not blur these: a skill script that imports `yaml` fails on the
machine of the person who needed it.

**Never `print()`.** Structured JSON to stdout via `sys.stdout.write()`, every
diagnostic to stderr via `logging`. Lint enforces it, with no exceptions.

**Never write a script that prompts.** No `input()`, no confirmation prompt, no
pager. An agent shell has nobody at the keyboard, so a prompt is an unbounded
hang.

**`CATALOG.md` is generated.** Change frontmatter, then run
`build_catalog.py --write`. CI fails on drift.

**This repository is public-safe.** No credentials, no customer or farmer data,
no unpublished commercial terms — regardless of whether it is published yet.

## Run before you claim done

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
uv run standards/scripts/validate_frontmatter.py --strict
uv run standards/scripts/check_budgets.py
uv run standards/scripts/build_catalog.py --check
uv run standards/scripts/scan_secrets.py
shellcheck --shell=sh install.sh
```

And for anything touching a bundled skill script, the floor that CI checks and
your machine does not:

```bash
/usr/bin/python3 skills/<layer>/crv-<name>/scripts/<script>.py --help
```

## Honesty rules

These are not style preferences. They are the reason anything in this repository
can be trusted.

- **Never report a check as passed that you did not run.** Name the ones you
  skipped and why.
- **Never record an eval result you did not produce.** A fabricated pass is
  worse than a missing test: it removes the reason to run the real one.
- **Never claim a path exists without checking.** Fabricated paths are
  individually plausible and destroy trust in the whole document.

## Markers

`[TODO]` and `[ASK USER]`. Those two, nothing else. Neither may survive into a
skill at `maturity: stable`.

## Commits

One coherent change per commit, with a message that says why rather than what —
the diff already says what. Do not batch unrelated work into one commit; the
history is how the next person reconstructs the reasoning.
