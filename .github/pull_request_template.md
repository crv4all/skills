## What and why

<!-- What changes, and the reason. The diff already says what; say why. -->

## Checks

Tick what you actually ran. **An unticked box is a fine answer**; a ticked box
that was not run is the thing this template exists to prevent.

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run pyright`
- [ ] `uv run pytest`
- [ ] `uv run standards/scripts/validate_frontmatter.py --strict`
- [ ] `uv run standards/scripts/check_budgets.py`
- [ ] `uv run standards/scripts/build_catalog.py --check`
- [ ] `uv run standards/scripts/scan_secrets.py`

Skipped anything? Say which and why:

<!-- e.g. "pyright: not installed locally, relying on CI" -->

## If this adds or changes a skill

- [ ] Boundary test applied — this genuinely needs to be a skill
- [ ] One layer, not two
- [ ] Description opens with a verb, says "Use when…", names near neighbours it
      should *not* fire for
- [ ] `execution: subagent` and `model-tier: economy`, or a written reason in
      the `## Execution` section
- [ ] Every rule in the body has a reason
- [ ] The body says what to do when a step fails
- [ ] Bundled scripts run under `/usr/bin/python3` (3.9.6)
- [ ] `CATALOG.md` regenerated and committed
- [ ] Eval cases written

Eval results — **record what actually happened**, including "not run":

<!-- e.g. "Trigger evals written, not run: needs a fresh session per prompt." -->

## Anything you are unsure about

<!-- The most useful section. Name what you would like a second opinion on. -->
