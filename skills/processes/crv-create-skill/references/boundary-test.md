# The boundary test

Most skill ideas should not become skills. This is the filter, and applying it
honestly is the highest-leverage thing this process does — a skill that should
not exist costs context on every session forever, and nobody ever deletes it.

## The four questions

### 1. Would a capable agent get this wrong without it?

The bar is a competent engineer with web access, not a beginner. If they would
already do it correctly, the skill adds context cost and buys nothing.

**Passes:** CRV animal identifiers have several forms with different scopes,
and joining on the wrong one is a silent correctness bug. Nobody outside CRV
knows this, and nothing in a typical repository says it.

**Fails:** "Write tests for new code." Every agent already believes this. The
skill would be a reminder, and reminders in a skill are just tax.

**The honest version of the question:** can you name a specific wrong thing a
good agent does today? If you cannot produce the failure, you cannot produce
the fix.

### 2. Is there a recognizable trigger?

You must be able to name the situations where this applies *and* the near
neighbours where it does not. "Sometimes useful" is a description of context,
not of a skill.

**Passes:** "When a repository contains `dbt_project.yml`" is checkable. "When
the user asks to onboard to a codebase" is a phrasing people actually use.

**Fails:** "When writing good code." Fires always, therefore fires never
usefully.

**Test it before you build it.** Write the description first. Show it alone to
someone who has not seen the skill, describe three tasks — one that should
trigger it, one that should not, one borderline — and see whether they route
correctly. If they cannot, an agent with fifty other descriptions in context
certainly cannot.

### 3. Is it stable enough to maintain?

A skill asserts things with confidence. A stale skill asserts *wrong* things
with the same confidence, and confidently wrong is worse than absent, because
the agent will defend it against the evidence in front of it.

Ask: how often do these facts change, and who re-verifies them? If the answer
to the second is "nobody", the honest outcome is not a skill.

**Passes:** the four capability layers in this repository. Deliberately slow to
change, and changing them is a decision someone makes on purpose.

**Fails:** "current versions of our services". Changes weekly, nobody owns it,
and the skill is wrong the first week nobody updates it.

Volatile facts belong where they are already maintained — a dashboard, a
service catalog — referenced by URL.

### 4. Is it one job?

If the skill spans two layers, it is two skills. It will trigger for the wrong
requests, load the wrong context for both jobs, and do each of them worse.

**Fails, and should be split:** "Explain our data platform and generate a new
pipeline." That is a `knowledge` skill and a `patterns` skill. Split them, and
have the pattern reference the knowledge.

Splitting is the most common correct outcome of the boundary test, and the one
authors resist most, because two small skills feel like less work than one big
one — right up until the big one fires on the wrong request.

## What to recommend instead

When the test fails, recommend the artifact that fits. Do not soften the
verdict; an unnecessary skill is a real cost, paid by everyone, forever.

| The idea is really… | Recommend |
| --- | --- |
| A rule about one repository | A paragraph in that repository's `AGENTS.md` |
| A mechanically checkable rule | A lint rule or a CI check — it runs every time and cannot be argued with |
| A command someone forgets the flags for | A script with a good `--help`, or a Makefile target |
| A fact that changes weekly | A link to wherever it is already maintained |
| A one-off for today's task | Say it in the prompt |
| Two jobs | Two skills |
| General good practice | Nothing. The agent already knows. |

## Borderline cases

**"It would be nice to have."** No. That is the description of something that
will be loaded ten thousand times and used twice.

**"Someone asked for it."** Ask what went wrong that prompted the request.
Usually there is a real failure underneath, and it is narrower than the skill
they asked for.

**"We already wrote most of it."** Sunk cost. The question is whether it earns
its context from here on.

**"It's only a few lines."** Every skill's `name` and `description` are loaded
at startup for every session. A few lines of body still costs a slot in the
selection problem, and selection gets harder with every skill added.

**"It duplicates part of an existing skill."** Then extend the existing one, or
split the shared part into a `knowledge` skill both reference. Two skills that
overlap will both fire, or neither will.
