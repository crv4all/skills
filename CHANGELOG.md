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
  the two shared reference files are byte-identical across both skills. They are
  duplicated on purpose — `install.sh` installs one skill at a time, so a skill
  reaching for a sibling's files would break silently — and nothing else in the
  repository would notice a one-sided edit.
- **Story input schema.** `story_input.schema.json` with a contract test pinning
  the required triple, the positive-integer estimate, and the deliberate absence
  of a Fibonacci enum.

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
