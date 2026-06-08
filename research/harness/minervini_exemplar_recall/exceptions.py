# research/harness/minervini_exemplar_recall/exceptions.py
from __future__ import annotations


class MinerviniRecallError(Exception):
    """Base class for all minervini_exemplar_recall harness errors."""


class TiingoArchiveMissingError(MinerviniRecallError):
    """The Tiingo CSV for a symbol does not exist on disk."""


class TiingoCoverageError(MinerviniRecallError):
    """The Tiingo CSV exists but has fewer than min_bars bars <= asof_date."""


class MalformedExemplarRowError(MinerviniRecallError):
    """An exemplar CSV row is missing a required field or has a bad value."""


class MalformedAsofDateError(MinerviniRecallError):
    """An asof_date string could not be parsed to a date."""
