# V2 OHLCV Full-63-Eval-Run Reproduction CRITERION DRIFT Triage — Investigation Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the V2 full-reproduction CRITERION DRIFT investigation implementer. No prior conversation context.

**Mission:** Root-cause the 14-entry V1↔V2 baseline-parity divergence surfaced by the **full 63-eval-run V2 reproduction** at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}`. This is a **THIRD distinct drift class** following:
- DK:62 (parallel-archive freshness desync; L4 / gotcha #24; REMEDIATED via D.1 Shape A refresh)
- DHC/UCO/VSAT × 60-64 (V2 harness false-positive on V1 pre-evaluation excluded sentinels; L5 / gotcha #25; REMEDIATED via Option A merge `b7f70ff`)

The new drift entries:
```
CNTA:42, CNTA:43, ECVT:40, APLS:34, APLS:38, APLS:39,
FTI:31, FTI:32, STNG:19, STNG:20, STNG:21, PL:6, PL:7, PL:8
```
**6 unique tickers spanning eval_runs 6-43** (NOT clustered at the recent boundary like prior classes). Identify (a) which side is correct (V1 persisted OR V2 recomputed); (b) per-criterion divergence point (which criterion flips and why); (c) drift-class scope (PL-shape-a-historical-desync? OQ-14 universe drift? source-ladder asymmetry? new sentinel-bucket class? something else?); (d) remediation recommendation (option A-style filter, OR D.1-style data refresh, OR new architectural fix).

**Workflow:** `superpowers:systematic-debugging` skill (investigation; mirrors DK:62 + DHC/UCO/VSAT investigation pattern). Adversarial Codex MCP review OPTIONAL — invoke only if proposed code changes land beyond the investigation surface.

**Branch:** `applied-research-v2-full-reproduction-drift-triage` — branches from main HEAD `9f72a68` (or later; reflects Option A merge + D.3 method-record amendment).

**Worktree:** `git worktree add .worktrees/applied-research-v2-full-reproduction-drift-triage applied-research-v2-full-reproduction-drift-triage`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~2-5 hours operator-paced. Hypothesis space is broader than DHC/UCO/VSAT because the drift signature spans 6 tickers + non-contiguous eval_runs.

---

## §0 Read first (in this order)

1. **`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`** — the full-63-eval-run smoke artifact that surfaced this drift class. Runtime 5172s (86 min; under 90-min cap; NOT truncated). 63 eval_runs (ids 2..64); 5666 candidates; 516 universe; 88 OHLCV coverage skips; tier-2 clean (120/0); 14 tier-1 drift entries listed in CRITERION DRIFT DETECTED section. Note: 5 binding variables identified in the Headline section — investigation must NOT modify the sensitivity matrix counts; they're operator-facing.

2. **`docs/v2-dhc-uco-vsat-drift-investigation-2026-05-24.md`** — predecessor investigation (DHC/UCO/VSAT × 60-64). KEY: §6 forward-binding lessons + §1.5 H5 root cause pattern. The 14-entry class may have analogous architecture-level root cause (V1 production path V2 doesn't replicate).

3. **`docs/v2-dk62-criterion-drift-investigation-2026-05-23.md`** — first investigation (parallel-archive freshness desync; L4). KEY: §1 hypothesis falsification pattern + §5 remediation Option D Shape A refresh path. If PL drift at eval_runs 6-8 traces to OLDER-boundary Shape A staleness, this informs the remediation.

4. **`research/method-records/aplus-criteria-calibration.md` §"Known limitations of V2 baseline-parity claims (v0.2.1 addendum 2026-05-24)"** — L4 + L5 entries with code:line citations. New investigation may produce L6 if a third drift class is root-caused.

5. **`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`** §E.4 (baseline parity invariant) — BINDING contract V2 implements:
   - **Tier-1 (non-risk-gated buckets)**: V2 invoked with no substitution MUST produce same bucket distribution as V1's persisted-bucket pass — EXACT match required.
   - **Tier-2 (risk-gate-dependent buckets)**: CONDITIONAL match via `current_equity` surrogate per OQ-15. Tier-2 was clean (120/0) in this smoke; pre-rule-out tier-2 paths.

6. **`research/harness/aplus_v2_ohlcv_evaluator/sweep.py:540-605`** (`_compute_baseline_parity`) — V2 baseline-parity surface (post-Option-A filter). Verify the filter for `{'excluded', 'error'}` is active.

7. **`research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`** — V2 reader (Shape A primary + legacy fallback per OQ-18 LOCK).

8. **`swing/data/ohlcv_archive.py`** (`read_or_fetch_archive` + `_compute_legacy_resolution_chain`) — V1's read path. Note V1 may consume from a different file shape (Shape A, legacy, or Schwab API parquet depending on ladder).

9. **`swing/pipeline/runner.py:1100-1200`** — V1's `_step_evaluate` per-ticker enumeration. Check for ANY other bucket short-circuit paths beyond excluded + error (L5 was the canonical set; new investigation may surface a third sentinel-class).

10. **`swing/evaluation/scoring.py`** (`bucket_for`) + criterion modules — V1 production criterion source. Confirm V2's `evaluate_one` invokes the same path.

11. **CLAUDE.md** gotchas:
    - **#24** (parallel-archive freshness desync; L4) — PRE-CANDIDATE for PL drift class given PL is on the both-exist list.
    - **#25** (sentinel-bucket parity-comparison discipline; L5) — PRE-CANDIDATE if a new V1 sentinel-bucket class exists.
    - **OQ-14 LOCK + V1 method-record V2 dependency #2** — RS universe drift between historical asof_date + V2 invocation; STRONG candidate for tickers without Shape A.
    - **OQ-15 LOCK** — `current_equity` surrogate for tier-2; PRE-RULED-OUT (tier-2 was clean 120/0).
    - **#19** cascade-call-graph verification.

---

## §1 Narrowed hypothesis space (5 candidates)

The 14 drift entries cluster across 6 tickers × non-contiguous mid-history eval_runs. Several DK:62 / DHC/UCO/VSAT hypotheses are PRE-RULED-OUT or CONDITIONALLY-IN:

- **L4 parallel-archive freshness desync (DK:62)**: PRE-CANDIDATE for PL (on both-exist banner; D.1 refreshed PL's most-recent boundary but older-history desync remains POSSIBLE). CONDITIONALLY-IN for PL:6,7,8 entries. RULED OUT for CNTA/ECVT/APLS/FTI/STNG (need to verify Shape A absence first).
- **L5 V2 harness false-positive on excluded sentinel (DHC/UCO/VSAT)**: RULED OUT — Option A filter at `sweep.py:545-557` filters `{'excluded', 'error'}`; these 14 candidates would have been filtered if they were sentinel-bucket. Confirm via SQL: `SELECT bucket, notes FROM candidates WHERE ticker IN ('CNTA','ECVT','APLS','FTI','STNG','PL') AND evaluation_run_id IN (6,7,8,19,20,21,31,32,34,38,39,40,42,43)` — verify NONE have `bucket IN ('excluded', 'error')`.
- **Tier-2 current_equity surrogate (OQ-15)**: RULED OUT — tier-2 clean (120/0) in the smoke; this is tier-1 drift.
- **Truncation artifact**: RULED OUT — smoke `Truncated by runtime cap: no` per artifact line 11; 63 eval_runs fully processed.

### §1.1 H1: V2 Shape A vs legacy desync at HISTORICAL boundary dates (extends L4)

PL is on the both-exist banner (AESI/DK/PL); D.1 refreshed PL Shape A to current boundary 2026-05-24. BUT PL drifts at eval_runs 6, 7, 8 — these are EARLY eval_runs (likely ~2025-12 to 2026-01 dates). D.1's refresh updated the most-recent bar; OLDER Shape A history may still differ from legacy at those dates if Shape A and legacy were initially written from different historical fetches OR if intervening corporate actions (splits/dividends) repriced bars asymmetrically across the two archives.

**Evidence to gather**:
- For PL: read both `PL.yfinance.parquet` (Shape A) and `PL.parquet` (legacy); diff bar-by-bar at the eval_runs 6, 7, 8 asof_dates; check for missing bars, Close-price deltas, Volume deltas.
- Query `SELECT id, data_asof_date FROM evaluation_runs WHERE id IN (6,7,8)` to identify the exact dates.
- Verify Shape A row count + first/last bar dates vs legacy.

**Falsification**: if Shape A and legacy are byte-identical at PL's eval_runs 6, 7, 8 asof_dates, H1 ruled out for PL.

**Scope question**: does H1 apply to ANY of the other 5 tickers (CNTA/ECVT/APLS/FTI/STNG)? Check whether each has Shape A presence: `Test-Path "$env:USERPROFILE\swing-data\prices_cache\<TICKER>.yfinance.parquet"`. If ABSENT, V2 reads legacy → H1 N/A for that ticker.

### §1.2 H2: V2 RS universe drift between historical asof_date and V2 invocation (OQ-14 LOCK)

Per OQ-14 LOCK, V2 uses CURRENT-universe snapshot for ALL historical eval_runs. If CNTA/ECVT/APLS/FTI/STNG had different RS percentile ranks at their historical eval_run dates (universe membership churn; new IPOs entering; delisted tickers exiting), TT8 (`rs_rank_min_pass`) criterion may flip → bucket changes.

**Evidence to gather**:
- For each (ticker, eval_run_id) pair in the drift list, compute V2's RS rank using current universe vs V1's persisted RS rank at `candidate_criteria` for those (ticker, eval_run_id) rows.
- Query `SELECT criterion_name, evidence_value FROM candidate_criteria WHERE candidate_id IN (...) AND criterion_name = 'rs_rank_min_pass'`.
- Diff V2's recomputed RS rank vs V1's persisted RS rank per (ticker, eval_run_id).
- If RS rank diverges by >5 percentile points AND the divergence crosses the `rs.rs_rank_min_pass=80` threshold (current cfg) → strong H2 evidence.

**Falsification**: if V2's RS rank matches V1's persisted RS rank exactly for all 14 (ticker, eval_run_id) combos, H2 ruled out.

**Banked V2 candidate consequence**: H2 confirmation REINFORCES the V1 method-record V2 dependency #2 (V2 historical RS universe snapshots) as a non-V1-fix-needed item; the OQ-14 LOCK is a known V1 limitation. Resolution likely: filter from baseline-parity comparison (similar to L5's approach) OR characterize as expected V1 limitation in L6 entry.

### §1.3 H3: V2 source-ladder asymmetry — V1 reads from a different file shape than V2

V1's `read_or_fetch_archive` consumes via ladder logic. V2 reads Shape A (per OQ-18 LOCK) or legacy fallback (when Shape A absent). If V1's ladder selects a DIFFERENT file shape (e.g., `{T}.schwab_api.parquet` if present, OR a different legacy file path) than V2, the bars differ → bucket diverges.

**Evidence to gather**:
- For each of 6 tickers, check `Test-Path "$env:USERPROFILE\swing-data\prices_cache\<TICKER>.schwab_api.parquet"`.
- If `schwab_api.parquet` present, verify V1's ladder behavior (read `swing/data/ohlcv_archive.py` ladder logic).
- L2 LOCK: V2 MUST NOT open `{T}.schwab_api.parquet`. If H3 is the root cause, the remediation is NOT to add Schwab parquet to V2 (L2 LOCK BINDING). Instead, the remediation is similar to L5 — filter or characterize the asymmetry.

**Falsification**: if all 6 tickers lack `schwab_api.parquet` OR V1's ladder doesn't prefer that shape, H3 ruled out.

### §1.4 H4: V1 production short-circuit path beyond excluded + error (extends L5)

L5 caught `bucket='excluded'` (open positions + ETF blocklist) + `bucket='error'` (OHLCV fetch failure). But are there OTHER V1 paths that write a bucket value V2's `bucket_for` cannot reproduce?

**Evidence to gather**:
- Grep `swing/pipeline/runner.py` lines 1100-1300 for ALL `Candidate(` constructions outside the main `evaluate_batch` path; enumerate every bucket value V1 may write.
- For the 14 drift candidates, query `SELECT bucket, notes, rs_method FROM candidates WHERE candidate_id IN (...)`. Look for unusual `notes` values or `rs_method` patterns (e.g., `rs_method='unavailable'`, `notes='OHLCV partial'`, etc.).
- If V1 writes a sentinel-bucket V2 can't reproduce → extend Option A filter analog.

**Falsification**: if all 14 drift candidates have normal `bucket IN ('aplus', 'watch', 'skip')` with no sentinel `notes`, H4 ruled out.

### §1.5 H5: OHLCV history depth threshold — V2 read fewer bars than V1 had at historical eval_run time

V2's `read_yfinance_shape_a_sliced` requires ≥200 bars per spec §D for criterion evaluation. If a ticker had <200 bars at the historical eval_run asof_date BUT V1 evaluated anyway (different threshold OR no threshold), V2 might bucket=skip while V1 says watch/skip-different-reason.

Conversely, OHLCV coverage skips list in the smoke is 88 globally; if any of the 14 drift candidates are in that 88, V2 emitted a skip-coverage signal vs V1's bucket — though that would typically show as a different drift signature.

**Evidence to gather**:
- For each ticker in {CNTA, ECVT, APLS, FTI, STNG, PL}, check bar count from earliest-available-date to drift asof_date in BOTH Shape A and legacy.
- If <200 bars at the drift asof_date, this is the H5 root cause.

**Falsification**: if all tickers have ≥200 bars at their drift eval_run asof_dates, H5 ruled out.

### §1.6 Decisive counter-test (MUST run regardless of which hypothesis falsifies)

Mirror DK:62 / DHC/UCO/VSAT counter-test: **for at least 1 of {PL:6, STNG:19, APLS:34, CNTA:42}** (one per ticker family + spanning eval_run range), invoke `evaluate_one` with the SAME inputs V1 had at eval_run time (reconstructed via SQL queries on `candidate_criteria`) AND verify V2's recomputed bucket matches V1's persisted bucket EXACTLY. If yes, V2 code is correct + divergence is in the CONTEXT (data source OR universe). If no, V2 has a real evaluator bug.

---

## §2 Investigation surface — per-criterion divergence pinpoint

After identifying the root cause for at least 1 representative ticker:eval_run combo, walk the per-criterion delta:

1. Query `candidate_criteria` for the representative candidates: per-criterion `result` + `evidence_value` as V1 persisted.
2. Invoke V2's `evaluate_one` for the same candidates + capture per-criterion `result` + `evidence_value`.
3. Identify WHICH criterion(s) flip + WHY (specific evidence_value delta).
4. If MULTIPLE criteria flip per (ticker, eval_run_id) → check if they share a common upstream input (OHLCV close prices, RS rank, etc.).
5. Tabulate per-criterion divergence across the 14 entries to identify patterns (e.g., all involve RS-related criteria → H2; all involve trend-template MA criteria → H1).

---

## §3 Deliverables

The investigation MUST produce:

1. **Investigation findings document** at `docs/v2-full-reproduction-drift-investigation-2026-MM-DD.md`:
   - Per-hypothesis evidence summary (H1, H2, H3, H4, H5)
   - Root cause identification (with code:line citation if applicable)
   - Per-criterion divergence (which criteria flip; why; for which subset of the 14)
   - Drift-class scope characterization (PL-specific? OQ-14-driven? per-ticker class? source-ladder?)
   - Decisive counter-test result for at least 1 representative (V2 evaluator correct or buggy?)
   - Remediation recommendation
   - Forward-binding lessons for future research-branch arcs
   - **Study impact analysis** (see §5 below) — explicit per-binding-variable assessment

2. **Optional**: if a V2 code fix is needed, implement + test on the same branch (same discipline as DHC/UCO/VSAT investigation — L2 LOCK 5 BINDING tests stay green; `git diff swing/` stays empty except for the existing OQ-17 carve-out; production read-only invariant).

3. **Optional**: if drift class is broader than expected (e.g., affects >1% of candidates), surface affected scope + recommend whether the operator's 5-binding-variable identification is robust OR pauses pending remediation.

4. **Return report** at `docs/v2-full-reproduction-drift-investigation-return-report.md`.

---

## §4 Watch items + cumulative discipline (BINDING)

### §4.1 Pre-Codex 7-expansion + 5 NEW candidate refinements + 2 NEW sub-refinements + 3 NEW sub-promotions + #24 + #25

If investigation surfaces code changes warranting Codex review:
- 7 expansions (#1-#7) + Expansion #8 + #9 + #10 + #11 + #12 candidates
- 2 NEW sub-refinements: #19 cascade-call-graph + #20 runtime-binding-shape + empty-result-set
- 3 NEW from V2 executing-plans: #21 cumulative regression cascade + #22 per-counter-accumulation + #23 dataclass attribution metadata
- 2 NEW from prior investigations: #24 parallel-archive freshness desync + #25 sentinel-bucket parity-comparison discipline

**25 cumulative gotchas (1-25) BINDING for any 34th cumulative C.C lesson #6 validation.**

### §4.2 Cumulative process discipline

- **NO Co-Authored-By footer** — ~503+ cumulative streak through commit `9f72a68`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + markdown narrative text (Windows cp1252 stdout safety)
- **TDD per task** via `superpowers:test-driven-development` if code changes land
- **Edit tool for per-file edits**

### §4.3 Schema discipline (LOCK)

Schema v21 LOCKED. Investigation MUST NOT touch migrations.

### §4.4 L2 LOCK preservation (BINDING)

ZERO new Schwab API calls. Investigation may READ `{T}.schwab_api.parquet` files (filesystem reads for source-ladder asymmetry verification per H3); that is file-side reads, NOT API calls. V2's reader still MUST NOT open `{T}.schwab_api.parquet` (per L2 LOCK reinforcement tests; preserve invariant).

### §4.5 Read-only invariant for V1 persisted state

DO NOT modify `candidate_criteria` rows for any eval_run during investigation. Read-only SELECT queries only.

### §4.6 Production swing/ read-only EXCEPT existing OQ-17 carve-out

`git diff main -- swing/` MUST remain empty (V2 already SHIPPED swing/cli.py +71 lines for OQ-17 carve-out per merge `a43a921`; investigation MUST NOT add to swing/). If a V2 reader fix is needed in `research/harness/aplus_v2_ohlcv_evaluator/`, that's allowed (research-branch); production swing/ writes are NOT.

---

## §5 Study impact analysis (BINDING — must address explicitly in findings doc)

The full-reproduction smoke identified **5 binding variables** in the Headline section (all VCP-family):

| Variable | Δ A+ at best sweep_point |
|---|---|
| `vcp.tightness_range_factor` | +75 |
| `vcp.tightness_days_required` | +16 |
| `vcp.adr_min_pct` | +11 |
| `vcp.proximity_max_pct` | +5 |
| `vcp.orderliness_max_bar_ratio` | +1 |

**Conservative worst-case impact analysis**: 14 drift entries / 5666 candidates = 0.25%. If ALL 14 are miscounted in V2's evaluation at the binding sweep_point in the WORST direction, deltas would shift by up to ±14 per variable:
- `tightness_range_factor` 75 → 61 (still strongly binding)
- `tightness_days_required` 16 → 2 (marginally binding)
- `adr_min_pct` 11 → -3 (could flip non-binding)
- `proximity_max_pct` 5 → -9 (would flip non-binding)
- `orderliness_max_bar_ratio` 1 → -13 (would flip non-binding)

Investigation findings doc MUST include a per-variable assessment:
1. **If drift class is L5-style (V2 harness comparison bug; V2 evaluator correct)** → sensitivity matrix counts UNCHANGED; binding variables UNCHANGED; only parity-comparison flips PASS.
2. **If drift class is L4-style (V2 data-input drift; V2 evaluator correct given inputs)** → counts MAY shift by ≤14 per variable; top 2 binding variables (tightness_range_factor + tightness_days_required) ROBUST; bottom 3 may shift in magnitude or flip non-binding.
3. **If drift class is V2 evaluator bug** → counts MAY shift more substantially; binding-variable identification could change. Per-candidate per-criterion divergence pinpoint required to characterize impact precisely.

Investigation findings doc's study-impact section is BINDING for the operator's downstream decision on whether to:
- Publish the study writeup with current binding-variable counts (if robust), or
- Pause study publication pending remediation (if bottom 3 binding variables flip), or
- Publish with caveats (if top 2 robust + bottom 3 uncertain).

---

## §6 Pre-investigation context (operator-side gathered)

- **14 drift entries** (full list at smoke artifact CRITERION DRIFT DETECTED section):
  - PL:6, PL:7, PL:8 (3 entries; EARLY eval_runs; PL on both-exist banner so may be L4-extended)
  - STNG:19, STNG:20, STNG:21 (3 entries; mid-history)
  - FTI:31, FTI:32 (2 entries)
  - APLS:34, APLS:38, APLS:39 (3 entries; non-contiguous mid-range)
  - ECVT:40 (1 entry; singleton)
  - CNTA:42, CNTA:43 (2 entries)
- **6 unique tickers** spanning eval_runs 6-43; NOT clustered at recent boundary (unlike DK:62 + DHC/UCO/VSAT).
- **Tier-2 clean** (120 match / 0 mismatch) — rules out tier-2 paths.
- **Truncation**: NONE — full 63 eval_runs processed.
- **Universe + hash**: 516 universe size; v2_universe_hash same as prior smokes (`v2_universe_hash_85b0871b5a5e0cc5aef399eabd65cd8cd5ba656af18f127098c2bc57647e4b34`).
- **Both-exist banner**: AESI/DK/PL — only PL of the 6 drift tickers is on the both-exist banner.
- **L5 / Option A filter active**: `_compute_baseline_parity` at `sweep.py:545-557` filters `{'excluded', 'error'}` per merge `b7f70ff`. The 14 drift candidates should NOT be in those sentinel buckets — verify via SQL early in investigation.

---

## §7 NON-scope

- ZERO Phase 14 commissioning consideration (DEFERRED per Path B sequencing)
- ZERO promotion of V2 method-record from `research` → `shadow` (DEFERRED per OQ-8 ladder; gated on resolving this drift class OR characterizing as L6 limitation)
- ZERO modification of the binding-variable identification in the smoke artifact (operator-facing; preserve)
- ZERO V1 production code changes (production read-only invariant)
- ZERO Schwab API calls (L2 LOCK preserved)
- ZERO new schema migrations (schema v21 LOCKED)
- ZERO modification of V1 persisted candidate_criteria / candidates / evaluation_runs / trades rows

---

## §8 Post-investigation handback

When investigation findings + recommendation are documented:

1. Write findings document at `docs/v2-full-reproduction-drift-investigation-2026-MM-DD.md` per §3.1
2. Write return report at `docs/v2-full-reproduction-drift-investigation-return-report.md` per §3.4
3. Inline self-verification: ruff check (if code changes); schema unchanged; ZERO new Schwab API calls; ZERO Co-Authored-By footer; V1 persisted state unchanged; per-binding-variable study-impact assessment present in findings
4. Hand back to operator with: root cause + code:line citation; per-criterion divergence; drift-class scope; remediation recommendation; per-binding-variable study-impact assessment; V2 candidates banked.

Orchestrator-side next steps post-investigation:
- QA findings per `feedback_orchestrator_qa_implementer_product`
- Merge investigation branch `--no-ff` to main; push
- Post-merge housekeeping (sub-event scale; in-place amendments; NEW gotcha #26 if banked)
- Operator-paired decision on remediation path (depends on findings: data refresh, filter extension, V2 fix, OR L6 characterization)
- IF remediation requires V2 code fix: separate dispatch OR continue in same branch per scope
- IF drift class is non-blocking (e.g., expected OQ-14 universe-drift limitation): characterize as L6 in method-record v0.2.1 → v0.2.2 amendment + study writeup proceeds with binding-variable findings (per §5 impact analysis)
- IF drift class invalidates ≥3 binding variables: study writeup pauses pending remediation re-run

---

*End of V2 OHLCV full-63-eval-run reproduction CRITERION DRIFT triage dispatch brief. Investigation scope only; remediation follows. 5 narrowed hypotheses (L4 parallel-archive desync conditionally-in for PL; L5 sentinel-bucket ruled out via Option A filter; H2 OQ-14 universe drift strong candidate for tickers without Shape A; H3 source-ladder asymmetry secondary candidate; H4 sentinel-class extension; H5 coverage threshold). Deliverable = findings + per-criterion divergence + remediation recommendation + per-binding-variable study impact assessment. ~503+ ZERO Co-Authored-By footer streak preserved through this brief commit. Investigation gates research → shadow promotion gate (condition 1 baseline parity green); condition 3 (binding variables) SATISFIED.*
