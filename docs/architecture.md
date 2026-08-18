# Architecture

What is in this repository, how the pieces fit, and which parts are generated.

## Repository map

```text
agent-skills/
├── skills/                     # the product
│   ├── utilities/  knowledge/  patterns/  processes/
│   └── <layer>/crv-<name>/{SKILL.md,references/,scripts/,assets/,evals/}
├── standards/                  # the enforcement
│   ├── schemas/                # JSON Schema draft 2020-12
│   ├── configs/                # budgets.json, pymarkdown.json
│   ├── scripts/                # validators and the catalog generator
│   │   └── lib/                # discovery, frontmatter parsing, logging, exit codes
│   └── tests/                  # pytest over the validators and bundled scripts
├── docs/                       # how and why
├── tests/fixtures/             # synthetic repositories for behavioural tests
├── .claude-plugin/marketplace.json   # generated
├── .cursor-plugin/marketplace.json   # generated
├── CATALOG.md                        # generated
└── install.sh                        # dependency-free installer
```

## The three sources of truth

Everything else is derived from one of these.

1. **`SKILL.md` frontmatter** — the identity, ownership, and maturity of every
   skill. `CATALOG.md` and both marketplace manifests are generated from it.
2. **`standards/schemas/skill-frontmatter-v1.schema.json`** — what valid
   frontmatter is. The spec's six closed fields plus CRV governance.
3. **`standards/configs/budgets.json`** — what "too big" means. Itself
   schema-validated, so a typo fails loudly rather than disabling a check.

## Validation pipeline

Each stage is independently runnable, and CI runs all of them.

| Stage | Script | Fails on |
| --- | --- | --- |
| Layout | `validate_frontmatter.py` | A directory under `skills/` that is not a discoverable skill: wrong depth, `skill.md` in the wrong case, an unrecognized layer directory |
| Frontmatter | `validate_frontmatter.py` | Schema violations, non-spec fields, `name` ≠ directory, `metadata.layer` ≠ parent directory, dangling file references |
| Description quality | `validate_frontmatter.py` | Warnings only: too short, no trigger clause, self-referential opening |
| Budgets | `check_budgets.py` | `SKILL.md` over 500 lines / 25,000 chars / 5,000 tokens. Warns at `draft`, errors at `stable` |
| Drift | `build_catalog.py --check` | `CATALOG.md` or a marketplace manifest disagreeing with frontmatter |
| Secrets | `scan_secrets.py` | Credential-shaped strings anywhere in the tree |
| Unit tests | `pytest` | Validator regressions, bundled-script behaviour against fixtures |
| Lint | `ruff`, `pyright`, `pymarkdown` | Style, types, markdown structure |

### Why `additionalProperties: false`

The Agent Skills frontmatter field set is closed. We reject anything outside it
— including `version`, which authors reach for constantly and which belongs
inside `metadata`.

This is stricter than any single harness, on purpose. Harnesses disagree about
unknown keys: some ignore them, Claude Code rejects them when packaging. A
skill that passes only because one harness is lenient breaks silently on the
next, and "silently" means the skill simply never appears.

### Why the config has a schema

A budget config with a misspelled key does not error — it just stops enforcing
that budget, and nobody notices for six months. Validating the config against
`budgets-config-v1.schema.json` turns a silent hole into a failed build.

## Distribution

Three paths, all reading the same frontmatter.

**`install.sh`** — dependency-free POSIX shell. Clones or updates a cache,
then copies selected skills into the target harness's directory. Supports
`--dry-run`, and refuses to overwrite a modified skill without `--force`.

**Marketplace manifests** — `.claude-plugin/marketplace.json` and
`.cursor-plugin/marketplace.json`, both generated. Neither is hand-edited; CI
fails on drift.

**Convenience wrappers** — `gh skill` and `npx skills` work against this
repository because it is a public GitHub repo with a conventional layout. They
are documented in [installing.md](installing.md), and are not a dependency:
`install.sh` never needs them.

## Deliberate omissions

**No plugin-bundle level above the layers.** The plugin format supports
grouping skills into installable bundles. With one team and two skills, that is
a directory nobody reads and a manifest that drifts. Add it when a second team
needs its own ownership boundary — the layer directories are already the natural
seam to split on.

**No harness-specific skill variants.** Canonical skills use only the six spec
fields, so one copy loads everywhere. Differences between harnesses are absorbed
by `install.sh` and the generated manifests, not by forking skills.

**No runtime skill registry or server.** Skills are files in git. A registry
would add an availability dependency to an offline capability.

**No `version` in frontmatter, and no per-skill release artifacts.** The
distributable unit is the repository tag. `metadata.version` is informational,
telling a reader how much a skill has moved, not what to install.

## Why GitHub and not Azure DevOps

Every other CRV repository lives on Azure DevOps
(`dev.azure.com/crv4all`, projects `DevOps` and `Cloudforce Team Data`). This
one is on public GitHub, deliberately, for two reasons:

- **Azure DevOps scopes repositories per project.** A skills repository that
  serves the whole organization would have to sit inside one project's
  boundary and be granted outward, which is exactly backwards.
- **The tooling ecosystem is GitHub-shaped.** Marketplace manifests, `gh
  skill`, `npx skills`, and every harness's documented install path assume a
  public git URL that resolves without authentication.

The cost is that nothing confidential can ever land here. That constraint is
enforced by CI (`scan_secrets.py`) and stated in the `knowledge` layer
guidance: facts that cannot be public are referenced by URL, never copied.
