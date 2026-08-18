# Test fixtures

Five synthetic repositories used by `standards/tests/` and by the behaviour
evals in each skill's `evals/` directory.

They are deliberately small and deliberately **imperfect**. Each contains at
least one trap, because a skill that reports a clean, confident picture of these
is a skill that is not looking:

| Fixture | Exercises | Traps planted |
| --- | --- | --- |
| `java-spring-maven` | Multi-module Maven, Spring Boot, Flyway, Kafka | README describes a module layout the code no longer has; secret-shaped environment variable; a dependency declared and never used |
| `typescript-nx-monorepo` | Nx workspace, pnpm, multiple apps and libs | Two lockfiles; a library imported without being declared |
| `python-dbt-databricks` | dbt project, Databricks bundle, Python packaging | A dbt model referencing a source that is not declared |
| `terraform-azure` | Terraform modules, Azure Pipelines, environment layering | Pipeline references a variable group defined outside the repository |
| `minimal-unknown` | Almost no signal | Nothing to find. The correct output is to say so. |

`minimal-unknown` is the most informative of the five. The correct behaviour on
a repository with no signal is to report that plainly — not to produce ten
confident files about a project it cannot see.

## Rules for fixtures

- **No real secrets.** Every credential-shaped string is a variable reference
  (`${VAR}`) or an obvious placeholder. CI runs `scan_secrets.py` over this
  tree like any other.
- **No real CRV data.** Domain vocabulary is fine and useful; farmer, herd, and
  animal records are not.
- **Small.** A fixture exists to exercise one behaviour, not to be realistic.
- **Traps are documented here.** A trap nobody recorded becomes a bug report.
