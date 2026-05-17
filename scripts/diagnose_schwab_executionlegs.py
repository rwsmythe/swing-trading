"""Diagnostic: capture production Schwab orderActivityCollection[].executionLegs[]
shape for Sub-bundle 1.5 T-1.5.1.

Sub-bundle 1's mapper validator silently dropped all 18 production order legs
(see CLAUDE.md "Post-Phase-12 Sub-bundle 1 SHIPPED" entry + GATE PASS-WITH-
FINDING). Root cause unknown because schwab_api_calls does NOT capture
response_body_json. This script BYPASSES the validator entirely and reports
raw leg shapes against the expected key set, so the operator + orchestrator
can decide whether to widen the validator (e.g., add `orderId` key handling),
fix the validator, or pivot the mapper-coherence-check.

Invocation:
    python scripts/diagnose_schwab_executionlegs.py --environment production

Authenticates via the project's standard cascade (env vars > cfg > prompt
DISABLED); calls Client.account_orders for the production account over the
configured lookback window; iterates orderActivityCollection[].executionLegs[]
for each order; pretty-prints up to 3 representative leg shapes per order
(capped at --max-orders total).

Output is written to ~/swing-data/diagnose-schwab-executionlegs-<UTC>.txt
(operator-local; .gitignore already covers swing-data/). Redaction scrubs
client_id / client_secret / access_token / refresh_token / accountHash /
accountNumber + heuristic 32+ hex + 40+ base64 sequences BEFORE write
(40-char base64 threshold tightened from a hypothetical 24 to avoid
false-positives on legitimate `<base64-token>` placeholders -- see
Layer 1c comment + rationale at `redact_text`).

DO NOT commit the output file. The script intentionally lives separate from
production code so it can be invoked in operator-paired session against the
live Schwab API.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Defer heavy imports until __main__ to keep `--help` snappy + cheap to
# import for the unit tests in tests/integrations/test_diagnose_executionlegs_script.py.

_log = logging.getLogger("scripts.diagnose_schwab_executionlegs")


# ---------------------------------------------------------------------------
# Expected leg key catalog (mirrors swing/integrations/schwab/models.py
# SchwabExecutionLeg fields; the script does NOT import the dataclass to keep
# the comparator stable even if the validator widens later).
# ---------------------------------------------------------------------------

# The 6 keys the V1 mapper extracts via .get():
#   legId          -> SchwabExecutionLeg.leg_id           (int)
#   price          -> SchwabExecutionLeg.price            (float > 0)
#   quantity       -> SchwabExecutionLeg.quantity         (float > 0)
#   mismarkedQuantity -> SchwabExecutionLeg.mismarked_quantity (float|None)
#   instrumentId   -> SchwabExecutionLeg.instrument_id    (int|None)
#   time           -> SchwabExecutionLeg.time             (str non-empty)
_EXPECTED_LEG_KEYS: frozenset[str] = frozenset(
    {"legId", "price", "quantity", "mismarkedQuantity", "instrumentId", "time"}
)


# Per-key expected types (for the comparator). `None` allowed for optional
# fields (mismarkedQuantity + instrumentId).
_EXPECTED_LEG_TYPES: dict[str, tuple[type, ...]] = {
    "legId": (int,),
    "price": (int, float),
    "quantity": (int, float),
    "mismarkedQuantity": (int, float, type(None)),
    "instrumentId": (int, type(None)),
    "time": (str,),
}


DEFAULT_MAX_ORDERS = 30
DEFAULT_MAX_LEGS_PER_ORDER = 3

# Expected-leg keys that legitimately accept None at the validator (mismarked
# and instrumentId are nullable per SchwabExecutionLeg.__post_init__).
_OPTIONAL_NONE_OK: frozenset[str] = frozenset(
    {"mismarkedQuantity", "instrumentId"}
)


# ---------------------------------------------------------------------------
# Redaction (Layer 0 known-secret exact-replace + Layer 1 heuristic regex).
# Mirrors swing/integrations/schwab/client.py:_make_redactor_from_global +
# scripts/record_schwab_cassettes.py:_LEAK_PATTERNS sanitization shape.
# ---------------------------------------------------------------------------

# Schwab/OAuth sensitive JSON-key patterns (mirrors record_schwab_cassettes).
_JSON_KEY_LEAK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r'"accountNumber"\s*:\s*"[^"]+"', "accountNumber (quoted)"),
    (
        r'"(?:accountNumber|account_number)"\s*:\s*\d+(?:\.\d+)?',
        "accountNumber (bare numeric)",
    ),
    (r'"accountHash"\s*:\s*"[^"]+"', "accountHash"),
    (r'"access_token"\s*:\s*"[^"]+"', "access_token"),
    (r'"refresh_token"\s*:\s*"[^"]+"', "refresh_token"),
    (r'"id_token"\s*:\s*"[^"]+"', "id_token"),
    (r'"code"\s*:\s*"[^"]+"', "code"),
    (r'"client_id"\s*:\s*"[^"]+"', "client_id"),
    (r'"client_secret"\s*:\s*"[^"]+"', "client_secret"),
    (r'"bearerToken"\s*:\s*"[^"]+"', "bearerToken"),
)


def redact_text(text: str, *, known_secrets: Sequence[str] = ()) -> str:
    """Three-layer redactor.

    Layer 0: exact-replace each entry in `known_secrets` with `<REDACTED>`.
    Layer 1a: JSON-key shaped values (accountNumber / accountHash / tokens).
    Layer 1b: bare 32+ hex-char sequences.
    Layer 1c: bare 40+ base64-shaped sequences (tightened from 24 per
              record_schwab_cassettes precedent to avoid false-positives on
              legitimate `<base64-token>` placeholders).

    Pure function; safe to invoke from test code.
    """
    if not text:
        return text
    out = text
    # Layer 0 -- longest-secret-first to avoid substring collision.
    for secret in sorted({s for s in known_secrets if s and len(s) >= 4},
                         key=len, reverse=True):
        out = out.replace(secret, "<REDACTED>")
    # Layer 1a -- JSON-key shaped values.
    for pattern, name in _JSON_KEY_LEAK_PATTERNS:
        out = re.sub(pattern, f'"<REDACTED:{name}>"', out)
    # Layer 1b -- bare 32+ hex-char (defense-in-depth for stray tokens).
    out = re.sub(r"[a-fA-F0-9]{32,}", "<REDACTED:hex32+>", out)
    # Layer 1c -- bare 40+ base64-shaped.
    out = re.sub(r"[A-Za-z0-9+/=]{40,}={0,2}", "<REDACTED:b64-40+>", out)
    return out


# ---------------------------------------------------------------------------
# Leg-shape comparator.
# ---------------------------------------------------------------------------

def compare_leg_to_expected(leg: Any) -> dict[str, Any]:
    """Compare a single leg dict (raw from Schwab response) against the
    expected key set + types.

    Returns a structured report dict:
        {
            "is_dict": bool,
            "missing_keys": [str, ...],          # keys in expected set absent from leg
            "unexpected_keys": [str, ...],        # keys present that aren't expected
            "wrong_type": {key: actual_type, ...},
            "none_values": [str, ...],            # expected keys present but value is None
                                                  # (excludes mismarkedQuantity + instrumentId
                                                  # which legitimately accept None)
            "would_pass_type_shape_only": bool,   # type-and-key-presence check
                                                  # ONLY -- does NOT replicate the
                                                  # dataclass __post_init__ value-
                                                  # range guards (e.g., price > 0).
        }

    Defensive -- never raises on malformed input (str, None, list, etc.).
    """
    if not isinstance(leg, dict):
        return {
            "is_dict": False,
            "leg_type": type(leg).__name__,
            "missing_keys": [],
            "unexpected_keys": [],
            "wrong_type": {},
            "none_values": [],
            "would_pass_type_shape_only": False,
        }

    leg_keys = set(leg.keys())
    missing = sorted(_EXPECTED_LEG_KEYS - leg_keys)
    unexpected = sorted(leg_keys - _EXPECTED_LEG_KEYS)

    wrong_type: dict[str, str] = {}
    none_values: list[str] = []
    for key in _EXPECTED_LEG_KEYS:
        if key not in leg:
            continue
        value = leg[key]
        expected_types = _EXPECTED_LEG_TYPES.get(key, ())
        # Reject bool-as-number defensively (Python `bool` is subclass of int).
        if isinstance(value, bool) and key in {"legId", "price", "quantity",
                                                "mismarkedQuantity",
                                                "instrumentId"}:
            wrong_type[key] = "bool (rejected as number)"
            continue
        if not isinstance(value, expected_types):
            wrong_type[key] = type(value).__name__
            continue
        if value is None and key not in _OPTIONAL_NONE_OK:
            none_values.append(key)

    would_pass = (
        not missing
        and not wrong_type
        and not none_values
    )

    return {
        "is_dict": True,
        "leg_type": "dict",
        "missing_keys": missing,
        "unexpected_keys": unexpected,
        "wrong_type": wrong_type,
        "none_values": none_values,
        # NOTE: this is a TYPE-and-KEY-presence check only. It does NOT
        # replicate the dataclass __post_init__ value-range guards
        # (e.g., `price > 0`, `quantity > 0`, `time` non-empty), so a
        # placeholder shape with leg.price=0.0 would surface as True
        # here despite being rejected at SchwabExecutionLeg construction
        # (Codex R1 M#5 -- field rename to make the limitation honest).
        "would_pass_type_shape_only": would_pass,
    }


# ---------------------------------------------------------------------------
# Order-list iteration + leg shape capture.
# ---------------------------------------------------------------------------

def iterate_orders_with_legs(
    orders: Sequence[Any],
    *,
    max_orders: int = DEFAULT_MAX_ORDERS,
    max_legs_per_order: int = DEFAULT_MAX_LEGS_PER_ORDER,
) -> list[dict[str, Any]]:
    """Iterate raw Schwab order dicts; collect representative leg shapes.

    Returns a list of per-order capture dicts:
        {
            "order_id": str | None,
            "status": str | None,
            "order_type": str | None,
            "instruction": str | None,
            "filled_quantity": float | None,
            "activity_count": int,
            "execution_activity_count": int,
            "legs_captured": [
                {
                    "activity_index": int,
                    "leg_index": int,
                    "leg_raw_keys": [str, ...],
                    "leg_raw_values_str": {key: str(value), ...},
                    "comparator_report": {...},  # from compare_leg_to_expected
                },
                ...
            ],
        }

    Defensive -- skips orders that aren't dicts; skips activities that aren't
    dicts; skips legs that aren't dicts. NEVER raises on malformed input.
    """
    captures: list[dict[str, Any]] = []
    for order_idx, order in enumerate(orders):
        if order_idx >= max_orders:
            break
        if not isinstance(order, dict):
            captures.append({
                "order_index": order_idx,
                "order_type_python": type(order).__name__,
                "note": "skipped: order not a dict",
                "legs_captured": [],
            })
            continue
        # Try to pull the first orderLegCollection entry's instruction for
        # context (best-effort -- never raise).
        first_leg_collection = order.get("orderLegCollection") or []
        instruction: str | None = None
        if (
            isinstance(first_leg_collection, list)
            and first_leg_collection
            and isinstance(first_leg_collection[0], dict)
        ):
            inst_raw = first_leg_collection[0].get("instruction")
            if isinstance(inst_raw, str):
                instruction = inst_raw

        activities = order.get("orderActivityCollection") or []
        activity_count = (
            len(activities) if isinstance(activities, list) else 0
        )
        exec_activity_count = 0

        legs_captured: list[dict[str, Any]] = []
        legs_collected = 0
        if isinstance(activities, list):
            for ai, activity in enumerate(activities):
                if not isinstance(activity, dict):
                    continue
                if activity.get("activityType") == "EXECUTION":
                    exec_activity_count += 1
                exec_legs = activity.get("executionLegs", [])
                if not isinstance(exec_legs, list):
                    continue
                for li, leg in enumerate(exec_legs):
                    if legs_collected >= max_legs_per_order:
                        break
                    report = compare_leg_to_expected(leg)
                    # Pretty-print leg values as strings for the report (so
                    # arbitrary nested dicts / lists / ints / floats all
                    # serialize without raising).
                    leg_value_strs: dict[str, str] = {}
                    leg_keys_list: list[str] = []
                    if isinstance(leg, dict):
                        leg_keys_list = sorted(leg.keys())
                        for k in leg_keys_list:
                            try:
                                # `repr` gives stable representation including
                                # type info (str vs int looks different).
                                leg_value_strs[k] = repr(leg[k])
                            except Exception as exc:  # noqa: BLE001
                                leg_value_strs[k] = (
                                    f"<repr-error: {type(exc).__name__}>"
                                )
                    legs_captured.append({
                        "activity_index": ai,
                        "leg_index": li,
                        "activity_type": activity.get("activityType"),
                        "leg_raw_keys": leg_keys_list,
                        "leg_raw_values_repr": leg_value_strs,
                        "comparator_report": report,
                    })
                    legs_collected += 1
                if legs_collected >= max_legs_per_order:
                    break

        # filled_quantity defensive parse.
        filled_qty_raw = order.get("filledQuantity")
        try:
            filled_qty = (
                float(filled_qty_raw) if filled_qty_raw is not None else None
            )
        except (TypeError, ValueError):
            filled_qty = None

        captures.append({
            "order_index": order_idx,
            "order_id": str(order.get("orderId")) if order.get("orderId") is not None else None,
            "status": order.get("status"),
            "order_type": order.get("orderType"),
            "instruction": instruction,
            "filled_quantity": filled_qty,
            "activity_count": activity_count,
            "execution_activity_count": exec_activity_count,
            "legs_captured": legs_captured,
        })
    return captures


# ---------------------------------------------------------------------------
# Summary aggregation.
# ---------------------------------------------------------------------------

def summarize_captures(captures: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate captures into a summary block for the head of the output file.

    Returns:
        {
            "total_orders_inspected": int,
            "orders_with_executions": int,
            "total_legs_captured": int,
            "legs_would_pass_type_shape_only": int,
            "missing_key_frequency": {key: count, ...},
            "unexpected_key_frequency": {key: count, ...},
            "wrong_type_frequency": {key: count, ...},
        }
    """
    total_orders = len(captures)
    orders_with_executions = sum(
        1 for c in captures if c.get("execution_activity_count", 0) > 0
    )
    total_legs = sum(len(c.get("legs_captured", [])) for c in captures)
    legs_pass = sum(
        1
        for c in captures
        for leg in c.get("legs_captured", [])
        if leg.get("comparator_report", {}).get("would_pass_type_shape_only")
    )
    missing_freq: dict[str, int] = {}
    unexpected_freq: dict[str, int] = {}
    wrong_type_freq: dict[str, int] = {}
    for c in captures:
        for leg in c.get("legs_captured", []):
            report = leg.get("comparator_report", {})
            for k in report.get("missing_keys", []):
                missing_freq[k] = missing_freq.get(k, 0) + 1
            for k in report.get("unexpected_keys", []):
                unexpected_freq[k] = unexpected_freq.get(k, 0) + 1
            for k in report.get("wrong_type", {}):
                wrong_type_freq[k] = wrong_type_freq.get(k, 0) + 1
    return {
        "total_orders_inspected": total_orders,
        "orders_with_executions": orders_with_executions,
        "total_legs_captured": total_legs,
        "legs_would_pass_type_shape_only": legs_pass,
        "missing_key_frequency": missing_freq,
        "unexpected_key_frequency": unexpected_freq,
        "wrong_type_frequency": wrong_type_freq,
    }


# ---------------------------------------------------------------------------
# Output rendering (ASCII-only).
# ---------------------------------------------------------------------------

def render_report(
    *,
    captures: Sequence[dict[str, Any]],
    summary: dict[str, Any],
    metadata: dict[str, Any],
    known_secrets: Sequence[str],
) -> str:
    """Render the human-readable diagnostic report. ASCII-only output."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("Schwab executionLegs production-shape diagnostic")
    lines.append("Sub-bundle 1.5 T-1.5.1")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Generated:   {metadata.get('generated_utc', '-')}")
    lines.append(f"Environment: {metadata.get('environment', '-')}")
    lines.append(f"Lookback days: {metadata.get('lookback_days', '-')}")
    lines.append(f"Max orders inspected: {metadata.get('max_orders', '-')}")
    lines.append(
        f"Window: {metadata.get('from_time', '-')} -> {metadata.get('to_time', '-')}"
    )
    lines.append("")
    lines.append("-" * 72)
    lines.append("Summary")
    lines.append("-" * 72)
    lines.append(f"Total orders inspected:    {summary['total_orders_inspected']}")
    lines.append(
        f"Orders with executions:    {summary['orders_with_executions']}"
    )
    lines.append(f"Total legs captured:       {summary['total_legs_captured']}")
    lines.append(
        f"Legs that pass type+key-shape check (does NOT include "
        f"value-range guards): {summary['legs_would_pass_type_shape_only']}"
    )
    if summary["missing_key_frequency"]:
        lines.append("Missing-key frequency:")
        for k, v in sorted(summary["missing_key_frequency"].items()):
            lines.append(f"  {k}: {v}")
    else:
        lines.append("Missing-key frequency: (none)")
    if summary["unexpected_key_frequency"]:
        lines.append("Unexpected-key frequency:")
        for k, v in sorted(summary["unexpected_key_frequency"].items()):
            lines.append(f"  {k}: {v}")
    else:
        lines.append("Unexpected-key frequency: (none)")
    if summary["wrong_type_frequency"]:
        lines.append("Wrong-type frequency:")
        for k, v in sorted(summary["wrong_type_frequency"].items()):
            lines.append(f"  {k}: {v}")
    else:
        lines.append("Wrong-type frequency: (none)")
    lines.append("")
    lines.append("Expected leg keys (V1 mapper):")
    for k in sorted(_EXPECTED_LEG_KEYS):
        types = _EXPECTED_LEG_TYPES[k]
        type_names = ", ".join(
            t.__name__ if t is not type(None) else "None" for t in types
        )
        lines.append(f"  {k} : {type_names}")
    lines.append("")
    lines.append("-" * 72)
    lines.append("Per-order capture")
    lines.append("-" * 72)
    for c in captures:
        lines.append("")
        order_id = c.get("order_id") or "<no orderId>"
        lines.append(
            f"Order #{c.get('order_index')} id={order_id} "
            f"status={c.get('status')!r} orderType={c.get('order_type')!r} "
            f"instruction={c.get('instruction')!r} "
            f"filledQty={c.get('filled_quantity')!r}"
        )
        lines.append(
            f"  activity_count={c.get('activity_count', 0)} "
            f"execution_activity_count={c.get('execution_activity_count', 0)}"
        )
        if c.get("note"):
            lines.append(f"  note: {c['note']}")
        legs = c.get("legs_captured", [])
        if not legs:
            lines.append("  (no executionLegs captured)")
            continue
        for leg_cap in legs:
            lines.append(
                f"  leg activity[{leg_cap['activity_index']}].legs[{leg_cap['leg_index']}]"
                f" activityType={leg_cap.get('activity_type')!r}"
            )
            report = leg_cap.get("comparator_report", {})
            lines.append(
                f"    is_dict={report.get('is_dict')} "
                f"would_pass_type_shape_only={report.get('would_pass_type_shape_only')}"
            )
            if not report.get("is_dict"):
                lines.append(
                    f"    leg type: {report.get('leg_type')}"
                )
                continue
            lines.append(
                f"    keys present: {leg_cap.get('leg_raw_keys', [])}"
            )
            if report.get("missing_keys"):
                lines.append(
                    f"    missing keys: {report['missing_keys']}"
                )
            if report.get("unexpected_keys"):
                lines.append(
                    f"    unexpected keys: {report['unexpected_keys']}"
                )
            if report.get("wrong_type"):
                lines.append(
                    f"    wrong types: {report['wrong_type']}"
                )
            if report.get("none_values"):
                lines.append(
                    f"    None values on required: {report['none_values']}"
                )
            lines.append("    values (repr):")
            for k, v in sorted(leg_cap.get("leg_raw_values_repr", {}).items()):
                lines.append(f"      {k} = {v}")

    body = "\n".join(lines) + "\n"
    return redact_text(body, known_secrets=known_secrets)


# ---------------------------------------------------------------------------
# Output file path computation.
# ---------------------------------------------------------------------------

def compute_output_path(
    *, output_dir: Path | None = None, now: datetime | None = None,
) -> Path:
    """Compute the output file path.

    Default: `~/swing-data/diagnose-schwab-executionlegs-<UTC-ISO>.txt`.
    Test-side: callers may pass `output_dir=tmp_path`.

    Timestamp suffix uses `YYYYMMDDTHHMMSSZ` (filesystem-safe ISO 8601 basic).
    """
    if output_dir is None:
        # ~/swing-data/ -- covered by .gitignore.
        output_dir = Path.home() / "swing-data"
    if now is None:
        now = datetime.now(UTC)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    return output_dir / f"diagnose-schwab-executionlegs-{ts}.txt"


# ---------------------------------------------------------------------------
# Argparse + main.
# ---------------------------------------------------------------------------

def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="diagnose_schwab_executionlegs",
        description=(
            "Capture production Schwab orderActivityCollection[].executionLegs[] "
            "shape to diagnose the Sub-bundle 1 validator-drop defect. Bypasses "
            "the mapper; reports raw leg shapes against the expected key set. "
            "Writes redacted output to ~/swing-data/."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "DO NOT commit the output file. Operator-paired session required "
            "for production environment."
        ),
    )
    parser.add_argument(
        "--environment",
        default="production",
        choices=("production", "sandbox"),
        help="Schwab tokens DB environment (default: production).",
    )
    parser.add_argument(
        "--max-orders",
        type=int,
        default=DEFAULT_MAX_ORDERS,
        help=(
            f"Maximum orders to inspect (default: {DEFAULT_MAX_ORDERS}). "
            "Capped at the order count Schwab returns for the window."
        ),
    )
    parser.add_argument(
        "--max-legs-per-order",
        type=int,
        default=DEFAULT_MAX_LEGS_PER_ORDER,
        help=(
            f"Maximum representative legs captured per order "
            f"(default: {DEFAULT_MAX_LEGS_PER_ORDER}). Bounds output verbosity."
        ),
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help=(
            "Lookback window in days for account_orders fromEnteredTime "
            "(default: 30 -- wider than pipeline's 7-day cfg default to "
            "maximize chance of capturing recent executions). Matches the "
            "T-1.5.1 brief default."
        ),
    )
    parser.add_argument(
        "--config",
        type=str,
        default="swing.config.toml",
        help="Path to swing.config.toml (default: swing.config.toml in cwd).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Authenticated client bootstrap. Thin wrappers seam-patchable in tests.
# ---------------------------------------------------------------------------

def _load_cfg(config_path: Path | None = None) -> Any:
    from swing.config import load
    if config_path is None:
        config_path = Path("swing.config.toml")
    return load(config_path)


def _apply_overrides_thin(cfg: Any) -> Any:
    from swing.config_overrides import apply_overrides
    return apply_overrides(cfg)


def _resolve_credentials_thin(
    cfg: Any, environment: str, *, allow_prompt: bool = False,
) -> tuple[str | None, str | None]:
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt
    return resolve_credentials_env_or_prompt(
        cfg, environment, allow_prompt=allow_prompt,
    )


def _construct_client_thin(
    *, cfg: Any, environment: str, client_id: str, client_secret: str,
) -> Any:
    from swing.integrations.schwab.auth import construct_authenticated_client
    return construct_authenticated_client(
        cfg=cfg,
        environment=environment,
        client_id=client_id,
        client_secret=client_secret,
    )


def _bootstrap_authenticated_client(
    *, environment: str, config_path: Path | None = None,
) -> tuple[Any, Any, list[str]]:
    """Apply project's standard auth cascade.

    Returns:
        (client, cfg, known_secrets) -- `known_secrets` carries all credential
        slot values that should be exact-redacted from output.

    Raises:
        SystemExit on credential-resolution failure (operator-actionable msg).
    """
    cfg_pre = _load_cfg(config_path)
    cfg = _apply_overrides_thin(cfg_pre)
    client_id, client_secret = _resolve_credentials_thin(
        cfg, environment, allow_prompt=False,
    )
    if not client_id or not client_secret:
        raise SystemExit(
            "FAILED: Schwab credentials unresolved. Set SCHWAB_CLIENT_ID + "
            "SCHWAB_CLIENT_SECRET env vars OR configure ~/swing-data/user-"
            "config.toml under [integrations.schwab]."
        )
    client = _construct_client_thin(
        cfg=cfg,
        environment=environment,
        client_id=client_id,
        client_secret=client_secret,
    )
    # schwabdev silent-failure-mode defense -- verify post-call state. The
    # auth helper already does this + raises SchwabAuthError if not; we
    # re-check here so the diagnostic script surfaces a clear error if a
    # future refactor relaxes the defense.
    tokens = getattr(client, "tokens", None)
    access_token = getattr(tokens, "access_token", None) if tokens else None
    refresh_token = getattr(tokens, "refresh_token", None) if tokens else None
    if not access_token or not isinstance(access_token, str):
        raise SystemExit(
            "FAILED: client.tokens.access_token unpopulated post-construction "
            "(schwabdev silent-failure-mode). Run `swing schwab refresh` or "
            "`swing schwab setup`."
        )
    known_secrets: list[str] = [client_id, client_secret, access_token]
    if refresh_token and isinstance(refresh_token, str):
        known_secrets.append(refresh_token)
    # Also redact accountHash if cfg has it.
    account_hash = getattr(
        getattr(cfg.integrations, "schwab", None), "account_hash", None,
    )
    if account_hash and isinstance(account_hash, str):
        known_secrets.append(account_hash)
    return client, cfg, known_secrets


def _fetch_raw_orders(
    *,
    client: Any,
    account_hash: str,
    from_time: str,
    to_time: str,
    max_orders: int,
) -> list[Any]:
    """Invoke `Client.account_orders(...)` directly to obtain the RAW
    Schwab response.

    Bypasses `swing.integrations.schwab.trader.get_account_orders` (which
    runs the mapper that DROPS legs). The mapper's drop+warn is exactly
    what we're diagnosing -- we need the pre-validator shape.

    schwabdev's `Client.account_orders` returns either a `requests.Response`
    (when called without explicit `.json()` parsing on schwabdev's side)
    OR a list (when called via project's higher-level wrappers). Both
    shapes are accepted defensively here.
    """
    response = client.account_orders(
        account_hash,
        from_time,
        to_time,
        status=None,
        maxResults=max_orders,
    )
    # Accept both shapes (raw requests.Response OR pre-parsed list).
    if isinstance(response, list):
        return response
    # requests.Response-like with .json() method.
    if hasattr(response, "json"):
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(
                f"FAILED: account_orders response.json() raised "
                f"{type(exc).__name__}; cannot parse for diagnostic."
            ) from exc
        if isinstance(payload, list):
            return payload
        # Sometimes the response is a dict with an embedded list -- accept it.
        if isinstance(payload, dict):
            for key in ("orders", "data", "items"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        raise SystemExit(
            f"FAILED: account_orders payload not a list "
            f"(got {type(payload).__name__}); cannot iterate orders."
        )
    raise SystemExit(
        f"FAILED: account_orders response neither list nor "
        f"requests-Response-like (got {type(response).__name__})."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Script entry. Returns process exit code."""
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    client, cfg, known_secrets = _bootstrap_authenticated_client(
        environment=args.environment,
        config_path=Path(args.config),
    )

    account_hash = getattr(
        getattr(cfg.integrations, "schwab", None), "account_hash", None,
    )
    if not account_hash or not isinstance(account_hash, str):
        sys.stderr.write(
            "FAILED: cfg.integrations.schwab.account_hash is unset; cannot "
            "invoke Schwab account-scoped endpoints. Run "
            "`swing schwab status --environment "
            f"{args.environment}` to populate.\n"
        )
        return 1

    now = datetime.now(UTC)
    from_dt = now - timedelta(days=int(args.lookback_days))
    from_time = from_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    sys.stdout.write(
        f"Diagnostic: fetching up to {args.max_orders} orders from "
        f"environment={args.environment} window={from_time} -> {to_time}\n"
    )

    orders = _fetch_raw_orders(
        client=client,
        account_hash=account_hash,
        from_time=from_time,
        to_time=to_time,
        max_orders=args.max_orders,
    )

    sys.stdout.write(f"Diagnostic: Schwab returned {len(orders)} orders\n")

    captures = iterate_orders_with_legs(
        orders,
        max_orders=args.max_orders,
        max_legs_per_order=args.max_legs_per_order,
    )
    summary = summarize_captures(captures)

    metadata = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": args.environment,
        "lookback_days": args.lookback_days,
        "max_orders": args.max_orders,
        "from_time": from_time,
        "to_time": to_time,
    }
    report_text = render_report(
        captures=captures,
        summary=summary,
        metadata=metadata,
        known_secrets=known_secrets,
    )

    output_path = compute_output_path(now=now)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")

    sys.stdout.write(
        f"Diagnostic: wrote redacted report to {output_path}\n"
    )
    sys.stdout.write(
        f"Diagnostic: summary -- orders={summary['total_orders_inspected']} "
        f"with-executions={summary['orders_with_executions']} "
        f"legs-captured={summary['total_legs_captured']} "
        f"type-shape-pass={summary['legs_would_pass_type_shape_only']}\n"
    )

    # If any leg would pass the type+key-shape check, that's good for the
    # surface diagnostic; if zero, that's the production-state defect we're
    # diagnosing. (Note: this is a type-shape check only; dataclass
    # __post_init__ value-range guards may still reject a "passing" leg.)
    # Either way exit 0 -- the report itself is the deliverable.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
