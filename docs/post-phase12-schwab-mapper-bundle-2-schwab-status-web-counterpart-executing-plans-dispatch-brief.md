# Post-Phase-12 Sub-bundle 2 — `/schwab/status` web counterpart (T-B.7 follow-up) — Executing-plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-bundle 2 of the post-Phase-12 Schwab mapper execution-grain widening implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` §B (Sub-bundle 2 scope; 7 tasks T-2.0 … T-2.6). This sub-bundle implements the deferred Phase 12 Sub-bundle B T-B.7 — a read-only web counterpart to `swing schwab status` CLI mirroring its 3-state output 1:1. CLOSES the post-Phase-12 mapper-widening arc. All per-task acceptance criteria + tests + commit shapes are in plan §B; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration (calibrated 3-5x per `feedback_time_estimates_overstated.md`):** ~3-5 hr implementation + ~1-2 hr Codex convergence + ~30 min operator-paired gate. Total **~1-1.5 days operator-paced**. Web-side mirror; smaller scope than Sub-bundle 1's architectural arc; no cassette session; no Schwab API calls; no schema work.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-bundle 2 (`PLAN_PATH=docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md`, `SCOPE=Sub-bundle 2 only (T-2.0..T-2.6)`).
- Adversarial review runs after all 7 tasks land. Expected **2-4 Codex rounds** (web-side; smaller scope; plan §B absorbed Codex review at writing-plans time + Codex R1/R3 binding contracts already pinned into per-task acceptance criteria).

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` (Codex R1-R6 convergence with all findings closed; LOCKED at `cc6fd2d`).
- **Sub-bundle 2 section** is plan §B (lines 624-857). Self-contained per-task spec with TDD acceptance criteria + per-task test projections.
- **Plan §A.0** pre-verifications all completed against shipped code with verbatim grep results (12 verifications; pinned at file:line citations).
- **Plan §A.0.1 D3** state-triplet correction: spec §7.1's `CONFIGURED/PROVISIONAL/NOT_CONFIGURED` triplet is misnamed; shipped CLI `swing schwab status` uses `LIVE/PROVISIONAL/DEGRADED` per `swing/cli_schwab.py:823-825`. **Plan §B T-2.0 binds to the shipped LIVE/PROVISIONAL/DEGRADED triplet** (NOT spec §7.1). V2.1 §VII.F amendment banked.
- **Plan §C.1** cross-bundle pin: Sub-bundle 2's `SchwabStatusVM` populates `unresolved_material_discrepancies_count` via same helper as `/schwab/setup` route (Phase 10 T-E.3 retrofit pattern; banner predicate widened transitively from Phase 12 Sub-sub-bundle C.D).
- **Plan §C.4** NO behavioral changes to NON-touched surfaces (`stop_mismatch` UNCHANGED; mapper UNCHANGED; classifier UNCHANGED; CLI UNCHANGED; schema v19 UNCHANGED).
- **Plan §C.5** schema additions during executing-plans cycle → ESCALATE (Phase 9/12 inheritance).

### §0.2 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` (Codex R1-R4 substantive + R5 advisory; ZERO ACCEPT-WITH-RATIONALE; LOCKED at `dda8730`).
- **Read for §7 architectural shape** (web counterpart contract; CLI parity; banner field population) + §A.0.1 D3 state-triplet supersession.

### §0.3 Project state at dispatch time

- **HEAD on `main`:** `65a80bb` (post-Sub-bundle-1.5 housekeeping commit). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **~4523 fast passing on main** + 3 pre-existing phase8 walkthrough failures + 5 skipped. Verified at brief drafting time.
- **Ruff baseline:** **18** (E501 only; unchanged across post-Phase-12 arc; banked for Phase 12.5 #3 cleanup).
- **Schema version:** **v19** (LOCKED). **Sub-bundle 2 MUST NOT widen schema** (§C.5 escalation rule). Sub-bundle 2 is consumer-side only — reads `schwab_api_calls` audit table + tokens DB metadata; ZERO mutations; ZERO new domain rows.
- **Production discrepancy state:** ZERO unresolved-material; banner count=0 (preserved through Sub-bundle 1.5 ship at `a7c1016`). Base-layout banner field renders 0 at Sub-bundle 2 gate by construction; S5 confirms.
- **Production refresh-token clock:** issued 2026-05-15T17:05; expires ~2026-05-22T17:05 (~5 days remaining at brief-draft time). Sub-bundle 2 is READ-ONLY against tokens DB metadata — no impact on the clock; no re-auth required pre-dispatch.
- **Production-write classifier soft-block awareness:** Sub-bundle 2 is READ-ONLY (no Schwab API calls; no domain mutations). Operator-witnessed gate S2-S4 are page renders + nav-link clicks; NO production-write classifier soft-blocks expected. **Exception:** if implementer adds any test that writes to `schwab_api_calls` (e.g., planting redaction-audit fixtures), the test fixtures use tmp_path schema; production DB untouched.
- **Worktree husks:** `.worktrees/schwab-mapper-bundle-1/` + `.worktrees/schwab-mapper-bundle-1.5/` pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass. NOT blocking.

### §0.4 Sub-bundle 2 scope (7 tasks per plan §B)

| Task | Title | Files (illustrative; plan §B locks) | Tests |
|---|---|---|---|
| **T-2.0** | `SchwabStatusVM` view-model + `SchwabCallSummary` dataclass + base-layout VM banner pin | MODIFY `swing/web/view_models/schwab.py` + MODIFY `tests/web/test_view_models/test_schwab.py` | 12 |
| **T-2.1** | `GET /schwab/status` route + `apply_overrides(cfg)` discipline + `?environment=` query-param override (case-insensitive) | MODIFY `swing/web/routes/schwab.py` + CREATE `tests/web/test_routes/test_schwab_status.py` | 13 |
| **T-2.2** | `schwab_status.html.j2` template extending `base.html.j2` + 3-state LIVE/PROVISIONAL/DEGRADED rendering + autoescape | CREATE `swing/web/templates/schwab_status.html.j2` + MODIFY `tests/web/test_templates/test_schwab_status.py` | 10 |
| **T-2.3** | `/config` "External integrations" nav-link to `/schwab/status` + regression test (Phase 6 I3 target-route-registered check) | MODIFY `swing/web/templates/config.html.j2:58-60` + MODIFY `tests/web/test_routes/test_config.py` | 3 |
| **T-2.4** | `POST /schwab/setup` HX-Redirect retargets to `/schwab/status` + `/config?schwab_setup=ok` passive no-op consumer retention (one release window per Codex R1 m#2 LOCK) | MODIFY `swing/web/routes/schwab.py` + MODIFY `tests/web/test_routes/test_schwab_setup.py` | 3 |
| **T-2.5** | HTMX trinity preservation regression test (HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted) | MODIFY `tests/web/test_routes/test_schwab_status.py` | 3 |
| **T-2.6** | OQ-D applicability — `/schwab/status` inherits CLI semantics 1:1 (no FIRED-stop-specific handling at web layer) | MODIFY `tests/web/test_routes/test_schwab_status.py` | 1 |

**Per-task tests: 12 + 13 + 10 + 3 + 3 + 3 + 1 = 45.** Plan locks **+25-45 fast tests** (per §E).

**Cross-bundle dependencies:** Sub-bundle 2 CONSUMES Sub-bundle 1's `_fetch_unresolved_material_count(db_path)` helper at `swing/web/routes/schwab.py:266` (Phase 10 T-E.3 retrofit pattern) + Sub-bundle B's `apply_overrides(cfg)` discipline at Schwab entry points (Codex R1 Critical #1 fix `e418d56`) + Sub-bundle B's `setup_paste_flow_with_callback_url` service helper (NOT MODIFIED; only the HX-Redirect target changes at T-2.4) + Phase 11 Sub-bundle D's `_compute_degraded_state` + `render_status` CLI primitives at `swing/cli_schwab.py:823-825` (consult for parity).

**Module boundaries (BINDING — preserve discipline):**
- `swing/web/view_models/schwab.py`: VM extension layer. `SchwabCallSummary` + `SchwabStatusVM` NEW frozen dataclasses with `__post_init__` validators per Sub-bundle C.B forward-binding lesson #5 (shape predicate tightening discipline). Base-layout VM fields populate per Phase 10 T-E.3 retrofit (5 fields: `stale_banner` / `price_source_degraded` / `price_source_degraded_until` / `ohlcv_source_degraded` / `unresolved_material_discrepancies_count`).
- `swing/web/routes/schwab.py`: route layer. NEW `GET /schwab/status` handler. EXISTING `POST /schwab/setup` HX-Redirect target ONLY changes from `/config?schwab_setup=ok` → `/schwab/status` (T-2.4); no other behavioral changes to `/schwab/setup` flow.
- `swing/web/templates/schwab_status.html.j2`: NEW template extending `base.html.j2`. Jinja2 autoescape (Starlette + Jinja2 default; verify ambient config).
- `swing/web/templates/config.html.j2`: ONE-LINE addition — second `<a>` in External integrations `<ul>` section (T-2.3).
- `swing/cli.py` + `swing/cli_schwab.py`: **NOT TOUCHED** (CLI surface unchanged; Sub-bundle 2 only mirrors CLI semantics at web layer).
- `swing/integrations/schwab/*`: **NOT TOUCHED** (no Schwab API calls; no auth flow changes).
- `swing/trades/*`: **NOT TOUCHED** (no reconciliation; no classifier; no auto-correct).
- `swing/data/*`: **NOT TOUCHED** (no schema; no migration; no new repos).

### §0.5 BINDING contracts (DO NOT re-litigate)

1. **Schema MUST stay at v19** (plan §C.5 + spec §1.3 LOCK). If T-2.0..T-2.6 surfaces a need for schema element, STOP + escalate to orchestrator BEFORE adding inline. Bank-after-write costs 2-3 cascade-cleanup rounds.
2. **State triplet is LIVE/PROVISIONAL/DEGRADED, NOT spec §7.1's CONFIGURED/PROVISIONAL/NOT_CONFIGURED** (plan §A.0.1 D3 + plan §B T-2.0 LOCK). Mirrors shipped CLI per `swing/cli_schwab.py:823-825`. V2.1 §VII.F amendment banked (spec misnamed at §7.1).
3. **`state_reason is None iff state == 'LIVE'`** (Codex R3 Minor #2 + plan §B T-2.0 invariant). Discriminating tests 11 + 12 pin both branches.
4. **`apply_overrides(cfg)` discipline at route entry** (Codex R1 Critical #1 inheritance from Sub-bundle B). T-2.1 acceptance criterion includes monkeypatch-spy test asserting `apply_overrides` invoked once per request.
5. **Case-insensitive env query-param** (Codex R1 Minor #3 + plan §B T-2.1). `?environment=PRODUCTION`, `?environment=Sandbox`, `?environment=production` all accepted; `?environment=banana` rejected with 400.
6. **XSS-safe error response via PlainTextResponse** (Codex R1 Major #7 + R2 Major #1 + plan §B T-2.1 test #11). Invalid `?environment=` returns `content-type: text/plain` (NOT `text/html`). The route echoes invalid value via `repr()` for debugging — text/plain content-type is the XSS-safe primitive; body MAY contain literal `<script>` substring without browser interpretation.
7. **Sentinel-leak audit per Phase 11 Sub-bundle A T-A.10 D1 redaction discipline** (Codex R1 Major #6 + plan §B T-2.1 test #13 + T-2.2 test #10). Plant non-token-shaped sentinels (e.g., `LEAK_TOKEN_BYTES_ACCESS`, `LEAK_TOKEN_BYTES_REFRESH`, `LEAK_TOKEN_BYTES_ID`) into tokens DB AND `schwab_api_calls.error_message`; render `/schwab/status`; assert ZERO substring matches in response body. VM + template MUST consume only DERIVED METADATA (issued timestamps, expiry deltas, redacted error excerpts), never raw token bytes.
8. **Jinja2 autoescape preservation** (plan §B T-2.2 test #9). Plant `<script>alert(1)</script>` into `state_reason`; render; assert literal `<script>` does NOT appear in response body; assert HTML-entity-escaped `&lt;script&gt;` DOES appear.
9. **HTMX trinity preservation** (plan §C.4 + spec §7.5 + Phase 5 R1 M1 + M2 + Phase 6 I3 inheritance). T-2.5 pins all 3 with regression tests.
10. **`/config?schwab_setup=ok` passive no-op consumer retention** (Codex R1 m#2 LOCK; plan §B T-2.4). T-2.4 retargets HX-Redirect from `/config?schwab_setup=ok` → `/schwab/status` BUT preserves `/config?schwab_setup=ok` route's silent tolerance for one release window (stale browser tabs/bookmarks). T-2.4 test #2 pins this.
11. **NO Schwab API calls within Sub-bundle 2 scope** — page is READ-ONLY consumer of pre-existing `schwab_api_calls` audit + tokens DB metadata. No new audit rows; no production-write classifier interactions.
12. **NO behavioral changes to NON-touched surfaces** (plan §C.4). Especially: `swing schwab status` CLI UNCHANGED; `_fetch_unresolved_material_count` helper UNCHANGED; `setup_paste_flow_with_callback_url` UNCHANGED; banner predicate UNCHANGED; Sub-bundle 1+1.5 mapper/classifier/comparator UNCHANGED.
13. **Base-layout VM banner pin** (Phase 10 Sub-bundle E T-E.3 inheritance + Phase 12 Sub-sub-bundle C.D widening). `SchwabStatusVM` populates 5 base-layout fields with safe defaults; `unresolved_material_discrepancies_count` populated via `_fetch_unresolved_material_count(db_path)` per Phase 10 retrofit pattern. T-2.1 test #8 plants 1 material discrepancy; asserts response renders banner count = 1.
14. **CLI semantics 1:1 mirror** (spec §7.4 OQ-D LOCK + plan §B T-2.6). `/schwab/status` is read-only V1; no reconciliation actions; no FIRED-stop-specific handling at web layer. Operator sees raw API call status only; no order_type-specific strings leak.

### §0.6 Forward-binding lessons inherited (BINDING for Sub-bundle 2)

Per orchestrator-context.md §"Lessons captured" + Sub-bundle 1 + 1.5 return reports:

1. **NO Co-Authored-By footer** (durable across Phase 12 C.B + C.C + C.D + post-Phase-12 brainstorm + writing-plans + Sub-bundle 1 + Sub-bundle 1.5 — ~80+ commits with ZERO drift via explicit citation in dispatch prompts). **DO NOT regress.**
2. **`python -m swing.cli` at worktree-side gates, NOT `swing`** (`feedback_worktree_cli_invocation.md`). For S2-S4 web gate surfaces, use `python -m swing.cli web --port 8081` from `cd .worktrees/schwab-mapper-bundle-2` cwd. Pytest works fine without prefix.
3. **Pre-Codex orchestrator-side review (C.C lesson #6)** — before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with plan §B acceptance criteria + brief §0.5 BINDING contracts as anchors; ask for deviation list ≤300 words. Saved 1-2 Codex rounds on C.C + C.D + Sub-bundle 1.
4. **Operator's "pause" means STOP all forward motion immediately** (`feedback_pause_means_pause.md`). If operator pauses mid-dispatch, halt ALL forward action — even items appearing independently confirmed.
5. **Wall-clock duration estimates 3-5x too long** (`feedback_time_estimates_overstated.md`). Brief's "~1-1.5 days operator-paced" reflects calibration.
6. **Synthetic-fixture-vs-production-emitter shape drift family** (C.D-arc lesson #2 + #4 + Sub-bundle 1.5 H1-extended hypothesis). For Sub-bundle 2: redaction-audit fixtures MUST plant sentinels matching the SHAPE of real `schwab_api_calls.error_message` rows + real tokens DB columns. Test fixtures use tmp_path schema; production DB untouched.
7. **Apply_overrides discipline at Schwab entry points** (Sub-bundle B forward-binding lesson #6; Codex R1 Critical #1 fix `e418d56`). T-2.1 acceptance criterion includes monkeypatch-spy test asserting `apply_overrides` invoked once per request — discriminating test that the cfg-cascade is actually consumed end-to-end at the route handler.
8. **HTMX gotcha trinity preservation discipline** (Phase 5 R1 M1 + M2 + Phase 6 I3 inheritance). HX-Request header propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted family — TestClient cannot detect any of these; operator-witnessed browser verification gate is BINDING for any HTMX-affected work.
9. **Base-layout VM banner pin discipline** (Phase 10 Sub-bundle E T-E.3 inheritance). Every page extending `base.html.j2` MUST populate 5 base-layout fields with safe defaults — current set: `DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`, `ConfigPageVM`, `ReviewVM`, `CadenceCompleteVM`, `ReviewsPendingVM`, `TradeDetailVM`, `SchwabSetupVM` + Sub-bundle 2 ADDS `SchwabStatusVM`. T-2.0 acceptance criterion includes test #1 asserting all 5 fields default-initialized; T-2.1 test #8 asserts banner count populates from helper.
10. **Operator-architectural-pushback STOP-and-recover (C.D-arc lesson #1)** — if T-2.1 production-render surfaces architectural divergences (e.g., unexpected banner count; CLI/web parity drift; new audit-row shape), STOP, investigate, recover. NOT push-through.

### §0.7 Test projection

Per plan §E.2: **+25-45 fast tests projected** (post Round-1/3 fixes; per-task projection 12+13+10+3+3+3+1 = 45 max).

Final main HEAD post-Sub-bundle-2-merge: **~4548-4568 fast tests** (was 4523 + +25-45).

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `schwab-mapper-bundle-2`
- **Worktree directory:** `.worktrees/schwab-mapper-bundle-2/`
- **BASELINE_SHA:** `65a80bb` (current main HEAD pre-brief-commit; resolve via `git rev-parse main` after this brief lands; expect `~65a80bb + 1`).
- **Branch naming intent:** `schwab-mapper-bundle-2` matches the cleanup-script `schwab(?:-\w+)?-bundle-` regex (verified at `cleanup-locked-scratch-dirs.ps1:156`); operator's `-DeregisterFirst` pass cleans cleanly post-merge.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 7 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes per plan §B commit message stems:
  - `feat(schwab-vm): SchwabStatusVM + SchwabCallSummary view-model (T-2.0)`
  - `feat(web): GET /schwab/status route + apply_overrides discipline (T-2.1)`
  - `feat(web): schwab_status.html.j2 template + 3-state renderer (T-2.2)`
  - `feat(web): /config nav-link to /schwab/status (T-2.3)`
  - `feat(web): retarget /schwab/setup HX-Redirect to /schwab/status (T-2.4)`
  - `test(web): HTMX trinity regression coverage for /schwab/status (T-2.5)`
  - `test(web): /schwab/status inherits CLI semantics 1:1 (T-2.6)`
  - `fix(schwab-bundle-2): Codex RN <severity> #N — <description>` for Codex-driven fixes
- **NO Claude co-author footer.** Per Phase 12 C.B + C.C + C.D + post-Phase-12 brainstorm + writing-plans + Sub-bundle-1 + Sub-bundle-1.5 chains' explicit citation produced ZERO footer drift across ~80+ commits — pattern is DURABLE. **This dispatch MUST NOT regress.**
- **NO `--no-verify`**, **NO `--amend`** (per CLAUDE.md binding conventions: prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task acceptance criteria in plan §B mark per-step boundaries.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree until Sub-bundle 2 integration commit.
- **Implementer (you) owns:** task-family TDD commits (T-2.0 → T-2.1 → T-2.2 → T-2.3 → T-2.4 → T-2.5 → T-2.6) → marker-file removal → pre-Codex review (NEW C.C lesson #6) → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below — 4-5 surfaces).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Phase 12.5 dispatch commissioning.

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~10..HEAD
python -m pytest -m "not slow" -q
python -m pytest tests/web/test_view_models/test_schwab.py tests/web/test_routes/test_schwab_status.py tests/web/test_templates/test_schwab_status.py tests/web/test_routes/test_schwab_setup.py tests/web/test_routes/test_config.py -v
ruff check swing/ --statistics
python -c "from swing.web.view_models.schwab import SchwabStatusVM, SchwabCallSummary; print('vm OK')"
python -c "from swing.web.routes.schwab import router; assert any(r.path == '/schwab/status' for r in router.routes); print('route OK')"
```

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 7 tasks land + tests GREEN + after the pre-Codex orchestrator-side review (C.C lesson #6 — implementer MUST do an explicit dispatched-reviewer-subagent pass BEFORE invoking adversarial-critic).

**Expected chain shape:** 2-4 substantive Codex rounds (web-side; smaller scope; plan §B absorbed multi-round Codex review at writing-plans time + Codex R1/R3 binding contracts already pinned into per-task acceptance criteria).

**Adversarial review watch items (Sub-bundle 2-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **State triplet is LIVE/PROVISIONAL/DEGRADED** (§0.5 #2). Re-running shipped CLI `swing schwab status` per `swing/cli_schwab.py:823-825` MUST yield identical 3-state taxonomy + reasons; web SHOULD NOT diverge.
2. **`state_reason is None iff state == 'LIVE'` invariant** (§0.5 #3 + plan §B T-2.0 tests 11 + 12). Both branches discriminatingly tested.
3. **`apply_overrides(cfg)` discipline** (§0.5 #4 + plan §B T-2.1 test 7). Monkeypatch-spy test asserts invoked once per request.
4. **Case-insensitive env query-param** (§0.5 #5 + plan §B T-2.1 test 12). Mixed-case + lowercase + uppercase all accepted; rejected values via PlainTextResponse.
5. **XSS-safe PlainTextResponse for invalid env** (§0.5 #6 + plan §B T-2.1 tests 6 + 11). content-type `text/plain`; body MAY contain literal `<script>` substring without browser interpretation.
6. **Sentinel-leak audit** (§0.5 #7 + plan §B T-2.1 test 13 + T-2.2 test 10). 3+ non-token-shaped sentinels planted in tokens DB + `schwab_api_calls.error_message` rows; ZERO substring matches in response body.
7. **Jinja2 autoescape regression** (§0.5 #8 + plan §B T-2.2 test 9). `<script>alert(1)</script>` planted in `state_reason`; assert literal NOT in response + HTML-entity-escaped DOES appear.
8. **HTMX trinity preservation** (§0.5 #9 + plan §B T-2.5). 3 regression tests pinning HX-Request propagation + HX-Redirect-vs-303-swap + HX-Redirect-target-unrouted.
9. **`/config?schwab_setup=ok` passive no-op consumer retention** (§0.5 #10 + plan §B T-2.4 test 2). Old query-param still tolerated silently — one release window for stale browser tabs/bookmarks.
10. **Base-layout VM banner pin** (§0.5 #13 + plan §B T-2.0 test 1 + T-2.1 test 8). 5 fields default-initialized at VM construction; banner count populates via `_fetch_unresolved_material_count(db_path)` helper.
11. **CLI semantics 1:1 mirror** (§0.5 #14 + plan §B T-2.6). No FIRED-stop / order_type-specific strings leak; web page is generic Schwab integration status only.
12. **NO behavioral changes to NON-touched surfaces** (§0.5 #12 + plan §C.4). Codex SHOULD verify the touch surface is bounded; especially: CLI `swing schwab status` UNCHANGED; `_fetch_unresolved_material_count` helper UNCHANGED; `setup_paste_flow_with_callback_url` UNCHANGED; mapper/classifier/comparator UNCHANGED.
13. **Schema additions during executing-plans cycle** (Phase 9 Sub-bundle A return report lesson #7 + Phase 12 inheritance). If implementer surfaces a need for schema element NOT in plan, STOP + escalate to orchestrator BEFORE adding inline. Cost of bank-after-write: 2-3 cascade-cleanup rounds.
14. **Windows cp1252 stdout encoder pre-emption** (C.D gate-fix #1+#3 family + Sub-bundle 1.5 ASCII-only stdout discipline). Any new CLI output (NONE expected in Sub-bundle 2) MUST NOT contain non-ASCII glyphs (`§`/`→`/etc.) OR rely on `swing/cli.py` entry's UTF-8 stdout reconfigure. Template rendering is HTML output via Starlette response — Jinja2 + browser handle unicode correctly; NO cp1252 concern for the template itself.
15. **Synthetic-fixture-vs-production-emitter shape drift pre-emption** (C.D + Sub-bundle 1 + 1.5 lesson family). Redaction-audit fixtures (T-2.1 test 13 + T-2.2 test 10) MUST plant sentinels matching production `schwab_api_calls.error_message` shape + tokens DB column shape (verify via `git log -p -- swing/integrations/schwab/auth.py` for the audit-row writer + tokens DB schema).
16. **OriginGuard strict-mode allows read-only GET** (plan §B T-2.5 test 3). Smoke test verifies GET `/schwab/status` returns 200 under strict-mode (no OriginGuard 403).

---

## §3 Operator-witnessed verification gate (Sub-bundle 2 integration — 5 surfaces)

Per plan §H.2:

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q -n auto` | GREEN at ~4548-4568 fast tests (worktree-side; +25-45 net from 4523 baseline). 3 pre-existing phase8 walkthrough failures unchanged; 5 skipped. |
| **S2** | `/schwab/status` web page rendering | `python -m swing.cli web --port 8081` worktree-side; operator navigates to http://127.0.0.1:8081/schwab/status; verifies 3-state badge rendering (LIVE green / PROVISIONAL yellow / DEGRADED red) + refresh-token TTL countdown + recent-calls table + environment switcher + re-auth link (when state != LIVE OR severity != ok) + Phase 10 banner field (count=0 in production state) + Sub-bundle 1's nav additions intact + ZERO console errors. |
| **S3** | `/config` nav-link to `/schwab/status` | Operator navigates to http://127.0.0.1:8081/config; verifies "External integrations" section shows BOTH `/schwab/setup` AND `/schwab/status` nav-links (T-2.3 acceptance); clicking `/schwab/status` navigates correctly. |
| **S4** | `POST /schwab/setup` HX-Redirect retarget | OPTIONAL — operator re-auths Schwab if refresh-token clock is low; verifies successful POST returns `HX-Redirect: /schwab/status` (NOT `/config?schwab_setup=ok`); browser navigates to status page. **SKIP if refresh-token clock is healthy** — no need to consume a re-auth cycle on the gate. Production-write classifier soft-block awareness: re-auth writes new tokens DB rows; operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" if classifier soft-blocks. |
| **S5** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged (Sub-bundle 2 adds no new E501 lines; banked for Phase 12.5 #3 cleanup). |

**Gate session budget:** 4-5 surfaces. Short-haul operator-paired session (per `feedback_orchestrator_vs_implementer_execution.md`).

**Operator-paired-gate driving — ONE COMMAND AT A TIME on any production writes** (per durable preference); inline-batched OK on reads/tests (S1 + S2 + S3 + S5 are all reads).

**Production state post-gate:** ZERO unresolved-material discrepancies preserved; banner count=0 preserved. **Production state CLEAN.** No Schwab API calls fired (web page is read-only consumer); tokens DB unchanged (unless S4 exercised); `schwab_api_calls` table read-only.

**S4 fallback:** if operator's refresh-token clock is healthy (>2 days remaining) AND production state is clean, S4 may be SKIPPED — the HX-Redirect retarget is fully covered by T-2.4's 3 discriminating tests at S1. Operator preference at gate-time.

---

## §4 OUT OF SCOPE (do not do)

- **Schema additions or migrations** — §0.5 #1. If T-2.0..T-2.6 surfaces a need for schema element, STOP + escalate to orchestrator; BANK as V2 candidate.
- **Schwab API calls** — §0.5 #11. Sub-bundle 2 is READ-ONLY consumer of pre-existing audit + tokens DB metadata; no new audit rows; no production-write interactions.
- **Tokens DB mutations** — §0.5 #12. Sub-bundle 2 reads tokens DB metadata (file path; refresh-token expiry timestamp); no rewrites. S4 (optional) exercises EXISTING `POST /schwab/setup` flow — that flow's tokens DB writes are NOT Sub-bundle 2 changes.
- **CLI surface changes** — §0.5 #12. `swing schwab status` CLI UNCHANGED; Sub-bundle 2 mirrors its semantics at web layer only.
- **Mapper/classifier/comparator changes** — §0.5 #12. Sub-bundle 1 + 1.5 shipped. Touch zero.
- **Reconciliation flow changes** — §0.5 #12. Sub-bundle C shipped. Touch zero.
- **`_fetch_unresolved_material_count` helper changes** — §0.5 #13. Phase 10 T-E.3 + Phase 12 C.D shipped. Consumed unchanged.
- **`setup_paste_flow_with_callback_url` service helper changes** — §0.5 #12. Sub-bundle B shipped. T-2.4 only retargets HX-Redirect in the POST success path; service helper itself untouched.
- **Banner predicate widening** — §0.5 #12. Phase 10 T-E.3 + Phase 12 C.D shipped (`'pending_ambiguity_resolution'` widening inherited transitively). Touch zero.
- **HTMX gotcha resolution within Sub-bundle 2 scope** — Sub-bundle 2 PRESERVES the trinity via regression tests; does NOT introduce new HTMX patterns that would require new gotcha analysis. Use established patterns (`hx-headers='{"HX-Request": "true"}'` on embedded forms; HX-Redirect for success-path; HX-Redirect target route registered).
- **Spec §7.1 CONFIGURED/PROVISIONAL/NOT_CONFIGURED triplet** — §0.5 #2 LOCK. Use LIVE/PROVISIONAL/DEGRADED per plan §A.0.1 D3 + shipped CLI. Banked as V2.1 §VII.F amendment.
- **Phase 12.5 dispatches** — Phase 12.5 #1 (OQ-F auto-redirect), #2 (Web Tier-2 discrepancy-resolution surface), #3 (Project hygiene maintenance pass) are SEPARATE dispatches; do NOT pre-empt scope here.
- **Re-litigating plan §B acceptance criteria** — accepted as given. Operator-locked at `cc6fd2d`; Codex R1-R6 chain absorbed.
- **Behavioral changes to non-touched surfaces** — plan §C.4. Verify every touched file's `git diff` is bounded to T-2.0..T-2.6 acceptance criteria.

---

## §5 Return report shape

After all 7 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/post-phase12-schwab-mapper-bundle-2-return-report.md` (mirroring `docs/post-phase12-schwab-mapper-bundle-1.5-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (7 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Test count delta + ruff baseline delta + schema version delta (v19 unchanged — Sub-bundle 2 touches no schema).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 4-5 surfaces).
5. Per-task deviations from plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any). Expectation: ZERO ACCEPT-WITH-RATIONALE (matches Sub-bundle 1.5's clean record — only 2 banked positions there).
7. Watch items for orchestrator (V2 candidates surfaced; particularly: V2.1 §VII.F amendment for spec §7.1 CONFIGURED/... triplet supersession).
8. Worktree teardown status.
9. Forward-binding lessons for future Phase 12.5 dispatches.
10. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time.
11. Composition-surface verification: `^def ` grep on `swing/web/view_models/schwab.py` + `swing/web/routes/schwab.py` confirming public surface matches plan §B acceptance criteria.
12. Pre-existing test count delta (3 phase8 walkthrough + 5 skipped should remain unchanged).
13. Sub-bundle 1 + 1.5 architectural-surface non-regression evidence (no changes to mapper / classifier / comparator / helpers / Shape C / Path B / early-exit gate / canary helper).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** ~3-5 hr implementation + ~1-2 hr Codex + 4-5-surface operator-witnessed gate. Total **~1-1.5 days operator-paced**.

---

## §7 If you get stuck

- If plan §B binding contracts conflict with what spec §7 says, **plan wins** (spec §7.1 misnamed the triplet; plan §A.0.1 D3 locks the shipped LIVE/PROVISIONAL/DEGRADED triplet).
- If T-2.1's `_fetch_unresolved_material_count(db_path)` helper signature differs from what plan §B says, verify shipped signature at `swing/web/routes/schwab.py:266` + use that exact signature. Helper is UNCHANGED — Sub-bundle 2 only CONSUMES it.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in return report.
- If you need a schema element NOT in plan §B, **STOP + escalate** (§0.5 #1; plan §C.5 escalation rule; bank-after-write costs 2-3 cascade-cleanup rounds).
- If the production refresh-token clock has expired during dispatch (`~2026-05-22T17:05`), Sub-bundle 2 itself does NOT require re-auth (read-only consumer of metadata); S4 gate may be DEFERRED if operator prefers not to consume a re-auth cycle at gate time.
- If Codex pushes back on the LIVE/PROVISIONAL/DEGRADED triplet LOCK (e.g., "but spec §7.1 says CONFIGURED..."), HOLD THE LINE — the LOCK is plan §A.0.1 D3 + Codex R3 + shipped CLI per `swing/cli_schwab.py:823-825`. V2.1 §VII.F amendment banked for spec correction.
- If Codex pushes back on the `state_reason is None iff state == 'LIVE'` invariant (§0.5 #3), HOLD THE LINE — the LOCK is plan §B T-2.0 Codex R3 Minor #2 + R3 LOCK. Both branches discriminatingly tested.
- If Codex pushes back on the `/config?schwab_setup=ok` passive no-op consumer retention (§0.5 #10), HOLD THE LINE — the LOCK is plan §B T-2.4 + Codex R1 m#2. One release window for stale browser tabs.
- If Codex pushes back on PlainTextResponse for invalid env (§0.5 #6), HOLD THE LINE — the LOCK is plan §B T-2.1 + Codex R1 Major #7 + R2 Major #1. content-type `text/plain` is the XSS-safe primitive.
- DO NOT propose new web routes within Sub-bundle 2 scope (§4 lock; only `GET /schwab/status` is in scope).
- DO NOT propose CLI surface changes within Sub-bundle 2 scope (§4 lock; web mirror only).
- DO NOT propose schema additions within Sub-bundle 2 scope (§4 lock; §C.5 escalation rule).
- DO NOT add `Co-Authored-By` footer to any commit message (per §1.3 + Sub-bundle 1 + 1.5 precedent of ZERO drift across ~80+ commits; do NOT regress).
- DO NOT propose new HTMX patterns within Sub-bundle 2 scope (§4 lock; preserve established trinity).
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with plan §B acceptance criteria + brief §0.5 BINDING contracts as anchors; ask for a deviation list ≤300 words. Cheap; absorbs LOCK divergences pre-Codex; saved 1-2 Codex rounds on C.C + C.D + Sub-bundle 1. Apply explicitly here.

---

## §8 Operator-paired gate notes

Sub-bundle 2's 4-5 surface gate is small (matches Phase 12 Sub-sub-bundle C.A's tightly-scoped sub-bundle gates + Sub-bundle 1.5's 5-surface gate). Plan for a brief operator-paired session:

- **No mid-dispatch operator pause** (unlike Sub-bundle 1's cassette session). Implementer ships all 7 tasks + pre-Codex review + adversarial-critic + return-report autonomously; operator engages at S1-S5 gate.
- **Production refresh-token clock** — expires ~2026-05-22; verify TTL at S2 page render. **S2 page MUST correctly render the days-remaining indicator** with severity-correct styling (ok / warn / error per cfg + `_compute_degraded_state`). If TTL is in WARN or ERROR range at gate time, S2 verification covers the rendering automatically.
- **Production-write classifier soft-block** — S1-S3 + S5 are READS; expect ZERO blocks. S4 (optional re-auth) writes new tokens DB rows; if exercised, operator pre-authorizes via plain-chat "yes" PER INVOCATION (C.D-arc lesson #2).
- **One command at a time** — per operator preference; orchestrator/implementer sends ONE command per turn, waits for output, verifies, sends next.
- **Worktree-side CLI invocation** — S2 + S3 + S4 use `python -m swing.cli web --port 8081` from `cd .worktrees/schwab-mapper-bundle-2` cwd (NOT `swing web ...`) per `feedback_worktree_cli_invocation.md`.
- **Operator-architectural-pushback STOP-and-recover** — if S2 page renders surface unexpected divergence (e.g., CLI/web parity drift; unexpected banner count; HTMX trinity regression), STOP, investigate, recover (C.D-arc lesson #1). NOT push-through.
- **Pause-means-pause discipline** — if operator pauses mid-dispatch or mid-gate for any reason, halt ALL forward action (`feedback_pause_means_pause.md`).

---

*End of brief. Sub-bundle 2 executing-plans dispatch — `/schwab/status` web counterpart implementing the deferred Phase 12 Sub-bundle B T-B.7 task. Branch `schwab-mapper-bundle-2` matches cleanup-script regex. Schema unchanged (v19); read-only web mirror; 7 tasks T-2.0..T-2.6; 45 max-projection per-task tests (+25-45 net); 4-5 surface operator-witnessed gate; ~2-4 Codex rounds. CLOSES the post-Phase-12 mapper-widening arc.*
