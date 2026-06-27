# Phase 14 Sub-bundle 2 -- Temporal Pattern Detection + Observation Log Infrastructure -- Executing-Plans Return Report

**Phase:** executing-plans (`copowers:executing-plans` = `superpowers:subagent-driven-development` + adversarial Codex review).
**Branch:** `phase14-sub-bundle-2-temporal-log-executing-plans` from main `dffaca9`.
**Plan:** `docs/superpowers/plans/2026-05-29-phase14-sub-bundle-2-temporal-log-plan.md` (3357 lines; AUTHORITATIVE).
**Spec:** `docs/superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md` (788 lines).
**Disposition:** SHIPPED on branch. BOTH Codex chains CONVERGED (NO_NEW_CRITICAL_MAJOR). Full fast suite green (6657 passed). Ready for orchestrator QA + operator-witnessed S1-S7 gate + merge.

---

## 1. Final HEAD + commit count breakdown (per-commit Codex round attribution; BOTH chains)

- **Final HEAD:** `12b4df4`.
- **Commit count:** 22 (18 task commits T-2.1..T-2.6 + 4 Codex-fix commits).

| # | SHA | Task / Codex attribution |
|---|---|---|
| 1 | `6d5e6ad` | T-2.1 v22 migration + backup-gate wiring |
| 2 | `20fddd7` | T-2.1 PatternDetectionEvent + PatternForwardObservation dataclasses |
| 3 | `6506630` | T-2.1 dataclass-barrier + status_change_event #11-mirror tests (two-stage review-loop) |
| 4 | `7e147f2` | T-2.2 detection_events repo insert/get/list |
| 5 | `c5db0e8` | T-2.2 UNIQUE + observable-detections tests |
| 6 | `8e15d9b` | T-2.2 append-only source-grep guards |
| 7 | `00c129e` | T-2.3 pattern_forward_observations repo |
| 8 | `27a2c04` | T-2.4 pure-bars temporal metadata helpers |
| 9 | `c70addc` | T-2.4 detection chart capture + evidence-key repair |
| 10 | `2becaf3` | T-2.4 detect-step appends frozen detection events + chart capture |
| 11 | `bfaa297` | T-2.4 3 Minor review-loop fixes (dead const, data_asof guard, overlay test) |
| 12 | `3aa974f` | T-2.5 PipelineConfig observe windows |
| 13 | `50dd1a5` | T-2.5 _advance_status + observe helpers |
| 14 | `ba864bc` | T-2.5 _step_pattern_observe integration set |
| 15 | `4ee7fd7` | T-2.5 DAG wiring + run-warnings accumulator (FB-N6) |
| 16 | `2f07893` | T-2.5 _bar_for_date magic-number clarification (review-loop, orchestrator-applied) |
| 17 | `1b9ae8b` | T-2.6 cross-step e2e + L2/ASCII tests |
| 18 | `ee09ec9` | T-2.6 ASCII cleanup (section-sign glyphs) + stale schema-assertion fix |
| 19 | `0638411` | **Codex chain #1 R1 Major #3** -- anchor list_observable_detections to observation_date |
| 20 | `73f60ea` | **Codex chain #1 R1 Major #1+#2** -- audit detect substrate desync + stop fabricating observe provenance |
| 21 | `363a519` | **Codex chain #1 R2 Major #1+#2 + Minor #1** -- audit cand-is-none skip + squeeze 2D ATR cols + e2e anchor-parse test |
| 22 | `12b4df4` | **Codex chain #2 R1 Minor #1** -- pin triggered_open horizon lower bound at 89 |

Per-task two-stage review (spec compliance + code quality) ran after each of T-2.1..T-2.6 (some performed inline by the orchestrator during a transient subagent-dispatch outage; all independent of the implementer's self-report). The two Codex chains then reviewed the FULL diff and served as the comprehensive final-reviewer pass.

---

## 2. Codex round chains (chain #1 + chain #2 summary tables + convergent shape)

**Transport note (FB-N1 RECURRED):** the copowers Codex MCP tool (`mcp__plugin_copowers_codex__codex`) timed out at the 1s client ceiling on the first call -- this session was NOT restarted after the 2026-05-29 active-cache (1.0.0) `.mcp.json` fix, so the registration was still the broken bare `command: "codex"`. Fell back to the `codex exec` CLI backstop with INLINE artifacts (the full git diff + a verified-signature digest pasted into the prompt; `-s read-only` cannot read repo files on this host). `codex exec resume --last` rejected the `-s/--skip-git-repo-check` flags (exit 2), so rounds 2+ ran as fresh self-contained `codex exec` reviews of the post-fix diff with a "prior rounds resolved -- do not re-raise" delta header. Adversarial substance unchanged; transport differs. **Banked: restart Claude Code before the Codex chains so the MCP transport binds (memory already corrected to patch the ACTIVE 1.0.0 cache version).**

**Chain #1 -- implementation review lens:**

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 3 | 2 | ISSUES_FOUND |
| R2 | 0 | 2 | 2 | ISSUES_FOUND |
| R3 | 0 | 0 | 3 | **NO_NEW_CRITICAL_MAJOR** |

Chain #1 cumulative: 0 Critical + 5 Major + 7 Minor; **all 5 Major resolved in-place; ZERO Major accepted-as-rationale.**

**Chain #2 -- schema/semantics-hardening lens:**

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 0 | 1 | NO_NEW_CRITICAL_MAJOR (pre-MIN_ROUNDS) |
| R2 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** |

Chain #2 cumulative: 0 Critical + 0 Major + 1 Minor (resolved). The schema/semantics substrate was clean on the first pass (matching the writing-plans chain #2 fast convergence -- the design was already hardened).

**Combined: 0 Critical + 5 Major + 8 Minor; ZERO Major/Critical accepted-as-rationale** (49th cumulative C.C lesson #6 validation slot: PASS).

### Codex's strongest catches (all code-grounded, all RESOLVED)
1. **(C1 R1 M3)** `list_observable_detections` ranked the ABSOLUTE latest observation per detection (no date bound) -> a future/replayed observation could drive latest-status. Fixed: `WHERE observation_date <= ?` in the latest-status CTE (date-anchored); discriminating test added (future terminal obs does not exclude an earlier query date).
2. **(C1 R1 M1)** Detection-insert-failure path did `log.warning + continue` -> SILENT substrate desync (eval row without detection row). Fixed: append a `run_warnings` audit entry (gotcha #27).
3. **(C1 R1 M2)** `_bar_for_date` defaulted provider to `"yfinance"` when provenance lacked the date -> fabricated provenance in the append-only log. Fixed: missing provenance -> return None (no-bar path; caller warns).
4. **(C1 R2 M1)** The sibling `cand is None` skip had the same #27 gap. Fixed: audited via `run_warnings`.
5. **(C1 R2 M2)** `compute_atr_pct` lacked the single-ticker 2D/MultiIndex squeeze that `_close_series` applies -> a 2D frame would raise during metadata build and roll back the whole fenced_write. Fixed: shared `_squeeze` helper applied to High/Low/Close + 2D regression test.
6. **(C2 R1 m1)** The `triggered_open -> expired` horizon boundary (90) was half-pinned. Fixed: added the immediately-under-threshold 89 case.

---

## 3. Per-task completion summary (T-2.1 .. T-2.6)

- **T-2.1 (v22 substrate; 3 commits):** migration `0022` (2 append-only tables; 8 indexes; CHECK enums incl. `sessions_since_detection >= 0`); `db.py` EXPECTED_SCHEMA_VERSION 21->22 + STRICT `_phase14_backup_gate` (`current_version == 21`) + `_create_pre_phase14_migration_backup` + `PHASE14_PRE_MIGRATION_EXPECTED_TABLES`; 2 frozen dataclasses + 3 enum constants + `__post_init__` validators. gotcha #9 + #11 paired honored; rollback-through-runner + CHECK-rejection + STRICT-gate + runner-wiring tests.
- **T-2.2 (detection_events repo; 3 commits):** append-only repo (insert/get/list/list_observable + `_row_to_detection_event`); UNIQUE; no-observation observable cases; append-only source-grep + mutating-SQL scan.
- **T-2.3 (observations repo; 1 commit):** append-only repo (insert/chain/latest/batch-latest dynamic-`?` + empty short-circuit + `_row_to_observation`); UNIQUE; RESTRICT FK; cross-repo terminal-status observable; source-grep.
- **T-2.4 (detect extension + chart; 4 commits):** `temporal_metadata.py` (pure-bars helpers + `build_*` + `build_ohlc_today_json` barrier); `detection_chart_capture.py` (narrow-except F6); `charts.py` evidence-key repair (5 keys); detect-loop append (substrate-completeness; bars retention; idempotency; chart NULL-on-fail; empty-pool warning). Existing detector tests UNCHANGED (L7).
- **T-2.5 (observe step; 5 commits):** `PipelineConfig` 30/60 windows; `_advance_status` (precedence invalidation>breakout>expiry + terminal guard) + `_structural_invalidation_level` + `_bar_for_date` (date-anchored read + provider provenance) + `_sessions_since` (business-day, from data_asof_date); DAG wiring + run_warnings accumulator + completion `lease.release(warnings_json=...)`; forward-walk freeze test.
- **T-2.6 (closer; 2 commits):** cross-step e2e (detect -> observe forward-walk); L2 source-grep verify; ASCII test + section-sign cleanup; consequential fix to a stale `== 21` schema assertion in `test_phase13_t2_sb4_detectors_e2e.py` (now asserts `EXPECTED_SCHEMA_VERSION`).

---

## 4. Test surface verification (per-task actual distribution; total before + after)

- **Full fast suite (post-Codex-fixes): `6657 passed, 3 skipped`** (`python -m pytest -m "not slow" -q`, 150s). ruff `swing/` clean (0 E501 preserved).
- **Baseline at dispatch:** ~6565 fast tests. **Net new: ~92** (within the ~94 projection; gotcha #1 -- trust pytest over the estimate).
- Per-task new-test counts (approximate, as run during execution): T-2.1 ~19 (migration 10 + models 9 incl. the review-loop additions); T-2.2 7; T-2.3 9; T-2.4 ~26 (metadata 7 + chart capture 4 + overlay 3 + extension 12); T-2.5 ~25 (config 2 + observe 23); T-2.6 ~4 (e2e + ascii). Plus Codex-fix discriminating tests (~6).
- **Known flake (NOT a regression):** `tests/research/test_pattern_cohort_evaluator_reader.py::test_ohlcv_reader_re_export_identity` failed once under xdist parallel ordering but **passes in isolation (7 passed, `-n0`)**. The branch touches NOTHING under `tests/research/` or the cohort/ohlcv_reader code (verified). Pre-existing xdist test-ordering flakiness, unrelated to this work.

---

## 5. Pre-locked decisions verbatim verification

| LOCK | Status |
|---|---|
| Sec 9.1 Q1-Q7 | HONORED -- temporal-log V1+ this sub-bundle; SERIAL single dispatch; operator-witnessed close-out (S1-S7); TWO Codex chains (Q7 = OQ-20). |
| L1-L8 (spec §2.2) | HONORED -- append-only both tables; forward-walk only; v22; observe zero-cost (reuses OhlcvCache); chart capture reuses theme2_annotated; metadata-at-detection; detect EXTENSION (L7 detector tests green); L2 LOCK. |
| spec §2.3 NORMATIVE forward-walk + append-only | HONORED -- select-by-observation_date (now date-anchored after C1 R1 M3 fix) + freeze; #26/#37 eliminated by construction (pure INSERT; freeze test discriminating). |
| 2-table primitive (Sec 2.5 + spec §2.4) | HELD -- no consolidation; neither chain challenged. |
| OQ-10 append-only = repo-layer + UNIQUE + RESTRICT (triggers V2) | HONORED. |
| OQ-16 market_cap = NULL | HONORED (`build_per_pattern_metadata` sets `market_cap: None`). |
| OQ-17 bounded fetch + provider provenance tag | HONORED -- observe reads via `resolve_ohlcv_window`; provider recorded in `ohlc_today_json`; fabrication removed (C1 R1 M2). |
| OQ-18 30/60 config windows + per-class invalidation | HONORED (`PipelineConfig` fields; ruleset-agnostic `{pending, triggered_open, invalidated, expired}`). |
| OQ-19 chart FK = ON DELETE SET NULL | HONORED (both `pipeline_run_id` + `chart_render_id`). |
| OQ-20 TWO Codex chains | HONORED. |

ZERO LOCKs re-litigated. ZERO scope widening. v22 ONLY (no v23).

---

## 6. Codex Major findings ACCEPTED with rationale

**ZERO Major accepted-as-rationale.** All 5 chain-1 Major were RESOLVED in-place. Minors accepted-with-rationale (no code change):
- **Stale schema-version test names** (`test_expected_schema_version_is_19` asserting 22): the documented "stale-name/current-assertion for grep-history continuity" convention (precedent `7ee5a4a`). Intentional; not renamed.
- **Observe read-then-write stale-read** (read scan on a separate connection before `lease.fenced_write()`): benign under the exclusive single-lease model -- concurrent pipeline runs are lease-forbidden, so the only overlap a UNIQUE collision could come from cannot occur. Moving the idempotency check inside the write tx is a banked V2 hardening.
- **Repo test fixture `ohlc_today_json` not 6-key shape:** the repo stores TEXT and does not inspect JSON; the `build_ohlc_today_json` construction barrier is tested separately. Fixture-fidelity nit only.
- **e2e planted-detection:** documented residual risk; the added `test_real_detect_anchors_parse_through_advance_status` proves production-emitted anchors parse through the status machine without crashing.

---

## 7. Production-code citations verified at task completion (FB-N2 re-grep)

Re-verified at executing-plans HEAD (production did NOT drift from the plan's `6574d2f` cites -- intervening main commits were docs-only):
- `swing/data/db.py`: `EXPECTED_SCHEMA_VERSION` (:46), `_phase13_sb6c_backup_gate` (:734), `_create_pre_phase13_sb6c_migration_backup` (:498), `run_migrations` (:780), `_apply_migration` (:171) -- all matched.
- `swing/pipeline/runner.py`: `_step_pattern_detect` (:1396), DAG `pattern_detect` block (:850) / `schwab_snapshot` (:879), completion `lease.release(state="complete")` (:969), `lease_data_asof` (:985) -- all matched.
- `swing/data/ohlcv_archive.py:resolve_ohlcv_window` (:372, lowercase `asof_date`/OHLCV + provenance dict); `swing/web/ohlcv_cache.py:get_or_fetch` (:131) -- matched.
- **FB-N2:** `candidates` has sector/industry/adr_pct but NO market_cap/atr_pct -- confirmed; ATR%/90d/52w computed from bars; market_cap NULL.
- `tests/pipeline/test_step_pattern_detect.py` harness: `_build_bars`/`_StubOhlcvCache`/`_StubLease`/`_seed_*` -- confirmed; §L.4 `conftest_temporal.py` built self-contained (T-2.4 STEP-0).

---

## 8. Schema impact verdict (v22)

Schema v22 applied via the SINGLE migration `0022_phase14_temporal_log.sql`. 2 NEW append-only tables: `pattern_detection_events` (12 cols incl. `data_asof_date`; both FK `pipeline_run_id` + `chart_render_id` `ON DELETE SET NULL`) + `pattern_forward_observations` (8 cols; `detection_id` `ON DELETE RESTRICT`; `UNIQUE(detection_id, observation_date)`; `CHECK(sessions_since_detection >= 0)`). 8 indexes (1 UNIQUE). `EXPECTED_SCHEMA_VERSION` 21->22. STRICT `_phase14_backup_gate` (`current_version == 21 AND target >= 22`; verbatim-mirrors `_phase13_sb6c_backup_gate`). `PHASE14_PRE_MIGRATION_EXPECTED_TABLES = PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` (v21 added no tables). gotcha #9 explicit `BEGIN;`/`COMMIT;` with `UPDATE schema_version SET version = 22;` as the final statement; rollback-through-runner test passes. gotcha #11 paired (CHECK + constants + validators in T-2.1; `_row_to_*` mappers in the repo tasks). **NO migration beyond v22.** ruff clean.

---

## 9. Append-only + forward-walk verification

- **Append-only:** both repos define NO `update_*`/`delete_*` (source-grep test) and contain NO mutating SQL (regex scan: UPDATE...SET / DELETE FROM / REPLACE INTO / DROP). UNIQUE rejection + RESTRICT-FK rejection tests pass at runtime.
- **Forward-walk (#26/#37 by construction):** `test_forward_walk_freezes_past_bar` mutates the stubbed archive's date-N bar and re-runs observe at N+1, asserting the date-N row is byte-identical (close 9.00, not the drifted 9.99). `insert_observation` is a pure INSERT (no upsert/REPLACE); the observe step never re-reads/rewrites a past row. The freeze test genuinely discriminates -- an introduced upsert/re-read would flip `chain[0].close` and fail it.
- **list_observable_detections** is now date-anchored (`WHERE observation_date <= ?`) so a future/replayed observation cannot drive the latest-status decision (Codex C1 R1 M3).

---

## 10. L2 LOCK verification

`tests/integration/test_l2_lock_source_grep.py` PASSES (in the full suite + verified standalone) -- ZERO new `schwabdev.Client.*` call sites vs baseline `bf7e071`. Chart capture = matplotlib; observe OHLCV = the existing `OhlcvCache` ladder + `resolve_ohlcv_window` archive read. Test UNCHANGED.

---

## 11. Operator-witnessed gate readiness (S1-S7)

Ready for the operator-witnessed gate (plan §I; DB-scriptable probes for the browser-MCP-unavailable fallback):
- **S1:** `python -m pytest -m "not slow" -q` -> 6657 passed, 3 skipped (1 known xdist flake passes in isolation); `ruff check swing/` clean. MET on branch.
- **S2:** v22 applied; `_current_version == 22`; both tables empty + readable; backup at the `current_version == 21` boundary. (DB-scriptable.)
- **S3:** run pipeline; `pattern_detection_events` accumulates; per-pattern metadata populated (sector/industry/adr_pct/atr%/90d/52w; market_cap NULL); `data_asof_date` populated; `chart_render_id` non-NULL for successful renders.
- **S4:** re-run next session; `pattern_forward_observations` appends today's bar; `provider` tag present; status transitions.
- **S5:** append-only (UPDATE -> no fn; DELETE detection-with-observations -> RESTRICT; dup observation -> UNIQUE) -- mechanical-test-covered.
- **S6:** chart_render chain `pattern_detection_events.chart_render_id` -> `chart_renders.id` -> non-empty `chart_svg_bytes`; **the rendered SVG overlay is the BINDING visual gate** (matplotlib gotcha -- byte tests insufficient).
- **S7:** forward-walk freeze (mutate a past `observation_date` bar; re-run observe; frozen `ohlc_today_json` unchanged) + L2 source-grep continues passing.

---

## 12. NEW forward-binding lessons banked (for Sub-bundle 3 + CLAUDE.md gotcha consideration)

- **FB-N1 (recurred):** RESTART Claude Code before the Codex chains so the MCP transport binds (the active 1.0.0 cache `.mcp.json` fix needs a restart). `codex exec` CLI + inline artifacts is the proven backstop; `codex exec resume --last` does NOT accept `-s`/`--skip-git-repo-check` (exit 2) -- run rounds 2+ as fresh self-contained `codex exec` reviews of the post-fix diff with a "prior rounds resolved" delta header.
- **#27 audit-consistency family:** every per-verdict early-`continue` in a substrate-writing loop (insert-failure, candidate-missing, bars-absent) MUST emit a `run_warnings` audit entry -- a `log.warning` alone is a SILENT desync between `pattern_evaluations` and `pattern_detection_events`. (Codex found two such gaps after the first was fixed; sweep ALL continue paths.)
- **MultiIndex-squeeze consistency:** if one helper squeezes single-ticker 2D columns (`_close_series`), ALL sibling helpers consuming the same frame must too (`compute_atr_pct` did not) -- otherwise a 2D frame raises mid-metadata-build and rolls back the whole fenced_write.
- **Date-anchored latest-status:** a "latest observation per detection" window function MUST bind `WHERE observation_date <= ?` to stay honest under replay/backfill, not rely on "the pipeline only moves forward."
- **FB-N6 activation note:** wiring the `run_warnings` accumulator into the DAG ALSO lit up the previously-dark detect-side #27 warnings (they existed since T-2.4 but were never threaded to `lease.release`). Detect-side warnings now persist to `pipeline_runs.warnings_json` in production.
- **Synthetic-bars degenerate evidence:** smooth synthetic `_build_bars` drives the production detectors to freeze `pivot_price=0.0` (no real pattern) -> a real detect-step detection triggers immediately. Use a PLANTED detection (real anchors) for status-transition assertions; the real detect path is fine for chart-chain + frozen-fact + anchor-parse assertions.

---

## 13. ASCII discipline scope (gotcha #32)

ASCII-only verified across all NEW production + test files via `test_phase14_ascii_discipline.py` (programmatic `text.encode("ascii")` over: `0022_phase14_temporal_log.sql`, `pattern_detection_events.py`, `pattern_forward_observations.py`, `temporal_metadata.py`, `detection_chart_capture.py`). Added lines in MODIFIED files (db.py/models.py/config.py/runner.py/charts.py -- which carry pre-existing non-ASCII from prior phases) verified ASCII branch-wide. T-2.4 had introduced 3 `section`-sign glyphs into `tests/web/test_charts.py` comments (+ 1 em-dash in a Phase 13 test) -- both converted to ASCII at the closer. Branch-wide added-line sweep: 0 non-ASCII remaining.

---

## 14. Cumulative gotcha set application summary (per task)

| Gotcha / discipline | Task(s) |
|---|---|
| #9 executescript implicit COMMIT -> BEGIN/COMMIT/ROLLBACK + rollback-through-runner | T-2.1 |
| #11 CHECK + constant + validator paired (+ `sessions_since_detection >= 0`) + `_row_to_*` | T-2.1 (+ T-2.2/T-2.3 mappers) |
| backup-gate STRICT `current_version == 21` + runner-wiring test | T-2.1 |
| sqlite3 dynamic-`?` IN-clause + empty short-circuit | T-2.3 |
| `date.fromisoformat` TEXT->date boundary | T-2.5 (`_sessions_since`) |
| #26 + #37 ELIMINATED BY CONSTRUCTION (freeze test) | T-2.5 |
| #27 silent-skip-without-audit (empty-pool, insert-failure, cand-missing, no-bar, chart-failure) | T-2.4 + T-2.5 + Codex C1 fixes |
| #5 OHLCV fetch scope (observe reuses cache; STEP-0 verified write-through) | T-2.5 (OQ-17) |
| F6 ChartRender empty-bytes barrier | T-2.4 |
| #16/#32 ASCII scope | T-2.6 |
| #24-family STEP-0 verify (get_or_fetch -> resolve_ohlcv_window write-through) | T-2.5 (verified PASS; no escalation) |
| MultiIndex squeeze | Codex C1 R2 M2 fix |
| Co-Authored-By suppression + plain-prose final paragraph | all commits |

---

## 15. Worktree teardown status

Worktree `.worktrees/phase14-sub-bundle-2-temporal-log-executing-plans/` **RETAINED** (orchestrator owns merge per `feedback_orchestrator_performs_merge`). `git status` clean (all 22 commits committed; this report is the 23rd, committed before push). Codex session temp files (`.codex-chain*.txt`/`-out.txt`) lived in the MAIN working tree and were deleted at teardown (untracked + off-branch). The copowers session-state JSON was written to `$TMPDIR`.

---

## 16. ZERO Co-Authored-By footer drift confirmation

`git log dffaca9..HEAD` -> all 22 commits emit ZERO `Co-Authored-By` trailers (`%(trailers)` empty per commit, audited). No `--no-verify` used. Final `-m` paragraphs kept plain prose (no accidental `Word:` trailer). Streak preserved (~640+ cumulative).

---

## 17. CLAUDE.md status-line refresh draft text

> **Sub-bundle 2 (temporal pattern detection + observation log infrastructure; V1+; v22 schema) EXECUTING-PLANS SHIPPED** on branch `phase14-sub-bundle-2-temporal-log-executing-plans` HEAD `12b4df4` (22 commits; 2 NEW append-only tables `pattern_detection_events` + `pattern_forward_observations` via migration `0022`; 2 append-only repos; `_step_pattern_detect` extension with per-pattern metadata + chart_render capture; NEW `_step_pattern_observe` forward-walk step + status state machine; run-warnings accumulator wired to `lease.release`). Eliminates gotchas #26 + #37 BY CONSTRUCTION (forward-walk; select-by-observation_date + freeze). **BOTH Codex chains CONVERGED** (OQ-20): chain #1 impl-review R1-R3 (0C+5M+7m, all 5 Major resolved); chain #2 schema/semantics R1-R2 (0C+0M+1m) -- ZERO Major accepted-as-rationale. Full fast suite 6657 passed; ruff clean; **Schema v21 -> v22 LANDED** (STRICT backup-gate); L2 LOCK preserved (source-grep). FB-N1 recurred (MCP timed out; ran via `codex exec` CLI backstop with inline artifacts). NEXT: orchestrator QA -> operator-witnessed S1-S7 gate -> merge -> Sub-bundle 3 (chart-surface uniformity + P14.N8; v23).

(Status-line pointer note: CLAUDE.md line 3 currently says "executing-plans NEXT" for Sub-bundle 2 -- update to "executing-plans SHIPPED at `12b4df4`; operator-witnessed gate + merge NEXT". Schema-streak note: v22 LANDED -- update the "Schema v21 LOCKED" streak line.)

---

## 18. Operator-witnessed gate handback summary

**READY** for orchestrator QA -> operator-witnessed S1-S7 gate -> merge. Branch pushed to origin; worktree retained.

- All 6 tasks (T-2.1..T-2.6) shipped; per-task two-stage reviews passed; BOTH Codex chains CONVERGED at NO_NEW_CRITICAL_MAJOR (0C+5M+1m; ZERO Major accepted).
- Full fast suite 6657 passed, 3 skipped (1 known pre-existing xdist flake, passes in isolation, branch-unrelated); ruff `swing/` clean.
- Schema v22 (exactly one `0022_*.sql`; no v23); STRICT backup-gate; rollback-through-runner verified.
- Append-only + forward-walk + #26/#37-freeze + L2 LOCK + ASCII + ZERO Co-Authored-By all verified.
- HOLD-THE-LINE LOCKs preserved; neither chain re-litigated the 2-table primitive, append-only, #26/#37-by-construction, v22, chart FK SET NULL, 30/60 windows, market_cap NULL, or OQ-17.
- **S6 visual gate (rendered chart overlay) + S2-S7 DB probes** require the operator/orchestrator at gate time (plan §I). On "gate passed" the orchestrator merges per `feedback_orchestrator_performs_merge`.

---

*End of Phase 14 Sub-bundle 2 executing-plans return report. SHIPPED at `12b4df4` (22 commits); v22 migration + 2 append-only tables + 2 repos + detect-step extension + NEW `_step_pattern_observe`. BOTH Codex chains CONVERGED (0C+5M+8m cumulative; ZERO Major accepted-as-rationale). Eliminates gotchas #26 + #37 by construction. Ready for orchestrator QA + operator-witnessed S1-S7 gate + merge.*
