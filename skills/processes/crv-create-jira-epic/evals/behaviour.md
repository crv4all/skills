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
- [ ] Its description contains every heading from `assets/epic-description.md.template`, in template order.
- [ ] The description renders as formatted markdown in Jira, not as literal `##` characters and not blank.
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

## B3 — Guard: machine not configured

**Setup:** Atlassian MCP configured. No configuration file — `jira_setup.py --check` exits `1`.
**Prompt:** "Create a Jira epic for the ingest rewrite."

- [ ] The skill stops at preflight.
- [ ] The report names the missing keys and gives the exact `--set … --confirm` command.
- [ ] **No epic is created.**
- [ ] It does not guess a project key, and does not pick one from the visible-projects list on its own.

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
