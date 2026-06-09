from __future__ import annotations

import json
from pathlib import Path

from research.harness.shadow_expectancy.run import run_harness
from tests.research.shadow_expectancy.testkit import (
    insert_candidate,
    insert_detection,
    insert_observation,
    insert_pipeline_run,
    make_db,
)


def _seed_one_aplus_winner(conn):
    # migration 0008 already seeded the active registry via make_db.
    eval_id = insert_candidate(conn, ticker="AAA", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="AAA", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    # entry bar triggers (high >= pivot), then a stop-out.
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-02", o=8.5, h=8.6, l=8.0, c=8.2,
                       status="triggered_open")
    conn.commit()


def test_run_harness_emits_four_artifacts(tmp_path):
    conn = make_db(tmp_path)        # creates + migrates tmp_path/t.db
    _seed_one_aplus_winner(conn)    # writes candidate/detection/observations into it
    out = tmp_path / "out"
    results, per_session, summary, manifest = run_harness(
        db_path=tmp_path / "t.db", output_dir=out, source="pipeline")
    for p in (results, per_session, summary, manifest):
        assert Path(p).exists()
    m = json.loads(Path(manifest).read_text(encoding="utf-8"))
    assert m["l2_lock_preserved"] is True
    summary_text = Path(summary).read_text(encoding="utf-8")
    assert "A+ baseline" in summary_text
    # M2 (spec 7.1): the unattributed reason breakdown is surfaced in summary.md. EVERY
    # canonical reason label renders (0 when absent) so the funnel's pre-/non-attribution
    # losses are externally visible, not buried in the manifest.
    assert "## Unattributed signals" in summary_text
    for reason in ("no_candidate_join", "matched_no_hypothesis", "multi_match",
                   "no_canonical_detection", "inconsistent_detection_series",
                   "inconsistent_trigger_state"):
        assert f"{reason}=" in summary_text


def test_reproducible_canonical_manifest(tmp_path):
    conn = make_db(tmp_path)
    _seed_one_aplus_winner(conn)
    out = tmp_path / "out"
    _, _, _, m1 = run_harness(db_path=tmp_path / "t.db", output_dir=out, source="pipeline")
    _, _, _, m2 = run_harness(db_path=tmp_path / "t.db", output_dir=out, source="pipeline")

    def _canonical(p):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for k in ("run_id", "started_iso_utc", "finished_iso_utc"):
            d.pop(k, None)
        return json.dumps(d, sort_keys=True)

    assert _canonical(m1) == _canonical(m2)


def _seed_attributed_open_runner(conn):
    # A second aplus signal that TRIGGERS then stays OPEN through a short horizon (no stop
    # hit on its single forward bar). Attributes to H1 (A+ baseline) via the real matcher.
    eval_id = insert_candidate(conn, ticker="BBB", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="BBB", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    # forward bar: low 10.1 > entry_bar.low (9.6) -> never stops -> open at horizon=1.
    insert_observation(conn, det_id, "2026-06-02", o=10.3, h=10.6, l=10.1, c=10.5,
                       status="triggered_open")
    conn.commit()


def _seed_no_candidate_join(conn):
    # A detection for CCC under a pipeline_run whose eval_run has NO CCC candidate row ->
    # resolve_candidate returns None -> collapse emits `no_candidate_join` (unattributed).
    eval_id = insert_candidate(conn, ticker="OTHER", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="CCC", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    conn.commit()


def _seed_multi_match_signal(conn):
    # A real aplus signal MMM; the matcher is MONKEYPATCHED in the test to return TWO
    # hypotheses for MMM (the 4 seeded hypotheses are mutually exclusive, so a real
    # multi-match is impossible -- it MUST be synthesized to exercise the guard).
    eval_id = insert_candidate(conn, ticker="MMM", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="MMM", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-02", o=8.5, h=8.6, l=8.0, c=8.2,
                       status="triggered_open")
    conn.commit()


def test_reconciliation_invariant_over_real_corpus(tmp_path, monkeypatch):
    # R3-M1 (spec 7.1): Sum(unattributed reason counts) + Sum(per-hypothesis terminal-status
    # counts) == unique_signals, asserted over a REAL run_harness corpus that includes an
    # attributed-CLOSED signal (AAA stops out -> H1.closed), an attributed-OPEN signal
    # (BBB -> H1.open_at_horizon at horizon=1), an UNATTRIBUTED signal (CCC -> no_candidate_join),
    # and a (synthetic) MULTI-MATCH signal (MMM, matcher monkeypatched to return 2 hypotheses).
    import research.harness.shadow_expectancy.run as run_mod

    conn = make_db(tmp_path)
    _seed_one_aplus_winner(conn)        # AAA -> H1, stops out -> closed
    _seed_attributed_open_runner(conn)  # BBB -> H1, open at horizon
    _seed_no_candidate_join(conn)       # CCC -> unattributed: no_candidate_join
    _seed_multi_match_signal(conn)      # MMM -> (patched) 2 hypotheses -> multi_match

    real_attribute = run_mod.attribute_hypotheses

    def _patched(candidate, *, registry):
        if candidate.ticker == "MMM":
            # synthesize a non-exclusive (>1) match the seeded registry can never produce.
            return ["A+ baseline", "Sub-A+ VCP-not-formed"]
        return real_attribute(candidate, registry=registry)

    monkeypatch.setattr(run_mod, "attribute_hypotheses", _patched)

    out = tmp_path / "out"
    # horizon=1 so BBB (one clean forward bar) lands open-at-horizon; AAA still stops on
    # its single forward bar (low 8.0 <= entry_bar.low 9.6).
    _, _, summary, manifest = run_mod.run_harness(
        db_path=tmp_path / "t.db", output_dir=out, source="pipeline", horizon_sessions=1)
    funnel = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    # M2: the non-zero unattributed reasons render in summary.md with their counts.
    summary_text = Path(summary).read_text(encoding="utf-8")
    assert "no_candidate_join=1" in summary_text
    assert "multi_match=1" in summary_text

    unattributed_total = sum(funnel["unattributed"].values())
    per_hyp_terminal_total = 0
    for card in funnel["per_hypothesis"].values():
        per_hyp_terminal_total += (
            card["closed"] + card["open_at_horizon"] + card["never_triggered"]
            + sum(card["excluded"].values()))
    unique_signals = funnel["detection_level"]["unique_signals"]

    # the corpus exercises every branch of the invariant.
    assert funnel["unattributed"]["no_candidate_join"] == 1
    assert funnel["unattributed"]["multi_match"] == 1   # MMM excluded, NOT counted in 2 hyps
    h1 = funnel["per_hypothesis"]["A+ baseline"]
    assert h1["closed"] == 1 and h1["open_at_horizon"] == 1
    # MMM did NOT contribute to any per-hypothesis bucket (it was excluded as multi_match).
    assert "Sub-A+ VCP-not-formed" not in funnel["per_hypothesis"]
    # THE INVARIANT, exact:
    assert unattributed_total + per_hyp_terminal_total == unique_signals == 4


def _seed_attributed_never_triggered(conn, ticker="NNN"):
    # An aplus candidate (-> H1) whose detection NEVER fires entry (only `pending`
    # observations, no entry_fired). It must still count as a SIGNAL for H1.
    eval_id = insert_candidate(conn, ticker=ticker, bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker=ticker, pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=9.0, h=9.8, l=8.9, c=9.5,
                       status="pending")  # never triggers (no entry_fired)
    conn.commit()


def test_never_triggered_signal_counts_in_scorecard_denominator(tmp_path):
    # Codex R1-M1: a never-triggered ATTRIBUTED signal must contribute to the scorecard's
    # signal denominator (trigger rate over ALL signals; per-signal expectancy counts it as
    # 0R). Without the ShadowTrade(triggered=False) emission it would vanish, reporting
    # trigger rate 1/1 instead of 1/2.
    conn = make_db(tmp_path)
    _seed_one_aplus_winner(conn)             # AAA -> H1, triggers + stops out (closed)
    _seed_attributed_never_triggered(conn)   # NNN -> H1, never triggers
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline")
    card = json.loads(Path(manifest).read_text(encoding="utf-8"))["scorecard"]["A+ baseline"]
    tr = card["trigger_rate"]
    assert tr["triggered"] == 1 and tr["signals"] == 2   # never-triggered IS in the denominator
    assert tr["rate"] == 0.5
    # per-signal expectancy averages the triggered R with a 0R non-trigger across 2 signals.
    funnel = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    assert funnel["per_hypothesis"]["A+ baseline"]["never_triggered"] == 1


def test_only_filter_reconciles_detection_level(tmp_path):
    # Codex R1-M2: --only must keep the detection-level funnel reconciling (total == unique +
    # collapsed). With BBB present but filtered out, total_detections must reflect ONLY AAA.
    conn = make_db(tmp_path)
    _seed_one_aplus_winner(conn)        # AAA
    _seed_attributed_open_runner(conn)  # BBB (filtered out by --only)
    out = tmp_path / "out"
    # run_harness now also enforces the reconciliation invariant internally; under the old
    # bug this would raise. Assert it completes and the detection level reconciles.
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline", only=("AAA",))
    dl = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]["detection_level"]
    assert dl["total_detections"] == 1       # ONLY AAA's detection
    assert dl["unique_signals"] == 1 and dl["collapsed_duplicate_detection"] == 0
    assert (dl["unique_signals"] + dl["collapsed_duplicate_detection"]
            == dl["total_detections"])


def _seed_excluded_duplicate_group(conn):
    # Two detections sharing (pipeline_run_id, ticker=DDD) but NO DDD candidate row ->
    # the group is excluded (no_candidate_join) yet still collapses 2 detections to 1 signal.
    eval_id = insert_candidate(conn, ticker="OTHER2", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    for pattern_class in ("vcp", "flat_base"):  # distinct classes dodge the UNIQUE index
        det_id = insert_detection(conn, ticker="DDD", pipeline_run_id=pr_id, pivot=10.0,
                                  data_asof_date="2026-05-28", detection_date="2026-05-29",
                                  pattern_class=pattern_class)
        insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                           status="triggered_open", event="entry_fired")
    conn.commit()


def test_excluded_multidetection_group_collapsed_count(tmp_path):
    # Codex R1-M3: an EXCLUDED group of 2 detections must still report 1 collapsed duplicate
    # (group_size - 1), so total(2) == unique(1) + collapsed(1). Under the old bug collapse
    # returned collapsed_ids=[] on exclusion -> total=2, unique=1, collapsed=0 (2 != 1).
    conn = make_db(tmp_path)
    _seed_excluded_duplicate_group(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    dl = f["detection_level"]
    assert dl["total_detections"] == 2
    assert dl["unique_signals"] == 1
    assert dl["collapsed_duplicate_detection"] == 1          # group_size - 1, even when excluded
    assert (dl["unique_signals"] + dl["collapsed_duplicate_detection"]
            == dl["total_detections"])
    assert f["unattributed"]["no_candidate_join"] == 1


def _seed_inverted_initial_stop_winner(conn, ticker="INV"):
    # An aplus candidate whose candidate.initial_stop is ABOVE the pivot (10.5 > 10.0) -- a
    # stale/inverted production stop. The mechanical trade ignores it (stop = entry_bar.low),
    # so this MUST still simulate, not be excluded as invalid_ohlc.
    eval_id = insert_candidate(conn, ticker=ticker, bucket="aplus", pivot=10.0,
                               initial_stop=10.5, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker=ticker, pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-02", o=8.5, h=8.6, l=8.0, c=8.2,
                       status="triggered_open")  # stops out -> closed
    conn.commit()


def test_inverted_candidate_initial_stop_not_excluded(tmp_path):
    # Codex R2-M1: a candidate whose initial_stop >= pivot used to be screened out as
    # invalid_ohlc by the candidate-level validator, silently dropping a mechanically-valid
    # shadow trade. The validator no longer consults candidate.initial_stop, so the signal
    # simulates normally (H1 closed), NOT excluded.
    conn = make_db(tmp_path)
    _seed_inverted_initial_stop_winner(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h1 = f["per_hypothesis"]["A+ baseline"]
    assert h1["closed"] == 1                       # simulated, not excluded
    assert h1["excluded"].get("invalid_ohlc", 0) == 0
