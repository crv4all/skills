# Layer: patterns

**Reusable implementation recipes — how we build.** A pattern skill is applied
*inside* a larger task the agent is already doing. It does not own the task; it
shapes one part of it.

## A skill belongs here when

- The agent is already writing code or configuration, and there is a CRV-correct
  way to write this particular part.
- The output is a diff to a project, not a standalone deliverable.
- It composes: two or three patterns can apply to the same change without
  fighting each other.

## A skill does not belong here when

- It defines the whole unit of work, start to finish → `processes/`
- It is a fact rather than a construction → `knowledge/`
- The hard part is invoking a tool → `utilities/`

## Expectations for this layer

- **Show the shape, not a copy-paste blob.** A pattern that is one large code
  block gets pasted verbatim into places it does not fit. Give the structure,
  name the decision points, and show a minimal correct example.
- **State the rejected alternative.** A pattern without a "not this, because"
  is indistinguishable from a preference, and the agent will discard it under
  pressure from the surrounding code.
- **Be explicit about scope.** Say which stacks and which layers the pattern
  applies to, and say plainly when it does not apply.
- Patterns must not conflict with the conventions actually observed in a target
  repository without saying so. If a repo already does it another way, the
  skill should tell the agent to surface the divergence rather than silently
  rewrite.

_No skills in this layer yet._
