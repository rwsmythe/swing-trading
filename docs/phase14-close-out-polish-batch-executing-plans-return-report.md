# Phase 14 Close-Out Polish Batch — Executing-Plans Return Report

**Branch:** `phase14-close-out-polish-batch-executing-plans` (worktree at
`.worktrees/phase14-close-out-polish-batch-executing-plans/`)
**Branched from:** `55e3f26` (main HEAD at dispatch)
**Final branch HEAD:** `14f79f6` (+ this return-report commit)
**Status:** ALL 5 slices SHIPPED on the branch. Codex single chain CONVERGED
(R1 → R2 NO_NEW_CRITICAL_MAJOR). Fast suite green on the branch. NO schema
change (v23 held). L2-LOCK green. Read-mostly.

> **⚠️ OPERATOR ACTION REQUIRED — `main` was contaminated mid-session.** A
> degraded-harness cwd-revert (see §"Incident") caused the orchestrator's
> Codex-R1 Minor fix commit (`3b0f5ff`, a 2-line test-comment change against
> baseline) to land on **`main`** instead of the branch. **`main` is now at
> `3b0f5ff` and must be reset to `55e3f26`** before merging this branch. The
> real Minor fix is correctly committed on the branch (`14f79f6`). I was
> denied permission to `git reset --hard main` (correct guardrail); the
> operator/orchestrator must do it. Full detail + exact recovery command in
> §"Incident".

---

## §1 Per-commit list (23 commits, 55e3f26..14f79f6) + Codex-round attribution

All 23 commits authored BEFORE the Codex chain except the last (the R1-Minor
fix). ZERO Co-Authored-By trailers across all 23 (verified via
`git log --format='%(trailers)'`).

**Slice A — A-7 Schwab badge UNKNOWN render**
- `ce3377e` fix(web): render UNKNOWN Schwab badge when checker expected (A-7)
- `38f029c` test(web): topbar renders UNKNOWN Schwab badge in unseeded default state (A-7)

**Slice B — P14.N1 dual-table thumbnails**
- `d1c8ef0` refactor(web): extract shared thumbnail render cap for dashboard reuse
- `9595713` feat(web): lazy candlestick thumbnail on open-positions rows
- `d5b1635` feat(web): render-direct lazy thumbnail route for hyp-rec rows
- `c8cab2d` feat(web): lazy ticker thumbnail on hyp-rec rows
- `dd31227` fix(web): align row-replacement colspans with the new Chart column
- `2c5e075` test(web): shift hyp-rec pivot cell index for the new Chart column
  (caught at the Slice-B full-suite gate — a pre-existing test that counted
  cells by index)

**Slice C — A-1 ≥200-bar fetch window**
- `fa756c9` fix(pipeline): widen market-weather/chart fetch window (_bars_or_none, runner.py:2763) — C.1
- `ee5fafa` fix(pipeline): widen classifier/per-ticker OHLCV window (runner.py:2694) — **C.1b, own revertible commit**
- `c92ece2` fix(pipeline): import MIN_CALENDAR_DAYS_FOR_MA200 lazily to break ohlcv_cache import cycle — see §4
- `596610f` fix(web): weather-chart refresh fetches >=200 bars (dashboard.py:94) — C.2
- `9c5a020` fix(web): widen JIT + hyp-rec thumbnail fetch window (chart_jit.py:117 + the hyp-rec route) — C.3 / OQ-6
- `df982ab` test(web): accept window_days in weather-refresh ohlcv stub (caught at the Slice-C full-suite gate)

**Slice D — cosmetics**
- `bafbbe5` fix(web): reposition VCP contraction labels off the price-tick column (A-2)
- `1afbea6` style(pipeline): isort the lazy ohlcv_cache import group (ruff gate-fix)
- `2b77572` refactor(web): rename _bulz_* risk/reward helpers to general names (A-4)
- `c61b2ca` fix(web): process-grade-trend chart visible via accent token in dark mode (A-6)

**Slice E — group-(a)**
- `0470d45` fix(web): daily-management provisional default False + accurate tooltip (C-1/C-2)
- `592b0ac` fix(cli): wrap backfill artifact-write OSError as ClickException (C-3)
- `688dab3` test(cli): assert BEGIN IMMEDIATE ordering vs SELECT/UPDATE (C-5)
- `1f5b2ed` test(research): pin ohlcv-reader re-export test to an xdist group (C-19)

**Codex R1 Minor fix**
- `14f79f6` test(web): finish A-4 rename in test comments (risk/reward zones, not BULZ)

---

## §2 Codex single chain (OQ-8) — CONVERGED

Transport: copowers v2.0.3 WSL fallback. `command -v codex` →
`/home/rwsmythe/.local/node22/bin/codex` (codex-cli 0.135.0) — verified the
node22 binary (NOT the `/mnt/c` npm shim) before the chain. Pre-generated diff
(`git diff 55e3f26 HEAD`) at `.copowers-diff.txt`; Codex told NOT to run git
(WSL can't resolve the worktree's Windows `.git`). Full prompts + responses
persisted on disk at `.copowers-findings.md` (gitignored), incl. both
`### Verdict` lines.

- **R1** (`-s read-only --skip-git-repo-check -C <worktree>`): ZERO Critical,
  ZERO Major, 1 Minor (A-4 rename hygiene — a leftover "Step 4/5: BULZ
  risk/reward zones" FEATURE-LABEL comment in test_charts.py; the BULZ *ticker*
  fixtures correctly preserved). Verdict: **NO_NEW_CRITICAL_MAJOR**. (114,684
  tokens.)
- Minor FIXED on the branch (`14f79f6`); zero non-fixture BULZ tokens remain.
- **R2** (`resume --last`): re-review after the fix. NO new Critical/Major;
  Codex cited real worktree changes (recommendations.py render-direct comment,
  open_positions_row lazy `<td>`, expanded colspan=10) confirming it reviewed
  the actual diff. Verdict: **NO_NEW_CRITICAL_MAJOR**. (165,802 tokens.)

**Codex Majors accepted: ZERO. Critical: ZERO.** Only 1 Minor (test-comment
hygiene), fixed. No finding required a schema change or a new
`schwabdev.Client.*` call site.

---

## §3 Per-slice completion

| Slice | Item | Status |
|---|---|---|
| A | A-7 UNKNOWN badge gated on `_is_ladder_active`; reuse `evaluate_liveness_state`+`_BADGE_MAP`; ASCII reason-text; UNSEEDED topbar witness | ✓ |
| B | P14.N1 open-positions (journal route reuse) + hyp-rec (NEW render-direct `/hyp-recs/{ticker}/thumbnail`) thumbnails; shared `thumbnail_render.py` cap; Task B.6 colspan alignment both tables | ✓ |
| C | A-1 `MIN_CALENDAR_DAYS_FOR_MA200=300` at runner.py:2763 (C.1) + runner.py:2694 (C.1b own commit) + dashboard.py:94 (C.2) + chart_jit.py:117 + hyp-rec route (C.3/OQ-6) | ✓ |
| D | A-2 (VCP labels x 0.98→0.74, mathtext-free) + A-4 (`_bulz_*`→`_rr_*`, NOT the BULZ ticker fixtures) + A-6 (process-grade dark-mode CSS via `var(--accent)`) | ✓ |
| E | C-1 (provisional default→False) + C-2 (tooltip wording) + C-3 (OSError→ClickException) + C-5 (BEGIN IMMEDIATE ordering) + C-19 (xdist_group) | ✓ |

**C-6 DEFERRED — NOT implemented** (Task E.0). Re-confirmed at executing-plans
STEP 0: `backfill_trades_sector_industry.py:104-131` holds `BEGIN IMMEDIATE`
across re-SELECT + `_emit_restore_sql` (FS write) + `_apply_updates` + COMMIT.
Narrowing the lock to exclude the FS write reopens either the TOCTOU
(re-SELECT/emit before the lock) or breaks crash-safety ordering (FS write
after COMMIT). Genuine invariant; banked follow-up, not this batch.

---

## §4 Re-grep findings + the circular-import discovery

- **STEP-0 re-grep:** all plan §B anchors verified against the worktree;
  no material drift. (A-6 template lives at `templates/metrics/
  process_grade_trend.html.j2`, not `partials/` — plan §3 path corrected;
  classes confirmed.)
- **Circular import (NEW, fixed `c92ece2`):** the plan asserted a module-top
  `from swing.web.ohlcv_cache import MIN_CALENDAR_DAYS_FOR_MA200` in runner.py
  was import-safe. It is NOT: `ohlcv_cache` imports `swing.pipeline` →
  `pipeline/__init__` imports `runner` → runner re-imports the partially-
  initialized `ohlcv_cache` → `ImportError` on standalone
  `import swing.web.ohlcv_cache`. Fixed by importing the constant LAZILY inside
  `_step_charts` (matching runner's existing lazy-import pattern). Verified
  `import swing.web.ohlcv_cache`, `swing.web.routes.dashboard`,
  `swing.pipeline.runner` all import standalone. This is a forward-binding
  lesson (see §M-style note below).

---

## §5 Test surface (production-path; #15 / L6)

- **Baseline:** 6976 passed, 3 skipped (worktree branch-point == main 55e3f26).
- **Net new tests:** +28 (full suite reached **7004 passed, 3 skipped** at
  `1f5b2ed`, the pre-Minor-fix HEAD). The Minor fix (`14f79f6`) is a test-
  comment-only change (no test count change). **Re-confirmed on branch HEAD
  `14f79f6`: 7004 passed, 3 skipped** (157.98s), `ruff check swing/` clean
  (per feedback_no_false_green_claim — re-run on the merged-Minor-fix HEAD).
- **A-7:** VM-level UNKNOWN/None branches (SimpleNamespace + real Config) +
  TestClient topbar UNSEEDED witness (`_construct_web_schwab_client`→None,
  isolated HOME, assert warn badge AND no sidecar created) + sandbox/ladder-
  disabled hidden + the L2-LOCK grep test. Two pre-existing tests that encoded
  the OLD hide-when-no-sidecar behavior were updated to the new semantics.
- **P14.N1:** real-route tests (open-positions reuses `/journal/.../thumbnail`;
  hyp-rec hits the new `/hyp-recs/{ticker}/thumbnail`) driving the real handler
  + real renderer + real Jinja partial (only the OHLCV-fetch boundary stubbed);
  the hyp-rec no-`chart_renders`-write assertion (L5); column-count regressions
  on BOTH tables (header == compact-row == expanded colspan); the
  `_row_error_colspan` 10/11 regression; the hyp-rec `<tr>`-trigger-free
  regression re-run; the invalid-ticker-no-fetch guard.
- **A-1:** `MIN_CALENDAR_DAYS_FOR_MA200 >= 290`; window reaches `get_or_fetch`
  AND `len(bars) >= 200` reaches the real `render_market_weather_svg` (spy) on
  the real `_step_charts` path AND the real dashboard refresh handler; the JIT
  + hyp-rec window assertions.
- **A-2:** ax.text capture (x ≤ 0.75 off the tick column; mathtext-free "pct",
  no $/^/_). **A-4:** import + rename completeness (ZERO `_bulz`/`bulz` feature
  tokens in `swing/`; BULZ ticker fixtures preserved). **A-6:** CSS-presence.
- **group-(a):** C-1 dataclass default; C-2 tooltip substring; C-3
  ClickException; C-5 ordering (distinguishes by construction); C-19 isolation
  + `-n auto` co-residency (928 passed, no flake).

---

## §6 LOCK + OQ verbatim verification

- **L1** scope = the 5 slices only; NO B-7 / close-out review / Phase 15+ / A-5. ✓
- **L2** NO schema change: `EXPECTED_SCHEMA_VERSION = 23` unchanged; no
  `0024_*.sql`; no `chart_renders`/domain write on the thumbnail path
  (hyp-rec route is render-direct; asserted). ✓
- **L3 (L2-LOCK)** A-7 adds ZERO new `schwabdev.Client.*` call sites
  (`_is_ladder_active` is a pure getattr config read);
  `tests/integration/test_l2_lock_source_grep.py` green. ✓
- **L4** REUSE not re-implement: both existing renderers reused;
  `thumbnail_render.py` is a DRY extraction (journal imports the SAME semaphore
  instance); A-6 reuses `var(--accent)`; A-7 reuses `evaluate_liveness_state` +
  `_BADGE_MAP`. ✓
- **L5** read-mostly: ZERO swing-domain writes; hyp-rec thumbnail render-direct
  (no `chart_renders` write — asserted). ✓
- **L6** production-path tests (#15): real route/VM/cache/topbar/renderer,
  only the external OHLCV-fetch boundary stubbed. ✓
- **L7** ASCII (A-7 reason text + C-2/C-3 text); no `setLogRecordFactory`
  change. ✓
- **OQ-1..8** honored (OQ-5 BOTH tables; OQ-6 JIT widened; OQ-8 single chain).
  C-6 deferred (OQ-4). ✓

---

## §7 Incident — `main` contamination + recovery (degraded-harness)

A degraded-harness cwd-revert (the foreground shell silently reverted from the
worktree to the primary repo on `main`) occurred during the Codex-R1 →
Minor-fix transition. Consequences + recovery:
1. The orchestrator wrote/committed the R1-Minor fix while cwd was the primary
   repo on `main`, landing commit `3b0f5ff` (a 2-line test-comment change
   against baseline test_charts.py) on **`main`**. (`main`: 55e3f26 → 3b0f5ff.)
2. **All 21+ implementation commits were never on `main`; they are intact on
   the branch** (`git worktree list` confirms the worktree is on
   `phase14-close-out-polish-batch-executing-plans`; `git log` shows all
   commits). NO work was lost.
3. Recovery performed: switched back to the worktree (explicit absolute `cd`),
   verified the branch + all files on disk, applied the A-4 Minor fix CORRECTLY
   on the branch (`14f79f6`), and ran R2 against the branch.
4. **REMAINING:** `main` must be reset to `55e3f26` (drop the orphan
   `3b0f5ff`). The reset was DENIED to me (correct guardrail for the default
   branch). **Operator/orchestrator command:** in the primary repo,
   `git checkout main && git reset --hard 55e3f26` (verified safe: `3b0f5ff`
   is solely the misplaced 2-line comment change; the real Minor fix is on the
   branch). Then merge the branch as usual.

Forward-binding lesson (per feedback_degraded_harness_sequential_tool_calls):
background shells start in the primary repo, and the foreground cwd can revert
mid-session — EVERY git/test command in a worktree session must use an explicit
absolute `cd <worktree> &&` (or `--git-dir`/`-C`), and `git rev-parse HEAD` /
`git branch --show-current` must be re-verified before any commit.

---

## §8 Gate readiness (operator S1–S8)

- **S1** fast suite + ruff green on the branch: **7004 passed, 3 skipped** on
  branch HEAD `14f79f6` (re-run on the merged-Minor-fix HEAD per
  feedback_no_false_green_claim); `ruff check swing/` clean. ✓
- **S2** schema unchanged (v23; no `0024`; no new `chart_renders`/domain write
  on the thumbnail path). ✓
- **S3** L2 source-grep green (A-7 zero new `schwabdev.Client.` sites). ✓
- **S4 (BINDING browser)** open-positions AND hyp-rec thumbnails render with
  real rows; no-coverage rows degrade cleanly; both column counts align —
  OPERATOR to witness.
- **S5 (A-1)** ≥200-bar regression green; OPERATOR confirms the market-weather
  200-MA renders as a full line.
- **S6 (BINDING browser)** VCP labels uncrowded; rename behavior-neutral; the
  process-grade-trend chart visible in DARK mode — OPERATOR to witness.
- **S7 (A-7, BINDING browser — the UNSEEDED default-state witness)** under
  production + ladder + NO sidecar + no constructible client, the topbar shows
  the `Schwab?` UNKNOWN (warn) badge — OPERATOR to witness (degraded production
  tokens reproduce this naturally).
- **S8** trailers `[]`; ZERO Co-Authored-By (verified across all 23 commits). ✓

**Post-merge (orchestrator):** reset `main` to 55e3f26 FIRST (§7), then merge;
re-run the fast suite ON THE MERGED HEAD and READ it
(feedback_no_false_green_claim); `pip install -e . --no-deps`.

---

## §9 Worktree teardown
Worktree LEFT INTACT for orchestrator QA + merge (branch `14f79f6` + the
return-report commit). Scratch files (`.copowers-diff.txt`,
`.copowers-r1-prompt.txt`, `.copowers-r2-prompt.txt`) are untracked and will be
removed at teardown; `.copowers-findings.md` is gitignored and retained for QA.

---

## §10 CLAUDE.md status-line refresh (draft for the orchestrator)

> close-out polish batch **EXECUTING-PLANS SHIPPED on-branch at `14f79f6`**
> (23 commits across 5 serial slices A-7/P14.N1-dual-table/A-1/cosmetics/
> group-(a); genuine single WSL Codex chain CONVERGED R1→R2
> NO_NEW_CRITICAL_MAJOR, 1 minor fixed, ZERO crit/major; NO schema v23 held;
> L2 green [A-7 zero new `schwabdev.Client.` sites]; read-mostly [hyp-rec
> thumbnail render-direct, no `chart_renders` write]; +28 tests → 7004; C-6
> deferred [TOCTOU]; runner.py:2694 A-1 widening its own revertible commit;
> circular-import lazy-import fix; **NOTE: `main` needs reset to 55e3f26 before
> merge — see return report §7 incident**).
