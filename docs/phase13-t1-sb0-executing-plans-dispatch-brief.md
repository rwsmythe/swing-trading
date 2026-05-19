# Phase 13 T1.SB0 — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 13 T1.SB0 executing-plans implementer. No prior conversation context.

**Mission:** Execute the 4-task T1.SB0 plan (OhlcvCache → `_step_charts` wiring; prerequisite Sub-bundle for the Phase 13 arc). Releases Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral. Substrate for Theme 2 detectors + T3.SB3 review auto-fill.

**Brief:** `docs/phase13-t1-sb0-executing-plans-dispatch-brief.md` (this file).

**Plan (PRIMARY):** `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.0 (lines 803-1043; 4 tasks T-T1.SB0.1..T-T1.SB0.4 with per-step instructions).

**Sequencing:** Phase 13 writing-plans SHIPPED 2026-05-18 PM at `08ce852`. T1.SB0 is the first executing-plans dispatch in the 11-sub-bundle loop per plan §H.1. After T1.SB0 merges to main, T2.SB1 ∥ T3.SB1 dispatch concurrent (T3.SB1 worktree branches off T2.SB1's first-commit SHA per OQ-12 Option E).

**Expected duration:** ~1-3 substantive Codex rounds (smallest sub-bundle in Phase 13 arc; 4 tasks; consumer-side over current v19 schema; expected convergent shape). Test delta projection per plan §K: **+20-40 fast tests + 0 slow**; LOC projection: **+50-100 prod / +200-350 test**. Schema delta: NONE (v19 unchanged; v20 lands at T2.SB1 task T-A.1.1).

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`** — PRIMARY SUBSTRATE. Read end-to-end at minimum: §0 top-matter + §A general architectural decisions + **§G.0 T1.SB0 (lines 803-1043; THE 4-TASK SPEC for this dispatch)** + §H.3 cross-bundle pin schedule + §K test/LOC projections + §L forward-binding lessons. §B-§F + §G.1-§G.10 + §I-§J optional context.

2. **`docs/phase13-t1-sb0-executing-plans-dispatch-brief.md`** (this file).

3. **`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`** — operator-confirmed brainstorm spec (1483 lines). Read §1 LOCKS L1-L11 + §4 Theme 1 (especially §4.1 T1.SB0 + §4.4 chart_renders cache architecture) + §11 forward-binding lessons inherited. T1.SB0 implements §4.1 + plan §G.0.

4. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" + "Maintenance: retention discipline" (especially §"Size-check trigger at housekeeping-commit time" subsection).

5. **`CLAUDE.md`** at repo root — project conventions + gotchas. **Especially**:
   - "OHLCV fetch scope = open-trade tickers ONLY" gotcha (existing discipline; T1.SB0 must preserve).
   - "Cache + executor race" gotcha (workers must not write to shared state on deadline miss; OhlcvCache already follows; T1.SB0 must preserve).
   - "yfinance `group_by='column'` MultiIndex regression" gotcha (existing discipline).
   - "yfinance `history(interval='1d')` includes in-progress bar during market hours" gotcha.
   - "`exchange_calendars.is_open_at_time` requires `pd.Timestamp`" gotcha.
   - HTMX gotcha trinity (preserved across any new route work — but T1.SB0 has ZERO route work; informational).
   - Matplotlib mathtext gotcha (informational; T1.SB0 doesn't ship new charts; just wires the OHLCV fetch path).
   - Windows cp1252 stdout gotcha (ASCII-only on any new CLI text — T1.SB0 doesn't ship new CLI, but the existing `python -m swing.cli pipeline run` operator-witnessed gate at S2 must still emit ASCII-only briefing.md).
   - Test fixture USERPROFILE+HOME monkeypatch (Phase 12 forward-binding lesson; T1.SB0 tests touching user-config.toml MUST monkeypatch BOTH env vars).

6. **Existing OhlcvCache surface** at `swing/web/ohlcv_cache.py` (T-T1.SB0.1 recon target; read end-to-end at recon time).

7. **Existing `_step_charts`** at `swing/pipeline/runner.py:1204` (T-T1.SB0.1 recon target; read lines 1204-1350 or until function end).

8. **Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral context** — this Sub-bundle CLOSES that deferral. Grep `swing/pipeline/runner.py:620-639` (legacy `fetcher.get(...)` path); the V1 deferral noted that OhlcvCache was constructed with Schwab ladder hooks but `_step_charts` still used the legacy path. T1.SB0 wires OhlcvCache into the chart-rendering daily-bar consumption path.

9. **Precedent executing-plans dispatch briefs** (format reference):
   - `docs/phase12-5-bundle-1-oqf-executing-plans-dispatch-brief.md` (Phase 12.5 #1 executing-plans; single-sub-bundle precedent).
   - `docs/phase12-5-bundle-2-web-tier2-executing-plans-dispatch-brief.md` (Phase 12.5 #2 executing-plans).
   - `docs/phase12-5-bundle-3-project-hygiene-executing-plans-dispatch-brief.md` (Phase 12.5 #3 executing-plans).

---

## §0.5 Skill posture

- Invoke **`copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- Plan §G.0 has per-task acceptance criteria + per-step instructions. Follow plan exactly; do NOT deviate.
- DO NOT invoke `superpowers:brainstorming` — brainstorm + writing-plans both complete.
- DO NOT invoke `superpowers:writing-plans` — plan is canonical at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.0.
- **TDD discipline**: each task has Step 1 (failing test) → Step 2 (verify fail) → Step 3 (minimal implementation) → Step 4 (verify pass) → commit. Plan §G.0 encodes this; follow verbatim.
- Use **`superpowers:test-driven-development`** for per-task work.

---

## §1 Strategic context

### §1.1 T1.SB0 scope (per plan §G.0)

- **Goal**: Close Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral by wiring OhlcvCache into `swing/pipeline/runner.py:_step_charts`. Substrate for Theme 2 detectors (T2.SB2 foundation primitives) + T3.SB3 review auto-fill (MFE/MAE candle-data source per OQ-8 BINDING).
- **Branch**: `phase13-t1-sb0-ohlcv-charts-wiring` (per plan §G.0 line 807). Worktree branches from main HEAD (`bf8d214` post-housekeeping at dispatch time; verify with `git log -1 --format=%H main`).
- **Files in scope** (per plan §G.0 line 809-814):
  - Modify: `swing/pipeline/runner.py` (`_step_charts` around line 1204).
  - Modify: `swing/web/ohlcv_cache.py` (add `get_or_fetch(ticker, window_days)` if not present; verify per-cache locking).
  - Modify: `swing/pipeline/ohlcv.py` (`fetch_daily_bars` shape reconciliation; deprecate legacy bare `fetcher.get(...)` path if applicable).
  - Create: `tests/pipeline/test_step_charts_ohlcv_cache_wiring.py`.
  - Create: `tests/pipeline/test_ohlcv_cache_shape_parity.py`.
  - Create: `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py` (T-T1.SB0.4).
  - Create: `tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py` (T-T1.SB0.4).
  - Create: `docs/phase13-t1-sb0-recon.md` (T-T1.SB0.1 recon doc).

### §1.2 Per-task structure (per plan §G.0)

- **T-T1.SB0.1** — Recon + OhlcvCache.get_or_fetch surface verification. Read-only inventory + recon doc.
- **T-T1.SB0.2** — Add `OhlcvCache.get_or_fetch` IF MISSING + shape-parity test plant (TDD).
- **T-T1.SB0.3** — Wire `_step_charts` through OhlcvCache + discriminating test (TDD).
- **T-T1.SB0.4** — Per-cache locking + concurrent-fetch discriminating test + chart-bytes parity test + ruff sweep (closer).

Each task has per-step instructions in plan §G.0 — follow them verbatim. Each task ends with a commit per the plan-provided commit message.

### §1.3 Inherited LOCKS + DROPS (per plan §A + spec §1.4)

- **L1**: No run-time AI inferencing. T1.SB0 ships ZERO AI dispatch code.
- **L5**: Drift detection logging side IN SCOPE at later sub-bundles. T1.SB0 ships NO drift-logging code (logging-side baseline lands at T2.SB3 detectors).
- **L6**: Schema v19 UNCHANGED for T1.SB0 (consumer-side wiring only). v20 lands at T2.SB1 task T-A.1.1 (migration-only commit).
- **Phase 12 C.C lessons inheritance** (forward-binding lessons #5, #6, #7 from plan §L): reject-caller-held-tx contract on new transactional services / sandbox short-circuit in inner / SELECT-first idempotency — T1.SB0 introduces NO new transactional services, so these lessons are informational only.
- **OHLCV fetch scope = open-trade tickers ONLY** (existing CLAUDE.md gotcha) — preserved.
- **Cache + executor race** (existing CLAUDE.md gotcha) — preserved.
- **yfinance regressions** (multiple CLAUDE.md gotchas) — preserved.

### §1.4 Cross-bundle pin (per plan §H.3)

T-T1.SB0.4 plants `test_ohlcv_cache_get_or_fetch_invariant` cross-bundle pin. Un-skips at T2.SB2 + T2.SB3 + T3.SB3 (consumers). Pin verifies `OhlcvCache.get_or_fetch` surface stable across consumers.

### §1.5 Forward-binding lessons inherited (per plan §L; most-load-bearing for T1.SB0)

1. **OhlcvCache cache+executor race discipline** (existing CLAUDE.md gotcha) — preserve.
2. **OhlcvCache sliding-window breaker + in-deadline futures only writes** (Phase 11 lesson) — preserve.
3. **yfinance API regression family** (CLAUDE.md gotchas: `threads=False` discipline; `group_by` MultiIndex; in-progress bar; `pd.Timestamp` argument) — preserve.
4. **`python -m swing.cli` at worktree-side gates** (NOT bare `swing` per memory entry `feedback_worktree_cli_invocation.md`).
5. **TDD discipline per task** (Phase 9/10/12 precedent; failing test → pass test → commit).
6. **Per-step commit discipline** — each task commits at its closing step; do NOT bundle tasks into a single commit (plan §G.0 explicit per-task commit messages).
7. **Implementer self-report accuracy gate** (Phase 12 C.C lesson #7) — cite file:line evidence in return report; do NOT paraphrase.

---

## §2 Executing-plans scope

Execute plan §G.0 verbatim. The plan provides:
- Per-task acceptance criteria.
- Per-step instructions with failing-test-first TDD pattern.
- Per-task commit messages.
- Operator-witnessed gate definitions (S1 inline pytest+ruff; S2 `python -m swing.cli pipeline run` operator-paired; S3 chart output PNG/SVG visual parity).

Plan §G.0 lines 803-1043 are authoritative. Implementer follows exactly. Any deviation requires escalation to orchestrator (do NOT silent-deviate).

---

## §3 OUT OF SCOPE

- **Schema changes** — v19 UNCHANGED in T1.SB0. v20 lands at T2.SB1 task T-A.1.1 (migration-only commit per OQ-12 Option E). If T-T1.SB0.* surfaces a need for schema work, STOP + escalate to orchestrator + amend plan §G.0 + spec §3 (per spec §B.6 escalation rule + dispatch brief §5 watch item 17 BINDING).
- **Theme 2 detector code** — T1.SB0 ships NO detector code. Foundation primitives at T2.SB2; detectors batch 1 at T2.SB3.
- **Chart rendering changes** — T1.SB0 wires the OHLCV fetch path; chart rendering shape is unchanged. The chart-bytes parity test at T-T1.SB0.4 ASSERTS chart bytes unchanged between cache-fetched DataFrame and legacy-fetched DataFrame.
- **Schwab integration code** — T1.SB0 doesn't touch Schwab paths. OhlcvCache already composes over Schwab ladder hooks via existing infrastructure (Phase 11 Sub-bundle C).
- **HTMX route work** — T1.SB0 ships NO new routes. HTMX gotcha trinity preserved by not-changing-routes.
- **CLI new commands** — T1.SB0 ships NO new CLI commands.
- **Re-litigating plan §G.0 per-task structure** — accepted as given. If a step doesn't work as written, escalate.
- **Phase 12.5 #1/#2/#3 issues** — separate dispatch arcs; T1.SB0 doesn't touch them.

---

## §4 Binding conventions

- **Branch**: `phase13-t1-sb0-ohlcv-charts-wiring` (per plan §G.0 line 807). Worktree at `.worktrees/phase13-t1-sb0-ohlcv-charts-wiring/`.
- **Commit messages**: per-task message provided in plan §G.0. Do NOT amend message text; do NOT bundle multiple tasks into one commit.
- **NO Claude co-author footer.** CLAUDE.md binding convention. Cumulative streak ~195+ commits ZERO drift across Phase 11/12/12.5/13 arcs. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message. C.B + C.C + C.D + post-Phase-12 + Phase 12.5 #1/#2/#3 + Phase 13 brainstorm + Phase 13 writing-plans chains' explicit citation produced ZERO footer drift across ~195+ commits. Pattern is DURABLE. This executing-plans MUST NOT regress.
- **`python -m swing.cli`** at worktree-side gates (NOT bare `swing` per memory entry `feedback_worktree_cli_invocation.md` BINDING).
- **ASCII-only on runtime CLI paths** (Windows cp1252 stdout gotcha).
- No `--no-verify`. No amending.
- **TDD discipline**: each task = failing test → verify fail → minimal implementation → verify pass → commit (per plan §G.0 per-step structure).
- **Pre-Codex orchestrator-side review** per C.C lesson #6 BINDING — before invoking `copowers:adversarial-critic` in final round, dispatch a focused reviewer subagent with §1 LOCKS + §2 scope + §5 watch items + plan §G.0 per-task acceptance criteria as anchors. Validated 10x cumulatively across Phase 12/12.5/13 brainstorms + writing-plans + this is the 1st executing-plans dispatch in Phase 13 (will be 11th cumulative validation).
- **Operator-witnessed gate per plan §G.0**: S1 inline pytest fast-tests + ruff; S2 `python -m swing.cli pipeline run` against operator's production produces complete briefing.md with `_step_charts` succeeding through OhlcvCache (cassette-mode acceptable for CI; live-mode under operator-paired session); S3 visual chart parity against pre-Phase-13 baseline.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Plan §G.0 per-task structure integrity.** Each of T-T1.SB0.1..T-T1.SB0.4 executed per the plan's per-step instructions verbatim. Tasks committed separately with the plan-provided commit messages. NO bundling.
2. **OhlcvCache.get_or_fetch surface stability.** The new method signature + return shape (DataFrame with capitalized columns Open/High/Low/Close/Volume + DatetimeIndex) is the surface T2.SB2 + T2.SB3 + T3.SB3 will consume per cross-bundle pin. Plant the pin test at T-T1.SB0.4 closer per plan §H.3.
3. **Shape parity with legacy `fetch_daily_bars` path.** T-T1.SB0.2 shape-parity test asserts DataFrames are identical (within float tolerance) between cache + legacy paths. This is the discriminating test that prevents silent shape drift.
4. **Chart bytes parity (T-T1.SB0.4 Step 3).** Chart bytes assertion verifies the WIRE didn't change chart output — only the data fetch path. Visual parity against pre-Phase-13 baseline PNG/SVG.
5. **Per-cache locking + concurrent-fetch race safety.** T-T1.SB0.4 concurrent-fetch test (5 threads × 5 tickers simultaneously) asserts no race / no data corruption. If RLock needs to be added to `OhlcvCache`, document at recon (T-T1.SB0.1) + apply at T-T1.SB0.4.
6. **Cache + executor race gotcha preservation** (CLAUDE.md gotcha). Workers must not write to shared `_store` from inside themselves; request thread writes only for futures that completed in-deadline. Preserve.
7. **Sliding-window breaker preservation** (Phase 11 Sub-bundle C discipline). The breaker bounds the rate of yfinance API calls; preserve.
8. **OHLCV fetch scope = open-trade tickers ONLY** (CLAUDE.md gotcha). Existing `_step_charts` consumes `ohlcv_tickers = sorted({t.ticker for t in open_trades})`. Preserve this scope; do NOT broaden to watchlist.
9. **yfinance API regression family preservation.** `threads=False` discipline on `yf.download()`; `group_by='column'` MultiIndex defensive squeeze; in-progress bar stripping; `pd.Timestamp` argument to `exchange_calendars.is_open_at_time`. All preserved.
10. **Sandbox short-circuit preservation under sandbox environment.** OhlcvCache existing pattern (Phase 11) falls through directly to yfinance under sandbox; preserve.
11. **Phase 12 forward-binding lesson family inheritance.** Reject-caller-held-tx + sandbox-short-circuit-in-inner + SELECT-first idempotency — these are INFORMATIONAL for T1.SB0 (no new transactional services); preserve discipline awareness for downstream sub-bundles.
12. **Test fixture USERPROFILE+HOME monkeypatch discipline.** If any T1.SB0 test touches user-config.toml write paths (likely none, but verify), monkeypatch BOTH `USERPROFILE` AND `HOME` env vars before invoking (per Phase 9 Sub-bundle A pattern).
13. **`python -m swing.cli` worktree-side discipline** (memory entry BINDING). Per-task acceptance criteria's `python -m pytest tests/pipeline/...` invocations are correct; the operator-witnessed S2 gate uses `python -m swing.cli pipeline run`.
14. **Per-task commit message consistency.** Each task's commit message follows plan §G.0 exactly. Implementer should NOT amend wording or compose new messages.
15. **Cross-bundle pin discipline** (Phase 10 + Phase 12 + Phase 12.5 #2 precedent). The `test_ohlcv_cache_get_or_fetch_invariant` pin planted at T-T1.SB0.4 is un-skipped at T2.SB2 + T2.SB3 + T3.SB3.
16. **Implementer self-report accuracy gate** (Phase 12 C.C lesson #7) — return report cites file:line evidence + chain test counts pre/post + commit SHAs verbatim.

---

## §6 Done criteria

1. Branch `phase13-t1-sb0-ohlcv-charts-wiring` at `.worktrees/phase13-t1-sb0-ohlcv-charts-wiring/`; 4 task-commits + optional Codex-fix commits + 1 return report commit.
2. 4 tasks T-T1.SB0.1..T-T1.SB0.4 executed per plan §G.0 per-step instructions verbatim.
3. ≥1 Codex round reaching NO_NEW_CRITICAL_MAJOR (smallest sub-bundle; 1-3 rounds expected).
4. Recon doc at `docs/phase13-t1-sb0-recon.md` (T-T1.SB0.1).
5. `OhlcvCache.get_or_fetch` method exists with documented signature (T-T1.SB0.2).
6. Shape-parity test passes (T-T1.SB0.2): DataFrames identical between cache + legacy paths.
7. `_step_charts` no longer invokes `fetch_daily_bars` directly (T-T1.SB0.3).
8. All existing pipeline tests continue to pass (T-T1.SB0.3 Step 5).
9. Concurrent multi-ticker fetch produces no race / no data corruption (T-T1.SB0.4).
10. Chart bytes parity assertion passes between OhlcvCache + legacy paths (T-T1.SB0.4).
11. Ruff baseline 0 E501 maintained (T-T1.SB0.4 Step 5).
12. Cross-bundle pin `test_ohlcv_cache_get_or_fetch_invariant` planted at T-T1.SB0.4 + skip-marker for un-skip at consumers (T2.SB2 + T2.SB3 + T3.SB3).
13. Operator-witnessed gate per plan §G.0: S1 (inline pytest+ruff) PASS; S2 (`python -m swing.cli pipeline run` operator-paired against production) PASS; S3 (chart output visual parity) PASS.
14. Return report at `docs/phase13-t1-sb0-return-report.md` per §7.
15. ZERO Co-Authored-By footer trailer drift across all commits (verified via `git log --pretty=format:"%(trailers:key=Co-Authored-By)"` returning empty).

---

## §7 Return report format

```
## Return report — Phase 13 T1.SB0

### Sub-bundle location
Worktree branch: `phase13-t1-sb0-ohlcv-charts-wiring` at `.worktrees/phase13-t1-sb0-ohlcv-charts-wiring/`
Commits on branch:
- {sha} `docs(phase13): T1.SB0 recon — OhlcvCache → _step_charts wiring inventory (T-T1.SB0.1)`
- {sha} `feat(phase13): OhlcvCache.get_or_fetch + shape-parity test (T-T1.SB0.2)`
- {sha} `feat(phase13): wire _step_charts through OhlcvCache.get_or_fetch (T-T1.SB0.3)`
- {sha} `feat(phase13): T1.SB0 closer — per-cache locking + chart-bytes parity + ruff (T-T1.SB0.4)`
- (optional) {sha} `fix(phase13): T1.SB0 Codex R<N> fixes`
- {sha} `docs(phase13): T1.SB0 return report`

### Codex review history
- Pre-Codex (orchestrator-side review per C.C lesson #6 BINDING): {N findings absorbed; 11th cumulative validation}
- R1: {C/M/m findings; FIXED/ACCEPTED counts; verdict}
- ... (1-3 rounds expected)
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Test count pre/post
- Pre-baseline: {fast count from main HEAD bf8d214}
- Post-T1.SB0: {fast count} (delta: +{N}; within +20-40 projection)

### Operator-witnessed gate results
- S1 (inline pytest+ruff): {PASS/FAIL with evidence}
- S2 (python -m swing.cli pipeline run live OR cassette-mode): {PASS/FAIL with evidence}
- S3 (chart output visual parity): {PASS/FAIL with evidence}

### Cross-bundle pin planted
- `test_ohlcv_cache_get_or_fetch_invariant` at {file:line}; skip-marker `@pytest.mark.skip(reason="un-skips at T2.SB2 + T2.SB3 + T3.SB3 per plan §H.3")`.

### V2.1 §VII.F amendment candidates banked (if any)
- ...

### Forward-binding lessons for downstream sub-bundles
- ...

### Capture-needs for next sub-bundle dispatch (T2.SB1 + T3.SB1 concurrent)
- T2.SB1's first-commit SHA will need recording for T3.SB1 worktree branch-base coordination.
- ...

### Outstanding capture-needs that DEFER
- ...
```

---

## §8 If you get stuck

- If plan §G.0 per-step instructions conflict with reality (e.g., a file path different from plan), STOP + escalate to orchestrator + amend plan via separate commit.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly + return report.
- If you find yourself proposing schema work, STOP — v19 UNCHANGED for T1.SB0 (per §3 OUT OF SCOPE).
- If you find yourself proposing route/Jinja/CLI changes, STOP — T1.SB0 is OHLCV cache wiring only.
- If you find yourself encountering a Phase 12 C.C lesson family that conflicts with T1.SB0 implementation, the lesson wins — surface as design constraint.
- If you find yourself proposing run-time AI inferencing, STOP — L1 LOCK violated.
- If concurrent-fetch test (T-T1.SB0.4) requires significant locking changes to OhlcvCache, document in recon (T-T1.SB0.1) + apply in T-T1.SB0.4 + cite Phase 11 forward-binding lesson family.
- If chart-bytes parity test (T-T1.SB0.4) fails (chart output differs between cache + legacy paths), STOP + escalate — the WIRE should not change chart output.
- If you find shape drift between OhlcvCache.get_or_fetch and legacy `fetch_daily_bars`, document at recon (T-T1.SB0.1) + add shape-reconciliation logic at T-T1.SB0.2 + ensure shape-parity test passes.

---

*End of brief. Phase 13 T1.SB0 executing-plans dispatch — 4 tasks per plan §G.0; closes Phase 11 Sub-bundle C R1 M#5 V1 deferral; substrate for Theme 2 + T3.SB3. Worktree branch `phase13-t1-sb0-ohlcv-charts-wiring`. Expected 1-3 Codex rounds + convergent shape. ZERO ACCEPT-WITH-RATIONALE preferred. Pre-Codex orchestrator-side review BINDING per C.C lesson #6 (will be 11th cumulative validation). After T1.SB0 merges, T2.SB1 ∥ T3.SB1 concurrent dispatch per OQ-12 Option E (T3.SB1 branches off T2.SB1's first-commit SHA).*
