"""One-shot cleanup: correct misleading Schwab audit rows from T-A.4 phase-2
operator-paired verification (2026-05-14).

Context — see hotfix commit `fix(schwab): T-A.4 hotfix — validate tokens +
accounts shape + reorder schema check (phase-2 findings)`:

The original T-A.4 implementation did not check ``client.tokens.access_token``
after ``schwabdev.Client(...)`` returned. Operator's live setup run hit the
30-second Schwab `code` expiry window; schwabdev printed the error + retried
internally + returned a Client object without raising — and the audit row
landed with ``status='success'`` despite no tokens being obtained. The
second audit row (``accounts.linked``) then also landed ``success`` because
``client.account_linked()`` returned a dict-shaped error envelope that
``_stub_call_account_linked`` did not validate (KeyError: 0 surfaced later
in the chosen-account path).

The hotfix (D1+D2) corrects future runs. This script corrects the two
misleading rows already in the operator's production ``swing.db``.

Idempotent:
  * Reads rows by ``call_id IN (1, 2)``.
  * Only UPDATEs rows whose ``status='success'`` (no-op if already
    ``auth_failed``).
  * Stamps a ``manual correction`` note in ``error_message`` so the
    correction is auditable.

Usage:
    cd <repo-root>
    python scripts/fix_phase2_misleading_audit_rows.py

Default DB path:  ``%USERPROFILE%/swing-data/swing.db``  (Windows).
Override with ``--db-path`` if needed.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

_CORRECTION_NOTE = (
    "<manual correction 2026-05-14: row was originally recorded "
    "status='success' but operator-paired verification (T-A.4 phase-2) "
    "showed the OAuth exchange actually failed; corrected to "
    "'auth_failed' per hotfix audit-trail discipline>"
)

# call_id → expected endpoint pair for the two misleading rows.
_TARGET_ROWS: list[tuple[int, str]] = [
    (1, "oauth.code_exchange"),
    (2, "accounts.linked"),
]


def _default_db_path() -> Path:
    profile = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if profile is None:
        raise RuntimeError("Neither USERPROFILE nor HOME is set")
    return Path(profile) / "swing-data" / "swing.db"


def fix(db_path: Path, *, dry_run: bool = False) -> int:
    """Return the number of rows updated. dry_run=True reports without writing."""
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        return 0
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        updates = 0
        for call_id, expected_endpoint in _TARGET_ROWS:
            row = conn.execute(
                "SELECT call_id, endpoint, status, error_message "
                "FROM schwab_api_calls WHERE call_id = ?",
                (call_id,),
            ).fetchone()
            if row is None:
                print(f"INFO: call_id={call_id} not found; skipping")
                continue
            if row["endpoint"] != expected_endpoint:
                print(
                    f"WARN: call_id={call_id} endpoint mismatch "
                    f"(expected {expected_endpoint!r}, got "
                    f"{row['endpoint']!r}); skipping",
                )
                continue
            if row["status"] != "success":
                print(
                    f"INFO: call_id={call_id} already status="
                    f"{row['status']!r}; skipping (idempotent)",
                )
                continue
            new_err = _CORRECTION_NOTE
            if dry_run:
                print(
                    f"DRY-RUN: would UPDATE call_id={call_id} "
                    f"({expected_endpoint!r}) status -> 'auth_failed'",
                )
            else:
                conn.execute(
                    "UPDATE schwab_api_calls "
                    "SET status = 'auth_failed', error_message = ? "
                    "WHERE call_id = ?",
                    (new_err, call_id),
                )
                conn.commit()
                print(
                    f"OK: UPDATED call_id={call_id} ({expected_endpoint!r}) "
                    f"status='success' -> 'auth_failed'",
                )
            updates += 1
        return updates
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to swing.db (default: %USERPROFILE%/swing-data/swing.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Report planned updates without writing.",
    )
    args = parser.parse_args(argv)
    db_path = args.db_path or _default_db_path()
    print(f"Target DB: {db_path}")
    updates = fix(db_path, dry_run=args.dry_run)
    print(f"Done. {updates} row(s) {'would be ' if args.dry_run else ''}updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
