# Phase 14 Sub-bundle 5.5 (Schwab) -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 5.5 writing-plans implementer. No prior conversation context.

**Mission:** Turn the LOCKed SB5.5 brainstorm spec into an executing-plans-ready implementation plan. Two items on the L2-LOCKED Schwab surface, on **schwabdev 2.5.1** (Phase 14 keeps 2.5.1; the v3 upgrade is a Phase 15 item):
- **A-3** -- install the EXISTING production-gated market-data ladder onto the WEB caches at FULL PARITY (daily bars + SMA + last-close quote), governed by the rate-limit-aware **L9** (open-trade scope + TTL + provider-tag cooldown + the L9c header fix).
- **P14.N7** -- WRAP the schwabdev `checker` token-refresh with exception-isolation + retry-with-backoff; surface checker-liveness via an **ephemeral sidecar file** read by BOTH `swing schwab status` (CLI) **AND a new web health badge** (operator re-ruled OQ-6 -- see §1.1). Design the wrap as a **cleanly-removable guard** (the Phase-15 v3 upgrade removes the checker and deletes P14.N7).

**Read-mostly on the trade/Schwab surface; NO swing schema change (v23 held); ZERO new `schwabdev.Client.*` call sites (L2 stays green by construction -- SB5.5 does NOT re-anchor the L2 baseline; that is the Phase-15 v3 arc).**

**Spec (AUTHORITATIVE for implementation):** `docs/superpowers/specs/2026-05-31-phase14-sub-bundle-5-5-schwab-web-marketdata-checker-design.md` (437 lines; merged `4205b63`; genuine single WSL Codex chain CONVERGED R7).

**Brief:** `docs/phase14-sub-bundle-5-5-schwab-writing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 SB1-SB5 SHIPPED; SB5.5 brainstorm SHIPPED `4205b63`; main HEAD at this dispatch: see §8. SB5.5 is the FIRST Phase 14 close-out-tail item.

**Cumulative discipline:** the entire CLAUDE.md **Schwab / schwabdev** gotcha block is the implementation checklist; ~700+ cumulative ZERO Co-Authored-By; **Schema v23 LOCKED (NO migration -- the sidecar is an ephemeral file, surface reuses `'pipeline'`); L2 LOCK** (zero new `schwabdev.Client.*` call sites vs `bf7e071`; `tests/integration/test_l2_lock_source_grep.py` stays green -- **NO re-anchor in SB5.5**).

**Expected duration:** ~3-5 hours writing-plans + a Codex chain to convergence. Plan line target **~800-1200 lines** (3 slices + a small 1b + the web-badge add).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief + the spec.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP DEAD in the VS Code extension):** `wsl bash -ilc` (INTERACTIVE login) OR prefix `export PATH="$HOME/.local/node22/bin:$PATH"`; **VERIFY `command -v codex` -> `/home/<wsluser>/.local/node22/bin/codex`** (NOT the `/mnt/c/.../npm/codex` shim -> `node: not found`) before the chain. `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < <prompt>` (R1) / `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+; `resume` REJECTS `-s`/`-C`). Pre-generate the diff on Windows; tell Codex NOT to run git. **PERSIST each round's PROMPT AND RESPONSE to `.copowers-findings.md`** (v2.0.3 does this by construction; the final `### Verdict` must be readable on disk for orchestrator QA). Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.
- Output: plan at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-5-5-schwab-web-marketdata-checker-plan.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end.**
2. **The SPEC** (`...2026-05-31-phase14-sub-bundle-5-5-...design.md`, 437 lines) -- AUTHORITATIVE. Especially §4 (A-3 full-parity + the L9 design §4.5.1-4.5.5), §5 (P14.N7 §5.1-5.6 incl. the liveness state machine), §6 (the L2 framing), §7 (sandbox + audit-surface), §9 (slices), §10 (tests + gate), §13 (the OQ table). **Where the spec says OQ-6 = CLI-only, the operator RE-RULED to ALSO include a web health badge (see §1.1 below) -- the plan ADDS that surface.**
3. **CLAUDE.md -- the Schwab / schwabdev gotcha block** (the implementation checklist) + `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (esp. #2 anchor re-grep, #15 production-path tests, the shared-`base.html.j2` VM-field-default gotcha for the new web badge).
4. **`docs/phase14-sub-bundle-5-5-schwab-brainstorming-dispatch-brief.md`** §1.0 (the operator rulings: OQ-1 sanctioned L2 extension, OQ-2 full parity, L9 rate-limit-aware) -- carry forward.
5. **Memory:** the WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + visual-gate entries.

---

## §1 LOCKed dispositions (operator 2026-05-31; BINDING -- DO NOT re-litigate)

### §1.1 The OQ dispositions
| OQ | LOCKed |
|---|---|
| **OQ-1** | A-3 is a SANCTIONED L2 extension (designed as intended; zero new call sites; the runtime surface is approved). |
| **OQ-2** | FULL PARITY -- daily bars + SMA + last-close quote (both ladder hooks). |
| **OQ-3** | Reuse `schwab_api_calls.surface='pipeline'` (`pipeline_run_id=NULL`) -- a `'web'` value would need v24; AVOIDED. |
| **OQ-4** | P14.N7 = **WRAP (Approach A)** -- instance-level exception-isolation + retry-with-backoff around the existing `update_tokens`; verify post-call token state (it does NOT raise on failure); the version guard uses `importlib.metadata.version("schwabdev")` -- NEVER construct a `Client` in a test (it spawns a checker + needs creds/network). |
| **OQ-5** | Liveness state = an **ephemeral SIDECAR file** (no schema; atomic `os.replace` from a same-filesystem temp). |
| **OQ-6 (RE-RULED at writing-plans 2026-05-31 -- LIFTS the spec's CLI-only / brainstorm-brief L8)** | Liveness surface = `swing schwab status` (CLI) **AND a new WEB HEALTH BADGE** (both, V1). The badge reads the SAME OQ-5 sidecar and renders a small alive/stale/degraded indicator. **This ADDS a web-render surface beyond the spec** -- plan it as a thin additive reader. Honor the shared-`base.html.j2` gotcha (the new VM field needs a safe default on EVERY base-layout VM: `DashboardVM`/`PipelineVM`/`JournalVM`/`WatchlistVM`/`MetricsIndexVM`/`PageErrorVM`); factor a shared helper. The operator gate gains a BROWSER leg for the badge. |
| **OQ-7** | ONE executing-plans cycle, **3 slices (+1b)** (Slice 1 A-3+L9 · Slice 1b L9c header fix · Slice 2 P14.N7 wrap+liveness record · Slice 3 sidecar writer + `render_status` line + the web badge). |
| **OQ-8** | SINGLE Codex chain (writing-plans + executing-plans each one chain to convergence). |
| **OQ-9** | Cross-process liveness RESOLVED via the OQ-5 sidecar (pure in-memory is invisible to the separate `swing schwab status` process AND the web process). |
| **OQ-10** | The exact Schwab rate-limit header name for L9c: the IMPLEMENTER confirms it (read the schwabdev/Schwab response headers at writing-plans/executing-plans) and lands the extractor change BEHIND the confirmed name -- do NOT guess a name that silently stays `None`. |

### §1.2 Inherited LOCKs (from the spec §2; BINDING)
- **L1** scope = A-3 + P14.N7 + the OQ-6 web badge ONLY.
- **L2** ZERO new `schwabdev.Client.*` call sites (vs `bf7e071`; source-grep stays green) -- A-3 reuses `construct_authenticated_client` + the existing ladder; P14.N7 wraps the existing `update_tokens`. **NO L2 re-anchor in SB5.5.**
- **L3** NO swing schema change (v23 held); the sidecar is an ephemeral file; surface reuses `'pipeline'`.
- **L4** the ladder's production gate (`env=='production' AND marketdata_ladder_enabled`) + the inside-the-ladder sandbox short-circuit PRESERVED -- under sandbox the web path is yfinance-only (audit rows only).
- **L5** REUSE, do not re-implement -- mirror `_install_pipeline_marketdata_caches` (the pipeline ladder install); reuse the existing ladder functions + hooks; wrap (not replace) the checker.
- **L6** audit + redaction preserved (the `"Schwabdev"` capital-S `setLogRecordFactory`; the typed-error audit-row close; the source-artifact shape).
- **L7** production-path test discipline (#15) -- A-3's wiring test exercises the REAL `app.py` cache construction; P14.N7's test simulates a real DNS failure during refresh; NOT stubs.
- **L9** rate-limit-aware (open-trade scope + TTL as the primary defense + a closure-local cooldown reusing `circuit_breaker_cooldown_seconds`; the L9c `rate_limit_remaining` header-name fix). **L9 cooldown is provider_tag-driven** -- the ladder SWALLOWS `SchwabRateLimitError` (`marketdata_ladder.py:317`); NEVER write a test expecting the hook to catch it.
- **P14.N7 = a cleanly-REMOVABLE guard** (Phase-15 v3 deletes the checker; keep the wrap self-contained so it lifts cleanly).

---

## §2 Production corrections + anchors (BINDING; re-grep at writing-plans STEP 0 per #2)
These were orchestrator-verified at the SB5.5 brainstorm QA -- the spec already embeds them, but re-confirm:
- The pipeline cache-install helper is **`_install_pipeline_marketdata_caches`** (`swing/pipeline/runner.py:305`; the ladder hooks install at `:465-466` via `price_cache.set_ladder_fetcher` / `ohlcv_cache.set_ladder_bars_fetcher`) -- **NOT `_build_caches_with_ladder`** (that string is only in a docstring range).
- Web caches are constructed in the **`create_app` body** (`swing/web/app.py:188-189`), NOT the lifespan (the lifespan owns only `price_fetch_executor`).
- `schwab_api_calls.surface` CHECK = `('pipeline','cli','trade_entry','trade_exit')` (`swing/data/migrations/0020*.sql:338`), mirrored in `audit_service._SCHWAB_API_SURFACE_VALUES` -- reuse `'pipeline'` (no v24).
- `rate_limit_remaining` IS extracted (`swing/integrations/schwab/marketdata.py:_extract_response_payload:101-144`) + plumbed (`:536`); the "always None" is a header-NAME mismatch -> L9c is a header-name addition (OQ-10).
- Credential resolution uses `resolve_credentials_env_or_prompt` (env > cfg-tier cascade), NOT env-only.
- `render_status` already emits em dashes (`swing/cli_schwab.py:829/831`) -> any `isascii()` assertion is scoped to the NEW line(s) only.

### §2.1 Forward-binding lessons (from the brainstorm; honor in the plan)
- All hook state (open-trade memo, fallback counter, cooldown ts) needs a `threading.Lock` (executor + request threads race).
- The liveness **daemon-vs-seed** distinction is load-bearing -- the seed call must NOT advance the heartbeat; the render state machine has a strict **6-step precedence** (explicit-failure > ALIVE > stale > STARTING > STARTING-expiry). The web badge must render the SAME state machine.
- Finalize `HEARTBEAT_WRITE_INTERVAL` / `STALE_THRESHOLD` / `STARTUP_GRACE` with the invariant **`STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL`**.
- The checker **startup-race** is the 1 accepted residual (narrow near-expiry-at-startup; seeding mitigation + surfaced-via-liveness; V2 full closure banked) -- the plan documents it, does NOT try to fully close it.

---

## §3 Codex SINGLE-chain placement (OQ-8; run to convergence)
Run ONE chain after the plan is written + internally chunk-reviewed. **Watch items:** L2 stays green (zero new call sites; the manual confirm); NO schema (sidecar ephemeral; surface reuses `'pipeline'`); the OQ-6 web-badge base-VM-field fan-out (every base-layout VM + a shared helper; the shared-`base.html.j2` gotcha); the sidecar cross-process correctness + the 6-step render precedence + the `STALE_THRESHOLD > HEARTBEAT` invariant; the provider_tag-driven cooldown (NOT hook-catches-SchwabRateLimitError); the L9c header-name (OQ-10, no silent-None guess); production-path tests (L7); the daily-bar `(year,N,daily,1)` footgun; redaction intact; the threading.Lock on hook state; P14.N7 stays cleanly-removable. **Persist prompt+response per round.** If a finding needs a schema change or a new call site, STOP + escalate.

---

## §4 The eventual operator gate (executing-plans; for plan §I)
Test/CLI-driven + a NEW browser leg:
- **S1** fast suite + ruff green. **S2** schema unchanged (v23; no `0024`; assert no new `chart_renders`/domain writes). **S3** L2 source-grep green (zero new `schwabdev.Client.` call sites). **S4** A-3 production-path wiring test (ladder hooks installed on the web caches under production; yfinance fallthrough under sandbox). **S5** P14.N7 DNS-failure-survival test + the sidecar liveness state machine + the `swing schwab status` checker-liveness output (operator confirms the CLI). **S6 (NEW -- browser leg)** the **web health badge** renders alive/stale/degraded in a real browser (operator-witnessed). **S7** trailers `[]`.
- **NOTE:** schwabdev **2.5.1** is the target (3.0.5 is Phase 15); the plan does NOT install/assume v3.

---

## §5 Deliverable shape
Plan at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-5-5-schwab-web-marketdata-checker-plan.md` (mirror the SB5 plan format): §A goals/non-goals · §B file map (the A-3 install in `app.py`; the P14.N7 wrap location + the sidecar module; the web-badge VM field + template + the base-VM fan-out; `cli_schwab.py` `render_status` line; the tests) · §C surface integration · §D out-of-scope · §E LOCK reverification (the OQ table + L1-L9) · §F discipline hooks · §G the 3 slices (+1b) as step-checkbox TDD tasks · §H test surface · §I the operator gate (S1-S7 incl. the browser badge leg) · §J Codex placement · §K schema (NO change) · §L fixtures · §M forward-binding lessons · §N self-review · §O Phase 14 close-out position. **Final `-m` paragraph plain prose; verify `%(trailers)` is `[]`.**

---

## §6 If you get stuck
- If a spec/brief anchor no longer matches production (re-grep at STEP 0), ESCALATE -- do NOT silently patch.
- If A-3 appears to need a NEW `schwabdev.Client.*` call site / a new client-construction path, or P14.N7 a new API call, STOP + escalate (L2/L5).
- If anything appears to need a swing schema change / a `'web'` surface enum, STOP + escalate -- reuse `'pipeline'` + the ephemeral sidecar (L3).
- HOLD THE LINE: the production gate + inside-ladder sandbox short-circuit (L4); reuse not re-implement (L5); the provider_tag cooldown (L9); P14.N7 stays cleanly-removable; the web badge reads the SAME sidecar (don't fork the liveness logic).
- NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose. Use the WSL Codex fallback (verify `command -v codex`; persist prompt+response). DO NOT widen to the v3 upgrade (Phase 15) / the close-out polish batch / B-7.

---

## §7 Return report shape
Mirror the prior writing-plans return reports: final HEAD + commit breakdown (per-round Codex attribution); the single Codex chain + convergent shape (**cite `.copowers-findings.md` rounds incl. the final `### Verdict`**); plan line count + sections; the OQ dispositions honored verbatim (incl. the OQ-6 web-badge add); L1-L9 reverification; Codex Majors accepted (ZERO preferred); production-anchor re-grep results (the `_install_pipeline_marketdata_caches` correction etc.); schema verdict (NO change); the L9c header-name resolution (OQ-10); the web-badge base-VM fan-out plan; the gate enumeration (S1-S7 incl. the browser leg); cumulative gotcha application; worktree teardown status; ZERO Co-Authored-By confirmation; CLAUDE.md status-line refresh draft; executing-plans dispatch-readiness.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-5-5-schwab-writing-plans`. Dir `.worktrees/phase14-sub-bundle-5-5-schwab-writing-plans/`. **Branch from main HEAD = the commit that adds this brief** (the orchestrator states it in the inline prompt).
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain to convergence via the WSL fallback (copowers v2.0.3; verify `command -v codex`; transcript -> `.copowers-findings.md`).
- **Schwabdev target:** 2.5.1 (3.0.5 is Phase 15 -- do NOT install/assume v3).

---

*End of brief. Phase 14 Sub-bundle 5.5 writing-plans dispatch -- derive an implementation plan from the LOCKed 437-line spec: A-3 (full-parity web market-data ladder install mirroring `_install_pipeline_marketdata_caches`, governed by L9 rate-limit-aware gates) + P14.N7 (wrap the schwabdev checker with exception-isolation + retry; ephemeral cross-process liveness sidecar read by BOTH `swing schwab status` AND a new web health badge [operator re-ruled OQ-6]); on schwabdev 2.5.1; NO schema (v23 held); ZERO new schwabdev.Client.* call sites (no L2 re-anchor in SB5.5); P14.N7 designed as a Phase-15-removable guard. Single Codex chain to convergence (persist prompt+response). The gate is test/CLI-driven + a browser leg for the badge. OUTPUT: an executing-plans-ready plan + return report.*
