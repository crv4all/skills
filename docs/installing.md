# Installing CRV skills

Every path below installs the same files. Skills in this repository use only
the six specification fields, so there is no per-harness variant to pick.

> **Not published yet.** This repository is shared as a git checkout while the
> skills mature. There are no marketplace manifests and no public install URL,
> deliberately: distribution machinery written before anyone has installed a
> skill is machinery nobody has tested. Clone it, install from the clone, and
> tell us what broke.
>
> Harness directory conventions below were verified against each vendor's
> documentation on 2026-08-18. If a path stops working, check the linked docs
> and open a PR against this file.

## Quick start

```bash
git clone <this-repo> ~/src/agent-skills
cd ~/src/agent-skills
./install.sh --list
```

`--list` prints the available skills and writes nothing. Then:

```bash
# personal install, auto-detecting which harnesses you have
./install.sh --skill crv-codebase-onboarding

# project install, committed with the repository
./install.sh --all --target project --harness claude,cursor
```

`install.sh` is POSIX shell with no dependencies beyond `git`, and only for the
remote path. It always supports `--dry-run`, and refuses to overwrite a locally
modified skill without `--force`.

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
  Copilot accepts it as a project location. If you install to one place,
  install there.
- **Same-named skills are not merged.** Codex shows both and makes the user
  choose; Claude Code resolves by precedence, so a project skill silently
  shadows a personal one. Cursor ships a built-in skill named `create-skill`.

## Choosing the model a skill runs on

Every CRV skill delegates its work to a subagent and declares a model tier in
`metadata.model-tier`. Before it starts, it tells you which tier it will use and
offers to change it. See
[design-principles.md](design-principles.md#14-every-skill-runs-in-a-subagent-on-the-cheapest-adequate-model)
for the tier-to-model mapping and how to set a standing override.

## Manual installation

A skill is a directory. Copying it is a legitimate install.

```bash
mkdir -p ~/.claude/skills
cp -R skills/processes/crv-codebase-onboarding ~/.claude/skills/
```

Copy the whole skill directory, not just `SKILL.md`: `references/`, `scripts/`,
and `assets/` are referenced by relative path from the skill root, and a skill
missing them fails at the moment it is most useful.

Note the flattening. The `<layer>/` component is a CRV organizing convention;
harnesses take a skill's identity from the directory that directly contains
`SKILL.md`.

## Keeping skills current

`install.sh` re-run against the same target updates in place and reports which
skills changed. A skill you have edited locally is skipped with a warning
unless you pass `--force`, because a silent overwrite of a local fix is worse
than an out-of-date skill.

For project installs, commit the skill directory. That is what makes the same
context available to a colleague and to CI agents.

## Verifying an install

Start a fresh session and ask the agent to list its available skills. If a CRV
skill does not appear:

1. **Check the path.** The directory must contain `SKILL.md`, spelled exactly
   that way — the match is case-sensitive on Linux even where it works on macOS.
2. **Check the frontmatter parses.** Run
   `uv run standards/scripts/validate_frontmatter.py <path>` from a clone. A
   harness that cannot parse frontmatter usually skips the skill in silence.
3. **Check for a name collision.** Two skills with the same directory name in
   different scopes resolve by precedence, and the loser is invisible.
4. **Restart the session.** Most harnesses read skills at startup.
