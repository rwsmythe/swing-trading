# Daily-Management Network-Under-Fence (#16) — Fetch-Hoist Design Spec

**Date:** 2026-06-07
**Phase:** 15 (B-family / operational hardening) — fence-hygiene fix arc, NO schema change (v24 holds)
**Status:** LOCKED (Codex-converged) — ready for `copowers:writing-plans`
**Branch (brainstorm):** `dm-fence-archive-split` from main HEAD `a460961c`
**Commission brief:** [`docs/daily-management-fence-arc-brainstorming-dispatch-brief.md`](../../daily-management-fence-arc-brainstorming-dispatch-brief.md)
**Precedent (formalized here):** [`docs/superpowers/specs/2026-06-06-fetch-vs-write-ordering-design.md`](2026-06-06-fetch-vs-write-ordering-design.md) §8 (OQ-D bank) + §3 (OQ-A governing pattern)

---

## 1. Problem statement (grounded on worktree HEAD `a460961c`, not re-derived)

`_step_daily_management` ([runner.py:3774](../../../swing/pipeline/runner.py)) performs **yfinance
network I/O while holding the per-trade SQLite write lock.** The per-trade fence at
**runner.py:3810** (`with lease.fenced_write() as conn:`) wraps
`compute_daily_approximate_snapshot(conn, …)` @3811, which calls `read_or_fetch_archive(...)` at
[daily_management.py:510](../../../swing/trades/daily_management.py) → `_yf_download_window` at
[ohlcv_archive.py:257/275](../../../swing/data/ohlcv_archive.py) (the `needs_full_refresh` weekly
refresh **and** the `latest_stored < today` gap-fill both fire yfinance). On a warm-miss /
transient-empty / gap-fill the held write transaction does a **network round-trip under the lock**.

**Same bug class as the just-fixed Schwab deadlock (`4f0b4010`), but NOT a deadlock.**
`_step_daily_management` writes **no Schwab audit row** during its sequential step (zero
`get_or_fetch` / ladder calls), so there is no competing `audit_conn` `BEGIN IMMEDIATE` to block.
It is a **latent lock-hold** (🟡 hygiene, precedent §2 row #16): the held write lock blocks a
concurrent web writer for the duration of a yfinance round-trip. Lower severity than the deadlock;
still a real fence-hygiene violation worth closing structurally.

**The fix is ordering, not timeout tuning** (precedent's universal rule): the network fetch happens
with **no held `fenced_write`**; the fence wraps only the fast SQLite trade-row read + the persist.

### 1.1 Why "warm-before-fence alone" is insufficient (the structural part)

Pre-warming the archive outside the fence is necessary but **not sufficient** to *guarantee* no
in-fence fetch, because `read_or_fetch_archive` re-enters `_yf_download_window` on any of:
warm-failure (transient network error), transient-empty upstream (F6 path returns the stale
archive or `None`), or gap-fill (`latest_stored < today`). If the in-fence call still *can* call
`read_or_fetch_archive`, a warm miss re-fetches under the lock. The guarantee must be **structural**:
the in-fence phase must be **incapable** of fetching. This spec achieves that by making
`compute_daily_approximate_snapshot` a **pure compute** that consumes a pre-warmed DataFrame passed
in by the caller — it has no archive directory, no fetch import, and therefore cannot perform any
archive I/O of any kind (its only in-fence I/O is the `get_trade(conn)` SQLite read).

---

## 2. STEP-0 audit — `_step_daily_management` is the ONLY remaining network-under-fence locus

Re-verified on HEAD `a460961c` (the precedent arc `4f0b4010` reordered detect Pass-2 + observe
AFTER the precedent spec was written, so its line numbers had drifted — all re-confirmed here):

| Locus | Line | Fetch reachable inside a held `fenced_write`? | Verdict |
|-------|------|----------------------------------------------|---------|
| detect Pass-2 exemplar prefetch | `ohlcv_cache.get_or_fetch` @1966 | **No** — between the short snapshot fence @1938 (a pure `list_exemplars` read that closes @1939) and the main write fence @2004; bars are built into `exemplar_bundles_by_class` BEFORE @2004 | ✅ safe (reordered by `4f0b4010`) |
| observe | `_bar_for_date`→`get_or_fetch` @2612, invoked @2756 | **No** — @2756 is the compute pass, OUTSIDE the write fence @2783 (which wraps only `insert_observation`) | ✅ safe (reordered by `4f0b4010`) |
| **daily_management** | `read_or_fetch_archive` @daily_management.py:510, invoked @3811 inside fence @3810 | **YES** — yfinance under the per-trade fence | 🟡 **#16 — THIS ARC** |

A fresh sweep of every `read_or_fetch_archive` / `get_or_fetch` / ladder call in `runner.py`
(grep-verified) confirms the only one reachable inside a held `fenced_write` is the
`compute_daily_approximate_snapshot` → `read_or_fetch_archive` path at @3811. **No new locus crept
in** since the precedent arc.

---

## 3. Decisions (operator-resolved 2026-06-07)

The brief surfaced four open questions. The operator resolved them in the brainstorm; the resolved
**core decision reshapes the arc from an "archive-API split" into a "fetch-hoist + pure-function
refactor"** — see §3.1 for why that is *stronger*, not weaker, than the banked split.

- **OQ-1 — read-only sibling shape: MOOT (subsumed by OQ-2).** The OQ-1 fork (reuse
  `resolve_ohlcv_window` Shape-A vs add a thin read-only reader over the legacy `{TICKER}.parquet`)
  only bites if the in-fence phase still *reads the archive*. The operator chose to pass pre-warmed
  bars in (OQ-2 below), so the in-fence phase does **no archive read at all** — there is no
  read-only sibling to shape. **No new archive-API function is added.** *(Shape analysis retained
  for the record: `compute_daily_approximate_snapshot` consumes a DatetimeIndex frame with
  capitalized OHLCV — `df["Close"]`, `df.index.date`; `resolve_ohlcv_window` returns a different
  shape — integer index, `asof_date` column, lowercase OHLCV, tuple return — and triggers
  `_backward_compat_rename`. Reusing it would have needed a reshaping adapter + Shape-A
  entanglement; the pass-bars-in choice sidesteps both.)*

- **OQ-2 — spec-locked-signature threading: PASS THE PRE-WARMED DataFrame IN (pure function).**
  `compute_daily_approximate_snapshot` **drops** `ohlcv_archive_dir: Path` and
  `archive_history_days: int`, **adds** `archive_df: pd.DataFrame | None`, and replaces its
  `read_or_fetch_archive(...)` call with a direct consume of `archive_df`. The runner performs the
  warm (the **existing** `read_or_fetch_archive`, unchanged) OUTSIDE the fence and passes its return
  in. This is a **§6.6 signature-lock amendment** — operator-sanctioned here (§3.2). Rationale:
  strongest structural guarantee (the function becomes incapable of fetching), immune to the
  `_backward_compat_rename` file-rename race (the bars are captured in memory, not re-read from a
  file that a concurrent web `resolve_ohlcv_window` could rename mid-step), simplest to test
  (no monkeypatch of a read function; tests pass the DataFrame they already build), and it adds
  **zero new archive-API surface**.

- **OQ-3 — warm-failure / read-only-miss behavior: SKIP + #27, ≤1-run staleness ACCEPTED.** On any
  miss cause (warm raised, warm transient-empty/`None`, archive has no `asof_session` row), the
  trade is **skipped for this run** and a #27 `warnings_json` entry is emitted; **no in-fence
  re-fetch**. This is the **status quo behavior upgraded with an audit**: today the function already
  returns `None` on an empty/short archive and the step logs + skips (the plain `log.warning` at
  runner.py:3828-3834); this arc routes that skip through a `run_warnings` entry
  (`step="daily_management"`, `ticker`, `reason`). The missing snapshot is benign for one run —
  daily-management's gap-flagged policy already says "NO auto back-fill of missed sessions; one
  snapshot per `last_completed_session(run_now)`", and the idempotent same-session re-run preserves
  `management_record_id`. The next run picks the trade up. Mirrors the observe no-bar #27 skip.

- **OQ-4 — warm scope: PER-OPEN-TRADE-TICKER, just before its own fence.** Each trade's ticker is
  warmed immediately before that trade's write fence, **inside** the existing per-trade
  `try`/`except`. Mirrors the precedent's OQ-A ("per-locus, just-before-its-own-write"); a warm
  failure is naturally isolated to that trade's iteration; simplest to reason about under the fence
  rule. No bulk up-front pass (open-trade count is a handful, so cost is equivalent, but per-trade
  keeps the trades decoupled and matches the precedent shape).

### 3.1 Why "fetch-hoist" supersedes the banked "archive-API split" framing

The precedent §8 banked design said "split `read_or_fetch_archive` into a fetch-capable warm path
+ a pure read-only path … change `compute_daily_approximate_snapshot` … to consume pre-warmed bars
**/** the read-only path." It offered **two** sanctioned shapes: (i) consume pre-warmed bars, or
(ii) a read-only sibling. The operator chose (i). Under (i) there is **nothing to split**:
`read_or_fetch_archive` is *already* the fetch-capable warm path, and it is reused **byte-identical**
by the runner outside the fence. The only change to the archive layer is **where its call site
lives** (runner, outside the fence — not inside `compute_daily_approximate_snapshot`). This makes
the §5 non-breakage proof trivial: the shared fetch API is untouched, so all of its consumers are
untouched by construction.

### 3.2 §6.6 signature-lock amendment (operator-sanctioned)

`compute_daily_approximate_snapshot` carries `# noqa: PLR0913 -- spec-locked signature` and the
`trail_MA_period_days_default` carries `# noqa: N803 -- name locked by spec §6.6`. This arc amends
the §6.6 signature lock as follows (and ONLY as follows):

- **Removed:** `ohlcv_archive_dir: Path`, `archive_history_days: int` (the function no longer fetches).
- **Added:** `archive_df: pd.DataFrame | None` (the pre-warmed bars, ≤ `asof_session`) and
  `expected_ticker: str` (the identity the bars were warmed for — the in-fence ticker guard, §4.1 /
  Codex R1 MAJOR #1).
- **Unchanged (still locked):** `conn`, `trade_id`, `asof_session`, `run_now`, `pipeline_run_id`,
  `capital_floor_dollars`, `trail_MA_period_days_default` (name + N803 lock preserved). The
  `PLR0913` noqa stays (9 params). The function's **return contract is unchanged**
  (`dict[str, Any] | None`, `None` ⇒ skip).

The amendment is justified by the fence-hygiene fix and is the minimal change that makes the
in-fence phase incapable of network I/O. No other §6.6-locked signature is touched.

---

## 4. Fix design

### 4.1 `compute_daily_approximate_snapshot` — pure compute ([daily_management.py:465](../../../swing/trades/daily_management.py))

**Signature** (kw-only after `conn`):

```python
def compute_daily_approximate_snapshot(  # noqa: PLR0913 -- spec-locked signature (§6.6, amended 2026-06-07)
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    asof_session: date,
    run_now: datetime,
    archive_df: pd.DataFrame | None,         # NEW — pre-warmed bars (rows ≤ asof_session)
    expected_ticker: str,                    # NEW — identity guard (Codex R1 MAJOR #1)
    pipeline_run_id: int | None,
    capital_floor_dollars: float = 7500.0,
    trail_MA_period_days_default: int = 21,  # noqa: N803 -- name locked by spec §6.6
) -> dict[str, Any] | None:
```

**Body change (the ONLY behavioral change):** remove the lazy
`from swing.data.ohlcv_archive import read_or_fetch_archive` import @503 and the
`read_or_fetch_archive(...)` call @510-515; replace with the in-fence ticker guard + a direct
consume:

```python
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")

    # Identity guard (Codex R1 MAJOR #1 / R2 MAJOR #1): the bars were warmed for
    # `expected_ticker` OUTSIDE the fence; the trade row is re-read fresh in-fence
    # here. Reject (skip, never re-fetch) if the trade's ticker changed between warm
    # and fence so old-ticker bars are never combined with a newly read trade row.
    # `trades.ticker` IS live-mutable (rarely) via a concurrent tier-3 reconciliation
    # operator override — `_update_journal_field` issues `UPDATE trades SET {field}`
    # and `validate_trade_correction` gates only `current_stop`/`state`, allowing other
    # fields incl. `ticker` (reconciliation_auto_correct.py:1215 /
    # reconciliation_validators.py:190,217). The pipeline lease blocks concurrent
    # *pipeline* runs but NOT CLI/web reconciliation, so this guard is a REAL (if
    # uncommon) audited skip, not a theoretical one.
    if trade.ticker != expected_ticker:
        return None

    df = archive_df
    if df is None or df.empty:
        return None
    # ... everything from here unchanged (anchor slice @522, asof_mask @527,
    #     MFE/MAE @536, cap_util/heat/maturity @555-567, 21-day SMA tail @573,
    #     created_at canonicalization @592, fields dict @607, validator @643).
```

Everything downstream of the `df` assignment is **untouched** — the same slicing, MFE/MAE running
extrema, SMA tail, cap-util/heat/maturity, `created_at` naive-UTC canonicalization, field dict, and
defensive validator. The `get_trade(conn)` read stays in-fence (a fast SQLite read consistent with
the write) and is **authoritative for every mutable field** (`current_stop`, `current_size`,
`current_avg_cost`, `pre_trade_locked_at`, …) exactly as pre-fix — only the *bars* come from the
warm, and the bars depend solely on `(ticker, asof_session)`.

**Snapshot-field parity (Codex R1 MAJOR #2 — claim narrowed):** the compute is **behavior-preserving
given the same captured DataFrame**. The runner warms with the *identical* call the function made
for itself today — `read_or_fetch_archive(ticker, end_date=asof_session, …)` — and the warm fires
per-trade *immediately before* that trade's fence (OQ-4), so the captured frame is the same one the
pre-fix in-fence call would have produced microseconds later. Any residual archive race (a
concurrent web `read_or_fetch_archive` / `resolve_ohlcv_window` writing the archive, or a gap-fill
landing between warm and fence) is bounded to **≤1-run staleness** — the *same kind* of fetch-vs-state
window the pre-fix in-fence fetch already had — and is now #27-audited on a miss (§4.2). The
**parity TEST (§7.3) feeds a fixed DataFrame to both pre- and post-fix paths** (deterministic), so it
asserts the compute is unchanged independent of any live-archive timing.

### 4.2 `_step_daily_management` — hoist the warm out, thread the result + `run_warnings` in ([runner.py:3774](../../../swing/pipeline/runner.py))

**Signature:** add `run_warnings: list[dict] | None = None` (mirrors `_step_pattern_observe`'s
parameter at runner.py:2663). `ohlcv_archive_dir` + `archive_history_days` **stay** on the step
(now consumed by the warm at the runner level, not forwarded to the pure function).

**Reordered body:**

```python
    asof_session = last_completed_session(run_now)
    with lease.fenced_write() as conn:
        trades = list_open_trades(conn)
    for trade in trades:
        try:
            # --- WARM, OUTSIDE the fence (yfinance I/O here, lock-free) ---
            # OQ-4: per-trade, just before its own fence. read_or_fetch_archive
            # is lease-free (touches no lease/lock), so it cannot raise
            # LeaseRevokedError; a warm error degrades to archive_df=None -> the
            # single #27 skip branch below. miss_reason (Codex R1 MINOR #2)
            # records the skip cause without reintroducing an in-fence fetch.
            miss_reason: str | None = None
            try:
                archive_df = read_or_fetch_archive(
                    trade.ticker, end_date=asof_session,
                    cache_dir=ohlcv_archive_dir,
                    archive_history_days=archive_history_days,
                )
                if archive_df is None or archive_df.empty:
                    miss_reason = "warm_empty_or_stale"
            except Exception as warm_exc:  # noqa: BLE001 -- best-effort warm; miss funnels to #27
                log.warning(
                    "daily_management warm fetch failed for trade %s (ticker=%s): "
                    "%s -- proceeding to skip path", trade.id, trade.ticker, warm_exc,
                )
                archive_df = None
                miss_reason = "warm_raised"

            # --- FENCE: fast SQLite read + compute + persist (no network) ---
            with lease.fenced_write() as conn:
                fields = _dm.compute_daily_approximate_snapshot(
                    conn, trade_id=trade.id, asof_session=asof_session,
                    run_now=run_now, archive_df=archive_df,
                    expected_ticker=trade.ticker,              # NEW identity guard
                    pipeline_run_id=lease.run_id,
                    capital_floor_dollars=capital_floor_dollars,
                    trail_MA_period_days_default=trail_MA_period_days_default,
                )
                if fields is None:
                    # If the warm succeeded, the in-fence miss is the ticker guard
                    # firing OR no usable rows in the warmed frame for this trade's
                    # window. RECOMMENDED (writing-plans): have compute_… return a
                    # typed miss reason so the labeler is authoritative — the function
                    # has FOUR internal None paths (ticker mismatch; df None/empty;
                    # anchor-window empty @daily_management.py:524; asof-row absent
                    # @529) that an external labeler cannot reliably distinguish.
                    if miss_reason is None:
                        miss_reason = _classify_infence_miss(
                            conn, trade.id, trade.ticker, archive_df, asof_session,
                        )  # -> "ticker_changed" | "no_eligible_window"
                    log.warning(
                        "daily_management snapshot skipped for trade %s "
                        "(ticker=%s): %s", trade.id, trade.ticker, miss_reason,
                    )
                    if run_warnings is not None:               # #27 audit (NEW)
                        run_warnings.append({
                            "step": "daily_management",
                            "ticker": trade.ticker,
                            "reason": "archive unavailable for asof_session",
                            "miss_reason": miss_reason,
                        })
                    continue
                upsert_snapshot(conn, trade_id=trade.id, snapshot_fields=fields)
                if trade.state == "entered":
                    state_transition(
                        conn, trade_id=trade.id, new_state="managing",
                        event_ts=fields["created_at"],
                        rationale="first_daily_management_record",
                    )
        except LeaseRevokedError:
            raise                                              # force-clear authoritative (R2 M5)
        except Exception as exc:
            log.warning("daily_management step failed for trade %s: %s", trade.id, exc)
```

**Runner call site** (runner.py:837) gains `run_warnings=run_warnings` (the list created @815 and
serialized into `warnings_json` @1022):

```python
                _step_daily_management(
                    lease=lease, run_now=run_now, eval_run_id=eval_run_id,
                    archive_history_days=cfg.archive.archive_history_days,
                    ohlcv_archive_dir=cfg.paths.prices_cache_dir,
                    run_warnings=run_warnings,                 # NEW
                )
```

**All miss causes funnel to the single `fields is None` #27 branch**, each with a distinct
`miss_reason` (Codex R1 MINOR #2 / R3 MINOR): `warm_raised` (the warm threw) · `warm_empty_or_stale`
(the warm returned `None`/empty) · `ticker_changed` (the in-fence identity guard fired — §4.1) ·
`no_eligible_window` (the warmed frame has no usable rows for this trade's window — covers BOTH the
empty anchor→asof window @daily_management.py:524 AND the absent `asof_session` row @529, which were
two separate internal `None` paths Codex R3 noted the original 4-token taxonomy missed). One uniform
audited skip path; no in-fence fetch on any cause. `LeaseRevokedError` still re-raises (the warm
cannot raise it; the fence/`upsert`/`state_transition` can, and the outer `except LeaseRevokedError`
re-raises before the catch-all — preserved exactly).

`_classify_infence_miss` is a cheap in-fence labeler (no network) used ONLY to tag `miss_reason`; the
**authoritative** guard is inside `compute_daily_approximate_snapshot` (§4.1). **RECOMMENDED for
writing-plans:** instead of an external labeler that cannot reliably distinguish the function's four
internal `None` paths (ticker mismatch; `df` None/empty; anchor-window empty; asof-row absent), have
`compute_daily_approximate_snapshot` **return the typed miss reason** (e.g. a small result object or
a `(fields, miss_reason)` tuple) so the audit tag is sourced from the path that actually fired. The
external labeler is an acceptable fallback; the typed return is preferred.

---

## 5. Blast radius — the shared fetch API is byte-identical (non-breakage proof)

`read_or_fetch_archive` ([ohlcv_archive.py:204](../../../swing/data/ohlcv_archive.py)) is **not
modified** — neither signature nor behavior. Its ~9 production consumers (grep-verified on HEAD
`a460961c`) are therefore untouched **by construction**:

| # | Consumer | Site |
|---|----------|------|
| 1 | `runner.py` market-data/OHLCV ladder hook (`_bars_hook`) | runner.py:426 |
| 2 | `prices.py` `PriceFetcher` | prices.py:56 |
| 3 | `web/app.py` archive read | app.py:321 |
| 4 | `web/ohlcv_cache.py` `OhlcvCache` fallback | ohlcv_cache.py:284 |
| 5 | `pipeline/ohlcv.py` `fetch_daily_bars` | ohlcv.py:44 |
| 6 | `web/trade_charts.py` | trade_charts.py:57 |
| 7 | `web/routes/patterns.py` | patterns.py:106 |
| 8 | `web/view_models/patterns/review_form.py` | review_form.py:482 |
| 9 | **`_step_daily_management`** (the warm — STILL a consumer, now at the runner level outside the fence) | runner.py (new warm call, formerly daily_management.py:510) |

The only change is that consumer #9's call site **moves** from inside
`compute_daily_approximate_snapshot` (under the fence) to `_step_daily_management` (outside the
fence). No consumer's signature or call shape changes. **No read-only sibling is added** (OQ-2
choice), so there is no new archive-API surface to review.

---

## 6. Locks / invariants (propagate to writing-plans)

- **Schema: NONE** — v24 holds. Zero migrations, zero CHECK changes, zero column adds.
- DB-outside-Drive (`%USERPROFILE%/swing-data/swing.db`).
- **Lease-fencing contract:** every write stays inside `fenced_write` + the in-tx lease check;
  ONLY the fetch (the warm) moves out. `LeaseRevokedError` MUST still re-raise (runner per-trade
  loop — Codex R2 M5; preserved at the outer `except LeaseRevokedError`).
- **§6.6 signature-lock amendment** (this arc, operator-sanctioned §3.2): `compute_daily_approximate
  _snapshot` drops `ohlcv_archive_dir`/`archive_history_days`, adds `archive_df` + `expected_ticker`.
  No other locked signature touched; `trail_MA_period_days_default` name + N803 lock preserved.
- **`trades.ticker` identity guard (a REAL audited skip — Codex R1 MAJOR #1 / R2 MAJOR #1):** the
  warm↔compute identity coupling is `ticker`-only (bars depend solely on `(ticker, asof_session)`;
  the in-fence `get_trade` is authoritative for every mutable field). `trades.ticker` IS live-mutable
  — **rarely** — via a concurrent **tier-3 reconciliation operator override**:
  `_update_journal_field` (reconciliation_auto_correct.py:1215) issues `UPDATE trades SET {field}=?`,
  and `validate_trade_correction` (reconciliation_validators.py:190,217) gates only `current_stop` /
  `state`, returning true for other fields — so an override carrying `{"ticker": …}` mutates it. The
  pipeline lease blocks concurrent *pipeline* runs but NOT CLI/web reconciliation. So the
  `expected_ticker` guard is a **real (if uncommon) consistency protection**: on a mismatch it
  **skips + #27-audits** (`miss_reason="ticker_changed"`), bounded to ≤1-run staleness, rather than
  combining old-ticker bars with a newly read trade row. *(Hardening reconciliation to allowlist
  trade-correction fields is a separate concern, explicitly out of scope — §8.)*
- **#27 silent-skip-audit:** the `fields is None` skip emits a `warnings_json` entry
  (`step="daily_management"`, `ticker`, `reason`, `miss_reason` ∈ {`warm_raised`,
  `warm_empty_or_stale`, `ticker_changed`, `no_eligible_window`}) — the existing plain `log.warning`
  skip becomes audited. (`run_warnings is None` defensive guard mirrors the detect/observe steps.)
- **F6 empty-result-transient:** the warm reuses `read_or_fetch_archive` unchanged — its F6 defense
  (ohlcv_archive.py:263, return the stale archive on a transient yfinance empty rather than blanking
  it) is preserved. Not regressed.
- **Session-anchor correctness:** `asof_session = last_completed_session(run_now)` (BACKWARD-looking)
  is computed once and passed to BOTH the warm (`end_date=asof_session`) and the compute
  (`asof_session=…`) — identical to today. The partial-bar strip stays inside `read_or_fetch_archive`
  / `_write_archive_atomic`. The anchor is NOT moved.
- **OhlcvBar bad-bar handling** (accepted-and-documented 2026-06-07): unaffected — the warm path's
  yfinance fallback already delivers correct bars; the compute reads the same DataFrame. This arc
  does not entangle bad-bar work.
- **Data-integrity arc barriers** (completed-day write-barrier, `topbar_session_date`) + the
  lock-contention arc keepers (`busy_timeout=30000`, serialized `audit_conn`, G2′ telemetry) remain
  intact (untouched by this arc).
- **Idempotency:** `upsert_snapshot` SELECT-then-UPDATE-or-INSERT (same-session re-run preserves
  `management_record_id`); the `entered → managing` state transition stays in-fence after the
  snapshot lands.

---

## 7. Test strategy (TDD — discriminating, pre-fix-fails / post-fix-passes)

Per `feedback_regression_test_arithmetic`: each test is constructed so it **fails on pre-fix code
and passes on post-fix code**. Baseline ≈ **7223** fast tests (re-confirm the actual count on the
branch).

1. **Gold-standard lock-hold reproduction (the binding regression).** Drive the real
   `_step_daily_management` against a **real file-backed** SQLite DB with one open trade whose
   on-disk archive is stale/missing (forces the warm to fetch). Use a spy wrapping
   `read_or_fetch_archive` that, when invoked, attempts a `BEGIN IMMEDIATE` on a **second**
   connection to the same DB (short `busy_timeout`, e.g. 200ms) and records (a) whether that
   second-conn `BEGIN IMMEDIATE` **succeeded** and (b) the **call count**.
   - **Patch BOTH namespaces with the same spy (Codex R1 MAJOR #3):** the **pre-fix** in-fence fetch
     resolves via `compute_daily_approximate_snapshot`'s *lazy* `from swing.data.ohlcv_archive import
     read_or_fetch_archive` (daily_management.py:503), so the spy MUST patch
     `swing.data.ohlcv_archive.read_or_fetch_archive` to intercept it; the **post-fix** warm calls the
     runner's *module-level* binding (runner.py:25), so the spy MUST also patch
     `swing.pipeline.runner.read_or_fetch_archive`. Patching only the runner symbol would make the
     pre-fix test fail *because the spy was never reached* (a false reproduction), not because of the
     lock-hold — patching both makes the pre-fix lock failure prove the actual in-fence path.
   - **Pre-fix:** `read_or_fetch_archive` runs inside `compute_daily_approximate_snapshot` under the
     held fence → second-conn `BEGIN IMMEDIATE` times out (`database is locked`) →
     `lock_observed=True` → **assert fails**.
   - **Post-fix:** the warm runs with no held fence → second-conn `BEGIN IMMEDIATE` succeeds →
     `lock_observed=False` → **assert passes**.
   - **Anti-false-pass:** seed the stale/missing-archive condition that actually fires the warm AND
     **assert the spy was called ≥ 1 time**, so "no lock-hold" cannot pass vacuously on a fixture
     that never reached the fetch.
2. **Ordering assertion (complements #1).** The spy lease exposes an `in_fenced_write` flag set on
   `__enter__` / cleared on `__exit__`. Assert every warm (`read_or_fetch_archive`) call observed
   `in_fenced_write is False`. Assert `compute_daily_approximate_snapshot` performs **zero** archive
   reads in-fence (it has no archive dir; a spy on `read_or_fetch_archive` records zero calls from
   within the function — the only call is the runner's warm).
3. **Snapshot-field parity — deterministic, fixed input (behavior-preserving; Codex R1 MAJOR #2).**
   Feed the **same fixed DataFrame** to both the pre-fix path (the function fetches it via a
   monkeypatched `read_or_fetch_archive` returning that frame) and the post-fix path (the runner warm
   returns the same frame, passed in as `archive_df`); assert the persisted snapshot field dict
   (`current_price`, `open_MFE_R_to_date`/`open_MAE_R_to_date`, `intraday_high`/`intraday_low`,
   `position_capital_utilization_pct`, `position_portfolio_heat_contribution_dollars`,
   `maturity_stage`, `trail_MA_candidate_price`/`trail_MA_period_days`/`trail_MA_eligibility_flag`,
   `open_R_effective`) + the `entered → managing` transition are **identical**. This isolates the
   compute (deterministic given the frame) from any live-archive timing — the claim is parity of the
   *compute*, not byte-identity of a live fetch (which is bounded to ≤1-run staleness per §4.1).
4. **Read-only-miss skip + #27 audit (all four `miss_reason`s).** Inject trades that each trigger a
   distinct miss and assert each is skipped with a #27 `warnings_json` entry carrying the right
   `miss_reason`, **no** in-fence fetch, and the step continues to the next trade:
   (a) warm returns `None`/empty → `miss_reason="warm_empty_or_stale"`;
   (b) warm raises → `archive_df=None` → `miss_reason="warm_raised"`;
   (c) warm returns a frame with rows but none in `[anchor, asof_session]` (empty anchor window) OR
   no `asof_session` row → `miss_reason="no_eligible_window"` (test BOTH sub-cases — Codex R3 MINOR);
   (d) **ticker guard** — warm succeeds for ticker X, but the in-fence `get_trade` row reports a
   different ticker (force via a stubbed `get_trade`/a mutated row): assert `compute_…` returns
   `None`, `miss_reason="ticker_changed"`, and **no** snapshot persists (Codex R1 MAJOR #1). Control:
   a healthy trade in the same run emits **no** skip warning and persists its snapshot.
5. **`LeaseRevokedError` still re-raises.** Inject a `LeaseRevokedError` from the in-fence
   `upsert_snapshot` (or the fence `__enter__`); assert it propagates out of `_step_daily_management`
   (not swallowed by the catch-all), preserving force-clear authority.
6. **Non-breakage of the shared fetch API.** Assert `read_or_fetch_archive`'s signature/behavior is
   unchanged (an existing consumer test stays green; no consumer call site touched). Assert no new
   public symbol was added to `swing.data.ohlcv_archive` (the pass-bars-in choice adds no sibling).
7. **Existing service-test migration (must stay green; Codex R1 MINOR #1 — SIX callers, not 4).** The
   **six** direct `compute_daily_approximate_snapshot` callers in
   `tests/trades/test_daily_management_service.py` (call sites @131 `full_path`, @204
   `canonicalizes_aware_run_now`, @237 `returns_None_on_empty_archive`, @272
   `returns_None_on_no_asof_row`, @295 `unknown_trade_raises_ValueError`, @332
   `stamps_trail_MA_period_days`) migrate to pass `archive_df=<the DataFrame they already build>` +
   `expected_ticker=<the seeded trade's ticker>` (and drop the `read_or_fetch_archive` monkeypatch +
   the removed `ohlcv_archive_dir`/`archive_history_days` args); the empty/None and "no asof row"
   variants pass `archive_df=None` / a frame without the asof row; `unknown_trade_raises` still raises
   `ValueError` before the archive is consulted. The 2 `tests/pipeline/test_daily_management_step.py`
   patches and the `tests/integration/test_phase8_pipeline_walkthrough.py` walkthrough drive the
   **step**, which now also calls `read_or_fetch_archive` for the warm — they must stub/patch
   `swing.pipeline.runner.read_or_fetch_archive` (the warm) so the step does not hit live yfinance.
8. **Full fast suite green** (≈7223 baseline — re-confirm) + `ruff check swing/`.

---

## 8. What this arc deliberately does NOT change / is NOT (keepers + out-of-scope)

- **Keepers:** `read_or_fetch_archive` (byte-identical), all 9 consumers, the F6 transient-empty
  defense, the completed-day write barrier, `busy_timeout=30000`, the serialized `audit_conn`, the
  G2′ telemetry, the `_step_charts` ordering (already correct), detect Pass-2 + observe (already
  reordered by `4f0b4010`). The session anchor is not moved.
- **NOT a deadlock** (no Schwab audit write during the sequential daily-management step) — a latent
  lock-hold (precedent §2 row #16). NOT the Schwab market-data deadlock (`4f0b4010`). NOT Issue #3
  (`_count_open_at_run`). NOT Gate 4 (the quote cassette). NOT the OhlcvBar bad-bar issue
  (accepted-and-documented; its own queued arc). **NO schema change.** Do not touch `_step_charts`,
  detect Pass-2, or observe.
- **No new archive-API function** (OQ-2 = pass-bars-in). No read-only sibling, no
  `resolve_ohlcv_window` reuse for daily-management.
- **NOT reconciliation hardening.** Codex R2 MAJOR #1 surfaced that the tier-3 reconciliation
  override can mutate `trades.ticker` (`validate_trade_correction` allowlists only
  `current_stop`/`state`). This arc does **not** fix that — it only DEFENDS daily-management against
  it via the `expected_ticker` guard (skip + #27). Allowlisting trade-correction fields in
  `validate_trade_correction` / `_update_journal_field` is a separate, banked concern for a future
  reconciliation arc; flag it to the orchestrator.

---

## 9. Acceptance criteria (executing-ready)

- [ ] `compute_daily_approximate_snapshot` signature amended per §3.2 (drop `ohlcv_archive_dir` +
      `archive_history_days`, add `archive_df` + `expected_ticker`); the `read_or_fetch_archive`
      import + call removed; the function consumes `archive_df`, enforces the `expected_ticker`
      identity guard (returns `None` on mismatch), and is otherwise byte-unchanged; returns `None` on
      `archive_df is None or df.empty`.
- [ ] `_step_daily_management` warms `read_or_fetch_archive` OUTSIDE the per-trade fence (per-trade,
      just before its own fence), passes the result + `expected_ticker=trade.ticker` in; the fence
      wraps only `get_trade` (inside the pure function) + `upsert_snapshot` + `state_transition`;
      `LeaseRevokedError` re-raises.
- [ ] `_step_daily_management` gains `run_warnings`; the call site @837 passes it; the `fields is
      None` skip emits a #27 `warnings_json` entry with a `miss_reason` ∈ {`warm_raised`,
      `warm_empty_or_stale`, `ticker_changed`, `no_eligible_window`}; all miss causes funnel to that
      one branch; no in-fence fetch on any cause.
- [ ] No `read_or_fetch_archive` / `get_or_fetch` / ladder (network) call executes inside ANY held
      `fenced_write` in `runner.py` (re-run the §2 audit on the post-fix tree; locus #16 flips to ✅).
- [ ] `read_or_fetch_archive` unchanged (signature + behavior); all 9 consumers untouched; no new
      public symbol in `swing.data.ohlcv_archive`.
- [ ] Tests §7.1–§7.8 land TDD (fail→pass); the migrated service/step/walkthrough tests stay green;
      full fast suite green + `ruff check swing/` clean.
- [ ] Schema unchanged (v24); ZERO `Co-Authored-By`; conventional commits; final `-m` paragraph
      plain prose.

---

## 10. Section map (for the orchestrator's QA)

| § | Contents |
|---|----------|
| 1 | Problem statement (grounded) + why warm-before-fence alone is insufficient |
| 2 | STEP-0 audit — #16 is the only remaining network-under-fence locus (re-verified on HEAD) |
| 3 | OQ-1..OQ-4 decisions (operator-resolved) + fetch-hoist-vs-split rationale + §6.6 amendment |
| 4 | Fix design — pure `compute_daily_approximate_snapshot` + hoisted warm + #27 skip |
| 5 | Blast radius — shared fetch API byte-identical; 9-consumer non-breakage proof |
| 6 | Locks / invariants (schema NONE) |
| 7 | Discriminating TDD test strategy (incl. existing-test migration) |
| 8 | Keepers + out-of-scope |
| 9 | Acceptance criteria |
| 10 | This map |
