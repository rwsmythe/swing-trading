# Finviz Elite API Integration — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author the Finviz Elite API integration implementation plan from the locked V1 design below; wrap with `copowers:writing-plans` for adversarial Codex review of the plan; iterate to `NO_NEW_CRITICAL_MAJOR`. **Brainstorm is skipped** — operator + orchestrator have locked V1 design via in-thread Q&A on 2026-05-05; the plan author's job is to convert design → plan, not to re-design.

**Expected duration:** ~3-5 hours of plan drafting + 3-5 rounds of Codex review on the resulting plan. V1 scope is medium-small (single integration; new namespace; new pipeline step; new schema migration; CLI commands; test-cassette infrastructure). No UI/HTMX work in V1.

---

## §0 — Read first

In this order:

1. **`docs/phase3e-todo.md` 2026-05-04 Finviz Elite API integration entry** (around line 333 in active backlog) — the queued entry; has the full V1 sketch + 8 design questions + V1-deferred / V2 list + cross-references. The in-thread design lock captured in §2 below overrides any specifics in this entry, but the entry's V1 sketch and rationale stand as background.
2. **`docs/orchestrator-context.md` §"Binding conventions" + §"Anti-patterns" + §"Lessons captured"** — binding for plan drafting. Especially relevant lessons (most-recent 30): `cfg.X 3-edit cascade`, `Plan templates can encode assertion errors`, `closed_date is derived not stored`, `Test count projections should bias high`, `HX-Redirect target route must be verified` (N/A but pattern), `Default discipline: no main-side commits while dispatch in flight` — these are plan-authoring discipline.
3. **`CLAUDE.md`** at repo root — gotchas + project conventions. Especially relevant: Finviz inbox section (`data/finviz-inbox/`); pipeline-lease-acquisition wait; SQLite WAL-mode `Connection.backup()` discipline; ruff baseline.
4. **`swing/pipeline/runner.py`** — existing pipeline step structure. Read enough to understand: how steps are sequenced; how `lease.fenced_write()` works for step-scoped DB writes; how steps log + handle errors; how `_step_evaluate` consumes Finviz CSVs from `data/finviz-inbox/`.
5. **`swing/pipeline/finviz_schema.py`** — canonical 13-column schema validator. The API integration emits CSVs that MUST pass this validator unchanged (per Q4 lock).
6. **`swing/config.py` + `swing/config_overrides.py`** — Phase 5 user-config TOML infrastructure. Understand: where user-config lives (`%USERPROFILE%/swing-data/user-config.toml`); how it's loaded; how `cfg.foo.bar` paths resolve through Python default → tracked toml → user-config → page-write.
7. **`swing/data/db.py` + `swing/data/migrations/0014_*.sql`** — schema_version mechanism + latest migration as exemplar. Phase 7 hotfix at `283d4fa` patched `_apply_migration` to toggle `foreign_keys=OFF` for table-rebuild migrations; this V1 doesn't rebuild tables but inherits the fixed runner discipline.
8. **`swing/data/models.py` + a small `swing/data/repos/*.py`** (e.g., `repos/pipeline_runs.py` or `repos/trades.py`) — dataclass + repo conventions.
9. **`swing/cli.py`** — Click conventions for subcommand groups. Find an existing group like `journal` or `pipeline`; mirror the structure for the new `finviz` group.
10. **`docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md` OR `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`** — recent plan exemplars. Phase 6 is closer in scope (single feature, smaller surface); Phase 7 is the larger-scope plan template if needed.
11. **`docs/phase6-post-trade-review-writing-plans-brief.md` OR `docs/phase7-trade-lifecycle-state-machine-writing-plans-brief.md`** — brief structure exemplars (NOT for content).
12. **`docs/cycle-checklist.md`** — current daily operator workflow; the API integration changes Step N (manual Finviz export); document the change.

You may also want to grep for `data/finviz-inbox/` references to enumerate every consumer of the canonical CSV directory.

---

## §0 — Skill posture

- **INVOKE:** `copowers:writing-plans` (the standard plan-authoring + adversarial-Codex-review wrapper). This skill handles the iterate-to-NO_NEW_CRITICAL_MAJOR loop.
- **DO NOT INVOKE:** `superpowers:brainstorming` — brainstorm is skipped per design-lock above; re-litigating decisions is anti-pattern (re-litigating decided framings; see orchestrator-context anti-patterns).
- **DO NOT INVOKE:** `superpowers:executing-plans` or `superpowers:subagent-driven-development` — this dispatch's deliverable is the PLAN, not the implementation. Implementation comes in a separate dispatch later.
- **DO NOT INVOKE:** `superpowers:using-git-worktrees` — writing-plans is docs-only output; no isolated workspace needed. Plan file lands directly on `main`.

Standard `copowers:writing-plans` flow: draft plan → Codex review round → fix findings → repeat until `NO_NEW_CRITICAL_MAJOR`. Plan file location: `docs/superpowers/plans/2026-05-XX-finviz-api-integration-plan.md` (use ship date).

---

## §1 — Strategic context (compressed)

The Swing Trading project's pipeline currently ingests candidate stocks from a manually-exported Finviz CSV that the operator drops in `data/finviz-inbox/` daily. Operator is on Finviz Elite (~$40/mo subscription confirmed 2026-05-05). The Finviz Elite API allows programmatic fetch of the same screen; replacing manual export removes a daily operator chore and adds drift-detection capability.

**Why now:** Phase 7 (trade lifecycle state machine + Fills first-class) shipped 2026-05-05; Phase 8 (Daily_Management) and Phase 9 (Risk_Policy + reconciliation depth) are unblocked but operator-paced. Operator chose Finviz API as a standalone establishing pattern — it builds the new `swing/integrations/` namespace that the much-larger Schwab API integration (queued at `docs/phase3e-todo.md` 2026-05-04 Schwab entry) will later inherit. Finviz API's narrower scope makes it the right vehicle for namespace establishment.

**What changes for operator after V1 ships:**
- Pipeline runs Finviz fetch automatically; daily manual CSV export becomes optional fallback.
- Operator can still drop a manual CSV in `data/finviz-inbox/` for a session — the pipeline detects the existing CSV and skips API fetch (manual override).
- New `swing finviz status` CLI shows recent API calls + rate-limit headroom + drift warnings.
- New `swing finviz fetch` CLI for ad-hoc invocation outside the pipeline.

**What does NOT change:**
- Existing `swing/pipeline/finviz_schema.py` 13-column validator runs unchanged on the API-emitted CSV (per Q4 lock).
- Existing `_step_evaluate` candidate-ingestion logic unchanged (per Q4/Q7 locks; Sector + Industry preserved verbatim from Finviz API).
- Manual-CSV-drop path remains permanently supported.

**Out of scope for this dispatch (V2+):**
- Multi-screen support (operator currently runs one screen).
- Backfill mode (historical screen pulls).
- Real-time price feed (Finviz Streamer; redundant with potential Schwab market-data integration).
- Phase 5 config-page UX surfacing of token/screen_id (V2; operator edits user-config.toml directly for V1).

---

## §2 — Locked V1 design (implementer treats as binding spec)

### 2.1 Architecture

- **New namespace:** `swing/integrations/`. This dispatch establishes it; future Schwab integration inherits the structure.
- **Module:** `swing/integrations/finviz_api.py`. Contains the API client class (suggested name `FinvizClient`) + supporting helpers (signature-hash computation; CSV normalization). Implementer can adjust naming if a cleaner factoring emerges; document any deviations from this brief in the plan.
- **HTTP library:** `requests` (project consistency — yfinance + other production paths use requests). Do NOT introduce `httpx` as a new dependency for V1.

### 2.2 Configuration

- **Token + screen_id storage:** user-config TOML at `%USERPROFILE%/swing-data/user-config.toml`. New section `[integrations.finviz]` with keys `token` (string) and `screen_id` (string).
- **Load path:** Phase 5 infrastructure (Python default → tracked `swing.config.toml` → user-config → page-write). Tracked `swing.config.toml` does NOT contain `token` (sensitive); MAY contain a placeholder `screen_id = ""` and timeout/retry defaults if appropriate.
- **Cfg structure:** new sub-dataclass `IntegrationsConfig` with nested `FinvizIntegrationConfig` (or flat — implementer chooses; the lesson "Adding a `cfg.X` field is a 3-edit cascade" applies, so plan must enumerate the cascade explicitly: sub-dataclass + top-level Config field + Config(...) constructor + toml row + `Config(...)` direct-construction audit in tests).
- **Verification at load time:** if token is missing from user-config, the API client construction raises a typed exception (e.g., `FinvizConfigMissingError`). Pipeline step catches + LOGs + skips. CLI commands surface a friendly error message + non-zero exit.

### 2.3 Pipeline step

- **Name:** `_step_finviz_fetch`.
- **Location:** `swing/pipeline/runner.py`.
- **Ordering:** Runs BEFORE `_step_evaluate`. Add to the step sequence at the appropriate position; existing steps after this point inherit unchanged behavior.
- **Logic flow:**
  1. Compute today's session-anchored CSV path (`data/finviz-inbox/finvizDDMmmYYYY.csv` per existing convention; date format must match `swing/pipeline/finviz_schema.py` filename pattern).
  2. **File-collision skip:** if today's CSV already exists, log `INFO: Manual CSV present at <path>; Finviz API fetch skipped (manual override).` Insert a `finviz_api_calls` row with `status='skipped_manual_override'`. Return without raising.
  3. **API fetch:** load token + screen_id from cfg; instantiate `FinvizClient`; call `fetch_screen()`. Handle: HTTP errors (4xx/5xx), rate-limit (429), network errors (`requests.RequestException`), token-missing.
  4. **Normalization:** map API response fields → canonical 13-column CSV schema (`No., Ticker, Sector, Industry, Country, Price, Change, Average Volume, Relative Volume, Average True Range, 52-Week High, 52-Week Low, Market Cap`). Sector + Industry preserved verbatim per Q7 lock.
  5. **Drift detection (Q8(b) lock — hash-and-warn):** compute `signature_hash` = stable hash (e.g., SHA256) of canonicalized concatenation: sorted column-names + first-row tuple of (Ticker, Sector, Industry). Use a deterministic encoding (e.g., JSON with `sort_keys=True` + UTF-8). Compare to most-recent prior `finviz_api_calls.signature_hash`; if different, log `WARNING: Finviz screen signature changed since prior run (<prev_hash> → <new_hash>); operator may have edited the saved screen.`
  6. **Persist:** write canonical CSV to `data/finviz-inbox/`; insert `finviz_api_calls` row with status='ok' + metrics.
  7. **Error path:** on any caught exception, log error, insert `finviz_api_calls` row with `status='error'` + `error_message` (token-redacted; see §7 watch items), and return without raising. `_step_evaluate` proceeds normally; if no CSV is present from any source, it follows existing handling for empty inbox.

### 2.4 Persistence

- **New table:** `finviz_api_calls`.
- **Schema:** `call_id INTEGER PRIMARY KEY AUTOINCREMENT`, `ts TEXT NOT NULL` (ISO-8601 naive datetime per Phase 7 Sub-B convention; lexicographic-sort-safe), `screen_id TEXT NOT NULL`, `status TEXT NOT NULL CHECK (status IN ('ok','error','skipped_manual_override'))`, `row_count INTEGER`, `response_time_ms INTEGER`, `rate_limit_remaining INTEGER`, `signature_hash TEXT`, `error_message TEXT`. Index on `ts DESC` for `swing finviz status` queries.
- **Migration:** new file `swing/data/migrations/0015_finviz_api_calls.sql`. Bump `EXPECTED_SCHEMA_VERSION` (currently 14 post-Phase-7) → 15. Per Phase 6 lesson `Plan templates can encode assertion errors`: plan-supplied test fixtures must use `ensure_schema(db_path)`, NOT `connect(db_path)`, for fresh DBs.
- **Migration-test discipline:** per Phase 7 Sub-A lesson `Test fixture connection state must mirror production runtime PRAGMA state`, the migration test MUST execute with `foreign_keys=ON` to mirror production. (This migration is additive — only CREATE TABLE — so no FK CASCADE risk; test still verifies under production-equivalent PRAGMA.)
- **Repo:** `swing/data/repos/finviz_api_calls.py` with `insert_call(conn, call: FinvizApiCall) -> int`, `list_recent_calls(conn, limit: int = 50) -> list[FinvizApiCall]`, `get_latest_signature_hash(conn, screen_id: str) -> str | None`.
- **Dataclass:** `FinvizApiCall` in `swing/data/models.py`.

### 2.5 CLI

- **New subcommand group:** `swing finviz` in `swing/cli.py` (Click).
- **Commands:**
  - `swing finviz fetch` — invokes the fetcher manually (NOT through the pipeline runner). Same file-collision skip behavior as `_step_finviz_fetch`. Useful for ad-hoc refresh between pipeline runs OR for operator testing token validity. Output: success (row count, signature hash) OR error (with friendly message).
  - `swing finviz status` — queries `finviz_api_calls`; shows last N calls (default 10) with timestamp, status, row_count, response_time_ms, rate_limit_remaining, signature_hash (abbreviated). Format: tabular text via `rich` or plain text — match existing CLI command formatting style.
- **Out of scope V1:** `swing finviz set-token` interactive setup (operator edits user-config.toml directly per Phase 5 convention).

### 2.6 Tests

Per Phase 6 lesson `Test count projections should bias high`, the implementer should expect 30-50+ new fast tests + 1-2 slow live tests. Plan must specify test cassette infrastructure explicitly.

- **Cassette library:** `pytest-recording` (uses VCR.py under the hood; cleaner pytest integration). Add to `[dev]` extras in `pyproject.toml`. Implementer researches at writing-plans time if a different library has clearer ergonomics; surface choice in plan.
- **Cassette location:** `tests/fixtures/finviz_api/` with one cassette per test scenario (success, 429 rate-limit, 500 server error, network error, schema-drift, empty result).
- **Cassette generation:** initial cassettes recorded by running tests against live API ONCE with a real token; cassettes committed; subsequent CI runs replay. Token MUST be redacted from cassettes (use VCR's `filter_headers` for `Authorization` or query-param filtering for `auth_token` — research at writing-plans time).
- **Slow-marked live test:** `tests/integrations/test_finviz_api_live.py` with `@pytest.mark.slow`. Hits real API; verifies the canonical-13-column schema match against current Finviz Elite response shape; serves as drift-detection harness for cassette staleness. Skip with `pytest.skip` if `cfg.integrations.finviz.token` is unset (so CI without secrets doesn't cascade RED on `pytest -m slow`).

### 2.7 Logging + observability

- Use the existing project logging setup (`logging.getLogger(__name__)` per module).
- All API call attempts produce a `finviz_api_calls` row regardless of outcome (queryable history via `swing finviz status`).
- Token MUST NOT appear in any log message, error message, exception text, or `finviz_api_calls.error_message`. Defense-in-depth: scrub Authorization headers + token-bearing query params before any string-coercion.

---

## §3 — Open research items (implementer closes during plan drafting)

These are deliberately deferred to writing-plans time. Plan must surface findings or update brief if they invalidate any locked decision.

1. **Endpoint shape.** Operator has not exercised the API. Implementer must:
   - Read https://elite.finviz.com/api_explanation.
   - Determine: API endpoint URL, authentication mechanism (header? query param?), screen-fetch query params, response format (CSV? JSON? specific Content-Type?), pagination semantics if any, rate-limit response shape (429 status? body? headers like `X-RateLimit-Remaining`?).
   - Document findings in plan §"Endpoint Reference" or equivalent.
   - If API requires multi-step flow (e.g., authentication → session token → fetch), plan accommodates accordingly.
2. **Rate-limit quota.** Operator does not know quota offhand. Implementer reads Finviz Elite docs; documents quota in plan as constants. If quota is unclear from docs, plan specifies conservative defaults (e.g., 1 fetch per pipeline run; backoff on 429 with retry-after header parsing) and flags the uncertainty for adversarial review.
3. **Cassette format / library.** `pytest-recording` is recommended; alternatives include raw `vcrpy`, `responses`, or `requests-mock`. Implementer picks; plan justifies briefly.
4. **Filename anchoring.** The existing `data/finviz-inbox/finvizDDMmmYYYY.csv` filename pattern uses operator-local-date OR `action_session_for_run(datetime.now())`. Implementer verifies: `swing/pipeline/runner.py` + `swing/pipeline/finviz_schema.py` to determine which date convention is canonical. Plan specifies the same convention for API-emitted file naming.

If any research finding contradicts a §2 lock, surface it explicitly in the plan as `OPEN QUESTION FOR ORCHESTRATOR`; do NOT silently re-design.

---

## §4 — Carve-out (files NEW + MOD)

Pre-flight scope enumeration for plan §"Carve-out" section.

**NEW files:**
- `swing/integrations/__init__.py` (empty namespace stub OR exports if helpful).
- `swing/integrations/finviz_api.py` (client class + helpers).
- `swing/data/migrations/0015_finviz_api_calls.sql` (schema migration).
- `swing/data/repos/finviz_api_calls.py` (repo functions).
- `tests/integrations/__init__.py` (test namespace).
- `tests/integrations/test_finviz_api.py` (cassette-based unit tests).
- `tests/integrations/test_finviz_api_live.py` (slow-marked live test).
- `tests/cli/test_finviz_commands.py` (CLI tests).
- `tests/pipeline/test_step_finviz_fetch.py` (pipeline-step tests).
- `tests/data/test_migration_0015_finviz_api_calls.py` (migration test).
- `tests/data/repos/test_finviz_api_calls.py` (repo tests).
- `tests/fixtures/finviz_api/*.yaml` (cassette files; count depends on test scenarios).

**MOD files:**
- `swing/cli.py` (add `finviz` subcommand group with `fetch` + `status`).
- `swing/pipeline/runner.py` (add `_step_finviz_fetch` step; insert into step sequence before `_step_evaluate`).
- `swing/data/db.py` (bump `EXPECTED_SCHEMA_VERSION` 14 → 15; possibly extend `ensure_schema` if it has migration-version-aware logic).
- `swing/data/models.py` (add `FinvizApiCall` dataclass).
- `swing/config.py` (add cfg cascade for `[integrations.finviz]`; remember the 3-edit pattern + `Config(...)` constructor sites).
- `swing.config.toml` (add `[integrations.finviz]` section with placeholder defaults; NO token).
- `pyproject.toml` (add `pytest-recording` or chosen cassette lib to `[dev]` extras).
- `CLAUDE.md` (update Finviz inbox section to mention API path; add gotcha for token-in-user-config-not-tracked-toml; possibly add gotcha for cassette-staleness if not generic enough for the lessons captured).
- `docs/cycle-checklist.md` (operator no longer needs to manually export Finviz CSV daily; reflect change).
- `tests/data/test_db_v8.py` (or current schema-version-pin test) — bump pin OR consolidate per Phase 6 V1 follow-up (operator-paced; not blocking — note in plan).

**Read-only (do NOT modify):**
- `swing/pipeline/finviz_schema.py` (validator; emitted CSV must pass it unchanged).
- `swing/pipeline/_step_evaluate` (existing candidate-ingestion path; unchanged).
- All Phase 6 / Phase 7 entities (Trades, Fills, trade_events, review_log, etc.).

---

## §5 — Binding conventions

Per project standards (see `docs/orchestrator-context.md` §"Binding conventions" for full text):

- **Branch:** `main`. Plan + Codex review fixes commit directly.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.**
  - Plan-drafting commits: e.g., `docs(plan): finviz-api integration — initial draft + Codex R1 fixes`.
  - Use `(internal)` qualifier on subagent-driven Codex round commits per binding-conventions formalization.
- **TDD discipline (in plan task structure):** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change.
- **DB location:** `%USERPROFILE%/swing-data/swing.db` outside Drive.
- **Tests:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green. Plan tasks ship green-fast-suite incrementally.
- **Ruff:** baseline 78 errors as of HEAD `a2d4aa7` (was 80 pre-Phase-7). Plan does NOT introduce new violations; does NOT fix the baseline incidentally.
- **Adversarial review (mandatory):** the standing convention. `copowers:writing-plans` chains directly into Codex review on the plan; iterate to `NO_NEW_CRITICAL_MAJOR`.
- **Schema migration runner discipline:** per Phase 7 hotfix `283d4fa`, `_apply_migration` toggles `foreign_keys=OFF` for the migration duration. Migration 0015 is additive (new table only); inherits the discipline automatically.

---

## §6 — Plan task structure (recommended; implementer adapts)

Sketch for plan tasks; implementer refines + adds discriminating-test specifications per task. Each task ships TDD red → green → commit.

- **Task 0a (research):** Endpoint discovery + cassette-library choice + filename-anchor verification. Document in plan §"Research findings."
- **Task 0b (research):** Rate-limit quota investigation. Document constants in plan.
- **Task 1:** Schema migration 0015 + `FinvizApiCall` dataclass + repo. Migration test, dataclass test, repo tests (insert, list, get_latest_signature). Bump schema_version pin.
- **Task 2:** `swing/integrations/finviz_api.py` `FinvizClient` — token loading, `fetch_screen()` happy path, normalization to canonical 13-column schema. Cassette-based tests (success scenario only).
- **Task 3:** `FinvizClient` error paths — HTTP 4xx, 5xx, 429, network errors, token-missing. Cassette-based tests.
- **Task 4:** Signature-hash computation utility. Discriminating test: same input across pandas-version drift produces same hash; column-set change produces different hash.
- **Task 5:** `_step_finviz_fetch` pipeline step — file-collision skip, API fetch, normalization, signature-hash, persist `finviz_api_calls` row, write CSV, error handling. Cassette-based tests + filesystem-fixture tests.
- **Task 6:** Pipeline step ordering test — `_step_finviz_fetch` runs before `_step_evaluate`.
- **Task 7:** CLI `swing finviz fetch` + `swing finviz status`. Click-based + tested via Click's `CliRunner`.
- **Task 8:** Slow-marked live integration test + skip-if-no-token semantics.
- **Task 9:** Documentation — CLAUDE.md update, cycle-checklist update, plus capture any new project-wide gotcha discovered during dispatch (cassette staleness; token-redaction discipline; etc.).

Plan should specify per-task done-criteria, discriminating tests with EXACT pre-fix vs post-fix expected values (per Phase 7 lesson `"Illustrative" placeholders in discriminating-test plan tasks are vacuous tests in disguise`), and explicit acceptance gates.

Test-count expectation: **+30 to +60 fast tests, biased toward the high end** per Phase 6 lesson on test-count projection. Plan does not tighten acceptance criteria around the optimistic projection.

---

## §7 — Adversarial review watch items

Pass these to `copowers:adversarial-critic` as explicit watch items. The critic should verify each is addressed in the plan.

### Security + token handling

1. **Token never appears in logs / errors / persisted error_message / cassettes.** Verify: a test introduces a known sentinel token; runs full fetch + error paths; greps all log output + DB rows for the sentinel. Test fails if found.
2. **VCR cassette token-redaction.** Cassettes committed to repo MUST have token redacted. Verify: a test reads each committed cassette and asserts `Authorization: Bearer <REDACTED>` (or equivalent) present, raw token absent.
3. **User-config file permission.** Plan flags whether to set restrictive permissions on `user-config.toml` (Windows ACL — likely out of V1 scope; surface as V2 hardening note).

### Multi-path data ingestion (per archived lesson "Multi-path data ingestion needs full-path audit")

4. **Pipeline step + standalone CLI fetcher BOTH write to `data/finviz-inbox/`.** Both must respect file-collision skip; both must persist `finviz_api_calls` rows; both must compute signature-hash. Verify: dedicated test asserts CLI `swing finviz fetch` and `_step_finviz_fetch` produce equivalent state (same row in DB, same CSV on disk) given identical inputs.

### Schema-parity + validator

5. **Emitted CSV passes existing `swing/pipeline/finviz_schema.py` validator.** Verify: a happy-path test reads the API-emitted CSV and runs the existing validator; asserts pass with zero rejection reasons. The integration layer's column-mapping is the contract under test.
6. **API response with unexpected/missing columns.** Verify: cassette with truncated response triggers a typed exception (e.g., `FinvizSchemaParityError`); pipeline step catches + LOGs + skips; `finviz_api_calls.status='error'` with informative `error_message`.

### Drift detection

7. **Signature hash deterministic across runs.** Verify: same input → same hash, irrespective of dict ordering / pandas version / Python version. Plan specifies stable canonicalization (sorted JSON, UTF-8 encoded).
8. **Signature hash sensitivity.** Verify: column-set change produces different hash; first-row-Ticker change produces different hash; first-row-Sector change produces different hash. (Discriminating tests.)
9. **Drift warning emission.** Verify: when latest `finviz_api_calls.signature_hash` differs from current fetch, `WARNING` log fires with both hashes; when it matches, no warning.

### Failure modes + fallback

10. **Pipeline continues after API failure.** Verify: API mock raises `RequestException`; `_step_finviz_fetch` catches; `_step_evaluate` runs after; pipeline does not raise. (Per Q5 lock.)
11. **Manual CSV present → API skipped, pipeline succeeds.** Verify: filesystem fixture creates today's CSV before `_step_finviz_fetch`; step skips fetch; `finviz_api_calls.status='skipped_manual_override'` row inserted; pipeline continues normally.
12. **No CSV from any source → existing pipeline `_step_evaluate` empty-inbox semantics.** Verify: API fails AND no manual CSV present; pipeline behavior matches pre-V1 baseline (existing handling).

### Plan-discipline watch items (per orchestrator-context lessons)

13. **`cfg.X` 3-edit cascade explicitly enumerated.** Plan task adding the Finviz cfg fields lists: sub-dataclass + top-level Config field + Config(...) constructor + toml row + audit of `Config(...)` direct construction in tests. (Per Phase 6 lesson.)
14. **`ensure_schema(db_path)` for fresh DBs in plan-supplied test fixtures.** NOT `connect(db_path)`. (Per Phase 6 lesson.)
15. **No "illustrative" placeholders in discriminating tests.** Every plan-specified discriminating test names exact field + exact pre-fix value + exact post-fix value. (Per Phase 7 writing-plans lesson.)
16. **HX-Redirect target route check.** N/A (no UI work in V1). State explicitly in plan to avoid Codex re-raising.
17. **Test fixture PRAGMA mirrors production.** Migration tests run with `foreign_keys=ON`. (Per Phase 7 Sub-A lesson — even though this migration is additive, discipline is binding.)
18. **Plan does NOT over-state contract vs framework's effective behavior** (per Phase 4 cleanup-remainder lesson). Where plan claims a helper has contract X, verify by reading the actual code, not the plan-author's mental model.

### Slow-marked live integration test

19. **Skip-if-no-token semantics.** Verify: `pytest -m slow` on a CI/dev environment without the operator's token does NOT fail; tests are skipped with a clear reason.
20. **Live test guards against cassette staleness.** Plan documents: when live test fails on schema-shape mismatch, cassettes need re-recording; brief implementer should encounter this as a documented runbook step.

---

## §8 — Done criteria

Plan-drafting dispatch is done when ALL of:

- Plan file exists at `docs/superpowers/plans/2026-05-XX-finviz-api-integration-plan.md` (use ship date).
- All tasks specified per `superpowers:writing-plans` discipline (per-task spec; discriminating-test specs; done criteria; per-task scope ≤ ~1 day implementer time).
- §3 research items resolved with findings documented in plan §"Research findings" (or marked OPEN with explicit rationale).
- All §7 adversarial-review watch items addressed in plan body.
- `copowers:adversarial-critic` reaches `NO_NEW_CRITICAL_MAJOR` verdict on the plan. Expect 3-5 rounds; if rounds exceed 6, surface in return report (per Phase 7 Sub-B lesson on round-count vs chain-convergence).
- Plan + Codex-fix commits land on `main`. (Writing-plans is docs-only; no worktree required.)

---

## §9 — Return report format

When done, paste back to operator:

```
# Finviz API Integration — Writing-Plans Dispatch Return Report

**Plan file:** docs/superpowers/plans/2026-05-XX-finviz-api-integration-plan.md
**Plan commits:** <chain SHA range>
**Codex rounds:** N → NO_NEW_CRITICAL_MAJOR

## Findings disposition (per round)

R1: <count critical>/<major>/<minor>; <one-line summary of fixes landed>
R2: ...
...

## §3 research findings

- Endpoint: <URL + auth + format>
- Rate-limit quota: <findings>
- Cassette library: <choice + rationale>
- Filename-anchor convention: <findings>

## Open questions for orchestrator

(Anything that surfaced during plan drafting OR Codex review that needs operator decision before executing-plans dispatch.)

## Plan task summary

<Task list with one-line per task>

## Test count projection

<Plan-projected test-count delta with rationale>

## Estimated executing-plans dispatches

(Single dispatch OR sub-decomposition recommendation.)

## Notable risks for executing-plans phase

(E.g., live API access required for cassette generation; rate-limit unknowns; etc.)
```

---

## §10 — If you get stuck

- **Endpoint research blocks plan drafting:** if Finviz Elite API docs are insufficient OR require login to access, surface explicitly + halt. Operator dispatches a separate research task or provides direct API access.
- **Token loading conflicts with Phase 5 user-config infrastructure:** read `swing/config.py` + `swing/config_overrides.py` carefully. Phase 5 lessons (archived in `docs/orchestrator-context-archive.md`) include cfg-cascade discipline and `ConfigPageVM.session_date` consistency. If integration cfg loading hits a Phase 5 abstraction that's surprising, halt + surface.
- **Cassette library choice non-obvious:** Default to `pytest-recording`; document rationale in plan; if it has friction (e.g., breaking changes vs project's pytest version), pick `vcrpy` or `responses` and justify.
- **Plan task partitioning unclear:** mirror Phase 6 plan structure (single dispatch, ~10-15 tasks). Phase 7 plan structure (sub-A/B/C decomposition) is too heavy for V1.
- **Codex round count exceeds 6:** review chain-convergence shape per Phase 7 Sub-B lesson; if convergent (each round catches an issue triggered by prior round's fix), continue. If thrashing (each round catches unrelated issues), halt + surface to orchestrator — likely indicates a plan-authoring discipline gap.
- **Operator-context drift:** if any §2 locked decision feels wrong during plan drafting (e.g., implementer discovers the Finviz API mandates JSON not CSV — fundamental contract change), halt + surface to orchestrator. Do NOT silently re-design.

---

## Final reminders

- Brainstorm is **skipped**; do NOT invoke `superpowers:brainstorming`. Operator + orchestrator have already locked V1 scope per the in-thread Q&A summarized in §2.
- This dispatch produces the PLAN, not the implementation. Stop after Codex `NO_NEW_CRITICAL_MAJOR` on the plan.
- Plan file naming: use the ship date of the merge into `main` for the writing-plans dispatch.
- Operator-witnessed verification gate is BINDING for the future executing-plans dispatch (not for this writing-plans dispatch). Plan should specify the gate but not run it.
- Ruff baseline is 78 errors at HEAD `a2d4aa7`; plan does not introduce new violations.
- Test-count projection biases high (Phase 6 lesson); +30 to +60 fast tests, +1-2 slow live tests, is a realistic band.
