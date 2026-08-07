"""`[latches]` -- the four item-3b calibrations (RD OQ-9 / OQ-10, 2026-08-06).

Every one of these knobs can be wrong in a way that is SILENT: a value that
looks armed and is not, a floor that disables the rule forever, an arm flag a
loose loader coerces to True. Each test below names the wrong value it refuses
and what that value would have done.
"""
from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path

import pytest

from swing.config import LatchesConfig
from swing.latches.constants import (
    DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR,
    DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT,
    DEFAULT_CRITERIA_LAPSE_SESSIONS,
)

_TRACKED_TOML = Path(__file__).resolve().parents[2] / "swing.config.toml"


def test_the_defaults_are_the_ruled_literals():
    """T5.0a. Mirror-to-mirror equality alone passes when BOTH mirrors move
    together, so a synchronized drift to 1.5 / 5.0 would go unnoticed while
    every T4 test -- which passes explicit arguments -- stayed green.

    RD ruled `5` (one trading week, and he said plainly he cannot derive it),
    `1.0` x the fire's own ADR, and `2.0`% of the latched pivot. Under the
    report-only framing these are calibration STARTING POINTS to be measured,
    not answers -- which is exactly why they must not drift unobserved.
    """
    cfg = LatchesConfig()
    assert cfg.criteria_lapse_armed is False        # OQ-9: DEFAULT OFF
    assert cfg.criteria_lapse_sessions == 5
    assert cfg.criteria_lapse_min_widening_adr == 1.0
    assert cfg.criteria_lapse_min_widening_pct == 2.0


def test_all_three_module_defaults_mirror_the_dataclass():
    """T5.0. The pure derivation carries module-level defaults for its
    signature; production passes `cfg.latches`. An earlier draft pinned only N,
    so either materiality default could drift from its dataclass while the pure
    derivation silently used a different floor from production."""
    cfg = LatchesConfig()
    assert DEFAULT_CRITERIA_LAPSE_SESSIONS == cfg.criteria_lapse_sessions
    assert (DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR
            == cfg.criteria_lapse_min_widening_adr)
    assert (DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT
            == cfg.criteria_lapse_min_widening_pct)


def test_the_tracked_toml_carries_every_key_EXPLICITLY():
    """T5.1 -- THE THIRD MIRROR, and the reason this test parses raw TEXT.

    Production loads `swing.config.toml`, not the dataclass. Comparing the
    LOADED values against the dataclass defaults CANNOT FAIL: if the `[latches]`
    block -- or just one key -- is absent, `load()` supplies those very defaults
    and the comparison passes over the exact missing-mirror defect it claims to
    catch. So this parses the file and asserts every field of `LatchesConfig` is
    present as a key with a value equal to its default.

    Iterating `dataclasses.fields` rather than listing four names is what makes
    a FIFTH knob join the pin automatically.
    """
    raw = tomllib.loads(_TRACKED_TOML.read_text(encoding="utf-8"))
    section = raw.get("latches")
    assert section is not None, "swing.config.toml is missing [latches]"
    for f in dataclasses.fields(LatchesConfig):
        assert f.name in section, f"[latches] is missing {f.name}"
        assert section[f.name] == getattr(LatchesConfig(), f.name), f.name


def test_a_config_without_a_latches_section_still_loads(tmp_path, sample_config):
    """T5.3. `[latches]` is NOT in `required_sections`, so every existing
    config file keeps loading -- the additive pattern `web`/`classifier`/
    `archive` already use. (And it is what makes T5.1's raw-text form
    necessary: the section being optional is precisely why a loaded-value
    comparison cannot detect its absence.)"""
    assert sample_config.latches == LatchesConfig()


class TestTheInertConfigurationFamily:
    """T5.4 -- one assertion each, and each names the silent failure it stops."""

    def test_N_of_1_is_rejected(self):
        # 2b compares first(B) with last(B); at N=1 they are the SAME bar, so
        # the conjunct is unsatisfiable and the whole feature is inert with no
        # error anywhere.
        with pytest.raises(ValueError):
            LatchesConfig(criteria_lapse_sessions=1)

    def test_a_fractional_N_is_rejected(self):
        # Discriminator: a bare `< 2` check ACCEPTS 2.5, and the derivation's
        # int() then silently truncates it to 2 -- a config value that does not
        # mean what it says.
        with pytest.raises(ValueError):
            LatchesConfig(criteria_lapse_sessions=2.5)

    def test_a_bool_N_is_rejected(self):
        # Discriminator: bool IS an int in Python, so True passes every numeric
        # comparison and configures N = 1.
        with pytest.raises(ValueError):
            LatchesConfig(criteria_lapse_sessions=True)

    @pytest.mark.parametrize("name", [
        "criteria_lapse_min_widening_adr", "criteria_lapse_min_widening_pct"])
    @pytest.mark.parametrize("bad", [
        float("inf"), float("nan"), 0, -1, True, "1.0", None])
    def test_a_non_finite_or_non_positive_floor_term_is_rejected(self, name, bad):
        # `inf` satisfies `> 0` and disables the lapse FOREVER, silently. Every
        # ordered comparison against `nan` is False, so a `> 0` guard admits it
        # too -- the same hole `zone_cap_for_pivot`'s docstring records.
        with pytest.raises(ValueError):
            LatchesConfig(**{name: bad})

    @pytest.mark.parametrize("bad", [1, 0, "false", "true", "no", None, 1.0])
    def test_the_arm_flag_rejects_every_non_bool(self, bad):
        """The one configuration error whose blast radius is a WITHDRAWN
        MANDATE. A loader coercing `1` or the string `"false"` could silently
        ARM the terminal while every other test here stayed green."""
        with pytest.raises(ValueError):
            LatchesConfig(criteria_lapse_armed=bad)

    def test_the_valid_shapes_are_accepted(self):
        """The paired positive case -- without it a validator that rejected
        EVERYTHING would pass every assertion above."""
        cfg = LatchesConfig(
            criteria_lapse_armed=True, criteria_lapse_sessions=7,
            criteria_lapse_min_widening_adr=1.5,
            criteria_lapse_min_widening_pct=0.5)
        assert cfg.criteria_lapse_armed is True
        assert cfg.criteria_lapse_sessions == 7
