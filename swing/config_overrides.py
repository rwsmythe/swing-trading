"""Effective Config with user-config overrides applied.

Per locked decision §2.3: per-request read. Re-reads user-config.toml on
every call; cheap (~50 bytes, OS-cached). Documented residual risk: caches
built at app startup hold the original immutable cfg; V1 fields don't
feed those caches, so the mismatch is benign. See plan §C.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Literal

from swing.config import Config
from swing.config_user import load_user_overrides


# V1 field paths — keep in lockstep with config_validation.FIELD_REGISTRY.
_V1_PATHS = ("web.chase_factor", "pipeline.chart_top_n_watch", "account.risk_equity_floor")


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
    """
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
    if new_finviz is not base_cfg.integrations.finviz:
        new_integrations = replace(base_cfg.integrations, finviz=new_finviz)

    return replace(
        base_cfg,
        web=new_web,
        pipeline=new_pipeline,
        account=new_account,
        integrations=new_integrations,
    )


def get_field_source(base_cfg: Config, field_path: str) -> Literal["default", "tracked", "override"]:
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
    section, key = field_path.split(".")
    section_obj = getattr(base_cfg, section)
    base_value = getattr(section_obj, key)
    return "tracked" if base_value != spec.default else "default"
