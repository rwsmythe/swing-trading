"""Effective Config with user-config overrides applied.

Per locked decision §2.3: per-request read. Re-reads user-config.toml on
every call; cheap (~50 bytes, OS-cached). Documented residual risk: caches
built at app startup hold the original immutable cfg; V1 fields don't
feed those caches, so the mismatch is benign. See plan §C.
"""
from __future__ import annotations

from dataclasses import is_dataclass, replace
from typing import Any, Literal

from swing.config import Config
from swing.config_user import load_user_overrides

# V1 field paths — keep in lockstep with config_validation.FIELD_REGISTRY.
# `integrations.schwab.account_hash` added Sub-bundle A T-A.2 (masked display
# entry; NOT user-editable via `swing config set`).
_V1_PATHS = (
    "web.chase_factor",
    "pipeline.chart_top_n_watch",
    "account.risk_equity_floor",
    "integrations.schwab.account_hash",
    # Phase 12 Sub-bundle B T-B.2 — Schwab app credentials cfg-cascade entries.
    # FIELD_REGISTRY surfaces both masked; `swing config show` calls
    # `get_field_source` for every registry path, so these must appear here too.
    "integrations.schwab.client_id",
    "integrations.schwab.client_secret",
    # Phase 15 schwabdev v3 (OQ-1) — Fernet token-at-rest key (masked registry entry).
    "integrations.schwab.encryption_key",
)


class _Missing:
    """Sentinel — distinguishes 'absent' from 'present and None'."""


_MISSING = _Missing()


def _get(overrides: dict[str, Any], path: str) -> Any | _Missing:
    """Walk a dotted path through nested dicts. Supports N-part paths
    (e.g. ``integrations.finviz.token``); preserves 2-part semantics for
    the existing ``_V1_PATHS`` registry consumers.
    """
    parts = path.split(".")
    cursor: Any = overrides
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            return _MISSING
        cursor = cursor[part]
    return cursor


def apply_overrides(base_cfg: Config) -> Config:
    """Return a Config with V1 user-config overrides applied.

    Cheap; safe to call at every route entry. Future V2 fields require
    extending the per-section replace blocks below.

    Codex R1 Critical #1 follow-up — defensive short-circuit when
    ``base_cfg`` is NOT a dataclass instance. Some test stubs build cfg
    via ``types.SimpleNamespace`` (e.g.
    ``tests/integrations/test_schwab_pipeline_active_exclusion.py``); the
    final ``dataclasses.replace(base_cfg, ...)`` call would raise
    ``TypeError: replace() should be called on dataclass instances`` for
    such stubs. Since SimpleNamespace cfgs cannot have ``user-config.toml``
    overrides applied to them in any meaningful way (no
    ``dataclasses.replace`` semantics), returning the base cfg unchanged
    preserves the V1 contract for production callers while remaining
    test-stub-friendly.
    """
    if not is_dataclass(base_cfg):
        return base_cfg
    overrides = load_user_overrides()
    new_web = base_cfg.web
    new_pipeline = base_cfg.pipeline
    new_account = base_cfg.account
    new_integrations = base_cfg.integrations

    cf = _get(overrides, "web.chase_factor")
    if not isinstance(cf, _Missing):
        new_web = replace(new_web, chase_factor=float(cf))

    ctnw = _get(overrides, "pipeline.chart_top_n_watch")
    if not isinstance(ctnw, _Missing):
        new_pipeline = replace(new_pipeline, chart_top_n_watch=int(ctnw))

    ref = _get(overrides, "account.risk_equity_floor")
    if not isinstance(ref, _Missing):
        new_account = replace(new_account, risk_equity_floor=float(ref))

    # integrations.finviz overrides — sensitive fields live in user-config only.
    # `_V1_PATHS` is intentionally NOT extended here (Phase 7e §A.6 Codex R1
    # Critical-2 fix); these paths bypass the registry by design.
    new_finviz = base_cfg.integrations.finviz
    fv_token = _get(overrides, "integrations.finviz.token")
    if not isinstance(fv_token, _Missing):
        new_finviz = replace(new_finviz, token=str(fv_token))
    fv_query = _get(overrides, "integrations.finviz.screen_query")
    if not isinstance(fv_query, _Missing):
        # Codex R4 Major-1: canonicalize at the cfg-load boundary so request
        # building, audit-row persistence, and signature-history lookups all
        # see the same form. Otherwise an operator who pastes '?v=152&...'
        # one day and 'v=152&...' the next forks the audit history under two
        # `screen_query` keys, defeating drift detection.
        new_finviz = replace(new_finviz, screen_query=str(fv_query).lstrip("?"))

    # integrations.schwab overrides — 4 user-config-only fields per Sub-bundle A
    # T-A.2 plan §A.6 + recon §2.9 (environment / account_hash / lookback_days /
    # callback_url). timeout_seconds + marketdata_ladder_enabled live in tracked
    # swing.config.toml and are NOT user-overridable (matches Finviz pattern).
    new_schwab = base_cfg.integrations.schwab
    sw_env = _get(overrides, "integrations.schwab.environment")
    if not isinstance(sw_env, _Missing):
        new_schwab = replace(new_schwab, environment=str(sw_env))
    sw_hash = _get(overrides, "integrations.schwab.account_hash")
    if not isinstance(sw_hash, _Missing):
        # Preserve None (explicit clear); else coerce to str.
        new_schwab = replace(
            new_schwab,
            account_hash=None if sw_hash is None else str(sw_hash),
        )
    sw_lookback = _get(overrides, "integrations.schwab.lookback_days")
    if not isinstance(sw_lookback, _Missing):
        new_schwab = replace(new_schwab, lookback_days=int(sw_lookback))
    sw_callback = _get(overrides, "integrations.schwab.callback_url")
    if not isinstance(sw_callback, _Missing):
        new_schwab = replace(new_schwab, callback_url=str(sw_callback))
    # Phase 12 Sub-bundle B T-B.2 — Schwab app credentials cfg-cascade
    # (env vars > user-config.toml > prompt; T-B.1 wires the consumer).
    sw_cid = _get(overrides, "integrations.schwab.client_id")
    if not isinstance(sw_cid, _Missing):
        new_schwab = replace(new_schwab, client_id=str(sw_cid))
    sw_csec = _get(overrides, "integrations.schwab.client_secret")
    if not isinstance(sw_csec, _Missing):
        new_schwab = replace(new_schwab, client_secret=str(sw_csec))
    sw_enc = _get(overrides, "integrations.schwab.encryption_key")
    if not isinstance(sw_enc, _Missing):
        new_schwab = replace(new_schwab, encryption_key=str(sw_enc))

    if (
        new_finviz is not base_cfg.integrations.finviz
        or new_schwab is not base_cfg.integrations.schwab
    ):
        new_integrations = replace(
            base_cfg.integrations,
            finviz=new_finviz,
            schwab=new_schwab,
        )

    return replace(
        base_cfg,
        web=new_web,
        pipeline=new_pipeline,
        account=new_account,
        integrations=new_integrations,
    )


def get_field_source(
    base_cfg: Config, field_path: str,
) -> Literal["default", "tracked", "override"]:
    """Report the precedence layer the field's effective value comes from.

    Codex watch-item #4: an explicit override at the registry default value
    still reports 'override' (operator chose to lock it).
    """
    if field_path not in _V1_PATHS:
        raise ValueError(f"unknown field_path: {field_path}")
    overrides = load_user_overrides()
    if not isinstance(_get(overrides, field_path), _Missing):
        return "override"
    from swing.config_validation import FIELD_REGISTRY
    spec = next(s for s in FIELD_REGISTRY if s.path == field_path)
    # Sub-bundle A T-A.2 — walk N-part dotted path (e.g.,
    # 'integrations.schwab.account_hash') to support nested sub-dataclasses.
    parts = field_path.split(".")
    cursor: Any = base_cfg
    for part in parts:
        cursor = getattr(cursor, part)
    base_value = cursor
    return "tracked" if base_value != spec.default else "default"
