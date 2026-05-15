"""V1 field registry + validation. Single source of truth for web + CLI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    path: str
    label: str
    description: str
    type: type
    default: Any
    hard_refuse_min: Any | None
    hard_refuse_max: Any | None
    soft_warn_min: Any | None
    soft_warn_max: Any | None
    # Sub-bundle A T-A.2 — `masked=True` triggers asterisk masking in CLI
    # `swing config show` + web VM rendering for sensitive fields (e.g.,
    # account_hash). Default False preserves existing call-sites.
    masked: bool = False


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str


@dataclass(frozen=True)
class ValidationWarning:
    field: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    hard_errors: list[ValidationError] = field(default_factory=list)
    soft_warnings: list[ValidationWarning] = field(default_factory=list)


FIELD_REGISTRY: tuple[FieldSpec, ...] = (
    FieldSpec(
        path="web.chase_factor",
        label="Chase factor",
        description=(
            "Buy-limit pad above pivot. 0.01 = 1% above pivot. "
            "Operator's pure-trigger discipline favors values <= 0.02."
        ),
        type=float, default=0.01,
        hard_refuse_min=0.0, hard_refuse_max=0.10,
        soft_warn_min=None, soft_warn_max=0.02,
    ),
    FieldSpec(
        path="pipeline.chart_top_n_watch",
        label="Watchlist chart count",
        description="Number of watchlist tickers to render charts for in the nightly briefing.",
        type=int, default=10,
        hard_refuse_min=1, hard_refuse_max=50,
        soft_warn_min=None, soft_warn_max=25,
    ),
    FieldSpec(
        path="account.risk_equity_floor",
        label="Risk floor",
        description="Position-sizing floor: sizing_equity = max(real_equity, this).",
        type=float, default=7500.0,
        hard_refuse_min=0.0, hard_refuse_max=None,
        soft_warn_min=1000.0, soft_warn_max=25000.0,
    ),
    # Sub-bundle A T-A.2 — Schwab account_hash is sensitive; FIELD_REGISTRY
    # surfaces it as a `masked=True` entry so CLI `swing config show` + web VM
    # render the masked form (first 3 + asterisks + last 2). NOT editable via
    # `swing config set` (Schwab account_hash is written via `swing schwab setup`
    # in T-A.4); the registry entry is read-only/display-only for masking.
    FieldSpec(
        path="integrations.schwab.account_hash",
        label="Schwab account hash",
        description=(
            "Operator's Schwab linked-account hashValue (sensitive). Set via "
            "`swing schwab setup`. Displayed masked here."
        ),
        type=str, default=None,
        hard_refuse_min=None, hard_refuse_max=None,
        soft_warn_min=None, soft_warn_max=None,
        masked=True,
    ),
    # Phase 12 Sub-bundle B T-B.2 — Schwab app credentials cfg-cascade entries.
    # Mirrors `account_hash` masked=True template; auto-inherits first-3 +
    # `***` + last-2 mask rendering via `mask_sensitive_value`. NOT editable
    # via `swing config set` (write path is user-config.toml direct + future
    # T-B.4 web form per dispatch brief); registry entry surfaces them masked
    # in `swing config show` + `/config` web page.
    FieldSpec(
        path="integrations.schwab.client_id",
        label="Schwab client_id",
        description=(
            "Schwab Developer Portal app client_id (sensitive). Cfg-cascade "
            "fallback when `SCHWAB_CLIENT_ID` env var absent. Displayed "
            "masked here."
        ),
        type=str, default="",
        hard_refuse_min=None, hard_refuse_max=None,
        soft_warn_min=None, soft_warn_max=None,
        masked=True,
    ),
    FieldSpec(
        path="integrations.schwab.client_secret",
        label="Schwab client_secret",
        description=(
            "Schwab Developer Portal app client_secret (sensitive). Cfg-cascade "
            "fallback when `SCHWAB_CLIENT_SECRET` env var absent. Displayed "
            "masked here."
        ),
        type=str, default="",
        hard_refuse_min=None, hard_refuse_max=None,
        soft_warn_min=None, soft_warn_max=None,
        masked=True,
    ),
)


_BY_PATH: dict[str, FieldSpec] = {s.path: s for s in FIELD_REGISTRY}


def mask_sensitive_value(value: Any) -> str:
    """Mask a sensitive value for CLI/VM rendering.

    Pattern: first 3 chars verbatim + 3 asterisks + last 2 chars verbatim
    (e.g., "1A2***9F" — matches spec §3.5 mock).

    - ``None`` -> ``"(not set)"``
    - Values shorter than 5 chars -> rendered verbatim (cannot mask sensibly;
      operator misconfiguration surfaced rather than hidden silently).
    """
    if value is None:
        return "(not set)"
    s = str(value)
    if len(s) < 5:
        return s
    return f"{s[:3]}***{s[-2:]}"


def get_spec(field_path: str) -> FieldSpec:
    if field_path not in _BY_PATH:
        raise ValueError(f"unknown field_path: {field_path}")
    return _BY_PATH[field_path]


def coerce_value(field_path: str, raw_value: str) -> Any:
    spec = get_spec(field_path)
    if spec.type is int:
        # Codex R1 Major 3 — accept integer-valued floats ("15.0" → 15) for
        # web-form UX (HTML `<input type="number" step="1">` can post a
        # trailing-zero float in some browser/locale combinations). Reject
        # only non-integer floats ("15.5" → ValueError).
        try:
            f = float(raw_value)
        except ValueError as exc:
            raise ValueError(f"{field_path} requires an integer; got {raw_value!r}") from exc
        if not f.is_integer():
            raise ValueError(f"{field_path} requires an integer; got {raw_value!r}")
        return int(f)
    if spec.type is float:
        return float(raw_value)
    if spec.type is str:
        # Sub-bundle A T-A.2 — str passthrough for masked display-only entries
        # (e.g., integrations.schwab.account_hash). No further coercion; the
        # CLI/web caller layer is responsible for any normalization.
        return raw_value
    raise ValueError(f"unsupported type for {field_path}: {spec.type}")


def validate_field(field_path: str, raw_value: str) -> ValidationResult:
    spec = get_spec(field_path)
    try:
        value = coerce_value(field_path, raw_value)
    except ValueError as exc:
        return ValidationResult(
            hard_errors=[ValidationError(field=field_path, message=str(exc))],
        )
    hard: list[ValidationError] = []
    soft: list[ValidationWarning] = []
    if spec.hard_refuse_min is not None and value < spec.hard_refuse_min:
        hard.append(ValidationError(
            field=field_path,
            message=f"{spec.label} must be >= {spec.hard_refuse_min}; got {value}",
        ))
    if spec.hard_refuse_max is not None and value > spec.hard_refuse_max:
        hard.append(ValidationError(
            field=field_path,
            message=f"{spec.label} must be <= {spec.hard_refuse_max}; got {value}",
        ))
    if hard:
        return ValidationResult(hard_errors=hard)
    if spec.soft_warn_min is not None and value < spec.soft_warn_min:
        soft.append(ValidationWarning(
            field=field_path,
            message=(
                f"{spec.label} = {value} is below the typical floor "
                f"of {spec.soft_warn_min}. Confirm intent."
            ),
        ))
    if spec.soft_warn_max is not None and value > spec.soft_warn_max:
        soft.append(ValidationWarning(
            field=field_path,
            message=(
                f"{spec.label} = {value} is above the typical ceiling "
                f"of {spec.soft_warn_max}. Confirm intent."
            ),
        ))
    return ValidationResult(soft_warnings=soft)


def validate_all(form: dict[str, str]) -> ValidationResult:
    """Validate every V1 field present in `form`. Hard errors short-circuit no
    individual write; route layer is responsible for refusing the WRITE on
    any hard error. Soft warnings on multiple fields all surface.
    """
    hard: list[ValidationError] = []
    soft: list[ValidationWarning] = []
    for spec in FIELD_REGISTRY:
        if spec.path not in form:
            continue
        r = validate_field(spec.path, form[spec.path])
        hard.extend(r.hard_errors)
        soft.extend(r.soft_warnings)
    return ValidationResult(hard_errors=hard, soft_warnings=soft)
