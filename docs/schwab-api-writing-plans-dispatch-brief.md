# Schwab API — writing-plans dispatch brief

**Audience:** Fresh Claude Code instance dispatched as the Schwab API integration writing-plans implementer. No prior conversation context.

**Mission:** Convert the Schwab API integration brainstorm spec into an executable implementation plan via `copowers:writing-plans` (which wraps `superpowers:writing-plans` with adversarial Codex MCP review). Output is a single plan file at `docs/superpowers/plans/<YYYY-MM-DD>-schwab-api-integration-plan.md` decomposed into sub-bundles that the orchestrator subsequently dispatches via `copowers:executing-plans` (one dispatch per sub-bundle).

**Expected duration:** ~5-9 hr planning + ~2-3 hr Codex convergence. Total ~6-9 hr (matches Phase 9 + Phase 10 writing-plans precedents: 5-6 Codex rounds + 2000-2500 line plan).

---

## §0 Inputs

### §0.1 Spec (canonical scope source)

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- **Spec status:** 5 Codex rounds → NO_NEW_CRITICAL_MAJOR (1C+21M+12m all RESOLVED inline; ZERO ACCEPT-WITH-RATIONALE — matches Phase 10 cleanest-arc precedent). 939 lines.
- **Spec produces** (per §1.1): V1 architecture for Schwab Developer Portal API integration — OAuth 2.0 auth flow + per-environment sidecar token storage + Trader API + Market Data API endpoint catalog + pipeline step ordering + `schwab_api_calls` audit-trail surface + operator setup runbook + production-only domain writes (sandbox = verification-only) + V1 INCLUDE branch for `schwab_api > yfinance` market-data ladder.
- **Spec deliberately does NOT produce** (per §1.2): schema SQL, CHECK constraints, indexes, FK cascade rules, Python class definitions, test code, CLI command body code, sub-bundle decomposition. **THAT IS WRITING-PLANS' JOB.**
- **Spec format precedent the implementer should mirror in plan format:** `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (Finviz integration plan — closest already-shipped API integration precedent) + `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (largest multi-source plan, 2257 lines, 5 sub-bundles).

### §0.2 Project state at dispatch time

- **HEAD on `main`:** `f308d93` (post-brainstorm-triage housekeeping + Q1 disposition + deviation-framing clarifications).
- **Test count:** **3287 fast passing on main** (1 skipped — Task 7.3 operator-only flag-classifier fixture; 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions, banked separately). Verified at `9d4edfc` per CLAUDE.md status; brainstorm dispatch added zero tests (spec-only).
- **Test runtime:** ~63s wall-clock at `-n auto` default (post-infra-bundle xdist integration; 6.56× from prior 415s baseline). Operator override: `pytest -n 0` for debug.
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 9 + Phase 10 + infra bundle).
- **Schema version:** **v17.** Locked since Phase 9 Sub-bundle A `6c8f3a9` 2026-05-12; preserved through Phase 10 V1. **Schwab arc lifts the §A.0 ZERO-new-schema LOCK that held through Phase 10 V1 — `EXPECTED_SCHEMA_VERSION` expected to bump to 18 at Sub-bundle A migration step. This is a HARD CHANGE from prior 5 dispatches.**

### §0.3 Operator-confirmed triage of spec §10 open questions (BINDING for plan scope)

The spec enumerated 17 open questions in §10. Orchestrator triaged with operator on 2026-05-13 (per `docs/phase3e-todo.md` 2026-05-13 entry "Schwab API integration brainstorm SHIPPED"). **An 18th question (build-vs-buy) was missed by the brainstorm + surfaced post-triage; operator decided on 2026-05-13 (see §0.3a below).** **All dispositions LOCKED for writing-plans scope:**

| # | Spec §10 question | Triaged disposition (BINDING) |
|---|---|---|
| **Q1** | Schwab Developer Portal app status | **Production-tier approved (operator-confirmed).** V1 disposition: production-only. Sandbox registration deferred to Task 0.b (operator decides at executing-plans whether sandbox cassette-recording adds value depending on whether Schwab requires distinct sandbox-app registration vs unified credentials). |
| **Q2** | Token storage encryption | **V1 plaintext** (Finviz precedent + risk disclosed in spec §3.2.2 + §5). V2 hardening (`keyring` / DPAPI) tracked as high-priority post-V1 follow-up — out of this plan's scope. |
| **Q3** | Multi-account support | **V1 single-primary-account.** V2 multi-account = separate dispatch (out of plan scope). |
| **Q4** | Streaming vs batch-poll | **V1 batch-poll only.** V2 streaming = out of plan scope. |
| **Q5** | Operator UI | **V1 CLI-only** (Finviz precedent). V2 web form = out of plan scope. |
| **Q6** | Schwab inception-CSV ingestion | **Separate dispatch** (per phase3e-todo 2026-05-12). Out of plan scope. |
| **Q7** | TOS CSV deprecation timing | **Stays as V1 fallback.** V2 deprecation = out of plan scope. |
| **Q9** | Cash-basis manual snapshot retention | **Yes, retained.** Source-ladder resolves at read time; manual snapshot CLI continues to work. |
| **Q10** | Pipeline step ordering | **AFTER `_step_recommendations`, BEFORE `_step_charts`** per spec §3.4.2. |
| **Q11** | Market-data ladder V1 INCLUDE vs EXCLUDE | **V1 INCLUDE** per spec §1.4 + §3.8 INCLUDE branch. Plan implements §3.8 design. |
| **Q16** | `schwab_account_hash` column on `account_equity_snapshots` | **V1 ADD** (NULL-permissible; forward-prep multi-account V2; cheap insurance per spec §10.16 default). |
| **Q8** | Sandbox/production HTTP-layer differentiation | **DEFERRED to Task 0.b.** Per-env sidecar LOCKED in spec §3.2.2; HTTP-layer (base URL / path / scope / TTL) operator-paired live verification at executing-plans Task 0.b. |
| **Q12** | Premium-tier Market Data endpoint access | **DEFERRED to Task 0.b.** Default V1 = default-tier (delayed quotes); Task 0.b verifies endpoint set vs operator's actual subscription tier. |
| **Q13** | OAuth callback localhost vs paste | **DEFERRED to Task 0.b.** Localhost default + `--paste` flag fallback if Task 0.b reveals env block. Plan implements both code paths. |
| **Q14** | OAuth scope-string composition | **DEFERRED to Task 0.b.** Synthesize default; operator-pair verification of exact format. |
| **Q15** | Refresh-token rotation behavior | **DEFERRED to Task 0.b.** Design handles both rotate-every and rotate-near-expiry per spec §3.2.3; cassette + test fixtures need known canonical case from operator-witnessed verification. |
| **Q17** | Market Data API rate limits independent of Trader API | **DEFERRED to Task 0.b.** Synthesize "~Trader API limits or looser"; flag verification gate. |

**Plan §A posture:** document each Q1-Q17 disposition explicitly per spec-question, citing the triage record (this brief §0.3 + the phase3e-todo entry). Q8 + Q12 + Q13 + Q14 + Q15 + Q17 must be flagged as **§D open questions for orchestrator (binding for executing-plans Task 0.b)** so the executing-plans implementer halts at Task 0.b until operator-paired live verification completes.

### §0.3a Q18 — build-vs-buy (LOCKED: COA B = `schwabdev`)

**Brainstorm-spec gap that orchestrator missed at first triage.** The spec implicitly chose COA C (roll our own) by enumerating `swing/integrations/schwab/` sub-package + `SchwabClient` + sidecar JSON token storage + custom file-lock + custom OAuth flow as the V1 architecture, without ever explicitly comparing against the two community-maintained Python wrappers it lists in §12 references (`schwab-py`, `schwabdev`). Operator surfaced the gap post-triage; orchestrator researched both libraries' OAuth implementations + presented tradeoff matrix; operator confirmed **COA B (use `schwabdev`)** on 2026-05-13.

**LOCKED disposition:**

- **Library:** [`schwabdev`](https://github.com/tylerebowers/Schwabdev) (Tyler Bowers; tylerebowers/Schwabdev) added as project dependency.
- **Wrapping discipline:** new `swing/integrations/schwab/` sub-package wraps `schwabdev.Client` thinly to enforce project gotcha discipline:
  - Production-only domain writes gate per spec §3.6.3 (caller-side enforcement around `record_snapshot()` + `run_schwab_reconciliation()`).
  - `schwab_api_calls` audit-row INSERT/UPDATE around schwabdev calls per spec §3.6.1.
  - Source-ladder write integration via `record_snapshot(source='schwab_api', ...)` + reconciliation_run INSERT (Phase 9 Sub-bundle C consumers per §0.4 below).
  - Token-redaction audit test on schwabdev's logger surface (verify schwabdev does NOT log tokens; one known caveat: schwabdev's `tokens.py` line ~338 logs `response.text` on auth failure which could include token-related error details — wrap-side verification required).

**Why COA B over COA A or C** (per orchestrator research findings; full table in phase3e-todo 2026-05-13 entry "Schwab API Q18 build-vs-buy disposition"):

- **schwabdev's OAuth implementation is materially better-designed than schwab-py's:** SQLite with `BEGIN EXCLUSIVE` cross-process atomic storage (vs schwab-py's no-locks JSON); explicit `if new_refresh_token: self.refresh_token = new_refresh_token` rotation handling (vs schwab-py's opaque authlib passthrough); hybrid lazy + proactive refresh strategy with separate 61s access threshold + 3630s refresh threshold (vs schwab-py's lazy-only with 300s leeway); optional Fernet encryption-at-rest available (vs schwab-py plaintext default).
- These exactly match what spec §3.2.2-3.2.4 was going to design from scratch in COA C.
- COA C would have re-implemented OAuth + token storage + refresh + concurrency from scratch — high implementation risk for security-critical code.
- COA A (`schwab-py`) has battle-tested maturity (~1.5k stars; Alex Golec tda-api lineage) BUT its OAuth implementation has design gaps schwabdev does not (no concurrency protection; opaque rotation; lazy-only refresh).

**Spec sections that COA B SUPERSEDES — plan author re-derives in plan §A or §H:**

| Spec section | COA C posture (what spec says) | COA B posture (what plan implements) |
|---|---|---|
| §3.1 module layout | `swing/integrations/schwab/` sub-package with custom `SchwabClient` | `swing/integrations/schwab/` sub-package with thin wrapper around `schwabdev.Client` |
| §3.2.1 setup flow | Two variants: `--callback localhost` (one-shot HTTPS listener on 127.0.0.1:8765) + `--callback paste` | **Paste-back only V1** (schwabdev does not ship localhost listener; operator pastes once at `swing schwab setup` per env). Q13 disposition simplifies — paste-back is the V1 path; localhost is a V2 candidate if operator surfaces friction. |
| §3.2.2 token storage | Per-environment sidecar JSON file at `%USERPROFILE%/swing-data/schwab-state.{sandbox,production}.json` | Per-environment SQLite DB at `%USERPROFILE%/swing-data/schwab-tokens.{sandbox,production}.db` (path passed to `Tokens(tokens_db=...)`); schwabdev manages schema + atomicity. |
| §3.2.3 token-refresh | Lazy-on-first-API-call with 60s proactive safety margin; file-lock during refresh | Schwabdev's hybrid lazy (per-request `update_tokens()`) + proactive (async `_checker()` every 30s) + 61s/3630s separate thresholds. **Better than spec.** |
| §3.2.4 concurrency | Custom file-lock cross-platform shim (`msvcrt.locking` Windows / `fcntl.flock` POSIX) | Schwabdev's `threading.RLock` (in-process) + SQLite `BEGIN EXCLUSIVE` (cross-process). **Custom file-lock shim NOT NEEDED.** Plan §B file map removes the file-lock module. |
| §3.2.5 revocation | `swing schwab logout` revokes via Schwab endpoint + atomically renames sidecar JSON to `*.deleted-<ts>` + unlinks | Same operator UX (`swing schwab logout`); implementation deletes the SQLite DB or wipes its rows — plan-author picks. |
| §3.3.1 endpoint catalog (Trader API) | URL pattern + HTTP method + headers + params + response shape per endpoint | We call schwabdev `Client.account_details(...)`, `Client.account_orders(...)`, `Client.transactions(...)` etc. Plan §E enumerates schwabdev method signatures + return shapes (mirror Finviz §E format adapted to library calls); raw HTTP details deferred to schwabdev's docs. |
| §3.3.2 endpoint catalog (Market Data API) | Same per-endpoint detail | Same — call schwabdev `Client.quotes(...)`, `Client.price_history(...)` etc. |
| §3.5 CLI surface | `swing schwab {setup, refresh, fetch, status, logout}` | Same CLI surface; setup wraps schwabdev's auth flow (paste-back); refresh wraps schwabdev's `update_tokens(force_refresh_token=True)`; status reads from `schwab_api_calls` audit + schwabdev's `Tokens` DB metadata. |
| §5 token redaction | Custom `_suppress_transport_debug_logs` context manager + cassette `filter_headers=['authorization']` + `filter_query_parameters` + `filter_post_data_parameters` + custom body redactor + sentinel-token-leak audit test | Same cassette discipline (still own `pytest-recording` config). DEBUG-log suppression context manager STILL applies (urllib3 logs the request URL regardless of which library issues it). Sentinel-token-leak audit test STILL required + adds verification that schwabdev's own logger does not leak tokens (one known caveat: line ~338 logs `response.text` on auth failure). Plan §J CLAUDE.md additions document the schwabdev wrapping discipline. |
| §3.6.3 production-only domain writes | `cfg.integrations.schwab.environment` gates `record_snapshot()` + `run_schwab_reconciliation()` | **UNCHANGED.** Caller-side gate before invoking schwabdev calls + before invoking source-ladder writes. Discriminating tests unchanged. |
| §3.6.1 audit lifecycle (`schwab_api_calls`) | INSERT in_flight → schwabdev call → UPDATE final status + linked rows | **UNCHANGED.** Wrap each schwabdev call with INSERT-then-UPDATE pattern. |
| §3.7 source-ladder write path | INHERITED from Phase 9 Sub-bundle C; no re-design | **UNCHANGED.** schwabdev returns parsed response data; we map to `record_snapshot(source='schwab_api', ...)` + reconciliation_run INSERT verbatim. |
| §3.8 market-data ladder | yfinance fallback discipline preserved per §3.8.4; Schwab-via-our-client first | **UNCHANGED in design.** Schwab-via-schwabdev first; yfinance fallback same. Persistence shape A/B/C decision unchanged. |
| §10 Q2 token encryption | V1 plaintext; V2 keyring/DPAPI | **OPTIONAL Fernet encryption now AVAILABLE V1 if operator wants.** Schwabdev accepts `encryption=<key>` constructor parameter; operator-provided 32-byte URL-safe base64 key. Plan §A flags this as a now-V1-feasible upgrade — orchestrator can take the V1 plaintext default OR operator can elect Fernet at writing-plans review. **Plan-author recommendation: V1 plaintext per spec disposition + V2 Fernet path documented.** |
| §10 Q13 callback localhost vs paste | Localhost default + `--paste` flag fallback | **Paste-only V1 (schwabdev constraint).** Plan §A documents the deviation from spec disposition; operator confirmed acceptable post-Q18 decision (paste-once-at-setup is operator-paced, not load-bearing). |
| §10 Q15 refresh-token rotation | Design handles both rotate-every and rotate-near-expiry; cassette case from operator-witnessed verification | **Schwabdev handles rotation explicitly** (`if new_refresh_token: self.refresh_token = new_refresh_token` at tokens.py:207). Operator-paired Task 0.b verification simplified — observe whether Schwab rotates + verify schwabdev persists the new token + record one cassette per case observed. |

**Spec sections UNAFFECTED by COA B** (plan implements per spec verbatim):

- §3.4 pipeline integration architecture (steps + ordering + failure tolerance + concurrency exclusion via `SchwabPipelineActiveError`).
- §3.6 audit trail (`schwab_api_calls` table; INSERT/UPDATE lifecycle).
- §3.6.2 audit-write surface boundary (pipeline + CLI synchronous; web-page-render explicitly-unaudited).
- §3.6.3 production-only domain writes.
- §3.7 source-ladder write path.
- §3.8 market-data ladder design (V1 INCLUDE branch).
- §4 schema candidates (`schwab_api_calls` table + ALTERs).
- §6 failure-mode catalog.
- §7 operator setup flow + cycle-checklist.
- §9 watch items.

**New plan §B addition:** `pyproject.toml` adds `schwabdev>=<version>` to `[project.dependencies]` (NOT dev-extras — schwabdev is a runtime dependency for the integration). Plan author picks pinned version + checks for any conflicting transitive deps (`requests` likely; verify version range).

**New plan §K verification gate:** schwabdev's own logger output verified token-redaction-safe at integration-test level (sentinel-token via DEBUG log capture; assert sentinel absent from all log records including schwabdev's loggers).

### §0.4 Phase 9 + Phase 10 source-ladder consumer (BINDING — DO NOT re-design)

Per spec §1.3 #1 + §3.7: the source-ladder write path is INHERITED, NOT RE-DESIGNED. Plan must consume:

- `swing/data/repos/account_equity_snapshots.py:_SOURCE_PRECEDENCE` (line 38) — `{schwab_api: 0, tos_csv: 1, manual: 2}` already encoded.
- `swing/data/repos/account_equity_snapshots.py:get_latest_snapshot_on_or_before` (line 130) — `with_provenance=True` mode already returns `(winner, suppressed)` for source-ladder UI rendering.
- `swing/trades/account_equity_snapshots.py:record_snapshot` (line 66) — accepts `source: str` parameter; UPSERT semantics on `(snapshot_date, source)` already shipped; `CallerHeldTransactionError` discipline already in force.
- `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:194 + 332` — `reconciliation_runs.source` and `account_equity_snapshots.source` CHECK enums already permit `'schwab_api'`.

**Plan acceptance criteria:** every Schwab API write path consumes these helpers verbatim (`record_snapshot(source='schwab_api', ...)` + direct INSERT to `reconciliation_runs` with `source='schwab_api'`). NO new source-ladder logic. NO new precedence-resolution code.

### §0.5 Phase 9 + Phase 10 arc lessons inherited (BINDING for writing-plans)

The 11 forward-binding lessons enumerated in `docs/phase10-writing-plans-dispatch-brief.md` §0.3 + the gotchas added since (CLAUDE.md gotchas section through `9d4edfc`) all apply. Of particular relevance for Schwab API plan:

1. **`__post_init__` validator pattern on all new dataclasses** (Phase 9 lock). New Schwab-API dataclasses (`SchwabApiCall`, `SchwabOAuthState`, etc.) must reject NaN/inf/out-of-range values at construction.
2. **Service-layer transaction discipline** — caller MUST NOT hold open transaction; service owns BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject-don't-auto-detect. Schwab integration introduces NEW write paths (snapshot + reconciliation_run + audit-row); ALL must follow this discipline.
3. **NO `INSERT OR REPLACE` on FK-referenced or audit-trail tables.** `schwab_api_calls` is audit-trail; UPSERTs (if any) MUST be SELECT-then-UPDATE-or-INSERT.
4. **Server-stamping discipline at handler entry.** No CLI hidden inputs for `recorded_at` / `ts` / etc. — server-stamps on entry.
5. **Composition-surface enumeration via `^def` grep, NOT memory-enumerate.** Schwab integration touches multiple call sites (`_step_finviz_fetch` ordering pattern + new `_step_schwab_*` siblings + CLI surface + cache layer for market-data ladder).
6. **Empirical-verification of brief assertions before locking.** Spec is canonical; verify all section references against actual spec text; do NOT memory-summarize.
7. **HTMX browser-only failure surfaces.** Plan does NOT introduce new HTMX surfaces (Q5: V1 CLI-only); BUT if any web-render-side surface emerges (e.g., `swing schwab status` rendered in dashboard), apply the lesson family.
8. **Test fixtures exercising `write_user_overrides` MUST monkeypatch USERPROFILE + HOME** — spec §3.2.2 stores tokens in sidecar JSON file (NOT user-config.toml) so this lesson does NOT directly apply, BUT any test fixture that writes `cfg.integrations.schwab.environment` to user-config DOES require the monkeypatch.

### §0.6 Empirical schema verification (plan §A locks)

The plan §A pre-plan recon MUST verify the following empirically before locking the schema posture:

1. **`schwab_api_calls` table** is NEW (not yet in v17 schema). Verify: `grep -i schwab swing/data/migrations/*.sql` returns ONLY the CHECK enum mentions (lines 194 + 332 of 0017); no table by this name.
2. **`account_equity_snapshots.schwab_account_hash` column** is NEW. Verify: `grep schwab_account_hash swing/data/migrations/0017_*.sql` returns nothing.
3. **`reconciliation_runs.schwab_api_call_id` column** is NEW. Verify: same grep returns nothing.
4. **Migration `0018_schwab_integration.sql`** is the next available migration number. Verify: `ls swing/data/migrations/00*.sql | tail` shows 0017 as latest.
5. **`EXPECTED_SCHEMA_VERSION = 17`** in `swing/data/db.py`. Verify: `grep "EXPECTED_SCHEMA_VERSION" swing/data/db.py`.
6. **The market-data ladder persistence** (per spec §3.8.2) is one of three shapes — A (parquet-per-(ticker, provider)) / B (SQLite table) / C (provider column inside parquet). Plan §A picks ONE + justifies. Default per spec §3.8.2: Shape A.
7. **No FK CASCADE risk** introduced by `0018_*.sql` ALTERs. Verify: schwab_account_hash + schwab_api_call_id are nullable + no ON DELETE CASCADE.

**Migration discipline:** spec §A.13 + Finviz §A.13 atomicity discipline applies — single CREATE TABLE + single ALTER ADD COLUMN per existing-table + single UPDATE schema_version. Atomic via `_apply_migration` per CLAUDE.md gotcha "executescript() implicit COMMIT" — already-shipped runner handles this.

### §0.7 Sub-bundle decomposition expected

Spec §1.4 + spec §3.8 + Phase 9 precedent suggests decomposition into **3-5 sub-bundles** (writing-plans implementer picks final shape):

- **Likely Sub-bundle A: Auth + token storage + CLI setup/refresh/logout/status.** New module `swing/integrations/schwab/` sub-package; OAuth flow; sidecar JSON file write/read with file-lock; per-env sidecar; CLI commands wired. Migration 0018 lands here (atomic single-file: `schwab_api_calls` table + `account_equity_snapshots.schwab_account_hash` + `reconciliation_runs.schwab_api_call_id` ALTERs + UPDATE schema_version 17→18). Test corpus: cassette-based unit tests for auth flow + token-redaction audit + sidecar file-lock + CLI surface tests.
- **Likely Sub-bundle B: Trader API endpoints + `_step_schwab_snapshot` + `_step_schwab_orders` pipeline integration + reconciliation source-ladder write.** Uses Phase 9 `record_snapshot(source='schwab_api')` + `reconciliation_runs` INSERT. Test corpus: cassette-based pipeline-step tests + integration test mirroring Phase 9 Sub-bundle E E2E pattern + reconciliation discrepancy emit tests.
- **Likely Sub-bundle C: Market Data API endpoints + `PriceCache` / `OhlcvCache` source-ladder rewrite (V1 INCLUDE branch per Q11).** Persistence shape A/B/C decision lands here per spec §3.8.2. yfinance fallback discipline preserved per spec §3.8.4. Test corpus: cassette-based market-data tests + cache layer source-ladder tests + yfinance-fallback-on-empty-API tests.
- **Likely Sub-bundle D: Audit trail + observability + `swing schwab status` CLI command.** `schwab_api_calls` INSERT/UPDATE lifecycle (in-flight + linked-row UPDATE per spec §3.6.1); CLI status subcommand renders recent rows. Test corpus: audit-row lifecycle tests + status CLI tests.
- **Likely Sub-bundle E: Polish + cycle-checklist update + CLAUDE.md additions + handoff to next dispatch.** Operator setup runbook documentation; daily-cycle integration; failure-recovery flow. Test corpus: integration-test polish + documentation-link verification.

**Plan author picks the actual count + final shape.** May be 3 (auth+snapshot bundled / market-data / polish) or 5 (auth / snapshot+orders / market-data / audit / polish). Justify the chosen shape in plan §0.

### §0.8 Operator-attention items the plan MUST surface

Per spec capture-needs §8 + §10 — the writing-plans implementer MUST surface in plan §A or §D:

- **Brief watch-item #17 reversal NORMAL TRIAGE FLOW** (per phase3e-todo deviation-framing clarification). Spec §3.2.4 + §3.4.5 + §10 inherit `SchwabPipelineActiveError` hard exclusion as Codex-discovered upgrade from spec author's R0 file-lock-only design. Plan implements the inherited design; no further triage needed.
- **Production-only domain writes (spec §3.6.3) — discriminating-test pattern enumerated.** Plan acceptance criteria for the domain-write gating MUST include a discriminating test that asserts `record_snapshot()` raises (or no-ops with audit-only) when `cfg.integrations.schwab.environment != 'production'`. Plan author firms up the exact contract.
- **12 firm-up items per spec capture-needs (writing-plans dispatch):** §3.3.1 endpoint shapes via Task 0.b; §3.3.1 scope strings via Task 0.b; §3.5 CLI subcommand body design; §3.6 `schwab_api_calls` DDL; §3.2.4 file-lock cross-platform shim; §3.2.1 callback HTTPS-vs-HTTP; §7 cycle-checklist updates; test fixtures + Task 0.b runbook; integration test E2E mirroring Phase 9 Sub-bundle E pattern; market-data persistence shape A/B/C choice; account_hash column V1/V2 (LOCKED V1 ADD per Q16); `schwab_account_hash` + `reconciliation_runs.schwab_api_call_id` ALTERs.

---

## §1 Skill posture

- Invoke **`copowers:writing-plans`** (which wraps `superpowers:writing-plans` with adversarial Codex MCP review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:executing-plans` or `superpowers:test-driven-development` — plan-only.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; single plan-doc commit on `main`.
- DO NOT invoke `superpowers:using-superpowers` again — you've already been oriented to skills via your session-start system reminder.

---

## §2 Plan scope (in scope)

Produce a plan at `docs/superpowers/plans/<YYYY-MM-DD>-schwab-api-integration-plan.md` (where date is plan-completion date) covering:

### §2.1 — §A resolved-during-planning items
- Each spec §10 disposition (per §0.3 above) cited explicitly in plan §A.
- Schema verification outcomes (per §0.6 above).
- Sub-bundle decomposition rationale (per §0.7 above; final count + per-bundle scope).
- Source-ladder consumer inheritance contract (per §0.4 above).
- Phase 9 + Phase 10 lesson inheritances acknowledged (per §0.5 above).

### §2.2 — §B file map (CREATE / MODIFY / READ-ONLY)
- New module: `swing/integrations/schwab/` sub-package with sub-modules per concern (auth, client, pipeline_step, cache_ladder if Q11 INCLUDE, etc.) — final count + names plan-author picks.
- New migration: `0018_schwab_integration.sql` (canonical SQL in plan §C).
- New repo: `swing/data/repos/schwab_api_calls.py`.
- New service: `swing/integrations/schwab/oauth.py` (or similar — sidecar file management + token refresh).
- Modifications: `swing/cli.py` (+`@main.group("schwab")`); `swing/pipeline/runner.py` (+`_step_schwab_snapshot` + `_step_schwab_orders`); `swing/data/db.py` (+ EXPECTED_SCHEMA_VERSION bump 17→18); `swing/config.py` + `swing.config.toml` (+`[integrations.schwab]` section); `pyproject.toml` (+`pytest-recording` if not yet there + any new auth deps).
- Read-only: `swing/data/repos/account_equity_snapshots.py`, `swing/trades/account_equity_snapshots.py`, `swing/trades/reconciliation.py`, `swing/journal/tos_import.py`, all Phase 6 + Phase 7 + Phase 8 entities (out of scope per phase isolation).

### §2.3 — §C migration 0018 SQL canonical reference
- Single CREATE TABLE `schwab_api_calls` (14 columns per spec §4.1).
- Single ALTER `account_equity_snapshots ADD COLUMN schwab_account_hash TEXT` (NULL-permissible).
- Single ALTER `reconciliation_runs ADD COLUMN schwab_api_call_id INTEGER` (NULL-permissible; FK candidate per spec §4.3 — plan picks FK or no-FK).
- UPDATE schema_version SET version = 18.

### §2.4 — §D open question for orchestrator (binding for executing-plans)
- The 6 Q8 / Q12 / Q13 / Q14 / Q15 / Q17 deferred-to-Task-0.b items per §0.3 above. Plan §D MUST list them with exact verification steps for executing-plans Task 0.b.

### §2.5 — §E endpoint reference (synthesized; verify at executing-plans Task 0.b)
- Per spec §3.3.1 + §3.3.2 — for each endpoint:
  - URL pattern + HTTP method.
  - Required headers.
  - Query/path parameters.
  - Expected response shape (JSON; project-consumed fields only).
  - Failure modes (401 / 403 / 429 / 5xx).
- `[VERIFY]` tag on any synthesized shape per spec §11 PENDING bucket.

### §2.6 — §F filename + file-lock convention (sidecar JSON)
- Sidecar file paths: `%USERPROFILE%/swing-data/schwab-state.{sandbox,production}.json`.
- File-lock cross-platform shim per spec §3.2.4 (Windows: `msvcrt.locking` or `portalocker` library; POSIX: `fcntl.flock`).
- Atomic write semantics (mirror Finviz §A.13 shadow-promote pattern; or simpler since sidecar is single-file per env).

### §2.7 — §G cassette runbook (operator/implementer)
- Mirror Finviz `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` §G.
- Per-endpoint cassette recording steps (operator-paired with real tokens).
- Token redaction at record time per spec §5 (filter_headers + filter_query_parameters + filter_post_data_parameters).
- Re-recording trigger: Schwab upstream changes → live test fails → operator re-records per runbook.

### §2.8 — §H algorithm spec (per pipeline step + per cache-layer ladder)
- `_step_schwab_snapshot`: full algorithm with shadow-promote-then-audit per spec §3.4.3 + §3.6.1.
- `_step_schwab_orders`: full algorithm.
- Market-data ladder (V1 INCLUDE branch): cache-layer integration into `_step_evaluate` + `_step_charts` per spec §3.8.5.

### §2.9 — §I cycle-checklist update (Task X binding spec)
- `docs/cycle-checklist.md` operator daily flow updates per spec §7.
- One-time setup steps (operator runs `swing schwab setup` once per environment).
- Daily flow updates (Schwab snapshot + orders auto-fetch).

### §2.10 — §J CLAUDE.md additions (Task X binding spec)
- Schwab token storage gotcha (sidecar JSON file location; per-env files; file-lock discipline).
- Schwab cassette staleness runbook pointer.
- Schwab production-only domain writes gotcha (sandbox = verification-only).
- Schwab CLI vs pipeline concurrency exclusion (`SchwabPipelineActiveError` mirror of `FinvizPipelineActiveError`).

### §2.11 — §K verification gates (executing-plans implementer; binding)
- Per-sub-bundle gate criteria.
- Operator-witnessed gate surfaces (CLI + pipeline + sandbox vs production behavior; multi-surface).
- Final integration test gate (E2E mirror Phase 9 Sub-bundle E pattern).

### §2.12 — §Tasks (per sub-bundle, with checkbox tracking)
- Each sub-bundle gets its own §Tasks subsection.
- Tasks numbered T-A.1, T-A.2, ... T-B.1, T-B.2, ...
- Each task has: scope description, files touched, test files added (count estimate), discriminating test patterns, acceptance criteria.
- Mirror Phase 9 Sub-bundle plan task structure (`docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`).

---

## §3 OUT OF SCOPE (do not do)

- **Code drafting** — no Python class definitions; no test code; no CLI command body code. The plan describes intent + algorithm + acceptance criteria + test patterns ONLY. Code drafting is executing-plans territory.
- **Sub-bundle execution** — that's per-sub-bundle executing-plans dispatch. Plan produces the plan; orchestrator dispatches per sub-bundle.
- **Re-litigating spec decisions** — spec §3 architecture is locked; plan firms up implementation. If plan-author disagrees with a spec decision, surface as plan §D open question for orchestrator review; do NOT silently override.
- **Re-litigating triaged dispositions** — Q1-Q17 dispositions per §0.3 above are operator-confirmed. Plan consumes verbatim.
- **Inception-CSV ingestion** (Q6 deferred to separate dispatch).
- **Multi-account support** (Q3 deferred to V2).
- **Order placement / cancellation** — explicit OUT-OF-SCOPE per spec §1.2 + §3.3.3.
- **Web UI for Schwab** (Q5 deferred to V2).

---

## §4 Binding conventions

- **Branch:** `main`. Single commit at end of writing-plans dispatch.
- **Commit timing (CRITICAL — clarification on prior brief contradiction):** **DEFER COMMIT until adversarial Codex review converges to NO_NEW_CRITICAL_MAJOR.** Do NOT commit at R0 (initial draft) and amend through rounds. The brainstorm dispatch's implementer flagged this clarification — the prior phrasing "single commit + no amending" was internally contradictory for Codex iteration; the explicit rule is: work through all Codex rounds in working tree, commit ONCE after R5 (or convergence) lands, push history is clean single-commit with NO amends.
- **Commit message:** `docs(schwab-api): integration writing-plans implementation plan`. No Claude co-author footer. No `--no-verify`. No amending.
- **Plan location:** `docs/superpowers/plans/<YYYY-MM-DD>-schwab-api-integration-plan.md` where date is plan-completion date.
- **Plan format:** mirror `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (2257 lines; the most recent multi-sub-bundle plan). Section structure: §0 sub-bundle decomposition → §A resolved-during-planning → §B file map → §C migration SQL → §D open questions → §E endpoint reference → §F file conventions → §G cassette runbook → §H algorithm spec → §I cycle-checklist → §J CLAUDE.md → §K verification gates → §Tasks per sub-bundle.
- **Plan line target:** ~1500-2500 lines. Tight beats padded; if exceeding 2500, re-scope by deferring more Task 0.b verification details to executing-plans Task 0.b runbook.
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Default `MAX_ROUNDS=5`; if a 6th round produces ≤1 new Major + 0 new Critical, accept-with-rationale + document. Phase 10 writing-plans precedent: 6 rounds with operator override past default + ZERO ACCEPT-WITH-RATIONALE.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Source-ladder consumer inheritance verbatim.** Plan §A or §B explicitly cites consuming `record_snapshot(source='schwab_api', ...)` + `reconciliation_runs INSERT source='schwab_api'`. NO new source-ladder code paths.
2. **Production-only domain writes discriminating tests.** Plan acceptance criteria for the `cfg.integrations.schwab.environment` gate explicitly enumerates discriminating tests asserting `record_snapshot()` is gated when env != 'production'.
3. **Migration 0018 atomic landing.** Plan §C SQL is single-file CREATE TABLE + ALTER ADD COLUMN (×2) + UPDATE schema_version. Atomic per `_apply_migration` runner (CLAUDE.md gotcha discipline).
4. **`schwab_api_calls` audit lifecycle.** Plan §H + §Tasks enumerate the in-flight + linked-row UPDATE lifecycle per spec §3.6.1 — initial INSERT with `status='in_flight'`, UPDATE with final status + linked_snapshot_id / linked_reconciliation_run_id on completion.
5. **Token redaction inheritance from Finviz verbatim.** Plan §G cassette runbook + per-test acceptance criteria explicitly enumerate `filter_headers=['authorization']` + `filter_query_parameters` + `filter_post_data_parameters` + custom body redactor + sentinel-token-leak audit test pattern (mirror `tests/integrations/test_finviz_token_redaction_audit.py`).
6. **Per-env sidecar discipline.** Plan §F + §Tasks acceptance criteria explicitly cover per-env sidecar isolation (writes to `schwab-state.production.json` do NOT touch `schwab-state.sandbox.json` and vice versa).
7. **OAuth refresh-token rotation handled both ways.** Plan §H + §Tasks cover both rotate-every and rotate-near-expiry behaviors per spec §3.2.3 — store new refresh_token IF present in response.
8. **`SchwabPipelineActiveError` hard exclusion.** Plan §H + §Tasks enumerate the exclusion logic for `swing schwab fetch --snapshot/--orders/--all` while pipeline is in flight (mirror Finviz `FinvizPipelineActiveError` per spec §3.2.4 + §3.4.5).
9. **Empty-API-response handling.** Plan §H + §Tasks enumerate the append-or-fall-back pattern per CLAUDE.md gotcha — empty Schwab response does NOT clobber existing data; logs + records `schwab_api_calls.status='error'`.
10. **Market-data ladder persistence shape decision.** Plan §A picks Shape A/B/C per spec §3.8.2 + justifies + enumerates downstream impact (cache layer rewrite scope).
11. **`schwab_api_calls` audit-write surface boundary.** Plan §H + §Tasks explicitly enumerate that pipeline + CLI surfaces emit synchronous audit rows; web-page-render surface does NOT (logs-only V1 per spec §3.6.2).
12. **Sub-bundle decomposition rationale.** Plan §0 documents why N sub-bundles + per-bundle scope. Inter-bundle dependencies enumerated (e.g., Sub-bundle B depends on Sub-bundle A's auth flow being shipped). **COA B impact:** sub-bundle scopes shrink relative to spec §0.7 estimate — Sub-bundle A no longer designs OAuth from scratch; auth + token storage become "wrap schwabdev's `Tokens` class with our gotcha discipline." Plan-author re-estimates per-bundle scope under COA B.

12a. **COA B integration completeness.** Plan §A explicitly enumerates which schwabdev features we use vs which we ignore (e.g., `ClientAsync` vs sync `Client`; streaming `_checker` vs not; encryption-at-rest vs plaintext). Plan §H walks through each schwabdev call we make, what we wrap around it, and what we DON'T let it do (e.g., DO NOT use schwabdev's logging passthrough; install our own log filter).

12b. **schwabdev wrapping discipline acceptance criteria.** Plan §K + §Tasks acceptance criteria explicitly include: (a) sentinel-token-leak audit covers schwabdev's loggers (one known caveat: `tokens.py:~338` logs `response.text` on auth failure); (b) production-only domain writes gate enforced caller-side BEFORE any schwabdev call that triggers a domain write; (c) audit-row INSERT-then-UPDATE lifecycle wraps EVERY schwabdev call.
13. **Q1 production-tier disposition wired through.** Plan acceptance criteria for executing-plans Task 0.b runbook accounts for production-only V1 (operator confirmed at triage); sandbox registration deferred to operator-decision at Task 0.b. Default Task 0.b path is production-only verification.
14. **Q11 V1 INCLUDE market-data ladder design surface.** Plan §B + §H enumerate the cache layer rewrite scope; honest about current `PriceCache`/`OhlcvCache` not having multi-source semantics today; persistence shape A/B/C decision impact on cache layer code.
15. **Q16 `schwab_account_hash` column V1 ADD.** Plan §C migration SQL + plan acceptance criteria for the single-account → multi-account forward-prep posture. Column populated for `source='schwab_api'` rows; NULL for non-Schwab sources.
16. **6 deferred-to-Task-0.b items in plan §D.** Plan §D explicitly enumerates Q8 / Q12 / Q13 / Q14 / Q15 / Q17 with exact operator-paired verification steps. Plan does NOT lock these.
17. **Test fixture USERPROFILE+HOME monkeypatch (where applicable).** Plan §Tasks for any test that writes `cfg.integrations.schwab.environment` to user-config-via-`apply_overrides` (NOT sidecar — sidecar is direct file path).
18. **Phase isolation preserved.** Plan §B READ-ONLY list explicitly enumerates Phase 6 + Phase 7 + Phase 8 + Phase 9 entities as out-of-scope. NO modifications outside `swing/integrations/schwab/`, the new repo, the new migration, the new pipeline-step additions, the new CLI group, the new config sub-dataclasses.
19. **Cassette discipline for OAuth flow.** Plan §G covers the auth-token-exchange + refresh-token-exchange cassettes — these are higher-risk than data-fetch cassettes because they contain the most sensitive secrets. Plan acceptance criteria for token-redaction audit tests on these cassettes.
20. **Test count projection per sub-bundle.** Plan §Tasks enumerate per-task test-count estimates (e.g., "+15-25 tests" range per task). Aggregate per sub-bundle expected within +50-150 fast tests (matches Phase 9 + Phase 10 sub-bundle precedents).

---

## §6 Done criteria

1. Plan at `docs/superpowers/plans/<YYYY-MM-DD>-schwab-api-integration-plan.md` covering §2.1–§2.12.
2. Adversarial review went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Plan section structure mirrors Phase 9 + Finviz plan format; locked decisions vs open questions explicitly delimited.
4. Single commit landed on main: `docs(schwab-api): integration writing-plans implementation plan`. Committed ONCE after Codex convergence (NOT amended through rounds).
5. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Schwab API integration writing-plans

### Plan location
`docs/superpowers/plans/<YYYY-MM-DD>-schwab-api-integration-plan.md` ({line count} lines)
Commit: {sha} `docs(schwab-api): integration writing-plans implementation plan`

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR (after R{n})

### Sub-bundle decomposition (final shape)
- Sub-bundle A: {scope; task count; test count estimate}
- Sub-bundle B: ...
- ...
- Total tasks: {N}; Total test count estimate: +{NN-MM} fast tests

### Schema posture decisions
- Migration 0018 SQL summary: {table + ALTERs + version bump}
- EXPECTED_SCHEMA_VERSION bump: 17 → 18
- Forward-prep: schwab_account_hash NULL-permissible per Q16

### Market-data ladder persistence shape decision (V1 INCLUDE branch)
- Chosen shape: A (parquet-per-(ticker, provider)) / B (SQLite table) / C (provider column inside parquet)
- Justification: ...
- Downstream impact: cache layer rewrite scope summary

### Q1-Q17 disposition wiring (per plan §A)
- All 11 LOCKED dispositions wired into plan acceptance criteria.
- 6 DEFERRED-to-Task-0.b items enumerated in plan §D.

### Inherited disciplines from Phase 9 + Phase 10 + Finviz
- Source-ladder consumer (no re-design): {how plan §A documents}
- Service-layer transaction discipline: {how plan §H documents}
- Token redaction layering: {how plan §G + §Tasks document}
- ...

### Three highest-leverage plan decisions
1. ...
2. ...
3. ...

### Operator-attention items beyond plan
- Brief deviations from this dispatch brief that warrant flagging.
- Any plan-author concerns about scope or sequence.

### Open questions for orchestrator triage (post-plan)
- Should be ZERO if §0.3 dispositions are fully wired through. If non-zero, enumerate.
```

---

## §8 If you get stuck

- **If §1 strategic-context constraints conflict with spec §3 architecture**, **spec §3 wins** unless plan-author can articulate why; surface as plan §D open question.
- **If a Codex round produces a finding requiring operator input**, ACCEPT-with-rationale + flag explicitly in plan §D + return report. Do NOT stall.
- **If plan exceeds ~2500 lines**, you're probably over-specifying — re-scope by deferring more Task 0.b verification details OR collapsing sub-bundles.
- **DO NOT propose code** (Python class definitions, full test bodies, CLI command implementations). Plan describes intent + algorithm + acceptance criteria + discriminating-test patterns ONLY.
- **DO NOT re-litigate triaged dispositions** (Q1-Q17 per §0.3). Operator confirmed; consume verbatim.
- **DO NOT commit prematurely.** Defer commit until Codex converges to NO_NEW_CRITICAL_MAJOR. Then commit ONCE.
- **If migration 0018 ALTER candidates surface FK CASCADE risk**, halt + surface to orchestrator. The Phase 7 backup gate fires on target_version >= 14 from current_version == 13 only — moot here — but plan author verifies no other CASCADE traps.
