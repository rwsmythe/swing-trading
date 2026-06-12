# Brainstorming Dispatch Brief — Phase 16 / Arc 4 (4b+4c): Routine Cash Reconciliation + Equity Coherence

**Arc:** Phase 16 / **Arc 4** — the account-equity follow-through. 4a (the missing 5/28 deposit) is DONE; this commissions **4b** (routine cash reconciliation + the equity-coherence check) + **4c** (cash-movement completeness + the cash-vs-NLV discriminator + date normalization — **the schema item**). The original investigation + requirements: [`docs/phase16-todo.md`](phase16-todo.md) §Arc 4 (read it end-to-end — the three-divergent-equities decomposition is the problem statement).
**Cycle stage:** `copowers:brainstorming` (produce a LOCKED design spec, Codex-converged). FULL copowers cycle — schema + a new Schwab wrapper + money-display semantics + real operator decisions.
**Branch-from:** main HEAD at worktree creation (currently `2cca1231`; re-verify — the operator commits in parallel).
**Schema:** **YES — the 4c migration (number at EXECUTING-branch time; latest today is `0028` → expect `0029`, v28→v29; the #11 sweep + strict-equality backup gate per the per-phase shape).**
**Deliverable:** a locked design spec at `docs/superpowers/specs/2026-06-11-cash-reconciliation-design.md` + Codex convergence + `.copowers-findings.md` (prompts AND responses). Commit ONLY the spec doc.

---

## 1. Mandate (one line)

Design the system that makes the journal cash ledger UNABLE to silently drift from the broker: routine ingestion/reconciliation of Schwab cash transactions (the missing-monthly-deposit class), an explicit equity-coherence check between the ACCOUNT tile (journal `current_equity`) and the sizing denominator (Schwab NLV snapshot) with a tolerance + surfacing, the cash-vs-NLV basis discriminator on `account_equity_snapshots`, and the `cash_movements` date-format normalization — under this project's reconciliation philosophy (append-only audit, tiered corrections, sandbox containment).

---

## 2. Grounded current state (orchestrator-verified 2026-06-11)

- **The pieces that EXIST:** `cash_movement_mismatch` discrepancy machinery ([schwab_reconciliation.py:83/331](../swing/trades/schwab_reconciliation.py) — the type-sets + classification); the mapper `map_transactions_to_cash_movement_candidates` ([mappers.py:543](../swing/integrations/schwab/mappers.py) — consumes `Client.transactions(...)` responses; V1 emits ACH_*/CASH_*/WIRE_*/JOURNAL/ELECTRONIC_FUND + TRADE; extracts transactionId/date/type/netAmount/description); manual `swing journal cash --deposit/--withdraw` ([cli.py:1796](../swing/cli.py)).
- **The piece that does NOT exist:** a Schwab CLIENT WRAPPER fetching transactions — NOTHING in `client.py` calls schwabdev's `transactions()` endpoint. 4b builds it, under the FULL Schwab wrapper discipline: **camelCase kwargs pinned via `inspect.signature` discriminating tests BEFORE wrapper code** (cassettes/mocks won't catch kwarg drift); the typed `SchwabApiError` audit-row close (`record_call_finish` before re-raise); `ensure_schwab_log_redaction_factory_installed` before calls; **domain rows ONLY under `environment == 'production'`** (sandbox → audit rows only); the `SchwabPipelineActiveError` refusal family if a CLI writer is added; the L2 lock (a NEW Schwab REST endpoint call — verify against `docs/schwab-v3-endpoint-diff.md` + the L2 source-grep posture; flag the endpoint addition explicitly in the spec for the lock audit).
- **The live ledger:** `cash_movements(id, date, kind, amount, ref, note)` — 4 rows; **rows 1-3 dated `M/D/YY`** (`'3/30/26'`…, the Schwab-import-path artifact) **vs row 4 ISO** (`'2026-05-28'`); row 1's `ref` carries a stray leading quote (`'"115520131470'`); **rows 1-3's refs ARE Schwab transaction ids — the natural idempotency key for ingestion dedup.**
- **The snapshots:** `account_equity_snapshots(snapshot_id, snapshot_date, equity_dollars, source, source_artifact_path, recorded_at, recorded_by, notes, schwab_account_hash)` — latest `(22, '2026-06-09', 2027.44, 'schwab_api')`. The 4c discriminator (cash-basis vs Net-Liq, per the banked formalization) lands here.
- **The two equity readers:** the ACCOUNT tile = `current_equity` ([equity.py:27](../swing/trades/equity.py): starting_equity + realized P&L + net cash) via [dashboard.py](../swing/web/view_models/dashboard.py); the sizing denominator = `resolve_live_capital_denominator_dollars` ([equity_resolver.py:32](../swing/metrics/equity_resolver.py): the Schwab NLV snapshot; the risk floor `max($7500, actual)` rides it). NOTHING reconciles them today.
- The drumbeat precedent: `_step_schwab_snapshot`/`_step_schwab_orders` (nightly, lease.step'd, sandbox-gated) + Arc-5's `shadow_expectancy` step — the established shapes for a new nightly step.

---

## 3. Design questions (the brainstorm resolves WITH the operator — these are genuinely theirs)

1. **OQ-1 — ingestion posture:** auto-CREATE `cash_movements` rows from Schwab cash transactions (objective, broker-confirmed; idempotent by transactionId-in-`ref`; append-only) vs flag-for-review (a discrepancy surface + operator confirm, the tier-2 pattern). The operator's recurring $100/month deposit ([[project_recurring_monthly_deposit]]) is the motivating class. Weigh: auto-ingest closes the drift permanently; flag-for-review preserves the operator-owns-the-ledger posture. A hybrid (auto-ingest deposits/withdrawals; flag interest/dividends/fees) is plausible.
2. **OQ-2 — cadence + surface:** a nightly pipeline step (the drumbeat pattern — sandbox-gated, lease.step'd, #27-audited) vs a CLI/dashboard on-demand action vs both. Where does a detected mismatch SURFACE (dashboard? warnings_json? the reconciliation page)?
3. **OQ-3 — equity coherence:** which equity is AUTHORITATIVE for the ACCOUNT tile (the journal ledger is the operator's book; the NLV is the broker's truth — the todo flags "the denominator and the tile reading different equities is itself a coherence smell"); the spread tolerance (the residual $0.44 is rounding — propose e.g. >$5 or >0.5% warn); the surfacing (tile badge / #27 / both).
4. **OQ-4 — the 4c discriminator shape:** a `basis` column (`'net_liq'`/`'cash'`) on `account_equity_snapshots` (+ backfill `'net_liq'` for existing schwab_api rows?) vs distinct columns. Mind #11 (CHECK + constant + validator in ONE task) and the strict backup gate.
5. **OQ-5 — date normalization (4c):** migrate rows 1-3 to ISO in the migration (a DATA migration — show the exact UPDATEs; fix row 1's stray-quote ref too?) + a write-path guard so new rows are ISO-only (CHECK vs validator — #11 applies). The 4a note: cosmetic for the sum, LOAD-BEARING for ingestion date-matching/dedup.
6. **OQ-6 — interest/dividends/fees as cash_movements kinds (4c):** widening the `kind` vocabulary — enumerate the Python mirrors (#11 sweep: constants, validators, repo guards) and whether the tile's `net cash` should include them (it must, or the ledger drifts on uncredited cash — the todo's point).
7. **OQ-7 — what the V1 does NOT do:** no position-level NLV decomposition, no intraday sync, no Schwab-statement parsing (the banked since-inception statement ingestion stays banked). Keep the arc shaped like "the ledger can't silently drift," not "a full broker sync."

---

## 4. Locks / invariants

- **Schema:** the 4c migration only (number at executing-branch time; #9 BEGIN/COMMIT + version bump in-file; strict-equality backup gate; migrate-twice no-op; the #11 sweep). DB-outside-Drive.
- **Schwab discipline (all of it):** signature-pin tests before wrapper code; audit-row close; redaction installed; sandbox → audit-only; production-only domain writes; `SchwabPipelineActiveError` for CLI writers; **the L2 lock — a new endpoint call must be explicitly flagged + reconciled with `docs/schwab-v3-endpoint-diff.md`** (the lock was re-anchored once; a NEW endpoint is a real event, not a drive-by).
- **`reconciliation_corrections` is APPEND-ONLY**; `cash_movements` additions follow the same posture (no UPDATE-in-place of ledger rows except the one-time date normalization in the migration).
- **The risk floor** `max($7500, actual)` ([[project_capital_risk_floor]]) and the denominator resolution stay semantically intact; the tile's `current_equity` formula changes ONLY if the operator decides so in OQ-3.
- **`swing/trades/` is a carve-out candidate** (the reconciliation service lives there) — the spec must scope it explicitly (the 4b machinery extends `schwab_reconciliation.py`; the historical precedent allows spec-scoped carve-outs).
- Suite baseline **7869**; ruff clean; zero `Co-Authored-By`; the 3 banked `-n0` schwab-route flakes are pre-existing.

---

## 5. copowers process (binding)

- Run `copowers:brainstorming` (explore the §3 OQs WITH the operator → adversarial Codex loop **to convergence**, `NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED). **Codex must verify load-bearing data claims against the live DB shapes** (the [[feedback_adversarial_review_verify_data_shapes]] discipline — this arc JOINs broker data to ledger rows; fixtures from REAL emitter output).
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git; capture output to FILES.
- Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Commit ONLY the spec doc; conventional; trailers `[]`.
- **Return a report:** the spec path; the resolved §3 OQs; the L2-lock note (the new endpoint); the Codex verdict (rounds + final line); flagged items for writing-plans. Then STOP — writing-plans is a separate commission after orchestrator QA.

---

## 6. What this arc is NOT

NOT the banked since-inception Schwab-statement ingestion (stays banked). NOT a trade/fill reconciliation change (Phase 12's machinery is untouched except the cash_movement_mismatch wiring). NOT a position-level or intraday sync. NOT a risk-policy change. NOT Arc 9 (separate, queued last).
