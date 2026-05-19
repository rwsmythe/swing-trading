# Phase 13 T2.SB1 — INTERIM Return Report (T-A.1.1 SHIPPED)

**Status:** PARTIAL — T-A.1.1 of 9 tasks SHIPPED. T3.SB1 concurrent dispatch UNBLOCKED. Remaining 8 tasks (T-A.1.1b through T-A.1.8) + 3-5 Codex rounds + operator-paired pause at T-A.1.7 DEFERRED to next implementer session per realistic single-session capacity.

**Audience:** Orchestrator + operator. This interim report captures T-A.1.1 ship status + the critical SHA T3.SB1 must branch off + the remaining scope so a follow-up session can resume.

---

## §1 CRITICAL: T-A.1.1 first-commit SHA

**`4cfd5f2ca9b0103231fb558b141cd87132939d12`**

Branch: `phase13-t2-sb1-dev-time-labeling-infra` at `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/`.

Per OQ-12 Option E (plan §B.2 + brief §1.2 BINDING): **T3.SB1 worktree branches off this SHA**, NOT off main HEAD. Operator relays to T3.SB1 implementer for branch-base coordination.

Verification:

```
$ git -C .worktrees/phase13-t2-sb1-dev-time-labeling-infra log -1 --pretty=format:'%H'
4cfd5f2ca9b0103231fb558b141cd87132939d12

$ git -C .worktrees/phase13-t2-sb1-dev-time-labeling-infra log -1 --pretty=format:'%s'
feat(phase13): v20 migration — phase13 charts patterns autofill usability schema landing (T-A.1.1)
```

Co-Authored-By trailer: ZERO (verified via `git log -1 --pretty=format:'%(trailers)'` → empty).

---

## §2 T-A.1.1 deliverables (atomic migration-only commit per OQ-12 Option E)

17 files changed; +2030 insertions / -22 deletions. NEW repo modules (T-A.1.1b) DEFERRED per OQ-12 Option E strict boundary + Codex R1 M#1 + R2 M#2 closure.

### Created

- `swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql` — 5 new tables (`pattern_exemplars` + `chart_renders` + `pattern_evaluations` + `watchlist_close_track_flags` + `watchlist_close_track_flag_events`) + `schwab_api_calls` rebuild widening `surface` CHECK 2→4 (adds `'trade_entry'` + `'trade_exit'`) + 4 ALTER ADDs on `fills` (incl. `fill_origin` DEFAULT `'operator_typed'`) + 1 ALTER ADD on `review_log` + 5 cross-column CHECK invariants on `pattern_exemplars` + 3 partial unique indexes on `chart_renders` + 1 partial unique index on `watchlist_close_track_flags` active-flag uniqueness. Atomic `BEGIN; ... COMMIT;` per CLAUDE.md `executescript()` implicit-COMMIT gotcha.
- `swing/patterns/__init__.py` — re-exports `DETECTOR_PATTERN_CLASSES` from `swing.data.models` per §A.14 constant-placement LOCK. Per Codex R3 Minor #3 closure: T-A.1.1 `__init__` does NOT preemptively reference symbols whose modules don't exist yet (later sub-bundles extend).
- `tests/data/test_v20_migration.py` — 6 binding discriminating tests + 1 audit (schwab widening) + 3 dataclass-validator sub-tests + 4 cross-bundle pins planted (currently skipped per plan §H.3 schedule).

### Modified

- `swing/data/db.py` — `EXPECTED_SCHEMA_VERSION = 20` bump + new `PHASE13_PRE_MIGRATION_EXPECTED_TABLES` constant + new `_create_pre_phase13_migration_backup` helper + new `_phase13_backup_gate` function (strict equality `pre_version == 19` per CLAUDE.md gotcha) + wired into `run_migrations`.
- `swing/data/models.py` — Phase 13 v20 enum constants block (9 constants near top per §A.14 constant-placement LOCK: `DETECTOR_PATTERN_CLASSES` + `_LABEL_SOURCE_VALUES` + `_FINAL_DECISION_VALUES` + `_PATTERN_EXEMPLAR_CREATED_BY_VALUES` + `_FILL_ORIGIN_VALUES` + `_CHART_SURFACE_VALUES` + `_FLAG_SURFACE_VALUES` + `_FLAG_CLEARED_REASON_VALUES` + `_FLAG_EVENT_TYPE_VALUES` + `_TIMEFRAME_VALUES`); `Fill` widened with 4 fields + `__post_init__` validator; `ReviewLog` widened with 1 field; 5 NEW dataclasses appended (`PatternExemplar` with 5-invariant `__post_init__` + `PatternEvaluation` + `ChartRender` + `WatchlistCloseTrackFlag` + `WatchlistCloseTrackFlagEvent`).
- `swing/integrations/schwab/audit_service.py` — `_SCHWAB_API_SURFACE_VALUES` constant added (4 values: `'pipeline', 'cli', 'trade_entry', 'trade_exit'`) + surface enum validation at `record_call_start` entry mirroring schema CHECK widening per §A.14 paired-atomic-landing LOCK.
- `tests/data/test_models_phase7.py` — `test_fill_dataclass_shape` updated to 16-field expected set including the 4 new Phase 13 fields.
- 10 existing migration tests (`tests/data/test_db_v8.py` + `test_migration_0010_*` + `test_migration_0012/13/15/16/17/18.py` + `test_migration_0019_atomic_apply.py` + `test_migration_0019_existing_data_preserved.py`) — `EXPECTED_SCHEMA_VERSION == 20` / `assert version == 20` / `assert post == 20` / `assert row[0] == 20` updated per paired-atomic-landing LOCK. `test_migration_0019_existing_data_preserved.py:133` kept at `== 19` (it pins post-apply-0019 state explicitly, not post-walk-to-HEAD state).

### Watch items honored

- §A.14 LOCK — ALL v20 enum constants live in `swing/data/models.py`; `swing/patterns/__init__.py` re-exports only.
- §A.15 LOCK — NO `INSERT OR REPLACE` in migration or new dataclass code paths.
- §B.6 escalation rule — ZERO schema additions beyond plan §G.1 + spec §3 (mapping 1:1 onto §3.0/3.1/3.2/3.3/3.4/7.2).
- Migration backup-gate strict equality (`pre_version == 19`, NOT `<=`).
- `executescript()` explicit `BEGIN;`/`COMMIT;` + `foreign_keys=OFF` discipline at runner level.
- 5 cross-column CHECK invariants on `pattern_exemplars` schema-defended AND mirrored as Python `__post_init__` predicates.
- `chart_renders` cross-column CHECK + 3 partial unique indexes (per Codex R2 M#5 closure — partial-index predicate also requires `pipeline_run_id IS NOT NULL` for `theme2_annotated`).
- Active-flag partial unique index `idx_wclf_active_ticker` on `watchlist_close_track_flags` (per Codex R1 M#9 closure — re-flagging cleared ticker inserts new lifecycle row).
- ASCII-only on CLI paths preserved (no CLI changes in T-A.1.1).
- ZERO Co-Authored-By footer trailer drift.
- Test fixture USERPROFILE+HOME monkeypatch — N/A for T-A.1.1 (no user-config.toml write paths exercised).

---

## §3 Test count + ruff status

| Metric | Pre-T-A.1.1 (main `6383cfa`) | Post-T-A.1.1 (`4cfd5f2`) |
|---|---|---|
| Fast tests | 4939 passed | 4949 passed (+10; **6 skipped** total = 4 v20 cross-bundle pins + 1 patterns fixture + 1 T1.SB0 cross-bundle pin) |
| Schema version | 19 | 20 |
| Ruff E501 (swing/) | 0 | 0 |
| Co-Authored-By trailer drift | 0 cumulative | 0 cumulative (212+ commits) |

Discriminating tests landed (all 6 from plan §G.1 step 1 + 1 schwab widening audit + 3 dataclass-validator coverage tests):

- `test_v20_migration_lands_all_tables`
- `test_v20_schema_python_constant_parity` (covers 8 enum constants + cross-column CHECKs)
- `test_v20_dataclass_validator_parity_pattern_exemplar_invariants` (all 5 numbered invariants exercised)
- `test_v20_dataclass_validator_parity_pattern_evaluation`
- `test_v20_dataclass_validator_parity_chart_render` (cross-column CHECK both directions)
- `test_v20_dataclass_validator_parity_flag_and_event`
- `test_v20_migration_backup_gate_fires_at_v19`
- `test_v20_migration_backup_gate_does_not_fire_at_v18`
- `test_v20_fill_origin_backfill_to_operator_typed`
- `test_v20_schwab_api_calls_widening_preserves_rows_and_indexes`

Cross-bundle pins planted (4; currently skipped per plan §H.3 schedule):

- `test_schema_version_v20_invariant` — un-skips at T3.SB1 merge.
- `test_pattern_exemplars_schema_shape_invariant` — un-skips at T2.SB3 + T2.SB5.
- `test_v20_atomic_landing_python_constants_validators_paired` — un-skips at T4.SB closer.
- `test_fill_origin_enum_complete_after_v20` — un-skips at T3.SB2 merge.

---

## §4 What is NOT in T-A.1.1 (deferred per OQ-12 Option E + remaining plan §G.1 scope)

Per OQ-12 Option E strict migration-only commit boundary + Codex R1 M#1 + R2 M#2 closure:

- **T-A.1.1b** — 4 NEW repo CRUD modules (`pattern_exemplars.py` + `pattern_evaluations.py` + `chart_renders.py` + `watchlist_close_track.py`) — minimum CRUD (`insert_*` + `get_*_by_id` + `list_*`); 12 discriminating tests asserting caller-tx contract + NO `INSERT OR REPLACE`.
- **T-A.1.2** — `.claude/agents/pattern-labeler.md` Claude Code project-local subagent definition per OQ-11.
- **T-A.1.3** — `swing/patterns/labeling.py` — `fire_claude_silver_label` + `fire_codex_review_for_silver_row` with selective Codex 15% random sampling per OQ-5 phased rollout + disagreement-chain `parent_exemplar_id` linkage; 4 discriminating tests.
- **T-A.1.4** — Cassette infrastructure (`tests/integrations/cassettes/pattern_labeler/` + `tests/integrations/cassettes/codex_mcp_pattern_review/` + sentinel-leak audit tests + `before_record_request` URI sanitization + `before_record_response` body sanitization per post-Phase-12 forward-binding lesson #2 + standalone recording scripts per lesson #3).
- **T-A.1.5** — `swing patterns label-exemplars` CLI subcommand (`--ticker` + `--start` + `--end` + `--pattern-class` + `--timeframe`); ASCII-only output; 3 discriminating tests.
- **T-A.1.6** — `/patterns/exemplars` GET + `/patterns/exemplars/{id}/action` POST web surface; `PatternExemplarsVM` extending `BaseLayoutVM` with banner pin (`unresolved_material_discrepancies_count` + `banner_resolve_link` + `recent_multi_leg_auto_correction_count`); HTMX gotcha trinity honored (HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted); 7 discriminating tests.
- **T-A.1.7** — **OPERATOR-PAIRED PAUSE** (NOT failable by implementer). Operator runs `swing patterns label-exemplars` against historical universe → produces ~30-80 silver-tier exemplars covering 5 V1 pattern classes → reviews via `/patterns/exemplars` → promotes ≥5 per class to gold (~25 minimum total) → commits exemplar corpus to worktree branch → signals resume.
- **T-A.1.8** — Closer: E2E cassette-mode test exercising Claude silver → Codex review T2.SB1 phase 15% random → disagreement-chain parent_exemplar_id linkage; ruff sweep; full-suite verification (+50-90 fast deltas land cumulatively).
- **Pre-Codex orchestrator-side review** + **Codex adversarial rounds to NO_NEW_CRITICAL_MAJOR** (3-5 rounds expected) — DEFERRED post all 8 task commits.
- **Final return report at `docs/phase13-t2-sb1-return-report.md`** — DEFERRED until full dispatch ships.

### Scope estimate for remaining 8 tasks

Per plan §K projection:
- LOC delta remaining: ~+450-750 production + ~+540-810 test (T-A.1.1 already shipped ~+500 prod / ~+700 test of the total).
- Test delta remaining: +40-80 fast (T-A.1.1 already shipped +10 of ~+50-90 total).
- Wall-clock remaining: ~3-5 substantive Codex rounds + operator-paired pause + closer.

---

## §5 Forward-binding lessons captured during T-A.1.1

NONE NEW. All discipline followed existing CLAUDE.md gotchas + plan §A LOCKs verbatim:

- §A.14 constant-placement LOCK satisfied (constants in `swing/data/models.py`; re-export only in `swing/patterns/__init__.py`).
- Migration backup-gate strict equality (`pre_version == 19`) — followed Phase 9 Sub-bundle A + Phase 12 C.A precedent.
- Schema-CHECK + Python-constant + dataclass-validator paired discipline (Phase 12 C.A T-A.2 LOCK) — all 8 paired-triples atomic in one commit.
- 5 cross-column CHECK invariants on `pattern_exemplars` mirrored in `PatternExemplar.__post_init__` as Python predicates.
- ZERO `INSERT OR REPLACE` (§A.15 LOCK) — migration uses explicit DROP-then-INSERT for schwab_api_calls rebuild; no UPSERT paths in T-A.1.1.

C.C lesson #6 13th cumulative validation: DEFERRED to post-Codex round (final orchestrator-side review before NO_NEW_CRITICAL_MAJOR verdict per plan §A.19 BINDING).

---

## §6 Operator-witnessed gate status

- **S1 (inline pytest + ruff): PASS** — 4949 fast + 6 skipped + 0 errors; ruff 0 E501.
- **S2 (CLI surface check):** N/A for T-A.1.1 alone; surfaces at T-A.1.5 (`swing patterns label-exemplars --help`) + T-A.1.8 (production-readiness check).
- **S3 (operator-paired exemplar bootstrap at T-A.1.7):** PENDING — not yet reached.

---

## §7 Next implementer dispatch handoff

The follow-up implementer session resumes at T-A.1.1b. Suggested dispatch brief footer:

> **Resume context (interim report at `docs/phase13-t2-sb1-interim-return-report.md`):**
> - Worktree: `.worktrees/phase13-t2-sb1-dev-time-labeling-infra/` (branch `phase13-t2-sb1-dev-time-labeling-infra`).
> - Branch HEAD: `4cfd5f2ca9b0103231fb558b141cd87132939d12` (T-A.1.1 SHIPPED).
> - Schema v20 lands at this commit; T3.SB1 worktree branches off here per OQ-12 Option E.
> - Remaining tasks T-A.1.1b → T-A.1.8 per plan §G.1 verbatim; pre-Codex orchestrator review at C.C lesson #6 13th cumulative validation before Codex rounds.
> - Baseline (post-T-A.1.1): 4949 fast tests / 0 ruff E501.

T3.SB1 implementer can dispatch IMMEDIATELY off `4cfd5f2ca9b0103231fb558b141cd87132939d12` — DOES NOT need to wait for T-A.1.1b through T-A.1.8 to ship (per OQ-12 Option E + plan §B.2 #5 concurrent dispatch posture).

---

*End of interim report. T-A.1.1 SHIPPED at SHA `4cfd5f2ca9b0103231fb558b141cd87132939d12`; T3.SB1 concurrent dispatch UNBLOCKED; remaining 8 tasks DEFERRED to next implementer session per single-session capacity envelope. ZERO Co-Authored-By footer drift; ZERO ACCEPT-WITH-RATIONALE in this partial; full §A.14 paired-atomic-landing discipline satisfied.*
