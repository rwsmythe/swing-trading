# Commissioning Brief — OOF-Buy Cash-Coherence Command (`swing journal oof-buy`)

**Commissioned by:** CHARC (Tool Development Director)
**Date:** 2026-06-18
**Arc:** Phase-18 deferred-follow-up #1 (the cash-recon ROOT fix), shaped as the explicit operator command (design option B).
**Status:** COMMISSIONED — CHARC §3 architecture pass = **GO** (one carve-out authorized; **NO schema**). Awaiting operator writing-plans dispatch.
**Tripwires crossed:** phase-isolation carve-out into `swing/trades/` (the step-7 matcher branch; additive/guard-only). **NOT crossed:** new schema, new module/package, new dependency, new standing process. **Measurement-chain → RD measurement-integrity QA is MERGE-BLOCKING.**

---

## §0 — Decision of record (the 4-item cluster disposition, operator 2026-06-18)

From the four Phase-18 deferred follow-ups, the operator chose:
- **#1 cash-recon ROOT fix → THIS ARC**, shaped as the explicit `oof-buy` command (option B of three; "full Schwab auto-detect" and "manual-polish-only" both declined).
- **#2 `equity_delta` materiality bump (`MATERIAL_BY_TYPE` 0→1) → DEFERRED.** Premature before benign-drift suppression: at the live ~$1.5K NLV the emit tolerance is ~$5–8 (`max($5, 0.5%×NLV)`), so an unrecorded ~$100 monthly deposit fires `equity_delta` every month → material=1 would nag the GUI material banner on a benign recurring event. Revisit after this arc + suppression land.
- **#3 general manual-cash ergonomic → §4 WATCH (D16).** Candidate fix = durable-acknowledge suppression-widening; build only if the monthly-deposit acknowledge becomes a chore.
- **#4 id 72 → operator's one-time acknowledge** via the tier-2 reconcile flow (not engineering).

---

## §1 — Problem (the root)

Swing cash used to buy an **out-of-framework (OOF)** holding (e.g. the SPCX IPO) leaves the swing framework but is **never captured on the swing ledger** → swing-NLV / `equity_delta` coherence drift. This is the residual root the §2.4 arc exposed: §2.4 subtracts declared-OOF market value from the broker NLV (the **swing** side), but the **ledger** side never records the OOF cash outflow → ledger overstated → drift fires. The current workaround is the manual path-(a) `swing journal cash --withdraw <cost>`, which itself fires a recurring `cash_movement_mismatch` (the live "id 72") because the Schwab counterpart is a `TRADE`, not a cash withdrawal.

---

## §2 — Verified grounding (CHARC, on disk — do NOT re-derive; do NOT inherit a false premise)

Every claim below was confirmed on disk by CHARC (a read-only mapping agent's "easy self-reconcile, no schema" read was **wrong** — see the third bullet — which is exactly why these are pinned):

- **TRADE-skip premise (confirmed):** `swing/trades/schwab_reconciliation.py:991` — `if tx.type in ("TRADE","RECEIVE_AND_DELIVER")` → `continue`; classifier set `_CASH_SKIP_TX_TYPES` at `:113` ("skip BY DESIGN — trade cash already enters the ledger via realized P&L"). The assumption is **false for OOF buys**.
- **No symbol on the transaction object (confirmed):** `SchwabTransactionResponse` (`swing/integrations/schwab/models.py:357-361`) carries only `{transaction_id, transaction_date, type, net_amount, description}` — **no traded symbol.** This is *why* option B uses operator-supplied `--ticker --cost` rather than fragile Schwab inference. (`trader.py:448` does support a `symbol=` API filter — relevant only to the declined full-auto option.)
- **Self-reconcile is NOT free (confirmed; the corrected claim):** an auto-created `withdraw` cash_movement reffed to the TRADE txn FAILS PASS-1's R9 type-validation — `swing/trades/schwab_reconciliation.py:1737` `kind_ok = tx.type in expected_types` where `expected_types = withdraw-types = {ACH_DISBURSEMENT, WIRE_OUT, CASH_DISBURSEMENT, ELECTRONIC_FUND}`; `"TRADE"` ∉ set → the row lands in `_ref_mismatch_cm_ids` → PASS-2 (`:1768-1771`) force-emits `cash_movement_mismatch` **every run**. Self-reconcile therefore REQUIRES an explicit matcher rule (see §4).
- **§2.4 composition is SOUND (CHARC re-walked the arithmetic):** `swing_nlv = finite_source_nlv − declared_oof_mv` (`:1939`); `eval_delta = finite_ledger_equity − swing_nlv` (`:1957`); `declared_oof_mv` is summed from **positions** (`:1905-1926`), NOT from cash_movements. So the auto transfer-out (ledger side, −cost) and the OOF MV subtraction (NLV side, −current MV) are **orthogonal** — `eval_delta` is 0 at purchase (cost == MV) and **stays 0 as the OOF price moves later** (both sides exclude the OOF entirely). **No double-count.** The root fix does NOT re-open the §2.4 drift.
- **cash_movements schema (migration 0029):** `(id, date, kind ∈ {deposit,withdraw,interest,dividend,fee}, amount REAL ≥ 0, ref TEXT nullable, note TEXT)`; unique partial index `ux_cash_ref ON cash_movements(ref) WHERE ref IS NOT NULL`. `ref` is **free-form** (no format CHECK) → a sentinel `ref` is schema-legal AND gives idempotency.
- **CLI/repo to mirror:** `@journal_group.command("cash")` → `journal_cash_cmd(...)` (`swing/cli.py:1700-1710`, already exposes `--ref`); the repo is `insert_cash(conn, CashMovement(date,kind,amount,ref,note))` (`swing/data/repos/cash.py:9`); `find_by_ref(conn, ref)` (`:30`) is the ref-exact lookup the dedup ladder uses.

---

## §3 — CHARC architecture pass (GO)

| Tripwire | Crossed? | Disposition |
|---|---|---|
| New schema | **NO** | Option B uses the existing free-form `ref` column as the origin marker. No migration. |
| New module/package under `swing/` | **NO** | A new CLI subcommand in `swing/cli.py` + a one-branch rule in the *existing* step-7 matcher. (Implementer may add a thin OOF-transfer service helper; still no new package.) |
| New external dependency | **NO** | — |
| New standing process | **NO** | A CLI command is operator-invoked — not a pipeline step / daemon / scheduled job / ritual. |
| Phase-isolation carve-out | **YES → AUTHORIZED** | `swing/trades/schwab_reconciliation.py` step-7 matcher: **additive/guard-only** — it only ADDS a self-sourced skip for OOF-marked rows; it MUST NOT alter any existing match/emit path for non-OOF rows (byte-unchanged). Precedent: the SPCX / §2.4 / limbo guard-scoped `swing/trades` carve-outs. The cash insert reuses the existing public `insert_cash` (not a new data function). |

**Measurement-chain:** the cash ledger feeds equity coherence → **RD measurement-integrity QA is MERGE-BLOCKING**; the §5 composition test is the binding artifact.

---

## §4 — Design contract

**The command** — a sibling of `journal cash`:
```
swing journal oof-buy --ticker <SYM> --cost <DOLLARS> [--date YYYY-MM-DD]
```
- Records a swing transfer-**OUT**: `insert_cash(CashMovement(date, kind="withdraw", amount=cost, ref=<OOF sentinel>, note=<audit string>))`.
- **OOF sentinel `ref`:** a deterministic, recognizable marker (e.g. an `oof:`-prefixed key encoding ticker + date) — NOT a real `transaction_id`. It (a) marks origin for the §4 matcher rule and (b) gives idempotency via `ux_cash_ref` (a re-run with the same key is a clean no-op/error, never a double-record). The exact sentinel format is a writing-plans detail; it MUST be shaped so it can never collide with a real Schwab `transaction_id`.

**Registry guard:** REJECT (clear `click.ClickException`) if `--ticker` is NOT in `cfg.reconciliation.out_of_framework_tickers`. A regular swing position must be journaled as a normal trade, not an OOF transfer-out.

**Self-reconcile (the matcher rule — the carve-out):** in the step-7 cash-movement matcher, ADD one branch: a cash_movement whose `ref` is an OOF sentinel is **self-sourced** → excluded from the `cash_movement_mismatch` emit (treated as matched). **Additive-only:** every non-OOF row's match/emit path is byte-unchanged.

**Sandbox gating:** cash_movements is a DOMAIN row → under `cfg.integrations.schwab.environment != "production"` the domain write short-circuits (mirror the existing domain-row sandbox gate; audit-only). The command respects it.

**Scope (V1):** BUY direction only (transfer-OUT). OOF SELLs (proceeds re-entering swing cash → transfer-IN) are a documented follow-up, OUT of V1 (rarer; the §2.4 driver was a buy).

---

## §5 — Test obligations

- **Distinguishing-test arithmetic** (memory `feedback_regression_test_arithmetic`): compute the coherence delta under BOTH the pre-fix path (no transfer-out → drift fires) and the post-fix path (transfer-out → delta 0); the test must DISTINGUISH the two.
- **Composition test (BINDING, RD):** a swing-NLV coherence scenario — OOF buy at cost C → after `oof-buy`, `eval_delta == 0`; AND after a later OOF **price move**, `eval_delta` STILL `== 0` (the both-sides-exclude property). Use real-derived inputs, NEVER values built to satisfy the premise (memory `feedback_verify_premise_arithmetic_vs_live`).
- **Self-reconcile test:** an OOF-marked cash_movement does NOT fire `cash_movement_mismatch` across a reconciliation run — and the test FAILS if the matcher branch is absent (assert the OOF row is *skipped as self-sourced*, not merely that some row matched).
- **Registry-guard test:** `oof-buy` for a non-OOF ticker → `ClickException`.
- **Idempotency test:** `oof-buy` run twice with the same key → no double-record (unique-index / no-op).
- **Sandbox test:** under sandbox, no domain row written (audit-only).
- **Live-DB-shape discipline** (§5.10): any read-path the command/matcher relies on is verified against the live-DB shape, not just seeded fixtures.
- **Encoding:** ASCII-only user-facing strings (the Windows cp1252 `UnicodeEncodeError` gotcha).

---

## §6 — Gates (all binding)

- **Codex review-strong** (gpt-5.5/high) to **CONVERGENCE** (zero new crit/major; the 5-round cap is suspended for this project) — the binding production-code gate — PLUS **codex-auto-review** with repo access (the adopted complementary second eye on production-code arcs).
- **RD measurement-integrity L-checklist — MERGE-BLOCKING** (cash coherence is measurement-core).
- **Operator §5.10 live-witness — BINDING:** run `oof-buy` for a real/sandbox OOF ticker, then a reconciliation run, and witness (a) the swing ledger coherent (`eval_delta` within tolerance), (b) NO recurring `cash_movement_mismatch` for the OOF row, (c) the registry guard rejects a non-OOF ticker.
- **Before-review full-suite run + `ruff check swing/` clean** (the recipe).

---

## §7 — Out of scope / follow-ups

- **OOF SELL direction (transfer-IN)** — V2.
- **#2 `equity_delta` materiality bump** — DEFERRED (revisit after this arc + benign-drift suppression).
- **#3 general manual-cash ergonomic** — §4 WATCH (D16); candidate = durable-acknowledge suppression-widening (verify the cross-run re-emit behavior of `acknowledged_immaterial` cash_movement_mismatch first).

---

## §8 — Return report

The **ORCHESTRATOR** posts the return report to `charc` (+`rd`) **AFTER its own QA gate** — this is NOT a raw implementer instruction. The implementer reports to its orchestrator in chat; it NEVER posts to a director inbox (memory `feedback_implementer_never_posts_to_directors`; CHARC §5.6).

---

## §9 — Dispatch model + effort recommendation

- **writing-plans → `implementer-opus-xhigh`** — design + the distinguishing/composition-test arithmetic + driving Codex to convergence.
- **executing → `implementer-opus-max`** — measurement-chain TDD + the subtle self-reconcile matcher interaction (the exact interaction that fooled a read-only mapping agent). Cash coherence is measurement-core; a wrong call here is costly.

(The orchestrator selects the cells per `docs/implementer-dispatch-recipe.md` and announces; this is the recommendation, not a binding selection.)
