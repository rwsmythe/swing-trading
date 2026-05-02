# Phase 5 — Configuration Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `/config` web page (plus parallel `swing config` CLI group) that lets the operator view and edit three settings (`web.chase_factor`, `pipeline.chart_top_n_watch`, `account.risk_equity_floor`) without hand-editing TOML, persisting overrides to a separate user-config file at `%USERPROFILE%/swing-data/user-config.toml`.

**Architecture:** A new `swing/config_user.py` module owns the user-config file (atomic load/write/delete). A new `swing/config_overrides.py` module composes the effective `Config` dataclass at request entry by re-reading user-config on each call (`apply_overrides(base_cfg) -> Config`). All 27 route-handler `cfg = request.app.state.cfg` sites and the pipeline runner's `run_pipeline` entry are updated to call `apply_overrides`. A shared `swing/config_validation.py` hosts a single field-registry table consumed by both web routes and CLI subcommands. The web `/config` page mirrors the existing `journal` route+VM+template structure; the soft-warn confirm fragment mirrors `partials/soft_warn_confirm.html.j2` adapted for the `<form>`-rooted (not `<tr>`-rooted) config page.

**Tech Stack:** FastAPI + Starlette `TemplateResponse`; HTMX for soft-warn round-trip; Click for CLI; `tomllib` (stdlib, read) + `tomli_w` (NEW dep, write); pytest + Starlette `TestClient`.

---

## §A — Resolved-during-planning items (locked decisions reconciled with code)

These are findings from the §0 file survey that diverge from the brief's pre-survey wording. The plan implements the reconciled positions below; they DO NOT contradict the brief's locked decisions in §2 — they refine field paths and remove an obsolete sub-task.

1. **`risk_floor` is ALREADY a config field.** `cfg.account.risk_equity_floor` exists (`swing/config.py:32`), is in tracked toml at `swing.config.toml:22` (`risk_equity_floor = 7500.0`), and is consumed at three production sites: `swing/pipeline/runner.py:424`, `swing/pipeline/runner.py:558`, `swing/web/view_models/dashboard.py:496`. Brief Task 0a (promotion from constant) is a NO-OP. The discriminating-override test the brief required is preserved in Task 2 (Task 2.4 below). Page UI label is "Risk floor"; underlying field path is unchanged: `cfg.account.risk_equity_floor`. User-config TOML schema mirrors tracked schema (`[account] risk_equity_floor = ...`).
2. **`chart_top_n_watch` lives at `cfg.pipeline.chart_top_n_watch`, NOT `cfg.web.chart_top_n_watch`.** Confirmed via grep of all consumer sites (`swing/pipeline/runner.py:635`, `swing/web/chart_scope.py`, `swing/web/routes/charts.py:69`, `swing/web/view_models/dashboard.py:492`, `swing/web/view_models/open_positions_row.py:198`, `swing/web/view_models/watchlist.py:282`). User-config TOML schema mirrors `[pipeline] chart_top_n_watch = ...`.
3. **`chase_factor` lives at `cfg.web.chase_factor`** (`swing/config.py:185`), consumed at `swing/web/view_models/dashboard.py:520, 522`. User-config TOML schema mirrors `[web] chase_factor = ...`.
4. **Config IS import-time cached.** `swing/cli.py:30` calls `load_config(Path(config_path))` once, storing the immutable `Config` dataclass in `ctx.obj["config"]` and (for `swing web`) in `app.state.cfg` at `swing/web/app.py:156`. Task 1b is REQUIRED: every route-handler `cfg = request.app.state.cfg` reader (27 sites enumerated below) and the pipeline runner's `run_pipeline` entry must call `apply_overrides(base_cfg) -> Config` so user-config takes effect on the next request without restart.
5. **`tomli_w` is NOT installed.** Plan adds `tomli_w >= 1.0` to `pyproject.toml` `[project] dependencies`. Rationale: stdlib `tomllib` is read-only; hand-serialization for 3 fields is tractable but accumulates float-repr edge cases (`0.020` vs `0.02`) and section-table presence rules. `tomli_w` is small, pure Python, MIT-licensed, ships from the same authors as `tomli`/`tomllib`. Task 1.0 below ships the dep bump.
6. **Existing `tests/web/test_config_web.py::test_config_web_chase_factor_no_toml_shadow` is now obsolete.** It explicitly states "until [Phase 5], operators write the value into their local untracked toml" — Phase 5 IS this dispatch. The audit's invariant ("chase_factor must NOT appear in any GIT-TRACKED toml file") is no longer the policy: tracked toml is now an explicit precedence layer per locked decision §2.2, AND user-config overrides on top of it. Task 2.0 below replaces this test with a positive override-precedence test asserting user-config beats tracked toml beats default.
7. **Task 7: Static nav link only.** Surveyed `swing/web/templates/base.html.j2` — the nav block is hardcoded `<a>` tags with no VM dereference. Adding `<a href="/config">Config</a>` requires NO new field on any of the 5 base-layout VMs. The CLAUDE.md "5-VM rule" does not apply.

8. **Web-vs-CLI parity (intentional V1 divergence).** (Codex R2 Major 1.) The web `POST /config` uses MERGE semantics: an unchanged-value submit is a no-op (preserves source-fidelity per Critical 1). The CLI `swing config set` writes UNCONDITIONALLY on every invocation (CLI users expect their explicit command to "do something"; idempotent-no-write would surprise scripted callers). **Consequence:** the corner case "operator wants to LOCK a V1 field at the registry default value WHILE that field's current source is `default`" is reachable via CLI (`swing config set web.chase_factor 0.01`) but NOT via the web form (typing `0.01` into a default-source row is a no-op). Operators who need to lock-at-default-from-default use the CLI for that one case; web users who want to lock typically arrive from a `tracked` source (where typing the registry default DOES diverge from current effective value, so it WILL write per merge invariant (b)). **Surface divergence is documented + accepted for V1.** A future V2 dispatch may add an explicit "Lock as override" checkbox per row to close this gap; it is NOT required for V1's three fields where the corner case has no operational urgency. The plan's "CLI + web validation parity" claim (Codex watch-item #7) covers VALIDATION (single FIELD_REGISTRY) only, NOT save-write semantics.

---

## §B — File map (creations / modifications)

### Files to CREATE

| Path | Responsibility |
|---|---|
| `swing/config_user.py` | User-config file I/O. Public API: `get_user_config_path() -> Path`, `load_user_overrides() -> dict`, `write_user_overrides(overrides: dict) -> None`, `delete_user_override(field_path: str) -> None`. Atomic write via `tempfile.NamedTemporaryFile(dir=<config-dir>) + os.replace`. Missing file → `{}`. Malformed file → `{}` + log warning. |
| `swing/config_overrides.py` | Effective-Config builder. Public API: `apply_overrides(base_cfg: Config) -> Config` (returns NEW Config dataclass via `dataclasses.replace`); `get_field_source(base_cfg: Config, field_path: str) -> Literal["default", "tracked", "override"]`. Re-reads user-config on every call. |
| `swing/config_validation.py` | Field registry + validation. Public API: `FIELD_REGISTRY: tuple[FieldSpec, ...]` (one row per V1 field: path, default, type, hard-refuse rule, soft-warn rule, description, label); `ValidationResult` dataclass (`hard_errors: list`, `soft_warnings: list`); `validate_field(field_path: str, raw_value: str) -> ValidationResult`; `validate_all(form_dict: dict) -> ValidationResult`; `coerce_value(field_path: str, raw_value: str) -> Any` (str → typed). |
| `swing/web/view_models/config.py` | `ConfigPageVM` + `build_config_vm(cfg: Config) -> ConfigPageVM` + per-field row dataclass (`ConfigFieldRow` with name, label, description, current_value, default_value, source, input_kind). |
| `swing/web/routes/config.py` | Three handlers: `GET /config`, `POST /config`, `POST /config/reset/{field_path}`. |
| `swing/web/templates/config.html.j2` | Page template extending `base.html.j2`. Per-field row + save form + per-field reset form. |
| `swing/web/templates/partials/config_soft_warn_confirm.html.j2` | Soft-warn confirm fragment. `<form>`-rooted (NOT `<tr>`-rooted). Uses `{% for key, value in form_values.items() %}` round-trip pattern + hidden `force=true`. |
| `swing/web/templates/partials/config_hard_refuse.html.j2` | Hard-refuse error fragment. `<div>`-rooted. Renders the field-level errors. |
| `swing/web/templates/partials/config_save_success.html.j2` | Optional banner partial used by `GET /config?saved=1` flow (303 redirect-back). |
| `swing/cli_config.py` | New module hosting the Click `config` group. Imported and registered into `swing/cli.py:main` group. Three subcommands: `show`, `set`, `reset`. |
| `tests/config_user/test_config_user.py` | Round-trip + atomic-write + missing-file + malformed-file tests for `swing.config_user`. |
| `tests/config_overrides/test_apply_overrides.py` | Override-precedence tests for the 3 V1 fields × 3 scenarios + source-introspection. |
| `tests/config_validation/test_validation.py` | Hard-refuse boundary + soft-warn boundary tests per V1 field. |
| `tests/web/test_config_route.py` | Route-level integration tests (GET/POST/reset). Uses `with TestClient(app) as client:`. |
| `tests/web/test_config_template.py` | Template-render tests. |
| `tests/cli/test_cli_config.py` | Click runner integration tests for `swing config show / set / reset`. |
| `tests/integration/test_config_end_to_end.py` | Two integration tests: (a) override applied via web route persists and is read by next dashboard render with the new value; (b) override applied via CLI persists and is read by `cfg.web.chase_factor` consumer site. |

### Files to MODIFY

| Path | Reason |
|---|---|
| `pyproject.toml` | Add `tomli_w >= 1.0` to `[project] dependencies`. |
| `swing/web/templates/base.html.j2` | Add `<a href="/config">Config</a>` to nav block (after `Pipeline` link). Static link only — no VM field added. |
| `swing/web/app.py` | Import `swing.web.routes.config` + `app.include_router(config_route.router)`. |
| `swing/cli.py` | Import + register `from swing.cli_config import config_group; main.add_command(config_group)`. |
| `swing/pipeline/__init__.py` | The PUBLIC `run_pipeline(cfg=..., trigger=...)` wrapper at line 13 is the single entry point (called from CLI + routes). Add `cfg = apply_overrides(cfg)` immediately before the call to `run_pipeline_internal(...)`. The private worker `run_pipeline_internal` in `swing/pipeline/runner.py:100` is NOT the patched function — patching the public wrapper covers every caller. (Codex R1 Minor 1.) |
| `swing/web/routes/dashboard.py` | Replace `cfg = request.app.state.cfg` with `cfg = apply_overrides(request.app.state.cfg)` (1 site at line 14). |
| `swing/web/routes/charts.py` | Same replacement (1 site at line 49). |
| `swing/web/routes/journal.py` | Same replacement (1 site at line 19). |
| `swing/web/routes/pipeline.py` | Same replacement (8 sites: 39, 49, 184, 204, 224, 250, 296, 381). |
| `swing/web/routes/recommendations.py` | Same replacement (2 sites: 54, 93). |
| `swing/web/routes/trades.py` | Same replacement (10 sites: 163, 215, 271, 696, 718, 802, 815, 845, 936, 963). |
| `swing/web/routes/watchlist.py` | Same replacement (3 sites: 18, 36, 58). |
| `tests/web/test_config_web.py` | DELETE the obsolete `test_config_web_chase_factor_no_toml_shadow` test (per §A.6). Other tests in this file remain unchanged. |

---

## §C — Override-precedence audit table (V1 fields × consumer sites)

This is the read-site-by-read-site audit demanded by Codex watch-item #1 ("Toml-shadowing audit completeness"). Every consumer site below routes through `apply_overrides` after Task 1b lands.

| Field path | Consumer file:line | Reads via base `cfg` (PRE-fix) | After Task 1b: reads via `apply_overrides(base)` |
|---|---|---|---|
| `web.chase_factor` | `swing/web/view_models/dashboard.py:520` | `cfg.web.chase_factor` | YES (cfg has been replaced at route entry) |
| `web.chase_factor` | `swing/web/view_models/dashboard.py:522` | `cfg.web.chase_factor` | YES |
| `pipeline.chart_top_n_watch` | `swing/pipeline/runner.py:635` | `cfg.pipeline.chart_top_n_watch` | YES (cfg replaced at run_pipeline entry) |
| `pipeline.chart_top_n_watch` | `swing/web/routes/charts.py:69` | `cfg.pipeline.chart_top_n_watch` | YES |
| `pipeline.chart_top_n_watch` | `swing/web/view_models/dashboard.py:492` | `cfg.pipeline.chart_top_n_watch` | YES (caller passes overridden cfg) |
| `pipeline.chart_top_n_watch` | `swing/web/view_models/open_positions_row.py:198` | `cfg.pipeline.chart_top_n_watch` | YES |
| `pipeline.chart_top_n_watch` | `swing/web/view_models/watchlist.py:282` | `cfg.pipeline.chart_top_n_watch` | YES |
| `account.risk_equity_floor` | `swing/pipeline/runner.py:424` | `cfg.account.risk_equity_floor` | YES |
| `account.risk_equity_floor` | `swing/pipeline/runner.py:558` | `cfg.account.risk_equity_floor` | YES |
| `account.risk_equity_floor` | `swing/web/view_models/dashboard.py:496` | `cfg.account.risk_equity_floor` | YES |

**Residual risk (documented per §9 fallback (b)):** Long-lived caches built at app startup (`PriceCache`, `OhlcvCache`) hold the original non-overridden `cfg` for their lifetime. These caches DO NOT consume any V1 field; their config dependencies are `web.price_cache_ttl_seconds`, `web.max_concurrent_price_fetches`, `web.ohlcv_cache_ttl_seconds`, `web.max_concurrent_ohlcv_fetches`, none of which are V1-overridable. If a future field is added to V2 that DOES feed these caches, the override mechanism must extend to cache rebuilds — out of scope for this dispatch.

---

## §D — User-config TOML schema

Empty / missing file = no overrides (every read falls through to tracked toml then default).

Example after operator sets all three fields:

```toml
# %USERPROFILE%/swing-data/user-config.toml
# Operator-tunable overrides. Generated by `swing config set` and the /config page.
# Hand-edits OK; the file is re-parsed on each read.

[account]
risk_equity_floor = 10000.0

[pipeline]
chart_top_n_watch = 15

[web]
chase_factor = 0.02
```

Schema rules:
- Mirror tracked-toml namespace: `[account]`, `[pipeline]`, `[web]` exactly.
- Section tables emitted ONLY when at least one V1 field in that section has an override (no empty `[web]`).
- Float fields written as `0.02` (not `0.020`) — `tomli_w` handles this canonically.
- Int fields written as `15` (not `15.0`).
- No schema_version, no last-modified-by/at, no audit (out-of-scope per locked decisions).

---

## §E — Field registry (single source of truth)

```python
# swing/config_validation.py — FIELD_REGISTRY (V1 = 3 rows)

@dataclass(frozen=True)
class FieldSpec:
    path: str               # dotted (e.g. "web.chase_factor")
    label: str              # human label for page + CLI
    description: str        # one-line operator-facing explanation
    type: type              # float or int
    default: float | int    # default value (matches Python dataclass default)
    hard_refuse_min: float | int | None
    hard_refuse_max: float | int | None
    soft_warn_min: float | int | None       # "below this triggers a warn"
    soft_warn_max: float | int | None       # "above this triggers a warn"

FIELD_REGISTRY: tuple[FieldSpec, ...] = (
    FieldSpec(
        path="web.chase_factor",
        label="Chase factor",
        description="Buy-limit pad above pivot. 0.01 = 1% above pivot.",
        type=float, default=0.01,
        hard_refuse_min=0.0, hard_refuse_max=0.10,
        soft_warn_min=None, soft_warn_max=0.02,
    ),
    FieldSpec(
        path="pipeline.chart_top_n_watch",
        label="Watchlist chart count",
        description="Number of watchlist tickers to render charts for in the nightly briefing.",
        type=int, default=10,
        hard_refuse_min=1, hard_refuse_max=50,
        soft_warn_min=None, soft_warn_max=25,
    ),
    FieldSpec(
        path="account.risk_equity_floor",
        label="Risk floor",
        description="Position-sizing floor: sizing_equity = max(real_equity, this).",
        type=float, default=7500.0,
        hard_refuse_min=0.0, hard_refuse_max=None,
        soft_warn_min=1000.0, soft_warn_max=25000.0,
    ),
)
```

Validation contract:
- `value < hard_refuse_min` (when set) OR `value > hard_refuse_max` (when set) → `hard_errors` populated. Write is refused.
- `value < soft_warn_min` (when set) OR `value > soft_warn_max` (when set) → `soft_warnings` populated. Caller decides (page returns confirm fragment; CLI prompts unless `--force`).
- Type coercion (`coerce_value`): str → float/int via the registry's `type`. ValueError on failure → hard error.
- Source-of-truth: `FIELD_REGISTRY.default` is authoritative for "default value" displayed on the page. Tracked `swing.config.toml` is the seed/example; if a tracked toml row exists and matches the registry default, source reports `tracked`. If it differs, source still reports `tracked` (the operator chose to put a non-default value in tracked toml; that beats the registry default per the precedence chain §2.2).

---

## §F — Tasks

### Task 0: Branch hygiene + dispatch baseline

**Files:** none (verification only)

- [ ] **Step 1: Verify clean main and capture baseline**

```bash
git status
git log --oneline -5
python -m pytest -m "not slow" -q 2>&1 | tail -3
ruff check swing/ 2>&1 | tail -3
```

Expected: clean working tree at HEAD `98b9a37` or later; baseline test count recorded for Done-criteria comparison; ruff baseline ≤91 warnings recorded.

- [ ] **Step 2: Subject-only ERE grep observable check (per binding convention)**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task [0-9]+\.[0-9]+' --since="2026-05-01"
```

Expected: empty output (no prior Phase 5 task commits). If non-empty, STOP and surface in return report — duplicate Task IDs would corrupt the audit trail.

---

### Task 1.0: Add `tomli_w` dependency

**Files:**
- Modify: `pyproject.toml` — add to `[project] dependencies` array

- [ ] **Step 1: Edit pyproject.toml**

```toml
# In [project] dependencies, add after the last entry:
    "tomli_w>=1.0",
```

- [ ] **Step 2: Reinstall dev environment**

```bash
pip install -e ".[dev,web]"
python -c "import tomli_w; print(tomli_w.__version__)"
```

Expected: prints a version string ≥ 1.0.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat(config): Task 1.0 — add tomli_w dependency for user-config writes"
```

---

### Task 1.1: User-config persistence layer (write failing tests first)

**Files:**
- Create: `swing/config_user.py`
- Create: `tests/config_user/__init__.py`
- Create: `tests/config_user/test_config_user.py`

- [ ] **Step 1: Create test directory + write failing tests (TDD)**

```bash
mkdir -p tests/config_user
touch tests/config_user/__init__.py
```

Write `tests/config_user/test_config_user.py`:

```python
"""User-config file I/O — round-trip + atomic + missing/malformed."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from swing.config_user import (
    delete_user_override,
    get_user_config_path,
    load_user_overrides,
    write_user_overrides,
)


@pytest.fixture
def isolated_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate USERPROFILE so tests don't touch the operator's real file."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_dir = tmp_path / "swing-data"
    cfg_dir.mkdir()
    return cfg_dir / "user-config.toml"


def test_get_user_config_path_returns_userprofile_path(isolated_user_config: Path):
    assert get_user_config_path() == isolated_user_config


def test_load_returns_empty_dict_when_file_missing(isolated_user_config: Path):
    assert not isolated_user_config.exists()
    assert load_user_overrides() == {}


def test_load_returns_empty_dict_when_file_malformed(
    isolated_user_config: Path, caplog: pytest.LogCaptureFixture,
):
    isolated_user_config.write_text("this is not = valid toml [[[", encoding="utf-8")
    with caplog.at_level("WARNING"):
        result = load_user_overrides()
    assert result == {}
    assert any("malformed" in r.message.lower() or "parse" in r.message.lower()
               for r in caplog.records)
    # File must NOT be deleted (preserve operator's content for inspection).
    assert isolated_user_config.exists()


def test_round_trip_flat_field(isolated_user_config: Path):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    assert load_user_overrides() == {"web": {"chase_factor": 0.02}}


def test_round_trip_multiple_sections(isolated_user_config: Path):
    payload = {
        "account": {"risk_equity_floor": 10000.0},
        "pipeline": {"chart_top_n_watch": 15},
        "web": {"chase_factor": 0.02},
    }
    write_user_overrides(payload)
    assert load_user_overrides() == payload


def test_toml_text_repr_float_and_int(isolated_user_config: Path):
    """Text-level check: tomli_w must emit canonical float/int repr.

    Codex R1 Major 4: round-trip tests don't catch textual drift like
    '15.0' for int or '0.020' for float. Assert the raw file bytes directly.
    """
    write_user_overrides({
        "account": {"risk_equity_floor": 10000.0},
        "pipeline": {"chart_top_n_watch": 15},
        "web": {"chase_factor": 0.02},
    })
    raw = isolated_user_config.read_text(encoding="utf-8")
    assert "risk_equity_floor = 10000.0" in raw   # float stays float
    assert "chart_top_n_watch = 15" in raw         # int NOT 15.0
    assert "chase_factor = 0.02" in raw            # NOT 0.020

def test_toml_empty_section_omitted(isolated_user_config: Path):
    """Section tables emitted ONLY when at least one key is present."""
    write_user_overrides({"web": {"chase_factor": 0.02}})
    raw = isolated_user_config.read_text(encoding="utf-8")
    assert "[web]" in raw
    assert "[account]" not in raw
    assert "[pipeline]" not in raw


def test_write_creates_directory_if_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    # Note: swing-data dir does NOT exist yet.
    write_user_overrides({"web": {"chase_factor": 0.02}})
    assert (tmp_path / "swing-data" / "user-config.toml").exists()


def test_atomic_write_uses_same_directory_tempfile(
    isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch,
):
    """CLAUDE.md cross-device-link gotcha: tempfile MUST be in dest dir.

    Discriminating-test: monkeypatch tempfile.NamedTemporaryFile to capture
    the `dir=` argument. If the implementation passes dir=None or relies on
    $TMP, this test fails — proving the cross-device guard is in place.
    """
    import tempfile as _tempfile
    captured: dict = {}
    real = _tempfile.NamedTemporaryFile

    def spy(*args, **kwargs):
        captured["dir"] = kwargs.get("dir")
        return real(*args, **kwargs)

    monkeypatch.setattr(_tempfile, "NamedTemporaryFile", spy)
    write_user_overrides({"web": {"chase_factor": 0.02}})
    assert captured["dir"] is not None
    assert Path(captured["dir"]).resolve() == isolated_user_config.parent.resolve()


def test_write_failure_leaves_destination_unchanged(
    isolated_user_config: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Simulate failure mid-write: existing file content must survive."""
    isolated_user_config.write_text(
        "[web]\nchase_factor = 0.015\n", encoding="utf-8",
    )
    original_content = isolated_user_config.read_text(encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError):
        write_user_overrides({"web": {"chase_factor": 0.99}})
    assert isolated_user_config.read_text(encoding="utf-8") == original_content


def test_delete_field_removes_section_when_empty(isolated_user_config: Path):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    delete_user_override("web.chase_factor")
    assert load_user_overrides() == {}


def test_delete_field_preserves_other_section_keys(isolated_user_config: Path):
    write_user_overrides({
        "web": {"chase_factor": 0.02},
        "pipeline": {"chart_top_n_watch": 15},
    })
    delete_user_override("web.chase_factor")
    assert load_user_overrides() == {"pipeline": {"chart_top_n_watch": 15}}


def test_delete_field_no_op_when_absent(isolated_user_config: Path):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    delete_user_override("account.risk_equity_floor")  # not present
    assert load_user_overrides() == {"web": {"chase_factor": 0.02}}


def test_write_backs_up_malformed_existing_file(
    isolated_user_config: Path, caplog: pytest.LogCaptureFixture,
):
    """Codex R3 Major 1 — auto-backup malformed file before overwrite.

    Discriminating-test: pre-populate user-config with broken TOML, write
    a valid override, then assert:
      (a) the new payload is at user-config.toml,
      (b) the broken content is preserved at user-config.malformed-*.toml,
      (c) a WARNING was logged.

    Pre-fix behavior (no guard): the malformed file is silently replaced
    with no recovery path; this test fails.
    Post-fix behavior: backup file exists with original broken content;
    this test passes.
    """
    isolated_user_config.write_text(
        "this is = not valid [[[ toml", encoding="utf-8",
    )
    original_broken = isolated_user_config.read_text(encoding="utf-8")
    with caplog.at_level("WARNING"):
        write_user_overrides({"web": {"chase_factor": 0.02}})
    assert load_user_overrides() == {"web": {"chase_factor": 0.02}}
    backups = list(isolated_user_config.parent.glob("user-config.malformed-*.toml"))
    assert len(backups) == 1, f"expected 1 backup, got {backups}"
    assert backups[0].read_text(encoding="utf-8") == original_broken
    assert any(
        "malformed" in r.message.lower() and "backed up" in r.message.lower()
        for r in caplog.records
    )


def test_write_does_not_back_up_well_formed_existing_file(
    isolated_user_config: Path,
):
    """Codex R3 Major 1 — backup only fires for malformed files.

    Negative-discriminator: a well-formed existing file is replaced via
    the normal atomic-replace path (no .malformed-* artifact). Without
    this guard, every save would generate a backup file, polluting the
    config dir.
    """
    write_user_overrides({"web": {"chase_factor": 0.015}})  # well-formed
    write_user_overrides({"web": {"chase_factor": 0.025}})  # overwrite
    backups = list(isolated_user_config.parent.glob("user-config.malformed-*.toml"))
    assert backups == []
    assert load_user_overrides() == {"web": {"chase_factor": 0.025}}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/config_user/ -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'swing.config_user'`.

- [ ] **Step 3: Implement `swing/config_user.py`**

```python
"""User-config file I/O. Atomic write per CLAUDE.md cross-device-link gotcha."""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib
import tomli_w

log = logging.getLogger(__name__)


def _user_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def get_user_config_path() -> Path:
    return _user_home() / "swing-data" / "user-config.toml"


def load_user_overrides() -> dict[str, Any]:
    path = get_user_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        log.warning("user-config malformed/unreadable at %s: %s — treating as empty", path, exc)
        return {}


def _existing_file_is_malformed(path: Path) -> bool:
    """True iff the file exists but cannot be parsed as TOML.
    Codex R3 Major 1 — used to gate auto-backup before overwrite so an
    operator's hand-edits in a syntax-broken user-config aren't silently
    lost on the next save.
    """
    if not path.exists():
        return False
    try:
        with open(path, "rb") as f:
            tomllib.load(f)
        return False
    except (tomllib.TOMLDecodeError, OSError):
        return True


def write_user_overrides(overrides: dict[str, Any]) -> None:
    from datetime import datetime as _dt
    path = get_user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Codex R3 Major 1 — auto-backup a malformed existing file BEFORE
    # overwriting it. Without this guard, the load-returns-empty contract
    # would silently destroy operator hand-edits on the next save: load()
    # returns {} for a malformed file → deepcopy({}) is empty → write
    # would replace the broken-but-recoverable file with the validated
    # write payload, irrevocably losing whatever the operator typed.
    # Backup filename includes a timestamp so multiple malformed-recovery
    # cycles don't clobber each other.
    if _existing_file_is_malformed(path):
        ts = _dt.now().strftime("%Y%m%dT%H%M%S")
        backup = path.with_name(f"user-config.malformed-{ts}.toml")
        os.replace(path, backup)  # atomic same-dir rename
        log.warning(
            "user-config malformed; backed up to %s before overwrite", backup,
        )
    # tempfile.NamedTemporaryFile(dir=path.parent, ...) — same filesystem as
    # destination, so os.replace is atomic at the filesystem-rename level on
    # Windows + POSIX. Cross-device-link gotcha (CLAUDE.md): NEVER use the
    # OS default $TMP — Drive-synced destinations live on a different volume.
    #
    # Codex R1 Major 1 — durability claim is best-effort atomic REPLACE,
    # NOT crash-durable through a power loss. We fsync the file payload
    # before replace, but Windows does not expose a portable directory
    # fsync; on POSIX we could `os.open(parent, O_RDONLY) + os.fsync(fd)`
    # after replace, but that is a no-op on Windows where the rename is
    # logged separately by the filesystem. For a single-operator local
    # tool with hand-typed config edits, a power-loss window between
    # rename-log and metadata-flush is acceptable; if it widens, a future
    # dispatch can add a journal/version pattern (out of scope for V1).
    fd = tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, delete=False, suffix=".tmp",
    )
    try:
        tomli_w.dump(overrides, fd)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        os.replace(fd.name, path)
    except Exception:
        try:
            fd.close()
        except Exception:
            pass
        # Best-effort cleanup; do NOT mask the original exception.
        try:
            Path(fd.name).unlink(missing_ok=True)
        except Exception:
            pass
        raise


def delete_user_override(field_path: str) -> None:
    """Delete one dotted field. No-op if absent. Empties trailing sections."""
    overrides = load_user_overrides()
    parts = field_path.split(".")
    if len(parts) != 2:
        raise ValueError(f"field_path must be 'section.key'; got {field_path!r}")
    section, key = parts
    if section not in overrides or key not in overrides[section]:
        return
    del overrides[section][key]
    if not overrides[section]:
        del overrides[section]
    write_user_overrides(overrides)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/config_user/ -v
```

Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/config_user.py tests/config_user/
git commit -m "feat(config): Task 1.1 — user-config persistence layer (atomic round-trip)"
```

---

### Task 1.2: Per-request read — `apply_overrides` (TDD)

**Files:**
- Create: `swing/config_overrides.py`
- Create: `tests/config_overrides/__init__.py`
- Create: `tests/config_overrides/test_apply_overrides.py`

- [ ] **Step 1: Write failing tests**

```bash
mkdir -p tests/config_overrides
touch tests/config_overrides/__init__.py
```

Write `tests/config_overrides/test_apply_overrides.py`:

```python
"""apply_overrides(base_cfg) returns Config with V1 fields overridden."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import load
from swing.config_overrides import apply_overrides, get_field_source
from swing.config_user import write_user_overrides
from tests.web.test_config_web import _write_cfg  # reuse helper


@pytest.fixture
def base_cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Built from a minimal swing.config.toml. Isolated USERPROFILE."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    return load(cfg_path)


def test_no_user_config_returns_base_unchanged(base_cfg):
    eff = apply_overrides(base_cfg)
    assert eff.web.chase_factor == base_cfg.web.chase_factor
    assert eff.pipeline.chart_top_n_watch == base_cfg.pipeline.chart_top_n_watch
    assert eff.account.risk_equity_floor == base_cfg.account.risk_equity_floor


def test_chase_factor_override_applied(base_cfg):
    write_user_overrides({"web": {"chase_factor": 0.025}})
    eff = apply_overrides(base_cfg)
    assert eff.web.chase_factor == 0.025
    # Other fields untouched
    assert eff.pipeline.chart_top_n_watch == base_cfg.pipeline.chart_top_n_watch


def test_chart_top_n_watch_override_applied(base_cfg):
    write_user_overrides({"pipeline": {"chart_top_n_watch": 20}})
    eff = apply_overrides(base_cfg)
    assert eff.pipeline.chart_top_n_watch == 20


def test_risk_equity_floor_override_applied(base_cfg):
    write_user_overrides({"account": {"risk_equity_floor": 12000.0}})
    eff = apply_overrides(base_cfg)
    assert eff.account.risk_equity_floor == 12000.0


def test_three_overrides_compose(base_cfg):
    write_user_overrides({
        "web": {"chase_factor": 0.025},
        "pipeline": {"chart_top_n_watch": 20},
        "account": {"risk_equity_floor": 12000.0},
    })
    eff = apply_overrides(base_cfg)
    assert eff.web.chase_factor == 0.025
    assert eff.pipeline.chart_top_n_watch == 20
    assert eff.account.risk_equity_floor == 12000.0


def test_unknown_section_ignored(base_cfg):
    """Forward-compat: future fields in user-config don't crash V1."""
    write_user_overrides({
        "web": {"chase_factor": 0.025, "unknown_v2_field": 99},
        "future_section": {"hypothetical": True},
    })
    eff = apply_overrides(base_cfg)
    assert eff.web.chase_factor == 0.025  # known field still applied
    # No exception, no field-on-Web added at runtime.


def test_apply_re_reads_user_config_each_call(base_cfg):
    """Per-request semantic: subsequent call sees subsequent overrides."""
    write_user_overrides({"web": {"chase_factor": 0.025}})
    eff1 = apply_overrides(base_cfg)
    assert eff1.web.chase_factor == 0.025

    write_user_overrides({"web": {"chase_factor": 0.030}})
    eff2 = apply_overrides(base_cfg)
    assert eff2.web.chase_factor == 0.030


def test_get_field_source_default(base_cfg, tmp_path, monkeypatch):
    """No tracked-toml override + no user-config → 'default'.

    Uses a CFG built from the registry default (web.chase_factor=0.01),
    NOT a tracked-toml override. Helper _write_cfg omits a [web] block,
    so cfg.web.chase_factor falls back to the dataclass default.
    """
    assert get_field_source(base_cfg, "web.chase_factor") == "default"


def test_get_field_source_tracked(tmp_path, monkeypatch):
    """Tracked-toml row present + no user-config → 'tracked'."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(
        tmp_path / "project", tmp_path / "home",
        extra='[web]\nchase_factor = 0.015\n',
    )
    cfg = load(cfg_path)
    assert get_field_source(cfg, "web.chase_factor") == "tracked"


def test_get_field_source_override(base_cfg):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    assert get_field_source(base_cfg, "web.chase_factor") == "override"


def test_get_field_source_override_even_when_value_equals_default(base_cfg):
    """Codex watch-item #4 — explicit override at default value is still 'override'.

    Operator's intent to lock the value is preserved by reporting the
    source as 'override'.
    """
    write_user_overrides({"web": {"chase_factor": 0.01}})  # == default
    assert get_field_source(base_cfg, "web.chase_factor") == "override"
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/config_overrides/ -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `swing/config_overrides.py`**

```python
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


def _get(overrides: dict[str, Any], path: str) -> Any | _Missing:
    section, key = path.split(".")
    return overrides.get(section, {}).get(key, _MISSING)


class _Missing:
    """Sentinel — distinguishes 'absent' from 'present and None'."""


_MISSING = _Missing()


def apply_overrides(base_cfg: Config) -> Config:
    """Return a Config with V1 user-config overrides applied.

    Cheap; safe to call at every route entry. Future V2 fields require
    extending the per-section replace blocks below.
    """
    overrides = load_user_overrides()
    new_web = base_cfg.web
    new_pipeline = base_cfg.pipeline
    new_account = base_cfg.account

    cf = _get(overrides, "web.chase_factor")
    if not isinstance(cf, _Missing):
        new_web = replace(new_web, chase_factor=float(cf))

    ctnw = _get(overrides, "pipeline.chart_top_n_watch")
    if not isinstance(ctnw, _Missing):
        new_pipeline = replace(new_pipeline, chart_top_n_watch=int(ctnw))

    ref = _get(overrides, "account.risk_equity_floor")
    if not isinstance(ref, _Missing):
        new_account = replace(new_account, risk_equity_floor=float(ref))

    return replace(base_cfg, web=new_web, pipeline=new_pipeline, account=new_account)


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
    # Tracked toml vs default: import the registry default and compare with
    # the value on base_cfg. If they differ, base came from tracked toml.
    from swing.config_validation import FIELD_REGISTRY
    spec = next(s for s in FIELD_REGISTRY if s.path == field_path)
    section, key = field_path.split(".")
    section_obj = getattr(base_cfg, section)
    base_value = getattr(section_obj, key)
    return "tracked" if base_value != spec.default else "default"
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/config_overrides/ -v
```

Expected: all PASS — but `get_field_source` imports `FIELD_REGISTRY` which doesn't exist yet. Plan task ordering: Task 2 ships the registry; until then, mark `test_get_field_source_*` tests as `xfail` OR ship a stub registry inline in this commit and replace in Task 2. CHOICE: ship a stub `_DEFAULTS` dict inline in `config_overrides.py` for Task 1.2 only — this is TRANSITIONAL SCAFFOLDING. Task 3.0 (config_validation.py) MUST remove the stub and replace the `get_field_source` FIELD_REGISTRY lookup with a direct import. See Task 3.0 Step 5 for the explicit removal step.

Adjust the implementation: define `_DEFAULTS = {"web.chase_factor": 0.01, "pipeline.chart_top_n_watch": 10, "account.risk_equity_floor": 7500.0}` at module top, drop the FIELD_REGISTRY import. Task 2 wires the registry to import these as the source-of-truth defaults.

```python
# Replace the get_field_source body's last 4 lines with:
    section, key = field_path.split(".")
    section_obj = getattr(base_cfg, section)
    base_value = getattr(section_obj, key)
    return "tracked" if base_value != _DEFAULTS[field_path] else "default"
```

And add at module top:

```python
_DEFAULTS: dict[str, Any] = {
    "web.chase_factor": 0.01,
    "pipeline.chart_top_n_watch": 10,
    "account.risk_equity_floor": 7500.0,
}
```

Re-run tests.

**IMPORTANT — transitional stub removal in Task 3.0:**
After Task 3.0 ships `FIELD_REGISTRY`, add an explicit removal step to Task 3.0:
(a) Delete `_DEFAULTS` from `config_overrides.py`,
(b) Replace the last two lines of `get_field_source` (`return "tracked" if base_value != _DEFAULTS[field_path] else "default"`) with:
```python
    from swing.config_validation import FIELD_REGISTRY
    spec = next(s for s in FIELD_REGISTRY if s.path == field_path)
    return "tracked" if base_value != spec.default else "default"
```
This closes the dual-source risk (Codex R1 Major 2).

- [ ] **Step 5: Commit**

```bash
git add swing/config_overrides.py tests/config_overrides/
git commit -m "feat(config): Task 1.2 — apply_overrides + get_field_source per-request"
```

---

### Task 2.0: Replace obsolete chase_factor toml-shadow audit

**Files:**
- Modify: `tests/web/test_config_web.py` — DELETE `test_config_web_chase_factor_no_toml_shadow`
- Create: `tests/config_overrides/test_precedence_smoke.py`

- [ ] **Step 1: Delete obsolete test**

Edit `tests/web/test_config_web.py`. Remove the function `test_config_web_chase_factor_no_toml_shadow` (lines 184-245). Also remove its `import subprocess, pytest` if no other test uses them (re-check after edit; pytest is used by other tests so it stays).

- [ ] **Step 2: Run remaining tests in the file to verify they still pass**

```bash
python -m pytest tests/web/test_config_web.py -v
```

Expected: 6 PASS (was 7 before deletion; the 7th is removed).

- [ ] **Step 3: Add positive precedence smoke test**

Write `tests/config_overrides/test_precedence_smoke.py`:

```python
"""Precedence chain smoke: default → tracked → override (per locked decision §2.2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import load
from swing.config_overrides import apply_overrides, get_field_source
from swing.config_user import write_user_overrides
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    return tmp_path


def test_chase_factor_precedence_default(isolated: Path):
    cfg_path = _write_cfg(isolated / "project", isolated / "home")
    base = load(cfg_path)
    eff = apply_overrides(base)
    assert eff.web.chase_factor == 0.01  # registry default
    assert get_field_source(base, "web.chase_factor") == "default"


def test_chase_factor_precedence_tracked(isolated: Path):
    cfg_path = _write_cfg(
        isolated / "project", isolated / "home",
        extra="[web]\nchase_factor = 0.015\n",
    )
    base = load(cfg_path)
    eff = apply_overrides(base)
    assert eff.web.chase_factor == 0.015
    assert get_field_source(base, "web.chase_factor") == "tracked"


def test_chase_factor_precedence_override_beats_tracked(isolated: Path):
    cfg_path = _write_cfg(
        isolated / "project", isolated / "home",
        extra="[web]\nchase_factor = 0.015\n",
    )
    base = load(cfg_path)
    write_user_overrides({"web": {"chase_factor": 0.025}})
    eff = apply_overrides(base)
    assert eff.web.chase_factor == 0.025
    assert get_field_source(base, "web.chase_factor") == "override"
```

- [ ] **Step 4: Run new tests**

```bash
python -m pytest tests/config_overrides/test_precedence_smoke.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/web/test_config_web.py tests/config_overrides/test_precedence_smoke.py
git commit -m "refactor(config): Task 2.0 — replace obsolete chase_factor shadow audit with precedence smoke"
```

---

### Task 2.1: Wire `apply_overrides` into all 27 web-route reader sites + pipeline runner

**Files (modify):**
- `swing/web/routes/dashboard.py` — line 14
- `swing/web/routes/charts.py` — line 49
- `swing/web/routes/journal.py` — line 19
- `swing/web/routes/pipeline.py` — lines 39, 49, 184, 204, 224, 250, 296, 381 (8 sites)
- `swing/web/routes/recommendations.py` — lines 54, 93
- `swing/web/routes/trades.py` — lines 163, 215, 271, 696, 718, 802, 815, 845, 936, 963 (10 sites)
- `swing/web/routes/watchlist.py` — lines 18, 36, 58 (3 sites)
- `swing/pipeline/runner.py` — top of `run_pipeline`
- `swing/web/cli_cmd.py` (if it instantiates VMs/caches; verify before modifying)

- [ ] **Step 1: Write failing integration test for one site (dashboard)**

Create `tests/integration/__init__.py` and `tests/integration/test_config_end_to_end.py`:

```python
"""End-to-end: user-config write → next dashboard render uses override."""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from swing.config_user import write_user_overrides
from swing.web.app import create_app
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Lifespan-aware TestClient per CLAUDE.md TestClient rule."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    from swing.config import load
    cfg = load(cfg_path)
    app = create_app(cfg, cfg_path=cfg_path)
    with TestClient(app) as client:
        yield client


def test_chase_factor_override_visible_to_dashboard_route(
    app_client: TestClient,
):
    """Discriminating-test: override at 0.025 produces a different
    HypRecsExpandedVM.buy_limit than the default 0.01.

    Pre-fix path (apply_overrides not wired): dashboard reads
    request.app.state.cfg directly → buy_limit uses 0.01.
    Post-fix path (apply_overrides wired): dashboard reads
    apply_overrides(state.cfg) → buy_limit uses 0.025.

    For a candidate with pivot=$100:
    - chase_factor=0.01 → buy_limit = 101.0
    - chase_factor=0.025 → buy_limit = 102.5
    These differ; the assertion distinguishes pre/post-fix.
    """
    # This test requires a fixture pre-populating one A+ candidate +
    # one hypothesis recommendation. Fixture builder lives in
    # tests/conftest.py or a local helper. Reuse the existing
    # hyp-recs expansion test fixtures from tests/web/test_view_models/
    # test_hyp_recs_expansion_vm.py.
    # Implementation note: this is the structural test; the actual
    # fixture wiring is task-2.1 step 2.
    pytest.skip("fixture wiring in step 2")  # filled in below
```

- [ ] **Step 2: Wire fixture (or skip if scope blow-up)**

If the test fixture for a populated DB + candidate + hypothesis is more than 30 lines of setup, mark this test as a follow-up integration smoke and instead rely on the unit-level VM tests in `tests/web/test_view_models/test_hyp_recs_expansion_vm.py` which already cover the chase_factor read path. Add a parameterized fixture to that file that constructs the VM with `apply_overrides`-replaced cfg and asserts the override-applied buy_limit value.

Concrete fix in `tests/web/test_view_models/test_hyp_recs_expansion_vm.py`: add one new test that calls `apply_overrides` after writing a user-config override, then re-builds the VM, then asserts `buy_limit` reflects the override.

- [ ] **Step 3: Edit each route file**

For each of the 27 route reader sites listed in §B "Files to MODIFY":

1. Add a single module-top import (NOT per-handler) to each route file that doesn't already have it:

```python
from swing.config_overrides import apply_overrides
```

2. Replace every occurrence of `cfg = request.app.state.cfg` with:

```python
cfg = apply_overrides(request.app.state.cfg)
```

Use `git grep -l 'request\.app\.state\.cfg' swing/web/routes/` to confirm the full list before editing. Note that `swing/web/routes/pipeline.py` line 50 reads `cfg_path` (not `cfg`) — leave that line unchanged.

- [ ] **Step 4: Edit `swing/pipeline/__init__.py`** (Codex R1 Minor 1 — patch the PUBLIC wrapper, not the internal worker)

Current `swing/pipeline/__init__.py` is the single public entry point:

```python
# swing/pipeline/__init__.py — current (5-line wrapper around run_pipeline_internal)
from swing.pipeline.runner import RunResult, run_pipeline_internal

__all__ = ["RunResult", "run_pipeline"]

def run_pipeline(*, cfg, trigger: str = "manual") -> RunResult:
    return run_pipeline_internal(cfg=cfg, trigger=trigger)
```

Edit to apply overrides exactly once at the public boundary:

```python
from swing.config_overrides import apply_overrides
from swing.pipeline.runner import RunResult, run_pipeline_internal

__all__ = ["RunResult", "run_pipeline"]

def run_pipeline(*, cfg, trigger: str = "manual") -> RunResult:
    cfg = apply_overrides(cfg)
    return run_pipeline_internal(cfg=cfg, trigger=trigger)
```

Do NOT also call `apply_overrides` inside `swing/pipeline/runner.py:run_pipeline_internal` — every caller routes through the public wrapper, so a second invocation would be wasted (and could mask a future regression where an internal call bypasses the wrapper).

- [ ] **Step 5: Run full fast suite**

```bash
python -m pytest -m "not slow" -q
```

Expected: ALL EXISTING TESTS PASS (no regressions). The change is value-preserving when no user-config exists, which is the test environment's default.

- [ ] **Step 6: Run the override-applied VM test**

```bash
python -m pytest tests/web/test_view_models/test_hyp_recs_expansion_vm.py -v -k override
```

Expected: PASS — buy_limit reflects the user-config chase_factor override.

- [ ] **Step 7: Commit**

```bash
git add swing/web/routes/ swing/pipeline/runner.py tests/web/test_view_models/test_hyp_recs_expansion_vm.py tests/integration/
git commit -m "feat(config): Task 2.1 — wire apply_overrides at all route + pipeline cfg readers"
```

---

### Task 3.0: Field registry + validation (TDD)

**Files:**
- Create: `swing/config_validation.py`
- Create: `tests/config_validation/__init__.py`
- Create: `tests/config_validation/test_validation.py`

- [ ] **Step 1: Write failing tests**

```bash
mkdir -p tests/config_validation
touch tests/config_validation/__init__.py
```

Write `tests/config_validation/test_validation.py` (this is the §5 acceptance criteria — 12 boundary tests; one inside-bound, one outside-bound, per field × hard/soft):

```python
"""Field validation — hard-refuse + soft-warn boundaries per V1 field."""
from __future__ import annotations

import pytest

from swing.config_validation import (
    FIELD_REGISTRY,
    coerce_value,
    validate_all,
    validate_field,
)


# --- Registry shape ---


def test_registry_has_three_v1_fields():
    paths = {s.path for s in FIELD_REGISTRY}
    assert paths == {
        "web.chase_factor",
        "pipeline.chart_top_n_watch",
        "account.risk_equity_floor",
    }


# --- chase_factor: hard-refuse [0, 0.10]; soft-warn > 0.02 ---

def test_chase_factor_hard_refuse_negative():
    r = validate_field("web.chase_factor", "-0.01")
    assert r.hard_errors and not r.soft_warnings


def test_chase_factor_hard_refuse_above_max():
    r = validate_field("web.chase_factor", "0.11")
    assert r.hard_errors and not r.soft_warnings


def test_chase_factor_inside_hard_bound_soft_warn_above_2pct():
    r = validate_field("web.chase_factor", "0.05")
    assert not r.hard_errors and r.soft_warnings


def test_chase_factor_inside_both_no_issues():
    r = validate_field("web.chase_factor", "0.015")
    assert not r.hard_errors and not r.soft_warnings


# --- chart_top_n_watch: hard-refuse [1, 50]; soft-warn > 25 ---

def test_chart_top_n_watch_hard_refuse_zero():
    r = validate_field("pipeline.chart_top_n_watch", "0")
    assert r.hard_errors


def test_chart_top_n_watch_hard_refuse_above_50():
    r = validate_field("pipeline.chart_top_n_watch", "51")
    assert r.hard_errors


def test_chart_top_n_watch_inside_hard_bound_soft_warn_above_25():
    r = validate_field("pipeline.chart_top_n_watch", "30")
    assert not r.hard_errors and r.soft_warnings


def test_chart_top_n_watch_inside_both_no_issues():
    r = validate_field("pipeline.chart_top_n_watch", "20")
    assert not r.hard_errors and not r.soft_warnings


# --- risk_equity_floor: hard-refuse < 0; soft-warn outside [1000, 25000] ---

def test_risk_equity_floor_hard_refuse_negative():
    r = validate_field("account.risk_equity_floor", "-1.0")
    assert r.hard_errors


def test_risk_equity_floor_soft_warn_below_1000():
    r = validate_field("account.risk_equity_floor", "500.0")
    assert not r.hard_errors and r.soft_warnings


def test_risk_equity_floor_soft_warn_above_25000():
    r = validate_field("account.risk_equity_floor", "30000.0")
    assert not r.hard_errors and r.soft_warnings


def test_risk_equity_floor_inside_both_no_issues():
    r = validate_field("account.risk_equity_floor", "10000.0")
    assert not r.hard_errors and not r.soft_warnings


# --- Coercion ---

def test_coerce_chase_factor_str_to_float():
    assert coerce_value("web.chase_factor", "0.02") == 0.02
    assert isinstance(coerce_value("web.chase_factor", "0.02"), float)


def test_coerce_chart_top_n_str_to_int():
    assert coerce_value("pipeline.chart_top_n_watch", "15") == 15
    assert isinstance(coerce_value("pipeline.chart_top_n_watch", "15"), int)


def test_coerce_int_field_rejects_non_integer_float_string():
    """Codex R1 Major 3 — '15.5' rejected (not integer-valued)."""
    with pytest.raises(ValueError):
        coerce_value("pipeline.chart_top_n_watch", "15.5")


def test_coerce_int_field_accepts_integer_valued_float_string():
    """Codex R1 Major 3 — '15.0' accepted (browser-friendly UX)."""
    assert coerce_value("pipeline.chart_top_n_watch", "15.0") == 15
    assert isinstance(coerce_value("pipeline.chart_top_n_watch", "15.0"), int)


def test_coerce_invalid_string_raises():
    with pytest.raises(ValueError):
        coerce_value("web.chase_factor", "not-a-number")


# --- validate_all (form submit: all 3 at once) ---

def test_validate_all_happy_path():
    r = validate_all({
        "web.chase_factor": "0.015",
        "pipeline.chart_top_n_watch": "20",
        "account.risk_equity_floor": "10000.0",
    })
    assert not r.hard_errors and not r.soft_warnings


def test_validate_all_first_hard_refuse_short_circuits_write():
    """All hard errors are reported; write must still be refused at the route layer."""
    r = validate_all({
        "web.chase_factor": "0.5",  # hard fail
        "pipeline.chart_top_n_watch": "20",
        "account.risk_equity_floor": "10000.0",
    })
    assert r.hard_errors
    assert any("chase_factor" in e.field for e in r.hard_errors)


def test_validate_all_collects_multiple_hard_errors():
    r = validate_all({
        "web.chase_factor": "0.5",
        "pipeline.chart_top_n_watch": "100",
        "account.risk_equity_floor": "10000.0",
    })
    assert len(r.hard_errors) == 2
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/config_validation/ -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `swing/config_validation.py`**

```python
"""V1 field registry + validation. Single source of truth for web + CLI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    path: str
    label: str
    description: str
    type: type
    default: Any
    hard_refuse_min: Any | None
    hard_refuse_max: Any | None
    soft_warn_min: Any | None
    soft_warn_max: Any | None


@dataclass(frozen=True)
class ValidationError:
    field: str
    message: str


@dataclass(frozen=True)
class ValidationWarning:
    field: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    hard_errors: list[ValidationError] = field(default_factory=list)
    soft_warnings: list[ValidationWarning] = field(default_factory=list)


FIELD_REGISTRY: tuple[FieldSpec, ...] = (
    FieldSpec(
        path="web.chase_factor",
        label="Chase factor",
        description=(
            "Buy-limit pad above pivot. 0.01 = 1% above pivot. "
            "Operator's pure-trigger discipline favors values <= 0.02."
        ),
        type=float, default=0.01,
        hard_refuse_min=0.0, hard_refuse_max=0.10,
        soft_warn_min=None, soft_warn_max=0.02,
    ),
    FieldSpec(
        path="pipeline.chart_top_n_watch",
        label="Watchlist chart count",
        description="Number of watchlist tickers to render charts for in the nightly briefing.",
        type=int, default=10,
        hard_refuse_min=1, hard_refuse_max=50,
        soft_warn_min=None, soft_warn_max=25,
    ),
    FieldSpec(
        path="account.risk_equity_floor",
        label="Risk floor",
        description="Position-sizing floor: sizing_equity = max(real_equity, this).",
        type=float, default=7500.0,
        hard_refuse_min=0.0, hard_refuse_max=None,
        soft_warn_min=1000.0, soft_warn_max=25000.0,
    ),
)


_BY_PATH: dict[str, FieldSpec] = {s.path: s for s in FIELD_REGISTRY}


def get_spec(field_path: str) -> FieldSpec:
    if field_path not in _BY_PATH:
        raise ValueError(f"unknown field_path: {field_path}")
    return _BY_PATH[field_path]


def coerce_value(field_path: str, raw_value: str) -> Any:
    spec = get_spec(field_path)
    if spec.type is int:
        # Codex R1 Major 3 — accept integer-valued floats ("15.0" → 15) for
        # web-form UX (HTML `<input type="number" step="1">` can post a
        # trailing-zero float in some browser/locale combinations). Reject
        # only non-integer floats ("15.5" → ValueError).
        try:
            f = float(raw_value)
        except ValueError as exc:
            raise ValueError(f"{field_path} requires an integer; got {raw_value!r}") from exc
        if not f.is_integer():
            raise ValueError(f"{field_path} requires an integer; got {raw_value!r}")
        return int(f)
    if spec.type is float:
        return float(raw_value)
    raise ValueError(f"unsupported type for {field_path}: {spec.type}")


def validate_field(field_path: str, raw_value: str) -> ValidationResult:
    spec = get_spec(field_path)
    try:
        value = coerce_value(field_path, raw_value)
    except ValueError as exc:
        return ValidationResult(
            hard_errors=[ValidationError(field=field_path, message=str(exc))],
        )
    hard: list[ValidationError] = []
    soft: list[ValidationWarning] = []
    if spec.hard_refuse_min is not None and value < spec.hard_refuse_min:
        hard.append(ValidationError(
            field=field_path,
            message=f"{spec.label} must be >= {spec.hard_refuse_min}; got {value}",
        ))
    if spec.hard_refuse_max is not None and value > spec.hard_refuse_max:
        hard.append(ValidationError(
            field=field_path,
            message=f"{spec.label} must be <= {spec.hard_refuse_max}; got {value}",
        ))
    if hard:
        return ValidationResult(hard_errors=hard)
    if spec.soft_warn_min is not None and value < spec.soft_warn_min:
        soft.append(ValidationWarning(
            field=field_path,
            message=(
                f"{spec.label} = {value} is below the typical floor "
                f"of {spec.soft_warn_min}. Confirm intent."
            ),
        ))
    if spec.soft_warn_max is not None and value > spec.soft_warn_max:
        soft.append(ValidationWarning(
            field=field_path,
            message=(
                f"{spec.label} = {value} is above the typical ceiling "
                f"of {spec.soft_warn_max}. Confirm intent."
            ),
        ))
    return ValidationResult(soft_warnings=soft)


def validate_all(form: dict[str, str]) -> ValidationResult:
    """Validate every V1 field present in `form`. Hard errors short-circuit no
    individual write; route layer is responsible for refusing the WRITE on
    any hard error. Soft warnings on multiple fields all surface.
    """
    hard: list[ValidationError] = []
    soft: list[ValidationWarning] = []
    for spec in FIELD_REGISTRY:
        if spec.path not in form:
            continue
        r = validate_field(spec.path, form[spec.path])
        hard.extend(r.hard_errors)
        soft.extend(r.soft_warnings)
    return ValidationResult(hard_errors=hard, soft_warnings=soft)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/config_validation/ -v
```

Expected: ~18 PASS (12 boundary + coercion + validate_all).

- [ ] **Step 4b: Remove transitional `_DEFAULTS` stub from `config_overrides.py` (Codex R1 Major 2 resolution)**

Edit `swing/config_overrides.py`:
1. Delete the `_DEFAULTS: dict[str, Any] = { ... }` block (3 lines).
2. Replace the last two lines of `get_field_source` with:
```python
    from swing.config_validation import FIELD_REGISTRY
    spec = next(s for s in FIELD_REGISTRY if s.path == field_path)
    return "tracked" if base_value != spec.default else "default"
```
3. Remove `from typing import Any` if it becomes unused after deleting `_DEFAULTS`.

Run:
```bash
python -m pytest tests/config_overrides/ tests/config_validation/ -v
```
Expected: all PASS (no circular import; `config_validation` imports nothing from `config_overrides`; `config_overrides` imports from `config_validation` only inside `get_field_source`).

- [ ] **Step 5: Commit**

```bash
git add swing/config_validation.py swing/config_overrides.py tests/config_validation/
git commit -m "feat(config): Task 3.0 — field registry + hard/soft validation; remove _DEFAULTS stub"
```

---

### Task 4.0: ConfigPageVM + builder (TDD)

**Files:**
- Create: `swing/web/view_models/config.py`
- Create: `tests/web/test_view_models/test_config_vm.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_view_models/test_config_vm.py
"""ConfigPageVM exposes 3 rows with current/default/source/input_kind."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import load
from swing.config_user import write_user_overrides
from swing.web.view_models.config import build_config_vm
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def base_cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    return load(cfg_path)


def test_vm_has_three_rows(base_cfg):
    vm = build_config_vm(base_cfg)
    assert len(vm.rows) == 3
    paths = [r.path for r in vm.rows]
    assert paths == [
        "web.chase_factor",
        "pipeline.chart_top_n_watch",
        "account.risk_equity_floor",
    ]


def test_vm_default_source_when_no_overrides(base_cfg):
    vm = build_config_vm(base_cfg)
    for row in vm.rows:
        assert row.source == "default"


def test_vm_override_source_after_user_config_write(base_cfg):
    write_user_overrides({"web": {"chase_factor": 0.025}})
    vm = build_config_vm(base_cfg)
    cf_row = next(r for r in vm.rows if r.path == "web.chase_factor")
    assert cf_row.source == "override"
    assert cf_row.current_value == 0.025


def test_vm_default_value_per_row(base_cfg):
    vm = build_config_vm(base_cfg)
    by_path = {r.path: r for r in vm.rows}
    assert by_path["web.chase_factor"].default_value == 0.01
    assert by_path["pipeline.chart_top_n_watch"].default_value == 10
    assert by_path["account.risk_equity_floor"].default_value == 7500.0


def test_vm_includes_session_date_for_base_layout(base_cfg):
    vm = build_config_vm(base_cfg)
    assert hasattr(vm, "session_date")
    assert isinstance(vm.session_date, str)


def test_vm_base_layout_banner_fields_safe_defaults(base_cfg):
    """CLAUDE.md base.html.j2 5-VM rule check: although Task 7 confirmed the
    nav link is static (no new field needed), the base layout DOES dereference
    stale_banner / price_source_degraded / ohlcv_source_degraded for banner
    rendering. ConfigPageVM must include these with safe defaults to avoid
    Jinja UndefinedError when /config renders.
    """
    vm = build_config_vm(base_cfg)
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.ohlcv_source_degraded is False
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/web/test_view_models/test_config_vm.py -v
```

Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `swing/web/view_models/config.py`**

```python
"""ConfigPageVM + build_config_vm."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from swing.config import Config
from swing.config_overrides import apply_overrides, get_field_source
from swing.config_validation import FIELD_REGISTRY, FieldSpec


@dataclass(frozen=True)
class ConfigFieldRow:
    path: str
    label: str
    description: str
    current_value: Any
    default_value: Any
    source: str         # "default" | "tracked" | "override"
    input_kind: str     # "float" | "int" — drives <input type="number" step="...">
    soft_warn_min: Any | None
    soft_warn_max: Any | None
    hard_refuse_min: Any | None
    hard_refuse_max: Any | None


@dataclass(frozen=True)
class ConfigPageVM:
    rows: list[ConfigFieldRow]
    saved: bool                                # set by ?saved=1 redirect-back
    # Base-layout banner fields (CLAUDE.md base.html.j2 5-VM rule check —
    # these fields are dereferenced by base.html.j2 even when Task 7 confirmed
    # the nav link is static; the VM still inherits the banner-field schema).
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False


def _current_value(cfg: Config, spec: FieldSpec) -> Any:
    section, key = spec.path.split(".")
    return getattr(getattr(cfg, section), key)


def build_config_vm(base_cfg: Config, *, saved: bool = False) -> ConfigPageVM:
    eff = apply_overrides(base_cfg)
    rows: list[ConfigFieldRow] = []
    for spec in FIELD_REGISTRY:
        rows.append(ConfigFieldRow(
            path=spec.path,
            label=spec.label,
            description=spec.description,
            current_value=_current_value(eff, spec),
            default_value=spec.default,
            source=get_field_source(base_cfg, spec.path),
            input_kind="int" if spec.type is int else "float",
            soft_warn_min=spec.soft_warn_min,
            soft_warn_max=spec.soft_warn_max,
            hard_refuse_min=spec.hard_refuse_min,
            hard_refuse_max=spec.hard_refuse_max,
        ))
    return ConfigPageVM(
        rows=rows,
        saved=saved,
        session_date=date.today().isoformat(),
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/web/test_view_models/test_config_vm.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/config.py tests/web/test_view_models/test_config_vm.py
git commit -m "feat(config): Task 4.0 — ConfigPageVM with rows + source badge"
```

---

### Task 4.1: Route handlers (GET / POST / reset) (TDD)

**Files:**
- Create: `swing/web/routes/config.py`
- Modify: `swing/web/app.py` — register router
- Create: `tests/web/test_config_route.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_config_route.py
"""GET/POST/reset handlers for /config. Lifespan-wrapped TestClient."""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from swing.config import load
from swing.config_user import load_user_overrides, write_user_overrides
from swing.web.app import create_app
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    cfg = load(cfg_path)
    app = create_app(cfg, cfg_path=cfg_path)
    with TestClient(app) as c:
        yield c


def test_get_config_renders_three_rows(client: TestClient):
    r = client.get("/config")
    assert r.status_code == 200
    body = r.text
    assert "Chase factor" in body
    assert "Watchlist chart count" in body
    assert "Risk floor" in body


def test_get_config_shows_default_source_badge(client: TestClient):
    r = client.get("/config")
    assert "default" in r.text  # source badge for at least one row


def test_post_happy_path_writes_and_redirects(client: TestClient):
    r = client.post("/config", data={
        "web.chase_factor": "0.015",
        "pipeline.chart_top_n_watch": "20",
        "account.risk_equity_floor": "10000.0",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/config")
    assert load_user_overrides() == {
        "web": {"chase_factor": 0.015},
        "pipeline": {"chart_top_n_watch": 20},
        "account": {"risk_equity_floor": 10000.0},
    }


def test_post_hard_refuse_returns_error_fragment_no_write(client: TestClient):
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.5",  # hard fail
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 400
    assert "Chase factor" in r.text
    assert "<= 0.1" in r.text or "<= 0.10" in r.text
    # No write happened
    assert load_user_overrides() == {}
    # CLAUDE.md HTMX <tr>-leading guard: response root must NOT be <tr>.
    assert not r.text.lstrip().startswith("<tr")


def test_post_soft_warn_returns_confirm_fragment_with_form_values(
    client: TestClient,
):
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.05",  # soft-warn (above 0.02)
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    body = r.text
    assert "force" in body and "true" in body  # hidden input round-trip
    assert "0.05" in body                       # proposed value preserved
    assert "Confirm" in body or "Submit anyway" in body
    # Crucially: NO write yet
    assert load_user_overrides() == {}


def test_post_force_true_persists_soft_warn_value(client: TestClient):
    """Round-trip ToCToU: force=true resubmit with form_values writes them."""
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.05",
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
            "force": "true",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert load_user_overrides() == {
        "web": {"chase_factor": 0.05},
        "pipeline": {"chart_top_n_watch": 20},
        "account": {"risk_equity_floor": 10000.0},
    }


def test_post_reset_deletes_field(client: TestClient):
    write_user_overrides({"web": {"chase_factor": 0.025}})
    r = client.post(
        "/config/reset/web.chase_factor",
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert load_user_overrides() == {}


def test_post_reset_all_three_dotted_paths_accepted(client: TestClient):
    """Routing test matrix: Starlette path converter captures dots.

    Codex R1 Major 5: must verify all three actual dotted field paths
    are accepted end-to-end, not just one example.
    """
    for field_path in (
        "web.chase_factor",
        "pipeline.chart_top_n_watch",
        "account.risk_equity_floor",
    ):
        write_user_overrides({
            field_path.split(".")[0]: {field_path.split(".")[1]: 999},
        })
        r = client.post(
            f"/config/reset/{field_path}",
            follow_redirects=False,
        )
        assert r.status_code == 303, f"Expected 303 for {field_path}, got {r.status_code}"


def test_cancel_link_is_plain_anchor_not_htmx(client: TestClient):
    """Codex R1 Major 4 — confirm fragment's Cancel must be a plain <a href>
    that triggers full-page navigation. NOT an hx-get (which would swap a
    full-page response into <body> and corrupt the DOM).
    """
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.05",
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    body = r.text
    # Cancel: plain <a> with full-page href.
    assert '<a' in body and 'href="/config"' in body
    # Negative-discriminator: no hx-get on the Cancel control.
    # (hx-get on a Submit-anyway form is OK; it's the Cancel that must be plain.)
    assert "Cancel" in body
    # Round-trip Cancel manually: GET /config returns a 200 full page.
    g = client.get("/config")
    assert g.status_code == 200
    assert "<html" in g.text.lower()


def test_post_reset_unknown_field_404(client: TestClient):
    r = client.post(
        "/config/reset/web.fake_field",
        follow_redirects=False,
    )
    assert r.status_code == 404


def test_post_unchanged_submit_does_not_create_overrides(client: TestClient):
    """Codex R1 Critical 1 — merge semantics. Submit the form WITHOUT changing
    any value (each input still holds its current effective value, which
    equals the registry default in this fixture) → no overrides written.

    Discriminating-test: the WRONG (replace) implementation would write all
    three values as overrides; this test fails it. The CORRECT (merge)
    implementation leaves user-config empty.
    """
    r = client.post("/config", data={
        "web.chase_factor": "0.01",            # == registry default
        "pipeline.chart_top_n_watch": "10",    # == registry default
        "account.risk_equity_floor": "7500.0", # == registry default
    }, follow_redirects=False)
    assert r.status_code == 303
    assert load_user_overrides() == {}


def test_post_changed_one_field_does_not_lock_others(client: TestClient):
    """Codex R1 Critical 1 — only changed fields become overrides."""
    r = client.post("/config", data={
        "web.chase_factor": "0.015",           # changed
        "pipeline.chart_top_n_watch": "10",    # unchanged (default)
        "account.risk_equity_floor": "7500.0", # unchanged (default)
    }, follow_redirects=False)
    assert r.status_code == 303
    assert load_user_overrides() == {"web": {"chase_factor": 0.015}}
    # chart_top_n_watch + risk_equity_floor source must remain 'default'
    g = client.get("/config")
    assert g.text.count("source-default") >= 2
    assert g.text.count("source-override") >= 1


def test_post_preserves_unknown_user_config_keys(
    client: TestClient,
):
    """Codex R1 Critical 1 — forward-compat with future V2 keys.

    An operator who hand-edited user-config to set a hypothetical V2 field
    (e.g. risk.max_risk_pct) must NOT see that key wiped by a V1 page save.
    """
    write_user_overrides({
        "web": {"chase_factor": 0.025},
        "risk": {"max_risk_pct": 0.01},   # V2 hypothetical — V1 page must preserve it
    })
    r = client.post("/config", data={
        "web.chase_factor": "0.030",            # changed
        "pipeline.chart_top_n_watch": "10",
        "account.risk_equity_floor": "7500.0",
    }, follow_redirects=False)
    assert r.status_code == 303
    saved = load_user_overrides()
    assert saved["web"]["chase_factor"] == 0.030
    assert saved["risk"] == {"max_risk_pct": 0.01}, (
        "unknown user-config keys must survive V1 saves"
    )


def test_post_preserves_top_level_scalar_unknown_key(
    client: TestClient,
):
    """Codex R2 Major 2 — deepcopy preservation must NOT assume every
    top-level value is a section table.

    Discriminating-test: hand-add a top-level scalar to user-config (TOML
    permits this) and verify a V1 page save preserves it. A naive
    one-level dict-comp `{section: dict(table) for ...}` would crash with
    a TypeError when iterating dict() over a non-dict value.
    """
    write_user_overrides({
        "web": {"chase_factor": 0.025},
        "experimental_flag": True,           # top-level scalar (operator-added)
    })
    r = client.post("/config", data={
        "web.chase_factor": "0.030",
        "pipeline.chart_top_n_watch": "10",
        "account.risk_equity_floor": "7500.0",
    }, follow_redirects=False)
    assert r.status_code == 303
    saved = load_user_overrides()
    assert saved["web"]["chase_factor"] == 0.030
    assert saved["experimental_flag"] is True, (
        "top-level scalar keys must survive V1 saves (Codex R2 M2)"
    )


def test_post_force_true_with_hard_refuse_value_still_refused(
    client: TestClient,
):
    """force=true bypasses soft-warn ONLY, never hard-refuse. Discriminating-test:
    a hard-refuse-value resubmit with force=true must be 400 + no write.
    """
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.5",  # hard fail
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
            "force": "true",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 400
    assert load_user_overrides() == {}
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/web/test_config_route.py -v
```

Expected: FAIL — route not registered.

- [ ] **Step 3: Implement `swing/web/routes/config.py`**

```python
"""Config page routes."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from swing.config_overrides import apply_overrides
from swing.config_user import (
    delete_user_override,
    load_user_overrides,
    write_user_overrides,
)
from swing.config_validation import (
    FIELD_REGISTRY,
    coerce_value,
    validate_all,
)
from swing.web.view_models.config import build_config_vm

router = APIRouter()

_FIELD_PATHS = tuple(s.path for s in FIELD_REGISTRY)


@router.get("/config", response_class=HTMLResponse)
def config_page(request: Request, saved: int = 0):
    cfg = apply_overrides(request.app.state.cfg)
    vm = build_config_vm(cfg, saved=bool(saved))
    return request.app.state.templates.TemplateResponse(
        request, "config.html.j2", {"vm": vm},
    )


@router.post("/config", response_class=HTMLResponse)
async def config_save(request: Request):
    form = await request.form()
    payload: dict[str, str] = {p: form.get(p, "") for p in _FIELD_PATHS}
    force = form.get("force", "").lower() == "true"

    result = validate_all(payload)

    # Hard errors ALWAYS short-circuit, even with force=true.
    if result.hard_errors:
        return request.app.state.templates.TemplateResponse(
            request, "partials/config_hard_refuse.html.j2",
            {"errors": result.hard_errors, "form_values": dict(payload)},
            status_code=400,
        )

    # Soft warnings + not-force → confirm fragment.
    if result.soft_warnings and not force:
        return request.app.state.templates.TemplateResponse(
            request, "partials/config_soft_warn_confirm.html.j2",
            {"warnings": result.soft_warnings, "form_values": dict(payload)},
            status_code=200,
        )

    # Happy path (no warnings) OR force=true confirm-resubmit → write.
    #
    # Codex R1 Critical 1 — MERGE semantics, NOT replace semantics. Three
    # invariants below preserve the spec's "default / tracked / override"
    # source-fidelity contract and forward-compat with future V2 keys:
    #
    #   (a) Untouched fields remain untouched. Compare each submitted value
    #       against the CURRENT EFFECTIVE value (after current overrides).
    #       Identical → no override write/delete for that field. The source
    #       badge stays as it was (default / tracked / override).
    #
    #   (b) Changed fields become explicit overrides. submitted != current
    #       effective → write the new value into user-config (under its
    #       canonical section). This is the only mutation path.
    #
    #   (c) Unknown user-config keys are preserved. Future V2 fields hand-
    #       added by the operator (or shipped by a later dispatch) survive
    #       a V1 page save unmodified.
    #
    # Locking a value at the registry default still works: from a 'tracked'
    # source, the operator types the registry default and submits — the new
    # value differs from the tracked-toml value, so it is written as an
    # override per (b). From a 'default' source, retyping the default is a
    # no-op per (a); the operator can use the CLI `swing config set` (which
    # writes unconditionally on operator-typed input) for the corner case
    # of locking-at-default-from-default.
    import copy as _copy
    base_cfg = request.app.state.cfg
    eff_cfg = apply_overrides(base_cfg)
    # Codex R2 Major 2 — `copy.deepcopy` (NOT a one-level dict comprehension)
    # so unknown user-config keys at ANY nesting level survive — including
    # hypothetical top-level scalars (e.g. `experimental_flag = true` at the
    # user-config root) and nested tables under future V2 sections. The
    # one-level dict-comp pattern would have crashed on a top-level scalar.
    new_overrides: dict = _copy.deepcopy(load_user_overrides())
    for spec in FIELD_REGISTRY:
        section, key = spec.path.split(".")
        submitted = coerce_value(spec.path, payload[spec.path])
        current_eff = getattr(getattr(eff_cfg, section), key)
        if submitted == current_eff:
            continue  # invariant (a)
        new_overrides.setdefault(section, {})[key] = submitted  # invariant (b)
    write_user_overrides(new_overrides)
    return RedirectResponse(url="/config?saved=1", status_code=303)


@router.post("/config/reset/{field_path}", response_class=HTMLResponse)
async def config_reset(request: Request, field_path: str):
    """Reset one field. Single path-segment captures the dotted field path
    (e.g. /config/reset/web.chase_factor) — Starlette's default path
    converter `[^/]+` captures up to the next slash, dot included.
    """
    if field_path not in _FIELD_PATHS:
        raise HTTPException(status_code=404, detail=f"unknown field: {field_path}")
    delete_user_override(field_path)
    return RedirectResponse(url="/config?saved=1", status_code=303)
```

- [ ] **Step 4: Register router in `swing/web/app.py`**

In the imports block at line 289-296:

```python
from swing.web.routes import (
    config as config_route,           # NEW
    dashboard as dashboard_route,
    journal as journal_route,
    pipeline as pipeline_route,
    recommendations as recommendations_route,
    trades as trades_route,
    watchlist as watchlist_route,
)
app.include_router(dashboard_route.router)
app.include_router(watchlist_route.router)
app.include_router(journal_route.router)
app.include_router(pipeline_route.router)
app.include_router(trades_route.router)
app.include_router(recommendations_route.router)
app.include_router(config_route.router)            # NEW
```

- [ ] **Step 5: Templates — minimal versions to make tests pass**

Create `swing/web/templates/config.html.j2`:

```jinja
{% extends "base.html.j2" %}
{% block content %}
<h1>Configuration</h1>
{% if vm.saved %}
  <div class="banner success">Saved.</div>
{% endif %}
<form method="post" action="/config" id="config-form"
      hx-post="/config" hx-target="#config-form-result" hx-swap="innerHTML"
      hx-headers='{"HX-Request": "true"}'>
  {% for row in vm.rows %}
    <div class="config-row">
      <label for="{{ row.path }}">
        {{ row.label }}
        <small class="muted">({{ row.path }})</small>
      </label>
      <p class="description">{{ row.description }}</p>
      <input
        type="number"
        id="{{ row.path }}"
        name="{{ row.path }}"
        value="{{ row.current_value }}"
        {% if row.input_kind == 'int' %}step="1"{% else %}step="0.001"{% endif %}
      />
      <span class="default-value">default: {{ row.default_value }}</span>
      <span class="source-badge source-{{ row.source }}">{{ row.source }}</span>
    </div>
  {% endfor %}
  <button type="submit">Save</button>
</form>
<div id="config-form-result"></div>

{% for row in vm.rows %}
  <form method="post" action="/config/reset/{{ row.path }}" class="reset-form">
    <button type="submit" class="reset-btn">Reset {{ row.label }}</button>
  </form>
{% endfor %}
{% endblock %}
```

Create `swing/web/templates/partials/config_hard_refuse.html.j2`:

```jinja
<div class="banner error" role="alert">
  <strong>Cannot save — invalid values.</strong>
  <ul>
    {% for err in errors %}
      <li>{{ err.message }}</li>
    {% endfor %}
  </ul>
</div>
```

Create `swing/web/templates/partials/config_soft_warn_confirm.html.j2`:

```jinja
{#- Soft-warn confirmation fragment for /config.
    Mirrors swing/web/templates/partials/soft_warn_confirm.html.j2 pattern,
    BUT root element is <div> not <tr> (CLAUDE.md HTMX <tr>-leading
    makeFragment pathology — config form is NOT inside a <table>).

    form_values round-trip per spec §3.6 + multi-path-ingestion lesson:
    every key in form_values rides along as hidden input on the
    force=true resubmit so the originally-typed values persist
    AS-IS (NOT re-fetched from current user-config).
-#}
<div class="banner warn" role="alert">
  <strong>Confirm: values exceed the typical range.</strong>
  <ul>
    {% for w in warnings %}
      <li>{{ w.message }}</li>
    {% endfor %}
  </ul>
  <form hx-post="/config" hx-target="#config-form-result" hx-swap="innerHTML"
        hx-headers='{"HX-Request": "true"}'>
    {% for key, value in form_values.items() %}
      <input type="hidden" name="{{ key }}" value="{{ value }}">
    {% endfor %}
    <input type="hidden" name="force" value="true">
    <button type="submit">Submit anyway</button>
  </form>
  {#- Codex R1 Major 4 — Cancel is a plain full-page navigation, NOT an
      HTMX hx-get. GET /config returns a FULL-PAGE response (extends
      base.html.j2); swapping the entire response into <body> via HTMX
      would inject a nested <html><body> structure and break the layout.
      A plain <a> triggers a normal browser navigation, which renders the
      full page cleanly and discards the operator's typed values
      (correct: Cancel discards). -#}
  <a class="btn btn-secondary" href="/config" role="button">Cancel</a>
</div>
```

- [ ] **Step 6: Add nav link to `base.html.j2`**

Edit `swing/web/templates/base.html.j2`. After the `<a href="/pipeline">Pipeline</a>` line, add:

```html
    <a href="/config">Config</a>
```

- [ ] **Step 7: Run tests**

```bash
python -m pytest tests/web/test_config_route.py -v
```

Expected: 9 PASS.

- [ ] **Step 8: Commit**

```bash
git add swing/web/routes/config.py swing/web/app.py swing/web/templates/config.html.j2 swing/web/templates/partials/config_hard_refuse.html.j2 swing/web/templates/partials/config_soft_warn_confirm.html.j2 swing/web/templates/base.html.j2 tests/web/test_config_route.py
git commit -m "feat(config): Task 4.1 — /config GET/POST/reset routes + templates + nav link"
```

---

### Task 5.0: Template render verification (TDD)

**Files:**
- Create: `tests/web/test_config_template.py`

- [ ] **Step 1: Write tests**

```python
"""Template rendering: rows, source badges, reset forms, no-<tr>-root partial."""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from swing.config import load
from swing.config_user import write_user_overrides
from swing.web.app import create_app
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    cfg = load(cfg_path)
    app = create_app(cfg, cfg_path=cfg_path)
    with TestClient(app) as c:
        yield c


def test_template_renders_all_three_rows(client: TestClient):
    r = client.get("/config")
    body = r.text
    for label in ("Chase factor", "Watchlist chart count", "Risk floor"):
        assert label in body


def test_template_source_badge_default_when_no_overrides(client: TestClient):
    r = client.get("/config")
    # Each row's source badge text appears.
    assert r.text.count("source-default") >= 3


def test_template_source_badge_override_when_user_config_present(client: TestClient):
    write_user_overrides({"web": {"chase_factor": 0.02}})
    r = client.get("/config")
    assert "source-override" in r.text


def test_template_each_row_has_separate_reset_form(client: TestClient):
    r = client.get("/config")
    # Three reset-form occurrences (one per V1 field).
    assert r.text.count('class="reset-form"') == 3


def test_soft_warn_fragment_root_is_not_tr(client: TestClient):
    """CLAUDE.md HTMX <tr>-leading makeFragment guard.

    Codex R1 Minor 2 — this server-side assertion ONLY proves the
    response payload's first non-whitespace token is not '<tr'. It does
    NOT exercise htmx.js makeFragment parsing. The CANONICAL guard for
    the <tr>-leading pathology (failure mode 2026-04-29) is the operator-
    witnessed browser smoke in Task 7.0 step 4 — TestClient cannot
    detect a parser-mangled OOB swap because it only sees the response
    bytes, not the post-parse DOM. Treat this test as a structural
    sanity check, not a sufficient guard.
    """
    r = client.post(
        "/config",
        data={
            "web.chase_factor": "0.05",
            "pipeline.chart_top_n_watch": "20",
            "account.risk_equity_floor": "10000.0",
        },
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert not r.text.lstrip().startswith("<tr")
    # Form-values round-trip: the iterator emits hidden inputs.
    assert 'name="web.chase_factor"' in r.text
    assert 'value="0.05"' in r.text


def test_nav_link_present_on_dashboard(client: TestClient):
    """Static nav link added in base.html.j2."""
    r = client.get("/")
    assert 'href="/config"' in r.text


def test_saved_banner_renders_when_saved_query_set(client: TestClient):
    r = client.get("/config?saved=1")
    assert "Saved" in r.text or "saved" in r.text
```

- [ ] **Step 2: Run**

```bash
python -m pytest tests/web/test_config_template.py -v
```

Expected: 7 PASS (templates from Task 4.1 cover this).

- [ ] **Step 3: Commit**

```bash
git add tests/web/test_config_template.py
git commit -m "test(config): Task 5.0 — template render + source badge + no-<tr>-root verification"
```

---

### Task 6.0: CLI parity (TDD)

**Files:**
- Create: `swing/cli_config.py`
- Modify: `swing/cli.py` — register `config` group
- Create: `tests/cli/test_cli_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/cli/test_cli_config.py
"""swing config show/set/reset — CLI parity with web routes."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.config_user import load_user_overrides, write_user_overrides
from tests.web.test_config_web import _write_cfg


@pytest.fixture
def runner_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    (tmp_path / "project").mkdir()
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    return CliRunner(), cfg_path


def test_show_lists_three_fields_default_source(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, ["--config", str(cfg_path), "config", "show"])
    assert r.exit_code == 0, r.output
    assert "Chase factor" in r.output
    assert "Watchlist chart count" in r.output
    assert "Risk floor" in r.output
    assert "default" in r.output
    # Default values present
    assert "0.01" in r.output
    assert "10" in r.output
    assert "7500" in r.output


def test_show_marks_override_after_set(runner_env):
    runner, cfg_path = runner_env
    write_user_overrides({"web": {"chase_factor": 0.025}})
    r = runner.invoke(main, ["--config", str(cfg_path), "config", "show"])
    assert "override" in r.output
    assert "0.025" in r.output


def test_set_writes_user_config(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set", "web.chase_factor", "0.015",
    ])
    assert r.exit_code == 0
    assert load_user_overrides() == {"web": {"chase_factor": 0.015}}


def test_set_hard_refuse_exits_nonzero_with_stderr(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set", "web.chase_factor", "0.5",
    ])
    assert r.exit_code != 0
    assert "must be" in r.output.lower() or "<=" in r.output
    assert load_user_overrides() == {}


def test_set_soft_warn_prompts_yes(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(
        main,
        ["--config", str(cfg_path), "config", "set", "web.chase_factor", "0.05"],
        input="y\n",
    )
    assert r.exit_code == 0
    assert "Confirm" in r.output or "above the typical" in r.output
    assert load_user_overrides() == {"web": {"chase_factor": 0.05}}


def test_set_soft_warn_prompts_no_does_not_write(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(
        main,
        ["--config", str(cfg_path), "config", "set", "web.chase_factor", "0.05"],
        input="n\n",
    )
    assert r.exit_code != 0  # aborted
    assert load_user_overrides() == {}


def test_set_force_skips_prompt_for_soft_warn(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set",
        "--force", "web.chase_factor", "0.05",
    ])
    assert r.exit_code == 0
    assert load_user_overrides() == {"web": {"chase_factor": 0.05}}


def test_set_force_does_not_bypass_hard_refuse(runner_env):
    """Discriminating-test: --force only bypasses soft-warn, NEVER hard-refuse."""
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set",
        "--force", "web.chase_factor", "0.5",  # hard fail
    ])
    assert r.exit_code != 0
    assert load_user_overrides() == {}


def test_set_unknown_field_exits_nonzero(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "set", "web.fake_field", "1.0",
    ])
    assert r.exit_code != 0


def test_reset_removes_field(runner_env):
    runner, cfg_path = runner_env
    write_user_overrides({"web": {"chase_factor": 0.025}})
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "reset", "web.chase_factor",
    ])
    assert r.exit_code == 0
    assert load_user_overrides() == {}


def test_reset_unknown_field_exits_nonzero(runner_env):
    runner, cfg_path = runner_env
    r = runner.invoke(main, [
        "--config", str(cfg_path), "config", "reset", "web.fake_field",
    ])
    assert r.exit_code != 0
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/cli/test_cli_config.py -v
```

Expected: FAIL — no `config` subgroup.

- [ ] **Step 3: Implement `swing/cli_config.py`**

```python
"""swing config show/set/reset — CLI parity with /config web page.

Shares the validation registry from swing.config_validation; same
hard/soft semantics.
"""
from __future__ import annotations

import click

from swing.config_overrides import apply_overrides, get_field_source
from swing.config_user import (
    delete_user_override,
    load_user_overrides,
    write_user_overrides,
)
from swing.config_validation import (
    FIELD_REGISTRY,
    coerce_value,
    validate_field,
)


_FIELD_PATHS = tuple(s.path for s in FIELD_REGISTRY)


@click.group("config")
def config_group() -> None:
    """View / edit operator-tunable settings (user-config.toml)."""


@config_group.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Print all V1 fields with current value, default, source."""
    base_cfg = ctx.obj["config"]
    eff = apply_overrides(base_cfg)
    click.echo(f"{'Field':<32} {'Current':<12} {'Default':<12} Source")
    click.echo("-" * 72)
    for spec in FIELD_REGISTRY:
        section, key = spec.path.split(".")
        current = getattr(getattr(eff, section), key)
        source = get_field_source(base_cfg, spec.path)
        click.echo(
            f"{spec.label + ' (' + spec.path + ')':<32} "
            f"{current!s:<12} {spec.default!s:<12} {source}"
        )


@config_group.command("set")
@click.argument("field_path", type=click.Choice(_FIELD_PATHS))
@click.argument("raw_value", type=str)
@click.option("--force", is_flag=True, help="Bypass soft-warn confirmation prompts")
@click.pass_context
def config_set(ctx: click.Context, field_path: str, raw_value: str, force: bool) -> None:
    """Set a field. Hard-refuse exits non-zero. Soft-warn prompts y/n unless --force."""
    result = validate_field(field_path, raw_value)
    if result.hard_errors:
        for err in result.hard_errors:
            click.echo(f"ERROR: {err.message}", err=True)
        ctx.exit(1)
    if result.soft_warnings and not force:
        click.echo("Confirm: values exceed the typical range.")
        for w in result.soft_warnings:
            click.echo(f"  - {w.message}")
        if not click.confirm("Proceed?", default=False):
            click.echo("Aborted.")
            ctx.exit(2)
    coerced = coerce_value(field_path, raw_value)
    overrides = load_user_overrides()
    section, key = field_path.split(".")
    overrides.setdefault(section, {})[key] = coerced
    write_user_overrides(overrides)
    click.echo(f"Set {field_path} = {coerced}")


@config_group.command("reset")
@click.argument("field_path", type=click.Choice(_FIELD_PATHS))
@click.pass_context
def config_reset(ctx: click.Context, field_path: str) -> None:
    """Remove a field from user-config.toml (subsequent reads fall through)."""
    delete_user_override(field_path)
    click.echo(f"Reset {field_path} (now reads from default/tracked).")
```

- [ ] **Step 4: Register `config_group` in `swing/cli.py`**

After existing imports (around line 21):

```python
from swing.cli_config import config_group
```

After existing `main.add_command` / group definitions (or simply at module bottom before `if __name__ == "__main__":`):

```python
main.add_command(config_group)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/cli/test_cli_config.py -v
```

Expected: 11 PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/cli_config.py swing/cli.py tests/cli/test_cli_config.py
git commit -m "feat(config): Task 6.0 — swing config show/set/reset CLI parity"
```

---

### Task 7.0: Base-layout VM check + final integration smoke

**Files:**
- (verification only) `swing/web/templates/base.html.j2`
- (verification only) `swing/web/view_models/{dashboard,pipeline,journal,watchlist,error}.py`

- [ ] **Step 1: Confirm base-layout 5-VM rule does not apply**

```bash
grep -n "vm\." swing/web/templates/base.html.j2
```

Expected output:

```
24:    <span class="date">{{ vm.session_date }}</span>
30:  {% if vm.stale_banner %}
33:  {% if vm.price_source_degraded %}
36:  {% if vm.ohlcv_source_degraded %}
```

These are the existing dereferences. The `<a href="/config">Config</a>` is a static `<a>` element with no `vm.` interpolation. ConfigPageVM (Task 4.0) ALREADY includes `session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded` as required. The other 4 VMs (DashboardVM, PipelineVM, JournalVM, WatchlistVM, PageErrorVM) ALREADY include these fields (verified in Phase 3d). No new field needed across the 5 base-layout VMs.

If a future change to `base.html.j2` introduces `{{ vm.is_config_page }}` or similar, all 5 base-layout VMs must gain it. Out of scope for this dispatch.

- [ ] **Step 2: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -5
```

Expected: ALL tests PASS. New count is approximately baseline + 50 (10 + 11 + 17 + 6 + 9 + 7 + 11 = 71 new tests, minus 1 deleted = +70). Some tests may be skipped/parametrized; trust the actual output.

- [ ] **Step 3: Ruff check**

```bash
ruff check swing/ 2>&1 | tail -3
```

Expected: ≤ baseline 91 warnings. New code MUST NOT increase the baseline.

- [ ] **Step 4: Manual smoke (operator browser verification gate)**

Per CLAUDE.md "JS-test-harness gap" (HTMX `<tr>`-leading lesson 2026-04-29), operator-witnessed browser verification is required for the new HTMX flows. Stage the smoke and surface in the return report (operator runs):

```bash
swing web
# Open http://127.0.0.1:8080/config
# Verify:
#   1. All 3 rows render with current/default/source
#   2. Setting chase_factor=0.015 → save → page reloads with "override" badge
#   3. Setting chase_factor=0.05 → save → soft-warn confirm fragment appears
#      (NOT a broken table, NOT a 500)
#   4. Click "Submit anyway" → page reloads with chase_factor=0.05
#   5. Click "Reset chase_factor" → badge returns to "default"; current = 0.01
#   6. Try chase_factor=0.5 → hard-refuse error fragment appears
#   7. CLI: swing config show + set + reset round-trip
```

If a regression appears in step 2-6, plan-author surfaces in return report; if all clear, mark "operator-witnessed verification gate: PASSED" in the return report.

- [ ] **Step 5: Final commit (no code change; just verification)**

No commit required for Task 7 — verification-only. Plan author reports findings.

---

## §G — Self-review

**Spec coverage:** All §3 in-scope tasks implemented:
- Task 0a (risk_floor promotion) — RECONCILED as no-op (already promoted); discriminating-test preserved in Task 1.2 + Task 4.1 happy-path test.
- Task 1 (persistence) — Task 1.1.
- Task 1b (per-request read) — Tasks 1.2 + 2.1.
- Task 2 (precedence) — Tasks 1.2 + 2.0 + 2.1.
- Task 3 (validation) — Task 3.0.
- Task 4 (web routes) — Task 4.1.
- Task 5 (template) — Tasks 4.1 (template files) + 5.0 (render tests).
- Task 6 (CLI) — Task 6.0.
- Task 7 (base-VM check) — Task 7.0.

**Acceptance criteria coverage** (per brief §5):
- 1.1 round-trip: 5 tests in Task 1.1 ✓
- 1.1 atomic: dir-tempfile + write-fail tests in Task 1.1 ✓
- 1.1 missing/malformed: 2 tests in Task 1.1 ✓
- 1.2 per-request: re-read + override tests in Task 1.2 ✓
- 2 precedence × 3 fields × 3 scenarios + source-introspection: Task 1.2 + Task 2.0 = 12 tests ✓
- 3 boundary tests: 13+ in Task 3.0 ✓ (Codex R1 M3 added the integer-valued-float acceptance test; Major 3 fixed)
- 4 GET / POST / soft-warn / force / reset: 9 tests in Task 4.1 + 1 force-hard-bypass + 3 merge-semantics + 1 cancel-link = 14 total (Codex R1 C1 + M4) ✓
- 5 template: 7 tests in Task 5.0 ✓
- 6 CLI: 11 tests in Task 6.0 ✓
- 7 base-VM: verification step in Task 7.0 ✓

**Codex watch-item coverage** (per brief §6):
1. Toml-shadowing audit completeness — §C audit table ✓
2. Atomic write under cross-device-link — Task 1.1 dir-tempfile test ✓
3. Per-request read regression — §C residual-risk note ✓
4. Source-introspection at boundaries — Task 1.2 explicit test ✓
5. Soft-warn ToCToU — Task 4.1 force=true test ✓
6. Reset semantics — Task 1.1 delete-field tests + Task 4.1 reset test ✓
7. CLI + web validation parity — single FIELD_REGISTRY in Task 3.0 ✓
8. Hard-refuse fragment shape — Task 4.1 no-<tr>-root assertion ✓
9. Risk_floor promotion consumer audit — §A.1 + §C audit table ✓
10. Base-layout 5-VM rule scope — §A.7 + Task 7.0 ✓
11. TOML serialization edge cases — `tomli_w` chosen + Task 1.1 round-trip preserves type ✓
12. Validation registry SoT duplication — §E source-of-truth note ✓

**Placeholder scan:** No `TBD`, no `implement later`, no `similar to Task N`. Every code block is concrete. Every test body is actual code.

**Type consistency:** `FIELD_REGISTRY` in Task 3.0 → consumed by `config_overrides.get_field_source` via local-import of `swing.config_validation.get_spec` (the transitional `_DEFAULTS` stub introduced in Task 1.2 is REMOVED in Task 3.0 Step 5; single source of truth post-Task-3.0 is the registry). `apply_overrides` returns `Config`; consumed by `build_config_vm` (Task 4.0) + `config_page` route (Task 4.1) + `cli_config show` (Task 6.0) — all expect `Config`. `ValidationResult.hard_errors: list[ValidationError]` consumed by route in Task 4.1 (`{"errors": result.hard_errors}`) and CLI in Task 6.0 (`for err in result.hard_errors: ...`). Names match.

---

## §H — Done criteria (per brief §7)

- [ ] All §F tasks implemented (1.0, 1.1, 1.2, 2.0, 2.1, 3.0, 4.0, 4.1, 5.0, 6.0, 7.0).
- [ ] All §5 acceptance criteria met (~70 new tests; baseline ~1381 → ~1450).
- [ ] `python -m pytest -m "not slow" -q` exits clean.
- [ ] `ruff check swing/` ≤ 91 warnings.
- [ ] All 4-tier commit-message convention checks pass; subject-only ERE grep returns empty before each task implementation commit.
- [ ] Codex adversarial review reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Plan committed to `docs/superpowers/plans/2026-05-01-configuration-page-plan.md`.
- [ ] Return report explicitly resolves Task 7 case, Task 1b status, risk_floor consumer audit + naming, TOML write library, user-config file path.
