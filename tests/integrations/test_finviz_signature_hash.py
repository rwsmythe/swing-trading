import pytest

from swing.config import FinvizIntegrationConfig
from swing.integrations.finviz_api import FinvizClient


def _client():
    from dataclasses import dataclass
    @dataclass(frozen=True)
    class _Stub:
        finviz: FinvizIntegrationConfig
    @dataclass(frozen=True)
    class _Cfg:
        integrations: _Stub
    return FinvizClient(_Cfg(integrations=_Stub(  # type: ignore[arg-type]
        finviz=FinvizIntegrationConfig(token="x", screen_query="y", timeout_seconds=30),
    )))


_BASE = (
    b"No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
    b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
    b"1,AAPL,Technology,Software,USA,100,1%,1000,1,1,200,50,1B\n"
    b"2,MSFT,Technology,Software,USA,200,1%,1000,1,1,250,80,2B\n"
)


def test_same_input_same_hash() -> None:
    c = _client()
    h1 = c.compute_signature_hash(_BASE)
    h2 = c.compute_signature_hash(_BASE)
    assert h1 == h2
    assert len(h1) == 64
    assert all(ch in "0123456789abcdef" for ch in h1)


def test_column_added_changes_hash() -> None:
    """Discriminating: removing the 'Country' column changes the hash."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(
        b"Sector,Industry,Country,",
        b"Sector,Industry,",
    ).replace(b",USA,", b",")
    h_alt = c.compute_signature_hash(altered)
    assert h_base != h_alt


def test_first_row_ticker_change_changes_hash() -> None:
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(b"1,AAPL,", b"1,GOOG,")
    h_alt = c.compute_signature_hash(altered)
    assert h_base != h_alt


def test_first_row_sector_change_changes_hash() -> None:
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(
        b"1,AAPL,Technology,Software,USA,100,1%,1000,1,1,200,50,1B\n",
        b"1,AAPL,Healthcare,Biotech,USA,100,1%,1000,1,1,200,50,1B\n",
    )
    assert c.compute_signature_hash(altered) != h_base


def test_second_row_change_does_NOT_change_hash() -> None:
    """Discriminating: signature is FIRST-ROW only; tail mutations are silent.

    This is by design (locked §2.3 step 5: signature_hash = first_row tuple).
    Trade-off: full-table-drift detection requires a heavier hash; out-of-V1
    scope. Pin behavior here so a future change to the hash payload is caught."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(b"2,MSFT,", b"2,NVDA,")
    assert c.compute_signature_hash(altered) == h_base


def test_row_order_matters_for_signature() -> None:
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    swapped = (
        b"No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        b"2,MSFT,Technology,Software,USA,200,1%,1000,1,1,250,80,2B\n"
        b"1,AAPL,Technology,Software,USA,100,1%,1000,1,1,200,50,1B\n"
    )
    assert c.compute_signature_hash(swapped) != h_base


def test_column_order_does_NOT_affect_hash() -> None:
    """Column-set is sorted before hashing, so column-order swap → same hash."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered_header = (
        b"No.,Ticker,Industry,Sector,Country,Price,Change,Average Volume,"
        b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        b"1,AAPL,Software,Technology,USA,100,1%,1000,1,1,200,50,1B\n"
        b"2,MSFT,Software,Technology,USA,200,1%,1000,1,1,250,80,2B\n"
    )
    assert c.compute_signature_hash(altered_header) == h_base
