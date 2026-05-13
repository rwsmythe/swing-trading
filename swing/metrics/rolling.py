"""Rolling-N window helper — Class D foundation (plan §D Task A.5).

Presentation-agnostic helpers; the §A.7 ``render_class_d`` honesty
dispatcher consumes the per-window output of these helpers + applies the
spec §5.4 four-band rendering policy.

Hardcoded window size ``N`` is NOT enforced here (the helpers are generic);
spec §3.8 callsites in Sub-bundle E pass ``window_size=10`` per spec §8.5
lock.
"""

from __future__ import annotations

# Per plan §D Task A.5: ``rolling_mean_series`` suppresses windows with
# fewer than this many samples — separate from the honesty-policy spec
# §5.4 effective_n>=5 line-drawability threshold (which is applied at the
# render layer in ``render_class_d``). This 3-floor is the operational
# "don't render a noise-dominated mean" floor; the 5-floor is the
# statistical-confidence drawability floor.
_MIN_N_FOR_MEAN: int = 3


def rolling_window_samples(
    *,
    samples: list[float],
    window_size: int,
    step: int = 1,
) -> list[list[float]]:
    """Return a list of windows, one per emitted position.

    For position ``i`` in ``samples`` (with stride ``step``), the window is
    ``samples[max(0, i - window_size + 1) : i + 1]`` — i.e., the most-recent
    ``window_size`` samples up to and including position ``i``. Windows GROW
    until full at ``i >= window_size - 1``, then SLIDE.

    With ``step=1`` (the default), the result has one window per sample
    position. With ``step>1``, only every ``step``-th position emits.

    Raises:
        ValueError: when ``window_size <= 0`` or ``step <= 0``.
    """
    if window_size <= 0:
        raise ValueError(f"window_size must be > 0; got {window_size!r}")
    if step <= 0:
        raise ValueError(f"step must be > 0; got {step!r}")
    n = len(samples)
    windows: list[list[float]] = []
    for i in range(0, n, step):
        start = max(0, i - window_size + 1)
        windows.append(list(samples[start : i + 1]))
    return windows


def rolling_mean_series(
    *,
    samples: list[float],
    window_size: int,
) -> list[tuple[int, float | None]]:
    """Return ``[(i, mean_or_none)]`` for each sample position.

    Each entry is ``(i, mean(window))`` where ``window`` is the
    most-recent ``window_size`` samples up to ``i``. When the window has
    fewer than ``_MIN_N_FOR_MEAN`` samples (i.e., near the start), the
    mean is ``None`` (operational don't-render-noise-dominated-mean floor;
    DOES NOT replace the spec §5.4 effective_n>=5 line-drawability floor
    which is applied at the render layer).

    Raises:
        ValueError: when ``window_size <= 0``.
    """
    if window_size <= 0:
        raise ValueError(f"window_size must be > 0; got {window_size!r}")
    result: list[tuple[int, float | None]] = []
    for i, _ in enumerate(samples):
        start = max(0, i - window_size + 1)
        window = samples[start : i + 1]
        if len(window) < _MIN_N_FOR_MEAN:
            result.append((i, None))
        else:
            result.append((i, sum(window) / len(window)))
    return result
