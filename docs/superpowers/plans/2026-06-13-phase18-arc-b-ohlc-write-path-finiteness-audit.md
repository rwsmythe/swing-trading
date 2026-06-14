# Phase 18 Arc 18-B — OHLC Write-Path Finiteness Audit & Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catch the CLASS that 18-A fixed one instance of. 18-A guarded the temporal-log writer (the second of two OHLC write paths) through the shared `swing/data/ohlcv_finiteness.py:is_finite_ohlc` predicate (C1). 18-B enumerates EVERY OHLC-bar persistence-write boundary in `swing/`, verifies each enforces finiteness via that ONE shared predicate, and closes the genuine gap so a third path cannot silently diverge.

**The audit's verdict (one gap):** the exhaustive enumeration (§1) found exactly ONE GAP — the **Schwab market-data ladder write path** (`swing/integrations/schwab/marketdata_ladder.py:_persist_window_to_archive` → `swing/data/ohlcv_archive.write_window`). It writes a freshly-FETCHED OHLC window (Schwab API bars OR a yfinance fallback window) into the Shape-A archive store (`{TICKER}.{provider}.parquet`) that `resolve_ohlcv_window` reads — and it does NOT apply the Arc-8 trailing-ragged finiteness barrier, whereas its SIBLING legacy-archive writer (`read_or_fetch_archive` via `_yf_download_window` / `_warm_one_window`) DOES. This is the exact two-path divergence (the #24–#26 parallel-archive family) the arc exists to kill.

**Architecture (the gap-closure):** Apply `_trim_trailing_ragged` (which already consumes the shared `is_finite_ohlc` predicate, from 18-A) to the INCOMING window inside `_persist_window_to_archive`, BEFORE it calls `write_window` — mirroring EXACTLY how the legacy serial (`_yf_download_window`) and warm (`_warm_one_window`) ingest paths trim their incoming fetch before writing. This:
- Routes through the ONE shared predicate (C1; NO new finiteness copy).
- Preserves the import-direction lock: `swing/integrations/schwab` → `swing/data` (allowed; the converse is never created).
- Preserves the interior-bar posture (LOCK 4): `_trim_trailing_ragged` is TRAILING-only — interior non-finite bars are PRESERVED, only the newest non-finite bar(s) are trimmed.
- Leaves `validate_bars` UNTOUCHED (LOCK 1) and `write_window`/`_write_archive_atomic` UNTOUCHED (the merge/completed-day chokepoint stays as-is; the finiteness trim happens at ingest, on the incoming window, exactly where the legacy paths do it).
- Requires NO schema change.

**Tech Stack:** Python 3.14, pandas, pytest (`-m "not slow"`), ruff. No new dependencies. **NO schema change, NO migration, NO data mutation.**

---

## Environment / shell note (read first)

All commands in this plan run in the **executing implementer's Windows shell** inside the worktree at `<repo>/.worktrees/phase18-arc-b`, where the worktree's `.git` resolves natively — `git add`/`git commit`/`git diff` work normally. The **bash-shaped snippets** (the Task 3 self-audit `grep`/pipe/`||` block) assume **Git Bash** — this project's POSIX shell, per CLAUDE.md "Windows + gitbash"; the single-line `pytest`/`ruff`/`git` commands run equally in Git Bash or PowerShell. **WSL is NOT the execution environment.** WSL is used ONLY for the writing-plans/executing-plans **Codex adversarial review** (the worktree `.git` is a file WSL cannot resolve, so the Codex invocation never runs `git`). Do not run this plan's git/commit steps inside WSL.

---

## Context the implementer needs (read before starting)

### The 18-A baseline this arc extends (already on `main`, `c45d8752`)

- The shared predicate `swing/data/ohlcv_finiteness.py:is_finite_ohlc(*values) -> bool` — `math.isfinite` over bare OHLC VALUES (volume EXEMPT by construction; empty call → True; finiteness ONLY, no `>= 0`). This is the ONE source of truth; do NOT add a second finiteness implementation anywhere (C1).
- `swing/data/ohlcv_archive.py:_trim_trailing_ragged(df) -> (df, n)` ([ohlcv_archive.py:204](../../../swing/data/ohlcv_archive.py#L204)) — the Arc-8 barrier: iterate from the END of a DataFrame, drop trailing rows where ANY of `Open/High/Low/Close` is non-finite (now via `is_finite_ohlc`); STOP at the first clean trailing row (interior preserved); volume excluded from the `ohlc` column list so volume-only-NaN never trims. Returns the trimmed frame + count.
- It is applied at TWO legacy ingest sites: the serial `_yf_download_window` return ([ohlcv_archive.py:264](../../../swing/data/ohlcv_archive.py#L264)) and the warm `_warm_one_window` per-ticker loop ([ohlcv_archive.py:697](../../../swing/data/ohlcv_archive.py#L697)). Both emit a `log.warning` ("dropped N trailing non-finite OHLC bar(s)") and skip a trim-to-empty without fallback.
- The temporal-log path is doubly guarded: `build_ohlc_today_json` ([temporal_metadata.py:186](../../../swing/pipeline/temporal_metadata.py#L186)) raises on non-finite (belt-and-suspenders), and `_step_pattern_observe` ([runner.py:2995](../../../swing/pipeline/runner.py#L2995)) skips-with-warning (`reason="non_finite_ohlc"`) BEFORE building the row.

### The measurement chain (verified end-to-end — defines what "measurement-consumed" means)

The shadow-expectancy engine (`research/harness/shadow_expectancy/`) is the instrument. `io.py` shows it reads from EXACTLY THREE DB stores:
- `candidates` (via `fetch_candidates_for_run`) — but `validate.py:validate_candidate_levels` documents that **"the screening pivot is the SOLE candidate field the mechanical trade consumes"**; `candidate.close`/`initial_stop` are NOT consumed as OHLC bars, and the pivot has its OWN engine-side belt (`validate_candidate_levels`: null/non-finite/<=0 → `no_candidate_pivot`).
- `pattern_forward_observations` (via `get_observations_for_detection`) — the `ohlc_today_json` bars → `parse_bar` → `Bar` → `validate_bars`. THIS is the OHLC-bar measurement input. Its write path is GUARDED (18-A).
- `pattern_detection_events` (via `list_detection_events`) — detection identity/geometry metadata; no OHLC bars.

The engine reads NO parquet directly. The prices-cache archive (legacy + Shape-A) feeds the measurement ONLY indirectly, via `_bar_for_date` → the temporal-log write path (which has its own 18-A finiteness skip).

### Why the Schwab-ladder write is still a GAP (despite the downstream temporal-log guard)

`_bar_for_date` ([runner.py:2841](../../../swing/pipeline/runner.py#L2841)) reads the Shape-A archive via `resolve_ohlcv_window`. So a non-finite bar that the Schwab ladder writes into the Shape-A archive is, TODAY, caught one layer downstream by the 18-A `_step_pattern_observe` skip before it can enter the temporal log. The mandate (§1, §2 of the brief) is NOT "is a NaN reaching the measurement today" — it is **"every OHLC-bar persistence-write boundary must enforce finiteness via the shared predicate, so a third path can't silently diverge."** The Shape-A archive is a persisted OHLC-bar store the pipeline consumes (charts, SMAs, the temporal-log bar source); its sibling writer is guarded and this one is not. Closing it at the write boundary (not relying on a single downstream consumer's guard) is the divergence-class fix — and it hardens the archive against future consumers that may NOT re-check finiteness (the #26 anti-drift guarantee).

### The exact gap-closure callsite

`_persist_window_to_archive` ([marketdata_ladder.py:165](../../../swing/integrations/schwab/marketdata_ladder.py#L165)) converts the ladder's window to a Shape-A DataFrame (`df`, lowercase OHLCV columns + an `asof_date` column) then calls `write_window(ticker, df, provider, cache_dir=cache_dir)`. The finiteness trim is inserted on `df` AFTER the `if df is None: return` guard and BEFORE `write_window`. `_trim_trailing_ragged` keys on the CAPITALIZED `Open/High/Low/Close` column list (`[c for c in ("Open","High","Low","Close") if c in df.columns]`); the Shape-A df has LOWERCASE `open/high/low/close`, so a literal call would no-op (the `ohlc` list would be empty → returns `(df, 0)`). The closure therefore needs a thin shape-agnostic application — see Resolved decision #2.

---

## Binding conditions / LOCKS (QA'd at the merge gate by orchestrator + CHARC + RD)

- **C1** — close via the ONE shared `is_finite_ohlc` predicate (reused transitively through `_trim_trailing_ragged`, which already consumes it). NO new finiteness copy anywhere. Import direction strictly `swing/integrations` → `swing/data` (and `swing/data` → `swing/data`); `swing/data` NEVER imports `swing/pipeline`.
- **LOCK 1** — `validate_bars` (`research/harness/shadow_expectancy/validate.py`) UNTOUCHED.
- **LOCK 2 (parity)** — writer↔engine finiteness parity preserved: the gap-closure uses the shared predicate (via `_trim_trailing_ragged`), so the Schwab-ladder write path rejects EXACTLY the engine's finiteness set (`math.isfinite`, OHLC-only, volume-exempt; no `>= 0` — that stays the engine's job).
- **LOCK 3 (NO schema)** — audit + a guard insertion only. If the audit had found a gap requiring a migration, the plan would STOP and route to CHARC (schema tripwire). It did NOT — the one gap closes with zero schema change.
- **LOCK 4 (interior-bar posture)** — guard non-finite at the WRITE boundary only, TRAILING-only. `_trim_trailing_ragged` preserves interior non-finite bars (Phase-15 bad-bar-accept for HISTORICAL interior bars unchanged). The merge/completed-day chokepoint `_write_archive_atomic` is NOT touched (so no full-archive interior trim risk).
- **LOCK 5 (discriminating test)** — the gap-closure carries a real-shape discriminating test: a Schwab-fetched window whose TRAILING bar has `Close=NaN` (O/H/L/V finite — the 06-10 artifact) is trimmed before write (RED pre-fix: the NaN bar persists to the Shape-A parquet); a fully-valid window writes unchanged (stays green); a volume-only-NaN trailing bar is NOT trimmed (volume-exempt discriminator). Pre/post arithmetic shown in Task 2 Step 2.

---

## 1. The exhaustive enumeration & classification (the writing-plans deliverable)

Audit-to-confirm (§5.7 — NO pre-asserted count). Every OHLC-bar persistence-write boundary in `swing/`, classified GUARDED / GAP / OUT. Grounded against live worktree code (post-18-A `main`).

| # | Path (file:func) | Writes what, to where | Classification | Reason |
|---|---|---|---|---|
| 1 | `swing/data/ohlcv_archive.py:_yf_download_window` (serial legacy fetch → `read_or_fetch_archive` write) | yfinance OHLCV → legacy `{TICKER}.parquet` | **GUARDED** | Applies `_trim_trailing_ragged` (→ `is_finite_ohlc`) on the incoming fetch BEFORE write ([:264](../../../swing/data/ohlcv_archive.py#L264)). 18-A. |
| 2 | `swing/data/ohlcv_archive.py:_warm_one_window` (warm-batch fetch) | yfinance OHLCV (both warm cohorts) → `{TICKER}.parquet` via `_merge_gap_subframe`/`_write_full_refresh_subframe` | **GUARDED** | Applies `_trim_trailing_ragged` per-ticker BEFORE merge ([:697](../../../swing/data/ohlcv_archive.py#L697)). 18-A. |
| 3 | `swing/pipeline/temporal_metadata.py:build_ohlc_today_json` | one bar-dict → serialized `ohlc_today_json` (the temporal log) | **GUARDED** | Belt-and-suspenders finiteness raise via `is_finite_ohlc` ([:186](../../../swing/pipeline/temporal_metadata.py#L186)). 18-A. |
| 4 | `swing/pipeline/runner.py:_step_pattern_observe` (caller of #3) | the bar that enters `pattern_forward_observations` | **GUARDED** | Skip-with-warning via `is_finite_ohlc` BEFORE the row is built ([:2995](../../../swing/pipeline/runner.py#L2995)). 18-A. |
| 5 | `swing/integrations/schwab/marketdata_ladder.py:_persist_window_to_archive` → `swing/data/ohlcv_archive.py:write_window` | a FETCHED window (Schwab API bars or a yfinance-fallback window) → Shape-A `{TICKER}.{provider}.parquet` | **GAP** | The OTHER archive writer. Writes a freshly-fetched OHLC window with NO finiteness barrier, unlike its sibling legacy writer (#1/#2). The Shape-A store is read by `resolve_ohlcv_window` → `_bar_for_date` (the temporal-log bar source) + chart/SMA consumers. Closes via `_trim_trailing_ragged` on the incoming window (Task 2). |
| 6 | `swing/data/ohlcv_archive.py:write_window` (the Shape-A merge writer itself) | merged Shape-A frame → parquet (via `_write_archive_atomic`) | **OUT** | Not the right consolidation locus. It operates on a FULLY-MERGED frame (full archive history + incoming); a finiteness barrier here would risk dropping INTERIOR non-finite bars (violates LOCK 4) or be a redundant trailing-only re-check. Finiteness belongs at INGEST (#5), exactly as the legacy paths do it. Left untouched. |
| 7 | `swing/data/ohlcv_archive.py:_write_archive_atomic` (the single Shape-A write chokepoint) | any frame → parquet; applies the completed-day strip | **OUT** | Same reasoning as #6 — operates on full merged history; adding finiteness here would over-reject interior bars or duplicate the ingest trim. The completed-day strip is a date barrier (orthogonal to finiteness). Untouched. |
| 7b | `swing/data/ohlcv_archive.py:_backward_compat_rename` (called by `resolve_ohlcv_window` on the read path) | normalizes EXISTING legacy `{TICKER}.parquet` rows → Shape-A `{TICKER}.yfinance.parquet` via `_write_archive_atomic` ([:1207-1209](../../../swing/data/ohlcv_archive.py#L1207), [:1286](../../../swing/data/ohlcv_archive.py#L1286)) | **OUT** | A LIVE persistence-write boundary into the Shape-A store (distinct from the one-time tool #18), but NOT an INGEST boundary: it performs NO external fetch — it RE-KEYS data ALREADY on disk (a pure shape transform via `normalize_legacy_dataframe`: DatetimeIndex+capitalized → asof_date+lowercase; no value mutation). The legacy `{TICKER}.parquet` it reads was written by `read_or_fetch_archive`/`_yf_download_window`, whose 18-A trailing-ragged barrier already finiteness-guarded the legacy archive's trailing bar at write time. So a NEW non-finite bar CANNOT enter here; the function only propagates the EXACT finiteness posture the guarded legacy archive already holds. Guarding it would be either a redundant trailing re-check OR — because it sees the FULL legacy history, not an incoming trailing window — an INTERIOR trim that would VIOLATE LOCK 4 (the Phase-15 bad-bar-accept posture for HISTORICAL interior bars). Documented; flagged for the gate. (Codex R1 MAJOR.) |
| 8 | `swing/data/repos/pattern_forward_observations.py:insert_observation` | a pre-serialized `ohlc_today_json` STRING → DB row | **OUT** | Dumb persist of an already-validated string; receives no raw OHLC values. Finiteness is enforced upstream at #3/#4 (the serializer + caller). |
| 9 | `swing/data/repos/candidates.py:insert_candidates` | `close`, `pivot`, `initial_stop` (derived scalars) → `candidates` | **OUT** | Not an OHLC bar. Per `validate.py`, the measurement consumes ONLY `candidate.pivot`, which has its OWN engine belt (`validate_candidate_levels`); `close`/`initial_stop` are not measurement bar inputs. No OHLC-bar persistence. |
| 10 | `swing/data/repos/pattern_detection_events.py:insert_detection_event` | `structural_anchors_json`, `composite_score`, `pattern_class` → `pattern_detection_events` | **OUT** | Derived detection geometry/scores, not OHLC bars. The measurement reads it for detection identity; the OHLC bars come from the temporal log (#3/#4). |
| 11 | `swing/data/repos/pattern_evaluations.py:insert_pattern_evaluation` | scores + `window_start/end_date` + JSON evidence → `pattern_evaluations` | **OUT** | Derived scores/geometry, not OHLC bars; not read by the measurement. |
| 12 | `swing/data/repos/pattern_classifications.py:insert_classification` | `pivot`, `pole_high`, `flag_low`, dates, scores → `pipeline_pattern_classifications` | **OUT** | Derived pattern landmarks (single levels), not OHLC bars; not measurement-consumed. |
| 13 | `swing/data/repos/pattern_exemplars.py:insert_exemplar` | exemplar ticker/dates/label/evidence → `pattern_exemplars` | **OUT** | Exemplar METADATA, not OHLC bars (exemplar bars live in the prices-cache archive, written via #1/#2/#5). |
| 14 | `swing/data/repos/weather.py:insert_weather_run`/`upsert_weather_run` | `close` + SMAs + slopes (a benchmark regime row) → `weather_runs` | **OUT** | Derived classification scalars (one benchmark `close`, not an OHLC bar). Source bars come from the guarded archive (#1/#2); not read by the measurement. |
| 15 | `swing/data/repos/daily_management.py:*` | `current_price`, `intraday_high`, `intraday_low`, R-metrics → `daily_management_records` | **OUT** | Per-trade operational management scalars (LIVE intraday values for an open trade's MFE/MAE), not completed-session OHLC bars; not measurement-consumed. |
| 16 | `swing/data/repos/account_equity_snapshots.py:record_snapshot` | equity dollars → `account_equity_snapshots` | **OUT** | Account equity, not OHLC bars. |
| 17 | `swing/pipeline/ohlcv.py:fetch_daily_bars` / `compute_smas` / `compute_adr_pct` / `previous_close` | reads bars; computes scalars | **OUT** | Read/COMPUTE path. `fetch_daily_bars` is a thin reader over `read_or_fetch_archive` (guarded #1); the compute helpers persist nothing. `compute_adr_pct` already independently no-ops on non-finite (`np.isfinite(...).all()`), but that is its own compute guard, not a write barrier. |
| 18 | `swing/tools/migrate_prices_cache.py:_consolidate_ticker` | re-keys EXISTING legacy `*_*d_asof-*.parquet` → per-ticker `{TICKER}.parquet` | **OUT** (borderline — flagged) | One-time operator migration tool (`python -m swing.tools.migrate_prices_cache`), run BEFORE the consumer-refactor commits; NOT in the live pipeline. It re-keys data ALREADY on disk — it performs NO external fetch, so it introduces NO new non-finite bar (it propagates only whatever already survived in legacy archives, which were written via the now-guarded #1/#2). Not a live OHLC INGEST boundary; outside the divergence class (a NEW non-finite bar cannot enter here). Documented for Codex scrutiny as the one debatable call. |
| 19 | `swing/evaluation/criteria/*` | consume OHLC to compute criteria | **OUT** | Read/COMPUTE; persist no bars (brief §2 explicit OUT). Not guarded (per scope). |

**Verdict:** 4 GUARDED (18-A), 1 GAP (#5, the Schwab-ladder write), 15 OUT (now 20 rows incl. #7b, added per Codex R1 MAJOR). The single gap closes with the shared predicate, no schema, no `validate_bars` touch.

**Why "exactly one GAP" holds after adding #7b:** the two LIVE Shape-A writers OTHER than the ladder ingest — `write_window`/`_write_archive_atomic` (#6/#7, the merge chokepoint) and `_backward_compat_rename` (#7b, the read-path re-keyer) — both operate on a FULL/MERGED frame and/or RE-KEY already-guarded on-disk data; neither is an INGEST boundary where a fresh non-finite bar can first enter the archive. The ONLY ingest boundary that fetches external OHLC and writes it to the Shape-A store WITHOUT the Arc-8 trailing barrier is the Schwab ladder (#5). Fresh non-finite OHLC enters the system at exactly three ingest boundaries — the legacy serial fetch (#1, GUARDED), the warm-batch fetch (#2, GUARDED), and the ladder fetch (#5, the GAP). Closing #5 completes coverage of the ingest class; the merge/re-key paths inherit the finiteness posture their already-guarded inputs carry.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `swing/integrations/schwab/marketdata_ladder.py` | Modify | `_persist_window_to_archive` trims the incoming Shape-A window via the shared barrier BEFORE `write_window` (the GAP closure). |
| `swing/data/ohlcv_archive.py` | Modify | Add a thin shape-agnostic wrapper so `_trim_trailing_ragged`'s shared-predicate barrier applies to a LOWERCASE-column Shape-A frame (the ladder's df shape) without a second finiteness copy. See Resolved decision #2. |
| `tests/integrations/schwab/test_marketdata_ladder.py` (or the existing ladder test module) | Modify | The GAP-closure discriminating tests (trailing-NaN trimmed before write; valid window unchanged; volume-only-NaN not trimmed). |
| `tests/data/test_ohlcv_archive_trailing_nan.py` | Modify | Unit test for the shape-agnostic wrapper (lowercase Shape-A frame: trailing NaN trimmed; interior NaN preserved; volume-only-NaN exempt). |

---

## Resolved plan-level design decisions (rationale)

1. **Close the gap at the LADDER ingest (`_persist_window_to_archive`), not at `write_window`/`_write_archive_atomic`.** The legacy paths (#1/#2) trim the INCOMING fetch before write; mirroring that at the ladder's incoming window is the parity-true, interior-safe placement. `write_window`/`_write_archive_atomic` operate on the full MERGED frame (archive history + incoming) — a finiteness barrier there would either drop interior non-finite bars (LOCK 4 violation) or be a redundant trailing-only re-check on a frame whose "trailing" semantics differ post-merge. Keep the merge chokepoint as the date-barrier only.

2. **Reuse `_trim_trailing_ragged` through a thin SHAPE-AGNOSTIC wrapper — do NOT add a second finiteness copy (C1).** `_trim_trailing_ragged` keys on CAPITALIZED `Open/High/Low/Close`; the ladder's Shape-A df has LOWERCASE `open/high/low/close`. Two options were considered:
   - **(a) Add a `columns=` parameter (or a lowercase-aware sibling) to `_trim_trailing_ragged`** so it can trim either column-case via the SAME `is_finite_ohlc` loop. CHOSEN. Implementation: generalize the `ohlc` column-detection to accept the relevant 4-tuple (default capitalized for the legacy callers; the ladder passes the lowercase tuple). The finiteness logic stays IDENTICAL (one `is_finite_ohlc` call); only the column-name list parameterizes. This adds ZERO finiteness logic — it is a column-name generalization of the EXISTING barrier. The function name `_trim_trailing_ragged` is shared `swing/data` infrastructure; `swing/integrations/schwab` importing it is the allowed `integrations → data` direction.
   - (b) Convert the Shape-A df to capitalized columns at the ladder, call the barrier, convert back. REJECTED — fragile column-renaming churn at the callsite; the parameterization in (a) is cleaner and keeps the one barrier authoritative.
   The implementer MUST verify (by reading the function) that the generalization keeps all existing capitalized-column callers behaviorally identical (default arg = the current `("Open","High","Low","Close")` tuple) — see Task 1.

3. **Trim BEFORE the `write_window` empty-window merge, and skip a trim-to-empty.** If trimming the incoming window empties it, the closure passes `None`/skips the `write_window` call (mirroring the legacy warm `if sub.empty: continue`). `write_window`'s own empty-incoming guard (F6) then leaves valid history intact — a trim-to-empty composes with the existing empty-fetch posture (no write, retry next call). The ladder's `_persist_window_to_archive` is already best-effort (failures logged, never propagated), so the trim is purely subtractive on the incoming frame.

4. **Volume EXEMPT, finiteness-ONLY, interior PRESERVED — identical to 18-A semantics.** The wrapper passes only the OHLC column tuple to `is_finite_ohlc` (volume never passed); it is TRAILING-only (interior non-finite bars preserved, LOCK 4); it is `math.isfinite` (no `>= 0`, LOCK 2 parity). No divergence from the legacy/temporal-log barriers.

5. **`write_window`, `_write_archive_atomic`, `validate_bars`, and all 14 OUT paths are UNTOUCHED.** The only production edits are: the column-name generalization of `_trim_trailing_ragged` (behavior-preserving for existing callers) and the trim insertion in `_persist_window_to_archive`.

6. **A warning is logged on a ladder trim** (mirroring the legacy serial/warm `log.warning("dropped N trailing non-finite OHLC bar(s)")`) so the audit trail is uniform across all three ingest sites. No test pins the string (consistent with 18-A Task 2).

---

## Task 1: Generalize `_trim_trailing_ragged` to a shape-agnostic column tuple (behavior-preserving)

**Files:**
- Modify: `swing/data/ohlcv_archive.py` (`_trim_trailing_ragged` signature + the `ohlc` column-detection line)
- Test: `tests/data/test_ohlcv_archive_trailing_nan.py` (add lowercase-column discriminators)

**Goal:** let the ONE barrier serve both the capitalized legacy frame and the lowercase Shape-A frame, with NO new finiteness logic and NO behavior change for existing callers.

- [ ] **Step 1: Read the current function + all call sites.** Read `_trim_trailing_ragged` ([ohlcv_archive.py:204](../../../swing/data/ohlcv_archive.py#L204)) and confirm its two call sites (`:264`, `:697`) pass a capitalized-column frame. Confirm the `ohlc` detection line is `ohlc = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]`.

- [ ] **Step 2: Write the failing tests** (append to `tests/data/test_ohlcv_archive_trailing_nan.py`, after the existing Phase-18 inf discriminator):

```python
def test_trim_lowercase_shape_a_trailing_nan_phase18b():
    """Phase 18 18-B: the Shape-A (ladder) frame uses LOWERCASE open/high/low/close.
    The generalized barrier trims a trailing Close=NaN row (the 06-10 artifact)
    when handed the lowercase column tuple, via the SAME is_finite_ohlc predicate.
    PRE-FIX (capitalized-only detection) the lowercase frame's ohlc list is EMPTY
    -> the barrier no-ops -> n == 0 (the NaN row survives)."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, float("nan")], "volume": [1000, 1200],
    })
    trimmed, n = mod._trim_trailing_ragged(
        df, columns=("open", "high", "low", "close"))
    assert n == 1
    assert list(trimmed["asof_date"]) == ["2026-06-09"]


def test_trim_lowercase_shape_a_interior_nan_preserved_phase18b():
    """LOCK 4: interior non-finite bar PRESERVED; only trailing trimmed."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-08", "2026-06-09", "2026-06-10"],
        "open": [10.0, float("nan"), 10.5], "high": [11.0, 11.0, 11.5],
        "low": [9.0, 9.0, 10.0], "close": [10.5, 10.6, 10.7], "volume": [1, 2, 3],
    })
    trimmed, n = mod._trim_trailing_ragged(
        df, columns=("open", "high", "low", "close"))
    assert n == 0  # trailing row is finite -> nothing trimmed; interior NaN kept
    assert len(trimmed) == 3


def test_trim_lowercase_shape_a_volume_only_nan_exempt_phase18b():
    """Volume-only-NaN trailing row is NOT trimmed (volume excluded from the tuple)."""
    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, 10.7], "volume": [1000, float("nan")],
    })
    trimmed, n = mod._trim_trailing_ragged(
        df, columns=("open", "high", "low", "close"))
    assert n == 0
    assert len(trimmed) == 2


def test_trim_capitalized_default_unchanged_phase18b():
    """Behavior-preserving: existing capitalized callers (default arg) still work
    with NO columns= passed -> identical to the pre-18-B barrier."""
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, float("nan"), 1200),
    })
    trimmed, n = mod._trim_trailing_ragged(df)  # no columns= -> capitalized default
    assert n == 1
    assert [d.date() for d in trimmed.index] == [d1]
```

(Read the test file's existing helpers — `_flat_frame`, the `mod` import alias, `date` import — before appending so the new tests match the established fixtures.)

- [ ] **Step 3: Run to verify they fail the right way.**
Run: `python -m pytest tests/data/test_ohlcv_archive_trailing_nan.py -q`
Expected — note the EXACT pre-fix red/green split (Codex R2 Minor 1): ONLY `test_trim_lowercase_shape_a_trailing_nan_phase18b` FAILS pre-fix (the capitalized-only `ohlc` detection yields an empty list for a lowercase frame → the `if df.empty or not ohlc: return df, 0` arm returns `n == 0`, so `assert n == 1` fails — the NaN row is NOT trimmed). The other two lowercase tests (`..._interior_nan_preserved...` and `..._volume_only_nan_exempt...`) BOTH already PASS pre-fix — they assert `n == 0` (no trim expected), and the pre-fix capitalized-only detector ALSO no-ops on a lowercase frame, so the expected-no-trim outcome coincides. They are guards-against-over-rejection that must STAY green post-fix (where the trim is now active but correctly leaves an interior NaN / volume-only-NaN untrimmed). `test_trim_capitalized_default_unchanged_phase18b` PASSES already (it exercises the unchanged default path). All PRE-EXISTING tests still pass. (The single binding RED→GREEN is the trailing-NaN test; the other three are over-rejection / behavior-preservation guards.)

- [ ] **Step 4: Write the implementation.** Generalize the signature + the `ohlc` detection line ONLY. Change:

```python
def _trim_trailing_ragged(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Arc 8 -- drop trailing rows where ANY of Open/High/Low/Close is non-finite.
    ...
    """
    ohlc = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
```

to:

```python
def _trim_trailing_ragged(
    df: pd.DataFrame,
    *,
    columns: tuple[str, ...] = ("Open", "High", "Low", "Close"),
) -> tuple[pd.DataFrame, int]:
    """Arc 8 -- drop trailing rows where ANY of the OHLC columns is non-finite.

    Phase 18 18-A: the finiteness test is the shared ``is_finite_ohlc`` (the ONE
    predicate also used by the temporal-log writer; C1) -- ``math.isfinite``, so
    a trailing +/-inf row is trimmed too (a strict superset of the prior
    ``isna()`` NaN-only check, aligning with the engine gate's finiteness
    definition). Volume is excluded from ``columns`` so Volume-only-NaN never
    trims.

    Phase 18 18-B: ``columns`` parameterizes the OHLC column NAMES so the SAME
    barrier serves both the legacy capitalized frame (default
    ``("Open","High","Low","Close")``) AND the Shape-A ladder frame
    (lowercase ``("open","high","low","close")``) WITHOUT a second finiteness
    copy. The finiteness logic is unchanged (one ``is_finite_ohlc`` call); only
    the column-name list is parameterized. Default arg preserves every existing
    caller's behavior.

    ...(retain the remaining scope-note bullets verbatim)...
    """
    ohlc = [c for c in columns if c in df.columns]
```

(Keep the rest of the body — the `if df.empty or not ohlc: return df, 0` guard, the `while ... not is_finite_ohlc(*df.iloc[cut - 1][ohlc])` loop, the return — UNCHANGED. Update the docstring's first line + add the 18-B paragraph as shown; leave the run-#99 scope bullets intact.)

- [ ] **Step 5: Run to verify pass.**
Run: `python -m pytest tests/data/test_ohlcv_archive_trailing_nan.py -q`
Expected: the full file PASSES — the four new tests + every pre-existing test (the default arg keeps the two legacy call sites and all their NaN/inf/interior/volume/empty/warm/serial tests behaviorally identical; `math.isfinite` catches NaN/inf the same).

- [ ] **Step 6: Commit.**
```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive_trailing_nan.py
git commit -m "refactor(data): _trim_trailing_ragged accepts an OHLC column tuple (shape-agnostic; behavior-preserving)"
```

---

## Task 2: Close the GAP — trim the Schwab-ladder window before `write_window`

**Files:**
- Modify: `swing/integrations/schwab/marketdata_ladder.py` (`_persist_window_to_archive`)
- Test: the ladder test module (read the existing one first; e.g. `tests/integrations/schwab/test_marketdata_ladder*.py`)

- [ ] **Step 1: Read the current `_persist_window_to_archive` + the existing ladder tests.** Confirm the function builds `df` (a Shape-A lowercase-column DataFrame) and then calls `write_window(ticker, df, provider, cache_dir=cache_dir)` ([marketdata_ladder.py:189-193](../../../swing/integrations/schwab/marketdata_ladder.py#L189-L193)). Locate the existing ladder test fixtures (how they build a `SchwabPriceHistoryWindow` / yfinance window and a cfg with a real `cache_dir`, how they assert on the persisted parquet — e.g. via `resolve_ohlcv_window` or a direct `pd.read_parquet`). Derive the new tests from the REAL persisted shape (the synthetic-fixture-vs-real-emitter discipline).

- [ ] **Step 2: Write the failing tests** (append to the ladder test module). Build a Schwab window whose TRAILING bar is the 06-10 artifact (O/H/L/V finite, `close=NaN`), run `fetch_window_via_ladder` through the SANDBOX/yfinance-fallback path (or directly call `_persist_window_to_archive` with a Shape-A df — choose the path the existing tests already exercise so the production wiring is hit), then assert the persisted Shape-A parquet (via `resolve_ohlcv_window` or `pd.read_parquet`) does NOT contain the NaN row.

```python
def test_ladder_persist_trims_trailing_nan_before_write_phase18b(tmp_path):
    """Phase 18 18-B GAP closure: a fetched window with a TRAILING Close=NaN
    (O/H/L/V finite -- the 06-10 artifact) must be trimmed BEFORE write_window,
    so the Shape-A archive never persists a non-finite bar.

    PRE-FIX arithmetic: _persist_window_to_archive builds df with the NaN row and
    calls write_window -> the parquet contains 2 rows incl. close=NaN; a later
    resolve_ohlcv_window read returns the NaN bar. POST-FIX: the trailing NaN row
    is trimmed -> 1 clean row persisted; resolve_ohlcv_window returns only the
    finite bar. The persisted-row-count + finiteness assertion distinguishes."""
    import math
    import pandas as pd
    from swing.data.ohlcv_archive import resolve_ohlcv_window
    from swing.integrations.schwab.marketdata_ladder import _persist_window_to_archive

    cache_dir = tmp_path
    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, float("nan")], "volume": [1000.0, 1200.0],
    })
    # Drive the production persist path for a yfinance-shape Shape-A frame.
    # (Use whichever entry the existing tests use; _persist_window_to_archive with
    #  a ready Shape-A df + provider='yfinance' is the minimal production-wiring hit
    #  -- it routes df through the same trim+write_window the ladder uses.)
    _persist_window_to_archive("AAA", df, "yfinance", cache_dir)
    out, prov = resolve_ohlcv_window(
        "AAA", start="2026-06-01", end="2026-06-30", cache_dir=cache_dir)
    closes = [float(c) for c in out["close"]]
    assert all(math.isfinite(c) for c in closes)        # no NaN persisted
    assert "2026-06-10" not in list(out["asof_date"])   # the NaN row was trimmed
    assert "2026-06-09" in list(out["asof_date"])        # the finite row survived


def test_ladder_persist_keeps_fully_valid_window_phase18b(tmp_path):
    """No over-rejection: a fully-finite window persists unchanged (both rows)."""
    import pandas as pd
    from swing.data.ohlcv_archive import resolve_ohlcv_window
    from swing.integrations.schwab.marketdata_ladder import _persist_window_to_archive

    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, 10.7], "volume": [1000.0, 1200.0],
    })
    _persist_window_to_archive("BBB", df, "yfinance", tmp_path)
    out, _ = resolve_ohlcv_window(
        "BBB", start="2026-06-01", end="2026-06-30", cache_dir=tmp_path)
    assert sorted(out["asof_date"]) == ["2026-06-09", "2026-06-10"]


def test_ladder_persist_volume_only_nan_not_trimmed_phase18b(tmp_path):
    """Volume-only-NaN trailing row is EXEMPT (finite OHLC) -> persisted."""
    import pandas as pd
    from swing.data.ohlcv_archive import resolve_ohlcv_window
    from swing.integrations.schwab.marketdata_ladder import _persist_window_to_archive

    df = pd.DataFrame({
        "asof_date": ["2026-06-09", "2026-06-10"],
        "open": [10.0, 10.5], "high": [11.0, 11.5], "low": [9.0, 10.0],
        "close": [10.5, 10.7], "volume": [1000.0, float("nan")],
    })
    _persist_window_to_archive("CCC", df, "yfinance", tmp_path)
    out, _ = resolve_ohlcv_window(
        "CCC", start="2026-06-01", end="2026-06-30", cache_dir=tmp_path)
    assert sorted(out["asof_date"]) == ["2026-06-09", "2026-06-10"]
```

(NOTE for the implementer: verify the chosen drive-path against the existing tests. If the existing suite exercises `_persist_window_to_archive` only via `fetch_window_via_ladder` (sandbox short-circuit with a yfinance-fallback fn returning a Shape-A-or-window object), prefer that fuller-wiring entry and assert on the persisted parquet the same way the existing tests do. The discriminating assertion — NaN row absent post-fix vs present pre-fix — must hold either way.)

- [ ] **Step 3: Run to verify they fail the right way.**
Run: `python -m pytest <ladder test module> -q -k phase18b`
Expected:
- `test_ladder_persist_trims_trailing_nan_before_write_phase18b` → FAIL pre-fix: the un-trimmed NaN row is written to the Shape-A parquet; `resolve_ohlcv_window` returns it → `assert all(math.isfinite(...))` fails (a NaN close) AND `assert "2026-06-10" not in ...` fails.
- `test_ladder_persist_keeps_fully_valid_window_phase18b` → PASS already (no trim needed; guards against over-rejection — must STAY green).
- `test_ladder_persist_volume_only_nan_not_trimmed_phase18b` → PASS already (no finiteness check pre-fix; volume serializes) — must STAY green post-fix (the volume-exempt discriminator).

- [ ] **Step 4: Write the implementation.** In `_persist_window_to_archive`, AFTER the `if df is None: return` guard and BEFORE the `write_window` call, trim the incoming Shape-A window via the shared barrier (lowercase column tuple), logging + skipping a trim-to-empty:

```python
    if df is None:
        return
    # Phase 18 Arc 18-B -- GAP closure. Mirror the Arc-8 legacy-ingest barrier
    # (_yf_download_window / _warm_one_window) at THIS second archive writer: trim
    # a trailing non-finite OHLC bar (the 06-10 yfinance Close=NaN artifact; also
    # +/-inf) from the INCOMING window BEFORE persisting, via the ONE shared
    # is_finite_ohlc predicate (C1; reused through _trim_trailing_ragged). Shape-A
    # frames carry LOWERCASE open/high/low/close, so pass the lowercase column
    # tuple. Volume EXEMPT (excluded from the tuple); interior bars PRESERVED
    # (trailing-only, LOCK 4); finiteness-only (no >=0 -- that stays the engine's
    # validate_bars belt, LOCK 1/2 parity). A trim-to-empty SKIPS the write
    # (write_window's F6 empty-incoming guard then leaves valid history intact).
    from swing.data.ohlcv_archive import _trim_trailing_ragged
    df, n_trimmed = _trim_trailing_ragged(
        df, columns=("open", "high", "low", "close"))
    if n_trimmed:
        log.warning(
            "fetch_window_via_ladder: trimmed %d trailing non-finite OHLC "
            "bar(s) for %s/%s before archive write (retry next fetch)",
            n_trimmed, ticker, provider,
        )
    if df.empty:
        return
    try:
        from swing.data.ohlcv_archive import write_window
        write_window(ticker, df, provider, cache_dir=cache_dir)
    except Exception as exc:
        ...
```

(Place the `_trim_trailing_ragged` import alongside the existing local `write_window` import, or hoist both to one local import block — match the file's established local-import style. `_trim_trailing_ragged` is shared `swing/data` infrastructure; importing it from `swing/integrations/schwab` is the allowed `integrations → data` direction. Do NOT import anything from `swing/pipeline`.)

- [ ] **Step 5: Run to verify pass.**
Run: `python -m pytest <ladder test module> -q`
Expected: the full ladder module PASSES — the trailing-NaN test now shows the row trimmed/absent; the valid + volume-only-NaN tests stay green; every pre-existing ladder test stays green (their windows are finite; the trim is a no-op on them).

- [ ] **Step 6: Commit.**
```bash
git add swing/integrations/schwab/marketdata_ladder.py tests/integrations/schwab/<ladder test module>
git commit -m "fix(schwab): trim trailing non-finite OHLC from the ladder window before archive write (shared barrier; C1)"
```

---

## Task 3: Full-suite + ruff + lock self-audit (no new code)

**Files:** none (verification only).

- [ ] **Step 1: Focused module set.**
```bash
python -m pytest tests/data/test_ohlcv_finiteness.py \
  tests/data/test_ohlcv_archive_trailing_nan.py \
  tests/integrations/schwab/<ladder test module> -q
```
Expected: all PASS.

- [ ] **Step 2: Full fast suite.**
Run: `python -m pytest -m "not slow" -q`
Expected: green (≈8146+ as of 18-A close; the new tests add a handful). Investigate any failure before proceeding; the research-test `sys.modules` polluter is a known intermittent (CLAUDE.md §Windows/tooling — now healed for `swing.*`); re-run with `-n 0` if a flake is suspected, but a real regression in the touched modules is not acceptable.

- [ ] **Step 3: Lint.**
Run: `ruff check swing/`
Expected: clean — the edited lines in `swing/data/ohlcv_archive.py` + `swing/integrations/schwab/marketdata_ladder.py`. (Test-file lint is OUT OF SCOPE — the project's gate is `swing/` only, per the 18-A precedent; keep new test code ≤100-char lines + local imports matching each file's style so the arc adds no NEW violation.)

- [ ] **Step 4: Grep the locks (self-audit before QA).**
```bash
# C1 / layer rule: data must NOT import pipeline; integrations must NOT import pipeline for this
grep -rn "import swing.pipeline\|from swing.pipeline" swing/data/ swing/integrations/schwab/marketdata_ladder.py || echo "OK: no pipeline import in data/ or the ladder"
# the predicate has exactly one definition (no third copy)
grep -rn "def is_finite_ohlc" swing/
# the ladder closure reuses the shared barrier (not a fresh finiteness loop)
grep -rn "_trim_trailing_ragged\|is_finite_ohlc" swing/integrations/schwab/marketdata_ladder.py
# validate_bars untouched (LOCK 1)
git diff --stat -- research/harness/shadow_expectancy/validate.py   # expect: empty
# no schema/migration (LOCK 3)
git diff --name-only | grep -E "migrations/|\.sql$" && echo "VIOLATION: schema touched" || echo "OK: no schema"
# write_window / _write_archive_atomic body untouched (only the ladder + the barrier signature changed)
git diff -- swing/data/ohlcv_archive.py | grep -E "^\+|^-" | grep -iE "write_window|_write_archive_atomic" || echo "OK: merge chokepoint bodies unchanged"
```
Expected: no pipeline import in `swing/data` or the ladder; exactly one `def is_finite_ohlc`; the ladder references `_trim_trailing_ragged` (NOT a new finiteness loop); `validate.py` unchanged; no `.sql`/migration in the diff; the only `ohlcv_archive.py` change is the `_trim_trailing_ragged` signature/docstring (no `write_window`/`_write_archive_atomic` body edits).

- [ ] **Step 5: No commit** (verification only).

---

## Self-Review (run after the plan is written; resolved here)

**1. Spec/condition coverage:**
- The exhaustive enumeration (§1) — 20 rows (incl. row #7b added per Codex R1 MAJOR), every OHLC-write boundary in `swing/`, audit-to-confirm (no pre-asserted count); 4 GUARDED, 1 GAP, 15 OUT.
- C1 (ONE shared predicate, both paths, allowed import direction) → the gap closes via `_trim_trailing_ragged` (which consumes `is_finite_ohlc`); Task 3 grep proves no third copy + `integrations → data` import only.
- LOCK 1 (validate_bars untouched) → Task 3 `git diff --stat` of validate.py empty.
- LOCK 2 (writer↔engine parity) → the gap uses the shared predicate; finiteness set identical (`math.isfinite`, OHLC-only, volume-exempt, no `>=0`).
- LOCK 3 (NO schema) → audit found no migration-requiring gap; Task 3 grep confirms no `.sql`. (Had a gap needed schema, the plan would STOP + route to CHARC.)
- LOCK 4 (interior preserved; finiteness-only; trailing-only) → the trim is `_trim_trailing_ragged` (trailing-only); `test_trim_lowercase_shape_a_interior_nan_preserved_phase18b` locks it; the merge chokepoint untouched.
- LOCK 5 (discriminating test, both-ways arithmetic) → Task 2 `test_ladder_persist_trims_trailing_nan_before_write_phase18b` (RED pre-fix: NaN persists; GREEN post-fix: trimmed) with pre/post arithmetic; + the volume-exempt + over-rejection discriminators.
- Scope honored → no read/compute path guarded (criteria/*, ohlcv.py compute helpers, weather/daily_management/candidates derived scalars all OUT with documented reasons).

**2. Placeholder scan:** none — every code/test step shows full content or names the exact insertion point + the existing pattern to match; every command shows expected output. The two implementer-verification notes (Task 2 Step 1/Step 2 "use the path the existing tests exercise") are explicit grounding instructions, not placeholders — the discriminating assertion is fully specified regardless of the chosen drive-path.

**3. Type/name consistency:** `_trim_trailing_ragged(df, *, columns=...)` is referenced identically in Task 1 (definition) and Task 2 (lowercase call); the shared predicate path `swing.data.ohlcv_finiteness.is_finite_ohlc` is unchanged; the warning string mirrors the 18-A legacy-ingest wording ("trailing non-finite OHLC bar(s)").

**Borderline call flagged for the gate (Task §1 row 18):** `swing/tools/migrate_prices_cache.py` is classified OUT (one-time historical re-keying tool, no external fetch, not a live ingest boundary, outside the divergence class). If CHARC/RD prefer it IN, the closure is mechanical and isolated (trim each `combined` frame's trailing non-finite via the same generalized barrier before `to_parquet` at `_consolidate_ticker`) — but the plan's position is that re-keying already-persisted data is not an ingest boundary and a NEW non-finite bar cannot enter there, so guarding it would be defense against a state the path cannot produce.
