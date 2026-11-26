# Eval results — crv-aidlc-inception

Dated record of runs that actually happened. An empty section means the eval
has not been run, which is a true and useful statement. Never record a result
you did not produce.

## Trigger evals

_Not yet run as the file describes (a fresh session per prompt with the skill installed)._

A weaker, simulated check ran on 2026-11-25: one Claude Sonnet agent read the descriptions of all
eleven skills in this repository and the 94 trigger prompts of the seven AI-DLC skills, without
the expected answers, and chose one skill or none for each. It is not the harness's own selection
and not one session per prompt.

Result for this skill's prompts: 14 of 16 as expected.

Not as expected:

- B3 "The new requirement contradicts the HLA's choice of queue." -> crv-aidlc-hla
- N4 "Scan the repository and document how it works." -> crv-codebase-onboarding

## Behaviour evals

Each case ran once, on 2026-11-25, as a fresh Claude Sonnet agent session inside an isolated planning repository with a local bare remote, built for the case with the real state script. The session was given the engineer's prompt and the skill folder to load by path (a copy of commit `fcf3bce` unless a row says otherwise); it was not shown the case's assertions. A second agent graded each assertion from the transcript and the repository state. One run per case: a pass is one observation, not a rate.

| Case | Result | What happened |
| --- | --- | --- |
| B9 | 4 of 4 pass | Two sessions (the second a new session after six answers): Slice 2 added as an increment, existing entries and the state of the existing Units untouched, `slice --add`, `units --set`, `slice --ready` in order. Outside the contract: it added a call to an existing contract and did not tell the engineer that two Units in Construction were now flagged; new Units were named `u-3` next to `u1`. Both corrected in the text (`c612670`); not rerun. Two of the six questions were answerable from the documents. |
| B10 | 2 of 2 pass | Gaps recorded on the engineer's direction with the note; both gaps explained with consequence. First graded as 1 fail because the transcript cut the final message off; regraded from the full message. |

Not run: B1, B2, B3, B4, B5, B6, B7, B8, B11, B12, B13, B14.

## Deterministic checks

| Date | Check | Result |
| --- | --- | --- |
| 2026-11-25 | `uv run pytest` at `c612670` (whole repository) | 971 passed, 1 skipped |
| 2026-11-25 | `aidlc_state.py --help` under `/usr/bin/python3` | pass |
