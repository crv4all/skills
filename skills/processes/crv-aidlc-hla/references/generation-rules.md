# Writing, validating and refining the HLA

Used to generate and refine `hla.md` from `hla-decisions.md`, the answers and the merged contributions, as a document reviewers can decide on.

## What to read

`hla-decisions.md`, the three question files (answers, `## Already answered`, `## Assumed`), `hla-clarifications.md`, the contributions that touch the section you are writing, and `assets/hla-template.md`. Open a knowledge or code-knowledge source only to cite it. Open a full ADR only when the document cites it and its index line is not enough.

## Section by section

Keep the template's headings, order and tables. Remove the guidance comments. Each layer feeds its sections:

| Layers | Sections |
| --- | --- |
| 1 | Business driver, problem and outcome; Scope |
| 2 | Conceptual design |
| 3 | Users, journeys and flows |
| 4 | Proposed architecture |
| 5 | Data and integration |
| 6 | Non-functional requirements |
| 7 | Security and privacy |
| 8 | Developer experience |
| 9 | Modernization plan |
| 10 | Architecture options considered |
| 11 | Risks and mitigation; header `decision_needed` |
| 12 | AI input block |
| all | Digest, Design decisions, Appendix, header |

- **Digest** last: at most 10 lines, because later stages and the gate read only this.
- A section marked Optional in the template may hold only `Not applicable: <reason>`. Required sections cannot. Modernization is required when `solution_type` is `modernization`.
- Every fact carries its source: a decision id, an answer id (`A-Q3`, `CL-Q2`), an ADR id, or a document path with lines. Anything not checked is marked `unverified`.
- In table cells with several items, put each on its own line with `<br/>`; never run them together with full stops.
- No `TODO`, `TBD` or `<...>` survives. If a value is unknown, the gap is a question for the owner, not a placeholder.

## Design decisions table

The table is for the organisation's reviewers, so it holds only decisions that need a reviewer's eye. A row qualifies when it is one of:

1. a departure from an accepted ADR, or reliance on a Proposed ADR that others would contest;
2. an approach new to the organisation;
3. a trade-off whose cost lands on another team, product or the compliance position;
4. a call where reasonable architects would disagree.

Routine choices that follow a pattern, ordinary engineering practice, and targets already stated in their own section stay out. The first column states the tension (for example "fresh data for operators versus load on the source system"), not the topic ("caching"). The `Id` column holds the decision id from `hla-decisions.md`. Leave `Signed off by` empty: it is the reviewers' record. If no row qualifies, mark the section not applicable and say so.

The record `hla-decisions.md` may add two optional columns after `Flag`: `Status` (`constraint`, `accepted`, `proposed`, `assumption`, `open`, `needs-evidence` or `superseded`) and `Owner`. Only a `constraint` binds later work: an `assumption` is never cited as one. A cross-team decision names its `Owner`. The checkpoint refuses any other Status word; a record without the columns stays valid.

## ADR rule

- Following an Accepted ADR is cited where it applies (a container's basis, a security row), never re-decided and never a row in the decisions table.
- Departing from an Accepted ADR is an exception, recorded in four places: header `exceptions` (`required: true`, `link_or_reason`), a Risks row, a `decision_needed` entry, and a Design decisions row.
- Using a Proposed ADR is a recorded decision in `hla-decisions.md`, flagged in the doc table only when it meets a criterion above.
- Superseded and Deprecated ADRs are never a basis. Find the successor, or record the gap as a risk.

## Header

Fill every field from the group C answers, the assumptions and `hla-decisions.md`; show any derived value's basis in the decision record. Rules that matter most:

- `security_consultation_required` is written only from an explicit answer or a named trigger. Never `false` by silence.
- Reviewer and owner names come from a person. If none was given, stop and ask; do not fill a name.
- `status: draft` while writing; `in-review` when handed to the organisation's reviewers. Those reviewers set `accepted`, `changes-requested` or `declined`, `signed_off_by` and `signed_off_on` in their own review; you never fill them to get past a checkpoint, and no stage waits for them.
- `document_version` is quoted. Raise the minor number for each review round.

## Diagrams

Plain Mermaid only; plugin syntaxes do not render everywhere.

- Context and container views: `flowchart LR`, a `subgraph` per boundary, data stores as cylinders `[("name")]`, people as `(["name"])`. Use the template's three `classDef` lines (person, internal, external) unchanged in every view, so the colours mean the same thing across documents.
- Flows: `sequenceDiagram`, one per flow, failure path included as an `alt` block when it matters.
- Data: `erDiagram` for new or changed entities only.
- Every diagram is followed by a paragraph saying what it shows. The validator rejects a diagram with no text after it.
- Label edges with what moves ("order events", "nightly file"), not with "uses".

## Validate

```bash
python3 scripts/validate_doc.py --file <bolt>/architecture/hla.md --kind hla \
  --adr-index <planning repo>/architecture-index.json
```

Fix every finding and run again until it exits 0. `--kind hla` also reads `hla-decisions.md` beside the document: a cited `D<n>` it does not declare, or a term or container with two owners, is a finding; a superseded decision cited or an interface party that is no container is a warning. Report warnings (also a non-accepted ADR, a stale index commit) rather than hiding them. What it cannot see is the consistency review in `SKILL.md`. Exit 3 or 4 means an input is missing or broken: report it, do not edit around it.

## Refinement

For any change asked after the document exists:

1. List every section, header field and decision the change touches, and show the list before editing.
2. Update them together in one pass; a change to a container usually touches flows, data, security, risks and the AI input block.
3. A significant change gets a new decision id (`aidlc_state.py decision-id`) and a row in `hla-decisions.md`; never renumber old ids. A superseded decision keeps its row, with Status `superseded`.
4. Re-derive `impact_flags`, `review_level`, `exceptions` and the consultation flag.
5. Raise `document_version`, validate, and summarise what changed in at most five lines.
6. For each decision touched, run `aidlc_state.py context --bolt <p> --id <D<n>>` and tell the engineer which Slices and Units rely on it. The HLA stage is not reopened.
