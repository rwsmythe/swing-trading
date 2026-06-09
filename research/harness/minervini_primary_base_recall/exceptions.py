from __future__ import annotations


class PrimaryBaseRecallError(Exception):
    """Base class for all minervini_primary_base_recall harness errors."""


class UnknownExemplarIdError(PrimaryBaseRecallError):
    """A curated cohort exemplar_id was not found in the exemplar CSV."""
