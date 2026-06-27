# 18-H.6 — Untracked broker position → a first-class `untracked_broker_position` discrepancy — CHARC dispatch brief

**Author:** CHARC. **Date:** 2026-06-16. **Phase 18, 18-H bug container.** Option **(a)**, operator-concurred 2026-06-16.

**TRIPWIRE — this brief IS the CHARC §3 architecture pass.** Crossings: **new schema** (migration **0031**, `discrepancy_type` CHECK enum widening, **v30→v31**) + a **`swing/trades` + `swing/data` carve-out** (the read-only-lock is lifted for exactly the files in §4). Conditions **C1–C5** below are binding.

## 1. The gap (CHARC-verified on disk)
The Schwab reconciliation is **journal-driven**: `run_schwab_reconciliation`'s position check loops the journal's `open_trades` and looks each up in the Schwab positions (`schwab_reconciliation.py:1241`; `:1243` `continue` when Schwab has no position for that journal ticker). It **never loops `schwab_positions`**, so a broker holding with no journal trade is never examined. The only orphan signal is the `orphan_broker_position` cash-warning (`:1610-1618`), gated on `journal_flat` — and the equity-coherence `equity_delta` only fires when **both** sides are flat (`:1619`). So with **any** open journal trade, an untracked broker position is **totally silent**: no discrepancy, and the ledger-derived dashboard equity drifts from the Schwab NLV by the orphan's unrealized P&L, unflagged. **Live instance:** the operator's 2 IPO shares bought outside the framework (2026-06-15) — invisible on the next Schwab pull.

## 2. The decision (option a + the 3 settled refinements)
A **first-class `untracked_broker_position` discrepancy** emitted by a new Schwab-driven orphan pass. Settled 2026-06-16: (1) the discrepancy **carries the equity impact** (broker qty + market value); (2) it **REPLACES** the journal-flat-only `orphan_broker_position` warning (strictly more informative; covers the orphan-with-open-trades case that bit us); (3) **V1 = visibility** — recomputing a *correct* `equity_delta` net of the orphan's value is **V2/separate**.

## 3. The build

### 3.1 New Schwab-driven orphan pass — `swing/trades/schwab_reconciliation.py`
A new section (place AFTER the journal-driven position-qty loop §5, independent of journal state): loop `schwab_positions`; for each position whose ticker has **no matching journal `open_trade`** (the reverse of `_find_position_qty` — reuse its ticker-matching/normalization for consistency), `_emit` an `untracked_broker_position` discrepancy:
- `ticker` = the broker ticker; `field_name` = `"broker_position"`; `trade_id` = NULL (no journal trade).
- `expected_value_json` = `{"journal_qty": 0}` (not in journal); `actual_value_json` = `{"qty": <broker_qty>, "market_value": <broker_mv>}` (verify the Schwab positions object shape for qty + market value; if MV is unavailable, carry qty + last price → MV, or document the field used).
- `delta_text` = the orphan summary (qty @ value not in journal). **ASCII only.**
- **Additive only** — the existing journal-driven checks (position_qty, stop, close-price, equity_delta, …) stay **byte-identical**.

### 3.2 The #11 enum widening — ONE atomic task (C1)
Add `'untracked_broker_position'` to **all** mirrors in a single commit; **grep all `swing/` first** for any hardcoded copy beyond these:
- migration **0031** schema CHECK (§3.3);
- `DISCREPANCY_TYPES` (`swing/trades/reconciliation.py:42`; bump the "(10 values)" comment → 11);
- `_DISCREPANCY_TYPES` (`swing/data/models.py:1050`) — the dataclass validator mirror (`:1246`);
- `MATERIAL_BY_TYPE` — add the `untracked_broker_position` → material entry (C5).
- The read-path/emit guards (`reconciliation.py:295`, `schwab_reconciliation.py:394`) reference the constant → auto-covered; **verify** they don't carry a separate hardcoded list.

### 3.3 The migration — `0031` (C2)
Widen the **live** `reconciliation_discrepancies` `discrepancy_type` CHECK to add `'untracked_broker_position'`. SQLite can't ALTER a CHECK → **table-rebuild** following the **0019 pattern** (`_new` table + copy + drop + rename), **preserving every column, index (incl. the `pending_ambiguity` partial index), and FK** of the CURRENT table (confirm the current definition on disk before writing the rebuild — it may have been rebuilt after 0019). `executescript` under explicit `BEGIN`/`COMMIT` + rollback (#9). **Backup-gate STRICT `pre_version == 30 AND target >= 31`** (copy the Phase-9 clause shape). Set `EXPECTED_SCHEMA_VERSION = 31`.

### 3.4 Replace the warning (refinement 2)
Remove the journal-flat `orphan_broker_position` cash-warning append (`:1610-1618`). The `equity_delta`-only-when-`journal_flat and broker_flat` suppression is **preserved structurally** (the `elif` already requires both flat — leave it). Update any existing test asserting the `orphan_broker_position` warning fires → assert the new discrepancy instead (grep for `orphan_broker_position`).

## 4. §3 binding conditions + carve-out scope
- **C1** — #11 atomicity: the CHECK + both Python constants + the validator + `MATERIAL_BY_TYPE` land in ONE commit (Task 0), with a grep-all-`swing/` sweep.
- **C2** — migration discipline: 0019 rebuild pattern, all columns/indexes/FKs preserved, #9 BEGIN/COMMIT, strict `pre==30` backup-gate, `EXPECTED_SCHEMA_VERSION=31`, read-path mappers accept the new value.
- **C3** — additive-only: the existing journal-driven checks are byte-identical; the carve-out ADDS the pass + widenings, it does NOT refactor existing recon logic.
- **C4** — sandbox gate: the new `_emit` writes domain rows ONLY under `environment=='production'` (mirror every other `_emit`; the discrepancy pass must sit inside the same production-gated path — verify).
- **C5** — `material_to_review = 1` for the new type.
- **Carve-out (CHARC-authorized):** exactly `swing/trades/schwab_reconciliation.py` + `swing/trades/reconciliation.py` + `swing/data/models.py` + the new `swing/data/migrations/0031_*.sql`. The read-only `swing/trades`+`swing/data` default returns after this arc.

## 5. Tests (distinguishing — `feedback_regression_test_arithmetic`)
- **New pass:** a broker position with NO journal trade → an `untracked_broker_position` discrepancy with qty + market_value (pre-fix: ZERO discrepancy — distinguishing); a broker position WITH a matching journal trade → no orphan discrepancy (only the existing qty check); an orphan present **alongside open journal trades** (the bug case) → the discrepancy fires (pre-fix: silent).
- **#11:** the new value passes the dataclass validator + a row with it inserts under the 0031 CHECK; a bogus type still raises.
- **Migration:** v30→v31 round-trip (the new value insertable post-migration; pre-existing discrepancy rows preserved; run-twice no-op; the strict backup-gate fires at `pre==30`).
- **Warning replacement:** the old `orphan_broker_position` warning no longer appends; the discrepancy fires in its place (journal-flat case).
- **Sandbox gate:** under `environment=='sandbox'`, the orphan pass writes NO domain row (audit/classify may still run per the existing pattern).

## 6. Gates
- **review-strong** (gpt-5.5/high, repo-access — binding) to convergence + **codex-auto-review** (repo-access, matched-HIGH — adopted gating-complementary; production + recon code). Save each round's response; verify Reviewer A ran at effort=high.
- **Operator MIGRATION live-witness** (v30→v31 on the live DB: `schema_version=31`, integrity ok, `reconciliation_discrepancies` intact + additive — the 18-C v30 discipline).
- **§5.10 BINDING operator RECON live-witness** — run the Schwab reconciliation on the operator's live system: the `untracked_broker_position` discrepancy **fires for the operator's actual IPO shares** (correct ticker, qty, market value), and a normally-tracked position does NOT false-orphan. A real orphan exists → this is the true net (byte-tests can't witness the live broker-vs-journal shape).
- Merged-head no-false-green fast suite + `ruff check swing/`.
- **No RD merge-block** (operational-correctness / broker-recon, NOT the research measurement core — RD released post-18-D).

## 7. Locks / return
- Carve-out scoped to the 4 files in §4; read-only default returns after. Sandbox gate (C4). #11 atomicity (C1). Conventional commits, **ZERO `Co-Authored-By`**, no `--no-verify`.
- The IMPLEMENTER reports to the ORCHESTRATOR in chat — never a director inbox; the ORCHESTRATOR posts the return to charc AFTER its QA.

**Cell:** `implementer-opus-high` (schema migration + locked-dir carve-out + the #11 atomicity is real-judgment work; bump to opus-max only if the table-rebuild/migration proves gnarlier than the 0019 precedent).
