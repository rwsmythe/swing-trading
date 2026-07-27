# Phase 21 Arc A — Latch Panel + Order-State Awareness + View Telemetry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a read-only web panel that shows every live A+ entry latch with its FIRE-TIME-frozen pivot / zone cap / invalidation level / sessions-to-horizon / state, joins live broker orders to fire the two alarms (armed-with-no-resting-order, order-resting-with-latch-cleared), and records one objective view-telemetry fact per (latch, session) so 21-B can distinguish *away* from *saw-it-and-didn't-act*.

**Architecture:** A new PURE derivation package `swing/latches/` (no DB, no network, no transactions — the Phase-12 classifier convention) consumed by a thin reader adapter that pre-fetches from `candidates` / `evaluation_runs` / `pipeline_runs` / `trades` and the on-disk OHLCV archive. The web layer adds its own route + VM + template (no base-layout VM field). ONE new table (`latch_view_events`, migration `0032`) holds the view telemetry keyed on the shared latch-identity block. The order join is a separately-lazy-loaded HTMX fragment on its own **POST** endpoint, so the ONLY GET this arc adds performs zero network I/O and zero writes of any kind.

**Tech Stack:** Python 3.14 / SQLite (`sqlite3`) / FastAPI + Starlette 1.0 + Jinja2 + HTMX 2.x / pandas + `exchange_calendars` (XNYS) / pytest.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Branch/base:** worktree `.worktrees/phase21-a-latch-panel`, branch `phase21-a-latch-panel`, base `4a2f7ce0`. All work on this branch; the ORCHESTRATOR merges.
- **Commits:** conventional, carrying the task id (`feat(latches): Task 3 — ...`). **ZERO `Co-Authored-By`. No `--no-verify`. No amend.** Keep the final `-m` paragraph plain prose (trailer-parse hazard).
- **TDD:** failing test → SEE it fail → minimal implementation → SEE it pass → commit. One red→green cycle per task.
- **Lint:** `ruff check swing/` must stay clean. `line-length = 100`, `select = ["E","F","W","I","N","UP","B","SIM"]`.
- **ASCII discipline:** no `§ → ↔ ✓ ✗`, em-dash, or fractions in any string that can reach stdout. Templates/HTML may use entities.
- **Phase isolation:** **NO `swing/trades/` edits of any kind.** The `swing/data/` additions (migration `0032`, `swing/data/repos/latch_view_events.py`, the `LatchViewEvent` model + constants in `swing/data/models.py`, and the `swing/data/db.py` version bump + backup gate) are the scoped addition the 21-A brief §2.2 SCHEMA TRIPWIRE authorizes — the 18-C precedent (migration 0030 + `repos/yfinance_calls.py` + `models.py:YfinanceCall`). Nothing else under `swing/data/` is modified.
- **#11 one-commit multi-mirror discipline:** the migration CHECK enum, the Python constant frozenset, the dataclass `__post_init__` validator, and any repo guard land in **ONE** task/commit (Task 1).
- **Backup gate:** STRICT equality `current_version != 31` / `target_version < 32`, copied verbatim from the `_phase18_arc_h6_backup_gate` clause shape (`swing/data/db.py:1499-1537`). NEVER `<=`.
- **A3:** the banked taxonomy-type rider (`fills_trades_price_divergence`) is **NOT** in this arc's migration. It takes the next free number whenever it lands (the colloquial name "the 0032 taxonomy type" is stale — 21-A takes `0032`).
- **A4:** every write this arc performs is on a **POST**. `GET /latches` is the ONLY GET added and it writes NOTHING AT ALL — not the view record, not a Schwab audit row (the order join is a lazy `POST /latches/orders`).
- **A5:** no new field on `base.html.j2` / any existing base-layout VM. The panel gets its own VM.
- **A6:** every derivation input is treated as possibly absent/malformed; the panel degrades VISIBLY and never 500s.
- **Suite:** run the FULL fast suite (`python -m pytest -m "not slow" -q`) to green BEFORE the Codex review, and again at the end.
- **Editable-install gotcha:** for CLI/runtime checks from the worktree use `PYTHONPATH=. python -m swing.cli ...`. `pytest` from the worktree cwd is unaffected.

---

## A. Derivation rulings (RD gates this section — brief §4 Gate 1)

Every number below was verified against the live DB (`~/swing-data/swing.db`, read-only) and the live archive on 2026-07-27.

### A.1 The live corpus (11 A+ fires ever, 126 evaluation runs)

| eval run | ticker | pivot | initial_stop | `action_session_date` | `pipeline_runs.id` |
|---|---|---|---|---|---|
| 9  | SLDB | 8.866 | 6.40 | **2026-04-22** | — |
| 10 | SLDB | 8.866 | 6.40 | **2026-04-22** | — |
| 12 | SLDB | 8.866 | 6.40 | 2026-04-24 | — |
| 31 | YOU  | 59.515 | 45.38 | **2026-05-04** | — |
| 32 | YOU  | 59.515 | 45.38 | **2026-05-04** | — |
| 94 | NVCR | 18.67 | 14.845 | **2026-06-18** | — |
| 95 | NVCR | 18.67 | 14.845 | **2026-06-18** | — |
| 99 | VSTS | 13.56 | 11.62 | 2026-06-25 | 112 |
| 103 | AMN | 33.48 | 28.81 | 2026-07-01 | 116 |
| 121 | FTRE | **18.34** | **14.88** | 2026-07-20 | 135 |
| 126 | VSTS | 16.90 | 13.40 | 2026-07-27 | 140 |

### A.2 RULING 1 — fire identity: the OPEN-LATCH RULE (**RD DECISION REQUIRED — see §G.1**)

**This is the plan's most load-bearing derivation decision and it is NOT settled by the brief.**

A literal reading of RD constraint 3 ("per-fire identity, keyed `(evaluation_run_id, ticker)`") over-splits. The live evidence is stronger than "consecutive nights":

- **SLDB runs 9 and 10 share `action_session_date = 2026-04-22`.** YOU 31/32 share `2026-05-04`. NVCR 94/95 share `2026-06-18`. All three "re-fire pairs" are **the same action session evaluated twice**, not two nights.
- **Duplicate-`action_session_date` evaluation runs are endemic:** 30 distinct sessions have more than one run; **six** sessions have SIX runs each (`2026-05-15`, `2026-06-08`, `2026-07-06`). A literal per-row identity would create up to six latches for one fire.
- SLDB 12 (`2026-04-24`) IS a genuinely later session — a re-fire two sessions after the 04-22 fire, while that latch was still live.

Constraints 1 and 3 then collide: if every re-fire opens a new latch, the pivot **RE-FREEZES** at the newer row. On SLDB/YOU/NVCR the prices are identical so the bug is invisible; on a ticker that drifts between A+ sessions it silently re-freezes — the FTRE failure mode reintroduced *inside the fix for FTRE*.

**The rule this plan adopts:**

> A `bucket='aplus'` candidates row **OPENS a new latch only if** — processing that ticker's fires in `(action_session_date, run_ts, candidates.id)` order — **NEITHER** of the following holds for the ticker's most recent latch:
> **(i) SAME-SESSION CLAUSE:** the latch's `anchor` equals this row's `action_session_date`; **or**
> **(ii) STILL-LIVE CLAUSE:** the latch is still LIVE as of this row's `action_session_date`.
> If either holds, the row is a **RE-CONFIRMATION**: recorded (its `candidate_id` joins the latch's candidate set), but the latch's identity, frozen pivot, frozen stop, and horizon anchor are **UNCHANGED**.
> Within one `action_session_date`, the **EARLIEST** row by `(evaluation_runs.run_ts, candidates.id)` is the fire; later same-session rows are re-confirmations.

**Why clause (i) is separate from clause (ii)** (Codex R1-1). The still-live clause ALONE is not enough: a fill (or an invalidation close) that lands DURING session S clears the latch *as of S*, so a second evaluation run for the SAME session S would then see "not live" and open a SECOND latch — one mandate becoming two, with the duplicate `armed` for a position the operator already holds and firing a false `LATCH_ARMED_NO_RESTING_ORDER`. This is reachable: 30 action sessions in the corpus have more than one evaluation run (six have SIX), and while the 17:30 scheduled run always rolls to the NEXT session, a manual mid-session re-run still carries `action_session_date = S`. Clause (i) makes the SESSION the atomic unit — **at most one latch per `(ticker, action_session_date)` can ever be opened** — which is also the semantically correct reading (a session has ONE verdict) and needs no intraday timestamp. It strengthens rather than weakens the SLDB 9/10, YOU 31/32 and NVCR 94/95 cases: all three ARE the same-session case.

**Justification against the settled latch semantics** (brief §0): the latch "clears ONLY on (a) FILL, (b) SETUP INVALIDATION, (c) HORIZON. **Bucket-label flicker NEVER clears it.**" A ticker that goes `aplus → watch → aplus` has flickered; treating the second `aplus` as a NEW latch would let flicker *reset* the latch, which is the same category of error the semantics forbid — it would move the frozen pivot and restart the horizon clock. A latch is a MANDATE; the mandate already exists; a second fire re-affirms it, it does not create a second mandate. Constraint 3's actual purpose ("concurrent/sequential latches on one ticker must never merge or overwrite") is fully preserved: VSTS @ 99 and VSTS @ 126 are separate latches because the first one CLEARED (filled by trade 17 on 2026-06-25) before the second fired. Constraint 1 is preserved exactly: the frozen values come from the OPENING fire's own row and are never rewritten.

**Empirical note (honest):** on the current corpus the naive per-row rule produces the same *prices* (SLDB/YOU/NVCR re-fires are byte-identical), so this rule cannot be justified by a live price diff. It is justified structurally, and the SLDB 9/10/12 fixture fails a naive per-row implementation on **latch COUNT** (3 vs 1), which is a hard, discriminating assertion.

**Canonical surrogate key:** the OPENING fire's **`candidates.id`**. It is exact (`candidates` has `UNIQUE(evaluation_run_id, ticker)`), immutable (grep confirms zero `UPDATE candidates` / `DELETE FROM candidates` anywhere in `swing/`, `research/`, `scripts/`), and already an established FK target (`trades.candidate_id`, migration 0021). No `latches` registry table is needed now, and one remains cheaply backfillable later because the identity is stored EXACTLY, not by convention.

### A.3 RULING 2 — freeze at fire time (RD constraint 1)

All prices come from the OPENING fire's own `candidates` row and NEVER a later row:

- `latched_pivot = fire_row.pivot`
- `latched_initial_stop = fire_row.initial_stop`
- `zone_cap = round(latched_pivot * (1 + LATCH_ZONE_CAP_PCT / 100), 4)` with `LATCH_ZONE_CAP_PCT = 3.0`

**The discriminating fixture (FTRE):** eval run 121 gives 18.34 / **14.88**. Runs 122-125 (all `bucket='watch'`, all present in the DB) drift to stop 15.195 → 15.25 → **16.515** → 16.515 and pivot 18.59 → 20.19. A derivation reading "the latest row for this ticker" renders **16.51** — the exact value RD himself quoted to the operator, ~11% early. The test seeds runs 121-125 and asserts `14.88`; it FAILS a latest-row implementation.

### A.4 RULING 3 — horizon in SESSIONS (RD constraint 2) (**RD DECISION REQUIRED — see §G.2**)

```
LATCH_HORIZON_SESSIONS = 20
anchor              = fire_row.action_session_date          (the FIRE's evaluation_runs.action_session_date)
sessions_elapsed(S) = sessions_behind(reference=S, candidate=anchor)   # swing/evaluation/dates.py:40
horizon_expiry      = session_offset(anchor, LATCH_HORIZON_SESSIONS) # NEW additive helper, Task 2
horizon_expired(S)  = sessions_elapsed(S) >= LATCH_HORIZON_SESSIONS    # inclusive-expire
sessions_to_horizon = max(0, LATCH_HORIZON_SESSIONS - sessions_elapsed(S))
```

**Why 20, why this anchor, why inclusive-expire — reproduced from RD's own live arithmetic.** `docs/rd-state.md:27` states FTRE's horizon is **2026-08-17**. With `anchor = 2026-07-20` (FTRE's `action_session_date`):

| basis | result |
|---|---|
| **20 NYSE sessions forward from the action session** | **2026-08-17** — matches RD |
| 20 NYSE sessions from `data_asof_date` (2026-07-17) | 2026-08-14 |
| 30 NYSE sessions (`cfg.pipeline.observe_max_pending_window_sessions`) | 2026-08-31 |
| 20 calendar days | 2026-08-09 |

So the anchor is the **action session** (correct semantically: the first session on which the GTC order can work) and the value is **20**. `sessions_elapsed(2026-08-17) = 20`, so inclusive-expire makes 2026-08-17 the first DEAD session, i.e. "the horizon date" — RD's phrasing.

Inclusive-expire also matches the in-tree precedent: `swing/pipeline/runner.py:2960` (`if sessions_since_detection >= max_pending: return "expired", "time_exit"` — "the boundary is inclusive (>=), so a non-triggering bar AT max_pending expires").

**FLAGGED PREMISE MISMATCH:** the brief §0 calls 20 "the shadow-parity bound". The pipeline's shadow entry window is **`observe_max_pending_window_sessions = 30`** (`swing/config.py:221`), not 20. The "20" is corroborated instead by `docs/research-director-context.md:146` — *"longest window 20 sessions (engine horizon cap)"* — the OBSERVED maturity of the log, plus RD's own 08-17 arithmetic. This plan implements **20** as a single named constant `LATCH_HORIZON_SESSIONS` in `swing/latches/constants.py` (one place to change) and routes the value to RD's gate. See §G.2.

### A.5 RULING 4 — invalidation on CLOSES (RD constraint 6)

The latch invalidates on the **first completed daily bar at-or-after the anchor whose `close < latched_initial_stop`**. An intraday `low` below the stop that closes at-or-above it does **NOT** invalidate. Strict `<` (a close exactly AT the stop is not below it).

Bars come from the **on-disk archive only** via `resolve_ohlcv_window(ticker, start=<anchor ISO>, end=<derivation_session ISO>, cache_dir=cfg.paths.prices_cache_dir)` (`swing/data/ohlcv_archive.py:971`) — a pure two-provider parquet read with **zero network I/O**, the same reader the pipeline observe step uses (`swing/pipeline/runner.py:3011`). Verified present for the live subjects: `FTRE.{yfinance,schwab_api}.parquet` (778/767 rows through 2026-07-24), `VSTS.*` (708/704 rows). Archives are warmed nightly for every screened ticker (`swing/pipeline/runner.py:1459` — `warm_set = [benchmark, *candidate_tickers, *universe_tickers]`).

**"base break" is OUT OF V1 SCOPE.** The brief §0 says invalidation is "close below the fire-time initial-stop / base break". V1 implements the close-below-initial-stop half only; the structural base-break level is not carried on `candidates` (it lives in `pattern_detection_events.structural_anchors_json`, a different id space with no rows before mid-June). Banked in §H.

### A.6 RULING 5 — latch-specific fill detection (RD constraint 4)

Two-rung ladder, EXACT first:

1. **EXACT (`fill_link_basis='candidate_id'`):** a `trades` row whose `candidate_id` is in this latch's candidate set (opening fire + all re-confirmations) **AND** whose `entry_date >= anchor`. Live proof this is real, not theoretical: trade 17 (VSTS) carries `candidate_id = 8851` = the run-99 fire row; trade 18 (AMN) carries `candidate_id = 9276` = the run-103 fire row. 8 of 18 trades carry a non-NULL `candidate_id`.
2. **WINDOWED (`fill_link_basis='windowed'`):** only when `trades.candidate_id IS NULL` — ticker match AND `anchor <= entry_date <= effective_end`, where **`effective_end = min(horizon_expiry, non_fill_terminal_session)`** and `non_fill_terminal_session` is the session at which this latch would clear by invalidation or horizon ABSENT any fill (`horizon_expiry` when it would not clear). (Legacy rows: trade 4 YOU has `candidate_id = NULL`.)
3. Otherwise: no fill.

**Overlapping-window disambiguation (Codex R1-3).** Latch windows on one ticker CAN overlap: latch 2 opens once latch 1 is terminal, but latch 1's NOMINAL `horizon_expiry` extends past its ACTUAL clear session whenever it cleared early by invalidation or fill. A legacy NULL-`candidate_id` trade dated between latch 2's anchor and latch 1's nominal expiry would otherwise satisfy BOTH. Three deterministic rules close it:

- **(a) Bound by the ACTUAL live window,** not the nominal horizon — the `effective_end` above. A trade dated after a latch's invalidation session is not that latch's fill.
- **(b) One trade fills at most one latch.** Latches are resolved per ticker in `anchor` order against a running `consumed_trade_ids` set; the windowed rung only considers unconsumed entries. Earliest-anchor latch wins a contested entry. (The EXACT rung consumes first and unconditionally — an explicit `candidate_id` beats any windowed claim.)
- **(c) Two-pass terminal resolution removes the circularity** (the fill bounds the terminal; the terminal bounds the fill): **pass 1** computes the NON-FILL terminal (invalidation walk, then horizon) over `[anchor, derivation_session]`; **pass 2** searches for a fill within `[anchor, effective_end]`; **pass 3** applies the fill > invalidation > horizon precedence of §A.7. `derive_latches` performs both passes inside its per-ticker fold, so the open-latch rule's liveness test (§A.2 clause ii) always sees a fully-resolved terminal.

A `candidate_id` match with `entry_date < anchor` is **NOT** a fill; it sets `fill_link_anomaly = True` on the latch (surfaced in the panel) so a mis-linked row is loud rather than silently clearing a latch backwards.

**The VSTS trap (RD's live subject) is blocked on all three rungs.** Trade 17 (`entry_date=2026-06-25`, `candidate_id=8851`) vs the run-126 latch (anchor `2026-07-27`, candidate set `{<run-126 fire id>}`): 8851 not in the set → rung 1 fails; `candidate_id` is not NULL → rung 2 does not apply; and even if it were NULL, `2026-06-25 < 2026-07-27` → rung 2 fails. Trade 17 correctly clears the run-**99** latch instead (`8851` in set, `2026-06-25 >= 2026-06-25`).

### A.7 RULING 6 — clear reason RECORDED, not inferred (RD constraint 5)

**The eligible bar set is EXACTLY `{bar : anchor <= bar.session <= derivation_session}`** — inclusive at BOTH ends. The anchor session's own bar counts (the mandate is live from that session's open); a bar before the anchor is history the pivot was computed FROM, not an invalidation of a mandate that did not yet exist; a bar after `derivation_session` is a look-ahead (the archive legitimately holds one, since the nightly warm runs at 17:30 for the NEXT session). Each of those four boundaries has its own discriminating test in Task 3 — an off-by-one at either end passes every interior-case test.

Terminal states are resolved by a forward walk over that eligible set, session by session, with this **precedence within a single session**:

1. **`fill`** — a mandate that was consummated is terminal in the strongest sense; it wins even if the same bar closed below the stop (that becomes the TRADE's problem, not the latch's).
2. **`invalidation`** — close below the frozen stop.
3. **`horizon`** — `sessions_elapsed >= 20`.

(This deliberately differs from `_advance_status`'s invalidation-first precedence, which has no fill concept. Both orderings are tested.)

Each latch records `clear_reason` ∈ `{fill, invalidation, horizon}` **and** `clear_session` (ISO date) **and**, for fills, `clear_trade_id` + `fill_link_basis`. State mapping:

| state | meaning |
|---|---|
| `armed` | live, no resting broker order matched |
| `order_resting` | live, a resting BUY order matched (order-join layer only) |
| `filled` | cleared, `clear_reason='fill'` |
| `invalidated` | cleared, `clear_reason='invalidation'` |
| `horizon_expired` | cleared, `clear_reason='horizon'` |

### A.8 RULING 7 — BOTH identities stored (RD finding 4)

`LatchIdentity` carries, and `latch_view_events` persists, both id spaces explicitly:

- **evaluation identity:** `candidate_id` (the surrogate key), `evaluation_run_id`, `ticker`
- **detection identity:** `detection_date` (= the fire's `evaluation_runs.action_session_date`), `pipeline_run_id`

Verified resolvable and 1:1: `SELECT evaluation_run_id, COUNT(*) FROM pipeline_runs GROUP BY 1 HAVING COUNT(*)>1` returns **zero rows**; runs 99→112, 103→116, 121→135, 126→140. Verified that the detection identity is the shadow artifact's real join key: `research/harness/shadow_expectancy/run.py:217` emits `{"ticker": ticker, "detection_date": detection_date, "run_id": pipeline_run_id, ...}` where `detection_date` comes from `pattern_detection_events.detection_date` (== the run's `action_session_date` for `source='pipeline'`, migration 0022 line 49). Verified the two id spaces genuinely collide on integers: `pipeline_runs.id = 126` has `action_session_date = 2026-07-08` while `evaluation_runs.id = 126` has `2026-07-27` — storing only one number is a live confusion trap.

`pipeline_run_id` is **NULLABLE**: `SELECT COUNT(*) FROM pattern_detection_events WHERE ticker='SLDB'` returns **0** (the temporal log postdates the April fires), and `pipeline_runs.evaluation_run_id` is NULL for the early runs. Absent linkage degrades, never raises.

### A.9 RULING 8 — the two order alarms

Broker order statuses partition into three buckets (from `_SCHWAB_ORDER_STATUSES`, `swing/integrations/schwab/models.py:38`):

```python
RESTING_ORDER_STATUSES = frozenset({
    "ACCEPTED", "AWAITING_CONDITION", "AWAITING_PARENT_ORDER",
    "AWAITING_RELEASE_TIME", "AWAITING_STOP_CONDITION", "AWAITING_UR_OUT",
    "NEW", "PENDING_ACKNOWLEDGEMENT", "PENDING_ACTIVATION", "QUEUED",
    "WAIT_TRG", "WORKING",
})
INDETERMINATE_ORDER_STATUSES = frozenset({
    "AWAITING_MANUAL_REVIEW", "PENDING_CANCEL", "PENDING_RECALL",
    "PENDING_REPLACE", "UNKNOWN",
})
# everything else (REJECTED / CANCELED / REPLACED / FILLED / EXPIRED) is TERMINAL
```

**Attribution is PER-ORDER against latch PRICES, not per-ticker liveness (Codex R1-2).** A ticker-level rule ("alarm only when the ticker has no live latch") SILENCES a stale order the moment a newer latch fires on that ticker — the exact VSTS geometry (fired 2026-06-25, cleared, fired again 2026-07-27), and precisely the operator's one manual duty going unannounced. So:

```
match_latch(order) = the latch on order.ticker whose FROZEN prices the order matches:
    round(order.stop_price, 2)  == round(latch.latched_pivot, 2)      # STOP-family
    or, when order.stop_price is None,
    round(order.limit_price, 2) == round(latch.zone_cap, 2)           # LIMIT-only
  (ties broken by the most recent anchor)
```

- **`LATCH_ARMED_NO_RESTING_ORDER`** (the FTRE mode, severity `critical`): a LIVE latch whose ticker has **ZERO** resting BUY orders. Deliberately keyed on ticker-level absence, not on `match_latch`: an order placed at a slightly wrong price must surface through the agreement flags, not through a "no order" alarm that is factually false.
- **`ORDER_RESTING_LATCH_CLEARED`** (the stale-order hazard): fires when a resting BUY order's `match_latch` is a **CLEARED** latch — **even when another latch on the same ticker is LIVE.** Attributed to that specific cleared latch. Severity `critical` when its `clear_reason == 'invalidation'` (the manual-cancel duty), `warning` otherwise.
- **Unmatched resting order:** `match_latch` is `None` (no latch's frozen prices match, or the order carries no usable price). If the ticker HAS a live latch, the order is reported against it with `order_stop_agrees=False` / `order_limit_agrees=False` and no alarm (it is a mispriced order for a live mandate, not a stale one). If the ticker has NO live latch, `ORDER_RESTING_LATCH_CLEARED` fires attributed to the ticker's most recently cleared latch, or `latch_candidate_id=None` when the ticker has no latch at all.
- **Indeterminate short-circuit:** if any INDETERMINATE-status BUY order matches the ticker, neither alarm fires for that ticker; the panel shows `order status indeterminate - verify at the broker`. A false all-clear and a false alarm are both worse than an honest "unknown".
- **Agreement check:** `order_stop_agrees = round(order.stop_price, 2) == round(latched_pivot, 2)`; `order_limit_agrees = round(order.limit_price, 2) == round(zone_cap, 2)`. Rounding to the DISPLAY precision, per the price-precision-parity gotcha. `None` on either side → `agrees = None` (unknown), never `False`.

### A.10 RULING 9 — A6 defensive degradation (verified NOT write-prevented)

Per A6's "verify whether a write path actually prevents the bad shape BEFORE dismissing it as impossible", each was checked against the real write boundary:

| bad shape | is it write-prevented? | verdict |
|---|---|---|
| `candidates.pivot IS NULL` on an `aplus` row | **NO.** Migration 0001 has no NOT NULL on `pivot` and no bucket↔pivot CHECK. `insert_candidates` (`repos/candidates.py:44`) persists whatever the dataclass carries. `bucket_for` (`evaluation/scoring.py:13`) never consults the pivot. Only `evaluate_ticker` happening to always set it prevents it — and **SQLite stores `float('nan')` as NULL** (verified), so a non-finite pivot lands as NULL with `bucket='aplus'`. 279 NULL-pivot rows already exist (233 `excluded`, 46 `error`). | **MUST degrade.** Emit `DegradedFire(reason='pivot_missing')`; render a visible degraded row; open NO latch. |
| `initial_stop IS NULL` / non-finite / `>= pivot` | Same analysis. | `DegradedFire(reason='stop_missing')` / `'stop_not_below_pivot'`. |
| zero bars in the archive for the window | Not prevented (archive is a filesystem cache; a ticker that rotates out of the screen goes stale). | Latch stays in its pre-bar state with `bars_available=False`; the panel shows `invalidation NOT evaluated - no bars`. Never a silent "not invalidated". |
| archive present but missing the trailing sessions | Not prevented. | `bars_through` (the last bar's `asof_date`) is carried on the latch and RENDERED, so staleness is visible. |
| Schwab client absent / sandbox / degraded / auth failure | Not prevented. | The order fragment renders a degraded block with the reason; alarms are SUPPRESSED (an unknown order book must not fire a false FTRE alarm). |
| `pipeline_runs` row absent for the fire's eval run | Not prevented (true for all pre-June fires). | `pipeline_run_id=None`; panel renders `-`. |
| malformed `detection_date` / `action_session_date` TEXT | Not prevented at the `evaluation_runs` writer. | `date.fromisoformat` at the TEXT→`date` boundary inside a try/except → `DegradedFire(reason='bad_session_date')`. |

The whole panel builder is additionally wrapped in the `build_tool_health_vm` degrade-to-grey pattern (`swing/web/view_models/health.py:87`) so no unforeseen exception 500s the page.

---

## B. File structure

**Create**

| path | responsibility |
|---|---|
| `swing/data/migrations/0032_latch_view_telemetry.sql` | the ONE new table + indexes + `schema_version` 31→32 |
| `swing/data/repos/latch_view_events.py` | `record_view` (SELECT-then-UPDATE-or-INSERT), `list_views_for_session`, `get_view` |
| `swing/latches/__init__.py` | package marker + public re-exports |
| `swing/latches/constants.py` | `LATCH_HORIZON_SESSIONS`, `LATCH_ZONE_CAP_PCT`, `LATCH_STATES`, `LATCH_CLEAR_REASONS`, `LATCH_DEGRADED_REASONS`, `RESTING_ORDER_STATUSES`, `INDETERMINATE_ORDER_STATUSES`, `LATCH_PANEL_LOOKBACK_SESSIONS`, `BUY_INSTRUCTIONS` |
| `swing/latches/identity.py` | `LatchIdentity` (frozen dataclass, both id spaces, validators) |
| `swing/latches/models.py` | `FireRow`, `DailyBar`, `EntryRecord`, `RestingOrder`, `Latch`, `DegradedFire`, `LatchDerivation`, `LatchOrderJoin`, `OrderAlarm` |
| `swing/latches/service.py` | `derive_latches(...)` — the PURE fold (open-latch rule + terminal resolution) |
| `swing/latches/orders.py` | `join_orders_to_latches(...)` — PURE |
| `swing/latches/reader.py` | the impure adapter: `load_fire_rows`, `load_entry_records`, `load_bars`, `build_latch_derivation` |
| `swing/web/routes/latches.py` | `GET /latches` (writes NOTHING), `POST /latches/orders`, `POST /latches/view` |
| `swing/web/view_models/latches.py` | `LatchPanelVM`, `LatchRowVM`, `DegradedRowVM`, `LatchOrdersFragmentVM`, `OrdersResolution`, `build_latch_panel_vm`, `build_latch_orders_vm`, `resolve_open_orders` |
| `swing/web/templates/latches.html.j2` | the panel page |
| `swing/web/templates/partials/latch_orders.html.j2` | the lazy order-awareness fragment |
| `tests/latches/__init__.py`, `test_identity.py`, `test_service_fire_grouping.py`, `test_service_terminal.py`, `test_orders.py`, `test_reader.py` | derivation tests |
| `tests/data/test_latch_view_events_repo.py`, `tests/data/test_migration_0032.py` | schema + repo tests |
| `tests/web/test_routes/test_latches_route.py`, `tests/web/test_view_models/test_latch_panel_vm.py`, `tests/web/test_latches_telemetry_beacon.py` | web tests |

**Modify**

| path | change |
|---|---|
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION` 31→32; `PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES`; `_create_pre_phase21_arc_a_migration_backup`; `_phase21_arc_a_backup_gate`; wire the gate into `run_migrations` |
| `swing/data/models.py` | `_LATCH_VIEW_STATES` frozenset + `LatchViewEvent` dataclass with `__post_init__` |
| `swing/evaluation/dates.py` | **ADD** `session_offset(reference, n)` (purely additive; no existing function touched — the ratified 18-E `sessions_behind` precedent) |
| `swing/integrations/schwab/models.py` | **ADD** tail-appended optional `stop_price: float | None = None` on `SchwabOrderResponse` + its validator |
| `swing/integrations/schwab/mappers.py` | populate `stop_price` from `stopPrice`; `price` semantics UNCHANGED |
| `swing/web/app.py` | `app.include_router(latches_route.router)` |
| `swing/web/templates/base.html.j2` | one nav link `<a href="/latches">Latches</a>` after Watchlist |
| `swing/web/static/app.css` | latch state/alarm tokens under `:root` + `body.dark`, `var()`-only rules |
| `tests/web/test_base_layout_nav.py` | `EXPECTED_NAV_HREFS` gains `/latches` (exact-order pin) |
| `tests/web/test_topbar_cross_vm_consistency.py` | `MANIFEST` gains `LatchPanelVM: PageKind.FORWARD_PLANNING` (mechanical completeness pin) |

---

## C. Schema: the one new table, and exactly how it extends to 21-B (A1)

### C.1 The table

```sql
CREATE TABLE latch_view_events (
    view_event_id      INTEGER PRIMARY KEY AUTOINCREMENT,

    -- ===== LATCH IDENTITY BLOCK =====
    -- The shared contract. 21-B's ledger table copies these five columns
    -- VERBATIM (see swing/latches/identity.py:LATCH_IDENTITY_COLUMNS).
    --
    -- candidate_id is the IMMUTABLE BRIDGE KEY: the OPENING fire's
    -- candidates.id. NOT NULL + ON DELETE RESTRICT (the migration-0022
    -- pattern_forward_observations.detection_id precedent -- "append-only:
    -- cannot delete a detection with observations"), NOT the SET NULL used for
    -- audit LINKAGES below. RESTRICT is what makes the 21-A <-> 21-B join a
    -- real key rather than a convention: a future pruner cannot silently sever
    -- the ledger, it fails loudly. (Deleting a candidates row IS possible --
    -- tests/data/test_v21_migration_trade_backlinks.py:346 does it -- which is
    -- exactly why SET NULL would be wrong here.)
    candidate_id       INTEGER NOT NULL REFERENCES candidates(id) ON DELETE RESTRICT,
    evaluation_run_id  INTEGER NOT NULL,
    ticker             TEXT NOT NULL,
    detection_date     TEXT NOT NULL,
    pipeline_run_id    INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,

    -- ===== VIEW TELEMETRY =====
    view_session_date         TEXT NOT NULL,
    first_viewed_ts           TEXT NOT NULL,
    last_viewed_ts            TEXT NOT NULL,
    view_count                INTEGER NOT NULL,
    latch_state_at_first_view TEXT NOT NULL,
    latch_state_at_last_view  TEXT NOT NULL,

    CHECK (latch_state_at_first_view IN
        ('armed','order_resting','filled','invalidated','horizon_expired')),
    CHECK (latch_state_at_last_view IN
        ('armed','order_resting','filled','invalidated','horizon_expired')),
    CHECK (view_count >= 1),
    CHECK (evaluation_run_id > 0),
    CHECK (length(trim(ticker)) > 0),
    CHECK (length(detection_date) = 10 AND date(detection_date) IS NOT NULL),
    CHECK (length(view_session_date) = 10 AND date(view_session_date) IS NOT NULL),
    CHECK (last_viewed_ts >= first_viewed_ts),

    UNIQUE (evaluation_run_id, ticker, view_session_date)
);
```

**Why these columns and no others.**
- The five identity columns are RD finding-4 verbatim (BOTH id spaces, explicit). `candidate_id` is the IMMUTABLE surrogate latch key (`NOT NULL`, `ON DELETE RESTRICT`); `evaluation_run_id` / `ticker` / `detection_date` are NOT NULL denormalized copies so the record is human-readable and shadow-joinable for years without a join; `pipeline_run_id` is the one true audit LINKAGE and keeps `ON DELETE SET NULL` (`pipeline_runs` genuinely IS pruned — the migration-0022/0030 convention).
- `view_session_date` + the `UNIQUE` triple bound growth: one row per latch per action session, however many times the operator refreshes. `first_viewed_ts` answers "how long after the fire did he first look" — a real discipline metric — and is IMMUTABLE after insert. `last_viewed_ts` / `view_count` advance monotonically (no fact is destroyed).
- `latch_state_at_first_view` / `latch_state_at_last_view` are what make the record *evidence* of RD's actual requirement ("viewed **while a latch was armed**") rather than something re-derived at read time against a world that has since changed.
- **Dropped as speculative:** a `surface` column (only the web can view a panel), any action/attestation column (21-B, per RD's telemetry-scope discipline), any denormalized price snapshot (the derivation is the source of truth; a persisted copy could drift).

### C.2 How this extends to 21-B (the A1 answer, stated explicitly)

**ONE table does NOT honestly serve both.** 21-B's stage-1 ledger (phase scope §"Stage-1 ledger shape") needs the framework's computed order + its derivation inputs, the three-state action + reason, the per-field framework-vs-actual delta, attestation, order-validity outcome, and outcome linkage — roughly 18 columns about a *different subject* (an order presentation and its disposition). Folding them here would leave every 21-A row carrying 18 permanent NULLs and every 21-B row carrying 6 NULL view columns — the one-table-two-jobs smell.

**What IS delivered (a real key, not a convention) — Codex R2-2.**

1. **An IMMUTABLE BRIDGE KEY: `candidate_id`, `NOT NULL`, `ON DELETE RESTRICT`** to `candidates(id)`. `candidates` is append-only in production (zero `UPDATE`/`DELETE` statements in `swing/`, `research/`, `scripts/`), the row is UNIQUE on `(evaluation_run_id, ticker)`, and RESTRICT means a future pruner cannot silently sever the ledger — it fails loudly. 21-B's `latch_order_intents` stores the SAME integer with the SAME constraint, so the two ledgers join as `ON a.candidate_id = b.candidate_id`: one integer, no re-derivation, no naming convention, no join problem punted. This is the specific thing RD's finding 4 demands and the specific thing round 1's design (`ON DELETE SET NULL`, nullable) failed to guarantee.
2. **A mechanically-pinned column contract.** `swing/latches/identity.py` ships `LATCH_IDENTITY_COLUMNS` and the `LatchIdentity` dataclass as the single source of truth; Task 1's migration test asserts the migration's columns 2-6 EQUAL that tuple, so a 21-B divergence cannot ship silently.
3. **A single producer.** `swing/latches/service.py:derive_latches` is the only thing that computes latch identity + frozen prices + state; 21-B's order computation CONSUMES its output rather than re-deriving, so the two ledgers cannot disagree about what a latch is.
4. **A shared state vocabulary.** `LATCH_STATES` / `LATCH_CLEAR_REASONS` are importable constants; a 21-B CHECK widens from the same frozensets under the #11 discipline.

**What is explicitly NOT delivered, and why.** There is **no `latches` registry table** — i.e. no row that exists for a latch merely because the latch exists. 21-A cannot honestly create one: the only write seam it owns is the view beacon (A4), so a registry populated from 21-A would contain exactly the latches the operator happened to LOOK AT, which is not a registry. 21-B, which writes on a deliberate operator action, is the right place to add one if it wants it. **Promotion path (so 21-B is not cornered):** add `latches(latch_id INTEGER PRIMARY KEY, candidate_id INTEGER NOT NULL UNIQUE REFERENCES candidates(id) ON DELETE RESTRICT, ...)` plus a nullable `latch_id` on both children, backfilled by `UPDATE ... SET latch_id = (SELECT latch_id FROM latches WHERE candidate_id = <child>.candidate_id)` — deterministic and total, precisely because `candidate_id` is NOT NULL and immutable here.

**21-B's migration is its own** (A3): this arc's `0032` contains exactly one `CREATE TABLE` and the version bump.

---

## D. The A4 write seam: an HTMX beacon POST with a rendered-set anchor

**Chosen seam: `POST /latches/view`, fired by HTMX `hx-trigger="load"` from the rendered panel. The panel GET (`GET /latches`) performs ZERO writes.**

Mechanics and why each part:

- **Why not a GET-side write:** GETs are re-fired by refresh, browser preconnect, and prefetchers; A4 forbids it outright.
- **Why not `navigator.sendBeacon`:** `OriginGuardMiddleware` is constructed with `strict=True` (hardcoded, `swing/web/app.py:656`), so every unsafe method REQUIRES an `HX-Request: true` header. `sendBeacon` cannot set headers. HTMX sets it automatically; the element also carries `hx-headers='{"HX-Request": "true"}'` explicitly, matching the shipped `POST /prices/refresh` precedent (`dashboard.html.j2:48`).
- **Success is `204`**, which `base.html.j2`'s `htmx.config.responseHandling` maps to `swap:false` — so a successful beacon renders nothing. The element uses `hx-swap="innerHTML"` on ITSELF (not `"none"`) so a `400`/`409` fragment CAN render (4xx swapping is already enabled in that same config). No `HX-Redirect` (nothing to navigate to).
- **The anchor (web hazard 2, GET/POST staleness TOCTOU — Codex R2-1):** the beacon posts a form body carrying `view_session_date=<ISO>` and `candidate_ids=<comma-separated ints>` — the session the GET was rendered FOR, and the exact latch set it rendered as LIVE. (Form encoding, not JSON: `swing/web/static/` ships only `htmx.min.js`; the `json-enc` extension is not vendored and must not be added.) The handler does **NOT** recompute "the latest session" at POST time; that is precisely the recompute the project's own hazard-2 gotcha forbids ("If the operator saw the value at form-render time, emit it as a hidden anchor and validate the POST against that exact anchor's row — don't recompute 'latest' at POST time"). Instead:
  1. **VALIDATE the session anchor** (never trust it): it must parse as an ISO date, must be `<= action_session_for_run(now)`, and must be within ONE session of it (`sessions_behind(action_session_for_run(now), submitted) <= 1`). A malformed or FUTURE anchor → `400`. A well-formed but MORE-THAN-ONE-SESSION-STALE anchor → **`409` + a LOUD, ACTIONABLE fragment**, never a silent drop (Codex R5-2).

     **Why the staleness bound stays (and why Codex's proposed removal is rejected).** The beacon fires milliseconds after render, so the only LEGITIMATE staleness is a session rollover inside that gap — at most one session. An anchor older than that is, by construction, a page RESTORED from cache / a back-button navigation / a re-opened tab from a previous session. Accepting it would WRITE A VIEW RECORD FOR A SESSION ON WHICH THE OPERATOR DID NOT VIEW THE PANEL — manufacturing evidence in the flattering direction, which is the bias RD's do-not-flatter rule forbids most strongly. Codex's fix ("do not hard-reject solely because it is older than one session") would open exactly that hole.

     **But the criticism's real half is accepted:** silently discarding it biases the record toward false `away`, which is the SAME sin in the other direction. So the rejection is made VISIBLE instead of silent: `409` + `log.warning` naming both sessions + an HTML fragment reading `This page is stale (rendered for <anchor>; current session is <current>). Reload to record your view.` `base.html.j2`'s `htmx.config.responseHandling` already swaps 4xx, so with `hx-swap="innerHTML"` on the beacon element the notice RENDERS. The operator reloads and the view is recorded honestly for the CURRENT session. Neither bias is introduced; the operator is told.

     (Consequence: the beacon element uses `hx-swap="innerHTML"` on itself, NOT `hx-swap="none"`, so the stale/error fragment can appear. The success path returns `204`, which `responseHandling` maps to `swap:false` — so a successful beacon still renders nothing.)
  2. **RE-DERIVE against THAT anchor**, not against "now": `build_latch_derivation(..., horizon_session=<validated anchor>)`. `derive_latches` already takes `horizon_session` as a parameter, so this is the natural call — it answers "which latches were live for the session the operator was looking at", which is exactly what the telemetry means.
  3. **Record the INTERSECTION** of the posted `candidate_ids` and that anchor-session live set. A forged id writes nothing; a legitimately-rendered view is NOT erased just because live state moved after the render.
  4. `view_session_date` is the VALIDATED ANCHOR; `latch_state_at_*` is the state AS OF that anchor session; `first_viewed_ts` / `last_viewed_ts` are **SERVER-STAMPED wall-clock at POST time** and are never read from the payload (the V1 server-stamp gotcha — validate the anchor, stamp the clock).
- **The rejection ladder** on the anchor (the 4-tier shape, extended for the session field): (a) body not parseable as a form → `400`; (b) missing `view_session_date` → `400`; (c) missing `candidate_ids` → `400`; (d) `view_session_date` not exactly a 10-char ISO date, or in the future, or more than one session stale → `400`; (e) any `candidate_ids` element not a positive decimal integer (`"1.5"`, `"0"`, `"-3"`, `"true"`, `"abc"` all rejected) → `400`. An EMPTY `candidate_ids` string is VALID and writes nothing (`204`). Cap at 200 ids → `400` beyond (a trivial flood guard). On any `400` the response body names the offending field so a broken beacon is diagnosable.
- **Idempotency:** `record_view` is SELECT-then-UPDATE-or-INSERT on `UNIQUE(evaluation_run_id, ticker, view_session_date)`. **NEVER `INSERT OR REPLACE`** (the cascade-wipe / new-PK gotcha). A refresh storm produces one row with an advancing `view_count`.
- **Transaction:** the route owns `with conn:`; the repo functions issue no BEGIN/COMMIT (the repo-vs-service asymmetry).
- **Observability of a broken beacon (the honest-instrument mitigation):** the panel RENDERS each live latch's persisted telemetry (`first viewed <ts> (n views)` or `NOT YET RECORDED THIS SESSION`) from the *previous* view. If the beacon is silently broken (JS disabled, blocked), the operator sees "NOT YET RECORDED" on every visit — a self-revealing failure. This matters because a false-negative view record would classify a genuinely-seen fire as `away`, which biases the 21-B discipline signal OPTIMISTIC — exactly what RD's do-not-flatter rule forbids. Named as a known limitation in §H.
- **Not in this arc (RD's telemetry-scope discipline):** no attestation prompt, no three-state action capture, no reason field. One view-timestamp record, period.

### D.1 The order fragment is a **POST**, not a GET (Codex R4-1)

The order-awareness fragment performs an **audited external call**: `trader.get_account_orders` inserts a `schwab_api_calls` audit row by the typed-`SchwabApiError` audit-row-close contract that EVERY Schwab wrapper enforces. That is a write. Calling the endpoint `GET` would (a) be a lie about the method's safety, (b) contradict A4's own rule in the same arc that asserts it, and (c) expose a real broker API call to browser prefetch / preconnect / refresh.

Round 1 of this plan justified it as "the same incidental audit-on-GET the shipped `/trades/new` entry form already performs". That precedent is real, but it is not a reason to repeat it in an arc whose binding condition is precisely "the GET path does not write". So:

**`POST /latches/orders`**, fired by HTMX the same way the beacon is:
```html
<section id="latch-orders" hx-post="/latches/orders" hx-trigger="load"
         hx-target="this" hx-swap="innerHTML"
         hx-headers='{"HX-Request": "true"}'>
  <p class="muted">Checking broker orders...</p>
</section>
```
Returns an HTML fragment with `200` (the `POST /prices/refresh` + reconcile-fragment precedent for a POST that returns markup). A `GET` on that path must be **405** — pinned by a test. The audit write is therefore on a POST, where a write belongs; it writes AUDIT rows only and NEVER a domain row (no `latch_view_events`, no `trades`, no `fills`) — pinned by a test that snapshots the row counts of every domain table across the call.

**Net result: `GET /latches` is the ONLY GET this arc adds, and it writes NOTHING AT ALL.** Both writes (the audit row, the view record) are on POSTs.

---

## E. Tasks

### Task 1: Schema + model + repo (the #11 one-commit multi-mirror task)

**Files:**
- Create: `swing/data/migrations/0032_latch_view_telemetry.sql`
- Create: `swing/data/repos/latch_view_events.py`
- Create: `swing/latches/__init__.py`, `swing/latches/constants.py`, `swing/latches/identity.py`
- Modify: `swing/data/db.py`, `swing/data/models.py`
- Test: `tests/data/test_migration_0032.py`, `tests/data/test_latch_view_events_repo.py`, `tests/latches/__init__.py`, `tests/latches/test_identity.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `swing.latches.constants.LATCH_STATES: frozenset[str]`, `LATCH_CLEAR_REASONS: frozenset[str]`, `LATCH_HORIZON_SESSIONS: int`, `LATCH_ZONE_CAP_PCT: float`, `LATCH_PANEL_LOOKBACK_SESSIONS: int`, `LATCH_DEGRADED_REASONS: frozenset[str]`, `RESTING_ORDER_STATUSES`, `INDETERMINATE_ORDER_STATUSES`, `BUY_INSTRUCTIONS`
  - `swing.latches.identity.LatchIdentity(candidate_id: int, evaluation_run_id: int, ticker: str, detection_date: str, pipeline_run_id: int | None)`; `LATCH_IDENTITY_COLUMNS: tuple[str, ...]`
  - `swing.data.models.LatchViewEvent(...)`
  - `swing.data.repos.latch_view_events.record_view(conn, *, identity, view_session_date, viewed_ts, latch_state) -> int`, `list_views_for_session(conn, *, view_session_date) -> list[LatchViewEvent]`, `get_view(conn, *, evaluation_run_id, ticker, view_session_date) -> LatchViewEvent | None`

- [ ] **Step 1: Write the failing tests**

`tests/latches/test_identity.py`:
```python
"""LatchIdentity + the shared identity-column contract (RD finding 4)."""
from __future__ import annotations

import pytest

from swing.latches.constants import (
    LATCH_CLEAR_REASONS,
    LATCH_HORIZON_SESSIONS,
    LATCH_STATES,
    LATCH_ZONE_CAP_PCT,
)
from swing.latches.identity import LATCH_IDENTITY_COLUMNS, LatchIdentity


def _ident(**over):
    base = dict(
        candidate_id=8851, evaluation_run_id=99, ticker="VSTS",
        detection_date="2026-06-25", pipeline_run_id=112,
    )
    base.update(over)
    return LatchIdentity(**base)


def test_identity_carries_both_id_spaces():
    i = _ident()
    assert (i.evaluation_run_id, i.ticker) == (99, "VSTS")
    assert (i.ticker, i.detection_date) == ("VSTS", "2026-06-25")
    assert i.candidate_id == 8851
    assert i.pipeline_run_id == 112


def test_identity_allows_absent_pipeline_run_id():
    assert _ident(pipeline_run_id=None).pipeline_run_id is None


@pytest.mark.parametrize("bad", ["", "  ", "2026-6-25", "26-06-25", "garbage"])
def test_identity_rejects_malformed_detection_date(bad):
    with pytest.raises(ValueError, match="detection_date"):
        _ident(detection_date=bad)


def test_identity_rejects_blank_ticker():
    with pytest.raises(ValueError, match="ticker"):
        _ident(ticker="   ")


@pytest.mark.parametrize("field", ["candidate_id", "evaluation_run_id"])
def test_identity_rejects_bool_and_nonpositive_ints(field):
    with pytest.raises(ValueError, match=field):
        _ident(**{field: True})
    with pytest.raises(ValueError, match=field):
        _ident(**{field: 0})


def test_identity_column_contract_is_the_five_shared_columns():
    """21-B copies this tuple verbatim; a silent reorder/rename breaks the join."""
    assert LATCH_IDENTITY_COLUMNS == (
        "candidate_id", "evaluation_run_id", "ticker",
        "detection_date", "pipeline_run_id",
    )


def test_locked_constants():
    assert LATCH_HORIZON_SESSIONS == 20
    assert LATCH_ZONE_CAP_PCT == 3.0
    assert LATCH_STATES == frozenset(
        {"armed", "order_resting", "filled", "invalidated", "horizon_expired"})
    assert LATCH_CLEAR_REASONS == frozenset({"fill", "invalidation", "horizon"})
```

`tests/data/test_migration_0032.py`:
```python
"""Migration 0032 - latch_view_events + the v31 -> v32 backup gate."""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES,
    ensure_schema,
)
from swing.latches.identity import LATCH_IDENTITY_COLUMNS


_INSERT = (
    "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, ticker, "
    "detection_date, pipeline_run_id, view_session_date, first_viewed_ts, "
    "last_viewed_ts, view_count, latch_state_at_first_view, "
    "latch_state_at_last_view) VALUES (?, 99, 'VSTS', ?, NULL, ?, "
    "'2026-06-25T10:00:00', '2026-06-25T10:00:00', 1, ?, 'armed')")


def _fresh(tmp_path):
    """Schema + ONE real candidates row (candidate_id is NOT NULL / RESTRICT)."""
    conn = ensure_schema(tmp_path / "t.db")
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(99, '2026-06-24T20:06:25', '2026-06-24', '2026-06-25', 1, 1, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(99, 'VSTS', 'aplus', 13.49, 13.56, 11.62, 'universe')")
    return conn, int(cur.lastrowid)


def test_expected_schema_version_is_32():
    assert EXPECTED_SCHEMA_VERSION == 32


def test_table_exists_with_identity_block_first(tmp_path):
    conn, _ = _fresh(tmp_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(latch_view_events)")]
        assert cols[0] == "view_event_id"
        assert tuple(cols[1:6]) == LATCH_IDENTITY_COLUMNS
    finally:
        conn.close()


def test_candidate_id_is_not_null_and_restricts_deletes(tmp_path):
    """The IMMUTABLE BRIDGE KEY (Codex R2-2). NOT NULL, and a delete of the
    referenced candidates row must FAIL LOUDLY rather than silently severing
    the 21-A <-> 21-B join. SET NULL here would be the 'unrecoverable later'
    failure RD's finding 4 forbids."""
    conn, cid = _fresh(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (None, "2026-06-25", "2026-06-25", "armed"))
        with conn:
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute("DELETE FROM candidates WHERE id = ?", (cid,))
    finally:
        conn.close()


def test_state_check_rejects_an_unknown_state(tmp_path):
    conn, cid = _fresh(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "bogus"))
    finally:
        conn.close()


def test_unique_triple_blocks_a_second_row_for_the_same_latch_session(tmp_path):
    conn, cid = _fresh(tmp_path)
    try:
        with conn:
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (cid, "2026-06-25", "2026-06-25", "armed"))
    finally:
        conn.close()


def test_malformed_detection_date_rejected(tmp_path):
    conn, cid = _fresh(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, (cid, "2026-6-25", "2026-06-25", "armed"))
    finally:
        conn.close()


def test_pre_migration_expected_tables_equals_the_v31_set():
    """0031 added NO table, so the v31 set == the 18-H.6 pre-migration set."""
    from swing.data.db import PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES
    assert PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES == (
        PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES)


@pytest.mark.parametrize("current,target,should_fire", [
    (31, 32, True),    # THE intended case -- without this cell a gate that
                       # NEVER fires passes the whole test (Codex R4-2)
    (30, 32, False),   # multi-version jump bypasses by design; also the cell
                       # that discriminates a buggy `current_version <= 31`
    (31, 31, False),   # target below the gate
    (32, 32, False),   # already past
])
def test_backup_gate_fires_only_on_the_strict_31_to_32_step(
        tmp_path, monkeypatch, current, target, should_fire):
    """STRICT `current_version == 31 AND target_version >= 32`, per the
    `pre_version == (target - 1)` gotcha (NEVER `<=`).

    The FULL boundary matrix is required. A single negative cell is not enough:
    a gate whose body is an unconditional `return` passes any all-negative
    test, and a silently-dead backup gate is the more dangerous failure of the
    two. (Verified arithmetic: cell (30,32) alone DOES discriminate the `<=`
    form, but nothing discriminated a dead gate until cell (31,32) was added.)
    """
    from swing.data import db as db_mod
    fired = []
    monkeypatch.setattr(
        db_mod, "_create_pre_phase21_arc_a_migration_backup",
        lambda src, *, dest_dir: (fired.append(src), tmp_path / "b.db")[1])
    monkeypatch.setattr(db_mod, "_verify_backup_integrity",
                        lambda path, *, expected_tables: None)
    monkeypatch.setattr(db_mod, "_resolve_main_db_path",
                        lambda conn: tmp_path / "src.db")
    db_mod._phase21_arc_a_backup_gate(
        sqlite3.connect(":memory:"), current_version=current,
        target_version=target, backup_dir=tmp_path)
    assert bool(fired) is should_fire


def test_backup_gate_verifies_against_the_declared_table_set(tmp_path, monkeypatch):
    """The gate must pass PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES to the
    verifier -- a gate that backs up but verifies nothing is a false net."""
    from swing.data import db as db_mod
    seen = {}
    monkeypatch.setattr(
        db_mod, "_create_pre_phase21_arc_a_migration_backup",
        lambda src, *, dest_dir: tmp_path / "b.db")
    monkeypatch.setattr(
        db_mod, "_verify_backup_integrity",
        lambda path, *, expected_tables: seen.update(t=expected_tables))
    monkeypatch.setattr(db_mod, "_resolve_main_db_path",
                        lambda conn: tmp_path / "src.db")
    db_mod._phase21_arc_a_backup_gate(
        sqlite3.connect(":memory:"), current_version=31,
        target_version=32, backup_dir=tmp_path)
    assert seen["t"] == PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES
```

`tests/data/test_latch_view_events_repo.py`:
```python
"""latch_view_events repo - SELECT-then-UPDATE-or-INSERT, never INSERT OR REPLACE."""
from __future__ import annotations

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.latch_view_events import get_view, list_views_for_session, record_view
from swing.latches.identity import LatchIdentity


@pytest.fixture
def conn_and_identity(tmp_path):
    """A migrated DB with ONE real candidates row, plus the LatchIdentity that
    points at it (candidate_id is NOT NULL / ON DELETE RESTRICT)."""
    conn = ensure_schema(tmp_path / "t.db")
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(99, '2026-06-24T20:06:25', '2026-06-24', '2026-06-25', 1, 1, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(99, 'VSTS', 'aplus', 13.49, 13.56, 11.62, 'universe')")
    ident = LatchIdentity(
        candidate_id=int(cur.lastrowid), evaluation_run_id=99, ticker="VSTS",
        detection_date="2026-06-25", pipeline_run_id=None)
    yield conn, ident
    conn.close()


def test_first_view_inserts_with_count_one(conn_and_identity):
    conn, ident = conn_and_identity
    with conn:
        rid = record_view(
            conn, identity=ident, view_session_date="2026-06-25",
            viewed_ts="2026-06-25T10:00:00", latch_state="armed")
    row = get_view(conn, evaluation_run_id=99, ticker="VSTS",
                   view_session_date="2026-06-25")
    assert row is not None and row.view_event_id == rid
    assert row.view_count == 1
    assert row.first_viewed_ts == row.last_viewed_ts == "2026-06-25T10:00:00"
    assert row.latch_state_at_first_view == "armed"
    assert row.candidate_id == ident.candidate_id


def test_second_view_same_session_updates_in_place_preserving_pk_and_first_ts(
        conn_and_identity):
    conn, ident = conn_and_identity
    with conn:
        rid = record_view(conn, identity=ident, view_session_date="2026-06-25",
                          viewed_ts="2026-06-25T10:00:00", latch_state="armed")
    with conn:
        rid2 = record_view(conn, identity=ident, view_session_date="2026-06-25",
                           viewed_ts="2026-06-25T15:30:00",
                           latch_state="order_resting")
    assert rid2 == rid, "PK must be preserved (no INSERT OR REPLACE)"
    row = get_view(conn, evaluation_run_id=99, ticker="VSTS",
                   view_session_date="2026-06-25")
    assert row.view_count == 2
    assert row.first_viewed_ts == "2026-06-25T10:00:00"     # IMMUTABLE
    assert row.last_viewed_ts == "2026-06-25T15:30:00"
    assert row.latch_state_at_first_view == "armed"          # IMMUTABLE
    assert row.latch_state_at_last_view == "order_resting"
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 1


def test_next_session_creates_a_second_row(conn_and_identity):
    conn, ident = conn_and_identity
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-25",
                    viewed_ts="2026-06-25T10:00:00", latch_state="armed")
    with conn:
        record_view(conn, identity=ident, view_session_date="2026-06-26",
                    viewed_ts="2026-06-26T10:00:00", latch_state="armed")
    assert len(list_views_for_session(conn, view_session_date="2026-06-26")) == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 2
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/latches/test_identity.py tests/data/test_migration_0032.py tests/data/test_latch_view_events_repo.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'swing.latches'` / `ImportError: cannot import name 'PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES'`.

- [ ] **Step 3: Write the migration**

`swing/data/migrations/0032_latch_view_telemetry.sql` — the DDL from §C.1, preceded by a header comment and wrapped in explicit `BEGIN;` / `COMMIT;` (gotcha #9), plus:

```sql
CREATE INDEX ix_lve_ticker_detection_date ON latch_view_events(ticker, detection_date);
CREATE INDEX ix_lve_candidate_id          ON latch_view_events(candidate_id);
CREATE INDEX ix_lve_view_session_date     ON latch_view_events(view_session_date);

UPDATE schema_version SET version = 32;   -- MUST be the final statement before COMMIT

COMMIT;
```

Header comment — the FK semantics here are ASYMMETRIC BY DESIGN and the comment must say so exactly (Codex R3-2; an earlier draft of this step described both FKs as `SET NULL`, which contradicts §C.1 and would have shipped a severable bridge):

```
-- 0032_latch_view_telemetry.sql
-- Phase 21 Arc 21-A: ONE view-telemetry fact per (latch, action session).
-- Atomic via explicit BEGIN; ... COMMIT; per the executescript implicit-COMMIT
-- gotcha. Bumps schema_version 31 -> 32.
--
-- Columns 2-6 are the SHARED LATCH IDENTITY BLOCK that 21-B's order-intent
-- ledger copies VERBATIM (single source of truth:
-- swing/latches/identity.py:LATCH_IDENTITY_COLUMNS).
--
-- THE TWO FKs ARE DELIBERATELY DIFFERENT:
--   candidate_id     NOT NULL ... ON DELETE RESTRICT  -- the IMMUTABLE BRIDGE
--       KEY (the OPENING fire's candidates.id). It is the join between this
--       ledger and 21-B's, so it must never be nullable and must never be
--       silently severed: RESTRICT makes a future pruner fail loudly. Mirrors
--       0022's pattern_forward_observations.detection_id RESTRICT.
--   pipeline_run_id  NULLABLE ... ON DELETE SET NULL   -- an AUDIT LINKAGE, not
--       a key. pipeline_runs IS pruned; the record must survive that with its
--       identity intact (the 0022 / 0030 audit-linkage convention). It is also
--       legitimately NULL for every pre-June-2026 fire.
--
-- first_viewed_ts + latch_state_at_first_view are IMMUTABLE after insert;
-- last_viewed_ts + latch_state_at_last_view + view_count advance monotonically
-- via UPDATE-in-place (NEVER INSERT OR REPLACE).
```

- [ ] **Step 4: Write the constants + identity module**

`swing/latches/constants.py`:
```python
"""Locked latch-derivation constants (Phase 21 Arc A).

Single source of truth for every value the latch derivation and the
21-A/21-B schema CHECKs mirror (the #11 one-commit multi-mirror discipline).
"""
from __future__ import annotations

# RD constraint 2. Reproduces RD's own live FTRE arithmetic: a fire anchored on
# action_session_date 2026-07-20 + 20 NYSE sessions == 2026-08-17, the horizon
# recorded in docs/rd-state.md. NOT 30 (cfg.pipeline.observe_max_pending_window
# _sessions) and NOT 20 calendar days (2026-08-09). See the plan section A.4.
LATCH_HORIZON_SESSIONS = 20

# The settled latch semantics: buy-zone limit cap = pivot x 1.03.
LATCH_ZONE_CAP_PCT = 3.0

# How far back the PANEL displays cleared latches (display filter only -- the
# derivation always folds every fire so the re-confirmation chain is exact).
LATCH_PANEL_LOOKBACK_SESSIONS = 40

LATCH_STATES = frozenset({
    "armed", "order_resting", "filled", "invalidated", "horizon_expired",
})
LATCH_CLEAR_REASONS = frozenset({"fill", "invalidation", "horizon"})
LATCH_FILL_LINK_BASES = frozenset({"candidate_id", "windowed"})
LATCH_DEGRADED_REASONS = frozenset({
    "pivot_missing", "stop_missing", "stop_not_below_pivot", "bad_session_date",
})

# Schwab order-status partition (swing/integrations/schwab/models.py:38).
RESTING_ORDER_STATUSES = frozenset({
    "ACCEPTED", "AWAITING_CONDITION", "AWAITING_PARENT_ORDER",
    "AWAITING_RELEASE_TIME", "AWAITING_STOP_CONDITION", "AWAITING_UR_OUT",
    "NEW", "PENDING_ACKNOWLEDGEMENT", "PENDING_ACTIVATION", "QUEUED",
    "WAIT_TRG", "WORKING",
})
INDETERMINATE_ORDER_STATUSES = frozenset({
    "AWAITING_MANUAL_REVIEW", "PENDING_CANCEL", "PENDING_RECALL",
    "PENDING_REPLACE", "UNKNOWN",
})
BUY_INSTRUCTIONS = frozenset({"BUY", "BUY_TO_OPEN", "BUY_TO_COVER"})

LATCH_ORDER_ALARMS = frozenset({
    "LATCH_ARMED_NO_RESTING_ORDER", "ORDER_RESTING_LATCH_CLEARED",
})
```

`swing/latches/identity.py`:
```python
"""The latch identity -- BOTH id spaces, stored explicitly (RD finding 4).

`(evaluation_run_id, ticker)` freezes pivot/stop; the shadow artifact keys on
`(ticker, detection_date)` and those are DIFFERENT id spaces (evaluation_runs
vs pipeline_runs -- pipeline_runs.id 126 is action session 2026-07-08 while
evaluation_runs.id 126 is 2026-07-27). Storing only one makes the shadow join
derivable-by-convention rather than exact: cheap now, unrecoverable later.

`candidate_id` (the OPENING fire's candidates.id) is the canonical surrogate
latch key -- exact (candidates has UNIQUE(evaluation_run_id, ticker)),
immutable (no UPDATE/DELETE path exists for candidates), and already an
established FK target (trades.candidate_id, migration 0021).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# The SHARED contract. 21-B's order-intent ledger copies these five column
# names VERBATIM so the two ledgers join exactly on candidate_id. Order is
# load-bearing: tests/data/test_migration_0032.py pins the migration against it.
LATCH_IDENTITY_COLUMNS: tuple[str, ...] = (
    "candidate_id", "evaluation_run_id", "ticker",
    "detection_date", "pipeline_run_id",
)


def _require_positive_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be int (not bool); got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{name} must be positive; got {value!r}")


def parse_session_date(name: str, value) -> date:
    """Convert an ISO YYYY-MM-DD TEXT column value to a `date`, or raise.

    The TEXT-column -> Python-date boundary: convert at the callsite with a
    typed error rather than letting a deep TypeError escape (CLAUDE.md).
    """
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"{name} must be an ISO YYYY-MM-DD str; got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid ISO date: {value!r}") from exc


@dataclass(frozen=True)
class LatchIdentity:
    candidate_id: int
    evaluation_run_id: int
    ticker: str
    detection_date: str          # == the FIRE's evaluation_runs.action_session_date
    pipeline_run_id: int | None

    def __post_init__(self) -> None:
        _require_positive_int("candidate_id", self.candidate_id)
        _require_positive_int("evaluation_run_id", self.evaluation_run_id)
        if not isinstance(self.ticker, str) or not self.ticker.strip():
            raise ValueError(f"ticker must be a non-blank str; got {self.ticker!r}")
        parse_session_date("detection_date", self.detection_date)
        if self.pipeline_run_id is not None:
            _require_positive_int("pipeline_run_id", self.pipeline_run_id)

    @property
    def detection_session(self) -> date:
        return parse_session_date("detection_date", self.detection_date)
```

`swing/latches/__init__.py`:
```python
"""Phase 21 Arc A -- the A+ entry-latch derivation (pure) + its readers.

The derivation is a PURE function over pre-fetched inputs: no DB access, no
network, no transaction management (the Phase-12 classifier convention). All
I/O lives in `reader.py` and the web layer.
"""
from swing.latches.identity import LATCH_IDENTITY_COLUMNS, LatchIdentity

__all__ = ["LATCH_IDENTITY_COLUMNS", "LatchIdentity"]
```

- [ ] **Step 5: Add the model mirror + the repo**

In `swing/data/models.py`, next to the other audit models:
```python
_LATCH_VIEW_STATES = frozenset({
    "armed", "order_resting", "filled", "invalidated", "horizon_expired",
})


@dataclass(frozen=True)
class LatchViewEvent:
    """One (latch, action-session) view-telemetry record (migration 0032).

    Defense-in-depth mirroring the SQL CHECKs. `first_viewed_ts` and
    `latch_state_at_first_view` are IMMUTABLE after insert; `last_viewed_ts`,
    `latch_state_at_last_view` and `view_count` advance monotonically.
    """

    view_event_id: int | None
    candidate_id: int          # NOT NULL in SQL: the immutable bridge key
    evaluation_run_id: int
    ticker: str
    detection_date: str
    pipeline_run_id: int | None
    view_session_date: str
    first_viewed_ts: str
    last_viewed_ts: str
    view_count: int
    latch_state_at_first_view: str
    latch_state_at_last_view: str

    def __post_init__(self) -> None:
        for fname in ("latch_state_at_first_view", "latch_state_at_last_view"):
            val = getattr(self, fname)
            if val not in _LATCH_VIEW_STATES:
                raise ValueError(
                    f"{fname} must be in {sorted(_LATCH_VIEW_STATES)}, got {val!r}")
        for fname, fval in (
            ("view_event_id", self.view_event_id),
            ("candidate_id", self.candidate_id),
            ("evaluation_run_id", self.evaluation_run_id),
            ("pipeline_run_id", self.pipeline_run_id),
            ("view_count", self.view_count),
        ):
            if fval is None:
                continue
            if isinstance(fval, bool) or not isinstance(fval, int):
                raise ValueError(
                    f"{fname} must be None or int (not bool), "
                    f"got {type(fval).__name__}")
        if self.evaluation_run_id <= 0:
            raise ValueError("evaluation_run_id must be positive")
        if self.candidate_id <= 0:
            raise ValueError("candidate_id must be positive (the bridge key)")
        if self.view_count < 1:
            raise ValueError("view_count must be >= 1")
        if not self.ticker.strip():
            raise ValueError("ticker must be non-blank")
        if self.last_viewed_ts < self.first_viewed_ts:
            raise ValueError("last_viewed_ts must be >= first_viewed_ts")
```

`swing/data/repos/latch_view_events.py`:
```python
"""latch_view_events repository (migration 0032, Phase 21 Arc A).

Caller-controlled tx discipline -- these functions issue NO BEGIN/COMMIT/
ROLLBACK; the route owns `with conn:`.

SELECT-then-UPDATE-or-INSERT ONLY. NEVER `INSERT OR REPLACE` (that is DELETE +
INSERT: it would issue a new PK and rewrite the immutable first-view facts).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import LatchViewEvent
from swing.latches.identity import LatchIdentity

_COLS = (
    "view_event_id, candidate_id, evaluation_run_id, ticker, detection_date, "
    "pipeline_run_id, view_session_date, first_viewed_ts, last_viewed_ts, "
    "view_count, latch_state_at_first_view, latch_state_at_last_view"
)


def _row_to_model(row: tuple) -> LatchViewEvent:
    return LatchViewEvent(
        view_event_id=row[0], candidate_id=row[1], evaluation_run_id=row[2],
        ticker=row[3], detection_date=row[4], pipeline_run_id=row[5],
        view_session_date=row[6], first_viewed_ts=row[7], last_viewed_ts=row[8],
        view_count=row[9], latch_state_at_first_view=row[10],
        latch_state_at_last_view=row[11],
    )


def get_view(
    conn: sqlite3.Connection, *, evaluation_run_id: int, ticker: str,
    view_session_date: str,
) -> LatchViewEvent | None:
    row = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events "
        "WHERE evaluation_run_id = ? AND ticker = ? AND view_session_date = ?",
        (evaluation_run_id, ticker, view_session_date),
    ).fetchone()
    return None if row is None else _row_to_model(row)


def list_views_for_session(
    conn: sqlite3.Connection, *, view_session_date: str,
) -> list[LatchViewEvent]:
    rows = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events WHERE view_session_date = ? "
        "ORDER BY ticker, evaluation_run_id",
        (view_session_date,),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def list_views_for_latch(
    conn: sqlite3.Connection, *, evaluation_run_id: int, ticker: str,
) -> list[LatchViewEvent]:
    rows = conn.execute(
        f"SELECT {_COLS} FROM latch_view_events "
        "WHERE evaluation_run_id = ? AND ticker = ? ORDER BY view_session_date",
        (evaluation_run_id, ticker),
    ).fetchall()
    return [_row_to_model(r) for r in rows]


def record_view(
    conn: sqlite3.Connection, *, identity: LatchIdentity, view_session_date: str,
    viewed_ts: str, latch_state: str,
) -> int:
    """Record a view of `identity`'s latch on `view_session_date`.

    First view of the session INSERTs (view_count=1). Subsequent views UPDATE
    IN PLACE: view_count += 1, last_viewed_ts + latch_state_at_last_view
    advance; first_viewed_ts + latch_state_at_first_view are NEVER rewritten.
    Returns the (stable) view_event_id.
    """
    existing = get_view(
        conn, evaluation_run_id=identity.evaluation_run_id,
        ticker=identity.ticker, view_session_date=view_session_date)
    if existing is not None:
        conn.execute(
            "UPDATE latch_view_events SET last_viewed_ts = ?, "
            "latch_state_at_last_view = ?, view_count = view_count + 1 "
            "WHERE view_event_id = ?",
            (viewed_ts, latch_state, existing.view_event_id))
        return int(existing.view_event_id)
    cur = conn.execute(
        "INSERT INTO latch_view_events (candidate_id, evaluation_run_id, ticker, "
        "detection_date, pipeline_run_id, view_session_date, first_viewed_ts, "
        "last_viewed_ts, view_count, latch_state_at_first_view, "
        "latch_state_at_last_view) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (identity.candidate_id, identity.evaluation_run_id, identity.ticker,
         identity.detection_date, identity.pipeline_run_id, view_session_date,
         viewed_ts, viewed_ts, latch_state, latch_state))
    return int(cur.lastrowid)
```

- [ ] **Step 6: Wire the version bump + backup gate in `swing/data/db.py`**

1. `EXPECTED_SCHEMA_VERSION = 32` and a header comment line describing 0032.
2. After `PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES`:
```python
# Phase 21 Arc 21-A (0032) pre-migration table set. 0031 rebuilt
# reconciliation_discrepancies in place -> added NO new table, so the v31 table
# set EQUALS the 18-H.6 (pre-v31) set. Derived deterministically for auditable
# provenance.
PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE18_ARC_H6_PRE_MIGRATION_EXPECTED_TABLES
)
```
3. A `_create_pre_phase21_arc_a_migration_backup` copied verbatim from `_create_pre_phase18_arc_h6_migration_backup` with the filename `swing-pre-phase21-arc-a-migration-{timestamp}.db`.
4. `_phase21_arc_a_backup_gate` copied verbatim from `_phase18_arc_h6_backup_gate` with `if target_version < 32 or current_version != 31: return` — **STRICT equality**, NOT `<=`.
5. Register the gate in `run_migrations` AFTER `_phase18_arc_h6_backup_gate`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/latches/test_identity.py tests/data/test_migration_0032.py tests/data/test_latch_view_events_repo.py -q`
Expected: PASS.
Then: `python -m pytest tests/data -q && ruff check swing/`
Expected: PASS + clean (catches any schema-version-aware fixture elsewhere in `tests/data`).

- [ ] **Step 8: Commit**

```bash
git add swing/data/migrations/0032_latch_view_telemetry.sql swing/data/db.py swing/data/models.py swing/data/repos/latch_view_events.py swing/latches tests/latches tests/data/test_migration_0032.py tests/data/test_latch_view_events_repo.py
git commit -m "feat(data): Task 1 - migration 0032 latch_view_events + LatchIdentity + repo

Schema CHECK enum, Python constant frozensets, dataclass validator and repo
guard land together per the one-commit multi-mirror discipline. Backup gate
copies the strict pre_version == target-1 clause shape verbatim."
```

---

### Task 2: `session_offset` + fire enumeration + the OPEN-LATCH rule

**Files:**
- Modify: `swing/evaluation/dates.py` (ADD `session_offset`; touch nothing existing)
- Create: `swing/latches/models.py`, `swing/latches/service.py`
- Test: `tests/evaluation/test_session_offset.py`, `tests/latches/test_service_fire_grouping.py`

**Interfaces:**
- Consumes: `swing.latches.constants.*`, `swing.latches.identity.LatchIdentity`.
- Produces:
  - `swing.evaluation.dates.session_offset(reference: date, n: int) -> date`
  - `swing.latches.models.FireRow(candidate_id, evaluation_run_id, ticker, pivot, initial_stop, action_session_date, run_ts, pipeline_run_id)`
  - `swing.latches.models.DailyBar(session: date, open: float, high: float, low: float, close: float)`
  - `swing.latches.models.EntryRecord(trade_id, ticker, entry_date, candidate_id, entry_price, shares)`
  - `swing.latches.models.Latch` / `DegradedFire` / `LatchDerivation`
  - `swing.latches.service.derive_latches(*, fires, bars_by_ticker, entries_by_ticker, horizon_session, derivation_session, horizon_sessions=LATCH_HORIZON_SESSIONS) -> LatchDerivation`

- [ ] **Step 1: Write the failing tests**

`tests/evaluation/test_session_offset.py`:
```python
"""session_offset -- the additive SIGNED NYSE session-walk helper (Arc 21-A)."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from swing.evaluation.dates import session_offset, sessions_behind


def test_zero_returns_the_reference():
    assert session_offset(date(2026, 7, 20), 0) == date(2026, 7, 20)


def test_ftre_horizon_reproduces_rds_live_arithmetic():
    """RD recorded FTRE's horizon as 2026-08-17 (docs/rd-state.md). The fire's
    action_session_date is 2026-07-20; 20 NYSE sessions forward == 2026-08-17.
    A calendar-day walk gives 2026-08-09; a 30-session walk gives 2026-08-31."""
    assert session_offset(date(2026, 7, 20), 20) == date(2026, 8, 17)
    assert session_offset(date(2026, 7, 20), 30) == date(2026, 8, 31)


def test_skips_the_july_3_2026_holiday():
    """2026-07-01 + 20 sessions == 2026-07-30 (not 2026-07-29): the observed
    July-4 holiday and two weekends are excluded."""
    assert session_offset(date(2026, 7, 1), 20) == date(2026, 7, 30)


def test_round_trips_with_sessions_behind():
    for anchor, n in ((date(2026, 7, 20), 20), (date(2026, 7, 1), 20),
                      (date(2026, 6, 25), 20), (date(2026, 7, 27), 20)):
        assert sessions_behind(session_offset(anchor, n), anchor) == n


def test_negative_n_walks_backward():
    """The derivation-session direction. 2026-07-20 is a Monday, so the prior
    session is the preceding Friday; and the July-3 holiday is skipped."""
    assert session_offset(date(2026, 7, 20), -1) == date(2026, 7, 17)
    assert session_offset(date(2026, 7, 6), -1) == date(2026, 7, 2)


def test_signed_offsets_are_inverses():
    for anchor in (date(2026, 7, 20), date(2026, 7, 1), date(2026, 7, 6)):
        assert session_offset(session_offset(anchor, -3), 3) == anchor


def test_rejects_a_bool_n():
    with pytest.raises(ValueError):
        session_offset(date(2026, 7, 20), True)


@pytest.mark.parametrize("now,expected_action", [
    (datetime(2026, 7, 20, 9, 0), date(2026, 7, 20)),    # session day, pre-close
    (datetime(2026, 7, 20, 17, 0), date(2026, 7, 21)),   # session day, post-close
    (datetime(2026, 7, 25, 12, 0), date(2026, 7, 27)),   # Saturday
    (datetime(2026, 7, 2, 12, 0), date(2026, 7, 2)),     # day before the Jul-3 holiday
])
def test_prev_session_of_the_action_anchor_equals_last_completed_session(
        now, expected_action):
    """THE INVARIANT the derivation relies on (Codex R3-1): for any clock,
    `session_offset(action_session_for_run(now), -1) == last_completed_session(now)`.
    That is what lets the beacon POST rebuild the ENTIRE render-time derivation
    context from the session anchor alone, consulting `now` for nothing that can
    change a latch's state.

    NOTE the times are Pacific/Honolulu (the helpers' default tz)."""
    from swing.evaluation.dates import action_session_for_run, last_completed_session
    action = action_session_for_run(now)
    assert action == expected_action
    assert session_offset(action, -1) == last_completed_session(now)
```

(The parametrize cases above are ILLUSTRATIVE of the four clock shapes — session-day pre-close, session-day post-close, weekend, pre-holiday. The implementer MUST compute the correct `expected_action` for each `now` under the helpers' `Pacific/Honolulu` default tz before asserting; if any case's expectation differs, fix the expectation, NOT the invariant. The invariant assertion — `session_offset(action, -1) == last_completed_session(now)` — is the load-bearing line and must hold for every case.)

`tests/latches/test_service_fire_grouping.py`:
```python
"""The OPEN-LATCH rule (plan A.2): a fire while a latch is LIVE is a
RE-CONFIRMATION, not a new latch -- so it never re-freezes the pivot."""
from __future__ import annotations

from datetime import date

from swing.latches.models import DailyBar, FireRow
from swing.latches.service import derive_latches


def _fire(cid, run, ticker, pivot, stop, session, run_ts, prid=None):
    return FireRow(candidate_id=cid, evaluation_run_id=run, ticker=ticker,
                   pivot=pivot, initial_stop=stop, action_session_date=session,
                   run_ts=run_ts, pipeline_run_id=prid)


# --- The live SLDB geometry: runs 9 + 10 share action session 2026-04-22
#     (TWO evaluation runs, ONE session); run 12 is 2026-04-24, a later
#     session, fired while the 04-22 latch was still live. -------------------
SLDB_FIRES = [
    _fire(101, 9, "SLDB", 8.866, 6.40, "2026-04-22", "2026-04-21T21:18:30"),
    _fire(102, 10, "SLDB", 8.866, 6.40, "2026-04-22", "2026-04-22T07:15:19"),
    _fire(103, 12, "SLDB", 8.866, 6.40, "2026-04-24", "2026-04-23T21:58:18"),
]


def test_sldb_three_aplus_rows_produce_exactly_one_latch():
    """FAILS a naive per-(evaluation_run_id, ticker) implementation, which
    would emit THREE latches for one mandate."""
    d = derive_latches(
        fires=SLDB_FIRES, bars_by_ticker={"SLDB": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 27), derivation_session=date(2026, 4, 24))
    assert len(d.latches) == 1
    latch = d.latches[0]
    assert latch.identity.candidate_id == 101          # the EARLIEST row wins
    assert latch.identity.evaluation_run_id == 9
    assert latch.anchor == date(2026, 4, 22)
    assert latch.reconfirmation_candidate_ids == (102, 103)


def test_reconfirmation_never_refreezes_a_drifted_pivot():
    """The invisible-on-live-data bug: identical SLDB prices hide it, so the
    test DRIFTS the re-fire. A per-row implementation freezes 9.90/7.10."""
    fires = [
        _fire(201, 9, "DRFT", 10.00, 8.00, "2026-04-22", "2026-04-21T21:00:00"),
        _fire(202, 12, "DRFT", 9.90, 7.10, "2026-04-24", "2026-04-23T21:00:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"DRFT": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 27), derivation_session=date(2026, 4, 24))
    assert len(d.latches) == 1
    assert d.latches[0].latched_pivot == 10.00
    assert d.latches[0].latched_initial_stop == 8.00


def test_vsts_two_fires_separated_by_a_fill_are_two_latches():
    """RD constraint 3: the run-99 latch FILLED (trade 17, 2026-06-25) and
    cleared; the run-126 fire therefore opens a genuinely NEW latch."""
    from swing.latches.models import EntryRecord
    fires = [
        _fire(8851, 99, "VSTS", 13.56, 11.62, "2026-06-25", "2026-06-24T20:06:25", 112),
        _fire(9999, 126, "VSTS", 16.90, 13.40, "2026-07-27", "2026-07-24T17:30:06", 140),
    ]
    entries = {"VSTS": [EntryRecord(
        trade_id=17, ticker="VSTS", entry_date=date(2026, 6, 25),
        candidate_id=8851, entry_price=13.61, shares=15)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"VSTS": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert len(d.latches) == 2
    first, second = d.latches
    assert (first.identity.evaluation_run_id, first.state) == (99, "filled")
    assert first.clear_reason == "fill" and first.clear_trade_id == 17
    assert (second.identity.evaluation_run_id, second.state) == (126, "armed")
    assert second.latched_pivot == 16.90 and second.latched_initial_stop == 13.40
    assert second.reconfirmation_candidate_ids == ()


def test_null_pivot_aplus_row_degrades_and_opens_no_latch():
    """A6: NOT write-prevented -- migration 0001 has no NOT NULL on pivot and
    SQLite stores float('nan') as NULL, so an aplus row CAN carry a NULL pivot."""
    d = derive_latches(
        fires=[_fire(301, 50, "BAD", None, 5.0, "2026-05-01", "2026-04-30T21:00:00")],
        bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 5, 1), derivation_session=date(2026, 5, 1))
    assert d.latches == ()
    assert len(d.degraded) == 1
    assert d.degraded[0].reason == "pivot_missing"
    assert d.degraded[0].candidate_id == 301


def test_a_degraded_fire_does_not_disturb_a_live_latch():
    fires = [
        _fire(401, 60, "MIX", 10.0, 8.0, "2026-05-01", "2026-04-30T21:00:00"),
        _fire(402, 61, "MIX", float("nan"), 8.0, "2026-05-04", "2026-05-01T21:00:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"MIX": []}, entries_by_ticker={},
        horizon_session=date(2026, 5, 5), derivation_session=date(2026, 5, 4))
    assert len(d.latches) == 1 and d.latches[0].latched_pivot == 10.0
    assert d.latches[0].reconfirmation_candidate_ids == ()
    assert [x.reason for x in d.degraded] == ["pivot_missing"]


def test_stop_not_below_pivot_degrades():
    d = derive_latches(
        fires=[_fire(501, 70, "FLAT", 10.0, 10.0, "2026-05-01", "2026-04-30T21:00:00")],
        bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 5, 1), derivation_session=date(2026, 5, 1))
    assert d.latches == () and d.degraded[0].reason == "stop_not_below_pivot"


def test_bad_action_session_date_degrades_instead_of_raising():
    d = derive_latches(
        fires=[_fire(601, 80, "BADD", 10.0, 8.0, "2026-5-01", "2026-04-30T21:00:00")],
        bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 5, 1), derivation_session=date(2026, 5, 1))
    assert d.latches == () and d.degraded[0].reason == "bad_session_date"


def test_zone_cap_is_pivot_times_one_point_oh_three():
    d = derive_latches(
        fires=[_fire(701, 121, "FTRE", 18.34, 14.88, "2026-07-20", "2026-07-17T17:30:05", 135)],
        bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].zone_cap == round(18.34 * 1.03, 4)


# --- Codex R1-1: the SAME-SESSION clause -----------------------------------
def test_a_same_session_refire_after_a_fill_does_not_open_a_second_latch():
    """A.2 clause (i). Without it, the fill clears the latch AS OF session S,
    the second same-session evaluation run then sees 'not live' and opens a
    DUPLICATE latch that is `armed` for a position the operator already holds
    -- firing a false LATCH_ARMED_NO_RESTING_ORDER. A still-live-only
    implementation FAILS this test with len(latches) == 2."""
    from swing.latches.models import EntryRecord
    fires = [
        _fire(801, 40, "SAME", 10.0, 8.0, "2026-05-04", "2026-05-01T21:00:00"),
        _fire(802, 41, "SAME", 10.0, 8.0, "2026-05-04", "2026-05-04T11:00:00"),
    ]
    entries = {"SAME": [EntryRecord(
        trade_id=55, ticker="SAME", entry_date=date(2026, 5, 4),
        candidate_id=801, entry_price=10.05, shares=5)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"SAME": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 5, 5), derivation_session=date(2026, 5, 4))
    assert len(d.latches) == 1
    assert d.latches[0].identity.candidate_id == 801
    assert d.latches[0].reconfirmation_candidate_ids == (802,)
    assert d.latches[0].state == "filled"


def test_a_same_session_refire_after_an_invalidating_close_also_collapses():
    fires = [
        _fire(811, 40, "SAME", 10.0, 8.0, "2026-05-04", "2026-05-01T21:00:00"),
        _fire(812, 41, "SAME", 10.0, 8.0, "2026-05-04", "2026-05-04T11:00:00"),
    ]
    bars = [DailyBar(session=date(2026, 5, 4), open=9.0, high=9.2,
                     low=7.5, close=7.90)]
    d = derive_latches(
        fires=fires, bars_by_ticker={"SAME": bars}, entries_by_ticker={},
        horizon_session=date(2026, 5, 5), derivation_session=date(2026, 5, 4))
    assert len(d.latches) == 1
    assert d.latches[0].state == "invalidated"


def test_a_NEXT_session_refire_after_a_fill_DOES_open_a_second_latch():
    """The discriminator in the other direction: clause (i) must not swallow a
    genuinely new session's fire. A blanket 'same ticker never re-opens' rule
    FAILS this test."""
    from swing.latches.models import EntryRecord
    fires = [
        _fire(821, 40, "NEXT", 10.0, 8.0, "2026-05-04", "2026-05-01T21:00:00"),
        _fire(822, 42, "NEXT", 11.0, 9.0, "2026-05-05", "2026-05-04T17:30:00"),
    ]
    entries = {"NEXT": [EntryRecord(
        trade_id=56, ticker="NEXT", entry_date=date(2026, 5, 4),
        candidate_id=821, entry_price=10.05, shares=5)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"NEXT": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 5, 6), derivation_session=date(2026, 5, 5))
    assert len(d.latches) == 2
    assert d.latches[0].state == "filled"
    assert d.latches[1].latched_pivot == 11.0     # the NEW fire's own price
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/evaluation/test_session_offset.py tests/latches/test_service_fire_grouping.py -q`
Expected: FAIL — `ImportError: cannot import name 'session_offset'` / `No module named 'swing.latches.service'`.

- [ ] **Step 3: Add `session_offset` to `swing/evaluation/dates.py`**

Append (no existing function is touched — the ratified 18-E additive-helper precedent):
```python
def session_offset(reference: date, n: int) -> date:
    """Return the NYSE session exactly `n` sessions from `reference`.

    SIGNED: positive walks forward (`next_session`), negative walks backward
    (`previous_session`), `n == 0` returns `reference` unchanged. The
    displacement twin of `sessions_behind`; pure, stdlib `date` in/out, and
    the canonical session-arithmetic home owns `_NYSE`. NO calendar-day
    fallback: a calendar walk false-counts across weekends and holidays (the
    19-E ruling-A precedent).

    Both directions are used: `+LATCH_HORIZON_SESSIONS` computes a latch's
    horizon expiry, and `-1` computes the derivation session (the last
    completed session) from an action-session anchor.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError(f"n must be int (not bool); got {type(n).__name__}")
    cursor = pd.Timestamp(reference)
    step = _NYSE.next_session if n > 0 else _NYSE.previous_session
    for _ in range(abs(n)):
        cursor = step(cursor)
    return cursor.date()
```

- [ ] **Step 4: Write `swing/latches/models.py`**

Frozen dataclasses, all with `__post_init__` validation of the fields the derivation depends on. `Latch` carries: `identity`, `latched_pivot`, `latched_initial_stop`, `zone_cap`, `anchor: date`, `horizon_expiry: date`, `sessions_elapsed: int`, `sessions_to_horizon: int`, `state: str`, `clear_reason: str | None`, `clear_session: date | None`, `clear_trade_id: int | None`, `fill_link_basis: str | None`, `fill_link_anomaly: bool`, `bars_available: bool`, `bars_through: date | None`, `reconfirmation_candidate_ids: tuple[int, ...]`, `reconfirmation_sessions: tuple[str, ...]`. `is_live` is a property: `state in {"armed", "order_resting"}`.

`DegradedFire` carries `candidate_id`, `evaluation_run_id`, `ticker`, `action_session_date`, `reason` (validated against `LATCH_DEGRADED_REASONS`).

`LatchDerivation` carries `latches: tuple[Latch, ...]`, `degraded: tuple[DegradedFire, ...]`, `derivation_session: date`, `horizon_session: date`.

- [ ] **Step 5: Write `swing/latches/service.py`**

```python
def derive_latches(*, fires, bars_by_ticker, entries_by_ticker,
                   horizon_session, derivation_session,
                   horizon_sessions=LATCH_HORIZON_SESSIONS) -> LatchDerivation:
    """PURE. No DB, no network, no transactions (the classifier convention).

    `horizon_session`   -- the FORWARD anchor (action_session_for_run): answers
                           "is the mandate live for the session I am about to
                           trade".
    `derivation_session`-- the BACKWARD anchor (last_completed_session): the
                           newest session whose CLOSE can be evaluated.
    Two anchors because a close can only be judged on a completed bar while a
    mandate is judged for the upcoming session (the session-anchor gotcha).
    """
```

Body outline (each bullet is a small helper so it stays readable):
1. Bucket `fires` by ticker; sort each bucket by `(action_session_date, run_ts, candidate_id)`.
2. `_validate_fire(fire)` → `None` or a `DegradedFire`: `parse_session_date` on `action_session_date`; pivot/stop must be `float`, `math.isfinite`, `> 0`; `initial_stop < pivot`.
3. Per ticker, fold: keep `open_latch`. For each valid fire —
   - if `open_latch is not None` and `_terminal_as_of(open_latch, fire.anchor) is None` → append `fire.candidate_id` to the open latch's re-confirmation tuple; continue.
   - else finalize the previous `open_latch` (already terminal) and open a new one from this fire.
4. `_terminal_as_of(latch, up_to: date) -> tuple[str, date, int | None, str | None] | None`: walk the ticker's bars ascending, skipping bars with `session < anchor`, stopping after `session > up_to`; per session apply FILL → INVALIDATION → HORIZON. After the walk, if uncleared and `sessions_behind(up_to, anchor) >= horizon_sessions`, return `("horizon", horizon_expiry, None, None)`.
5. Fill match per §A.6 (`_match_fill(latch, entries)`), returning the basis and setting `fill_link_anomaly` for a `candidate_id` match dated before the anchor.
6. Finalize each latch: resolve terminal with `up_to=derivation_session` for fill/invalidation; compute `sessions_elapsed = sessions_behind(horizon_session, anchor)` and `sessions_to_horizon`; map to `state` (`filled`/`invalidated`/`horizon_expired`, else `armed` — `order_resting` is assigned later by the order layer); set `bars_available` / `bars_through`.

Guard for horizon vs bars: the horizon check uses `horizon_session`, so a latch expires on schedule even with an empty archive.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/evaluation/test_session_offset.py tests/latches/test_service_fire_grouping.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add swing/evaluation/dates.py swing/latches/models.py swing/latches/service.py tests/evaluation/test_session_offset.py tests/latches/test_service_fire_grouping.py
git commit -m "feat(latches): Task 2 - session_offset + the open-latch fire rule

A bucket='aplus' row opens a latch only when no latch on that ticker is still
live; otherwise it re-confirms without re-freezing. SLDB runs 9/10/12 pin one
latch, not three, and a drifted re-fire pins the frozen pivot."
```

---

### Task 3: The terminal state machine — invalidation on closes, horizon in sessions, latch-specific fills

**Files:**
- Modify: `swing/latches/service.py` (the `_terminal_as_of` / `_match_fill` internals from Task 2 gain full coverage; no signature change)
- Test: `tests/latches/test_service_terminal.py`

**Interfaces:**
- Consumes: `derive_latches` (Task 2) — signature unchanged.
- Produces: no new public names; this task pins the semantics.

- [ ] **Step 1: Write the failing tests**

`tests/latches/test_service_terminal.py`:
```python
"""Terminal-state semantics: RD constraints 1, 2, 4, 5, 6."""
from __future__ import annotations

from datetime import date

from swing.latches.models import DailyBar, EntryRecord, FireRow
from swing.latches.service import derive_latches


def _bar(d, o, h, low, c):
    return DailyBar(session=date.fromisoformat(d), open=o, high=h, low=low, close=c)


FTRE_FIRE = FireRow(
    candidate_id=9500, evaluation_run_id=121, ticker="FTRE", pivot=18.34,
    initial_stop=14.88, action_session_date="2026-07-20",
    run_ts="2026-07-17T17:30:05", pipeline_run_id=135)

# The REAL drifted later rows (runs 122-125, all bucket='watch'). They are NOT
# fires, so they are not in `fires` at all -- but the reader's SQL is what keeps
# them out, and this fixture documents the values a latest-row read would show.
FTRE_DRIFTED_STOPS = (15.195, 15.25, 16.515, 16.515)


def test_ftre_freezes_the_fire_time_stop_not_the_drifted_one():
    """RD constraint 1. A latest-row derivation renders 16.51 -- the value RD
    himself quoted, ~11% early. Only the fire's own row gives 14.88."""
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.latched_initial_stop == 14.88
    assert latch.latched_pivot == 18.34
    assert latch.latched_initial_stop not in FTRE_DRIFTED_STOPS


def test_intraday_touch_below_the_stop_that_closes_above_does_not_invalidate():
    """RD constraint 6 -- CLOSES, not intraday touches."""
    bars = [_bar("2026-07-21", 15.0, 15.2, 14.10, 15.05)]   # low 14.10 < 14.88
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].state == "armed"
    assert d.latches[0].clear_reason is None


def test_a_close_below_the_frozen_stop_invalidates_and_stamps_the_session():
    bars = [_bar("2026-07-21", 15.0, 15.2, 14.10, 14.87)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    latch = d.latches[0]
    assert latch.state == "invalidated"
    assert latch.clear_reason == "invalidation"
    assert latch.clear_session == date(2026, 7, 21)


def test_a_close_exactly_at_the_stop_does_not_invalidate():
    bars = [_bar("2026-07-21", 15.0, 15.2, 14.10, 14.88)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].state == "armed"


def test_a_close_below_the_DRIFTED_stop_but_above_the_frozen_one_does_not_invalidate():
    """The combined constraint-1 x constraint-6 discriminator: 16.00 is below
    the drifted 16.515 and above the frozen 14.88. Only a frozen-stop
    implementation stays armed."""
    bars = [_bar("2026-07-23", 16.5, 16.8, 15.9, 16.00)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 24), derivation_session=date(2026, 7, 23))
    assert d.latches[0].state == "armed"


# --- Horizon: sessions, NOT calendar days (the AMN discriminator) -----------
AMN_FIRE = FireRow(
    candidate_id=9276, evaluation_run_id=103, ticker="AMN", pivot=33.48,
    initial_stop=28.81, action_session_date="2026-07-01",
    run_ts="2026-07-01T06:30:23", pipeline_run_id=116)


def test_amn_is_still_armed_15_sessions_out_where_a_calendar_horizon_would_expire():
    """AMN's real fire geometry with the fill withheld. On 2026-07-23:
      sessions elapsed = 15  -> ARMED under a 20-SESSION horizon
      calendar days    = 22  -> EXPIRED under a 20-CALENDAR-DAY horizon
    A calendar-day implementation FAILS this test."""
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 23), derivation_session=date(2026, 7, 23))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.sessions_elapsed == 15
    assert latch.sessions_to_horizon == 5
    assert latch.horizon_expiry == date(2026, 7, 30)


def test_horizon_expires_inclusively_on_the_20th_session():
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 30), derivation_session=date(2026, 7, 30))
    latch = d.latches[0]
    assert latch.state == "horizon_expired"
    assert latch.clear_reason == "horizon"
    assert latch.clear_session == date(2026, 7, 30)
    assert latch.sessions_to_horizon == 0


def test_still_armed_on_the_19th_session():
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 29), derivation_session=date(2026, 7, 29))
    assert d.latches[0].state == "armed"
    assert d.latches[0].sessions_elapsed == 19


def test_ftre_horizon_expiry_matches_rds_recorded_2026_08_17():
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].horizon_expiry == date(2026, 8, 17)
    assert d.latches[0].sessions_elapsed == 5


# --- Fill detection: LATCH-SPECIFIC (RD constraint 4) -----------------------
VSTS_126 = FireRow(
    candidate_id=9999, evaluation_run_id=126, ticker="VSTS", pivot=16.90,
    initial_stop=13.40, action_session_date="2026-07-27",
    run_ts="2026-07-24T17:30:06", pipeline_run_id=140)
TRADE_17 = EntryRecord(trade_id=17, ticker="VSTS", entry_date=date(2026, 6, 25),
                       candidate_id=8851, entry_price=13.61, shares=15)


def test_the_old_closed_vsts_position_does_not_fill_the_new_latch():
    """RD's named live subject. Trade 17 carries candidate_id 8851 (the run-99
    fire); the run-126 latch's candidate set is {9999}."""
    d = derive_latches(
        fires=[VSTS_126], bars_by_ticker={"VSTS": []},
        entries_by_ticker={"VSTS": [TRADE_17]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.clear_reason is None and latch.clear_trade_id is None


def test_a_null_candidate_id_entry_before_the_anchor_also_does_not_match():
    """The windowed fallback must not reach backwards past the anchor."""
    legacy = EntryRecord(trade_id=4, ticker="VSTS", entry_date=date(2026, 6, 25),
                         candidate_id=None, entry_price=13.61, shares=15)
    d = derive_latches(
        fires=[VSTS_126], bars_by_ticker={"VSTS": []},
        entries_by_ticker={"VSTS": [legacy]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].state == "armed"


def test_exact_candidate_id_link_fills_its_own_latch():
    fire99 = FireRow(candidate_id=8851, evaluation_run_id=99, ticker="VSTS",
                     pivot=13.56, initial_stop=11.62,
                     action_session_date="2026-06-25",
                     run_ts="2026-06-24T20:06:25", pipeline_run_id=112)
    d = derive_latches(
        fires=[fire99], bars_by_ticker={"VSTS": []},
        entries_by_ticker={"VSTS": [TRADE_17]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "filled"
    assert latch.clear_reason == "fill"
    assert latch.clear_trade_id == 17
    assert latch.clear_session == date(2026, 6, 25)
    assert latch.fill_link_basis == "candidate_id"


def test_windowed_fallback_fills_when_candidate_id_is_null():
    legacy = EntryRecord(trade_id=4, ticker="FTRE", entry_date=date(2026, 7, 22),
                         candidate_id=None, entry_price=18.40, shares=3)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [legacy]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].state == "filled"
    assert d.latches[0].fill_link_basis == "windowed"


def test_candidate_id_match_dated_before_the_anchor_flags_an_anomaly_not_a_fill():
    weird = EntryRecord(trade_id=77, ticker="FTRE", entry_date=date(2026, 7, 10),
                        candidate_id=9500, entry_price=18.0, shares=1)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [weird]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.clear_reason is None
    assert latch.fill_link_anomaly is True


def test_fill_beats_invalidation_on_the_same_session():
    """Precedence (plan A.7): a consummated mandate is terminal in the
    strongest sense; the bar's close below the stop becomes the TRADE's
    problem, not the latch's."""
    entry = EntryRecord(trade_id=88, ticker="FTRE", entry_date=date(2026, 7, 21),
                        candidate_id=9500, entry_price=18.40, shares=3)
    bars = [_bar("2026-07-21", 18.4, 18.6, 14.0, 14.10)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars},
        entries_by_ticker={"FTRE": [entry]},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].clear_reason == "fill"


def test_invalidation_beats_horizon_on_the_same_session():
    bars = [_bar("2026-07-30", 29.0, 29.5, 28.0, 28.00)]
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 30), derivation_session=date(2026, 7, 30))
    assert d.latches[0].clear_reason == "invalidation"


def test_absent_bars_leave_invalidation_unevaluated_and_say_so():
    """A6: never a silent 'not invalidated'."""
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.bars_available is False
    assert latch.bars_through is None


def test_bars_through_reports_archive_staleness():
    bars = [_bar("2026-07-21", 17.9, 18.3, 17.6, 17.91)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].bars_available is True
    assert d.latches[0].bars_through == date(2026, 7, 21)


# --- Codex R1-3: overlapping windows ---------------------------------------
def _ovl_fires():
    """Latch 1 fires 2026-06-25 and INVALIDATES 2026-06-30, but its NOMINAL
    horizon_expiry is 2026-07-24 -- so its nominal window overlaps latch 2's
    (fires 2026-07-01, expiry 2026-07-30)."""
    return [
        FireRow(candidate_id=7001, evaluation_run_id=99, ticker="OVL",
                pivot=13.56, initial_stop=11.62,
                action_session_date="2026-06-25",
                run_ts="2026-06-24T20:06:25", pipeline_run_id=112),
        FireRow(candidate_id=7002, evaluation_run_id=103, ticker="OVL",
                pivot=16.90, initial_stop=13.40,
                action_session_date="2026-07-01",
                run_ts="2026-07-01T06:30:23", pipeline_run_id=116),
    ]


_OVL_BARS = [_bar("2026-06-30", 12.0, 12.2, 11.0, 11.50)]   # closes below 11.62


def test_a_legacy_entry_after_latch1_invalidated_belongs_to_latch2_only():
    """The windowed window is bounded by the ACTUAL non-fill terminal
    (2026-06-30), not the nominal horizon (2026-07-24). A nominal-horizon
    implementation credits the 2026-07-05 entry to latch 1 as well."""
    legacy = EntryRecord(trade_id=90, ticker="OVL", entry_date=date(2026, 7, 5),
                         candidate_id=None, entry_price=17.0, shares=4)
    d = derive_latches(
        fires=_ovl_fires(), bars_by_ticker={"OVL": _OVL_BARS},
        entries_by_ticker={"OVL": [legacy]},
        horizon_session=date(2026, 7, 10), derivation_session=date(2026, 7, 10))
    first, second = d.latches
    assert first.state == "invalidated" and first.clear_trade_id is None
    assert second.state == "filled" and second.clear_trade_id == 90
    assert second.fill_link_basis == "windowed"


def test_one_trade_can_fill_at_most_one_latch():
    """Rule (b): the consumed-trade_ids set. An entry inside BOTH latches'
    bounds goes to the EARLIEST-anchor latch and is not re-used."""
    legacy = EntryRecord(trade_id=91, ticker="OVL", entry_date=date(2026, 7, 2),
                         candidate_id=None, entry_price=17.0, shares=4)
    fires = _ovl_fires()
    d = derive_latches(
        fires=fires, bars_by_ticker={"OVL": []},   # NO bars -> no invalidation
        entries_by_ticker={"OVL": [legacy]},
        horizon_session=date(2026, 7, 10), derivation_session=date(2026, 7, 10))
    filled = [x for x in d.latches if x.clear_trade_id == 91]
    assert len(filled) == 1
    assert filled[0].identity.candidate_id == 7001      # earliest anchor wins


def test_an_explicit_candidate_id_beats_a_windowed_claim_on_the_same_trade():
    """Rule (b) precedence: the EXACT rung consumes first."""
    exact = EntryRecord(trade_id=92, ticker="OVL", entry_date=date(2026, 7, 2),
                        candidate_id=7002, entry_price=17.0, shares=4)
    d = derive_latches(
        fires=_ovl_fires(), bars_by_ticker={"OVL": []},
        entries_by_ticker={"OVL": [exact]},
        horizon_session=date(2026, 7, 10), derivation_session=date(2026, 7, 10))
    first, second = d.latches
    assert first.clear_trade_id is None
    assert second.clear_trade_id == 92
    assert second.fill_link_basis == "candidate_id"


# --- Codex R3-3: BAR-WALK BOUNDARIES ---------------------------------------
# The walk's eligible set is EXACTLY {bar : anchor <= bar.session <=
# derivation_session}. Each boundary gets its own discriminating test, because
# an off-by-one at either end passes every interior-case test above.

def test_the_ANCHOR_SESSION_bar_is_INCLUDED():
    """FTRE's anchor is 2026-07-20. A close below 14.88 ON 07-20 itself must
    invalidate. A walk that starts at anchor+1 leaves the latch `armed` and
    FAILS here."""
    bars = [_bar("2026-07-20", 15.0, 15.2, 14.0, 14.50)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 21), derivation_session=date(2026, 7, 20))
    assert d.latches[0].state == "invalidated"
    assert d.latches[0].clear_session == date(2026, 7, 20)


def test_a_bar_BEFORE_the_anchor_is_EXCLUDED():
    """FTRE's pivot/stop were computed FROM pre-anchor bars; a pre-anchor close
    below the stop is history, not an invalidation of a mandate that did not
    exist yet. A walk that forgets the lower bound FAILS here."""
    bars = [_bar("2026-07-17", 15.0, 15.2, 14.0, 14.00),      # BEFORE the anchor
            _bar("2026-07-20", 17.6, 17.9, 17.4, 17.76)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 21), derivation_session=date(2026, 7, 20))
    assert d.latches[0].state == "armed"


def test_a_bar_AFTER_derivation_session_is_EXCLUDED_even_when_present():
    """The archive can legitimately hold a bar newer than derivation_session
    (the warm runs at 17:30 for the NEXT session). Judging a latch on a bar the
    operator's session boundary has not reached is a look-ahead. An
    implementation that walks the whole archive FAILS here."""
    bars = [_bar("2026-07-21", 17.9, 18.3, 17.6, 17.91),
            _bar("2026-07-22", 17.7, 18.6, 14.0, 14.00)]     # AFTER the bound
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].state == "armed"
    assert d.latches[0].bars_through == date(2026, 7, 21)


def test_the_same_bar_set_one_session_later_DOES_invalidate():
    """The paired discriminator for the test above -- proves the 07-22 bar is
    excluded by the BOUND, not silently dropped by the reader."""
    bars = [_bar("2026-07-21", 17.9, 18.3, 17.6, 17.91),
            _bar("2026-07-22", 17.7, 18.6, 14.0, 14.00)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 23), derivation_session=date(2026, 7, 22))
    assert d.latches[0].state == "invalidated"
    assert d.latches[0].clear_session == date(2026, 7, 22)


def test_an_invalidating_close_ON_the_horizon_expiry_session_beats_horizon():
    """AMN's expiry is 2026-07-30. A close below 28.81 on 07-30 must record
    `invalidation` (the more informative terminal), not `horizon`. An
    implementation that checks the horizon before walking the bars FAILS."""
    bars = [_bar("2026-07-30", 29.0, 29.5, 27.5, 28.00)]
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 30), derivation_session=date(2026, 7, 30))
    assert d.latches[0].clear_reason == "invalidation"
    assert d.latches[0].clear_session == date(2026, 7, 30)


def test_the_horizon_anchors_on_action_session_not_data_asof():
    """RD's recorded FTRE horizon is 2026-08-17 == action_session (2026-07-20)
    + 20 sessions. Anchoring on data_asof_date (2026-07-17) gives 2026-08-14
    and FAILS -- and would expire the mandate three sessions early."""
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 14), derivation_session=date(2026, 8, 13))
    assert d.latches[0].state == "armed"          # NOT expired on 08-14
    assert d.latches[0].horizon_expiry == date(2026, 8, 17)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/latches/test_service_terminal.py -q`
Expected: FAIL on the assertions whose semantics Task 2's outline left thin (fill precedence, anomaly flag, `bars_through`, inclusive horizon).

- [ ] **Step 3: Complete the state machine in `swing/latches/service.py`**

Implement `_terminal_as_of` and `_match_fill` exactly per §A.5-A.7, plus `bars_available` / `bars_through` (max bar session `<= derivation_session`, `None` when no bars at or after the anchor).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/latches -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/latches/service.py tests/latches/test_service_terminal.py
git commit -m "test(latches): Task 3 - terminal semantics for RD constraints 1,2,4,5,6

Invalidation on closes with the frozen stop, sessions-not-calendar horizon
with inclusive expiry, latch-specific fill linkage that refuses the old
closed VSTS position, and a recorded clear reason per terminal state."
```

---

### Task 4: Order join + the two alarms (pure) + the `stop_price` mapper extension

**Files:**
- Modify: `swing/integrations/schwab/models.py` (tail-append `stop_price`), `swing/integrations/schwab/mappers.py`
- Create: `swing/latches/orders.py`
- Test: `tests/latches/test_orders.py`, `tests/integrations/test_order_mapper_stop_price.py`

**Interfaces:**
- Consumes: `swing.latches.models.Latch` (Task 2/3).
- Produces:
  - `swing.integrations.schwab.models.SchwabOrderResponse.stop_price: float | None = None`
  - `swing.latches.models.RestingOrder(order_id, ticker, instruction, quantity, order_type, limit_price, stop_price, status)`
  - `swing.latches.models.LatchOrderJoin(latch_candidate_id, orders, order_stop_agrees, order_limit_agrees, indeterminate)`
  - `swing.latches.models.OrderAlarm(kind, ticker, latch_candidate_id, detail, severity)`
  - `swing.latches.orders.join_orders_to_latches(*, latches, orders) -> tuple[dict[int, LatchOrderJoin], tuple[OrderAlarm, ...]]`
  - `swing.latches.orders.to_resting_orders(schwab_orders) -> tuple[RestingOrder, ...]`

- [ ] **Step 1: Write the failing tests**

`tests/integrations/test_order_mapper_stop_price.py`:
```python
"""stop_price is ADDITIVE: `price` semantics are unchanged."""
from __future__ import annotations

from swing.integrations.schwab.mappers import map_orders_to_fill_candidates


def _order(**over):
    base = {
        "orderId": 1, "status": "WORKING", "enteredTime": "2026-07-20T13:30:00Z",
        "orderType": "STOP_LIMIT", "price": 18.89, "stopPrice": 18.34,
        "orderLegCollection": [{
            "instruction": "BUY", "quantity": 3,
            "instrument": {"symbol": "FTRE"}}],
    }
    base.update(over)
    return base


def test_stop_limit_carries_both_prices():
    (o,) = map_orders_to_fill_candidates([_order()])
    assert o.price == 18.89       # the LIMIT -- unchanged behavior
    assert o.stop_price == 18.34  # NEW


def test_plain_stop_order_price_still_falls_back_to_stop_price():
    """REGRESSION: reconciliation depends on `price` falling back to stopPrice
    when `price` is absent. That must not change."""
    (o,) = map_orders_to_fill_candidates(
        [_order(orderType="STOP", price=None)])
    assert o.price == 18.34
    assert o.stop_price == 18.34


def test_limit_order_has_no_stop_price():
    (o,) = map_orders_to_fill_candidates(
        [_order(orderType="LIMIT", stopPrice=None)])
    assert o.price == 18.89
    assert o.stop_price is None


def test_default_is_none_for_positional_construction():
    """Tail placement preserves the 8-positional backward compat the
    `executions` field established."""
    from swing.integrations.schwab.models import SchwabOrderResponse
    o = SchwabOrderResponse("1", "WORKING", "", "FTRE", "BUY", 3.0, "STOP", 18.34)
    assert o.stop_price is None
```

`tests/latches/test_orders.py`:
```python
"""The two alarms (plan A.9)."""
from __future__ import annotations

from datetime import date

from swing.latches.models import FireRow, RestingOrder
from swing.latches.orders import join_orders_to_latches
from swing.latches.service import derive_latches

FTRE_FIRE = FireRow(
    candidate_id=9500, evaluation_run_id=121, ticker="FTRE", pivot=18.34,
    initial_stop=14.88, action_session_date="2026-07-20",
    run_ts="2026-07-17T17:30:05", pipeline_run_id=135)


def _armed():
    return derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27),
        derivation_session=date(2026, 7, 24)).latches


def _order(**over):
    base = dict(order_id="1", ticker="FTRE", instruction="BUY", quantity=3.0,
                order_type="STOP_LIMIT", limit_price=18.89, stop_price=18.34,
                status="WORKING")
    base.update(over)
    return RestingOrder(**base)


def test_armed_with_no_resting_order_fires_the_ftre_alarm():
    joins, alarms = join_orders_to_latches(latches=_armed(), orders=())
    assert [a.kind for a in alarms] == ["LATCH_ARMED_NO_RESTING_ORDER"]
    assert alarms[0].ticker == "FTRE"
    assert alarms[0].latch_candidate_id == 9500


def test_a_matching_resting_order_promotes_the_state_and_silences_the_alarm():
    joins, alarms = join_orders_to_latches(latches=_armed(), orders=(_order(),))
    assert alarms == ()
    j = joins[9500]
    assert j.order_stop_agrees is True
    assert j.order_limit_agrees is True


def test_a_sell_order_never_satisfies_an_entry_latch():
    joins, alarms = join_orders_to_latches(
        latches=_armed(), orders=(_order(instruction="SELL"),))
    assert [a.kind for a in alarms] == ["LATCH_ARMED_NO_RESTING_ORDER"]


def test_a_filled_or_canceled_order_is_not_resting():
    for status in ("FILLED", "CANCELED", "REJECTED", "EXPIRED", "REPLACED"):
        _, alarms = join_orders_to_latches(
            latches=_armed(), orders=(_order(status=status),))
        assert [a.kind for a in alarms] == ["LATCH_ARMED_NO_RESTING_ORDER"], status


def test_an_indeterminate_order_suppresses_both_alarms():
    joins, alarms = join_orders_to_latches(
        latches=_armed(), orders=(_order(status="PENDING_CANCEL"),))
    assert alarms == ()
    assert joins[9500].indeterminate is True


def test_disagreeing_prices_are_reported_without_silencing_the_join():
    joins, _ = join_orders_to_latches(
        latches=_armed(), orders=(_order(stop_price=18.59, limit_price=19.15),))
    j = joins[9500]
    assert j.order_stop_agrees is False
    assert j.order_limit_agrees is False


def test_price_comparison_uses_display_precision():
    """18.340001 must not read as 'operator edited' (the precision-parity
    gotcha)."""
    joins, _ = join_orders_to_latches(
        latches=_armed(), orders=(_order(stop_price=18.340001),))
    assert joins[9500].order_stop_agrees is True


def test_unknown_side_of_a_comparison_is_None_not_False():
    joins, _ = join_orders_to_latches(
        latches=_armed(), orders=(_order(stop_price=None),))
    assert joins[9500].order_stop_agrees is None


def test_order_resting_on_a_cleared_latch_fires_the_stale_order_alarm():
    from swing.latches.models import DailyBar
    bars = [DailyBar(session=date(2026, 7, 21), open=15.0, high=15.2,
                     low=14.1, close=14.0)]
    cleared = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22),
        derivation_session=date(2026, 7, 21)).latches
    _, alarms = join_orders_to_latches(latches=cleared, orders=(_order(),))
    assert [a.kind for a in alarms] == ["ORDER_RESTING_LATCH_CLEARED"]
    assert alarms[0].severity == "critical"    # cleared by INVALIDATION
    assert "invalidation" in alarms[0].detail


def test_order_resting_with_no_latch_at_all_also_fires_the_stale_alarm():
    _, alarms = join_orders_to_latches(
        latches=(), orders=(_order(ticker="ZZZZ"),))
    assert [a.kind for a in alarms] == ["ORDER_RESTING_LATCH_CLEARED"]
    assert alarms[0].latch_candidate_id is None


def test_horizon_cleared_latch_with_a_resting_order_is_warning_not_critical():
    from swing.latches.models import FireRow as FR
    old = FR(candidate_id=9276, evaluation_run_id=103, ticker="FTRE", pivot=18.34,
             initial_stop=15.00, action_session_date="2026-07-01",
             run_ts="2026-07-01T06:30:23", pipeline_run_id=116)
    expired = derive_latches(
        fires=[old], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 30),
        derivation_session=date(2026, 7, 30)).latches
    _, alarms = join_orders_to_latches(latches=expired, orders=(_order(),))
    assert alarms[0].kind == "ORDER_RESTING_LATCH_CLEARED"
    assert alarms[0].severity == "warning"


# --- Codex R1-2: PER-ORDER attribution, not per-ticker liveness ------------
def _two_latches_one_cleared_one_live():
    """The live VSTS geometry: an earlier latch INVALIDATED (its GTC order is
    still resting at the OLD pivot 13.56) while a newer latch is LIVE at 16.90."""
    from swing.latches.models import DailyBar
    fires = [
        FireRow(candidate_id=8851, evaluation_run_id=99, ticker="VSTS",
                pivot=13.56, initial_stop=11.62,
                action_session_date="2026-06-25",
                run_ts="2026-06-24T20:06:25", pipeline_run_id=112),
        FireRow(candidate_id=9999, evaluation_run_id=126, ticker="VSTS",
                pivot=16.90, initial_stop=13.40,
                action_session_date="2026-07-27",
                run_ts="2026-07-24T17:30:06", pipeline_run_id=140),
    ]
    bars = [DailyBar(session=date(2026, 6, 30), open=12.0, high=12.2,
                     low=11.0, close=11.50)]      # closes below 11.62
    return derive_latches(
        fires=fires, bars_by_ticker={"VSTS": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27),
        derivation_session=date(2026, 7, 27)).latches


def test_a_stale_order_alarms_even_though_a_newer_latch_is_live_on_that_ticker():
    """THE R1-2 discriminator. A ticker-level rule ('alarm only when the ticker
    has no live latch') stays SILENT here -- and the operator never learns his
    invalidation-cancel duty is outstanding."""
    latches = _two_latches_one_cleared_one_live()
    stale = _order(ticker="VSTS", stop_price=13.56, limit_price=13.97)
    _, alarms = join_orders_to_latches(latches=latches, orders=(stale,))
    kinds = [a.kind for a in alarms]
    assert "ORDER_RESTING_LATCH_CLEARED" in kinds
    stale_alarm = next(a for a in alarms if a.kind == "ORDER_RESTING_LATCH_CLEARED")
    assert stale_alarm.latch_candidate_id == 8851      # the CLEARED latch
    assert stale_alarm.severity == "critical"          # cleared by invalidation


def test_an_order_matching_the_LIVE_latch_does_not_fire_the_stale_alarm():
    latches = _two_latches_one_cleared_one_live()
    good = _order(ticker="VSTS", stop_price=16.90, limit_price=17.41)
    _, alarms = join_orders_to_latches(latches=latches, orders=(good,))
    assert [a.kind for a in alarms] == []


def test_a_mispriced_order_on_a_live_latch_reports_disagreement_not_a_false_no_order_alarm():
    """An order at neither latch's price must NOT produce a factually false
    LATCH_ARMED_NO_RESTING_ORDER."""
    latches = _two_latches_one_cleared_one_live()
    odd = _order(ticker="VSTS", stop_price=15.00, limit_price=15.45)
    joins, alarms = join_orders_to_latches(latches=latches, orders=(odd,))
    assert "LATCH_ARMED_NO_RESTING_ORDER" not in [a.kind for a in alarms]
    assert joins[9999].order_stop_agrees is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/latches/test_orders.py tests/integrations/test_order_mapper_stop_price.py -q`
Expected: FAIL — `AttributeError: 'SchwabOrderResponse' object has no attribute 'stop_price'` / `No module named 'swing.latches.orders'`.

- [ ] **Step 3: Extend `SchwabOrderResponse` + the mapper (strictly additive)**

In `swing/integrations/schwab/models.py`, append AFTER `executions` (tail placement preserves positional compat):
```python
    # Phase 21 Arc A: the STOP TRIGGER, kept SEPARATE from `price`.
    # `price` semantics are UNCHANGED (limit when present, else the stop
    # trigger) so every existing reconciliation consumer is untouched; the
    # latch panel needs the stop/limit PAIR for a STOP_LIMIT order, which the
    # collapsed `price` cannot express.
    stop_price: float | None = None
```
plus a `__post_init__` clause mirroring the existing `price` validator (number-or-None, finite, `>= 0`).

In `swing/integrations/schwab/mappers.py`, inside `map_orders_to_fill_candidates`, after the existing `price_raw` block:
```python
        stop_raw = _opt(raw, "stopPrice")
        stop_price: float | None = (
            float(stop_raw) if stop_raw is not None else None
        )
```
and pass `stop_price=stop_price` to the `SchwabOrderResponse(...)` construction. **Do not touch the existing `price_raw` fallback.**

- [ ] **Step 4: Write `swing/latches/orders.py`**

```python
def to_resting_orders(schwab_orders) -> tuple[RestingOrder, ...]:
    """Map SchwabOrderResponse -> RestingOrder, keeping BUY-side orders whose
    status is RESTING or INDETERMINATE. Terminal statuses are dropped."""


def join_orders_to_latches(*, latches, orders):
    """PURE. Returns ({latch_candidate_id: LatchOrderJoin}, alarms)."""
```

Algorithm (**PER-ORDER attribution against latch PRICES** — Codex R1-2; a ticker-level rule silences a stale order the moment a newer latch fires on the same ticker, which is the live VSTS geometry):
1. Index `orders` by ticker; split each ticker's list into `resting` and `indeterminate`.
2. `_match_latch(order, ticker_latches)` → the latch whose FROZEN prices the order matches: `round(order.stop_price, 2) == round(latch.latched_pivot, 2)`, or — when `order.stop_price is None` — `round(order.limit_price, 2) == round(latch.zone_cap, 2)`. Ties break to the most recent `anchor`. Returns `None` when nothing matches or the order carries no usable price.
3. For each latch: build a `LatchOrderJoin` with the resting orders that `_match_latch`ed to IT (plus, for a live latch, any unmatched resting orders on its ticker so a mispriced order is still visible), the `indeterminate` flag, and `order_stop_agrees` / `order_limit_agrees` computed with `round(x, 2)` on BOTH sides (`None` when either side is `None`; `True` if ANY single order agrees on both legs).
4. For each LIVE latch whose ticker has **ZERO** resting BUY orders and no indeterminate order → `LATCH_ARMED_NO_RESTING_ORDER` (severity `critical`). Deliberately ticker-level: a mispriced order must not produce a factually false "no order" alarm — it surfaces through the agreement flags instead.
5. For each resting order whose `_match_latch` is a **CLEARED** latch → `ORDER_RESTING_LATCH_CLEARED` attributed to THAT latch, **even when another latch on the same ticker is LIVE**; severity `critical` when its `clear_reason == "invalidation"` else `warning`; `detail` names the clear reason and session.
6. For each resting order with `_match_latch is None` on a ticker that has **no** live latch → `ORDER_RESTING_LATCH_CLEARED` attributed to the ticker's most recently cleared latch (or `latch_candidate_id=None`). On a ticker that HAS a live latch, no alarm — the order is reported against that latch with `order_stop_agrees=False`.
7. A ticker with any indeterminate BUY order emits NO alarm at all for that ticker.
8. Latch `state` promotion to `order_resting` is applied by the CALLER (the VM) via `dataclasses.replace`, so `service.py` stays free of order concerns.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/latches tests/integrations/test_order_mapper_stop_price.py -q`
Expected: PASS.
Then the reconciliation regression net: `python -m pytest tests/integrations tests/trades -q`
Expected: PASS (proves the mapper change is behavior-neutral for existing consumers).

- [ ] **Step 6: Commit**

```bash
git add swing/integrations/schwab/models.py swing/integrations/schwab/mappers.py swing/latches/orders.py swing/latches/models.py tests/latches/test_orders.py tests/integrations/test_order_mapper_stop_price.py
git commit -m "feat(latches): Task 4 - order join, the two alarms, additive stop_price

SchwabOrderResponse gains a tail-appended optional stop_price so a STOP_LIMIT
order's trigger and limit can both be compared against the latched pivot and
zone cap. The existing price fallback is unchanged and pinned by a regression
test."
```

---

### Task 5: The reader adapter (DB + archive, defensive)

**Files:**
- Create: `swing/latches/reader.py`
- Test: `tests/latches/test_reader.py`

**Interfaces:**
- Consumes: `derive_latches` (Task 2/3), `resolve_ohlcv_window` (`swing/data/ohlcv_archive.py:971`), `session_offset` (Task 2).
- Produces:
  - `swing.latches.reader.load_fire_rows(conn) -> tuple[FireRow, ...]`
  - `swing.latches.reader.load_entry_records(conn, tickers) -> dict[str, list[EntryRecord]]`
  - `swing.latches.reader.load_bars(cfg, ticker, *, start, end) -> list[DailyBar]`
  - `swing.latches.reader.build_latch_derivation(conn, cfg, *, now=None, horizon_session_override: date | None = None) -> LatchDerivation`

- [ ] **Step 1: Write the failing tests**

`tests/latches/test_reader.py` — seeds a real schema DB and asserts:
```python
def test_load_fire_rows_returns_only_aplus_rows_with_both_identities(tmp_path):
    """Runs 121 (aplus) and 122-125 (watch, drifted) all present; only 121 is
    returned, and it carries the pipeline_run_id from the pipeline_runs join."""

def test_load_fire_rows_tolerates_a_missing_pipeline_runs_link(tmp_path):
    """SLDB-era fires have no pipeline_runs row: pipeline_run_id is None, not
    an exception (verified: SELECT COUNT(*) FROM pattern_detection_events
    WHERE ticker='SLDB' == 0)."""

def test_load_entry_records_short_circuits_the_empty_ticker_set(tmp_path):
    """No `IN ()` -- invalid SQL (the dynamic-placeholder gotcha)."""

def test_load_bars_returns_empty_for_an_absent_archive(tmp_path):
    """A6: a missing parquet degrades to [], never raises."""

def test_load_bars_skips_rows_with_a_non_finite_close(tmp_path):
    """A ragged archive row must not be read as an invalidation."""

def test_load_bars_orders_ascending_by_asof_date(tmp_path):

def test_build_latch_derivation_uses_forward_and_backward_anchors(tmp_path, monkeypatch):
    """horizon_session == action_session_for_run(now);
       derivation_session == session_offset(horizon_session, -1)
       == last_completed_session(now)."""

def test_horizon_session_override_rebuilds_the_whole_context_from_the_anchor(tmp_path):
    """Codex R3-1: with an override, `now` must influence NOTHING. Call twice
    with the same override and two wildly different `now` values; both
    LatchDerivations must be equal (same horizon_session, same
    derivation_session, same latch states)."""

def test_build_latch_derivation_never_raises_on_a_malformed_row(tmp_path):
    """A NULL-pivot aplus row planted via RAW conn.execute (bypassing any
    writer) yields a DegradedFire, not an exception."""
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/latches/test_reader.py -q`
Expected: FAIL — `No module named 'swing.latches.reader'`.

- [ ] **Step 3: Write `swing/latches/reader.py`**

```python
_FIRE_SQL = """
    SELECT c.id, c.evaluation_run_id, c.ticker, c.pivot, c.initial_stop,
           e.action_session_date, e.run_ts, p.id
    FROM candidates c
    JOIN evaluation_runs e ON e.id = c.evaluation_run_id
    LEFT JOIN pipeline_runs p ON p.evaluation_run_id = e.id
    WHERE c.bucket = 'aplus'
    ORDER BY c.ticker, e.action_session_date, e.run_ts, c.id
"""
```
Notes baked into the implementation:
- **ALL** A+ fires are loaded (11 rows ever; the display lookback is applied in the VM). Loading a truncated set would break the re-confirmation chain.
- `LEFT JOIN pipeline_runs` — verified 1:1 (`GROUP BY evaluation_run_id HAVING COUNT(*)>1` returns zero rows), and NULL for pre-June fires.
- `load_entry_records` selects `id, ticker, entry_date, candidate_id, entry_price, initial_shares` from `trades` for the given tickers using dynamic `?` expansion, short-circuiting the empty set. `entry_date` is converted with `date.fromisoformat` inside a try/except; a malformed row is SKIPPED with a `log.warning` (it cannot be allowed to clear a latch).
- `load_bars` calls `resolve_ohlcv_window(ticker, start=..., end=..., cache_dir=cfg.paths.prices_cache_dir)`, then builds `DailyBar`s skipping any row whose `close` is not finite (`math.isfinite`) — a ragged archive row must never read as an invalidation. Wrapped in `try/except Exception` → `[]` + `log.warning`. (Note for reviewers: `resolve_ohlcv_window` performs a one-shot legacy `{TICKER}.parquet` → Shape-A rename on first read (`_backward_compat_rename`, `ohlcv_archive.py:1010`). That is pre-existing production read-path behavior shared with the pipeline observe step; it is a cache-file migration, not domain state, and is explicitly NOT the A4 view record.)
- `build_latch_derivation(conn, cfg, *, now=None, horizon_session_override=None)` computes **ONE** anchor and derives the other from it:
  ```python
  horizon_session = horizon_session_override or action_session_for_run(now or datetime.now())
  derivation_session = session_offset(horizon_session, -1)
  ```
  It then loads fires, loads bars per distinct latched ticker over `[min(anchor), derivation_session]`, loads entries, and calls `derive_latches`. **`now` is consulted for NOTHING ELSE** — no bar bound, no state input (Codex R3-1). `horizon_session_override` is what the Task-8 beacon passes so a POST rebuilds the exact render-time context; a GET never passes it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/latches -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/latches/reader.py tests/latches/test_reader.py
git commit -m "feat(latches): Task 5 - the read-only reader adapter

Loads every A+ fire with both identities, reads bars from the on-disk archive
with zero network I/O, and degrades to empty on any missing or malformed
input rather than raising."
```

---

### Task 6: The panel — VM, route, template, nav, CSS, and the two global-invariant manifests

**Files:**
- Create: `swing/web/view_models/latches.py`, `swing/web/routes/latches.py`, `swing/web/templates/latches.html.j2`
- Modify: `swing/web/app.py`, `swing/web/templates/base.html.j2`, `swing/web/static/app.css`, `tests/web/test_base_layout_nav.py`, `tests/web/test_topbar_cross_vm_consistency.py`
- Test: `tests/web/test_view_models/test_latch_panel_vm.py`, `tests/web/test_routes/test_latches_route.py`

**Interfaces:**
- Consumes: `build_latch_derivation` (Task 5), `list_views_for_latch` (Task 1), `_base_banner_fields` (`swing/web/view_models/journal.py:240`).
- Produces:
  - `swing.web.view_models.latches.LatchRowVM`, `DegradedRowVM`, `LatchPanelVM` (the last with `PAGE_KIND = PageKind.FORWARD_PLANNING`)
  - `swing.web.view_models.latches.build_latch_panel_vm(conn, cfg, cache, executor, *, now=None) -> LatchPanelVM`
  - `GET /latches`

> **CRITICAL — two cross-cutting global-invariant tests must be updated IN THIS TASK or the full suite fails:**
> 1. `tests/web/test_topbar_cross_vm_consistency.py::MANIFEST` — AST-discovers every class in `swing/web` declaring a `session_date` field and asserts the manifest equals that set. Add `LatchPanelVM: PageKind.FORWARD_PLANNING` and its import.
> 2. `tests/web/test_base_layout_nav.py::EXPECTED_NAV_HREFS` — pins nav hrefs in EXACT order. Insert `/latches` after `/watchlist`.
>
> Additionally, `LatchPanelVM` MUST spread `**_base_banner_fields(conn, cfg)` so `tests/web/test_base_layout_vm_recent_multi_leg_field.py`'s template-mount scan passes (it greps route + VM modules for the template filename and asserts each referenced VM carries the banner fields).

- [ ] **Step 1: Write the failing tests**

`tests/web/test_routes/test_latches_route.py`:
```python
"""GET /latches -- the read-only panel."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _seed_ftre(cfg, *, with_drift=True):
    """Seed the REAL FTRE geometry: run 121 aplus 18.34/14.88 plus the
    drifted watch rows 122-125 (stop -> 16.515, pivot -> 20.19)."""
    conn = connect(cfg.paths.db_path)
    rows = [(121, "2026-07-17", "2026-07-20", "aplus", 18.34, 14.88)]
    if with_drift:
        rows += [
            (122, "2026-07-20", "2026-07-21", "watch", 18.34, 15.195),
            (123, "2026-07-21", "2026-07-22", "watch", 18.34, 15.25),
            (124, "2026-07-22", "2026-07-23", "watch", 18.59, 16.515),
            (125, "2026-07-23", "2026-07-24", "watch", 20.19, 16.515),
        ]
    with conn:
        for rid, asof, action, bucket, pivot, stop in rows:
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0)",
                (rid, f"{asof}T17:30:05", asof, action))
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) "
                "VALUES (?, 'FTRE', ?, 17.76, ?, ?, 'universe')",
                (rid, bucket, pivot, stop))
    conn.close()


def test_empty_state_renders_200_with_no_latches(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "No live latches" in r.text


def test_panel_renders_the_fire_time_stop_not_the_drifted_one(seeded_db, monkeypatch):
    """THE discriminating render test: a latest-row implementation prints
    16.51 (the value RD quoted, ~11% early)."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: datetime(2026, 7, 27, 8, 0))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "14.88" in r.text
    assert "16.51" not in r.text
    assert "18.34" in r.text
    assert "18.89" in r.text            # zone cap 18.34 * 1.03 == 18.8902
    assert "2026-08-17" in r.text       # RD's recorded horizon


def test_two_vsts_fires_render_as_two_rows_that_do_not_merge(seeded_db, monkeypatch):
    ...  # runs 99 + 126; assert both 13.56 and 16.90 appear


def test_null_pivot_aplus_row_renders_a_degraded_row_not_a_500(seeded_db):
    """A6 -- planted via RAW conn.execute (write-barrier-bypass technique)."""
    ...


def test_panel_writes_nothing_on_get(seeded_db, monkeypatch):
    """A4: the panel GET must not touch latch_view_events."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        client.get("/latches")
    conn = connect(cfg.paths.db_path)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 0
    finally:
        conn.close()


def test_panel_degrades_to_a_visible_message_when_the_builder_raises(
        seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db

    def _boom(*_a, **_k):
        raise RuntimeError("boom")

    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "build_latch_derivation", _boom)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "latch derivation unavailable" in r.text.lower()


def test_panel_survives_a_base_banner_failure(seeded_db, monkeypatch):
    """Codex R5-1: `_base_banner_fields` runs THREE DB reads before the
    derivation guard. If any raises, an unguarded builder 500s the page --
    an A6 violation. A guarded builder renders 200 with the safe banner."""
    cfg, cfg_path = seeded_db

    def _boom(*_a, **_k):
        raise RuntimeError("banner boom")

    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_base_banner_fields", _boom)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200


def test_safe_banner_covers_every_base_layout_field(seeded_db):
    """Drift pin: a MISSING key in the fallback is a Jinja UndefinedError 500
    on an unrelated banner -- exactly the failure the fallback exists to
    prevent."""
    import dataclasses

    from swing.web.view_models.latches import _SAFE_BANNER, LatchPanelVM
    declared = {f.name for f in dataclasses.fields(LatchPanelVM)}
    assert set(_SAFE_BANNER) <= declared
    assert set(_SAFE_BANNER) == {
        "session_date", "stale_banner", "price_source_degraded",
        "price_source_degraded_until", "ohlcv_source_degraded",
        "unresolved_material_discrepancies_count",
        "recent_multi_leg_auto_correction_count", "banner_resolve_link",
    }


def test_order_fragment_is_lazily_loaded_with_an_explicit_hx_target(seeded_db):
    """The hx-target INHERITANCE gotcha: a revealed/loaded child inside any
    ancestor that sets hx-target must set hx-target='this'."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert 'hx-post="/latches/orders"' in r.text
    assert 'hx-target="this"' in r.text


def test_nav_link_target_route_exists(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    assert any(getattr(rt, "path", None) == "/latches" for rt in app.routes)
```

`tests/web/test_view_models/test_latch_panel_vm.py` — asserts the VM carries every base-banner field, declares `PAGE_KIND = PageKind.FORWARD_PLANNING`, applies the `LATCH_PANEL_LOOKBACK_SESSIONS` display filter (an old cleared latch drops off while a recent one stays), sorts live latches before cleared ones, and renders `sessions_to_horizon` / `bars_through` / telemetry echo strings. **Plus the current-price-vs-zone block (brief §1.1, Codex R6-1)**, parametrized on the REAL FTRE geometry (pivot 18.34, cap 18.8902):

```python
@pytest.mark.parametrize("price,expected_position", [
    (17.76, "below_pivot"),   # the FIRE-day close -- not yet triggered
    (18.34, "in_zone"),       # exactly AT the pivot -- inclusive lower bound
    (18.60, "in_zone"),
    (18.89, "in_zone"),       # exactly AT the cap (rounds to 18.89) -- inclusive
    (19.52, "above_zone"),    # the LIVE 2026-07-24 close -- do not chase
    (None,  "unknown"),
])
def test_current_price_vs_zone(price, expected_position, ...):
    """Brief section 1.1's 'current price vs zone'. Both bounds are INCLUSIVE
    and compared at display precision, so a sub-cent difference cannot flip the
    verdict. FAILS an implementation that omits the comparison, that uses a
    strict bound, or that treats an absent price as `below_pivot`."""


def test_the_panel_renders_the_zone_verdict_not_just_the_number(...):
    """GET /latches with the live FTRE geometry and a stubbed price of 19.52
    must render the ABOVE-ZONE label, not merely '19.52'. This is the
    2026-07-23 situation in which declining to chase was CORRECT."""


def test_a_last_close_fallback_price_is_labelled_stale(...):
    """`PriceCache` falls back to the most recent `candidates.close`, which for
    a ticker that rotated out of the screen can be days old. It must not render
    as a live quote."""


def test_an_absent_price_snapshot_does_not_block_the_row(...):
    """A6: current_price '-', zone_position 'unknown', row still rendered with
    its frozen pivot/stop/horizon."""
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/web/test_routes/test_latches_route.py tests/web/test_view_models/test_latch_panel_vm.py -q`
Expected: FAIL — 404 on `/latches` / `No module named 'swing.web.view_models.latches'`.

- [ ] **Step 3: Write the VM**

`swing/web/view_models/latches.py` — `LatchRowVM` (all display-ready strings + booleans; NO logic in the template):

```python
_ZONE_POSITIONS = ("below_pivot", "in_zone", "above_zone", "unknown")


@dataclass(frozen=True)
class LatchRowVM:
    # identity + the FROZEN mandate (brief section 1.1)
    ticker: str
    fire_date: str                     # the fire's action_session_date
    latched_pivot: str                 # "18.34"  -- %.2f of the FIRE's row
    zone_cap: str                      # "18.89"  -- pivot x 1.03
    invalidation_level: str            # "14.88"  -- the FIRE's initial_stop
    # LIVE price vs the buy zone (brief section 1.1 "current price vs zone")
    current_price: str                 # "19.52", or "-" when unavailable
    zone_position: str                 # one of _ZONE_POSITIONS
    zone_position_label: str           # ASCII, e.g. "ABOVE ZONE - do not chase"
    price_source: str                  # PriceSnapshot.source, or "-"
    price_asof: str                    # ISO, or "-"
    price_is_stale: bool
    # horizon + state
    sessions_to_horizon: int
    horizon_expiry: str
    state: str                         # one of LATCH_STATES
    clear_reason: str | None
    clear_session: str | None
    clear_trade_id: int | None
    fill_link_basis: str | None
    fill_link_anomaly: bool
    # provenance + honesty
    evaluation_run_id: int
    candidate_id: int
    detection_date: str
    pipeline_run_id: int | None
    reconfirmation_count: int
    bars_available: bool
    bars_through: str                  # ISO, or "-"
    telemetry_label: str
    is_live: bool
```

**The zone comparison (brief §1.1, Codex R6-1).** The buy zone is the closed interval `[latched_pivot, zone_cap]`:

| condition | `zone_position` | label |
|---|---|---|
| `price < latched_pivot` | `below_pivot` | `below pivot - not triggered` |
| `latched_pivot <= price <= zone_cap` | `in_zone` | `IN ZONE` |
| `price > zone_cap` | `above_zone` | `ABOVE ZONE - do not chase` |
| no price snapshot | `unknown` | `price unavailable` |

Comparison is at DISPLAY precision (`round(x, 2)` on both sides, the price-precision-parity gotcha) so a boundary price does not flip on a sub-cent difference. `above_zone` is a first-class rendered state, not an afterthought: it is the FTRE 2026-07-23 situation in which the operator's refusal to chase at 19.475 was the zone cap working correctly (`docs/rd-state.md:27`), and the panel must make that legible rather than merely showing a number.

Price comes from `cache.get_many([...], deadline_seconds=cfg.web.price_fetch_deadline_seconds, executor=executor)`; a missing snapshot yields `current_price="-"` + `zone_position="unknown"` and NEVER blocks the render (A6). `price_source` / `price_asof` / `price_is_stale` are rendered so a last-close fallback is visible as such rather than passing for a live quote (the `_last_close` path reads the most recent `candidates.close`, which for a ticker that rotated out of the screen can be days old).

And:
```python
@dataclass(frozen=True)
class DegradedRowVM:
    """Display shape for a DegradedFire (A.10): a fire whose own candidates row
    is unusable. Rendered as a visibly-degraded row so the operator sees that a
    fire EXISTED and why it produced no latch -- never silently dropped."""
    ticker: str
    fire_date: str            # the fire's action_session_date, or "-"
    evaluation_run_id: int
    candidate_id: int
    reason: str               # one of LATCH_DEGRADED_REASONS
    reason_label: str         # operator-facing ASCII, e.g. "pivot missing"


@dataclass(frozen=True)
class LatchPanelVM:
    rows: tuple[LatchRowVM, ...]
    degraded_rows: tuple[DegradedRowVM, ...]
    available: bool
    unavailable_reason: str | None
    live_candidate_ids: tuple[int, ...]     # the beacon anchor
    derivation_session: str
    horizon_session: str
    PAGE_KIND = PageKind.FORWARD_PLANNING

    # base-banner fields (populated via **_base_banner_fields):
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0
    recent_multi_leg_auto_correction_count: int = 0
    banner_resolve_link: str | None = None
```
`build_latch_panel_vm` mirrors `build_tool_health_vm`'s degrade-to-grey shape but closes a hole that pattern leaves open (Codex R5-1): **`_base_banner_fields` itself must be guarded.** It issues three DB reads (`count_unresolved_material`, `count_recent_multi_leg_auto_corrections`, `fetch_first_pending_ambiguity_resolve_link_path`, `journal.py:252-272`); any one of them raising would 500 `GET /latches` BEFORE the derivation guard is even reached — a direct A6 violation.

```python
# The all-fields-present fallback. Every key here is a base.html.j2 field:
# a MISSING key is a Jinja UndefinedError 500 on an unrelated banner, which is
# the very failure mode this is guarding against.
_SAFE_BANNER: dict = {
    "session_date": "", "stale_banner": None,
    "price_source_degraded": False, "price_source_degraded_until": None,
    "ohlcv_source_degraded": False,
    "unresolved_material_discrepancies_count": 0,
    "recent_multi_leg_auto_correction_count": 0,
    "banner_resolve_link": None,
}


def _safe_base_banner_fields(conn, cfg) -> dict:
    try:
        return _base_banner_fields(conn, cfg)
    except Exception as exc:      # noqa: BLE001 -- A6: never 500 the panel
        _log.warning("latch panel base-banner degraded: %s", exc)
        return dict(_SAFE_BANNER)
```

Then `banner = _safe_base_banner_fields(conn, cfg)` and everything else inside `try/except Exception` → `available=False, unavailable_reason="latch derivation unavailable"`.

**Drift pin (required test):** `_SAFE_BANNER.keys()` must equal the set of base-banner field names declared on `LatchPanelVM` — asserted mechanically against `dataclasses.fields(LatchPanelVM)` minus the panel-specific fields, so a future base-layout field addition cannot silently leave the fallback incomplete.

`build_tool_health_vm` / `build_research_health_vm` have the SAME unguarded shape; that is a PRE-EXISTING condition in `swing/web/view_models/health.py:75,99` and is **NOT** fixed here (out of scope). Flagged in the return report. Current price comes from `cache.get_many([...], deadline_seconds=cfg.web.price_fetch_deadline_seconds, executor=executor)`; a missing snapshot renders `-` and never blocks. Telemetry echo comes from `list_views_for_latch`.

**`session_date` note:** `_base_banner_fields` hardcodes `topbar_session_date(PageKind.HISTORY_ANALYSIS, ...)`. Because `LatchPanelVM.PAGE_KIND` is FORWARD_PLANNING, `build_latch_panel_vm` OVERRIDES the spread value: `banner["session_date"] = topbar_session_date(PageKind.FORWARD_PLANNING, now).isoformat()`. `test_topbar_cross_vm_consistency` only checks the declared `PAGE_KIND` against the manifest, but the override keeps the rendered topbar honest and is asserted in the VM test.

- [ ] **Step 4: Write the route + template + nav + CSS**

`swing/web/routes/latches.py` — `GET /latches`, mirroring `health_tool_page` (`swing/web/routes/health.py:22`) but threading the price cache + executor the way `dashboard.index` does (`swing/web/routes/dashboard.py:46`):

```python
@router.get("/latches", response_class=HTMLResponse)
def latches_panel(request: Request):
    """The read-only latch panel. Writes NOTHING (A4): the view record is
    POST /latches/view and the broker join is POST /latches/orders."""
    cfg = apply_overrides(request.app.state.cfg)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            vm = build_latch_panel_vm(
                conn, cfg,
                request.app.state.price_cache,
                request.app.state.price_fetch_executor,
            )
    finally:
        conn.close()
    return request.app.state.templates.TemplateResponse(
        request, "latches.html.j2", {"vm": vm},
    )
```

**TestClient note:** tests touching `app.state.price_fetch_executor` MUST use `with TestClient(app) as client:` (it is created in the lifespan) — the shipped convention, and every test snippet in this plan already does.

`swing/web/templates/latches.html.j2` — `{% extends "base.html.j2" %}`; a per-latch `<section class="latch-card ...">` (NOT a table at fragment root; the panel is a full page so this is a style choice, but it keeps future OOB swaps safe); the alarm block first (invalidation-cleared latches with resting orders LOUDEST per brief §1.1); an empty state reading `No live latches.`; a degraded-fire list; and the lazy order fragment:
```html
<section id="latch-orders" hx-post="/latches/orders" hx-trigger="load"
         hx-target="this" hx-swap="innerHTML"
         hx-headers='{"HX-Request": "true"}'>
  <p class="muted">Checking broker orders...</p>
</section>
```

`base.html.j2` — insert `<a href="/latches">Latches</a>` immediately after the Watchlist link.

`app.css` — under `:root` add `--latch-armed-bg/-fg`, `--latch-alarm-bg/-fg`, `--latch-cleared-bg/-fg`, `--latch-degraded-bg/-fg`; redefine at least the alarm pair under `body.dark`; every new rule references `var(--token)` only (contract A.3 forbids hex/rgb outside those two blocks).

`app.py` — `from swing.web.routes import latches as latches_route` + `app.include_router(latches_route.router)` next to `health_route`.

- [ ] **Step 5: Update the two global-invariant manifests**

- `tests/web/test_topbar_cross_vm_consistency.py`: import `LatchPanelVM` and add `LatchPanelVM: PageKind.FORWARD_PLANNING` to `MANIFEST`.
- `tests/web/test_base_layout_nav.py`: `EXPECTED_NAV_HREFS = ["/", "/watchlist", "/latches", "/journal", "/reviews/pending", "/pipeline", "/metrics", "/config"]`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/web -q && ruff check swing/`
Expected: PASS + clean. (Running ALL of `tests/web` here is deliberate — it is where the cross-VM and nav manifests live.)

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/latches.py swing/web/routes/latches.py swing/web/templates/latches.html.j2 swing/web/templates/base.html.j2 swing/web/static/app.css swing/web/app.py tests/web
git commit -m "feat(web): Task 6 - the read-only latch panel

Own VM and route (no base-layout VM field), fire-time-frozen prices, the
sessions-basis horizon, visible degradation, and the cross-VM plus nav
manifests updated in the same commit."
```

---

### Task 7: The order-awareness fragment + the Schwab resolve helper

**Files:**
- Modify: `swing/web/routes/latches.py`, `swing/web/view_models/latches.py`
- Create: `swing/web/templates/partials/latch_orders.html.j2`
- Test: `tests/web/test_routes/test_latches_orders_fragment.py`

**Interfaces:**
- Consumes: `join_orders_to_latches` / `to_resting_orders` (Task 4), `build_latch_derivation` (Task 5).
- Produces: `POST /latches/orders` (a POST because it makes an AUDITED Schwab call -- see section D.1); `swing.web.view_models.latches.build_latch_orders_vm(conn, cfg, app_state, *, now=None) -> LatchOrdersFragmentVM`; `swing.web.view_models.latches.resolve_open_orders(conn, cfg, app_state) -> OrdersResolution`.

- [ ] **Step 1: Write the failing tests**

```python
def test_fragment_reports_sandbox_short_circuit_without_constructing_a_client(...):
    """cfg.integrations.schwab.environment == 'sandbox' -> degraded block, and
    NO client construction is attempted (the sandbox short-circuit fires
    FIRST, mirroring swing/trades/entry_auto_fill.py:243)."""

def test_fragment_degrades_when_no_schwab_client_holder_is_installed(...):
    """A test config has no credentials, so _install_web_marketdata_caches
    returns None and app.state.schwab_client_holder is absent."""

def test_fragment_suppresses_alarms_when_the_order_book_is_unknown(...):
    """An unknown order book must NOT fire a false LATCH_ARMED_NO_RESTING
    _ORDER alarm."""

def test_fragment_fires_the_ftre_alarm_when_the_order_book_is_known_and_empty(...):
    """Stub the holder + get_account_orders -> []. THE FTRE failure mode."""

def test_fragment_renders_the_stale_order_alarm_for_an_invalidated_latch(...):

def test_fragment_borrows_the_client_through_the_holder(...):
    """18-H.4: the client must be taken via holder.borrow() so a concurrent
    /schwab/setup drain can finish before the tokens-DB rename."""

def test_fragment_returns_200_with_a_degraded_block_on_a_schwab_api_error(...):

def test_fragment_root_is_not_a_table_row(...):
    """The HTMX makeFragment synthetic-table-wrap gotcha."""

def test_a_GET_on_the_orders_path_is_405(...):
    """Codex R4-1: the fragment makes an AUDITED Schwab call, so it is NOT a
    safe method. A GET route would expose a real broker call to browser
    prefetch and would contradict A4 inside the arc that asserts it."""

def test_the_fragment_writes_ONLY_schwab_api_calls_and_no_domain_row(...):
    """Snapshot the row count of EVERY domain table (trades, fills,
    latch_view_events, reconciliation_*, account_equity_snapshots, candidates)
    before and after; only schwab_api_calls may change."""

def test_the_panel_GET_writes_nothing_at_all(...):
    """The companion assertion: GET /latches touches neither
    latch_view_events NOR schwab_api_calls (it makes no Schwab call -- the
    order join is lazy)."""

def test_the_fragment_requires_the_hx_request_header(...):
    """OriginGuard strict mode applies to this POST as it does to the beacon."""
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/web/test_routes/test_latches_orders_fragment.py -q`
Expected: FAIL — 404/405 on `POST /latches/orders`.

- [ ] **Step 3: Write `resolve_open_orders` + the fragment route/template**

The route is `@router.post("/latches/orders")` returning `HTMLResponse` (§D.1). Its docstring must state plainly: *this endpoint is NOT a safe method — it performs an AUDITED external Schwab call that inserts a `schwab_api_calls` row. It writes NO domain row. It is a POST for exactly that reason.*


`resolve_open_orders` reproduces the shipped ladder from `swing/trades/entry_auto_fill.py:236-380` **by construction, not by import** (no `swing/trades` dependency):
1. `environment != "production"` → `OrdersResolution(kind="sandbox"/"not_configured", ...)`.
2. `holder = getattr(app_state, "schwab_client_holder", None)`; `None` → `kind="unavailable"`.
3. `with holder.borrow() as client:` — `client is None` (the release→reconstruct window) → `kind="unavailable"`.
4. `account_hash` absent → `kind="unavailable"`.
5. `trader.get_account_orders(client, conn, account_hash, now - timedelta(days=14), now, surface="trade_entry", environment=environment, pipeline_run_id=None, status=None, max_results=None)` inside `try/except (SchwabAuthError, SchwabRateLimitError, SchwabApiError, SchwabSchemaParityError)` → `kind="error"` with the exception TYPE name only (never the message — redaction discipline).
6. Success → `kind="ok"` with `to_resting_orders(orders)`.

**Surface-value note (deviation, flagged):** `schwab_api_calls.surface` is CHECK-constrained to `('pipeline','cli','trade_entry','trade_exit')` (migration 0020). A dedicated `'latch_panel'` value would require a `schwab_api_calls` table REBUILD, which A3 forbids folding into this arc's migration. `'trade_entry'` is used — semantically the closest (this read exists to support the entry decision) and consistent with the existing precedent of the web OAuth setup writing `surface='cli'`. Banked in §H for the next time that enum is widened.

Only `kind == "ok"` enables alarms; every other kind renders a degraded block and passes `alarms=()`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/web tests/latches -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/latches.py swing/web/view_models/latches.py swing/web/templates/partials/latch_orders.html.j2 tests/web/test_routes/test_latches_orders_fragment.py
git commit -m "feat(web): Task 7 - lazy broker-order awareness fragment

The main panel GET stays network-free; the fragment borrows the shared Schwab
client holder, degrades on every failure mode, and suppresses both alarms
whenever the order book is unknown."
```

---

### Task 8: The view-telemetry beacon (the A4 seam) + the panel's telemetry echo

**Files:**
- Modify: `swing/web/routes/latches.py`, `swing/web/templates/latches.html.j2`, `swing/web/view_models/latches.py`
- Test: `tests/web/test_latches_telemetry_beacon.py`

**Interfaces:**
- Consumes: `record_view` (Task 1), `build_latch_derivation` (Task 5).
- Produces: `POST /latches/view` → `204` / `400`.

- [ ] **Step 1: Write the failing tests**

```python
def test_beacon_records_one_row_per_live_latch(...):
    """POST {"view_session_date": <rendered>, "candidate_ids": [<live id>]}
    -> 204, one row, view_count 1, latch_state_at_first_view == 'armed'."""

def test_a_second_beacon_the_same_session_updates_in_place(...):
    """view_count 2, ONE row, first_viewed_ts unchanged."""

def test_beacon_ignores_a_candidate_id_that_was_not_live_at_the_anchor(...):
    """Server RE-DERIVES against the ANCHOR session: a forged id writes
    nothing (204, zero rows)."""

def test_beacon_ignores_a_cleared_latchs_id(...):

def test_view_session_date_is_the_RENDERED_anchor_not_a_post_time_recompute(...):
    """Codex R2-1 + the project's hazard-2 gotcha. Render at 17:29 for session
    S; freeze the POST-handler clock past 17:30 so action_session_for_run(now)
    is S+1; POST the anchor S. The row MUST land on S, and the latch MUST NOT
    be dropped. A post-time-recompute implementation writes S+1 (or nothing)
    and FAILS this test."""

def test_a_future_session_anchor_is_rejected(...):                 # 400

def test_a_two_session_stale_anchor_returns_409_with_a_reload_prompt(...):
    """Codex R5-2. NOT a silent 400: a stale anchor means a RESTORED page,
    and accepting it would manufacture a view for a session the operator did
    not view (the flattering bias). Rejecting it silently would bias the other
    way. So: 409 + a rendered 'reload to record your view' fragment."""

def test_the_stale_response_body_names_both_sessions(...):
    """The notice must be actionable, and ASCII (Windows cp1252)."""

def test_the_beacon_element_swaps_into_itself_so_a_4xx_can_render(...):
    """hx-target='this' + hx-swap='innerHTML'; hx-swap='none' would silently
    discard the stale notice."""

def test_a_one_session_stale_anchor_is_accepted(...):
    """The bounded tolerance: a rollover between render and beacon is a real
    (if narrow) window and must not silently drop the view."""

def test_beacon_timestamps_are_server_stamped_not_client_supplied(...):
    """A payload carrying viewed_ts / view_count / latch_state is ignored
    entirely (the V1 server-stamp gotcha). Only the SESSION anchor and the id
    set are read from the client, and both are validated."""

def test_empty_candidate_ids_is_valid_and_writes_nothing(...):     # 204

@pytest.mark.parametrize("form,label", [
    ({"candidate_ids": "1"}, "missing view_session_date"),
    ({"view_session_date": "2026-07-27"}, "missing candidate_ids"),
    ({"view_session_date": "2026-7-27", "candidate_ids": ""}, "bad date shape"),
    ({"view_session_date": "garbage", "candidate_ids": ""}, "unparseable date"),
    ({"view_session_date": "2026-07-27", "candidate_ids": "true"}, "not an int"),
    ({"view_session_date": "2026-07-27", "candidate_ids": "0"}, "non-positive"),
    ({"view_session_date": "2026-07-27", "candidate_ids": "-3"}, "negative"),
    ({"view_session_date": "2026-07-27", "candidate_ids": "1.5"}, "float"),
    ({"view_session_date": "2026-07-27", "candidate_ids": "9500,abc"}, "one bad id"),
])
def test_beacon_rejection_ladder(form, label, ...):                # all 400

def test_a_400_names_the_offending_field(...):
    """A silently-broken beacon must be diagnosable."""

def test_beacon_over_the_cap_is_rejected(...):                     # 201 ids -> 400

def test_beacon_without_the_hx_request_header_is_403(...):
    """OriginGuard strict mode (swing/web/app.py:656)."""

def test_panel_renders_the_beacon_element_with_hx_headers_and_the_session_anchor(...):
    """hx-post, hx-trigger='load', hx-swap='none', hx-headers HX-Request, and
    an hx-vals payload carrying BOTH view_session_date and candidate_ids."""

def test_panel_echoes_the_persisted_telemetry_for_a_live_latch(...):
    """After a beacon, the next GET shows 'first viewed' + the count -- the
    self-revealing check that the beacon still works."""

def test_panel_says_not_yet_recorded_when_no_view_row_exists(...):
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/web/test_latches_telemetry_beacon.py -q`
Expected: FAIL — 405/404 on `POST /latches/view`.

- [ ] **Step 3: Write the beacon route**

```python
_MAX_BEACON_IDS = 200


@router.post("/latches/view")
async def latches_view_beacon(request: Request) -> Response:
    """Record that the latch panel was viewed while these latches were live.

    A4 seam: the PANEL GET writes nothing; this dedicated POST is the ONLY
    write path.

    The payload is an ANCHOR of what the GET rendered -- the session it was
    rendered FOR and the latch ids it showed as live -- never a source of
    truth. Both fields are VALIDATED, then the handler RE-DERIVES the latches
    AS OF THE ANCHOR SESSION and records the INTERSECTION. It does NOT
    recompute "the latest session" at POST time: that is the GET/POST TOCTOU
    recompute the project's hazard-2 gotcha forbids, and it would either
    misdate or silently DROP a view whose latch changed state between render
    and beacon. Wall-clock timestamps are still SERVER-STAMPED.
    """
```
Body:
1. `form = await request.form()`; `_parse_beacon_anchor(form) -> tuple[date, list[int]]` raising `_BeaconRejected(field, reason)`; the handler maps it to `HTMLResponse(status_code=400, content=f"<p class='latch-beacon-error'>beacon rejected: {field}: {reason}</p>")` (ASCII only).
2. Validate the session anchor: `current = action_session_for_run(datetime.now())`.
   - `anchor > current` (future) → `400`.
   - `sessions_behind(current, anchor) > 1` (a RESTORED page) → `log.warning(...)` naming both sessions, then `HTMLResponse(status_code=409, content="<p class='latch-beacon-stale'>This page is stale (rendered for {anchor}; current session is {current}). Reload to record your view.</p>")`. **NOT a silent drop and NOT an acceptance** — see §D.
3. `derivation = build_latch_derivation(conn, cfg, horizon_session_override=anchor)` — the override sets `horizon_session = anchor` and `derivation_session = session_offset(anchor, -1)`, so the ENTIRE derivation context is rebuilt from the anchor and `now` influences NOTHING that can change a recorded latch state (Codex R3-1). `now` is NOT passed.
4. `live = {lat.identity.candidate_id: lat for lat in derivation.latches if lat.is_live}`; `matched = [live[cid] for cid in posted_ids if cid in live]`.
5. `with conn:` loop → `record_view(conn, identity=lat.identity, view_session_date=anchor.isoformat(), viewed_ts=datetime.now().isoformat(timespec="seconds"), latch_state=lat.state)`.
6. `return Response(status_code=204)`.

**Interface note (drift guard):** `build_latch_derivation` already declares `horizon_session_override` in Task 5's `Interfaces` block and implements it in Task 5's Step 3 — Task 8 only CALLS it. No signature changes in this task.

New test for the completeness of the anchor rebuild:
```python
def test_the_beacon_derivation_ignores_now_entirely(...):
    """Codex R3-1. Freeze the handler clock at two wildly different instants,
    POST the SAME anchor both times, and assert the recorded
    latch_state_at_last_view is identical. A handler that still derives its bar
    bound from `now` records a different state for the second POST."""
```

- [ ] **Step 4: Add the beacon element + the telemetry echo**

In `latches.html.j2`, inside the `{% if vm.available and vm.live_candidate_ids %}` guard (no beacon when nothing is live):
```html
<div id="latch-view-beacon"
     hx-post="/latches/view"
     hx-trigger="load"
     hx-target="this"
     hx-swap="innerHTML"
     hx-headers='{"HX-Request": "true"}'
     hx-vals='{{ vm.beacon_payload_json }}'
     aria-hidden="true"></div>
```
`beacon_payload_json` is a VM field: `json.dumps({"view_session_date": horizon_session.isoformat(), "candidate_ids": "9500,9999"})` — the RENDER-TIME session anchor plus the rendered live set as a COMMA-SEPARATED digit string, autoescape-safe inside single quotes.

**Encoding decision (verified on disk):** `swing/web/static/` ships ONLY `htmx.min.js` — the `json-enc` extension is NOT vendored and `hx-ext` is used nowhere in the templates. So the beacon uses HTMX's DEFAULT `application/x-www-form-urlencoded` body and the handler reads `await request.form()`. `candidate_ids` is a comma-separated string rather than a JS array precisely because array serialization under form encoding is ambiguous. **Do NOT vendor a new JS file for this** — that would be a new dependency the brief did not authorize.

Each live latch card renders `vm_row.telemetry_label` — `"first viewed 2026-07-27T08:14:02 (2 views this session)"` or `"view telemetry: NOT YET RECORDED THIS SESSION"`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/web tests/latches tests/data -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/latches.py swing/web/templates/latches.html.j2 swing/web/view_models/latches.py tests/web/test_latches_telemetry_beacon.py
git commit -m "feat(web): Task 8 - the view-telemetry beacon POST

A dedicated HTMX POST is the only write path; the panel GET stays read-only.
The posted id set is an anchor validated against a server re-derivation, all
timestamps are server-stamped, and the panel echoes the persisted record so a
silently broken beacon is visible on the next visit."
```

---

### Task 9: Full-suite green, ruff, and the operator-witness runbook

**Files:**
- Modify: none expected (fix-forward only if the suite reveals a cross-cutting break)
- Create: none

- [ ] **Step 1: Run the FULL fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: PASS. This is the recipe §2 pre-review gate — it is where a latent cross-VM / CSS-token / nav-manifest / schema-version-fixture regression surfaces.

- [ ] **Step 2: Run ruff**

Run: `ruff check swing/`
Expected: clean.

- [ ] **Step 3: Verify the trailer discipline**

Run: `git log 4a2f7ce0..HEAD --format='%H%n%(trailers)'`
Expected: every commit shows EMPTY trailers. If a forbidden trailer slipped in, STOP and flag it in the return report (no amend, no `--no-verify`).

- [ ] **Step 4: Record the operator-witness runbook in the return report**

Both states are required (brief §4 Gate 4), browser not TestClient:
1. **LIT:** `PYTHONPATH=. python -m swing.cli web` against the live DB → `http://127.0.0.1:8080/latches`. Expect FTRE (run 121) showing pivot **18.34**, invalidation **14.88** (NOT 16.51), zone cap **18.89**, horizon **2026-08-17**; VSTS (run 126) showing **16.90 / 13.40**; VSTS (run 99) and AMN (run 103) shown as `filled`; the order fragment resolving after the page paints; and, on a SECOND load, the telemetry echo showing a first-viewed timestamp.
2. **CLEAN/EMPTY:** the seeded-gate memory — witness the panel with NO live latches too (point `swing.config.toml`'s `db_path` at a freshly migrated empty DB, or wait past every horizon). Expect `No live latches.` with no alarms and no beacon element.
3. **Teardown:** the detached web server survives TaskStop — find the PID via `Get-NetTCPConnection -LocalPort 8080`, `Stop-Process -Force`, and VERIFY the port is free.

---

## F. Self-review

**Spec coverage.**

| brief requirement | task |
|---|---|
| §1.1 latch panel: fire date, latched pivot, zone cap, sessions-to-horizon, invalidation level, 5 states | 6 (`LatchRowVM`) |
| §1.1 **current price vs zone** (`current_price` + `zone_position` + label; `below_pivot` / `in_zone` / `above_zone` / `unknown`, inclusive bounds at display precision) | 6 (`LatchRowVM`, `test_current_price_vs_zone`) |
| §1.1 invalidation visibility FIRST-CLASS | 4 (severity) + 6 (loud alarm block) |
| §1.2 tier-1 order-state awareness + present/stop/limit/qty + agreement | 4, 7 |
| §1.2 the two alarms | 4, 7 |
| §1.3 view telemetry (one timestamp, objective) | 1, 8 |
| §2.1 identity = the fire + BOTH identities stored | 1 (§A.8) |
| §2.1 all prices from the fire's own row | 2, 3 (§A.3) |
| §2.2 A1 minimal + the 21-B extension statement | §C |
| §2.2 A2 #11 one-commit + strict backup gate | 1 |
| §2.2 A3 taxonomy rider stays separate | Global Constraints |
| §2.3 RD 1 freeze at fire time | 3 |
| §2.3 RD 2 horizon in sessions | 2, 3 (§A.4) |
| §2.3 RD 3 per-fire identity | 2 (§A.2) |
| §2.3 RD 4 latch-specific fill | 3 (§A.6) |
| §2.3 RD 5 clear reason recorded | 3 (§A.7) |
| §2.3 RD 6 invalidation on closes | 3 (§A.5) |
| §2.4 one view-timestamp record; NO prompt | 1, 8 |
| §2.5 A4 deliberate write seam, named | §D, 8 |
| §2.5 A5 no base-layout VM field | 6 |
| §2.5 A6 defensive degradation | §A.10, all tasks |
| §3 FTRE 121 discriminating fixture | 3, 6 |
| §3 VSTS 99+126 must not merge | 2, 6 |
| §3 AMN sessions-vs-calendar discriminator | 3 |
| §3 armed-no-order / order-latch-cleared | 4, 7 |
| §3 invalidation on a close, not an intraday touch | 3 |
| §3 each terminal state stamps its own clear reason | 3 |
| §3 view record writes once per view, attributable to the armed latch | 1, 8 |
| phase-scope web hazard 2 (GET/POST TOCTOU) | §D, 8 |

**Placeholder scan:** every code step carries real code or an exact, named algorithm; Task 5/7's test bodies are given as named test functions with docstrings stating the exact assertion (the file-level detail an implementer needs is in the `Interfaces` + implementation steps). No "TBD", no "add error handling", no "similar to Task N".

**Type consistency:** `LatchIdentity`, `FireRow`, `DailyBar`, `EntryRecord`, `RestingOrder`, `Latch`, `DegradedFire`, `LatchDerivation`, `LatchOrderJoin`, `OrderAlarm`, `LatchViewEvent`, `LatchRowVM`, `LatchPanelVM`, `LatchOrdersFragmentVM`, `OrdersResolution` are each defined exactly once and used with the same names/fields throughout. `derive_latches` keeps one signature across Tasks 2, 3, 4, 5.

---

## G. Decisions routed to RD's plan-stage gate (brief §4 Gate 1)

**G.1 — THE FIRE-IDENTITY RULE (not contemplated by the brief; the orchestrator surfaced it at dispatch QA).**
A literal `(evaluation_run_id, ticker)` identity over-splits, and the live evidence is worse than "consecutive nights": **SLDB 9/10, YOU 31/32 and NVCR 94/95 are each the SAME action session evaluated twice**, and 30 sessions in the corpus have multiple runs (six of them have SIX). Constraints 1 and 3 then conflict — every re-fire would RE-FREEZE the pivot, which is the FTRE failure mode reintroduced inside the fix for FTRE. The plan adopts the OPEN-LATCH rule (§A.2), which has TWO clauses. Two sub-decisions inside it:

- **(i) the SAME-SESSION clause** — at most ONE latch per `(ticker, action_session_date)`, unconditionally, even if the latch already cleared during that session. Without it a fill or invalidating close mid-session lets a second same-session evaluation run open a duplicate `armed` latch for a position already held (Codex R1-1). This makes a trading session the atomic unit of the mandate.
- **within one action session, the EARLIEST row wins** — the operator's briefing is regenerated by later same-session runs, but the mandate came into existence at the first fire; empirically no A+ ticker ever has mixed buckets within a session, and within-session pivot divergence is confined to genesis week 04-20/04-21 plus two stragglers.

**RD to confirm or overrule.**

**G.2 — THE HORIZON VALUE + ANCHOR + BOUNDARY (a brief premise that does not match live code).**
The brief calls 20 sessions "the shadow-parity bound". The pipeline's shadow ENTRY window is `cfg.pipeline.observe_max_pending_window_sessions = **30**`. The plan implements **20**, because RD's own recorded FTRE horizon (2026-08-17, `docs/rd-state.md:27`) is reproduced EXACTLY by 20 NYSE sessions forward from the fire's `action_session_date` — 30 sessions gives 2026-08-31 and 20 calendar days gives 2026-08-09. Three sub-decisions ride on it: the **anchor** is `action_session_date` (not `data_asof_date`, which would give 2026-08-14), the boundary is **inclusive-expire** (`>= 20`, matching `_advance_status`'s precedent, making 2026-08-17 the first DEAD session), and the value lives in ONE constant `LATCH_HORIZON_SESSIONS`. **RD to confirm the value and whether "shadow parity" should instead bind it to 30.**

**G.3 — THE DUAL SESSION ANCHOR, AND ITS SINGLE SOURCE.** Horizon is evaluated against the FORWARD anchor `horizon_session` ("is the mandate live for the session I am about to trade"); invalidation is evaluated against the BACKWARD anchor `derivation_session` (a close can only be judged on a completed bar). Both are rendered on the panel. **The two are NOT computed independently:** `derivation_session := session_offset(horizon_session, -1)`, which is provably equal to `last_completed_session(now)` for every clock shape (pinned by `test_prev_session_of_the_action_anchor_equals_last_completed_session`). One clock read (`action_session_for_run`) therefore determines the WHOLE derivation context — which is what lets the beacon POST rebuild the exact render-time context from the session anchor alone, consulting `now` for nothing that can change a latch's state (Codex R3-1). Sole known divergence: at the exact instant of a session close both helpers return that same session, so this formulation is one session MORE conservative for one instant — it excludes a bar the nightly warm has not written yet anyway. **RD to confirm.**

**G.4 — SAME-SESSION TERMINAL PRECEDENCE.** `fill` > `invalidation` > `horizon`. This inverts `_advance_status`'s invalidation-first ordering, which has no fill concept. **RD to confirm.**

**G.5 — "BASE BREAK" DEFERRED.** The settled semantics say invalidation is "close below the fire-time initial-stop **/ base break**". V1 implements the initial-stop half only; the structural base-break level is not on `candidates` (it lives in `pattern_detection_events.structural_anchors_json`, a different id space with zero rows for the April fires). **RD to confirm the V1 narrowing.**

---

## H. V1 simplifications + banked items

1. **Structural base-break invalidation** — deferred (§G.5). V2 dependency: reading `pattern_detection_events.structural_anchors_json` for the fire's session and carrying a second frozen invalidation level.
2. **Beacon requires JavaScript.** No JS → no view record → the fire reads as `away`, which biases the 21-B discipline signal OPTIMISTIC. Mitigated by rendering the persisted telemetry on every visit (a silently-broken beacon is visible on the second load), not eliminated. Named for 21-B.
3. **`schwab_api_calls.surface='trade_entry'`** for the latch-panel order read. A dedicated `'latch_panel'` value needs a `schwab_api_calls` REBUILD which A3 keeps out of this arc's migration. Bank it for the next widening of that enum, under the #11 discipline.
4. **No order-fetch cache.** One Schwab call per panel view (bounded by the lazy fragment). A short TTL is a V2 candidate if the operator's usage makes it matter.
5. **No `latches` registry table** — `candidates.id` of the opening fire is the surrogate key. The promotion path (a registry + a nullable `latch_id` FK on both children, deterministically backfilled) is documented in §C.2 so 21-B is not cornered.
6. **Multi-order agreement is ANY-order-agrees.** With several resting BUY orders on one ticker, the join reports agreement if any single order matches on both legs. Per-order reconciliation is 21-B/21-C territory (phase-scope hazard 3, cancel targeting).
7. **`quantity` is not checked against the risk policy.** The panel shows the order qty; framework-computed sizing is 21-B's job.
8. **Display lookback is 40 sessions** (`LATCH_PANEL_LOOKBACK_SESSIONS`). The DERIVATION always folds every fire (11 rows ever), so the re-confirmation chain is never truncated; only the render is bounded.
