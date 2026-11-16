# User stories

Turns requirements into stories that a person can accept: who needs what, and how to tell it is done. Every story points back to a requirement and forward to a unit.

## Runs when / skipped when

Runs for user-facing features, several personas, complex business logic or work spanning teams. Skipped for refactors, isolated bug fixes, infrastructure-only work and tooling, and always in the `express` and `bugfix` scopes. When skipped, still write the assessment with its reason. One gate, at the end.

## Reads

As listed by `aidlc_state.py inputs --stage user-stories`:

- `requirements.md`: the `FR-n` and `NFR-n` every story must cover;
- `codekb/<repo>/` business overview and component inventory: who uses the system today and what already exists;
- `knowledge/_digest.md`, only for personas and journeys already described.

## Question categories

Cover all; scale to depth.

- **Personas and goals**: who uses this, and what are they trying to achieve? "Which roles interact with this, and which is the primary one?"
- **Story format**: size and shape. "Should a story fit one sprint of one person, or cover a whole journey?"
- **Priority**: must / should / could / won't for the first release. "Which stories can slip without breaking the release goal?"
- **Breakdown**: by feature, persona, workflow or domain. "Do you want stories per persona journey or per capability?"
- **Granularity**: how fine acceptance criteria go. "One criterion per rule, or per scenario?"
- **Acceptance criteria**: the measurable proof. "What would you check to accept this?"
- **User journeys**: end-to-end flows and their failure paths. "Where does the person go when this step fails?"
- **Business context and technical constraints**: deadlines, regulation, accessibility, device or browser limits. "Any group of users for whom the standard flow does not work?"

## Settles

The personas; the stories with priority and dependencies; the acceptance criteria of each; which requirements each story covers.

## Steps

1. Assess whether stories are needed and write the decision with its factors.
2. Write the questions and the story plan in one file; the plan states the intended persona count, story count and breakdown.
3. After the answers, state the plan in one line and proceed; there is no separate plan approval.
4. Draft personas, then stories. Each `FR-n` is covered by at least one story; an `NFR-n` appears as an acceptance criterion or a story of its own.
5. Self-check each story for value to the persona, for buildability by one team, and for testability of every criterion; rewrite what fails.

## Writes

In `docs/inception/user-stories/`:

- `user-stories-assessment.md`: Decision, Rationale, Factors.
- `user-stories-questions.md` (and clarifications).
- `personas.md`: one `## <Persona>` each with goals, context and pain points.
- `stories.md`, starting with `## Digest`. Each story is `### US-n <title>` with: "As a ... I want ... so that ...", Covers (`FR-n`, `NFR-n`), Priority, Depends on (`US-n`), and a table `| AC-n.m | Given / When / Then |` (declare each `AC-n.m` in the first cell). Add a short note per INVEST property only where it is at risk.

## Good

Every `FR-n` is referenced by a story, every story has at least two criteria including one failure path, and each criterion can be turned into a test without asking anyone. Personas are specific enough to disagree with.

## Common failure

Stories that restate a requirement as "As a user I want the system to..." with criteria no one can fail.
