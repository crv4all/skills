# The round-based interview

## The rule

**Facts are your job. Decisions are the user's.**

Never ask what the filesystem, git history, the repository's own documentation,
or the Agent Skills specification can answer. Look it up. Every question you
ask should be one where a reasonable person could answer either way, and where
the answer changes what you build.

Questions that are never acceptable, because the answer is available:

- "What layers does this repository use?" — `skills/README.md`
- "What frontmatter fields are allowed?" — the specification, and the schema
- "Does a skill with this name already exist?" — list the directory
- "What is the budget?" — `standards/configs/budgets.json`
- "Who owns the neighbouring skill?" — read its `metadata.owner`

Asking these signals that you have not looked, and it teaches the user that
answering you is cheaper than expecting you to check.

## Why rounds

Skill decisions are dependent. Scope depends on purpose; reference structure
depends on scope; triggers depend on what the near neighbours turned out to be.
Asking everything at once produces answers that have to be revised, and worse,
it asks questions that are not yet real — the user has to imagine a context
that does not exist yet in order to answer.

So: work the **frontier of settled decisions.** In each round,

1. Research the facts this round needs.
2. Identify the decisions now unblocked — inputs settled, answers consequential.
3. Ask those, batched, in one turn, each with a recommendation.
4. Record what was settled, and move the frontier.

Stop when the frontier is empty. Do not manufacture rounds to look thorough.

Always give a recommendation with each question. "Which layer?" makes the user
do your work. "I'd put this in `patterns` because the output is a diff to an
existing project rather than a standalone deliverable — does that match how you
think about it?" gives them something to disagree with, which is much easier
than starting from nothing.

## Round 1 — Purpose and near neighbours

*Blocked by nothing. Settles what the skill is for.*

- What does an agent get wrong today that this would fix? Ask for the actual
  failure, not the abstraction.
- Who hits that failure, and how often?
- What is the closest existing skill, and why is this not that?

**Do the research first:** list existing skills and read their descriptions.
Arriving with "the closest existing skill is X; here is why I think yours is
different" is worth more than any question you could ask.

## Round 2 — Layer

*Blocked by Round 1. Settles the shape of the output.*

- What does the skill *produce*: a command result, an answer, a diff, or a
  reviewable deliverable?
- Is it applied inside someone else's task, or does it own the task?

Recommend a layer with your reasoning. If two layers fit, say so and propose
the split — that is a decision the user must make, and it is the most
consequential one in the whole interview.

## Round 3 — Scope

*Blocked by Round 2. Settles the boundary.*

- What is explicitly in?
- What is explicitly out, and where should it go instead?
- Which cases must it handle, and which may it decline?
- What is the smallest version that is still worth having?

The last question is the useful one. Authors describe the complete version;
what ships should be the smallest thing that beats the status quo.

## Round 4 — Triggers

*Blocked by Round 3. Settles the description.*

- In the user's own words, what would someone type when they need this?
- What would someone type that looks similar but should *not* fire it?
- Are there file names, tool names, or error strings that mean "this applies"?

Push for the user's actual vocabulary. A description written in the author's
words and tested with the author's words passes an eval it should have failed;
real users say "get me up to speed", not "produce codebase context".

## Round 5 — Scripts

*Blocked by Round 3. Settles what becomes code.*

- Which parts have exactly one correct answer? Those belong in a script.
- Does it need to touch anything outside the repository? (It should not.)
- Is anything destructive? Then it needs `--dry-run` and `--confirm`.

Anything deterministic that stays in prose gets re-derived, differently, every
run. See [script-contract.md](script-contract.md).

## Round 6 — Governance

*Blocked by Round 2. Settles maintenance.*

- Which team owns it? A person's name is a stopgap; skills outlive team
  assignments.
- How often do the underlying facts change? That sets `review-cadence` — pick
  from the facts, not from how important the skill feels.
- Start at `draft`. Promotion has its own bar; see [promotion.md](promotion.md).

## Recognizing the end

The frontier is empty when every remaining unknown is a fact you can look up or
a detail that does not change the design. At that point, stop asking and start
writing. An interview that keeps going past this point is not thoroughness; it
is deferring the part where you commit to something.
