# Eval results — crv-codebase-onboarding

Dated record of runs that actually happened. An empty section means the eval
has not been run, which is a true and useful statement. Never record a result
you did not produce.

Format:

```markdown
## <YYYY-MM-DD> — <harness and version> — <who ran it>

| Case | Result | Notes |
| --- | --- | --- |
| T1 | pass | |
| B4 | fail | Asserted a Python project from a single .py file |
```

## Trigger evals

_Not yet run._

## Behaviour evals

_Not yet run._

## Deterministic checks

Bundled scripts run under the Python floor (`/usr/bin/python3`, 3.9.6 on stock
macOS):

| Date | Check | Result |
| --- | --- | --- |
| 2026-08-18 | `scan.py --help` under Python 3.9.6 | pass |
| 2026-08-18 | `validate_context.py --help` under Python 3.9.6 | pass |
| 2026-08-18 | `scan.py` self-scan: stdout is pure JSON, logs on stderr | pass |
