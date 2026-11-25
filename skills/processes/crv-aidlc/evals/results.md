# Eval results — crv-aidlc

Dated record of runs that actually happened. An empty section means the eval
has not been run, which is a true and useful statement. Never record a result
you did not produce.

## Trigger evals

_Not yet run as the file describes (a fresh session per prompt with the skill installed)._

A weaker, simulated check ran on 2026-11-25: one Claude Sonnet agent read the descriptions of all
eleven skills in this repository and the 94 trigger prompts of the seven AI-DLC skills, without
the expected answers, and chose one skill or none for each. It is not the harness's own selection
and not one session per prompt.

Result for this skill's prompts: 11 of 13 as expected.

Not as expected:

- B1 "Do the requirements analysis for the billing Bolt." -> crv-aidlc-inception
- T5 "What is blocking my Unit in the billing Bolt?" -> crv-aidlc-construction

## Behaviour evals

Each case ran once, on 2026-11-25, as a fresh Claude Sonnet agent session inside an isolated planning repository with a local bare remote, built for the case with the real state script. The session was given the engineer's prompt and the skill folder to load by path (a copy of commit `fcf3bce` unless a row says otherwise); it was not shown the case's assertions. A second agent graded each assertion from the transcript and the repository state. One run per case: a pass is one observation, not a rate.

| Case | Result | What happened |
| --- | --- | --- |
| B2 | 2 pass, 2 not evaluated | The harness permission layer of the evaluating session denied the session's `gate --approve` command, so the refusal on the missing digest was never exercised. Nothing changed in the Bolt. |
| B12 | 4 of 4 pass | Changed decision found from the context report, impact explained, conclusion recorded in the Unit log; nothing else changed. |
| B13 | 3 of 3 pass | Answer from the digest, read-only. |
| B14 | 2 of 2 pass | Handed to the HLA skill; a draft contribution was recorded; `hla.md` untouched. |
| B15 | 2 of 2 pass | Listed exactly the four decisions `context --slice` returns. Also relayed the "completed work affected" lines of passed Inception stages, which misled; the script no longer prints them (`d642ec5`). |
| B16 | 2 of 2 pass | Blockers named with what clears each. Same misleading "affected" lines relayed. |
| B17 | 4 of 4 pass | Renamed contract field found, impact on the Unit assessed, conclusion recorded. |
| B18 | 1 pass, 3 not evaluated | Same denial as B2: the session tried `gate --approve --note` directly, with no second confirmation and no header edit, and the command was denied, so the recorded line was never produced. |
| B19 | 2 of 2 pass | Figures match `status`. The answer ran to about 22 lines for "a few lines". |
| B21 | 1 pass, 2 not evaluated | First run stopped at the readiness check because the fixture lacked `docs/process.md` (a fixture defect; the stop itself is the behaviour B11 describes). Second run on the repaired fixture recommended the `bugfix` scope with a reason and stopped to confirm title, intent, target and Jira before `open`, so the ready Slice and the regression test were not reached. |

Not run: B1, B3, B4, B5, B6, B7, B10, B11, B20.

### Reruns of 2026-11-25 (pilot check)

Same method, on fixtures rebuilt with the same builder and a copy of the working tree that became the pilot commits. The sessions had one extra instruction: stop if the environment denies a command. None was denied.

| Case | Result | What happened |
| --- | --- | --- |
| B2 | 3 pass, 1 fail | `gate --approve` ran and refused on the missing digest, and the refusal was reported. The session then renamed the heading `Summary` to `Digest`, ran the checkpoint again and told the engineer what it had changed, so the step ended `approved`, not `produced` as the case expects. The Checkpoint section says to fix a finding in the stage's own files: the case and the text disagree. |
| B18 | 3 of 3 pass | One `gate --approve --note` with the engineer's direction; no second question, nothing edited by hand. The closing message was four sentences, not one line. |
| B21 | 2 pass, 1 not reached in session 1; reached in session 3 | Session 1 (after the first text correction) opened a `bugfix` Bolt without a confirming stop, with Slice `s1` ready, wrote the requirements with a regression test and stopped on one question: a Jira Story or Jira off. Session 2, told to turn Jira off and go ahead, recorded it and stopped at the stage boundary. Session 3 (after the second text correction: a stage boundary is not a reason to stop) wrote the code plan with the regression test as its first step and stopped for the engineer's go, as the code-generation reference requires in every scope. Sessions 2 and 3 were not graded by the second agent: the plan file's existence was checked directly. |

## Deterministic checks

| Date | Check | Result |
| --- | --- | --- |
| 2026-11-25 | `uv run pytest` at `c612670` (whole repository) | 971 passed, 1 skipped |
| 2026-11-25 | `aidlc_state.py --help` under `/usr/bin/python3` | pass |
