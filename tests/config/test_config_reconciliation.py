"""SPCX out-of-framework carve-out — Task 1 config plumbing tests.

`[reconciliation] out_of_framework_tickers` is the declared-holdings registry.
Tracked-toml default = empty tuple; the operator's actual declaration lives in
`user-config.toml` (operator-specific, like `account_hash`). Per CHARC Ruling 1
the tracked `swing.config.toml` MUST stay empty of any declaration.

Distinguishing posture (feedback_regression_test_arithmetic): each test states
the pre-fix value (the field/override block does not exist) and the post-fix
value so it provably distinguishes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import Config, load
from swing.config_overrides import apply_overrides
from swing.config_user import write_user_overrides


def _strip_section(cfg_text: str, header_prefix: str) -> str:
    """Drop any section whose header starts with ``header_prefix``."""
    out: list[str] = []
    skipping = False
    for line in cfg_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("[") and stripped.rstrip().endswith("]"):
            skipping = stripped.startswith(header_prefix)
            if skipping:
                continue
        if skipping:
            continue
        out.append(line)
    return "\n".join(out)


def _base_cfg_text() -> str:
    return _strip_section(
        Path("swing.config.toml").read_text(), "[reconciliation"
    )


def test_config_reconciliation_section_defaults_empty(tmp_path: Path) -> None:
    """No [reconciliation] section -> out_of_framework_tickers == ()."""
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_base_cfg_text())
    cfg = load(cfg_path)
    # Pre-fix: AttributeError ('Config' has no attribute 'reconciliation').
    # Post-fix: ().
    assert cfg.reconciliation.out_of_framework_tickers == ()


def test_config_reconciliation_normalizes_tickers(tmp_path: Path) -> None:
    """Tracked toml [reconciliation] list is uppercased, deduped, sorted."""
    cfg_text = _base_cfg_text()
    cfg_text += (
        '\n\n[reconciliation]\n'
        'out_of_framework_tickers = ["spcx", "AAPL", "spcx"]\n'
    )
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(cfg_text)
    cfg = load(cfg_path)
    # Pre-fix: AttributeError. Post-fix: normalized tuple.
    assert cfg.reconciliation.out_of_framework_tickers == ("AAPL", "SPCX")


def test_apply_overrides_reads_out_of_framework_from_user_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply_overrides layers user-config [reconciliation] over the base."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir()
    write_user_overrides({"reconciliation": {"out_of_framework_tickers": ["spcx"]}})

    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_base_cfg_text())
    base_cfg = load(cfg_path)
    cfg = apply_overrides(base_cfg)
    # Pre-fix: () (override block absent). Post-fix: ("SPCX",).
    assert cfg.reconciliation.out_of_framework_tickers == ("SPCX",)


def test_apply_overrides_malformed_out_of_framework_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bare-string (not a list) user-config value degrades, never crashes.

    Distinguishing form (a): the override block must LOG a malformed-value
    diagnostic (proving it ran + degraded). A "no-raise + falls-through-to-()"
    assertion ALONE is non-distinguishing (it passes whether the block exists
    or is absent). Pre-fix (block absent): no diagnostic -> the caplog
    assertion FAILS. Post-fix: diagnostic present -> passes.
    """
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir()
    write_user_overrides(
        {"reconciliation": {"out_of_framework_tickers": "SPCX"}}
    )

    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_base_cfg_text())
    base_cfg = load(cfg_path)
    with caplog.at_level("WARNING"):
        cfg = apply_overrides(base_cfg)
    assert isinstance(cfg, Config)
    # Bare-string is rejected as too-clever: falls through to the base ().
    assert cfg.reconciliation.out_of_framework_tickers == ()
    # The degrade path actually ran (distinguishing assertion).
    assert any(
        "out_of_framework_tickers" in r.message
        for r in caplog.records
    )


def test_apply_overrides_toml_table_does_not_silently_activate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Codex R1 MAJOR: a TOML TABLE user-config value (dict) must NOT iterate
    its keys into a silent carve-out (that would suppress an orphan for a
    ticker the operator never validly declared, violating C2/L3). It degrades
    to base () + logs a diagnostic.

    Distinguishing: pre-fix the iterable-accepting normalizer turned
    {"SPCX": true} into ("SPCX",) (a silent carve-out). Post-fix it raises
    TypeError -> apply_overrides logs + falls through to ().
    """
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "swing-data").mkdir()
    # A TOML table writes as a nested dict in user-config.toml.
    write_user_overrides(
        {"reconciliation": {"out_of_framework_tickers": {"SPCX": True}}}
    )
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(_base_cfg_text())
    base_cfg = load(cfg_path)
    with caplog.at_level("WARNING"):
        cfg = apply_overrides(base_cfg)
    assert cfg.reconciliation.out_of_framework_tickers == ()
    assert any(
        "out_of_framework_tickers" in r.message for r in caplog.records
    )


def test_config_reconciliation_tracked_bare_string_rejected(
    tmp_path: Path,
) -> None:
    """Codex R1 MAJOR: a bare-string tracked value is REJECTED (TypeError),
    NOT char-split into a phantom list by a tuple() pre-wrap.

    Distinguishing: pre-fix tuple("SPCX") == ('S','P','C','X') passed the
    element-is-str check -> a 4-char phantom carve-out. Post-fix the strict
    normalizer raises on the bare string.
    """
    cfg_text = _base_cfg_text()
    cfg_text += '\n\n[reconciliation]\nout_of_framework_tickers = "SPCX"\n'
    cfg_path = tmp_path / "swing.config.toml"
    cfg_path.write_text(cfg_text)
    with pytest.raises(TypeError):
        load(cfg_path)
