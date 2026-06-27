# V2 OHLCV DHC / UCO / VSAT × eval_runs 60-64 CRITERION DRIFT Triage — Investigation Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the DHC/UCO/VSAT × 60-64 CRITERION DRIFT investigation implementer. No prior conversation context.

**Mission:** Root-cause the 15-entry V1↔V2 baseline parity divergence on **DHC / UCO / VSAT × eval_runs 60-64** surfaced by V2 OHLCV harness post-Codex-fix smoke at `exports/diagnostics/aplus-sensitivity-v2-20260524T162641Z.{csv,md}`. This is a **distinct drift class** from the previously-investigated DK:62 finding (which was per-Codex-fix-bug pre-merge smoke + single-day boundary-bar staleness on the only Shape-A-stale both-exist ticker). The new finding surfaced AFTER D.1 Shape A refresh + the post-Codex-fix re-run. Identify (a) which side is correct (V1 persisted OR V2 recomputed); (b) per-criterion divergence point (which criterion flips and why); (c) drift-class scope (DHC/UCO/VSAT × 60-64 systemic? per-ticker class? per-criterion class? cross-sectional RS issue?); (d) remediation recommendation.

**Workflow:** `superpowers:systematic-debugging` skill (investigation; mirrors DK:62 investigation pattern at `applied-research-v2-dk62-criterion-drift-triage` precedent). Adversarial Codex MCP review OPTIONAL — invoke if proposed code changes land.

**Branch:** `applied-research-v2-dhc-uco-vsat-drift-triage` — branches from main HEAD `bef2d4e` (or later).

**Worktree:** `git worktree add .worktrees/applied-research-v2-dhc-uco-vsat-drift-triage applied-research-v2-dhc-uco-vsat-drift-triage`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~2-5 hours operator-paced (narrower hypothesis space than DK:62 due to pre-ruled-out candidates; may converge faster).

---

## §0 Read first (in this order)

1. **`exports/diagnostics/aplus-sensitivity-v2-20260524T162641Z.md`** — the post-D.1 + post-Codex-fix smoke artifact that surfaced this drift class. Note: 15 CRITERION DRIFT entries (DHC/UCO/VSAT × eval_runs 60-64; 3 tickers × 5 eval_runs = 15 systematic). DK:62 NO LONGER appears (D.1 Shape A refresh fixed that). Tier-2 went from 30/45 (pre-Codex-fix) to 10/0 (post-Codex-fix) — dramatic improvement; Codex fixes corrected tier classification.

2. **`exports/diagnostics/aplus-sensitivity-v2-20260523T230131Z.md`** — original pre-Codex-fix + pre-D.1-refresh smoke. Comparison reference. Note: DHC/UCO/VSAT drift was NOT visible in this artifact — it was MASKED by the pre-R3.M1 / pre-R4.M1 buggy flip-recording in sweep.py (per DK:62 investigation findings §5.3 lesson #3 anticipation).

3. **`docs/v2-dk62-criterion-drift-investigation-2026-05-23.md`** — predecessor investigation. KEY: §5.3 lesson #3 explicitly anticipated "regenerate the smoke against HEAD `a43a921` (post-merge with all Codex fixes applied) and confirm the drill-down rows behave per spec". This investigation is the materialization of that anticipated regeneration step.

4. **`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`** §E.4 (baseline parity invariant) — the BINDING contract V2 implements:
   - **Tier-1 (non-risk-gated buckets)**: V2 invoked with no substitution MUST produce same bucket distribution as V1's persisted-bucket pass — EXACT match required.
   - **Tier-2 (risk-gate-dependent buckets)**: CONDITIONAL match via `current_equity` surrogate per OQ-15.
   - DHC/UCO/VSAT × 60-64 hit Tier-1 FAIL → V2 recomputed bucket ≠ V1 persisted bucket.

5. **`research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`** lines 91-93 — V2's legacy-fallback reader (the path DHC/UCO/VSAT take since Shape A is ABSENT for these tickers).

6. **`research/harness/aplus_v2_ohlcv_evaluator/context_builder.py`** + `research/harness/aplus_v2_ohlcv_evaluator/sweep.py` — V2 evaluator surface.

7. **`swing/data/ohlcv_archive.py:172` (`read_or_fetch_archive`)** — V1's legacy-only read path (per CLAUDE.md gotcha #24 — V1 reads `{T}.parquet` only via this helper; consumed by `swing/prices.py`, `swing/pipeline/ohlcv.py`, `swing/trades/daily_management.py`).

8. **`swing/evaluation/scoring.py` (`bucket_for`) + `swing/evaluation/criteria/*.py`** — V1 production criterion source. Same code V2 invokes via `evaluate_one(ctx)`.

9. **`swing/evaluation/rs.py` (`load_universe`, `compute_rs`)** — RS universe + percentile computation. **HIGH-RELEVANCE**: V2 uses current-universe snapshot per OQ-14 (NOT per-eval_run-historical); if DHC/UCO/VSAT's RS percentile shifted between eval_run 60-64 dates and today (V2 invocation), the bucket assignment could flip on TT8 (`rs_rank_min_pass`).

10. **CLAUDE.md** gotchas — especially relevant:
    - **#24 NEW** — Parallel-archive freshness desync. PRE-RULED-OUT for this investigation (DHC/UCO/VSAT are legacy-only; no parallel archive).
    - **OQ-14 LOCK + V1 method-record V2 dependency #2** — RS universe drift between historical asof_date + V2 invocation; CANDIDATE root cause for systemic drift.
    - **OQ-15 LOCK** — `current_equity` surrogate for tier-2; PRE-RULED-OUT (DHC/UCO/VSAT are tier-1 drift, not tier-2).
    - **#19 cascade-call-graph verification** — V2's evaluate_one cascade through criteria; verify each criterion invocation matches V1 production behavior.

---

## §1 Narrowed hypothesis space (4 candidates)

Several DK:62 hypotheses are PRE-RULED-OUT for this drift class:

- **DK:62-style parallel-archive freshness desync** RULED OUT — DHC/UCO/VSAT have ZERO Shape A files (`{T}.yfinance.parquet` ABSENT); V2 falls through to legacy at `ohlcv_reader.py:91-93`.
- **Legacy archive staleness** RULED OUT pre-investigation — all 3 legacy files have `last_asof_date=2026-05-22` (verified during D.1 inspection).
- **Tier-2 current_equity surrogate** RULED OUT — these are tier-1 drift entries; surrogate is tier-2-only.
- **Schwab API parquet asymmetry** PARTIALLY RULED OUT — DHC + VSAT have `{T}.schwab_api.parquet` but UCO does NOT; if the source-ladder asymmetry were the cause, UCO should NOT drift; UCO drift presence rules this out as the unitary cause. May still be a CONTRIBUTING factor for DHC + VSAT subset; verify.

### §1.1 H1: V2 legacy-fallback reader differs from V1's `read_or_fetch_archive`

**Evidence to gather**:
- Read `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py:91-93` legacy-fallback code path.
- Compare to `swing/data/ohlcv_archive.py:172` `read_or_fetch_archive` legacy path.
- Per-difference enumeration: column normalization (capitalized vs lowercase OHLCV); asof_date handling (DatetimeIndex vs asof_date column); date filtering (inclusive/exclusive bounds); row count (200+ bars requirement); edge cases.
- **Counter-test**: for DHC at eval_run 60 asof_date, read via V1 `read_or_fetch_archive` AND V2 `read_yfinance_shape_a_sliced` + diff the DataFrames at row + column + dtype + asof boundary level.

**Falsification**: if V2's legacy-fallback reader produces byte-identical bars to V1's legacy reader for these tickers, H1 ruled out.

### §1.2 H2: V2 RS universe drift between historical asof_date and V2 invocation (OQ-14 surrogate)

**Evidence to gather**:
- Per OQ-14 LOCK, V2 uses CURRENT-universe snapshot for ALL historical eval_runs. If DHC/UCO/VSAT's RS percentile rank computed at TODAY's universe ≠ their rank computed at eval_run 60-64's historical universe, TT8 (`rs_rank_min_pass`) criterion may flip → bucket changes.
- Inspect `cfg.paths.rs_universe_path` (current file mtime + first/last lines).
- For DHC/UCO/VSAT, compute V2's RS rank at eval_run 60-64 asof_date USING CURRENT universe vs V1's persisted RS rank in `candidate_criteria` for those eval_run/ticker pairs.
- If RS rank diverges by 1+ percentile bucket → strong evidence for H2.

**Falsification**: if V2's RS rank matches V1's persisted RS rank exactly for all 15 ticker:eval_run combos, H2 ruled out.

### §1.3 H3: V2 OHLCV slicing edge case at asof_date boundary (off-by-one / inclusive vs exclusive)

**Evidence to gather**:
- V2's `read_yfinance_shape_a_sliced` (or legacy-fallback equivalent) takes asof_date + filters bars. Compare slicing semantic to V1's `read_or_fetch_archive` end_date semantic.
- Per cumulative gotcha "Session-anchor inequality discipline depends on anchor directionality": backward-looking anchors use STRICT `>`; forward-looking use `>=`. Verify V2 matches V1's directionality.
- Specific test: for DHC at eval_run 60 asof_date, verify V2 returns bars ending AT or BEFORE that date (V1 semantic).
- **Counter-test**: feed V2's evaluate_one V1's exact bar slice (e.g., bars ending at eval_run 60 asof_date inclusive); compare bucket vs V1 persisted.

**Falsification**: if V2's OHLCV slice matches V1's bar count + last-bar asof_date for these ticker:eval_run combos, H3 ruled out.

### §1.4 H4: V2 BatchContext reconstruction differs at historical asof_date

**Evidence to gather**:
- V2's `build_eval_run_cohort` reconstructs BatchContext from current universe per OQ-14 LOCK. Verify the BatchContext fields used by criteria at eval_run 60-64:
  - `returns_12w_by_ticker` — per OQ-14 historical, this is recomputed using current OHLCV which may differ if universe membership changed.
  - `spy_return_12w` — same.
  - `current_equity` surrogate — tier-2-only, ruled out for tier-1 drift but verify it doesn't leak.
- Per the DK:62 investigation §1.3 counter-test pattern: feed `evaluate_one` the SAME BatchContext as V1 had at eval_run 60-64 (via direct queries against `candidate_criteria` to reconstruct) + assert V2's bucket matches V1's.

**Falsification**: if V2's BatchContext reconstruction matches V1's persisted BatchContext for all 15 ticker:eval_run combos, H4 ruled out.

### §1.5 Decisive counter-test (MUST run regardless of which hypothesis falsifies)

Mirror DK:62 investigation §1.3 counter-test: **for at least 1 of {DHC:60, DHC:64, UCO:62, VSAT:60}**, invoke `evaluate_one` with the SAME inputs V1 had at eval_run time (legacy bars + V1's RS universe / BatchContext state if reconstructable) AND verify V2's recomputed bucket matches V1's persisted bucket EXACTLY. If yes, V2 code is correct and the divergence is in the CONTEXT (universe drift OR BatchContext drift). If no, V2 has a real bug somewhere.

---

## §2 Investigation surface — per-criterion divergence pinpoint

After identifying the root cause for ONE representative ticker:eval_run combo, walk the per-criterion delta:

1. Query `candidate_criteria` for DHC:60 (and 1-2 other representatives): per-criterion `status` + `evidence_value` as V1 persisted.
2. Invoke V2's `evaluate_one` for DHC:60 + capture per-criterion `status` + `evidence_value`.
3. Identify WHICH criterion(s) flip + WHY (specific evidence_value delta).
4. If MULTIPLE criteria flip per ticker:eval_run → check if they share a common upstream input (e.g., all 8 trend_template criteria depend on OHLCV close prices; all RS-related criteria depend on rs_rank).

---

## §3 Deliverables

The investigation MUST produce:

1. **Investigation findings document** at `docs/v2-dhc-uco-vsat-drift-investigation-2026-MM-DD.md`:
   - Per-hypothesis evidence summary (H1, H2, H3, H4, H5+)
   - Root cause identification (with code:line citation)
   - Per-criterion divergence (which criteria flip; why)
   - Drift-class scope characterization (legacy-only-tickers-only? cross-sectional? specific RS-band? other pattern?)
   - Remediation recommendation
   - Forward-binding lessons for future research-branch arcs

2. **Optional**: if a V2 code fix is needed, implement + test on the same branch (same discipline as DK:62 investigation — L2 LOCK 5 BINDING tests stay green; `git diff swing/` stays empty except for the existing OQ-17 carve-out; production read-only invariant).

3. **Optional**: if drift class is broader than expected, surface affected scope + recommend whether full operator 63-eval-run reproduction proceeds OR pauses.

4. **Return report** at `docs/v2-dhc-uco-vsat-drift-investigation-return-report.md`.

---

## §4 Watch items + cumulative discipline (BINDING)

### §4.1 Pre-Codex 7-expansion + 5 NEW candidate refinements + 2 NEW sub-refinements + 3 NEW sub-promotions + #24

If investigation surfaces code changes warranting Codex review:
- 7 expansions (#1-#7) + Expansion #8 + #9 + #10 + #11 + #12 candidates
- 2 NEW sub-refinements: #19 cascade-call-graph + #20 runtime-binding-shape + empty-result-set
- 3 NEW from V2 executing-plans: #21 cumulative regression cascade + #22 per-counter-accumulation + #23 dataclass attribution metadata
- 1 NEW from DK:62 investigation: #24 parallel-archive freshness desync (PRE-RULED-OUT for this investigation but the discriminating-test pattern may inform H1 evidence-gathering)

24 cumulative gotchas (1-24) BINDING for any 34th cumulative C.C lesson #6 validation.

### §4.2 Cumulative process discipline

- **NO Co-Authored-By footer** — ~496+ cumulative streak through housekeeping `bef2d4e`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + markdown narrative text (Windows cp1252 stdout safety)
- **TDD per task** via `superpowers:test-driven-development` if code changes land
- **Edit tool for per-file edits**

### §4.3 Schema discipline (LOCK)

Schema v21 LOCKED. Investigation MUST NOT touch migrations.

### §4.4 L2 LOCK preservation (BINDING)

ZERO new Schwab API calls. Investigation may READ `{T}.schwab_api.parquet` files for DHC + VSAT (Schwab parquet exists; UCO does NOT) to verify source-ladder asymmetry; that is file-side reads, NOT API calls. V2's reader still MUST NOT open `{T}.schwab_api.parquet` (per L2 LOCK reinforcement tests; preserve invariant).

### §4.5 Read-only invariant for V1 persisted state

DO NOT modify `candidate_criteria` rows for eval_runs 60-64 OR any other eval_run during investigation. Read-only SELECT queries only.

### §4.6 Production swing/ read-only EXCEPT existing OQ-17 carve-out

`git diff main -- swing/` MUST remain empty (V2 already SHIPPED swing/cli.py +71 lines for OQ-17 carve-out per merge `a43a921`; investigation MUST NOT add to swing/). If a V2 reader fix is needed in `research/harness/aplus_v2_ohlcv_evaluator/`, that's allowed (research-branch); production swing/ writes are NOT.

---

## §5 Pre-investigation context (operator-side gathered)

- **DHC** = Diversified Healthcare Trust (REIT). Legacy `.parquet` + `schwab_api.parquet` present; Shape A `.yfinance.parquet` ABSENT. Legacy mtime 2026-05-22 14:52; last_asof=2026-05-22.
- **UCO** = ProShares Ultra Bloomberg Crude Oil (2x leveraged ETF). Legacy `.parquet` ONLY (no schwab_api, no Shape A). Legacy mtime 2026-05-22 21:27; last_asof=2026-05-22. **NOTE: Leveraged ETF may have distinctive OHLCV characteristics; consider if criteria thresholds behave unexpectedly on leveraged ETF returns.**
- **VSAT** = Viasat (satellite communications). Legacy `.parquet` + `schwab_api.parquet` present; Shape A `.yfinance.parquet` ABSENT. Legacy mtime 2026-05-22 20:49; last_asof=2026-05-22.
- **eval_runs 60-64**: the most-recent 5 eval_runs in operator's S3 universe (per the V2 smoke `--eval-runs 5` parameter). Likely dates ~2026-05-15 through ~2026-05-22 (one trading day per eval_run + skip weekends).
- **Drift signature**: 3 tickers × 5 eval_runs = 15 systematic tier-1 drift entries. NOT a per-boundary-bar single-day failure; suggests SYSTEMIC reader / context divergence.
- **Both-exist tickers** (AESI/DK/PL) are NOT in this drift class (they're parallel-archive tickers; DK:62 was the only one with stale Shape A; D.1 fixed it).
- **D.2 post-Codex-fix smoke header**: 351 candidates evaluated; 516 universe size; v2_universe_hash same as pre-refresh (`v2_universe_hash_85b0871b5a5e0cc5aef399eabd65cd8cd5ba656af18f127098c2bc57647e4b34`). Truncated by 120s cap (only 10 of 17 variables completed — drift detection happens at BASELINE before sweep loop so truncation doesn't affect tier-1 list).

---

## §6 NON-scope

- ZERO Phase 14 commissioning consideration (DEFERRED per Path B sequencing)
- ZERO promotion of V2 method-record from `research` → `shadow` (DEFERRED per OQ-8 ladder; gated on resolving DHC/UCO/VSAT drift)
- ZERO full 63-eval-run operator reproduction (gated on this investigation)
- ZERO V1 production code changes (production read-only invariant)
- ZERO Schwab API calls (L2 LOCK preserved)
- ZERO new schema migrations (schema v21 LOCKED)
- ZERO modification of V1 persisted candidate_criteria / pipeline_runs / evaluation_runs rows

---

## §7 Post-investigation handback

When investigation findings + recommendation are documented:

1. Write findings document at `docs/v2-dhc-uco-vsat-drift-investigation-2026-MM-DD.md` per §3.1
2. Write return report at `docs/v2-dhc-uco-vsat-drift-investigation-return-report.md` per §3.4
3. Inline self-verification: ruff check; schema unchanged; ZERO new Schwab API calls; ZERO Co-Authored-By footer; V1 persisted state unchanged
4. Hand back to operator with: root cause + code:line citation; per-criterion divergence; drift-class scope; remediation recommendation; V2 candidates banked.

Orchestrator-side next steps post-investigation:
- QA findings per `feedback_orchestrator_qa_implementer_product`
- Merge investigation branch `--no-ff` to main; push
- Post-merge housekeeping (sub-event scale; in-place amendments; NEW gotcha if banked)
- Operator-paired decision on remediation path
- IF remediation requires V2 code fix: separate dispatch OR continue in same branch per scope
- IF drift is non-blocking (documented in method-record Limitation L5): proceed to D.3 v0.2.1 amendment + D.4 V2 candidate banking + full 63-eval-run reproduction

---

*End of V2 OHLCV DHC/UCO/VSAT × 60-64 CRITERION DRIFT triage dispatch brief. Investigation scope only. 4 narrowed hypotheses (DK:62 parallel-archive desync PRE-RULED-OUT). Deliverable = findings + per-criterion divergence + remediation. ~496+ ZERO Co-Authored-By footer streak preserved through this brief commit. Investigation unblocks D.3 method-record v0.2.1 amendment + D.4 V2 candidate banking + full 63-eval-run operator reproduction.*
