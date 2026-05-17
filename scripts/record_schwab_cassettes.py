"""Record Schwab cassettes for Sub-bundle 1 T-1.13 consumption.

Recording mechanism is independent of the T-1.13 test file (which has not
yet been authored at T-1.0-commit time) and of the V2 mapper code (which
does not yet exist). Run this script with valid production tokens to
populate ``tests/integrations/cassettes/schwab/test_e2e_<order_type>.yaml``.

Operator workflow (per plan §F.2):

    python scripts/record_schwab_cassettes.py --environment production

Per plan §A.1.0 acceptance criterion #7 + Codex R4/R5/R6 LOCKs:

- `--environment {production,sandbox}` REQUIRED; `--order-types <list>`
  OPTIONAL default `limit_buy,limit_sell,stop_fired,market_buy` (4 REQUIRED;
  `stop_limit_fired` admissible stretch); `--days N` default 30.
- Uses the SAME config + auth path as `swing schwab fetch` / `swing schwab status`:
  `swing.config.load()` → `apply_overrides(cfg)` →
  `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` →
  `construct_authenticated_client(cfg=, environment=, client_id=, client_secret=)`.
- Imports the shared sanitization filter dict from ``tests/conftest.py:vcr_config``
  via the ``__wrapped__`` indirection.
- Per-order-type recording loop: opens ``vcr.use_cassette(...)`` with
  ``record_mode='new_episodes'`` + replays via ``record_mode='none'`` for
  post-record validation gate.
- Post-record validation: at least ONE order matches the requested type AND
  carries non-empty ``orderActivityCollection[].executionLegs[]``. On failure
  cassette is DELETED + non-zero exit with operator-actionable message.
- Sentinel-leak audit (mirror ``tests/conftest.py`` scrubber catalog): scans
  the just-written cassette for unsanitized substrings; deletes + exits if
  any pattern matches.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Defer heavy imports until __main__ to keep `--help` snappy + the test file's
# importable thin helpers cheap.

_log = logging.getLogger("scripts.record_schwab_cassettes")


# ---------------------------------------------------------------------------
# Constants per plan §A.1.0 acceptance criterion #7.
# ---------------------------------------------------------------------------

REQUIRED_ORDER_TYPES: tuple[str, ...] = (
    "limit_buy",
    "limit_sell",
    "stop_fired",
    "market_buy",
)
STRETCH_ORDER_TYPES: tuple[str, ...] = ("stop_limit_fired",)
ALL_ORDER_TYPES: tuple[str, ...] = REQUIRED_ORDER_TYPES + STRETCH_ORDER_TYPES

DEFAULT_DAYS = 30

CASSETTE_DIR_REL = Path("tests/integrations/cassettes/schwab")


# Predicates per order_type: (orderType match, instruction match, status hint).
# Map of order_type label -> predicate dict.
ORDER_TYPE_PREDICATES: dict[str, dict[str, Any]] = {
    "limit_buy": {
        "orderType": ("LIMIT",),
        "instruction": ("BUY", "BUY_TO_OPEN"),
        "status": ("FILLED",),
    },
    "limit_sell": {
        "orderType": ("LIMIT",),
        "instruction": ("SELL", "SELL_TO_CLOSE"),
        "status": ("FILLED",),
    },
    "stop_fired": {
        # Schwab fires a STOP -> FILLED transition; orderType remains
        # 'STOP' (or 'TRAILING_STOP') even after the fill.
        "orderType": ("STOP", "TRAILING_STOP"),
        "instruction": (
            "SELL", "SELL_TO_CLOSE", "BUY_TO_CLOSE",
        ),
        "status": ("FILLED",),
    },
    "market_buy": {
        "orderType": ("MARKET",),
        "instruction": ("BUY", "BUY_TO_OPEN"),
        "status": ("FILLED",),
    },
    "stop_limit_fired": {
        "orderType": ("STOP_LIMIT", "TRAILING_STOP_LIMIT"),
        "instruction": (
            "SELL", "SELL_TO_CLOSE", "BUY_TO_CLOSE",
        ),
        "status": ("FILLED",),
    },
}


# Sentinel-leak audit regex catalog (mirrors plan §G.4 + tests/conftest.py).
_LEAK_PATTERNS: tuple[tuple[str, str], ...] = (
    # Unsanitized JSON-key value forms.
    (r'"accountNumber"\s*:\s*"[^<][^"]{0,80}"', "accountNumber"),
    (r'"accountHash"\s*:\s*"[^<][a-fA-F0-9]{16,}[^"]*"', "accountHash"),
    (r'"access_token"\s*:\s*"[^<][^"]{4,}"', "access_token"),
    (r'"refresh_token"\s*:\s*"[^<][^"]{4,}"', "refresh_token"),
    (r'"id_token"\s*:\s*"[^<][^"]{4,}"', "id_token"),
    (r'"code"\s*:\s*"[^<][^"]{4,}"', "code"),
    (r'"client_id"\s*:\s*"[^<][^"]{4,}"', "client_id"),
    (r'"client_secret"\s*:\s*"[^<][^"]{4,}"', "client_secret"),
    (r'"bearerToken"\s*:\s*"[^<][^"]{4,}"', "bearerToken"),
    # Form-encoded values.
    (r"\bclient_secret=[^&\s<][^&\s]{3,}", "client_secret form"),
    (r"\baccess_token=[^&\s<][^&\s]{3,}", "access_token form"),
    (r"\brefresh_token=[^&\s<][^&\s]{3,}", "refresh_token form"),
    # URI accountHash path segments — Codex R2 Critical #1.
    (r"/accounts/[^<][^/?#]{8,}", "accountHash URL path segment"),
    # Bare token-shape (40+ base64 / 32+ hex) — defense-in-depth.
    # NOTE: tightened base64 threshold from 24 to 40 per §G.4 to avoid
    # false-positives on legitimate `<base64-token>` placeholders.
    (r"\b[A-Za-z0-9+/=]{40,}={0,2}\b", "base64-token-shape"),
)


# ---------------------------------------------------------------------------
# Argparse + main entry.
# ---------------------------------------------------------------------------

def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """argparse with the AC#7.a defaults."""
    parser = argparse.ArgumentParser(
        prog="record_schwab_cassettes",
        description=(
            "Record Schwab API cassettes for Sub-bundle 1 T-1.13 consumption. "
            "Operator workflow per plan §F.2; sanitization filter spec per "
            "plan §F.3."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Defaults --order-types covers the 4 REQUIRED set: "
            f"{','.join(REQUIRED_ORDER_TYPES)}. "
            f"Stretch (OPTIONAL): {','.join(STRETCH_ORDER_TYPES)}. "
            "--days default is 30 (lookback window for account_orders "
            "fromEnteredTime). --environment is REQUIRED (production or "
            "sandbox)."
        ),
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("production", "sandbox"),
        help="Schwab tokens DB environment (REQUIRED).",
    )
    parser.add_argument(
        "--order-types",
        default=",".join(REQUIRED_ORDER_TYPES),
        help=(
            "Comma-separated list of order types to record. Defaults to "
            f"4 REQUIRED: {','.join(REQUIRED_ORDER_TYPES)}. Choices: "
            f"{','.join(ALL_ORDER_TYPES)}."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=(
            f"Lookback window in days for account_orders fromEnteredTime. "
            f"Default {DEFAULT_DAYS}."
        ),
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=200,
        help="schwabdev maxResults arg for account_orders. Default 200.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="swing.config.toml",
        help=(
            "Path to swing.config.toml (mirrors `swing --config` CLI flag). "
            "Default: swing.config.toml relative to cwd."
        ),
    )

    ns = parser.parse_args(argv)
    # Validate order-types post-parse.
    raw = [s.strip() for s in str(ns.order_types).split(",") if s.strip()]
    unknown = [s for s in raw if s not in ALL_ORDER_TYPES]
    if unknown:
        parser.error(
            f"Unknown order-type(s): {','.join(unknown)}. "
            f"Choices: {','.join(ALL_ORDER_TYPES)}.",
        )
    ns.order_types_list = raw
    return ns


# ---------------------------------------------------------------------------
# Thin wrappers (monkeypatch-able by Test 7 + auth bootstrap).
# Per Codex R5 M#2 + R6 M#1 — these are the seams Test 7 patches.
# ---------------------------------------------------------------------------

def _load_cfg(config_path: Path | None = None) -> Any:
    """Loads project config via `swing.config.load(config_path)`.

    Mirrors the `swing` CLI default (`swing.config.toml` relative to cwd
    per `swing/cli.py:178`). Callers may override via `--config` arg.
    """
    from swing.config import load
    if config_path is None:
        config_path = Path("swing.config.toml")
    return load(config_path)


def _apply_overrides_thin(cfg: Any) -> Any:
    """Applies cfg-cascade overrides via `swing.config_overrides.apply_overrides`."""
    from swing.config_overrides import apply_overrides
    return apply_overrides(cfg)


def _resolve_credentials_thin(
    cfg: Any, environment: str, *, allow_prompt: bool = False,
) -> tuple[str | None, str | None]:
    """Resolve client_id + client_secret via the same cascade the CLI uses."""
    from swing.integrations.schwab.auth import resolve_credentials_env_or_prompt
    return resolve_credentials_env_or_prompt(
        cfg, environment, allow_prompt=allow_prompt,
    )


def _construct_client_thin(
    *, cfg: Any, environment: str, client_id: str, client_secret: str,
) -> Any:
    """Construct an authenticated schwabdev client via the shared helper.

    BINDING: invokes with ALL 4 named args per Codex R6 M#1 + writing-plans
    forward-binding lesson #1.
    """
    from swing.integrations.schwab.auth import construct_authenticated_client
    return construct_authenticated_client(
        cfg=cfg,
        environment=environment,
        client_id=client_id,
        client_secret=client_secret,
    )


def _bootstrap_authenticated_client(
    *, environment: str, config_path: Path | None = None,
) -> tuple[Any, Any]:
    """Bootstrap path — load cfg → apply overrides → resolve creds → construct.

    Test 7 patches the four thin helpers above + asserts this function
    invokes them in order with the exact contracts the gate documents.

    Returns:
        Tuple `(client, cfg)`. Caller derives `account_hash` +
        per-environment paths from `cfg.integrations.schwab.*`.
    """
    cfg_pre = _load_cfg(config_path)
    cfg = _apply_overrides_thin(cfg_pre)
    client_id, client_secret = _resolve_credentials_thin(
        cfg, environment, allow_prompt=False,
    )
    if not client_id or not client_secret:
        raise SystemExit(
            "FAILED: Schwab credentials unresolved at recording time. "
            "Set SCHWAB_CLIENT_ID + SCHWAB_CLIENT_SECRET env vars OR "
            "configure ~/swing-data/user-config.toml under "
            "[integrations.schwab].client_id + .client_secret. "
            "See docs/runbooks/schwab-cassette-recording.md §3.",
        )
    client = _construct_client_thin(
        cfg=cfg,
        environment=environment,
        client_id=client_id,
        client_secret=client_secret,
    )
    return client, cfg


# ---------------------------------------------------------------------------
# Cassette ops + validation helpers.
# ---------------------------------------------------------------------------

def _resolve_repo_root() -> Path:
    """Locate the repo root by walking up from this script."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "scripts").exists() and (parent / "swing").exists():
            return parent
    raise FileNotFoundError(
        f"could not locate repo root walking up from {here}",
    )


def _resolve_cassette_path(order_type: str) -> Path:
    """Cassette file path per plan §A.1.0 acceptance criterion #3."""
    root = _resolve_repo_root()
    return root / CASSETTE_DIR_REL / f"test_e2e_{order_type}.yaml"


def _load_shared_vcr_kwargs() -> dict[str, Any]:
    """Import the shared `vcr_config` fixture dict from `tests/conftest.py`.

    Test 3 covers the import. Production callsite uses this to ensure the
    cassette filter applied at recording time matches what the test suite
    consumes at replay time (single source of truth for sanitization config).
    """
    try:
        import tests.conftest as conftest_mod
        fixture = getattr(conftest_mod, "vcr_config", None)
        if fixture is None:
            raise AttributeError("vcr_config fixture not found in tests.conftest")
        underlying = (
            getattr(fixture, "__wrapped__", None)
            or getattr(fixture, "func", None)
        )
        if underlying is None:
            raise AttributeError(
                "vcr_config fixture has no __wrapped__ or .func attribute",
            )
        cfg = underlying()
        if not isinstance(cfg, dict):
            raise TypeError(
                f"vcr_config returned {type(cfg).__name__}; expected dict",
            )
        return cfg
    except Exception as exc:
        # Codex R2 Major #2 fix — fail closed per single-source-of-truth
        # discipline. The previous "inline fallback dict" omitted
        # `before_record_request` (URI accountHash path scrubbing per
        # Codex R2 Critical #1) AND `before_record_response` (JSON-key
        # value scrubbing for accountNumber/accountHash/access_token/
        # refresh_token/etc.). If conftest import fails for ANY reason,
        # recording with an incomplete filter would silently leak the
        # operator's accountHash + tokens into committed cassettes. Refuse
        # to proceed; surface operator-actionable error.
        raise SystemExit(
            f"FAILED: tests.conftest.vcr_config import failed ({exc!r}); "
            f"the recording script REFUSES to fall back to an inline "
            f"filter dict because that risks losing the "
            f"before_record_request + before_record_response sanitization "
            f"hooks (which would silently leak accountHash + tokens into "
            f"committed cassettes). Operator action: invoke this script "
            f"from inside the project's worktree where tests/conftest.py "
            f"is importable, OR install pytest-recording in your env if "
            f"the import error is dependency-related."
        ) from exc


def _validate_cassette_contains_order_type(
    *,
    cassette_path: Path,
    order_type: str,
    recorded_orders: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Post-record validation gate per AC#7 bullet 4 + Codex R4 M#2.

    Validates that at least one order in `recorded_orders` matches the
    requested order_type AND carries non-empty
    `orderActivityCollection[].executionLegs[]`.

    Returns:
        (True, '') on success.
        (False, '<operator-actionable msg>') on failure.
    """
    predicate = ORDER_TYPE_PREDICATES.get(order_type)
    if predicate is None:
        return False, (
            f"FAILED: unknown order_type {order_type!r}; cannot validate "
            f"cassette {cassette_path.name}."
        )
    matched_orders = 0
    matched_with_legs = 0
    for order in recorded_orders:
        if not isinstance(order, dict):
            continue
        ot = order.get("orderType", "")
        if ot not in predicate["orderType"]:
            continue
        status = order.get("status", "")
        if status not in predicate["status"]:
            continue
        legs = order.get("orderLegCollection", [])
        if not isinstance(legs, list) or not legs:
            continue
        leg0 = legs[0] if isinstance(legs[0], dict) else {}
        instruction = leg0.get("instruction", "")
        if instruction not in predicate["instruction"]:
            continue
        matched_orders += 1
        # Check for non-empty executionLegs across orderActivityCollection.
        activities = order.get("orderActivityCollection", [])
        if not isinstance(activities, list):
            continue
        for act in activities:
            if not isinstance(act, dict):
                continue
            if act.get("activityType") != "EXECUTION":
                continue
            exec_legs = act.get("executionLegs", [])
            if isinstance(exec_legs, list) and len(exec_legs) >= 1:
                matched_with_legs += 1
                break
    if matched_with_legs >= 1:
        return True, ""
    msg = (
        f"FAILED: cassette {cassette_path} contains no {order_type!r} orders "
        f"with non-empty orderActivityCollection[].executionLegs[]. "
        f"Recent recorded orders matching {order_type!r}: {matched_orders}; "
        f"of those, with executionLegs[]: {matched_with_legs}. "
        f"Operator action: (a) widen --days window; (b) ensure a recent "
        f"{order_type} filled within the lookback; (c) re-run after placing "
        f"such an order in TOS / Schwab Mobile."
    )
    return False, msg


def _scan_cassette_for_sentinel_leak(cassette_path: Path) -> list[str]:
    """Sentinel-leak audit per plan §G.4 + AC#7 bullet 8.

    Reads the cassette file bytes + scans for unsanitized patterns. Returns
    list of `(pattern_name, sample_match)` strings; empty list when clean.
    """
    if not cassette_path.exists():
        return []
    try:
        text = cassette_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"<read-error: {exc!r}>"]
    findings: list[str] = []
    for pattern_re, name in _LEAK_PATTERNS:
        try:
            m = re.search(pattern_re, text)
        except re.error:
            continue
        if m:
            sample = m.group(0)
            # Truncate sample to a reasonable display length.
            if len(sample) > 80:
                sample = sample[:80] + "..."
            findings.append(f"{name}: {sample!r}")
    return findings


def _safe_delete_cassette(cassette_path: Path) -> None:
    """Delete the cassette file if present, swallowing OSError to remain
    crash-safe."""
    try:
        if cassette_path.exists():
            cassette_path.unlink()
    except OSError as exc:
        _log.warning("cassette delete failed for %s: %s", cassette_path, exc)


def _read_cassette_response_orders(
    cassette_path: Path,
) -> list[dict[str, Any]]:
    """Codex R2 Major #1 fix — re-load the just-written cassette FROM DISK
    + parse the persisted response body for post-record validation.

    Plan §A.1.0 acceptance criterion #7 bullet 4 BINDING: validation MUST
    target the persisted YAML payload, NOT the in-memory live API response.
    This catches cassette write failures, body-sanitization mutations,
    + path/serialization edge cases that the in-memory check cannot see.

    Returns the parsed `interactions[0].response.body.string` as a list of
    Schwab order dicts. Returns empty list on any parse error (the caller
    treats empty as validation failure with operator-actionable message).
    """
    try:
        import yaml as _yaml
    except ImportError:
        _log.warning(
            "PyYAML not installed; cannot re-read cassette %s for "
            "post-record validation; returning empty list",
            cassette_path,
        )
        return []
    if not cassette_path.exists():
        return []
    try:
        with cassette_path.open(encoding="utf-8") as f:
            cassette = _yaml.safe_load(f)
    except (OSError, _yaml.YAMLError) as exc:
        _log.warning(
            "cassette re-read failed for %s: %s",
            cassette_path, exc,
        )
        return []
    interactions = (cassette or {}).get("interactions", [])
    if not interactions:
        return []
    try:
        body_str = interactions[0]["response"]["body"]["string"]
        parsed = json.loads(body_str)
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        _log.warning(
            "cassette body parse failed for %s: %s",
            cassette_path, exc,
        )
        return []
    return parsed if isinstance(parsed, list) else []


# ---------------------------------------------------------------------------
# Recording loop.
# ---------------------------------------------------------------------------

def _record_one_order_type(
    *,
    client: Any,
    account_hash: str,
    order_type: str,
    days: int,
    max_results: int,
    vcr_kwargs: dict[str, Any],
) -> int:
    """Record cassette for a single order_type. Returns 0 on success, non-zero
    on failure (caller aggregates + decides exit code)."""
    import vcr

    cassette_path = _resolve_cassette_path(order_type)
    cassette_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    from_time = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Recording phase — open a cassette in record_mode=new_episodes.
    raw_orders: list[dict[str, Any]] = []
    try:
        with vcr.use_cassette(
            str(cassette_path),
            record_mode="new_episodes",
            **vcr_kwargs,
        ):
            # schwabdev signature per swing/integrations/schwab/trader.py:365 +
            # tests/integrations/test_schwab_trader_kwarg_signatures.py:
            # `Client.account_orders(account_hash, from_str, to_str,
            # status=..., maxResults=...)` — accountHash + from + to are
            # POSITIONAL; status + maxResults are camelCase kwargs (per
            # CLAUDE.md gotcha family).
            response = client.account_orders(
                account_hash,
                from_time,
                to_time,
                status="FILLED",
                maxResults=max_results,
            )
            # Response is either a list (mapped) or requests.Response-like
            # (schwabdev returns the raw response object pre-mapper). We
            # accept both shapes for the post-record validation read.
            if isinstance(response, list):
                raw_orders = response
            else:
                try:
                    raw_orders = response.json()
                except Exception:  # noqa: BLE001
                    raw_orders = []
    except Exception as exc:  # noqa: BLE001
        _log.error(
            "recording exception for order_type=%s: %s",
            order_type, exc,
        )
        _safe_delete_cassette(cassette_path)
        sys.stderr.write(
            f"FAILED: recording exception for {order_type}: "
            f"{type(exc).__name__}: {exc}\n",
        )
        return 2

    # Post-record validation gate — Codex R2 Major #1 fix.
    # Plan §A.1.0 acceptance criterion #7 bullet 4 requires re-loading the
    # JUST-WRITTEN CASSETTE FROM DISK (NOT the in-memory live response) +
    # parsing its response body for the validation. This catches:
    # - cassette write that didn't actually serialize (vcrpy edge case)
    # - cassette body sanitized into a non-replayable JSON shape
    # - cassette path that points somewhere unexpected
    # The in-memory `raw_orders` was the live API response; the post-write
    # YAML may differ if a filter mutated the body.
    persisted_orders = _read_cassette_response_orders(cassette_path)
    ok, msg = _validate_cassette_contains_order_type(
        cassette_path=cassette_path,
        order_type=order_type,
        recorded_orders=persisted_orders,
    )
    if not ok:
        _safe_delete_cassette(cassette_path)
        sys.stderr.write(msg + "\n")
        return 3

    # Sentinel-leak audit — re-read the just-written cassette.
    leaks = _scan_cassette_for_sentinel_leak(cassette_path)
    if leaks:
        _safe_delete_cassette(cassette_path)
        sys.stderr.write(
            f"FAILED: sentinel-leak audit found unsanitized substrings in "
            f"{cassette_path}: {leaks}. Cassette DELETED to prevent commit. "
            f"Operator action: extend tests/conftest.py:vcr_config filters + "
            f"re-run.\n",
        )
        return 4

    sys.stdout.write(
        f"OK: recorded + validated {cassette_path.relative_to(_resolve_repo_root())} "
        f"({len(raw_orders) if isinstance(raw_orders, list) else 0} orders)\n",
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Script entry point. Returns process exit code."""
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    client, cfg = _bootstrap_authenticated_client(
        environment=args.environment,
        config_path=Path(args.config),
    )
    account_hash = getattr(
        getattr(cfg.integrations, "schwab", None), "account_hash", None,
    )
    if not account_hash or not isinstance(account_hash, str):
        sys.stderr.write(
            "FAILED: cfg.integrations.schwab.account_hash is unset; cannot "
            "invoke Schwab account-scoped endpoints. Set it in "
            "~/swing-data/user-config.toml under [integrations.schwab] OR "
            "via `swing schwab status --environment production` which "
            "populates the field on first link. See "
            "docs/runbooks/schwab-cassette-recording.md §3.\n",
        )
        return 1
    vcr_kwargs = _load_shared_vcr_kwargs()

    failures = 0
    for order_type in args.order_types_list:
        rc = _record_one_order_type(
            client=client,
            account_hash=account_hash,
            order_type=order_type,
            days=args.days,
            max_results=args.max_results,
            vcr_kwargs=vcr_kwargs,
        )
        if rc != 0:
            failures += 1

    if failures:
        sys.stderr.write(
            f"FAILED: {failures} of {len(args.order_types_list)} order types "
            f"did not record cleanly. See messages above for operator-actionable "
            f"remediation.\n",
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
