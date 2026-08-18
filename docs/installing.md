# Installing CRV skills

Every path below installs the same files. Skills in this repository use only the
six specification fields, so there is no per-harness variant to pick.

Repository: `https://github.com/crv4all/agent-skills`

> Directory conventions below were verified against each vendor's documentation
> on 2026-08-18. Harnesses move quickly; if a path no longer works, check the
> vendor docs linked in each section and open a PR against this file.

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/crv4all/agent-skills/main/install.sh | sh -s -- --list
```

That prints the available skills and exits without writing anything. Then:

```bash
# personal install, auto-detecting which harnesses you have
./install.sh --skill crv-codebase-onboarding

# project install, committed with the repository
./install.sh --all --target project --harness claude,cursor
```

`install.sh` is POSIX shell with no dependencies beyond `git`, and it is the
only supported path that works identically everywhere. It always supports
`--dry-run`, and refuses to overwrite a locally modified skill without
`--force`.

Reading a script before piping it into a shell is a reasonable habit. It is a
short file.

## Where each harness looks

| Harness | Personal | Project | Reference |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills/<name>/SKILL.md` | `.claude/skills/<name>/SKILL.md` | [docs](https://code.claude.com/docs/en/skills) |
| Cursor | `~/.cursor/skills/`, `~/.agents/skills/` | `.cursor/skills/`, `.agents/skills/` | [docs](https://cursor.com/docs/skills) |
| GitHub Copilot | — | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | [docs](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) |
| VS Code (Copilot) | — | `.github/skills/` | [docs](https://code.visualstudio.com/docs/copilot/customization/agent-skills) |
| Codex | `$HOME/.agents/skills/` | `$CWD/.agents/skills/`, `$REPO_ROOT/.agents/skills/` | [docs](https://learn.chatgpt.com/docs/build-skills) |

Two things follow from that table, and they are why every CRV skill is prefixed
`crv-`:

- **`.agents/skills/` is the common ground.** Cursor and Codex both read it, and
  Copilot accepts it as a project location. If you install to one place, install
  there.
- **Same-named skills are not merged.** Codex shows both and makes the user
  choose; Claude Code resolves by precedence, so a project skill silently
  shadows a personal one. Cursor ships a built-in skill named `create-skill`.
  The prefix is what keeps our skills identifiable rather than ambiguous.

## Manual installation

A skill is a directory. Copying it is a legitimate install.

```bash
git clone https://github.com/crv4all/agent-skills.git /tmp/crv-agent-skills

mkdir -p ~/.claude/skills
cp -R /tmp/crv-agent-skills/skills/processes/crv-codebase-onboarding ~/.claude/skills/
```

Copy the whole skill directory, not just `SKILL.md`: `references/`, `scripts/`,
and `assets/` are referenced by relative path from the skill root, and a skill
missing them fails at the moment it is most useful.

Note the flattening. The `<layer>/` component of the source path is a CRV
organizing convention; harnesses do not use it, and Claude Code and Cursor take
the skill's identity from the directory that directly contains `SKILL.md`.

## Claude Code plugin marketplace

```text
/plugin marketplace add crv4all/agent-skills
/plugin install crv-agent-skills@crv-skills
```

`.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json` are generated
from frontmatter by `standards/scripts/build_catalog.py`; CI fails on drift. The
plugin manifest lists each skill directory explicitly in its `skills` array,
rather than relying on directory-walking, because plugin skill discovery is
documented as one level deep and our layout is two.

Plugin skills are namespaced: the skill is invoked as
`/crv-agent-skills:crv-codebase-onboarding`.

## Cursor plugin marketplace

Cursor reads `.cursor-plugin/marketplace.json` from a repository root and
`.cursor-plugin/plugin.json` from a plugin root. Both are generated here, with
the same explicit `skills` array. Add the marketplace from Cursor's **Customize**
page, or install the skills directly with `install.sh --harness cursor`.

## Convenience wrappers

`gh skill` and `npx skills` work against this repository because it is a public
GitHub repo with a conventional layout. They are conveniences, not dependencies:

```bash
npx skills add crv4all/agent-skills
```

Neither is required, and neither is tested in our CI. If one of them behaves
differently from `install.sh`, `install.sh` is the reference.

## Keeping skills current

`install.sh` re-run against the same target updates in place, and reports which
skills changed. A skill you have edited locally is skipped with a warning
unless you pass `--force`, because a silent overwrite of a local fix is worse
than an out-of-date skill.

For project installs, commit the skill directory. That is what makes the same
context available to a colleague, to CI agents, and to a cloud session that
never sees your home directory.

## Verifying an install

Start a fresh session and ask the agent to list its available skills. If a CRV
skill does not appear:

1. **Check the path.** The skill directory must contain `SKILL.md`, spelled
   exactly that way — the match is case-sensitive on Linux even where it works
   on macOS.
2. **Check the frontmatter parses.** Run
   `uv run standards/scripts/validate_frontmatter.py <path>` from a clone. A
   harness that cannot parse frontmatter usually skips the skill in silence.
3. **Check for a name collision.** Two skills with the same directory name in
   different scopes resolve by precedence, and the loser is invisible.
4. **Restart the session.** Most harnesses read skills at startup; Claude Code
   watches top-level skill directories for changes, but a directory that did
   not exist at startup is not watched.
