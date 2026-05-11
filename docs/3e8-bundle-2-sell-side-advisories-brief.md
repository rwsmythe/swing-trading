# 3e.8 Bundle 2 — Sell-side advisories (§4.B + §4.K + §4.D) dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Add THREE new sell-side advisory rules to `swing/trades/advisory.py` and wire each into all FIVE existing advisory-composition surfaces (dashboard list view, open-positions row, open-positions expanded HTMX partial, trade-detail page, pipeline briefing):

1. **§4.B** — `suggest_trim_into_strength` — emit a trim hint at +1R first-time when trade has not yet been trimmed.
2. **§4.K** — `suggest_planned_target_r_hit` — emit a target-hit hint when `r_so_far` ≥ `trades.planned_target_R`.
3. **§4.D** — `suggest_parabolic_trim` — emit a parabolic-extension hint when price is ≥ 7× ADR% above the 50SMA (DST D.7 / Realsimpleariel doctrine anchor).

All three are **advisory-message-only**. No schema changes. No V2.1 §VII.F routing. NEW cfg keys on `StopAdvisoryConfig`. NEW `adr_pct` field on `AdvisoryContext` (cheap; reuse existing `swing/evaluation/criteria/_base.py:102 adr_pct()` helper).

**Expected duration:** ~8-10 hr implementation + ~30-45 min dispatch overhead. Total ~9-11 hr.

**Skill posture:**
- Invoke `superpowers:subagent-driven-development` directly (NOT via `copowers:executing-plans` wrapper).
- DO NOT invoke `superpowers:writing-plans` or `copowers:brainstorming` — design is locked in §0.3 below by orchestrator + operator (2026-05-11 in-session lock for §4.B trigger + §4.D thresholds; investigation + phase3e-todo for the rest).
- Adversarial review via `copowers:adversarial-critic` after all task families land. Iterate to NO_NEW_CRITICAL_MAJOR. Expected 2-4 Codex rounds (new rule logic + 5-site composition mirroring + new cfg keys + ADR plumbing — moderate surface).

---

## §0 Read first

### §0.1 Backlog entries
- `docs/phase3e-todo.md` 2026-05-10 §3e.8 disposition section "Bundle 2 — Sell-side advisories (§4.B + §4.K + §4.D)" (line ~1108).
- `docs/3e8-sell-side-advisories-investigation.md`:
  - §4.B Recommendation B (line 338-365)
  - §4.D Recommendation D (line 395-425)
  - §4.K Recommendation K (line 539-562)
  - §5.1 per-stage advisory matrix (line 572-588)
- `reference/methodology/dst-take-profit-and-trail.md`:
  - D.2 (50% Day 3-5 calendar trigger — NOT chosen for §4.B; operator-policy hybrid +1R/25% locked instead)
  - D.7 (>7x ADR above 50SMA — chosen for §4.D doctrine anchor)
- `reference/methodology/minervini-sell-side-rules.md`:
  - M.2 (R-multiple sell-into-strength — adjacent to §4.B; informs §4.K Bundle 3 framing)

### §0.2 Code surface

**For all three rules (advisory.py):**
- `swing/trades/advisory.py:18-26` — current `AdvisoryContext` dataclass. Add `adr_pct: float | None` field for §4.D. Add helper to construct it from OHLCV in the existing composer callers.
- `swing/trades/advisory.py:35-43` — current `suggest_breakeven` shape. Mirror pattern for the three new rules.
- `swing/config.py:91-96` — current `StopAdvisoryConfig`. Add:
  - `trim_first_r_trigger: float = 1.0` (NEW; §4.B trigger)
  - `trim_first_pct_default: float = 0.25` (NEW; §4.B trim percentage in message)
  - `parabolic_adr_multiple: float = 7.0` (NEW; §4.D doctrine multiplier per D.7)

**For §4.B trim-detection ("no prior trim" check):**
- `swing/trades/state.py` (and the derived-metrics surface around `swing/trades/derived_metrics.py`) — Phase 7 introduced state-machine + Fills first-class with `initial_shares` + computed `remaining_shares`. **Verify which exact field/predicate gives the "trade has had no prior trim" answer.** Candidates: `trade.remaining_shares == trade.initial_shares`, OR a derived `has_been_trimmed: bool`, OR a fills-count check. Implementer's recon: read `swing/trades/derived_metrics.py` + `swing/data/repos/fills.py` to pick the canonical predicate. The Trade dataclass at `swing/trades/state.py:27` already lists `initial_shares` in its construction tuple.

**For §4.K planned_target_R:**
- `trades.planned_target_R` column added in Phase 8 (per CLAUDE.md; schema_version 16). Nullable. Read via existing Trade row dataclass; check the field name via `grep planned_target_R swing/data/models.py`.
- `swing/data/repos/trades.py` — verify the Trade row dataclass surface to confirm the attribute name (`planned_target_R` vs `planned_target_r` casing).

**For §4.D parabolic-extension detector:**
- `swing/evaluation/criteria/_base.py:102` — `adr_pct(df: pd.DataFrame, lookback: int = 20) -> float`. Reusable directly. Returns ADR as a percent of price (mean of `(High - Low) / Close * 100`).
- OHLCV data already loaded in advisory paths: dashboard side via `OhlcvCache`; pipeline-briefing side via the cached fetcher in `swing/pipeline/runner.py` (per Bundle 1's `_CachingFetcherWrapper`).

**For the 5-site composition mirroring (one site per advisory caller):**

Per the Bundle 1 V2 watch-item: advisory composition is hand-duplicated across 5 paths post-Bundle-1 ship. Bundle 2's three new rules MUST be added to each:

1. `swing/web/view_models/dashboard.py:build_dashboard` — composes per-row advisories for the dashboard list view.
2. `swing/web/view_models/open_positions_row.py` — (verify exact path; may be `dashboard.py:build_open_positions_row`) per-row composer.
3. `swing/web/view_models/dashboard.py:build_open_positions_expanded` — HTMX-expanded row composer.
4. `swing/web/view_models/trades.py:build_trade_detail_vm` — `/trades/{id}` page composer.
5. `swing/pipeline/runner.py:882 compose_open_trade_advisories_for_briefing` — pipeline briefing composer (introduced Bundle 1).

ALL FIVE need the three new rules added in the SAME ORDER and with consistent `AdvisoryContext` construction. Where the §4.D rule requires `adr_pct`, the caller must pass it through (None when OHLCV is unavailable; rule no-ops on None).

**For test surface:**
- `tests/trades/test_advisory.py` (or equivalent) — unit tests for individual rule functions.
- `tests/web/` — integration tests for VM composers (mirror Bundle 1's added tests).
- `tests/pipeline/` — pipeline-side composer + briefing snapshot tests.

### §0.3 LOCKED DESIGN DECISIONS (DO NOT re-litigate)

Locked by orchestrator + operator in-thread design lock 2026-05-11:

1. **§4.B trigger: R-multiple, NOT calendar.** Operator selected (a) R-multiple over (b) DST D.2 calendar (Day 3-5 / 50%) over (c) both / (d) hybrid. Rationale: lowest-friction, aligns with framework's existing R-multiple plumbing; D.2-faithful Day-3-5 calendar trigger banked for V2 if evidence accrues that the R-multiple version mis-times the trim window.

   - Default `trim_first_r_trigger = 1.0` (R-multiple).
   - Default `trim_first_pct_default = 0.25` (advisory text reads "trim 25%"; operator-tunable).
   - Predicate: fires when `r_so_far(trade, ctx.current_price) >= cfg.trim_first_r_trigger` AND `trade has had no prior trim`. Implementer determines the canonical "no prior trim" predicate during recon (see §0.2 above).
   - Message: `f"Consider trimming {trim_first_pct_default*100:.0f}% of position — up +{r_so_far:.2f}R; sell-into-strength discipline"`.
   - Continues to fire across maturity stages until trim is registered (per §5.1 matrix).

2. **§4.D thresholds: DST D.7 doctrine-anchored (>7× ADR above 50SMA), NOT 3e.8 arbitrary defaults.** Operator selected (b) DST D.7 over (a) 3e.8 originals (25%/5d/15%) over (c) both. Rationale: doctrine-clean; ADR helper already exists; 3e.8 originals were explicitly flagged "arbitrary" in the investigation.

   - Default `parabolic_adr_multiple = 7.0` (Realsimpleariel-anchored per DST D.7).
   - MA reference: SMA50 (already on `AdvisoryContext.sma50`).
   - Predicate: fires when `ctx.adr_pct IS NOT NULL AND ctx.sma50 IS NOT NULL AND ctx.current_price > ctx.sma50 AND (ctx.current_price - ctx.sma50) / ctx.sma50 * 100 >= cfg.parabolic_adr_multiple * ctx.adr_pct`.
   - Message: `f"Parabolic extension — price ${ctx.current_price:.2f} is ≥{cfg.parabolic_adr_multiple:.1f}× ADR above 50SMA (ADR={ctx.adr_pct:.2f}%); consider aggressive trim per DST D.7 / Realsimpleariel"`.
   - Fires regardless of maturity stage (per §5.1).
   - **Banked V2 watch item:** D.6 (intraday-EMA reference for parabolic moves) — V1 stays on daily-bar 50SMA per ADR formulation; intraday MA upgrade is V2.

3. **§4.K planned_target_R hit advisory: straightforward.** No design lock needed.
   - No new cfg keys.
   - Predicate: fires when `trade.planned_target_R IS NOT NULL AND r_so_far(trade, ctx.current_price) >= trade.planned_target_R`.
   - Message: `f"Reached planned target +{trade.planned_target_R:.1f}R — consider trim per sell-into-strength discipline"`.
   - Fires regardless of maturity stage; once-condition-met fires every render until trade closes or target updated.

4. **Hand-duplicate the 5-site composition mirror; do NOT extract a shared composer.** Bundle 1 V2 watch item #1 banked the shared-composer extract as a separate dispatch. Bundle 2 ACCEPTS the drift risk consciously and mirrors the existing pattern across all 5 sites — same accept-with-rationale Bundle 1 took on R1 Minor #1. **If, during implementation, the implementer surfaces a clear case that 5-site mirroring is structurally impossible** (e.g., context types diverged in a way that prevents uniform rule addition), pause + surface to orchestrator before extracting a composer.

5. **AdvisoryContext `adr_pct` plumbing:**
   - Add `adr_pct: float | None` field to `AdvisoryContext` (default `None` via field-init or constructor default).
   - For web-side callers (dashboard / open-positions-row / open-positions-expanded / trade-detail): compute `adr_pct` from the same OHLCV bundle already loaded for the SMA computations. Falls back to `None` when OHLCV is unavailable / sliding-window breaker tripped.
   - For pipeline-briefing-side caller (`compose_open_trade_advisories_for_briefing`): compute `adr_pct` from the same cached fetcher Bundle 1 introduced. Document any divergence in inline comment (per Bundle 1 §0.3 #2 pattern).
   - §4.D rule no-ops (returns None) when `ctx.adr_pct is None OR ctx.sma50 is None OR ctx.current_price <= ctx.sma50`.

6. **No new schema; no V2.1 §VII.F routing.** Pure advisory-rule additions + cfg keys + composer-mirroring + ADR field plumb.

7. **No emission-format changes to existing rules.** §4.B + §4.K + §4.D messages are new strings; existing `breakeven` / `trail_10MA` / `trail_20MA` / `exit_below_*MA` / `weather` / `time_stop` messages are unchanged.

8. **HTMX safety:** the only HTMX surface affected is the open-positions expanded row (Bundle 1 already wired advisory rendering there). Bundle 2 adds new rules INSIDE the existing advisory list rendering — no template structure changes. Per CLAUDE.md gotcha "HTMX response leading with `<tr>` triggers `makeFragment`", verify the expanded-row response shape is unchanged after Bundle 2 adds the new rules to the per-row advisory tuple.

9. **DHC operational reality check (informs operator-witnessed gate):**
   - Per snapshot 2026-05-08T11:24:23: open_R=0.85, MFE=0.88R, maturity_stage=pre_+1.5R.
   - §4.B trim-into-strength: WILL fire once DHC crosses +1R (current 0.85R; trigger 1.0R).
   - §4.K target-hit: depends on `planned_target_R` value for DHC; verify operator entered one at Phase 8 entry-form time.
   - §4.D parabolic: depends on current_price vs sma50 × ADR; unlikely to fire at +0.85R but verify empirically.
   - Operator-gate Surface 1 below references DHC explicitly.

---

## §1 Strategic context

This is the post-3e.8-investigation Bundle 2 commission. Three new sell-side advisory rules close the §4.B/§4.K/§4.D items from the investigation's §6 operator-decision matrix. All advisory-message-only; no doctrine claims encoded in code beyond the message strings.

**Schema state (binding):** Production DB at schema_version 16 post-Phase 8 ship. No schema work in scope.

**What's NOT in scope:**
- Maturity-stage gating for trim/target-hit/parabolic (Bundle 3 work; §4.A.bis + new M.2 R-multiple stop-tighten)
- Shared composer extract (Bundle 1 V2 watch item; deferred)
- §4.B Day-3-5 calendar trigger (V2 watch item; doctrine-faithful alternative banked)
- §4.D D.6 intraday-EMA upgrade (V2 watch item; daily-bar 50SMA in V1)
- §4.C / §4.C.bis time-stop changes (banked-without-gate per phase3e-todo)
- §4.H / §4.I / §4.J (deferred-with-second-source-gate)
- §4.A full classification-altering trail-MA gating (banked-without-gate)

---

## §2 Worktree + binding conventions

### §2.1 Worktree
- **Branch:** `3e8-bundle-2-sell-side-advisories`
- **Worktree directory:** `.worktrees/3e8-bundle-2-sell-side-advisories/` at repo root.
- **BASELINE_SHA:** `<bundle-2-brief-commit-SHA>` (resolved post-commit; orchestrator fills in after committing this brief).

### §2.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task families land + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §2.3 Commits
- Conventional prefix:
  - `feat(advisory): Task A.X — <description>` for rule additions in `swing/trades/advisory.py`
  - `feat(config): Task A.X — <description>` for `StopAdvisoryConfig` extensions
  - `feat(web): Task A.X — <description>` for VM composer changes
  - `feat(pipeline): Task A.X — <description>` for `compose_open_trade_advisories_for_briefing` changes
  - `test(...)` for test-only commits
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change OR cluster cycles when tests are essentially discriminators of one feature.

### §2.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§5).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping.

### §2.5 Verify command
PowerShell from inside worktree:
```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```

---

## §3 Per-task implementation breakdown

### §3.1 Task family A — `AdvisoryContext` extension + cfg keys

**Acceptance criteria:**

- (A.AC.1) `swing/trades/advisory.py` `AdvisoryContext` dataclass gains `adr_pct: float | None` field with safe default (`None` via dataclass-default).
- (A.AC.2) `swing/config.py` `StopAdvisoryConfig` gains three new fields with defaults:
  - `trim_first_r_trigger: float = 1.0`
  - `trim_first_pct_default: float = 0.25`
  - `parabolic_adr_multiple: float = 7.0`
- (A.AC.3) Defaults match §0.3 spec; no other StopAdvisoryConfig fields modified.
- (A.AC.4) Existing tests that instantiate `AdvisoryContext` and `StopAdvisoryConfig` (without the new fields) continue to pass (defaults make this safe).

**Suggested test names:**

- `test_advisory_context_accepts_adr_pct_field`
- `test_stop_advisory_config_has_trim_first_r_trigger_default`
- `test_stop_advisory_config_has_trim_first_pct_default`
- `test_stop_advisory_config_has_parabolic_adr_multiple_default`

**Suggested commit shape:**
- A.1: `feat(advisory): Task A.1 — add adr_pct field to AdvisoryContext` (single commit; trivial change with RED+GREEN test)
- A.2: `feat(config): Task A.2 — add trim/parabolic cfg keys to StopAdvisoryConfig` (single commit; trivial change with RED+GREEN tests)

**Watch items:**
- Default-mutability: ensure `adr_pct` default is `None` (immutable), not a mutable default that would trip dataclass.
- Existing `AdvisoryContext` callers that construct via positional args may break if the new field is positional — add as keyword-only OR at end of field list to preserve ordering (verify by running existing test suite after change).
- Per CLAUDE.md gotcha "`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM": NOT applicable here — `AdvisoryContext` is a service-layer dataclass, not a page VM. `StopAdvisoryConfig` lives in `cfg.stop_advisory`; not a page VM. Verify by grepping `base.html.j2` for any `vm.adr_pct` reference (expect zero).

### §3.2 Task family B — Rule implementations (three new advisory functions)

**Acceptance criteria:**

- (B.AC.1) `swing/trades/advisory.py` gains `suggest_trim_into_strength(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None`:
  - Returns `None` when `r_so_far(trade, ctx.current_price) < ctx.config.trim_first_r_trigger`
  - Returns `None` when trade has been trimmed already (implementer determines canonical predicate during recon; see §0.2)
  - Returns `AdvisorySuggestion(rule="trim_into_strength", message="...")` per §0.3 #1 message template otherwise.
- (B.AC.2) `swing/trades/advisory.py` gains `suggest_planned_target_r_hit(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None`:
  - Returns `None` when `trade.planned_target_R is None`
  - Returns `None` when `r_so_far(trade, ctx.current_price) < trade.planned_target_R`
  - Returns `AdvisorySuggestion(rule="planned_target_r_hit", message="...")` per §0.3 #3 message template otherwise.
- (B.AC.3) `swing/trades/advisory.py` gains `suggest_parabolic_trim(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None`:
  - Returns `None` when `ctx.adr_pct is None OR ctx.sma50 is None OR ctx.current_price <= ctx.sma50`
  - Returns `None` when `(ctx.current_price - ctx.sma50) / ctx.sma50 * 100 < ctx.config.parabolic_adr_multiple * ctx.adr_pct`
  - Returns `AdvisorySuggestion(rule="parabolic_trim", message="...")` per §0.3 #2 message template otherwise.
- (B.AC.4) Each rule's `AdvisorySuggestion.rule` field is a unique string (`"trim_into_strength"`, `"planned_target_r_hit"`, `"parabolic_trim"`) that does NOT collide with any existing rule string.
- (B.AC.5) Each rule's message respects the f-string template in §0.3 (operator will visually verify wording in §5 surfaces).

**Suggested test names:**

- `test_suggest_trim_into_strength_returns_none_below_trigger_r`
- `test_suggest_trim_into_strength_returns_none_when_already_trimmed`
- `test_suggest_trim_into_strength_fires_at_trigger_r_no_prior_trim`
- `test_suggest_trim_into_strength_message_format`
- `test_suggest_planned_target_r_hit_returns_none_when_target_is_null`
- `test_suggest_planned_target_r_hit_returns_none_below_target`
- `test_suggest_planned_target_r_hit_fires_at_target_r`
- `test_suggest_planned_target_r_hit_message_format`
- `test_suggest_parabolic_trim_returns_none_when_adr_pct_none`
- `test_suggest_parabolic_trim_returns_none_when_sma50_none`
- `test_suggest_parabolic_trim_returns_none_when_price_below_sma50`
- `test_suggest_parabolic_trim_returns_none_when_extension_below_multiple`
- `test_suggest_parabolic_trim_fires_at_7x_adr_above_50sma`
- `test_suggest_parabolic_trim_message_format`

**Suggested commit shape:**
- B.1: `feat(advisory): Task B.1 — suggest_trim_into_strength rule + tests` (RED+GREEN cycle)
- B.2: `feat(advisory): Task B.2 — suggest_planned_target_r_hit rule + tests` (RED+GREEN cycle)
- B.3: `feat(advisory): Task B.3 — suggest_parabolic_trim rule + tests` (RED+GREEN cycle)

**Watch items:**
- Per CLAUDE.md gotcha "Python `... or ""` idiom collides with SQL CHECK-constraint nullability": NOT applicable here — no new schema. But for §4.K: `trade.planned_target_R` is nullable per Phase 8 — must guard against `None` BEFORE the comparison (Python `None >= 1.0` raises `TypeError`).
- For §4.B trim-detection: the canonical "no prior trim" predicate may interact with Phase 7 state-machine + Fills semantics. **Implementer must verify** via test fixture: a trade with one partial sell-side fill recorded should NOT fire this advisory; a trade with zero sell-side fills SHOULD fire (subject to R trigger).
- For §4.D ADR computation: `adr_pct` may be `nan` for trades with insufficient OHLCV bars (`< lookback`). Guard against `math.isnan(ctx.adr_pct)` if needed (or filter at construction time — pick one consistent strategy).
- **Pre-empt regression-test arithmetic** per operator-memory feedback `feedback_regression_test_arithmetic.md`: for each new rule, compute the expected outcome under BOTH the pre-fix path (rule absent / wrong threshold) and the post-fix path. Confirm the test distinguishes. Specifically for §4.D: a 6.9× ADR fixture should NOT fire; a 7.1× ADR fixture SHOULD fire.

### §3.3 Task family C — 5-site composition mirroring + ADR plumbing

**Acceptance criteria:**

- (C.AC.1) All FIVE advisory-composition sites (per §0.2) add the three new rules to their per-trade advisory tuple in a consistent order.
- (C.AC.2) Each composition site constructs `AdvisoryContext` with the new `adr_pct` field populated from the same OHLCV bundle already loaded for SMA computations. When OHLCV is unavailable, `adr_pct = None` (rule no-ops correctly per B.AC.3).
- (C.AC.3) Dashboard list-view row rendering shows the three new rules when triggers met (operator verifies via §5 Surface 1).
- (C.AC.4) Open-positions expanded HTMX row rendering shows the three new rules (operator verifies via §5 Surface 2).
- (C.AC.5) Trade-detail page rendering shows the three new rules (operator verifies via §5 Surface 3).
- (C.AC.6) Pipeline-emitted briefing rendering shows the three new rules (operator verifies via §5 Surface 4).
- (C.AC.7) Snapshot/golden tests cover the new rules' presence in pipeline briefing (mirror Bundle 1 pattern).
- (C.AC.8) NO new yfinance / OHLCV fetches introduced (ADR reuses existing OHLCV bundle — verify via mock-fetcher call-count instrumentation, mirroring Bundle 1 A.AC.5 pattern).

**Suggested test names:**

- `test_dashboard_open_positions_row_includes_new_advisories`
- `test_dashboard_open_positions_row_passes_adr_pct_to_context`
- `test_open_positions_expanded_includes_new_advisories`
- `test_trade_detail_vm_includes_new_advisories`
- `test_compose_open_trade_advisories_for_briefing_includes_new_advisories`
- `test_compose_open_trade_advisories_for_briefing_no_extra_yfinance_calls`
- `test_briefing_md_renders_trim_into_strength_when_triggered` (snapshot/golden test)
- `test_briefing_md_renders_planned_target_r_hit_when_triggered`
- `test_briefing_md_renders_parabolic_trim_when_triggered`

**Suggested commit shape:**
- C.1: `feat(web): Task C.1 — thread adr_pct into AdvisoryContext on 4 web composition sites` (single commit; ADR computation factored out + threaded through)
- C.2: `feat(pipeline): Task C.2 — thread adr_pct into AdvisoryContext on briefing composer` (single commit)
- C.3: `feat(web): Task C.3 — add 3 new rules to 4 web composition sites` (single commit)
- C.4: `feat(pipeline): Task C.4 — add 3 new rules to briefing composer` (single commit)
- C.5: `test(pipeline): Task C.5 — briefing snapshot tests for 3 new rules` (single commit)

**Watch items:**
- Per Bundle 1 V2 watch item #1: 5-site hand-duplication is accepted-with-rationale. Maintain rule-ordering consistency: implementer picks one canonical order (suggested: append the three new rules after existing rules in declaration order — `breakeven, trail_10MA, trail_20MA, exit_below_10MA, exit_below_20MA, exit_below_50MA, weather, time_stop, trim_into_strength, planned_target_r_hit, parabolic_trim`).
- Per CLAUDE.md gotcha "OHLCV fetch scope = open-trade tickers ONLY": ADR computation uses the SAME OHLCV bundle as SMA computations; no new tickers added; no scope change.
- Per CLAUDE.md gotcha "External-API empty-result must be treated as transient when write-through-caching": `adr_pct = None` on empty/insufficient OHLCV is acceptable (rule no-ops); do NOT write `adr_pct = 0.0` as a fallback.
- Per CLAUDE.md gotcha "HTMX OOB-swap partials that hand-duplicate full-page markup drift silently": Bundle 1 already wired the expanded-row to use the canonical advisory rendering partial; Bundle 2 adds advisories to the existing tuple without touching the partial structure. Verify by reading the partial post-implementation.
- Per CLAUDE.md gotcha "Queries ordered by `started_ts DESC` on `pipeline_runs` mask prior completes mid-run": NOT applicable here — no pipeline_runs queries added.
- Per CLAUDE.md gotcha "Session-anchor read/write mismatch": NOT applicable here — advisory composition is request-time / live; no session-anchored writes.

---

## §4 Adversarial review (Codex)

### §4.1 Setup (IMPLEMENTER runs this — convention per orchestrator-context "Executing-plans dispatch convention" 2026-05-02)

After ALL task-family commits land + tests are GREEN at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `3e8-bundle-2-sell-side-advisories`
   - `SPEC_PATH`: `docs/3e8-bundle-2-sell-side-advisories-brief.md`
   - `PLAN_PATH`: `docs/3e8-bundle-2-sell-side-advisories-brief.md`
   - `BASELINE_SHA`: (the SHA pinned in §2.1 above)
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **2-4 rounds** (Bundle 1 took 4 rounds for similar surface size).

### §4.2 Pre-empt list

Adversarial-review value-add concentrates on:

- **`r_so_far` semantics across rules.** Bundle 2 introduces TWO new rules that read `r_so_far` (§4.B trim; §4.K target-hit) plus one that reads `current_price - sma50` directly (§4.D parabolic). Verify the `r_so_far` helper is called consistently across the three (or two, plus the breakeven precedent) with the same arguments + price source.
- **"No prior trim" predicate correctness.** The choice of `remaining_shares == initial_shares` vs `has_been_trimmed` vs fill-count check is implementer-discretionary post-recon. The Codex round should validate that the chosen predicate behaves correctly under the THREE fill scenarios: (a) zero fills, (b) one partial sell fill, (c) one full-close sell fill. Scenario (c) shouldn't fire because the trade is no longer "open" — confirm the open-trade filter upstream excludes it; the §4.B predicate doesn't need to re-check.
- **ADR floor / nan handling.** When OHLCV has <20 bars (lookback default), `adr_pct(df, lookback=20)` may return `nan` from a partial-tail mean. Implementer chooses: (a) filter `nan` at construction time (set `adr_pct = None`), or (b) guard at rule time (`if math.isnan(ctx.adr_pct): return None`). Either works; Codex should verify the choice is consistent + tested.
- **Cfg-key defaults regression test.** New cfg keys must respect the existing `swing.config.toml` round-trip pattern: defaults applied when key absent; overrides applied when present. Verify with a parametrized `test_stop_advisory_config_round_trip` test.
- **5-site rule-ordering consistency.** Across all five composition sites, the three new rules should appear in the same relative position. Easy to drift; Codex round should grep for `trim_into_strength` across the codebase and confirm consistent ordering.
- **§4.K NULL planned_target_R guard.** `trade.planned_target_R IS NULL` is the common case for pre-Phase-8 trades (and any post-Phase-8 trade where operator didn't enter a target). Rule MUST no-op silently; Python `None >= 1.0` raises `TypeError`. Discriminating test: a trade with NULL `planned_target_R` should produce zero §4.K advisories (not raise).
- **§4.D fixture realism.** Default `parabolic_adr_multiple = 7.0` is doctrine-correct for a ~25% extension on a 5%-ADR stock (i.e., 7 × 5 = 35% above 50SMA). Verify the §4.D test fixture uses realistic SMA/ADR/current_price values; an unrealistic fixture risks false-positive testing.
- **Pipeline-side ADR computation cost.** Bundle 1's `_CachingFetcherWrapper` was introduced to amortize OHLCV fetches across briefing helpers; ADR computation re-uses the same OHLCV bundle so should incur ~zero additional cost. Verify the cache-hit ratio is unchanged post-Bundle-2.
- **Briefing snapshot test must distinguish.** Per operator-memory `feedback_regression_test_arithmetic.md`: for each of the three new rules, the snapshot test must include a fixture that DOES fire AND a fixture that DOES NOT fire, and the snapshot must differ between them. Don't snapshot only the fire-case.

---

## §5 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR:

- **Surface 1 — Dashboard list-view + open-positions row.** Operator opens `http://127.0.0.1:8080/` (after `swing web`); verifies the open-positions table's Advisory column includes the three new rules when triggered. Specifically: if DHC has crossed +1R since 2026-05-08, the trim-into-strength advisory should be visible (subject to no prior trim).
- **Surface 2 — Open-positions expanded HTMX row.** Operator clicks the expand action on a row; verifies the expanded view shows the same three new advisories as the list view (per Bundle 1 dedup convention).
- **Surface 3 — Trade-detail page.** Operator navigates to `http://127.0.0.1:8080/trades/{id}` for an open trade; verifies the Advisories section shows the three new rules when triggered.
- **Surface 4 — Pipeline-emitted briefing.** Operator runs `swing pipeline run` (or waits for the next pipeline run); opens `exports/<session>/briefing.md` + `briefing.html`; verifies per-open-position rendering shows the three new advisories when triggered.
- **Surface 5 — DHC-specific empirical check.** Operator reads DHC's current open_R + planned_target_R + (current_price - sma50) / sma50 × 100; compares against the three rules' triggers; verifies the surfaces above agree with the operator's manual calculation. (Sanity check that the rule predicates match operator's mental model.)
- **Surface 6 — pytest + ruff.** From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows 18 (no new violations) or fewer.

**Expected test count delta:** +18-25 (Task A: 4 cfg/context tests; Task B: 14 rule unit tests; Task C: 5-9 composer + snapshot tests).
**Expected ruff baseline:** 18 (no change) or 17-18 (depending on imports added).

---

## §6 Return report shape

After operator-gate PASS, draft a return report with:

1. Final HEAD on branch
2. Commit count breakdown (task-impl / Codex-fix / operator-gate-fix)
3. Codex round chain (e.g., "R1 X/Y/Z → R2 ... → R3 NO_NEW_CRITICAL_MAJOR")
4. Test count delta (expect +18-25)
5. Ruff baseline delta
6. Operator-gate surface results (S1-S6)
7. Per-task-family deviations from the brief
8. Codex Major findings ACCEPTED with rationale
9. Watch items surfaced but not acted on (for V2 bank)
10. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8 pattern)

---

## §7 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading 3e8-bundle-2-sell-side-advisories dispatch.

WORKING DIRECTORY: c:\Users\rwsmy\swing-trading\.worktrees\3e8-bundle-2-sell-side-advisories
BRANCH: 3e8-bundle-2-sell-side-advisories
BASELINE_SHA: <pinned in brief §2.1>

Step 1 — Read the dispatch brief end-to-end:
  docs/3e8-bundle-2-sell-side-advisories-brief.md

It locks 9 design decisions (§0.3) that you do NOT re-litigate. Three task families:
  - Task A: AdvisoryContext extension + cfg keys
  - Task B: three new rule implementations
  - Task C: 5-site composition mirroring + ADR plumbing

Step 2 — Read CLAUDE.md + docs/orchestrator-context.md (binding conventions).

Step 3 — Verify worktree state:
  git rev-parse HEAD                  # expect BASELINE_SHA from brief §2.1
  git status                          # expect clean
  python -m pytest -m "not slow" -q   # expect baseline GREEN (2206 passed)

Step 4 — Execute the brief via superpowers:subagent-driven-development. TDD discipline per task family.

Step 5 — After ALL task families land + GREEN, run the adversarial review YOURSELF (per §4.1):
  - Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
  - Invoke copowers:adversarial-critic with PHASE=3e8-bundle-2-sell-side-advisories,
    SPEC_PATH=docs/3e8-bundle-2-sell-side-advisories-brief.md,
    PLAN_PATH=docs/3e8-bundle-2-sell-side-advisories-brief.md,
    BASELINE_SHA=<the SHA from §2.1>
  - Iterate rounds + land Codex-fix commits until NO_NEW_CRITICAL_MAJOR.

Step 6 — Draft return report per §6 + signal orchestrator. Operator drives §5 witnessed verification gate; orchestrator handles integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Extract a shared composer (Bundle 1 V2 watch item; deferred to a future dispatch)
  - Switch §4.B to calendar trigger (operator locked R-multiple in §0.3 #1)
  - Switch §4.D to 3e.8 arbitrary defaults (operator locked DST D.7 doctrine in §0.3 #2)
  - Add intraday-EMA reference for §4.D (V2 watch item; daily-bar 50SMA in V1)
  - Add maturity-stage gating to the new rules (Bundle 3 work)
```

---

## §8 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-11 (post-Bundle-1-ship handoff).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `202f8d6` on main (post-Bundle-1-ship + handoff brief).
- **Worktree path (binding):** `.worktrees/3e8-bundle-2-sell-side-advisories/`.
- **Baseline test count:** 2206 fast (1 skipped).
- **Baseline ruff count:** 18 (E501 only).
- **Expected post-dispatch test count:** ~2224-2231 (+18-25).
- **Expected post-dispatch ruff count:** 18 (no change) or 17-18.
- **Bundle 1 carry-over:** advisory composition is hand-duplicated across 5 paths (V2 watch item banked). Bundle 2 ACCEPTS the drift risk; mirrors all 5 sites consistently. Future V2 extracts a shared composer when triggered.
