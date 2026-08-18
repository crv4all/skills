# Trigger evals — crv-codebase-onboarding

Run each prompt in a **fresh session** with the skill installed and no other
context. Observe whether the agent selects the skill before you say anything
else. A session where you have already mentioned the skill proves nothing.

Record results in `results.md` with the date. Never report a result you did not
produce.

## Should fire

| # | Prompt | Why |
| --- | --- | --- |
| T1 | "Get me up to speed on this repo." | The canonical request, in the words people actually use. |
| T2 | "I just joined this team. Where do I start with this codebase?" | Same intent, no shared vocabulary with the skill's description. |
| T3 | "Document how this system fits together so the next person doesn't have to work it out." | Names the deliverable without naming the skill. |
| T4 | "Our docs/codebase notes are from March. Are they still right?" | Should fire and detect `verify` mode. |
| T5 | "I need to make a big change to the billing service and I've never seen this repo before." | The pre-change case named in the description. |
| T6 | "What's the architecture here, and where does the data actually live?" | Two of the ten output files, asked for directly. |

## Should not fire

| # | Prompt | Why not | Should fire instead |
| --- | --- | --- | --- |
| N1 | "What does this function do?" | Single symbol, no deliverable. | nothing |
| N2 | "Write a README for this library." | Public-facing doc, different audience and content. | nothing |
| N3 | "Create a skill that captures our deployment runbook." | Skill authoring. | `crv-create-skill` |
| N4 | "Why is this test failing?" | Debugging. | nothing |
| N5 | "Refactor OrderService to use constructor injection." | A code change. | nothing |
| N6 | "Summarize the last 20 commits." | History, not structure. | nothing |

## Borderline

| # | Prompt | Correct answer | Reasoning |
| --- | --- | --- | --- |
| B1 | "Document the payment module." | Do not fire | Scoped to one module and to prose docs. Fire only if the user asks for the codebase context set, or names `docs/codebase/`. |
| B2 | "What tech stack does this use?" | Do not fire | One question with a short answer. The full ten-file process is disproportionate; answer directly. |
| B3 | "Onboard me to the payments service in this monorepo." | Fire, in `focus` mode | "Onboard" plus a named scope is exactly what `focus` exists for. |
| B4 | "Is our AGENTS.md still accurate?" | Fire, in `verify` mode | Checking whether existing agent context matches the code is squarely in scope. |
| B5 | "Write ADRs for the decisions in this codebase." | Do not fire | ADRs are decision records with authorship and status; this skill produces context, not decisions. |

## Reading a failure

- **A missed should-fire** usually means the description lacks the user's
  vocabulary. People say "get me up to speed", not "produce codebase context".
- **A false fire** usually means the description claims territory it does not
  own. Narrow it, or add an explicit exclusion to the last sentence.
- **B1 and B2 firing** would be the most likely real-world failure: both are
  adjacent, both are cheap to answer directly, and firing on them costs the
  user a ten-file process they did not ask for.
