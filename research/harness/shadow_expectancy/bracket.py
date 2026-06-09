from __future__ import annotations


def price_stop_fill(arm: str, *, stop: float, bar_open: float) -> float:
    """Spec 5.6 price-level stop fill. realistic = min(stop, open) (gap-down
    realizes the >1R loss); favorable_reprice = stop exactly."""
    if arm == "realistic":
        return min(stop, bar_open)
    if arm == "favorable_reprice":
        return stop
    raise ValueError(f"unknown bracket arm: {arm!r}")


def ma_exit_fill(arm: str, *, signal_close: float, next_open: float) -> float:
    """Spec 5.6 close-below-MA trail fill. realistic = next-session open;
    favorable_reprice = max(signal_close, next_open) (non-executable upper bound)."""
    if arm == "realistic":
        return next_open
    if arm == "favorable_reprice":
        return max(signal_close, next_open)
    raise ValueError(f"unknown bracket arm: {arm!r}")
