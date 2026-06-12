# Executing Dispatch Brief — Phase 16 / Arc 4 (4b+4c): Routine Cash Reconciliation + Equity Coherence

**Arc:** Phase 16 / **Arc 4**. THIRD + final copowers stage. **The CHARC's GO carries FOUR BINDING DISPATCH NOTES (§2 below)** — folded here per the operator relay (also logged at `6e5177ea`).
**Cycle stage:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`; adversarial Codex after ALL tasks, run to convergence).
**Authoritative script (LOCKED, merged):** [`docs/superpowers/plans/2026-06-11-cash-reconciliation-plan.md`](superpowers/plans/2026-06-11-cash-reconciliation-plan.md) — **EXECUTE IT TASK-BY-TASK** (11 tasks + the STEP-0 #11 sweep). Spec: [`docs/superpowers/specs/2026-06-11-cash-reconciliation-design.md`](superpowers/specs/2026-06-11-cash-reconciliation-design.md). If plan or spec is wrong, STOP and flag (the plan already corrected the spec's stale §2 amounts — live rows 1-3 are $100/$100/$600 deposits; fixtures use the REAL values, binding).
**Branch-from:** main HEAD at worktree creation (currently `2dee9a7f`; re-verify — the operator commits in parallel).
**Schema:** **migration `0029` (v28→v29)** — re-check the number at branch time; the plan's SQL is the script (the WHEN-pinned date normalization + GLOB-CHECK abort gate; `ux_cash_ref` recreated verbatim; the `basis` column + backfill + uniqueness-index rebuild; strict `==28` backup gate; migrate-twice; the #11 sweep incl. the version-pin bumps).
**Suite baseline:** **7869** (the 3 banked `-n0` schwab-route flakes are pre-existing).

---

## 1. Mandate (one line)

Execute the 11-task plan: migration 0029; the five-kind vocabulary wired into `equity.py` same-task; ref-idempotent append-only auto-ingestion of ALL Schwab cash types inside `run_schwab_reconciliation`'s existing transaction; the ±4-day/transactionId-primary matcher + the exits-adapter lift; the ledger-primary equity-coherence check (tolerance `max($5, 0.5%)`, flat-only) + the ACCOUNT-tile badge; the `source_without_journal` choice-menu + resolution service; the `cash_warnings` runner capture; the operator runbook — TDD, green-per-commit, Codex-converged.

---

## 2. THE CHARC's FOUR DISPATCH NOTES (BINDING)

1. **ALL-OR-NOTHING MERGE.** The arc lands as ONE unit — no partial merge of the migration without the matcher/equity semantics (they interlock: the widened kinds change `net_cash_movements` which changes the tile). Your branch is merged whole by the orchestrator or not at all; structure commits so every intermediate is green but never propose a partial landing.
2. **CARVE-OUT RELABEL AT BRANCH START.** STEP 0 includes re-verifying + RESTATING the `swing/trades/` carve-out scope against the plan's final file map (the spec-scoped carve-out = `schwab_reconciliation.py` + `equity.py` [incl. the `_ExitShape`/`list_all_exitshape_via_fills` lift INTO equity.py; dashboard.py re-imports]) — record the restated scope in your first commit message body so the lock audit reads it.
3. **FLAGGED ITEMS 4+6 CONFIRMED.** (4) the `_render_pre_resolution_context_cash_movement_mismatch` source-direction render branch (the `expected["amount"]` vs `net_amount` KeyError guard) — implement as planned; (6) `net_cash_movements` RAISES on unknown kind — implement as planned AND audit every fixture planting a `CashMovement` for non-5-kind values at STEP 0.
4. **THE TWO OPERATOR-IN-THE-LOOP MOMENTS ARE SCHEDULED THROUGH THE ORCHESTRATOR.** (a) the REAL-payload capture (the supervised `swing schwab fetch` / latest `schwab_api_calls` body read for dividend/interest markers): when you reach that task, STOP and signal — the orchestrator coordinates the operator session; if the account history carries no DIVIDEND_OR_INTEREST rows, markers ship EMPTY + the visible `@pytest.mark.skip("pending real payload")` per the plan (never invented strings). (b) the pendings-66/67 disposition is POST-MERGE runbook (Task 11) — document it; do NOT auto-resolve.

---

## 3. The plan's flagged items (confirmed dispositions — implement, don't re-ask)

- **Live-value fixtures binding** (rows 1-3 = $100/$100/$600 deposits; refs incl. the stray-quote `'"115520131470'`; discrepancies 66/67 carry `cash_movement_id=4` journal-direction — the NEW source-direction `missing_journal_row` rows are the all-NULL-FK ones).
- **`run_schwab_reconciliation` gains `starting_equity`** — the production caller passes `cfg.account.starting_equity`; update every caller + test harness.
- **The banner-join caveat is the ACCEPTED V1 surface:** trade-joined banner excludes `trade_id IS NULL` pendings; the §6.2 dashboard badge (direct COUNT) is the surfacing for cash pendings. Do not rework the banner.
- **The `summary_json["cash_warnings"]` indirection is CONFIRMED** (vs a return-signature change); Task 9 fixes the runner's discard-the-return so the #27 warnings reach `warnings_json`.

---

## 4. Execution disciplines (binding)

- **TDD, green-per-commit** (failing test → SEE fail → minimal impl → SEE pass → ruff → commit; conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; trailers `[]` each commit; the plan gives the messages).
- **The discriminating tests are binding** (plan §3): ingestion idempotency (re-run → ZERO duplicates); the ±4-day boundary (5-days-off does NOT match); the tolerance arithmetic ($4.99 silent / $5.01 warns; floor-binding NLV per the Codex R1 fix); **the 4a regression — pendings 66/67 must NOT regenerate under the new matcher**; the migration round-trip (rows 1-3 ISO + refs intact + `ux_cash_ref` + the unexpected-shape ABORT); the coverage-gap helper's 2 tests; the run-row ledger-equity metadata test.
- **Schwab discipline:** reuse `get_account_transactions` (trader.py:437) as-is; sandbox → audit-rows-only; production-only domain writes; redaction installed; NO new endpoints (L2 stays untriggered).
- **Append-only:** `cash_movements` never UPDATEd in place (the migration normalization is the one sanctioned exception); `reconciliation_corrections` append-only.
- **Full fast suite + ruff ON YOUR FINAL HEAD** (actual count); degraded-harness guard on mid-batch cancellations.

---

## 5. copowers Codex review (after ALL tasks)

- Adversarial loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED) over the full diff vs plan + spec + this brief. Probe: the migration's abort path against a planted unexpected shape; the matcher window boundaries; the ingestion idempotency under re-runs + the sandbox gate; the tile/badge semantics; the all-or-nothing interlock (no commit leaves the tile reading widened kinds the migration hasn't created).
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git; capture output to FILES. Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Scrutinize rebuttals against disk.

---

## 6. Return report (then STOP — do NOT merge)

The commit SHAs + messages; the restated carve-out (note 2); the real-payload outcome (markers captured vs shipped-empty+skip — note 4a); the full fast-suite result ON YOUR FINAL HEAD (actual count) + ruff; the locks confirmation (append-only, sandbox gating, L2 untriggered, risk floor intact); the Codex verdict (rounds + final line); any deviation with justification; the operator-gate list (the live v28→v29 migration; the pendings-66/67 disposition runbook; the equity-tile/badge witness — these fold into the phase's combined gate run).
