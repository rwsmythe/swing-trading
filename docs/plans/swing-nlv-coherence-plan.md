# Implementation plan — swing-NLV coherence refinement (SPCX §2.4 fast-follow)

**Phase:** writing-plans (this doc is the deliverable). **Executing model:** `implementer-opus-high`
(opus-max defensible — orchestrator selects + announces). **Spec:**
`docs/swing-nlv-coherence-commissioning-brief.md` (CHARC §3 architecture pass, verdict GO; the
design is SETTLED — drift-only — and this plan implements it EXACTLY, it does not re-open it).

**Tripwire:** crosses the `swing/trades` carve-out (the reconciliation service), scoped to ONE
function (`schwab_reconciliation.py` step 8). NO schema, NO migration, NO new module. The brief IS
the §3 pass; this plan adds no new tripwire.

---

## 1. Overview + the settled design

### The problem

Step 8 of `run_schwab_reconciliation` emits an `equity_delta` discrepancy (the swing-ledger vs
broker-NLV coherence check) ONLY when `journal_flat AND broker_flat`, where
`broker_flat = len(schwab_positions) == 0`. With the operator holding a declared out-of-framework
position (SPCX), `broker_flat = False`, so the coherence check is **suppressed entirely** — a real
swing-ledger-vs-broker drift (an unrecorded fill, a cash-movement mismatch) goes **undetected** for
as long as the declared position is held. §2.4 restores drift-detection by reconciling the swing
ledger against a **swing-scoped NLV** (broker NLV minus declared out-of-framework market value), so
the check fires when swing is flat-for-swing even while a declared holding is open.

### The settled design (drift-only — implement exactly)

Generalize the both-flat gate to "flat for swing", DRIFT-ONLY:

- **`broker_flat_swing` := `(schwab_positions − declared_out_of_framework_set) is empty`** — REUSE
  the `out_of_framework_set` the SPCX carve-out already builds (no new registry, no new parameter).
- **`swing_nlv` := `source_nlv − Σ(marketValue of the declared positions)`** — the declared MV taken
  from the **SAME** Schwab account payload as `source_nlv` (C1 same-snapshot; cross-snapshot is the
  false-coherence vector).
- Fire `equity_delta` on `journal_flat AND broker_flat_swing` against a single **evaluated target**
  (settled in §2.4): on the swing-scoped path (a declared position held with all MVs finite) the target
  is `swing_nlv` (`|ledger − swing_nlv| > tol(swing_nlv)`, `basis="net_liq_minus_declared_oof"`); on the
  LEGACY path (nothing declared/held — `broker_flat_swing == broker_flat`) the target is
  `finite_source_nlv` (`|ledger − finite_source_nlv| > tol`, `basis="net_liq"`, byte-identical to today);
  the C2 degrade (declared held but a MV/NLV unavailable) NEVER fires. (The fire predicate does NOT
  blanket-require "swing_nlv computable" — the legacy path fires without it; see §2.4's 3-case table.)
- **DRIFT-ONLY (C5):** NO positive "flat + coherent" PERSISTED surface. The check fires (emits a
  discrepancy) only on a real drift, exactly as today. The operator infers coherence from the absence of
  a discrepancy + the equity tile. **(§9.4 adds a swing-scoped LOG line on the coherent path — an
  internal/operational audit record in `pipeline.log`, NOT a persisted positive-coherence surface; it is
  also test (a)'s distinguisher. The drift-only persistence posture is unchanged: nothing is written on
  coherence.)**
- **REUSE the `equity_delta` discrepancy type** (no new type). Record the swing-scoping in the
  emitted `actual_value_json` (`swing_nlv`, `source_nlv`, `declared_oof_mv`,
  `basis="net_liq_minus_declared_oof"`) so the basis is explicit + auditable.
- **C2 suppress-on-missing (§9.2 — suppress, NEVER treat-as-0):** if ANY declared position's
  `marketValue` is `None`/unavailable, the swing-scoped check does NOT fire AND the missing MV is NEVER
  coerced to 0 (treat-as-0 → `swing_nlv = full NLV` → a FALSE DRIFT of ~the declared MV, the OTHER L2
  direction). A false green is the cardinal sin; a false drift is the §9.2 mirror-image failure — both
  are blocked by suppression. Mirror the existing `source_nlv is not None` guard.
- **C3 byte-identical when nothing declared/held:** empty declared set OR no declared position held →
  `broker_flat_swing == broker_flat` AND the evaluated NLV reduces to `finite_source_nlv` (the brief's
  "`swing_nlv == source_nlv`" — i.e. the legacy path evaluates `finite_source_nlv`, no surfaced
  `swing_nlv` field) → ZERO behavior change vs today (same fire decision, legacy `actual_value_json`,
  legacy run-row stamps, NO swing-scoped log line, byte-identical `summary_json`). Regression-locked by
  a test.

> **§9.4 RD L2 resolution (binding — RESOLVED, supersedes the prior run-row design).** The brief's
> §9.4 settles the §2 run-row design point the OPPOSITE way from this plan's first pass: the
> dashboard-read run-row columns **STAY RAW** (`account_equity_source_dollars` = the RAW broker NLV;
> `equity_delta_dollars` = the RAW `ledger − source_nlv`, NOT swing-scoped). The swing-scoped values
> ride **ADDITIVELY in the `equity_delta` discrepancy's `actual_value_json` ONLY WHEN IT FIRES**; there
> is **NO persisted `summary_json.equity_coherence` key** and **NO swing-scoped run-row column**. When
> swing-flat-and-coherent (no fire), the check **persists NO swing delta** and instead **LOGS** its
> swing-scoped evaluation — and that **log line is test (a)'s distinguisher** (caplog). This plan is
> realigned to §9.4 throughout (§2.4, the run-row table, test (a), the traceability row). The ONLY
> run-row behavior change vs today is the non-finite-NLV degrade (`None` instead of a raw `nan`/`inf`)
> so `ReconciliationRun.__post_init__`'s NaN/inf rejection cannot crash the run — a latent-gap fix,
> consistent with §9.4's "stays raw" (raw NLV; `None` only when non-finite).

### Math sanity (from the SPCX live-witness)

Subtracting the declared MV from the broker NLV strips the out-of-framework value, leaving
swing-relevant cash, which matches the realized-only ledger (`current_equity`) when swing is flat.
Live numbers: `NLV − SPCX $392.51 = cash ≈ ledger`.

---

## 2. Grounded code facts (re-ground against live `main` at executing — anchors drift)

All line anchors below are read off the worktree base (current `main` HEAD `3033c0f8`). The executing
implementer MUST re-ground every anchor against live code before editing (line numbers drift).

### 2.1 Step 8 — the equity-coherence block (`swing/trades/schwab_reconciliation.py`)

The block lives at **`:1804-1853`** in the current tree:

```python
# --- 8. Equity coherence (Arc 4b Task 8) — ledger-vs-NLV, flat-only ---
ledger_equity = current_equity(
    starting_equity=starting_equity,
    exits=list_all_exitshape_via_fills(conn),
    cash_movements=list_cash(conn),
)                                                               # :1820-1824
coherence_delta: float | None = (
    ledger_equity - source_nlv if source_nlv is not None else None
)                                                               # :1825-1827
journal_flat = len(open_trades) == 0                            # :1828
broker_flat = len(schwab_positions) == 0                        # :1829
if (
    journal_flat
    and broker_flat
    and source_nlv is not None
    and coherence_delta is not None
    and abs(coherence_delta) > _cash_coherence_tolerance(source_nlv)
):                                                              # :1830-1836
    _emit(
        conn, run_id=run_id, discrepancy_type="equity_delta",
        field_name="net_liquidating_value", counters=counters, dedup_seen=dedup_seen,
        expected_value_json=json.dumps(
            {"equity_dollars": ledger_equity, "basis": "ledger"}, sort_keys=True),
        actual_value_json=json.dumps(
            {"equity_dollars": source_nlv, "basis": "net_liq"}, sort_keys=True),
        delta_text=f"${coherence_delta:+.2f} (ledger minus net_liq)",
    )                                                           # :1837-1853
```

- `source_nlv: float | None = float(schwab_account.net_liquidating_value) if schwab_account is not None else None`
  at **`:1246-1249`** (pre-BEGIN).
- `schwab_positions = getattr(schwab_account, "positions", []) or []` at **`:1347`** (inside the txn,
  reused by step 5 + the orphan pass).
- `out_of_framework_set = frozenset(t.upper() for t in out_of_framework_tickers if t)` at
  **`:1237-1239`** — the SPCX carve-out's normalized set, already in scope at step 8.
- `_cash_coherence_tolerance(nlv) -> float` at **`:202-205`**: `return max(5.00, 0.005 * abs(float(nlv)))`.
- `current_equity(*, starting_equity, exits, cash_movements)` (`swing/trades/equity.py:39-45`):
  `starting + Σ realized_pnl + net_cash_movements`. With no exits and no cash → `ledger == starting_equity`
  (controllable test arithmetic).

### 2.2 The Schwab position dict shape (read off the existing orphan pass, `:1396-1460`)

Each `schwab_positions` element is a dict with:
- `p.get("instrument").get("symbol")` — the ticker (the orphan pass uppercases for the
  `out_of_framework_set` membership test at `:1443`).
- `p.get("longQuantity")` / `p.get("shortQuantity")` — qty (net = long − short).
- `p.get("marketValue")` — a **top-level numeric** field, sibling of `instrument`
  (account-specification.md L176). The orphan pass already handles a `None`/non-finite MV at
  `:1427-1434` (carries it as `None` so JSON stays RFC-7159-valid). **The §2.4 declared-MV sum REUSES
  this exact `p.get("marketValue")` read** — same field, same dict, no new fetch.

### 2.3 C1 same-snapshot — VERIFIED ON DISK

The plan verified that `schwab_account.net_liquidating_value` and `schwab_positions[].marketValue`
originate from ONE account-details call (one snapshot):

- Production caller `_step_schwab_orders` (`swing/integrations/schwab/pipeline_steps.py:543-548`)
  makes a SINGLE `details = get_account_details(client, conn, account_hash, ...)` call, then passes
  `schwab_account=details` to `run_schwab_reconciliation` at `:589-602`.
- The mapper `map_account_details_to_response` (`swing/integrations/schwab/mappers.py:183-237`)
  extracts BOTH from the SAME `response` object: `net_liquidating_value` from
  `response['securitiesAccount']['currentBalances']['liquidationValue']` (`:205-221`) and `positions`
  (each carrying its own `marketValue`) from `response['securitiesAccount']['positions']`
  (`:225-227`). Both land on ONE `SchwabAccountResponse` dataclass (`models.py:95-98`).

**Conclusion: C1 holds structurally at the `run_schwab_reconciliation` boundary.** `source_nlv`
(from `schwab_account.net_liquidating_value`) and the declared `Σ marketValue` (from
`schwab_account.positions[].marketValue`) are siblings of ONE snapshot — no cross-snapshot or
separately-fetched MV is possible in the production path. **The executing implementer re-confirms this
read still holds (no intervening refactor split the fetch).**

### 2.4 Run-row recording — the column/JSON/log layout (SETTLED here, per brief §9.4)

`update_run_completed` (`swing/data/repos/reconciliation.py:170-216`) stamps exactly THREE equity
columns on `reconciliation_runs`: `account_equity_journal_dollars`, `account_equity_source_dollars`,
`equity_delta_dollars`. There is **NO column** for `swing_nlv` or `Σ declared MV`, and **C4 forbids a
schema change**. The `ReconciliationRun.__post_init__` (`swing/data/models.py:1121-1143`) REJECTS
NaN/inf on all three columns — so whatever value is stamped MUST be finite-or-`None`.

Today step 8's completion stamp (`:1910-1924`) writes:
- `account_equity_journal_dollars = ledger_equity`
- `account_equity_source_dollars = source_nlv` (raw broker NLV)
- `equity_delta_dollars = coherence_delta` (= `ledger − source_nlv`, computed at `:1825-1827`, ALWAYS,
  independent of whether the check fired).

**The SETTLED §2.4 layout — run-row columns STAY RAW (brief §9.4 RD L2 resolution).** The
dashboard-read columns are NOT swing-scoped. The swing-scoped evaluation surfaces in TWO places ONLY:
(1) ADDITIVELY in the `equity_delta` discrepancy's `actual_value_json` **WHEN IT FIRES**, and (2) a
**LOG line** when the swing-scoped path runs and finds coherence (no fire). No persisted swing artifact
exists in the coherent case; no new column; no `summary_json.equity_coherence` key.

| field | value | rationale |
|---|---|---|
| `account_equity_journal_dollars` (column) | `ledger_equity` | UNCHANGED — the realized-only ledger. |
| `account_equity_source_dollars` (column) | `finite_source_nlv` (the RAW broker NLV when finite, else `None`) | **RAW broker NLV — UNCHANGED on every real run (§9.4: stays raw).** The equity tile must NOT under-report the operator's TRUE account value by the declared MV. The ONLY behavior change vs today is that a non-finite NLV stamps `None` (not the raw `nan`/`inf`) so `__post_init__`'s NaN/inf rejection cannot crash the run (Codex R2 MAJOR 1) — i.e. "raw NLV, `None` only when non-finite." Any "broker's NLV" consumer reads this column; it stays the raw finite snapshot value. |
| `equity_delta_dollars` (column) | the **RAW** `coherence_delta` (= `ledger − finite_source_nlv`, itself `None` when `finite_source_nlv is None`) — **NOT swing-scoped** | **§9.4: STAYS RAW.** The prior plan made this swing-scoped (`ledger − swing_nlv`); §9.4 REVERTS that. The column reflects `ledger − source_nlv` exactly as today on every run (legacy, swing-scoped-coherent, swing-scoped-drift, and C2-degrade alike). **Finite-or-None invariant (Codex R1 MAJOR 1 / R2 MAJOR 1):** finite-or-`None` because the single normalized `finite_source_nlv` closes the mapper's unchecked-`float(nlv)` gap (a non-finite NLV → `finite_source_nlv is None` → `coherence_delta is None`), and `ledger` is finite by construction; `__post_init__`'s NaN/inf rejection never trips. |
| `summary_json` (existing column) | **UNCHANGED — NO `equity_coherence` key (§9.4 drops it).** The legacy `summary_json` is byte-identical on EVERY path (legacy, swing-scoped, C2-degrade). | §9.4: the coherent case persists NO swing delta — there is no persisted swing artifact at all (the LOG carries it). Dropping the key keeps `summary_json` byte-identical and simplifies C3. |
| `equity_delta` discrepancy `actual_value_json` (when it FIRES) | the swing-scoped shape `{swing_nlv, source_nlv (= finite_source_nlv), declared_oof_mv, basis="net_liq_minus_declared_oof"}` **ONLY on a swing-scoped fire** (`swing_scope_active AND swing_nlv_computable`); a LEGACY fire (nothing declared/held) keeps the EXISTING `{equity_dollars (= finite_source_nlv), basis="net_liq"}` shape verbatim | the brief §2/§9.4 auditable basis rides ADDITIVELY here, ONLY on fire (Codex R3 MAJOR 2 — the legacy fire shape is unchanged, test (d) asserts it). |
| **LOG line** (swing-scoped coherent case — NO fire) | a single `log.info(...)` recording the swing-scoped evaluation: `basis="net_liq_minus_declared_oof"`, `source_nlv` (= `finite_source_nlv`), `swing_nlv`, `declared_oof_mv`, and the evaluated `swing_coherence_delta` (= `ledger − swing_nlv`) | §9.4: when swing-flat-and-coherent the check LOGS its swing-scoped evaluation rather than persisting it. **This log line is test (a)'s distinguisher** (caplog) — it proves the swing-scoped path RAN and found coherence (so a real drift WOULD have fired). |

**The swing-scoped evaluation is recorded on `equity_delta`'s `actual_value_json` ON FIRE, and LOGGED
on coherence — NEVER on the run-row columns (§9.4).** The run-row `equity_delta_dollars` stays the RAW
`ledger − source_nlv` on every path; it is NOT the live-witness signal anymore (the prior plan's swing-
scoped-delta-in-the-column design is superseded). The live-witness signal is: (i) NO false
`equity_delta` discrepancy when coherent, and (ii) the swing-scoped LOG line (`pipeline.log`) showing
`swing_nlv` and a near-zero `swing_coherence_delta`.

**The swing-scoped LOG line — the EXACT shape + emission gate (determinism the executing tests
assert):** the line is emitted at `log.info` level on `swing.trades.schwab_reconciliation`'s module
logger (`log = logging.getLogger(__name__)`, `:72`) when `swing_nlv_computable AND broker_flat_swing
AND journal_flat AND NOT fired` (the swing-scoped path RAN, was eligible, and found coherence). It is a
single structured INFO line carrying `basis="net_liq_minus_declared_oof"`, `source_nlv`, `swing_nlv`,
`declared_oof_mv`, `swing_coherence_delta` (ASCII-only per the recipe §2 ASCII discipline — this rides
the `pipeline.log` seam where the redactor scrubs prose, mirroring the existing Arc-4b cash INFO line at
`:1928`). The emission cases:

| case | LOG line emitted? | `actual_value_json` written? |
|---|---|---|
| swing-scoped coherent (`swing_nlv_computable`, swing-flat, |delta| ≤ tol → NO fire) | YES — the swing-scoped INFO line (test (a)'s caplog distinguisher) | no (no discrepancy) |
| swing-scoped drift (`swing_nlv_computable`, swing-flat, |delta| > tol → FIRES) | (the fire path emits the discrepancy; the swing-scoped basis rides `actual_value_json`) | YES — `basis="net_liq_minus_declared_oof"` |
| C2 degrade (`swing_scope_active AND NOT swing_nlv_computable`) | NO swing-scoped line (the swing-scoped path could NOT run — MV/NLV unavailable) | no |
| legacy (`NOT swing_scope_active`, nothing declared/held) | NO swing-scoped line (byte-identical to today) | legacy `{equity_dollars, basis="net_liq"}` only on a legacy fire |

(The swing-scoped LOG line is emitted ONLY on the swing-scoped-coherent path. The executing test (a)
asserts the caplog record exists with the swing-scoped fields; test (c)/the legacy path assert the
swing-scoped line is ABSENT — proving the degrade/legacy path did not run the swing-scoped evaluation.)

### 2.5 Dashboard / equity-tile consumers of `account_equity_*` / `equity_delta_dollars` (cross-checked)

The brief mandates cross-checking the consumers so the raw broker NLV is not misreported. Result of
the grep audit (`account_equity_source_dollars | equity_delta_dollars | account_equity_journal_dollars`
across `swing/`):

- **The web equity tile does NOT read these columns.** The dashboard/account equity tile sources its
  value from the SEPARATE `account_equity_snapshots` table (`swing/web/view_models/dashboard.py:13`
  imports `swing.data.repos.account_equity_snapshots`; `swing/web/routes/account.py` + the capital-
  friction surface read `account_equity_snapshots`). It does NOT consume `reconciliation_runs.account_equity_*`.
- **The ONLY web consumer of `reconciliation_runs` equity data** is `dashboard.py:82-95`, which reads
  the most-recent completed schwab run's `run_id` and COUNTS its `unresolved` `equity_delta`
  discrepancies for a "needs attention" banner. It reads the discrepancy COUNT, not the
  `account_equity_*` / `equity_delta_dollars` columns. (It is improved by §2.4: an unresolved
  swing-scoped `equity_delta` now correctly lights the banner when a real drift exists while holding
  a declared position — the exact case the bug hid.)
- The `account_equity_source_dollars` / `equity_delta_dollars` columns ARE read by the non-web
  `swing/trades/reconciliation.py` + `swing/journal/tos_import.py` (the TOS-CSV path, a DIFFERENT
  reconciliation source) and surfaced on the `ReconciliationRun` model (`models.py:1104-1106`,
  `:1138-1140`). The TOS path does not run step 8; its writes are independent.

**Decision (explicit, per brief §9.4):** the equity tile shows the **raw `source_nlv`** (unchanged —
because it reads `account_equity_snapshots`, not these columns, the tile is untouched either way; and
`account_equity_source_dollars` keeps the raw broker NLV regardless). **Per §9.4 the run-row columns
STAY RAW:** `account_equity_source_dollars` = the raw broker NLV and `equity_delta_dollars` = the raw
`ledger − source_nlv` (NOT swing-scoped). No consumer misreports the raw broker NLV — the swing-scoped
value never touches these columns; it rides ADDITIVELY in the `equity_delta` discrepancy's
`actual_value_json` on fire, and the coherent case LOGS it (persists nothing). The ONLY behavior change
vs today on these columns is the non-finite-NLV degrade to `None` (the latent `__post_init__` crash
fix). RD verifies the equity-tile consumers are unaffected at executing (§9.4).

### 2.6 Existing tests + fixtures (the production-shape fixture template)

- `tests/trades/test_schwab_equity_coherence.py` — the existing step-8 tests (tolerance, within/past
  tolerance, suppressed-with-open-trade, the 18-H.6 orphan case, the run-row ledger stamp). These are
  the REGRESSION LOCKS for C3 (the both-flat path must stay byte-identical). Its `cash_recon_full`
  fixture (`tests/trades/conftest.py:80-153`) builds positions as
  `{"instrument": {"symbol": t}, "longQuantity": q, "shortQuantity": 0}` with **NO `marketValue`** and
  does **NOT** thread `out_of_framework_tickers`.
- `tests/trades/test_out_of_framework_carveout.py` — the SPCX-arc fixture template that DOES carry the
  real shape:
  - `_position(symbol, *, long_qty=0.0, short_qty=0.0, market_value=None)` → the REAL Schwab position
    dict (`{"shortQuantity", "longQuantity", "instrument": {"symbol", "type"}, "marketValue"}`).
  - `_SchwabAccount(net_liquidating_value, positions)`.
  - `_run(conn, positions, *, out_of_framework=())` → calls `run_schwab_reconciliation` threading
    `out_of_framework_tickers=out_of_framework`.

  **The new §2.4 tests REUSE this `_position` + `_SchwabAccount` + `_run` pattern** (derive fixtures
  from real emitter output; the `cash_recon_full` fixture is insufficient because it lacks
  `marketValue` + the `out_of_framework_tickers` pass-through).

---

## 3. Per-task breakdown (TDD-first)

Three tasks. Each: failing test FIRST (with the pre-fix vs post-fix assertion value proving it
distinguishes), then the minimal implementation, then acceptance. The whole change is localized to
`schwab_reconciliation.py` step 8 + one new test file (plus a small assertion or two added to the
existing coherence test file for the C3 regression locks).

### Task 1 — `broker_flat_swing` + the swing-scoped fire condition (tests (b), (e))

**Purpose:** generalize the gate from `broker_flat` to `broker_flat_swing` so the check FIRES on a
real drift while a declared position is held, and STAYS suppressed when an undeclared position is held.

**Files:** `swing/trades/schwab_reconciliation.py` step 8 (`:1820-1853`). New test file
`tests/trades/test_swing_nlv_coherence.py`.

**Failing test(s) FIRST:**

- `test_drift_while_holding_declared_fires` (test (b) — THE core value). Setup: declared `SPCX`
  held (`marketValue=392.51`), journal flat, `source_nlv = 392.51 + 1500.00 = 1892.51` (so swing cash
  component `= source_nlv − 392.51 = 1500.00`), `starting_equity = 1450.00`, no exits/cash → `ledger =
  1450.00`. `swing_nlv = 1500.00`; `|ledger − swing_nlv| = |1450 − 1500| = $50.00`;
  `tolerance = max($5, 0.5% × 1500) = $7.50`; `50 > 7.50` → FIRES.
  - **Assertion (Task 1 — the GATE only):** exactly one `equity_delta` discrepancy row exists (FIRE vs
    NO-FIRE). The swing-scoped `actual_value_json` SHAPE assertion (`basis ==
    "net_liq_minus_declared_oof"`, `swing_nlv == 1500.0`, `source_nlv == 1892.51`, `declared_oof_mv ==
    392.51`) is deferred to Task 2 (Codex R2 MINOR 1 — `swing_nlv` is a Task 2 product, so the
    JSON-shape assertion lands in the Task 2 commit, keeping each commit independently green; see the
    sequencing note below).
  - **Pre-fix value:** ZERO `equity_delta` rows (`broker_flat = False` because a position is held →
    the whole `if` is suppressed — the bug). **Post-fix value:** one row. **Distinguishes.**

- `test_undeclared_position_present_suppresses` (test (e) — the scoping distinguisher). Setup (pinned
  arithmetic per Codex R1 MINOR 1 so BOTH bad impl variants would fire): declared `SPCX` held
  (`marketValue=392.51`) + an UNDECLARED `FOO` held (`marketValue=500.00`), journal flat,
  `source_nlv = 2392.51`, `starting_equity = 1450.00`, no exits/cash → `ledger = 1450.00`.
  `out_of_framework=("SPCX",)`. (Under the over-eager "subtract-declared-only-while-ignoring-FOO" impl,
  swing_nlv would be `2392.51 − 392.51 = 2000.00`, delta `−550.00`, tol `$10.00` → FIRES. Under the
  over-eager "subtract-all-positions" impl, swing_nlv would be `2392.51 − 892.51 = 1500.00`, delta
  `−50.00`, tol `$7.50` → FIRES. The CORRECT impl never computes a swing delta because FOO makes swing
  non-flat.)
  - **Assertion:** (1) ZERO `equity_delta` discrepancy rows (`broker_flat_swing = False` because FOO is
    an unaccounted real position → swing is not flat); (2) `FOO` STILL emits an
    `untracked_broker_position` discrepancy (the orphan pass is byte-identical); (3) `SPCX` emits NO
    orphan (carved out) — i.e. the swing-flat predicate correctly partitions declared from undeclared.
  - **Pre-fix value:** ZERO `equity_delta` (suppressed because `broker_flat = False`). **Post-fix
    value:** ZERO `equity_delta` (suppressed because `broker_flat_swing = False`). *This pre/post pair
    is equal* — so it is NOT a raw pre/post distinguisher; it is the SCOPING lock that distinguishes a
    CORRECT generalization from BOTH over-eager variants above (each of which FIRES on the pinned
    numbers). A naive "subtract-declared-only" OR "subtract-all-positions" impl fires `equity_delta`
    erroneously; this test FAILS both.

**Minimal implementation:** define `broker_flat_swing` over the **SAME `schwab_positions` list
elements** the legacy `broker_flat = len(schwab_positions) == 0` counts — do NOT introduce a
nonzero-quantity "held" filter (Codex R1 MAJOR 3: a qty filter would make `broker_flat_swing == True`
while legacy `broker_flat == False` for an empty declared set + a zero-qty position row, breaking C3
byte-identical):

```python
undeclared_positions = [
    p for p in schwab_positions
    if (p.get("instrument") or {}).get("symbol", "").upper() not in out_of_framework_set
]
broker_flat_swing = len(undeclared_positions) == 0
```

(REUSING the same `p["instrument"]["symbol"]` upper-case read the orphan pass uses at `:1443`.) Then
replace `broker_flat` in the `if` with `broker_flat_swing`. **Reduction proof (C3):** when the
declared set is empty, EVERY element survives the comprehension → `undeclared_positions ==
schwab_positions` → `broker_flat_swing == (len(schwab_positions) == 0) == broker_flat`, byte-identical
across ALL list shapes (including zero-qty rows).

**Task-sequencing note (Codex R2 MINOR 1 / R4 MINOR — Task 1's gate depends on Task 2's `swing_nlv`).**
Tasks 1 and 2 form ONE logical change. **PRIMARY path: merge Tasks 1 + 2 into a SINGLE implementation
commit** (the production change is small + localized to step 8 + one logical unit) — all the
swing-scoped assertions (the FIRE-vs-NO-FIRE gate AND the swing-scoped `actual_value_json` shape) land
in that one commit, so there is no inter-task green-state ambiguity. **ALTERNATIVE (if split):** ship
Task 2's `finite_source_nlv`/`swing_nlv`/C2-guard COMPUTATION first (no gate change yet → still green),
THEN Task 1's gate swap (`broker_flat` → `broker_flat_swing`) WITH the swing-scoped emitted
`actual_value_json` — in that ordering the swing-scoped JSON-shape test lands WITH the Task-1 gate
commit (because `swing_nlv` already exists from the Task-2 commit). Either way: do NOT ship a gate-only
commit whose test asserts a swing-scoped JSON shape its own commit has not produced.

**Acceptance:** (b) fires with the swing-scoped `actual_value_json`; (e) suppressed with the orphan
pass intact; the existing `test_coherence_suppressed_with_open_trade` (journal not flat) still
passes (journal_flat gate unchanged).

### Task 2 — `swing_nlv` computation + the C1/C2 guards (tests (a), (c))

**Purpose:** compute `swing_nlv = source_nlv − Σ(declared marketValue)` from the SAME snapshot (C1),
suppress on any missing declared MV (C2 — suppress NEVER treat-as-0, §9.2), and make the
coherent-while-holding case LOG the swing-scoped evaluation (test (a)'s §9.4 caplog distinguisher — the
run-row columns STAY RAW).

**Files:** `swing/trades/schwab_reconciliation.py` step 8. Tests in `tests/trades/test_swing_nlv_coherence.py`.

**Failing test(s) FIRST:**

- `test_coherent_while_holding_logs_swing_scoped_evaluation` (test (a) — the §9.4 caplog
  distinguisher). Setup: declared `SPCX` held (`marketValue=392.51`), journal flat, `nlv = 392.51 +
  1450.00 = 1842.51`, `starting_equity = 1450.00`, no exits/cash → `ledger = 1450.00`. `swing_nlv =
  source_nlv − Σ declared MV = 1842.51 − 392.51 = 1450.00`; `swing_coherence_delta = ledger − swing_nlv
  = 1450.00 − 1450.00 = 0.00`; `tolerance = max($5, 0.5% × 1450) = $7.25`; `0.00 ≤ 7.25` → NO fire.
  - **Assertion (the §9.4 realignment — caplog is the distinguisher):** (1) ZERO `equity_delta`
    discrepancy rows; (2) **a `caplog` record exists** at INFO on `swing.trades.schwab_reconciliation`
    carrying the swing-scoped evaluation — `basis="net_liq_minus_declared_oof"`, `swing_nlv ≈ 1450.0`,
    `source_nlv ≈ 1842.51`, `declared_oof_mv ≈ 392.51`, `swing_coherence_delta ≈ 0.0` (assert on the
    record's structured args / message substring); (3) the completed run row's `equity_delta_dollars`
    is the **RAW** `ledger − source_nlv = 1450.00 − 1842.51 = −392.51` (STAYS RAW per §9.4 — NOT
    swing-scoped); (4) `account_equity_source_dollars ≈ 1842.51` (raw broker NLV, UNCHANGED); (5)
    `summary_json` has **NO `equity_coherence` key** (§9.4 — no persisted swing artifact in the
    coherent case).
  - **Pre-fix value (legacy code):** the check is SUPPRESSED (broker not flat → the whole `if` never
    runs the swing-scoped evaluation) → **NO swing-scoped caplog record is emitted** (the swing-scoped
    code path does not exist pre-fix); the run row carries the source-based delta `equity_delta_dollars
    = ledger − source_nlv = −392.51`. **Post-fix value:** the swing-scoped caplog record IS emitted
    (`basis="net_liq_minus_declared_oof"`, `swing_nlv ≈ 1450.0`, `swing_coherence_delta ≈ 0.0`) proving
    the swing-scoped path RAN and found coherence; the run row's `equity_delta_dollars` is STILL the
    raw `−392.51` (unchanged column). **Distinguishes via the caplog LOG line:** pre-fix the
    swing-scoped evaluation never runs (no record); post-fix it runs and logs (a record with the
    swing-scoped basis + `swing_nlv` + near-zero `swing_coherence_delta`). The `equity_delta_dollars`
    column is NO LONGER the distinguisher (it is raw `−392.51` both before and after — equal — so it
    CANNOT distinguish; only the LOG line does, per §9.4).

- `test_drift_while_holding_records_swing_scoped_actual_value_json` (the swing-scoped JSON half of test
  (b) — Codex R2 MINOR 1; lands in the merged Tasks-1+2 commit [PRIMARY], or, if split, with the
  Task-1 gate-swap commit after the Task-2 computation exists). Same setup as
  `test_drift_while_holding_declared_fires` (`source_nlv =
  1892.51`, declared SPCX `marketValue=392.51`, `ledger = 1450.00` → FIRES). **Assertion:** the emitted
  `equity_delta` row's `actual_value_json` carries `basis == "net_liq_minus_declared_oof"`, `swing_nlv
  == 1500.0`, `source_nlv == 1892.51`, `declared_oof_mv == 392.51`. **Pre-fix:** no row at all (the
  whole `if` suppressed). **Post-fix:** the row with the swing-scoped basis. **Distinguishes** via the
  swing-scoped `actual_value_json` shape (this is the JSON-shape assertion moved off Task 1).

- `test_missing_declared_mv_suppresses` (test (c) — C2). Setup (pinned arithmetic per Codex R1
  MAJOR 2 so a `None→0` impl provably FIRES): declared `SPCX` held with `marketValue=None`, journal
  flat, `source_nlv = 1500.00`, `starting_equity = 1450.00`, no exits/cash → `ledger = 1450.00`.
  `out_of_framework=("SPCX",)`. (Under a bad `None→0` impl, swing_nlv would be `1500.00 − 0 = 1500.00`,
  delta `|1450 − 1500| = $50.00`, tol `max($5, 0.5%×1500) = $7.50` → `50 > 7.50` → FIRES. The CORRECT
  C2 impl suppresses because the declared MV is missing.)
  - **Assertion (§9.4-aligned):** (1) ZERO `equity_delta` discrepancy rows (the PRIMARY distinguisher —
    a `None→0` impl would FALSE-FIRE this row); (2) **NO swing-scoped caplog record** — no INFO line with
    `basis="net_liq_minus_declared_oof"` / `swing_nlv` — proving the degrade path did NOT run a coherent
    swing-scoped evaluation (the C2 path suppressed cleanly: the declared MV is missing → suppress, NEVER
    treat-as-0; §9.2 — no bogus `swing_nlv` was computed or logged); (3) the run row's
    `equity_delta_dollars == −50.00` (the RAW legacy `ledger − source_nlv = 1450 − 1500`, STAYS RAW per
    §9.4 — NOT a swing-scoped value); (4) `summary_json` has **NO `equity_coherence` key** (§9.4 dropped
    it; byte-identical legacy summary).
  - **Pre-fix value:** suppressed anyway (`broker_flat = False`); the run row carries the legacy
    source-based delta `−50.00`; no swing-scoped log line (the path does not exist pre-fix).
    **Post-fix value:** STILL no fire (C2 guard caught the `None` MV) AND no swing-scoped coherent log
    line (the degrade path ran — `swing_nlv` was never computed, so neither a fire nor a coherent log
    happened). **Distinguishes the suppress-NEVER-treat-as-0 (§9.2) PRIMARILY via the spurious
    discrepancy row:** a naive impl that treated a `None` MV as `0.0` would compute a bogus `swing_nlv ==
    1500.00` and FALSE-FIRE an `equity_delta` (`|1450 − 1500| = 50 > 7.50` tol — the OTHER L2 direction:
    a false drift of ~the declared MV) — assertion (1) FAILS that impl. Assertion (2) is the
    complementary lock: it proves NO coherent swing-scoped evaluation was logged on the degrade path (the
    swing-scoped path did not run); it does NOT claim a false-fire impl must log (under the
    mutually-exclusive fire/log design a false-FIRE would emit the discrepancy, not a coherent log). The
    C2 guard suppresses cleanly — no fire, no log.

- `test_active_holding_nonfinite_nlv_degrades` (Codex R3 MINOR — active declared holding + non-finite
  `source_nlv`). Setup: declared `SPCX` held (`marketValue=392.51`), journal flat,
  `net_liquidating_value = float("nan")` (or `inf`), `starting_equity = 1450.00`. `out_of_framework=("SPCX",)`.
  - **Assertion (§9.4-aligned):** (1) ZERO `equity_delta` discrepancy rows (`finite_source_nlv is
    None` → no fire); (2) the run row's `account_equity_source_dollars IS NULL` and
    `equity_delta_dollars IS NULL` (NOT a raw `nan`/`inf` — so `ReconciliationRun.__post_init__`'s
    NaN/inf rejection never trips and the run COMPLETES, not fails); (3) **NO swing-scoped caplog
    record** (the swing-scoped path could NOT run — `finite_source_nlv is None`, so `swing_nlv` is never
    computed; the C2-family degrade); (4) `summary_json` has **NO `equity_coherence` key** (§9.4).
  - **Pre-fix value:** with the existing code the non-finite NLV flows into `coherence_delta` /
    `account_equity_source_dollars` and `update_run_completed` → `ReconciliationRun.__post_init__`
    raises `ValueError` (the run FAILS) — i.e. today this is an unhandled latent gap on a non-finite
    NLV. **Post-fix value:** the run COMPLETES with `None` stamps (raw NLV, `None` only when non-finite
    — consistent with §9.4's "stays raw"). **Distinguishes** the finite-NLV normalization (the run
    completes-vs-fails on a non-finite NLV). This is the ONLY run-row column behavior change vs today.

**Minimal implementation.** Define these SEPARATE, single-purpose booleans/values (Codex R2 MINOR 2 —
do NOT overload one `swing_nlv_computable` flag with three meanings):

- `finite_source_nlv := source_nlv if (source_nlv is not None and math.isfinite(source_nlv)) else None`
  — the SINGLE normalized NLV (Codex R2 MAJOR 1). **Every finite stamp uses `finite_source_nlv`, NEVER
  the raw `source_nlv`** (the mapper does `float(nlv)` with NO finiteness check, so a `nan`/`inf` NLV is
  reachable and would trip `ReconciliationRun.__post_init__`'s NaN/inf rejection on
  `account_equity_source_dollars`/`equity_delta_dollars`). When `finite_source_nlv is None`, the equity
  check does not fire and the legacy `None` stamp posture applies (consistent with today's `source_nlv
  is not None` gate — §2.4 widens nothing).
- `declared_held := [p for p in schwab_positions if symbol_upper(p) in out_of_framework_set]` (the
  complement of `undeclared_positions`); `has_declared_oof_position := len(declared_held) > 0`. **(§9.3
  Σ scope:** `declared_held` iterates the positions PRESENT in the payload whose ticker is declared — an
  un-held declared ticker is simply absent from `schwab_positions`, so it never appears in `declared_held`,
  contributes 0 to the sum, and cannot error. The membership test is on the declared SET; the iteration
  is over the PRESENT positions.)
- `declared_mv_available` + `declared_oof_mv`: sum `marketValue` over `declared_held`. **MV
  normalization (Codex R1 MINOR 2 — cover non-numeric malformed payloads, not just `None`):** for each
  declared held position attempt `float(raw_mv)` inside a `try/except (TypeError, ValueError)`; if
  `raw_mv is None`, conversion fails, OR the result is not `math.isfinite(...)` → `declared_mv_available
  = False`. Else `declared_oof_mv = Σ float(raw_mv)`. (Mirrors the orphan pass MV handling at `:1427-1434`.)
- `swing_scope_active := has_declared_oof_position` — i.e. a declared position is actually held. (Per
  §9.4 this no longer gates any persisted artifact — `summary_json` stays byte-identical on EVERY path;
  the key was DROPPED. `swing_scope_active` still distinguishes the swing-scoped/C2-degrade paths from
  the legacy path for the fire/log decision below.)
- `swing_nlv_computable := swing_scope_active and declared_mv_available and (finite_source_nlv is not
  None)`. When true: `swing_nlv = finite_source_nlv − declared_oof_mv`; assert `math.isfinite(swing_nlv)`
  (belt — both inputs already finite); the live delta `swing_coherence_delta = ledger_equity − swing_nlv`;
  the fire predicate uses `_cash_coherence_tolerance(swing_nlv)`.

**Wiring the gate via a single "evaluated target" (Codex R3 MAJOR 1 — the legacy both-flat path MUST
still fire when nothing is declared/held; `swing_nlv_computable` is `False` there, so the fire
predicate CANNOT require it).** The "evaluated target" governs the FIRE decision + the emitted
`actual_value_json` (on fire) + the swing-scoped LOG (on coherence) ONLY. **Per §9.4 it does NOT govern
the run-row columns — those stay RAW.** Derive ONE evaluated `(eval_nlv, eval_delta, eval_basis)` per
run:

| case | eval_nlv | eval_delta | eval_basis | fires? | swing-scoped LOG on coherence? |
|---|---|---|---|---|---|
| `not swing_scope_active` (nothing declared/held) — the legacy path | `finite_source_nlv` | `ledger − finite_source_nlv` (= legacy `coherence_delta`) | `"net_liq"` | when `journal_flat AND broker_flat_swing AND finite_source_nlv is not None AND abs(eval_delta) > tol(eval_nlv)` (byte-identical to today — `broker_flat_swing == broker_flat` here) | NO (legacy path, byte-identical to today) |
| `swing_scope_active AND swing_nlv_computable` — the swing-scoped path | `swing_nlv` | `ledger − swing_nlv` | `"net_liq_minus_declared_oof"` | when `journal_flat AND broker_flat_swing AND abs(eval_delta) > tol(eval_nlv)` | YES, when eligible (swing-flat) and NOT fired — the swing-scoped INFO line (test (a)) |
| `swing_scope_active AND NOT swing_nlv_computable` — the C2 degrade | (none) | (none) | (degrade) | NEVER fires (C2; §9.2 suppress-NEVER-treat-as-0); the RAW legacy `coherence_delta` is still STAMPED to `equity_delta_dollars` (column stays raw), but NO discrepancy is emitted | NO (swing-scoped evaluation could not run) |

- Fire `equity_delta` only per the per-case predicate above (the swing-scoped tolerance uses
  `_cash_coherence_tolerance(eval_nlv)`). The emitted `actual_value_json` uses `eval_basis`'s shape:
  the legacy `{equity_dollars: finite_source_nlv, basis: "net_liq"}` on the legacy path, the
  `{swing_nlv, source_nlv: finite_source_nlv, declared_oof_mv, basis: "net_liq_minus_declared_oof"}`
  shape on the swing-scoped path (Codex R3 MAJOR 2). **This is the ONLY place the swing-scoped values
  are persisted — additively, on fire (§9.4).**
- **The swing-scoped LOG line (§9.4 — the coherent-case artifact + test (a)'s distinguisher):** on the
  swing-scoped path, when eligible (`journal_flat AND broker_flat_swing AND swing_nlv_computable`) and
  the check does NOT fire (`abs(swing_coherence_delta) <= tol(swing_nlv)`), emit a single
  `log.info(...)` recording `basis="net_liq_minus_declared_oof"`, `source_nlv (= finite_source_nlv)`,
  `swing_nlv`, `declared_oof_mv`, `swing_coherence_delta` (ASCII-only). This proves the swing-scoped
  evaluation RAN and found coherence (so a real drift would have fired). NO log line on the legacy or
  C2-degrade paths. The fire/log paths are MUTUALLY EXCLUSIVE for determinism: fire → discrepancy +
  `actual_value_json` (no coherent log line); coherent → LOG (no discrepancy).
- `account_equity_source_dollars = finite_source_nlv` — the **RAW** broker NLV when finite, else `None`
  (§9.4: stays raw; non-finite degrade to `None` is the only behavior change vs today).
- `equity_delta_dollars = coherence_delta` — the **RAW** `ledger − finite_source_nlv` on EVERY path
  (itself `None` when `finite_source_nlv is None`). **§9.4: STAYS RAW — NOT `ledger − swing_nlv`.**
  (The prior plan's swing-scoped stamp is REVERTED.) The single normalized `finite_source_nlv` is the
  only change to this column's value vs today (non-finite → `None`); on every finite run it is the
  identical legacy value.
- **`summary_json` — UNCHANGED (§9.4 dropped the `equity_coherence` key).** Do NOT add any key. The
  legacy `summary_json` is byte-identical on EVERY path (legacy / swing-scoped / C2-degrade). The
  coherent-case swing-scoped artifact lives in the LOG, not `summary_json`; the fire-case artifact lives
  in the discrepancy's `actual_value_json`.

**Acceptance:** (a) NO fire + a swing-scoped caplog INFO line (`basis="net_liq_minus_declared_oof"`,
`swing_nlv`, `swing_coherence_delta ≈ 0`) + RAW `equity_delta_dollars` (= `ledger − source_nlv`) + RAW
`account_equity_source_dollars` + NO `equity_coherence` key; (c) suppresses on missing/malformed MV +
NO swing-scoped log line (degrade proven, §9.2 suppress-NEVER-treat-as-0) + RAW legacy
`equity_delta_dollars`; non-finite `source_nlv` → `finite_source_nlv = None` → no fire + `None` stamps
(the `__post_init__` NaN/inf guard never trips on any stamped column) + NO swing-scoped log line; the
legacy (nothing-declared/held) path's run row + `summary_json` are byte-identical (no log line) — C3.

### Task 3 — C3 regression locks (nothing-declared/held byte-identical) (test (d))

**Purpose:** prove ZERO behavior change on the normal both-flat case (empty declared set OR no
declared position held). This guards against an over-eager generalization changing the common case.

**Files:** add lock assertions to `tests/trades/test_swing_nlv_coherence.py` (and/or extend the
existing `tests/trades/test_schwab_equity_coherence.py` — those are the canonical both-flat locks). No
new production code (Tasks 1+2 must already be byte-identical here by construction).

**Failing/lock test(s):**

- `test_nothing_declared_both_flat_byte_identical` (test (d) — C3 LOCK, stated as a lock, pre == post).
  Setup: empty declared set, journal flat, ZERO broker positions, a drifted `nlv` past tolerance.
  - **Assertion (§9.4-aligned):** the `equity_delta` fires exactly as the legacy both-flat path
    (`actual_value_json.basis == "net_liq"`, NOT `"net_liq_minus_declared_oof"`);
    `equity_delta_dollars == ledger − source_nlv` (RAW); **`summary_json` has NO `equity_coherence` key**
    (§9.4 dropped it — byte-identical legacy summary); AND **NO swing-scoped caplog INFO line** (the
    legacy path never runs the swing-scoped evaluation). This is a LOCK (pre == post) — its value is
    guarding against an over-eager generalization (a gate change, an unconditional `summary_json` key,
    OR a spurious swing-scoped log on the legacy path) changing the common case.
- `test_declared_set_nonempty_but_not_held_byte_identical` (C3, second half). Setup:
  `out_of_framework=("SPCX",)` but SPCX NOT in `schwab_positions`, ZERO held positions, journal flat,
  drifted `nlv`.
  - **Assertion (§9.4-aligned):** identical to the legacy both-flat path (`broker_flat_swing ==
    broker_flat == True`, fires with `basis == "net_liq"`, RAW `equity_delta_dollars == ledger −
    source_nlv`); **NO `equity_coherence` key in `summary_json`** (`swing_scope_active == False` —
    nothing held → the swing-scoped path never runs); **NO swing-scoped caplog INFO line**. LOCK
    (pre == post).
- `test_empty_declared_set_with_position_row_suppresses_like_legacy` (C3 — the Codex R1 MAJOR 3 lock).
  Setup: `out_of_framework=()` (EMPTY), journal flat, ONE broker position row held
  (`_position("AAPL", long_qty=10.0, market_value=...)`), drifted `nlv`.
  - **Assertion:** ZERO `equity_delta` discrepancy rows — i.e. `broker_flat_swing == broker_flat ==
    False` (the empty declared set leaves EVERY position element in `undeclared_positions`, so the
    swing predicate reduces EXACTLY to legacy `len(schwab_positions) == 0 == False`). Proves the
    comprehension does NOT introduce a nonzero-qty filter that would falsely flip `broker_flat_swing`
    to `True` on a held position. LOCK (pre == post — both legacy and new suppress). (The AAPL position
    STILL emits its `untracked_broker_position` orphan, byte-identical to 18-H.6.)
- The EXISTING `tests/trades/test_schwab_equity_coherence.py` tests
  (`test_coherence_silent_within_tolerance`, `test_coherence_warns_past_tolerance`,
  `test_coherence_suppressed_with_open_trade`, `test_coherence_orphan_position_emits_untracked_discrepancy`,
  `test_completed_run_stores_ledger_equity_not_stale_snapshot`) MUST stay green unchanged — they are
  the standing both-flat + orphan-pass regression locks (the executing implementer runs the FULL fast
  suite to green BEFORE the Codex review per recipe §2).

**Acceptance:** both new C3 locks pass pre AND post (byte-identical); the full pre-existing coherence
suite stays green.

---

## 4. The §6 discriminating tests, mapped to tasks

Fixtures built from the REAL Schwab account + positions payload shape (the
`test_out_of_framework_carveout._position` + `_SchwabAccount` + `_run` template — `marketValue` on each
position, `net_liquidating_value` on the account, `out_of_framework_tickers` threaded).

| # | test | task | pre-fix value | post-fix value | distinguishes via |
|---|---|---|---|---|---|
| (a) | coherent-while-holding → no fire; LOGS the swing-scoped evaluation (§9.4) | Task 2 | suppressed (broker not flat) → the swing-scoped path never runs → **NO swing-scoped log line**; run row `equity_delta_dollars = ledger − source_nlv ≈ −392.51` (RAW) | no fire; **a swing-scoped caplog INFO line** (`basis="net_liq_minus_declared_oof"`, `swing_nlv ≈ 1450`, `swing_coherence_delta ≈ 0`); run row `equity_delta_dollars ≈ −392.51` (RAW, UNCHANGED) | **the swing-scoped LOG line (caplog)** — pre-fix absent, post-fix present (§9.4; the run-row column is RAW both ways and CANNOT distinguish) |
| (b) | drift-while-holding → `equity_delta` FIRES (THE core value) | Task 1 | suppressed → NO fire (the bug — a real drift undetected) | fires (one `equity_delta` row, `actual_value_json.basis="net_liq_minus_declared_oof"`) | fire vs no-fire |
| (c) | missing declared MV → suppress (C2; §9.2 suppress-NEVER-treat-as-0) | Task 2 | suppressed anyway; RAW legacy source-based delta recorded; no log line | still no fire (C2 guard); RAW legacy `equity_delta_dollars`; NO swing-scoped coherent log line | PRIMARILY the absence of a spurious `equity_delta` row (FAILS a `None→0` false-drift impl); the no-swing-scoped-log assertion is the complementary lock (degrade path logged no coherent eval) |
| (d) | nothing declared/held → byte-identical (C3 LOCK) | Task 3 | fires legacy both-flat (evaluated NLV == `finite_source_nlv`, `basis="net_liq"`, NO `equity_coherence` summary key, NO swing-scoped log line, legacy `actual_value_json` with no `swing_nlv` field) | identical | LOCK (pre == post) — guards over-eager generalization |
| (e) | undeclared position present → `broker_flat_swing=False` → no fire | Task 1 | suppressed (`broker_flat=False`) | suppressed (`broker_flat_swing=False`); orphan pass STILL banners the undeclared ticker, declared ticker carved out | the scoping (declared vs undeclared partition); FAILS a naive "subtract all positions" impl |

**Regression-test-arithmetic note (memory `feedback_regression_test_arithmetic`):** every numeric test
above states the ledger, NLV, declared MV, `swing_nlv`, the delta, and the tolerance so the assertion
is computed under BOTH the pre-fix path (legacy `broker_flat`/`source_nlv`) and the post-fix path
(`broker_flat_swing`/`swing_nlv`) — proving the test distinguishes (a test that passes under both
paths is worthless). **Note on test (a) (§9.4):** because the run-row `equity_delta_dollars` STAYS RAW
(= `ledger − source_nlv ≈ −392.51` both pre- and post-fix), the COLUMN cannot distinguish — the
distinguisher is the swing-scoped LOG line (pre-fix: the swing-scoped path is suppressed, no line;
post-fix: the path runs on coherence and logs). Tests (d)/(e) are explicitly LOCKS (pre == post) with
their distinguishing value spelled out (over-eager-generalization guards), not silent.

---

## 5. C1–C5 + L2 traceability table (the QA checklist)

| condition | requirement | task(s) | test(s) | honored-on-disk anchor |
|---|---|---|---|---|
| **C1** (L2 same-snapshot; §9.1 READ-PATH) | declared MV from the SAME Schwab account payload/object as `source_nlv` (§9.1: RD verifies the READ PATH, not just the arithmetic) | Task 2 | the §2.3 disk-verification (no new fetch); (a)/(b) read MV from the same `schwab_account.positions` | declared `Σ marketValue` reads `schwab_positions[].marketValue` (the SAME object `source_nlv` derives from); verified `get_account_details` → mapper extracts both from one `response` (`mappers.py:205-236`) onto ONE `SchwabAccountResponse` (§2.3); executing re-confirms no intervening refactor split the fetch |
| **C2** (L2 suppress-on-missing; §9.2 suppress NEVER treat-as-0) | any declared MV `None`/malformed/non-finite → do NOT fire AND do NOT treat-as-0 (treat-as-0 → `swing_nlv = full NLV` → a FALSE DRIFT of ~the declared MV, the OTHER L2 direction); also non-finite `source_nlv` → unavailable | Task 2 | (c) `test_missing_declared_mv_suppresses` (pinned to FALSE-FIRE a `None→0` impl — asserts NO fire AND NO swing-scoped log line, proving the degrade path RAN per §9.2) + `test_active_holding_nonfinite_nlv_degrades` (non-finite NLV → run completes with `None` stamps, no log line) | the `declared_mv_available` flag (a `float()` try/except + `math.isfinite` per declared MV) + the single `finite_source_nlv` normalization both feed `swing_nlv_computable`; on NOT-computable the swing-scoped path is SUPPRESSED (no fire, no swing-scoped log) — the MV is never coerced to 0; mirrors the existing `source_nlv is not None` guard at `:1833`; the `finite_source_nlv` guard closes the mapper's unchecked-`float(nlv)` gap (R1 MAJOR 1 / R2 MAJOR 1) |
| **C3** (byte-identical) | empty declared set OR none held → `broker_flat_swing==broker_flat` AND the evaluated NLV == `finite_source_nlv` (no surfaced `swing_nlv` field on the legacy path) → zero behavior change | Task 3 | (d) both halves + `test_empty_declared_set_with_position_row_suppresses_like_legacy` (R1 MAJOR 3 — empty declared set + a held position row) + the 5 existing coherence locks | `broker_flat_swing` is defined over the SAME `schwab_positions` elements legacy `broker_flat` counts (NO qty filter) → reduces to `broker_flat` exactly; the evaluated NLV is `finite_source_nlv`; the RAW run-row stamps are byte-identical (§9.4) and `summary_json` has NO `equity_coherence` key (DROPPED on every path) and NO swing-scoped log line on the legacy path |
| **C4** (no schema / no module / reuse `equity_delta`) | config-driven; NO migration; NO new run-row column; ONLY `schwab_reconciliation.py` step 8 | all | the tripwire self-cert §7; `_emit(discrepancy_type="equity_delta")` reused | NO new `swing/data/migrations/*`, NO new module, **NO new run-row column** (§9.4); the swing-scoped values ride the existing discrepancy `actual_value_json` on fire + a LOG line on coherence — NOTHING is added to `summary_json` or the run-row columns |
| **C5** (drift-only) | NO positive "flat + coherent" surface | all | NO test asserts a positive surface; the check only emits a discrepancy on a drift | the `if` still emits a discrepancy ONLY when `abs(delta) > tolerance`; the swing-scoped LOG line is an internal/operational audit record (a log, not a persisted positive-coherence surface — §9.4), not a new positive emit path |
| **L2** (no false equity signal, either direction; §9 RD checklist) | no false coherence (a green hiding a real drift) NOR false drift | C1 + C2 are the guards | (a) no false drift + LOGS the swing-scoped eval; (b) catches a real drift; (c) no false coherence on missing data AND no false DRIFT via treat-as-0 (§9.2); (e) no false coherence on an undeclared position | RD QAs L2 against the shipped diff at the executing return per the §9 checklist (C1 read-path, C2 suppress-never-treat-as-0, Σ scope, run-row-stays-RAW, C3); **RD sign-off is merge-blocking** |

---

## 6. Verification gates

1. **The §6 discriminating tests** (Tasks 1–3 above) — each states the pre-fix vs post-fix value.
2. **Full fast suite to GREEN before the Codex review** (recipe §2) — `python -m pytest -m "not slow"
   -q` from the worktree; fix any cross-cutting/global-invariant break to green so the review converges
   on a green diff. Then again at end-of-run (after review fixes).
3. **`ruff check swing/`** clean (no new violation in `swing/`).
4. **Operator live-witness (binding — mirrors SPCX §5.10; §9.4-aligned):** on the live DB while holding
   declared SPCX, a real reconciliation run → the swing-NLV check RUNS (no false `equity_delta` when
   coherent), witnessed via the **swing-scoped LOG line** in `pipeline.log` (`basis=net_liq_minus_declared_oof`,
   `swing_nlv`, near-zero `swing_coherence_delta`) — proving the swing-scoped evaluation ran and found
   coherence. The run row's `account_equity_source_dollars` shows the RAW broker NLV and
   `equity_delta_dollars` shows the RAW `ledger − source_nlv` (NOT swing-scoped — §9.4); there is NO
   persisted swing artifact in the coherent case. Optionally inject a known ledger drift (e.g. a
   synthetic cash-movement) to confirm test (b) FIRES live (an `equity_delta` discrepancy whose
   `actual_value_json` carries the swing-scoped basis).
5. **Executing review stack** (per §8 below): `review-strong` (binding, repo-access, run to
   `NO_NEW_CRITICAL_MAJOR`, NEVER tier down) + `codex-auto-review` (gating, repo-access) + RD L2 QA +
   the operator live-witness. The orchestrator's merged-head no-false-green re-run is the final net.

---

## 7. Tripwire self-certification

- **`swing/trades` carve-out** → scoped to `swing/trades/schwab_reconciliation.py` step 8 ONLY (the
  gate condition + the `broker_flat_swing`/`swing_nlv` computation + the RAW run-row recording + the
  `equity_delta` `actual_value_json` shape on fire + the swing-scoped LOG line on coherence). The
  read-only `swing/trades` default returns after the arc.
- **NO schema, NO migration, NO new run-row column (§9.4)** — `swing_nlv`/`declared_oof_mv` ride the
  discrepancy `actual_value_json` ON FIRE + a LOG line on coherence; NOTHING is added to `summary_json`
  or the run-row columns. The three `account_equity_*` / `equity_delta_dollars` columns stay RAW (only
  `equity_delta_dollars`/`account_equity_source_dollars` change value vs today on a NON-finite NLV → the
  `None` degrade; finite runs are byte-identical). NO `swing/data/migrations/*` file.
- **NO new module, NO new standing process, NO new dependency.**
- **Exact production file list (the ONLY `swing/` touch):** `swing/trades/schwab_reconciliation.py`
  (step 8). No other `swing/` file changes. Test files added/edited:
  `tests/trades/test_swing_nlv_coherence.py` (new) + possibly small additions to
  `tests/trades/test_schwab_equity_coherence.py` (C3 locks).
- This plan adds NO new tripwire beyond the brief's CHARC §3 pass (GO).

---

## 8. The EXECUTING spec (baked in so the plan accounts for it — brief §7)

- **Executing cell:** `implementer-opus-high` (opus-max defensible — the orchestrator selects +
  announces). The design is fully settled here, the change is small + localized to step 8, the
  L2-safety is precisely specified (C1–C5), and the gate stack (double review + RD L2 + live-witness)
  is the real net.
- **Review:** `review-strong` (binding, **repo-access**, run to `NO_NEW_CRITICAL_MAJOR`, NEVER tier
  down) + `codex-auto-review` (gating, **repo-access**, matched-high effort
  `codex exec review --commit <pre-review-sha> -c model_reasoning_effort=high`). Production-code review
  MUST be able to read beyond the diff (recipe §3 REPO-ACCESS note — the C1 same-snapshot correctness
  depends on the UN-CHANGED `get_account_details` → mapper reference graph; a pure diff-only review is
  blind to it). Either point Codex cwd at the worktree (`-s read-only`) OR include
  `pipeline_steps.py:543-602` + `mappers.py:183-237` in the stdin bundle so the reviewer can confirm
  C1.
- **The two standing MUST-DOs:**
  1. The convergence transcript persisted to the TRACKED path
     `docs/reviews/swing-nlv-coherence-executing-codex-findings.md` (the round-by-round verbatim Codex
     responses + per-finding adjudication + the final `NO_NEW_CRITICAL_MAJOR` verdict line + round
     count), and the verdict/round-count quoted verbatim in the executing return (a director QA cannot
     read a torn-down worktree — it must be post-merge-verifiable).
  2. Commit with **BARE git from the worktree cwd** (`cd` into `.worktrees/<name>`, run `git add` /
     `git commit` directly — NOT `git -C`); if a commit is denied, STOP + report up (do not pre-broaden
     permissions).
- **Base** = then-current `main`; the orchestrator rebases before merge + re-runs the fast suite on the
  MERGED HEAD (the binding no-false-green). The `actual_value_json` shape change (swing-scoped basis on
  fire) could surface a cross-arc fixture interaction (the 18-B.1×18-D lesson) — the merged-head re-run
  is the net. (`summary_json` is UNCHANGED per §9.4, so it adds no cross-arc surface.)

---

## 9. Explicitly OUT of scope

- **Any positive "flat + coherent" confirmation surface** (C5 — operator decision; drift-only).
- **Any new discrepancy type** (reuse `equity_delta`).
- **Any schema change / migration / new run-row column** (C4/§9.4; `swing_nlv`/`declared_oof_mv` ride
  the discrepancy `actual_value_json` ON FIRE + a LOG line on coherence — NOT `summary_json`, NOT a new
  column; the run-row columns stay RAW).
- **Any measurement-chain touch** (L4 — §2.4 journals nothing: no `trades`/`fills` row, touches no
  measurement-chain module; the change is the equity-coherence computation only).
- **The SPCX out-of-framework carve-out itself** (already shipped at 18-H.6 / SPCX; this arc REUSES
  its `out_of_framework_set` + `out_of_framework_tickers` parameter, adds nothing to the registry).
- **The TOS-CSV reconciliation path** (`run_tos_reconciliation`) — a different source that does not run
  step 8; untouched.
- **The web equity tile** — reads `account_equity_snapshots`, not these columns; untouched.
