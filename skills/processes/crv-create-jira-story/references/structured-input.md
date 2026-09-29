# Rendering structured input

A caller may supply stories against
[../assets/story_input.schema.json](../assets/story_input.schema.json) rather
than in prose. The schema says what each field holds. This says where it goes,
because a batch whose Test plan is a nested list on one story and a paragraph on
the next reads as though nobody owned it.

Render in template order. Every schema property is in exactly one row below.

| Field | Where it goes | How |
| --- | --- | --- |
| `user_story` | The opening lines, with no heading | Three lines: `As a <role>`, `I want <capability>`, `So that <benefit>`. |
| `goal` | The opening line, with no heading, in place of the user story | The sentence as a paragraph. |
| `acceptance_criteria` | `## Acceptance criteria` | One `- [ ]` item each. A multi-line criterion keeps its line breaks, indented under its checkbox. |
| `test_plan` | `## Test plan` | One bullet per item, `- <Level>: <title>`, or `- <title>` with no level. Steps as a numbered list nested under their item, because steps are ordered. |
| `dependencies` | `## Dependencies` | One bullet each, `[[dep:<n>]]` kept verbatim for pass two. |
| `blocked_by`, `blocks` | `## Dependencies`, and native links | Any edge no `dependencies` item already names gets a bullet, `Blocked by <ref>` or `Blocks <ref>`. Every edge also becomes a native link in pass two. |
| `context` | `## Context` | The text as a paragraph. |
| `out_of_scope` | `## Out of scope` | One bullet each. |
| `notes` | `## Technical notes` | One bullet each. Code and payloads keep their fences. |
| `description_markdown` | The whole description | Replaces rendering, not checking. Every row above is ignored when it is present. |
| `summary` | The summary field | Never repeated in the description. |
| `parent` | Epic membership | Resolved per [field-resolution.md](field-resolution.md#epic-membership-parent-or-epic-link). |
| `story_points` | The story-point field | Never in the description. |
| `estimate_source` | The report, and a comment when `proposed-and-approved` | Never in the description. |
| `priority` | The Priority field | Only when present. Never in the description. |
| `labels` | The Labels field | Never in the description. |
| `additional_fields` | The fields they name | Resolved by name. Never in the description. |
| `project_key`, `issue_type` | Where the story is filed | Never in the description. |
| `id` | Nowhere in Jira | Plan-local, for dependency edges only. |

## Missing and empty values

- **A required section with no input** (neither `user_story` nor `goal`, no
  `acceptance_criteria`, no `test_plan`) is asked about in the batch question,
  never invented. A story filed with an invented test plan cites an agreement
  nobody made.
- **Dependencies with nothing in it** renders as `None`. The heading is required,
  and an empty one reads as unasked.
- **An optional field absent or empty** drops its heading entirely.
