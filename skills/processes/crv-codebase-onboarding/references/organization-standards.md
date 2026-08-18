# CRV organizational context

Facts about CRV that change how a repository should be read. Everything here is
public-safe by construction: this repository is public, and anything that could
not be published belongs in an internal repository and is referenced by URL,
never copied.

> Last verified: 2026-08-18. Review cadence: quarterly. If a fact here is
> wrong, fix it in a PR — a stale organizational fact is worse than a missing
> one, because it is asserted with the same confidence as a true one.

## What CRV is

CRV (crv4all.com) is a cattle breeding and genetics company. The software
estate spans herd and animal data, genetic evaluation, breeding programme
management, and the data platform underneath all of it.

The consequence for onboarding: **the domain vocabulary is load-bearing and
mostly not guessable.** Words that look like ordinary English are technical
terms with precise meanings, and an agent that reads them as ordinary English
produces confidently wrong work. This is the main reason `DOMAIN.md` exists.

## Where CRV code lives

Almost every CRV repository is on Azure DevOps at `dev.azure.com/crv4all`,
under two projects: `DevOps` and `Cloudforce Team Data`.

Consequences when onboarding a CRV repository:

- **Azure Pipelines is the default CI.** Look for `azure-pipelines.yml` before
  `.github/workflows/`.
- **Pipeline templates and variable groups often live outside the repository**
  — in another repository, or in Azure DevOps configuration you cannot read
  from a checkout. Report the reference and the gap. Do not describe a pipeline
  as if you had read all of it.
- **Cross-repository references are normal.** A service whose deployment
  definition is elsewhere is the common case, not an anomaly. Name what you can
  see, and mark the rest `[ASK USER]`.
- **Work item links** in commit messages (`AB#1234`) point at Azure Boards.
  They are useful history; they are not readable from a checkout.

This skills repository is the deliberate exception, on public GitHub. The
reasoning is in [docs/architecture.md](../../../../docs/architecture.md).

## Reading the domain, without inventing it

Do not import a glossary from this file. Terms belong in `DOMAIN.md` only when
the repository actually uses them, bound to the symbol that implements them.

What to watch for, because these are where misreadings cluster:

- **Animal identity.** Cattle carry several identifiers with different scopes
  and lifetimes. They are not interchangeable, and a join on the wrong one is a
  silent correctness bug. If a repository has more than one identifier for an
  animal, that distinction is the single most important thing `DOMAIN.md` can
  record.
- **Evaluations and indexes.** Genetic evaluation produces values that are
  versioned, published on a schedule, and not comparable across runs. Code that
  treats them as a plain number is making an assumption worth surfacing.
- **Time and lifecycle.** Lactations, calvings, and breeding cycles are
  intervals with domain-specific boundaries, not arbitrary date ranges.
- **Units and scales.** Domain-specific units and reference bases appear
  throughout. A number without its base is not a number.

When you meet a term you cannot pin to a definition in the code, say so and
mark it `[ASK USER]`. A guessed definition in `DOMAIN.md` propagates into every
downstream agent session, and it is asserted with exactly as much confidence as
a correct one.

## Data sensitivity

Farmer, herd, and customer data is confidential and frequently commercially
sensitive.

- Never copy sample data into generated context.
- Never quote a connection string, hostname, or account name from a config
  file. Names of environment variables only.
- If you find production-looking data or credentials committed, that is a
  `CONCERNS.md` entry: report the path, do not read the contents, and do not
  quote them.

## Organization-required conventions

`CONVENTIONS.md` has a section for standards that come from outside the
repository being onboarded. Populate it only from a written CRV standard you
can point at.

If no written standard exists for something, it is not organization-required —
it is an observed pattern, and it belongs in the observed section with a count.
The distinction matters: an observed pattern reported as a standard becomes one
by citation.

[TODO] Link the internal CRV engineering standards here once a canonical
location exists. Until then, treat the organization-required section as empty
by default rather than filling it from memory.
