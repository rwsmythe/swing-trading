# Phase 14 Close-Out Polish Batch -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 close-out polish-batch writing-plans implementer. No prior conversation context.

**Mission:** Turn the LOCKed close-out polish-batch brainstorm spec (+ the operator's OQ rulings below) into an executing-plans-ready implementation plan. ONE executing-plans bundle, **5 slices**, on already-shipped surfaces:
- **Slice A -- A-7** Schwab web health badge: render an `UNKNOWN` (`Schwab?`, warn) badge **gated on `_is_ladder_active(cfg)`** instead of hiding (pure web-VM change; reuse the existing `evaluate_liveness_state` UNKNOWN branch + `_BADGE_MAP`; + a reason-text refinement).
- **Slice B -- P14.N1** dashboard-table thumbnails on **BOTH tables** -- open-positions (via `render_trade_window_thumbnail_svg`, trade-keyed) AND hyp-rec (via `render_watchlist_thumbnail_svg`, ticker-keyed), both **lazy** (mirror the SB4 journal `hx-get`+semaphore pattern).
- **Slice C -- A-1** widen the market_weather benchmark fetch window to >=200 trading bars (~300 calendar days) at both live sites + the JIT path.
- **Slice D -- cosmetics** A-2 (VCP label reposition) + A-4 (`_bulz_*`->general rename) + A-6 (process-grade-trend dark-mode CSS).
- **Slice E -- group-(a)** all six minors (C-1/C-2/C-3/C-5/C-6/C-19; C-6 reviewed carefully).

**Read-mostly UX/wiring/cosmetic + test-hardening; NO swing schema change (v23 held); L2-LOCK stays green (A-7 adds ZERO new `schwabdev.Client.*` call sites by construction -- the `_is_ladder_active` gate is a pure config read).**

**Spec (AUTHORITATIVE for implementation, with ONE operator override):** `docs/superpowers/specs/2026-06-01-phase14-close-out-polish-batch-design.md` (546 lines; merged `83043ba`; genuine single WSL Codex chain CONVERGED R3). **OVERRIDE: the spec's §3.1/§9/§11/OQ-5 DEFER of hyp-rec thumbnails is REVERSED (operator 2026-06-01).** Hyp-rec thumbnails ARE in scope -- they reuse the EXISTING `render_watchlist_thumbnail_svg` (ticker-keyed), NOT a new renderer; the spec's deferral was a content-completeness gap (it considered only the trade-window renderer). See §1.1 OQ-5.

**Brief:** `docs/phase14-close-out-polish-batch-writing-plans-dispatch-brief.md` (this file).

**Context:** ALL Phase 14 feature sub-bundles SHIPPED (SB1 `e323339` · SB2 `27f8007` · SB3 `edd098d` · SB4 `31da4a5` · SB5 `6206fb6` · SB5.5 `16b3366`); close-out polish-batch brainstorm SHIPPED `83043ba`. Main HEAD at this dispatch: see §8 (the commit that adds this brief). This batch is the FIRST close-out-tail item; after it: B-7 (final touch) -> Sec 9.1 Q6 close-out review -> "Phase 14 CLOSED" at v23.

**Cumulative discipline:** the CLAUDE.md **Web / HTMX** + **Schwab / schwabdev** + **Windows / test-discipline** gotcha blocks are the implementation checklist; ~700+ cumulative ZERO Co-Authored-By; **Schema v23 LOCKED (NO migration); L2 LOCK** (A-7 keeps `tests/integration/test_l2_lock_source_grep.py` green vs `bf7e071` -- NO re-anchor; that is the Phase-15 v3 arc).

**Expected duration:** ~3-5 hours writing-plans + a Codex chain to convergence. Plan line target **~700-1000 lines** (5 slices; depth on Slice A [A-7] + Slice B [P14.N1 dual-renderer lazy delivery]; the cosmetics + group-(a) are short step-lists).

**Skill posture:**
- Invoke `copowers:writing-plans` against this brief + the spec.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP DEAD in the VS Code extension):** `wsl bash -ilc` (INTERACTIVE login) OR prefix `export PATH="$HOME/.local/node22/bin:$PATH"`; **VERIFY `command -v codex` -> `/home/<wsluser>/.local/node22/bin/codex`** (NOT the `/mnt/c/.../npm/codex` shim -> `node: not found`) before the chain. `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < <prompt>` (R1) / `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+; `resume` REJECTS `-s`/`-C`). Pre-generate the diff on Windows; tell Codex NOT to run git. **PERSIST each round's PROMPT AND RESPONSE to `.copowers-findings.md`** (v2.0.3 does this; the final `### Verdict` must be readable on disk for orchestrator QA). Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.
- Output: plan at `docs/superpowers/plans/2026-06-01-phase14-close-out-polish-batch-plan.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end** (esp. §1.1 the OQ-5 hyp-rec OVERRIDE).
2. **The SPEC** (`...2026-06-01-phase14-close-out-polish-batch-design.md`, 546 lines) -- AUTHORITATIVE EXCEPT the OQ-5 hyp-rec deferral (reversed; see §1.1). Especially §3 (per-item design), **§4 (the A-7 design-vs-wiring investigation -- the `_is_ladder_active` gate + the verified no-wiring-bug verdict + §4.3 the UNSEEDED-witness precondition)**, §5 (group-(a) table), §6 (module touch list), §9 (decomposition), §10 (the gate + the production-path tests).
3. **CLAUDE.md** -- the **Web / HTMX** gotcha block (the HTMX `<tr>`-at-fragment-root synthetic-table-wrap hazard; `hx-headers HX-Request`; the shared-`base.html.j2` VM-field-default gotcha; matplotlib mathtext `$`/`^`/`_`) + the **Windows/test-discipline** block (the `USERPROFILE`+`HOME` monkeypatch for any sidecar/HOME-isolated test; #15 production-path tests; cp1252 ASCII). + `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (esp. #2 anchor re-grep at STEP 0, #10a triangulate template-vs-VM-vs-emitter, #15 production-path).
4. **The brainstorm dispatch brief** (`docs/phase14-close-out-polish-batch-brainstorming-dispatch-brief.md`) §0.5 (the orchestrator-verified anchors) -- carry forward, re-grep at STEP 0.
5. **Memory:** `feedback_seeded_gate_masks_default_state` (the A-7 gate witnesses the UNSEEDED state), the WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + visual-gate entries.

---

## §1 LOCKed dispositions (operator 2026-06-01; BINDING -- DO NOT re-litigate)

### §1.1 The OQ dispositions
| OQ | LOCKed |
|---|---|
| **OQ-1 (A-7 design)** | Render the `UNKNOWN` (`Schwab?`, warn) badge **gated on `_is_ladder_active(cfg)`** (production AND ladder enabled -- the EXACT "checker is expected" predicate; a pure config read, L3-safe) when no usable sidecar exists; ELSE return `None` (hide -- no sandbox/non-Schwab noise). Replaces the SB5.5 "UNKNOWN is CLI-only" ruling. Reuse the existing `evaluate_liveness_state` (its `data is None`->UNKNOWN branch) + `_BADGE_MAP`. Keep the `cfg is None -> return None` guard. **Plus the reason-text refinement** (the no-sidecar-but-expected case: the hardcoded "web server not running, or pre-N7 build" is misleading -> supply a more accurate `title`, e.g. "Schwab client unavailable -- no checker running; check credentials/tokens"; state stays UNKNOWN/warn; ASCII only). |
| **OQ-2 (A-7 wiring verdict)** | **NO checker-non-start bug under valid tokens** (orchestrator-verified the static trace on disk: `app.py:407` -> `_install_web_marketdata_caches` -> `_construct_web_schwab_client` [gated `_is_ladder_active` FIRST] -> on a valid client, installs the checker + **synchronously seeds** a sidecar via `update_tokens()` before serving). "No badge" = the by-design hide manifesting under degraded tokens / failed client construction. **A-7 stays ONE slice; NO cycle-split.** (Re-open contingency ONLY if the live S7 session ever shows the checker failing to start under genuinely valid tokens -- not expected.) |
| **OQ-3 (decomposition)** | ONE executing-plans bundle, **5 slices** (A / B / C / D / E per the Mission). Serial; Slice A (A-7) first. |
| **OQ-4 (group-(a) subset)** | **ALL SIX** (C-1/C-2/C-3/C-5/C-6/C-19). **C-6 (narrow the backfill apply-path write-lock) reviewed CAREFULLY** -- verify it does NOT reopen a TOCTOU the original lock closed; if risk surfaces at executing-plans, DEFER C-6 to its own follow-up (do NOT force it). |
| **OQ-5 (P14.N1 scope -- OVERRIDES the spec's deferral)** | **BOTH dashboard tables.** Open-positions rows -> `render_trade_window_thumbnail_svg` (trade-keyed; `trade_charts.py:88`). **Hyp-rec rows -> `render_watchlist_thumbnail_svg` (ticker-keyed; `charts.py:514`)** -- the EXISTING watchlist thumbnail renderer (hyp-rec rows are ticker-keyed `rec.ticker`; the hyp-rec-expand caller already shares a ticker-keyed detail chart with the watchlist per `charts.py:556-558`). **NO new renderer -- L4 preserved.** **Delivery: LAZY for BOTH tables** (mirror the SB4 journal `hx-get` on `revealed` + the `BoundedSemaphore(2)` render cap; avoid blocking the dashboard's eager build). **Visual difference is INTENTIONAL** -- open-positions get a trade-window thumbnail; hyp-rec get a ticker trailing-window thumbnail (a held position warrants its actual window; a candidate gets a generic ticker view). Do NOT force both onto one renderer for uniformity. |
| **OQ-6 (A-1 JIT-path scope)** | Widen the JIT-path constant (`chart_jit.py:117`) TOO, for uniformity + correctness of any MA200-bearing surface (low risk; more bars only) -- in ADDITION to the two live market_weather sites. |
| **OQ-7 (A-6 mechanism)** | **CSS rule** (`swing/web/static/app.css`): `.process-grade-rolling-line { stroke: var(--accent); }` + `.process-grade-marker { fill: var(--accent); }` (resolves per theme via the existing `--accent` token; mirrors the SB5 sparkline precedent). NOT inline `stroke=`. |
| **OQ-8 (Codex chain count)** | SINGLE Codex chain (writing-plans + executing-plans each one chain to convergence). |

### §1.2 Inherited LOCKs (from the spec §2; BINDING)
- **L1** scope = the 5 slices ONLY. NO B-7, NO close-out review, NO Phase 15+. **A-5 (styled 404) is CLOSED** -- do NOT design it.
- **L2** NO swing schema change (v23 held; `EXPECTED_SCHEMA_VERSION = 23` at `swing/data/db.py:51`). If ANY item appears to need a persisted row/column -> STOP + escalate; NO v24.
- **L3 (L2-LOCK, Schwab)** A-7 adds ZERO new `schwabdev.Client.*` call sites (the `_is_ladder_active` gate is a pure config read; reuse `evaluate_liveness_state` + `_BADGE_MAP`); `tests/integration/test_l2_lock_source_grep.py` (baseline `bf7e071`) stays green. **NO L2 re-anchor.**
- **L4** REUSE, do not re-implement. P14.N1 reuses BOTH existing renderers (`render_trade_window_thumbnail_svg` + `render_watchlist_thumbnail_svg`) + the SB4 journal lazy route/semaphore pattern; A-6 reuses `var(--accent)`; A-7 reuses `evaluate_liveness_state` + `_BADGE_MAP`. NO new renderer; NO new helper where an existing one fits.
- **L5** Read-mostly. ZERO swing-domain writes from any item. The thumbnail renderers are render-direct (no `chart_renders` write on the thumbnail path -- the trade-window helper is render-direct; confirm the watchlist-thumbnail path's cache write semantics and keep the dashboard reuse read-only).
- **L6** Production-path test discipline (#15). P14.N1's thumbnail tests, A-1's >=200-bar regression, and A-7's badge test MUST exercise the REAL production derivation path (the actual route/VM/cache construction + the topbar `base.html.j2` render), NOT a stub.
- **L7** ASCII + redaction. Any new/changed CLI/stdout text stays ASCII (#16/#32). A-7 must not regress the `setLogRecordFactory` redaction; the badge title stays ASCII.

---

## §2 Production anchors (BINDING; re-grep at writing-plans STEP 0 per #2)
Orchestrator-verified at the brainstorm QA -- the spec embeds them; re-confirm:
- **A-7:** `build_schwab_checker_badge(cfg)` at `swing/web/view_models/schwab_checker_badge.py:30` (the `if data is None: return None` early-out at `:42-43` is what to replace with the `_is_ladder_active`-gated UNKNOWN path); `_BADGE_MAP["UNKNOWN"] = ("Schwab?","warn")` (`:26`); `evaluate_liveness_state(None, now_ts=...)` -> `("UNKNOWN", ...)` (`swing/integrations/schwab/checker_resilience.py:218/228-229`); `read_liveness_sidecar` (`:180`); `_is_ladder_active(cfg)` (`swing/integrations/schwab/marketdata_ladder.py:221`, a pure `env=='production' AND marketdata_ladder_enabled` read). The badge renders in the topbar via `base.html.j2`'s `{% if vm.schwab_checker_badge %}` guard -- **A-7 adds NO new `vm.*` field** (`schwab_checker_badge` already exists on all base-layout VMs from SB5.5; the change only alters None-vs-VM).
- **P14.N1 open-positions:** `render_trade_window_thumbnail_svg(*, trade, fills, cfg)` (`swing/web/trade_charts.py:88`); the SB4 journal lazy route `GET /journal/trades/{trade_id}/thumbnail` (`swing/web/routes/journal.py:80`) + the `BoundedSemaphore(2)` cap (`:34`) + the `journal_thumbnail.html.j2` partial (fragment root `<svg>`/`<span>`, never bare `<tr>`); the lazy cell pattern `journal_row.html.j2:14-18` (`hx-get`, `hx-trigger="revealed"`, `hx-swap="innerHTML"`, `hx-headers='{"HX-Request":"true"}'`). Targets: `swing/web/templates/partials/open_positions_row.html.j2` + the 10-col table shape (`open_positions.html.j2:8` 10 `<th>`; `open_positions_expanded.html.j2:27` `colspan="10"` + the "MUST match" comment at `:5`) -> add `<th>Chart</th>` + bump `colspan` 10->11 + a column-count regression.
- **P14.N1 hyp-rec:** `render_watchlist_thumbnail_svg(*, ticker, bars, ma_lines)` (`swing/web/charts.py:514`, ticker-keyed); the `watchlist_row` JIT surface (`swing/web/chart_jit.py:60` registry) + `get_cached_chart_svg`/`refresh_chart_render`. Targets: `swing/web/templates/partials/hypothesis_recommendations_row.html.j2` + its VM (re-grep: `swing/web/view_models/dashboard.py` / `trades.py`; the row carries `rec.ticker`). **The plan resolves the exact LAZY ticker-keyed delivery route** -- reuse an existing JIT chart endpoint serving the `watchlist_row` surface keyed by ticker, OR a thin parallel `/...thumbnail` route calling `render_watchlist_thumbnail_svg` with the SAME semaphore constant. (The watchlist itself delivers EAGERLY via a `chart_svg_bytes_for_row` VM-map at `watchlist_row.html.j2:14-22`; for the DASHBOARD we want LAZY -- reuse the RENDERER, not the watchlist's eager delivery.) Mind the hyp-rec table's own column-shape (mirror the open-positions `<th>Chart</th>` + colspan treatment).
- **A-1:** `OhlcvCache.get_or_fetch(*, ticker, window_days=180)` default (`swing/web/ohlcv_cache.py:131`; `window_days` = CALENDAR lookback per the docstring); pipeline `_bars_or_none` (`swing/pipeline/runner.py:2761`, benchmark at `:2884`); web refresh `dashboard.py:94` (passes NO `window_days` -> inherits 180 -> must pass the constant explicitly); JIT `chart_jit.py:117`; `render_market_weather_svg` (`charts.py:777`, `ma_windows=(50,200)`). Use a NAMED shared constant (~300 calendar days for >=200 trading bars; e.g. `_MIN_CALENDAR_DAYS_FOR_MA200 = 300`). Regression (L6): >=200 bars reach `render_market_weather_svg` via the REAL fetch path at both live sites.
- **A-2:** `_annotate_vcp` (`swing/web/charts.py:836-841`, in `render_theme2_annotated_svg` `:924`): the `f"contraction {i+1}: {depth:.1f}pct"` labels at `transAxes x=0.98, ha="right", y=0.92-i*0.05` -> reposition off the right price-tick column (LEFT inset `x=0.02,ha="left"` OR inward `x~0.74`). No mathtext metachars.
- **A-4:** `_bulz_target_price` (`charts.py:632`, called `:756`) + `_draw_bulz_zones` (`:725`, called `:708`) -> general names (e.g. `_rr_target_price` / `_draw_risk_reward_zones`); grep ALL `_bulz`/`bulz` tokens in `swing/` + `tests/`; rename atomically + comments + WARN text; behavior-neutral.
- **A-6:** `swing/web/templates/metrics/process_grade_trend.html.j2:39-60` (the `<circle class="process-grade-marker">` no `fill=` -> black; the `<polyline class="process-grade-rolling-line ...">` `stroke-width` but NO `stroke=` -> SVG-default `none` -> invisible in BOTH themes). Add the CSS rules to `swing/web/static/app.css` using `--accent` (light `#0066cc` / dark `#6ab0ff`; re-grep the exact lines). The SB5 sparkline precedent: `app.css` `.metrics-card__sparkline { color: var(--accent); }` + `index.html.j2` `stroke="currentColor"`.
- **Group-(a):** per the spec §5 table -- C-1 (`view_models/trades.py:2153` / `view_models/metrics/shared.py:142` provisional default), C-2 (daily-management tooltip text), C-3 (backfill CLI `OSError`->`ClickException`), C-5 (`BEGIN IMMEDIATE` ordering test), C-6 (backfill apply-path write-lock narrowing -- CAREFUL), C-19 (`tests/research/test_pattern_cohort_evaluator_reader.py::test_ohlcv_reader_re_export_identity` xdist flake -> `@pytest.mark.xdist_group`).

---

## §3 Codex SINGLE-chain placement (OQ-8; run to convergence)
Run ONE chain after the plan is written + internally chunk-reviewed. **Watch items:** NO schema (all 5 slices); L2 stays green (A-7 zero new `schwabdev.Client.*` sites; `_is_ladder_active` is a pure config read); the A-7 `_is_ladder_active`-gate semantics + the reason-text + the UNSEEDED-witness test (the regression the SB5.5 seeded gate missed -- production+ladder+isolated HOME+no constructible client); P14.N1 dual-renderer LAZY delivery (the HTMX `<tr>`-at-fragment-root hazard; `hx-headers HX-Request`; the column-count alignment regression for BOTH tables; read-only reuse of the watchlist renderer); A-1 calendar-vs-trading-bar arithmetic + the >=200-bar production-path regression at both sites; A-2 mathtext-free labels; A-4 rename completeness (every `_bulz`/`bulz` token, behavior-neutral); A-6 CSS resolves in BOTH themes; group-(a) C-6 TOCTOU caution + the `USERPROFILE`+`HOME` monkeypatch on any HOME-isolated test; ASCII; production-path tests (L6). **Persist prompt+response per round.** If a finding needs a schema change or a new `schwabdev.Client.*` site, STOP + escalate.

---

## §4 The eventual operator gate (executing-plans; for plan §I) -- UNSEEDED/default-state witness
Mechanical + an operator browser leg:
- **S1** fast suite (`python -m pytest -m "not slow" -q`) + ruff green. **S2** schema unchanged (v23; no `0024`; no new domain/`chart_renders` writes). **S3** L2 source-grep green (A-7 zero new `schwabdev.Client.` sites).
- **S4 (P14.N1, browser)** open-positions AND hyp-rec table thumbnails render with real rows present (open trades + hyp-recs in the live DB); no-coverage rows degrade cleanly; both tables' column counts align (compact == header == expanded).
- **S5 (A-1)** the >=200-bar regression + operator confirms the market-weather widget's 200-MA renders (full line).
- **S6 (A-2/A-4/A-6, browser)** VCP labels uncrowded; the rename is behavior-neutral (tests green); the process-grade-trend chart visible in DARK mode.
- **S7 (A-7, browser -- THE default-state witness)** under the reproducible UNSEEDED precondition (spec §4.3): production + ladder enabled, NO pre-existing sidecar, AND no constructible Schwab client at startup (degraded/missing creds -> no app-created sidecar). The topbar shows the `Schwab?` UNKNOWN (warn) badge instead of nothing. (The operator's currently-degraded production tokens reproduce this NATURALLY -- running the branch server in production mode yields no constructible client -> UNKNOWN. Optional SEPARATE witness if valid tokens are available: the badge shows ALIVE/STARTING, validating the §4.2 wiring verdict.)
- **S8** trailers `[]`; ZERO Co-Authored-By.

---

## §5 Deliverable shape
Plan at `docs/superpowers/plans/2026-06-01-phase14-close-out-polish-batch-plan.md` (mirror the SB5/SB5.5 plan format): §A goals/non-goals · §B file map (per slice) · §C surface integration · §D out-of-scope · §E LOCK reverification (the OQ table + L1-L7) · §F discipline hooks · §G the 5 slices as step-checkbox TDD tasks (Slice A A-7 · Slice B P14.N1 dual-table lazy · Slice C A-1 · Slice D cosmetics A-2/A-4/A-6 · Slice E group-(a)) · §H test surface (production-path) · §I the operator gate (S1-S8 incl. the A-7 UNSEEDED witness + the P14.N1/A-6/A-2 browser legs) · §J Codex placement · §K schema (NO change) · §L fixtures (esp. the A-7 UNSEEDED fixture: production+ladder+isolated HOME+no constructible client; `USERPROFILE`+`HOME` monkeypatch) · §M forward-binding lessons · §N self-review · §O Phase 14 close-out position (next = B-7). **Final `-m` paragraph plain prose; verify `%(trailers)` is `[]`.**

---

## §6 If you get stuck
- If a spec/brief anchor no longer matches production (re-grep at STEP 0), ESCALATE -- do NOT silently patch.
- If ANY item appears to need a swing schema change (a persisted row/column), STOP + escalate -- NO v24 (L2).
- If A-7's design appears to need a NEW `schwabdev.Client.*` call site or a new client-construction path, STOP -- L3 forbids it (the fix is a pure web-VM change + a pure-config-read gate).
- If P14.N1 hyp-rec appears to need a NEW renderer, STOP -- reuse `render_watchlist_thumbnail_svg` (L4; the operator-confirmed reuse). If open-positions reuse of the trade-window renderer needs a domain write, STOP (L5 read-mostly).
- If group-(a) C-6 (write-lock narrowing) appears to reopen a TOCTOU, DEFER it to its own follow-up (do NOT force it into the batch) and note it in the plan.
- HOLD THE LINE: NO schema (L2); L2-LOCK green (L3); reuse not re-implement (L4); read-mostly (L5); the gate witnesses the UNSEEDED A-7 state (S7 / `feedback_seeded_gate_masks_default_state`); both dashboard tables LAZY.
- NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose. Use the WSL Codex fallback (verify `command -v codex`; persist prompt+response). DO NOT widen to B-7 / the close-out review / Phase 15+; DO NOT touch the v22/v23 substrate.

---

## §7 Return report shape
Mirror the prior writing-plans return reports: final HEAD + commit breakdown (per-round Codex attribution); the single Codex chain + convergent shape (**cite `.copowers-findings.md` rounds incl. the final `### Verdict`**); plan line count + sections; the OQ dispositions honored verbatim (esp. OQ-1 `_is_ladder_active` gate, OQ-5 hyp-rec INCLUDED via `render_watchlist_thumbnail_svg`); L1-L7 reverification; Codex Majors accepted (ZERO preferred); production-anchor re-grep results (any line that drifted); schema verdict (NO change); the L2-LOCK analysis (A-7 zero new sites); the P14.N1 dual-renderer lazy-delivery design (the exact hyp-rec route chosen) + the dual-table column-count regression plan; the A-7 UNSEEDED-fixture design; the gate enumeration (S1-S8 incl. the browser legs); cumulative gotcha application; worktree teardown status; ZERO Co-Authored-By confirmation (`%(trailers)`); CLAUDE.md status-line refresh draft; executing-plans dispatch-readiness summary + the Phase 14 close-out position note.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-close-out-polish-batch-writing-plans`. Dir `.worktrees/phase14-close-out-polish-batch-writing-plans/`. **Branch from main HEAD = the commit that adds this brief** (the orchestrator states the exact SHA in the inline prompt).
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain to convergence via the WSL fallback (copowers v2.0.3; verify `command -v codex`; transcript -> `.copowers-findings.md`).
- **Schema:** NO change (v23 held); the batch is read-mostly UX/wiring/cosmetic + test.

---

*End of brief. Phase 14 close-out polish-batch writing-plans dispatch -- derive an executing-plans-ready plan from the LOCKed 546-line spec (with the OQ-5 hyp-rec OVERRIDE): 5 slices -- A-7 (render an UNKNOWN Schwab badge gated on `_is_ladder_active` instead of hiding; reuse `evaluate_liveness_state` + `_BADGE_MAP`; reason-text refinement; verified no checker-non-start wiring bug) · P14.N1 (BOTH dashboard tables -- open-positions via `render_trade_window_thumbnail_svg`, hyp-rec via the EXISTING `render_watchlist_thumbnail_svg`; both LAZY mirroring the journal hx-get+semaphore; column-count regressions) · A-1 (>=200-trading-bar market_weather fetch window at both live sites + the JIT path; named ~300-calendar-day constant) · cosmetics A-2/A-4/A-6 · group-(a) all six (C-6 carefully). NO schema (v23 held); L2-LOCK green (A-7 zero new schwabdev.Client.* sites); reuse not re-implement; read-mostly. Single Codex chain to convergence (persist prompt+response). The gate witnesses the UNSEEDED A-7 default state (S7) + browser legs for P14.N1/A-2/A-6. OUTPUT: an executing-plans-ready plan + return report.*
