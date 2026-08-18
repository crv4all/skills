# Design principles

Why this repository is shaped the way it is. Every section states a decision and
the reason behind it, so that a future change can argue with the reason rather
than rediscover it.

## 1. A skill is a context-window intervention, not documentation

The whole mechanism is: the agent sees `name` and `description` for every
installed skill at startup, and loads the rest only after deciding one is
relevant. That has three consequences we design around.

- **The description does all the selection work.** A skill with a perfect body
  and a vague description never runs. We validate description quality, not just
  length.
- **The body is charged to the user's task.** Everything in `SKILL.md` displaces
  something the agent could have been thinking about. Hence hard budgets
  (§6) rather than a style preference for brevity.
- **Detail that is consulted sometimes belongs in a file loaded sometimes.**
  That is what `references/` is for.

The corollary: write for an agent that is already competent. A skill exists to
correct what a capable agent would otherwise get *wrong* — CRV-specific facts,
non-obvious ordering, a deliverable contract. It does not exist to teach
programming.

## 2. Follow the specification exactly, and treat it as unversioned

The [Agent Skills specification](https://agentskills.io/specification) is a
living document with no version number. Six frontmatter fields exist, and the
set is closed: `name`, `description`, `license`, `compatibility`, `metadata`,
`allowed-tools`.

We enforce this with `additionalProperties: false`, which is stricter than any
single harness. The reason is portability. Harnesses disagree about unknown
keys — some ignore them, some warn, and Claude Code rejects unexpected
frontmatter keys when packaging. A skill that only works because a particular
harness is lenient is a skill that breaks silently on the next one.

Two consequences worth stating plainly, because both are common mistakes:

- **`version` is not a field.** It goes in `metadata`, quoted.
- **`metadata` values are strings.** `version: 1.0` is a YAML float and will
  fail validation. Quote it.

Because the spec is unversioned, re-verify it before changing the schema. Our
schema file is versioned (`skill-frontmatter-v1`) so that our own governance
rules can move without pretending the upstream spec did.

## 3. Vendor-neutral by construction

Baseline harnesses are Cursor, GitHub Copilot, and Claude Code, with Codex on a
best-effort basis. Canonical skills use only the six spec fields, so they load
everywhere without a per-harness variant.

Harness-specific frontmatter is forbidden in v1 — including
`disable-model-invocation`. If a skill should not be auto-selected, say so in
the description; that works in every harness and is visible to the reader.

Where harnesses differ in installation rather than format, we absorb the
difference in tooling (`install.sh`, generated marketplace manifests) rather
than in the skills themselves.

## 4. Four layers, and a skill that spans two gets split

`utilities` (cross-cutting tooling) · `knowledge` (reference and organizational
context) · `patterns` (how we build) · `processes` (what we deliver).

The layer is a signal for humans. Agents never see the path; they select on the
description alone. Layers exist so a reviewer can tell immediately whether a
change alters organizational fact, house style, or a shipped deliverable, and
apply the matching scrutiny.

A skill that does not fit one layer cleanly is doing two jobs. It will trigger
for the wrong requests and carry the wrong context for both of them. Split it,
and have the `processes` skill reference the `knowledge` skill.

There is no plugin-bundle level above the layers. Add one when a second team
needs its own ownership boundary — not before, because until then it is
structure with no reader. See [architecture.md](architecture.md).

## 5. Evidence before interpretation

Process skills separate *gathering* from *deciding*. A deterministic script
collects evidence and concludes nothing; a later phase interprets it.

This is not tidiness. An agent that reads a README and infers an architecture
produces something fluent and unfalsifiable. An agent that first collects file
paths, dependency declarations, and entry points, and *then* interprets them,
produces claims a reviewer can check — and notices when the README disagrees
with the code, which is where the useful findings are.

The same principle drives the requirement that generated context be stamped
with the commit it was verified against. Documentation without a verification
point cannot be distinguished from documentation that has quietly gone stale.

## 6. Budgets are enforced, and severity depends on maturity

500 lines, 25,000 characters, 5,000 tokens (`cl100k_base`) for `SKILL.md`; a
soft 400-line warning for files under `references/`. Configured in
`standards/configs/budgets.json`, which is itself schema-validated, so a typo
in a budget key fails loudly instead of silently disabling a check.

Warnings at `maturity: draft`; hard failure at `stable` or `deprecated`. A
draft is someone thinking out loud and should not be blocked by a budget before
the content exists. A stable skill is one other people depend on.

Token counts are a yardstick, not a measurement: no harness publishes its
production tokenizer. `cl100k_base` is stable, offline, and comparable across
our own skills over time, which is all a budget needs.

## 7. Two tiers of Python, for two different audiences

**Skill-bundled scripts** (`skills/**/scripts/`) are stdlib-only, carry a PEP
723 header with `requires-python = ">=3.9"`, use
`from __future__ import annotations`, and must run as a plain
`python3 script.py`. The floor is 3.9 because stock macOS ships 3.9.6, and a
skill that needs a working `uv` before it can do anything has replaced the
user's problem with an installation problem.

**Repo tooling** (`standards/`) uses `uv` with real dependencies —
`jsonschema`, `tiktoken`, `pyyaml`, `pytest`, `ruff`, `pyright`,
`pymarkdownlnt` — because it runs only in CI and on contributor machines.

## 8. Scripts an agent invokes obey a fixed contract

Every Python script in this repository, in both tiers:

| Rule | Why |
| --- | --- |
| Structured JSON on stdout via `sys.stdout.write()` | The caller parses it. One stray `print` of a progress message makes the output unparseable. |
| Every diagnostic on stderr via `logging` | Keeps stdout a clean channel. `print` is banned by lint, with no exceptions to reason about. |
| Never prompt for input | An agent shell has no one at the keyboard. A prompt is an infinite hang, and the agent cannot tell it apart from slow work. |
| `--help` covering flags, examples, and exit codes | It is the only documentation available at the moment of use. |
| Distinct exit code per failure class | Lets a caller distinguish "the repo is wrong" from "the script is broken". Collapsing them hides broken validators. |
| Actionable error messages | Name the file, the line, and the fix. |
| Idempotent | Re-running after a partial failure must be safe, because the agent will re-run. |
| `--dry-run` plus explicit `--confirm` for destructive work | The agent should be able to show its plan before it acts. |
| `--output` or pagination for large output | Prevents a multi-megabyte payload from evicting the context it was meant to inform. |
| `pathlib`, not `os.path` | Consistency, and correct behaviour on Windows checkouts. |

Shared exit codes live in `standards/scripts/lib/cli.py`:
`0` ok · `1` findings · `2` usage · `3` missing input · `4` malformed input ·
`5` internal error.

## 9. Enterprise-safe by default

Skill scripts that inspect a repository must be safe to point at any CRV
codebase without asking permission first:

- **No network access.**
- **No execution of project scripts.** Reading `package.json` is evidence;
  running `npm run build` is a side effect on someone else's machine.
- **No secret values in output.** Detecting that `DATABASE_PASSWORD` is
  required is useful; printing it is a disclosure.
- **No modification of source.** Generated output goes to its own directory.

This repository is public, which raises the stakes on the third point.
`standards/scripts/scan_secrets.py` runs in CI, and reports redacted
fingerprints rather than matched values — a CI log is itself a place secrets
leak from.

## 10. Never claim a step ran that did not run

If a validation was skipped, the skill or script says which one and why. An
agent that reports "validated" without validating destroys the value of every
other check in the repository, because a reader can no longer distinguish a
real pass from a claimed one.

The same rule covers evals: a skill must not report an eval result it did not
produce.

## 11. Two markers, and they are the only two

`[TODO]` for work the author knows is outstanding. `[ASK USER]` for a decision
that is genuinely the user's and cannot be resolved from the code, the docs, or
the repository. Nothing else — a proliferation of markers means none of them
get searched for.

Neither marker may survive into a skill at `maturity: stable`.

## 12. Generated files are generated, and drift fails the build

`CATALOG.md` is produced from frontmatter by
`standards/scripts/build_catalog.py`. CI runs it with `--check`. A hand-edit
that disagrees with the source of truth fails, rather than quietly becoming the
version people read.

Nothing else is generated, and nothing is published. Marketplace manifests are
cheap to add and premature to add: they would describe skills nobody has
installed yet. Share the checkout, install with `install.sh`, and add a
distribution channel when `install.sh` stops being enough.

## 13. Every skill runs in a subagent, on the cheapest adequate model

Two mandatory defaults, declared in metadata and enforced by
`validate_frontmatter.py`:

```yaml
metadata:
  execution: subagent
  model-tier: economy
```

**Subagent, not the main session.** Skill work reads a lot of files and
produces a lot of intermediate reasoning. In the main session all of that stays
in the conversation the user has to keep using afterwards, degrading every turn
that follows. A subagent exits when it is done and hands back the conclusion.

**Economy tier by default.** Most skill work is following an explicit
procedure, not solving a hard problem — that is the whole point of writing the
procedure down. Running it on a frontier model spends the budget on capability
the skill was designed not to need. Escalation is available, and the validator
warns when a skill declares a higher tier so the reason has to be written down.

**Tiers, not model ids.** A tier is harness-neutral and survives a vendor
renaming a model, which they do often. Model ids in fifty SKILL.md files is
fifty files to update.

| Tier | Meaning | Claude Code | Other harnesses |
| --- | --- | --- | --- |
| `economy` | Cheapest model that can follow instructions and call tools | Haiku 4.5 | The cheapest model the harness offers |
| `balanced` | Real judgement needed, not just procedure | Sonnet 5 | The harness default |
| `frontier` | Hardest reasoning, and the skill says why | Opus 5 | The most capable model available |

**Asked once, at the start.** Before spawning, the skill states the tier and
offers to change it. One prompt per invocation, before any work happens — not
a per-step interruption, and not a silent choice made on the user's behalf.

The question is skipped when the user has already stated a preference in the
session or in the project's agent configuration, which is how a standing
override works: say it once, or put it in `AGENTS.md`.

**Never silently escalate.** A subagent that turns out to be out of its depth
stops and says so. Re-running on a bigger model without asking charges twice
and hides the signal that the cheap tier was not enough — which is the most
useful thing the run produced.

## 14. Attribution is deliberate

The design was informed by prior art. The code is ours. We do not copy code,
templates, or wording from `github/awesome-copilot`, `affaan-m/ECC`,
`mattpocock/skills`, or `anthropics/skills`. Anthropic's `docx`, `pdf`, `pptx`,
and `xlsx` skills are proprietary and prohibit derivative works; they are out
of bounds entirely.

If anything is ever adapted, it carries a file header
`Adapted from <url> (<license>, <copyright holder>)` and an entry in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
