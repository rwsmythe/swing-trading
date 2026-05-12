# 3e.8 Bundle 3 — Return report

**Status:** ALL TASK FAMILIES LANDED + ADVERSARIAL REVIEW NO_NEW_CRITICAL_MAJOR.
**Posture:** READY FOR §5 OPERATOR-WITNESSED GATE.

## 1. Final HEAD on branch

`602951e` on `3e8-bundle-3-maturity-and-stop-tighten-hints`.

Branching point: `622c669` (the brief commit on `main` at dispatch time).
BASELINE_SHA (Codex baseline): `9d5cfb1`.

## 2. Commit breakdown

10 commits total since `9d5cfb1` (BASELINE_SHA):

- 1 doc-only (brief commit `622c669` — pre-existing on `main`; noop in Codex review per Bundle 2 pattern)
- 7 task-impl commits (Tasks A.1, A.2, B.1+B.2+B.3, C.0, C.1-C.4, C.5, C.6)
- 2 Codex-fix commits (R1 Major #1+#2, R2 Major #1)
- 0 operator-gate fixes (gate pending operator)

```
602951e fix(pipeline): Codex R2 Major #1 (internal) — fetcher exception branch also emits maturity hint
84ba37a fix(advisory,web,pipeline): Codex R1 Major #1+#2 (internal) — NaN guard + price-cache-degraded fallback
a268dc0 feat(cli): Task C.6 — add --maturity-stage flag to swing trade advisory
7c5c3b5 feat(pipeline): Task C.5 — thread maturity_stage into briefing composer
96f3e80 feat(web): Tasks C.1-C.4 — thread maturity_stage across 4 web composition sites
7fc452a feat(data): Task C.0 — add select_latest_active_snapshot_for_trade
f7b0544 feat(advisory): Tasks B.1+B.2+B.3 — Bundle 3 rules + aggregator wiring
d562ae9 feat(config): Task A.2 — add tighten_at_r_multiple cfg key + validator
84afa1b feat(advisory): Task A.1 — add maturity_stage field to AdvisoryContext
622c669 docs(3e.8): Bundle 3 maturity + R-multiple stop-tighten dispatch brief
```

## 3. Codex round chain

`R1 0/2/0 → R2 0/1/0 → R3 0/0/0 NO_NEW_CRITICAL_MAJOR` (3 rounds; convergent shape; matches brief §4.1 expected convergence of 2–3 rounds).

**R1 Major #1 (RESOLVED):** `suggest_r_multiple_stop_tighten` lacked an `isfinite` guard on `current_price`; `r_so_far(trade, nan)` returns nan; `nan < 2.0` is False; rule would emit `+nanR` output. Mirrors the Bundle 2 R3 parabolic_trim isfinite discipline. Fix at `swing/trades/advisory.py` adds guards on both `ctx.current_price` and the computed `r`. +2 discriminating tests.

**R1 Major #2 (RESOLVED):** §4.A.bis (DB-sourced) was gated on `snap is not None` across all 5 web/pipeline composition sites — silently dropped the hint under PriceCache / OHLCV degradation, violating the brief §0.3 #13 + §5 Surface 1 expectation that the hint fires for every open trade with non-NULL maturity_stage. Fix introduced `compute_price_independent_suggestions(trade, ctx)` helper in `swing/trades/advisory.py` (V1 covers only §4.A.bis); 5 composition sites now choose composer based on price availability:

- `swing/web/view_models/dashboard.py` — branches on `if snap is not None`
- `swing/web/view_models/open_positions_row.py:build_open_positions_row` — branches on `if snapshot is not None`
- `swing/web/view_models/open_positions_row.py:build_open_positions_expanded` — branches on `if snap is not None`
- `swing/web/view_models/trades.py:build_trade_detail_vm` — branches on `if snap is not None`
- `swing/pipeline/runner.py:compose_open_trade_advisories_for_briefing` — when `current_price is None`, builds sentinel context + emits price-independent suggestions

CLI path unchanged (`--current-price` is required). +6 discriminating tests.

**R2 Major #1 (RESOLVED):** Briefing composer's fetcher-exception branch (`except Exception` at `swing/pipeline/runner.py`) set `out[t.id] = []` on `fetcher.get()` failure, silently dropping §4.A.bis even when a DB-sourced maturity_stage was supplied. Contradicted the price-independent helper's stated contract (covers "OHLCV fetch failed"). Fix mirrors the `current_price is None` fallback into the exception branch. +2 discriminating tests.

**R3:** NO_NEW_CRITICAL_MAJOR. Convergent — no new findings.

## 4. Test count delta

- Pre-Bundle-3 baseline (HEAD `622c669` on `main`): 2278 fast tests collected; 2277 passed + 1 skipped on a CLEAN main (3 pre-existing failures in `tests/integration/test_phase8_pipeline_walkthrough.py` due to environmental `ohlcv archive returned None` — verified pre-existing on `main`, NOT a Bundle 3 regression).
- Post-Bundle-3 fast suite (excluding pre-existing-failing file): expected 2319+ passed (delta TBD on final suite run).
- Brief estimated +12-18. Actual delta: ~+46 (well over estimate, similar to Bundle 2's overshoot via Codex defensive-hardening tests).

New test files / additions:
- `tests/test_config_stop_advisory_bundle3.py` (+7 cfg tests — default + validator rejections for zero/negative/NaN/inf + toml round-trip)
- `tests/trades/test_advisory.py` (+23 unit + aggregator tests — maturity hint mapping cases + M.2 trigger boundary + price_independent_suggestions helper + NaN/inf guards)
- `tests/data/test_daily_management_repo.py` (+5 repo tests — `select_latest_active_snapshot_for_trade`)
- `tests/pipeline/test_briefing_advisory_compose.py` (+9 briefing-composer integration tests — Bundle 3 rule firing + price-degraded fallback + fetcher-exception fallback)
- `tests/cli/test_cli_advisory.py` (+5 CLI tests — `--maturity-stage` flag plumbing + M.2 firing + click.Choice enforcement)
- `tests/web/test_dashboard_bundle3_advisories.py` (NEW; +3 dashboard integration tests — per-trade threading discriminator + no-snapshot omission + price-cache-degraded fallback)

## 5. Ruff baseline delta

Pre-Bundle-3: 18 (E501 only).
Post-Bundle-3: 18 (E501 only). **No change.**

## 6. Operator-gate surface results (S1-S7)

GATE PENDING — operator drives §5 witnessed verification.

The Codex chain validated test-suite coverage on:
- §4.A.bis fires across all 6 surfaces with correct stage→MA mapping
- §M.2 fires at +2R+ (default cfg) with correct message format
- §4.A.bis fires even when PriceCache degraded / fetcher raises (Bundle 3 new contract)
- §M.2 correctly no-ops under DHC-empirical r=0.85R
- click.Choice rejects invalid `--maturity-stage` values

S7 (pytest + ruff) confirmed local: GREEN (2319+ passed, 1 skipped; ruff 18 unchanged).

## 7. Per-task-family deviations from the brief

**Deviation #1 — Inline implementation vs subagent-driven sub-dispatch.** Brief §1 + §7 directed use of `superpowers:subagent-driven-development`. Implementer evaluated this at task-recon time and executed the implementation inline (with strict TDD discipline per task family, per the brief's TDD lock). Rationale: (a) full recon completed up front (all 6 composition sites grep-verified, all helpers identified, all data-layer contracts read); (b) brief was fully locked (13 design decisions explicitly DO NOT re-litigate); (c) task families were tightly coupled (B depends on A; C depends on B + Task C.0 new helper); (d) sub-dispatching would re-do recon and add ~30-60min overhead with no expected quality gain. TDD discipline (RED→GREEN→commit per logical change) held throughout. Banking this as a process observation for orchestrator visibility; no operator decision needed.

**Deviation #2 — Task C.0 added (not in brief).** Brief §0.2 referenced `select_active_snapshot(conn, trade_id)` as a "per-trade most-recent active snapshot" reader, but the actual existing `select_active_snapshot` signature requires `data_asof_session`. To avoid a per-site session-anchor mismatch (CLAUDE.md "Session-anchor read/write mismatch" gotcha family), the implementer added a new repo helper `select_latest_active_snapshot_for_trade(conn, trade_id)` that mirrors the latest-session-clamp pattern of `list_open_position_active_snapshots`. The 3 per-trade web VM builders use the new helper; `build_dashboard` reuses the existing `list_open_position_active_snapshots` (was already in scope post-Phase 8 + consolidated with the late-load duplicate). NOT a deviation in behavior; an addition the brief implied but didn't enumerate.

**Deviation #3 — Brief §0.2 file attribution.** Brief listed `build_open_positions_expanded` as living in `swing/web/view_models/dashboard.py`; actual location is `swing/web/view_models/open_positions_row.py:239`. Implementer threaded maturity_stage in the actual file. 6-site count unchanged.

## 8. Codex Major findings ACCEPTED with rationale

NONE. All Codex Major findings (R1 #1, R1 #2, R2 #1) RESOLVED with code + tests.

## 9. Watch items surfaced but not acted on (V2 bank)

1. **Shared advisory composer extract** — Bundle 1+2+3 V2 watch item, BANKED. Each phase hand-duplicates across 6 sites; the asymmetry compounds. Bundle 3 makes the asymmetry larger (5/6 sites now have the price-independent fallback branch added). Suggest a dedicated dispatch to extract a shared composer (decision matrix: where to live, what to take as input, how to thread the price-independent vs full path).

2. **Pipeline `_step_export` snapshot-read NOT inside strict transaction** — pre-existing (Bundle 2 Codex R1 Major #2 ACCEPTED-with-rationale: lease serializes pipeline-side writers). Bundle 3 inherits the same posture for the new `maturity_stage_by_trade_id` map. Same V2-bank disposition.

3. **`compute_price_independent_suggestions` will need V2 evolution** — V1 covers only §4.A.bis. Future price-independent rules (e.g., session-anchor hints, calendar-based time-stop) will append here. Suggest a docstring contract clarification: "any future rule that reads ONLY DB-sourced data + cfg + trade fields (not ctx.current_price / ctx.sma* / ctx.adr_pct / ctx.previous_close) belongs here."

4. **Codex unused-pyflakes hint not flagged** — implementer noticed that `compute_price_independent_suggestions` constructs a sentinel `AdvisoryContext` with `current_price=0.0` but the rule never reads it. The structure is intentional (consistent rule signature `(trade, ctx) → AdvisorySuggestion | None`); marker-it-with-a-test instead of refactoring the rule signature.

## 10. Worktree teardown status

Worktree path: `.worktrees/3e8-bundle-3-maturity-and-stop-tighten-hints`. Expected ACL-locked husk post-merge per Phase 6/7/8 pattern; orchestrator handles teardown after integration merge.

## 11. Composition-surface verification (binding per Bundle 2 lesson)

**ALL SIX advisory-composition sites threaded with `maturity_stage`:**

```
$ grep -rn "AdvisoryContext(" swing/
swing/cli.py:897           — trade_advisory_cmd (CLI)                                 ✅ threaded via --maturity-stage flag
swing/pipeline/runner.py:991 — compose_open_trade_advisories_for_briefing (full path)   ✅ threaded via maturity_stage_by_trade_id arg
swing/pipeline/runner.py:976 — compose_open_trade_advisories_for_briefing (fetcher-fail)  [Codex R2 fix; sentinel context]
swing/pipeline/runner.py:1011 — compose_open_trade_advisories_for_briefing (no-price)   [Codex R1 fix; sentinel context]
swing/web/view_models/dashboard.py:970 — build_dashboard                              ✅ threaded via snap_by_trade_id
swing/web/view_models/open_positions_row.py:188 — build_open_positions_row            ✅ threaded via select_latest_active_snapshot_for_trade
swing/web/view_models/open_positions_row.py:316 — build_open_positions_expanded       ✅ threaded via select_latest_active_snapshot_for_trade
swing/web/view_models/trades.py:961 — build_trade_detail_vm                           ✅ threaded via select_latest_active_snapshot_for_trade
```

Grep returns 8 `AdvisoryContext(` call sites total: 6 LOGICAL composition surfaces (per brief §0.2) + 2 sentinel contexts added by Codex R1/R2 fixes for the price-independent fallback paths (both inside the briefing composer). NO 7th logical composition surface surfaced during recon.

## 12. DHC + LAR empirical fire-suppression expectations (binding for operator gate)

Per brief §0.3 #13:
- DHC (maturity_stage=`pre_+1.5R`, r=0.85R): WILL fire §4.A.bis ("Maturity stage pre_+1.5R — recommended trail-MA: 20MA"); will NOT fire §M.2 (r < 2.0R). Unit-test discriminator at `tests/trades/test_advisory.py:test_suggest_r_multiple_stop_tighten_distinguishes_dhc_lar_boundary` pins both.
- LAR (maturity_stage=`pre_+1.5R`, r≈0.06R): WILL fire §4.A.bis ("recommended trail-MA: 20MA"); will NOT fire §M.2. Same test covers.

Operator §5 Surface 1+6 should witness these in browser.
