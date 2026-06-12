from swing.trades.reconciliation_validators import _CASH_MOVEMENT_KINDS


def test_validator_kinds_widened_to_five():
    assert set(_CASH_MOVEMENT_KINDS) == {
        "deposit", "withdraw", "interest", "dividend", "fee"}
