# Watchlist Pin + Hypothesis-Labeling Effectiveness — Design Spec (Phase 16 / Arc 7)

**Phase:** copowers:brainstorming (design only — do NOT implement).
**Authored:** 2026-06-10. **Commission:** `docs/phase16-watchlist-pin-and-labeling-effectiveness-commissioning-brief.md`
(read its dated **AMENDMENT 2026-06-10** block FIRST — it supersedes parts of R2/R4 and carries the research-director
QA rulings this spec is written to). **Dispatch:** `docs/arc7-watchlist-pin-labeling-brainstorming-dispatch-brief.md`.
**Branch-from:** main HEAD `0ff853e9` (the amendment `0b1e37bd` is in this base).

**Plugs into / amends:** `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md` §3.2 + §5.1
(the opt-in containment design). This arc adds a dated **§ADDENDUM** to that spec (drafted verbatim in §13 below) —
a dated section, NOT a rewrite. The frozen `hypothesis_registry` row (migration `0026`) is UNTOUCHED.

---

## 1. Problem & mandate

The hypothesis-labeling workflow is not effective end-to-end in the operator's web-first workflow, for two coupled
reasons:

1. **Watchlist names cannot be retained.** A qualifying ticker ages off after `AGING_STREAK_THRESHOLD` (3) consecutive
   stable-criteria failures (`swing/watchlist/service.py:127-135`), and a ticker that leaves the finviz screen
   entirely is dropped from evaluation (`service.py:70` `if candidate is None: continue`). The operator has no way to
   say "keep tracking this name — it's a future candidate I'm watching" independent of the screen.
2. **Web-entered watch trades persist `hypothesis_label = NULL`.** The entry-form label is server-stamped via
   `lookup_active_recommendation_label`, whose matcher call uses the default `include_baseline=False`
   (`hypothesis_prefill.py:55`) → it can never produce `Broad-watch baseline` → the dominant watch population (the
   operator's actual practice: 12 of 16 live trades were watch) saves no hypothesis attribution.

**Mandate (one line):** a per-ticker **watchlist pin** that keeps a ticker actively fetched + evaluated + retained
until the operator unpins it (blocks the age-off removal; the screen no longer gates membership), plus the
**matcher-driven auto-label** so web/CLI entry prefill yields the narrow label when a narrow cohort matches, else
`Broad-watch baseline (watch); failed: …` for watch candidates — under the R6 lock set, with the 0026-spec addendum.

This arc does NOT add a tag store, a sort-by-tags feature, a post-hoc label editor, a new metrics surface, or any
registry / matcher-gate / tier / measurement-chain change (R6). **Labels are NEVER driven by pins/tags** — they mirror
shadow attribution (operator decision).

---

## 2. Binding requirements (commission §1 + AMENDMENT 2026-06-10)

- **R1** — per-ticker `pinned` flag + optional `pin_note` (+ `pinned_at` audit timestamp), set/clear from the web GUI.
  Additive migration on `watchlist`; `swing/data` carve-out scoped to schema + repo column plumbing.
- **R2 (amended)** — the pin keeps the ticker **actively fetched and fully evaluated** every nightly run (it is unioned
  into the `_step_evaluate` universe), and **blocks the age-off removal**. Streak counting + requalification continue
  exactly as today; on unpin, accumulated state takes effect at the next nightly run (no mid-session retroactive
  removal). The original "stale-display for an absent pinned ticker" framing is SUPERSEDED — a pinned ticker is never
  absent. Pinned rows are visibly badged.
- **R3** — the matcher-driven auto-label: the entry-form/CLI prefill passes `include_baseline=True`. Result: narrow
  label when a narrow cohort matches (the two-phase gate gives narrow-first structurally), else
  `Broad-watch baseline (watch); failed: …` for watch-bucket candidates, `None` otherwise.
- **R4 (amended)** — population visibility: a per-row cohort hint on the watchlist page (narrow name | `broad-watch` |
  none), computed at render via the matcher with `include_baseline=True` (the SECOND production opt-in site).
- **R5** — the soft-warn confirm + `force=true` round-trips the new prefill VALUE (hidden-anchor family).
- **R6 locks** — registry rows; matcher two-phase gate + the dashboard call sites' `include_baseline=False` default;
  `swing/metrics/tier.py` + deviation allowlist; the shadow engine + temporal log + measurement chain; the 16
  historical trade labels; `mistake_tags`/`process_grade` — ALL untouched. The persisted label matches
  `Broad-watch baseline` under `swing/metrics/label_match.py`'s 3-rule contract.

**Research-director riders (AMENDMENT, binding):** (a) `_step_evaluate` carve-out APPROVED; (b) cohort-hint opt-in
APPROVED with the two-site addendum + the call-site inventory guard test; (c) measurement-universe ACCEPTED with the
universe-composition note + a per-run pin-injection audit line; (d) the delisted/unfetchable pinned-ticker edge must
route through F6 without blanking the row.

---

## 3. Architecture overview

Five units, each independently testable, communicating through existing well-defined interfaces:

| Unit | File(s) | Responsibility | Depends on |
|---|---|---|---|
| **Schema + models + repo** | `migrations/00NN_*.sql`, `data/models.py`, `data/repos/watchlist.py`, `data/db.py` | persist `pinned`/`pin_note`/`pinned_at`; preserve them across nightly upserts; a `set_watchlist_pin` writer | sqlite |
| **Pin-veto service** | `watchlist/service.py` | PURE — given `pinned_tickers`, divert would-be removes into `streak_increments` + a `suppressed_removes` audit lane | models |
| **Universe injection** | `pipeline/runner.py:_step_evaluate`, `_step_watchlist` | union pinned tickers into the fetch+eval universe; pass `pinned_tickers` to the service; emit the pin-injection + suppressed-remove audit lines | repo, service |
| **Auto-label opt-in** | `recommendations/hypothesis_prefill.py` | flip the prefill matcher call to `include_baseline=True` (opt-in site #1) | matcher (unchanged) |
| **Web pin UI + cohort hint** | `web/view_models/watchlist.py`, `web/routes/watchlist.py`, `templates/partials/watchlist_*.j2` | expanded-row pin form; compact-row badge; per-row cohort hint via the matcher (opt-in site #2) | VM, matcher |

The matcher (`recommendations/hypothesis.py`) and its `include_baseline` two-phase gate already exist (shipped at
migration 0026) — this arc adds **no** matcher logic, only two new opt-in *callers* plus a guard test bounding the
opt-in set.

---

## 4. Schema (additive — `watchlist`, migration number taken at executing-branch time)

```sql
-- Migration 00NN: watchlist pin (Arc 7). ADDITIVE columns only — no table
-- rewrite, no change to existing rows. Explicit BEGIN;...COMMIT; per gotcha #9
-- (_apply_migration runs executescript in autocommit; 0023-0026 all wrap).
BEGIN;
ALTER TABLE watchlist ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1));
ALTER TABLE watchlist ADD COLUMN pin_note TEXT;
ALTER TABLE watchlist ADD COLUMN pinned_at TEXT;
UPDATE schema_version SET version = NN;
COMMIT;
```

- **Number:** the next free at executing-branch time. Latest on disk is `0026`; the P0 tuition-vs-error arc
  (at writing-plans/executing in the research-director lane) will likely take `0027` → **expect this arc at `0028`**.
  Whatever number lands re-runs the #11 version-pin sweep (the 0025/0026 precedent is the playbook).
- **`pin_note`** nullable TEXT; the web handler applies `... or None` so an empty textarea persists `NULL` (CHECK/
  nullability family). **`pinned_at`** ISO-8601 TEXT, server-stamped on pin, set to `NULL` on unpin.
- **`db.py`:** `EXPECTED_SCHEMA_VERSION` bumps to `NN`. Add `_arc7_watchlist_pin_backup_gate` (registered in
  `run_migrations`) mirroring `_phase16_backup_gate`'s **STRICT equality** shape — fires ONLY when
  `current_version == NN-1 AND target_version >= NN` (NOT `<=`; multi-version jumps are separate two-step migrations).
  Expected-tables constant = the prior version's table set (this migration adds **no** table, so the post-migration
  table set equals the pre-migration set; the gate verifies the snapshot has the expected prior-version tables).
- **Migrate-twice no-op test:** apply 00NN twice → second run is a version-gate short-circuit (`current >= target`);
  asserts the columns exist exactly once and values are unchanged. Per `feedback_regression_test_arithmetic`, the
  backup-gate test computes the fire/no-fire condition under both `current==NN-1` and `current==NN`.

### 4.1 Model + repo plumbing (#11 — same task as the schema)

- `WatchlistEntry` (`data/models.py:380`) gains `pinned: bool = False`, `pin_note: str | None = None`,
  `pinned_at: str | None = None` (defaults → existing construction sites in the service compile unchanged; the service
  explicitly threads them, §6).
- `_row_to_entry`, `list_active_watchlist`, `get_watchlist_entry` (`repos/watchlist.py`) SELECT + map the three new
  columns. (Read-path + write-path widened in the SAME task — #11.)
- **`upsert_watchlist_entry`:** the INSERT column-list gains the three columns (fresh adds write explicit
  `0`/`NULL`/`NULL`); the **`ON CONFLICT(ticker) DO UPDATE SET` list EXCLUDES all three** — they are operator-owned and
  preserved across nightly upserts, identical to the FROZEN `entry_target`/`initial_stop_target` treatment. A
  regression test pins a ticker, runs a nightly upsert (requalify + streak_increment), and asserts `pinned`/`pin_note`/
  `pinned_at` survive unchanged.
- **New writer `set_watchlist_pin(conn, ticker, *, pinned, pin_note, pinned_at)`** — a targeted `UPDATE watchlist SET
  pinned=?, pin_note=?, pinned_at=? WHERE ticker=?` with a SELECT-first existence check that raises
  `WatchlistEntryNotFoundError` when the ticker is not on the active watchlist (an audit-honest writer; you cannot pin
  a row that isn't there). Caller wraps in `with conn:`.

---

## 5. Universe injection — pinned tickers stay fresh (`_step_evaluate`)

The operator-confirmed model (AMENDMENT §1): the evaluated universe becomes **screen ∪ pinned (∪ held)**.

At the established held-ticker injection seam (`runner.py:1389-1400`), after `held_tickers` is unioned into `tickers`,
union the **pinned watchlist tickers** as well:

```python
pin_conn = connect(cfg.paths.db_path)
try:
    pinned_tickers = sorted({
        e.ticker.upper() for e in list_active_watchlist(pin_conn) if e.pinned
    })
finally:
    pin_conn.close()
injected_pins = [t for t in pinned_tickers if t not in seen]
for t in injected_pins:
    tickers.append(t)
    seen.add(t)
```

**Key difference from held tickers:** held positions are added to `excluded` (`runner.py:1481`) → routed to
`bucket='excluded'` (close fetched, NOT evaluated). Pinned tickers are **NOT** added to `excluded` → they flow through
the `contexts` loop (`runner.py:1484-1494`) into `evaluate_batch` and get **real criteria / bucket / streak** every
night. (A pinned ticker that is ALSO an open trade stays `excluded` — held status wins; it is already retained by the
open-trade injection. A pinned ticker on the ETF blocklist similarly stays excluded — do not override the blocklist.)

**Quota / scope:** the OHLCV fetch loop (`runner.py:1433`) already iterates the full finviz screen (hundreds of
tickers); a handful of pinned additions is negligible and trips no breaker. **`build_dashboard`'s OHLCV scope is
NOT touched** — the "open-trade tickers ONLY" gotcha stands; this injection is confined to `_step_evaluate`.

**Per-run pin-injection audit line (rider c-ii):** when `injected_pins` is non-empty, emit a `warnings_json` /
`pipeline.log` line via the existing `run_warnings` channel listing the count + symbols (e.g.
`{"step":"evaluate","kind":"pin_injection","count":3,"tickers":["ABCD","EFGH","IJKL"]}`) so screen-vs-pin provenance is
decomposable from run logs. No schema. A pinned ticker already in the finviz screen is NOT "injected" (it's
screen-native) and is not listed — only the off-screen additions are.

### 5.1 Delisted / unfetchable pinned ticker (rider d — Codex probe target)

A pinned ticker whose fetch fails goes to `error_tickers` (`runner.py:1440-1441`) and is appended as a `bucket='error'`
candidate (`runner.py:1514-1521`). It is therefore **present** in `today_candidates` (not absent) → flows through
`compute_watchlist_changes` → `_stable_passes` is False on empty criteria → not-qualifies → streak increments (or, at
threshold, the pin-veto path, §6) → **the watchlist row is retained, never blanked**. The existing F6 write-through
discipline (`ohlcv_archive.py`: empty external result is transient, never overwrites cached content) means a transient
empty fetch does not blank the archive. The web row renders a small "data unavailable" / degraded indicator for an
`error`-bucket pinned ticker (§9), and the pin-injection + error are visible in the run warnings. The pin holds the
row; the operator unpins manually if the name is genuinely dead.

---

## 6. Pin-veto seam — `compute_watchlist_changes` stays PURE

Signature gains a keyword-only `pinned_tickers: frozenset[str] = frozenset()` (default empty → existing callers /
tests unaffected). `WatchlistDelta` gains a `suppressed_removes: list[WatchlistArchiveEntry] = field(default_factory=
list)` audit lane (built from the same shape the real `removes` would have used, for trace fidelity).

In the not-qualifies branch (`service.py:123-150`), when `new_streak >= AGING_STREAK_THRESHOLD`:

```python
if new_streak >= AGING_STREAK_THRESHOLD:
    if ticker in pinned_tickers:
        # Pin vetoes the age-off. Keep the streak HONEST (R2: streak counting
        # continues) by persisting the incremented streak via a streak_increment
        # rather than freezing it, AND record the suppression for audit.
        delta.suppressed_removes.append(WatchlistArchiveEntry(... new_streak ...))
        delta.streak_increments.append(WatchlistEntry(... not_qualified_streak=new_streak,
                                                      pinned=True, pin_note=existing.pin_note,
                                                      pinned_at=existing.pinned_at ...))
    else:
        delta.removes.append(WatchlistArchiveEntry(... new_streak ...))
else:
    delta.streak_increments.append(WatchlistEntry(... pinned=existing.pinned ...))
```

Consequences (all tested):
- **Streak keeps incrementing past the threshold** while pinned (operator's Q2 choice): the pinned ticker accrues
  `streak = 3, 4, 5, …` as `streak_increments` rows, never a `removes` row.
- **On unpin**, the next nightly sees `pinned=False` (the operator cleared it) and `streak >= 3` → the normal `removes`
  path fires → **immediate age-off** ("accumulated state takes effect at the next nightly run").
- The pin fields are **threaded through** every `WatchlistEntry` the service constructs (adds → `pinned=False`;
  requalifies / streak_increments → copied from `existing`) so a requalify or streak_increment never silently clears a
  pin. (Belt-and-suspenders: the upsert's DO-UPDATE excludes the pin columns anyway, §4.1 — so even an unthreaded value
  could not clobber the DB. Both defenses hold.)

The service remains a pure function on `(prior, today_candidates, data_asof_date, pinned_tickers)` — no DB, no I/O.

### 6.1 #27 audit — warnings, not a phantom archive

A suppressed removal is **not** a removal. Writing it to `watchlist_archive` would DELETE the live row (the archive
writer deletes-then-inserts, `repos/watchlist.py:79`) — exactly the wrong outcome. So `_step_watchlist` does NOT
archive suppressed removes; instead it emits a `warnings_json` run-warning per suppressed ticker (ticker + streak +
`"pin prevented age-off"`), satisfying the silent-skip-without-audit gotcha (#27) without a phantom archive row. The
`suppressed_removes` lane on the delta is the structured carrier the step iterates to emit those warnings.

`_step_watchlist` (`runner.py:1565`) reads the active watchlist (it already does, for `prior`), derives
`pinned_tickers = frozenset(e.ticker for e in prior if e.pinned)`, passes it to `compute_watchlist_changes`, persists
`adds`/`requalifies`/`streak_increments` + `removes` as today, and emits the suppressed-remove warnings. No new write
path.

---

## 7. R3 — matcher-driven auto-label (opt-in site #1)

`lookup_active_recommendation_label` (`recommendations/hypothesis_prefill.py:55`) changes ONE line:

```python
matches = match_candidate_to_hypotheses(cand, registry=registry, include_baseline=True)
```

Everything downstream already exists and is unchanged: `_descriptive_label` emits `Broad-watch baseline (watch);
failed: <criteria>`; `prioritize_recommendations` ranks it (a single broad-watch match for the chosen ticker → it is
`prioritized[0]`); the entry-form VM renders the descriptive label into the display span + hidden input
(`view_models/trades.py:542`); the POST persists it via `canonicalize_hypothesis_label`. **No dashboard call site
changes** — `dashboard.py`'s two `match_candidate_to_hypotheses` calls keep the default `include_baseline=False`
(regression-tested, §10).

**Narrow-first is structural** (matcher two-phase gate `hypothesis.py:349`): the baseline phase fires only when the
narrow phase returned ZERO matches, so a ticker that fits H2/H4 still prefills the narrow label — the broad-watch label
appears only for watch candidates with no narrow match.

---

## 8. R4 — per-row cohort hint (opt-in site #2, render-time, no column)

`build_watchlist` (`view_models/watchlist.py:140`) already loads `candidates_by_ticker`. Add a
`cohort_hints: Mapping[str, str]` field on `WatchlistVM` (default `{}`), populated in the builder:

```python
registry = list_hypotheses(conn)              # active rows only matter to the matcher
for r in rows:
    cand = by_ticker.get(r.ticker)
    if cand is None:
        continue                              # error-edge / not-yet-evaluated → no hint
    matches = match_candidate_to_hypotheses(cand, registry=registry, include_baseline=True)
    if matches:
        cohort_hints[r.ticker] = _hint_label(matches[0].hypothesis_name)  # narrow name | "broad-watch"
```

`_hint_label` maps the matched hypothesis name to a short chip: the narrow name (abbreviated) for H1–H4, or
`broad-watch` for `Broad-watch baseline`. The matcher is a **pure** function; running it per row at render is cheap and
requires **no schema column**. The hint is an affordance (a chip in a new small column / appended to the tags cell),
NOT a metrics surface. Tickers absent from the latest eval (error-edge only, since pinned tickers are now always
evaluated) show no hint.

This is the SECOND production `include_baseline=True` opt-in site and is enumerated as an attribution surface in the
addendum (§13) and bounded by the inventory guard test (§10).

---

## 9. Pin UI (all controls in the expanded detail row — operator's Q1 choice)

**Compact row** (`templates/partials/watchlist_row.html.j2`): a small **📌 pin badge** rendered when `w.pinned`
(with the abbreviated `pin_note` as the `title=` tooltip). NO button in the compact row — keeps it clean. The badge is
plain HTML/UTF-8 (no cp1252-stdout or matplotlib-mathtext exposure — it is a template, not a `print()` or a rendered
PNG). The cohort-hint chip (§8) also renders here.

**Expanded row** (`templates/partials/watchlist_expanded.html.j2`): an embedded pin form —

```html
<form hx-post="/watchlist/{{ expanded.ticker }}/pin"
      hx-target="#watchlist-row-{{ expanded.ticker }}" hx-swap="outerHTML"
      hx-headers='{"HX-Request": "true"}'>
  <label><input type="checkbox" name="pinned" {% if expanded.entry.pinned %}checked{% endif %}> Pinned</label>
  <textarea name="pin_note">{{ expanded.entry.pin_note or "" }}</textarea>
  <button type="submit">Save pin</button>
</form>
```

**Route `POST /watchlist/{ticker}/pin`** (`routes/watchlist.py`):
- Parses `pinned` (checkbox → bool) + `pin_note` (`... or None`).
- **Server-stamps** `pinned_at`: re-computed from canonical state at POST time — `now` when transitioning to pinned,
  `NULL` when unpinning; NOT trusted from any hidden input (server-stamp discipline; there is no hidden `pinned_at`
  field at all).
- Calls `set_watchlist_pin(...)` inside `with conn:`; 404 when the ticker is not on the active watchlist.
- Returns the **re-rendered expanded row** partial (`build_watchlist_expanded` + the JIT chart helper, exactly as the
  `/expand` route does), 200, swapped via `outerHTML` into the expanded `<tr>`. This is a `<tr>`→`<tr>` outerHTML swap
  — the identical shape the existing expand/collapse path uses (`watchlist_row.html.j2:15` / the expand route), so the
  `<tr>`-fragment `makeFragment` hazard does NOT apply (that hazard is specific to OOB `<section>` chunks, not a direct
  `outerHTML` swap onto a `<tr>` target).

**HTMX gotcha compliance (each browser-only, each designed-to-rule):**
- Embedded form carries `hx-headers '{"HX-Request":"true"}'` → OriginGuard strict-mode does not 403 the submit.
- `hx-target` is set **explicitly** on the form (`#watchlist-row-{ticker}`) → no inheritance from the ancestor
  `<tr hx-target>` (the `hx-target` inheritance gotcha).
- Success is an in-place 200 fragment swap (the established expand-shape), NOT a 303 — the 204+HX-Redirect rule applies
  to navigation success paths (trade entry), not to an in-place row re-render.
- The `base.html.j2` 4xx `htmx.config.responseHandling` override is preserved (validation errors swap).
- **State propagation without OOB:** the operator toggles the pin while the row is expanded; the re-rendered expanded
  row reflects the new state immediately. On collapse, `/watchlist/{ticker}/row` re-reads the DB (`pinned=1`) → the
  compact-row badge renders. No OOB swap needed → no `makeFragment`-in-`<section>` exposure.

`WatchlistExpandedVM` gains the pin fields by carrying the full `entry` (it already does: `entry: WatchlistEntry`), so
no VM field churn beyond the model change. `WatchlistRowVM` likewise carries `w: WatchlistEntry`.

**Operator-witnessed browser gate (BINDING per the HTMX discipline):** pin a ticker → run a nightly that would have
aged it off → the row survives and stays fresh (re-evaluated) → unpin → it ages off at the next nightly. AND the entry
form for a watch ticker renders `Broad-watch baseline (watch); failed: …` server-stamped (form-render + a TestClient
persist test suffice; no real trade required — the operator witnesses the render).

---

## 10. R5 + R6 + the guard tests

**R5 (label round-trip):** the hidden-anchor round-trip for `hypothesis_label` through the soft-warn confirm +
`force=true` ALREADY exists (`routes/trades.py:1504-1513`) — R3 changes the VALUE, not the mechanism. Deliverable is
the **regression test**: a watch-bucket entry whose prefill resolves to `Broad-watch baseline …`, submitted through the
soft-warn confirm path, persists that exact label; a `force=true` resubmit does not drop it to `NULL` (the hidden-anchor
4-tier family).

**R6 (locks) — explicitly UNTOUCHED:** `hypothesis_registry` rows; `match_candidate_to_hypotheses`' two-phase gate;
`dashboard.py`'s two matcher call sites' `include_baseline=False` default; `swing/metrics/tier.py` + deviation
allowlist; the shadow engine + temporal log + measurement chain; the 16 historical trade labels;
`mistake_tags`/`process_grade`.

**Guard / regression tests (the load-bearing ones):**
1. **Label-match contract** — `label_matches_hypothesis('Broad-watch baseline (watch); failed: tightness',
   'Broad-watch baseline')` is True under `label_match.py`'s 3-rule contract, and is False against each of the other
   four registry names (both directions). (The 0026 spec §6 already proved no prefix collision; this re-asserts it at
   the persisted-label layer.)
2. **Dashboard containment regression** — assert `dashboard.py`'s `match_candidate_to_hypotheses` calls do NOT pass
   `include_baseline` (call-site kwargs assertion, not just behavior) → no broad-watch rows reach the hyp-recs panel.
   A behavioral companion: build the dashboard VM with a pure-watch candidate and assert zero broad-watch
   recommendation rows.
3. **Opt-in call-site inventory guard (rider b-ii)** — a test that statically scans `swing/` + `research/` for
   `include_baseline=True` occurrences and asserts the set of call sites is EXACTLY:
   `swing/recommendations/hypothesis_prefill.py` (prefill), `swing/web/view_models/watchlist.py` (cohort hint), and
   `research/harness/shadow_expectancy/attribution.py` (engine). Any new opt-in fails the test → forces a governance
   touch. (Implementation: grep the source tree, normalize, compare to the frozen allowlist set.)
4. **Pin-preserved-across-upsert** — pin a ticker, run a nightly upsert (requalify + streak_increment), assert the
   three pin columns survive (§4.1).
5. **Pin-veto semantics** — a pinned ticker with a removal-grade streak stays (no `removes`, a `streak_increment` with
   the incremented streak + a `suppressed_removes` entry); unpin → next nightly `removes` fires. Per
   `feedback_regression_test_arithmetic`, compute the streak under both pinned and unpinned to confirm the test
   distinguishes the veto.
6. **Universe injection** — `_step_evaluate` with a pinned off-screen ticker fetches + evaluates it (real candidate
   row, not `excluded`), and emits the pin-injection audit line; a pinned open-trade ticker stays `excluded`.
7. **Delisted-pin edge** — a pinned ticker with an unfetchable fetch → `error`-bucket candidate → row retained (not
   blanked), streak increments under the veto, run-warning surfaces the degradation (§5.1).

---

## 11. Production-touch carve-out (this arc's scope)

- `swing/data/migrations/00NN_*.sql` — NEW: 3 additive `ALTER TABLE watchlist ADD COLUMN` + version bump (§4).
- `swing/data/db.py` — `EXPECTED_SCHEMA_VERSION` bump + `_arc7_watchlist_pin_backup_gate` + expected-tables constant +
  gate registration.
- `swing/data/models.py` — `WatchlistEntry` gains 3 fields (defaults).
- `swing/data/repos/watchlist.py` — `_row_to_entry` + SELECTs widened; `upsert` INSERT widened / DO-UPDATE excludes pin
  cols; new `set_watchlist_pin` writer.
- `swing/watchlist/service.py` — `pinned_tickers` param + `suppressed_removes` lane + the veto branch (pure).
- `swing/pipeline/runner.py` — `_step_evaluate` pinned-universe injection + audit line; `_step_watchlist` passes
  `pinned_tickers` + emits suppressed-remove warnings.
- `swing/recommendations/hypothesis_prefill.py` — `include_baseline=True` (one line).
- `swing/web/view_models/watchlist.py` — `cohort_hints` builder (`include_baseline=True`) + `WatchlistVM.cohort_hints`.
- `swing/web/routes/watchlist.py` — `POST /watchlist/{ticker}/pin`.
- `swing/web/templates/partials/watchlist_row.html.j2` + `watchlist_expanded.html.j2` — badge + hint chip + pin form.
- Tests (§10) + this spec doc + the 0026 addendum (§13).

**NOT touched:** `recommendations/hypothesis.py` matcher logic; `dashboard.py` call sites; `metrics/tier.py`;
the registry / `hypothesis_status_history`; the shadow engine / temporal log; `mistake_tags`/`process_grade`;
`build_dashboard`'s OHLCV scope. No new production dependency.

---

## 12. Coordination with the in-flight P0 arc

The P0 tuition-vs-error arc (research-director lane, at writing-plans/executing) adds an `entry_intent` column +
entry/review-form changes. Both arcs touch `trade_entry_form.html.j2` + `routes/trades.py`. This arc's touch on those
two files is **minimal**: it adds NO field to the entry form (R3 reuses the existing `hypothesis_label` span + hidden
input + soft-warn round-trip) and NO new route to `routes/trades.py` (the pin route lives in `routes/watchlist.py`).
The migration numbers are disjoint (P0 `0027`, this arc `0028` — taken at branch time). Expect a small,
mostly-mechanical merge reconciliation at whichever lands second; no design conflict.

---

## 13. ADDENDUM to the 0026 broad-watch-baseline spec (R3 governance — DRAFT, dated section)

> The following is the verbatim dated section to APPEND to
> `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md` as part of this arc's deliverables.
> The research director QAs its language at the post-merge review. It does NOT rewrite the 0026 spec; the frozen
> registry row and the matcher two-phase gate are untouched.

---

### ADDENDUM 2026-06-10 — Arc 7 attribution-surface re-classification (V2.1 §VII.F governance)

**Context.** Phase 16 / Arc 7 (`docs/superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md`) makes
hypothesis labeling effective in the web-first workflow. It introduces TWO production callers that opt into the
broad-watch baseline via `match_candidate_to_hypotheses(..., include_baseline=True)`. This addendum amends the LETTER
of §3.2 + §5.1 of this spec (which listed `hypothesis_prefill.py:55` among the CONTAINED, default-`False` surfaces) —
NOT its spirit. The containment of the *recommendation flood* surfaces is preserved exactly.

**Re-classification.** The following two surfaces are re-classified from "contained recommendation surface" to
**attribution surface** — they opt into `include_baseline=True`:

1. **`swing/recommendations/hypothesis_prefill.py` — `lookup_active_recommendation_label`** (the entry-form/CLI
   server-stamped label prefill). Rationale: it fires ONLY for a ticker the operator has ALREADY chosen to enter and
   it recommends nothing — it labels an entry for downstream shadow attribution. The §3.2 flood rationale ("cannot put
   a recommendation row on every watch ticker") never applied to it: it surfaces exactly one label for one
   operator-selected ticker. Labeling watch trades with `Broad-watch baseline` is the PERMITTED secondary use already
   sanctioned in §5.3.
2. **`swing/web/view_models/watchlist.py` — the per-row cohort-hint builder** (`build_watchlist`). Rationale: an
   affordance that tells the operator what a name WOULD attribute as on entry (narrow name | `broad-watch` | none). It
   is read-only, surfaces no recommendation row, and drives no ranking — it is an attribution *preview*, not a
   recommendation. It does not call `prioritize_recommendations`.

**Still CONTAINED (unchanged, default `include_baseline=False`).** The live *recommendation* surfaces remain contained:
`swing/web/view_models/dashboard.py` (~L540 + ~L1061, the recommendations build + the 2nd matcher call) and
`prioritize_recommendations`. The broad-watch rule never fires for them, so it cannot put a recommendation row on every
watch ticker nor outrank H2/H4 via `distance_to_target`. **Enforced by a regression test** asserting the dashboard call
sites do NOT pass `include_baseline` (kwargs assertion) and that no broad-watch rows reach the hyp-recs panel.

**Bounded opt-in set.** The COMPLETE set of `include_baseline=True` call sites is now exactly THREE: the two above plus
the engine's `research/harness/shadow_expectancy/attribution.py` (the original §4 opt-in). An **opt-in call-site
inventory guard test** (Arc 7 §10.3) asserts this set verbatim; any future opt-in fails the test and requires a
governance amendment (this addendum's path).

**Measurement-universe note (research-director ruling, AMENDMENT 2026-06-10).** The watchlist pin unions pinned
tickers into the `_step_evaluate` evaluated universe, so the evaluated universe is **screen ∪ pinned (∪ held)**. A
pin-injected ticker that evaluates to `bucket=watch` enters the #23 detect/observe pool → the v22 temporal log → the
shadow-engine broad-watch measurement population. This is ACCEPTED and coherent: the FROZEN hypothesis statement
already defines the cohort as "the population the temporal log contains and the operator actually trades," and pinned
names literally are that population (the operator's intentional forward-watch universe). Per-run auditability is
preserved by the pin-injection `warnings_json`/`pipeline.log` line (Arc 7 §5) listing the injected tickers (count +
symbols), so screen-vs-pin provenance stays decomposable from run logs. No schema change; the frozen registry row and
the matcher gate are untouched.

---

## 14. Out of scope / explicitly deferred

- No tag store / sort-by-tags feature; no post-hoc label editor; no new metrics surface.
- No matcher-logic / registry / tier / deviation / shadow-engine / temporal-log change (R6).
- No `build_dashboard` OHLCV-scope change.
- No automated reconciliation of pin-injected watch population into a separate measurement bucket (the universe note is
  documented, not re-architected).
- TDD posture for the eventual writing-plans → executing-plans dispatches; this phase produces the SPEC only.
