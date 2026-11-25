# Eval results — crv-aidlc-operation

Dated record of runs that actually happened. An empty section means the eval
has not been run, which is a true and useful statement. Never record a result
you did not produce.

## Trigger evals

_Not yet run as the file describes (a fresh session per prompt with the skill installed)._

A weaker, simulated check ran on 2026-11-25: one Claude Sonnet agent read the descriptions of all
eleven skills in this repository and the 94 trigger prompts of the seven AI-DLC skills, without
the expected answers, and chose one skill or none for each. It is not the harness's own selection
and not one session per prompt.

Result for this skill's prompts: 12 of 13 as expected.

Not as expected:

- N5 "Scan the repo and document its structure." -> crv-codebase-onboarding

## Behaviour evals

Each case ran once, on 2026-11-25, as a fresh Claude Sonnet agent session inside an isolated planning repository with a local bare remote, built for the case with the real state script. The session was given the engineer's prompt and the skill folder to load by path (a copy of commit `fcf3bce` unless a row says otherwise); it was not shown the case's assertions. A second agent graded each assertion from the transcript and the repository state. One run per case: a pass is one observation, not a rate.

| Case | Result | What happened |
| --- | --- | --- |
| B6 | 3 of 3 pass | Planned the release of the second Slice only, ran nothing, stopped at seven questions; the grader found none answerable from the documents. |

Not run: B1, B2, B3, B4, B5, B7.

## Deterministic checks

| Date | Check | Result |
| --- | --- | --- |
| 2026-11-25 | `uv run pytest` at `c612670` (whole repository) | 971 passed, 1 skipped |
| 2026-11-25 | `aidlc_state.py --help` under `/usr/bin/python3` | pass |
