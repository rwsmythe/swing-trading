"""Process-global yfinance audit context (Phase 18 Arc 18-C).

DB-FREE by construction: imports nothing from ``swing.data.db`` or any repo, so
``swing/data/ohlcv_archive.py`` (deliberately DB-free at module import) can
import it at module level without pulling in a DB module. It DOES import the
shared ``_YFINANCE_VALID_SURFACES`` frozenset from ``swing.data.models`` (a
pure-dataclass module, no DB) so the context-install surface validation does
NOT hardcode a copy (the #11 enum-grep rule).

WHY a process-global (mirroring ``swing/log_correlation.py``), NOT a
``ContextVar``: yfinance calls fire from PROCESS-WIDE consumers + worker threads
(the price-fetch executor; the warm's threads=True batch) that would NOT inherit
a ``ContextVar`` set on the main thread -- the id would silently drop on those
records. A lock-guarded module global is single-writer / many-reader and correct
across all threads.

State machine (Codex R5/R8/R12/R13):
  - ``_base``: the persistent BASE slot (web startup / CLI group callback). Set
    via ``set_yfinance_audit_base_context`` -- updates ONLY ``_base``; a base set
    while a scope is active does NOT clobber the scope.
  - ``_scope``: the nested ACTIVE-SCOPE slot (the pipeline run). Set via the
    ``yfinance_audit_scope`` context-manager with LIFO token-restore + a
    single-active-scope guard (a second overlapping scope RAISES). The
    PRODUCTION exit is NON-THROWING (a LIFO mismatch is logged + best-effort
    restored, never raised out of the with-block).
  - ``_disabled``: a depth counter overlay (``yfinance_audit_disabled``) that
    takes PRECEDENCE over BOTH ``_scope`` and ``_base`` so ``get()`` is ``None``
    -- the runner uses it to ensure a degraded (stale-scope) run records NO rows
    rather than MISATTRIBUTING to the stale context.

``get_yfinance_audit_context()`` = ``None`` if disabled, ELSE ``_scope``, ELSE
``_base``, ELSE ``None``.

Run-linkage validation at INSTALL (Codex R12/R13; KEPT per section-9 #4 as the
SINGLE correctly-placed guard for the unattributable-row concern): a
``surface='pipeline'`` install REQUIRES a run id; ``cli``/``web`` install
REQUIRES a NULL run id. Caught at the SOURCE (upstream of the insert); never sees
the post-prune SET-NULLed state.
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass

from swing.data.models import _YFINANCE_VALID_SURFACES

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class YfinanceAuditContext:
    db_path: str
    pipeline_run_id: int | None
    surface: str


_lock = threading.Lock()
_base: YfinanceAuditContext | None = None
_scope: YfinanceAuditContext | None = None
_disabled_depth: int = 0


def _validate_install(*, surface: str, pipeline_run_id: int | None) -> None:
    """Run-linkage + surface validation at context install. Raises ValueError."""
    if surface not in _YFINANCE_VALID_SURFACES:
        raise ValueError(
            f"surface must be in {sorted(_YFINANCE_VALID_SURFACES)}, got {surface!r}"
        )
    # bool is an int subclass; reject it explicitly (Codex executing-R1 MINOR) so
    # an accidental True does NOT bind to SQLite as a pipeline_run_id of 1 (mirrors
    # the YfinanceCall dataclass bool-is-int discipline).
    if pipeline_run_id is not None and (
        isinstance(pipeline_run_id, bool) or not isinstance(pipeline_run_id, int)
    ):
        raise ValueError(
            "pipeline_run_id must be None or int (not bool), "
            f"got {type(pipeline_run_id).__name__}"
        )
    if surface == "pipeline" and pipeline_run_id is None:
        raise ValueError(
            "surface='pipeline' requires a pipeline_run_id (run-linkage invariant)"
        )
    if surface in ("cli", "web") and pipeline_run_id is not None:
        raise ValueError(
            f"surface={surface!r} requires pipeline_run_id=None (it has no pipeline run)"
        )


def get_yfinance_audit_context() -> YfinanceAuditContext | None:
    with _lock:
        if _disabled_depth > 0:
            return None
        if _scope is not None:
            return _scope
        return _base


def set_yfinance_audit_base_context(
    *, db_path: str, pipeline_run_id: int | None, surface: str,
) -> None:
    """Set/replace the persistent BASE context. Updates ONLY ``_base`` -- never
    touches ``_scope`` (a base set under an active scope does not clobber it).
    Validates surface + run-linkage at install (raises on a bad combo)."""
    _validate_install(surface=surface, pipeline_run_id=pipeline_run_id)
    global _base
    with _lock:
        _base = YfinanceAuditContext(
            db_path=db_path, pipeline_run_id=pipeline_run_id, surface=surface,
        )


@contextmanager
def yfinance_audit_scope(
    *, db_path: str, pipeline_run_id: int | None, surface: str,
):
    """Set ``_scope`` on enter; restore the prior ``_scope`` (LIFO) on exit.

    Single-active-scope guard: RAISES ``RuntimeError`` if a scope is already
    active (a stray overlap fails loud). A scope OVER a base is fine (the base
    lives in ``_base``). The PRODUCTION EXIT is NON-THROWING: a LIFO-token
    mismatch is logged + best-effort restored, never raised out of the block
    (audit cleanup must never mask a pipeline exception)."""
    _validate_install(surface=surface, pipeline_run_id=pipeline_run_id)
    new = YfinanceAuditContext(
        db_path=db_path, pipeline_run_id=pipeline_run_id, surface=surface,
    )
    global _scope
    with _lock:
        if _scope is not None:
            raise RuntimeError(
                "yfinance_audit_scope is already active; overlapping scopes are "
                "unsupported (single-active-scope guard)"
            )
        token = _scope  # None by construction here; the LIFO restore target
        _scope = new
    try:
        yield new
    finally:
        with _lock:
            if _scope is not new:
                log.warning(
                    "yfinance_audit_scope LIFO mismatch on exit (expected our "
                    "scope, found a different one); best-effort restoring"
                )
            _scope = token


@contextmanager
def yfinance_audit_disabled():
    """Disable recording for the dynamic extent (PRECEDENCE over scope + base).

    A depth counter (re-entrant). ``get()`` returns ``None`` while depth > 0,
    then the prior state is restored on exit -- NOT a sticky flag."""
    global _disabled_depth
    with _lock:
        _disabled_depth += 1
    try:
        yield
    finally:
        with _lock:
            _disabled_depth -= 1
            if _disabled_depth < 0:
                _disabled_depth = 0


def _set_for_test(
    *, db_path: str, pipeline_run_id: int | None, surface: str,
) -> None:
    """Test-only direct base seam (no validation, no env round-trip)."""
    global _base
    with _lock:
        _base = YfinanceAuditContext(
            db_path=db_path, pipeline_run_id=pipeline_run_id, surface=surface,
        )


def _reset_for_test() -> None:
    """Clear BOTH slots + the disabled overlay between tests."""
    global _base, _scope, _disabled_depth
    with _lock:
        _base = None
        _scope = None
        _disabled_depth = 0
