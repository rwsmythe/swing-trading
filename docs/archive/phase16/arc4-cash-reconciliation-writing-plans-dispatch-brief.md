# Writing-Plans Dispatch Brief — Phase 16 / Arc 4 (4b+4c): Routine Cash Reconciliation + Equity Coherence

**Arc:** Phase 16 / **Arc 4** (4b+4c). SECOND of the full copowers cycle; the brainstorm spec is LOCKED + merged (QA'd — its grounding corrections to the original dispatch verified on disk: the wrapper exists @trader.py:437; the L2 lock is NOT triggered [endpoint = row 4 of the v3 diff]; pendings 66/67 are live).
**Source of truth (LOCKED, merged):** [`docs/superpowers/specs/2026-06-11-cash-reconciliation-design.md`](superpowers/specs/2026-06-11-cash-reconciliation-design.md) — **READ IT END-TO-END.** The plan implements it; do NOT re-litigate. §3 (the binding operator decisions), §9 (the binding testing posture), and **§12 (the items deferred to YOU)** are the raw material.
**Branch-from:** main HEAD at worktree creation (currently `c1fc062d`; re-verify — the operator commits in parallel).
**Schema:** **YES — migration `0029` (v28→v29)** per spec §7 (the `basis` column + backfill on `account_equity_snapshots`; the `cash_movements` rebuild with the ISO-date CHECK + the kind-vocabulary widening + the rows-1-3 normalization + the `ux_cash_ref` index preservation). Number re-checked at executing-branch time; #9 BEGIN/COMMIT + version bump in-file; strict-equality backup gate (`current_version == 28`); migrate-twice; the full #11 sweep.
**Deliverable:** an executing-ready plan at `docs/superpowers/plans/2026-06-11-cash-reconciliation-plan.md` + Codex convergence (`NO_NEW_CRITICAL_MAJOR`) + `.copowers-findings.md` (prompts AND responses). Commit ONLY the plan doc.

---

## 1. Mandate (one line)

Turn the LOCKED spec into an ordered, TDD-structured, executing-ready plan: auto-ingestion of ALL Schwab cash types (ref-idempotent, append-only, inside `run_schwab_reconciliation`'s existing transaction), the ±4-day/transactionId-primary matcher fix, the equity-coherence check (ledger-primary tile + NLV alongside; tolerance `max($5, 0.5%)`; flat-only), migration 0029 with the data normalization, the five-kind vocabulary wired into `equity.py` same-task, the #27/badge surfacing — resolving every §12 deferred item.

---

## 2. The §12 deferred items YOU resolve in the plan (each is a named plan section)

1. **The exact migration SQL** — the `cash_movements` rebuild (SQLite ALTER limitations → CREATE-copy-DROP-rename per the 0014/0023 precedent; FK toggle at the runner; **preserve/recreate `ux_cash_ref`** — the Codex catch), the date `CASE` normalization for rows 1-3 (M/D/YY → ISO) + the stray-quote `ref` fix, the **GLOB sanity gate** (no row survives non-ISO), the `basis` column + `'net_liq'` backfill on snapshots + the uniqueness-index reconciliation Codex flagged.
2. **Dividend/interest markers from REAL captured payloads (a BINDING precondition)** — the spec mandates fixtures derive from real `Client.transactions(...)` responses, not invented type strings. The plan must specify HOW the executing phase captures/verifies them (the existing 30-day nightly fetch's audit artifacts, a recorded payload, or an explicit operator-assisted capture step) BEFORE the ingestion-type tests are written. If no real dividend/interest payload exists in the account history, the plan says so and pins those types as marker-verified-deferred (ingestion code present, the type-set test marked pending-real-payload).
3. **The exits-adapter lift** (spec §5) — the matcher-fix locus.
4. **The no-FK resolve branch's `get_choice_menu` wiring** (the un-dispositionable all-NULL-FK pendings catch) — per-choice `requires_custom_value` (the Phase-12 contract).
5. **The `equity_delta` render-path tolerance of the new basis envelope keys** (the audit-envelope `None`-uniformity gotcha applies).
6. **The #11 grep-sweep of `('deposit','withdraw')` hardcodes** — enumerate every Python mirror (constants, `__post_init__`, repo guards, CLI validation) at STEP 0.
7. **The one-time operator disposition of live pendings 66/67** — an operator-gated step in the plan's post-merge runbook (NOT auto-resolved by code).

---

## 3. Plan shape (you own the decomposition; map every task to spec §9's testing posture)

Natural ordering: (1) migration 0029 + #11 sweep (atomic); (2) models/repo widening (five kinds + read/write together); (3) the ingestion core (inside the existing transaction; ref-idempotent; sandbox-gated; append-only); (4) the matcher fix (±4-day window + transactionId-primary + ambiguity flags + the exits-adapter); (5) equity coherence (the tile + tolerance + flat-only check + badge); (6) surfacing (#27 + pipeline.log + the dashboard badge; the `equity_delta` envelope keys); (7) the CLI/choice-menu wiring; (8) full suite + ruff. **Discriminating tests per [[feedback_regression_test_arithmetic]] throughout** — esp.: the ingestion idempotency (re-run ingests ZERO duplicates), the ±4-day window (a 5-day-off transaction does NOT match), the tolerance arithmetic (a $4.99 spread is silent; $5.01 warns; computed under both the old exact-date and new windowed matcher for the 4a row — pendings 66/67 must NOT regenerate), and the migration round-trip (rows 1-3 ISO + refs intact + `ux_cash_ref` present post-rebuild).

---

## 4. Locks (spec §10 — propagate verbatim)

The Schwab wrapper discipline for any NEW fetch surface (the spec §4 reuses the EXISTING `get_account_transactions` — if the plan needs a different window/params, signature-pin tests first); sandbox → audit-only; production-only domain writes; append-only `cash_movements` (the migration's one-time normalization is the sole exception); the risk floor + denominator resolution intact; `swing/trades/` carve-out scoped to `schwab_reconciliation.py` + `equity.py` (per the spec); the L2 lock NOT triggered (no new endpoints — keep it that way); suite baseline **7869**; zero `Co-Authored-By`.

---

## 5. copowers process (binding)

- **Run `copowers:writing-plans`** → adversarial Codex loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED). Codex must verify load-bearing data claims against the live DB (the standing discipline for this arc family).
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git; capture output to FILES.
- Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Commit ONLY the plan doc; conventional; trailers `[]`.
- **Return a report:** the plan path; the §2 resolutions (esp. the real-payload capture mechanism + the migration SQL approach); the Codex verdict (rounds + final line); flagged items for executing. Then STOP — executing is a separate commission after orchestrator QA.
