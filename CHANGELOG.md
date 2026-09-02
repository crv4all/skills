# Changelog

Notable changes to this repository. The distributable unit is the repository
itself, so versions here are repository versions;
[`metadata.version`](docs/authoring-skills.md) on a skill is informational and
tells a reader how much that skill has moved.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`crv-create-jira-epic`** (`processes`, draft). Files one Jira Epic through
  an Atlassian MCP server, with a description rendered from a fixed section
  template. Preflight is a hard stop: no MCP tools or no machine configuration
  means nothing is created, because an epic filed into a guessed project looks
  like success in the transcript and is expensive to find later.
- **`crv-create-jira-story`** (`processes`, draft). Files Stories under a parent
  Epic. Searches the epic by JQL before the first create, so re-running a
  request that filed eight stories skips all eight rather than filing them
  again. Story points are required and are not restricted to a Fibonacci
  ladder: a roll-up of several items lands on no ladder at all.
- **Read-back before reporting, in both skills.** A create call that returns
  success proves an issue exists and nothing about what is in it: Jira accepts a
  field identifier it does not recognise on that screen by ignoring it. Both
  skills now re-read what they wrote and report the stored values, and the story
  skill asserts row count, epic membership, estimates, applied defaults and the
  point total against that read-back. Written after a run filed 29 stories with
  no epic link and reported completion "under the epic".
- **Epic membership resolved by name.** A company-managed project carries an
  `Epic Link` custom field; a team-managed one carries `parent`. The field
  reference now names both, with the payload shape each takes, and forbids
  assuming a `customfield_` number. Sending the wrong one produces a batch of
  orphans that reports as success.
- **Two-pass creation, and native issue links.** Stories are created first, then
  cross-references are backfilled with the keys Jira allocated, because a key
  cannot be cited before it exists. Dependencies are also written as native
  `Blocks` links, since blocked-by views, dependency reports and automation read
  links and not a prose heading. The inward issue is the blocker, and the skill
  verifies the direction against one read-back before creating the rest.
- **Dependency-graph validation before the first create.** Self-references,
  unknown references, and cycles of any length are caught on the candidate list.
  A cycle is reported as a decomposition error with its path, not silently
  resolved by dropping an edge.
- **Per-project field defaults.** `jira_setup.py --field-default "NAME=VALUE"`
  records what the organisation expects on every issue in a project, keyed by
  human-readable field name and scoped by `--defaults-project`. A create screen
  enforces what an administrator marked required, not what the team agreed to, so
  a field like `Assigned Team(s)` was left unset and then patched one issue at a
  time. Repeating a name stores a list; re-running the same command replaces
  rather than appends, so it stays idempotent.
- **Writing rules for titles and descriptions.** A shared `issue-writing.md`
  caps summaries at 80 characters and 12 words, bans em dashes, en dashes,
  arrows, plan-local numbering and field-duplicating prefixes, lists the words
  that name nothing, and shows rewrites. A summary is the most-read text in Jira
  and almost every place it appears truncates it.
- **Remediation for a batch that succeeded incorrectly.** "Stop and report,
  never improvise" covers a failure, not 29 issues created wrong. A shared
  reference covers establishing what is actually stored, patching in place as the
  default because keys are already in use elsewhere, one approval for one patch
  table, and the narrow cases where refiling is right. Deleting stays the user's
  call.
- **Derivable configuration.** Absent site or project no longer hard-stops when
  the answer was supplied: a board or issue URL in the conversation, or a single
  accessible site. The value used, and where it came from, is reported along with
  the command that records it. Two candidate sites, or a project named but not
  keyed, is still a guess and still stops the run.
- **Bulk estimation, sanctioned.** Asking for 29 estimates one at a time is 29
  questions. The skills may propose every estimate in one table and take one
  approval, provided each issue records that its number was proposed and
  bulk-approved rather than groomed. `estimate_source` in the input schema
  carries that provenance.
- **One tier question, asked by the orchestrator.** Both skills now distinguish
  the session that spawns from the subagent that executes. The executor is told
  the tier and starts work; it does not re-ask a question the user already
  answered, which previously cost two round trips per invocation.
- **Tenant configuration outside the repository.** Both skills bundle
  `jira_setup.py`, which records the Jira site and default project key in
  `${XDG_CONFIG_HOME:-$HOME/.config}/crv-agent-skills/jira.json` at mode `0600`.
  Nothing tenant-specific is committed. Credentials are refused outright — a
  token passed to the script exits `2` with a message saying authentication
  belongs to the MCP server, because a second copy on disk is a second thing to
  leak. Custom-field identifiers are not stored at all; they are resolved from
  project create-metadata by field *name* on every run, since they differ per
  tenant and change when an administrator edits a screen.
- **Drift guard.** `test_shared_jira_files.py` asserts that the setup script and
  the four shared reference files are byte-identical across both skills. They are
  duplicated on purpose — `install.sh` installs one skill at a time, so a skill
  reaching for a sibling's files would break silently — and nothing else in the
  repository would notice a one-sided edit.
- **Story input schema.** `story_input.schema.json` with a contract test pinning
  the required triple, the positive-integer estimate, the deliberate absence of a
  Fibonacci enum, the estimate provenance, and machine-readable dependency edges.
- **Setup-script tests.** `test_jira_setup.py` covers the field defaults end to
  end: scalar against list, per-project scoping, idempotent re-runs, refusal of
  `customfield_NNNNN` identifiers, and a hand-mangled defaults block reported as
  malformed rather than absent.

## [0.1.0] — 2026-08-18

First working repository. Not published, and not tagged for release: both
skills are `draft`, and nobody outside the authors has completed a real task
with either.

### Added

- **Governance.** JSON Schema for `SKILL.md` frontmatter — the specification's
  six closed fields plus CRV metadata, with `additionalProperties: false` so a
  non-spec key fails loudly instead of being ignored by one harness and
  rejected by another. Required: `owner`, `layer`, `maturity`, `execution`,
  `model-tier`; additionally at `stable`: `version`, `tags`, `review-cadence`.
- **Execution contract.** Every skill runs in a subagent on the `economy` model
  tier, states the tier before starting, and offers to change it. Enforced in
  the schema and, separately, by requiring a `## Execution` section in the body.
- **Context budgets.** 500 lines / 25,000 characters / 5,000 tokens
  (`cl100k_base`) for `SKILL.md`; soft 400-line warning under `references/`.
  Warns at `draft`, fails at `stable`. The budget config is itself
  schema-validated, so a misspelled key cannot silently disable a check.
- **Validators.** `validate_frontmatter.py`, `check_budgets.py`,
  `scan_secrets.py`, `build_catalog.py`. JSON on stdout, diagnostics on stderr,
  distinct exit codes, no prompting.
- **`crv-codebase-onboarding`** (`processes`, draft). Five phases, four modes
  detected rather than asked. Evidence gathering is deterministic and concludes
  nothing; interpretation happens afterwards, so README/code divergences surface
  instead of being smoothed over. Bundled `scan.py` and `validate_context.py`
  are stdlib-only on Python 3.9 and never reach the network, execute project
  scripts, emit secret values, or modify the target.
- **`crv-create-skill`** (`processes`, draft). Boundary test first, then a
  round-based interview over the frontier of settled decisions.
- **Documentation.** Design principles, authoring, testing, architecture,
  installing.
- **Five test fixtures**, each with a documented planted trap, plus a pytest
  suite covering the validators and the bundled scripts.
- **`install.sh`.** POSIX shell, no dependencies beyond `git`, `--dry-run`
  always available, and refuses to overwrite a locally modified skill without
  `--force`.
- **CI.** Lint, types, markdown, tests, skill gates, a Python 3.9 floor job, and
  shellcheck. Actions pinned to commit SHAs.

### Removed

- Claude Code and Cursor marketplace and plugin manifests, and the code and
  tests behind them. Nobody has installed one of these skills yet; a manifest at
  this point is untested machinery describing untested content, and it commits
  us to a distribution channel before we know whether the skills are worth
  distributing.

### Fixed

Bugs found by writing the tests, recorded because each one is a class of
mistake likely to recur:

- Skill discovery matched `skill.md` as `SKILL.md` on case-insensitive macOS,
  so it would have disagreed with Linux CI and every Linux agent runtime.
- The bundled-reference check treated `standards/scripts/x.py` as a bundled
  `scripts/x.py`, producing false dangling-reference errors.
- `install.sh` used `find -print0` with `read -d ''`, both bashisms. They work
  on macOS, where `/bin/sh` is bash in POSIX mode, and fail silently on dash —
  taking local-modification detection with them.
- `install.sh` counted results inside a pipeline, so the subshell's exit state
  was lost and a refused overwrite still exited `0`.

[Unreleased]: https://github.com/crv4all/agent-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/crv4all/agent-skills/releases/tag/v0.1.0
