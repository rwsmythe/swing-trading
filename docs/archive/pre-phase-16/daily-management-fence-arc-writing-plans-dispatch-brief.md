# Writing-Plans Dispatch Brief — Daily-Management Network-Under-Fence (#16) Fetch-Hoist

**Arc:** Phase 15 / B-family operational hardening — the daily-management network-under-fence fix (`#16`), fetch-hoist design.
**Cycle stage:** `copowers:writing-plans` (produce an executing-ready implementation plan, Codex-converged). This is the SECOND of the full copowers cycle; the brainstorm spec is LOCKED + merged.
**Source of truth (LOCKED, merged to main):** [`docs/superpowers/specs/2026-06-07-daily-management-fence-archive-api-split-design.md`](superpowers/specs/2026-06-07-daily-management-fence-archive-api-split-design.md) — READ IT END-TO-END. The plan implements that spec; it does NOT re-litigate it.
**Branch-from:** main HEAD at worktree creation (currently `5d9cd9b7`; re-verify with `git log --oneline -3`).
**Schema:** NONE — v24 holds. Zero migrations.
**Deliverable:** an executing-ready plan at `docs/superpowers/plans/2026-06-07-daily-management-fence-fetch-hoist-plan.md` + Codex convergence (zero new crit/major) + `.copowers-findings.md` (prompts AND responses). Commit ONLY the plan doc.

---

## 1. Mandate (one line)

Turn the LOCKED fetch-hoist spec into an ordered, TDD-structured, executing-ready task plan: make `compute_daily_approximate_snapshot` a pure compute (consumes a pre-warmed `archive_df`), hoist the `read_or_fetch_archive` warm OUTSIDE the per-trade `lease.fenced_write` in `_step_daily_management`, add the `expected_ticker` in-fence identity guard, and route all misses through one #27-audited skip — so no network I/O ever runs under the daily-management write lock.

The design is settled (Codex-converged, 4 rounds). Your job is the **plan**: task decomposition, the TDD test→impl→commit ordering, the exact per-task acceptance, and resolving the TWO decisions the brainstorm explicitly deferred to writing-plans (§3 below). Do NOT redesign.

---

## 2. STEP 0 — re-ground (cheap; the spec already grounded on `a460961c`)

The spec re-grounded line numbers on `a460961c`; main is now `5d9cd9b7` (only the spec doc was added since, so source line numbers are unchanged). Still, on your worktree HEAD, re-confirm the three anchors before pinning task line numbers:
- `_step_daily_management` @runner.py:3774; the per-trade fence @3810; `compute_daily_approximate_snapshot(conn, …)` @3811.
- `compute_daily_approximate_snapshot` @daily_management.py:465; the `read_or_fetch_archive` import @503 + call @510.
- `run_warnings` plumbing (orchestrator-verified): created @runner.py:815, serialized to `warnings_json` @1022, param-precedent `_step_pattern_observe(*, …, run_warnings)` @2663. **Locate the actual `_step_daily_management(...)` call site** (the spec wrote @837 as illustrative — find the real one and pin it; it currently does NOT pass `run_warnings`, and `_step_daily_management`'s signature currently has no `run_warnings` param).
- The 6 service-test callers @tests/trades/test_daily_management_service.py:131/204/237/272/295/332; the 2 step-test patches @tests/pipeline/test_daily_management_step.py; the walkthrough @tests/integration/test_phase8_pipeline_walkthrough.py.

---

## 3. The TWO decisions the brainstorm deferred to YOU (resolve in the plan, with the operator if pivotal)

1. **Miss-reason mechanism (spec §4.2 RECOMMENDED).** The spec offers two ways to tag the `miss_reason` for the #27 audit:
   - (preferred) `compute_daily_approximate_snapshot` **returns a typed miss reason** (a small result object or `(fields, miss_reason)` tuple) so the audit tag is sourced from the path that actually fired (ticker mismatch / df None-empty / empty anchor window / absent asof row).
   - (fallback) an external `_classify_infence_miss(conn, …)` labeler that re-derives the cause outside the function.
   The spec RECOMMENDS the typed return (the external labeler cannot reliably distinguish the function's four internal `None` paths and duplicates its logic). **Resolve this in the plan.** If you choose the typed return, it is a SECOND (small) amendment to the function's return contract (`dict | None` → e.g. `(dict | None, miss_reason | None)` or a result dataclass) — note it explicitly, update the 6 service-test migrations to consume the new return shape, and keep the `expected_ticker`-mismatch case mapping to `miss_reason="ticker_changed"`. The four-token taxonomy is fixed: `warm_raised` / `warm_empty_or_stale` / `ticker_changed` / `no_eligible_window`.
2. **Warm vs `list_open_trades`-snapshot ticker.** The warm uses `trade.ticker` from the up-front `list_open_trades` snapshot; the in-fence `get_trade` re-reads and the guard compares. Confirm the plan threads `expected_ticker=trade.ticker` (the snapshot value the bars were warmed for) — NOT a re-read — so a mid-step ticker mutation is *caught* by the guard rather than silently masked. (This is already the spec's design; just make the task explicit so an executor can't accidentally re-read.)

---

## 4. Plan shape (guidance — you own the final decomposition)

Structure as TDD tasks, each: write the failing test → see it fail → minimal impl → see it pass → commit (conventional, no Co-Authored-By). A natural ordering:

- **Task 1 — `compute_daily_approximate_snapshot` → pure compute.** Amend the §6.6 signature (drop `ohlcv_archive_dir`/`archive_history_days`, add `archive_df: pd.DataFrame | None` + `expected_ticker: str`; preserve `trail_MA_period_days_default` name + N803 + `PLR0913`); remove the `read_or_fetch_archive` import @503 + call @510; add the `expected_ticker` identity guard (return on mismatch); consume `archive_df`; everything downstream of the `df` assignment byte-unchanged. Plus the §3.1 miss-reason mechanism decision. Migrate the 6 service-test callers in the SAME task (drop the `read_or_fetch_archive` monkeypatch + removed args; pass `archive_df=<the frame they already build>` + `expected_ticker=<seeded ticker>`; the None/empty + no-asof + unknown-trade variants per spec §7.7).
- **Task 2 — `_step_daily_management` warm-hoist + `run_warnings` + #27 skip.** Add `run_warnings` to the step signature + wire the real call site to pass it; hoist `read_or_fetch_archive` warm OUTSIDE the per-trade fence (per-trade, just before its fence, in a best-effort try/except → `archive_df=None` + `miss_reason` on failure); keep the fence wrapping only `get_trade`(in the pure fn) + `upsert_snapshot` + `state_transition`; funnel all miss causes to one `fields is None` #27 branch; preserve `LeaseRevokedError` re-raise before the catch-all. Migrate the 2 step-test patches + the walkthrough to stub `swing.pipeline.runner.read_or_fetch_archive` (the warm).
- **Task 3 — the gold-standard lock-hold regression (spec §7.1).** Real file-backed SQLite, one open trade with a stale/missing archive (forces the warm); spy on `read_or_fetch_archive` attempting `BEGIN IMMEDIATE` on a 2nd connection. **Patch BOTH `swing.data.ohlcv_archive.read_or_fetch_archive` (pre-fix lazy import in the function) AND `swing.pipeline.runner.read_or_fetch_archive` (post-fix warm) with the same spy** (Codex R1 MAJOR #3 — patching only one gives a false reproduction). Anti-false-pass: assert the spy was called ≥1. Plus §7.2 ordering assertion (`in_fenced_write is False` on every warm; zero in-fence archive reads).
- **Task 4 — parity + miss-audit + lease-revoke (spec §7.3–§7.5).** Deterministic fixed-DataFrame parity (compute identical pre/post given the same frame); all four `miss_reason`s skip + #27 (test BOTH `no_eligible_window` sub-cases — empty anchor window AND absent asof row, per Codex R3); `LeaseRevokedError` still propagates.
- **Task 5 — non-breakage + suite (spec §7.6, §7.8).** Assert `read_or_fetch_archive` signature/behavior unchanged + no new public symbol in `swing.data.ohlcv_archive`; full fast suite green + `ruff check swing/`.

Pin each task's exact files, the discriminating assertion (per `feedback_regression_test_arithmetic` — compute the value under both pre- and post-fix paths to confirm the test distinguishes), and the commit message.

---

## 5. Locks / invariants (from spec §6 — propagate; do not regress)

- **Schema NONE** (v24). DB-outside-Drive.
- **Lease-fencing contract:** every write stays in `fenced_write` + in-tx lease check; ONLY the warm moves out. `LeaseRevokedError` re-raises (the warm cannot raise it; the fence/`upsert`/`state_transition` can).
- **§6.6 signature amendment** (operator-sanctioned): the drop/add above + (if chosen) the return-shape change. NO other locked signature touched; `trail_MA_period_days_default` name+N803 preserved.
- **`expected_ticker` guard is a REAL audited skip** — `trades.ticker` IS live-mutable (rarely) via tier-3 reconciliation override (orchestrator-verified on disk: `reconciliation_auto_correct.py:1216` generic `UPDATE trades SET {field}`; `validate_trade_correction` gates only `current_stop`/`state`). Skip + #27 on mismatch; never re-fetch.
- **#27 silent-skip-audit:** the skip emits a `warnings_json` entry (`step="daily_management"`, `ticker`, `reason`, `miss_reason`); `run_warnings is None` defensive guard mirrors detect/observe.
- **F6 transient-empty** (warm reuses `read_or_fetch_archive` unchanged — its stale-archive-on-empty defense @ohlcv_archive.py:263 preserved); **session-anchor** (`asof_session = last_completed_session(run_now)`, backward-looking, computed once, passed to both warm + compute — not moved); **idempotency** (`upsert_snapshot` SELECT-then-UPDATE/INSERT; `entered → managing` stays in-fence). Data-integrity barriers + lock-contention keepers (busy_timeout=30000, serialized audit_conn, G2′ telemetry) untouched.

---

## 6. Out of scope / banked (carry to the plan's out-of-scope §)

- **NOT reconciliation hardening.** The tier-3 reconciliation override mutating `trades.ticker` (`validate_trade_correction` allowlisting only `current_stop`/`state`) is a REAL gap, but allowlisting trade-correction fields is a **separate banked arc** — this arc only DEFENDS daily-management via the `expected_ticker` guard. Keep it banked; the plan's out-of-scope § notes it (orchestrator is tracking it for a future reconciliation arc).
- NO schema change. NO new archive-API function / read-only sibling (OQ-2 = pass-bars-in). Do not touch `_step_charts`, detect Pass-2, or observe (already reordered by `4f0b4010`). NOT Issue #3, NOT Gate 4, NOT the bad-bar issue.

---

## 7. copowers process (binding)

- **Run `copowers:writing-plans`** — wraps `superpowers:writing-plans` then the adversarial Codex loop **to convergence** (zero new crit/major / `NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED). Do not stop early; do not pad after convergence.
- **Codex transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows + tell Codex not to run git.
- **Persist BOTH prompts AND responses** of every Codex round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md` for independent orchestrator convergence-confirmation at QA.
- **No `Co-Authored-By`; no `--no-verify`; conventional commits; final `-m` paragraph plain prose** (no `Word:`-leading line → trailer-parse hazard). Commit ONLY the plan doc.
- **Return a report:** the plan path, how you resolved the §3 deferred decisions (esp. the miss-reason mechanism — typed return vs labeler — and any consequent return-contract change), the Codex convergence verdict (round count + final line), and anything flagged for executing. Then STOP — do NOT execute. Executing is a separate commission after the orchestrator QAs the plan.
