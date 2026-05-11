# 3e.8 Bundle 3 — Maturity-stage MA hint + M.2 R-multiple stop-tighten hint (Option δ) dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Add TWO complementary sell-side advisory rules to `swing/trades/advisory.py` and wire each into all SIX advisory-composition surfaces (web list view + open-positions row + open-positions expanded HTMX partial + trade-detail page + pipeline briefing composer + CLI `swing trade advisory`):

1. **§4.A.bis** — `suggest_maturity_stage_trail_ma_hint` — emit a maturity-stage → recommended-trail-MA hint based on the trade's active-snapshot `maturity_stage` (operator-policy hybrid of M.2 + DST D.3 per Tier-3 #6).
2. **M.2** — `suggest_r_multiple_stop_tighten` — emit an R-multiple stop-tighten hint when `r_so_far ≥ cfg.stop_advisory.tighten_at_r_multiple` (default 2.0R; doctrine-anchored to TLSMW Ch 13 p. 296 verbatim).

Both are **advisory-message-only**. No schema changes. No V2.1 §VII.F routing. NEW cfg key on `StopAdvisoryConfig`. NEW `maturity_stage` field on `AdvisoryContext` plumbed through all 6 composition surfaces.

**Expected duration:** ~4-5 hr implementation + ~30-45 min dispatch overhead. Total ~5-6 hr. Smaller than Bundle 2 (~9-11 hr) — two rules vs three; no new data-boundary helper (ADR equivalent); maturity-stage data already loaded for the dashboard daily-management tile + briefing daily-management snapshot.

**Skill posture:**
- Invoke `superpowers:subagent-driven-development` directly (NOT via `copowers:executing-plans` wrapper).
- DO NOT invoke `superpowers:writing-plans` or `copowers:brainstorming` — design is locked in §0.3 below by orchestrator + operator (handoff brief 2026-05-11 locks Option δ scope + cfg defaults; this brief locks the remaining minor questions).
- Adversarial review via `copowers:adversarial-critic` after all task families land. Iterate to NO_NEW_CRITICAL_MAJOR. Expected 2-3 Codex rounds (smaller surface than Bundle 2; less numeric/data-boundary risk; main risks concentrated on maturity-stage plumbing across 6 sites + composition-surface enumeration completeness).

---

## §0 Read first

### §0.1 Backlog entries
- `docs/phase3e-todo.md`:
  - 2026-05-10 §3e.8 disposition section "Bundle 3 — Maturity-stage hint + M.2 R-multiple stop-tighten hint (Option δ) — DISPATCH-READY POST-BUNDLE-2"
  - 2026-05-11 V2 watch items section from Bundle 2 ship (composition-surface enumeration lesson; APPLIED here in §0.2 enumeration discipline)
- `docs/3e8-sell-side-advisories-investigation.md`:
  - §4.A + §4.A.bis (line 250-336)
  - §5.1 per-stage advisory matrix (line 572-588)
  - §5.3 DHC-specific application (line 607-626)
- `reference/methodology/minervini-sell-side-rules.md`:
  - M.2 sell-into-strength (line 39-72) — TLSMW Ch 13 p. 296 verbatim quote with the "7%/20%" example (=2.86R) anchoring the default 2.0R tighten trigger.
- `reference/methodology/dst-take-profit-and-trail.md`:
  - D.3 10DSMA primary trail (line 99-134) — speed-correlated MA selection per Qullamaggie; project-policy maturity-stage gating is the operator-policy hybrid, NOT doctrine-faithful.
- `docs/3e8-bundle-1-advisory-parity-brief.md` + `docs/3e8-bundle-2-sell-side-advisories-brief.md` — template + accumulated locks reference.

### §0.2 Code surface

**For both rules (advisory.py):**
- `swing/trades/advisory.py:18-26` — current `AdvisoryContext` dataclass post-Bundle-2 (has `adr_pct: float | None = None` + `has_been_trimmed: bool = False`). Add `maturity_stage: str | None = None` field for §4.A.bis (safe default; NULL means "no daily-management snapshot yet → rule no-ops").
- `swing/trades/advisory.py:35-43` — current `suggest_breakeven` shape. Mirror pattern for the two new rules.
- `swing/config.py:91+` — current `StopAdvisoryConfig` post-Bundle-2 (has `trim_first_r_trigger`, `trim_first_pct_default`, `parabolic_adr_multiple` + `__post_init__` NaN/inf/out-of-range validators). Add:
  - `tighten_at_r_multiple: float = 2.0` (NEW; M.2 trigger; operator-tunable; default rough-match to TLSMW 7%/20% example = 2.86R but conservatively floored to 2.0R).
- Extend `__post_init__` validator to reject NaN / inf / `tighten_at_r_multiple <= 0` per the Bundle 2 R3 defensive-numeric pattern.

**For §4.A.bis maturity-stage hint:**
- `swing/trades/daily_management.py:324` — `compute_maturity_stage(open_MFE_R_to_date)` returns one of: `None`, `"pre_+1.5R"`, `"+1.5R_to_+2R"`, `">=+2R_trail_eligible"`.
- `swing/trades/daily_management.py:53` — `select_active_snapshot` reads the per-trade most-recent active snapshot from `daily_management_records`.
- Mapping (operator-policy lock per Tier-3 #6):
  - `"pre_+1.5R"` → `"20MA"` (trade has not yet proven itself; default trail)
  - `"+1.5R_to_+2R"` → `"20MA"` (mature; same default trail; pending +2R promotion)
  - `">=+2R_trail_eligible"` → `"10MA"` (well-mature; tighter trail unlocked)
  - `None` (no snapshot) → rule no-ops

**For M.2 R-multiple stop-tighten:**
- `swing/trades/equity.py` (or wherever `r_so_far(trade, current_price)` is canonical) — reuse the existing helper; no new math needed.
- No additional data dependencies beyond `AdvisoryContext.current_price` + `trade.entry_price` + `trade.initial_stop`.

**For the 6-site composition mirroring (lesson applied from Bundle 2):**

Per the Bundle 2 V2 lesson banked at `docs/phase3e-todo.md` "2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 2 ship", advisory composition has 6 sites and the brief MUST grep to confirm (not memory-enumerate). Bundle 3 will add the two new rules + `maturity_stage` plumbing to each:

1. `swing/web/view_models/dashboard.py:build_dashboard` — composes per-row advisories for the dashboard list view.
2. `swing/web/view_models/open_positions_row.py:build_open_positions_row` — per-row VM composer.
3. `swing/web/view_models/dashboard.py:build_open_positions_expanded` — HTMX-expanded row composer.
4. `swing/web/view_models/trades.py:build_trade_detail_vm` — `/trades/{id}` page composer.
5. `swing/pipeline/runner.py:compose_open_trade_advisories_for_briefing` (introduced Bundle 1; expanded Bundle 2) — pipeline briefing composer.
6. `swing/cli.py:trade_advisory_cmd` (caught as 6th surface by Bundle 2 Codex R1 Major #1) — CLI `swing trade advisory` command.

ALL SIX need:
- `maturity_stage` threaded into the `AdvisoryContext` constructor call. For web + briefing: read from per-trade active snapshot via `select_active_snapshot` (or whatever the canonical read path is for the surface). For CLI: add `--maturity-stage` flag (similar to Bundle 2's `--adr-pct` flag).
- The two new rule invocations appended to the existing tuple in canonical declaration order (after Bundle 2's three rules).

**For test surface:**
- `tests/trades/test_advisory.py` — unit tests for the two new rule functions.
- `tests/test_config_stop_advisory_bundle3.py` (NEW file mirroring Bundle 2's `tests/test_config_stop_advisory_bundle2.py`) — cfg-validation tests for `tighten_at_r_multiple`.
- `tests/web/test_*` — integration tests for the 4 web composition sites picking up `maturity_stage` from active snapshots.
- `tests/pipeline/test_briefing_advisory_compose.py` — extend with Bundle 3 rule cases.
- `tests/cli/test_cli_advisory.py` — extend with `--maturity-stage` flag + new-rule firing cases.

### §0.3 LOCKED DESIGN DECISIONS (DO NOT re-litigate)

Locked by orchestrator handoff brief 2026-05-11 + in-session 2026-05-11:

1. **§4.A.bis fires informationally; does NOT suppress existing `trail_10ma` / `trail_20ma` advisories.** Per handoff brief Step 5.1: "Does NOT suppress existing `trail_10MA` / `trail_20MA` advisories". Per investigation §4.A.bis line 336: "ADVISORY-MESSAGE-ONLY — does not suppress anything, just adds a hint." The full `§4.A` classification-altering trail-MA gating with suppression is BANKED-WITHOUT-GATE per phase3e-todo (revisit trigger = n≥10 closed trades with Bundle-3 evidence).

2. **§4.A.bis maturity-stage → MA mapping** (operator-policy lock per Tier-3 #6):
   - `"pre_+1.5R"` → recommended MA: `"20MA"`
   - `"+1.5R_to_+2R"` → recommended MA: `"20MA"`
   - `">=+2R_trail_eligible"` → recommended MA: `"10MA"`
   - `None` (no active snapshot) → rule no-ops (returns `None`)
   - Message: `f"Maturity stage {ctx.maturity_stage} → recommended trail-MA: {recommended_ma}"`
   - Rule name: `"maturity_stage_trail_ma_hint"`
   - Fires regardless of whether the existing `trail_10ma` / `trail_20ma` advisories also fire (complementary, not redundant — the operator can read both at once).

3. **§4.A.bis is NOT doctrine-faithful** — DST D.3 selects trail-MA by stock-strength/speed (strongest→10MA, strong→20MA, slower institutional→50MA per the Qullamaggie quote in `dst-take-profit-and-trail.md` line 121-125), NOT by trade-maturity stage. The maturity-stage gating is a PROJECT/OPERATOR-POLICY interpretation per Tier-3 #6. V2 doctrine-faithful version would require a new schema field (`stock_speed_class` captured at entry) and is OUT OF SCOPE.

4. **M.2 R-multiple stop-tighten trigger** (doctrine per TLSMW Ch 13 p. 296):
   - Default `tighten_at_r_multiple = 2.0` (rough match to TLSMW 7%/20% example = 2.86R; conservatively floored to 2.0R; operator-tunable).
   - Predicate: fires when `r_so_far(trade, ctx.current_price) >= ctx.config.tighten_at_r_multiple`.
   - Message: `f"At +{r_so_far(trade, ctx.current_price):.2f}R (≥{ctx.config.tighten_at_r_multiple:.1f}× stop) — Minervini M.2: consider moving stop to breakeven OR tightening trail to lock in majority of gain"`.
   - Rule name: `"r_multiple_stop_tighten"`.
   - Fires regardless of current stop position (e.g., still fires when current_stop is already at breakeven — the second half of the message "tighten trail" remains actionable).
   - Fires regardless of maturity stage (per §5.1 matrix — M.2 is cross-cutting on R-multiple).
   - Does NOT suppress existing `breakeven` advisory (which uses a different trigger — `r_so_far >= 1.0R AND current_stop < entry_price`); they may both fire concurrently for trades crossing +2R with stop still below entry, which is the intended behavioral overlap.

5. **No suppression interactions; both new rules append to the existing advisory tuple.** Bundle 1 + Bundle 2 established that advisory rules are accumulative — operator sees all firing advisories. Bundle 3 maintains the same pattern.

6. **`AdvisoryContext` extension** — add `maturity_stage: str | None = None` as a keyword-able field with safe default (mirrors Bundle 2's `adr_pct` + `has_been_trimmed` pattern). Existing callers that construct without the new field continue to work; rule no-ops on `None`.

7. **6-site composition surface enumeration is BINDING.** Per Bundle 2 lesson: the canonical advisory composition surface count is 6 (web ×4 + pipeline briefing + CLI). The implementer's recon at task family start MUST grep:
   ```
   grep -rn "AdvisoryContext(" swing/
   grep -rn "compose_open_trade_advisories" swing/
   ```
   and confirm all 6 sites are addressed. If a 7th site surfaces during recon (e.g., a route handler that builds an `AdvisoryContext` inline that wasn't in the file list), surface to orchestrator BEFORE proceeding — don't silently fix.

8. **Hand-duplicate the 6-site composition mirror; do NOT extract a shared composer.** Bundle 1 V2 watch item #1 banked the shared-composer extract as a separate dispatch. Bundle 2 ACCEPTED the drift risk at 5 sites; Bundle 3 ACCEPTS the same drift risk at 6 sites. If, during implementation, the implementer surfaces a clear case that 6-site mirroring is structurally impossible OR the drift cost finally outweighs the dispatch-scope benefit, pause + surface to orchestrator before extracting a composer.

9. **No schema; no V2.1 §VII.F routing.** Pure advisory-rule additions + cfg key + AdvisoryContext field plumb.

10. **No emission-format changes to existing rules.** §4.A.bis + M.2 messages are new strings; existing rules' messages are unchanged.

11. **`__post_init__` validator pattern for `tighten_at_r_multiple`** — extend the existing Bundle 2 validators in `StopAdvisoryConfig.__post_init__`: reject NaN, reject inf, reject `tighten_at_r_multiple <= 0`. Mirror the Bundle 2 R3 Major #1 fix shape.

12. **HTMX safety:** the open-positions expanded row is the only HTMX surface affected. Bundle 1 + 2 already wired advisory rendering there. Bundle 3 adds new rules INSIDE the existing advisory list — no template structure changes. Per CLAUDE.md gotcha "HTMX response leading with `<tr>` triggers `makeFragment`", verify the expanded-row response shape is unchanged after Bundle 3 adds the new rules to the per-row advisory tuple.

13. **DHC operational reality check (informs operator-witnessed gate):**
   - Per the post-Bundle-2-ship briefing.md (2026-05-11 worktree pipeline run 51): DHC at maturity_stage=`pre_+1.5R`, MFE 0.88R, current R=0.85R.
   - §4.A.bis: WILL fire on DHC → "Maturity stage pre_+1.5R → recommended trail-MA: 20MA". Operator can compare against current behavior (today operator must read the maturity-badge cell + map mentally; Bundle 3 closes this mental-mapping step).
   - M.2 R-multiple stop-tighten: will NOT fire on DHC (r=0.85R < 2.0R). Suppression-path verified empirically.
   - LAR has maturity_stage=`pre_+1.5R` (MFE 0.06R) → §4.A.bis fires there too (`"recommended trail-MA: 20MA"`). LAR's existing parabolic advisory + new maturity-stage advisory complement each other.
   - For M.2 fire-verification: no current open trade has r ≥ 2.0R; FIRE path covered by unit tests only (per Bundle 2 precedent for trim_into_strength / planned_target_r_hit fire-suppression on live data).

---

## §1 Strategic context

This is the post-3e.8-investigation Bundle 3 commission and the final Bundle in the 3e.8 advisory-expansion arc. Together with Bundle 1 (advisory parity §4.E + §4.F) and Bundle 2 (sell-side advisories §4.B + §4.K + §4.D), Bundle 3 closes the operator-locked subset of the §6 investigation decision matrix.

The two new rules address DIFFERENT operator questions, per the handoff brief's "Why hybrid" rationale:
- **§4.A.bis** answers "which trail-MA should I use?" (MFE-anchored maturity stage; informational hint)
- **M.2** answers "should I tighten anything yet?" (live R-multiple; action-prompting hint)

For DHC's current state (open_R=0.85, MFE=0.88R, pre_+1.5R) NEITHER fires for action yet — but §4.A.bis fires informationally TODAY because DHC has a maturity-stage value. M.2 will activate once DHC (or any open trade) crosses +2R.

**Schema state (binding):** Production DB at schema_version 16 post-Phase 8 ship. No schema work in scope.

**What's NOT in scope:**
- §4.A full classification-altering trail-MA gating with suppression (banked-without-gate per phase3e-todo; revisit trigger = n≥10 closed trades' worth of Bundle-3 evidence)
- Stock-speed-driven trail-MA selection (doctrine-faithful DST D.3 alternative to maturity-stage gating; requires new schema)
- D.6 intraday-EMA reference for trail (Bundle 2 V2 watch item; daily-bar V1)
- §4.C / §4.C.bis time-stop changes (banked-without-gate)
- §4.H / §4.I / §4.J (deferred-with-second-source-gate)
- Shared-composer extract (Bundle 1+2 V2 watch item; carries forward unchanged)

---

## §2 Worktree + binding conventions

### §2.1 Worktree
- **Branch:** `3e8-bundle-3-maturity-and-stop-tighten-hints`
- **Worktree directory:** `.worktrees/3e8-bundle-3-maturity-and-stop-tighten-hints/` at repo root.
- **BASELINE_SHA:** `9d5cfb1` (HEAD of `main` after Bundle 2 ship + housekeeping; this is the commit BEFORE this brief is committed). The Codex baseline diff will include one doc-only commit (the Bundle 3 brief itself) — harmless, mirrors Bundle 2's one-commit-lag pattern.
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main` immediately before creating the worktree — should be the brief commit). Implementer notes the actual SHA in their return report.

### §2.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task families land + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §2.3 Worktree data dir (Bundle 2 dispatch-lesson encoded)

Worktrees do NOT inherit `data/finviz-inbox/` from main (gitignored). If the implementer needs to trigger a live pipeline run for operator-gate verification, they must FIRST:

```powershell
mkdir .worktrees\3e8-bundle-3-maturity-and-stop-tighten-hints\data\finviz-inbox
# Then either let _step_finviz_fetch auto-fetch via API, OR
# copy main's most recent finvizDDMmmYYYY.csv into the worktree's inbox dir
```

This was a Bundle 2 dispatch-time fix-up; not strictly required if the implementer relies on test-suite coverage for verification. Documented here so the implementer doesn't burn a cycle on the "no CSV files" error if they go for live-gate verification.

### §2.4 Commits
- Conventional prefix:
  - `feat(advisory): Task A.X — <description>` for rule additions in `swing/trades/advisory.py`
  - `feat(config): Task A.X — <description>` for `StopAdvisoryConfig` extensions
  - `feat(web): Task A.X — <description>` for VM composer changes
  - `feat(pipeline): Task A.X — <description>` for `compose_open_trade_advisories_for_briefing` changes
  - `feat(cli): Task A.X — <description>` for CLI `--maturity-stage` flag changes
  - `test(...)` for test-only commits
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change OR cluster cycles when tests are essentially discriminators of one feature.

### §2.5 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§5).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping.

### §2.6 Verify command
PowerShell from inside worktree:
```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```

---

## §3 Per-task implementation breakdown

### §3.1 Task family A — `AdvisoryContext.maturity_stage` field + cfg key + cfg validator

**Acceptance criteria:**

- (A.AC.1) `swing/trades/advisory.py` `AdvisoryContext` dataclass gains `maturity_stage: str | None` field with safe default (`None`).
- (A.AC.2) `swing/config.py` `StopAdvisoryConfig` gains:
  - `tighten_at_r_multiple: float = 2.0`
- (A.AC.3) `__post_init__` validator extended to reject NaN / inf / non-positive `tighten_at_r_multiple` (mirror Bundle 2 R3 Major #1 pattern).
- (A.AC.4) Existing tests that instantiate `AdvisoryContext` and `StopAdvisoryConfig` (without the new fields) continue to pass (defaults make this safe).

**Suggested test names:**

- `test_advisory_context_accepts_maturity_stage_field`
- `test_advisory_context_maturity_stage_defaults_to_none`
- `test_stop_advisory_config_has_tighten_at_r_multiple_default`
- `test_stop_advisory_config_rejects_nan_tighten_at_r_multiple`
- `test_stop_advisory_config_rejects_inf_tighten_at_r_multiple`
- `test_stop_advisory_config_rejects_negative_tighten_at_r_multiple`
- `test_stop_advisory_config_rejects_zero_tighten_at_r_multiple`

**Suggested commit shape:**
- A.1: `feat(advisory): Task A.1 — add maturity_stage field to AdvisoryContext` (single commit; trivial change with RED+GREEN test)
- A.2: `feat(config): Task A.2 — add tighten_at_r_multiple cfg key + validator` (single commit; trivial change with RED+GREEN tests for default + validator rejections)

**Watch items:**
- Default-mutability: ensure `maturity_stage` default is `None` (immutable). Same pattern as Bundle 2's `adr_pct`.
- Existing `AdvisoryContext` callers should not break — add the field as keyword-only OR at the END of the field list (after Bundle 2's `adr_pct` + `has_been_trimmed`).
- Per CLAUDE.md gotcha "`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM": NOT applicable — `AdvisoryContext` is service-layer; `StopAdvisoryConfig` is cfg-layer. Neither is a page VM.

### §3.2 Task family B — Two new rule implementations

**Acceptance criteria:**

- (B.AC.1) `swing/trades/advisory.py` gains `suggest_maturity_stage_trail_ma_hint(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None`:
  - Returns `None` when `ctx.maturity_stage is None`
  - Maps `ctx.maturity_stage` → recommended_ma per §0.3 #2 mapping (`pre_+1.5R` → `20MA`; `+1.5R_to_+2R` → `20MA`; `>=+2R_trail_eligible` → `10MA`)
  - For any other (unexpected) maturity_stage value, returns `None` (defensive: should not occur because `compute_maturity_stage` returns only the three values + None, but guard anyway).
  - Returns `AdvisorySuggestion(rule="maturity_stage_trail_ma_hint", message="...")` per §0.3 #2 message template.
- (B.AC.2) `swing/trades/advisory.py` gains `suggest_r_multiple_stop_tighten(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None`:
  - Returns `None` when `r_so_far(trade, ctx.current_price) < ctx.config.tighten_at_r_multiple`
  - Returns `AdvisorySuggestion(rule="r_multiple_stop_tighten", message="...")` per §0.3 #4 message template otherwise.
- (B.AC.3) Each rule's `AdvisorySuggestion.rule` field is a unique string (`"maturity_stage_trail_ma_hint"`, `"r_multiple_stop_tighten"`) that does NOT collide with any Bundle 1 / Bundle 2 / pre-existing rule string.
- (B.AC.4) Each rule's message respects the f-string template in §0.3 (operator will visually verify wording in §5 surfaces).

**Suggested test names:**

- `test_suggest_maturity_stage_trail_ma_hint_returns_none_when_stage_is_none`
- `test_suggest_maturity_stage_trail_ma_hint_pre_1_5r_recommends_20ma`
- `test_suggest_maturity_stage_trail_ma_hint_1_5r_to_2r_recommends_20ma`
- `test_suggest_maturity_stage_trail_ma_hint_2r_plus_recommends_10ma`
- `test_suggest_maturity_stage_trail_ma_hint_unknown_stage_returns_none`
- `test_suggest_maturity_stage_trail_ma_hint_message_format`
- `test_suggest_r_multiple_stop_tighten_returns_none_below_trigger`
- `test_suggest_r_multiple_stop_tighten_fires_at_trigger`
- `test_suggest_r_multiple_stop_tighten_fires_above_trigger`
- `test_suggest_r_multiple_stop_tighten_message_format`
- `test_suggest_r_multiple_stop_tighten_message_uses_cfg_multiple`

**Suggested commit shape:**
- B.1: `feat(advisory): Task B.1 — suggest_maturity_stage_trail_ma_hint rule + tests` (RED+GREEN cycle)
- B.2: `feat(advisory): Task B.2 — suggest_r_multiple_stop_tighten rule + tests` (RED+GREEN cycle)

**Watch items:**
- For §4.A.bis: the `compute_maturity_stage` return-value enum can grow in V2 (e.g., new "very_well_mature" tier). Treat unknown values as no-op (return None) rather than raising.
- For M.2: `r_so_far` requires `trade.initial_stop` to be set (otherwise the risk denominator is undefined). Verify the helper handles this — existing rules like `breakeven` already use `r_so_far` so the pattern is established. If `initial_stop` is `None`, the rule should silently no-op (let `r_so_far` return None or raise → catch and return None at rule layer).
- Per CLAUDE.md gotcha "Python `... or ""` idiom collides with SQL CHECK-constraint nullability": NOT applicable here — no new schema.
- **Pre-empt regression-test arithmetic** per operator-memory feedback `feedback_regression_test_arithmetic.md`: for §4.A.bis, compute the rule's output under BOTH stages where MA differs (`pre_+1.5R` → 20MA vs `>=+2R_trail_eligible` → 10MA) to confirm the test distinguishes. For M.2, fixtures should have r=1.9R (no-fire) AND r=2.1R (fire) to confirm trigger boundary.

### §3.3 Task family C — 6-site composition mirroring + maturity_stage plumbing

**Acceptance criteria:**

- (C.AC.1) All SIX advisory-composition sites (per §0.2) add the two new rules to their per-trade advisory tuple in a consistent order (append after Bundle 2's three rules: `..., trim_into_strength, planned_target_r_hit, parabolic_trim, maturity_stage_trail_ma_hint, r_multiple_stop_tighten`).
- (C.AC.2) Each composition site constructs `AdvisoryContext` with the new `maturity_stage` field populated from the per-trade active snapshot via `select_active_snapshot` (or equivalent). When no active snapshot exists for a trade, `maturity_stage = None` (rule no-ops correctly per B.AC.1).
- (C.AC.3) Dashboard list-view row rendering shows the two new rules when triggers met (operator verifies via §5 Surface 1; §4.A.bis fires on every open trade with non-NULL maturity_stage; M.2 only fires when r ≥ 2.0R).
- (C.AC.4) Open-positions expanded HTMX row rendering shows the two new rules (operator verifies via §5 Surface 2).
- (C.AC.5) Trade-detail page rendering shows the two new rules (operator verifies via §5 Surface 3).
- (C.AC.6) Pipeline-emitted briefing rendering shows the two new rules (operator verifies via §5 Surface 4).
- (C.AC.7) CLI `swing trade advisory` command accepts a new `--maturity-stage` flag (mirroring Bundle 2's `--adr-pct` flag pattern) and emits the two new rules when triggers met (operator verifies via §5 Surface 5 manual CLI invocation OR test suite covers the path).
- (C.AC.8) Snapshot/golden tests cover the new rules' presence in pipeline briefing (extend `tests/pipeline/test_briefing_advisory_compose.py`).
- (C.AC.9) NO new yfinance / OHLCV fetches introduced (maturity_stage reads from DB only; no external data sources).

**Suggested test names:**

- `test_dashboard_open_positions_row_includes_maturity_stage_hint`
- `test_dashboard_open_positions_row_passes_maturity_stage_to_context`
- `test_open_positions_expanded_includes_maturity_stage_hint`
- `test_trade_detail_vm_includes_maturity_stage_hint`
- `test_compose_open_trade_advisories_for_briefing_includes_bundle_3_rules`
- `test_cli_trade_advisory_maturity_stage_flag_threads_through`
- `test_cli_trade_advisory_fires_maturity_stage_hint`
- `test_cli_trade_advisory_fires_r_multiple_stop_tighten`
- `test_briefing_md_renders_maturity_stage_trail_ma_hint_when_triggered`
- `test_briefing_md_renders_r_multiple_stop_tighten_when_triggered`

**Suggested commit shape:**
- C.1: `feat(advisory): Task C.1 — thread maturity_stage into AdvisoryContext on 4 web composition sites` (single commit)
- C.2: `feat(pipeline): Task C.2 — thread maturity_stage into AdvisoryContext on briefing composer` (single commit)
- C.3: `feat(cli): Task C.3 — add --maturity-stage flag to swing trade advisory CLI` (single commit)
- C.4: `feat(web,pipeline,cli): Task C.4 — add Bundle 3 rules to all 6 composition sites` (single commit OR split per-surface if cleaner)
- C.5: `test(pipeline): Task C.5 — extend briefing snapshot tests for Bundle 3 rules` (single commit)

**Watch items:**
- Per Bundle 2 V2 lesson: 6-site hand-duplication is accepted-with-rationale. Maintain rule-ordering consistency. Bundle 2's rules are at positions 9-11 in the per-trade tuple (after the 8 pre-existing rules); Bundle 3's should append at positions 12-13.
- Per CLAUDE.md gotcha "OHLCV fetch scope = open-trade tickers ONLY": NOT applicable here — Bundle 3 doesn't touch OHLCV; `maturity_stage` is DB-sourced.
- Per CLAUDE.md gotcha "Session-anchor read/write mismatch (forward-looking `action_session_for_run` vs backward-looking `last_completed_session`)": `daily_management_records` writer stamps `review_date` per its own session-anchor convention (per `swing/trades/daily_management.py:567`); reader (`select_active_snapshot`) selects by most-recent-without-session-anchor-predicate. **Verify before reading from any new path** that the active-snapshot selection uses `select_active_snapshot` (which queries by ORDER BY recency, NOT by `review_date = action_session_for_run(...)`). If you find yourself writing a new query like `WHERE review_date = action_session_for_run(now())`, STOP and use `select_active_snapshot` instead.
- Per CLAUDE.md gotcha "HTMX OOB-swap partials that hand-duplicate full-page markup drift silently": NOT applicable — Bundle 3 doesn't touch templates; only adds new rules to the existing advisory tuple.
- Per CLAUDE.md gotcha "External-API empty-result must be treated as transient when write-through-caching": NOT applicable — `maturity_stage` comes from DB writes by `_step_daily_management`, not external API; if the snapshot is missing (e.g., trade just opened, no daily-management run yet), rule correctly no-ops.

---

## §4 Adversarial review (Codex)

### §4.1 Setup (IMPLEMENTER runs this — convention per orchestrator-context "Executing-plans dispatch convention" 2026-05-02)

After ALL task-family commits land + tests are GREEN at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `3e8-bundle-3-maturity-and-stop-tighten-hints`
   - `SPEC_PATH`: `docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md`
   - `PLAN_PATH`: `docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md`
   - `BASELINE_SHA`: `9d5cfb1`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **2-3 rounds** (Bundle 3 has smaller numeric/data-boundary surface than Bundle 2; main risks concentrated on composition-surface completeness + maturity_stage plumbing correctness).

### §4.2 Pre-empt list

Adversarial-review value-add concentrates on:

- **6-site composition completeness.** Per Bundle 2 R1 Major #1 lesson: the brief enumerates 6 sites; verify implementer addressed ALL six (not 5). Specifically: grep for `AdvisoryContext(` invocations and confirm each one is updated to pass `maturity_stage`. If the implementer missed CLI again, Codex must catch it.
- **`maturity_stage` source-of-truth consistency.** All 6 composition sites should read `maturity_stage` from the SAME canonical source (per-trade `select_active_snapshot` result). Mixing sources (e.g., dashboard reads from active_snapshot but briefing reads from the dataclass directly) would create drift.
- **Rule-ordering consistency across 6 sites.** Bundle 3's two new rules should appear in the SAME relative position at every site. Easy to drift; Codex round should grep for `maturity_stage_trail_ma_hint` + `r_multiple_stop_tighten` across the codebase and confirm consistent ordering.
- **`tighten_at_r_multiple` cfg validation.** Mirror Bundle 2's R3 Major #1 pattern: reject NaN, reject inf, reject non-positive. Discriminating tests for each. If the validator is incomplete, Codex must catch.
- **Active-snapshot session-anchor correctness.** Per CLAUDE.md gotcha "Session-anchor read/write mismatch": verify `select_active_snapshot` is the reader (no session-anchor predicate); writer (`_step_daily_management`) stamps per its own convention. If implementer introduces a new query with `WHERE review_date = action_session_for_run(now())`, Codex should flag it.
- **`r_so_far` helper consumption.** M.2 advisory should reuse the same `r_so_far(trade, current_price)` helper that `breakeven` + `trim_into_strength` use. Don't recompute the R-multiple math inline.
- **CLI `--maturity-stage` flag plumbing.** Mirror Bundle 2's `--adr-pct` flag. Verify the CLI test fixture exercises BOTH the no-flag case (maturity_stage=None → no §4.A.bis fire) AND the flag-supplied case (maturity_stage="pre_+1.5R" → §4.A.bis fires with "20MA").
- **DHC empirical case.** DHC has maturity_stage="pre_+1.5R" today. The Codex round should verify that the integration tests include a DHC-like fixture where §4.A.bis fires + M.2 does NOT fire (because DHC's r=0.85R < 2.0R). This is the discriminating regression-arithmetic case.

---

## §5 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR:

- **Surface 1 — Dashboard list-view + open-positions row.** Operator opens `http://127.0.0.1:8080/` (after `swing web`); verifies the open-positions table's Advisory column shows §4.A.bis maturity-stage hint for every open trade with a non-NULL maturity_stage (all 5 current open trades expected). M.2 should NOT fire on any current trade (no trade at r≥2.0R).
- **Surface 2 — Open-positions expanded HTMX row.** Operator clicks the expand action on any open-positions row; verifies the expanded view shows the §4.A.bis advisory (same as list view per Bundle 1 dedup convention).
- **Surface 3 — Trade-detail page.** Operator navigates to `http://127.0.0.1:8080/trades/{id}` for an open trade; verifies the Advisories section shows §4.A.bis.
- **Surface 4 — Pipeline-emitted briefing.** Operator runs `swing pipeline run` (or uses the fresh worktree briefing if the implementer triggered one); opens `exports/<session>/briefing.md`; verifies per-open-position rendering shows §4.A.bis. (Bundle 2's S4 verified this surface via the same path — fresh worktree pipeline run.)
- **Surface 5 — CLI `swing trade advisory --maturity-stage pre_+1.5R --current-price ... --sma10 ... --sma20 ... --sma50 ... <trade_id>` invocation.** Operator runs the CLI against an open trade with the maturity_stage flag supplied; verifies the output includes the §4.A.bis advisory text. Verifies the test-suite coverage by reading at least one assertion in `tests/cli/test_cli_advisory.py` covering the new flag path.
- **Surface 6 — DHC-specific empirical check.** Operator confirms DHC's dashboard / detail page shows §4.A.bis advisory ("Maturity stage pre_+1.5R → recommended trail-MA: 20MA"). Compares against the daily-management tile's maturity-badge cell + the dashboard's explicit Recommend MA hint (the latter is what Bundle 3 adds). Validates the mental-mapping-step-closure framing from investigation §5.3.
- **Surface 7 — pytest + ruff.** From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows 18 (or 17/18 if imports added) — no new violations.

**Expected test count delta:** +12-18 (Task A: 7 cfg/context tests; Task B: 11 rule unit tests; Task C: 5-8 composer + snapshot + CLI tests).
**Expected ruff baseline:** 18 (no change) or 17-18.

---

## §6 Return report shape

After operator-gate PASS, draft a return report with:

1. Final HEAD on branch
2. Commit count breakdown (task-impl / Codex-fix / operator-gate-fix)
3. Codex round chain (e.g., "R1 X/Y/Z → R2 ... → R3 NO_NEW_CRITICAL_MAJOR")
4. Test count delta (expect +12-18; Bundle 2 exceeded brief estimate due to Codex defensive-hardening — Bundle 3 may also exceed if Codex drives extra cfg-validation discrimination tests)
5. Ruff baseline delta
6. Operator-gate surface results (S1-S7)
7. Per-task-family deviations from the brief
8. Codex Major findings ACCEPTED with rationale (if any)
9. Watch items surfaced but not acted on (for V2 bank)
10. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8 pattern; that's the 5th of the current batch)
11. **Composition-surface verification.** Explicit statement that all 6 sites were addressed (per Bundle 2 lesson — orchestrator wants explicit confirmation that the grep-based enumeration discipline held).

---

## §7 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading 3e8-bundle-3-maturity-and-stop-tighten-hints dispatch.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\3e8-bundle-3-maturity-and-stop-tighten-hints
BRANCH: 3e8-bundle-3-maturity-and-stop-tighten-hints
BASELINE_SHA: 9d5cfb1  (per brief §2.1; this is the Codex baseline = HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (9d5cfb1 → worktree HEAD) will include one doc-only commit (the brief commit itself). That's expected; Codex will treat it as a noop. Same pattern as Bundle 2.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\3e8-bundle-3-maturity-and-stop-tighten-hints -b 3e8-bundle-3-maturity-and-stop-tighten-hints $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md

It locks 13 design decisions (§0.3) that you do NOT re-litigate. Three task families:
  - Task A: AdvisoryContext.maturity_stage field + StopAdvisoryConfig.tighten_at_r_multiple cfg key + __post_init__ validator
  - Task B: 2 new advisory rule implementations (suggest_maturity_stage_trail_ma_hint, suggest_r_multiple_stop_tighten)
  - Task C: 6-site composition mirroring (web ×4 + pipeline briefing + CLI) + maturity_stage plumbing

Step 2 — Read CLAUDE.md + docs/orchestrator-context.md (binding conventions).

Step 3 — Verify worktree state:
  git rev-parse HEAD                   # expect current main HEAD (typically the brief commit)
  git status                           # expect clean
  python -m pytest -m "not slow" -q    # expect baseline GREEN (2277 passed)

Step 4 — Execute the brief via superpowers:subagent-driven-development. TDD discipline per task family.

Step 4a — **Pre-implementation recon step (Bundle 2 lesson applied):**
  Before starting Task C, run:
    grep -rn "AdvisoryContext(" swing/
    grep -rn "compose_open_trade_advisories" swing/
  Confirm 6 composition sites match brief §0.2. If a 7th site exists, STOP and report to orchestrator before proceeding.

Step 5 — After ALL task families land + GREEN, run adversarial review YOURSELF (per §4.1):
  - Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
  - Invoke copowers:adversarial-critic with:
      PHASE=3e8-bundle-3-maturity-and-stop-tighten-hints,
      SPEC_PATH=docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md,
      PLAN_PATH=docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md,
      BASELINE_SHA=9d5cfb1
  - Iterate rounds + land Codex-fix commits until NO_NEW_CRITICAL_MAJOR.
  - Expected convergence: 2-3 rounds.

Step 6 — Draft return report per §6 + signal orchestrator. Operator drives §5 witnessed verification gate; orchestrator handles integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Skip the Step 4a pre-implementation grep recon (Bundle 2 lesson)
  - Extract a shared advisory composer (Bundle 1 V2 watch item; banked for separate dispatch)
  - Add suppression of trail_10ma / trail_20ma when §4.A.bis fires (operator locked "does NOT suppress" in §0.3 #1)
  - Add maturity-stage gating to M.2 (operator locked "fires regardless of maturity stage" in §0.3 #4)
  - Add stock-speed-driven trail-MA selection (V2; not in scope — operator locked maturity-stage-driven in §0.3 #2-#3)
```

---

## §8 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-11 (post-Bundle-2-ship).
- **Brief commit:** `<filled-in-after-commit>` (pinned via second commit if needed; see Bundle 2 pattern).
- **Brief HEAD context:** `9d5cfb1` on main (post-Bundle-2-ship + housekeeping).
- **Worktree path (binding):** `.worktrees/3e8-bundle-3-maturity-and-stop-tighten-hints/`.
- **Baseline test count:** 2277 fast (1 skipped).
- **Baseline ruff count:** 18 (E501 only).
- **Expected post-dispatch test count:** ~2289-2295 (+12-18; Bundle 2 exceeded its estimate by 46 via Codex-driven defensive-hardening; Bundle 3 may also exceed if cfg-validation discrimination drives extra tests).
- **Expected post-dispatch ruff count:** 18 (no change) or 17-18.
- **Bundle 2 lessons carried forward:**
  - 6-site composition-surface enumeration (grep, not memory-enumerate)
  - cfg validator pattern for NaN/inf/non-positive
  - worktree data/finviz-inbox dir setup if live pipeline run needed for gate
  - one-commit-lag BASELINE_SHA pin (acceptable; doc-only commit in Codex diff)
