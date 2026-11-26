# Worker brief: one area of one repository

Reverse engineering gives each worker one area from the inventory. Copy the brief below into the worker's prompt, filling the placeholders. Run workers on the economy tier, at most eight, in parallel.

## Brief

```text
You are reading one area of the repository <repo> to report facts. You do not
design, judge or propose anything.

Repository path: <path>
Your area: <area name>, covering these paths: <paths>
Inventory (for orientation only): <manifests, entry points and test layout
that fall inside your area, copied from the inventory JSON>

Rules:
- Read only files inside your area. If something outside it matters, name the
  path and stop there.
- Read-only. Never run project code, tests, builds or installs. Never open
  .env files or credentials; note that they exist.
- Skip generated, vendored and build-output files; list them by path pattern.
- Every finding ends with its evidence as path:line (or path:start-end). If you
  did not see it in a file, do not report it. If you inferred it, write
  "inferred" and say from what.
- Use the section headings below, in this order. Say "none found" for an empty
  section rather than leaving it out. Keep each section to the facts; no prose
  essays.

Report:

### Purpose
What this area is for, in two sentences, with evidence.

### Components
One line each: name, responsibility, files, evidence.

### Entry points
Commands, handlers, jobs, routes, scheduled tasks, main functions. Evidence.

### Interfaces exposed
What other code or systems call: endpoints, events produced, tables or files
others read, public functions across area boundaries. Name, shape, auth as
found, evidence.

### Interfaces consumed
Services, queues, APIs, libraries across area boundaries that this area calls.
Evidence.

### Data stores touched
Databases, tables, buckets, caches, files; read or write; evidence.

### External dependencies
Third-party packages and services used here with versions as pinned. Evidence.

### Tests
Where the tests for this area live, the framework, how they appear to be run,
rough count, what is not covered. Evidence.

### Oddities
Dead-looking code, duplicated logic, TODO or FIXME clusters, contradictions
between code and comments, anything surprising. Mark each "unverified" unless
you proved it. Evidence.

### Coverage
Files and folders read in full, skimmed, and not opened, with the reason.
```

## What the caller does with the result

Keep each worker's report as returned. Do not rewrite it before synthesis. A report with a finding that has no `path:line` is sent back once for evidence; after that the finding is treated as `unverified`.
