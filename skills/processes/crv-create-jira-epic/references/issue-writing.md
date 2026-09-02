# Writing the title and the description

A summary line is the most-read text in Jira. It appears in the backlog, on the
board, in the sprint report, in every notification, and in whatever chat channel
the team pastes it into. Almost all of those places truncate it. The description
is read once by the person who picks the issue up, and again by whoever argues
about scope later.

Both fail the same two ways. They are too long, so the part that carries the
meaning is cut off or skimmed past. Or they read as generated text, which tells
the team that nobody owned the ticket.

## The summary line

| Rule | Reason |
| --- | --- |
| At most 80 characters | Jira accepts 255. Boards, backlog rows, sprint reports and chat previews cut well before that, and the cut lands mid-phrase. |
| At most 12 words | A title that needs more is describing two pieces of work. |
| Sentence case, no trailing full stop | Matches how Jira renders every other title. Title Case reads like a document heading. |
| A story starts with an imperative verb | "Reject expired tokens at the ingest endpoint". The verb states what changes, which is what a reader scanning a sprint wants. |
| An epic names the outcome as a noun phrase | "Token expiry enforced across ingest". An epic is a state to reach, not a task to do. |
| One subject only | If the title needs "and", or a colon carrying a second clause, file two issues. |
| Domain nouns, not abstractions | Use the words the team and the code already use. |
| No plan-local numbering | "Story 4", "phase 1 item 3" and "part 2 of 3" mean nothing in Jira. Issue keys are the only names a reader has. |
| No prefixes that repeat a field | "CHO:", "[Backend]", "Epic 3 -" duplicate the project, component, label and parent link. |
| No em dash, en dash, arrow, or bracketed aside | Punctuation a keyboard does not have easily is the clearest tell of generated text. |

### Words that name nothing

Delete or replace: handling, support for, enablement, improvements, robust,
seamless, leverage, holistic, comprehensive, streamline, optimise, various,
appropriate, proper, enhanced, capability, framework, solution.

Each of them can be swapped for the specific thing. "Improve error handling"
does not say what is wrong; "Return 400 instead of 500 on a malformed payload"
does, and it is shorter.

### Rewrites

| Weak | Better |
| --- | --- |
| Implement comprehensive validation and error handling improvements for the ingest API endpoint payload processing | Reject malformed ingest payloads with a 400 |
| CHO: Story 4 - Token expiry enforcement (backend) | Reject expired tokens at the ingest endpoint |
| Enhance the data pipeline to support robust reconciliation across sources | Reconcile animal counts between Databricks and the source system |
| Epic: Phase 1 platform enablement work stream | Ingest runs on the shared platform |
| Refactor and optimise the legacy service layer as needed | Split OrderService into pricing and persistence |

## The description

Write the thing the implementer cannot get from the code or from the epic. Then
stop. A description that restates its own title, or repeats the epic, adds
reading time and takes on a second copy to keep current.

House rules, in order of how often they are broken:

1. **No em dash or en dash, anywhere.** A comma, a colon, a full stop, or two
   sentences do the same work and read as though a person wrote them.
2. **No arrows, no bullet glyphs other than the markdown list, no emoji.**
3. **Drop the rhetorical shapes.** "Not just X, but Y", a closing sentence that
   summarises the paragraph above it, three examples where one is enough, and a
   final line about why this matters. These are padding, and a team learns to
   skip whole sections that start that way.
4. **Short sentences, present tense, active voice.** One idea each.
5. **Name real things.** The service, the table, the endpoint, the file, the
   team. A description with no proper nouns in it is usually describing nothing.
6. **No invented facts.** An acceptance criterion nobody agreed to is worse than
   an open question, because it gets cited as agreed.

## Vocabulary

Take the words from the epic, the schema, the UI labels and the code. If the
team says lactation, do not write milk production cycle. If the service is
called `order-api`, do not write the ordering subsystem. Reusing the exact term
is what makes a ticket searchable, and what tells the reader the writer had
actually looked.

Write for the person who picks the issue up next sprint with no memory of this
conversation. They need the current behaviour, the wanted behaviour, and how
anyone will know it worked.

## Checking a batch before it is filed

Mechanical rules, so they can be checked rather than felt. For each candidate:

- summary length at most 80 characters, word count at most 12
- summary contains none of `—`, `–`, `->`, `=>`, `:` followed by a second clause
- summary does not start with the project key, a component in brackets, or a
  number
- summary starts with a verb (story) or a noun phrase naming a state (epic)
- neither summary nor description contains `#` followed by a digit as a
  reference to another candidate
- description contains no em dash or en dash

When candidate text is prepared in a file first, the punctuation rules are one
command:

```bash
grep -n '[—–]' candidates.md
```

Any hit is a rewrite, not a warning. Fix it before the create call, because
editing 30 issues afterwards costs 30 calls and leaves an edit history that
suggests the batch was filed carelessly.
