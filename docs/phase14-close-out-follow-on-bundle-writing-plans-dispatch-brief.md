# Phase 14 Close-Out FOLLOW-ON Bundle -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 close-out follow-on-bundle writing-plans implementer. No prior conversation context.

**Mission:** Turn the LOCKed follow-on brainstorm spec into an executing-plans-ready implementation plan. ONE executing-plans bundle, **4 serial slices** (F-1 first) -- corrections to the close-out polish batch (which SHIPPED at `f2cd376`):
- **F-1 -- P14.N7 web-checker liveness in normal operation.** The A-7 badge shows `Schwab?` UNKNOWN under HEALTHY tokens because no liveness sidecar exists. The brief's no-op-seed hypothesis was **REFUTED**: `record_tick("seed")` fires BEFORE `original()` ([checker_resilience.py:130/135](swing/integrations/schwab/checker_resilience.py)), so a STARTING sidecar is written unconditionally WHEN a client constructs. The absent sidecar is therefore **Class A** (`_construct_web_schwab_client` returned None despite healthy tokens -- likely a creds-plumbing gap) OR **Class B** (silent sidecar-write failure). **The plan runs a one-shot startup diagnostic FIRST to pin Class A vs B, then locks the fix.** Zero new `schwabdev.Client.*` call sites.
- **F-2 -- market-weather trend "undefined".** Deeper than a bar-count issue: `current_stage` ([foundation.py:745](swing/patterns/foundation.py)) reads PERSISTED `candidate_criteria` for the benchmark, which is **not in the evaluated set** -> undefined regardless of bars. Fix: compute the regime LIVE from a >=250-bar fetch via a **two-tier shared helper** (`structural_checks` per-check + `structural_stage` wrapper; `evaluate()` refactors to REUSE `structural_checks` with **byte-identical** TT1-TT5 `Result` rows), decoupling the compute-window from the display-window.
- **F-3 -- segmented rolling-line polylines.** Replace the single gap-bridging `<polyline>` ([process_grade_trend.py `_format_polyline_points`](swing/web/view_models/metrics/process_grade_trend.py)) with one `<polyline>` per contiguous non-None run (drop 1-point segments).
- **F-4 -- hyp-rec thumbnail spine borders.** Hide the matplotlib axes spines in `render_watchlist_thumbnail_svg` ([charts.py:514](swing/web/charts.py)).

**Read-mostly; NO swing schema change (v23 held); L2-LOCK stays green (F-1 ZERO new `schwabdev.Client.*` call sites -- construction stays in `auth.py:construct_authenticated_client`). Preserve the close-out A-7 badge fix.**

**Spec (AUTHORITATIVE):** `docs/superpowers/specs/2026-06-02-phase14-close-out-follow-on-bundle-design.md` (547 lines; merged `6836aa5`; genuine single WSL Codex chain CONVERGED R3 -- the brief's F-1 hypothesis refuted + F-2 reframed, both orchestrator-verified on disk).

**Brief:** `docs/phase14-close-out-follow-on-bundle-writing-plans-dispatch-brief.md` (this file).

**Context:** ALL Phase 14 feature sub-bundles + the close-out polish batch SHIPPED; the follow-on brainstorm SHIPPED `6836aa5`. **Main HEAD at this dispatch: `3892457`.** After this bundle: B-7 (final touch) -> Sec 9.1 Q6 close-out review -> "Phase 14 CLOSED" at v23.

**Cumulative discipline:** the CLAUDE.md **Schwab / schwabdev** + **Web / HTMX** + **yfinance** ("return the FULL archive; consumers slice" -- F-2's compute-vs-display) + **Windows/test-discipline** gotcha blocks are the checklist; ~700+ ZERO Co-Authored-By; **Schema v23 LOCKED (NO migration)**; **L2 LOCK** (`tests/integration/test_l2_lock_source_grep.py` stays green; baseline `bf7e071`; F-1 adds NO new `schwabdev.Client.*` sites).

**Expected duration:** ~3-5 hours writing-plans + a Codex chain to convergence. Plan line target **~700-1000 lines** (depth on F-1's two-class diagnostic-then-fix + F-2's two-tier helper + the byte-identical regression).

**Skill posture:**
- Invoke `copowers:writing-plans` against this brief + the spec.
- **Codex chain count: SINGLE chain**, **run to CONVERGENCE** (`NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended -- `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP DEAD in the VS Code extension):** `wsl bash -ilc` OR `export PATH="$HOME/.local/node22/bin:$PATH"`; **VERIFY `command -v codex` -> `/home/<wsluser>/.local/node22/bin/codex`** before the chain. `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < <prompt>` (R1) / `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+; `resume` REJECTS `-s`/`-C`). Pre-generate the diff on Windows; tell Codex NOT to run git. **PERSIST each round's prompt AND response to `.copowers-findings.md`** (`feedback_implementer_persist_codex_responses`).
- **Worktree-cwd corollary (`feedback_degraded_harness_sequential_tool_calls`):** in a worktree session the foreground cwd can silently revert to the primary repo (main), and every `run_in_background` shell starts in the primary repo. **Prefix EVERY git/test command with an explicit `cd <worktree> &&`** (or `git -C <worktree>`) and re-verify `git branch --show-current` + `git rev-parse --short HEAD` BEFORE every commit. (Docs-only plan -> low risk, but the discipline holds.)
- Output: plan at `docs/superpowers/plans/2026-06-02-phase14-close-out-follow-on-bundle-plan.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end.**
2. **The SPEC** (547 lines) -- AUTHORITATIVE. Especially §3 (F-1 root-cause Class A/B + the startup diagnostic + the UNSEEDED gate), §4 (F-2 the two-tier `structural_checks`/`structural_stage` helper + the byte-identical `evaluate()` refactor + the compute-vs-display split), §5 (F-3 segmented polylines), §6 (F-4 spines), §10 (decomposition), §11 (tests/gate), §13 (the OQ table). Re-grep every anchor at STEP 0 (#2).
3. **CLAUDE.md** -- the **Schwab/schwabdev** block (esp. `update_tokens()` does NOT raise on auth failure + `force_access_token` semantics; the `"Schwabdev"` `setLogRecordFactory` redaction; the Schwab CLIENT_ID/SECRET resolution cascade env>cfg>prompt + `SchwabConfigMissingError`) + the **Windows/test-discipline** block (`USERPROFILE`+`HOME` monkeypatch; #15 production-path tests; cp1252 ASCII). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (#2 anchor re-grep, #11 schema-CHECK + Python-constant atomicity if any constant is touched, #15 production-path).
4. **The brainstorm dispatch brief** (`docs/phase14-close-out-follow-on-bundle-brainstorming-dispatch-brief.md`) + the SB5.5 P14.N7 spec/plan (F-1 is SB5.5 code -- the liveness state machine + the checker wrap).
5. **Memory:** `feedback_seeded_gate_masks_default_state` (F-1's gate witnesses the UNSEEDED real-token state), the WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + visual-gate + `feedback_no_false_green_claim` + `feedback_taskstop_does_not_kill_detached_server` entries.

---

## §1 LOCKed dispositions (operator + brainstorm convergence; BINDING -- DO NOT re-litigate)
| OQ | LOCKed |
|---|---|
| **OQ-1 (F-1 fix shape)** | Install-anchored STARTING write -- the install path writes an initial STARTING sidecar with a **readback-verify + WARNING** (addresses Class B). For Class A (no client constructed) the fix is **credential plumbing so `_construct_web_schwab_client` succeeds in the web process** -- NO new `schwabdev.Client.*` site (construction stays in `auth.py:construct_authenticated_client`). **The §3.3 startup diagnostic (a one-shot log of which class fired) runs FIRST at executing-plans to pin A vs B; the plan designs BOTH fixes + the diagnostic, and the executing-plans diagnostic selects.** |
| **OQ-2 (F-1 daemon)** | RESOLVED -- the daemon `checker` heartbeats to ALIVE within ~30s via per-iteration attribute lookup; no separate heartbeat writer needed. |
| **OQ-3a (F-2 helper)** | Two-tier: `structural_checks` (per-check TT1-TT5 `Result` rows) + `structural_stage` (the aggregate wrapper). `evaluate()` REFACTORS to reuse `structural_checks` -- the 8-criterion output stays **byte-identical** (a byte-identical-output regression test is MANDATORY). |
| **OQ-4 (MA windows)** | KEEP `(50, 200)` for the market-weather render. |
| **OQ-5 (F-3 polylines)** | Multiple `<polyline>` elements (one per contiguous non-None run); DROP 1-point segments (a single point is not a line). |
| **OQ-6 (decomposition)** | ONE bundle, 4 slices (F-1 -> F-2 -> F-3 -> F-4). |
| **OQ-7 (Codex chain)** | SINGLE chain (writing-plans + executing-plans each one chain to convergence). |
| **OQ-8 (F-1 Class A vs B)** | Pinned by the §3.3 startup diagnostic at executing-plans -- the plan does NOT pre-assume; it designs the diagnostic + both fixes. |
| **OQ-9 (F-2 SPY criteria)** | Confirm at executing-plans (a DB check that SPY has no persisted `candidate_criteria`) -- the plan notes the check; the live-compute fix is correct regardless. |

### §1.1 Inherited LOCKs (from the spec §2; BINDING)
- **L1** scope = F-1 + F-2 + F-3 + F-4 ONLY. NO B-7, NO close-out review, NO Phase 15 (the schwabdev v3 upgrade stays `#9`; F-1 INFORMS it but does NOT do it).
- **L2** NO swing schema change (v23; `EXPECTED_SCHEMA_VERSION = 23` at `swing/data/db.py:51`; assert no `0024_*.sql`). The liveness stays the existing ephemeral sidecar.
- **L3 (L2-LOCK)** F-1 ZERO new `schwabdev.Client.*` call sites (the Class-A creds fix plumbs `_construct_web_schwab_client`; construction stays in `auth.py:construct_authenticated_client`); `test_l2_lock_source_grep.py` (baseline `bf7e071`) stays green. Do NOT regress the `"Schwabdev"` `setLogRecordFactory` redaction.
- **L4** REUSE not re-implement -- F-1 fixes the existing seed/sidecar path; F-2's two-tier helper reuses the existing TT1-TT5 check logic; F-3 reuses `_polyline_x`/`_polyline_y`; F-4 reuses the existing renderer.
- **L5** read-mostly (ZERO swing-domain writes; the sidecar is an ephemeral file; the chart paths are render-direct; `current_stage`/the new live-compute are SELECT/compute-only).
- **L6** production-path tests (#15) -- **F-1's automated test exercises the REAL `create_app` -> `_install_web_marketdata_caches` seed path with a fake-client monkeypatch (NOT a hand-written sidecar)** + a parameterized construction-path test for the Class-A creds fix; F-2's test asserts the trend classifies (not NA) via the REAL live-compute path given >=250 bars. **Do NOT validate F-1 with a hand-seeded sidecar (the SB5.5 gate's exact mistake).**
- **L7** ASCII; preserve the close-out A-7 badge fix (it must keep rendering UNKNOWN-when-no-sidecar; F-1 makes the sidecar actually appear so the badge shows STARTING/ALIVE in normal operation).

---

## §2 Production anchors (re-grep at STEP 0 per #2; the spec §B/§3/§4 embeds these)
F-1: `checker_resilience.py:130` (`record_tick` BEFORE `original()` at `:135`); `_install_web_marketdata_caches` (`app.py:251`, seed `:274`); `_construct_web_schwab_client` (`app.py:148`, gated `_is_ladder_active`); `resolve_credentials_env_or_prompt` + `construct_authenticated_client` (`auth.py`); `write_liveness_sidecar`/`read_liveness_sidecar`/`checker_liveness_sidecar_path` + `evaluate_liveness_state` (`checker_resilience.py`); the A-7 badge VM (`schwab_checker_badge.py`); `test_l2_lock_source_grep.py` (`bf7e071`). F-2: `current_stage` (`foundation.py:745`, persisted-criteria SELECT); `trend_template.py:22` `evaluate()` / `:24` the `<200` NA / `:33-34` the 150/200 SMAs; the market-weather refresh (`dashboard.py:131-140`); `runner.py:1102` (the evaluated set); the fetch sites + `MIN_CALENDAR_DAYS_FOR_MA200` (`ohlcv_cache.py`); `render_market_weather_svg` (`charts.py:777`). F-3: `_format_polyline_points` (`process_grade_trend.py:262-301`) + the `<polyline>` loop (`process_grade_trend.html.j2:54-62`). F-4: `render_watchlist_thumbnail_svg` (`charts.py:514-552`).

## §3 Codex SINGLE chain (run to convergence; persist prompt+response)
**Watch items:** NO schema (all 4 slices); L2 green (F-1 zero new `schwabdev.Client.*` sites); the F-1 diagnostic-then-fix design covers BOTH Class A (creds plumbing) + Class B (readback-verify) without pre-assuming; the F-1 test exercises the REAL install/seed path (NOT a hand-seeded sidecar) + the UNSEEDED real-token gate; F-2's `evaluate()` byte-identical regression (the 8-criterion output unchanged) + the >=250-bar live-compute via the real fetch path + the compute-vs-display slice; F-3's multiple-`<polyline>` (SVG can't gap a single polyline) + drop-1-point; F-4 spines + the watchlist re-check; the close-out A-7 badge fix preserved; the redaction intact; ASCII; trailer-parse (final `-m` paragraph plain prose). **If a finding needs a schema change or a new `schwabdev.Client.*` call site, STOP + escalate.**

## §4 The eventual operator gate (executing-plans; plan §I; UNSEEDED real-token for F-1)
- **S1** suite + ruff green (READ the actual numbers; baseline 7005; no false-green). **S2** schema v23 / no migration / no new domain writes. **S3** L2 source-grep green (F-1 zero new `schwabdev.Client.` sites). **S4 (F-1, BINDING, UNSEEDED real-token)** the operator runs `swing web` with HEALTHY production tokens + NO hand-seeded sidecar -> the sidecar FILE appears + the badge shows STARTING->ALIVE (the §3.3 diagnostic logged which class fired + the fix resolved it). **S5 (F-2, browser)** the market-weather trend is DEFINED (not "undefined") via the live compute. **S6 (F-3/F-4, browser)** the process-grade-trend lines render gaps-as-gaps; the hyp-rec thumbnails have NO spine borders (+ the watchlist still looks right). **S7** trailers `[]`.
- **If a `swing web` server is launched for S4-S6:** orchestrator-run the BRANCH server (`python -m swing.cli web --port 8081`); kill by PID (`Get-NetTCPConnection -LocalPort 8081` -> `Stop-Process -Force`; verify free) per `feedback_taskstop_does_not_kill_detached_server`. After merge re-run the suite on the MERGED head + READ it; reinstall `swing`.

## §5 Deliverable shape
Plan at `docs/superpowers/plans/2026-06-02-phase14-close-out-follow-on-bundle-plan.md` (mirror the close-out plan format): §A goals/non-goals · §B file map (per slice) · §C surface integration · §D out-of-scope · §E LOCK reverification (the OQ table + L1-L7) · §F discipline hooks · §G the 4 slices as step-checkbox TDD tasks (**F-1 = the §3.3 startup diagnostic FIRST, then the Class-A creds fix + the Class-B readback-verify write, then the UNSEEDED real-token test**; F-2 = the two-tier helper + the byte-identical `evaluate()` regression + the live-compute + the compute-vs-display slice + the `MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE` constant; F-3; F-4) · §H test surface (production-path) · §I the operator gate (S1-S7; UNSEEDED real-token for F-1) · §J Codex placement · §K schema (NO change) · §L fixtures (the F-1 fake-client monkeypatch; the F-2 >=250-bar fixture) · §M forward-binding lessons · §N self-review · §O close-out position note. **Final `-m` paragraph plain prose; verify `%(trailers)` `[]`.**

## §6 If you get stuck
- **F-1 is the deep one:** design the diagnostic + BOTH class fixes; do NOT pre-assume Class A vs B (the executing-plans diagnostic pins it). If the Class-A fix appears to need a new `schwabdev.Client.*` site or a new client path, STOP -- L3 forbids it (plumb the existing `construct_authenticated_client`). If F-1 appears to need a persisted health table or a schema change, STOP -- L2 (ephemeral sidecar).
- **F-2:** if the byte-identical `evaluate()` refactor risks changing ANY of the 8 criterion `Result` rows, STOP -- the two-tier helper must preserve them exactly (the regression is the gate). If the live-compute appears to need a schema change, STOP -- reuse the fetch helpers + a window constant.
- HOLD THE LINE: NO schema (L2); L2-LOCK green (L3); reuse not re-implement (L4); read-mostly (L5); the F-1 gate witnesses the UNSEEDED real-token state (`feedback_seeded_gate_masks_default_state`); preserve the close-out A-7 badge fix.
- NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose. Use the WSL Codex fallback (verify `command -v codex`; persist prompt+response). DO NOT widen to B-7 / the close-out review / Phase 15.

## §7 Return report shape
Mirror the close-out writing-plans return report: final HEAD + commit breakdown (per-round Codex attribution); the single chain + convergent shape (cite `.copowers-findings.md` incl. the final `### Verdict`); plan line count + sections; the OQ dispositions honored verbatim (esp. OQ-1 the diagnostic-then-fix; OQ-3a the two-tier helper); L1-L7 reverification; Codex Majors accepted (ZERO preferred); production-anchor re-grep results; schema verdict (NO change); the L2-LOCK analysis (F-1 zero new sites); the F-1 diagnostic + dual-class fix design + the UNSEEDED test; the F-2 byte-identical regression + the live-compute + the window constant; the gate enumeration (S1-S7; UNSEEDED real-token for F-1); cumulative gotcha application; worktree teardown status; ZERO Co-Authored-By; CLAUDE.md status-line refresh draft; executing-plans dispatch-readiness + the close-out position note.

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-close-out-follow-on-bundle-writing-plans`. Dir `.worktrees/phase14-close-out-follow-on-bundle-writing-plans/`. **Branch from main HEAD `3892457`** (or later if the orchestrator states a newer HEAD in the inline prompt).
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). Prefix git/test commands with `cd <worktree> &&`; re-verify the branch before each commit.
- **Codex chain count:** SINGLE chain to convergence via the WSL fallback (verify `command -v codex`; transcript -> `.copowers-findings.md`).

---

*End of brief. Phase 14 close-out FOLLOW-ON bundle writing-plans dispatch -- derive an executing-plans-ready plan from the LOCKed 547-line spec: 4 serial slices -- F-1 (P14.N7 web checker; the brief's no-op-seed hypothesis was refuted, so the plan designs a §3.3 startup diagnostic to pin Class A [construction-None -> creds plumbing, zero new schwabdev.Client.* sites] vs Class B [silent write-fail -> install-anchored STARTING write + readback-verify], plus an UNSEEDED real-token gate) + F-2 (market-weather trend live-compute via a two-tier structural_checks/structural_stage helper from a >=250-bar fetch, decoupled compute vs display, with a byte-identical evaluate() regression) + F-3 (segmented rolling-line polylines -- one per contiguous run, drop 1-point) + F-4 (hide the hyp-rec thumbnail axes spines). NO schema (v23 held); L2-LOCK green (F-1 zero new schwabdev.Client.* sites); reuse not re-implement; read-mostly. Single Codex chain to convergence (persist prompt+response). The F-1 gate witnesses the UNSEEDED real-token STARTING->ALIVE transition (the SB5.5 gate's miss). OUTPUT: an executing-plans-ready plan + return report.*
