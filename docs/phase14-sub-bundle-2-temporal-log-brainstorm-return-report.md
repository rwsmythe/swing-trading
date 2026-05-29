# Phase 14 Sub-bundle 2 -- Temporal Pattern Detection + Observation Log Infrastructure -- Brainstorm Return Report

**Phase:** brainstorming (copowers:brainstorming = superpowers:brainstorming + adversarial Codex MCP review).
**Branch:** `phase14-sub-bundle-2-temporal-log-brainstorming` from main `665cab0`.
**Spec:** [`docs/superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md`](superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md).
**Disposition:** Brainstorm SHIPPED on branch; Codex chain CONVERGED at R4 (NO_NEW_CRITICAL_MAJOR). Ready for orchestrator QA + merge + writing-plans dispatch.

---

## 1. Final HEAD + commit breakdown

- **Final HEAD on branch:** `815471a`.
- **Commit count:** 2 (both `docs(phase14-sub-bundle-2-spec):`).

| Commit | Codex attribution | Content |
|---|---|---|
| `3ec8d1b` | pre-Codex draft | Initial spec draft (758 lines); 20 OQs (15 from brief + 5 new code-read findings). |
| `815471a` | R1-R4 converged | All 13 cumulative Codex findings resolved in-place; spec -> 788 lines. |

(Per gotcha #36 + Sec 9.1 Q7: SINGLE Codex chain at brainstorming. The chain ran across 4 rounds; the converged result was committed as one post-chain commit to keep the brainstorm artifact atomic. Writing-plans phase will use its own commit cadence.)

---

## 2. Codex round chain (convergent shape; finding-count taper)

**Transport note:** the copowers Codex MCP server tools (`mcp__plugin_copowers_codex__codex` / `codex-reply`) timed out at the 1s client ceiling on every call (a registration/config issue, NOT a cold-start -- a real review takes minutes). Per the adversarial-critic prerequisite guidance, the Codex review is the core deliverable, so the chain ran via the `codex exec` CLI transport (codex-cli 0.130.0; `-s read-only` round 1, `resume --last` rounds 2-4) -- identical adversarial substance, different transport. The single-chain count + the round structure are unchanged. **Banked forward-binding lesson FB-N1 (§8): copowers Codex MCP tool has a 1s timeout; CLI `codex exec`/`resume` is the working fallback.**

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 2 | 4 | 2 | ISSUES_FOUND |
| R2 | 2 | 1 | 0 | ISSUES_FOUND |
| R3 | 0 | 3 | 2 | ISSUES_FOUND |
| R4 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** |

**Cumulative: 4 CRITICAL + 8 MAJOR + 4 MINOR; ALL 16 resolved in-place; ZERO accepted-as-rationale.** Convergence shape matches Sub-bundle 1 precedent (2-5 rounds). The R2 findings were a textbook cumulative-regression cascade (gotcha #21): the R1 chart-immutability fix (RESTRICT) introduced a run-prune CASCADE deadlock + collided with a previously-undiscovered exemplar writer -- R2 caught both; R3 was pure consistency-sweep lag from the R2 edits (gotcha #31 narrative-fact-lag applied to a spec); R4 clean.

### Codex's strongest catches (all code-grounded)
1. **(R2 C#1)** `theme2_annotated` is ALREADY written by the exemplar cache-miss path (`swing/web/view_models/patterns/exemplars.py:223-321`) -- my "no other writer" premise was false. Resolved: `chart_render_id ON DELETE SET NULL` + standard `refresh_chart_render` (last-writer-wins coexistence).
2. **(R2 C#2)** `chart_render_id RESTRICT` deadlocks `chart_renders.pipeline_run_id ON DELETE CASCADE` (migration `0020:183`) -- a pipeline_run with a detection-referenced chart could never be pruned. Resolved by the SET NULL above.
3. **(R1 C#2 + R2 M#1)** the forward-walk boundary must key on `data_asof_date` (the detector's data cutoff), NOT `detection_date` (= `action_session_date`, a forward-looking not-yet-traded session) -- else the first tradable session's bar is skipped. Resolved: ADDED `data_asof_date` column; `observation_date` = run `data_asof_date`; boundary `detection.data_asof_date < observation_date`.
4. **(R1 M#1)** use the DEDICATED `render_theme2_annotated_svg` (`charts.py:481`), NOT `render_hyprec_detail_svg`. Resolved.
5. **(R1 M#2)** the charts.py annotation path reads STALE evidence keys (`top_of_range`/`depth_ratio`/`pole_advance_pct`) vs actual detector fields (`range_top_price`/`cup_depth_pct`/`pole_pct`) -- evidence-key repair brought IN SCOPE (T-2.4).

---

## 3. Spec line count + per-section breakdown

**Total: 788 lines** (target ~700-1100; matches Sub-bundle 1 brainstorm ~600-725 + extra depth for 2 new tables + new step + chart integration + per-pattern metadata).

| Section | Lines | Section | Lines |
|---|---|---|---|
| §0 Glossary | 15-31 | §8 chart_render capture | 551-583 |
| §1 Architecture overview | 32-98 | §9 Per-pattern metadata (REDESIGN) | 584-615 |
| §2 Pre-locked decisions + L1-L8 | 99-135 | §10 Sub-bundle decomposition | 616-646 |
| §3 Module touch list | 136-160 | §11 Test fixture strategy | 647-682 |
| §4 v22 schema migration | 161-324 | §12 Schema impact | 683-697 |
| §5 Repo layer (append-only) | 325-442 | §13 V1+ simplifications + V2 | 698-715 |
| §6 _step_pattern_detect extension | 443-470 | §14 Open Questions (20) | 716-744 |
| §7 _step_pattern_observe | 471-550 | §15 Cumulative discipline | 745-788 |

---

## 4. Pre-locked operator decisions verbatim verification

| LOCK | Status in spec |
|---|---|
| Sec 9.1 Q1 sequencing (data-wiring -> temporal log THIS -> charts -> review+journal -> metrics) | HONORED (§2.1) |
| Sec 9.1 Q2 SERIAL | HONORED (§2.1) |
| Sec 9.1 Q3 V1+ scope (base + chart_render bytes capture) | HONORED (§1, §8) -- chart capture is V1+ via `theme2_annotated` |
| Sec 9.1 Q6 operator-witnessed gate (incl. v22 verification) | HONORED -- 7 gate surfaces S1-S7 (§10.2) |
| Sec 9.1 Q7 SINGLE Codex chain at brainstorming | HONORED -- 1 chain, 4 rounds |
| L1 append-only on BOTH tables | HONORED (§2.3, §5; repo-layer no update/delete + UNIQUE + RESTRICT FK on observations) |
| L2 forward-walk; #26 + #37 eliminated by construction | HONORED (§1.1, §2.3 NORMATIVE; both gotchas cited explicitly) |
| L3 v22 migration (gotcha #9 + #11 + strict backup-gate pre_version==21) | HONORED (§4) |
| L4 _step_pattern_observe zero-cost | HONORED with audited fetch-scope nuance (§7.2; OQ-17) |
| L5 chart_render bytes capture at detection | HONORED (§8) -- reuses theme2_annotated |
| L6 per-pattern metadata at detect time | HONORED with REDESIGN (§9) -- market_cap finding surfaced |
| L7 _step_pattern_detect EXTENSION not replacement | HONORED (§6; pattern_evaluations coexists) |
| L8 L2 LOCK (zero new Schwab calls) | HONORED (§1.6, §11.4; existing source-grep test cited) |
| Commissioning Sec 2.5 2-table architectural primitive | HONORED + validated against schema (§4); HELD against any consolidation pushback (none raised) |

ZERO LOCKs re-litigated. ZERO scope widening.

---

## 5. Open Questions: resolved + deferred (20 enumerated; brief asked for 15+)

**Resolved at brainstorm (15):** OQ-1 (reuse theme2_annotated), OQ-2 (DAG after detect/before charts), OQ-3 (reuse OhlcvCache), OQ-4 (status machine enumerated), OQ-5 (JSON metadata), OQ-6 (canonicalized finviz_screen_state), OQ-7 (full evidence asdict for anchors), OQ-8 (nullable chart_render_id + audit), OQ-9 (strict backup-gate), OQ-11 (all 5 detectors), OQ-12 (coexist; asymmetric FK), OQ-13 (every A+ detection), OQ-14 (run-warnings accumulator), OQ-15 (§13), OQ-19 (render_theme2_annotated_svg + evidence-key repair).

**Flagged for OPERATOR TRIAGE at executing-plans dispatch (5):**
- **OQ-10** append-only enforcement: repo-layer (RECOMMENDED, matches precedent) vs schema triggers (brief leaned schema-level). Operator confirms.
- **OQ-16** market_cap = NULL in V1+ (NOT persisted to candidates). Confirm acceptable, OR pull market_cap persistence into scope.
- **OQ-17** observe-step fetch scope = open-detection set (a bounded, archive-first, zero-Schwab expansion of the open-trade-only fetch scope, gotcha #5). RECOMMENDED accept.
- **OQ-18** status-machine thresholds: `max_pending_window=30` / `max_post_trigger_window=60` sessions + per-class `structural_invalidation_level` defns; config-surfaced. Confirm (or choose the leaner pure-time V1-- variant).
- **OQ-20** Codex two-chain at WRITING-PLANS (gotcha #36): single-chain defensible (pure infra, no analytical artifact); lean toward two-chain given the append-only v22 substrate permanence + status-machine semantics. Operator decides at writing-plans dispatch.

---

## 6. Codex Major findings ACCEPTED with rationale

**ZERO.** All 4 Critical + 8 Major + 4 Minor were RESOLVED in-place (matches the Sub-bundle 1 "ZERO acceptances strongly preferred" precedent). The R1 RESTRICT resolution was itself superseded by R2 (RESTRICT -> SET NULL) -- a resolution-revised-by-a-later-round, not an acceptance.

---

## 7. V1+ simplifications + V2 candidates banked (spec §13)

11 V1+ simplifications banked with V2 dependencies, incl.: market_cap=NULL (V2: persist Finviz Market Cap to candidates); structural_anchors_json = full evidence asdict (V2: normalized anchor columns); per_pattern_metadata JSON blob (V2: typed columns); status machine ruleset-agnostic subset (Phase 15+ replay engine emits closed_at_target/stop); chart capture via theme2_annotated SET NULL best-effort snapshot (V2: dedicated permanent detection-chart store); repo-layer append-only (V2: SQLite triggers); theme2 renderer evidence-key repair (V2: full annotation parity if deferred); source always 'pipeline' (V2: backfill + V2-cohort ingestion).

---

## 8. Forward-binding lessons for writing-plans dispatch

**NEW (this brainstorm):**
- **FB-N1** copowers Codex MCP server tool times out at 1s; use the `codex exec`/`resume --last` CLI transport (`-s read-only` for round 1; `resume --last -o <file>` for deltas). Same adversarial substance.
- **FB-N2** brief-vs-reality column verification (Expansion #4): the brief's L6 claimed `candidates.market_cap_dollars` + `candidates.atr_pct` -- NEITHER exists (only `sector`/`industry`/`adr_pct`). Writing-plans MUST re-grep every metadata source column before locking the INSERT shape.
- **FB-N3** the `theme2_annotated` surface is SHARED (the exemplar cache-miss path writes it) -- any detection-chart write must coexist last-writer-wins; do NOT assume sole ownership of a chart_renders surface.
- **FB-N4** detection_date (action_session, forward-looking) vs data_asof_date (data cutoff, backward-looking) is a session-anchor-directionality trap (the recurring CLAUDE.md family): the forward-walk boundary + metadata as-of slice + sessions_since_detection ALL key on data_asof_date.
- **FB-N5** the existing `render_theme2_annotated_svg` reads stale evidence keys -- writing-plans verifies which renderer function owns each stale key + scopes the repair.
- **FB-N6** `warnings_json` is currently unused in runner.py -- the run-level warnings accumulator threaded to `lease.release(warnings_json=...)` is NEW plumbing (gotcha #27); writing-plans designs it once for both detect + observe steps.

**INHERITED (13 from Sub-bundle 1; all re-applied):** brief-vs-production-signature verification (re-grep at writing-plans); cumulative regression cascade audit (R2 validated this); schema-CHECK + Python-constant + dataclass-validator paired discipline; migration runner BEGIN/COMMIT; append-only enforcement + discriminating tests; gotcha #27 silent-skip audit; #26+#37 elimination-by-construction; per-pattern metadata sourcing audit (no new fetches); chart_render integration audit; status state machine completeness; backwards-compat with pattern_evaluations; empty-input handling; runtime-binding-shape (dynamic `?` expansion); test-fixture-vs-production-emitter shape parity; L2 LOCK source-grep; ASCII discipline scope; Co-Authored-By suppression.

---

## 9. Sub-bundle decomposition recommendation

**SINGLE writing-plans + executing-plans dispatch** with 6 internal task slices (T-2.1 schema -> T-2.2 models+repos -> T-2.3 detect extension -> T-2.4 chart capture + evidence-key repair -> T-2.5 observe step -> T-2.6 closer). The slices cohere around the v22 substrate. **Alternative (operator option):** split into 2 executing-plans dispatches (substrate then behavior). Estimated ~15-25 commits + ~50-100 tests (commissioning Sec 2.5 estimate).

---

## 10. Schema impact verdict

**Schema v22; single migration `0022_phase14_temporal_log.sql`.** 2 NEW tables (pattern_detection_events: 12 cols incl. data_asof_date + 4 indexes; pattern_forward_observations: 8 cols + 3 indexes). NO chart_renders CHECK widening (reuses theme2_annotated). `EXPECTED_SCHEMA_VERSION` 21 -> 22. NEW `_phase14_backup_gate` STRICT `current_version == 21`; `PHASE14_PRE_MIGRATION_EXPECTED_TABLES = PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` (v21 added no tables). gotcha #9 explicit BEGIN/COMMIT + final schema_version bump; gotcha #11 paired CHECK + constants + `__post_init__`. No migration beyond v22.

---

## 11. Cumulative gotcha set application summary

Matrix at spec §15.1. Highlights: #9 (migration runner), #11 (paired discipline + read-path mappers), strict backup-gate, sqlite3 list-bind (dynamic `?`), date.fromisoformat boundary, **#26 + #37 ELIMINATED BY CONSTRUCTION** (hardened per R2 M#1 + R1 M#3 bar-anchoring), #27 (3 audit sites: detect empty-pool + observe empty-pool/no-bar + chart-render-failure), #5 (observe fetch-scope audited), #32 (ASCII scope declared), #36 (single chain; writing-plans evaluated at OQ-20). Append-only precedent (`watchlist_close_track_flag_events`, `pattern_evaluations`, `reconciliation_corrections`) MIRRORED.

---

## 12. Worktree teardown status

Worktree `.worktrees/phase14-sub-bundle-2-temporal-log-brainstorming/` RETAINED (orchestrator owns merge per project convention). `git status` clean; all `.copowers-review-*` + round temp files deleted; session-state JSON written to `$TMPDIR/.copowers-session-acd291c3ae89.json`. 2 commits on branch, both pushed-ready.

---

## 13. ZERO Co-Authored-By footer drift confirmation

`git log --pretty="%(trailers)" main..HEAD` emits ZERO `Co-Authored-By:` lines across both branch commits. Streak preserved (~611+ cumulative). No `--no-verify` used.

---

## 14. CLAUDE.md status-line refresh draft text

> **Sub-bundle 2 (temporal pattern detection + observation log infrastructure; V1+; v22 schema) BRAINSTORM SHIPPED** at branch `phase14-sub-bundle-2-temporal-log-brainstorming` HEAD `815471a` -- spec at `docs/superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md` (788 lines). Single Codex MCP chain CONVERGED at R4 (4 rounds; 4C+8M+4m cumulative ALL resolved in-place; ZERO acceptances) -- Codex caught the chart_render immutability-vs-cache-refresh + CASCADE-deadlock + shared-exemplar-surface tangle (resolved to chart_render_id ON DELETE SET NULL, nullable audit linkage) + the data_asof_date-vs-detection_date forward-walk boundary trap (ADDED data_asof_date column) + the dedicated render_theme2_annotated_svg renderer + stale-evidence-key repair. 2 NEW append-only tables eliminate gotchas #26 + #37 BY CONSTRUCTION (forward-walk; no archive re-read; no regeneration). Schema v22 (strict backup-gate pre_version==21); L1-L8 + Sec 9.1 Q1-Q7 LOCKs honored; L2 LOCK preserved; brief-vs-reality finding banked (market_cap + true ATR NOT in candidates). 20 OQs (5 for operator triage: OQ-10 trigger-vs-repo enforcement, OQ-16 market_cap=NULL, OQ-17 observe fetch-scope, OQ-18 status-machine thresholds, OQ-20 writing-plans two-chain). NEXT: orchestrator QA + merge + writing-plans dispatch.

(Codex transport note for orchestrator: the copowers Codex MCP tool timed out at 1s; the chain ran via `codex exec` CLI -- banked as FB-N1.)

---

## 15. Writing-plans dispatch-readiness summary

**READY** for orchestrator QA -> merge -> writing-plans dispatch, contingent on operator triage of the 5 flagged OQs (10, 16, 17, 18, 20). The spec is internally consistent (R3/R4 swept all date-anchor + chart-FK references), code-grounded (every cited signature/line verified against production at brainstorm; re-grep at writing-plans per FB-N2), and scoped (Schema v22; 2 tables; no widening). Writing-plans should: (a) re-verify all production signatures (`render_theme2_annotated_svg`, `refresh_chart_render`, `lease_data_asof`, `insert_evaluation`, the evidence dataclass anchor fields, the CriterionResult shape); (b) lock the per-pattern metadata INSERT shape after confirming OQ-16; (c) design the run-warnings accumulator plumbing (FB-N6); (d) decide single vs two Codex chains (OQ-20). Recommend the operator-paired OQ triage happen at the writing-plans dispatch brief (not blocking the merge of this brainstorm spec).
