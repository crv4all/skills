# Third-party notices

## Current status

**Nothing in this repository is adapted from third-party code.** Every skill,
script, schema, and document here was written for it.

This file exists so that the first time that stops being true, there is an
obvious place to record it — and so its emptiness is a claim someone made
deliberately rather than a file nobody created.

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
| _(none yet)_ | | | | |

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
