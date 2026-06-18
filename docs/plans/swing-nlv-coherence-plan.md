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
- **DRIFT-ONLY (C5):** NO positive "flat + coherent" surface. Fires only on a real drift, exactly as
  the check does today. The operator infers coherence from the absence of a discrepancy + the equity
  tile.
- **REUSE the `equity_delta` discrepancy type** (no new type). Record the swing-scoping in the
  emitted `actual_value_json` (`swing_nlv`, `source_nlv`, `declared_oof_mv`,
  `basis="net_liq_minus_declared_oof"`) so the basis is explicit + auditable.
- **C2 suppress-on-missing:** if ANY declared position's `marketValue` is `None`/unavailable, the
  swing-scoped check does NOT fire (cannot compute `swing_nlv` reliably; a false green is the
  cardinal sin). Mirror the existing `source_nlv is not None` guard.
- **C3 byte-identical when nothing declared/held:** empty declared set OR no declared position held →
  `broker_flat_swing == broker_flat` AND the evaluated NLV reduces to `finite_source_nlv` (the brief's
  "`swing_nlv == source_nlv`" — i.e. the legacy path evaluates `finite_source_nlv`, no surfaced
  `swing_nlv` field) → ZERO behavior change vs today (same fire decision, legacy `actual_value_json`,
  NO `equity_coherence` summary key). Regression-locked by a test.

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

### 2.4 Run-row recording — the column/JSON layout (SETTLED here)

`update_run_completed` (`swing/data/repos/reconciliation.py:170-216`) stamps exactly THREE equity
columns on `reconciliation_runs`: `account_equity_journal_dollars`, `account_equity_source_dollars`,
`equity_delta_dollars`. There is **NO column** for `swing_nlv` or `Σ declared MV`, and **C4 forbids a
schema change**. The `ReconciliationRun.__post_init__` (`swing/data/models.py:1121-1143`) REJECTS
NaN/inf on all three columns — so whatever value is stamped into `equity_delta_dollars` MUST be finite.

Today step 8's completion stamp (`:1910-1924`) writes:
- `account_equity_journal_dollars = ledger_equity`
- `account_equity_source_dollars = source_nlv` (raw broker NLV)
- `equity_delta_dollars = coherence_delta` (= `ledger − source_nlv`, computed at `:1825-1827`, ALWAYS,
  independent of whether the check fired).

**The SETTLED §2.4 layout:**

| field | value | rationale |
|---|---|---|
| `account_equity_journal_dollars` (column) | `ledger_equity` | UNCHANGED — the realized-only ledger. |
| `account_equity_source_dollars` (column) | `finite_source_nlv` (the raw broker NLV when finite, else `None`) | **UNCHANGED on every real run** — the raw broker NLV must NOT be misreported. The ONLY behavior change vs today is that a non-finite NLV stamps `None` (not the raw `nan`/`inf`) so `__post_init__`'s NaN/inf rejection cannot trip (Codex R2 MAJOR 1). The equity machinery + any future "broker's NLV" consumer reads this column; it stays the raw finite snapshot value. |
| `equity_delta_dollars` (column) | `swing_coherence_delta` when `swing_nlv_computable`, else the legacy `coherence_delta` (= `ledger − finite_source_nlv`, itself `None` when `finite_source_nlv is None`) | the evaluated delta when an evaluation is possible (`ledger − swing_nlv` on the swing-scoped path); otherwise the legacy source-NLV delta `ledger − finite_source_nlv` (the legacy both-flat path AND the C2/non-computable degrade — where the check never FIRES but the legacy delta is still STAMPED). **Finite-or-None invariant (Codex R1 MAJOR 1 / R2 MAJOR 1):** finite-or-`None` because (i) `swing_nlv` is computed only when `finite_source_nlv is not None` AND all declared MVs are finite (the single normalized `finite_source_nlv` closes the mapper's unchecked-`float(nlv)` gap), and (ii) `ledger` is finite by construction; `__post_init__`'s NaN/inf rejection never trips. |
| `summary_json` (existing column, conditional key) | append an `equity_coherence` sub-object `{basis, source_nlv, swing_nlv, declared_oof_mv, evaluated_delta}` **ONLY when `swing_scope_active` (a declared position is held)** — incl. the C2 degrade case (`basis="net_liq"`, no `swing_nlv`). When nothing is declared/held, DO NOT add the key (Codex R2 MAJOR 2 — keeping the legacy path's `summary_json` BYTE-IDENTICAL for C3). | records `source_nlv` AND `swing_nlv` AND `Σ declared MV` so the operator live-witness can SEE the swing-scoped delta and test (a) is distinguishable WITHOUT a schema change — while preserving C3 byte-identity on the common legacy path. |
| `equity_delta` discrepancy `actual_value_json` (when it FIRES) | the swing-scoped shape `{swing_nlv, source_nlv (= finite_source_nlv), declared_oof_mv, basis="net_liq_minus_declared_oof"}` **ONLY on a swing-scoped fire** (`swing_scope_active AND swing_nlv_computable`); a LEGACY fire (nothing declared/held) keeps the EXISTING `{equity_dollars (= finite_source_nlv), basis="net_liq"}` shape verbatim | the brief §2 auditable basis on the emitted row (Codex R3 MAJOR 2 — the legacy fire shape is unchanged, test (d) asserts it). |

**`equity_delta_dollars` is the load-bearing run-row field for the live-witness:** when holding a
declared SPCX coherently, the recorded `equity_delta_dollars ≈ 0` (swing-scoped) instead of the legacy
`≈ −Σ declared MV` (large). That single column flip is the test-(a) distinguisher AND the operator
live-witness signal.

**The `equity_coherence` summary sub-object — the EXACT 3-case shape (Codex R5 — determinism the
executing tests assert):** the key exists ONLY when `swing_scope_active` (a declared position held);
its fields are:

| case | basis | source_nlv | swing_nlv | declared_oof_mv | evaluated_delta |
|---|---|---|---|---|---|
| swing-scoped (`swing_scope_active AND swing_nlv_computable`) | `"net_liq_minus_declared_oof"` | `finite_source_nlv` | the computed `swing_nlv` | the computed `Σ declared MV` | `ledger − swing_nlv` |
| C2 degrade (`swing_scope_active AND NOT swing_nlv_computable`) | `"net_liq"` | `finite_source_nlv` (= `None` if non-finite NLV) | KEY OMITTED | KEY OMITTED | the legacy `ledger − finite_source_nlv` (the value stamped to `equity_delta_dollars`; `None` if `finite_source_nlv is None`) |
| legacy (`NOT swing_scope_active`, nothing declared/held) | — the `equity_coherence` key is ABSENT entirely (C3 byte-identical) — | | | | |

(Omitted keys are absent, NOT present-with-`null` — the executing tests assert `"swing_nlv" not in
summary_json["equity_coherence"]` for the C2 degrade.)

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

**Decision (explicit, per brief):** the equity tile shows the **raw `source_nlv`** (unchanged —
because it reads `account_equity_snapshots`, not these columns, the tile is untouched either way; and
`account_equity_source_dollars` keeps the raw broker NLV regardless). The **coherence delta**
(`equity_delta_dollars`) becomes **swing-scoped** when swing-flat-computable. No consumer misreports
the raw broker NLV: the raw value lives in `account_equity_source_dollars` (kept raw) + the
`summary_json.equity_coherence.source_nlv` (kept raw); only the *delta* column carries the
swing-scoped value, which is correct (it is the delta the check evaluated).

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
suppress on any missing declared MV (C2), and make the coherent-while-holding case record the
swing-scoped delta ≈ 0 (test (a) distinguisher).

**Files:** `swing/trades/schwab_reconciliation.py` step 8. Tests in `tests/trades/test_swing_nlv_coherence.py`.

**Failing test(s) FIRST:**

- `test_coherent_while_holding_records_swing_scoped_delta` (test (a) — the distinguisher). Setup:
  declared `SPCX` held (`marketValue=392.51`), journal flat, `nlv = 392.51 + 1450.00`,
  `starting_equity = 1450.00`, no exits/cash → `ledger = 1450.00`. `swing_nlv = 1450.00`;
  `|ledger − swing_nlv| = 0.00 < tolerance` → NO fire.
  - **Assertion:** (1) ZERO `equity_delta` discrepancy rows; (2) the completed run row's
    `equity_delta_dollars ≈ 0.0` (the swing-scoped delta, `ledger − swing_nlv`); (3)
    `account_equity_source_dollars ≈ 1842.51` (raw broker NLV, UNCHANGED); (4)
    `summary_json.equity_coherence.swing_nlv ≈ 1450.0` and `.source_nlv ≈ 1842.51` and
    `.declared_oof_mv ≈ 392.51` and `.basis == "net_liq_minus_declared_oof"`.
  - **Pre-fix value:** the check is suppressed (broker not flat) AND the run row carries the
    SOURCE-based delta `equity_delta_dollars = ledger − source_nlv = 1450 − 1842.51 = −392.51` (large,
    `≈ −Σ declared MV`). **Post-fix value:** `equity_delta_dollars ≈ 0.0` + the swing-scoped
    `summary_json`. **Distinguishes** via the recorded swing-scoped delta (≈ 0 vs ≈ −392.51).

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
  - **Assertion:** (1) ZERO `equity_delta` discrepancy rows; (2) the `equity_coherence` key IS present
    in `summary_json` (a declared position IS held → `swing_scope_active == True`) but proves the
    degrade path ran — `summary_json.equity_coherence.basis == "net_liq"` (the legacy basis, NOT
    `"net_liq_minus_declared_oof"`) and the `swing_nlv` key is ABSENT (omitted, NOT present-with-`None`
    — Codex R3 NIT; assert `"swing_nlv" not in summary_json["equity_coherence"]`); AND
    `equity_delta_dollars == −50.00` (the legacy `ledger − source_nlv = 1450 − 1500`, NOT a swing-scoped
    value). (This is the C2 degrade case the `swing_scope_active` summary gate explicitly covers —
    Codex R2 MAJOR 2.)
  - **Pre-fix value:** suppressed anyway (`broker_flat = False`); the run row carries the legacy
    source-based delta `−50.00`. **Post-fix value:** STILL no fire (C2 guard caught the `None` MV),
    proven by asserting the swing-scoped delta was NOT recorded (the degrade path ran — `basis="net_liq"`,
    not `"net_liq_minus_declared_oof"`). **Distinguishes** the suppress-on-missing: a naive impl that
    treated a `None` MV as `0.0` would compute a bogus `swing_nlv == 1500.00` and FALSE-FIRE; this test
    FAILS that impl.

- `test_active_holding_nonfinite_nlv_degrades` (Codex R3 MINOR — active declared holding + non-finite
  `source_nlv`). Setup: declared `SPCX` held (`marketValue=392.51`), journal flat,
  `net_liquidating_value = float("nan")` (or `inf`), `starting_equity = 1450.00`. `out_of_framework=("SPCX",)`.
  - **Assertion:** (1) ZERO `equity_delta` discrepancy rows (`finite_source_nlv is None` → no fire);
    (2) the run row's `account_equity_source_dollars IS NULL` and `equity_delta_dollars IS NULL` (NOT a
    raw `nan`/`inf` — so `ReconciliationRun.__post_init__`'s NaN/inf rejection never trips and the run
    COMPLETES, not fails); (3) `summary_json.equity_coherence` IS present (`swing_scope_active == True`)
    with `source_nlv == None` (= `finite_source_nlv`, NOT the raw `nan`/`inf`) + `swing_nlv` key ABSENT.
  - **Pre-fix value:** with the existing code the non-finite NLV flows into `coherence_delta` /
    `account_equity_source_dollars` and `update_run_completed` → `ReconciliationRun.__post_init__`
    raises `ValueError` (the run FAILS) — i.e. today this is an unhandled latent gap on a non-finite
    NLV. **Post-fix value:** the run COMPLETES with `None` stamps. **Distinguishes** the finite-NLV
    normalization (the run completes-vs-fails on a non-finite NLV).

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
  complement of `undeclared_positions`); `has_declared_oof_position := len(declared_held) > 0`.
- `declared_mv_available` + `declared_oof_mv`: sum `marketValue` over `declared_held`. **MV
  normalization (Codex R1 MINOR 2 — cover non-numeric malformed payloads, not just `None`):** for each
  declared held position attempt `float(raw_mv)` inside a `try/except (TypeError, ValueError)`; if
  `raw_mv is None`, conversion fails, OR the result is not `math.isfinite(...)` → `declared_mv_available
  = False`. Else `declared_oof_mv = Σ float(raw_mv)`. (Mirrors the orphan pass MV handling at `:1427-1434`.)
- `swing_scope_active := has_declared_oof_position` — i.e. a declared position is actually held. This
  is the SOLE gate for recording the `equity_coherence` summary sub-object (Codex R2 MAJOR 2): the
  legacy path (`swing_scope_active == False`) leaves `summary_json` BYTE-IDENTICAL to today.
- `swing_nlv_computable := swing_scope_active and declared_mv_available and (finite_source_nlv is not
  None)`. When true: `swing_nlv = finite_source_nlv − declared_oof_mv`; assert `math.isfinite(swing_nlv)`
  (belt — both inputs already finite); the live delta `swing_coherence_delta = ledger_equity − swing_nlv`;
  the fire predicate uses `_cash_coherence_tolerance(swing_nlv)`.

**Wiring the gate via a single "evaluated target" (Codex R3 MAJOR 1 — the legacy both-flat path MUST
still fire when nothing is declared/held; `swing_nlv_computable` is `False` there, so the fire
predicate CANNOT require it).** Derive ONE evaluated `(eval_nlv, eval_delta, eval_basis)` per run:

| case | eval_nlv | eval_delta | eval_basis | fires? |
|---|---|---|---|---|
| `not swing_scope_active` (nothing declared/held) — the legacy path | `finite_source_nlv` | `ledger − finite_source_nlv` (= legacy `coherence_delta`) | `"net_liq"` | when `journal_flat AND broker_flat_swing AND finite_source_nlv is not None AND abs(eval_delta) > tol(eval_nlv)` (byte-identical to today — `broker_flat_swing == broker_flat` here) |
| `swing_scope_active AND swing_nlv_computable` — the swing-scoped path | `swing_nlv` | `ledger − swing_nlv` | `"net_liq_minus_declared_oof"` | when `journal_flat AND broker_flat_swing AND abs(eval_delta) > tol(eval_nlv)` |
| `swing_scope_active AND NOT swing_nlv_computable` — the C2 degrade | (none) | (none) | (degrade) | NEVER fires (C2); the legacy `coherence_delta` is still STAMPED to `equity_delta_dollars`, but NO discrepancy is emitted |

- Fire `equity_delta` only per the per-case predicate above (the swing-scoped tolerance uses
  `_cash_coherence_tolerance(eval_nlv)`). The emitted `actual_value_json` uses `eval_basis`'s shape:
  the legacy `{equity_dollars: finite_source_nlv, basis: "net_liq"}` on the legacy path, the
  `{swing_nlv, source_nlv: finite_source_nlv, declared_oof_mv, basis: "net_liq_minus_declared_oof"}`
  shape on the swing-scoped path (Codex R3 MAJOR 2).
- `account_equity_source_dollars = finite_source_nlv` (the raw broker NLV when finite, else `None` —
  same value as today on every real run; non-finite is the only behavior change, and it MUST be `None`
  not the raw `nan`/`inf`).
- `equity_delta_dollars = (ledger − swing_nlv)` when `swing_nlv_computable`, else the legacy
  `coherence_delta` (= `ledger − finite_source_nlv`, itself `None` when `finite_source_nlv is None`).
- **`summary_json` (Codex R2 MAJOR 2):** append the `equity_coherence` sub-object ONLY when
  `swing_scope_active` is True (a declared position is held) — this INCLUDES the C2 degrade case
  (declared held, MV missing → record `basis="net_liq"`, `swing_nlv` key ABSENT, to prove the
  attempt+degrade). The `equity_coherence.source_nlv` field ALWAYS uses `finite_source_nlv` (= `None`
  for `nan`/`inf`) — never the raw non-finite NLV (Codex R3 MINOR). When `swing_scope_active` is False
  (nothing declared/held), DO NOT add the key → `summary_json` stays byte-identical to the legacy path.

**Acceptance:** (a) records the swing-scoped delta ≈ 0 + raw `account_equity_source_dollars` + the
`equity_coherence` key; (c) suppresses on missing/malformed MV + records `equity_coherence`
(`basis="net_liq"`, degrade proven); non-finite `source_nlv` → `finite_source_nlv = None` → no fire +
`None` stamps (the `__post_init__` NaN/inf guard never trips on any stamped column); the legacy
(nothing-declared/held) path's `summary_json` is byte-identical (no `equity_coherence` key) — C3.

### Task 3 — C3 regression locks (nothing-declared/held byte-identical) (test (d))

**Purpose:** prove ZERO behavior change on the normal both-flat case (empty declared set OR no
declared position held). This guards against an over-eager generalization changing the common case.

**Files:** add lock assertions to `tests/trades/test_swing_nlv_coherence.py` (and/or extend the
existing `tests/trades/test_schwab_equity_coherence.py` — those are the canonical both-flat locks). No
new production code (Tasks 1+2 must already be byte-identical here by construction).

**Failing/lock test(s):**

- `test_nothing_declared_both_flat_byte_identical` (test (d) — C3 LOCK, stated as a lock, pre == post).
  Setup: empty declared set, journal flat, ZERO broker positions, a drifted `nlv` past tolerance.
  - **Assertion:** the `equity_delta` fires exactly as the legacy both-flat path
    (`actual_value_json.basis == "net_liq"`, NOT `"net_liq_minus_declared_oof"`);
    `equity_delta_dollars == ledger − source_nlv`; AND **`summary_json` has NO `equity_coherence` key**
    (Codex R2 MAJOR 2 — `swing_scope_active == False` → the legacy `summary_json` is byte-identical).
    This is a LOCK (pre == post) — its value is guarding against an over-eager generalization (a gate
    change OR an unconditional `summary_json` key) changing the common case.
- `test_declared_set_nonempty_but_not_held_byte_identical` (C3, second half). Setup:
  `out_of_framework=("SPCX",)` but SPCX NOT in `schwab_positions`, ZERO held positions, journal flat,
  drifted `nlv`.
  - **Assertion:** identical to the legacy both-flat path (`broker_flat_swing == broker_flat == True`,
    fires with `basis == "net_liq"`, `equity_delta_dollars == ledger − source_nlv`); **NO
    `equity_coherence` key in `summary_json`** (`swing_scope_active == False` — nothing held). LOCK
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
| (a) | coherent-while-holding → no fire, run row records swing-scoped delta ≈ 0 | Task 2 | suppressed (broker not flat); run row `equity_delta_dollars = ledger − source_nlv ≈ −Σ declared MV` (≈ −392.51, large) | no fire; run row `equity_delta_dollars ≈ 0` + `summary.equity_coherence.swing_nlv` recorded | the recorded swing-scoped delta (≈ 0 vs ≈ −392.51) |
| (b) | drift-while-holding → `equity_delta` FIRES (THE core value) | Task 1 | suppressed → NO fire (the bug — a real drift undetected) | fires (one `equity_delta` row, `basis="net_liq_minus_declared_oof"`) | fire vs no-fire |
| (c) | missing declared MV → suppress (C2) | Task 2 | suppressed anyway; legacy source-based delta recorded | still no fire (C2 guard); swing-scoped delta NOT recorded (`basis="net_liq"`, degrade path ran) | the degrade path: swing-scoped delta NOT computed/recorded |
| (d) | nothing declared/held → byte-identical (C3 LOCK) | Task 3 | fires legacy both-flat (evaluated NLV == `finite_source_nlv`, `basis="net_liq"`, NO `equity_coherence` summary key, legacy `actual_value_json` with no `swing_nlv` field) | identical | LOCK (pre == post) — guards over-eager generalization |
| (e) | undeclared position present → `broker_flat_swing=False` → no fire | Task 1 | suppressed (`broker_flat=False`) | suppressed (`broker_flat_swing=False`); orphan pass STILL banners the undeclared ticker, declared ticker carved out | the scoping (declared vs undeclared partition); FAILS a naive "subtract all positions" impl |

**Regression-test-arithmetic note (memory `feedback_regression_test_arithmetic`):** every numeric test
above states the ledger, NLV, declared MV, `swing_nlv`, the delta, and the tolerance so the assertion
is computed under BOTH the pre-fix path (legacy `broker_flat`/`source_nlv`) and the post-fix path
(`broker_flat_swing`/`swing_nlv`) — proving the test distinguishes (a test that passes under both
paths is worthless). Tests (d)/(e) are explicitly LOCKS (pre == post) with their distinguishing value
spelled out (over-eager-generalization guards), not silent.

---

## 5. C1–C5 + L2 traceability table (the QA checklist)

| condition | requirement | task(s) | test(s) | honored-on-disk anchor |
|---|---|---|---|---|
| **C1** (L2 same-snapshot) | declared MV from the SAME Schwab account payload as `source_nlv` | Task 2 | the §2.3 disk-verification (no new fetch); (a)/(b) read MV from the same `schwab_account.positions` | declared `Σ marketValue` reads `schwab_positions[].marketValue` (the SAME object `source_nlv` derives from); verified `get_account_details` → mapper extracts both from one `response` (`mappers.py:205-236`) |
| **C2** (L2 suppress-on-missing) | any declared MV `None`/malformed/non-finite → do NOT fire; also non-finite `source_nlv` → unavailable | Task 2 | (c) `test_missing_declared_mv_suppresses` (pinned to FALSE-FIRE a `None→0` impl) + `test_active_holding_nonfinite_nlv_degrades` (non-finite NLV → run completes with `None` stamps) | the `declared_mv_available` flag (a `float()` try/except + `math.isfinite` per declared MV) + the single `finite_source_nlv` normalization both feed `swing_nlv_computable`; mirrors the existing `source_nlv is not None` guard at `:1833`; the `finite_source_nlv` guard closes the mapper's unchecked-`float(nlv)` gap (R1 MAJOR 1 / R2 MAJOR 1) |
| **C3** (byte-identical) | empty declared set OR none held → `broker_flat_swing==broker_flat` AND the evaluated NLV == `finite_source_nlv` (no surfaced `swing_nlv` field/key on the legacy path) → zero behavior change | Task 3 | (d) both halves + `test_empty_declared_set_with_position_row_suppresses_like_legacy` (R1 MAJOR 3 — empty declared set + a held position row) + the 5 existing coherence locks | `broker_flat_swing` is defined over the SAME `schwab_positions` elements legacy `broker_flat` counts (NO qty filter) → reduces to `broker_flat` exactly; the evaluated NLV is `finite_source_nlv` and `summary_json` has NO `equity_coherence` key when the declared∩held set is empty |
| **C4** (no schema / no module / reuse `equity_delta`) | config-driven; NO migration; ONLY `schwab_reconciliation.py` step 8 | all | the tripwire self-cert §7; `_emit(discrepancy_type="equity_delta")` reused | NO new `swing/data/migrations/*`, NO new module; `swing_nlv`/`declared_oof_mv` recorded in `summary_json` + the discrepancy `actual_value_json` (no new column) |
| **C5** (drift-only) | NO positive "flat + coherent" surface | all | NO test asserts a positive surface; the check only emits on a drift | the `if` still emits ONLY when `abs(delta) > tolerance`; no new positive emit path |
| **L2** (no false equity signal, either direction) | no false coherence (a green hiding a real drift) NOR false drift | C1 + C2 are the guards | (a) no false drift; (b) catches a real drift; (c) no false coherence on missing data; (e) no false coherence on an undeclared position | RD QAs L2 against the shipped diff at the executing return; **RD sign-off is merge-blocking** |

---

## 6. Verification gates

1. **The §6 discriminating tests** (Tasks 1–3 above) — each states the pre-fix vs post-fix value.
2. **Full fast suite to GREEN before the Codex review** (recipe §2) — `python -m pytest -m "not slow"
   -q` from the worktree; fix any cross-cutting/global-invariant break to green so the review converges
   on a green diff. Then again at end-of-run (after review fixes).
3. **`ruff check swing/`** clean (no new violation in `swing/`).
4. **Operator live-witness (binding — mirrors SPCX §5.10):** on the live DB while holding declared
   SPCX, a real reconciliation run → the swing-NLV check RUNS (no false `equity_delta` when coherent);
   the run row carries the swing-scoped `equity_delta_dollars ≈ 0` (read off
   `reconciliation_runs` for the latest completed schwab run) + `summary_json.equity_coherence.swing_nlv`
   recorded; `account_equity_source_dollars` still shows the raw broker NLV. Optionally inject a known
   ledger drift (e.g. a synthetic cash-movement) to confirm test (b) FIRES live.
5. **Executing review stack** (per §8 below): `review-strong` (binding, repo-access, run to
   `NO_NEW_CRITICAL_MAJOR`, NEVER tier down) + `codex-auto-review` (gating, repo-access) + RD L2 QA +
   the operator live-witness. The orchestrator's merged-head no-false-green re-run is the final net.

---

## 7. Tripwire self-certification

- **`swing/trades` carve-out** → scoped to `swing/trades/schwab_reconciliation.py` step 8 ONLY (the
  gate condition + the `broker_flat_swing`/`swing_nlv` computation + the run-row recording + the
  `equity_delta` `actual_value_json` shape). The read-only `swing/trades` default returns after the arc.
- **NO schema, NO migration** — `swing_nlv`/`declared_oof_mv` recorded in the existing `summary_json`
  column + the discrepancy `actual_value_json`; the three `account_equity_*` / `equity_delta_dollars`
  columns are reused (one's value changes; no new column). NO `swing/data/migrations/*` file.
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
  MERGED HEAD (the binding no-false-green). The `summary_json` / `actual_value_json` shape change could
  surface a cross-arc fixture interaction (the 18-B.1×18-D lesson) — the merged-head re-run is the net.

---

## 9. Explicitly OUT of scope

- **Any positive "flat + coherent" confirmation surface** (C5 — operator decision; drift-only).
- **Any new discrepancy type** (reuse `equity_delta`).
- **Any schema change / migration / new module** (C4; `swing_nlv`/`declared_oof_mv` live in
  `summary_json` + the discrepancy `actual_value_json`).
- **Any measurement-chain touch** (L4 — §2.4 journals nothing: no `trades`/`fills` row, touches no
  measurement-chain module; the change is the equity-coherence computation only).
- **The SPCX out-of-framework carve-out itself** (already shipped at 18-H.6 / SPCX; this arc REUSES
  its `out_of_framework_set` + `out_of_framework_tickers` parameter, adds nothing to the registry).
- **The TOS-CSV reconciliation path** (`run_tos_reconciliation`) — a different source that does not run
  step 8; untouched.
- **The web equity tile** — reads `account_equity_snapshots`, not these columns; untouched.
