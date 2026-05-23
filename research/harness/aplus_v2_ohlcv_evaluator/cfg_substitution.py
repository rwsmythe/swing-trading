"""cfg substitution helper for the V2 OHLCV harness.

Substitutes one cfg field at a time via dataclasses.replace + returns a NEW
Config (immutable; original unchanged). The vcp.watch_max_fails variable is
NOT routed through this helper -- see spec §E.3 / OQ-11 special-case at
sweep.py.
"""
from __future__ import annotations

import dataclasses

from swing.config import Config

_KNOWN_SUBSECTIONS: frozenset[str] = frozenset(
    {"trend_template", "vcp", "risk", "rs"}
)


def substitute_cfg(
    cfg: Config,
    variable_name: str,
    sweep_value: float | int,
) -> Config:
    """Return a NEW Config with `variable_name` = `sweep_value`; other
    fields unchanged.

    Args:
      cfg: production cfg from Config.from_defaults() or operator's cfg.
      variable_name: dotted-path form "<sub>.<field>" where <sub> is one of
        {trend_template, vcp, risk, rs}.
      sweep_value: numeric value to substitute. Must match the field's
        expected type (int for additive variables; float for multiplicative).

    Raises:
      ValueError: when <sub> is not in {trend_template, vcp, risk, rs}
        (per Expansion #11 taxonomy discipline + cumulative
        "Literal[...] type hints are NOT runtime-enforced" gotcha).
    """
    sub, field_name = variable_name.split(".", 1)
    if sub not in _KNOWN_SUBSECTIONS:
        raise ValueError(
            f"substitute_cfg: unknown cfg subsection {sub!r}; "
            f"expected one of {sorted(_KNOWN_SUBSECTIONS)}"
        )
    sub_obj = getattr(cfg, sub)
    new_sub = dataclasses.replace(sub_obj, **{field_name: sweep_value})
    return dataclasses.replace(cfg, **{sub: new_sub})
