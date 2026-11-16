# Writing, validating, refining and signing off the HLA

Used by the generate, refine and sign-off steps. The rounds are settled; this is about turning `hla-decisions.md` and the answers into a document reviewers can decide on.

## What to read

`hla-decisions.md`, the three round files (answers and `## Already answered`), `hla-clarifications.md`, and `assets/hla-template.md`. Open a knowledge or code-knowledge source only to cite it. Open a full ADR only when the document cites it and its index line is not enough.

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

The table is for reviewers to sign, so it holds only decisions that need a reviewer's eye. A row qualifies when it is one of:

1. a departure from an accepted ADR, or reliance on a Proposed ADR that others would contest;
2. an approach new to the organisation;
3. a trade-off whose cost lands on another team, product or the compliance position;
4. a call where reasonable architects would disagree.

Routine choices that follow a pattern, ordinary engineering practice, and targets already stated in their own section stay out. The first column states the tension (for example "fresh data for operators versus load on the source system"), not the topic ("caching"). The `Id` column holds the decision id from `hla-decisions.md`. Leave `Signed off by` empty. If no row qualifies, mark the section not applicable and say so.

## ADR rule

- Following an Accepted ADR is cited where it applies (a container's basis, a security row), never re-decided and never a row in the decisions table.
- Departing from an Accepted ADR is an exception, recorded in four places: header `exceptions` (`required: true`, `link_or_reason`), a Risks row, a `decision_needed` entry, and a Design decisions row.
- Using a Proposed ADR is a recorded decision in `hla-decisions.md`, flagged in the doc table only when it meets a criterion above.
- Superseded and Deprecated ADRs are never a basis. Find the successor, or record the gap as a risk.

## Header

Fill every field from the round C answers and `hla-decisions.md`; show any derived value's basis in the decision record. Rules that matter most:

- `security_consultation_required` is written only from an explicit answer or a named trigger. Never `false` by silence.
- Reviewer and owner names come from a person. If none was given, stop and ask; do not fill a name.
- `status: draft` while writing; `in-review` when handed to reviewers. Never set `accepted`, `changes-requested` or `declined`, and never fill `signed_off_by` or `signed_off_on`.
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
python3 scripts/validate_doc.py --file <paddock>/architecture/hla.md --kind hla \
  --adr-index <planning repo>/architecture-index.json
```

Fix every finding and run again until it exits 0. Report warnings (a non-accepted ADR cited, a stale index commit) to the owner rather than hiding them. Exit 3 or 4 means an input is missing or broken: report it, do not edit around it.

## Refinement

For any change asked after the document exists:

1. List every section, header field and decision the change touches, and show the list before editing.
2. Update them together in one pass; a change to a container usually touches flows, data, security, risks and the AI input block.
3. A significant change gets a new decision id (`aidlc_state.py decision-id`) and a row in `hla-decisions.md`; never renumber old ids.
4. Re-derive `impact_flags`, `review_level`, `exceptions` and the consultation flag.
5. Raise `document_version`, validate, and summarise what changed in at most five lines.

If the stage was already approved, follow the core rules for changes after approval: the later artifacts that depend on the HLA are listed and re-opened.

## Sign-off

The decision is recorded in the file by people, then mirrored into paddock state by the script.

1. Set `status: in-review` and give the owner the path, the Digest and the `decision_needed` list.
2. A reviewer edits the header: `status` to `accepted`, `changes-requested` or `declined`; `signed_off_by`; `signed_off_on`; any `review_conditions` (a TDD request goes there). The `Signed off by` cells in the decisions table are theirs too.
3. Validate again.
4. Accepted: `aidlc_state.py gate --stage hla --approve --by "<signed_off_by>"`. The gate refuses unless the header says `accepted` and is signed.
5. Changes requested: `gate --request-changes --note "<the requests>"`, then refine. Declined: the same with the reason, and tell the owner the paddock needs a new direction.
