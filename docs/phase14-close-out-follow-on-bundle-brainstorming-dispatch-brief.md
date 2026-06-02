# Phase 14 Close-Out FOLLOW-ON Bundle -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 close-out follow-on-bundle brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for the **close-out FOLLOW-ON bundle** -- four issues surfaced at the operator-witnessed gate of the close-out polish batch (which SHIPPED end-to-end at `f2cd376`). The operator decided (2026-06-02) to ship the batch and correct these in a dedicated follow-on:

- **F-1 (highest value) -- P14.N7 web-checker liveness sidecar not written in normal operation.** A-7's UNSEEDED gate revealed that the `swing web` server writes **NO** checker liveness sidecar even under **healthy** production tokens, so the new A-7 badge correctly shows `Schwab?` UNKNOWN in real use. The likely cause: the seed `client.tokens.update_tokens()` ([app.py:274](swing/web/app.py)) is a **no-op when the access token is still valid**, so no STARTING sidecar is written; the daemon heartbeat (if any) hasn't fired yet. **The SB5.5 S6 gate masked this by seeding sidecars** (`feedback_seeded_gate_masks_default_state`) -- so P14.N7's real liveness behavior was never validated. Make the checker write a real sidecar in normal operation (so the badge reflects genuine health), and design a gate that witnesses the **UNSEEDED -> STARTING/ALIVE** transition with real tokens.
- **F-2 -- market-weather trend-template "undefined" / 200-MA.** The market-weather chart shows "trend: undefined" because the Minervini Trend Template bails to NA at `<200` closes ([trend_template.py:24](swing/evaluation/criteria/trend_template.py); TT1-TT4 use the 150/200-day SMAs). The close-out A-1 widened the fetch to ~300 calendar days (~207 trading bars) -- barely at the 200 floor, insufficient for the "200 rising" check + an unreadable 200-MA on a small chart. **Fix: fetch ~250+ trading bars for the 150/200-SMA classification, DECOUPLE the compute-window from the display-window** (the small chart stays readable; the 200-MA's value is the regime STATE, not a chart line). Operator ruling: do NOT chase a visible 200-MA line; restore the trend classification.
- **F-3 -- A-6 segmented rolling-line polylines.** The process-grade-trend rolling lines use ONE `<polyline>` per metric that skips `None` points ([process_grade_trend.py `_format_polyline_points`](swing/web/view_models/metrics/process_grade_trend.py)), so a single polyline **bridges gaps with straight diagonals** (visible now that A-6's dark-mode CSS made the lines render). Emit **one polyline per contiguous run** so gaps render as gaps. (A-6's visibility CSS already SHIPPED; only the pre-existing Phase-13 geometry is in scope here.)
- **F-4 -- hyp-rec thumbnail axes-spine borders (cosmetic).** `render_watchlist_thumbnail_svg` ([charts.py:514](swing/web/charts.py)) emits matplotlib default axes spines (black box around each sub-panel), visible on the new hyp-rec dashboard thumbnails. Hide the spines so they match the clean look. (Shared renderer -- re-check the watchlist surface too.)

This is a **read-mostly corrections bundle** (F-1 touches the SB5.5 P14.N7 checker; F-2 the market-weather fetch/trend; F-3/F-4 render geometry). NOT a new-feature bundle. **The load-bearing brainstorm deliverables: (1) the F-1 P14.N7 root-cause + fix design + the UNSEEDED gate, and (2) the F-2 compute-vs-display-window architecture.**

**Brief:** `docs/phase14-close-out-follow-on-bundle-brainstorming-dispatch-brief.md` (this file).

**Commissioning context:** ALL Phase 14 feature sub-bundles SHIPPED (SB1-SB5.5) + the close-out polish batch SHIPPED end-to-end at `f2cd376`. **Main HEAD at this dispatch: `67c7b3d`.** The close-out tail sequence: **this follow-on bundle -> B-7 (operator failure-mode classification, final touch) -> Phase 14 close-out review (Sec 9.1 Q6) -> "Phase 14 CLOSED" at v23.** Full history in `docs/phase3e-todo.md` `#15`.

**Cumulative discipline at dispatch:** 38+ CLAUDE.md gotchas BINDING (incl. the NEW HTMX `hx-target`-inheritance gotcha + the seeded-gate-masks-default-state lesson; the "Expansion #N" process disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); **~700+ cumulative ZERO Co-Authored-By**; **Schema v23 LOCKED -- expected NO change** (all 4 items are wiring/render/cosmetic); **L2 LOCK -- F-1 must add ZERO new `schwabdev.Client.*` call sites** (it wraps/fixes the existing P14.N7 checker; `tests/integration/test_l2_lock_source_grep.py` stays green; baseline `bf7e071`).

**Expected duration:** ~3-5 hours brainstorming + a Codex chain to convergence. Spec line target **~350-500 lines** (depth on F-1 + F-2; F-3/F-4 short).

**Skill posture:**
- Invoke `copowers:brainstorming` against this brief.
- **Codex chain count: SINGLE chain**, **run to CONVERGENCE** (`NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended -- `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP DEAD in the VS Code extension):** `wsl bash -ilc` (INTERACTIVE login) OR `export PATH="$HOME/.local/node22/bin:$PATH"`; **VERIFY `command -v codex` -> `/home/<wsluser>/.local/node22/bin/codex`** before the chain. `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < <prompt>` (R1) / `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+; `resume` REJECTS `-s`/`-C`). Pre-generate the diff on Windows; tell Codex NOT to run git. **PERSIST each round's prompt AND response to `.copowers-findings.md`** (`feedback_implementer_persist_codex_responses`). See `feedback_wsl_native_codex_invocation` + `feedback_copowers_codex_mcp_windows_launcher`.
- Output: design spec at `docs/superpowers/specs/2026-06-02-phase14-close-out-follow-on-bundle-design.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end.**
2. **`docs/phase3e-todo.md`** `#15` -- the close-out batch ship + the FOLLOW-ON bundle definition (the 4 items + the gate findings that produced them) + `#12`/the SB5.5 spec for the P14.N7 design context.
3. **The close-out batch artifacts** (for context): the spec `docs/superpowers/specs/2026-06-01-phase14-close-out-polish-batch-design.md` + the plan `docs/superpowers/plans/2026-06-01-phase14-close-out-polish-batch-plan.md` (esp. §4 the A-7 design, §3.5 A-6, the A-1 sites) + the return report `docs/phase14-close-out-polish-batch-executing-plans-return-report.md`.
4. **The SB5.5 P14.N7 artifacts** (F-1 is SB5.5 code): `docs/superpowers/specs/2026-05-31-phase14-sub-bundle-5-5-schwab-web-marketdata-checker-design.md` §5 (the checker-resilience design + the liveness state machine) + the plan. The CLAUDE.md **Schwab / schwabdev** gotcha block (esp. `update_tokens()` does NOT raise on auth failure + `force_access_token=True` = silent rotation; the `"Schwabdev"` `setLogRecordFactory` redaction; the 7-day refresh TTL).
5. **CLAUDE.md** -- the **Web / HTMX** block + the **yfinance/market-data** block ("shared cache hooks return the FULL archive; consumers slice" -- directly relevant to F-2's compute-vs-display decoupling) + the **Windows/test-discipline** block (#15 production-path; `USERPROFILE`+`HOME` monkeypatch). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (#2, #10a, #15).
6. **Production anchors (ORCHESTRATOR-VERIFIED at this dispatch; re-grep at writing-plans per #2):**
   - **F-1:** `_install_web_marketdata_caches` ([app.py:251](swing/web/app.py)); the seed `client.tokens.update_tokens()` (`:274`) -- the suspected no-op-on-valid-token; `install_resilient_checker` + `record_tick`/`write_liveness_sidecar` (`swing/integrations/schwab/checker_resilience.py`); `checker_liveness_sidecar_path(env)` (`:154`); `evaluate_liveness_state` 6-step state machine (`:218`); the A-7 badge VM (`swing/web/view_models/schwab_checker_badge.py` -- consumes the sidecar; do NOT regress the close-out A-7 fix). **The L2 source-grep test (`bf7e071`) MUST stay green.**
   - **F-2:** `current_stage` / the trend-template call at the market-weather refresh ([dashboard.py:131-140](swing/web/routes/dashboard.py)); `trend_template.py:24` (`if len(closes) < 200: na_`) + the 150/200 SMAs (`:33-34`); the market-weather fetch sites (`runner.py:_bars_or_none`, `dashboard.py:94`, `chart_jit.py:117`) + `MIN_CALENDAR_DAYS_FOR_MA200` (`ohlcv_cache.py`); `render_market_weather_svg` (`charts.py:777`, `ma_windows=(50,200)`).
   - **F-3:** `_format_polyline_points` ([process_grade_trend.py:262-301](swing/web/view_models/metrics/process_grade_trend.py)) -- the single-polyline-skips-None gap-bridge; the template `process_grade_trend.html.j2:54-62` (the `{% for series in vm.rolling_series %}` `<polyline>` loop).
   - **F-4:** `render_watchlist_thumbnail_svg` ([charts.py:514-552](swing/web/charts.py)) -- add `for spine in ax.spines.values(): spine.set_visible(False)` (or equivalent) to both sub-axes; re-check the watchlist surface (shared renderer).
   - **Schema anchor:** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`). Expected NO change.
7. **Memory:** `feedback_seeded_gate_masks_default_state` (F-1's gate witnesses the UNSEEDED real-token state -- this is the lesson F-1 itself proves, AGAIN), `feedback_copowers_codex_mcp_windows_launcher`, `feedback_wsl_native_codex_invocation`, `feedback_implementer_persist_codex_responses`, `feedback_codex_round_limit_suspended`, `feedback_commit_message_trailer_parse_hazard`, `feedback_no_false_green_claim`, `feedback_taskstop_does_not_kill_detached_server`.

---

## §1 Pre-locked operator decisions + LOCKs (DO NOT re-litigate)
- **Sec 9.1 Q2** SERIAL -- this follow-on is its own cycle, AFTER the close-out batch (SHIPPED), BEFORE B-7. **Q6** operator-witnessed gate at merge. **Q7** single Codex chain.
- **F-2 ruling (operator 2026-06-02):** do NOT pursue a visible 200-MA line (the small chart can't usefully show it); fetch enough history for the trend classification + decouple compute-vs-display. The 200-MA's value is the regime STATE.
- **L1** Scope = F-1 + F-2 + F-3 + F-4 ONLY. NO B-7, NO close-out review, NO Phase 15+ (the schwabdev v3 upgrade stays `#9`; F-1 may INFORM it but does NOT do it), NO new feature.
- **L2** Expected NO schema change (v23 held). If any item appears to need a persisted row/column -> STOP + escalate (F-1's liveness stays the existing ephemeral sidecar; NO v24).
- **L3 (L2-LOCK, F-1)** F-1 adds ZERO new `schwabdev.Client.*` call sites (it fixes/wraps the existing P14.N7 seed + checker; the L2 source-grep test stays green; baseline `bf7e071`). Do NOT regress the `"Schwabdev"` `setLogRecordFactory` redaction.
- **L4** REUSE, do not re-implement -- F-1 fixes the existing P14.N7 seed/sidecar path (reuse `record_tick`/`write_liveness_sidecar`/the state machine); F-2 reuses the existing fetch helpers + the trend-template; F-3 reuses the existing `_polyline_x`/`_polyline_y`; F-4 reuses the existing renderer.
- **L5** Read-mostly. ZERO swing-domain writes (the liveness sidecar is an ephemeral file, not the DB; the chart paths are render-direct).
- **L6** Production-path tests (#15) -- F-1's test exercises the REAL `create_app` -> `_install_web_marketdata_caches` seed path (a sidecar is written under valid-token conditions) WITHOUT seeding the sidecar by hand; F-2's test asserts the trend classifies (not NA) given >=250 bars via the real fetch path. **Do NOT validate F-1 with a hand-seeded sidecar** (the SB5.5 gate's exact mistake).
- **L7** ASCII + the A-7 close-out fix preserved (F-1 must keep the A-7 badge rendering UNKNOWN-when-no-sidecar; it just makes the sidecar actually appear in normal operation so the badge shows STARTING/ALIVE).

---

## §2 Spec scope to design (per item)

### §2.1 F-1 -- P14.N7 web-checker liveness in normal operation (the deep item)
Diagnose precisely WHY no sidecar is written under healthy tokens (the leading hypothesis: the seed `update_tokens()` is a no-op when the access token is still valid, so the wrap records no tick / writes no sidecar). Design the fix so that **install-time seeding ALWAYS writes an initial STARTING sidecar** (independent of whether the access token needed refreshing), and the daemon heartbeat keeps it fresh -- so in normal `swing web` operation the A-7 badge shows STARTING then ALIVE, not UNKNOWN. Confirm the daemon `checker` thread actually runs + writes heartbeats (the `STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL` invariant). Preserve: the L3 zero-new-call-sites LOCK; the redaction; the A-7 badge contract; P14.N7 stays a cleanly-removable Phase-15 guard. **Gate design (CRITICAL):** witness the UNSEEDED real-token transition -- start the web server with the operator's HEALTHY production tokens, assert a sidecar appears + the badge shows STARTING/ALIVE (NO hand-seeding). This is the SB5.5 gate's exact miss, now corrected.

### §2.2 F-2 -- market-weather trend-template / compute-vs-display
Design the decoupling: fetch ~250+ trading bars (enough for the 150/200 SMAs + the "200 rising" slope) for the trend-template COMPUTATION, but the market-weather chart DISPLAYS a readable recent window (the existing display window, or a slightly wider one). Determine the exact bar count needed (200 for the SMA + N for the rising-slope + margin -> ~250-260 trading bars ~= ~380 calendar days). Decide where the compute-window vs display-window split lives (the fetch helper returns full history; the renderer/classifier consume full, the chart slices for display -- the "return FULL archive; consumers slice" gotcha). Fix "trend: undefined" at the market-weather refresh (`dashboard.py:131-140`). Decide whether to keep/omit the 200-MA line on the small display (operator: the line is not the goal). Regression: the trend classifies (not NA) given >=250 bars via the REAL fetch path.

### §2.3 F-3 -- A-6 segmented rolling-line polylines (cosmetic-ish; SHORT)
Replace the single gap-bridging `<polyline>` with **one polyline per contiguous non-None run** (so `None` gaps render as gaps, not straight diagonals). Decide the VM shape (`svg_polyline_points` -> a tuple of segment point-strings) + the template loop. Reuse `_polyline_x`/`_polyline_y`. A render-string test asserts gaps split into multiple segments.

### §2.4 F-4 -- hyp-rec thumbnail spine borders (cosmetic; SHORT)
Hide the matplotlib axes spines in `render_watchlist_thumbnail_svg` so the thumbnails have no black box borders. Shared renderer -> re-check the watchlist surface at the gate.

### §2.5 Decomposition + gate
Recommend ONE executing-plans bundle, ~4 slices (F-1 first -- the deep one; F-2; F-3+F-4 cosmetics). Gate: S1 suite + ruff; S2 schema v23; S3 L2 source-grep green (F-1); **S4 (F-1, BINDING, UNSEEDED real-token) the web badge shows STARTING/ALIVE with a real sidecar written by the checker (NO hand-seed)**; S5 (F-2) the market-weather trend is defined (not "undefined") in a real browser; S6 (F-3/F-4 browser) the process-grade-trend lines render gaps-as-gaps + the hyp-rec thumbnails have no spine borders; S7 trailers `[]`.

---

## §3 Open questions (Codex surfaces; operator triages at writing-plans)
1. **OQ-1 (F-1 seed fix):** force an initial sidecar write at install (decouple the STARTING-sidecar write from the token-refresh no-op) vs force a token refresh at startup (heavier). Recommend the former (write a STARTING tick unconditionally at install).
2. **OQ-2 (F-1 daemon):** does schwabdev's daemon `checker` thread actually run + does the wrap write heartbeats on its interval? Confirm; if the daemon never ticks in practice, the fix may need an explicit heartbeat writer.
3. **OQ-3 (F-2 bar count + window split):** the exact compute-window bar count + where the display-slice happens.
4. **OQ-4 (F-2 200-MA line):** keep a short 200-MA tail on the display vs omit it (operator leans omit).
5. **OQ-5 (F-3 VM/template shape):** multiple `<polyline>` elements vs one polyline with `M`/`L`-style breaks (SVG `<polyline>` can't break -> multiple elements; or switch to `<path>`).
6. **OQ-6 (decomposition):** one bundle / 4 slices (recommend) vs split F-1 (it's the deepest).
7. **OQ-7 (Codex chain count at writing-plans/executing-plans):** single (recommend).

---

## §4 OUT OF SCOPE
- B-7 (the NEXT cycle); the Phase 14 close-out review; the schwabdev v3 upgrade (Phase 15 `#9` -- F-1 may inform it but does NOT do it); any new schema (v24); any new `schwabdev.Client.*` call site / new Schwab feature; a persisted liveness table (keep the ephemeral sidecar); a visible 200-MA line as a goal (F-2 ruling); the v22/v23 substrate.

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **F-1 root-cause correctness** -- the spec correctly identifies WHY no sidecar is written (the no-op seed) + the fix writes a real STARTING sidecar at install WITHOUT seeding; the daemon heartbeat is confirmed; the A-7 badge contract + redaction preserved; L3 zero-new-call-sites.
2. **F-1 gate = UNSEEDED real-token** (the SB5.5 miss) -- the test/gate does NOT hand-seed a sidecar; it exercises the real install seed path. Codex must reject any hand-seeded validation.
3. **F-2 compute-vs-display** -- the trend-template gets >=250 bars (not NA); the chart stays readable; the "return FULL archive; consumers slice" pattern; the regression hits the real fetch path (#15).
4. **Schema (L2)** -- NO migration; no v24. **L2-LOCK (L3)** -- F-1 zero new `schwabdev.Client.*` sites.
5. **Reuse (L4)** -- F-1 reuses the existing seed/sidecar/state-machine; F-3/F-4 reuse the existing helpers/renderer.
6. **F-3 SVG correctness** -- `<polyline>` can't have gaps -> multiple elements (or `<path>`); gaps render as gaps; no regression to the dark-mode CSS (the close-out A-6 visibility fix).
7. **F-4** -- spines hidden; the watchlist surface re-checked.
8. **ASCII; Co-Authored-By suppression + the trailer-parse hazard (final `-m` paragraph plain prose).**

---

## §6 Deliverable shape
Design spec at `docs/superpowers/specs/2026-06-02-phase14-close-out-follow-on-bundle-design.md` (mirror the close-out brainstorm spec format): §1 overview · §2 pre-locked decisions (Sec 9.1 + L1-L7) · §3 **F-1 P14.N7 root-cause + fix + the UNSEEDED gate (the deep section)** · §4 **F-2 compute-vs-display architecture** · §5 F-3 segmented polylines (short) · §6 F-4 spine borders (short) · §7 module touch list · §8 schema impact (NO change) · §9 L2-LOCK analysis (F-1) · §10 decomposition (slices) · §11 test + gate strategy (UNSEEDED real-token for F-1; production-path for F-2) · §12 V1 simplifications + V2 · §13 operator decision items (OQs) · §14 cumulative discipline · §15 close-out position note. **Target ~350-500 lines.** Commit stem `docs(phase14-follow-on-spec): brainstorm <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` `[]`).

---

## §7 If you get stuck
- **F-1 is the one that can grow:** if the no-sidecar cause is NOT the no-op seed (e.g. the daemon thread never runs, or `_construct_web_schwab_client` returns None in normal operation), characterize the real cause + recommend the fix; do NOT design a large rework -- escalate if it needs a new client path (L3) or schema (L2).
- If F-1 appears to need a NEW `schwabdev.Client.*` call site or a persisted health table, STOP + escalate (L3/L2).
- If F-2 appears to need a schema change or a new fetch path, STOP -- reuse the existing helpers + widen the window constant.
- HOLD THE LINE: NO schema (L2); L2-LOCK green (L3); reuse not re-implement (L4); read-mostly (L5); the F-1 gate witnesses the UNSEEDED real-token state (`feedback_seeded_gate_masks_default_state`); preserve the close-out A-7 badge fix.
- NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose. Use the WSL Codex fallback (verify `command -v codex`; persist prompt+response). DO NOT widen to B-7 / the close-out review / Phase 15.

---

## §8 Return report shape
Mirror the close-out brainstorm return report: final HEAD + commit breakdown; Codex chain + convergent shape (cite `.copowers-findings.md` incl. the final `### Verdict`); spec line count + per-section; pre-locked decisions verbatim; the F-1 root-cause finding + fix recommendation + the UNSEEDED gate design; the F-2 compute-vs-display design + the bar count; OQs resolved/deferred; Codex Majors accepted (ZERO preferred); brief-vs-production anchor corrections; V1 simplifications + V2; decomposition (slices); schema verdict (NO change); L2-LOCK analysis (F-1); cumulative gotcha application; worktree teardown status; ZERO Co-Authored-By; CLAUDE.md status-line refresh draft; writing-plans dispatch-readiness + the close-out position note.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-close-out-follow-on-bundle-brainstorming`. Dir `.worktrees/phase14-close-out-follow-on-bundle-brainstorming/`. Branch from main HEAD `67c7b3d` (or later if the orchestrator states a newer HEAD in the inline prompt).
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain to convergence via the WSL fallback (verify `command -v codex`; transcript -> `.copowers-findings.md`).

---

*End of brief. Phase 14 close-out FOLLOW-ON bundle brainstorming dispatch -- produce a design spec for the four gate-found issues: F-1 (the deep one -- P14.N7 web checker writes no liveness sidecar in normal operation despite healthy tokens; the seed update_tokens() no-op; the SB5.5 gate masked it by seeding; design the fix + an UNSEEDED real-token gate) + F-2 (market-weather "trend: undefined" -- the Trend Template bails at <200 closes; fetch ~250+ bars for the 150/200-SMA classification, decouple compute-window from display-window; the 200-MA's value is the regime STATE, not a line) + F-3 (segmented rolling-line polylines -- one polyline per contiguous run so gaps render as gaps) + F-4 (hide the hyp-rec thumbnail axes-spine borders). ~350-500 lines; single Codex chain to convergence. Expected NO schema (v23 held); L2-LOCK green (F-1 zero new schwabdev.Client.* sites); reuse not re-implement; read-mostly. The F-1 gate witnesses the UNSEEDED real-token STARTING/ALIVE transition (the SB5.5 gate's exact miss). OUTPUT: a design spec the writing-plans phase can derive a plan from.*
