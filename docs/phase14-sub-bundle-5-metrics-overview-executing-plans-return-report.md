# Phase 14 Sub-bundle 5 (FINAL) — Metrics Overview (P14.N5) — Executing-Plans Return Report

**Status:** COMPLETE — ready for orchestrator QA + operator-witnessed render gate (S3). NOT self-merged.
**Branch:** `phase14-sub-bundle-5-metrics-overview-executing-plans` (from main HEAD `3986540`).
**Worktree:** `.worktrees/phase14-sub-bundle-5-metrics-overview-executing-plans`.
**CLI in worktree:** `python -m swing.cli` (editable install points at main).

---

## §1 Final HEAD + commit-count breakdown

**Final HEAD: `c0201e8`** (7 commits on the branch; baseline `3986540`).

| # | SHA | Task | Stem |
|---|-----|------|------|
| 1 | `81a5cd2` | T-5.1 | feat(web): pure inline-SVG sparkline points helper |
| 2 | `f143f5c` | T-5.2.a | feat(web): overview fields on MetricsIndexSurface + card holder + formatter |
| 3 | `dd140c2` | T-5.2.b | feat(web): trend-surface extractors w/ per-surface sparkline thresholds |
| 4 | `f60e629` | T-5.2.c | feat(web): headline-only extractors for the six point-estimate surfaces |
| 5 | `675d68e` | T-5.2.d | feat(web): widen build_metrics_index_vm to (cfg, conn) + route + 3 call-sites (ATOMIC) |
| 6 | `c16d187` | T-5.3 | feat(web): render the metrics overview card grid with inline sparklines |
| 7 | `c0201e8` | T-5.4 gate-fix | fix(web): semantic theme tokens in overview CSS + harden sparkline min_points |

Commit 7 is the post-suite/post-Codex gate-fix (theme-CSS A.3 + the Codex R1 MINOR). T-5.4 itself shipped NO production code beyond that fix (verification + this report).

---

## §2 Codex single chain (OQ-7) — CONVERGED

**ONE chain, run via the WSL Codex CLI fallback** (`codex-cli 0.135.0`; MCP dead in the VS Code extension). Read-only, reads the worktree from disk; diff pre-generated on Windows (WSL cannot resolve the worktree `.git`).

| Round | Transport | Verdict | New CRIT | New MAJOR | Other |
|-------|-----------|---------|----------|-----------|-------|
| R1 | `codex exec -s read-only --skip-git-repo-check - < r1-prompt.md` | **NO_NEW_CRITICAL_MAJOR** | 0 | 0 | 1 MINOR (min_points<2 ZeroDivision risk) |
| R2 | `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check - < r2-prompt.md` | **NO_NEW_CRITICAL_MAJOR** | 0 | 0 | 0 findings (post-fix confirm) |

**Convergent shape:** R1 converged immediately (zero crit/major). The single MINOR (defensive `min_points >= 2` guard) was fixed in commit 7; R2 confirmed convergence holds on the post-fix state with zero findings. Cap suspended per `feedback_codex_round_limit_suspended`; chain stopped at convergence (no padding).

**On-disk EVIDENCE (gitignored, `.tmp-codex-review/`, NOT committed):** `r1-prompt.md`, `r1-response.md` (ends `NO_NEW_CRITICAL_MAJOR`), `r2-prompt.md`, `r2-response.md` (ends `NO_NEW_CRITICAL_MAJOR`), `diff.patch`. Both rounds genuinely invoked codex via WSL (the responses show codex attempting `python -m pytest` from the worktree and the `exec` tool traces — proving it ran against the on-disk worktree).

---

## §3 Per-task completion summary

- **T-5.1** — `swing/web/view_models/metrics/sparkline.py`: pure `build_sparkline_points(values, *, width=100, height=30, pad=2.0, min_points=2) -> str | None`. X over the ORIGINAL index (None gaps do not compress time); Y normalised over defined min/max, inverted (SVG y-down); flat -> mid-line; `< min_points` defined -> None; `min_points<2` -> ValueError (R1 MINOR); 2-dp; ASCII-only; NO matplotlib / NO `_RENDER_LOCK`. **10 tests.**
- **T-5.2.a** — `MetricsIndexSurface` +6 leaf fields; `_OverviewCard`; `_ASCII_SUBSTITUTIONS` (built via `chr(0xXXXX)` so the source file is pure ASCII); central `_ascii()`; `_format_metric_value`; ASCII-ified the one non-ASCII `_SURFACES` description + all docstring/comment `§` glyphs. **3 tests.**
- **T-5.2.b** — `_extract_capital_friction` / `_extract_identification_funnel` / `_extract_process_grade_trend`. Capital gate = `TREND_MIN_RUNS=5` (capital.py), funnel = `TREND_MIN_RUNS=10` (funnel.py), process-grade = `series.drawability_text == "rolling line drawable"`. process-grade uses a SINGLE `compute_process_grade_trend(conn)` (raw `line_points`/`rendered_value`/`drawability_text`), NOT the pre-scaled VM string. **5 tests** (incl. the 7-run discriminator).
- **T-5.2.c** — the 6 headline-only extractors + `DEVIATION_HEADLINE_COHORT="Near-A+ defensible: extension test"` + `PATTERN_HEADLINE_CLASS="vcp"` (OQ-4 defaults, shipped as-planned; operator may re-point in one place). **5 tests.**
- **T-5.2.d** — widened `build_metrics_index_vm(conn)` -> `(cfg, conn)`; `_enrich_surface` dispatch + per-card try/except isolation + central `_ascii` chokepoint; ROUTE call-site widened in the SAME commit (Codex R1 MAJOR #2 from writing-plans); the 3 existing call-site tests updated (2 mechanical, 1 constructed-Config). **2 tests.** Cascade-audit: `git grep build_metrics_index_vm(` shows only the def + route + 4 test call-sites.
- **T-5.3** — template `<ul class="metrics-tiles">` -> 9-card grid (label + headline-or-suppressed + inline `<svg><polyline>` on the 3 trend cards else suppressed caption + drill-down link); CSS card-grid + sparkline glyph (semantic `var(--token)` colours). **3 route render tests.**
- **T-5.4** — full suite + ruff + schema + L2 + ASCII + trailer gates (below); §O close-out note; this report.

---

## §4 Test surface verification (READ actual counts — no false-green)

- **Branch-creation baseline (captured at `3986540`):** `6905 passed, 3 skipped` (183s).
- **Final on HEAD `c0201e8`:** `6933 passed, 3 skipped, 0 failed` (144s). Re-run on the final HEAD per `feedback_no_false_green_claim`.
- **Net delta: +28 tests.** Breakdown: `test_sparkline.py` 10 + `test_index_overview.py` 15 (3a+5b+5c+2d) + `test_metrics_index_overview.py` 3 = 28. Matches the delta exactly.
- **ruff:** `ruff check swing/` clean (0 E501).

**Flaky-test note (NOT SB5-caused):** the first post-implementation full run showed `tests/research/test_pattern_cohort_evaluator_reader.py::test_ohlcv_reader_re_export_identity` failing under xdist; it PASSES in isolation and did NOT recur on the final run. This is pre-existing xdist-ordering flakiness in the research OHLCV-reader re-export identity (gotcha #24/#26 archive-state family), unrelated to the metrics overview. Worth a banked follow-up.

---

## §5 Pre-locked decisions — verbatim verification

| LOCK | Disposition as shipped |
|------|------------------------|
| Q1 metrics LAST | SB5 is the FINAL sub-bundle (§O note) |
| Q2 SERIAL | single executing-plans bundle, T-5.1->T-5.4 serial |
| Q5 no-JS static | inline `<polyline>`, pure server-render, no JS |
| Q6 operator render gate | binding browser gate — orchestrator runs post-return (S3) |
| Q7 SINGLE Codex chain | ONE chain, converged R1/R2 |
| L1 P14.N5 only | no new metric/route; per-surface DATA logic untouched |
| L2 read-mostly | reuse `build_*_vm`/`compute_*`; ZERO write; ZERO new compute (see §8) |
| L3 no schema | `EXPECTED_SCHEMA_VERSION` stays 23; NO migration added |
| L4 honesty floor | sparklines on 3 surfaces ONLY; each its OWN threshold (5/10/line-band); honest suppressed captions; no fabricated line |
| L5 visual gate | rendered card binding; ASCII-only |
| L6 render-lock N/A | pure string build; no matplotlib, no `_RENDER_LOCK` |
| L7 leaf-VM | new fields on `MetricsIndexSurface`; `BaseLayoutVM` (shared.py) untouched |
| L8 HTMX | overview pure server-render; no HTMX added |
| L9 close-out | §O note drafted |
| OQ-1 inline-`<polyline>` | the only sparkline tech |
| OQ-2 3 trend surfaces | capital/funnel/process-grade only |
| OQ-3 enhance `/metrics` in place | no new `/metrics/overview` route |
| OQ-4 selectors | spec accessors re-grepped (§7); `DEVIATION_HEADLINE_COHORT`/`PATTERN_HEADLINE_CLASS` shipped at plan defaults (NOT re-pointed) |
| OQ-5 render-direct | no cache, no schema |
| OQ-6 eager | no HTMX lazy-load |
| OQ-7 single chain | converged |

---

## §6 Codex Major findings ACCEPTED with rationale

**NONE.** Zero criticals, zero majors across both rounds. The single MINOR (min_points guard) was FIXED, not accepted-as-rationale.

---

## §7 Production-code citations verified at task completion (#2 re-grep)

All re-grepped against the worktree at STEP 0 (production at `3986540`); all matched the plan:
- `build_metrics_index_vm(conn)` at `index.py:97` (now widened); route imports it at `metrics.py:30`, called at `:56`.
- `EXPECTED_SCHEMA_VERSION = 23` (`db.py:51`); highest migration `0023_*`.
- `capital.TREND_MIN_RUNS = 5` (`:61`); `funnel.TREND_MIN_RUNS = 10` (`:42`); `≥` glyph confirmed in `capital.py:640` + `funnel.py:288` (+ `honesty.py:42`).
- Builder signatures all `*, cfg, conn=None` (surfaces 1-7); `build_pattern_outcomes_vm(conn, *, session_date)` positional-conn (surface 9); `compute_process_grade_trend(conn, *, window_size=...)` (surface 8).
- `MetricCellB.value: BootstrapCI | SuppressedMetric` (`process.py:347`); `expectancy_R: MetricCellB` (`:421`).
- `APLUS_COHORT="A+ baseline"`; `TAXONOMY_COHORTS` (4 entries; `DEVIATION_HEADLINE_COHORT` = the 2nd); `CohortStatistics.expectancy`, `DeviationOutcomeRow.expectancy_relative_to_aplus_pct`/`row_suppressed`.
- `RollingMetricSeries.line_points`/`rendered_value`/`drawability_text`/`suppressed`; `RollingLinePoint.value: float | None`; metric key `process_grade_rolling_N`.
- 4 hypothesis cohorts seeded at schema creation (`0008` `INSERT OR IGNORE`) -> hypothesis headline `"4"`.

---

## §8 Schema impact verdict — NO migration (v23 held)

- `EXPECTED_SCHEMA_VERSION == 23` unchanged. `git diff 3986540..HEAD -- swing/data/migrations/` is EMPTY (no `0024`).
- **ZERO data-write:** the overview path issues only SELECTs (via the reused `build_*_vm`/`compute_*` + the existing discrepancy-count helpers). No INSERT/UPDATE/REPLACE, no `chart_renders` write.
- **ZERO new computation:** every headline + sparkline value is read from an EXISTING per-surface result/VM field; no cross-row aggregate is computed in `index.py`. The sparkline points string is built per-request from already-computed series and embedded in the HTML — nothing persists.

---

## §9 Central `_ascii()` + non-uniform-threshold + per-card-isolation verification

- **Central `_ascii()` chokepoint** in `_enrich_surface` coerces every reused text field (mapped substitutions then `encode("ascii","replace")`) AND label/description (defense-in-depth). Substitution map built from `chr(0xXXXX)` so `index.py` is pure ASCII. **Verified via a RENDERED test through the REAL builder** (`test_overview_real_builder_coerces_reused_suppression_text_to_ascii`): on an empty/low-sample DB, honesty.py's `≥` placeholder reaches the page as `>=` (overview-section `isascii()` True, contains `>=`, no `?`-masking). The unit test `test_ascii_sanitizer_coerces_geq_glyph_without_question_mark` covers `_ascii` directly.
- **Non-uniform thresholds:** capital imports `TREND_MIN_RUNS as _CAPITAL_TREND_MIN_RUNS` (=5), funnel imports `TREND_MIN_RUNS as _FUNNEL_TREND_MIN_RUNS` (=10); process-grade gates on `drawability_text`. The **7-run discriminator** (`test_capital_draws_on_same_7_run_db_funnel_suppresses` + `test_funnel_sparkline_threshold_is_10_not_5`) proves capital draws while funnel suppresses on the SAME DB — a single hardcoded `n<5` would fail it.
- **Per-card isolation:** `_enrich_surface` wraps each extractor in `try/except Exception  # noqa: BLE001` + `_LOG.warning(..., exc_info=True)` -> that card degrades to `"unavailable"`, the grid still renders 9. Verified by `test_one_surface_failure_degrades_only_that_card`.

---

## §10 L2 LOCK verification

`tests/integration/test_l2_lock_source_grep.py` — **2 passed.** No new Schwab API call-sites on this branch (the reused capital computation reads equity from existing DB snapshots; no `_call_endpoint`/schwabdev call added).

---

## §11 Operator-witnessed gate readiness (S1–S6)

| Step | Owner | Status |
|------|-------|--------|
| S1 suite + ruff | orchestrator | **READY** — 6933 passed / 0 failed on HEAD; ruff clean |
| S2 schema | orchestrator | **READY** — v23, no migration file added |
| S3 browser overview | **operator (BINDING)** | PENDING — orchestrator launches the BRANCH server (`python -m swing.cli web --port 8081` against the live v23 DB; read-mostly so safe) and the operator confirms: 9 cards in registry order; the 3 trend cards show inline sparkline when data sufficient else honest suppressed caption (never flat/fabricated); the 6 non-trend cards headline-only, no sparkline slot; every drill-down link resolves; headline figures match the drill-down; no mojibake / no `UnicodeEncodeError` in the console |
| S4 L2 grep | orchestrator | **READY** — L2 lock test passes |
| S5 ASCII | orchestrator | **READY** — authored files pure ASCII; rendered overview-section `isascii()` tests pass |
| S6 trailers | orchestrator | **READY** — `%(trailers)` `[]` on all 7 commits; no Co-Authored-By |

**Re-confirm the gate split** with the operator (`feedback_visual_gate_both_render_and_browser`). Teardown after S3 per `feedback_taskstop_does_not_kill_detached_server` (find PID via `Get-NetTCPConnection -LocalPort 8081`, `Stop-Process -Force`, verify port free).

---

## §12 NEW forward-binding lessons banked

1. **A shared base-layout glyph defeats a full-page `body.isascii()`** — `base.html.j2` carries a pre-existing U+2014 em-dash in its inline FOUC `<style>` comment. An overview ASCII assertion must scope to the rendered surface section, not the whole page. (Banked for any future "rendered body ASCII" gate.)
2. **Jinja autoescapes `>` to `&gt;`** — substring assertions for `>=`-bearing text must `html.unescape(body)` first. The plan's literal `assert "needs >=5 runs" in body` would fail against real autoescaped HTML.
3. **A `_ascii`-style substitution MAP must not itself live as literal glyphs** if a file-wide non-ASCII gate covers the file — build the map from `chr(0xXXXX)` so the source stays pure ASCII.
4. **Monkeypatched render tests cannot exercise a real-glyph coercion chokepoint** — a determinism monkeypatch (Codex R1 MAJOR #4 from writing-plans) injects a pre-built ASCII VM, bypassing `_enrich_surface`. A SEPARATE real-builder render test on a low-sample DB is needed to actually exercise `_ascii` on honesty.py text.
5. **`pytest.approx` is unhashable** — cannot appear inside a set literal; assert per-element instead.
6. **Theme A.3 no-raw-hex contract** — any NEW CSS rule outside `:root`/`body.dark` must use `var(--token)`, never raw hex, or `test_a3_no_raw_hex_outside_root_and_dark_blocks` fails (and the dark theme silently breaks for that selector).

---

## §13 ASCII discipline scope (gotcha #32)

- **NEW files (pure ASCII, verified):** `swing/web/view_models/metrics/sparkline.py`, `tests/web/view_models/metrics/test_sparkline.py`, `tests/web/view_models/metrics/test_index_overview.py`, `tests/web/test_routes/test_metrics_index_overview.py`. (Test files contain an intentional literal `≥` in the `_ascii` unit-test INPUT — outside the production-file ASCII grep scope.)
- **MODIFIED production files:** `index.py` (pure ASCII — substitution map via `chr()`, all `§` docstrings ASCII-ified); `index.html.j2` (pure ASCII — old `§4.1-§4.8` intro removed); `routes/metrics.py` (ASCII); `app.css` NEW block (ASCII; pre-existing comment em-dashes from prior phases are out of scope — served as static CSS, never through a cp1252 stdout path or the HTML body).

---

## §14 Cumulative gotcha application summary (per task)

- **#16/#32 ASCII** — T-5.2.a/d (central `_ascii` + chr()-map) + T-5.3 (rendered-body test).
- **base.html.j2 shared / L7** — verified `BaseLayoutVM` (shared.py) untouched; new fields on the leaf VM (no base-VM fan-out).
- **bad-exemplar isolation** (per-card try/except) — T-5.2.d.
- **`vm.result is None` + empty-collection guards** — every extractor (T-5.2.b/c).
- **shared connection** — all 9 builders run on the route's single `conn`.
- **TestClient lifespan** — `with TestClient(app) as client:` in all route tests.
- **synthetic-fixture-vs-emitter drift** — fixtures seed via the production INSERT shape (pipeline_runs / reviewed-trade seeder copied from existing tests).
- **trailer-parse hazard** — plain-prose final `-m` paragraph; `%(trailers)` `[]` per commit.
- **`feedback_regression_test_arithmetic`** — the 7-run discriminator computed under both thresholds.
- **`feedback_no_false_green_claim`** — re-ran the suite on the final HEAD and read the actual count.

---

## §15 Worktree teardown status

NOT torn down (branch pushed; orchestrator needs the worktree for the S3 branch-server render gate). `.tmp-codex-review/` (gitignored) holds the Codex prompts+responses+diff for QA. Teardown after the operator gate passes + merge.

---

## §16 ZERO Co-Authored-By footer drift

All 7 branch commits: `git log -1 --format='%(trailers)'` == `[]`; `git log 3986540..HEAD --format='%B' | grep -i co-authored` returns NOTHING. Streak preserved.

---

## §17 CLAUDE.md status-line refresh draft text

> **Sub-bundle 5 (metrics overview; P14.N5) EXECUTING-PLANS SHIPPED** at `<merge-sha>` (9-card `/metrics` overview: pure inline-`<polyline>` sparkline helper; `build_metrics_index_vm(cfg, conn)` widened atomic with the route + 3 call-sites; 9 read-only per-surface extractors — headline on all 9, sparklines on the 3 trend surfaces each gated by its OWN threshold 5/10/line-band; central `_ascii()` chokepoint for reused metric text; per-card try/except isolation; 7 commits incl. 1 gate-fix; genuine single WSL Codex chain CONVERGED R1/R2 [1 MINOR fixed, ZERO crit/major]; 6933 fast tests green on HEAD [+28]; NO schema change, v23 held; ZERO data-write + ZERO new computation; read-mostly). **ALL 5 Phase 14 sub-bundles MERGED** → Phase 14 close-out review (Sec 9.1 Q6).

---

## §18 §O Phase 14 close-out readiness note (L9)

SB5 is the **FINAL** Phase 14 sub-bundle. On SB5 merge, all 5 are shipped:
SB1 (data-wiring `e323339`) · SB2 (temporal log v22 `27f8007`) · SB3 (chart uniformity v23 `edd098d`) · SB4 (review+journal `31da4a5`) · SB5 (metrics overview, this branch).

**Close-out (Sec 9.1 Q6) — NOT in SB5 scope; sequenced after merge:**
1. Operator-witnessed **cross-sub-bundle integration review** — charts + review/journal + metrics overview rendering coherently together in one browser session.
2. Sequence the **banked Phase 14 follow-ups** (per `docs/phase3e-todo.md`): SB5.5 (Schwab A-3 daily-bar web wiring + P14.N7 checker-thread resilience); `market_weather` 200MA fetch-window (SB3 banked); vcp 5-contraction cosmetic crowding (SB3 banked); `_bulz_*`->general row-expand rename (SB4 banked); the close-out polish batch + B-7. **NEW banked item:** the `test_ohlcv_reader_re_export_identity` xdist-ordering flake (§4).
3. CLAUDE.md status-line refresh to "Phase 14 CLOSED" once the close-out review passes.

**Schema verdict for close-out:** Phase 14 lands at **v23** (SB5 adds no schema). L2 LOCK preserved.

---

*End of return report. SB5 ships the metrics overview read-mostly (no schema, no data-write, no new computation); ONE WSL Codex chain converged R1/R2; 6933 fast tests green on HEAD; the rendered overview in a real browser is the BINDING operator gate (S3) — orchestrator runs it post-return; NOT self-merged.*
