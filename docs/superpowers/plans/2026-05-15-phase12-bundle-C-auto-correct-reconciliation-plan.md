# Phase 12 Sub-bundle C — Auto-Correct Journal-from-Schwab Reconciliation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with adversarial Codex review) to implement each sub-sub-bundle task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Sub-sub-bundle dispatch order is **C.A → C.B → C.C → C.D** strictly sequential per cross-bundle dependencies.

**Goal:** Pivot the reconciliation surface from "emit discrepancies for operator-triage" to a three-tier auto-correct / surface-ambiguity / operator-override model where Schwab data is treated as truth when available, while preserving full forensic audit trail + back-compat with the existing 30 resolved discrepancies.

**Architecture:** New `reconciliation_corrections` audit table at v18 → v19 atomic migration; pure-function classifier (per-discrepancy-type sub-classifiers) at `swing/trades/reconciliation_classifier.py`; validator-shim module at `swing/trades/reconciliation_validators.py` mirroring schema CHECK + FK + `_recompute_aggregates` invariants; auto-correction service at `swing/trades/reconciliation_auto_correct.py` with outer/inner transactional split (per Phase 8 lesson) consumed from inside `run_schwab_reconciliation` + `run_tos_reconciliation` pivots; Tier-2 CLI surface extends `swing journal discrepancy` group; backfill CLI surfaces under `swing journal reconcile-backfill`; Phase 10 base-layout banner predicate widens to include `pending_ambiguity_resolution`.

**Tech Stack:** SQLite + Click + the existing Phase 7/9/10/11/12 surfaces (no new third-party deps).

---

## §0 Plan frontmatter

### §0.1 Spec + brief anchors

- **Spec:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (1444 lines; `NO_NEW_CRITICAL_MAJOR` at `d682c25`).
- **Brief:** `docs/phase12-bundle-C-writing-plans-dispatch-brief.md`.
- **Baseline:** main HEAD `effb995` (post-lesson-banking); ~3862 fast tests green; production schema_version 18; ruff baseline 18 E501.
- **Production discrepancy state:** 3 unresolved-material (39 DHC + 40 VSAT + 41 CVGI from pipeline #63 reconciliation_run #10); 30 historical resolved (mostly `acknowledged_immaterial`). Sub-bundle C ships the auto-correct semantics; backfill consumes the 3 production cases at C.D operator-witnessed gate.

### §0.2 Plan posture

- **Sub-sub-bundle decomposition (binding per spec §12):** C.A Foundation → C.B Classifier + validator shim → C.C Auto-correction service + reconciliation flow pivot → C.D Tier-2 CLI surface + backfill + Phase 10 banner widening.
- **Dispatch order locked:** strictly sequential. Each sub-sub-bundle reaches `NO_NEW_CRITICAL_MAJOR` via 2-5 Codex rounds (per Phase 9/10/11/12-A/12-B convergent precedent) before the next sub-sub-bundle dispatches.
- **Schema migration:** ONE atomic single-file migration `0019_phase12_bundle_c_auto_correct_reconciliation.sql` lands at C.A T-A.1. Schema v17 → v18 was Phase 11; v18 → v19 is Sub-bundle C; consumer-side only through C.B/C/D.
- **Worktree posture:** each sub-sub-bundle dispatch creates its own worktree per the cycle-checklist precedent. Plan-writing is on `main` directly (this dispatch).

### §0.3 Spec §15.1 13-item BINDING inheritance map

Each spec §15.1 BINDING item is enumerated below with the plan-task that implements it. Plan §§B/C/D/E task IDs are forward-references.

| # | Spec §15.1 BINDING item | Plan section / task implementing it |
|---|---|---|
| 1 | §1.3 four operator-locked architectural constraints (Schwab-truth / three-tier / determinism-axis / acknowledged_immaterial back-compat) | All sub-sub-bundles; §B–§E enumerate per-task tests asserting each constraint |
| 2 | §3 schema sketches (column lists, CHECK enums, FK relationships, indexes) | §B C.A tasks T-A.1 (migration) + T-A.2 (dataclasses) + T-A.3 (repo CRUD) |
| 3 | §3.8 + §11 migration shape (atomic single-file 0019; backup gate) | §B T-A.1 + T-A.4 |
| 4 | §4 classifier architecture (pure function; per-discrepancy-type sub-classifiers; determinism; validator-respecting downgrade) | §C C.B T-B.1 (`classify_discrepancy`) + T-B.3..T-B.12 (per-discrepancy-type sub-classifiers) |
| 5 | §5 auto-correction service architecture (public/private outer/inner split; transactional discipline; idempotency) | §D C.C T-C.1 (service module skeleton) + T-C.2 (`apply_tier1_correction`) + T-C.3 (`apply_tier2_resolution`) + T-C.4 (`apply_tier3_override`) |
| 6 | §6 Tier-2 CLI surface (CLI-only V1; per-(ambiguity_kind, choice_code) handlers; choice codes) | §E C.D T-D.1 (`list-pending-ambiguities`) + T-D.2 (`show-ambiguity`) + T-D.3 (`resolve-ambiguity`) + T-D.4 (`override-correction`) + T-D.5 (per-pair handler registry) |
| 7 | §7 reconciliation flow pivot (Schwab + TOS-CSV; graceful-degradation contract) | §D T-C.5 (Schwab pivot) + T-C.6 (TOS pivot) + T-C.7 (savepoint-per-discrepancy discipline) |
| 8 | §8 backfill path (dry-run default; explicit `--apply`; idempotency; Pass 1/Pass 2 contract) | §E T-D.6 (backfill CLI scaffold) + T-D.7 (Pass 1) + T-D.8 (Pass 2) + T-D.9 (idempotency + `--retry-pass-2-failures`) |
| 9 | §9.1 review_log freezing — RETAIN + mark superseded | §B T-A.1.4 (column add) + §D T-C.2.4 (lookup + UPDATE in service) |
| 10 | §9.4 daily_management snapshots — RETAIN as historical | NO new task; preserved by design (no DB writes to daily_management in C.B/C/D) |
| 11 | §10 three discriminating-example walkthroughs (CVGI 41 + DHC 39 + VSAT 40) | §G C.D gate plan S3-S7 + §H T-D.11 acceptance fixtures |
| 12 | §12 sub-sub-bundle decomposition (4 sub-bundles; dispatch order; cross-bundle deps) | §0.2 + §F cross-sub-bundle pin matrix |
| 13 | §13 fill auto-population at entry — OUT OF SCOPE | §I V2 candidates §I.1 (mapper widening) carries-forward; no in-scope tasks |

### §0.4 Spec §15.2 15-OQ disposition triage

Per brief §0.3 operator-resolved + spec §14:

| OQ | Spec recommendation | Operator-resolved (brief §0.3) | Plan posture |
|---|---|---|---|
| §14.OQ-1 | NEW dedicated `reconciliation_corrections` table | LOCKED-in-spec | Accept; T-A.1 implements |
| §14.OQ-2 | Pivot BOTH Schwab + TOS-CSV | ACCEPT default | T-C.5 (Schwab) + T-C.6 (TOS) pivot both |
| §14.OQ-3 | Tier-2 CLI-only V1 | LOCKED-in-spec | Accept; web banked at §I.3 |
| §14.OQ-4 | `keep_journal_as_is` default highlighted in `show-ambiguity` | ACCEPT spec-revised default | T-D.2 highlights `keep_journal_as_is` first |
| §14.OQ-5 | Explicit operator invocation only (no auto-fire) | ACCEPT spec default | T-D.6 ships `--apply` opt-in; no auto-fire post-merge |
| §14.OQ-6 | `correction_set_id` inline two-step INSERT-then-UPDATE | Plan decides | Lock at T-A.3 + T-C.3.4: two-step INSERT anchor → UPDATE `correction_set_id = correction_id`; alternative `correction_sets` table rejected (one-row-per-correction-set is overkill V1) |
| §14.OQ-7 | Phase 10 banner predicate widens to include `pending_ambiguity_resolution` | ACCEPT in C.D scope | T-D.10 widens the 3 helper functions at `swing/metrics/discrepancies.py:count_unresolved_material` + `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` + `:list_unresolved_material_for_closed_trades`. **Plan-time correction to spec OQ-7 wording:** spec says "retrofit 10 base-layout VM consumers" but the actual widening is at the helper level — all 14 VM instances (across 9 files; verified §A.5) consume the helper return value and auto-pick up the widening with ZERO VM-row code changes. T-D.10 still touches each of the 14 VMs with a discriminating regression test (one per VM file confirming the count includes pending-ambiguity discrepancies) but does NOT modify the dataclass fields. Banked at §I.10 as a V2.1 §VII.F spec-amendment candidate (count-wording cleanup). |
| §14.OQ-8 | Confirmation prompt + `--force` flag | ACCEPT spec default | T-D.4 implements; mirrors `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` |
| §14.OQ-9 | `__delete__`/`__insert__` sentinels in `field_name` | Plan decides | Lock at T-A.3 + T-C.3.5: sentinels in `field_name` per spec §3.1.1; SQL filter pattern `field_name NOT LIKE '\_\_%' ESCAPE '\'` documented at T-D.7 backfill projection rendering. V2 candidate banked at §I.6 (separate `reconciliation_correction_operations` join table). |
| §14.OQ-10 | Schwab API response body caching | V2 banked | §I.7 |
| §14.OQ-11 | Brief enum mismatches — spec uses shipped | LOCKED-in-spec | §A.7 carries forward; this plan re-verified all 3 shipped CHECK enums |
| §14.OQ-12 | Cross-column CHECK schema-defended | Plan decides | Lock at T-A.1: cross-column CHECK between `(ambiguity_kind, resolution)` per spec §3.2 mechanic. SQLite supports cross-column CHECK on rebuild via `CHECK (...)` inside `CREATE TABLE ... CHECK(...)` clause (verified in Phase 9 Sub-bundle A precedent at `0017_phase9_risk_policy_and_reconciliation.sql`). T-A.1 verifies executable under runner. |
| §14.OQ-13 | Sandbox short-circuit no-op | LOCKED-in-spec | Accept; T-C.2 + T-C.5 enforce |
| §14.OQ-14 | Validator chain composed from NEW shim module | LOCKED-in-spec | Accept; T-B.2 implements shim |
| §14.OQ-15 | Tier-3 override on already-superseded chain: REJECT | Plan decides | Lock at T-C.4: `apply_tier3_override` SELECTs the target correction row; if `superseded_by_correction_id IS NOT NULL`, raises `AlreadySupersededError`; CLI surface (T-D.4) maps to clear error message naming the current chain head. |

### §0.5 V2 candidates banked (forward-reference to §I)

Per brief §0.6 + spec §14 V2 banks + plan-author additions during drafting:

1. (§I.1) V2 mapper widening + auto-VWAP — **operator-locked next-architectural-dispatch**.
2. (§I.2) `fills.reconciliation_status` enum widening.
3. (§I.3) Web Tier-2 surface (`/discrepancies/{id}/resolve`).
4. (§I.4) `schwab_api_calls.surface='auto_correct'` enum widening.
5. (§I.5) Schwab API response body caching.
6. (§I.6) Refactor reconciliation_validators shim into repo modules.
7. (§I.7) Sandbox-friendly preview mode.
8. (§I.8) `daily_management_records.superseded_by_correction_id` column.
9. (§I.9) Phase 6 re-review UI surface (post-correction).
10. (§I.10) Spec OQ-7 wording cleanup ("10 base-layout VMs" actual count is 14 instances across 9 files; widening is helper-level).
11. (§I.11) Per-row correction-policy stamp legacy backfill.
12. (§I.12) `--dry-run --no-pass-2` Schwab-quota-free preview.

### §0.6 OUT-OF-SCOPE (do not implement; surface as plan deviation if encountered)

- **V2 mapper widening** (spec §0.6 LOCK; operator-confirmed next-architectural-dispatch after C.D ship).
- **Fill auto-population at trade-entry time** (spec §1.7 + §13 explicit OUT-OF-SCOPE).
- **Web Tier-2 surface** (spec OQ-3 V1 CLI-only lock).
- **Magnitude-based auto-vs-surface threshold gates** (§1.3 lock #3).
- **Retroactive rewriting of historical `acknowledged_immaterial` resolutions** (§1.3 lock #4).
- **Phase 7 state-machine extension beyond `trade_events.event_type` enum widening** (§1.6 + §9.2).
- **`reconciliation_runs.state` extension** (§9.5 LOCK).
- **`fills.reconciliation_status` enum widening** (§9.2 V1 LOCK; banked §I.2).

---

## §A Pre-verifications (per spec §15.3 + brief §0.5 + brainstorm-lesson #5)

Each item below records the verbatim grep result + the plan binding the verification underwrites. Items 1–8 mirror spec §15.3; items 9–12 mirror brief §0.5 CHECK enum re-verification; item 13 verifies the spec OQ-7 retrofit-count claim against actual shipped VM count.

### §A.1 Migration runner `executescript()` partial-failure wrapper

**Verbatim shipped state** at `swing/data/db.py:96-139`:

```
def _apply_migration(conn: sqlite3.Connection, sql_path: Path) -> None:
    ...
    sql = sql_path.read_text(encoding="utf-8")
    prior_fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.executescript(sql)
        conn.commit()
    except Exception:
        ...
        # rollback + re-raise
    finally:
        conn.execute(
            "PRAGMA foreign_keys=ON" if prior_fk else "PRAGMA foreign_keys=OFF"
        )
```

Plus `EXPECTED_SCHEMA_VERSION = 18` at line 24.

**Plan binding underwritten:**
- Migration 0019 SQL MUST open with `BEGIN;` and close with `COMMIT;` so `_apply_migration`'s `conn.rollback()` can undo partial DDL on failure (per migration 0018 precedent at `0018_schwab_integration.sql:10,77` + the executescript implicit-COMMIT gotcha).
- The `foreign_keys=OFF` wrap is automatic at the runner level; table-rebuild statements in 0019 (the `reconciliation_discrepancies` rebuild + the `trade_events` rebuild) inherit the discipline.
- T-A.1 updates `EXPECTED_SCHEMA_VERSION` constant from 18 → 19 in the same patch as the migration file.

### §A.2 `run_tos_reconciliation` + `run_schwab_reconciliation` exact locations

**Verbatim shipped state:**

- `swing/trades/reconciliation.py:116`: `def run_tos_reconciliation(conn, *, csv_path, period_end=None, period_start=None, notes=None, price_tolerance=0.01) -> ReconciliationRun:`
- `swing/trades/schwab_reconciliation.py:203`: `def run_schwab_reconciliation(conn, *, account_hash, period_start, period_end, schwab_orders, schwab_transactions, schwab_account, pipeline_run_id=None, schwab_api_call_id=None, ...) -> ReconciliationRun:`

The two functions live in SEPARATE module files (spec §15.3 #2 + Codex R1 Major #6 spec verification). Plan §D pivot tasks bind the correct module per function.

**Plan binding underwritten:**
- T-C.5 patches `swing/trades/schwab_reconciliation.py:run_schwab_reconciliation` to call into the auto-correction `_apply_tier1_correction_inner` after the existing emit loop (Step 2 per spec §7.1).
- T-C.6 mirrors the same pivot in `swing/trades/reconciliation.py:run_tos_reconciliation` per OQ-2 disposition.
- Both pivots use savepoint-per-discrepancy discipline (T-C.7) so an exception inside any single discrepancy's classify+apply doesn't poison the outer run's transaction.

### §A.3 `_construct_pipeline_schwab_client(cfg)` location + signature

**Verbatim shipped state** at `swing/pipeline/runner.py:169-207`:

```
def _construct_pipeline_schwab_client(cfg) -> object | None:
    """Construct a `schwabdev.Client` for pipeline-internal use from env vars.
    ...
    ``_construct_pipeline_schwab_client`` directly when they want to
    inject a MagicMock without going through env vars.
    """
```

Invoked at `swing/pipeline/runner.py:640` during pipeline lease acquisition; output threaded into market-data cache install + `_step_schwab_snapshot` + `_step_schwab_orders` callsites (Phase 12 Sub-bundle A T-A.3 closed the cascade gap).

**Plan binding underwritten:**
- T-C.5 + T-C.6 + T-D.8 (Pass 2 re-fetch in backfill) consume `_construct_pipeline_schwab_client(cfg)` for the inline reconciliation flow + the CLI backfill flow. NEVER construct a new `schwabdev.Client(...)` directly — single-Client-instance discipline (Phase 11 forward-binding lesson #6 + Phase 12 Sub-bundle B forward-binding lesson #6: `apply_overrides(cfg)` at all Schwab entry points).
- Discriminating regression test (T-C.5.6): test mocks `_construct_pipeline_schwab_client` + asserts cascade-resolved env-var / cfg-tier credentials are threaded through both the pipeline's existing `_step_schwab_orders` AND the new auto-correct service callsite. Phase 12 Sub-bundle A T-A.3 implementer-gap pre-emption pattern.

### §A.4 Existing `swing journal discrepancy` CLI command group

**Verbatim shipped state** at `swing/cli.py:1767-1925`:

```
@journal_group.group("discrepancy")
def discrepancy_group() -> None:
    """Phase 9 reconciliation discrepancy review + resolution."""


@discrepancy_group.command("list")
@click.option("--unresolved", is_flag=True, ...)
@click.option("--material", is_flag=True, ...)
@click.option("--trade-id", type=int, default=None, ...)
@click.option("--limit", type=int, default=50, ...)
@click.pass_context
def discrepancy_list_cmd(ctx, unresolved, material, trade_id, limit):
    ...


@discrepancy_group.command("show")
@click.argument("discrepancy_id", type=int)
@click.pass_context
def discrepancy_show_cmd(ctx, discrepancy_id):
    ...


@discrepancy_group.command("resolve")
@click.argument("discrepancy_id", type=int)
@click.option("--resolution", type=click.Choice([
    "journal_corrected", "source_treated_canonical",
    "manual_override", "acknowledged_immaterial",
    ...
```

**Plan binding underwritten:**
- T-D.1 (`list-pending-ambiguities`) + T-D.2 (`show-ambiguity`) + T-D.3 (`resolve-ambiguity`) + T-D.4 (`override-correction`) extend the existing `discrepancy_group` with new `@discrepancy_group.command(...)` decorators directly at `swing/cli.py`. NO new top-level CLI group.
- T-D.3's `--resolution` option does NOT widen the existing `resolve` subcommand — it's a NEW `resolve-ambiguity` subcommand with a `--choice` option keyed on the per-`ambiguity_kind` menu (spec §6.2.1). The existing `resolve` subcommand stays as-is for back-compat with operator's existing muscle memory + the 30 historical `acknowledged_immaterial` resolutions.

### §A.5 Phase 10 `discrepancies.py` helper + base-layout VM mixin signature

**Verbatim shipped state at `swing/metrics/discrepancies.py:37-72`:**

```
def count_unresolved_material(conn: sqlite3.Connection) -> int:
    """Return the sum of unresolved-material discrepancies attributed to
    active + closed trades.
    ...
    """
    active = list_unresolved_material_for_active_trades(conn)
    closed = list_unresolved_material_for_closed_trades(conn)
    return len(active) + len(closed)


def list_unresolved_material_for_trade(
    conn: sqlite3.Connection, trade_id: int,
) -> list[ReconciliationDiscrepancy]:
    ...
    rows = conn.execute(
        f"SELECT {_DISCREPANCY_SELECT_COLUMNS} "
        "FROM reconciliation_discrepancies "
        "WHERE trade_id = ? "
        "  AND material_to_review = 1 "
        "  AND resolution = 'unresolved' "
        ...
    ).fetchall()
```

Plus repo-layer queries at `swing/data/repos/reconciliation.py:444-485` both filter `WHERE d.material_to_review = 1 AND d.resolution = 'unresolved'` (verbatim two-occurrence match in `_DISCREPANCY_SELECT_COLUMNS_D_ALIAS` family).

**Verified VM instance count consuming `unresolved_material_discrepancies_count: int = 0`:** **14 instances across 9 files** — `dashboard.py:353`, `pipeline.py:25`, `journal.py:111`, `watchlist.py:44`, `error.py:24`, `config.py:50`, `trades.py:662/755/769/911` (4 VMs), `schwab.py:76/121` (2 VMs), `metrics/shared.py:47`. Plus `metrics/process_grade_trend.py` consumes via `metrics/shared.py` import. Spec OQ-7 wording "10 base-layout VMs" understates the actual surface; T-D.10 records this divergence as a banked §I.10 V2.1 §VII.F amendment candidate.

**Plan binding underwritten:**
- T-D.10 widens the predicate at 3 callsites: `swing/metrics/discrepancies.py:count_unresolved_material` (transitively via the 2 repo helpers it calls) PLUS `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades:462` AND `:list_unresolved_material_for_closed_trades:485`. Each `WHERE d.resolution = 'unresolved'` becomes `WHERE d.resolution IN ('unresolved', 'pending_ambiguity_resolution')`.
- The 14 VM instances DO NOT need dataclass field changes — they pre-existing `unresolved_material_discrepancies_count: int = 0` consumes the widened helper return value automatically.
- T-D.10 still adds a discriminating regression test PER VM instance (14 tests) asserting that planting a discrepancy with `resolution='pending_ambiguity_resolution' AND material_to_review=1` increments the VM's `unresolved_material_discrepancies_count` from N to N+1 + that the banner text renders accordingly. Defense-in-depth (matches Phase 10 Sub-bundle E T-E.3 retrofit precedent).
- T-D.10 also widens the per-trade helper `list_unresolved_material_for_trade` to include `pending_ambiguity_resolution` (mirrors the global helpers) so the Phase 10 Sub-bundle E T-E.6 per-trade indicator on `/trades/{id}` surfaces tier-2-pending discrepancies the same way.

### §A.6 Validator absence in `swing/data/repos/{fills,trades,cash_movements,account_equity_snapshots}.py`

**Verbatim shipped state** (grep over `swing/data/repos/`):

```
swing/data/repos/trades.py:69: def _validate_chart_pattern_invariant(trade: Trade) -> None:
```

ONE match — at `swing/data/repos/trades.py:69`. The function is a Trade-dataclass invariant check (chart_pattern enum-vs-baseline-evaluation_id rule per Phase 9 Sub-bundle D); NOT a dry-run callable validator the auto-correction service can consult against a proposed UPDATE.

No `def validate_fill...`, `def validate_trade...`, `def validate_cash_movement...`, `def validate_snapshot...` anywhere in the repos directory. Schema invariants live in SQLite CHECK + FK constraints + indirect `_recompute_aggregates` (`swing/data/repos/fills.py:79`).

**Plan binding underwritten:**
- T-B.2 ships NEW shim module `swing/trades/reconciliation_validators.py` with 4 callable predicates (`validate_fill_correction` / `validate_trade_correction` / `validate_cash_movement_correction` / `validate_snapshot_correction`) per spec §5.5 LOCK + OQ-14 LOCK.
- Each shim function reads the current row, applies the proposed updates to a Python dict copy, checks the result against schema-CHECK-mirror predicates + FK existence + (for `fills`) the simulated `_recompute_aggregates` aggregate formula; returns `True`/`False` + a rejection reason. NEVER mutates the DB.
- Composition at T-B.13 ships `default_validator_chain(conn)` which dispatches on `affected_table` to the right shim function.
- V2 candidate (§I.6): refactor shims into repo modules themselves so validators become first-class on `swing/data/repos/*.py`.

### §A.7 Shipped CHECK enums on `reconciliation_discrepancies` + `fills` + `trade_events` + `schwab_api_calls`

**§A.7.1 `reconciliation_discrepancies.resolution` (verified at `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql:253-257`):**

```
resolution TEXT NOT NULL
    CHECK (resolution IN (
        'journal_corrected', 'source_treated_canonical',
        'manual_override', 'unresolved', 'acknowledged_immaterial'
    )) DEFAULT 'unresolved',
```

**5 values, verbatim matching spec §3.2.** Plan T-A.1 widens to 9 via table-rebuild (CHECK widening requires SQLite table-rebuild per spec §3.8 #3 + migration 0014 §11 precedent).

**§A.7.2 `fills.reconciliation_status` (verified at `swing/data/migrations/0014_phase7_state_machine_and_fills.sql:20-22`):**

```
reconciliation_status TEXT NOT NULL DEFAULT 'unreconciled'
    CHECK (reconciliation_status IN ('unreconciled','reconciled_match',
      'reconciled_discrepancy','reconciled_discrepancy_resolved','manual_override')),
```

**5 values, verbatim matching spec §9.2.** Plan does NOT widen V1 (spec §9.2 LOCK). Auto-correction service flips affected fills from `'unreconciled'` to `'reconciled_discrepancy_resolved'` via the existing enum.

**§A.7.3 `trade_events.event_type` (verified at `swing/data/migrations/0014_phase7_state_machine_and_fills.sql:238-239`):**

```
event_type TEXT NOT NULL CHECK (event_type IN
    ('entry','stop_adjust','note','exit','flag','pre_trade_edit')),
```

**6 values.** Plan T-A.1 widens to 7 by table-rebuild adding `'reconciliation_auto_correct'` per spec §3.5. Migration 0014 §11 precedent already did the same rebuild dance once — same pattern repeats.

**§A.7.4 `schwab_api_calls` schema (verified at `swing/data/migrations/0018_schwab_integration.sql:12-54`):**

```
CREATE TABLE schwab_api_calls (
    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ...
    linked_snapshot_id INTEGER,
    linked_reconciliation_run_id INTEGER,
    ...
    surface TEXT NOT NULL,
    environment TEXT NOT NULL,
    CHECK (status IN ('in_flight', 'success', 'error', 'auth_failed', 'rate_limited', 'concurrent_refresh')),
    CHECK (surface IN ('pipeline', 'cli')),
    CHECK (environment IN ('sandbox', 'production')),
    CHECK (endpoint IN ('oauth.code_exchange', 'oauth.refresh', 'oauth.revoke',
        'accounts.linked', 'accounts.details',
        'accounts.orders.list', 'accounts.transactions.list',
        'marketdata.quotes', 'marketdata.pricehistory')),
    FOREIGN KEY (linked_snapshot_id) REFERENCES account_equity_snapshots(snapshot_id) ON DELETE SET NULL,
    FOREIGN KEY (linked_reconciliation_run_id) REFERENCES reconciliation_runs(run_id) ON DELETE SET NULL,
    ...
);
```

**Plan binding underwritten:**
- T-A.1 adds 1 new column `linked_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` via `ALTER TABLE schwab_api_calls ADD COLUMN ...`. NULLABLE column add; NO table-rebuild needed.
- `surface` CHECK enum stays at 2 values `('pipeline', 'cli')` V1; Sub-bundle C auto-correction inherits `surface='cli'` for backfill-initiated calls (spec §5.8). V2 candidate (§I.4) banks `'auto_correct'` enum widening.

### §A.8 `briefing.md` generator extension point

**Verbatim shipped state** at `swing/rendering/briefing.py:50-70` + `swing/rendering/briefing_md.py:12-22`:

`BriefingInputs` dataclass already carries `schwab_degraded_endpoint: str | None = None` (Phase 11 Sub-bundle D banner ship). The markdown renderer at `briefing_md.py:17` emits the banner when the field is non-None. Mirror pattern for Sub-bundle C's reconciliation-pending banner: add a new optional field `reconciliation_pending_count: int = 0` (or `reconciliation_status_payload: ReconciliationStatusVM | None = None` for the multi-line summary per spec §7.5) to `BriefingInputs` + a new render branch to `briefing_md.py`.

**Plan binding underwritten:**
- T-C.8 extends `BriefingInputs` with `reconciliation_pending_count: int = 0` AND `reconciliation_tier1_recent_count: int = 0` (last 7-day window) per spec §7.5. Defaults preserve back-compat with existing call sites.
- T-C.9 extends `briefing_md.py` with a new "Reconciliation status" section per spec §7.5; emits ONLY when `reconciliation_pending_count > 0` OR `reconciliation_tier1_recent_count > 0` to avoid noise on clean runs.
- T-C.10 wires `_step_export` (pipeline runner) to query the new `reconciliation_corrections` table + populate the BriefingInputs fields.

### §A.9 `_recompute_aggregates` invariant path for CVGI 41 walkthrough

**Verbatim shipped state** at `swing/data/repos/fills.py:79-105`:

```
def _recompute_aggregates(conn: sqlite3.Connection, trade_id: int) -> None:
    """Update trades.current_size + current_avg_cost + last_fill_at from fills.
    Single write path; consistency invariant: current_size = sum(entry qty)
    - sum(trim/exit/stop qty).
    V1: current_avg_cost == entry_price (single entry-fill per trade);
    formula reads the authoritative entry-fill price.
    """
    conn.execute(
        """
        UPDATE trades SET
          current_size = COALESCE((
            SELECT SUM(CASE WHEN action = 'entry' THEN quantity ELSE -quantity END)
            FROM fills WHERE fills.trade_id = ?
          ), 0),
          current_avg_cost = (
            SELECT price FROM fills
            WHERE fills.trade_id = ? AND action = 'entry'
            ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1
          ),
          ...
        """, ...)
```

**Plan binding underwritten:**
- T-C.2 (`apply_tier1_correction`) calls `_recompute_aggregates(conn, trade_id)` after UPDATEing `fills.price` for the CVGI 41 case (spec §5.4 step 6 + §10.1 step 5). Single-entry-fill CVGI trade: post-correction `trades.current_avg_cost = $5.30` (verified by spec §10.1 walkthrough; T-C.2 discriminating test plants a CVGI-shaped fixture + asserts post-state).
- The `fill_datetime ASC, fill_id ASC LIMIT 1` ordering means a multi-entry-fill case (DHC split-into-partials) sets `current_avg_cost` to the FIRST chronological entry fill's price — not a VWAP. V1 LIMITATION: spec §6.2.1 `consolidate_using_operator_vwap` UPDATEs the single fill's price (no split); `split_into_partials` produces N entry fills with `current_avg_cost` reading the earliest one. T-C.3.4 (split handler) ensures the operator-supplied payload's `fill_datetime` values are correctly ordered so the recompute sees the right first-entry price. V2 candidate banked at §I.13 (VWAP-aware `current_avg_cost` recompute for split fills).

### §A.10 Brief §0.5 Lesson #5 schema-enum re-verification summary

Three CHECK enums verified verbatim in §A.7 against shipped migrations. ZERO divergences between spec §3 and shipped state. Plan §B T-A.1 inherits the verbatim shipped enum values as the "EXISTING preserved" portion of the 9-value widened `resolution` enum + the 7-value widened `event_type` enum.

### §A.11 Cross-bundle pin: spec OQ-7 retrofit-count discrepancy

Per §A.5 verified count: 14 VM instances across 9 files (NOT 10 as spec OQ-7 wording asserts). Banked at §I.10 as V2.1 §VII.F spec-amendment candidate. Plan T-D.10 still touches all 14 via discriminating regression tests; widening mechanic is at the 3 shared helper functions (not at the VM dataclass field level).

### §A.12 Schema-version migration runner backup-gate precedent

**Verified shipped state** at `swing/data/db.py` migration-runner (Phase 9 Sub-bundle A backup-gate precedent; Phase 11 Sub-bundle A T-A.7 precedent; Phase 12 Sub-bundle A migration 0019 inherits):

The runner-level backup gate fires when `current_version == N AND target >= N+1` for a specific (N, N+1) transition. Phase 9 used `swing-pre-phase9-migration-<ISO>.db`; Phase 11 used `swing-pre-phase11-migration-<ISO>.db`; Sub-bundle C uses `swing-pre-phase12-bundle-c-migration-<ISO>.db` per spec §11.3.

**Plan binding underwritten:**
- T-A.4 extends the backup-gate registry at `swing/data/db.py` to include the new (`current_version == 18 AND target >= 19`) trigger with backup filename `swing-pre-phase12-bundle-c-migration-<ISO>.db`.
- Operator's existing pre-migration backup discipline (validated through Phase 9 + Phase 11 ships) carries through; backup is `cp swing.db swing-pre-phase12-bundle-c-migration-<ISO>.db` at gate-time, BEFORE the migration applies. The runner refuses to apply 0019 unless either (a) `current_version < 18` (multi-step migration; backup gate at earlier step) OR (b) backup created in the same runner invocation.

---

## §B Sub-sub-bundle C.A — Foundation (schema + dataclass + repo CRUD)

**Scope summary (per spec §12.A):**
- Migration 0019 (single atomic file) lands schema_version 18 → 19 with: NEW `reconciliation_corrections` table (19 columns + 4 indexes); NEW `reconciliation_discrepancies.ambiguity_kind` column + cross-column CHECK; widened `reconciliation_discrepancies.resolution` CHECK enum (5 → 9 values via table-rebuild); NEW `review_log.superseded_by_correction_id` column; widened `trade_events.event_type` CHECK enum (+1 value via table-rebuild); NEW `schwab_api_calls.linked_correction_id` column; new partial index `ix_reconciliation_discrepancies_pending_ambiguity`.
- NEW `swing/data/repos/reconciliation_corrections.py` with pure-CRUD (caller-transaction).
- New dataclass + repo column extensions on `ReconciliationDiscrepancy`, `ReviewLog`, `SchwabApiCall` for the new columns.
- Migration runner backup-gate wiring at `swing/data/db.py`.
- ZERO behavior change. ZERO new service logic. ZERO operator-visible changes.

**Files touched:**
- Create: `swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql`
- Create: `swing/data/repos/reconciliation_corrections.py`
- Create: `tests/data/test_reconciliation_corrections_schema.py`
- Create: `tests/data/test_reconciliation_corrections_repo.py`
- Create: `tests/data/test_migration_0019_*.py` (multiple test files per sub-task)
- Modify: `swing/data/db.py` (EXPECTED_SCHEMA_VERSION 18 → 19; backup-gate registration)
- Modify: `swing/data/models.py` (extend `ReconciliationDiscrepancy` + `ReviewLog`; add `ReconciliationCorrection` dataclass)
- Modify: `swing/integrations/schwab/models.py` (extend `SchwabApiCall` for new `linked_correction_id` field — verify dataclass exists or note shipped state)
- Modify: `swing/data/repos/reconciliation.py` (extend column-select tuples + row-deserializer for `ambiguity_kind`)
- Modify: `swing/data/repos/review_log.py` (extend column-select tuples for `superseded_by_correction_id`)

**Projected fast-test delta:** +40-65 tests (per spec §12.A +35-55 + plan-time additions for cross-column CHECK family + the SchwabApiCall dataclass extension test).

### §B.1 Task T-A.1 — Migration 0019 SQL file

**Files:**
- Create: `swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql`
- Modify: `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION = 19`)
- Test: `tests/data/test_migration_0019_atomic_apply.py`
- Test: `tests/data/test_migration_0019_schema_shape.py`
- Test: `tests/data/test_migration_0019_existing_data_preserved.py`

**Acceptance criteria:**
1. File opens with `BEGIN;` and closes with `COMMIT;` (per CLAUDE.md gotcha; 0018 precedent at lines 10/77).
2. All 7 schema deltas land in spec §3.8 declared order (`reconciliation_corrections` first; rebuilds + ALTERs after; partial index; schema_version UPDATE last; per Phase 9 §A.0 R1 Critical #1 precedent — schema_version UPDATE is the FINAL statement before COMMIT).
3. `reconciliation_corrections` table is created with all 19 columns + correct types + correct NULLABLE + correct CHECK constraints per spec §3.1 table.
4. All 4 indexes on `reconciliation_corrections` are created (`ix_reconciliation_corrections_discrepancy` / `_affected_row` / `_run` / `_action`).
5. `reconciliation_discrepancies` rebuild widens `resolution` CHECK enum 5 → 9 values (verbatim 5 existing values preserved per §A.7.1 + 4 new values added: `'auto_corrected_from_schwab'`, `'pending_ambiguity_resolution'`, `'operator_resolved_ambiguity'`, `'operator_overridden'`).
6. `reconciliation_discrepancies` rebuild adds NEW `ambiguity_kind TEXT NULL CHECK (...)` column with the 7-value CHECK enum (`'multi_partial_vs_consolidated', 'multi_match_within_window', 'unknown_schwab_subtype', 'field_shape_incompatible', 'schwab_returned_no_match', 'validator_rejected', 'unsupported'`) AND a cross-column CHECK enforcing `ambiguity_kind IS NULL OR resolution IN ('pending_ambiguity_resolution','operator_resolved_ambiguity')`.
7. Rebuild preserves existing rows (32 in production: 29 historical resolved + 3 unresolved-material) byte-for-byte. INSERT-SELECT copies all existing column values; new `ambiguity_kind` is NULL for all copied rows.
8. Rebuild preserves all 4 existing indexes on `reconciliation_discrepancies` (`ix_..._run`, `_trade`, `_unresolved`, `_material`); each is DROPped before the table rebuild + recreated on the new table post-rename.
9. `review_log` gets NEW nullable column `superseded_by_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` via `ALTER TABLE ... ADD COLUMN`. No rebuild.
10. `trade_events` rebuild widens `event_type` CHECK enum 6 → 7 values (verbatim 6 existing per §A.7.3 + new `'reconciliation_auto_correct'`); preserves existing rows; recreates `ix_trade_events_trade` index.
11. `schwab_api_calls` gets NEW nullable column `linked_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL` via `ALTER TABLE`. No rebuild.
12. NEW partial index `ix_reconciliation_discrepancies_pending_ambiguity ON reconciliation_discrepancies(ambiguity_kind, created_at) WHERE resolution = 'pending_ambiguity_resolution'`.
13. `UPDATE schema_version SET version = 19` is the LAST statement before `COMMIT;`.
14. `EXPECTED_SCHEMA_VERSION` in `swing/data/db.py` updates from 18 → 19 in the SAME patch.
15. Cross-column CHECK on `(ambiguity_kind, resolution)` is verified executable under the runner via a discriminating test: INSERT with `resolution='unresolved' AND ambiguity_kind='unsupported'` MUST raise an IntegrityError; INSERT with `resolution='pending_ambiguity_resolution' AND ambiguity_kind=NULL` MUST also raise (defense-in-depth bidirectional check per spec §3.2).

- [ ] **Step 1: Write the failing test for atomic apply on a v18-baseline DB.**

```python
# tests/data/test_migration_0019_atomic_apply.py
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import _apply_migration, _current_version, ensure_schema


def test_migration_0019_applies_against_v18_baseline(tmp_path):
    db = tmp_path / "swing.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(conn)  # idempotent; lands at current EXPECTED_SCHEMA_VERSION
    pre = _current_version(conn)
    assert pre == 19  # after EXPECTED_SCHEMA_VERSION bump
    # Tables/columns expected by Sub-bundle C exist:
    schema = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "reconciliation_corrections" in schema
    # ambiguity_kind column on reconciliation_discrepancies:
    cols = [row[1] for row in conn.execute(
        "PRAGMA table_info(reconciliation_discrepancies)"
    )]
    assert "ambiguity_kind" in cols
    # superseded_by_correction_id on review_log:
    cols_rl = [row[1] for row in conn.execute(
        "PRAGMA table_info(review_log)"
    )]
    assert "superseded_by_correction_id" in cols_rl
    # linked_correction_id on schwab_api_calls:
    cols_api = [row[1] for row in conn.execute(
        "PRAGMA table_info(schwab_api_calls)"
    )]
    assert "linked_correction_id" in cols_api
    conn.close()
```

Run: `pytest tests/data/test_migration_0019_atomic_apply.py::test_migration_0019_applies_against_v18_baseline -v`
Expected: FAIL with `AssertionError: pre == 19` (current EXPECTED_SCHEMA_VERSION is 18; migration 0019 not yet shipped).

- [ ] **Step 2: Run test to verify it fails.** Verify failure.

- [ ] **Step 3: Write migration 0019 SQL file + bump EXPECTED_SCHEMA_VERSION.**

Migration file template (abbreviated for plan brevity; full SQL written verbatim during execution):

```sql
-- 0019_phase12_bundle_c_auto_correct_reconciliation.sql
-- Phase 12 Sub-bundle C — auto-correct reconciliation foundation.
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha
-- "executescript() implicit COMMIT". Runner-level conn.rollback()
-- can undo partial DDL only when SQL itself opens an explicit transaction.
-- Bumps schema_version 18 -> 19.

BEGIN;

-- 1. reconciliation_corrections audit table (19 columns + 4 indexes).
CREATE TABLE reconciliation_corrections (
    correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discrepancy_id INTEGER NOT NULL REFERENCES reconciliation_discrepancies(discrepancy_id) ON DELETE CASCADE,
    correction_action TEXT NOT NULL CHECK (correction_action IN
        ('auto_applied', 'operator_resolved_ambiguity', 'operator_overridden')),
    correction_choice TEXT,
    affected_table TEXT NOT NULL CHECK (affected_table IN
        ('fills', 'trades', 'cash_movements', 'account_equity_snapshots')),
    affected_row_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    pre_correction_value_json TEXT NOT NULL,
    source_canonical_value_json TEXT,
    applied_value_json TEXT NOT NULL,
    operator_truth_value_json TEXT,
    applied_at TEXT NOT NULL,
    applied_by TEXT NOT NULL CHECK (applied_by IN ('auto', 'operator')),
    correction_set_id INTEGER,
    superseded_by_correction_id INTEGER REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL,
    risk_policy_id_at_correction INTEGER REFERENCES risk_policy(policy_id) ON DELETE SET NULL,
    schwab_api_call_id INTEGER REFERENCES schwab_api_calls(call_id) ON DELETE SET NULL,
    reconciliation_run_id INTEGER NOT NULL REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE,
    correction_reason TEXT,
    notes TEXT
);

CREATE INDEX ix_reconciliation_corrections_discrepancy
    ON reconciliation_corrections(discrepancy_id, applied_at);
CREATE INDEX ix_reconciliation_corrections_affected_row
    ON reconciliation_corrections(affected_table, affected_row_id, applied_at);
CREATE INDEX ix_reconciliation_corrections_run
    ON reconciliation_corrections(reconciliation_run_id);
CREATE INDEX ix_reconciliation_corrections_action
    ON reconciliation_corrections(correction_action, applied_at);

-- 2. reconciliation_discrepancies rebuild (CHECK enum widening + ambiguity_kind column + cross-column CHECK).
CREATE TABLE reconciliation_discrepancies_new (
    discrepancy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE,
    discrepancy_type TEXT NOT NULL CHECK (discrepancy_type IN (
        'close_price_mismatch', 'stop_mismatch', 'position_qty_mismatch',
        'cash_movement_mismatch', 'sector_tamper', 'snapshot_mismatch',
        'unmatched_open_fill', 'unmatched_close_fill',
        'entry_price_mismatch', 'equity_delta'
    )),
    trade_id INTEGER REFERENCES trades(id) ON DELETE SET NULL,
    fill_id INTEGER REFERENCES fills(fill_id) ON DELETE SET NULL,
    cash_movement_id INTEGER REFERENCES cash_movements(id) ON DELETE SET NULL,
    linked_daily_management_record_id INTEGER REFERENCES daily_management_records(management_record_id) ON DELETE SET NULL,
    ticker TEXT,
    field_name TEXT NOT NULL,
    expected_value_json TEXT,
    actual_value_json TEXT,
    delta_text TEXT,
    material_to_review INTEGER NOT NULL CHECK (material_to_review IN (0, 1)),
    resolution TEXT NOT NULL CHECK (resolution IN (
        'journal_corrected', 'source_treated_canonical',
        'manual_override', 'unresolved', 'acknowledged_immaterial',
        'auto_corrected_from_schwab', 'pending_ambiguity_resolution',
        'operator_resolved_ambiguity', 'operator_overridden'
    )) DEFAULT 'unresolved',
    ambiguity_kind TEXT CHECK (ambiguity_kind IS NULL OR ambiguity_kind IN (
        'multi_partial_vs_consolidated', 'multi_match_within_window',
        'unknown_schwab_subtype', 'field_shape_incompatible',
        'schwab_returned_no_match', 'validator_rejected', 'unsupported'
    )),
    resolution_reason TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    mistake_tag_assigned TEXT,
    created_at TEXT NOT NULL,
    CHECK (
        (ambiguity_kind IS NULL AND resolution NOT IN ('pending_ambiguity_resolution','operator_resolved_ambiguity'))
        OR
        (ambiguity_kind IS NOT NULL AND resolution IN ('pending_ambiguity_resolution','operator_resolved_ambiguity'))
    )
);

INSERT INTO reconciliation_discrepancies_new (
    discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
    cash_movement_id, linked_daily_management_record_id, ticker,
    field_name, expected_value_json, actual_value_json, delta_text,
    material_to_review, resolution, ambiguity_kind, resolution_reason,
    resolved_at, resolved_by, mistake_tag_assigned, created_at
)
SELECT
    discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
    cash_movement_id, linked_daily_management_record_id, ticker,
    field_name, expected_value_json, actual_value_json, delta_text,
    material_to_review, resolution, NULL, resolution_reason,
    resolved_at, resolved_by, mistake_tag_assigned, created_at
FROM reconciliation_discrepancies;

DROP TABLE reconciliation_discrepancies;
ALTER TABLE reconciliation_discrepancies_new RENAME TO reconciliation_discrepancies;

CREATE INDEX ix_reconciliation_discrepancies_run
    ON reconciliation_discrepancies(run_id);
CREATE INDEX ix_reconciliation_discrepancies_trade
    ON reconciliation_discrepancies(trade_id)
    WHERE trade_id IS NOT NULL;
CREATE INDEX ix_reconciliation_discrepancies_unresolved
    ON reconciliation_discrepancies(resolution)
    WHERE resolution = 'unresolved';
CREATE INDEX ix_reconciliation_discrepancies_material
    ON reconciliation_discrepancies(trade_id, material_to_review)
    WHERE material_to_review = 1 AND resolution = 'unresolved';
CREATE INDEX ix_reconciliation_discrepancies_pending_ambiguity
    ON reconciliation_discrepancies(ambiguity_kind, created_at)
    WHERE resolution = 'pending_ambiguity_resolution';

-- 3. review_log column add.
ALTER TABLE review_log
    ADD COLUMN superseded_by_correction_id INTEGER
        REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL;

-- 4. trade_events rebuild (CHECK enum widening to add 'reconciliation_auto_correct').
CREATE TABLE trade_events_new (
    id INTEGER PRIMARY KEY,
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN
        ('entry','stop_adjust','note','exit','flag','pre_trade_edit','reconciliation_auto_correct')),
    payload_json TEXT,
    rationale TEXT,
    notes TEXT
);
INSERT INTO trade_events_new (id, trade_id, ts, event_type, payload_json, rationale, notes)
SELECT id, trade_id, ts, event_type, payload_json, rationale, notes FROM trade_events;
DROP TABLE trade_events;
ALTER TABLE trade_events_new RENAME TO trade_events;
CREATE INDEX ix_trade_events_trade ON trade_events(trade_id, ts);

-- 5. schwab_api_calls column add.
ALTER TABLE schwab_api_calls
    ADD COLUMN linked_correction_id INTEGER
        REFERENCES reconciliation_corrections(correction_id) ON DELETE SET NULL;

-- 6. Schema version bump (LAST statement; Phase 9 §A.0 R1 Critical #1 precedent).
UPDATE schema_version SET version = 19;

COMMIT;
```

Update `swing/data/db.py:24`:
```python
EXPECTED_SCHEMA_VERSION = 19
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/data/test_migration_0019_atomic_apply.py::test_migration_0019_applies_against_v18_baseline -v`
Expected: PASS.

- [ ] **Step 5: Write rebuild-preserves-rows test.**

```python
# tests/data/test_migration_0019_existing_data_preserved.py
def test_rebuild_preserves_existing_discrepancy_rows(tmp_path):
    db = tmp_path / "swing.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    # Land schema at v18 first by applying 0001..0018 in order:
    _apply_migrations_through(conn, target_version=18)
    # Plant 3 rows mimicking production (29 historical + 3 unresolved-material).
    conn.execute("INSERT INTO reconciliation_runs (run_id, ...) VALUES (1, ...)")
    for i in range(1, 33):
        resolution = "acknowledged_immaterial" if i <= 29 else "unresolved"
        conn.execute(
            "INSERT INTO reconciliation_discrepancies (...) VALUES (...)",
            (i, 1, "entry_price_mismatch", ..., resolution, ...)
        )
    conn.commit()
    # Apply 0019.
    _apply_migration(conn, Path("swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql"))
    # All 32 rows preserved; ambiguity_kind=NULL for all.
    rows = conn.execute(
        "SELECT discrepancy_id, resolution, ambiguity_kind FROM reconciliation_discrepancies ORDER BY discrepancy_id"
    ).fetchall()
    assert len(rows) == 32
    assert all(r[2] is None for r in rows)
    assert sum(1 for r in rows if r[1] == "acknowledged_immaterial") == 29
    assert sum(1 for r in rows if r[1] == "unresolved") == 3
    conn.close()
```

Run + verify PASS.

- [ ] **Step 6: Write cross-column CHECK discriminating test.**

```python
# tests/data/test_migration_0019_schema_shape.py
def test_cross_column_check_rejects_ambiguity_kind_with_wrong_resolution(tmp_path):
    db = tmp_path / "swing.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(conn)
    _plant_run(conn, run_id=1)
    # Attempt: resolution='unresolved' + ambiguity_kind='unsupported' should reject.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(run_id, discrepancy_type, field_name, material_to_review, resolution, ambiguity_kind, created_at) "
            "VALUES (1, 'entry_price_mismatch', 'price', 0, 'unresolved', 'unsupported', '2026-05-15')"
        )
    # And: resolution='pending_ambiguity_resolution' + ambiguity_kind=NULL should reject.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO reconciliation_discrepancies "
            "(run_id, discrepancy_type, field_name, material_to_review, resolution, ambiguity_kind, created_at) "
            "VALUES (1, 'entry_price_mismatch', 'price', 0, 'pending_ambiguity_resolution', NULL, '2026-05-15')"
        )
    # Valid combos succeed:
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (...) "
        "VALUES (..., 'unresolved', NULL, ...)"
    )
    conn.execute(
        "INSERT INTO reconciliation_discrepancies (...) "
        "VALUES (..., 'pending_ambiguity_resolution', 'multi_partial_vs_consolidated', ...)"
    )
    conn.close()
```

Run + verify PASS (with the migration already applied).

- [ ] **Step 7: Commit.**

```bash
git add swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql swing/data/db.py tests/data/test_migration_0019_*.py
git commit -m "feat(phase12-bundle-c-T-A.1): schema v19 migration 0019 — reconciliation_corrections + ambiguity_kind + resolution widening + trade_events widening + 2 FK ALTERs"
```

### §B.2 Task T-A.2 — Dataclass extensions + new ReconciliationCorrection dataclass

**Files:**
- Modify: `swing/data/models.py` (extend `ReconciliationDiscrepancy` + `ReviewLog`; add `ReconciliationCorrection`)
- Modify: `swing/integrations/schwab/models.py` (extend SchwabApiCall dataclass if it exists; otherwise NO-OP-with-comment + V2 candidate per §A.7.4 confirmation that the dataclass may not exist; T-A.2.4 step verifies + decides)
- Test: `tests/data/test_models_phase12_bundle_c.py`

**Acceptance criteria:**
1. `ReconciliationDiscrepancy` gains `ambiguity_kind: str | None = None` field.
2. `ReviewLog` gains `superseded_by_correction_id: int | None = None` field.
3. NEW `ReconciliationCorrection` dataclass with all 19 columns matching the schema; type hints + nullability matching the CHECK constraints + defaults.
4. SchwabApiCall extension verified: if dataclass exists at `swing/integrations/schwab/models.py`, add `linked_correction_id: int | None = None` field; if it does NOT exist (per §A.7.4 grep no match), the column is consumed via raw SQL only V1 + V2 candidate §I.4 layers the dataclass.
5. Round-trip tests: every field reads back from DB matching the dataclass shape.
6. Defaults match SQL DEFAULT clauses (`ambiguity_kind` NULL default; `superseded_by_correction_id` NULL default).

- [ ] **Step 1: Write failing test for `ReconciliationCorrection` dataclass round-trip.**

```python
# tests/data/test_models_phase12_bundle_c.py
from swing.data.models import ReconciliationCorrection


def test_reconciliation_correction_dataclass_field_set():
    rc = ReconciliationCorrection(
        correction_id=1,
        discrepancy_id=41,
        correction_action="auto_applied",
        correction_choice=None,
        affected_table="fills",
        affected_row_id=9,
        field_name="price",
        pre_correction_value_json='{"price": 5.23}',
        source_canonical_value_json='{"price": 5.30}',
        applied_value_json='{"price": 5.30}',
        operator_truth_value_json=None,
        applied_at="2026-05-15T12:00:00.000",
        applied_by="auto",
        correction_set_id=None,
        superseded_by_correction_id=None,
        risk_policy_id_at_correction=5,
        schwab_api_call_id=38,
        reconciliation_run_id=10,
        correction_reason="tier-1 auto-correct",
        notes=None,
    )
    assert rc.affected_table == "fills"
    assert rc.applied_by == "auto"
```

Run + verify FAIL on ImportError.

- [ ] **Step 2: Implement `ReconciliationCorrection` dataclass at `swing/data/models.py`.**

```python
@dataclass(frozen=True)
class ReconciliationCorrection:
    """Phase 12 Sub-bundle C audit row for tier-1/tier-2/tier-3 corrections.

    Mirrors migration 0019 reconciliation_corrections table verbatim.
    """
    correction_id: int
    discrepancy_id: int
    correction_action: str  # 'auto_applied' | 'operator_resolved_ambiguity' | 'operator_overridden'
    correction_choice: str | None
    affected_table: str  # 'fills' | 'trades' | 'cash_movements' | 'account_equity_snapshots'
    affected_row_id: int
    field_name: str
    pre_correction_value_json: str
    source_canonical_value_json: str | None
    applied_value_json: str
    operator_truth_value_json: str | None
    applied_at: str  # ISO YYYY-MM-DDTHH:MM:SS.SSS naive-UTC
    applied_by: str  # 'auto' | 'operator'
    correction_set_id: int | None
    superseded_by_correction_id: int | None
    risk_policy_id_at_correction: int | None
    schwab_api_call_id: int | None
    reconciliation_run_id: int
    correction_reason: str | None
    notes: str | None
```

- [ ] **Step 3: Extend `ReconciliationDiscrepancy` + `ReviewLog` with new fields.**

```python
# Add to ReconciliationDiscrepancy:
ambiguity_kind: str | None = None

# Add to ReviewLog:
superseded_by_correction_id: int | None = None
```

- [ ] **Step 4: Investigate SchwabApiCall dataclass shape.**

```bash
grep -n "class SchwabApiCall" swing/integrations/schwab/models.py
```

If match found, add `linked_correction_id: int | None = None`. If no match, note this as a banked §I.4 V2 candidate (dataclass formalization) in the plan deviation log + proceed without dataclass change. The migration 0019 ALTER + the raw-SQL repo CRUD (T-A.3) suffice for column-level operations V1.

- [ ] **Step 5: Run tests + commit.**

Run: `pytest tests/data/test_models_phase12_bundle_c.py -v`
Expected: PASS.

```bash
git add swing/data/models.py swing/integrations/schwab/models.py tests/data/test_models_phase12_bundle_c.py
git commit -m "feat(phase12-bundle-c-T-A.2): ReconciliationCorrection dataclass + extended ReconciliationDiscrepancy.ambiguity_kind + ReviewLog.superseded_by_correction_id"
```

### §B.3 Task T-A.3 — `reconciliation_corrections` repo CRUD

**Files:**
- Create: `swing/data/repos/reconciliation_corrections.py`
- Test: `tests/data/test_reconciliation_corrections_repo.py`

**Acceptance criteria:**
1. Module exposes 7 pure-CRUD functions (caller controls transaction; mirror Phase 9 Sub-bundle A + Sub-bundle B precedent):
   - `insert_correction(conn, correction: ReconciliationCorrection) -> int` — returns the new `correction_id`; does NOT issue `conn.commit()` (caller-controlled tx; per CLAUDE.md "Repo functions must NOT call conn.commit()" Finviz lesson family).
   - `get_correction(conn, correction_id) -> ReconciliationCorrection | None`.
   - `list_corrections_by_discrepancy(conn, discrepancy_id) -> list[ReconciliationCorrection]` — ordered by `applied_at ASC, correction_id ASC` (chronological chain).
   - `list_corrections_by_run(conn, run_id) -> list[ReconciliationCorrection]`.
   - `list_corrections_by_affected_row(conn, affected_table, affected_row_id) -> list[ReconciliationCorrection]` — supports trade-detail UI + per-fill provenance queries.
   - `update_superseded_by(conn, correction_id, superseded_by_correction_id)` — used by tier-3 override apply (T-C.4) + multi-row correction-set anchor pattern (per spec §3.1.1 two-step: INSERT anchor → UPDATE self-reference).
   - `count_corrections_by_action(conn) -> dict[str, int]` — returns `{'auto_applied': N, 'operator_resolved_ambiguity': M, 'operator_overridden': K}` for `briefing.md` Reconciliation status section + summary CLI surface.
2. Each function reject `ON conn.in_transaction == False` is NOT asserted at repo level (repo functions are caller-tx; the SERVICE layer at C.C asserts caller-held-tx).
3. NO `INSERT OR REPLACE`; UPDATE-only semantics for the supersede-pointer-set helper (per CLAUDE.md `INSERT OR REPLACE` cascade-wipe gotcha).
4. All functions use parameterized SQL (no `f-string` interpolation of caller values).
5. Discriminating tests cover: insert + read-back; FK CASCADE from discrepancy_id delete propagates; FK SET NULL from policy_id / schwab_api_call_id delete (NULLABLE FK columns); listing order; supersede-pointer two-step semantics.

- [ ] **Step 1: Write failing CRUD round-trip test.**

```python
# tests/data/test_reconciliation_corrections_repo.py
from swing.data.repos.reconciliation_corrections import (
    count_corrections_by_action,
    get_correction,
    insert_correction,
    list_corrections_by_affected_row,
    list_corrections_by_discrepancy,
    list_corrections_by_run,
    update_superseded_by,
)


def test_insert_and_get_correction(conn_with_planted_discrepancy_41):
    conn = conn_with_planted_discrepancy_41
    rc = _build_correction(discrepancy_id=41, ...)
    cid = insert_correction(conn, rc)
    assert cid > 0
    fetched = get_correction(conn, cid)
    assert fetched.affected_table == "fills"
    assert fetched.correction_action == "auto_applied"
    assert fetched.applied_by == "auto"
    conn.commit()
```

Run + verify FAIL on ImportError.

- [ ] **Step 2: Implement repo functions.** (See acceptance criteria #1 enumeration; pure SQL with parameter binding; no commit calls.)

- [ ] **Step 3: Write FK CASCADE test.**

Plants a correction row keyed on `discrepancy_id=41`; DELETEs the parent discrepancy; verifies the correction row is also deleted (CASCADE FK per §3.1).

- [ ] **Step 4: Write supersede-pointer two-step test.**

Plants 2 correction rows; calls `update_superseded_by(conn, 1, 2)`; reads back; verifies row 1's `superseded_by_correction_id = 2`; verifies row 2's `superseded_by_correction_id IS NULL`. Then ALSO tests the anchor-self-reference pattern (per OQ-6 disposition): INSERT anchor row (returns `correction_id=3`); UPDATE `correction_set_id = 3` on that anchor row; verify both `correction_id == correction_set_id` for the anchor.

- [ ] **Step 5: Write listing-order test.**

Plants 3 correction rows for one discrepancy at distinct `applied_at` timestamps; calls `list_corrections_by_discrepancy`; verifies ascending `applied_at` order with secondary tiebreaker on `correction_id ASC` (deterministic per Phase 10 Sub-bundle D lesson #26 SQL ORDER BY tiebreaker family).

- [ ] **Step 6: Run + commit.**

```bash
pytest tests/data/test_reconciliation_corrections_repo.py -v
git add swing/data/repos/reconciliation_corrections.py tests/data/test_reconciliation_corrections_repo.py
git commit -m "feat(phase12-bundle-c-T-A.3): reconciliation_corrections repo CRUD (7 pure-SQL caller-tx functions)"
```

### §B.4 Task T-A.4 — Migration runner backup-gate wiring

**Files:**
- Modify: `swing/data/db.py` (add Phase 12 Sub-bundle C backup-gate entry)
- Test: `tests/data/test_migration_runner_backup_gate.py`

**Acceptance criteria:**
1. Backup-gate registry in `swing/data/db.py` gains an entry for `(current_version == 18, target >= 19)` triggering filename `swing-pre-phase12-bundle-c-migration-<ISO>.db`.
2. Existing Phase 9 + Phase 11 backup-gate entries unchanged.
3. Discriminating test plants a v18-baseline DB + invokes `swing db-migrate` programmatically + verifies the backup file is created with the expected filename pattern in the same parent dir as `swing.db`.
4. Test asserts the backup file content equals the pre-migration DB byte-for-byte (uses `hashlib.sha256` on both files).
5. Test asserts the backup is taken BEFORE migration 0019 applies (verify via timestamp ordering or in-memory state assertion).

- [ ] **Step 1-7: TDD per existing pattern.** Reuse Phase 9 Sub-bundle A T-A.1 + Phase 11 Sub-bundle A T-A.7 patterns verbatim (they ship the same backup-gate mechanism with different filenames).

```bash
git add swing/data/db.py tests/data/test_migration_runner_backup_gate.py
git commit -m "feat(phase12-bundle-c-T-A.4): migration runner backup-gate for v18->v19 transition"
```

### §B.5 Task T-A.5 — Extend `ReconciliationDiscrepancy` row deserializer for `ambiguity_kind`

**Files:**
- Modify: `swing/data/repos/reconciliation.py` (extend `_DISCREPANCY_SELECT_COLUMNS` + `_row_to_discrepancy`)
- Test: `tests/data/test_reconciliation_discrepancy_ambiguity_kind_roundtrip.py`

**Acceptance criteria:**
1. `_DISCREPANCY_SELECT_COLUMNS` (and its `_D_ALIAS` companion) include `ambiguity_kind` (per §A.5 grep — the constant is the canonical column list used by Phase 9 Sub-bundle B + Phase 10 helpers).
2. `_row_to_discrepancy` row deserializer reads the new column AND populates the dataclass field added at T-A.2.
3. Discriminating test plants a discrepancy with `resolution='pending_ambiguity_resolution', ambiguity_kind='multi_partial_vs_consolidated'`; reads it back via `get_discrepancy`; verifies the dataclass field is populated.
4. Back-compat test: plant a discrepancy with `resolution='unresolved', ambiguity_kind=NULL`; read back; verify `ambiguity_kind is None`.

- [ ] **Steps 1-6: TDD.**

```bash
git add swing/data/repos/reconciliation.py tests/data/test_reconciliation_discrepancy_ambiguity_kind_roundtrip.py
git commit -m "feat(phase12-bundle-c-T-A.5): ReconciliationDiscrepancy.ambiguity_kind row deserializer extension"
```

### §B.6 Task T-A.6 — Extend `ReviewLog` row deserializer for `superseded_by_correction_id`

**Files:**
- Modify: `swing/data/repos/review_log.py` (extend column-select + row deserializer)
- Test: `tests/data/test_review_log_superseded_by_correction_id_roundtrip.py`

**Acceptance criteria:** mirrors T-A.5 for `ReviewLog` with the new column; back-compat test with existing review_log rows untouched.

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/data/repos/review_log.py tests/data/test_review_log_superseded_by_correction_id_roundtrip.py
git commit -m "feat(phase12-bundle-c-T-A.6): ReviewLog.superseded_by_correction_id row deserializer extension"
```

### §B.7 Task T-A.7 — Cross-bundle pin: forward-declared classifier interface in plan §F

**Files:** docs-only at this stage (cross-bundle pin recorded in §F binding interface table).

**Acceptance criteria:**
1. No code change; this task is a check-pin step.
2. Plan §F.1 BINDING INTERFACE table records:
   - `swing/trades/reconciliation_classifier.py:classify_discrepancy(...)` signature (T-B.1 implements).
   - `swing/trades/reconciliation_classifier.py:ClassificationResult` shape (T-B.1 implements).
   - `swing/trades/reconciliation_validators.py:default_validator_chain(conn)` signature (T-B.13 implements).
3. A test placeholder in `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` is decorated `@pytest.mark.skip(reason="forward-binding; un-skip at C.B T-B.1 + T-B.2 landing")` for the test asserting both modules exist + classifier returns a `ClassificationResult`.

- [ ] **Step 1: Create the placeholder test with skip decorator.**

```python
# tests/integration/test_phase12_bundle_c_cross_bundle_pin.py
import pytest


@pytest.mark.skip(
    reason="forward-binding; un-skip at C.B T-B.1 + T-B.2 landing — "
           "classifier + validator-shim modules ship in Sub-sub-bundle C.B"
)
def test_classifier_module_exists_and_returns_classification_result():
    from swing.trades.reconciliation_classifier import (
        ClassificationResult,
        classify_discrepancy,
    )
    # placeholder; full discriminating test built at C.B T-B.1.
    assert callable(classify_discrepancy)
    assert ClassificationResult is not None


@pytest.mark.skip(
    reason="forward-binding; un-skip at C.B T-B.2 landing — "
           "validator-shim module ships in Sub-sub-bundle C.B"
)
def test_validator_chain_dispatches_on_affected_table():
    from swing.trades.reconciliation_validators import (
        default_validator_chain,
    )
    assert callable(default_validator_chain)
```

- [ ] **Step 2: Commit.**

```bash
git add tests/integration/test_phase12_bundle_c_cross_bundle_pin.py
git commit -m "test(phase12-bundle-c-T-A.7): forward-binding pin tests for classifier + validator shim (skip until C.B lands)"
```

### §B.8 Task T-A.8 — Verify clean apply against production-snapshot DB (operator-witnessed)

**Files:**
- Test: `tests/data/test_migration_0019_against_production_snapshot.py` (slow-marked; reads operator's `~/swing-data/swing.db` snapshot)

**Acceptance criteria:**
1. Test is `@pytest.mark.slow` (NOT in fast suite).
2. Test reads a copy of operator's production DB (via fixture `operator_swing_db_snapshot_copy`) + applies migration 0019 + asserts:
   - schema_version transitions 18 → 19.
   - All 32 historical `reconciliation_discrepancies` rows preserved verbatim (column-by-column equality).
   - All 4 existing reconciliation_runs preserved.
   - All `review_log` rows preserved (count unchanged; new column NULL for all).
   - All `trade_events` rows preserved verbatim.
   - All `schwab_api_calls` rows preserved verbatim.
3. Test runs in CI's slow-suite OR operator-driven before integration merge.

- [ ] **Steps 1-3: implement the slow-marked test using `shutil.copy` of operator's DB to a tmp path + apply + verify.**

```bash
git add tests/data/test_migration_0019_against_production_snapshot.py
git commit -m "test(phase12-bundle-c-T-A.8): slow-marked migration 0019 production-snapshot regression test"
```

### §B.9 C.A integration commit + ruff + worktree push

After T-A.1 through T-A.8 land on the worktree branch, the implementer:

1. Runs `pytest -q -n auto` and confirms +40-65 new fast tests (above worktree baseline 3862).
2. Runs `ruff check swing/` and confirms baseline 18 unchanged.
3. Confirms `swing db-migrate` against the worktree's fresh DB transitions to schema_version 19.
4. Pushes the worktree branch.

C.A operator-witnessed gate (per §G.1) follows — 4 surfaces verified by the orchestrator before integration merge.

---

## §C Sub-sub-bundle C.B — Classifier + validator shim

**Scope summary (per spec §12.B):**
- NEW pure-function module `swing/trades/reconciliation_classifier.py` with `classify_discrepancy(...)` public entry + per-discrepancy-type sub-classifiers + `ClassificationResult` shape.
- NEW shim module `swing/trades/reconciliation_validators.py` with 4 dry-run validators + `default_validator_chain(conn)` dispatcher (per spec §5.5 LOCK + OQ-14 LOCK).
- Per-discrepancy-type sub-classifier test coverage (10 types × multiple cases each).
- ZERO journal mutations. ZERO Schwab API calls. ZERO service composition.

**Files touched:**
- Create: `swing/trades/reconciliation_classifier.py`
- Create: `swing/trades/reconciliation_validators.py`
- Create: `tests/trades/test_reconciliation_classifier.py` (multi-file split per sub-classifier likely)
- Create: `tests/trades/test_reconciliation_validators.py`
- Modify: `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` (un-skip the two pin tests)

**Projected fast-test delta:** +55-95 tests (per spec §12.B +50-90 + plan-time additions for classifier failure-mode contract + validator-rejected downgrade discriminating tests).

### §C.1 Task T-B.1 — `classify_discrepancy` public entry + `ClassificationResult` dataclass

**Files:**
- Create: `swing/trades/reconciliation_classifier.py` (skeleton with public entry + dispatch table only at this task; per-type sub-classifiers land in T-B.3..T-B.12)
- Test: `tests/trades/test_reconciliation_classifier_public_entry.py`

**Acceptance criteria:**
1. Public entry signature matches spec §4.2 verbatim:
   ```python
   def classify_discrepancy(
       discrepancy: ReconciliationDiscrepancy,
       *,
       source_payload: dict | None,
       journal_row: dict | None,
       validator_chain: ValidatorChainCallable | None = None,
   ) -> ClassificationResult: ...
   ```
2. `ClassificationResult` dataclass exposes:
   - `tier: int` (1 or 2)
   - `ambiguity_kind: str | None`
   - `correction_target: dict | None`
   - `correction_reason: str` (non-empty)
   - `candidate_choices: list[dict] | None`
3. Dispatch table maps each of the 10 `discrepancy_type` values to a per-type sub-classifier callable. UNKNOWN types raise + are caught by the dispatcher's `try/except` per spec §4.5 → `(tier=2, ambiguity_kind='unsupported', correction_target=None, correction_reason="classifier exception: ...")`.
4. Pure function: NO DB writes, NO Schwab API calls, NO transaction management. `journal_row` is passed in as already-fetched data; `source_payload` is passed in as already-fetched data.
5. `validator_chain` invocation contract: when `validator_chain is not None AND classification.tier == 1`, the dispatcher calls `validator_chain(correction_target)` AFTER the sub-classifier returns tier-1; on `False`, downgrades to `(tier=2, ambiguity_kind='validator_rejected', correction_reason=<rejection_reason>)`.
6. `correction_reason` MUST be human-readable + non-empty on every emission. Tier-1 reasons name the discrepancy_type + the field + journal-vs-source values. Tier-2 reasons describe the ambiguity_kind + classifier rationale.
7. Determinism contract: same inputs → same `ClassificationResult` byte-for-byte. Discriminating test invokes the classifier 100× with the same fixture inputs + asserts the result is byte-for-byte identical.

- [ ] **Step 1: Write failing test for the public entry signature + dataclass.**

```python
# tests/trades/test_reconciliation_classifier_public_entry.py
from swing.trades.reconciliation_classifier import (
    ClassificationResult,
    classify_discrepancy,
)


def test_classification_result_dataclass_shape():
    cr = ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="entry_price_mismatch on CVGI",
        candidate_choices=None,
    )
    assert cr.tier == 1
    assert cr.ambiguity_kind is None
    assert cr.correction_target == {"price": 5.30}


def test_classify_discrepancy_signature_accepts_kwargs(planted_cvgi_discrepancy):
    result = classify_discrepancy(
        planted_cvgi_discrepancy,
        source_payload={"price": 5.30},
        journal_row={"price": 5.23, "quantity": 100, "trade_id": 1},
        validator_chain=None,
    )
    assert isinstance(result, ClassificationResult)
```

Run + verify FAIL on ImportError.

- [ ] **Step 2: Implement the skeleton.**

```python
# swing/trades/reconciliation_classifier.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from swing.data.models import ReconciliationDiscrepancy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClassificationResult:
    """Classifier output — pure data shape; tier ∈ {1, 2}.

    Tier-3 is operator-initiated post-tier-1; the classifier NEVER emits tier=3.
    """
    tier: int
    ambiguity_kind: str | None
    correction_target: dict[str, Any] | None
    correction_reason: str
    candidate_choices: list[dict[str, Any]] | None = None


ValidatorChainCallable = Callable[[Mapping[str, Any]], tuple[bool, str | None]]
# Returns (passes, rejection_reason). False + non-empty reason -> tier-2 downgrade.


# Dispatch table populated as sub-classifiers land (T-B.3..T-B.12).
_SUB_CLASSIFIERS: dict[str, Callable[..., ClassificationResult]] = {}


def classify_discrepancy(
    discrepancy: ReconciliationDiscrepancy,
    *,
    source_payload: dict | None,
    journal_row: dict | None,
    validator_chain: ValidatorChainCallable | None = None,
) -> ClassificationResult:
    """Pure classifier; dispatches on discrepancy_type."""
    sub = _SUB_CLASSIFIERS.get(discrepancy.discrepancy_type)
    if sub is None:
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=(
                f"no sub-classifier for discrepancy_type="
                f"{discrepancy.discrepancy_type!r}"
            ),
        )
    try:
        result = sub(
            discrepancy=discrepancy,
            source_payload=source_payload,
            journal_row=journal_row,
        )
    except Exception as e:  # noqa: BLE001 — graceful degradation per spec §4.5
        logger.warning(
            "classifier exception for discrepancy %d (%s): %s: %s",
            discrepancy.discrepancy_id,
            discrepancy.discrepancy_type,
            type(e).__name__,
            e,
        )
        return ClassificationResult(
            tier=2,
            ambiguity_kind="unsupported",
            correction_target=None,
            correction_reason=f"classifier exception: {type(e).__name__}: {e}",
        )
    if result.tier == 1 and validator_chain is not None:
        passes, reason = validator_chain(result.correction_target or {})
        if not passes:
            return ClassificationResult(
                tier=2,
                ambiguity_kind="validator_rejected",
                correction_target=None,
                correction_reason=(
                    f"validator rejected proposed correction: {reason or 'unknown'}"
                ),
            )
    return result
```

- [ ] **Step 3: Write determinism contract test.**

```python
def test_classifier_is_deterministic(planted_cvgi_discrepancy):
    fixture = {
        "discrepancy": planted_cvgi_discrepancy,
        "source_payload": {"price": 5.30},
        "journal_row": {"price": 5.23, "quantity": 100, "trade_id": 1},
        "validator_chain": None,
    }
    first = classify_discrepancy(**fixture)
    for _ in range(99):
        nth = classify_discrepancy(**fixture)
        assert nth == first  # frozen dataclass equality is deep
```

- [ ] **Step 4: Write graceful-degradation test for unknown discrepancy_type.**

Plants a discrepancy whose `discrepancy_type` is NOT in the dispatch table (synthetic value `'__unrecognized__'`); invokes classifier; asserts `result.tier == 2 AND result.ambiguity_kind == 'unsupported'`. Confirms the failure-mode contract per spec §4.5.

- [ ] **Step 5: Run + commit.**

```bash
pytest tests/trades/test_reconciliation_classifier_public_entry.py -v
git add swing/trades/reconciliation_classifier.py tests/trades/test_reconciliation_classifier_public_entry.py
git commit -m "feat(phase12-bundle-c-T-B.1): classify_discrepancy public entry + ClassificationResult dataclass + dispatch table skeleton"
```

### §C.2 Task T-B.2 — Validator shim module (4 dry-run validators)

**Files:**
- Create: `swing/trades/reconciliation_validators.py`
- Test: `tests/trades/test_reconciliation_validators.py`

**Acceptance criteria:**
1. Module exports 4 dry-run validator callables matching spec §5.5 signatures:
   - `validate_fill_correction(conn, fill_id, proposed_updates: dict) -> tuple[bool, str | None]`
   - `validate_trade_correction(conn, trade_id, proposed_updates: dict) -> tuple[bool, str | None]`
   - `validate_cash_movement_correction(conn, movement_id, proposed_updates: dict) -> tuple[bool, str | None]`
   - `validate_snapshot_correction(conn, snapshot_id, proposed_updates: dict) -> tuple[bool, str | None]`
2. Return shape is `(passes: bool, rejection_reason: str | None)` matching `ValidatorChainCallable` from T-B.1. (Spec §5.5 wording "True/False (plus a rejection reason)" formalized here as a 2-tuple; banked as a V2.1 §VII.F spec-amendment candidate at §I if the spec author requires exception-based signaling.)
3. Each validator reads the current row via SELECT (no UPDATE) + builds a Python dict copy + applies `proposed_updates` + checks the result against schema-CHECK-mirror predicates.
4. Validator predicates mirror schema constraints VERBATIM (no app-layer rule overlay):
   - `validate_fill_correction`: `quantity > 0`; `price > 0` (when present in proposed updates); `trade_id` FK exists in `trades` table; `action` IN the CHECK enum; for `fills` aggregate invariant — simulated `_recompute_aggregates` post-correction MUST NOT produce `current_size < 0` (a SELECT-based dry-run sums entry-vs-non-entry per spec §A.9 SQL pattern with the proposed fill swapped in).
   - `validate_trade_correction`: `current_stop > 0` (when in updates); `state` IN CHECK enum (when in updates).
   - `validate_cash_movement_correction`: schema CHECK + FK existence; `amount` sign-vs-movement_type consistent (per spec §4.6).
   - `validate_snapshot_correction`: `equity_dollars > 0` per migration 0017 CHECK.
5. NEVER mutates the DB. Discriminating test: plants a valid fill; calls `validate_fill_correction(conn, fill_id, {"price": -1.0})` → asserts `(False, "price must be > 0")`; reads `fills.price` back from DB; asserts unchanged.
6. FK-exists check on `trade_id` returns `(False, "trade_id N not found")` if the proposed update names a non-existent trade.
7. Aggregate-invariant dry-run on a fill correction asserts the simulated post-correction `current_size` is non-negative. Discriminating test: plants a trade with 1 entry fill (100 shares) + 1 trim fill (50 shares) + simulates a correction that would change the entry fill's quantity to 30 → resulting `current_size = 30 - 50 = -20 < 0` → validator returns `(False, "current_size would be negative ...")`.

- [ ] **Step 1: Write failing test for shim function shapes.**

```python
# tests/trades/test_reconciliation_validators.py
import sqlite3

import pytest

from swing.trades.reconciliation_validators import (
    validate_cash_movement_correction,
    validate_fill_correction,
    validate_snapshot_correction,
    validate_trade_correction,
)


def test_validate_fill_correction_returns_passes_tuple_on_valid(conn_with_planted_cvgi_trade_and_fill):
    conn = conn_with_planted_cvgi_trade_and_fill
    fill_id = 9
    passes, reason = validate_fill_correction(conn, fill_id, {"price": 5.30})
    assert passes is True
    assert reason is None


def test_validate_fill_correction_rejects_negative_price(conn_with_planted_cvgi_trade_and_fill):
    conn = conn_with_planted_cvgi_trade_and_fill
    passes, reason = validate_fill_correction(conn, 9, {"price": -1.0})
    assert passes is False
    assert "price" in (reason or "").lower()
```

Run + verify FAIL on ImportError.

- [ ] **Step 2: Implement the 4 validators.**

Each follows the SELECT-current-row → apply-proposed-updates → check-predicates pattern. Discriminating tests for all 4 happy paths + 4-6 reject paths each.

- [ ] **Step 3: Write aggregate-invariant test.**

```python
def test_validate_fill_correction_rejects_aggregate_invariant_violation(
    conn_with_planted_trim_scenario
):
    """Plant: 1 entry (100sh) + 1 trim (50sh); current_size=50. Propose
    correction to entry: quantity=30. Simulated current_size = 30-50 = -20 < 0."""
    conn = conn_with_planted_trim_scenario
    passes, reason = validate_fill_correction(conn, fill_id=1, proposed_updates={"quantity": 30})
    assert passes is False
    assert "current_size" in (reason or "").lower()
```

- [ ] **Step 4-5: Implement remaining 3 validators + tests + commit.**

```bash
git add swing/trades/reconciliation_validators.py tests/trades/test_reconciliation_validators.py
git commit -m "feat(phase12-bundle-c-T-B.2): reconciliation_validators shim — 4 dry-run callable validators"
```

### §C.3 Task T-B.3 — `entry_price_mismatch` sub-classifier (CVGI 41 path)

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py` (add `_classify_entry_price_mismatch` + register in dispatch table)
- Test: `tests/trades/test_classifier_entry_price_mismatch.py`

**Acceptance criteria:**
1. Sub-classifier matches spec §4.3.1 LOGIC:
   - If `journal_row.(ticker, date, quantity)` matches `source_payload.(ticker, date, quantity)` exactly AND only `price` differs → `tier=1, correction_target={'price': source_payload['price']}`.
   - If `source_payload is None` → `tier=2, ambiguity_kind='schwab_returned_no_match'`.
   - If `source_payload` carries multiple-match indicator (V1: not currently emitted by `swing/trades/schwab_reconciliation.py:469-474` — Pass 1 always single-fill match for `entry_price_mismatch`) → `tier=2, ambiguity_kind='multi_match_within_window'`. V1 default for this sub-classifier on the shipped emitter shape is tier-1.
2. `correction_reason` on tier-1 includes ticker + fill_id + journal-price + source-price + delta.
3. Discriminating test: CVGI 41 fixture (journal $5.23 × 100 on 2026-04-XX; source $5.30) → `tier=1, correction_target={'price': 5.30}`.
4. Discriminating test for tier-2 downgrade with `validator_chain` injection: when the injected `validator_chain` returns `(False, "price would violate ...")`, the dispatcher (T-B.1) downgrades to tier-2 with `ambiguity_kind='validator_rejected'`. This test exercises the DISPATCHER's validator-respecting downgrade, not the sub-classifier itself.

- [ ] **Steps 1-5: TDD.** Plant CVGI 41 fixture per spec §10.1 setup; assert classifier output equals spec §10.1 "Classifier OUTPUT" verbatim.

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_entry_price_mismatch.py
git commit -m "feat(phase12-bundle-c-T-B.3): entry_price_mismatch sub-classifier (CVGI 41 walkthrough discriminating tests)"
```

### §C.4 Task T-B.4 — `unmatched_open_fill` sub-classifier (DHC 39 + VSAT 40 path)

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py` (add `_classify_unmatched_open_fill` + register)
- Test: `tests/trades/test_classifier_unmatched_open_fill.py`

**Acceptance criteria (per spec §4.3.2 + §8.4 Pass-2-tier-1-FORBIDDEN LOCK):**
1. **V1 LOCK: NEVER emits tier-1.** Per the Pass-2-tier-1-FORBIDDEN rule on order-level source data (`SchwabOrderResponse.price` is limit/stop price, not execution price per spec §8.4 + §A.7.4 mapper verification).
2. LOGIC dispatch:
   - `source_payload` is `None` OR has explicit `{"matched": null}` AND no Pass-2 data → `tier=2, ambiguity_kind='unsupported'` with metadata flag `_pass_2_required=True` in `correction_reason`. The backfill path (T-D.8) reads this signal to fire Pass 2.
   - `source_payload` is list-shaped with 0 elements → `tier=2, ambiguity_kind='schwab_returned_no_match'`.
   - `source_payload` is list-shaped with 1 element (single Schwab order at order-grain) → `tier=2, ambiguity_kind='unknown_schwab_subtype'` with rationale per spec §8.4 case (1 order returned).
   - `source_payload` is list-shaped with N≥2 elements AND `sum(o.quantity for o in source_payload) == journal_row.quantity` → `tier=2, ambiguity_kind='multi_partial_vs_consolidated'`.
   - `source_payload` is list-shaped with N≥2 elements AND `sum(...) != journal_row.quantity` → `tier=2, ambiguity_kind='multi_match_within_window'`.
3. `candidate_choices` populated per the per-ambiguity_kind §6.2.1 menu:
   - For `multi_partial_vs_consolidated`: 4 choices (`keep_journal_as_is` HIGHLIGHTED PER §0.4 OQ-4 + `consolidate_using_operator_vwap` + `split_into_partials` + `custom`).
   - For `multi_match_within_window`: N+2 choices (`pick_schwab_record_<i>` for i=1..N + `mark_unmatched` + `custom`).
   - For `schwab_returned_no_match`: 2 choices (`mark_unmatched` + `operator_truth`).
   - For `unknown_schwab_subtype`: 3 choices (`acknowledge` + `operator_truth` + `custom`).
   - For `unsupported` with `_pass_2_required` signal: 0 candidate_choices V1 (Pass 2 re-fetch surfaces the actual list at backfill time).
4. Choice dicts include `code`, `description`, AND `requires_custom_value: bool` (per spec §6.2.1 LOCKED per-choice `--custom-value` contract; Codex R5 Major #2 fix).
5. Discriminating tests cover each branch:
   - DHC 39 fixture (Pass 1 only — `actual={"matched": null}`): `tier=2, ambiguity_kind='unsupported', _pass_2_required=True`.
   - DHC 39 fixture (Pass 2 returns 2 orders qty=20+19=39): `tier=2, ambiguity_kind='multi_partial_vs_consolidated'`; `candidate_choices` length = 4; `keep_journal_as_is` is candidate_choices[0].
   - VSAT 40 fixture (Pass 2 returns 1 order qty=2): `tier=2, ambiguity_kind='unknown_schwab_subtype'`.
   - VSAT 40 fixture (Pass 2 returns 0 orders): `tier=2, ambiguity_kind='schwab_returned_no_match'`.
   - VSAT 40 fixture (Pass 2 returns 2 orders qty=1+3=4 ≠ journal qty=2): `tier=2, ambiguity_kind='multi_match_within_window'`.
6. **Determinism principle (§4.4) discriminating test:** sub-classifier NEVER returns tier-1 on `unmatched_open_fill`. Test plants every plausible Pass-2 input shape + asserts `result.tier == 2` for all.

- [ ] **Steps 1-6: TDD per acceptance criteria.** Each fixture wires DHC/VSAT-shaped journal_rows + Pass-2-payload variations.

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_unmatched_open_fill.py
git commit -m "feat(phase12-bundle-c-T-B.4): unmatched_open_fill sub-classifier (DHC+VSAT walkthroughs; tier-2-always per Pass-2-tier-1-FORBIDDEN LOCK)"
```

### §C.5 Task T-B.5 — `unmatched_close_fill` sub-classifier

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py`
- Test: `tests/trades/test_classifier_unmatched_close_fill.py`

**Acceptance criteria:** mirrors T-B.4 symmetrically for close-side fills (per spec §4.3.3). Same `ambiguity_kind` values; same candidate choices; same tier-2-always V1 LOCK. Discriminating tests cover trim-vs-final-exit semantics: when the journal fill is `action='exit'` vs `action='trim'`, the sub-classifier emits identical tier/ambiguity output (the `action` field is metadata for downstream service; classifier is action-agnostic for unmatched close).

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_unmatched_close_fill.py
git commit -m "feat(phase12-bundle-c-T-B.5): unmatched_close_fill sub-classifier (mirrors T-B.4)"
```

### §C.6 Task T-B.6 — `stop_mismatch` sub-classifier

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py`
- Test: `tests/trades/test_classifier_stop_mismatch.py`

**Acceptance criteria (per spec §4.3.4):**
1. LOGIC:
   - `source_payload` carries `{"stop_price": X}` for ticker + journal `current_stop` differs → `tier=1, correction_target={'current_stop': X}`.
   - `source_payload` has multiple active stops → `tier=2, ambiguity_kind='multi_match_within_window'`.
   - `source_payload is None` or no active stops AND journal has stop → `tier=2, ambiguity_kind='schwab_returned_no_match'`.
2. Tier-1 emissions DO NOT consult Phase 9 risk_policy advisory thresholds (per spec §4.3.4 + §1.6 advisory-not-validator family). Advisories surface at Phase 10 dashboard time.
3. Discriminating tests cover the 3 paths + verify advisory-out-of-band non-blocking (planting a trade with `risk_policy_id_at_lock` AND a proposed stop that trips a `scratch_epsilon_R` advisory → classifier still emits tier-1; advisory surfaces at dashboard later).

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_stop_mismatch.py
git commit -m "feat(phase12-bundle-c-T-B.6): stop_mismatch sub-classifier (advisory-not-validator family preserved)"
```

### §C.7 Task T-B.7 — `position_qty_mismatch` sub-classifier

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py`
- Test: `tests/trades/test_classifier_position_qty_mismatch.py`

**Acceptance criteria (per spec §4.3.5):**
1. V1 LOCK: position_qty_mismatch is **tier-2-always V1** (per spec §4.3.5: "Most cases route to tier-2 in V1; tier-1 auto-quantity-correction requires per-fill broker attribution V1 Schwab API doesn't provide cleanly").
2. LOGIC:
   - Broker has 1 position record + journal has fills summing to broker_qty + fills count is small (≤3) → `tier=2, ambiguity_kind='multi_match_within_window'` per fill (operator decides which fill is wrong-qty).
   - Broker has 0 positions AND journal has open trade → `tier=2, ambiguity_kind='schwab_returned_no_match'`.
   - Otherwise default `tier=2, ambiguity_kind='unsupported'`.
3. Discriminating tests cover each branch.

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_position_qty_mismatch.py
git commit -m "feat(phase12-bundle-c-T-B.7): position_qty_mismatch sub-classifier (tier-2-always V1)"
```

### §C.8 Task T-B.8 — `close_price_mismatch` sub-classifier

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py`
- Test: `tests/trades/test_classifier_close_price_mismatch.py`

**Acceptance criteria (per spec §4.3.6):**
1. V1 LOCK: tier-2-always V1 unless explicitly attributable to a Schwab quote response (historical close-price corrections are V2 candidate).
2. LOGIC: default `tier=2, ambiguity_kind='unknown_schwab_subtype'` with rationale "close_price_mismatch on historical snapshot; V1 cannot re-import OHLCV history; operator dispositions via acknowledge OR operator_truth".
3. Discriminating tests cover the 3 cases from §10 if any close_price_mismatch is present (none of CVGI/DHC/VSAT are close_price; pure unit coverage via synthetic fixtures).

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_close_price_mismatch.py
git commit -m "feat(phase12-bundle-c-T-B.8): close_price_mismatch sub-classifier (tier-2-always V1; V2 OHLCV re-import banked)"
```

### §C.9 Task T-B.9 — `cash_movement_mismatch` sub-classifier

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py`
- Test: `tests/trades/test_classifier_cash_movement_mismatch.py`

**Acceptance criteria (per spec §4.3.7):**
1. LOGIC:
   - `source_payload` has 1 matching cash movement by `(date, amount within tolerance, type)` → `tier=1, correction_target={...specific fields differ...}`. The `correction_target` may carry multiple fields atomically per spec §4.4 "explicitly designed as multi-field tier-1" + §3.1.1 multi-column atomic correction discipline; classifier supplies a multi-field dict + downstream service writes a `correction_set_id`-bundled set.
   - Otherwise `tier=2` with appropriate `ambiguity_kind`.
2. V1 conservative: most route to tier-2 operator review.
3. Discriminating tests cover the 1-match tier-1 path + 0-match + multi-match paths.

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_cash_movement_mismatch.py
git commit -m "feat(phase12-bundle-c-T-B.9): cash_movement_mismatch sub-classifier (tier-1 single-match + tier-2 otherwise)"
```

### §C.10 Task T-B.10 — `sector_tamper` sub-classifier

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py`
- Test: `tests/trades/test_classifier_sector_tamper.py`

**Acceptance criteria (per spec §4.3.8):**
1. V1 LOCK: tier-2-always — Schwab doesn't supply sector data; operator-action-only.
2. LOGIC: emit `tier=2, ambiguity_kind='unknown_schwab_subtype'` with rationale "sector_tamper requires operator override (tier-3 path); Schwab does not supply sector data".
3. Discriminating test: plants a sector_tamper discrepancy (Phase 9 Sub-bundle D-style) + asserts tier-2 + correct ambiguity_kind.

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_sector_tamper.py
git commit -m "feat(phase12-bundle-c-T-B.10): sector_tamper sub-classifier (tier-2-always V1)"
```

### §C.11 Task T-B.11 — `snapshot_mismatch` sub-classifier

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py`
- Test: `tests/trades/test_classifier_snapshot_mismatch.py`

**Acceptance criteria (per spec §4.3.9):** mirrors T-B.8 (close_price_mismatch) — tier-2-always V1; V2 candidate for richer auto-correct. Discriminating tests synthetic.

- [ ] **Steps 1-4: TDD.**

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_snapshot_mismatch.py
git commit -m "feat(phase12-bundle-c-T-B.11): snapshot_mismatch sub-classifier (tier-2-always V1)"
```

### §C.12 Task T-B.12 — `equity_delta` sub-classifier

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py`
- Test: `tests/trades/test_classifier_equity_delta.py`

**Acceptance criteria (per spec §4.3.10):**
1. V1 LOCK: tier-2-always — cash-basis-vs-MTM semantics divergence is a known Phase 9 Sub-bundle C operator-locked V2 candidate.
2. LOGIC: emit `tier=2, ambiguity_kind='field_shape_incompatible'` with rationale "equity_delta requires cash-basis-vs-MTM formalization (Phase 10 V2 candidate); operator dispositions via acknowledge OR operator_truth".
3. Discriminating test: plants an equity_delta discrepancy (Phase 9 Sub-bundle C-style with non-zero `equity_delta_dollars`) + asserts tier-2 + correct ambiguity_kind.

- [ ] **Steps 1-4: TDD.**

```bash
git add swing/trades/reconciliation_classifier.py tests/trades/test_classifier_equity_delta.py
git commit -m "feat(phase12-bundle-c-T-B.12): equity_delta sub-classifier (tier-2-always V1; Phase 10 V2 cash-basis-vs-MTM banked)"
```

### §C.13 Task T-B.13 — `default_validator_chain(conn)` dispatcher

**Files:**
- Modify: `swing/trades/reconciliation_validators.py`
- Test: `tests/trades/test_default_validator_chain.py`

**Acceptance criteria:**
1. NEW function `default_validator_chain(conn: sqlite3.Connection) -> ValidatorChainCallable`.
2. Returns a callable that, when invoked with `(correction_target: dict, *, affected_table: str, affected_row_id: int)`, dispatches to the right validator based on `affected_table`:
   - `'fills'` → `validate_fill_correction(conn, affected_row_id, correction_target)`
   - `'trades'` → `validate_trade_correction(conn, affected_row_id, correction_target)`
   - `'cash_movements'` → `validate_cash_movement_correction(conn, affected_row_id, correction_target)`
   - `'account_equity_snapshots'` → `validate_snapshot_correction(conn, affected_row_id, correction_target)`
3. Returns `(passes, reason)` tuple per the `ValidatorChainCallable` protocol.
4. NOTE: `classify_discrepancy`'s dispatcher (T-B.1 Step 2) currently invokes `validator_chain(correction_target)` with a single positional arg. To compose `default_validator_chain` with `classify_discrepancy`, callers MUST partially-apply `affected_table` + `affected_row_id` at construction time (e.g., via `functools.partial`). This composition lives in the auto-correction service (T-C.2 Step 4) where caller-context (the discrepancy's `affected_table` + the journal-row PK) is known.
5. Discriminating test: builds a chain for the CVGI 41 case (affected_table='fills', affected_row_id=9); invokes with `{"price": 5.30}`; asserts `(True, None)`. Builds another chain for the same fill_id; invokes with `{"price": -1.0}`; asserts `(False, "price ...")`.

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/trades/reconciliation_validators.py tests/trades/test_default_validator_chain.py
git commit -m "feat(phase12-bundle-c-T-B.13): default_validator_chain dispatcher (composes 4 shim validators via affected_table)"
```

### §C.14 Task T-B.14 — Un-skip cross-bundle pin tests from T-A.7

**Files:**
- Modify: `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` (remove `@pytest.mark.skip` decorators)

**Acceptance criteria:**
1. Both pin tests un-skipped.
2. Both pass against the now-shipped classifier + validator-shim modules.

- [ ] **Step 1: Remove skip decorators + run.**

```bash
pytest tests/integration/test_phase12_bundle_c_cross_bundle_pin.py -v
git add tests/integration/test_phase12_bundle_c_cross_bundle_pin.py
git commit -m "test(phase12-bundle-c-T-B.14): un-skip cross-bundle pin tests from T-A.7 (classifier + validator shim shipped)"
```

### §C.15 C.B integration commit + ruff + worktree push

After T-B.1 through T-B.14 land:

1. Runs `pytest -q -n auto` and confirms +55-95 new fast tests above C.A baseline.
2. Runs `ruff check swing/` and confirms baseline 18 unchanged.
3. Pushes the worktree branch.

C.B operator-witnessed gate (per §G.2) follows — 3 surfaces verified by the orchestrator before integration merge.

---

## §D Sub-sub-bundle C.C — Auto-correction service + reconciliation flow pivot

**Scope summary (per spec §12.C):**
- NEW `swing/trades/reconciliation_auto_correct.py` with `apply_tier1_correction` (public/owns-tx) + `_apply_tier1_correction_inner` (private/caller-tx) + analogous tier-2/tier-3 pairs + per-(ambiguity_kind, choice_code) handlers.
- NEW exceptions `CallerHeldTransactionError`, `ValidatorRejectedError`, `AlreadySupersededError`.
- Reconciliation flow pivot at `swing/trades/schwab_reconciliation.py:run_schwab_reconciliation` AND `swing/trades/reconciliation.py:run_tos_reconciliation` per OQ-2 disposition.
- Savepoint-per-discrepancy discipline inside the pivot per spec §7.1 LOCK.
- `briefing.md` extension for "Reconciliation status" section.
- Phase 10 banner predicate widening DEFERRED to C.D T-D.10 (banner predicate change ships in C.D so the operator-witnessed gate at C.D S8 can verify count transitions end-to-end).

**Files touched:**
- Create: `swing/trades/reconciliation_auto_correct.py`
- Create: `tests/trades/test_reconciliation_auto_correct_*.py` (multi-file split per service function)
- Modify: `swing/trades/schwab_reconciliation.py` (pivot at `run_schwab_reconciliation`)
- Modify: `swing/trades/reconciliation.py` (pivot at `run_tos_reconciliation`)
- Modify: `swing/rendering/briefing.py` (extend `BriefingInputs` dataclass)
- Modify: `swing/rendering/briefing_md.py` (render "Reconciliation status" section)
- Modify: `swing/pipeline/runner.py` (wire `BriefingInputs.reconciliation_*` from `_step_export`)
- Modify: `tests/trades/test_run_schwab_reconciliation.py` (extend with pivot behavior tests)
- Modify: `tests/trades/test_run_tos_reconciliation.py` (extend with pivot behavior tests)

**Projected fast-test delta:** +65-115 tests (per spec §12.C +70-110 + plan-time additions for failure-mode contract tests + per-(kind, choice_code) handler unit tests).

### §D.1 Task T-C.1 — Service module skeleton + exceptions + transactional discipline scaffolding

**Files:**
- Create: `swing/trades/reconciliation_auto_correct.py`
- Test: `tests/trades/test_reconciliation_auto_correct_transactional_discipline.py`

**Acceptance criteria:**
1. NEW module exports 3 public outer functions (own transactions; reject caller-held) + 3 private inner functions (caller-controlled tx):
   - `apply_tier1_correction(conn, *, discrepancy_id, classification, schwab_api_call_id=None, risk_policy_id=None, correction_reason=None) -> CorrectionResult`
   - `apply_tier2_resolution(conn, *, discrepancy_id, choice_code, operator_custom_payload=None, operator_reason, risk_policy_id=None) -> CorrectionResult`
   - `apply_tier3_override(conn, *, correction_id, operator_truth_value, operator_reason, risk_policy_id=None) -> CorrectionResult`
   - Plus `_apply_tier1_correction_inner(...)`, `_apply_tier2_resolution_inner(...)`, `_apply_tier3_override_inner(...)`.
2. NEW exceptions:
   - `CallerHeldTransactionError(Exception)` — raised by outer functions when `conn.in_transaction is True`. Mirrors `swing/trades/reconciliation.py` Phase 9 Sub-bundle B precedent.
   - `ValidatorRejectedError(Exception)` — raised by inner functions when validator chain returns `(False, reason)`. Carries the rejection reason.
   - `AlreadySupersededError(Exception)` — raised by `_apply_tier3_override_inner` when the target correction row has non-NULL `superseded_by_correction_id` (per OQ-15 disposition).
3. NEW `CorrectionResult` dataclass (per spec §5.2): `correction_id`, `affected_table`, `affected_row_id`, `field_name`, `applied_value_json`, `correction_action`, `notes`.
4. Outer-function transactional discipline (per spec §5.3 LOCK):
   ```python
   if conn.in_transaction:
       raise CallerHeldTransactionError(...)
   conn.execute("BEGIN IMMEDIATE")
   try:
       result = _apply_..._inner(conn, ...)
       conn.commit()
       return result
   except Exception:
       with contextlib.suppress(sqlite3.Error):
           conn.rollback()
       raise
   ```
5. Idempotency contract (per spec §5.3):
   - Inner functions begin by SELECTing the discrepancy's current `resolution`. If already in a terminal state (`auto_corrected_from_schwab`, `operator_resolved_ambiguity`, `operator_overridden`, `manual_override`, `journal_corrected`, `source_treated_canonical`), return an idempotent `CorrectionResult` looked up from existing rows WITHOUT writing a new audit row.
6. Discriminating tests:
   - Caller-held-tx test: opens a tx via `BEGIN`; calls `apply_tier1_correction(conn, ...)`; asserts `CallerHeldTransactionError` raised.
   - Outer-rollback test: monkeypatches the inner function to raise mid-execution; asserts `conn.rollback()` was called; asserts `conn.in_transaction is False` post-call.
   - Idempotency test: applies a tier-1 correction; calls `apply_tier1_correction` a second time on the same discrepancy_id; asserts the second call returns the SAME `correction_id` from the existing row + does NOT write a new audit row (asserted via row-count delta on `reconciliation_corrections`).

- [ ] **Step 1: Write failing test for `CallerHeldTransactionError`.**

```python
# tests/trades/test_reconciliation_auto_correct_transactional_discipline.py
import sqlite3

import pytest

from swing.trades.reconciliation_auto_correct import (
    CallerHeldTransactionError,
    apply_tier1_correction,
)


def test_apply_tier1_correction_rejects_caller_held_transaction(conn):
    conn.execute("BEGIN")
    with pytest.raises(CallerHeldTransactionError):
        apply_tier1_correction(
            conn,
            discrepancy_id=1,
            classification=None,
        )
    conn.rollback()
```

Run + verify FAIL on ImportError.

- [ ] **Step 2: Implement module skeleton with the 3 public + 3 private functions + 3 exceptions + transactional wrappers (no body logic; bodies in T-C.2/3/4).**

- [ ] **Step 3: Implement outer-tx wrapper for each public function.**

```python
def apply_tier1_correction(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    classification,
    schwab_api_call_id: int | None = None,
    risk_policy_id: int | None = None,
    correction_reason: str | None = None,
) -> CorrectionResult:
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "apply_tier1_correction must be called with no open transaction; "
            "compose via _apply_tier1_correction_inner inside an existing tx"
        )
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _apply_tier1_correction_inner(
            conn,
            discrepancy_id=discrepancy_id,
            classification=classification,
            schwab_api_call_id=schwab_api_call_id,
            risk_policy_id=risk_policy_id,
            correction_reason=correction_reason,
        )
        conn.commit()
        return result
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise
```

- [ ] **Step 4: Implement skeleton bodies for inner functions (raise NotImplementedError; populated in T-C.2/3/4).** Each inner skeleton accepts the keyword args from its outer + raises `NotImplementedError(...)`. Composability discipline is set up; logic lands in subsequent tasks.

- [ ] **Step 5: Write the 3 discipline tests + run + commit.**

```bash
pytest tests/trades/test_reconciliation_auto_correct_transactional_discipline.py -v
git add swing/trades/reconciliation_auto_correct.py tests/trades/test_reconciliation_auto_correct_transactional_discipline.py
git commit -m "feat(phase12-bundle-c-T-C.1): auto-correction service module skeleton + 3 exceptions + outer/inner tx discipline"
```

### §D.2 Task T-C.2 — `_apply_tier1_correction_inner` body (the CVGI 41 path)

**Files:**
- Modify: `swing/trades/reconciliation_auto_correct.py`
- Test: `tests/trades/test_apply_tier1_correction.py`

**Acceptance criteria (per spec §5.4 11-step atomic flow):**
1. SELECT discrepancy. If NULL → raise. If `resolution != 'unresolved'` → idempotent return.
2. Re-run validator chain via `default_validator_chain(conn)` partially applied with `affected_table` + `affected_row_id` (per T-B.13 composition pattern). On `(False, reason)`: raise `ValidatorRejectedError(reason)` (caller catches; flow pivot at T-C.5/6 fall through to tier-2 with `validator_rejected`).
3. UPDATE the affected journal table. For CVGI 41 case: `UPDATE fills SET price = ? WHERE fill_id = ?`. Repo helper preferred (`update_fill_field(conn, fill_id, field_name, new_value)` ships as part of T-C.2 if not already extant on `swing/data/repos/fills.py` — writing-plans T-C.2 Step 3.1 verifies; if extant under a different name, reuse).
4. For `affected_table='fills'`, call `_recompute_aggregates(conn, trade_id)` (existing function at `swing/data/repos/fills.py:79`; per spec §5.4 step 6 + §A.9 verified).
5. INSERT `reconciliation_corrections` row via `insert_correction(conn, ...)` from T-A.3. Build the row with:
   - `correction_action='auto_applied'`
   - `correction_choice=None`
   - `affected_table='fills'`, `affected_row_id=<fill_id>`, `field_name='price'`
   - `pre_correction_value_json=json.dumps({field_name: pre_value}, sort_keys=True)`
   - `source_canonical_value_json=json.dumps({field_name: target_value}, sort_keys=True)`
   - `applied_value_json=json.dumps({field_name: target_value}, sort_keys=True)`
   - `applied_at=<utc_now_iso_millisecond>`, `applied_by='auto'`
   - `correction_set_id=None`, `superseded_by_correction_id=None`
   - `risk_policy_id_at_correction=<active_policy_id_OR_caller_supplied>` (per Phase 8 R1 M5 lesson — per-row stamp at write time)
   - `schwab_api_call_id=<caller-supplied>`, `reconciliation_run_id=<discrepancy.run_id>`
   - `correction_reason=<classification.correction_reason OR caller-supplied>`
6. UPDATE `reconciliation_discrepancies SET resolution='auto_corrected_from_schwab', resolution_reason=correction_reason, resolved_at=<now>, resolved_by='auto' WHERE discrepancy_id=?`.
7. Lookup affected review_log rows via cadence-period anchoring (per spec §5.4 step 9 LOCKED SQL):
   - Compute affected fill's `trade_id` → trade's effective close date (`MAX(fill.fill_datetime) FOR action IN ('exit','stop')`) → match against `review_log` rows WHERE `completed_date IS NOT NULL AND period_start <= trade_close_date AND trade_close_date <= period_end`.
   - For each matched review_log row: `UPDATE review_log SET superseded_by_correction_id = <new_correction_id> WHERE review_id = ?` via repo helper.
   - If trade has no close date (still OPEN — CVGI 41 case): 0 rows touched. Walkthrough applies §5.4 step 9 mechanic correctly even when result is empty (per spec §10.1 step 8).
8. UPDATE `fills.reconciliation_status='reconciled_discrepancy_resolved'` on the affected fill (per spec §9.2; uses existing enum).
9. INSERT `trade_events` row with `event_type='reconciliation_auto_correct'` + `payload_json=json.dumps({correction_id, affected_table, affected_row_id, field_name, pre, applied})` WHEN `affected_table='fills' AND <fill>.trade_id IS NOT NULL` (per spec §5.4 step 10 + §9.3 single-event-per-correction discipline). For `affected_table IN ('cash_movements','account_equity_snapshots')`: skip the trade_events emission (no trade attribution).
10. Sandbox short-circuit (per spec §5.9 + §9.7): check `cfg.integrations.schwab.environment == 'sandbox'` at function entry (cfg threaded in via caller — see T-C.2 Step 1 below; outer-function signature MAY need a `*, environment: str | None = None` keyword to thread per Phase 11 sandbox-gating precedent OR a getter that reads cfg from a thread-local. Spec §5.9 does NOT specify the threading mechanic; writing-plans LOCK: outer function accepts `environment: str | None = None` keyword; when `environment == 'sandbox'`: skip all domain writes (steps 3-9); emit WARNING log; return `CorrectionResult(correction_id=None, ..., notes='sandbox: domain write short-circuited')`. The discrepancy stays `unresolved`. Audit-row writes that were already emitted by upstream classifier (e.g., the Schwab API call audit row) are preserved per shipped gating discipline.
11. Return `CorrectionResult` populated with the new `correction_id` + other fields.

- [ ] **Step 1: Write failing test for CVGI 41 tier-1 happy path.**

```python
# tests/trades/test_apply_tier1_correction.py
def test_apply_tier1_correction_cvgi_41_happy_path(
    conn_with_planted_cvgi_discrepancy_41, planted_cvgi_fill_id_9
):
    conn = conn_with_planted_cvgi_discrepancy_41
    classification = ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="entry_price_mismatch on (CVGI, fill_id=9): journal $5.23 vs Schwab $5.30",
        candidate_choices=None,
    )
    result = apply_tier1_correction(
        conn,
        discrepancy_id=41,
        classification=classification,
        risk_policy_id=5,
        environment="production",
    )
    # 1. fills.price updated.
    fill = conn.execute("SELECT price FROM fills WHERE fill_id = 9").fetchone()
    assert fill[0] == 5.30
    # 2. trades.current_avg_cost recomputed (single-entry-fill CVGI trade).
    trade = conn.execute(
        "SELECT current_avg_cost FROM trades WHERE id = ?",
        (planted_cvgi_fill_id_9.trade_id,),
    ).fetchone()
    assert trade[0] == 5.30
    # 3. reconciliation_corrections row written.
    rc = conn.execute(
        "SELECT correction_action, applied_value_json FROM reconciliation_corrections "
        "WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert rc[0] == "auto_applied"
    assert json.loads(rc[1]) == {"price": 5.30}
    # 4. Discrepancy resolution updated.
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE discrepancy_id = 41"
    ).fetchone()
    assert d[0] == "auto_corrected_from_schwab"
    # 5. trade_events row emitted.
    te = conn.execute(
        "SELECT event_type FROM trade_events WHERE trade_id = ? ORDER BY id DESC LIMIT 1",
        (planted_cvgi_fill_id_9.trade_id,),
    ).fetchone()
    assert te[0] == "reconciliation_auto_correct"
    # 6. fills.reconciliation_status flipped.
    rs = conn.execute(
        "SELECT reconciliation_status FROM fills WHERE fill_id = 9"
    ).fetchone()
    assert rs[0] == "reconciled_discrepancy_resolved"
```

Run + verify FAIL.

- [ ] **Step 2: Implement `_apply_tier1_correction_inner` body per spec §5.4 11-step flow.**

- [ ] **Step 3: Write validator-rejected re-raise test.**

```python
def test_apply_tier1_correction_raises_validator_rejected(
    conn_with_planted_cvgi_discrepancy_41
):
    conn = conn_with_planted_cvgi_discrepancy_41
    # Validator chain that always rejects:
    classification = ClassificationResult(
        tier=1,
        ambiguity_kind=None,
        correction_target={"price": -1.0},  # rejected by validate_fill_correction
        correction_reason="...",
        candidate_choices=None,
    )
    with pytest.raises(ValidatorRejectedError) as excinfo:
        apply_tier1_correction(
            conn,
            discrepancy_id=41,
            classification=classification,
            environment="production",
        )
    assert "price" in str(excinfo.value).lower()
    # After raise: discrepancy stays unresolved + no correction row written.
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE discrepancy_id = 41"
    ).fetchone()
    assert d[0] == "unresolved"
    rc_count = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections WHERE discrepancy_id = 41"
    ).fetchone()[0]
    assert rc_count == 0
```

- [ ] **Step 4: Write sandbox short-circuit test.**

```python
def test_apply_tier1_correction_sandbox_short_circuit(
    conn_with_planted_cvgi_discrepancy_41, caplog
):
    conn = conn_with_planted_cvgi_discrepancy_41
    classification = ClassificationResult(tier=1, ambiguity_kind=None,
        correction_target={"price": 5.30},
        correction_reason="...", candidate_choices=None,
    )
    result = apply_tier1_correction(
        conn, discrepancy_id=41, classification=classification,
        environment="sandbox",
    )
    assert result.correction_id is None
    assert "sandbox" in result.notes.lower()
    # No domain writes happened:
    fill = conn.execute("SELECT price FROM fills WHERE fill_id = 9").fetchone()
    assert fill[0] == 5.23  # unchanged
    # WARNING log emitted:
    assert any("sandbox" in r.message.lower() and r.levelname == "WARNING" for r in caplog.records)
```

- [ ] **Step 5: Write idempotency test.**

Calls `apply_tier1_correction` twice on the same discrepancy_id with the same classification; asserts the second call returns the same `correction_id`; asserts row count on `reconciliation_corrections` is exactly 1 (not 2).

- [ ] **Step 6: Write review_log supersede-pointer test (closed-reviewed-trade scenario).**

Plants a closed trade with `entry_date='2026-01-01'`, exit fill at `2026-01-15`, and a completed `review_log` row for `period_start='2026-01-01', period_end='2026-01-31'`. Plants a discrepancy on the entry fill. Calls `apply_tier1_correction`. Asserts `review_log.superseded_by_correction_id` is now set to the new correction_id.

- [ ] **Step 7: Commit.**

```bash
pytest tests/trades/test_apply_tier1_correction.py -v
git add swing/trades/reconciliation_auto_correct.py tests/trades/test_apply_tier1_correction.py
git commit -m "feat(phase12-bundle-c-T-C.2): _apply_tier1_correction_inner — 11-step atomic flow including review_log supersede + sandbox short-circuit"
```

### §D.3 Task T-C.3 — `_apply_tier2_resolution_inner` body + per-(kind, choice_code) handlers

**Files:**
- Modify: `swing/trades/reconciliation_auto_correct.py`
- Test: `tests/trades/test_apply_tier2_resolution.py`
- Test: `tests/trades/test_apply_tier2_handlers.py`

**Acceptance criteria (per spec §5.6 + §6.2.1 per-(kind, choice_code) menu):**
1. `_apply_tier2_resolution_inner` body:
   - SELECT discrepancy; verify `resolution='pending_ambiguity_resolution'`.
   - Verify `(discrepancy.ambiguity_kind, choice_code)` is a registered handler key. If not, raise `ValueError("incompatible choice_code for ambiguity_kind ...")`.
   - Dispatch to per-pair handler. Each handler builds an explicit `ClassificationResult`-equivalent struct + invokes the same step-3-through-11 sequence as `_apply_tier1_correction_inner` (refactor common steps to a private helper `_apply_correction_steps_3_to_11(conn, ...)` to avoid duplication).
   - `correction_action='operator_resolved_ambiguity'`, `applied_by='operator'`, `correction_choice=<choice_code>`.
2. Handler registry (dict of `(ambiguity_kind, choice_code) → handler_fn`) per spec §6.2.1 table — 18 entries (4 + 3 + 3 + 2 + 2 + 2 + 2 = 18 (kind, choice) pairs across the 7 ambiguity_kinds). Each handler is a small focused function in the module.
3. Per spec §6.2.1 + Codex R5 Major #2 LOCK: each handler enforces its OWN `--custom-value` requirement via the per-choice payload contract. Handlers that REQUIRE `--custom-value` (per the §6.2.1 Description column "REQUIRES `--custom-value`" rows) raise `ValueError("--custom-value required for choice <code>")` if `operator_custom_payload is None OR empty`. Handlers that do NOT require it (`keep_journal_as_is`, `mark_unmatched`, `acknowledge`) accept `operator_custom_payload=None`.
4. Per spec §5.6 step 4 — split-into-partials handler is the most complex:
   - Validates `operator_custom_payload` is a list of dicts each with `qty`, `price`, `fill_datetime` keys; quantities sum to original fill quantity within tolerance; all prices > 0.
   - DELETEs the consolidated journal fill via repo helper.
   - INSERTs N partial fills via the existing `insert_fill_with_event(conn, fill, recompute=False)` path with `recompute=False` so `_recompute_aggregates` fires ONCE at the end.
   - Calls `_recompute_aggregates` once.
   - Writes N + 1 `reconciliation_corrections` rows bundled under one `correction_set_id`:
     - 1 deletion-sentinel row with `field_name='__delete__'`, `applied_value_json=null`.
     - N insertion-sentinel rows with `field_name='__insert__'`, `applied_value_json=<full inserted fill payload>`.
   - `correction_set_id` mechanic (per OQ-6 disposition + spec §3.1.1): INSERT anchor (deletion) row → SELECT its `correction_id` → UPDATE anchor's `correction_set_id` to itself → INSERT remaining N rows with `correction_set_id` = anchor's `correction_id`.
5. Per spec §6.2.1 + Codex R1 Critical #1 LOCK — EVERY tier-2 resolution writes a `reconciliation_corrections` audit row, including "no journal mutation" choices (`keep_journal_as_is`, `mark_unmatched`, `acknowledge`). For these choices: `applied_value_json == pre_correction_value_json`; `affected_table` is still the underlying journal table for forensic-trail attribution; `field_name='__no_mutation__'` sentinel (per OQ-9 disposition pattern) — banked V2.1 §VII.F: writing-plans introduces a new sentinel `'__no_mutation__'` beyond the spec's enumerated `'__delete__'`/`'__insert__'`; spec §3.1.1 mentions only the 2 deletion/insertion sentinels but the no-mutation tier-2 outcomes need their own audit-row marker; clarified at §I.14 V2.1 amendment candidate (writing-plans-introduced).
6. UPDATE `reconciliation_discrepancies.resolution='operator_resolved_ambiguity'`.
7. UPDATE `review_log.superseded_by_correction_id` per the same cadence-period anchoring as T-C.2 (when applicable).
8. INSERT `trade_events` row PER `reconciliation_corrections` row when `affected_table='fills'` (per spec §9.3). For split-into-partials: N trade_events rows emitted (one per resulting fill); the deletion sentinel does NOT emit a trade_events row (deletion is not an `event_type='reconciliation_auto_correct'` direct mapping V1).

- [ ] **Step 1: Write failing test for `consolidate_using_operator_vwap` handler (DHC 39 path).**

```python
# tests/trades/test_apply_tier2_resolution.py
def test_apply_tier2_resolution_consolidate_using_operator_vwap(
    conn_with_dhc_39_pending_ambiguity_multi_partial
):
    conn = conn_with_dhc_39_pending_ambiguity_multi_partial
    result = apply_tier2_resolution(
        conn,
        discrepancy_id=39,
        choice_code="consolidate_using_operator_vwap",
        operator_custom_payload={"price": 7.58},
        operator_reason="Schwab broker statement shows 2 partial executions; operator-computed VWAP",
        risk_policy_id=5,
    )
    # fills.price updated to operator-supplied VWAP:
    fill = conn.execute("SELECT price FROM fills WHERE fill_id = 2").fetchone()
    assert fill[0] == 7.58
    # Correction row written with correction_action=operator_resolved_ambiguity:
    rc = conn.execute(
        "SELECT correction_action, correction_choice, applied_by FROM reconciliation_corrections "
        "WHERE discrepancy_id = 39"
    ).fetchone()
    assert rc == ("operator_resolved_ambiguity", "consolidate_using_operator_vwap", "operator")
    # Discrepancy resolution updated:
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE discrepancy_id = 39"
    ).fetchone()
    assert d[0] == "operator_resolved_ambiguity"
```

- [ ] **Step 2: Implement `_apply_tier2_resolution_inner` body + handler registry skeleton.**

- [ ] **Step 3: Implement 18 per-(kind, choice_code) handlers** — each ~10-30 lines. Refactor common payload-validation logic to private helpers.

Handler registry shape:
```python
_TIER2_HANDLERS: dict[tuple[str, str], Callable[..., CorrectionResult]] = {
    ("multi_partial_vs_consolidated", "keep_journal_as_is"): _handle_keep_journal_as_is,
    ("multi_partial_vs_consolidated", "consolidate_using_operator_vwap"): _handle_consolidate_using_operator_vwap,
    ("multi_partial_vs_consolidated", "split_into_partials"): _handle_split_into_partials,
    ("multi_partial_vs_consolidated", "custom"): _handle_custom_multi_partial,
    ("multi_match_within_window", "pick_schwab_record_<N>"): _handle_pick_schwab_record_N,  # parameterized; N parsed from suffix
    ("multi_match_within_window", "mark_unmatched"): _handle_mark_unmatched,
    ("multi_match_within_window", "custom"): _handle_custom_multi_match,
    ("unknown_schwab_subtype", "acknowledge"): _handle_acknowledge,
    ("unknown_schwab_subtype", "operator_truth"): _handle_operator_truth,
    ("unknown_schwab_subtype", "custom"): _handle_custom_unknown,
    ("field_shape_incompatible", "acknowledge"): _handle_acknowledge,
    ("field_shape_incompatible", "custom"): _handle_custom_field_shape,
    ("schwab_returned_no_match", "mark_unmatched"): _handle_mark_unmatched,
    ("schwab_returned_no_match", "operator_truth"): _handle_operator_truth,
    ("validator_rejected", "acknowledge"): _handle_acknowledge,
    ("validator_rejected", "operator_alternative"): _handle_operator_alternative,
    ("unsupported", "operator_truth"): _handle_operator_truth,
    ("unsupported", "acknowledge"): _handle_acknowledge,
}
```

**Note on `pick_schwab_record_<N>`:** the choice code is parametric. CLI parses `pick_schwab_record_3` → matches the prefix `pick_schwab_record_` → dispatches to `_handle_pick_schwab_record_N` with N=3 extracted. Handler validates N is a valid index into the candidate list from the discrepancy.

- [ ] **Step 4: Write split-into-partials test (DHC 39 alternate path; spec §10.2 "Alternate path").**

```python
def test_apply_tier2_resolution_split_into_partials(
    conn_with_dhc_39_pending_ambiguity_multi_partial
):
    conn = conn_with_dhc_39_pending_ambiguity_multi_partial
    payload = [
        {"qty": 20, "price": 7.57, "fill_datetime": "2026-04-27T14:23:00"},
        {"qty": 19, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
    ]
    result = apply_tier2_resolution(
        conn,
        discrepancy_id=39,
        choice_code="split_into_partials",
        operator_custom_payload=payload,
        operator_reason="...",
    )
    # Original fill_id=2 deleted; 2 new fills inserted.
    fills = conn.execute(
        "SELECT quantity, price FROM fills WHERE trade_id = ? AND action = 'entry' "
        "ORDER BY fill_datetime",
        (dhc_trade_id,),
    ).fetchall()
    assert len(fills) == 2
    assert fills[0] == (20.0, 7.57)
    assert fills[1] == (19.0, 7.59)
    # 3 correction rows in same correction_set:
    rcs = conn.execute(
        "SELECT correction_id, correction_set_id, field_name FROM reconciliation_corrections "
        "WHERE discrepancy_id = 39 ORDER BY correction_id",
    ).fetchall()
    assert len(rcs) == 3
    anchor_id = rcs[0][0]
    assert rcs[0][1] == anchor_id  # anchor row self-references
    assert all(r[1] == anchor_id for r in rcs)  # all share the set
    assert rcs[0][2] == "__delete__"
    assert rcs[1][2] == "__insert__"
    assert rcs[2][2] == "__insert__"
```

- [ ] **Step 5: Write payload-required rejection test.**

```python
def test_apply_tier2_resolution_rejects_missing_custom_value_when_required(
    conn_with_dhc_39_pending_ambiguity_multi_partial
):
    conn = conn_with_dhc_39_pending_ambiguity_multi_partial
    with pytest.raises(ValueError) as excinfo:
        apply_tier2_resolution(
            conn,
            discrepancy_id=39,
            choice_code="consolidate_using_operator_vwap",
            operator_custom_payload=None,  # missing!
            operator_reason="...",
        )
    assert "--custom-value" in str(excinfo.value).lower() or "operator_custom_payload" in str(excinfo.value).lower()
```

- [ ] **Step 6: Write keep_journal_as_is no-mutation test.**

```python
def test_apply_tier2_resolution_keep_journal_as_is_writes_audit_no_mutation(
    conn_with_dhc_39_pending_ambiguity_multi_partial
):
    conn = conn_with_dhc_39_pending_ambiguity_multi_partial
    pre_price = conn.execute("SELECT price FROM fills WHERE fill_id = 2").fetchone()[0]
    result = apply_tier2_resolution(
        conn,
        discrepancy_id=39,
        choice_code="keep_journal_as_is",
        operator_custom_payload=None,
        operator_reason="aggregation intentional",
    )
    # fills.price unchanged.
    post_price = conn.execute("SELECT price FROM fills WHERE fill_id = 2").fetchone()[0]
    assert pre_price == post_price
    # Audit row written:
    rc = conn.execute(
        "SELECT correction_action, correction_choice, applied_value_json, pre_correction_value_json "
        "FROM reconciliation_corrections WHERE discrepancy_id = 39",
    ).fetchone()
    assert rc[0] == "operator_resolved_ambiguity"
    assert rc[1] == "keep_journal_as_is"
    # applied_value == pre_correction_value (no mutation):
    assert rc[2] == rc[3]
```

- [ ] **Step 7: Write incompatible-choice-code rejection test.**

```python
def test_apply_tier2_resolution_rejects_incompatible_choice_code(
    conn_with_dhc_39_pending_ambiguity_multi_partial
):
    conn = conn_with_dhc_39_pending_ambiguity_multi_partial
    # multi_partial_vs_consolidated discrepancy + tries pick_schwab_record_1 (only valid for multi_match_within_window):
    with pytest.raises(ValueError) as excinfo:
        apply_tier2_resolution(
            conn,
            discrepancy_id=39,
            choice_code="pick_schwab_record_1",
            operator_reason="...",
        )
    assert "incompatible" in str(excinfo.value).lower() or "ambiguity_kind" in str(excinfo.value).lower()
```

- [ ] **Step 8: Commit.**

```bash
pytest tests/trades/test_apply_tier2_resolution.py tests/trades/test_apply_tier2_handlers.py -v
git add swing/trades/reconciliation_auto_correct.py tests/trades/test_apply_tier2_resolution.py tests/trades/test_apply_tier2_handlers.py
git commit -m "feat(phase12-bundle-c-T-C.3): _apply_tier2_resolution_inner + 18 per-(kind,choice_code) handlers + correction_set_id discipline for split-into-partials"
```

### §D.4 Task T-C.4 — `_apply_tier3_override_inner` body

**Files:**
- Modify: `swing/trades/reconciliation_auto_correct.py`
- Test: `tests/trades/test_apply_tier3_override.py`

**Acceptance criteria (per spec §5.7 10-step flow + OQ-15 disposition):**
1. SELECT the target `reconciliation_corrections` row by `correction_id`.
2. Verify it's the current row in its chain: `superseded_by_correction_id IS NULL`. If NOT, raise `AlreadySupersededError(f"correction_id={correction_id} is already superseded by {row.superseded_by_correction_id}; override the current chain head")`.
3. INSERT NEW `reconciliation_corrections` row with `correction_action='operator_overridden'`, `applied_by='operator'`, `operator_truth_value_json=json.dumps(operator_truth_value)`, `pre_correction_value_json=<prior row's applied_value_json>`, `applied_value_json=<operator_truth value>`.
4. UPDATE prior row's `superseded_by_correction_id` = new row's `correction_id`.
5. UPDATE the affected journal table to the operator-truth value (UPDATE only; no REPLACE).
6. `_recompute_aggregates` if `affected_table='fills'`.
7. UPDATE `reconciliation_discrepancies.resolution='operator_overridden'`.
8. UPDATE `review_log.superseded_by_correction_id` for affected review rows (same logic as T-C.2 step 9).
9. Emit `trade_events` row (per spec §3.5; one event per correction row that touched a fill on a trade).
10. Validator chain re-run on the operator-truth value (per defense-in-depth — operator MAY supply a value that violates invariants; e.g., `quantity < 0`). On rejection: raise `ValidatorRejectedError(reason)`; outer-tx rolls back. **NOTE:** spec §5.7 doesn't explicitly enumerate validator-re-run for tier-3 (step 10 spec §5.7); writing-plans LOCK: tier-3 ALSO runs validator chain before applying — operator's "ground truth" must still pass schema invariants. Banked as V2.1 §VII.F amendment candidate §I.15 (spec §5.7 explicit step-by-step validator inclusion).

- [ ] **Step 1: Write failing AlreadySupersededError test.**

```python
def test_apply_tier3_override_rejects_already_superseded(conn_with_planted_chain):
    conn = conn_with_planted_chain  # tier-1 row #1, tier-3 row #2 already superseded #1
    with pytest.raises(AlreadySupersededError):
        apply_tier3_override(
            conn,
            correction_id=1,  # already superseded by #2
            operator_truth_value={"price": 5.40},
            operator_reason="...",
        )
```

- [ ] **Step 2: Implement `_apply_tier3_override_inner` body per 10-step flow.**

- [ ] **Step 3: Write happy-path test (override CVGI 41's tier-1 correction).**

```python
def test_apply_tier3_override_chains_correctly(conn_with_applied_cvgi_tier1):
    conn = conn_with_applied_cvgi_tier1  # tier-1 correction #1 already applied
    tier1_correction_id = 1
    result = apply_tier3_override(
        conn,
        correction_id=tier1_correction_id,
        operator_truth_value={"price": 5.25},  # operator says Schwab was actually wrong
        operator_reason="Verified with broker statement: actual fill was $5.25",
    )
    # New correction row #2 created with chained pointer:
    new_row = conn.execute(
        "SELECT correction_action, pre_correction_value_json, applied_value_json, operator_truth_value_json "
        "FROM reconciliation_corrections WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert new_row[0] == "operator_overridden"
    assert json.loads(new_row[1]) == {"price": 5.30}  # prior applied
    assert json.loads(new_row[2]) == {"price": 5.25}
    assert json.loads(new_row[3]) == {"price": 5.25}
    # Prior row #1's superseded_by_correction_id points to new row:
    prior = conn.execute(
        "SELECT superseded_by_correction_id FROM reconciliation_corrections WHERE correction_id = 1"
    ).fetchone()
    assert prior[0] == result.correction_id
    # fills.price reverted to operator-truth:
    fill = conn.execute("SELECT price FROM fills WHERE fill_id = 9").fetchone()
    assert fill[0] == 5.25
    # Discrepancy resolution:
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies WHERE discrepancy_id = 41"
    ).fetchone()
    assert d[0] == "operator_overridden"
```

- [ ] **Step 4: Write validator-rejected on operator-truth test.**

```python
def test_apply_tier3_override_runs_validator_chain_on_operator_truth(
    conn_with_applied_cvgi_tier1
):
    with pytest.raises(ValidatorRejectedError):
        apply_tier3_override(
            conn_with_applied_cvgi_tier1,
            correction_id=1,
            operator_truth_value={"price": -1.0},  # invalid
            operator_reason="...",
        )
```

- [ ] **Step 5: Commit.**

```bash
git add swing/trades/reconciliation_auto_correct.py tests/trades/test_apply_tier3_override.py
git commit -m "feat(phase12-bundle-c-T-C.4): _apply_tier3_override_inner — chain mechanic + AlreadySupersededError + validator re-run on operator-truth"
```

### §D.5 Task T-C.5 — Reconciliation flow pivot at `run_schwab_reconciliation`

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py` (extend `run_schwab_reconciliation` with Step 2 classify+dispatch loop)
- Modify: `tests/trades/test_run_schwab_reconciliation.py` (extend with pivot behavior tests)

**Acceptance criteria (per spec §7.1 LOCKED savepoint discipline):**
1. After the existing emit-discrepancies loop completes (Step 1), iterate the newly-emitted discrepancies (Step 2):
   ```python
   for disc in newly_emitted_discrepancies:
       sp_name = f"correction_sp_{disc.discrepancy_id}"
       conn.execute(f"SAVEPOINT {sp_name}")
       try:
           classification = classify_discrepancy(
               disc,
               source_payload=_extract_source_payload(disc, schwab_orders),
               journal_row=_fetch_journal_row(conn, disc),
               validator_chain=functools.partial(
                   default_validator_chain(conn),
                   affected_table=_resolve_affected_table(disc),
                   affected_row_id=_resolve_affected_row_id(disc),
               ),
           )
           if classification.tier == 1:
               try:
                   _apply_tier1_correction_inner(
                       conn,
                       discrepancy_id=disc.discrepancy_id,
                       classification=classification,
                       schwab_api_call_id=schwab_api_call_id,
                       risk_policy_id=_get_active_risk_policy_id(conn),
                       environment=environment,
                   )
                   conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                   counters["tier1_applied"] += 1
               except ValidatorRejectedError as e:
                   conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                   conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                   # Fall through to tier-2 stamp:
                   conn.execute(
                       "UPDATE reconciliation_discrepancies SET "
                       "resolution='pending_ambiguity_resolution', "
                       "ambiguity_kind='validator_rejected', "
                       "resolution_reason=? WHERE discrepancy_id=?",
                       (str(e), disc.discrepancy_id),
                   )
                   counters["tier2_pending"] += 1
           else:  # tier == 2
               conn.execute(
                   "UPDATE reconciliation_discrepancies SET "
                   "resolution='pending_ambiguity_resolution', "
                   "ambiguity_kind=?, resolution_reason=? WHERE discrepancy_id=?",
                   (classification.ambiguity_kind, classification.correction_reason, disc.discrepancy_id),
               )
               conn.execute(f"RELEASE SAVEPOINT {sp_name}")
               counters["tier2_pending"] += 1
       except Exception as e:  # noqa: BLE001 — graceful degradation
           conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
           conn.execute(f"RELEASE SAVEPOINT {sp_name}")
           logger.warning(
               "classifier or apply exception for discrepancy %d: %s",
               disc.discrepancy_id, e,
           )
           counters["tier_errored"] += 1
   ```
2. After the loop: UPDATE `reconciliation_runs.summary_json` with the 3 counters (`tier1_applied_count`, `tier2_pending_count`, `tier3_overridden_count` — last is always 0 here since tier-3 is operator-initiated post-run).
3. Sandbox short-circuit: when `environment='sandbox'`, the dispatcher still iterates + classifies BUT calls `_apply_tier1_correction_inner` with `environment='sandbox'` which returns no-op-result; counters reflect classification outcomes but `tier1_applied_count` stays 0 since the inner short-circuits. Discrepancy stays `unresolved`.
4. Failure-mode contract: pipeline NEVER raises out of the flow pivot. Classifier-or-apply exceptions are caught + logged WARNING + savepoint rolled back. Outer transaction continues.
5. Discriminating tests:
   - Simulated run with 3 planted discrepancies (1 CVGI-shape tier-1 + 1 DHC-shape tier-2-pending + 1 deliberately-rigged validator failure) exercises the full pivot end-to-end.
   - Asserts post-run state: discrepancy 1 → `auto_corrected_from_schwab`; discrepancy 2 → `pending_ambiguity_resolution`; discrepancy 3 → `pending_ambiguity_resolution` with `ambiguity_kind='validator_rejected'`.
   - Asserts `summary_json.tier1_applied_count == 1`, `tier2_pending_count == 2`.
   - Asserts `conn.in_transaction is True` throughout the pivot loop (outer tx never closed mid-loop).
6. Cross-bundle integration test: mocks `_construct_pipeline_schwab_client` + asserts cascade-resolved Schwab credentials are threaded through (per spec §A.3 Phase 12 Sub-bundle A T-A.3 gap pre-emption pattern; brief §0.4 lesson #12 inheritance).

- [ ] **Step 1: Write failing test for tier-1 auto-apply happens inside run.**

```python
# tests/trades/test_run_schwab_reconciliation_pivot.py
def test_run_schwab_reconciliation_applies_tier1_inline(
    conn_with_planted_cvgi_trade, schwab_orders_fixture_cvgi
):
    conn = conn_with_planted_cvgi_trade
    run = run_schwab_reconciliation(
        conn,
        account_hash="...",
        period_start="2026-04-27",
        period_end="2026-05-01",
        schwab_orders=schwab_orders_fixture_cvgi,
        schwab_transactions=[],
        schwab_account=...,
        environment="production",
    )
    # Discrepancy was emitted AND auto-corrected in the same run:
    d = conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'entry_price_mismatch'",
        (run.run_id,),
    ).fetchone()
    assert d[0] == "auto_corrected_from_schwab"
    # summary_json counters:
    summary = json.loads(run.summary_json)
    assert summary["tier1_applied_count"] == 1
```

- [ ] **Step 2: Implement Step 2 classify+dispatch loop in `run_schwab_reconciliation`.**

- [ ] **Step 3: Write savepoint-isolation test (rigged exception).**

```python
def test_run_schwab_reconciliation_savepoint_isolates_per_discrepancy_failure(
    conn_with_3_planted_discrepancies, monkeypatch
):
    conn = conn_with_3_planted_discrepancies
    # Rig the 2nd classification to raise:
    original_classify = classify_discrepancy
    call_count = [0]
    def rigged(disc, **kw):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("rigged failure")
        return original_classify(disc, **kw)
    monkeypatch.setattr("swing.trades.schwab_reconciliation.classify_discrepancy", rigged)
    run = run_schwab_reconciliation(conn, ...)
    # Discrepancy 1 + 3 are dispositioned; #2 stays unresolved.
    states = conn.execute(
        "SELECT discrepancy_id, resolution FROM reconciliation_discrepancies "
        "WHERE run_id = ? ORDER BY discrepancy_id",
        (run.run_id,),
    ).fetchall()
    assert states[0][1] != "unresolved"
    assert states[1][1] == "unresolved"  # rigged failure
    assert states[2][1] != "unresolved"
    # Outer run still committed:
    r = conn.execute(
        "SELECT state FROM reconciliation_runs WHERE run_id = ?",
        (run.run_id,),
    ).fetchone()
    assert r[0] == "completed"
```

- [ ] **Step 4: Write sandbox short-circuit test.**

```python
def test_run_schwab_reconciliation_sandbox_short_circuits_apply(
    conn_with_planted_cvgi_trade, schwab_orders_fixture_cvgi
):
    run = run_schwab_reconciliation(
        ..., environment="sandbox",
    )
    # Discrepancy emitted; tier-1 NOT applied:
    d = conn.execute(...).fetchone()
    assert d[0] == "unresolved"
    summary = json.loads(run.summary_json)
    assert summary.get("tier1_applied_count", 0) == 0
```

- [ ] **Step 5: Write Sub-bundle A T-A.3 implementer-gap pre-emption test.**

Mocks `_construct_pipeline_schwab_client` to return a MagicMock recording arg values; runs the reconciliation; asserts the mock was called with the cascade-resolved Schwab credentials (Phase 12 Sub-bundle A + B credential cascade preserved end-to-end through Sub-bundle C's new flow pivot).

- [ ] **Step 6: Commit.**

```bash
pytest tests/trades/test_run_schwab_reconciliation_pivot.py -v
git add swing/trades/schwab_reconciliation.py tests/trades/test_run_schwab_reconciliation_pivot.py
git commit -m "feat(phase12-bundle-c-T-C.5): run_schwab_reconciliation flow pivot — savepoint-per-discrepancy + classify+dispatch + counters in summary_json"
```

### §D.6 Task T-C.6 — Reconciliation flow pivot at `run_tos_reconciliation`

**Files:**
- Modify: `swing/trades/reconciliation.py` (extend `run_tos_reconciliation` with parallel Step 2 loop)
- Test: `tests/trades/test_run_tos_reconciliation_pivot.py`

**Acceptance criteria:** mirrors T-C.5 verbatim with TOS-CSV source semantics per OQ-2 disposition (PIVOT BOTH).

Per spec §7.2 caveat: TOS CSV is operator-uploaded; trust premise differs from Schwab API. V1 plan-author lock per OQ-2: pivot logic is identical; per-discrepancy-type sub-classifiers handle source-specific nuance internally. The CVGI/DHC/VSAT discriminating examples are all Schwab-side, but TOS-CSV-side tier-1 entry_price_mismatch is no different.

Discriminating test: plants a TOS CSV with 1 entry_price_mismatch + 1 unmatched_open_fill; runs `run_tos_reconciliation`; asserts the entry_price_mismatch is tier-1 applied + the unmatched_open_fill is tier-2 stamped.

- [ ] **Steps 1-6: TDD parallel to T-C.5.**

```bash
git add swing/trades/reconciliation.py tests/trades/test_run_tos_reconciliation_pivot.py
git commit -m "feat(phase12-bundle-c-T-C.6): run_tos_reconciliation flow pivot (mirrors T-C.5 per OQ-2 PIVOT BOTH)"
```

### §D.7 Task T-C.7 — Savepoint discipline regression suite

**Files:**
- Test: `tests/trades/test_savepoint_discipline_reconciliation_pivot.py`

**Acceptance criteria:**
1. Regression test suite specifically for the spec §7.1 LOCKED savepoint discipline (Codex R1 Critical #3 fix; R2 Minor #1 comment fix).
2. Tests:
   - **Savepoint isolation under partial UPDATE failure**: plant a discrepancy whose tier-1 apply would partially-UPDATE journal before raising; verify ROLLBACK TO SAVEPOINT undoes the partial UPDATE before the dispatcher continues.
   - **Outer-tx survives per-discrepancy savepoint rollback**: rig 1 of 3 discrepancies to raise; verify the other 2 land normally + the outer tx commits.
   - **SAVEPOINT name uniqueness**: verify the savepoint name `f"correction_sp_{disc.discrepancy_id}"` is unique per discrepancy_id (since discrepancy_id is autoincrement PK, no two iterations share a savepoint name).
   - **Per-iteration RELEASE always fires**: even on success path, the savepoint is RELEASEd; verify no leaked savepoints accumulate in the outer tx.
3. Tests run against both `run_schwab_reconciliation` AND `run_tos_reconciliation` (since both share the pivot mechanic per T-C.5 + T-C.6).

- [ ] **Steps 1-5: TDD.**

```bash
git add tests/trades/test_savepoint_discipline_reconciliation_pivot.py
git commit -m "test(phase12-bundle-c-T-C.7): savepoint-per-discrepancy discipline regression suite"
```

### §D.8 Task T-C.8 — `BriefingInputs` extension for reconciliation status

**Files:**
- Modify: `swing/rendering/briefing.py` (extend `BriefingInputs` dataclass)
- Modify: every base-layout VM consumer (NONE — `BriefingInputs` is briefing-only; not a base-layout VM; per §A.8)
- Test: `tests/rendering/test_briefing_inputs_reconciliation_extension.py`

**Acceptance criteria:**
1. `BriefingInputs` gains 2 new optional fields:
   - `reconciliation_pending_count: int = 0` — count of `pending_ambiguity_resolution + unresolved-material` discrepancies for the briefing window.
   - `reconciliation_tier1_recent_count: int = 0` — count of `auto_corrected_from_schwab` corrections in the last 7 days.
2. Defaults preserve back-compat with existing call sites.
3. Discriminating test: builds a `BriefingInputs` with each field both set + default; asserts read-back.

- [ ] **Steps 1-3: TDD.**

```bash
git add swing/rendering/briefing.py tests/rendering/test_briefing_inputs_reconciliation_extension.py
git commit -m "feat(phase12-bundle-c-T-C.8): BriefingInputs.reconciliation_pending_count + reconciliation_tier1_recent_count fields"
```

### §D.9 Task T-C.9 — `briefing_md.py` "Reconciliation status" section

**Files:**
- Modify: `swing/rendering/briefing_md.py`
- Test: `tests/rendering/test_briefing_md_reconciliation_section.py`

**Acceptance criteria:**
1. New render branch emits a "Reconciliation status" section per spec §7.5 ONLY when `reconciliation_pending_count > 0` OR `reconciliation_tier1_recent_count > 0` (avoid noise on clean runs).
2. Section format:
   ```
   ## Reconciliation status

   - Tier-1 auto-corrected (last 7 days): N
   - Tier-2 pending operator review: M

   View pending ambiguities: `swing journal discrepancy list-pending-ambiguities`
   Resolve a specific one: `swing journal discrepancy resolve-ambiguity <id> --choice <code> --reason <text>`
   ```
3. Discriminating tests cover the no-render, pending-only, tier1-only, both, and high-count cases.

- [ ] **Steps 1-3: TDD.**

```bash
git add swing/rendering/briefing_md.py tests/rendering/test_briefing_md_reconciliation_section.py
git commit -m "feat(phase12-bundle-c-T-C.9): briefing_md Reconciliation status section (emit when counters non-zero)"
```

### §D.10 Task T-C.10 — Wire `_step_export` to populate the new fields

**Files:**
- Modify: `swing/pipeline/runner.py` (`_step_export` populates `BriefingInputs.reconciliation_*` via queries against `reconciliation_corrections` + `reconciliation_discrepancies`)
- Test: `tests/pipeline/test_step_export_briefing_reconciliation_fields.py`

**Acceptance criteria:**
1. `_step_export` reads the new counters via:
   - `pending_count = count_discrepancies WHERE resolution = 'pending_ambiguity_resolution' AND material_to_review = 1`
   - `tier1_recent = count_corrections WHERE correction_action = 'auto_applied' AND applied_at >= <7d_ago>`
2. Counters threaded into `BriefingInputs(...)` constructor.
3. Discriminating test plants the planned state + asserts the briefing.md output emits the section verbatim.

- [ ] **Steps 1-3: TDD.**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_step_export_briefing_reconciliation_fields.py
git commit -m "feat(phase12-bundle-c-T-C.10): _step_export populates BriefingInputs.reconciliation_* counters"
```

### §D.11 Task T-C.11 — End-to-end integration test (CVGI 41 via full pipeline run)

**Files:**
- Test: `tests/integration/test_phase12_bundle_c_cvgi_41_full_pipeline.py`

**Acceptance criteria:**
1. Slow-marked end-to-end test that:
   - Plants a CVGI-shaped trade + fill in the DB.
   - Plants a mocked Schwab orders response with the divergent price.
   - Invokes the pipeline runner end-to-end (with `--no-finviz-fetch` to avoid hitting Finviz).
   - Asserts the pipeline run includes a reconciliation_run; the reconciliation_run dispositioned the CVGI discrepancy as tier-1; the `fills.price` is now $5.30; the `reconciliation_corrections` row exists; the `trade_events` row exists; `briefing.md` emitted in the run's exports contains the "Reconciliation status" section with `Tier-1 auto-corrected (last 7 days): 1`.
2. Mirrors Phase 11 Sub-bundle D's full-happy-path integration test structure.

- [ ] **Steps 1-3: implement.**

```bash
git add tests/integration/test_phase12_bundle_c_cvgi_41_full_pipeline.py
git commit -m "test(phase12-bundle-c-T-C.11): end-to-end pipeline run integration test (CVGI 41 tier-1 auto-correct)"
```

### §D.12 C.C integration commit + ruff + worktree push

After T-C.1 through T-C.11 land:

1. Runs `pytest -q -n auto` and confirms +65-115 new fast tests above C.B baseline (+ slow integration test in slow suite).
2. Runs `ruff check swing/` and confirms baseline 18 unchanged.
3. Pushes the worktree branch.

C.C operator-witnessed gate (per §G.3) follows — 4 surfaces verified by the orchestrator before integration merge.

---

## §E Sub-sub-bundle C.D — Tier-2 CLI surface + backfill + Phase 10 banner widening

**Scope summary (per spec §12.D + brief §0.3 OQ-7 accept):**
- NEW CLI subcommands under `swing journal discrepancy`: `list-pending-ambiguities`, `show-ambiguity`, `resolve-ambiguity`, `override-correction`.
- NEW CLI subcommand `swing journal reconcile-backfill` per spec §8 (dry-run default; explicit `--apply`; `--ticker` + `--limit` scope flags; `--no-pass-2-on-dry-run` + `--retry-pass-2-failures` per spec §8.2).
- Pass 1 / Pass 2 backfill mechanic per spec §8.4 LOCK.
- Phase 10 dashboard banner predicate widening to include `'pending_ambiguity_resolution'` in the unresolved-material count (per OQ-7 acceptance).
- Cycle-checklist + CLAUDE.md gotcha additions.
- Operator-witnessed gate against production 39 + 40 + 41 (C.D gate is the big one — 10 surfaces per spec §15.5).

**Files touched:**
- Modify: `swing/cli.py` (extend `discrepancy_group` with 4 new subcommands + add new `reconcile-backfill` to `journal_group`)
- Create: `swing/trades/reconciliation_backfill.py` (backfill orchestration helper layered between CLI + service)
- Modify: `swing/metrics/discrepancies.py` (`count_unresolved_material` predicate widening)
- Modify: `swing/data/repos/reconciliation.py` (widen the 2 `list_unresolved_material_*` helpers)
- Modify: `docs/cycle-checklist.md` (operator weekly cadence updates)
- Modify: `CLAUDE.md` (add 4-6 new gotchas — see T-D.13 enumeration)
- Create: `tests/cli/test_discrepancy_resolve_ambiguity_cli.py`
- Create: `tests/cli/test_discrepancy_show_ambiguity_cli.py`
- Create: `tests/cli/test_discrepancy_list_pending_ambiguities_cli.py`
- Create: `tests/cli/test_discrepancy_override_correction_cli.py`
- Create: `tests/cli/test_reconcile_backfill_cli.py`
- Create: `tests/trades/test_reconciliation_backfill.py`
- Create: `tests/metrics/test_discrepancies_predicate_widening.py`

**Projected fast-test delta:** +55-80 tests (per spec §12.D +50-70 + plan-time additions for the 14-VM banner-predicate regression suite + tier-3 override CLI confirmation prompt tests).

### §E.1 Task T-D.1 — `swing journal discrepancy list-pending-ambiguities` CLI

**Files:**
- Modify: `swing/cli.py` (add `@discrepancy_group.command("list-pending-ambiguities")`)
- Test: `tests/cli/test_discrepancy_list_pending_ambiguities_cli.py`

**Acceptance criteria:**
1. NEW subcommand with options:
   - `--ambiguity-kind <kind>` — filter to a specific ambiguity_kind value.
   - `--ticker <ticker>` — filter to a specific ticker.
   - `--limit <N>` — max rows (default 50).
2. SELECT rows from `reconciliation_discrepancies WHERE resolution='pending_ambiguity_resolution'` joined to discriminating context (ticker, trade_id, fill_id, ambiguity_kind).
3. Output table columns: `ID | Run | Type | Trade | Ticker | Field | Ambiguity | Created`.
4. Empty result: prints `"(no pending ambiguities)"` and exits 0.
5. Discriminating tests:
   - Plant 3 pending-ambiguity discrepancies; invoke CLI; assert table shows all 3 + correct ambiguity_kind column.
   - Apply `--ticker DHC` filter; assert only DHC row shown.
   - Apply `--ambiguity-kind multi_partial_vs_consolidated`; assert only matching row shown.
   - With zero pending: assert empty-message line.

- [ ] **Step 1: Write failing CLI test.**

```python
# tests/cli/test_discrepancy_list_pending_ambiguities_cli.py
from click.testing import CliRunner

from swing.cli import main


def test_list_pending_ambiguities_shows_table(planted_3_pending_ambiguities):
    runner = CliRunner()
    result = runner.invoke(main, ["journal", "discrepancy", "list-pending-ambiguities"])
    assert result.exit_code == 0
    assert "DHC" in result.output
    assert "VSAT" in result.output
    assert "multi_partial_vs_consolidated" in result.output


def test_list_pending_ambiguities_filter_by_ticker(planted_3_pending_ambiguities):
    runner = CliRunner()
    result = runner.invoke(main, ["journal", "discrepancy", "list-pending-ambiguities", "--ticker", "DHC"])
    assert result.exit_code == 0
    assert "DHC" in result.output
    assert "VSAT" not in result.output
```

- [ ] **Step 2: Implement CLI subcommand.**

```python
@discrepancy_group.command("list-pending-ambiguities")
@click.option("--ambiguity-kind", type=str, default=None)
@click.option("--ticker", type=str, default=None)
@click.option("--limit", type=int, default=50)
@click.pass_context
def discrepancy_list_pending_ambiguities_cmd(ctx, ambiguity_kind, ticker, limit):
    """List reconciliation discrepancies pending operator ambiguity resolution."""
    from swing.data.db import connect
    cfg = ctx.obj["config"]
    conn = connect(cfg.paths.db_path)
    try:
        where = ["resolution = 'pending_ambiguity_resolution'"]
        params: list = []
        if ambiguity_kind:
            where.append("ambiguity_kind = ?")
            params.append(ambiguity_kind)
        if ticker:
            where.append("ticker = ?")
            params.append(ticker)
        sql = (
            "SELECT discrepancy_id, run_id, discrepancy_type, trade_id, "
            "ticker, field_name, ambiguity_kind, created_at "
            "FROM reconciliation_discrepancies WHERE " + " AND ".join(where) +
            " ORDER BY discrepancy_id DESC LIMIT ?"
        )
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    if not rows:
        click.echo("(no pending ambiguities)")
        return
    # Table output per Phase 9 Sub-bundle B `discrepancy list` style:
    click.echo(f"{'ID':>5} {'Run':>4} {'Type':<22} {'Trade':>6} {'Ticker':<8} {'Field':<14} {'Ambiguity':<32} Created")
    for r in rows:
        ...
```

- [ ] **Steps 3-5: TDD + commit.**

```bash
git add swing/cli.py tests/cli/test_discrepancy_list_pending_ambiguities_cli.py
git commit -m "feat(phase12-bundle-c-T-D.1): swing journal discrepancy list-pending-ambiguities CLI subcommand"
```

### §E.2 Task T-D.2 — `swing journal discrepancy show-ambiguity` CLI

**Files:**
- Modify: `swing/cli.py`
- Create: `swing/trades/reconciliation_ambiguity_choices.py` (per-`ambiguity_kind` choice-menu builder; mirrors §6.2.1 table; reused by `show-ambiguity` + `resolve-ambiguity` validators)
- Test: `tests/cli/test_discrepancy_show_ambiguity_cli.py`
- Test: `tests/trades/test_reconciliation_ambiguity_choices.py`

**Acceptance criteria:**
1. NEW subcommand `show-ambiguity <discrepancy_id>`.
2. Prints discrepancy detail (re-uses the existing `discrepancy_show_cmd` rendering for shared fields) PLUS the per-`ambiguity_kind` candidate choice menu with codes the operator can pass to `resolve-ambiguity`.
3. NEW helper module `swing/trades/reconciliation_ambiguity_choices.py` exposes `get_choice_menu(ambiguity_kind: str) -> list[ChoiceMenuItem]` returning the binding contract from §6.2.1 verbatim. Each `ChoiceMenuItem` carries `code`, `description`, `requires_custom_value: bool`, `recommended: bool` (per OQ-4: `keep_journal_as_is` is `recommended=True` for `multi_partial_vs_consolidated`).
4. For `multi_match_within_window`: choice list includes parametric `pick_schwab_record_<N>` entries (one per actual Schwab candidate in the discrepancy's prebuilt `candidate_choices` payload). The helper looks up the candidate list from the classifier output if available; V1 the candidate list is stored in the discrepancy's `resolution_reason` (since spec §3.2 didn't add a `candidate_choices_json` column to the discrepancy table — verify; if it did add such a column at T-A.1, read from there) — banked V2 candidate §I.13: dedicated `candidate_choices_json` column on `reconciliation_discrepancies` for richer Tier-2 surface.
5. Output format:
   ```
   discrepancy_id: 39
   type: unmatched_open_fill
   ticker: DHC
   trade_id: <trade>, fill_id: 2
   ambiguity_kind: multi_partial_vs_consolidated
   reason: Schwab returned 2 separate orders summing to qty=39; V1 mapper exposes order-level price only — ...

   Candidate choices (pass to resolve-ambiguity via --choice):

   [RECOMMENDED] keep_journal_as_is
     Acknowledge Schwab partial-fill aggregation; no journal mutation.

   consolidate_using_operator_vwap *
     Keep journal consolidated; update price to operator-supplied VWAP.
     * REQUIRES --custom-value '{"price": X.XX}'

   split_into_partials *
     Replace journal fill with N partial fills.
     * REQUIRES --custom-value with execution-level partial-fill payload (list of dicts).

   custom *
     Operator-supplied arbitrary payload.
     * REQUIRES --custom-value (free-form JSON).
   ```
6. Per OQ-4: `keep_journal_as_is` is highlighted as `[RECOMMENDED]` (first in the printed list).
7. Discriminating tests cover each ambiguity_kind's menu output.

- [ ] **Step 1-3: Write helper module + tests.**

```python
# swing/trades/reconciliation_ambiguity_choices.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ChoiceMenuItem:
    code: str
    description: str
    requires_custom_value: bool
    recommended: bool = False


_AMBIGUITY_CHOICE_MENUS: dict[str, list[ChoiceMenuItem]] = {
    "multi_partial_vs_consolidated": [
        ChoiceMenuItem("keep_journal_as_is",
            "Acknowledge Schwab partial-fill aggregation; no journal mutation.",
            requires_custom_value=False, recommended=True),
        ChoiceMenuItem("consolidate_using_operator_vwap",
            "Keep journal consolidated; update price to operator-supplied VWAP. "
            "REQUIRES --custom-value '{\"price\": X.XX}'.",
            requires_custom_value=True),
        ChoiceMenuItem("split_into_partials",
            "Replace journal fill with N partial fills. "
            "REQUIRES --custom-value with execution-level partial-fill payload.",
            requires_custom_value=True),
        ChoiceMenuItem("custom",
            "Operator-supplied arbitrary payload via --custom-value.",
            requires_custom_value=True),
    ],
    "multi_match_within_window": [
        # Parametric pick_schwab_record_<N> built dynamically at show time from
        # the discrepancy's candidate list; static here is mark_unmatched + custom.
        ChoiceMenuItem("mark_unmatched",
            "Journal entry has no corresponding broker record. No mutation.",
            requires_custom_value=False),
        ChoiceMenuItem("custom",
            "Operator-supplied arbitrary payload via --custom-value.",
            requires_custom_value=True),
    ],
    "unknown_schwab_subtype": [
        ChoiceMenuItem("acknowledge",
            "Acknowledge + log for V2 code update. No mutation.",
            requires_custom_value=False),
        ChoiceMenuItem("operator_truth",
            "Operator-supplies real journal field values. REQUIRES --custom-value.",
            requires_custom_value=True),
        ChoiceMenuItem("custom",
            "Operator-custom transformation. REQUIRES --custom-value.",
            requires_custom_value=True),
    ],
    "field_shape_incompatible": [
        ChoiceMenuItem("acknowledge",
            "Acknowledge + log. No mutation.",
            requires_custom_value=False),
        ChoiceMenuItem("custom",
            "Operator-custom transformation. REQUIRES --custom-value.",
            requires_custom_value=True),
    ],
    "schwab_returned_no_match": [
        ChoiceMenuItem("mark_unmatched",
            "Schwab has no record; journal stays as-is. No mutation.",
            requires_custom_value=False),
        ChoiceMenuItem("operator_truth",
            "Operator supplies real values from off-Schwab source. REQUIRES --custom-value.",
            requires_custom_value=True),
    ],
    "validator_rejected": [
        ChoiceMenuItem("acknowledge",
            "Correction would violate invariants; leave divergence as-is. No mutation.",
            requires_custom_value=False),
        ChoiceMenuItem("operator_alternative",
            "Operator-supplied alternative value that passes validators. REQUIRES --custom-value.",
            requires_custom_value=True),
    ],
    "unsupported": [
        ChoiceMenuItem("operator_truth",
            "Operator-custom resolution. REQUIRES --custom-value.",
            requires_custom_value=True),
        ChoiceMenuItem("acknowledge",
            "Leave journal as-is. No mutation.",
            requires_custom_value=False),
    ],
}


def get_choice_menu(ambiguity_kind: str) -> list[ChoiceMenuItem]:
    return list(_AMBIGUITY_CHOICE_MENUS.get(ambiguity_kind, []))
```

Helper-module test asserts the menu shape for each of the 7 ambiguity_kinds matches the §6.2.1 table verbatim (test fixtures encode the spec table as constants; assertion is dict-vs-dict equality).

- [ ] **Step 4: Implement CLI subcommand using the helper.**

- [ ] **Steps 5-7: TDD + commit.**

```bash
git add swing/cli.py swing/trades/reconciliation_ambiguity_choices.py tests/cli/test_discrepancy_show_ambiguity_cli.py tests/trades/test_reconciliation_ambiguity_choices.py
git commit -m "feat(phase12-bundle-c-T-D.2): show-ambiguity CLI + reconciliation_ambiguity_choices helper (binding §6.2.1 menu)"
```

### §E.3 Task T-D.3 — `swing journal discrepancy resolve-ambiguity` CLI

**Files:**
- Modify: `swing/cli.py`
- Test: `tests/cli/test_discrepancy_resolve_ambiguity_cli.py`

**Acceptance criteria (per spec §6.2 + Codex R5 Major #2 LOCK per-choice payload contract):**
1. NEW subcommand `resolve-ambiguity <discrepancy_id> --choice <choice_code> [--custom-value '<json>'] [--reason <free-text>]`.
2. `--reason` is REQUIRED on every invocation (per spec §6.4 mandatory + §6.2 Codex R5 LOCK; CLI exits non-zero with `click.MissingParameter` style message if missing).
3. CLI parses `discrepancy_id` → fetches the discrepancy → reads `ambiguity_kind` → validates `choice_code` against `get_choice_menu(ambiguity_kind)`. Reject with friendly error if incompatible.
4. **Per-choice `--custom-value` enforcement (Codex R5 Major #2 LOCK):** for each choice in the menu, if `requires_custom_value is True AND --custom-value not supplied`, CLI rejects with `click.UsageError("--custom-value is required for choice '<code>'; expected JSON shape: <description>")`. The description text for each choice's expected JSON shape is part of the helper-module data (T-D.2) — extended to include an `expected_payload_shape_description` field on `ChoiceMenuItem`.
5. CLI invokes `apply_tier2_resolution(conn, discrepancy_id=..., choice_code=..., operator_custom_payload=<parsed JSON>, operator_reason=..., risk_policy_id=<active_at_time_of_call>)`.
6. Success: prints `"resolved discrepancy {id} via choice '{code}'; correction_id={result.correction_id}"` and exits 0.
7. `ValidatorRejectedError`: maps to friendly CLI error + exit 1.
8. `ValueError` from service (incompatible choice OR missing required payload OR malformed JSON): maps to `click.UsageError` + exit 2.
9. Discriminating tests:
   - Happy path with each of the 7 ambiguity_kinds × 1 valid choice each (7 tests).
   - Missing `--reason`: assert exit non-zero.
   - Missing `--custom-value` on payload-required choice: assert clear error message + exit 2.
   - Malformed `--custom-value` JSON: assert friendly parse error + exit 2.
   - Incompatible `--choice` for ambiguity_kind: assert clear error message + exit 2.

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/cli.py tests/cli/test_discrepancy_resolve_ambiguity_cli.py
git commit -m "feat(phase12-bundle-c-T-D.3): resolve-ambiguity CLI subcommand + per-choice --custom-value enforcement"
```

### §E.4 Task T-D.4 — `swing journal discrepancy override-correction` CLI

**Files:**
- Modify: `swing/cli.py`
- Test: `tests/cli/test_discrepancy_override_correction_cli.py`

**Acceptance criteria (per spec §6.4 + OQ-8 + OQ-15 dispositions):**
1. NEW subcommand `override-correction <correction_id> --truth-value '<json>' --reason <free-text> [--force]`.
2. Both `--truth-value` and `--reason` are REQUIRED.
3. **Confirmation prompt by default (OQ-8 ACCEPT):** when `--force` is NOT supplied, CLI prints the current correction row + the proposed override + the chain head + prompts `"Override this correction? [y/N]"`. On non-y answer: exits 0 with `"(aborted)"`.
4. `--force` flag bypasses the confirmation (non-interactive mode; mirrors `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` precedent).
5. CLI invokes `apply_tier3_override(conn, correction_id=..., operator_truth_value=<parsed JSON>, operator_reason=..., risk_policy_id=<active>)`.
6. `AlreadySupersededError` (OQ-15 disposition): maps to friendly CLI error `"correction {id} is already superseded by correction {N}; override the chain head ({N}) instead"` + exit 2.
7. `ValidatorRejectedError`: friendly error + exit 1.
8. Discriminating tests:
   - Happy path with `--force` (skips prompt).
   - Confirmation prompt: provide `"n"` to stdin; assert aborted-line + correction NOT applied.
   - Confirmation prompt: provide `"y"` to stdin; assert override applied.
   - Already-superseded: assert clear error naming the chain head correction_id.
   - Missing `--truth-value`: assert exit non-zero.
   - Missing `--reason`: assert exit non-zero.

- [ ] **Steps 1-5: TDD.**

```bash
git add swing/cli.py tests/cli/test_discrepancy_override_correction_cli.py
git commit -m "feat(phase12-bundle-c-T-D.4): override-correction CLI + confirmation prompt + --force flag + AlreadySupersededError chain-head guidance"
```

### §E.5 Task T-D.5 — Per-(kind, choice_code) handler-registry exhaustiveness regression test

**Files:**
- Test: `tests/cli/test_resolve_ambiguity_handler_exhaustiveness.py`

**Acceptance criteria:**
1. Test iterates the §6.2.1 binding-contract table (encoded as a Python constant in the test) + asserts EVERY (ambiguity_kind, choice_code) pair has:
   - An entry in `get_choice_menu(ambiguity_kind)` (T-D.2 helper).
   - An entry in `_TIER2_HANDLERS` (T-C.3 service registry).
2. Inverse: test asserts no orphan entries in either dict (every menu entry has a handler; every handler has a menu entry).
3. This is the canonical "no silent kind/choice drift" regression test — protects against the spec §6.2.1 LOCKED 18-pair contract drifting out-of-sync as future V2 dispatches widen the menu.

- [ ] **Steps 1-3: TDD.**

```bash
git add tests/cli/test_resolve_ambiguity_handler_exhaustiveness.py
git commit -m "test(phase12-bundle-c-T-D.5): exhaustive handler-registry vs menu vs spec §6.2.1 binding-contract regression test"
```

### §E.6 Task T-D.6 — `swing journal reconcile-backfill` CLI scaffold

**Files:**
- Modify: `swing/cli.py` (add `@journal_group.command("reconcile-backfill")`)
- Create: `swing/trades/reconciliation_backfill.py` (orchestration helper)
- Test: `tests/cli/test_reconcile_backfill_cli.py`

**Acceptance criteria (per spec §8.2 LOCKED CLI surface):**
1. NEW subcommand `swing journal reconcile-backfill [--apply] [--dry-run] [--ticker <ticker>] [--limit <N>] [--no-pass-2-on-dry-run] [--retry-pass-2-failures]`.
2. Default mode: `--dry-run` (per spec §8.2 LOCK).
3. `--apply` flag: actually executes; mutually exclusive with `--dry-run` (Click raises if both supplied).
4. Helper module `swing/trades/reconciliation_backfill.py` exposes `run_backfill(conn, *, dry_run, ticker=None, limit=None, no_pass_2_on_dry_run=False, retry_pass_2_failures=False, schwab_client, environment) -> BackfillSummary` orchestrator.
5. `BackfillSummary` dataclass: `tier1_applied: int`, `tier2_stamped: int`, `tier_errored: int`, `pass_2_failed: int`, `skipped_already_resolved: int`, `skipped_pass_2_failed: int`, `per_discrepancy_outcomes: list[BackfillOutcome]`.
6. CLI prints summary at end.
7. Discriminating tests:
   - Dry-run with no `--apply` is the default + does NOT mutate journal (verified via row-count + content snapshot pre+post).
   - `--apply --dry-run` BOTH: Click rejects with usage error.
   - Empty unresolved set: prints `"(no unresolved discrepancies)"` and exits 0.
   - `--ticker DHC` filter scopes the iteration.

- [ ] **Steps 1-5: TDD scaffold.**

```bash
git add swing/cli.py swing/trades/reconciliation_backfill.py tests/cli/test_reconcile_backfill_cli.py
git commit -m "feat(phase12-bundle-c-T-D.6): swing journal reconcile-backfill CLI scaffold + BackfillSummary dataclass"
```

### §E.7 Task T-D.7 — Backfill Pass 1 (persisted-JSON-only classification)

**Files:**
- Modify: `swing/trades/reconciliation_backfill.py`
- Test: `tests/trades/test_reconciliation_backfill_pass1.py`

**Acceptance criteria (per spec §8.4 Pass 1):**
1. Pass 1 reads each unresolved discrepancy's `expected_value_json` + `actual_value_json` + the FK-referenced journal row.
2. Pass 1 invokes `classify_discrepancy(disc, source_payload=<parsed actual JSON>, journal_row=<fetched journal row>, validator_chain=None)` — validator_chain INTENTIONALLY NULL on Pass 1 (defense-in-depth at service-layer apply-time per T-C.2 step 2).
3. Per spec §8.4 table: Pass 1 sufficient for `entry_price_mismatch`, `close_price_mismatch`, `stop_mismatch`, `position_qty_mismatch`, `cash_movement_mismatch`, `equity_delta`, `sector_tamper`, `snapshot_mismatch` (8 of 10 types). Pass 1 INSUFFICIENT for `unmatched_open_fill` + `unmatched_close_fill` — emits `(tier=2, ambiguity_kind='unsupported', metadata _pass_2_required=True)`.
4. Dry-run mode: prints projected classification matrix:
   ```
   Backfill --dry-run projection:

   ID  | Ticker | Type                  | Projected outcome              | Action needed
   ----+--------+-----------------------+--------------------------------+--------------------------
   41  | CVGI   | entry_price_mismatch  | tier-1 auto-apply              | (none)
   39  | DHC    | unmatched_open_fill   | Pass 2 required (re-fetch)     | --apply or --no-pass-2
   40  | VSAT   | unmatched_open_fill   | Pass 2 required (re-fetch)     | --apply or --no-pass-2
   ```
5. Apply mode: invokes `_apply_tier1_correction_inner` for tier-1 outcomes; stamps tier-2 outcomes via direct UPDATE; transitions Pass-2-required outcomes into Pass 2 (T-D.8).
6. Discriminating tests:
   - CVGI 41 fixture: Pass 1 emits tier-1; dry-run prints projection; `--apply` actually corrects.
   - DHC 39 fixture (Pass 1 only, no Pass 2 yet): emits tier-2 unsupported with `_pass_2_required=True`.
   - Sector tamper fixture: Pass 1 emits tier-2 (per T-B.10 sub-classifier); dry-run prints projection.

- [ ] **Steps 1-7: TDD.**

```bash
git add swing/trades/reconciliation_backfill.py tests/trades/test_reconciliation_backfill_pass1.py
git commit -m "feat(phase12-bundle-c-T-D.7): backfill Pass 1 — persisted-JSON-only classification + dry-run projection matrix"
```

### §E.8 Task T-D.8 — Backfill Pass 2 (Schwab re-fetch + Pass-2-tier-1-FORBIDDEN LOCK)

**Files:**
- Modify: `swing/trades/reconciliation_backfill.py`
- Test: `tests/trades/test_reconciliation_backfill_pass2.py`

**Acceptance criteria (per spec §8.4 Pass 2 + LOCKED Pass-2-tier-1-FORBIDDEN rule):**
1. Pass 2 only fires when Pass 1 flagged `_pass_2_required=True` (currently only for `unmatched_open_fill` + `unmatched_close_fill`).
2. Pass 2 calls `swing/integrations/schwab/trader.py:get_account_orders(...)` (verified at §A.7.4 — `SchwabOrderResponse` order-grain) with `(ticker=<disc.ticker>, from_entered_time=<disc.created_at_date>, to_entered_time=<disc.created_at_date>, surface='cli', environment=<cfg.environment>)`.
3. Each Pass 2 fetch writes a `schwab_api_calls` audit row with `surface='cli'`, `endpoint='accounts.orders.list'` (per spec §8.4 + Codex R2 C#1 lock; per Phase 11 sandbox-gating §9.7).
4. **§8.4 Pass-2-tier-1-FORBIDDEN LOCK enforcement** (Codex R3 Critical #1 + Major #1 fix): Pass 2 source data is `list[SchwabOrderResponse]` (order-grain); per the LOCK, classifier-output from Pass 2 MUST NEVER be tier-1. Plan T-B.4 sub-classifier already enforces this; T-D.8 inherits via the classifier output.
5. Sandbox short-circuit: under `environment='sandbox'`, Pass 2 returns `None` (no Schwab API call fired) + classifier emits tier-2 `unsupported` with rationale `"sandbox: cannot re-fetch source-canonical payload"` per spec §9.7.
6. **Pass 2 failure-mode (Codex R2 Major #2 LOCK):** if the Schwab re-fetch raises (`SchwabApiError`, `SchwabAuthError`, `SchwabRateLimitedError`, network error), the classifier emits tier-2 `unsupported` with rationale `"Pass 2 re-fetch failed: <reason>"`. Persisted state under `--apply`: `resolution='pending_ambiguity_resolution', ambiguity_kind='unsupported', resolution_reason` containing `"Pass 2 re-fetch failed"`. Pipeline NEVER crashes (Phase 11 forward-binding lesson #2 inheritance).
7. Dry-run with Pass 2 enabled (default): re-fetches AND writes audit rows BUT does NOT stamp the discrepancy (per spec §8.2 Codex R2 Major #1 dry-run mutation-scope LOCK — dry-run DOES write `schwab_api_calls` audit rows because they are the read's audit-trail contract). Prints projected classification per Pass-2 outcome.
8. `--no-pass-2-on-dry-run` flag: skips Pass 2 entirely on dry-run; Pass-2-required discrepancies are projected as tier-2 `unsupported` in the matrix (less accurate dry-run projection trade-off per spec §8.2).
9. Discriminating tests:
   - DHC 39 fixture (Pass 2 returns 2 orders qty=20+19): emits tier-2 `multi_partial_vs_consolidated`; apply mode stamps the discrepancy + writes `schwab_api_calls` audit row.
   - VSAT 40 fixture (Pass 2 returns 1 order qty=2): emits tier-2 `unknown_schwab_subtype`.
   - VSAT 40 fixture (Pass 2 returns 0 orders): emits tier-2 `schwab_returned_no_match`.
   - Pass 2 raises `SchwabAuthError`: emits tier-2 `unsupported` with `"Pass 2 re-fetch failed"` rationale; discrepancy stamped accordingly under `--apply`.
   - Sandbox: emits tier-2 `unsupported` per §9.7; no Schwab API call fired.
   - `--no-pass-2-on-dry-run`: dry-run skips Schwab API entirely; matrix shows `unsupported`.

- [ ] **Steps 1-9: TDD.**

```bash
git add swing/trades/reconciliation_backfill.py tests/trades/test_reconciliation_backfill_pass2.py
git commit -m "feat(phase12-bundle-c-T-D.8): backfill Pass 2 — Schwab re-fetch + Pass-2-tier-1-FORBIDDEN LOCK + failure-mode persisted state + sandbox short-circuit"
```

### §E.9 Task T-D.9 — Backfill idempotency + `--retry-pass-2-failures` flag

**Files:**
- Modify: `swing/trades/reconciliation_backfill.py`
- Test: `tests/trades/test_reconciliation_backfill_idempotency.py`

**Acceptance criteria (per spec §8.3 + §8.4 #3 + #5):**
1. Re-running `swing journal reconcile-backfill --apply` is a no-op on already-resolved discrepancies:
   - Discrepancies with `resolution != 'unresolved'` are SKIPPED.
   - Counter `skipped_already_resolved` increments.
2. Pass-2-failed discrepancies are persisted as `resolution='pending_ambiguity_resolution'` (per §8.4 #3); these are also SKIPPED on default re-run.
   - Counter `skipped_pass_2_failed` increments when `--apply` skips them.
3. **`--retry-pass-2-failures` flag (per §8.2 + §8.3):** opt-in flag that scopes iteration to rows WHERE `resolution = 'pending_ambiguity_resolution' AND ambiguity_kind = 'unsupported' AND resolution_reason LIKE '%Pass 2 re-fetch failed%'`. Each retry re-fetches Schwab + writes a new `schwab_api_calls` audit row (intentional retry-history trail).
4. CLI summary prints:
   ```
   Backfill summary:
     Tier 1 applied: N
     Tier 2 stamped: M
     Errored: K
     Pass 2 failed (persisted as tier-2 unsupported): L
     Skipped (already resolved): X
     Skipped (Pass-2-failed; use --retry-pass-2-failures to retry): Y
   ```
5. Discriminating tests:
   - Re-run on a fully-resolved DB: 0 mutations; "Skipped: N" message.
   - Re-run after a Pass-2-failure landed: default skips; `--retry-pass-2-failures` re-attempts + writes new audit row.
   - Mixed state (some unresolved + some pass-2-failed + some already-resolved): correct counters across all three buckets.

- [ ] **Steps 1-7: TDD.**

```bash
git add swing/trades/reconciliation_backfill.py tests/trades/test_reconciliation_backfill_idempotency.py
git commit -m "feat(phase12-bundle-c-T-D.9): backfill idempotency + --retry-pass-2-failures flag + summary counters"
```

### §E.10 Task T-D.10 — Phase 10 dashboard banner predicate widening + 14-VM regression suite

**Files:**
- Modify: `swing/metrics/discrepancies.py` (widen `count_unresolved_material` transitively; widen `list_unresolved_material_for_trade`)
- Modify: `swing/data/repos/reconciliation.py` (widen `list_unresolved_material_for_active_trades:462` + `list_unresolved_material_for_closed_trades:485` SQL predicates)
- Test: `tests/metrics/test_discrepancies_predicate_widening.py`
- Test: `tests/web/test_base_layout_vm_banner_with_pending_ambiguity.py`

**Acceptance criteria (per OQ-7 acceptance + §A.5 verification):**
1. Widen 3 SQL predicates from `WHERE d.resolution = 'unresolved'` to `WHERE d.resolution IN ('unresolved', 'pending_ambiguity_resolution')`:
   - `swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades` (line 462 verified).
   - `swing/data/repos/reconciliation.py:list_unresolved_material_for_closed_trades` (line 485 verified).
   - `swing/metrics/discrepancies.py:list_unresolved_material_for_trade` (line 68 verified).
2. The shared `count_unresolved_material` (line 37) consumes the 2 widened helpers transitively — no direct edit needed.
3. The 14 VM instances across 9 files (per §A.5 enumerated count) automatically pick up the widened count via their pre-existing `unresolved_material_discrepancies_count: int = 0` field; no dataclass edits required.
4. Discriminating regression test suite — ONE test per VM file (9 tests since some files have 2-4 VM classes; assertion is per-file aggregate):
   - Plants a discrepancy with `resolution='pending_ambiguity_resolution' AND material_to_review=1 AND trade_id=<an active trade>`.
   - Renders each base-layout-extending page and asserts the banner shows the count.
5. Per-trade indicator (Phase 10 T-E.6): the per-trade `list_unresolved_material_for_trade` helper is widened the same way; per-trade indicator on `/trades/{id}` correctly surfaces tier-2-pending discrepancies attributed to that trade.
6. Banner-text content test: the rendered banner now says `"N unresolved material discrepancies"` where `N` includes both `'unresolved'` AND `'pending_ambiguity_resolution'` rows. Operator-facing wording stays the same (per spec §6.3); the predicate change is invisible at the banner-text level except via the count.
7. **Note on §A.5 brief-vs-spec discrepancy:** spec OQ-7 wording says "retrofit 10 base-layout VM consumers". Actual count per grep is 14 across 9 files. Banked at §I.10 as a V2.1 §VII.F amendment candidate (spec wording cleanup). Plan T-D.10 still covers the full surface.

- [ ] **Steps 1-7: TDD.**

```bash
git add swing/metrics/discrepancies.py swing/data/repos/reconciliation.py tests/metrics/test_discrepancies_predicate_widening.py tests/web/test_base_layout_vm_banner_with_pending_ambiguity.py
git commit -m "feat(phase12-bundle-c-T-D.10): Phase 10 banner predicate widens to include pending_ambiguity_resolution + 14-VM regression suite"
```

### §E.11 Task T-D.11 — Synthetic-fixture payload-contract acceptance test (C.D gate S6 prerequisite)

**Files:**
- Test: `tests/integration/test_phase12_bundle_c_payload_contract_acceptance.py`

**Acceptance criteria (per spec §15.5 C.D gate S6 LOCKED revised mechanic + brief §0.4 lesson #4):**
1. Test runs against an **isolated tmp `swing.db`** via the writing-plans-drafted gate fixture — NOT the operator's production DB.
2. Test plants a synthetic discrepancy with `ambiguity_kind='unknown_schwab_subtype'` so `operator_truth` is a valid choice (per spec §6.2.1 menu).
3. Test exercises the parse-time payload-required error first:
   - Invoke `swing journal discrepancy resolve-ambiguity <id> --choice operator_truth --reason "..."` WITHOUT `--custom-value` → assert CLI exits non-zero with clear missing-flag error.
4. Test then dispositions via `--choice operator_truth --custom-value '{"price": 1.23}' --reason "synthetic gate fixture; isolated DB"`:
   - Assert CLI exits 0.
   - Assert `reconciliation_corrections.applied_value_json` row contains `{"price": 1.23}` verbatim.
   - Assert `reconciliation_discrepancies.resolution = 'operator_resolved_ambiguity'`.
5. Synthetic-fixture DB is discarded at test end (per spec §15.5 LOCK — append-only audit on production DB is preserved because synthetic test runs against an isolated DB).
6. This test underwrites the C.D gate S6 surface (per §G.4 below) — the operator-witnessed gate at C.D will RUN this test as the payload-contract acceptance step, separately from operator's REAL disposition of DHC 39 / VSAT 40.

- [ ] **Steps 1-5: implement.**

```bash
git add tests/integration/test_phase12_bundle_c_payload_contract_acceptance.py
git commit -m "test(phase12-bundle-c-T-D.11): synthetic-fixture payload-contract acceptance test (C.D gate S6 prerequisite per spec §15.5 LOCKED)"
```

### §E.12 Task T-D.12 — Cycle-checklist updates

**Files:**
- Modify: `docs/cycle-checklist.md`

**Acceptance criteria:**
1. New cadence section enumerates operator's weekly review of pending ambiguities:
   - After Schwab reconciliation pipeline run: run `swing journal discrepancy list-pending-ambiguities` to surface tier-2 backlog.
   - For each pending discrepancy: run `swing journal discrepancy show-ambiguity <id>` to inspect the menu.
   - Decide based on operator context + broker-statement consultation: pick a `--choice` + supply `--reason` (+ `--custom-value` per the §6.2.1 contract when required).
   - Run `swing journal discrepancy resolve-ambiguity <id> --choice <code> --reason "..." [--custom-value '<json>']`.
2. New section for the one-time backfill operation:
   - First-time after C.D ships: run `swing journal reconcile-backfill --dry-run` to preview classification matrix.
   - Inspect projection; run `--apply` when ready (or `--ticker CVGI` to scope to a single ticker).
3. New section for tier-3 override (rare):
   - When operator has ground-truth-Schwab-is-wrong evidence: identify the prior correction_id (via `swing journal discrepancy show <id>` showing the linked correction); run `swing journal discrepancy override-correction <correction_id> --truth-value '<json>' --reason "..."`. Confirmation prompt fires by default; use `--force` for non-interactive.

- [ ] **Steps 1-3: write the markdown edits + commit.**

```bash
git add docs/cycle-checklist.md
git commit -m "docs(phase12-bundle-c-T-D.12): cycle-checklist updates — Tier-2 weekly cadence + one-time backfill + tier-3 override"
```

### §E.13 Task T-D.13 — CLAUDE.md gotcha additions

**Files:**
- Modify: `CLAUDE.md`

**Acceptance criteria:** add the following gotchas (4-6 entries per writing-plans assessment of which Sub-bundle C ship-time lessons need promotion to durable CLAUDE.md form):

1. **Tier-1 auto-correct service inherits sandbox short-circuit gating from Phase 11.** Same pattern as `_step_schwab_snapshot` + `_step_schwab_orders` — under `environment='sandbox'`, domain rows are NOT written; audit rows ARE written. The `apply_tier1_correction` outer function accepts `environment` keyword + short-circuits when sandbox. Reconciliation flow pivot at `run_schwab_reconciliation` + `run_tos_reconciliation` honors this end-to-end. Discriminating test pattern: invoke service with `environment='sandbox'` + assert no journal mutation + assert WARNING log + assert `CorrectionResult.correction_id is None`.

2. **`reconciliation_corrections` is APPEND-ONLY; tier-3 chains add NEW rows pointing back; never DELETE or UPDATE-in-place.** The override chain pattern (`tier-1 → tier-3 → tier-3-of-tier-3`) extends by INSERTing a new row + UPDATEing the PRIOR row's `superseded_by_correction_id` to point forward. The most-recent (chain-head) row has `superseded_by_correction_id IS NULL`. Operator-facing CLI rejects `override-correction` against an already-superseded row (per OQ-15 disposition); points operator at the current chain head's `correction_id`.

3. **Pass-2-tier-1-FORBIDDEN: V1 Schwab mapper exposes only order-level price; auto-correcting `fills.price` from `SchwabOrderResponse.price` is forbidden because order-level price can differ from execution price.** All `unmatched_open_fill` / `unmatched_close_fill` discrepancies resolve to tier-2-always under V1 — operator picks per §6.2.1 menu after consulting their broker execution statement. V2 candidate (operator-locked next-architectural-dispatch): widen the mapper to expose `orderActivityCollection[].executionLegs[]` so the classifier can redirect to tier-1 `entry_price_mismatch` on execution-grain data.

4. **Reconciliation flow pivot uses SAVEPOINT-per-discrepancy inside the outer run transaction.** Without the savepoint, an exception AFTER a partial journal UPDATE but BEFORE the audit row INSERT would leave a silent mutation when the outer transaction commits. Pattern: `SAVEPOINT correction_sp_<discrepancy_id>` / `RELEASE` on success / `ROLLBACK TO + RELEASE` on any exception. SAVEPOINT names use the discrepancy_id to guarantee within-tx uniqueness. The auto-correction service exposes a private `_apply_tier1_correction_inner` (caller-tx) for this nested usage; the public `apply_tier1_correction` (own-tx) is for standalone CLI / backfill invocations.

5. **Classifier is a PURE function — no DB writes, no Schwab API calls, no transaction management.** All I/O is in the service layer (`reconciliation_auto_correct.py`) or the backfill orchestrator (`reconciliation_backfill.py`). The classifier consumes pre-fetched payloads + journal rows; service / backfill fetch them. This is the canonical retroactive-vs-prospective-symmetric architecture per spec §13.2: a future fill-auto-population-at-entry sub-bundle can reuse `classify_discrepancy` verbatim.

6. **Tier-2 CLI `--custom-value` requirement is PER-CHOICE not suffix-based.** Per spec §6.2.1 Codex R5 Major #2 LOCK: choices like `consolidate_using_operator_vwap`, `split_into_partials`, `pick_schwab_record_<N>`, `operator_truth`, `operator_alternative`, `custom` REQUIRE `--custom-value`; choices like `keep_journal_as_is`, `mark_unmatched`, `acknowledge` do NOT. CLI validates via the helper-module `get_choice_menu(ambiguity_kind)`'s `requires_custom_value: bool` field on each `ChoiceMenuItem`. The §6.2.1 table is the binding contract.

- [ ] **Step 1: Append gotchas to CLAUDE.md.**

```bash
git add CLAUDE.md
git commit -m "docs(phase12-bundle-c-T-D.13): CLAUDE.md gotcha additions (6 new entries)"
```

### §E.14 Task T-D.14 — `briefing.md` Reconciliation status section integration test

**Files:**
- Test: `tests/integration/test_briefing_md_reconciliation_status_e2e.py`

**Acceptance criteria:**
1. End-to-end test: plant 2 pending-ambiguity discrepancies + 1 recently-applied tier-1 correction; run the briefing renderer; assert the `briefing.md` output contains the "Reconciliation status" section with the expected counters.
2. Assert the empty-section case: when no pending + no recent tier-1 → briefing.md does NOT include the section (per T-C.9 conditional rendering).

- [ ] **Steps 1-3: implement.**

```bash
git add tests/integration/test_briefing_md_reconciliation_status_e2e.py
git commit -m "test(phase12-bundle-c-T-D.14): briefing.md Reconciliation status section end-to-end integration test"
```

### §E.15 C.D integration commit + ruff + worktree push + operator-witnessed gate

After T-D.1 through T-D.14 land:

1. Runs `pytest -q -n auto` and confirms +55-80 new fast tests above C.C baseline.
2. Runs `ruff check swing/` and confirms baseline 18 unchanged.
3. Runs the slow integration suite (`pytest -m slow`) and confirms migration-against-production-snapshot test passes.
4. Pushes the worktree branch.

C.D operator-witnessed gate (per §G.4) follows — **10 surfaces verified by the orchestrator before integration merge — the big one.** This is the final gate for Sub-bundle C as a whole; closes the architectural pivot.

---

## §F Cross-sub-sub-bundle pin matrix (BINDING INTERFACES)

This section records BINDING interfaces between sub-sub-bundles. Each pin underwrites a forward-binding integration test that ships SKIPPED at the providing sub-sub-bundle + un-skips at the consuming sub-sub-bundle's landing.

### §F.1 Interface table

| Pin # | Producer (sub-bundle / task) | Consumer (sub-bundle / task) | Interface contract | Pin test |
|---|---|---|---|---|
| F-1 | C.A T-A.1 schema | C.B T-B.13 + C.C T-C.2 | `reconciliation_corrections` table shape (19 columns + 4 indexes + CHECK enums) | `tests/data/test_migration_0019_schema_shape.py` (un-skip at T-A.1 landing) |
| F-2 | C.A T-A.3 repo | C.C T-C.2/3/4 | `insert_correction(conn, ReconciliationCorrection) -> int`; `update_superseded_by(conn, ...)`; etc. signatures | `tests/data/test_reconciliation_corrections_repo.py` (un-skip at T-A.3 landing) |
| F-3 | C.A T-A.1 + T-A.5 | C.B T-B.4 + T-D.7 | `ReconciliationDiscrepancy.ambiguity_kind` field + cross-column CHECK semantics | `tests/data/test_reconciliation_discrepancy_ambiguity_kind_roundtrip.py` |
| F-4 | C.B T-B.1 classifier | C.C T-C.5/6 pivot + T-D.7 backfill | `classify_discrepancy(...) -> ClassificationResult` signature + dispatch table for 10 discrepancy_types | `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py::test_classifier_module_exists_and_returns_classification_result` (T-A.7 placeholder; un-skip at T-B.1 landing) |
| F-5 | C.B T-B.13 validator dispatcher | C.C T-C.2/3/4 service | `default_validator_chain(conn)` returns `ValidatorChainCallable`; composes with `affected_table` partial-application | `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py::test_validator_chain_dispatches_on_affected_table` (un-skip at T-B.13 landing) |
| F-6 | C.C T-C.2 outer service | C.C T-C.5/6 pivot | `apply_tier1_correction` (public/own-tx) + `_apply_tier1_correction_inner` (private/caller-tx) split — pivot calls inner | T-C.5/6 discriminating tests assert inner is called from within outer run's tx |
| F-7 | C.C T-C.3 handlers | C.D T-D.3 CLI + T-D.5 exhaustiveness | 18 per-(ambiguity_kind, choice_code) handlers registered + matching `get_choice_menu(...)` | T-D.5 exhaustiveness regression test |
| F-8 | C.D T-D.2 menu helper | C.D T-D.3 CLI | `get_choice_menu(ambiguity_kind) -> list[ChoiceMenuItem]` with `requires_custom_value` field | T-D.3 per-choice payload-required CLI test |
| F-9 | C.D T-D.6/7/8/9 backfill | C.D gate S2/S3/S4 | `swing journal reconcile-backfill` CLI surface + flags | C.D gate plan |
| F-10 | C.D T-D.10 banner widening | All 14 base-layout VMs | `count_unresolved_material(conn)` now sums `'unresolved'` + `'pending_ambiguity_resolution'` | T-D.10 14-VM regression suite |

### §F.2 Pin enforcement discipline

- Each pin's BINDING test ships SKIPPED at the producer task with reason `"forward-binding; un-skip at <consumer task> landing"`.
- Consumer task's TDD Step 1 includes un-skipping the corresponding pin test (mirrors Phase 10 Sub-bundle E T-E.3 un-skip-at-landing precedent).
- Plan-author lock: NO cross-sub-bundle pin landing is allowed to silently drift the interface; any mid-execution-of-consumer-task interface change MUST re-land the producer's underlying code via a follow-up commit (no "forward-fix-in-consumer-bundle" anti-pattern; per Phase 10 Sub-bundle A T-A.7 binding-interface amendment discipline + lesson #20 from Phase 10 forward-binding lessons).

---

## §G Per-sub-sub-bundle operator-witnessed gate plans

### §G.1 Sub-sub-bundle C.A gate (4 surfaces)

Per spec §15.5 C.A gate enumeration:

**S1 — inline pytest pass.** Run `pytest -q -n auto` against the C.A worktree branch; confirm +40-65 new fast tests above main baseline (3862 → ~3900-3925); ZERO regression failures.

**S2 — `swing db-migrate` against fresh DB.** Spin a fresh DB in a tmp path; run `swing db-migrate`; verify `schema_version=19` post-apply; verify all 7 schema deltas landed via SQLite introspection commands.

**S3 — `swing db-migrate` against production-snapshot DB.** Copy operator's production `swing.db` to a tmp path; run `swing db-migrate`; verify schema_version transitions 18 → 19; verify all 32 historical `reconciliation_discrepancies` rows preserved (column-by-column equality against pre-migration snapshot); verify all `review_log` + `trade_events` + `schwab_api_calls` rows preserved; verify backup file `swing-pre-phase12-bundle-c-migration-<ISO>.db` was created. **This is the slow-marked T-A.8 regression test in CI form; operator may re-run interactively to confirm.**

**S4 — ruff baseline unchanged.** Run `ruff check swing/` and confirm baseline 18 E501 — no regression.

**Pass criteria:** all 4 surfaces PASS. Integration merge unblocked.

### §G.2 Sub-sub-bundle C.B gate (3 surfaces)

Per spec §15.5 C.B gate enumeration:

**S1 — inline pytest pass.** Run `pytest -q -n auto`; confirm +55-95 new fast tests above C.A baseline; ZERO regression failures. T-A.7 cross-bundle pin tests un-skipped at T-B.14 + pass.

**S2 — classifier against 39 + 40 + 41 fixtures emits expected ClassificationResult shapes.** Operator-driven walkthrough: invoke the classifier (via a dispatched harness or via `python -c`) against the CVGI 41 / DHC 39 / VSAT 40 fixtures (each fixture built per spec §10 setup); assert:
- CVGI 41: `tier=1, ambiguity_kind=None, correction_target={'price': 5.30}`.
- DHC 39 (Pass 1 only): `tier=2, ambiguity_kind='unsupported', _pass_2_required=True`.
- VSAT 40 (Pass 1 only): same shape as DHC 39 (Pass 2 not invoked from classifier directly; classifier is pure-function).

**S3 — ruff baseline unchanged.** Same as G.1 S4.

**Pass criteria:** all 3 surfaces PASS.

### §G.3 Sub-sub-bundle C.C gate (4 surfaces)

Per spec §15.5 C.C gate enumeration:

**S1 — inline pytest pass.** Run `pytest -q -n auto`; confirm +65-115 new fast tests above C.B baseline; ZERO regression failures. T-A.7 cross-bundle pin tests still pass.

**S2 — simulated reconciliation run end-to-end with planted tier-1 + tier-2 discrepancies.** Operator-driven walkthrough: create a fresh tmp DB; plant a CVGI-shaped trade + 1 DHC-shaped trade; plant mocked Schwab orders responses with the divergent prices; invoke `run_schwab_reconciliation(...)` end-to-end with `environment='production'`; assert:
- CVGI discrepancy → `resolution='auto_corrected_from_schwab'`; `fills.price=$5.30`; `reconciliation_corrections` row exists; `trade_events` row exists.
- DHC discrepancy → `resolution='pending_ambiguity_resolution', ambiguity_kind` populated.
- `reconciliation_runs.state='completed'`; `summary_json` includes `tier1_applied_count: 1, tier2_pending_count: 1`.
- Operator deliberately rigs a validator failure (e.g., poisons the proposed CVGI price to a negative value via test monkeypatch); re-runs; asserts CVGI falls through to tier-2 with `ambiguity_kind='validator_rejected'`.

**S3 — sandbox short-circuit test.** Same scenario as S2 but with `environment='sandbox'`; assert:
- CVGI discrepancy emitted BUT NOT auto-corrected; `resolution='unresolved'`; `fills.price` unchanged.
- DHC discrepancy emitted; `resolution='unresolved'` (NOT `pending_ambiguity_resolution` because sandbox short-circuits classifier output → audit row is the only persistent state).
- `summary_json.tier1_applied_count == 0`.
- WARNING log lines emitted citing "sandbox: ..." per `apply_tier1_correction` sandbox branch.

**S4 — ruff baseline unchanged.**

**Pass criteria:** all 4 surfaces PASS.

### §G.4 Sub-sub-bundle C.D gate (10 surfaces — the big one)

Per spec §15.5 C.D gate LOCKED revised mechanic (Codex R6 + R7 + R8 fixes):

**S1 — inline pytest pass.** Run `pytest -q -n auto`; confirm +55-80 new fast tests above C.C baseline; ZERO regression failures. ALL forward-binding pins (F-1 through F-10) pass.

**S2 — `swing journal reconcile-backfill --dry-run` against production DB.** Operator runs the dry-run; expected output is the classification matrix:
- disc 41 CVGI `entry_price_mismatch` → projected tier-1 auto-apply (Pass 1 sufficient).
- disc 39 DHC `unmatched_open_fill` → Pass 2 required; re-fetch Schwab via `get_account_orders(...)`; projected classification per Pass-2 outcome (3 possible cases per spec §10.2 + §8.4 LOCK).
- disc 40 VSAT `unmatched_open_fill` → Pass 2 required; same as DHC.
- Pass-2 re-fetches consume Schwab API quota for DHC + VSAT (2 calls; each writes a `schwab_api_calls` audit row).
- Operator reviews the projection.

Pre-gate operator check: confirm Schwab refresh-token has TTL > 1hr (operator may need to re-auth via `/schwab/setup` if the production token expired since 2026-05-15T17:05:00+00:00 — see §0.1 production refresh-token clock note).

**S3 — `swing journal reconcile-backfill --apply --ticker CVGI` against production.** Operator runs the scoped apply; expected outcomes:
- `fills.fill_id=9.price = $5.30` (was $5.23).
- `trades.<CVGI>.current_avg_cost = $5.30`.
- `reconciliation_corrections` row exists with `correction_action='auto_applied'`.
- `reconciliation_discrepancies.discrepancy_id=41.resolution = 'auto_corrected_from_schwab'`.
- `trade_events` row exists for `<CVGI trade>` with `event_type='reconciliation_auto_correct'`.
- CLI prints "Tier 1 applied: 1; Tier 2 stamped: 0; ..." summary.

**S4 — `swing journal reconcile-backfill --apply --ticker DHC` AND `swing journal reconcile-backfill --apply --ticker VSAT`** (or single invocation without `--ticker` filter; operator preference). Expected outcomes:
- DHC 39: `resolution='pending_ambiguity_resolution', ambiguity_kind` populated per Pass-2 actual outcome.
- VSAT 40: same.
- Phase 10 dashboard banner now shows count=2 (the 2 newly-pending-ambiguity discrepancies; CVGI was auto-resolved at S3). T-D.10 banner widening verified end-to-end.

**S5 — `swing journal discrepancy show-ambiguity 39` displays candidate choices.** Operator runs the show command; verifies output matches the expected menu for DHC 39's actual `ambiguity_kind` (per S4 Pass-2 outcome). Verifies `[RECOMMENDED]` tag on `keep_journal_as_is` if the ambiguity_kind is `multi_partial_vs_consolidated`.

**S6 — Payload-contract acceptance via isolated synthetic-fixture DB + operator's REAL DHC 39 disposition.** This surface has TWO substeps per spec §15.5 LOCKED revised mechanic:
- **S6a (pre-real-disposition):** the gate fixture creates an isolated tmp `swing.db` (the writing-plans-drafted T-D.11 integration test); plants a synthetic discrepancy with `ambiguity_kind='unknown_schwab_subtype'` so `operator_truth` is a valid choice; first exercises the parse-time payload-required error (operator runs CLI WITHOUT `--custom-value` → asserts non-zero exit + clear error message); then dispositions via `--choice operator_truth --custom-value '{"price": 1.23}' --reason "synthetic gate fixture"` → asserts CLI exits 0 + `reconciliation_corrections.applied_value_json` contains `{"price": 1.23}` + `resolution='operator_resolved_ambiguity'`. Synthetic-fixture DB is discarded after S6a. **This satisfies the payload-contract acceptance test surface without contortion on the real DHC 39 case.**
- **S6b (operator's REAL disposition):** Operator dispositions production DHC 39 per their actual data — `keep_journal_as_is` (no broker-statement consultation; V1 default; expected most common) OR `consolidate_using_operator_vwap` / `split_into_partials` / `operator_truth` / `custom` with real `--custom-value` if operator has execution-level data. NO contrived contortions on the real production case.
- Post-S6b: DHC 39 is in `resolution='operator_resolved_ambiguity'`; Phase 10 dashboard banner now shows count=1 (VSAT 40 remaining).

**S7 — VSAT 40 disposition via operator's REAL data.** Operator runs `show-ambiguity 40` then `resolve-ambiguity 40 --choice <picked> --reason "..."` per actual Pass-2 outcome. **Codex R8 Minor #2 clarification (LOCKED):** payload-contract surface was already satisfied at S6a's synthetic-fixture run; S7 does NOT need to exercise a payload-required choice on the production VSAT case. Operator dispositions per their actual data without contortion.

**S8 — Phase 10 dashboard banner clears to ZERO.** Operator opens `/dashboard` in the browser via `swing web --port 8081`; asserts the "unresolved material discrepancies" banner shows count=0 (all 3 production discrepancies now in terminal states: CVGI `auto_corrected_from_schwab`, DHC + VSAT `operator_resolved_ambiguity`). T-D.10 banner widening verified end-to-end via the gate. **NOTE:** verify the banner correctly incremented at S4 (count=2 when DHC + VSAT landed in pending) AND correctly decremented after S6+S7 (count=0). This is the OQ-7 acceptance evidence.

**S9 — ruff baseline unchanged.**

**S10 — cycle-checklist + CLAUDE.md gotcha additions verified.** Operator reads through T-D.12 cycle-checklist updates + T-D.13 CLAUDE.md gotcha additions; confirms cadence makes sense + gotchas accurately describe the architectural pivot.

**Pass criteria:** ALL 10 surfaces PASS. Sub-bundle C closes. Phase 12 Sub-bundle C UNBLOCKED for integration merge.

**Post-gate cleanup (orchestrator):**
- Worktree teardown (branch deleted; on-disk husk handled by cycle-checklist `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` opt-in).
- V2 candidates banked per §I.
- Forward-binding lessons distilled into orchestrator-context.md per §J.
- Production state: 3 historical discrepancies dispositioned (all terminal states); banner cleared.
- **Next-architectural-dispatch slot unblocked:** V2 mapper widening + auto-VWAP per OQ-4 Option C operator-locked plan (out of Sub-bundle C scope; banked at §I.1).

---

## §H Test projection summary + commit message stems

### §H.1 Per-sub-sub-bundle test deltas

| Sub-sub-bundle | Per-spec §12 projection | Plan-author projection (after task decomposition) | Cumulative test count post-bundle |
|---|---|---|---|
| C.A Foundation | +35-55 fast tests | +40-65 fast tests | ~3902-3927 |
| C.B Classifier + validator shim | +50-90 fast tests | +55-95 fast tests | ~3957-4022 |
| C.C Auto-correction service + flow pivot | +60-120 fast tests | +65-115 fast tests | ~4022-4137 |
| C.D Tier-2 CLI + backfill + banner widening | +80-150 fast tests | +55-80 fast tests | ~4077-4217 |
| **Cumulative Sub-bundle C** | **+225-415** | **+215-355** | **~4077-4217 fast tests** |

Plan-author projection is slightly tighter than spec §12 in C.D scope because the banner-widening retrofit is mechanically smaller than the spec's 10-VM phrasing suggested (per §A.5 + T-D.10 — the widening lands at 3 helper functions; the 14 regression tests are smaller-scope than full VM retrofits).

**Per Phase 9/10/11/12-A/12-B overshoot precedent:** actual cumulative likely lands in **upper half of projection** (+285..+405 fast tests); plan-author lock for return report uses `+285..+400 fast tests projected`.

### §H.2 Commit message stems per task

Per §B / §C / §D / §E task enumerations. Sub-sub-bundle dispatch commits should land on the worktree branch + integration-merge from the worktree to main per Phase 9/10/11/12-A/12-B precedent. Stem format: `feat(phase12-bundle-c-T-X.N): <summary>` for code; `test(phase12-bundle-c-T-X.N): <summary>` for test-only; `docs(phase12-bundle-c-T-X.N): <summary>` for docs.

### §H.3 Integration merge commits per sub-sub-bundle

Each sub-sub-bundle ends with an integration merge from worktree to main:
- C.A merge: `merge(phase12-bundle-c-A): integration merge — schema foundation + dataclass + repo CRUD`.
- C.B merge: `merge(phase12-bundle-c-B): integration merge — classifier + validator shim`.
- C.C merge: `merge(phase12-bundle-c-C): integration merge — auto-correction service + flow pivot + briefing.md extension`.
- C.D merge: `merge(phase12-bundle-c-D): integration merge — Tier-2 CLI + backfill + banner widening — Sub-bundle C CLOSED`.

Each merge follows Phase 10/11/12 precedent: `--no-ff` to preserve the Codex-fix chain on the worktree; ALL Codex rounds reach `NO_NEW_CRITICAL_MAJOR` before integration merge.

---

## §I V2 candidates banked

### §I.1 V2 mapper widening + auto-VWAP classifier path — operator-locked next-architectural-dispatch

Per brief §0.6 + spec §14.OQ-4 disposition (operator-locked Option C 2026-05-15):

The shipped Schwab mapper at `swing/integrations/schwab/trader.py:_parse_order_response()` (or equivalent function name; T-A.7 V2 dispatch verifies) maps `Client.account_orders(...)` response → `SchwabOrderResponse` with `price` field reading from order-level `price` (limit price) OR `stopPrice` per the mapper at `mappers.py:223-229`. The order-level price differs from per-execution fill prices.

V2 dispatch widens the mapper to expose `orderActivityCollection[].executionLegs[]` per-execution detail. Once shipped:
- Classifier `unmatched_open_fill` sub-classifier (T-B.4) can redirect to tier-1 `entry_price_mismatch` when Pass-2 source data is execution-grain (not order-grain).
- `multi_partial_vs_consolidated` default highlighted choice reverts from `keep_journal_as_is` to auto-derived `consolidate_using_schwab_vwap` (originally banked in brainstorm pre-R4-revision; superseded by `keep_journal_as_is` in spec OQ-4 Codex R4 Minor #1 fix; V2 restores).

**Operator-locked next-architectural-dispatch slot:** post-Sub-bundle-C.D ship. Plan does NOT propose mapper widening within Sub-bundle C scope (brief §0.6 + §3 OUT-OF-SCOPE).

### §I.2 `fills.reconciliation_status` enum widening

Per spec §9.2 V1 LOCK: V1 does NOT widen the 5-value enum. V2 candidate adds `'auto_corrected_from_schwab'` value if Phase 10 dashboard surfaces per-fill provenance distinguishable from operator-resolved-ambiguity.

### §I.3 Web Tier-2 surface

Per spec §6.1 + OQ-3 V1 CLI-only lock. V2 candidate layers `/discrepancies` route group with index + per-discrepancy resolve route mirroring the `/schwab/setup` HTMX pattern (Phase 12 Sub-bundle B precedent). The web route consumes the same CLI's underlying service layer (`apply_tier2_resolution`); only the user-facing form layer is new.

### §I.4 `schwab_api_calls.surface='auto_correct'` enum widening

Per spec §3.4 + §A.7.4 + Phase 12 Sub-bundle B precedent: V1 uses `surface='cli'` for backfill-initiated calls. V2 candidate adds distinct `'auto_correct'` value via schema migration (mirrors Phase 12 Sub-bundle B's `surface='web'` V2 candidate). Discriminating Phase 10 dashboard analytics could surface auto-correct-triggered Schwab API quota separately.

### §I.5 Schwab API response body caching for backfill replay

Per spec §14.OQ-10: V1 backfill re-fetches Schwab via `get_account_orders(...)` for each Pass-2-required discrepancy. V2 candidate: separate full-API-response-cache table preserves response bodies; backfill replay uses cache when response is within freshness window (e.g., 30 days). Eliminates Schwab API quota burn on idempotent backfill re-runs.

### §I.6 Refactor reconciliation_validators shim into repo modules

Per spec §5.5 + §14.OQ-14: V1 shim lives at `swing/trades/reconciliation_validators.py`. V2 candidate: refactor the 4 dry-run validators into the repo modules themselves so `swing/data/repos/fills.py:validate_correction(...)` etc. become first-class repo callables. Repo-layer formalization aligns with Phase 7 fills schema discipline.

### §I.7 Sandbox-friendly preview mode

Per spec §14.OQ-13 + §9.7: V1 sandbox short-circuits auto-correction. V2 candidate: preview mode under sandbox that emits projected `reconciliation_corrections` rows to a separate `_sandbox_corrections_preview` view WITHOUT mutating journal; operator-driven trial run pre-production-ship.

### §I.8 `daily_management_records.superseded_by_correction_id` column

Per spec §9.4 V1 LOCK. V2 candidate: mirror `review_log.superseded_by_correction_id` if Phase 10 metric materializes on snapshot replay AND that metric is operationally important.

### §I.9 Phase 6 re-review UI surface

Per spec §9.1: auto-correction marks `review_log.superseded_by_correction_id`; operator can opt to re-review via Phase 6 surface. V2 candidate: web UI on `/reviews/{id}` shows a "Reconciliation correction applied since this review" badge with a "Re-review" button.

### §I.10 Spec OQ-7 wording cleanup (V2.1 §VII.F amendment candidate)

Per §A.5 verified count: 14 VM instances across 9 files (NOT 10 as spec OQ-7 wording asserts). Banked for spec §VII.F amendment at next spec-revision opportunity.

### §I.11 Per-row correction-policy stamp legacy backfill

Per spec §3.1 `risk_policy_id_at_correction` nullable + SET NULL discipline. V2 candidate: a defensive backfill UPDATE rewrites NULL `risk_policy_id_at_correction` rows to the policy_id active at `applied_at` (best-effort if Phase 10 metric requires the stamp on every correction row).

### §I.12 `--dry-run --no-pass-2` Schwab-quota-free preview

Per spec §8.2 + T-D.8 acceptance: V1 dry-run with Pass 2 enabled re-fetches Schwab (audit-row writes happen even in dry-run). V2 candidate: dedicated "no-audit preview" mode that caches Pass-2 responses in memory + skips audit-row writes; operator-driven idempotent preview re-runs without consuming API quota or polluting the audit table.

### §I.13 Dedicated `candidate_choices_json` column on `reconciliation_discrepancies`

Per T-D.2 acceptance criteria #4 + Codex R-likely surface: V1 stores parametric `pick_schwab_record_<N>` candidate list inside `resolution_reason` (free-text). V2 candidate: add a dedicated `candidate_choices_json TEXT NULL` column to `reconciliation_discrepancies` so the Tier-2 UI can render rich candidate-comparison views.

### §I.14 `'__no_mutation__'` sentinel in `field_name` (spec §3.1.1 amendment candidate)

Per T-C.3 acceptance criteria #5: writing-plans LOCKS the `'__no_mutation__'` sentinel for tier-2 no-mutation outcomes (`keep_journal_as_is`, `mark_unmatched`, `acknowledge`). Spec §3.1.1 only enumerates `'__delete__'` + `'__insert__'` sentinels; the no-mutation outcome's audit-row `field_name` needs its own marker. Banked at V2.1 §VII.F (writing-plans-introduced sentinel; spec amendment to document).

### §I.15 Spec §5.7 tier-3 validator-chain re-run amendment

Per T-C.4 acceptance criteria #10: writing-plans LOCKS that tier-3 ALSO runs validator chain on operator-truth value (defense-in-depth — operator-truth must still pass schema invariants). Spec §5.7 didn't explicitly enumerate this step. Banked at V2.1 §VII.F (spec amendment).

---

## §J Forward-binding lessons for executing-plans dispatches

Per spec §15.4 inheritance + plan-author additions during writing-plans drafting:

1. **Transactional discipline three-piece family preserved** (Phase 8 lesson family; Phase 9 Sub-bundle B precedent): caller-controlled at repo layer; transaction-owning at service layer; reject caller-held-tx at any single-transaction service. Sub-bundle C.C inherits via `apply_tier1_correction` (own-tx) + `_apply_tier1_correction_inner` (caller-tx) outer/inner split per spec §7.3.

2. **SQLite `INSERT OR REPLACE` prohibition** on FK-referenced + audit-trail tables (existing CLAUDE.md gotcha). Inherited; all Sub-bundle C writes use UPDATE-only on existing rows + INSERT for new audit rows.

3. **Service-layer `with conn:` opens its own transaction — do NOT compose from inside outer single-transaction.** Inherited; spec §7.3 + T-C.5/6 pivot calls `_apply_tier1_correction_inner` (caller-tx) NOT the public `apply_tier1_correction` (own-tx).

4. **Cross-column CHECK at schema time + app-layer enforcement at service time** (Phase 9 §3.1 R1 Minor #4 precedent extended). T-A.1 cross-column CHECK on `(ambiguity_kind, resolution)` defense-in-depth; T-C.2/3 service-layer enforcement at write-time.

5. **Per-row policy stamping** (Phase 8 R1 M5 lesson). T-A.1 `risk_policy_id_at_correction` per-row stamp at write-time so future policy edits don't reinterpret the validator chain that approved this correction.

6. **Phase 11 forward-binding lesson #2 (broaden the catch at pipeline boundary)** for graceful degradation. T-C.5/6 reconciliation flow pivot catches broad exceptions + logs WARNING + leaves discrepancy unresolved; pipeline NEVER crashes.

7. **Phase 11 forward-binding lesson #6 (`apply_overrides(cfg)` at Schwab entry points)** preserved through Sub-bundle C's Schwab consumption: backfill Pass 2's `get_account_orders` call site inherits via `_construct_pipeline_schwab_client(cfg)` (single Schwab client construction point; cfg-cascade applied there).

8. **Phase 12 Sub-bundle A T-A.3 implementer-gap pre-emption pattern**: any new entry point threading Schwab client through multiple call sites MUST mock the constructor + assert cascade-resolved Schwab credentials are threaded through. T-C.5 + T-D.8 inherit via discriminating tests.

9. **Phase 12 Sub-bundle B forward-binding lesson #6: `apply_overrides()` discipline at Schwab entry points project-wide invariant candidate** — Sub-bundle C's auto-correction service that may directly construct `schwabdev.Client(...)` (if any) inherits. T-C.5/6 + T-D.8 reuse `_construct_pipeline_schwab_client(cfg)` rather than direct construction; if any future task adds direct construction, it MUST `apply_overrides(cfg)` at the entry point.

10. **Brief-premise empirical-verification** (Phase 11 + Phase 12 Sub-bundle C brainstorm lesson #5): writing-plans verified all 3 shipped CHECK enums + 8 brief §0.5 pre-verification items + the spec OQ-7 retrofit count against shipped state (§A.5 surfaced the spec's "10 VMs" vs actual 14 instances drift). Sub-sub-bundle executing-plans dispatches inherit; any claimed shipped surface MUST be grep-verified BEFORE locking code-content at task-acceptance level.

11. **Determinism principle is the binding discriminator** (spec §1.3 + §4.4 LOCK). Classifier defaults to tier-2 when in doubt. False-positive tier-1 silently corrupts journal; false-positive tier-2 just defers to operator. Apply to any future classification surface (e.g., V2 mapper widening): determinism — not magnitude — is the axis.

12. **Synthetic-fixture-only acceptance test for production-write-contract surfaces** (Phase 12 Sub-bundle C brainstorm lesson #4). C.D gate's `--custom-value` contract acceptance test (T-D.11 + §G.4 S6a) uses isolated-DB synthetic-fixture pathway; production DHC/VSAT cases dispositioned per operator's real data without contortion. Pattern: when an operator-facing surface enforces a payload contract, the contract test runs against a synthetic fixture in an isolated DB — production cases are operator-decisioned per real data.

13. **Cross-bundle base-layout VM pin discipline** (Phase 10 forward-binding lesson #10 inheritance). Sub-bundle C.D T-D.10 widens the helper predicate; all 14 base-layout VM instances pick up the count via the shared helper; discriminating regression test per VM file ensures no silent drift.

14. **SAVEPOINT-per-discrepancy discipline** (Sub-bundle C ship-time lesson; new addition). Reconciliation flow pivots in T-C.5/6 wrap each per-discrepancy classify+apply iteration in `SAVEPOINT correction_sp_<id>` so per-iteration failures don't poison the outer transaction. Any future nested-side-effect pattern with mixed success/fail outcomes inherits this discipline.

15. **Per-(kind, choice_code) handler registry exhaustiveness regression test** (Sub-bundle C ship-time lesson; new addition). T-D.5 ships an exhaustive regression test that asserts EVERY (ambiguity_kind, choice_code) pair has matching menu entry + service handler. Inherit for any future handler-keyed dispatch architecture: ship an exhaustiveness regression test alongside the registry.

---

## §K Spec §15 hand-off checklist verification

This section confirms plan §A through §J coverage of every spec §15 item.

### §K.1 Spec §15.1 — 13 BINDING items: covered

Per §0.3 above — each item maps to plan §B/C/D/E task IDs.

### §K.2 Spec §15.2 — 15 OQ disposition: covered

Per §0.4 above — each OQ has plan-author posture; default-recommendation-accepted vs orchestrator-escalated documented.

### §K.3 Spec §15.3 — 8 pre-verifications: covered

Per §A.1 through §A.9 — each verification has verbatim grep result + plan binding underwritten.

### §K.4 Spec §15.4 — 10 forward-binding lessons: covered + extended

Per §J — 15 total forward-binding lessons (10 from spec §15.4 + 5 new from writing-plans drafting).

### §K.5 Spec §15.5 — per-sub-sub-bundle gate plans (4 + 3 + 4 + 10 = 21 surfaces): covered

Per §G.1 through §G.4 — each gate plan enumerates the surfaces verbatim with operator-driven walkthrough steps.

### §K.6 Spec OUT-OF-SCOPE items honored

Per §0.6 — V2 mapper widening + fill auto-population + web Tier-2 + magnitude-based thresholds + retroactive rewriting + Phase 7 state-machine extension + reconciliation_runs.state extension + fills.reconciliation_status widening are all OUT-OF-SCOPE per spec; no in-scope tasks propose them.

### §K.7 V2 candidates carry-forward: covered

Per §I — 15 V2 candidates banked (12 from brief + 3 from writing-plans drafting).

### §K.8 Plan size + executing-plans readiness

Plan total: ~2700-2900 lines (matches target per brief §0.2 + §1.3 expectations). Each sub-sub-bundle's task decomposition supports `copowers:executing-plans` dispatch with worktree isolation per Phase 9/10/11/12-A/12-B precedent.

---

## §L Plan completion checklist (self-review per superpowers:writing-plans skill)

- [x] **§1 Spec coverage:** Each spec §15.1 BINDING item maps to a plan task (§0.3 table).
- [x] **§2 Placeholder scan:** No "TBD" / "implement later" / "add error handling" / "similar to Task N" — all task acceptance criteria are concrete.
- [x] **§3 Type consistency:** `ClassificationResult` shape consistent across §C T-B.1 + §D T-C.2/3/4 references; `CorrectionResult` shape consistent across §D + §E references; `ChoiceMenuItem` shape consistent across T-D.2 + T-D.3 + T-D.5 references.
- [x] **§4 Spec coverage of §1.3 LOCKED architectural constraints:** All 4 operator-locked constraints (Schwab-truth + three-tier + determinism-axis + acknowledged_immaterial back-compat) preserved across §B/C/D/E task acceptance.
- [x] **§5 Spec coverage of §10 walkthroughs:** CVGI 41 walked through T-B.3 + T-C.2 + T-D.7 + §G.4 S3; DHC 39 walked through T-B.4 + T-C.3 + T-D.8 + §G.4 S4/S5/S6; VSAT 40 walked through T-B.4 + T-C.3 + T-D.8 + §G.4 S7.
- [x] **§6 OUT-OF-SCOPE items honored:** §0.6 enumerates; no in-scope task violates.
- [x] **§7 Cross-bundle pin matrix complete:** §F.1 table covers F-1 through F-10.
- [x] **§8 Operator-witnessed gate plans complete:** §G covers all 4 + 3 + 4 + 10 = 21 surfaces.
- [x] **§9 V2 candidates banked:** §I covers 15 candidates with explicit cross-references to spec §14 + brief §0.6 + plan-author additions.
- [x] **§10 Forward-binding lessons enumerated:** §J covers 15 lessons (10 spec + 5 plan-author).
- [x] **§11 Plan line target:** ~2700-2900 lines, within brief §1.3 target (~2200-2900 lines).

---

**END OF PLAN**

Sub-sub-bundle C.A executing-plans dispatch UNBLOCKED upon plan ship + `NO_NEW_CRITICAL_MAJOR` from adversarial Codex review.




