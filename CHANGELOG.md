# Changelog

Notable changes to this repository. The distributable unit is the repository
itself, so versions here are repository versions;
[`metadata.version`](docs/authoring-skills.md) on a skill is informational and
tells a reader how much that skill has moved.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **A failed verification can no longer be skipped into done, and the verdict line
  cannot hide.** `decide --decision skip` is refused once a stage that records a
  `Verdict:` has started (finish it with a passing run or reopen it). Skipped before it
  starts, the Slice stays `built` and the Slice and Unit rows say "verification
  skipped"; `verified` needs a stored `Verdict: pass`. The verdict reader ignores fenced
  lines and counts a line with any decoration (bold, quote, indent, heading, BOM), so two
  verdict lines of any kind are ambiguous. `gate` warns when the Unit or Slice belongs to
  someone else, as `step` and `decide` do, and the stage texts no longer mention an
  approver.
- **A Unit's reliance now reaches its stories, requirements and decisions.** In the
  documents Inception writes, the story map and the stories cite the Unit and the Unit's
  own section cites only components and contracts, so a changed story, requirement or
  decision was reported to nobody. The relied-on set now starts from the Unit's own
  declaration, every declaration that cites the Unit (story-map rows, stories, contracts)
  and what its own files cite, then follows two hops; per-Unit stages and Build and Test
  also read `stories.md`. A started Unit that relies on nothing, or on no decision, says
  so in one line in `context --unit` and `status`. A Markdown file that is not UTF-8 is
  skipped with a warning instead of dropping the whole index; if the index cannot be built
  the report says `index: unavailable` and the stored baseline is kept. `step --to
  produced` returns and logs what changed before it refreshes the baseline. Decisions are
  tracked as a set of numbers, so one reserved early and written late is seen. Spacing and
  column padding no longer count as a change, a long section is hashed whole, a missing
  baseline is reported only for open per-Unit and per-Slice work, and `deployment-pipeline`
  reads `hla.md` and `tdd.md` without tracking them as files (it tracks the decision
  records by id).
- **Work saved here but not shared no longer turns into a manual conflict.** A push that
  failed (offline, or rejected three times) left local commits; when the team then changed
  the same Bolt `state.json`, the next command stopped in `state.json` and `log.md` and
  its advice dropped only one of the commits. Now the next command and `sync` set the
  clashing commands aside, keep every other unshared commit (artifacts, a Unit's own
  file) by applying it again in order, and list the undone commands by their commit
  subjects so the engineer can repeat them. If a clashing commit also holds other files,
  or a kept commit does not apply, it stops with exit 6 and the branch exactly as it
  was; it never uses `reset --hard` and uncommitted work stays. The race check
  recognises the command's own commit by its hash, the checkout lock waits 200 s (a git
  step can take 120 s) and sits in the git directory even with `--no-git`, and only the
  script's own temp file pattern is left out of a commit.
- **A Bolt or Slice whose Units are all cancelled can be closed.** The "no Units yet"
  placeholder appears only when no Unit exists; a Slice whose Units are all cancelled
  derives the status `cancelled` and has no Build and Test. A new Unit without a `slice`
  is refused when the Bolt has Slices (it would never be covered), and a units file with
  a `slice`, `name` or `units` of the wrong type fails with the malformed-input exit
  code instead of a traceback.

### Added

- **`contribution` records where an architecture contribution stands, and the team
  can see them.** `aidlc_state.py contribution --bolt B --concern C --status
  draft|proposed|merged [--note "..."]` checks that
  `architecture/contributions/C.md` exists and that its header carries that status
  and an owner, then appends one log line. It edits no file and runs no validator.
  `status` and `overview` list each contribution (concern, owner, status, the
  sections it touches) read from the headers; a proposed one is shown as open work.
  Nothing is stored in `state.json`, so two engineers adding two contributions and
  editing two sections of `hla.md` push without a manual step.
- **The HLA check finds contradictions a script can see.** `validate_doc.py` on
  `hla.md` now reads `hla-decisions.md` next to it and reports a cited `D<n>` the
  record does not declare (a finding; unit-scoped ids, code fences and appendices
  are ignored), a cited decision whose Status is `superseded` (a warning), a term
  or container with two different owners (a finding) and an interface producer or
  consumer that is no container named in the document (a warning). A table or a
  record the document does not have is skipped silently. Run on the real frame
  Bolt HLA it adds no finding and no warning.
- **Several engineers can contribute to one architecture, each in their own file.**
  One Bolt has one `architecture/hla.md`, but a concern (security, networking, a
  data model) is often investigated by a different person in a different session.
  A contribution is `architecture/contributions/<concern>.md`: a small file with a
  yaml header (`concern`, `owner`, `status` draft, proposed or merged, `touches`,
  `affects`) and six short sections. It has no stage and no lifecycle; its author
  merges the conclusion into `hla.md`, and the reasoning stays in the file. The HLA
  skill ships `contribution-template.md` and `contribution-header.schema.json`, and
  `validate_doc.py --kind contribution` checks the header, the leftover
  placeholders, the file name against the concern, and that every decision id the
  file cites exists in the decision record.
- **Work is told about the changes that matter to it, and only those.**
  Change detection used one hash per input file, taken when a stage was produced
  or passed. A second Slice adding rows to a shared document flagged every Unit of
  the first Slice, while a value changed below a document's digest, an input that
  appeared later or a changed dependency list went unnoticed, and the architecture
  decisions were not an input of any Unit stage. Now a Unit (or Slice) relies on
  the ids it cites, and on the ids those declarations cite, two hops out. The
  baseline is taken when work starts and keeps hashes and ids only, never text.
  `stages.json` inputs may say `"track": "ids"`; the architecture and Inception
  decision records are now optional inputs of every per-Unit stage and of Build and
  Test. `next`, `brief`, `status`, `overview` and the checkpoint report, by id, what
  changed, was superseded or removed; later decisions that cite something the work
  relies on; later Bolt-wide constraints; inputs that changed, appeared or vanished;
  a changed dependency list; and a missing baseline. An addition that touches none
  of these reports nothing. Finished work that relied on something that changed is
  listed apart. The new `context` command shows the report and what a Unit or Slice
  relies on (`--unit` or `--slice`), who relies on one id (`--id D63`), and records
  a conclusion with `--note`, the one way a report clears. Nothing waits for it and
  the checkpoint never refuses on it. `aidlc_refs.py` gains `cited_in` and keeps a
  table row's cells on the declaration; `status` and `overview` no longer carry
  `stale` rows.

- **The readiness check warns when logs have no `merge=union` rule.**
  `check_prerequisites.py` reports, as a warning, a planning repo whose
  `.gitattributes` does not merge `bolts/*/log.md` and `bolts/*/units/*/log.md`
  by union, because two engineers' log lines would then conflict.

- **Decision ids never repeat, and `--provisional` is gone.**
  A Bolt whose decision record already holds D75 while its counter says 73 used
  to hand out D74 again. `decision-id` now starts above both the stored counter
  and the highest `D<n>` in the Bolt's `hla-decisions.md` and `tdd-decisions.md`,
  and the counter follows. A reservation, shared or a unit's own, returns no ids
  when it could not be shared with the team; the shared counter still refuses
  outright when the remote cannot be reached. The `--provisional` flag, which
  handed out ids that might clash, is removed.
- **A state file is never merged: the command runs again on the team's newer state.**
  When two engineers changed the same Bolt's `state.json`, the rebase conflict
  said "take the team's version", which silently dropped one engineer's change
  while its log line stayed; and when both made the identical change (both took
  decision id D1) git merged it cleanly and both held the same id. Now, if the
  team's newer commits touch a state file the command also wrote, the command's
  own commit is dropped (`git reset --keep`, never `--hard`), the clone is
  brought up to date, and the command runs again on the new state (at most three
  times, then it stops saying the change was not applied). A re-run that no
  longer applies, for example because someone else closed the Bolt, fails
  cleanly and leaves state and log equal to the team's. `open` and `close` are
  not run twice automatically, and their conflict rule no longer tells anyone to
  take one side. When a push did not happen, the result says `not_shared: true`
  and `status` and `overview` show how many changes are saved here but not
  shared yet.

- **Leftovers and unresolved conflicts are never committed.**
  A state write that was killed halfway used to leave `.state.json.tmp`, which
  the next automatic commit picked up. Each write now uses a temp name of its
  own process and cleans it up, and no `*.tmp` file is ever staged. A file in
  the Bolt that still holds git conflict markers (`<<<<<<<`, `=======`,
  `>>>>>>>`) stops the commit with exit 6 and the files are named.

- **One lock per planning checkout, held for a whole command.**
  Two sessions in one checkout on two different Bolts used to fail half of
  their commands (`index.lock`, "a rebase is in progress"), because the old
  per-Bolt lock covered only the state write and not the git steps. A command
  that changes a Bolt, and `sync`, now holds a single lock for the sync before,
  the command and the sync after; the second session waits up to 60 s and then
  stops with a message naming the lock file. The lock lives in the git
  directory (`.git/aidlc.lock`), or at the planning root outside git, and the
  operating system frees it when a session dies, so there is no stale lock and
  no expiry. Reads never wait. Native Windows keeps a weaker file-based lock.

- **`overview` shows every Bolt of a planning repo at once, and an edit to an approved artifact is noticed.**
  `aidlc_state.py overview --root <repo>` reads each Bolt (a broken or newer
  one is listed with its error) and prints its next step, children, units with
  owner and what they wait for, changed context, the latest log line and a short
  list of deterministic problems: a parent HLA not accepted, an unowned or
  waiting unit, a contested or still-open decision. `--log N` merges the last
  lines of all logs. When the automatic commit includes a changed artifact of an
  approved stage, it warns, once, and logs `approved-change`; it never refuses.
- **Decisions carry a status and an owner, a parent hands each child a brief, and questions are classed.**
  The decision record may add `Status` and `Owner` columns; the gate refuses a
  status word outside the list. The `hla` stage reads an optional
  `architecture/briefs/<child slug>.md` from its parent in full. A question may
  carry `Class:`; `lint_questions.py` refuses a reversible or trivial one
  (`should-not-ask`) and an unknown class, and a bullet under `## Assumed`
  needs a `because`. The rule is in the router's SKILL.md because the shared
  core rules have no token room left.
- **Several engineers can build different units of one Bolt at the same time.**
  `open --units split` (or `"units": "split"` in `aidlc.json`) keeps one
  `state.json` and one `log.md` per unit under `units/<id>/`, so moving a unit
  never rewrites the shared files, and a git conflict can only happen when two
  people change the same unit, which has its own rule. A state-changing command
  holds a short local lock, a unit's owner is asked before someone else changes
  it (`--takeover` records why), and `decision-id --unit` numbers a unit's
  decisions from D1, cited elsewhere as `<unit>:D<n>`. The shared decision
  counter now refuses, or returns no ids, when it cannot be confirmed with the
  remote. `aidlc_refs.py` resolves `<unit>:D<n>` in a split Bolt. The framework
  number is now 3.
- **Units have an owner, a repository and what they wait for, and a stage notices changed context.**
  `units --set` takes `owner`, `repo` and `depends_on` (a unit id, or
  `{"unit", "on": "done" | "contract"}`) and refuses a cycle or a repository
  the Bolt does not target. `next --unit U` and `next --mine` route one
  engineer's own units and say what each waits for, `assign` changes an owner,
  and `brief --unit U --write` writes a starting page of pointers. A stage
  records a hash of each input it relied on; when one changes later, `next` and
  `status` show it and the gate asks for `--ack-context` before approving.
- **A Bolt's `state.json` holds no machine paths, and records who did what.**
  Targets, the ADR registry and extra folders were stored as absolute paths, so
  a second engineer's checkout broke the Bolt. State now keeps the repository
  name; the path lives in a per-machine `.aidlc-local.json` at the planning root
  (never staged) and defaults to the folder of that name next to the planning
  repo. An older state is moved over on its next change. The log's fourth field
  becomes `agent:<git user.name>` when it is known, and an approval entered for
  someone else needs `--channel` (for example `email 2026-11-24`), stored with
  who recorded it. Each state also carries a framework number, and skills that
  are older than the Bolt refuse it instead of misreading it.
- **`aidlc_refs.py` makes every Bolt id resolvable without model tokens.**
  Ids such as `D10`, `A-Q3` and `L986` are forgotten, and recalling one meant
  re-reading whole files. `show` answers an agent in one line per id, `link`
  turns each cited id into a Markdown link plus one generated block per file
  (reversible with `--remove`), and `index` writes a page of every id. The
  traceability check and the document validator now ignore the generated
  block, so linking never changes their result. An optional `aidlc-refs.json`
  in the Bolt names the documents that line references cite and the words
  that mark an id from another numbering. No core rule calls it: the shared
  rules have no token room in the construction budget, so it runs when someone
  asks for it.
- **Bolt work is committed and pushed by the state script.** Every
  `aidlc_state.py` command that changes a Bolt first brings in the team's
  work, then commits the Bolt and pushes it to the shared branch named in
  `aidlc.json`; a new `sync` command does the same for work that changes files
  but no state. A conflict stops with exit 6 and a rule per file, so the agent
  resolves it without asking the person. A likely secret in the commit also
  stops it.
- **`onboard.py` sets up a new machine.** It checks the tools and the git
  identity, creates and registers an SSH key for Azure DevOps when none works,
  clones or updates the ADR registry, the planning repo and this repository over
  SSH, installs the skills and runs the readiness check. It runs on macOS,
  Windows and Linux, and a second run is the update path.
- **The readiness check covers access and freshness.** It now checks SSH access
  to Azure DevOps, that no remote uses https, the working branch, whether the
  installed skills are current, and compares the ADR index with the registry's
  remote, not only the local checkout.
- **`build_adr_index.py --refresh`** fetches the ADR registry, fast-forwards a
  clean checkout and reports which ADRs were added or changed in status. The
  architecture skill runs it before shortlisting ADRs.
- **A staged delivery process starts with its entry skill.** `crv-aidlc` opens,
  resumes and closes a "Bolt" (the folder for one piece of work), says which
  stage skill is next, and refuses to approve a stage whose artifact is missing,
  has no digest, or whose questions are unanswered. Progress lives in one
  `state.json` changed only by a script, and the checks that have one right
  answer (question-file linting, document outlines, ADR indexing) are scripts
  too, so resuming costs a few hundred tokens instead of rereading the folder.
  The stage list is provisional until the stage contract is written; the other
  five skills of the process follow.

- **Architecture is designed in three rounds of written questions, not a long
  chat.** `crv-aidlc-hla` keeps twelve design layers but asks them in three
  question files, proposing a design per layer and asking only what the inputs
  and accepted ADRs leave open, so every answer and decision stays on record and
  each round can be its own session. Following an accepted ADR is cited rather
  than decided again; departing from one surfaces as an exception, a risk and a
  question for reviewers. The security-consultation flag has no default, and an
  HLA counts as accepted only when a person signs its header: the gate refuses
  otherwise.

- **A technical design document is written only when it earns its cost.**
  `crv-aidlc-tdd` first checks whether the HLA review asked for one or a
  high-risk impact flag applies, and records a skip with the reason when
  neither does. It refuses to start before the HLA is accepted, carries HLA
  decisions forward instead of asking them again, and treats an answer that
  contradicts the HLA as an HLA change.

- **Code research happens once per repository, not once per piece of work.**
  `crv-aidlc-reverse-engineering` keeps one code-knowledge store per target
  repository and checks it against the repository's current commit, so a second
  Bolt on the same code reuses it and a stale store is rescanned only where
  files changed. A script inventories the repository first, so the model spends
  its tokens on understanding the code instead of discovering the layout.

- **Requirements, stories and units stay traceable without anyone reading
  them all.** `crv-aidlc-inception` gives every requirement, story, acceptance
  criterion and unit a stable id, and `check_traceability.py` blocks the last
  Inception gate while anything is unassigned or referenced but never declared.
  Decisions the accepted HLA already made are cited, not asked again.

- **Construction is deliberately thin.** `crv-aidlc-construction` loads about
  2,500 tokens of rules per stage because the design effort belongs before it.
  Code is written only from an approved checkbox plan, in every scope, and
  Build and Test runs the commands and records each target as met, not met or
  unverified.

- **A release is planned and recorded, never run by the agent.**
  `crv-aidlc-operation` closes the gap after Build and Test, which never
  deploys: people had no staged place to agree the order, the rollback and the
  checks for a migration or cut-over. The agent prepares the runbook and records
  each step with the evidence a named person gives; anything that changes an
  environment stays a human task, because a wrong command there cannot be taken
  back. It reuses each repository's existing release mechanism instead of
  designing a pipeline. Bolts opened before the two stages existed keep
  working and are asked to decide them.

- **Units of work are tied to Jira tickets, and the tie is checked.** Nothing
  in the process said what becomes a ticket, so work started on units nobody
  had filed and finished work stayed open in Jira. One Epic per Bolt and one
  Story per unit are now recorded through the state script; Construction of a
  unit is refused until its Story key is recorded (or Jira is turned off with a
  reason), and a Bolt cannot close as complete while a filed Story is not
  recorded as done. User stories stay planning detail and are never filed.
  Older Bolts work unchanged.

- **The organisation answers its policy questions once.** A programme of seven
  Bolts asked the same questions about story format, acceptance-criteria
  style and unit granularity seven times. `docs/presets.md` in the planning
  repo now holds default answers written by people; a stage does not ask what
  a preset answers, and a Bolt can override one, for itself only, with the
  approver's reason. `lint_questions.py --presets` checks the file and the
  preset ids a question file cites. The template ships empty, because a
  default invented by a tool is not the organisation's answer.

- **A retirement is planned piece by piece.** One point of no return for a
  whole runbook is wrong when pieces are removed one at a time, and nothing
  proved that no unlisted consumer still used a piece. Operation now marks a
  point of no return per component, states what rollback means before and
  after each, requires a quiet period before anything is removed, runs the
  neighbours' checks after every change, and records a support window.

- **A new person can tell whether they are ready before the first Bolt.**
  A partial install (a skill added to the repository but not on the machine)
  made a stage fail in a way that looked like a process bug.
  `check_prerequisites.py` names what is missing or out of date, with the fix
  command, and `crv-aidlc` runs it before opening a Bolt. It only reads; a
  pass is remembered until an installed shared file changes. A getting-started
  guide in the planning repo covers the rest.

- **Smaller work takes a shorter path through the same process.** The
  `express` and `bugfix` scopes skip stories, units and Slice planning; `bugfix`
  requires a regression test that fails before the fix and passes after.

- **Design documents are checked by a script before anyone reads them.**
  `validate_doc.py`, shipped with both design skills, catches what a skim
  misses: a header field left empty or as a placeholder, a section missing or
  out of order, a decision id reused, an ADR id that does not exist, a diagram
  with no explanation, a TDD written against an HLA nobody accepted. The
  templates themselves fail only on their placeholders, which a test keeps
  true.

- **A stage can now gate on several question files and a signed header.** The
  HLA's three rounds share one stage, its clarification files no longer mix
  with the TDD's in the same folder, and a stage can require that a person set
  its document's header to accepted before approval. The `hla` and `tdd`
  entries of the stage list are final; the rest stay provisional.

- **Every folder of a Bolt opens at once, and an old checkout is caught
  before it is read.** A Bolt spans the planning repo, the ADR registry and
  several target repositories, which people opened by hand, and a checkout
  behind its origin was scanned without anyone noticing. `aidlc_state.py
  workspace` writes a multi-root workspace file and a terminal command that adds
  the same folders, and reports per checkout its branch, how far it is behind or
  ahead of the default branch, and local edits; `--fetch` refreshes origin first
  and records a failed fetch instead of stopping. Reverse engineering now stops
  on a stale checkout unless the approver says to scan as is. Targets added
  after `open` go through `target --add`, which classifies them as `open` does.

- **A programme can be designed once and delivered in phases.** A Bolt opened
  with `--parent` is a child of a frame Bolt: its HLA stage reads the
  parent's decision record and HLA digest first, opens round A with what the
  parent already settled, and never asks it again. A child decision that
  departs from a parent decision is flagged like a departure from an accepted
  ADR. `status` and `inputs` say when the parent's HLA is not yet accepted, and
  `validate_doc.py` checks every `parent:D<n>` citation against the parent's
  record, so a cited parent decision cannot quietly not exist.

- **A frame Bolt closes at its HLA.** A programme-level Bolt designs no
  component, yet closing it as complete was refused until someone decided the
  TDD, Inception and Construction stages by hand. `open --kind frame` skips
  every stage after the HLA with that reason, so the Bolt is done once the
  HLA gate is approved. `kind --set` converts an existing Bolt, and is
  refused once any of those later stages has started.

- **Answer lines are written as `Answer:`.** Followed by text, the old
  `[Answer]:` is Markdown link-reference syntax: a formatter deleted one answer
  line and rewrote the rest as links, and the question lint then failed on every
  question. `lint_questions.py` still reads `[Answer]:` in existing files, and
  reports the rewritten form as `answer-rewritten` with the fix. It also counts
  a layer's `Proposal:` paragraph as the context of that layer's first
  question, which a first real run reported as eight false failures.

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

- **Build and Test and Operation run once per Slice.** They existed once per
  Bolt, became next only when every Unit was done, and could not be redone for a
  second Slice. `build-and-test`, `deployment-pipeline` and `deployment-execution`
  are now `per_slice` in `stages.json`: their records live in the Slice, their
  files under `docs/slices/<slice>/...` (for example
  `docs/slices/s1/build-and-test/test-results.md`) and `<unit>` in their inputs
  covers only that Slice's Units that are not cancelled. `decide`, `step`,
  `gate` and `inputs` take `--slice ID`; with one Slice the flag is optional,
  with several it is a usage error that lists them. A Slice's Build and Test is
  next when its own Units are done, whatever the other Slices do, and `next`
  says "waits for slice s1 (verified)" for a Slice that depends on one that is
  not. `next --slice ID` routes one Slice, plain `next` in a split Bolt lists
  Units and Slices in progress, and `next --mine` includes the Slices you own.
  A Unit of a Slice that is not ready reports it. `status` and `overview` show
  one line per Slice, and `close --status complete` needs every executed stage
  of every Slice and every live Unit passed. A passed Slice stage can be
  reopened like a Unit stage. A `state.json` written earlier loses its
  Bolt-level records for these three stages when it is read; progress moves into
  the only Slice, or the first one, with one `migrate` log line.

- **A Slice is a small record with one readiness checkpoint.** A Slice used to
  store `{id, units, status}` and nothing read the status. Now each Unit's own
  `slice` key is the only record of membership, a Slice stores
  `{id, name, owner, depends_on, ready, stages}`, and its status (planning,
  ready, building, built, verified, released) is worked out from what happened,
  never stored. New `slice --add ID [--name] [--owner] [--depends-on]` adds
  one, `assign --slice ID --owner NAME` changes its owner and `units --set`
  merges slice entries by id like units. `slice --ready ID` checks whether
  enough engineering context exists to start the Slice's Units: it refuses a
  Slice with no Units or a broken dependency, and lists the gaps it finds (an
  unfinished Discovery or Inception stage, a failing increment question file,
  traceability findings about this Slice's Units, an unknown decision status)
  with what each one costs. With gaps it needs `--note "<direction>"` to go on;
  the Slice is then ready with the gap codes stored and `status` shows
  "ready, N open gap(s)". A single-Slice Bolt (express, bugfix) starts ready.

- **Loading units adds and updates; it no longer reloads.** `units --set` used
  to replace every unit, which dropped each unit's decision counter (a unit was
  handed D1 twice), rewrote every unit's state file, silently overwrote owners
  and could orphan units. It now adds the ids it has not seen, updates an
  existing unit only in the keys the file gives (`name`, `kind`, `repo`,
  `depends_on`, `slice`) and leaves everything else, and every unit the file
  does not mention, as it was. A different `owner` for an existing unit is
  refused and points to `assign`. Dependency checks run over the merged set.
  New `units --cancel U --reason "why" [--superseded-by u7,u8]` takes a unit out
  of routing, progress and the "all units done" tests without deleting its
  record, files or history; a unit that depends on it shows that until its
  dependencies are updated. Splitting a unit is a cancel plus new units.

- **The work folder is a Bolt and the Construction slice is a Slice.** A Bolt
  is a bounded, outcome-driven engineering initiative: its shared requirements,
  architecture decisions, units of work and audit trail, held in one folder
  under `bolts/` and addressed with `--bolt`. What AWS AI-DLC calls a Bolt, the
  planned Construction slice over dependency-linked units, is a Slice here:
  `slices` and `slice` in `state.json`, default id `s1`, and `slice-plan.md`.
  Stages, gates, exit codes and file formats are otherwise unchanged. A
  `state.json` written earlier needs its top-level `bolts` key renamed to
  `slices`, each unit's `bolt` key renamed to `slice`, and its folder moved
  under `bolts/`. Every script takes `--bolt`.
- **A justified model tier no longer warns.** The validator asked for a
  higher tier to be justified in the Execution section but warned whether or
  not it was, so `--strict` failed every skill that genuinely needed one. It now
  stays quiet when the section states ``**Model tier: `<tier>`.**`` with a
  reason on the same line, and still warns when the reason is missing.

- **Story points are never pushed.** They were already optional, but the
  check-in asked about them on every batch, and the report listed each story
  without points "so grooming has the list", which treated an empty field as a
  gap. An empty estimate is the normal state before grooming. The skill now
  sets points only when the person gives them, proposes numbers only when
  asked to, and otherwise says nothing about sizing.
- **Rules for the fields nobody mentioned.** Sprint, components and fix
  versions had no rule, so a request for "the current sprint" had nowhere to
  go. They are now asked only where the project has them and left unset
  otherwise, and a named sprint is resolved through an issue already in it,
  since create-metadata lists none. Supplied labels merge with a recorded
  default instead of replacing it. A tenant without a `Blocks` link type gets
  its stories and a prose-only dependency list, never a `Relates` link standing
  in for one, and a dependency on a key that does not exist is asked about
  before it becomes a link to nothing.
- **One check-in, with the draft, before anything is filed.** Both skills run
  in a subagent, which cannot wait for an answer, yet the story skill asked
  about team, estimates, splits and cycles in three different steps, and the
  person filing first saw the stories in Jira, where each correction is an edit
  call. Each skill now builds everything, hands back once with the draft and
  every question numbered, each with the default an unanswered one takes, and
  re-runs the duplicate search before creating. A partial answer applies what
  was answered; it never starts a second round. The story skill also proposes
  an epic the conversation already mentioned, instead of asking cold, and
  files nothing until the user confirms it. Sprint, components and fix versions
  are asked only where the project has them, and left unset otherwise.
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

- **Passing a checkpoint is one command, with the engineer's direction in the log.**
  AI-DLC has no approval system: a checkpoint checks technical conditions, and
  when nothing is wrong the engineer's instruction to continue is enough.
  `gate --approve` no longer needs `--by` (it defaults to the git user name) and
  takes `--note "<the direction or decision>"`, written to the `gate-approve` log
  line. The header status of an HLA or TDD records the organisation's own review
  and no longer refuses a stage; the gate result reports it as `review`. Inputs
  that changed since the stage was produced are listed as `context` in the gate
  result and never refuse. Everything technical still refuses as before.

- **A step on someone else's Unit warns instead of refusing.** The owner guard
  stopped a step, `decide`, `jira` or `decision-id` on a Unit owned by another
  person unless `--takeover "<why>"` was given, which made the engineer argue with
  the tool. The command now runs, the result's `warnings` names the owner and the
  actor, and the log line says the same. `assign`, `next --mine` and the
  unowned-Unit problem are unchanged.

- **A failed build or test can no longer be stored as passed.** The Build and Test
  gate only checked that `test-results.md` existed, so a red run passed like a
  green one and the verdict sat in prose nobody read. A stage in `stages.json`
  may now name a `verdict` file; `build-and-test` names `test-results.md` and
  `code-generation` names the Unit's `code-summary.md`. The file must hold exactly
  one line `Verdict: pass`, `Verdict: fail` or `Verdict: not-run`. No such line is
  the finding `verdict-missing`; `fail` is `verdict-fail` and refuses whatever
  `--note` says (there is no override flag); `not-run` is `verdict-not-run` unless
  `--note` gives the reason, and the record then stores `"verdict": "not-run"`.
  `status` and `overview` show such a stage as not verified. The build-and-test
  and code-generation references tell the agent to write the line.

- **A passed Unit stage can be reopened.** Nothing could reopen a passed stage,
  and the warning for an edited artifact advised `gate --request-changes`, which
  was refused. `gate --request-changes --unit <u> --note "<why>"` now works on a
  passed Unit stage: the step becomes `changes-requested`, who and when it passed
  (and its verdict) are cleared and the note is logged. The Unit's later stages
  keep their records; `next --unit` returns to the reopened stage. Bolt-level
  stages stay closed to it, with a message that says why: change the document
  (the edit is logged) and the Units that rely on it are told. The warning for an
  edited artifact now says which of the two applies.

- **The seven AI-DLC skills teach what the scripts now do.** After six rounds of
  script changes the skill text still told a session to hand out approver names,
  `--channel`, `--parent`, `--kind frame` and `--takeover`, to expect three question
  rounds, and to write Build and Test under `docs/construction/` and Operation under
  `docs/operation/`. A session following it would have issued commands that no
  longer exist. The text now matches the scripts and teaches one operating model:
  one Bolt per initiative with one shared architecture, Slices added over time and
  Units inside them. The entry skill carries a table that maps plain requests
  ("Continue my Unit", "What is blocking this implementation?", "Plan the next
  Slice") to the commands a session runs, so an engineer never needs a flag. A
  stage ends in a checkpoint the session passes itself when nothing technical or
  material is open, asks once with a recommendation when a choice is open, and
  never passes a failed run. Questions follow what is open, with no quota. The
  HLA skill explains contributions, the merge into `hla.md` and the consistency
  review; Inception explains additive Slices and readiness; Construction explains
  the `Verdict:` line, `context` and per-Slice Build and Test; Operation works per
  Slice. The shared core rules were rewritten once and copied to all seven skills.
  The evaluation cases for removed behaviour were deleted and cases for the new
  behaviour were written; none has been run, so no `results.md` exists.

### Removed

- **Parent and child Bolts, and the frame kind of Bolt, are gone.** A Bolt is one
  initiative that holds its shared architecture, its Slices and its Units. Splitting
  a large piece of work into a frame Bolt and child Bolts made a concern-sized
  investigation cost a whole lifecycle. `aidlc_state.py` no longer has `open --parent`,
  `open --kind` or the `kind` command, `status`, `inputs`, `overview` and the workspace
  file no longer mention a parent or children, the five `parent:` inputs are gone from
  `stages.json`, and `validate_doc.py` no longer knows a `parent:D<n>` citation. An older
  `state.json` that still holds a `kind` or `parent` key loads as a normal Bolt and drops
  the keys at its next write. The framework number goes from 3 to 4, so an older copy of
  the skills refuses a Bolt written by this one.
- **Approval records are gone.** `gate --channel`, the `recorded_by` and
  `channel` fields, the refusal when `--by` names someone else, `open --approver`
  and the Bolt's `approver` key, the `signoff-*` findings and `--ack-context`
  with the `context-changed` finding are removed: they made a checkpoint look
  like an approval workflow while the engineer's own call is what matters. Old
  records that hold these fields load and lose them at the next write.
- **`--takeover` is gone** from `decide`, `step`, `jira` and `decision-id`: the
  owner guard no longer refuses, so there is nothing to take over.

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
