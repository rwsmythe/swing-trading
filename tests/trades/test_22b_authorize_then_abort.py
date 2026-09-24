"""Arc 22-B Task 11 -- AUTHORIZE-THEN-ABORT closure over the attestation triggers.

The property: no row the service ADMITS is aborted by SQL -- the trigger
predicate set is a SUBSET of the service's. The instrument is a hand-written
map, CLOSURE-CHECKED against the stored ``target_version=40`` schema two ways:

* by NAME: every trigger on ``entry_intent_attestations``, and every trigger
  0040 creates on ANY table (the v40 trigger set minus the v39 set, so
  ``trades`` and ``latch_view_events`` are covered), is either an admission
  map entry or on ``SCHEMA_ONLY``; and no map entry is stale;
* by PREDICATE (R3-08): each map entry carries the manifest hash (the D51b
  normalization of ``scripts/schema_manifest.py``, IMPORTED, never retyped)
  of its object's stored SQL, taken from the ``target_version=40`` image when
  this test was written and pasted as a literal. A predicate ADDED to an
  existing trigger moves the hash, and the closure names the object -- so a
  new SQL refusal cannot land without this map being re-edited, together with
  its predicate id, its refusal code or derived-value proof, and its test.

Predicate ids come in TWO kinds (SS-7):

* ``REFUSAL`` -- maps to a ``preflight`` refusal code; a ONE-mutation fixture
  of the admitting trade-20 world, driven through ``preflight`` FIRST, yields
  that code (``test_each_refusal_predicate_yields_its_preflight_code_b22_160``);
* ``DERIVED_VALUE`` -- a field the service COMPUTES rather than admits on; a
  service-built row for EACH admitting path (b22_80 deployment, b22_90
  telemetry, b22_91 structural) inserts through the REAL triggers, and the raw
  one-mutation SQL test (Task 4) shows the trigger bites.

``SERVICE_ONLY`` holds the two derivations SQL never re-performs;
``SQL_ONLY`` is empty among admission predicates.

FORWARD RULE (R0.I): every image pins ``target_version=40``.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

import swing.trades.entry_intent_assignment as svc
from swing.data.db import open_connection, run_migrations
from tests._22b_fixtures import AMN_ORDER_ID, envelope, insert_row, record_envelope_readings
from tests.trades.test_22b_assignment_service import (
    BREACH_0806,
    CITE,
    REASON,
    _other_fill,
    _speaking,
    _structural,
    _world,
)

EIA = "entry_intent_attestations"
REFUSAL = "REFUSAL"
DERIVED_VALUE = "DERIVED_VALUE"


@dataclass(frozen=True)
class Predicate:
    """One conjunct (or CHECK bind) of an admission object, and its twin.

    ``code`` is the ``preflight`` refusal code of a REFUSAL predicate (None for
    a DERIVED_VALUE one). ``sql_tests`` are the raw one-mutation tests that
    show the SQL half bites (Task 4; empty where none exists -- reported).
    ``note`` says how the service reaches it."""

    kind: str
    code: str | None
    sql_tests: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class AdmissionEntry:
    sha256: str
    predicates: dict[str, Predicate]


def _p(kind: str, code: str | None, sql_tests: tuple[str, ...], note: str) -> Predicate:
    return Predicate(kind, code, sql_tests, note)


# ---------------------------------------------------------------------------
# THE MAP. Hashes: `read_manifest` over `run_migrations(c, target_version=40)`,
# taken at Task 11 (after RULING G1b moved trg_eia_trade_binding and
# trg_eia_tier2, and RULING G1d's NULL-id close moved trg_eia_trade_binding
# again: manifest e7125868... -> 636c8a6c...).
# ---------------------------------------------------------------------------
ADMISSION_MAP: dict[tuple[str, str], AdmissionEntry] = {
    ("trigger", "trg_eia_trade_binding"): AdmissionEntry(
        "636c8a6c52e66dfe65ba8bd372becf5508311a191f3866738e94ccaeac14d1d5", {
            "trade_exists": _p(
                REFUSAL, "no_trade", (),
                "_check_trade: the trade row is read first"),
            "trade_entry_intent_is_null": _p(
                REFUSAL, "already_set", ("b22_71",),
                "_check_trade: no relabel path"),
            "trade_entry_date_is_the_live_entry_date": _p(
                DERIVED_VALUE, None, (),
                "trade_entry_date is copied from the trade row read in _check_trade"),
            "an_authoritative_entry_fill_exists": _p(
                REFUSAL, "no_entry_fill", ("b22_52",),
                "_check_trade: get_authoritative_entry_fill is None"),
            "entry_fill_ids_are_the_authoritative_fill": _p(
                DERIVED_VALUE, None, ("b22_52",),
                "entry_fill_id and entry_fill_id_at_assignment are both "
                "get_authoritative_entry_fill's id (the trigger's own ORDER BY)"),
            "order_id_is_the_stored_canonical_reading": _p(
                DERIVED_VALUE, None, ("b22_210", "b22_211"),
                "RULING G1b: the order id IS stored_identity of the fill's "
                "CURRENT document, after ensure_entry_fill_identities"),
            "null_id_absent_or_canonical_reading": _p(
                REFUSAL, "envelope_refused", ("b22_213", "b22_216"),
                "RULING G1d item 3: the step-5 refuse-first -- a refused reading "
                "refuses envelope_refused (b22_208); an envelope with NO reading "
                "after ensure raises EnvelopeReadingMissingError, an invariant, "
                "never a refusal (b22_212); passing twins b22_214, b22_215, "
                "b22_193"),
        }),
    ("trigger", "trg_eia_cited_fields"): AdmissionEntry(
        "477ea37cb7ab149eb7cbd9a4d76a1804ef5254bf7951d7ec58e90ba61b754cfc", {
            "cited_members_are_text_in_the_allowlist": _p(
                REFUSAL, "not_citable", ("b22_57",),
                "_check_citation: CITABLE_FIELDS membership"),
            "cited_members_are_distinct": _p(
                REFUSAL, "not_citable", (),
                "_check_citation: a cited field named twice"),
            "a_descriptive_field_is_cited": _p(
                REFUSAL, "no_descriptive_field", ("b22_58",),
                "_check_citation: DESCRIPTIVE_FIELDS (F2 S4)"),
            "snapshot_keys_are_the_cited_set": _p(
                DERIVED_VALUE, None, (),
                "the snapshot is built from the cited list itself"),
            "snapshot_values_are_the_live_text": _p(
                DERIVED_VALUE, None, ("b22_59",),
                "the snapshot values are the trade row's own columns"),
            "citation_and_snapshot_are_valid_json": _p(
                DERIVED_VALUE, None, ("b22_48",),
                "json.dumps of a list / a dict"),
        }),
    ("trigger", "trg_eia_audit_trail"): AdmissionEntry(
        "cf79e7b8420adb31f52ae95b21bd973387c0e820a926befe9e27058d2a5feae6", {
            "no_reconciliation_correction_touches_a_cited_field": _p(
                REFUSAL, "cited_field_corrected", ("b22_60", "b22_61"),
                "_check_audit_trail over reconciliation_corrections: field_name "
                "and both JSON envelopes' keys (a superset of the trigger's "
                "field_name match)"),
            "no_provenance_correction_names_a_cited_field": _p(
                REFUSAL, "cited_field_corrected", ("b22_62",),
                "_check_audit_trail over provenance_corrections"),
        }),
    ("trigger", "trg_eia_outcome"): AdmissionEntry(
        "dd09b941ea645822dd15102b335bae9db7e2efb9ec35fd2c936e6a882758a9c5", {
            "outcome_is_the_earliest_non_entry_fill": _p(
                DERIVED_VALUE, None, ("b22_63",),
                "_check_outcome runs the trigger's own MIN(fill_datetime)"),
        }),
    ("trigger", "trg_eia_tier2"): AdmissionEntry(
        "15ac12be5a0de2f4d2e90bdeadfa5b39c46c820b900e38e0444a464aeb3da500", {
            "no_link_names_the_order": _p(
                DERIVED_VALUE, None, ("b22_64",),
                "the tier is DETECTED: a link for the order routes structural "
                "(the b22_91 path), so no tier-2 row is built for it"),
            "no_intent_names_the_order": _p(
                REFUSAL, "unlinked_intent", ("b22_65",),
                "_detect_tier: an order-naming intent with no link (N5 (b))"),
            "no_ticker_record_without_an_order_id": _p(
                REFUSAL, "unprovable", ("b22_66",),
                "_detect_tier: E9, fail-closed"),
            "placement_source_pairing": _p(
                DERIVED_VALUE, None, (),
                "a fallback placement IS the trade's entry_date by construction"),
            "no_pre_row_offered_the_order": _p(
                REFUSAL, "instrument_offered", ("b22_67",),
                "_detect_tier over _pre_rows: the trigger's own PRE predicate"),
            "telemetry_leg_evidence_is_exactly_the_pre_set": _p(
                DERIVED_VALUE, None, ("b22_68", "b22_79"),
                "the evidence IS the PRE rows as read"),
            "deployment_leg_has_no_pre_row_and_precedes_0803": _p(
                REFUSAL, "instrument_existed", ("b22_69", "b22_55"),
                "_detect_tier: no PRE row and placement >= 2026-08-03 refuses"),
            "deployment_leg_evidence_by_value": _p(
                DERIVED_VALUE, None, ("b22_79",),
                "the evidence dict is built from the placement and the constant"),
        }),
    ("trigger", "trg_eia_structural"): AdmissionEntry(
        "a9018b3b6a770a2513cabcf2c6d3179b970429a290eb1b615ed91012e8583cc6", {
            "the_cited_link_is_the_fills_order": _p(
                DERIVED_VALUE, None, ("b22_52",),
                "the link is find_accepted_latch_order(order id) itself"),
            "the_probe_binds_to_the_row_by_value": _p(
                DERIVED_VALUE, None, ("b22_79",),
                "the probe JSON is built from the same verdict and link"),
        }),
    ("table", EIA): AdmissionEntry(
        "ae5d4b93377e94eae2fc9ef1f2589cf4a0a8df1621df83e60134847bae6d95d2", {
            "death_strictly_before_the_fill_session": _p(
                REFUSAL, "death_not_before_fill", ("b22_53", "b22_54"),
                "_structural: session < entry on the probe's verdict"),
            "the_terminal_rung_is_a_death_rung": _p(
                REFUSAL, "not_a_death_rung", (),
                "_structural: DEATH_RUNGS membership"),
            "the_deployment_bound": _p(
                REFUSAL, "instrument_existed", ("b22_55", "b22_56"),
                "_detect_tier: leg 2 only below 2026-08-03"),
            "the_outcome_after_the_record": _p(
                REFUSAL, "outcome_not_after_record", ("b22_49",),
                "_check_outcome (CF-R3-1)"),
            "reason_is_not_blank": _p(
                REFUSAL, "blank_reason", ("b22_52",),
                "_check_citation (R3-07); Python strip() refuses a superset of "
                "SQL trim()"),
            "an_envelope_placement_is_a_date": _p(
                REFUSAL, "unprovable", ("b22_77",),
                "_detect_tier: _is_iso_date on the envelope's entry_date"),
            "copied_date_shapes": _p(
                REFUSAL, "source_date_malformed", ("b22_77", "b22_75"),
                "RULING G4: trade_entry_date, outcome_known_at and a fallback "
                "placement are COPIED from trades.entry_date / "
                "fills.fill_datetime, which carry no shape CHECK; _check_trade "
                "refuses a malformed source value as source_date_malformed at "
                "step 1, before any lexical comparison and before __post_init__ "
                "(b22_218-221)"),
            "json_shapes": _p(
                DERIVED_VALUE, None, ("b22_48",),
                "every JSON column is json.dumps of a list / a dict"),
            "entry_fill_id_pairing": _p(
                DERIVED_VALUE, None, (),
                "both ids are the same authoritative fill id"),
            "the_paired_tier_nulls": _p(
                DERIVED_VALUE, None, ("b22_52",),
                "preflight fills exactly one tier's columns"),
            "enumerated_values": _p(
                DERIVED_VALUE, None, ("b22_75",),
                "assigned_value, admission_tier, the source and the leg are "
                "service constants"),
            "corrections_touching_cited_fields_is_zero": _p(
                DERIVED_VALUE, None, (),
                "written 0 only after _check_audit_trail found none"),
            "foreign_keys": _p(
                DERIVED_VALUE, None, (),
                "trade_id, entry_fill_id and cited_latch_link_id are rows the "
                "service read in the same transaction"),
        }),
}

SERVICE_ONLY: dict[str, str] = {
    "death_before_fill_derivation": (
        "the death is DERIVED by mandate_alive_at (Python); SQL binds only the "
        "recorded rung/session shape and the probe by value -- never a second "
        "comparison (gotcha #31)"),
    "placement_session_derivation": (
        "persist-canonical: SQL never reads the envelope; provenance is "
        "replay-verified in Python by drift (vi)"),
}
SQL_ONLY: frozenset[str] = frozenset()

SCHEMA_ONLY: dict[str, str] = {
    "trg_eia_no_update": "append-only barrier, no service operation to mirror; "
                         "b22_72, and its one FK-nulling permit b22_191",
    "trg_eia_no_delete": "append-only barrier; b22_73",
    "trg_eia_no_replace": "append-only barrier; b22_74",
    "trg_trades_entry_intent_attested_terminal": "N4 barrier; b22_34-37",
    "trg_trades_entry_intent_unattested_update": "CHARC-S3.2 twin; b22_202, b22_203, b22_205",
    "trg_trades_entry_intent_unattested_insert": "CHARC-S3.2 twin; b22_204",
    "trg_lve_actionable_ever_viewed_monotonic": "leg-1 evidence belt; b22_38-40",
    "trg_lve_no_delete": "leg-1 evidence belt; b22_41",
    "trg_lve_no_replace": "leg-1 evidence belt; b22_42, b22_43",
    "trg_lve_view_window_immutable": "leg-1 evidence belt; b22_197-199",
}


# ---------------------------------------------------------------------------
# The closure
# ---------------------------------------------------------------------------
def _manifest_module():
    """scripts/schema_manifest.py, loaded by the tests/data idiom (its OWN
    normalization; never retyped here)."""
    mod = sys.modules.get("schema_manifest")
    if mod is None:
        script = Path(__file__).resolve().parents[2] / "scripts" / "schema_manifest.py"
        spec = importlib.util.spec_from_file_location("schema_manifest", script)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules["schema_manifest"] = mod
        spec.loader.exec_module(mod)
    return mod


def _image(root: Path, version: int) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    c = open_connection(root / "swing.db")
    try:
        run_migrations(c, target_version=version, backup_dir=root / "bak")
    finally:
        c.close()
    return root / "swing.db"


def _trigger_names(path: Path) -> dict[str, str]:
    c = sqlite3.connect(path)
    try:
        return dict(c.execute(
            "SELECT name, tbl_name FROM sqlite_master WHERE type = 'trigger'"))
    finally:
        c.close()


@pytest.fixture(scope="module")
def images(tmp_path_factory) -> tuple[Path, set[str]]:
    root = tmp_path_factory.mktemp("att_closure")
    v40 = _image(root / "v40", 40)
    v39_names = set(_trigger_names(_image(root / "v39", 39)))
    return v40, v39_names


def _copy(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    s, d = sqlite3.connect(src), sqlite3.connect(dst_dir / "swing.db")
    try:
        s.backup(d)
    finally:
        s.close()
        d.close()
    return dst_dir / "swing.db"


def closure_problems(path: Path, v39_trigger_names: set[str]) -> list[str]:
    """Every way the stored schema escapes the map: an unmapped trigger on the
    table, an unmapped trigger 0040 created, a stale entry, a moved hash."""
    problems: list[str] = []
    triggers = _trigger_names(path)
    mapped = {name for (kind, name) in ADMISSION_MAP if kind == "trigger"}
    known = mapped | set(SCHEMA_ONLY)
    for name, table in sorted(triggers.items()):
        if table == EIA and name not in known:
            problems.append(f"unmapped trigger on {EIA}: {name}")
        elif name not in v39_trigger_names and name not in known:
            problems.append(f"unmapped trigger created by 0040 on {table}: {name}")
    for name in sorted(known - set(triggers)):
        problems.append(f"stale entry: {name} is not in the stored schema")
    c = sqlite3.connect(path)
    try:
        stored = {(r.type, r.name): r.sql_sha256
                  for r in _manifest_module().read_manifest(c)}
    finally:
        c.close()
    for key, entry in ADMISSION_MAP.items():
        if key not in stored:
            problems.append(f"stale entry: {key} is not in the stored schema")
        elif stored[key] != entry.sha256:
            problems.append(f"hash moved: {key[0]} {key[1]} stored "
                            f"{stored[key][:12]} != map {entry.sha256[:12]} "
                            "-- a predicate changed; re-edit the map")
    return problems


def test_every_admission_trigger_predicate_has_a_reached_service_check_b22_160(
        images) -> None:
    v40, v39_names = images
    assert closure_problems(v40, v39_names) == []
    # The shape of the map itself.
    assert set(SCHEMA_ONLY).isdisjoint(name for _, name in ADMISSION_MAP)
    assert not SQL_ONLY
    assert set(SERVICE_ONLY) == {"death_before_fill_derivation",
                                 "placement_session_derivation"}
    assert SERVICE_ONLY["placement_session_derivation"] == (
        "persist-canonical: SQL never reads the envelope; provenance is "
        "replay-verified in Python by drift (vi)")
    for entry in ADMISSION_MAP.values():
        for pid, pred in entry.predicates.items():
            assert pred.kind in (REFUSAL, DERIVED_VALUE), pid
            assert (pred.code is not None) == (pred.kind == REFUSAL), pid
    binding = ADMISSION_MAP[("trigger", "trg_eia_trade_binding")].predicates
    assert binding["null_id_absent_or_canonical_reading"].code == "envelope_refused"
    # Every REFUSAL predicate has its one-mutation preflight fixture (below).
    refusals = {pid for e in ADMISSION_MAP.values()
                for pid, p in e.predicates.items() if p.kind == REFUSAL}
    assert refusals == set(REFUSAL_FIXTURES)
    # Every cited SQL test exists under tests/ (a cited id is a real test).
    text = "\n".join(p.read_text(encoding="utf-8") for p in
                     (Path(__file__).resolve().parents[1]).rglob("test_*.py"))
    for entry in ADMISSION_MAP.values():
        for pid, pred in entry.predicates.items():
            for test_id in pred.sql_tests:
                assert f"_{test_id}(" in text, (pid, test_id)


# ---- discriminators (a) and (b): the closure FAILS when the schema moves ----
def test_the_name_closure_fails_on_an_unmapped_trigger_b22_160(images, tmp_path) -> None:
    v40, v39_names = images
    cases = {
        "on_the_table": (
            "CREATE TRIGGER trg_eia_new_rule BEFORE INSERT ON "
            "entry_intent_attestations FOR EACH ROW BEGIN SELECT 1; END",
            f"unmapped trigger on {EIA}: trg_eia_new_rule"),
        "on_trades_by_0040": (
            "CREATE TRIGGER trg_trades_new_rule BEFORE UPDATE ON trades "
            "FOR EACH ROW BEGIN SELECT 1; END",
            "unmapped trigger created by 0040 on trades: trg_trades_new_rule"),
    }
    for label, (ddl, expected) in cases.items():
        path = _copy(v40, tmp_path / label)
        assert closure_problems(path, v39_names) == []  # the unmutated copy
        c = sqlite3.connect(path)
        try:
            c.execute(ddl)
            c.commit()
        finally:
            c.close()
        assert closure_problems(path, v39_names) == [expected], label


def test_the_hash_closure_fails_on_a_predicate_added_to_an_existing_trigger_b22_160(
        images, tmp_path) -> None:
    """R3-08: a name-keyed map stays green when a predicate is ADDED; the hash
    does not. Proven on a copy by rewriting one trigger's body."""
    v40, v39_names = images
    path = _copy(v40, tmp_path / "rewritten")
    c = sqlite3.connect(path)
    try:
        sql = c.execute("SELECT sql FROM sqlite_master WHERE type = 'trigger' "
                        "AND name = 'trg_eia_outcome'").fetchone()[0]
        anchor = "WHEN NOT COALESCE("
        assert sql.count(anchor) == 1
        c.execute("DROP TRIGGER trg_eia_outcome")
        c.execute(sql.replace(anchor, anchor + "NEW.reason <> 'x' AND "))
        c.commit()
        names = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'")}
    finally:
        c.close()
    assert "trg_eia_outcome" in names  # the NAME closure alone stays green
    problems = closure_problems(path, v39_names)
    assert len(problems) == 1 and problems[0].startswith(
        "hash moved: trigger trg_eia_outcome"), problems


# ---------------------------------------------------------------------------
# (c) REFUSAL: each predicate's ONE-mutation fixture yields its code at preflight
# ---------------------------------------------------------------------------
def _plant_pc_on_notes(c, tmp_path) -> None:
    """b22_101's schema-unreachable provenance correction (P2-a), planted raw."""
    from tests._tier2_world_22a2 import base_last_word_payload

    prov = copy.deepcopy(base_last_word_payload(tmp_path))
    c.execute("PRAGMA foreign_keys=OFF")
    c.execute("DROP TRIGGER trg_provenance_corrections_citation_graph")
    c.execute("PRAGMA ignore_check_constraints=ON")
    prov.update(provenance_correction_id=None, trade_id=20, entry_fill_id=41,
                entry_fill_id_at_correction=41,
                corrected_fields_json=json.dumps(
                    ["trades.hypothesis_label", "trades.notes"]))
    insert_row(c, "provenance_corrections", prov)
    c.execute("PRAGMA ignore_check_constraints=OFF")
    c.commit()
    c.execute("PRAGMA foreign_keys=ON")


def _unlinked_intent(c) -> None:
    """b22_95: an intent naming the order, its minting trigger dropped."""
    from tests._latch_link_fixtures_22a import accept_order
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    for (name,) in c.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND "
            "tbl_name='latch_order_intents' AND sql LIKE "
            "'%INSERT INTO latch_order_mandate_links%'").fetchall():
        c.execute(f"DROP TRIGGER {name}")
    accept_order(c, seed_link_fire(c), actual_broker_order_id=AMN_ORDER_ID)


def _amn_ticker_link(c) -> None:
    """b22_66: a recorded AMN order (a minted link) at or before the entry."""
    from tests._latch_link_fixtures_22a import insert_intent, place_row, validity_row
    from tests._latch_link_fixtures_22a import seed_fire as seed_link_fire

    cand = seed_link_fire(c, run_id=500, ticker="AMN", action_session_date="2026-08-03")
    amn = {"run_id": 500, "ticker": "AMN", "detection_date": "2026-08-03"}
    place_id = insert_intent(c, place_row(cand, idempotency_key="amn-place", **amn))
    insert_intent(c, validity_row(cand, place_id, key="amn-validity",
                                  actual_broker_order_id="999", **amn))


def _rc_on_notes(c) -> None:
    from tests.data.test_migration_0040_attestations import _plant_rc

    _plant_rc(c, field_name="notes", pre='{"notes": "a"}', applied='{"notes": "b"}')


def _base(tmp_path, name, **kw):
    c, cfg, _ = _world(tmp_path, name, **kw)
    return c, cfg


def _offered(tmp_path, name):
    c, cfg = _base(tmp_path, name, env=envelope(entry_date="2026-08-06"))
    _speaking(c, first="2026-08-05T09:00:00", ever=1)
    return c, cfg


def _with(setup):
    def build(tmp_path, name):
        c, cfg = _base(tmp_path, name, **({"env": None} if setup is _amn_ticker_link
                                          else {}))
        if setup is _plant_pc_on_notes:
            setup(c, tmp_path)
        else:
            setup(c)
        c.commit()
        return c, cfg
    return build


def _structural_case(**kw):
    def build(tmp_path, name):
        c, cfg, _, _ = _structural(tmp_path, name, **kw)
        return c, cfg
    return build


def _delete_entry_fill(tmp_path, name):
    c, cfg = _base(tmp_path, name)
    c.execute("DELETE FROM fills WHERE fill_id = 41")
    c.commit()
    return c, cfg


# pid -> (builder(tmp_path, name) -> (conn, cfg), preflight overrides, code)
REFUSAL_FIXTURES = {
    "trade_exists": (lambda t, n: _base(t, n), {"trade_id": 999}, "no_trade"),
    "trade_entry_intent_is_null": (
        lambda t, n: _base(t, n, entry_intent="standard"), {}, "already_set"),
    "an_authoritative_entry_fill_exists": (_delete_entry_fill, {}, "no_entry_fill"),
    "null_id_absent_or_canonical_reading": (
        lambda t, n: _base(t, n, env=envelope(schwab_order_id=" 1007427919619 ")),
        {}, "envelope_refused"),
    "cited_members_are_text_in_the_allowlist": (
        lambda t, n: _base(t, n), {"cite": ["notes", "pre_trade_locked_at"]},
        "not_citable"),
    "cited_members_are_distinct": (
        lambda t, n: _base(t, n), {"cite": ["notes", "notes"]}, "not_citable"),
    "a_descriptive_field_is_cited": (
        lambda t, n: _base(t, n), {"cite": ["emotional_state_pre_trade"]},
        "no_descriptive_field"),
    "no_reconciliation_correction_touches_a_cited_field": (
        _with(_rc_on_notes), {}, "cited_field_corrected"),
    "no_provenance_correction_names_a_cited_field": (
        _with(_plant_pc_on_notes), {}, "cited_field_corrected"),
    "no_intent_names_the_order": (_with(_unlinked_intent), {}, "unlinked_intent"),
    "no_ticker_record_without_an_order_id": (
        _with(_amn_ticker_link), {}, "unprovable"),
    "no_pre_row_offered_the_order": (_offered, {}, "instrument_offered"),
    "deployment_leg_has_no_pre_row_and_precedes_0803": (
        lambda t, n: _base(t, n, row5=False, env=envelope(entry_date="2026-08-03")),
        {}, "instrument_existed"),
    "death_strictly_before_the_fill_session": (
        _structural_case(horizon=4), {}, "death_not_before_fill"),
    "the_terminal_rung_is_a_death_rung": (
        _structural_case(setup=_other_fill), {}, "not_a_death_rung"),
    "the_deployment_bound": (
        lambda t, n: _base(t, n, row5=False, env=envelope(entry_date="2026-08-05")),
        {}, "instrument_existed"),
    "the_outcome_after_the_record": (
        lambda t, n: _base(t, n, outcome_dt="2026-08-07T16:00:00"), {},
        "outcome_not_after_record"),
    "reason_is_not_blank": (lambda t, n: _base(t, n), {"reason": "  "}, "blank_reason"),
    "an_envelope_placement_is_a_date": (
        lambda t, n: _base(t, n, env=envelope(entry_date="2026-8-01")), {},
        "unprovable"),
    "copied_date_shapes": (
        lambda t, n: _base(t, n, entry_date="2026-8-07"), {},
        "source_date_malformed"),
}


def _preflight(c, cfg, **over):
    """``preflight`` after the authority's readings exist (``assign`` runs
    ``ensure`` first inside its transaction; preflight itself reads only)."""
    record_envelope_readings(c)
    c.commit()
    kwargs = {"trade_id": 20, "cite": list(CITE), "reason": REASON, **over}
    return svc.preflight(c, cfg, **kwargs)


@pytest.mark.parametrize("pid", sorted(REFUSAL_FIXTURES))
def test_each_refusal_predicate_yields_its_preflight_code_b22_160(
        tmp_path: Path, pid: str) -> None:
    build, over, code = REFUSAL_FIXTURES[pid]
    [pred] = [e.predicates[pid] for e in ADMISSION_MAP.values() if pid in e.predicates]
    assert pred.code == code
    c, cfg = build(tmp_path, pid)
    try:
        r = _preflight(c, cfg, **over)
    finally:
        c.close()
    assert (r.admitted, r.refusal_code) == (False, code), r.message
    assert r.attestation is None


# ---------------------------------------------------------------------------
# (c) DERIVED_VALUE: each admitting path's service-built row passes the REAL
# triggers (b22_80 deployment, b22_90 telemetry, b22_91 structural)
# ---------------------------------------------------------------------------
def _admit_deployment(tmp_path):
    c, cfg, path = _world(tmp_path, "b80")
    return c, cfg, path


def _admit_telemetry(tmp_path):
    c, cfg, path = _world(tmp_path, "b90", env=envelope(entry_date="2026-08-06"))
    _speaking(c, first="2026-08-05T09:00:00", ever=0)
    return c, cfg, path


def _admit_structural(tmp_path):
    c, cfg, path, _ = _structural(tmp_path, "b91", closes=BREACH_0806)
    return c, cfg, path


@pytest.mark.parametrize("path_name,build,tier,leg", [
    ("b22_80", _admit_deployment, "contemporaneous_record", "deployment"),
    ("b22_90", _admit_telemetry, "contemporaneous_record", "telemetry"),
    ("b22_91", _admit_structural, "structural", None),
])
def test_each_admitting_paths_service_built_row_passes_the_real_triggers_b22_160(
        tmp_path: Path, path_name: str, build, tier: str, leg: str | None) -> None:
    c, cfg, path = build(tmp_path)
    try:
        names = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = ?",
            (EIA,))}
        assert {n for (k, n) in ADMISSION_MAP if k == "trigger"} <= names
        r = svc.assign(c, cfg, trade_id=20, cite=list(CITE), reason=REASON,
                       applied_by="operator")
    finally:
        c.close()
    assert r.admitted, (path_name, r.message)
    assert (r.tier, r.admitted_leg) == (tier, leg)
    fresh = sqlite3.connect(path)
    try:
        assert fresh.execute(f"SELECT COUNT(*) FROM {EIA} WHERE trade_id = 20 "
                             "AND attestation_id = ?", (r.attestation_id,)
                             ).fetchone() == (1,)
    finally:
        fresh.close()


@pytest.mark.parametrize("case", ["outcome_datetime_with_a_space",
                                  "open_trade_entry_date_unpadded"])
def test_a_copied_value_of_the_wrong_shape_never_reaches_sql_b22_160(
        tmp_path: Path, case: str) -> None:
    """``copied_date_shapes``: trades.entry_date and fills.fill_datetime carry
    no shape CHECK. RULING G4 (CHARC 2026-09-24): the service refuses a
    malformed copied source value with the typed code
    ``source_date_malformed`` at preflight step 1 -- never a raise from
    ``__post_init__``, never an ``IntegrityError``, nothing written."""
    kw = ({"outcome_dt": "2026-08-11 16:00:00"} if case.startswith("outcome")
          else {"entry_date": "2026-8-07", "with_outcome": False})
    c, cfg, path = _world(tmp_path, case, **kw)
    try:
        try:
            r = svc.assign(c, cfg, trade_id=20, cite=list(CITE), reason=REASON,
                           applied_by="operator")
        except sqlite3.IntegrityError as exc:  # pragma: no cover - the failure
            pytest.fail(f"SQL aborted a row the service authorized: {exc}")
        assert (r.admitted, r.refusal_code) == (False, "source_date_malformed"), (
            r.refusal_code, r.message)
        assert not c.in_transaction
    finally:
        c.close()
    fresh = sqlite3.connect(path)
    try:
        assert fresh.execute(f"SELECT COUNT(*) FROM {EIA}").fetchone() == (0,)
    finally:
        fresh.close()
