from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow, read_exemplars

from .exceptions import UnknownExemplarIdError


@dataclass(frozen=True)
class CohortMember:
    exemplar_id: str
    role: str  # "sub_floor" | "positive_control"
    book_citation: str


@dataclass(frozen=True)
class ResolvedMember:
    member: CohortMember
    row: ExemplarRow


# The curated documented-primary-base cohort (spec section 3). Roles: sub_floor names were
# un-screenable by the original Minervini-recall study (< YOUNG_NAME_CEILING_BARS bars at entry);
# the positive_control has sufficient history. JNPR is a sub_floor name that the screen will report
# history-excluded at runtime (25 bars < MIN_HISTORY_BARS). MELI is excluded (young-VCP, R1.M4).
CURATED_COHORT: tuple[CohortMember, ...] = (
    CohortMember("twosmw-fig11-1-amzn", "sub_floor", "TWoSMW Ch.11 Fig 11.1 (AMZN-1997)"),
    CohortMember("ttlc-fig10-1-body", "sub_floor", "TWoSMW Ch.11 Fig 11.5 / TTLC Fig 10-1 (BODY)"),
    CohortMember("twosmw-fig11-6-dks", "sub_floor", "TWoSMW Ch.11 Fig 11.6 (DKS)"),
    CohortMember("twosmw-fig11-7-jnpr", "sub_floor", "TWoSMW Ch.11 Fig 11.7 (JNPR, history-excluded)"),
    CohortMember("twosmw-fig11-3-yhoo", "positive_control", "TWoSMW Ch.11 Fig 11.3 (YHOO)"),
)


def resolve_cohort(csv_path: Path) -> list[ResolvedMember]:
    """Pair each curated cohort member with its ExemplarRow; raise on any missing id."""
    rows_by_id = {r.exemplar_id: r for r in read_exemplars(csv_path)}
    resolved: list[ResolvedMember] = []
    for member in CURATED_COHORT:
        row = rows_by_id.get(member.exemplar_id)
        if row is None:
            raise UnknownExemplarIdError(
                f"curated cohort id {member.exemplar_id!r} not found in {csv_path}"
            )
        resolved.append(ResolvedMember(member=member, row=row))
    return resolved
