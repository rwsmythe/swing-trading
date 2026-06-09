from __future__ import annotations


class ShadowExpectancyError(Exception):
    """Base class for all shadow_expectancy harness errors."""


class InvalidLogStructureError(ShadowExpectancyError):
    """The temporal log violated a structural invariant the harness relies on."""
