# Layer: knowledge

**Reference and organizational context.** A knowledge skill exists to correct
what a capable agent would otherwise assume. It carries facts about CRV — our
platforms, our domain, our constraints — that are not discoverable from the
repository the agent happens to be working in.

## A skill belongs here when

- Its value is in the *facts*, and a well-informed engineer already knowing
  those facts would need no further instruction.
- Getting it wrong produces confidently incorrect work rather than an error.
- It is referenced by other skills more often than it is invoked directly.

## A skill does not belong here when

- It prescribes a procedure with steps and a deliverable → `processes/`
- It prescribes a way of writing code → `patterns/`

## Expectations for this layer

- **State the fact, then the consequence.** "Animal identifiers are life-number
  based, not database-surrogate based" is only useful next to "so never join on
  the surrogate across systems".
- **Date and source volatile claims.** Anything that can change — a platform
  version, a team boundary, an active migration — carries the date it was last
  verified and a pointer to where it can be re-verified.
- **No secrets, no credentials, no customer or farmer data, no unpublished
  commercial terms.** This repository is public. Facts that cannot be public go
  in an internal repository and are referenced by URL, not copied here.
- Cattle-breeding and genetics domain vocabulary is exactly the kind of context
  that belongs in this layer; a reader outside CRV should still be able to read
  the file without learning anything confidential.

_No skills in this layer yet._
