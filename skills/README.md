# Skills

Every skill in this repository lives at exactly one path:

```text
skills/<layer>/<skill-name>/SKILL.md
```

`<skill-name>` is the value of the `name:` field in the frontmatter, is prefixed
`crv-`, and matches the directory name exactly. `<layer>` is one of four
capability layers, and matches `metadata.layer` in the frontmatter. Both
constraints are enforced by `standards/scripts/validate_frontmatter.py`.

## The four layers

| Layer | Answers | Typical shape |
| --- | --- | --- |
| [`utilities/`](utilities/README.md) | "Run this thing correctly." | Cross-cutting tooling, mostly a thin wrapper around scripts |
| [`knowledge/`](knowledge/README.md) | "What is true at CRV?" | Reference material and organizational context; little or no procedure |
| [`patterns/`](patterns/README.md) | "How do we build this?" | A reusable implementation recipe applied inside a larger task |
| [`processes/`](processes/README.md) | "What do we deliver, end to end?" | A multi-phase workflow with a stated output contract |

## Choosing a layer

Ask what the skill's *output* is:

- A command result or a transformed file → `utilities`
- An answer, a decision, or a correction to the agent's assumptions → `knowledge`
- Code or configuration written the CRV way → `patterns`
- A named deliverable produced through several phases → `processes`

If more than one answer fits, the skill is doing more than one job. **Split it.**
A skill that both explains a domain and drives a workflow will trigger for the
wrong requests and load the wrong context for both. The usual split is a
`knowledge` skill the `processes` skill references.

## Why layers instead of one flat directory

The layer is a routing signal for humans, not for the agent — agents select
skills from `description`, never from the path. Layers exist so that reviewers
can tell at a glance whether a change alters organizational fact
(`knowledge`), house style (`patterns`), or a shipped deliverable
(`processes`), and can apply the right level of scrutiny.

There is deliberately no plugin-bundle level above the layers in v1. Add one
only when a second team needs its own ownership boundary; until then it is
structure without a reader. See [docs/architecture.md](../docs/architecture.md).
