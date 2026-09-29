# Changelog

Notable changes to this repository. The distributable unit is the repository
itself, so versions here are repository versions;
[`metadata.version`](docs/authoring-skills.md) on a skill is informational and
tells a reader how much that skill has moved.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Issues are written to be read, not to be impressive.** A shared
  `issue-writing.md` caps the summary at 80 characters and catalogues the
  patterns that make text read as generated, with the rewrite for each:
  padding, false shape, the overused vocabulary, and the formatting tells. The
  templates dropped from eight required sections to four for a story and five
  for an epic, and an optional heading is now dropped rather than filled.
  Written after a batch whose stories were padded to three times the length
  anyone would read, which is how a team learns to skim acceptance criteria.
  Descriptions carry **no word cap**. An earlier draft capped a story at 200
  words and an epic at 400, and even the skill's own example story used 172 of
  its 200. The cap measured length when the failure was padding, so it cut the
  files, contracts and edge cases an implementer needs along with the filler.
  A story now keeps all of its content, gains an optional Technical notes
  section for exactly that detail, and more than about seven acceptance criteria
  prompts an offer to split rather than a cut. The
  pattern catalogue is adapted from
  [`blader/humanizer`](https://github.com/blader/humanizer) (MIT) and recorded
  in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- **The team field is asked, not defaulted.** `Assigned Team(s)`, `Team` or
  `Squad`, resolved by name, with the allowed values read from create-metadata
  and offered to the user in one question for the whole batch. `none` is a valid
  answer and is reported as the user's choice. A recorded default is now the
  starting point for that question rather than a substitute for it, because a
  default nobody is shown is a default nobody notices is wrong, and team
  assignments change faster than anyone re-runs setup. This is the one field the
  agent cannot derive: a spec does not say who will do the work.
- **Documentation is part of the change.** [AGENTS.md](AGENTS.md) carries a
  table of what else to update for each kind of change, and
  [CONTRIBUTING.md](CONTRIBUTING.md) the short version, binding the user, every
  session, and every subagent equally. `test_documentation_sync.py` enforces the
  part that had already failed: two Jira skills shipped and sat unlisted in the
  README for four commits. A skill nobody can find is a skill nobody uses.

- **`crv-create-jira-epic`** (`processes`, draft). Files one Jira Epic through
  an Atlassian MCP server, with a description rendered from a fixed section
  template. Preflight is a hard stop: no MCP tools or no machine configuration
  means nothing is created, because an epic filed into a guessed project looks
  like success in the transcript and is expensive to find later.
- **`crv-create-jira-story`** (`processes`, draft). Files Stories under a parent
  Epic. Searches the epic by JQL before the first create, so re-running a
  request that filed eight stories skips all eight rather than filing them
  again. Story points are optional and are not restricted to a Fibonacci
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
  approval, provided each issue carries a comment recording that its number was
  proposed and bulk-approved rather than groomed. `estimate_source` in the input
  schema carries that provenance. A comment rather than a line in the
  description, because a comment is dated history and stays true after the
  story is re-sized, where the description would contradict the field.
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

### Changed

- **The setup script is called by the skill's path, not the shell's.** Both
  skills said `python3 scripts/jira_setup.py`, which only works from inside the
  skill folder. From the user's repository it exits `2`, which the skill
  documents as a usage error, so the preflight failed with the wrong diagnosis.
- **The epic skill checks it can fix what it files.** It told the agent to
  patch an epic in place when the read-back contradicted the write, but never
  required the edit capability, so on a server without it the only possible
  outcome was a wrong epic reported as wrong. Edit is now a preflight
  requirement, as it already was for stories.
- **A failed batch finishes what it can.** After a create error the story skill
  said to stop, and the failure table said to finish pass two, so created
  stories kept their `[[dep:` placeholders and had no links. Pass two now runs
  among the stories that exist, the rest is reported, and a re-run backfills
  the leftovers. The same pass fixed text an economy model would follow the
  wrong way: a heading count left over from the unheaded opening, an example
  date it would copy literally, and two evals that contradicted the skill.
- **Re-running a batch with long titles no longer duplicates it.** The
  duplicate check compared the summaries as given, before they were rewritten
  to the 80-character rule, so a re-run's raw title never equalled the rewrite
  already in Jira and every such story was filed again as a "near match". Titles
  are now rewritten first, and both the rewritten and the given form are
  compared.
- **The story read-back checks what the run created, and nothing else.** It
  queried every child of the epic and asserted that the row count equalled the
  number created, so any epic that already had stories failed a correct run,
  and the team check judged stories other people had filed. Both it and the
  duplicate search also filtered on `issuetype = Story`, which made a candidate
  filed as a Task invisible to each. The duplicate search now covers every
  child type, and the read-back is `key in (<created keys>)` with the fields it
  needs named explicitly.
- **A project's own Priority default is not a failure.** The skills claimed
  `TBD` was not an allowed value on any tenant and expected Priority unset after
  every create. On BAPP, `TBD` is a real option and the project default, with
  an icon hosted off-site that renders broken, so Jira stores it on every issue
  created without a Priority, and the read-back would have failed every run.
  The skills still never choose a Priority. They now read the default from
  create-metadata, accept it in the read-back as the project's value, name it
  in the report, and offer the user the chance to set a real one.
- **Epic membership is always `parent`.** The skills told a company-managed
  project to use the legacy `Epic Link` field and treated `parent` there as a
  different relationship. That rule is out of date: Jira Cloud moved epic
  membership onto `parent` for both project styles, and a company-managed
  BAPP story holds its epic in `parent` while the create screen still offers
  `Epic Link` beside it. The skills now send `parent` only, search and read
  back with `parent = <key>`, and stop if `parent` is absent rather than
  falling back.
- **A story can open with a goal instead of a user story.** Refactors,
  migrations and platform changes have no real person to put in "As a ... I
  want", and forcing one produced "As a developer, I want the service split",
  which is the kind of filler the writing reference bans. A story may now open
  with a goal: one sentence on what is true afterwards and why. The input
  schema takes `goal` or `user_story`, never both.
- **Stories can carry a Tasks checklist.** Acceptance criteria say what is true
  when a story is done, and teams also want the steps to get there in the
  story itself. Tasks is an optional `- [ ]` section filled only from steps the
  person or the spec gave, since a generated task list is a plan nobody agreed
  to. A task that restates a criterion is dropped, and one big enough for its
  own owner is flagged in the report as a likely sub-task. It is called Tasks
  rather than TODO because TODO is a banned placeholder, and the pre-create
  check would fail every story that used it.
- **A story opens with its user story, not a heading.** Jira already labels the
  field Description, so a `## User story` heading as the first line repeated
  the frame the "As a / I want / So that" lines already carry, and looked
  wrong under the field label. The opening statement is now unheaded, and the
  three sections after it keep theirs.
- **Structured input has one rendering.** The story schema said what each field
  held but not where it went, so the same batch could render a test plan as a
  nested list on one story and a paragraph on the next. `structured-input.md`
  now maps every schema field to its heading or Jira field, and says what a
  missing required section does: it is asked about, never invented. A test
  fails if a schema field is added without a row.
- **A pre-rendered description is checked like any other.** The schema said
  `description_markdown` was "used as-is", which read as permission to skip the
  writing checks and the required headings. It now says the field replaces
  rendering, not checking, so the one input path with no template behind it is
  not also the one with no rules.
- **Filing an epic twice files it once.** `crv-create-jira-epic` now searches
  the project for an epic with the same summary before creating one, as the
  story skill always has. It used to search only after a create call errored,
  so re-running a request, or filing an epic a teammate had already filed, left
  two epics splitting the same stories. An exact match creates nothing and
  names the existing key. A near match is asked about once.
- **Story points are no longer mandatory.** Sizing belongs to the team, in
  grooming, with the people who will do the work. A story with no estimate is
  now filed with the field unset, named in the report, and counted separately
  in the total rather than folded in as zero.
  Requiring an estimate left only two moves, and both were wrong: block the
  batch over a value that takes five seconds to set in grooming, or invent a
  number that gets summed into a sprint commitment and cannot be told apart from
  an agreed one. `story_points` left the schema's required set, and
  `estimate_source` gained `unsized`.
- **Priority is never chosen by the skill.** Not from a recorded default, not
  inferred from a spec, and never as `TBD`, which is not an allowed option value
  on any tenant and renders as a broken icon on the board. That is what happened
  and what prompted this. A priority a person names explicitly is still sent,
  validated against the project's allowed options and reported as supplied; the
  input schema gives it a dedicated `priority` key and refuses it through
  `additional_fields`, so setting one stays a deliberate act.
- **The tier is stated, not asked.** Every skill now says which tier it is
  running on in one line and starts work. The rule was one prompt per
  invocation, before any work happened, and in practice nobody answered it: the
  user cannot judge the tier before seeing what the run involves, so it cost a
  round trip every time and taught them the skill's questions are noise. A tier
  named in the session or in the project's agent configuration is still honoured
  and reported. Choosing one silently is still forbidden.
- **A subagent with no Atlassian tools is diagnosed, not misreported.** MCP
  servers are granted per agent, so a spawned subagent can see no Jira tools
  while the session that spawned it has them, and the symptom is identical to a
  server nobody installed. Both skills now tell the two apart and hand back for
  an inline re-run instead of sending the user to reinstall something that is
  already there. Running inline is the sanctioned fallback: the subagent exists
  to keep intermediate reasoning out of the conversation, which is worth less
  than the run happening at all.
- **The story skill's failure table moved to `references/failure-modes.md`.** It
  had grown into a lookup table, which is what a reference is for, and the body
  keeps the non-negotiable stops. This brought `SKILL.md` back inside its token
  budget.

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
