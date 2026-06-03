"""OQ-1 Fernet cfg source: key resolution + masking (the cipher helpers are Slice 2)."""
from swing.integrations.schwab import auth


class _SchwabCfg:
    def __init__(self, encryption_key):
        self.encryption_key = encryption_key


class _Cfg:
    def __init__(self, *, encryption_key=None):
        self.integrations = type("I", (), {"schwab": _SchwabCfg(encryption_key)})()


def _cfg(*, encryption_key=None):
    return _Cfg(encryption_key=encryption_key)


def test_resolve_fernet_key_none_when_absent() -> None:
    assert auth._resolve_fernet_key(_cfg(encryption_key=None)) is None
    assert auth._resolve_fernet_key(_cfg(encryption_key="")) is None


def test_resolve_fernet_key_value_when_present() -> None:
    k = auth._generate_fernet_key()
    assert auth._resolve_fernet_key(_cfg(encryption_key=k)) == k


def test_config_show_masks_encryption_key(monkeypatch, tmp_path) -> None:
    # swing config show MUST mask encryption_key like client_secret.
    from click.testing import CliRunner

    from swing.cli import main

    key = auth._generate_fernet_key()
    # Monkeypatch BOTH USERPROFILE and HOME so write_user_overrides cannot leak to the
    # operator's real ~/swing-data (CLAUDE.md test-discipline gotcha).
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    swing_data = tmp_path / "swing-data"
    swing_data.mkdir(parents=True, exist_ok=True)
    (swing_data / "user-config.toml").write_text(
        f'[integrations.schwab]\nencryption_key = "{key}"\n', encoding="utf-8")
    result = CliRunner().invoke(main, ["config", "show"])
    assert result.exit_code == 0, result.output
    # Pre-fix: encryption_key unknown to config-show -> printed raw OR absent. Post-fix:
    # the key is present-but-masked; the RAW key bytes never appear.
    assert key not in result.output
    assert "encryption_key" in result.output  # the field IS surfaced (masked), not hidden
    assert "***" in result.output  # the mask token used for client_secret
