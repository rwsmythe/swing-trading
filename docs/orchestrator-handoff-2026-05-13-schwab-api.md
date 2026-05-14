# Orchestrator handoff — 2026-05-13 (post-Phase-10-close; Schwab API dispatch ready)

You are taking over as orchestrator for the Swing Trading project at the **post-Phase-10-close** breakpoint. Phase 10 SHIPPED at `38dbac3` (Sub-bundle E close) → Phase 10 closer housekeeping at `d560218` → post-Phase-10 infrastructure bundle SHIPPED at `27ce96f` → post-bundle housekeeping at `9d4edfc`.

The prior orchestrator is handing off NOW because:
1. **Clean steady state** — Phase 10 fully shipped + infrastructure bundle (cleanup-script + test-runtime) fully shipped + all housekeeping landed on main.
2. **Major-phase boundary** — Schwab API integration is multi-day scope (brainstorm + writing-plans + executing-plans cycle). Operator + prior orchestrator agreed at the bundle dispatch (commit `92e0b8e` brief §1.4) that a fresh orchestrator instance benefits from clean context window for the larger scope.
3. **Context economy** — prior session has been heavy (mid-Phase-10 handoff → Sub-bundles C+D+E ship + Phase 10 closer + infra bundle ship). New context window starts the Schwab API arc fresh.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*` or `mem-search` skill — both will fail. Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded by the harness. See `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/feedback_claude_mem_hook_blocks_disabled.md` for re-enablement criteria.

**Chrome MCP is AVAILABLE** at handoff (confirmed working throughout Phase 10 arc — Sub-bundle A through E gates + infra bundle). Use `mcp__claude-in-chrome__*` tools for browser-driven operator-witnessed gates. Load via `ToolSearch` with `select:mcp__claude-in-chrome__<tool_name>` before invoking. **Use port 8081** to avoid collision with operator's main-HEAD `swing web` session on 8080.

**Fast suite now runs `-n auto` by default** at ~63s wall-clock (was ~6:00 pre-infra-bundle). Operator override: `pytest -n 0` for debug; `pytest -n logical` if SQLite contention surfaces.

## Step 1 — Read these in order

1. **This brief end-to-end** — captures post-Phase-10-close state + Schwab API dispatch readiness.

2. **`docs/orchestrator-handoff-2026-05-13-mid-phase10.md`** — prior orchestrator's handoff brief at mid-Phase-10. Most of its "Operator preferences" + "Production-write classifier soft-block awareness" + "Worktree-side swing web launch pattern" sections REMAIN VALID. Skim only.

3. **`docs/phase3e-todo.md`** top entries 2026-05-13 — post-infra-bundle-ship + Phase 10 Sub-bundle E ship + Phase 10 closer (line 1788+) sections enumerate the 27 V2.1 §VII.F amendments + 3 post-Phase-10 standalone dispatches + Phase 11 candidates pre-banked.

4. **CLAUDE.md** status line + Gotchas section — status line updated through `9d4edfc`; gotchas catalog is comprehensive (no new promotions in Phase 10 or infra bundle — Phase 9's 6 gotcha promotions cover all defect classes seen since).

5. **`docs/orchestrator-context.md`** — durable orchestrator-role conventions; Codex-driven discipline; retention-discipline + archive-split trigger.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                # expect 9d4edfc at HEAD
git status                           # expect clean (3 untracked operator-provided artifact dirs)
git worktree list                    # depends on S2 elevated PS run status (see Step 3)
python -m pytest -m "not slow" -q | tail -5     # NOW with -n auto default; expect ~63s
ruff check swing/ --statistics | tail -3        # expect 18 (E501 only)
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 17
python verify_phase10.py             # expect exit 0
```

Expected:
- HEAD on main: `9d4edfc` (post-infra-bundle housekeeping).
- Working tree clean (3 untracked operator-provided artifact dirs: `reference/Books/`, `reference/minervini/`, `scripts/`).
- Fast suite ~3286 main / 3283 worktree-side. **NEW default: `-n auto` parallel execution at ~63s wall-clock.**
- Ruff baseline 18 (E501 only).
- Schema version 17.
- `verify_phase10.py` exits 0.

## Step 3 — Project state at handoff (post-Phase-10-close)

### HEAD + commit chain on main

```
9d4edfc docs(post-phase10-infra): post-bundle-ship housekeeping
27ce96f Merge post-phase10-infra-bundle into main: cleanup-script -DeregisterFirst + pytest-xdist baseline (6.56× speedup)
566e3a3 docs(post-phase10-infra): return report
cdea854 fix(post-phase10-infra): Codex R1 Critical #1 — confirm before deregister loop
f0e906f chore(post-phase10-infra): integration sweep + ruff (T-6)
3e0df3d chore(deps): add pytest-xdist + configure -n auto baseline (T-3)
d178d89 feat(scripts): -DeregisterFirst switch for cleanup-locked-scratch-dirs.ps1 (T-2)
92e0b8e docs(post-phase10): infrastructure bundle executing-plans dispatch brief
d560218 docs(phase10): Phase 10 CLOSER housekeeping — Sub-bundle E ship + arc closer aggregate
38dbac3 Merge phase10-bundle-E-process-grade-trend-and-polish into main: Phase 10 Sub-bundle E (CLOSES Phase 10)
```

### Project state

- **HEAD on main:** `9d4edfc` (post-infra-bundle housekeeping).
- **Test count:** ~3286 main HEAD / 3283 worktree-side (post-Phase-10-arc-close + infra bundle).
- **Test runtime:** ~63s wall-clock at `-n auto` default (post-infra-bundle xdist integration; 6.56× from prior 415s baseline).
- **Ruff baseline:** 18 (E501 only). Unchanged since Phase 9 close.
- **Schema version:** v17. LOCKED through Phase 10. Schwab API dispatch MAY introduce schema changes (new tables for OAuth tokens, API audit trail, possibly Schwab-source `cash_movements` / `fills` columns). New orchestrator should treat schema posture as OPEN for Schwab API — `EXPECTED_SCHEMA_VERSION` may bump to 18 if migration warranted.
- **Active risk_policy:** `policy_id=5` (Option C revert from Sub-bundle A; `max_account_risk_per_trade_pct=0.5` cfg-aligned; `capital_floor_constant_dollars=7500.0`; `scratch_epsilon_R=0.10`). Unchanged through entire Phase 10 + infra bundle.
- **Production trades:** 8 total; 5 open (DHC/YOU/VSAT/CVGI/LAR) + 3 closed-reviewed (VIR/CC/SGML). All 8 have `risk_policy_id_at_lock IS NULL` (pre-Phase-9 legacy; rendered with `[legacy: pre-Phase-9 trade]` annotation in metrics).
- **Production review_log:** 12 rows; 7 completed + 5 pending. Reviews 10+11 stamped `risk_policy_id_at_review_completion=4`.
- **Production account_equity_snapshots:** **3 manual snapshots** (#1 $2000 at 2026-05-11; #2 $1800 at 2026-04-01 back-recorded; **#3 $2000 at 2026-05-13** from Sub-bundle E T-E.5 S6 gate via `/account/snapshot` form). All `source='manual'`. Schwab API integration will write `source='schwab_api'` snapshots that outrank manual per spec §A.9 source ladder.
- **Production reconciliation_discrepancies:** 30 total; all resolved as `acknowledged_immaterial`. 7 reconciliation_runs across Phase 9 + Phase 10 gates.
- **swing.config.toml:** clean (`risk.max_risk_pct=0.005`).
- **user-config.toml:** intact (Finviz token + screen_query). Schwab API will likely add an `[integrations.schwab]` section (OAuth client_id, client_secret, refresh_token) following the Finviz precedent.

### Worktree husks state at handoff

**Indeterminate at handoff time** — operator may have run S2 (elevated PowerShell `-DeregisterFirst`) since the bundle ship, OR may not have.

**If S2 NOT yet run:** 8 husks pending = 4 phase9 still-registered (B/C/D/E) + 3 phase10 orphans (C/D/E) + 1 infra-bundle orphan.
**If S2 run successfully:** 0 husks pending; `git worktree list` shows ONLY main repo.

**Check at session start:**
```bash
git worktree list
ls .worktrees/ 2>/dev/null || echo "no worktrees dir"
```

If husks remain + operator wants them cleared, surface the `-DeregisterFirst` run again. If husks remain + operator wants to defer, do not block on it.

### Phase 10 + Phase 9 dispatches shipped so far

**Phase 9 arc (5 sub-bundles A+B+C+D+E + writing-plans + brainstorm):** 53 commits / 19 Codex rounds / +503 cumulative fast tests / schema v16 → v17 / 4 ACCEPT-WITH-RATIONALE banked / 6 CLAUDE.md gotchas promoted.

**Phase 10 arc (5 sub-bundles A+B+C+D+E + writing-plans + brainstorm + electives amendment):** 52 commits / 13 Codex rounds / +494 cumulative fast tests / schema v17 unchanged / **ZERO ACCEPT-WITH-RATIONALE banked entire arc — cleanest 5-bundle arc-final state in project history** / ZERO CLAUDE.md gotchas promoted entire arc / 9 operator-visible metrics surfaces shipped (8 metric pages + cross-bundle reconciliation banner on 10 base-layout pages + T-E.5 manual snapshot form + T-E.6 per-trade discrepancy indicator on trade detail).

**Post-Phase-10 infrastructure bundle:** 5 commits / 2 Codex rounds / +28 fast tests / 6.56× test-runtime speedup / ZERO production code touched / cleanup-script `-DeregisterFirst` switch + pytest-xdist baseline integration.

## Step 4 — Schwab API dispatch readiness (your next major arc)

### Why Schwab API now

Operator's stated motivation (from phase3e-todo entries + return-report watch items):

1. **Source-ladder upgrade.** Spec §A.9 source ladder is `schwab_api > tos_csv > manual`. Currently only `tos_csv` + `manual` exist. Schwab API integration unlocks the top-priority source path.
2. **Replaces 7-day Account Statement CSV** (already wired in Phase 9 Sub-bundle B + C) with real-time API queries — eliminates the multi-line `Account Order History` parser fragility (Phase 9 Sub-bundle E T-E.3 fix) + the 7-day window limitation.
3. **Unlocks pre-Phase-7 trade history** — Schwab inception-CSV ingestion is a banked V2 candidate (Phase 9 Sub-bundle C 2026-05-12 entry); Schwab API gives the same data via authenticated query.
4. **Closes the `account_equity_snapshots.equity_dollars` cash-basis-vs-MTM ambiguity** — Schwab API returns authoritative Net Liquidating Value (NLV) per-call, removing operator's manual cash-basis-stamp ambiguity (Phase 9 Sub-bundle C 2026-05-12 entry; T-E.5 manual snapshot still operator-stamps cash basis).
5. **Operational metrics LIVE-badge stay LIVE** — Sub-bundle D capital-friction surface relies on `account_equity_snapshots` rows ≤ `asof_date`. Schwab API can write a snapshot per pipeline run, making PROVISIONAL state effectively impossible in steady-state.

### Scope dimensions (for brainstorm)

**Authentication:**
- Schwab Developer Portal OAuth 2.0 flow.
- Client credentials (client_id, client_secret) → user-config.toml `[integrations.schwab]` section.
- Refresh token rotation; access token caching with TTL.
- Token storage MUST follow Phase 9 Sub-bundle A "user-config.toml monkeypatch" gotcha pattern + CLAUDE.md "Finviz token storage" gotcha precedent (tokens in user-config NOT tracked swing.config; `swing config show` masks).

**Pipeline integration:**
- New `swing/integrations/schwab/` namespace (parallel to `swing/integrations/finviz/`).
- Pipeline steps: `_step_schwab_snapshot` (writes `account_equity_snapshots` with `source='schwab_api'`), `_step_schwab_orders` (reconciliation source ranked above TOS CSV), possibly `_step_schwab_fills`.
- Cassette-based fast-test corpus (Finviz precedent at `tests/integrations/test_finviz_api_live.py`).
- Drift-detection signature-hash (Finviz precedent in `swing/pipeline/runner.py:_step_finviz_fetch`).

**Reconciliation source-ladder:**
- Per spec §A.9: schwab_api > tos_csv > manual. Multiple snapshots on same `snapshot_date` → highest-source wins per-source-ladder.
- Existing `record_snapshot` service (Phase 9 Sub-bundle C; per E3 deviation from Sub-bundle E return report) needs source-aware override semantics — or new service for API-sourced writes that respects the source-ladder.

**Schema considerations:**
- Possibly new table: `schwab_oauth_state` (refresh tokens, access tokens, expiry, last_refresh_at).
- Possibly new columns on `account_equity_snapshots`: `schwab_account_hash`, `schwab_position_count` (denominator-context for verification).
- Possibly new table: `schwab_audit_log` (every API call + response code + rate-limit headers for operator transparency).
- New migration: `0018_schwab_integration.sql` (if migration warranted).

**Rate limits + reliability:**
- Schwab documented limit: 120 requests/minute per app (estimate; verify at dispatch).
- Cache + breaker pattern per existing `PriceCache` / `OhlcvCache` precedent.
- Append-or-fall-back pattern for empty API responses per CLAUDE.md gotcha "External-API empty-result must be treated as transient" — DO NOT overwrite cached data on empty response.

**Operator workflow:**
- Initial setup: operator runs `swing schwab setup` (or similar) → OAuth flow → tokens persist to user-config.toml.
- Refresh-token rotation: automatic; operator alerted if refresh fails.
- Daily flow: pipeline auto-fetches snapshot + orders + fills; reconciliation runs against Schwab data first; TOS CSV becomes V2-deprecated.

### Pre-banked V2 candidates that are Schwab-API-shaped

Per phase3e-todo entries throughout Phase 9 + 10 + infra bundle:

1. **Schwab inception-CSV ingestion** (Phase 9 Sub-bundle C 2026-05-12 entry) — richer historical seed than 7-day Account Statement; could be unified into Schwab API dispatch OR remain standalone if operator wants to ingest historical CSV first then go live via API.
2. **`account_equity_snapshots.equity_dollars` semantic formalization** (Phase 9 Sub-bundle C 2026-05-12 entry) — cash-basis vs net-liq distinction; Schwab API resolves by returning authoritative NLV.
3. **Orphan-emit discrepancy detail page** (Phase 10 Sub-bundle E return report §8) — orphan emits (sector_tamper / equity_delta / cash_movement_mismatch with NULL trade_id) not surfaced anywhere. Schwab API may emit additional orphan-discrepancy types worth surfacing.
4. **`render_class_d` "point" branch mean-semantics switch** (Phase 10 Sub-bundle A V2 candidate) — not directly Schwab-shaped but related to broader spec §A.21 amendment.

### Recommended dispatch shape (operator-decision at session start)

**Option A (recommended): full brainstorm → writing-plans → executing-plans cycle.**
- Brainstorm dispatch: produces spec doc at `docs/superpowers/specs/2026-05-14-schwab-api-design.md` (or similar). Establishes scope, source-ladder semantics, auth flow, capture-needs, schema posture. Codex review 3-6 rounds typical for spec phase.
- Writing-plans dispatch: produces plan doc decomposing into sub-bundles (likely 3-5: A auth + token storage; B snapshot integration; C reconciliation source-ladder; D fills + cash_movements; E polish + handoff). Codex review 3-6 rounds.
- Executing-plans dispatch per sub-bundle (operator-paced).

**Option B (faster but riskier): skip brainstorm; writing-plans directly.**
- Only if operator already has clear scope mental model + time-budget pressure.
- Lose the Codex value-add at brainstorm phase (typical 3+ Critical findings caught at brainstorm prevent expensive plan revisions).

**Option C (most conservative): scope-bound investigation FIRST.**
- Standalone investigation dispatch (similar to `docs/3e8-sell-side-advisories-investigation.md` precedent): survey Schwab Developer Portal docs + decide what's V1 scope vs V2.
- THEN brainstorm with clearer scope bounds.
- Useful if operator hasn't already done the API-surface survey.

Prior orchestrator recommends Option A (full cycle) unless operator says otherwise. The Schwab API surface is well-documented; brainstorm-first establishes the spec without conflating it with implementation choices.

### Sub-bundle electives (operator may pre-elect at brainstorm or after)

Likely operator-elective items the Schwab API brainstorm should flag:

- **§E1 Schwab inception-CSV ingestion** — V1 scope or V2 follow-up?
- **§E2 OAuth client-secret storage** — plaintext in user-config.toml (Finviz precedent) or encrypted (Windows DPAPI / cross-platform `keyring` lib)?
- **§E3 Multi-account support** — Schwab supports multiple linked accounts per OAuth app; V1 single-account-only or multi-account?
- **§E4 Webhook / streaming** — Schwab offers streaming quotes + real-time order updates; V1 batch-poll or V1 streaming?
- **§E5 Operator-facing Schwab UI** — web form for token refresh / account selection, or CLI-only?

These will surface during brainstorm; flag for operator triage.

## Step 5 — Operator preferences (durable; carry over from prior handoff)

- **Implementer-dispatch is the default** per `~/.claude/projects/.../memory/feedback_orchestrator_vs_implementer_execution.md`. Small dispatches (e.g., a brainstorm of 1-3 hr scope) still go to implementer.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention 2026-05-09).
- **Implementer runs adversarial-critic** (per orchestrator-context "Executing-plans dispatch convention" 2026-05-02).
- **Multi-choice format for design questions** (operator preference; AskUserQuestion preferred).
- **Chrome MCP gate-driving** is the established pattern. Use port 8081 to avoid collision with operator's 8080 session.
- **Spec is canonical over brief on cosmetic typos** (codified via Phase 9 Sub-bundle C R1 M#1 equity_delta sign convention ACCEPT-WITH-RATIONALE).
- **Production-write classifier soft-block** workaround: when about to invoke production-write where operator pre-authorized via AskUserQuestion, IF the classifier blocks, surface back to operator with action description + ask for plain-chat "yes" confirmation. Schwab API OAuth flow + token storage operations are production-writes — expect classifier interaction.
- **Stop the web server when done.** Worktree-side `swing web` MUST use `--port 8081` if operator's main-HEAD swing web is on 8080.
- **27 V2.1 §VII.F amendments pending triage** — operator + new orchestrator may want to process these BEFORE Schwab API arc (read-side ~1-2 hrs operator+orchestrator review). Or fold into brainstorm context.

## Step 6 — Production-write classifier soft-block awareness

Carried forward from prior handoffs. When the orchestrator drives production-mutating actions (any direct SQLite UPDATE on production swing.db, any `swing config policy set`, any `swing account snapshot record`, any OAuth flow that writes user-config), the auto-mode classifier may soft-block even if operator pre-authorized via AskUserQuestion.

**Workaround:** surface back to operator with action description + ask for plain-chat "yes" confirmation. Don't try to work around the classifier in any other way.

**Forward-relevance for Schwab API:** OAuth token storage writes will hit this. So will any Schwab-driven snapshot writes during testing. Plan for explicit operator authorization at each production-write surface during executing-plans.

## Step 7 — Banked items NOT to scope into Schwab API arc

Schwab API dispatch should explicitly exclude (operator may revisit at brainstorm):

- **§8.4 Corporate_Actions MVP** — still deferred as separate standalone dispatch (per phase3e-todo 2026-05-13 entry + Phase 10 closer section line 1788+). Schwab API may surface corporate-action data; that's distinct from the Corporate_Actions MVP scope.
- **§8.6 / T-B.7 lucky_violation_R** — already shipped at Phase 10 Sub-bundle B (`6ed0f35`). Not in scope.
- **§11.2(b) / T-E.6 per-trade discrepancy indicator** — already shipped at Phase 10 Sub-bundle E (`38dbac3`). Not in scope.
- **§11.2(c) / T-C.5 per-cohort discrepancy filter** — already shipped at Phase 10 Sub-bundle C (`a814006`). Not in scope.
- **Per-cohort paused-interval filter** — V2 candidate; T-C.5 UI pattern reuse. Out of Schwab API scope.
- **Schwab inception-CSV ingestion** — operator-decision at brainstorm: bundle into Schwab API V1 OR separate dispatch?

## Step 8 — Quick reference summary

| Artifact | Path / commit |
|---|---|
| Prior orchestrator handoff (mid-Phase-10) | `docs/orchestrator-handoff-2026-05-13-mid-phase10.md` |
| Phase 9 closer | `docs/orchestrator-handoff-2026-05-13.md` (prior session before mid-Phase-10) |
| Phase 10 plan (AMENDED in-tree) | `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` |
| Phase 10 spec | `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` |
| Phase 10 electives amendment | `docs/phase10-electives-amendment.md` |
| Phase 10 Sub-bundle return reports | `docs/phase10-bundle-{A,B,C,D,E}-return-report.md` |
| Post-Phase-10 infra bundle | `docs/post-phase10-infra-bundle-*.md` (brief + return report) |
| Phase 9 plan + return reports | `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` + `docs/phase9-bundle-{A,B,C,D,E}-return-report.md` |
| Finviz API integration (closest API precedent) | `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (merged `002338a`) |
| Schwab API brainstorm | TBD (new orchestrator drafts) |
| Schwab API plan | TBD |
| Cross-phase backlog | `docs/phase3e-todo.md` (active; archive companion at `docs/phase3e-todo-archive.md`) |
| Orchestrator-role context | `docs/orchestrator-context.md` (active; archive companion at `docs/orchestrator-context-archive.md`) |
| Daily routine | `docs/cycle-checklist.md` |

## Step 9 — Operator-facing notes for handoff turn

When operator reads this brief at session start, they should expect:
1. Confirmation that Phase 10 closed cleanly + post-Phase-10 infra bundle shipped + S2 may or may not have run depending on operator's elevated-PS run.
2. Schwab API dispatch readiness as your next major action — operator commissions when ready.
3. Recommended Option A (brainstorm → writing-plans → executing-plans full cycle).
4. Active risk_policy = `policy_id=5` (cfg-aligned; unchanged through entire Phase 10).
5. 27 V2.1 §VII.F amendments pending triage (read-side; may want to process before Schwab arc).
6. 3 production snapshots in `account_equity_snapshots` (#1 + #2 + #3 from Sub-bundle E S6 gate); Schwab API will add `source='schwab_api'` rows that outrank manual per source-ladder.
7. Test suite now runs `-n auto` by default at ~63s (6.56× speedup from infra bundle).

### Recommended absorption order at session start

- Read this handoff brief end-to-end.
- Read CLAUDE.md status line + Gotchas section (gotchas catalog comprehensive; Finviz API integration gotcha family is the closest precedent for Schwab API work).
- Read prior orchestrator handoff `docs/orchestrator-handoff-2026-05-13-mid-phase10.md` (skim Step 5 operator preferences + Step 7 worktree-side swing web pattern + Step 8 production-write classifier awareness).
- Read `docs/phase3e-todo.md` top entries 2026-05-13 (post-infra-bundle-ship + Phase 10 Sub-bundle E ship + Phase 10 closer section line 1788+; covers all 27 V2.1 §VII.F amendments + Phase 11 candidates).
- Read existing Finviz integration as the closest precedent: `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` + `swing/integrations/finviz/` source + `tests/integrations/test_finviz_api_live.py` cassette pattern.
- Read Phase 9 Sub-bundle C return report §A.9 source-ladder semantics + `swing/trades/account_equity_snapshots.py:record_snapshot` service contract (the API write path will need source-aware extension).
- Stand by for operator to commission either: (a) Schwab API brainstorm dispatch; (b) 27-amendment triage first; (c) §8.4 Corporate_Actions or some other backlog item first.

## Step 10 — Closing note from prior orchestrator

This handoff caps a productive session that closed Phase 10 + cleaned up the test-runtime + worktree-husk debt that had been accumulating. Phase 10 ended with the **cleanest 5-bundle arc-final state in project history** (ZERO ACCEPT-WITH-RATIONALE + ZERO CLAUDE.md gotchas promoted across the entire arc — a sign that the project's defensive coverage has matured to where every Phase 10 defect class hit was already pre-empted by an existing gotcha).

The Schwab API arc is the next major operator-paced milestone. It WILL touch schema (new tables for OAuth state + audit trail; possibly new columns) — so the §A.0 ZERO-new-schema LOCK that held through Phase 10 V1 will lift. New orchestrator should expect `EXPECTED_SCHEMA_VERSION` to bump to 18 at the migration step.

Operator preference reaffirmed via durable memory: implementer-dispatch is the default; orchestrator-inline only at token-cost crossover. The Schwab API arc has enough scope (likely 3-5 sub-bundles + ~5-10 dispatches over multiple days) that implementer-dispatch is clearly the right default.

Good luck.

---

*End of handoff brief. Post-Phase-10-close orchestrator transition. Phase 10 SHIPPED; infrastructure bundle SHIPPED. Next: operator commissions Schwab API arc (recommended Option A full cycle: brainstorm → writing-plans → executing-plans).*
