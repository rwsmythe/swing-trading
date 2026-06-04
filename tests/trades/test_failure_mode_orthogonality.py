import inspect

from swing.data.models import FAILURE_MODES
from swing.trades.review import (
    ALL_MISTAKE_TAGS,
    MISTAKE_TAGS,
    compute_process_grade,
)


def test_failure_mode_does_not_feed_process_grade() -> None:
    # The grade measures execution quality; the failure mode measures outcome
    # cause. They are deliberately decoupled -- no failure_mode parameter.
    assert "failure_mode" not in inspect.signature(compute_process_grade).parameters


def test_failure_mode_vocabulary_is_disjoint_from_mistake_tags() -> None:
    # failure_mode is NOT a mistake tag. Disjoint token sets prove the
    # computational separation at the vocabulary level.
    assert FAILURE_MODES.isdisjoint(ALL_MISTAKE_TAGS)
    flat = {t for tags in MISTAKE_TAGS.values() for t in tags}
    assert FAILURE_MODES.isdisjoint(flat)
