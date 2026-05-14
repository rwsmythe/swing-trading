# Cross-Phase Operational Backlog

> **Filename note (2026-05-01):** this file is named `phase3e-todo.md` for historical reasons (it was created at the end of the Phase 3d walkthrough as the Phase 3e backlog). It has since accumulated cross-phase items (Phase 4 / 4.5 / 6-9 + standalone bundles + Tier-3 deferrals + research-branch followups). The filename is preserved to keep ~46 cross-references in shipped briefs valid; the canonical title is "Cross-Phase Operational Backlog." Not a commitment, just a trackable list.

> **Archive companion (2026-05-05):** SHIPPED + closed entries previously inline have moved to `docs/phase3e-todo-archive.md`. Fresh-orchestrator bootstrap reads only this active file; grep the archive on demand for historical context (commit hashes, prior dispatches). Retention discipline + archive-split trigger are documented in `docs/orchestrator-context.md` §"Maintenance: retention discipline."

---

## 2026-05-13 Schwab API integration brainstorm SHIPPED — 939-line spec + 17 open questions for orchestrator triage (operator-paced)

**Brainstorm SHIPPED 2026-05-13** at `585556f` (single commit on main; `docs(schwab-api): integration brainstorm spec`). Operator-dispatched implementer per orchestrator-drafted brief at `c4252d3` (`docs/schwab-api-brainstorm-dispatch-brief.md`, 390 lines). Spec at `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (939 lines; within 600-1100 brief budget).

**5 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering (R1 0C/10M/5m → R2 0C/6M/3m → R3 1C/3M/2m → R4 0C/2M/2m → R5 0C/0M/0m); cumulative 1C + 21M + 12m all RESOLVED inline; **ZERO ACCEPT-WITH-RATIONALE banked** — matches Phase 10 cleanest-arc precedent. Terminated within MAX_ROUNDS=5; no operator-override past default needed.

### Three highest-leverage design decisions

1. **§3.6.3 production-only domain writes (R3 Critical resolution).** `cfg.integrations.schwab.environment` gates `record_snapshot()` + `run_schwab_reconciliation()`; sandbox is verification-only (audit rows written; ZERO domain rows; market-data ladder short-circuits). Prevents synthetic Schwab data from winning the source-ladder (Schwab is precedence 0) and silently contaminating Phase 10 metrics + reconciliation discrepancies + cohort analysis. **Critical-class find Codex R3 surfaced; brief did not anticipate.**
2. **§3.8 market-data ladder rewrite scope honestly enumerated for writing-plans.** Brief recommended V1 INCLUDE (per operator §1.9 preference); spec writes the INCLUDE branch. Honestly admits current `PriceCache`/`OhlcvCache` do NOT have multi-source semantics today. Writing-plans picks persistence shape A (parquet-per-(ticker, provider)) / B (SQLite table) / C (provider column inside parquet). Default recommendation: A.
3. **§3.6.2 audit-write surface boundary.** Pipeline + CLI surfaces SYNCHRONOUS audit; web-page-render path is EXPLICITLY-UNAUDITED V1 (logs-only). Prevents SQLite contention from web cache misses + cardinality explosion. V2 candidates (batched-summary writer; `/admin/schwab-counters` debug endpoint) enumerated.

### Auth + token storage decisions LOCKED in spec

- **Initial-setup flow:** two first-class variants — `--callback localhost` default (one-shot HTTPS listener on 127.0.0.1:8765 with self-signed cert) + `--callback paste` V1 IF Task 0.b verifies one of three OOB mechanisms; else DROPPED V1.
- **Token storage:** per-environment sidecar JSON file at `%USERPROFILE%/swing-data/schwab-state.{sandbox,production}.json` — NOT user-config.toml.
- **Refresh strategy:** lazy-on-first-API-call with 60s proactive safety margin; file-lock on sidecar during refresh.
- **Encrypted at rest:** V1 plaintext, disclosed as **HIGHER-RISK deviation from Finviz precedent** (client_secret + long-TTL refresh_token co-stored). V2 hardening (`keyring` / DPAPI) promoted to high priority (§10 Q2).
- **Active env selection:** `cfg.integrations.schwab.environment` is SoT (default production); CLI `--environment` override per-invocation; pipeline cfg-only.
- **Revocation:** `swing schwab logout` revokes via Schwab endpoint + atomically renames sidecar to `schwab-state.{env}.json.deleted-<ts>` + unlinks.

### Pipeline integration LOCKED

- **New steps:** `_step_schwab_snapshot` + `_step_schwab_orders` (two new pipeline steps). Market-data path is NOT a separate step; integrated into `_step_evaluate`/`_step_charts` cache fetch boundaries.
- **Step ordering:** AFTER `_step_recommendations`, BEFORE `_step_charts` (briefing-includes-Schwab-data + charts-can-feed-back-on-stop-drift).
- **Failure tolerance:** continue-with-error (mirror Finviz precedent at `swing/pipeline/runner.py:285-294`).
- **CLI surface:** `swing schwab {setup, refresh, fetch [--snapshot|--orders|--all|--verify-marketdata], status, logout}`.
- **Concurrency:** `SchwabPipelineActiveError` hard exclusion for `fetch --snapshot/--orders/--all` (UPSERT-provenance race + INSERT-only duplication); `logout`/`setup` refused unless `--force`; `refresh`/`status` concurrent-safe (sidecar file-lock handles refresh).

### Schema candidates DEFERRED to writing-plans

- **New table:** `schwab_api_calls` (14 columns enumerated in spec §4.1).
- **ALTER candidates:** `account_equity_snapshots.schwab_account_hash TEXT NULL` (V1 ADD per §10 Q16 default; forward-prep multi-account V2); `reconciliation_runs.schwab_api_call_id INTEGER NULL` (FK candidate).
- **Market-data persistence:** writing-plans picks Shape A/B/C per §3.8.2 (default A: parquet-per-(ticker, provider) — no new SQL table).
- **EXPECTED_SCHEMA_VERSION bump:** 17 → 18 (driven by `schwab_api_calls` + ALTERs; Shape B would also drive a bump from market-data side).

### 17 open questions for orchestrator triage (operator-paced)

Orchestrator-grouped by triage urgency for operator review:

**A. Operator-decide-NOW (impacts writing-plans scope; 4 items):**
- Q1: Schwab Developer Portal app status — operator-actionable; orchestrator default: start sandbox today; promote to production when Schwab approves.
- Q3: Multi-account support — orchestrator default: V1 single-primary-account; V2 multi-account.
- Q11: Market-data ladder V1 INCLUDE vs EXCLUDE — orchestrator default: **V1 INCLUDE** (operator-flagged at brief time; spec writes INCLUDE branch).
- Q6: Schwab inception-CSV ingestion — orchestrator default: **separate dispatch** (per phase3e-todo 2026-05-12 entry; keep this arc focused).

**B. Operator-confirm-defaults (orchestrator-can-take; 6 items):**
- Q2: Token encryption — V1 plaintext (Finviz precedent + risk disclosed; V2 keyring/DPAPI = high-priority hardening).
- Q5: Operator UI — V1 CLI-only.
- Q7: TOS CSV deprecation — stays as V1 fallback.
- Q9: Cash-basis manual snapshot retention — yes (source-ladder resolves at read time).
- Q10: Pipeline step ordering — after `_step_recommendations`, before `_step_charts` (architectural).
- Q16: `account_hash` column on `account_equity_snapshots` — V1 ADD (NULL-permissible; forward-prep multi-account; cheap insurance).

**C. Defer-to-Task-0.b live verification (5 items; operator-paired at executing-plans):**
- Q4: Streaming vs batch-poll — V1 batch-poll; V2 streaming.
- Q8: Sandbox vs production HTTP-layer differentiation (per-env sidecar LOCKED; HTTP-layer base URL / path / scope / TTL OPEN).
- Q12: Premium-tier Market Data endpoint access (default: V1 default-tier delayed quotes).
- Q13: OAuth callback localhost vs paste — localhost default + `--paste` flag fallback if Task 0.b reveals env block.
- Q14: OAuth scope-string composition — synthesize default; live-verify exact format.
- Q15: Refresh-token rotation behavior — design handles both rotate-every and rotate-near-expiry; cassette+test fixtures need known canonical case from operator-witnessed verification.
- Q17: Market Data API rate limits independent of Trader API — synthesized "~Trader API limits or looser"; flag Task 0.b verification.

(Note: Q14 + Q15 + Q17 are 3 of the 5 in C; total = Q4+Q8+Q12+Q13+Q14+Q15+Q17 = 7 items — orchestrator counts 5+7+4 = 16 not 17 due to Q4 fitting both B confirm + C verify; numerically 17 questions total.)

### Inherited disciplines from Finviz precedent (verbatim)

- urllib3 + requests-bundled-urllib3 DEBUG-log suppression context manager (`_suppress_transport_debug_logs`).
- Cassette `filter_headers=['authorization']` + EXTENDED `filter_query_parameters=['code', 'refresh_token', 'client_id', 'client_secret', 'redirect_uri', 'access_token']` + `filter_post_data_parameters` + custom body redactor for token/secret substrings.
- Sentinel-token-leak audit test pattern (`tests/integrations/test_schwab_token_redaction_audit.py`).
- Exception `__str__` no-token contract on every Schwab exception class.
- CLI vs pipeline concurrency exclusion via `SchwabPipelineActiveError` — INHERITED from Finviz's `FinvizPipelineActiveError` (V1 decision REVERSED implementer's R1 initial framing per brief watch-item #17 reversal; R2 Major-3 surfaced UPSERT-provenance race + reconciliation_runs INSERT-only duplication risk — **brief watch-item #17 was technically violated by final design BUT the rationale is Codex-discovered + documented**).
- Single-retry-on-429 semantics with `Retry-After` cap at 30s.

### Capture-needs feedback

- For Phase 6/7/8/9/10: **None.** All consumer surfaces already in place (Phase 9 source-ladder + Phase 10 metrics consume transparently; capital-friction LIVE badge gap closes automatically).
- **For writing-plans dispatch (12 firm-up items):** §3.3.1 endpoint shapes via Task 0.b; §3.3.1 scope strings via Task 0.b; §3.5 CLI subcommand body design; §3.6 `schwab_api_calls` DDL; §3.2.4 file-lock cross-platform shim; §3.2.1 callback HTTPS-vs-HTTP; §7 cycle-checklist updates; test fixtures + Task 0.b runbook; integration test E2E mirroring Phase 9 Sub-bundle E pattern; market-data persistence shape A/B/C choice; account_hash column V1/V2; `schwab_account_hash` + `reconciliation_runs.schwab_api_call_id` ALTERs.

### Brief deviations flagged for orchestrator awareness

1. **Amended single commit instead of one-shot commit at end of all rounds.** Brief §4 listed "no amending" alongside "single commit ... no rogue commits" — internally contradictory because Codex iteration produces 5 rounds of fixes that must all land in ONE commit. Implementer committed prematurely at R0 (`da30045`) before adversarial loop, then amended through R1-R5 fixes; final SHA `585556f`. Local-only history (no push); does not violate published-commit safety the "no amending" guard targets. **Brief-template improvement candidate:** future brainstorm-dispatch briefs should phrase as "defer commit until all Codex rounds complete + commit once at end" rather than the contradictory "single commit + no amending" pairing.
2. **Brief watch-item #17 reversed during R2.** Initial spec at R0 had "NO `SchwabPipelineActiveError`-style hard exclusion" (file-lock-only). R2 Major-3 surfaced UPSERT-provenance race (snapshot UPSERT preserves PK but overwrites `source_artifact_path` + audit row pointing to the OTHER writer's call_id — real audit-trail integrity break) + reconciliation_runs INSERT-only duplication risk. Final spec REVERSES to "HARD exclusion via `SchwabPipelineActiveError` on `fetch --snapshot/--orders/--all`". Watch-item 17 technically violated by final design BUT rationale Codex-discovered + documented; binding "Finviz precedent" actually inherited rather than rejected.

### Cross-references

- Brainstorm dispatch brief: `docs/schwab-api-brainstorm-dispatch-brief.md` (`c4252d3`).
- Spec: `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`).
- Closest API integration precedent: `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (Finviz; merged `002338a`) + `swing/integrations/finviz_api.py`.
- Source-ladder consumer (binding inheritance per spec §3.7): `swing/data/repos/account_equity_snapshots.py:_SOURCE_PRECEDENCE` + `get_latest_snapshot_on_or_before(with_provenance=True)`; `swing/trades/account_equity_snapshots.py:record_snapshot`.
- Spec format precedent: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines).
- Post-Phase-10-close handoff: `docs/orchestrator-handoff-2026-05-13-schwab-api.md`.

### Next dispatch

**Operator-paced.** Triage 17 open questions (C-bucket items can defer to Task 0.b at executing-plans; A+B-bucket items decide-now-or-rubber-stamp orchestrator defaults). Once triage complete, orchestrator dispatches Schwab API writing-plans via separate brief.

---

## 2026-05-13 Post-Phase-10 infrastructure bundle SHIPPED — cleanup-script `-DeregisterFirst` + pytest-xdist baseline (6.56× speedup)

**Bundle SHIPPED 2026-05-13** at `27ce96f` (integration merge of `post-phase10-infra-bundle`). 5 commits = 3 task-impl (T-2 + T-3 + T-6) + 1 Codex-fix (R1 Critical #1 confirm-before-deregister) + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR**. ZERO ACCEPT-WITH-RATIONALE. **ZERO production code touched** (binding lock from dispatch brief §0; read-side / infrastructure-only).

Tests: 3255 → 3283 worktree-side (+28 net). Ruff 18 unchanged. Schema v17 unchanged.

### Key deliverables

**1. `cleanup-locked-scratch-dirs.ps1` `-DeregisterFirst` switch** (default OFF; opt-in):
- Pre-pass scans `git worktree list` for paths matching `^.+\.worktrees[\\/]+phase\d+.*` OR `^.+\.claude[\\/]+worktrees[\\/]+phase\d+.*`.
- Presents candidate list to operator + prompts for confirmation BEFORE invoking `git worktree remove --force` (R1 Critical #1 defense-in-depth gate).
- After deregister loop, existing orphan-discovery pass picks up resulting orphans.
- Safety filter: BINDING regex strict `phase\d+-*` prefix; rejects non-matching branches.
- `test_safety_filter_rejects_own_worktree_explicitly` pins that `post-phase10-infra-bundle` itself is REJECTED.
- DryRun compatibility preserved.

**2. pytest-xdist baseline integration:**
- Added `pytest-xdist>=3.5.0` to `[project.optional-dependencies].dev`.
- Configured `[tool.pytest.ini_options].addopts = "-n auto"` (operator override via `-n 0` / `-n logical` / `-n N`).
- All 3283 tests pass under `-n auto` across 3 independent runs (zero xdist-unsafe state-leak failures).

### Measurement (BINDING per dispatch brief §0.7)

- Serial baseline: **415.17s** (3255 tests).
- Parallel median (`-n auto`; 3 runs): **63.24s** (3276 tests; #1 60.82s, #2 76.07s, #3 63.24s).
- **Speedup ratio: 6.56×** (well above 2× minimum + 3-5× projection).
- Post-R1-fix final sweep: 60.96s at 3283 tests + 5 skipped + 3 pre-existing fails.

### T-1 recon findings + conditional-task disposition

**T-4 (session-scoped schema fixtures) SKIPPED:**
- `ensure_schema` NOT in `--durations` top-30 (called 254 times but aggregate <0.3% of serial baseline).
- Risk asymmetry: migration tests + rollback-semantics tests + pre/post-v17 ratify tests would silently break if schema state shared across tests.

**T-5 (TestClient lifespan audit) SKIPPED:**
- Lifespan footprint is microsecond-level (`ThreadPoolExecutor` constructor + `shutdown(wait=False)`).
- Top-30 cost is route-execution time, NOT lifespan startup.
- Audit cost (per-test app.state reachability analysis) exceeds savings.

Both remain backlog-eligible if operator surfaces a specific hotspot later.

### 5 deviations from brief (none require V2.1 §VII.F)

1. §6.1 — 1+3 serial+parallel readings instead of 3+3 (6.56× speedup unambiguous from one baseline + three readings).
2. §6.2 — Python-side tests reading `.ps1` source (NOT PowerShell Pester); 26 admit/reject corpus tests + 5 source-invariants at zero PowerShell infrastructure cost.
3. §6.3 — `-n auto` in addopts default (NOT opt-in via CLI); matches operator's stated goal.
4. §6.4 — integration test file created (was optional per brief).
5. R1 Critical #1 — confirm-before-deregister gate added in `cdea854` (not in brief; surfaced by Codex as defense-in-depth for the new destructive surface).

### Operator-witnessed gate S2 PENDING

Elevated PowerShell run of `-DeregisterFirst` against the 7 pre-merge husks + 1 new infra-bundle orphan = **8 husks to clear**. Operator-driven — orchestrator surfaces to operator post-merge for plain-chat authorization. Run:

```powershell
cd c:\Users\rwsmy\swing-trading
.\cleanup-locked-scratch-dirs.ps1 -DeregisterFirst
```

### Cross-references

- Return report: `docs/post-phase10-infra-bundle-return-report.md`.
- Dispatch brief: `docs/post-phase10-infra-bundle-executing-plans-dispatch-brief.md`.
- Cleanup script: `cleanup-locked-scratch-dirs.ps1` (extended with `-DeregisterFirst` switch).

### Next dispatch

Post-bundle handoff to NEW ORCHESTRATOR INSTANCE for Schwab API integration (multi-day brainstorm + writing-plans + executing-plans cycle). Operator-decided sequencing.

---

## 2026-05-13 Phase 10 Sub-bundle E ship: CLOSES Phase 10 — arc closer aggregate

**Sub-bundle E SHIPPED 2026-05-13** at `38dbac3` (integration merge of `phase10-bundle-E-process-grade-trend-and-polish`). 8 commits = 6 task-impl (T-E.1..T-E.6 + T-E.4 closer) + 1 Codex-fix + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — ties FASTEST Phase 10 chain (matches Sub-bundle B + C + Phase 9 Sub-bundle E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 3147 worktree-side → 3254 (+107 net; ~3257 main HEAD post-merge). Ruff 18 unchanged. Schema v17 unchanged.

**Cross-bundle T-A.7 pin UN-SKIPPED at T-E.3 SAME COMMIT** (`fb6e48a`) — `test_existing_dashboard_vm_has_unresolved_material_field` no longer carries `@pytest.mark.skip` decorator + passes against retrofitted DashboardVM. Plan §H named 6 base-layout VMs to retrofit; implementation retrofitted **10** (defense-in-depth catching 4 additional VMs that extend base.html.j2 per CLAUDE.md gotcha — ReviewVM / CadenceCompleteVM / ReviewsPendingVM / TradeDetailVM).

### 7-surface operator-witnessed gate ALL PASS via Chrome MCP on port 8081

- **S1 inline** pytest+ruff+verify_phase10 PASS at 3254 tests.
- **S2** `/metrics/process-grade-trend` PASS — spec §4.8 reference + numeric encoding A=4..F=0 visible per lesson #19 + N=10 window + 3 closed-reviewed trades + 7-metric Class column per §A.21 matrix; all 7 metrics suppressed at n=3<5 per spec §5.4; ZERO console errors.
- **S3 banner FIRES** PASS — planted discrepancy id=1 (DHC #2 stop_mismatch material) → dashboard shows §A.18 banner "1 unresolved material reconciliation discrepancy" + "Resolve via CLI" CLI hint.
- **S4 banner CLEARS** PASS — reverted discrepancy to acknowledged_immaterial → banner absent from DOM; count=0 restored.
- **S5** `/metrics` umbrella PASS — 8 tile descriptions verified.
- **S6 T-E.5 form POST** PASS — `equity_dollars=2000` + note "S6 gate test 2026-05-13" submitted via curl (form_input + computer click did not trigger HTMX events; curl with HX-Request header reproduced operator browser submit semantics) → HTTP 204 + `HX-Redirect: /metrics/capital-friction` per Phase 5 R1 M2 LOCK; snapshot #3 created in DB with server-stamped `snapshot_date='2026-05-13'` per lesson #4 + Phase 8 server-stamping discipline; HX-Redirect target resolves to capital-friction with LIVE badge $2000.00; multi-run trend shows $1800 → $2000 transition by date correctly; ZERO console errors.
- **S7 T-E.6 trade detail indicator** PASS — DHC #2 with planted discrepancy shows "⚠ Unresolved reconciliation discrepancy (1)" at top per electives §2 Task E.6 acceptance; after revert, indicator section hidden entirely per "hide when empty" rule.

### Production state post-gate

- Snapshot #3 left in production as valid operator cash-basis reading per dispatch brief §7 #11 default (operator can update via CLI any time).
- Discrepancy id=1 reverted to `acknowledged_immaterial` with reason "post-S3/S4/S7 gate cleanup 2026-05-13".
- 30 reconciliation_discrepancies all resolved (production state restored).

### Phase 10 arc closer aggregate (return report §9)

| Sub-bundle | Commits | Codex rounds | Tests delta | Critical-resolved | Major-resolved | ACCEPT-WITH-RATIONALE | CLAUDE.md gotchas |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 15 | 4 | +128 | 0 | 3 | 0 | 0 |
| B | 9 | 2 | +73 | 0 | 2 | 0 | 0 |
| C | 8 | 2 | +84 | 0 | 2 | 0 | 0 |
| D | 12 | 3 | +102 | 0 | 5 | 0 | 0 |
| E | 8 | 2 | +107 | 0 | 1 | 0 | 0 |
| **Total** | **52** | **13** | **+494** | **0** | **13** | **0** | **0** |

**Phase 10 closer highlights:**

- **52 commits across A+B+C+D+E** (34 task-impl + 12 Codex-fix + 5 return-reports + 1 ruff).
- **13 Codex rounds total** (4+2+2+3+2).
- **+494 cumulative fast tests** (final 3254 worktree-side / ~3257 main HEAD; from pre-Phase-9 baseline 1957 → +1297 across Phase 9 + Phase 10).
- **ZERO Critical findings entire arc.**
- **ZERO ACCEPT-WITH-RATIONALE banked** — **cleanest 5-bundle arc-final state in project history.** Phase 9 had 4 banked (2 A + 1 B-later-resolved-C + 1 C; D + E clean).
- **ZERO CLAUDE.md gotchas promoted** — every defect class hit during Phase 10 was already covered by existing gotchas. Phase 9 promoted 6.
- **27 V2.1 §VII.F amendments pending** (3 A + 5 B + 5 C + 5 D + 4 E + 2 Phase 9 + 3 elsewhere). See T-E.4 "Phase 10 closer" section near end of file for full enumeration.
- **3 post-Phase-10 standalone dispatches unblocked** (cleanup-script `-DeregisterFirst` + test-runtime xdist + §8.4 Corporate_Actions MVP).
- **§A.0 ZERO-new-schema LOCK preserved** through entire arc — schema v17 unchanged through Phase 10 V1.

### 8 operator-visible Phase 10 surfaces shipped

1. `GET /metrics` (A T-A.8) — umbrella index.
2. `GET /metrics/trade-process` (B T-B.3) — 7 cohort tabs × 22 §3.1 metrics.
3. `GET /metrics/hypothesis-progress` (B T-B.5) — 4 cohort row + tripwire + transition timeline.
4. `GET /metrics/tier-comparison` (C T-C.2) — 4-cohort Wilson + bootstrap CIs + descriptor.
5. `GET /metrics/deviation-outcome` (C T-C.3) — doctrine deviation class + decision criterion.
6. `GET /metrics/capital-friction` (D T-D.2) — 6 §3.4 metrics + PROVISIONAL/LIVE dynamic badge + trend.
7. `GET /metrics/maturity-stage` (D T-D.4) — per-open-position table.
8. `GET /metrics/identification-funnel` (D T-D.6) — per-run + 30-trading-session trend.
9. `GET /metrics/process-grade-trend` (E T-E.2) — per-trade markers + rolling lines per §A.21.

Plus 4 cross-bundle integrations:
- Reconciliation banner on 10 base-layout pages (E T-E.3 retrofit; A-D inheritance).
- T-B.7 lucky_violation_R on Phase 6 review form (B elective).
- T-E.5 web-form snapshot capture at `/account/snapshot` (E elective).
- T-E.6 per-trade discrepancy indicator on `/trades/{id}` (E elective).

### Phase 11 candidate triage UNBLOCKED

Phase 11 triage owned by operator+orchestrator at next session. Pre-banked candidates enumerated at T-E.4 closer section (line 1788+):
- §8.4 Corporate_Actions MVP (standalone post-Phase-10).
- Schwab API Phase A integration.
- `mistake_cost_R_rolling_N_total` sum-class with bootstrap CI.
- Schwab inception-CSV ingestion.
- `account_equity_snapshots.equity_dollars` cash-basis-vs-MTM semantic formalization.
- Orphan discrepancy detail surface.
- Per-cohort paused-interval filter (T-C.5 UI pattern reuse).
- 27 V2.1 §VII.F amendments triage.

### Cross-references

- Sub-bundle E return report: `docs/phase10-bundle-E-return-report.md`.
- Sub-bundle E dispatch brief: `docs/phase10-bundle-E-executing-plans-dispatch-brief.md`.
- Phase 10 closer details (T-E.4 commit 4a666d1): bottom of this file at line 1788+.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment: `docs/phase10-electives-amendment.md`.
- Post-Phase-10 standalone dispatch backlog: 2026-05-13 entries below (cleanup-script + test-runtime).

---

## 2026-05-13 Phase 10 Sub-bundle D ship: 5 spec amendments + 4 forward-binding lessons (FIRST PROVISIONAL/LIVE dynamic contract)

**Sub-bundle D SHIPPED 2026-05-13** at `a71cc24` (integration merge of `phase10-bundle-D-capital-maturity-funnel`). 12 commits = 7 task-impl (T-D.1..T-D.7) + 3 Codex-fix (R1+R2+R3) + 2 return-report; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering. ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 3045 worktree-side → 3147 (+102 net; upper end of +67..+104 projection; matches Sub-bundle A +128 / B +73 / C +84 overshoot precedent). S1 inline gate ~6:00 wall-clock. Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (return report §5)

1. **D1: Dispatch brief §0.8 PROVISIONAL/LIVE math wording.** Brief said `LIVE: denominator = max(capital_floor_constant_dollars, snapshot.equity_dollars)`. Plan §A.6 line 222 + the shipped `resolve_live_capital_denominator_dollars` (Sub-bundle A) return `snapshot.equity_dollars` directly (NO max-with-floor). Implementation followed plan + shipped code. **Amendment:** brief §0.8 wording should remove the `max()` qualifier.

2. **D2: Plan §A.19 SQL references `criterion_results.criterion_name`; actual schema is `candidate_criteria`.** Plan §A.19 lines 463-490 use `criterion_results cr ON cr.candidate_id ...` in the worked SQL example. Actual schema table (migration 0001:48) is `candidate_criteria` with the same column names. Implementation uses `candidate_criteria`. **Amendment:** plan §A.19 should match actual table name OR clarify the example is logical pseudo-schema.

3. **D3: Capital-friction trend window size not explicitly pinned.** Plan §G T-D.1 + spec §4.4 do not explicitly pin the multi-run trend window size for capital-friction (spec §4.4 only specifies "≥5 runs"). Implementation reused the funnel surface's 30-trading-session window for operator-readability parity. **Amendment:** plan §G T-D.1 wording — add explicit window-size lock.

4. **D4: `MaturityStageRow` carries `capital_denominator_dollars` + `capital_denominator_badge_text` fields not in plan §G T-D.3 acceptance.** Per Codex R1 M#1 + R2 M#1 fixes (verbatim plan §A.6 line 233 inline-text LOCK required visibility per-row), the dataclass gains both fields beyond what plan §G T-D.3 enumerated. **Amendment:** plan §G T-D.3 acceptance criteria.

5. **D5: `IdentificationFunnelPoint.aplus_take_rate_per_run` is NOT clamped to [0, 1].** Per Codex R1 M#3 fix, the rate is honestly emitted as `aplus_taken / aplus_id` without bounding. Plan §G T-D.5 + spec §3.6 say "proportion" implying [0, 1] in typical reading. **Amendment:** clarify "≥0; values >1 surface as data-quality anomaly signals (not clamped)" — see lesson #25.

### 4 forward-binding lessons for Sub-bundle E dispatch (return report §9; #23-#26 in cumulative catalog)

1. **#23 (NEW from D R1 M#1):** Plan-prescribed verbatim explanatory text MUST surface through a dedicated dataclass FIELD + template rendering target (NOT a `title="..."` hover-only attribute, which fails mobile + non-mouse usage AND loses audit-trail intent). Discriminating-test pattern: assert `data-{marker}=` substring in body PLUS assert `title="{format_prefix}"` substring absent. Forward-relevance for Sub-bundle E: process-grade-trend chart annotations + reconciliation badge text MUST follow this pattern.

2. **#24 (NEW from D R1 M#2):** Session-anchor read/write mismatch family extension — when a plan pins per-run aggregation on `pipeline_runs.started_ts.date()`, the implementation MUST use exactly that column (NOT `data_asof_date`, NOT `action_session_date`). These diverge on weekend/holiday runs in ways that silently drop or misbucket historical data points. Discriminating-test pattern: seed a row with `started_ts` and `data_asof_date` divergent, assert correct inclusion.

3. **#25 (NEW from D R1 M#3):** Bounded-range metrics MUST distinguish mathematically-bounded cases (e.g., `num <= denom` by SQL construction → rate ∈ [0, 1] guaranteed) from two-source aggregates (numerator + denominator independently computed → ratio can exceed 1 in anomaly cases). Clamping the latter HIDES data-quality issues. Pattern: bounded-by-construction → assert bounds; two-source → allow honest values + add anomaly badge surface. Forward-relevance for Sub-bundle E: process_grade aggregates may face the same.

4. **#26 (NEW from D R3 m#1):** SQL `ORDER BY` clauses on potentially-tied columns MUST include a deterministic tiebreaker (typically `id DESC`). Plan + Codex consistently catch nondeterminism in latest-record queries.

### Production-state observation (not blocking)

Maturity-stage surface renders 4 of 5 open positions (DHC/YOU/VSAT/CVGI shown; **LAR missing**). Production has 5 open trades per Phase 9 + Phase 10 prior gates. Root cause: `swing/data/repos/daily_management.list_open_position_active_snapshots(conn)` clamps to latest `data_asof_session` per trade; LAR has no recent daily_management snapshot covering current session. This is a **daily-management capture gap** at the operator-flow level, NOT a code regression. Operator may record fresh LAR snapshot via daily-management surface to surface LAR in maturity-stage.

### Post-merge state

- HEAD on main: `a71cc24` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (unchanged through Sub-bundles A+B+C+D).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle E executing-plans dispatch UNBLOCKED (CLOSES Phase 10).
- Cumulative pending V2.1 §VII.F amendment candidates: **22** entering Sub-bundle E (was 17 entering D; +5 this dispatch). Phase 10 arc cumulative ACCEPT-WITH-RATIONALE: ZERO (cleanest 4-bundle arc state in project history).
- 6 worktree husks pending cleanup-script (4 Phase 9 still-registered + 1 Sub-bundle C orphan + 1 Sub-bundle D orphan).

### Cross-references

- Sub-bundle D return report: `docs/phase10-bundle-D-return-report.md`.
- Sub-bundle D dispatch brief: `docs/phase10-bundle-D-executing-plans-dispatch-brief.md`.
- Plan §G (lines 1354-1550) consumed; AMENDED §A.6 + §A.7 + §A.18 + §A.19 + §A.20 from Sub-bundle A inherited.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.

---

## 2026-05-13 Phase 10 Sub-bundle C ship: 5 spec amendments + 3 forward-binding lessons + cleanup-script gap surfaced

**Sub-bundle C SHIPPED 2026-05-13** at `a814006` (integration merge of `phase10-bundle-C-tier-and-deviation`). 8 commits = 5 task-impl (T-C.1..T-C.5) + 1 Codex-fix + 2 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — ties FASTEST Phase 10 chain (B + Phase 9 E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 2961 worktree-side → 3045 (+84 new; ~3048 main post-merge from 2964 baseline; above projection +34..+56; matches Sub-bundle A +128 + B +73 overshoot precedent). Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (return report §5)

1. **T-C.1 `cohort_relative_to_aplus` rendering.** Spec §3.3 row 147 defines as `cohort_expectancy_R / aplus_expectancy_R - 1` (delta proportion); dispatch brief §0.9 LOCK specified PERCENT raw-ratio `cohort_expectancy / aplus_expectancy * 100`. Implementation followed brief (binding implementer-facing artifact). Two semantically distinct metrics exist at the same numeric value: §3.3's "what fraction of A+ does this cohort achieve?" (0–200% typical) vs §3.7's "how far above/below A+" (-100% to +∞%). **Amendment:** spec §3.3 + §3.7 text should explicitly state rendering-unit semantics + the two-metric split.

2. **T-C.1 `cohort_doctrine_deviation_class` baseline enum value.** Spec §3.7 row 205 uses `"0"` as A+ baseline cohort's deviation class; implementation uses `"baseline"` string. Rationale: text field rendering; integer "0" would visually collide with the descriptive enum strings + operator's mental model that baseline IS a class label. Test pins `"baseline"` for A+. **Amendment:** cosmetic spec wording.

3. **T-C.5 filter SQL predicate.** Electives amendment §2 specified `resolution IS NULL`; schema reality (Phase 9 migration 0017) stores resolution as NOT NULL with sentinel `'unresolved'` enum default. Implementation uses `resolution = 'unresolved'` matching `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` Phase 9 Sub-bundle B convention. **Amendment:** electives amendment §2 wording.

4. **T-C.5 filter threading.** Amendment specified `CohortFilter` enum OR new bool param on tier + deviation VMs. Implementation chose bool throughout (compute + VM + route layers). Filter applied AT COMPUTE LAYER (before classification) so surface-locked cohort suppression cascade fires correctly when filter brings n<5. **Amendment:** minor; aligns with "new bool param" alternative.

5. **T-C.5 toggle href shape.** Amendment showed `<a href="/metrics/tier-comparison?exclude_discrepancies=1">` (absolute path). Implementation uses relative query href `<a href="?exclude_discrepancies=1">` + `<a href="?">` (Codex R1 M#1 fix). Relative form is more robust under mounted-app / root-path deployments. **Amendment:** illustrative-vs-binding-shape clarification.

### 3 forward-binding lessons for Sub-bundle D dispatch (return report §9; #20-#22 in cumulative catalog)

1. **#20: body-wide unit-substring assertions are non-discriminating when seed text contains the same substring** (e.g., decision-criteria contains literal `%` from "win rate > 30%"). Discriminating-test pattern: seed a specific worked example + assert the EXACT rendered numeric+unit substring at the cell location, NOT a body-wide `unit_string in body` check. Forward-relevance for Sub-bundle D: capital-friction percent-unit metrics + PROVISIONAL/LIVE badge text should follow this pattern.

2. **#21: toggle/filter links use relative query href** (`href="?key=value"` to set + `href="?"` to clear) rather than absolute path hrefs. Survives mounted-app / root-path deployments. Forward-relevance: capital-friction + identification-funnel + maturity-stage surfaces may need similar per-cohort or per-stage filter toggles.

3. **#22: per-cohort filters affecting cell suppression MUST be applied at compute layer** (before surface-locked suppression cascade fires). Applying at VM-layer post-compute would require duplicating suppression logic. Discriminating test: seed cohort with N>=5 where K trades have filter-trigger condition; filter-active brings cohort to (N-K) AND re-triggers suppression if (N-K) < surface floor.

### Cleanup-script gap surfaced (operator-decided 2026-05-13)

Operator verified the cleanup-script (`cleanup-locked-scratch-dirs.ps1`) catches **only orphaned** worktree dirs (deregistered from `git worktree list` but on-disk dir remains). Currently registered worktrees are by-design skipped (lines 215-234 short-circuit on `$isRegistered = $true`). The 4 remaining Phase 9 husks (B/C/D/E) are still registered and require `git worktree remove --force` first (deregisters; likely fails at on-disk delete due to ACL lock → produces orphan → script catches on next run). **Operator concurred with option 2: extend script with `-DeregisterFirst` switch** that drives `git worktree remove --force` against matched paths before orphan-discovery. **DEFERRED as separate orchestrator dispatch on `main`** (read-side, non-blocking, separate PR from Phase 10 sub-bundles). 5 husks pending after this dispatch (4 Phase 9 + new Phase 10 Sub-bundle C).

### Test-runtime concern surfaced 2026-05-13

Fast pytest suite at 3045 tests is 5:15 wall-clock (~103ms/test average; slow for unit-style). Orchestrator recommendation queued: (1) `pytest --durations=30` profile pass; (2) `pytest-xdist -n auto` parallelization (highest ROI; ~3-5x wall-clock reduction at zero coverage cost); (3) session-scoped schema fixtures audit. **DEFERRED as separate orchestrator dispatch.** Reduce-tests-with-coverage-preservation is the WRONG frame — each test exists as a discriminating-pin; the real lever is eliminating per-test fixture overhead.

### Post-merge state

- HEAD on main: `a814006` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert from Sub-bundle A; unchanged through Sub-bundle B + C).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle D executing-plans dispatch UNBLOCKED.
- Pending V2.1 §VII.F amendment candidates cumulative: **17** entering Sub-bundle D (was 12 entering C; +5 this dispatch). Phase 10 arc cumulative ACCEPT-WITH-RATIONALE: ZERO (A+B+C clean record).

### Cross-references

- Sub-bundle C return report: `docs/phase10-bundle-C-return-report.md`.
- Sub-bundle C dispatch brief: `docs/phase10-bundle-C-executing-plans-dispatch-brief.md`.
- Plan §F (lines 1257-1334) consumed verbatim; AMENDED §A.7 + §A.18 + §A.5.1 from Sub-bundle A inherited.
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment §2 Task C.5: `docs/phase10-electives-amendment.md`.

---

## 2026-05-13 Post-Phase-10 standalone dispatches (deferred per operator decision; sequence AFTER Phase 10 Sub-bundles D + E ship)

Operator decision 2026-05-13 (mid-Phase-10, post-Sub-bundle-C-ship): two operational improvements surfaced during the Sub-bundle C dispatch + post-ship triage. Both are **read-side / infrastructure-side**, non-blocking for Sub-bundles D + E, and **DEFERRED as separate orchestrator dispatches AFTER Phase 10 completes** (Sub-bundle E ship closes the phase).

### Item 1 — Extend `cleanup-locked-scratch-dirs.ps1` with `-DeregisterFirst` switch

**Problem:** the script's worktree-orphan discovery (lines 215-234) currently catches ONLY orphaned worktree dirs (deregistered from `git worktree list` but on-disk dir remains due to Windows `.tmp/pytest-of-rwsmy/` ACL-lock pattern). Worktrees that are still registered in `git worktree list` are by-design skipped. The standard post-merge workflow is two-step: (a) operator/orchestrator runs `git worktree remove --force`; (b) if on-disk delete fails (ACL lock), the dir is now orphaned + the cleanup-script catches it on next run. Workflow gap: between step (a) and step (b), the operator's environment carries registered husks indefinitely if step (a) is skipped.

**Evidence:** at handoff 2026-05-13 mid-Phase-10, 11 worktree husks were pending operator cleanup-script per the handoff brief enumeration. After the operator's cleanup pass, 4 Phase 9 husks remained (B/C/D/E) because they were still git-registered (step (a) was never run on them). Operator confirmed cleanup-script-as-shipped does not catch them.

**Proposed extension:** add a `-DeregisterFirst` switch that drives `git worktree remove --force` against paths matching `^.worktrees/phase\d+-.*` (or accepts an explicit list) before the orphan-discovery pass. After deregistration completes, the existing orphan-discovery pass picks up the now-orphaned dirs + cleans them.

**Estimated effort:** ~30-45 min orchestrator-or-implementer dispatch on `main`. Read-side / infrastructure-side; no production-code impact; cannot conflict with Phase 10 sub-bundle worktrees (D + E will run on their own worktree branches with their own husks).

**Sequencing:** AFTER Sub-bundle E ship closes Phase 10. Avoids worktree-management changes mid-arc.

### Item 2 — Test-runtime analysis + improvements (zero-coverage-loss interventions)

**Problem:** fast pytest suite is at 3045 tests / ~5:15 wall-clock on Windows + Python 3.14 (Sub-bundle C post-ship). Per-test overhead average is ~103ms which is slow for unit-style tests (typical: 10-30ms). Going to ~3100+ tests at Sub-bundle D + E ship pushes past 6 min wall-clock. Operator surfaced 2026-05-13 the concern that approaching 3000 tests is making the dev-loop test-feedback latency painful.

**Wrong frame:** "reduce tests to retain coverage" — each test exists as a discriminating-pin for a Codex finding or regression-prevention assertion; deletion re-opens closed risks. The right frame is **eliminate per-test fixture overhead**, not test count.

**Recommended interventions in order of ROI (zero coverage loss):**

1. **Profile first (5 min, zero risk):** `pytest --durations=30` to identify the 80/20 hotspots. Without profiling, every other intervention is guessing.
2. **`pytest-xdist` parallelization (highest ROI; estimated ~3-5x wall-clock reduction):** single-line dependency add + `-n auto` in pyproject. With 8+ cores this is a 5 min → ~90s win at zero coverage cost. Risks: SQLite contention (file-based DBs need per-worker tmp dirs — `tmp_path_factory` already gives this); shared `pipeline_runs` lease tests need careful scoping. Most of the suite is already worker-safe by construction.
3. **Session/module-scoped schema fixtures:** large fraction of tests do `tmp_path → ensure_schema(conn) → seed → assert`. `ensure_schema` walks all 17 migrations on every call. Caching a fresh-DB template at session scope + `shutil.copy()` per test is ~10-50ms saved per test × thousands of tests = several minutes recovered. Medium-impact; fixture refactor required.
4. **TestClient lifespan audit:** `with TestClient(app) as client:` enters lifespan (starts `price_fetch_executor`); plain `TestClient(app)` does not. Many web tests use the `with` form even when they don't need the executor. Mechanical sweep.
5. **Audit duplicate discriminating-tests:** some Phase 9 + 10 Codex rounds added 2-3 tests pinning the same invariant via different fixtures. Manual audit; small wins; some risk of removing a real pin (requires careful per-test review).
6. **Move E2E integration tests behind `slow` marker:** `tests/integration/test_phase8_pipeline_walkthrough.py` already slow-marked. Audit `tests/integration/` for others. Doesn't reduce coverage, just reduces fast-suite footprint.

**Expected outcome:** profile + xdist together likely 5 min → ~1-1.5 min with zero coverage loss. Fixture-scope refactor adds another 30-60s reduction.

**Estimated effort:** ~1-2 hr orchestrator profile pass + ~30 min xdist integration + ~2-4 hr fixture-scope refactor if profile evidence warrants. Dispatch as a standalone read-side / infrastructure-side bundle.

**Sequencing:** AFTER Sub-bundle E ship closes Phase 10. Avoids test-runner / fixture changes mid-arc that could mask Codex-detectable regressions in Sub-bundle D + E.

### Cross-references

- Sub-bundle C return report §7 #7-#8 (this bundle surfaced the gap).
- Cleanup-script: `cleanup-locked-scratch-dirs.ps1` lines 215-234 (orphan-only discovery branch).
- Test-runtime baseline: 2964 → 3045 worktree-side at Sub-bundle C ship (~5:15 wall-clock).

---

## 2026-05-13 Phase 10 Sub-bundle B ship: 5 spec amendments + 2 forward-binding lessons + 4 V2 candidates banked

**Sub-bundle B SHIPPED 2026-05-13** at `6ed0f35` (integration merge of `phase10-bundle-B-trade-process-and-hypothesis-progress`). 9 commits = 7 task-impl (T-B.1..T-B.7 incl. T-B.7 elective) + 1 Codex-fix + 1 return-report; **2 Codex rounds → NO_NEW_CRITICAL_MAJOR** — FASTEST Phase 10 chain (matches Phase 9 Sub-bundle E precedent). ZERO Critical + ZERO ACCEPT-WITH-RATIONALE.

Tests: 2895 worktree-side → 2951 (+73 new tests; +56 net; matches +46..+75 dispatch brief projection); 2899 → 2960 main HEAD. Ruff 18 unchanged. Schema v17 unchanged.

### 5 V2.1 §VII.F amendment candidates (4 from return report §5 + 1 surfaced at orchestrator-driven gate)

1. **Plan §E Task B.1 acceptance text — `mistake_cost_R` aggregator source.** Plan said "prefer `review_log.total_mistake_cost_R` aggregate when present; fall back to per-trade compute when absent"; implementation always recomputes per-trade because `review_log` is **CADENCE-grain** (one row per daily/weekly/monthly review window covering N trades) with NO per-trade foreign key. The cadence aggregate CANNOT be cleanly mapped onto a cohort-grain sum at the metrics layer. Discriminating regression test `test_mistake_cost_R_recomputes_per_trade_ignoring_review_log_aggregate` pins the per-trade-recompute behavior. **Amendment:** plan §E Task B.1 should say "always re-compute via Phase 6 helpers; cohort-grain sum is reproducible from per-trade fields." V2 candidate: add `review_log_trade_links` audit table; cohort aggregator could then prefer frozen review-time values for already-reviewed trades + recompute only for unreviewed.

2. **Plan §E Task B.2 acceptance text — sentinel value for "All closed trades" toggle.** Plan didn't specify a URL-parameter sentinel. Implementation uses `__all__` as the sentinel (`?cohort=__all__`) to avoid collision with any legitimate cohort name containing the literal "all". Documented in the module docstring. **Amendment:** plan §E Task B.2 should include the sentinel choice explicitly.

3. **Plan §A.5.1 + spec §3.2 `cumulative_R_pct_of_capital` rendering unit.** Plan §A.5.1 specifies the metric as "proportion" (dimensionless); implementation stores + surfaces in **PERCENT units** (e.g., `-1.667` means `-1.667%`, NOT `-1.667 ratio` = `-166.7%`) because spec §3.2 `distance_to_absolute_loss_tripwire = absolute_loss_tripwire_pct - abs(min(0, cumulative_R_pct_of_capital))` requires comparing against `absolute_loss_tripwire_pct` which is in percent units per migration 0008 (e.g., `5.0` = `5%`). Conversion `sum(dimensionless ratios) * 100` happens inside `_build_cohort_vm`. **Amendment:** plan §A.5.1 + spec §3.2 should explicitly state the rendering unit.

4. **Electives amendment §2 Task B.7 acceptance text — existing display assumption.** Amendment said the new field renders "symmetrically alongside the existing `mistake_cost_R` display." Empirical verification of the Phase 6 template showed there was **NO pre-existing `mistake_cost_R` display** — only the operator-input form for `realized_R_if_plan_followed`. Implementation surfaces BOTH `mistake_cost_R` AND `lucky_violation_R` as derived display values in a new `<dl class="counterfactual-pair">` block placed BEFORE the existing form. Symmetric rendering criterion is met WITHIN the new block. **Amendment:** electives amendment §2 should be corrected: "the new block surfaces BOTH `mistake_cost_R` AND `lucky_violation_R` as derived per-trade display values; the existing form is unchanged."

5. **(GATE-SURFACED 2026-05-13)** **Plan §E Task B.2 acceptance text — cohort-tab enumeration scope.** Plan said `test_vm_renders_4_cohort_tabs_plus_all_toggle` expecting "5 tabs total" (4 registered + "all"). Implementation surfaces 7 tabs at production gate (4 pre-registered + 2 orphan-label + "All") because production has 2 orphan-labeled closed trades ("inaugural trade test" with 1 closed VIR + "Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness" with 2 closed). Hiding orphan-labeled cohorts would hide closed-trade data from the operator. **Sensible deviation; not banked in return report but caught at orchestrator-driven S2 gate via Chrome MCP read_page.** **Amendment:** plan §E Task B.2 should say "render tabs for ALL distinct `hypothesis_label` values across closed trades (registered + orphan) + "All" toggle; default-active is FIRST registered cohort regardless of orphan presence."

### 2 forward-binding lessons for Sub-bundle C dispatch (return report §8)

1. **Cadence-grain audit tables CANNOT be cleanly mapped to cohort-grain metrics without per-trade FK.** Sub-bundle B R1 Major #1 surfaced the mismatch between `review_log` (cadence-grain, no trade FK) and cohort-grain `mistake_cost_R` sum. If Sub-bundle C (tier-comparison + deviation-outcome) or future sub-bundles encounter similar cadence-grain audit columns (e.g., `reconciliation_runs.summary_json` for cohort-grain "data-quality" gating), document the mismatch + always re-compute from per-trade source data. **Discriminating-test pattern** (canonical regression-pin): plant a conflicting cadence row + assert metric reflects per-trade compute, NOT the planted aggregate. Sub-bundle C dispatch brief §0.5/§0.6 should add this as forward-binding lesson #18.

2. **Unit-semantic precision needs explicit rendering pin (percent vs proportion).** Sub-bundle B's `cumulative_R_pct_of_capital` rendered in PERCENT units to match the `absolute_loss_tripwire_pct` comparison. Future tier-comparison metrics (`cohort_relative_to_aplus`, `cohort_expectancy_relative_to_aplus_pct`) likely face the same: explicit rendering-unit pin in the VM + template + discriminating test is required at writing-plans time. Sub-bundle C dispatch brief §0.5/§0.6 should add this as forward-binding lesson #19.

### 4 V2 candidates banked (return report §7)

1. **`review_log_trade_links` audit table** — would unlock cadence-prefer for already-reviewed trades; recompute only for unreviewed. Connects to Phase 11 candidate scoping.
2. **Per-cohort "exclude paused-interval trades" filter** — same UI pattern as Sub-bundle C's T-C.5 "exclude trades with unresolved discrepancies" filter family. Sub-bundle C may surface the reuse pattern when T-C.5 lands.
3. **`mistake_cost_R_per_trade` Class B representation alongside cohort sum** — implementation surfaces BOTH `MetricCellB` (Class B mean) AND `PointMetricCell` (cohort sum); spec §3.1 only enumerates "cohort sum." V2 candidate: clarify spec or drop the Class B representation if redundant.
4. **`canonicalize_hypothesis_label` query-time canonicalization** — `list_trades_for_cohort` already canonicalizes; verify that `count_per_cohort` orphan-label fallback path also canonicalizes (current implementation uses the registry's stored name directly + the orphan label as-is from `trades.hypothesis_label`). Edge case: an orphan trade with a non-canonicalized stored label might appear separately from a canonicalized-form match. Low risk in V1 (writer canonicalizes at persist time); banked for V2 audit.

### Post-merge state

- HEAD on main: `6ed0f35` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert from Sub-bundle A; unchanged through Sub-bundle B).
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle C executing-plans dispatch UNBLOCKED.
- Sub-bundle B added 4 new sub-VM exclusions to `tests/web/test_view_models/test_base_layout_vm_coverage.py::_SUB_VM_EXCLUSIONS`: `CohortTabVM`, `CohortProgressVM`, plus the existing `ConfidenceBadgeVM` / `ProvisionalBadgeVM` / `SuppressionRowVM`. Sub-bundle C dispatch brief should propagate the pattern: new sub-VMs ending in `VM` that compose into a page VM (not BaseLayoutVM-extending) should be added to the exclusion set in the same commit.

### Cross-references

- Sub-bundle B return report: `docs/phase10-bundle-B-return-report.md`.
- Plan §E (lines 1063-1254; AMENDED at integration triage per amendments #1, #2, #5 above + §A.5.1 percent-unit clarification #3).
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment §2: `docs/phase10-electives-amendment.md` (amendment #4 above corrects "existing display" assumption).
- Sub-bundle C dispatch brief: TBD (orchestrator drafts post-merge; will propagate T-C.5 elective + 2 NEW forward-binding lessons + Sub-bundle A AMENDED §A.7 interface).
- Pending V2.1 §VII.F spec amendments cumulative count: **12** (2 Phase 9 D/E + 3 Sub-bundle A + 4 Sub-bundle B return-report + 1 Sub-bundle B gate-surfaced + 2 Sub-bundle A return-report orphans-from-Phase-10-spec).

---

## 2026-05-13 Phase 10 Sub-bundle A ship: spec amendments + forward-binding lessons + V2 candidates banked

**Sub-bundle A SHIPPED 2026-05-13** at `096de83` (integration merge of `phase10-bundle-A-shared-honesty-utility`). 15 commits = 11 task-impl + 3 Codex-fix + 1 return-report; 4 Codex rounds → NO_NEW_CRITICAL_MAJOR; ZERO Critical + ZERO ACCEPT-WITH-RATIONALE; +128 fast tests (2767 → 2895); ruff 18 unchanged; schema v17 unchanged.

### 3 V2.1 §VII.F amendment candidates (plan-text corrections; banked from return report §8)

1. **Plan §D Task A.1 Wilson CI reference value drift.** Plan acceptance criterion locked `k=2,n=4 → [0.094, 0.901]` (Wilson-with-continuity-correction); implementation chose standard Wilson (yields `[0.150, 0.850]`); plan's other two reference values `k=0,n=20 → [0.000, 0.161]` + `k=20,n=20 → [0.839, 1.000]` match standard Wilson exactly. Plan §D Task A.1 should be amended to either (a) correct the k=2,n=4 reference to `[0.150, 0.850]` (matches standard Wilson; downstream comparable to `statsmodels.stats.proportion_confint(method='wilson')`); OR (b) explicitly require Wilson-with-continuity-correction + update implementation. Implementer chose (a) per Wikipedia primary formula + statsmodels-default alignment. **V2.1 §VII.F routing recommended:** standalone amendment dispatch or fold into Phase 10 plan revision.

2. **Plan §A.5 `read_at_trade_time_policy` signature.** Plan signature `read_at_trade_time_policy(conn, *, trade: Trade) -> RiskPolicy` assumes `Trade` dataclass carries `risk_policy_id_at_lock` field. Phase 9 Sub-bundle A added the column via ALTER but did NOT extend `Trade` dataclass (`_TRADE_SELECT_COLS` in `swing/data/repos/trades.py` omits it). Implementation signature is `read_at_trade_time_policy(conn, *, policy_id_stamp: int | None) -> tuple[RiskPolicy, bool]` with two convenience accessors `get_trade_policy_id_stamp(conn, *, trade_id: int)` + `get_review_policy_id_stamp(conn, *, review_id: int)` added in `swing/metrics/policy.py`. Sub-bundle B consumers fetch the stamp from DB then pass into resolver. Plan §A.5 to be amended to match implementation; OR alternatively V2-disruptive option: extend `Trade` dataclass to include `risk_policy_id_at_lock` (every existing consumer accepts new field).

3. **Plan §A.6 `BaseLayoutVM.stale_banner` type.** Plan says `stale_banner: bool = False`; implementation chose `stale_banner: str | None = None` to match existing base-layout VM pattern (`DashboardVM`/`PipelineVM`/`JournalVM`/`WatchlistVM`/`ConfigVM` all use `str | None`). `base.html.j2` renders `{% if vm.stale_banner %}` + included partial does `{{ vm.stale_banner }}` (substitutes banner text). With `bool = False` the rendered banner would be literal "True"/"False" text. Plan §A.6 to be amended to `str | None = None`.

### Plan §A.7 + §D Task A.1 amendments ALREADY APPLIED in-tree

Codex R2 + R3 caught the SAME failure-mode twice (plan-text drift from code interface changes). Implementer amended plan §A.7 + §D Task A.1 IN THE WORKTREE during Codex R2 + R3 fix commits (`e32f71c` + `75dd63f`). These are NOT pending amendments — they LANDED at merge `096de83`. The 3 candidates above are SEPARATE from those (plan-text-vs-impl divergences caught at return-report-time, not at Codex-time).

### 2 forward-binding lessons for Sub-bundle B+ dispatch (banked from return report §10)

1. **Plan §A.7 binding-interface amendments flow into plan text in SAME commit as code change.** Codex R2 Major #1 + R3 Major #1 in Sub-bundle A caught the SAME failure-mode twice: code-level interface changes (adding `HonestyBadges.window_not_full_warning` in R1; making `badges_for_n` public in R1) were NOT reflected in binding plan §A.7 text, even though Sub-bundles B-E read §A.7 as binding. **Pre-empt for Sub-bundle B+ dispatch brief §0.5:** when implementer changes any §A.7-listed interface element (HonestyBadges fields, function signatures, Decoupling discipline assignment), update plan §A.7 IN THE SAME COMMIT. Brief watch item: "if implementer adds new public function / dataclass field / signature param in `swing/metrics/honesty.py`, plan §A.7 binding interface MUST update in-tree to match."

2. **Statistical helpers with multiple textbook-correct variants need explicit spec pin at writing-plans time.** Wilson CI standard-vs-continuity-correction divergence (deviation #1 above) is a textbook ambiguity. Plan §A.7 cited "Wikipedia formula" but Wikipedia documents BOTH variants; plan's reference values mixed the two. **Pre-empt for future writing-plans dispatches:** any statistical helper that has multiple textbook-correct implementations (Wilson CI, bootstrap CI tail-handling, bias-correction, Wilson-vs-Agresti-Coull, etc.) needs an EXPLICIT formula pin in the plan with a citation to Wikipedia section, scipy/statsmodels function name, or equivalent. Add to writing-plans §5 watch items: "for statistical helpers, plan §A.7 names the SPECIFIC variant + cites Wikipedia/scipy/statsmodels function name to disambiguate."

### 2 V2 candidates banked (from return report §7)

1. **`count_unresolved_material` widen to include orphan-emit discrepancies.** Current implementation returns ONLY trade-attributed discrepancies (underlying repo helpers JOIN on trades). Orphan-emit discrepancies (sector_tamper / equity_delta / cash_movement_mismatch with NULL trade_id from Phase 9 Sub-bundle D's sector_tamper audit + Sub-bundle C's equity_delta) are EXCLUDED from the count. Discriminating regression test `tests/metrics/test_discrepancies.py::test_count_unresolved_material_excludes_orphan_emit_no_trade` pins V1 behavior. V2 could widen via separate sub-query joining on the run-attribution side.

2. **`render_class_d` "point" branch hardcodes sum semantics.** Implementation hardcodes sum semantics per §A.21 + §J.1.1 for `mistake_cost_R_rolling_N_total`. Other future "point" callers (if any) needing mean semantics would need a new helper or a parameter to switch aggregation. Banked at the §A.21 V2.1 §VII.F amendment candidate; consider when Sub-bundle E lands the §3.8 process-grade-trend surface.

### Post-merge state

- HEAD on main: `096de83` (integration merge) + housekeeping commit (this entry).
- Active risk_policy: `policy_id=5` (Option C revert; `max_account_risk_per_trade_pct=0.5` cfg-aligned per operator decision 2026-05-13). Policy chain: 1 (seed) → 2 (operator test) → 3 (S2.bis divergence) → 4 (S2.bis revert) → **5 (Option C revert; ACTIVE)**.
- Cross-bundle pin at T-A.7 (still SKIPPED): un-skip lands at Sub-bundle E T-E.3 retrofit of 6 existing base-layout VMs.
- Sub-bundle B executing-plans dispatch UNBLOCKED.

### Cross-references

- Sub-bundle A return report: `docs/phase10-bundle-A-return-report.md`.
- Plan §A.7 + §D Task A.1 (AMENDED in-tree at `e32f71c` + `75dd63f`).
- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`.
- Electives amendment: `docs/phase10-electives-amendment.md` (Sub-bundle B will propagate T-B.7 elective).

---

## 2026-05-13 §8.4 Corporate_Actions MVP — standalone post-Phase-10 dispatch (deferred per Phase 10 electives amendment)

**Decision (operator 2026-05-13 post-Phase-10-writing-plans-merge):** §8.4 Corporate_Actions MVP defers to a standalone post-Phase-10 dispatch. Phase 10 plan §A.0 ZERO-new-schema lock preserved; Phase 10 V1 arc shape stays at 5 sub-bundles A→B→C→D→E with 39 tasks (4 other electives propagated; see `docs/phase10-electives-amendment.md`).

**Scope when dispatched (per Phase 10 spec §8.4 + plan §A.4 cost estimate):**
- New `corporate_actions` table: columns approximately `(id, ticker, action_type, action_date, ratio_numerator, ratio_denominator, notes, recorded_at, source)`. Action types: `split`, `dividend`, `ticker_change`, `delisting`. `0018_*.sql` migration bumping `EXPECTED_SCHEMA_VERSION` 17 → 18.
- New CLI surface: `swing corporate-action {record,list,resolve}` group (mirrors Phase 9 `swing journal discrepancy` shape).
- Manual reconcile flow: operator-driven; defensive logging only; NO automated price-adjustment in V1 (per spec §8.4 recommendation).
- Estimated ~3-6hr executing-plans wall-clock; brainstorm + writing-plans + executing-plans full cycle since schema work merits independent Codex rigor.

**Rationale for standalone (not Phase 10 V1):**
- Phase 10 V1 is read-side dominant (metrics dashboard atop v17 schema); §A.0 ZERO-new-schema lock was a Codex-converged 6-round decision.
- Bundling §8.4 into Phase 10 V1 as "Sub-bundle F" would break the §A.0 lock + add ~3-6hr + 1 new table + 1 CLI surface to the executing-plans arc. Operator chose to preserve §A.0 lock + preserve Phase 10 arc shape.
- §8.4 ships first among Phase 11 candidates (along with Schwab API Phase A, inception-CSV ingestion, snapshot semantics formalization — see Phase 10 plan §10 hand-off + return-report §10).

**Sequencing:** standalone dispatch unblocks AFTER Phase 10 V1 closes (all 5 sub-bundles A→B→C→D→E integrated). Standalone dispatch may run in parallel with other Phase 11 candidates per orchestrator + operator triage.

**Cross-references:**
- Phase 10 spec §8.4 (orchestrator-decision open question; brainstorm recommendation = DEFENSIVE log-only).
- Phase 10 plan §A.4 disposition (default DEFER; operator decision 2026-05-13 confirms defer-as-standalone).
- Phase 10 electives amendment `docs/phase10-electives-amendment.md` §5.
- v1.1-alternate F-019 corporate-action interaction concern (anchored spec §8.4 risk framing).

---

## 2026-05-12 Phase 9 closer: Sub-bundle E lessons banked + Phase 10 writing-plans hand-off note

**Phase 9 arc SHIPPED 2026-05-12** (Sub-bundles A → B → C → D → E). Bundle E shipped as `phase9-bundle-E-polish-and-phase10-handoff` worktree dispatch (T-E.0 combined E2E happy path + T-E.1 CLAUDE.md gotcha promotion ratification + T-E.2 this hand-off note + T-E.3 cross-bundle Account Order History multi-line parser fix). Plan §H Task E.2 acceptance verified: `ruff check swing/ --statistics` returns 18 E501 (unchanged from Sub-bundle A baseline; zero new violations across A+B+C+D+E).

### Phase 10 writing-plans hand-off (binding inputs from Phase 9 spec §11)

Phase 10 writing-plans dispatch follows Phase 9 close. Phase 9 design choices Phase 10 needs to know about:

**§11.1 Risk_Policy as the source for metric defaults at dashboard read-time.** Phase 10 dashboard reads LIVE policy (`risk_policy.is_active=1`) for: `low_sample_size_threshold_class_*_n` (suppression at render); `global_confidence_floor_n` (n=20 floor); `bootstrap_resample_count` (CI computation); `process_grade_weight_*` (weight reconstitution if stamp absent on legacy review_log rows). Phase 10 dashboard reads AT-TRADE-TIME policy (`trades.risk_policy_id_at_lock`) for: `capital_floor_constant_dollars` (preserves historical-trade interpretation under capital-floor change); `scratch_epsilon_R` (preserves win/loss/scratch classification under threshold change); trade-grain metrics that need policy-as-of-trade-time semantics. Locked decision per spec §3.1.1: the per-row stamp on trades + review_log enables this at-trade-time vs live-time distinction. **Schema ready; Phase 10 wires the queries.**

**§11.2 Reconciliation discrepancy surface for metrics-data-quality reporting.** Phase 9 ships `reconciliation_runs` + `reconciliation_discrepancies` + the canonical query `list_unresolved_material_for_active_trades` (with closed-trade companion). Phase 10+ writing-plans may add a "reconciliation status" badge on dashboard / journal review surfaces. Recommended Phase 10+ surfaces: (a) dashboard top "N unresolved material discrepancies" badge (links to discrepancy list); (b) per-trade detail "Trade X has unresolved reconciliation discrepancies" indicator; (c) per-cohort metrics view optional filter "exclude trades with unresolved discrepancies" for sample-purity. **Schema scopes the LEFT JOIN pattern per spec §5.3; Phase 10+ implements the rendering.**

**§11.3 Hypothesis status history surfaces.** Phase 10 §3.2 surfaces "single most-recent transition only" in V1; full history requires Phase 9's `hypothesis_status_history` audit table. Phase 10 writing-plans uses the new table to render: (a) per-hypothesis transition timeline (active → paused → active → closed-target-met); (b) cohort-level "active period" calculations (excludes paused intervals from rate-metric numerators if operator opts in). **Schema sufficient; Phase 10 wires the queries via `list_history_for_hypothesis` + cohort-aggregation helpers.**

**§11.4 account_equity_snapshots resolution for `live_capital_denominator_dollars`.** Phase 10 §6.2 + §3.4 capital-friction metrics depend on a unified denominator. Phase 9 ships the table + the source-ladder discipline (schwab_api > tos_csv > manual). Phase 10 metric layer resolves:

```sql
live_capital_denominator_dollars(asof_date) :=
  COALESCE(
    (SELECT equity_dollars FROM account_equity_snapshots
       WHERE snapshot_date <= asof_date
       ORDER BY snapshot_date DESC,
                CASE source WHEN 'schwab_api' THEN 1
                            WHEN 'tos_csv' THEN 2
                            WHEN 'manual' THEN 3 END ASC
       LIMIT 1),
    (SELECT capital_floor_constant_dollars FROM risk_policy WHERE is_active = 1)
  )
```

Source ladder enforces broker-authoritative > csv > manual when same date has multiple rows. Fallback to `risk_policy.capital_floor_constant_dollars` when no snapshot exists at-or-before asof_date (Phase 10 §2 split-policy PROVISIONAL). **`get_latest_snapshot_on_or_before` already implements the source-ladder + provenance; Phase 10 consumes it.**

**§11.5 Phase 9 capture-needs already accommodated for Phase 10.** Phase 10 §6.3 enumerated capture-needs beyond Phase 8/9 plans: (a) per-pipeline-run capital-utilization aggregate — Phase 10+ writing-plans territory; uses Phase 9 `account_equity_snapshots` for live denominator; NOT a Phase 9 column; (b) benchmark series capture (Phase 10 §8.3 open question) — OUT of Phase 9 scope; orchestrator triages separately; (c) Corporate_Actions MVP (Phase 10 §8.4 open question) — OUT of Phase 9 scope; orchestrator triages separately; (d) daily account equity capture (Phase 10 §8.2 open question) — SATISFIED by Phase 9 `account_equity_snapshots`.

### Phase 9 final ruff sweep (T-E.2 acceptance criterion 1)

`ruff check swing/ --statistics` returns **18 E501** (line-too-long only). Unchanged from:
- Pre-Phase-9 baseline at HEAD `622c669` (verified 2026-05-11 in Phase 9 writing-plans return report §6).
- Sub-bundle A landing at `6c8f3a9`.
- Sub-bundle B landing at `e96834a`.
- Sub-bundle C landing at `e5d5892`.
- Sub-bundle D landing at `4894688` + housekeeping `6ba1925`.
- Sub-bundle E task family commits.

**Phase 9 introduces ZERO new ruff violations** across +500+ lines of consumer-side code + 5 new tables' worth of repo functions + 4 new service modules + ~430+ new fast tests.

### Phase 9 closing summary (for orchestrator)

- 5 sub-bundles SHIPPED across 2026-05-12 (one calendar day end-to-end).
- ~430+ new fast tests across the arc; cumulative fast suite 2462 → ~2766 at Bundle E close.
- Schema version v16 → v17 in atomic landing at Sub-bundle A T-A.1; v17 unchanged through B/C/D/E (consumer-side only).
- 1 single ACCEPT-WITH-RATIONALE position banked across the arc (Sub-bundle C R1 M#1 equity_delta sign convention; brief-vs-spec cosmetic — implementation correctly followed spec).
- 6 CLAUDE.md gotchas promoted (3 Sub-bundle A at `de10601` + 2 Sub-bundle D at `6ba1925` + 1 Sub-bundle E at T-E.1).
- 1 spec amendment pending V2.1 §VII.F routing (Sub-bundle D's §7 supersession to chart_pattern-mirror hidden-anchor pattern; recon doc `docs/phase9-bundle-D-task-D0-recon.md` carries the binding design).
- 1 spec amendment pending V2.1 §VII.F routing (Sub-bundle E T-E.3's §6.2 supersession to multi-line group parser; recon doc `docs/phase9-bundle-E-task-E3-parser-recon.md` carries the binding design).
- 2 V2 candidates banked at this file (Schwab inception-CSV ingestion; account_equity_snapshots semantic formalization).

**Phase 10 writing-plans dispatch is unblocked.** Orchestrator queues Phase 10 writing-plans next per spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-dashboard-design.md`. Brainstorm already SHIPPED 2026-05-06 at `fe6cb45`. Phase 10 reads this hand-off note's binding inputs.

---

## 2026-05-12 Phase 9 Sub-bundle D/E candidate: Schwab "since-inception" Account Statement ingestion

**Observation (operator-witnessed gate Sub-bundle C 2026-05-12):** Operator's "since-inception" Schwab Account Statement export `thinkorswim/2026-05-12-AccountStatementInception.csv` is structurally richer than the 7-day Account Statement Bundle B's `extract_account_summary_net_liq` (T-C.6) consumes. The inception export's full section inventory:

| Section | Bundle B/C consumes | V2 ingestion candidate use |
|---|---|---|
| Cash Balance (full inception history) | partially (cash_movements only) | seed `cash_movements` retroactively from inception; reconcile against existing rows for any pre-Phase-7 gaps |
| Account Order History | yes (Bundle B `extract_stop_orders` — banked Bundle E parser-gap fix pending) | richer inception sample for the Bundle E parser fix's regression corpus |
| Account Trade History | partially (Bundle B's `extract_stock_fills`) | full-history fill reconciliation against the journal's `fills` table for any pre-Phase-7 gaps |
| Equities (current open positions snapshot) | no | could seed `position_qty_mismatch` baselines or feed Phase 10 dashboard's open-position MTM |
| Profits and Losses (per-position YTD aggregates) | no | could seed `realized_R` cross-checks against Phase 6 `review_log` aggregates |
| Account Summary (current Net Liq + buying power) | yes (Bundle C T-C.6 `extract_account_summary_net_liq`) | unchanged |

**Concrete use cases:**

1. **Cash movements historical seed.** Bundle B's reconciliation already extracts cash_movements from any TOS export. The inception export covers the full history; ingesting it would seed the `cash_movements` table with deposits/withdrawals since account inception (verified via the operator-witnessed gate: 2 deposits of $100 each on 3/30/26 + 4/29/26 totaling $200 are in the production cash_movements; inception export would surface the same + any prior we missed).
2. **Account equity snapshots historical series.** Per-statement Net Liq values from prior monthly statements could seed an `account_equity_snapshots` historical series, giving Phase 10 metrics dashboard a real cash-basis vs MTM trajectory rather than just current point-in-time.
3. **Fills audit against the journal.** Account Trade History since inception could audit the `fills` table for any pre-Phase-7 fills missing from the journal (especially historical trades where operator may not have manually backfilled).
4. **Equity_delta historical baseline.** Bundle C's T-C.6 wires equity_delta for present-day reconciliation; an inception ingestion could backfill equity_delta history.

**Scope notes:**

- The existing `swing/journal/tos_import.py` parsing infrastructure is already there for the 7-day export shape. The inception export uses the same column structures + section headers (verified during operator-witnessed gate); the diff is the date range (full inception vs 7 days). The parser may "just work" against the inception export with minor section-specific handling.
- Section "Profits and Losses" is NEW to consume — not currently parsed. Would need a new extractor.
- Section "Equities" (current open positions snapshot) is NEW to consume — not currently parsed (Bundle B's `extract_equity_positions` parses ONLY the qty column for `position_qty_mismatch`; the Trade Price + Mark + Mark Value columns are not extracted).
- The 4 prior sample exports in `thinkorswim/` are 7-day; the inception export is the first multi-month sample. Bundle D/E or post-Phase-9 work could leverage it.

**Cross-references:**
- Schwab inception export: `thinkorswim/2026-05-12-AccountStatementInception.csv` (untracked, ~20 KB).
- Operator-witnessed gate Sub-bundle C 2026-05-12 — equity reconciliation discussion that surfaced this candidate.
- Bundle B's `extract_stop_orders` + `extract_stock_fills` + `extract_equity_positions` + Bundle C's `extract_account_summary_net_liq` in `swing/journal/tos_import.py`.
- Phase 10 metrics dashboard (brainstorm `fe6cb45`; writing-plans pending post-Phase-9) §3 `live_capital_denominator_dollars` (R1 M2 + R3 M1 lock) — would benefit directly from historical cash basis + MTM series.
- V2.1 §VII.F source-of-truth correction protocol (if ingestion changes invariants).

**Operator-paced; not orchestrator-blocking.** Phase 9 Sub-bundles D + E + Phase 10 brainstorm are higher-priority; this ingestion candidate sequences behind in-flight phases.

---

## 2026-05-12 Phase 9 / V2 candidate: account_equity_snapshots semantic formalization (cash-basis vs net-liq)

**Observation (operator-witnessed gate Sub-bundle C 2026-05-12):** Bundle C's T-C.6 equity_delta wiring revealed a semantic ambiguity in `account_equity_snapshots.equity_dollars`. The operator stored `$2000` representing "cash basis since inception" (deposits − withdrawals); Schwab's Account Summary reports `$2014.36` as Net Liquidating Value (cash basis + realized P&L + unrealized MTM). The equity_delta column then surfaces as ≈ -(YTD P/L) which is informative but ambiguous — the operator must mentally distinguish what `equity_dollars` meant when each snapshot was taken.

**Concrete impact:**

If Bundle C had stored `$2014.36` (MTM), equity_delta would be near zero and the comparison would surface only Schwab-vs-journal drift (e.g., parser-gap stops, missing fills). If it stored `$2000` (cash basis), equity_delta ≈ Schwab's YTD P/L — informative for "where is my P&L?" but not the spec's apparent intent (which is "where do my equity numbers disagree?").

The operator's clarification post-gate established that V1 stored cash basis, not MTM — but V1's spec/CLI doesn't force the disambiguation. Future operator could store either value at different times, producing inconsistent equity_delta interpretation.

**V2 hardening options:**

1. **Add `kind` discriminator** to `account_equity_snapshots` (`'cash_basis'` / `'net_liq'` / `'cash_balance'` — 3-value CHECK enum). Bundle B's reconciliation T-C.6 then compares like-to-like: if snapshot is `kind='net_liq'`, compare directly to Schwab's Net Liq; if `kind='cash_basis'`, compute expected_net_liq = cash_basis + realized + unrealized (using journal-computed P&L) and compare to Schwab's Net Liq. Equity_delta becomes meaningful regardless of kind.
2. **Distinct columns** instead of `kind` discriminator: `equity_cash_basis_dollars`, `equity_net_liq_dollars`, `equity_cash_balance_dollars`. Operator inputs whichever they have visibility into; reconciliation does multi-axis comparison.
3. **Auto-derive cash basis from `cash_movements`.** If `cash_movements` is fully populated (deposit / withdrawal kinds), cash basis = SUM(deposit amounts) − SUM(withdrawal amounts). Then operator doesn't even need to input cash basis — only MTM observations. Requires the Schwab inception-CSV ingestion above to seed cash_movements fully.
4. **Defer / accept V1.** Keep `equity_dollars` ambiguous; document operator convention in CLI help text + operator-facing reference; resolve via Phase 10 metrics dashboard's prescribed convention.

**Recommendation:** option 3 (auto-derive cash basis from `cash_movements`) sequenced AFTER the Schwab inception-CSV ingestion task above. Cleanest data model + lowest operator burden. Option 1 (kind discriminator) is a fallback if cash_movements completeness can't be guaranteed.

**Cross-references:**
- Bundle C return report §6 (R1 M#1 equity_delta sign convention ACCEPT-WITH-RATIONALE).
- Bundle C operator-witnessed gate S6 + post-gate equity reconciliation discussion 2026-05-12.
- Spec `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` §3.5 + §3.2 + §3.3.1 equity_delta JSON shape.
- Phase 10 metrics dashboard `live_capital_denominator_dollars` spec (R1 M2 + R3 M1 lock) — uses similar split semantic (constant vs live).

**Operator-paced; not orchestrator-blocking.** Sequences behind Schwab inception-CSV ingestion (above) for option 3 path.

---

## 2026-05-12 Phase 9 Sub-bundle E polish: Account Order History multi-line parser gap (operator-witnessed gate finding)

**Observation (operator-witnessed gate finding 2026-05-12):** Phase 9 Sub-bundle B's `stop_mismatch` detection emitted 5 false-positive discrepancies during the operator-witnessed gate when reconciling the operator's real-world Schwab/TOS export `thinkorswim/2026-05-12-AccountStatement.csv` against the production journal. All 5 open trades (DHC/YOU/VSAT/CVGI/LAR) were flagged "no broker working stop" despite working stops being placed at Schwab with prices matching journal `current_stop` values exactly.

**Root cause:** Bundle B's `extract_stop_orders` in `swing/journal/tos_import.py` per spec §6.2 looks narrowly for `STP` in the order_type column. Real-world Schwab/TOS Account Order History exports use a **2-line group** structure per working order:

```
,,5/11/26 23:09:41,STOCK,SELL,-20,TO CLOSE,CVGI,,,STOCK,~,MKT,GTC,WORKING
,,,RE #1006290692715,,,,,,,,4.36,STP,STD,
```

The header line carries `order_type=MKT` + `price=~` + `time_in_force=GTC` + `status=WORKING`. The continuation row carries the STP trigger price + `STP STD` qualifier. The parser only sees the header line and concludes "no STP order" — missing the actual trigger price in the continuation row.

Additional patterns observed across the 4 sample exports in `thinkorswim/`:

| File | Pattern | Notes |
|---|---|---|
| 2026-04-15 | (no Account Order History rows) | empty section — operator had no working orders on that date |
| 2026-04-30 (CC) | 3-line group: header + `TRG BY #ID BASE-6.74 STP STD` + `20.51 STP` | Conditional trigger (base-price relative) chained with absolute stop trigger |
| 2026-05-08 (DHC) | header `MKT GTC WAIT TRG` (no continuation) | Conditional order not yet armed; status `WAIT TRG` not `WORKING` |
| 2026-05-08 + 2026-05-12 | header `MKT GTC WORKING` + continuation `<price> STP STD` | Canonical 2-line stop-market group |
| various | header `MKT GTC CANCELED` | Correctly skipped (not WORKING) |

**Bundle E acceptance criteria:**

1. **Multi-line grouping.** Rewrite `extract_stop_orders` (or introduce a streaming-grouper) to read the Account Order History section as **order groups** — header row + N continuation rows until the next dated header row OR section boundary.
2. **Stop trigger extraction from continuation.** When the continuation row contains `STP STD` (or just `STP` per Schwab's column conventions), read the trigger price from the price column. Handle both simple absolute (`4.36 STP STD`) and conditional `TRG BY #ID BASE-X.XX STP STD` + absolute trigger row variants.
3. **Status filter widening.** Include `WAIT TRG` alongside `WORKING` — both indicate a placed-but-not-yet-filled stop. `CANCELED` and `FILLED` correctly remain excluded.
4. **Backwards compatibility.** Existing fixture-based discriminating tests (boundary delta=0/0.005/0.01/0.02 + 3 stop_mismatch sub-cases) MUST still pass. Add new fixture CSVs at `tests/fixtures/tos/` capturing the multi-line pattern variants observed in the operator's 4 sample exports.
5. **Regression test against operator's real-world exports.** Add a new fast-test that reconciles `thinkorswim/2026-05-12-AccountStatement.csv` against a fixture journal with the matching open trades + asserts ZERO stop_mismatch discrepancies emitted (the matching path). Mirror for the 2026-05-08 export (with `WAIT TRG` DHC).
6. **Spec §6.2 amendment.** Update spec text to reflect the 2-line group structure (currently spec assumes 1-row STP rows). Brief explicitly notes the spec text was a brainstorm-time approximation; the migration + production reality require the 2-line parse.

**Scope:** ~3-4 hr implementation. Single-task dispatch suitable for inline orchestrator OR a small implementer dispatch. Sub-bundle E's existing scope (E2E happy path + CLAUDE.md gotcha promotion + Phase 10 hand-off prep per plan §H) absorbs this naturally as a new task T-E.0.bis or T-E.3.

**Operator-side action items pending parser fix:**

- The 5 `acknowledged_immaterial` resolutions on discrepancies 1-5 in production DB stand as the V1 disposition. Operator should re-reconcile after Bundle E ships to confirm the matching path produces zero stop_mismatch findings.
- Real-world fixture corpus at `thinkorswim/*.csv` is currently untracked (in project root, not in `data/finviz-inbox/` or `tests/fixtures/tos/`); Bundle E should formalize the corpus location (copy a subset to `tests/fixtures/tos/schwab-real-world-*.csv` for the regression tests; keep the originals untracked at the operator's working location).

**Cross-references:**

- Sub-bundle B return report `docs/phase9-bundle-B-return-report.md` (merge `e96834a`).
- Operator-witnessed gate findings: §S4 of Sub-bundle B gate, 2026-05-12.
- Spec §6.2 + §3.3.1 expected_value/actual_value JSON shapes for `stop_mismatch`.
- Bundle B parser current implementation: `swing/journal/tos_import.py` (the `extract_stop_orders` function — verified single-line per the current spec; gap is the multi-line group recognition).
- Prior 3e.12 tos-import diagnostic fixed multi-day `Exec Time` parsing (commit `a9541d2`) — similar real-world-export-structure investigation pattern.

---

## 2026-05-12 Low priority: Minervini reference review vs current strategy implementation

**Observation (operator-surfaced 2026-05-12):** Two new methodology reference artifacts landed in `reference/minervini/`:
- `896159773-Minervini-Trading-Strategy-Deep-Dive.txt` — 91 KB summary of SEPA.
- `Mark Minervini - Think & Trade Like a Champion-Access Publishing Group (2017).pdf` — Minervini's second book (~6 MB).
- `think-and-trade-like-a-champion.md` — pymupdf4llm conversion of the PDF (415 KB markdown + 87 figures in `reference/minervini/figures/`).

These supplement the existing `reference/methodology/minervini-trend-template.md` + `reference/methodology/minervini-sell-side-rules.md` source-of-truth extracts but contain broader doctrine + commentary not yet reconciled against current implementation.

**Scope of review (operator-locked focus: entry/exit/stop; NOT limited to these):**

- **Entry criteria.** Current implementation: `swing/evaluation/` (A+ criteria); `swing/web/routes/trades.py` entry form; `swing/trades/entry.py:entry_create` lock-time service; sector/industry tamper hardening (Phase 9 Bundle D queued). Compare to: Trend Template threshold logic; VCP / pivot pattern requirements; volume-confirmation rules; relative-strength minimums; sector-leadership posture.
- **Exit criteria.** Current implementation: `swing/trades/exit.py`; advisory rules in `swing/trades/advisory.py` (3e.8 Bundle 2 = `suggest_trim_into_strength` + `suggest_planned_target_r_hit` + `suggest_parabolic_trim`); Phase 6 review-completion outcome bucketing. Compare to: profit-take rules; +20% / +25% targets; parabolic / blow-off climax exits; "violation of the line" exits.
- **Stop criteria.** Current implementation: `swing/trades/stop_adjust.py`; trail-MA advisories (3e.8 Bundle 3 = `suggest_maturity_stage_trail_ma_hint` + `suggest_r_multiple_stop_tighten`); R-multiple stop tightening per TLSMW Ch 13 p. 296. Compare to: maximum-loss rule (-7%/-8% absolute floor); breakeven-stop timing; trailing-stop discipline; sell on first violation vs second.
- **Position sizing + risk per trade.** Current: `swing/recommendations/compute_shares` + capital floor convention ($7500 floor; user memory `project_capital_risk_floor.md`); Phase 9 risk_policy `max_account_risk_per_trade_pct` (currently 0.75 inherited from S3 test). Compare to: 1.25-2.5% baseline per Minervini; concentration vs diversification stance; pyramid-up rules.
- **Portfolio-level risk.** Current: Phase 9 risk_policy `max_concurrent_positions` + `max_portfolio_heat_pct` + `max_sector_concentration_positions` (foundation landed Sub-bundle A; consumption queued). Compare to: Minervini's portfolio-heat convention; pause-on-drawdown thresholds; consecutive-loss exit-the-market discipline.
- **Trade journal cadence + post-trade review.** Current: Phase 6 review_log + cadence card; Phase 8 daily_management_records (event_log + daily_snapshot); MFE/MAE precision tiers. Compare to: Minervini's "post-analysis" prescription (Chapter 8 of TLSMW; chapters in TTLAC); win/loss size asymmetry tracking; batting-average framing.
- **Mental model / discipline (not limited).** Compare current advisory + cadence surfaces to Minervini's psychological framework — pre-trade plan locking, batting-average framing, "trade the plan not the P&L" discipline, post-loss review cadence.

**Output target:** `docs/methodology-review-minervini-2026-MM-DD.md` (or similar dated memo) enumerating divergences + gaps with citations to both reference sources + current-code surfaces. Memo classifies each finding:
- **MATCHES** (current implementation aligns with reference; no action).
- **DIVERGES** (current implementation deliberately differs; document rationale or escalate via V2.1 §VII.F).
- **GAP** (reference prescribes something current implementation lacks; potential Phase 10+ candidate; route through V2.1 §VII.F if production-touching).
- **UNCLEAR** (reference ambiguous OR current implementation under-specified; flag for operator adjudication).

**Suggested dispatch shape (when sequenced):**

Best handled as a single research-subagent dispatch (Explore or general-purpose agent), NOT orchestrator-inline. The grep-and-compare work would burn orchestrator context unnecessarily. Implementer brief: read all 3 reference sources + `reference/methodology/minervini-*.md` + grep current implementation surfaces (entry/exit/stop/sizing/portfolio/journal); produce structured memo. Adjudicate findings with operator after first draft.

**Operator-paced; not orchestrator-blocking.** Phase 9 arc (Sub-bundles B-E) + Phase 10 brainstorm are higher-priority; this review is durable reference work that should sequence behind in-flight phases. Capturing here so the new reference artifacts don't sit unreconciled.

**Cross-references:**
- `reference/minervini/think-and-trade-like-a-champion.md` (converted 2026-05-12 via pymupdf4llm).
- `reference/methodology/minervini-trend-template.md` + `minervini-sell-side-rules.md` (existing source-of-truth extracts).
- `docs/3e8-sell-side-advisories-investigation.md` (746-line survey of sell-side advisory surface vs Minervini SEPA + DST + Qullamaggie doctrine; SHIPPED 2026-05-10 at `63350ad`; informs the exit/stop comparison axis).
- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §VII.F (source-of-truth correction protocol; routes production-touching findings).
- CLAUDE.md "Strategy" section — `reference/methodology/` is reference-only; any production change driven by methodology reference routes through V2.1 §VII.F.

---

## 2026-05-07 Research candidate: risk level vs earnings proximity correlation

**Observation (operator-surfaced 2026-05-07):** There appears to be a correlation between risk level and proximity to earnings announcements. Pattern not yet quantified; surfacing for future research-branch investigation.

**Possible mechanisms (NON-exhaustive; investigation should disambiguate):**

1. **Stop-overshoot magnitude.** Earnings gaps (overnight 10-30% moves) blow through stops; realized loss exceeds planned -1R. Correlation = "trades held through earnings have higher realized-R variance than trades closed before earnings."
2. **Implied volatility expansion.** ATR-based position sizing reads pre-earnings ATR as elevated; risk_per_share inflates; planned_risk_budget_dollars allocates differently. Correlation = "trades entered N days before earnings have wider initial stops AND higher position-size variance."
3. **Per-cohort earnings exposure imbalance.** Sub-A+ VCP-not-formed cohort may attract more pre-earnings trades than A+ baseline (operator hasn't waited for clean post-earnings setups). Correlation = "hypothesis cohort × earnings-proximity is non-uniform."
4. **Pipeline criteria-pass interaction.** Some trend-template / VCP criteria are MORE forgiving in the post-earnings window (e.g., gap-up creates new pivot context); correlation = "criteria pass-rate × earnings-proximity is non-uniform."
5. **Discretionary-confirmation drift.** Operator-perceived risk correlates with earnings calendar awareness (operator may take MORE / FEWER trades pre-earnings based on framing). Confounds outcome attribution.

**Existing infrastructure that could feed investigation:**

- `research/studies/earnings-proximity-exclusion.md` (Tranche B-research Sessions 2a/b/c; methodology established; canonical applied-research study format).
- `research/method-records/` (V2.1 §IV.B minimum viable field list).
- Phase 6 + Phase 7 + queued Phase 8 schema captures `mistake_cost_R` + `lucky_violation_R` + per-day MFE/MAE + outcome bucketing — enables per-cohort × earnings-proximity outcome aggregation when sample size matures.
- `swing/data/ohlcv_archive.py` historical OHLCV archive (Phase 3 consolidation; 696 tickers).
- External earnings-calendar data source: undecided. yfinance `Ticker.calendar` exists but reliability is unverified for historical earnings dates. Schwab API Phase B (queued) may surface fundamentals incl. earnings; alternative paid sources exist (Earnings Whispers, Zacks, EOD historical-earnings APIs).

**Suggested dispatch shape (when sequenced):**

1. **Brainstorm** to lock the research question — which mechanism (or set) is the primary investigative target. Per V2.1 §X pre-registration discipline, decision tiers + thresholds committed before viewing data.
2. **Replay-harness extension** to per-trade-window earnings-proximity binning (mirror earnings-proximity-exclusion study's binning).
3. **Applied-research dispatch** to compute per-cohort × earnings-proximity outcome distributions over operator's actual closed trades (n=2 today; usable for n≥10 baseline).
4. **Tier-3 outcome adjudication** per V2.1 promotion path. If pattern is robust, eventual policy change candidate routes through V2.1 §VII.F source-of-truth correction protocol.

**Operator-paced; not orchestrator-blocking.** Sample size today (n=2 closed) is insufficient for any quantitative investigation; the right time to dispatch is when n≥10 closed trades accumulate AND the operator has spare research-branch time. Capturing here so the observation doesn't decay; signal-tracking only until investigation triggers.

**Cross-references:**
- `research/studies/earnings-proximity-exclusion.md` (existing study; methodology baseline).
- `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §IV.B (research-branch method-record format) + §VII.F (source-of-truth correction protocol).
- `docs/orchestrator-context.md` §"Three-branch architecture" (Applied Research is the right home).
- 2026-04-25 Hypothesis 5 (Production-vs-replay parity check) — establishes the harness pattern.

---

## Dashboard / UX enhancements

> **Archived:** 3e.1 (mark-to-market on Account card; SHIPPED 2026-04-26 `2b5cded`) + 3e.3 (`POST /prices/refresh` clears OHLCV breaker; SHIPPED 2026-04-26 `5b56a2d`). See archive.

### 3e.4 — Current price in hyp-rec expanded row — **SHIPPED 2026-05-10 at `44ac760`** (polish-bundle Task family A; commits 083fa68 + 88d17ca + Codex-fix 17d6e55)

> **Outcome:** SHIPPED as Task family A in polish bundle 2026-05-10. New `HypRecsExpandedVM.current_price: PriceSnapshot | None` field; `build_hyp_recs_expanded` extended with `cache=None, executor=None` kwargs; route threads `request.app.state.price_cache` + `price_fetch_executor`. Template renders `Current: $X.XX` with `(stale)` indicator at top of expanded panel above Order parameters. Codex R1 Major #1+#2+#3 caught brief-author error: brief watch-item named non-existent `PriceCache.get_or_fetch(ticker, executor=...)` API; real API is `cache.get_many([tickers], deadline_seconds=..., executor=executor)`. Implementer fix in 17d6e55 mirrors open-positions dashboard path. +8 tests; operator-witnessed Surface 1 PASS. Original entry retained below for historical reference.

**Observed (original):** When a hypothesis-recommendation row on the dashboard is expanded (chevron click → `GET /hyp-recs/<ticker>/expand` → `partials/hypothesis_recommendations_expanded.html.j2`), the additional details panel does NOT include current price. Operator workflow: expand a hyp-rec to evaluate the trade decision; current-price context is needed alongside pivot, ADR, sector etc., but currently absent.

**Proposed fix:** Surface current price in the expanded panel. Mirrors the pattern already used in open-positions row (price_snapshot from PriceFetcher). VM `build_hyp_recs_expanded` already resolves the binding pipeline run; extend to also fetch the current price for the ticker (likely via the same `PriceCache` pathway the dashboard uses) and add to `HypRecsExpandedVM`. Template renders the price + stale-flag if applicable.

**Scope:** `swing/web/view_models/recommendations.py` (or equivalent VM) + `partials/hypothesis_recommendations_expanded.html.j2` + 1-2 discriminating tests (price renders when fetched; price omitted/marked stale when fetch fails). ~30-45 min standalone dispatch.

**Cross-references:**
- `swing/web/routes/recommendations.py:160` — `/hyp-recs/{ticker}/expand` route.
- `partials/open_positions_row.html.j2` — price + stale-flag rendering pattern to mirror.
- CLAUDE.md gotcha "OHLCV fetch scope = open-trade tickers ONLY" — does NOT apply here (this is current-price via PriceCache, not OHLCV).
- Watchlist row already shows price; same primitive likely available.

### 3e.5 — Daily management "logged?" indicator on open-positions row — **SHIPPED 2026-05-09 at `b4bb9dd`** (polish-bundle)

> **Outcome:** SHIPPED as Task family A in polish bundle 2026-05-09 (5 commits — A.2 helper + A.4 superseded test + A.5 yesterday-session test + A.6 event_log predicate test + A.3 VM + A.7 template badge; +R1 fix `cfacbc5` correcting predicate to `last_completed_session(now())`; +R2 fix `69a9026` correcting badge labels to `✓ logged / ⚠ pending`). Helper at `swing/data/repos/daily_management.py:has_update_today_for_trades`. Original entry retained below for historical reference.

**Observed (original):** Phase 8 daily management surface lets operator log a daily snapshot OR event_log per trade per session, but the dashboard's open-positions table provides no at-a-glance signal of which trades have been touched today vs. which still need attention. Operator workflow: scan dashboard at end of day, must individually open `/trades/<id>` for each open trade to determine update status.

**Proposed fix (original — predicate corrected at ship):** Add a small icon or badge to each open-positions row indicating whether a `daily_management_records` row (`record_type IN ('daily_snapshot', 'event_log')` AND `is_superseded = 0`) exists for that trade with `review_date == last_completed_session(now()).isoformat()` (originally specified `action_session_for_run(now())`; corrected mid-dispatch by Codex R1 Major #1 — writers stamp `last_completed_session`, not `action_session_for_run`; using the wrong anchor would silently invisibility every just-submitted entry on weekends/holidays/evenings/pre-market). Two-state visual: ✓ logged / ⚠ pending (originally specified ✓ today / ⚠ not yet; corrected mid-dispatch by Codex R2 Major #1 — original labels were temporal lies on weekends/holidays).

**Scope (as shipped):** new helper `has_update_today_for_trades` at `swing/data/repos/daily_management.py` + `OpenPositionsRowVM.has_update_today: bool` + `partials/open_positions_row.html.j2` badge + 8 discriminating tests including round-trip integration test pinning read/write predicate alignment.

**Cross-references:**
- Phase 8 §7.1 dashboard-tile feed (`list_open_position_active_snapshots`) — same predicate, scoped to "active snapshot for this trade today."
- `swing/evaluation/dates.py:last_completed_session` — backward-looking session anchor (the writer-side function; mirrors weather lookup gotcha per CLAUDE.md "Session-anchor read/write mismatch" gotcha promoted 2026-05-09).
- `partials/state_badge.html.j2` — existing badge-rendering pattern.

### 3e.6 — Auto-return to dashboard after daily management event submission — **SHIPPED 2026-05-09 at `b4bb9dd`** (polish-bundle Task family B; commits 4154e4c + c108474 + 6b33c98)

**Observed:** After submitting a daily management event/snapshot via the `POST /trades/<id>/daily-management/event` form on the trade-detail page, the response re-renders the detail page. Operator workflow at end of day is "tour open trades, log update on each, move to next" — current behavior requires manual navigation back to `/` after each submission.

**Proposed fix:** On successful submission, return `204 No Content` + `HX-Redirect: /` header (browser navigates to dashboard via htmx.js). Pattern: same as Phase 5 config page success-path (CLAUDE.md gotcha "HX-Redirect for HTMX success-path response"). Watch item: assert HX-Redirect target route resolves to 200 (Phase 6 lesson — TestClient verifies header but doesn't follow).

**Scope:** `swing/web/routes/trades.py` daily-management POST handler success-path + 2 discriminating tests (HX-Redirect emitted on success; target `/` resolves). ~15-30 min standalone dispatch.

**Cross-references:**
- CLAUDE.md gotcha "HTMX form-driven endpoints have two browser-only failure surfaces" (Phase 5 R1 M2).
- CLAUDE.md gotcha "HX-Redirect target route must be verified to exist" (Phase 6 I3).

### 3e.7 — Example entries beside premortem + pre-trade-thesis textareas — **SHIPPED 2026-05-10 at `44ac760`** (polish-bundle Task family B; commits 40b3daf + d973126 + operator-gate I1 fix ed563d3)

> **Outcome:** SHIPPED as Task family B in polish bundle 2026-05-10. 8 example asides — one per textarea: thesis + why_now + expected_scenario + invalidation_condition + 4 premortem subs (technical / market_sector / execution / additional). Each aside wrapped in HTML5 native `<details>`/`<summary>` for individually-expandable behavior, default collapsed. CSS in `swing/web/static/app.css`. Two operator-driven mid-gate iterations caught by operator-witnessed Surface 4: (1) brief-author undercount (locked '5 textareas' but Pre-trade thesis fieldset has 4 — only thesis got an aside originally); (2) inverted visibility lock from "visible always, NO toggle" → "default collapsed, individually expandable." Both fixed inline via operator-gate I1 commit ed563d3 (+3 new content tests + bumped layout-class count assertion 5→8 + new default-collapsed test). +7 tests total. Original entry retained below for historical reference.

**Observed (original):** Trade entry form has free-text fields for pre-mortem + pre-trade thesis. New / occasional users may not know what an effective entry looks like; operator wants generic example text rendered alongside (not inside) the textareas to assist with filling them out.

**Proposed fix:** Add a side-panel `<aside>` to the right of each textarea showing 2-3 generic example entries (NOT trade-specific; static content). Operator preference: examples visible always, not toggle-shown. CSS layout: textarea + aside in a flex/grid container.

**Scope:** `partials/trade_entry_form.html.j2` (add aside elements with hard-coded example strings) + minor CSS for the side-panel layout in `static/style.css` + 1 discriminating test (asserts example text is rendered on entry form). ~30-45 min standalone dispatch. No VM changes (static template content).

**Cross-references:**
- `partials/trade_entry_form.html.j2` — current form rendering.
- `static/style.css` — flex/grid container patterns.

### 3e.8 — Sell-position indications for winning trades — **INVESTIGATION SHIPPED 2026-05-10 at `63350ad`** (746-line analysis doc; commission decisions pending operator review)

> **Outcome:** SHIPPED via worktree dispatch on `3e8-sell-side-advisories-investigation` branch. 746-line analysis doc at `docs/3e8-sell-side-advisories-investigation.md`. 4 commits = 1 stage-assembly + 2 Codex-fix + 1 polish. Codex chain 3 rounds → NO_NEW_CRITICAL_MAJOR (R1 0/4/3 → R2 0/2/2 → R3 0/0/2; convergent). All 6 Major findings RESOLVED in-doc; 1 Minor accepted (Qullamaggie citation form is replay-oriented per brief authorization). 11 recommendations: 7 advisory-message-only + 3 classification-altering + 1 alternative + 1 operator-action prerequisite. **Critical structural finding §3.G:** `reference/methodology/` contains ONLY Minervini Trend Template (entry criteria), NOT sell-side rules — 12 of 13 [UNVERIFIED] flags are sell-side claims requiring physical-copy text; §4.G (transcribe Minervini SEPA + DST sell-side into reference/methodology/) is operator-action prerequisite gating §4.A/§4.C/§4.H V2.1 §VII.F routing. **DHC-applicable §5.3:** three-field decision matrix (read maturity_stage + open_R_effective + open_MFE_R_to_date together; maturity-badge alone is unsafe). **Operator decision pending on 27 items** in §6 (12 recommendation dispositions + 1 DHC + 1 sequencing + 13 [UNVERIFIED] triages). Each commissioned recommendation will be banked as separate backlog entry with own brainstorm/writing-plans/executing-plans cycle.

**Observed (original, 2026-05-08):**

**Operator question:** What sell-side advisories / indications are surfaced for winning trades today, and what additions would close the doctrine gap? Framework currently emphasizes initial-stop discipline + trail-stop advisories (Phase 3d trail-MA at 20MA pre-+2R, 10MA post-+2R per Tier-3 #6 doctrine), but the affirmative "sell signal" surface for winners is less explicit. Tied to Tier-3 #6 (advisory state-machine + trade-maturity gating; operator-context.md deferred-with-tracking — MEDIUM-HIGH operational urgency; DHC currently approaching trail-MA decision territory).

**Investigation scope:**
1. **Survey current state.** Enumerate what sell-side / trim-side / take-profit advisories the dashboard currently surfaces (open-positions row advisory column; per-trade detail page Phase 8 daily-management `action_taken` enum; `swing/trades/advisory.py` rules). Identify gaps vs Minervini SEPA + Disciplined Swing Trader winner-management doctrine.
2. **Doctrine reconciliation.** Reference Minervini sell-into-strength + parabolic-extension-trim + 7-week-rule + violated-MA-on-volume rules. Reference Disciplined Swing Trader take-profit-into-strength + trail-tighten-after-+2R rules. Compare against Phase 8 maturity stages (pre_+1.5R / +1.5R-2R / +2R+ per Tier-3 #6 doctrine).
3. **Recommend additions.** Specific advisories to add (e.g., "20% advance in 1-3 weeks → consider sell-into-strength"; "violated 50MA on volume → exit"; "parabolic extension → trim 25-50%"). Per V2.1 §VII.F source-of-truth correction protocol if any addition would alter operational classification logic; per ordinary brief-then-dispatch path if it's only advisory-message extension.

**Scope estimate:** investigation 2-4 hours; subsequent implementation dispatch (if approved) 4-8 hours depending on rule count. Investigation can be orchestrator-thread OR dispatch (per Phase 4.5 brainstorm-dispatch threshold).

**Cross-references:**
- `docs/orchestrator-context.md` Tier-3 #6 (advisory state-machine + trade-maturity gating; deferred-with-tracking).
- `swing/trades/advisory.py` — current advisory rule surface.
- `reference/methodology/` — Minervini Trend Template + Disciplined Swing Trader transcriptions.
- Phase 10 metrics-dashboard `maturity_stage` cohort axis (`docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`).
- V2.1 §VII.F source-of-truth correction protocol.

### 3e.9 — Market weather chart surface (INVESTIGATION; operator-surfaced 2026-05-08)

**Operator question:** evaluate for a good way to display a chart of market weather. Today the UI surfaces only a one-word label (Bullish / Caution / Bearish / STALE) on the dashboard `status_strip` + pipeline progress + open-positions row VMs. The classifier at `swing/weather/classifier.py:53` already computes close + 10MA + 20MA + 50MA + slope20_5bar + slope10_5bar from 180-day OHLCV on `cfg.rs.benchmark_ticker`; all values are persisted per run in `weather_runs`. The visual signal is absent.

**Investigation scope:**

1. **Survey current state** (above; ground truth captured in this entry).
2. **Display options to evaluate:**
   - **Option A — Benchmark price chart with MA overlays.** Mirror the per-trade chart-rendering pattern (`swing/rendering/charts.py` if applicable; matplotlib/mplfinance pipeline). 180-day candles + 10MA + 20MA + 50MA lines; current close annotation. Static PNG generated by pipeline alongside per-trade charts; rendered as `<img>` in dashboard `status_strip` or a dedicated `market_weather` section. Pre-empts mathtext gotcha (CLAUDE.md — no `$` / `^` / `_` in title format).
   - **Option B — Historical weather-status timeline.** Render `weather_runs` history (last N days) as a horizontal color-coded ribbon (green=Bullish / amber=Caution / red=Bearish). Lightweight; no new chart-rendering pipeline. Could be inline SVG or HTML divs colored via CSS.
   - **Option C — Combined.** A above with a B-style ribbon below the chart showing classification history.
   - **Option D — Trader-style breadth/regime mini-dashboard.** Beyond benchmark — add SPY/QQQ/IWM relative strength, ADL/breadth proxies if data sourceable. Higher scope; potential research-branch territory.
3. **Recommend.** Match recommendation to operator's actual decision-making cadence. Daily-prep-only? Daily-prep + intra-day glance? At-trade-entry? Each cadence implies different latency tolerance + chart freshness expectations.
4. **Implementation sketch.** Once option is locked: VM extension (likely `MarketWeatherChartVM`); rendering surface (pipeline-time chart-render OR runtime SSR); template wire-up; cache discipline (matches existing weather-run cadence — daily). Estimated 2-4 hr implementation depending on option.

**Out-of-scope until investigation completes:** what specific chart library, where in the dashboard layout, frequency of refresh, mobile-friendliness considerations.

**Cross-references:**
- `swing/weather/classifier.py:53` — current classification logic (binding; do NOT reinvent).
- `swing/data/repos/weather.py:get_latest`, `list_weather_runs` — historical data source for Option B/C ribbon.
- `swing/rendering/charts.py` (if exists) — per-trade chart-rendering pipeline pattern to mirror for Option A/C.
- `swing/web/templates/partials/status_strip.html.j2` — current weather label rendering (the surface to extend or replace).
- CLAUDE.md gotcha "Matplotlib mathtext fires on `$` / `^` / `_`" — applies to any new chart titles.
- CLAUDE.md gotcha "yfinance `interval='1d'` includes in-progress bar" — applies to any benchmark-OHLCV fetch in the new chart pipeline.
- Phase 10 metrics-dashboard spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` — may have overlapping regime-display requirements; investigate during scoping.

### 3e.10 — Dark theme — **SHIPPED 2026-05-10 at `8488bf0`** (worktree dispatch; 7 commits = 3 task-impl + 3 Codex-fix + 1 orchestrator pre-gate I1)

> **Outcome:** SHIPPED via worktree dispatch on `3e10-dark-theme` branch. CSS-variable-driven theme with localStorage-persisted nav-bar toggle (🌙/☀️). Light is default; operator opts in to dark. Codex chain 3 rounds → NO_NEW_CRITICAL_MAJOR (R1 0/5/4 → R2 0/2/3 → R3 0/0/3; convergent shape). 4 Major findings ACCEPTED with sound rationale (.field-error + soft_warn_confirm + visual audit ownership + cross-tab storage event). Orchestrator-side pre-gate I1 added `color-scheme: dark` hint to pre-empt white-on-white form inputs on Windows browsers — operator-witnessed Surface 4 confirmed Config form inputs render dark + readable post-patch. Operator-witnessed gate via Chrome MCP: S1+S2+S3+S4+S5+S7 PASS; S6 covered by S3+S5 localStorage writes. Test count 2166 → 2183 (+17); ruff baseline 18 unchanged. **8 V2 watch items banked** for future polish: .field-error universal styling, soft-warn inline color, native `<details>` chevron, non-topbar link color contrast, cross-tab sync via storage event, weather badge classes (tokens defined; classes not yet in templates), toggle button initial-reconciliation sub-frame FOUC, CSP forward-compat for inline scripts. **Trade-entry-form-direct-URL noted: form is fragment-without-layout when accessed via direct URL; operator's normal "Take this trade" flow keeps form inside dark dashboard body so no operational impact.** Original entry retained.

**Observed (original, 2026-05-08):**

**Observed:** Web UI is light-theme only. Operator wants dark theme available (operator preference + reduces eye strain in evening prep windows; aligns with most modern trader-facing tools).

**Proposed fix:** CSS-variable-driven theme system. Steps:
1. Refactor existing colors in `static/style.css` to CSS variables (`--bg`, `--fg`, `--accent`, `--badge-bullish-bg`, etc.) with light-theme defaults.
2. Add a `.dark` body class with dark-theme variable overrides.
3. Add a toggle UI element (likely in nav bar or status_strip) that flips the class + persists preference via `localStorage` (cookie if server-side persistence is preferred — Phase 5 user-config infrastructure could host it but localStorage is lighter).
4. Audit chart rendering — matplotlib chart PNGs are baked at pipeline time with light backgrounds; either regenerate per theme (heavy) or accept that charts stay light-themed against dark UI (acceptable V1).
5. Verify Phase 8 daily-management timeline rendering, watchlist tag colors, hyp-rec recommendation rows, advisory badges, state badges all read correctly under both themes.

**Scope:** ~2-4 hr standalone dispatch. CSS-heavy; minimal Python/template change. No VM changes.

**Cross-references:**
- `static/style.css` — current light-theme colors.
- `swing/web/templates/base.html.j2` — body element + nav bar.
- Phase 5 user-config infrastructure (`swing.config.toml` user-config) if server-side persistence preferred over localStorage.
- Operator's actual viewing environment (browser; OS-dark-mode preference) to inform whether to add `prefers-color-scheme: dark` media-query default.

### 3e.11 — CLI `swing review` help text leaks "Phase 6" internal nomenclature — **SHIPPED 2026-05-09 at `b4bb9dd`** (polish-bundle Task family C; commit d64978a; in-scope-expanded to fix 4 additional operator-facing leaks beyond the 2 originally locked — Tranche B-ops T4/T5/T6 in entry/exit/stop-adjust rationale help + Phase 7 §10 in entry-path discriminator help)

**Observed:** `swing --help` and `swing review --help` show:
```
review       Phase 6: cadence review (daily / weekly / monthly...
```
Phase nomenclature is internal-development context, not operator-facing. The help text should describe the command's purpose self-contained.

**Locations** (per `grep -n "Phase 6" swing/cli.py`):
- `swing/cli.py:1174` — `"""Post-trade review (Phase 6).` (group docstring; surfaces in `swing review --help`)
- `swing/cli.py:1303` — `"""Phase 6: cadence review (daily / weekly / monthly Review_Log completion)."""` (subcommand; surfaces in `swing review cadence --help` AND `swing --help` group listing)

**Proposed fix:** Replace "Phase 6" leakage with self-descriptive text. Suggested:
- Group: `"""Post-trade review surface — log mistakes, process grade, and outcome attribution."""`
- Subcommand: `"""Cadence review — complete daily / weekly / monthly Review_Log entries."""`

**Scope:** 2-line change in `swing/cli.py` + 1 discriminating test asserting help text doesn't contain "Phase". ~10 min standalone fix; could bundle with any next CLI-touching dispatch. Audit other commands for similar phase-nomenclature leakage at the same time (`grep -n "Phase [0-9]\|Tranche" swing/cli.py`).

**Cross-references:**
- `swing/cli.py:1174` + `swing/cli.py:1303` — sites to fix.
- Pre-empt similar leakage in future CLI additions: per brief-drafting checklist, verify CLI help strings are operator-facing, not phase-nomenclature.

### 3e.12 — `swing tos-import` silent zero-result diagnosis — **SHIPPED 2026-05-09 at `a9541d2`**

> **Outcome:** Investigation-first dispatch (brief at `docs/tos-import-diagnostic-brief.md`) on worktree branch `tos-import-diagnostic` (BASELINE_SHA `25bbaa2`); 5 commits = 2 task-impl + 3 adversarial-fix; integration merge `a9541d2`. Investigation identified THREE mechanisms (originally orchestrator analyzed two; implementer surfaced the third empirically): (A) `Exec Time` column in real Schwab/TOS export (parser was looking for `Date`/`DATE`); (B) signed Qty (`+7` BUY / `-3` SELL) tripped `qty <= 0` guard; (C) M/D/YY date format vs journal's ISO `entry_date` blocked match-query even after (A)+(B). Operator-confirmation gate PASSED. Fix scope expanded mid-dispatch by operator clarification ("the whole point of reconciliation is to check for existence AND correct values") — broadened §3.1 from extraction-only to full-pipeline reconciliation tests. Adversarial review chain: R1 0/4/2 → R2 0/2/2 → R3 0/1/2 → R4 NO_NEW_CRITICAL_MAJOR (convergent shape; 4→2→1→0 majors). Test count 2090 → 2099 (+9; ruff baseline 78 preserved). New `_normalize_date()` helper + `FillDecision` dataclass + `tests/fixtures/tos/real-world-2026-05-08.csv` real-world fixture. New `--verbose` flag surfaces per-section row counts + per-fill price-comparison output. Post-merge smoke test against operator's actual CSV: `matched=4, already-reconciled=2, price-mismatch=0` (4 OPEN fills LAR/CVGI/VSAT/YOU reconciled with journal entry_prices matching; SGML round-trip routed to already-reconciled). Per retention discipline, this entry stays in active until next phase ship; original investigation content retained below for historical reference.

### Original entry (2026-05-08; pre-dispatch; superseded by SHIPPED outcome above)

`swing tos-import` silent zero-result diagnosis (INVESTIGATION; operator-surfaced 2026-05-08)

**Observed:** Operator ran `swing tos-import --csv "...\2026-05-08-AccountStatement.csv"` (with and without `--dry-run`). Output:
```
Cash: 0 new, 0 duplicate
Fills: matched=0, already-reconciled=0, price-mismatch=0, unmatched OPEN=0, unmatched CLOSE=0
```
Every counter is zero. Operator has open trades + at least one Phase 8 stop-change today (DHC) so the CSV almost certainly contains transactions. The CLI provides NO indication of WHY the result is empty — parser silent-fallback OR file structure changed OR everything-already-reconciled-and-empty-CSV-section all collapse to the same output.

**Possible mechanisms (NON-exhaustive; investigation must disambiguate):**

1. **CSV section-parser silent failure.** TOS Account Statement CSVs are multi-section (Cash Balance, Account Order History, Account Trade History, Profits And Losses, Forex Account Summary, etc.). The parser at `swing/journal/tos_import.py` looks for specific section headers; if Schwab/TOS renamed a section header in a recent export-format update, the parser silently produces 0 rows for that section. Pattern complement to existing CLAUDE.md gotcha "TOS-import TRD-as-withdrawal" + "Excel-quoted REF cleanup" (both 2026-04-30); same family — TOS export format drift breaking parser silently.
2. **Empty trade window in this specific export.** If operator exported only a date range with no fills (e.g., 1-day window with no trades on 5/8), parser correctly produces 0. Unlikely given operator's open trades + Phase 8 stop-change activity, but verify.
3. **All transactions already reconciled.** Existing journal state already includes all CSV transactions; `matched=0` because matched-already-skipped, but `already-reconciled` should then be > 0 (it's also 0). This rules out the "everything already done" hypothesis — parser ISN'T finding rows at all.
4. **Encoding / line-ending / BOM mismatch.** TOS CSVs sometimes have UTF-16 BOM or CRLF variants; if the parser splits on a different newline pattern than the export uses, rows silently dropped.
5. **Filename-date mismatch with parser's date-anchoring logic.** Some TOS parsers anchor to filename date; if the CSV content's session date doesn't match the filename date, rows could be filtered.

**Investigation steps:**

1. **Open the actual CSV** (`thinkorswim/2026-05-08-AccountStatement.csv`) and verify structure manually: does it contain a trades section? How many rows? What section headers does it use?
2. **Add diagnostic logging** to `reconcile_tos` (or a new `--verbose` flag on the CLI) that reports: total bytes parsed; section headers detected; rows-per-section count; sample row from each section. Operator-facing observability — converts silent-zero into observable-zero-with-context.
3. **Run synthetic-fixture comparison.** `tests/fixtures/tos/synthetic-tos.csv` is the test fixture; verify it currently parses correctly (`pytest tests/journal/test_tos_import.py`). If parser works on synthetic but fails on operator's real export, diff the structure.
4. **If section-header drift confirmed:** add per-section "found 0 rows in section X" warnings to the CLI output even on success. Pre-empts future silent-fail.
5. **Bonus:** consider extending the CLI report with "Sections parsed: Cash=1 (0 rows), Trades=1 (0 rows), Forex=0 (skipped)" so operator can distinguish "section absent" from "section present but empty."

**Scope:** ~1-2 hr investigation + 30-60 min hardening dispatch (logging, parser-error visibility). Could be bundled into a single dispatch if root-cause is clear from initial CSV inspection.

**Cross-references:**
- `swing/journal/tos_import.py` — parser code.
- `tests/fixtures/tos/synthetic-tos.csv` — synthetic fixture (CLAUDE.md gotcha "Synthetic-fixture coverage gap can mask real-world data shape bugs" 2026-05-01 — same family).
- CLAUDE.md gotcha "TOS-import TRD-as-withdrawal fix + Excel-quoted REF cleanup" (2026-04-30) — prior parser breakage on real-world export format.
- `thinkorswim/2026-05-08-AccountStatement.csv` — the actual CSV that triggered this.
- 2026-04-30 TOS reconciliation depth follow-ups bundle (BUNDLED into Phase 9 brainstorm at `31ee51c`) — Phase 9 will redesign the reconciliation surface; this investigation may inform Phase 9 writing-plans (or get subsumed if Phase A of Schwab API ships first).

### 3e.13 — Top-nav "Reviews" link to `/reviews/pending` — **SHIPPED 2026-05-09 at `b4bb9dd`** (polish-bundle Task family D; commits 9dbed5a + e6717a5; V1 link-only per design lock; count badge V1.5 deferred)

**Observed:** The base template's nav bar (`swing/web/templates/base.html.j2`) renders Dashboard / Watchlist / Journal / Pipeline / Config — but NO Reviews link. The Phase 6 review list view at `/reviews/pending` is reachable only via direct URL OR via the post-review-complete HX-Redirect (per Phase 6 I3 fix). Operator workflow: there's no obvious path from the dashboard to the daily/weekly/monthly cadence reviews surface.

**Proposed fix:**
1. Add `<a href="/reviews/pending">Reviews</a>` to the base.html.j2 nav between Journal and Pipeline (workflow-aligned position — review is a journal-adjacent activity).
2. **Optional enhancement (V1.5):** add a count badge `Reviews (N)` where N = count of pending Review_Logs (mirror the existing "needs review" badge pattern shipped in Phase 6 — `swing/web/view_models/dashboard.py` has `pending_reviews_count` or similar field already).

**Scope:**
- V1 (link only): 1-line template addition + 1 discriminating test (assert nav contains "Reviews" + correct href). ~10-15 min.
- V1.5 (link + count badge): + base-layout VM extension to surface count + base.html.j2 conditional render. ~30-45 min if VMs need extension; possibly ~15 min if `pending_reviews_count` already lives on a base-layout-friendly VM.

**Cross-references:**
- `swing/web/templates/base.html.j2` — nav bar location.
- `swing/web/routes/reviews.py` (or wherever `/reviews/pending` route lives) — confirms route exists.
- Phase 6 archived follow-up "Cadence card lacks clickable 'Complete review' link" (in `docs/phase3e-todo-archive.md`) — RELATED but different gap; that's about cadence card → completion form on dashboard; this is about top-nav → review list view.
- CLAUDE.md gotcha "base.html.j2 is shared — new vm.foo field requires adding to EVERY base-layout VM" — applies if V1.5 (count badge) requires a new base-layout-dereferenced field.

**Bundling note (2026-05-09):** This item is the same size profile + UX-polish theme as 3e.5 / 3e.6 / 3e.11 (the in-flight polish-bundle-2026-05-09 dispatch at brief `1957946`). If dispatch hasn't fired yet, consider expanding the brief to a 4-item bundle. Otherwise picks up as an independent ~15-min standalone after the polish bundle ships.

### 3e.14 — Cadence card "Complete review" inline link — **SHIPPED 2026-05-09 at `b4bb9dd`** (polish-bundle Task family E; commits f46ca98 + d2d7f23; CadenceCardVM extended with `review_id: int`; E.5 audit confirmed zero hand-constructed test fixtures needed update)

**Observed:** Cadence cards on the dashboard (rendered by `swing/web/templates/partials/cadence_cards.html.j2`) display period + scheduled/completed status but have NO clickable link to the completion form when `card.is_pending`. Operator must navigate via direct URL OR (with 3e.13 in flight) via top-nav Reviews → list view → click into the matching review. The cadence card itself, where the pending status is visible, has no direct action surface. **This entry was archived as a Phase 6 V1 follow-up 2026-05-04 + lifted back to active 2026-05-09 because operator surfaced the gap during the polish-bundle-2026-05-09 dispatch and confirmed it remains valid.**

**Proposed fix:**
1. Extend `CadenceCardVM` (`swing/web/view_models/dashboard.py:292`) with `review_id: int` field (currently absent — archived fix sketch assumed `card.review_id` existed but VM doesn't carry it).
2. Populate `review_id=row.id` in the construction site at `swing/web/view_models/dashboard.py:1016-1023`.
3. Add link in template `partials/cadence_cards.html.j2`: `{% if card.is_pending %}<a href="/reviews/{{ card.review_id }}/complete">Complete review</a>{% endif %}`.
4. 2 discriminating tests: link rendered when card is_pending; link absent when completed.

**Scope:** ~15-20 min standalone; pairs naturally with 3e.13 (top-nav Reviews link) since both surface review reachability gaps from the dashboard.

**Cross-references:**
- `swing/web/templates/partials/cadence_cards.html.j2` — current card template (no link).
- `swing/web/view_models/dashboard.py:292-306` — `CadenceCardVM` definition (needs `review_id` field).
- `swing/web/view_models/dashboard.py:1016-1023` — construction site (populate `review_id=row.id`).
- `swing/web/routes/reviews.py` (or wherever) — `/reviews/{id}/complete` route confirmed Phase 6 R5 I3.
- 3e.13 (in-flight bundle) — top-nav reachability; this is the per-card direct-action surface.
- Archived entry at `docs/phase3e-todo-archive.md:736` — original 2026-05-04 capture.

### 3e.15 — Analyze utility of "logged today?" badge given pipeline auto-snapshots — **SHIPPED 2026-05-10 at `d1aed5a`** (option (a) — narrowed predicate to event_log only)

> **Outcome:** SHIPPED inline by orchestrator (single-commit; ~30 min impl). Empirical premise re-verified at code (`swing/pipeline/runner.py:997-1074` iterates `list_open_trades` with no filter; `swing/data/repos/daily_management.py:147-194` matched both record types). Design-locked option (a): narrowed predicate from `record_type IN ('daily_snapshot', 'event_log')` to `record_type = 'event_log'`. Badge now means "operator personally engaged via daily-management form" rather than "pipeline ran today." Tests: 5 existing tests renamed/fixture-switched in place + 2 new discriminator tests; full suite 2140 → 2142 GREEN. **Operator-facing impact:** open trades will show ⚠ pending after pipeline runs unless operator submits an event_log entry; this is the intended contract (badge previously was effectively decorative once pipeline ran).

### Original entry (2026-05-09; pre-dispatch; superseded by SHIPPED outcome above)

**Operator question (Surface 2 verification 2026-05-09):** "Will running the pipeline end up causing all open trades to report logged? If so, analyze utility of tracking the pending/logged status."

**Empirical answer (orchestrator-confirmed):** YES. Phase 8 `_step_daily_management` (per `swing/pipeline/runner.py` after `_step_evaluate`) writes a `daily_management_records` row with `record_type='daily_snapshot'` AND `review_date == last_completed_session()` for every open trade. The polish bundle 2026-05-09 badge predicate (per the cfacbc5 fix) is `record_type IN ('daily_snapshot', 'event_log') AND is_superseded = 0 AND review_date == last_completed_session()`. **After every successful pipeline run, every open trade satisfies this predicate → every badge shows ✓ logged.** The badge as currently defined cannot distinguish "pipeline auto-snapshot landed" from "operator paid attention today" — it collapses two distinct concepts into a single state.

**Window of utility (current behavior):** the badge is operator-actionable ONLY between (a) the start of a new session AND (b) the next pipeline run. Once pipeline runs, badge degrades to "did pipeline run today?" — a question the existing pipeline-status banner already answers.

**Investigation scope:**

1. **Confirm assumption empirically.** Verify `_step_daily_management` writes for ALL open trades (not just A+ candidates / specific maturity stages). Check spec §7 + actual code at `swing/pipeline/runner.py` (the daily-management step body) + `swing/data/repos/daily_management.py:list_for_trade_timeline` predicate semantics.

2. **Enumerate operator workflow scenarios** where the current badge would be operator-useful vs. not:
   - Pre-market session prep BEFORE pipeline runs → badge meaningful (shows operator hasn't toured yet)
   - Mid-day: pipeline already ran → badge always ✓ → useless
   - Operator manually logs an event_log entry → predicate already satisfied by snapshot anyway → no visual change
   - Post-market evening review → badge meaningful only if pipeline didn't run for some reason

3. **Design alternatives to evaluate:**
   - **(a) Filter predicate to `event_log` only.** Distinguishes operator-driven entries from pipeline auto-snapshots. Badge means "operator paid attention" rather than "either source touched the row". Aligns with original operator-intent "did I log anything for this trade today?"
   - **(b) Two-state expansion to three: ✓ event-logged / ⊙ snapshot-only / ⚠ pending.** Three glyphs preserve the snapshot signal while distinguishing operator-action.
   - **(c) Operator-action-only predicate with dismissible state.** Badge clears via operator-confirmation (click-to-dismiss). Per-session dismissal stored in localStorage OR a new `daily_management_records.acknowledged_at` column. More UX surface; less doctrine-clean.
   - **(d) Drop the badge.** If operator concludes the badge isn't useful given pipeline timing, V1.5 reverses the badge addition. Polish-bundle ship would be partially superseded; orchestrator-context lesson would be captured.

**Recommendation (orchestrator preliminary):** Option (a) — filter predicate to `event_log` only. Smallest change; cleanest semantic ("operator-action today"); doesn't require new column or three-state UI. Pipeline snapshots already surface elsewhere (timeline view; `swing tos-import` style audit-trail surfaces).

**Scope:** Investigation 1-2 hr (steps 1-2 above + scope-recommendation). If recommendation is (a), implementation ~30 min standalone (predicate change + 1-2 discriminating tests + label may need adjustment from `✓ logged` to `✓ event-logged`). If (b) or (c), larger scope.

**Cross-references:**
- `swing/pipeline/runner.py` — `_step_daily_management` body (the auto-snapshot writer).
- `swing/data/repos/daily_management.py:has_update_today_for_trades` — current badge predicate (post-cfacbc5 fix).
- `partials/open_positions_row.html.j2` — current badge rendering.
- CLAUDE.md gotcha "Session-anchor read/write mismatch" (promoted 2026-05-09) — applies to any predicate change here.
- Polish bundle 2026-05-09 brief at `docs/polish-bundle-2026-05-09-brief.md` — original badge design rationale.

### 3e.16 — Trade summary section in daily/weekly/monthly review pages — **SHIPPED 2026-05-10 at `1b43efb`** (worktree dispatch; 8 commits = 4 task-impl + 4 Codex-fix; 5 Codex rounds NO_NEW_CRITICAL_MAJOR)

> **Outcome:** SHIPPED via worktree dispatch on `3e16-cadence-review-trade-summary` branch. Adds "Trade activity during this period" section to `/reviews/{id}/complete` form view with state-tagged rows (`[OPENED]` / `[CLOSED]` / `[OPENED+CLOSED]` / `[EVENT]`) per brief §0.3 #2 contract. New repo helper `list_trades_with_activity_in_period` at `swing/data/repos/trades.py` (data-layer placement chosen over view_models per layer-clean rationale). Codex chain caught real edge cases including a brief-author error on the `was_closed_in_period` predicate (would have mis-tagged partial-trim fills as `[CLOSED]`). 3 Major findings ACCEPTED with rationale (data-layer adapter import + V1 closing-fill proxy + [EVENT] semantic for fill-fallback). Operator-witnessed gate via Chrome MCP browser automation: S1+S3+S4+S5 PASS; S2 SKIPPED-with-test-coverage (could not induce truly-empty period in operator's actual data). Test count 2142 → 2166 (+24; +14 over expectation due to Codex-driven discriminator enrichment); ruff baseline 18 unchanged. Three V2 watch items banked separately below.

> **V2 watch items banked from 3e.16 dispatch:**
> 1. **Production `record_exit` ts-divergence pattern check.** R3 fix anticipated fill_datetime / paired-event-ts divergence based on Codex's reading of the exit-service code. Worth a follow-up check whether the current production `swing.trades.exit.record_exit` actually writes them separately; if always-identical, the R3 fallback in `list_trades_with_activity_in_period` is dead code but harmless.
> 2. **Phase 9 `is_closing_fill` flag (or equivalent).** R3 Major #2 ACCEPTED-with-rationale flagged that "last non-entry fill across all time" is a proxy for terminal-fill semantics; V1 schema has no closing-fill marker. Phase 9 reconciliation work (brainstorm at `31ee51c`) is the right venue for adding the explicit marker.
> 3. **CSS scoping for `.cadence-trade-summary-list` + `.trade-summary-tag`.** Brief §0.3 #9 explicitly bookmarks visual polish as V2. Class names exist in template; no stylesheet rules added — current rendering is browser-default `<ul>`/`<li>` list with bracket-tagged inline state.

**Observed (original, 2026-05-09):** The `/reviews/{id}/complete` form view (Phase 6 cadence completion surface) does NOT surface the trades conducted during the review period (entered, exited, or event-logged within the period's date range). Operator has to context-switch to other surfaces (journal, dashboard, trades list) to see what happened — defeating part of the cadence-review value (review with relevant context in front of you).

**Proposed fix:** Add a "Trades during this review period" section to the cadence completion form template. Section lists trades with activity within `[period_start, period_end]` from the Review_Log row. Per-trade summary line: ticker + entry_date + exit_date (if closed) + entry_price + exit_price (if closed) + realized_R + hypothesis_label. Possibly grouped by state (closed during period | opened during period | event-logged during period).

**Scope:**
- Extend `CadenceCompleteVM` (or whatever VM serves `/reviews/{id}/complete`) with a `trades_during_period: tuple[TradeSummaryVM, ...]` field.
- Repo helper to query trades with relevant activity within `[period_start, period_end]` (entry_date OR exit_date OR trade_event ts within period).
- Template extension in `templates/reviews/complete.html.j2` (or wherever) — render the trade list section above (or alongside) the completion form.
- 3-4 discriminating tests: trades-in-period populated correctly; trades-outside-period excluded; closed/open/event-only paths each represented.

Estimated ~1-2 hr standalone dispatch (depends on how rich the per-trade summary needs to be). Could grow if operator wants R-multiple distributions / pattern-tag aggregation / hypothesis-label rollup.

**Open design questions for brainstorm-skip in-thread lock:**
1. Group trades by activity type (opened / closed / event-only) OR show flat chronological?
2. Per-trade summary fields — ticker + dates + R only, OR include hypothesis_label + sector + chart-pattern + emotional_state aggregations?
3. Should completed-cadence read-only view also show this? (Phase 6 shipped completion form; read-only completed view is V1.5 territory per archived Phase 6 follow-up.)

**Cross-references:**
- Phase 6 completion form: `swing/web/templates/reviews/complete.html.j2` (or partial per template structure).
- `swing/web/view_models/dashboard.py:CadenceCardVM` — has `period_start` + `period_end` fields; the completion form likely has the same window via Review_Log row.
- Trades repo: `swing/data/repos/trades.py:list_open_trades` + `list_closed_trades` — likely starting point for the new "list_trades_with_activity_in_period" helper.
- Phase 6 archived follow-ups at `docs/phase3e-todo-archive.md:737` ("Completion route 404s for already-completed Review_Logs") — related; both are completion-form-extension territory.
- Aligns with Phase 6 v1.2 §10.3 "Cadence Review Workflow" — reviewing trades-during-period is the canonical workflow per spec.

### 3e.2 — Include realized-from-partial-exits in journal stats total

**Observed:** `swing journal review --period month` shows 0 trades / $0.00 total
when you have 1 partial exit recorded on a still-open trade. The realized $0.74
is in the DB and in the Account card, but not in the journal stats.

**Proposed:** Split the journal stats into two figures:
- **Closed-trade metrics** (existing): win rate, expectancy, avg win/loss, R multiples
  — require a full trade cycle to compute
- **Cash-realized total** (new): sum of `realized_pnl` across ALL exits in period,
  regardless of whether the trade is closed

**Rationale:** "What have I made this month?" should include locked-in partial
exits even on open trades. R-multiple math doesn't fit a partial, but dollar
P&L does.

**Scope:** Journal stats computation + review output. Phase 2 untouched.

---

## Tranche B-ops deferred items (2026-04-24)

Items surfaced during Tranche B-ops sessions 1 (design) and 2 (execution) that were deliberately deferred. See the session-1 design spec §8 (`docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md`) for full context on items marked (§8).

### From design (§8):

- **Pipeline-linkage bundle** — add `evaluation_run_id` FK on `pipeline_runs` + new `pipeline_chart_targets` table keyed on `(run_id, ticker)`. Would eliminate both chart-scope drift modes documented in spec §4 AND subsume the `insufficient-data` → `fetcher-failed` / `too-few-bars` split. Estimated ~1 pipeline-layer session. Phase 2 carve-out required.
- **Exit-form field preservation** — `TradeExitFormVM` has the same latent preservation gap as the stop form. No live bug; the spec scopes preservation specifically to the stop form. Low-effort follow-up.
- **ExitRationale enum distinct from ExitReason** — revisit when journal analysis produces evidence that `reason=partial|manual` rows corrupt downstream queries.
- **Total-book risk cap config** — `cfg.risk.max_total_risk_pct` + warn-coloring on the Open-risk tile. Deferred until evidence about the right default.
- **Book-equity-based Open-risk percent** — requires live prices in risk math. Current denominator is realized equity.
- **Chart-reason split: `insufficient-data` → `fetcher-failed` vs `too-few-bars`** — needs pipeline-layer per-ticker chart-status persistence. Subsumed by the pipeline-linkage bundle above.

### From Session 2 adversarial review:

- **Session-gating propagation for read-only surfaces** — `DashboardVM.stale_banner` currently does not propagate to watchlist/expand and other non-dashboard surfaces. Chart-scope resolver accepts the weekend/holiday drift for this reason. A future brainstorming session would design strict cross-UI session-gating. Spec-level decision required.
- **Transport/decode img failure fallback** — Session 2 C3 intentionally dropped `<img onerror>` per spec §4 rationale (transient static-mount errors "should page someone"). If real operational experience argues for a narrow client-side fallback distinct from the server-side intentional-absence states, reconsider. Low priority; monitor.

### From Session 3 adversarial review:

- **`TradeEntryFormVM.force` pre-existing dead field** — symmetric to the `TradeStopFormVM.force` removal shipped in Session 3 C5. No template consumer; no re-render usage. Session 3 declined to touch it mid-session per scope discipline. ~5-minute cleanup commit.
- **`(str, Enum)` → `StrEnum` migration across three enums** — `ExitReason`, `EntryRationale`, `StopAdjustRationale` all currently use the `(str, Enum)` pattern and carry `# noqa: UP042`. A single-commit migration clears all three `noqa` comments at once. Cohesive, small, low-priority.

---

## Tranche C deferred items (2026-04-25)

Items surfaced during Tranche C sessions (pipeline-linkage bundle, commits `f45dae8..1cfc117`; candidate-sparsity diagnostic, commits `1b33e21..bd0dae6`) that were deliberately deferred per scope discipline.

### From pipeline-linkage bundle:

- **`build_watchlist` mixed-anchor fix.** Same disease as today_decisions / candidates_by_ticker / _step_export had pre-Tranche-C; the standalone `/watchlist` page still reads via "latest eval" rather than `pipeline_run.evaluation_run_id`. Small commit (~30-60 min) now that the FK exists. File: `swing/web/view_models/watchlist.py:50-53` (the `SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1` query).
- **Stale `pipeline_chart_targets` rows on lease revoke.** When `_step_charts` writes `'pending'` rows then crashes / is force-cleared, those rows persist for the now-force_cleared `pipeline_runs` row. Resolver only reads `state='complete'` so they're inert, but accumulate over many failed runs. Worth a `sweep_stale_artifacts`-style addition if they grow.
- **"no-run" chart-reason wording inconsistency.** Pre-existing message says "for this session" but resolver is no longer session-gated. Revisit only if operators report confusion.
- **Per-ticker `fenced_write` granularity in `_step_charts`.** Each ticker outcome is its own `lease.fenced_write()` transaction (~15 small transactions per pipeline run). Acceptable now; if chart-step performance becomes a bottleneck, batching the per-ticker UPDATEs into a single fenced commit at end-of-step is straightforward.

### From candidate-sparsity diagnostic:

- **Hypothesis 5 — Production-vs-replay parity check.** The diagnostic's most-permissive matrix cell (Russell 3000 5×) reaches 0.0098%; production observation (Session 2a) is ~0.5%. **~50× residual gap unexplained** by universe + capital combined. Cheapest applied-research follow-on: side-by-side comparison of harness `evaluate_one` output vs production pipeline output for same inputs over the same window. Surfaces any silent code drift between research-branch reuse and production execution. Estimated ~1 session, applied-research scope.
- **Hypothesis 6 — Finviz universe reconstruction.** Most explanatory route to closing the residual gap but multi-week scope. Reconstructs the time-series of operator's actual Finviz-filtered universes to test universe-source hypothesis. Out of scope absent specific reason and time budget.
- **Newcombe interval on cross-universe rate difference.** Diagnostic R2 review noted the disjoint-CI rule has anti-conservative properties; a formal Newcombe interval on (p_C − p_A) would be the proper instrument. The qualitative-direction conclusion is robust to choice of test; nice-to-have refinement, not load-bearing.
- **Supplementary `--base-capital 100000 --capital-multiplier 1.0` parity run.** Would reproduce Session 2c's 11 A+ count (or surface a parity drift) and close the matrix's third capital interval [$37.5k, $100k]. Pre-authorized as thin follow-on if hypothesis-5 work happens.
- **`recompute_binding_prod_gated.py` parameterization.** Currently hardcoded against `build_harness_config()`. If a future diagnostic uses different criteria configurations, parameterize. Defer until that need arises (registry-maximalism risk per V2.1 anti-patterns).
- **Methodology lesson — production-gating-aware instrumentation as standing pattern.** Captured durably in `docs/orchestrator-context.md` §"Lessons captured." When instrumenting production logic for diagnostic measurement, mimic production's gating order, not criteria emission order. Future diagnostic instrumentation should adopt this pattern from the start.

### Capital-sensitivity finding disposition (informational):

The diagnostic established that risk_feasibility blocking is highly capital-sensitive in proportional terms but modest in deterministic A+ count terms. Operator (2026-04-25) declined to act: "the amount of money available is the amount of money available; without proven history, doesn't make sense to raise capital 2 orders of magnitude to go from 5 months to 2.5 months per A+ candidate." Recorded here so future operator/orchestrator sessions don't re-litigate.

---

## 2026-04-25 parallel-work follow-ups

Items surfaced during the parallel `build_watchlist` mixed-anchor fix (commit `77877c1`) and harness-vs-production parity check (commits `c47a783..1a88fb7`) that were deliberately deferred per scope discipline.

### From `build_watchlist` mixed-anchor fix:

- **Stale banner on `/watchlist`.** `WatchlistVM.stale_banner` is currently always `None` on the standalone `/watchlist` page despite being declared. On "new day, no fresh pipeline yet" workflows the page can render today's session_date alongside flag tags from the previous completed pipeline. Moderate-scope follow-on: touches `WatchlistVM`, `build_watchlist`, watchlist template; coordinates with the base-layout shared-VM gotcha listed in CLAUDE.md (every base-layout VM must gain new fields). Mirror `build_dashboard`'s stale_banner derivation at `dashboard.py:154-165`. Genuine UX gap; defer until you want to scope a session for it.
- **Deterministic tiebreaker on `ORDER BY finished_ts DESC LIMIT 1` (class-level pattern).** Several query sites in `swing/web/` (dashboard.py:107-111, 143-147, 155-159; watchlist.py uses the new pattern in `build_watchlist` post-`77877c1`; `build_watchlist_expanded` separately) use second-precision timestamp ordering without a deterministic tiebreaker. **Recommendation: defer indefinitely.** SQLite second-precision collision requires two pipeline completions in the same second — essentially impossible given pipeline runtime. Pre-existing across the layer; cost is small but value is theoretical until we see an actual collision in the wild. Capture here so a future session doesn't accidentally pick it up as urgent.

### From harness-vs-production parity check:

- **Multi-run parity characterization.** The Tier 1 result is on n=1 production run (eval_15, action_session 2026-04-25). For tighter inference, run the parity comparator across the last 5–6 production runs with preserved Finviz CSVs. Operator-decision gated; not urgent given the Tier 1 single-run result.
- **A+-surface-exercising parity run.** The n=80 eval_15 produced zero A+ candidates, so parity at A+ classification level is empirically unverified. Pick a historical production run that produced ≥1 A+; verify parity at A+ level. Not urgent given Tier 1 already verifies the watch/skip-level classification logic.
- **Parity comparator as periodic regression check.** Open question whether to run the parity comparator on every release or never again. **Recommendation: never-again unless a future change to `swing/evaluation/` or `research/harness/` specifically warrants it** (any change to the production scoring chain or the harness's evaluator wrapper). The comparator is durable in `research/parity/`; re-running is ~30 min when the question recurs.
- **`PriceFetcher` cache-stat introspection.** Production's `swing.prices.PriceFetcher` does not expose hit/miss counts; the parity comparator wrapped it in `_CountingPriceFetcher` (in `research/parity/run.py`) to report cache stats in the D3 manifest. Minor architectural gap; backlog item for if cache observability becomes operationally valuable elsewhere in the production layer.

---

## 2026-04-25 Bug 1 follow-ups (watchlist Enter-button event-propagation)

Items raised by Codex during Bug 1's adversarial review (commit `9aabe8b` shipped) and accepted-with-rationale per scope-bounded brief. Captured here for future-session pickup; not urgent but real architectural concerns.

- **Watchlist row HTMX trigger architecture refactor.** The current row design — `<tr hx-get="/watchlist/<ticker>/expand">` makes the entire row a click target — means any interactive child added to the row (button, input, link) has to remember `onclick="event.stopPropagation()"`. Bug 1's fix is a point-fix at the Enter button; it doesn't prevent recurrence with future interactive children (e.g., when Phase 3e §3e.5's "Log entry" button replaces the existing CLI placeholder in `watchlist_expanded.html.j2:33`). Two architectural alternatives:
  - **Option A: dedicated chevron cell** — move the expand trigger from the row to a leftmost `<td class="expand-trigger">` chevron. Visual UI change; explicit affordance for expand.
  - **Option B: scope the trigger** — use `hx-trigger="click from:td.row-trigger"` to limit the row's expand trigger to a specific cell or class. Invisible to user; same effect as Option A.
  - **Recommendation when scoped:** Option B unless operator wants the chevron UI affordance. Estimated ~1-2 sessions including tests. Picks itself up when more row-level controls ship.
- **JS-execution test harness gap.** Project currently uses FastAPI TestClient + assertion on rendered HTML strings for web-layer tests. Sufficient for server-side rendering correctness; INSUFFICIENT for JavaScript event behavior, HTMX runtime swap targeting, DOM updates after script execution, and CSS-driven visual states. Bug 1's fix test (string-match `stopPropagation`) confirms the attribute is present but does NOT confirm the runtime behavior is correct — operator manual verification is the actual confidence source. Adding a JS test harness (Playwright or Selenium) would close this gap but adds: heavy dependency (chromium driver), slow tests (browser startup overhead), flakiness risk (timing-dependent failures), CI complexity. **Recommendation: defer** until either (a) 5+ event-handling-related bugs accumulate, (b) chart-pattern algorithm or other rich-UI work approaches and would benefit, or (c) manual verification becomes a bottleneck. When scoped: ~2-4 sessions for harness setup + CI integration + re-architecture of test patterns. For now, manual verification remains the JS-behavior testing surface for the project.

---

## 2026-04-25 Bug 2 follow-ups (trade entry form vanishes mid-typing)

Items flagged by the Bug 2 investigation (commits `04ef355` → `20d2cab` shipped) as defense-in-depth opportunities and pre-existing degradations not in the fix scope.

- ~~**`_handle_any` HX-Target-awareness (defense-in-depth).**~~ SHIPPED 2026-04-26 as Session 1 T7 of the QoL UI-polish bundle (commit `d9603c9`). `_handle_any` now uses `_is_row_swap_target(request)` and `_ROW_TARGET_PREFIXES`-aware fragment selection, mirroring `_handle_http_exc`. Latent risk for unhandled non-HTTPException raised inside row-target routes is closed.
- **Sizing-hint hx-trigger parsing bug (pre-existing behavioral degradation).** Current trigger string in `partials/trade_entry_form.html.j2` (sizing-hint span): `change from:input[name=entry_price],input[name=initial_stop] delay:200ms`. Per HTMX 2.0.3's tokenizer, this parses as TWO separate triggers because HTMX splits on top-level commas: (1) `change` event from `input[name=entry_price]` with NO delay (delay:200ms attaches to the second trigger only); (2) `input` event with broken filter expression `[name=initial_stop]` which compiles into `event.name = (event.initial_stop ?? window.initial_stop)` — always evaluates undefined → never fires. Net effect: sizing-hint fires correctly on entry_price changes (without intended debounce) but NEVER fires on initial_stop changes. **Recommendation:** likely fix is HTMX's parens-grouped from-selector syntax: `change from:(input[name=entry_price],input[name=initial_stop]) delay:200ms`. Verify against HTMX 2.0.3 behavior (test in browser; check HTMX docs). ~30 min including a smoke test that asserts both fields trigger sizing-hint requests with debounce. Behavioral degradation; affects sizing feedback UX but not correctness. **2026-04-29 update:** investigation-first bug-fix dispatch's DevTools capture confirmed `htmx:syntax:error: Invalid left-hand side in assignment` fires on EVERY entry-form render at `partials/trade_entry_form.html.j2:22-23` from the same selector. Severity confirmed; fix is the parens-grouped syntax above. Form still works because HTMX recovers from the syntax error, but every form open logs a JS error. Prioritize bundling with other entry-form-touching dispatches (reuses operator-witnessed-verification overhead) OR pick up standalone if a CLAUDE.md gotcha entry isn't sufficient.

### Bug 2 root-cause fix history note (informational, not a follow-up)

Bug 2's actual root cause was **not** the form-submit ValueError path that the first fix attempt (`04ef355` → `20d2cab`) addressed. The actual mechanism was sizing-hint span `hx-target` inheritance from parent `<form>`: the span had no explicit `hx-target`, so it inherited `hx-target="closest tr"` from the form, causing every sizing-hint hx-get response to swap into the entry-form `<tr>` position — replacing the entire form with just the sizing-hint span. Real fix: `2a167d1` adds explicit `hx-target="this"` to the sizing-hint span (one-line). The first fix is preserved as defense-in-depth (correct behavior for actual form submission with stop≥entry). Lesson captured in `docs/orchestrator-context.md` anti-patterns: "Bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction"; mitigation in operating-processes via investigation-phase operator-confirmation gate for INVESTIGATION-FIRST bug-fix briefs.

---

## 2026-04-25 hypothesis-engine + analyze + backup follow-ups

Items surfaced from the Monday-prep operational batch (commits `4a565c6` → `fe270a6`).

### From hypothesis-recommendation engine work:

- **WatchlistVM extension for active recommendations** (optional). hyp2 declined per scope discipline — dashboard + CLI pre-fill cover the primary loop; the watchlist page already shows flag tags. If operator wants the standalone `/watchlist` page to also list active recommendations, clean follow-up: add `active_recommendations` field to `WatchlistVM`; render the same partial in the watchlist template. ~30 min work.
- **Monitor for first hypothesis closure → revisit longer-horizon planning.** Per orchestrator-context.md 2026-04-25 entry: when the first hypothesis closes (target sample met OR tripwire-fired escape), revisit the longer-horizon planning question with operator. Likely first to close: Sub-A+ VCP-not-formed (5-sample target; VIR is sample 1) or A+ baseline (20-sample) depending on operator's actual identification + take pace.
- **Hypothesis registry-mutation discipline (operator-facing).** Per pre-registration discipline, only `status` is mutable via `swing hypothesis update`. To add a NEW hypothesis or change target_sample / tripwire / decision_criteria of existing hypotheses requires a formal new migration (e.g., `0009_hypothesis_v0.2_amendment.sql`). This boundary is a feature, not a limitation; preserves anti-rationalization integrity. If operator decides to add hypothesis 5 (e.g., post-first-closure planning), it's a small Phase 2 carve-out: new migration + seed.

### From `swing trade analyze` CLI work:

- **Cross-contamination commit-title misattribution.** Commits `375344f` (titled "feat(pipeline): trigger weekly DB backup...") and `43b4d35` (titled "feat(cli): add db-backup subcommand...") accidentally bundled trade-analyze implementer's work due to parallel `git add` race. Code is correct; commit titles are misattributed. Could be addressed via git notes if attribution preservation matters; recommendation per orchestrator-context.md 2026-04-25 lesson is to leave as-is (the lesson is durable; archaeology fix is administrative overhead). Future parallel dispatches should use git worktrees to prevent this class of issue.

### From weekly DB backup work:

- (No follow-ups; clean implementation.)

---

## 2026-04-26 QoL bundle + watchlist sort follow-ups

Items surfaced during the QoL UI-polish bundle (Session 1, commits `4c264b2..d9603c9` + adversarial fixes `61424f2`, `20ecc70`, `d9ab7ff`) and the watchlist sort-by-tags session (Session 2, commits `1d6ed42..e613f39`) that were deliberately deferred per scope discipline. Adversarial review reached `NO_NEW_CRITICAL_MAJOR` in both sessions (Session 1 R3, Session 2 R5).

### From Session 1 (QoL UI-polish bundle):

- **Target-family-aware error fragments (Session 1 R1 Major 2 — accepted, not fixed).** `partials/trade_form_error.html.j2` hardcodes `colspan="8"`; watchlist row tables use 7 cells. Affects both `_handle_any` (T7 just shipped) and `_handle_http_exc` (pre-existing) symmetrically. Browsers tolerate `colspan` greater than column count, so functionally non-blocking; structural correctness would pick a fragment per `_ROW_TARGET_PREFIXES` family. Cheap follow-up when a future row-target table gains a different cell count or when a stricter validator complains.
- **Alternating-row CSS scoping (Session 1 R1 Minor 2 — accepted with rationale).** Global `tbody tr:nth-child(even) td` rule may bleed striping into future tables that don't want it. Currently relies on source-order vs `tr.tripwire-fired`. If a future class needs to override, increase its specificity (e.g., `tr.expanded > td`) or scope the alternating rule to specific tables (`#open-positions tbody tr:nth-child(even) td`). Operator manually verified that `tr.expanded` rows currently inherit the underlying stripe color naturally — no awkward mid-table jump.
- **`build_watchlist_row` single-ticker performance (Session 1 R2 Minor 1 — accepted with rationale).** `swing/web/view_models/watchlist.py:build_watchlist_row` scans the full active watchlist and full candidates list to render one row. Acceptable today; **trigger threshold: watchlist > ~100 rows**, at which point add a single-ticker variant of `list_active_watchlist`.
- **Close-button server-round-trip failure model (Session 1 R2 Major 1 — accepted with rationale per Option-A spec).** A transient backend failure on `/watchlist/<ticker>/row` (collapse) can leave the row temporarily stuck expanded or replaced with an error fragment. Identical failure model to `/expand`. If operator-visible failures occur, evaluate Option B (client-side stash + collapse via cached compact-row HTML).

### From Session 2 (watchlist sort-by-tags):

- **Centralize eval-anchor resolver (Session 2 R2 Minor 3 — accepted, out of scope).** The same ~10-line `pipeline_runs.evaluation_run_id`-with-fallback block now lives in three places: `swing/web/view_models/dashboard.py:73-86` (already factored as `latest_evaluation_run_id`), `swing/web/view_models/watchlist.py:59-66`, and `swing/web/routes/pipeline.py` `/prices/refresh` route. The dashboard module already exports `latest_evaluation_run_id`; the other two sites should consume it. ~30-min DRY refactor.
- **Extract `swing/web/watchlist_ranking.py` module (Session 2 R1 Minor 1 — accepted, out of scope).** `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, and `_flag_tags` currently live in `swing/web/view_models/dashboard.py` and are imported from `watchlist.py` and `routes/pipeline.py`. Module extraction would clarify ownership; minor cleanup.
- **Decouple `_TAG_PRECEDENCE` from UI label strings (Session 2 R1 Minor 3 — accepted, out of scope).** `_TAG_PRECEDENCE` is keyed on the same presentation strings (`"TT✓"`, `"VCP✓"`, `"A+"`) that templates render. A future label rename would silently zero out precedence (unknown keys score 0 because the fallback for unknown tags is `0`). Decoupling: introduce a tag-id enum or constants like `TAG_TT_PASS = "TT✓"` referenced from both the precedence map and the templates. Not urgent; current state is correct.
- **(2026-04-28 sector dispatch follow-up) Factor non-web utility helpers out of `swing.web.view_models.dashboard` once 3+ cross-imports exist.** Surfaced during sector-capture writing-plans dispatch return report. Pattern observation: `latest_evaluation_run_id()` is now imported by CLI for sector auto-resolution (sector dispatch Task 7), making it the second cross-import from `swing.web.view_models.dashboard` (first precedent: `_lookup_active_recommendation_label` for hypothesis pre-fill). Currently fine — two consumers is below the refactor threshold. **Trigger:** when a third non-web call-site needs to consume one of these helpers, factor them into a non-web-bound module (likely `swing/data/utils.py` or similar). Picks itself up naturally.
- **(2026-04-29 journal-flag fix follow-up) Emit a dedicated "all winners closed same-day" behavioral flag instead of silently skipping the losers-held-too-long ratio.** Current behavior post-2026-04-29 fix: when `avg_w == 0` (all winners are same-day-open-and-close), `_losers_held_too_long` returns None (silent skip). The same-day-winner pattern is itself a behavioral signal worth surfacing — operator may be cutting winners short by closing same-day instead of letting them run. Proposed flag: code `winners_closed_same_day`, title "All winners closed same-day", detail along the lines of "{N} winners closed same-day; consider letting winners run multi-day for trend continuation." Defer until operator confirms the signal is operator-relevant (currently the losers-held flag is the canonical "behavioral concern" surface; adding a parallel flag is a UX decision). Small dispatch when picked up: extend `_losers_held_too_long` OR add a sibling `_winners_closed_same_day` function in `swing/journal/flags.py`; add discriminating regression test mirroring the just-shipped guard test.

- **(2026-04-29 production-verification investigation dispatch follow-up) `/watchlist` standalone entry-flow polish (R1 Critical 1 ACCEPTED).** Trade records correctly via the `/watchlist` standalone page; UX is silent (no confirmation banner; no on-page open-positions table; no toast). Operator confirms trade was recorded by navigating to dashboard. Operator workflow is dashboard-centric so low-priority. Proposed enhancement: toast notification on success + status-strip rendering + open-positions section parity with dashboard flow on the standalone `/watchlist` page. Investigation evidence at `C:/tmp/bug-probe/` (2026-04-29; may decay; reproduce on demand). ~1-2 dispatch cycles when picked up.

- **(2026-04-29 production-verification investigation dispatch follow-up) Shared protocol/dataclass for `hypothesis_recommendations.html.j2` partial (R3 Minor 1 ACCEPTED).** Duck-typed VM contract — `vm=dashboard_vm` and `vm=HypRecsSectionVM` both work today because the partial only reads `vm.active_recommendations`. Future template edit reading another field could break one consumer. Long-term hardening: introduce a shared protocol (e.g., `class HypRecsConsumerVM(Protocol)`) with the partial's required fields; both consuming VMs implement it; partial template-typed against the protocol. Discipline currently documented in source comments at the call sites. Pick up when (a) the partial gains a new field reference OR (b) a third consumer joins.

- **(2026-04-30 OHLCV archive Phase 3 follow-up) `research/parity/run.py:178` references removed `_cache_path` method on `PriceFetcher`.** Phase 3's PriceFetcher refactor removed the `_cache_path` method (replaced by per-ticker archive helper). `research/parity/run.py:178` still calls it — research-branch CLI code (per CLAUDE.md bifurcated architecture); not in fast suite; runtime-fails if invoked. Not used in production `swing/` flow. **Bundle into Phase 4 cleanup-remainder dispatch** (or fold into the eventual `_CountingPriceFetcher` rewrite that the new archive directory shape requires for cache-stat introspection).

- **(2026-04-30 OHLCV archive Phase 3 follow-up) Parallel cold-start test with today-aligned archive (R1 Minor 1 advisory).** Current OhlcvCache cold-start test mocks `yf.download` empty as a safety guard against test-suite network calls; this weakens the "no network call" claim because the discriminating contract is verified via `helper_calls == ["AAPL"]` + bundle reflects archive content. Future improvement: add a parallel cold-start test using a today-aligned archive (no gap fetch needed) to assert TRUE zero-yfinance behavior end-to-end. Small additive test; ~30 min when picked up. Bundle into Phase 4 cleanup-remainder.

- **(2026-04-30 OHLCV archive Phase 3 process-meta) Task 5/6 scope co-dependency observation.** Phase 3 plan partitioned `swing/web/ohlcv_cache.py` kwargs wiring under Task 6, but the wiring had to land in Task 5 commit (`9a61d19`) to keep the fast suite green during the `fetch_daily_bars` signature change. Task 6 commit (`75526fe`) became pure test-additive. **Generalization:** task-by-task plan partitioning can have "gotcha co-dependencies" where a downstream task's wiring must land co-temporal with an upstream task's signature change to preserve test-green throughout. Writing-plans phase should anticipate these by tracing signature-change ripple effects across consumer files; task partitioning that splits a signature change from its consumer wiring across tasks should explicitly call out the co-temporal-landing requirement. Add to writing-plans phase as a checklist item for any plan modifying a function signature that's consumed by other plan-affected files.

- **(2026-04-30 hypothesis_label web-form gap) ARCHITECTURAL: web entry form does not capture `hypothesis_label`.** Latent since 2026-04-25 hypothesis-recommendation-engine ship; surfaced by operator's CC trade entry on 2026-04-30 (per-row "Take this trade" button on hyp-recs expansion). **Concrete failure mode:** every web-form trade entry persists `hypothesis_label = NULL` (then empty string at canonicalization) → progress count never increments → tripwire never fires from web entries. Verified in `swing/web/`: ZERO references to `hypothesis_label` in views, view_models, routes, templates. CLI has full pre-fill machinery (`swing/cli.py:415-501`); web has none. VIR (id=1) only has its label because backfilled via SQL UPDATE 2026-04-25; CC (id=3) backfilled the same way 2026-04-30. **Operator workflow tax:** every hypothesis-tagged trade taken via the web form requires a SQL UPDATE backfill to attribute it correctly. Bearable at current ~50-trades/year ceiling, but real friction. **Fix scope:** small-medium dispatch (~3-5 tasks): (a) add `hypothesis_label` field to `TradeEntryFormVM` populated via the same matcher logic the CLI uses (`_lookup_active_recommendation_label` from `swing.web.view_models.dashboard` already exists; matches the cross-import note); (b) add hidden input + read-only display rows in `partials/trade_entry_form.html.j2` (mirrors the sector/industry pattern from sector capture Phase 1); (c) add `Form(...)` param + thread through `EntryRequest.hypothesis_label` in `swing/web/routes/trades.py entry_post`; (d) discriminating tests + soft-warn round-trip preserves the label (per the multi-path-ingestion lesson 2026-04-29). **Sequencing:** sequence after Phase 4 cleanup-remainder ships (operator-paced; not Phase-4-blocking). OR inline into Phase 4 if implementer has bandwidth — but operator decided Phase 4 plan continues separately, so default to standalone follow-up dispatch post-Phase-4. **Cross-references:** orchestrator-context.md "Recent decisions and framings" 2026-04-25 (hypothesis-recommendation engine framing — "dashboard PROPOSES, operator DISPOSES"); 2026-04-25 "Prefix-label convention" (operator-facing — manual labels start with canonical hypothesis name); CLI precedent at `swing/cli.py:486-501` (pre-fill logic to mirror in web). _Note: 2026-04-30 SHIPPED as Phase 4.5 hypothesis_label web-form gap fix at `f9a07bf` per orchestrator-context in-flight ledger; entry retained here for cross-reference._

- **(2026-04-30 entry-form stop-value observation; defer-investigate)** Operator reported during CC entry (Take-this-trade button on hyp-recs expansion, 2026-04-30): "the table did not have the stop values correctly populated; potentially others." Operator instruction: "we do not need to investigate further" until another instance reproduces. Logged for memory; if a second observation surfaces with screenshots or specific field values, dispatch investigation-first. **Possible mechanisms (NON-exhaustive; do NOT design fixes against these without empirical reproduction):** (a) sell-stop snapshot field reads from the wrong source (Candidate.initial_stop vs SizingResult.stop_loss vs computed-fallback); (b) origin-aware re-resolution at form-render time loses snapshot context; (c) PriceFetcher stale archive returning wrong reference price (Phase 3 just shipped; not yet operator-verified end-to-end); (d) ToCToU window between expansion-render and form-render. **No action until reproducer.**

---

## 2026-04-26 chart-pattern flag-v1 brainstorm follow-ups

Items surfaced during the chart-pattern flag-v1 brainstorm dispatch (commit chain `9583f19..081f689`, spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`, 5 adversarial Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`). Implementation Phase 1-7 SHIPPED via the per-phase dispatch chain (archived); these items are explicitly out of V1 scope.

### V2+ pattern coverage (deferred per locked-constraint #1):

- **Pennant pattern.** Same shape geometry as flag but with converging trendlines. V2 adds to `pattern` IN-list via new migration; classifier adds geometric gates for trendline convergence.
- **Cup-with-handle pattern.** Multi-month U-shape + shallow pullback near pivot. Larger geometric definition surface; likely benefits from multi-timeframe consideration.
- **Flat base pattern.** ≥5 weeks, range ≤~15%. Simpler than flag; mostly range-CV + duration check.
- **Tight channel pattern.** 2+ weeks of converging highs/lows. Variant of flag with stricter parallel-line geometry. **Methodology-reference candidate:** Lo, Mamaysky, Wang (2000) covers "rectangle" (RTOP/RBOT) which is the academic-finance name for tight-channel geometry — kernel-regression-smoothed local-extrema definitions in their §II.A are a starting point for V2 spec drafting.
- **Qullamaggie taxonomy patterns.** episodic_pivot, power_earnings_gap, parabolic_short, gap_and_go, base_breakout, ipo_breakout — all available as reference layer via the qullamaggie MCP; some require external context (earnings calendar, IPO date) and are not pure-shape classifications.

### Methodology reference for future pattern-catalog expansion (added 2026-04-28):

- **Lo, Mamaysky, Wang (2000) — "Foundations of Technical Analysis"** (Journal of Finance 55(4), pp. 1705–1765; PDF at `https://www.cis.upenn.edu/~mkearns/teaching/cis700/lo.pdf`; full reference entry in `reference/Future Work/QuantEcon/external-references.md`). Canonical academic paper on algorithmic chart-pattern detection via Nadaraya-Watson kernel regression + geometric detection on local extrema. Pattern catalog: HS/IHS, broadening top/bottom, triangle top/bottom, rectangle top/bottom, double top/bottom — 10 patterns, NOT including flag/pennant/cup-handle/base. **Use as starting-point methodology reference if V2+ pattern scope ever expands beyond the current operator V2+ list to include head-and-shoulders, triangle, rectangle, or double-top patterns.** Replication caveats: 0.3×h* bandwidth is admitted ad-hoc tuning; effect sizes small (information, not profit); sample period 1962–1996 pre-modern-microstructure. Treatment: reference-only per V2.1 §VII.F; the operator-drives-agent-serves discipline (QuantEcon companion) flags academic methodology homogenization as a risk — Lo et al. is evidence base + methodology reference, NOT prescription.

### V2 capability extensions:

- **Sort-PARTICIPATING flag tag (operator-decision; affects production UX-priority).** V1 keeps `_sort_watchlist` byte-for-byte unchanged; flag tag is parallel render-only data via `pattern_tags`. Promoting to sort-participation would change watchlist ordering — affects production UX-priority surface and would require V2.1 §VII.F protocol.
- **Calibration study (algo vs operator agreement-rate).** Gated on 20+ overrides accumulated. Compares `chart_pattern_algo` vs `chart_pattern_operator` to surface algorithm bias / blind spots / threshold-mis-calibration. Output: tuning recommendations for `cfg.classifier.*` defaults and `cfg.web.flag_pattern_display_threshold`.
- **Slow-test live-fetch suite (`tests/evaluation/patterns/test_flag_classifier_live.py`, `@pytest.mark.slow`).** Exercises classifier against live yfinance pulls for upstream-data-format-drift detection. Deferred per V1 scope; useful when yfinance API changes or pandas/numpy upgrades land.
- **Tuning-history versioning.** Record `cfg.classifier.*` values per pipeline run alongside the cached classification. Currently `components_json` captures clearances but not the threshold values themselves; without history, retroactive analysis can't distinguish "operator override during low-tightness window" from "operator override after we tuned tightness threshold." Modest scope: extend cache schema, capture threshold dict at compute time.
- **Manual-trade fallback for out-of-chart-scope tickers.** V1 explicitly does not handle this — operator entering a trade for a ticker not in chart-scope sees "Not classified" stub with override surface hidden. V2 adds synchronous classifier fetch on form load (single-ticker yfinance pull + classifier run + persist). Adds entry-time latency (~1-3s for cold fetch); needs cache-warm check + circuit-breaker discipline.
- **Multi-timeframe classification (weekly + daily).** V1 is daily-only. Some patterns (cup-with-handle, long bases) are more naturally weekly. V2 extension: classifier accepts both timeframes; gates can require confirmation across timeframes.
- **Real-time / intraday classification.** Out of V1 scope; classifier runs on completed-bar daily data. V2 candidate if intraday execution becomes operator-relevant (currently it's not — daily-cycle workflow).

### V2 schema / hardening:

- **Schema-layer hardening for trades cross-column constraint.** V1 enforces the `chart_pattern_algo='flag' iff confidence IS NOT NULL` invariant at the repo layer (`insert_trade_with_event` raises `ValueError`). Schema-layer enforcement requires CREATE-COPY-DROP-RENAME migration — heavyweight. **Bundle with the next column-change migration on `trades`** to amortize the cost. Risk in the meantime: non-repo writers (raw SQL via sqlite3 CLI, future migrations) can violate the invariant.
- **Hidden form-field tampering hardening for chart_pattern_classification_pipeline_run_id.** V1 accepts the field as operator-claimed input from a hidden form field (per §3.6 threat model: "operator-claimed input, not server-verified provenance"). For personal-use single-operator scope this is acceptable residual risk. V2 hardening: re-resolve cache at submit + validate against form-supplied pipeline_run_id; refuse if mismatched.
- **Dashboard banner for classifier-error count per pipeline run.** V1 emits `logger.warning` per-ticker on classifier exception + end-of-step error count summary log line. Dashboard surface deferred — pipeline logs cover the operational visibility gap. V2 surface = banner showing "Pipeline N had X classifier errors" with drill-down to which tickers.

### Process / lessons-derivative:

- **`swing/web/watchlist_ranking.py` module extraction (per 2026-04-26 deferred item) — natural place to land flag-tag separation if extracted.** `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, `_flag_tags` currently in `swing/web/view_models/dashboard.py`; flag-tag rendering also lives in `_pattern_tags`. Bundling all tag/sort logic in one module clarifies ownership and provides a single edit point for future pattern additions.
- **§1.2 doc inconsistency fix.** Spec §1.2 item 2 originally said "three trade columns" but R4 added a 4th (audit anchor). Fixed in this housekeeping commit; preserved as a lesson on doc/spec drift across adversarial review rounds.
- **d266e5f commit message says "R3 fixes" but is actually R4 fixes.** Implementer flagged; preserved per no-amend rule. Commit substance is correct; only the message header is inaccurate.

---

## 2026-04-27 chart-pattern flag-v1 V1-ship gates (operator-paced; long-horizon)

> Tasks 7.1 + 7.2 SHIPPED via Phase 7 implementer-side dispatch (archived). Tasks 7.3 + 7.4 retained here as operator-paced; cross-referenced from `docs/orchestrator-context.md` §"Currently in-flight work."

- **Task 7.3 (operator-paced fixture labeling, ≥15 fixtures)** — operator's earlier framing: blocked more by external constraints (figuring out best way to label) than by orchestrator-side bandwidth. No urgency. Loader + parametrized test infrastructure shipped at `tests/evaluation/patterns/fixtures/README.md` + `test_flag_classifier_integration.py`.
- **Task 7.4 (FP-biased classifier tuning checkpoint)** — gated on Task 7.3. Per Q2 (2026-04-27): operator does manual FP/FN classification from pytest output; no automated aggregator added in V1. Tune `cfg.classifier.*` if FP > FN per spec §3.1.4.

---

## 2026-04-27 chart-pattern flag-v1 manual verification round 1 — Tier 3 operator-design questions (retained)

> Tier 1 (mathtext fix) + Tier 2 (chart-image route + open-positions expand + chart-scope alignment) + Tier 4 (verification doc fixes) all SHIPPED — see archive. Tier 3 items retained here; also cross-referenced from `docs/orchestrator-context.md` §"Operator-paced items."

5. **Lightning icon trigger logic re-evaluation.** Current rule: `price >= 0.99 × entry_target`. Operator surfaced concern that simple "near pivot" indicator may not be the right "actionability" signal post-Phase-4 (with richer tag tier + pattern classification + hypothesis-recommendation engine). Options enumerated in `docs/chart-pattern-flag-v1-manual-verification-results.md`.
6. **Multiple concurrent advisories vs single price-stop field.** Open positions can show multiple trail-stop advisories (e.g., 10MA + 20MA based) but trade row supports only one stop value. Reconciliation needed: state-machine when stop adjusted to satisfy one but not all advisories. Phase 3d follow-up. _Operator framing recorded 2026-04-27 (verification-results doc §#6): maximum-communication principle — annotate, don't suppress; trade-maturity gating concept (default 20MA early, upgrade to 10MA after ~+1.5-2R)._

---

## 2026-04-28 chart-scope policy v3 (4th tier `hypothesis_rec`) — operator-paced deferral

> Chart-scope policy v2 SHIPPED 2026-04-28 (`c4820d0..527e334`); follow-up V1-deferred items + hyp-recs trade-prep expansion design — all archived. v3 retained as the only OPEN item.

**Original deferral per hyp-recs trade-prep expansion brainstorm Q2 (2026-04-28):** "Chart unavailable message for now is fine. We may eventually adjust the rules for when charts are created, that will be explicit direction from me if/when I feel the workflow needs it."

**2026-04-30 reaffirm-deferral signal:** operator took CC trade (hyp-rec; Sub-A+ VCP-not-formed); chart was unavailable per design (CC not in `aplus + open_position + tag_aware_top_n`). Operator wanted to view chart for hyp-rec trade-decision; "Chart unavailable" was working as designed but cost was real. **Operator decided to keep deferring** rather than dispatch v3 now. Trigger condition was nearly hit; track future occurrences as accumulating signal.

**Fix scope when picked up:** mirrors chart-scope policy v2 cycle structurally — migration 0013 extends `pipeline_chart_targets.source` CHECK to allow `'hypothesis_rec'`; resolver gains 4th tier (`aplus > open_position > tag_aware_top_n > hypothesis_rec`); pipeline `_step_charts` enumerates hyp-recs and renders charts. Cost: +5-15 chart renders per pipeline run (bounded by hyp-recs panel size). With Phase 3 OHLCV archive shipped, the yfinance cost is mostly archive cache hits. Brainstorm-skip viable when picked up — Q1-Q6-equivalent of v2 already known.

---

## 2026-04-30 Phase 4 cleanup-remainder follow-up

- **(2026-04-30 Phase 4 Task 7 follow-up) Promote 7-day staleness threshold to a public constant in `swing/data/ohlcv_archive.py`.** Phase 4 Task 7 inlined a `_STALENESS_THRESHOLD_DAYS = 7` class constant in `research/parity/run.py:_CountingPriceFetcher` because the data-layer's predicate is inlined at line 205-210 with no public symbol; promoting it would have required a `swing/data/` carve-out beyond Phase 4 scope (research-branch rewrite). **Risk:** if the data-layer threshold ever changes from 7, the wrapper's duplicate must be updated in lockstep — easy to miss. Promote when a `swing/data/ohlcv_archive` touch becomes natural (next archive-related dispatch).

## 2026-04-30 TOS reconciliation depth follow-ups (BUNDLED — single dispatch)

Surfaced after operator dry-ran + reconciled the 4/30 Schwab/TOS export against the production DB. Current `reconcile_tos` only verifies a SUBSET of the disagreement surface; three concrete gaps where TOS-vs-DB drift would pass reconciliation silently. **Operator decision 2026-05-01: bundle all three as a single dispatch ("real reconciliation depth").** Estimated half-day; not orchestrator-blocking; pick up when operator-prioritized vs Phase 5 / Tier-3 #6 / chart-scope-v3.

### What `reconcile_tos` verifies today (audit-trail anchor):

- **OPEN fill (BUY TO OPEN):** ticker + entry_date + qty matched against `find_open_trade_by_match`; entry_price compared with `price_tolerance` (default $0.01). Mismatches surface in `price_mismatch_fills`.
- **CLOSE fill (SELL TO CLOSE):** ticker matched against `find_any_open_trade`; cumulative qty across the batch ≤ `initial_shares`. **No price comparison.** No-match attempts a historical-claim against unclaimed recorded exits before falling through to `unmatched_close_fills`.
- **`Account Order History` section:** parsed by `parse_tos_export` but NEVER consumed by `reconcile_tos`. Working orders, stops, OCO triggers — all silently dropped.
- **`Equities` section, `Profits and Losses` section, `Account Summary` net-liq:** not parsed at all (sections aren't in `_SECTION_LABELS`).

### Gaps to address:

- **(1) CLOSE-fill price-mismatch detection.** Symmetric to the OPEN-fill check at `swing/journal/tos_import.py:193-194`. If TOS reports `SLD -5 X @42.50` but the recorded exit's `exit_price = 42.30`, surface to `price_mismatch_fills` (or a sibling `close_price_mismatch_fills` field if separate categories matter). Small fix (~30 min): in the CLOSE branch (line 208-244), after a successful match, compare `f.price` to the matching exit's price and route to the mismatch list. Need to identify WHICH exit row matched the fill — currently the live-allocation branch doesn't track that explicitly. Likely need to refactor the within_batch_alloc tracking or add an exit-id lookup. **Test:** seed an open trade with a recorded partial exit at $42.30; pass a TOS CSV with a CLOSE fill at $42.50; assert it surfaces as price_mismatch.

- **(2) Stop-order reconciliation against `Account Order History`.** TOS exports include WORKING SELL TO CLOSE stop orders in this section (e.g., the operator's 4/30 CSV has CC stop at `20.51` and DHC stop at `7.06`). `reconcile_tos` currently parses but ignores the section. Add an extractor for the STP rows + a new report category `stop_mismatches: list[(ticker, db_stop, tos_stop)]`. For each open trade, look up the corresponding TOS WORKING stop; compare `current_stop` with the TOS stop price within `price_tolerance`. Surface mismatches. ~1-2 hr including parser + reconciliation logic + tests. **Notable parser challenge:** the Order History section has variable columns + the stop value lives across two row types (`TRG BY #ref` parent row + child row with the actual stop price); needs careful parsing. **Test:** seed open trade with current_stop=20.00; pass TOS CSV with WORKING stop at 20.51; assert mismatch surfaces.

- **(3) Position-level holdings reconciliation against `Equities` section.** TOS lists current open quantities per ticker (e.g., operator's 4/30 CSV shows `CC +5` and `DHC +39`). DB's `list_open_trades` should agree, factoring partial exits. Add `Equities` to `_SECTION_LABELS` + an extractor + a new report category `position_mismatches: list[(ticker, db_qty, tos_qty)]`. Catches "TOS shows 5 shares CC; DB shows 0 shares CC" (or vice versa) — most likely cause is an unrecorded partial exit OR a missed entry. ~1-2 hr including parser + tests. **Test:** seed open trade with 5 shares + 0 exits; pass TOS CSV showing only 3 shares for that ticker; assert mismatch surfaces.

### Bundle dispatch shape (when scoped):

Single brainstorm-skip writing-plans dispatch covering all three gaps; one schema-free implementation across `swing/journal/tos_import.py` + `tests/journal/test_tos_import.py`. Real-world fixture base: operator's 4/30 Schwab/TOS export at `thinkorswim/2026-04-30-AccountStatement.csv` exercises stops + Equities; pair with synthetic permutations for edge cases (qty mismatch, price mismatch, missing stop, ticker-not-in-DB). Per-gap tasks roughly: Task 1 close-fill price-mismatch (cheapest symmetric fix); Task 2 Order-History parser + stop reconciliation; Task 3 Equities-section parser + position-qty reconciliation; Task 4 CLI report integration (display the new mismatch categories). Done criteria includes operator-witnessed dry-run against the 4/30 CSV showing all three new categories surface zero mismatches (production DB is correctly reconciled today; the new checks should confirm the existing matched state, not flag false positives).

### Cross-references:
- `swing/journal/tos_import.py:reconcile_tos` (current verification surface).
- `swing/journal/tos_import.py:_SECTION_LABELS` (parsed sections; extend for Equities + others).
- 2026-04-30 TRD-as-withdrawal fix (`c9159c7`) — same module; same operator-surfaced via 4/30 export.
- `tests/fixtures/tos/synthetic-tos.csv` — current synthetic fixture only covers entry+exit fills + DEP/WD cash flow. Bundle dispatch should extend it.
- 2026-05-04 Schwab API integration entry below — Phase A subsumes this bundle (API surfaces close-price + stop + position-qty natively).

## 2026-05-01 Journal v1.2 incorporation (Phases 6-9)

> **Phase 6 SHIPPED 2026-05-04 at `51c79ed`** + **Phase 7 SHIPPED 2026-05-05 at `c617777`** — full per-phase detail in archive. This active entry retains cross-cutting framing + Phase 8/9 (gated on Phase 7) + sequencing alternatives + modification rationale.

Sourced from operator-commissioned research at `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` (and the v1.0 → v1.1 → v1.2 evolution chain at `reference/Future Work/Trading Journal/swing_trading_journal_*.md`). v1.2 is a discretionary-trader's journal spec; OUR platform is a framework-research-loop. The phases below adopt v1.2's discipline scaffold WHERE it adds value over our existing infrastructure, modify it WHERE its assumptions conflict with our framework-driven flow, and DROP elements we don't need (pyramiding, Setup_Playbook as DB rows, Screen_Definitions versioning).

**Umbrella sequencing decision (operator 2026-05-01):** Decompose into four phases by value × independence; ship Phase 6 first as the cheapest highest-value piece, re-evaluate before committing to Phase 7's larger schema disruption. Phase 6 + Phase 7 SHIPPED; Phase 8 + 9 unblocked, operator-paced.

### Cross-cutting framing (applies to all four phases):

- **v1.2 assumes self-rated quality scoring.** Drop self-rated components that the pipeline asserts (valid setup, regime supportive, sector supportive). Keep operator-only fields (emotional_state, confidence_score, manual override-of-doctrine).
- **v1.2 assumes operator-composed thesis.** Adapt to "thesis = pipeline bucket + criteria tags + hypothesis_label" + operator-added context (why_now, invalidation_condition).
- **v1.2's `trade_origin` enum** maps onto our actual ingestion paths: `pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline` (4-value, NOT v1.2's 7-value discretionary enum).
- **Setup_Playbook as DB entity:** DROP. Our setups are encoded in `swing/evaluation/scoring.py` + `criteria.py`; v1.2's setup_id maps to our `hypothesis_id` + doctrine layer.
- **Screen_Definitions versioning:** DROP. `finviz_schema.py` is git-versioned; explicit screen-version entity adds friction without value.
- **Pyramiding R-views (R_initial / R_effective / R_campaign):** DROP. Operator at $7,500 capital, 5 concurrent, no pyramiding plan.
- **Drawdown circuit breaker:** v1.2 defaults this opt-in disabled; align (do not enable by default).

### Phase 8 — Daily_Management + MFE/MAE precision — **SHIPPED to main 2026-05-07 at `ddfdfcb`**

> **Brainstorm outcome:** Dispatched 2026-05-06; brief at `docs/phase8-daily-management-brainstorm-brief.md` (`e9ce5a3`). Spec at `docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md` (875 lines; commits `c2507d3..c954eef`; 5 substantive Codex rounds + R5 confirmation → `NO_NEW_CRITICAL_MAJOR`; convergent chain per Phase 7 Sub-B lesson — each round caught fix-introduced regressions, not adversarial thrash). Three highest-leverage locked decisions: (1) **single table** `daily_management_records` with `record_type` discriminator + validator-level operation-contextual requiredness; (2) **tier-upgrade additive with audit trail** via `is_superseded` flag + `superseded_by_record_id` FK; (3) **authoritative-source precedence ladder** anchoring `trades.current_stop` as LIVE truth. Capture cadence: new pipeline step `_step_daily_management` after `_step_evaluate`; UPSERT key `(trade_id, data_asof_session, mfe_mae_precision_level)` via SELECT-then-UPDATE-or-INSERT (NOT SQLite REPLACE per R4 fix); GAP-FLAGGED no auto back-fill. `trail_MA_candidate_price` = 21-day SMA at session close with per-row `trail_MA_period_days` stamp; `planned_target_R` lives on trades table (pre-trade-locked discipline). Phase 8 spec §11 surfaces 4 capture-needs feedback for Phase 9 brainstorm.

> **Writing-plans outcome:** Dispatched 2026-05-07; brief at `docs/phase8-daily-management-writing-plans-brief.md` (`206b900`). Plan at `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md` (4140 lines; commit `17b1845`; 8 substantive Codex rounds + R9 confirmation → `NO_NEW_CRITICAL_MAJOR`; new high-water mark for round count in this project; tapered finding count 5→5→3→5→2→1→2→1→0; convergent chain per Phase 7 Sub-B + Phase 8/9 brainstorm lesson family — most R3+ findings were fix-introduced regressions or detail-cascade follow-ups). 15 active tasks; test count projection +55 to +100 fast tests (planner-projected subtotal +79; range biased high per Phase 6 lesson); estimated executing-plans dispatch effort ~13-15 hours. Three highest-leverage plan decisions: (1) **§A.1 service-call-inside-transaction empirical resolution** — Phase 8's `record_event_log` calls REPO-level `swing/data/repos/trades.py:update_stop_with_event` (NOT service-level `swing/trades/stop_adjust.py:update_stop_with_event` at line 105 which opens its own `with conn:` block); `linked_trade_event_id` resolved via TRADE-SCOPED max-id-after-insert pattern (NOT `last_insert_rowid()` which can return zero/stale on no-op early-return); defense-in-depth validator boundary rejects no-op stops + stale prior_stop re-read; (2) **§A.0 migration rename 0015→0016** because 0015 was already shipped as Finviz V1 — orchestrator-brief miss caught as Critical R1 by implementer; new `_phase8_backup_gate` function wired at `current_version == 15 AND target_version >= 16`; pre-Phase-8 expected table set redefined as `(PHASE7_EXPECTED_TABLES - {"exits"}) | {"fills", "finviz_api_calls"}` per empirical v15 schema; (3) **§A.2 V1-defer CLI** (web-only) per Phase 6 review surface precedent; V2 follow-up queued separately. CLI scope decision locked V1-defer. T7.0 operator-witnessed verification gate is BINDING per Phase 5/6 lesson family. Executing-plans dispatch queued (worktree-isolated; subagent-driven-development; marker-file workflow; targets schema_version 16; expected fast-suite range 1996-2041 tests). Per retention discipline, this entry stays in active until next phase ship.

### Original queued entry (2026-05-04; pre-design-lock; superseded by SHIPPED brainstorm above)

**Bundle:** Daily_Management snapshot/event_log + per-day MFE/MAE computation via OHLCV cache + precision-flag hierarchy.

**Scope:**
- New `daily_management_records` table: `management_record_id, trade_id, record_type (daily_snapshot/event_log), review_date, current_price, current_stop, open_R_effective, portfolio_heat_contribution_dollars, MFE_to_date_R, MAE_to_date_R, thesis_status` + event_log additional fields (prior_stop, stop_changed, stop_change_reason, action_taken, emotional_state, rule_violation_suspected).
- MFE/MAE precision per v1.2 §8.6: `intraday_exact / intraday_estimated / daily_approximate`. We have OHLCV cache → daily_approximate ships immediately; intraday_estimated when intraday data sourced.
- Web dashboard tile: per-open-trade MFE/MAE-to-date.

**Estimated dispatches:** 2-3.

**Cross-references:**
- `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` §7.7 (Daily_Management), §8.6 (MFE/MAE), §10.3 (In-Trade Review workflow).
- Existing OHLCV cache: `swing/data/ohlcv_archive.py` (Phase 3 OHLCV consolidation; 696 tickers consolidated 2026-04-30).
- Existing advisory infrastructure: `swing/trades/advisory.py` (Phase 3d SMA-aware advisories) — extends naturally.

### Phase 9 — Risk_Policy entity + reconciliation depth — **brainstorm SHIPPED 2026-05-06 at `31ee51c`**

> **Outcome:** Brainstorm dispatched 2026-05-06; brief at `docs/phase9-risk-policy-reconciliation-brainstorm-brief.md` (`d89b74b`). Spec at `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; commits `bc6da37..31ee51c`; 4 substantive Codex rounds + R5 confirmation → `NO_NEW_CRITICAL_MAJOR`; convergent chain — every R2/R3/R4 finding was an R-N-1-fix-introduced regression). Three highest-leverage locked decisions: (1) **per-policy-snapshot risk_policy versioning** with `is_active` + `superseded_by_policy_id` dual-column pattern (per Phase 8 `is_superseded` lesson application); (2) **Phase 7 state machine UNTOUCHED** — reopen review surface via query-side JOIN against `reconciliation_discrepancies.material_to_review = 1 AND resolution = 'unresolved'`, NOT a schema flag (R1 Major #4 catch — review_log is cadence-period-grain not trade-grain); (3) **`risk_policy` canonical post-Phase-9 source-of-truth** — `swing.config.toml` becomes startup-mirror with divergence banner + explicit `swing config policy import-from-toml` ratification (preserves audit-trail integrity). 5 new tables: `risk_policy`, `reconciliation_runs`, `reconciliation_discrepancies`, `hypothesis_status_history`, `account_equity_snapshots`. Phase 6 review_log gets ONE column add (`risk_policy_id_at_review_completion`). 10 discrepancy_type enum values (close_price_mismatch / stop_mismatch / position_qty_mismatch / cash_movement_mismatch / sector_tamper / snapshot_mismatch / unmatched_open_fill / unmatched_close_fill / entry_price_mismatch / equity_delta); `material_to_review` is CLASSIFICATION (not workflow trigger). TOS reconciliation depth bundle SUBSUMED — 3 queued gaps + new Gap 4 (cash_movement) mapped to discrepancy_type with locked JSON shapes. Sector/industry tamper hardening: BOTH schema-side (reserved enum value) + route-layer (writing-plans territory). Schwab API Phase A coordination: `source` enum reserves `schwab_api`; no Schwab-specific columns in V1; boundary contract specified for V2. 6 open questions surfaced with implementer recommendations; orchestrator concur on all 6. Spec §11 enumerates capture-needs feedback for Phase 10 writing-plans (LIVE policy reads vs at-trade-time policy reads; account_equity_snapshots resolution ladder schwab_api > tos_csv > manual > PROVISIONAL fallback). Writing-plans dispatch queued (Phase 8 writing-plans first per execution order 8 → 9 → 10). Per retention discipline, this entry stays in active until next phase ship.

### Original queued entry (2026-05-04; pre-design-lock; superseded by SHIPPED brainstorm above)

**Bundle:** Lift `swing.config` risk fields to versioned DB Risk_Policy entity + integrate the queued TOS-reconciliation-depth bundle (close-fill price mismatch + stop-order reconciliation + position-qty reconciliation) into a structured Reconciliation_Run / Reconciliation_Discrepancy framework.

**Scope:**
- New `risk_policy` table: `policy_id, effective_from, effective_to, is_active, max_account_risk_per_trade_pct, max_concurrent_positions, max_portfolio_heat_pct, max_sector_concentration_positions, consecutive_losses_pause_threshold, drawdown_circuit_breaker_enabled` (default false). Existing `swing.config.toml` values become the seed of policy_id=1.
- New `reconciliation_runs` + `reconciliation_discrepancies` tables. Existing `tos_import` reconcile flow refactors to write Reconciliation_Run rows + Discrepancy rows for each mismatch (close-price, stop, position-qty, cash). Material-to-review semantics: discrepancies on reviewed trades reopen the review.
- Subsumes the standalone "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" entry above — when Phase 9 ships, the queued bundle's three gaps (close-price + stop + position-qty) ship as part of Phase 9, not as a separate dispatch.

**Estimated dispatches:** 3-4.

**Cross-references:**
- `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md` §7.8 (Risk_Policy), §7.9 (Reconciliation_Log), §10.5 (Reconciliation Workflow).
- This document's "2026-04-30 TOS reconciliation depth follow-ups (BUNDLED)" entry above.
- Existing config: `swing/config.py` + `swing.config.toml`.
- Existing TOS import: `swing/journal/tos_import.py`.

### Sequencing alternatives (for future re-evaluation):

- **(A) Phase 6 only, defer 7-9 indefinitely.** Operator stops journal extension at the cheapest piece. Acceptable if Phase 6 turns out sufficient.
- **(B) Phase 6 + 9, defer 7 + 8.** "Journal Lite" — post-trade review + risk policy + reconciliation depth. Skips state-machine + Daily_Management.
- **(C) Full sequence 6 → 7 → 8 → 9.** Multi-month commitment to full v1.2 equivalence.
- **(D) Defer all of v1.2 until first hypothesis closure.** Per orchestrator-context lesson: "the actually-urgent next move is operational — take hypothesis-tagged trades, accumulate evidence." If journal-discipline-measurement isn't bottlenecking the loop today, defer engagement until a hypothesis closes and "did the framework work?" requires deeper retrospective tooling.

**Outcome (2026-05-05):** Phase 6 + Phase 7 shipped along path (C). Phase 8/9 sequencing decision pending evaluation soak of Phase 7 production behavior.

### Modification rationale (why we don't adopt v1.2 verbatim):

v1.2 was authored agnostic of our platform. Several design choices encode discretionary-trader assumptions that don't fit our framework-research-loop:

| v1.2 assumption | Why it doesn't fit | Our adaptation |
|---|---|---|
| Trader independently composes thesis per trade | Our framework asserts thesis via bucket + criteria + hypothesis_label | Keep thesis as text field but auto-pre-fill from candidate row + hypothesis matcher; operator adds context |
| Self-rated `pre_trade_quality_score` 0-10 | Pipeline already computes A+/watch/skip + criteria pass/fail; self-rating duplicates and conflicts | Drop self-rated framework components; keep emotional_state, confidence_score, manual override |
| Setup_Playbook as DB rows with status active/pilot/paused/retired | Our setups are encoded in `swing/evaluation/`; trader doesn't manage setups as data | DROP; reference hypothesis_id when setup-attribution needed |
| Pyramiding R_views | Operator at $7,500 capital with 5 concurrent doesn't pyramid | DROP indefinitely |
| `trade_origin` 7-value discretionary enum | Our ingestion is pipeline-driven (4 paths) | 4-value pipeline-aware enum: `pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline` |
| Drawdown circuit breaker | v1.2 default opt-in disabled (matches our caution) | Align: opt-in disabled by default |

---

## 2026-05-06 Phase 10 metrics dashboard — **brainstorm SHIPPED 2026-05-06 at `fe6cb45`**

> **Outcome:** Operator-commissioned external research at `reference/Future Work/Metrics/` (5 docs: v1.0 baseline + v1.1 + v1.1-alternate + findings + rebuttal-determinations) — orchestrator-thread analysis confirmed v1.1-alternate as structural baseline + identified framework-fit gaps requiring NEW design (hypothesis-cohort as primary axis; tier-comparison; capital-friction; maturity-stage; identification-vs-trade-funnel; deviation-outcome; process-grade-trend). Brainstorm-dispatched 2026-05-06; brief at `docs/phase10-metrics-brainstorm-brief.md` (`3ad5ea2`). Spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` (641 lines; commits `a46b458` + `fe6cb45`; 5 substantive Codex rounds + R6 confirmation → `NO_NEW_CRITICAL_MAJOR`). Three highest-leverage locked decisions: (1) **capital-denominator split-policy** — governance metrics lock to constant `$7,500`; operational/live-state metrics PROVISIONAL with `$7,500` fallback until §8.2 resolves; (2) **global statistical-confidence floor** `n=20` decoupled from cohort target; (3) **tier-comparison view** explicitly avoids false-significance signals (text-only `cohort_ci_overlap_descriptor`; no boolean flag). Mistake-cost formula DECISION: brainstorm AFFIRMS Phase 6's already-shipped v1.1-alternate / v1.2 §8.8 formula (the brief's §1.5 premise that Phase 6 ships v1.1-main was empirically wrong; Phase 6 already ships the correct formula at `swing/trades/review.py:157-174`). Spec §11 enumerates capture-needs feedback for Phase 8 (consumed) + Phase 9 + Phase 10+. **Sequencing locked: brainstorms 10 → 8 → 9; execution order 8 → 9 → 10.** RESEARCH-posture (no schema/code; only metric definitions + dashboard sketches + capture-needs feedback). Per retention discipline, this entry stays in active until next phase ship.

### Open follow-ups from Phase 10 brainstorm (operator-paced)

- **§8.6 — Surface `lucky_violation_R` on Phase 6 review form.** Phase 6 already computes + persists `total_lucky_violation_R` (per migration 0013); review form does NOT surface the per-trade or cohort field. Operator concurred with implementer's recommendation: small standalone follow-up dispatch (~30 min), separate from Phase 10 writing-plans. Not bundled with Phase 10 because it's Phase-6-surface-extension, not metrics-dashboard scope. Pick up when bandwidth allows.
- Other open questions (§8.1 fills.action enum gap; §8.2 daily equity capture; §8.3 benchmark series location; §8.4 Corporate_Actions MVP; §8.5 process_grade_rolling_N window; §8.7 decision-criteria automation) — operator concurred with implementer's recommendations across all 7. Bundled with Phase 10+ writing-plans + execution unless re-litigated.

### Open follow-ups from Phase 8 writing-plans dispatch (operator-paced)

- **V2 CLI `swing trade event-log` follow-up.** Phase 8 plan §A.2 deferred CLI per Phase 6 review surface web-only-V1 precedent. Schema + service are CLI-agnostic; landing wire-up estimated ~1-2 hours. Pick up when convenient post-Phase-8-ship; dispatch shape: small standalone CLI dispatch (mirror Phase 6 review CLI pattern at `swing/cli.py` review-command region; reuse Phase 8's `record_event_log` service helper).

### Phase 8 V1 follow-ups (operator-witnessed gate observations 2026-05-07)

> **Status: BOTH SHIPPED to main 2026-05-08 at integration merge `24b3e9a`** (worktree branch `worktree-phase8-v1-polish` → main; 16 commits = 12 task-impl + 4 adversarial-fix). Plan: `docs/superpowers/plans/2026-05-07-phase8-v1-polish.md`. Test count delta: 2079 → 2090 (+11 fast tests). Ruff baseline 78 preserved. Schema unchanged at v16. Writing-plans 2 Codex rounds + executing-plans 3 Codex rounds → both NO_NEW_CRITICAL_MAJOR; convergent shape (executing-plans tapered 3→1→0 majors; sort-key tiebreak hardened in `7c08f12` from R1 finding). 4-surface operator-witnessed gate PASS via Chrome MCP walkthrough 2026-05-08 (Surface 1 Detail button on every open-position row; Surface 2 timeline union surfaces orphan stop-adjusts on DHC chronologically; Surface 3 dedup via `linked_trade_event_id` correctly suppresses Phase-8-form-written trade_events; Surface 4 regression-spot-check across all 7 routes). Three V2 advisory items captured at the §"Phase 8 V2 advisory items" subsection below. Per retention discipline this entry stays in active until next phase ship.

- **Phase 7 stop-adjust legacy path doesn't surface in Phase 8 timeline (Surface 6 finding).** ~~When operator uses the dashboard's "Adjust stop" button (Phase 7 route at `/trades/<id>/stop`), the resulting `trade_events` row IS audit-trailed but does NOT appear in Phase 8's per-trade `daily-management-timeline` view~~ — **SHIPPED.** Took path (a): VM-level read-side union. `build_daily_management_timeline_vm` now unions Phase 7 orphan `trade_events` of `event_type='stop_adjust'` (those NOT linked via `daily_management_records.linked_trade_event_id`) into the timeline, rendered as `record_type='trade_event_legacy'` with badge "Stop adjustment (legacy quick-adjust)".
- **No dashboard → bare detail page navigation link.** ~~Operator can navigate to `/trades/<id>` only via direct URL~~ — **SHIPPED.** `partials/open_positions_row.html.j2` now emits `<a href="/trades/{id}" class="row-action-link" onclick="event.stopPropagation()">Detail</a>` after the existing Exit + Adjust stop buttons.
- **emotional_state form preserves stale checkbox state across browser visit cycles.** When operator visually toggles checkboxes during inspection (without submitting), those checkmarks persist in browser form state through subsequent navigations away + back to the detail page. Cosmetic; potentially confusing for next-time submission. **Fix:** form re-render on detail-page GET should explicitly clear any preserved checkbox state (re-initialize `vm.emotional_state_set` to `()`). May require deeper investigation of where the persistence comes from (server-side render OR browser autofill). Defer until operator confirms confusion; not a correctness issue.
- **Spec wording vs implementation: "GAP-FLAGGED" → "gap-by-absence".** Phase 8 spec §2.2 + Surface 5 brief-language said gap-handling would "flag missed-day in §7.2 timeline as `(no snapshot — pipeline did not run)`"; actual implementation is gap-by-absence (no row written for missed days; operator infers gap from row-date discontinuity in timeline). Functionally equivalent (operator sees the gap visually) but spec-vs-impl wording mismatch. **Fix:** Phase 8 V2 adds explicit placeholder rows in timeline for missed days OR spec amended to match gap-by-absence. Defer until operator naturally encounters a gap workflow + confirms whether explicit placeholders would be useful. Cosmetic.
- ~~**Worktree husk `.worktrees/phase8-daily-management/` ACL-locked at integration merge.**~~ **RESOLVED 2026-05-07** (operator-elevated cleanup performed). Same Windows ACL pattern as Phase 6/7 cleanup leftovers; cleared via existing `cleanup-locked-scratch-dirs.ps1` extension landed at `5430c1c`.

### Phase 8 V2 advisory items (surfaced 2026-05-07 writing-plans + executing-plans phase8-v1-polish)

Three non-blocking advisories surfaced during phase8-v1-polish dispatches (2026-05-07; plan at `docs/superpowers/plans/2026-05-07-phase8-v1-polish.md`). All noted as out-of-scope for V1 polish; surfaced here so they don't decay.

- **Audit-chain symmetry: legacy `/trades/{id}/stop` route also writes Phase 8 event_log row.** V1 polish surfaces legacy stop-adjusts via read-side VM union; does NOT write Phase 8 audit rows for them. If operator eventually wants the timeline uniformly Phase-8-shaped (every stop-change has both a `trade_events` row AND an `event_log` row with `linked_trade_event_id`), the legacy route should be refactored to call `record_event_log` atomically instead of writing only `trade_events` directly. ~3-4 hr standalone dispatch (route + tests + audit-chain alignment). Defer until operator surfaces a workflow gap that this would close.
- **Template `data-trade-event-id` attribute for orphan rows.** Plan §A.2 sort-tiebreak uses `-trade_events.id` for orphan rows; the template currently exposes `data-timeline-record-id="-{event.id}"` (negative-int-from-positive-PK). If a future feature deep-links to a specific orphan row (e.g., notification → "your stop-adjust on AAPL was logged as legacy"), parsing the negative ID is awkward. A dedicated `data-trade-event-id` attribute on `trade_event_legacy` rows would be cleaner. ~15 min cosmetic; defer until first deep-link consumer surfaces.
- **Read-side snapshot consistency for `build_daily_management_timeline_vm` (R2 acceptance, 2026-05-07).** Surfaced by adversarial-critic R1 Major 2 + clarified by R2 Major 1. The VM build issues two sequential SELECTs (`list_for_trade_timeline` then `list_events_for_trade`) without a wrapping read transaction. Python's default `sqlite3` isolation does NOT escalate SELECT-only flows to a snapshot read; `with conn:` only manages commit/rollback on exit. If a `record_event_log` COMMIT lands BETWEEN the two reads, the timeline VM can compute `linked_event_ids` from a pre-commit `records` view while seeing the post-commit `trade_events` row in `events` — producing a false "(legacy quick-adjust)" row that omits the canonical Phase 8 `event_log` row for the same change. Impact framing (R2-corrected): NOT a microsecond UI flash; the rendered HTML page persists with the wrong content until the operator refreshes or navigates. Underlying tables stay correct (no data corruption). Probability: very low on a single-operator desktop app (Windows, journal_mode=delete, single FastAPI worker process; the operator must submit the Phase 8 form AND view the same trade's detail page via separate concurrent requests AT exactly the moment the read interleaves with the commit). Fix options: (a) collapse the union into a single SQL query JOIN (clean V2 refactor); (b) manually `BEGIN DEFERRED + COMMIT` around both reads (requires `conn.isolation_level=None` manipulation that ripples through the function's call chain). Both options exceed V1-polish dispatch scope; banked here for V2.

---

## 2026-05-04 Finviz Elite API integration — **SHIPPED 2026-05-06 at `002338a`** (V1)

> **Outcome:** Brainstorm-skipped per operator + orchestrator in-thread design lock 2026-05-05 (Q1-Q8 from the original queued entry below answered + locked + Q-bonus on file-collision policy). Writing-plans dispatch shipped plan `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` (5 Codex rounds → NO_NEW_CRITICAL_MAJOR; HEAD `734ba6f`). Executing-plans dispatch on worktree branch `finviz-api-integration` (BASELINE_SHA `734ba6f`); 17 task-anchored commits + 5 Codex-fix commits; 5 Codex rounds → NO_NEW_CRITICAL_MAJOR. Operator-witnessed verification gate 2026-05-06: 1 mid-verification fix (`code-review I1` at `0e02ed6` — `swing/data/repos/finviz_api_calls.py:insert_call` removed internal `conn.commit()` that was breaking `lease.fenced_write()` contract on the pipeline path; CLI raw-conn path now commits explicitly); all 8 surfaces PASS post-fix. Integration merge `002338a`. Test count delta: +63 fast (1877 → 1940) + 2 slow live tests; ruff baseline 78 preserved. Production DB at schema_version 15 with new `finviz_api_calls` audit table. New `swing/integrations/` namespace established as pattern for future Schwab API integration. New CLI: `swing finviz fetch` + `swing finviz status`. Drift-detection signature-hash + WARNING emission verified via DB-tamper test (Finviz API URL params fully define the screen — no saved-screen-handle to edit on UI side per writing-plans research finding). Two new lessons captured in `docs/orchestrator-context.md` §"Lessons captured": subprocess cfg-propagation (Codex R2 finding; child-process CLI body is binding override point) + repo-functions-must-not-commit (operator-witnessed I1 finding). Per retention discipline, this entry stays in active until next phase ship; original queued content retained below for historical reference.

### Original queued entry (2026-05-04; pre-design-lock; superseded by SHIPPED V1 above)


Operator-surfaced 2026-05-04. Replace the manual-CSV-export-to-`data/finviz-inbox/` ingestion workflow with programmatic Finviz Elite API access (https://elite.finviz.com/api_explanation). Concurrent goal: improved structured logging of all ingestion calls (request params, response sizes, screen versions, rate-limit consumption, failure modes) — current pipeline logging is per-step but not data-source-instrumented.

### Current state (orchestrator survey 2026-05-04):

- **Manual ingestion:** operator exports a Finviz screen as CSV with 13 specific columns (`No., Ticker, Sector, Industry, Country, Price, Change, Average Volume, Relative Volume, Average True Range, 52-Week High, 52-Week Low, Market Cap`); names file `finvizDDMmmYYYY.csv`; drops in `data/finviz-inbox/`.
- **Validator:** `swing/pipeline/finviz_schema.py:12` checks 13-column schema; missing columns → reject to `data/finviz-inbox/rejected/` with sidecar JSON.
- **Pipeline consumption:** `_step_evaluate` reads the CSV, ingests rows as candidates, drops Sector/Industry until Phase 4 wired them.
- **Cadence:** daily (operator's actual workflow per `docs/cycle-checklist.md`).
- **Failure modes today:** wrong column count (rejected); wrong filename pattern (silently skipped); operator forgot to export (pipeline runs against stale or empty inbox).

### V1 scope (sketch — pre-brainstorm):

1. **`swing/integrations/finviz_api.py`** — auth (API token from a new `cfg.integrations.finviz.token` field; persist in user-config TOML per Phase 5 infrastructure, NOT tracked toml). Wraps the Finviz Elite REST endpoint with the operator's saved-screen-id parameter.
2. **Pipeline ingestion path** — new `_step_finviz_fetch` runs BEFORE `_step_evaluate`; pulls latest screen results; emits to the same 13-column CSV format in `data/finviz-inbox/` (preserves the existing validator + rejected-fallback pattern). Manual CSV drop remains supported as fallback if API unavailable.
3. **Structured logging** — per-call: timestamp, screen_id, row count, response time, rate-limit consumed, rate-limit remaining; persisted to a new `finviz_api_calls` table (or appended to `pipeline_runs.notes`); surfaced on dashboard pipeline-status surface.
4. **CLI parity** — `swing finviz fetch` command for ad-hoc invocation outside the pipeline; `swing finviz status` for rate-limit + recent-call inspection.
5. **Config surface** — add `[integrations.finviz]` section with token + screen_id + (optional) timeout/retry params; surface in Phase 5 config page in V2 if operator wants edit access.

### Open design questions (for brainstorm dispatch):

1. **Cost confirmation.** Finviz Elite is a paid subscription (~$40/mo). Confirm operator is on Elite OR plans to subscribe before any work commits. If not, this entry stays QUEUED indefinitely.
2. **Screen-id management.** The screen is currently a saved Finviz user-screen (operator-created). API likely requires a screen_id reference. Persist as cfg field; surface in config page as V2.
3. **Rate-limit handling.** Finviz Elite API documents rate limits (TBD: needs operator-confirmed quota). Pipeline cadence is daily so likely fine; ad-hoc CLI invocations need backoff.
4. **Schema-parity verification.** Verify Finviz API response fields map 1:1 to the 13-column CSV schema. If API returns different column set, the integration layer normalizes before emitting to the canonical schema (same validator runs).
5. **Failure fallback.** If API returns error / rate-limit-exceeded / network failure, pipeline should LOG and skip — not fail the entire run. Operator can drop a manual CSV as backup.
6. **Token storage.** API token is sensitive; persist in user-config TOML (per Phase 5 infrastructure, outside Drive) NOT in tracked `swing.config.toml`. Revisit if Phase 9 introduces a secrets-management layer.
7. **Sector/industry consistency.** Phase 4 wired Sector/Industry from the CSV; API-emitted CSV must preserve same field names + values to avoid breaking the existing pipeline ingestion.
8. **Screen-version drift.** The operator's saved screen on Finviz can be edited; API call would silently start returning different rows. Capture screen-id + (if available) screen-version-hash on each fetch; surface drift detection on dashboard.

### V1-deferred / V2:

- **Multi-screen support** (operator currently runs one screen; future: A+ screen + watchlist screen + research screen).
- **Backfill mode** — pull historical screen results for evidence-loop research (depends on Finviz Elite API supporting historical-screen endpoints; unverified).
- **Real-time price feed** (Finviz Elite has a price stream; out-of-V1; redundant with potential Schwab API integration below).

### Cross-references:

- `swing/pipeline/finviz_schema.py:12` (validator — preserve schema contract).
- `data/finviz-inbox/` (canonical drop directory; preserve as fallback).
- `swing.config.toml` + Phase 5 user-config infrastructure (`cfg.integrations.finviz` section).
- `docs/cycle-checklist.md` (daily operator workflow — fetch step replaces manual export).
- 2026-05-04 Schwab API integration entry below (may share `swing/integrations/` namespace + secrets-management approach).

---

## 2026-05-04 Schwab API integration (QUEUED; Large effort; multi-phase; brainstorm needed)

Operator-surfaced 2026-05-04. Three concurrent uses of the official Charles Schwab Trader API (https://developer.schwab.com/): (1) automate account reconciliation (replace TOS-CSV-import workflow + subsume the queued 2026-04-30 TOS reconciliation depth bundle); (2) potentially automate trade entry/exit/stop-management; (3) provide an alternative data source to yfinance (real-time prices + intraday OHLCV + fundamentals — addresses 4+ yfinance gotchas in CLAUDE.md). This is a comparable-to-Phase-7-9-scope multi-phase commitment; not a single dispatch.

### Current state (orchestrator survey 2026-05-04):

- **Operator already on Schwab.** `thinkorswim/2026-04-30-AccountStatement.csv` is the manual TOS export; production DB has 3 trades reconciled against it.
- **TOS-CSV reconciliation:** `swing journal import-tos` reads the CSV; `reconcile_tos` verifies a SUBSET of disagreement surface (entry-fill price-mismatch only; gaps for close-price, stop-orders, position-qty per the queued 2026-04-30 TOS bundle).
- **yfinance is the SOLE production data source** — historical OHLCV (consolidated archive at `swing/data/ohlcv_archive.py` after Phase 3 OHLCV consolidation 2026-04-30); price fetcher (`swing/prices.py PriceFetcher`); `_step_charts` chart fetch. Multiple production-impacting yfinance API regressions captured in CLAUDE.md gotchas.
- **No trade automation today** — all entry / exit / stop-adjust go through manual CLI or web form; trader places orders manually in Schwab/TOS UI.

### V1 scope (sketch — pre-brainstorm; multi-phase decomposition):

**Candidate library:** [Schwabdev](https://github.com/tylerebowers/Schwabdev) — unofficial Python wrapper for the Schwab Trader API; covers OAuth 3-legged flow + account/positions/orders/quotes/streamer endpoints. Evaluate at brainstorm time vs build-from-scratch (see design question 1 below).

**Phase A — OAuth + read-only account access (cheapest first):**
1. **Schwab Developer Portal app registration** (operator action; production-access approval can take days).
2. **`swing/integrations/schwab/auth.py`** — OAuth 3-legged flow; refresh-token persistence in user-config TOML (parallel to Phase 5 infrastructure). If Schwabdev adopted, this layer is a thin wrapper around Schwabdev's auth handling rather than rolling our own.
3. **`swing/integrations/schwab/account.py`** — read-only: positions, balances, transactions. Maps to current `tos_import` data shape.
4. **`swing journal reconcile-schwab`** CLI — replaces `swing journal import-tos` for the API-available account-state surfaces. CSV import path remains supported as fallback.
5. **Subsumes the 2026-04-30 TOS reconciliation depth bundle** (close-price + stop + position-qty mismatch detection) — API surfaces these natively; no CSV-parsing edge cases.

**Phase B — Alternative data source (highest-value second):**
6. **`swing/integrations/schwab/market_data.py`** — quote, OHLCV (daily + intraday), fundamentals. Wrap with same interface as `swing/prices.py PriceFetcher` so caller code is data-source-agnostic.
7. **`cfg.data_source.primary`** = `"yfinance" | "schwab"` (default `"yfinance"` for V1; flip to `"schwab"` after parity verification). Per-call fallback if primary errors.
8. **Parity verification harness** — research-branch dispatch comparing yfinance vs Schwab on N tickers × M sessions; document divergence (price + dividend-adjustment + corporate-action handling).
9. **Replaces multiple yfinance gotchas** — `Ticker.history` `threads=` regression; `group_by='column'` MultiIndex; `interval=1d` partial-bar inclusion; rate-limit pressure.

**Phase C — Trade automation (highest-risk last; opt-in only):**
10. **`swing/integrations/schwab/orders.py`** — place stop-buy entry (per hypothesis-tagged trade discipline); place initial stop; modify stop on advisory-trail trigger.
11. **`cfg.trade_automation.enabled`** = `false` default; explicit operator opt-in per trade.
12. **Dry-run mode** — emit the order JSON without submitting; operator reviews + confirms manually OR commits to live submission.
13. **Audit log** — every API call logged with request + response + timestamp; persisted to a new `schwab_orders` table joined to `trades` for full audit trail.
14. **Bilateral verification** — every automated order followed by a Schwab API position-state read to confirm the order landed; mismatch → halt automation + alert operator.

### Open design questions (for brainstorm dispatch):

1. **Library choice: three candidates surfaced 2026-05-06.** Evaluate at brainstorm time:
   - **Schwabdev** (https://github.com/tylerebowers/Schwabdev) — wraps entire Schwab Trader API surface (auth/account/orders/market data/streamer); single-author; newer trajectory.
   - **schwab-py** (https://github.com/alexgolec/schwab-py) — by alexgolec who previously authored `tda-api` for the TD Ameritrade API; multi-year community-usage lineage; broker-API client design experience.
   - **Build-from-scratch** — direct Schwab Trader API integration in `swing/integrations/schwab/`; max control + max maintenance burden.
   Operator leaning toward schwabdev (2026-05-06) but explicitly evaluating at brainstorm time. Risks: unofficial wrappers can break on Schwab API changes; maintainer-bus-factor; supply-chain trust. For any wrapper choice, recommend vendored / version-pinned dependency + thin abstraction layer (`swing/integrations/schwab/client.py`) so swap-to-direct-API is bounded if the wrapper goes stale.
2. **Phase A vs Phase B vs Phase C ordering — operator preference.** Recommendation: A (account reconciliation) → B (data source) → C (trade automation). A is cheapest; B has highest yfinance-pain-relief value; C is highest-risk + lowest urgency at $7,500 capital with 1-2 trades/month pace.
3. **OAuth refresh-token storage location.** User-config TOML (per Phase 5)? New encrypted store? Operator's risk preference.
4. ~~**Schwab Developer Portal production-access approval time.**~~ **RESOLVED 2026-05-06.** Operator confirms Dev Portal app registration + production-access approval are both COMPLETE. The long-pole approval friction is gone — when Phase A is sequenced, brainstorm + writing-plans + executing-plans can dispatch immediately without external approval gating.
5. **Schwab API entitlements scope.** Read-only account vs trading entitlements require separate Schwab approvals; operator decides per-phase.
6. **yfinance vs Schwab data parity.** Adjusted vs unadjusted prices; corporate-action handling; dividend treatment; intraday-bar timestamping. Need a parity study before flipping `cfg.data_source.primary`.
7. **Trade automation safety gates.** Hard maximums (per-trade size; daily order count; circuit breaker on N consecutive failed orders); operator-defined override path.
8. **Subsumption of TOS-CSV bundle.** When Schwab API account access works, does the 2026-04-30 TOS reconciliation depth bundle get DROPPED or RETAINED as fallback for offline-mode? Recommendation: retain CSV path as fallback (defense-in-depth); but the queued depth-bundle work becomes lower priority since the API surfaces the same data natively.
9. **Sequencing vs Phase 9 (Risk_Policy + reconciliation depth).** Phase 9 from journal v1.2 covers reconciliation depth + Risk_Policy entity. Schwab API Phase A IS the reconciliation-depth implementation; logical merger is "Phase 9 ships using Schwab API as the data layer." Re-evaluate when both items ripen.
10. **Cost.** Schwab API access is free for account holders; no subscription cost like Finviz Elite. Approval friction is the primary cost.
11. **Failure fallback.** Trade-automation failure modes are operationally severe (failed entry on a hypothesis-tagged trade = lost evidence). Phase C MUST have explicit fallback-to-manual semantics + clear operator alerting.

### V1-deferred / V2:

- **Multi-account support** (operator has one trading account; future: separate research / paper-trading accounts).
- **Options trading** (out of framework scope; equity swing-trade only).
- **Schwab StreamerAPI** (real-time quotes via WebSocket; future if dashboard real-time price ticks become valuable).

### Cross-references:

- `thinkorswim/2026-04-30-AccountStatement.csv` (current manual reconciliation source; replaced by Phase A).
- `swing/journal/tos_import.py` (`reconcile_tos` + `extract_cash_movements`; CSV path retained as fallback).
- 2026-04-30 TOS reconciliation depth follow-ups bundle (subsumed by Phase A; lower priority once API works).
- 2026-05-01 Journal v1.2 incorporation Phase 9 (Risk_Policy + reconciliation depth — logical merger with Schwab API Phase A).
- `swing/prices.py PriceFetcher` (current yfinance interface; Phase B mirrors).
- `swing/data/ohlcv_archive.py` (Phase 3 consolidated archive; Phase B fetch path writes here for parity).
- CLAUDE.md gotchas (4+ yfinance regressions Phase B replaces).
- `swing.config.toml` + Phase 5 user-config infrastructure (`cfg.integrations.schwab` section).
- 2026-05-04 Finviz API integration entry above (shared `swing/integrations/` namespace + secrets-management approach).
- Schwabdev unofficial Python wrapper: https://github.com/tylerebowers/Schwabdev (candidate library; see V1 sketch + design question 1).

---

## 2026-05-05 Sector/industry tamper vector hardening (BACKLOG; SCHEDULED for Phase 9; low-stakes)

**Surfaced 2026-05-05 by Phase 7 Sub-C Codex R3 Minor 2** (accepted-deferred per operator triage 2026-05-05; **operator-decided Phase 9 inclusion**). Sub-C C.3 entry route hardened the chart_pattern_algo + classification_pipeline_run_id round-trip with route-layer enum + FK existence + cache-content match validation (Codex R1 M1 + R2 M1 fixes). The sector + industry hidden-form snapshots have NO analogous server-side cache/content validation — a forged form POST could persist arbitrary sector/industry strings.

**Why low-stakes (today):** sector + industry are descriptive metadata only; they do NOT feed gating logic, A+ identification, hypothesis attribution, or trade-decision algorithms (per spec §11.3 + observations across `swing/evaluation/`). Compromising them produces wrong dashboard labels but does not corrupt correctness-critical paths.

**Why scheduled for Phase 9:** Phase 9 Risk_Policy entity introduces sector concentration limits (`max_sector_concentration_positions` per v1.2 §7.8). Once sector becomes a gating dimension, the tamper vector becomes correctness-critical — same severity as the chart_pattern_algo concern. Bundling the hardening into Phase 9 aligns the fix with the criticality elevation.

**V1 scope (executed within Phase 9):**
1. Route-layer Finviz-snapshot existence check at trade entry POST (mirror chart_pattern pattern in `swing/web/routes/trades.py` commits `117dc97` + `2b9d6f3`).
2. Reject if `(ticker, action_session)` sector/industry snapshot doesn't match cached candidate row.
3. Same-shape route + test pattern as chart_pattern hardening.

**Estimated effort if triggered:** 1-2 hours (mechanical mirror of chart_pattern route-layer pattern).

**Cross-references:**
- Phase 7 Sub-C return report 2026-05-05 (Codex R3 Minor 2 accepted-deferred + operator decision to schedule for Phase 9).
- `swing/web/routes/trades.py` chart_pattern hardening (commits `117dc97` + `2b9d6f3`) — fix-pattern template.
- Phase 9 Risk_Policy entity (sector concentration limits = trigger).
- v1.2 §7.8 `max_sector_concentration_positions` field.

---

## 2026-05-05 Fill.quantity fractional-share forward-compat (BACKLOG; gated on fractional-share feature)

**Surfaced 2026-05-05 by Phase 7 Sub-C Codex R1 Major 3** (accepted-with-rationale per operator triage). `Fill.quantity` is REAL in schema (Sub-A migration 0014); ~7 modules currently truncate to int via `_ExitShape` adapters because all current production code paths produce integer-share fills (`compute_shares()` returns int; CLI/web/trim/exit all submit `shares: int`). Forward-compat concern: when fractional-share trading lands, the int truncation across 7 modules becomes a bug surface.

**Trigger:** future feature work introducing fractional-share trading. Most likely path: Schwab API integration Phase B (broker fills can be fractional in modern broker APIs) OR an explicit operator decision to trade fractional shares.

**V1 scope when triggered:**
1. Audit the 7 modules with `_ExitShape` int-truncation (enumerated in code comment at `swing/web/view_models/trades.py:_ExitShape` declaration per Sub-C R1 M3 ACCEPTED-with-rationale).
2. Refactor each consumer to handle REAL `quantity` correctly (display formatting; aggregation arithmetic; CLI parsing; web form input).
3. Update `compute_shares()` to optionally return float when fractional flag set.
4. Add Fractional-share-specific test coverage.

**Estimated effort if triggered:** 3-5 hours (mechanical type widening across 7 modules + format polish + tests).

**Cross-references:**
- Phase 7 Sub-C return report 2026-05-05 (Codex R1 Major 3 accepted-with-rationale).
- `swing/web/view_models/trades.py:_ExitShape` declaration — code comment enumerates the 7 affected modules.
- Schwab API integration Phase B (`docs/phase3e-todo.md` 2026-05-04 entry) — likely activation trigger.

---

## 2026-05-04 Future schema migration: trade.entry_date datetime promotion (BACKLOG)

**Surfaced 2026-05-04 by Phase 7 Sub-B Codex R5 finding** (open question 2). Phase 7 keeps `trades.entry_date` as YYYY-MM-DD date-only TEXT column. The B.1 atomic-flow refactor's `_normalize_trade_event_date_to_iso` helper accepts the date-only `entry_date` + synthesizes the `T<HH:MM:SS>` portion for the entry-fill `fill_datetime`. Many downstream consumers call `date.fromisoformat(trade.entry_date)` directly (CLI hold-duration; `swing/journal/{flags,analyze}.py`; `swing/trades/advisory.py`; `swing/pipeline/briefing.py`; `swing/cli.py`).

**Why this is in the backlog:** any future schema migration that wants to promote `trades.entry_date` to ISO datetime (e.g., for sub-second precision; for tz-aware tracking; for richer chronology in research-branch back-tests) would need to migrate every `date.fromisoformat(trade.entry_date)` consumer. Scope is bounded but cross-cutting.

**Trigger:** future phase that has a use case for sub-day entry datetime precision (likely Phase 9 if Schwab API integration ships and broker fill timestamps become canonical) OR research-branch needs (intraday entry timing studies).

**Estimated dispatches if triggered:** 1 brainstorm (operator decides whether to promote vs keep date-only) + 1 writing-plans + 1 executing-plans (consumer audit + migration + per-consumer rewrite + tests).

**Cross-references:**
- Phase 7 Sub-B return report 2026-05-04 (open question 2).
- `swing/cli.py`, `swing/journal/flags.py`, `swing/journal/analyze.py`, `swing/trades/advisory.py`, `swing/pipeline/briefing.py` — current consumers of `date.fromisoformat(trade.entry_date)`.
- Phase 7 Sub-B `_normalize_trade_event_date_to_iso` helper (commits `e6541fe..71ddb95`) — established pattern for trade-chronology canonicalization at service boundary; likely the migration's API surface.
- 2026-05-04 Schwab API integration entry (Phase B market_data integration may surface intraday-precision needs).

## 2026-05-09 Chart pattern detection v2 — research captured (RESEARCH-CAPTURED; greenfield expansion; brainstorm-needed)

**Operator-surfaced 2026-05-09**: dropped three reference documents into `reference/Future Work/Chart Pattern Detection/` (committed `6b40292`). These describe research informing potential paths forward for expanding chart-pattern detection from the shipped flag-v1 classifier to a full swing-trading setup detector.

### Reference documents

- **`stock_chart_pattern_detection_ai_ingestion.md`** (v1.0) — generic original; surveys 9 mathematical approaches across all chart-pattern families.
- **`stock_chart_pattern_detection_delta_review.md`** — section-by-section critical review re-scoping for swing trading (Minervini/CANSLIM); adds VCP as headline pattern, Development Data Strategy, Drift Detection, Small ML Model Decision Analysis with G1-G7 implementation gates.
- **`stock_chart_pattern_detection_ai_ingestion_v2.md`** (v2.0; **canonical** — supersedes v1.0 per its frontmatter) — merged swing-trading-scoped analysis brief; 8-phase roadmap; rule-based + template-matching as production primary; ML re-ranker deferred 12-18 months gated on G1-G7.

### Scope vs shipped flag-v1

**Distinct from existing chart-pattern flag-v1 follow-ups** (this file's 2026-04-26 + 2026-04-27 sections). Flag-v1 is a single-pattern (pole-and-flag) classifier with no closed-loop outcome back-linkage. The v2 docs propose a substantially broader greenfield surface:

- **Primary buy-side patterns:** VCP (highest-priority; Minervini signature), cup-with-handle, flat base, high-tight flag, double-bottom W; pole-and-flag overlaps flag-v1 turf and would need explicit reconciliation at brainstorm time.
- **Upstream context:** trend-template universe pre-filter (Stage 2 + RS rank + liquidity floor) — runs before pattern detection, dramatically reducing multiple-comparisons surface area.
- **Sell-side detector module:** H&S top, climax run, Stage 4 breakdown, MA50/MA200 violations — separate from buy-side detector.
- **Closed-loop:** trade actions + outcomes back-linked to candidates; outcome-distribution surfaces in review interface ("of the last 20 VCPs flagged with similar scores, X% triggered, Y% reached 1R, Z% hit stop"). Depends on Phase 10 metrics infrastructure.
- **Drift detection:** feature drift / pattern frequency drift / outcome drift / self-drift dashboards as first-class system component (not afterthought).
- **Development data strategy:** five sources tagged in corpus — curated exemplars / AI-assisted labeling / parametric synthetic / perturbation / organic from trade history; mixed training with stratified evaluation on real-only held-out subset.
- **Optional ML re-ranker:** deferred 12-18 months minimum, gated on G1-G7 (rule saturation; label volume ≥200/class with ≥100 outcomes; multi-regime coverage; self-drift bounded; articulable failure mode; feature stability; operational bandwidth). Recommended initial implementation: LightGBM/XGBoost over ~50-100 engineered features as Role-2 setup-quality re-ranker (NOT primary detector; NOT outcome predictor).

### Trigger and effort estimate

**Trigger:** operator decision to expand beyond flag-v1 classifier scope. Likely sequence-locked after Phase 9 (risk_policy + reconciliation) + Phase 10 (metrics dashboard) ship, since outcome-distribution surfaces in the review interface depend on the metrics infrastructure being in place.

**Effort estimate (pre-brainstorm; speculative):** comparable-to-Phase-7-or-larger multi-phase commitment. Universe pipeline (Phase 0 in v2's roadmap) is potentially valuable on its own and could be the first dispatchable slice — runs once daily, gates pattern detection, surfaces useful trend-template state independent of any pattern detector.

**Brainstorm gate:** v2 doc is research-quality — explicit + introspectable but not project-scoped. Brainstorm dispatch would translate the 8-phase roadmap into project-specific phase decomposition (likely "Phase 11+ chart-pattern detection v2" or similar) with concrete schema + CLI + web surfaces, reconciliation against shipped flag-v1 module, and integration points with shipped Phase 6 (review_log) + Phase 7 (state machine + fills) + Phase 9 (risk_policy) + Phase 10 (metrics).

### Cross-references

- `reference/Future Work/Chart Pattern Detection/stock_chart_pattern_detection_ai_ingestion_v2.md` — canonical v2 analysis brief.
- 2026-04-26 chart-pattern flag-v1 brainstorm follow-ups (above) — flag-v1-specific, narrower scope; calibration study + schema-layer hardening + hidden-form-field tampering hardening remain valid for flag-v1 itself even under v2.
- 2026-04-27 chart-pattern flag-v1 V1-ship gates — operator-paced gates for shipping flag-v1 V1 (precedes any v2 work).
- `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` — flag-v1 brainstorm spec (subsumed under v2's broader scope but flag-v1 implementation choices remain authoritative for the pole-and-flag pattern).
- 2026-05-06 Phase 10 metrics dashboard entry (above) — outcome-distribution surfaces in v2's review interface depend on Phase 10 infrastructure.
- 2026-05-04 Schwab API integration entry (above) — v2's "delisted-stock data is essential" requirement may surface in Schwab Phase B market-data integration scope.

## 2026-05-10 Ruff residual cleanup (BACKLOG; **N818 SHIPPED 2026-05-10 at `44ac760`**; E501 still open)

> **N818 outcome (2026-05-10):** SHIPPED as Task family C in polish bundle 2026-05-10 (commit `efd3e15`). All 8 exception class renames landed in one mechanical commit: `SchemaVersionMismatch`, `LeaseRevoked`, `WatchlistEntryNotFound`, `ConcurrentRunBlocked`, `ChartingUnavailable`, `SoftWarnException`, `HardCapException`, `DuplicateOpenPositionException` → `…Error` suffixed. ~284 lines changed across `swing/` + `tests/` + `docs/` (the docs/ touches were spec/plan/backlog historical-reference renames; Codex R1 Minor #1 surfaced that the phase3e-todo N818 table cells got reflowed by the sed pass and the audit trail was restored via parenthetical). Ruff baseline 26 → 18 (matches expectation). 18 E501 still open per below.

**Surfaced 2026-05-10** during a ruff sweep that took the `swing/` baseline from 78 → 26 across three commits (`e99047f` safe auto-fixes 78→44, `33338f7` unsafe auto-fixes 44→34, `9c9b57c` manual B904+E741+SIM115-noqa batch 34→26). The 26 remaining are deferred for bundling with other minor fixes rather than a dedicated dispatch.

### Remaining ruff issues in `swing/`

| Code | Count | Description | Effort | Risk |
|---|---:|---|---|---|
| **N818** | 8 | Exception class names lacking `Error` suffix | ~10 min mechanical rename + verify | Medium — cross-cutting (~79 file references across swing/ + tests/) |
| **E501** | 18 | Lines exceeding 100-char `line-length` | ~30 min judgment work | Low per-site; no mechanical fix |

### N818 — exception class renames (8 classes)

Each rename is a sed-style global replace; names are distinctive enough that no substring false-positives are likely.

| Old | New | swing/ files | tests/ files |
|---|---|---:|---:|
| `SchemaVersionMismatch` (renamed to `SchemaVersionMismatchError`) | `SchemaVersionMismatchError` | 4 | 4 |
| `LeaseRevoked` (renamed to `LeaseRevokedError`) | `LeaseRevokedError` | 10 | 12 |
| `WatchlistEntryNotFound` (renamed to `WatchlistEntryNotFoundError`) | `WatchlistEntryNotFoundError` | 2 | 2 |
| `ConcurrentRunBlocked` (renamed to `ConcurrentRunBlockedError`) | `ConcurrentRunBlockedError` | 4 | 4 |
| `ChartingUnavailable` (renamed to `ChartingUnavailableError`) | `ChartingUnavailableError` | 4 | 2 |
| `SoftWarnException` (renamed to `SoftWarnError`) | `SoftWarnError` | 6 | 4 |
| `HardCapException` (renamed to `HardCapError`) | `HardCapError` | 7 | 2 |
| `DuplicateOpenPositionException` (renamed to `DuplicateOpenPositionError`) | `DuplicateOpenPositionError` | 7 | 5 |

(Note: this table was a planning artifact pre-2026-05-10 polish bundle rename. Both columns originally read identically because the planner left the "Old" cell as a TODO mirror of "New"; the polish-bundle-2026-05-10 sed pass through `docs/` reflowed the still-pending TODO mirrors. The old-name parenthetical above restores the audit trail.)

**Approach when attempted:** `git grep -l <OldName> | xargs sed -i 's/<OldName>/<NewName>/g'` per class; run `pytest -m "not slow"` after each batch (or after the full set) to verify; commit as a single rename pass.

**Watch-item:** verify no test asserts on the OLD class name as a string literal (e.g., `pytest.raises(ValueError, match="WatchlistEntryNotFound")` would have to become `match="WatchlistEntryNotFoundError"`). If found, those test assertions need the new name too — sed handles that uniformly since the match string contains the class name.

### E501 — line-too-long (18 lines)

`line-length = 100` is already configured (per `pyproject.toml`). The 18 violators exceed even that. No mechanical fix; each needs an editorial choice (break the string literal, extract a variable, accept a `# noqa: E501` for a justified comment). Would benefit from looking at all 18 sites and grouping by category (long log strings, long expressions, long comments) before deciding.

### Bundling guidance

These are good candidates to fold into ANY future small-scope dispatch as out-of-band cleanup, e.g.:
- A backlog UX-polish bundle (3e.4 + 3e.7) — add the N818 rename as a separate commit in the same dispatch
- A future tooling/lint pass — bundle with any pyproject.toml or CI configuration work
- Phase 9 writing-plans/executing-plans dispatch — N818 may surface naturally if any new exception classes get added (single batch commit at that point covers both new + legacy)

Per project baseline-tracking convention: when bundled in, update `docs/orchestrator-context.md`'s "ruff baseline" line in the track-record summary to the post-fix count. (CLAUDE.md does not currently track a ruff baseline; the living-state mention is in orchestrator-context.md.)

### Cross-references

- Sweep commits: `e99047f`, `33338f7`, `9c9b57c` on `main` (2026-05-10).
- `docs/orchestrator-context.md` track-record summary still reads "ruff baseline 78 preserved" (anchored to HEAD `b4bb9dd` polish-bundle ship — historical narrative). The live state at HEAD `9c9b57c` is **26**; orchestrator-context.md track-record summary line should be updated to the new live count at next housekeeping commit, OR when this backlog item is attempted (whichever comes first).

---

## 2026-05-10 Formalize orchestrator-vs-implementer execution-mode policy (PROCESS; below current backlog priority)

**Operator-surfaced 2026-05-10** during the 3e.16 dispatch design-question round. Operator clarified the principle: **default to implementer-dispatch over orchestrator-inline; minimize orchestrator context growth; crossover where inline beats dispatch is when orchestrator's token cost is less than the implementer's spinup-plus-task cost.** Captured as auto-memory at `feedback_orchestrator_vs_implementer_execution.md`. This entry tracks the formalization work to make the policy operationally enforceable across future sessions.

### Why formalize

- Auto-memory captures the principle but is fuzzy on the cost-estimation method. Without a heuristic the orchestrator can run pre-task, the default-to-dispatch rule will erode under orchestrator-side optimism ("this one is small enough").
- This session already had orchestrator-inline drift (operator-gate I1 + 3e.15 both inline) before the principle was made explicit. Recurrence likely without a checklist.
- Brief-drafting checklist + orchestrator-context Conventions section both lack a "decide execution mode" step — currently implicit in operator-driven choice (which means the orchestrator carries the cognitive load each time).

### Scope (what "formalize" likely means)

1. **Cost-estimation heuristic.** A back-of-envelope rubric the orchestrator runs before each task:
   - Estimate orchestrator token cost: file reads + file edits + tests written + commit drafting + housekeeping. Use ~prior-session anchors as benchmarks (3e.15 was ~5-8k orchestrator tokens; operator-gate I1 was ~3-4k; polish-bundle-2026-05-10 brief authorship was ~12-15k orchestrator tokens for the dispatch path).
   - Estimate implementer spinup cost: bootstrap (CLAUDE.md + orch-context + brief read) ≈ 30-50k tokens; plus task-implementation cost (~similar to orchestrator-inline since same code surface).
   - Crossover: if estimated orchestrator-inline < ~30k AND task is single-file + no TDD discipline benefit + no adversarial-review benefit, INLINE; else DISPATCH.

2. **Brief-drafting checklist addition.** Add a §0 "execution mode decision" line: orchestrator records the chosen mode + rationale BEFORE drafting brief content. Forces explicit consideration.

3. **Orchestrator-context Conventions update.** Promote the auto-memory feedback into a Conventions §-level entry (with cap-rotation if needed). Future fresh-orchestrator sessions read it at bootstrap.

4. **Telemetry-style retrospective.** After each ship, capture in the return report: actual orchestrator tokens consumed (estimable from the conversation log) vs the pre-task estimate. Builds a feedback loop on the heuristic's calibration.

5. **Edge cases worth enumerating:**
   - Mid-gate operator-driven scope changes (operator-gate I1 pattern) — defaults to inline regardless because dispatch overhead doesn't make sense for a 30-min mid-gate hotfix on an active worktree branch
   - Housekeeping commits (orchestrator-context updates, phase3e-todo SHIPPED markers, post-merge memory captures) — always inline
   - Brief-author-error mid-dispatch fixes — could be either path; operator's call

### Effort estimate

~1-2 hr orchestrator-thread work to draft the checklist + heuristic + memory→conventions promotion + brief-template addition. No code; pure process-doc work. Can be done by orchestrator inline in a quiet moment between dispatches OR queued as a thinking-session task.

**NOT a dispatch candidate** — this is orchestrator-doctrine work that lives in orchestrator-context + brief templates; an implementer doesn't have the cross-session orchestrator-perspective to do it well. (And this very item demonstrates the principle: process-doc work IS the kind of thing where orchestrator-inline beats implementer-dispatch on the cost-crossover.)

### Cross-references

- `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/feedback_orchestrator_vs_implementer_execution.md` — the auto-memory entry capturing the principle
- `docs/orchestrator-context.md` Conventions section — target home for the formalized policy
- `feedback_orchestrator_performs_merge.md` — pattern complement (both about scoping orchestrator actions to high-leverage edges)

---

## 2026-05-10 3e.8 disposition + commission bundles (derived from sell-side advisories investigation)

**Operator-orchestrator walkthrough 2026-05-10** of the 14 operator-decision items in [`docs/3e8-sell-side-advisories-investigation.md`](3e8-sell-side-advisories-investigation.md) §6 produced the dispositions below. Three commission bundles + three deferred-with-gate items + one in-flight operator-action (§4.G transcription) + two banked-without-gate items.

### Disposition matrix (14 items)

| # | §3e.8 item | Disposition | Workstream / trigger |
|---|---|---|---|
| 1 | §4.A trail-MA gating | §4.A.bis commissioned (advisory-only); §4.A deferred (V2.1 §VII.F-routed; gated on §4.G) | Bundle 3 below |
| 2 | §4.B trim/sell-into-strength | Commission V1 (single hint at +1R; default 25%) | Bundle 2 below |
| 3 | §4.C / §4.C.bis time-stop | Defer both; revisit at n≥10 closed sub-A+ trades OR §4.G-driven Minervini 7-week confirmation | Banked — see "Banked without gate" below |
| 4 | §4.D parabolic detector | Commission, bundled with §4.B + §4.K (sell-side bundle) | Bundle 2 below |
| 5 | §4.E briefing advisories | Commission, bundled with §4.F (parity bundle) | Bundle 1 below |
| 6 | §4.F detail+expanded advisory column | Commission, bundled with §4.E | Bundle 1 below |
| 7 | §4.G Minervini SEPA + DST sell-side transcription | Commission as immediate priority — operator-action; PRECEDES Bundles 1-3 | In-flight — scaffolding files at `reference/methodology/minervini-sell-side-rules.md` + `reference/methodology/dst-take-profit-and-trail.md` |
| 8 | §4.H sector RS check | Defer with second-source gate | Deferred-with-gate below |
| 9 | §4.I volume-confirmed exit | Defer with §4.G-completion-gate-trichotomy | Deferred-with-gate below |
| 10 | §4.J combined-violation | Defer with second-source gate | Deferred-with-gate below |
| 11 | §4.K planned_target_R hit | Commission, bundled with §4.B + §4.D | Bundle 2 below |
| 12 | DHC §6.2 decision | Case A confirmed 2026-05-10 (snapshot 2026-05-08T11:24:23: open_R=0.85, MFE=0.88R, maturity_stage=pre_+1.5R) — keep 20MA trail; ignore 10MA suggestion | Resolved |
| 13 | §6.3 sequencing | Approved as 4-step: §4.G transcription → Bundle 1 → Bundle 2 → Bundle 3 | Resolved |
| 14 | §6.4 [UNVERIFIED] flags (13 items) | Triage folded into §4.G transcription work | In-flight — see scaffolding files |

### §4.G transcription — **COMPLETE 2026-05-10 within available sources**

**DST file** (`reference/methodology/dst-take-profit-and-trail.md`): `~ PARTIAL` — 3/5 CONFIRMED-with-correction; 2/5 NOT-PRESENT-IN-SOURCE; 2 NEW rules surfaced (D.6 intraday-EMA parabolic + D.7 ADR-extension trim). Orchestrator pre-filled via PyMuPDF extraction of the DST PDF.

**Minervini file** (`reference/methodology/minervini-sell-side-rules.md`): `~ PARTIAL` — 1/7 CONFIRMED-QUANTITATIVE (M.2 sell-into-strength with R-multiple-of-stop-loss anchor); 4/7 BRIEF-MENTION-NO-DETAIL; 2/7 NOT-PRESENT-IN-AVAILABLE-SOURCES (M.1, M.4). Operator reviewed TLSMW (2013) on 2026-05-10. Think & Trade Like a Champion (2017) is NOT available — M.4 7-week rule remains unverifiable.

**Triggered post-completion (resolutions):**

- **§4.I gate-trichotomy → OUTCOME 2 (escalate to second-source gate).** M.6 is qualitative-without-threshold in TLSMW. §4.I now in same bucket as §4.H + §4.J (deferred-with-second-source-gate).
- **§4.A full + §4.C/§4.C.bis deferrals REINFORCED.** No quantitative anchor for either in available sources. §4.C/§4.C.bis: doctrine landscape on time-stops favors the AGGRESSIVE end (Q.1 3-5 day) — opposite of original 3e.8 framing.
- **Bundle 2 §4.B trim defaults need re-anchoring.** Doctrine = DST D.2 (50% on Day 3-5 calendar window) OR Minervini M.2 (R-multiple stop-tighten, NOT trim). The 3e.8 default (+1R first-time / 25% trim) is operator-policy hybrid. Implementation brief should support EITHER trigger pattern OR keep operator-policy hybrid with explicit annotation.
- **Bundle 2 §4.D parabolic defaults need re-anchoring.** Doctrine = DST D.7 (>7x ADR above 50SMA per Realsimpleariel). The 3e.8 defaults (25%/5d/15%) are arbitrary. Implementation brief should re-anchor.
- **Bundle 3 reframed to Option δ (hybrid α + β-LITE).** Operator-locked 2026-05-10. TWO complementary advisories: (a) §4.A.bis maturity-stage MA hint (operator-policy per Tier-3 #6); (b) M.2 R-multiple stop-tighten hint (doctrine per TLSMW Ch 13 p. 296). Different triggers (MFE-anchored stage vs live R-multiple); complementary signals. ~4-5 hr bundled.
- **13 [UNVERIFIED] flags in `docs/3e8-sell-side-advisories-investigation.md` §6.4 — dispositions captured in methodology files.** Future doc-update pass can refresh §6.4 inline if/when operator wants the investigation doc to reflect the post-transcription state.

### Bundle 1 — Advisory-parity (§4.E + §4.F) — **SHIPPED 2026-05-11 at `b535cb2`** (worktree dispatch; 9 commits = 5 task-impl + 1 ruff-style + 3 Codex-fix; 4 Codex rounds NO_NEW_CRITICAL_MAJOR)

> **Outcome:** SHIPPED via worktree dispatch on `3e8-bundle-1-advisory-parity` branch from BASELINE_SHA `a0d8d21`. Wires existing advisory rules into pipeline briefing (`exports/<session>/briefing.md` + `.html`) + trade-detail page (`/trades/{id}`) + open-positions expanded HTMX partial. NO new advisory rules; pure parity work. Codex chain 4 rounds → NO_NEW_CRITICAL_MAJOR (R1 0/4/2 → R2 0/2/2 → R3 0/1/1 → R4 0/0/0; convergent shape; each round caught real issues including a transient-failure cache-divergence trap fixed via new `_CachingFetcherWrapper`). 2 Major findings ACCEPTED with rationale (R1 M1 brief-on-main-vs-baseline procedural; R1 M4 V2-hardening on yfinance call enforcement). Operator-witnessed gate via Chrome MCP: S2+S3+S4+S5+S6 PASS; S1 SKIPPED-with-test-coverage. Test count 2183 → 2206 (+23); ruff baseline 18 unchanged. **2 V2 watch items banked separately below.**

**Cross-refs:** §3e.8 §4.E + §4.F. Brief at `docs/3e8-bundle-1-advisory-parity-brief.md`.

### Bundle 2 — Sell-side advisories (§4.B + §4.K + §4.D) — **SHIPPED 2026-05-11** at `3485f51` (worktree dispatch; 9 commits = 5 task-impl + 4 Codex-fix; 4 Codex rounds NO_NEW_CRITICAL_MAJOR)

> **Outcome:** SHIPPED via worktree dispatch on `3e8-bundle-2-sell-side-advisories` branch from BASELINE_SHA `7f3cfa6`. Three new sell-side advisory rules (§4.B `suggest_trim_into_strength` at +1R first-time / 25% trim; §4.K `suggest_planned_target_r_hit` when `r_so_far ≥ trades.planned_target_R`; §4.D `suggest_parabolic_trim` at >7× ADR above 50SMA per DST D.7 / Realsimpleariel doctrine anchor) wired into 6 composition surfaces (dashboard list view + open-positions row + open-positions expanded HTMX partial + trade-detail page + pipeline briefing composer + CLI `swing trade advisory`). All advisory-message-only; no schema; no V2.1 §VII.F routing. `AdvisoryContext` gains `adr_pct: float | None` + `has_been_trimmed: bool` fields; `StopAdvisoryConfig` gains 3 cfg keys with `__post_init__` validation rejecting NaN/inf/out-of-range overrides. New `compute_adr_pct` helper at [`swing/pipeline/ohlcv.py`](../swing/pipeline/ohlcv.py) with robust guards (insufficient bars, NaN/inf/non-numeric/zero-close/High<Low rejected at the data boundary). Codex chain 4 rounds → NO_NEW_CRITICAL_MAJOR (R1 0/3/2 → R2 0/2/2 → R3 0/1/2 → R4 0/0/1; convergent shape; chain drove +25 tests via 4 rounds of defensive numeric / config-validation hardening that wasn't in brief acceptance criteria). 1 Major finding ACCEPTED-with-rationale (R1 M2: `_step_export` not a strict snapshot — pipeline lease serializes all writers; matches pre-existing posture of equity/exits/trades reads in same block; misleading comment corrected). Operator-witnessed gate via Chrome MCP S1+S2+S3+S4+S5+S6 ALL PASS — LAR `parabolic_trim` fires across all 4 UI/output surfaces with exact spec-matching message ("Parabolic extension — price $11.68 is ≥7.0× ADR above 50SMA (ADR=6.36%); consider aggressive trim per DST D.7 / Realsimpleariel"); DHC r=0.85R matches CLAUDE.md snapshot, all Bundle 2 rules correctly suppressed where triggers not met. Test count 2206 → 2277 (+71); ruff baseline 18 unchanged.

**Operator design locks** (in-session 2026-05-11):
- §4.B trigger: (a) R-multiple over (b) DST D.2 Day-3-5 calendar / (c) both / (d) hybrid. Doctrine-faithful Day-3-5 trigger banked for V2 if R-multiple version mis-times the trim window.
- §4.D thresholds: (b) DST D.7 doctrine (>7× ADR above 50SMA) over (a) 3e.8 arbitrary defaults / (c) both. D.6 intraday-EMA upgrade banked for V2.

**Brief defect surfaced (lesson banked below):** Brief enumerated 5 composition surfaces in §0.2; actual count is **6** — `swing/cli.py:trade_advisory_cmd` was the 6th surface (CLI), caught by Codex R1 Major #1. Resolved with `--adr-pct` CLI flag + fill-loading + `has_been_trimmed` derivation. Lesson: orchestrator brief should grep ALL invocations of the composition target, not memory-enumerate.

**Cross-refs:** §3e.8 §4.B + §4.K + §4.D. Brief at `docs/3e8-bundle-2-sell-side-advisories-brief.md`.

### Bundle 3 — Maturity-stage hint + M.2 R-multiple stop-tighten hint (Option δ) — **SHIPPED 2026-05-11** at `ea95bc8` (worktree dispatch; 10 commits = 7 task-impl + 2 Codex-fix + 1 return-report; 3 Codex rounds NO_NEW_CRITICAL_MAJOR)

> **Outcome:** SHIPPED via worktree dispatch on `3e8-bundle-3-maturity-and-stop-tighten-hints` branch from BASELINE_SHA `9d5cfb1`. Two new sell-side advisory rules closing the operator-locked subset of the 3e.8 advisory-expansion arc: (1) **§4.A.bis** `suggest_maturity_stage_trail_ma_hint` — informational hint per Tier-3 #6 (`pre_+1.5R` / `+1.5R_to_+2R` → `20MA`; `>=+2R_trail_eligible` → `10MA`); does NOT suppress existing trail advisories. (2) **M.2** `suggest_r_multiple_stop_tighten` — doctrine-anchored to TLSMW Ch 13 p. 296 verbatim (default `tighten_at_r_multiple = 2.0R`). Both advisory-message-only; no schema; no V2.1 §VII.F routing. `AdvisoryContext` gains `maturity_stage: str | None` field; `StopAdvisoryConfig` gains `tighten_at_r_multiple` cfg key with `__post_init__` NaN/inf/non-positive rejection. New `select_latest_active_snapshot_for_trade` repo helper at [`swing/data/repos/daily_management.py`](../swing/data/repos/daily_management.py) (Task C.0 extraction). 6 composition surfaces threaded (web ×4 + pipeline briefing + CLI); CLI gains `--maturity-stage` flag with enum-constrained choices. Codex chain 3 rounds → NO_NEW_CRITICAL_MAJOR (R1 0/2/0 → R2 0/1/0 → R3 0/0/0; convergent). Operator-witnessed gate via Chrome MCP S1+S2+S3+S4+S5+S6+S7 ALL PASS — §4.A.bis fires on all 5 open trades with "Maturity stage pre_+1.5R — recommended trail-MA: 20MA"; M.2 correctly suppressed everywhere (max R is DHC 0.82R, VSAT 0.64R); LAR carries Bundle 2 parabolic + Bundle 3 maturity hint together; CLI `--maturity-stage` flag verified accept-with-flag / suppress-without; fresh worktree pipeline run (session 2026-05-12) emitted briefing.md with §4.A.bis advisory line per open trade verbatim. Test count 2278 → 2328 (+51); ruff baseline 18 unchanged. **2 V2 lessons banked separately below.**

**Operator design locks** (operator handoff brief 2026-05-11 locked Option δ scope + cfg defaults; this brief locked remaining minor questions):
- §4.A.bis fires informationally; does NOT suppress existing trail_10ma / trail_20ma. Full classification-altering §4.A remains banked-without-gate.
- §4.A.bis is operator-policy maturity-stage-driven; doctrine-faithful stock-speed-driven version (per DST D.3) is V2 (requires new schema).
- M.2 default `tighten_at_r_multiple = 2.0R` (conservative floor; TLSMW example = 2.86R for 7%/20%).

**Codex Major findings resolved** (3 majors total across 2 rounds):
- R1 #1: NaN guard on M.2 rule (mirrors Bundle 2 parabolic isfinite discipline).
- R1 #2: **`compute_price_independent_suggestions` helper** introduced. §4.A.bis is the only price-independent rule today (DB-sourced, not PriceCache-dependent); fires even under PriceCache degradation. Architectural fix banked as V2 lesson on degradation pathways. Threaded across 5 web/pipeline composition sites.
- R2 #1: Briefing composer's fetcher-exception branch also emits the maturity hint (not just `current_price is None` path).

**Brief deviations banked for orchestrator learning:**
- §4.A.bis message glyph: implementer used em-dash `—` instead of brief's arrow `→` for consistency with existing advisory message convention ("Trail stop up to $X — 0.3% below 10MA"). Right call.
- Brief §0.2 file-attribution error: `build_open_positions_expanded` lives in `swing/web/view_models/open_positions_row.py`, NOT `dashboard.py`. Implementer addressed at actual location. Lesson banked V2 #2 below.

**Pre-existing test failures noted:** 3 tests in `tests/integration/test_phase8_pipeline_walkthrough.py` fail on main HEAD `622c669` PRE-Bundle-3 with same error ("archive returned None" → no daily_snapshot rows). NOT Bundle 3 regressions; banked for separate triage.

**Cross-refs:** §3e.8 §4.A.bis + new M.2 rule. Brief at `docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md`. Return report at `docs/3e8-bundle-3-return-report.md`.

### Deferred §4.H — Sector RS check (second-source gate)

**Trigger to revisit:** A doctrine-confluent sector-lag exit rule surfaces from §4.G transcription OR another future doctrine source.

**Rationale:** Single-source-Q (Qullamaggie only) is structural weakness; no Minervini or DST analog in surveyed sources. Cost-benefit (10-14 hr + V2.1 §VII.F) doesn't change with trade-volume scale. Drop-equivalent for now; gate preserves optionality.

**Cross-refs:** §3e.8 §4.H + §3.H.

### Deferred §4.I — Volume-confirmed exit overlay (§4.G-completion-gate-trichotomy)

**Trigger to revisit:** §4.G transcription completes. Then THREE possible dispositions per M.6 outcome:
- M.6 carries **specific** volume threshold in source → commission §4.I with confirmed defaults (~2-3 hr; advisory-message-only)
- M.6 is **qualitative** without numerical threshold → escalate to second-source gate (mirror §4.H pattern)
- M.6 **doesn't exist** in source → drop §4.I

**Rationale:** Threshold-tuning friction without doctrine anchor; premature optimization. Gate ties revisit to concrete trichotomy.

**Cross-refs:** §3e.8 §4.I + §3.I.

### Deferred §4.J — Combined-violation rule (second-source gate)

**Trigger to revisit:** A doctrine-confluent combined-violation rule surfaces from §4.G transcription OR another future doctrine source.

**Rationale:** Single-source-Q (Qullamaggie only); cosmetic refinement (operator already sees both messages). Same gate-pattern as §4.H for matrix consistency.

**Cross-refs:** §3e.8 §4.J + §3.J.

### Banked without gate — §4.A full + §4.C / §4.C.bis

**§4.A full** (classification-altering trail-MA gating with suppression): Banked. Trigger to revisit = sufficient evidence accumulation from Bundle 3's §4.A.bis hint adoption (n≥10 closed trades where operator's actual stop adjustments consistently follow the maturity-stage-recommended MA). At that point, the §4.A.bis behavioral evidence IS the shadow-mode-equivalent that V2.1 §VII.F would otherwise require.

**§4.C / §4.C.bis** (time-stop discipline change): Banked. Triggers to revisit = either (a) n≥10 closed sub-A+ hypothesis trades giving statistical signal on whether 10/0.5R is too aggressive, OR (b) operator surfaces a specific trade time-stopped prematurely with hypothesis still under evaluation, OR (c) §4.G Minervini transcription confirms 7-week rule context that justifies an informed default change.

### Cross-references for this disposition

- `docs/3e8-sell-side-advisories-investigation.md` — full investigation analysis (746 lines)
- `reference/methodology/minervini-sell-side-rules.md` — §4.G scaffolding (Minervini)
- `reference/methodology/dst-take-profit-and-trail.md` — §4.G scaffolding (DST)
- Earlier 3e.8 entry above (line 311) — investigation entry summary

---

## 2026-05-11 V2 watch items banked from 3e.8 Bundle 1 ship

### V2 — Extract shared advisory composer (drift-risk reduction)

**Banked from:** Bundle 1 Codex R1 Minor #1 (orchestrator triage 2026-05-11).

**Symptom:** Advisory composition is now hand-duplicated across 5 paths post-Bundle-1 ship: `build_dashboard`, `build_open_positions_row`, `build_trade_detail_vm`, `build_open_positions_expanded`, briefing helper (`compose_open_trade_advisories_for_briefing`). Future drift risk if `AdvisoryContext` inputs change — every change to advisory composition needs to be propagated to all 5 sites independently.

**Brief-locked deferral:** Bundle 1 brief §0.3 #2 explicitly locks "mirror dashboard composition" for V1 to avoid scope-creep. The hand-duplication is a known trade-off accepted at brief time.

**Proposed V2:** Extract a shared "compose advisory VMs for trade" web-side helper + a separate data_asof-pinned pipeline-side helper. Both consume a common `AdvisoryContext` constructor; both produce the same `tuple[AdvisorySuggestionVM, ...]` shape. Single source of truth for advisory composition logic.

**Effort estimate:** ~3-4 hr (refactor + update 5 call sites + verify all existing tests still pass).

**Trigger:** When `AdvisoryContext` inputs change OR a third advisory-rendering surface gets added OR a Codex round on a future bundle flags drift.

### V2 — `build_open_positions_expanded` cache I/O during SQLite read-snapshot

**Banked from:** Bundle 1 Codex R1 Minor #2 (orchestrator triage 2026-05-11).

**Symptom:** `build_open_positions_expanded` performs cache I/O (PriceCache.get_many) while the route holds a SQLite read-snapshot transaction. Lock window is bounded by `cfg.web.price_fetch_deadline_seconds` (typically 5-8s) but the pattern diverges from `build_dashboard`'s open-own-conn-DB-phase-then-cache-phase canonical pattern.

**Operational impact:** Under sustained load (many concurrent expand requests), the SQLite read-snapshot lock window blocks other read transactions for the cache-I/O duration. At single-operator scale this is invisible; it surfaces if/when the project ever supports concurrent operator sessions or background read-heavy workloads.

**Proposed V2:** Refactor `build_open_positions_expanded` to mirror `build_dashboard`'s pattern — open own connection, complete DB phase, close connection, then enter cache phase. Symmetric with the canonical pattern.

**Effort estimate:** ~2-3 hr (refactor + verify expand-route tests still pass).

**Trigger:** When concurrent-session support becomes a project goal OR when operator surfaces lock-related latency on the expand route.

### Cross-references

- Bundle 1 SHIPPED entry above (line ~417 post-housekeeping)
- `docs/3e8-bundle-1-advisory-parity-brief.md` §0.3 #2 (mirror-dashboard-composition lock)
- `swing/web/view_models/dashboard.py:build_dashboard` — canonical open-own-conn pattern reference

---

## 2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 2 ship

### V2 — Brief composition-surface enumeration: grep, don't memory-enumerate

**Banked from:** Bundle 2 Codex R1 Major #1 (orchestrator triage 2026-05-11).

**Symptom:** Bundle 2 dispatch brief §0.2 enumerated 5 advisory-composition surfaces (4 web VMs + 1 pipeline briefing composer). The actual surface count is **6** — `swing/cli.py:trade_advisory_cmd` was the 6th, missed by orchestrator recon. Without Codex's discovery in R1 Major #1, the CLI `swing trade advisory` command would have emitted `trim_into_strength` advisories on already-trimmed trades because `has_been_trimmed` defaulted to `False` at the CLI composition site (no fill-loading wired through). Fixed in same Codex round with new `--adr-pct` flag + fill loading + 3 CLI tests.

**Generalized lesson:** When writing a dispatch brief that lists N composition / hand-mirroring sites for a new feature, the orchestrator MUST grep the codebase for ALL invocations of the canonical composition target — never enumerate from memory. Bundle 1 also listed 5 surfaces (same memory enumeration); Bundle 2 inherited the count without re-grepping. The CLI command lives outside the obvious web + pipeline namespaces and gets missed.

**Pre-empt in future dispatches:** writing-plans phase grep target = the function name or class name of the composition target (e.g., `compose_open_trade_advisories`, `AdvisorySuggestion`, `build_open_positions_row`). Cross-reference grep output against the brief's surface list before approving for dispatch.

**Effort estimate:** N/A — process change, not a code change. Lesson encoded in this entry + applied to all future bundle briefs.

**Promotion candidate to CLAUDE.md gotcha:** consider promoting "advisory composition has 6 sites (web ×4 + pipeline ×1 + CLI ×1) — grep for invocations, don't memory-enumerate" as a gotcha if a third bundle adds new rules. For now, lesson lives here.

### Inherited from Bundle 1 (unchanged)

The two V2 watch items banked at the 2026-05-11 Bundle 1 section above carry forward unchanged — Bundle 2 incremented the hand-duplication surface count from 5 → 6 (CLI added) but did NOT extract a shared composer. Same accept-with-rationale on the drift risk. Same trigger for V2 composer extract.

### Cross-references

- Bundle 2 SHIPPED entry above (line ~1108)
- `docs/3e8-bundle-2-sell-side-advisories-brief.md` §0.2 (5-site enumeration that missed CLI; §0.3 #4 V2 hand-duplication acceptance)
- `swing/cli.py:trade_advisory_cmd` — the 6th composition site

---

## 2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 3 ship

### V2 — Price-independent vs price-dependent advisory degradation pathways differ

**Banked from:** Bundle 3 Codex R1 Major #2 (`compute_price_independent_suggestions` helper introduction; orchestrator triage 2026-05-11).

**Symptom:** Before R1 fix, when PriceCache was degraded (live price unavailable), ALL advisory rules silently no-opped because the entire advisory composition was gated on having a valid `current_price`. But §4.A.bis (maturity_stage_trail_ma_hint) reads `maturity_stage` from DB and does NOT consume `ctx.current_price` — so it should still fire even when PriceCache fails. The original composition path conflated "price unavailable" with "skip ALL advisories", which masked DB-sourced advisories like §4.A.bis.

**Architectural fix (Bundle 3 R1 M#2):** `compute_price_independent_suggestions` helper splits the rule set into two tiers:
- **Price-independent rules** (e.g., §4.A.bis): fire when `AdvisoryContext` has the relevant DB-sourced fields populated; do NOT require valid `current_price`.
- **Price-dependent rules** (existing breakeven, trail_*, exit_below_*, weather, time_stop, Bundle 2's trim_into_strength + planned_target_r_hit + parabolic_trim): require valid `current_price`; no-op when PriceCache is degraded.

**Generalized lesson:** When adding new advisory rules in future bundles, classify the rule by data dependencies:
- If the rule's predicate consumes ONLY DB-sourced fields (from `AdvisoryContext` or `trade` model), it's price-independent — must remain visible under PriceCache degradation.
- If the rule's predicate consumes `ctx.current_price` (directly or via `r_so_far`), it's price-dependent — correctly no-ops under degradation.

The current 11-rule advisory surface is:
- Price-independent: §4.A.bis maturity_stage_trail_ma_hint (1 rule).
- Price-dependent: breakeven, trail_10ma, trail_20ma, exit_below_10ma, exit_below_20ma, exit_below_50ma, weather, time_stop, trim_into_strength, planned_target_r_hit, parabolic_trim, r_multiple_stop_tighten (12 rules including Bundle 3's M.2 trigger via `r_so_far`).

**Pre-empt in future dispatches:** writing-plans phase classifies each new rule + verifies it lands in the appropriate composition tier. Discriminating test: simulate PriceCache degradation; assert price-independent rules still fire while price-dependent rules no-op.

**Promotion candidate to CLAUDE.md gotcha:** consider promoting "advisory degradation must differentiate price-independent vs price-dependent rules — the `compute_price_independent_suggestions` split is the canonical pattern" as a gotcha if a third bundle adds a price-independent rule. For now, lesson lives here.

### V2 — Orchestrator brief composition-surface enumeration must use `def build_*` grep, not caller-site grep

**Banked from:** Bundle 3 brief §0.2 file-attribution error (orchestrator triage 2026-05-11).

**Symptom:** Bundle 3 brief §0.2 listed `build_open_positions_expanded` as living in `swing/web/view_models/dashboard.py`. Actual location: `swing/web/view_models/open_positions_row.py`. The implementer addressed the function at its actual location without surfacing the discrepancy. Brief inaccuracy did not block dispatch but creates rot-risk for future bundles that grep the brief looking for canonical surface enumerations.

**Root cause:** orchestrator's grep in §0.2 of Bundle 3 was scoped too broadly (matched any file referencing the function NAME) rather than the file containing the function DEFINITION. The brief recorded a CALLER location, not a DEFINITION location.

**Generalized lesson:** When orchestrator briefs enumerate function locations, the grep MUST scope to definitions:
```
grep -rn "^def build_" swing/web/view_models/
# Or, more targeted:
grep -rn "def build_open_positions_expanded" swing/
```
NOT:
```
grep -rn "build_open_positions_expanded" swing/  # matches both definitions AND callers
```

**Pre-empt in future dispatches:** writing-plans phase enumeration step uses `^def` anchored patterns for function locations; verify each location is a definition (the line starts with `def` or `class`, not a call).

### Cross-references

- Bundle 3 SHIPPED entry above (line ~1152)
- `docs/3e8-bundle-3-maturity-and-stop-tighten-hints-brief.md` §0.2 (file-attribution error documented; addressed at actual location by implementer)
- `docs/3e8-bundle-3-return-report.md` §7 (process deviation: inline TDD per task family; not surfaced to orchestrator mid-flight)
- `swing/trades/advisory.py:compute_price_independent_suggestions` — canonical pattern for advisory-degradation split
- `swing/web/view_models/open_positions_row.py:build_open_positions_expanded` — corrected location (NOT dashboard.py as brief §0.2 stated)

---

## 2026-05-13 Phase 10 closer — Phase 11 hand-off

Sub-bundle E SHIPPED (T-E.0..T-E.4 + T-E.5 + T-E.6 electives). Phase 10 CLOSED.

### Capture-needs surfaced during Phase 10 implementation (V2.1 §VII.F amendments pending)

Cumulative pending V2.1 §VII.F amendments at Phase 10 close (27+):

- (A T-A.7 + R2/R3) plan §A.7 binding-interface amendments (3): Wilson CI standard-vs-continuity-correction; `read_at_trade_time_policy` policy_id_stamp shape; `BaseLayoutVM.stale_banner` `str | None` vs `bool` (matches existing pattern).
- (B) plan-text deviations (5): T-B.1 `mistake_cost_R` cadence-grain rejection; T-B.2 `ALL_COHORTS_KEY='__all__'`; T-B.4 `cumulative_R_pct_of_capital` PERCENT units; T-B.7 display-block placement; T-B.2 7 cohort tabs (4 pre-registered + 2 orphan-label + "All").
- (C) plan-text deviations (5): T-C.1 cohort_relative_to_aplus rendering; T-C.1 doctrine_deviation_class baseline enum; T-C.5 filter SQL predicate; T-C.5 threading; T-C.5 toggle href shape.
- (D) plan-text deviations (5): D1 PROVISIONAL/LIVE math; D2 `candidate_criteria` vs `criterion_results.criterion_name`; D3 capital-friction trend window size; D4 `MaturityStageRow` per-row badge fields; D5 `aplus_take_rate_per_run` un-clamped.
- (E NEW) plan-text deviations (4):
  1. T-E.3 `ConfigPageVM` (not `ConfigVM` per brief §0.11).
  2. T-E.3 retrofitted 10 base-layout VMs (6 plan-named + 4 additional whose templates extend base.html.j2: ReviewVM / CadenceCompleteVM / ReviewsPendingVM / TradeDetailVM). Defense-in-depth per CLAUDE.md "base.html.j2 is shared" gotcha.
  3. T-E.5 service function is `record_snapshot` (NOT `record_snapshot_with_audit` per brief §0.5); Phase 9 Sub-bundle C ship-time naming preserved.
  4. T-E.1 N=10 + global_confidence_floor_n=20 + spec §5.4 "drops at n>=20": with the §A.4 N=10 LOCK the confidence-floor warning NEVER drops via the production callsite by construction. Implementation matches the locked behavior; spec wording could be amended to make the conditional dependence explicit. Discriminating test exercises window_size=20 to verify the band semantics are reachable.

- (D R2 M#1 banked at D) Phase 9 §7 sector_industry anchor + Phase 9 §6.2 multi-line parser amendments still pending.

**Total V2.1 §VII.F amendments pending: 27** (3 A + 5 B + 5 C + 5 D + 4 E + 2 Phase 9 = 24 Phase 10 + Phase 9 amendments banked).

### Operator-decision items pending Phase 11

1. **§8.4 Corporate_Actions MVP** — DEFERRED at Phase 10 electives triage (electives amendment §5). Banked at this section's existing 2026-05-13 entry. Phase 11 candidate.

2. **Schwab API Phase A** — operational metrics in Sub-bundle D (capital-friction + maturity-stage PROVISIONAL/LIVE) consume the Phase 9 Sub-bundle C `account_equity_snapshots` table. Schwab API integration (future phase) would write `source='schwab_api'` snapshots that outrank `source='manual'` per the spec §A.9 source ladder. Pre-Phase-11 triage decision: operator-paced.

3. **`mistake_cost_R_rolling_N_total` sum-class with bootstrap CI** — §A.21 spec-conformance deviation banked at writing-plans + carried through E T-E.1. Sub-bundle E ships "point" class (bare float); V2 may add sum-class with bootstrap CI on the window sum.

4. **Schwab inception-CSV ingestion** + **`account_equity_snapshots.equity_dollars` cash-basis vs MTM semantic formalization** (both banked at 2026-05-12 Phase 9 Sub-bundle C entry). Phase 11 candidates.

### Post-Phase-10 standalone dispatches (UNBLOCKED by Phase 10 close)

Per dispatch brief §1 + §7 watch items:

1. **Cleanup-script `-DeregisterFirst` extension** — Phase 9 husks (B/C/D/E) + Phase 10 Sub-bundle C/D/E orphan husks remain still-registered. Standalone dispatch will extend cleanup-script with a `-DeregisterFirst` switch + clear all pending husks.
2. **Test-runtime xdist + fixture-scope analysis** — fast suite at ~6:45 wall-clock at 3300+ tests; recommendation: profile → pytest-xdist → fixture-scope refactor for ~3-5x wall-clock reduction at zero coverage cost.
3. **§8.4 Corporate_Actions MVP** — schema-introducing standalone dispatch (new `corporate_actions` table + `0018_*.sql` migration + CLI surface + manual reconcile flow). Preserves Phase 10 §A.0 ZERO-new-schema lock; Phase 9 Sub-bundle A precedent (schema-introducing bundles get their own scoped review).

### V2 candidates banked at Phase 10 ship

1. **Orphan-emit discrepancy attribution surface** — Phase 9 Sub-bundle B per-run dedup allows orphan emits (discrepancies not attributed to a specific trade_id). Global discrepancy badge (T-E.3) counts these; per-trade indicator (T-E.6) does NOT. V2: "orphan discrepancy detail page" surfacing trade-less discrepancies.
2. **`render_class_d` "point" branch mean-semantics switch** (banked from Sub-bundle A return report §7). V2 may add sum-class semantics with bootstrap CI.
3. **Per-cohort "exclude trades stamped during paused intervals" filter** (banked from Sub-bundle B + electives amendment §7). Same UI shape as T-C.5; same VM pattern. Phase 11 candidate.

### Cross-references

- Phase 10 plan: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (HEAD `a34c00d`).
- Phase 10 electives amendment: `docs/phase10-electives-amendment.md`.
- Phase 10 spec: `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`.
- Sub-bundle E dispatch brief: `docs/phase10-bundle-E-executing-plans-dispatch-brief.md`.
- Sub-bundle E return report: `docs/phase10-bundle-E-return-report.md`.
