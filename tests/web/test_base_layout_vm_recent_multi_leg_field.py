"""Phase 12.5 #1 Task T-1.8 — base-layout VM retrofit regression for
``recent_multi_leg_auto_correction_count``.

Mirrors the Phase 10 Sub-bundle A T-A.7 + Sub-bundle E T-E.3 cross-bundle
pin coverage pattern (see
``tests/web/test_view_models/test_base_layout_vm_coverage.py``) — every VM
whose template extends ``base.html.j2`` MUST carry
``recent_multi_leg_auto_correction_count`` so the T-1.9 banner block can
read ``{{ vm.recent_multi_leg_auto_correction_count }}`` without
``UndefinedError`` (CLAUDE.md "base.html.j2 is shared" gotcha).

**Codex R1 Major #3 fix / F23 LOCK (TEMPLATE-MOUNT scope):** the
retrofit is enumerated by ``{% extends "base.html.j2" %}`` and NOT by
field-presence on ``unresolved_material_discrepancies_count``. The
``AccountSnapshotFormVM`` case is the canonical reason — it inherits the
banner field via ``BaseLayoutVM`` rather than declaring it explicitly,
so a field-presence-only check would silently miss it. The
auxiliary FIELD-PRESENCE test (``test_every_vm_with_unresolved_material
_field_also_has_recent_multi_leg_field``) is defense-in-depth complement.
"""
from __future__ import annotations

import dataclasses
import importlib
import pkgutil
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

import pytest

from swing.web.view_models import metrics as metrics_vm_pkg
from swing.web.view_models.metrics.shared import BaseLayoutVM

_NEW_FIELD: str = "recent_multi_leg_auto_correction_count"
_EXISTING_BANNER_FIELD: str = "unresolved_material_discrepancies_count"


# ---------------------------------------------------------------------------
# 1. BaseLayoutVM field + validation
# ---------------------------------------------------------------------------


def test_base_layout_vm_has_recent_multi_leg_field():
    """``BaseLayoutVM`` declares ``recent_multi_leg_auto_correction_count``
    with a default of 0."""
    field_names = {f.name for f in dataclasses.fields(BaseLayoutVM)}
    assert _NEW_FIELD in field_names, (
        f"BaseLayoutVM missing required field: {_NEW_FIELD}"
    )
    vm = BaseLayoutVM(session_date="2026-05-17")
    assert vm.recent_multi_leg_auto_correction_count == 0


def test_base_layout_vm_rejects_negative_recent_multi_leg_count():
    """Negative counts MUST raise ValueError (mirrors the existing
    ``unresolved_material_discrepancies_count`` validation pattern)."""
    with pytest.raises(ValueError) as exc:
        BaseLayoutVM(
            session_date="2026-05-17",
            recent_multi_leg_auto_correction_count=-1,
        )
    assert "recent_multi_leg_auto_correction_count" in str(exc.value)


def test_base_layout_vm_accepts_positive_recent_multi_leg_count():
    """Sanity check: a non-zero positive count is accepted."""
    vm = BaseLayoutVM(
        session_date="2026-05-17",
        recent_multi_leg_auto_correction_count=3,
    )
    assert vm.recent_multi_leg_auto_correction_count == 3


# ---------------------------------------------------------------------------
# 2. TEMPLATE-MOUNT introspection (F23 LOCK — the binding contract)
# ---------------------------------------------------------------------------


_TEMPLATES_DIR = (
    Path(__file__).resolve().parents[2]
    / "swing" / "web" / "templates"
)
_VIEW_MODELS_DIR = (
    Path(__file__).resolve().parents[2]
    / "swing" / "web" / "view_models"
)
_ROUTES_DIR = (
    Path(__file__).resolve().parents[2]
    / "swing" / "web" / "routes"
)


def _templates_extending_base() -> list[Path]:
    """Glob every ``.html.j2`` template under
    ``swing/web/templates/`` whose source contains
    ``{% extends "base.html.j2" %}``.
    """
    found: list[Path] = []
    for path in _TEMPLATES_DIR.rglob("*.html.j2"):
        src = path.read_text(encoding="utf-8")
        if '{% extends "base.html.j2" %}' in src:
            found.append(path)
    return found


# Pattern that matches `vm = SomeVM(...)` OR `SomeVM(` import + use.
_VM_INSTANTIATION_RX = re.compile(
    r"\b([A-Z][A-Za-z0-9_]*VM)\s*\(",
)


def _enumerate_all_dataclass_vms() -> list[type]:
    """Walk every module under ``swing/web/view_models/`` (including
    ``metrics/``) and return every ``@dataclass``-decorated class whose
    name ends with ``VM`` — i.e., a candidate page or sub VM.
    """
    import swing.web.view_models as vm_pkg

    found: list[type] = []
    # Walk top-level + subpackages (just `metrics` for now).
    for module_info in pkgutil.walk_packages(
        vm_pkg.__path__, prefix=vm_pkg.__name__ + ".",
    ):
        try:
            mod = importlib.import_module(module_info.name)
        except Exception:
            continue
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if not isinstance(attr, type):
                continue
            if not dataclasses.is_dataclass(attr):
                continue
            if not attr_name.endswith("VM"):
                continue
            # Avoid duplicates from re-import in different modules.
            if attr in found:
                continue
            found.append(attr)
    return found


def _vm_classes_by_name() -> dict[str, type]:
    out: dict[str, type] = {}
    for cls in _enumerate_all_dataclass_vms():
        # Keep the first occurrence — re-exports point at the same type.
        out.setdefault(cls.__name__, cls)
    return out


def _vm_class_names_referenced_by_route_handlers_for_template(
    template_name: str,
) -> set[str]:
    """For a given template filename, grep route handlers + VM modules
    for ``TemplateResponse(..., "template_name", ...)`` and ``"templ
    ate_name"`` literal anchors, then extract the VM class names mentioned
    in the same handler region. Best-effort: route handler patterns vary,
    so we widen via the route file + relevant VM module + nearby
    ``XxxVM(`` instantiations.
    """
    referenced: set[str] = set()
    for root in (_ROUTES_DIR, _VIEW_MODELS_DIR):
        for path in root.rglob("*.py"):
            src = path.read_text(encoding="utf-8")
            if f'"{template_name}"' in src:
                referenced.update(_VM_INSTANTIATION_RX.findall(src))
    return referenced


def test_every_base_layout_template_renders_vm_with_recent_multi_leg_field():
    """F23 LOCK — TEMPLATE-MOUNT scope.

    For every template that extends ``base.html.j2``, locate the VM
    class(es) instantiated by code paths referencing that template name,
    then assert each such VM declares (or inherits)
    ``recent_multi_leg_auto_correction_count``.

    Discriminating: catches VMs that inherit ``BaseLayoutVM`` (e.g.,
    ``AccountSnapshotFormVM``) where the field flows via inheritance,
    AND catches future page VMs whose templates extend base but lack
    explicit inheritance.

    Method: greps route files + VM modules for the template filename
    string + any ``XxxVM(`` instantiations nearby. Best-effort by-design;
    the auxiliary FIELD-PRESENCE test below complements this with a
    static-only enumeration on the existing banner-field signal.
    """
    templates = _templates_extending_base()
    assert templates, (
        "no base.html.j2-extending templates found — discovery glob is broken"
    )
    vms_by_name = _vm_classes_by_name()

    # Each base-layout-mounted template must surface at least one VM that
    # carries the new field. If a template's VM cannot be located via the
    # heuristic (route file naming mismatch), the auxiliary tests catch
    # the omission via field-presence checks.
    missing_field_per_template: dict[str, set[str]] = {}
    located_any = False
    for template_path in templates:
        template_name = template_path.relative_to(_TEMPLATES_DIR).as_posix()
        referenced_names = (
            _vm_class_names_referenced_by_route_handlers_for_template(
                template_name,
            )
        )
        # Filter to known dataclass VM types.
        page_vms = [
            vms_by_name[name]
            for name in referenced_names
            if name in vms_by_name
        ]
        if not page_vms:
            # Template's VM could not be located via the heuristic — the
            # auxiliary FIELD-PRESENCE check below will still pin the
            # contract since these templates' VMs all carry the existing
            # banner field.
            continue
        located_any = True
        for vm_cls in page_vms:
            field_names = {f.name for f in dataclasses.fields(vm_cls)}
            if _NEW_FIELD not in field_names:
                missing_field_per_template.setdefault(
                    template_name, set(),
                ).add(f"{vm_cls.__module__}.{vm_cls.__name__}")

    assert located_any, (
        "TEMPLATE-MOUNT introspection located zero VMs across all "
        "base-layout templates — heuristic is broken; need to revisit "
        "_vm_class_names_referenced_by_route_handlers_for_template."
    )
    assert not missing_field_per_template, (
        f"VMs missing {_NEW_FIELD!r} for base-layout templates: "
        f"{missing_field_per_template!r}"
    )


# ---------------------------------------------------------------------------
# 3. Auxiliary FIELD-PRESENCE complement (defense-in-depth)
# ---------------------------------------------------------------------------


def test_every_vm_with_unresolved_material_field_also_has_recent_multi_leg_field():
    """Every VM dataclass that declares (or inherits)
    ``unresolved_material_discrepancies_count`` MUST also declare/inherit
    ``recent_multi_leg_auto_correction_count``.

    The two fields are siblings under base.html.j2's banner block — they
    landed via the same TEMPLATE-MOUNT scope discipline (Phase 10 T-E.3
    + Phase 12.5 #1 T-1.8). Diverging on the second field reintroduces
    the exact UndefinedError gotcha class.
    """
    offenders: list[str] = []
    for vm_cls in _enumerate_all_dataclass_vms():
        field_names = {f.name for f in dataclasses.fields(vm_cls)}
        if _EXISTING_BANNER_FIELD in field_names:
            if _NEW_FIELD not in field_names:
                offenders.append(
                    f"{vm_cls.__module__}.{vm_cls.__name__}",
                )
    assert not offenders, (
        f"VMs carrying {_EXISTING_BANNER_FIELD!r} but NOT {_NEW_FIELD!r}: "
        f"{sorted(offenders)!r}"
    )


def test_every_subclass_of_base_layout_vm_inherits_recent_multi_leg_field():
    """Sanity-check the inheritance leg of the TEMPLATE-MOUNT scope:
    every dataclass-VM that subclasses ``BaseLayoutVM`` (directly or
    transitively) inherits ``recent_multi_leg_auto_correction_count``.
    Catches the ``AccountSnapshotFormVM`` case explicitly.
    """
    offenders: list[str] = []
    for vm_cls in _enumerate_all_dataclass_vms():
        if vm_cls is BaseLayoutVM:
            continue
        if not issubclass(vm_cls, BaseLayoutVM):
            continue
        field_names = {f.name for f in dataclasses.fields(vm_cls)}
        if _NEW_FIELD not in field_names:
            offenders.append(f"{vm_cls.__module__}.{vm_cls.__name__}")
    assert not offenders, (
        f"BaseLayoutVM subclasses missing {_NEW_FIELD!r}: "
        f"{sorted(offenders)!r}"
    )


# ---------------------------------------------------------------------------
# 4. Per-builder populates tests — build_X reads the helper + writes the VM
# ---------------------------------------------------------------------------


def _create_empty_db(path: Path) -> None:
    """Apply the project schema migrations to an empty tmp_path DB."""
    from swing.data.db import ensure_schema
    ensure_schema(path)


def _open_conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _stub_price_cache(monkeypatch):
    """Stub PriceCache.get_many to return empty dict (no executor needed)."""
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *args, **kwargs: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_dashboard_vm_recent_multi_leg_defaults_to_zero_when_no_runs(tmp_path, monkeypatch):
    """Empty DB → no reconciliation_runs → DashboardVM carries 0."""
    from swing.web.price_cache import PriceCache
    from swing.config import load as load_cfg
    _config_path = Path(__file__).resolve().parents[2] / "swing.config.toml"

    db = tmp_path / "swing.db"
    _create_empty_db(db)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    _stub_price_cache(monkeypatch)
    cfg = load_cfg(_config_path)
    # Override DB path on a copy of the cfg.
    cfg = dataclasses.replace(
        cfg, paths=dataclasses.replace(cfg.paths, db_path=db),
    )

    cache = PriceCache(cfg=cfg)
    from swing.web.view_models.dashboard import build_dashboard
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert vm.recent_multi_leg_auto_correction_count == 0


def _seed_multi_leg_auto_correction(conn: sqlite3.Connection) -> None:
    """Insert minimum rows to make
    ``count_recent_multi_leg_auto_corrections`` return >= 1:

      - 1 reconciliation_runs row (state='completed', finished_ts set).
      - 1 reconciliation_discrepancies row with resolved_by =
        'auto_tier1_multi_leg'.
      - 1 reconciliation_corrections row linking the discrepancy to the
        run.

    Schema source: ``swing/data/migrations/`` — see PRAGMA table_info
    output captured during test authoring for the canonical column lists.
    """
    conn.execute(
        "INSERT INTO reconciliation_runs "
        "(run_id, source, period_start, period_end, "
        "started_ts, finished_ts, state, summary_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            1, "schwab_api",
            "2026-05-10", "2026-05-17",
            "2026-05-17T12:00:00", "2026-05-17T12:00:05",
            "completed", "{}",
        ),
    )
    conn.execute(
        "INSERT INTO reconciliation_discrepancies "
        "(discrepancy_id, run_id, discrepancy_type, "
        "trade_id, fill_id, cash_movement_id, ticker, field_name, "
        "material_to_review, expected_value_json, actual_value_json, "
        "resolution, resolved_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            101, 1, "entry_price_mismatch",
            None, None, None, "AAPL", "price",
            1, '{"price": 150.0}', '{"matched": null}',
            "auto_corrected_from_schwab", "auto_tier1_multi_leg",
            "2026-05-17T12:00:03",
        ),
    )
    conn.execute(
        "INSERT INTO reconciliation_corrections "
        "(correction_id, reconciliation_run_id, discrepancy_id, "
        "correction_action, affected_table, affected_row_id, field_name, "
        "pre_correction_value_json, source_canonical_value_json, "
        "applied_value_json, applied_by, applied_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            201, 1, 101,
            "auto_applied", "fills", 9001, "price",
            '{"price": 149.0}', '{"price": 150.0}',
            '{"price": 150.0}', "auto",
            "2026-05-17T12:00:04",
        ),
    )
    conn.commit()


def test_dashboard_vm_populates_recent_multi_leg_field(tmp_path, monkeypatch):
    """Planted discrepancy with resolved_by='auto_tier1_multi_leg' →
    DashboardVM surfaces a non-zero count."""
    from swing.web.price_cache import PriceCache
    from swing.config import load as load_cfg
    _config_path = Path(__file__).resolve().parents[2] / "swing.config.toml"

    db = tmp_path / "swing.db"
    _create_empty_db(db)
    conn = _open_conn(db)
    try:
        _seed_multi_leg_auto_correction(conn)
    finally:
        conn.close()
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    _stub_price_cache(monkeypatch)
    cfg = load_cfg(_config_path)
    cfg = dataclasses.replace(
        cfg, paths=dataclasses.replace(cfg.paths, db_path=db),
    )
    cache = PriceCache(cfg=cfg)
    from swing.web.view_models.dashboard import build_dashboard
    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert vm.recent_multi_leg_auto_correction_count == 1


def test_config_page_vm_populates_recent_multi_leg_field(tmp_path, monkeypatch):
    from swing.config import load as load_cfg
    _config_path = Path(__file__).resolve().parents[2] / "swing.config.toml"
    from swing.web.view_models.config import build_config_vm

    db = tmp_path / "swing.db"
    _create_empty_db(db)
    conn = _open_conn(db)
    try:
        _seed_multi_leg_auto_correction(conn)
    finally:
        conn.close()
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_cfg(_config_path)
    cfg = dataclasses.replace(
        cfg, paths=dataclasses.replace(cfg.paths, db_path=db),
    )
    conn = _open_conn(db)
    try:
        vm = build_config_vm(cfg, saved=False, conn=conn)
    finally:
        conn.close()
    assert vm.recent_multi_leg_auto_correction_count == 1


def test_metrics_index_vm_populates_recent_multi_leg_field(tmp_path, monkeypatch):
    from swing.config import load as load_cfg
    _config_path = Path(__file__).resolve().parents[2] / "swing.config.toml"
    from swing.web.view_models.metrics.index import build_metrics_index_vm
    db = tmp_path / "swing.db"
    _create_empty_db(db)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_cfg(_config_path)
    cfg = dataclasses.replace(
        cfg, paths=dataclasses.replace(cfg.paths, db_path=db),
    )
    conn = _open_conn(db)
    try:
        _seed_multi_leg_auto_correction(conn)
        vm = build_metrics_index_vm(cfg, conn)
    finally:
        conn.close()
    assert vm.recent_multi_leg_auto_correction_count == 1


def test_journal_vm_populates_recent_multi_leg_field(tmp_path, monkeypatch):
    from swing.config import load as load_cfg
    _config_path = Path(__file__).resolve().parents[2] / "swing.config.toml"
    from swing.web.view_models.journal import build_journal

    db = tmp_path / "swing.db"
    _create_empty_db(db)
    conn = _open_conn(db)
    try:
        _seed_multi_leg_auto_correction(conn)
    finally:
        conn.close()
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_cfg(_config_path)
    cfg = dataclasses.replace(
        cfg, paths=dataclasses.replace(cfg.paths, db_path=db),
    )
    vm = build_journal(cfg=cfg, period="month")
    assert vm.recent_multi_leg_auto_correction_count == 1


def test_review_vm_populates_recent_multi_leg_field(tmp_path, monkeypatch):
    """Phase 10 T-B.7 ``ReviewVM`` (in ``swing/web/view_models/trades.py``)
    is one of the base-layout-mounted VMs that explicitly declares the
    banner field. The companion populating builder must also stamp the
    new field via the helper.

    Skipped at the build_review_vm-return path when no closed-unreviewed
    trade exists (the builder returns None); we plant the minimal trade +
    entry-fill rows to drive the happy path.
    """
    from swing.config import load as load_cfg
    _config_path = Path(__file__).resolve().parents[2] / "swing.config.toml"
    from swing.web.view_models.trades import build_review_vm

    db = tmp_path / "swing.db"
    _create_empty_db(db)
    conn = _open_conn(db)
    try:
        _seed_multi_leg_auto_correction(conn)
        # Plant a closed trade with reviewed_at=NULL so build_review_vm
        # finds it.
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_stop, current_stop, initial_shares, "
            "hypothesis_label, state, pre_trade_locked_at, trade_origin) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                999, "AAPL", "2026-05-10", 150.0, 145.0, 145.0, 10,
                "research/test", "closed",
                "2026-05-10T09:30:00", "manual_off_pipeline",
            ),
        )
        conn.execute(
            "INSERT INTO fills (fill_id, trade_id, action, "
            "fill_datetime, price, quantity, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                9001, 999, "entry", "2026-05-10T09:30:00",
                150.0, 10, None,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = load_cfg(_config_path)
    cfg = dataclasses.replace(
        cfg, paths=dataclasses.replace(cfg.paths, db_path=db),
    )
    vm = build_review_vm(trade_id=999, cfg=cfg)
    assert vm is not None
    assert vm.recent_multi_leg_auto_correction_count == 1
