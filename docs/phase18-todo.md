# Phase 18 — Data-Collection Integrity (TODO)

**Opened:** 2026-06-13 (scoped with the operator; CHARC-drafted per charter §2.3, operator-approved). **Theme:** the instrument's *inputs*. Phase 17 consolidated the code; Phase 18 makes the data the tool collects/stores trustworthy and its health visible. Motivated by the RD's 2026-06-13 data-collection audit (one real defect + the monitoring gap) + the operator's request for at-a-glance health.
**Demand-side:** RD (Briefs 1+2) + operator (tool-health monitor, GUI stoplights). **Supply-side:** CHARC (write-path audit, yfinance audit, boundary hygiene).
**Status:** OPERATOR-APPROVED 2026-06-13 (overall plan + 18-H added at approval). Nothing commissioned until Phase 17 closes (17-D.4 + the .2 icon recheck) and the operator sequences. Architecture passes for the tripwire-crossing arcs are pre-done or owed by CHARC at commissioning.
**Baseline at open:** main `98dff618` · schema v29 · (test count confirmed at first-arc branch).

---

## Tripwire posture
Most arcs cross a §3 tripwire (new schema, new module, new standing process, base-layout change) → their commissioning briefs route through CHARC. RD's two briefs already have the architecture pass (`docs/phase18-rd-briefs-charc-architecture-pass.md`, conditions C1-C5). CHARC authors the passes for the write-path audit, the yfinance audit, the tool-health monitor, and the stoplight GUI at commissioning.

## Backfill decision (LOCKED, on record)
The temporal-log 103-NaN-row **backfill is WITHDRAWN** (operator-locked 2026-06-13; three independent reads converged — RD/Codex/CHARC — payoff ~1 unique priced name, recoverable by time, not worth eroding the anti-#26-drift reproducibility guarantee). Only the **writer fix** (Arc 18-A) proceeds. Full record + override-guards: the architecture-pass doc.

---

## Arc 18-A — Temporal-log NaN writer fix + shared finiteness predicate [RD Brief 1; HIGH]
**Brief:** `docs/temporal-log-nan-writer-fix-commissioning-brief.md` (architecture-passed; conditions C1-C3).
**Scope:** add the finiteness guard to `build_ohlc_today_json` (skip-with-warning, mirroring Arc-8), extracting a SHARED finiteness predicate (C1) into `swing/data/` that BOTH this writer and `ohlcv_archive`'s trim consume — `temporal_metadata` (pipeline) imports FROM data, never the reverse (layer rule). NO backfill, NO migration, normal cycle. The skip→`warnings_json` partially closes the going-forward observability; the historical surface is the monitor (18-D, C3 dedup).
**Tripwire:** passed. **Couples with 18-B** (produces the shared predicate 18-B audits against).

## Arc 18-B — OHLC write-path finiteness audit & consolidation [CHARC; HIGH]
**Why:** Brief 1 is ONE instance of a recurring class — Arc-8 guarded `ohlcv_archive` but the temporal-log writer was missed (the #24-#26 two-path-divergence family). Grounded 2026-06-13: ≥3 OHLC persistence paths (archive, temporal log, candidates/pattern_forward_observations) and finiteness guards are ad-hoc across ~25 files, NOT systematic at persistence boundaries.
**Scope:** enumerate EVERY OHLC-bar persistence boundary; verify each routes through the 18-A shared predicate; close the gaps. Catches the class so it can't recur a third time. First task = the enumeration (audit-to-confirm; no pre-asserted count, per §5.7).
**Tripwire:** CHARC pass at commissioning (touches multiple write paths + the shared predicate). Sequence AFTER/with 18-A (consumes its predicate).

## Arc 18-C — yfinance call audit [CHARC; deferred Arc-1c]
**Why:** confirmed on disk — NO yfinance-call audit exists (Schwab calls audited via `schwab_api_calls`; yfinance blind). Direct collection observability + feeds both monitors (18-D/18-E read it).
**Scope:** a `yfinance_calls`-style audit (timings, errors, empty-results) paralleling `schwab_api_calls`. **NEW SCHEMA (a table)** — CHARC tripwire; migration discipline (in-file BEGIN/COMMIT #9, backup gate strict-equality, migrate-twice test, #11 mirrors).
**Tripwire:** CHARC pass at commissioning. Sequence BEFORE the monitors that consume it.

## Arc 18-D — Research data-collection health monitor [RD Brief 2; HIGH]
**Brief:** `docs/data-collection-health-monitor-commissioning-brief.md` (architecture-passed; conditions C4-C5).
**Scope:** read-only integrity monitor (the audit mechanized) — temporal-log non-finite scan, excluded-reason breakdown, coverage gaps, orphans/look-ahead, drumbeat liveness. **Build the read-only SCRIPT first; DEFER the nightly pipeline-step half** (C4); if nightly, it MUST use the 17-B `step_guard`. **Emit structured JSON status** (for the 18-F stoplight). Reads the engine manifest (no funnel fork). RD owns the watch-standard amendment post-build.
**Tripwire:** passed (new standing process). RD-lane; RD QAs.

## Arc 18-E — Operational tool-health monitor [operator + CHARC; focused subset]
**Why:** operational signals exist piecemeal (pipeline_runs heartbeat/state, Schwab token TTL, archive/weather freshness, recon backlog, cash-coherence badge) but there's no aggregated early-warning — the same "rode invisibly" failure applies operationally (a dying 7-day token, a silently-failing best-effort step, stale data).
**Scope:** an AGGREGATING read-only roll-up of EXISTING signals — NO new instrumentation, NO new schema — same shape as `harness_probe`/`weekly_glance` (stdlib, ASCII, ATTENTION-on-threshold). **Scoped to the data-collection-ENABLING subset** (pipeline-run health, token TTL, data freshness) — these failing = no data collected, upstream of 18-D. Broader operational coverage (perf, all subsystems) is Phase 19+. **Emit structured JSON status** (for 18-F).
**Tripwire:** CHARC pass at commissioning (new standing process). Operator-facing; build via orchestrator.

## Arc 18-F — GUI health stoplights [operator; web; downstream consumer]
**Scope:** TWO top-row stoplights (green/yellow/red = worst-of each monitor's checks) — **tool-health (18-E)** + **research-measurement (18-D)**; harness-hygiene stays CLI-only (operator decision 2026-06-13). Top row (with date + theme toggle), visible on ALL pages, each clickable to a read-only drill-down page showing which checks flipped.
**Architecture (CHARC-settled, the tripwire content):**
- **The base-layout 500-risk is the load-bearing constraint.** "All pages" = `base.html.j2` → the documented gotcha (a base field missing from any base VM 500s unrelated routes). Bind: a single shared `health_stoplights(conn)` helper called in EVERY base-VM construction with a safe default + a regression test that every base route renders with the stoplights. (Option to weigh in the plan: a base-context consolidation so base-wide fields stop being hand-duplicated across 5 VMs — not mandated.)
- **Data sources differ (reinforces independence):** tool-health computes at render from the DB (like the cash badge — precedent); research reads 18-D's structured artifact. Separate computations.
- **Refresh:** compute-at-render to start; HTMX poll deferred.
- **NO new schema.**
**Tripwire:** CHARC pass (base-layout change). **Operator-witnessed browser gate BINDING** (all-pages HTMX/base-layout — the full web gotcha family; TestClient won't catch a base-VM 500 on an unrelated route). Sequence LAST — depends on 18-D + 18-E emitting structured status.

## Arc 18-H — OPEN bug / small-feature catch-all [operator-added at approval]
Standing container for defects + small features identified WHILE Phase 18 is worked (the 17-D pattern). Each gets its own focused dispatch (TDD; review depth proportional to blast radius — the orchestrator's call; tripwire rules apply as everywhere, so anything crossing §3 still routes through CHARC). Entries accumulate here with commit SHAs so the close audit has one place to look. Empty at open — that's the goal state at close too. (Sub-items registered as 18-H.1, 18-H.2, … as they arrive.)

## Boundary hygiene + riders
- **18-G — broad brief-corpus sweep (D10):** ~246 dead briefs from phases 3e-15 + research lanes beyond the 24 archived at Phase-16 close (departing P16 orchestrator flagged it). `git mv` closed-arc briefs to `docs/archive/phase<N>/`; specs/plans stay. Off-theme but phase-boundary-appropriate + overdue. Operator: include or defer.
- **R1 (D7):** declare `requests` in `[project] dependencies` — fold into the first arc touching pyproject (likely 18-C); fast suite required (inline-edit memory).
- **R2 (D9):** frozen-clock convention line in `orchestrator-context.md` — land with the first Phase-18 brief; pairs with any test-determinism work.
- **Conditional carry — D14** (`-n auto` web-route polluter): carry ONLY if 17-D.4 (in-flight hunt) doesn't fully close it. Don't double-commission; wait for its return.

## Sequencing (CHARC recommendation; operator's call)
Dependency chain: **18-A+18-B** (coupled; shared predicate) · **18-C** (yfinance audit; before the monitors) → **18-D + 18-E** (monitors; emit structured JSON) → **18-F** (stoplights; consume both). 18-G + riders slot anytime. D14 conditional on 17-D.4.
Recommended order: 18-A/18-B → 18-C → 18-D / 18-E (parallel) → 18-F → 18-G. Nothing dispatches until Phase 17 closes + operator go.

## Out of scope (considered, deprioritized)
- The temporal-log backfill (withdrawn — locked above).
- Broader operational-dashboard coverage beyond the data-collection-enabling subset (Phase 19+).
- D1 runner.py infra relocation (navigability, off-theme, downgraded — 17-B took the high-value part).
- D8 (form anchor-ladder) / D12 (latest-eval guard) — trigger-gated watch items; no trigger.
