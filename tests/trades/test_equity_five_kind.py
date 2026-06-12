import pytest

from swing.data.models import CashMovement
from swing.trades.equity import net_cash_movements


def _cm(kind, amount):
    return CashMovement(id=None, date="2026-06-01", kind=kind, amount=amount, ref=None, note=None)


def test_net_cash_movements_five_kinds():
    movements = [
        _cm("deposit", 100.0), _cm("withdraw", 25.0),
        _cm("interest", 3.0), _cm("dividend", 7.0), _cm("fee", 1.0),
    ]
    # +100 -25 +3 +7 -1 = 84
    assert net_cash_movements(movements) == pytest.approx(84.0)


def test_net_cash_movements_unknown_kind_raises():
    bogus = CashMovement.__new__(CashMovement)  # bypass __post_init__ to plant a bad kind
    object.__setattr__(bogus, "kind", "bogus")
    object.__setattr__(bogus, "amount", 5.0)
    with pytest.raises(ValueError, match="unknown cash kind"):
        net_cash_movements([bogus])
