# Trigger evals — crv-create-skill

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. Record results in `results.md` with a date.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "I want to create a skill for our dbt conventions." | The direct request. |
| T2 | "We keep pasting the same review checklist into chat. Can we make that reusable?" | The real trigger, described without the word "skill". |
| T3 | "Review this SKILL.md before I open a PR." | Improving an existing skill is in scope. |
| T4 | "This skill never fires when I expect it to." | A description problem, which is squarely this skill's territory. |
| T5 | "Should our deployment runbook be a skill or just a doc?" | The boundary test, asked directly. |
| T6 | "Split crv-data-platform — it's doing two things." | Splitting is a named part of the process. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "Use the onboarding skill on this repo." | Invoking a skill, not authoring one. | `crv-codebase-onboarding` |
| N2 | "Get me up to speed on this codebase." | Codebase context. | `crv-codebase-onboarding` |
| N3 | "Write a Python script that validates YAML." | Ordinary coding. | nothing |
| N4 | "What skills do I have installed?" | A harness question. | nothing |
| N5 | "Add a section to our CONTRIBUTING.md." | Repository documentation. | nothing |
| N6 | "Create a new microservice from our template." | "Create" plus a template, unrelated domain. | nothing |

N6 is the useful one: it shares the verb and the word "template" with this
skill's vocabulary and shares nothing else. If the description is too generic
about "creating things from templates", this fires.

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "Write instructions for the agent about this repo." | Do not fire | That is `AGENTS.md`, which is exactly what the boundary test recommends *instead* of a skill. Answer directly, and mention the distinction. |
| B2 | "Turn our code review checklist into something Copilot can use." | Fire | Names a harness and a reusable artifact; this is a skill request in different words. |
| B3 | "Why isn't my SKILL.md loading?" | Fire | Frontmatter and layout diagnosis is inside the validation step. |
| B4 | "Add a section to the crv-codebase-onboarding skill." | Fire | Modifying an existing skill, including its budgets and validation. |
| B5 | "Make a Claude Code slash command for deploying." | Fire, with a caveat | Custom commands are skills in Claude Code, but the answer must flag that a harness-specific command is not a portable skill. |
