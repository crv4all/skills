# Jira handoff

Read only when filing, after the Delivery Planning gate and before the first unit's Construction. Mapping: one Epic per Bolt, one Story per unit of work. A user story (`US-n`) never becomes a Jira issue. Reason: a unit is what a team builds and tracks; user stories are planning detail inside it.

If the Bolt has no Jira, run `aidlc_state.py jira --bolt <p> --off --reason "<why>"` and stop.

## Epic

Build the input for `crv-create-jira-epic` from the digests of `requirements.md` and `hla.md` (when it exists):
- outcome and problem: the intent and the requirements digest, in plain words;
- scope and out of scope: the units and what the requirements exclude;
- success criteria: the measurable outcomes of the requirements.

Ask the person for the project and team; never guess them. Record the key: `aidlc_state.py jira --bolt <p> --epic KEY`.

## Stories

One input candidate per unit, in the schema of `crv-create-jira-story`:

| Field | Value |
| --- | --- |
| `id` | the unit id from `state.json` |
| `summary` | the unit name |
| `parent` | the epic key |
| `goal` | for a technical unit: one sentence on what is true afterwards and why |
| `user_story` | instead of `goal`, when the unit serves one persona's stories |
| `acceptance_criteria` | the texts of the acceptance criteria of the stories mapped to the unit in `unit-of-work-story-map.md` |
| `blocked_by` | the ids of the units it depends on, from `unit-of-work-dependency.md` |
| `notes` | the target repository, the contracts it provides or consumes, and the Bolt id |
| `out_of_scope` | only when the unit states it |

Rules:
- Never set `story_points` or `priority`. People decide them.
- Write no planning ids (`FR-n`, `US-n`, `AC-n.m`, `D<n>`) in summary, goal, criteria or tasks. Jira readers do not know them. The Bolt id in `notes` is the only pointer back.
- Show the candidates to the person before filing; `crv-create-jira-story` reads each back.

## After filing

1. Record every key: `aidlc_state.py jira --bolt <p> --unit <u> --story KEY`. Construction of a unit is refused until its key is recorded.
2. Write the key next to the unit heading in `unit-of-work.md`.
