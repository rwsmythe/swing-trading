from swing.data.models import FAILURE_MODES
from swing.trades.review import (
    FAILURE_MODE_DISPLAY,
    failure_mode_display_choices,
    failure_mode_label,
)


def test_display_values_match_vocabulary_exactly() -> None:
    # The display set and the validation set must never drift.
    assert {v for v, _ in FAILURE_MODE_DISPLAY} == FAILURE_MODES


def test_display_order_is_deterministic_and_complete() -> None:
    choices = failure_mode_display_choices()
    assert isinstance(choices, tuple) and len(choices) == 7
    assert choices[0] == ("thesis_invalidated", "Thesis invalidated")
    # Every label is plain ASCII (the form is rendered; the CLI echo is cp1252).
    for value, label in choices:
        assert label.isascii(), f"non-ASCII label for {value!r}: {label!r}"


def test_label_lookup() -> None:
    assert failure_mode_label("execution_error") == "Execution error"
    assert failure_mode_label(None) is None
    assert failure_mode_label("unknown_token") == "unknown_token"  # passthrough
