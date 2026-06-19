# Implementation plan — `swing journal oof-buy` cash-coherence command (Phase-18 deferred follow-up #1)

**Status:** writing-plans deliverable (PLAN-ONLY — NO production code, NO tests committed). **Spec / settled design:** `docs/oof-buy-command-commissioning-brief.md` (commit `27a0347f`; the CHARC-verified §2 grounding + the CHARC §3 architecture pass [GO; ONE carve-out authorized; NO schema] + the §4 settled design contract). **Lane:** CHARC — a `swing/trades` carve-out scoped to the step-7 cash-movement matcher (additive/guard-only), plus a new `swing/cli.py` subcommand. **Author:** writing-plans implementer (`implementer-opus-xhigh`). **Date:** 2026-06-18.

The design is SETTLED by the brief — this plan grounds it on disk and lays out the TDD task breakdown + the discriminating tests with pre/post arithmetic; it does NOT re-open the design.

---

## 0. BLOCKING OPEN QUESTIONS for CHARC

**NONE.** Every brief §2 grounding fact + §4 design clause re-grounded clean on disk (`main` HEAD `caa57a50`). The authorized scope (the CLI subcommand + the one-branch step-7 matcher skip reusing the existing public `insert_cash`; NO schema, NO new module, NO new dependency) is sufficient to implement the full settled design — no schema, no second carve-out, no new module is required. The grounding turned up **four benign drift / strengthening OBSERVATIONS** (Appendix A) that make the tests STRONGER (notably the registry-guard MUST read `apply_overrides(cfg)`, not bare config — O1); none crosses a binding gate or the authorized scope, so none is a §0 blocker.

---

## 1. Overview + the settled design (restated)

**Problem (brief §1).** Swing cash spent to buy an out-of-framework (OOF) holding (e.g. the SPCX IPO) leaves the swing framework but is never captured on the swing ledger. The §2.4 swing-NLV arc subtracts the declared-OOF market value from the broker NLV on the **swing-NLV side** (`swing_nlv = finite_source_nlv - declared_oof_mv`), but the **ledger side** never records the OOF cash outflow → the ledger is overstated by the spent cash → `eval_delta = finite_ledger_equity - swing_nlv` drifts → `equity_delta` fires. The current manual workaround (`swing journal cash --withdraw <cost>`) itself fires a recurring `cash_movement_mismatch` (the live "id 72") because the Schwab counterpart is a `TRADE`, not a cash withdrawal — and a `TRADE`-reffed withdraw fails PASS-1 R9 type-validation (§2.3).

**Settled design (brief §4).** A new CLI subcommand, a sibling of `journal cash`:

```
swing journal oof-buy --ticker <SYM> --cost <DOLLARS> [--date YYYY-MM-DD]
```

It does exactly two things, both reusing existing public surfaces:

1. **Records a swing transfer-OUT** — `insert_cash(conn, CashMovement(date, kind="withdraw", amount=cost, ref=<OOF sentinel>, note=<audit string>))` (the existing public repo function `swing/data/repos/cash.py:9`). The `withdraw` reduces `finite_ledger_equity` by `cost` (via `current_equity` → `net_cash_movements`, `swing/trades/equity.py:30-31` `withdraw` is in `_CASH_SUB_KINDS`), fixing the ledger-side overstatement.
2. **Marks the row self-sourced** via a deterministic OOF sentinel `ref` (§3) so the step-7 matcher recognizes it and excludes it from the `cash_movement_mismatch` emit (§4 self-reconcile branch) — killing the recurring "id 72"-class false discrepancy.

Plus three guards the brief mandates:

- **Registry guard:** REJECT (clear `click.ClickException`) if `--ticker` is NOT in `cfg.reconciliation.out_of_framework_tickers` (read via `apply_overrides` — O1).
- **Sandbox gating:** under `cfg.integrations.schwab.environment != "production"` the domain write short-circuits (no `cash_movements` row written); echo an advisory only. Mirrors the canonical domain-row gate `swing/integrations/schwab/pipeline_steps.py:292`.
- **Idempotency:** a re-run with the same key is a clean no-op/error (never a double-record) via the partial unique index `ux_cash_ref`.

**Command control-flow ORDER (the Codex R2 MAJOR-2 fix — the sandbox short-circuit is WRITE-SCOPED, validation always runs first).** The CLI MUST execute its steps in this exact order so the sandbox gate never swallows validation:
1. `cfg = apply_overrides(ctx.obj["config"])` (materialize the registry + the env — O1).
2. `ticker = ticker.strip().upper()` then the **registry guard** (reject a non-OOF ticker → `ClickException`) — ALWAYS, regardless of env.
3. **ISO-date validation** of `--date` (reject → `ClickException`) — ALWAYS (mirror `journal_cash_cmd:1732-1744`).
4. The **SELECT-first idempotency check** (`find_by_ref(_build_oof_ref(ticker, date))` → already present → clean no-op message + return).
5. The **sandbox gate** — `if cfg.integrations.schwab.environment != "production": echo advisory + return` (NO write). This is the LAST gate BEFORE the write; it scopes the WRITE ONLY.
6. The `insert_cash(...)` domain write (production only) + the success echo.

This ordering guarantees a non-OOF ticker is REJECTED even under sandbox (validation precedes the write short-circuit) — the property SB1's new arm pins (§4).

**V1 scope:** BUY direction only (transfer-OUT). OOF SELLs (proceeds re-entering swing cash → transfer-IN) are an explicit V2 follow-up (§8).

**The both-sides-exclude property (the binding measurement claim, brief §2.4 + §5).** Because `declared_oof_mv` is summed from POSITIONS (`schwab_reconciliation.py:1911-1926`), NOT from cash_movements, the ledger transfer-out (`-cost`) and the NLV `declared_oof_mv` subtraction (`-current_MV`) are ORTHOGONAL. At purchase, `cost == MV` so `eval_delta == 0`; and as the OOF price moves LATER, BOTH sides exclude the OOF entirely, so `eval_delta STAYS 0`. No double-count; the root fix does NOT re-open the §2.4 drift.

---

## 2. Grounded code facts (re-grounded on disk 2026-06-18, worktree base `main` HEAD `caa57a50`)

All line numbers are from the worktree base. The executing implementer re-grounds before editing (line numbers drift).

### 2.1 The step-7 cash-movement matcher (the carve-out edit site) — `swing/trades/schwab_reconciliation.py`

Step 7 (`:1697-1825`) is a two-pass matcher over `journal_cash_in_period` (`:1692-1695`, journal cash_movements whose `date` is within the recon period):

- **PASS 1 (`:1717-1748`) — exact `transactionId`-in-`ref` reservation.** For each ref-bearing `cm`, it scans `schwab_transactions` for `str(tx.transaction_id) == cm.ref` (`:1723`). On an exact-ref hit it reserves the tx and value-validates: `kind_ok = tx.type in expected_types` (`:1737`), `sign_ok`, `amount_ok`; a clean match → `_ref_matched_cm_ids` (`:1745`), a value-drift match → `_ref_mismatch_cm_ids` (`:1747`).
- **PASS 2 (`:1750-1825`) — heuristic for rows not matched by exact ref.** Skips `_ref_matched_cm_ids` (`:1751`). A `_ref_mismatch_cm_ids` row force-breaks to the emit path (`:1768-1771`). Otherwise it heuristically matches on (kind→type, sign, ±4-day window, amount-tolerance) (`:1769-1790`); `match_idx is None` → emits `cash_movement_mismatch` (`:1804-1823`).

**Where an OOF sentinel-reffed `withdraw` row lands TODAY (the bug the carve-out fixes):**
- PASS 1: `str(tx.transaction_id) == "oof:..."` is FALSE for every Schwab tx (real `transaction_id`s are numeric — §3 collision proof), so the OOF row enters NEITHER `_ref_matched_cm_ids` NOR `_ref_mismatch_cm_ids`.
- PASS 2: the OOF row is not ref-matched, not ref-mismatch → it runs the heuristic; the OOF buy's Schwab counterpart is a `TRADE` (skipped at ingest, §2.2 — and `TRADE ∉ _SCHWAB_WITHDRAW_TYPES` so it could never heuristic-match a `withdraw` anyway) → `match_idx is None` → **emits `cash_movement_mismatch` every run** (the recurring false discrepancy).

**The carve-out (ONE additive branch).** At the TOP of the PASS-2 loop body — after the `_ref_matched_cm_ids` skip (`:1751`) and BEFORE the heuristic loop — add:

```python
if cm.ref and _is_oof_sentinel_ref(cm.ref):
    # Self-sourced OOF transfer-out (`swing journal oof-buy`): the swing
    # cash that bought an out-of-framework holding. Its Schwab counterpart
    # is a TRADE (skipped at ingest by design) so there is NO cash-side
    # source transaction to match -- it is self-sourced. Excluded from the
    # cash_movement_mismatch emit (treated as matched). ADDITIVE-ONLY: every
    # non-OOF row's match/emit path below is byte-unchanged.
    cash_counters["cash_oof_self_sourced_count"] += 1  # see O3 disposition
    continue
```

This `continue`s past BOTH the heuristic match loop AND the `_emit(...)` — the OOF row never emits `cash_movement_mismatch`. Non-OOF rows (`_is_oof_sentinel_ref` returns False) fall through to the byte-unchanged existing code. **It does NOT touch PASS 1** (an OOF ref never ref-matches there, so PASS 1 already has no effect on it; one branch in PASS 2 fully covers the case → satisfies the brief's "one-branch OOF-origin-marker skip").

> **O3 (Appendix A) — the counter line is OPTIONAL.** A `cash_counters[...]` increment makes the skip auditable (the run record shows the OOF rows were recognized), consistent with the existing `cash_pending_suppressed_count` audit at `:1802`. If the executing implementer prefers strict minimalism (no new counter key), the branch is just `continue` with the comment. EITHER is additive/guard-only and byte-unchanged for non-OOF rows. If the counter is added, the cash-summary envelope (`:1827`) and any `_empty_cash_counters()` initializer (`schwab_reconciliation.py`, the `cc` dict) must include the new key with a 0 default so the envelope is shape-stable — verify at executing time. **The plan does NOT require the counter; it is a documented option, not a second carve-out.** The self-reconcile TEST (§4 test S1) asserts the row is SKIPPED-AS-SELF-SOURCED via the ABSENCE of a `cash_movement_mismatch` row for the OOF `cm.id` (not via the counter), so the test is counter-independent.

### 2.2 The ingest TRADE-skip (why there is no Schwab cash counterpart) — `swing/trades/schwab_reconciliation.py:991` + `:113` + `:180`

- `_CASH_SKIP_TX_TYPES = frozenset({"TRADE", "RECEIVE_AND_DELIVER"})` at `:113` ("Skip BY DESIGN — trade cash already enters the ledger via realized P&L").
- The ingest classifier skips them: `_classify_cash_transaction` returns `action="skip"` when `ttype in _CASH_SKIP_TX_TYPES` (`:180`); the ingest loop `continue`s on a `TRADE` (`:991`, incrementing `cash_skipped_trade_count`).

So an OOF buy's `TRADE` transaction is NEVER auto-ingested into the journal as a cash_movement, and NEVER offered as a step-7 cash match candidate. The OOF row genuinely has no Schwab cash counterpart — confirming it is correctly classed self-sourced (NOT a hidden true mismatch).

### 2.3 Self-reconcile is NOT free — the R9 type-validation proof — `swing/trades/schwab_reconciliation.py:1737` + `:1768-1771`

The brief §2 third bullet (a CHARC correction of a prior FALSE "self-reconcile is free" premise) is confirmed on disk: an auto-created `withdraw` cash_movement reffed to the `TRADE` `transaction_id` would, in PASS 1, hit `str(tx.transaction_id) == cm.ref` → reserve the tx → value-validate with `kind_ok = tx.type in expected_types` (`:1737`) where `expected_types = _SCHWAB_WITHDRAW_TYPES = {ACH_DISBURSEMENT, WIRE_OUT, CASH_DISBURSEMENT, ELECTRONIC_FUND}` (`:92-94`, via `_CASH_KIND_TO_SCHWAB_TYPES["withdraw"]` `:126`). `"TRADE" ∉` that set → `kind_ok = False` → the row lands in `_ref_mismatch_cm_ids` (`:1747`) → PASS 2 force-breaks to the emit path (`:1768-1771`) → `cash_movement_mismatch` fires EVERY run.

**Design consequence (already in the settled design):** this is precisely WHY the OOF sentinel ref must NOT be a real `transaction_id` and WHY the matcher needs an explicit self-sourced branch. The OOF sentinel ref (`oof:...`, §3) never ref-matches in PASS 1 → never enters `_ref_mismatch_cm_ids` → the §2.1 PASS-2-top branch handles it cleanly. (An alternate "ref it to the TRADE txn_id" design would FAIL — this proves the settled design is the correct one.)

### 2.4 The §2.4 composition arithmetic (the orthogonality proof) — `swing/trades/schwab_reconciliation.py`

- `ledger_equity = current_equity(starting_equity=starting_equity, exits=list_all_exitshape_via_fills(conn), cash_movements=list_cash(conn))` (`:1854-1858`). `current_equity = starting_equity + realized + net_cash_movements` (`equity.py:39-45`); `net_cash_movements` SUBTRACTS `withdraw` (`equity.py:22,30-31` — `withdraw ∈ _CASH_SUB_KINDS`). So an OOF `withdraw` of `cost` reduces `ledger_equity` (and `finite_ledger_equity`, `:1870-1872`) by exactly `cost`.
- `declared_oof_mv` summed from POSITIONS (`:1911-1926`, over `declared_held` — the held positions whose symbol is in `out_of_framework_set`), NOT from cash_movements.
- `swing_nlv = finite_source_nlv - declared_oof_mv` (`:1939`), basis `_SWING_COHERENCE_BASIS = "net_liq_minus_declared_oof"` (`:205`, `:1958`).
- `eval_delta = finite_ledger_equity - swing_nlv` (`:1957`).
- Fire condition: `journal_flat and broker_flat_swing and eval_nlv is not None and eval_delta is not None and abs(eval_delta) > _cash_coherence_tolerance(eval_nlv)` (`:1971-1977`); tolerance `= max(5.00, 0.005 * |NLV|)` (`_cash_coherence_tolerance`, `:208-211`).

**Orthogonality (the both-sides-exclude property).** Let `L0 = starting_equity + realized` (the pre-OOF ledger, no OOF cash row). Let `N = finite_source_nlv` (broker NLV including the OOF position at current MV `M`). With ONE declared held OOF position of market value `M`:
- `declared_oof_mv = M`, so `swing_nlv = N - M`.
- **PRE-fix (no OOF withdraw row):** `finite_ledger_equity = L0`, so `eval_delta_pre = L0 - (N - M) = L0 - N + M`. At purchase the broker NLV `N` already reflects the OOF buy (cash converted to the position at cost `C`, with `M == C` at purchase): `N` = (ledger value of everything else) `= L0` PLUS the OOF position `M` MINUS the spent cash `C` ... but the broker NLV is the SAME total assets either way (cash `C` became position worth `M==C`), so `N = L0 - C + M = L0` at purchase (since `M == C`). Then `eval_delta_pre = L0 - N + M = L0 - L0 + M = M = C`. **The pre-fix drift equals the OOF cost `C`.** (After a price move to `M' != C`: `N' = L0 - C + M'`, `eval_delta_pre = L0 - N' + M' = C - M' + M' = C` — still `C`; the drift is the un-recorded spent cash, constant at `C`.)
- **POST-fix (OOF withdraw row of amount `C`):** `finite_ledger_equity = L0 - C`, so `eval_delta_post = (L0 - C) - (N - M)`. At purchase `N = L0`, `M = C` → `eval_delta_post = L0 - C - L0 + C = 0`. After a price move `M' != C`: `N' = L0 - C + M'` → `eval_delta_post = (L0 - C) - (N' - M') = (L0 - C) - (L0 - C + M' - M') = (L0 - C) - (L0 - C) = 0`. **`eval_delta_post == 0` at purchase AND after any later price move.**

This is the binding distinguisher: `eval_delta_pre = C` (fires when `C > tolerance`) vs `eval_delta_post = 0` (never fires). The executing test (§4 C1) computes both under the real emitter and asserts they DIFFER (pre fires, post is 0).

### 2.5 `cash_movements` schema (migration 0029) — `swing/data/migrations/0029_cash_reconciliation.sql`

- `cash_movements (id, date TEXT [ISO-GLOB CHECK], kind TEXT CHECK IN ('deposit','withdraw','interest','dividend','fee'), amount REAL CHECK >= 0, ref TEXT, note TEXT)` (`:14-21`). `kind="withdraw"` and a free-form `ref` are both schema-legal.
- `CREATE UNIQUE INDEX ux_cash_ref ON cash_movements(ref) WHERE ref IS NOT NULL` (`:56`) — the partial unique index that gives the OOF sentinel ref its idempotency (a second insert with the same ref raises `sqlite3.IntegrityError`).
- `ref` has NO format CHECK → an `oof:`-prefixed sentinel is schema-legal.

### 2.6 The model + the repo (the surfaces the command reuses) — `swing/data/models.py:384` + `swing/data/repos/cash.py`

- `CashMovement(id, date, kind, amount, ref, note)` (`models.py:384-390`). `__post_init__` (`:392-414`) validates `kind` against `_CASH_MOVEMENT_KINDS` + `date` ISO-shape; it does NOT validate `amount >= 0` (DB CHECK only) and does NOT validate `ref` shape → an OOF sentinel ref passes the model.
- `insert_cash(conn, m)` (`cash.py:9-17`): `INSERT INTO cash_movements (...) VALUES (...)`; returns `lastrowid`. Docstring "Caller wraps in `with conn:`" — it does NOT open its own tx and does NOT catch `IntegrityError`. So a duplicate `ref` raises `sqlite3.IntegrityError` out of `insert_cash` → the CLI must catch it for the idempotency path (§3, §4 test I1).
- `find_by_ref(conn, ref)` (`cash.py:30-37`): the ref-exact lookup; returns the existing `CashMovement` or `None`. The idempotency ladder uses this (SELECT-first) so a re-run is a clean no-op message rather than an `IntegrityError` traceback.

### 2.7 The `journal cash` CLI to mirror — `swing/cli.py:1700-1755` + `@main.group("journal")` at `:1602`

`journal_cash_cmd` (`:1710`) is the structural mirror: it reads `cfg = ctx.obj["config"]` (`:1746`), `connect(cfg.paths.db_path)` (`:1747`), `with conn: insert_cash(...)` (`:1749-1752`), echoes a confirmation (`:1755`), and validates the ISO date with a clean `ClickException` (`:1732-1744`). The new `oof-buy` command registers as a third sibling under `@journal_group.command("oof-buy")`. **There is NO existing `oof-buy` command** (grep-confirmed) — purely additive.

> **O1 (the load-bearing divergence from the mirror): the registry guard MUST use `apply_overrides`, NOT the bare `ctx.obj["config"]`.** `ctx.obj["config"] = load_config(...)` (`cli.py:212`) is the BASE (tracked-TOML) config; `out_of_framework_tickers` lives ONLY in user-config.toml overrides and is materialized by `apply_overrides` (`config_overrides.py:159-182`). `journal_cash_cmd` reads bare config because it never needs the registry; the OOF command DOES (for the registry guard AND the sandbox-env read). The canonical pattern is `cfg = apply_overrides(ctx.obj["config"])` then `getattr(getattr(cfg, "reconciliation", None), "out_of_framework_tickers", ()) or ()` (the exact shape at `cli_schwab.py:1037-1043`) and `cfg.integrations.schwab.environment` for the sandbox gate. **The membership test compares the UPPER-CASED `--ticker` (`ticker.strip().upper()`) against the [already-upper] registry** (the Codex R1 fix; §3) — case-insensitive at the user boundary. **If the executing implementer mirrors `journal_cash_cmd`'s bare-config read, the registry guard reads an EMPTY tuple on the live system and rejects EVERY ticker** (a false-negative that the registry-guard test below catches only if it seeds the OOF ticker via the OVERRIDES path — §4 test R1 mandates that). This is the 18-E "default-arg filter diverges from production config" gotcha family.

### 2.8 The sandbox-gate precedent — `swing/integrations/schwab/pipeline_steps.py:292` + `swing/trades/exit_auto_fill.py:389`

The canonical domain-row gate: `if environment != "production": log.info("...sandbox short-circuit (no domain write)"); return <audit-only result>` (`pipeline_steps.py:292-302`). For the OOF command there is NO Schwab API call (it is a pure manual journal entry), so "audit-only" reduces to "write NO `cash_movements` row + echo an advisory" (there is no `schwab_api_calls`-style audit table for a manual cash entry — verify at executing time; §4 test SB1 asserts zero `cash_movements` rows under sandbox). The gate reads `cfg.integrations.schwab.environment` from the `apply_overrides`-materialized cfg (the same cfg the registry guard uses). **The gate is WRITE-SCOPED and is the LAST step before `insert_cash` (the §1 control-flow order, the Codex R2 MAJOR-2 fix): the registry guard + the ISO-date validation + the idempotency SELECT ALL run BEFORE it, so a non-OOF ticker is rejected even under sandbox** (the short-circuit never pre-empts validation — SB1 pins this).

### 2.9 The registry config surface — `swing/config.py:281-300` + `config_overrides.py:159-182`

`cfg.reconciliation.out_of_framework_tickers: tuple[str, ...]` (`config.py:291`), normalized to upper-case via `_normalize_out_of_framework_tickers` (`config.py:244-270`, `:299-300`). The live value is `("SPCX",)`. `apply_overrides` DEFENSIVELY degrades a malformed user-config value to the base value (`config_overrides.py:166-182`) — so the command never crashes on a malformed registry; the guard just rejects (the safe direction).

---

## 3. The OOF sentinel `ref` format (a writing-plans detail per brief §4) + the collision proof

**Format (canonical):**

```
oof:<TICKER>:<YYYY-MM-DD>
```

- `<TICKER>` = the UPPER-CASED, registry-normalized ticker (e.g. `SPCX`).
- `<YYYY-MM-DD>` = the OOF buy date (the resolved `--date`, defaulting to today).
- Example: `oof:SPCX:2026-06-18`.

**Ticker normalization (the Codex R1 MAJOR fix — load-bearing).** `cfg.reconciliation.out_of_framework_tickers` is stored UPPER-CASED (`_normalize_out_of_framework_tickers`, `config.py:244-270`, does `.strip().upper()`). The CLI MUST upper-case `--ticker` ONCE at the boundary — `ticker = ticker.strip().upper()` — BEFORE BOTH (a) the registry-membership lookup AND (b) the ref construction. Without this, a user passing `spcx` would be (a) FALSELY REJECTED by the registry guard (`"spcx" in ("SPCX",)` is False) AND (b) produce a non-canonical ref `oof:spcx:...` that does NOT dedup against the canonical `oof:SPCX:...` (idempotency silently broken across case). The normalized `ticker` is the SINGLE value threaded through the guard, the ref, and the audit note — so the command is case-INSENSITIVE at the user boundary and the ref is always canonical. `_build_oof_ref(ticker, date)` ALSO upper-cases its ticker argument (belt: a deterministic ref regardless of the caller's case), and the §4 R1 + I1 tests exercise lower/mixed-case inputs (the R1 finding's missing coverage).

**Why this shape (each property maps to a brief requirement):**

1. **Deterministic + recognizable (origin marker for the §2.1 matcher branch).** `_is_oof_sentinel_ref(ref)` is a pure predicate: `ref.startswith("oof:")`. (Implementer may tighten to a full regex `^oof:[A-Z0-9.\-]+:\d{4}-\d{2}-\d{2}$` for robustness; the load-bearing property is the `oof:` PREFIX, which is what the matcher branch keys on — and which a numeric `transaction_id` can never produce.) `_build_oof_ref(ticker, date)` UPPER-CASES its ticker argument (`f"oof:{ticker.strip().upper()}:{date}"`) so the ref is canonical regardless of caller case (the Codex R1 fix). A SINGLE source-of-truth helper (`_OOF_REF_PREFIX = "oof:"` + `_is_oof_sentinel_ref` + the `_build_oof_ref(ticker, date)` constructor) is defined ONCE and imported by BOTH the CLI (to build the ref) and the matcher (to recognize it) — never two hand-duplicated string literals (the Arc-6 shared-predicate lesson: two impls WILL diverge). Home: the constructor + predicate live in `swing/trades/schwab_reconciliation.py` (next to the matcher) and are imported by `swing/cli.py`; OR a thin shared helper — the executing implementer picks the import direction that avoids a cycle (the matcher module already imports broadly; the CLI imports from it lazily, the established cli.py pattern). NO new module/package (brief §3 tripwire).

2. **Idempotent via `ux_cash_ref`.** The ref is a deterministic function of `(ticker, date)`, so a second `oof-buy SPCX --cost ... --date 2026-06-18` produces the IDENTICAL ref → the partial unique index `ux_cash_ref` rejects the duplicate. The CLI's idempotency ladder is SELECT-first (`find_by_ref` before `insert_cash`) so the operator sees a clean "already recorded" message, not an `IntegrityError` traceback (§4 test I1). (Belt: even if a TOCTOU race slipped past the SELECT, the `INSERT` still raises `IntegrityError`, which the CLI catches and reports as the same no-op — defense in depth.)

3. **Can NEVER collide with a real Schwab `transaction_id` (the brief's hard requirement).** A Schwab `transaction_id` is a NUMERIC string (`SchwabTransactionResponse.transaction_id: str`, `models.py:357`; the live/migration example `"115520131470"` is a 12-digit numeric string; `str(tx.transaction_id)` of a numeric id is `[0-9]+`). The OOF sentinel ALWAYS contains the literal substring `"oof:"` (lowercase letters + a colon) at position 0, which `[0-9]+` can never contain. Therefore:
   - **The step-7 PASS-1 ref-exact match `str(tx.transaction_id) == cm.ref` can NEVER be True for an OOF ref** → an OOF row never enters `_ref_matched_cm_ids`/`_ref_mismatch_cm_ids`, never reserves a tx, never force-emits.
   - **The §2.1 OOF-skip branch `_is_oof_sentinel_ref(cm.ref)` can NEVER be True for a real `transaction_id`** (a numeric string lacks the `oof:` prefix) → a genuine ref-backed manual cash_movement is NEVER skipped as OOF.

   These two are MUTUALLY EXCLUSIVE by construction (numeric vs `oof:`-prefixed), and §4 test C2 is the discriminating test that pins BOTH directions (a synthetic numeric `transaction_id` equal to the digits of an OOF ref is still NOT matched by the OOF branch, and a real OOF ref is never ref-matched in PASS 1).

> **O4 (Appendix A) — `ticker` and `date` are constrained at the CLI boundary, so the ref is well-formed.** The ticker is registry-validated (upper-case, in `out_of_framework_tickers`) before the ref is built, and the date is ISO-validated (mirroring `journal_cash_cmd:1732-1744`). So the ref's `<TICKER>` segment is `[A-Z0-9.\-]+` and the `<YYYY-MM-DD>` segment is a valid ISO date — the ref can never contain a stray `:` from the ticker that would confuse a future parser (tickers do not contain colons). The colon delimiter is safe.

---

## 4. Per-task breakdown (TDD-first)

**Task structure (executing phase).** Three production touches, each red→green→commit:
- **Task 1** — the OOF sentinel ref helper (`_OOF_REF_PREFIX`, `_build_oof_ref`, `_is_oof_sentinel_ref`) — a pure, self-contained unit (tested by C2's collision discriminator + a unit round-trip).
- **Task 2** — the step-7 matcher self-reconcile branch (the `swing/trades` carve-out) — tested by S1 (self-reconcile), C3 (additive/guard-only byte-unchanged), and the C1 composition test's post-fix arm.
- **Task 3** — the `swing journal oof-buy` CLI subcommand (registry guard + sandbox gate + idempotency ladder + the `insert_cash` write) — tested by R1, I1, SB1, and the end-to-end leg of C1.

(The executing implementer MAY reorder so the matcher branch [Task 2] lands before the CLI [Task 3], since C1's composition test exercises both. The order above is the dependency order: the ref helper is the shared primitive.)

Each test states its PRE/POST arithmetic so it provably DISTINGUISHES (a test green under both pre-fix and post-fix code is worthless — memory `feedback_regression_test_arithmetic`). Tests are built from the REAL emitter path (`run_schwab_reconciliation` end-to-end and the real `swing journal oof-buy` CLI via `CliRunner`), NEVER values hand-built to satisfy the premise (memory `feedback_verify_premise_arithmetic_vs_live`). Test fixtures mirror `tests/trades/` recon fixtures (a synthetic `_SchwabAccount` / positions / transactions; `out_of_framework_tickers=("SPCX",)`).

### Test C1 — the BINDING composition test (RD, MERGE-BLOCKING measurement artifact)

**Intent (brief §5):** an OOF buy at cost `C` → after `oof-buy`, `eval_delta == 0` at `cost == MV`; AND after a LATER OOF price move, `eval_delta` STILL `== 0` (the both-sides-exclude property). PRE-fix (no transfer-out): the ledger is overstated by `C` → drift fires (`> tolerance`).

**Fixture (real-derived; §2.4 arithmetic):**
- `out_of_framework_tickers=("SPCX",)`.
- `schwab_account.positions = [{"instrument": {"symbol": "SPCX", "type": "EQUITY"}, "longQuantity": <q>, "marketValue": M}]` (ONE declared held OOF position → `swing_scope_active=True`, `declared_held` non-empty, `broker_flat_swing=True` since the only position is declared, `declared_oof_mv = M`, `declared_mv_available=True`).
- No open trades → `journal_flat=True`.
- `starting_equity = L0` read from the test config (`cfg.account.starting_equity`); no other cash movements pre-OOF, no exits → the pre-OOF ledger is `L0`.
- Broker NLV `N` set to the at-purchase identity `N = L0` (cash `C` became the OOF position worth `M == C`; total assets unchanged). Choose `C = M` comfortably above the tolerance band: with `swing_nlv = N - M = L0 - C` and `tolerance = max(5.00, 0.005*|L0 - C|)`, pick `C` (e.g. `C = M = 500` against a four-figure `L0`) so `C > tolerance` (single-to-low-tens of dollars). **The test COMPUTES the actual tolerance from the resolved `swing_nlv` and asserts `abs(eval_delta_pre) > tol` AND `eval_delta_post == 0` (within float epsilon).**

**Assertions + pre/post arithmetic (per §2.4):**

1. **Pre-fix (no OOF withdraw row).** Run `run_schwab_reconciliation(...)` with the fixture and NO OOF cash row. `finite_ledger_equity = L0`, `swing_nlv = N - M = L0 - C`, `eval_delta_pre = L0 - (L0 - C) = C`. With `C > tol` → `fired == True` and EXACTLY ONE `equity_delta` row exists, whose `actual_value_json` carries `"basis": "net_liq_minus_declared_oof"` (PROVES the swing-scoped §2.4 path — guards against a fixture that degrades to the legacy `net_liq` basis or to a no-fire). Assert the fired delta text reflects `C`. **This is the PRE state.**
2. **Post-fix (after `oof-buy`).** Insert the OOF withdraw via the production path — the `swing journal oof-buy --ticker SPCX --cost C --date <d>` CLI (`CliRunner`, env=production) — OR, for a unit-focused matcher test, `insert_cash(CashMovement(kind="withdraw", amount=C, ref=_build_oof_ref("SPCX", d)))`. Re-run `run_schwab_reconciliation(...)`. `finite_ledger_equity = L0 - C`, `swing_nlv = L0 - C`, `eval_delta_post = (L0 - C) - (L0 - C) = 0`. Assert: ZERO `equity_delta` rows fired (`abs(0) <= tol`) AND the swing-scoped coherent LOG path was taken (or simply assert no `equity_delta` row + the run completed). **This is the POST state.**
3. **The later-price-move arm (the both-sides-exclude property).** Keep the OOF withdraw row (amount `C`). Re-run with the OOF position re-priced to `M' != C` (e.g. `M' = 750`), so the broker NLV becomes `N' = L0 - C + M'`. `swing_nlv' = N' - M' = L0 - C`, `eval_delta = (L0 - C) - (L0 - C) = 0`. Assert: STILL ZERO `equity_delta` fired. **PROVES the both-sides-exclude property: the ledger transfer-out is orthogonal to the NLV `declared_oof_mv` subtraction; the coherence holds as the OOF price moves.**

**Distinguishes:** assertion 1 fires (`eval_delta = C > tol`) under pre-fix; assertions 2+3 are 0 under post-fix. The two states DIFFER. (Computed under both paths; not a both-paths-pass test.) The basis assertion + the fired-count assertion ensure a non-firing / wrong-basis / degraded fixture cannot vacuously pass. The tolerance is computed from the RESOLVED ledger, not assumed (memory `feedback_verify_premise_arithmetic_vs_live`).

### Test S1 — the self-reconcile test (the matcher carve-out distinguisher)

**Intent (brief §5):** across a reconciliation run an OOF-marked cash_movement does NOT fire `cash_movement_mismatch`, asserted as SKIPPED-AS-SELF-SOURCED (the OOF row is recognized + excluded) — the test FAILS if the matcher branch is absent (not merely "some row matched").

**Fixture (real-derived; the Codex R2 MAJOR-1 isolation is LOAD-BEARING):**
- A journal `cash_movements` row: `kind="withdraw"`, `amount=C`, `ref=_build_oof_ref("SPCX", d)`, `date=d` within the recon period. Insert via `insert_cash` (the production writer; the ref is well-formed, no barrier rejects it).
- `schwab_transactions`: **the fixture MUST contain NO withdraw-typed Schwab transaction** (`ACH_DISBURSEMENT` / `WIRE_OUT` / `CASH_DISBURSEMENT` / `ELECTRONIC_FUND` — i.e. NOTHING in `_SCHWAB_WITHDRAW_TYPES`) within the ±4-day window at amount ~`C`. If such a counterpart existed, the OOF `withdraw` row would HEURISTIC-MATCH it in PASS 2 EVEN WITHOUT the branch → no emit → the test would pass pre-fix (the both-paths-pass risk Codex flagged). The ONLY transactions in the fixture are: (i) the ingest-skipped `TRADE` — `SchwabTransactionResponse(transaction_id="115520131470", type="TRADE", net_amount=-C, transaction_date=d, ...)` — which is NOT a step-7 candidate (it is in `_CASH_SKIP_TX_TYPES` AND `"TRADE" ∉ _SCHWAB_WITHDRAW_TYPES`); and OPTIONALLY (ii) an UNRELATED matched `deposit` (positive `net_amount`, an `ACH_RECEIPT`/`WIRE_IN`) so the run is not empty — a positive-sign deposit CANNOT match a `withdraw` (the sign gate `:1776-1780` rejects it). **By construction the OOF row has NO heuristic counterpart.**
- `out_of_framework_tickers=("SPCX",)`.

**Assertions + pre/post arithmetic:**
- **Post-fix:** the OOF row's `cm.id` has NO `cash_movement_mismatch` discrepancy row (`SELECT ... WHERE discrepancy_type='cash_movement_mismatch' AND cash_movement_id = <oof cm.id>` → empty). Assert SKIPPED-AS-SELF-SOURCED by the ABSENCE of the emit FOR THAT cm.id (not by a generic "no mismatches" — an unrelated mismatch may legitimately exist; scope the assertion to the OOF `cm.id`).
- **Pre-fix arithmetic (proves the test fails without the branch):** without the §2.1 branch, the OOF row is not ref-matched (PASS 1: `oof:...` != numeric txn_id), not ref-mismatch, runs the PASS-2 heuristic, and — BECAUSE the fixture provably has no withdraw-typed counterpart in window (the isolation above) — finds `match_idx is None` → `_emit(cash_movement_mismatch, cash_movement_id=<oof cm.id>)` (`:1804`). So pre-fix there IS a `cash_movement_mismatch` row for the OOF `cm.id`; the assertion FAILS. Post-fix the branch `continue`s before the emit → no row; the assertion PASSES.
- **The branch-disabled belt (the cleanest distinguisher — REQUIRED):** run the SAME fixture through the matcher with the OOF branch FORCED INERT (monkeypatch `_is_oof_sentinel_ref` to return `False`, OR a parametrize that toggles the branch) and assert the emit DOES fire for the OOF `cm.id`; then with the branch ACTIVE assert it does NOT. The emit FLIPPING on the single boolean (branch on vs off, identical fixture) directly proves the branch is load-bearing — eliminating any residual both-paths-pass risk. (If a monkeypatch of the predicate is awkward across the import boundary, the equivalent is asserting the pre-edit emit-set against the post-edit emit-set for the SAME fixture, captured deterministically.)
- **Distinguishes:** pre-fix (or branch-disabled) emits for the OOF cm.id; post-fix (branch active) does not. The assertion is scoped to the OOF cm.id so it cannot vacuously pass on "some other row matched," and the fixture isolation + the branch-toggle belt close the both-paths-pass hole.

### Test C3 — the additive/guard-only proof (every non-OOF row byte-unchanged)

**Intent (brief §5):** a discriminating test that EVERY non-OOF cash_movement's match/emit path is byte-unchanged by the new branch.

**Fixture:** a run with a MIX of non-OOF cash_movements exercising each step-7 outcome class:
- (a) a ref-backed clean match (`ref = str(tx.transaction_id)`, value-valid) → `_ref_matched_cm_ids` → no emit.
- (b) a ref-backed value-drift (`ref = str(tx.transaction_id)`, wrong amount) → `_ref_mismatch_cm_ids` → force-emit `cash_movement_mismatch`.
- (c) a ref-less heuristic match (matching date/amount/kind/sign Schwab tx) → matched → no emit.
- (d) a ref-less no-counterpart row → `match_idx is None` → emit `cash_movement_mismatch`.

**Assertions + pre/post arithmetic:** the set of `cash_movement_mismatch` discrepancies emitted (and the matched/unmatched disposition of each cm.id) is IDENTICAL whether or not the §2.1 branch is present — because `_is_oof_sentinel_ref` returns False for every ref in (a)-(d) (none is `oof:`-prefixed) → the branch's `continue` never fires for them → they flow the byte-unchanged existing code. **Pre==post for non-OOF rows (the LOCK).** The discriminating value: the test seeds NO OOF row, so the new branch is provably inert; assert the emit set equals the pre-edit emit set (captured by RUNNING the assertion against the deterministic fixture). A non-vacuity guard: at least (b) and (d) MUST emit (so the test proves the emit path still works), and (a)+(c) MUST NOT emit (so it proves matches are preserved).

> This C3 lock is the analog of the equity-delta plan's "unrelated type still dispatches" lock — it proves the carve-out is truly additive. It is NOT the load-bearing pre/post distinguisher for the FIX (that is S1); it locks SCOPE.

### Test C2 — the OOF-ref collision discriminator (Task 1 unit + matcher boundary)

**Intent (§3 collision proof):** a real Schwab `transaction_id` can NEVER be matched by the OOF-skip branch, AND an OOF ref can NEVER ref-match a real `transaction_id` in PASS 1.

**Assertions:**
- **Unit (Task 1):** `_is_oof_sentinel_ref("oof:SPCX:2026-06-18") is True`; `_is_oof_sentinel_ref("115520131470") is False`; `_is_oof_sentinel_ref(str(<any numeric>)) is False`; `_build_oof_ref("SPCX", "2026-06-18") == "oof:SPCX:2026-06-18"` (round-trip: `_is_oof_sentinel_ref(_build_oof_ref(...)) is True`). Edge: `_is_oof_sentinel_ref(None)` / `""` → False (the matcher guards `cm.ref and _is_oof_sentinel_ref(cm.ref)`).
- **Matcher boundary (a discriminating fixture):** a run with (i) an OOF row `ref="oof:SPCX:<d>"` AND (ii) a Schwab `TRADE` whose `transaction_id` is the DIGITS-only string `"<...>"` (a numeric id that could superficially resemble the OOF date digits). Assert the OOF row is skipped-as-self-sourced (via S1's mechanism) AND the numeric `transaction_id` tx is NOT consumed by the OOF row (PASS 1 never ref-matches `oof:...` to a number). Conversely, a separate NON-OOF ref-backed row with `ref = str(tx.transaction_id)` (numeric) ref-matches in PASS 1 as today and is NOT caught by the OOF branch.
- **Distinguishes:** the predicate returns different booleans for the two ref shapes; the matcher consumes/skips them on different paths. A buggy predicate (e.g. `ref in (...)` or a substring match that catches a numeric id) would flip an assertion.

### Test R1 — the registry-guard test

**Intent (brief §5):** `oof-buy` for a ticker NOT in `cfg.reconciliation.out_of_framework_tickers` → `click.ClickException`.

**Fixture (via `CliRunner`, exercising the REAL CLI):**
- Seed `out_of_framework_tickers=("SPCX",)` via the **OVERRIDES path** (write a user-config.toml `[reconciliation] out_of_framework_tickers = ["SPCX"]` and monkeypatch `USERPROFILE` AND `HOME` per the `write_user_overrides` gotcha — so `apply_overrides` materializes it). This is the O1 discriminator: a test that seeds bare config would PASS against a bug that reads bare config; seeding via overrides exercises the production read.
- Run `swing journal oof-buy --ticker AAPL --cost 100 --date 2026-06-18` (AAPL NOT in the registry).

**Assertions + pre/post arithmetic:**
- The command exits non-zero with a `ClickException` whose message names the rejected ticker + points to `[reconciliation] out_of_framework_tickers`; NO `cash_movements` row is written.
- A PARALLEL positive case: `--ticker SPCX` (in the registry) is accepted (writes the row) — so the guard is proven to ACCEPT registered tickers, not reject everything.
- **The lower-case acceptance arm (the Codex R1 MAJOR coverage):** `--ticker spcx` (lower-case; registry has `SPCX`) is ACCEPTED and writes a row whose `ref == "oof:SPCX:<d>"` (the CANONICAL upper-cased ref). PRE-the-fix (no boundary upper-casing) this would be REJECTED by the case-sensitive registry lookup (`"spcx" in ("SPCX",)` is False) AND/OR produce a non-canonical `oof:spcx:...` ref → the assertion FAILS. POST-fix it is accepted with the canonical ref. **Distinguishes** the boundary-normalization fix.
- **O1 discriminator:** if the command read bare `ctx.obj["config"]` (the bug), the registry would be EMPTY (overrides not applied) and EVEN `--ticker SPCX` would be rejected → the positive case FAILS. So this test distinguishes the correct `apply_overrides` read from the bare-config bug.

### Test I1 — the idempotency test

**Intent (brief §5):** `oof-buy` run twice with the same key → no double-record (unique-index / no-op).

**Fixture:** run `swing journal oof-buy --ticker SPCX --cost 500 --date 2026-06-18` TWICE (identical args → identical `_build_oof_ref("SPCX","2026-06-18")`), env=production, SPCX registered.

**Assertions + pre/post arithmetic:**
- After the FIRST run: exactly ONE `cash_movements` row with `ref="oof:SPCX:2026-06-18"`.
- After the SECOND run: STILL exactly ONE `cash_movements` row (no double-record); the command exits 0 (or a clean non-error "already recorded" message) — NOT an uncaught `sqlite3.IntegrityError` traceback. The SELECT-first ladder (`find_by_ref` → already-present → echo no-op) is the primary path; the `IntegrityError` catch is the belt.
- **The mixed-case idempotency arm (the Codex R1 MAJOR coverage):** run `--ticker spcx` (lower) then `--ticker SPCX` (upper), same date → STILL exactly ONE row (`ref="oof:SPCX:2026-06-18"`). Because both upper-case at the boundary to the IDENTICAL canonical ref, the second run dedups. PRE-the-fix (no boundary upper-casing) the lower-case run would write `oof:spcx:...` and the upper-case run `oof:SPCX:...` → TWO rows (idempotency silently broken across case) → the assertion FAILS. **Distinguishes** the boundary-normalization fix at the idempotency layer.
- **Distinguishes:** without the idempotency ladder, the second run either inserts a duplicate (if `ux_cash_ref` were absent — it is not) OR crashes with an `IntegrityError` traceback (the bad UX the ladder prevents). The assertion "exactly one row AND clean exit" fails both bad behaviors.

### Test SB1 — the sandbox test

**Intent (brief §5):** under `environment != "production"`, no domain row written (audit-only).

**Fixture:** set `cfg.integrations.schwab.environment = "sandbox"` (via overrides / config), SPCX registered, run `swing journal oof-buy --ticker SPCX --cost 500 --date 2026-06-18`.

**Assertions + pre/post arithmetic:**
- ZERO `cash_movements` rows written; the command echoes a clear sandbox advisory (ASCII-only) and exits 0.
- A PARALLEL production case (same args, `environment="production"`) writes exactly ONE row — so the gate is proven to be env-conditional, not "never writes."
- **The validation-still-runs arm (the Codex R2 MAJOR-2 fix — proves the short-circuit is WRITE-SCOPED, not a pre-validation bail):** under SANDBOX, a NON-OOF ticker (`--ticker AAPL`, not in the registry) STILL raises the registry `ClickException` (NOT a silent sandbox no-op). PRE-the-fix (if the CLI short-circuited to sandbox BEFORE the registry guard) this arm would NOT raise — the command would silently no-op → the assertion FAILS. POST-fix (validation precedes the write-scoped sandbox gate, §1 control-flow order) it raises → the assertion PASSES. **Distinguishes** the control-flow ordering: it proves the registry guard runs regardless of env.
- **Distinguishes:** without the gate, the sandbox run writes a row → the "zero rows" assertion fails. With the gate, sandbox writes nothing, production writes one. The two env paths DIFFER; AND the validation-still-runs arm proves the sandbox gate did not swallow the registry guard.

### Live-DB-shape discipline (brief §5.10) + encoding (Windows cp1252)

- **Read-path verification:** the registry read-path (`apply_overrides(cfg).reconciliation.out_of_framework_tickers`) and the env read (`cfg.integrations.schwab.environment`) are verified against the LIVE config shape (the live registry is `("SPCX",)`), not just seeded fixtures (the 18-E lesson). The R1 test's overrides-seeding exercises the production read shape.
- **ASCII-only user-facing strings:** every `click.echo` / `ClickException` message added (the registry-rejection message, the sandbox advisory, the success confirmation, the idempotency no-op message) is ASCII — no `§ → ↔ ✓ ✗`, no em-dash, no fractions (the Windows cp1252 `UnicodeEncodeError` gotcha; `capsys` hides it). A subprocess-through-PowerShell encoding test is OUT of this arc's scope (the existing CLI-entry UTF-8 `errors='replace'` safety net covers it) but the added strings are written ASCII-clean by construction.

### Acceptance (executing)

- Tests C1, S1, C3, C2, R1, I1, SB1 green; the FULL fast suite green (`python -m pytest -m "not slow" -q`) BEFORE the Codex review (recipe §2: review converges on a green diff).
- `ruff check swing/` clean.
- The §5/§6 traceability table (§5) honored on disk; the tripwire self-certification (§6) holds.

---

## 5. §5 / §6 traceability table (the CHARC + RD QA checklist)

| brief obligation | plan task | plan test | how it distinguishes / honored-on-disk |
| --- | --- | --- | --- |
| §5 distinguishing-test arithmetic (pre: drift fires; post: delta 0) | Task 2 + 3 | C1 | `eval_delta_pre = C > tol` (fires) vs `eval_delta_post = 0` (never), both computed under the real emitter (§2.4 arithmetic). |
| §5 composition test (BINDING, RD): `eval_delta == 0` at cost==MV AND after a later price move | Task 2 + 3 | C1 (3 arms) | the both-sides-exclude property: ledger −cost orthogonal to NLV −declared_oof_mv (`declared_oof_mv` from POSITIONS, §2.4 `:1911-1926`). |
| §5 self-reconcile test (OOF row NOT firing `cash_movement_mismatch`, asserted SKIPPED-AS-SELF-SOURCED; FAILS if branch absent) | Task 2 | S1 | scoped to the OOF `cm.id`: fixture has NO withdraw-typed counterpart in window (R2-1 isolation) so pre-fix emits (PASS-2 no-counterpart); post-fix the §2.1 branch `continue`s before emit; the branch-disabled belt flips the emit on the single boolean. |
| §5 additive/guard-only proof (every non-OOF row byte-unchanged) | Task 2 | C3 | the 4-outcome mix; `_is_oof_sentinel_ref` False for all non-OOF refs → branch inert → emit set pre==post. |
| §5 OOF sentinel ref can NEVER collide with a real `transaction_id` | Task 1 | C2 | numeric `transaction_id` vs `oof:`-prefixed ref are mutually exclusive by construction; both directions pinned. |
| §5 registry-guard test (non-OOF ticker → `ClickException`) | Task 3 | R1 | reads `apply_overrides(cfg)` (O1); seeds via overrides; positive SPCX case proves accept, AAPL case proves reject. |
| §5 idempotency test (twice, same key → no double-record) | Task 3 | I1 | deterministic ref + `ux_cash_ref` + SELECT-first ladder; exactly-one-row + clean-exit. |
| §5 sandbox test (no domain row, audit-only) | Task 3 | SB1 | WRITE-SCOPED `environment != "production"` gate (mirror `pipeline_steps.py:292`); zero rows sandbox, one row production; AND a non-OOF ticker under sandbox STILL rejects (validation precedes the write short-circuit — R2-2). |
| §5.10 live-DB-shape discipline | Task 3 | R1 (overrides-seeded) | registry + env read-paths verified vs the live `("SPCX",)` shape, not just fixtures. |
| §5 ASCII encoding | Task 3 | (by construction) | all added user-facing strings ASCII (cp1252 gotcha). |
| §6 Codex review-strong to convergence + codex-auto-review | (executing) | — | §7 executing spec: review-strong repo-access to `NO_NEW_CRITICAL_MAJOR` + codex-auto-review matched-high. |
| §6 RD measurement-integrity L-checklist MERGE-BLOCKING | (executing) | C1 | cash coherence is measurement-core; C1 is the binding artifact. |
| §6 operator §5.10 live-witness BINDING | (executing) | — | §7: real/sandbox OOF ticker → recon run → witness (a) ledger coherent, (b) no recurring `cash_movement_mismatch`, (c) registry rejects non-OOF. |
| §6 before-review full-suite + `ruff check swing/` clean | (executing) | — | §4 acceptance + recipe §2. |

---

## 6. Tripwire self-certification

| tripwire | crossed? | disposition |
| --- | --- | --- |
| New schema / migration | **NO** | reuses the free-form `ref` column (0029) as the origin marker + `ux_cash_ref` for idempotency. No migration. Schema stays v31. |
| New module / package under `swing/` | **NO** | a new CLI subcommand in `swing/cli.py` + a one-branch rule + a 3-line ref helper in the EXISTING `swing/trades/schwab_reconciliation.py`. The cash insert reuses the EXISTING public `insert_cash` (NOT a new data function). |
| New external dependency | **NO** | — |
| New standing process | **NO** | a CLI command is operator-invoked — not a pipeline step / daemon / scheduled job / ritual. |
| Phase-isolation carve-out (`swing/trades`) | **YES → AUTHORIZED** (brief §3) | `swing/trades/schwab_reconciliation.py` step-7 matcher: **additive/guard-only** — ONE branch that ADDs a self-sourced skip for OOF-marked rows; it MUST NOT alter any existing match/emit path for non-OOF rows (byte-unchanged, proven by C3). The ref helper lives in the same module (a pure predicate/constructor; no behavior change to existing functions). Precedent: the SPCX / §2.4 / limbo guard-scoped `swing/trades` carve-outs. |

**ONE authorized carve-out** (the step-7 matcher branch + the co-located ref helper, additive/guard-only). **NO schema, NO new module/package, NO new dependency, NO new standing process.** The optional `cash_oof_self_sourced_count` counter (O3) is within the matcher's existing counter dict (additive, not a carve-out widening); the plan does NOT require it. **No §0 BLOCKING question** — the authorized scope fully implements the settled design. If executing discovers the design needs schema or a SECOND carve-out, it STOPS and surfaces it to CHARC via the orchestrator (recipe §5) — it does NOT bake it in.

**File list (production, executing):**
- `swing/cli.py` — the new `@journal_group.command("oof-buy")` subcommand (registry guard via `apply_overrides`, sandbox gate, idempotency ladder, `insert_cash` write).
- `swing/trades/schwab_reconciliation.py` — the ref helper (`_OOF_REF_PREFIX` + `_build_oof_ref` + `_is_oof_sentinel_ref`) + the ONE PASS-2-top self-reconcile branch.
- **Tests (executing):** new `tests/trades/test_oof_buy_cash_coherence.py` (C1/S1/C3/C2 — the recon-path + ref-helper tests) + new `tests/cli/test_oof_buy_command.py` (R1/I1/SB1 — the CLI tests). The executing implementer picks the exact test-module split to match the repo's `tests/` layout; mirror `tests/trades/` recon fixtures + `tests/cli/` `CliRunner` patterns.

Default `swing/trades` read-only posture returns after this arc.

---

## 7. Executing-phase spec (baked in from brief §6 + §9)

- **Cell:** `implementer-opus-max` (measurement-core; the subtle self-reconcile matcher interaction that fooled a read-only mapping agent — brief §9).
- **Review (executing, BINDING gate):** `review-strong` (gpt-5.5/high) with **REPO ACCESS** — production-code: the matcher branch's correctness depends on the surrounding two-pass step-7 loop + the ingest TRADE-skip + the §2.4 composition, all UN-changed neighbors, so the reviewer MUST read beyond the diff (recipe §3 18-H.4 repo-access note). Run to `NO_NEW_CRITICAL_MAJOR`; the 5-round cap is suspended; **NEVER tier down.** PLUS **`codex-auto-review`** (gating, repo-access, matched-HIGH effort — `codex exec review --commit <pre-review-sha> -c model_reasoning_effort=high`) as the complementary second eye on production code; a B `major`/`[P1]` is adjudicated + resolved-or-cited before merge.
- **RD:** measurement-integrity L-checklist is **MERGE-BLOCKING** (cash coherence is measurement-core; C1 is the binding artifact). The orchestrator routes to RD after its own QA; the implementer NEVER posts.
- **Operator §5.10 live-witness — BINDING:** run `swing journal oof-buy` for a real/sandbox OOF ticker, then a reconciliation run, and witness (a) the swing ledger coherent (`eval_delta` within tolerance — no `equity_delta` fire), (b) NO recurring `cash_movement_mismatch` for the OOF row, (c) the registry guard rejects a non-OOF ticker.
- **Convergence transcript:** the executing Codex `NO_NEW_CRITICAL_MAJOR` transcript → a TRACKED `docs/reviews/oof-buy-command-executing-codex-findings.md`.
- **Commit discipline:** BARE git from the worktree cwd (never `git -C`); ZERO `Co-Authored-By`; conventional commits carrying the task id; before-review full-suite + `ruff check swing/` clean (recipe §2).
- **Base:** then-current `main`; the orchestrator rebases your branch + runs the merged-head no-false-green suite (the cross-arc seeding-regression net — recipe / the 18-B.1×18-D lesson).

---

## 8. Explicitly OUT of scope

- **OOF SELL direction (transfer-IN)** — V2. Proceeds from selling an OOF holding re-enter swing cash; the symmetric command would insert a `deposit` with an `oof:` sentinel. V2 dependency: the same matcher branch already skips ANY `oof:`-reffed row (deposit or withdraw), so the matcher is forward-compatible, but the CLI `oof-sell` surface + its own composition test are V2. (V1 ships BUY-only because the §2.4 driver was a buy and SELLs are rarer.)
- **#2 `equity_delta` materiality bump (`MATERIAL_BY_TYPE` 0→1)** — DEFERRED (brief §0/§7). Premature before benign-drift suppression (the ~$100 monthly-deposit drift would nag the material banner). Revisit after this arc + suppression land.
- **#3 general manual-cash ergonomic** — §4 WATCH (D16). Candidate = durable-acknowledge suppression-widening; build only if the monthly-deposit acknowledge becomes a chore (verify the cross-run re-emit behavior of `acknowledged_immaterial` cash_movement_mismatch first).
- **Any measurement-chain touch** — the §2.4 coherence/emit logic, the `declared_oof_mv` derivation, the swing-NLV basis, the `equity_delta` columns. SHIPPED + correct; this arc only RECORDS the ledger transfer-out + SKIPS the self-sourced cash row in the matcher. The §2.4 arithmetic is read-only-relied-upon, never edited.
- **Schwab full-auto OOF detection** — declined (brief §0 option, declined). `SchwabTransactionResponse` carries no symbol (§2.2), so auto-attribution is fragile; the operator-supplied `--ticker --cost` is the settled design.
- **The web orphan-acknowledge branch** — an OOF transfer-out is recorded via the CLI, not a web surface; no web change.

---

## Appendix A — grounding observations (benign drift / strengthening; do NOT re-open the settled design)

Every brief §2 grounding fact + §4 design clause re-grounded CLEAN on disk (`main` HEAD `caa57a50`); all line anchors confirmed (the brief's `~:` anchors are accurate within drift):
- `_CASH_SKIP_TX_TYPES` at `:113` ✓; the ingest TRADE-skip at `:991` ✓; `:180` classifier-skip ✓.
- R9 `kind_ok = tx.type in expected_types` at `:1737` ✓; `_ref_mismatch_cm_ids` at `:1747` ✓; PASS-2 force-emit at `:1768-1771` ✓; the emit at `:1804` ✓.
- `swing_nlv = finite_source_nlv - declared_oof_mv` at `:1939` ✓; `eval_delta = finite_ledger_equity - swing_nlv` at `:1957` ✓; `declared_oof_mv` from positions at `:1911-1926` (brief `~:1905-1926`) ✓; tolerance `max(5, 0.005*|NLV|)` at `:208-211` ✓.
- `SchwabTransactionResponse` fields at `:357-361`, `transaction_id: str`, no symbol ✓.
- `cash_movements` schema + `ux_cash_ref` (migration 0029) ✓; `insert_cash` `cash.py:9` + `find_by_ref` `:30` ✓; `journal cash` CLI `cli.py:1700-1755`, `--ref` exposed ✓; `@main.group("journal")` `:1602` ✓.

The four OBSERVATIONS that STRENGTHEN the tests (none crosses a binding gate or the authorized scope; none re-opens the design):

1. **O1 (load-bearing) — the registry guard MUST read `apply_overrides(ctx.obj["config"])`, NOT the bare `ctx.obj["config"]` the `journal cash` mirror uses.** `out_of_framework_tickers` lives in user-config.toml overrides only (`config_overrides.py:159-182`); bare config returns an EMPTY tuple on the live system → every ticker rejected (the 18-E default-arg-diverges-from-production gotcha). **Consequence:** §2.7 + §3 specify `apply_overrides`; the R1 registry-guard test seeds the OOF ticker via the OVERRIDES path (monkeypatch `USERPROFILE`+`HOME`) and asserts the POSITIVE SPCX case is ACCEPTED — so it distinguishes the correct read from the bare-config bug. (Makes R1 stronger; does NOT change scope.)
2. **O2 — `insert_cash` does not catch `IntegrityError` and does not open its own tx.** A duplicate `ref` raises `sqlite3.IntegrityError` out of `insert_cash` (`cash.py:9-17`). **Consequence:** the CLI idempotency path is SELECT-first (`find_by_ref`) with an `IntegrityError` belt-catch, so a re-run is a clean no-op message, not a traceback (§3 property 2; I1 asserts it). (Makes I1 stronger.)
3. **O3 — the matcher counter is OPTIONAL.** A `cash_oof_self_sourced_count` increment makes the skip auditable (consistent with `cash_pending_suppressed_count`), but the self-reconcile TEST asserts the skip via the ABSENCE of an emit for the OOF cm.id, NOT the counter — so the counter is a documented option, not a requirement, and S1 is counter-independent. If added, the cash-summary envelope + `_empty_cash_counters` must include the key (shape-stable). (§2.1.)
4. **O4 — the sentinel ref segments are NORMALIZED + constrained at the CLI boundary.** The CLI upper-cases `--ticker` (`ticker.strip().upper()`) ONCE at the boundary BEFORE the registry lookup AND the ref construction (the Codex R1 MAJOR fix — §3), and the date is ISO-validated before the ref is built (mirroring `journal_cash_cmd:1732-1744`). So the ref's `<TICKER>` segment is always upper `[A-Z0-9.\-]+`, the `<YYYY-MM-DD>` segment is a valid ISO date, the command is case-INSENSITIVE at the user boundary, and the colon delimiter is unambiguous (tickers contain no colons). (§3.)

**Codex R1 MAJOR (ticker case normalization) — ADOPTED:** the plan now specifies the boundary upper-casing (§3 + §2.7) and adds the lower-case acceptance arm (R1) + the mixed-case idempotency arm (I1). See `.copowers-findings.md` Round 1.

**These observations make the plan's tests STRONGER (the registry-guard read pinned to the production path + case-insensitive, the idempotency UX hardened across case, the counter scoped as optional) — none is used to relax a binding condition or re-open the settled design.**
