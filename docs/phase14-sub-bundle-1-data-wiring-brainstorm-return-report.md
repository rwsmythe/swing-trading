# Phase 14 Sub-bundle 1 -- Data-wiring -- Brainstorm Return Report

**Status:** Brainstorm SHIPPED. Codex MCP single-chain CONVERGED at R4 NO_NEW_CRITICAL_MAJOR (4 rounds; 1 CRITICAL + 10 MAJOR + 11 MINOR cumulative; ALL CRITICAL + MAJOR RESOLVED in-place).

**Mission:** Produce design spec closing three Phase 14 data-wiring defects -- V2.G3 (VSAT lost Sector/Industry on /dashboard); V2.G4 (Refresh weather chart SPY error); P14.N3 (daily-management Capital % PROVISIONAL badge unexplained). Per dispatch brief at `docs/phase14-sub-bundle-1-data-wiring-brainstorm-dispatch-brief.md` (committed at main `3648e56`).

**Spec:** `docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md` (~810 lines after R4 convergence).

**Branch:** `phase14-sub-bundle-1-data-wiring-brainstorm` (HEAD `af6ad48`); 5 commits ahead of main `3648e56`. ZERO Co-Authored-By trailer drift across all 5 commits per `%(trailers)` inspection.

---

## §1 Final HEAD + commit count breakdown

Branch `phase14-sub-bundle-1-data-wiring-brainstorm` -- 5 commits ahead of main `3648e56`:

| # | SHA | Commit |
|---|---|---|
| 1 | `992d7c6` | brainstorm draft -- pre-Codex (spec scaffold; 809 lines; Sec 9.1 LOCKs honored) |
| 2 | `789c93b` | Codex R1 fixes -- 1C + 5M + 2m resolved in-place |
| 3 | `0a238ba` | Codex R2 fixes -- 0C + 3M + 3m resolved in-place |
| 4 | `7f6f184` | Codex R3 fixes -- 0C + 2M + 4m resolved in-place |
| 5 | `af6ad48` | Codex R4 NO_NEW_CRITICAL_MAJOR convergence -- 0C + 0M + 2m banked non-blocking |

All 5 commits emit ZERO `Co-Authored-By:` trailer lines per `git log main..HEAD --pretty="%(trailers)"`.

---

## §2 Codex round chain summary

| Round | CRITICAL | MAJOR | MINOR | Cumulative | Disposition |
|---|---|---|---|---|---|
| R1 | 1 | 5 | 2 | 1C+5M+2m | All C+M resolved in-place at `789c93b` |
| R2 | 0 | 3 | 3 | 1C+8M+5m | All M resolved in-place at `0a238ba` |
| R3 | 0 | 2 | 4 | 1C+10M+9m | All M resolved in-place at `7f6f184` |
| R4 | 0 | 0 | 2 | 1C+10M+11m | 2 minors banked non-blocking; **NO_NEW_CRITICAL_MAJOR sentinel emitted** at `af6ad48` |

**Convergence shape:** 4 rounds; finding taper 8 -> 6 -> 6 -> 2 (CRITICAL+MAJOR taper 6 -> 3 -> 2 -> 0). On-target per dispatch brief §1.2 LOCK + §5 expectation (2-4 rounds). 45th cumulative C.C lesson #6 validation **NOTABLE** (single chain caught 1 CRITICAL + 10 MAJOR; pre-Codex orchestrator-side review applied all 19+ expansion candidates but Codex still surfaced substantive defects on first read).

**Highlights of Codex's catches (all real defects against shipped production code):**
- **R1.C1**: P14.N3 spec named non-existent `equity_resolver.resolve_live_capital(...)` + non-existent `tile.review_date` field. Actual production names: `resolve_live_capital_denominator_dollars` + `data_asof_session`. Brief-vs-production-function-signature verification gotcha #17 / Expansion #2 refinement directly applies; pre-Codex review applied the lesson but to V2.G4 only (correct catch on dashboard.py:75-77 signature mismatch) and missed the P14.N3 surface.
- **R1.M1**: P14.N3 bool-only badge would render badge=LIVE but capital % still computed against stale floor denominator. Codex prescribed mirroring the canonical `swing/metrics/maturity.py:197-219` denominator-stamping pattern (compare `stored_denom` to fresh via `math.isclose(...)`; recompute util_pct when divergent).
- **R3.M1**: percent-vs-proportion unit mismatch. Initial R1 fix recommended `_compute_position_util_pct` from maturity.py (returns percent already × 100); but the daily-management template multiplies by 100 again. Would have rendered 1500.0% on a 15% utilization. Codex caught it; fix locks `compute_position_capital_utilization` (proportion) from daily_management.py.
- **R3.M2**: `swing/web/routes/dashboard.py` has no module-level logger. Spec's R1-locked `log.warning(...)` would NameError + convert the ValueError degraded path into an uncaught 500. Codex prescribed explicit `import logging; log = logging.getLogger(__name__)` addition.
- **R1.M3** + **R2.M3**: V2.G3 backfill reversibility (DHA/DHC carve-out via SKIP action labels + restore-SQL artifact emission) + strict all-or-nothing semantic LOCK across §4.2 + §4.3 + §4.4 + §4.5.
- **R1.M5**: V2.G4 fix initially preserved the broad-Exception-catch-then-409 pattern that hid the original bug. Codex prescribed narrow `ValueError`-only catch + propagation of programming errors to FastAPI default 500. Anti-pattern lock per the V2.G4 root-cause class.

---

## §3 Spec line count

**~810 lines after R4 convergence** (within dispatch brief target of ~400-600; the +200 line drift reflects the depth required by Codex R1-R3 substantive locks — denominator-stamping pattern + restore-SQL artifact design + logger addition + 3-field VM contract + S5a/S5b operator-gate split. The expansion is content-mandated rather than ceremonial).

---

## §4 Pre-locked operator decisions verbatim verification (Sec 9.1 LOCKs + §1 sub-bundle locks)

| LOCK | Decision | Spec citation | Status |
|---|---|---|---|
| Sec 9.1 Q1 | Sub-bundle sequencing -- data-wiring first | §2.3 | PRESERVED |
| Sec 9.1 Q2 | Serial execution | §2.3 | PRESERVED |
| Sec 9.1 Q6 | Operator-witnessed gate per merge | §2.4 + §10.5 | PRESERVED + EXPANDED (S5 split into S5a/S5b per R3.m4) |
| Sec 9.1 Q7 | Codex chain count per orchestrator discretion | §2.2 | PRESERVED -- single chain at end per gotcha #36 caveat for pure UX/wiring sub-bundles |
| §1.1 | Sub-bundle scope only V2.G3 + V2.G4 + P14.N3 | §2.1 | PRESERVED |
| §1.2 | Codex single chain target 2-4 rounds | §2.2 | ACHIEVED (4 rounds; NO_NEW_CRITICAL_MAJOR) |
| §1.4 | Operator-witnessed gate at merge | §10.5 | PRESERVED |
| §1.5 | Schema v21 LOCKED -- no migration | §2.5 + §12 | PRESERVED + VERIFIED via direct migration file read |
| §1.6 | DHA/DHC legacy carve-out preserved | §2.6 + §4 SKIP_NO_CANDIDATES_ROW path | PRESERVED |

**ZERO deviations from operator-paired LOCKs.**

---

## §5 Open Questions: resolved + deferred

All 10 Open Questions from dispatch brief §3 resolved at brainstorm + locked into spec §14. Summary:

| OQ # | Resolution at brainstorm |
|---|---|
| 1 | V2.G3 Fix A (backfill CLI) RECOMMENDED for V1; Fix B / C / D banked as V2 candidates |
| 2 | V2.G4 root cause is LOCAL call-signature mismatch; NO overlap with V2.G1 chart-renderer concern. V2.G1 stays Sub-bundle 3 scope. |
| 3 | V2.G4 cfg.rs.benchmark_ticker -- request-time resolution already correct; no change |
| 4 | P14.N3 PROVISIONAL is template-rendered (NOT persisted); Fix A applies, B + C not applicable |
| 5 | Test fixture strategy -- TestClient + monkeypatched OhlcvCache + ephemeral SQLite per §11 |
| 6 | Operator-witnessed gate has 7 surfaces (S1-S6 + S5b after R3.m4 split) per §10.5 |
| 7 | Schema migration -- NONE required; Schema v21 LOCKED |
| 8 | Sub-bundle decomposition -- SINGLE writing-plans/executing-plans dispatch for all 3 items |
| 9 | `_thumb_bytes` precedent NOT directly applicable; em-dash placeholder is the text-data analogue |
| 10 | HTMX trinity preserved on existing weather-chart/refresh endpoint; NO new HTMX surfaces |

**None deferred to operator review.** All Codex Round 4 minor findings banked as non-blocking with explicit dispositions.

---

## §6 Codex Major findings ACCEPTED with rationale

**ZERO.** All 1 CRITICAL + 10 MAJOR resolved in-place across R1+R2+R3.

The 2 R4 MINOR findings were absorbed via direct fix at the R4 commit (test-count estimate bumped to 34-36; commit-cadence note added). No findings carry forward to writing-plans phase as accepted-with-rationale.

---

## §7 V2 candidates banked (per dispatch brief §8 #7)

| # | V2 candidate | Source | Trigger condition |
|---|---|---|---|
| 1 | V2.G3 Fix B -- denormalize Sector/Industry on `trades` at trade-entry time via form-handler write (Schema v22+) | Spec §4.2 + §13.2 | Future operator-witnessed gate finds new trades opening with empty sector/industry post-Sub-bundle-1 ship |
| 2 | V2.G3 Fix-1b -- VM-time per-ticker fallback at render time (mirrors PriceCache `_last_close` discipline) | Spec §4.2 + §13.2 | Backfill alone proves insufficient at operator-witnessed gate |
| 3 | V2.G3 Fix C -- union open-trade tickers into `_step_evaluate` Sector/Industry persistence | Spec §4.2 + §13.2 | Alternative architectural V2 path |
| 4 | V2.G3 Fix D -- per-ticker `sector_industry_cache` table (Schema v22+) | Spec §4.2 + §13.2 | Higher-frequency or per-render fallback need |
| 5 | V2.G3 partial-recovery -- relax all-or-nothing to per-column lookup | Spec §4.4 + §13.1 #5 | If R3.M3 strict-all-or-nothing locks too many tickers as SKIP_PARTIAL_EMPTY in operator gate |
| 6 | V2.G4 Fix B -- migrate refresh handler to `read_or_fetch_archive` directly (bypass OhlcvCache) | Spec §5.2 + §13.1 #6 | Cache layer drift |
| 7 | V2.G4 Fix C -- hydrate-then-fetch belt-and-suspenders defense | Spec §5.2 + §13.1 #7 | Fix A proves unstable at operator-witnessed gate |
| 8 | P14.N3 NEW operator-facing "Set capital equity" form surface (manual `account_equity_snapshots` entry) | Spec §13.2 | Operators without Schwab LIVE need a manual clear-condition path |

---

## §8 Forward-binding lessons for writing-plans dispatch

1. **Brief-vs-production-function-signature verification (gotcha #17 / Expansion #2 refinement)** -- pre-Codex review MUST grep the production function's source + verify signature + side-effect contract per the dispatched spec; R1.C1 confirms this expansion catches the largest defects. Writing-plans dispatch SHALL verify `resolve_live_capital_denominator_dollars` + `read_live_policy` + `compute_position_capital_utilization` signatures against current production code at plan-authoring time.
2. **Cumulative regression cascade audit (gotcha #21 / Expansion #13)** -- a fix at one section can introduce a stale-reference cascade at sibling sections. R2.M1 + R2.M2 + R3.m1-m4 all surfaced as cumulative regression follow-ups to R1 fixes. Writing-plans should review the entire plan post-fix at each Codex round + apply grep-sweep discipline.
3. **Percent-vs-proportion unit lock (R3.M1 surfaced)** -- when proposing a fix that consumes an existing helper, READ the helper's docstring + return-value math to verify unit semantics. The daily-management contract uses PROPORTION (0.0-1.0+); the maturity.py contract uses PERCENT (× 100). Writing-plans dispatch SHALL preserve the proportion semantic + cite the binding test.
4. **Module-level logger addition (R3.M2 surfaced)** -- new `log.warning(...)` / `log.exception(...)` calls require an explicit module-level `import logging; log = logging.getLogger(__name__)` addition. Writing-plans SHALL bundle the logger import into the same commit as the new log calls; do NOT split.
5. **Restore-SQL artifact discipline for one-time backfills (R1.M3 surfaced)** -- any one-time backfill helper that issues UPDATEs SHALL emit a restore-SQL artifact at a deterministic path BEFORE the apply step (defense-in-depth against crash post-UPDATE; reversibility). Writing-plans SHALL define the exact path + format + cite the discriminating test.
6. **Strict all-or-nothing vs partial-recovery semantic lock (R2.M3 surfaced)** -- when designing UPDATE flows touching MULTIPLE columns, LOCK the semantic explicitly (AND-empty vs OR-empty WHERE clause; SKIP labels for the off-path; separate diagnostic enumeration). Writing-plans SHALL preserve §4.3 strict all-or-nothing for V1 + bank per-column lookup as V2.
7. **Browser-only HTMX failure surface preservation (cumulative)** -- Sub-bundle 1 does NOT introduce new HTMX surfaces but PRESERVES the existing weather-chart/refresh trinity (HX-Request header, 204 + HX-Redirect, target route registered). Writing-plans SHALL verify no regression.
8. **Programming-error propagation discipline (R2.M2 LOCK)** -- the broad-Exception-then-409 pattern at `swing/web/routes/dashboard.py` is the V2.G4 root-cause class. Writing-plans SHALL preserve narrow `ValueError`-only catch + propagation of TypeError / AttributeError / KeyError / RuntimeError to 500. Discriminating test at §5.6 case #4 asserts this.
9. **Operator-witnessed gate split for behavior-conditional surfaces (R3.m4 surfaced)** -- when the UI behavior depends on state (PROVISIONAL vs LIVE), the operator-witnessed gate SHALL split into per-state cases (S5a + S5b). Writing-plans SHALL preserve the split + add the state-planting fixture instructions to the gate runbook.

---

## §9 CLAUDE.md status-line refresh draft text

Append to CLAUDE.md "Current state" line, prepending to the existing Applied Research Tranche 1 + V2 evaluator state:

> **Current state (2026-05-27 PM #4 + sub-bundle-1-brainstorm SHIPPED, HEAD `af6ad48` on branch `phase14-sub-bundle-1-data-wiring-brainstorm`):** **Phase 14 Sub-bundle 1 (data-wiring) BRAINSTORM SHIPPED + Codex MCP single-chain CONVERGED at R4 NO_NEW_CRITICAL_MAJOR** post 5 commits on the brainstorm branch (1 spec scaffold + R1+R2+R3+R4 fix commits; ZERO Co-Authored-By trailer drift; ~582+ cumulative streak preserved). Spec at `docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md` (~810 lines; 3 data-wiring items V2.G3 + V2.G4 + P14.N3). Sec 9.1 commissioning LOCKs honored: serial first; single Codex chain per Q7 + gotcha #36 caveat; Schema v21 LOCKED (no migration); L2 LOCK preserved. **45th cumulative C.C lesson #6 validation NOTABLE** (Codex caught 1 CRITICAL + 10 MAJOR + 11 MINOR across 4 rounds; ALL CRITICAL + MAJOR resolved in-place; ZERO accepted-with-rationale). Substantive Codex catches: R1.C1 P14.N3 non-existent function name + anchor field; R1.M1 denominator-stamping divergence; R3.M1 percent-vs-proportion unit mismatch (would have rendered 1500.0%); R3.M2 missing module-level logger; R1.M3 + R2.M3 backfill restore-SQL artifact + strict all-or-nothing LOCK; R1.M5 + R2.M2 V2.G4 narrow-exception-handling discipline (propagate programming errors to 500). NO new CLAUDE.md gotchas surfaced this brainstorm. Forward sequence: orchestrator-side QA + return-trip to operator -> writing-plans dispatch.

---

## §10 Sub-bundle decomposition recommendation

**SINGLE writing-plans + executing-plans dispatch** per spec §10.1. The three items cohere around dashboard + daily-management surfaces; no inter-item dependencies; combined surface fits within a single dispatch (~8-12 commits + ~34-36 tests per spec §10.2 + §10.3).

Anticipated commit topology per spec §10.2:
- T-1.1 V2.G3 repo helper + tests
- T-1.2 V2.G3 CLI subcommand + restore-SQL artifact + tests
- T-1.3 (OPTIONAL) V2.G3 Fix-1b VM fallback
- T-2.1 V2.G4 route handler signature fix + logger addition + tests
- T-3.1 P14.N3 VM 3-field extension + template rewrite + tests
- T-4.1 + T-4.2 cross-cutting (L2 LOCK source-grep + ASCII discipline + closer)

---

## §11 Schema impact verdict

**Schema v21 UNCHANGED.** Spec §12 verifies via direct migration file read:
- `trades.sector` + `trades.industry` columns ALREADY EXIST at migration `0012_sector_industry.sql:23-24` (TEXT NOT NULL DEFAULT '')
- `candidates.sector` + `candidates.industry` columns ALREADY EXIST at migration `0012_sector_industry.sql:20-21` (TEXT NOT NULL DEFAULT '')
- `account_equity_snapshots` table ALREADY EXISTS per Phase 9 Sub-bundle C ship
- `equity_resolver.resolve_live_capital_denominator_dollars` ALREADY EXISTS per Phase 11 ship

ZERO `swing/data/migrations/0022_*.sql` files added. Per dispatch brief §1.5 LOCK preserved.

---

## §12 Cumulative gotcha set application summary

Per spec §15.1 -- **6 gotchas APPLIED across the three items + 31 gotchas N/A. ZERO gotchas violated.** Cumulative discipline through 37 gotchas BINDING.

Notable applications:
- **#4 PriceCache `_last_close` ticker-rotation** -- V2.G3 backfill helper consults `candidates` last-known per ticker (one-time scope); Fix-1b extends to render-time fallback.
- **#11 Schema-CHECK + Python-constant + dataclass-validator paired discipline** -- N/A (no CHECK widening); but P14.N3 spec extends to MIRROR the maturity.py denominator-stamping pattern.
- **#17 Brief-vs-production-function-signature verification** -- DIRECTLY APPLIED to V2.G4 root-cause identification AND caught by Codex R1.C1 on P14.N3 surface.
- **#18 + #20 SQL skeleton verification + runtime-binding shape** -- APPLIED to V2.G3 repo helper (dynamic `?` expansion; empty-input short-circuit).
- **#21 Cumulative regression cascade audit** -- Codex R2.M1 + R2.M2 + R3.m1-m4 confirm the expansion's value (R1 fixes introduced stale-reference cascades at sibling sections; R2 swept).
- **#27 Silent-skip-without-audit** -- APPLIED to V2.G4 -- `log.warning` emitted BEFORE the 409 degrade response.
- **#32 ASCII discipline** -- APPLIED to production code + tests + return report; spec + dispatch brief EXCLUDED with rationale (§ usage extensive).
- **#36 Two-Codex-chain default** -- explicit caveat for pure UX/wiring sub-bundles applied; SINGLE chain at end per Sec 9.1 Q7 LOCK.

---

## §13 Worktree teardown status

Worktree at `c:/Users/rwsmy/swing-trading/.worktrees/phase14-sub-bundle-1-data-wiring-brainstorm`. **Worktree PRESERVED for orchestrator-side QA + return-trip to operator.** Teardown is the orchestrator's responsibility post-merge per `feedback_orchestrator_performs_merge` BINDING memory.

5 commits ready for merge to main:
```
af6ad48 docs(phase14-sub-bundle-1-spec): Codex R4 NO_NEW_CRITICAL_MAJOR convergence
7f6f184 docs(phase14-sub-bundle-1-spec): Codex R3 fixes
0a238ba docs(phase14-sub-bundle-1-spec): Codex R2 fixes
789c93b docs(phase14-sub-bundle-1-spec): Codex R1 fixes
992d7c6 docs(phase14-sub-bundle-1-spec): brainstorm draft -- pre-Codex
```

Merge command (orchestrator-executed): `git merge --no-ff phase14-sub-bundle-1-data-wiring-brainstorm`.

---

## §14 ZERO Co-Authored-By footer drift confirmation

`git log main..HEAD --pretty="%(trailers:only=true)"` emits ZERO `Co-Authored-By:` lines across all 5 brainstorm-branch commits. Verified empty trailer slot per commit:

```
af6ad48e6eadbcc08254b64fd81069506d9dec86 [empty]
7f6f1847f8d09be3e7bc3d1e4bbe428edae0d730 [empty]
0a238baece6b328f58e60875f8fa93e1e8a93e0c [empty]
789c93b3f16a28a214772638999e77e7d4ed7e3b [empty]
992d7c6af874a18f80c915e6fa44f1ed21f33855 [empty]
```

**~582+ cumulative ZERO Co-Authored-By trailer drift streak preserved.**

---

*End of brainstorm return report. Phase 14 Sub-bundle 1 data-wiring spec ready for orchestrator-side QA + return-trip to operator + writing-plans dispatch authoring. ZERO operator-decision items pending. ZERO Codex Major findings carried forward as accepted-with-rationale. Cumulative discipline preserved + 45th C.C lesson #6 validation NOTABLE.*
