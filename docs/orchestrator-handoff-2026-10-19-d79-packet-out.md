# Orchestrator handoff -- 2026-10-19 -- D81 merged; D79 round 0 done, its ruling packet is with the directors

**Supersedes:** `orchestrator-handoff-2026-09-28-followups-exit-witness.md`.
**From:** the generation bootstrapped 2026-09-28 (session `d0e97b42`, Opus 5.5). It rolled at ~370K on a clean boundary.
**Re-derive every fact below.**

## 1. STATE

- **`main` @ this handoff's commit,** on `34b6e2b0`. It is ahead of `origin/main`, NOT pushed; the push is the operator's (CHARC pushed `47ca888d` on the operator's 09-28 direction).
- **Schema v41, unchanged.**
- **Merged this generation:**
  - the exit re-render anchor fix (`c6640faf`; operator browser witness passed on a scratch DB; merged-head 15360/13/0);
  - **D81**, the in-run coverage_gaps cry-wolf (`34b6e2b0`; merged-head **15380/13/0**, read; ledger `docs/superpowers/plans/2026-10-18-d81-coverage-gaps-inrun.ledger.md` @ `f692b823`, with CHARC's B-3 ruling block-quoted).
- **Worktrees:** ONE. `.worktrees/d79-exit-identity`, branch `d79-exit-identity` @ `072c5844`, clean, nothing committed.
  - Branches KEPT because ledgers cite them: `exit-rerender-anchor`, `d81-coverage-gaps`, `22-f-exec`, `22-f-plan`.
- **Cells:**
  - None RUNNING.
  - The D79 round-0 cell (opus-high, depth 320,531) has RETURNED and may read `parked`. Its state is fully on disk and **it will NOT be resumed**: the plan stage is a fresh cell off the rulings.
  - The D81 cell (sonnet-high, depth ~229K) has returned, and its work is merged.
- **Directors:** CHARC `swing-charc-20261014-1207`; RD `swing-rd-20260928-1659`. Trust the `ping ->` line.

## 2. IN FLIGHT, owner = you: D79 (the post-pause exit arc; F2 double-record + F1 non-default pick)

**Operator words, verbatim:**
- 2026-09-28: "exit double-record defect will be after the pause."
- 2026-09-28: "Concur with RDs recommendation.  Let's plan it to dothose two fixes post-pause."
- 2026-10-18: "draft the brief", then "go on round 0".

**Those cover round 0 ONLY.** The plan dispatch and the executing dispatch each need the operator's word, unless he grants a standing authorization.

**Where things stand:**
- **Brief:** `docs/d79-exit-order-identity-brief.md` @ `072c5844`. **It has a KNOWN ERROR, the orchestrator's:** it cites `swing/integrations/schwab/trader.py:_compute_signature_hash` (:195), which is an API drift fingerprint. The candidate hash is `swing/trades/exit_auto_fill.py:1652-1691`. Fix it in the plan dispatch. CHARC was asked to fix the D79 register row.
- **Round-0 record:** `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\round0\return-report.md`. It is RE-SET from the cell's chat return and labelled not-verbatim; the probes and query outputs are beside it. READ IT FIRST.
- **The ruling packet,** posted `20261019T011352Z` to charc and rd (`--type query`), ONE ruler per item:
  - **CHARC:** K1 (the guard in `record_exit` under one `BEGIN IMMEDIATE`, i.e. the `exit.py` carve-out); K6 (schema backstop; the cell is against it).
  - **RD:** K2 (the key: order id alone); **K3, the crux** (what a CONFIRMED F1 contradiction records; the cell recommends (iv), a confirmation counts as link evidence, else (ii)); the K5 sub-fork ((c) confirm-before or warn-after, which also decides the CLI); K7.1 (global versus per-trade guard scope); K7.2 (a typed partial of a WORKING order).
  - **YOU rule, after the directors' rulings land:** K4 (the F1 surface; the server check against the SELECTED entry is required; refill none / JS / HTMX `hx-get`); K5 (the confirm flow; the entry `SoftWarnError` + `force` shape); K7.3 (the false "operator corrected" label); K7.4 (the false `_exit_candidates_maps_equal` docstring); K7.5 (the flag text).
- **NEXT, in order:**
  1. Drain the inbox for the two ruling packets. Transcribe each ruling into a COMMITTED D79 plan ledger, with the director as author and you as courier.
  2. Rule K4/K5/K7.3-5 in the same ledger.
  3. Ask the operator for the plan-dispatch go.
  4. Dispatch the plan cell (opus-high default), off a FRESH worktree cut from the then-current main, so it carries the ledger. Remove or re-cut `d79-exit-identity` at that point.
- **Timing:** before the first live exit. The pause ends ~10-20.

**Key measurements to carry (from round 0):**
- F2-A (stale-form replay) and F2-B (re-offer after the retention rule drops the id; a single-candidate variant stamps NO `selected_*` key) were both reproduced through the real route.
- RD's case (b) is UNREACHABLE by fill growth (terminal orders only), so the id alone is a sufficient key.
- Reconciliation is NOT a backstop: shape C emits zero discrepancies.
- Live: zero duplicates.
- 13 of 19 envelope-bearing exit fills lack a stored 22-A reading.
- Split-into-partials legitimately copies one order id onto N fills. A guard in `insert_fill_with_event`, or a unique index, would break it.

## 3. AUTHORITIES (a grant is STATE)

- Operator 2026-09-28 follow-ups grant: SPENT.
- D81: commissioned by the operator 2026-10-18 ("concur with the fix", RD courier); CHARC dispatched it; SPENT at the merge.
- D79: round 0 only (section 2). **No standing grant exists for the plan or the execution.**
- No authority was granted by cell message this generation beyond the D81 B-minor instruction (tests only, no Codex), recorded in the D81 ledger.

## 4. OPEN / OWED

- **Schwab token:** re-authenticated 2026-09-28, and the TTL is 7 days, so it is almost certainly expired. D79's browser witness needs `swing schwab logout` then `swing schwab setup` by the operator.
- **RD's study questions to the operator:** the unresolved `equity_delta` of +$219.57 (RKLB out-of-framework buy suspected); `degenerate_risk` 23 -> 30 to re-read in November. Both are RD's.
- **CHARC owes:** D81's register row to CLOSED; the D79 row's `trader.py` correction; the test-5 fixture error as a sixth D80 instance.
- The D79 brief's `trader.py` error (section 2).

## 5. WHAT WILL BITE YOU

- **Two seats can draft the same brief.** CHARC and this seat each wrote a D81 brief minutes apart. Mine was retired at `eab23a95`. When a director is mid-ruling on an item, ask before drafting it.
- **A witness instruction that says "leave field X as it is" can plant the very defect being witnessed.** At the 09-28 exit witness, F1 was found that way.
- **`ux_pipeline_one_running` (0003:151) allows only ONE running `pipeline_runs` row.** Tests needing a decoy use a `failed` row.
- **The merged-head suite runs ~11 min** and outlives the Bash 600s timeout. Background it and read the saved output.
- **Every role_mail post goes from the MAIN repo cwd;** verify delivery on disk.
