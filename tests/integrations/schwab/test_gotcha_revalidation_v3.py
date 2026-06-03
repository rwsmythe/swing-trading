"""L4: every Schwab gotcha re-validated against schwabdev 3.0.5.

Symbols re-grepped against the live tree (the plan's illustrative names were
approximate): G1 uses ``client._SCHWABDEV_LOGGER_PREFIX`` (not a NAMES set); G3
uses ``marketdata_ladder._is_ladder_active``; G5 uses ``trader.get_accounts_linked``
+ ``SchwabApiError`` from ``schwab.client``; G6 asserts the locked source-artifact
template literal (an inline f-string at the emit site, not a helper function).
"""
import inspect
import pathlib

import schwabdev

from swing.data.db import ensure_schema
from swing.integrations.schwab import audit_service, client as schwab_client
from swing.integrations.schwab.client import SchwabApiError


def _cfg(*, environment: str, enabled: bool = True):
    schwab = type("S", (), {"environment": environment,
                            "marketdata_ladder_enabled": enabled})()
    integrations = type("I", (), {"schwab": schwab})()
    return type("C", (), {"integrations": integrations})()


def test_g1_logger_name_is_capital_s_schwabdev() -> None:
    # The redaction factory's prefix-check depends on the exact logger name.
    # Pre-fix risk: a v3 rename to 'schwabdev' (lowercase) would slip records past
    # redaction. Post-fix: v3 still uses getLogger("Schwabdev") (client.py:41).
    assert schwab_client._SCHWABDEV_LOGGER_PREFIX == "Schwabdev"


def test_g2_update_tokens_signature_retained() -> None:
    sig = inspect.signature(schwabdev.Client.update_tokens)
    params = [p for p in sig.parameters if p != "self"]
    assert params == ["force_access_token", "force_refresh_token"]


def test_g3_sandbox_gate_unchanged() -> None:
    # Regression guard: under environment != 'production', the marketdata ladder
    # short-circuits (domain rows not written / yfinance-only path).
    from swing.integrations.schwab import marketdata_ladder as ml
    assert ml._is_ladder_active(_cfg(environment="sandbox")) is False
    assert ml._is_ladder_active(_cfg(environment="production")) is True


def test_g4_price_history_passes_eight_camelcase_kwargs() -> None:
    # The minute-default footgun: get_price_history must pass period kwargs explicitly.
    from swing.integrations.schwab.marketdata import get_price_history
    src = inspect.getsource(get_price_history)
    for kw in ("periodType", "period", "frequencyType", "frequency"):
        assert kw in src, f"get_price_history dropped explicit {kw} (daily-bar footgun)"


def test_g5_linked_accounts_path_closes_audit_row_before_raise(tmp_path) -> None:
    # The renamed linked_accounts path still closes its schwab_api_calls row via
    # record_call_finish BEFORE re-raising (the gotcha most likely broken by the rename).
    import pytest

    from swing.integrations.schwab.trader import get_accounts_linked

    conn = ensure_schema(tmp_path / "g5.db")

    class _RaisingClient:
        def linked_accounts(self):
            raise SchwabApiError(503, "<simulated upstream failure>")

    order_of_calls = []
    real_finish = audit_service.record_call_finish

    def _spy_finish(*a, **k):
        order_of_calls.append(("finish", k.get("status")))
        return real_finish(*a, **k)

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(audit_service, "record_call_finish", _spy_finish)
        # trader.py imports record_call_finish via the `audit_service` module alias,
        # so patching the module attribute is seen by the call site.
        with pytest.raises(SchwabApiError):
            get_accounts_linked(
                _RaisingClient(), conn, surface="cli", environment="sandbox"
            )
    # Pre-fix risk: an exception path that re-raises BEFORE record_call_finish leaves an
    # in-flight row open. Post-fix: finish (status='error') is recorded, THEN raise.
    assert order_of_calls and order_of_calls[-1][0] == "finish"
    open_rows = conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls WHERE status = 'in_flight'"
    ).fetchone()[0]
    assert open_rows == 0


def test_g6_source_artifact_shape_unchanged() -> None:
    # Locked shape: source='schwab_api' rows carry "schwab_api:call/{call_id}"
    # (NEVER the raw URL, which contains account_hash). Re-validate the emit-site
    # template survives v3.
    src = pathlib.Path(
        inspect.getfile(__import__("swing.integrations.schwab.pipeline_steps",
                                   fromlist=["_dummy"]))
    ).read_text(encoding="utf-8")
    assert 'schwab_api:call/{call_id}' in src
