# Behaviour evals — crv-create-jira-epic

Each case: setup, prompt, and a contract of checkable assertions. Prefer
assertions a reader can verify by looking over judgements like "the output is
good" — a criterion that cannot fail is decoration.

Cases B2 to B5 are the no-silent-failure guards. Each one asserts that **nothing
was created**, because the characteristic failure of this skill is not an error
message — it is an epic that exists, looks fine, and is wrong.

## B1 — The main path

**Setup:** Atlassian MCP configured and authenticated. `jira_setup.py --check`
exits `0`. A project the user can see, with an Epic issue type.
**Prompt:** "Create a Jira epic for rejecting expired tokens at the ingest endpoint."

- [ ] Preflight runs before any content questions are asked.
- [ ] Missing template sections are asked for in one batch, not one at a time.
- [ ] Exactly one epic is created.
- [ ] Its description contains the five required headings from `assets/epic-description.md.template`, in template order.
- [ ] Optional headings with nothing under them are absent, not present and empty.
- [ ] No scope item, out-of-scope item, or success criterion the user supplied is dropped to shorten the description.
- [ ] **The create payload contains no Priority**, the stored Priority is the project default or empty and is reported as such, and the description contains no `Priority:` line and no `TBD`.
- [ ] The description renders as formatted markdown in Jira, not as literal `##` characters and not blank.
- [ ] The created epic is read back, and the report quotes the stored project and issue type rather than the intended ones.
- [ ] The report names the issue key, the browse URL, the project, and the issue type.
- [ ] The report points at `crv-create-jira-story` for the stories.
- [ ] No section of the description was invented — success criteria and dependencies not supplied by the user appear as "Not yet decided" or are asked about, never fabricated.

## B2 — Guard: MCP server absent

**Setup:** No Atlassian MCP server configured. `jira_setup.py --check` exits `0`.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The skill stops at preflight.
- [ ] It reports that the Jira tools are unavailable and points at `references/jira-setup.md`.
- [ ] **No epic is created, and no create call is attempted.**
- [ ] It does not gather epic content first and fail afterwards.

## B3 — Guard: machine not configured, and nothing to derive from

**Setup:** Atlassian MCP configured. No configuration file — `jira_setup.py --check`
exits `1`. Two sites are accessible. The prompt names no project.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The skill stops at preflight.
- [ ] The report names the missing keys and gives the exact `--set … --confirm` command.
- [ ] **No epic is created.**
- [ ] It does not guess a project key, and does not pick one from the visible-projects list on its own.
- [ ] It does not pick one of the two accessible sites.

## B4 — Guard: configuration file corrupt

**Setup:** The configuration file exists but contains invalid JSON —
`jira_setup.py --check` exits `4`.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The skill stops and names the configuration path.
- [ ] It distinguishes this from "never configured" — it does **not** tell the user to re-run `--set` as if nothing were recorded.
- [ ] **No epic is created.**

## B5 — Guard: a required field cannot be resolved

**Setup:** Everything configured. The target project marks a custom field
required on the Epic create screen that the user supplied no value for.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] Create-metadata is read before any create call.
- [ ] The skill stops and names the unresolved field, the project, and the issue type.
- [ ] It lists the field names that *are* available.
- [ ] **No epic is created without that field.**
- [ ] It does not create the epic and mention the gap afterwards.

## B6 — Guard: no duplicate on an ambiguous error

**Setup:** Everything configured. The first create call returns a timeout after
the issue was in fact created.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The skill searches for the summary before attempting any retry.
- [ ] **Exactly one epic exists afterwards.**
- [ ] The report states that the create call errored and what was found on re-check.

## B7 — Configuration derived from what the user supplied

**Setup:** Atlassian MCP configured and authenticated. `jira_setup.py --check`
exits `1`. The user's first message contains a board URL of the form
`https://acme.atlassian.net/jira/software/c/projects/ABC/boards/12`.
**Prompt:** "Create an epic for the ingest rewrite." (in the same message as the URL)

- [ ] The skill uses the site and project from the URL rather than stopping.
- [ ] It says where each value came from.
- [ ] It gives the `--set … --confirm` command that records them for next time.
- [ ] It does **not** treat a single accessible site plus no project key as sufficient: a project has to come from somewhere.

## B8 — The description carries no child count

**Setup:** Everything configured. The user describes an epic and mentions that
there will be "about 29 stories in phase 1".
**Prompt:** "Create the epic for this."

- [ ] The created description states no number of child stories.
- [ ] It does not list the stories either.
- [ ] The count is not smuggled into Scope or Technical notes as prose.

## B9 — Title and prose held to the house rule

**Setup:** Everything configured.
**Prompt:** "Create an epic: comprehensive enablement of robust, streamlined ingest capabilities across the platform — phase 1 of 3."

- [ ] The created summary is at most 80 characters and 12 words.
- [ ] It names the outcome rather than echoing the phrasing given.
- [ ] Neither summary nor description contains an em dash or an en dash.
- [ ] The summary carries no "phase 1 of 3" style numbering.
- [ ] None of "comprehensive", "robust", "streamlined", "enablement" or "capabilities" survives into the summary or the description.
- [ ] The rewritten title is shown in the report so the user can object to it.

## B10 — The tier is stated, not asked

**Setup:** Everything configured. Harness supports subagents.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The run states the tier in one line and continues.
- [ ] **No question about the tier is asked**, and no round trip is spent waiting for one.
- [ ] Repeat with "use the balanced tier" in the prompt: the stated tier is honoured and named in the report.

## B11 — The team field is asked, not defaulted

**Setup:** Everything configured. The Epic create screen carries
`Assigned Team(s)` with allowed values Platform, Empower, Insight, and a
recorded default of Platform exists.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The user is asked which team, in the same batch of questions as the missing template sections.
- [ ] The question lists the allowed values read from create-metadata and names the recorded default.
- [ ] The recorded default alone does not suppress the question.
- [ ] Answer "Empower": the epic carries Empower, confirmed by read-back.
- [ ] Answer "none": the field is unset, and the report says so as the user's choice.
- [ ] Answer with a value not in the list: it is **not** sent. The allowed values are listed and the question is asked again.

## B12 — Priority is never set

**Setup:** Everything configured. The Epic create screen offers Priority,
optional, defaulting to Medium, and `jira_setup.py --show` records a
`project_defaults` entry setting Priority to High.
**Prompt:** "Create a Jira epic for the ingest rewrite, high priority."

- [ ] Priority **is** set to High, because the user said so in the prompt. This is the one thing that makes a Priority legitimate: a person chose it.
- [ ] The value is validated against the project's allowed options before being sent, and reported as supplied rather than as a default.
- [ ] The recorded `project_defaults` Priority of High is **not** what was applied, and the report distinguishes the two even though the value happens to match.
- [ ] The description contains no `Priority:` line and no `TBD`, whatever the field holds.
- [ ] Then repeat with the priority removed from the prompt: **the create payload contains no Priority field**, the recorded default is ignored, and the report says it was ignored rather than applied.
- [ ] Then make Priority **required with no default** and no priority in the prompt: the skill stops and asks which value rather than choosing one. With the Medium default, the read-back holds Medium and that is a pass, reported as the project default.

## B13 — A subagent with no Atlassian tools

**Setup:** Harness supports subagents, and the spawned subagent is granted no
Atlassian MCP server. The main session has one, authenticated.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The run distinguishes this from a server that was never installed.
- [ ] It says the tools exist in the main session and that this is tool inheritance.
- [ ] It does **not** send the user to the setup reference.
- [ ] **No epic is created.**
- [ ] It hands back for an inline re-run, and the inline re-run completes normally and says it ran inline.

## B14 — Re-running must not file a second epic

**Setup:** Everything configured. The project already holds an epic, status
In Progress, whose summary is exactly the one the request produces.
**Prompt:** "Create a Jira epic for rejecting expired tokens at the ingest endpoint."

- [ ] A JQL search for an existing epic runs **before** any create call, not only after an error.
- [ ] **No epic is created.** The project still holds exactly one epic with that summary.
- [ ] The report names the existing key and its status, and says nothing was created.
- [ ] The existing epic is not modified.
- [ ] Then change the existing epic's summary to the same outcome in other words: the skill asks once whether it is the same epic, and creates nothing until answered.

## B15 — A wrong read-back is patched, not refiled

**Setup:** Everything configured. The create call succeeds, but the read-back
shows the team field empty although the user answered Empower.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The run does not report done.
- [ ] The epic is patched in place with the edit capability, and a second read-back shows Empower.
- [ ] No second epic is created, and nothing is deleted.
- [ ] Then run with a server that has no edit capability: preflight names it as missing before any content is gathered, and nothing is created.

## B16 — One hand-back, with the draft, before the epic exists

**Setup:** Everything configured. The request gives an outcome and a scope but
no success criteria, and the project has `Assigned Team(s)`, a Priority default
of TBD, and an existing epic whose summary is close to the new one.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] **Exactly one hand-back happens before the create call**, and no epic exists while it is open.
- [ ] It shows the summary and the full description as they would be filed.
- [ ] It asks, in one message, for the success criteria, the team, whether to set a Priority, and whether the close epic is the same one.
- [ ] Answer only the team: the epic is **not** created, because the near-match was not answered.
- [ ] Then answer "different epic" as well: it is created, success criteria read "Not yet decided", Priority holds the project default and the report says so.
- [ ] The duplicate search runs again after the answers and before the create call.
