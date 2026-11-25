# Eval results — crv-aidlc-hla

Dated record of runs that actually happened. An empty section means the eval
has not been run, which is a true and useful statement. Never record a result
you did not produce.

## Trigger evals

_Not yet run as the file describes (a fresh session per prompt with the skill installed)._

A weaker, simulated check ran on 2026-11-25: one Claude Sonnet agent read the descriptions of all
eleven skills in this repository and the 94 trigger prompts of the seven AI-DLC skills, without
the expected answers, and chose one skill or none for each. It is not the harness's own selection
and not one session per prompt.

Result for this skill's prompts: 14 of 14 as expected.

## Behaviour evals

Each case ran once, on 2026-11-25, as a fresh Claude Sonnet agent session inside an isolated planning repository with a local bare remote, built for the case with the real state script. The session was given the engineer's prompt and the skill folder to load by path (a copy of commit `fcf3bce` unless a row says otherwise); it was not shown the case's assertions. A second agent graded each assertion from the transcript and the repository state. One run per case: a pass is one observation, not a rate.

| Case | Result | What happened |
| --- | --- | --- |
| B9 | 2 pass, 1 fail, 1 not evaluated | Two sessions (the second a new session after the engineer answered three questions): the resume recovered everything from files and re-asked nothing. Failed: the merge also changed the appendix line naming the decision range, outside `touches`. Not evaluated: the listing of three contributions (the fixture had one). Outside the contract: session 2 set four `proposed` decisions to `accepted` because the engineer "did not object". Both points are corrected in the text (`c612670`); not rerun. |
| B10 | 3 of 3 pass | Found the two owners of the consent record and three further contradictions, each with consequence, options and who should talk; changed nothing. It recommended one option while asking the owners to confirm. |

Not run: B1, B2, B3, B4, B5, B6, B7, B8, B11, B12, B13, B14.

### Reruns of 2026-11-25 (pilot check)

Same method, on rebuilt fixtures and a copy of the working tree that became the pilot commits (the skill text of `c612670`).

| Case | Result | What happened |
| --- | --- | --- |
| B9 | 1 pass, 2 fail, 1 not applicable | Two sessions. Between them the engineer answered one question, left one open and said nothing about the four proposed decisions. Session 2 set the one decision the written answer settles to `accepted` and said so; the other three stayed `proposed` "until you tell me". Only the `hla.md` section named in `touches` changed; no other decision row and no other person's file. Failed: the first commit of the contribution cited its ids one commit before the rows were in `hla-decisions.md`; `contribution --status merged` was never run, because the contribution stays `proposed` while decisions are undecided, which step 4 allows. Not applicable: the listing of three contributions (one engineer). |
| B10 | 3 of 3 pass | Named the two owners of the consent record with both decision ids and both lines, the consequence, the options, a recommendation and who should talk; chose no side; changed nothing; reported the validator's `owner-duplicate`. |

## Deterministic checks

| Date | Check | Result |
| --- | --- | --- |
| 2026-11-25 | `uv run pytest` at `c612670` (whole repository) | 971 passed, 1 skipped |
| 2026-11-25 | `aidlc_state.py --help` under `/usr/bin/python3` | pass |
