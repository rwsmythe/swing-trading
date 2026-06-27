# Phase 18 Close Audit — CHARC (Tool Development Director)

**Date:** 2026-06-27. **Auditor:** CHARC, per charter §2.4 (phase audit) + §4.2 (harness probe mandatory at phase close). **Scope:** Phase 18 (Data-Collection Integrity) — arcs 18-A…18-H + the cash-coherence cluster + the close groups G1–G6 + the `coverage_gaps` calibration. **Trigger:** G6 (the last work group) complete; the only remaining Phase-18 items are this audit + the orchestrator's close-out housekeeping. **Method:** every claim below carries fresh on-disk evidence (verification-before-completion); the suite was re-run on the actual merged HEAD, not carried forward.

---

## 1. Verdict

**Phase 18 is ENGINEERING-clean to close.** Every commissioned arc landed or was correctly dispositioned; the streaks hold; the merged-head suite is green; the harness probe is clean. **Two honest caveats** that the verdict does NOT paper over:

1. **#5 (`drumbeat_liveness` recurring false-RED) closes as a DELIBERATE paused/observe-first disposition, not a resolution** — diagnosed on disk, fix commissioned (brief `19185b04`) but HELD at writing-plans (orchestrator `be363355` not dispatched). This is the operator's settled call (transient/self-recovering, non-emergency, possibly a dev-context artifact). Diagnosis is banked either way. Carried past close.
2. **The orchestrator-lane close housekeeping is NOT yet done** — the §4.3 archival sweep (no `docs/archive/phase18/` bucket exists; 496 top-level `docs/*.md`) and the CLAUDE.md line-3/§6 compaction. These are the writing role's CONTENT work (custodian boundary §2.6), not CHARC's. The FULL phase close completes when that pass runs; this audit clears the engineering side and verifies the sweep landed once it does.

Net: the codebase is sound to draw a line under the phase. The two caveats are sequencing/lane items for the operator, not engineering defects.

## 2. Streaks + gates — verified on disk (HEAD `b735ef45`)

| Check | Result | Evidence |
|---|---|---|
| Fast suite (merged head) | **8881 passed, 5 skipped, 0 failed** (278.61s) | fresh `pytest -m "not slow" -q -n auto` on HEAD; 5 skips all known-intentional (operator-only fixtures / forbidden-pattern locks / UNIQUE dup-guard / gated git-diff / pending DIVIDEND payload) |
| `ruff check swing/` | **All checks passed!** | fresh run |
| Schema version | **v31** (unchanged since 18-H.6) | `EXPECTED_SCHEMA_VERSION = 31` (`swing/data/db.py:55`); latest migration `0031_untracked_broker_position.sql`; 31 files, none beyond 0031 |
| `Co-Authored-By` streak | **INTACT — 3774 consecutive trailer-free commits ending at HEAD** | parsed-trailer scan; only 3 co-authored commits in all 3846 history, all genesis-week (`2026-04-17`/`18`, depth #3775/#3803/#3807), pre-convention. This session's commits all parse `[]` |
| Harness probe | **all checks within thresholds, zero ATTENTION** | §5 below |

**Streak calibration note (for the next CLAUDE.md compaction):** the often-cited "ZERO Co-Authored-By — 3137 consecutive" is a *stale undercount*, not an error — the streak is measured from HEAD backward and never reaches the 3 genesis commits; it grows with every commit. Current true figure: **3774**. (Consistent with CLAUDE.md's own note that the prior "~720+ was a stale undercount.") "ZERO Co-Authored-By" is precise as "zero in the consecutive streak window," imprecise as "zero in all history" — the load-bearing word is *consecutive*.

## 3. Arc roster + outcomes (by group; full per-arc detail → `docs/phase18-todo.md` + `charc-state.md` + git)

| Group / arc | Outcome |
|---|---|
| **18-A/B/B.1 OHLC integrity** | SHIPPED. NaN-writer fix + shared `ohlcv_finiteness` predicate (`c45d8752`); OHLC write-path consolidation killing the #24–#26 divergence class (`5cce72db`); the `insert_observation` fail-loud write-barrier (`8022d45d`). |
| **18-C yfinance audit** | SHIPPED at **schema v30** (migration 0030, `2b381461`); operator-witnessed live migration; new `yfinance_calls` table + audit-context module (purely-additive observability around the raw fetch). Closed rider R3. |
| **18-D research-health monitor** | SHIPPED (`2f13f0f5` + nightly half `4d17492b`); script-first `compute_research_health` + the read-only pipeline step lighting 18-F's research stoplight. |
| **18-E tool-health monitor** | SHIPPED (`65de5a7f`); new `swing/monitoring/` package. **The 18-E false-RED `weather_freshness` data-shape miss → CHARC §5.10** (the live-DB witness caught what my C-E review + 4 Codex rounds missed). |
| **18-F GUI stoplights** | SHIPPED (`f075e7b5`); base-wide context-processor injection (sidestepped D15, not worsened); codex-auto-review ADOPTED here. |
| **18-H Schwab hardening + recon** | SHIPPED+CLOSED: .1 token-health YELLOW, .2/.3+R1 web-polish (**closed D7** — `requests` declared in pyproject), .4/.4.1 web re-auth self-lock (the closure-graph release lesson), .6 `untracked_broker_position` at **schema v31** (migration 0031), .6.1 orphan attribution, .7 nightly→rd-push (new automated `pipeline` comms sender). |
| **Cash-coherence cluster** | SHIPPED+CLOSED: SPCX out-of-framework (`5b24ef68`), swing-NLV §2.4 (`e1017b1e`), equity_delta-limbo (`8fee6a1d`), OOF-buy (`5855c760`), web simple-acknowledge (`023d6753`), cash-void/D19 (`be567712`). Closed the cash-correction gap (operator-correctable, no raw DB deletes). |
| **G2 paydown** | D20 Schwab-txn-id `^[0-9]+$` (`7eabb3d2`); D18 content-half ~1.56 GB reclaimed. |
| **G3** | 18-G brief-corpus retention convention (§4.3, closes D10); 18-H.7 (`ceecd837`). |
| **G4 scaffold code arcs** | B-9/B-12 (`f0da3aa`) + B-16 (`db644b4`) in harness-template (cross-repo). |
| **`coverage_gaps` calibration C** | `83c21305` — the first live research-health RED (benign 842-gap missed-run) now clears to accepted/green; both directors cleared. |
| **G6 comms-system sync** | COMPLETE. Arc A per-gen orchestrator inbox + registry (`94e8c7cb`), Arc B launch role + GUI bus (`1f8b8545`), B.1 newest-live self-read (`df262a4d`), Arc C scaffold GUI re-sync (`c1a1522`, harness-template, pushed). The comms-authority model was amended + validated (operator pre-authorized director→orchestrator dispatch; canonical `harness-architecture.md §3`). |

All cited swing commits confirmed ancestors of HEAD. Cross-repo arcs (G4, Arc C) landed in harness-template, operator-browser-witnessed.

## 4. Tripwire-gate scorecard

Phase 18 exercised the §3 tripwire gate more than any prior phase (it was schema-, monitor-, and comms-heavy): new schema ×2 (0030, 0031), new modules/packages (`monitoring/`, `ohlcv_finiteness`, `yfinance_audit*`, `research_health`, the comms mechanism), new standing processes (the research-health pipeline step, the automated `pipeline` comms sender, the orchestrator inbox + launch role + heartbeat hook), and several `swing/trades`/`swing/data` carve-outs (the OHLC barrier, the OOF + void matchers, `find_by_id`). **Zero tripwire false-negatives** — every cross-scope arc routed to CHARC as designed.

What the gate did NOT catch alone, and what did (the layered-defense design working as intended — Codex/CHARC are fallible intermediate filters; the operator/live-DB witness is the net):
- **18-E weather-freshness false-RED** — a read-path data-shape miss past my C-E review + 4 Codex rounds; the operator live-DB witness caught it. → §5.10 (review of read-path code verifies data-shape vs the live DB).
- **18-H.7 sender-type widening** — adding the `pipeline` sender inherited the full message types; codex-auto-review (repo-access) caught that `pipeline→operator decision_request` would have succeeded; my plan-stage review checked only the recipient-gate. → `harness-architecture.md §3` (automated senders are type-constrained at the sender gate).
- **G6 Arc-B stale bootstrap + launcher-effort defect** — codex-auto-review caught a stale reused artifact (`orchestrator_bootstrap.md`) and the operator browser witness caught the `--effort max` launcher bug. → §5.11 EXTENSION (existence ≠ currency when reusing an artifact as a given).

These are review-DEPTH lessons, all banked, all caught downstream — not gate failures.

## 5. Harness probe (2026-06-26 phase-close run)

**All checks within thresholds — zero ATTENTION.** Highlights: CLAUDE.md 61,503 (line-3 7,732 — under the 9K cap but the closest-to-threshold live figure, compaction due at this close); `orchestrator-context.md` **110,500** (heaviest live doc, approaching the 120K cap — its archive pass is the orchestrator's close housekeeping); `docs/*.md` **496/600** (the §4.3 Phase-18 sweep will trim it — not yet run); memory 50/80; comms mailboxes drained (0 unread each); `exports/` dated dirs 49 (+40 research, D3 — `archive_old_exports` keep-90 covers it). The two near-threshold figures (line-3, orchestrator-context) are exactly what the orchestrator close pass addresses.

## 6. CHARC self-critique (Phase 18 — owned squarely, per §5.1)

A heavier self-critique than Phase 17; the discipline is to record it, not bury it. The common thread: I was reliably right on logic/scope and reliably caught on PREMISE/CURRENCY by the live witness.

- **The §2.4 "math-sanity" premise was false on live numbers** (the swing-NLV brief) — caught by the live-DB witness; banked memory `feedback_verify_premise_arithmetic_vs_live`.
- **The 18-E data-shape miss** (→ §5.10) — verified logic, not the live data shape.
- **The B-9/B-12 pre-existence miss** (→ §5.11) — cited a sibling-project symbol as pre-existing on the target.
- **The Arc-B stale-bootstrap miss** (→ §5.11 EXTENSION) — reused an artifact as a given without a content-currency check.
- **The #5 "NON-ISSUE" close was WRONG** — a single GREEN `latest.json` snapshot does not disprove an INTERMITTENT false-RED; I assumed `exports_dir` was repo-absolute without tracing the `config_path→project_root` chain. Owned; re-opened; diagnosed; then paused observe-first.

Every one was caught — by the operator, the live DB, or codex-auto-review. The nets held. That is also the evidence that the review-tiering + live-witness-as-net model is sound.

## 7. Debt register at Phase-18 close (full state → charter §4)

- **Closed this phase:** D7 (R1, `requests` declared), D10 (resolved-as-convention, §4.3 / 18-G), D18 content-half (~1.56 GB reclaimed), D19 (cash-void), D20 (Schwab-txn-id).
- **Deferred-to-close / carried:** D17 (OOF provenance — premise-corrected, not column-closeable; a future legibility nice-to-have), D18 FORM-half (the `harness_probe` research-size check — forward-looking guard, ceilings sit quiet at the post-cleanup baseline).
- **Open / watch (no trigger):** D1 (runner size — wrapper sub-debt closed Phase 17, size/relocation deferred), D5 (suite runtime — 8881 tests, de-flaked, well under the 5-min trigger), D8 (anchor ladder), D9 (live-clock), D12 (latest-eval guard), D15 (base-layout VM duplication), D16 (manual-cash ergonomic).

## 8. Close-out + carried items + Phase-19 readiness

- **Engineering side: CLEAR.** Streaks, suite, ruff, probe all green on disk.
- **Remaining for FULL close (orchestrator lane, operator-sequenced):** the §4.3 Phase-18 archival sweep (~450 dead briefs → `docs/archive/phase18/`, with a `pre-phase-16` catch-all for the backlog) + the CLAUDE.md line-3/§6 compaction. CHARC's audit verifies the sweep landed (the top-level docs count drops) once it runs.
- **Carried past close:** #5 (paused observe-first; resume ONLY if it recurs in clean ops) · the CHARC follow-ups F1–F6 (incl. F6, the swing `comms_stop_hook.py` hardening back-port) · the decide-as-reached D16/D17 + the deferred #2 `equity_delta` materiality bump.
- **Phase 19 is NOT yet scoped** — the §2.3 next-phase proposal is the immediate post-close CHARC deliverable, drafted in dialogue with the operator (and contended for cycles against RD demand). No commission until then.
- **Phase 18 → CLOSED** (engineering) pending the orchestrator housekeeping + the operator's call.
