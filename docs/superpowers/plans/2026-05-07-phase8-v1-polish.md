# Phase 8 V1 Polish — Detail Button + Timeline Union Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land two operator-witnessed Phase 8 V1 follow-ups in a single bundled dispatch — (Item #2) add a "Detail" navigation button to each dashboard open-positions row that opens `/trades/{id}`, and (Item #1) extend `build_daily_management_timeline_vm` so Phase 7 stop-adjust orphan `trade_events` rows surface in the per-trade timeline alongside Phase 8 `daily_management_records`, deduped via `linked_trade_event_id`, labelled "Stop adjustment (legacy quick-adjust)".

**Architecture:** Pure web-layer change. Repo functions (`list_for_trade_timeline`, `list_events_for_trade`) are consumed READ-ONLY. The union + dedup happens at the VM layer in `swing/web/view_models/trades.py:build_daily_management_timeline_vm` (locked design choice — Option B from §0.3 #2 of the writing-plans brief). The existing `DailyManagementTimelineRowVM` dataclass extends with six optional `legacy_*` fields defaulted `None` so non-orphan rows construct unchanged. Template `partials/daily_management_timeline.html.j2` gains a third `record_type == 'trade_event_legacy'` branch. Dashboard partial `partials/open_positions_row.html.j2` gains an `<a class="row-action-link">` "Detail" button next to the existing Exit / Adjust stop HTMX buttons; full-page navigation (NOT HTMX swap) so the destination route's full layout renders.

**Tech Stack:** SQLite + sqlite3 (read-only on existing tables); FastAPI + Starlette `TemplateResponse` (existing route `/trades/{trade_id}`); HTMX 2.x (existing patterns; new "Detail" link uses plain `<a href>`, NOT HTMX); Jinja2 templates extending `base.html.j2`; pytest + `fastapi.testclient.TestClient`.

---

## §A — Resolved-during-planning items

### §A.1 Phase 7 `payload_json` field name for stop_adjust events

**Empirical verification** (`swing/data/repos/trades.py:191-219`): Phase 7's `update_stop_with_event` writes the JSON payload as `{"old_stop": <prior>, "new_stop": <new>}` (key `old_stop`, not `prior_stop`). The Phase 8 `daily_management_records` table uses the column name `prior_stop` for the operator-supplied "stop before this change" value. To minimize confusion in the new template branch + helper:

- The VM field is `legacy_prior_stop: float | None` (semantically maps to "stop before the change", consistent with the Phase 8 `prior_stop` column).
- The decoder helper `_orphan_stop_adjust_to_timeline_row` maps `payload_json["old_stop"] → legacy_prior_stop` and `payload_json["new_stop"] → legacy_new_stop`.
- The decoder uses `dict.get("old_stop")` / `dict.get("new_stop")` (NOT subscript) so a malformed or partial payload yields `None` rather than `KeyError`. Wrapped in `try/except (json.JSONDecodeError, TypeError)` — see Task B.4.

### §A.2 Sort-key tiebreak for orphan rows

Per writing-plans brief §0.3 #7, orphan rows map to the canonical timeline sort key as:

- `review_date := trade_events.ts[:10]` (string slice — `ts` is ISO-8601 `YYYY-MM-DDTHH:MM:SS`).
- `created_at := trade_events.ts` (full ISO timestamp).
- `management_record_id := -trade_events.id` (NEGATIVE int).

The negative-id choice gives orphans a deterministic tiebreak position WITHIN the same `(review_date, created_at)` bucket: orphans with `management_record_id = -42` sort BEFORE Phase 8 daily-management rows with positive IDs. This satisfies the brief's "stable chronological ordering with deterministic tiebreaks" constraint without requiring a synthetic discriminator column. The negative value never collides with the positive `management_record_id` autoincrement, and the only consumer of `management_record_id` (template `data-timeline-record-id` attribute) is informational; tests differentiate orphans via `data-record-type="trade_event_legacy"`.

### §A.3 Detail button form — plain anchor vs HTMX button

**Locked:** plain `<a href="/trades/{id}" class="row-action-link" onclick="event.stopPropagation()">Detail</a>`. Rationale:

- Destination is a **full-page navigation** (`/trades/{id}` renders the entire trade-detail page, not an HTMX swap into the dashboard row).
- Existing Exit / Adjust stop buttons use HTMX because they swap the row in place with a form fragment; Detail does not match that pattern.
- Plain `<a>` tag respects `Ctrl+click` (open in new tab), `right-click → Save link`, and middle-click — affordances HTMX `<button>` patterns lose.
- `event.stopPropagation()` prevents the row-level `hx-get="/trades/open/{id}/expand"` from firing when the user clicks Detail (CLAUDE.md "HTMX click propagation" gotcha).
- No `class="button"` because the existing dashboard CSS doesn't define a `.button` class on anchors; the anchor is rendered with default link styling. If operator wants visual parity with the buttons, that's a follow-up CSS polish; functional parity is met.

### §A.4 Test count projection

Per Phase 6/7/8 discriminating-test discipline + §0.3 brief: target **+10 to +14 fast tests**. Subtotal (per-task projections): A.1 (1) + A.3 (1) + A.4 (1) + B.1 (1, RED) + B.6 (orphan surfaces, 1) + B.7 (non-stop-adjust filter, 1) + B.8 (sort order, 1) + B.9 (dedup, 1) + B.5 (template label, 1) + B.4-defensive (malformed payload, 1) = 10 expected. Range allows for splitting if a task discovers a sub-case needing isolation.

### §A.5 `DailyManagementTimelineRowVM` — six new optional fields

The existing dataclass (`swing/web/view_models/trades.py:1051-1073`) has 19 required-positional fields. Adding optional defaulted fields requires those defaults to come AFTER all required fields — which they will, as the existing order is preserved and the six new fields are appended at the end with `= None` defaults. The dataclass remains `frozen=True`. All existing call sites (only `_record_to_timeline_row` constructs them) use kwargs, so positional-construction hazard does not apply.

### §A.6 Schema state

`EXPECTED_SCHEMA_VERSION == 16`. NO migration in scope. NO new repo functions. NO new service-layer functions.

---

## §B — File map

### Files to MODIFY

| Path | Reason |
|---|---|
| `swing/web/view_models/trades.py` | (1) Extend `DailyManagementTimelineRowVM` dataclass with six new optional fields: `trade_event_id: int \| None = None`, `event_type: str \| None = None`, `legacy_prior_stop: float \| None = None`, `legacy_new_stop: float \| None = None`, `legacy_rationale: str \| None = None`, `legacy_notes: str \| None = None`. (2) Add module-level helper `_orphan_stop_adjust_to_timeline_row(event: TradeEvent) -> DailyManagementTimelineRowVM`. (3) Extend `build_daily_management_timeline_vm` to additionally call `list_events_for_trade`, compute `linked_event_ids` set from existing event_log records, filter trade_events to `event_type == 'stop_adjust'` orphans, construct rows via the helper, merge + sort by `(review_date, created_at, management_record_id)`. |
| `swing/web/templates/partials/daily_management_timeline.html.j2` | Add a third top-level branch `{% elif row.record_type == 'trade_event_legacy' %}` in the `<td>Type</td>` cell (renders `<span class="badge badge-event-legacy" data-record-type="trade_event_legacy">Stop adjustment (legacy quick-adjust)</span>`) and in the `<td>Details</td>` cell (renders `stop $X.XX → $Y.YY` ONLY when at least one of `legacy_prior_stop`/`legacy_new_stop` is non-None; otherwise renders the fallback "stop adjustment details unavailable" so a malformed-payload row does NOT show a dangling "stop  →" transition). Add the legacy `legacy_rationale` and `legacy_notes` to the `<td>Notes</td>` cell. |
| `swing/web/templates/partials/open_positions_row.html.j2` | Insert a new `<a href="/trades/{{ row.trade.id }}" class="row-action-link" onclick="event.stopPropagation()">Detail</a>` element inside the `<td class="row-actions">` cell, between the Exit and Adjust stop buttons OR before/after them — locked: append AFTER Exit + Adjust stop so Detail is the rightmost action (least frequent click; preserves muscle memory for the existing two). |

### Files to CREATE

| Path | Responsibility |
|---|---|
| `tests/web/test_dashboard_detail_button.py` | Three tests: (1) Detail anchor present + correct href on every open-positions row (rendered dashboard HTML grep), (2) Detail anchor includes `event.stopPropagation()` literal, (3) `/trades/{trade_id}` route registered and resolves to 200 for a seeded trade (Phase 6 R5 I3 lesson). |
| `tests/web/test_daily_management_timeline_legacy_union.py` | Six tests covering Item #1 union behavior — see Tasks B.1, B.6, B.7, B.8, B.9, B.5, plus B.4 defensive payload-decode. |

### Files NOT to modify

- `swing/data/repos/daily_management.py` — `list_for_trade_timeline` consumed read-only.
- `swing/data/repos/trades.py` — `list_events_for_trade` consumed read-only.
- `swing/data/models.py` — `TradeEvent` dataclass shape unchanged.
- `swing/trades/stop_adjust.py` — Phase 7 service unchanged.
- `swing/web/routes/trades.py` — handler signature unchanged; `build_daily_management_timeline_vm`'s return-shape extends but its kwargs and return type are stable.
- Any migration / schema file — schema version stays at 16.

---

## §C — Tasks

### Task A.1 — Detail button: write failing test for anchor presence

**Files:**
- Create: `tests/web/test_dashboard_detail_button.py`

- [ ] **Step 1: Write the failing test**

```python
"""Phase 8 V1 polish Item #2: Dashboard "Detail" button visible per open
positions row. Plan: docs/superpowers/plans/2026-05-07-phase8-v1-polish.md.
"""
from __future__ import annotations

import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import ensure_schema
from swing.web.app import create_app
from swing.web.price_cache import PriceCache


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str = "DHC",
    state: str = "managing",
) -> None:
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (?, ?, '2026-05-01', 100.0, 50, 90.0, 92.0, ?, "
        " 'manual_off_pipeline', '2026-05-01T09:30:00', 50.0, 100.0)",
        (trade_id, ticker, state),
    )
    conn.commit()


@pytest.fixture
def dashboard_app(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    db_path = tmp_path / "phase8_polish.db"
    conn = ensure_schema(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC")
        _seed_trade(conn, trade_id=2, ticker="CC")
    finally:
        conn.close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )
    return create_app(cfg), db_path


def test_dashboard_detail_anchor_present_per_open_position(dashboard_app):
    """Pre-fix: zero anchors with href='/trades/<id>' in dashboard HTML.
    Post-fix: exactly one such anchor per seeded open trade (2 → 2 matches)."""
    app, _ = dashboard_app
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.text
    # Anchor with the exact href our partial emits.
    assert body.count('href="/trades/1"') >= 1
    assert body.count('href="/trades/2"') >= 1
    # And it carries the literal "Detail" anchor text within the row-actions cell.
    assert ">Detail</a>" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/test_dashboard_detail_button.py::test_dashboard_detail_anchor_present_per_open_position -v`
Expected: FAIL with assertion error on `body.count('href="/trades/1"') >= 1` (currently zero — no Detail anchor in partial).

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/web/test_dashboard_detail_button.py
git commit -m "test(web): Task A.1 — failing test for dashboard Detail button presence"
```

---

### Task A.2 — Detail button: implement template change

**Files:**
- Modify: `swing/web/templates/partials/open_positions_row.html.j2`

- [ ] **Step 1: Add the Detail anchor inside `<td class="row-actions">`**

Edit the `<td class="row-actions">` block (currently lines 42-51) to append the Detail anchor AFTER the existing Exit and Adjust stop buttons:

```jinja
  <td class="row-actions">
    <button onclick="event.stopPropagation()"
            hx-get="/trades/{{ row.trade.id }}/exit/form"
            hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Exit</button>
    <button onclick="event.stopPropagation()"
            hx-get="/trades/{{ row.trade.id }}/stop/form"
            hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Adjust stop</button>
    <a href="/trades/{{ row.trade.id }}"
       class="row-action-link"
       onclick="event.stopPropagation()">Detail</a>
  </td>
```

Rationale: the anchor is a plain link (full-page navigation). `event.stopPropagation()` prevents the row's `hx-get="/trades/open/{id}/expand"` (line 20) from firing when the user clicks Detail.

- [ ] **Step 2: Run the failing test from A.1**

Run: `python -m pytest tests/web/test_dashboard_detail_button.py::test_dashboard_detail_anchor_present_per_open_position -v`
Expected: PASS.

- [ ] **Step 3: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q tests/web/test_state_badge_partial.py tests/web/ -k "open_position or dashboard"`
Expected: All pass; no regressions.

- [ ] **Step 4: Commit**

```bash
git add swing/web/templates/partials/open_positions_row.html.j2
git commit -m "feat(web): Task A.2 — add Detail navigation button to dashboard open-positions row"
```

---

### Task A.3 — Detail button: stopPropagation marker test

**Files:**
- Modify: `tests/web/test_dashboard_detail_button.py`

- [ ] **Step 1: Add second test asserting `event.stopPropagation()` marker**

Append to `tests/web/test_dashboard_detail_button.py`:

```python
def test_dashboard_detail_anchor_includes_stop_propagation(dashboard_app):
    """Per CLAUDE.md HTMX click-propagation gotcha: the Detail anchor MUST
    include `event.stopPropagation()` so a click on Detail does NOT also fire
    the row's `hx-get="/trades/open/{id}/expand"` row-expand binding.

    Pre-fix expectation: rendered HTML for the open-positions row contains an
    anchor without the literal `event.stopPropagation()` marker.
    Post-fix expectation: every Detail anchor includes the marker.
    """
    app, _ = dashboard_app
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    # Locate every "Detail" anchor and verify the stopPropagation marker is
    # present in the same anchor opening tag. We grep for the substring once
    # since the partial template emits the marker inline.
    needle = '<a href="/trades/1"'
    assert needle in body, f"Detail anchor not found for trade 1; body subset: {body[:500]}"
    anchor_start = body.index(needle)
    anchor_end = body.index("</a>", anchor_start)
    anchor_block = body[anchor_start:anchor_end]
    assert "event.stopPropagation()" in anchor_block
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/web/test_dashboard_detail_button.py::test_dashboard_detail_anchor_includes_stop_propagation -v`
Expected: PASS (Task A.2's template change already includes the marker).

- [ ] **Step 3: Commit**

```bash
git add tests/web/test_dashboard_detail_button.py
git commit -m "test(web): Task A.3 — assert Detail anchor carries event.stopPropagation marker"
```

---

### Task A.4 — Detail button: target route resolves test

**Files:**
- Modify: `tests/web/test_dashboard_detail_button.py`

- [ ] **Step 1: Add third test asserting `/trades/{id}` resolves**

Append to `tests/web/test_dashboard_detail_button.py`:

```python
def test_dashboard_detail_target_route_resolves(dashboard_app):
    """Phase 6 R5 I3 lesson: navigation target route MUST be registered AND
    resolve. The Detail anchor's href is `/trades/{id}`; verify both the route
    is registered + GET to that path returns 200 for a seeded trade.

    Pre-fix expectation (had we shipped a broken href like `/trade/1`): GET
    returns 404. Post-fix expectation: GET returns 200 with the trade-detail
    page rendered.
    """
    app, _ = dashboard_app
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/trades/{trade_id}" in paths, (
        f"GET /trades/{{trade_id}} not registered; routes: {sorted(p for p in paths if p)}"
    )
    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    # And the page renders the Phase 8 timeline section header (sanity that
    # the Detail destination is actually the trade-detail page).
    assert 'id="daily-management-timeline"' in response.text
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/web/test_dashboard_detail_button.py -v`
Expected: All three tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/web/test_dashboard_detail_button.py
git commit -m "test(web): Task A.4 — assert Detail anchor target route registered + resolves"
```

---

### Task B.0 — Survey: confirm Phase 7 trade_events stop_adjust shape

This task is documentation-only (no code, no commit). Read these to confirm the assumptions in §A.1 and §A.2 above before proceeding to B.1:

- [ ] `swing/data/repos/trades.py:191-219` (`update_stop_with_event`) — confirm payload JSON is `{"old_stop": <float>, "new_stop": <float>}`.
- [ ] `swing/data/repos/trades.py:282-294` (`list_events_for_trade`) — confirm signature `list_events_for_trade(conn, trade_id) -> list[TradeEvent]` ordered by `(ts, id)`.
- [ ] `swing/data/models.py:182-189` (`TradeEvent`) — confirm dataclass fields `id, trade_id, ts, event_type, payload_json, rationale, notes`.
- [ ] `swing/data/models.py:431-447` (`DailyManagementRecord`) — confirm `linked_trade_event_id` is the column we filter against (NULLABLE FK to `trade_events.id`; populated by Phase 8 `record_event_log` for stop_changed event_log rows).

If any assumption above is WRONG, halt + escalate to orchestrator before proceeding (the plan's helper signature depends on these).

---

### Task B.1 — Timeline union: failing test that orphan stop_adjust does NOT yet appear

**Files:**
- Create: `tests/web/test_daily_management_timeline_legacy_union.py`

- [ ] **Step 1: Write the failing test**

```python
"""Phase 8 V1 polish Item #1: Phase 7 stop-adjust trade_events that have NO
corresponding Phase 8 event_log row (orphans) surface in the per-trade
timeline labelled "Stop adjustment (legacy quick-adjust)".

Plan: docs/superpowers/plans/2026-05-07-phase8-v1-polish.md.

The union happens at the VM layer (build_daily_management_timeline_vm);
repo functions stay atomic.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import replace as dc_replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.web.app import create_app
from swing.web.price_cache import PriceCache
from swing.web.view_models.trades import build_daily_management_timeline_vm


def _seed_trade(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    ticker: str = "DHC",
    state: str = "managing",
    current_stop: float = 92.0,
) -> None:
    conn.execute(
        "INSERT INTO trades "
        "(id, ticker, entry_date, entry_price, initial_shares, initial_stop, "
        " current_stop, state, trade_origin, pre_trade_locked_at, "
        " current_size, current_avg_cost) "
        "VALUES (?, ?, '2026-05-01', 100.0, 50, 90.0, ?, ?, "
        " 'manual_off_pipeline', '2026-05-01T09:30:00', 50.0, 100.0)",
        (trade_id, ticker, current_stop, state),
    )
    conn.commit()


@pytest.fixture
def cfg_with_db(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)
    db_path = tmp_path / "phase8_polish_timeline.db"
    ensure_schema(db_path).close()
    base_cfg = load(Path("swing.config.toml"))
    cfg = dc_replace(
        base_cfg, paths=dc_replace(base_cfg.paths, db_path=db_path),
    )
    return cfg, db_path


def _insert_orphan_stop_adjust(
    conn: sqlite3.Connection, *, trade_id: int, ts: str,
    old_stop: float, new_stop: float,
    rationale: str = "trail-up",
    notes: str | None = "manual",
) -> int:
    """Mirrors Phase 7 update_stop_with_event INSERT shape exactly so the
    orphan row is byte-identical to a row written by the legacy code path,
    minus the trades.current_stop UPDATE side-effect (which is irrelevant
    for read-side timeline rendering)."""
    payload = {"old_stop": old_stop, "new_stop": new_stop}
    cur = conn.execute(
        "INSERT INTO trade_events "
        "(trade_id, ts, event_type, payload_json, rationale, notes) "
        "VALUES (?, ?, 'stop_adjust', ?, ?, ?)",
        (trade_id, ts, json.dumps(payload, sort_keys=True), rationale, notes),
    )
    conn.commit()
    return cur.lastrowid


def test_orphan_stop_adjust_surfaces_in_timeline_post_fix(cfg_with_db):
    """Discriminating test (Item #1):

    Pre-fix expectation: with one orphan trade_events row of event_type=
    'stop_adjust' and zero daily_management_records, the timeline VM has
    `len(rows) == 0` (the existing build function only consults
    daily_management_records).
    Post-fix expectation: `len(rows) == 1` with `rows[0].record_type ==
    'trade_event_legacy'` carrying the decoded prior_stop/new_stop.
    """
    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        event_id = _insert_orphan_stop_adjust(
            conn, trade_id=1,
            ts="2026-05-05T10:30:00",
            old_stop=90.0, new_stop=95.0,
            rationale="trail-up",
            notes="trail to entry+5",
        )
    finally:
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    assert len(vm.rows) == 1
    row = vm.rows[0]
    assert row.record_type == "trade_event_legacy"
    assert row.trade_event_id == event_id
    assert row.event_type == "stop_adjust"
    assert row.legacy_prior_stop == 90.0
    assert row.legacy_new_stop == 95.0
    assert row.legacy_rationale == "trail-up"
    assert row.legacy_notes == "trail to entry+5"
    # Sort key mapping per §A.2:
    assert row.review_date == "2026-05-05"
    assert row.created_at == "2026-05-05T10:30:00"
    assert row.management_record_id == -event_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py::test_orphan_stop_adjust_surfaces_in_timeline_post_fix -v`
Expected: FAIL with `AssertionError: assert 0 == 1` (the existing build function returns zero rows when only trade_events exist).

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/web/test_daily_management_timeline_legacy_union.py
git commit -m "test(web): Task B.1 — failing test for legacy stop-adjust timeline union"
```

---

### Task B.2 — Timeline VM: extend `DailyManagementTimelineRowVM` with six optional `legacy_*` fields

**Files:**
- Modify: `swing/web/view_models/trades.py:1051-1073` (the `DailyManagementTimelineRowVM` dataclass).

- [ ] **Step 1: Append six new optional fields to the dataclass**

Edit the `@dataclass(frozen=True)` block (currently ending at line 1073 with `management_notes: str | None`) to append:

```python
    # Phase 8 V1 polish — Item #1: legacy Phase 7 trade_events surfacing.
    # Populated only on `record_type == 'trade_event_legacy'` rows. None
    # everywhere else (defaulted so existing _record_to_timeline_row call
    # sites construct unchanged).
    trade_event_id: int | None = None
    event_type: str | None = None  # raw trade_events.event_type
    legacy_prior_stop: float | None = None  # decoded from payload_json["old_stop"]
    legacy_new_stop: float | None = None    # decoded from payload_json["new_stop"]
    legacy_rationale: str | None = None     # trade_events.rationale
    legacy_notes: str | None = None         # trade_events.notes
```

Note: Python frozen dataclasses require defaulted fields to come AFTER all required fields. The 19 existing fields are required-positional; the 6 new fields with `= None` defaults append cleanly. If any existing field accidentally lacks a default, this will raise `TypeError: non-default argument follows default argument` at import time — that is a STOP signal, halt + escalate (means the existing dataclass needs reordering, which is out of scope). At time of plan-write the 19 existing fields are all required-positional so the append works.

- [ ] **Step 2: Run import smoke test**

Run: `python -c "from swing.web.view_models.trades import DailyManagementTimelineRowVM; print(DailyManagementTimelineRowVM.__dataclass_fields__.keys())"`
Expected: clean print listing 25 field names (19 existing + 6 new).

- [ ] **Step 3: Run B.1's still-failing test (sanity that the VM extension didn't accidentally fix it)**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py::test_orphan_stop_adjust_surfaces_in_timeline_post_fix -v`
Expected: STILL FAIL — same assertion (the union logic in B.3 is what flips the test).

- [ ] **Step 4: Commit**

```bash
git add swing/web/view_models/trades.py
git commit -m "feat(web): Task B.2 — extend DailyManagementTimelineRowVM with legacy trade_events fields"
```

---

### Task B.3 — Timeline VM: extend `build_daily_management_timeline_vm` with union + dedup

**Files:**
- Modify: `swing/web/view_models/trades.py:1121-1144` (the `build_daily_management_timeline_vm` function).

- [ ] **Step 1: Replace the function body with the union-aware version**

The new body MUST preserve the existing semantics for the daily_management_records branch (still calls `list_for_trade_timeline` with the same args; still returns `None` when trade is missing) and ADD the trade_events union + dedup. Replace the function:

```python
def build_daily_management_timeline_vm(
    *, trade_id: int, cfg: Config,
) -> DailyManagementTimelineVM | None:
    """Build the per-trade timeline VM (spec §7.2 + Phase 8 V1 polish Item #1).

    V1 polish: also surfaces Phase 7 ``trade_events`` rows of
    ``event_type='stop_adjust'`` that have NO corresponding Phase 8
    ``daily_management_records`` row referencing them via
    ``linked_trade_event_id`` (orphans). Dedup rule: a trade_event is an
    orphan iff its ``id`` is NOT in the set of ``linked_trade_event_id``
    values from the trade's event_log records. Orphans render with
    ``record_type='trade_event_legacy'``.

    Returns ``None`` when the trade does not exist.
    """
    from swing.data.repos.daily_management import list_for_trade_timeline
    from swing.data.repos.trades import list_events_for_trade

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None:
                return None
            records = list_for_trade_timeline(conn, trade_id=trade_id)
            events = list_events_for_trade(conn, trade_id=trade_id)
    finally:
        conn.close()

    # Dedup: collect linked_trade_event_id values from event_log records.
    # Snapshots never carry linked_trade_event_id; the predicate also gates
    # on record_type defensively in case repo-layer semantics widen later.
    linked_event_ids = {
        r.linked_trade_event_id for r in records
        if r.record_type == "event_log" and r.linked_trade_event_id is not None
    }

    # Filter trade_events to orphan stop_adjusts (per §0.3 #4 of brief: ONLY
    # event_type='stop_adjust'; entry/exit/partial/review_complete have their
    # own surfaces and are intentionally excluded).
    orphan_stop_adjusts = [
        e for e in events
        if e.event_type == "stop_adjust" and e.id not in linked_event_ids
    ]

    record_rows = [_record_to_timeline_row(r) for r in records]
    orphan_rows = [_orphan_stop_adjust_to_timeline_row(e) for e in orphan_stop_adjusts]

    # Merge + sort by canonical timeline key (review_date ASC, created_at ASC,
    # management_record_id ASC). For orphans, management_record_id is
    # negative (-trade_events.id) per §A.2 — gives deterministic tiebreak
    # without colliding with positive autoincrements.
    merged = sorted(
        record_rows + orphan_rows,
        key=lambda r: (r.review_date, r.created_at, r.management_record_id),
    )

    return DailyManagementTimelineVM(
        trade_id=trade_id, ticker=trade.ticker, rows=tuple(merged),
    )
```

- [ ] **Step 2: Run B.1's failing test**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py::test_orphan_stop_adjust_surfaces_in_timeline_post_fix -v`
Expected: STILL FAIL — at `_orphan_stop_adjust_to_timeline_row` (NameError; helper not yet defined; that's Task B.4).

This is intentional — the failure mode shifts from "logic missing" to "helper missing", giving B.4 a clear next step.

- [ ] **Step 3: Do NOT commit yet — incomplete (helper is referenced but undefined)**

---

### Task B.4 — Helper: `_orphan_stop_adjust_to_timeline_row` with defensive payload decode

**Files:**
- Modify: `swing/web/view_models/trades.py` (insert AFTER the existing `_record_to_timeline_row` definition near line 1118).

- [ ] **Step 1: Add the helper function**

Insert after `_record_to_timeline_row`:

```python
def _orphan_stop_adjust_to_timeline_row(event):
    """Map an orphan Phase 7 ``trade_events`` row of event_type='stop_adjust'
    to the timeline-row VM (Phase 8 V1 polish Item #1).

    Sort-key mapping per plan §A.2:
        review_date           := event.ts[:10]   (YYYY-MM-DD slice of ISO ts)
        created_at            := event.ts        (full ISO timestamp)
        management_record_id  := -event.id       (negative to avoid PK collision)

    Payload decode is DEFENSIVE — the helper never raises on malformed
    payload_json or missing keys; missing values render as None (template
    branch handles None gracefully via `is not none` checks).
    """
    import json

    prior_stop: float | None = None
    new_stop: float | None = None
    try:
        payload = json.loads(event.payload_json) if event.payload_json else {}
    except (json.JSONDecodeError, TypeError):
        payload = {}
    if isinstance(payload, dict):
        old = payload.get("old_stop")
        new = payload.get("new_stop")
        if isinstance(old, (int, float)):
            prior_stop = float(old)
        if isinstance(new, (int, float)):
            new_stop = float(new)

    return DailyManagementTimelineRowVM(
        management_record_id=-event.id,
        record_type="trade_event_legacy",
        review_date=event.ts[:10],
        created_at=event.ts,
        is_superseded=0,  # Phase 7 trade_events have no supersedure semantics.
        mfe_mae_precision_level="",  # Not applicable; template branch ignores.
        # All daily_snapshot/event_log column-group fields stay None on legacy rows:
        current_price=None,
        current_stop=None,
        open_R_effective=None,
        open_MFE_R_to_date=None,
        open_MAE_R_to_date=None,
        maturity_stage=None,
        action_taken=None,
        action_reason=None,
        stop_changed=None,
        prior_stop=None,
        new_stop=None,
        thesis_status=None,
        rule_violation_suspected=None,
        emotional_state=None,
        management_notes=None,
        # Phase 8 V1 polish legacy fields (populated):
        trade_event_id=event.id,
        event_type=event.event_type,
        legacy_prior_stop=prior_stop,
        legacy_new_stop=new_stop,
        legacy_rationale=event.rationale,
        legacy_notes=event.notes,
    )
```

- [ ] **Step 2: Run B.1's test**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py::test_orphan_stop_adjust_surfaces_in_timeline_post_fix -v`
Expected: PASS (B.1 RED → GREEN).

- [ ] **Step 3: Commit B.3 + B.4 together (paired change — VM helper + caller landed in one logical unit)**

```bash
git add swing/web/view_models/trades.py
git commit -m "feat(web): Tasks B.3+B.4 — VM-level union of legacy trade_events orphans into timeline"
```

---

### Task B.5 — Template: branch on `record_type == 'trade_event_legacy'`

**Files:**
- Modify: `swing/web/templates/partials/daily_management_timeline.html.j2`

- [ ] **Step 1: Extend the Type cell with a third branch**

Replace the existing `<td>` Type-cell block (lines 34-41) with:

```jinja
          <td>
            {% if row.record_type == 'daily_snapshot' %}
              <span class="badge badge-snapshot" data-record-type="snapshot">snapshot</span>
              <span class="precision-badge">{{ row.mfe_mae_precision_level }}</span>
            {% elif row.record_type == 'trade_event_legacy' %}
              <span class="badge badge-event-legacy" data-record-type="trade_event_legacy">Stop adjustment (legacy quick-adjust)</span>
            {% else %}
              <span class="badge badge-event" data-record-type="event_log">event</span>
            {% endif %}
          </td>
```

- [ ] **Step 2: Extend the Details cell with a third branch**

Replace the existing `<td>` Details-cell block (lines 43-80) — the existing if/else stays, append a new `elif` branch:

```jinja
          <td>
            {% if row.record_type == 'daily_snapshot' %}
              {%- if row.current_price is not none %}
                price ${{ "%.2f"|format(row.current_price) }};
              {%- endif %}
              {%- if row.current_stop is not none %}
                stop ${{ "%.2f"|format(row.current_stop) }};
              {%- endif %}
              {%- if row.open_R_effective is not none %}
                R {{ "%.2f"|format(row.open_R_effective) }};
              {%- endif %}
              {%- if row.open_MFE_R_to_date is not none %}
                MFE {{ "%.2f"|format(row.open_MFE_R_to_date) }}R;
              {%- endif %}
              {%- if row.open_MAE_R_to_date is not none %}
                MAE {{ "%.2f"|format(row.open_MAE_R_to_date) }}R;
              {%- endif %}
              {%- if row.maturity_stage %}
                <span class="maturity-badge">{{ row.maturity_stage }}</span>
              {%- endif %}
            {% elif row.record_type == 'trade_event_legacy' %}
              {# Phase 7 always writes both old_stop+new_stop together;
                 require BOTH so a half-decoded payload falls back instead
                 of rendering a half transition like "stop $90.00 →". #}
              {% if row.legacy_prior_stop is not none and row.legacy_new_stop is not none %}
                stop ${{ "%.2f"|format(row.legacy_prior_stop) }} → ${{ "%.2f"|format(row.legacy_new_stop) }}
              {% else %}
                <em>stop adjustment details unavailable</em>
              {% endif %}
            {% else %}
              {%- if row.action_taken %}
                <strong>{{ row.action_taken }}</strong>
              {%- endif %}
              {% if row.stop_changed == 1 %}
                — stop
                {%- if row.prior_stop is not none %} ${{ "%.2f"|format(row.prior_stop) }}{%- endif %}
                →
                {%- if row.new_stop is not none %} ${{ "%.2f"|format(row.new_stop) }}{%- endif %}
              {% endif %}
              {%- if row.thesis_status %}
                ; thesis: {{ row.thesis_status }}
              {%- endif %}
              {% if row.rule_violation_suspected == 1 %}
                <span class="badge badge-rule-violation">rule violation</span>
              {% endif %}
            {% endif %}
          </td>
```

- [ ] **Step 2 (continued): Extend the Notes cell with a third branch**

Replace the existing Notes `<td>` block (lines 81-86):

```jinja
          <td>
            {%- if row.record_type == 'event_log' %}
              {%- if row.action_reason %}{{ row.action_reason }}{%- endif %}
              {%- if row.management_notes %}{% if row.action_reason %} — {% endif %}{{ row.management_notes }}{%- endif %}
            {%- elif row.record_type == 'trade_event_legacy' %}
              {%- if row.legacy_rationale %}{{ row.legacy_rationale }}{%- endif %}
              {%- if row.legacy_notes %}{% if row.legacy_rationale %} — {% endif %}{{ row.legacy_notes }}{%- endif %}
            {%- endif %}
          </td>
```

- [ ] **Step 3: Add a discriminating template-render test**

Append to `tests/web/test_daily_management_timeline_legacy_union.py`:

```python
def test_orphan_stop_adjust_renders_label_in_trade_detail_page(cfg_with_db):
    """Discriminating test for the template branch:

    Pre-fix expectation (no template branch): the literal string "stop adjustment
    (legacy quick-adjust)" is absent from the trade-detail HTML even when an
    orphan trade_event exists.
    Post-fix expectation: the label appears in the timeline section AND the
    decoded prior_stop → new_stop dollar amounts render."""
    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        _insert_orphan_stop_adjust(
            conn, trade_id=1,
            ts="2026-05-05T10:30:00",
            old_stop=90.0, new_stop=95.0,
            rationale="trail-up to entry+5",
            notes=None,
        )
    finally:
        conn.close()

    app = create_app(cfg)
    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    body = response.text
    assert 'id="daily-management-timeline"' in body
    timeline_html = (
        body.split('id="daily-management-timeline"')[1].split("</section>")[0]
    )
    assert "Stop adjustment (legacy quick-adjust)" in timeline_html
    assert "$90.00" in timeline_html
    assert "$95.00" in timeline_html
    assert "trail-up to entry+5" in timeline_html
```

- [ ] **Step 4: Run the new + existing tests**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py -v tests/web/test_daily_management_timeline.py -v`
Expected: All pass — orphan tests green AND existing Phase 8 timeline tests still green (template additions don't regress the existing branches).

- [ ] **Step 5: Commit**

```bash
git add swing/web/templates/partials/daily_management_timeline.html.j2 tests/web/test_daily_management_timeline_legacy_union.py
git commit -m "feat(web): Task B.5 — render legacy stop-adjust orphan rows in timeline template"
```

---

### Task B.6 — Discriminating test: orphan AND non-orphan stop_adjusts together

**Files:**
- Modify: `tests/web/test_daily_management_timeline_legacy_union.py`

- [ ] **Step 1: Append the test**

```python
def test_dedup_linked_stop_adjust_does_not_double_appear(cfg_with_db):
    """Discriminating test for the dedup rule:

    Setup: insert a Phase 7 stop_adjust trade_event (id=E) AND a Phase 8
    event_log row whose `linked_trade_event_id = E`.

    Pre-fix expectation (no dedup): the trade_event surfaces as a
    'trade_event_legacy' row AND the event_log row also renders → operator
    sees TWO rows describing the same stop change.
    Post-fix expectation: only the event_log row surfaces (canonical Phase 8
    audit row); the trade_event is suppressed by the linked_event_ids set."""
    from swing.data.repos.daily_management import insert_event_log

    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        event_id = _insert_orphan_stop_adjust(
            conn, trade_id=1,
            ts="2026-05-05T10:30:00",
            old_stop=90.0, new_stop=95.0,
            rationale="trail-up",
        )
        # The matching Phase 8 event_log row referencing this trade_event:
        insert_event_log(
            conn, trade_id=1,
            event_log_fields={
                "review_date": "2026-05-05",
                "data_asof_session": "2026-05-05",
                "created_at": "2026-05-05T10:30:00",
                "mfe_mae_precision_level": "daily_approximate",
                "stop_changed": 1,
                "prior_stop": 90.0,
                "new_stop": 95.0,
                "linked_trade_event_id": event_id,
                "stop_change_reason": "trail-up",
                "action_taken": "move_stop",
                "rule_violation_suspected": 0,
                "emotional_state": "[]",
            },
        )
    finally:
        # `insert_event_log` docstring (`swing/data/repos/daily_management.py`)
        # explicitly defers transaction control to the caller. Commit BEFORE
        # close — sqlite3 rolls back uncommitted work on connection close, so
        # without this the dedup setup row vanishes and the test no longer
        # discriminates the dedup logic.
        conn.commit()
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    legacy_rows = [r for r in vm.rows if r.record_type == "trade_event_legacy"]
    event_log_rows = [r for r in vm.rows if r.record_type == "event_log"]
    assert legacy_rows == [], (
        f"linked stop_adjust should be deduped; got {len(legacy_rows)} legacy rows"
    )
    assert len(event_log_rows) == 1
    assert event_log_rows[0].new_stop == 95.0
    assert event_log_rows[0].prior_stop == 90.0
```

- [ ] **Step 2: Run + commit**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py::test_dedup_linked_stop_adjust_does_not_double_appear -v`
Expected: PASS.

```bash
git add tests/web/test_daily_management_timeline_legacy_union.py
git commit -m "test(web): Task B.6 — assert linked stop_adjust dedups against event_log row"
```

---

### Task B.7 — Discriminating test: non-stop_adjust event types stay excluded

**Files:**
- Modify: `tests/web/test_daily_management_timeline_legacy_union.py`

- [ ] **Step 1: Append the test**

```python
def test_non_stop_adjust_trade_events_do_not_appear_in_timeline(cfg_with_db):
    """Discriminating test for the event_type filter (per locked design §0.3 #4):

    Insert orphan trade_events of representative non-stop_adjust event_types
    that exist in the production CHECK constraint enum: 'entry', 'exit',
    'note', 'flag'. Lifecycle events (entry/exit) have their own UI surfaces
    (dashboard row, exit form) and MUST NOT also surface in the timeline.

    Pre-fix expectation (had we shipped a too-wide filter `event_type IN
    ('stop_adjust','entry','exit','note','flag')`): all four orphans appear.
    Post-fix expectation: ONLY stop_adjust orphans surface; entry/exit/note/
    flag rows are absent from the timeline."""
    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        # Insert representative orphans across the lifecycle + audit
        # event_type space. Raw INSERT bypasses Phase 7 service-layer guards
        # (which would reject e.g. an 'entry' on an already-entered trade) —
        # appropriate here because the test is a READ-side filter check, not
        # a write-side state-machine check.
        # Cover the full CHECK enum minus 'stop_adjust' (per Phase 7
        # migration 0014: entry/stop_adjust/note/exit/flag/pre_trade_edit).
        for ts, event_type, payload in [
            ("2026-05-05T11:00:00", "entry",          '{"shares":50,"price":100.0}'),
            ("2026-05-05T11:30:00", "exit",           '{"shares":50,"price":105.0}'),
            ("2026-05-05T12:00:00", "note",           '{"note":"NOTE_MARKER"}'),
            ("2026-05-05T12:30:00", "flag",           '{"flag":"FLAG_MARKER"}'),
            ("2026-05-05T13:00:00", "pre_trade_edit", '{"field":"thesis"}'),
        ]:
            conn.execute(
                "INSERT INTO trade_events "
                "(trade_id, ts, event_type, payload_json, rationale, notes) "
                "VALUES (1, ?, ?, ?, NULL, NULL)",
                (ts, event_type, payload),
            )
        conn.commit()
    finally:
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    assert vm.rows == (), (
        "Non-stop_adjust trade_events must NOT surface in the timeline; "
        f"got {len(vm.rows)} unexpected rows: "
        f"{[r.record_type for r in vm.rows]}"
    )
```

- [ ] **Step 2: Run + commit**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py::test_non_stop_adjust_trade_events_do_not_appear_in_timeline -v`
Expected: PASS.

```bash
git add tests/web/test_daily_management_timeline_legacy_union.py
git commit -m "test(web): Task B.7 — assert event_type filter excludes note/flag trade_events"
```

---

### Task B.8 — Discriminating test: chronological sort across mixed row sources

**Files:**
- Modify: `tests/web/test_daily_management_timeline_legacy_union.py`

- [ ] **Step 1: Append the test**

```python
def test_timeline_orders_legacy_orphan_chronologically_with_dmr_rows(cfg_with_db):
    """Discriminating test for the merged sort order:

    Insert (in scrambled insertion order):
      - daily_snapshot for 2026-05-04 (created_at 2026-05-04T16:00:00)
      - orphan stop_adjust for 2026-05-05 (ts 2026-05-05T10:30:00)
      - event_log for 2026-05-06 (created_at 2026-05-06T09:00:00)

    Pre-fix expectation (had we appended orphans without sorting): they'd
    appear at the end of the rows list regardless of date.
    Post-fix expectation: rows ordered chronologically ascending — snapshot
    (4th), orphan (5th), event_log (6th)."""
    from swing.data.repos.daily_management import insert_event_log, insert_snapshot

    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        # Snapshot first chronologically:
        insert_snapshot(
            conn, trade_id=1,
            snapshot_fields={
                "review_date": "2026-05-04",
                "data_asof_session": "2026-05-04",
                "created_at": "2026-05-04T16:00:00",
                "mfe_mae_precision_level": "daily_approximate",
                "pipeline_run_id": None,
                "current_price": 110.0, "current_stop": 95.0,
                "current_size": 50.0, "current_avg_cost": 100.0,
                "open_R_effective": 1.0,
                "open_MFE_R_to_date": 1.5, "open_MAE_R_to_date": 0.2,
                "intraday_high": 111.0, "intraday_low": 109.0,
                "position_capital_utilization_pct": 0.15,
                "position_capital_denominator_dollars": 7500.0,
                "position_portfolio_heat_contribution_dollars": 50.0,
                "maturity_stage": "+1.5R_to_+2R",
                "trail_MA_candidate_price": 105.0,
                "trail_MA_period_days": 21,
                "trail_MA_eligibility_flag": 0,
            },
        )
        # Orphan in the middle:
        _insert_orphan_stop_adjust(
            conn, trade_id=1,
            ts="2026-05-05T10:30:00",
            old_stop=90.0, new_stop=95.0,
        )
        # Event_log last chronologically:
        insert_event_log(
            conn, trade_id=1,
            event_log_fields={
                "review_date": "2026-05-06",
                "data_asof_session": "2026-05-06",
                "created_at": "2026-05-06T09:00:00",
                "mfe_mae_precision_level": "daily_approximate",
                "stop_changed": 0,
                "action_taken": "hold",
                "rule_violation_suspected": 0,
                "emotional_state": "[]",
            },
        )
    finally:
        # See B.6 fix: insert_snapshot/insert_event_log defer commit to caller.
        conn.commit()
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    assert len(vm.rows) == 3
    types_in_order = [r.record_type for r in vm.rows]
    assert types_in_order == [
        "daily_snapshot", "trade_event_legacy", "event_log",
    ], f"got order: {types_in_order}"
```

- [ ] **Step 2: Run + commit**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py::test_timeline_orders_legacy_orphan_chronologically_with_dmr_rows -v`
Expected: PASS.

```bash
git add tests/web/test_daily_management_timeline_legacy_union.py
git commit -m "test(web): Task B.8 — assert chronological merge across snapshot/orphan/event_log"
```

---

### Task B.9 — Discriminating test: defensive payload decode (malformed JSON)

**Files:**
- Modify: `tests/web/test_daily_management_timeline_legacy_union.py`

- [ ] **Step 1: Append the test**

```python
def test_orphan_with_malformed_payload_renders_with_none_stops(cfg_with_db):
    """Discriminating test for the defensive payload decoder:

    Insert an orphan trade_event with a malformed payload_json (not valid
    JSON).

    Pre-fix expectation (had we used `json.loads(...)` without try/except):
    the VM build raises JSONDecodeError and the trade-detail page 500s.
    Post-fix expectation: the row appears with `legacy_prior_stop is None
    and legacy_new_stop is None` (decoder swallows the malformed payload),
    and the page renders 200."""
    cfg, db_path = cfg_with_db
    conn = connect(db_path)
    try:
        _seed_trade(conn, trade_id=1, ticker="DHC", current_stop=95.0)
        conn.execute(
            "INSERT INTO trade_events "
            "(trade_id, ts, event_type, payload_json, rationale, notes) "
            "VALUES (1, '2026-05-05T10:30:00', 'stop_adjust', "
            " 'this is not json', 'trail-up', NULL)",
        )
        conn.commit()
    finally:
        conn.close()

    vm = build_daily_management_timeline_vm(trade_id=1, cfg=cfg)
    assert vm is not None
    assert len(vm.rows) == 1
    row = vm.rows[0]
    assert row.record_type == "trade_event_legacy"
    assert row.legacy_prior_stop is None
    assert row.legacy_new_stop is None
    assert row.legacy_rationale == "trail-up"

    app = create_app(cfg)
    with TestClient(app) as client:
        response = client.get("/trades/1")
    assert response.status_code == 200
    # Template fallback: with both legacy stops None, the row renders the
    # fallback marker rather than a dangling "stop  →" transition.
    assert "stop adjustment details unavailable" in response.text
```

- [ ] **Step 2: Run + commit**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py::test_orphan_with_malformed_payload_renders_with_none_stops -v`
Expected: PASS.

```bash
git add tests/web/test_daily_management_timeline_legacy_union.py
git commit -m "test(web): Task B.9 — defensive payload decode for malformed trade_events"
```

---

### Task Z.1 — Full fast suite

- [ ] **Step 1: Run the entire fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: pre-dispatch baseline 2080 → 2090 passing (+10 new tests landed across A.1, A.3, A.4, B.1, B.5, B.6, B.7, B.8, B.9 + the 1 RED→GREEN flip on B.1; no skips added; no regressions).

If the count is below 2090, halt + escalate. If a non-new test fails, that's a regression — investigate before declaring done.

- [ ] **Step 2: Verify the previously-RED B.1 test is now GREEN**

Run: `python -m pytest tests/web/test_daily_management_timeline_legacy_union.py -v`
Expected: 6 PASS (one per Task B.1, B.5, B.6, B.7, B.8, B.9).

---

### Task Z.2 — Ruff baseline preserved

- [ ] **Step 1: Run ruff against `swing/`**

Run: `ruff check swing/`
Expected: 78 errors (the pre-dispatch baseline — UNCHANGED). The plan's edits MUST NOT introduce new violations AND MUST NOT incidentally fix baseline violations (per project convention on baseline preservation).

If new violations appear (`> 78`), fix them inline (the plan's code samples are already ruff-compliant; any new violation is a typo or accidental import). If baseline drops (`< 78`), revert the incidental fix.

- [ ] **Step 2: Run ruff against `tests/`**

Run: `ruff check tests/web/test_dashboard_detail_button.py tests/web/test_daily_management_timeline_legacy_union.py`
Expected: 0 violations on the two new test files.

---

### Task Z.3 — Manual operator-witnessed verification gate

This task is OPERATOR-FACING (the dispatch agent does NOT run the dev server; the operator runs the gate after the dispatch returns). The dispatch agent ONLY documents the gate in the return report. The acceptance criteria below are also restated in §D.

**Gate steps the operator will perform:**

1. **Surface 1 (Detail button):** Run `swing web` (the dashboard server). Visit `http://127.0.0.1:8080/`. Verify the open-positions table shows a "Detail" link/button on every row. Click it. Verify the URL changes to `/trades/{id}` and the trade-detail page renders fully (Pre-Trade Decision section + Daily Management Timeline section + event-log form).
2. **Surface 2 (Timeline union):** On the trade-detail page for any trade with a Phase 7 stop_adjust history (DHC qualifies per CLAUDE.md production state), confirm the Daily Management Timeline section shows ANY pre-Phase-8 stop adjustments labelled "Stop adjustment (legacy quick-adjust)" interleaved chronologically with Phase 8 daily snapshots and event_logs.
3. **Surface 3 (Dedup):** If the operator submits a Phase 8 event_log entry that includes a stop change (which Phase 8's `record_event_log` writes WITH `linked_trade_event_id` populated), verify the resulting trade_events row does NOT also appear as a "(legacy quick-adjust)" row in the timeline — only the Phase 8 event_log row renders for that change.

If the operator reports any of these surfaces failing, the dispatch is NOT complete; reopen the relevant Task B.x with a discriminating regression test.

---

## §D — Acceptance criteria (summary)

- [ ] `python -m pytest -m "not slow" -q` shows ~2090 passing (was 2080); no new skips; no regressions in existing tests.
- [ ] `ruff check swing/` shows 78 violations (baseline preserved).
- [ ] `ruff check tests/web/test_dashboard_detail_button.py tests/web/test_daily_management_timeline_legacy_union.py` shows 0 violations.
- [ ] Dashboard open-positions row template emits `<a href="/trades/{id}" class="row-action-link" onclick="event.stopPropagation()">Detail</a>` per row.
- [ ] `build_daily_management_timeline_vm` unions Phase 7 orphan stop_adjust trade_events into the timeline VM.
- [ ] Dedup rule: orphan iff `trade_events.id NOT IN {linked_trade_event_id from event_log records}` for the same trade.
- [ ] Event-type filter: ONLY `event_type == 'stop_adjust'` orphans surface; entry/exit/partial/note/flag/review_complete do NOT.
- [ ] Sort order canonical `(review_date ASC, created_at ASC, management_record_id ASC)` with orphans using `-trade_events.id` for the tiebreak.
- [ ] Template renders the literal label "Stop adjustment (legacy quick-adjust)" + decoded prior_stop → new_stop transition + rationale + notes; renders the literal fallback "stop adjustment details unavailable" when both `legacy_prior_stop` and `legacy_new_stop` are `None`.
- [ ] Defensive payload decode: malformed `payload_json` does NOT crash the VM build; missing keys yield `None` cell values.
- [ ] Schema version unchanged (`EXPECTED_SCHEMA_VERSION == 16`); no migration runs; no new repo functions; no new service-layer functions.
- [ ] Operator-witnessed verification gate (Z.3 surfaces 1, 2, 3) PASS.

---

## §E — Operator-witnessed verification gate (binding)

Per Phase 5/6/7/8 precedent (JS-test-harness gap lesson family — TestClient assertions verify response body, NOT browser DOM behavior), the operator-witnessed gate is BINDING for HTMX-driven UX work AND for navigation-link work where TestClient does not follow redirects/links.

The gate enumerated in §C Z.3 is the canonical operator-facing checklist. The dispatch agent's return report MUST flag the gate as PENDING (operator runs it) or PASSED (operator confirms post-merge).

---

## §F — Out of scope

- Changing the legacy `/trades/{id}/stop` route to also write a Phase 8 event_log row (deferred — orchestrator may revisit if operator wants audit-chain symmetry).
- Surfacing `entry`/`exit`/`partial`/`note`/`flag`/`review_complete` trade_events in the timeline (per locked design §0.3 #4).
- Backfilling existing orphan trade_events into Phase 8 event_log via migration (the union renders them live; backfill would be redundant + write-amplify).
- Visual styling polish beyond a minimal "Detail" link + "(legacy quick-adjust)" label.
- emotional_state form stale checkbox state (Phase 8 V1 follow-up #3 — separate dispatch).
- Spec wording GAP-FLAGGED vs gap-by-absence (Phase 8 V1 follow-up #4 — cosmetic deferred).
- Adding a CSS `.row-action-link` style rule (the class exists for future styling; no CSS file is modified in this dispatch).
- Adding a `data-trade-event-id` attribute to the template row (tests differentiate orphans via `data-record-type="trade_event_legacy"`).

---

## §G — Risks + mitigations

| Risk | Mitigation |
|---|---|
| Sort key non-determinism when an orphan trade_events.ts equals a daily_management_records.created_at to the second | Negative-id tiebreak per §A.2 — orphans always sort before dmr rows in the same `(review_date, created_at)` bucket. Discriminating test B.8 covers chronological order across distinct dates; same-second ties are deterministic by sign-of-id and acceptable per design lock. |
| `DailyManagementTimelineRowVM` field append order breaks frozen-dataclass construction | Plan §A.5 documents required-vs-defaulted field ordering. Task B.2 Step 2 includes a pre-flight `python -c "..."` import smoke test to catch ordering breakage before downstream tasks proceed. |
| Operator confusion between "(legacy quick-adjust)" rows and Phase 8 event_log rows in the timeline | The badge text is explicit ("legacy quick-adjust") + the row carries `data-record-type="trade_event_legacy"` for any future CSS theming. Phase 8 V2 may introduce an audit-chain-symmetry option that converts legacy rows in-place via `linked_trade_event_id` backfill. |
| Defensive payload decode silently masks a real bug (e.g., a future Phase 7 hotfix renames `old_stop` to something else and the helper returns `None` everywhere) | The defensive decode does NOT raise but it DOES log nothing — a future maintainer renaming the payload key would silently break the rendered prior_stop → new_stop. Mitigation: B.1's discriminating assertion `row.legacy_prior_stop == 90.0` AND `row.legacy_new_stop == 95.0` would catch a rename that breaks the existing key extraction; CI would fail. The defensive layer ONLY masks malformed-data rows from breaking the page, not key renames. |
| Detail anchor href collides with browser default styling differences across themes | The anchor uses `class="row-action-link"`; styling is not in scope. Tests assert behavior (href + propagation), not visual rendering. Operator can flag visual polish as a separate follow-up. |
| Existing `test_timeline_orders_chronologically_with_tiebreak` (Phase 8 ship) breaks because the merge sort changed semantics | The merge sort with the canonical key MATCHES the existing repo-side ORDER BY. Same-day same-second event_log rows rendered in `management_record_id ASC` previously; they still render in `management_record_id ASC` after the merge (orphans only enter when `record_type == 'trade_event_legacy'`; the existing test inserts only event_log rows, so no orphans, so no behavior change). Z.1 verifies no regression. |

---

## §H — Notes for the executing agent

- **TDD discipline:** strict per-task RED → GREEN → COMMIT cycle. B.1's RED state persists until B.4 lands (B.2 + B.3 keep it RED but shift the failure mode from "logic missing" to "helper missing").
- **No `git add -A`:** per Phase 8 R1 Critical 1 lesson — explicit `git add <path>` per commit. The plan's commit blocks list paths verbatim.
- **Marker-file workflow:** the orchestrator manages `.copowers-subagent-active` creation/removal; the executing agent does NOT touch it.
- **Plan-template fixture defects:** if a fixture helper has a different shape than the plan template assumes (e.g., `_minimal_event_log_fields` requires keys not listed), correct inline + flag in return report per Phase 6/8 lesson; do NOT halt unless the defect blocks an entire task family.
- **HEAD at dispatch start:** `188d1ea` (verify via `git rev-parse main`).
- **Branch:** worktree-isolated branch off `main` (suggested name: `phase8-v1-polish`; per `superpowers:using-git-worktrees`).
