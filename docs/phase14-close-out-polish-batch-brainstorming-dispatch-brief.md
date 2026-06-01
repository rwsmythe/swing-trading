# Phase 14 Close-Out Polish Batch -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 close-out polish-batch brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for the **Phase 14 close-out polish batch** -- a heterogeneous set of small, well-specified Phase-14-scope cleanups banked across SB1-SB5.5. This is the FIRST item of the close-out tail proper (the Schwab-focused SB5.5 already SHIPPED). The batch items (operator-LOCKed list at `docs/phase3e-todo.md` `#5` "close-out polish batch"):

- **P14.N1 (dashboard portion)** -- open-positions + hyp-rec TABLE thumbnails (the orphaned bit; journal-listing thumbnails already SHIPPED at SB4).
- **A-1** -- market_weather benchmark fetch-window too short for a 200-day MA.
- **A-2** -- theme2_annotated VCP 5-contraction label crowding (cosmetic).
- **A-4** -- `_bulz_*` -> general rename (cosmetic; the zones are a general open-long feature, not BULZ-specific).
- **A-6** -- process-grade-trend drill-down chart invisible in dark mode (SVG-default stroke/fill).
- **A-7 (freshest; operator-reported 2026-06-01)** -- the Schwab web health badge does NOT render in normal operation (hides instead of showing UNKNOWN). **Carries a DESIGN-vs-WIRING fix-investigation** (see §2.6) -- the highest-value item in the batch.
- **Group (a) minors** -- C-1/C-2/C-3/C-5/C-6/C-19 (six small SB1-era advisories + the xdist flake).

This is a **read-mostly UX/wiring/cosmetic + test-hardening batch on already-shipped surfaces.** NOT a new-feature, new-metric, or new-schema bundle. **The two load-bearing brainstorm deliverables are (1) the operator triage of which items are IN/OUT + the decomposition, and (2) the A-7 design-vs-wiring investigation.** For the trivially-mechanical items (A-2, A-4, group-(a) cosmetics) the spec can be LIGHT -- a paragraph each is enough.

**Brief:** `docs/phase14-close-out-polish-batch-brainstorming-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at `bf7e071`; Sec 9.1 LOCKs at `7a558e4`. **ALL Phase 14 feature sub-bundles SHIPPED end-to-end:** SB1 `e323339` · SB2 (v22) `27f8007` · SB3 (v23) `edd098d` · SB4 `31da4a5` · SB5 `6206fb6` · SB5.5 (Schwab) `16b3366`. **Main HEAD at this dispatch: `e26803f`** (the close-out orchestrator handoff). The close-out tail sequence: **close-out polish batch (THIS) -> B-7 operator failure-mode classification (final touch) -> Phase 14 close-out review (Sec 9.1 Q6) -> CLAUDE.md "Phase 14 CLOSED" at v23.**

**Cumulative discipline at dispatch:** 37+ CLAUDE.md gotchas BINDING (the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); **~700+ cumulative ZERO Co-Authored-By trailer drift**; **Schema v23 LOCKED -- the batch is expected to introduce NO schema change** (confirm at brainstorm; all items are cosmetic/wiring/render/test); **L2 LOCK stays green** (the only Schwab-touching item is A-7; it must add ZERO new `schwabdev.Client.*` call SITES vs baseline `bf7e071`).

**Expected duration:** ~3-5 hours brainstorming + a Codex chain run to convergence. Spec line target **~300-500 lines** (a batch of small items; depth concentrated on A-7's investigation + the decomposition + the gate strategy; the cosmetics are short).

**Skill posture:**
- Invoke `copowers:brainstorming` against this brief.
- **Codex chain count: SINGLE chain** at end (Sec 9.1 Q7 = orchestrator discretion). **Run to CONVERGENCE** (zero new criticals AND zero new majors; `NO_NEW_CRITICAL_MAJOR`); the ~5-round cap is **suspended for this project** (memory `feedback_codex_round_limit_suspended`); may exceed 5 rounds; do NOT stop while majors surface, do NOT pad after convergence.
- **Codex transport -- copowers v2.0.3 + WSL Codex CLI fallback (reads the repo FROM DISK):** the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension. **Do NOT attempt the MCP tools.** The `adversarial-critic` skill auto-routes to the WSL fallback that reads the worktree from disk and (v2.0.3) appends the **full prompt+response transcript** per round to `.copowers-findings.md` (`## Round N` / `### Prompt sent to Codex` / `### Codex response` incl. the `### Verdict` line). **Preferred: invoke `copowers:brainstorming` normally.** If driving directly: use `wsl.exe bash -ilc` (INTERACTIVE login) OR prefix `export PATH="$HOME/.local/node22/bin:$PATH"`, and **VERIFY `command -v codex` resolves to `/home/<wsluser>/.local/node22/bin/codex`** (NOT a `/mnt/c/.../npm/codex` shim, which dies `node: not found`) BEFORE the chain. `codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/<this-worktree> - < <promptfile>` (R1) / `... codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+; `resume` REJECTS `-s` AND `-C`). The worktree `.git` is a Windows path WSL can't resolve -> pre-generate the diff on Windows; tell Codex NOT to run git. See memory `feedback_wsl_native_codex_invocation` + `feedback_copowers_codex_mcp_windows_launcher` + `feedback_implementer_persist_codex_responses`.
- Output: design spec at `docs/superpowers/specs/2026-06-01-phase14-close-out-polish-batch-design.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/phase3e-todo.md`** -- the **`#5`** close-out punch-list entry, specifically: the **"Phase 14 close-out polish batch"** block (P14.N1-dashboard / A-1 / A-2 / A-4 / A-6 / A-7) + the **"Group (a) open minor advisories"** block (C-1/C-2/C-3/C-5/C-6/C-19, with sources in the SB1 executing-plans return report §2 + the cross-SB flake note). Also `#12` (SB5.5 SHIPPED -- the A-7 web-badge context: reachable web states ALIVE/STARTING/DEGRADED, UNKNOWN currently CLI-only-by-design) + `#8` (SB5 -- where A-6 was banked).

3. **`docs/phase14-commissioning-brief.md`** -- Sec 9.1 LOCKs (Q2 serial, Q6 operator-witnessed close-out, Q7 Codex-chain discretion). The deferred-list + forward-look entries that seeded P14.N1 / A-1 / A-2.

4. **CLAUDE.md** -- the **Web / HTMX / templates / forms** gotcha block (HTMX OOB-swap drift; `base.html.j2` shared-VM-field hazard; matplotlib mathtext `$`/`^`/`_`; session-anchor read/write mismatch) is load-bearing for P14.N1 + A-1 + A-6. The **Schwab / schwabdev** block is load-bearing for A-7 (the badge VM reads the SB5.5 liveness sidecar; the `setLogRecordFactory` redaction must stay intact; the L2 source-grep test stays green). The **#15 byte-parity-insufficient** gotcha (render-path regression tests must hit the production derivation path). The **#16/#32 ASCII** discipline (any new CLI/stdout output; A-7 if it touches `swing schwab status`). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **#2** (signature/anchor re-grep at writing-plans), **#10a** (triangulate template-vs-VM-vs-emitter for "doesn't render" gaps -- directly relevant to A-6 + A-7), **#15** (production-path regression test).

5. **Production code surfaces to read BEFORE drafting (architectural anchors -- ORCHESTRATOR-VERIFIED at this dispatch against `e26803f`; re-grep exact line numbers at writing-plans per #2):**
   - **P14.N1 -- the render-direct helper (REUSE):** `swing/web/trade_charts.py:88` `render_trade_window_thumbnail_svg(*, trade, fills, cfg) -> bytes | None` (no markers, no title -> no mathtext risk; None on no-coverage; render-direct, no `chart_renders` write). The **journal-listing precedent** SHIPPED at SB4 (the VM->row-template thumbnail pattern). **Install targets:** `swing/web/templates/partials/open_positions_row.html.j2` + `swing/web/templates/partials/hypothesis_recommendations_row.html.j2` + their VMs (`swing/web/view_models/open_positions_row.py`; the hyp-rec row VM in `swing/web/view_models/dashboard.py`/`trades.py` -- re-grep). Lazy-load like the journal thumbnails (a route serving the SVG bytes; the row references it). Confirm the open-trades / hyp-rec preconditions for the gate (thumbnails only render when rows exist).
   - **A-1 -- market_weather fetch-window:** the benchmark bars feeding `render_market_weather_svg` (`swing/web/charts.py:777`) are fetched via `ohlcv_cache.get_or_fetch(ticker=..., window_days=200)`. **`window_days=200` is CALENDAR days (~138 trading bars) -- INSUFFICIENT for a 200-trading-bar SMA200.** Two sites: pipeline `_bars_or_none` (`swing/pipeline/runner.py:2761`, called for the benchmark at `:2884`) + the web refresh handler (`swing/web/routes/dashboard.py:141` `render_market_weather_svg`, fed by the benchmark `get_or_fetch` just above it). Widen to **>=200 TRADING bars (~300 calendar days)** at BOTH sites; the regression asserts >=200 bars reach `render_market_weather_svg`. (Note `chart_jit.py:117` also uses `window_days=200` for the JIT chart path -- confirm whether that consumer is in/out of A-1 scope; the market-weather 200MA is the operator-reported symptom.)
   - **A-2 -- VCP contraction-label crowding:** `swing/web/charts.py:823-838` (`render_theme2_annotated_svg` path, fn at `:924`): the contraction markers loop emits `f"contraction {i + 1}: {depth:.1f}pct"` labels at `:838`; the right-edge labels crowd the price y-axis ticks. **Cosmetic reposition** -- move the labels off the y-axis tick column. Mind the matplotlib-mathtext gotcha (no `$`/`^`/`_` in label text -- `pct` not `%`, already compliant).
   - **A-4 -- `_bulz_*` rename:** `swing/web/charts.py:632` `_bulz_target_price(trade)` + `:725` `_draw_bulz_zones(...)` (called at `:708`, target at `:756`). **Pure rename** -> general (`_rr_target_price` / `_draw_risk_reward_zones` or the spec's chosen names) + comments + any WARN text. The zones are a GENERAL open-long-position risk/reward feature (operator-confirmed at the SB4 gate), NOT BULZ-special-cased. Grep ALL `_bulz` references in `swing/` + `tests/` and rename atomically.
   - **A-6 -- process-grade dark-mode chart:** `swing/web/templates/metrics/process_grade_trend.html.j2` -- the per-trade `<circle ... class="process-grade-marker">` (`:41-49`, NO explicit `fill=`/`stroke=` -> SVG-default black) + the per-metric `<polyline ... stroke-width="1.5" ... class="process-grade-rolling-line metric-{name}">` (`:56-60`, **`stroke-width` but NO `stroke=`** -> SVG-default black). NO CSS rule anywhere for `.process-grade-rolling-line` / `.process-grade-marker`. They vanish against the dark background. **Fix:** give them theme-aware stroke/fill via dark-mode tokens (mirror the SB5 overview sparkline `var(--accent)` = `#6ab0ff` in dark mode). Decide CSS-rule vs inline-`stroke=` (CSS preferred so light+dark both resolve via tokens).
   - **A-7 -- the Schwab web badge (THE investigation item; see §2.6 for the full design-vs-wiring framing):** `swing/web/view_models/schwab_checker_badge.py:30` `build_schwab_checker_badge(cfg)` returns **`None` when `read_liveness_sidecar(...)` is `None`** (`:42-43`) -- BEFORE ever calling the state machine. The state machine `evaluate_liveness_state` (`swing/integrations/schwab/checker_resilience.py:218`) **already returns `("UNKNOWN", "web server not running, or pre-N7 build")` for `data is None`** (`:228-229`), and `read_liveness_sidecar`'s own comment (`:188-190`) says non-/absent-dict -> "caller renders UNKNOWN" -- but the caller currently returns None instead. `_BADGE_MAP["UNKNOWN"] = ("Schwab?", "warn")` (`:26`) exists but is UNREACHABLE from the web path. The sidecar lives at `checker_liveness_sidecar_path(env)` = `~/swing-data/schwab-checker-liveness.<env>.json` (`:154`), written by the SB5.5 checker (`write_liveness_sidecar`, `:158`).
   - **Group (a) minors -- canonical sources (do NOT re-derive; cite #5 + the SB1 return report §2):** C-1 a provisional-flag default `=True` (candidate anchors: `swing/web/view_models/trades.py:2153` `position_capital_utilization_is_provisional: bool = True`; `swing/web/view_models/metrics/shared.py:142` `is_provisional: bool`) -- flip to `False` or make required, per the SB1 advisory; C-2 daily-management tooltip "covers today" -> "covers this row's session date"; C-3 backfill CLI artifact-write `OSError` -> wrap to `ClickException` (not a raw traceback); C-5 strengthen the `BEGIN IMMEDIATE` ordering regression test (assert lock-vs-SELECT/UPDATE order); C-6 narrow the backfill apply-path write-lock so it is NOT held during the restore-artifact filesystem write; C-19 harden the `test_ohlcv_reader_re_export_identity` xdist co-residency flake (`tests/research/test_pattern_cohort_evaluator_reader.py`; e.g. `@pytest.mark.xdist_group`; passes in isolation). **The brainstorm enumerates each + lets the operator triage which are in/out; it does NOT need a deep design for the cosmetics.**
   - **L2 LOCK test (must stay green; A-7 only):** `tests/integration/test_l2_lock_source_grep.py` -- baseline `L2_LOCK_BASELINE_SHA = "bf7e071"`. A-7 is a web view-model + (maybe) a checker-install-timing change; it must add ZERO new `schwabdev.Client.*` call sites.
   - **Schema anchor:** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`). The batch adds NO migration (confirm at brainstorm).

6. **`docs/orchestrator-context.md`** §"Pre-Codex review + brief-authoring disciplines" + §"Lessons captured".

7. **Memory:** `feedback_copowers_codex_mcp_windows_launcher` + `feedback_wsl_native_codex_invocation` (WSL Codex transport + `command -v codex` verification), `feedback_implementer_persist_codex_responses` (persist responses; read `.copowers-findings.md` for QA), `feedback_codex_round_limit_suspended` (run to convergence), `feedback_commit_message_trailer_parse_hazard` (final `-m` paragraph plain prose), `feedback_visual_gate_both_render_and_browser` (the operator-witnessed gate pattern), **`feedback_seeded_gate_masks_default_state`** (witness the UNSEEDED/default state -- THE lesson that A-7 itself proves; the SB5.5 S6 gate only witnessed the badge via orchestrator-SEEDED sidecars, masking the live no-badge behavior).

---

## §1 Pre-locked operator decisions (DO NOT re-litigate)

### §1.1 Sec 9.1 LOCKs
- **Q2** SERIAL -- the close-out polish batch is its own cycle, AFTER SB5.5 (SHIPPED), BEFORE B-7.
- **Q6** operator-witnessed verification at merge -- the render-bearing items (P14.N1 thumbnails, A-1 market-weather, A-2 VCP labels, A-6 dark-mode chart, A-7 badge) get an operator-witnessed browser gate; the test-only items (group-(a)) are mechanically gated. **Per `feedback_seeded_gate_masks_default_state`: the gate MUST witness the UNSEEDED/default state, not a seeded one** (esp. A-7 -- witness the genuine no-sidecar badge render, NOT a synthetic sidecar).
- **Q7** Codex chain count = orchestrator discretion -> **SINGLE chain** for this brainstorming.

### §1.2 Close-out polish-batch phase-specific LOCKs (this brief)
- **L1** Scope = the `#5` close-out polish-batch items ONLY (P14.N1-dashboard + A-1 + A-2 + A-4 + A-6 + A-7 + group-(a) C-1/C-2/C-3/C-5/C-6/C-19). Do NOT pull in B-7 (the NEXT cycle), the close-out review, Phase 15+, or any new feature. **A-5 (styled 404) is CLOSED** (operator "no intention to revisit") -- do NOT design it.
- **L2** **Expected NO schema change** (v23 held). Every item is cosmetic / wiring / render / test. If ANY item appears to need a persisted row/column (it should not), STOP and escalate -- do NOT design a v24.
- **L3 (L2-LOCK, Schwab)** A-7 must keep `tests/integration/test_l2_lock_source_grep.py` GREEN (ZERO new `schwabdev.Client.*` call sites vs `bf7e071`). The A-7 design fix (render UNKNOWN instead of hiding) is a pure web view-model change -- no Schwab API calls. The A-7 wiring investigation (does the checker run under valid tokens?) must NOT add a new client-construction path or call site.
- **L4** **REUSE, do not re-implement.** P14.N1 reuses `render_trade_window_thumbnail_svg` + the SB4 journal VM->row pattern; A-6 reuses the existing dark-mode token (`var(--accent)`); A-7 reuses the existing `evaluate_liveness_state` state machine (the UNKNOWN branch already exists) + `_BADGE_MAP`. NO new helper where an existing one fits.
- **L5** **Read-mostly.** ZERO swing-domain writes from any item (P14.N1/A-1/A-2/A-4/A-6 are render/cosmetic; A-7 is a VM; group-(a) is test + small advisory edits). The chart helpers are render-direct (no `chart_renders` write on the thumbnail path).
- **L6** **Production-path test discipline (#15).** P14.N1's thumbnail wiring test + A-1's >=200-bar regression + A-7's badge test MUST exercise the REAL production derivation path (the actual VM/route/cache construction), NOT a stub. A-7's test asserts the badge renders UNKNOWN when NO sidecar exists (the default state) -- this is the regression the SB5.5 seeded gate missed.
- **L7** **ASCII + redaction discipline.** Any new/changed CLI or stdout text stays ASCII (#16/#32; cp1252 crash). A-7 must not regress the `setLogRecordFactory` redaction or leak tokens; the badge title text stays ASCII (it already is).
- **L8** **Decomposition is an operator decision at brainstorm.** Recommend ONE executing-plans bundle with N slices (likely: A-7 + P14.N1 thumbnails as the two substantive slices; A-1 as its own slice; A-2/A-4/A-6 as a cosmetics slice; group-(a) as a test/advisory slice). BUT: **if the A-7 wiring investigation (§2.6.ii) concludes there is a REAL production wiring bug** (the checker should run under valid tokens but does not start/write the sidecar), that remediation may be larger than a badge tweak -> flag it for the operator as a possible split (A-7-wiring could become its own cycle).

---

## §2 Spec scope to design (per item)

### §2.1 P14.N1 -- dashboard-table thumbnails
Wire `render_trade_window_thumbnail_svg` onto `open_positions_row.html.j2` + `hypothesis_recommendations_row.html.j2` + their VMs, mirroring the SB4 journal-listing thumbnail pattern (lazy-loaded SVG via a route; the row references it). Define: the VM field(s) carrying the thumbnail URL/availability; the lazy-load route (reuse the journal thumbnail route shape if one exists, or a parallel one); the no-coverage / no-open-trades behavior (helper returns None -> no thumbnail, no crash); the gate precondition (needs real open trades + hyp-recs in the live DB to witness).

### §2.2 A-1 -- market_weather 200MA fetch-window
Widen the benchmark fetch window to **>=200 trading bars (~300 calendar days)** at the pipeline site (`runner.py:_bars_or_none`, benchmark call `:2884`) + the web refresh handler (`dashboard.py:141` feed). Specify the exact `window_days` value (calendar) that guarantees >=200 trading bars with margin. Add a regression asserting >=200 bars reach `render_market_weather_svg`. Confirm whether the JIT-chart `get_or_fetch(window_days=200)` (`chart_jit.py:117`) is in or out of scope (the symptom is the market-weather 200MA specifically).

### §2.3 A-2 -- VCP contraction-label crowding (cosmetic; LIGHT)
Reposition the `contraction {i+1}: {depth}pct` right-edge labels (`charts.py:838`) off the price y-axis tick column in `render_theme2_annotated_svg`. No mathtext metacharacters. A render-format-string test is sufficient; the binding check is the operator's eyes at the gate.

### §2.4 A-4 -- `_bulz_*` -> general rename (cosmetic; LIGHT)
Rename `_bulz_target_price` (`charts.py:632`) + `_draw_bulz_zones` (`:725`) + all references + comments + WARN text to general risk/reward naming. Grep `swing/` + `tests/` for every `_bulz`/`bulz` token and rename atomically (no behavior change; tests stay green).

### §2.5 A-6 -- process-grade-trend dark-mode chart (LIGHT)
Give `.process-grade-rolling-line` (polyline) + `.process-grade-marker` (circle) theme-aware stroke/fill so they are visible in BOTH light and dark mode (mirror `var(--accent)`'s dark value). Prefer a CSS rule over inline `stroke=` so the token resolves per theme. The binding check is the operator viewing `/metrics/process-grade-trend` in DARK mode at the gate (the bug is dark-mode-only).

### §2.6 A-7 -- Schwab web badge not rendering (THE investigation; resolve BOTH questions)
The badge is invisible in normal browser use because `build_schwab_checker_badge` returns `None` whenever no liveness sidecar exists, and the operator's production Schwab client is degraded (likely expired refresh tokens) so no checker writes the sidecar. NET: the badge vanishes exactly when Schwab is DOWN -- defeating its purpose. The brainstorm MUST resolve TWO questions and recommend the fix(es):

- **(i) DESIGN -- render a visible UNKNOWN state instead of hiding.** Have `build_schwab_checker_badge` render the `Schwab?` (warn) UNKNOWN badge when the sidecar is absent/unusable, instead of returning `None`. The state machine (`evaluate_liveness_state(None, ...)` -> `("UNKNOWN", ...)`) + `_BADGE_MAP["UNKNOWN"]` ALREADY support this; `read_liveness_sidecar`'s own comment anticipates "caller renders UNKNOWN." This is a ~3-line web-VM change. **Design question:** is "always surface Schwab health (UNKNOWN when no checker)" the right product call vs the SB5.5 "UNKNOWN is CLI-only by design" ruling? (Recommend: YES, flip to always-render -- the SB5.5 ruling predates the operator discovering the badge vanishes when most needed. HOLD for operator confirmation.) Also reconcile: does the `cfg is None -> return None` guard (`:38-39`, render-safe for cfg-less callers) stay (badge truly hidden only when there's no Config at all)?
- **(ii) WIRING -- should the checker be running under the operator's VALID production tokens?** Investigate: when the operator HAS valid production Schwab tokens + `env==production`, does the SB5.5 checker actually start and write the sidecar under `swing web`? If tokens are valid but the checker still does not start/write, that is a REAL A-3/P14.N7 wiring bug (not just the by-design hide) -> characterize it + recommend the fix + flag the possible cycle-split (L8). If the checker DOES run under valid tokens (and the operator only sees no-badge because their tokens are currently degraded), then (i) alone is the fix and (ii) is "working as intended; surfaced via UNKNOWN."
- **Caveat to carry into the spec:** the SB5.5 S6 gate witnessed the badge ONLY via orchestrator-SEEDED sidecars (cleaned up post-gate), which MASKED the live no-checker-no-badge behavior (`feedback_seeded_gate_masks_default_state`). A-7's own gate MUST witness the UNSEEDED state (no sidecar -> the badge renders UNKNOWN).

### §2.7 Group (a) minors (enumerate; operator triages in/out; LIGHT)
C-1 provisional-flag default; C-2 tooltip wording; C-3 backfill `OSError`->`ClickException`; C-5 `BEGIN IMMEDIATE` test strengthening; C-6 backfill write-lock narrowing; C-19 xdist flake hardening. One short paragraph each (trigger + proposed fix + source citation). The brainstorm asks the operator which of the six to include in THIS batch vs defer.

### §2.8 Operator-witnessed gate enumeration (default-state-witnessing)
- **S1** fast suite (`python -m pytest -m "not slow" -q`) green + ruff clean.
- **S2** schema unchanged (assert v23; NO migration).
- **S3 (L2)** `tests/integration/test_l2_lock_source_grep.py` green (A-7 adds no `schwabdev.Client.*` site).
- **S4 (P14.N1)** operator browser: open-positions + hyp-rec table thumbnails render (real open trades present; no-coverage rows degrade cleanly).
- **S5 (A-1)** the >=200-bar regression + operator confirms the market-weather widget's 200MA renders.
- **S6 (A-2/A-4/A-6)** operator browser: VCP labels uncrowded; the rename is behavior-neutral (tests green); the process-grade-trend chart visible in DARK mode.
- **S7 (A-7 -- the default-state witness)** operator browser with NO seeded sidecar: the topbar shows the `Schwab?` UNKNOWN (warn) badge instead of nothing. (Plus, if the wiring investigation found the checker SHOULD run under valid tokens, the operator confirms it does under a live production session -- optional/feasibility-gated.)
- **S8** trailers `[]`; ZERO Co-Authored-By.

---

## §3 Open questions (Codex SHOULD surface; operator triages at writing-plans dispatch)

1. **OQ-1 (A-7 design ruling):** flip the web badge to always-render UNKNOWN (recommend) vs keep "UNKNOWN is CLI-only" (the SB5.5 ruling)? **HOLD for operator** -- this is the central A-7 product decision.
2. **OQ-2 (A-7 wiring verdict):** is there a REAL checker-non-start-under-valid-tokens bug (ii), or is no-badge purely the by-design hide under degraded tokens? Codex + the investigation surface evidence; operator confirms the verdict + whether A-7-wiring splits into its own cycle.
3. **OQ-3 (batch decomposition):** ONE executing-plans bundle with N slices (recommend) vs splitting A-7. Slice grouping (A-7 / P14.N1 / A-1 / cosmetics A-2+A-4+A-6 / group-(a)).
4. **OQ-4 (group-(a) triage):** which of C-1/C-2/C-3/C-5/C-6/C-19 are IN this batch vs deferred.
5. **OQ-5 (P14.N1 scope):** open-positions AND hyp-rec tables both, or one? (Brief says both; confirm.) Lazy-load route reuse vs new route.
6. **OQ-6 (A-1 JIT-path scope):** is `chart_jit.py:117 window_days=200` in scope, or market-weather sites only?
7. **OQ-7 (A-6 mechanism):** CSS rule (recommend) vs inline `stroke=`.
8. **OQ-8 (Codex chain count at writing-plans/executing-plans):** single chain (recommend).

---

## §4 OUT OF SCOPE (do not design into V1)
- **B-7** operator failure-mode classification (the NEXT cycle, Phase 14 final touch) -- may add a nullable review column -> v24; NOT here.
- The **Phase 14 close-out review** (Sec 9.1 Q6) -- after the batch + B-7.
- **A-5** styled full-page 404 -- CLOSED (operator, no revisit).
- Any **new schema** (v24) -- L2; every item is schema-free.
- Any **new `schwabdev.Client.*` call site** / new Schwab feature / the schwabdev v3 upgrade (the PHASE 15 item, `#9`).
- The **v22/v23 substrate**; SB1-SB5.5 feature surfaces beyond the specific cosmetic/wiring touch; Phase 15+ (B-1..B-8).
- Deep redesign of any cosmetic item -- keep A-2/A-4/A-6/group-(a) minimal.

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **Brief-vs-production-anchor verification (#2)** -- cite real anchors (`trade_charts.py:88`; `charts.py:632`/`:725`/`:823-838`/`:777`/`:924`; `process_grade_trend.html.j2:41-60`; `schwab_checker_badge.py:30/42-43/26`; `checker_resilience.py:218/228-229/188-190/154`; `runner.py:2761/2884`; `dashboard.py:141`; `test_l2_lock_source_grep.py` baseline `bf7e071`; `db.py:51`). Re-grep exact lines.
2. **A-7 completeness (the core)** -- the spec resolves BOTH (i) design and (ii) wiring; does NOT silently pick the hide-vs-UNKNOWN design without surfacing the SB5.5-ruling tension; characterizes the wiring question with evidence (does the checker start under valid tokens?). Codex must NOT wave A-7 through as "just render UNKNOWN" without the wiring investigation.
3. **Seeded-gate-masks-default-state (the lesson A-7 proves)** -- the gate (S7) witnesses the UNSEEDED no-sidecar state; the A-7 test asserts UNKNOWN-when-absent (the regression the SB5.5 gate missed). Codex confirms the gate does not rely on a seeded sidecar.
4. **Schema (L2)** -- assert NO migration across ALL items; no v24.
5. **L2-LOCK (L3, A-7)** -- the source-grep test stays green; A-7 adds no `schwabdev.Client.*` site.
6. **Reuse, no re-implementation (L4)** -- P14.N1 reuses the helper + the SB4 pattern; A-7 reuses the state machine + `_BADGE_MAP`; A-6 reuses `var(--accent)`.
7. **Production-path tests (#15 / L6)** -- P14.N1 / A-1 / A-7 tests hit the real derivation path, not a stub.
8. **Render gotchas** -- P14.N1/A-2/A-6 don't reintroduce the matplotlib-mathtext `$`/`^`/`_` footgun; A-6's CSS resolves in BOTH themes; P14.N1's lazy-load partial doesn't trip the HTMX OOB/`<tr>`-at-fragment-root drift.
9. **A-4 rename completeness** -- every `_bulz`/`bulz` token in `swing/` + `tests/` renamed; behavior-neutral; tests green.
10. **ASCII (#16/#32)** for any CLI/stdout text; Co-Authored-By suppression + the trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape

**Design spec at `docs/superpowers/specs/2026-06-01-phase14-close-out-polish-batch-design.md`** (mirror the SB5.5 brainstorm spec format, but lighter on the cosmetics):
§1 Overview (the batch + the close-out position) · §2 Pre-locked decisions (Sec 9.1 + L1-L8) · §3 Per-item design (P14.N1 / A-1 / A-2 / A-4 / A-6 -- the cosmetics SHORT) · §4 **A-7 design-vs-wiring investigation (the deep section -- both questions, evidence, recommendation, the SB5.5-ruling tension, the possible cycle-split)** · §5 Group-(a) enumeration (one paragraph each; operator-triage table) · §6 Module touch list (per item) · §7 Schema impact (NO change) · §8 L2-LOCK analysis (A-7; zero new call sites) · §9 Sub-bundle decomposition recommendation (slices; the A-7-split contingency) · §10 Test + gate strategy (production-path; the UNSEEDED-state witness for A-7) · §11 V1 simplifications + V2 candidates · §12 Operator decision items (OQs, esp. OQ-1 + OQ-2) · §13 Cumulative discipline compliance · §14 Phase 14 close-out position note (this is the first close-out-tail item after SB5.5; next is B-7).

**Target ~300-500 lines.** Commit stem: `docs(phase14-close-out-spec): brainstorm <draft|R1|...> -- ...` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- **A-7 is the one item that can grow:** if the wiring investigation (§2.6.ii) finds a REAL checker-non-start bug under valid tokens, do NOT design a large remediation into this batch -- characterize it, recommend the fix, and FLAG the possible split for the operator (L8 / OQ-2). The DESIGN fix (i, render UNKNOWN) is in-scope regardless.
- If ANY item appears to need schema (a persisted row/column), STOP and escalate -- L2 forbids a v24 here.
- If A-7's design fix appears to need a new `schwabdev.Client.*` call site or client path, STOP -- L3 forbids it (the fix is a pure web-VM change).
- HOLD THE LINE: NO schema (L2); L2-LOCK green (L3); reuse not re-implement (L4); read-mostly (L5); the gate witnesses the UNSEEDED state (Q6 / `feedback_seeded_gate_masks_default_state`).
- Keep the cosmetics (A-2/A-4/A-6/group-(a)) MINIMAL -- the brainstorm depth belongs to A-7 + the decomposition.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep the final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead in the VS Code extension); use the WSL Codex fallback (verify `command -v codex` first; v2.0.3 writes the transcript to `.copowers-findings.md`).
- DO NOT widen scope to B-7 / the close-out review / Phase 15+; DO NOT touch the v22/v23 substrate.

---

## §8 Return report shape

Mirror the SB5.5 brainstorm return report: final HEAD + commit breakdown; Codex round chain + convergent shape (**EVIDENCE it ran genuinely via WSL -- cite the `.copowers-findings.md` rounds incl. the final `### Verdict` line**); spec line count + per-section; pre-locked decisions verbatim verification (Sec 9.1 + L1-L8); the per-item IN/OUT triage recommendation + the group-(a) table; **A-7 investigation outcome (the design recommendation + the wiring verdict + the cycle-split contingency)** -- flagged for operator; OQs resolved + deferred (esp. OQ-1 + OQ-2); Codex Major findings accepted (ZERO preferred); brief-vs-production anchor corrections (any line that drifted); V1 simplifications + V2 candidates; sub-bundle decomposition recommendation (slices); schema impact verdict (NO change); L2-LOCK analysis (A-7 zero new sites); the gate strategy summary (UNSEEDED-state witness); cumulative gotcha application; worktree teardown status; ZERO Co-Authored-By confirmation (`%(trailers)`); CLAUDE.md status-line refresh draft; writing-plans dispatch-readiness summary + the Phase 14 close-out position note.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-close-out-polish-batch-brainstorming`. Dir `.worktrees/phase14-close-out-polish-batch-brainstorming/`. Branch from main HEAD `e26803f`.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain at end (Sec 9.1 Q7), run to convergence via the WSL Codex fallback (copowers v2.0.3; MCP dead in the VS Code extension; verify `command -v codex` first; transcript persists to `.copowers-findings.md`).
- **Expected duration:** ~3-5 hours brainstorming + a Codex chain run to convergence.

---

*End of brief. Phase 14 close-out polish-batch brainstorming dispatch -- produce a design spec for the banked-items batch: P14.N1 (dashboard-table thumbnails, reusing render_trade_window_thumbnail_svg + the SB4 pattern) + A-1 (market_weather >=200-trading-bar fetch window) + A-2 (VCP label crowding, cosmetic) + A-4 (_bulz_* -> general rename, cosmetic) + A-6 (process-grade-trend dark-mode chart visibility) + A-7 (the Schwab web badge that vanishes in normal use -- resolve BOTH the DESIGN question [render UNKNOWN instead of hiding] AND the WIRING question [should the checker run under valid tokens?]) + group-(a) minors (operator-triaged). ~300-500 lines; single Codex chain to convergence. Expected NO schema change (v23 held); L2-LOCK green (A-7 adds zero schwabdev.Client.* sites); reuse not re-implement; read-mostly. The operator-witnessed gate MUST witness the UNSEEDED/default state (esp. A-7), per the lesson A-7 itself proves. The two load-bearing deliverables are the per-item IN/OUT triage + decomposition, and the A-7 design-vs-wiring investigation. OUTPUT: a design spec the writing-plans phase can derive a plan from once the operator rules on OQ-1 + OQ-2.*
