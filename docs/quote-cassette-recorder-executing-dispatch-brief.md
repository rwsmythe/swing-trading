# Executing Dispatch Brief — Schwab Quote-Cassette Recorder (Gate 4 enablement)

**Arc:** Phase 15 / data-integrity arc Slice-B Gate 4 enablement — build the recording mechanism for the live-quote cassette so the operator's market-open step is turnkey.
**Cycle stage:** **focused `copowers:executing-plans`** — the design is fully scoped below (orchestrator pre-scoped the mechanism, operator-requested). Implement TDD, then Codex on the diff to convergence. NOT a brainstorm/writing-plans cycle (dev-tooling, pinned design).
**Branch-from:** main HEAD at worktree creation (currently `911ce31e`; re-verify with `git log --oneline -3` — main may have advanced via operator research commits; branch from the live HEAD).
**Schema:** NONE — v24 holds. Dev-tooling (`scripts/` + a test + a runbook section); no `swing/` production runtime change.
**Deliverable:** `scripts/record_schwab_quote_cassette.py` + a MOCK-based test + a quote section in `docs/runbooks/schwab-cassette-recording.md`, Codex-converged + `.copowers-findings.md`. **Mergeable now** (the test uses mocks — NO live calls; fast-suite-safe). Then STOP — do NOT merge.

---

## 1. Mandate (one line)

Build a small dedicated recorder that produces the sanitized VCR cassette `tests/integrations/schwab/cassettes/quote_regular_fields.yaml` from one live `client.quotes(...)` call — so that at market open the operator runs ONE command, confirms the `regularMarket*` fields + leak-clean, commits, and the slow `test_quote_fields_live.py` (Gate 4) passes, fully closing the data-integrity arc.

---

## 2. Grounding (orchestrator-verified on HEAD `911ce31e` — re-confirm)

- **The gate test** ([tests/integrations/schwab/test_quote_fields_live.py](../tests/integrations/schwab/test_quote_fields_live.py), `@pytest.mark.slow`) does a **pure substring grep**: asserts `<this_dir>/cassettes/quote_regular_fields.yaml` exists and its text contains `regularMarketLastPrice`, `regularMarketTradeTime`, `regularMarketBidPrice`, `regularMarketAskPrice`. No VCR replay. So the cassette path is **exactly** `tests/integrations/schwab/cassettes/quote_regular_fields.yaml` (note: `schwab/cassettes`, the REVERSE of the order script's `tests/integrations/cassettes/schwab/`). The dir is **missing** — the recorder must `mkdir(parents=True, exist_ok=True)`.
- **Reuse — do NOT duplicate** (import from `scripts/record_schwab_cassettes.py`):
  - `_bootstrap_authenticated_client(*, environment, config_path=None) -> (client, cfg)` — the auth path (load cfg → apply_overrides → resolve creds → construct client). Same as `swing schwab fetch`.
  - `_load_shared_vcr_kwargs() -> dict` — imports `tests/conftest.py:vcr_config` (the SINGLE SOURCE OF TRUTH sanitization: filter_headers + filter_query_parameters + `before_record_response` masking tokens/accountNumber/accountHash + `before_record_request` URI-path accountHash scrub). It **fails closed** (`SystemExit`) if conftest can't be imported — preserve that; **NEVER inline a fallback filter dict** (that risks committing the operator's accountHash/tokens — the exact failure the order script refuses).
  - `_scan_cassette_for_sentinel_leak(path) -> list[str]` — the leak-audit regex catalog (`_LEAK_PATTERNS`).
  - `_resolve_repo_root()` — for the cassette path.
- **The quote call:** `client.quotes(symbols=<list>, fields="quote")` ([marketdata.py:337](../swing/integrations/schwab/marketdata.py); `fields="quote"` already the default @289) — schwabdev snake_case kwargs (`symbols`/`fields`; CLAUDE.md gotcha family). This is an HTTP GET that `vcr.use_cassette` intercepts. (You call `client.quotes` DIRECTLY inside the cassette context — not `get_quotes_batch`, which maps + needs a `conn`; the raw HTTP interaction is what the cassette captures, and the substring grep just needs the response body fields.)
- **The runbook** ([docs/runbooks/schwab-cassette-recording.md](../docs/runbooks/schwab-cassette-recording.md)) is order-only (zero quote coverage); add a quote section.

---

## 3. The recorder design (`scripts/record_schwab_quote_cassette.py`)

Mirror the structure + discipline of `scripts/record_schwab_cassettes.py`:

- **argparse:** `--environment {production,sandbox}` (REQUIRED), `--symbols` (default `"AAPL"`, comma-separated → list), `--config` (default `swing.config.toml`). Deferred heavy imports (keep `--help` snappy, like the order script).
- **`main(argv)`:**
  1. `_bootstrap_authenticated_client(environment=args.environment, config_path=Path(args.config))` → `(client, cfg)`.
  2. `vcr_kwargs = _load_shared_vcr_kwargs()` (fails closed).
  3. Resolve `cassette = _resolve_repo_root() / "tests/integrations/schwab/cassettes/quote_regular_fields.yaml"`; `cassette.parent.mkdir(parents=True, exist_ok=True)`.
  4. **Delete any existing cassette first** (mirror the order script's Codex R3 fix — `record_mode="new_episodes"` APPENDS; force a single-interaction cassette).
  5. Record: `with vcr.use_cassette(str(cassette), record_mode="new_episodes", **vcr_kwargs): resp = client.quotes(symbols=symbols, fields="quote")` (capture `resp.json()` / list for the printout).
  6. **Post-record validation against the PERSISTED file** (re-read from disk, mirror the order script's discipline): read the written cassette text; assert all 4 `regularMarket*` field names present. On absence → DELETE the cassette + non-zero exit + operator-actionable message ("`fields="quote"` did not return bid/ask; re-run with a wider selection [`fields="all"`] OR accept that the Schwab quote path drops to yfinance per **OQ-3** — B2 is L1-correct either way"). Consider a `--fields` arg (default `"quote"`) so the operator can re-run with `"all"` without editing code.
  7. **Leak-scan:** `_scan_cassette_for_sentinel_leak(cassette)` → on findings, DELETE + non-zero exit + actionable message (extend `tests/conftest.py:vcr_config` + re-run).
  8. On success: print `OK: recorded + validated <relpath> (symbols=...)` + the 4-field confirmation; exit 0.
- **ASCII-only stdout/stderr** (Windows cp1252 gotcha — no non-ASCII glyphs in any print).

---

## 4. Tests (MOCK-based; NO live calls — mirror `tests/integrations/test_record_schwab_cassettes_script.py`)

The full `vcr.use_cassette` + `client.quotes` live recording is operator-run (needs live tokens) — do NOT live-call in tests. Test the *seams* + *helpers*:
- `--help` argparse smoke (subprocess, like the order test).
- The shared-filter import smoke (`_load_shared_vcr_kwargs()` returns a dict with the sanitization hooks).
- **The 4-field validation** function (extract it as a testable unit, e.g. `_validate_quote_cassette_has_regular_fields(cassette_path) -> (bool, msg)`): pass a synthetic cassette YAML text containing all 4 fields → `(True, "")`; pass one missing `regularMarketBidPrice` → `(False, <actionable msg mentioning OQ-3 / fields="all">)`.
- **Leak-scan** on a synthetic cassette containing an unsanitized token → returns a finding (reuse `_scan_cassette_for_sentinel_leak`).
- **The bootstrap ordering** (optional, if you mirror the order test's thin-helper patching): patch the imported `_bootstrap_authenticated_client` + `client.quotes` (mock returning a synthetic response with the 4 fields) + a tmp cassette path, assert the record function writes + validates + leak-scans. If full vcr-in-test is awkward (vcr needs a real HTTP layer to intercept; a mocked `client.quotes` bypasses it), prefer testing the validation + leak-scan + path logic directly (as the order test does) rather than forcing a fake-HTTP vcr capture.

Per `feedback_regression_test_arithmetic`, the validation test must distinguish: all-4-present → pass, one-missing → fail with the right message.

---

## 5. Runbook section (add to `docs/runbooks/schwab-cassette-recording.md`)

A "Quote cassette (Gate 4 / OQ-3)" section: the 3-step market-open workflow — (1) `python scripts/record_schwab_quote_cassette.py --environment production` during regular hours with live tokens; (2) confirm the printout shows the 4 `regularMarket*` fields + leak-clean, `git add` the cassette; (3) `pytest tests/integrations/schwab/test_quote_fields_live.py` (slow) passes → data-integrity arc closes. Document the **OQ-3 decision**: if bid/ask are absent under `fields="quote"`, re-run with `--fields all`, OR accept the yfinance-drop (B2 stays L1-correct). Note the cassette is committed (sanitized — no accountHash/tokens, enforced by the shared `vcr_config` + leak-scan).

---

## 6. Locks / invariants

- **Schema NONE** (v24). Dev-tooling only — no `swing/` production runtime change. The cassette PATH must EXACTLY match the gate test (`tests/integrations/schwab/cassettes/quote_regular_fields.yaml`).
- **Sanitization is non-negotiable:** reuse `tests/conftest.py:vcr_config` via `_load_shared_vcr_kwargs` (fail-closed); the leak-scan is the belt. A committed cassette MUST carry zero accountHash/tokens/account numbers. This is the whole point — a recording that leaks secrets is a critical failure.
- **schwabdev kwarg discipline:** `client.quotes(symbols=, fields=)` snake_case.
- **NO live calls in tests** (mock the client/seams) → the new test is fast-suite-safe; the slow `test_quote_fields_live.py` stays skipped-by-existence until the operator records.
- ASCII-only user-facing strings (Windows cp1252).
- Do NOT modify `scripts/record_schwab_cassettes.py`'s behavior (import its helpers read-only; if a helper needs to be shared, import it — don't fork it).

## 7. Process (binding)

- **TDD:** failing test → see fail → implement → see pass → `ruff check swing/ scripts/` → commit (conventional, NO `Co-Authored-By`, NO `--no-verify`, final `-m` paragraph plain prose).
- **Full fast suite + ruff** at the end: `python -m pytest -m "not slow" -q` (baseline ≈7246 — report the ACTUAL count + net-new delta; isolate the 3 known xdist flakes with `-n0` if they appear) + `ruff check swing/ scripts/`.
- **Codex review to convergence** on the diff (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED). **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`) + tell Codex not to run git. **Persist BOTH prompts AND responses** to gitignored `.copowers-findings.md`. (Adversarial focus: the sanitization fail-closed path + leak-scan completeness — a leak here is critical; the cassette-path exactness; the OQ-3 absent-field handling.)
- **Degraded-harness guard** (`feedback_degraded_harness_sequential_tool_calls`): if mid-batch tool cancellations, drop to single sequential calls + re-Read before each Edit.

## 8. Return report (then STOP — do NOT merge)

Return: the commit SHA(s) + messages; the full-suite result (ACTUAL count + net-new delta + any isolated flakes); `ruff` clean; the Codex convergence verdict (round count + final line); confirmation the recorder writes to the EXACT gate-test path + reuses the shared sanitization (fail-closed) + leak-scan; and any deviation. Then STOP — merge is the orchestrator's action after QA, and the live recording is the operator's market-open step (NOT yours; do NOT attempt a live Schwab call).

## 9. What this is NOT

NOT the live recording (operator's market-open step). NOT a `swing/` production change. NOT a modification of the order-cassette script's behavior. NOT a schema change. NOT (a) #16 / (b) Issue #3 (both closed). The OQ-3 fields decision is the operator's at record time — the recorder surfaces it, it does not pre-decide.
