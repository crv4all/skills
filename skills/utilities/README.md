# Layer: utilities

**Cross-cutting tooling.** A utility skill teaches the agent to run something
correctly — a script, a CLI, a repeatable transformation — in a way that does
not depend on which project the agent is sitting in.

## A skill belongs here when

- Its value is in the *execution*, not the judgement. The hard part is the
  flags, the exit codes, and the failure modes.
- It applies to any repository, any team, any language.
- Most of the SKILL.md body is "when to reach for this, how to invoke it, how
  to read the output, what to do when it fails".

## A skill does not belong here when

- The agent has to decide *what* to build → `patterns/`
- The agent has to produce a multi-file deliverable → `processes/`
- The content is CRV fact rather than tooling → `knowledge/`

## Expectations for this layer

- Bundled scripts follow the script conventions in
  [docs/authoring-skills.md](../../docs/authoring-skills.md): stdlib-only, PEP
  723 header, `requires-python = ">=3.9"`, JSON on stdout, diagnostics on
  stderr, never interactive, `--help` with exit codes, `--dry-run` plus
  `--confirm` for anything destructive.
- The SKILL.md should read as an operator's guide, not a tutorial. Prefer a
  short body plus `references/` over a long body.

_No skills in this layer yet._
