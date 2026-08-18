# Jira prerequisites and first-run setup

Two things must be true before either Jira skill can file anything: the agent
can reach an Atlassian MCP server, and this machine has recorded which site and
project to file into. They fail differently and are fixed differently, so check
them separately.

## 1. The Atlassian MCP server

Authentication lives here and nowhere else. The skills never read a Jira API
token, never accept one as an argument, and never store one — a token on disk
beside the skill would be a second copy to leak, and it would go stale
independently of the one the harness already manages.

Enable the server for the harness in use:

| Harness | Where |
| --- | --- |
| Claude Code | `claude mcp add` for the Atlassian server, or an `mcpServers` entry in `.mcp.json` / `~/.claude.json` |
| Cursor | Settings → MCP, or an `mcpServers` entry in `.cursor/mcp.json` |
| GitHub Copilot | An `mcp` entry in `.vscode/mcp.json` |

Atlassian publishes a hosted MCP endpoint that authenticates through the browser
on first use. Whichever server you configure, complete its OAuth flow once
before invoking a skill: an agent cannot complete a browser consent screen, so a
half-authorised server looks to the skill exactly like a missing one.

### Capabilities the skills need

Tool names vary between MCP server implementations and versions. Do not assume
a name — **enumerate the tools actually available and match on capability**. The
names in the right column are the ones Atlassian's own server uses today and are
the first thing to look for.

| Capability | Needed by | Commonly named |
| --- | --- | --- |
| Create an issue | both | `createJiraIssue` |
| Read an issue | story | `getJiraIssue` |
| List visible projects | both | `getVisibleJiraProjects` |
| Read project create-metadata | both | `getJiraProjectIssueTypesMetadata` |
| Search by JQL | story | `searchJiraIssuesUsingJql` |

If the create-metadata capability is genuinely absent, say so and stop. Guessing
field identifiers is the failure mode both skills exist to prevent, and a tenant
where they cannot be read is a tenant where these skills cannot run correctly.

## 2. Machine configuration

Run the bundled script. It records the site and the default project key in the
user configuration directory — outside any repository, so nothing tenant-specific
can reach version control by accident:

```bash
python3 scripts/jira_setup.py --check
```

Exit `0` means configured. Exit `1` means absent or incomplete, and the JSON on
stdout names exactly which keys are missing. To record them:

```bash
python3 scripts/jira_setup.py --set --site https://YOUR-SITE.atlassian.net --project ABC
```

That prints the plan and writes nothing. Re-run with `--confirm` to write. The
file lands at `${XDG_CONFIG_HOME:-$HOME/.config}/crv-agent-skills/jira.json` with
mode `0600`.

| Key | Required | Notes |
| --- | --- | --- |
| `site` | yes | `https://<name>.atlassian.net`, no path, no trailing slash |
| `project_key` | yes | Default project. A caller may override it per invocation. |
| `cloud_id` | no | Only if the MCP server asks for one it cannot resolve itself |

`cloud_id` is optional on purpose. Most servers resolve it from the site, and
requiring it up front would block setup on a value most people cannot find
without an admin.

### Exit codes

Distinct per failure class, so a caller can branch without reading prose.

| Code | Meaning |
| --- | --- |
| 0 | Configuration complete, or a write succeeded |
| 1 | Configuration absent or incomplete — run `--set` |
| 2 | Usage error, including any attempt to pass a credential |
| 3 | `--show` with no configuration recorded |
| 4 | The configuration file exists but is not valid JSON |
| 5 | Internal error, including an unwritable configuration directory |

Code `4` is deliberately not folded into `1`. "Never set up" and "set up, then
corrupted" have different remedies, and a script that reports them identically
sends someone to re-run setup when they should be reading the file.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| No Jira tools in the tool list | Server not configured, or the harness was not restarted | Configure it, restart the harness, re-check |
| Every call returns unauthorised | OAuth never completed, or the grant expired | Re-run the server authentication flow in a browser |
| `--check` exits `1` | Nothing recorded yet | Run `--set … --confirm` |
| `--check` exits `4` | Configuration file hand-edited into invalid JSON | Inspect the path in the error, fix or delete it, re-run `--set` |
| Project key rejected as invalid | A project *name* was passed instead of its key | Use the key — the `ABC` in `ABC-123` |
| Create fails on an unknown field | The project requires a field the input does not supply | Read the create-metadata error; it names the field |
