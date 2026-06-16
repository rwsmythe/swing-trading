"""Phase 18 arc 18-H.4 — web `/schwab/setup` self-lock (WinError 32) regression.

The bug (operator-reported, root-caused by CHARC): the long-lived web Schwab
client held in ``app.state.schwab_client`` (constructed at
``swing/web/app.py`` :478 via ``_install_web_marketdata_caches`` ->
``_construct_web_schwab_client``) keeps the per-env tokens DB
(``~/swing-data/schwab-tokens.{env}.db``) open with ``BEGIN EXCLUSIVE`` for the
whole ``swing web`` session. When ``POST /schwab/setup`` runs in that same
process the setup flow's rename-the-stale-DB-aside step (``os.replace`` in
``auth.py:_rename_stale_tokens_db``) fails on Windows because the web app's OWN
open handle holds the file -> ``PermissionError: [WinError 32]`` -> the broad
except renders a generic 500.

The fix (release-before-replace, then reconstruct): the POST handler must, BEFORE
invoking the setup flow, RELEASE the long-lived ``app.state.schwab_client``
(drop the ref + ``gc.collect()`` so the SQLite handle is released
deterministically), run the setup flow, then RECONSTRUCT via the existing
``_construct_web_schwab_client(cfg)`` factory and store it back in app.state.

These tests exercise the WEB setup path (the ``app.state`` client lifecycle +
the POST handler), NOT ``auth.py`` in isolation -- an isolated-auth test would
pass against the broken code because it bypasses the web client lifecycle (the
synthetic-vs-production-emitter gotcha). The discriminator: a STUB long-lived
client that, while it is still referenced by ``app.state``, makes the setup
flow's rename FAIL (mirroring the real Windows file-in-use lock); the handler
must release it before the rename so the rename succeeds.
"""
from __future__ import annotations

import dataclasses
import threading

from fastapi.testclient import TestClient

from swing.web.app import _SchwabClientHolder, create_app


def _production_ladder_cfg(base_cfg):
    """Return a cfg with production env + ladder enabled (no live network).

    Mirrors ``tests/web/test_app_marketdata_ladder_wiring.py:_production_cfg`` so
    ``create_app`` -> ``_install_web_marketdata_caches`` actually CONSTRUCTS the
    web Schwab client and installs the REAL ladder-fetcher closures (the full
    production reference graph) instead of the sandbox no-client default.
    """
    schwab = dataclasses.replace(
        base_cfg.integrations.schwab,
        environment="production", marketdata_ladder_enabled=True,
    )
    integ = dataclasses.replace(base_cfg.integrations, schwab=schwab)
    return dataclasses.replace(base_cfg, integrations=integ)


def _isolate_home(monkeypatch, tmp_path) -> None:
    """Monkeypatch USERPROFILE+HOME to ``tmp_path`` (see the sibling
    test_schwab_setup_route.py docstring) so ``_resolve_tokens_db_path``'s
    ``_user_home()`` reads test-controlled state, not the operator's real
    ``~/swing-data/``."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


class _StubLockingClient:
    """A stand-in for the long-lived schwabdev web client that, while a
    reference to it remains held, simulates the Windows ``BEGIN EXCLUSIVE``
    file lock on the tokens DB.

    ``locked`` is a class-level flag toggled True at construction and False
    only when the instance is finalized (``__del__``). The handler's fix
    drops the ``app.state`` ref + ``gc.collect()`` -> ``__del__`` runs ->
    ``locked`` flips False BEFORE the setup flow's rename runs. Pre-fix, the
    handler never releases the ref, so ``locked`` is still True when the
    setup stub checks it -> the stub raises PermissionError (the WinError 32
    proxy) -> the broad except renders a 500.

    Codex R1 MAJOR 4 — the instance deliberately builds a REFERENCE CYCLE
    (``self._self_ref = self``) so plain CPython refcounting CANNOT finalize
    it when ``app.state`` drops its reference. Only the cyclic garbage
    collector reclaims it -> ``__del__`` runs ONLY when the handler actually
    calls ``gc.collect()`` (the real release dance). A weak fix that merely
    set ``app.state.schwab_client = None`` WITHOUT ``gc.collect()`` would
    leave ``locked is True`` at setup time -> the discriminator stays red.
    This proves the test distinguishes the full release dance, not just the
    app.state clear.
    """

    locked = False

    def __init__(self) -> None:
        _StubLockingClient.locked = True
        # Reference cycle: defeats immediate refcount finalization so only
        # gc.collect() (the handler's release dance) can reclaim + finalize.
        self._self_ref = self

    def __del__(self) -> None:  # pragma: no cover - finalizer timing
        _StubLockingClient.locked = False


def test_post_releases_client_so_rename_succeeds_and_reconstructs(
    seeded_db, monkeypatch, tmp_path,
):
    """The binding 18-H.4 discriminator.

    Construct the web app, inject a stub long-lived client that holds the
    tokens-DB "lock" (``_StubLockingClient.locked is True``). The setup
    service stub raises PermissionError if the lock is STILL held when it
    runs -- i.e. if the handler did not release the client first. The
    reconstruction factory is stubbed to return a fresh sentinel client so
    we can assert app.state is repopulated.

    Both-ways arithmetic:
      * PRE-FIX (no release step): the handler calls the setup flow with the
        stub client still referenced by app.state -> ``locked is True`` ->
        the setup stub raises PermissionError -> broad except -> 500. The
        ``status_code == 204`` assertion FAILS (red).
      * POST-FIX (release -> setup -> reconstruct): the handler drops the
        app.state ref + ``gc.collect()`` -> ``__del__`` -> ``locked is
        False`` -> the setup stub's rename "succeeds" -> 204, and app.state
        holds the freshly-reconstructed client. Both assertions PASS (green).
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "selflock_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "selflock_secret_abc")

    import swing.web.routes.schwab as schwab_route

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        # The rename-aside step fails iff the long-lived client still holds
        # the lock at setup time (the WinError 32 proxy).
        if _StubLockingClient.locked:
            raise PermissionError(
                32,
                "The process cannot access the file because it is being "
                "used by another process",
            )
        return {
            "tokens_path": "/tmp/stub.db",
            "account_hash": "SELFLOCK",
            "environment": environment,
            "call_id_setup": 1,
            "call_id_account_linked": 2,
            "num_accounts": 1,
            "oauth_http_status": 200,
        }

    reconstructed = object()

    def _stub_reconstruct(_cfg):
        return reconstructed

    monkeypatch.setattr(
        schwab_route, "setup_paste_flow_with_callback_url", _stub_service,
    )
    # The reconstruction reuses the EXISTING factory via a LAZY import from
    # swing.web.app (Codex R1 MAJOR 1 — circular-import-safe), so we patch the
    # factory at its SOURCE module so we can assert app.state is repopulated
    # without a live schwabdev construction.
    import swing.web.app as web_app
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", _stub_reconstruct,
    )

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as test_client:
        # Inject the long-lived stub client AFTER lifespan startup (the
        # default test app constructs no client -- sandbox / ladder
        # inactive -- so app.state.schwab_client starts None).
        app.state.schwab_client = _StubLockingClient()
        r = test_client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=abc%40xyz"},
            headers={"HX-Request": "true"},
        )

    assert r.status_code == 204, (
        f"expected 204 (release-before-rename succeeded); got "
        f"{r.status_code}: {r.text[:200]} -- the long-lived client was not "
        "released before the setup rename (WinError 32 self-lock)"
    )
    assert r.headers.get("HX-Redirect") == "/schwab/status"
    # The client was reconstructed afterward (app.state has a live client).
    assert app.state.schwab_client is reconstructed, (
        "app.state.schwab_client not reconstructed after setup -- web "
        "market-data would stay on yfinance until restart"
    )


def test_post_reconstruct_failure_degrades_to_none_not_500(
    seeded_db, monkeypatch, tmp_path,
):
    """Graceful-degradation lock: if reconstruction returns None (creds gone
    / construction failure), the setup STILL succeeds (204) and app.state
    degrades to None (yfinance) -- never a hard crash. The token write is
    independent of the web client."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "selflock_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "selflock_secret_abc")

    import swing.web.routes.schwab as schwab_route

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        return {
            "tokens_path": "/tmp/stub.db",
            "account_hash": "SELFLOCK",
            "environment": environment,
            "call_id_setup": 1,
            "call_id_account_linked": 2,
            "num_accounts": 1,
            "oauth_http_status": 200,
        }

    monkeypatch.setattr(
        schwab_route, "setup_paste_flow_with_callback_url", _stub_service,
    )
    import swing.web.app as web_app
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", lambda _cfg: None,
    )

    app = create_app(cfg, _cfg_path)
    with TestClient(app) as test_client:
        app.state.schwab_client = _StubLockingClient()
        r = test_client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=abc%40xyz"},
            headers={"HX-Request": "true"},
        )

    assert r.status_code == 204, (
        f"setup must still succeed when reconstruction fails; got "
        f"{r.status_code}: {r.text[:200]}"
    )
    assert app.state.schwab_client is None


def test_post_with_no_long_lived_client_still_succeeds(
    seeded_db, monkeypatch, tmp_path,
):
    """When there is no long-lived client (sandbox / ladder inactive ->
    app.state.schwab_client is None), the release step is a no-op and setup
    proceeds normally. Guards against an AttributeError / None-deref in the
    release path."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "selflock_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "selflock_secret_abc")

    import swing.web.routes.schwab as schwab_route

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        return {
            "tokens_path": "/tmp/stub.db",
            "account_hash": "SELFLOCK",
            "environment": environment,
            "call_id_setup": 1,
            "call_id_account_linked": 2,
            "num_accounts": 1,
            "oauth_http_status": 200,
        }

    monkeypatch.setattr(
        schwab_route, "setup_paste_flow_with_callback_url", _stub_service,
    )
    import swing.web.app as web_app
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", lambda _cfg: None,
    )

    app = create_app(cfg, _cfg_path)
    # Do NOT inject a client; app.state.schwab_client stays None.
    with TestClient(app) as test_client:
        assert app.state.schwab_client is None
        r = test_client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=abc%40xyz"},
            headers={"HX-Request": "true"},
        )

    assert r.status_code == 204, (
        f"setup with no long-lived client must succeed; got "
        f"{r.status_code}: {r.text[:200]}"
    )


def test_post_reconstruct_factory_raise_degrades_to_none_not_500(
    seeded_db, monkeypatch, tmp_path,
):
    """Codex R2 MAJOR 2 — when the reconstruction factory itself RAISES (not
    just returns None; e.g. an import/lookup failure or a construction
    exception the factory does not catch), the POST must STILL succeed (204)
    and degrade to app.state.schwab_client = None -- never a hard 500. The
    token write is independent of the web client."""
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "selflock_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "selflock_secret_abc")

    import swing.web.routes.schwab as schwab_route

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        return {
            "tokens_path": "/tmp/stub.db",
            "account_hash": "SELFLOCK",
            "environment": environment,
            "call_id_setup": 1,
            "call_id_account_linked": 2,
            "num_accounts": 1,
            "oauth_http_status": 200,
        }

    def _raising_factory(_cfg):
        raise RuntimeError("reconstruction factory exploded")

    monkeypatch.setattr(
        schwab_route, "setup_paste_flow_with_callback_url", _stub_service,
    )

    app = create_app(cfg, _cfg_path)
    import swing.web.app as web_app
    # Patch the factory AFTER create_app's startup install (which also calls
    # the factory) so ONLY the route's post-setup reconstruction path hits the
    # raiser -- exercising the reconstruct-failure-degrades guard in isolation.
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", _raising_factory,
    )
    with TestClient(app) as test_client:
        app.state.schwab_client = _StubLockingClient()
        r = test_client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=abc%40xyz"},
            headers={"HX-Request": "true"},
        )

    assert r.status_code == 204, (
        f"setup must still succeed when the reconstruct factory raises; got "
        f"{r.status_code}: {r.text[:200]}"
    )
    assert app.state.schwab_client is None


def test_post_release_finalizes_client_through_real_ladder_closures(
    seeded_db, monkeypatch, tmp_path,
):
    """18-H.4.1 binding discriminator -- the FULL production reference graph.

    The 18-H.4 test (``test_post_releases_client_so_rename_succeeds_and_
    reconstructs``) injected a bare stub into ``app.state.schwab_client`` with NO
    cache-hook closures. It passed against ``4d8b92bb`` even though the fix was
    INEFFECTIVE in the only case the bug actually occurs (the ladder-active
    production case), because the closures that ALSO strong-ref the client lived
    OUTSIDE the test's reference graph (the synthetic-vs-production-emitter
    gotcha).

    This test replicates the production reference graph: build the app with a
    PRODUCTION + ladder-enabled cfg so ``create_app`` ->
    ``_install_web_marketdata_caches`` constructs the client AND installs the
    REAL ``_quote_hook`` / ``_bars_hook`` closures over it (price_cache /
    ohlcv_cache hold them on ``app.state`` for the app's lifetime). The
    constructed client is a ``_StubLockingClient`` (returned by the patched
    ``construct_authenticated_client``) so we can observe finalization via its
    ``locked`` class flag.

    Both-ways arithmetic (proves the test distinguishes 4d8b92bb from the fix):
      * PRE-FIX (closures capture the local ``client``): the route's release
        nulls ``app.state.schwab_client`` + ``gc.collect()``, but the two
        closures STILL strong-ref the stub -> it is NOT finalized -> ``locked``
        stays True at setup time -> the setup stub raises PermissionError(32)
        (the WinError-32 self-lock proxy) -> broad except -> 500. The
        ``status_code == 204`` assertion FAILS (red).
      * POST-FIX (closures resolve ``app.state.schwab_client`` at call time, NOT
        a captured ref): nulling the holder leaves NO strong ref from the
        closures -> ``gc.collect()`` reclaims the stub -> ``__del__`` -> ``locked
        is False`` -> the setup stub's rename "succeeds" -> 204, and app.state
        holds the freshly-reconstructed client. PASSES (green).
    """
    cfg, _cfg_path = seeded_db
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "selflock_id_value_1234567890")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "selflock_secret_abc")

    import swing.web.routes.schwab as schwab_route

    def _stub_service(
        cfg_arg, environment, client_id, client_secret,
        callback_url_with_code, conn, *, force=False, account_picker=None,
    ):
        # The rename-aside step fails iff the long-lived client (incl. via the
        # ladder closures) still holds the lock at setup time (WinError 32 proxy).
        if _StubLockingClient.locked:
            raise PermissionError(
                32,
                "The process cannot access the file because it is being "
                "used by another process",
            )
        return {
            "tokens_path": "/tmp/stub.db",
            "account_hash": "SELFLOCK",
            "environment": environment,
            "call_id_setup": 1,
            "call_id_account_linked": 2,
            "num_accounts": 1,
            "oauth_http_status": 200,
        }

    monkeypatch.setattr(
        schwab_route, "setup_paste_flow_with_callback_url", _stub_service,
    )

    # create_app -> _install_web_marketdata_caches -> _construct_web_schwab_client
    # -> construct_authenticated_client. Patch the LEAF so the STARTUP install
    # really constructs the locking stub AND the REAL ladder closures capture/
    # reference IT (the full production graph). _construct_web_schwab_client stays
    # UNPATCHED through create_app so this leaf is reached.
    monkeypatch.setattr(
        "swing.web.app.construct_authenticated_client",
        lambda *a, **k: _StubLockingClient(),
    )

    app = create_app(_production_ladder_cfg(cfg))
    # The production install really constructed the locking stub AND installed the
    # real closures over it -- the exact reference graph 18-H.4 missed.
    assert app.state.schwab_client is not None
    assert app.state.price_cache._ladder_fetcher is not None
    assert app.state.ohlcv_cache._ladder_bars_fetcher is not None
    assert _StubLockingClient.locked is True

    # Reconstruction reuses the EXISTING factory via a lazy import from
    # swing.web.app; patch at the source AFTER startup so ONLY the post-setup
    # reconstruct yields a fresh sentinel (no live schwabdev construction) and
    # the startup install above still builds the real stub + closures.
    reconstructed = object()
    import swing.web.app as web_app
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", lambda _cfg: reconstructed,
    )

    with TestClient(app) as test_client:
        r = test_client.post(
            "/schwab/setup",
            data={"callback_url": "https://127.0.0.1/?code=abc%40xyz"},
            headers={"HX-Request": "true"},
        )

    assert r.status_code == 204, (
        f"expected 204 (release finalized the client THROUGH the real ladder "
        f"closures so the rename succeeded); got {r.status_code}: "
        f"{r.text[:200]} -- the closures still strong-ref the old client "
        "(WinError 32 self-lock survives in the ladder-active production case)"
    )
    assert r.headers.get("HX-Redirect") == "/schwab/status"
    assert app.state.schwab_client is reconstructed, (
        "app.state.schwab_client not reconstructed after setup -- web "
        "market-data would stay on yfinance until restart"
    )


def test_holder_drain_waits_for_inflight_borrow_then_releases():
    """18-H.4.1 R1 MAJOR (Codex, repo-access round) -- the in-flight-fetch self-
    lock window.

    A ladder hook that has ALREADY ``borrow()``ed the client and is mid-fetch
    holds a transient local strong ref to it. If ``/schwab/setup``'s release only
    cleared the holder slot + gc.collect (ignoring the in-flight borrow), that
    local ref would keep the tokens-DB SQLite handle open -> the rename re-hits
    WinError 32. ``drain_and_release`` must WAIT for in-flight borrows to finish
    before returning so the caller's gc can finalize the client.

    This drives the holder directly (a deterministic two-thread handshake) rather
    than racing the real executor: a borrow is entered + held, the drain is
    started on another thread + observed to BLOCK while the borrow is open, then
    the borrow exits and the drain is observed to COMPLETE and return the client.
    """
    sentinel = object()
    holder = _SchwabClientHolder(sentinel)

    borrow_entered = threading.Event()
    release_borrow = threading.Event()
    drain_returned = threading.Event()
    drained_value = {}

    def _hold_a_borrow():
        with holder.borrow() as c:
            assert c is sentinel
            borrow_entered.set()
            # Hold the in-flight borrow until the test lets it go.
            release_borrow.wait(timeout=5.0)

    def _do_drain():
        drained_value["v"] = holder.drain_and_release(timeout=5.0)
        drain_returned.set()

    t_borrow = threading.Thread(target=_hold_a_borrow)
    t_borrow.start()
    assert borrow_entered.wait(timeout=5.0)

    t_drain = threading.Thread(target=_do_drain)
    t_drain.start()
    # While the borrow is still in-flight, the drain MUST NOT have returned.
    assert not drain_returned.wait(timeout=0.3), (
        "drain_and_release returned while a ladder borrow was still in-flight "
        "-- the old client's tokens-DB handle could still be open at rename time"
    )
    # New borrows during the drain window resolve None (-> yfinance), never the
    # released client.
    with holder.borrow() as c2:
        assert c2 is None

    # Let the in-flight borrow finish -> the drain unblocks + returns the client.
    release_borrow.set()
    assert drain_returned.wait(timeout=5.0)
    assert drained_value["v"] is sentinel
    t_borrow.join(timeout=5.0)
    t_drain.join(timeout=5.0)


def test_holder_drain_bounded_timeout_does_not_hang():
    """A pathologically stuck in-flight borrow must NOT hang the setup POST:
    ``drain_and_release`` returns after the bounded timeout (the rename then
    proceeds; a transient WinError is operator-retryable -- never a hang)."""
    sentinel = object()
    holder = _SchwabClientHolder(sentinel)
    stuck_borrow_entered = threading.Event()
    let_stuck_go = threading.Event()

    def _stuck_borrow():
        with holder.borrow():
            stuck_borrow_entered.set()
            let_stuck_go.wait(timeout=5.0)

    t = threading.Thread(target=_stuck_borrow)
    t.start()
    assert stuck_borrow_entered.wait(timeout=5.0)

    # Bounded timeout -> returns despite the still-in-flight borrow.
    returned = holder.drain_and_release(timeout=0.2)
    assert returned is sentinel  # the slot value is still returned for gc

    let_stuck_go.set()
    t.join(timeout=5.0)


def test_scope_bypass_yfinance_path_does_not_borrow_the_client(
    seeded_db, monkeypatch, tmp_path,
):
    """18-H.4.1 R3 MAJOR (Codex) -- the L9 scope-gate-bypass (yfinance-only) path
    must NOT count as an in-flight borrow. Otherwise a long yfinance fallback for
    a non-open-trade ticker would hold the Schwab client borrowed and could
    outlive the setup drain -> WinError 32 even though that path never touches the
    Schwab client.

    Drive the REAL installed bars hook for a ticker OUTSIDE open-trade scope and
    assert the shared holder's in-flight count is zero both DURING (probed via a
    monkeypatched yfinance fallback) and after the call.
    """
    import dataclasses

    from unittest.mock import MagicMock

    cfg, _ = seeded_db
    schwab = dataclasses.replace(
        cfg.integrations.schwab,
        environment="production", marketdata_ladder_enabled=True,
    )
    integ = dataclasses.replace(cfg.integrations, schwab=schwab)
    prod_cfg = dataclasses.replace(cfg, integrations=integ)

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "id-xxxx")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "secret-xxxx")
    monkeypatch.setattr(
        "swing.web.app.construct_authenticated_client", lambda *a, **k: MagicMock(),
    )

    # No open trades seeded -> should_use_schwab(ticker) is False -> the hook must
    # take the yfinance branch WITHOUT borrowing the client.
    app = create_app(prod_cfg)
    holder = app.state.schwab_client_holder
    assert holder is not None

    inflight_during = {}

    def _probe_yf_window(ticker, *, end_date, cache_dir, archive_history_days):
        # Probe the in-flight count from inside the yfinance fallback: it must be
        # 0 (the scope-bypass path did not borrow the client).
        inflight_during["n"] = holder._inflight
        import pandas as pd
        return pd.DataFrame(
            {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0],
             "Volume": [1]},
            index=pd.bdate_range(end=pd.Timestamp("2026-06-08"), periods=1),
        )

    monkeypatch.setattr(
        "swing.data.ohlcv_archive.read_or_fetch_archive", _probe_yf_window,
    )
    monkeypatch.setattr(
        "swing.evaluation.dates.last_completed_session",
        lambda _n: __import__("datetime").date(2026, 6, 8),
    )

    _bars, provider = app.state.ohlcv_cache._ladder_bars_fetcher("ZZZ")  # not open
    assert provider == "yfinance"
    assert inflight_during.get("n") == 0, (
        "scope-bypass yfinance path borrowed the Schwab client (in-flight "
        f"count={inflight_during.get('n')}) -- it would outlive the setup drain"
    )
    assert holder._inflight == 0


def test_drain_timeout_exceeds_configured_schwab_request_timeout(seeded_db):
    """18-H.4.1 R2 MAJOR (Codex) -- the release drain wait MUST outlive a routine
    in-flight Schwab call. Source it from the configured Schwab request timeout +
    a margin so a normal slow ladder fetch always finishes before the drain
    expires (a hard-coded sub-timeout would let a routine slow request keep the
    tokens-DB handle open past the release -> WinError 32 survives)."""
    import dataclasses

    from swing.web.app import web_client_drain_timeout_seconds

    cfg, _ = seeded_db
    schwab_timeout = cfg.integrations.schwab.timeout_seconds
    drain_timeout = web_client_drain_timeout_seconds(cfg)
    # STRICTLY greater than the Schwab request timeout (a routine in-flight call
    # is bounded by schwab_timeout, so the drain wait outlives it).
    assert drain_timeout > schwab_timeout

    # Coupled: a larger configured Schwab timeout yields a larger drain timeout.
    schwab = dataclasses.replace(
        cfg.integrations.schwab, timeout_seconds=schwab_timeout + 120.0,
    )
    integ = dataclasses.replace(cfg.integrations, schwab=schwab)
    bigger_cfg = dataclasses.replace(cfg, integrations=integ)
    assert web_client_drain_timeout_seconds(bigger_cfg) > drain_timeout
    assert (
        web_client_drain_timeout_seconds(bigger_cfg)
        > bigger_cfg.integrations.schwab.timeout_seconds
    )
