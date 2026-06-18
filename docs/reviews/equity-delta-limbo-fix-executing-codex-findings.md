# Codex executing review — equity_delta limbo-routing fix

Tier: review-strong (fallback path: -p profile absent, so -c model_reasoning_effort=high passed explicitly).
Model: gpt-5.5  |  reasoning effort: high  |  sandbox: read-only (repo read-access + diff/refgraph via stdin).
Base for diff: 91a14083 (worktree branch point).
Convergence: round 1 -> NO_NEW_CRITICAL_MAJOR (5-round cap suspended; converged round 1, no padding).

Adjudication summary + the persisted .copowers-findings.md disposition are reproduced after the verbatim transcript.

---

## Round 1 — verbatim Codex transcript (.codex-review-r1.txt)

```
OpenAI Codex v0.135.0
--------
workdir: /mnt/c/Users/rwsmy/swing-trading/.worktrees/equity-delta-limbo-exec
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019eda62-07d8-7c11-90c7-7e1196117c71
--------
user
# Adversarial review — equity_delta limbo-routing fix (executing, review-strong, PRODUCTION code)

You are an adversarial code reviewer. Review the DIFF below (a one-line skip-set
widen + a new test module) against the supplied REFERENCE GRAPH (the un-changed
surrounding pivot/resolver/schema the fix's correctness depends on — you cannot
run git; everything you need is inline). Run to convergence: report new
critical/major findings; if none, emit the exact line `NO_NEW_CRITICAL_MAJOR`.

## The settled design (do NOT re-open it)
A fired `equity_delta` (an account-level ledger-vs-NLV coherence discrepancy)
was flowing the reconciliation classify/dispatch pivot
(`_pivot_classify_and_dispatch_for_run`), getting classified tier-2
(`_classify_equity_delta` -> `field_shape_incompatible`), and the pivot's
else-branch stamped it `pending_ambiguity_resolution` (the tier-2 fill-matching
limbo — the WRONG, uncleanable state). The fix (the 18-H.6.1 twin) widens the
pivot's existing `untracked_broker_position` skip-set to also skip
`equity_delta` so it stays `unresolved` (run-level-counted + CLI-clearable via
the existing manual resolver `resolve_discrepancy` -> `acknowledged_immaterial`).

## BINDING SCOPE (these are settled rulings — adjudicate findings against them)
- **CHARC Sec-0 RULING = (A):** the fix is CLEANABILITY ONLY. `equity_delta` has
  been `MATERIAL_BY_TYPE["equity_delta"]=0` since Phase 9, so the material-banner
  EXCLUSION is CORRECT-BY-DESIGN. There is **NO** `MATERIAL_BY_TYPE` change and
  there MUST NOT be one (that is a deferred, separate decision (B), NOT this arc).
  A finding that the equity_delta "should" enter the material banner is OUT OF
  SCOPE.
- **C1:** extend the skip to `equity_delta` ONLY; every other discrepancy type's
  classify/dispatch must stay byte-identical.
- **C3 is TEST-ONLY:** the existing `resolve_discrepancy` already clears a
  `pending_ambiguity_resolution` equity_delta (auto-NULLing `ambiguity_kind` via
  `clear_ambiguity_kind`). NO resolver code change is in scope.
- **C4:** the ONLY production touch is `_pivot_classify_and_dispatch_for_run`.
  NO schema, NO migration, NO new module.

## What to scrutinize (production blast radius)
1. Does the widened skip-set leave ANY path by which a fired `equity_delta`
   still reaches `pending_ambiguity_resolution` (or any tier-2/tier-1 stamp)?
2. Does the skip touch any OTHER discrepancy type's dispatch (C1 violation)?
3. Is the post-pivot `unresolved_discrepancies_count` recompute correct for an
   `equity_delta` that now stays `unresolved`?
4. Are the tests genuinely discriminating (pass post-fix, fail pre-fix) and
   non-vacuous (the C1 stop_mismatch lock actually reaches the sub-classifier;
   the firing fixtures actually FIRE on the asserted basis)?
5. Any correctness defect in the fix that depends on the surrounding (un-diffed)
   reference graph.

## Adjudication note (binding, recipe Sec-3)
A finding premised SOLELY on a value the WRITE boundary verifiably prevents
(a schema CHECK/UNIQUE/NOT NULL/FK, a migration, or a constrained writer) is
NON-blocking IF the exact constraint is cited. Otherwise it stays in-scope.

The DIFF and the REFERENCE GRAPH follow.
diff --git a/swing/trades/schwab_reconciliation.py b/swing/trades/schwab_reconciliation.py
index 56ac67b3..f0a0dc9c 100644
--- a/swing/trades/schwab_reconciliation.py
+++ b/swing/trades/schwab_reconciliation.py
@@ -578,29 +578,34 @@ def _pivot_classify_and_dispatch_for_run(
         return
 
     for disc in discrepancies:
         # Only act on still-unresolved rows — pre-resolved rows (rare
         # via pre-Phase-12 import paths) are passed-through.
         if disc.resolution != "unresolved":
             continue
 
-        # Phase 18 Arc 18-H.6.1 Part 3 — an `untracked_broker_position`
-        # (18-H.6, all-FK-null orphan) is NOT a fill-matching ambiguity. It
-        # has no sub-classifier, so classify_discrepancy would return tier-2
-        # 'unsupported' -> the else-branch below would stamp
-        # `pending_ambiguity_resolution` (the wrong limbo: there is no
-        # broker-vs-journal RECORD to disposition, only an untracked holding
-        # the operator must journal). Skip the classify/dispatch entirely so
-        # the orphan stays `unresolved` — a real unaddressed finding that
-        # banners (Part 1) and is cleared via the manual resolver
-        # (`resolve_discrepancy` -> `acknowledged_immaterial`, Part 2) once
-        # the operator journals the position. Every OTHER discrepancy type's
+        # Phase 18 Arc 18-H.6.1 Part 3 + the equity_delta limbo-routing fix
+        # (the 18-H.6.1 twin) — neither `untracked_broker_position` (18-H.6,
+        # all-FK-null orphan) nor `equity_delta` (an account-level
+        # ledger-vs-NLV coherence discrepancy) is a fill-matching ambiguity:
+        # there is no broker-vs-journal RECORD to disposition. The orphan has
+        # no sub-classifier (tier-2 'unsupported'); `equity_delta` DOES have a
+        # sub-classifier (`_classify_equity_delta` -> tier-2
+        # 'field_shape_incompatible'); EITHER way the else-branch below would
+        # stamp `pending_ambiguity_resolution` (the wrong, uncleanable limbo).
+        # Skip the classify/dispatch entirely so both stay `unresolved` — real
+        # unaddressed findings that are run-level-counted and cleared via the
+        # manual resolver (`resolve_discrepancy` -> `acknowledged_immaterial`)
+        # once the operator acknowledges them. Every OTHER discrepancy type's
         # classify/dispatch behavior below is byte-identical (C1).
-        if disc.discrepancy_type == "untracked_broker_position":
+        if disc.discrepancy_type in (
+            "untracked_broker_position",
+            "equity_delta",
+        ):
             continue
 
         sp_name = f"correction_sp_{disc.discrepancy_id}"
         conn.execute(f"SAVEPOINT {sp_name}")
         try:
             source_payload = _extract_source_payload(disc, schwab_orders)
             journal_row = _fetch_journal_row(conn, disc)
             affected_table = _resolve_affected_table(disc)
diff --git a/tests/trades/test_equity_delta_limbo_routing.py b/tests/trades/test_equity_delta_limbo_routing.py
new file mode 100644
index 00000000..838ebd5a
--- /dev/null
+++ b/tests/trades/test_equity_delta_limbo_routing.py
@@ -0,0 +1,381 @@
+"""equity_delta limbo-routing fix — the 18-H.6.1 pivot-skip pattern.
+
+A fired ``equity_delta`` (an account-level ledger-vs-NLV coherence
+discrepancy) used to flow the reconciliation classify/dispatch pivot,
+get classified tier-2 (``_classify_equity_delta`` -> ``field_shape_incompatible``),
+and the pivot's else-branch stamped it ``pending_ambiguity_resolution`` (the
+tier-2 fill-matching limbo — the WRONG state: an ``equity_delta`` is not a
+broker-vs-journal fill RECORD to disposition, and that limbo is uncleanable
+via the legitimate operator surfaces). The live witness is run-59 id 71.
+
+The fix (CHARC settled, the 18-H.6.1 twin): widen the pivot's existing
+``untracked_broker_position`` skip-set to also skip ``equity_delta`` so a
+fired ``equity_delta`` stays ``unresolved`` — a real unaddressed coherence
+finding that is run-level-counted + CLI-clearable via the existing manual
+resolver (``resolve_discrepancy`` -> ``acknowledged_immaterial``).
+
+CHARC Sec-0 RULING = (A): cleanability. ``equity_delta`` has been
+``MATERIAL_BY_TYPE=0`` since Phase 9 -> the material-banner EXCLUSION is
+correct-by-design (test (b)(iii) is a SCOPE LOCK, not the distinguisher).
+NO ``MATERIAL_BY_TYPE`` change; the arc stays the single-line pivot skip.
+
+Fixtures are built from the REAL emitter path (``run_schwab_reconciliation``
+for the firing fixtures; a focused direct ``_pivot_classify_and_dispatch_for_run``
+call for the C1 lock; a raw-insert for the C3 legacy-limbo seed).
+"""
+from __future__ import annotations
+
+import sqlite3
+from dataclasses import dataclass
+from pathlib import Path
+from typing import Any
+
+import pytest
+
+from swing.data.db import ensure_schema
+from swing.data.repos.reconciliation import (
+    get_discrepancy,
+    list_discrepancies_for_run,
+)
+from swing.metrics.discrepancies import count_unresolved_material
+from swing.trades.reconciliation import resolve_discrepancy
+from swing.trades.schwab_reconciliation import (
+    _pivot_classify_and_dispatch_for_run,
+    run_schwab_reconciliation,
+)
+
+_SWING_BASIS = "net_liq_minus_declared_oof"
+
+
+@dataclass
+class _SchwabAccount:
+    net_liquidating_value: float | None = None
+    positions: list[Any] | None = None
+
+
+def _position(
+    symbol: str,
+    *,
+    long_qty: float = 0.0,
+    market_value: float | None = None,
+) -> dict:
+    """The REAL Schwab position dict (sibling top-level ``marketValue``)."""
+    return {
+        "shortQuantity": 0.0,
+        "longQuantity": long_qty,
+        "instrument": {"symbol": symbol, "type": "EQUITY"},
+        "marketValue": market_value,
+    }
+
+
+@pytest.fixture
+def conn(tmp_path: Path) -> sqlite3.Connection:
+    return ensure_schema(tmp_path / "equity_delta_limbo.db")
+
+
+def _run(
+    conn: sqlite3.Connection,
+    positions: list[dict],
+    *,
+    nlv: float | None,
+    starting_equity: float = 1000.0,
+    out_of_framework: tuple[str, ...] = (),
+):
+    acct = _SchwabAccount(net_liquidating_value=nlv, positions=positions)
+    return run_schwab_reconciliation(
+        conn,
+        account_hash="<acct>",
+        period_start="2026-06-15",
+        period_end="2026-06-15",
+        schwab_orders=[],
+        schwab_transactions=[],
+        schwab_account=acct,
+        out_of_framework_tickers=out_of_framework,
+        starting_equity=starting_equity,
+    )
+
+
+def _equity_delta_rows(conn: sqlite3.Connection, run_id: int):
+    return [
+        d
+        for d in list_discrepancies_for_run(conn, run_id)
+        if d.discrepancy_type == "equity_delta"
+    ]
+
+
+# --------------------------------------------------------------------------- #
+# Test (a) — the LOAD-BEARING distinguisher: a fired SWING-SCOPED equity_delta
+# (the id-71 path) stays `unresolved`, not `pending_ambiguity_resolution`.
+# --------------------------------------------------------------------------- #
+
+
+def test_fired_swing_scoped_equity_delta_stays_unresolved_not_pending_ambiguity(
+    conn: sqlite3.Connection,
+):
+    """Test (a) — REQUIRED swing-scoped fixture (the live id-71 path).
+
+    nlv = 392.51 (declared SPCX mv) + 1500.00; swing_nlv = 1500.00;
+    ledger = starting 1000.00; |1000 - 1500| = 500.00;
+    tol = max(5, 0.5%*1500) = 7.50; 500 > 7.50 -> FIRES on the swing basis.
+
+    Pre-fix arithmetic: the pivot calls classify_discrepancy(equity_delta) ->
+    _classify_equity_delta -> tier=2, field_shape_incompatible -> the
+    else-branch stamps `pending_ambiguity_resolution`. Assertion (2) would
+    FAIL (resolution == 'pending_ambiguity_resolution').
+    Post-fix arithmetic: the widened skip-set `continue`s past the
+    equity_delta -> it stays `unresolved`. Assertion (2) PASSES. Distinguishes.
+    """
+    run = _run(
+        conn,
+        [_position("SPCX", long_qty=2.0, market_value=392.51)],
+        nlv=1892.51,
+        starting_equity=1000.00,
+        out_of_framework=("SPCX",),
+    )
+    rows = _equity_delta_rows(conn, run.run_id)
+    # (1) exactly one equity_delta fired AND it is the SWING-SCOPED basis
+    # (proves the §2.4 path, not the legacy both-flat basis / a C2-degrade).
+    assert len(rows) == 1
+    import json
+
+    actual = json.loads(rows[0].actual_value_json)
+    assert actual["basis"] == _SWING_BASIS
+    # (2) post-fix: it stays unresolved (NOT pending_ambiguity_resolution).
+    assert rows[0].resolution == "unresolved"
+
+
+def test_fired_legacy_both_flat_equity_delta_stays_unresolved(
+    conn: sqlite3.Connection,
+):
+    """Test (1b) — the legacy both-flat firing basis also routes to unresolved.
+
+    nlv = 1100.00; ledger = 1000.00; |1000 - 1100| = 100;
+    tol = max(5, 0.5%*1100=5.5) = 5.5; 100 > 5.5 -> FIRES on basis 'net_liq'.
+
+    Same pre/post distinguisher as test (a): pre-fix stamped
+    `pending_ambiguity_resolution`; post-fix stays `unresolved`. Proves BOTH
+    firing bases route to `unresolved` post-fix (the pivot dispatches on
+    discrepancy_type, not basis — but this pins both rather than assuming).
+    """
+    run = _run(conn, [], nlv=1100.00, starting_equity=1000.00)
+    rows = _equity_delta_rows(conn, run.run_id)
+    assert len(rows) == 1
+    import json
+
+    actual = json.loads(rows[0].actual_value_json)
+    assert actual["basis"] == "net_liq"
+    assert rows[0].resolution == "unresolved"
+
+
+# --------------------------------------------------------------------------- #
+# Test (b) — the unresolved equity_delta is run-level-counted + CLI-clearable;
+# (iii) the material-banner exclusion is correct-by-design (a SCOPE LOCK).
+# --------------------------------------------------------------------------- #
+
+
+def test_fired_equity_delta_counts_in_run_unresolved_count_and_clearable(
+    conn: sqlite3.Connection,
+):
+    """Test (b) — C2 satisfied by the run-level count + the clearable path.
+
+    Reuses the swing-scoped fixture (test (a)).
+    (i)   run.unresolved_discrepancies_count includes the equity_delta.
+          Pre-fix: stamped pending_ambiguity_resolution -> the post-pivot
+          recompute (COUNT WHERE resolution='unresolved') excludes it -> 0.
+          Post-fix: stays unresolved -> the recompute counts it -> 1.
+          Distinguishes.
+    (ii)  resolve_discrepancy(... acknowledged_immaterial) clears it.
+    (iii) SCOPE LOCK (CHARC Sec-0 = A): the fired equity_delta is ABSENT from
+          count_unresolved_material because material_to_review=0 since Phase 9.
+          This is correct-by-design — NOT a missing feature, NOT the pre/post
+          distinguisher (it does not change pre-vs-post; it locks scope).
+    """
+    run = _run(
+        conn,
+        [_position("SPCX", long_qty=2.0, market_value=392.51)],
+        nlv=1892.51,
+        starting_equity=1000.00,
+        out_of_framework=("SPCX",),
+    )
+    rows = _equity_delta_rows(conn, run.run_id)
+    assert len(rows) == 1
+    disc = rows[0]
+
+    # (i) run-level unresolved count includes the equity_delta.
+    assert run.unresolved_discrepancies_count == 1
+
+    # (iii) SCOPE LOCK — material-banner exclusion correct-by-design (material=0).
+    assert disc.material_to_review == 0
+    assert count_unresolved_material(conn) == 0
+
+    # (ii) CLI-clearable via the existing manual resolver.
+    resolve_discrepancy(
+        conn,
+        discrepancy_id=disc.discrepancy_id,
+        resolution="acknowledged_immaterial",
+        resolution_reason="acknowledged coherence drift",
+    )
+    assert (
+        get_discrepancy(conn, disc.discrepancy_id).resolution
+        == "acknowledged_immaterial"
+    )
+
+
+# --------------------------------------------------------------------------- #
+# Test (c) — C1 LOCK: an unrelated sub-classified type still flows the FULL
+# savepoint+classify+dispatch path + reaches its REAL non-vacuous disposition.
+# --------------------------------------------------------------------------- #
+
+
+def _seed_trade(conn: sqlite3.Connection, *, ticker: str) -> int:
+    cur = conn.execute(
+        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
+        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at) "
+        "VALUES (?, '2026-04-27', 10.0, 100, 9.0, 9.0, 'managing', "
+        "'manual_off_pipeline', '2026-04-27T16:00:00')",
+        (ticker,),
+    )
+    return int(cur.lastrowid)
+
+
+def _raw_insert_stop_mismatch(
+    conn: sqlite3.Connection, *, run_id: int, trade_id: int, ticker: str
+) -> int:
+    """Raw-insert an unresolved stop_mismatch (actual_value_json NULL) so the
+    pivot's _extract_source_payload yields None -> _classify_stop_mismatch
+    returns tier-2 schwab_returned_no_match (a REAL, deterministic, non-vacuous,
+    NON-`unsupported` disposition)."""
+    return int(
+        conn.execute(
+            "INSERT INTO reconciliation_discrepancies ("
+            "run_id, discrepancy_type, trade_id, ticker, field_name, "
+            "material_to_review, resolution, created_at"
+            ") VALUES (?, 'stop_mismatch', ?, ?, 'current_stop', 1, "
+            "'unresolved', '2026-06-15T09:00:00')",
+            (run_id, trade_id, ticker),
+        ).lastrowid
+    )
+
+
+def test_unrelated_sub_classified_type_still_dispatches_post_skip(
+    conn: sqlite3.Connection,
+):
+    """Test (c) — the C1 lock (NO vacuous-pass escape hatch).
+
+    A stop_mismatch (sub-classified by _classify_stop_mismatch) with no
+    matching Schwab order (schwab_orders=[]) flows the FULL pivot path and
+    reaches its REAL tier-2 disposition: resolution ==
+    'pending_ambiguity_resolution' with ambiguity_kind == 'schwab_returned_no_match'
+    (NOT 'unsupported', NOT skipped — proving the sub-classifier actually ran).
+
+    Pre==post (the LOCK): the skip-set never matched stop_mismatch; widening it
+    to add equity_delta cannot touch the stop_mismatch dispatch path. The
+    asserted disposition is identical under both the pre-edit and post-edit
+    pivot — that identity, with the non-vacuity assertion, IS the C1 lock.
+    """
+    from swing.data.repos.reconciliation import insert_run
+
+    trade_id = _seed_trade(conn, ticker="ABC")
+    run_id = insert_run(
+        conn,
+        source="schwab_api",
+        started_ts="2026-06-15T09:00:00.000",
+        state="running",
+    )
+    did = _raw_insert_stop_mismatch(
+        conn, run_id=run_id, trade_id=trade_id, ticker="ABC"
+    )
+    conn.commit()
+
+    counters: dict[str, int] = {}
+    with conn:
+        _pivot_classify_and_dispatch_for_run(
+            conn,
+            run_id=run_id,
+            schwab_orders=[],
+            schwab_api_call_id=None,
+            environment="production",
+            counters=counters,
+        )
+
+    disc = get_discrepancy(conn, did)
+    # Non-vacuity: it reached the sub-classifier's REAL tier-2 outcome.
+    assert disc.resolution == "pending_ambiguity_resolution"
+    assert disc.ambiguity_kind == "schwab_returned_no_match"
+    assert counters.get("tier2_pending_count", 0) == 1
+
+
+# --------------------------------------------------------------------------- #
+# Test (d) — C3 (test-only, NO resolver code): a raw-inserted legacy-limbo
+# equity_delta (id-71 shape) is clearable by the EXISTING resolver.
+# --------------------------------------------------------------------------- #
+
+
+def _raw_insert_pending_ambiguity_equity_delta(
+    conn: sqlite3.Connection, *, run_id: int
+) -> int:
+    """Plant an equity_delta in the LEGACY pending_ambiguity_resolution state
+    (the id-71 shape: ambiguity_kind='field_shape_incompatible'). RAW insert is
+    mandatory — the cross-column CHECK requires ambiguity_kind IS NOT NULL for
+    this resolution, AND the manual resolver REJECTS setting
+    pending_ambiguity_resolution, so it cannot be planted via any write-path
+    (the cross-arc write-barrier lesson)."""
+    return int(
+        conn.execute(
+            "INSERT INTO reconciliation_discrepancies ("
+            "run_id, discrepancy_type, trade_id, fill_id, cash_movement_id, "
+            "ticker, field_name, expected_value_json, actual_value_json, "
+            "delta_text, material_to_review, resolution, ambiguity_kind, "
+            "resolution_reason, created_at"
+            ") VALUES (?, 'equity_delta', NULL, NULL, NULL, NULL, "
+            "'net_liquidating_value', "
+            "'{\"equity_dollars\": 1000.0, \"basis\": \"ledger\"}', "
+            "'{\"equity_dollars\": 1500.0, \"swing_nlv\": 1500.0, "
+            "\"basis\": \"net_liq_minus_declared_oof\"}', "
+            "'$+500.00 (ledger minus swing_nlv)', 0, "
+            "'pending_ambiguity_resolution', 'field_shape_incompatible', "
+            "'classifier: field_shape_incompatible', '2026-06-15T09:00:00')",
+            (run_id,),
+        ).lastrowid
+    )
+
+
+def test_legacy_pending_ambiguity_equity_delta_clearable_to_acknowledged_immaterial(
+    conn: sqlite3.Connection,
+):
+    """Test (d) — C3: the EXISTING resolver clears a legacy-limbo equity_delta.
+
+    Mirrors test_resolve_orphan_discrepancy.py's
+    test_resolve_legacy_pending_ambiguity_orphan_clears_ambiguity_kind (the
+    exact twin precedent). The resolver clears ambiguity_kind in the same
+    UPDATE so the migration-0031 cross-column CHECK permits the transition.
+    No resolver CODE change — this pins that the equity_delta variant is
+    already covered by the existing path.
+
+    Distinguishing: an impl that left ambiguity_kind non-NULL ->
+    acknowledged_immaterial + non-NULL ambiguity_kind violates the CHECK ->
+    IntegrityError. On `main` it resolves cleanly + ambiguity_kind is NULL.
+    """
+    from swing.data.repos.reconciliation import insert_run
+
+    run_id = insert_run(
+        conn,
+        source="schwab_api",
+        started_ts="2026-06-15T09:00:00.000",
+        state="completed",
+        finished_ts="2026-06-15T09:00:01.000",
+        unresolved_discrepancies_count=0,
+    )
+    did = _raw_insert_pending_ambiguity_equity_delta(conn, run_id=run_id)
+    conn.commit()
+
+    resolve_discrepancy(
+        conn,
+        discrepancy_id=did,
+        resolution="acknowledged_immaterial",
+        resolution_reason="Clearing the legacy pending equity_delta (id-71 shape).",
+    )
+
+    disc = get_discrepancy(conn, did)
+    assert disc.resolution == "acknowledged_immaterial"
+    assert disc.ambiguity_kind is None
===== REFERENCE GRAPH (un-changed surrounding code the fix's correctness depends on) =====

----- swing/trades/schwab_reconciliation.py:550-820 (the pivot loop: skip, classify, dispatch, tier-2 else stamp) -----
def _pivot_classify_and_dispatch_for_run(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    schwab_orders: list[Any],
    schwab_api_call_id: int | None,
    environment: str | None,
    counters: dict[str, int],
) -> None:
    """Spec §7.1 LOCKED pivot — savepoint-per-discrepancy classify +
    dispatch. Called inside the outer reconciliation_run transaction
    AFTER all emitters have landed; the function NEVER raises out
    (graceful-degradation per spec §7.4), EXCEPT for
    :class:`InvalidOverrideComboError` (developer-bug signal per Phase
    12.5 #1 spec §7.4 R4 M2 LOCK + plan §F invariant F16 + F21) which
    propagates out so the overall reconciliation_run fails-fast at
    integration time rather than being hidden inside
    ``tier_errored_count`` graceful-degradation.
    """
    counters.setdefault("tier1_applied_count", 0)
    counters.setdefault("tier2_pending_count", 0)
    counters.setdefault("tier_errored_count", 0)
    counters.setdefault("tier1_multi_leg_auto_redirected_count", 0)
    counters.setdefault("sandbox_auto_redirect_skipped_count", 0)

    # Read the newly-emitted discrepancies for this run.
    discrepancies = repo.list_discrepancies_for_run(conn, run_id=run_id)
    if not discrepancies:
        return

    for disc in discrepancies:
        # Only act on still-unresolved rows — pre-resolved rows (rare
        # via pre-Phase-12 import paths) are passed-through.
        if disc.resolution != "unresolved":
            continue

        # Phase 18 Arc 18-H.6.1 Part 3 + the equity_delta limbo-routing fix
        # (the 18-H.6.1 twin) — neither `untracked_broker_position` (18-H.6,
        # all-FK-null orphan) nor `equity_delta` (an account-level
        # ledger-vs-NLV coherence discrepancy) is a fill-matching ambiguity:
        # there is no broker-vs-journal RECORD to disposition. The orphan has
        # no sub-classifier (tier-2 'unsupported'); `equity_delta` DOES have a
        # sub-classifier (`_classify_equity_delta` -> tier-2
        # 'field_shape_incompatible'); EITHER way the else-branch below would
        # stamp `pending_ambiguity_resolution` (the wrong, uncleanable limbo).
        # Skip the classify/dispatch entirely so both stay `unresolved` — real
        # unaddressed findings that are run-level-counted and cleared via the
        # manual resolver (`resolve_discrepancy` -> `acknowledged_immaterial`)
        # once the operator acknowledges them. Every OTHER discrepancy type's
        # classify/dispatch behavior below is byte-identical (C1).
        if disc.discrepancy_type in (
            "untracked_broker_position",
            "equity_delta",
        ):
            continue

        sp_name = f"correction_sp_{disc.discrepancy_id}"
        conn.execute(f"SAVEPOINT {sp_name}")
        try:
            source_payload = _extract_source_payload(disc, schwab_orders)
            journal_row = _fetch_journal_row(conn, disc)
            affected_table = _resolve_affected_table(disc)
            affected_row_id = _resolve_affected_row_id(disc)
            # Build validator chain partial (kwargs-only binding).
            if affected_row_id is not None:
                validator_chain = _functools.partial(
                    default_validator_chain(conn),
                    affected_table=affected_table,
                    affected_row_id=affected_row_id,
                )
            else:
                validator_chain = None

            classification = classify_discrepancy(
                disc,
                source_payload=source_payload,
                journal_row=journal_row,
                validator_chain=validator_chain,
            )

            if classification.tier == 1:
                try:
                    result = _apply_tier1_correction_inner(
                        conn,
                        discrepancy_id=disc.discrepancy_id,
                        classification=classification,
                        schwab_api_call_id=schwab_api_call_id,
                        environment=environment,
                    )
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    # Plan §D.5 step 1 LOCK: increment counter ONLY when
                    # the inner returned a real correction_id. Sandbox
                    # short-circuit returns id=None → counter stays at 0
                    # naturally (no journal mutation occurred).
                    if result.correction_id is not None:
                        counters["tier1_applied_count"] += 1
                except ValidatorRejectedError as e:
                    # ROLLBACK TO undoes partial UPDATEs, but does NOT
                    # release the savepoint (SQLite semantics).
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    # Fall through to tier-2 stamp in a FRESH savepoint
                    # so failures here don't try to ROLLBACK TO an
                    # already-released sp_name (Codex R2 Minor #1).
                    fb_sp = f"correction_fallback_sp_{disc.discrepancy_id}"
                    conn.execute(f"SAVEPOINT {fb_sp}")
                    try:
                        _stamp_pending_ambiguity_inner(
                            conn,
                            discrepancy_id=disc.discrepancy_id,
                            ambiguity_kind="validator_rejected",
                            resolution_reason=str(e),
                        )
                        conn.execute(f"RELEASE SAVEPOINT {fb_sp}")
                        counters["tier2_pending_count"] += 1
                    except Exception as fb_exc:  # noqa: BLE001
                        with contextlib.suppress(sqlite3.Error):
                            conn.execute(
                                f"ROLLBACK TO SAVEPOINT {fb_sp}"
                            )
                            conn.execute(f"RELEASE SAVEPOINT {fb_sp}")
                        log.warning(
                            "tier-2 fallback stamp failed for discrepancy "
                            "%d: %s", disc.discrepancy_id, fb_exc,
                        )
                        counters["tier_errored_count"] += 1
            elif (
                classification.tier == 2
                and classification.auto_redirect_recipe is not None
            ):
                # Phase 12.5 #1 T-1.5 — multi-leg auto-redirect path.
                # Defensive future-proofing per F20: the initial pivot
                # cannot currently emit the recipe (source_payload reads
                # the persisted ``{"matched": null}`` sentinel for
                # ``unmatched_*_fill`` discrepancies; the classifier
                # treats that as the no-payload sentinel), so this branch
                # is a guard for any future emit-shape widening AND a
                # symmetry mirror of the backfill operational firing site
                # at ``reconciliation_backfill._handle_pass_2`` (where
                # ``_orders_to_classifier_payload`` builds the rich
                # list-shape source_payload from freshly-fetched Schwab
                # orders WITH execution-grain data).
                recipe = classification.auto_redirect_recipe
                try:
                    # Defense-in-depth: validate override combo BEFORE
                    # any mutation. Mirrors the T-1.4 service-layer
                    # guard. InvalidOverrideComboError MUST propagate
                    # per F21 (handled by the outer catch ladder below).
                    _validate_override_combo(
                        choice_code=recipe["choice_code"],
                        applied_by_override=recipe["applied_by_override"],
                        correction_action_override=recipe[
                            "correction_action_override"
                        ],
                        resolved_by_override=recipe["resolved_by"],
                    )
                    _stamp_pending_ambiguity_inner(
                        conn,
                        discrepancy_id=disc.discrepancy_id,
                        ambiguity_kind=classification.ambiguity_kind
                        or "multi_partial_vs_consolidated",
                        resolution_reason=classification.correction_reason,
                    )
                    _apply_tier2_resolution_inner(
                        conn,
                        discrepancy_id=disc.discrepancy_id,
                        choice_code=recipe["choice_code"],
                        operator_custom_payload=recipe["payload"],
                        operator_reason=(
                            f"multi-leg auto-redirect: "
                            f"{classification.correction_reason}"
                        ),
                        applied_by_override=recipe["applied_by_override"],
                        correction_action_override=recipe[
                            "correction_action_override"
                        ],
                        resolved_by_override=recipe["resolved_by"],
                        risk_policy_id=None,
                        schwab_api_call_id=schwab_api_call_id,
                        environment=environment or "production",
                    )
                    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    counters["tier1_multi_leg_auto_redirected_count"] += 1
                except _SandboxAutoRedirectShortCircuit:
                    # T-1.6 sandbox short-circuit. ROLLBACK TO unwinds
                    # the immediately-preceding stamp + RELEASE clears
                    # the savepoint. Discrepancy state returns to
                    # 'unresolved'.
                    with contextlib.suppress(sqlite3.Error):
                        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    counters["sandbox_auto_redirect_skipped_count"] += 1
                    log.warning(
                        "auto-redirect short-circuited under sandbox "
                        "for discrepancy %d",
                        disc.discrepancy_id,
                    )
                except InvalidOverrideComboError:
                    # Developer-bug per F21 + spec §7.4 R4 M2 LOCK:
                    # clean savepoint + re-raise out of the per-disc
                    # try-block so the outer catch ladder propagates
                    # (the outer ``except InvalidOverrideComboError``
                    # added below MUST come BEFORE the generic
                    # ``except Exception``).
                    with contextlib.suppress(sqlite3.Error):
                        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    raise
                except (ValidatorRejectedError, ValueError) as e:
                    # Spec §7.5 fallback: roll back the auto-redirect
                    # attempt + fresh-savepoint stamp
                    # pending_ambiguity_resolution for manual operator
                    # review. NOTE: InvalidOverrideComboError is a
                    # ValueError subclass — the earlier
                    # ``except InvalidOverrideComboError`` catch above
                    # guarantees it never reaches this catch.
                    with contextlib.suppress(sqlite3.Error):
                        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                    fb_sp = (
                        f"correction_fallback_sp_{disc.discrepancy_id}"
                    )
                    conn.execute(f"SAVEPOINT {fb_sp}")
                    try:
                        _stamp_pending_ambiguity_inner(
                            conn,
                            discrepancy_id=disc.discrepancy_id,
                            ambiguity_kind="multi_partial_vs_consolidated",
                            resolution_reason=(
                                f"multi-leg auto-redirect declined "
                                f"post-classifier: {e}"
                            ),
                        )
                        conn.execute(f"RELEASE SAVEPOINT {fb_sp}")
                        counters["tier2_pending_count"] += 1
                    except Exception as fb_exc:  # noqa: BLE001
                        with contextlib.suppress(sqlite3.Error):
                            conn.execute(
                                f"ROLLBACK TO SAVEPOINT {fb_sp}"
                            )
                            conn.execute(f"RELEASE SAVEPOINT {fb_sp}")
                        log.warning(
                            "auto-redirect §7.5 fallback stamp failed "
                            "for discrepancy %d: %s",
                            disc.discrepancy_id, fb_exc,
                        )
                        counters["tier_errored_count"] += 1
            else:
                # Tier-2 — stamp pending_ambiguity_resolution via the
                # canonical service helper inside the active savepoint.
                _stamp_pending_ambiguity_inner(
                    conn,
                    discrepancy_id=disc.discrepancy_id,
                    ambiguity_kind=classification.ambiguity_kind
                    or "unsupported",
                    resolution_reason=classification.correction_reason,
                )
                conn.execute(f"RELEASE SAVEPOINT {sp_name}")
                counters["tier2_pending_count"] += 1
        except InvalidOverrideComboError:
            # Phase 12.5 #1 spec §7.4 R4 M2 LOCK + F21 — developer-bug
            # propagates out of the pivot loop. SAVEPOINT cleanup was
            # already performed by the per-disc auto-redirect catch
            # above before re-raise; defense-in-depth here in case the
            # exception was raised outside that try-block (e.g., from
            # _validate_override_combo at the dispatcher seam).
            with contextlib.suppress(sqlite3.Error):
                conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                conn.execute(f"RELEASE SAVEPOINT {sp_name}")
            raise
        except Exception as e:  # noqa: BLE001 — graceful degradation

----- swing/trades/schwab_reconciliation.py:2039,2065 (pivot call site + post-pivot unresolved-count recompute) -----
        # reflect what would have happened) but pass environment='sandbox'
        # through to `_apply_tier1_correction_inner` which short-circuits
        # the journal mutation. tier1_applied_count stays 0 naturally
        # because the inner returns correction_id=None and the counter
        # increment guards on that.
        _pivot_classify_and_dispatch_for_run(
            conn,
            run_id=run_id,
            schwab_orders=schwab_orders,
            schwab_api_call_id=schwab_api_call_id,
            environment=environment,
            counters=counters,
        )

        # --- 9. UPDATE state='completed' ---
        finished_ts = now_ms()
        if finished_ts < started_ts:
            finished_ts = started_ts

        # Codex R1 Major #3 — recompute unresolved_discrepancies_count
        # post-pivot. _emit increments at INSERT time; the pivot flips
        # rows OFF 'unresolved' (tier-1 → auto_corrected_from_schwab;
        # tier-2 → pending_ambiguity_resolution). Recomputing from the
        # canonical resolution column is more robust than tracking
        # decrement deltas in counter state.
        unresolved_now = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_discrepancies "

----- swing/trades/reconciliation.py:45-115 (RECON_DISCREPANCY_TYPES + MATERIAL_BY_TYPE; confirms equity_delta material=0, the Sec-0=(A) no-change) -----
# migration 0031 CHECK + MATERIAL_BY_TYPE land in ONE commit.
DISCREPANCY_TYPES: tuple[str, ...] = (
    "close_price_mismatch",
    "stop_mismatch",
    "position_qty_mismatch",
    "cash_movement_mismatch",
    "sector_tamper",
    "snapshot_mismatch",
    "unmatched_open_fill",
    "unmatched_close_fill",
    "entry_price_mismatch",
    "equity_delta",
    "untracked_broker_position",
)


# Spec §3.3 CHECK enum — Phase 12 Sub-bundle C T-A.1 widened 5 → 9 values
# at the migration 0019 schema layer; Codex R1 Major #4 folded the matching
# widening into this Python constant. ``RESOLUTION_TYPES`` is the
# SCHEMA-COVERAGE source-of-truth: the dataclass validator at
# ``swing/data/models.py:_RESOLUTION_VALUES`` mirrors this set verbatim so
# reads of existing rows never raise. Paired schema-CHECK + Python-constant
# + dataclass-validator discipline per CLAUDE.md gotcha.
#
# IMPORTANT (Codex R2 Major #1 + R3 Minor #1 clarification):
# ``resolve_discrepancy`` (the manual operator-resolver service in this
# module) does NOT accept the full 9-value set. The 4 service-owned
# resolutions (``auto_corrected_from_schwab``, ``pending_ambiguity_resolution``,
# ``operator_resolved_ambiguity``, ``operator_overridden``) route through
# the auto-correct service entries in ``swing.trades.reconciliation_auto_correct``
# (apply_tier1 / stamp_pending_ambiguity / apply_tier2 / apply_tier3) and
# are REJECTED by ``resolve_discrepancy`` via
# ``_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS`` + ``_SERVICE_OWNED_RESOLUTIONS``
# below.
RESOLUTION_TYPES: tuple[str, ...] = (
    "journal_corrected",
    "source_treated_canonical",
    "manual_override",
    "unresolved",
    "acknowledged_immaterial",
    # Phase 12 Sub-bundle C T-A.1 widening (matches migration 0019 +
    # swing/data/models.py:_RESOLUTION_VALUES; spec §3.3 lifecycle).
    "auto_corrected_from_schwab",
    "pending_ambiguity_resolution",
    "operator_resolved_ambiguity",
    "operator_overridden",
)


# Spec §3.3.1 + §3.3.2 — default material_to_review per discrepancy type.
# Operator may override post-INSERT via the CLI ``swing journal
# discrepancy resolve --material`` flag (T-B.7). The lookup is the
# binding artifact for emitter-time classification; schema CHECK does
# NOT bind type → material mapping (spec §3.3.2).
MATERIAL_BY_TYPE: dict[str, int] = {
    "close_price_mismatch": 1,
    "stop_mismatch": 1,
    "position_qty_mismatch": 1,
    "cash_movement_mismatch": 0,
    "sector_tamper": 0,  # V1 immaterial; V2 elevates per spec §3.3.2
    "snapshot_mismatch": 0,
    "unmatched_open_fill": 1,
    "unmatched_close_fill": 1,
    "entry_price_mismatch": 1,
    "equity_delta": 0,
    # Phase 18 Arc 18-H.6 (C5) — an untracked broker position is MATERIAL
    # (it drifts the ledger-derived equity from the broker NLV by the orphan's
    # unrealized P&L; the operator must reconcile it).
    "untracked_broker_position": 1,
}


----- swing/trades/reconciliation.py:568-700 (resolve_discrepancy: allowlist, require_current_resolution, clear_ambiguity_kind path -- the C3 surface) -----
def resolve_discrepancy(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    resolution: str,
    resolution_reason: str | None = None,
    resolved_by: str = _V1_RESOLVED_BY,
    mistake_tag_assigned: str | None = None,
    material_to_review: int | None = None,
    require_current_resolution: str | None = None,
) -> None:
    """Update an existing discrepancy's resolution lifecycle.

    Per spec §3.3 + §4.2 — operator dispositions via this entry point
    (CLI ``swing journal discrepancy resolve`` wraps it in T-B.7).

    Validation:
        - resolution must be in ``_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS``
          (a TIGHTER subset of ``RESOLUTION_TYPES`` — the 4 service-owned
          lifecycle states added at C.A T-A.1 route through
          ``swing.trades.reconciliation_auto_correct`` entries instead
          per Codex R2 M#1).
        - resolution_reason required for journal_corrected /
          source_treated_canonical / manual_override (acknowledged_immaterial
          allows null per spec §3.3 + dataclass validator).
        - material_to_review override (if provided) restricted to {0, 1}.

    ``require_current_resolution`` (Phase 18 Arc 18-H.6.1 Codex R1 Major
    #2; default None preserves every existing caller verbatim): when set,
    the row's CURRENT ``resolution`` is re-read INSIDE this function's
    ``BEGIN IMMEDIATE`` transaction and MUST equal the expected value, else
    :class:`DiscrepancyResolutionStateError` is raised (and the tx rolled
    back). This closes the caller's pre-read → resolve TOCTOU window (e.g.
    the web orphan resolver's concurrent-POST race) atomically under the
    serializing lock — without it a race-loser silently overwrites the
    winner's audit metadata and returns success.

    Rejects caller-held transaction (single-transaction service).
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "resolve_discrepancy owns its own transaction; caller MUST NOT "
            "hold an open transaction."
        )
    if resolution in _SERVICE_OWNED_RESOLUTIONS:
        routing_hint = _SERVICE_OWNED_ROUTING_HINT[resolution]
        raise ValueError(
            f"resolution={resolution!r} is service-owned and cannot be set "
            f"via resolve_discrepancy; route through {routing_hint} in "
            f"swing.trades.reconciliation_auto_correct"
        )
    if resolution not in _MANUAL_RESOLVE_ALLOWED_RESOLUTIONS:
        raise ValueError(
            f"resolution must be one of {_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS}; "
            f"got {resolution!r}"
        )
    # spec §3.3 nullability rule.
    if (
        resolution in ("journal_corrected", "source_treated_canonical",
                       "manual_override")
        and not resolution_reason
    ):
        raise ValueError(
            f"resolution={resolution!r} requires non-empty resolution_reason"
        )

    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = repo.get_discrepancy(conn, discrepancy_id)
        if existing is None:
            raise ValueError(f"discrepancy_id={discrepancy_id} not found")
        # 18-H.6.1 Codex R1 Major #2 — atomic state precondition (TOCTOU
        # close). Checked AFTER BEGIN IMMEDIATE so a concurrent resolver
        # that committed first is visible here and the loser raises.
        if (
            require_current_resolution is not None
            and existing.resolution != require_current_resolution
        ):
            raise DiscrepancyResolutionStateError(
                f"discrepancy_id={discrepancy_id} is no longer "
                f"{require_current_resolution!r} (current="
                f"{existing.resolution!r}); resolution not applied"
            )
        # 18-H.6.1 Codex R2 Major #1 — the migration-0031 cross-column CHECK
        # ties ``ambiguity_kind IS NOT NULL`` to ``resolution IN
        # ('pending_ambiguity_resolution', 'operator_resolved_ambiguity')``.
        # ``resolve_discrepancy`` only ever sets a NON-pending manual
        # resolution (the two service-owned pending states are rejected
        # above), so if the EXISTING row carries a non-NULL ambiguity_kind
        # (e.g. an orphan 18-H.6 swept into pending_ambiguity_resolution —
        # the live-ID-68 case) the UPDATE MUST clear ambiguity_kind in the
        # SAME statement or the CHECK rejects the transition. Cleared
        # unconditionally when present; for a row already at ambiguity_kind
        # NULL the extra ``ambiguity_kind = NULL`` is a harmless no-op.
        clear_ambiguity_kind = existing.ambiguity_kind is not None
        repo.update_discrepancy_resolution(
            conn,
            discrepancy_id=discrepancy_id,
            resolution=resolution,
            resolution_reason=resolution_reason,
            resolved_by=resolved_by,
            resolved_at=now_ms(),
            mistake_tag_assigned=mistake_tag_assigned,
            clear_ambiguity_kind=clear_ambiguity_kind,
        )
        if material_to_review is not None:
            repo.update_discrepancy_material(
                conn,
                discrepancy_id=discrepancy_id,
                material_to_review=int(material_to_review),
            )
        # If the resolution moved off 'unresolved', decrement the
        # parent run's unresolved counter (best-effort — only when
        # the prior state was unresolved AND new is not).
        if (
            existing.resolution == "unresolved"
            and resolution != "unresolved"
        ):
            conn.execute(
                "UPDATE reconciliation_runs SET "
                "unresolved_discrepancies_count = "
                "  MAX(0, COALESCE(unresolved_discrepancies_count, 0) - 1) "
                "WHERE run_id = ?",
                (existing.run_id,),
            )
        conn.commit()
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


__all__ = [

----- swing/data/migrations/0031_untracked_broker_position.sql:60-90 (the cross-column ambiguity_kind/resolution CHECK) -----
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
        (ambiguity_kind IS NULL
            AND resolution NOT IN (
                'pending_ambiguity_resolution',
                'operator_resolved_ambiguity'
            ))
        OR
        (ambiguity_kind IS NOT NULL
            AND resolution IN (
                'pending_ambiguity_resolution',
                'operator_resolved_ambiguity'
            ))
    )
);

INSERT INTO reconciliation_discrepancies_new (
    discrepancy_id, run_id, discrepancy_type, trade_id, fill_id,
    cash_movement_id, linked_daily_management_record_id, ticker,
    field_name, expected_value_json, actual_value_json, delta_text,
    material_to_review, resolution, ambiguity_kind, resolution_reason,

codex
NO_NEW_CRITICAL_MAJOR
tokens used
19,440
NO_NEW_CRITICAL_MAJOR
```

---

## Adjudication (.copowers-findings.md)

# Codex adversarial review — equity_delta limbo-routing fix (executing)

- Tier: `review-strong` (the `-p` profile was absent in this cell's `$CODEX_HOME`,
  so per the recipe fallback `-p` was OMITTED and `-c model_reasoning_effort=high`
  was passed explicitly — NEVER `effort=none`).
- Model (from the run header): `gpt-5.5`.
- `reasoning effort: high` (confirmed in the run header).
- Sandbox: `read-only`; cwd pointed at the worktree (repo read-access) AND the
  diff + full reference graph bundled via stdin (production-code review per the
  18-H.4 repo-access note — the reviewer can read beyond the diff).
- Base for the diff: `91a14083` (the worktree branch point).
- Convergence: round 1 emitted `NO_NEW_CRITICAL_MAJOR`. The 5-round cap is
  suspended for this project; convergence on round 1 with zero new
  critical/major findings is the terminal state — no padding after convergence.

---

## Round 1

### Codex response (verbatim verdict)

```
OpenAI Codex v0.135.0
model: gpt-5.5
reasoning effort: high
sandbox: read-only
...
codex
NO_NEW_CRITICAL_MAJOR
```

(The full round-1 prompt + diff + reference graph + verdict are preserved
verbatim in `.codex-review-r1.txt`, copied into the tracked
`docs/reviews/equity-delta-limbo-fix-executing-codex-findings.md`.)

### Adjudication

No findings raised. Zero critical/major, zero minor. The reviewer was given:
1. The diff (the one-line skip-set widen `untracked_broker_position` ->
   `("untracked_broker_position", "equity_delta")` + comment, and the new test
   module).
2. The reference graph: the full pivot loop (skip / classify / tier-1 / tier-2
   else stamp), the pivot call site + post-pivot `unresolved_discrepancies_count`
   recompute, `MATERIAL_BY_TYPE` (confirming `equity_delta`=0 -> the Sec-0=(A)
   no-change), `resolve_discrepancy` (the C3 surface incl. `clear_ambiguity_kind`),
   and the migration-0031 cross-column CHECK.
3. The binding scope (Sec-0=(A) cleanability-only / no MATERIAL_BY_TYPE change;
   C1 byte-identical-for-other-types; C3 test-only; C4 single-touch) and the
   schema-prevented-value adjudication note.

No schema-prevented-value finding was raised, so the citation discipline did not
need to be exercised. Convergence accepted.
