# Eval results — crv-create-skill

Dated record of runs that actually happened. An empty section means the eval
has not been run, which is a true and useful statement. Never record a result
you did not produce.

## Trigger evals

_Not yet run._ Trigger evals require a fresh session per prompt with the skill
installed and nothing else in context; they cannot be run from the session that
authored the skill, because that session has already established the context
the eval is testing for.

## Behaviour evals

_Not yet run._

## Deterministic checks

| Date | Check | Result |
| --- | --- | --- |
| 2026-08-18 | `scaffold.py --help` under Python 3.9.6 | pass |
| 2026-08-18 | `scaffold.py` dry run writes nothing | pass |
| 2026-08-18 | `scaffold.py --confirm` renders all five template files | pass |
| 2026-08-18 | Re-run without `--force` refuses and exits 1 | pass |
| 2026-08-18 | Invalid `--name` exits 2 before touching the filesystem | pass |
| 2026-08-18 | Scaffolded SKILL.md passes `validate_frontmatter.py` | see note |

Note: the scaffolded `SKILL.md` is a template with placeholders. It passes
frontmatter validation and fails nothing structural, but it is not a finished
skill until the body is written.
