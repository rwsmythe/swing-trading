# schwabdev v2.5.1 → v3.x Upgrade Investigation Findings

**Date:** 2026-05-31
**Author:** dependency-upgrade investigation agent (read-only scoping)
**Status:** RECOMMENDATION — see §8
**Current pin:** `schwabdev>=2.4.0,<3.0.0` (`pyproject.toml:20`); installed = `2.5.1`
**Verdict (TL;DR):** **KEEP 2.5.1.** v3 is a near-total rewrite (SQLite tokens, renamed methods, removed sync daemon checker, async split) that breaks our deepest couplings. **It DOES, however, fully obviate the P14.N7 checker-resilience item by construction** — so the recommended path is "keep 2.5.1 + do P14.N7 as a thin best-effort wrapper now; treat v3 as its own future arc."

---

## 1. The schwabdev v3 release landscape

Sources: PyPI history + raw GitHub `main` source + DeepWiki. The GitHub `/releases` page and the docs-site changelog are JS-rendered and did NOT return changelog body text via WebFetch (only headers/dates loaded); all v3 *code* claims below are taken from the **raw source on `main`** (`raw.githubusercontent.com/tylerebowers/Schwabdev/main/...`), not from release notes.

| Version | Released | Notes |
|---|---|---|
| 2.5.0 | 2025-01-28 | last-but-one 2.x |
| **2.5.1** | **2025-08-20** | **our installed/pinned version** |
| 3.0.0 | 2025-12-14 | major rewrite (sync+async split, SQLite tokens, encryption) |
| 3.0.1 | 2026-01-21 | |
| 3.0.2 | 2026-02-10 | |
| 3.0.3 | 2026-02-12 | |
| 3.0.4 | 2026-05-07 | (`main` `__init__.py` version string reads `"3.0.4"`) |
| **3.0.5** | **2026-05-09** | **current latest on PyPI** |

Maturity read: 3.0.0 is ~5.5 months old; 6 releases in the line; the two most recent (3.0.4/3.0.5) landed *two days apart* immediately before our 2026-05-13 pin — i.e., the line was still actively churning when we chose 2.x. Requires-Python `>=3.11` (unchanged; compatible with our 3.14). No published migration guide was retrievable; the repo README/DeepWiki document the new API surface but not a 2→3 delta table.

**This confirms the operator's premise:** v3.0.x (through 3.0.3) was available when we pinned `<3.0.0` on 2026-05-13 and built Phase 11/12 against 2.5.1. The decision to build on 2.x was correct given the couplings documented below.

---

## 2. v3.0.0 headline breaking changes (vs 2.5.x), from raw source

1. **Token storage moved from JSON file → SQLite DB.** 2.5.1 `Tokens(... tokens_file="tokens.json")` writes a JSON file with keys `access_token_issued` / `refresh_token_issued` / `token_dictionary` (`schwabdev/tokens.py:_set_tokens`, installed L132-157). v3 `Tokens(... tokens_db="~/.schwabdev/tokens.db", encryption=None ...)` writes a SQLite DB (table `schwabdev`), with optional Fernet `encryption=` (tokens stored `enc:`-prefixed).
2. **`Client.__init__` signature changed.** 2.5.1: `Client(app_key, app_secret, callback_url, tokens_file="tokens.json", timeout=10, capture_callback=False, use_session=True, call_on_notify=None)` (installed `client.py:23`). v3: `Client(app_key, app_secret, callback_url="https://127.0.0.1", tokens_db="~/.schwabdev/tokens.db", encryption=None, timeout=10, call_on_auth=None, open_browser_for_auth=True)`. Removed: `tokens_file`, `capture_callback`, `use_session`, `call_on_notify`. Added: `tokens_db`, `encryption`, `call_on_auth`, `open_browser_for_auth`.
3. **Sync/async split.** v3 ships `Client` + `ClientAsync` (and `Stream` + `StreamAsync`), all exported from `schwabdev/__init__.py`. (Ironically the operator-observed "v3 was already out" premise: v3's headline feature is the async client.)
4. **Background daemon token checker REMOVED from sync `Client`.** See §3 — the single highest-value finding.
5. **Account method rename: `account_linked()` → `linked_accounts()`.** v3 has NO `account_linked` method. (DeepWiki + raw `client.py` confirm.)
6. **Token public methods made private + reworked.** 2.5.1 public `update_access_token` / `update_refresh_token`; v3 `_update_access_token` / `_update_refresh_token` (private), and `_update_access_token` now wraps the POST in `try/except requests.RequestException` → logs + `conn.rollback()` + `return False` (network-error hardened).
7. **`Tokens` no longer takes `client`; takes `logger` + DB connection.** v3 `Tokens.__init__(app_key, app_secret, callback_url, logger, tokens_db=..., encryption=None, call_for_auth=None, open_browser_for_auth=True)`.

**Unchanged (good news):** the logger name is STILL `logging.getLogger("Schwabdev")` (capital S) inside `Client` (v3 raw `client.py`). Market-data signatures `quotes(symbols, fields, indicative)` and `price_history(symbol, periodType, period, frequencyType, frequency, startDate, endDate, needExtendedHoursData, needPreviousClose)` are IDENTICAL in v3. `account_orders` / `account_details` / `transactions` camelCase param sets are unchanged.

---

## 3. THE KEY QUESTION — the background `checker` thread (P14.N7)

### What 2.5.1 does (the P14.N7 problem)
Installed `schwabdev/client.py:50-56`:
```python
def checker():
    while True:
        if self.tokens.update_tokens() and use_session:
            self._session = requests.Session()
        time.sleep(30)
threading.Thread(target=checker, daemon=True).start()
```
This daemon loop has **no try/except**. `self.tokens.update_tokens()` → `update_access_token()` (installed `tokens.py:204-217`) calls `requests.post(...)` **un-guarded**. A `ConnectionError`/`NameResolutionError` (laptop sleep/wake, DNS hiccup) propagates out of the loop, the thread dies silently (daemon, no logging of thread death), and token auto-refresh stops until the process (`swing web`) restarts. **This is exactly the P14.N7 failure mode.** Our code is aware of it — `auth.py:1779-1782` documents "the daemon-thread checker schwabdev spawns is `daemon=True`".

### What v3 does
- **Synchronous `Client` (the class we use): the daemon `checker` thread is GONE.** v3's sync `Client` refreshes tokens **per-request, synchronously**, inside `_request()`:
  ```python
  def _request(self, method, path, **kwargs):
      self.update_tokens()              # synchronous, before each call
      with self._session_lock: ...
  ```
  There is **no long-lived background thread that can die**. (Confirmed: raw `client.py` has no `threading.Thread`/`checker`/`while True` in sync `Client`; only an `RLock`. DeepWiki: "Unlike the synchronous Client which checks tokens before every request, ClientAsync starts a background asyncio task named `_checker`...".)
- **`_update_access_token` is now network-error-hardened** regardless: `try: ... except requests.RequestException: log + rollback + return False` (raw `tokens.py`). So even the refresh call itself no longer throws on DNS/connection failure.
- `ClientAsync._checker` (async coroutine, every 30s) does still call `update_tokens()` with **no try/except/backoff** — but that's the ASYNC client, which we do NOT and would NOT use.

### Verdict
**v3 FIXES the checker problem by construction (for the sync `Client` we use): P14.N7's specific failure mode is ELIMINATED — there is no daemon checker thread to die, and the refresh call is exception-guarded.** P14.N7 (wrap-the-checker-loop) becomes a no-op against v3's sync client.

**BUT this does NOT argue for upgrading to get the fix** — because (a) the fix arrives bundled with all the §2 breaking changes (high cost), and (b) P14.N7 is independently implementable on 2.5.1 as a thin wrapper for a fraction of the cost. The clean recommendation: **do P14.N7 on 2.5.1 now (cheap), and note that a future v3 migration would let us delete it.** P14.N7 stands as planned on 2.5.1.

---

## 4. Breaking-change × our-usage matrix

Our entire schwabdev surface is confined to `swing/integrations/schwab/` + `swing/cli_schwab.py` + `swing/cli.py` + `swing/pipeline/runner.py` (per full repo grep). We never call `schwabdev.Client.<method>` statically; we always invoke on an instance (`client.quotes(...)`, `client.account_linked()`).

| v3 breaking change | Affects us? | Callsite(s) | Fix needed |
|---|---|---|---|
| `tokens_file=` removed (→ `tokens_db=`) | **YES (5 construction sites)** | `auth.py:762, 901, 1680, 1864`; `pipeline_steps.py:_build...`; `cli_schwab.py:_build_schwabdev_client_for_fetch` (and `runner.py`, `cli.py` callers) | Replace `tokens_file=str(path)` with `tokens_db=str(path)`; rename `_resolve_tokens_db_path` semantics; tokens now SQLite not JSON. |
| Tokens stored in SQLite, not JSON | **YES — deep** | `cli_schwab.py:_read_tokens_metadata` (L469-490) JSON-parses the tokens file to compute `swing schwab status` days-remaining + DEGRADED health; `cli_schwab.py:608+` reads `access_token_issued`/`refresh_token_issued`/`token_dictionary` keys; staleness logic L611-725 | Rewrite `_read_tokens_metadata` + the status renderer to read the v3 SQLite schema (or query `client.tokens` attributes). Non-trivial: ~250 LOC of status/health logic keyed on the JSON shape. |
| Web setup writes JSON tokens file byte-for-byte | **YES — deep** | `auth.py:_write_schwabdev_tokens_file` (L1335-1425) mirrors `Tokens._set_tokens` JSON format so `Client(...)` can load it; `setup_paste_flow_with_callback_url` (L1428+) depends on it | Must rewrite to populate the v3 SQLite tokens DB (or use a v3 token-injection API if one exists). The byte-for-byte JSON mirror is dead on v3. |
| `account_linked()` → `linked_accounts()` | **YES** | `trader.py:270` (`client.account_linked()`); `auth.py:653` (`_stub_call_account_linked`) | Rename both call sites to `client.linked_accounts()`. |
| `update_access_token`/`update_refresh_token` → private | **MAYBE** | `force_refresh` calls `client.tokens.update_tokens(force_access_token=True)` (`auth.py:1879`) — `update_tokens` is still public in v3, so likely OK; but `_post_oauth_token` mirror in `_exchange_code_for_tokens` (`auth.py:1176+`) is our own copy and is fine. | Verify `update_tokens(force_access_token=...)` kwarg names unchanged in v3 (signature in §2 item 6 shows `update_tokens(force_access_token, force_refresh_token)` retained). Low risk. |
| Constructor kwargs `capture_callback`/`use_session`/`call_on_notify` removed | **NO (we never pass them)** | We pass only `app_key, app_secret, callback_url, tokens_file, timeout` | Just the `tokens_file`→`tokens_db` rename (above). |
| Logger name `"Schwabdev"` | **NO — unchanged** | Layer-2 redaction `setLogRecordFactory` keys on `"Schwabdev"` | None. (Re-verify after upgrade as a gotcha-revalidation item.) |
| `price_history` minute-default footgun | **NO change** | `marketdata.py:379` passes all 4 period kwargs explicitly | None (still must pass explicitly; v3 defaults are all `None` per §2). |
| `quotes`/`price_history`/`account_orders`/`account_details`/`transactions` signatures | **NO — identical in v3** | `marketdata.py`, `trader.py` | None. |
| Signature-pin tests | **YES (test breakage)** | `test_schwab_trader_kwarg_signatures.py:37` does `inspect.signature(schwabdev.Client.account_linked)` → **AttributeError on v3** (method gone) — test ERRORS | Rename the pinned method to `linked_accounts`. The other 6 pin tests (quotes/price_history/account_orders/account_details/transactions) PASS unchanged on v3. |

### Test-suite impact
- `tests/integrations/test_schwab_trader_kwarg_signatures.py::test_account_linked_no_kwargs_required` — **ERRORS** on v3 (`schwabdev.Client.account_linked` no longer exists).
- All other kwarg-signature pins pass on v3 (signatures verified identical).
- Any test that constructs/monkeypatches `schwabdev.Client(... tokens_file=...)` or asserts the JSON tokens-file shape needs updating.
- Mock-based trader/marketdata tests are unaffected (they stub the whole call).

---

## 5. L2 LOCK impact

The L2 LOCK test (`tests/integration/test_l2_lock_source_grep.py`) greps the **literal substring `schwabdev.Client.`** in `swing/` and Counter-compares HEAD vs baseline `bf7e071`, failing on any NEW or inflated `(path, line_text)`.

**Key finding:** EVERY current match of `schwabdev.Client.` in `swing/` is a **comment, docstring, or type annotation** — NOT a method-invocation call site. We invoke methods on instances (`client.account_linked()`, `client.quotes(...)`), which the pattern does NOT match. (Verified via `git grep schwabdev.Client. bf7e071 -- swing/` and at HEAD — both return only prose/annotation lines like `self._schwabdev_client: schwabdev.Client | None`, `-> schwabdev.Client:`, and docstrings.)

**Implications for a v3 upgrade:**
- The method renames (`account_linked`→`linked_accounts`) happen on *instance* calls (`client.account_linked()`), which the grep does NOT see → **no L2 trip from the renames themselves.**
- Risk is from **comment/docstring churn**: a migration will necessarily rewrite many of the docstrings/comments that currently contain `schwabdev.Client(...)` (e.g., `auth.py` module docstring, `pipeline_steps.py:90-93` which embeds the literal 2.5.1 signature). Because the test is a **multiset subset check (HEAD ⊆ baseline)**, *editing* an existing matched comment line changes its `line_text` key → becomes a NEW key → **FAILS the test**. Adding/clarifying comments mentioning `schwabdev.Client(...)` also fails it.
- **Conclusion:** A v3 migration would almost certainly require **re-anchoring `L2_LOCK_BASELINE_SHA`** to the migration commit (or expanding the whitelist). This is a deliberate, operator-visible action — the test is doing its job (it's a doc/intent tripwire as much as a call-site one). Flag: the migration brief MUST budget for an L2 baseline re-anchor + a fresh operator sign-off that the new call-site set is intentional. The lock's *spirit* (zero new Schwab API endpoints) is preserved by a v3 upgrade — we'd call the same endpoints via renamed methods.

---

## 6. Migration effort + risk

**Files that change (estimate):**
- `pyproject.toml` (pin bump) — 1 line.
- `swing/integrations/schwab/auth.py` — **heaviest.** `tokens_file`→`tokens_db` (4 sites); rewrite `_write_schwabdev_tokens_file` (JSON→SQLite, ~90 LOC); `_stub_call_account_linked` rename; revisit `_rename_stale_tokens_db` (still valid — it renames a file, and a SQLite DB is still a file, but `.db` semantics + WAL/SHM siblings need handling); `construct_authenticated_client` + both setup flows + `force_refresh`. ~150-250 LOC touched.
- `swing/cli_schwab.py` — **heavy.** `_read_tokens_metadata` + status/days-remaining/DEGRADED renderer rewrite (JSON-key parsing → SQLite read). ~150-250 LOC. Plus `_build_schwabdev_client_for_fetch` constructor kwarg.
- `swing/integrations/schwab/trader.py` — `account_linked`→`linked_accounts` (1 call + comments).
- `swing/integrations/schwab/pipeline_steps.py` — constructor kwarg + signature-doc comment (L90-93).
- `swing/pipeline/runner.py`, `swing/cli.py` — constructor call paths.
- Tests: `test_schwab_trader_kwarg_signatures.py` (rename pin); any tokens-file JSON-shape fixtures; web-setup tests around `_write_schwabdev_tokens_file`; status-command tests. ~10-25 tests touched/rewritten.
- `tests/integration/test_l2_lock_source_grep.py` — re-anchor baseline SHA.
- Gotcha re-validation: logger-name (`"Schwabdev"` — unchanged, re-confirm), `update_tokens` no-raise semantics, the `setup`-needs-clean-DB behavior (changes — v3 SQLite, the self-heal rename targets `.db`+WAL), the 7-day refresh TTL model (we hardcode `7*24*3600` in `cli_schwab.py:46` — verify v3 still 7d).

**Rough scale:** ~400-600 LOC touched across ~8 source files + ~15-25 tests; a focused sub-bundle (brainstorm → plan → execute with Codex convergence), NOT a one-commit bump. The **tokens-storage rewrite (JSON→SQLite) is the dominant risk** — it touches OAuth state at rest for a live brokerage integration, plus the operator's existing `~/swing-data/schwab-tokens.{env}.db` files would need a one-time re-`setup` (the old JSON-format DBs are unreadable by v3). Schema-at-rest change to live OAuth tokens warrants operator-witnessed browser + CLI gates.

**Risk profile:** 3.x is moderately mature (~5.5 months, 6 releases) but the line was actively churning days before our pin; a brokerage integration is high-stakes (token loss = locked-out trading). Encryption (`encryption=` Fernet) is a genuine v3 *benefit* that retires our CLAUDE.md "plaintext OAuth at rest (V1)" gotcha — but that's an enhancement, not a forcing function.

---

## 7. Net assessment

- **Cost to upgrade:** high (token-storage rewrite + status-command rewrite + setup-flow rewrite + L2 re-anchor + live OAuth re-setup + operator-gated brokerage testing).
- **Benefit to upgrade:** (a) P14.N7 obviated (but cheaply solvable on 2.5.1 anyway); (b) optional token-DB encryption (retires a V1 gotcha); (c) async support (we have no async need); (d) staying current.
- **Forcing functions:** NONE. 2.5.1 is `Production/Stable`, works today, all 6 of 7 signature pins already match v3, and the one behavior we'd most want fixed (checker resilience) is independently fixable.

---

## 8. Recommendation

**KEEP schwabdev 2.5.1. Implement P14.N7 as planned (thin best-effort wrapper around the 2.5.1 daemon checker loop) now.** Defer v3 to its own dedicated arc after Phase 14 close-out.

**Sequencing:**
1. **Now / SB5.5 (as planned):** P14.N7 on 2.5.1 — wrap the daemon `checker` loop (or our access to it) so a `ConnectionError`/DNS failure during `update_tokens()` is caught + logged + the loop survives (retry next 30s tick), rather than the daemon thread dying silently. Small (a guarded wrapper + a test simulating a raised `ConnectionError`). This is the correct V1 fix and is independent of the v3 question.
2. **Phase 14 close-out:** unchanged; do NOT entangle a v3 migration with the close-out tail.
3. **Future, as its own bundle (post-Phase-14):** "schwabdev v3 migration" arc — token-storage JSON→SQLite, `account_linked`→`linked_accounts`, constructor kwargs, status-command rewrite, L2 baseline re-anchor, opt-in Fernet encryption, operator-witnessed re-`setup` + browser/CLI gates. At that point P14.N7's wrapper is deleted (v3 sync client has no daemon checker to guard).

**What would change this recommendation:** if the operator decides to adopt **token-DB encryption** as a near-term V1 security requirement (it retires the "plaintext OAuth at rest" gotcha), that becomes a genuine forcing function and the v3 migration should be pulled forward — but it would still be its own arc, not bundled into Phase 14 close-out.

**One resolving check, if desired:** confirm against a live `pip install schwabdev==3.0.5` in a throwaway venv that (a) `inspect.signature(schwabdev.Client.__init__)` matches the `main`-branch signature quoted here (the `main` `__init__.py` reads `3.0.4`; the 3.0.5 tag may differ slightly), and (b) `schwabdev.Client.linked_accounts` exists and `account_linked` does not. This investigation read the `main` branch raw source, which corresponds to 3.0.4/3.0.5-era code; a venv pin to the exact 3.0.5 sdist removes the last residual `main`-vs-tag uncertainty.

---

### Evidence index (file:line / URL)
- Installed 2.5.1 source: `C:\Users\rwsmy\AppData\Roaming\Python\Python314\site-packages\schwabdev\{client.py,tokens.py,__init__.py}`. Checker thread: `client.py:50-56`. Constructor: `client.py:23`. JSON tokens write: `tokens.py:132-157`. Un-guarded refresh POST: `tokens.py:204-217`.
- v3 raw source (`main` branch): `https://raw.githubusercontent.com/tylerebowers/Schwabdev/main/schwabdev/{client.py,tokens.py,__init__.py}` — confirms SQLite tokens, removed sync checker, `linked_accounts`, guarded `_update_access_token`, retained `"Schwabdev"` logger + identical market-data signatures.
- PyPI version history + latest 3.0.5 (2026-05-09): `https://pypi.org/project/schwabdev/`.
- DeepWiki async/sync architecture: `https://deepwiki.com/tylerebowers/Schwabdev/7.1-async-client-and-streamer`.
- Our couplings: `swing/integrations/schwab/auth.py` (construction L758/897/1680/1860, `_write_schwabdev_tokens_file` L1335, `_stub_call_account_linked` L638/653, `force_refresh` L1879, daemon-checker note L1779-1782); `swing/integrations/schwab/trader.py:270` (`account_linked`); `swing/integrations/schwab/marketdata.py:379` (`price_history` camelCase); `swing/cli_schwab.py:46` (7d TTL), `:469-490` (`_read_tokens_metadata` JSON parse), `:608-725` (status/health JSON-key logic).
- L2 LOCK: `tests/integration/test_l2_lock_source_grep.py` (baseline `bf7e071`, pattern `schwabdev.Client.`, Counter-subset check). All matches are prose/annotation, not call sites.
- Signature pins: `tests/integrations/test_schwab_trader_kwarg_signatures.py:37` (breaks on v3), `tests/integrations/test_schwab_marketdata_kwarg_signatures.py` (passes on v3).
- Pin: `pyproject.toml:20` (`schwabdev>=2.4.0,<3.0.0`).
