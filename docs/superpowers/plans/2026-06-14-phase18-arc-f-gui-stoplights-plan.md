# Phase 18 Arc 18-F — GUI health stoplights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface at-a-glance system health on EVERY page. Add TWO top-row stoplights to `base.html.j2` — **tool-health (18-E)** + **research-measurement (18-D)** — each a small colored indicator (green/yellow/red/grey = worst-of that monitor's checks) linking to a read-only drill-down that lists which checks flipped. Tool-health computes at render via 18-E's shipped `compute_tool_health(...)`; research reads 18-D's JSON status artifact and shows GREY until 18-D is deployed (18-D is NOT built yet). Ships a new `swing/monitoring/stoplights.py` (the `Stoplight` dataclass + `health_stoplights(conn, cfg)` aggregator + the two independent providers + the shared artifact-path constant + the research-artifact reader), the base-wide injection of `health_stoplights` into every template render, the topbar render in `base.html.j2`, and two read-only routes (`GET /health/tool`, `GET /health/research`) with their VM builders + templates.

**Architecture:** The load-bearing decision (brief §2.2) is HOW `health_stoplights` reaches the shared `base.html.j2` without the every-base-VM-or-500 gotcha. **DECISION: a Starlette context processor** registered on `Jinja2Templates`, NOT a per-VM field. Grounded on disk (the live versions, not the brief's assumption): FastAPI 0.135.2 / Starlette 1.0.0 / Jinja2 3.1.6. `Jinja2Templates.__init__` (Starlette 1.0.0, via `inspect.getsource`) is `(self, directory=None, *, context_processors: list[Callable[[Request], dict]] | None = None, env: jinja2.Environment | None = None)` — `context_processors` is a STANDALONE keyword-only param, NOT mutually exclusive with `env` (the only mutual-exclusion is `assert bool(directory) ^ bool(env)`). `TemplateResponse` runs `for cp in self.context_processors: context.update(cp(request))` on EVERY render. So `Jinja2Templates(env=env, context_processors=[_health_stoplights_context_processor])` is cleanly viable with the project's existing `env=` construction at `swing/web/app.py:_build_templates` (lines 86-100). The processor receives `request` (carrying `request.app.state.cfg` → `db_path`), calls `health_stoplights(conn, cfg)` DEFENSIVELY, and returns `{"health_stoplights": (...)}`. `base.html.j2` reads `health_stoplights` from the render context (NOT from `vm`), so there is NO per-VM field to add and NO 500 risk from a forgotten VM. The processor is registered INSIDE `_build_templates` so EVERY `Jinja2Templates` instance — `app.state.templates` AND the fresh `_build_templates(...)` the error handler builds at `app.py:112` — carries it (the error page renders through `health_stoplights` too, which is exactly why the aggregator MUST never raise).

The two providers are independent functions inside `swing/monitoring/stoplights.py`: `_tool_stoplight(conn, cfg)` calls 18-E's `compute_tool_health(conn, cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir)` and maps `ToolHealthStatus.overall` ∈ {green,yellow,red} → the stoplight color; `_research_stoplight()` reads the shared artifact path `exports/research/health/latest.json`, parses the §3 monitor-status envelope, maps its `overall` → the color, and degrades to GREY on absent/malformed/old. Each provider is wrapped so ANY exception degrades that ONE stoplight to grey (the other still computes). The drill-down routes (`/health/tool`, `/health/research`) mirror the `journal_trade_detail_page` read-only pattern (`swing/web/routes/journal.py:149-171`): `cfg = apply_overrides(request.app.state.cfg)`, connect, build a VM carrying `_base_banner_fields(conn, cfg)` (so the existing base-banner fields render) + the monitor's `checks`, `templates.TemplateResponse(request, "...", {"vm": vm})`.

**Tech Stack:** Python 3.14. `swing/monitoring/stoplights.py` imports only stdlib (`dataclasses`, `json`, `pathlib`, `logging`, `sqlite3` for the type hint) at module top; the 18-E aggregator + repos are LAZY-imported inside the providers (matches 18-E's lazy-import discipline + keeps the module-import graph light). REUSES 18-E's `compute_tool_health` (NO reimplementation). The web wiring uses the existing `Jinja2Templates`/`apply_overrides`/`connect`/`_base_banner_fields` machinery. pytest (`monkeypatch`, `tmp_path`, `TestClient` with `with TestClient(app) as client:` for lifespan). **NO new schema, NO migration, NO new dependency, NO `swing/data`/`swing/trades`/`swing/pipeline` touch.** The only `swing/` edits are the new `swing/monitoring/stoplights.py`, `swing/web/app.py` (the context processor registration), `swing/web/templates/base.html.j2` (the topbar block + CSS), `swing/web/static/app.css` (the stoplight color classes), the two new route handlers + VM builders + 2 templates.

**Codex review tier for THIS plan:** `review-fast` (writing-plans). The EXECUTING dispatch (separate) runs `review-strong` + the `codex-auto-review` A/B + the BINDING operator browser gate (brief §6) — noted in the Verification section as executing-gate items, NOT run here.

---

## Background — grounding (verified on disk at branch base `main` HEAD `fc342511`)

### The base-injection mechanism (brief §2.2 — THE load-bearing decision)
- **`_build_templates(directory)` at `swing/web/app.py:86-100`** constructs `jinja2.Environment(loader=..., autoescape=True)` then `return Jinja2Templates(env=env)`. The `env=` form is in use; `directory=` is NOT.
- **`app.state.templates = _build_templates(app.state.templates_dir)`** at `swing/web/app.py:437` (the long-lived per-request templates).
- **The error handler `_handle_any` at `swing/web/app.py:112`** builds a FRESH `tpls = _build_templates(app.state.templates_dir)` for the 500 page; `_handle_http_exc` / `_handle_validation_error` use `request.app.state.templates`. ALL paths flow through `_build_templates` OR `app.state.templates` — so registering the context processor INSIDE `_build_templates` covers EVERY render including the error pages.
- **Live versions (this box, `importlib.metadata`):** fastapi 0.135.2, starlette 1.0.0, jinja2 3.1.6.
- **`Jinja2Templates.__init__` (Starlette 1.0.0, `inspect.getsource`):**
  ```
  def __init__(self, directory=None, *, context_processors=None, env=None):
      assert bool(directory) ^ bool(env), "either 'directory' or 'env' arguments must be passed"
      self.context_processors = context_processors or []
      ...
      elif env is not None:
          self.env = env
      self._setup_env_defaults(self.env)
  ```
  `context_processors` is independent of the `directory ^ env` assertion → `Jinja2Templates(env=env, context_processors=[...])` is VALID with `env=`. **This is the viability evidence that decided the mechanism.**
- **`TemplateResponse` (Starlette 1.0.0, `inspect.getsource`)** runs `context.setdefault("request", request); for cp in self.context_processors: context.update(cp(request))` before rendering — i.e. each processor is called with `request` and its dict is merged into the render context on EVERY `TemplateResponse`. The processor reads `request.app.state.cfg` for the db path.
- **CONCLUSION:** the RECOMMENDED context-processor injection is cleanly viable. The FALLBACK per-VM path (and the ~15-VM hand-duplication the brief §2.2 + charter D15 enumerate) is NOT taken. The `swing/web/view_models/metrics/shared.py:30` `BaseLayoutVM` + `swing/web/view_models/journal.py:235` `_base_banner_fields` are UNCHANGED by 18-F (they keep populating the EXISTING base-banner fields; `health_stoplights` is purely context-injected).

### The base template topbar (where the stoplights render)
- **`swing/web/templates/base.html.j2:68-81`** — `<nav class="topbar">` with `<span class="date">{{ vm.session_date }}</span>`, the nav links, and `<button id="theme-toggle">`. The stoplights render as a `<div class="stoplights">` adjacent to the date. The base template reads `vm.session_date`, `vm.stale_banner`, `vm.price_source_degraded`, `vm.ohlcv_source_degraded`, `vm.unresolved_material_discrepancies_count`, `vm.recent_multi_leg_auto_correction_count`, `vm.banner_resolve_link` — so EVERY page that renders base STILL needs a base-VM carrying those (the existing contract; unchanged). `health_stoplights` is the ONLY new symbol and it comes from the context, not `vm`.

### 18-E's `compute_tool_health` (the tool-health provider's REUSE target — grounded)
- **`swing/monitoring/tool_health.py:508-531`:** `def compute_tool_health(conn: sqlite3.Connection, *, cfg=None, prices_cache_dir=None, now: datetime | None = None) -> ToolHealthStatus`.
- **`ToolHealthStatus`** (`tool_health.py:101-134`): `frozen`; `.overall: str` ∈ {green,yellow,red} (enforced); `.checks: tuple[ToolHealthCheck]` (coerced to tuple in `__post_init__`); `.generated_ts: str`; `.to_dict()` → `{"monitor", "generated_ts", "overall", "checks":[{key,status,summary,detail}]}` — the §3 envelope.
- **`ToolHealthCheck`** (`tool_health.py:69-94`): `frozen`; `.key`, `.status` ∈ {green,yellow,red}, `.summary`, `.detail: str | None`; `.to_dict()`. **`status` REJECTS grey at construction** (`tool_health.py:76-82`) — grey is render-only (LOCK #3).
- The 18-F tool provider calls `compute_tool_health(conn, cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir)` (the brief §2.1 signature), maps `.overall` → the stoplight color (green→green, yellow→yellow, red→red), and uses `.checks` for the drill-down. The compute is "cheap DB-backed reads" (the cash-badge precedent, brief §2.1).
- **`cfg.paths.prices_cache_dir`** is a `Path` on the Config (used at `swing/web/app.py:323`, `swing/data/ohlcv_archive.py`). When `cfg` is None (should not happen in the web app — `app.state.cfg` is always set) the provider degrades to grey defensively.

### The research-artifact contract (brief §2.3 — CHARC-owned; 18-D conforms)
- **Shared path: `exports/research/health/latest.json`.** Anchored to the repo root the `weekly_glance.py:22-23` way: `EXPORTS = REPO_ROOT / "exports" / "research"` where `REPO_ROOT = Path(__file__).resolve().parent.parent`. For `swing/monitoring/stoplights.py` the repo root is `Path(__file__).resolve().parents[2]` (`swing/monitoring/stoplights.py` → `swing/monitoring` → `swing` → repo root). The path constant is defined ONCE in `swing/monitoring/` (LOCK #4) so BOTH 18-F (reader) and 18-D (writer) reference it.
- **Envelope shape** (the §3 monitor-status contract, identical to `ToolHealthStatus.to_dict()`): `{"monitor": str, "generated_ts": str, "overall": "green"|"yellow"|"red", "checks": [{"key","status","summary","detail"}]}`.
- **Artifact-IDENTITY validation (Codex R1 MAJOR #1 — never false-green on a wrong object).** The `exports/research/` dir holds OTHER JSON artifacts (the shadow-expectancy exports). A wrong JSON object that happens to carry a valid `overall` MUST NOT light the research stoplight. So the shared module defines `RESEARCH_MONITOR_ID = "research_measurement"` (the value 18-D stamps in its envelope's `monitor` field) and the validator checks `env.get("monitor") == RESEARCH_MONITOR_ID` BEFORE trusting `overall` — a missing/mismatched `monitor` → grey + WARNING (treated like malformed). 18-D conforms to this `monitor` id (cross-lane contract, RD FYI).
- **Artifact-STALENESS gate (Codex R2 MAJOR — close the same-monitor stale-but-green false-green vector).** A stale `latest.json` from the RIGHT monitor could still show green long after the research monitor stopped writing — still a false-green under LOCK #3. 18-F uses the envelope's OWN `generated_ts` (already part of the §3 contract — `ToolHealthStatus.generated_ts`, `tool_health.py:105`) for a CONSERVATIVE staleness gate: if `generated_ts` is absent/unparseable OR older than `RESEARCH_ARTIFACT_MAX_AGE_DAYS` (a generous V1 default = 7 calendar days; weekly-cadence-tolerant, the `weekly_glance` T1=4d precedent loosened because the research monitor's cadence is 18-D's to define) → grey + WARNING. This uses the envelope's existing field (NOT a new schema/contract) and does NOT invent a 18-D-owned cadence; 18-D may later tighten the threshold via the shared constant. The tool-health stoplight needs NO staleness gate (it computes live at render — its `overall` is always current). The age comparison reuses the host-tz-independent pattern (parse `generated_ts`; compare to `datetime.now()` with the same naive-local convention 18-E uses; on ANY parse error → grey, never a crash).
- **Degradation:** absent file → grey ("research monitor not deployed"); unreadable/malformed JSON / wrong-or-missing `monitor` id / missing-or-invalid `overall` / stale-or-unparseable `generated_ts` → grey + a logged WARNING (never a 500, never a false green).

### The read-only drill-down route precedent (brief §2.4)
- **`journal_trade_detail_page` at `swing/web/routes/journal.py:149-171`:** `@router.get(..., response_class=HTMLResponse)`; `cfg = apply_overrides(request.app.state.cfg)`; `templates = request.app.state.templates`; `conn = connect(cfg.paths.db_path)`; `with conn: vm = build_...(conn, cfg, ...)`; `finally: conn.close()`; `return templates.TemplateResponse(request, "...", {"vm": vm})`. Read-only (SELECTs only).
- **`_base_banner_fields(conn, cfg)` at `swing/web/view_models/journal.py:235-268`** returns the dict of base-banner fields every base-layout page VM needs (`session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded`, `unresolved_material_discrepancies_count`, `recent_multi_leg_auto_correction_count`, `banner_resolve_link`). The two drill-down VMs spread `**_base_banner_fields(conn, cfg)` (the `TradeDrilldownVM` precedent at `journal.py:624-632`) so they render through base without an `UndefinedError`. `health_stoplights` arrives via the context processor (the SAME mechanism as every other page) — the drill-down does NOT special-case it.
- **`app.include_router(...)` block at `swing/web/app.py:567-616`** registers every route group; the new `health` router is added here (mirror the import + `include_router` pattern).

### Disciplines preserved (CLAUDE.md §Gotchas / dispatch recipe §5)
- **The every-base-VM-or-500 gotcha is SIDESTEPPED, not paid:** the context processor injects `health_stoplights` into the render context, so there is NO new `vm.foo` field on any VM. (The existing base-banner-field hand-duplication debt — charter D15 — is UNCHANGED and NOT touched by 18-F.)
- **The defensive-never-raise lock (LOCK #2):** the aggregator + each provider catch ALL exceptions and degrade to grey, because the processor runs on EVERY render INCLUDING the error page — a raising processor would 500 every page (strictly worse than the gotcha it replaces).
- **`grey` is render-only (LOCK #3):** the `Stoplight.color` enum admits grey, but the monitors' own envelopes never emit it (18-E rejects grey at construction; 18-D conforms to the §3 envelope which is {green,yellow,red}). Grey is produced only by the 18-F providers (no-data / not-deployed / error).
- **ASCII discipline (cp1252):** every `Stoplight.label`/`summary`/`detail` Python string and any template text is ASCII (no em-dash, arrows, glyphs). The colored indicator is CSS, not a unicode glyph.
- **Starlette TemplateResponse signature:** `TemplateResponse(request, "name", {...}, status_code=...)` (request-first, the project convention).
- **TestClient lifespan:** tests building `create_app(...)` and exercising routes use `with TestClient(app) as client:` (the lifespan installs `app.state.price_fetch_executor`; CLAUDE.md convention).
- **HTMX/nested-table family:** the drill-down pages are full-page navigations (NOT HTMX fragments) and the topbar stoplights are plain `<a>` links — no `<tr>`-at-fragment-root / `hx-target` inheritance surface is introduced. (TestClient cannot catch a base-render 500; the operator browser gate is the BINDING net — executing-cycle, brief §6.)

---

## File Map

- **Create:** `swing/monitoring/stoplights.py` — the `Stoplight` frozen dataclass; the shared `RESEARCH_HEALTH_ARTIFACT_PATH` constant + a `research_health_artifact_path()` accessor; the shared `RESEARCH_MONITOR_ID` + `RESEARCH_ARTIFACT_MAX_AGE_DAYS` constants; `read_validated_research_envelope()` (the ONE identity+staleness-validating reader shared by the stoplight + the drill-down VM); `_tool_stoplight(conn, cfg)` + `_research_stoplight()` providers (each defensively wrapped); `health_stoplights(conn, cfg) -> tuple[Stoplight, ...]` aggregator (never raises). Module-top imports stdlib only (`datetime` added for the staleness parse); the 18-E aggregator + repos lazy-imported inside the providers.
- **Create:** `swing/web/view_models/health.py` — a small frozen `ResearchCheck` dataclass (`key/status/summary/detail`, all dot-accessible) + `ToolHealthPageVM` + `ResearchHealthPageVM` (frozen; carry the base-banner fields + the monitor's `checks` tuple + an `available: bool` for the research-not-deployed page) + `build_tool_health_vm(conn, cfg)` + `build_research_health_vm(conn, cfg)`.
- **Create:** `swing/web/routes/health.py` — the `health` `APIRouter` with `GET /health/tool` + `GET /health/research` (read-only; the `journal_trade_detail_page` pattern).
- **Create:** `swing/web/templates/health_tool.html.j2` — extends `base.html.j2`; lists the tool-health checks (key / status / summary / detail).
- **Create:** `swing/web/templates/health_research.html.j2` — extends `base.html.j2`; lists the research checks, OR the "research monitor (18-D) is not yet deployed" message when absent.
- **Modify:** `swing/web/app.py` — add `_health_stoplights_context_processor(request)` (defensive; returns `{"health_stoplights": (...)}`) + register it in `_build_templates` via `Jinja2Templates(env=env, context_processors=[...])`; import + `include_router` the new `health` router.
- **Modify:** `swing/web/templates/base.html.j2` — the topbar `<div class="stoplights">` (small colored `<a>` indicators linking to the drill-downs) adjacent to `<span class="date">` (lines 68-81).
- **Modify:** `swing/web/static/app.css` — `.stoplights` + `.stoplight` + `.stoplight-green/-yellow/-red/-grey` color classes (light + dark theme).
- **Create:** `tests/monitoring/test_stoplights.py` — the `Stoplight` dataclass + the aggregator + the two providers (defensive-grey-on-raise, color mapping, grey-on-absent/malformed artifact) + the shared-path constant.
- **Create:** `tests/web/test_routes/test_health_stoplights.py` — the every-base-route regression (every base route renders 200 with stoplights present), the per-provider-raise → grey-not-500 web test, the two drill-down route tests, the grey-until-18-D test.

**Executing worktree (for the executing-plans cycle that follows this plan): `<repo>/.worktrees/phase18-arc-f-exec`.**

---

## Task 1: The `Stoplight` dataclass + the shared research-artifact path constant

**Files:**
- Create: `swing/monitoring/stoplights.py` (dataclass + path constant only)
- Create: `tests/monitoring/test_stoplights.py`

**Step 1 (RED):** write `tests/monitoring/test_stoplights.py::test_stoplight_dataclass_fields_and_color_enum`:
- `Stoplight(id="tool", label="Tool health", color="green", drilldown_path="/health/tool")` constructs; `.id`, `.label`, `.color`, `.drilldown_path` round-trip.
- A bad color raises `ValueError`: `Stoplight(id="tool", label="x", color="blue", drilldown_path="/health/tool")` → `pytest.raises(ValueError)`. (Both-ways: under a no-validation impl this would NOT raise — the test distinguishes by asserting the raise.)
- `color="grey"` is ACCEPTED (grey is a valid render-only Stoplight color — LOCK #3): `Stoplight(..., color="grey", ...)` constructs.
- An empty `drilldown_path` raises `ValueError` (the topbar `<a href>` must be a real path).
- `test_research_health_artifact_path_constant`: `research_health_artifact_path()` returns a `Path` ending with `exports/research/health/latest.json`; `RESEARCH_HEALTH_ARTIFACT_PATH` is that same path. Assert `path.parts[-3:] == ("research", "health", "latest.json")` and `path.parts[-4] == "exports"`.
- `test_research_monitor_id_constant`: `RESEARCH_MONITOR_ID == "research_measurement"` (the cross-lane contract value 18-D stamps; pinned so the reader + writer agree).

Run: `( cd .worktrees/phase18-arc-f-plan && python -m pytest tests/monitoring/test_stoplights.py -q )` — SEE it fail (module/symbol missing).

**Step 2 (GREEN):** implement in `swing/monitoring/stoplights.py`:
- Module-top imports: `from __future__ import annotations`, `import json`, `import logging`, `import sqlite3` (type hint only), `from dataclasses import dataclass`, `from pathlib import Path`.
- `_COLORS = frozenset({"green", "yellow", "red", "grey"})`.
- `@dataclass(frozen=True) class Stoplight:` fields `id: str`, `label: str`, `color: str`, `drilldown_path: str`; `__post_init__` validates `color in _COLORS` (else `ValueError` naming the allowed set, the `ToolHealthCheck` precedent) and `drilldown_path` non-empty.
- `RESEARCH_HEALTH_ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "exports" / "research" / "health" / "latest.json"` and a `def research_health_artifact_path() -> Path: return RESEARCH_HEALTH_ARTIFACT_PATH` accessor (so tests can monkeypatch the function without rebinding a module constant; the providers call the accessor).
- `RESEARCH_MONITOR_ID = "research_measurement"` — the envelope `monitor` id 18-D stamps; the research validator (Task 3) validates against it so a wrong JSON object at the shared path cannot false-green the stoplight (Codex R1 MAJOR #1). Define it here so BOTH 18-F (reader) and 18-D (writer) reference the SAME id (LOCK #4 — one shared contract).
- `RESEARCH_ARTIFACT_MAX_AGE_DAYS = 7` — the conservative V1 staleness threshold (Codex R2 MAJOR); a same-monitor artifact whose `generated_ts` is older than this → grey (closes the stale-but-green false-green vector). Module constant so 18-D can later tighten it.

**Acceptance:** the dataclass validates color + path; the shared constant resolves to `exports/research/health/latest.json` at the repo root. ASCII labels. Test passes.

---

## Task 2: The tool-health provider (`_tool_stoplight`) — reuse 18-E, defensive-grey-on-error

**Files:**
- Modify: `swing/monitoring/stoplights.py` (add `_tool_stoplight`)
- Modify: `tests/monitoring/test_stoplights.py`

**Step 1 (RED):** add tests:
- `test_tool_stoplight_maps_overall_to_color[green|yellow|red]`: monkeypatch the lazy-imported `compute_tool_health` (patch `swing.monitoring.tool_health.compute_tool_health`) to return a real `ToolHealthStatus(overall=<c>, checks=[ToolHealthCheck(key="k", status=<c>, summary="s")])`. Assert `_tool_stoplight(conn, cfg).color == <c>` and `.id == "tool"`, `.drilldown_path == "/health/tool"`. Build the fixture from the REAL 18-E dataclasses (recipe §5 anti-drift) — NOT a hand dict.
- `test_tool_stoplight_grey_when_compute_raises`: monkeypatch `compute_tool_health` to raise `RuntimeError("boom")`. Assert `_tool_stoplight(conn, cfg).color == "grey"` AND the call does NOT raise. (Both-ways: a non-defensive impl propagates the `RuntimeError` — the test distinguishes by asserting no-raise + grey.) Assert a WARNING was logged (caplog).
- `test_tool_stoplight_grey_when_cfg_none`: `_tool_stoplight(conn, None).color == "grey"` (no prices_cache_dir derivable; defensive). No raise.
- `test_tool_stoplight_passes_prices_cache_dir`: assert the patched `compute_tool_health` was called with `cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir` (the brief §2.1 signature; use a recording stub or `mock.call_args`).

Run the file — SEE fail.

**Step 2 (GREEN):** implement `def _tool_stoplight(conn, cfg) -> Stoplight:`
- Wrap the whole body in `try/except Exception` → on any exception, `log.warning("tool-health stoplight degraded to grey: %s", exc)` and `return Stoplight(id="tool", label="Tool health", color="grey", drilldown_path="/health/tool")`.
- Inside the try: if `cfg is None`, return the grey stoplight (can't derive `prices_cache_dir`). Else LAZY-import `from swing.monitoring.tool_health import compute_tool_health`; `status = compute_tool_health(conn, cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir)`; `return Stoplight(id="tool", label="Tool health", color=status.overall, drilldown_path="/health/tool")`. (`status.overall` ∈ {green,yellow,red}, all valid `Stoplight` colors.)

**Acceptance:** maps overall→color; degrades to grey + WARNING on ANY exception or cfg-None; never raises; calls `compute_tool_health` with the §2.1 signature. The 18-E reuse is via lazy import (no reimplementation — LOCK #4).

---

## Task 3: The research provider (`_research_stoplight`) — read the §3 envelope at the shared path; grey-until-18-D

**Files:**
- Modify: `swing/monitoring/stoplights.py` (add `_research_stoplight` + a tiny `_read_research_envelope` helper)
- Modify: `tests/monitoring/test_stoplights.py`

**Step 1 (RED):** add tests (monkeypatch `research_health_artifact_path` to a `tmp_path` file so no real `exports/` is touched):
- `test_research_stoplight_grey_when_artifact_absent`: point the path accessor at a non-existent file. Assert `_research_stoplight().color == "grey"`, `.id == "research"`, `.drilldown_path == "/health/research"`, and the label conveys "not deployed" (assert the label is non-empty ASCII; e.g. `"Research monitor"`). No WARNING required for the absent case (absence is the expected pre-18-D state — do NOT log-spam every render). (Both-ways: an impl that raised `FileNotFoundError` would fail the no-raise assertion.)
- `test_research_stoplight_maps_overall[green|yellow|red]`: write a valid envelope JSON `{"monitor":"research_measurement","generated_ts":<now-iso>,"overall":<c>,"checks":[{"key":"k","status":<c>,"summary":"s","detail":null}]}` to the tmp file (the `monitor` MUST be `RESEARCH_MONITOR_ID` or the identity gate greys it; `generated_ts` MUST be recent or the staleness gate greys it — use `datetime.now().isoformat()`). Assert `_research_stoplight().color == <c>`.
- `test_research_stoplight_grey_on_malformed_json`: write `"{ not json"`. Assert `.color == "grey"` + a WARNING logged (caplog) + no raise.
- `test_research_stoplight_grey_on_missing_or_invalid_overall`: write `{"monitor":"research_measurement","checks":[]}` (no `overall`) AND, parametrized, `{"monitor":"research_measurement","overall":"purple"}` (invalid). Assert `.color == "grey"` + WARNING + no raise. (Never a false green — an artifact missing `overall` must NOT default to green.)
- `test_research_stoplight_grey_on_monitor_mismatch` (Codex R1 MAJOR #1): write a VALID-looking envelope but with a WRONG `monitor` — `{"monitor":"shadow_expectancy","overall":"green","generated_ts":<now>,"checks":[]}` (a green `overall` from a DIFFERENT artifact). Assert `.color == "grey"` + WARNING + no raise. **Both-ways:** an impl that maps `overall` WITHOUT the `monitor`-id gate would return green here (a false-green from a wrong object) — the test distinguishes by asserting grey. Also `{}` (no `monitor`) → grey.
- `test_research_stoplight_grey_on_stale_generated_ts` (Codex R2 MAJOR): write a correct-monitor green envelope with `generated_ts` = `(now - 30 days).isoformat()`. Assert `.color == "grey"` + WARNING + no raise. **Both-ways:** the SAME envelope with `generated_ts = now.isoformat()` returns green (30 days > 7-day max → grey; 0 days < 7 → green — proving the gate distinguishes). Also a parametrized `generated_ts` absent / `"not-a-date"` → grey.
- `test_research_stoplight_grey_on_just_over_7_days` (Codex R3 MAJOR — the `.days`-floor boundary): write a correct-monitor green envelope with `generated_ts = (now - timedelta(days=7, hours=23)).isoformat()`. Assert `.color == "grey"`. **Both-ways:** a FLOORED `age.days > 7` impl yields `7 > 7 == False` → green (the bug); the EXACT `timedelta(days=7)` comparison yields `7d23h > 7d == True` → grey (correct). The test FAILS the floored impl and PASSES the exact-duration impl — proving the distinction. (Pair with `(now - timedelta(days=6, hours=23))` → green to bound the threshold from below.)

Run — SEE fail.

**Step 2 (GREEN):** implement:
- `def _read_research_envelope() -> dict | None:` — `path = research_health_artifact_path()`; `if not path.exists(): return None`; else `return json.loads(path.read_text(encoding="utf-8"))` (let JSON errors propagate to the caller's except). (The raw reader; identity-validation lives in `read_validated_research_envelope` below so BOTH the stoplight and the drill-down VM share ONE gate.)
- `def read_validated_research_envelope() -> tuple[str, dict] | None:` — the SHARED reader used by BOTH `_research_stoplight` (Task 3) and `build_research_health_vm` (Task 7), so the Codex R1 MAJOR #1 identity gate is defined ONCE (not re-derived). Returns `None` when the artifact is absent OR fails validation (malformed JSON, non-dict, wrong/missing `monitor` id, missing/invalid `overall`), else `(overall, env)`. It logs the WARNING on a present-but-invalid artifact (NOT on absent). `_research_stoplight` and `build_research_health_vm` both call THIS; the stoplight maps `overall`, the VM maps `env["checks"]`. (Public name — no leading underscore — because the VM module imports it.)
- `read_validated_research_envelope` does the work: `try:` `env = _read_research_envelope()`; `if env is None: return None` (absent — expected pre-18-D; no warning); `if not isinstance(env, dict) or env.get("monitor") != RESEARCH_MONITOR_ID: log.warning("research artifact monitor id mismatch/absent (%r); grey", (env.get("monitor") if isinstance(env, dict) else type(env).__name__)); return None` (the identity gate — Codex R1 MAJOR #1; a wrong object cannot false-green); `overall = env.get("overall")`; `if overall not in {"green","yellow","red"}: log.warning("research artifact overall invalid/absent (%r); grey", overall); return None`; THEN the staleness gate (Codex R2 MAJOR + R3 MAJOR — EXACT-duration, not floored `.days`): parse `env.get("generated_ts")` via `datetime.fromisoformat`; normalize BOTH sides to the SAME frame before subtracting (the host-tz-independent rule): if `parsed.tzinfo is not None`, compare against `datetime.now(parsed.tzinfo)` (aware-vs-aware); else compare against naive `datetime.now()` (naive-vs-naive, both host-local — symmetric, so host tz cancels). Compute `age = now_same_frame - parsed`; `if generated_ts absent/unparseable OR age > timedelta(days=RESEARCH_ARTIFACT_MAX_AGE_DAYS): log.warning("research artifact stale/undated (%r); grey", env.get("generated_ts")); return None`. **Use the EXACT `timedelta` comparison, NOT `age.days > N`** — `.days` FLOORS, so a 7d-23h artifact would wrongly stay green (Codex R3 MAJOR); `timedelta(days=7)` greys anything beyond 7*24h. ANY parse/compare error → `return None` (never raise). `return (overall, env)`. `except Exception as exc:` `log.warning("research artifact unreadable; grey: %s", exc); return None`.
- `def _research_stoplight() -> Stoplight:`
  - `grey = Stoplight(id="research", label="Research monitor", color="grey", drilldown_path="/health/research")`.
  - `validated = read_validated_research_envelope()`; `if validated is None: return grey`; `overall, _env = validated`; `return Stoplight(id="research", label="Research monitor", color=overall, drilldown_path="/health/research")`. (No try/except needed here — the shared reader never raises; but a belt-and-suspenders `try/except → grey` is acceptable and matches `_tool_stoplight`.)

**Acceptance:** absent → grey (no warning); valid + matching `monitor` id + fresh `generated_ts` → overall→color; malformed / wrong-or-missing `monitor` id / missing-invalid-overall / stale-or-unparseable `generated_ts` → grey + WARNING; never raises; never false-green (the identity gate closes the wrong-object vector; the staleness gate closes the same-monitor-stale vector — Codex R1 MAJOR #1 + R2 MAJOR). Reads the §3 envelope at the shared constant (LOCK #4). The research stoplight auto-lights when 18-D writes a fresh artifact stamped with `RESEARCH_MONITOR_ID`, with NO 18-F change (LOCK #3 — provider-driven).

---

## Task 4: The `health_stoplights` aggregator — never raises; two stoplights

**Files:**
- Modify: `swing/monitoring/stoplights.py` (add `health_stoplights`)
- Modify: `tests/monitoring/test_stoplights.py`

**Step 1 (RED):** add tests:
- `test_health_stoplights_returns_tool_then_research`: with both providers stubbed (tool→green via patched compute, research→grey via absent artifact), `health_stoplights(conn, cfg)` returns a 2-tuple `(tool, research)` in that order; `[s.id for s in result] == ["tool", "research"]`.
- `test_health_stoplights_never_raises_when_a_provider_raises`: monkeypatch `_tool_stoplight` to raise (simulate a defect that slipped its own guard) — `health_stoplights` STILL returns a 2-tuple with the tool slot grey and research intact; no exception. (Belt-and-suspenders: the aggregator itself wraps each provider call so even a non-defensive provider can't 500 the page. Both-ways: an unwrapped aggregator would propagate.)
- `test_health_stoplights_returns_tuple_not_list`: `isinstance(result, tuple)` (frozen render contract; the template iterates it).

Run — SEE fail.

**Step 2 (GREEN):** implement `def health_stoplights(conn, cfg) -> tuple[Stoplight, ...]:`
- Build each slot via a private `_safe(provider_callable, fallback_id, fallback_label, fallback_path)` wrapper: `try: return provider(...)` `except Exception as exc: log.warning(...); return Stoplight(id=fallback_id, label=fallback_label, color="grey", drilldown_path=fallback_path)`.
- `tool = _safe(lambda: _tool_stoplight(conn, cfg), "tool", "Tool health", "/health/tool")`; `research = _safe(lambda: _research_stoplight(), "research", "Research monitor", "/health/research")`.
- `return (tool, research)`.

**Acceptance:** returns `(tool, research)` always; NEVER raises even if a provider raises; tuple. This is the LOCK #2 core (defensive-never-raise) at the aggregator boundary — the context processor adds one more outer guard (Task 5) so the chain is doubly defended.

---

## Task 5: The base-wide context-processor injection (the load-bearing wiring)

**Files:**
- Modify: `swing/web/app.py` (add `_health_stoplights_context_processor` + register in `_build_templates`)
- Create: `tests/web/test_routes/test_health_stoplights.py`

**Step 1 (RED):** write `tests/web/test_routes/test_health_stoplights.py` (uses the `seeded_db` fixture + `create_app` + `with TestClient(app) as client:`):
- `test_dashboard_renders_with_stoplights_present`: GET `/` → 200; the body contains `class="stoplights"` AND both `/health/tool` and `/health/research` hrefs (the two stoplight links). (Both-ways: before the template/processor wiring, `/health/tool` would not appear in the topbar.)
- `test_context_processor_injects_health_stoplights`: assert the rendered topbar contains a `stoplight-` color class for each slot (e.g. at least two `stoplight-` occurrences). On a seeded-but-minimal DB the tool stoplight may be red (no completed run) and research grey — assert the PRESENCE of two color classes, not a specific color (the live status varies; the operator browser gate checks the true live color).

(The every-base-route + raise→grey-not-500 + drill-down tests come in Tasks 6-7; this task lands the processor + its unit-level proof.)

Run — SEE fail (no `stoplights` div / processor yet; this also depends on Task 8's template edit, so sequence Task 5's RED to assert the processor injects the key into the context via a direct unit test FIRST, then the rendered-body assertions go green after Task 8). **Sequencing note:** implement the processor (Task 5) + the template (Task 8) before asserting rendered-body strings; the processor's own unit test (below) is independent of the template.

Add a processor-unit test that does NOT depend on the template:
- `test_health_stoplights_context_processor_returns_key`: build a `Request`-like object whose `.app.state.cfg` is the seeded cfg (or call through a tiny seam). Assert `_health_stoplights_context_processor(request)` returns a dict with key `"health_stoplights"` whose value is a 2-tuple of `Stoplight`. (If constructing a bare Starlette `Request` is awkward, assert via a `TestClient` GET that the rendered context produced the stoplights — fold into the rendered-body test after Task 8. Prefer the direct unit test using a minimal stub object exposing `.app.state.cfg`.)
- `test_context_processor_never_raises_when_aggregator_raises`: monkeypatch `swing.web.app.health_stoplights` (the import-bound name in app.py) to raise; assert `_health_stoplights_context_processor(request)` returns `{"health_stoplights": ()}` (empty tuple) and does NOT raise. (Both-ways: an unwrapped processor would 500 EVERY page — the strictly-worse-than-the-gotcha failure mode LOCK #2 guards.)

**Step 2 (GREEN):** in `swing/web/app.py`:
- Add (module level): `from swing.monitoring.stoplights import health_stoplights` (top-level is fine — `stoplights.py` is stdlib-only at import; the heavy 18-E import is lazy inside the provider).
- `def _health_stoplights_context_processor(request: Request) -> dict:` — DEFENSIVE: `try:` `cfg = getattr(request.app.state, "cfg", None)`; `if cfg is None: return {"health_stoplights": ()}`; `from swing.data.db import connect`; `conn = connect(cfg.paths.db_path)`; `try: stoplights = health_stoplights(conn, cfg)` `finally: conn.close()`; `return {"health_stoplights": stoplights}`. `except Exception as exc:` `log.warning("health stoplights context processor degraded to empty: %s", exc); return {"health_stoplights": ()}`. (The empty-tuple fallback renders ZERO stoplights rather than 500 — the absolute floor. The base template tolerates an empty `health_stoplights` — Task 8.)
- In `_build_templates`: `return Jinja2Templates(env=env, context_processors=[_health_stoplights_context_processor])`. (Define `_health_stoplights_context_processor` ABOVE `_build_templates` so it is in scope; or reference it — both module-level. Verified viable: Starlette 1.0.0 accepts `context_processors=` alongside `env=`.)

**Acceptance:** the processor injects `health_stoplights` into EVERY render via `_build_templates` (so `app.state.templates` AND the error-handler's fresh templates both carry it); it NEVER raises (cfg-None → `()`; any exception → `()`); the DB connection is opened+closed per render (cheap, the cash-badge precedent). LOCK #2 outer guard. The connection is read-only in effect (the providers SELECT only; no `with conn:` write transaction).

---

## Task 6: The every-base-route regression test + the per-provider raise→grey-not-500 web test (the BINDING locks)

**Files:**
- Modify: `tests/web/test_routes/test_health_stoplights.py`

**Step 1 (RED → then GREEN after Task 8's template lands):**
- `test_every_base_route_renders_with_stoplights_and_no_500`: parametrize over the base-layout GET routes — `/`, `/watchlist`, `/journal`, `/pipeline`, `/metrics`, `/config`, a trade drill-down (`/journal/trades/<seeded_id>`), `/schwab/status`, and a deliberately-triggered error route (a 404 like `/journal/trades/999999` → the error page, which ALSO renders base via the context processor). For each: status_code != 500 (200 for the real pages; 404 for the missing-trade page is acceptable — the assertion is NO 500). For each 200 base page, assert `class="stoplights"` is present in the body. **This is the brief §3 LOCK-2 every-base-route regression test.** (Both-ways: a missed VM under the per-VM approach would 500 here; the context-processor approach makes this pass by construction — the test still GUARDS against a future regression of the processor or template.)
  - Seed the DB enough that each page renders (the `seeded_db` fixture + a seeded trade for the drill-down). Routes that need extra seed (e.g. a trade) get it; routes that 404/redirect without seed are asserted on the no-500 contract only.
  - NOTE in the test docstring: TestClient asserts the BODY, not the rendered DOM — a base-render 500 on an unrelated route IS catchable here (a 500 status), but a browser-only DOM defect is NOT; the operator browser gate (executing, brief §6) is the binding net for DOM/visual regressions.
- `test_provider_raise_degrades_to_grey_not_500`: monkeypatch `swing.monitoring.tool_health.compute_tool_health` to raise; GET `/` → 200 (NOT 500) and the body contains `stoplight-grey` (the tool slot degraded). Then monkeypatch the research artifact path to a malformed file; GET `/` → 200 + a `stoplight-grey`. **This is the brief §3 LOCK-2 "force each provider to raise → grey + no 500" test.** (Both-ways: a non-defensive provider/processor would yield a 500 here.)
- `test_forced_500_error_page_renders_stoplights` (Codex R1 MAJOR #2 — the LOAD-BEARING error-page path the 404 case does NOT exercise): a 404 flows through `_handle_http_exc` → `request.app.state.templates`; but the plan's "every render INCLUDING the error page" claim rests on `_handle_any` (`app.py:104-133`), which builds a FRESH `_build_templates(...)` instance for the 500 page. That fresh-templates path is what the context-processor registration must also cover. **Test sequencing (Codex R2 MINOR — make it explicit so the test cannot accidentally exercise client-side propagation):** (1) build the app via `create_app(cfg, cfg_path)`; (2) register a test-only raising route on THAT app instance BEFORE creating the client — `app.add_api_route("/__boom__", _raise_boom)` where `def _raise_boom(): raise RuntimeError("boom")`; (3) create the client with `TestClient(app, raise_server_exceptions=False)` (REQUIRED — the default `raise_server_exceptions=True` re-raises the exception into the test instead of returning the rendered 500 response, so the assertion would never see the error page) inside the `with` lifespan block; (4) `resp = client.get("/__boom__")`; assert `resp.status_code == 500` (the real `_handle_any` rendered `error.html.j2` through the fresh templates) AND `'class="stoplights"' in resp.text` (the processor ran on the fresh-templates render). **Both-ways:** if the processor were registered ONLY on `app.state.templates` (not inside `_build_templates`), the 500 page would render WITHOUT the stoplights — this test distinguishes the correct registration site.

**Step 2 (GREEN):** these pass once Task 5 (processor) + Task 8 (template) are in. No new production code beyond Tasks 5+8 (the forced-500 test's `/__boom__` route is test-only — added to the app instance inside the test, NOT to production code).

**Acceptance:** every base route renders without a 500 and shows the stoplights; the REAL `_handle_any` 500 path (fresh `_build_templates`) renders the stoplights too; forcing each provider to raise degrades to grey, never 500. The three binding LOCK-2 tests (every-base-route, forced-500-error-page, per-provider-raise→grey) exist and pass.

---

## Task 7: The two drill-down routes + VMs + templates (`/health/tool`, `/health/research`)

**Files:**
- Create: `swing/web/view_models/health.py`
- Create: `swing/web/routes/health.py`
- Create: `swing/web/templates/health_tool.html.j2`, `swing/web/templates/health_research.html.j2`
- Modify: `swing/web/app.py` (import + `include_router` the `health` router)
- Modify: `tests/web/test_routes/test_health_stoplights.py`

**Step 1 (RED):** add tests:
- `test_health_tool_route_lists_checks`: GET `/health/tool` → 200; the body lists each tool-health check's `key` + `summary` (assert at least one known check key appears, e.g. `pipeline_freshness`, given the seeded DB). Renders through base (assert `class="stoplights"` present — the drill-down is itself a base page).
- `test_health_research_route_not_deployed_message`: with the artifact absent, GET `/health/research` → 200; the body contains an ASCII "not yet deployed" message naming 18-D (e.g. "research monitor (18-D) is not yet deployed"). No 500.
- `test_health_research_route_lists_checks_when_artifact_present`: write a valid envelope to the monkeypatched path; GET `/health/research` → 200 lists the artifact's check keys/summaries.
- `test_health_routes_read_only`: (light) the routes issue no writes — assert they return 200 against a `mode`-default DB and the test's DB row counts are unchanged (or simply that the handler uses `connect` + SELECTs; a structural assertion is acceptable for V1).

Run — SEE fail (routes missing → 404).

**Step 2 (GREEN):**
- `swing/web/view_models/health.py`:
  - `@dataclass(frozen=True) class ResearchCheck:` `key: str`, `status: str`, `summary: str`, `detail: str | None = None` — the render shape for a research check (dot-accessible, mirroring 18-E's `ToolHealthCheck` so BOTH templates use uniform `{{ check.key }}` dot access — Codex R1 MINOR #3; NEVER dicts/item-access).
  - `@dataclass(frozen=True) class ToolHealthPageVM:` base-banner fields (carry them as explicit fields-with-defaults populated via the `**_base_banner_fields` spread, the `TradeDrilldownVM` precedent at `journal.py:588-596`) + `overall: str` + `checks: tuple` (REUSE 18-E's `ToolHealthCheck` directly — already `.key/.status/.summary/.detail` dot-accessible; the VM holds `status.checks`) + `generated_ts: str`. `PAGE_KIND = PageKind.HISTORY_ANALYSIS`.
  - `@dataclass(frozen=True) class ResearchHealthPageVM:` base-banner fields + `available: bool` + `overall: str | None` + `checks: tuple[ResearchCheck, ...]` + `generated_ts: str | None`. When the artifact is absent/malformed, `available=False`, `checks=()`.
  - `build_tool_health_vm(conn, cfg)`: lazy-import `compute_tool_health`; `status = compute_tool_health(conn, cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir)`; `banner = _base_banner_fields(conn, cfg)` (import from `swing.web.view_models.journal`); return `ToolHealthPageVM(overall=status.overall, checks=status.checks, generated_ts=status.generated_ts, **banner)`. Defensive: wrap the compute in try/except → on error build a VM with `overall="grey"`, `checks=()` (NO 500 on the drill-down either).
  - `build_research_health_vm(conn, cfg)`: call `read_validated_research_envelope()` (the SHARED reader from `swing.monitoring.stoplights` — reuses the SAME `monitor`-id gate as `_research_stoplight`, Codex R1 MAJOR #1; validation is NOT re-derived); `banner = _base_banner_fields(conn, cfg)`; if it returns `None` (absent/malformed/wrong-monitor-id/invalid-overall) → `ResearchHealthPageVM(available=False, overall=None, checks=(), generated_ts=None, **banner)`; else `overall, env = validated`; map EACH `env["checks"]` dict to `ResearchCheck(key=c["key"], status=c["status"], summary=c["summary"], detail=c.get("detail"))` (guard a malformed `checks` shape with `c.get(...)` + a per-item try/except so one bad check doesn't 500 the page), `generated_ts = env.get("generated_ts")`, `available=True`. Defensive: an outer try/except → the not-available VM (NO 500 on the drill-down).
- `swing/web/routes/health.py`: `router = APIRouter()`; `@router.get("/health/tool", response_class=HTMLResponse) def health_tool_page(request): cfg = apply_overrides(request.app.state.cfg); templates = request.app.state.templates; conn = connect(cfg.paths.db_path); try: with conn: vm = build_tool_health_vm(conn, cfg) finally: conn.close(); return templates.TemplateResponse(request, "health_tool.html.j2", {"vm": vm})`. Same shape for `/health/research`.
- Templates `health_tool.html.j2` / `health_research.html.j2`: `{% extends "base.html.j2" %}{% block content %}` — an `<h1>` + a table/list of `{{ check.key }}` / `{{ check.status }}` / `{{ check.summary }}` / `{{ check.detail or '' }}`. The research template guards `{% if not vm.available %}` → the ASCII "research monitor (18-D) is not yet deployed" paragraph; `{% else %}` lists the checks. ASCII only.
- `swing/web/app.py`: in the `from swing.web.routes import (...)` block + the `app.include_router(...)` block (lines 567-616), add `health as health_route` and `app.include_router(health_route.router)`.

**Acceptance:** both drill-downs render read-only base pages listing the monitor's checks; research-absent shows the 18-D-pending message; both are defensive (no 500). They render through the SAME base (so the stoplights appear on the drill-downs too).

---

## Task 8: The `base.html.j2` topbar stoplights + the CSS

**Files:**
- Modify: `swing/web/templates/base.html.j2` (the topbar block, lines 68-81)
- Modify: `swing/web/static/app.css`

**Step 1 (RED):** the rendered-body assertions in Tasks 5/6/7 (`class="stoplights"`, the two `/health/*` hrefs, the `stoplight-<color>` classes) are the RED proof for this task — they fail until the template renders the block. (No NEW test is strictly required here; the existing rendered-body tests cover it. Optionally add `test_base_topbar_stoplights_markup` asserting the exact `<div class="stoplights">` + `<a class="stoplight stoplight-...">` shape for one rendered page, so a future template-shape regression is caught.)

**Step 2 (GREEN):** in `base.html.j2`, inside `<nav class="topbar">`, adjacent to `<span class="date">{{ vm.session_date }}</span>`, add:
```
<div class="stoplights">
  {% for s in (health_stoplights | default([])) %}
  <a class="stoplight stoplight-{{ s.color }}" href="{{ s.drilldown_path }}"
     title="{{ s.label }}: {{ s.color }}" aria-label="{{ s.label }} status {{ s.color }}"></a>
  {% endfor %}
</div>
```
- `health_stoplights` is read from the CONTEXT (the processor), NOT `vm`. The `| default([])` tolerates the empty-tuple fallback (LOCK #2 floor — an empty `health_stoplights` renders zero indicators, never an error). Each indicator is a colored dot (CSS), not a glyph — ASCII-clean. The `title`/`aria-label` give the operator the label+color on hover/screenreader.
- In `app.css`: `.stoplights { display: inline-flex; gap: ... }`; `.stoplight { width/height; border-radius: 50%; display: inline-block; }`; `.stoplight-green { background: <green>; }` / `-yellow` / `-red` / `-grey` (grey = a neutral no-data tone). Add dark-theme variants under `html.dark .stoplight-*` if the existing palette needs them (mirror the existing topbar dark-mode treatment).

**Acceptance:** the topbar renders the two stoplights as colored `<a>` links to the drill-downs on EVERY base page; an empty `health_stoplights` renders nothing (no error); CSS colors render in both themes (the operator browser gate confirms the visual — executing).

---

## Verification

**This dispatch (writing-plans):** the plan is reviewed by WSL-Codex at the `review-fast` tier to `NO_NEW_CRITICAL_MAJOR` (transcript in `.copowers-findings.md`); committed once at convergence.

**Executing-cycle gates (NOT run here — brief §6, noted for the executing dispatch):**
- **Codex `review-strong`** on the shipped diff (production web code — the high floor; never tiered down) to convergence.
- **The operator-approved `codex-auto-review` A/B** (the FIRST run of it) on the same diff alongside review-strong; persist BOTH transcripts; the orchestrator reports the comparison. CHARC assesses promotion at the gate.
- **The BINDING operator browser gate:** drive a real browser through EVERY base route (dashboard, watchlist, journal, pipeline, metrics, config, a trade drill-down, the schwab pages, AND a deliberately-triggered error page) — assert no 500, both stoplights render, the tool stoplight shows the TRUE live color, the research stoplight is GREY ("18-D pending"), and both drill-downs load. The all-pages base-layout family is browser-only (TestClient asserts body, not the rendered DOM / a base-render 500).
- **No-false-green** full fast suite (`python -m pytest -m "not slow" -q`) on the MERGED head + `ruff check swing/` before close.

**Test-count note for executing:** read the count off the final merged HEAD; do not carry a branch count forward.

---

## LOCKS (brief §3) — reflected in this plan

1. **NO new schema, NO new dependency.** Compute-at-render (18-E's `compute_tool_health`) + a `json.loads` of a file; no migration, no `pyproject` touch. (File Map: zero `swing/data`/`swing/trades`/`swing/pipeline`/migration edits.)
2. **The base-wide injection is DEFENSIVE — it NEVER raises → grey.** Triply guarded: each provider catches all exceptions → grey (Tasks 2/3); the aggregator wraps each provider call → grey (Task 4); the context processor wraps the aggregator → `()` (Task 5). Tests: the per-provider raise→grey-not-500 web test (Task 6) + the every-base-route regression incl. the error page (Task 6) + the processor-never-raises unit test (Task 5).
3. **`grey` is RENDER-ONLY + never a false-green.** The monitors' envelopes emit only {green,yellow,red} (18-E rejects grey at construction, grounded at `tool_health.py:76-82`; 18-D conforms to the §3 envelope). Grey is produced ONLY by the 18-F providers (no-data / not-deployed / error). The research stoplight is grey until 18-D's artifact exists, then auto-lights with NO 18-F change (Task 3 — provider-driven). TWO gates close the false-green vectors (Codex R1 MAJOR #1 + R2 MAJOR): the artifact-IDENTITY gate (`monitor == RESEARCH_MONITOR_ID`) blocks a wrong object; the STALENESS gate (`generated_ts` older than `RESEARCH_ARTIFACT_MAX_AGE_DAYS`) blocks a same-monitor-but-stale object. Both → grey.
4. **Reuse, don't fork.** Tool-health = 18-E's `compute_tool_health(conn, cfg=cfg, prices_cache_dir=cfg.paths.prices_cache_dir)` lazy-imported (Task 2; NO reimplementation). The research read is the §3 envelope at the SINGLE shared `swing/monitoring/` path constant `RESEARCH_HEALTH_ARTIFACT_PATH` = `exports/research/health/latest.json` (Task 1/3).
5. **Browser gate BINDING** (executing; Verification section).

## V1 simplifications (flagged for the return report)
- **Artifact-staleness uses a conservative 7-day default** (`RESEARCH_ARTIFACT_MAX_AGE_DAYS`) keyed on the envelope's own `generated_ts` — this CLOSES the same-monitor-stale false-green vector (Codex R2 MAJOR) without inventing a 18-D-owned cadence. When 18-D ships, it may tighten the threshold via the shared constant; until then 7 days is weekly-cadence-tolerant. (NOT a deferred gap — the gate is in V1.)
- **The drill-down's research-absent page** is a static message; once 18-D ships its envelope, the same template lists the checks with NO route change.
- **The base-banner-field hand-duplication debt (charter D15)** is UNCHANGED — 18-F sidesteps it via the context processor and does NOT worsen it; a deliberate base-field consolidation remains a separate future item.
