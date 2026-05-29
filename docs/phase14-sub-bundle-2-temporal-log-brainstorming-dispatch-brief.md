# Phase 14 Sub-bundle 2 -- Temporal Pattern Detection + Observation Log Infrastructure -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 2 brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for the **temporal pattern detection + observation log infrastructure** — the V1+ scope LOCKed at Sec 9.1 Q3 (base substrate + chart_render bytes capture at detection). This is **the highest-leverage methodological improvement** surfaced at the close of the applied research arc per Turn H 2026-05-27 PM #3; it eliminates gotchas #26 (OHLCV archive bar-content TEMPORAL mutation) + #37 (substrate-freshness sensitivity) by architectural construction (append-only forward-walk semantics). Sub-bundle 2 is the **largest-leverage substrate** Phase 14 ships.

**Brief:** `docs/phase14-sub-bundle-2-temporal-log-brainstorming-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; **Sub-bundle 1 SHIPPED end-to-end at `e323339` 2026-05-29** (V2.G3 + V2.G4 + P14.N3 production code + tests; operator-witnessed gate PASS); housekeeping at `a730a05`. Main HEAD at Sub-bundle 2 brainstorming dispatch: `a730a05`.

**Cumulative discipline at dispatch:** 37 CLAUDE.md gotchas BINDING; ~609+ cumulative ZERO Co-Authored-By trailer drift; 47th cumulative C.C lesson #6 validation NOTABLE at Sub-bundle 1 executing-plans SHIPPED; Schema v21 LOCKED baseline — **Sub-bundle 2 expected to introduce v22 schema migration** (gotcha #11 + #9 + #11-paired-discipline apply; backup-gate equality form per gotcha #11 LOCK applies); L2 LOCK preserved through Sub-bundle 1 (multiset Counter source-grep test at `tests/integration/test_l2_lock_source_grep.py` asserts HEAD multiset SUBSET of `bf7e071` baseline).

**Expected duration:** ~3-5 hours brainstorming + 2-5 Codex rounds. Sub-bundle 2 is the largest substrate-changing sub-bundle Phase 14 ships; spec line target **~700-1100 lines** (matches Sub-bundle 1 brainstorm at ~810 lines + extra depth for new tables + new pipeline step + chart_render integration coupling + per-pattern metadata enrichment).

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- `copowers:brainstorming` wraps `superpowers:brainstorming` with adversarial Codex MCP review after the spec is written.
- Codex chain count: **SINGLE chain at end** for the brainstorming phase per Sec 9.1 Q7 LOCK (orchestrator discretion); reconsider at writing-plans phase if brainstorm surfaces methodologically-substantive dimensions warranting the gotcha #36 two-chain default.
- Output: design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-2-temporal-log-design.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/phase14-commissioning-brief.md`** Sec 2.5 — architectural primitive enumeration for temporal log infrastructure (table shapes + properties + daily pipeline integration). Also Sec 9.1 LOCKs (especially Q3 V1+ scope LOCK + Q7 Codex chain count + Q1 sequencing).

3. **`docs/phase3e-todo.md`** — Phase 14 preliminary scope roll-up + Sub-bundle 1 SHIPPED top entry (substantive context on cumulative discipline + 13 forward-binding lessons applied at Sub-bundle 1).

4. **CLAUDE.md** (all 37 cumulative gotchas) — especially:
   - **#26 (OHLCV archive bar-content TEMPORAL mutation)** — temporal log eliminates by construction (no archive re-read; forward-walk observation log captures bars at observation time)
   - **#27 (silent-skip-without-audit)** — pattern_detection_events MUST emit audit on empty-pool / early-return paths
   - **#37 (substrate-freshness sensitivity)** — temporal log eliminates by construction (append-only; no regeneration)
   - **#11 (Schema-CHECK + Python-constant + dataclass-validator paired discipline)** — v22 schema migration MUST land all three layers in same task
   - **#9 (executescript implicit COMMIT)** — migration runner discipline
   - **#36 (two-Codex-chain default for analytical sub-bundles)** — sub-bundle 2 substrate-changing; consider for writing-plans phase
   - **Other gotchas relevant to schema/migration work**: #25 sentinel-bucket parity discipline (does NOT apply; temporal log is forward-walk not parity comparison); #24 cross-archive desync (does NOT apply; observation log is own substrate)

5. **`docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md`** (Sub-bundle 1 brainstorm spec) — REFERENCE for spec shape + Codex catch documentation precedent + per-section flow.

6. **`docs/phase14-sub-bundle-1-data-wiring-brainstorm-return-report.md`** + **`docs/phase14-sub-bundle-1-data-wiring-writing-plans-return-report.md`** + **`docs/phase14-sub-bundle-1-data-wiring-executing-plans-return-report.md`** — 13 cumulative forward-binding lessons (load-bearing for Sub-bundle 2 from §M of writing-plans plan).

7. **`docs/orchestrator-context.md`** §"Currently in-flight work" — Phase 14 in-flight; Sub-bundle 2 next.

8. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_orchestrator_qa_implementer_product` (informational)
   - `project_applied_research_arc_2026-05-27` (substantive context on WHY temporal log = operator-stated forward path)
   - `feedback_verify_regression_test_arithmetic` (relevant for the new pipeline step + observation log status state machine)

9. **Existing production code surfaces** to read BEFORE drafting (architectural anchors):
   - `swing/data/migrations/0021_*.sql` (most recent migration; template for v22)
   - `swing/data/db.py` migration runner (gotcha #9 explicit `BEGIN`/`COMMIT`/`ROLLBACK` discipline)
   - `swing/pipeline/runner.py:_step_pattern_detect` (Phase 13 existing detector; the EXTEND target for `pattern_detection_events` write path)
   - `swing/pipeline/runner.py:_step_*` (existing pipeline-step pattern; the NEW `_step_pattern_observe` mirrors these)
   - `swing/data/models.py` (dataclass patterns for new tables)
   - `swing/data/repos/` (repo patterns)
   - `swing/web/chart_jit.py` + `swing/data/repos/chart_renders.py` (chart_render integration for V1+ chart bytes capture LOCK per Sec 9.1 Q3)
   - `swing/web/chart_scope.py` (chart_render surface enum extension point if NEW surface needed)

10. **G2 + V2-selection-mechanic + R2-A + R2-D applied research artifacts** for substantive context on WHY the temporal log substrate enables future investigations: `research/studies/2026-05-27-applied-research-arc-closure.md` Sec 6 (9-metric scorecard methodological contribution) + Sec 7 (future-revisit predicates).

---

## §1 Pre-locked operator decisions (DO NOT re-litigate)

### §1.1 Sec 9.1 LOCKs (commissioning-time; binding for all Phase 14 sub-bundles)

- **Q1** sequencing = data-wiring (SHIPPED) -> **temporal log V1+ (THIS SUB-BUNDLE)** -> charts -> review+journal -> metrics
- **Q2** execution = SERIAL
- **Q3** temporal log V1 scope = **V1+** -- base 2 tables + `_step_pattern_observe` pipeline step + per-pattern metadata enrichment at detection PLUS **chart_render bytes capture at detection time** (closes CR.1 dependency cleanly)
- **Q6** close-out = all 5 sub-bundles merged + operator browser-witnessed verification at each merge
- **Q7** Codex chain count = orchestrator discretion per sub-bundle; **SINGLE chain at end** for THIS brainstorming phase; revisit at writing-plans phase if analytical-substrate-changing dimensions warrant gotcha #36 two-chain default

### §1.2 Architectural primitive LOCKed per commissioning brief Sec 2.5

The two append-only tables are LOCKed as the V1+ substrate shape (operator-approved at Sec 9.1 Q3):

```
pattern_detection_events
  detection_id PK (INTEGER)
  ticker TEXT NOT NULL
  detection_date TEXT NOT NULL          -- (= asof_date at which the pattern was identified)
  pattern_class TEXT NOT NULL           -- (double_bottom_w / cup_with_handle / vcp / flat_base / high_tight_flag / etc.)
  structural_anchors_json TEXT NOT NULL -- LOCKED at detection (trough_1_date, center_peak_date, prior_high_date, etc.)
  composite_score REAL NOT NULL         -- LOCKED at detection
  finviz_screen_state TEXT              -- which Finviz criteria the ticker passed at detection (JSON; nullable for non-pipeline sources)
  source TEXT NOT NULL                  -- ('pipeline' / 'V2_cohort' / 'D2_baseline' / etc.; CHECK enum)
  per_pattern_metadata_json TEXT NOT NULL -- LOCKED (sector / industry / market_cap / ATR_pct / 90d_return / 52w_prox at detection)
  pipeline_run_id INTEGER               -- FK to pipeline_runs (nullable if source != 'pipeline')
  created_at TEXT NOT NULL              -- INSERT timestamp
  chart_render_id INTEGER               -- FK to chart_renders (V1+ chart bytes capture LOCK per Sec 9.1 Q3; nullable if render failed)

pattern_forward_observations
  observation_id PK (INTEGER)
  detection_id INTEGER NOT NULL         -- FK to pattern_detection_events; ON DELETE RESTRICT (append-only invariant)
  observation_date TEXT NOT NULL
  ohlc_today_json TEXT NOT NULL         -- LOCKED at observation; never re-fetched
  status TEXT NOT NULL                  -- CHECK ('pending' / 'triggered_open' / 'triggered_closed_at_target' / 'triggered_closed_at_stop' / 'invalidated' / 'expired')
  status_change_event TEXT              -- ('entry_fired' / 'stop_fired' / 'target_fired' / 'time_exit' / etc.; nullable if status == 'pending')
  created_at TEXT NOT NULL
  UNIQUE (detection_id, observation_date)
```

The spec MUST validate this primitive against the existing schema landscape + adjust per Codex review BUT MAY NOT re-litigate the V1+ scope (Q3 LOCK).

### §1.3 Sub-bundle 2 phase-specific LOCKs (this brief)

- **L1** Append-only invariant on BOTH tables (no UPDATE; no DELETE; INSERT-only). Repo layer MUST enforce; CHECK constraints + repo discipline mirror.
- **L2** Forward-walk semantic ONLY -- gotchas #26 + #37 ELIMINATED BY CONSTRUCTION (no archive re-read; no regeneration). Spec MUST state this invariant explicitly + cite both gotchas.
- **L3** v22 schema migration -- gotcha #11 paired-discipline (CHECK + Python constant + dataclass validator) applies; gotcha #9 explicit-BEGIN/COMMIT/ROLLBACK applies; backup-gate equality form `pre_version == 21` strict per existing CLAUDE.md gotcha.
- **L4** `_step_pattern_observe` pipeline step is **zero-cost beyond existing detector invocations** per commissioning brief Sec 2.5 -- the spec MUST design it so observation enumeration reads only the (detection_id WHERE status IN open states) set + appends today's bar + status update; no OHLCV re-fetch for observed tickers (use the candidates_cache or open-trades OHLCV fetch already running).
- **L5** Chart_render bytes capture at detection time per Sec 9.1 Q3 V1+ LOCK -- the spec MUST design integration with the existing `chart_renders` table + chart_jit substrate (couples with Sub-bundle 1 T2.SB6 ship at Phase 13). Cache-key shape may need NEW surface enum value (e.g., `pattern_detection_chart`); evaluate vs reusing existing surfaces.
- **L6** Per-pattern metadata at detection time -- sector / industry / market_cap / ATR_pct / 90d_return / 52w_prox MUST be captured at detection (not reconstructed later) for future stratified analysis; spec MUST define the source-of-truth for each field at detection time + commit cadence.
- **L7** Existing `_step_pattern_detect` MUST be EXTENDED (not replaced) to APPEND rows to `pattern_detection_events`. Backwards-compat: existing `pattern_evaluations` table continues to receive rows; the new `pattern_detection_events` is ADDITIONAL substrate. The two coexist.
- **L8** L2 LOCK preserved -- ZERO new Schwab API calls (`schwabdev.Client.*`); existing multiset Counter source-grep test at `tests/integration/test_l2_lock_source_grep.py` MUST continue passing.

---

## §2 Spec scope to design

Given §1's locks, the brainstorming phase MUST produce:

### §2.1 v22 schema migration design

- Spec §3+ enumerates 2 NEW tables (`pattern_detection_events` + `pattern_forward_observations`) with full DDL including CHECK constraints + indexes + FK semantics + append-only enforcement at the schema layer where possible
- Migration file at `swing/data/migrations/0022_phase14_temporal_log.sql` (or operator-paired naming)
- Backup-gate equality form `pre_version == 21` per gotcha #11 LOCK (NOT `<=`)
- gotcha #9 explicit `BEGIN`/`COMMIT`/`ROLLBACK` discipline at the runner level
- Indexes optimized for: (a) status-IN-open-states scan at observe-step time; (b) per-ticker historical lookup; (c) per-pattern-class strata; (d) date-range queries for backtest replay
- FK semantics: pattern_forward_observations.detection_id `ON DELETE RESTRICT` (append-only invariant; no cascade delete)

### §2.2 Repo layer design

- NEW `swing/data/repos/pattern_detection_events.py` -- append-only repo with `insert_event()` + `get_open_detections(asof_date)` + `get_by_id()` + `list_by_ticker_date_range()` etc.
- NEW `swing/data/repos/pattern_forward_observations.py` -- append-only repo with `insert_observation()` + `get_for_detection_chain(detection_id)` + status state machine helpers
- Dataclass shapes per gotcha #11 paired-discipline (CHECK enum mirror in Python constants + `__post_init__` validators)
- Append-only enforcement: NO `update_*` or `delete_*` repo functions

### §2.3 `_step_pattern_detect` extension design

Per L7: extend the EXISTING Phase 13 `_step_pattern_detect` at `swing/pipeline/runner.py:1485-1490` (the empty-pool early-return per CLAUDE.md gotcha #27) to ALSO append rows to `pattern_detection_events` when patterns ARE detected. Spec defines:
- Per-pattern metadata enrichment at write time (sector + industry + market_cap + ATR_pct + 90d_return + 52w_prox sources)
- finviz_screen_state JSON shape (which criteria the ticker passed)
- structural_anchors_json shape per pattern_class (W-bottom: trough_1_date + center_peak_date + trough_2_date; cup-with-handle: prior_high_date + cup_low_date + handle_low_date; etc.)
- composite_score LOCKED at detection (NOT recomputed)
- chart_render_id population via the V1+ chart_render bytes capture
- Source = `'pipeline'` for runner-emitted; reserve other source values for V2 backfill / cohort imports

### §2.4 NEW `_step_pattern_observe` pipeline step design

- Position in pipeline DAG: AFTER `_step_pattern_detect`; BEFORE `_step_charts` (or position-paired at brainstorming)
- Algorithm: SELECT (detection_id, ticker, pattern_class) FROM pattern_detection_events WHERE (most-recent observation has status IN open-states); for each, append observation row with today's OHLC + status update
- OHLCV source: reuse the OhlcvCache populated by `_step_evaluate` for open-position tickers + observation-scope tickers (avoid duplicate fetches)
- Status state machine: define transitions explicitly (`pending` -> `triggered_open` on entry; `triggered_open` -> `triggered_closed_*` on stop/target; `pending` -> `invalidated` on pattern-shape-break; etc.)
- Empty-pool early-return per gotcha #27 MUST emit `warnings_json` audit (no silent skip)

### §2.5 chart_render bytes capture at detection time (V1+ LOCK)

- Couples with the existing `chart_renders` table + `chart_jit` substrate from Phase 13 T2.SB6
- Cache-key shape: evaluate NEW surface enum value (e.g., `pattern_detection_chart`) vs reusing existing surfaces (`hyprec_detail`)
- The capture is INVOKED at detect-step time + chart_render_id FK populated on the new `pattern_detection_events` row
- If chart_render fails (matplotlib hiccup; bar shortage; etc.), pattern_detection_events row still INSERTs with `chart_render_id IS NULL`; gotcha #27 audit MUST emit
- Closes CR.1 (closeout review chart snapshot) dependency cleanly

### §2.6 Per-pattern metadata sourcing (L6)

For each per_pattern_metadata field, spec defines source-of-truth at detection time:
- **sector / industry**: from `candidates` table for the (ticker, evaluation_run_id) row (consistent with V2.G3 fix at Sub-bundle 1)
- **market_cap**: from `candidates.market_cap_dollars` (verify column exists)
- **ATR_pct**: from `candidates.atr_pct` (verify column exists)
- **90d_return** + **52w_prox**: derived from OHLCV bars at detection_date; spec defines computation
- All sources MUST be available at detect-step time; do NOT add NEW Schwab/yfinance fetches (L2 LOCK preserved)

### §2.7 Operator-witnessed gate enumeration

- **S1**: fast suite + ruff
- **S2**: schema v22 applied; `PRAGMA user_version` returns 22 (or whatever migration tracking shows); both new tables empty + readable
- **S3**: Run pipeline; pattern_detection_events accumulates rows for detected patterns; per-pattern metadata populated; chart_render_id non-NULL for successful renders
- **S4**: Re-run pipeline; pattern_forward_observations accumulates today's bar for previously-open detections; status state machine transitions correctly
- **S5**: Append-only invariant verification (attempt UPDATE on pattern_detection_events → reject; attempt DELETE → reject; INSERT only path works)
- **S6**: chart_render_id chain: pattern_detection_events.chart_render_id -> chart_renders.chart_id -> chart_svg_bytes verifiable
- (gates S5 + S6 may be runbook OR mechanical-test-covered per brainstorming Codex assessment)

---

## §3 Open questions (Codex chain SHOULD surface answers; operator triage at executing-plans dispatch)

1. **chart_render integration architecture** -- NEW surface enum value vs reuse existing? Cache-key shape with detection_date AND pattern_class context?
2. **pipeline step DAG positioning** -- `_step_pattern_observe` after detect, before charts (recommended); OR alternative position?
3. **observe-step OHLCV source** -- reuse OhlcvCache (recommended; zero cost) OR direct read from OhlcvArchive?
4. **status state machine completeness** -- enumerate ALL transitions + invariants; defer to writing-plans phase if Codex flags ambiguity
5. **per_pattern_metadata schema** -- structured JSON columns vs separate columns? (JSON recommended for V1; V2 candidate for normalization)
6. **finviz_screen_state JSON shape** -- which criteria recorded? Verbatim vs canonicalized?
7. **structural_anchors_json shape per pattern_class** -- spec needs explicit schema per class
8. **chart_render failure handling** -- nullable chart_render_id + warnings_json audit (recommended); alternative emit-with-placeholder
9. **migration runner safety** -- backup-gate equality form `pre_version == 21` strict per existing CLAUDE.md gotcha
10. **append-only enforcement layer** -- schema-level CHECK + triggers OR repo-layer-only? (Schema-level recommended for robustness)
11. **per-pattern_class detector emission** -- which detector classes WRITE to pattern_detection_events in V1+? (all 5 V1 detectors per Phase 13 spec OR a subset)
12. **backwards-compat with existing pattern_evaluations** -- coexistence semantics + when/whether to deprecate
13. **V1+ chart_render bytes capture trigger** -- on EVERY detection OR only A+ tier OR all watch+aplus? (impacts substrate size growth rate)
14. **observe-step empty-pool warnings_json audit** -- gotcha #27 application
15. **operator-paired V1 simplifications + V2 candidates** -- enumerate at spec §13

---

## §4 OUT OF SCOPE (do not design into V1+)

- Backfill of pattern_detection_events from EXISTING `pattern_evaluations` rows (V2 candidate; substantive scope on its own)
- Cross-pattern composite signals (W + cup-and-handle co-occurrence; etc.)
- Real-time ruleset replay engine consuming the observation log (Phase 15+ candidate; the temporal log substrate ENABLES this but Sub-bundle 2 doesn't build the engine)
- Operator failure-mode classification surface (Sec 9.1 Q3 V1++ scope; deferred)
- ML re-ranker against per-pattern metadata (indefinite defer; L4 cumulative LOCK)
- Sell-side execution / paper-trading hooks (L3 cumulative LOCK; Phase 14+ deferred)
- Drift monitoring against detection rates over time (L5 cumulative LOCK; Phase 13.5 candidate)
- Sub-bundle 3 / 4 / 5 scope (per Sec 9.1 Q1 LOCK; serial execution)
- Phase 15+ scope
- Schwab API integration changes (L2 LOCK preserved)
- HTMX surface introductions (Sub-bundle 2 is pipeline + schema; no NEW HTMX endpoints)
- Backfill of CHART_render bytes for HISTORICAL detections (V2 candidate)
- Multi-source same-detection_date dedupe (V2; assume different sources emit distinct rows; let downstream queries dedupe if needed)
- Active monitoring / alerting on observation-log state transitions (V2 candidate; Phase 15+)

---

## §5 Adversarial review (Codex)

Invoked automatically by `copowers:brainstorming` after the spec draft + before final commit.

**Expected chain shape:** 2-5 substantive Codex rounds (matches Sub-bundle 1 brainstorming + writing-plans phases).

**Adversarial review watch items (load-bearing; consume the 13 forward-binding lessons from Sub-bundle 1 cumulative)**:

1. **Brief-vs-production-function-signature verification (gotcha #17 / Expansion #2 refinement)** -- spec MUST cite real production names + verify signatures (`current_stage`, `OhlcvCache.get_or_fetch`, `compute_position_capital_utilization`, `_step_pattern_detect`, etc.); RE-GREP at writing-plans phase.
2. **Cumulative regression cascade audit (gotcha #21 / Expansion #13)** -- post-fix sweep at each Codex round.
3. **Schema-CHECK + Python-constant + dataclass-validator paired discipline (gotcha #11)** -- V1+ 2 NEW tables; CHECK enums must mirror Python constants + dataclass validators in SAME task; backup-gate equality form `pre_version == 21` strict.
4. **Migration runner discipline (gotcha #9)** -- explicit `BEGIN`/`COMMIT`/`ROLLBACK`; `executescript()` discipline; partial-failure rollback tests.
5. **Append-only invariant enforcement** -- schema CHECK + repo layer + discriminating tests; attempting UPDATE/DELETE on pattern_detection_events MUST fail; verify at multiple layers.
6. **gotcha #27 silent-skip-without-audit** -- `_step_pattern_observe` empty-pool early-return MUST emit `warnings_json` audit row; same for chart_render failure path.
7. **gotcha #26 + #37 elimination by construction** -- spec MUST state both gotcha references explicitly + cite "forward-walk; no archive re-read; no regeneration" invariant.
8. **Per-pattern metadata sourcing audit** -- each field's source-of-truth verified against production code at detect-step time; NO new yfinance / Schwab calls (L2 LOCK preserved).
9. **chart_render integration audit** -- cache-key shape + surface enum decision; fallback behavior on render failure; warnings_json audit; integration with `chart_jit` substrate.
10. **Status state machine completeness** -- ALL transitions enumerated; no orphan states; spec defines per-transition trigger.
11. **Backwards-compat with `pattern_evaluations`** -- spec defines coexistence semantics; existing detector tests continue passing.
12. **Empty-input handling** (Expansion #4 refinement) -- empty patterns-detected case; empty open-detections-to-observe case; both MUST be tested.
13. **Runtime-binding-shape audit** (Expansion #4 sub-refinement) -- parameterized SQL with sqlite3-specific binding semantics; dynamic `?` expansion for IN clauses.
14. **Test fixture shape vs production emitter shape** (Phase 12 C.D family) -- test fixtures match production INSERT shape exactly.
15. **L2 LOCK parametric source-grep regression** -- existing test at `tests/integration/test_l2_lock_source_grep.py` MUST continue passing; spec cites this discriminating test.
16. **ASCII discipline scope** (gotcha #32) -- declare scope across NEW files at spec §15.
17. **`Co-Authored-By` footer suppression** -- explicit citation in spec; ~609+ cumulative ZERO drift streak.
18. **gotcha #36 two-Codex-chain default** -- spec evaluates whether writing-plans phase warrants two-chain (analytical-substrate-changing methodology REVIEW after implementation review).

---

## §6 Deliverable shape

**Design spec at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-2-temporal-log-design.md`** (mirror Sub-bundle 1 brainstorm spec format; reference `docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md`):

- §1 Architecture overview
- §2 Pre-locked operator decisions verbatim (Sec 9.1 Q1+Q2+Q3+Q6+Q7 + L1-L8 sub-bundle LOCKs)
- §3 Module touch list (NEW migration / NEW repos / MODIFIED runner.py / MODIFIED chart_jit integration)
- §4 v22 schema migration design (DDL + indexes + CHECK + FK)
- §5 Repo layer design (NEW repos for both tables; append-only enforcement)
- §6 `_step_pattern_detect` extension design (write-path to pattern_detection_events)
- §7 NEW `_step_pattern_observe` pipeline step design (algorithm + position + status state machine)
- §8 chart_render bytes capture at detection (V1+ LOCK; cache-key + integration + fallback)
- §9 Per-pattern metadata sourcing (per-field source-of-truth at detect-step time)
- §10 Sub-bundle decomposition recommendation (single writing-plans + executing-plans dispatch OR split per task complexity)
- §11 Test fixture strategy
- §12 Schema impact analysis (v22 LOCK + backup-gate equality form + migration runner discipline)
- §13 V1+ simplifications + V2 candidates banked
- §14 Operator decision items pending (Open Questions; 15+ enumerated)
- §15 Cumulative discipline compliance summary

**Target line count: ~700-1100 lines** (matches Sub-bundle 1 brainstorm at ~810; +substrate for the larger architectural surface).

**Commit message stem:** `docs(phase14-sub-bundle-2-spec): brainstorm <draft|R1|R2|...> -- ...`.

---

## §7 If you get stuck

- If a code-read against production surfaces an unexpected dependency NOT in Sub-bundle 1 substrate, ESCALATE to orchestrator (do NOT silently restructure scope).
- If Codex pushes back on the V1+ scope LOCK (chart_render bytes capture), HOLD THE LINE -- Sec 9.1 Q3 LOCK.
- If Codex pushes back on the 2-table design (proposes consolidation), HOLD THE LINE -- commissioning brief Sec 2.5 LOCK + separation-of-concerns rationale (detection events frozen; observations append-only forward-walk).
- If Codex pushes back on append-only invariants (proposes UPDATE paths), HOLD THE LINE -- L1 + L2 cumulative LOCK + gotcha #26 + #37 elimination rationale.
- If Codex pushes back on v22 schema (proposes deferring schema work), HOLD THE LINE -- Sec 9.1 Q3 V1+ requires the substrate.
- DO NOT propose schema migrations beyond v22 within Sub-bundle 2 scope.
- DO NOT add `Co-Authored-By` footer to ANY commit.
- DO NOT skip hooks (`--no-verify`).
- DO NOT widen scope to other Phase 14 items or Phase 15+ items.
- DO NOT design backfill of historical detections in V1+ (V2 candidate).
- DO NOT design real-time ruleset replay engine in V1+ (Phase 15+ candidate; Sub-bundle 2 ENABLES it but doesn't build it).

---

## §8 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase14-sub-bundle-2-temporal-log-brainstorm-return-report.md` (mirror Sub-bundle 1 brainstorm return report shape):

1. Final HEAD on branch + commit count breakdown (per-commit Codex round attribution)
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper)
3. Spec line count + per-section line count breakdown
4. Pre-locked operator decisions verbatim verification (Sec 9.1 LOCKs + L1-L8 sub-bundle LOCKs + commissioning brief Sec 2.5 architectural primitive)
5. Open Questions: resolved + deferred (15+ enumerated)
6. Codex Major findings ACCEPTED with rationale (if any; ZERO acceptances strongly preferred per Sub-bundle 1 precedent)
7. V1+ simplifications + V2 candidates banked (per V1+ scope)
8. Forward-binding lessons for writing-plans dispatch (NEW + inherited 13)
9. Sub-bundle decomposition recommendation (single writing-plans + executing-plans dispatch OR split)
10. Schema impact verdict (v22 LOCKED + backup-gate equality form)
11. Cumulative gotcha set application summary (per design dimension)
12. Worktree teardown status
13. ZERO Co-Authored-By footer drift confirmation (`%(trailers)` inspection)
14. CLAUDE.md status-line refresh draft text
15. Writing-plans dispatch-readiness summary (per OQ disposition triage)

---

## §9 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed for production code reads + spec writing).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES -- branch `phase14-sub-bundle-2-temporal-log-brainstorming`. Worktree directory `.worktrees/phase14-sub-bundle-2-temporal-log-brainstorming/`.
- **Model:** defer to harness default.
- **Expected duration:** ~3-5 hours brainstorming + ~30-90 min Codex chain. Total ~4-6 hours operator-paced.
- **Codex MCP chain count:** SINGLE chain at end (per Sec 9.1 Q7 LOCK + brainstorming-phase precedent at Sub-bundle 1).

---

*End of brief. Phase 14 Sub-bundle 2 brainstorming dispatch -- produce a design spec for the temporal pattern detection + observation log infrastructure (V1+ scope: 2 NEW append-only tables + NEW `_step_pattern_observe` pipeline step + per-pattern metadata enrichment at detection + chart_render bytes capture at detection per Sec 9.1 Q3 LOCK). Eliminates gotchas #26 + #37 by architectural construction. Sub-bundle 2 is the highest-leverage methodological improvement Phase 14 ships per Turn H 2026-05-27 PM #3 substantive synthesis.*
