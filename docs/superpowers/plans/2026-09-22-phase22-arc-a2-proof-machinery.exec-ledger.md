# Phase 22 arc 22-A2 (PROOF MACHINERY) -- EXECUTING ledger

Plan: `2026-09-22-phase22-arc-a2-proof-machinery.md` (merged at `23313918`). Plan ledger: `...proof-machinery.ledger.md`. Branch `22-a2-exec`, base `05702929`.

## Gate table (depth read by the orchestrator from `scripts/cell_depth.py --live`; never a cell's self-estimate)

| gate | cell | after | last commit | depth | disposition |
|---|---|---|---|---|---|
| G1 | exec cell 1 (implementer-opus-high) | Task 3 (+ R4.0 edits, Tasks 1-2) | `010e8f9f` | 557,321 (OVER) | NOT resumed; fresh exec cell 2 dispatched off `010e8f9f` from Task 4. Cell 1's uncommitted Task-4 drafts (session scratchpad) are NOT carried; cell 2 writes Task 4 from the plan. |
| G-T4 | exec cell 2 (implementer-opus-high) | Task 4 | `cd02374b` | 208,150 | resumed. Orchestrator re-measured the P-correction: `9f315cc6:docs/rd-state.md` line 57 = 1015 bytes / **1005 chars** (plan section 4 + ledger R1.0 say 1006 -- a premise count error; sha256 + offsets unaffected; A2-37 asserts 1005). |

## G1 record (orchestrator QA of cell 1's gate report, against disk)

- Commits `84f63a63` (R4.0 edits), `37bd7929` (Task 1), `a045835b` (Task 2), `010e8f9f` (Task 3); trailers empty on all four.
- Fixture diff `05702929..010e8f9f` on `tests/data/schema_manifest_head.tsv`: exactly four changed line pairs (header 38->39; table `provenance_corrections`; triggers `..._append_only_update`, `..._citation_graph`), zero other deletions -- F12 condition (4) as ruled.
- Cell 1 reports: tests/data + tests/trades + tests/cli green after one fix (the 0036 HEAD nullable-column roster); the 22-A mutation matrix (`test_22a_task11_citation_evidence.py`) green against the HEAD 0039 trigger (the latch_ladder byte-unchanged-semantics evidence); ruff clean. Full fast suite NOT yet run (G3).
- Cell 1's plan-vs-implementation notes 1-5 (frozen_value_evidence.py created at Task 3 holding only the version constant, for #11 same-commit; TIER2-PREDICATE markers on the four rung-9 predicates too; A2-28 gained `ticker_AMN_in_text`; the P34 classification (i)/(ii) to be recorded at Task 12; the 0039 SQL composed by an UNCOMMITTED scratch generator -- the generated SQL is the reviewed artifact) are carried to cell 2 verbatim via its dispatch.
