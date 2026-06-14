# Phase 18 Arc 18-B — OHLC write-path finiteness audit & consolidation (commissioning brief)

**Authored:** 2026-06-14 by CHARC. **Register/roadmap:** D-family (#24–#26 two-path-divergence); `docs/phase18-todo.md` §18-B. **Tripwire:** satisfied by construction (CHARC-authored — the §3 architecture pass IS this brief; touches multiple OHLC write paths + the 18-A shared predicate). Route back to CHARC only on a schema need / new dependency / a §3 departure discovered in the audit.
**Cycle:** writing-plans → executing (NO brainstorm — the approach is settled: extend the 18-A shared predicate's coverage). Codex to convergence at each phase; persist responses.
**>>> PILOT: the writing-plans phase runs as the sub-agent-dispatch PILOT (operator-concurred 2026-06-14) — `run_in_background`, under CHARC architecture-pass conditions C-a..C-e (`docs/orchestrator-subagent-dispatch-charc-architecture-pass.md`). See §Pilot. <<<**

## 1. Mandate
18-A fixed ONE instance of a recurring class: Arc-8 guarded `ohlcv_archive`, the temporal-log writer was missed (the #24–#26 family), and 18-A closed it with a shared predicate. **18-B catches the CLASS:** enumerate EVERY OHLC-bar persistence-write boundary, verify each enforces finiteness via the **18-A shared `swing/data/ohlcv_finiteness.py:is_finite_ohlc`**, and close genuine gaps — so a third path can't silently diverge.

## 2. Scope boundary (READ THIS — it prevents the audit from ballooning)
- **IN scope:** boundaries that **WRITE an OHLC bar into a persisted store the pipeline/measurement consumes** (e.g. the OHLCV archive parquet, the temporal log `ohlc_today_json`, `candidates` price columns, `pattern_forward_observations` rows).
- **OUT of scope:** **read/compute paths.** The `swing/evaluation/criteria/*` files (and similar) *consume* OHLC to compute criteria — they do NOT persist bars. They are NOT 18-B targets. Do not guard them.
- **A path may legitimately NOT need a guard** — e.g. it's read-only, or a downstream `validate_bars` already rejects non-finite for that store, or the value never reaches the measurement. **Document that finding** (path → classification → why) rather than blanket-guarding. The deliverable is *correct coverage of the divergence class*, not "is_finite_ohlc sprinkled everywhere."

## 3. First task = the EXHAUSTIVE enumeration (audit-to-confirm; §5.7 — no pre-asserted count)
Enumerate every OHLC persistence-write boundary in `swing/` and classify each:
- **GUARDED** (already routes through `is_finite_ohlc` — archive trim + temporal-log writer/caller, from 18-A), or
- **GAP** (writes OHLC to a measurement-consumed store with NO finiteness enforcement — close it via the shared predicate), or
- **OUT** (read/compute, or downstream-caught, or non-measurement — document why).

**Starting anchors (NOT the final list — enumerate exhaustively):** `ohlcv_archive.py` (GUARDED), `temporal_metadata.py` + `runner.py` caller (GUARDED), `repos/candidates.py`, `repos/pattern_forward_observations.py`, `integrations/schwab/marketdata_ladder.py`, `pipeline/ohlcv.py`, `tools/migrate_prices_cache.py`. Confirm/extend by grep; the enumeration + classification table is the writing-plans deliverable.

## 4. Closing a gap (the C1 discipline — non-negotiable)
Any genuine gap closes by routing through the **ONE shared `is_finite_ohlc` predicate** — NO new finiteness copies (a third copy is the exact divergence this arc exists to kill). Import direction strictly **pipeline → data** (the verified-healthy layer rule; `swing/data` never imports `swing/pipeline`). Match 18-A's semantics: `math.isfinite`, OHLC-only, volume-exempt, finiteness-only (no `>=0` — that stays `validate_bars`' job).

## 5. LOCKS
1. **`validate_bars` untouched** (the engine's honest-rejection belt stays; LOCK 1 from 18-A).
2. **Writer↔engine finiteness PARITY preserved** — every gap-closure uses the shared predicate, so all write paths reject EXACTLY the engine's finiteness set; no path may diverge.
3. **NO schema.** This is an audit + guard insertions. If the audit finds a gap that *requires* a migration to close, **STOP and route to CHARC** (it crosses the schema tripwire) — do not improvise one.
4. **Interior-bar posture unchanged** (Phase-15 bad-bar-accept for HISTORICAL interior bars; this guards non-finite at write boundaries, per 18-A LOCK 4).
5. Each gap-closure carries a discriminating test (real-shape non-finite → rejected/skipped; valid → recorded; the regression-arithmetic-both-ways discipline).

## 6. Pilot (sub-agent dispatch — writing-plans phase only)
The 18-B **writing-plans** phase is the first run of the orchestrator-spawned-implementer model (operator-concurred; my pass `3f6311b6`). Conditions that bind it:
- **Sub-agent via the Agent tool, `run_in_background`** so the operator can watch in flight (the visibility mitigant).
- **C-b:** the sub-agent creates/uses `.worktrees/<name>` — NO Agent `isolation: worktree`.
- **C-c:** if the writing-plans phase runs Codex, the dispatch enforces round/persist/converge and the orchestrator verifies convergence from the REAL `.copowers-findings.md` at QA — never the sub-agent's claim.
- **C-d:** the orchestrator owns failure handling (null-result / WSL-Codex-unreachable / stall-timeout → recover or escalate).
- **C-e:** the orchestrator sets the sub-agent's model/effort on the Agent call (writing-plans + measurement-chain + gate-blocked → Opus high–xhigh per the convention), **announced in chat + vetoable before spawn.**
- Writing-plans is plan-only (low stakes) — the right pilot. **Executing-plans is NOT yet cleared for sub-agent dispatch** (C-a: prove the writing-plans pilot first); 18-B executing is a separate go.

## 7. Gate (18-B is measurement-core — RD stays up)
Three-eye MERGE gate at executing/merge: orchestrator QA-against-disk + CHARC (C1/parity/scope + the enumeration is genuinely exhaustive) + **RD measurement-integrity (MERGE-BLOCKING** — the write paths feed the instrument). The writing-plans pilot is plan-only; the full gate binds at executing. No-false-green merged-head re-run + ruff by the orchestrator before close.

## 8. Return report
The ORCHESTRATOR posts to `charc, rd, operator` (`--type return_report`) AFTER its QA (the implementer/sub-agent reports to the orchestrator, never a director inbox). Itemize: the enumeration+classification table, gap-closures via the shared predicate (C1), parity preserved, scope honored (no read/compute paths guarded), locks, Codex rounds + verdict, and — for the pilot — how the sub-agent dispatch went (Codex-gate handling, failure modes hit, the model/effort used).
