from __future__ import annotations

import pytest

from swing.data import yfinance_audit_context as ctxmod
from swing.data.yfinance_audit_context import (
    get_yfinance_audit_context,
    set_yfinance_audit_base_context,
    yfinance_audit_disabled,
    yfinance_audit_scope,
)


@pytest.fixture(autouse=True)
def _reset():
    ctxmod._reset_for_test()
    yield
    ctxmod._reset_for_test()


def test_default_is_none():
    assert get_yfinance_audit_context() is None


def test_base_round_trips():
    set_yfinance_audit_base_context(db_path="x.db", pipeline_run_id=None, surface="web")
    c = get_yfinance_audit_context()
    assert c is not None
    assert (c.db_path, c.pipeline_run_id, c.surface) == ("x.db", None, "web")


def test_base_can_be_replaced():
    set_yfinance_audit_base_context(db_path="a.db", pipeline_run_id=None, surface="web")
    set_yfinance_audit_base_context(db_path="b.db", pipeline_run_id=None, surface="cli")
    c = get_yfinance_audit_context()
    assert (c.db_path, c.surface) == ("b.db", "cli")


def test_scope_sets_and_restores_prior_none():
    assert get_yfinance_audit_context() is None
    with yfinance_audit_scope(db_path="r.db", pipeline_run_id=7, surface="pipeline"):
        c = get_yfinance_audit_context()
        assert (c.surface, c.pipeline_run_id) == ("pipeline", 7)
    assert get_yfinance_audit_context() is None


def test_scope_nested_over_base_restores_base():
    set_yfinance_audit_base_context(db_path="w.db", pipeline_run_id=None, surface="web")
    with yfinance_audit_scope(db_path="r.db", pipeline_run_id=7, surface="pipeline"):
        assert get_yfinance_audit_context().surface == "pipeline"
    after = get_yfinance_audit_context()
    assert after.surface == "web"  # NOT None


def test_base_set_does_not_clobber_active_scope():
    set_yfinance_audit_base_context(db_path="w.db", pipeline_run_id=None, surface="web")
    with yfinance_audit_scope(db_path="r.db", pipeline_run_id=7, surface="pipeline"):
        set_yfinance_audit_base_context(db_path="c.db", pipeline_run_id=None, surface="cli")
        # scope still wins while active
        assert get_yfinance_audit_context().surface == "pipeline"
    # after the scope exits, get() is the NEW cli base
    assert get_yfinance_audit_context().surface == "cli"


def test_second_overlapping_scope_raises():
    with yfinance_audit_scope(db_path="r.db", pipeline_run_id=7, surface="pipeline"):
        with pytest.raises(RuntimeError):
            with yfinance_audit_scope(db_path="r2.db", pipeline_run_id=8, surface="pipeline"):
                pass


def test_disabled_overlay_precedence_over_scope_and_base():
    set_yfinance_audit_base_context(db_path="w.db", pipeline_run_id=None, surface="web")
    with yfinance_audit_scope(db_path="r.db", pipeline_run_id=7, surface="pipeline"):
        with yfinance_audit_disabled():
            assert get_yfinance_audit_context() is None  # precedence over scope+base
        # restored after disabled exits
        assert get_yfinance_audit_context().surface == "pipeline"
    assert get_yfinance_audit_context().surface == "web"


def test_disabled_over_base_only():
    set_yfinance_audit_base_context(db_path="w.db", pipeline_run_id=None, surface="web")
    with yfinance_audit_disabled():
        assert get_yfinance_audit_context() is None
    assert get_yfinance_audit_context().surface == "web"


def test_scope_exit_does_not_raise_even_on_state_mismatch():
    # The PRODUCTION exit is NON-THROWING: even if the global state is mutated
    # mid-scope (a mismatch), exiting the with-block must NOT raise out of it.
    with yfinance_audit_scope(db_path="r.db", pipeline_run_id=7, surface="pipeline"):
        ctxmod._reset_for_test()  # clobber the scope slot mid-block
    # no exception escaped


# -- context-install run-linkage validation (KEPT per section-9 #4) --

def test_install_pipeline_with_none_run_id_raises():
    with pytest.raises(ValueError):
        set_yfinance_audit_base_context(db_path="x.db", pipeline_run_id=None, surface="pipeline")
    with pytest.raises(ValueError):
        with yfinance_audit_scope(db_path="x.db", pipeline_run_id=None, surface="pipeline"):
            pass


@pytest.mark.parametrize("surface", ["cli", "web"])
def test_install_cli_web_with_run_id_raises(surface):
    with pytest.raises(ValueError):
        set_yfinance_audit_base_context(db_path="x.db", pipeline_run_id=5, surface=surface)
    with pytest.raises(ValueError):
        with yfinance_audit_scope(db_path="x.db", pipeline_run_id=5, surface=surface):
            pass


def test_install_unknown_surface_raises():
    with pytest.raises(ValueError):
        set_yfinance_audit_base_context(db_path="x.db", pipeline_run_id=None, surface="mobile")


def test_install_bool_run_id_raises():
    # bool is an int subclass; a True run id must NOT bind as 1 (Codex executing-R1).
    with pytest.raises(ValueError):
        set_yfinance_audit_base_context(
            db_path="x.db", pipeline_run_id=True, surface="pipeline")
    with pytest.raises(ValueError):
        with yfinance_audit_scope(db_path="x.db", pipeline_run_id=True, surface="pipeline"):
            pass
