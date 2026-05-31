# Phase 14 Sub-bundle 5.5 -- Schwab-focused (A-3 web market-data wiring + P14.N7 checker resilience) -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 5.5 brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for the **Schwab-focused close-out sub-bundle (SB5.5)** -- the FIRST item of the Phase 14 close-out tail. Two coherent Schwab-integration-surface items:
- **A-3 -- Schwab daily-bar web wiring:** the web-side SMA/daily-bar path (`OhlcvCache`/`PriceCache`, constructed plain in `swing/web/app.py`) is **yfinance-only by wiring** -- the Schwab market-data ladder (`swing/integrations/schwab/marketdata_ladder.py`, gated `env==production AND marketdata_ladder_enabled`) is installed **pipeline-side only**. Install the EXISTING ladder onto the WEB caches so the web SMA path uses the same Schwab->yfinance ladder the pipeline does (under the same gate).
- **P14.N7 -- schwabdev background `checker`-thread resilience:** schwabdev spawns a daemon `checker` thread for background token refresh that **dies on an uncaught `ConnectionError`/`NameResolutionError`** under sleep/wake/DNS-failure cycles -> **silent token-refresh degradation until `swing web` restart**. Wrap/replace the checker loop with exception-isolation + retry-with-backoff; add an operator-visible degraded-health surface (`swing schwab status` checker-liveness).

This is an **infrastructure + resilience sub-bundle on the L2-LOCKED Schwab surface** -- the L2 framing of A-3 is THE central brainstorm question (see §3 OQ-1). NOT a new-metrics, new-UX, or new-Schwab-feature sub-bundle.

**Brief:** `docs/phase14-sub-bundle-5-5-schwab-brainstorming-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at `bf7e071`; Sec 9.1 LOCKs at `7a558e4`. **ALL 5 sub-bundles SHIPPED end-to-end:** SB1 (data-wiring) `e323339`; SB2 (temporal log v22) `27f8007`; SB3 (chart-surface v23) `edd098d`; SB4 (review+journal) `31da4a5`; SB5 (metrics overview) `6206fb6`. Housekeeping at `f274dd8`. **Main HEAD at SB5.5 brainstorming dispatch: `f274dd8`.** SB5.5 is the FIRST of the operator-LOCKed close-out tail (SB5.5 -> close-out polish batch -> B-7 -> Sec 9.1 Q6 close-out review).

**Cumulative discipline at dispatch:** 37+ CLAUDE.md gotchas BINDING (the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); **~700+ cumulative ZERO Co-Authored-By trailer drift**; **Schema v23 LOCKED -- SB5.5 expected to introduce NO schema change** (A-3 is pure wiring; P14.N7's health surface is in-memory/ephemeral -- confirm at brainstorm); **L2 LOCK is the central constraint** (zero NEW `schwabdev.Client.*` call SITES vs baseline `bf7e071`; the source-grep test `tests/integration/test_l2_lock_source_grep.py` MUST stay green).

**Expected duration:** ~3-5 hours brainstorming + a Codex chain run to convergence. Spec line target **~500-800 lines** (two infrastructure items on a shared surface; the L2 framing + the ladder-install + the checker-resilience contract + the test/gate strategy).

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- **Codex chain count: SINGLE chain** at end (Sec 9.1 Q7). **Run to CONVERGENCE** (zero new criticals AND zero new majors); the ~5-round cap is **suspended for this project** (memory `feedback_codex_round_limit_suspended`); may exceed 5 rounds; do NOT stop while majors surface, do NOT pad after convergence.
- **Codex transport -- copowers v2.0.3 + WSL Codex CLI fallback (reads the repo FROM DISK):** the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension. **Do NOT attempt the MCP tools.** The `adversarial-critic` skill auto-routes to a WSL Codex fallback that reads the worktree from disk and (v2.0.3) appends the **full prompt+response transcript** per round to `.copowers-findings.md` (`## Round N` / `### Prompt sent to Codex` / `### Codex response` incl. the `### Verdict` line). **Preferred: invoke `copowers:brainstorming` normally.** If driving directly: use `wsl.exe bash -ilc` (INTERACTIVE login) OR prefix `export PATH="$HOME/.local/node22/bin:$PATH"`, and **VERIFY `command -v codex` resolves to `/home/<wsluser>/.local/node22/bin/codex`** (NOT a `/mnt/c/.../npm/codex` shim, which dies `node: not found`) BEFORE the chain. `codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/<this-worktree> - < <promptfile>` (R1) / `... codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+; `resume` REJECTS `-s` AND `-C`). The worktree `.git` is a Windows path WSL can't resolve -> pre-generate the diff on Windows; tell Codex NOT to run git. See memory `feedback_wsl_native_codex_invocation` + `feedback_copowers_codex_mcp_windows_launcher` + `feedback_implementer_persist_codex_responses`.
- Output: design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-5-5-schwab-web-marketdata-checker-design.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/phase3e-todo.md`** -- the **`#5`** close-out punch-list entry, specifically the **"NEW Sub-bundle 5.5 -- Schwab-focused"** block (the operator-LOCKed A-3 + P14.N7 framing, dated 2026-05-30) + the L2-LOCK note ("A-3 installs the EXISTING ladder -- intended ZERO new `schwabdev.Client.*` call SITES beyond the ladder's own; confirm the L2 framing at SB5.5 brainstorm").

3. **`docs/phase14-commissioning-brief.md`** -- the deferred-list + forward-look entries for the Schwab market-data ladder web wiring + the schwabdev checker resilience (Sec 1 / Sec 8); Sec 9.1 LOCKs (Q2 serial, Q6 operator-witnessed close-out, Q7 Codex chain discretion).

4. **CLAUDE.md** -- the entire **Schwab / schwabdev gotcha block** is load-bearing here. Especially: **Schwab `price_history` minute-default footgun** (any DAILY-bar consumer MUST pass `(year|month, N, daily, 1)` -- the ladder already does; verify the web path inherits it); **Schwab writes domain rows ONLY when `environment=='production'`** + **sandbox short-circuit lives INSIDE the ladder layer** (so the web path under sandbox falls through to yfinance with audit-only rows -- preserve this); **schwabdev `update_tokens()` does NOT raise on auth failure** (P14.N7 must verify post-call state); **schwabdev 2.5.1 logger name `"Schwabdev"`** + the `setLogRecordFactory` redaction (don't regress it); **7-day refresh-token TTL** (`swing schwab status` already surfaces days-remaining -- P14.N7 ADDS checker-liveness to the same surface). AND the **#15 "byte-parity tests are INSUFFICIENT when fixtures bypass the production derivation path"** gotcha (the A-3 wiring test MUST exercise the real web-cache construction, not a stub). AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- esp. **#2** (signature/anchor re-grep at writing-plans), **#15** (production-path regression test, not a stub).

5. **Production code surfaces to read BEFORE drafting (architectural anchors -- ORCHESTRATOR-VERIFIED at dispatch; re-grep at writing-plans per #2):**
   - **A-3 -- the web caches (install target):** `swing/web/app.py:188-189` constructs `PriceCache(cfg)` + `OhlcvCache(cfg)` **plain -- NO ladder hooks**. The hooks ALREADY EXIST on the caches: `OhlcvCache.set_ladder_bars_fetcher` (`swing/web/ohlcv_cache.py:112`) + `PriceCache.set_ladder_fetcher` (`swing/web/price_cache.py:75`). **A-3 = call these in `app.py`, mirroring the pipeline.**
   - **A-3 -- the PIPELINE precedent (mirror this; do NOT re-implement):** `swing/pipeline/runner.py:308-327` `_build_caches_with_ladder` constructs the caches + installs the ladder hooks via `set_ladder_fetcher`/`set_ladder_bars_fetcher`, each closing over a Schwab client; gated by `env==production AND marketdata_ladder_enabled`; **sandbox short-circuit lives INSIDE the ladder** so under sandbox the hooks fall through to yfinance (audit rows `surface='pipeline'`). A-3's web equivalent would record `surface='web'` (confirm the audit-surface value at brainstorm).
   - **A-3 -- the ladder itself (REUSE, do not modify):** `swing/integrations/schwab/marketdata_ladder.py` -- `fetch_quote_via_ladder:264`, `fetch_window_via_ladder:358`, `_is_ladder_active:221` (the `env==production AND marketdata_ladder_enabled` gate). **The ladder's own `schwabdev.Client.*` calls are PRE-EXISTING (counted at the L2 baseline)** -- installing the ladder on the web caches reuses them.
   - **A-3 -- the web daily-bar consumer:** `swing/web/chart_jit.py:117` `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=200)` -> `swing/web/ohlcv_cache.py:131` `get_or_fetch` (the SMA/daily-bar path the ladder would feed). Confirm which web consumers (charts, SMA, last-close) are in/out of A-3 scope.
   - **P14.N7 -- the checker thread:** schwabdev's `Client` spawns a `daemon=True` `checker` thread for background token refresh (referenced at `swing/integrations/schwab/auth.py:1781`). It dies silently on an uncaught network exception. Find where the web app constructs/holds the Schwab client (the checker runs for the life of `swing web`); design the resilience wrap (exception-isolation + retry-with-backoff) + the liveness signal.
   - **P14.N7 -- the health surface:** `swing schwab status` (the schwab CLI status subcommand in `swing/cli.py` / the schwab CLI group; re-grep the exact location per #2) already surfaces refresh-token days-remaining with severity escalation (CLAUDE.md). P14.N7 ADDS checker-liveness (last-successful-refresh timestamp / alive flag) to the SAME surface.
   - **L2 LOCK test (the gate that must stay green):** `tests/integration/test_l2_lock_source_grep.py` -- baseline `L2_LOCK_BASELINE_SHA = "bf7e071"`; greps for NEW/inflated `schwabdev.Client.` call-sites in `swing/` at HEAD vs baseline (`test_l2_lock_no_new_call_sites_vs_commissioning_baseline`). **A-3 + P14.N7 must NOT inflate any `schwabdev.Client.` call-site count.**
   - **Schema anchor:** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`). SB5.5 expected to add NO migration (confirm at brainstorm).

6. **`docs/superpowers/specs/`** -- the Schwab-mapper + Phase 11/12 Schwab specs (REFERENCE for the ladder/auth architecture + the audit-row discipline + the sandbox-gating LOCK).

7. **`docs/orchestrator-context.md`** §"Pre-Codex review + brief-authoring disciplines".

8. **Memory:** `feedback_copowers_codex_mcp_windows_launcher` + `feedback_wsl_native_codex_invocation` (the v2.0.3 WSL Codex transport + the `command -v codex` verification), `feedback_implementer_persist_codex_responses` (read `.copowers-findings.md` for QA), `feedback_codex_round_limit_suspended` (run to convergence), `feedback_commit_message_trailer_parse_hazard` (final `-m` paragraph plain prose), `feedback_visual_gate_both_render_and_browser` (the operator-witnessed gate pattern -- re-confirm the SB5.5 gate, which is more test/CLI-driven than browser-driven).

---

## §1 Pre-locked operator decisions (DO NOT re-litigate)

### §1.1 Sec 9.1 LOCKs
- **Q2** SERIAL (SB5.5 is its own cycle, after SB5, before the close-out polish batch).
- **Q6** operator-witnessed verification at merge -- but SB5.5 is infrastructure/resilience, NOT a visual surface; the gate is the wiring/test/CLI evidence (see §2.4), with operator confirmation of the `swing schwab status` checker-liveness output + (if feasible) a production-session smoke of the web ladder path.
- **Q7** Codex chain count = orchestrator discretion -> **SINGLE chain** for THIS brainstorming.

### §1.2 Sub-bundle 5.5 phase-specific LOCKs (this brief)
- **L1** Scope = **A-3 (web market-data ladder wiring) + P14.N7 (checker resilience) ONLY.** Do NOT add new Schwab features, new market-data sources, new metrics, or UX. Do NOT widen to the close-out polish batch / B-7 / Phase 15+.
- **L2 (CENTRAL)** **Zero NEW `schwabdev.Client.*` call SITES** vs baseline `bf7e071` (`tests/integration/test_l2_lock_source_grep.py` stays green). A-3 INSTALLS the EXISTING ladder (its Schwab calls are pre-existing); P14.N7 WRAPS the existing checker (adds no API calls). **The open question is whether installing the ladder on the web path -- which adds a new RUNTIME Schwab-call SURFACE (the web app, under the existing production gate) even with zero new call SITES -- stays within the L2 LOCK's intent or needs an explicit operator carve-out (§3 OQ-1). HOLD for operator triage; do NOT unilaterally decide.**
- **L3** **Expected NO schema change** (v23 held). A-3 is pure wiring; P14.N7's checker-liveness is in-memory/ephemeral state surfaced by `swing schwab status` (NOT a new persisted table/column -- recommend; confirm at brainstorm). Do NOT touch the v22/v23 substrate.
- **L4** **Sandbox-gating + the inside-the-ladder short-circuit are PRESERVED** -- under `env != production` OR `marketdata_ladder_enabled == False`, the web path falls through to yfinance EXACTLY as the pipeline does (audit rows only; NO domain Schwab calls). The web ladder install MUST inherit the ladder's own gate, not re-implement a looser one.
- **L5** **REUSE, do not re-implement** -- A-3 mirrors `_build_caches_with_ladder` (runner.py) + the existing `set_ladder_*_fetcher` hooks + the existing ladder functions; P14.N7 wraps schwabdev's existing checker. NO new ladder, NO new client-construction path, NO new market-data fetcher.
- **L6** **Audit + redaction discipline** -- A-3's web ladder calls record `schwab_api_calls` audit rows (confirm `surface` value, e.g. `'web'`); the schwabdev log-redaction `setLogRecordFactory` (capital-S `"Schwabdev"`) MUST stay intact; P14.N7's checker wrap must not leak tokens in its retry/health logging.
- **L7** **Production-path test discipline (#15)** -- the A-3 wiring test MUST exercise the REAL `app.py` cache construction (assert the ladder hooks are installed on `app.state.ohlcv_cache`/`price_cache` under production + that they fall through to yfinance under sandbox), NOT a stubbed cache. The P14.N7 test simulates a DNS failure during refresh and asserts the checker survives + liveness reflects degraded->recovered.
- **L8** **No new web-render / HTMX surface** (P14.N7's liveness is CLI-surfaced via `swing schwab status`; if a web health badge is proposed, that is a SEPARATE OQ -- recommend CLI-only for V1).

---

## §2 Spec scope to design

### §2.1 A-3 -- install the market-data ladder on the web caches
- Mirror `swing/pipeline/runner.py:308-327` `_build_caches_with_ladder`: in `swing/web/app.py` (lifespan/startup), after constructing `PriceCache`/`OhlcvCache`, install the ladder hooks via `set_ladder_fetcher`/`set_ladder_bars_fetcher` when `env==production AND marketdata_ladder_enabled`, each closing over a Schwab client from the EXISTING client factory. Define: the audit `surface` value for web ladder calls; which web consumers are in scope (`chart_jit.get_or_fetch` daily bars; SMA path; last-close quote); the failure/degrade behavior (ladder miss -> yfinance fallback, F6 transient-empty discipline); the no-open-trades / quota considerations (OHLCV fetch scope gotcha).
- **The L2 framing (§3 OQ-1) gates this whole item** -- the spec lays out the call-SITE-count argument (zero new `schwabdev.Client.*` sites) vs the new-runtime-Schwab-SURFACE argument (the web app now issues Schwab market-data calls under the production gate) and HOLDS for operator triage.

### §2.2 P14.N7 -- schwabdev checker-thread resilience
- Design the exception-isolation + retry-with-backoff wrap around schwabdev's `checker` token-refresh loop (so an uncaught `ConnectionError`/`NameResolutionError` no longer kills the daemon thread); decide wrap-vs-replace (monkeypatch the loop vs supervise/restart the thread); verify post-refresh state (`update_tokens()` does not raise on failure -- check `access_token` rotated). Define the liveness signal (last-successful-refresh ts + alive flag) and how `swing schwab status` surfaces it (severity escalation alongside the existing days-remaining).

### §2.3 Shared concerns
- The Schwab client lifecycle under `swing web` (the checker runs for the server's life); the L6 redaction/audit discipline; whether A-3 and P14.N7 share the web Schwab-client construction (likely yes -- one client feeds both the ladder hooks and the checker).

### §2.4 Operator-witnessed gate enumeration (test/CLI-driven, not browser)
- S1 fast suite + ruff; S2 schema (assert NO migration); **S3 the L2-lock source-grep test stays green** (zero new `schwabdev.Client.` call sites); S4 the A-3 production-path wiring test (ladder hooks installed on the web caches under production; yfinance fallthrough under sandbox); S5 the P14.N7 DNS-failure-survival test + the `swing schwab status` checker-liveness output (operator confirms the CLI surface); S6 trailers `[]`. If a production Schwab session is available, an optional operator smoke of the web daily-bar path using the ladder.

---

## §3 Open questions (Codex SHOULD surface answers; operator triage at writing-plans dispatch)

1. **OQ-1 (THE central L2 question):** does installing the EXISTING ladder on the web path stay within the L2 LOCK -- because it adds ZERO new `schwabdev.Client.*` call SITES and reuses the existing production-gated ladder -- **or** does it require an explicit operator carve-out because it introduces a NEW RUNTIME Schwab-call SURFACE (the web app issuing market-data calls under `swing web`, where before the web was yfinance-only)? Lay out BOTH framings with the call-site-count evidence + the runtime-surface implication; **HOLD for operator triage. Do NOT proceed to writing-plans on A-3 until the operator rules.**
2. **OQ-2 (A-3 consumer breadth):** which web market-data consumers does A-3 wire to the ladder -- daily bars (`chart_jit.get_or_fetch`) only, or also the SMA path + the last-close quote (`PriceCache`)? Narrow (daily bars) vs full parity with the pipeline.
3. **OQ-3 (A-3 audit surface):** the `schwab_api_calls.surface` value for web ladder calls (`'web'`? a new value? reuse `'pipeline'`? -- a new CHECK enum value would be a schema trigger -> AVOID; confirm the existing enum allows a web value or use an existing one).
4. **OQ-4 (P14.N7 wrap vs replace):** monkeypatch/wrap schwabdev's checker loop in place vs supervise-and-restart the thread externally. Tradeoffs (schwabdev-version brittleness vs control).
5. **OQ-5 (P14.N7 liveness persistence):** in-memory/ephemeral liveness (recommend; no schema) vs a persisted health row (schema v24 -- AVOID).
6. **OQ-6 (P14.N7 surface):** CLI-only (`swing schwab status`; recommend V1) vs also a web health badge (a new render surface -- defer).
7. **OQ-7 (decomposition):** A-3 and P14.N7 as ONE executing-plans bundle (2 slices) vs two separate cycles. (Operator LOCKed them into ONE SB5.5 cycle; the spec recommends the slice decomposition.)
8. **OQ-8 (Codex chain count at writing-plans/executing-plans):** single chain (recommend) vs two.

---

## §4 OUT OF SCOPE (do not design into V1)
- The close-out polish batch (P14.N1 dashboard thumbnails, A-1 market_weather 200MA, A-2 vcp crowding, A-4 `_bulz_*` rename, A-6 process-grade dark-mode chart) -- sequenced AFTER SB5.5
- B-7 operator failure-mode classification (Phase 14 final touch)
- The Phase 14 close-out review (Sec 9.1 Q6) -- after the polish batch + B-7
- Any NEW Schwab feature / new market-data source / new broker; any NEW `schwabdev.Client.*` call SITE (L2)
- A new persisted health/schema surface (L3; keep liveness ephemeral) -- no v24
- A web health-badge render surface (defer; CLI-only V1)
- Loosening the ladder's `env==production AND marketdata_ladder_enabled` gate or the inside-the-ladder sandbox short-circuit (L4)
- The v22/v23 substrate; SB1-SB5 surfaces; Phase 15+

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **Brief-vs-production-signature verification (#2)** -- cite real anchors (`app.py:188-189`, `set_ladder_bars_fetcher`/`set_ladder_fetcher`, `_build_caches_with_ladder` runner.py:308-327, `marketdata_ladder._is_ladder_active:221`, `chart_jit.get_or_fetch:117`, the checker at `auth.py:1781`, `test_l2_lock_source_grep.py` baseline `bf7e071`). Re-grep the exact `swing schwab status` command location.
2. **L2 LOCK (CENTRAL)** -- the spec proves A-3 + P14.N7 add ZERO new `schwabdev.Client.*` call sites AND frames the new-runtime-Schwab-surface question for operator triage (OQ-1). Codex must NOT wave A-3 through without surfacing the runtime-surface implication.
3. **Sandbox-gating preserved (L4)** -- the web ladder inherits the production gate + the inside-the-ladder short-circuit; under sandbox the web path is yfinance-only (audit rows only).
4. **Reuse, no re-implementation (L5)** -- mirror `_build_caches_with_ladder`; no new ladder/client/fetcher.
5. **Production-path test discipline (#15 / L7)** -- the A-3 test exercises the real `app.py` construction; the P14.N7 test simulates a real DNS failure during refresh (not a stubbed checker).
6. **Schema (L3)** -- assert NO migration; liveness ephemeral; the audit `surface` value does not require a new CHECK enum.
7. **Redaction/audit (L6)** -- the checker wrap + ladder web calls don't leak tokens; the `setLogRecordFactory` stays intact; `update_tokens()` post-call state is verified (it doesn't raise on failure).
8. **schwabdev brittleness (P14.N7)** -- the wrap-vs-replace choice is robust to schwabdev's daemon-checker internals; the daily-bar footgun (`periodType=day,...,minute`) is not reintroduced on the web path.
9. **L2 source-grep continues passing; ASCII (#16/#32) for any new CLI status output; Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape

**Design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-5-5-schwab-web-marketdata-checker-design.md`** (mirror the SB5 brainstorm spec format):
§1 Architecture overview (the two items + the shared Schwab-client lifecycle under `swing web`) · §2 Pre-locked decisions (Sec 9.1 + L1-L8) · §3 Module touch list (`swing/web/app.py` ladder install; the checker-resilience wrap location; `swing schwab status` liveness; the tests) · §4 A-3 web-ladder-install design (mirroring the pipeline) · §5 P14.N7 checker-resilience design · §6 The L2 framing analysis (OQ-1 -- both arguments, for operator triage) · §7 Sandbox-gating + audit-surface contract · §8 Schema impact (NO change) · §9 Sub-bundle decomposition recommendation (slices) · §10 Test fixture strategy + gate enumeration (production-path; DNS-failure sim) · §11 Schema impact (NO change) · §12 V1 simplifications + V2 candidates · §13 Operator decision items (OQs, esp. OQ-1) · §14 Cumulative discipline compliance (L2/L4/L6 central) · §15 Phase 14 close-out position note (SB5.5 is the first close-out-tail item).

**Target ~500-800 lines.** Commit stem: `docs(phase14-sub-bundle-5-5-spec): brainstorm <draft|R1|...> -- ...` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- **If the L2 framing (OQ-1) cannot be resolved as "zero new call sites + within-intent" without an operator ruling, STOP at the OQ -- do NOT design the A-3 install as if approved.** Present both framings and HOLD. (This is the single most important hold in SB5.5.)
- If A-3 appears to need a NEW `schwabdev.Client.*` call site, a new client-construction path, or a new fetcher, ESCALATE -- L2/L5 forbid it (reuse the existing ladder + factory).
- If P14.N7 appears to need a persisted health table/column, PREFER ephemeral in-memory liveness (L3); escalate before designing a v24.
- HOLD THE LINE: the production gate + inside-the-ladder sandbox short-circuit (L4); zero new schwabdev call sites (L2); reuse not re-implement (L5); CLI-only liveness V1 (L8).
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep the final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead in the VS Code extension); use the WSL Codex fallback (verify `command -v codex` first; v2.0.3 writes the transcript to `.copowers-findings.md`).
- DO NOT widen scope to the close-out polish batch / B-7 / Phase 15+; DO NOT touch the v22/v23 substrate.

---

## §8 Return report shape

Mirror the SB5 brainstorm return report (15 items): final HEAD + commit breakdown; Codex round chain + convergent shape (**EVIDENCE it ran genuinely via WSL -- cite the `.copowers-findings.md` rounds incl. the final `### Verdict` line**); spec line count + per-section; pre-locked decisions verbatim verification (Sec 9.1 + L1-L8); OQs resolved + deferred (esp. OQ-1, the L2 framing -- flagged for operator); Codex Major findings accepted (ZERO preferred); brief-vs-production corrections (any anchor that drifted); V1 simplifications + V2 candidates; forward-binding lessons for writing-plans; sub-bundle decomposition recommendation (slices); schema impact verdict (NO change); L2-LOCK analysis summary (zero new call sites + the runtime-surface framing); cumulative gotcha application; worktree teardown status; ZERO Co-Authored-By confirmation (`%(trailers)`); CLAUDE.md status-line refresh draft; writing-plans dispatch-readiness summary + the Phase 14 close-out position note.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-5-5-schwab-brainstorming`. Dir `.worktrees/phase14-sub-bundle-5-5-schwab-brainstorming/`. Branch from main HEAD `f274dd8`.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** SINGLE chain at end (Sec 9.1 Q7), run to convergence via the WSL Codex fallback (copowers v2.0.3; MCP dead in the VS Code extension; verify `command -v codex` first; transcript persists to `.copowers-findings.md`).
- **Expected duration:** ~3-5 hours brainstorming + a Codex chain run to convergence.

---

*End of brief. Phase 14 Sub-bundle 5.5 (the FIRST close-out-tail item) brainstorming dispatch -- produce a design spec for the Schwab-focused infrastructure pair: A-3 (install the EXISTING production-gated market-data ladder onto the web caches in app.py, mirroring the pipeline's _build_caches_with_ladder) + P14.N7 (exception-isolate + retry the schwabdev checker token-refresh thread; surface checker-liveness via swing schwab status). ~500-800 lines; single Codex chain to convergence. The L2 LOCK is the central constraint -- the spec must prove ZERO new schwabdev.Client.* call sites AND frame the new-runtime-Schwab-surface question for operator triage (OQ-1; HOLD, do not decide). Expected NO schema change (v23 held); reuse not re-implement; sandbox-gating preserved. The gate is test/CLI-driven (L2-lock green + production-path wiring test + DNS-failure-survival test + the swing schwab status liveness output), not browser-driven. OUTPUT: a design spec the writing-plans phase can derive a plan from once the operator rules on OQ-1.*
