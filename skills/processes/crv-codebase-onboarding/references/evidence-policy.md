# Evidence policy

What counts as evidence, what may be read, and what may never leave the
repository. These rules make the output checkable and make the skill safe to
point at any CRV codebase without asking first.

## What counts as evidence

| Strength | Kind | Example |
| --- | --- | --- |
| Strongest | A declaration in a build or config file | `pom.xml:34` declares `spring-boot-starter-web` |
| Strong | Code at a specific path and line | `OrderService.java:88` calls `repository.save` |
| Strong | A CI definition | `.github/workflows/ci.yml:22` runs `mvn verify` |
| Moderate | A dominant pattern, with a count | 23 of 27 controllers return `ResponseEntity` |
| Weak | Prose in a README | "the service is stateless" |
| Not evidence | A name that sounds like a thing | A directory called `core` |
| Not evidence | Absence, unqualified | "there are no tests" without saying where you looked |

Prose in a README is a **claim to verify**, not a fact to repeat. When code and
README disagree, both go in the output: the code as the fact, the disagreement
as a concern.

Absence is reportable only when scoped: not "there are no integration tests",
but "no files match the integration-test conventions this scan knows
(`*IT.java`, `tests/integration/`, `*.e2e.ts`); if they exist they use a
convention I did not detect."

## Citation format

- A file: `src/api/OrderController.java`
- A specific line: `src/api/OrderController.java:42`
- A range, only when the whole range matters: `pom.xml:120-138`
- A directory, when the claim is about the group: `src/domain/`

Every path must exist in the target repository. Check them before reporting.
Fabricated paths are the characteristic failure of this task: each one is
individually plausible, they are trivially cheap to verify, and a reader who
finds one stops trusting the entire document.

Line numbers must point at what the text says they point at. A line reference
that is off by thirty lines is worse than no line reference, because the reader
concludes the file changed and goes looking for a change that never happened.

## Hard safety rules

**No network access.** Nothing is fetched, resolved, or looked up. Everything
comes from the working tree.

**No execution of project code.** Read `package.json`; do not run
`npm run build`. Read the `Makefile`; do not run `make`. Read the test config;
do not run the tests. Running a project's scripts has side effects on a machine
you do not own — installs, generated files, network calls, occasionally a
deployment.

Read-only `git` is the single exception: `git log`, `git status`,
`git rev-parse`, `git diff --name-only`. Never `git checkout`, `git clean`,
`git stash`, or anything that changes the working tree.

**No secret values, ever.** Report that `DATABASE_PASSWORD` is required and
where it is referenced. Never report its value — not from `.env`, not from a
config file, not from a CI variable, not "redacted but obviously the default".
A committed `.env` is a *finding*, reported by path, contents unread.

**No modification of source.** The only writes are `docs/codebase/` and the
marked block in `AGENTS.md`. Not a formatting fix, not a typo, not a lint
error. If you find one, report it.

## Reading policy by file type

| Type | Read | Notes |
| --- | --- | --- |
| Source, build manifests, config, CI, IaC, migrations | Yes | The core evidence |
| `.env.example` and friends | Yes | Variable *names* are the point; treat any value as untrusted and do not copy it |
| `.env`, `*.pem`, `*.key`, `*.pfx`, keystores | No | Report existence by path only |
| Lockfiles | Existence and package manager only | Never inventory the contents |
| Generated code | Enough to identify it as generated | Then note what generates it and move on |
| Vendored dependencies | No | Note that they are vendored and where |
| Binary assets, media, data files | No | Count and note; do not read |

Generated and vendored code dominates file counts and teaches nothing about how
the project is built. Identifying it correctly is itself a useful finding,
because a newcomer will otherwise read it as house style.

## Reporting what you could not determine

A named gap is a finding. Silence reads as "there was nothing there", which is a
claim you did not make and cannot support.

Good: "How this service is deployed is not determinable from this repository.
`.github/workflows/ci.yml` builds and pushes an image to a registry, and
nothing here references that image. The deployment definition is probably in
another repository — `[ASK USER]` which one."

Bad: silence, or "deployed via CI/CD".

## Markers

`[TODO]` — outstanding work you know about.
`[ASK USER]` — a decision or fact that is genuinely the user's and cannot be
resolved from the code, the docs, or the history.

Nothing else. Every `[ASK USER]` is collected into the final report; a marker
left in a file and never surfaced is a question nobody was asked.
