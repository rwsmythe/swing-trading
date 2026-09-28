"""22-I round-0 guard census probe (Phase 22, arc 22-I, the REPLACE-exposure sweep).

WHAT IT DOES
    Probes every EXISTING append-only / immutability guard in the schema by the
    measured standard (control + test, default ``PRAGMA recursive_triggers``),
    runs the NULL-``WHEN`` per-input coverage probes on every WHEN-clause (and
    body-WHERE) validation trigger, and measures the CURRENT exposure of every
    unguarded table carrying a stated contract (the F-I1 evidence).

SAFETY -- READ BEFORE RUNNING
    * Plain ``sqlite3`` only. This script never imports ``swing`` and therefore
      can never reach ``ensure_schema`` (which would auto-migrate the file it
      opened -- CLAUDE.md, the pre-image gotcha).
    * ``--make-copy`` opens the LIVE DB ``mode=ro`` and writes ONE backup-API
      copy into the scratch dir. The live file is never opened writable.
    * Every write probe runs on the COPY inside ``BEGIN ... ROLLBACK``; the copy
      is left byte-for-byte as the backup wrote it. The script REFUSES to run
      write probes against the live path.
    * ``--live-ro`` runs the catalogue checks only (trigger inventory,
      ``recursive_triggers``, negative-id scan, ``foreign_key_check``) against
      the live DB ``mode=ro`` -- the witness sitting's W5 form.
    * ``--post-migrate`` (22-I T18; requires ``--copy``, keeps the live-path
      refusal) runs the census on a copy MIGRATED to v41: it adds ONE section,
      ``G-0041`` (every 0041 guard, driven by ``tests/data/_22i_guard_spec.py``
      loaded BY PATH -- the spec imports nothing from ``swing``), and applies
      the ruled expectation corrections to the existing sections: the five
      PK -> NULL probes (4 pc + 1 eia) expect the engine's ``datatype
      mismatch`` (CHARC F-I2: engine-refused, not a finding); F-I5's
      first-view columns expect ``trg_lve_first_view_immutable``; and two
      in-txn SETUP changes, each rolled back with its probe -- the pc
      risk-policy-branch probes drop ``trg_rp_no_delete`` before deleting
      their risk_policy row (a clause pin, the parent delete is refused in
      production, AL-9), and the lve identity-UPDATE probes drop
      ``trg_lve_first_view_immutable``, which now pre-empts the older
      identity trigger they pin. On the two (c) no-twin tables the PK is
      probed as REFUSED by ``trg_<abbr>_pk_immutable`` (Reviewer B B2, CHARC
      Branch A); it is no longer an M probe.

USAGE
    python scripts/probe_22i_guard_census.py --make-copy
    python scripts/probe_22i_guard_census.py --copy <copy.db> --out <result.txt>
    python scripts/probe_22i_guard_census.py --live-ro --out <result.txt>
    python scripts/probe_22i_guard_census.py --post-migrate --copy <v41 copy> --out <r>

OUTPUT
    One TSV line per probe: section, table, trigger-under-test, probe id,
    expectation, observed outcome, verdict (PASS / FAIL / INFO).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sqlite3
import sys
from pathlib import Path

LIVE_DB = Path(os.path.expanduser("~")) / "swing-data" / "swing.db"
SCRATCH = Path(os.path.expanduser("~")) / "swing-data" / "scratch" / "22-i-probe"

_RAISE_RE = re.compile(r"RAISE\s*\(\s*ABORT\s*,\s*'((?:[^']|'')*)'\s*\)", re.S)

# The guarded tables and their guard triggers (v40), with the conflict targets
# each no_replace barrier covers.
GUARDED = {
    "candidates": dict(pk="id", no_replace="trg_candidates_no_replace",
                       no_delete="trg_candidates_no_delete",
                       no_update="trg_candidates_no_update"),
    "fill_envelope_identity": dict(pk="identity_id",
                                   no_replace="trg_fei_no_replace",
                                   no_delete="trg_fei_no_delete",
                                   no_update="trg_fei_no_update"),
    "latch_order_intents": dict(pk="intent_id", no_replace="trg_loi_no_replace",
                                no_delete="trg_loi_no_delete",
                                no_update="trg_loi_no_update"),
    "latch_order_mandate_links": dict(pk="link_id",
                                      no_replace="trg_loml_no_replace",
                                      no_delete="trg_loml_no_delete",
                                      no_update="trg_loml_no_update"),
    "latch_view_events": dict(pk="view_event_id", no_replace="trg_lve_no_replace",
                              no_delete="trg_lve_no_delete", no_update=None),
    "entry_intent_attestations": dict(pk="attestation_id",
                                      no_replace="trg_eia_no_replace",
                                      no_delete="trg_eia_no_delete",
                                      no_update="trg_eia_no_update"),
    "provenance_corrections": dict(
        pk="provenance_correction_id", no_replace="trg_pc_no_replace",
        no_delete="trg_provenance_corrections_append_only_delete",
        no_update="trg_provenance_corrections_append_only_update"),
}


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------
class Probe:
    def __init__(self, path: Path, out):
        self.path = path
        self.out = out
        self.conn = self._open(fk=True)
        self.msg_to_trigger: dict[str, list[str]] = {}
        for name, sql in self.conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger'"):
            for m in _RAISE_RE.finditer(sql):
                self.msg_to_trigger.setdefault(
                    m.group(1).replace("''", "'"), []).append(name)
        self.n_pass = self.n_fail = self.n_info = 0
        self.post_migrate = False

    def _open(self, fk: bool) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path), isolation_level=None)
        c.execute(f"PRAGMA foreign_keys={'ON' if fk else 'OFF'}")
        assert c.execute("PRAGMA recursive_triggers").fetchone()[0] == 0
        return c

    def info_row(self, section: str, table: str, tut: str | None, pid: str,
                message: str) -> None:
        """The ONE place a direct (non-``run``-routed) INFO row is emitted --
        couples the row write to the counter so they cannot diverge again
        (R-4, 2026-09-28: ``exposure()``'s empty-table INFO write was
        missing its ``n_info += 1``, undercounting ``#SUMMARY`` INFO by one
        per empty exposure table). Column shape matches ``run()``'s own
        write exactly: section, table, tut-or-dash, pid, the literal
        ``info`` expectation, the message, the literal ``INFO`` verdict."""
        self.out.write(
            "\t".join([section, table, tut or "-", pid, "info", message, "INFO"]) + "\n"
        )
        self.n_info += 1

    def classify(self, exc: Exception | None) -> str:
        if exc is None:
            return "OK"
        msg = str(exc)
        if msg in self.msg_to_trigger:
            return "TRIGGER:" + "|".join(sorted(self.msg_to_trigger[msg]))
        for k in ("NOT NULL", "CHECK", "UNIQUE", "FOREIGN KEY"):
            if msg.startswith(k + " constraint failed"):
                return f"CONSTRAINT:{k}:{msg[len(k) + 19:][:80]}"
        return "ERROR:" + msg[:120]

    def run(self, section, table, tut, pid, expect, setup, stmt, params=(),
            post=None, fk=True):
        """Run one probe in BEGIN..ROLLBACK. ``expect`` is a predicate over
        the outcome string, given as ('fires', trig) / ('ok',) / ('not', trig)
        / ('outcome', substring) / ('info',)."""
        conn = self.conn if fk else self._open(fk=False)
        conn.execute("BEGIN")
        exc = None
        extra = ""
        try:
            for s in setup:
                if isinstance(s, tuple):
                    conn.execute(*s)
                else:
                    conn.execute(s)
            try:
                if isinstance(stmt, list):
                    for s in stmt:
                        conn.execute(*s) if isinstance(s, tuple) else conn.execute(s)
                else:
                    conn.execute(stmt, params)
            except sqlite3.DatabaseError as e:  # noqa: PERF203
                exc = e
            if post and exc is None:
                extra = " | " + str(post(conn))
        finally:
            conn.execute("ROLLBACK")
            if not fk:
                conn.close()
        outcome = self.classify(exc)
        kind = expect[0]
        if kind == "fires":
            ok = outcome.startswith("TRIGGER:") and expect[1] in outcome
        elif kind == "ok":
            ok = outcome == "OK"
        elif kind == "not":
            ok = not (outcome.startswith("TRIGGER:") and expect[1] in outcome)
        elif kind == "outcome":
            ok = expect[1] in outcome
        else:
            ok = None
        verdict = "INFO" if ok is None else ("PASS" if ok else "FAIL")
        if verdict == "PASS":
            self.n_pass += 1
        elif verdict == "FAIL":
            self.n_fail += 1
        else:
            self.n_info += 1
        exp = " ".join(map(str, expect))
        cell = " ".join((outcome + extra).split())
        self.out.write("\t".join([section, table, tut or "-", pid, exp,
                                  cell, verdict]) + "\n")
        return outcome

    # helpers -------------------------------------------------------------
    def cols(self, table):
        return [r[1] for r in self.conn.execute(f"PRAGMA table_info('{table}')")]

    def row(self, table, where, params=()):
        cur = self.conn.execute(f"SELECT * FROM {table} WHERE {where}", params)
        names = [d[0] for d in cur.description]
        r = cur.fetchone()
        return None if r is None else dict(zip(names, r, strict=True))

    @staticmethod
    def ins(table, rowd, verb="INSERT"):
        cols = list(rowd)
        return (f"{verb} INTO {table} ({', '.join(cols)}) VALUES "
                f"({', '.join('?' * len(cols))})", tuple(rowd[c] for c in cols))

    def other_triggers_drop(self, table, keep, event_like):
        return [f"DROP TRIGGER {n}" for (n,) in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? "
            "AND name<>? AND sql LIKE ?", (table, keep, event_like))]


# --------------------------------------------------------------------------
# section A: catalogue (read-only; safe on live mode=ro)
# --------------------------------------------------------------------------
def catalogue(conn, out):
    w = out.write
    ver = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    rt = conn.execute("PRAGMA recursive_triggers").fetchone()[0]
    w(f"#CATALOGUE\tschema_version\t{ver}\n")
    w(f"#CATALOGUE\trecursive_triggers\t{rt}\n")
    rows = conn.execute("SELECT tbl_name, count(*) FROM sqlite_master "
                        "WHERE type='trigger' GROUP BY tbl_name ORDER BY 1").fetchall()
    w(f"#CATALOGUE\ttrigger_total\t{sum(n for _, n in rows)} on {len(rows)} tables\n")
    for t, n in rows:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? "
            "ORDER BY name", (t,))]
        w(f"#CATALOGUE\ttriggers\t{t}\t{n}\t{','.join(names)}\n")
    for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' "
                             "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        pk = [r[1] for r in conn.execute(f"PRAGMA table_info('{t}')") if r[5]]
        if len(pk) == 1:
            neg = conn.execute(f'SELECT count(*) FROM "{t}" WHERE typeof("{pk[0]}")'
                               f"='integer' AND \"{pk[0]}\" <= 0").fetchone()[0]
            w(f"#CATALOGUE\tnonpositive_pk\t{t}.{pk[0]}\t{neg}\n")
    w(f"#CATALOGUE\tforeign_key_check\t{conn.execute('PRAGMA foreign_key_check').fetchall()}\n")


# --------------------------------------------------------------------------
# section B: the guard triple, three directions + delete + update
# --------------------------------------------------------------------------
def fresh_row(p: Probe, table):
    """A NON-conflicting append built from a live row (the pk omitted), plus the
    setup that isolates the guard under test where a copied row cannot pass the
    table's own validation triggers unaided. Returns (setup, rowdict, note)."""
    pk = GUARDED[table]["pk"]
    if table == "candidates":
        r = p.row(table, "id = (SELECT max(id) FROM candidates)")
        r.pop(pk)
        r["ticker"] = "ZZPROBE"
        return [], r, "copy of max-id row, ticker=ZZPROBE"
    if table == "fill_envelope_identity":
        r = p.row(table, "identity_id = 1")
        r.pop(pk)
        r["envelope_raw"] = r["envelope_raw"] + " "
        return [], r, "copy of id 1, envelope_raw + ' '"
    if table == "latch_order_intents":
        r = p.row(table, "intent_id = 1")  # a place row: no mint
        r.pop(pk)
        r["idempotency_key"] = "zz-probe-22i"
        return [], r, "copy of place intent 1, new idempotency_key"
    if table == "latch_order_mandate_links":
        r = p.row(table, "link_id = 1")
        r.pop(pk)
        r["validity_intent_id"] = 3  # an unlinked intent (a place row; FK-valid)
        return [], r, "copy of link 1, validity_intent_id=3 (unlinked)"
    if table == "latch_view_events":
        r = p.row(table, "view_event_id = 1")
        r.pop(pk)
        r["view_session_date"] = "2099-01-02"
        return [], r, "copy of view 1, view_session_date=2099-01-02"
    if table == "entry_intent_attestations":
        r = p.row(table, "attestation_id = 1")
        r.pop(pk)
        r["trade_id"] = 1
        setup = p.other_triggers_drop(table, GUARDED[table]["no_replace"],
                                      "%BEFORE INSERT%")
        return setup, r, ("copy of attestation 1, trade_id=1; the six validation "
                          "triggers dropped in-txn to isolate the guard")
    if table == "provenance_corrections":
        r = p.row(table, "trade_id = 23")
        r.pop(pk)
        r["trade_id"] = 1
        r["entry_fill_snapshot_json"] = p.conn.execute(
            "SELECT json_set(?, '$.trade_id', 1)",
            (r["entry_fill_snapshot_json"],)).fetchone()[0]
        setup = ["DROP TRIGGER trg_provenance_corrections_citation_graph"]
        return setup, r, ("copy of trade-23 correction, trade_id=1; citation "
                          "graph dropped in-txn to isolate the guard")
    raise KeyError(table)


def conflict_rows(p: Probe, table):
    """(unique-key conflict row with pk omitted, explicit-pk conflict row with a
    fresh unique key, value-change column) for the REPLACE directions."""
    pk = GUARDED[table]["pk"]
    # a CHILDLESS live row where FK RESTRICT children would otherwise make the
    # barrier-dropped control fail on the FK rather than show the REPLACE.
    where = {"latch_order_intents": "intent_id = 3",
             "latch_order_mandate_links":
                 "link_id NOT IN (SELECT cited_latch_link_id FROM provenance_corrections "
                 "WHERE cited_latch_link_id IS NOT NULL UNION SELECT cited_latch_link_id "
                 "FROM entry_intent_attestations WHERE cited_latch_link_id IS NOT NULL) "
                 "ORDER BY link_id LIMIT 1"}.get(table, f"{pk} = (SELECT min({pk}) FROM {table})")
    live = p.row(table, where)
    setup, fresh, _ = fresh_row(p, table)
    uk = dict(live)
    uk.pop(pk)
    # change one non-key payload column so a successful REPLACE is visible
    change = {
        "candidates": ("close", (live.get("close") or 1.0) + 1000),
        "fill_envelope_identity": ("recorded_ts", "2099-01-01T00:00:00"),
        "latch_order_intents": ("recorded_ts", "2099-01-01T00:00:00"),
        "latch_order_mandate_links": ("linked_at", "2099-01-01T00:00:00Z"),
        "latch_view_events": ("last_viewed_ts", "2099-01-01T00:00:00"),
        "entry_intent_attestations": ("applied_by", "zz-probe"),
        "provenance_corrections": ("correction_reason", "zz-probe rewrite"),
    }[table]
    uk[change[0]] = change[1]
    idc = dict(fresh)
    idc[pk] = live[pk]
    return setup, live, uk, idc, change


def guard_triple(p: Probe):
    for table, g in GUARDED.items():
        pk = g["pk"]
        nr, nd, nu = g["no_replace"], g["no_delete"], g["no_update"]
        setup, fresh, note = fresh_row(p, table)
        # D1 ordinary append SUCCEEDS (the -1 sentinel for an omitted pk does
        # not match any stored row)
        p.run("B-triple", table, nr, "D1-append", ("ok",), setup,
              *Probe.ins(table, fresh), post=lambda c, t=table, k=pk, note=note:
              f"new {k}={c.execute(f'SELECT max({k}) FROM {t}').fetchone()[0]} ({note})")
        s2, live, uk, idc, change = conflict_rows(p, table)
        # D2 conflicting REPLACE on the UNIQUE key (pk omitted) ABORTS; control
        # with the barrier dropped shows what the barrier prevents.
        for verb in ("INSERT OR REPLACE", "REPLACE", "INSERT OR IGNORE"):
            p.run("B-triple", table, nr, f"D2-{verb.replace(' ', '_')}-uniquekey",
                  ("fires", nr), s2, *Probe.ins(table, uk, verb))
        sql, prm = Probe.ins(table, uk)
        p.run("B-triple", table, nr, "D2-ON_CONFLICT_DO_NOTHING-uniquekey",
              ("fires", nr), s2, sql + " ON CONFLICT DO NOTHING", prm)
        p.run("B-triple", table, nr, "D2-control-barrier-dropped", ("info",),
              s2 + [f"DROP TRIGGER {nr}"], *Probe.ins(table, uk, "INSERT OR REPLACE"),
              post=lambda c, t=table, k=pk, lv=live, ch=change:
              "rows at old id="
              f"{c.execute(f'SELECT count(*) FROM {t} WHERE {k}=?', (lv[k],)).fetchone()[0]}"
              f"; {ch[0]} rewritten="
              f"{c.execute(f'SELECT count(*) FROM {t} WHERE {ch[0]}=?', (ch[1],)).fetchone()[0]}")
        # D3 explicit conflicting id ABORTS (plain INSERT and INSERT OR REPLACE)
        p.run("B-triple", table, nr, "D3-explicit-id-INSERT", ("fires", nr),
              s2, *Probe.ins(table, idc))
        p.run("B-triple", table, nr, "D3-explicit-id-INSERT_OR_REPLACE",
              ("fires", nr), s2, *Probe.ins(table, idc, "INSERT OR REPLACE"))
        # D4 DELETE ABORTS
        p.run("B-triple", table, nd, "D4-delete", ("fires", nd), [],
              f"DELETE FROM {table} WHERE {pk} = ?", (live[pk],))
        # D5 UPDATE of a guarded column ABORTS
        if nu:
            p.run("B-triple", table, nu, f"D5-update-{change[0]}", ("fires", nu),
                  [], f"UPDATE {table} SET {change[0]} = ? WHERE {pk} = ?",
                  (change[1], live[pk]))
        # the -1 sentinel residual (INFO): an explicit -1 is indistinguishable
        # from an omitted pk.
        m1 = dict(fresh)
        m1[pk] = -1
        p.run("B-triple", table, nr, "R-explicit-minus-1", ("info",), setup,
              *Probe.ins(table, m1))


def lve_update_guards(p: Probe):
    t = "latch_view_events"
    r0 = p.row(t, "actionable_ever_viewed = 0")
    r1 = p.row(t, "actionable_ever_viewed = 1")
    for col, val in (("first_viewed_ts", "2099-01-01T00:00:00"),
                     ("ticker", "ZZPROBE"), ("first_viewed_ts", None),
                     ("ticker", None)):
        p.run("B-lve-update", t, "trg_lve_view_window_immutable",
              f"update-{col}={'NULL' if val is None else 'x'}",
              ("fires", "trg_lve_view_window_immutable"), [],
              f"UPDATE {t} SET {col}=? WHERE view_event_id=?",
              (val, r0["view_event_id"]))
    mono = "trg_lve_actionable_ever_viewed_monotonic"
    if r1:
        p.run("B-lve-update", t, mono, "1->0", ("fires", mono), [],
              f"UPDATE {t} SET actionable_ever_viewed=0 WHERE view_event_id=?",
              (r1["view_event_id"],))
        p.run("B-lve-update", t, mono, "1->NULL (NULL-WHEN)", ("fires", mono), [],
              f"UPDATE {t} SET actionable_ever_viewed=NULL WHERE view_event_id=?",
              (r1["view_event_id"],))
    p.run("B-lve-update", t, mono, "control 0->1", ("not", mono), [],
          f"UPDATE {t} SET actionable_ever_viewed=1 WHERE view_event_id=?",
          (r0["view_event_id"],))
    # columns with NO update guard (the declared UPDATE-in-place columns)
    first_view = ("view_session_date", "latch_state_at_first_view",
                  "actionable_at_first_view")
    fv = "trg_lve_first_view_immutable"
    for col, val in (("last_viewed_ts", "2099-01-01T00:00:00"), ("view_count", 99),
                     ("latch_state_at_last_view", "superseded"),
                     ("view_session_date", "2099-01-03"),
                     ("latch_state_at_first_view", "superseded"),
                     ("actionable_at_first_view", 1)):
        if p.post_migrate and col in first_view:  # F-I5 (0041)
            p.run("B-lve-update", t, fv, f"first-view-update-{col}", ("fires", fv),
                  [], f"UPDATE {t} SET {col}=? WHERE view_event_id=?",
                  (val, r0["view_event_id"]))
            continue
        p.run("B-lve-update", t, None, f"unguarded-update-{col}", ("info",), [],
              f"UPDATE {t} SET {col}=? WHERE view_event_id=?",
              (val, r0["view_event_id"]))


def epoch(p: Probe):
    t = "candidates_immutability_epoch"
    live = p.row(t, "epoch_id = 1")
    ni, nu, nd = ("trg_candidates_epoch_no_insert", "trg_candidates_epoch_no_update",
                  "trg_candidates_epoch_no_delete")
    ch = dict(live)
    ch["max_candidate_id_at_barrier"] = live["max_candidate_id_at_barrier"] + 1
    for verb in ("INSERT OR REPLACE", "REPLACE", "INSERT OR IGNORE", "INSERT"):
        p.run("B-epoch", t, ni, f"{verb.replace(' ', '_')}-id1", ("fires", ni), [],
              *Probe.ins(t, ch, verb))
    sql, prm = Probe.ins(t, ch)
    p.run("B-epoch", t, ni, "ON_CONFLICT_DO_NOTHING-id1", ("fires", ni), [],
          sql + " ON CONFLICT DO NOTHING", prm)
    p.run("B-epoch", t, ni, "control-no_insert-dropped-REPLACE", ("info",),
          [f"DROP TRIGGER {ni}"], *Probe.ins(t, ch, "INSERT OR REPLACE"),
          post=lambda c: "stored max_candidate_id_at_barrier="
          f"{c.execute(f'SELECT max_candidate_id_at_barrier FROM {t}').fetchone()[0]}"
          f" (was {live['max_candidate_id_at_barrier']}); no_delete did NOT fire")
    p.run("B-epoch", t, nd, "delete", ("fires", nd), [], f"DELETE FROM {t}")
    p.run("B-epoch", t, nu, "update", ("fires", nu), [],
          f"UPDATE {t} SET applied_at='x'")


# --------------------------------------------------------------------------
# section C: NULL-WHEN coverage -- provenance_corrections (FIRST target)
# --------------------------------------------------------------------------
PC_CG = "trg_provenance_corrections_citation_graph"
PC_UP = "trg_provenance_corrections_append_only_update"
PC_JSON = ("entry_fill_snapshot_json", "cited_latch_probe_json",
           "cited_frozen_value_evidence_json")


def json_nodes(conn, blob):
    return [(fp, ty) for fp, ty in conn.execute(
        "SELECT fullkey, type FROM json_tree(?) WHERE fullkey <> '$'", (blob,))]


def pc_citation_graph(p: Probe):
    iso = ["DROP TRIGGER trg_pc_no_replace",
           "DROP INDEX ux_provenance_corrections_trade"]
    for trade in (23, 25):
        base = p.row("provenance_corrections", "trade_id = ?", (trade,))
        base.pop("provenance_correction_id")
        tag = f"pc-{trade}-{base['admission_tier']}"
        # CONTROL: an exact replay of the STORED row
        p.run("C-pc-citation", tag, PC_CG, "control-replay-stored-row", ("info",),
              iso, *Probe.ins("provenance_corrections", base))
        # The trade-23 row predates the R14-02 operand freeze (its snapshot has
        # no quantity/price/fill_origin/envelope), so v40 refuses its replay by
        # design. The per-input probes run on the OPERAND-COMPLETED row -- a
        # base the trigger ADMITS -- or every mutation would "fire" on the
        # missing operands and the probe would route around the branch.
        snap = base["entry_fill_snapshot_json"]
        if p.conn.execute("SELECT json_type(?, '$.quantity')", (snap,)).fetchone()[0] is None:
            base["entry_fill_snapshot_json"] = p.conn.execute(
                "SELECT json_set(?, '$.quantity', f.quantity, '$.price', f.price, "
                "'$.fill_origin', f.fill_origin, '$.envelope', "
                "f.schwab_source_value_json) FROM fills f WHERE f.fill_id = ?",
                (snap, base["entry_fill_id_at_correction"])).fetchone()[0]
            tag += "-operand-completed"
        p.run("C-pc-citation", tag, PC_CG, "control-replay", ("ok",), iso,
              *Probe.ins("provenance_corrections", base))
        # CONTROL: the JSON re-minification the mutations use does not flip it
        mini = dict(base)
        for jc in PC_JSON:
            if mini[jc] is not None:
                mini[jc] = p.conn.execute("SELECT json(?)", (mini[jc],)).fetchone()[0]
        p.run("C-pc-citation", tag, PC_CG, "control-replay-minified-json", ("ok",),
              iso, *Probe.ins("provenance_corrections", mini))
        # per NEW column NULL
        code = p.conn.execute("SELECT sql FROM sqlite_master WHERE name=?",
                              (PC_CG,)).fetchone()[0]
        code = "\n".join(ln.split("--")[0] for ln in code.splitlines())
        refd = sorted(set(re.findall(r"NEW\.(\w+)", code)))
        for col in refd:
            if base[col] is None:
                continue
            m = dict(mini)
            m[col] = None
            p.run("C-pc-citation", tag, PC_CG, f"NULL {col}", ("fires", PC_CG), iso,
                  *Probe.ins("provenance_corrections", m))
        # per JSON node: ABSENT, and JSON-null where the base is non-null
        for jc in PC_JSON:
            if mini[jc] is None:
                continue
            for path, ty in json_nodes(p.conn, mini[jc]):
                m = dict(mini)
                m[jc] = p.conn.execute("SELECT json_remove(?, ?)",
                                       (mini[jc], path)).fetchone()[0]
                p.run("C-pc-citation", tag, PC_CG, f"ABSENT {jc}:{path}",
                      ("fires", PC_CG), iso, *Probe.ins("provenance_corrections", m))
                if ty != "null":
                    m = dict(mini)
                    m[jc] = p.conn.execute("SELECT json_set(?, ?, json('null'))",
                                           (mini[jc], path)).fetchone()[0]
                    p.run("C-pc-citation", tag, PC_CG, f"JSONNULL {jc}:{path}",
                          ("fires", PC_CG), iso,
                          *Probe.ins("provenance_corrections", m))


def pc_append_only_update(p: Probe):
    t = "provenance_corrections"
    for trade in (23, 25):
        live = p.row(t, "trade_id = ?", (trade,))
        pcid, fill, rp = (live["provenance_correction_id"], live["entry_fill_id"],
                          live["risk_policy_id_at_correction"])
        tag = f"pc-{trade}"
        # CONTROL: the legitimate FK-driven nulling (the split_into_partials
        # fill DELETE, foreign_keys ON) is ADMITTED.
        p.run("C-pc-update", tag, PC_UP, "control-legit-fill-delete-cascade",
              ("ok",), [], "DELETE FROM fills WHERE fill_id = ?", (fill,),
              post=lambda c, i=pcid: "entry_fill_id now=" + str(c.execute(
                  f"SELECT entry_fill_id FROM {t} WHERE provenance_correction_id=?",
                  (i,)).fetchone()[0]))
        for col in p.cols(t):
            if col in ("entry_fill_id", "risk_policy_id_at_correction"):
                continue
            nullable = col in ("provenance_correction_id",) or not any(
                r[1] == col and r[3] for r in p.conn.execute(
                    f"PRAGMA table_info('{t}')"))
            # (i) plain UPDATE col=NULL (no FK change): the FK-change conjunct
            #     is FALSE, so it must fire regardless.
            pk_null = p.post_migrate and col == "provenance_correction_id"
            engine = ("outcome", "datatype mismatch")  # CHARC F-I2: engine-refused
            if live[col] is not None:
                p.run("C-pc-update", tag, PC_UP, f"plain NULL {col}",
                      engine if pk_null else ("fires", PC_UP), [],
                      f"UPDATE {t} SET {col}=NULL WHERE provenance_correction_id=?",
                      (pcid,))
            # (ii) the NULL-WHEN probe: the legitimate FK-null branch TRUE
            #      (fill gone, entry_fill_id -> NULL) AND col -> NULL.
            if live[col] is not None:
                p.run("C-pc-update", tag, PC_UP,
                      f"FKnull+NULL {col}{' (nullable)' if nullable else ''}",
                      engine if pk_null else ("fires", PC_UP),
                      [("DELETE FROM fills WHERE fill_id=?", (fill,))],
                      f"UPDATE {t} SET entry_fill_id=NULL, {col}=NULL "
                      f"WHERE provenance_correction_id=?", (pcid,), fk=False)
            # (iii) the same with a NON-NULL rewrite (the ordinary branch)
            p.run("C-pc-update", tag, PC_UP, f"FKnull+rewrite {col}",
                  ("fires", PC_UP), [("DELETE FROM fills WHERE fill_id=?", (fill,))],
                  f"UPDATE {t} SET entry_fill_id=NULL, {col}="
                  f"CASE WHEN typeof({col}) IN ('integer','real') THEN {col}+100000 "
                  f"ELSE coalesce({col},'') || 'x' END "
                  f"WHERE provenance_correction_id=?", (pcid,), fk=False)
        # risk-policy branch of the FK-null exception, NULL-WHEN form
        if rp is not None:
            # 22-I: 0041's trg_rp_no_delete refuses the parent delete these
            # clause probes set up with; under --post-migrate it is dropped
            # in-txn (rolled back with the probe) -- "clause pin, parent delete
            # refused in production" (AL-9).
            rp_pre = ["DROP TRIGGER trg_rp_no_delete"] if p.post_migrate else []
            p.run("C-pc-update", tag, PC_UP, "control-legit-riskpolicy-null",
                  ("ok",),
                  rp_pre + [("DELETE FROM risk_policy WHERE policy_id=?", (rp,))],
                  f"UPDATE {t} SET risk_policy_id_at_correction=NULL "
                  f"WHERE provenance_correction_id=?", (pcid,), fk=False)
            p.run("C-pc-update", tag, PC_UP, "RPnull+NULL correction_reason",
                  ("fires", PC_UP),
                  rp_pre + [("DELETE FROM risk_policy WHERE policy_id=?", (rp,))],
                  f"UPDATE {t} SET risk_policy_id_at_correction=NULL, "
                  f"correction_reason=NULL WHERE provenance_correction_id=?",
                  (pcid,), fk=False)


# --------------------------------------------------------------------------
# section D: NULL-WHEN coverage -- the other validation triggers
# --------------------------------------------------------------------------
def referenced(p, trig):
    code = p.conn.execute("SELECT sql FROM sqlite_master WHERE name=?",
                          (trig,)).fetchone()[0]
    code = "\n".join(ln.split("--")[0] for ln in code.splitlines())
    return sorted(set(re.findall(r"NEW\.(\w+)", code)))


def eia_insert_triggers(p: Probe):
    t = "entry_intent_attestations"
    base = p.row(t, "attestation_id = 1")
    base.pop("attestation_id")
    # the live trade is now ATTESTED; trade_binding requires entry_intent NULL
    # at insert, so the setup restores the pre-assignment state in-txn.
    pre = ["DROP TRIGGER trg_trades_entry_intent_attested_terminal",
           ("UPDATE trades SET entry_intent=NULL WHERE id=?", (base["trade_id"],))]
    json_cols = ("cited_fields_json", "cited_text_snapshot_json",
                 "leg_evidence_json", "cited_latch_probe_json")
    for trig in ("trg_eia_audit_trail", "trg_eia_cited_fields", "trg_eia_outcome",
                 "trg_eia_structural", "trg_eia_tier2", "trg_eia_trade_binding"):
        iso = pre + p.other_triggers_drop(t, trig, "%BEFORE INSERT%")
        p.run("D-eia", t, trig, "control-replay (expect UNIQUE, trigger silent)",
              ("not", trig), iso, *Probe.ins(t, base))
        full = pre + ["DROP TRIGGER trg_eia_no_replace"]
        for col in referenced(p, trig):
            if base.get(col) is None:
                continue
            m = dict(base)
            m[col] = None
            o = p.run("D-eia", t, trig, f"NULL {col}", ("fires", trig), iso,
                      *Probe.ins(t, m))
            if not o.startswith("TRIGGER:"):
                p.run("D-eia-fullset", t, "any eia trigger", f"NULL {col} (all eia "
                      f"triggers present)", ("fires", "trg_eia_"), full,
                      *Probe.ins(t, m))
        for jc in json_cols:
            if base[jc] is None or jc not in referenced(p, trig):
                continue
            for path, _ty in json_nodes(p.conn, base[jc]):
                m = dict(base)
                m[jc] = p.conn.execute("SELECT json_remove(?, ?)",
                                       (base[jc], path)).fetchone()[0]
                o = p.run("D-eia", t, trig, f"ABSENT {jc}:{path}", ("fires", trig),
                          iso, *Probe.ins(t, m))
                if not o.startswith("TRIGGER:"):
                    p.run("D-eia-fullset", t, "any eia trigger",
                          f"ABSENT {jc}:{path} (all eia triggers present)",
                          ("fires", "trg_eia_"), full, *Probe.ins(t, m))


def eia_no_update(p: Probe):
    t = "entry_intent_attestations"
    trig = "trg_eia_no_update"
    live = p.row(t, "attestation_id = 1")
    fill = live["entry_fill_id"]
    p.run("D-eia-update", t, trig, "control-legit-fill-delete-cascade", ("ok",), [],
          "DELETE FROM fills WHERE fill_id=?", (fill,))
    for col in p.cols(t):
        if col == "entry_fill_id" or live[col] is None:
            continue
        exp = (("outcome", "datatype mismatch")  # CHARC F-I2: engine-refused
               if p.post_migrate and col == "attestation_id" else ("fires", trig))
        p.run("D-eia-update", t, trig, f"FKnull+NULL {col}", exp,
              [("DELETE FROM fills WHERE fill_id=?", (fill,))],
              f"UPDATE {t} SET entry_fill_id=NULL, {col}=NULL WHERE attestation_id=1",
              fk=False)


def identity_triggers(p: Probe):
    for t, trig_i, trig_u, pk, _key in (
            ("latch_order_intents", "trg_loi_identity_coherent_insert",
             "trg_loi_identity_coherent_update", "intent_id", "idempotency_key"),
            ("latch_view_events", "trg_lve_identity_coherent_insert",
             "trg_lve_identity_coherent_update", "view_event_id",
             "view_session_date")):
        _, fresh, _ = fresh_row(p, t)
        iso = [f"DROP TRIGGER {n}" for n in (
            "trg_loi_no_replace", "trg_loi_validity_parent_insert")
            if t == "latch_order_intents"] or ["DROP TRIGGER trg_lve_no_replace"]
        p.run("D-identity", t, trig_i, "control-fresh-append", ("ok",), iso,
              *Probe.ins(t, fresh))
        for col in ("candidate_id", "evaluation_run_id", "ticker", "detection_date",
                    "pipeline_run_id"):
            m = dict(fresh)
            m[col] = None
            exp = ("info",) if col == "pipeline_run_id" else ("fires", trig_i)
            p.run("D-identity", t, trig_i, f"NULL {col}", exp, iso, *Probe.ins(t, m))
        live_id = p.conn.execute(f"SELECT min({pk}) FROM {t}").fetchone()[0]
        drop_upd = (["DROP TRIGGER trg_loi_no_update"]
                    if t == "latch_order_intents" else [])
        for col in ("candidate_id", "evaluation_run_id", "ticker", "detection_date"):
            p.run("D-identity", t, trig_u, f"update NULL {col}", ("fires", trig_u),
                  drop_upd + (["DROP TRIGGER trg_lve_view_window_immutable"]
                              if t == "latch_view_events" else [])
                  + (["DROP TRIGGER trg_lve_first_view_immutable"]
                     if t == "latch_view_events" and p.post_migrate else []),
                  f"UPDATE {t} SET {col}=NULL WHERE {pk}=?", (live_id,))


def loi_validity_and_mint(p: Probe):
    t = "latch_order_intents"
    base = p.row(t, "intent_id = 13")  # an accepted validity row
    base.pop("intent_id")
    base["idempotency_key"] = "zz-probe-22i-validity"
    # its parent (place 7) already has a link via 13; the mint would collide on
    # nothing (validity_intent_id is the NEW id), so the control mints.
    p.run("D-loi", t, "trg_latch_link_mint_on_acceptance", "control-accepted-mints",
          ("ok",), [], *Probe.ins(t, base),
          post=lambda c: "links=" + str(c.execute(
              "SELECT count(*) FROM latch_order_mandate_links").fetchone()[0]))
    for col in ("validated_place_intent_id", "intent_kind", "validity_outcome",
                "actual_broker_order_id", "candidate_id", "action_session_date"):
        m = dict(base)
        m[col] = None
        p.run("D-loi", t, "trg_loi_validity_parent_insert|mint", f"NULL {col}",
              ("info",), [], *Probe.ins(t, m),
              post=lambda c: "links=" + str(c.execute(
                  "SELECT count(*) FROM latch_order_mandate_links").fetchone()[0]))


# --------------------------------------------------------------------------
# section E: current exposure of the unguarded contract tables (F-I1 evidence)
# --------------------------------------------------------------------------
EXPOSURE = ("account_equity_snapshots", "candidate_criteria", "cash_movements",
            "chart_renders", "daily_management_records", "daily_recommendations",
            "evaluation_runs", "finviz_api_calls", "hypothesis_registry",
            "hypothesis_status_history", "pattern_detection_events",
            "pattern_evaluations", "pattern_exemplars", "pattern_forward_observations",
            "pipeline_step_timings", "reconciliation_corrections",
            "reconciliation_discrepancies", "reconciliation_runs", "review_log",
            "risk_policy", "schwab_api_calls", "trade_events", "watchlist_archive",
            "watchlist_close_track_flag_events", "watchlist_close_track_flags",
            "yfinance_calls")


def exposure(p: Probe):
    for t in EXPOSURE:
        n = p.conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        if n == 0:
            p.info_row("E-exposure", t, None, "empty", "no rows to probe")
            continue
        r = p.conn.execute(f"SELECT rowid, * FROM {t} LIMIT 1")
        names = [d[0] for d in r.description]
        vals = r.fetchone()
        row = dict(zip(names[1:], vals[1:], strict=True))
        rid = vals[0]
        # REPLACE of an identical row (explicit pk): accepted today?
        p.run("E-exposure", t, None, "REPLACE-same-row", ("info",), [],
              *Probe.ins(t, row, "INSERT OR REPLACE"),
              post=lambda c, t=t, rid=rid: "row still at rowid="
              f"{c.execute(f'SELECT count(*) FROM {t} WHERE rowid=?', (rid,)).fetchone()[0]}")
        pk = [r[1] for r in p.conn.execute(f"PRAGMA table_info('{t}')") if r[5]]
        if len(pk) == 1:
            nopk = dict(row)
            nopk.pop(pk[0])
            p.run("E-exposure", t, None, "REPLACE-uniquekey-pk-omitted", ("info",),
                  [], *Probe.ins(t, nopk, "INSERT OR REPLACE"),
                  post=lambda c, t=t, k=pk[0], v=row[pk[0]]: "old pk still present="
                  f"{c.execute(f'SELECT count(*) FROM {t} WHERE {k}=?', (v,)).fetchone()[0]}"
                  f"; new max pk={c.execute(f'SELECT max({k}) FROM {t}').fetchone()[0]}")
        p.run("E-exposure", t, None, "DELETE", ("info",), [],
              f"DELETE FROM {t} WHERE rowid=?", (rid,))
        p.run("E-exposure", t, None, "UPDATE-noop-rewrite", ("info",), [],
              f"UPDATE {t} SET rowid=rowid WHERE rowid=?", (rid,))


def step_timings_priced_cost(p: Probe):
    """The priced cost, measured on the ONE known ON CONFLICT writer: with a
    conflict-scoped no_replace barrier in place, the production statement on a
    present key ABORTS; the WHERE NOT EXISTS pre-filtered form is a no-op."""
    t = "pipeline_step_timings"
    r = p.row(t, "id = (SELECT min(id) FROM pipeline_step_timings)")
    barrier = (f"CREATE TRIGGER trg_pst_no_replace_PROBE BEFORE INSERT ON {t} "
               f"WHEN EXISTS (SELECT 1 FROM {t} WHERE (NEW.id != -1 AND id = NEW.id) "
               f"OR (run_id = NEW.run_id AND ordinal = NEW.ordinal)) "
               f"BEGIN SELECT RAISE(ABORT, 'PROBE pst no_replace'); END")
    prod = (f"INSERT INTO {t} (run_id, ordinal, step_name, started_ts, finished_ts, "
            f"duration_ms) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(run_id, ordinal) DO NOTHING")
    args = (r["run_id"], r["ordinal"], r["step_name"], r["started_ts"],
            r["finished_ts"], r["duration_ms"])
    p.run("E-priced-cost", t, None, "v40 production stmt on present key", ("ok",),
          [], prod, args)
    p.run("E-priced-cost", t, "PROBE", "with barrier: production stmt", ("info",),
          [barrier], prod, args)
    pre = (f"INSERT INTO {t} (run_id, ordinal, step_name, started_ts, finished_ts, "
           f"duration_ms) SELECT ?, ?, ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM {t} "
           f"WHERE run_id = ? AND ordinal = ?) ON CONFLICT(run_id, ordinal) DO NOTHING")
    p.run("E-priced-cost", t, "PROBE", "with barrier: pre-filtered stmt", ("ok",),
          [barrier], pre, args + (r["run_id"], r["ordinal"]))
    # THE PRICED COST REACHES `ON CONFLICT ... DO UPDATE` TOO: the production
    # daily_recommendations upsert (swing/data/repos/recommendations.py:18) on
    # a present key, with a conflict-scoped no_replace barrier in place.
    t3 = "daily_recommendations"
    d = p.row(t3, "id = (SELECT max(id) FROM daily_recommendations)")
    dr_barrier = (f"CREATE TRIGGER trg_dr_no_replace_PROBE BEFORE INSERT ON {t3} "
                  f"WHEN EXISTS (SELECT 1 FROM {t3} WHERE (NEW.id != -1 AND id = NEW.id) "
                  f"OR (action_session_date = NEW.action_session_date AND ticker = "
                  f"NEW.ticker AND recommendation = NEW.recommendation)) "
                  f"BEGIN SELECT RAISE(ABORT, 'PROBE dr no_replace'); END")
    ups = (f"INSERT INTO {t3} (evaluation_run_id, data_asof_date, action_session_date, "
           f"ticker, recommendation) VALUES (?, ?, ?, ?, ?) ON CONFLICT(action_session_date, "
           f"ticker, recommendation) DO UPDATE SET evaluation_run_id = "
           f"excluded.evaluation_run_id")
    uargs = (d["evaluation_run_id"], d["data_asof_date"], d["action_session_date"],
             d["ticker"], d["recommendation"])
    p.run("E-priced-cost", t3, None, "v40 production upsert on present key", ("ok",),
          [], ups, uargs)
    p.run("E-priced-cost", t3, "PROBE", "with barrier: production upsert", ("info",),
          [dr_barrier], ups, uargs)
    # THE FK-ACTION COST: a blanket no_update on a table whose parent FK is
    # ON DELETE SET NULL aborts the PARENT's production delete. Measured on
    # pattern_detection_events.chart_render_id, whose parent chart_renders is
    # pruned in production (swing/diagnostics/prune_chart_cache.py).
    t2 = "pattern_detection_events"
    cr = p.conn.execute(f"SELECT chart_render_id FROM {t2} WHERE chart_render_id "
                        "IS NOT NULL LIMIT 1").fetchone()[0]
    blanket = (f"CREATE TRIGGER trg_pde_no_update_PROBE BEFORE UPDATE ON {t2} "
               f"BEGIN SELECT RAISE(ABORT, 'PROBE pde no_update'); END")
    exempt = (f"CREATE TRIGGER trg_pde_no_update_PROBE BEFORE UPDATE ON {t2} "
              f"WHEN NOT COALESCE(NEW.chart_render_id IS NULL AND OLD.chart_render_id "
              f"IS NOT NULL AND NOT EXISTS (SELECT 1 FROM chart_renders WHERE id = "
              f"OLD.chart_render_id) AND NEW.detection_id IS OLD.detection_id, 0) "
              f"BEGIN SELECT RAISE(ABORT, 'PROBE pde no_update'); END")
    p.run("E-priced-cost", t2, None, "v40 chart_renders delete (SET NULL cascade)",
          ("ok",), [], "DELETE FROM chart_renders WHERE id = ?", (cr,))
    p.run("E-priced-cost", t2, "PROBE", "blanket no_update: chart_renders delete",
          ("info",), [blanket], "DELETE FROM chart_renders WHERE id = ?", (cr,))
    p.run("E-priced-cost", t2, "PROBE", "FK-null-exempt no_update: chart delete",
          ("ok",), [exempt], "DELETE FROM chart_renders WHERE id = ?", (cr,))


# --------------------------------------------------------------------------
# section G-0041: every 0041 guard (22-I T18; --post-migrate only)
# --------------------------------------------------------------------------
_SPEC_PATH = Path(__file__).resolve().parents[1] / "tests" / "data" / "_22i_guard_spec.py"


def load_spec():
    """The 22-I guard spec, loaded BY PATH (it imports nothing from swing)."""
    import importlib.util

    name = "_22i_guard_spec_for_probe"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SPEC_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod  # dataclass field-type resolution needs it registered
    spec.loader.exec_module(mod)
    return mod


# The row a partial-UNIQUE barrier's A2 copies must itself satisfy the partial
# predicate, or its copy collides with nothing.
_SPECIAL_ROW = {
    "risk_policy": "is_active = 1",
    "hypothesis_status_history": "effective_to IS NULL",
    "daily_management_records": "record_type = 'daily_snapshot' AND is_superseded = 0",
}


def _diff(v):
    """A value different from ``v`` (a BEFORE trigger fires before any type,
    NOT NULL, CHECK or FK check, so admissibility does not matter for an
    abort-expected probe)."""
    if v is None:
        return "x"
    if isinstance(v, bytes):
        return v + b"x"
    if isinstance(v, bool):
        return int(not v)
    if isinstance(v, int):
        return v + 1000000
    if isinstance(v, float):
        return v + 1.5
    return str(v) + "x"


def _w_seed(col: str, pk_val):
    """A NULL -> value write-once seed: the row's own id for a self/FK id
    column (it exists, so the setup statement's FK check passes), else a
    timestamp."""
    return pk_val if col.endswith("_id") else "2099-01-01T00:00:00.000"


def g0041(p: Probe):
    spec_mod = load_spec()
    sec = "G-0041"
    for table, s in spec_mod.SPEC.items():
        nr, nd = f"trg_{s.abbr}_no_replace", f"trg_{s.abbr}_no_delete"
        ut = s.update_trigger
        order = ", ".join(s.pk)
        first = p.row(table, f"1=1 ORDER BY {order} ASC LIMIT 1")
        if first is None:
            p.info_row(sec, table, None, "no-row", "no rows to probe")
            continue
        last = p.row(table, f"1=1 ORDER BY {order} DESC LIMIT 1")
        rows = [first] if [first[k] for k in s.pk] == [last[k] for k in s.pk] \
            else [first, last]
        # A2 -- REPLACE on each conflict key (the PK omitted), once per table.
        keys = list(s.conflict_keys)
        if not s.integer_pk:
            keys.insert(0, s.pk)
        for key in keys:
            r = dict(first)
            if s.integer_pk:
                r.pop(s.pk[0])
            p.run(sec, f"{table}[key]", nr, f"A2-REPLACE-{'+'.join(key)}",
                  ("fires", nr), [], *Probe.ins(table, r, "INSERT OR REPLACE"))
        if s.special_conflict:
            srow = p.row(table, f"{_SPECIAL_ROW[table]} ORDER BY {order} LIMIT 1")
            if srow is None:
                p.info_row(sec, f"{table}[partial]", nr, "A2-partial",
                          f"no row satisfies {_SPECIAL_ROW[table]}")
            else:
                srow.pop(s.pk[0])
                p.run(sec, f"{table}[partial]", nr, "A2-REPLACE-partial-key",
                      ("fires", nr), [], *Probe.ins(table, srow, "INSERT OR REPLACE"))
        for r in rows:
            where = " AND ".join(f"{k} = ?" for k in s.pk)
            wp = tuple(r[k] for k in s.pk)
            tag = f"{table}[{','.join(str(r[k]) for k in s.pk)}]"
            pkv = r[s.pk[0]]

            def upd(col, val, expect, pid, setup=(), *, _w=where, _wp=wp, _tag=tag,
                    _t=table, _ut=ut or f"trg_{s.abbr}_"):
                p.run(sec, _tag, _ut, pid, expect, list(setup),
                      f"UPDATE {_t} SET {col} = ? WHERE {_w}", (val, *_wp))

            fires = ("fires", ut) if ut else None
            not_ut = ("not", ut or f"trg_{s.abbr}_")
            # A4 explicit conflicting PK; A6 DELETE
            p.run(sec, tag, nr, "A4-explicit-pk", ("fires", nr), [],
                  *Probe.ins(table, dict(r)))
            p.run(sec, tag, nd, "A6-delete", ("fires", nd), [],
                  f"DELETE FROM {table} WHERE {where}", wp)
            for col in s.I:
                upd(col, _diff(r[col]), fires, f"I-{col}")
            for col in s.W:
                seed = _w_seed(col, pkv)
                if r[col] is None:
                    setup = [(f"UPDATE {table} SET {col} = ? WHERE {where}",
                              (seed, *wp))]
                    upd(col, _diff(seed), fires, f"W-{col}-value-to-other", setup)
                else:
                    upd(col, _diff(r[col]), fires, f"W-{col}-value-to-other")
            for col in s.D:  # risk_policy.is_active: 0 -> 1 refused
                setup = ([(f"UPDATE {table} SET {col} = 0 WHERE {where}", wp)]
                         if r[col] == 1 else [])
                upd(col, 1, fires, f"D-{col}-0-to-1", setup)
            for col in s.M:
                upd(col, _diff(r[col]), not_ut, f"M-{col}")
            if s.pk_trigger:  # B2 (CHARC Branch A): the (c) no-twin PK freeze
                for col in s.pk:
                    upd(col, _diff(r[col]), ("fires", s.pk_trigger), f"PK-{col}",
                        _ut=s.pk_trigger)
            completed = table == "review_log" and r["completed_date"] is not None
            for col in s.S:
                upd(col, _diff(r[col]), fires if completed else not_ut,
                    f"S-{col}-{'completed' if completed else 'pending'}")
            superseded = table == "daily_management_records" and r["is_superseded"] == 1
            for col in s.DATA:
                upd(col, _diff(r[col]), fires if superseded else not_ut,
                    f"DATA-{col}-{'superseded' if superseded else 'active'}")
            if table == "daily_management_records":
                if superseded:
                    upd("is_superseded", 0, fires, "STATE-is_superseded-1-to-0")
                    if r["superseded_by_record_id"] is not None:
                        upd("superseded_by_record_id", None, fires,
                            "STATE-pointer-value-to-NULL")
                else:
                    upd("superseded_by_record_id", pkv, fires,
                        "STATE-pointer-set-on-an-active-row")
            for f in s.F:
                if r[f.col] is None:
                    p.info_row(sec, tag, ut, f"F-{f.col}-parent-present",
                              "fk is NULL on this row")
                    continue
                frozen = table != "review_log" or completed
                upd(f.col, None, fires if frozen else not_ut,
                    f"F-{f.col}-to-NULL-parent-present")


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-copy", action="store_true")
    ap.add_argument("--copy")
    ap.add_argument("--live-ro", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--post-migrate", action="store_true",
                    help="22-I T18: the census on a copy migrated to v41 "
                         "(requires --copy): section G-0041 + the ruled "
                         "expectation corrections")
    a = ap.parse_args(argv)
    if a.post_migrate and not a.copy:
        print("REFUSED: --post-migrate requires --copy <migrated copy>",
              file=sys.stderr)
        return 2
    ts = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    if a.make_copy:
        SCRATCH.mkdir(parents=True, exist_ok=True)
        dst_path = SCRATCH / f"swing-v40-copy-{ts}.db"
        src = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
        dst = sqlite3.connect(str(dst_path))
        src.backup(dst)
        dst.close()
        src.close()
        print(dst_path)
        return 0
    out_path = Path(a.out) if a.out else SCRATCH / f"probe-output-{ts}.txt"
    with out_path.open("w", encoding="utf-8", newline="\n") as out:
        if a.live_ro:
            c = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
            out.write(f"#TARGET\tLIVE mode=ro\t{LIVE_DB}\n")
            catalogue(c, out)
            c.close()
            print(out_path)
            return 0
        copy = Path(a.copy).resolve()
        if copy == LIVE_DB.resolve():
            print("REFUSED: write probes never run against the live DB",
                  file=sys.stderr)
            return 2
        out.write(f"#TARGET\tCOPY\t{copy}\n")
        p = Probe(copy, out)
        p.post_migrate = bool(a.post_migrate)
        if p.post_migrate:
            out.write("#MODE\tpost-migrate (G-0041 + the ruled corrections)\n")
        catalogue(p.conn, out)
        out.write("section\ttable\ttrigger_under_test\tprobe\texpect\toutcome\tverdict\n")
        guard_triple(p)
        lve_update_guards(p)
        epoch(p)
        pc_citation_graph(p)
        pc_append_only_update(p)
        eia_insert_triggers(p)
        eia_no_update(p)
        identity_triggers(p)
        loi_validity_and_mint(p)
        exposure(p)
        step_timings_priced_cost(p)
        if p.post_migrate:
            g0041(p)
        out.write(f"#SUMMARY\tPASS={p.n_pass}\tFAIL={p.n_fail}\tINFO={p.n_info}\n")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
