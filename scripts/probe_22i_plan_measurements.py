"""22-I plan-stage measurements (Phase 22, arc 22-I; the plan cell's step 3).

WHAT IT DOES
    The measurements the round-0 rulings require the PLAN to make, each proven
    by execution on a COPY of the live DB (never the live file):

    M1  RD row 4  -- REPLACE and DELETE on the two CITED daily_recommendations
                     rows (169, 172) under foreign_keys=ON, with an uncited
                     CONTROL row proving the probes can succeed.
    M2  CHARC F-I2 -- the REBUILT trg_provenance_corrections_append_only_update
                     (stored v40 text, WHEN NOT ( ... ) -> WHEN NOT COALESCE(( ... ), 0),
                     nothing else) on a SCRATCH COPY OF THE COPY: the census's
                     own pc sections re-run against it (the split_into_partials
                     fill-delete CONTROL stays ADMITTED; the (ii) set flips
                     SILENT -> FIRES).
    M3  writer x ruled-guard compositions -- each candidate twin/barrier created
                     inside BEGIN..ROLLBACK, then the PRODUCTION writer's own
                     statement run against it, to find writers a ruled guard
                     would abort.

SAFETY
    Plain sqlite3; never imports swing (cannot reach ensure_schema). Refuses the
    live path. M1/M3 run in BEGIN..ROLLBACK on the copy; M2 writes only to its
    own scratch copy of the copy.

USAGE
    python scripts/probe_22i_plan_measurements.py --copy <copy.db> --out <tsv>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

LIVE_DB = Path(os.path.expanduser("~")) / "swing-data" / "swing.db"
_HERE = Path(__file__).resolve().parent


def _census():
    spec = importlib.util.spec_from_file_location(
        "probe_22i_guard_census", _HERE / "probe_22i_guard_census.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def twin_predicate(immutable, write_once=(), fk_setnull=None, extra=()):
    """The ruled (c)-twin predicate: IS-comparisons (never NULL), write-once
    NULL->value, SET-NULL FK value->NULL only with the parent gone."""
    parts = [f"NEW.{c} IS OLD.{c}" for c in immutable]
    parts += [f"(NEW.{c} IS OLD.{c} OR OLD.{c} IS NULL)" for c in write_once]
    for c, (parent, pk) in (fk_setnull or {}).items():
        parts.append(
            f"(NEW.{c} IS OLD.{c} OR (OLD.{c} IS NOT NULL AND NEW.{c} IS NULL "
            f"AND NOT EXISTS (SELECT 1 FROM {parent} WHERE {pk} = OLD.{c})))")
    parts += list(extra)
    return "\n    AND ".join(parts)


def twin_ddl(name, table, predicate, msg):
    return (f"CREATE TRIGGER {name} BEFORE UPDATE ON {table} FOR EACH ROW\n"
            f"WHEN NOT COALESCE(\n    {predicate},\n    0)\n"
            f"BEGIN SELECT RAISE(ABORT, '{msg}'); END")


def cols(conn, t):
    return [r[1] for r in conn.execute(f"PRAGMA table_info('{t}')")]


# ---------------------------------------------------------------- M1
def m1_daily_recommendations(p):
    t = "daily_recommendations"
    cited = [r[0] for r in p.conn.execute(
        "SELECT DISTINCT cited_daily_recommendation_id FROM provenance_corrections "
        "WHERE cited_daily_recommendation_id IS NOT NULL ORDER BY 1")]
    uncited = p.conn.execute(
        "SELECT id FROM daily_recommendations WHERE id NOT IN "
        "(SELECT cited_daily_recommendation_id FROM provenance_corrections "
        " WHERE cited_daily_recommendation_id IS NOT NULL) ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    c = cols(p.conn, t)
    nonid = [x for x in c if x != "id"]
    p.out.write(f"#M1\tcited={cited}\tcontrol_uncited={uncited}\n")
    for rid, role in [(r, "cited") for r in cited] + [(uncited, "CONTROL-uncited")]:
        want_ok = role.startswith("CONTROL")
        exp = ("ok",) if want_ok else ("info",)
        p.run("M1-dr", f"{t}#{rid}", "FK RESTRICT", f"{role} DELETE", exp, [],
              f"DELETE FROM {t} WHERE id = ?", (rid,))
        p.run("M1-dr", f"{t}#{rid}", "FK RESTRICT", f"{role} REPLACE same id",
              exp, [], f"REPLACE INTO {t} SELECT * FROM {t} WHERE id = ?", (rid,),
              post=lambda cn, i=rid: "id still present="
              + str(cn.execute(f"SELECT count(*) FROM {t} WHERE id=?", (i,)).fetchone()[0]))
        p.run("M1-dr", f"{t}#{rid}", "FK RESTRICT",
              f"{role} INSERT OR REPLACE on UNIQUE key (new id)", exp, [],
              f"INSERT OR REPLACE INTO {t} ({', '.join(nonid)}) "
              f"SELECT {', '.join(nonid)} FROM {t} WHERE id = ?", (rid,),
              post=lambda cn, i=rid: "old id present="
              + str(cn.execute(f"SELECT count(*) FROM {t} WHERE id=?", (i,)).fetchone()[0]))
        # the sole writer's DO UPDATE upsert path (recommendations.py:18) on the
        # same key -- expected ADMITTED (an UPDATE, not a parent-key change)
        p.run("M1-dr", f"{t}#{rid}", "writer upsert", f"{role} ON CONFLICT DO UPDATE",
              ("ok",), [],
              f"INSERT INTO {t} ({', '.join(nonid)}) SELECT {', '.join(nonid)} "
              f"FROM {t} WHERE id = ? ON CONFLICT(action_session_date, ticker, "
              f"recommendation) DO UPDATE SET action_text = excluded.action_text",
              (rid,))


# ---------------------------------------------------------------- M2
PC_UP = "trg_provenance_corrections_append_only_update"


def rebuilt_pc_update_sql(stored: str) -> str:
    a, b = "FOR EACH ROW WHEN NOT (", "\n)\nBEGIN"
    assert stored.count(a) == 1 and stored.count(b) == 1, "stored text shape moved"
    return stored.replace(a, "FOR EACH ROW WHEN NOT COALESCE((").replace(
        b, "\n), 0)\nBEGIN")


def m2_rebuilt_pc_update(copy: Path, scratch_dir: Path, out, census):
    ts = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    dst_path = scratch_dir / f"swing-v40-copy-of-copy-pc-rebuilt-{ts}.db"
    src = sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(str(dst_path))
    src.backup(dst)
    src.close()
    stored = dst.execute("SELECT sql FROM sqlite_master WHERE name=?",
                         (PC_UP,)).fetchone()[0]
    new = rebuilt_pc_update_sql(stored)
    dst.execute("BEGIN")
    dst.execute(f"DROP TRIGGER {PC_UP}")
    dst.execute(new)
    dst.execute("COMMIT")
    got = dst.execute("SELECT sql FROM sqlite_master WHERE name=?",
                      (PC_UP,)).fetchone()[0]
    dst.close()
    out.write(f"#M2\tscratch={dst_path}\n")
    out.write(f"#M2\tstored_len={len(stored)}\trebuilt_len={len(got)}\t"
              f"delta_chars={len(got) - len(stored)}\t"
              f"inverse_transform_equals_stored="
              f"{got.replace('WHEN NOT COALESCE((', 'WHEN NOT (').replace(chr(10) + '), 0)' + chr(10) + 'BEGIN', chr(10) + ')' + chr(10) + 'BEGIN') == stored}\n")
    p = census.Probe(dst_path, out)
    p.out.write("section\ttable\ttrigger_under_test\tprobe\texpect\toutcome\tverdict\n")
    census.pc_append_only_update(p)
    census.pc_citation_graph(p)
    out.write(f"#M2-SUMMARY\tPASS={p.n_pass}\tFAIL={p.n_fail}\tINFO={p.n_info}\n")
    p.conn.close()
    return dst_path


# ---------------------------------------------------------------- M3
def m3_compositions(p):
    c = p.conn
    for msg, name in (("probe rc twin", "trg_probe_rc_twin"),
                      ("probe dmr (i) literal", "trg_probe_dmr_superseded_frozen"),
                      ("probe dmr (i) corrected", "trg_probe_dmr_superseded_frozen"),
                      ("probe review_log no_replace", "trg_probe_review_log_no_replace"),
                      ("probe review_log twin", "trg_probe_review_log_twin")):
        p.msg_to_trigger[msg] = [name]
    # (a) reconciliation_corrections: the RD-enumerated twin (every column
    #     except superseded_by_correction_id + the three SET NULL FKs) vs the
    #     split_into_partials step 2.5 UPDATE (reconciliation_auto_correct.py:3251).
    t = "reconciliation_corrections"
    # superseded_by_correction_id is BOTH write-once AND a SET NULL FK, so it
    # takes the combined clause (NULL->value, or value->NULL with the parent
    # gone) in `extra` and is kept out of the plain FK map.
    fk = {"schwab_api_call_id": ("schwab_api_calls", "call_id"),
          "risk_policy_id_at_correction": ("risk_policy", "policy_id")}
    sup = ("(NEW.superseded_by_correction_id IS OLD.superseded_by_correction_id "
           "OR OLD.superseded_by_correction_id IS NULL OR "
           "(NEW.superseded_by_correction_id IS NULL AND NOT EXISTS (SELECT 1 FROM "
           "reconciliation_corrections WHERE correction_id = "
           "OLD.superseded_by_correction_id)))")
    imm = [x for x in cols(c, t)
           if x not in fk and x != "superseded_by_correction_id"]
    ddl_ruled = twin_ddl("trg_probe_rc_twin", t, twin_predicate(
        [x for x in imm], write_once=[], fk_setnull=fk,
        extra=[sup]), "probe rc twin")
    imm2 = [x for x in imm if x != "correction_set_id"]
    ddl_alt = twin_ddl("trg_probe_rc_twin", t, twin_predicate(
        imm2, write_once=["correction_set_id"], fk_setnull=fk,
        extra=[sup]), "probe rc twin")
    src = c.execute(f"SELECT correction_id FROM {t} ORDER BY correction_id "
                    "LIMIT 1").fetchone()[0]
    ncols = [x for x in cols(c, t) if x not in ("correction_id",)]
    sel = ", ".join("NULL" if x in ("correction_set_id", "superseded_by_correction_id")
                    else x for x in ncols)
    seed = (f"INSERT INTO {t} (correction_id, {', '.join(ncols)}) SELECT 900001, "
            f"{sel} FROM {t} WHERE correction_id = {src}")
    stmt = (f"UPDATE {t} SET correction_set_id = ? WHERE correction_id = ?",
            (900001, 900001))
    p.run("M3-rc", t, "RD-enumerated twin", "3251 correction_set_id NULL->self",
          ("info",), [seed, ddl_ruled], [stmt])
    p.run("M3-rc", t, "twin + correction_set_id write-once",
          "3251 correction_set_id NULL->self", ("ok",), [seed, ddl_alt], [stmt])
    p.run("M3-rc", t, "twin + correction_set_id write-once",
          "correction_set_id value->other ABORTS", ("fires", "trg_probe_rc_twin"),
          [seed, ddl_alt, stmt], [(f"UPDATE {t} SET correction_set_id = 1 "
                                   "WHERE correction_id = 900001",)])
    p.run("M3-rc", t, "twin + correction_set_id write-once",
          "repo:208 superseded_by NULL->value", ("ok",), [seed, ddl_alt],
          [(f"UPDATE {t} SET superseded_by_correction_id = ? WHERE correction_id = ?",
            (src, 900001))])

    # (b) daily_management_records: RD's twin (i) as written -- refuse ANY
    #     UPDATE of a row whose OLD.superseded_by_record_id IS NOT NULL OR
    #     OLD.is_superseded = 1, except the SET NULL FK transitions -- vs the
    #     supersede sequence step 3 (:822) then step 5 (:875).
    t = "daily_management_records"
    fk = {"linked_trade_event_id": ("trade_events", "id"),
          "superseded_by_record_id": ("daily_management_records",
                                      "management_record_id"),
          "pipeline_run_id": ("pipeline_runs", "id")}
    others = [x for x in cols(c, t) if x not in fk]
    fk_only = twin_predicate(others, fk_setnull=fk)
    ddl_i = twin_ddl(
        "trg_probe_dmr_superseded_frozen", t,
        f"(OLD.superseded_by_record_id IS NULL AND OLD.is_superseded = 0) OR (\n    "
        f"{fk_only})", "probe dmr (i) literal")
    ids = [r[0] for r in c.execute(
        f"SELECT management_record_id FROM {t} ORDER BY 1 LIMIT 2")]
    step3 = (f"UPDATE {t} SET is_superseded = 1 WHERE management_record_id = ?",
             (ids[0],))
    step5 = (f"UPDATE {t} SET superseded_by_record_id = ? "
             "WHERE management_record_id = ?", (ids[1], ids[0]))
    p.run("M3-dmr", t, "RD twin (i) literal", "supersede step 3 (:822) 0->1",
          ("ok",), [ddl_i], [step3])
    p.run("M3-dmr", t, "RD twin (i) literal", "supersede step 5 (:875) after step 3",
          ("info",), [ddl_i, step3], [step5])
    ddl_i2 = twin_ddl(
        "trg_probe_dmr_superseded_frozen", t,
        f"(OLD.superseded_by_record_id IS NULL AND OLD.is_superseded = 0) OR (\n    "
        f"OLD.superseded_by_record_id IS NULL AND OLD.is_superseded = 1 AND "
        f"NEW.superseded_by_record_id IS NOT NULL AND "
        f"{twin_predicate([x for x in cols(c, t) if x != 'superseded_by_record_id'])}"
        f") OR (\n    {fk_only})", "probe dmr (i) corrected")
    p.run("M3-dmr", t, "twin (i) + step-5 pointer admission",
          "supersede step 5 after step 3", ("ok",), [ddl_i2, step3], [step5])
    p.run("M3-dmr", t, "twin (i) + step-5 pointer admission",
          "data column on a superseded row ABORTS",
          ("fires", "trg_probe_dmr_superseded_frozen"), [ddl_i2, step3, step5],
          [(f"UPDATE {t} SET current_price = 1.0 WHERE management_record_id = ?",
            (ids[0],))])
    p.run("M3-dmr", t, "twin (i) + step-5 pointer admission",
          "step-5 shape carrying a data column ABORTS",
          ("fires", "trg_probe_dmr_superseded_frozen"), [ddl_i2, step3],
          [(f"UPDATE {t} SET superseded_by_record_id = ?, current_price = 1.0 "
            "WHERE management_record_id = ?", (ids[1], ids[0]))])

    # (c) review_log: a conflict-scoped no_replace on the UNIQUE key vs the
    #     NIGHTLY insert_pre_create (review_log.py:135-164, runner.py:4207),
    #     which is idempotent by catching the UNIQUE IntegrityError BY MESSAGE.
    t = "review_log"
    ddl_nr = ("CREATE TRIGGER trg_probe_review_log_no_replace BEFORE INSERT ON "
              "review_log FOR EACH ROW WHEN EXISTS (SELECT 1 FROM review_log WHERE "
              "(NEW.review_id != -1 AND review_id = NEW.review_id) OR "
              "(review_type = NEW.review_type AND period_start = NEW.period_start "
              "AND period_end = NEW.period_end)) BEGIN SELECT RAISE(ABORT, "
              "'probe review_log no_replace'); END")
    rt, ps, pe, sd = c.execute("SELECT review_type, period_start, period_end, "
                               "scheduled_date FROM review_log ORDER BY review_id "
                               "DESC LIMIT 1").fetchone()
    ins = ("INSERT INTO review_log (review_type, period_start, period_end, "
           "scheduled_date) VALUES (?, ?, ?, ?)", (rt, ps, pe, sd))
    o = p.run("M3-rl", t, "no_replace absent (v40)",
              "insert_pre_create on existing key", ("info",), [], [ins])
    p.out.write(f"#M3-rl\tv40 message contains UNIQUE: {'UNIQUE' in o}\n")
    o = p.run("M3-rl", t, "no_replace present",
              "insert_pre_create on existing key", ("info",), [ddl_nr], [ins])
    p.out.write(f"#M3-rl\tguarded message contains UNIQUE: {'UNIQUE' in o} "
                "(the writer's idempotent branch keys on it)\n")
    p.run("M3-rl", t, "no_replace present",
          "WHERE NOT EXISTS pre-filter form (F-I3) no-ops", ("ok",), [ddl_nr],
          [("INSERT INTO review_log (review_type, period_start, period_end, "
            "scheduled_date) SELECT ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM "
            "review_log WHERE review_type = ? AND period_start = ? AND "
            "period_end = ?)", (rt, ps, pe, sd, rt, ps, pe))],
          post=lambda cn: "changes=" + str(cn.execute("SELECT changes()").fetchone()[0]))

    # (d) review_log: RD's twin (frozen aggregates once completed_date IS NOT
    #     NULL) vs complete_review_atomic's UPDATE (review_log.py:293) re-run on
    #     an ALREADY-completed row -- reachable from the CLI (cli.py:2196), which
    #     carries no completed-row refusal (the web route refuses 409,
    #     routes/trades.py:3766-3770).
    frozen = ["completed_date", "n_trades_reviewed", "total_mistake_cost_R",
              "total_lucky_violation_R", "net_R_effective", "expectancy_R_effective",
              "win_rate", "avg_win_R", "avg_loss_R", "profit_factor",
              "max_drawdown_R", "risk_policy_id_at_review_completion"]
    ddl_rl = twin_ddl("trg_probe_review_log_twin", t,
                      "OLD.completed_date IS NULL OR (" + twin_predicate(frozen) + ")",
                      "probe review_log twin")
    rid = c.execute("SELECT review_id FROM review_log WHERE completed_date IS NOT "
                    "NULL ORDER BY review_id DESC LIMIT 1").fetchone()[0]
    p.run("M3-rl", t, "RD twin (frozen once completed)",
          "CLI re-completion of a completed row (repo :293 shape)", ("info",),
          [ddl_rl], [("UPDATE review_log SET completed_date = '2099-01-01', "
                      "n_trades_reviewed = n_trades_reviewed + 1 "
                      "WHERE review_id = ?", (rid,))])
    p.run("M3-rl", t, "RD twin (frozen once completed)",
          "auto_correct :2404 superseded pointer on a completed row", ("ok",),
          [ddl_rl], [("UPDATE review_log SET superseded_by_correction_id = "
                      "(SELECT max(correction_id) FROM reconciliation_corrections) "
                      "WHERE review_id = ?", (rid,))])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--copy", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    copy = Path(a.copy).resolve()
    if copy == LIVE_DB.resolve():
        print("REFUSED: never against the live DB", file=sys.stderr)
        return 2
    census = _census()
    with Path(a.out).open("w", encoding="utf-8", newline="\n") as out:
        out.write(f"#TARGET\tCOPY\t{copy}\n")
        p = census.Probe(copy, out)
        out.write("section\ttable\ttrigger_under_test\tprobe\texpect\toutcome\tverdict\n")
        m1_daily_recommendations(p)
        m3_compositions(p)
        out.write(f"#M1M3-SUMMARY\tPASS={p.n_pass}\tFAIL={p.n_fail}\tINFO={p.n_info}\n")
        p.conn.close()
        m2_rebuilt_pc_update(copy, copy.parent, out, census)
    print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
