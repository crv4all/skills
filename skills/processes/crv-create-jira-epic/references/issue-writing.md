<!--
Adapted from https://github.com/blader/humanizer (MIT, Copyright (c) 2025 Siqi Chen)

The pattern catalogue under "Patterns that mark generated text" is adapted from
that project's list of AI writing patterns: the pattern names and the idea of
naming them mechanically are its contribution. Every example here was rewritten
for Jira issues, and the size caps, the summary rules and the placeholder rules
are ours. See THIRD_PARTY_NOTICES.md.
-->

# Writing the title and the description

A summary line is the most-read text in Jira. It appears in the backlog, on the
board, in the sprint report, in every notification, and in whatever chat channel
the team pastes it into. Almost all of those places truncate it. The description
is read once by the person who picks the issue up, and again by whoever argues
about scope later.

Both fail the same three ways. They are too long, so the part that carries the
meaning is cut off or skimmed past. They are padded, so a reader learns to skip
whole sections. Or they read as generated text, which tells the team that nobody
owned the ticket.

## Size caps

An issue is a working instruction, not a document. These are hard caps, checked
before the create call.

| Text | Cap | Reason |
| --- | --- | --- |
| Story summary | 80 characters, 12 words | Jira accepts 255. Boards, backlog rows, sprint reports and chat previews cut well before that, and the cut lands mid-phrase. |
| Story description | 200 words | Past that the reader skims, and a skimmed acceptance criterion is an ungroomed one. A story that genuinely needs more is usually two stories. |
| Context section | 3 sentences | It exists to say what the code and the epic do not. Anything longer is restating one of them. |
| Acceptance criteria | 5 bullets, one line each | Six criteria on one story is a decomposition that has not finished. |
| Epic description | 400 words | An epic is read to decide whether work belongs in it. That decision needs the outcome and the boundary, not a narrative. |
| Any single sentence | 25 words | One idea per sentence. Two ideas joined by a comma is two sentences. |

Going over a cap is a rewrite, not a warning. Cut, do not compress: dropping
the padding is what gets a description under 200 words, and reflowing the same
content into denser prose does not.

## The summary line

| Rule | Reason |
| --- | --- |
| At most 80 characters and 12 words | See the caps above. |
| Sentence case, no trailing full stop | Matches how Jira renders every other title. Title Case reads like a document heading. |
| A story starts with an imperative verb | "Reject expired tokens at the ingest endpoint". The verb states what changes, which is what a reader scanning a sprint wants. |
| An epic names the outcome as a noun phrase | "Token expiry enforced across ingest". An epic is a state to reach, not a task to do. |
| One subject only | If the title needs "and", or a colon carrying a second clause, file two issues. |
| Domain nouns, not abstractions | Use the words the team and the code already use. |
| No plan-local numbering | "Story 4", "phase 1 item 3" and "part 2 of 3" mean nothing in Jira. Issue keys are the only names a reader has. |
| No prefixes that repeat a field | "CHO:", "[Backend]", "Epic 3 -" duplicate the project, component, label and parent link. |
| No em dash, en dash, arrow, or bracketed aside | Punctuation a keyboard does not have easily is the clearest tell of generated text. |

## Never write a placeholder value

`TBD`, `TODO`, `N/A`, `To be determined` and `<fill this in>` are not answers.
They read as an oversight rather than a decision, and nobody comes back to
them.

Three legitimate moves when a value is unknown:

1. **Say the state in words.** "Not yet decided" and "None known" are real
   answers, and the templates use them by name. Say who decides, if anyone does.
2. **Leave the field unset.** An empty Jira field is honest and searchable. A
   field containing `TBD` is neither, and on an option or priority field it
   renders as a broken icon because `TBD` is not one of the allowed values.
3. **Stop and ask**, when the value is one the issue cannot be filed without.

**Never choose a Priority.** Priority is a scheduling decision the team makes
in grooming against everything else in the backlog, so a value the run picked is
either wrong or a guess that gets treated as agreed. Leave the field unset. A
priority the **user** names explicitly is a supplied value and does get sent,
validated against the allowed values first; the field-resolution reference has
the two exceptions. Either way, do not write a `Priority` line in the
description: it duplicates a real Jira field, and the two then disagree.

## Patterns that mark generated text

Named so they can be checked rather than felt. Each one is a rewrite, not a
preference.

### Padding

| Pattern | Instead |
| --- | --- |
| Inflated importance: "a pivotal step in modernising the platform" | State the change. "Moves token checks into the gateway." |
| Sales language: "a robust, seamless solution for ingest reliability" | Name the behaviour that changes. |
| Shallow `-ing` clauses: "returning a 400, improving the client experience and reducing support load" | Stop after the fact. The clause adds words, not meaning. |
| Formulaic challenges and outlook: a closing paragraph on risks and next steps that names neither | Delete it, or name a specific risk with an owner. |
| Generic positive ending: "This sets the team up for future scalability." | End on the last concrete fact. |
| Announcing the next point: "Let's look at what this involves." | Say what it involves. |
| A heading restated in its first sentence | Delete the sentence. The heading already said it. |
| Answering an objection nobody raised: "This is not about performance." | Say what it is about. |
| Rejecting a fake alternative: introducing an approach only to dismiss it | State what happens. A discarded option belongs in Technical notes with the reason, or nowhere. |

### False shape

| Pattern | Instead |
| --- | --- |
| "Not just X, but Y" | State Y. |
| Forced groups of three, where the third is filler | Two, or one. Match the number of real items. |
| False ranges: "from validation to observability" | List the items. A range needs endpoints on a scale. |
| Fake profundity: "at its core", "the real question is" | Ask the question. |
| Formulaic saying: "Reliability is a feature, not an afterthought." | Cut. It asserts nothing checkable. |
| Forced punchlines and dramatic fragments: "No retries. No fallback. Nothing." | One sentence saying what the code does. |
| Fake-candid opening: "Honestly? It depends." | State what it depends on. |

### Language

| Pattern | Instead |
| --- | --- |
| Overused words: additionally, moreover, furthermore, crucial, pivotal, testament, landscape, realm, delve, leverage, robust, seamless, holistic, comprehensive, streamline | The specific word, or nothing. |
| "serves as", "boasts", "features", "acts as" | "is" and "has". |
| Stacked qualifiers: "could potentially possibly affect" | "may affect", or state it plainly. |
| Filler: "in order to", "due to the fact that", "at this point in time" | "to", "because", "now". |
| Passive with no subject: "The results are preserved." | Name who or what does it. On an acceptance criterion this matters: an untraceable actor is an untestable criterion. |
| Synonym cycling: endpoint, then route, then handler, for one thing | One name, every time. Reusing the exact term is what makes an issue searchable. |
| Vague sources: "experts recommend", "best practice suggests" | Name the source, or drop the claim. |

### Formatting

| Pattern | Instead |
| --- | --- |
| Em dash, en dash, arrows | A comma, a colon, a full stop, or two sentences. |
| Bold scattered through prose | Plain text. Bold a term once, if at all. |
| Every bullet opening with a bold mini-heading and a colon | Plain bullets. |
| Title Case headings | Sentence case. |
| Emoji, decorative glyphs, curly quotes | None. Markdown lists and straight quotes. |
| Hyphenated pairs everywhere: "cross-functional end-to-end user-facing" | Hyphenate only where grammar needs it. |
| Chatbot leftovers: "I hope this helps", "Let me know if" | Delete. Nothing addressed to a chat reader belongs in a Jira field. |
| Knowledge disclaimers: "while specific details are not readily available" | Say what is not documented, or leave the section as "Not yet decided". |

### Words that name nothing

Delete or replace: handling, support for, enablement, improvements, robust,
seamless, leverage, holistic, comprehensive, streamline, optimise, various,
appropriate, proper, enhanced, capability, framework, solution.

Each can be swapped for the specific thing. "Improve error handling" does not
say what is wrong; "Return 400 instead of 500 on a malformed payload" does, and
it is shorter.

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

1. **No em dash or en dash, anywhere.**
2. **No arrows, no glyphs other than the markdown list, no emoji.**
3. **Drop the rhetorical shapes** catalogued above. They are padding, and a team
   learns to skip whole sections that start that way.
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

- summary at most 80 characters and 12 words
- description within its word cap, and no section over its own cap
- summary contains none of `—`, `–`, `->`, `=>`, `:` followed by a second clause
- summary does not start with the project key, a component in brackets, or a
  number
- summary starts with a verb (story) or a noun phrase naming a state (epic)
- neither summary nor description contains `#` followed by a digit as a
  reference to another candidate
- description contains no em dash or en dash
- neither summary nor description contains `TBD`, `TODO`, `N/A`, or a `Priority`
  line
- no Priority field appears in the create payload

When candidate text is prepared in a file first, three of those are one command
each:

```bash
grep -n '[—–]' candidates.md
grep -nEi '\b(TBD|TODO|N/A)\b' candidates.md
awk 'BEGIN{RS="";} {print NF, FILENAME}' candidates.md
```

Any hit on the first two is a rewrite. Fix it before the create call, because
editing 30 issues afterwards costs 30 calls and leaves an edit history that
suggests the batch was filed carelessly.
