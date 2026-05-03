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
