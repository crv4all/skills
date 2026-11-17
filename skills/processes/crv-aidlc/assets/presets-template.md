# Presets

A preset is the organisation's default answer to a question that every paddock would otherwise be asked again, such as story format, acceptance-criteria style, unit granularity or who signs what. A stage does not ask a question a preset answers; it lists the preset under `## Already answered`.

Only people add presets, in this file, by pull request. A skill never writes or edits one. A paddock may override a preset for that paddock only, with a reason the approver gives; the override never changes this file.

Check the file with `lint_questions.py --presets docs/presets.md`.

## Format

One entry per preset, as a level-2 heading with the four fields below. Ids `P-n` are never renumbered or reused. `Applies to` is a list of stage ids from `stages.json`, separated by commas, or `all`. `Set by` ends in a date.

```
## P-1 <topic>
Applies to: <stage ids separated by commas, or all>
Answer: <the default, one or two lines>
Reason: <why this is the organisation's default>
Set by: <name>, <YYYY-MM-DD>
```

## Presets

No presets yet.
