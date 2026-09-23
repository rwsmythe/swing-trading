# 22-B executing ledger — Demand A, `unintended_execution`

**Plan:** `docs/superpowers/plans/2026-09-23-phase22-arc-b-unintended-execution.md` (converged `351b2e60`; post-convergence encodings at `f5fc0568`). **Plan ledger:** beside it (`…ledger.md`, rulings R0.A–R0.K-RULING, RD-PLAN-READ, CHARC-S3, EXEC-ENCODE). **Branch:** `22-b-exec` off `22-b-plan` @ `e61dad27` (contains `57187164`). **Evidence:** `~/swing-data/review-transcripts/22-b-exec/`. **Brief of record:** `docs/phase22-arc-b-commissioning-brief.md` @ `8ae82947`.

The depth column is the ORCHESTRATOR's, read with `scripts/cell_depth.py --live`; a cell cannot see its own depth.

## Gate table

| gate | cell | last commit | tasks | suite | depth at return | disposition |
|---|---|---|---|---|---|---|
| G1 | cell 1 (implementer-opus-high) | `cd5945b5` | encode (`f5fc0568`), 1, 2, 2A, 3, 4 | not full; `tests/data` + seam/pin/closure 2151 passed after Tasks 3 and 4 | **648,799 (OVER the 400K cap)** | Cell RETIRED, not resumed; Tasks 5+ go to a fresh cell 2 off the commits. The orchestrator re-derived the v39→v40 diff independently (`run_migrations` to 39 and 40 in memory, `sqlite_master` compared): missing = none, changed = {table `trades`}, added = 18 objects (the attestation table + its autoindex, 9 `trg_eia_*`, 4 `trg_lve_*`, 3 `trg_trades_entry_intent_*`). That is exactly CHARC-S3.2's D51 expectation. Trailers across `e61dad27..cd5945b5`: empty. Tree clean. |

## G1 notes carried forward (from cell 1's gate report)

- **Ruling-fact differences, encoded as measured; posted to CHARC (the ruler for all four):**
  - (a) R0.J-RULING (iii): "the foreign-object set naming trades is EQUAL at v39 and v40" is false by construction, because 0040's own `trg_eia_*` triggers read `trades`. b22_44 asserts the v39 members byte-identical plus the named difference {`trg_eia_trade_binding`, `cited_fields`, `audit_trail`, `tier2`}.
  - (b) CHARC-S3.2: the `entry_intent_attestations` census is 2 rows by the textual method. They are the UPDATE twin (a real reference) and the N4 trigger (a hit on its RAISE message text only); the INSERT twin does not name the table. Recorded as measured in the 0040 header; the v40 `trades` census is 5 rows.
  - (c) R0.I: "a HEAD run under 22-B fires TWO gates" is false. `run_migrations` evaluates gates once, on the starting version, so 38→40 fires only `22a2`. "Four changed pairs" executes as 3 object pairs plus the header.
  - (d) An execution-level completion that needs CHARC to confirm or strike: `trg_lve_no_replace` carries the 0037 PK clause `(NEW.view_event_id != -1 AND view_event_id = NEW.view_event_id)` (the `trg_loml_no_replace` shape it was ruled to copy), and the 0037 `_NO_REPLACE_PK` roster now carries `trg_lve_no_replace` and `trg_eia_no_replace`.
- (e) `trg_eia_tier2` / `trg_eia_structural` WHENs are written `NOT COALESCE(NEW.admission_tier IS NOT '<tier>' OR (<pred>), 0)`, the ruled total form.
- (f) The version sweep also moved four non-`== 39` mirror pins: 0027's `ENTRY_INTENTS` test, the no_schema_change ceiling (39→40), the manifest object count (163→181), and the 0037 no-replace roster. The `_migrate_to_head` helper in the 0039 test file asserted `== 39` and was bumped to 40; it is a helper, not a pinned case.
- **Task 0 baseline.** The first base-suite run is VOID: the cell edited the tree while it ran (164 reds). The re-run on a `git archive` extract of `e61dad27` gave 12932 passed / 30 skipped / 11 failed. All 11 failures are git-dependent tests (the extract is not a work tree), so none is a code red. The binding baseline is the G3 full suite on the worktree.
- **Binding-rule slip, owned by cell 1:** one read-only `git stash list`, against the no-stash rule. It changed nothing.
- **Task 5 draft:** cell 1 wrote a full service draft WITHOUT committing it or writing its tests first. It is preserved at `~/swing-data/review-transcripts/22-b-exec/.task5-service-draft-cell1.WIP.py` (sha256 prefix recorded in the orchestrator's commit). It is REFERENCE ONLY: cell 2 builds Task 5 red-first, and the draft is not a commit.
