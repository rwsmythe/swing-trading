"""Record the Schwab live-quote cassette (data-integrity arc Gate 4 enablement).

Phase 15 / data-integrity arc Slice-B Gate 4. Produces the sanitized VCR
cassette ``tests/integrations/schwab/cassettes/quote_regular_fields.yaml`` from
ONE live ``client.quotes(symbols=[...], fields="quote")`` call so the slow gate
test ``tests/integrations/schwab/test_quote_fields_live.py`` (a pure substring
grep for the 4 ``regularMarket*`` fields the B2 mapper consumes) passes after
the operator's market-open recording step.

Operator workflow (runbook ``docs/runbooks/schwab-cassette-recording.md``
section "Quote cassette (Gate 4 / OQ-3)"):

    python scripts/record_schwab_quote_cassette.py --environment production

This is a DEV-TOOLING script: no ``swing/`` runtime change, no schema change
(v24 holds). It REUSES (imports, never duplicates) the order recorder's
helpers in ``scripts/record_schwab_cassettes.py``:

- ``_bootstrap_authenticated_client`` — the auth path (load cfg -> apply
  overrides -> resolve creds -> construct client), same as ``swing schwab
  fetch``.
- ``_load_shared_vcr_kwargs`` — imports ``tests/conftest.py:vcr_config`` (the
  single source of truth sanitization). It FAILS CLOSED (``SystemExit``) if
  conftest can't be imported; this script NEVER inlines a fallback filter dict
  (that would risk committing the operator's accountHash + tokens).
- ``_scan_cassette_for_sentinel_leak`` — the leak-audit regex catalog.
- ``_resolve_repo_root`` / ``_safe_delete_cassette`` — path + cleanup helpers.

OQ-3 decision (operator's, at record time): under ``fields="quote"`` Schwab may
omit bid/ask. The B2 mapper requires last AND bid AND ask, so if either is
absent every Schwab quote drops to yfinance (the path goes dead). The recorder
SURFACES this -- it does not pre-decide. On a missing field the cassette is
deleted + the script exits non-zero with an actionable message: re-run with
``--fields all`` to widen, OR accept the yfinance-drop (B2 stays L1-correct
either way) and do NOT commit the cassette.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# Distinct exit code: a failing-cassette cleanup could not delete the file (it
# may carry unsanitized data). Surfaced so the operator removes it by hand.
DELETE_FAILED_CODE = 6

# Defer heavy imports (vcr, swing.config, the order-recorder module) until they
# are needed so `--help` stays snappy, mirroring the order recorder.

_log = logging.getLogger("scripts.record_schwab_quote_cassette")

# The 4 regular-session quote fields the B2 mapper consumes; the gate test
# greps the cassette text for ALL of these.
REGULAR_SESSION_FIELDS: tuple[str, ...] = (
    "regularMarketLastPrice",
    "regularMarketTradeTime",
    "regularMarketBidPrice",
    "regularMarketAskPrice",
)

# The EXACT cassette path the gate test asserts on
# (tests/integrations/schwab/test_quote_fields_live.py). Note the directory
# order `schwab/cassettes` (the REVERSE of the order recorder's
# `cassettes/schwab`).
QUOTE_CASSETTE_RELPATH = Path(
    "tests/integrations/schwab/cassettes/quote_regular_fields.yaml",
)


# ---------------------------------------------------------------------------
# Order-recorder reuse (import, do NOT duplicate).
# ---------------------------------------------------------------------------

_ORDER_MOD: Any = None


def _order_module() -> Any:
    """Load the order recorder (`scripts/record_schwab_cassettes.py`) by file
    path + cache it. Loading by absolute path is independent of `sys.path`, so
    it works whether this script is run directly or imported in a test.

    Side effect: prepends the repo root to `sys.path` so the order recorder's
    `_load_shared_vcr_kwargs` can `import tests.conftest` (the single source of
    truth sanitization config) when this script is invoked as
    `python scripts/record_schwab_quote_cassette.py` (whose `sys.path[0]` is
    `scripts/`, not the repo root).
    """
    global _ORDER_MOD
    if _ORDER_MOD is not None:
        return _ORDER_MOD
    order_path = Path(__file__).resolve().parent / "record_schwab_cassettes.py"
    spec = importlib.util.spec_from_file_location(
        "record_schwab_cassettes", str(order_path),
    )
    if spec is None or spec.loader is None:
        raise SystemExit(
            f"FAILED: cannot load the order recorder module at {order_path}; "
            f"the quote recorder reuses its sanitization + auth helpers.",
        )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    repo_root = str(mod._resolve_repo_root())
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _ORDER_MOD = mod
    return mod


def _bootstrap_authenticated_client(
    *, environment: str, config_path: Path | None = None,
) -> tuple[Any, Any]:
    """Delegate to the order recorder's auth bootstrap (single source)."""
    return _order_module()._bootstrap_authenticated_client(
        environment=environment, config_path=config_path,
    )


def _load_shared_vcr_kwargs() -> dict[str, Any]:
    """Delegate to the order recorder's FAIL-CLOSED sanitization loader.

    Raises `SystemExit` (propagated from the order recorder) if
    `tests/conftest.py:vcr_config` can't be imported -- this script NEVER
    falls back to an inline filter dict.
    """
    return _order_module()._load_shared_vcr_kwargs()


def _scan_cassette_for_sentinel_leak(cassette_path: Path) -> list[str]:
    """Delegate to the order recorder's leak-audit catalog (single source)."""
    return _order_module()._scan_cassette_for_sentinel_leak(cassette_path)


def _safe_delete_cassette(cassette_path: Path) -> None:
    """Delegate to the order recorder's crash-safe cassette delete."""
    _order_module()._safe_delete_cassette(cassette_path)


def _resolve_repo_root() -> Path:
    """Delegate to the order recorder's repo-root resolver (single source)."""
    return _order_module()._resolve_repo_root()


def _delete_cassette_verifying(cassette_path: Path) -> bool:
    """Delete the cassette + VERIFY it is gone.

    The delegated `_safe_delete_cassette` swallows `OSError` (e.g. a Windows
    file lock) and never confirms removal, so a failed delete on a leaking /
    invalid cassette could otherwise pass silently. Returns True if the file is
    gone afterwards (or never existed), False if it still exists.
    """
    _safe_delete_cassette(cassette_path)
    return not cassette_path.exists()


def _fail_and_clean(cassette_path: Path, msg: str, code: int) -> int:
    """Emit `msg`, delete the cassette, and verify removal.

    On a verified delete returns `code`. If the cassette cannot be deleted,
    escalate loudly (it may carry unsanitized data) + return the distinct
    DELETE-FAILED code so the operator removes it by hand before committing.
    """
    sys.stderr.write(msg + "\n")
    if _delete_cassette_verifying(cassette_path):
        return code
    sys.stderr.write(
        f"CRITICAL: could not delete {cassette_path} -- DELETE FAILED. The "
        f"cassette may contain unsanitized data; remove it MANUALLY before "
        f"committing.\n",
    )
    return DELETE_FAILED_CODE


# ---------------------------------------------------------------------------
# Argparse.
# ---------------------------------------------------------------------------

def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="record_schwab_quote_cassette",
        description=(
            "Record the sanitized Schwab live-quote cassette "
            "(tests/integrations/schwab/cassettes/quote_regular_fields.yaml) "
            "for the data-integrity arc Gate 4. Run during regular market "
            "hours with live production tokens. Reuses the order recorder's "
            "fail-closed sanitization + leak-scan."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "OQ-3: under --fields quote Schwab may omit bid/ask; the B2 mapper "
            "needs last AND bid AND ask. On a missing field the cassette is "
            "deleted + the script exits non-zero -- re-run with --fields all "
            "to widen, OR accept the yfinance-drop (B2 stays L1-correct) and "
            "do NOT commit the cassette. --environment is REQUIRED."
        ),
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("production", "sandbox"),
        help="Schwab tokens DB environment (REQUIRED).",
    )
    parser.add_argument(
        "--symbols",
        default="AAPL",
        help=(
            "Comma-separated symbol(s) to quote. Default: AAPL. A single "
            "large-cap regular-session symbol is sufficient for the gate."
        ),
    )
    parser.add_argument(
        "--fields",
        default="quote",
        help=(
            "schwabdev quotes `fields` selection. Default: quote (the "
            "regularMarket* block). Re-run with `all` per OQ-3 if bid/ask are "
            "absent under `quote`."
        ),
    )
    parser.add_argument(
        "--config",
        type=str,
        default="swing.config.toml",
        help=(
            "Path to swing.config.toml (mirrors `swing --config`). "
            "Default: swing.config.toml relative to cwd."
        ),
    )
    ns = parser.parse_args(argv)
    ns.symbols_list = [s.strip() for s in str(ns.symbols).split(",") if s.strip()]
    if not ns.symbols_list:
        parser.error("--symbols resolved to an empty list; pass at least one symbol.")
    return ns


# ---------------------------------------------------------------------------
# Validation.
# ---------------------------------------------------------------------------

def _validate_quote_cassette_has_regular_fields(
    cassette_path: Path,
) -> tuple[bool, str]:
    """Post-record validation against the PERSISTED cassette file.

    Re-reads the written cassette from disk (mirroring the order recorder's
    discipline) + asserts ALL 4 `regularMarket*` field names are present --
    the same substring contract the slow gate test enforces.

    Returns:
        (True, '') when all 4 fields are present.
        (False, '<operator-actionable OQ-3 message>') otherwise.
    """
    if not cassette_path.exists():
        return False, (
            f"FAILED: cassette {cassette_path} was not written; the recording "
            f"step produced no file. Confirm live tokens + regular market "
            f"hours, then re-run."
        )
    try:
        text = cassette_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"FAILED: cannot read cassette {cassette_path}: {exc!r}"
    missing = [f for f in REGULAR_SESSION_FIELDS if f not in text]
    if not missing:
        return True, ""
    msg = (
        f"FAILED: cassette {cassette_path} is missing regular-session quote "
        f"field(s): {', '.join(missing)}. Under fields=\"quote\" the Schwab "
        f"response did not carry bid/ask. The B2 mapper requires last AND bid "
        f"AND ask, so every Schwab quote would drop to yfinance (the path goes "
        f"dead). Operator decision (OQ-3): re-run with --fields all to widen "
        f"the selection, OR accept the yfinance-drop (B2 stays L1-correct "
        f"either way) and do NOT commit this cassette."
    )
    return False, msg


def _validate_quote_cassette_single_interaction(
    cassette_path: Path,
) -> tuple[bool, str]:
    """Enforce the single-quote-interaction contract on the persisted cassette.

    schwabdev v3 refreshes tokens synchronously per request; if the access
    token is stale at record time the first `client.quotes(...)` call triggers
    an OAuth token-refresh HTTP exchange that `vcr.use_cassette` would ALSO
    capture -- yielding a 2-interaction cassette (refresh + quote). The shared
    sanitization + leak-scan scrub the refresh tokens, but the recorder's
    contract is a SINGLE clean quote interaction. Reject anything else so a
    stray OAuth-refresh interaction is never committed.

    Returns (True, '') for exactly one interaction whose request targets the
    quotes endpoint; (False, '<operator-actionable msg>') otherwise.
    """
    try:
        import yaml as _yaml
    except ImportError:
        return False, (
            f"FAILED: PyYAML unavailable; cannot verify {cassette_path} is a "
            f"single quote interaction. Install the dev extra + re-run."
        )
    if not cassette_path.exists():
        return False, f"FAILED: cassette {cassette_path} was not written."
    try:
        with cassette_path.open(encoding="utf-8") as fh:
            cassette = _yaml.safe_load(fh)
    except (OSError, _yaml.YAMLError) as exc:
        return False, f"FAILED: cannot parse cassette {cassette_path}: {exc!r}"
    interactions = (cassette or {}).get("interactions", []) or []
    if len(interactions) != 1:
        return False, (
            f"FAILED: cassette {cassette_path} has {len(interactions)} "
            f"interaction(s); expected exactly 1 (the quote call). A stale-token "
            f"OAuth refresh was likely captured alongside the quote. Run "
            f"`swing schwab refresh` (or confirm `swing schwab status "
            f"--environment <env>` reports LIVE) BEFORE recording so the "
            f"cassette is a single clean quote interaction, then re-run."
        )
    uri = ""
    first = interactions[0]
    if isinstance(first, dict):
        request = first.get("request")
        if isinstance(request, dict):
            uri = str(request.get("uri", "") or "")
    # Require the request PATH (not the query string) to be the quotes
    # endpoint, so an unrelated URI carrying `?fields=quote` cannot pass.
    path = urlparse(uri).path.rstrip("/")
    if not path.endswith("/quotes"):
        return False, (
            f"FAILED: the sole recorded interaction in {cassette_path} does not "
            f"target the Schwab quotes endpoint (uri={uri!r}). Confirm tokens "
            f"are LIVE + re-run so the quote call is the only captured "
            f"interaction."
        )
    return True, ""


def _count_quote_symbols(resp: Any) -> int:
    """Best-effort count of symbols in a quotes response (for the printout)."""
    data = resp
    json_method = getattr(resp, "json", None)
    if callable(json_method):
        try:
            data = json_method()
        except Exception:  # noqa: BLE001 -- printout only; never fatal
            return 0
    if isinstance(data, (dict, list)):
        return len(data)
    return 0


# ---------------------------------------------------------------------------
# Recording.
# ---------------------------------------------------------------------------

def _record_quote_cassette(
    *,
    client: Any,
    symbols: list[str],
    fields: str,
    cassette_path: Path,
    vcr_kwargs: dict[str, Any],
) -> int:
    """Record one `client.quotes(...)` call into the gate cassette under the
    shared sanitization, then validate + leak-scan the persisted file.

    Returns 0 on success; non-zero (and DELETES the cassette) on any failure so
    a leaking / incomplete cassette can never be committed.
    """
    import vcr

    cassette_path.parent.mkdir(parents=True, exist_ok=True)
    # Delete any existing cassette FIRST: record_mode="new_episodes" APPENDS,
    # so a rerun would leave the stale prior interaction in interactions[0].
    # Force a single-interaction cassette (mirrors the order recorder's R3 fix).
    _safe_delete_cassette(cassette_path)

    try:
        with vcr.use_cassette(
            str(cassette_path), record_mode="new_episodes", **vcr_kwargs,
        ):
            resp = client.quotes(symbols=symbols, fields=fields)
        symbol_count = _count_quote_symbols(resp)
    except Exception as exc:  # noqa: BLE001 -- surface + clean up, never leak
        return _fail_and_clean(
            cassette_path,
            f"FAILED: recording exception: {type(exc).__name__}: {exc}",
            2,
        )
    except BaseException:
        # KeyboardInterrupt / SystemExit etc: VCR may have flushed a partial,
        # un-validated cassette on __exit__. Delete it (best effort) then
        # re-raise so the interruption is never silently swallowed.
        _safe_delete_cassette(cassette_path)
        raise

    ok, msg = _validate_quote_cassette_has_regular_fields(cassette_path)
    if not ok:
        return _fail_and_clean(cassette_path, msg, 3)

    ok, msg = _validate_quote_cassette_single_interaction(cassette_path)
    if not ok:
        return _fail_and_clean(cassette_path, msg, 5)

    leaks = _scan_cassette_for_sentinel_leak(cassette_path)
    if leaks:
        return _fail_and_clean(
            cassette_path,
            f"FAILED: sentinel-leak audit found unsanitized substrings in "
            f"{cassette_path}: {leaks}. Operator action: extend "
            f"tests/conftest.py:vcr_config filters + re-run.",
            4,
        )

    rel: Path = cassette_path
    with contextlib.suppress(ValueError):
        rel = cassette_path.relative_to(_resolve_repo_root())
    sys.stdout.write(
        f"OK: recorded + validated {rel} "
        f"(symbols={','.join(symbols)}, fields={fields}, "
        f"quote_symbols={symbol_count})\n",
    )
    for field in REGULAR_SESSION_FIELDS:
        sys.stdout.write(f"  present: {field}\n")
    sys.stdout.write(
        "Next: git add the cassette + run `pytest "
        "tests/integrations/schwab/test_quote_fields_live.py` (slow).\n",
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    client, _cfg = _bootstrap_authenticated_client(
        environment=args.environment, config_path=Path(args.config),
    )
    vcr_kwargs = _load_shared_vcr_kwargs()
    cassette_path = _resolve_repo_root() / QUOTE_CASSETTE_RELPATH
    return _record_quote_cassette(
        client=client,
        symbols=args.symbols_list,
        fields=args.fields,
        cassette_path=cassette_path,
        vcr_kwargs=vcr_kwargs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
