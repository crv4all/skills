# Third-party notices

## Current status

One file is adapted, and it is recorded in the table below. Everything else
here, every skill, script, schema, and document, was written for this
repository.

## Prior art that informed the design

Ideas, not code. Reading a repository and deciding what to do differently is not
derivation, and none of the following contributed text, templates, or
implementation to this repository:

- [`github/awesome-copilot`](https://github.com/github/awesome-copilot)
- [`affaan-m/ECC`](https://github.com/affaan-m/ECC)
- [`mattpocock/skills`](https://github.com/mattpocock/skills)
- [`anthropics/skills`](https://github.com/anthropics/skills)

Anthropic's `docx`, `pdf`, `pptx`, and `xlsx` skills are proprietary and
prohibit derivative works. They are out of bounds entirely: not adapted, not
excerpted, not used as a template.

## If you adapt something

Two steps, both required.

1. A header at the top of the file:

   ```text
   Adapted from <url> (<license>, <copyright holder>)
   ```

2. An entry in the table below.

| File | Source | Licence | Copyright holder | What was adapted |
| --- | --- | --- | --- | --- |
| `skills/processes/crv-create-jira-epic/references/issue-writing.md` | [`blader/humanizer`](https://github.com/blader/humanizer) | MIT | Siqi Chen | The catalogue of patterns that mark generated text, under "Patterns that mark generated text": the pattern names, and the approach of naming them mechanically so they can be checked rather than felt. Every example was rewritten for Jira issues. The summary rules, the size caps, and the placeholder and Priority rules are ours. |
| `skills/processes/crv-create-jira-story/references/issue-writing.md` | [`blader/humanizer`](https://github.com/blader/humanizer) | MIT | Siqi Chen | A byte-identical copy of the file above. Both Jira skills ship their own copy so each installs standalone; `test_shared_jira_files.py` keeps them identical. |

Check the licence before adapting, not after. A permissive licence is not
permission to omit attribution, and some licences that look permissive are not.

## Dependencies

Repository tooling depends on third-party Python packages, resolved and pinned
in [`uv.lock`](uv.lock): `jsonschema`, `pyyaml`, `tiktoken`, and the development
group. Those are dependencies, not adapted code, and each carries its own
licence — inspect them with:

```bash
uv pip list
```

Skill-bundled scripts under `skills/**/scripts/` have **no** dependencies at
all. They are stdlib-only by policy, so a skill copied out of this repository
carries no third-party obligations with it.
