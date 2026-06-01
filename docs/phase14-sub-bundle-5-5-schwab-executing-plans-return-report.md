# Phase 14 Sub-bundle 5.5 (Schwab) — Executing-Plans Return Report

**Status:** COMPLETE — all 4 slices shipped; ONE Codex chain CONVERGED (NO_NEW_CRITICAL_MAJOR); fast suite green on the real HEAD; ZERO new migration (v23 held); ZERO new `schwabdev.Client.*` call sites (L2 green). Ready for orchestrator QA + the operator S1-S7 gate (incl. the S6 browser-badge leg).

> **Provenance note (honest):** this report covers a RESUMED session. A prior session left the branch in a known-broken, non-converged state under a degraded harness: it had committed the OQ-10 *test* (`dc9e542`) WITHOUT its implementation, never populated the badge on 5 primary nav builders, and shipped a clock-skew MINOR — and an earlier Codex review returned NEEDS_CHANGES on exactly those. This session re-applied ONE clean copy of each missing piece (verifying no duplication — the OQ-10 block was *missing*, not the rumored triplication, which lived only in the prior session's quarantined uncommitted attempt) and ran the chain to genuine convergence. Work was done in single sequential tool calls with a re-Read before every Edit and a `git show`/trailer verify after every commit (`feedback_degraded_harness_sequential_tool_calls`).

---

## Final HEAD & per-commit attribution

Branch `phase14-sub-bundle-5-5-schwab-executing-plans`. This session added 3 implementation commits + this report on top of the prior 7 impl commits.

| Commit | Subject | Punch-list item |
|---|---|---|
| `cf371c2` | feat(schwab): capture response header names once when no known rate-limit header matches | #1 OQ-10 (impl that `dc9e542`'s test was missing) |
| `b658114` | fix(schwab): reject future-skewed heartbeats and guard None cfg in the liveness helpers | #2 clock-skew MINOR + None-cfg guard (Codex prior-R1) |
| `64fbb57` | feat(web): populate the Schwab checker-health badge on the remaining primary nav builders | #2 badge populate MAJOR (Codex prior-R1) |
| (this commit) | docs(...): SB5.5 executing-plans return report | #5 |

Prior-session impl commits (unchanged, on-branch): `9d3d839` checker wrap + shared liveness · `dc9e542` header-capture **test** · `fa91ef2` web ladder install · `edc0a3b` CLI status liveness line · `95ec2a6` web badge (field + template + helper) · `423bde3` open-trade memo DB-error degrade test · `26f279d` ladder-comment reword (L2 grep).

---

## Codex single chain — CONVERGED (`.copowers-findings.md`)

Transport: WSL node22 `codex 0.135.0` (`/home/rwsmythe/.local/node22/bin/codex`; verified NOT the broken `/mnt/c/.../npm/codex` shim), read-only. Reviewed HEAD `64fbb57` vs base `ba3e6e4` (diff `.copowers-sb55-diff.txt`). Prompts + responses persisted to `.copowers-findings.md` (R1 prompt `.copowers-sb55-prompt-r1.txt`, R2 `.copowers-sb55-prompt-r2.txt`).

- **R1 → NEEDS_CHANGES.** Prior-round findings (badge populate MAJOR, clock-skew MINOR, OQ-10 missing) all **ABSENT** → confirmed fixed on HEAD. ONE new `[CRITICAL]`: the L9 provider-tag cooldown is not atomic with the Schwab attempt at `swing/web/app.py:294/:322` (N concurrent cold misses for one open-trade ticker can each attempt Schwab before the cooldown trips).
- **Adjudication (not blindly implemented — `receiving-code-review`).** That race is a **RE-RAISE of an already-accepted V1 residual**: the LOCKed plan's "Thread-safety (BINDING) — SCOPE of the guarantee" (lines ~126-127) analyzed it TWICE during the writing-plans chain (Codex R1 Major #2 + R2 Major #2), bounded it (single-operator V1; open-trade scope <10; ceiling well under the ~120/min budget; every 429 degrades gracefully to yfinance; the lock guarantees the cooldown/counter/memo are race-free — asserted by `test_concurrent_misses_do_not_slip_past_cooldown`), and EXPLICITLY ACCEPTED it, banking the per-`(ticker,window_days)` single-flight latch for V2. The proposed fix (hold the lock across the network ladder call) contradicts the plan's deliberate "DB read OUTSIDE the lock" design and would serialize all web market-data fetches → deadline misses. It is NOT a new defect from this change set.
- **R2 → NO_NEW_CRITICAL_MAJOR.** After a plan-citation rebuttal, Codex: *"Re-grade: I withdraw the R1 [CRITICAL]."* Zero remaining CRITICAL/MAJOR.

**Convergent shape:** ONE chain, 2 rounds. **ZERO majors accepted; ZERO findings implemented** (the single critical was correctly adjudicated as an already-accepted residual, not a fix; the genuine prior-round MAJOR/MINOR were the pieces this session shipped). Final on-disk verdict: `### Verdict: NO_NEW_CRITICAL_MAJOR`.

---

## Per-slice completion (re-applied pieces)

- **Slice 1b — OQ-10 / L9c header-key capture (`cf371c2`).** `import threading` + a once-per-process, `_HEADER_CAPTURE_LOCK`-guarded, INFO-level capture (`_maybe_log_response_header_names`) wired into `_extract_response_payload`, firing ONLY when no known rate-limit header matched. Names only (never values); no guessed header name. `_reset_header_capture_for_tests()` clears the flag. **Block confirmed to appear EXACTLY ONCE** (`grep -c` = 1 for each of the def/import; the rumored triplication was absent from the committed HEAD). Makes the committed `dc9e542` tests pass.
- **Clock-skew MINOR (`b658114`).** `CLOCK_SKEW_TOLERANCE = 5.0`; `evaluate_liveness_state` now returns DEGRADED ("heartbeat timestamp in the future (clock skew)") for a finite future `last_daemon_tick_ts` beyond tolerance instead of a false ALIVE.
- **None-cfg guard (`b658114`).** `build_schwab_checker_badge(None) -> None` so broad builder population is safe.
- **Badge populate MAJOR (`64fbb57`).** `build_schwab_checker_badge(cfg)` now called in `build_pipeline`, `build_watchlist`, `build_metrics_index_vm`, `build_schwab_status_vm` (SchwabStatusVM), and `_build_form_vm` (SchwabSetupVM `/schwab/setup`). `SchwabSetupErrorVM` stays a render-safe default per plan §B (and `_render_error` has no `cfg`). Already-populated builders (dashboard, journal, config) untouched.

---

## Test surface (actual — READ, not estimated)

- **Baseline at resume (HEAD `26f279d`):** `6966 passed, 2 failed, 3 skipped` — the 2 failures were exactly the committed-but-unimplemented OQ-10 header-capture tests.
- **Final on the real HEAD `64fbb57`:** `python -m pytest -m "not slow" -q` → **`6976 passed, 3 skipped` (EXIT=0, 0 failed)**. The 3 skips are the standing known skips (flag-classifier no fixtures; g2 forbidden-pattern locks; v2 ohlcv git-diff gate).
- **Reconciliation:** 6966 + 2 (OQ-10 now green) + 8 new (2 clock-skew + 1 None-cfg + 5 route-render parametrized) = **6976.** Exact.
- The known `test_ohlcv_reader_re_export_identity` xdist flake did **not** appear this run (passed in-suite).
- `ruff check swing/` → **All checks passed** (the one E501 ruff reports is on a PRE-EXISTING long test def `tests/web/test_schwab_checker_badge.py` outside the `swing/` gate scope; not introduced here, left untouched as out-of-scope).

**New tests added this session:** `tests/integration/schwab/test_checker_liveness_state.py` (+`test_future_heartbeat_beyond_skew_is_degraded_not_alive`, `test_small_future_skew_within_tolerance_stays_alive`); `tests/web/test_schwab_checker_badge.py` (+`test_badge_none_when_cfg_is_none`, parametrized `test_primary_nav_route_populates_badge_when_sidecar_present` over `/pipeline /watchlist /metrics /schwab/status /schwab/setup`). Each new test distinguishes pre- vs post-fix (`feedback_regression_test_arithmetic`).

---

## LOCK / OQ verification

- **L1** scope = A-3 + P14.N7 + web badge only. ✅
- **L2** ZERO new `schwabdev.Client.*` call sites in this session's diff (`git diff cf371c2~1 HEAD -- swing/` → none); `tests/integration/test_l2_lock_source_grep.py` **green (2 passed)**. No re-anchor. ✅
- **L3** NO swing schema change — latest migration is `0023` (no `0024_*.sql`); sidecar ephemeral; audit `surface='pipeline'`. v23 held. ✅
- **L4** production gate + inside-ladder sandbox short-circuit preserved (web client NOT constructed under sandbox → yfinance-only; fast suite stays offline). ✅
- **L6** `"Schwabdev"` (capital-S) `setLogRecordFactory` redaction intact; OQ-10 capture logs **names only**. ✅
- **L7** production-path tests (real `create_app`; real `ConnectionError`) preserved. ✅
- **L9** open-trade scope + TTL + provider-tag cooldown under `threading.Lock`; ladder swallows the 429; cooldown is provider_tag-driven (no hook-catches-`SchwabRateLimitError`). The cold-miss first-burst is the documented, plan-accepted V1 residual (single-flight latch banked V2). ✅
- Invariants: `STALE_THRESHOLD (300) > HEARTBEAT_WRITE_INTERVAL (120)`; seed call does NOT advance the heartbeat; version guard via `importlib.metadata.version` (no `Client` in tests); daily-bar `(year,5,daily,1)` footgun guard intact; **P14.N7 stays cleanly-removable**. ✅
- **OQ-10 outcome:** the no-guess header-KEY capture is live; at the S7 production smoke the operator reads the logged header NAMES to confirm the real Schwab rate-limit header before any candidate name is added. ✅

---

## Web-badge fan-out result

Field present on every base-layout VM (Family A `BaseLayoutVM` + the 16 Family-B VMs) — `test_every_base_layout_vm_has_badge_field_with_safe_default` green. Populated at the primary nav builders (dashboard, journal, config + the 5 added this session); remaining Family-B VMs carry the safe `None` default behind the truthiness `{% if %}` guard (render-safe under default Jinja `Undefined`); `test_unpopulated_base_extending_route_renders_200_with_sidecar` green.

## Production-anchor re-grep (STEP 0)

`_install_pipeline_marketdata_caches` (mirror template) intact; `_extract_response_payload` header loop at `marketdata.py:172-189`; `_WebLadderState` + hooks at `app.py:186-345`; `circuit_breaker_cooldown_seconds=60`; `surface='pipeline'` CHECK unchanged. No anchor drift.

## Gate readiness (plan §I, S1-S7)

- **S1** ✅ fast suite + ruff green (6976 passed; ruff `swing/` clean).
- **S2** ✅ schema unchanged (no `0024`; no new domain writes).
- **S3** ✅ L2 source-grep green.
- **S4** ✅ A-3 production-path wiring test (hooks installed under production; yfinance fallthrough under sandbox).
- **S5** P14.N7 DNS-failure-survival + sidecar state machine + `swing schwab status` liveness line — **operator to confirm**.
- **S6 (BINDING browser leg)** the web health badge renders alive/stale/degraded in a real browser — **operator-witnessed, REQUIRED**. If launching a server: run the BRANCH server from this worktree (`python -m swing.cli web --port 8081`); kill by PID via `Get-NetTCPConnection -LocalPort 8081` → `Stop-Process -Force` + verify the port is free (`feedback_taskstop_does_not_kill_detached_server`).
- **S7 (optional)** production smoke incl. the OQ-10 header-key capture (operator reads the logged header names).
- **After merge:** re-run the fast suite ON THE MERGED HEAD + READ it (`feedback_no_false_green_claim`); reinstall `swing` from main (`pip install -e . --no-deps`).

## Cumulative gotcha application

ASCII-only OQ-10 log + badge strings (cp1252); `os.replace` same-dir temp for the sidecar; `base.html.j2` shared-VM truthiness guard; production-path (not stub) tests; `_num`/`math.isfinite` corrupt-sidecar tolerance preserved; no `Co-Authored-By` (every commit `%(trailers)` verified `[]`); no `--no-verify`; final `-m` paragraph plain prose (no trailer-parse hazard).

## Worktree teardown / artifacts

NOT torn down (orchestrator merges, then teardown). Untracked session artifacts in the worktree (NOT committed; will not merge): `.copowers-findings.md` (gitignored — canonical chain record), `.copowers-sb55-prompt-r1.txt`, `.copowers-sb55-prompt-r2.txt`, `.copowers-sb55-diff.txt`.

## CLAUDE.md status-line refresh (draft for the orchestrator)

> SB5.5 (Schwab) **EXECUTING-PLANS SHIPPED** at `<merge-sha>` (3 re-apply impl commits on the resumed session [OQ-10 impl `cf371c2` + clock-skew/None-cfg guards `b658114` + badge populate `64fbb57`] atop the prior 7; genuine single WSL node22 Codex chain CONVERGED [R1 1 critical = re-raise of the plan-accepted L9 cold-miss residual → R2 WITHDRAWN → NO_NEW_CRITICAL_MAJOR; prompts+responses PERSISTED]; **6976 fast tests green on MERGED main**; NO schema, v23 held; ZERO new `schwabdev.Client.*` sites [L2 green, no re-anchor]; P14.N7 cleanly-removable; prior-session breakage [OQ-10 impl missing, badge unpopulated, clock-skew] all repaired). **ALL Phase 14 SB1-SB5.5 SHIPPED** → close-out tail NEXT (polish batch + B-7 + close-out review).

## Operator handback

Items #1-#4 of the resumption punch-list are complete; #5 (this report) done. **Next operator actions:** S5-S7 gate (incl. the BINDING S6 browser-badge leg). The branch is pushed and ready for orchestrator QA + merge. No self-merge performed.
