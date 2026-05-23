# Phase 13 T4.SB Executing-Plans Return Report

**SHIPPED:** 2026-05-22 PM (executing-plans phase complete; ready for `--no-ff` integration merge).

**Branch:** `phase13-t4-sb-executing-plans` (HEAD `6bfd81c`; baseline `cbc5945`).

**Codex MCP adversarial-critic verdict:** R3 NO_NEW_CRITICAL_MAJOR (3 rounds; 0 CRITICAL + 4 MAJOR + 3 MINOR cumulative; ALL RESOLVED in-place).

---

## §1 Status

- **6 task commits + 5 Codex fix commits = 43 commits cumulative** on `phase13-t4-sb-executing-plans` branch.
- **Final fast test count:** 5778 PASS + 1 SKIP (known pre-existing flag-classifier fixture-shape pin per CLAUDE.md gotcha; un-skips when corpus shape compatible). **Delta from baseline 5670 = +108** (within plan §F.1 budget of +90 to +135).
- **Schema v21 UNCHANGED** through all 6 tasks (T4.SB is schema-LOCKED per spec §A.2).
- **Ruff `swing/` 0 E501** preserved; ruff clean on all T4.SB surfaces. Pre-existing E501 violations in `research/finviz_pool_analysis/` + `research/harness/earnings_proximity/scripts/sp1500_findings_aggregate.py` UNTOUCHED.
- **ZERO new Schwab API calls** (L2 LOCK preserved).
- **ZERO Co-Authored-By footer** across all 43 commits — verified via `git log --format=fuller cbc5945..6bfd81c | grep -ci "Co-Authored-By"` returning 0. **~430 cumulative project-wide streak** preserved through this dispatch.
- **Phase 13 sub-bundle ship count: 12 of 12 — Phase 13 FULLY CLOSED** marker landed at T-T4.SB.6 commit `c62fd98` per spec §K + plan §L.

## §2 Codex MCP adversarial-critic chain shape

**3-round chain; converged at R3 NO_NEW_CRITICAL_MAJOR.**

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 2 | 2 | ISSUES_FOUND |
| R2 | 0 | 2 | 1 | ISSUES_FOUND |
| R3 | 0 | 0 | 0 | NO_NEW_CRITICAL_MAJOR |

**Cumulative defects caught + resolved:** 0 CRITICAL + 4 MAJOR + 3 MINOR (all in-place; zero advisory-only).

### R1 findings (resolved across 4 commits)

| Finding | Severity | Resolution commit | Discriminating test |
|---|---|---|---|
| R1.M1 `watchlist_expand` mixed-anchor race (VM + JIT independent connections; pipeline completing mid-render → old-run metadata + new-run chart bytes) | Major | `cb7e8be` | `tests/web/test_watchlist_expand_single_pipeline_anchor.py::test_watchlist_expand_threads_single_pipeline_anchor` |
| R1.M2 F6 transient-empty defense incomplete on cache-HIT path (`get_or_render_surface` returns cached `b""` verbatim, bypassing ChartRender non-empty barrier) | Major | `0b96865` | `tests/web/test_chart_jit.py::test_get_or_render_surface_treats_empty_cached_bytes_as_miss` |
| R1.m1 Closer E2E `return True` fallback on missing hyp-progress element (template drift = silent false-pass) | Minor | `5f2f148` | Replaced template scraping with direct VM-layer assertion (`build_hypothesis_progress_card_vm`) |
| R1.m2 `swing diagnose` raw `sqlite3.connect()` (typoed path auto-creates empty DB + unwrapped OperationalError) | Minor | `9629f5b` | `tests/cli/test_diagnose_db_path_validation.py` (3 subcommands × missing-path rejection) |

### R2 findings (resolved in single combined commit)

| Finding | Severity | Resolution commit | Discriminating test |
|---|---|---|---|
| R2.M1 `/expand` mixed-anchor race extends to no-run scenario (VM `pipeline_run_id=None` → helper falls back to "resolve latest now" → suppresses unavailable banner) | Major | `6bfd81c` | `test_watchlist_expand_no_run_does_not_pick_up_mid_request_pipeline` |
| R2.M2 `/row` route same race — `build_watchlist_row` resolves own latest run for tags/pivot but JIT call re-resolves (row metadata from run N + thumbnail from run N+1) | Major | `6bfd81c` | `test_watchlist_row_threads_single_pipeline_anchor` + `test_watchlist_row_no_run_does_not_pick_up_mid_request_pipeline` |
| R2.m1 Partial-anchor silent fallback masks call-site bugs | Minor | `6bfd81c` | `test_resolve_jit_chart_bytes_partial_anchor_returns_none_and_warns` (both XOR directions) |

### R3 verdict

NO_NEW_CRITICAL_MAJOR — chain converged. No advisory-only items banked.

## §3 Per-task summary

### T-T4.SB.1 — Item 1 sensitivity harness (research/) + Item 7 Phase 1 diagnostic + `swing diagnose` CLI

**Commits (8):** `dc86a4c` `d864bd0` `753b3ab` `a34ea13` `1c00a77` `ca1d6f2` `9274bb2` `aafc3c7` + `6c996d5` (ruff cleanup)

**Test delta:** +20 fast tests (5670 → 5690). Below plan §F.1 budget of +30-40 but all spec-bound discriminating assertions in plan §B.1 step bodies are present + GREEN.

**Key decisions:**
- 17-variable enumeration LOCKED (NOT `>= 10` as §G.1 stub implies; per R2 LOCK in plan §B.1 step 1A.1 set-equality assertion): 2 gate + 3 trend_template numeric + 8 vcp + 1 risk + 3 rs.
- `Config.from_defaults()` classmethod added inline at `swing/config.py:398-407` (plan calls it without specifying existence; resolves via `Path(__file__).resolve().parent.parent / "swing.config.toml"`).
- Plan-template `from swing.cli import cli` → adapted to `from swing.cli import main as cli` per project convention.
- Inline plant-fixture helpers (`_plant_minimal_eval_run_fixture`, `_plant_eval_runs_with_known_distribution`, `_plant_minimal_db`) defined per-test module; production-shape against migration `0001_phase1_initial.sql`.

**Cumulative gotcha applications:** Expansion #11 (taxonomy propagation) — `kind` enum `{gate, threshold_additive, threshold_multiplicative}` propagates uniformly through `SweepVariable` → `SweepEntry` → CSV header position 2 → markdown matrix Kind column → all test fixtures. FIRST clean-on-arrival validation of Expansion #11 candidate banked from writing-plans phase.

### T-T4.SB.2 — Item 7 broader audit + delimiter-aware label-match helper + cross-bundle pin row 13

**Commits (8):** `fbc7710` `68de6e3` `2fe91d8` `afeca2e` `0436072` `06430cf` `d7de966` + `27ed086` (ruff SIM103)

**Test delta:** +17 fast tests (5690 → 5707).

**Key decisions:**
- 3-rule delimiter-aware match contract LOCKED in `swing/metrics/label_match.py`: (1) case-fold exact equality; (2) space-delimited prefix; (3) semicolon-delimited prefix. SQL helper returns 3-tuple `(fragment, [raw_lowered, escaped, escaped])` per Codex R4 M#2 brainstorm LOCK (raw-vs-escaped asymmetry; equality predicate must NOT escape `_` and `%`).
- `count_per_cohort` orphan-fallback preservation via second SQL query with AND-NOT chaining of per-name delimiter-aware fragments + empty-registry defensive branch.
- Pre-existing `tests/metrics/test_cohort.py::test_list_trades_case_difference_does_not_match` semantically inverted (`..._matches_under_three_rule_contract`) — Rule 1 is case-INSENSITIVE per spec.
- `_KNOWN_SURFACES` registry dispositions flipped WIRING DEFECT → LIVE for all 4 surfaces; `match_strategy` updated `exact_equality`/`prefix_match` → `delimiter_aware`.

**Cumulative gotcha applications:** Expansion #10 sub-discipline (d) SQL LIKE binding asymmetry + sub-discipline (e) orphan-label preservation + Expansion #8 SQL aggregation UNIT audit (single-table `COUNT(*)` — no JOIN inflation).

### T-T4.SB.3 — Item 5 architecture (chart_jit.py NEW + JIT wiring + pre-gen scope reduction)

**Commits (9):** `6d2b0a8` `d958600` `74af644` `269cd53` `e56d29a` `23753f5` `fdcfade` `07e8608` `b262dae` (ruff autofix)

**Test delta:** +24 fast tests (5707 → 5731).

**Key decisions:**
- NEW `swing/web/chart_jit.py:get_or_render_surface` — cache-hit short-circuit / cache-miss → OHLCV → render → write-through; F6 construction-barrier defense + (extended in R1 fix) empty-bytes cache-hit re-render.
- DB connection acquired per-request via `sqlite3.connect(str(cfg.paths.db_path))` (NOT `app.state.db_conn` which doesn't exist) — mirrors `swing/web/routes/account.py` precedent.
- `_RENDERERS` registry module-level dict (mockable per-test via `importlib.reload`).
- Renderer-kwargs uniformity LOCK per Codex R4 M#3: `_step_charts` pre-gen `ma_lines` changed from `[50, 150, 200]` → `[20, 50]` to match JIT default for cache-collision avoidance. **Operator-witnessed S2 gate item** (visual change in watchlist pre-gen thumbnails).
- `_step_charts` pre-gen scope reduced: hyprec_detail loop REMOVED; watchlist `n=5` (was top-10).
- OQ-5.1 R4 manual prune CLI shipped: `swing diagnose prune-chart-cache --db PATH --older-than DAYS`.
- 4 pre-existing tests adapted to new inline-SVG cascade behavior (each still discriminating against regression; not trivially passing).

**Cumulative gotcha applications:** Expansion #10 sub-discipline (a) architecture-location (NEW module; chart_scope.py LOCKED read-only) + sub-discipline (c) renderer-kwargs uniformity LOCK (cache-collision test).

### T-T4.SB.4 — Item 2 labeler contract widening (rule_criteria + narrative alias)

**Commits (5):** `10de427` `a33fa6e` `2ddfda8` `6af7e5c` `d3e7894`

**Test delta:** +25 fast tests (5731 → 5756). Over plan §F.1 budget of +10-15 but all discriminating coverage warranted.

**Key decisions:**
- `_persist_silver_label` plan-template helper doesn't exist; envelope assembly is inline in `fire_claude_silver_label`. Tests exercise via monkeypatched dispatch (mirrors `tests/patterns/test_labeling.py` precedent).
- **DEVIATION**: Sub-task 4E shipped as NEW `label-corpus-all` subcommand (NOT `--corpus-all` flag on existing `label-exemplars`). Justification: `label-exemplars` carries 4 `required=True` options (`--ticker`, `--start`, `--end`, `--pattern-class`); a `--corpus-all` flag would require operator to pass nonsense values OR introduce click validation tangle. NEW subcommand preserves separation of concerns; emit-only JSONL; gold + synthetic + perturbation EXCLUDED. Adjudicated APPROVED by review pass.
- `rule_criteria` per-element validation: `name` non-empty string + `status` in `{"pass", "fail"}` frozenset; optional `evidence_value`/`threshold`/`tolerance` accept any type (VM parser stringifies at read path).
- Envelope key omission discipline: `rule_criteria` key ABSENT from envelope when None (NOT serialized as `null`); empty `[]` PERSISTED (meaningful "zero criteria" signal distinct from None). `narrative` alias ALWAYS populated even when `rule_criteria` None.
- 5 per-pattern-class example payloads in `.claude/agents/pattern-labeler.md` — criterion-name lists verified to match `spec_static.get_rule_criteria` byte-for-byte.

**Cumulative gotcha applications:** Literal-runtime-validation via explicit frozenset; audit-envelope empty-state uniformity; Expansion #10 sub-discipline (b) template-VM-parser-emitter triangulation (template + parser ALREADY correct per writing-plans-phase analysis; fix lived purely at EMIT side).

### T-T4.SB.5 — Items 3+4+6 cosmetic/UX bundle (OQ-X.1 LOCK)

**Commits (3):** `3cb9d44` `49258a5` `7c6fe4c`

**Test delta:** +12 fast tests (5756 → 5768). Within plan §F.1 budget of +8-12.

**Key decisions:**
- Item 3 volume y-tick stripping via `ax_vol.set_yticks([])` in both `render_market_weather_svg` + `render_hyprec_detail_svg`. ASCII-only output (no mathtext introduced).
- Item 4 lightning glyph removed from `watchlist_row.html.j2`. Existing `test_lightning_trigger_unchanged_uses_entry_target` renamed + inverted to `test_lightning_glyph_absent_post_item_4_removal`.
- Item 6 partial-rewire — `chart_svg_bytes_for_row` explicit template param; `watchlist.html.j2` + `partials/watchlist_top5_section.html.j2` (NOT bare `dashboard.html.j2`) pass via `{% set %}` in row loop. Plan-template line numbers updated (lightning glyph block moved 14→20 post-T-T4.SB.3 refactor; chart-bytes-set moved 9→15).
- **3 operator-witnessed S2 gate items** (all visual): volume y-tick label stripping; lightning glyph absence; expand-collapse thumbnail preservation.

### T-T4.SB.6 — Closer (E2E + cross-bundle pin promotion + Phase 13 FULLY CLOSED docs)

**Commits (4):** `be84f44` `97170e7` `5d6f613` `c62fd98`

**Test delta:** +2 fast tests (5768 → 5770; +1 fast E2E + 1 un-skipped v20 atomic-landing pin per Phase 13 main plan §H.3 schedule).

**Key decisions:**
- Fast E2E scoped to Items 4+5+6+7 (Items 1+2+3 covered by discrete tests; Item 1 sensitivity harness CLI is separate from TestClient flow; Item 2 labeler envelope exercised in T-T4.SB.4 discrete tests; Item 3 matplotlib-layer visual not amenable to E2E SVG-byte assertion).
- Inlined `seeded_db` + `_seed_watchlist_and_evaluation_run` helpers because `tests/integration/` does NOT inherit `tests/web/conftest.py`.
- Cross-bundle pin row 13 GREEN at all 4 surfaces (`list_trades_for_cohort` + `count_per_cohort` + `hyp_progress_card_vm` + `cli_compute_hypothesis_progress_breakdown`).
- Phase 13 main plan §H.3 row 13 appended.
- Triage-agenda artifact `docs/phase13-closer-next-phase-triage.md` shipped per §1.5.2 amendment (3 paths A/B/C; cross-references to T-T4.SB.1 deliverables).
- CLAUDE.md current-state line flipped: "Phase 13 sub-bundle ship count: 11 of 11 SHIPPED — T4.SB closer arc IN-FLIGHT" → "Phase 13 sub-bundle ship count: 12 of 12 SHIPPED — Phase 13 FULLY CLOSED 2026-05-22 PM". Plus Note 2026-05-22 PM #4 paragraph.
- `docs/orchestrator-context.md` + `docs/cycle-checklist.md` + `docs/phase3e-todo.md` all updated per plan §L.1.
- Un-skipped `tests/data/test_v20_migration.py::test_v20_atomic_landing_python_constants_validators_paired` per Phase 13 main plan §H.3 row 12 schedule.

### Codex R1+R2 fix commits (5 commits post-T-T4.SB.6)

`cb7e8be` watchlist_expand single anchor (R1.M1)  
`0b96865` chart_jit empty cached bytes (R1.M2)  
`5f2f148` closer E2E VM-layer assertion (R1.m1)  
`9629f5b` diagnose subcommands DB-path validation (R1.m2)  
`6bfd81c` watchlist /row + /expand no-run + partial anchor guard (R2.M1+M2+m1)

Cumulative fix-tests: +8 fast tests across the 5 fix commits.

## §4 V1 simplifications banked with V2 dependency cited

Per writing-plans return report §4 + cumulative banking discipline (forward-binding lesson #7); items 1-10 carried forward from writing-plans phase + items 11-20 surfaced at executing-plans phase:

**Carried forward from writing-plans phase:**
1. Sensitivity-harness 15-of-17 threshold deltas-0 V1 (V2 OHLCV criterion-evaluator harness)
2. `allowed_miss_names` tuple-set sweep excluded (V2 set-membership combinatorial grid)
3. `benchmark_ticker` string-identifier excluded (V2 per-benchmark sub-sweep + ticker-discovery)
4. `metrics_wiring_audit._KNOWN_SURFACES` hand-maintained registry (V2 decorator-marked codegen)
5. Corpus-all re-label operator-paired (V2 auto-firing with Agent-tool harness)
6. OQ-5.1 R4 manual prune CLI (V2 automated R2/R3 retention policy)
7. OQ-5.2 sync JIT no-timeout (V2 async-JIT HTMX placeholder swap)
8. `hyprec_detail` surface-name grandfathered (V2 dedicated `watchlist_expanded` surface enum value)
9. OHLCV cache validity at original `asof_date` V2-dependent for threshold-variable resimulation
10. `_known_surfaces` R1 best-guess seed (V2 codegen)

**Surfaced at executing-plans phase:**
11. `Config.from_defaults()` resolves project root via `Path(__file__).resolve().parent.parent` (V2: env-var or pyproject-metadata for non-conventional install layouts)
12. 17-variable enumeration hardcoded (V2: decorator-marked variable registry per cfg dataclass)
13. `_KNOWN_SURFACES` registry hand-maintained — V1 stub assertion only on presence (V2: pin disposition values as discriminating regression)
14. `audit_surface_match_strategy` is V1 stub returning row unchanged (V2: T-T4.SB.2 broader audit per-surface discriminating queries)
15. Renderer-kwargs `[20, 50]` pre-gen ma_lines vs prior `[50, 150, 200]` for cache-collision uniformity LOCK (V2: operator-paired decision on canonical MA overlay set)
16. `OhlcvCache.get_or_fetch(ticker, window_days=200)` window pinned at 200 (V2: per-surface window tuning)
17. JIT helper does not call `chart_scope.resolve_chart_scope` — renders SVG for any ticker with OHLCV data regardless of pipeline_chart_targets scope (V2: optional pre-render scope filter to mirror chart_scope.py classification)
18. Prune CLI default behavior is "manual operator-invoked"; no automatic eviction (V2: automated time-based eviction on pipeline-end OR per-row TTL column)
19. Watchlist expanded inline-SVG uses shared `hyprec_detail` surface — V1 cache-key reuse with hyp-recs route (V2: dedicated `watchlist_expanded` surface enum value + renderer-kwargs distinction)
20. `rule_criteria` optional-element type validation — V1 validates `name` + `status` only; optional fields (`evidence_value`/`threshold`/`tolerance`) accept any type (V2: tighten when operator usage surfaces type confusion)
21. `label-corpus-all` does NOT auto-fetch bars — emit payload has `bars: []`; operator supplies via `--window-bars-file` on per-row `label-exemplars` persist call (V2: `--bars-cache-dir` option to reuse cached bars per row)
22. `label-corpus-all` emit-only — no `--silver-response-dir <dir>` bulk-persist subcommand (V2: bulk persist iterator consuming directory of response files)
23. Legacy envelopes NOT re-written with `narrative` alias — pre-T4.SB.4 silver rows render "no narrative" placeholder rather than retroactively populating from `geometric_evidence_narrative` (V2: backfill migration OR VM parser fallback)

## §5 Forward-binding lessons banked

### Lesson #1: OQ-5.4 Option A LOCK extends to ALL `/watchlist/*` routes, not just `/expand` (Codex R1.M1 + R2.M1 + R2.M2 cumulative)

**Surfaced via:** R1.M1 (`/expand` initial fix) + R2.M1 (`/expand` no-run case missed by R1 fix) + R2.M2 (`/row` same race as `/expand`).

**Pattern:** When introducing a "single-anchor-binding" discipline for one route handler, audit ALL sibling routes that interact with the same data layer + cache pipeline. A fix at one handler doesn't transitively close the race at others.

**Pre-empt:** Writing-plans + executing-plans §5 watch item for any new "single-anchor" architectural discipline: enumerate ALL routes consuming the affected VMs / cache surfaces + verify each carries the anchor binding explicitly. Add discriminating mid-request-mutation tests per route, NOT just the headline route.

**Pattern complement:** Existing T3.SB2 hotfix surface-guard widening gotcha (4 sites needed audit when widening 1 constant) — same family extended to route-handler-side anchor discipline.

### Lesson #2: F6 transient-empty defense MUST extend to cache-HIT read path, not just write path (Codex R1.M2)

**Surfaced via:** R1.M2 — `get_or_render_surface` returns cached `b""` verbatim, bypassing ChartRender non-empty barrier.

**Pattern:** F6 cumulative gotcha was originally written for direct-API wrappers (yfinance/broker APIs). When applied to write-through cache architecture:
- ChartRender's `__post_init__` empty-bytes rejection guards the WRITE path (any new bytes flowing through the dataclass)
- But READ path returning cached blobs from prior writes (which may have bypassed the dataclass — e.g., legacy data, direct-SQL inserts, future regressions) is UNGUARDED

**Pre-empt:** For any write-through cache helper, the READ path must ALSO guard against empty/invalid cached values: treat as cache miss + WARN log + force re-render + write-through replacement. Discriminating test: plant via raw SQL bypassing dataclass barrier + verify re-render fires.

### Lesson #3: Plan-template DB-connection patterns need defense-in-depth pre-validation (Codex R1.m2)

**Surfaced via:** R1.m2 — `swing diagnose` subcommands' raw `sqlite3.connect()` auto-creates empty SQLite file on typoed path + unwraps `OperationalError`.

**Pattern:** Any new CLI subcommand consuming a DB path MUST pre-validate path existence BEFORE `sqlite3.connect`. Plus wrap subsequent `OperationalError` in `click.ClickException` (service-layer-ValueError-wrap gotcha extends to DB operational errors). Use a shared helper (`_validate_diagnose_db_path` precedent in `swing/cli.py`).

**Pre-empt:** Writing-plans §5 watch item for new CLI DB-consuming subcommands — enumerate per-subcommand: (a) DB-path pre-validation; (b) OperationalError wrap; (c) discriminating test asserting missing-path raises ClickException (NOT auto-creates file).

### Lesson #4: Template-scraping E2E assertions MUST fail closed on missing element (Codex R1.m1)

**Surfaced via:** R1.m1 — `_post_fix_cohort_n_closed_ge_one` returned `True` when hyp-progress element absent.

**Pattern:** Any E2E test that scrapes template output for a substring or attribute value MUST fail-closed when the element cannot be located. Template drift (selector renames, structural refactor) would otherwise create silent false-passes. **Better pattern**: assert at the VM/data layer directly when possible (`build_*_vm` returns frozen dataclass; assert fields directly), bypassing template parsing entirely.

**Pre-empt:** Any new E2E test fixture that scrapes HTML — code review checklist: (a) does every code path return a verifiable assertion? (b) is there a fail-closed branch for missing elements? (c) can the assertion be moved to VM layer for higher discrimination?

### Lesson #5: Partial-anchor silent-fallback masks call-site bugs (Codex R2.m1)

**Surfaced via:** R2.m1 — `_resolve_jit_chart_bytes` falls back to latest when exactly one of `pipeline_run_id` / `data_asof_date` is None.

**Pattern:** Helper functions accepting multi-field "binding" parameters (anchor pairs, scope tuples, etc.) MUST refuse partial inputs with explicit log+degrade OR raise, NOT silent fallback. Silent fallback masks call-site bugs (typed-tuple destructuring error; future refactor passing only one field).

**Pre-empt:** Any new helper with multi-field binding parameters — explicit XOR guard at the top of the function: `if (a is None) != (b is None): log/raise`. Discriminating test asserting partial input is rejected.

## §6 Cumulative streaks

- **ZERO Co-Authored-By footer trailer drift** — ~430 cumulative across project through this dispatch (43 T4.SB executing-plans commits + ~387 prior). `git log --format=fuller cbc5945..6bfd81c | grep -ci "Co-Authored-By"` returns 0.
- **C.C lesson #6 cumulative validations** — 30th NOTABLE at executing-plans phase. **Expansion #11 candidate FIRST clean-on-arrival** (taxonomy propagation audit — `kind` enum already scrubbed across `SweepVariable` + `SweepEntry` + CSV + markdown + tests during writing-plans phase; executing-plans phase ran ZERO regressions on this surface). **Expansion #10 (architecture-location 5-sub-discipline) FIRST clean executing-plans validation** — all 5 sub-disciplines applied cleanly: (a) chart_jit.py NEW module (NOT chart_scope.py); (b) template-VM-parser-emitter triangulation; (c) cache-key + renderer-kwargs uniformity LOCK; (d) SQL LIKE binding asymmetry; (e) orphan-label preservation.
- **Phase 13 sub-bundle ship count** — 11 of 11 → 12 of 12 SHIPPED at T-T4.SB.6 SHIPPED. Phase 13 FULLY CLOSED.
- **Baseline 5670 fast tests → 5778 fast tests** (+108 net) — within plan §F.1 budget (+90 to +135).
- **Schema v21 LOCKED** through all 6 tasks + Codex fix commits.
- **ZERO new Schwab API calls** (L2 LOCK preserved).
- **Ruff `swing/` 0 E501** preserved.

## §7 30th cumulative C.C lesson #6 validation — per-expansion verdict

| # | Expansion | Pre-Codex applied? | Codex surfaced? | Verdict |
|---|---|---|---|---|
| 1 | Hardcoded-duplicate audit | Yes | No new widening | CLEAN N/A |
| 2 | Brief-vs-spec source-of-truth | Yes | No | CLEAN |
| 3 | Schema-CHECK vs semantic-contract | N/A | N/A (schema unchanged) | N/A |
| 4 | SQL-skeleton column verification | Yes | No | CLEAN |
| 5 | Cross-section spec inventory grep | Yes | No | CLEAN |
| 6 | Content-completeness audit | Yes (V1 stubs disposition-tracked) | No | CLEAN |
| 7 | Cross-row semantic scope | Yes | No | CLEAN |
| 8 | SQL aggregation UNIT audit | Yes | No | CLEAN |
| 9 | Form-render anchor lifecycle | N/A (no new hidden anchors) | N/A | N/A |
| 10 | Architecture-location 5-sub-discipline | Yes — all 5 applied | No regressions | CLEAN (first clean executing-plans validation post-banking) |
| 11 | Taxonomy propagation audit (NEW candidate) | Yes — `kind` enum scrubbed at writing-plans | No regressions | CLEAN (first clean-on-arrival validation; Expansion #11 candidate promoted from CANDIDATE to BINDING for 31st cumulative validation onwards) |

**Per-expansion summary:** ALL 7 expansions + 4 NEW candidate refinements + Expansion #11 candidate ran CLEAN at executing-plans phase. Codex MCP adversarial-critic chain caught NEW issues in a previously-unaddressed lesson family (single-pipeline-anchor binding extends to all routes consuming the affected VMs — Lesson #1 above). This banking becomes a candidate Expansion #12 / fresh forward-binding lesson for future arc dispatches.

## §8 Operator-witnessed S2-S5 gates (BINDING for post-merge session)

Per plan §H.4 — operator-paired browser/CLI session post-merge:

**S1 (inline; orchestrator-verified pre-merge)** — fast pytest + ruff + schema-unchanged-at-v21. **STATUS: GREEN**.

**S2 (browser; post-merge operator session)** — `/dashboard` confirm:
- [ ] Market-weather chart has no volume y-axis labels (Item 3)
- [ ] No lightning glyph on watchlist row even at trigger threshold (Item 4)
- [ ] Watchlist expand-collapse preserves thumbnail across full cycle (Item 6 Option 6B canonical-include)
- [ ] Sub-A+ hyp-rec expand renders chart inline (Item 5 JIT cache-hit OR live render)
- [ ] Hyp-progress card non-zero for "Sub-A+ VCP-not-formed" cohort (Item 7 fix; delimiter-aware match)

**S3 (CLI; post-merge operator session)** — `swing diagnose aplus-sensitivity --eval-runs 63 --output-dir exports/diagnostics/` (Item 1; sensitivity-harness output feeds §1.5.2 deferred Phase-14 decision). **Triage-agenda artifact at `docs/phase13-closer-next-phase-triage.md` enumerates the next-phase path A/B/C decision based on harness output.**

**S4 (CLI)** — `swing diagnose metrics-wiring --db <operator_db> --output exports/diagnostics/metrics-wiring-audit-postfix.md` (Item 7 broader audit; verify 4 dispositions LIVE).

**S5 (CLI)** — `swing patterns label-corpus-all --label-source claude_silver --limit 5` invocation OR per-exemplar `swing patterns label-exemplars ... ` with new contract — new envelope keys (`narrative` alias + `rule_criteria`) persisted (Item 2; operator-paired re-label-corpus V2-banked via EMIT-mode JSONL).

**Operator-paired post-T4.SB-SHIPPED triage meeting** — Phase 14 trigger / Applied Research focus / idle monitoring decision per §1.5.2 amendment; agenda at `docs/phase13-closer-next-phase-triage.md`.

## §9 §1.5 amendments encoded (per writing-plans dispatch brief)

- **§1.5.1** OQ-1.3 SCOPE EXPANSION — 1D parameter-sweep sensitivity harness shipped at T-T4.SB.1 (17 variables; kind taxonomy; V1-limitation paragraph in markdown output). VERIFIED.
- **§1.5.2** OQ-CL.2 deferred-until-diagnostic disposition — triage-agenda artifact stub at `docs/phase13-closer-next-phase-triage.md` shipped at T-T4.SB.6 commit `5d6f613`. VERIFIED.
- **§1.5.3** OQ-5.4 Option A LOCKED — dashboard reader binds to ONE pipeline_run anchor; JIT writes match anchor; `pipeline_run_id` field added to `WatchlistExpandedVM` + `WatchlistRowVM` per R1.M1 + R2.M2 Codex fixes (orchestrator-extension to original Option A LOCK). VERIFIED.
- **§1.5.4** OQ-1.4 REVISED to research-branch placement — sensitivity harness shipped under `research/harness/aplus_sensitivity/`; first method-record stub at `research/method-records/aplus-criteria-calibration.md`; `research/phase-0-tasks.md` "Next" promotion. VERIFIED.

## §10 References

- **Plan (BINDING):** `docs/superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md` at HEAD `9b2a4db`
- **Brainstorming spec (REFERENCE):** `docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md` at `f7dec0e`
- **Executing-plans dispatch brief:** `docs/phase13-t4-sb-executing-plans-dispatch-brief.md` at `cbc5945`
- **Writing-plans return report:** `docs/phase13-t4-sb-writing-plans-return-report.md` at `c8d21b9`
- **Triage-agenda artifact:** `docs/phase13-closer-next-phase-triage.md` (T-T4.SB.6 commit `5d6f613`)
- **Research-branch artifacts:** `research/harness/aplus_sensitivity/` + `research/method-records/aplus-criteria-calibration.md` + `research/studies/aplus-criterion-sensitivity-2026-05-22.md`
- **Cross-bundle pin:** `tests/metrics/test_phase13_t4_sb_cross_bundle_pin_row_13.py` (4 surfaces parametrized; GREEN; row 13 appended to Phase 13 main plan §H.3)
- **Closer E2E:** `tests/integration/test_phase13_t4_sb_closer_e2e.py` (Items 4+5+6+7 in one TestClient round-trip; VM-layer assertion post R1.m1 fix)

---

*End of Phase 13 T4.SB executing-plans return report. Ready for `--no-ff` integration merge to main. Post-merge orchestrator-side housekeeping: CLAUDE.md current-state refresh (already landed at T-T4.SB.6 `c62fd98`; verify on main post-merge); cycle-checklist quarterly diagnostic reminder verification; Phase 13 main plan §H.3 row 13 GREEN-marker verification; Phase 13 FULLY CLOSED announcement.*
