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


def test_first_row_ticker_change_does_NOT_change_hash() -> None:
    """THE FIX (signature-provenance): the #1 result ticker is volatile -- it
    drifts as the market moves -- so a top-ticker change MUST NOT change the
    signature. Pre-fix the hashed payload carried a `first_row` [Ticker, Sector,
    Industry] tuple, so this DIFFERED (the false 'operator edited the screen'
    warning on routine result drift); post-fix only the canonicalized
    column_set is hashed -> SAME.

    Non-tautological (per feedback_verify_regression_test_arithmetic): the
    discriminating axis is first_row insensitivity. Under the OLD basis
    json{column_set, first_row=[GOOG,..]} != json{column_set, first_row=
    [AAPL,..]}; under the NEW basis json{column_set} == json{column_set}."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(b"1,AAPL,", b"1,GOOG,")
    h_alt = c.compute_signature_hash(altered)
    assert h_base == h_alt


def test_first_row_sector_change_does_NOT_change_hash() -> None:
    """Companion to the ticker case: a first-row Sector/Industry change is also
    result drift (the screen DEFINITION is unchanged) -> SAME hash post-fix.
    Pre-fix the `first_row` tuple carried Sector/Industry, so this DIFFERED."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(
        b"1,AAPL,Technology,Software,USA,100,1%,1000,1,1,200,50,1B\n",
        b"1,AAPL,Healthcare,Biotech,USA,100,1%,1000,1,1,200,50,1B\n",
    )
    assert c.compute_signature_hash(altered) == h_base


def test_second_row_change_does_NOT_change_hash() -> None:
    """Tail-row mutations stay silent -- now because the signature reflects ONLY
    the column_set (EVERY result row is excluded), not merely because the hash
    was first-row-only. Pin behavior so a future hash-payload change is caught."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    altered = _BASE.replace(b"2,MSFT,", b"2,NVDA,")
    assert c.compute_signature_hash(altered) == h_base


def test_row_order_does_NOT_change_hash() -> None:
    """Re-baselined: pre-fix swapping the data rows changed WHICH row was the
    `first_row`, so the hash DIFFERED; post-fix only the column_set is hashed,
    so row order is irrelevant -> SAME."""
    c = _client()
    h_base = c.compute_signature_hash(_BASE)
    swapped = (
        b"No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        b"2,MSFT,Technology,Software,USA,200,1%,1000,1,1,250,80,2B\n"
        b"1,AAPL,Technology,Software,USA,100,1%,1000,1,1,200,50,1B\n"
    )
    assert c.compute_signature_hash(swapped) == h_base


def test_signature_reflects_only_column_set() -> None:
    """Strongest fix assertion: a full result table hashes IDENTICALLY to its
    header-only equivalent (no data rows at all). Pre-fix _BASE carried
    first_row=[AAPL, Technology, Software] vs header-only first_row=[] -> the
    hashes DIFFERED; post-fix both reduce to json{column_set} -> SAME."""
    c = _client()
    header_only = (
        b"No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
    )
    assert c.compute_signature_hash(_BASE) == c.compute_signature_hash(header_only)


def test_empty_body_uses_sentinel() -> None:
    """A header-less body (no non-blank rows) returns the sha256 of the
    `<empty>` sentinel -- preserved verbatim through the fix."""
    import hashlib

    c = _client()
    expected = hashlib.sha256(b"<empty>").hexdigest()
    assert c.compute_signature_hash(b"") == expected
    assert c.compute_signature_hash(b"\n\n") == expected


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
