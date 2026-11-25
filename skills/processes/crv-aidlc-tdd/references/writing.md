# Writing, validating and refining the TDD

Used by the produce and refine steps. The answers are settled; this is about writing a design the delivery team can build from and the organisation's reviewers can assess.

## What to read

`tdd-decisions.md`, `tdd-questions.md` and its clarifications, the HLA's header, Digest and decisions table, and `assets/tdd-template.md`. Reopen other HLA sections only to cite them.

## Rules for every section

- Keep the template's headings, order and tables; remove the guidance comments.
- Write only what is new or more detailed than the HLA. Where the HLA already says it, cite it in one line (`HLA D6`, `HLA: Security and privacy`) instead of restating it.
- Every fact carries its source: a decision id, an answer id (`T-Q3`, `TC-Q1`), an ADR id, or a document path with lines. Mark anything not checked `unverified`.
- A section marked Optional in the template may hold only `Not applicable: <reason>`. Required sections cannot.
- Numbers have units and a measurement point. Performance targets give P50, P95 and P99 per operation.
- No `TODO`, `TBD` or `<...>` survives. An unknown value is a question for the owner.
- **Digest** last, at most 10 lines: what is built, why a TDD was required, the new decisions, what reviewers must check.

## Section notes

- **Detailed architecture:** a container view only if containers changed since the HLA (then reuse the HLA's diagram conventions and colours). At most two sequence diagrams, each followed by a paragraph that includes the failure path.
- **Release readiness** is before and during the release. **Post-release validation** is after it: each check has a who, a when, an expected result and the action if it fails. Do not repeat the release table there.
- **Risks and mitigations:** seen from the user's side, with an owning role and whether the risk blocks release.
- **AI input block:** each task is one story-sized piece of work naming its section and decision id; tasks follow dependency order. Every MUST cites a decision or ADR. Post-release checks are concrete requests or queries with the expected result.
- **Appendix:** fill the `Covered in` column for each attribute, or say why it does not matter here.

## Design decisions table

Same rule as the HLA: only departures from an accepted ADR, approaches new to the organisation, trade-offs that cost another team, and calls where reasonable architects would disagree. First column states the tension. `Id` holds the id from `tdd-decisions.md`, which must be higher than every id in the HLA and its record. Leave `Signed off by` empty: it is the reviewers' record. No qualifying row: mark the section not applicable with the reason.

Departing from an accepted ADR here also fills `exception_link` in the header and adds a row to Risks.

## Header

- `hla_link` is the HLA's path relative to the TDD (normally `hla.md`). `trigger` lists why the TDD exists. `review_conditions` copies the HLA conditions this TDD answers.
- `adr_links` lists ADRs relied on beyond those the HLA cites.
- Owner and reviewer names come from a person, never invented.
- `status: draft` while writing, `in-review` when handed over. The organisation's reviewers set `accepted`, `changes-requested` or `declined`, `signed_off_by` and `signed_off_on`; you never fill them to get past a checkpoint.

## Splitting into parts

When the questions chose a split: `tdd.md` keeps the header, overview, shared decisions, cross-part risks and the combined AI input block, and lists the parts. Each `tdd-<part>.md` is a full TDD with `part` set in its header; a section fully covered in `tdd.md` says `Not applicable: covered in tdd.md` where the template allows it. Validate every file.

## Validate

```bash
python3 scripts/validate_doc.py --file <bolt>/architecture/tdd.md --kind tdd \
  --adr-index <planning repo>/architecture-index.json
```

Fix every finding and rerun until exit 0. Report warnings to the owner. `hla-not-accepted` means the HLA header does not say accepted: report it and let the engineer decide.

## Refinement

1. List every section, header field and decision the change touches before editing.
2. If the change contradicts an HLA decision, stop: it goes to the HLA first.
3. Update the affected sections together; a significant change gets a new id from `aidlc_state.py decision-id`; old ids are never renumbered.
4. Raise `document_version`, validate, summarise the change in at most five lines.

## Review and the checkpoint

Set `status: in-review` and give the owner the path and the Digest. The organisation's reviewers record their outcome in the header themselves. The session runs the checkpoint as the core rules say; it never waits for the header and never edits it. A later change to `tdd.md` gets new decision ids, and `aidlc_state.py context --bolt <p> --id <D<n>>` names the Slices and Units that rely on a changed one.
