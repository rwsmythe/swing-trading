from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import swing.pipeline.runner as runner
from swing.data import yfinance_audit_context as ctxmod
from swing.data.yfinance_audit_context import (
    get_yfinance_audit_context,
    yfinance_audit_scope,
)


@pytest.fixture(autouse=True)
def _reset_ctx():
    ctxmod._reset_for_test()
    yield
    ctxmod._reset_for_test()


class _FakeLease:
    run_id = 4242

    def __init__(self):
        self.released = False

    def release(self, **k):
        self.released = True


class _FakeCfg:
    class paths:
        db_path = "/tmp/whatever.db"


def test_pipeline_scope_sets_and_restores_prior(monkeypatch):
    cfg = _FakeCfg()
    lease = _FakeLease()
    assert get_yfinance_audit_context() is None
    with runner._pipeline_yfinance_audit_scope(cfg, lease):
        c = get_yfinance_audit_context()
        assert c.surface == "pipeline"
        assert c.pipeline_run_id == 4242
    assert get_yfinance_audit_context() is None  # restored


def test_pipeline_scope_restores_web_base(monkeypatch):
    ctxmod.set_yfinance_audit_base_context(
        db_path="w.db", pipeline_run_id=None, surface="web")
    cfg = _FakeCfg()
    lease = _FakeLease()
    with runner._pipeline_yfinance_audit_scope(cfg, lease):
        assert get_yfinance_audit_context().surface == "pipeline"
    assert get_yfinance_audit_context().surface == "web"  # NOT cleared


def test_scope_entry_failure_degrades_to_disabled_not_strand(monkeypatch):
    # Pre-seed an ACTIVE scope so the single-active-scope guard rejects the
    # runner's entry -> it must degrade to disabled (records None), NOT raise.
    cfg = _FakeCfg()
    lease = _FakeLease()
    with yfinance_audit_scope(db_path="r.db", pipeline_run_id=99, surface="pipeline"):
        # the runner scope entry now collides with the active scope
        with runner._pipeline_yfinance_audit_scope(cfg, lease):
            # degraded -> get() is None (disabled overlay precedence)
            assert get_yfinance_audit_context() is None
        # outer pre-seeded scope still active + intact
        assert get_yfinance_audit_context().pipeline_run_id == 99


def test_every_post_lease_return_is_inside_the_scope():
    # AST: every `return RunResult(...)` lexically AFTER set_pipeline_run_id in
    # run_pipeline_internal must be inside the `with _pipeline_yfinance_audit_scope`
    # block. (The pre-lease blocked-return at acquire_lease is BEFORE the scope and
    # is exempt.)
    src = inspect.getsource(runner.run_pipeline_internal)
    tree = ast.parse(src)
    fn = tree.body[0]
    # find the set_pipeline_run_id call line + the With node
    set_line = None
    with_node = None
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "set_pipeline_run_id"):
            set_line = node.lineno
        if (isinstance(node, ast.With)
                and any(isinstance(it.context_expr, ast.Call)
                        and getattr(it.context_expr.func, "id", "")
                        == "_pipeline_yfinance_audit_scope"
                        for it in node.items)):
            with_node = node
    assert set_line is not None and with_node is not None
    with_start, with_end = with_node.lineno, with_node.end_lineno
    # collect every RunResult return + its line
    bad = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            f = node.value.func
            if getattr(f, "id", "") == "RunResult":
                ln = node.lineno
                if ln > set_line and not (with_start <= ln <= with_end):
                    bad.append(ln)
    assert not bad, f"post-lease RunResult return(s) outside the scope at lines {bad}"


def test_web_has_no_in_process_run_pipeline():
    # AST/grep guard: NO in-process import/call of run_pipeline anywhere under
    # swing/web/ (only the subprocess command construction in routes/pipeline.py).
    web_dir = Path(runner.__file__).resolve().parents[1] / "web"
    offenders = []
    for py in web_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        # a bare reference to run_pipeline / run_pipeline_internal as an attr/name
        for needle in ("run_pipeline_internal", "import run_pipeline",
                       "runner.run_pipeline", "run_pipeline("):
            if needle in text:
                offenders.append((py.name, needle))
    assert not offenders, f"in-process run_pipeline reference under swing/web/: {offenders}"
