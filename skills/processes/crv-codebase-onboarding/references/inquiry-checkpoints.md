# Inquiry checkpoints

The questions each phase must be able to answer before the next one starts. If
a question cannot be answered, that is a result — record it and move on. Do not
stall, and do not guess.

## Phase 0 — Detect

- [ ] Which mode, and what is the evidence for it?
- [ ] Does `docs/codebase/` exist? What SHA and date is it stamped with?
- [ ] Is that SHA an ancestor of HEAD?
- [ ] What agent context already exists — `AGENTS.md` (root and nested),
      `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/`?
- [ ] Are there ADRs?
- [ ] Is the working tree dirty? Uncommitted work makes the stamp misleading;
      say so.

**Never ask the user which mode to use.** The one question worth asking at this
point is scope, and only when the repository is large and the request was
vague.

## Phase 1 — Evidence

- [ ] What did `scan.py` find, and what is in its `notes` array?
- [ ] Which build systems are declared, and where?
- [ ] Is this one project or several? Where are the module boundaries?
- [ ] What are the entry points?
- [ ] What runs in CI, and does CI build something this repository also deploys?
- [ ] Which environment variables are required? Which are secret-shaped?
- [ ] Which files are largest by line count, and what do they do?
- [ ] What did the scan explicitly fail to classify?

Read the `notes` array in full. It is where the parts of a codebase that do not
fit a pattern end up, and those are usually the parts worth knowing.

## Phase 2 — Stated intent

- [ ] What does the README claim this project is for?
- [ ] Which of those claims are confirmed by code, at which paths?
- [ ] Which are contradicted, at which paths?
- [ ] Which cannot be checked either way?
- [ ] Do the ADRs describe decisions the code still honours?
- [ ] Does `CONTRIBUTING.md` describe a workflow that matches CI?
- [ ] Does existing agent context (`AGENTS.md`, Cursor rules) contain
      instructions the code contradicts?

Every divergence found here goes in `CONCERNS.md`. This is the highest-value
output of the whole process: anyone can restate a README, and nobody else is
checking whether it is still true.

## Phase 3 — Architecture

- [ ] What are the deployable or runnable units?
- [ ] What is the boundary of each, and what crosses it?
- [ ] Where does state live?
- [ ] What is the one flow this system exists to serve?
- [ ] Can that flow be traced hop by hop, with a real path at every hop?
- [ ] What is the failure behaviour at each boundary — retry, queue, drop, fail?
- [ ] Is anything synchronous that the README implies is asynchronous, or the
      reverse?

If the end-to-end flow cannot be traced completely, say where the trace broke
and why. A trace with an invented hop is worse than a trace that stops.

## Phase 4 — Domain and conventions

- [ ] Which terms carry business meaning a newcomer would get wrong?
- [ ] Which code symbol implements each term?
- [ ] Do different parts of the code use different words for the same thing?
      That is a finding, not a cleanup task.
- [ ] Which conventions are configured (linter, formatter, compiler)?
- [ ] Which are observed only, and with what count and what exceptions?
- [ ] Which are required by CRV standards but absent here?
- [ ] Where does the code disagree with its own configured rules?

Never promote an observed pattern to a rule. "23 of 27 controllers return
`ResponseEntity`; the 4 exceptions are in `LegacyController`" is honest and
actionable. "Controllers return `ResponseEntity`" is a policy you invented, and
it will be cited as one.

## Before reporting

- [ ] Every required file written, every skipped file explained.
- [ ] Every path verified to exist.
- [ ] Every claim carries evidence.
- [ ] No secret values.
- [ ] No template placeholder text left.
- [ ] Every `[ASK USER]` collected into the report.
- [ ] Every validation check either run or explicitly named as skipped.

## When to actually ask the user

Ask only for things the repository cannot answer. Batch the questions, and put
them at the end; do not interrupt the process for them.

Worth asking:

- Where the deployment definition lives, when it is clearly elsewhere.
- Which of two contradictory documents is current.
- Whether a subsystem is deprecated, when the code is ambiguous and the git
  history is inconclusive.
- Who owns a component, when there is no `CODEOWNERS`.

Not worth asking, because the repository answers them:

- Which mode to run in.
- What language or framework this is.
- Whether to include a conditional file.
- Where to write the output.
