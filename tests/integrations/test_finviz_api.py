import pytest

from swing.config import Config, FinvizIntegrationConfig, IntegrationsConfig
from swing.integrations.finviz_api import (
    FinvizApiError,
    FinvizClient,
    FinvizConfigMissingError,
    FinvizRateLimitError,
    FinvizSchemaParityError,
)


def _cfg_with(
    token: str = "test-sentinel-token",
    screen_query: str = "v=152&f=cap_largeover",
    timeout: int = 30,
) -> Config:
    """Construct a minimal Config-shaped object for FinvizClient.

    FinvizClient consumes only cfg.integrations.finviz; we don't need a full Config.
    """
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _IntegrationsStub:
        finviz: FinvizIntegrationConfig

    @dataclass(frozen=True)
    class _CfgStub:
        integrations: _IntegrationsStub

    return _CfgStub(
        integrations=_IntegrationsStub(
            finviz=FinvizIntegrationConfig(
                token=token, screen_query=screen_query, timeout_seconds=timeout
            ),
        ),
    )  # type: ignore[return-value]


def test_finviz_client_raises_when_token_missing() -> None:
    cfg = _cfg_with(token="", screen_query="v=152")
    with pytest.raises(FinvizConfigMissingError) as ei:
        FinvizClient(cfg).fetch_screen()
    assert "token" in str(ei.value).lower()


def test_finviz_client_raises_when_screen_query_missing() -> None:
    cfg = _cfg_with(token="abc", screen_query="")
    with pytest.raises(FinvizConfigMissingError) as ei:
        FinvizClient(cfg).fetch_screen()
    assert "screen_query" in str(ei.value).lower()


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_happy_path() -> None:
    """Cassette replay; auth query-param redacted at record-time."""
    cfg = _cfg_with(token="test-sentinel-token", screen_query="v=152&f=cap_largeover")
    body = FinvizClient(cfg).fetch_screen()
    assert isinstance(body, bytes)
    first_line = body.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    assert "Ticker" in first_line
    assert "Sector" in first_line


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_normalize_to_canonical_csv_passes_existing_validator(tmp_path) -> None:
    """End-to-end: API response body → canonical 13-column CSV → existing
    finviz_schema validator accepts it."""
    from swing.pipeline.finviz_schema import REQUIRED_COLUMNS, validate_csv

    cfg = _cfg_with(token="test-sentinel-token", screen_query="v=152&f=cap_largeover")
    client = FinvizClient(cfg)
    body = client.fetch_screen()
    canonical_text = client.normalize_to_canonical_csv(body)
    csv_path = tmp_path / "finviz5May2026.csv"
    csv_path.write_text(canonical_text, encoding="utf-8")
    result = validate_csv(csv_path)
    assert result.is_valid, result.reasons
    assert result.reasons == []
    assert result.row_count > 0

    header = canonical_text.split("\n", 1)[0]
    columns = [c.strip() for c in header.split(",")]
    assert tuple(columns) == REQUIRED_COLUMNS, columns


def test_normalize_raises_on_missing_column(tmp_path) -> None:
    """Discriminating: API returns body without 'Ticker'; raise SchemaParityError."""
    cfg = _cfg_with()
    body = b"No.,Sector,Industry\n1,Tech,Software\n"
    with pytest.raises(FinvizSchemaParityError) as ei:
        FinvizClient(cfg).normalize_to_canonical_csv(body)
    assert "Ticker" in str(ei.value)


def test_normalize_raises_on_excessive_rows(tmp_path) -> None:
    """Discriminating: 5001 rows triggers safety bound; 4999 rows do not."""
    cfg = _cfg_with()
    header = (
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
    )
    row = "1,AAPL,Tech,Software,USA,100,1%,1000,1,1,200,50,1B\n"
    big = (header + row * 5001).encode()
    with pytest.raises(FinvizSchemaParityError) as ei:
        FinvizClient(cfg).normalize_to_canonical_csv(big)
    assert "5000" in str(ei.value) or "exceeds" in str(ei.value).lower()

    small = (header + row * 4999).encode()
    out = FinvizClient(cfg).normalize_to_canonical_csv(small)
    assert out.count("\n") == 5000  # 1 header + 4999 data rows = 5000 newlines


def test_signature_hash_deterministic_across_runs() -> None:
    """Discriminating: same input → same hash on repeated invocation."""
    cfg = _cfg_with()
    body = (
        b"No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        b"Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        b"1,AAPL,Tech,Software,USA,100,1%,1000,1,1,200,50,1B\n"
        b"2,MSFT,Tech,Software,USA,200,1%,1000,1,1,250,80,2B\n"
    )
    client = FinvizClient(cfg)
    assert client.compute_signature_hash(body) == client.compute_signature_hash(body)


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_500_raises_FinvizApiError() -> None:
    cfg = _cfg_with()
    with pytest.raises(FinvizApiError) as ei:
        FinvizClient(cfg).fetch_screen()
    assert ei.value.status_code == 500
    assert not isinstance(ei.value, FinvizRateLimitError)


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_403_raises_FinvizApiError() -> None:
    cfg = _cfg_with()
    with pytest.raises(FinvizApiError) as ei:
        FinvizClient(cfg).fetch_screen()
    assert ei.value.status_code == 403
    assert "test-sentinel-token" not in str(ei.value)


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_429_with_retry_after_retries_once_and_succeeds(monkeypatch) -> None:
    """Cassette double-interaction: first response 429 + Retry-After: 1; second response 200."""
    monkeypatch.setattr("swing.integrations.finviz_api.time.sleep", lambda *_: None)
    cfg = _cfg_with()
    body = FinvizClient(cfg).fetch_screen()
    assert b"Ticker" in body


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_429_with_oversized_retry_after_raises_FinvizRateLimitError() -> None:
    """Cassette: response 429 + Retry-After: 999."""
    cfg = _cfg_with()
    with pytest.raises(FinvizRateLimitError):
        FinvizClient(cfg).fetch_screen()


@pytest.mark.vcr(filter_query_parameters=["auth"])
def test_fetch_screen_429_then_429_raises_FinvizRateLimitError(monkeypatch) -> None:
    """Cassette double-interaction: both responses 429."""
    monkeypatch.setattr("swing.integrations.finviz_api.time.sleep", lambda *_: None)
    cfg = _cfg_with()
    with pytest.raises(FinvizRateLimitError):
        FinvizClient(cfg).fetch_screen()


def test_fetch_screen_network_error_raises_FinvizApiError(monkeypatch) -> None:
    """No cassette; monkeypatch requests.get to raise."""
    cfg = _cfg_with()

    def _raise(*args, **kwargs):
        import requests

        raise requests.ConnectionError("DNS failure simulated")

    monkeypatch.setattr("swing.integrations.finviz_api.requests.get", _raise)
    with pytest.raises(FinvizApiError) as ei:
        FinvizClient(cfg).fetch_screen()
    assert ei.value.status_code == 0
    assert "test-sentinel-token" not in str(ei.value)
