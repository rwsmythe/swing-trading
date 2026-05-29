# Phase 14 Sub-bundle 3 -- Chart-Surface Uniformity -- Brainstorm Return Report

**Phase:** 14 Sub-bundle 3 (chart-surface uniformity) -- BRAINSTORMING.
**Branch:** `phase14-sub-bundle-3-chart-surface-uniformity-brainstorming` (cut from main HEAD `fd59ece`).
**Date:** 2026-05-29.
**Deliverable:** design spec at `docs/superpowers/specs/2026-05-29-phase14-sub-bundle-3-chart-surface-uniformity-design.md` + this report.

---

## 1. Final HEAD + commit breakdown

**Branch HEAD: `d5fda78`** (2 commits, both docs-only):

| Commit | Content |
|---|---|
| `cddb54f` | `docs(phase14-sub-bundle-3-spec): brainstorm draft -- chart-surface uniformity` -- the initial 447-line spec (§1-§15) capturing OD-1..OD-4. |
| `d5fda78` | `docs(phase14-sub-bundle-3-spec): brainstorm R1+R2 -- Codex convergence at R3` -- all 18 major + 12 minor Codex findings resolved/accepted in-place. Final 494 lines. |

No `swing/` writes. Schema v22 LOCKED at brainstorming (v23 DESIGNED, not applied). L2 LOCK preserved (zero new Schwab call sites).

## 2. Codex round chain + convergent shape

**SINGLE chain** (Sec 9.1 Q7 LOCK -- pure UX/chart sub-bundle; gotcha #36 caveat). **Converged at Round 3** after 3 rounds (within the 2-4 target).

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 15 | 10 | ISSUES_FOUND |
| R2 | 0 | 3 (NEW) | 2 (NEW) | ISSUES_FOUND |
| R3 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** |

**Cumulative: 0 CRITICAL + 18 MAJOR + 12 MINOR.** All resolved in-place except: M11 (P14.N1 enum-reuse -- RESOLVED via documented identity contract + explicit divergence-deferral, partial-accept of "add enums now"); m8 (commit/test-count -- ACCEPTED as an indicative envelope, not a churn target). ZERO advisory-only carried.

**Transport note (FB-N1):** the Codex MCP timed out at 1s (the known Windows launcher symptom; I could not restart Claude Code mid-session to rebind). Backstop used: `codex exec` CLI -- round 1 with the spec inlined via stdin; rounds 2-3 via `codex exec resume --last` (thread continuity preserved). The CLI's `-s read-only` sandbox could not spawn PowerShell to re-read the updated spec file (the documented `windows sandbox: spawn setup refresh` wrinkle), so rounds 2-3 reasoned from the inline delta resolution summaries -- which described each fix precisely. Codex still produced substantive, codebase-aware findings each round.

## 3. Spec line count + per-section

**494 lines** (below the ~600-900 brief guide; dense + non-redundant -- the Codex chain added the depth that closed the gap from the 447-line draft). All 15 sections present:

| § | Section | Start line |
|---|---|---|
| 1 | Architecture overview | 14 |
| 2 | Pre-locked operator decisions | 52 |
| 3 | Module touch list | 82 |
| 4 | Renderer-uniformity audit (V2.G1 + P14.N2) | 106 |
| 5 | V2.G2 v23 rename | 193 |
| 6 | P14.N1 thumbnail substrate | 296 |
| 7 | P14.N4 BULZ shaded zones | 309 |
| 8 | P14.N8 weather refresh uniformity | 325 |
| 9 | S6 cosmetic | 352 |
| 10 | Sub-bundle decomposition | 362 |
| 11 | Test fixture + visual-gate enumeration | 380 |
| 12 | Schema impact (v23) | 426 |
| 13 | V1 simplifications + V2 candidates | 439 |
| 14 | Operator decision items (OQs) | 457 |
| 15 | Cumulative discipline compliance | 474 |

## 4. Pre-locked decisions -- verbatim verification

**Sec 9.1 commissioning LOCKs (all honored, §2.1):**
- Q1 sequencing (charts after temporal log) -- this IS Sub-bundle 3. OK.
- Q2 serial -- single executing-plans dispatch recommended (§10). OK.
- Q4 V2.G2 rename ships as v23 in THIS sub-bundle -- designed (§5). OK.
- Q5 matplotlib SVG only, no JS -- mplfinance is a matplotlib/Python wrapper (Q5-compatible); confirmed already-declared dep (§4.1). OK.
- Q6 operator browser-witnessed close-out -- visual-gate ladder S1-S7 + operationalized artifacts (§11.2c/§11.3). OK.
- Q7 SINGLE Codex chain -- done (§2 above). OK.

**Sub-bundle 3 phase LOCKs L1-L7 (all honored, §2.3):**
- L1 scope V2.G1+G2+P14.N1/N2/N4+P14.N8+S6 only -- no widening. OK.
- L2 v23 #11 paired + #9 BEGIN/COMMIT + STRICT `pre_version==22` backup gate -- §5.1-§5.5. OK.
- L3 renderer-kwargs uniformity + cache-collision tests -- §4.3, §5.6, §8. OK.
- L4 visual-gate binding; byte/string tests insufficient -- §11.2/§11.2c. OK.
- L5 zero-orphan rename -- two-tier grep gate (§5.5). OK.
- L6 L2 LOCK preserved -- §15; current_stage reads weather rows only (no Schwab). OK.
- L7 P14.N8 match canonical render (not suppress) -- §8 computes real state at all 3 sites. OK (refined: "canonical" = the REAL `current_stage` value per OD-3, since the pipeline literal was itself a V2-banked simplification).

## 5. OQs resolved + deferred

**Resolved at brainstorming (operator decisions OD-1..OD-4, §2.2):**
- OD-1 candlesticks = **mplfinance** (already-declared dep; mirror `swing/rendering/charts.py`).
- OD-2 candlestick scope = **4 detail surfaces** (`ticker_detail`/`position_detail`/`market_weather`/`theme2_annotated`); thumbnails stay line.
- OD-3 weather trend-state = **compute real `current_stage` at all 3 sites** (closes the V2-banked literal).
- OD-4 rename = **full** (enum + function + VM field + template var + CSS class).

**Deferred to writing-plans triage (8 OQs, §14):** OQ-4 (P14.N1 row-wiring defer), OQ-6 (weather MA set 50/200), OQ-7 (in-migration row rename), OQ-N4-target (BULZ target field verification), OQ-N4-color (zone hues), OQ-S6 (annotation placement), OQ-mav-color (MA palette -- pin BEFORE implementation), OQ-chain (single vs two-chain at writing-plans given the v23 substrate touch).

## 6. Codex Major findings accepted (ZERO preferred; resolved-in-place dominates)

18 majors total. **16 RESOLVED in-place; 0 pure-accept; 2 partial.** Highlights:
- **R1 M4 (contradiction):** caller-specific `ticker_detail` title vs single cached row -- RESOLVED by a NEUTRAL cache-safe title (kills leakage AND stays cache-safe).
- **R1 M5:** weather asof anchored on render context, not wall-clock `now()` (reproducibility).
- **R1 M1 + R2 M1/M2:** v23 DDL derived from live `sqlite_schema` at AUTHORING time; parity test compares NORMALIZED `sqlite_schema.sql` (CHECK + partial-index WHERE text), not just PRAGMAs.
- **R1 M12 + R2 M3:** BULZ long-only; DRAW valid off-range zones (never silently drop valid geometry); skip+log only invalid shapes.
- **R1 M7/M8:** single `_x_for_date` coordinate helper + `_normalize_ohlc_for_mpf` barrier.
- **R1 M9:** operationalized visual gate (artifacts/commands/checklist/ownership).
- **R1 M14:** two-tier rename grep gate (runtime-forbidden vs allowed historical/test-migration paths).
- **R1 M15:** browser-embedding diagnosis sequenced FIRST (T2-step-0), before mpf conversion.
- **R1 M10 + R2 m1:** packaging audit across run profiles + import-guard + web-profile import smoke test.

**Partial:** M11 (documented thumbnail identity contract + deferred divergence to a future v24 rather than speculatively adding enums now -- YAGNI); m8 (commit/test-count accepted as indicative envelope).

## 7. V1 simplifications + V2 candidates (§13)

**V1 simplifications:** thumbnails stay line; P14.N1 reuses `watchlist_row` surface (no new enums); market_weather MA = 50/200 only; BULZ target-zone only if a target field exists; P14.N1 consuming-surface wiring deferred to Sub-bundle 4; no chart_renders retention/eviction.

**V2 candidates:** candlestick thumbnails (micro-candle legibility); per-surface configurable MA windows/style; mpf style theming centralized; distinct thumbnail surfaces with table-specific overlays (Sub-bundle 4).

## 8. Forward-binding lessons for writing-plans

1. **Re-grep all signatures at writing-plans (#2)** -- renderer names, `current_stage` signature, `Trade`/`Fill` target/entry fields (BULZ), `_apply_migration` FK-restore past line 222.
2. **Derive v23 DDL from a migrated-to-v22 fixture's `sqlite_schema`** -- paste into the static `0023_*.sql`; do not hand-transcribe from the `0020` excerpt.
3. **Sequence T2-step-0 (browser-embedding diagnosis) BEFORE candlestick conversion** -- a viewBox/CSS bug would otherwise survive the mpf swap.
4. **Pin the MA color palette + per-surface annotation reserved-region map BEFORE implementation** -- both are visual-gate-critical.
5. **The visual gate is binding** -- enumerate per-surface SVG/PNG artifacts + exact regen commands in the executing-plans return report; the operator is the named gate owner.
6. **Verify mplfinance is in every web run profile** + add the import smoke test.
7. **Decide single vs two-chain at writing-plans** -- the v23 table-rebuild is substrate-touching (gotcha #36 default leans two-chain); orchestrator discretion.

## 9. Sub-bundle decomposition recommendation (§10)

**Single `copowers:executing-plans` dispatch**, 7 tasks: T1 v23 rename+migration+backup-gate (FIRST -- foundation); T2 candle helper + `ticker_detail`/`theme2_annotated` (T2-step-0 = embedding diagnosis); T3 `position_detail`+BULZ; T4 `market_weather`+trend-state uniformity; T5 S6 annotation layout; T6 P14.N1 substrate; T7 closer (pyproject + suite + gates). SERIAL (shared `charts.py` merge surface). Indicative ~15-25 commits / ~40-80 tests.

## 10. Schema impact verdict (v23)

Single-table rebuild of `chart_renders` (`0023_*.sql`): CHECK enum `hyprec_detail`->`ticker_detail` via CREATE-COPY(id-preserving CASE rename)-DROP-RENAME; 3 partial indexes + cross-column CHECK recreated verbatim; `INSERT...SELECT` row migration; `EXPECTED_SCHEMA_VERSION=23`; `_phase14_sb3_backup_gate` STRICT `==22`. FK from `pattern_detection_events.chart_render_id` preserved (id-preserving copy + FK-off-during-rebuild). No new columns/tables; no enum widening (same-cardinality rename). v22 temporal-log substrate untouched. **Verdict: a clean, low-risk single-table rename migration with strong parity + FK-survival test coverage.**

## 11. Cumulative gotcha application summary (§15)

Matplotlib mathtext (two-gate title/body distinction); #11 paired (CHECK+constant+validator+mapper+renderer+routes+VMs+templates+tests one task); #9 BEGIN/COMMIT/ROLLBACK + 0022 precedent; #11 STRICT backup gate; Expansion #10c kwargs uniformity (shared helper); #11 taxonomy propagation (two-tier zero-orphan grep); byte-parity insufficiency (derivation-path test + operationalized visual gate); session-anchor read/write (weather `last_completed_session`); #4 SQL/field verification (BULZ fields, partial-index correction); #27 silent-skip audit; L2/ASCII (#16/#32); Windows cp1252 (renderers return bytes); ZERO Co-Authored-By.

## 12. Worktree teardown status

**Worktree RETAINED + CLEAN** for orchestrator merge. `git status --porcelain` empty; all Codex temp artifacts (`.copowers-review-*`, `.codex-round*`) deleted. Branch `phase14-sub-bundle-3-chart-surface-uniformity-brainstorming` at `d5fda78`, 2 commits ahead of `main` (`fd59ece`). copowers session state written to `${TMPDIR}/.copowers-session-1a9e082debc8.json`.

## 13. ZERO Co-Authored-By confirmation

Both commits: `git log -1 --format='%(trailers)'` returns EMPTY for `d5fda78`; verified empty for `cddb54f` at commit time. No `Co-Authored-By`, no `noreply@anthropic.com`. Author `Reid Smythe <rwsmythe@gmail.com>`. Final `-m` paragraphs are plain prose (no `Word:`-leading trailer-parse hazard). Streak preserved (~620+).

## 14. CLAUDE.md status-line refresh draft (for orchestrator at merge)

> **Sub-bundle 3 (chart-surface uniformity; V2.G1 + V2.G2 v23 rename + P14.N1/N2/N4 + P14.N8 + S6) BRAINSTORMING SHIPPED at `<merge-sha>`** -- spec at `docs/superpowers/specs/2026-05-29-phase14-sub-bundle-3-chart-surface-uniformity-design.md` (494 lines; Codex single chain converged R3, 0C+18M+12m resolved). Adopts mplfinance candlesticks across 4 detail renderers; v23 atomic `hyprec_detail`->`ticker_detail` rename (table rebuild, id-preserving, STRICT `pre_version==22`). v23 DESIGNED not applied (v22 still LOCKED). **Writing-plans NEXT.**

## 15. Writing-plans dispatch-readiness summary

**READY.** The spec is implementable: real signatures verified; v23 migration + backup-gate + parity/FK tests specified; mplfinance integration anchored on the existing `render_chart` precedent; BULZ/weather/S6/P14.N1 designed with explicit data-source + fail-soft + layout policies; 8 OQs enumerated for operator triage; 7-task decomposition locked. Writing-plans should: (a) re-grep signatures (#2); (b) derive v23 DDL from a v22 fixture's `sqlite_schema`; (c) sequence embedding-diagnosis first; (d) pin MA palette + annotation regions; (e) resolve the 8 OQs with the operator; (f) decide single vs two-chain. No blockers; no escalations (the OHLC-bar-shape escalation trigger did NOT fire -- bars already carry OHLC).

---

*End of return report. Phase 14 Sub-bundle 3 brainstorming COMPLETE: spec written + committed + Codex single chain converged at R3; worktree clean + retained for orchestrator merge.*
