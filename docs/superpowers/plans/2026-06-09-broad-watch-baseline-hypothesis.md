# Broad-Watch-Baseline Hypothesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register a fifth pre-registered hypothesis — a *broad-watch baseline* (`bucket==watch`, any non-pass set, not otherwise hypothesized) — via migration `0026` (schema v25→v26) and a two-phase opt-in fallback matcher, so the shadow-expectancy engine prices the watch population the temporal log now accrues.

**Architecture:** Additive registry row (NO new column, NO `ALTER`) seeded by migration `0026` + a `hypothesis_status_history` open-interval seed; `swing/data/db.py` bumps `EXPECTED_SCHEMA_VERSION` 25→26 with a strict-equality backup gate; `swing/recommendations/hypothesis.py` gains a `H_BROAD_WATCH_BASELINE` constant + a `_broad_watch_baseline_match` predicate + a keyword-only `include_baseline: bool = False` two-phase fallback gate (`if include_baseline and not matches:`); the shadow engine's `attribution.py` is the ONLY opt-in caller. Live recommendation surfaces are contained-by-construction (default `False`); tier/deviation surfaces auto-exclude the 5th cohort via their existing 4-name allowlist.

**Tech Stack:** Python 3.14, SQLite (migration runner in `swing/data/db.py`), pytest (`-m "not slow"` fast suite), ruff. Frozen-registry amendment route: V2.1 §VII.F.

**Binding spec:** `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md` (commit `99e0608f`). Do NOT re-open its settled decisions (two-phase fallback matcher; `include_baseline` opt-in; NO `measurement_only` column; `tier.py` untouched; frozen H1–H4 rows untouched; no engine funnel/scorecard change; no new production dependency).

---

## Verified live-DB data shapes (read-only `~/swing-data/swing.db`, 2026-06-09)

These were re-confirmed against the live DB while writing this plan and are the ground truth for every fixture. **Codex must independently re-verify these against the supplied query output — fixtures must NOT force them true (memory `feedback_adversarial_review_verify_data_shapes`).**

- `schema_version = 25` → migration `0026 → v26` is the correct next bump.
- Registry: `(1, 'A+ baseline', active, 20)`, `(2, 'Near-A+ defensible: extension test', active, 10)`, `(3, 'Sub-A+ VCP-not-formed', closed-target-met, 5)`, `(4, 'Capital-blocked: smaller-position test', active, 10)`. The engine's `status='active'` load EXCLUDES H3.
- Watch-pool non-pass composition (400 most-recent `watch` candidates), top sets:
  `{proximity_20ma,tightness}`=110, `{adr,tightness}`=61, `{tightness,vcp_volume_contraction}`=60, `{tightness}`=36, `{TT8_rs_rank,tightness,vcp_volume_contraction}`=20, `{orderliness,tightness}`=15, `{adr}`=15, `{TT8_rs_rank,adr,tightness}`=10, …
- **H2-exact `=={proximity_20ma}` = 1 of 400; H4-exact `=={risk_feasibility}` = 0 of 400.** (Fixtures 2/3 are "rare but real".)
- `criterion_name` vocabulary present in `candidate_criteria`: `TT1_above_150_200`, `TT2_150_above_200`, `TT3_200_rising`, `TT4_50_above_150_200`, `TT5_above_50`, `TT6_above_52w_low_30pct`, `TT7_within_52w_high_25pct`, `TT8_rs_rank`, `adr`, `ma_short_rising`, `ma_stack_10_20_50`, `orderliness`, `prior_trend`, `proximity_20ma`, `pullback`, `risk_feasibility`, `tightness`, `vcp_volume_contraction`. Fixtures draw ONLY from this vocabulary.

**Fixture/CRITICAL distinction (spec §7.1):** H3's `closed-target-met` was set on the LIVE DB by an operator CLI action — it is NOT in any migration. A FRESH migrated test DB seeds ALL of H1–H4 (and now H5) as `active` (0008/0026 default `'active'`). So:
- **Live DB at head (v26):** 5 rows, **4 active** (H3 closed).
- **Fresh migrated/`ensure_schema` test DB at head (v26):** 5 rows, **5 active** (H3 active unless the test closes it).

---

## File Map

**Production (the spec §8 carve-out — exactly these four + tests):**
- `swing/data/migrations/0026_broad_watch_baseline.sql` — **CREATE.** Frozen spec §2 SQL: `BEGIN;` + registry `INSERT OR IGNORE` + `hypothesis_status_history` open-interval seed (scoped to the new row) + `UPDATE schema_version SET version = 26;` + `COMMIT;`.
- `swing/data/db.py` — **MODIFY.** `EXPECTED_SCHEMA_VERSION` 25→26; new `BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES` constant; `_create_pre_broad_watch_migration_backup` helper; `_broad_watch_baseline_backup_gate`; gate registration in `run_migrations`.
- `swing/recommendations/hypothesis.py` — **MODIFY.** `H_BROAD_WATCH_BASELINE` constant; `_broad_watch_baseline_match` predicate; keyword-only `include_baseline: bool = False` param + the two-phase post-loop gate in `match_candidate_to_hypotheses`.
- `research/harness/shadow_expectancy/attribution.py` — **MODIFY.** Pass `include_baseline=True` (the ONLY opt-in caller).

**Tests (new):**
- `tests/data/test_migration_0026_broad_watch_baseline.py` — migration mechanics + backup gate + migrate-twice no-op + history seed.

**Tests (modify — the #11 sweep, §7.1 + the omitted version-pin family):**
- Matcher: `tests/recommendations/test_hypothesis_matcher.py` (add baseline + containment + name-safety tests).
- Engine: `tests/research/shadow_expectancy/testkit.py` (target_version 24→26), `tests/research/shadow_expectancy/test_attribution.py` (flip + new fixtures), `tests/research/shadow_expectancy/test_run.py` (priced-end-to-end + H3-flip golden fixtures).
- Hypothesis-count pins: `tests/data/test_repos_hypothesis.py`, `tests/data/test_db_v8.py`, `tests/journal/test_hypothesis_progress.py`, `tests/metrics/test_cohort.py`, `tests/web/test_view_models/test_trade_process_card_vm.py`, `tests/web/test_view_models/test_hypothesis_progress_card_vm.py`, `tests/web/test_routes/test_metrics_routes.py`.
- Schema-version head-pins (→26): the migration-test family enumerated in **Task 2 Step 7**.
- Prose-only: `tests/data/test_phase9_hypothesis_seed_verification.py`, `tests/data/test_migration_0017.py`, `tests/web/test_routes/test_phase10_metrics_e2e.py`, `tests/cli/test_cli_journal.py`.

**NOT touched (locks — spec §8):** `swing/metrics/tier.py`, `swing/web/view_models/metrics/tier_comparison.py`, `swing/web/view_models/metrics/deviation_outcome.py` (allowlist auto-excludes the 5th cohort; their `== 4` STAYS 4), `swing/data/models.py`, `swing/data/repos/hypothesis.py`, live recommendation call sites (`dashboard.py`, `hypothesis_prefill.py`), `swing/metrics/cohort.py`, the progress/process-card VMs, `journal/stats.py`, `cli.py` hypothesis/journal surfaces (CODE — only their TESTS update), `DOCTRINE_DEFENSIBLE_MISS_SET`, the four frozen H1–H4 rows, the engine simulator/bracket/funnel/scorecard/`constants.py`. No new production dependency.

---

## Task 1: Two-phase opt-in matcher (`swing/recommendations/hypothesis.py`)

The matcher change is orthogonal to the schema version — its unit tests construct an in-memory registry that includes the baseline row, so this task is fully green standalone. Default `include_baseline=False` means every existing matcher/recommendation test is unaffected.

**Files:**
- Modify: `swing/recommendations/hypothesis.py` (constant block ~L124-130; matcher ~L296-334)
- Test: `tests/recommendations/test_hypothesis_matcher.py`

- [ ] **Step 1: Write failing matcher unit tests (baseline fallback + containment + anti-cannibalization + name-safety)**

Append to `tests/recommendations/test_hypothesis_matcher.py`. The file already has `_candidate(bucket, results)` and `_registry()` (4 active rows). Add a baseline-augmented registry helper and the new tests:

```python
from swing.recommendations.hypothesis import (  # extend existing import
    H_BROAD_WATCH_BASELINE,
    match_candidate_to_hypotheses,
)


def _registry_with_baseline(*, h3_status: str = "active"):
    """The 4 v0.1 rows + the migration-0026 baseline row (active).
    h3_status lets a test close H3 to exercise the active-set complement."""
    reg = _registry()
    for i, h in enumerate(reg):
        if h.name == "Sub-A+ VCP-not-formed":
            reg[i] = HypothesisRegistryEntry(
                id=h.id, name=h.name, statement=h.statement,
                target_sample_size=h.target_sample_size,
                decision_criteria=h.decision_criteria, status=h3_status,
                consecutive_loss_tripwire=h.consecutive_loss_tripwire,
                absolute_loss_tripwire_pct=h.absolute_loss_tripwire_pct,
                created_at=h.created_at,
            )
    reg.append(HypothesisRegistryEntry(
        id=5, name="Broad-watch baseline",
        statement="x", target_sample_size=30,
        decision_criteria="x", status="active",
        consecutive_loss_tripwire=5, absolute_loss_tripwire_pct=5.0,
        created_at="2026-06-09",
    ))
    return reg


def test_broad_watch_name_constant():
    assert H_BROAD_WATCH_BASELINE == "Broad-watch baseline"


def test_baseline_fires_only_with_opt_in_for_pure_watch():
    # Fixture 5 (spec §9.1.5): a real {adr} watch miss (no H2/H3/H4 fit).
    cand = _candidate("watch", [("adr", "vcp", "fail")])
    reg = _registry_with_baseline()
    # default include_baseline=False -> live path -> ZERO matches (containment).
    assert match_candidate_to_hypotheses(cand, registry=reg) == []
    # opt-in -> exactly the baseline.
    matches = match_candidate_to_hypotheses(cand, registry=reg, include_baseline=True)
    assert [m.hypothesis_name for m in matches] == ["Broad-watch baseline"]


def test_baseline_silent_when_narrow_rule_fires_h2():
    # Fixture 2 (spec §9.1.2): anti-cannibalization. {proximity_20ma} -> H2 ONLY.
    cand = _candidate("watch", [("proximity_20ma", "trend_template", "fail")])
    matches = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True)
    names = [m.hypothesis_name for m in matches]
    assert names == ["Near-A+ defensible: extension test"]   # len==1, NO baseline


def test_baseline_silent_when_narrow_rule_fires_h4():
    # Fixture 3 (spec §9.1.3): {risk_feasibility} watch -> H4 ONLY.
    cand = _candidate("watch", [("risk_feasibility", "risk", "fail")])
    matches = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True)
    assert [m.hypothesis_name for m in matches] == [
        "Capital-blocked: smaller-position test"]


def test_baseline_membership_flips_on_h3_active_status():
    # Fixture 4 (spec §9.1.4): the dominant real shape {tightness, vcp_volume_contraction}.
    cand = _candidate("watch", [("tightness", "vcp", "fail"),
                                ("vcp_volume_contraction", "vcp", "fail")])
    # H3 ACTIVE -> H3 claims it; baseline silent.
    m_active = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(h3_status="active"),
        include_baseline=True)
    assert [m.hypothesis_name for m in m_active] == ["Sub-A+ VCP-not-formed"]
    # H3 CLOSED (today's live state) -> falls to the baseline.
    m_closed = match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(h3_status="closed-target-met"),
        include_baseline=True)
    assert [m.hypothesis_name for m in m_closed] == ["Broad-watch baseline"]


def test_baseline_does_not_fire_for_non_watch_even_opted_in():
    # Baseline requires bucket=='watch'. A skip miss stays unmatched (keeps the
    # matched_no_hypothesis funnel reason reachable). Spec §9.1 / §7.2.
    cand = _candidate("skip", [("tightness", "vcp", "fail")])
    assert match_candidate_to_hypotheses(
        cand, registry=_registry_with_baseline(), include_baseline=True) == []


def test_baseline_absent_from_registry_yields_no_match_even_opted_in():
    # If the baseline row is not present+active (e.g. pre-0026), the gate cannot
    # synthesize a match (no id) -> []. Order-robust by construction.
    cand = _candidate("watch", [("adr", "vcp", "fail")])
    assert match_candidate_to_hypotheses(
        cand, registry=_registry(), include_baseline=True) == []


def test_broad_watch_name_no_prefix_collision_both_directions():
    # Spec §6: 3-rule delimiter-aware contract; no prefix collision either way.
    from swing.metrics.label_match import label_matches_hypothesis
    others = ["A+ baseline", "Near-A+ defensible: extension test",
              "Sub-A+ VCP-not-formed", "Capital-blocked: smaller-position test"]
    labelled = "Broad-watch baseline (watch); failed: adr"
    for other in others:
        assert label_matches_hypothesis(labelled, other) is False
        assert label_matches_hypothesis(f"{other} (watch); failed: x",
                                        "Broad-watch baseline") is False
    # exact-name still matches itself.
    assert label_matches_hypothesis("Broad-watch baseline", "Broad-watch baseline")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/recommendations/test_hypothesis_matcher.py -k "baseline or broad_watch" -q`
Expected: FAIL — `ImportError: cannot import name 'H_BROAD_WATCH_BASELINE'` (collection error). (Pre-fix arithmetic: the symbol does not exist and the matcher has no `include_baseline` kwarg, so every new test errors at import/call.)

- [ ] **Step 3: Add the constant + predicate**

In `swing/recommendations/hypothesis.py`, after the existing name constants (~L130, after `H_CAPITAL_BLOCKED`):

```python
H_BROAD_WATCH_BASELINE = "Broad-watch baseline"
```

Add the predicate near the other `_*_match` functions (after `_capital_blocked_match`, ~L257):

```python
def _broad_watch_baseline_match(candidate: Candidate) -> bool:
    """Watch bucket, any non-pass set. The fallback gate (caller-side, on
    `not matches`) -- NOT this predicate -- enforces the complement semantics
    (spec §3.1). Fires only when the caller opts in AND no narrow rule matched."""
    return candidate.bucket == "watch"
```

- [ ] **Step 4: Add the `include_baseline` param + two-phase gate**

Modify `match_candidate_to_hypotheses` signature (add a keyword-only param) and append the post-loop baseline phase. The narrow `rules` list is UNCHANGED — the baseline is a structural gate, NOT a list entry (spec §3.1):

```python
def match_candidate_to_hypotheses(
    candidate: Candidate,
    *,
    doctrine_defensible_set: frozenset[str] = DOCTRINE_DEFENSIBLE_MISS_SET,
    registry: Iterable[HypothesisRegistryEntry],
    include_baseline: bool = False,
) -> list[HypothesisMatch]:
```

Then, immediately before `return matches` (after the `for name, rule in rules:` loop):

```python
    # Baseline phase (spec §3.1): the broad-watch fallback fires iff the caller
    # opted in AND the narrow phase returned ZERO matches. Order-robust -- gated
    # on the emptiness of `matches`, not on list position. Requires the row to
    # be active+present (mirrors the narrow rules; the engine loads status=='active'
    # only). The ONLY opt-in caller is the shadow-expectancy attribution wrapper.
    if include_baseline and not matches:
        h = active_by_name.get(H_BROAD_WATCH_BASELINE)
        if h is not None and _broad_watch_baseline_match(candidate):
            matches.append(HypothesisMatch(
                hypothesis_id=h.id,
                hypothesis_name=h.name,
                suggested_label_descriptive=_descriptive_label(candidate, h.name),
                priority_hint=_priority_hint_for(candidate),
                candidate_ticker=candidate.ticker,
            ))
    return matches
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `python -m pytest tests/recommendations/test_hypothesis_matcher.py -q`
Expected: PASS (new tests green; the pre-existing matcher tests unaffected — default `include_baseline=False`).

- [ ] **Step 6: Commit**

```bash
git add swing/recommendations/hypothesis.py tests/recommendations/test_hypothesis_matcher.py
git commit -m "feat(recommendations): add broad-watch-baseline two-phase opt-in matcher"
```

---

## Task 2: Migration 0026 + db.py schema gate + the #11 pin sweep + testkit bump

This is the atomic schema unit (#11 atomicity). The `EXPECTED_SCHEMA_VERSION` bump turns the entire version-pin and hypothesis-count families red, so the pin sweep and the testkit bump land in THIS task to end green. The matcher change (Task 1) is already in; `attribution.py` stays default-`False` here, so `test_attribution` and the engine `test_run` suite remain green through this task.

**Files:**
- Create: `swing/data/migrations/0026_broad_watch_baseline.sql`
- Modify: `swing/data/db.py`
- Create: `tests/data/test_migration_0026_broad_watch_baseline.py`
- Modify (sweep): the test files enumerated in Steps 6–8.

- [ ] **Step 1: Write the failing migration + gate test**

Create `tests/data/test_migration_0026_broad_watch_baseline.py` (mirrors `tests/data/test_migration_0025_phase16.py`):

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    MigrationBackupRequiredException,
    _broad_watch_baseline_backup_gate,
    _current_version,
    run_migrations,
)


def _migrate(tmp_path: Path, version: int, backup_dir: Path | None = None):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=version,
                   backup_dir=backup_dir or tmp_path)
    return conn


def test_expected_schema_version_is_26():
    assert EXPECTED_SCHEMA_VERSION == 26


def test_migrate_to_26_seeds_broad_watch_row(tmp_path):
    conn = _migrate(tmp_path, 26)
    assert _current_version(conn) == 26
    row = conn.execute(
        "SELECT name, target_sample_size, status, consecutive_loss_tripwire, "
        "absolute_loss_tripwire_pct, created_at, statement, decision_criteria, notes "
        "FROM hypothesis_registry WHERE name = 'Broad-watch baseline'"
    ).fetchone()
    assert row is not None
    assert row[1] == 30                      # target_sample_size
    assert row[2] == "active"                # status (default)
    assert row[3] == 5                       # consecutive_loss_tripwire
    assert row[4] == 5.0                     # absolute_loss_tripwire_pct
    assert row[5] == "2026-06-09"            # created_at
    assert row[6].startswith("The widened watch pool")
    assert row[7].startswith("SHADOW-measured (not closed live trades)")
    assert "V2.1 §VII.F" in row[8]
    # exactly 5 rows; the 4 frozen rows untouched.
    assert conn.execute("SELECT COUNT(*) FROM hypothesis_registry").fetchone()[0] == 5
    conn.close()


def test_migrate_to_26_seeds_one_open_history_interval(tmp_path):
    conn = _migrate(tmp_path, 26)
    hid = conn.execute(
        "SELECT id FROM hypothesis_registry WHERE name='Broad-watch baseline'"
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT status, effective_from, effective_to FROM hypothesis_status_history "
        "WHERE hypothesis_id = ?", (hid,)).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "active"
    assert rows[0][1] == "2026-06-09T00:00:00.000"
    assert rows[0][2] is None                # one OPEN interval
    conn.close()


def test_migrate_twice_is_noop(tmp_path):
    conn = _migrate(tmp_path, 26)
    run_migrations(conn, target_version=26)  # current >= target -> early return
    assert _current_version(conn) == 26
    assert conn.execute(
        "SELECT COUNT(*) FROM hypothesis_registry WHERE name='Broad-watch baseline'"
    ).fetchone()[0] == 1
    hid = conn.execute(
        "SELECT id FROM hypothesis_registry WHERE name='Broad-watch baseline'"
    ).fetchone()[0]
    assert conn.execute(
        "SELECT COUNT(*) FROM hypothesis_status_history WHERE hypothesis_id=?",
        (hid,)).fetchone()[0] == 1           # NO second open interval
    conn.close()


def test_backup_gate_fires_strict_on_v25(tmp_path):
    # In-memory connection -> file-backed source is absent -> raises.
    conn = sqlite3.connect(":memory:")
    inert = tmp_path / "inert"; fire = tmp_path / "fire"; naive = tmp_path / "naive"
    # current==26 -> already past, inert (no raise).
    _broad_watch_baseline_backup_gate(conn, current_version=26, target_version=26,
                                      backup_dir=inert)
    # current==24, target==26 -> multi-version jump bypasses the v25-strict gate.
    _broad_watch_baseline_backup_gate(conn, current_version=24, target_version=26,
                                      backup_dir=naive)
    assert not inert.exists() and not naive.exists()
    # current==25, target>=26 -> fires; in-memory source -> raises.
    with pytest.raises(MigrationBackupRequiredException):
        _broad_watch_baseline_backup_gate(conn, current_version=25, target_version=26,
                                          backup_dir=fire)


def test_run_migrations_wires_broad_watch_gate(tmp_path):
    # v25 DB crossing v26 through the REAL runner writes exactly one backup.
    backups = tmp_path / "v25_backups"; backups.mkdir()
    conn = _migrate(tmp_path, 25)            # build a real file-backed v25 DB
    conn.close()
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=26, backup_dir=backups)
    assert _current_version(conn) == 26
    snaps = list(backups.glob("swing-pre-broad-watch-baseline-migration-*.db"))
    assert len(snaps) == 1
    conn.close()
```

- [ ] **Step 2: Run the migration test to verify it fails**

Run: `python -m pytest tests/data/test_migration_0026_broad_watch_baseline.py -q`
Expected: FAIL — `ImportError: cannot import name '_broad_watch_baseline_backup_gate'` (and `EXPECTED_SCHEMA_VERSION == 26` would be `25`). Pre-fix: neither the gate nor the migration exists.

- [ ] **Step 3: Create the migration SQL (frozen spec §2 text, verbatim)**

Create `swing/data/migrations/0026_broad_watch_baseline.sql` with EXACTLY the spec §2 content (the `||` are SQLite string-literal concatenation for line-wrapping; the stored value has no embedded newlines):

```sql
-- Migration 0026: broad-watch-baseline hypothesis (V2.1 §VII.F amendment).
-- ADDITIVE. The four frozen H1-H4 rows from 0008 are UNTOUCHED. INSERT OR IGNORE
-- keyed on the UNIQUE `name` column (mirrors 0008) so a re-run is a no-op.
-- Explicit BEGIN;...COMMIT; per gotcha #9 (executescript runs in autocommit;
-- _apply_migration does NOT open its own transaction -- 0023/0024/0025 all wrap).
-- Load-bearing here: the history INSERT...SELECT below is NON-idempotent, so a
-- mid-script failure must roll back the registry insert too.
BEGIN;
INSERT OR IGNORE INTO hypothesis_registry
  (name, statement, target_sample_size, decision_criteria,
   consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at, notes)
VALUES
  ('Broad-watch baseline',
   'The widened watch pool (bucket==watch, any non-pass set, not matching a '
   || 'narrower active hypothesis), priced by the mechanical shadow ruleset, '
   || 'establishes the baseline expectancy of the population the temporal log '
   || 'contains and the operator actually trades.',
   30,
   'SHADOW-measured (not closed live trades): primary read = realistic bracket '
   || 'arm on the closed_only and mtm_at_horizon censoring scenarios at N>=30 '
   || 'priced shadow signals; report mean R + Wilson lower-bound win rate across '
   || 'all four censoring scenarios. Pre-registered as a BASELINE: negative or '
   || 'zero mean R is a bankable validation of A+ gate selectivity; positive mean '
   || 'R triggers cohort-refinement research (which miss-sets carry the edge), '
   || 'NOT direct deployment.',
   5, 5.0, '2026-06-09',
   'Measurement substrate is the shadow-expectancy engine '
   || '(research/harness/shadow_expectancy), not labeled live trades. The baseline '
   || 'cohort = watch signals NOT otherwise matching a narrower active hypothesis '
   || '(the honest complement, via fallback matching). Surfaced by the production '
   || 'matcher ONLY in shadow/measurement context (opt-in); live recommendation '
   || 'surfaces never surface it. Tripwires apply only if the operator labels live '
   || 'watch trades with this hypothesis (permitted; matches practice). Not an '
   || 'operator recommendation cohort. Registry amendment via migration 0026 per '
   || 'V2.1 §VII.F.');

-- Seed the initial OPEN status-history interval for the new row, mirroring
-- migration 0017's per-row seed. Without this the governance/progress timeline
-- is EMPTY until the first status transition. Scoped to the new row only (the
-- four frozen rows already have their 0017 seed -- UNTOUCHED).
INSERT INTO hypothesis_status_history
  (hypothesis_id, status, effective_from, effective_to, change_reason, recorded_at)
SELECT id, status,
       strftime('%Y-%m-%dT00:00:00.000', created_at), NULL, NULL,
       strftime('%Y-%m-%dT%H:%M:%f', 'now')
FROM hypothesis_registry
WHERE name = 'Broad-watch baseline';

UPDATE schema_version SET version = 26;
COMMIT;
```

- [ ] **Step 4: Bump `EXPECTED_SCHEMA_VERSION` + add the expected-tables constant**

In `swing/data/db.py`:
- Line 51: `EXPECTED_SCHEMA_VERSION = 25` → `EXPECTED_SCHEMA_VERSION = 26`.
- After the `PHASE16_PRE_MIGRATION_EXPECTED_TABLES` block (~L226), add the true-v25 set (the PHASE16 constant aliases the v24/B7 set and intentionally EXCLUDES `pipeline_step_timings`, which 0025 created — spec §7 / Codex R2-M2):

```python
# Broad-watch-baseline (migration 0026) backup gate: migrating v25 -> v26
# snapshots the live v25 DB. 0026 adds NO table (additive registry row only), so
# the v26 table set equals the v25 set. The v25 set = the v24 set PLUS
# pipeline_step_timings (created by 0025) -- PHASE16_PRE_MIGRATION_EXPECTED_TABLES
# is the v24 set, so derive the v25 set from it for auditable provenance.
BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE16_PRE_MIGRATION_EXPECTED_TABLES | {"pipeline_step_timings"}
)
```

- [ ] **Step 5: Add the backup helper + the strict gate + register it**

In `swing/data/db.py`, after `_create_pre_phase16_migration_backup` (~L680):

```python
def _create_pre_broad_watch_migration_backup(
    src_path: Path, *, dest_dir: Path,
) -> Path:
    """Broad-watch-baseline (0026) mirror. SQLite-native Connection.backup()
    before the 0026 migration. Backup file pattern
    ``swing-pre-broad-watch-baseline-migration-<ISO>.db``."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = dest_dir / f"swing-pre-broad-watch-baseline-migration-{timestamp}.db"
    src_conn = open_connection(src_path, busy_timeout_ms=DEFAULT_BUSY_TIMEOUT_MS)
    try:
        dest_conn = sqlite3.connect(backup_path)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return backup_path
```

After `_phase16_backup_gate` (~L1130):

```python
def _broad_watch_baseline_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Broad-watch-baseline (0026) backup-before-migrate gate.

    Fires ONLY when ``current_version == 25 AND target_version >= 26`` -- a real
    production v25 DB about to cross v26. STRICT EQUALITY on pre_version per the
    ``pre_version == (target - 1)`` gotcha (NOT ``<=``); multi-version jumps from
    pre-v25 baselines bypass this gate by design.
    """
    if target_version < 26 or current_version != 25:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-broad-watch backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_broad_watch_migration_backup(
            src_path, dest_dir=backup_dir)
        _verify_backup_integrity(
            backup_path, expected_tables=BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-broad-watch backup failed: {exc}"
        ) from exc
```

Register it in `run_migrations`, immediately after the `_phase16_backup_gate(...)` call (~L1216):

```python
    _broad_watch_baseline_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
```

- [ ] **Step 6: Run the migration test — expect PASS; then run the hypothesis-count + version-pin families — expect the predicted RED**

Run: `python -m pytest tests/data/test_migration_0026_broad_watch_baseline.py -q`
Expected: PASS.

Run: `python -m pytest tests/data tests/recommendations tests/journal tests/metrics tests/web/test_view_models tests/web/test_routes -q`
Expected: the version-pin and hypothesis-count assertions fail (this is the predicted red the sweep fixes). Use this run to confirm the sweep list below is exhaustive — any failure NOT in Steps 7–8 must be triaged with the rule and added.

- [ ] **Step 7: Schema-version head-pin sweep (→ 26)**

These all reach HEAD via `ensure_schema` or assert the `EXPECTED_SCHEMA_VERSION` constant. Per `feedback_regression_test_arithmetic`: pre-0026 each asserts `25` (passes today); post-0026 head is `26`, so each `25` literal that tracks head must become `26`. Stale test/comment names are PRESERVED per repo convention (`stale-name-but-current-assertion`); only the asserted value changes.

`EXPECTED_SCHEMA_VERSION == 25` → `== 26`:
- `tests/data/test_b7_failure_mode_schema.py:45`
- `tests/data/test_db_v8.py:112`
- `tests/data/test_migration_0012.py:38`
- `tests/data/test_migration_0015_finviz_api_calls.py:59`
- `tests/data/test_migration_0017.py:44`
- `tests/data/test_migration_0018.py:65`
- `tests/data/test_migration_0019_atomic_apply.py:65`
- `tests/data/test_migration_0025_phase16.py:29`
- `tests/data/test_no_schema_change_v3.py:15`
- `tests/data/test_phase13_t3_sb1_prerequisite.py:54`
- `tests/data/test_temporal_log_migration.py:30`
- `tests/data/test_v20_migration.py:236`
- `tests/data/test_v21_migration_trade_backlinks.py:722`
- `tests/data/test_v23_migration.py:115`

Head-tracking `version`/`row[0]`/`post`/`_current_version` literals reached via `ensure_schema` (→ HEAD): `25` → `26`:
- `tests/data/test_migration_0010_trade_chart_pattern.py:18`
- `tests/data/test_migration_0013.py:27`
- `tests/data/test_migration_0015_finviz_api_calls.py:18`
- `tests/data/test_migration_0016.py:38`
- `tests/data/test_migration_0017.py:49`
- `tests/data/test_migration_0018.py:70`
- `tests/data/test_migration_0019_atomic_apply.py:70` and `:86`
- `tests/data/test_phase13_t3_sb1_prerequisite.py:199` (`version == EXPECTED_SCHEMA_VERSION == 26`)
- `tests/data/test_v20_migration.py:233` and `:833`
- `tests/data/test_v21_migration_trade_backlinks.py:787`

**`tests/data/test_migration_0025_phase16.py` — mixed; reason about each:**
- `:29` `EXPECTED_SCHEMA_VERSION == 25` → `26` (head pin, above).
- `:35`, `:51`, `:95` assert reaching `v25` via an EXPLICIT `target_version=25` walk → **STAY `25`** (they test 0025 specifically; pre- and post-0026 both stop at 25).
- `:107` — the ceiling-clamp scenario `test_run_migrations_wires_phase16_gate`: a v24 DB run with `target_version=26`. **Pre-0026:** `apply_ceiling = min(26, EXPECTED=25) = 25`, so it clamped to 25 (the old assertion `== 25`). **Post-0026:** `apply_ceiling = min(26, EXPECTED=26) = 26`; the walk applies 0025 then 0026 (the broad-watch gate is INERT here because the runner evaluates gates once against the ORIGINAL `current=24`, not 25), reaching **26**. Update `:107` assertion `== 25` → `== 26` AND update its inline comment (it no longer demonstrates ceiling-clamp-at-25 — note that the ceiling now equals the target). Compute both ways to confirm the assertion distinguishes: pre-fix the walk yields 25, post-fix 26.

**STAY (migration-pinned via explicit `run_migrations(target_version=N<26)`) — do NOT touch:** `tests/data/test_migration_0018.py:451,482,529,538`; `tests/data/test_migration_0019_atomic_apply.py:216,249`; `tests/data/test_temporal_log_migration.py` (all `target_version=21/22`); `tests/data/test_v23_migration.py` (all `target_version=21/22/23`).

After editing, run: `python -m pytest tests/data -q` → Expected: PASS (incl. the new 0026 test).

- [ ] **Step 8: Hypothesis-count + cohort-tab sweep (ensure_schema head → 5 rows / 5 active)**

Each builds the DB at HEAD via `ensure_schema`, so post-0026 the registry has 5 rows, **all 5 active** (fresh DB; H3 not closed). Arithmetic: pre-0026 = 4; post-0026 = 5 (and `active` = 5, NOT 4 — the live-DB H3-closed state is absent in fixtures).

- `tests/data/test_repos_hypothesis.py`:
  - `:35` `len(rows) == 4` → `== 5`; add `"Broad-watch baseline"` to the name-set at `:39-44`.
  - `:54` `len(active) == 4` → `== 5` (fresh DB: H3 active).
- `tests/data/test_db_v8.py`:
  - `:48` `len(rows) == 4` → `== 5`; append `"Broad-watch baseline"` to the `names` list `:50-55`.
  - `:57` `all(r[2] == "active" ...)` STAYS (the 5th seeds active).
  - `:106` `n == 4` → `== 5` (update the message string too).
  - (`:112` handled in Step 7.)
- `tests/journal/test_hypothesis_progress.py`:
  - `:111` `len(rows) == 4` → `== 5`; append `"Broad-watch baseline"` to the `names ==` list (it is `ORDER BY id`, so the 5th id appends last).
- `tests/metrics/test_cohort.py`:
  - `test_count_per_cohort_returns_all_4_cohorts_even_when_zero` (`:149`): the `set(result.keys()) == {...}` (`:153-159`) must add `"Broad-watch baseline"`; the `for ... count == 0` loop stays.
  - `test_count_per_cohort_includes_orphan_labels` (`:182`): asserts specific keys only — robust; no change required, but confirm `result["Broad-watch baseline"] == 0` is implied (no edit needed unless the suite flags it).
- `tests/web/test_view_models/test_trade_process_card_vm.py`:
  - `test_vm_renders_4_cohort_tabs_plus_all_toggle` (`:77`): `len(vm.cohort_tabs) == 5` → `== 6` (5 cohorts + All); add `"Broad-watch baseline"` to the `registered ==` set (`:86-91`).
- `tests/web/test_view_models/test_hypothesis_progress_card_vm.py`:
  - `:129` `len(vm.cohorts) == 4` → `== 5`.
- `tests/web/test_routes/test_metrics_routes.py`:
  - `test_trade_process_renders_all_5_tabs_in_html_body` (`:140`): add `"Broad-watch baseline"` to the label tuple (`:147-152`).
  - `test_hypothesis_progress_renders_all_4_cohorts` (`:220`): add `"Broad-watch baseline"` to the label tuple.

**STAY 4 (tier/deviation allowlist — do NOT touch):** `tests/metrics/test_tier.py:135,156`; `tests/integration/test_phase10_bundle_c_e2e.py:243` (a `TierComparisonResult` — `cohort_name`/`APLUS_COHORT`/`row_suppressed`).

**Prose/docstring-only (no assertion change; update the "4" wording for accuracy):** `tests/data/test_phase9_hypothesis_seed_verification.py:15` (its assertions are idempotency `count1==count2` + `n_hyp >= 1`, robust to 5); `tests/data/test_migration_0017.py:404` (asserts `n_hyp >= 1` + history==registry, robust); `tests/web/test_routes/test_phase10_metrics_e2e.py:4,45` (docstrings); `tests/cli/test_cli_journal.py:219,233` (prose; the `len(...)==1` assertions are per-cohort lines, not a registry count). If the Step-6 run shows any of these actually fail on a hard count, triage with the rule and bump.

- [ ] **Step 9: Bump the shadow-engine testkit to v26**

`tests/research/shadow_expectancy/testkit.py:13`: `run_migrations(c, target_version=24, backup_dir=tmp_path)` → `target_version=26`. This seeds the 5th row (active) for engine fixtures. `attribution.py` is still default-`False` in this task, so `test_attribution`/`test_run` remain green (baseline never fires yet).

- [ ] **Step 10: Run the affected suites — expect GREEN**

Run: `python -m pytest tests/data tests/recommendations tests/journal tests/metrics tests/web tests/research/shadow_expectancy tests/integration/test_phase10_bundle_c_e2e.py -q`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add swing/data/migrations/0026_broad_watch_baseline.sql swing/data/db.py \
  tests/data/test_migration_0026_broad_watch_baseline.py tests/data tests/recommendations \
  tests/journal/test_hypothesis_progress.py tests/metrics/test_cohort.py \
  tests/web/test_view_models/test_trade_process_card_vm.py \
  tests/web/test_view_models/test_hypothesis_progress_card_vm.py \
  tests/web/test_routes/test_metrics_routes.py tests/web/test_routes/test_phase10_metrics_e2e.py \
  tests/cli/test_cli_journal.py tests/research/shadow_expectancy/testkit.py
git commit -m "feat(data): migration 0026 broad-watch-baseline registry row + schema v26 gate"
```

---

## Task 3: Attribution opt-in + engine golden fixtures (priced end-to-end + H3 flip + funnel reachability)

Now `attribution.py` opts in, so the engine attributes the watch population to the baseline. This task flips `test_no_match_returns_empty` (it now falls to the baseline) and adds the end-to-end golden fixtures.

**Files:**
- Modify: `research/harness/shadow_expectancy/attribution.py`
- Modify: `tests/research/shadow_expectancy/test_attribution.py`
- Modify: `tests/research/shadow_expectancy/test_run.py`

- [ ] **Step 1: Write the failing attribution + engine fixtures**

In `tests/research/shadow_expectancy/test_attribution.py`, REPLACE `test_no_match_returns_empty` and ADD fixtures (the file already has `_cand`, `_active_registry`):

```python
def test_unmatched_watch_falls_to_baseline(tmp_path):
    # Renamed from test_no_match_returns_empty: with the engine opted in
    # (include_baseline=True via attribute_hypotheses) and the v26 testkit
    # seeding the active baseline row, a watch/{orderliness} miss now attributes
    # to the broad-watch baseline (the honest complement). Spec §7.2.
    conn = make_db(tmp_path)
    cand = _cand("watch", [("orderliness", "vcp", "fail")])
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == [
        "Broad-watch baseline"]


def test_non_watch_unmatched_stays_empty(tmp_path):
    # Preserve a genuine empty-match (matched_no_hypothesis stays reachable):
    # baseline requires bucket=='watch', so a skip/{tightness} miss matches NOTHING
    # even opted in. Spec §7.2 / §9.1.
    conn = make_db(tmp_path)
    cand = _cand("skip", [("tightness", "vcp", "fail")])
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == []


def test_h2_exact_does_not_cannibalize_to_baseline(tmp_path):
    # Fixture 2 at the attribution level: {proximity_20ma} -> H2 ONLY.
    conn = make_db(tmp_path)
    cand = _cand("watch", [("proximity_20ma", "trend_template", "fail")])
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == [
        "Near-A+ defensible: extension test"]


def test_h3_flip_active_vs_closed(tmp_path):
    # Fixture 4: the dominant {tightness, vcp_volume_contraction} shape.
    conn = make_db(tmp_path)
    cand = _cand("watch", [("tightness", "vcp", "fail"),
                           ("vcp_volume_contraction", "vcp", "fail")])
    # Fresh testkit -> H3 active -> H3 claims it.
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == [
        "Sub-A+ VCP-not-formed"]
    # Close H3 (mirror the live DB) -> falls to the baseline.
    conn.execute(
        "UPDATE hypothesis_registry SET status='closed-target-met' "
        "WHERE name='Sub-A+ VCP-not-formed'")
    conn.commit()
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == [
        "Broad-watch baseline"]
```

In `tests/research/shadow_expectancy/test_run.py`, ADD the priced-end-to-end golden fixture (mirrors `_seed_one_aplus_winner` but bucket=`watch` with a real `{adr}` miss — single, no H2/H3/H4 fit even with H3 active → baseline):

```python
def _seed_baseline_watch_priced(conn, ticker="WBL"):
    # Fixture 1: a real broad-watch signal ({adr} miss; 15/400 live) that triggers
    # then stops out -> baseline priced, closed terminal (a priced LOSER, not a
    # winner -- the name reflects "reaches a priced row", not the sign of R).
    # {adr} has no VCP trigger
    # and is not proximity/risk-only, so it routes to the baseline even with H3 active.
    eval_id = insert_candidate(conn, ticker=ticker, bucket="watch", pivot=10.0,
                               initial_stop=9.0, close=10.0,
                               criteria=[("adr", "vcp", "fail")])
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker=ticker, pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-02", o=8.5, h=8.6, l=8.0, c=8.2,
                       status="triggered_open")  # stops out -> closed
    conn.commit()


def test_broad_watch_baseline_prices_end_to_end(tmp_path):
    # Fixture 1 (spec §9.1.1): the baseline cohort reaches a priced scorecard row.
    conn = make_db(tmp_path)
    _seed_baseline_watch_priced(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline")
    m = json.loads(Path(manifest).read_text(encoding="utf-8"))
    card = m["per_hypothesis"] if "per_hypothesis" in m else m["funnel"]["per_hypothesis"]
    assert card["Broad-watch baseline"]["closed"] == 1
    sc = m["scorecard"]["Broad-watch baseline"]
    assert sc["scenarios"]["closed_only"]["n"] >= 1   # a priced row exists
```

- [ ] **Step 2: Run the new/changed tests to verify they fail**

Run: `python -m pytest tests/research/shadow_expectancy/test_attribution.py tests/research/shadow_expectancy/test_run.py -k "baseline or falls or flip or cannibalize or non_watch" -q`
Expected: FAIL — `test_unmatched_watch_falls_to_baseline` returns `[]` (attribution still default-False) and `test_broad_watch_baseline_prices_end_to_end` finds no `"Broad-watch baseline"` per-hypothesis card (engine still attributes via default-False). Pre-fix: the engine never opts in.

- [ ] **Step 3: Pass the opt-in through the attribution wrapper**

`research/harness/shadow_expectancy/attribution.py` — change the matcher call:

```python
    matches = match_candidate_to_hypotheses(
        candidate, registry=list(registry), include_baseline=True,
    )
```

(No other engine change. `run.py`, `constants.py`, the simulator/bracket/scorecard, and the L2 forbidden-import set are UNCHANGED — `attribution.py` already imports the production matcher.)

- [ ] **Step 4: Run the changed tests to verify they pass**

Run: `python -m pytest tests/research/shadow_expectancy -q`
Expected: PASS (incl. the unchanged H1/H2/H3/H4-shaped tests and the reconciliation-invariant corpus, which the narrow rules leave intact).

- [ ] **Step 5: Commit**

```bash
git add research/harness/shadow_expectancy/attribution.py \
  tests/research/shadow_expectancy/test_attribution.py \
  tests/research/shadow_expectancy/test_run.py
git commit -m "feat(research): opt the shadow engine into broad-watch-baseline attribution"
```

---

## Task 4: Verification tail

**Files:** none (verification only).

- [ ] **Step 1: Full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: PASS (baseline ~7408+ tests + the new tests; ZERO failures). Per memory `feedback_no_false_green_claim`, READ the actual summary line — do not infer green.

- [ ] **Step 2: ruff**

Run: `ruff check swing/ research/ tests/`
Expected: clean (no new findings).

- [ ] **Step 3: Migrate-twice no-op (already covered by the 0026 test; re-run as the explicit gate)**

Run: `python -m pytest tests/data/test_migration_0026_broad_watch_baseline.py::test_migrate_twice_is_noop -q`
Expected: PASS — exactly one `Broad-watch baseline` registry row and one open history interval after a second migrate.

- [ ] **Step 4: Live-DB-shaped smoke assertion (v26 fixture; default vs opt-in)**

Run: `python -m pytest tests/research/shadow_expectancy/test_attribution.py -k "falls_to_baseline or non_watch or h3_flip" -q` and `python -m pytest tests/recommendations/test_hypothesis_matcher.py -k "opt_in" -q`
Expected: PASS — a watch candidate with a dominant real non-pass set attributes to the baseline under `include_baseline=True` and to NOTHING under the default (the containment proof, spec §3.2 / §9.1.5).

- [ ] **Step 5: Confirm the locks held (grep)**

Run: `git diff --name-only main` and confirm the touched-file set is exactly: `swing/data/migrations/0026_broad_watch_baseline.sql`, `swing/data/db.py`, `swing/recommendations/hypothesis.py`, `research/harness/shadow_expectancy/attribution.py`, the tests enumerated above, and this plan doc. `swing/metrics/tier.py`, `swing/data/models.py`, `swing/data/repos/hypothesis.py`, and the live recommendation/cohort/card/journal CODE must NOT appear.

---

## Self-Review (run against the spec)

**Spec coverage:**
- §2 frozen migration SQL → Task 2 Step 3 (verbatim). ✓
- §3.1 two-phase fallback (gate on `not matches`, NOT list position; requires active+present row) → Task 1 Step 4 + `test_baseline_absent_from_registry_yields_no_match_even_opted_in`. ✓
- §3.2 opt-in containment (kw-only `include_baseline=False`; NO `measurement_only` column) → Task 1 Step 4 + `test_baseline_fires_only_with_opt_in_for_pure_watch`. ✓
- §4 attribution opt-in (only caller) → Task 3 Step 3. ✓
- §5 consumer split: progress/process ACCEPT (Task 2 Step 8 cohort/card/route bumps); tier/deviation AUTO-EXCLUDE (Step 8 STAY-4 list; tier.py untouched). ✓
- §6 name-safety both directions → `test_broad_watch_name_no_prefix_collision_both_directions`. ✓
- §7 migration mechanics: EXPECTED bump, strict gate, true-v25 expected-tables constant, gate registration, migrate-twice → Task 2 Steps 4–5 + the 0026 test. ✓
- §7.1 #11 sweep, version-aware AND active-vs-all-aware → Task 2 Steps 7–8 (incl. the `EXPECTED_SCHEMA_VERSION` head-pin family the spec table omitted — see ambiguities). ✓
- §7.2 testkit bump + `test_no_match` flip + preserved non-watch empty + direct matcher containment → Task 2 Step 9 + Task 3 Step 1 + Task 1 Step 1. ✓
- §9.1 golden fixtures 1–6: 1 (priced) Task 3; 2/3 matcher Task 1 + attribution Task 3; 4 (H3 flip) Task 1 + Task 3; 5 (containment) Task 1; 6 (migrate-twice + name-safety) Task 2 + Task 1. ✓
- §9.2 real-emitter fixture shapes → all fixtures use the verified live vocabulary (`adr`, `proximity_20ma`, `risk_feasibility`, `tightness`, `vcp_volume_contraction`, `orderliness`) and real sets ({adr}=15, {proximity_20ma}=1, {tightness,vcp_volume_contraction}=60). ✓

**Placeholder scan:** every code/test step shows complete content; no TBD/TODO. ✓

**Type consistency:** `H_BROAD_WATCH_BASELINE`, `_broad_watch_baseline_match`, `include_baseline`, `_broad_watch_baseline_backup_gate`, `BROAD_WATCH_PRE_MIGRATION_EXPECTED_TABLES`, `_create_pre_broad_watch_migration_backup` used consistently across tasks. ✓

## Spec ambiguities resolved (spec-faithful readings)

1. **The §7.1 table omitted the `EXPECTED_SCHEMA_VERSION == 25` head-pin family.** The spec table enumerated only hypothesis-row-count assertions. But bumping `EXPECTED_SCHEMA_VERSION` 25→26 fails ~25 head-tracking version pins across the migration-test suite (every `assert EXPECTED_SCHEMA_VERSION == 25` and every `ensure_schema`-built `version == 25`). These MUST be swept for any migration to land green; this is the routine version-pin discipline the spec assumed. Resolution: Task 2 Step 7 enumerates them with the head-tracking-vs-migration-pinned classification rule. (Codex must confirm the enumeration is exhaustive against the Step-6 red run.)
2. **`tests/data/test_db_v8.py` migrates to HEAD, not v8.** The spec §7.1 conditioned its STAY-4 verdict on "the test migrates to exactly v8 (its name implies so)". It does NOT — it uses `ensure_schema` (→ `EXPECTED_SCHEMA_VERSION`). The spec's own escape clause ("Do NOT bump unless it actually migrates to head") therefore resolves to BUMP. Resolution: `:48`/`:106` → 5, names list + 5th, `:112` → 26 (Task 2 Steps 7–8).
3. **`test_repos_hypothesis.py:54` active-count is 5, not 4.** Spec §7.1 flagged "NOT 4 — H3 is active in fixtures, UNLESS the test closes H3." The test does not close H3 → `len(active) == 5`. Resolution applied.
4. **`test_migration_0025_phase16.py:107` ceiling-clamp premise inverts.** Pre-0026 the clamp stopped a v24→target-26 walk at 25 (EXPECTED=25); post-0026 the same walk reaches 26 (EXPECTED=26, 0026 applies; the broad-watch gate is inert because gates evaluate against the original `current=24`). Resolution: `:107` → 26 + comment update (Task 2 Step 7), with both-ways arithmetic shown.
5. **Fixture 1 must avoid H3 too.** Spec §9.1.1 said "non-pass set NOT matching H2/H4", but the v26 testkit seeds H3 active, so a `tightness`-bearing set would match H3. Resolution: fixture 1 uses the real `{adr}` miss (15/400, no VCP trigger) → baseline regardless of H3.

## Codex review note (for the executing/review phase)

Per the dispatch brief §3 + memory `feedback_adversarial_review_verify_data_shapes`, the adversarial Codex review must (a) verify every edit against the SHIPPED signatures cited here (the matcher's keyword-only block, the `db.py` gate-registration pattern at ~L1211, the testkit pin at `:13`, the §7.1 test files' actual current assertions), and (b) re-verify the load-bearing live-DB data claims (the "Verified live-DB data shapes" block above) against the supplied query output — challenging any the fixtures would otherwise force true.
