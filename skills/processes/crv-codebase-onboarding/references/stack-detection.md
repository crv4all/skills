# Stack detection

Signals per ecosystem, and — more usefully — what each signal *implies* that a
reader would otherwise have to infer.

`scan.py` finds the markers. This file is about interpretation, which is a
judgement and therefore not the scanner's job.

## The rule that governs `STACK.md`

`STACK.md` is **not a dependency inventory.** A list of libraries is available
from the manifest, adds nothing, and goes stale immediately.

Write only:

1. **Non-obvious facts** — a pinned version with a reason, an unusual
   combination, a library used for something other than its usual purpose.
2. **Divergences** — from the CRV default, from the framework's convention,
   from what the rest of the repository does.
3. **Consequences** — what a newcomer would get wrong without knowing.

"Uses Spring Boot" is not worth a line. "Spring Boot 2.7, which is past
end-of-life; the upgrade is blocked by `javax.*` imports in `common/`" is the
entire reason the file exists.

## Java / JVM

| Signal | Implies |
| --- | --- |
| `pom.xml` with `<modules>` | Multi-module Maven. Build order is declared; module boundaries are real. |
| `spring-boot-starter-parent` | Spring Boot manages versions. A version pinned in the POM anyway is a deliberate override — find out why. |
| `build.gradle.kts` | Kotlin DSL. Check `settings.gradle.kts` for the real project list. |
| `src/main/resources/application-*.yml` | Profile-based config. The profile set at deploy time decides behaviour. |
| `@SpringBootApplication` | Entry point, and the component-scan root. |
| `V<n>__*.sql` under a migration path | Flyway. Numbering is the ordering contract; never renumber. |
| `db.changelog-*.xml` | Liquibase. |
| `*IT.java`, failsafe plugin | Integration tests, separate lifecycle from surefire unit tests. |
| `javax.*` alongside `jakarta.*` | A half-finished Jakarta migration. Report it. |

## TypeScript / Node

| Signal | Implies |
| --- | --- |
| `nx.json` | Nx workspace. `project.json` per project; the dependency graph is explicit and the build is cached. |
| `turbo.json` | Turborepo. Pipeline declared centrally. |
| `pnpm-workspace.yaml` | pnpm workspaces. Strict node_modules — a package importing something it does not declare will fail here and pass under npm. |
| `workspaces` in `package.json` | npm or yarn workspaces. |
| `tsconfig.json` with `references` | TypeScript project references; build order matters. |
| `"type": "module"` | ESM. Mixed CJS/ESM is a real source of runtime failures. |
| Multiple lockfiles | A genuine problem. Report it — the CI lockfile is the one that counts. |
| `.nvmrc`, `engines` | The Node version is pinned; note where. |

## Python

| Signal | Implies |
| --- | --- |
| `pyproject.toml` with `[project]` | PEP 621. Look at `requires-python` for the real floor. |
| `[tool.poetry]` | Poetry. `poetry.lock` is authoritative. |
| `uv.lock` | uv. Fast, and a recent choice — note when it was adopted. |
| `requirements*.txt` only | Older or deliberately simple. Check whether versions are pinned. |
| `alembic.ini` | Alembic migrations; `versions/` holds the chain and it is linear. |
| `dbt_project.yml` | dbt. Models are SQL, the DAG is inferred from `ref()`; lineage is the architecture. |
| `conftest.py` | pytest, and the fixtures there apply to everything below. |
| `databricks.yml` | Databricks asset bundle: jobs and targets defined as code. |

## .NET

| Signal | Implies |
| --- | --- |
| `*.sln` | Solution grouping. Not always the deployment grouping. |
| `Directory.Build.props` | Shared MSBuild settings; check before believing a per-project setting. |
| `Program.cs` with top-level statements | .NET 6+ minimal hosting. |
| `appsettings.*.json` | Environment layering; the environment name selects the overlay. |
| `global.json` | The SDK version is pinned. |

## Go

| Signal | Implies |
| --- | --- |
| `go.mod` | Module root and Go version floor. |
| `cmd/<name>/main.go` | Standard layout; each `cmd` subdirectory is a binary. |
| `internal/` | Import-restricted by the compiler. A real boundary, not a convention. |

## Infrastructure and delivery

| Signal | Implies |
| --- | --- |
| `Dockerfile` | Check the base image and whether it is multi-stage. The final stage is what runs. |
| `docker-compose.yml` | Usually local development only. Do not present it as production. |
| `Chart.yaml` | Helm. `values.yaml` per environment is where the real configuration is. |
| `*.tf` | Terraform. Backend configuration says where state lives — that is who really owns the environment. |
| `*.bicep`, `azuredeploy.json` | Azure-native IaC. |
| `azure-pipelines.yml` | Azure Pipelines. Templates and variable groups often live outside the repository — note the gap. |
| `.github/workflows/` | GitHub Actions. |

At CRV, an Azure Pipelines definition referencing a variable group or template
repository you cannot see is common and expected. Report the reference and the
gap rather than describing the pipeline as if you had read all of it.

## Monorepo or polyrepo

Markers in subdirectories with none at the root usually means a monorepo. Check
for a workspace declaration (`nx.json`, `pnpm-workspace.yaml`, `<modules>`,
`*.sln`) before saying so — a repository can contain several unrelated projects
without being a monorepo, and the difference matters for how changes are built
and released.

## When nothing is recognized

Say so. List what *is* there — top-level directories, file extensions by count,
anything that looks like an entry point — and state plainly that the build
system was not identified. That is a useful, honest answer.

Guessing here is unusually damaging: a wrong stack claim in the first paragraph
of `STACK.md` gets quoted for months.
