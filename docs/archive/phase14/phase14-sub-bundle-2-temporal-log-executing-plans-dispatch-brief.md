# Phase 14 Sub-bundle 2 -- Temporal Pattern Detection + Observation Log Infrastructure -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 2 executing-plans implementer. No prior conversation context.

**Mission:** Execute the LOCKed implementation plan to ship the **temporal pattern detection + observation log infrastructure (V1+)** to production code + tests: a **v22 schema migration** introducing 2 NEW append-only tables (`pattern_detection_events` + `pattern_forward_observations`), 2 append-only repos, a `_step_pattern_detect` EXTENSION (per-pattern metadata + chart_render bytes capture), and a NEW `_step_pattern_observe` pipeline step (forward-walk observation + status state machine). This is the **largest substrate-changing sub-bundle Phase 14 ships** -- it eliminates cumulative gotchas #26 + #37 BY CONSTRUCTION (forward-walk; no archive re-read; no regeneration). Plan is dispatch-ready per writing-plans return report §15.

**Brief:** `docs/phase14-sub-bundle-2-temporal-log-executing-plans-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs at `7a558e4`; Sub-bundle 1 SHIPPED end-to-end at `e323339`; Sub-bundle 2 brainstorm SHIPPED at `9fc661b`; writing-plans SHIPPED at `62bf876`; housekeeping at `2854b13`. Main HEAD at executing-plans dispatch time: `2854b13`.

**Cumulative discipline at dispatch:** 37 CLAUDE.md gotchas BINDING (NOTE: as of `665cab0` CLAUDE.md gotchas are compressed to trigger+fix; the "Expansion #N" process/review disciplines live in `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" -- read BOTH); ~618+ cumulative ZERO Co-Authored-By trailer drift; 48th cumulative C.C lesson #6 validation NOTABLE at writing-plans SHIPPED; **Schema v21 -> v22 INTRODUCED by THIS dispatch** (v22 is the substrate; do NOT go beyond v22; do NOT add a v23); L2 LOCK preserved (multiset Counter source-grep test at `tests/integration/test_l2_lock_source_grep.py` baseline `bf7e071`).

**Expected duration:** ~5-8 hours executing-plans implementation + 2 Codex chains. Plan §G enumerates 6 task slices T-2.1..T-2.6; **~21 commits + ~94 fast tests** projected (trust `pytest -m "not slow" -q` over the estimate per gotcha #1). Operator-paced; SHIPS production code + tests + a NEW migration under `swing/` + `tests/`.

**Skill posture:**
- Invoke `copowers:executing-plans` skill against this brief.
- `copowers:executing-plans` wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review after all tasks complete.
- **Codex chain count: TWO chains** per OQ-20 operator LOCK + plan §J.2 (see §4). The append-only v22 substrate is PERMANENT and hard to walk back, so a dedicated schema/semantics-hardening chain follows the implementation-review chain.
- Output: production code + tests + return report at `docs/phase14-sub-bundle-2-temporal-log-executing-plans-return-report.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/superpowers/plans/2026-05-29-phase14-sub-bundle-2-temporal-log-plan.md`** -- the LOCKed plan (3357 lines; AUTHORITATIVE for implementation; TWO Codex chains CONVERGED NO_NEW_CRITICAL_MAJOR). Especially:
   - §A Goals + non-goals; §B File map (per-file diff projections with file:line); §C Surface-by-surface integration analysis
   - §E Operator-paired LOCKs reverification (20-row table; all LOCKs verbatim)
   - §F Cumulative discipline + watch items per task
   - **§G Per-task slicing (T-2.1..T-2.6; bite-sized step-checkbox TDD with real code per step; BINDING substrate)** + §G.0 commit cadence preface
   - §H Test surface (per-task distribution; ~94 fast sum-check); §I Operator-witnessed gate runbook (S1-S7; DB-scriptable for browser-MCP-unavailable fallback)
   - **§J Codex MCP TWO-chain placement (§J.1 writing-plans [done]; §J.2 executing-plans [run now per §4])**
   - §K Schema impact analysis (v22 introduction; STRICT backup-gate; runner discipline; ASCII scope)
   - §L Test fixture strategy (+ §L.4 concrete fixtures reusing the verified detect-step harness)
   - **§M Forward-binding lessons; §N Self-review checklist (pre-Codex)**

3. **`docs/phase14-sub-bundle-2-temporal-log-writing-plans-return-report.md`** -- return report. Especially §5 (6 residual OQs LOCKed at plan-authoring), §7 (per-task acceptance criteria), **§9 (forward-binding lessons incl. the FB-N1 recurrence + read-only-sandbox codex-cli wrinkle + the 2 implementer pre-flight verifications)**, §15 (executing-plans dispatch readiness).

4. **`docs/superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md`** -- brainstorm spec (788 lines; reference for architectural rationale). Especially §2 (LOCKs + §2.3 NORMATIVE forward-walk + §2.4 2-table primitive), §4-§9 per-surface designs, §13 V1+ simplifications + V2 candidates (do NOT design in V1+).

5. **`docs/phase14-sub-bundle-2-temporal-log-writing-plans-dispatch-brief.md`** §1 LOCKs (incl. §1.3 the 5 operator-LOCKed OQ dispositions) + §5 watch items -- carry forward.

6. **`docs/phase14-sub-bundle-2-temporal-log-brainstorming-dispatch-brief.md`** §1 (L1-L8) + **`docs/phase14-commissioning-brief.md`** Sec 2.5 + Sec 9.1 LOCKs (binding).

7. **`CLAUDE.md`** -- gotchas cited at plan §F (per task). Most relevant: #9, #11 (+ `sessions_since_detection >= 0` CHECK mirror), #27, #26/#37 (by-construction), #5 (observe fetch-scope), F6, sqlite3 dynamic-`?` IN-clause, `date.fromisoformat` boundary, append-only precedent. AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (the Expansion #N catalog) for the pre-Codex self-review (§N).

8. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_verify_regression_test_arithmetic` (compute both at-threshold + over-threshold for the 30/60 window + same-bar precedence + append-only-rejection tests)
   - `feedback_copowers_codex_mcp_windows_launcher` (FB-N1: fix the ACTIVE copowers cache version; restart-required; codex-cli `-s read-only` can't spawn shells -> paste artifacts inline)
   - `feedback_commit_message_trailer_parse_hazard` (keep the final `-m` paragraph plain prose; verify `%(trailers)` is `[]` before push)
   - `feedback_worktree_cli_invocation` (`python -m swing.cli`, NOT bare `swing`)
   - `project_capital_risk_floor` ($7500 floor; relevant if any metadata field references capital)

9. **Production code surfaces** cited in plan §B + §C. RE-VERIFY at executing-plans start to catch drift since the writing-plans merge (forward-binding lesson FB-N2; the plan re-grepped at `6574d2f`, main is now `2854b13`):
   - `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION`; `_phase13_sb6c_backup_gate` template; `run_migrations`; `_apply_migration`)
   - `swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql` (the `0022` template)
   - `swing/pipeline/runner.py:_step_pattern_detect` (~`runner.py:1396`/`1441`/`1603`; the L7 EXTEND target + `bars_by_ticker` retention + the DAG insertion point) + the lease/warnings_json accumulator
   - `swing/data/ohlcv_archive.py:resolve_ohlcv_window` (returns `(DataFrame, provenance_dict)`; provider priority `schwab_api` > `yfinance`; OQ-17) + `swing/web/ohlcv_cache.py:get_or_fetch`
   - `swing/web/charts.py:render_theme2_annotated_svg` + `swing/data/repos/chart_renders.py:refresh_chart_render` + `swing/web/view_models/patterns/exemplars.py` (the coexisting theme2_annotated writer)
   - `swing/data/repos/candidates.py` (sector/industry/adr_pct; `market_cap_dollars` + `atr_pct` ABSENT -- §9 redesign) + `swing/data/models.py` + the detector evidence dataclasses (`pivot_price` etc.)
   - `tests/pipeline/test_step_pattern_detect.py` (the VERIFIED harness §L.4 fixtures reuse)

---

## §1 LOCKs inherited (BINDING through executing-plans; DO NOT re-litigate)

All LOCKs preserved verbatim through 2 brainstorm + 2 writing-plans Codex chains per plan §E.

### §1.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing = data-wiring (SHIPPED) -> **temporal log V1+ (THIS)** -> charts -> review+journal -> metrics
- **Q2** execution = SERIAL; **Q3** scope = V1+ (2 tables + observe step + per-pattern metadata + chart bytes capture)
- **Q6** close-out = operator browser-witnessed verification at merge (incl. v22 schema verification)
- **Q7** Codex chain count = orchestrator discretion; **TWO chains for THIS sub-bundle** (OQ-20)

### §1.2 Spec §2 + L1-L8 LOCKs
- **L1** append-only on BOTH tables (INSERT-only; NO `update_*`/`delete_*` repo fns); **L2** forward-walk ONLY (#26/#37 eliminated by construction; NORMATIVE spec §2.3 -- select-by-`observation_date` + freeze; never blind-last-row; never re-read a past date from a later archive)
- **L3** v22 migration; gotcha #11 paired (CHECK + constant + validator + `_row_to_*` mapper same task) + gotcha #9 explicit BEGIN/COMMIT/ROLLBACK + STRICT backup-gate `current_version == 21`
- **L4** observe step zero-cost (reuse OhlcvCache ladder; no NEW fetch infra); **L5** chart capture REUSE `theme2_annotated` + `render_theme2_annotated_svg`; `chart_render_id` FK = `ON DELETE SET NULL` (nullable audit linkage; best-effort, NOT a frozen fact)
- **L6** per-pattern metadata at detection per §9 REDESIGN (ATR%/90d/52w computed from already-fetched bars; sector/industry/adr_pct from `candidates`; `market_cap` NULL); **L7** EXTEND `_step_pattern_detect` (coexist with `pattern_evaluations`; existing detector tests stay green); **L8** L2 LOCK (ZERO new `schwabdev.Client.*` call sites)
- **2-table primitive** (commissioning Sec 2.5 + spec §2.4) -- NO consolidation

### §1.3 The 5 operator-LOCKed OQ dispositions (BINDING)
- **OQ-10** append-only = repo-layer (no update/delete fns) + UNIQUE(detection_id, observation_date) + RESTRICT FK; triggers are V2 (do NOT add in V1+)
- **OQ-16** `market_cap = NULL` in V1+ (V2 dependency banked)
- **OQ-17** bounded observe scope (open-detection set) + reuse the Schwab-preferred ladder + **record the `provider` provenance tag ('schwab_api'/'yfinance') in `ohlc_today_json`** (sourced from `resolve_ohlcv_window`'s `provenance_dict`); do NOT relax L2 to force a Schwab fetch
- **OQ-18** `max_pending_window = 30` / `max_post_trigger_window = 60` sessions, config-surfaced; per-class `structural_invalidation_level` per spec §7.3.1; V1+ emits the ruleset-agnostic subset {pending, triggered_open, invalidated, expired}
- **OQ-19** chart FK = `ON DELETE SET NULL` (HELD against RESTRICT -- RESTRICT deadlocked the run-prune CASCADE + collided with the exemplar path)
- **OQ-20** TWO Codex chains

---

## §2 Scope inheritance from plan §G (BINDING substrate)

Plan §G is AUTHORITATIVE. Implement task-by-task in the locked order:

| Task | Scope | Commits | Tests |
|---|---|---|---|
| **T-2.1** v22 substrate | `0022_phase14_temporal_log.sql` (2 tables + 8 indexes + CHECK enums incl. `sessions_since_detection >= 0`); `db.py` `EXPECTED_SCHEMA_VERSION` 21->22 + STRICT `_phase14_backup_gate` (`current_version == 21`, verbatim-mirrors `_phase13_sb6c_backup_gate`) + `PHASE14_PRE_MIGRATION_EXPECTED_TABLES`; 2 dataclasses + 3 constants + `__post_init__` validators (gotcha #11 paired). Apply / rollback-through-runner / backup-gate / CHECK-rejection tests (gotcha #9). | ~5 | ~16 |
| **T-2.2** detection_events repo | `swing/data/repos/pattern_detection_events.py` append-only (`insert_event`/`get_by_id`/`list_*`/`list_observable` + `_row_to_detection_event`); NO `update_*`/`delete_*` (source-grep + mutating-SQL scan); UNIQUE; observable (no-observation) cases. | ~4 | ~10 |
| **T-2.3** observations repo | `swing/data/repos/pattern_forward_observations.py` append-only (`insert_observation`/`get_for_detection_chain`/`get_latest_observations_for_detections` dynamic-`?` IN-clause + empty short-circuit + `_row_to_observation` + status helpers); UNIQUE; RESTRICT FK; cross-repo terminal-status; source-grep. | ~4 | ~12 |
| **T-2.4** detect extension + chart | `temporal_metadata.py` (3 pure-bars helpers + `build_structural_anchors_json` + `build_finviz_screen_state` + `build_ohlc_today_json` construction barrier + `_usable` guard); `detection_chart_capture.py` (narrow-except F6); `charts.py` evidence-key repair (FB-N5); detect-loop append (`bars_by_ticker` retention; **substrate-completeness invariant -- every verdict -> a detection row**; idempotency; chart NULL-on-fail; empty-pool warning #27). **STEP 0 pre-flight:** diff §L.4 `pipeline_runs`/`EvaluationRun`/`Candidate` fixtures against live `tests/pipeline/test_step_pattern_detect.py`; adjust only on drift. | ~5 | ~26 |
| **T-2.5** observe step | `PipelineConfig` 30/60 window fields; NEW `_step_pattern_observe` + `_bar_for_date` (**provider provenance via `resolve_ohlcv_window`**) + `_advance_status` (**precedence invalidation > breakout > expiry** + terminal guard) + `_sessions_since` (from `data_asof_date`; `date.fromisoformat` boundary); DAG wiring after `pattern_detect`, before `schwab_snapshot` + run-warnings accumulator; forward-walk freeze test (#26/#37). **STEP 0 pre-flight:** confirm `get_or_fetch` write-throughs to the `prices_cache_dir` that `resolve_ohlcv_window` reads; a structural mismatch is a #24-family ESCALATION, not a silent patch. | ~5 | ~26 |
| **T-2.6** closer | cross-step e2e (detect -> observe forward-walk over simulated sessions) + L2 source-grep continued-pass verify + ASCII verify + return report. | ~2 | ~4 |

**Total: ~21 commits + ~94 fast tests** projected (trust pytest per gotcha #1). **Do NOT widen task scope** beyond plan §G acceptance criteria + step-checkbox TDD.

---

## §3 Watch items + cumulative discipline (BINDING)

**Forward-binding lessons (plan §M + return report §9; LOAD-BEARING per task):**
- **FB-N1 (Codex MCP transport):** RESTART Claude Code before the Codex chains so the fixed `.mcp.json` binds; VERIFY which copowers version is active via the skill's "Base directory" line before assuming a fix applies (all three copies 1.0.0/2.0.0/marketplace are patched as of `2854b13`). **NEW codex-cli `-s read-only` wrinkle:** cannot spawn shells on this host -> Codex cannot read repo files; paste the GIT DIFF + spec + plan + a re-grepped production-signature DIGEST INLINE (the skill's round-1 "paste full content" pattern). The `codex exec` CLI is the transport-independent backstop.
- **FB-N2 column verification:** `candidates.market_cap_dollars` + `atr_pct` do NOT exist (only sector/industry/adr_pct); §9 computes ATR%/90d/52w from bars; market_cap NULL. **FB-N3** theme2_annotated has a coexisting writer (last-writer-wins). **FB-N4** `detection_date` vs `data_asof_date` directionality (forward-walk boundary). **FB-N5** stale evidence keys in `charts.py` (repair IN T-2.4). **FB-N6** `warnings_json` is NEW plumbing for the observe step.
- **Substrate-completeness invariant:** every emitted verdict appends a `pattern_detection_events` row -- a defensive skip must DEGRADE GRACEFULLY (empty-frame metadata + warn), never silently skip, or `pattern_evaluations` and `pattern_detection_events` desync.
- **Status-machine same-bar precedence is load-bearing:** invalidation (confirmed close) > breakout (intraday touch) > expiry; preserve the ordering + boundary tests verbatim.
- **`bars_by_ticker` retention:** the Pass-1 fetch (~`runner.py:1603`) must be retained into the Pass-2 emit loop; `pd` already imported in `_step_pattern_detect`; do NOT re-fetch.

**Cumulative gotchas (plan §F):** #9 (BEGIN/COMMIT/ROLLBACK + rollback-through-runner) / #11 (CHECK+constant+validator + `_row_to_*` same task; `sessions_since_detection >= 0` mirror; STRICT backup-gate) / #27 (3 silent-skip audit sites: detect empty-pool + observe empty-pool/no-bar + chart-failure) / #26+#37 (by-construction; forward-walk freeze test) / #5 (observe fetch-scope AUDITED, OQ-17) / F6 (chart empty-bytes barrier) / sqlite3 dynamic-`?` + empty-input / `date.fromisoformat` boundary / #16+#32 (ASCII scope, programmatic `encode("ascii")`).

**Streaks to preserve:** ~618+ ZERO `Co-Authored-By` (verify `%(trailers)` per commit; keep final `-m` paragraph plain prose per `feedback_commit_message_trailer_parse_hazard`); **Schema v22 INTRODUCED -- do NOT exceed v22 (no v23)**; L2 LOCK (source-grep continues passing); ASCII discipline; gotcha #33 banned-terms across narrative. **49th cumulative C.C lesson #6 validation slot consumed by this dispatch** (two chains).

---

## §4 Codex MCP TWO-chain placement (OQ-20 LOCK; plan §J.2)

Run TWO chains at the end of executing-plans:
- **Chain #1 -- implementation review:** after ALL code + tests land + green, BEFORE the operator-witnessed gate. Lens: production-signature correctness, test coverage/discrimination, per-task acceptance criteria met, no placeholders, cascade-regression audit.
- **Chain #2 -- schema/semantics hardening:** append-only invariants hold at runtime (UPDATE/DELETE rejected; UNIQUE; RESTRICT); the forward-walk freeze test is genuinely discriminating (#26/#37); the v22 migration is clean + rolls back; the status-machine precedence + window arithmetic are correct; L2 source-grep continues passing; backup-gate STRICT.

Each converges to `NO_NEW_CRITICAL_MAJOR`. **FB-N1:** prefer the MCP transport (restart first); if it fails, use `codex exec` CLI with INLINE artifacts (read-only sandbox can't read files). Re-build the verified-signature digest at executing-plans HEAD (drift since `6574d2f`). Aim for ZERO Major accepted-as-rationale (writing-plans + brainstorm both hit zero).

**If Codex finds a defect requiring a schema change beyond v22:** STOP + escalate (do NOT add a v23; v23 belongs to Sub-bundle 3).

---

## §5 Operator-witnessed gate (plan §I; S1-S7)

After both chains converge + return report drafted, orchestrator returns to operator. Browser MCP may be unavailable -- the proven fallback is operator-driven browser with the orchestrator running DB-side probes step-by-step; the plan made S2-S7 DB-scriptable.

- **S1**: `python -m pytest -m "not slow" -q` green (~6565 baseline + ~94 NEW) + `ruff check swing/` clean
- **S2**: v22 applied; schema_version = 22; both new tables empty + readable; pre-migration backup emitted at the `current_version == 21` boundary
- **S3**: run pipeline; `pattern_detection_events` accumulates for detected patterns; per-pattern metadata populated (sector/industry/adr_pct/atr%/90d/52w; `market_cap` NULL); `data_asof_date` populated; `chart_render_id` non-NULL for successful renders
- **S4**: re-run pipeline next session; `pattern_forward_observations` appends today's bar for previously-open detections; `provider` provenance tag present in `ohlc_today_json`; status transitions correctly
- **S5**: append-only verification (UPDATE -> reject; DELETE a detection with observations -> RESTRICT; duplicate observation -> UNIQUE; INSERT-only path works)
- **S6**: chart_render chain `pattern_detection_events.chart_render_id` -> `chart_renders.chart_id` -> `chart_svg_bytes` verifiable; **the rendered chart is the BINDING visual gate** (matplotlib mathtext/text gotcha -- byte/format tests are insufficient); chart-failure path leaves `chart_render_id` NULL + emits `warnings_json`
- **S7**: forward-walk freeze verification (#26/#37) -- mutate the archive's bar for a past `observation_date`; re-run observe; confirm the frozen `ohlc_today_json` is UNCHANGED; L2 source-grep continues passing

**Gate-pass triggers** ("all surfaces pass" / "gate passed" / equivalent) -> orchestrator merges per `feedback_orchestrator_performs_merge` BINDING.

---

## §6 Done criteria

1. All 6 tasks shipped (T-2.1..T-2.6)
2. BOTH Codex chains CONVERGED at NO_NEW_CRITICAL_MAJOR
3. ~6565+ fast tests green on branch (baseline + ~94 NEW); `python -m pytest -m "not slow" -q`
4. `ruff check swing/` clean (preserve 0 E501 baseline)
5. ZERO Co-Authored-By trailer drift (verify `%(trailers)`); final `-m` paragraphs plain prose
6. **Schema v22 applied; exactly ONE new migration `0022_*.sql`; no v23** (escalate if a v23 seems needed)
7. L2 LOCK preserved (source-grep test PASSES against `bf7e071` baseline)
8. Return report at `docs/phase14-sub-bundle-2-temporal-log-executing-plans-return-report.md` complete per §7
9. Branch pushed to origin; ready for orchestrator QA + operator-witnessed gate

---

## §7 Return report shape

1. Final HEAD + commit count breakdown (per-commit Codex round attribution; BOTH chains)
2. Codex round chains (chain #1 + chain #2 summary tables + convergent shape)
3. Per-task completion summary (T-2.1..T-2.6)
4. Test surface verification (~94 fast projected; per-task actual distribution; total before + after)
5. Pre-locked decisions verbatim verification (Sec 9.1 + L1-L8 + 5 OQ dispositions + OQ-19)
6. Codex Major findings ACCEPTED with rationale (if any; ZERO preferred)
7. Production-code citations verified at task completion (FB-N2 re-grep; per-task signature re-verification)
8. Schema impact verdict (v22 applied; exactly one `0022_*.sql`; backup-gate STRICT; runner discipline; rollback test)
9. Append-only + forward-walk verification (UPDATE/DELETE rejected; UNIQUE; RESTRICT; #26/#37 freeze test discriminating)
10. L2 LOCK verification (source-grep PASSES against `bf7e071`; cite test name + result)
11. Operator-witnessed gate readiness (S1-S7 runbook; DB-scriptable probes; S6 visual gate)
12. NEW forward-binding lessons banked (for Sub-bundle 3 + CLAUDE.md gotcha consideration)
13. ASCII discipline scope (gotcha #32; enumerate NEW + MODIFIED files)
14. Cumulative gotcha set application summary (per task)
15. Worktree teardown status
16. ZERO Co-Authored-By footer drift confirmation (`%(trailers)` across all branch commits) + `%(trailers)` empty on merge-candidate
17. CLAUDE.md status-line refresh draft text
18. Operator-witnessed gate handback summary

---

## §8 OUT OF SCOPE (do not implement)

- Backfill of `pattern_detection_events` from `pattern_evaluations` (V2)
- SQLite BEFORE UPDATE/DELETE triggers (OQ-10: repo-layer only in V1+)
- Persisting `market_cap` to `candidates` (OQ-16: NULL in V1+)
- Relaxing L2 to force a Schwab fetch (OQ-17 rejected alternative)
- Real-time ruleset replay engine + `triggered_closed_at_*` status emission (Phase 15+)
- Schema beyond v22 (v23 = Sub-bundle 3; escalation rule)
- NEW HTMX endpoints/surfaces; Sub-bundle 3/4/5 scope (Sec 9.1 Q1 serial LOCK)
- V2 candidates banked at spec §13 + return report
- Production code modifications NOT in plan §B file map
- CLAUDE.md / orchestrator-context archive-splits

---

## §9 If you get stuck

- If production has drifted since the writing-plans merge (`62bf876`) and a plan-cited file:line no longer matches, ESCALATE (do NOT silently patch). Plan was verified at `6574d2f`.
- T-2.5 STEP 0: if `get_or_fetch` does NOT write-through to the `prices_cache_dir` that `resolve_ohlcv_window` reads, ESCALATE (#24-family) -- do NOT silently patch the provenance path.
- If Codex pushes back on the **2-table primitive / append-only / #26-#37-by-construction / v22 / chart FK SET NULL / 30-60 windows / repo-layer enforcement / market_cap NULL / OQ-17 provider provenance** -- HOLD THE LINE (LOCKs at §1).
- If Codex pushes back on the **TWO-chain count**, HOLD THE LINE (OQ-20).
- If a chain finds a defect needing a schema change beyond v22, STOP + escalate (no v23).
- If the Codex MCP times out, RESTART + verify the active copowers version; else use `codex exec` CLI with INLINE artifacts.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; keep final `-m` paragraphs plain prose (verify `%(trailers)` is `[]`).
- DO NOT widen scope to other Phase 14 items or Phase 15+.

---

## §10 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface for production code + tests + migration).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES -- branch `phase14-sub-bundle-2-temporal-log-executing-plans`. Worktree directory `.worktrees/phase14-sub-bundle-2-temporal-log-executing-plans/`.
- **Model:** defer to harness default.
- **Expected duration:** ~5-8 hours implementation + ~1-2 hours for 2 Codex chains. Operator-paced.
- **Codex MCP chain count:** TWO chains (OQ-20 LOCK + plan §J.2). FB-N1: restart for MCP; `codex exec` CLI + inline artifacts is the backstop.
- **Production surface:** `swing/data/migrations/0022_*.sql` + `swing/data/db.py` + `swing/data/repos/pattern_detection_events.py` (NEW) + `swing/data/repos/pattern_forward_observations.py` (NEW) + `swing/data/models.py` + `swing/pipeline/runner.py` + `swing/pipeline/temporal_metadata.py` (NEW) + `swing/pipeline/detection_chart_capture.py` (NEW) + `swing/web/charts.py` + `swing/config.py` (PipelineConfig windows). **Test surface:** `tests/data/` + `tests/data/repos/` + `tests/pipeline/` + `tests/integration/`.

---

*End of brief. Phase 14 Sub-bundle 2 executing-plans dispatch -- execute the LOCKed 3357-line plan (v22 migration + 2 append-only tables + 2 repos + detect-step extension + NEW `_step_pattern_observe`; 6 tasks T-2.1..T-2.6; ~21 commits + ~94 fast tests); TWO Codex chains (implementation review + schema/semantics hardening); operator-witnessed gate S1-S7 per plan §I. Eliminates gotchas #26 + #37 BY CONSTRUCTION. OUTPUT: production code + tests + the v22 migration + return report; ready for orchestrator merge + operator-witnessed gate + post-merge housekeeping.*
