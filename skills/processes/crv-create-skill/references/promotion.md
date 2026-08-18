# draft → stable → deprecated

`maturity` is the promise the skill makes to people who are not its author. The
gates below are what makes the promise mean something.

## draft

Where every skill starts.

- Required metadata: `owner`, `layer`, `maturity`.
- Budget overruns **warn**. Authoring is never blocked by a budget before the
  content exists.
- `[TODO]` and `[ASK USER]` markers are allowed.
- Evals may be written but unrun, as long as `results.md` says so.

A draft is someone thinking out loud in public. It is installable, and users
should treat it as provisional.

## draft → stable

All of these, actually done:

- [ ] `version`, `tags`, and `review-cadence` present in `metadata`.
- [ ] `execution: subagent` and `model-tier: economy`, or a written reason in
      the Execution section for departing from either.
- [ ] Budgets pass as hard errors: `check_budgets.py` exits 0.
- [ ] `validate_frontmatter.py --strict` exits 0 — warnings included.
- [ ] Bundled scripts run under `/usr/bin/python3` (Python 3.9.6).
- [ ] Trigger evals **run in a fresh session**, with results and a date in
      `evals/results.md`.
- [ ] At least one behaviour eval run end to end.
- [ ] No `[TODO]` or `[ASK USER]` markers remain anywhere in the skill.
- [ ] Someone other than the author has completed a real task with it.
- [ ] `CATALOG.md` regenerated.

The last three are the ones that get skipped, and they are the ones that
matter. An unrun eval and an untested-by-anyone-else skill are the two most
common ways a `stable` label turns out to be a claim rather than a fact.

**Never record an eval result you did not produce.** A fabricated pass is worse
than a missing test, because it removes the reason to run the real one.

## stable

- Budget overruns **fail** the build. Other people depend on this now.
- Breaking changes bump the minor or major of `metadata.version` and are noted
  in `CHANGELOG.md`.
- The owner re-verifies at the stated `review-cadence`.

### Choosing review-cadence

From how fast the underlying facts move, not from how important the skill
feels.

| Cadence | For |
| --- | --- |
| `monthly` | Facts tied to a moving platform or an active migration |
| `quarterly` | Most organizational context |
| `semiannual` | Process skills whose steps rarely change |
| `annual` | Structural facts that change when someone decides to change them |

A cadence nobody honours is worse than a longer one that gets honoured: it
makes every stamp in the repository less believable.

## stable → deprecated

- [ ] The body **opens** with a deprecation notice naming the replacement.
- [ ] `metadata.maturity` set to `deprecated`; `version` bumped.
- [ ] `CHANGELOG.md` entry saying what replaces it.
- [ ] The replacement skill exists and is at least `draft`.

Deprecated skills stay shipped so that existing references resolve. Deleting a
skill breaks every document that links to it, and those links are how people
found it in the first place.

## When to delete instead

Delete only when the skill was wrong rather than superseded, and nothing links
to it. Record the deletion in `CHANGELOG.md`, and say so in the release notes:
anyone who installed it with `install.sh` still has a copy on disk, and nothing
will remove it for them.

## Demotion

`stable` → `draft` is legitimate and underused. If a skill's facts have gone
stale and nobody can re-verify them this week, demoting is more honest than
leaving a `stable` label on something nobody stands behind. Say so in
`CHANGELOG.md`.
