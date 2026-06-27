# Phase 13 T2.SB3 — Pipeline integration recon (T-A.3.1)

**Status:** RECON COMPLETE. Drafted 2026-05-20 PM on branch `phase13-t2-sb3-detectors-batch1` (worktree branched from main HEAD `71739ed`). Closes Step 1 + Step 2 of task T-A.3.1 per plan §G.4 + dispatch brief §1.2.

**Scope:** This doc anchors the T-A.3.6 pipeline integration task by enumerating:

1. The integration-point decision (NEW step vs extend existing).
2. Per-detector evaluation order.
3. `pattern_evaluations` write discipline.
4. Per-mode `anchor_date` contract for detectors consuming `generate_candidate_windows` output.
5. Sandbox gating decision.
6. Foundation primitive consumers per detector.
7. Pattern_evaluations row shape (columns the step writes).

Read-only on production code: this is a recon pass; no edits to `swing/pipeline/runner.py` here.

---

## §1 Decision: NEW `_step_pattern_detect` step

**Decision:** ship a NEW `_step_pattern_detect` step. Do NOT extend `_step_evaluate`.

**Rationale (citations to `swing/pipeline/runner.py` at HEAD of this worktree):**

- `_step_evaluate` (defined at runner.py:953) is already a large unit responsible for:
  - reading the validated Finviz CSV,
  - building the sector/industry passthrough dict (runner.py:970-980),
  - unioning open-trade tickers into the OHLCV fetch loop (runner.py:982-998),
  - warming the optional Schwab market-data ladder via `_warm_pipeline_marketdata` (runner.py:1009-1011),
  - computing SPY benchmark return + RS-12w returns + batch evaluation,
  - writing `evaluation_runs` + `candidates` + `candidate_criteria` rows.
  Adding three rule-based geometric detectors (each consuming bars + foundation primitives) inside this function would (a) blur the Stage-2-evaluation responsibility with pattern-detection responsibility, and (b) make per-step failure surfacing harder — `_step_evaluate` is currently treated as fatal (runner.py:766-773 `lease.release(state='failed')` on exception), whereas pattern detection should be best-effort like `_step_watchlist` / `_step_recommendations` / `_step_charts` (each catches Exception + sets a degraded `lease.status(...)` without aborting the run).
- The existing pipeline step boundaries already follow a single-responsibility pattern: `evaluate` -> `daily_management` -> `watchlist` -> `recommendations` -> `schwab_snapshot` -> `schwab_orders` -> `charts` -> `export` -> `complete`. A NEW `pattern_detect` step slots cleanly between `recommendations` and `schwab_snapshot` (Section 2 below) and inherits the same try/except + `lease.status(...)` shape.
- Spec §5.1.3 line 506 binds the per-pipeline-run scope: candidate-window generation runs ONCE per pipeline run AFTER trend-template filter + RS-rank filter (i.e., AFTER `_step_evaluate`). Detector pipeline integration consumes the same Stage-2-filtered + RS-rank-filtered candidate pool. A NEW step honors this AFTER-`_step_evaluate` ordering directly.
- The `pattern_evaluations` table has FK `pipeline_run_id` -> `pipeline_runs(id)` (per migration `0020_phase13_charts_patterns_autofill_usability.sql:232-233`). It does NOT FK to `evaluation_runs(id)`. Owning the write in a dedicated step makes the `pipeline_run_id` = `lease.run_id` binding explicit (Section 4 below) — folding into `_step_evaluate` would muddy the dual-id story (that function returns the `evaluation_runs.id` integer; the new writes need `pipeline_runs.id`).

**Conclusion:** NEW `_step_pattern_detect` step. This matches the dispatch brief §1.2 default and is reinforced by reading the runner end-to-end.

---

## §2 Integration point — exact location in runner.py

**Insertion location:** between `_step_recommendations` (runner.py:806-817) and `_step_schwab_snapshot` (runner.py:835-862).

**Concretely:** insert a new `lease.step("pattern_detect")` + try/except block AFTER runner.py:817 (the existing `except Exception: lease.status(recommendations_status="failed")` line) and BEFORE runner.py:819 (the comment block introducing the Schwab snapshot step at "Phase 11 Sub-bundle B (T-B.3 + T-B.4 ...)").

**Sequencing rationale:**

- MUST run AFTER `_step_evaluate` (runner.py:757-773) because detection consumes Stage-2-filtered + RS-rank-filtered candidates (spec §5.1.3 line 506 LOCK). `_step_evaluate` returns `eval_run_id`; detectors consume `candidates` rows via that id.
- MAY run before OR after `_step_daily_management` / `_step_watchlist` / `_step_recommendations`. Brief default = AFTER `_step_recommendations`. Rationale:
  - Detection feeds the briefing emitter at `_step_export` (runner.py:903-915) — placing detection AFTER recommendations groups all "value-chain" steps together before the chart/export tail.
  - Detection does NOT depend on `_step_recommendations` outputs; the ordering is purely organizational.
  - `_step_daily_management` / `_step_watchlist` / `_step_recommendations` do not depend on `pattern_evaluations` rows either, so there is no upstream / downstream dependency cycle.
- MUST run BEFORE `_step_charts` (runner.py:886-901) because T2.SB6 (future) will couple chart annotations to `pattern_evaluations.structural_evidence_json`. T2.SB3 itself does NOT bind that coupling, but inserting detection BEFORE charts pre-empts the dependency-inversion problem when T2.SB6 lands.
- MUST run BEFORE `_step_export` (runner.py:903-915) because the briefing.md emitter at T2.SB6 will consume verdicts.

**Failure mode:** detection is best-effort. Failure path mirrors `_step_watchlist` (runner.py:794-804) — catch `Exception`, log warning, `lease.status(pattern_detect_status="failed")`, continue.

**Signature** (proposed for T-A.3.6 dispatch):

```python
def _step_pattern_detect(
    *,
    cfg: Config,
    lease: Lease,
    eval_run_id: int,
    ohlcv_cache: OhlcvCache,
) -> None:
```

- `cfg` — read sandbox-environment field (Section 6 below) + any tunables.
- `lease` — the step uses `lease.fenced_write()` to acquire the connection for write; `lease.run_id` is the `pipeline_runs.id` that becomes `pattern_evaluations.pipeline_run_id`.
- `eval_run_id` — passed for consumer ergonomics (allows `fetch_candidates_for_run(conn, eval_run_id)` from `swing.data.repos.candidates`).
- `ohlcv_cache` — already constructed at runner.py:749-755; pass through so the detectors see the same ladder-routed bars `_step_charts` consumes.

**No new caller-side caller-tx requirement on existing callers:** the step owns its own write transaction via `lease.fenced_write()` (caller-tx contract documented in Section 4 below).

---

## §3 Per-detector evaluation order

Three detectors run independently per `(ticker, candidate_window)`. Each emits one `pattern_evaluations` row per `(ticker, pattern_class)`.

**Evaluation order:** `vcp` -> `flat_base` -> `cup_with_handle`.

**Rationale for fixing the order:**

- Ordering matters for nothing except log-line determinism. The unique index `idx_pattern_evaluations_run_ticker_class` (migration line 253-254) is on `(pipeline_run_id, ticker, pattern_class)` — collisions between detector classes are impossible (each writes a distinct row).
- All three detectors are PURE FUNCTIONS per LOCK L2 (dispatch brief §6 L2). No shared mutable state.
- Order is documented here so post-merge log diffs / regression debugging have a stable reference. Implementation MUST iterate the three detectors via a `tuple[Callable[..., Evidence], str]`-style registry (NOT a Python `set` whose iteration order differs across runs).

**Per-ticker iteration:** outer loop over `(ticker, candidate_windows[ticker])`; inner loop over the 3 detector classes. Skip the ticker if `generate_candidate_windows` returned zero windows for it; log INFO with the skip reason (see Section 4 below for zero-candidate handling).

**Concurrency:** V1 is single-threaded. Detectors are CPU-bound + pure; V2 may parallelize via `concurrent.futures.ProcessPoolExecutor`. Out of scope for T2.SB3.

---

## §4 `pattern_evaluations` write discipline

### §4.1 Caller-tx vs own-tx

`_step_pattern_detect` is a STEP-LAYER function. It owns its own write transaction. Pattern follows existing precedent at `_step_recommendations` (runner.py:1214-1217):

```python
# Write phase (lease-fenced).
with lease.fenced_write() as conn:
    for row in rows_to_write:
        ...
```

`lease.fenced_write()` (see `swing/pipeline/lease.py:124-132`) opens the connection under a fence check + the underlying `with conn:` yields the standard SQLite deferred transaction. The write block:

1. Verifies the lease is still held (raises `LeaseRevokedError` if not).
2. Wraps the body in `with conn:` so SQLite issues an implicit BEGIN/COMMIT (or ROLLBACK on exception).

**Choice for T2.SB3:** use `lease.fenced_write()` for the SELECT-then-INSERT write block. The 3 detectors run BEFORE the write block (pure function calls); the write block atomically INSERTs all rows for this pipeline run.

**Strict explicit BEGIN IMMEDIATE? NO for V1.** The `_step_pattern_detect` writes do not interleave with any other concurrent writer (the lease fence + pipeline_runs `state='running'` row are the SQLite-level write-exclusion mechanism). The existing `_step_recommendations` and `_step_watchlist` precedents both rely on `lease.fenced_write()` rather than explicit `BEGIN IMMEDIATE`; T2.SB3 inherits that convention.

**No nested transaction concern:** detectors are pure functions; they never call `with conn:` themselves; LOCK L2 (ZERO DB writes inside detector functions) precludes any of the transactional-discipline failure modes documented in CLAUDE.md (service-layer `with conn:` opens its own transaction; `in_transaction` auto-detect anti-pattern; etc.).

### §4.2 SELECT-then-INSERT idempotency (NO `INSERT OR REPLACE`)

LOCK L3 binds per dispatch brief §6: NO `INSERT OR REPLACE` on `pattern_evaluations`. The CLAUDE.md gotcha "SQLite `INSERT OR REPLACE` is `DELETE old + INSERT new` semantically" binds here:

1. `pattern_evaluations` has `id INTEGER PRIMARY KEY AUTOINCREMENT` (migration line 231); REPLACE would re-issue a NEW autoincrement id even for the same `(pipeline_run_id, ticker, pattern_class)` tuple, breaking any future audit reference.
2. While `pattern_evaluations` does NOT have child FK references TODAY, the spec §3.6 v21+ candidates flag a `feature_drift_baseline` table that may carry an FK to `pattern_evaluations.id`. REPLACE would CASCADE-WIPE such future child rows.
3. The unique index `idx_pattern_evaluations_run_ticker_class` (migration line 253-254) prevents duplicate inserts on the same tuple — a naive `INSERT` against an already-populated tuple raises `IntegrityError`. The SELECT-then-INSERT pattern handles this idempotently:

```python
existing = conn.execute(
    "SELECT id FROM pattern_evaluations "
    "WHERE pipeline_run_id = ? AND ticker = ? AND pattern_class = ?",
    (pipeline_run_id, ticker, pattern_class),
).fetchone()
if existing is not None:
    # Idempotent re-invocation: skip. Log INFO with existing id.
    log.info("pattern_evaluations row exists for (%d, %s, %s); skipping",
             pipeline_run_id, ticker, pattern_class)
    continue
conn.execute("INSERT INTO pattern_evaluations (...) VALUES (...)", (...))
```

**Idempotency contract:** re-running `_step_pattern_detect` against the same `(eval_run_id, lease.run_id)` MUST be safe — either skip existing rows (V1 default) or overwrite-via-UPDATE (V2 if operator workflow demands re-detect). V1 SKIP is the simpler default; V2 if/when the use case emerges.

**Discriminating test pattern for T-A.3.6:** plant a `pattern_evaluations` row at `(lease.run_id, "FOO", "vcp")` then invoke `_step_pattern_detect` again under the same lease; assert no `IntegrityError` raised + row count unchanged + log INFO line emitted.

### §4.3 Zero-candidate-windows graceful handling

If `generate_candidate_windows(bars, ...)` returns an empty list for every ticker (e.g., post-evaluate Stage-2 set is empty; or every ticker fails the zigzag anchor search), `_step_pattern_detect` MUST:

1. Open `lease.fenced_write()` for fence verification (lease still held?).
2. Log INFO with reason ("no candidate windows generated for any Stage-2 ticker").
3. `lease.status(pattern_detect_status="ok")` — the empty case is a normal outcome, not a failure.
4. Return without writes.

Discriminating-test target: T-A.3.6 acceptance criterion #4 ("zero-candidate-windows succeeds without writes").

### §4.4 Per-detector failure inside the step

If one of the three detectors raises (e.g., NaN bar in unsanitized fixture; programming error in `Contraction` dataclass `__post_init__`), the step:

1. Logs WARNING with the ticker + pattern_class + exception type + truncated message.
2. Skips that `(ticker, pattern_class)` write.
3. CONTINUES to the next pattern_class + next ticker.
4. The step itself returns success (other detectors / tickers may have written rows).

Per-detector failures do NOT abort the run. The pipeline `_step_pattern_detect`-wrapping try/except in `run_pipeline_internal` catches only programming-error escapes (unhandled exceptions outside the per-detector loop).

---

## §5 Per-mode `anchor_date` contract for detectors

Per spec §5.1.3 LOCK + T2.SB2 forward-binding lesson #2 (banked at HEAD `71739ed` housekeeping), `generate_candidate_windows` emits 3 anchor modes with DIFFERENT `anchor_date` semantics. See `swing/patterns/foundation.py:376-388` (CandidateWindow dataclass) + `swing/patterns/foundation.py:456-...` (generate_candidate_windows docstring):

| anchor_search_method | `anchor_date` semantic | Detector backward-slice needed? |
|---|---|---|
| `zigzag_pivot` | inferred base START (matches spec §5.1.3 line 502 abstraction) | NO — `anchor_date` IS the base start |
| `ma_crossover` | trigger event date (MA50 crosses above MA150); NOT base start | YES — detector backward-slices from `anchor_date` to find the base start |
| `high_low_breakout` | breakout confirmation bar (close exceeds prior 50-bar high); NOT base start | YES — detector backward-slices from `anchor_date` to find the base start |

**T2.SB3 detector contract:** each of the 3 detectors (`detect_vcp`, `detect_flat_base`, `detect_cup_with_handle`) consumes a `CandidateWindow` AND the full bars DataFrame. For non-`zigzag_pivot` modes, the detector MUST:

1. Read `window.anchor_reason` (V1 format = `'<mode>:<descriptor>'`).
2. If the mode prefix is `ma_crossover` or `high_low_breakout`, backward-slice from `anchor_date` to locate the base start. Backward-slice mechanic varies per detector:
   - **VCP** (spec §5.2 criterion #1): find the most-recent prior swing-LOW that precedes the trigger by at least the "8-week prior uptrend" requirement (criterion #2). The base START is the swing-LOW where the contraction sequence begins.
   - **flat_base** (spec §5.3 criterion #2 + #6): find the most-recent prior swing-LOW that precedes the trigger by at least 5 weeks (`(base_end - base_start).days >= 35`). The base START is that swing-LOW.
   - **cup_with_handle** (spec §5.4 criterion #2): find the cup left edge by walking BACK from the trigger to find the most-recent prior swing-HIGH. The base START is that swing-HIGH.
3. If the backward-slice fails (no suitable prior swing found), the detector emits an evidence dataclass with `geometric_score == 0.0` and `criteria_pass['<criterion_1>'] == False` (the Stage-2-uptrend hard gate captures upstream context; the missing-base-start failure is downstream noise).

**Discriminating test for T-A.3.6 acceptance criterion (per dispatch brief §4.2 #11):** feed a `ma_crossover` candidate window where `anchor_date == trigger_date`; assert detector backward-slices to find the base start (not anchor_date itself).

**T-A.3.2 / T-A.3.3 / T-A.3.4 implication:** each detector implements its own backward-slice helper. The 3 helpers should NOT be shared in a single util (the swing-LOW vs swing-HIGH semantics differ); separate helpers per detector are clearer.

---

## §6 Sandbox gating decision

**Decision:** NO sandbox gating on `_step_pattern_detect`.

**Rationale:**

- Sandbox gating exists at the Schwab integration boundary to prevent SYNTHETIC Schwab data from contaminating production rows (per CLAUDE.md gotcha "Schwab API integration writes domain rows ONLY when `cfg.integrations.schwab.environment == 'production'`"). Affected surfaces are `_step_schwab_snapshot`, `_step_schwab_orders`, `apply_tier1_correction`, and the market-data ladder layer (`PriceCache` / `OhlcvCache` fall-through to yfinance under sandbox).
- `_step_pattern_detect` consumes bars via the SAME `ohlcv_cache` that `_step_charts` consumes (runner.py:749-755 + 886-893). Under `environment='sandbox'`, that cache is ALREADY routed through yfinance (per the Schwab gotcha above + runner.py:749-755 fallback to ladder-less OhlcvCache when `_install_pipeline_marketdata_caches` returns None). Detectors see real-yfinance bars regardless of sandbox setting.
- The `pattern_evaluations` table is NOT a Schwab-derived integrity surface. It is an internal-derivation surface: geometric verdicts computed from bars by pure rule-based functions. There is no equivalent "synthetic Schwab data contamination" failure mode for `pattern_evaluations` — the bars upstream determine the verdict; verdicts are deterministic given bars.
- Adding a sandbox short-circuit would create a NEW degraded-data surface (no `pattern_evaluations` rows under sandbox), which would cascade into T2.SB6 chart annotation gaps + briefing emitter no-ops under sandbox. No operator-value benefit; only degraded-UX cost.

**V2 reconsideration trigger:** if a future sub-bundle introduces a detector path that calls Schwab directly (e.g., Phase 14 fundamentals overlay consuming `/v1/marketdata/{symbol}/fundamentals`), THAT path inherits sandbox gating. The `_step_pattern_detect` step layer itself remains environment-agnostic.

---

## §7 Foundation primitive consumers per detector

Per spec §5.1 (T2.SB2 foundation primitives) + spec §5.2 / §5.3 / §5.4 criteria. Functions sourced from `swing/patterns/foundation.py`:

### §7.1 VCP detector (spec §5.2; T-A.3.2)

- `current_stage(conn, ticker, asof_date)` -> criterion #1 (Stage-2-uptrend hard gate).
- `extract_zigzag_swings(bars, ...)` -> identifies the contraction sequence boundaries for criteria #3 + #4.
- `volume_trend_through_swings(bars, swings)` -> criterion #5 (volume declines through contractions). Consumes `VolumeSegment` dataclass (foundation.py:610).
- `breakout_volume_ratio(bars, breakout_date, baseline_days=50)` -> criterion #8 (optional breakout-volume confirmation).
- `adaptive_initial_threshold_pct(bars)` -> tunes the zigzag threshold for the per-ticker volatility regime (consumed by `extract_zigzag_swings`).
- Either `smooth_ema(...)` OR `smooth_kernel_regression(...)` -> per-bar trend smoothing for criterion #2 (prior 30% uptrend over 8 weeks).

### §7.2 flat_base detector (spec §5.3; T-A.3.3)

- `current_stage(conn, ticker, asof_date)` -> criterion #1 (Stage-2-uptrend hard gate).
- `extract_zigzag_swings(bars, ...)` -> bounds the base range top + bottom for criterion #3.
- Linear regression over base-mid-range close (NOT a foundation primitive; pure NumPy `np.polyfit(...)` inline) -> criterion #4 (slope <= 0.005/week).
- ATR over 5-day windows (NOT a foundation primitive; pure NumPy mean of (high - low) inline) -> criterion #5 (mean_atr_pct <= 0.025).

### §7.3 cup_with_handle detector (spec §5.4; T-A.3.4)

- `current_stage(conn, ticker, asof_date)` -> criterion #1 (Stage-2-uptrend hard gate).
- `extract_zigzag_swings(bars, ...)` -> identifies cup_left_edge_date / cup_bottom_date / cup_right_edge_date / handle_low_date for criteria #2 + #3 + #5 + #6.
- `volume_trend_through_swings(bars, swings)` -> criterion #8 (volume drying up during handle; consumes `VolumeSegment.avg_volume`).
- `_is_rounded_cup(bars, cup_bottom_date)` -> spec §10.7 + §D.11 LOCK: 5-bars-in-marginal-window predicate for the rounded-vs-V hard gate (criterion #3 modifier). Per dispatch brief §1.1 #8 + L5 LOCK: HARD PASS / 0.10 PENALTY (marginal) / HARD FAIL semantics.

### §7.4 Shared NaN sanitizer

Per dispatch brief §1.1 #3 forward-binding lesson: all 3 detectors call a shared NaN sanitizer BEFORE invoking foundation primitives. yfinance / Schwab archives carry NaN holiday-adjacent rows; foundation primitives reject NaN at entry. Location: NEW `swing/patterns/_sanitize.py` (optional per brief §3) OR reuse existing helper. Implementation deferred to T-A.3.2 (first detector + first consumer).

---

## §8 Pattern_evaluations row shape

Per `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql:230-250` (15 columns total).

| Column | Type | Nullable | Source |
|---|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | (auto) | autoincrement on INSERT |
| `pipeline_run_id` | INTEGER NOT NULL FK -> `pipeline_runs(id)` ON DELETE CASCADE | NO | `lease.run_id` (the pipeline_runs row id; NOT `eval_run_id`) |
| `ticker` | TEXT NOT NULL | NO | candidate ticker (uppercased) |
| `pattern_class` | TEXT NOT NULL CHECK IN (5 V1 classes) | NO | one of `'vcp'`, `'flat_base'`, `'cup_with_handle'`, `'high_tight_flag'`, `'double_bottom_w'`. T2.SB3 writes 3 of 5 (high_tight_flag + double_bottom_w land at T2.SB4). |
| `detector_version` | TEXT NOT NULL | NO | per-detector version string (e.g., `'vcp@v1.0.0'`). Pin via a module-level constant in each detector file; bump at any algorithm change. |
| `geometric_score` | REAL NOT NULL | NO | 0..1 numeric verdict; weighted sum of criteria pass/fail per spec §5.8. |
| `geometric_score_json` | TEXT NOT NULL | NO | JSON-serialized per-criterion granular pass/fail dict (matches the `criteria_pass` field on the evidence dataclass). |
| `template_match_score` | REAL | YES | NULL in T2.SB3 (template matching lands at T2.SB5). |
| `template_match_nearest_exemplar_ids_json` | TEXT | YES | NULL in T2.SB3. |
| `composite_score` | REAL NOT NULL | NO | T2.SB3 = `geometric_score` (no template-match component yet; T2.SB5 will widen to `0.5 * geometric_score + 0.5 * template_match_score`). |
| `structural_evidence_json` | TEXT NOT NULL | NO | JSON-serialized evidence dataclass (VCPEvidence / FlatBaseEvidence / CupWithHandleEvidence per spec §5.2 / §5.3 / §5.4). Frozen dataclass with `__post_init__` Literal[...] validation. |
| `feature_distribution_log_json` | TEXT NOT NULL | NO | JSON-serialized `FeatureDistributionLog` dataclass per spec §D.7 + OQ-9 disposition (V1 LOCK = JSON column on `pattern_evaluations`; V2 dedicated table only if Phase 13.5 demands). T-A.3.5 deliverable. |
| `window_start_date` | TEXT NOT NULL | NO | ISO-format date string; the candidate window's `start_date`. |
| `window_end_date` | TEXT NOT NULL | NO | ISO-format date string; the candidate window's `end_date`. |
| `created_at` | TEXT NOT NULL | NO | ISO-format timestamp at INSERT time (`datetime.now(timezone.utc).isoformat()`). |

**JSON-encoded columns** (4 total): `geometric_score_json`, `template_match_nearest_exemplar_ids_json` (NULL in T2.SB3), `structural_evidence_json`, `feature_distribution_log_json`.

**Encoding rule:** dataclass -> `dataclasses.asdict(...)` -> `json.dumps(..., default=str)` (dates serialize as ISO strings; floats serialize natively; tuples serialize as lists). Decode at read-time with `json.loads` + dataclass reconstruction helper.

**Production-shape fixture discipline:** per the CLAUDE.md "Synthetic-fixture-vs-production-emitter shape drift" gotcha family (now 4 cumulative instances banked), tests asserting JSON column shape MUST decode via the same `json.loads(...)` -> dataclass-reconstruction path that read-time consumers use; do NOT compare pre-serialized strings.

---

## §9 Summary + forward-binding to T-A.3.6

**Decision summary:**

1. NEW `_step_pattern_detect` step (Section 1).
2. Insertion at runner.py between `_step_recommendations` (line 817) and the Schwab snapshot block (line 819) (Section 2).
3. Evaluation order: vcp -> flat_base -> cup_with_handle (Section 3).
4. Caller-tx via `lease.fenced_write()`; SELECT-then-INSERT idempotency; NO `INSERT OR REPLACE` (Section 4).
5. Per-mode anchor_date backward-slicing required for `ma_crossover` + `high_low_breakout` modes (Section 5).
6. NO sandbox gating (Section 6).
7. Foundation primitives per detector enumerated (Section 7).
8. 15-column pattern_evaluations row shape locked (Section 8).

**Forward-binding to T-A.3.6 (pipeline integration task):**

- Implement `_step_pattern_detect` per the signature in Section 2.
- Implement the SELECT-then-INSERT idempotency pattern per Section 4.2.
- Implement zero-candidate handling per Section 4.3.
- Implement per-detector failure isolation per Section 4.4.
- Pass `lease.run_id` (NOT `eval_run_id`) as `pipeline_run_id` in the INSERT.
- Add discriminating tests:
  - `test_step_pattern_detect_idempotent_re_invocation` (Section 4.2).
  - `test_step_pattern_detect_zero_candidates_no_writes` (Section 4.3).
  - `test_step_pattern_detect_per_detector_failure_isolated` (Section 4.4).
  - `test_step_pattern_detect_writes_pipeline_run_id_not_eval_run_id` (Section 8; pins the dual-id distinction).

**Forward-binding to T-A.3.2 / T-A.3.3 / T-A.3.4 (per-detector tasks):**

- Per-mode anchor_date backward-slicing helper per detector (Section 5).
- Shared NaN sanitizer call BEFORE foundation primitive invocation (Section 7.4).
- Production-shape JSON encoding for `structural_evidence_json` (Section 8).

**Forward-binding to T-A.3.5 (drift_logging task):**

- `FeatureDistributionLog` dataclass shape per spec §D.7 (Section 8).
- JSON-encoded column `feature_distribution_log_json`; one log per row (Section 8).

---

*End of recon. Closes T-A.3.1 Step 2 per plan §G.4. Commit message: `docs(phase13): T2.SB3 pipeline integration recon (T-A.3.1)` with NO Co-Authored-By footer (ZERO trailer drift across ~249+ commits BINDING).*
