# Contributing

## Setup

```bash
git clone <this-repo> && cd skills
uv sync --all-groups
uv run pytest
```

You need [uv](https://docs.astral.sh/uv/). Everything else it installs.

If `uv` is itself a pyenv shim on your machine, `.python-version` steers pyenv
as well as uv — it is pinned to `3.12`, which must be a version pyenv has.

Optional, and worth it:

```bash
uvx pre-commit install
```

## Adding a skill

Use `crv-create-skill` if you have it installed; it is
[docs/authoring-skills.md](docs/authoring-skills.md) made executable. Otherwise
follow that document.

The order that matters:

1. **Apply the boundary test before writing anything.** Most skill ideas should
   not become skills, and finding that out early is the point. A skill that
   should not exist costs context on every session forever, and nobody deletes
   it. See
   [the boundary test](skills/processes/crv-create-skill/references/boundary-test.md).
2. Pick one layer. Two layers means two skills.
3. Scaffold, write the body, write the evals.
4. Run the checks below.

## Checks

Everything CI runs, with the same command:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
uv run standards/scripts/validate_frontmatter.py --strict
uv run standards/scripts/check_budgets.py
uv run standards/scripts/build_catalog.py --check
uv run standards/scripts/scan_secrets.py
uv run pymarkdown --config standards/configs/pymarkdown.json scan \
  README.md AGENTS.md CONTRIBUTING.md docs skills
shellcheck --shell=sh install.sh
```

Touched a bundled skill script? Run it on the floor:

```bash
/usr/bin/python3 skills/<layer>/crv-<name>/scripts/<script>.py --help
```

macOS ships Python 3.9.6. CI checks this; your 3.12 virtualenv does not.

Changed frontmatter? Regenerate and commit:

```bash
uv run standards/scripts/build_catalog.py --write
```

## What review looks for

- **Does the description trigger?** Show it alone to someone who has not read
  the skill, with three tasks — one that should fire it, one that should not,
  one borderline — and see whether they route correctly.
- **Does every rule have a reason?** A rule without one is discarded the moment
  the surrounding code disagrees with it.
- **Does it say what to do when a step fails?** Unhandled failure is where an
  agent starts improvising.
- **Is anything in it something a capable agent already knows?** Cut it.
- **Are the eval results real?** `results.md` saying "not yet run" is a fine
  answer. A fabricated pass is not.

## Commits and PRs

One coherent change per commit. Write why, not what — the diff says what.

Branch off `main`; `main` is protected. Fill in the PR template: it asks which
checks you ran, and "I skipped pyright because it was slow" is an acceptable
answer while "all checks pass" when they did not is not.

## Maturity

New skills start at `draft`. Promotion to `stable` has a real bar, including
evals actually run and one real task completed by someone other than the
author: see
[promotion.md](skills/processes/crv-create-skill/references/promotion.md).

Demotion from `stable` back to `draft` is legitimate and underused. If a skill's
facts have gone stale and nobody can re-verify them this week, demote it rather
than leaving a `stable` label on something nobody stands behind.

## Security

Nothing confidential, ever: no credentials, no customer or farmer data, no
unpublished commercial terms. The repository is held to public-safe rules from
the first commit so that publishing later is a decision rather than an audit.

Found something that should not be here? Do not open a public issue — contact
the owner in [.github/CODEOWNERS](.github/CODEOWNERS).

## Attribution

Write our own implementations. We do not copy code, templates, or wording from
other skill repositories. If you do adapt something, add a file header

```text
Adapted from <url> (<license>, <copyright holder>)
```

and an entry in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
