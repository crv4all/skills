# The checkpoint: one hand-back before anything is created

Three problems share one fix.

- **A subagent cannot wait for an answer.** It stops, and whatever it had built
  is gone unless it handed that back.
- **Questions spread across steps become several round trips**, or guesses
  where the agent decided not to bother the user again.
- **The user otherwise first sees the stories in Jira**, where each correction
  is an edit call and an edit history.

So the run checks in exactly once: after the epic is read, the candidates are
built and rewritten, duplicates are searched, the batch is validated and the
fields are resolved, and before the first create call.

Skip it only when the user said to file without review ("just file them") and no
question below applies. A question that applies is never skipped, because each
one is a value the run may not choose.

## What the hand-back contains

A draft table, one row per candidate, then the questions that apply, numbered,
then one line saying how to answer. Add an Estimate column only when some
candidate has points: a column of blanks reads as something missing.

```text
Ready to file 3 stories under BAPP-56. Nothing has been created yet.

| # | Summary | Opens with | Criteria | Tasks | Depends on | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Add freshness checks on refined breeding tables | User story | 4 | 3 | | new |
| 2 | Alert the Breeding team on incomplete animal data | User story | 3 | | 1 | new |
| 3 | Split TripleAQueryService into read and assemble steps | Goal | 5 | 2 | | new, resembles BAPP-61 |

1. Epic: BAPP-56, "Breeding-app technical optimizations", status Doing, which
   you mentioned earlier. File all three under it?
2. Assigned Team(s): Herman, Minotaurus, MooToo, ... No recorded default.
   One or more, or none.
3. Priority: the project default is TBD. Name one, or leave the default.
4. Sprint: the backlog, unless you name one.

Answer by number, edit any row, or reply "go" to take each question's default.
```

Ask only the questions that apply, and give each one's default in its wording:

| Question | Ask when | No answer means |
| --- | --- | --- |
| Epic | The epic came from the conversation rather than from this request, or its status is done | **Stop.** Stories are never filed under an epic nobody confirmed. |
| Team | The project has a team field | The recorded default, reported as a default, or unset if there is none |
| Priority | The field is on the screen and the user named none | The project default, or unset where there is none |
| Sprint | The project has a Sprint field | Unset, so the stories land in the backlog |
| Components, Fix versions | The field has allowed values in create-metadata | Unset |
| Proposed estimates | **Only when the user asked for them.** Never offered unprompted: story points are never required | Filed without points |
| Split | A candidate has more than about seven acceptance criteria | Filed as one story, every criterion kept |
| Cycle | The dependency graph has a cycle | Stories filed; the links in the cycle are not created |
| Missing section | A candidate has no user story or goal, no criteria, or no test plan | "Not yet decided" in that section, and the report names it |
| Real-key dependency | A dependency names a key that did not resolve | That dependency is left out of the links and named in the report |

Near-duplicates are shown in the Outcome column, not asked about: they are
created and named as resembling the existing key, per Step 3.

## Where the epic comes from

The request names it, or the conversation does. Before asking cold, look for an
epic key or browse URL the user mentioned, or an epic filed earlier in the same
session by `crv-create-jira-epic`. Read it, search and validate against it, and
propose it in question 1 with its summary and status. A mentioned epic is a
guess until the user confirms it, which is why its "no answer" is a stop.

If none can be found, question 1 asks for the key instead, and nothing is
created until there is one.

## Answers

- **"go", or a question left unanswered:** that question's default, from the
  table above.
- **A partial answer:** the answered questions apply, the rest take their
  defaults. Do not ask again.
- **An edit to a row** (a title, a criterion, a story dropped or added): apply it
  and re-run the Step 4 checks on that candidate. Ask again only if the edit
  raises a question that was not there before.
- **A different epic:** repeat Steps 1 and 3 against it before creating.
- **An answer Jira would not keep**, such as a team name not among the allowed
  values: ask that one again, alone, listing the allowed values. It is the only
  second round, because sending it would be accepted and silently dropped.

## Resuming after the hand-back

The subagent's result **is** the checkpoint message. The main session shows it
to the user as it stands and passes the answers back. It does not answer on the
user's behalf, including by taking "go" for granted.

If the harness can continue the same subagent, continue it with the answers.
Otherwise start a new one with the checkpoint message and the answers: it
re-reads create-metadata, which is one call, and rebuilds nothing else.

Either way, **re-run the Step 3 duplicate search immediately before the first
create.** Time has passed, and someone may have filed one of these meanwhile.
