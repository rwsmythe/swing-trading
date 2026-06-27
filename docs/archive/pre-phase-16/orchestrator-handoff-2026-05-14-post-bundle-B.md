# Orchestrator handoff — 2026-05-14 (post-Sub-bundle-B-merge; Schwab arc 50% shipped)

You are taking over as orchestrator for the Swing Trading project at the **post-Sub-bundle-B-merge** breakpoint of the Schwab API integration arc. The Schwab arc is 50% shipped (A + B done; C + D remaining). Sub-bundle C dispatch is UNBLOCKED and is your first major action when operator commissions.

The prior orchestrator is handing off NOW because:
1. **Clean breakpoint** — Sub-bundle B fully shipped + integrated + housekeeping landed; gate passed live against operator's production Schwab credentials.
2. **Context-budget pressure** — prior orchestrator's session has been heavy (commissioned A brief + drove A merge + commissioned B brief + drove B gate + inline-fixed gate-caught defect + drove B merge + housekeeping). Fresh context window for C+D arc completion benefits from a clean slate.
3. **Schwab arc inheritance well-trodden** — A + B's lessons + 8+ tracked artifacts (specs, plans, briefs, return reports, recon docs) document everything; new orchestrator picks up cold from artifacts.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*`. Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded.

**Chrome MCP is AVAILABLE** for browser-driven gates (Phase 10 metrics surfaces still relevant; not needed for Sub-bundle C which is CLI-driven). Use port 8081 to avoid collision with operator's main-HEAD `swing web` session on 8080.

**Fast suite runs `-n auto` by default** at ~74s wall-clock post-Sub-bundle-B (3597 tests). Operator override: `pytest -n 0` for debug.

**Operator dispatches implementers themselves** (per durable preference `feedback_orchestrator_vs_implementer_execution.md`). Orchestrator drafts the brief + provides inline dispatch prompt as fenced code block; operator dispatches when ready.

**Always provide an inline dispatch prompt** with every brief (per durable preference `feedback_always_provide_inline_dispatch_prompt.md`).

## Step 1 — Read these in order

1. **This brief end-to-end** — captures post-Sub-bundle-B-merge state + Sub-bundle C dispatch readiness + B's gate-caught defect + camelCase gotcha + 4 unresolved-discrepancy operator explanations.

2. **`docs/phase3e-todo.md`** top entries 2026-05-14 — Sub-bundle B SHIPPED entry (with gate observations + V2 candidates + operator-explained discrepancies); Sub-bundle A SHIPPED entry; schwabdev distillation findings; Q18 build-vs-buy COA B disposition; writing-plans SHIPPED entry. **Read in reverse order** (top entries are most recent + most relevant).

3. **`docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md`** §Tasks-C at line 2130+ — per-task Sub-bundle C scope (8 tasks T-C.0.b..T-C.7; +68 tests projected; 4-5 Codex rounds estimated; **largest novel scope of the arc** — cache layer rewrite for Shape A parquet-per-(ticker, provider) market-data ladder per Q11 V1 INCLUDE).

4. **`docs/schwab-bundle-A-return-report.md`** + **`docs/schwab-bundle-B-return-report.md`** — Sub-bundle A + B implementer return reports. §6 watch items + §8 forward-binding lessons in each.

5. **`docs/schwab-bundle-A-task-A0b-recon.md`** + **`docs/schwab-bundle-B-task-B0b-recon.md`** — operator-paired live verification observations from A + B.

6. **`docs/schwab-bundle-B-executing-plans-dispatch-brief.md`** — most recent dispatch brief; format precedent for Sub-bundle C brief drafting.

7. **CLAUDE.md** status line + Gotchas section — status line through `df29232`. **NEW gotcha promotion candidate banked** for Sub-bundle D T-D.4: schwabdev camelCase parameter names vs project snake_case convention (see Sub-bundle B SHIPPED entry).

8. **`docs/orchestrator-context.md`** — durable orchestrator-role conventions.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                # expect 311bc2f at HEAD
git status                           # expect clean (some untracked operator artifact dirs)
git worktree list                    # expect main + 1-2 husks
python -m pytest -m "not slow" -q | tail -5     # expect ~3597 fast pass; 3 pre-existing failures
ruff check swing/ --statistics | tail -3        # expect 18 E501
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 18
```

Expected post-merge state:
- HEAD on main: `311bc2f` (post-Sub-bundle-B SHIPPED entry).
- ~3597 fast tests passing on main; 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures (NOT regressions); 2 cross-bundle pins SKIPPED (T-C.5 + T-C.7 — un-skip in Sub-bundle C).
- Schema v18.

## Step 3 — Schwab arc state at handoff

### Commit chain since prior orchestrator handoff

```
311bc2f docs(phase3e-todo): Schwab API Sub-bundle B SHIPPED entry — df29232 merge + gate-caught defect + camelCase gotcha + V2 candidates + operator-explained discrepancies
df29232 Merge schwab-bundle-B-trader-and-snapshot into main: Schwab API Sub-bundle B SHIPPED — Trader API + snapshot/orders/reconciliation pipeline + sandbox-gating (5 Codex rounds + 1 gate-caught fix; 11 commits)
34be84e fix(schwab-bundle-B): operator-paired-gate-caught defect — trader.py:362 max_results→maxResults camelCase + discriminating signature tests
0124a76 docs(schwab-api): Sub-bundle B return report
... (10 implementer commits T-B.0.b..T-B.8 + 4 Codex-fix commits)
19622b6 docs(schwab-api): Sub-bundle B executing-plans dispatch brief
4efc059 docs(phase3e-todo): correct Sub-bundle A post-merge pip framing — shim rebuild is cosmetic, code-pointer was already at main
a9900b1 docs(phase3e-todo): Schwab API Sub-bundle A SHIPPED entry — 5b6e5ba merge + post-merge state
5b6e5ba Merge schwab-bundle-A-foundational into main: Schwab API Sub-bundle A SHIPPED — schwabdev wrap + auth + migration 0018 + audit infrastructure (4 Codex rounds; 19 commits)
```

### Schwab arc bundles

| Bundle | Status | Branch / Merge SHA | Tasks | Tests delta | Codex rounds | Notes |
|---|---|---|---|---:|---:|---|
| **A** foundational | ✅ SHIPPED 2026-05-14 | `5b6e5ba` | 11 (T-A.0..T-A.10) | +209 net | 4 | Migration 17→18; 3-layer redactor; CLI setup/refresh/logout/status skeleton; audit infra |
| **B** Trader API + snapshot/orders | ✅ SHIPPED 2026-05-14 | `df29232` | 9 (T-B.0.b..T-B.8) | +101 net | 5 + inline fix | First live source-ladder writes; 4 real material discrepancies surfaced; camelCase kwarg defect caught + fixed inline |
| **C** Market Data API + cache ladder | 🟡 UNBLOCKED — your first dispatch | TBD | 8 (T-C.0.b..T-C.7) | +68 projected | 4-5 estimated | **Largest novel scope** — `PriceCache`/`OhlcvCache` rewrite to Shape A parquet-per-(ticker, provider); yfinance fallback discipline preserved; sandbox short-circuit; `--verify-marketdata` CLI |
| **D** polish + briefing + E2E + handoff | ⏸ BLOCKED on C | TBD | 7 (T-D.1..T-D.7) | +19 projected | 2-3 estimated | `swing schwab status` full surface; briefing banner; E2E test; cycle-checklist; CLAUDE.md gotchas; Phase 11 hand-off |

Strict A→B→C→D dispatch order per plan §0.3. C is unblocked post-B-merge.

### Production state at handoff

- **Schema:** v18 (locked since A T-A.7).
- **Tests:** ~3597 fast passing on main.
- **Production tokens DB:** `~/swing-data/schwab-tokens.production.db` exists (refresh-token clock started 2026-05-14; expires ~2026-05-21 — **operator must re-auth via `swing schwab setup` paste-back before then OR Sub-bundle C gate session needs rescheduling**).
- **Production schwab_api_calls:** 17 rows (mix of refresh + snapshot + orders + transactions + sandbox).
- **Production account_equity_snapshots:** 5 rows (3 manual + 2 schwab_api).
- **Production reconciliation_runs:** 9 (7 TOS-CSV + 2 schwab_api).
- **Production reconciliation_discrepancies:** 38 (30 resolved as `acknowledged_immaterial` + **8 unresolved material from Sub-bundle B gate** — see operator-action items below).

### Sub-bundle B forward-binding lessons (BINDING for Sub-bundle C)

Per `docs/schwab-bundle-B-return-report.md` §8 + Sub-bundle B SHIPPED entry. Sub-bundle C MUST honor:

1. **`schwabdev camelCase parameter names` discipline** — schwabdev uses `accountHash`, `fromEnteredTime`, `maxResults`, `startDate`, `endDate`, etc. Wrapper kwargs MUST match exactly. Sub-bundle B caught `max_results` vs `maxResults` defect at gate; orchestrator-inline fix at `34be84e`. Discriminating-test pattern at `tests/integrations/test_schwab_trader_kwarg_signatures.py` — replicate for any Sub-bundle C wrappers (`marketdata.quotes`, `marketdata.pricehistory`).
2. **Typed `SchwabApiError` audit-row close discipline** (R1 M#3) — pre-success rejection paths fire `record_call_finish(status='auth_failed'/'rate_limited'/'error', ...)` BEFORE re-raise. Audit log honest about both outcomes.
3. **Single-Client-instance discipline via `construct_authenticated_client()`** (R1 M#7) — Sub-bundle B added this helper in `auth.py`; cli_schwab delegates. Sub-bundle C's CLI must follow same pattern.
4. **Same-day account_hash-flip guard** (R1 M#8) — refuses on differing non-NULL hash. Sub-bundle C may need to verify Market Data calls don't bypass this guard (likely don't since Market Data API is symbol-driven, not account-driven).
5. **Pipeline-internal silent-skip vs CLI advisory rows** (R2 M#1) — pipeline-internal `_step_schwab_*` for `client=None` logs only (NO audit row); CLI surface writes advisory audit rows. Sub-bundle C's `_step_evaluate`/`_step_charts` cache integration should follow same pattern.
6. **CLI fetch preflight account_hash check** (R5 M#1) — before credentials prompt. Sub-bundle C's `--verify-marketdata` may not need this (Market Data is symbol-driven), but check the pattern.

### Sub-bundle A's 5 forward-binding lessons (still BINDING for Sub-bundle C)

Per `docs/schwab-bundle-A-return-report.md` §8:
1. schwabdev silent-failure-mode discipline — wrap+verify post-call state.
2. Audit-success-fire ordering.
3. `ensure_schwab_log_redaction_factory_installed()` (NOT `_install_*`) before every schwabdev call.
4. Redact-then-truncate audit-error ordering.
5. schwabdev 2.5.1 actual surfaces (8-param ctor; JSON tokens DB; **`Schwabdev` capital-S logger**; etc.).

### Cross-bundle pins remaining

- **T-C.5 verify-marketdata cross-bundle pin** — currently SKIPPED at `tests/integrations/test_schwab_pipeline_active_exclusion.py:257` (un-skip target: T-C.5 once `fetch --verify-marketdata` ships).
- **T-C.7 sentinel-leak audit Market Data coverage** — currently SKIPPED at `tests/integrations/test_schwab_token_redaction_audit.py:920` (un-skip target: T-C.7 once Market Data API cassettes recorded).

### V2 candidates banked from Sub-bundle B (operator-action follow-ups, not orchestrator-blocking)

- **Credential entry UX** — `SCHWAB_CLIENT_ID` / `SCHWAB_CLIENT_SECRET` env-var fallback OR session-cached prompt OR `--client-id` / `--client-secret` CLI flags. Operator prompted at every CLI invocation in B's gate session per Sub-bundle A T-A.2 security posture. Acceptable for V1 but friction-heavy for ops use.
- **Lease status fields** (R2 M#2 + R3 M#2 ACCEPT-WITH-RATIONALE family) — dedicated `schwab_step_status` lease column deferred to V2 since Bundle B was ZERO-new-schema scope.
- **Same-day-replay-provenance live-validation** — gate dates rolled between S2 and S4, so live UPSERT path NOT exercised. Cassette unit test in T-B.3 still pins discipline.

### Operator-action items pending post-handoff (NOT orchestrator-blocking)

1. **4 unresolved material discrepancies pending journal-side resolution** (operator-explained 2026-05-14):
   - **DHC `position_qty_mismatch` + `unmatched_open_fill`** (rows on runs 8 + 9): operator sold 9 shares 2026-05-14 as ~25% trim (sell into strength); NOT yet in journal. Operator-action: record trim fill via journal CLI + resolve discrepancies as `mistake_corrected`.
   - **VSAT + CVGI `entry_price_mismatch`** (rows on runs 8 + 9): journal entry-price misreadings (~$0.01 off). Operator-action: update entry prices in journal + resolve as `mistake_corrected`.
2. **`pip install -e .` shim rebuild** (cosmetic; per Sub-bundle A SHIPPED entry §6 #1) — `swing.exe` shim still locked; `python -m swing.cli` workaround works.
3. **Worktree husks cleanup** — Sub-bundle A husk + Sub-bundle B husk likely ACL-locked. Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (elevated PowerShell) at convenience.
4. **7-day refresh-token clock** — production tokens DB clock started 2026-05-14 / expires ~2026-05-21. Operator may need to re-run `swing schwab setup` paste-back before Sub-bundle C gate session if it lands past 2026-05-21.
5. **Optional Sub-bundle A S6 (`swing schwab logout`)** — not driven during A's gate; operator-elective.

## Step 4 — Sub-bundle C dispatch brief drafting (your first deliverable)

Sub-bundle C is the LARGEST NOVEL SCOPE of the arc — Q11 V1 INCLUDE market-data ladder rewrite. Cache architecture changes; persistence shape A (parquet-per-(ticker, provider)); yfinance fallback discipline; sandbox short-circuit; `--verify-marketdata` CLI.

### What the Sub-bundle C dispatch brief MUST include

Mirror `docs/schwab-bundle-B-executing-plans-dispatch-brief.md` structure (282 lines; 8 sections). Must consume:

1. **§0 reads:** plan §Tasks-C at line 2130+; Sub-bundle A + B return reports; A + B recon docs; `reference/schwabdev/api-calls.md` (pre-check for `quotes` + `pricehistory` method-name + signature pre-answers — Q12 + Q17 likely pre-answerable); `reference/schwabdev/client.md` (rate limits); `reference/schwab-api/market-data-{documentation,specification}.md`.
2. **§0.4 BINDING forward-binding lessons** from A (5) + B (6 NEW). Especially the camelCase kwarg discipline.
3. **§0.5 Codex pre-emption table** — extend Sub-bundle B's 4 patterns + add C-specific patterns.
4. **§0.6 inter-bundle dependencies** — single-Client-instance discipline (consume from `client.py:SchwabClient`); audit service-layer wrappers from A; source-ladder write path NOT applicable to C (market data is read-side cache, not source-ladder write).
5. **§2 operator-paired T-C.0.b verification gate** (HARD BLOCKER for cassette recording; operator's production-tier credentials already persisted; mirrors B's T-B.0.b).
6. **§3 operator-witnessed verification gate** — Sub-bundle C surfaces are mostly inline (cassette tests + sandbox short-circuit verification); only `--verify-marketdata` CLI requires operator-driven session.
7. **§5 watch items** including the un-skip-at-T-C.5 + T-C.7 cross-bundle pin reminders.

### Sub-bundle C task summary (per plan §Tasks-C)

8 tasks; +68 fast tests projected:

| Task | Scope | Tests |
|---|---|---:|
| T-C.0.b | Operator-paired live verification (cassette recording for marketdata.quotes + pricehistory; Q12 + Q17) | 0 |
| T-C.1 | Market Data API endpoint methods + mappers (`marketdata.py`) | +12 |
| T-C.2 | OHLCV archive Shape A parquet persistence + backward-compat rename + window-filter + empty-write-guard | +18 |
| T-C.3 | Market-data ladder fetcher (`marketdata_ladder.py`) | +14 |
| T-C.4 | `PriceCache` + `OhlcvCache` integration | +10 |
| T-C.5 | `swing schwab fetch --verify-marketdata` CLI subcommand | +6 |
| T-C.6 | Pipeline integration — `_step_evaluate` + `_step_charts` ladder injection | +4 |
| T-C.7 | Sentinel-leak audit Bundle C coverage (un-skip cross-bundle pin) | +4 |

**Largest task: T-C.2** (+18 tests; cache layer rewrite). Implementer should pre-check `reference/schwabdev/api-calls.md` for `pricehistory` exact kwarg names — if implementer assumes snake_case (per project convention), they'll repeat Sub-bundle B's defect.

## Step 5 — Operator preferences (durable; carry over)

- **Implementer-dispatch is the default** per `feedback_orchestrator_vs_implementer_execution.md`.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention).
- **Implementer runs adversarial-critic via `copowers:executing-plans` wrapper.**
- **Multi-choice format for design questions** (AskUserQuestion preferred).
- **Spec is canonical over brief on cosmetic typos.**
- **Production-write classifier soft-block** — Sub-bundle C's `--verify-marketdata` calls write `schwab_api_calls` audit rows; may trigger soft-block. Operator pre-authorizes via gate-path AskUserQuestion.
- **Always provide an inline dispatch prompt** (per `feedback_always_provide_inline_dispatch_prompt.md`).
- **Stop the web server when done** — worktree-side `swing web` MUST use `--port 8081` if operator's main session uses 8080. Not relevant for Sub-bundle C (no web surfaces in C scope).

## Step 6 — When Sub-bundle D dispatch brief gets drafted (post-C-ship)

Threading reminders for the Sub-bundle D dispatch brief (D closes the arc; you'll draft after C ships):

1. **Review-form polish task** — drop stale "(Phase 7 will auto-derive this from Fills.)" parenthetical at `swing/web/templates/partials/review_form.html.j2:66-67` per phase3e-todo "2026-05-13 Trade exit review form" entry. Operator-locked into Sub-bundle D last-bundle disposition.
2. **7-day refresh-token expiry alert design** — `swing schwab status` full surface MUST surface days-remaining alert (≤24hr WARN; ≤2hr ERROR + bold red); briefing banner; cycle-checklist weekly re-auth reminder; CLAUDE.md gotcha promotion at T-D.4.
3. **`unsupported_token_type` → `update_tokens(force_refresh_token=True)`** remediation surface design (per schwabdev `troubleshooting.md`).
4. **schwabdev camelCase kwarg discipline gotcha promotion** to CLAUDE.md per Sub-bundle B SHIPPED entry — Sub-bundle D T-D.4 candidate.
5. **R1 M#3 typed-SchwabApiError audit-row close discipline gotcha promotion** to CLAUDE.md — Sub-bundle D T-D.4 candidate.

## Step 7 — Banked items NOT to scope into Sub-bundle C

- **§8.4 Corporate_Actions MVP** — still deferred as standalone post-Phase-10 dispatch (separate from Schwab arc per phase3e-todo).
- **Schwab inception-CSV ingestion** (Q6) — separate dispatch per phase3e-todo.
- **Q3 multi-account / Q4 streaming / Q5 web UI / Q7 TOS deprecation / Q2 token encryption** — V2 candidates.
- **Order placement / cancellation** — explicit OUT-OF-SCOPE per spec §1.2 + §3.3.3.

## Step 8 — Quick reference summary

| Artifact | Path / commit |
|---|---|
| Brainstorm spec | `docs/superpowers/specs/2026-05-13-schwab-api-design.md` (`585556f`) |
| Plan | `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` (`7faab72`) |
| Sub-bundle A executing-plans brief | `docs/schwab-bundle-A-executing-plans-dispatch-brief.md` (`bd166c5`) |
| Sub-bundle A return report | `docs/schwab-bundle-A-return-report.md` (`6550494`) |
| Sub-bundle A T-A.0.b recon | `docs/schwab-bundle-A-task-A0b-recon.md` |
| Sub-bundle A merge | `5b6e5ba` |
| Sub-bundle B executing-plans brief | `docs/schwab-bundle-B-executing-plans-dispatch-brief.md` (`19622b6`) |
| Sub-bundle B return report | `docs/schwab-bundle-B-return-report.md` (`0124a76`) |
| Sub-bundle B T-B.0.b recon | `docs/schwab-bundle-B-task-B0b-recon.md` |
| Sub-bundle B inline gate-fix | `34be84e` |
| Sub-bundle B merge | `df29232` |
| Sub-bundle B SHIPPED entry | phase3e-todo top entry @ `311bc2f` |
| Sub-bundle C executing-plans brief | TBD (your first deliverable) |
| Distilled refs (BINDING §0 reads) | `reference/schwab-api/` (4 files; Schwab Developer Portal) + `reference/schwabdev/` (7 files; library docs) |
| Cross-phase backlog | `docs/phase3e-todo.md` (active; archive at `docs/phase3e-todo-archive.md`) |
| Orchestrator-role context | `docs/orchestrator-context.md` |

## Step 9 — Closing note from prior orchestrator

This handoff caps a productive session that drove Sub-bundle B from operator-dispatch through gate to merge. The Schwab arc is now operationally validated end-to-end against operator's actual production Schwab account: first live source-ladder source='schwab_api' writes; first Schwab-sourced reconciliation_runs; first sandbox-gating verified; 4 real broker-vs-journal discrepancies surfaced for operator triage (operator already has explanations: 1 NEW trim not yet journaled + 3 OLD entry-price journal mistakes).

The Sub-bundle B gate caught a real defect (camelCase vs snake_case kwarg) that cassette tests missed. Orchestrator-inline fix landed at `34be84e` with 5 discriminating tests pinning all 4 trader methods against `inspect.signature(schwabdev.Client.X)`. Worth promoting to CLAUDE.md gotcha at Sub-bundle D T-D.4.

Sub-bundle C is the LARGEST NOVEL SCOPE remaining (Q11 V1 INCLUDE market-data ladder; cache architecture rewrite). Pre-empt the camelCase trap in C's brief — implementer will be writing wrappers around `schwabdev.Client.quotes` + `schwabdev.Client.price_history` + similar.

Operator preference reaffirmed via durable memory: implementer-dispatch is default; orchestrator-inline only at token-cost crossover. Provide inline dispatch prompt with every brief.

Good luck.

---

*End of handoff brief. Post-Sub-bundle-B-merge orchestrator transition. Sub-bundle B SHIPPED. Sub-bundle C dispatch UNBLOCKED. Operator-paced.*
