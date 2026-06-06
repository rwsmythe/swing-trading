import io
import tokenize
from pathlib import Path
import pytest

# TOKENIZE-based detection (Codex R1 major #3 + R2 major: alias-aware AND
# docstring/comment-proof). Finds only REAL `sqlite3|_sqlite3 . connect (` call
# token sequences; STRING (docstring) + COMMENT tokens are never NAME/OP tokens,
# so prose mentions of "sqlite3.connect(...)" are correctly ignored.

# These files have ZERO legitimate raw opens after routing -- every open is a
# live swing.db open that must go through open_connection.
_LIVE_OPEN_FILES = [
    "swing/web/routes/account.py",
    "swing/web/routes/config.py",
    "swing/web/routes/metrics.py",
    "swing/web/routes/reconcile.py",
    "swing/web/routes/schwab.py",
    "swing/web/routes/watchlist.py",
    "swing/web/view_models/schwab.py",
    "swing/web/app.py",
]


def _raw_connect_call_lines(rel):
    """Line numbers of every real `sqlite3.connect(` / `_sqlite3.connect(` CALL."""
    text = Path(rel).read_text(encoding="utf-8")
    toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    lines = []
    for i, t in enumerate(toks):
        if (
            t.type == tokenize.NAME and t.string == "connect"
            and i >= 2
            and toks[i - 1].type == tokenize.OP and toks[i - 1].string == "."
            and toks[i - 2].type == tokenize.NAME
            and toks[i - 2].string in ("sqlite3", "_sqlite3")
            and i + 1 < len(toks)
            and toks[i + 1].type == tokenize.OP and toks[i + 1].string == "("
        ):
            lines.append(t.start[0])
    return sorted(set(lines))


@pytest.mark.parametrize("rel", _LIVE_OPEN_FILES)
def test_no_raw_sqlite3_connect_for_live_db(rel):
    # Every live-swing.db open routes through open_connection (busy_timeout).
    src = Path(rel).read_text(encoding="utf-8").splitlines()
    offenders = [src[n - 1].strip() for n in _raw_connect_call_lines(rel)]
    assert offenders == [], f"{rel} still has raw sqlite3 connect call: {offenders}"


def test_cli_remaining_raw_connect_are_backup_dest_only():
    # cli.py legitimately KEEPS the db-migrate backup DESTINATION open
    # (dst = _sqlite3.connect(backup_path)). EVERY OTHER raw open (the divergence
    # check, the db-migrate src, the version probe, the two diagnose --db opens)
    # must route through open_connection. So the ONLY raw connect-call line
    # remaining must reference `backup_path`; anything else is an unrouted live
    # open and fails here.
    src = Path("swing/cli.py").read_text(encoding="utf-8").splitlines()
    offenders = [
        src[n - 1].strip()
        for n in _raw_connect_call_lines("swing/cli.py")
        if "backup_path" not in src[n - 1]
    ]
    assert offenders == [], f"unrouted live open(s) in cli.py: {offenders}"
