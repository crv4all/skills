# Eval results — crv-aidlc-reverse-engineering

Dated record of runs that actually happened. An empty section means the eval
has not been run, which is a true and useful statement. Never record a result
you did not produce.

## Trigger evals

_Not yet run as the file describes (a fresh session per prompt with the skill installed)._

A weaker, simulated check ran on 2026-11-25: one Claude Sonnet agent read the descriptions of all
eleven skills in this repository and the 94 trigger prompts of the seven AI-DLC skills, without
the expected answers, and chose one skill or none for each. It is not the harness's own selection
and not one session per prompt.

Result for this skill's prompts: 13 of 14 as expected.

Not as expected:

- B2 "Get me up to speed on the legacy importer before I change it." -> crv-codebase-onboarding

## Behaviour evals

_Not yet run._

## Deterministic checks

| Date | Check | Result |
| --- | --- | --- |
| 2026-11-25 | `uv run pytest` at `c612670` (whole repository) | 971 passed, 1 skipped |
| 2026-11-25 | `aidlc_state.py --help` under `/usr/bin/python3` | pass |
