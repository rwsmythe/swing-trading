# Phase 14 Close-Out FOLLOW-ON Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the four gate-found corrections from the Phase 14 close-out polish batch's UNSEEDED operator gate — F-1 (the `swing web` Schwab checker liveness badge stuck at UNKNOWN under healthy tokens), F-2 (market-weather chart "trend: undefined"), F-3 (process-grade-trend rolling lines bridging None gaps), F-4 (hyp-rec/watchlist thumbnail axes-spine boxes).

**Architecture:** ONE executing-plans bundle, **4 serial slices** (F-1 -> F-2 -> F-3 -> F-4). Read-mostly: ZERO swing-domain DB writes, NO schema change (v23 held), L2-LOCK green (F-1 adds ZERO new `schwabdev.Client.*` call sites). Each fix reuses existing helpers (F-1 the seed/sidecar/checker path + the established `apply_overrides` entry-point discipline; F-2 the trend-template SMA logic + the OHLCV fetch helpers; F-3 `_polyline_x`/`_polyline_y`; F-4 the existing thumbnail renderer).

**Tech Stack:** Python 3.14, FastAPI + HTMX + Jinja2, matplotlib/mplfinance (SVG charts), pandas, SQLite, schwabdev 2.5.1, pytest (`-m "not slow"` fast suite ~7005 tests), ruff.

---

## §A Goals / Non-Goals

### Goals
1. **F-1:** Make the Schwab checker liveness sidecar actually appear in normal `swing web` operation under healthy production tokens so the A-7 topbar badge shows **STARTING -> ALIVE** instead of `Schwab?` UNKNOWN. Pin the root cause (Class A construction-None vs Class B silent sidecar-write-failure) via a one-shot startup diagnostic, then deliver BOTH fixes (the diagnostic selects which is operative at the gate).
2. **F-2:** Make the market-weather chart show a DEFINED trend state by computing the regime LIVE from fetched benchmark bars via a shared two-tier `structural_checks`/`structural_stage` helper (instead of reading persisted `candidate_criteria` for a benchmark that is not in the evaluated set), decoupling the compute-window from the display-window — with a MANDATORY byte-identical `evaluate()` regression.
3. **F-3:** Render the process-grade-trend rolling lines with gaps-as-gaps (one `<polyline>` per contiguous non-None run; drop 1-point segments).
4. **F-4:** Hide the matplotlib axes spines on the shared thumbnail renderer (hyp-rec + watchlist).

### Non-Goals (DO NOT widen)
- **NO B-7** (operator failure-mode classification / final touch), **NO** the Phase 14 close-out review (Sec 9.1 Q6), **NO Phase 15** (the schwabdev v2.5.1 -> v3 upgrade stays gotcha `#9`; F-1's diagnosis INFORMS it but does NOT do it).
- **NO schema change** (v23 held; `EXPECTED_SCHEMA_VERSION = 23`). The F-1 liveness stays the existing **ephemeral sidecar file** (NOT a persisted row/table). If any item appears to need a persisted health row/column -> **STOP + escalate** (L2).
- **NO new `schwabdev.Client.*` call site** (L3). Construction stays exclusively in `swing/integrations/schwab/auth.py:construct_authenticated_client`. If the Class-A fix appears to need a new client path -> **STOP + escalate**.
- **NO visible 200-MA line chase** for F-2 (operator ruling 2026-06-02: the 200-MA's value is the regime STATE; keep `ma_windows=(50,200)` per OQ-4).
- **NO** making SPY a first-class evaluated candidate (that is a write-touching pipeline change; the live-compute fix is the read-mostly choice; see §G Slice 2 escalation note + OQ-9).

---

## §B File map (per slice)

### Slice 1 (F-1) — P14.N7 web-checker liveness
- **Modify** `swing/web/app.py`
  - `_construct_web_schwab_client` (`:148-183`): add a redacted reason log to the currently-SILENT `(None, None)` None-path (`:170-171`) so the §3.3 diagnostic can distinguish Class-A sub-paths.
  - `_install_web_marketdata_caches` (`:251-274`): add the **install-anchored STARTING write + readback-verify + WARNING** (Class B detection) and the **one-shot startup INFO diagnostic** (ladder-active? / client-constructed-or-None-path / sidecar path / readback OK).
- **Modify** `swing/cli.py`
  - `web_cmd` (`:3319-3333`): apply `apply_overrides(ctx.obj["config"])` before `run_server(...)` — the **Class-A credential-plumbing fix** (mirrors `pipeline_run_cmd` `:3199` + the Schwab CLI entry `:1877`). NO new `schwabdev.Client.*` site.
- **NO change** to `swing/integrations/schwab/auth.py` (construction unchanged; L3), `swing/integrations/schwab/checker_resilience.py` (reuse `CheckerLiveness`/`record_tick`/`write_liveness_sidecar`/`read_liveness_sidecar`/`evaluate_liveness_state` as-is — see §G Slice 1 note F1-N1), `swing/web/view_models/schwab_checker_badge.py` (A-7 contract preserved; L7).
- **Test** `tests/web/test_checker_liveness_install_path.py` (NEW) — the production-path install+wrap+seed test (fake client, tmp sidecar) + the daemon-tick -> ALIVE test.
- **Test** `tests/web/test_construct_web_schwab_client.py` (NEW) — the parameterized construction-path test (4 credential scenarios) + USERPROFILE/HOME monkeypatch.
- **Test** `tests/web/test_web_cmd_applies_overrides.py` (NEW) — the credential-plumbing-propagation test (CliRunner + mocked `run_server`).

### Slice 2 (F-2) — market-weather trend live-compute
- **Modify** `swing/web/ohlcv_cache.py`: add `MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE = 390` (compute-window constant, distinct from `MIN_CALENDAR_DAYS_FOR_MA200 = 300`); add the pure `slice_recent_calendar_days(bars, *, window_days)` display-slice helper.
- **Modify** `swing/evaluation/criteria/trend_template.py`: add the `StructuralCheck` dataclass + `structural_checks(closes, *, rising_period)` (TT1-TT5) + the `structural_stage(closes, *, rising_period)` wrapper; **refactor `evaluate()` to build its TT1-TT5 `Result` rows from `structural_checks`** (byte-identical; TT6-TT8 unchanged).
- **Modify** `swing/pipeline/runner.py` (`_step_charts` market-weather site `:2890-2931`): replace `current_stage(...)` with `structural_stage(...)` computed from a `MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE` fetch; slice the display frame to `MIN_CALENDAR_DAYS_FOR_MA200`.
- **Modify** `swing/web/routes/dashboard.py` (refresh site `:93-146`): same replacement.
- **Test** `tests/evaluation/test_trend_template_structural.py` (NEW) — byte-identical `evaluate()` regression + `structural_checks`/`structural_stage` unit tests.
- **Test** `tests/web/test_market_weather_live_state.py` (NEW) — the production-path live-compute regression (>=250-bar fixture -> DEFINED; <221-bar fixture -> fallback).

### Slice 3 (F-3) — segmented rolling-line polylines
- **Modify** `swing/web/view_models/metrics/process_grade_trend.py`: `_format_polyline_points` -> `_format_polyline_segments` (returns `tuple[str, ...]`); `RollingSeriesDisplay.svg_polyline_points: str` -> `svg_polyline_segments: tuple[str, ...]`; update `is_drawable`.
- **Modify** `swing/web/templates/metrics/process_grade_trend.html.j2` (`:52-62`): segment `{% for %}` loop.
- **Test** `tests/web/view_models/metrics/test_process_grade_trend_segments.py` (NEW).

### Slice 4 (F-4) — thumbnail spines
- **Modify** `swing/web/charts.py` (`render_watchlist_thumbnail_svg` `:514-552`): hide spines on both sub-axes.
- **Test** `tests/web/test_charts_thumbnail_spines.py` (NEW).

---

## §C Surface integration

- **F-1** integrates at the `swing web` startup chain `web_cmd -> run_server -> create_app -> _install_web_marketdata_caches -> _construct_web_schwab_client / install_resilient_checker / seed update_tokens`. The badge VM (`build_schwab_checker_badge`) is the read consumer (UNCHANGED). The sidecar file at `~/swing-data/schwab-checker-liveness.{env}.json` is the integration medium.
- **F-2** integrates at the two LIVE market-weather render sites (pipeline `_step_charts` + web dashboard refresh). The shared `structural_stage` replaces `current_stage`; `render_market_weather_svg` is the render consumer (UNCHANGED signature). The `evaluate()` refactor is internal to `trend_template.py` and MUST NOT change the 8-criterion pipeline-evaluation path's output.
- **F-3** integrates at the process-grade-trend metrics surface (VM -> template, same-fragment render — no new HTMX endpoint).
- **F-4** integrates at the shared `render_watchlist_thumbnail_svg` (consumed by BOTH the hyp-rec dashboard thumbnails AND the watchlist thumbnails).

---

## §D Out-of-scope

Listed in §A Non-Goals. Additionally: NO change to the `"Schwabdev"` `setLogRecordFactory` redaction (preserve it; L3); NO change to `checker_resilience.py`'s state machine or timing constants; NO change to the A-7 badge VM's UNKNOWN-when-no-sidecar contract; NO change to `render_market_weather_svg`/`render_chart`/`render_position_detail_svg` signatures; NO removal of the existing fail-soft `try/except -> "undefined"` fallbacks; NO change to `MIN_CALENDAR_DAYS_FOR_MA200`'s value or its other consumers.

---

## §E LOCK reverification (the OQ table + L1-L7)

### OQ dispositions honored (brief §1; BINDING — DO NOT re-litigate)
| OQ | LOCKed disposition | Where honored in this plan |
|---|---|---|
| **OQ-1** (F-1 fix shape) | Install-anchored STARTING write + readback-verify + WARNING (Class B); credential plumbing so `_construct_web_schwab_client` succeeds (Class A) — NO new `schwabdev.Client.*` site. §3.3 diagnostic runs FIRST at executing-plans to pin A vs B; the plan designs BOTH + the diagnostic. | §G Slice 1 Tasks F1.1 (diagnostic), F1.2 (Class B write+readback), F1.3 (Class A apply_overrides) |
| **OQ-2** (F-1 daemon) | RESOLVED — daemon heartbeats to ALIVE within ~30s via per-iteration attribute lookup; no separate heartbeat writer. | §G Slice 1 note F1-N2; Task F1.4 daemon-tick test |
| **OQ-3a** (F-2 helper) | Two-tier: `structural_checks` (per-check TT1-TT5) + `structural_stage` (aggregate). `evaluate()` REFACTORS to reuse `structural_checks` — 8-criterion output byte-identical (regression MANDATORY). | §G Slice 2 Tasks F2.1-F2.3 |
| **OQ-4** (MA windows) | KEEP `ma_windows=(50, 200)` for the market-weather render. | §G Slice 2 Task F2.6 (render call unchanged) |
| **OQ-5** (F-3 polylines) | Multiple `<polyline>` (one per contiguous non-None run); DROP 1-point segments. | §G Slice 3 Tasks F3.1-F3.3 |
| **OQ-6** (decomposition) | ONE bundle, 4 slices (F-1 -> F-2 -> F-3 -> F-4). | This plan structure |
| **OQ-7** (Codex chain) | SINGLE chain to convergence. | §J |
| **OQ-8** (F-1 Class A vs B) | Pinned by the §3.3 startup diagnostic at executing-plans — the plan does NOT pre-assume; designs the diagnostic + both fixes. | §G Slice 1 Task F1.1 + the executing-plans gate note |
| **OQ-9** (F-2 SPY criteria) | Confirm at executing-plans (DB check that SPY has no persisted `candidate_criteria`); the live-compute fix is correct regardless. | §G Slice 2 note F2-N1 |

### Inherited LOCKs (spec §2; BINDING)
- **L1** Scope = F-1 + F-2 + F-3 + F-4 ONLY. (See §A Non-Goals.)
- **L2** NO schema change (v23; `EXPECTED_SCHEMA_VERSION = 23` at `swing/data/db.py:51`; assert no `0024_*.sql`). Liveness stays the ephemeral sidecar. **Verified at STEP 0:** schema version 23; last migration `0023_phase14_sb3_chart_surface_rename.sql`.
- **L3 (L2-LOCK)** F-1 ZERO new `schwabdev.Client.*` call sites. **Verified at STEP 0:** `git grep -n "schwabdev.Client\." -- swing/` count = **3** (all comments/docstrings: `auth.py:1666`, `client.py:13`, `trader.py:364` — NOT call sites). The new HEAD count must still equal 3. `construct_authenticated_client` unchanged. `"Schwabdev"` redaction preserved. `tests/integration/test_l2_lock_source_grep.py` (baseline `bf7e071`) stays green.
- **L4** REUSE not re-implement. F-1 reuses the seed/sidecar/checker path + the `apply_overrides` discipline; F-2's two-tier helper reuses the existing SMA logic; F-3 reuses `_polyline_x`/`_polyline_y`; F-4 reuses the existing renderer.
- **L5** Read-mostly. ZERO swing-domain DB writes (the sidecar is an ephemeral file; the chart paths are render-direct; `structural_stage`/the live-compute are SELECT/compute-only).
- **L6** Production-path tests (#15). F-1's automated test exercises the REAL `create_app` -> `_install_web_marketdata_caches` seed path with a fake-client monkeypatch (NOT a hand-seeded sidecar) + a parameterized construction-path test. F-2's test asserts the trend classifies (not NA/undefined) via the REAL live-compute path given >=250 bars. **Do NOT validate F-1 with a hand-seeded sidecar** (the SB5.5 gate's exact mistake; `feedback_seeded_gate_masks_default_state`).
- **L7** ASCII; preserve the close-out A-7 badge fix (it must keep rendering UNKNOWN when no sidecar exists; F-1 makes the sidecar actually appear so the badge shows STARTING/ALIVE in normal use).

---

## §F Discipline hooks (executing-plans implementer MUST follow)

- **STEP 0 anchor re-grep (#2):** before any edit, re-grep every §B anchor (line numbers drift). The line numbers in this plan are from HEAD `a56d5f9`.
- **Worktree-cwd corollary (`feedback_degraded_harness_sequential_tool_calls`):** prefix EVERY git/test command with an explicit `cd <worktree> &&` (or `git -C <worktree>`); re-verify `git branch --show-current` + `git rev-parse --short HEAD` BEFORE every commit. The foreground cwd can silently revert to the primary repo.
- **CLI in the worktree:** use `python -m swing.cli` (NOT bare `swing`).
- **TDD:** write failing test -> see it fail -> minimal implementation -> see it pass -> commit, per task.
- **Commits:** conventional (`fix(web):`, `refactor(...)`, `test(...)`). **NO `Co-Authored-By` footer. NO `--no-verify`.** Keep the final `-m` paragraph PLAIN PROSE; verify `git log -1 --format='%(trailers)'` is `[]` before finishing (`feedback_commit_message_trailer_parse_hazard`).
- **Windows cp1252 (#WindowsASCII):** all user-facing strings (log lines, badge text, chart text) ASCII-only.
- **`USERPROFILE`+`HOME` monkeypatch:** any test touching `write_user_overrides` / `_user_home()` / user-config resolution MUST monkeypatch BOTH (writes leak to the operator's real `~/swing-data/user-config.toml` otherwise).
- **TestClient lifespan:** tests touching `app.state.price_fetch_executor` MUST use `with TestClient(app) as client:`.
- **#15 production-path:** never substitute a stub/hand-seed for the real derivation path (F-1's whole reason for existing).
- **No false green (`feedback_no_false_green_claim`):** re-run the fast suite ON THE MERGED HEAD and READ the actual number before claiming green.

---

## §G The 4 slices (step-checkbox TDD tasks)

### SLICE 1 — F-1: P14.N7 web-checker liveness in normal operation

**Root-cause analysis (orchestrator-verified at STEP 0; the executing-plans §3.3 diagnostic CONFIRMS at the gate):**
The A-7 badge is VISIBLE (operator saw `Schwab?` UNKNOWN), which requires `_is_ladder_active(cfg)` True. That holds on the web cfg WITHOUT `apply_overrides` because tracked `swing.config.toml` carries `marketdata_ladder_enabled = true` and the `IntegrationsSchwab` dataclass defaults `environment = "production"`. But `client_id`/`client_secret` are **user-config-only** (NOT in tracked config, NOT defaults), and **`web_cmd` -> `run_server` -> `create_app` never calls `apply_overrides`** (unlike `pipeline_run_cmd:3199` + the Schwab CLI `:1877`). So the web `cfg.integrations.schwab.client_id/.client_secret` are empty -> `resolve_credentials_env_or_prompt(cfg, env, allow_prompt=False)` finds nothing at the cfg tier; if env vars are also absent in the web process it returns `(None, None)` -> `_construct_web_schwab_client` returns None at `app.py:170-171` (**Class A, sub-path #3**) -> no checker installed -> no sidecar -> badge UNKNOWN.

**This is the LEADING hypothesis, NOT a pre-assumption.** The §3.3 startup diagnostic (Task F1.1) confirms A vs B (and which sub-path) against the operator's actual config/env state at the gate. The plan delivers BOTH the Class-A fix (Task F1.3, `apply_overrides` on the web cfg) AND the Class-B hardening (Task F1.2, install-anchored write + readback-verify), so whichever class the diagnostic pins, the fix is already in place.

**Note F1-N1 (REUSE, L4):** `record_tick("seed")` (`checker_resilience.py:54-65`) already writes a STARTING sidecar unconditionally for the seed origin BEFORE the network `original()` call (the wrapper calls `record_tick` at `:130` before `original()` at `:135`). The install-anchored write (Task F1.2) is therefore NOT a new timing mechanism — its load-bearing addition is the **readback-verify + WARNING** that surfaces a silent write failure (the `_write_sidecar` swallow at `:104-108` logs only at `debug`). Do NOT modify `checker_resilience.py`.

**Note F1-N2 (OQ-2 RESOLVED):** schwabdev 2.5.1's daemon `checker()` calls `self.tokens.update_tokens()` via attribute lookup each iteration, so once `install_resilient_checker` replaces the attribute the daemon's next tick (within ~30s) reaches the wrapper -> `record_tick("daemon")` -> the badge advances STARTING -> ALIVE. No separate heartbeat writer.

---

#### Task F1.1: §3.3 startup diagnostic — log which None-path fired + the sidecar readback

**Files:**
- Modify: `swing/web/app.py:170-171` (the silent `(None, None)` path) + `swing/web/app.py:251-274` (`_install_web_marketdata_caches` one-shot INFO summary)
- Test: `tests/web/test_construct_web_schwab_client.py` (assertions added in Task F1.5; the diagnostic logs are asserted there)

- [ ] **Step 1: Add a redacted reason log to the currently-silent None-path.** In `_construct_web_schwab_client`, replace the bare `return None  # silent` at `:170-171`:

```python
    if client_id is None or client_secret is None:
        log.info(
            "Web schwab_client construction skipped: Schwab credentials "
            "absent at the env and cfg tiers (allow_prompt=False); web "
            "market-data falls back to yfinance. If you use Schwab, set "
            "integrations.schwab.client_id/client_secret in "
            "~/swing-data/user-config.toml (the web app now applies "
            "user-config overrides).",
        )
        return None
```

(ASCII-only; NO secret interpolation. This distinguishes Class-A sub-path #3 from #2 (`SchwabConfigMissingError`, already logged at `:165`) and #4 (construction raise, already logged at `:178`).)

- [ ] **Step 2: Add the one-shot startup INFO diagnostic in `_install_web_marketdata_caches`.** After `client = _construct_web_schwab_client(cfg)` (`:258`) and BEFORE the `if client is None:` return, capture the ladder-active state for the summary; emit the summary AFTER the install-anchored write (Task F1.2 wires the readback value in). Wire as part of Task F1.2's edit (they touch the same block). The summary line shape:

```python
        log.info(
            "P14.N7 checker install summary: ladder_active=%s "
            "client_constructed=%s sidecar_path=%s starting_write_readback=%s",
            ladder_active, client is not None, sidecar_path, readback_ok,
        )
```

(See Task F1.2 for the full assembled block. `ladder_active` is read once via `_is_ladder_active(cfg)` at the top of the function for the diagnostic; `readback_ok` is `None` when no client constructed.)

- [ ] **Step 3: Commit** (this task's edit is the silent-path log + the diagnostic scaffolding; the full assembled `_install_web_marketdata_caches` lands in F1.2 — commit F1.1 and F1.2 together if the diagnostic summary references F1.2's `readback_ok`. Recommended: implement F1.1 Step 1 + F1.2 together, single commit).

```bash
cd <worktree> && git add swing/web/app.py && git commit -m "fix(web): F-1 startup diagnostic + install-anchored checker liveness write"
```

> **Implementer note:** F1.1 and F1.2 edit the same `_install_web_marketdata_caches` block. Implement them as ONE coherent edit + ONE commit (the diagnostic summary line consumes F1.2's `readback_ok`). The two tasks are split here for clarity of intent, not to force two commits.

---

#### Task F1.2: install-anchored STARTING write + readback-verify + WARNING (Class B)

**Files:**
- Modify: `swing/web/app.py:251-274` (`_install_web_marketdata_caches`)
- Test: `tests/web/test_checker_liveness_install_path.py` (Task F1.4)

- [ ] **Step 1: Write the failing production-path test FIRST** (this is Task F1.4 Step 1 — see Task F1.4). The install-anchored write is the behavior that test pins. Implement the test (F1.4 Step 1-2), watch it fail, then return here.

- [ ] **Step 2: Rewrite the `_install_web_marketdata_caches` head block** (`:251-274`) to: read `ladder_active` once for the diagnostic, construct `CheckerLiveness`, install the wrapper, write+readback the STARTING anchor, then emit the diagnostic + seed. Full replacement of the block from the docstring close through the seed line:

```python
def _install_web_marketdata_caches(cfg, price_cache, ohlcv_cache) -> object | None:
    """Install the EXISTING ladder hooks on the web caches (full parity).

    Returns the constructed web Schwab client or None (sandbox / no creds /
    construction failure -> yfinance-only web app, today's behavior). Also
    installs the P14.N7 resilient checker wrap + seeds one refresh, anchoring
    a STARTING liveness sidecar at install (readback-verified) so the A-7
    topbar badge flips to STARTING the instant the checker is wired -- even if
    the seed network call is slow -- and a silent sidecar-write failure
    surfaces as a WARNING (not the debug-only swallow in CheckerLiveness).
    """
    from swing.integrations.schwab.marketdata_ladder import _is_ladder_active
    ladder_active = _is_ladder_active(cfg)

    client = _construct_web_schwab_client(cfg)
    if client is None:
        log.info(
            "P14.N7 checker install summary: ladder_active=%s "
            "client_constructed=False (no checker installed; badge UNKNOWN)",
            ladder_active,
        )
        return None

    # P14.N7: wrap the checker + anchor a STARTING sidecar before serving.
    from swing.integrations.schwab.checker_resilience import (
        CheckerLiveness,
        checker_liveness_sidecar_path,
        install_resilient_checker,
        read_liveness_sidecar,
    )
    env = cfg.integrations.schwab.environment
    sidecar_path = checker_liveness_sidecar_path(env)
    liveness = CheckerLiveness(
        installed_ts=_time.time(),
        sidecar_path=sidecar_path,
    )
    install_resilient_checker(client, liveness=liveness)

    # Install-anchored STARTING write (independent of the seed network timing)
    # + readback-verify. record_tick("seed") writes the sidecar; the readback
    # turns CheckerLiveness's debug-only write swallow into a visible WARNING
    # so a Class-B path/permission failure is no longer invisible.
    liveness.record_tick("seed")
    readback_ok = read_liveness_sidecar(sidecar_path) is not None
    if not readback_ok:
        log.warning(
            "P14.N7 checker liveness sidecar readback FAILED at %s -- the "
            "STARTING write did not persist (check path/permissions under the "
            "web process); the topbar badge will read UNKNOWN.",
            sidecar_path,
        )
    log.info(
        "P14.N7 checker install summary: ladder_active=%s "
        "client_constructed=True sidecar_path=%s starting_write_readback=%s",
        ladder_active, sidecar_path, readback_ok,
    )

    client.tokens.update_tokens()  # seed (origin='seed'; exception-isolated by the wrap)
```

(The remainder of the function — `_WebLadderState`, the quote/window hooks, `install_ladder_hooks` — is UNCHANGED below this point.)

- [ ] **Step 3: Run the F1.4 production-path test to verify it passes.**

Run: `cd <worktree> && python -m pytest tests/web/test_checker_liveness_install_path.py -v`
Expected: PASS (the STARTING sidecar is written + readback succeeds).

- [ ] **Step 4: Commit** (combined with F1.1 per the F1.1 note).

```bash
cd <worktree> && git add swing/web/app.py tests/web/test_checker_liveness_install_path.py && git commit -m "fix(web): F-1 anchor + readback-verify the checker STARTING sidecar with startup diagnostic"
```

---

#### Task F1.3: Class-A credential-plumbing fix — `apply_overrides` on the web cfg

**Files:**
- Modify: `swing/cli.py:3324-3333` (`web_cmd`)
- Test: `tests/web/test_web_cmd_applies_overrides.py` (Task F1.5)

- [ ] **Step 1: Write the failing propagation test FIRST** (Task F1.5 Step 1).

- [ ] **Step 2: Apply `apply_overrides` in `web_cmd`** (mirror `pipeline_run_cmd:3194-3199`). Replace the `web_cmd` body:

```python
def web_cmd(ctx, host, port, reload):
    """Run the dashboard on localhost."""
    # Lazy import: do NOT hoist to module top — keeps base install working
    # without [web] extra (invariant 12).
    from swing.config_overrides import apply_overrides
    from swing.web.cli_cmd import run_server
    # F-1 (Phase 14 close-out follow-on): apply user-config overrides so the
    # web process surfaces Schwab credentials (integrations.schwab.client_id /
    # client_secret) + environment + marketdata_ladder_enabled the same way
    # the CLI + pipeline entry points do (cli.py:1877 / cli.py:3199). Without
    # this, _construct_web_schwab_client cannot resolve creds at the cfg tier
    # -> returns None -> no checker -> the A-7 badge reads UNKNOWN under
    # healthy tokens. ZERO new schwabdev.Client.* sites (config plumbing only).
    cfg = apply_overrides(ctx.obj["config"])
    run_server(
        cfg=cfg,
        cfg_path=ctx.obj.get("config_path"),
        host=host, port=port, reload=reload,
    )
```

- [ ] **Step 3: Run the F1.5 propagation test to verify it passes.**

Run: `cd <worktree> && python -m pytest tests/web/test_web_cmd_applies_overrides.py -v`
Expected: PASS (`run_server` receives a cfg with overrides applied).

- [ ] **Step 4: Commit.**

```bash
cd <worktree> && git add swing/cli.py tests/web/test_web_cmd_applies_overrides.py && git commit -m "fix(web): F-1 apply user-config overrides at the web entry so Schwab creds reach the checker"
```

> **Escalation guard:** if applying `apply_overrides` broadly in `web_cmd` causes unexpected test failures (e.g. a test relied on the web app seeing RAW cfg), narrow the fix to surface ONLY the four schwab cred/env fields — but do NOT introduce a new client-construction path (L3). If the only viable fix needs a new `schwabdev.Client.*` site or a persisted health table -> **STOP + escalate**.

---

#### Task F1.4: production-path install/seed test (fake client, tmp sidecar) + daemon -> ALIVE

**Files:**
- Create: `tests/web/test_checker_liveness_install_path.py`

- [ ] **Step 1: Write the failing test.** It drives the REAL `_install_web_marketdata_caches` with a FAKE client (NOT a hand-seeded sidecar) + a monkeypatched `checker_liveness_sidecar_path` pointing at `tmp_path`.

```python
"""F-1 production-path test: the REAL install+wrap+seed path writes a STARTING
liveness sidecar (NOT a hand-seeded one). Corrects the SB5.5 seeded-gate miss
(feedback_seeded_gate_masks_default_state)."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import swing.web.app as web_app
from swing.integrations.schwab import checker_resilience as cr


class _FakeTokens:
    def __init__(self) -> None:
        self.access_token = "fake-access-token-not-a-secret"
        self.update_tokens_calls = 0

    def update_tokens(self, force_access_token=False, force_refresh_token=False):
        self.update_tokens_calls += 1
        return False  # no rotation needed (healthy token)


class _FakeClient:
    def __init__(self) -> None:
        self.tokens = _FakeTokens()


def test_install_writes_starting_sidecar_via_real_seed_path(tmp_path, monkeypatch):
    sidecar = tmp_path / "schwab-checker-liveness.production.json"
    # Point BOTH the app module's symbol and the checker module's path helper
    # at tmp so the install path writes there (no real ~/swing-data touch).
    monkeypatch.setattr(
        cr, "checker_liveness_sidecar_path", lambda env: sidecar,
    )
    # Force construction to succeed with the fake client (bypass real Schwab).
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", lambda cfg: _FakeClient(),
    )

    class _Cfg:
        class integrations:
            class schwab:
                environment = "production"

    # price_cache / ohlcv_cache are only used further down the function; the
    # STARTING write happens before they are touched, but pass simple stand-ins
    # so the call does not raise before the assertion point.
    client = web_app._install_web_marketdata_caches(
        _Cfg(), _DummyCache(), _DummyCache(),
    )

    assert client is not None
    assert sidecar.exists()  # the REAL seed wiring wrote it -- NOT hand-seeded
    data = cr.read_liveness_sidecar(sidecar)
    assert data is not None
    state, _reason = cr.evaluate_liveness_state(data, now_ts=time.time())
    assert state == "STARTING"


def test_daemon_origin_tick_advances_to_alive(tmp_path, monkeypatch):
    sidecar = tmp_path / "schwab-checker-liveness.production.json"
    monkeypatch.setattr(
        cr, "checker_liveness_sidecar_path", lambda env: sidecar,
    )
    fake = _FakeClient()
    monkeypatch.setattr(
        web_app, "_construct_web_schwab_client", lambda cfg: fake,
    )

    class _Cfg:
        class integrations:
            class schwab:
                environment = "production"

    web_app._install_web_marketdata_caches(_Cfg(), _DummyCache(), _DummyCache())

    # Simulate a daemon tick from a NON-startup thread (origin='daemon').
    result: dict[str, None] = {}

    def _daemon_tick():
        fake.tokens.update_tokens()  # wrapped -> origin='daemon' -> record_tick
        result["done"] = None

    t = threading.Thread(target=_daemon_tick)
    t.start()
    t.join(timeout=5)

    data = cr.read_liveness_sidecar(sidecar)
    assert data is not None
    state, _reason = cr.evaluate_liveness_state(data, now_ts=time.time())
    assert state == "ALIVE"
```

> **Implementer note:** define a minimal `_DummyCache` whose `_fetch_live_price` / attributes used after the STARTING write are no-ops, OR — cleaner — refactor the assertion to call only up to the seed if the downstream hooks raise on the stand-ins. The STARTING write + diagnostic happen BEFORE `_WebLadderState(cfg)` is constructed, so a stand-in that survives to that point is sufficient. If the downstream `install_ladder_hooks` raises on the stand-in, wrap the call in `pytest.raises`-free isolation by giving `_DummyCache` the attributes the hooks read (`install_ladder_quote_hook`/`install_ladder_window_hook` — re-grep at STEP 0) OR monkeypatch those installers to no-ops. Keep the STARTING-write assertion intact either way.

- [ ] **Step 2: Run to verify it fails** (pre-implementation, the readback/anchor isn't there yet, OR the test fails on the stand-in wiring).

Run: `cd <worktree> && python -m pytest tests/web/test_checker_liveness_install_path.py -v`
Expected: FAIL (before F1.2's anchored write, OR until the stand-in wiring is correct).

- [ ] **Step 3: (implementation is Task F1.2 Step 2).**

- [ ] **Step 4: Run to verify it passes** (after F1.2).

Run: `cd <worktree> && python -m pytest tests/web/test_checker_liveness_install_path.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** (folded into F1.2 Step 4).

---

#### Task F1.5: construction-path parameterized test (4 credential scenarios) + propagation test

**Files:**
- Create: `tests/web/test_construct_web_schwab_client.py`
- Create: `tests/web/test_web_cmd_applies_overrides.py`

- [ ] **Step 1: Write the construction-path parameterized test.** Exercises `_construct_web_schwab_client` directly with `_is_ladder_active` True + a monkeypatched `construct_authenticated_client` (NO real network/`schwabdev.Client`). Monkeypatch BOTH `USERPROFILE` AND `HOME` (the test touches credential resolution).

```python
"""F-1 construction-path test: _construct_web_schwab_client resolves creds via
the env > cfg cascade and returns a client (post-fix) or None + a redacted log
on each None-path. NO real schwabdev.Client (construct_authenticated_client is
monkeypatched). Covers the Class-A credential-plumbing fix (Codex R1 Major #2)."""
from __future__ import annotations

import pytest

import swing.web.app as web_app
import swing.integrations.schwab.auth as schwab_auth
from swing.integrations.schwab.errors import SchwabConfigMissingError


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    # Prevent any user-config write/read from leaking to the real ~/swing-data.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    # Default: no env-tier creds (each test sets what it needs).
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)


def _ladder_active_cfg(*, client_id="", client_secret=""):
    class _Cfg:
        class integrations:
            class schwab:
                environment = "production"
                marketdata_ladder_enabled = True
    _Cfg.integrations.schwab.client_id = client_id
    _Cfg.integrations.schwab.client_secret = client_secret
    return _Cfg()


class _Sentinel:
    pass


def test_env_tier_creds_construct_client(monkeypatch):
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "envid")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "envsecret")
    monkeypatch.setattr(
        web_app, "construct_authenticated_client",
        lambda cfg, env, *, client_id, client_secret: _Sentinel(),
    )
    out = web_app._construct_web_schwab_client(_ladder_active_cfg())
    assert isinstance(out, _Sentinel)


def test_cfg_tier_creds_construct_client(monkeypatch):
    # The post-fix path: the web cfg surfaces user-config creds at the cfg tier.
    monkeypatch.setattr(
        web_app, "construct_authenticated_client",
        lambda cfg, env, *, client_id, client_secret: _Sentinel(),
    )
    cfg = _ladder_active_cfg(client_id="cfgid", client_secret="cfgsecret")
    out = web_app._construct_web_schwab_client(cfg)
    assert isinstance(out, _Sentinel)


def test_creds_absent_all_tiers_returns_none_and_logs(monkeypatch, caplog):
    import logging
    caplog.set_level(logging.INFO)
    out = web_app._construct_web_schwab_client(_ladder_active_cfg())
    assert out is None
    assert any(
        "credentials absent at the env and cfg tiers" in r.message
        for r in caplog.records
    )


def test_partial_env_tier_raises_caught_returns_none(monkeypatch, caplog):
    import logging
    caplog.set_level(logging.WARNING)
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "onlyid")  # secret missing -> partial
    out = web_app._construct_web_schwab_client(_ladder_active_cfg())
    assert out is None
    assert any("credentials incomplete" in r.message for r in caplog.records)
```

> **Implementer note:** re-grep at STEP 0 the exact import location of `construct_authenticated_client` + `SchwabConfigMissingError` as referenced inside `app.py` (the monkeypatch target must be the name `app.py` actually calls — `web_app.construct_authenticated_client` iff `app.py` imports it at module scope; if it imports lazily inside the function, patch `swing.integrations.schwab.auth.construct_authenticated_client` instead). The redacted-log assertion strings must match the EXACT messages added in Task F1.1 Step 1 + the existing `:165`/`:178` logs.

- [ ] **Step 2: Run to verify the construction-path test behavior** (some sub-tests pass against current code; `test_cfg_tier_creds_construct_client` validates the cfg-tier resolution path that the apply_overrides fix relies on).

Run: `cd <worktree> && python -m pytest tests/web/test_construct_web_schwab_client.py -v`
Expected: PASS for all four (these test `_construct_web_schwab_client` given a cfg that ALREADY has creds — the apply_overrides fix in F1.3 is what makes the real web cfg HAVE them; this test pins the resolution contract).

- [ ] **Step 3: Write the propagation test** (`test_web_cmd_applies_overrides.py`). CliRunner + mocked `run_server` asserting the cfg reaching `run_server` had `apply_overrides` applied.

```python
"""F-1 propagation test: `swing web` applies user-config overrides before
handing the cfg to run_server (mirrors the pipeline_run_cmd propagation
contract). Without this the web Schwab client cannot resolve creds."""
from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from swing.cli import main


def test_web_cmd_applies_overrides_before_run_server(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    captured = {}

    def _fake_run_server(*, cfg, cfg_path, host, port, reload):
        captured["cfg"] = cfg

    sentinel_cfg = object()

    with patch("swing.web.cli_cmd.run_server", _fake_run_server), \
         patch("swing.config_overrides.apply_overrides", return_value=sentinel_cfg) as ov:
        runner = CliRunner()
        # `--config` points at the tracked config; ctx.obj["config"] is loaded
        # by the group callback, then web_cmd applies overrides.
        result = runner.invoke(main, ["web"])

    assert ov.called, "web_cmd must call apply_overrides"
    assert captured.get("cfg") is sentinel_cfg, (
        "run_server must receive the OVERRIDDEN cfg"
    )
    assert result.exit_code == 0
```

> **Implementer note:** re-grep at STEP 0 the exact group-callback that builds `ctx.obj["config"]` and whether `swing web` with no `--config` loads a default config without error under CliRunner. If the group callback requires a real DB/config, pass `["--config", "swing.config.toml", "web"]` and assert against the loaded cfg. The patch target for `run_server` is where `web_cmd` IMPORTS it (`swing.web.cli_cmd.run_server`); the patch target for `apply_overrides` is where `web_cmd` imports it (`swing.config_overrides.apply_overrides`). Adjust patch paths to the import style in F1.3's edit (lazy import inside `web_cmd` -> patch the source module).

- [ ] **Step 4: Run to verify it fails (pre-F1.3) then passes (post-F1.3).**

Run: `cd <worktree> && python -m pytest tests/web/test_web_cmd_applies_overrides.py -v`
Expected: FAIL before F1.3 (`apply_overrides` not called); PASS after.

- [ ] **Step 5: Commit.**

```bash
cd <worktree> && git add tests/web/test_construct_web_schwab_client.py tests/web/test_web_cmd_applies_overrides.py && git commit -m "test(web): F-1 construction-path + override-propagation coverage for the checker creds fix"
```

- [ ] **Step 6: Run the L2-LOCK source grep + verify ZERO new `schwabdev.Client.*` sites.**

Run: `cd <worktree> && python -m pytest tests/integration/test_l2_lock_source_grep.py -v && git grep -c "schwabdev.Client\." -- swing/`
Expected: PASS; the grep total stays **3**.

---

### SLICE 2 — F-2: market-weather trend live-compute

**Note F2-N1 (OQ-9; escalation guard):** confirm at executing-plans (against the operator's DB or a representative pipeline run) that SPY has NO passing `candidate_criteria` rows — pinning the §4.2 structural finding empirically. The live-compute fix is correct regardless. **If** the operator prefers making SPY a first-class evaluated candidate (un-exclude + evaluate + persist trend criteria), that is a larger, write-touching pipeline change (NOT read-mostly) and an **escalation point** — do NOT pursue it here.

**Note F2-N2 (byte-identical is the gate):** the `evaluate()` refactor MUST preserve every one of the 8 criterion `Result` rows (name / value / rule / result) exactly. The regression in Task F2.2 is the binding gate. If the refactor risks changing ANY criterion row -> **STOP**; the two-tier helper must preserve them exactly.

---

#### Task F2.1: add the compute-window constant + the display-slice helper

**Files:**
- Modify: `swing/web/ohlcv_cache.py:43` (constant) + a new module-level helper
- Test: `tests/web/test_market_weather_live_state.py` (helper unit test added in Task F2.5)

- [ ] **Step 1: Add the compute-window constant** after `MIN_CALENDAR_DAYS_FOR_MA200` (`:43`):

```python
# Phase 14 close-out follow-on (F-2): the market-weather trend classification
# needs the structural Trend-Template checks INCLUDING TT3 (200MA rising over
# rising_ma_period_days=21 bars), i.e. >= 200 + 21 = 221 trading bars. 221 bars
# ~= 221 * 365/252 ~= 320 calendar days; add margin -> 390 (~= 250-260 trading
# bars). This is the COMPUTE window (decoupled from the 300-day DISPLAY/MA200
# window). Monotonic-safe (more bars only; consumers slice).
MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE = 390
```

- [ ] **Step 2: Add the display-slice helper** (mirrors `_fetch_bars_window`'s cutoff logic `:220-261` so the display frame is byte-identical to a `get_or_fetch(window_days=MIN_CALENDAR_DAYS_FOR_MA200)` frame). Place it as a module-level function near the constants:

```python
def slice_recent_calendar_days(bars: "pd.DataFrame", *, window_days: int) -> "pd.DataFrame":
    """Slice a fetched bar frame to the most recent ``window_days`` calendar
    days, mirroring OhlcvCache._fetch_bars_window's cutoff so a wider compute
    fetch can be displayed at the narrower (prior) window without a second
    fetch. ``end`` anchors at last_completed_session(now()) (backward-looking).
    Returns the input unchanged if it is empty.
    """
    from datetime import timedelta
    from swing.evaluation.dates import last_completed_session
    from datetime import datetime as _dt
    if bars is None or bars.empty:
        return bars
    end = last_completed_session(_dt.now())
    cutoff = end - timedelta(days=window_days)
    return bars.loc[(bars.index.date >= cutoff) & (bars.index.date <= end)]
```

> **Implementer note:** re-grep at STEP 0 the exact import for `last_completed_session` already used in `ohlcv_cache.py` (it is imported at module top for `_fetch_bars_window` — reuse that import rather than the inline import shown; the inline import here is illustrative). Match the EXACT inequality (`>=` cutoff, `<= end`) from `_fetch_bars_window:259-261`.

- [ ] **Step 3: Commit.**

```bash
cd <worktree> && git add swing/web/ohlcv_cache.py && git commit -m "feat(web): F-2 add trend-template compute-window constant + display-slice helper"
```

---

#### Task F2.2: extract `StructuralCheck` + `structural_checks` + refactor `evaluate()` (byte-identical)

**Files:**
- Modify: `swing/evaluation/criteria/trend_template.py`
- Test: `tests/evaluation/test_trend_template_structural.py`

- [ ] **Step 1: Write the byte-identical `evaluate()` regression test FIRST.** It captures `evaluate()` output for representative fixtures and asserts the refactored output is identical. Build a real `CandidateContext` fixture; the simplest robust assertion compares the FULL tuple of `Result` rows before vs after — but since the refactor happens in one commit, the test must encode a GOLDEN: assert specific `Result` field values for a deterministic synthetic uptrend fixture (>=221 bars) AND a `<200`-bar fixture.

```python
"""F-2: structural_checks / structural_stage + evaluate() byte-identical
regression. The evaluate() 8-criterion output MUST NOT change after the
TT1-TT5 extraction (OQ-3a; the two-tier helper is reuse, not behavior change)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing.evaluation.criteria.trend_template import (
    CHECK_NAMES,
    StructuralCheck,
    evaluate,
    structural_checks,
    structural_stage,
)


def _uptrend_closes(n: int) -> pd.Series:
    # Deterministic smooth uptrend so all structural checks pass.
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.Series(np.linspace(100.0, 300.0, n), index=idx, name="Close")


def test_structural_checks_uptrend_all_pass():
    closes = _uptrend_closes(260)
    checks = structural_checks(closes, rising_period=21)
    assert len(checks) == 5
    assert all(isinstance(c, StructuralCheck) for c in checks)
    assert [c.name for c in checks] == list(CHECK_NAMES[:5])
    assert all(c.status == "pass" for c in checks)


def test_structural_stage_uptrend_is_stage_2():
    closes = _uptrend_closes(260)
    assert structural_stage(closes, rising_period=21) == "stage_2"


def test_structural_stage_short_history_is_undefined():
    closes = _uptrend_closes(150)  # < 200 -> TT1-TT5 NA -> undefined
    assert structural_stage(closes, rising_period=21) == "undefined"


def test_evaluate_byte_identical_tt1_tt5_for_uptrend():
    # Build a minimal CandidateContext for a known-uptrend ticker and assert
    # the TT1-TT5 Result rows match the pre-refactor formatting EXACTLY.
    closes = _uptrend_closes(260)
    ctx = _make_ctx(closes)  # see implementer note
    results = evaluate(ctx)
    by_name = {r.name: r for r in results}
    # TT1: close > 150MA AND close > 200MA (pass), with the exact value string.
    tt1 = by_name["TT1_above_150_200"]
    assert tt1.result == "pass"
    assert tt1.rule == "close > 150MA AND close > 200MA"
    assert tt1.value.startswith("close=") and "150MA=" in tt1.value and "200MA=" in tt1.value
    # TT3: rising over 21 bars (the rising_period-dependent string).
    tt3 = by_name["TT3_200_rising"]
    assert tt3.result == "pass"
    assert tt3.rule == "200MA rising over 21 bars"


def test_evaluate_under_200_bars_all_na_unchanged():
    closes = _uptrend_closes(150)
    ctx = _make_ctx(closes)
    results = evaluate(ctx)
    assert len(results) == 8
    assert all(r.result == "na" for r in results)
    assert all(r.value == "need 200 bars, have 150" for r in results)
    assert [r.name for r in results] == list(CHECK_NAMES)
```

> **Implementer note (`_make_ctx`):** re-grep at STEP 0 the `CandidateContext` constructor + `ctx.config.trend_template.rising_ma_period_days` + `ctx.batch.*` (RS context for TT8) shapes. Build the smallest valid ctx (real config load or a stub config exposing `trend_template.rising_ma_period_days=21`, `rs.*`, and a `batch` with `returns_12w_by_ticker`/`universe_tickers`/`spy_return_12w`/`universe_version`). TT8 may legitimately be NA in the stub (no universe) — that is fine; the regression asserts TT1-TT5 (the refactored rows) + the `<200` all-NA path. The STRONGEST form of this regression: in a separate throwaway step, capture `evaluate(ctx)` output on the PRE-refactor code into a literal, then assert equality post-refactor. Recommended: snapshot the full `tuple(Result)` for 2-3 fixtures before editing `evaluate()` and assert exact equality after.

- [ ] **Step 2: Run to verify it fails** (`StructuralCheck`/`structural_checks`/`structural_stage` don't exist yet).

Run: `cd <worktree> && python -m pytest tests/evaluation/test_trend_template_structural.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Add `StructuralCheck` + `structural_checks` + `structural_stage` and refactor `evaluate()`.** Insert before `evaluate()` in `trend_template.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class StructuralCheck:
    """One TT1-TT5 structural check result (status + display strings).

    status: 'pass' | 'fail' | 'na'. For 'na', `value` carries the reason and
    `rule` is "" (mirrors Result.na_).
    """
    name: str
    status: str
    value: str
    rule: str


def structural_checks(closes, *, rising_period: int) -> tuple[StructuralCheck, ...]:
    """Compute the TT1-TT5 structural Trend-Template checks from `closes`.

    ONE source of truth for the TT1-TT5 math, shared by evaluate() (which
    converts these to Result rows -- byte-identical) and structural_stage()
    (which maps them to a regime label). TT6-TT8 stay in evaluate() (they need
    52w-window / batch-RS context not available at the live render sites).
    """
    if len(closes) < 200:
        reason = f"need 200 bars, have {len(closes)}"
        return tuple(
            StructuralCheck(name=n, status="na", value=reason, rule="")
            for n in CHECK_NAMES[:5]
        )

    last_close = float(closes.iloc[-1])
    sma50 = sma(closes, 50)
    sma150 = sma(closes, 150)
    sma200 = sma(closes, 200)
    s50 = float(sma50.iloc[-1])
    s150 = float(sma150.iloc[-1])
    s200 = float(sma200.iloc[-1])

    checks: list[StructuralCheck] = []

    # TT1: close > 150MA and close > 200MA
    v = f"close={last_close:.2f} 150MA={s150:.2f} 200MA={s200:.2f}"
    ok = (last_close > s150) and (last_close > s200)
    checks.append(StructuralCheck(
        name=CHECK_NAMES[0], status="pass" if ok else "fail",
        value=v, rule="close > 150MA AND close > 200MA",
    ))

    # TT2: 150MA > 200MA
    v = f"150MA={s150:.2f} 200MA={s200:.2f}"
    ok = s150 > s200
    checks.append(StructuralCheck(
        name=CHECK_NAMES[1], status="pass" if ok else "fail",
        value=v, rule="150MA > 200MA",
    ))

    # TT3: 200MA trending up over `rising_period` bars
    if len(sma200.dropna()) < rising_period + 1:
        checks.append(StructuralCheck(
            name=CHECK_NAMES[2], status="na",
            value="not enough 200MA history", rule="",
        ))
    else:
        past = float(sma200.iloc[-(rising_period + 1)])
        v = f"200MA now={s200:.2f} vs {rising_period}bars ago={past:.2f}"
        ok = s200 > past
        checks.append(StructuralCheck(
            name=CHECK_NAMES[2], status="pass" if ok else "fail",
            value=v, rule=f"200MA rising over {rising_period} bars",
        ))

    # TT4: 50MA > 150MA and 50MA > 200MA
    v = f"50MA={s50:.2f} 150MA={s150:.2f} 200MA={s200:.2f}"
    ok = (s50 > s150) and (s50 > s200)
    checks.append(StructuralCheck(
        name=CHECK_NAMES[3], status="pass" if ok else "fail",
        value=v, rule="50MA > 150MA AND 50MA > 200MA",
    ))

    # TT5: close > 50MA
    v = f"close={last_close:.2f} 50MA={s50:.2f}"
    ok = last_close > s50
    checks.append(StructuralCheck(
        name=CHECK_NAMES[4], status="pass" if ok else "fail",
        value=v, rule="close > 50MA",
    ))

    return tuple(checks)


def structural_stage(closes, *, rising_period: int) -> str:
    """Map the TT1-TT5 structural checks to a regime label.

    All five pass -> 'stage_2'; any fail/NA (incl. insufficient bars) ->
    'undefined'. TT6/TT7 (52w high/low) + TT8 (RS rank) are stock-selection
    criteria, not meaningful for the index benchmark vs itself, so the live
    market-weather regime uses the structural TT1-TT5 set (OQ-3a).
    """
    checks = structural_checks(closes, rising_period=rising_period)
    return "stage_2" if all(c.status == "pass" for c in checks) else "undefined"


def _check_to_result(c: StructuralCheck) -> Result:
    if c.status == "pass":
        return Result.pass_(c.value, c.rule, name=c.name, layer=LAYER)
    if c.status == "fail":
        return Result.fail_(c.value, c.rule, name=c.name, layer=LAYER)
    return Result.na_(c.value, name=c.name, layer=LAYER)
```

Then **refactor `evaluate()`** to build TT1-TT5 from `structural_checks` while leaving TT6-TT8 + the `<200` semantics byte-identical:

```python
def evaluate(ctx: CandidateContext) -> tuple[Result, ...]:
    closes = ctx.ohlcv["Close"]
    period = ctx.config.trend_template.rising_ma_period_days

    # TT1-TT5 via the shared structural helper (ONE source of truth).
    results: list[Result] = [
        _check_to_result(c) for c in structural_checks(closes, rising_period=period)
    ]

    if len(closes) < 200:
        # TT6-TT8 also NA with the legacy message (byte-identical pre-refactor).
        results += [
            Result.na_(f"need 200 bars, have {len(closes)}", name=n, layer=LAYER)
            for n in CHECK_NAMES[5:]
        ]
        return tuple(results)

    last_close = float(closes.iloc[-1])

    # TT6/TT7: 52-week high/low (use last 252 bars = 1 trading year)
    lookback_52w = min(252, len(closes))
    window = closes.iloc[-lookback_52w:]
    low_52w = float(window.min())
    high_52w = float(window.max())
    # ... (TT6, TT7, TT8 bodies UNCHANGED from the current implementation) ...
    return tuple(results)
```

> **Implementer note:** copy the TT6/TT7/TT8 bodies VERBATIM from the current `evaluate()` (`:90-157`) into the refactored function below the `last_close` line — do NOT paraphrase. The ONLY changes are: (a) TT1-TT5 now come from `structural_checks`; (b) `period`/`last_close`/`closes` are computed once at the top. Verify the `<200` early-return produces the IDENTICAL 8-NA tuple (TT1-TT5 from `structural_checks` NA + TT6-TT8 appended) — same order (`CHECK_NAMES`), same message.

- [ ] **Step 4: Run the regression to verify it passes.**

Run: `cd <worktree> && python -m pytest tests/evaluation/test_trend_template_structural.py -v`
Expected: PASS.

- [ ] **Step 5: Run the FULL existing trend-template + evaluation suite** to confirm byte-identical (no existing test breaks).

Run: `cd <worktree> && python -m pytest tests/evaluation/ -q`
Expected: PASS (all existing evaluation tests green — the strongest byte-identical proof).

- [ ] **Step 6: Commit.**

```bash
cd <worktree> && git add swing/evaluation/criteria/trend_template.py tests/evaluation/test_trend_template_structural.py && git commit -m "refactor(evaluation): F-2 extract structural_checks/structural_stage; evaluate() byte-identical"
```

---

#### Task F2.3: replace `current_stage` with `structural_stage` at the pipeline `_step_charts` market-weather site

**Files:**
- Modify: `swing/pipeline/runner.py:2890-2931`
- Test: `tests/web/test_market_weather_live_state.py` (Task F2.5; the pipeline-site test)

- [ ] **Step 1: Write the failing pipeline-site test** (Task F2.5 Step 1 includes both sites).

- [ ] **Step 2: Rewrite the market-weather block** (`:2890-2931`). Fetch the compute window, compute `structural_stage`, slice the display frame, render:

```python
    # market_weather surface — cfg.rs.benchmark_ticker. Compute the trend state
    # LIVE from a wide (>= MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE) benchmark fetch
    # via structural_stage (F-2: current_stage read PERSISTED criteria for SPY,
    # which is not in the evaluated set -> always 'undefined'). Display the
    # narrower MIN_CALENDAR_DAYS_FOR_MA200 window (legibility unchanged).
    benchmark_ticker = cfg.rs.benchmark_ticker.upper()
    try:
        compute_bars = ohlcv_cache.get_or_fetch(
            ticker=benchmark_ticker,
            window_days=MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
        )
    except Exception as exc:  # noqa: BLE001 - per-ticker isolation
        log.warning(
            "market_weather benchmark fetch failed for %s: %s",
            benchmark_ticker, exc,
        )
        compute_bars = None
    if compute_bars is not None and not compute_bars.empty:
        try:
            closes = compute_bars["Close"]
            if getattr(closes, "ndim", 1) == 2:
                closes = closes.iloc[:, 0]
            weather_state = structural_stage(
                closes, rising_period=cfg.trend_template.rising_ma_period_days,
            )
        except Exception as exc:  # noqa: BLE001 - fail-soft, never abort step
            log.warning(
                "market_weather structural_stage failed for %s: %s",
                benchmark_ticker, exc,
            )
            weather_state = "undefined"
        display_bars = slice_recent_calendar_days(
            compute_bars, window_days=MIN_CALENDAR_DAYS_FOR_MA200,
        )
        try:
            svg_bytes = render_market_weather_svg(
                bars=display_bars, trend_template_state=weather_state,
            )
        except Exception as exc:  # noqa: BLE001 - per-ticker isolation
            log.warning(
                "render_market_weather_svg failed for %s: %s",
                benchmark_ticker, exc,
            )
        else:
            _refresh_one(
                ticker=benchmark_ticker, surface="market_weather",
                pipeline_run_id=lease.run_id, pattern_class=None,
                bytes_=svg_bytes,
            )
```

> **Implementer note:** re-grep at STEP 0 the exact accessor for `rising_ma_period_days` on the pipeline `cfg` (`cfg.trend_template.rising_ma_period_days` vs `cfg.config.trend_template...` — match how `trend_template.evaluate` reads it via `ctx.config.trend_template`; the pipeline cfg is the top-level `Config`, so `cfg.trend_template.rising_ma_period_days`). Add the imports at the top of `runner.py`: `structural_stage` from `swing.evaluation.criteria.trend_template` + `MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE` + `slice_recent_calendar_days` from `swing.web.ohlcv_cache` (verify `MIN_CALENDAR_DAYS_FOR_MA200` is already imported — it is, used at `:2701`/`:2772`). The `current_stage` import (`:65`) may now be unused IF no other runner site uses it — re-grep `current_stage` usage in `runner.py` (there ARE other references at `:1372`/`:1555`/`:1630` comments + detector calls; the IMPORT stays if any live call remains; remove only if grep shows zero live calls). Keep the `_ws_conn` connect/close removed for THIS block (no DB read needed now).

- [ ] **Step 3: Run the pipeline-site test to verify it passes** (Task F2.5).

- [ ] **Step 4: Commit.**

```bash
cd <worktree> && git add swing/pipeline/runner.py && git commit -m "fix(pipeline): F-2 compute market-weather trend live via structural_stage"
```

---

#### Task F2.4: replace `current_stage` with `structural_stage` at the web dashboard refresh site

**Files:**
- Modify: `swing/web/routes/dashboard.py:93-146`
- Test: `tests/web/test_market_weather_live_state.py` (Task F2.5; the web-site test)

- [ ] **Step 1: Rewrite the fetch + state derivation** (`:93-146`). Fetch the compute window, compute `structural_stage`, slice the display frame:

```python
        benchmark = cfg.rs.benchmark_ticker
        try:
            compute_bars = ohlcv_cache.get_or_fetch(
                ticker=benchmark,
                window_days=MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
            )
        except ValueError as exc:
            log.warning(
                "weather-chart refresh: get_or_fetch returned empty for %s: %s",
                benchmark, exc,
            )
            compute_bars = None
        if compute_bars is None or compute_bars.empty:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"no OHLCV bars available for benchmark {benchmark!r}; "
                    "run the pipeline first"
                ),
            )
        # F-2: compute the trend state LIVE from the wide compute window via
        # structural_stage (current_stage read persisted criteria for a
        # benchmark not in the evaluated set -> always 'undefined'). Fail-soft.
        try:
            closes = compute_bars["Close"]
            if getattr(closes, "ndim", 1) == 2:
                closes = closes.iloc[:, 0]
            weather_state = structural_stage(
                closes, rising_period=cfg.trend_template.rising_ma_period_days,
            )
        except Exception as exc:  # noqa: BLE001 - fail-soft, never crash refresh
            log.warning(
                "weather refresh structural_stage failed for %s: %s",
                benchmark, exc,
            )
            weather_state = "undefined"
        bars = slice_recent_calendar_days(
            compute_bars, window_days=MIN_CALENDAR_DAYS_FOR_MA200,
        )
        svg_bytes = render_market_weather_svg(
            bars=bars, trend_template_state=weather_state,
        )
```

> **Implementer note:** preserve the surrounding `ChartRender` construction (`:147-...`) UNCHANGED (it consumes `svg_bytes`). Preserve the existing `# NOTE: Do NOT catch broad Exception here` rationale comment (`:111-119`) — the broad-except ban on the FETCH stays; the new structural_stage try/except is fail-soft for the STATE compute only (mirrors the prior `current_stage` fail-soft). Add imports: `structural_stage` from `swing.evaluation.criteria.trend_template`; `MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE` + `slice_recent_calendar_days` from `swing.web.ohlcv_cache` (verify `MIN_CALENDAR_DAYS_FOR_MA200` already imported — it is, used at `:96`). Remove the now-unused `current_stage` import from this module IF no other dashboard.py site uses it (re-grep; `last_completed_session` is still used for `data_asof_date`). Re-grep `cfg.trend_template.rising_ma_period_days` accessor for the WEB cfg (`app.state.cfg` is a `Config`; `cfg.trend_template.rising_ma_period_days`).

- [ ] **Step 2: Run the web-site test to verify it passes** (Task F2.5).

- [ ] **Step 3: Commit.**

```bash
cd <worktree> && git add swing/web/routes/dashboard.py && git commit -m "fix(web): F-2 compute market-weather trend live via structural_stage on refresh"
```

---

#### Task F2.5: production-path live-compute regression (both sites)

**Files:**
- Create: `tests/web/test_market_weather_live_state.py`

- [ ] **Step 1: Write the failing tests.** Assert the LIVE compute path classifies a >=250-bar uptrend as DEFINED (`stage_2`) and a <221-bar fixture as `undefined`, via the REAL fetch/compute wiring (a `get_or_fetch` returning a synthetic uptrend frame, NOT a stubbed `current_stage`).

```python
"""F-2 production-path regression: the market-weather trend state is computed
LIVE from fetched bars (structural_stage), so a healthy uptrend benchmark
classifies as DEFINED (stage_2) -- NOT 'undefined'. Exercises the real
fetch -> closes -> structural_stage wiring, not a stubbed current_stage."""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing.web.ohlcv_cache import (
    MIN_CALENDAR_DAYS_FOR_MA200,
    MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE,
    slice_recent_calendar_days,
)
from swing.evaluation.criteria.trend_template import structural_stage


def _uptrend_frame(n: int) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=n, freq="B")
    close = np.linspace(100.0, 300.0, n)
    return pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99,
         "Close": close, "Volume": np.full(n, 1_000_000.0)},
        index=idx,
    )


def test_uptrend_classifies_stage_2():
    bars = _uptrend_frame(260)
    state = structural_stage(bars["Close"], rising_period=21)
    assert state == "stage_2"  # DEFINED -- the F-2 fix


def test_short_history_classifies_undefined():
    bars = _uptrend_frame(150)
    state = structural_stage(bars["Close"], rising_period=21)
    assert state == "undefined"


def test_compute_window_wider_than_display_window():
    assert MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE > MIN_CALENDAR_DAYS_FOR_MA200


def test_display_slice_narrows_compute_frame():
    bars = _uptrend_frame(300)  # ~300 business days spans > 300 calendar days
    display = slice_recent_calendar_days(bars, window_days=MIN_CALENDAR_DAYS_FOR_MA200)
    assert len(display) <= len(bars)
    assert not display.empty
    # The display tail anchors at the same last bar as the compute frame.
    assert display.index[-1] == bars.index[-1]
```

> **Implementer note:** for a STRONGER production-path test of the dashboard refresh ROUTE (exercising `get_or_fetch` -> `structural_stage` -> `render_market_weather_svg`), add a TestClient test that monkeypatches `OhlcvCache.get_or_fetch` (or the ladder fetcher) to return `_uptrend_frame(260)` and asserts the rendered market-weather SVG contains `trend: stage_2` (NOT `trend: undefined`). Use `with TestClient(app) as client:` (lifespan). Re-grep at STEP 0 the exact refresh route path + how `ohlcv_cache` is reached from the route (via `request.app.state.ohlcv_cache`). This is the #15 production-path assertion the gate's S5 mirrors.

- [ ] **Step 2: Run to verify (pre-implementation fails on import; post-F2.1/F2.2 passes).**

Run: `cd <worktree> && python -m pytest tests/web/test_market_weather_live_state.py -v`
Expected: PASS after F2.1 + F2.2 land (this task's commit follows them).

- [ ] **Step 3: Commit.**

```bash
cd <worktree> && git add tests/web/test_market_weather_live_state.py && git commit -m "test(web): F-2 production-path market-weather live-state regression"
```

---

### SLICE 3 — F-3: segmented rolling-line polylines

#### Task F3.1: refactor `_format_polyline_points` -> `_format_polyline_segments`

**Files:**
- Modify: `swing/web/view_models/metrics/process_grade_trend.py:262-301`
- Test: `tests/web/view_models/metrics/test_process_grade_trend_segments.py`

- [ ] **Step 1: Write the failing segment unit test.**

```python
"""F-3: the rolling-line polyline is segmented at None gaps (one segment per
contiguous non-None run; 1-point segments dropped) so gaps render as gaps."""
from __future__ import annotations

from swing.web.view_models.metrics.process_grade_trend import (
    RollingLinePoint,
    _format_polyline_segments,
)


def _pts(values):
    return tuple(
        RollingLinePoint(ordinal=i, value=v) for i, v in enumerate(values)
    )


_GEOM = dict(
    total_points=6, y_min=0.0, y_max=4.0,
    layout_width=400, layout_height=120,
    margin_left=10, margin_right=10, margin_top=5, margin_bottom=5,
)


def test_contiguous_series_one_segment():
    segs = _format_polyline_segments(_pts([1.0, 2.0, 3.0, 2.0]), **_GEOM)
    assert len(segs) == 1
    assert segs[0].count(",") == 4  # 4 points


def test_gap_splits_into_two_segments():
    segs = _format_polyline_segments(_pts([1.0, 2.0, None, 3.0, 4.0]), **_GEOM)
    assert len(segs) == 2


def test_one_point_segments_dropped():
    # A lone defined point between gaps is not a line -> dropped.
    segs = _format_polyline_segments(_pts([1.0, None, 9.0, None, 2.0, 3.0]), **_GEOM)
    assert len(segs) == 1  # only the trailing 2-point run survives


def test_all_none_is_empty():
    segs = _format_polyline_segments(_pts([None, None]), **_GEOM)
    assert segs == ()
```

- [ ] **Step 2: Run to verify it fails.**

Run: `cd <worktree> && python -m pytest tests/web/view_models/metrics/test_process_grade_trend_segments.py -v`
Expected: FAIL (`_format_polyline_segments` not defined).

- [ ] **Step 3: Replace `_format_polyline_points`** (`:262-301`) with `_format_polyline_segments`:

```python
def _format_polyline_segments(
    line_points: tuple[RollingLinePoint, ...],
    *,
    total_points: int,
    y_min: float,
    y_max: float,
    layout_width: int,
    layout_height: int,
    margin_left: int,
    margin_right: int,
    margin_top: int,
    margin_bottom: int,
) -> tuple[str, ...]:
    """SVG polyline ``points`` strings, ONE per contiguous non-None run.

    A single ``<polyline>`` cannot contain a break, so a None gap in the
    rolling-mean series (operational <3 floor) must split into multiple
    polyline elements -- otherwise the line bridges the gap with a straight
    diagonal. Runs of a single defined point are dropped (one point is not a
    line). Returns () when no >=2-point run exists.
    """
    segments: list[str] = []
    current: list[str] = []

    def _flush() -> None:
        if len(current) >= 2:
            segments.append(" ".join(current))
        current.clear()

    for p in line_points:
        if p.value is None:
            _flush()
            continue
        x = _polyline_x(
            p.ordinal,
            total_points=total_points,
            layout_width=layout_width,
            margin_left=margin_left,
            margin_right=margin_right,
        )
        y = _polyline_y(
            p.value,
            y_min=y_min,
            y_max=y_max,
            layout_height=layout_height,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
        )
        current.append(f"{x:.2f},{y:.2f}")
    _flush()
    return tuple(segments)
```

(Reuses `_polyline_x`/`_polyline_y` UNCHANGED — L4.)

- [ ] **Step 4: Run to verify it passes.**

Run: `cd <worktree> && python -m pytest tests/web/view_models/metrics/test_process_grade_trend_segments.py -v`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
cd <worktree> && git add swing/web/view_models/metrics/process_grade_trend.py tests/web/view_models/metrics/test_process_grade_trend_segments.py && git commit -m "feat(web): F-3 segment rolling-line polylines at None gaps"
```

---

#### Task F3.2: update `RollingSeriesDisplay` field + `is_drawable`

**Files:**
- Modify: `swing/web/view_models/metrics/process_grade_trend.py:69-95` (dataclass) + `:340-393` (builder)

- [ ] **Step 1: Rename the dataclass field** (`:91-95`): replace `svg_polyline_points: str` with:

```python
    # SVG polyline points strings, one per contiguous non-None run; () when
    # not drawable (a single <polyline> cannot bridge a None gap).
    svg_polyline_segments: tuple[str, ...]
    # Whether at least one >=2-point rolling-line segment is renderable.
    is_drawable: bool
```

- [ ] **Step 2: Update the suppressed branch** (`:340-354`): replace `svg_polyline_points="",` with `svg_polyline_segments=(),`.

- [ ] **Step 3: Update the builder** (`:356-393`): replace the `_format_polyline_points(...)` call + `is_drawable` + the constructor:

```python
    segments = _format_polyline_segments(
        series.line_points,
        total_points=total_points,
        y_min=y_min,
        y_max=y_max,
        layout_width=layout_width,
        layout_height=layout_height,
        margin_left=margin_left,
        margin_right=margin_right,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
    )
    # Drawability gate: the §5.4 line band must have fired AND at least one
    # >=2-point segment must survive (else the template would emit an empty
    # <polyline> set).
    is_drawable = (
        drawability == "rolling line drawable"
        and bool(segments)
    )
    return RollingSeriesDisplay(
        metric_name=metric_name,
        underlying_class=series.underlying_class,
        is_suppressed=False,
        suppressed_placeholder=None,
        point_value_text=point_text,
        ci_lower_text=lo_text,
        ci_upper_text=hi_text,
        drawability_text=drawability,
        window_not_full_warning_text=window_text,
        confidence_floor_warning_text=floor_text,
        svg_polyline_segments=segments,
        is_drawable=is_drawable,
    )
```

- [ ] **Step 4: Write a builder-level test** asserting the VM carries segments + `is_drawable` (append to the Task F3.1 test file):

```python
def test_builder_emits_segments_and_drawable_flag():
    # Re-grep the builder name + RollingMetricSeries shape at STEP 0; this test
    # constructs a minimal series with a None gap and asserts >=2 segments when
    # the line band fired, or () + is_drawable False otherwise.
    ...  # implementer fills in per the real RollingMetricSeries constructor
```

> **Implementer note:** re-grep at STEP 0 the `RollingMetricSeries` + `series.badges`/`series.drawability_text`/`series.rendered_value`/`series.line_points`/`series.suppressed` shapes to build a real minimal series. If constructing a full `RollingMetricSeries` is heavy, assert at the builder boundary via an existing fixture used by the current process-grade-trend VM tests (re-grep `tests/.../process_grade_trend` for an existing series fixture and reuse it). Keep this test meaningful (it must exercise the real builder, not a stub).

- [ ] **Step 5: Run + commit.**

```bash
cd <worktree> && python -m pytest tests/web/view_models/metrics/test_process_grade_trend_segments.py -v
cd <worktree> && git add swing/web/view_models/metrics/process_grade_trend.py tests/web/view_models/metrics/test_process_grade_trend_segments.py && git commit -m "feat(web): F-3 RollingSeriesDisplay carries polyline segments"
```

---

#### Task F3.3: update the template to loop over segments

**Files:**
- Modify: `swing/web/templates/metrics/process_grade_trend.html.j2:52-62`
- Test: a render-string test (append to the Task F3.1 file or a route-level test)

- [ ] **Step 1: Write the failing render test.** Assert that a series with a mid-series None renders >=2 `<polyline>` elements and a fully-contiguous series renders exactly 1.

```python
def test_template_renders_multiple_polylines_for_gapped_series():
    # Render the process-grade-trend fragment/page with a gapped series via the
    # real route; assert the rendered HTML has >=2 <polyline ... metric-...>
    # for the gapped metric and exactly 1 for a contiguous metric.
    ...  # implementer: use TestClient against the process-grade-trend surface
```

> **Implementer note:** re-grep at STEP 0 the process-grade-trend route + how the VM is seeded for a route test (the metrics surfaces commonly accept a monkeypatched VM builder or a seeded DB). Reuse the existing process-grade-trend route test harness if present. The assertion counts `<polyline` occurrences carrying `class="process-grade-rolling-line metric-..."`.

- [ ] **Step 2: Update the template** (`:52-62`):

```jinja
    {# Per-metric rolling polylines — drawn only when the §5.4 line band fires
       AND at least one >=2-point segment survives. One <polyline> per
       contiguous non-None run so None gaps render as gaps (F-3). #}
    {% for series in vm.rolling_series %}
      {% if series.is_drawable %}
        {% for seg in series.svg_polyline_segments %}
        <polyline points="{{ seg }}"
                  fill="none"
                  stroke-width="1.5"
                  data-series="{{ series.metric_name }}"
                  class="process-grade-rolling-line metric-{{ series.metric_name }}" />
        {% endfor %}
      {% endif %}
    {% endfor %}
```

- [ ] **Step 3: Run to verify it passes.**

Run: `cd <worktree> && python -m pytest tests/web/view_models/metrics/test_process_grade_trend_segments.py -v`
Expected: PASS.

- [ ] **Step 4: Grep for any other reader of `svg_polyline_points`** to confirm none remain.

Run: `cd <worktree> && git grep -n "svg_polyline_points" -- swing/ tests/`
Expected: ZERO matches (all references migrated to `svg_polyline_segments`).

- [ ] **Step 5: Commit.**

```bash
cd <worktree> && git add swing/web/templates/metrics/process_grade_trend.html.j2 tests/web/view_models/metrics/test_process_grade_trend_segments.py && git commit -m "feat(web): F-3 render one polyline per contiguous rolling-line segment"
```

---

### SLICE 4 — F-4: thumbnail axes-spine borders

#### Task F4.1: hide the spines on both thumbnail sub-axes

**Files:**
- Modify: `swing/web/charts.py:514-552` (`render_watchlist_thumbnail_svg`)
- Test: `tests/web/test_charts_thumbnail_spines.py`

- [ ] **Step 1: Write the failing test.**

```python
"""F-4: the shared thumbnail renderer hides matplotlib axes spines (no black
box around the hyp-rec / watchlist thumbnails). Asserts the spines are set
invisible (rendered-SVG path absence is brittle; assert via the Axes state by
rendering and checking no full-border rect, OR via a render that succeeds + a
spine-visibility unit check)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing.web.charts import render_watchlist_thumbnail_svg


def _frame(n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = np.linspace(10.0, 20.0, n)
    return pd.DataFrame(
        {"Open": close, "High": close * 1.01, "Low": close * 0.99,
         "Close": close, "Volume": np.full(n, 1000.0)},
        index=idx,
    )


def test_thumbnail_renders_without_spines(monkeypatch):
    # Capture spine visibility by intercepting the spine.set_visible calls.
    import matplotlib.axes
    visibilities: list[bool] = []
    orig = matplotlib.spines.Spine.set_visible

    def _track(self, b):
        visibilities.append(b)
        return orig(self, b)

    monkeypatch.setattr(matplotlib.spines.Spine, "set_visible", _track)
    out = render_watchlist_thumbnail_svg(
        ticker="AAPL", bars=_frame(), ma_lines=[10, 20],
    )
    assert isinstance(out, bytes) and len(out) > 0
    # Both sub-axes (price + vol) have 4 spines each = 8 set_visible(False).
    assert visibilities.count(False) >= 8
```

> **Implementer note:** if intercepting `Spine.set_visible` proves flaky (matplotlib internals), the simpler robust assertion is to render the SVG and assert it still produces valid bytes (smoke) PLUS a focused unit assertion that the renderer code path calls `set_visible(False)` — re-grep at STEP 0 a comparable spine-hiding test elsewhere in `tests/web/` and mirror its assertion style. The SVG-string approach (assert no full-perimeter `<rect>`/path) is brittle across matplotlib versions; prefer the call-interception or a direct figure-inspection approach if the renderer can be refactored to return the fig in a test seam (do NOT add such a seam if it widens scope — the interception test is sufficient).

- [ ] **Step 2: Run to verify it fails.**

Run: `cd <worktree> && python -m pytest tests/web/test_charts_thumbnail_spines.py -v`
Expected: FAIL (spines not hidden -> count < 8).

- [ ] **Step 3: Hide the spines.** In `render_watchlist_thumbnail_svg`, after the `ax_price.set_xticks([])`/`set_yticks([])` (and the `ax_vol` tick clears at `:550-551`), add spine-hiding for BOTH axes. Insert after `:541` (`ax_price.set_yticks([])`) and after `:551` (`ax_vol.set_yticks([])`) respectively, OR consolidate after both axes are configured:

```python
    for _spine in ax_price.spines.values():
        _spine.set_visible(False)
    for _spine in ax_vol.spines.values():
        _spine.set_visible(False)
```

- [ ] **Step 4: Run to verify it passes.**

Run: `cd <worktree> && python -m pytest tests/web/test_charts_thumbnail_spines.py -v`
Expected: PASS.

- [ ] **Step 5: Run the existing watchlist/thumbnail render tests** to confirm no regression on the shared renderer.

Run: `cd <worktree> && python -m pytest tests/web/ -k "thumbnail or watchlist" -q`
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
cd <worktree> && git add swing/web/charts.py tests/web/test_charts_thumbnail_spines.py && git commit -m "fix(web): F-4 hide axes spines on the shared thumbnail renderer"
```

---

## §H Test surface (production-path summary)

| Slice | Test file | What it pins (#15 production-path) |
|---|---|---|
| F-1 | `test_checker_liveness_install_path.py` | REAL `_install_web_marketdata_caches` install+wrap+seed writes a STARTING sidecar (fake client, tmp path — NOT hand-seeded); daemon-origin tick -> ALIVE |
| F-1 | `test_construct_web_schwab_client.py` | the 4 credential-resolution paths (env / cfg-tier / absent / partial-env) + the redacted None-path logs |
| F-1 | `test_web_cmd_applies_overrides.py` | `swing web` applies `apply_overrides` so creds reach the cfg tier (the Class-A fix) |
| F-1 | `test_l2_lock_source_grep.py` (existing) | ZERO new `schwabdev.Client.*` sites (count stays 3) |
| F-2 | `test_trend_template_structural.py` | `evaluate()` byte-identical after the TT1-TT5 extraction; `structural_checks`/`structural_stage` |
| F-2 | `test_market_weather_live_state.py` | live compute classifies >=250-bar uptrend as `stage_2` (DEFINED), <221 as `undefined`; display slice narrows the compute frame |
| F-3 | `test_process_grade_trend_segments.py` | segment split at None gaps; 1-point drop; >=2 `<polyline>` for gapped, 1 for contiguous |
| F-4 | `test_charts_thumbnail_spines.py` | spines hidden on both sub-axes; render still valid |

Plus: the FULL fast suite (`pytest -m "not slow"`) + `ruff check swing/` green on the MERGED head.

---

## §I The operator gate (executing-plans; S1-S7; UNSEEDED real-token for F-1)

- **S1** Fast suite (`python -m pytest -m "not slow" -q`) + `ruff check swing/` green on the MERGED head. READ the actual count (baseline 7005; `feedback_no_false_green_claim`).
- **S2** Schema v23 unchanged (`EXPECTED_SCHEMA_VERSION = 23`; no `0024_*.sql`); DB backup gate (no migration); no new domain writes.
- **S3** `tests/integration/test_l2_lock_source_grep.py` green (F-1 zero new `schwabdev.Client.` sites; `git grep -c "schwabdev.Client\." -- swing/` == 3).
- **S4 (F-1, BINDING, UNSEEDED real-token):** the operator runs `swing web` with HEALTHY production tokens + `marketdata_ladder_enabled=True`, **after deleting any existing `~/swing-data/schwab-checker-liveness.production.json`**. The §3.3 startup INFO diagnostic logs which class fired (`ladder_active` / `client_constructed` / `starting_write_readback`). Assert in a real browser: within a few seconds the sidecar FILE appears + the topbar badge shows **STARTING** -> (within ~30-60s) **ALIVE**, NOT `Schwab?` UNKNOWN. **This is the SB5.5 gate's exact miss, corrected (`feedback_seeded_gate_masks_default_state`).**
- **S5 (F-2, browser):** the market-weather trend is DEFINED (not "undefined") in a real browser refresh + pipeline-rendered chart.
- **S6 (F-3/F-4, browser):** the process-grade-trend rolling lines render gaps-as-gaps (no diagonal bridges); the hyp-rec AND watchlist thumbnails have NO spine borders (shared renderer).
- **S7** commit trailers `git log -1 --format='%(trailers)'` == `[]`; ZERO `Co-Authored-By`.

**If a `swing web` server is launched for S4-S6:** orchestrator-run the BRANCH server (`python -m swing.cli web --port 8081`); kill by PID (`Get-NetTCPConnection -LocalPort 8081` -> `Stop-Process -Force`; verify free) per `feedback_taskstop_does_not_kill_detached_server`. After merge re-run the suite on the MERGED head + READ it; reinstall `swing`.

**Executing-plans diagnostic ordering (OQ-8):** the §3.3 startup diagnostic runs FIRST (the operator/implementer reads ONE startup line). If it reports `client_constructed=False`, the Class-A fix (apply_overrides, already shipped in F1.3) is operative — re-run after confirming creds are in user-config OR env. If it reports `client_constructed=True starting_write_readback=False`, the Class-B path/permission cause is operative (the WARNING names the path). The plan ships BOTH fixes; the diagnostic confirms which resolved the gate.

---

## §J Codex placement

SINGLE adversarial Codex chain at the END of writing-plans (this document), run to CONVERGENCE (`NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended — `feedback_codex_round_limit_suspended`). Transport: copowers v2.0.3 WSL fallback (`command -v codex` -> `/home/<wsluser>/.local/node22/bin/codex`; MCP codex tools DEAD in the VS Code extension). Pre-generate the diff on Windows; tell Codex NOT to run git. PERSIST each round's prompt AND response to `.copowers-findings.md` (incl. the final `### Verdict`). **Watch items:** NO schema (all 4 slices); L2 green (F-1 zero new `schwabdev.Client.*` sites); the F-1 diagnostic-then-fix covers BOTH Class A + Class B without pre-assuming; the F-1 test exercises the REAL install/seed path (NOT a hand-seeded sidecar) + the UNSEEDED gate; F-2's `evaluate()` byte-identical regression + the >=250-bar live-compute via the real fetch + the compute-vs-display slice; F-3's multiple `<polyline>` + drop-1-point; F-4 spines + the watchlist re-check; the A-7 badge fix preserved; the redaction intact; ASCII; trailer-parse. **If a finding needs a schema change or a new `schwabdev.Client.*` site -> STOP + escalate.**

The executing-plans phase runs its OWN single Codex chain to convergence (OQ-7).

---

## §K Schema (NO change)

**NO change. v23 held.** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`) unchanged; no `0024_*.sql`. F-1's liveness stays the existing ephemeral sidecar file (NOT a persisted row/table). F-2 is SELECT/compute + render only. F-3/F-4 are render-geometry only. If any item appears to need a persisted row/column -> STOP + escalate (L2; no v24).

---

## §L Fixtures

- **F-1 fake-client monkeypatch:** `_FakeClient` with `tokens.access_token` (non-empty str) + `tokens.update_tokens(force_access_token=False, force_refresh_token=False)` callable returning `False` (no rotation). Monkeypatch `_construct_web_schwab_client` -> `_FakeClient()` to drive the REAL install/seed path; monkeypatch `checker_liveness_sidecar_path` -> a `tmp_path` file. NEVER hand-write the sidecar JSON.
- **F-1 construction-path:** monkeypatch `construct_authenticated_client` -> a sentinel (no real `schwabdev.Client`); a cfg stub with `_is_ladder_active` True (`environment='production'`, `marketdata_ladder_enabled=True`) + `integrations.schwab.client_id/client_secret` set/unset per scenario; monkeypatch BOTH `USERPROFILE` AND `HOME`.
- **F-2 >=250-bar fixture:** a deterministic synthetic uptrend (`np.linspace(100,300,260)` over business days) so all TT1-TT5 pass -> `stage_2`; a 150-bar variant for the `undefined` fallback.
- **F-3:** `RollingLinePoint` tuples with mid-series `None`s; reuse the real `RollingMetricSeries` fixture from the existing process-grade-trend VM tests for the builder/route assertions.
- **F-4:** a small OHLCV frame (>= a few bars) through `render_watchlist_thumbnail_svg`; intercept `Spine.set_visible`.

---

## §M Forward-binding lessons

1. **Entry-point `apply_overrides` discipline is NOT universal — the web entry was missing it.** `pipeline_run_cmd` and the Schwab CLI apply overrides; `web_cmd` did not, silently denying the whole web app its user-config (creds, environment, ladder flag). When adding a NEW CLI entry that builds/serves a long-lived app, mirror the `apply_overrides(ctx.obj["config"])` step — and add a propagation test. (The root cause was invisible because tracked `swing.config.toml` + dataclass defaults made `_is_ladder_active` True regardless, so the badge rendered but the client never constructed.)
2. **A debug-only swallow in a best-effort IO path hides a whole failure class.** `CheckerLiveness._write_sidecar` logged write failures at `debug`, so Class-B silent-write-failure was indistinguishable from Class-A construction-None. The fix surfaces it via an install-anchored readback + WARNING. Best-effort IO that drives a USER-VISIBLE signal needs a one-shot readback-verify at install, not just a swallow.
3. **A read-from-persisted-state wrapper silently returns the default when the entity is not in the persisted set.** `current_stage('SPY')` returned `undefined` not because the math failed but because SPY is never an evaluated candidate. When a render site needs a derived state for an entity OUTSIDE the producing pipeline's universe, compute it LIVE from inputs — do not read the producer's persisted output.
4. **SVG `<polyline>` cannot bridge a break — segment at gaps.** Any None-gapped series rendered as a single polyline draws a false diagonal across the gap. One element per contiguous run; drop 1-point runs.
5. **Byte-identical refactor = capture a golden BEFORE editing.** The strongest byte-identical regression snapshots the pre-refactor output for representative fixtures and asserts exact equality after. Field-by-field assertions are a weaker backstop.

---

## §N Self-review

**1. Spec coverage:**
- §3 (F-1 Class A/B + diagnostic + UNSEEDED gate) -> Slice 1 Tasks F1.1-F1.5 + §I S4. ✓
- §4 (F-2 two-tier helper + byte-identical evaluate + compute-vs-display + window constant) -> Slice 2 Tasks F2.1-F2.5. ✓
- §5 (F-3 segmented polylines, drop-1-point, is_drawable) -> Slice 3 Tasks F3.1-F3.3. ✓
- §6 (F-4 spines) -> Slice 4 Task F4.1. ✓
- §7 module touch list -> §B file map. ✓
- §8 schema NO change -> §K. ✓
- §9 L2-LOCK analysis -> §E L3 + Task F1.5 Step 6. ✓
- §10 decomposition (1 bundle, 4 slices, F-1 first) -> plan structure. ✓
- §11 test+gate (S1-S7) -> §H + §I. ✓
- §13 OQ table -> §E. ✓

**2. Placeholder scan:** the F3.2 Step 4 / F3.3 Step 1 / F4.1 builder-and-route assertions carry explicit `...` with implementer notes pointing at the real fixtures to re-grep — these are intentional "re-grep the real fixture shape at STEP 0" hooks, NOT lazy placeholders (the surrounding test structure + assertions are concrete). The executing-plans implementer fills the fixture construction from the real `RollingMetricSeries`/route harness. All CODE steps that introduce new functions show full code.

**3. Type consistency:** `StructuralCheck(name, status, value, rule)` used consistently in F2.2; `structural_checks(closes, *, rising_period)` + `structural_stage(closes, *, rising_period)` signatures match across F2.2/F2.3/F2.4/F2.5; `svg_polyline_segments: tuple[str, ...]` consistent across F3.1/F3.2/F3.3; `_format_polyline_segments` name consistent; `slice_recent_calendar_days(bars, *, window_days)` consistent across F2.1/F2.3/F2.4/F2.5.

---

## §O Close-out position note

This FOLLOW-ON bundle is the FIRST item of the Phase 14 close-out tail: **follow-on bundle (this) -> B-7 (operator failure-mode classification, final touch) -> Phase 14 close-out review (Sec 9.1 Q6) -> "Phase 14 CLOSED" at v23.** F-1's diagnosis feeds the Phase 15 schwabdev v3 upgrade (gotcha `#9`), which will obviate P14.N7's checker guard entirely. NO scope creep into B-7 / the close-out review / Phase 15.
