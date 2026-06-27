# Phase 14 Sub-bundle 5.5 (Schwab) -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 5.5 executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed SB5.5 plan to ship production code + tests on the L2-LOCKED Schwab surface, on **schwabdev 2.5.1**:
- **A-3** -- install the EXISTING production-gated market-data ladder onto the WEB caches in `swing/web/app.py` at FULL PARITY (daily bars + SMA + last-close quote), mirroring `swing/pipeline/runner.py:_install_pipeline_marketdata_caches`; the L9 rate-limit gates (open-trade scope + TTL + provider-tag cooldown) live inside the new hook closures under a `threading.Lock`.
- **A-3 / L9c** -- a once-per-process, thread-safe, redaction-safe INFO log of the Schwab rate-limit response-header KEYS (names only) so the operator confirms the real header name at the production smoke (OQ-10; do NOT guess a name that silently stays `None`).
- **P14.N7** -- WRAP the one web Schwab client's bound `update_tokens` with exception-isolation + retry-with-backoff (a cleanly-removable guard); write liveness to an ephemeral JSON sidecar (atomic `os.replace`); ONE shared 6-step liveness state machine consumed by BOTH `swing schwab status` (CLI) AND a NEW web health badge.

**Read-mostly on the trade/Schwab surface; NO swing schema change (v23 held); ZERO new `schwabdev.Client.*` call sites (L2 stays green; NO re-anchor in SB5.5 -- that is the Phase-15 v3 arc). schwabdev 2.5.1 is the target -- 3.0.5 is Phase 15; do NOT install or assume v3.**

**Plan (AUTHORITATIVE):** `docs/superpowers/plans/2026-05-31-phase14-sub-bundle-5-5-schwab-web-marketdata-checker-plan.md` (1821 lines; merged `1bd1558`; genuine single WSL Codex chain CONVERGED R6). The spec is `docs/superpowers/specs/2026-05-31-phase14-sub-bundle-5-5-schwab-web-marketdata-checker-design.md`.

**Brief:** `docs/phase14-sub-bundle-5-5-schwab-executing-plans-dispatch-brief.md` (this file).

**Context:** Phase 14 SB1-SB5 SHIPPED; SB5.5 brainstorm `4205b63` + writing-plans `1bd1558` SHIPPED. **Main HEAD at this dispatch: `94d0b88`.** SB5.5 is the FIRST Phase 14 close-out-tail item.

**Cumulative discipline:** the entire CLAUDE.md **Schwab / schwabdev** gotcha block is the implementation checklist; ~700+ cumulative ZERO Co-Authored-By; **Schema v23 LOCKED (NO migration)**; **L2 LOCK** (zero new `schwabdev.Client.*` call sites vs `bf7e071`; `tests/integration/test_l2_lock_source_grep.py` MUST stay green; NO re-anchor).

**Expected duration:** ~4-7 hours implementation + 1 Codex chain. Plan §G enumerates 4 slices (Slice 1 -> 1b -> 2 -> 3, serial); **~32 fast tests** projected (trust `pytest -m "not slow" -q` over the estimate; **capture the exact baseline at branch creation** -- prior merged-main baseline was 6933). SHIPS production code + tests under `swing/` + `tests/` with **ZERO new migration**.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief + the plan.
- **Codex chain count: ONE chain** (OQ-8). **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP DEAD in the VS Code extension):** `wsl bash -ilc` (INTERACTIVE login) OR prefix `export PATH="$HOME/.local/node22/bin:$PATH"`; **VERIFY `command -v codex` -> `/home/<wsluser>/.local/node22/bin/codex`** (NOT the `/mnt/c/.../npm/codex` shim) before the chain. `codex exec -s read-only --skip-git-repo-check -C /mnt/c/.../<worktree> - < <prompt>` (R1) / `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (R2+; `resume` REJECTS `-s`/`-C`). Pre-generate the diff on Windows; tell Codex NOT to run git. **PERSIST each round's PROMPT AND RESPONSE to `.copowers-findings.md`** (v2.0.3 by construction; the final `### Verdict` must be readable on disk for orchestrator QA). Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.
- Output: production code + tests + return report at `docs/phase14-sub-bundle-5-5-schwab-executing-plans-return-report.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end.**
2. **The PLAN** (1821 lines) -- AUTHORITATIVE for implementation. §B file map (re-grep every anchor at STEP 0 per #2); §G the 4 slices (step-checkbox TDD); §H test surface; §I the operator gate (S1-S7); §K schema (NO change); §M forward-binding lessons.
3. **CLAUDE.md -- the Schwab / schwabdev gotcha block** + `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (esp. #2 anchor re-grep, #15 production-path tests, the shared-`base.html.j2` VM-field-default gotcha for the web badge).
4. **The SB5.5 spec** (reference for architectural rationale; the L9 design §4.5, the P14.N7 liveness state machine §5).
5. **Memory:** WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + visual-gate + `feedback_no_false_green_claim` + `feedback_taskstop_does_not_kill_detached_server` (if a server is launched for the badge gate).

---

## §1 Slices (plan §G is AUTHORITATIVE; serial; 3-5 commits/slice; cascade-audit + `%(trailers)` `[]` after each)
- **Slice 1 -- A-3 web ladder install + L9 gates:** in `create_app` (`swing/web/app.py:188-189`, NOT the lifespan), when `env=='production' AND marketdata_ladder_enabled`, construct a web Schwab client via the EXISTING `construct_authenticated_client` factory + install the EXISTING `set_ladder_fetcher`/`set_ladder_bars_fetcher` hooks on the web `PriceCache`/`OhlcvCache`, mirroring `_install_pipeline_marketdata_caches`. The L9 gates (open-trade scope + TTL + provider-tag cooldown reusing `circuit_breaker_cooldown_seconds=60`) live inside the hook closures under a `threading.Lock`. Audit `surface='pipeline'`. Production-path test (real `create_app`); sandbox -> yfinance-only (client NOT constructed -> fast suite stays offline).
- **Slice 1b -- L9c header-key capture (OQ-10):** the once-per-process, thread-safe, INFO-level, redaction-safe log of the response-header KEYS (names only). NO guessed header name.
- **Slice 2 -- P14.N7 checker wrap + liveness record:** replace the one web client's bound `client.tokens.update_tokens` with a resilient wrapper (exception-isolation + retry-with-backoff; verify post-call token state -- `update_tokens` does NOT raise on failure); record liveness. The version guard uses `importlib.metadata.version("schwabdev")` -- NEVER construct a `Client` in a test. Simulate a real `ConnectionError` during refresh (L7).
- **Slice 3 -- sidecar writer + CLI line + web badge:** the ephemeral JSON sidecar (atomic `os.replace`, same-filesystem temp); the ONE shared 6-step state machine (explicit-failure > ALIVE > stale > STARTING > STARTING-expiry); the `swing schwab status` line (`cli_schwab.py` `render_status`; `isascii()` assertion scoped to the NEW line only -- existing lines already emit em dashes at `:829/831`); the WEB HEALTH BADGE (field on `BaseLayoutVM` + the 16 leaf Family-B VMs behind a truthiness `{% if %}` guard; populated at the primary nav builders; a fan-out field-presence test + a route-render regression test).

---

## §2 LOCKs (BINDING; plan §E + the OQ dispositions)
- **L1** scope = A-3 + P14.N7 + the web badge ONLY. **L2** ZERO new `schwabdev.Client.*` call sites (reuse `construct_authenticated_client`; wrap existing `update_tokens`); NO re-anchor. **L3** NO swing schema (v23; ephemeral sidecar; `surface='pipeline'`; assert no `0024_*.sql`). **L4** production gate + inside-ladder sandbox short-circuit preserved (yfinance-only under sandbox). **L5** REUSE not re-implement (mirror `_install_pipeline_marketdata_caches`; wrap-not-replace the checker). **L6** audit + the `"Schwabdev"` capital-S `setLogRecordFactory` redaction intact; the header-key capture logs NAMES ONLY (no values). **L7** production-path tests (real `create_app`; real `ConnectionError`); NOT stubs. **L9** open-trade scope + TTL + provider-tag cooldown under a `threading.Lock`; **the ladder SWALLOWS the 429** (`marketdata_ladder.py:317`) -> the cooldown is provider_tag-driven; NEVER test the hook catching `SchwabRateLimitError`.
- **OQ recap:** OQ-1 sanctioned extension · OQ-2 full parity · OQ-3 `surface='pipeline'` · OQ-4 instance wrap · OQ-5 ephemeral sidecar · OQ-6 CLI + web badge (same sidecar, same state machine) · OQ-7 these 4 slices · OQ-8 single chain · OQ-9 sidecar bridges the process boundary · OQ-10 no-guess header-key capture.
- **P14.N7 = a cleanly-REMOVABLE guard** (the Phase-15 v3 upgrade deletes the checker; keep the wrap self-contained).

## §3 Production anchors (re-grep at STEP 0 per #2; the plan embeds these)
`_install_pipeline_marketdata_caches` (`runner.py:305`, install `:465-466`); web caches in `create_app` body (`app.py:188-189`); `get_or_fetch(*, ticker, window_days=180)` keyword-only; ladder swallows 429 at `marketdata_ladder.py:317`; `circuit_breaker_cooldown_seconds=60`; `SchwabConfigMissingError` (`schwab/client.py:314`); credential resolution via `resolve_credentials_env_or_prompt`; `schwab_api_calls.surface` CHECK `('pipeline','cli','trade_entry','trade_exit')` (`0020*.sql:338`); `rate_limit_remaining` extracted at `marketdata.py:101-144`; the Jinja env is default-Undefined (`app.py:91`, NOT StrictUndefined) -> the badge truthiness guard is render-safe.

## §3.1 Forward-binding lessons (honor)
All hook state under a `threading.Lock`; the seed call must NOT advance the heartbeat; `STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL`; the checker startup-race is the 1 accepted residual (document, do not fully close); `importlib.metadata.version` for the version guard (no Client construction in tests).

---

## §4 Codex SINGLE chain (OQ-8; run to convergence; persist prompt+response)
**Watch items:** L2 stays green (zero new call sites); NO schema (sidecar ephemeral; `surface='pipeline'`); the web-badge base-VM fan-out (every base-layout VM + a shared helper; the shared-`base.html.j2` gotcha); the sidecar cross-process correctness + the 6-step render precedence + the `STALE_THRESHOLD > HEARTBEAT` invariant; the provider_tag-driven cooldown (NOT hook-catches-429); the L9c header-key capture (names only; no guessed name; redaction-safe); production-path tests (L7); the daily-bar `(year,N,daily,1)` footgun; the `"Schwabdev"` redaction intact; P14.N7 cleanly-removable. **If a finding needs a schema change or a new `schwabdev.Client.*` call site, STOP + escalate.**

## §5 Operator-witnessed gate (plan §I; BINDING)
- **S1** fast suite + ruff green (baseline + ~32; READ the actual numbers -- no false-green). **S2** schema unchanged (v23; no `0024`; assert no new `chart_renders`/domain writes). **S3** L2 source-grep green. **S4** A-3 production-path wiring test (ladder hooks installed under production; yfinance fallthrough under sandbox). **S5** P14.N7 DNS-failure-survival + the sidecar state machine + the `swing schwab status` checker-liveness line (operator-confirmed). **S6 (BINDING browser leg)** the WEB HEALTH BADGE renders alive/stale/degraded in a real browser (operator-witnessed). **S7 (optional)** production smoke incl. the OQ-10 header-key capture (operator reads the logged header names).
- **If a `swing web` server is launched for S6:** run the BRANCH server from the worktree (`python -m swing.cli web --port 8081`); kill by PID via `Get-NetTCPConnection -LocalPort 8081` -> `Stop-Process -Force` + verify the port is free (`feedback_taskstop_does_not_kill_detached_server`). **After merge: re-run the fast suite ON THE MERGED HEAD + READ it** (`feedback_no_false_green_claim`); reinstall `swing` from main (`pip install -e . --no-deps`).

## §6 Done criteria
All 4 slices shipped; Codex single chain CONVERGED (`.copowers-findings.md` evidences it); fast suite green (baseline + ~32); ruff clean; ZERO Co-Authored-By (`%(trailers)`); NO migration (v23) + ZERO new `schwabdev.Client.*` call sites (L2 green); the redaction + audit discipline intact; P14.N7 cleanly-removable; return report complete; branch pushed; ready for orchestrator QA + the operator S1-S7 gate.

## §7 Return report shape
Final HEAD + per-commit Codex-round attribution; the single chain + convergent shape (cite `.copowers-findings.md` incl. the final `### Verdict`); per-slice completion; test surface (baseline + ~32 actual); LOCK + OQ verbatim verification; Codex Majors accepted (ZERO preferred); production-anchor re-grep results; schema verdict (NO change); the L9c header-key-capture outcome (OQ-10); the web-badge fan-out result; the gate readiness (S1-S7 incl. the browser leg); L2 verification (source-grep green); cumulative gotcha application; worktree teardown status; ZERO Co-Authored-By confirmation; CLAUDE.md status-line refresh draft; operator-gate handback.

## §8 OUT OF SCOPE
The Phase-15 schwabdev v3 upgrade (do NOT install/assume v3); a `'web'` surface enum (v24 -- reuse `'pipeline'`); a persisted health table (use the ephemeral sidecar); any new `schwabdev.Client.*` call site / new endpoint (L2); the close-out polish batch + B-7 + the close-out review; Phase 15+.

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `phase14-sub-bundle-5-5-schwab-executing-plans`. Dir `.worktrees/phase14-sub-bundle-5-5-schwab-executing-plans/`. **Branch from main HEAD `94d0b88`** (or later if the orchestrator states a newer HEAD in the inline prompt).
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).
- **Codex chain count:** ONE chain to convergence via the WSL fallback (verify `command -v codex`; transcript -> `.copowers-findings.md`).
- **Schwabdev target:** 2.5.1.

---

*End of brief. Phase 14 Sub-bundle 5.5 executing-plans dispatch -- execute the LOCKed 1821-line plan across 4 serial slices (A-3 full-parity web ladder install + L9 gates; L9c header-key capture; P14.N7 checker wrap + liveness; sidecar + CLI line + web health badge); ~32 tests; schwabdev 2.5.1; NO schema (v23 held); ZERO new schwabdev.Client.* call sites (no L2 re-anchor); P14.N7 a cleanly-removable guard. ONE Codex chain to convergence (persist prompt+response). The gate is test/CLI-driven + a BINDING browser leg for the web badge (S6); after merge re-run the suite on the merged HEAD + reinstall swing. OUTPUT: production code + tests + return report.*
