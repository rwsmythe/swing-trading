"""22-F shared test instruments: the both-verbs-fail connection proxy.

A PROXY, not a monkeypatched module function (the model is
`tests/trades/test_cohort_provenance_write.py::_FailingCleanupConn`), so the
production handler reacts to a REAL call on the REAL statement it issues.

THE DID-IT-FIRE RULE (22-F plan section 0.4, R3-01/R4-01, no exceptions):
every proxy records its calls per verb, and every test driven through it
asserts the verb it fails (or, for a pass-through, the verb it observes) was
called at least once.  A missed patch then fails RED instead of passing
vacuously.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any, Callable

_OWN = frozenset({
    "_real", "_fail_sql_prefix", "_fail_sql_times", "_fail_rollback",
    "_fail_close", "_raise_on_sql", "_fail_after_executescript",
    "_fail_executescript", "_executescripts_returned", "_after_fired",
    "calls", "sql_log", "_sql_failures", "_rollback_failures",
})


def _make_exc(raise_on: Any, what: str) -> BaseException:
    if isinstance(raise_on, BaseException):
        return raise_on
    if raise_on is KeyboardInterrupt:
        return KeyboardInterrupt(f"planted on {what}")
    return raise_on(f"planted on {what}")


class FailingVerbsConn:
    """Delegates to a real `sqlite3.Connection`; fails the named verbs.

    * ``fail_sql_prefix`` -- an ``execute``/``executemany`` whose SQL (left-
      stripped, upper-cased) starts with this prefix raises ``raise_on_sql``.
      ``fail_sql_times`` bounds how many matches fail (``None`` = all).
    * ``fail_rollback`` -- ``True`` fails every ``rollback()`` AND every
      ``execute("ROLLBACK")`` (not ``ROLLBACK TO``); an ``int`` fails only the
      first N such attempts.
    * ``fail_close`` -- ``close()`` raises ``sqlite3.OperationalError`` AFTER
      closing the real connection (the handle is released either way, so a
      test's temp DB is not left locked).
    * ``fail_after_executescript=(prefix, n)`` -- fails ONLY the FIRST
      statement matching ``prefix`` issued AFTER the proxy's ``n``-th
      ``executescript`` call has RETURNED; every earlier match passes.
    * ``fail_executescript=<exc class>`` -- ``executescript`` first runs the
      real ``executescript("BEGIN;")`` (leaving a transaction OPEN, as a
      mid-script failure does) and then raises.
    """

    def __init__(self, real: sqlite3.Connection, *,
                 fail_sql_prefix: str | None = None,
                 fail_sql_times: int | None = None,
                 fail_rollback: bool | int = False,
                 fail_close: bool = False,
                 raise_on_sql: Any = sqlite3.OperationalError,
                 fail_after_executescript: tuple[str, int] | None = None,
                 fail_executescript: Any = None) -> None:
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "_fail_sql_prefix",
                           fail_sql_prefix.upper() if fail_sql_prefix else None)
        object.__setattr__(self, "_fail_sql_times", fail_sql_times)
        object.__setattr__(self, "_fail_rollback", fail_rollback)
        object.__setattr__(self, "_fail_close", fail_close)
        object.__setattr__(self, "_raise_on_sql", raise_on_sql)
        object.__setattr__(self, "_fail_after_executescript",
                           fail_after_executescript)
        object.__setattr__(self, "_fail_executescript", fail_executescript)
        object.__setattr__(self, "_executescripts_returned", 0)
        object.__setattr__(self, "_after_fired", False)
        object.__setattr__(self, "calls", Counter())
        object.__setattr__(self, "sql_log", [])
        object.__setattr__(self, "_sql_failures", 0)
        object.__setattr__(self, "_rollback_failures", 0)

    # -- delegation --------------------------------------------------------
    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _OWN:
            object.__setattr__(self, name, value)
        else:
            setattr(self._real, name, value)

    def __enter__(self) -> "FailingVerbsConn":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # sqlite3's own context manager: commit on success, rollback on any
        # exception, never suppress.  Routed through THIS proxy's methods so a
        # planted rollback failure is reachable from `with conn:` too.
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False

    # -- helpers -----------------------------------------------------------
    def _rollback_should_fail(self) -> bool:
        fr = self._fail_rollback
        if fr is True:
            return True
        if isinstance(fr, int) and not isinstance(fr, bool) and fr > 0:
            if self._rollback_failures < fr:
                return True
        return False

    def _check_sql(self, sql: str) -> None:
        norm = sql.lstrip().upper()
        verb = norm.split(None, 1)[0] if norm else ""
        self.calls[f"execute:{verb}"] += 1
        self.sql_log.append(sql)
        is_plain_rollback = (norm.rstrip("; ") == "ROLLBACK"
                             or norm.startswith("ROLLBACK TRANSACTION"))
        if is_plain_rollback:
            self.calls["rollback"] += 1
            if self._rollback_should_fail():
                self._rollback_failures += 1
                raise sqlite3.OperationalError(
                    "cannot rollback (planted on execute ROLLBACK)")
        fae = self._fail_after_executescript
        if (fae is not None and not self._after_fired
                and self._executescripts_returned >= fae[1]
                and norm.startswith(fae[0].upper())):
            self._after_fired = True
            self.calls["failed_after_executescript"] += 1
            raise _make_exc(self._raise_on_sql, fae[0])
        p = self._fail_sql_prefix
        if p is not None and norm.startswith(p):
            if (self._fail_sql_times is None
                    or self._sql_failures < self._fail_sql_times):
                self._sql_failures += 1
                self.calls["failed_sql"] += 1
                raise _make_exc(self._raise_on_sql, p)

    # -- the verbs ---------------------------------------------------------
    def execute(self, sql: str, *args: Any) -> Any:
        self._check_sql(sql)
        return self._real.execute(sql, *args)

    def executemany(self, sql: str, *args: Any) -> Any:
        self._check_sql(sql)
        return self._real.executemany(sql, *args)

    def executescript(self, script: str) -> Any:
        self.calls["executescript"] += 1
        if self._fail_executescript is not None:
            self._real.executescript("BEGIN;")
            raise _make_exc(self._fail_executescript, "executescript")
        out = self._real.executescript(script)
        self._executescripts_returned += 1
        return out

    def rollback(self) -> None:
        self.calls["rollback"] += 1
        if self._rollback_should_fail():
            self._rollback_failures += 1
            raise sqlite3.OperationalError("cannot rollback (planted on rollback)")
        return self._real.rollback()

    def commit(self) -> None:
        self.calls["commit"] += 1
        return self._real.commit()

    def close(self) -> None:
        self.calls["close"] += 1
        if self._fail_close:
            self._real.close()
            raise sqlite3.OperationalError("cannot close (planted on close)")
        return self._real.close()


def patch_conn_opener(monkeypatch, target: str,
                      proxy_factory: Callable[[sqlite3.Connection], Any]
                      ) -> list:
    """Patch the dotted opener ``target`` (``"<module>.<name>"``).

    ``target`` MUST be the name the code under test resolves AT CALL TIME,
    read from its source: a module-level ``from swing.data.db import connect``
    binds ``<that module>.connect``; a FUNCTION-LOCAL import re-reads
    ``swing.data.db.connect`` on every call.  Returns the list the proxies are
    appended to, so the test can assert the did-it-fire rule on them.
    """
    import importlib

    module_name, _, attr = target.rpartition(".")
    module = importlib.import_module(module_name)
    original = getattr(module, attr)
    built: list = []

    def _opener(*args: Any, **kwargs: Any) -> Any:
        real = original(*args, **kwargs)
        proxy = proxy_factory(real)
        built.append(proxy)
        return proxy

    monkeypatch.setattr(module, attr, _opener)
    return built


def open_connection_returning(monkeypatch,
                              proxy_factory: Callable[[sqlite3.Connection], Any]
                              ) -> list:
    """Patch the MODULE GLOBAL ``swing.data.db.open_connection`` -- the name
    ``ensure_schema`` resolves (``db.py``)."""
    return patch_conn_opener(monkeypatch, "swing.data.db.open_connection",
                             proxy_factory)


class CountingWrapper:
    """A counting wrapper around a monkeypatched FUNCTION (did-it-fire)."""

    def __init__(self, fn: Callable[..., Any]) -> None:
        self.fn = fn
        self.calls = 0

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return self.fn(*args, **kwargs)


def raising(exc: BaseException) -> CountingWrapper:
    """A counting wrapper that raises ``exc`` on every call."""
    def _raise(*_a: Any, **_k: Any) -> Any:
        raise exc
    return CountingWrapper(_raise)
