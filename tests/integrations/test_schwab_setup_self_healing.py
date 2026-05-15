"""T-A.2 — `swing schwab setup` self-heals stale tokens DB before paste-back.

Phase 12 Sub-bundle A T-A.2 acceptance tests (7 binding patterns).

Problem solved: when `~/swing-data/schwab-tokens.{env}.db` exists from a prior
session AND the refresh_token has expired, schwabdev's `Client.__init__`
auto-attempts a refresh + bails hard with `unsupported_token_type`. The
setup paste-back code never runs. Pre-T-A.2 operator recovery was the
`logout → setup` sequence (per CLAUDE.md gotcha). T-A.2 self-heals: setup
auto-detects + atomically renames the stale tokens DB BEFORE invoking
schwabdev.

Audit-row disposition LOCK (per AC3): a single audit row is emitted at
`endpoint='oauth.code_exchange'` (schema CHECK enum at v18 does NOT include
`oauth.tokens_db_rename` — brief deviation banked) with `status='success'`,
`surface='cli'`, `environment=<env>`, and `error_message` containing the
"auto-detected" + "renamed before paste-back" substrings so operators can
grep the audit log to find self-heal events. This audit row is SEPARATE
from + precedes the setup flow's own `oauth.code_exchange` audit row.

Test discipline:
  - USERPROFILE+HOME monkeypatch (CLAUDE.md gotcha — `_user_home` reads
    them unmonkeypatched; without both, writes would leak to operator's
    real ~/swing-data/).
  - schwabdev.Client stubbed BEFORE the call site references it.
  - `_utc_now` in auth.py monkeypatched to a deterministic timestamp for
    the collision-disambiguation test (Test 3).
  - Tests assert os.replace specifically (per CLAUDE.md cross-device-link
    gotcha) — Test 6 greps the auth.py source for `os.replace` usage.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.integrations.schwab import auth as auth_mod
from swing.integrations.schwab.auth import setup_paste_flow


_SENTINEL_ACCESS_TOKEN = "AUTH_BYTES_DO_NOT_LEAK_ABCDEF0123456789012345"
_SENTINEL_REFRESH_TOKEN = "REFRESH_BYTES_DO_NOT_LEAK_ZYXWVU09876543210987"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated USERPROFILE+HOME pointing at tmp_path.

    CRITICAL per CLAUDE.md gotcha: BOTH env vars must be monkeypatched;
    `_user_home()` in `swing/config_user.py` reads them unmonkeypatched
    and writes would otherwise leak to operator's real user-config.toml.
    """
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def cfg(home: Path) -> Any:
    """Minimal cfg object that exposes `cfg.integrations.schwab.callback_url`
    + `cfg.integrations.schwab.timeout_seconds` (the only fields
    `setup_paste_flow` reads from cfg)."""

    class _Schwab:
        callback_url = "https://127.0.0.1"
        timeout_seconds = 10

    class _Integrations:
        schwab = _Schwab()

    class _Cfg:
        integrations = _Integrations()

    return _Cfg()


@pytest.fixture
def conn(home: Path) -> sqlite3.Connection:
    """Initialised SQLite DB connection at ~/swing-data/swing.db so
    `audit_service.record_call_start` + `record_call_finish` can write.
    """
    from swing.data.db import ensure_schema
    db_path = home / "swing-data" / "swing.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = ensure_schema(db_path)
    yield conn
    conn.close()


class _FakeTokens:
    access_token = _SENTINEL_ACCESS_TOKEN
    refresh_token = _SENTINEL_REFRESH_TOKEN


class _FakeSchwabdevClient:
    """Test stub mimicking schwabdev.Client surface area.

    On construction, writes an empty JSON file at the resolved tokens_file
    path so subsequent assertions about "new tokens DB present at canonical
    path" can pass without invoking real schwabdev paste-back.
    """

    def __init__(self, *args: Any, accounts: list[dict] | None = None, **kwargs: Any) -> None:
        self._init_args = args
        self._init_kwargs = kwargs
        self.tokens = _FakeTokens()
        self._accounts = accounts if accounts is not None else [
            {"accountNumber": "12345678", "hashValue": "SINGLEHASH"},
        ]
        self.tokens_file = kwargs.get("tokens_file")
        # Simulate schwabdev writing the on-disk tokens file post-OAuth.
        if self.tokens_file:
            Path(self.tokens_file).write_text(
                '{"token_dictionary": {"access_token": "NEW", "refresh_token": "NEW"}}'
            )

    def account_linked(self) -> list[dict]:
        return self._accounts


def _patch_schwabdev_ok(monkeypatch: pytest.MonkeyPatch, accounts: list[dict] | None = None) -> None:
    """Patch schwabdev.Client to a benign stub."""
    import schwabdev

    def factory(*args: Any, **kwargs: Any) -> _FakeSchwabdevClient:
        return _FakeSchwabdevClient(*args, accounts=accounts, **kwargs)

    monkeypatch.setattr(schwabdev, "Client", factory)


def _patch_schwabdev_raises(
    monkeypatch: pytest.MonkeyPatch,
    exc: BaseException,
    *,
    after_tokens_file_check: bool = False,
) -> dict:
    """Patch schwabdev.Client so __init__ raises `exc`.

    Records whether the tokens_file pre-rename was already gone at the
    time schwabdev was invoked (i.e. our self-heal rename happened first).
    """
    import schwabdev
    state: dict = {"tokens_file_existed_pre_init": None}

    def factory(*args: Any, **kwargs: Any) -> _FakeSchwabdevClient:
        tokens_file = kwargs.get("tokens_file")
        state["tokens_file_existed_pre_init"] = (
            tokens_file is not None and Path(tokens_file).exists()
        )
        raise exc

    monkeypatch.setattr(schwabdev, "Client", factory)
    return state


def _read_audit_rows(home: Path) -> list[dict]:
    db_path = home / "swing-data" / "swing.db"
    c = sqlite3.connect(db_path)
    try:
        c.row_factory = sqlite3.Row
        return [
            dict(r) for r in c.execute(
                "SELECT * FROM schwab_api_calls ORDER BY call_id",
            ).fetchall()
        ]
    finally:
        c.close()


# ============================================================================
# Tests
# ============================================================================


def test_t_a_2_self_heal_renames_existing_tokens_db_before_paste_back(
    home: Path, cfg: Any, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 1 — existing tokens DB at canonical path → renamed pre-schwabdev.

    Plant existing tokens DB; invoke setup with happy-path schwabdev stub.
    Assert:
      - canonical path has a NEW tokens file (written by stub during paste-back),
      - SOME file matching `<canonical>.deleted-*` pattern exists (the renamed
        stale DB).
    """
    tokens_path = home / "swing-data" / "schwab-tokens.production.db"
    # Plant existing stale tokens DB.
    tokens_path.write_text("stale-tokens-payload")
    assert tokens_path.exists()

    _patch_schwabdev_ok(monkeypatch)

    result = setup_paste_flow(
        cfg=cfg,
        environment="production",
        client_id="my_client_id",
        client_secret="my_client_secret",
        conn=conn,
    )

    # Canonical path: stub wrote a JSON tokens file there.
    assert tokens_path.exists(), "new tokens file missing post-setup"
    # Renamed file: glob for the deleted-* sibling.
    renamed = list(home.glob("swing-data/schwab-tokens.production.db.deleted-*"))
    assert len(renamed) == 1, (
        f"expected exactly 1 renamed file; got {renamed}"
    )
    # Stale payload preserved in renamed file.
    assert renamed[0].read_text() == "stale-tokens-payload"
    # Sanity: setup returned the standard summary dict.
    assert result["environment"] == "production"
    assert result["account_hash"] == "SINGLEHASH"


def test_t_a_2_no_existing_tokens_db_no_rename_no_audit_row(
    home: Path, cfg: Any, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 2 — no existing tokens DB → setup proceeds without rename.

    Assert:
      - no `*.deleted-*` files appear post-call,
      - the rename audit row is NOT emitted (only the 2 normal setup rows
        — `oauth.code_exchange` for Client + `accounts.linked` — are
        present).
    """
    tokens_path = home / "swing-data" / "schwab-tokens.production.db"
    assert not tokens_path.exists(), "fixture pre-state assumed empty"

    _patch_schwabdev_ok(monkeypatch)

    setup_paste_flow(
        cfg=cfg,
        environment="production",
        client_id="my_client_id",
        client_secret="my_client_secret",
        conn=conn,
    )

    # No rename happened.
    renamed = list(home.glob("swing-data/schwab-tokens.production.db.deleted-*"))
    assert renamed == [], f"unexpected rename happened: {renamed}"
    # No self-heal audit row — only the two normal setup rows.
    rows = _read_audit_rows(home)
    rename_rows = [
        r for r in rows
        if r["error_message"]
        and "auto-detected" in r["error_message"]
    ]
    assert rename_rows == [], (
        f"unexpected self-heal audit row(s): {rename_rows}"
    )
    # Should be exactly 2 rows (setup code_exchange + accounts.linked).
    assert len(rows) == 2, (
        f"expected 2 audit rows on no-rename path; got {len(rows)}: {rows}"
    )


def test_t_a_2_collision_at_expected_renamed_path_uses_disambiguation_suffix(
    home: Path, cfg: Any, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 3 — collision at `<canonical>.deleted-<ts>` → suffix `-1`.

    Monkeypatch `_utc_now` to a fixed timestamp so we can pre-create the
    expected collision file. Then plant the stale tokens DB. Then invoke
    setup. Assert the renamed file gets a `-1` suffix; the planted
    collision file is unchanged.
    """
    import datetime as _dt
    fixed_ts = _dt.datetime(2026, 5, 14, 22, 15, 30, tzinfo=_dt.timezone.utc)
    monkeypatch.setattr(auth_mod, "_utc_now", lambda: fixed_ts)

    tokens_path = home / "swing-data" / "schwab-tokens.production.db"
    expected_renamed = home / "swing-data" / (
        "schwab-tokens.production.db.deleted-20260514T221530"
    )
    # Plant the stale tokens DB AND the collision file.
    tokens_path.write_text("STALE_PAYLOAD")
    expected_renamed.write_text("PREVIOUS_DELETION_PAYLOAD")

    _patch_schwabdev_ok(monkeypatch)

    setup_paste_flow(
        cfg=cfg,
        environment="production",
        client_id="my_client_id",
        client_secret="my_client_secret",
        conn=conn,
    )

    # Pre-existing collision file untouched.
    assert expected_renamed.read_text() == "PREVIOUS_DELETION_PAYLOAD"
    # New renamed file at `-1` suffix.
    disambiguated = home / "swing-data" / (
        "schwab-tokens.production.db.deleted-20260514T221530-1"
    )
    assert disambiguated.exists(), (
        f"expected disambiguated rename at {disambiguated}; "
        f"glob: {list(home.glob('swing-data/*.deleted-*'))}"
    )
    assert disambiguated.read_text() == "STALE_PAYLOAD"


def test_t_a_2_rename_completes_before_schwabdev_failure(
    home: Path, cfg: Any, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 4 — simulates the original failure mode that motivated T-A.2.

    Plant stale tokens DB; mock schwabdev to raise on __init__. Assert
    rename happened BEFORE schwabdev was invoked (the stale tokens DB
    was no longer at the canonical path when schwabdev got constructed)
    AND schwabdev's failure surfaces as the real error (not blocked by
    stale tokens).
    """
    from swing.integrations.schwab.client import SchwabAuthError

    tokens_path = home / "swing-data" / "schwab-tokens.production.db"
    tokens_path.write_text("STALE_TOKENS_THAT_WOULD_HAVE_BLOCKED_PASTE_BACK")

    state = _patch_schwabdev_raises(
        monkeypatch, RuntimeError("unsupported_token_type"),
    )

    with pytest.raises(SchwabAuthError):
        setup_paste_flow(
            cfg=cfg,
            environment="production",
            client_id="my_client_id",
            client_secret="my_client_secret",
            conn=conn,
        )

    # CRITICAL: rename was performed BEFORE schwabdev got called.
    assert state["tokens_file_existed_pre_init"] is False, (
        "schwabdev was invoked WHILE stale tokens DB was still present; "
        "self-heal rename must happen BEFORE Client.__init__"
    )
    # The renamed file should still be on disk.
    renamed = list(home.glob("swing-data/schwab-tokens.production.db.deleted-*"))
    assert len(renamed) == 1, (
        f"expected exactly 1 renamed file post-call; got {renamed}"
    )
    assert renamed[0].read_text() == (
        "STALE_TOKENS_THAT_WOULD_HAVE_BLOCKED_PASTE_BACK"
    )


def test_t_a_2_operator_visible_message_emitted(
    home: Path, cfg: Any, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Test 5 — operator-visible advisory text emitted on stdout.

    Plant stale tokens DB + invoke setup. Capture stdout; assert all three
    operator-visible substrings appear:
      - "Auto-detected existing tokens DB"
      - "renamed to"
      - "24h recovery window"
    """
    tokens_path = home / "swing-data" / "schwab-tokens.production.db"
    tokens_path.write_text("stale-payload")

    _patch_schwabdev_ok(monkeypatch)

    setup_paste_flow(
        cfg=cfg,
        environment="production",
        client_id="my_client_id",
        client_secret="my_client_secret",
        conn=conn,
    )

    out = capsys.readouterr().out
    assert "Auto-detected existing tokens DB" in out, (
        f"missing 'Auto-detected existing tokens DB' substring; out={out!r}"
    )
    assert "renamed to" in out, (
        f"missing 'renamed to' substring; out={out!r}"
    )
    assert "24h recovery window" in out, (
        f"missing '24h recovery window' substring; out={out!r}"
    )


def test_t_a_2_os_replace_is_the_rename_primitive(
    home: Path, cfg: Any, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 6 — `os.replace` is the only rename primitive used.

    Per CLAUDE.md gotcha "os.replace requires same filesystem": rename of
    tokens DB stays inside ~/swing-data/ so cross-device-link risk is
    nil, but the discipline is to use os.replace (atomic + overwrite-safe
    on POSIX + Windows), NOT os.rename or shutil.move.

    Approach: wrap `os.replace` with a counter; wrap `os.rename` and
    `shutil.move` with raising side-effects. Plant stale tokens DB +
    invoke setup. Assert os.replace was called exactly once; os.rename
    + shutil.move were NEVER called.
    """
    import os
    import shutil

    tokens_path = home / "swing-data" / "schwab-tokens.production.db"
    tokens_path.write_text("stale-payload")

    _patch_schwabdev_ok(monkeypatch)

    replace_calls: list[tuple[str, str]] = []
    real_replace = os.replace

    def counting_replace(src, dst, *args, **kwargs):
        replace_calls.append((str(src), str(dst)))
        return real_replace(src, dst, *args, **kwargs)

    def banned_rename(*args, **kwargs):
        raise AssertionError(
            f"os.rename called with args={args}, kwargs={kwargs}; "
            "tokens DB rename MUST use os.replace per CLAUDE.md gotcha"
        )

    def banned_move(*args, **kwargs):
        raise AssertionError(
            f"shutil.move called with args={args}, kwargs={kwargs}; "
            "tokens DB rename MUST use os.replace per CLAUDE.md gotcha"
        )

    monkeypatch.setattr(os, "replace", counting_replace)
    monkeypatch.setattr(os, "rename", banned_rename)
    monkeypatch.setattr(shutil, "move", banned_move)

    setup_paste_flow(
        cfg=cfg,
        environment="production",
        client_id="my_client_id",
        client_secret="my_client_secret",
        conn=conn,
    )

    # Exactly one rename op happened (for the stale tokens DB).
    rename_ops = [
        c for c in replace_calls
        if "schwab-tokens.production.db" in c[0]
        and ".deleted-" in c[1]
    ]
    assert len(rename_ops) == 1, (
        f"expected exactly 1 stale-tokens-DB rename via os.replace; "
        f"got {len(rename_ops)}: {rename_ops}"
    )


def test_t_a_2_audit_row_emitted_with_locked_disposition(
    home: Path, cfg: Any, conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 7 — disposition LOCK (per AC3).

    After self-heal rename, query schwab_api_calls. Assert exactly ONE row
    exists with the locked disposition:
      - endpoint='oauth.code_exchange' (schema CHECK enum at v18 does NOT
        include `oauth.tokens_db_rename` — brief deviation banked in commit
        message + return report),
      - status='success',
      - surface='cli',
      - environment='production',
      - error_message substring contains both 'auto-detected' AND
        'renamed before paste-back'.

    This row is SEPARATE from + precedes the setup flow's own
    `oauth.code_exchange` audit row.
    """
    tokens_path = home / "swing-data" / "schwab-tokens.production.db"
    tokens_path.write_text("stale-payload")

    _patch_schwabdev_ok(monkeypatch)

    setup_paste_flow(
        cfg=cfg,
        environment="production",
        client_id="my_client_id",
        client_secret="my_client_secret",
        conn=conn,
    )

    rows = _read_audit_rows(home)
    # Locate the self-heal row via its distinctive error_message substring.
    self_heal_rows = [
        r for r in rows
        if r["error_message"]
        and "auto-detected" in r["error_message"]
        and "renamed before paste-back" in r["error_message"]
    ]
    assert len(self_heal_rows) == 1, (
        f"expected exactly 1 self-heal audit row; got {len(self_heal_rows)}: "
        f"rows={rows}"
    )
    row = self_heal_rows[0]
    assert row["endpoint"] == "oauth.code_exchange", (
        f"expected endpoint='oauth.code_exchange'; got {row['endpoint']!r}"
    )
    assert row["status"] == "success", (
        f"expected status='success'; got {row['status']!r}"
    )
    assert row["surface"] == "cli", (
        f"expected surface='cli'; got {row['surface']!r}"
    )
    assert row["environment"] == "production", (
        f"expected environment='production'; got {row['environment']!r}"
    )
    # Self-heal row precedes the setup-flow oauth.code_exchange row.
    self_heal_call_id = row["call_id"]
    other_code_exchange = [
        r for r in rows
        if r["endpoint"] == "oauth.code_exchange"
        and r["call_id"] != self_heal_call_id
    ]
    assert len(other_code_exchange) == 1, (
        f"expected exactly 1 OTHER oauth.code_exchange row (the setup-flow "
        f"row); got {len(other_code_exchange)}: rows={rows}"
    )
    # call_id ordering: self-heal MUST come first.
    assert self_heal_call_id < other_code_exchange[0]["call_id"], (
        f"self-heal row call_id={self_heal_call_id} must precede setup "
        f"row call_id={other_code_exchange[0]['call_id']}"
    )
