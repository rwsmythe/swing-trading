"""Pure-helper tests for swing.trades.review."""
import pytest

from swing.trades.review import (
    ALL_MISTAKE_TAGS, MISTAKE_TAGS,
    canonicalize_mistake_tags, validate_mistake_tags,
)


class TestMistakeTagsConstant:
    def test_six_categories(self) -> None:
        assert set(MISTAKE_TAGS.keys()) == {
            "entry", "risk", "management", "psychology", "reconciliation", "none",
        }

    def test_total_tag_count_is_34(self) -> None:
        assert len(ALL_MISTAKE_TAGS) == 34

    def test_specific_v12_section_710_tags(self) -> None:
        assert "CHASED" in MISTAKE_TAGS["entry"]
        assert "OVERSIZED" in MISTAKE_TAGS["risk"]
        assert "MOVED_STOP_AWAY" in MISTAKE_TAGS["management"]
        assert "REVENGE" in MISTAKE_TAGS["psychology"]
        assert "FILL_NOT_LOGGED" in MISTAKE_TAGS["reconciliation"]
        assert "none_observed" in MISTAKE_TAGS["none"]


class TestValidateMistakeTags:
    def test_valid_single_tag(self) -> None:
        validate_mistake_tags(["CHASED"])

    def test_valid_multi_category_combo(self) -> None:
        validate_mistake_tags(["CHASED", "FOMO"])

    def test_unknown_tag_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown mistake tag"):
            validate_mistake_tags(["NOT_A_REAL_TAG"])

    def test_none_observed_with_other_tag_raises(self) -> None:
        with pytest.raises(ValueError, match="none_observed"):
            validate_mistake_tags(["none_observed", "CHASED"])

    def test_only_none_observed_is_valid(self) -> None:
        validate_mistake_tags(["none_observed"])


class TestCanonicalizeMistakeTags:
    def test_dedup_and_sort(self) -> None:
        result = canonicalize_mistake_tags(["FOMO", "CHASED", "FOMO"])
        assert result == ["CHASED", "FOMO"]

    def test_strips_whitespace(self) -> None:
        result = canonicalize_mistake_tags(["  CHASED  ", " FOMO"])
        assert result == ["CHASED", "FOMO"]

    def test_nfc_unicode_normalize(self) -> None:
        import unicodedata
        nfd = unicodedata.normalize("NFD", "CHASED")
        result = canonicalize_mistake_tags([nfd])
        assert result == ["CHASED"]

    def test_empty_list_returns_empty(self) -> None:
        assert canonicalize_mistake_tags([]) == []


from swing.data.models import Exit, Trade
from swing.trades.review import (
    compute_actual_realized_R_effective,
    compute_lucky_violation_R, compute_max_drawdown_R, compute_mistake_cost_R,
    compute_profit_factor,
)


def _make_trade(*, id_: int, status: str = "closed",
                state: str = "closed",
                initial_shares: int = 10) -> Trade:
    return Trade(
        id=id_, ticker=f"T{id_}", entry_date="2026-01-01",
        entry_price=10.0, initial_shares=initial_shares, initial_stop=9.0,
        current_stop=9.0, status=status, state=state,
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
    )


def _make_exit(*, trade_id: int, r: float, shares: int = 10,
               exit_date: str = "2026-02-01") -> Exit:
    return Exit(
        id=None, trade_id=trade_id, exit_date=exit_date,
        exit_price=11.0, shares=shares, reason="manual",
        realized_pnl=r * 10.0, r_multiple=r, notes=None,
    )


class TestCostAndLucky:
    @pytest.mark.parametrize(
        "plan,actual,expected_cost,expected_lucky",
        [
            (2.0, 0.5, 1.5, 0.0),    # cost
            (0.5, 2.0, 0.0, 1.5),    # lucky
            (1.0, 1.0, 0.0, 0.0),    # equal
            (None, 1.5, 0.0, 0.0),   # no plan
            (-0.5, -2.0, 1.5, 0.0),  # both losses; planned loss less than actual
            (-2.0, -0.5, 0.0, 1.5),  # both losses; actual loss less than planned (lucky)
        ],
    )
    def test_cost_and_lucky_table(
        self, plan: float | None, actual: float,
        expected_cost: float, expected_lucky: float,
    ) -> None:
        assert compute_mistake_cost_R(
            realized_R_if_plan_followed=plan,
            actual_realized_R_effective=actual,
        ) == pytest.approx(expected_cost)
        assert compute_lucky_violation_R(
            realized_R_if_plan_followed=plan,
            actual_realized_R_effective=actual,
        ) == pytest.approx(expected_lucky)

    @pytest.mark.parametrize(
        "plan,actual",
        [(2.0, 0.5), (0.5, 2.0), (1.0, 1.0), (None, 1.5),
         (-0.5, -2.0), (-2.0, -0.5)],
    )
    def test_cost_and_lucky_never_both_positive(
        self, plan: float | None, actual: float,
    ) -> None:
        cost = compute_mistake_cost_R(
            realized_R_if_plan_followed=plan,
            actual_realized_R_effective=actual,
        )
        lucky = compute_lucky_violation_R(
            realized_R_if_plan_followed=plan,
            actual_realized_R_effective=actual,
        )
        assert not (cost > 0 and lucky > 0), \
            f"cost={cost} and lucky={lucky} both positive — invariant violated"


class TestComputeActualR:
    def test_share_weighted_full_exit(self) -> None:
        t = _make_trade(id_=1, initial_shares=10)
        ex = [_make_exit(trade_id=1, r=2.0, shares=10)]
        assert compute_actual_realized_R_effective(t, ex) == pytest.approx(2.0)

    def test_share_weighted_partial(self) -> None:
        t = _make_trade(id_=1, initial_shares=10)
        ex = [
            _make_exit(trade_id=1, r=1.0, shares=5, exit_date="2026-02-01"),
            _make_exit(trade_id=1, r=3.0, shares=5, exit_date="2026-02-15"),
        ]
        assert compute_actual_realized_R_effective(t, ex) == pytest.approx(2.0)

    def test_skips_other_trades(self) -> None:
        t = _make_trade(id_=1, initial_shares=10)
        ex = [
            _make_exit(trade_id=1, r=1.0, shares=10),
            _make_exit(trade_id=99, r=5.0, shares=10),
        ]
        assert compute_actual_realized_R_effective(t, ex) == pytest.approx(1.0)


class TestProfitFactor:
    def test_basic_two_trades(self) -> None:
        trades = [_make_trade(id_=1), _make_trade(id_=2)]
        exits = [_make_exit(trade_id=1, r=2.0), _make_exit(trade_id=2, r=-1.0)]
        assert compute_profit_factor(trades, exits) == pytest.approx(2.0)

    def test_no_losses_returns_none(self) -> None:
        trades = [_make_trade(id_=1)]
        exits = [_make_exit(trade_id=1, r=1.0)]
        assert compute_profit_factor(trades, exits) is None

    def test_no_wins_returns_zero(self) -> None:
        trades = [_make_trade(id_=1), _make_trade(id_=2)]
        exits = [_make_exit(trade_id=1, r=-1.0), _make_exit(trade_id=2, r=-2.0)]
        assert compute_profit_factor(trades, exits) == pytest.approx(0.0)

    def test_empty_input(self) -> None:
        assert compute_profit_factor([], []) is None


class TestMaxDrawdown:
    def test_no_drawdown(self) -> None:
        trades = [_make_trade(id_=i) for i in (1, 2, 3)]
        exits = [
            _make_exit(trade_id=1, r=1.0, exit_date="2026-01-10"),
            _make_exit(trade_id=2, r=1.0, exit_date="2026-01-20"),
            _make_exit(trade_id=3, r=1.0, exit_date="2026-01-30"),
        ]
        assert compute_max_drawdown_R(trades, exits) == pytest.approx(0.0)

    def test_simple_drawdown(self) -> None:
        trades = [_make_trade(id_=1), _make_trade(id_=2)]
        exits = [
            _make_exit(trade_id=1, r=2.0, exit_date="2026-01-10"),
            _make_exit(trade_id=2, r=-3.0, exit_date="2026-01-20"),
        ]
        assert compute_max_drawdown_R(trades, exits) == pytest.approx(3.0)

    def test_recovers_then_new_peak(self) -> None:
        trades = [_make_trade(id_=i) for i in (1, 2, 3)]
        exits = [
            _make_exit(trade_id=1, r=1.0, exit_date="2026-01-10"),
            _make_exit(trade_id=2, r=-2.0, exit_date="2026-01-20"),
            _make_exit(trade_id=3, r=3.0, exit_date="2026-01-30"),
        ]
        assert compute_max_drawdown_R(trades, exits) == pytest.approx(2.0)

    def test_empty_input(self) -> None:
        assert compute_max_drawdown_R([], []) == pytest.approx(0.0)


from swing.trades.review import compute_process_grade


class TestComputeProcessGrade:
    """Parameterized table covering F-floor, disqualifying-D, weighted boundaries."""

    @pytest.mark.parametrize(
        "entry,management,exit_,disqualifying,expected",
        [
            # F-floor: any single F → F regardless of other stages
            ("A", "A", "F", False, "F"),
            ("A", "F", "A", False, "F"),
            ("F", "A", "A", False, "F"),
            ("F", "F", "F", False, "F"),
            # F-floor beats disqualifying-D cap (F is harder)
            ("A", "A", "F", True, "F"),
            ("F", "A", "A", True, "F"),
            # Disqualifying-D cap with no F stages
            ("A", "A", "A", True, "D"),
            ("B", "B", "B", True, "D"),
            ("C", "C", "C", True, "D"),
            ("D", "D", "D", True, "D"),
            # Weighted-numeric boundaries (no F, no disqualifying)
            ("A", "A", "A", False, "A"),  # weighted = 4.0 → A
            ("A", "B", "B", False, "B"),  # weighted = 0.40*4 + 0.35*3 + 0.25*3 = 3.40 → B
            ("B", "B", "B", False, "B"),  # weighted = 3.0 → B
            ("B", "C", "B", False, "C"),  # weighted = 0.40*3 + 0.35*2 + 0.25*3 = 2.65 → C
            ("C", "C", "C", False, "C"),  # weighted = 2.0 → C
            ("D", "D", "D", False, "D"),  # weighted = 1.0 → D
            # B/B/A: 0.40*3 + 0.35*3 + 0.25*4 = 1.20 + 1.05 + 1.00 = 3.25 → B
            ("B", "B", "A", False, "B"),
            # A/B/A: 0.40*4 + 0.35*3 + 0.25*4 = 1.60 + 1.05 + 1.00 = 3.65 → A
            ("A", "B", "A", False, "A"),
        ],
    )
    def test_process_grade_table(
        self, entry: str, management: str, exit_: str,
        disqualifying: bool, expected: str,
    ) -> None:
        assert compute_process_grade(
            entry=entry, management=management, exit_=exit_,
            disqualifying=disqualifying,
        ) == expected
