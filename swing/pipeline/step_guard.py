"""The best-effort per-step wrapper for the pipeline runner (Arc 17-B).

Collapses the repeated ``lease.step(name)`` + ``try/except LeaseRevokedError/
except Exception`` boilerplate around best-effort step calls into one tested
context manager. Handles ONLY the two best-effort variants:

  * BS (best-effort + status): pass ``status_key`` -> sets ``<key>="ok"`` on
    clean exit, ``<key>="failed"`` when the body raises a non-revoke Exception.
  * B  (best-effort, no status): omit ``status_key`` -> no status writes.

NOT handled here (left explicit in runner.py): the FATAL ``evaluate`` step
(returns RunResult from run_pipeline -- a context manager cannot), the two
``finviz_fetch`` branches, ``charts`` (a three-way typed handler), the
``shadow_expectancy`` failure-side run_warnings append (gotcha #27 keeps
run_warnings in the SITE, never the guard), ``complete``, and
``review_log_cadence`` (kept inline: it runs under the ``complete`` breadcrumb
with no breadcrumb of its own, and -- per 17-D.3 -- re-raises LeaseRevokedError
then swallows only ordinary Exceptions, like every other guarded step).

LOCK invariants (Arc 17-B brief §5): lease.step fires in __enter__ at the same
point as today (#25); LeaseRevokedError ALWAYS re-raises (#4); the failure log
emits on the caller-supplied ``logger`` so records keep the runner logger name
-> the RENDERED log line, logger name, level, and message are byte-identical and
redaction routing + the [logging.loggers] override table are unaffected (#5; see
the Round-2 caller-metadata caveat in the plan's design notes); the guard never
touches run_warnings (#27).
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from swing.data.repos.pipeline import LeaseRevokedError


@contextmanager
def step_guard(
    lease,
    name: str,
    *,
    logger: logging.Logger,
    status_key: str | None = None,
    log_failure: Callable[[logging.Logger, str, Exception], None] | None = None,
) -> Iterator[None]:
    """Wrap a best-effort pipeline step.

    Args:
        lease: the run lease (provides ``.step(name)`` and ``.status(**cols)``).
        name: the step name -> the ``lease.step`` timing breadcrumb (#25).
        logger: the logger used for the default failure warning. The runner
            passes its own ``log`` so records emit on ``swing.pipeline.runner``
            (LOCK #5 byte-identical log surface).
        status_key: the ``*_status`` column for a BS site, or None for a B site.
        log_failure: optional override invoked as ``log_failure(logger, name,
            exc)`` to reproduce a site's exact current warning text (e.g. the
            ``"... (continuing pipeline): <type>"`` schwab wording). When None,
            the default ``logger.warning("%s failed: %s", name, exc)`` is used.
    """
    lease.step(name)
    try:
        yield
        # The success status write lives INSIDE the try (not an `else:`) so it
        # has byte-identical behavior to the inline runner sites, where
        # `lease.status(<key>="ok")` sits inside the step `try` (e.g. weather
        # runner.py:770, watchlist:880, recommendations:893, export:1031): if
        # the "ok" write itself raises a non-revoke Exception, the current code
        # logs the warning + writes "failed" + continues. An `else:` clause
        # would let that exception PROPAGATE -- a behavior change. (Codex R1 #1.)
        if status_key is not None:
            lease.status(**{status_key: "ok"})
    except LeaseRevokedError:
        raise
    except Exception as exc:  # noqa: BLE001 -- best-effort swallow by design
        if log_failure is not None:
            log_failure(logger, name, exc)
        else:
            logger.warning("%s failed: %s", name, exc)
        if status_key is not None:
            lease.status(**{status_key: "failed"})
