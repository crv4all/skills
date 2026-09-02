# Fixing issues that were created wrongly

"Stop and report, never improvise" covers a run that failed. It does not cover
the more expensive case: the run succeeded, the issues exist, and the values in
them are wrong. Twenty-nine stories with no epic link look exactly like
twenty-nine stories with one, until someone opens the epic.

This is the procedure for that. It is deliberately slower than the wrong instinct,
which is to start patching immediately from memory of what was intended.

## 1. Establish what is actually there

Do not patch from the transcript. The transcript records what was sent, and the
whole problem is that what was sent is not what was stored.

Read the batch back, in one query, and build a table of stored values: key,
summary, epic membership, story points, and every field under discussion. Count
the rows. Sum the points from the rows.

Every later step compares against that table, not against the plan.

## 2. Classify each defect

| Class | Examples | Fix |
| --- | --- | --- |
| Field value wrong or absent | Epic link, story points, team, labels | Patch in place |
| Field set that should never have been set | A Priority chosen by a previous run, rendering as a broken icon | Clear it, with the same one-table approval |
| Description text wrong | Unresolved placeholder, plan-local numbering, missing section, a `TBD` or a `Priority:` line | Patch in place |
| Description too long | Over the word cap, padded with the patterns the writing reference names | Patch in place, and rewrite rather than trim |
| Relationship missing | No native `Blocks` link behind a prose dependency | Add the link |
| Relationship backwards | Blocker and blocked swapped | Delete that link, create the opposite |
| Structurally wrong | Wrong project, wrong issue type, duplicate of an existing issue | See below |

## 3. Patch in place, by default

Patching keeps the key. That matters more than it looks: the key is already in
chat messages, commit trailers, branch names, sprint reports and somebody's
notes. Refiling invalidates all of it, silently.

Order the patches so that the most useful correction lands first. Epic membership
before anything else, because until it is set the batch is invisible on the
board and nobody can review the rest of the fix.

Protocol for a batch patch:

1. Propose the whole thing as one table: key, field, stored value, intended
   value. One approval for the table, not one question per issue.
2. Apply it. One edit call per issue, with every field for that issue in it, not
   one call per field.
3. Read back again and report stored values. A patch run reports the same way a
   create run does, and the same rule applies: quote what came back.
4. If a patch call fails partway, report which keys are corrected and which are
   not. A half-corrected batch that is described accurately is recoverable.

Patching is idempotent by nature: setting a field to the value it already holds
is harmless, so a re-run after a partial failure is safe.

## 4. Delete and refile only when structure is wrong

Refiling is right in three cases, and only these:

- **Wrong project.** Prefer a move if the tenant allows it, because a move keeps
  the history. Refile if it does not.
- **Duplicates from a blind retry.** Two issues where one was meant. Keep the one
  the team has touched.
- **Wrong issue type, in a project that will not let the type change.** Rare, and
  worth checking before assuming it.

Never delete an issue that has any sign of a human on it: a comment, a worklog,
an attachment, a transition past the initial status, a watcher who is not you, or
a reference from another issue or a pull request. In that case, keep it and
correct what can be corrected, even if the result is untidy.

**This skill creates. It does not delete.** Deleting Jira issues is destructive
and usually irreversible for the person asking. Report the keys and the reason,
recommend the action, and let the user delete or explicitly authorise it. Do not
fold a deletion into a remediation the user approved as a patch.

## 5. Report the correction as a correction

Say plainly: the batch was created with N issues wrong in a specific way, here is
what was patched, here is the read-back proving it, here is anything still
outstanding. Do not quietly re-report the original run as successful. The record
of what went wrong is what stops it happening the same way twice, and it is the
only part of this that cannot be recovered later.
