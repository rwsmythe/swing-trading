# Phase 22 arc 22-A2 (PROOF MACHINERY) -- EXECUTING ledger

Plan: `2026-09-22-phase22-arc-a2-proof-machinery.md` (merged at `23313918`). Plan ledger: `...proof-machinery.ledger.md`. Branch `22-a2-exec`, base `05702929`.

## Gate table (depth read by the orchestrator from `scripts/cell_depth.py --live`; never a cell's self-estimate)

| gate | cell | after | last commit | depth | disposition |
|---|---|---|---|---|---|
| G1 | exec cell 1 (implementer-opus-high) | Task 3 (+ R4.0 edits, Tasks 1-2) | `010e8f9f` | 557,321 (OVER) | NOT resumed; fresh exec cell 2 dispatched off `010e8f9f` from Task 4. Cell 1's uncommitted Task-4 drafts (session scratchpad) are NOT carried; cell 2 writes Task 4 from the plan. |
| G-T4 | exec cell 2 (implementer-opus-high) | Task 4 | `cd02374b` | 208,150 | resumed. Orchestrator re-measured the P-correction: `9f315cc6:docs/rd-state.md` line 57 = 1015 bytes / **1005 chars** (plan section 4 + ledger R1.0 say 1006 -- a premise count error; sha256 + offsets unaffected; A2-37 asserts 1005). |
| G-T5 | exec cell 2 | Task 5 | `503e27b2` | 339,960 | NOT resumed (Task 5 cost ~130K; Task 6 would cross the cap mid-task). Fresh exec cell 3 from Task 6. |

## G1 record (orchestrator QA of cell 1's gate report, against disk)

- Commits `84f63a63` (R4.0 edits), `37bd7929` (Task 1), `a045835b` (Task 2), `010e8f9f` (Task 3); trailers empty on all four.
- Fixture diff `05702929..010e8f9f` on `tests/data/schema_manifest_head.tsv`: exactly four changed line pairs (header 38->39; table `provenance_corrections`; triggers `..._append_only_update`, `..._citation_graph`), zero other deletions -- F12 condition (4) as ruled.
- Cell 1 reports: tests/data + tests/trades + tests/cli green after one fix (the 0036 HEAD nullable-column roster); the 22-A mutation matrix (`test_22a_task11_citation_evidence.py`) green against the HEAD 0039 trigger (the latch_ladder byte-unchanged-semantics evidence); ruff clean. Full fast suite NOT yet run (G3).
- Cell 1's plan-vs-implementation notes 1-5 (frozen_value_evidence.py created at Task 3 holding only the version constant, for #11 same-commit; TIER2-PREDICATE markers on the four rung-9 predicates too; A2-28 gained `ticker_AMN_in_text`; the P34 classification (i)/(ii) to be recorded at Task 12; the 0039 SQL composed by an UNCOMMITTED scratch generator -- the generated SQL is the reviewed artifact) are carried to cell 2 verbatim via its dispatch.


## G-T5 record (orchestrator QA)

- **TDD DEVIATION, recorded:** Task 5's tests (A2-42..A2-60) were written AFTER the implementation (no red-first run). Cell 2's substitute: ten one-line mutations of the module, each failing exactly its targeted discriminator (A2-50 SQLite half-up; A2-45 `<=`; A2-46 local-offset date; A2-48 committer date; A2-52 substring ticker; A2-55 no year rule; A2-56 year rule on ISO; A2-57 no fire bracket; A2-44 no ancestry; A2-49 no pivot check). Accepted as evidence of discrimination, NOT as TDD; cell 3 is instructed red-first. Reviewer B is told to weigh it.
- **Encodings for Task 12's record (cell 2's notes 1-4):** A2-60 walks name-reference reachability, not an AST call walk (`_BLOB_MIRRORS` counts); a failed blob mirror refuses as `tier2_unverifiable` naming the predicate id (an added refusal class; `blob_unbuildable` for an absent epoch row / unparseable endpoint); UTC rendering = naive-UTC `isoformat()` + `Z`; A2-42 compares builder vs literal on `VERDICT_BEARING_KEYS` + constants, segments/prose covered by A2-43 on live values.
- **OPEN, routed to RD (F2.I is his):** `match_only` = [record_at, barrier_armed_at) goes NEGATIVE when the record is authored after the barrier was armed (a long-latched pre-barrier mandate). The plan is silent; the code computes it literally. Trade 25 is unaffected (1,977,720 s). Options per cell 2: clamp to zero, a distinct kind, or refuse.
- **For Task 7:** the correction service's dependency manifest names `_to_utc_naive` (`cohort_provenance_correction.py:258/287`); `frozen_value_evidence` imports it at call time -- the manifest may need a line.
