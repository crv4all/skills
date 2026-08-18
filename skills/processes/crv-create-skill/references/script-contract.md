# The contract for bundled scripts

Anything with exactly one correct answer belongs in a script, not in prose the
agent re-derives every run. Prose gets re-derived differently each time; a
script gets the same answer twice.

## Two tiers

**Skill-bundled scripts** — `skills/**/scripts/`. Stdlib only. PEP 723 header
with `requires-python = ">=3.9"`. Must run as `python3 script.py` on stock
macOS, which ships Python 3.9.6.

The floor is 3.9 because a skill that needs a working `uv` before it can do
anything has replaced the user's problem with an installation problem, at the
exact moment they were trying to get something else done.

**Repo tooling** — `standards/`. Uses `uv` with real dependencies. It only runs
in CI and on contributor machines, so it can assume a working toolchain.

## The header

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""One line on what this does, then why it exists."""

from __future__ import annotations
```

`from __future__ import annotations` lets you write `list[str]` and `X | None`
in annotations on 3.9, where they would otherwise be a runtime error.

## The rules

| Rule | Why |
| --- | --- |
| Structured JSON to stdout via `sys.stdout.write()` | The caller parses it. One `print` of a progress message makes the output unparseable at the worst moment. |
| Every diagnostic to stderr via `logging` | Keeps stdout a clean channel. `print` is banned by lint, so there is no exception to reason about. |
| **Never prompt for input** | An agent shell has nobody at the keyboard. A prompt is an unbounded hang the agent cannot distinguish from slow work. |
| `--help` with flags, examples, and exit codes | It is the only documentation available at the moment of use. |
| Distinct exit code per failure class | Lets the caller tell "the input is wrong" from "the script is broken". |
| Actionable errors | Name the file, the line, and the fix. |
| Idempotent | The agent will re-run after a partial failure. That must be safe. |
| `--dry-run` plus explicit `--confirm` for destructive work | The agent should be able to show its plan before acting. |
| `--output` or pagination for large output | A multi-megabyte payload evicts the context it was meant to inform. |
| `pathlib`, not `os.path` | Consistency, and correct behaviour on Windows checkouts. |

## Exit codes

```text
0  success, no findings
1  findings (the input is wrong, and the script worked correctly)
2  usage error
3  a required input was missing or unreadable
4  a required input was malformed
5  internal error, including a missing dependency
```

The distinction that matters is between `1` and `2`/`5`. Collapsing them is how
a broken script gets mistaken for a clean run.

## No prompting: what that rules out

- `input()` and `getpass`
- "Press any key to continue"
- Confirmation prompts — use `--confirm` as a flag instead
- Anything that opens a pager (`git log` without `--no-pager`)
- Anything that opens an editor
- `sudo`, which prompts for a password on a TTY that does not exist

## Scripts that inspect somebody's repository

Additional rules, and they are not negotiable, because the agent will point
these at repositories nobody asked permission for:

- **No network access.**
- **No execution of project scripts.** Read `package.json`; do not run
  `npm run build`. Reading is inspection; running has side effects on a machine
  you do not own.
- **No secret values in output.** Report that `DATABASE_PASSWORD` is required;
  never report what it is set to.
- **No modification of the target.** Not a formatting fix, not a lint error.
  Report it instead.

Read-only `git` is the one allowed subprocess: `log`, `status`, `rev-parse`,
`diff --name-only`. Never anything that changes the working tree.

## Referencing a script from SKILL.md

```markdown
Run the scanner:

    python3 scripts/scan.py --root <repo> --output scan.json

`--help` documents every flag and the exit codes.
```

Relative to the skill root, one level deep. The validator checks that the path
exists — a dangling reference costs the agent a failed tool call and then an
improvisation, which is exactly what the skill existed to prevent.

## Testing

```bash
/usr/bin/python3 skills/<layer>/crv-<name>/scripts/<script>.py --help
```

Run it against the real floor before committing. A script that only works
inside this repository's 3.12 virtualenv fails on the machine of the person who
needed it, and it fails in a way they cannot diagnose.
