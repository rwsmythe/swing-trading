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

from fastapi.testclient import TestClient

from swing.web.app import create_app


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

    Using ``__del__`` (rather than the stub merely inspecting app.state) is
    deliberate: it proves the fix actually DROPS the reference + collects, the
    same mechanism that releases the real schwabdev SQLite handle (the
    project's documented ``del client; gc.collect()`` release dance). A fix
    that set ``app.state.schwab_client = None`` but kept a live reference
    elsewhere would NOT finalize the object and the test would still fail.
    """

    locked = False

    def __init__(self) -> None:
        _StubLockingClient.locked = True

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
    # The reconstruction reuses the EXISTING factory; stub it at the route
    # module's import site so we can assert app.state is repopulated without
    # a live schwabdev construction.
    monkeypatch.setattr(
        schwab_route, "_construct_web_schwab_client", _stub_reconstruct,
        raising=False,
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
    monkeypatch.setattr(
        schwab_route, "_construct_web_schwab_client", lambda _cfg: None,
        raising=False,
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
    monkeypatch.setattr(
        schwab_route, "_construct_web_schwab_client", lambda _cfg: None,
        raising=False,
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
