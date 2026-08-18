# Eval results — crv-create-jira-story

Dated record of runs that actually happened. An empty section means the eval has
not been run, which is a true and useful statement. Never record a result you did
not produce.

Format:

```markdown
## <YYYY-MM-DD> — <harness and version> — <who ran it>

| Case | Result | Notes |
| --- | --- | --- |
| T1 | pass | |
| B2 | fail | Created a second copy of every story |
```

## Trigger evals

_Not yet run._ Running these needs a fresh session with the skill installed, and
a model in the loop. Nothing in CI does that.

## Behaviour evals

_Not yet run._ These additionally need a Jira tenant the runner can file into.

## Deterministic checks

Bundled scripts run under the Python floor (`/usr/bin/python3`, 3.9.6 on stock
macOS):

| Date | Check | Result |
| --- | --- | --- |
| 2026-08-18 | `jira_setup.py --help` under Python 3.9.6 | pass |
| 2026-08-18 | `--check` with no configuration exits 1, JSON on stdout | pass |
| 2026-08-18 | `--check` against a corrupt file exits 4, not 1 | pass |
| 2026-08-18 | `--token` refused with exit 2 | pass |
| 2026-08-18 | `--set` without `--confirm` writes nothing | pass |
| 2026-08-18 | written configuration has mode 0600 | pass |
