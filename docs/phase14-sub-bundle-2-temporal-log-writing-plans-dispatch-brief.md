# Phase 14 Sub-bundle 2 -- Temporal Pattern Detection + Observation Log Infrastructure -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 2 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan derived from the Sub-bundle 2 brainstorm spec. Plan lives at `docs/superpowers/plans/2026-05-29-phase14-sub-bundle-2-temporal-log-plan.md`. The plan decomposes the spec into bite-sized TDD slices with per-task acceptance criteria, file-level diff projections, test scope, commit cadence, and an executing-plans dispatch-readiness package. This is the **largest substrate-changing sub-bundle Phase 14 ships** (a v22 schema migration introducing 2 NEW append-only tables + a NEW pipeline step), so the plan must be correspondingly rigorous on schema/semantics correctness.

**Brief:** `docs/phase14-sub-bundle-2-temporal-log-writing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; Sub-bundle 1 (data-wiring) SHIPPED end-to-end at `e323339`; **Sub-bundle 2 brainstorm SHIPPED at `9fc661b`** (788-line spec; Codex single-chain CONVERGED R4 NO_NEW_CRITICAL_MAJOR); CLAUDE.md gotchas restructure at `665cab0`; housekeeping at `88ad22d`; FB-N1 Codex-MCP root-cause + fix at `d134833`. Main HEAD at writing-plans dispatch time: `d134833`.

**Cumulative discipline at dispatch:** 37 CLAUDE.md gotchas BINDING (NOTE: as of `665cab0` the CLAUDE.md Gotchas section was compressed to trigger+fix and the "Expansion #N" process/review + brief-authoring disciplines were RELOCATED to `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); ~616+ cumulative ZERO Co-Authored-By trailer drift; 48th cumulative C.C lesson #6 validation NOTABLE (Sub-bundle 2 brainstorm; single chain caught 2C+1M cumulative across R1-R2 despite pre-Codex review); Schema v21 LOCKED baseline -- **Sub-bundle 2 INTRODUCES v22** (the substrate); L2 LOCK preserved (multiset Counter source-grep test at `tests/integration/test_l2_lock_source_grep.py` baseline `bf7e071`).

**Expected duration:** ~2.5-4 hours writing-plans + 2 Codex chains (per OQ-20 LOCK; see §1.5 L6). Plan line target: **~2000-3500 lines** (substrate-changing: 2-table DDL + 2 append-only repos + migration runner discipline + detect-step extension + NEW observe step + status machine + chart capture inflate the plan beyond Sub-bundle 1's).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief.
- `copowers:writing-plans` wraps `superpowers:writing-plans` with adversarial Codex MCP review after the plan is written.
- **Codex chain count: TWO chains** per OQ-20 operator LOCK (see §1.4 + §1.5 L6 + §5). **FB-N1 RESOLVED (2026-05-29 #2 at `d134833`):** the copowers Codex MCP "1s timeout" was a Windows spawn failure -- bare `command: "codex"` in `.mcp.json` picked the extensionless POSIX shell script over `codex.cmd` (no PATHEXT in a raw MCP spawn), and `MCP_CONNECTION_NONBLOCKING=true` masked the dead server as a ~1s fast-fail. FIXED in both `.mcp.json` copies via `"command": "cmd", "args": ["/c", "codex", "mcp-server"]` (memory `feedback_copowers_codex_mcp_windows_launcher`; RE-APPLY on copowers upgrade -- a version bump overwrites the cache copy). A freshly-dispatched implementer reads the fixed `.mcp.json` at startup, so **use the MCP transport.** The `codex exec` CLI (`codex exec resume --last -o <file> -`) remains the transport-independent BACKSTOP if the MCP ever fails again.
- Output: plan doc at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-2-temporal-log-plan.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md`** -- the brainstorm spec (788 lines; AUTHORITATIVE for architectural decisions). Especially:
   - §1 Architecture overview (§1.1 why #26+#37 eliminated by construction; §1.3 coexistence with `pattern_evaluations` L7; §1.4 the DAG)
   - §2 Pre-locked operator decisions (Sec 9.1 LOCKs + L1-L8 sub-bundle LOCKs + §2.3 NORMATIVE forward-walk/append-only invariant + §2.4 architectural primitive)
   - §3 Module touch list
   - §4 v22 schema migration design (§4.1 detection_events DDL incl. NEW `data_asof_date` column; §4.2 observations DDL; §4.3 migration file structure gotcha #9; §4.4 backup gate STRICT `pre_version == 21`; §4.5 indexes)
   - §5 Repo layer (§5.1 detection_events repo; §5.2 observations repo incl. dynamic-`?` IN-clause; §5.3 dataclasses gotcha #11 paired discipline)
   - §6 `_step_pattern_detect` extension (L7; §6.3 structural_anchors_json; §6.4 empty-pool audit)
   - §7 NEW `_step_pattern_observe` (§7.1 algorithm; §7.2 OHLCV source + fetch-scope; §7.3 status state machine + §7.3.1 anchor sourcing; §7.4 empty-pool audit; §7.5 DAG position)
   - §8 chart_render bytes capture (§8.1 REUSE theme2_annotated; §8.2 dedicated `render_theme2_annotated_svg`; §8.3 failure handling + ON DELETE SET NULL FK)
   - §9 Per-pattern metadata sourcing -- **REDESIGNED per code-read** (§9.1 brief-vs-reality finding; §9.2 per-field source-of-truth; §9.4 finviz_screen_state shape)
   - §10 Sub-bundle decomposition recommendation
   - §11 Test fixture strategy
   - §12 Schema impact analysis (v22)
   - §13 V1+ simplifications + V2 candidates banked
   - §14 Operator decision items pending (20 OQs; 5 flagged -> NOW LOCKED, see §1.3 below)
   - §15 Cumulative discipline compliance summary (§15.5 Codex chain evaluation)

3. **`docs/phase14-sub-bundle-2-temporal-log-brainstorm-return-report.md`** -- return report (15 items). Especially the V2 candidates banked (do NOT design into V1+ plan), the forward-binding lessons, the schema impact verdict (v22), and FB-N1 (Codex MCP transport).

4. **`docs/phase14-sub-bundle-2-temporal-log-brainstorming-dispatch-brief.md`** -- original brainstorm dispatch brief. Especially §1 LOCKs (L1-L8) + §5 the 18 adversarial-review watch items (carry forward to writing-plans).

5. **`docs/phase14-commissioning-brief.md`** -- Sec 2.5 architectural primitive (2-table LOCK) + Sec 9.1 LOCKs (BINDING) + Sec 4 cumulative discipline + Sec 6 cross-cutting watch items.

6. **`CLAUDE.md`** -- the compressed Gotchas section (post-`665cab0` restructure). Most relevant for this sub-bundle:
   - **(#9)** sqlite3 `executescript()` implicit COMMIT -> explicit BEGIN/COMMIT/ROLLBACK migration-runner discipline
   - **(#11)** Schema-CHECK + Python-constant + dataclass-validator paired (same task) + read-path `_row_to_*` mappers same task + migration backup-gate STRICT `pre_version == 21`
   - **(#27)** silent-skip-without-audit -> detect-step + observe-step empty-pool + chart-render-failure emit `warnings_json`
   - **(#26 + #37)** eliminated BY CONSTRUCTION (forward-walk; no archive re-read; no regeneration) -- the methodological payoff; the plan must keep this honest (select-by-`observation_date` + freeze; never blind-last-row; never re-read a past date from a later archive)
   - **(#5)** OHLCV fetch scope = open-trade tickers -> observe-step expansion AUDITED + accepted (OQ-17 LOCK)
   - sqlite3 list-bind / dynamic-`?` IN-clause + empty-input short-circuit
   - `date.fromisoformat` TEXT->date boundary
   - append-only precedent: `reconciliation_corrections`, `pattern_evaluations`, `watchlist_close_track_flag_events`

7. **`docs/orchestrator-context.md`** -- (a) §"Pre-Codex review + brief-authoring disciplines" (the relocated Expansion #N catalog; apply ALL in the pre-Codex review pass -- especially #2 brief-vs-signature, #4 SQL-column verification, #8 counter-unit audit, #11 taxonomy/attribution propagation, #13 cumulative regression cascade); (b) §"Maintenance: retention discipline" size-check trigger; (c) "Currently in-flight work".

8. **Production code surfaces enumerated in spec §3** -- read each BEFORE plan-authoring to re-verify the spec's path + signature claims at writing-plans time (gotcha #2; the brainstorm already corrected the candidates-schema assumption -- re-confirm):
   - `swing/pipeline/runner.py:1396 _step_pattern_detect` (the L7 EXTEND target) + the existing `_step_*` shape + lease/warnings_json accumulator
   - `swing/data/db.py` migration runner (`_apply_migration` + the `pre_version == 21` backup gate insertion point)
   - `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql` (template for `0022`)
   - `swing/data/repos/` append-only precedent repos + `swing/data/models.py` dataclass patterns
   - `swing/data/ohlcv_archive.py:372 resolve_ohlcv_window` (provider priority `schwab_api` > `yfinance`) + `swing/web/ohlcv_cache.py` (the `provider` provenance tag for OQ-17)
   - `swing/web/charts.py:481 render_theme2_annotated_svg` + `swing/data/repos/chart_renders.py:refresh_chart_render` + `swing/web/view_models/patterns/exemplars.py` (the existing theme2_annotated writer it coexists with)
   - `swing/data/repos/candidates.py` (sector/industry/adr_pct sourcing for §9; confirm `market_cap_dollars` + `atr_pct` ABSENT)

9. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_orchestrator_qa_implementer_product` (orchestrator-side; informational)
   - `feedback_verify_regression_test_arithmetic` (compute test arithmetic both pre/post for the status-machine state transitions + the append-only-rejection tests)
   - `project_applied_research_arc_2026-05-27` (why the temporal log is the operator-stated forward path)

---

## §1 Pre-locked operator decisions (DO NOT re-litigate at writing-plans phase)

### §1.1 Sec 9.1 LOCKs (commissioning-time; binding for all Phase 14 sub-bundles)

Per `docs/phase14-commissioning-brief.md` Sec 9.1:
- **Q1** sequencing = data-wiring (SHIPPED) -> **temporal log V1+ (THIS SUB-BUNDLE)** -> charts -> review+journal -> metrics
- **Q2** execution = SERIAL
- **Q3** temporal log scope = **V1+** (base 2 tables + `_step_pattern_observe` + per-pattern metadata + chart_render bytes capture at detection)
- **Q6** close-out = all 5 sub-bundles merged + operator browser-witnessed verification (incl. v22 schema verification)
- **Q7** Codex chain count = orchestrator discretion per sub-bundle (THIS sub-bundle: TWO chains per OQ-20 LOCK below)

### §1.2 Brainstorm dispatch brief + spec LOCKs (L1-L8 + §2)

Per brainstorm dispatch brief §1.3 + spec §2 (verbatim binding; see sources for full text):
- **L1** Append-only on BOTH tables (INSERT-only; no UPDATE/DELETE repo functions)
- **L2** Forward-walk semantic ONLY; gotchas #26 + #37 ELIMINATED BY CONSTRUCTION (stated NORMATIVELY at spec §2.3; the plan MUST preserve this)
- **L3** v22 migration; gotcha #11 paired discipline + gotcha #9 explicit BEGIN/COMMIT/ROLLBACK + backup-gate STRICT `pre_version == 21`
- **L4** `_step_pattern_observe` zero-cost beyond existing detector invocations (reuse the OhlcvCache ladder; no NEW fetch infrastructure)
- **L5** chart_render bytes capture REUSING `theme2_annotated` surface + dedicated `render_theme2_annotated_svg`; `chart_render_id` FK = `ON DELETE SET NULL` (nullable audit linkage; chart is best-effort, NOT a frozen fact)
- **L6** Per-pattern metadata captured at detection (not reconstructed) -- per spec §9 REDESIGN (compute ATR%/90d-ret/52w-prox from already-fetched bars; sector/industry/adr_pct from `candidates`; `market_cap` NULL)
- **L7** EXTEND existing `_step_pattern_detect` (don't replace); `pattern_evaluations` coexists; existing detector tests stay green
- **L8** L2 LOCK preserved -- ZERO new `schwabdev.Client.*` call sites; source-grep test continues passing
- **2-table architectural primitive** (commissioning brief Sec 2.5 + spec §2.4): `pattern_detection_events` + `pattern_forward_observations` -- DO NOT propose consolidation

### §1.3 Operator-LOCKed dispositions for the 5 flagged OQs (operator-paired triage 2026-05-29 #2; BINDING)

The brainstorm flagged 5 OQs for operator triage; operator LOCKED them at the writing-plans dispatch:

| OQ | LOCKed disposition |
|---|---|
| **OQ-10** append-only enforcement layer | **Repo-layer (no update/delete fns) + UNIQUE(detection_id, observation_date) + RESTRICT FK on observations.detection_id.** SQLite BEFORE UPDATE/DELETE triggers banked as a V2 defense-in-depth candidate (do NOT add triggers in V1+). Matches existing project append-only precedent. |
| **OQ-16** market_cap NULL | **Accept `market_cap = NULL` in V1+.** Persisting Finviz Market Cap to `candidates` is its own migration (out of Sub-bundle 2 scope); banked as V2 dependency. |
| **OQ-17** observe-step fetch scope + provenance | **Accept the bounded open-detection-set expansion** (reuse the existing OhlcvCache ladder -- which prefers `schwab_api` > `yfinance` per `resolve_ohlcv_window`); zero NEW `schwabdev.Client.*` call sites (L2 LOCK preserved). **NEW REQUIREMENT: record the `provider` provenance tag ('schwab_api' / 'yfinance') inside each `ohlc_today_json` observation** so every captured bar is self-documenting about its source. (Operator raised provenance; this makes it auditable per-bar.) Do NOT relax L2 LOCK to force a Schwab fetch (that was the rejected alternative). |
| **OQ-18** status-machine windows + invalidation | **`max_pending_window = 30` sessions; `max_post_trigger_window = 60` sessions; config-surfaced** (small cfg block; tunable without code change). Per-class `structural_invalidation_level` per spec §7.3.1 (VCP/flat_base base low; cup_with_handle cup bottom; high_tight_flag pole/consolidation low; double_bottom_w min(trough_1, trough_2)). V1+ emits the ruleset-agnostic subset {pending, triggered_open, invalidated, expired}. |
| **OQ-20** Codex chain count | **TWO chains for the rest of Sub-bundle 2** (see §1.5 L6 + §5): a plan-completeness/implementation-feasibility lens AND a schema/semantics-hardening lens, each to NO_NEW_CRITICAL_MAJOR convergence. Rationale: the v22 append-only substrate is PERMANENT and hard to walk back. |

The other 15 OQs are resolved in the spec (§14 table). Do NOT re-open them.

### §1.4 Sub-bundle decomposition LOCK (per spec §10)

**Single writing-plans + single executing-plans dispatch for the whole sub-bundle.** Do NOT split into multiple executing-plans dispatches. The plan's per-task slicing (§G) decomposes internally (T-2.1 .. T-2.6 suggested), but it is ONE executing-plans dispatch.

### §1.5 Writing-plans phase-specific LOCKs (this brief)

- **L1**: Plan SHALL produce ONE executing-plans dispatch (per §1.4).
- **L2**: Per-task slicing in §G MUST be bite-sized (each task 3-5 commits max; per-task acceptance criteria + step-checkbox TDD).
- **L3**: Test count target = ~50-100 fast tests (matches spec + implementer recommendation). Plan SHALL distribute across tasks + sum-check in §H. (Trust pytest output over the estimate per gotcha #1.)
- **L4**: Commit cadence target = ~15-25 commits total. Plan SHALL enumerate per-task commit count + verify total in §G.0.
- **L5**: Plan §E SHALL re-cite Sec 9.1 LOCKs + L1-L8 + spec §2 LOCKs + this brief §1 LOCKs + the 5 OQ dispositions (§1.3) in a cumulative LOCK summary table.
- **L6**: **TWO Codex chains** (OQ-20 LOCK). Plan §J SHALL design BOTH the writing-plans two-chain placement (chain #1 plan-completeness lens to convergence; chain #2 schema/semantics-hardening lens to convergence -- append-only invariants + forward-walk #26/#37 correctness + v22 DDL/CHECK/FK posture + status-machine completeness + migration-runner rollback) AND the executing-plans two-chain placement (chain #1 implementation review after code+tests land but before the operator-witnessed gate; chain #2 schema/semantics-hardening review). FB-N1 RESOLVED at `d134833` (Windows spawn fix; see skill posture) -- the MCP transport is available to a fresh implementer; the `codex exec` CLI is the transport-independent backstop.

---

## §2 Architectural surface for the plan to design

Given §1's locks, the writing-plans phase MUST produce:

### §2.1 Per-task slicing (plan §G)

Suggested task buckets (plan refines; bite-sized per L2):

- **T-2.1** v22 migration `0022_phase14_temporal_log.sql`: both tables' DDL (incl. detection_events `data_asof_date` column + `chart_render_id` `ON DELETE SET NULL`; observations `detection_id` `ON DELETE RESTRICT` + `UNIQUE(detection_id, observation_date)`) + indexes (§4.5) + CHECK enums; migration runner `pre_version == 21` STRICT backup gate; explicit BEGIN/COMMIT/ROLLBACK (#9); rollback-through-runner test. Schema-CHECK + Python constants + dataclass validators land in THIS task (#11 paired).
- **T-2.2** `swing/data/repos/pattern_detection_events.py` append-only repo (`insert_event` + `get_open_detections` + `get_by_id` + `list_by_ticker_date_range`) + `PatternDetectionEvent` dataclass + `_row_to_*` mapper (same task; #11 read-path) + append-only assertion tests (NO update/delete fns).
- **T-2.3** `swing/data/repos/pattern_forward_observations.py` append-only repo (`insert_observation` + `get_for_detection_chain` + `get_latest_observations_for_detections` with dynamic-`?` IN-clause + empty-input short-circuit + status helpers) + `PatternForwardObservation` dataclass + mapper + UNIQUE/RESTRICT discriminating tests.
- **T-2.4** `_step_pattern_detect` EXTENSION (L7): append `pattern_detection_events` for the 5 V1 detectors over the aplus pool; per-pattern metadata enrichment (§9 redesign); `structural_anchors_json` (§6.3); `finviz_screen_state` (§9.4); chart_render capture via `render_theme2_annotated_svg` + `refresh_chart_render` + nullable `chart_render_id`; empty-pool + chart-failure `warnings_json` (#27). Existing `pattern_evaluations` write + existing detector tests UNCHANGED.
- **T-2.5** NEW `_step_pattern_observe` (after detect, before charts; §7.5): open-detection-set enumeration; OHLCV reuse via the ladder + **`provider` provenance tag into `ohlc_today_json` (OQ-17)**; select-by-`observation_date` + freeze (never blind-last-row); status state machine (30/60 config-surfaced windows + per-class invalidation §7.3.1); empty-pool/no-bar `warnings_json` (#27).
- **T-2.6** (closer): cross-step integration tests (detect -> observe forward-walk over multiple simulated sessions) + Sec 9.1 + L1-L8 + 5-OQ-LOCK verification + L2 LOCK source-grep continued-pass + operator-witnessed gate runbook (§2.4) + return report.

**Plan SHALL define** per-task commit count, per-task fast-test count, per-task acceptance criteria with file:line citations, per-task step-checkbox TDD.

### §2.2 Per-task acceptance criteria (plan §G.X.acceptance)

Each task SHALL enumerate: files modified/added (exact paths); functions added + signatures verified against production code; discriminating tests (name + assertion shape); cumulative discipline preservation (specific gotchas at this task); Sec 9.1 + L1-L8 + OQ LOCK preservation at this task.

### §2.3 Test surface (plan §H)

- **~50-100 fast tests** distributed across T-2.1 .. T-2.6 (rough proportions: migration/rollback + CHECK/validator ~12-18; detection_events repo append-only ~8-12; observations repo append-only + UNIQUE/RESTRICT + dynamic-? IN-clause + empty-input ~10-15; detect-step extension + metadata + chart capture + warnings ~10-15; observe-step + status machine + provenance tag + warnings ~12-18; integration + L2 source-grep ~4-6).
- **Append-only enforcement tests** (OQ-10 LOCK): assert no `update_*`/`delete_*` repo fns exist; assert UNIQUE(detection_id, observation_date) rejects a duplicate observation; assert RESTRICT FK blocks deleting a detection with observations.
- **Forward-walk discriminating test** (#26/#37): plant a detection at session N; append an observation at N; mutate the archive's bar for date N; re-run observe at N+1; assert the frozen `ohlc_today_json` for date N is UNCHANGED (no re-read).
- **Status-machine arithmetic tests** (`feedback_verify_regression_test_arithmetic`): compute the 30/60 window transitions both at-threshold and over-threshold; assert pending->expired at 30, triggered_open->expired at 60, pending->invalidated on structural break.
- **0 slow tests** anticipated (observe-step OHLCV mocked; no live yfinance/Schwab).
- **Plan SHALL sum-check** the test count in §H.

### §2.4 Operator-witnessed gate runbook (plan §I per spec §10/§2.7)

- **S1**: `pytest -m "not slow"` green + `ruff check swing/` clean
- **S2**: v22 applied; `PRAGMA user_version`/schema_version = 22; both new tables empty + readable; backup file emitted at the `pre_version == 21` boundary
- **S3**: run pipeline; `pattern_detection_events` accumulates rows for detected patterns; per-pattern metadata populated (sector/industry/adr_pct/atr%/90d/52w; market_cap NULL); `chart_render_id` non-NULL for successful renders; `data_asof_date` populated
- **S4**: re-run pipeline next session; `pattern_forward_observations` appends today's bar for previously-open detections; `provider` provenance tag present in `ohlc_today_json`; status transitions correctly
- **S5**: append-only verification (attempt UPDATE -> reject; attempt DELETE of a detection with observations -> RESTRICT; duplicate observation -> UNIQUE violation; INSERT-only path works) -- may be mechanical-test-covered per Codex assessment
- **S6**: chart_render chain: `pattern_detection_events.chart_render_id` -> `chart_renders.chart_id` -> `chart_svg_bytes` verifiable; chart-render-failure path leaves `chart_render_id` NULL + emits `warnings_json`
- (NOTE: browser MCP may be unavailable -- the proven fallback is operator-driven browser with orchestrator running the DB-side probes step-by-step; plan the gate so DB-verifiable steps S2/S3/S4/S5/S6 are scriptable.)

### §2.5 Codex two-chain placement + watch items (plan §J)

- **TWO chains** per OQ-20 + §1.5 L6 (writing-plans: completeness lens + schema/semantics lens; executing-plans designed similarly).
- Plan §J SHALL enumerate the 18 brainstorm adversarial watch items (brainstorm dispatch brief §5) + the brainstorm return-report forward-binding lessons explicitly.
- FB-N1: attempt MCP; fall back to `codex exec` CLI if it times out; bank recurrence.

### §2.6 Schema impact analysis (plan §K)

Plan SHALL design (NOT re-decide) the v22 introduction:
- Confirm baseline is 21 `*.sql` files; `0022` is the ONLY new migration (no v23).
- `pre_version == 21` STRICT backup gate (NOT `<=`); copy the Phase 9 `pre_version == 16` clause shape verbatim.
- gotcha #9 explicit BEGIN/COMMIT/ROLLBACK; rollback-through-runner test (malformed `0022` variant asserts `conn.in_transaction == False` post-failure + tables absent).
- gotcha #11 paired: CHECK enums (status; source) + Python constants + dataclass `__post_init__` validators + `_row_to_*` mappers all in the SAME task.

---

## §3 Open questions (Codex chains SHOULD surface answers; most resolved)

The spec's 20 OQs are resolved (15 in-spec; 5 LOCKed at §1.3). Residual writing-plans-phase questions for the Codex chains to lock in the plan:

1. Exact `0022` index set + names (§4.5 rationale -> concrete `CREATE INDEX` statements). Plan locks.
2. The config block shape + location for the 30/60 windows (OQ-18) -- which cfg file/section; defaults; validation. Plan locks.
3. `structural_anchors_json` exact serialization per detector class (full evidence asdict + window per §6.3) -- plan pins the shape + a round-trip test.
4. `finviz_screen_state` canonicalization (§9.4) -- exact JSON keys; plan pins.
5. The observe-step DAG insertion point in `runner.py` (after the pattern_detect block, before schwab_snapshot/charts) -- plan pins the exact call-site + the warnings_json accumulator wiring.
6. Per-task commit cadence preface (plan §G.0) -- enumerate any consolidations; gotcha #13 cumulative-regression-cascade audit at each Codex round.

---

## §4 OUT OF SCOPE (do not design into the plan)

- Backfill of `pattern_detection_events` from existing `pattern_evaluations` (V2 candidate)
- SQLite BEFORE UPDATE/DELETE triggers (OQ-10 LOCK: repo-layer only in V1+; triggers are V2)
- Persisting `market_cap` to `candidates` (OQ-16 LOCK: NULL in V1+; V2 dependency)
- Relaxing L2 LOCK to force a Schwab market-data fetch (OQ-17 rejected alternative)
- The real-time ruleset replay engine + `triggered_closed_at_*` status emission (Phase 15+; the substrate ENABLES it but does NOT build it)
- Operator failure-mode classification surface (V1++)
- Cross-pattern composite signals; ML re-ranker; drift monitoring; active alerting
- chart-render backfill for historical detections
- Schema migrations beyond v22 (v23 belongs to Sub-bundle 3)
- NEW HTMX endpoints / surfaces (Sub-bundle 2 is pipeline + schema)
- Sub-bundle 3/4/5 scope (Sec 9.1 Q1 serial LOCK)
- V2 candidates banked at spec §13 + return report
- CLAUDE.md / orchestrator-context archive-splits

---

## §5 Adversarial review (Codex) -- TWO chains (OQ-20 LOCK)

Invoked by `copowers:writing-plans` after the plan draft. **Run TWO chains** (§1.5 L6): chain #1 plan-completeness/implementation-feasibility lens; chain #2 schema/semantics-hardening lens. Each converges to NO_NEW_CRITICAL_MAJOR.

**Adversarial review watch items (LOAD-BEARING; inherit the brainstorm dispatch brief §5 18 items + the relocated Expansion #N catalog at `docs/orchestrator-context.md`)**:

1. **Brief-vs-production-function-signature verification (#2 + cascade-call-graph)** -- re-verify `_step_pattern_detect`, `resolve_ohlcv_window`, `render_theme2_annotated_svg`, `refresh_chart_render`, the lease/warnings_json accumulator, `_apply_migration` signatures against current production at plan time; cite file:line.
2. **SQL skeleton column verification (#4 + JOIN-cardinality + runtime-binding-shape)** -- every `0022` DDL column + every repo SQL verified against migrations; the observations IN-clause uses dynamic-`?` expansion + empty-input short-circuit.
3. **Schema-CHECK + Python-constant + dataclass-validator paired (#11)** + read-path mappers same task; CHECK enums (status; source) mirror Python constants + `__post_init__`.
4. **Migration runner discipline (#9)** -- explicit BEGIN/COMMIT/ROLLBACK; `pre_version == 21` STRICT; rollback-through-runner test.
5. **Append-only enforcement (OQ-10 LOCK)** -- repo-layer no-update/delete + UNIQUE + RESTRICT FK; discriminating tests at multiple layers.
6. **#27 silent-skip-without-audit** -- detect empty-pool + observe empty-pool/no-bar + chart-render-failure emit `warnings_json`.
7. **#26 + #37 elimination-by-construction kept honest** -- select-by-`observation_date` + freeze; never blind-last-row; never re-read a past date from a later archive; the `data_asof_date` column + forward-walk test.
8. **Per-pattern metadata sourcing (#4 + §9 redesign)** -- ATR%/90d/52w computed from already-fetched bars; sector/industry/adr_pct from `candidates`; market_cap NULL; NO new yfinance/Schwab fetch (L2).
9. **chart_render integration** -- REUSE theme2_annotated + dedicated `render_theme2_annotated_svg`; `ON DELETE SET NULL` nullable audit linkage; coexists last-writer-wins with the exemplar writer; failure -> NULL + warnings.
10. **OQ-17 provenance tag** -- `provider` recorded in `ohlc_today_json`; discriminating test asserts the tag round-trips.
11. **Status state machine completeness (OQ-18)** -- all transitions enumerated; 30/60 config-surfaced; per-class invalidation (§7.3.1); ruleset-agnostic subset only.
12. **Backwards-compat with `pattern_evaluations` (L7)** -- coexist; existing detector tests stay green.
13. **Empty-input handling (#4 sub-refinement)** -- empty patterns-detected + empty open-detections-to-observe both tested.
14. **Taxonomy/attribution propagation (#11 promotion)** -- the `status` + `source` enums propagate to dataclass + mapper + serializer + fixtures; the `provider` attribution field consumed by field, not value-matching.
15. **Cumulative regression cascade audit (#13)** -- post-fix sweep each round; §G.0 commit-cadence preface.
16. **Test fixture shape vs production emitter shape** (Phase 12 C.D family) -- fixtures match the production INSERT shape for both tables exactly.
17. **L2 LOCK source-grep** -- `tests/integration/test_l2_lock_source_grep.py` continues passing; ZERO new `schwabdev.Client.*` call sites; plan cites this.
18. **ASCII discipline (#16/#32)** -- declare scope across all NEW files (migration SQL comments, repos, dataclasses, observe-step) in §K.
19. **`Co-Authored-By` footer suppression** -- explicit citation; ~616+ ZERO drift streak.

---

## §6 Deliverable shape

**Plan document at `docs/superpowers/plans/<YYYY-MM-DD>-phase14-sub-bundle-2-temporal-log-plan.md`:**

- §A Goals + non-goals
- §B File map (per-file diff projections; exact paths + line ranges from production)
- §C Surface-by-surface integration analysis (migration / repos / detect-extension / observe-step / chart-capture / metadata)
- §D Out-of-scope explicit list
- §E Operator-paired locks reverification (cumulative LOCK summary table: Sec 9.1 + L1-L8 + spec §2 + this brief §1 + the 5 OQ dispositions)
- §F Cumulative discipline + watch items applied (per task)
- §G Per-task slicing (T-2.1 .. T-2.6; per-task acceptance criteria + step-checkbox TDD)
- §G.0 Commit cadence preface (~15-25 commits total estimate)
- §H Test surface (fast/slow split; ~50-100 fast target; per-task distribution table + sum-check)
- §I Operator-witnessed gate runbook (S1-S6; DB-scriptable steps for the browser-MCP-unavailable fallback)
- §J Codex MCP TWO-chain placement (writing-plans + executing-plans; FB-N1 fallback note)
- §K Schema impact analysis (v22 introduction; backup-gate STRICT; runner discipline; ASCII scope)
- §L Test fixture strategy (per table + per step)
- §M Forward-binding lessons (from brainstorm return report; carry forward)
- §N Self-review checklist (pre-Codex; apply the relocated Expansion #N catalog)

**Target line count: ~2000-3500 lines.**

**Commit message stem:** `docs(phase14-sub-bundle-2-plan): writing-plans -- <N> Codex rounds (2 chains) -> NO_NEW_CRITICAL_MAJOR convergent`.

---

## §7 If you get stuck

- If a code-read surfaces a signature/schema drift NOT cited in the spec, ESCALATE to orchestrator (do NOT silently patch). The brainstorm verified surfaces at R1-R4; if production drifted since `9fc661b`, escalate.
- If Codex pushes back on the **2-table design** (proposes consolidation), HOLD THE LINE -- commissioning brief Sec 2.5 + spec §2.4 LOCK.
- If Codex pushes back on **append-only / no-UPDATE paths**, HOLD THE LINE -- L1 + L2 + OQ-10 LOCK + #26/#37 rationale.
- If Codex pushes back on the **chart `ON DELETE SET NULL` posture** (proposes RESTRICT), HOLD THE LINE -- spec §8.3 + OQ-19 (RESTRICT deadlocked the run-prune CASCADE + collided with the exemplar path).
- If Codex pushes back on the **v22 schema** (proposes deferring), HOLD THE LINE -- Sec 9.1 Q3 V1+ requires the substrate.
- If Codex pushes back on the **30/60 windows or repo-layer enforcement**, HOLD THE LINE -- OQ-18 + OQ-10 operator LOCKs.
- If the Codex MCP tool times out (FB-N1), use `codex exec` CLI; do NOT skip the adversarial chain.
- DO NOT propose schema migrations beyond v22.
- DO NOT add `Co-Authored-By` footer to ANY commit. DO NOT `--no-verify`.
- DO NOT widen scope to other Phase 14 items or Phase 15+.
- DO NOT design backfill / replay-engine / triggers in V1+.

---

## §8 Return report shape

After BOTH Codex chains converge + before final commit, draft `docs/phase14-sub-bundle-2-temporal-log-writing-plans-return-report.md`:

1. Final HEAD on branch + commit count breakdown (per-commit Codex round attribution; BOTH chains).
2. Codex round chains (chain #1 + chain #2 summary tables + convergent shape).
3. Plan line count + per-section breakdown.
4. Pre-locked decisions verbatim verification (Sec 9.1 + L1-L8 + spec §2 + this brief §1 + the 5 OQ dispositions).
5. §3 Open Questions: which Codex resolved + which locked at plan-authoring time.
6. Codex Major findings ACCEPTED with rationale (if any; ZERO strongly preferred).
7. Per-task acceptance criteria summary (T-2.1 .. T-2.6).
8. Test surface verification (~50-100 fast projected; per-task distribution + sum-check).
9. Forward-binding lessons for executing-plans dispatch.
10. Schema impact verdict (v22 introduced; backup-gate STRICT; runner discipline).
11. Cumulative gotcha set application summary (per task).
12. Worktree teardown status.
13. ZERO Co-Authored-By footer drift confirmation (`%(trailers)` across all branch commits).
14. CLAUDE.md status-line refresh draft text.
15. Executing-plans dispatch readiness summary (OQs all resolved; two-chain executing-plans posture designed).

---

## §9 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES -- branch `phase14-sub-bundle-2-temporal-log-writing-plans`. Worktree directory `.worktrees/phase14-sub-bundle-2-temporal-log-writing-plans/`.
- **Model:** defer to harness default.
- **Expected duration:** ~2.5-4 hours writing-plans + ~1-2 hours for 2 Codex chains. Total ~4-6 hours operator-paced.
- **Codex MCP chain count:** TWO chains (per OQ-20 LOCK + §1.5 L6). FB-N1: `codex exec` CLI fallback if MCP times out.

---

*End of brief. Phase 14 Sub-bundle 2 writing-plans dispatch -- produce a per-task implementation plan derived from the 788-line brainstorm spec (2 NEW append-only tables via v22 migration + NEW `_step_pattern_observe` + per-pattern metadata enrichment + chart_render bytes capture; 6 task buckets T-2.1..T-2.6; ~15-25 commits + ~50-100 fast tests target); ~2000-3500 line plan; TWO Codex chains. The 5 flagged OQs are LOCKed (§1.3); HOLD THE LINE on the 2-table + append-only + #26/#37-by-construction + v22 + ON DELETE SET NULL chart-FK + 30/60-window LOCKs. OUTPUT: implementation plan that executing-plans phase can dispatch directly to an implementer.*
