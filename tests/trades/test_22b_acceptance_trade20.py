"""Arc 22-B Task 13 -- trade-20 acceptance on live shapes.

b22_180: the four governed readers (journal progress, tier comparison, the
tripwire, the hypothesis-progress card) and ``swing hypothesis list`` read
the SAME before and after trade 20 is assigned ``unintended_execution``
through the one writer, ``assign(...)``; trade 20 is in NO cohort's
candidate set before AND after, asserted by calling each reader's own
membership step (never inferred from N). N3 (a): trade 20 carries a NULL
``hypothesis_label``, so it was in no cohort and is in none, and no reader
names it.

b22_181: the attestation row read back on a ``mode=ro`` connection, EXACT
stored bytes (Task 5 step 6's serialization).

FIXTURE PROVENANCE. Every ``LIVE_*`` literal below is the non-NULL columns of
the row as read on 2026-09-23 with plain ``sqlite3`` ``mode=ro`` from a copy
of the live v39 journal (``~/swing-data/swing.db``, copied by the backup API
over a ``mode=ro`` connection; never opened through ``swing``'s ``connect``).
The rows: trade 20 (AMN, the subject) + fills 41/44; one COUNTED trade per
cohort -- trade 18 (A+ baseline, ``standard``; the other AMN), trade 14
(Near-A+, ``hypothesis_test_by_design``), trade 3 (Sub-A+,
``hypothesis_test_by_design``), trade 19 (Broad-watch, ``standard``) -- with
all their fills. The AMN ``latch_view_events`` row 5 is planted verbatim by
``tests._22b_fixtures.seed_amn_row5`` (its fire rows are that module's).

ONE ROW IS NOT LIVE, declared: no live trade carries the
``Capital-blocked: smaller-position test`` label (0 of 28, read on the same
copy), so its counted trade is trade 3's bytes with ``id`` 29 and ONLY the
label's cohort name changed (fills re-keyed). It exists so that cohort's N
is non-zero and "N unchanged" is not vacuous there.

Rows are planted by RAW ``INSERT`` on a plain connection (foreign keys OFF,
the 18-B.1 technique): the live rows carry ``candidate_id`` /
``pattern_evaluation_id`` / ``risk_policy_id_at_lock`` pointers into tables
this fixture does not reproduce, and no reader here joins them.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

from click.testing import CliRunner

from swing.config import load as load_config
from swing.data.db import open_connection, run_migrations
from tests._22b_fixtures import FILL41, FILL44, TRADE20, insert_row, seed_amn_row5
from tests.metrics.test_22b_cohort_exclusion import _readers

UNINT = "unintended_execution"
REASON = "Stale A+ latch order fired after A+ condition disappeared"
CAPITAL_BLOCKED = "Capital-blocked: smaller-position test"

LIVE_TRADE20 = {'id': 20,
 'ticker': 'AMN',
 'entry_date': '2026-08-07',
 'entry_price': 36.43,
 'initial_shares': 5,
 'initial_stop': 33.72,
 'current_stop': 33.72,
 'state': 'reviewed',
 'watchlist_entry_target': 36.27000045776367,
 'watchlist_initial_stop': 29.979999542236328,
 'notes': 'Stale A+ latch order fired after A+ condition disappeared.  This happened as we '
          'were working on the latch removal code.',
 'sector': '',
 'industry': '',
 'reviewed_at': '2026-08-12T21:11:02',
 'mistake_tags': '["none_observed"]',
 'entry_grade': 'A',
 'management_grade': 'A',
 'exit_grade': 'A',
 'process_grade': 'A',
 'disqualifying_process_violation': 0,
 'lesson_learned': 'Followed plan to the letter to collect data.  Would likely have exited '
                   'one day earlier, otherwise.',
 'trade_origin': 'manual_off_pipeline',
 'pre_trade_locked_at': '2026-08-07T16:00:00',
 'current_size': 0.0,
 'current_avg_cost': 36.43,
 'last_fill_at': '2026-08-11T16:00:00',
 'thesis': 'Old A+ setup, high likelihood of loss',
 'why_now': 'Accidental entry while working on latch/unlatch mechanism',
 'invalidation_condition': 'price falls below 20MA',
 'expected_scenario': 'unknown',
 'premortem_technical': 'Price falls below 20MA',
 'premortem_market_sector': 'sector pulls back',
 'premortem_execution': 'Fail to set sell stop',
 'event_risk_present': 0,
 'gap_risk_present': 0,
 'emotional_state_pre_trade': '["distracted"]',
 'market_regime': 'Bullish',
 'catalyst': 'technical_only',
 'risk_policy_id_at_lock': 5}
LIVE_FILLS20 = [{'fill_id': 41,
  'trade_id': 20,
  'fill_datetime': '2026-08-07T16:00:00',
  'action': 'entry',
  'quantity': 5.0,
  'price': 36.43,
  'manual_entry_confidence': 'low',
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'schwab_auto_then_operator_corrected',
  'schwab_source_value_json': '{"entry_date": "2026-08-01", "entry_price": 36.43, '
                              '"schwab_instrument_symbol": "AMN", "schwab_order_id": '
                              '"1007427919619", "shares": 5}',
  'operator_corrected_value_json': '{"entry_date": "2026-08-07", "entry_price": 36.43, '
                                   '"shares": 5}',
  'auto_fill_audit_at': '2026-08-09T06:17:45.135038+00:00'},
 {'fill_id': 44,
  'trade_id': 20,
  'fill_datetime': '2026-08-11T16:00:00',
  'action': 'stop',
  'quantity': 5.0,
  'price': 33.73,
  'reason': 'stop-hit',
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'operator_typed'}]
LIVE_TRADE18 = {'id': 18,
 'ticker': 'AMN',
 'entry_date': '2026-07-01',
 'entry_price': 33.66,
 'initial_shares': 6,
 'initial_stop': 25.54,
 'current_stop': 31.84,
 'state': 'reviewed',
 'watchlist_entry_target': 32.52000045776367,
 'watchlist_initial_stop': 25.540000915527344,
 'hypothesis_label': 'A+ baseline (aplus)',
 'chart_pattern_algo': 'none',
 'chart_pattern_classification_pipeline_run_id': 116,
 'sector': 'Healthcare',
 'industry': 'Medical Care Facilities',
 'reviewed_at': '2026-07-10T07:13:16',
 'mistake_tags': '["none_observed"]',
 'entry_grade': 'A',
 'management_grade': 'A',
 'exit_grade': 'A',
 'process_grade': 'A',
 'disqualifying_process_violation': 0,
 'lesson_learned': 'Followed plan to the letter to collect data.  Would likely have exited '
                   'one day earlier, otherwise.',
 'trade_origin': 'pipeline_aplus',
 'pre_trade_locked_at': '2026-07-01T16:00:00',
 'current_size': 0.0,
 'current_avg_cost': 33.66,
 'last_fill_at': '2026-07-09T16:00:00',
 'thesis': 'A+ Setup, taken as recommended',
 'why_now': 'Requirements met, hit pivot',
 'invalidation_condition': 'Stock closes below pivot',
 'expected_scenario': 'Stock continues to rise IAW hypothesis',
 'premortem_technical': 'Stock closes below pivot',
 'premortem_market_sector': 'Market turns bear / general downtrend',
 'premortem_execution': 'Do not set exit stop correctly, large loss',
 'premortem_additional': 'None',
 'event_risk_present': 0,
 'gap_risk_present': 0,
 'emotional_state_pre_trade': '["calm", "confident"]',
 'market_regime': 'Caution',
 'catalyst': 'technical_only',
 'risk_policy_id_at_lock': 5,
 'candidate_id': 9276,
 'pattern_evaluation_id': 1804,
 'failure_mode': 'normal_volatility_stop',
 'entry_intent': 'standard'}
LIVE_FILLS18 = [{'fill_id': 35,
  'trade_id': 18,
  'fill_datetime': '2026-07-01T16:00:00',
  'action': 'entry',
  'quantity': 6.0,
  'price': 33.66,
  'manual_entry_confidence': 'normal',
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'schwab_auto_then_operator_corrected',
  'schwab_source_value_json': '{"entry_date": "2026-07-01", "entry_price": 33.6584, '
                              '"schwab_instrument_symbol": "AMN", "schwab_order_id": '
                              '"1007001429471", "shares": 6}',
  'operator_corrected_value_json': '{"entry_date": "2026-07-01", "entry_price": 33.66, '
                                   '"shares": 6}',
  'auto_fill_audit_at': '2026-07-01T16:37:30.967044+00:00'},
 {'fill_id': 37,
  'trade_id': 18,
  'fill_datetime': '2026-07-07T16:00:00',
  'action': 'trim',
  'quantity': 3.0,
  'price': 35.65,
  'reason': 'partial',
  'reconciliation_status': 'reconciled_discrepancy_resolved',
  'fill_origin': 'schwab_auto_then_operator_corrected',
  'schwab_source_value_json': '{"candidate_count": 1, "candidates_map": '
                              '{"d655caffa1588d1a": {"date": "2026-07-07", "order_id": '
                              '"1007055818435", "price": 35.65, "quantity": 3}}, '
                              '"closed_shares": 3, "exit_date": "2026-07-07", '
                              '"exit_price": 35.65, "schwab_instrument_symbol": "AMN", '
                              '"schwab_order_id": "1007055818435"}',
  'operator_corrected_value_json': '{"closed_shares": 3, "exit_date": "2026-07-07", '
                                   '"exit_price": 35.75}',
  'auto_fill_audit_at': '2026-07-07T16:23:32.602606+00:00'},
 {'fill_id': 38,
  'trade_id': 18,
  'fill_datetime': '2026-07-09T16:00:00',
  'action': 'stop',
  'quantity': 3.0,
  'price': 32.06,
  'reason': 'stop-hit',
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'schwab_auto',
  'schwab_source_value_json': '{"candidate_count": 1, "candidates_map": '
                              '{"27773cb301e47991": {"date": "2026-07-09", "order_id": '
                              '"1007098393320", "price": 32.06, "quantity": 3}}, '
                              '"closed_shares": 3, "exit_date": "2026-07-09", '
                              '"exit_price": 32.06, "schwab_instrument_symbol": "AMN", '
                              '"schwab_order_id": "1007098393320"}',
  'auto_fill_audit_at': '2026-07-10T17:09:06.074472+00:00'}]
LIVE_TRADE14 = {'id': 14,
 'ticker': 'BULZ',
 'entry_date': '2026-05-27',
 'entry_price': 48.05,
 'initial_shares': 4,
 'initial_stop': 26.42,
 'current_stop': 44.49,
 'state': 'reviewed',
 'watchlist_entry_target': 47.16999816894531,
 'watchlist_initial_stop': 26.420000076293945,
 'hypothesis_label': 'Near-A+ defensible: extension test (watch); failed: proximity_20ma',
 'chart_pattern_algo': 'none',
 'chart_pattern_classification_pipeline_run_id': 79,
 'sector': 'Financial',
 'industry': 'Exchange Traded Fund',
 'reviewed_at': '2026-06-04T23:56:11',
 'mistake_tags': '["none_observed"]',
 'entry_grade': 'A',
 'management_grade': 'A',
 'exit_grade': 'A',
 'process_grade': 'A',
 'disqualifying_process_violation': 0,
 'lesson_learned': 'Followed recommendation.  No VCP due to hyp-rec.  Good trade.',
 'trade_origin': 'pipeline_watch_hyp_recs',
 'pre_trade_locked_at': '2026-05-27T16:00:00',
 'current_size': 0.0,
 'current_avg_cost': 48.05,
 'last_fill_at': '2026-06-04T16:00:00',
 'thesis': 'BULZ showed contraction.  Should be a reasonable setup',
 'why_now': 'Hit the breakout',
 'invalidation_condition': 'Immediate multi-day fall',
 'expected_scenario': 'Relatively slow rise',
 'premortem_technical': 'Close below pivot',
 'premortem_market_sector': 'N/A',
 'premortem_execution': 'None, good',
 'premortem_additional': 'N/A',
 'event_risk_present': 0,
 'gap_risk_present': 0,
 'emotional_state_pre_trade': '["hopeful"]',
 'market_regime': 'Bullish',
 'catalyst': 'technical_only',
 'risk_policy_id_at_lock': 5,
 'candidate_id': 5768,
 'entry_intent': 'hypothesis_test_by_design'}
LIVE_FILLS14 = [{'fill_id': 26,
  'trade_id': 14,
  'fill_datetime': '2026-05-27T16:00:00',
  'action': 'entry',
  'quantity': 4.0,
  'price': 48.05,
  'manual_entry_confidence': 'low',
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'schwab_auto',
  'schwab_source_value_json': '{"entry_date": "2026-05-27", "entry_price": 48.05, '
                              '"schwab_instrument_symbol": "BULZ", "schwab_order_id": '
                              '"1006490552819", "shares": 4}',
  'auto_fill_audit_at': '2026-05-27T16:19:45.922350+00:00'},
 {'fill_id': 32,
  'trade_id': 14,
  'fill_datetime': '2026-06-04T16:00:00',
  'action': 'exit',
  'quantity': 4.0,
  'price': 49.96,
  'reason': 'manual',
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'schwab_auto',
  'schwab_source_value_json': '{"candidate_count": 1, "candidates_map": '
                              '{"44339fe5419fc498": {"date": "2026-06-04", "order_id": '
                              '"1006614887695", "price": 49.96, "quantity": 4}}, '
                              '"closed_shares": 4, "exit_date": "2026-06-04", '
                              '"exit_price": 49.96, "schwab_instrument_symbol": "BULZ", '
                              '"schwab_order_id": "1006614887695"}',
  'auto_fill_audit_at': '2026-06-04T17:09:17.337509+00:00'}]
LIVE_TRADE3 = {'id': 3,
 'ticker': 'CC',
 'entry_date': '2026-04-30',
 'entry_price': 26.97,
 'initial_shares': 5,
 'initial_stop': 20.51,
 'current_stop': 24.61,
 'state': 'reviewed',
 'watchlist_entry_target': 24.1299991607666,
 'watchlist_initial_stop': 17.59000015258789,
 'notes': 'Hyp-Rec',
 'hypothesis_label': 'Sub-A+ VCP-not-formed (watch); failed: proximity_20ma, tightness',
 'sector': 'Basic Materials',
 'industry': 'Specialty Chemicals',
 'reviewed_at': '2026-05-06T04:21:59',
 'mistake_tags': '["EVENT_IGNORED"]',
 'entry_grade': 'A',
 'management_grade': 'A',
 'exit_grade': 'A',
 'process_grade': 'A',
 'disqualifying_process_violation': 0,
 'lesson_learned': 'Consider selling positions at end of day prior to earnings call',
 'trade_origin': 'pipeline_watch_hyp_recs',
 'pre_trade_locked_at': '2026-04-30T16:00:00',
 'current_size': 0.0,
 'current_avg_cost': 26.97,
 'last_fill_at': '2026-05-06T16:00:00',
 'entry_intent': 'hypothesis_test_by_design'}
LIVE_FILLS3 = [{'fill_id': 3,
  'trade_id': 3,
  'fill_datetime': '2026-04-30T16:00:00',
  'action': 'entry',
  'quantity': 5.0,
  'price': 26.97,
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'operator_typed'},
 {'fill_id': 7,
  'trade_id': 3,
  'fill_datetime': '2026-05-06T16:00:00',
  'action': 'stop',
  'quantity': 5.0,
  'price': 24.61,
  'reason': 'stop-hit',
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'operator_typed'}]
LIVE_TRADE19 = {'id': 19,
 'ticker': 'FTRE',
 'entry_date': '2026-07-31',
 'entry_price': 18.8,
 'initial_shares': 10,
 'initial_stop': 14.47,
 'current_stop': 18.4,
 'state': 'reviewed',
 'watchlist_entry_target': 18.159900665283203,
 'watchlist_initial_stop': 14.470000267028809,
 'hypothesis_label': 'Broad-watch baseline (watch); failed: tightness',
 'chart_pattern_algo': 'none',
 'chart_pattern_operator': 'none',
 'chart_pattern_classification_pipeline_run_id': 144,
 'sector': 'Healthcare',
 'industry': 'Biotechnology',
 'reviewed_at': '2026-08-12T21:12:10',
 'mistake_tags': '["none_observed"]',
 'entry_grade': 'A',
 'management_grade': 'A',
 'exit_grade': 'A',
 'process_grade': 'A',
 'disqualifying_process_violation': 0,
 'lesson_learned': 'N/A',
 'trade_origin': 'pipeline_watch_manual',
 'pre_trade_locked_at': '2026-07-23T16:00:00',
 'current_size': 0.0,
 'current_avg_cost': 18.8,
 'last_fill_at': '2026-08-04T16:00:00',
 'thesis': 'A+ setup, continued growth',
 'why_now': 'Dropped below limit.',
 'invalidation_condition': 'Closes below 20MR',
 'expected_scenario': 'Continued growth',
 'premortem_technical': 'Closes below 20MR',
 'premortem_market_sector': 'Downturn',
 'premortem_execution': 'No sell position set',
 'event_risk_present': 0,
 'gap_risk_present': 0,
 'emotional_state_pre_trade': '["calm", "confident"]',
 'market_regime': 'Caution',
 'catalyst': 'technical_only',
 'risk_policy_id_at_lock': 5,
 'candidate_id': 11852,
 'pattern_evaluation_id': 4791,
 'entry_intent': 'standard'}
LIVE_FILLS19 = [{'fill_id': 39,
  'trade_id': 19,
  'fill_datetime': '2026-07-31T16:00:00',
  'action': 'entry',
  'quantity': 10.0,
  'price': 18.8,
  'manual_entry_confidence': 'normal',
  'reconciliation_status': 'reconciled_discrepancy_resolved',
  'fill_origin': 'schwab_auto',
  'schwab_source_value_json': '{"entry_date": "2026-07-23", "entry_price": 18.8, '
                              '"schwab_instrument_symbol": "FTRE", "schwab_order_id": '
                              '"1007308870656", "shares": 10}',
  'auto_fill_audit_at': '2026-08-01T02:04:54.097907+00:00'},
 {'fill_id': 40,
  'trade_id': 19,
  'fill_datetime': '2026-08-04T16:00:00',
  'action': 'stop',
  'quantity': 10.0,
  'price': 18.4,
  'reason': 'stop-hit',
  'reconciliation_status': 'unreconciled',
  'fill_origin': 'schwab_auto_then_operator_corrected',
  'schwab_source_value_json': '{"candidate_count": 1, "candidates_map": '
                              '{"fc57a43216a9e4f3": {"date": "2026-08-03", "order_id": '
                              '"1007444179553", "price": 18.4, "quantity": 10}}, '
                              '"closed_shares": 10, "exit_date": "2026-08-03", '
                              '"exit_price": 18.4, "schwab_instrument_symbol": "FTRE", '
                              '"schwab_order_id": "1007444179553"}',
  'operator_corrected_value_json': '{"closed_shares": 10, "exit_date": "2026-08-04", '
                                   '"exit_price": 18.4}',
  'auto_fill_audit_at': '2026-08-06T12:01:22.874864+00:00'}]

# The declared non-live row (see the module docstring): trade 3's bytes, id 29,
# the label's cohort name moved to Capital-blocked -- nothing else changed.
DERIVED_TRADE29 = {
    **LIVE_TRADE3, "id": 29,
    "hypothesis_label": LIVE_TRADE3["hypothesis_label"].replace(
        "Sub-A+ VCP-not-formed", CAPITAL_BLOCKED),
}
DERIVED_FILLS29 = [{k: v for k, v in {**f, "trade_id": 29}.items() if k != "fill_id"}
                   for f in LIVE_FILLS3]

COUNTED = (LIVE_TRADE18, LIVE_TRADE14, LIVE_TRADE3, LIVE_TRADE19, DERIVED_TRADE29)


def test_the_shared_trade20_fixture_agrees_with_the_live_bytes() -> None:
    """The subset ``tests._22b_fixtures`` plants is the live row's own."""
    shared = {k: v for k, v in TRADE20.items() if v is not None}
    assert shared.items() <= LIVE_TRADE20.items()
    assert "hypothesis_label" not in LIVE_TRADE20  # NULL live
    assert "entry_intent" not in LIVE_TRADE20  # NULL live
    by_id = {f["fill_id"]: f for f in LIVE_FILLS20}
    for fixture in (FILL41, FILL44):
        planted = {k: v for k, v in fixture.items() if v is not None}
        assert planted.items() <= by_id[fixture["fill_id"]].items()


def _world(tmp_path: Path):
    root = tmp_path / "t13"
    root.mkdir()
    db_path = root / "swing.db"
    c = open_connection(db_path)
    try:
        run_migrations(c, target_version=40, backup_dir=root / "bak")
    finally:
        c.close()
    plain = sqlite3.connect(db_path)  # foreign keys OFF (the 18-B.1 technique)
    try:
        seed_amn_row5(plain)
        for trade, fills in ((LIVE_TRADE20, LIVE_FILLS20),
                             (LIVE_TRADE18, LIVE_FILLS18),
                             (LIVE_TRADE14, LIVE_FILLS14),
                             (LIVE_TRADE3, LIVE_FILLS3),
                             (LIVE_TRADE19, LIVE_FILLS19),
                             (DERIVED_TRADE29, DERIVED_FILLS29)):
            insert_row(plain, "trades", trade)
            for fill in fills:
                insert_row(plain, "fills", fill)
        plain.commit()
    finally:
        plain.close()
    base = load_config(Path("swing.config.toml"))
    cfg = dc_replace(base, paths=dc_replace(base.paths, db_path=db_path))
    return db_path, cfg


def _registry(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    return [(int(i), str(n)) for i, n in
            conn.execute("SELECT id, name FROM hypothesis_registry ORDER BY id")]


def _memberships(conn: sqlite3.Connection) -> dict[str, dict[str, tuple[int, ...]]]:
    """reader -> cohort -> the trade ids its OWN membership step selects.

    journal (``journal/stats.py`` ``_in_cohort``) and tripwire
    (``recommendations/hypothesis.py`` ``compute_tripwire_status``) both compose
    ``_label_matches_hypothesis`` AND ``trade_counts_toward_cohort`` over the
    closed trades; tier (``metrics/tier.py``) calls
    ``list_closed_trades_for_cohort`` with the cohort's intent predicate and
    clause-(4) exclusion over ``TAXONOMY_COHORTS``; the card calls its
    ``_list_cohort_trades_sorted`` over the registry rows. The naming step
    ``list_intent_excluded_for_cohort`` (N3 (a)) is read beside them.
    """
    from swing.data.repos.trades import list_closed_trades
    from swing.metrics.cohort import (
        list_closed_trades_for_cohort,
        list_intent_excluded_for_cohort,
    )
    from swing.metrics.cohort_intent import (
        cohort_entry_intent,
        cohort_excluded_entry_intents,
        trade_counts_toward_cohort,
    )
    from swing.metrics.tier import TAXONOMY_COHORTS
    from swing.recommendations.hypothesis import _label_matches_hypothesis
    from swing.web.view_models.metrics.hypothesis_progress_card import (
        _list_cohort_trades_sorted,
    )

    names = [n for _i, n in _registry(conn)]
    registered = set(names)
    closed = list_closed_trades(conn)
    in_memory = {
        name: tuple(sorted(
            t.id for t in closed
            if _label_matches_hypothesis(t.hypothesis_label, name)
            and trade_counts_toward_cohort(entry_intent=t.entry_intent,
                                           hypothesis_name=name)))
        for name in names}
    tier = {
        name: tuple(sorted(t.id for t in list_closed_trades_for_cohort(
            conn, hypothesis_label=name,
            entry_intent=cohort_entry_intent(name, registered_names=registered),
            exclude_entry_intents=cohort_excluded_entry_intents(
                name, registered_names=registered))))
        for name in TAXONOMY_COHORTS}
    card = {name: tuple(sorted(t.id for t in _list_cohort_trades_sorted(conn, name)))
            for name in names}
    named = {name: tuple(tid for tid, _r in list_intent_excluded_for_cohort(
        conn, hypothesis_label=name, state_filter=None)) for name in names}
    return {"journal": in_memory, "tripwire": in_memory, "tier": tier,
            "card": card, "named": named}


def _capture(db_path: Path, cfg) -> dict:
    from swing.cli import hypothesis_list_cmd
    from swing.recommendations.hypothesis import compute_tripwire_status

    conn = open_connection(db_path)
    try:
        readers = _readers(conn, cfg)
        tripwire_all = {
            name: compute_tripwire_status(conn, hypothesis_id=hid,
                                          starting_equity=7500.0).current_sample
            for hid, name in _registry(conn)}
        members = _memberships(conn)
    finally:
        conn.close()
    r = CliRunner().invoke(hypothesis_list_cmd, obj={"config": cfg})
    assert r.exit_code == 0, r.output
    return {"readers": readers, "tripwire_all": tripwire_all,
            "members": members, "list": r.output.splitlines()}


def _assign20(db_path: Path):
    from swing.trades.entry_intent_assignment import assign

    c = open_connection(db_path)
    try:
        return assign(c, None, trade_id=20, cite=["why_now", "notes"],
                      reason=REASON, applied_by="operator")
    finally:
        c.close()


def test_trade20_before_and_after_every_reader_n_unchanged_b22_180(
        tmp_path: Path) -> None:
    db_path, cfg = _world(tmp_path)
    before = _capture(db_path, cfg)
    result = _assign20(db_path)
    assert result.admitted, result.message
    after = _capture(db_path, cfg)

    # Non-vacuous: every cohort each reader reads counts >= 1 trade.
    for reader, cohorts in before["members"].items():
        if reader == "named":
            continue
        for name, ids in cohorts.items():
            assert ids, (reader, name)
    # Every reader's N (and its named lines) identical.
    assert after["readers"] == before["readers"]
    assert after["tripwire_all"] == before["tripwire_all"]
    # Trade 20 in NO cohort's candidate set, before AND after, per reader.
    for snap in (before, after):
        for reader, cohorts in snap["members"].items():
            for name, ids in cohorts.items():
                assert 20 not in ids, (reader, name, ids)
    assert after["members"] == before["members"]
    # `swing hypothesis list`, line for line (the witness pre-image, R2-11).
    assert after["list"] == before["list"]
    assert not any("trade 20" in ln for ln in after["list"])
    # The value did land (the equality above is about a changed row).
    c = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        assert c.execute("SELECT entry_intent FROM trades WHERE id = 20"
                         ).fetchone() == (UNINT,)
    finally:
        c.close()


# The EXACT stored bytes (plan Task 13 step 2; Task 5 step 6 serialization).
EXPECTED_LEG_EVIDENCE = '{"deployment_session": "2026-08-03", "placement_session": "2026-08-01"}'
EXPECTED_CITED_FIELDS = '["notes", "why_now"]'
EXPECTED_SNAPSHOT = (
    '{"notes": "Stale A+ latch order fired after A+ condition disappeared.  '
    'This happened as we were working on the latch removal code.", '
    '"why_now": "Accidental entry while working on latch/unlatch mechanism"}')


def test_trade20_attestation_readback_b22_181(tmp_path: Path) -> None:
    db_path, _cfg = _world(tmp_path)
    result = _assign20(db_path)
    assert result.admitted, result.message
    c = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute("SELECT * FROM entry_intent_attestations").fetchall()
    finally:
        c.close()
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["attestation_id"] == result.attestation_id
    assert row["trade_id"] == 20
    assert row["assigned_value"] == UNINT
    assert row["admission_tier"] == "contemporaneous_record"
    assert row["admitted_leg"] == "deployment"
    assert row["leg_evidence_json"] == EXPECTED_LEG_EVIDENCE
    assert row["cited_fields_json"] == EXPECTED_CITED_FIELDS
    assert row["cited_text_snapshot_json"] == EXPECTED_SNAPSHOT
    assert row["outcome_known_at"] == "2026-08-11T16:00:00"
    assert (row["placement_session"], row["placement_session_source"]) == (
        "2026-08-01", "schwab_envelope")
    assert row["entry_broker_order_id"] == "1007427919619"
    assert (row["entry_fill_id"], row["entry_fill_id_at_assignment"]) == (41, 41)
    assert row["trade_entry_date"] == "2026-08-07"
    assert row["corrections_touching_cited_fields"] == 0
    assert (row["reason"], row["applied_by"]) == (REASON, "operator")
    for struct in ("cited_latch_link_id", "cited_latch_terminal_rung",
                   "cited_latch_terminal_session", "cited_latch_probe_json"):
        assert row[struct] is None, struct


def test_the_derived_row_moves_only_the_cohort_name() -> None:
    diff = {k for k in LIVE_TRADE3 if DERIVED_TRADE29[k] != LIVE_TRADE3[k]}
    assert diff == {"id", "hypothesis_label"}
    assert DERIVED_TRADE29["hypothesis_label"].startswith(CAPITAL_BLOCKED + " (watch)")
