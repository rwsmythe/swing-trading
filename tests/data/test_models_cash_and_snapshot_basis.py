import pytest

from swing.data.models import AccountEquitySnapshot, CashMovement


@pytest.mark.parametrize("kind", ["deposit", "withdraw", "interest", "dividend", "fee"])
def test_cashmovement_accepts_five_kinds(kind):
    CashMovement(id=None, date="2026-06-01", kind=kind, amount=1.0, ref=None, note=None)


def test_cashmovement_rejects_unknown_kind():
    with pytest.raises(ValueError, match="kind"):
        CashMovement(id=None, date="2026-06-01", kind="bogus", amount=1.0, ref=None, note=None)


@pytest.mark.parametrize("bad", ["6/1/26", "2026-6-01", "abcd-ef-gh", "2026-13-40", "2026/06/01"])
def test_cashmovement_rejects_non_iso_date(bad):
    # Must mirror the migration-0029 SQL GLOB (digit shape) AND reject
    # calendar-invalid -- every value here would either fail the GLOB or be a
    # raw IntegrityError if it slipped through (Codex R1 MAJOR).
    with pytest.raises(ValueError, match="date"):
        CashMovement(id=None, date=bad, kind="deposit", amount=1.0, ref=None, note=None)


def test_snapshot_basis_field_validates():
    s = AccountEquitySnapshot(
        snapshot_id=None, snapshot_date="2026-06-01", equity_dollars=100.0,
        source="schwab_api", source_artifact_path=None,
        recorded_at="2026-06-01T00:00:00", recorded_by="op", notes=None,
        basis="net_liq")
    assert s.basis == "net_liq"
    with pytest.raises(ValueError, match="basis"):
        AccountEquitySnapshot(
            snapshot_id=None, snapshot_date="2026-06-01", equity_dollars=100.0,
            source="schwab_api", source_artifact_path=None,
            recorded_at="2026-06-01T00:00:00", recorded_by="op", notes=None,
            basis="bogus")
