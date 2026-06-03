# schwabdev 2.5.1 -> 3.0.5 Upgrade -- Migration Design Spec

**Date:** 2026-06-02
**Phase:** 15 (FIRST commissioned Phase-15 arc)
**Status:** BRAINSTORM DRAFT -- design only, no code
**Author:** schwabdev-v3-upgrade brainstorming implementer (worktree `schwabdev-v3-upgrade-brainstorming`, branched from main `f1b008d`)
**Inputs:** `docs/schwabdev-v3-upgrade-brainstorming-dispatch-brief.md` (binding contract) + `docs/schwabdev-v3-upgrade-investigation-findings.md` (`9d4f6a4`, the substrate) + the installed-3.0.5 surface (throwaway venv `~/schwabdev305venv`, per L5)
**Deliverable target:** the writing-plans phase derives an implementation plan from this spec.

---

## §1 Architecture overview -- what v3 changes, and what this arc is

This is a **dependency migration on the L2-LOCKED Schwab surface**, not a new-feature arc. We move the project's only brokerage dependency from `schwabdev 2.5.1` to `3.0.5` (latest on PyPI 2026-06-02). The Schwab REST API surface we consume is **unchanged** (same endpoints, same camelCase market-data signatures); what changes is *how schwabdev itself stores tokens and names a few methods*.

**The five things v3 changes that touch us** (all re-confirmed against the INSTALLED 3.0.5 source -- see §3 evidence column):

1. **Token storage: JSON file -> SQLite DB.** 2.5.1 wrote a JSON file (`access_token_issued` / `refresh_token_issued` / `token_dictionary`). v3 writes a SQLite DB (table `schwabdev`, single row, 8 columns). The constructor kwarg renames `tokens_file=` -> `tokens_db=`. This is the dominant change and the dominant risk (it is live brokerage OAuth state at rest).
2. **`account_linked()` -> `linked_accounts()`** (same endpoint `/trader/v1/accounts/accountNumbers`; method renamed).
3. **`Client.__init__` signature changed** (drops `capture_callback`/`use_session`/`call_on_notify` -- we never passed them; adds `tokens_db`/`encryption`/`call_on_auth`/`open_browser_for_auth`).
4. **The sync `Client` daemon checker thread is GONE.** v3's sync `Client` refreshes tokens synchronously, per-request, inside `_request()` (installed `client.py:156-159`). There is no long-lived thread to die. This **eliminates the P14.N7 failure mode by construction** -> the now-SHIPPED P14.N7 daemon-checker resilience wrapper becomes dead code, and the F-1 web checker-liveness badge loses its data source.
5. **Optional Fernet token-at-rest encryption** via `encryption=<key>` -- the pull-forward incentive; retires the CLAUDE.md "plaintext OAuth at rest (V1)" gotcha.

**Unchanged (the good news, re-confirmed at 3.0.5):** logger name is still `logging.getLogger("Schwabdev")` (capital-S, installed `client.py:41`); `update_tokens(force_access_token, force_refresh_token) -> bool` is retained and still public; market-data signatures (`quotes`, `price_history` with 8 camelCase kwargs) are byte-identical; refresh-token TTL is still 7 days (installed `tokens.py:64`: `7 * 24 * 60 * 60`).

**Net architectural shape of the migration:**
- `swing/integrations/schwab/auth.py` is the heaviest touch (4 construction sites; the `_write_schwabdev_tokens_file` JSON-mirror -> v3-SQLite writer; the `_stub_call_account_linked` rename; the **`revoke_and_delete` logout path that JSON-parses the tokens file (§5.5)**; the `_rename_stale_tokens_db` self-heal, which renames ONLY the `.db` and needs a sidecar review for v3 -- it does NOT currently loop `-journal`/`-wal`/`-shm` siblings, contra an earlier draft claim).
- `swing/cli_schwab.py` is the second-heaviest (the `_read_tokens_metadata` JSON-parse -> v3-SQLite read; the `status` health renderer that consumes the JSON keys; the checker-liveness reporting block).
- The P14.N7 wrapper + the F-1 badge + their full blast radius (every base-layout VM, `base.html.j2`, `app.py` install, 6 test files) are removed/reconciled in ONE atomic task.
- The L2 LOCK baseline is **re-anchored** (the FIRST-EVER baseline move) -- audited, operator-signed, with a manual endpoint-set diff proving zero new endpoints.

---

## §2 Pre-locked decisions + L1-L7 (verbatim from the brief, with this spec's compliance note)

- **L1 -- scope = the 2.5.1 -> 3.0.5 migration ONLY.** Re-pin; fix every breaking change; remove the P14.N7 wrapper; reconcile the F-1 badge; update the signature-pin tests; the L2 re-anchor; the operator re-setup UX; (optionally) Fernet. NO new Schwab endpoints/features; do NOT re-touch A-3/SB5.5 (shipped) except the F-1 badge disposition. *Compliance: every §3 touch-list entry maps to one of these; nothing else.*
- **L2 -- RE-ANCHORED BY THIS ARC (the first-ever baseline move; requires EXPLICIT operator sign-off).** The lock = ZERO new Schwab API *endpoints*. The migration changes HOW (renames/storage), not WHICH -- spirit preserved. The source-grep WILL trip on docstring/comment churn. §7 designs the re-anchor: bump `L2_LOCK_BASELINE_SHA` to post-migration HEAD, audited rationale, a MANUAL endpoint-set diff (not just the grep), an operator sign-off gate (OQ-4). *Compliance: §7.*
- **L3 -- NO swing-DB schema change.** schwabdev's tokens DB is its own SQLite under `~/swing-data/`, separate from `swing.db`. `EXPECTED_SCHEMA_VERSION` stays 23; no `00NN` migration. *Compliance: §8, confirmed.*
- **L4 -- preserve EVERY Schwab gotcha post-upgrade.** Logger-name redaction; `update_tokens` post-call-state; sandbox `environment=='production'` domain-row gate; `price_history` daily-bar discipline; typed-error audit-row close; source-artifact `schwab_api:call/{id}` shape. *Compliance: §10 test plan has one re-validation per gotcha.*
- **L5 -- EXACT-3.0.5-surface verification REQUIRED.** Done: installed `schwabdev==3.0.5` in `~/schwabdev305venv` and read the installed source. §3 cites installed-3.0.5 file:line. The findings doc (which read GitHub `main`, version string `3.0.4`) is CONFIRMED on every point; one cosmetic divergence noted (§3 note A). *Compliance: §3.*
- **L6 -- P14.N7 + F-1 are now SHIPPED surfaces to RECONCILE.** Remove the daemon-checker wrapper + wiring + tests; design the F-1 badge disposition (delete vs rewire). *Compliance: §5.3 + OQ-5.*
- **L7 -- the binding gate is an operator LIVE-OAuth re-setup smoke** (`logout` -> `setup` on v3 -> `status` -> `fetch`). Mock tests necessary but INSUFFICIENT for the auth/token path. *Compliance: §10 gate G7.*

---

## §3 Module touch list (grounded in the findings doc + the installed 3.0.5 surface)

Legend: **[C]** construction/kwarg change / **[R]** logic rewrite / **[D]** delete / **[T]** test.
Evidence column cites installed 3.0.5 (`~/schwabdev305venv/Lib/site-packages/schwabdev/...`) OR our source at `f1b008d`.

| File | Change | Detail | Evidence (installed-3.0.5 / our source) |
|---|---|---|---|
| `pyproject.toml:20` | **[C]** | `schwabdev>=2.4.0,<3.0.0` -> v3 range (OQ-3). `cryptography` becomes a transitive dep (Fernet); pin directly only if §6 Fernet ships. | our `pyproject.toml:20`; venv pulled `cryptography-48.0.0` transitively |
| `swing/integrations/schwab/auth.py` (4 sites) | **[C]** | `tokens_file=str(tokens_path)` -> `tokens_db=str(tokens_path)` at `:762, :897(ish), :1680, :1860`. Keep `app_key/app_secret/callback_url/timeout`; we never pass the removed kwargs. | construction site read at our `auth.py:758-764`; `Client.__init__` installed `client.py:123` |
| `swing/integrations/schwab/auth.py` `_write_schwabdev_tokens_file:1335` | **[R]** | JSON-mirror writer -> v3-SQLite writer (INSERT the 8-col `schwabdev` row mirroring `_set_tokens`). §5.1. | our `auth.py:1335-1425`; v3 `_set_tokens` installed `tokens.py:193-250` + table DDL `tokens.py:80-91` |
| `swing/integrations/schwab/auth.py` `_stub_call_account_linked:638` + `:653` | **[R]** | `client.account_linked()` -> `client.linked_accounts()`. Audit endpoint label `accounts.linked` unchanged (same REST path). | our `auth.py:653`; v3 `linked_accounts` installed `client.py:181-189` |
| `swing/integrations/schwab/auth.py` `_rename_stale_tokens_db:299` | **[R]** (verify) | Renames ONLY `tokens_db_path` (a single `os.replace`, our `auth.py:299-368`) -- it does NOT loop `-journal`/`-wal`/`-shm` siblings. v3 uses a rollback journal (sets `busy_timeout` only, NO `WAL` pragma -- installed `tokens.py:92`). A `-journal` orphaned by the rename-aside is inert (SQLite applies a journal only to a present same-named DB), but the plan must either add sibling cleanup OR assert inertness explicitly (gotcha #11 atomic-consistency). | our `auth.py:299-368`; v3 connect installed `tokens.py:76,92` |
| `swing/integrations/schwab/auth.py` `revoke_and_delete:2098-2129` (the `swing schwab logout` path) | **[R]** (CRITICAL) | JSON-parses the tokens file to extract `token_dictionary.refresh_token` (`json.load` at `:2117-2119`) before POSTing `/v1/oauth/revoke`. On a v3 SQLite DB this raises -> `refresh_token=None` -> `:2129` records error + RAISES `SchwabApiError` -> the DB is NEVER renamed. **Breaks `swing schwab logout` on v3 -- which is step 1 of the L7 gate AND the §11 rollback.** Rewrite to read+decrypt the refresh_token from the v3 SQLite DB (§5.5). | our `auth.py:2098-2189`; v3 schema installed `tokens.py:80-91` |
| `swing/integrations/schwab/auth.py` -- NEW COMPREHENSIVE preflight `_assert_v3_tokens_db_loadable_or_raise` | **[R]** (NEW) | A comprehensive preflight on every NON-setup construction path (`construct_authenticated_client` fetch, `force_refresh`, the web/pipeline client builders) -- NOT the setup paths (setup uses `_rename_stale_tokens_db` + writes a fresh DB). It reads the v3 DB directly and asserts: (1) v3 `schwabdev` table present (else old/foreign-format crash averted -> clean error); (2) one token row exists; (3) refresh-token FRESH (`rt_delta >= 3630s`) so construction won't force the interactive refresh; (4) decryptability driven by the column `enc:` prefix, not config (key-loss gap). Any failure -> clean `SchwabAuthError(... run logout+setup)`, NEVER an unwrapped `DatabaseError` or a blocked `input()`. v3 `Client.__init__` connects + `CREATE TABLE` immediately (installed `tokens.py:43,76,80`) and forces interactive refresh on stale/undecryptable rows (`tokens.py:94-103,293,421`). §5.4. | v3 `tokens.py:43,76,80,94-103,293,421` |
| `swing/integrations/schwab/trader.py:270` | **[R]** | `client_method=lambda: client.account_linked()` -> `client.linked_accounts()`. Internal mapper name `map_account_linked_to_hash_set` may stay (not a schwabdev call). | our `trader.py:270` |
| `swing/integrations/schwab/marketdata.py:378` | **none** | `get_price_history` passes 8 camelCase kwargs explicitly; identical in v3 (still MUST pass explicitly -- daily-bar discipline). | v3 `price_history` installed `client.py:472-501` |
| `swing/integrations/schwab/pipeline_steps.py:85-111` | **[C]** | Constructor kwarg + the signature-doc comment that embeds the 2.5.1 `tokens_file=` signature (L2-churn line). | our `pipeline_steps.py:85-111` |
| `swing/pipeline/runner.py:206,281` + `swing/cli.py` | **[C]** | Constructor call paths -> `tokens_db=`. | our `runner.py:206` |
| `swing/cli_schwab.py` `_read_tokens_metadata:469` | **[R]** | JSON-parse -> read v3 SQLite (`SELECT access_token_issued, refresh_token_issued, expires_in, refresh_token FROM schwabdev LIMIT 1`). §5.2. | our `cli_schwab.py:469-490`; v3 schema installed `tokens.py:80-91` |
| `swing/cli_schwab.py` `status`/health `:606-900` | **[R]** | Re-map the DEGRADED-health signals from JSON keys to v3 columns; `expires_in` moves from `token_dictionary.expires_in` (nested) to a top-level column; refresh-bytes-presence check reads the `refresh_token` column (non-empty; `enc:`-prefix OK, no decrypt needed). | our `cli_schwab.py:611-725, 881-893` |
| `swing/cli_schwab.py` `_REFRESH_TOKEN_TTL_SECONDS:46` | **none** | `7*24*3600` still correct (v3 `tokens.py:64`). Add a discriminating test asserting v3 still 7d. | our `cli_schwab.py:46`; v3 `tokens.py:64` |
| `swing/cli_schwab.py` checker-liveness block `:837-842` | **[D]/[R]** | Part of the F-1/P14.N7 reconciliation (§5.3 / OQ-5). | our `cli_schwab.py:837-842` |
| `swing/integrations/schwab/checker_resilience.py` (255 LOC) | **[D]** | Dead on v3 (no daemon to wrap). Its own docstring says "the Phase-15 schwabdev v3 upgrade deletes the checker and this module with it." | our `checker_resilience.py:10-12` |
| `swing/web/app.py:265-324` (`_install_*` checker) | **[D]** | The install + STARTING-sidecar seed + readback. Dead on v3. | our `app.py:265-324` |
| `swing/web/view_models/schwab_checker_badge.py` (63 LOC) | **[D]/[R]** | The F-1 badge VM. §5.3 / OQ-5. | our `schwab_checker_badge.py` |
| base-layout VMs (dashboard, metrics/shared, schwab route, + the `=None` field across config/error/journal/pipeline/reconcile/trades/watchlist) | **[D]/[R]** | `schwab_checker_badge` field + the two `build_schwab_checker_badge(cfg)` call sites (`dashboard.py:1535`, `routes/schwab.py:238`). Reconcile ALL in ONE task (gotcha #11). | our `dashboard.py:391,1533-1535`; `routes/schwab.py:227,238` |
| `swing/web/templates/base.html.j2:81-84` | **[D]/[R]** | The topbar badge block. Guarded by `{% if vm.schwab_checker_badge %}` (so a None field renders nothing -- no Jinja 500). | our `base.html.j2:81-84` |
| `tests/integrations/test_schwab_trader_kwarg_signatures.py:31-42` | **[T]** | `test_account_linked_no_kwargs_required` does `inspect.signature(schwabdev.Client.account_linked)` -> AttributeError on v3. Rename pin to `linked_accounts` (still no-kwargs: installed `client.py:181` `linked_accounts(self)`). Other 3 pins PASS unchanged. | our test `:37`; v3 `client.py:181` |
| `tests/integration/test_l2_lock_source_grep.py:26` | **[T]** | Re-anchor `L2_LOCK_BASELINE_SHA`. §7. | our test `:26` |
| 6 checker tests (`tests/cli/test_schwab_status_checker_liveness.py`, `tests/integration/schwab/test_checker_liveness_state.py`, `tests/integration/schwab/test_checker_resilience.py`, `tests/web/test_checker_liveness_install_path.py`, `tests/web/test_schwab_checker_badge.py`, `tests/web/test_schwab_checker_badge_topbar.py`) | **[D]/[R]** | Removed (delete disposition) or rewritten (rewire disposition). | grep of importers |
| tokens-file JSON-shape fixtures + web-setup tests around `_write_schwabdev_tokens_file` + status-command tests | **[R]** | Re-shape to the v3 SQLite tokens DB. ~10-25 tests. | findings §4 test-impact |
| `CLAUDE.md` Schwab gotcha block + status-line | **[R]** | Refresh the plaintext-tokens gotcha (if Fernet ships), the daemon-checker note, the `setup`-clean-DB note (`.db` semantics), L2 re-anchor record. | CLAUDE.md Schwab block |

**Note A (L5 divergence -- cosmetic only):** the installed 3.0.5 package's `schwabdev.__version__` reads **`3.0.4`** (the maintainer did not bump the internal string; matches the findings-doc note that GitHub `main` reads `3.0.4`). The **distribution** is 3.0.5 (`pip show schwabdev` -> 3.0.5; the wheel/sdist version). No behavioral divergence. Implication: a signature-pin or version test MUST assert the *distribution* version (`importlib.metadata.version("schwabdev")`), NOT `schwabdev.__version__`.

**Note B (new transitive deps):** v3 pulls `cryptography` (Fernet) + `aiohttp` (used by the async client we do not use). Both arrive transitively. **Correction (verified installed):** `aiohttp` is imported at MODULE TOP in `schwabdev/client.py:12` (`import aiohttp`), NOT lazily -- so `import schwabdev` imports `aiohttp` unconditionally; it is a HARD transitive dependency (the `ClientAsync.__init__` `if aiohttp is None` guard at `client.py:581` is vestigial since the top-level import already requires it). Flag for the operator: a materially heavier dependency tree (`aiohttp` + `cryptography` + their own transitives: `multidict`, `yarl`, `frozenlist`, `cffi`, etc.). If the heavier tree is unwanted, that is an argument to weigh against the upgrade -- but it does not block it.

---

## §4 Migration strategy (re-pin + the breaking-change fixes)

**Ordering principle:** land the mechanical, test-coverable changes first (re-pin, renames, constructor kwargs, signature-pin); then the token-storage rewrite (the risky core); then the P14.N7/F-1 reconciliation; then the L2 re-anchor (which can only be computed once the churn is final); the operator live-OAuth gate is last.

1. **Re-pin (`pyproject.toml:20`).** Change `schwabdev>=2.4.0,<3.0.0` -> the OQ-3 choice (recommend `>=3.0.5,<4.0.0`). `pip install -e ".[dev,web]"` re-resolves; `cryptography` + `aiohttp` arrive transitively. The dev box's installed 2.5.1 is replaced by 3.0.5 at this step -- this is the cutover point for the operator's *dev* env (the live tokens DB cutover is §5.4).
2. **`account_linked` -> `linked_accounts`** at the two call sites (`trader.py:270`, `auth.py:653` via `_stub_call_account_linked`) + the signature-pin test rename. Discriminating test: `inspect.signature(schwabdev.Client.linked_accounts)` has no params beyond `self` (confirmed installed `client.py:181`).
3. **Constructor kwarg `tokens_file=` -> `tokens_db=`** at all construction sites (auth.py x4, pipeline_steps, runner, cli). Pure rename; the path value is unchanged (`~/swing-data/schwab-tokens.{env}.db`).
4. **`update_tokens` survives** -- `force_refresh` (`auth.py:1879` `update_tokens(force_access_token=True)`) is unchanged (installed `client.py:142`, `tokens.py:278`). No change; re-validate post-call state (L4).
5. **Token-storage rewrite** (§5) -- the writer + the reader + the operator re-setup UX.
6. **P14.N7 + F-1 reconciliation** (§5.3) -- delete the wrapper + reconcile the badge.
7. **L2 re-anchor** (§7) -- compute the post-migration baseline + the endpoint diff + the operator sign-off.

**Install/uninstall note:** because v3 cannot read the 2.x JSON token DBs, an operator who pulls the new pin and runs `swing web`/pipeline BEFORE re-`setup` hits the §5.4 failure: a 2.x JSON file at the tokens path makes v3 construction CRASH (`sqlite3.DatabaseError` on the immediate `CREATE TABLE`), which the §5.4 preflight converts to a clean `SchwabAuthError`. The cutover ordering (OQ-6) makes the re-`setup` a gate BEFORE first v3 run.

**Concrete before/after (the mechanical changes, illustrative -- re-grep line numbers at writing-plans):**

```python
# auth.py:758-764 -- construction site (one of 4). BEFORE:
client = schwabdev.Client(
    app_key=client_id, app_secret=client_secret,
    callback_url=cfg.integrations.schwab.callback_url,
    tokens_file=str(tokens_path),                  # <- 2.x JSON file
    timeout=int(cfg.integrations.schwab.timeout_seconds),
)
# AFTER (v3 -- kwarg rename; + optional Fernet per OQ-1; + non-interactive guard):
client = schwabdev.Client(
    app_key=client_id, app_secret=client_secret,
    callback_url=cfg.integrations.schwab.callback_url,
    tokens_db=str(tokens_path),                    # <- v3 SQLite DB
    encryption=_resolve_fernet_key(cfg),           # <- None unless OQ-1=include
    call_on_auth=_raise_on_auth,                   # <- non-setup paths: raise, never prompt
    open_browser_for_auth=False,                   # <- never launch a browser headlessly
    timeout=int(cfg.integrations.schwab.timeout_seconds),
)

# trader.py:270 -- the rename. BEFORE: client_method=lambda: client.account_linked()
#                                AFTER: client_method=lambda: client.linked_accounts()
```

Note we never passed the removed kwargs (`capture_callback`/`use_session`/`call_on_notify`), so the constructor deltas are `tokens_file=`->`tokens_db=` (+ the optional `encryption=`) PLUS a NON-INTERACTIVE GUARD (below).

**Non-interactive construction guard (REQUIRED on all non-setup paths -- the interactive-auth-leak fix):** v3's `Client.__init__` calls `tokens.update_tokens()` at construction (installed `client.py:43`), and `Tokens` starts an INTERACTIVE auth flow -- `input()` and (default) a browser launch -- not only on a missing table but whenever `_load_tokens_from_db()` returns false (no row OR decrypt failure), OR when the refresh token is expired/near-expiry (`rt_delta < 3630s` forces `_update_refresh_token` -> `input()`): installed `tokens.py:94-103,278-300,421-435`. The default `open_browser_for_auth=True` would even launch a browser. **In a headless context (`swing web`, the pipeline subprocess, `swing schwab fetch`) this BLOCKS on stdin forever or pops a browser -- a production hazard.** Therefore every NON-setup construction site MUST pass `open_browser_for_auth=False` AND a `call_on_auth` callback that RAISES a clean `SchwabAuthError("tokens expired/invalid; run swing schwab logout then setup")` instead of prompting:

```python
def _raise_on_auth(auth_url):              # injected as call_on_auth on non-setup paths
    raise SchwabAuthError(401, "<tokens expired/invalid; run swing schwab logout then setup>")
client = schwabdev.Client(..., tokens_db=str(tokens_path), encryption=_resolve_fernet_key(cfg),
                          call_on_auth=_raise_on_auth, open_browser_for_auth=False, timeout=...)
```

This converts v3's silent interactive-prompt into a clean, catchable error for fetch/web/pipeline. **IMPORTANT -- the guard is defense-in-depth, NOT the primary defense:** raising inside `call_on_auth` happens AFTER schwabdev's `BEGIN EXCLUSIVE` with no try/finally (installed `tokens.py:395-422`), so it can leave the tokens-DB transaction open until the partially-constructed object is collected. The PRIMARY defense is the COMPREHENSIVE §5.4 preflight (checks table+row presence, refresh-token FRESHNESS, and decryptability BEFORE constructing the `Client`), which makes the interactive refresh path UNREACHABLE in normal operation so the callback never fires. The guard catches only the residual preflight-read-to-construct race; when it fires the caller drops the reference + `gc.collect()`s to release the lock (§5.4). The SETUP path does NOT need the guard (our setup writes a fresh valid DB via §5.1 BEFORE constructing the load-back Client, so no auth flow fires) -- but passing it there too is harmless and uniform.

---

## §5 Token-storage rewrite + operator re-setup UX + the P14.N7/F-1 reconciliation

### §5.1 The writer: `_write_schwabdev_tokens_file` -> v3 SQLite

**v3 tokens-DB schema** (installed `tokens.py:80-91`), table `schwabdev`, single row (the writer does `DELETE FROM schwabdev` then INSERT, installed `tokens.py:220-245`):

```
access_token_issued  TEXT NOT NULL   -- ISO 8601 (NOT encrypted)
refresh_token_issued TEXT NOT NULL   -- ISO 8601 (NOT encrypted)
access_token         TEXT NOT NULL   -- enc:-prefixed iff encryption on
refresh_token        TEXT NOT NULL   -- enc:-prefixed iff encryption on
id_token             TEXT NOT NULL
expires_in           INTEGER         -- access-token lifetime (sec)
token_type           TEXT
scope                TEXT
```

The 2.x writer mirrored schwabdev's JSON byte-for-byte (keys `access_token_issued`/`refresh_token_issued`/`token_dictionary`). The v3 writer must produce a row schwabdev's `_load_tokens_from_db` (installed `tokens.py:137-190`) will read cleanly. Two design options:

- **Option W-A (recommended): write the SQLite row ourselves, mirroring `_set_tokens`.** After our manual OAuth exchange (`_exchange_code_for_tokens`, which already mirrors `_post_oauth_token`), open the v3 tokens DB, `CREATE TABLE IF NOT EXISTS` the exact 8-col schema, `DELETE` + `INSERT` one row. Pros: keeps the web/headless two-phase paste flow (GET shows URL, POST receives pasted URL) -- the existing architecture -- and keeps our atomic-write discipline (`mkstemp` in dest dir + `os.replace`). Cons: we now own a copy of schwabdev's table DDL (drift risk if v3.x adds a column -- mitigate with a comment pinning the installed-3.0.5 DDL + a test that constructs a real `Client` against our-written DB and asserts `tokens.access_token` loads).
- **Option W-B: use schwabdev's `call_for_auth` callback.** v3 `Tokens` accepts `call_for_auth(auth_url) -> callback_url_or_code` (installed `tokens.py:421-422`); schwabdev then does the exchange + DB write itself. Pros: no DDL copy. Cons: `call_for_auth` is invoked *synchronously inside construction* and BLOCKS for the return value -- it fits the CLI `input()` flow but NOT the two-phase web POST (the web request returns before the operator pastes). Would force a redesign of the web setup flow. **Rejected for V1** as a scope-widening of the SHIPPED web setup surface.

**Recommendation: W-A.** It is the minimal-delta analog of the SHIPPED `_write_schwabdev_tokens_file`, preserves the web setup UX, and the DDL-drift risk is bounded by a load-back regression test (already the existing post-write discipline). The `enc:`-prefix wrapping is applied IFF Fernet ships (§6): if encryption is on, our writer must `Fernet(key).encrypt(...)` the `access_token`/`refresh_token` values with the `enc:` prefix (installed `tokens.py:120-123`), else schwabdev's `_dec` raises on load.

**W-A writer shape (illustrative -- the v3 analog of `_write_schwabdev_tokens_file`):**

```python
def _write_schwabdev_tokens_db(*, tokens_path, token_dictionary, issued_at, fernet_key=None):
    # Atomic-write discipline preserved: build in a same-dir temp DB, os.replace over.
    cipher = Fernet(fernet_key) if fernet_key else None
    def _enc(v):  # mirror installed tokens.py:120-123
        return ("enc:" + cipher.encrypt(v.encode()).decode()) if cipher else v
    fd, tmp = tempfile.mkstemp(dir=str(tokens_path.parent),
                               prefix=tokens_path.name + ".", suffix=".tmp")
    os.close(fd)
    try:
        conn = sqlite3.connect(tmp)
        conn.execute(_V3_SCHWABDEV_DDL)   # the 8-col CREATE TABLE, pinned to installed-3.0.5
        conn.execute("DELETE FROM schwabdev")
        conn.execute(
            "INSERT INTO schwabdev (access_token_issued, refresh_token_issued, "
            "access_token, refresh_token, id_token, expires_in, token_type, scope) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (issued_at.isoformat(), issued_at.isoformat(),
             _enc(token_dictionary["access_token"]), _enc(token_dictionary["refresh_token"]),
             token_dictionary.get("id_token", ""), token_dictionary.get("expires_in", 1800),
             token_dictionary.get("token_type", "Bearer"), token_dictionary.get("scope", "api")))
        conn.commit(); conn.close()
        os.replace(tmp, str(tokens_path))   # intra-volume; Windows-safe (CLAUDE.md gotcha)
    except BaseException:
        with contextlib.suppress(OSError): Path(tmp).unlink()
        raise
```

`_V3_SCHWABDEV_DDL` is a verbatim copy of the installed-3.0.5 DDL (`tokens.py:80-91`) with a comment pinning the source. Because we copy schwabdev's PRIVATE internals (`_set_tokens`/`_load_tokens_from_db`/the table DDL are all underscore-private, installed `tokens.py:137,193`), the floored pin (OQ-3 `>=3.0.5,<4.0.0`) is safe ONLY if a **DDL-drift guard test** (T1b, §10) introspects the LIVE installed `schwabdev` table (`PRAGMA table_info(schwabdev)` after a real `Client` constructs its DB) and asserts it still matches our pinned 8-column copy -- failing loudly the moment a future 3.x changes the schema. The T1 load-back test (construct a real `Client` against the DB OUR writer produced; assert `tokens.access_token` loads) is the complementary tripwire. Together they convert "we depend on private internals" from a silent risk into a CI-visible one.

### §5.2 The reader: `_read_tokens_metadata` + the status health renderer

The 2.x reader `json.load`s the file and returns the dict; the status command consumes `access_token_issued`, `refresh_token_issued`, and `token_dictionary.{refresh_token, expires_in}` (our `cli_schwab.py:881-893` + the DEGRADED health signals `:611-725`). The v3 reader becomes a SQLite read:

```sql
SELECT access_token_issued, refresh_token_issued, expires_in, refresh_token
FROM schwabdev LIMIT 1
```

Key mapping for the DEGRADED-health signals (our `cli_schwab.py:630-705`):
- "token_dictionary missing/non-dict" -> **no row in `schwabdev`** (or DB file absent) => DEGRADED / setup-needed.
- "token_dictionary.refresh_token bytes missing" -> the `refresh_token` column empty/absent => DEGRADED. (Read presence only; the `enc:`-prefixed value is NOT decrypted -- we never need the secret, only its presence, exactly as the 2.x reader's SECURITY note promised.)
- "refresh_token_issued missing/unparseable/expired (issued + 7d <= now)" -> read the `refresh_token_issued` column; same `_parse_iso_datetime` + `_REFRESH_TOKEN_TTL_SECONDS` math, unchanged.
- `expires_in` moves from nested `token_dictionary.expires_in` to the top-level `expires_in` column.

**Security-preserving design:** the v3 reader returns ONLY the four non-secret/presence fields above (issued timestamps + `expires_in` + a boolean "refresh_token present"). It does NOT SELECT/return the `access_token` value. This is *stronger* than the 2.x reader (which returned the full payload with a "caller must not echo" warning) -- the v3 reader never holds the secret bytes. Add a test asserting the reader's return shape carries no token bytes.

**Reader shape (illustrative):**

```python
def _read_tokens_metadata_v3(tokens_path):
    # Returns (meta, error) where meta carries ONLY non-secret presence fields.
    if not tokens_path.exists():
        return None, None                       # caller: setup-needed
    try:
        # TRUE read-only via a PROPERLY-ESCAPED file: URI. Path.as_uri()
        # percent-encodes spaces / '#' / '?' (the f"file:{path}?mode=ro" form
        # misparses on such paths), so append the query to the escaped URI:
        ro_uri = Path(tokens_path).as_uri() + "?mode=ro"
        conn = sqlite3.connect(ro_uri, uri=True)
        # detect old format: a 2.x JSON file opened as sqlite raises DatabaseError;
        # a sqlite file with no schwabdev table => old/foreign DB.
        row = conn.execute(
            "SELECT access_token_issued, refresh_token_issued, expires_in, "
            "       (refresh_token IS NOT NULL AND refresh_token != '') "
            "FROM schwabdev LIMIT 1").fetchone()
    except sqlite3.OperationalError as exc:      # locked OR no such table
        if "no such table" in str(exc):
            return None, "<tokens DB pre-v3 / foreign format; run logout+setup>"
        return None, "<tokens DB busy (refresh in progress); retry>"
    except sqlite3.DatabaseError:
        return None, "<tokens DB pre-v3 (2.x JSON) format; run logout+setup>"
    finally:
        with contextlib.suppress(Exception): conn.close()
    if row is None:
        return None, "<no token row; run swing schwab setup>"
    at_issued, rt_issued, expires_in, has_refresh = row
    return {"access_token_issued": at_issued, "refresh_token_issued": rt_issued,
            "expires_in": expires_in, "refresh_token_present": bool(has_refresh)}, None
```

**Concurrency note:** schwabdev opens the tokens DB with `check_same_thread=False` + `busy_timeout=30000` (installed `tokens.py:76,92`) and `_update_access_token` holds `BEGIN EXCLUSIVE` across the HTTP refresh (installed `tokens.py:320`). Our status reader is a short `SELECT LIMIT 1` -- open read-only (`mode=ro` URI), do NOT hold a transaction, tolerate `sqlite3.OperationalError` (database locked) by reporting "tokens busy (refresh in progress); retry" rather than crashing. (This is a NEW concurrency surface vs the 2.x file read -- flag for the test plan, T4.)

### §5.3 The P14.N7 + F-1 web-badge reconciliation (OQ-5; L6)

v3's sync `Client` has no daemon checker, so:
- **P14.N7 daemon-checker resilience wrapper** (`checker_resilience.py`, 255 LOC) is DEAD. Remove it + the `app.py:265-324` install/seed/readback + the CLI status liveness block (`cli_schwab.py:837-842`) + the 6 checker tests.
- **F-1 web checker-liveness badge** loses its data source (nothing writes the `~/swing-data/schwab-checker-liveness.{env}.json` sidecar on v3) -> it would be permanently the A-7 "Schwab? UNKNOWN" state. Two dispositions:

  - **Option D5-DELETE (recommended): remove the badge entirely.** The badge existed SOLELY to surface daemon-checker death (A-7). With no daemon and a network-hardened per-request refresh (`_update_access_token` catches `RequestException`, installed `tokens.py:336-339`), the "silent daemon death" failure mode no longer exists -- there is nothing for the badge to warn about. `swing schwab status` remains the canonical token-health surface (it reads the tokens DB directly per §5.2 and reports refresh-token expiry/DEGRADED). Remove: the badge VM module, the two `build_schwab_checker_badge(cfg)` call sites, the `schwab_checker_badge` field across the base VMs, the `base.html.j2:81-84` topbar block, the badge tests. ONE atomic task (gotcha #11 + the "base.html.j2 is shared" gotcha).
  - **Option D5-REWIRE: keep a topbar badge, re-source it from the v3 tokens DB.** The v3 `access_token_issued` column advances on every access-token rotation (<=30 min). A rewired badge could read that column and show ALIVE if `now - access_token_issued < ~35min`, DEGRADED if stale, UNKNOWN if no row. Pros: keeps an at-a-glance topbar health signal. Cons: semantics shift from "daemon alive" to "token fresh"; on v3 the token is refreshed per-request so it is ~always fresh whenever the page renders -> the badge is near-tautologically green and carries little signal; it also adds a tokens-DB read to every page render (the §5.2 locked-DB concurrency surface on the hot path). **Lower value, higher coupling.**

  **Recommendation: D5-DELETE**, with `swing schwab status` as the single health surface. REWIRE is the documented alternative if the operator wants a persistent topbar signal.

  **Gate discipline (memory `feedback_seeded_gate_masks_default_state`):** whichever is chosen, the operator gate MUST witness the UNSEEDED production-default state in normal `swing web` -- a seeded sidecar is exactly the gap that produced the A-7 defect. For DELETE: witness the topbar has NO badge and no console error in a normal run. For REWIRE: witness the badge with a REAL tokens DB (not a seeded sidecar).

### §5.4 The operator re-setup UX (OQ-2)

v3 cannot read the 2.x JSON token DBs (different on-disk format), so existing operators must re-auth ONCE. Two designs:

- **Option U-A (recommended): force a clean re-`setup`.** On first v3 run, `swing schwab status` detects the old-format DB (a JSON file where v3 expects SQLite, OR a SQLite file with no `schwabdev` table) and reports: "Token DB is in the pre-v3 (2.x JSON) format. Run `swing schwab logout` then `swing schwab setup` to re-authenticate (one-time, ~2 min). Your trading data is unaffected." `logout` already atomically renames the stale DB (`_rename_stale_tokens_db`); `setup` writes the fresh v3 SQLite. Simple, safe, no fragile parsing of secret bytes.
- **Option U-B: auto-migrate the old JSON -> v3 SQLite.** Read the 2.x JSON, write the v3 row. Rejected: it copies live refresh-token bytes through our code (a secret-handling surface we avoid), the 2.x `token_dictionary` may lack fields v3's `_set_tokens` expects, and a one-time 2-min re-auth is cheaper than the migration's risk. The 7-day refresh-token TTL means the operator re-auths weekly anyway.

**Recommendation: U-A (force re-setup).**

**Comprehensive preflight (REQUIRED on NON-setup construction paths -- and the SAME logic in `status`):** an old-format DB does NOT "trigger an auth flow" -- it CRASHES. v3 `ClientBase.__init__` constructs `Tokens(...)` which `sqlite3.connect()`s the path and immediately runs `CREATE TABLE IF NOT EXISTS schwabdev` (installed `tokens.py:76,80`); a 2.x JSON file there raises `sqlite3.DatabaseError: file is not a database` BEFORE any `_load_tokens_from_db`/auth-prompt logic. Therefore a comprehensive preflight `_assert_v3_tokens_db_loadable_or_raise(tokens_path, fernet_key)` MUST run before every NON-setup v3 `Client(...)` construction site -- `construct_authenticated_client` (the fetch path), `force_refresh`, and the web/pipeline client builders -- raising a clean `SchwabAuthError` instead of letting a `DatabaseError` escape OR letting an interactive prompt fire. The detector does the full (1)-(4) check below (table present, single row, refresh-token fresh, columns decryptable). `swing schwab status` uses the SAME detector to render the actionable message (not a traceback). The SETUP paths do NOT use this preflight: `_rename_stale_tokens_db` (called inside `setup_paste_flow` before construction, our `auth.py:860`) renames any existing DB aside and then writes a fresh one -- so setup never constructs against a stale/foreign DB. It is the FETCH/web/pipeline paths (which do NOT rename) that the preflight guards.

**Preflight is the PRIMARY defense; the guard is defense-in-depth (the open-transaction hazard):** there is a subtlety that makes the `call_on_auth` guard insufficient ALONE. v3 `_update_refresh_token` runs `BEGIN EXCLUSIVE` (installed `tokens.py:395-398`) and then calls `call_for_auth` (`tokens.py:421-422`) **with NO try/finally around the callback** -- so if our `_raise_on_auth` raises there, schwabdev SKIPS its own rollback (`tokens.py:442-447` is never reached) and the connection holds the EXCLUSIVE lock until the (partially-constructed) `Client`/`Tokens` object is collected. On CPython 3.14 the raising constructor's locals are refcount-collected when the frame unwinds (the lock releases promptly), but relying on that is fragile.

**Therefore the §5.4 preflight is EXTENDED to be COMPREHENSIVE and is the PRIMARY defense** -- it makes the interactive refresh path UNREACHABLE in normal operation. Before EVERY non-setup construction, the preflight checks, by reading the v3 DB directly (NOT by constructing a `Client`):
  1. the file is a v3 SQLite with the `schwabdev` table (else old/foreign format -> clean error);
  2. exactly one token row exists (else -> setup-needed);
  3. the refresh token is FRESH ENOUGH that construction will not force a refresh: `now - refresh_token_issued < (7d - refresh_threshold)`, i.e. `rt_delta >= 3630s` (the v3 threshold, `tokens.py:293`); if stale -> clean `SchwabAuthError("refresh token expired/expiring; run logout+setup")`;
  4. decryptability driven by the DB CONTENT, NOT the config flag (the key-loss gap): inspect the `access_token`/`refresh_token` column VALUES for the `enc:` prefix (installed `tokens.py:16,120-134`). If a column is `enc:`-prefixed, a valid Fernet key MUST be configured AND must successfully `decrypt(...)` it -- if config has NO key, a WRONG key, or decryption fails, raise a clean `SchwabAuthError("encrypted tokens but key missing/invalid (key loss?); run logout+setup")`. Do NOT key this check on config's "is Fernet enabled" flag: a DB written WITH encryption while config now reports NO key (key removed/lost) is exactly the case schwabdev turns into a silent decrypt-fail -> `_load_tokens_from_db` returns false (`tokens.py:179-184`) -> the interactive refresh path. Inspecting the column prefix catches it BEFORE construction.

With (1)-(4) passing, construction's `update_tokens()` finds a fresh, loadable row and does NOT enter `_update_refresh_token` -> the callback never fires -> no open-tx hazard. (The access-token refresh path that CAN still fire at construction -- `at_delta < 61s` -> `_update_access_token` -- does its OWN network POST with proper rollback handling, `tokens.py:332-351`, so it is safe.) The §4 `call_on_auth=_raise_on_auth` + `open_browser_for_auth=False` remain as a defense-in-depth BELT for the residual race (a refresh token that expires between the preflight read and the construct), and when that rare path fires the caller MUST drop the reference + (defensively) `gc.collect()` so the partially-constructed connection's lock releases deterministically before any subsequent tokens-DB read.

The `swing schwab setup`-needs-clean-DB gotcha persists in spirit: `logout` (rename-aside) before `setup` remains the recovery -- but on v3 `logout` itself must be fixed first (§5.5), else the recovery path is also broken.

### §5.5 The `swing schwab logout` / revoke rewrite (Critical -- the orphaned 2.x token path)

`revoke_and_delete` (our `auth.py:2098-2189`) is the `swing schwab logout` path. It currently `json.load`s the tokens file to pull `token_dictionary.refresh_token` (`:2117-2119`), POSTs it to `/v1/oauth/revoke` (`:2177`), then renames/deletes the DB. On a v3 SQLite DB the `json.load` raises -> `refresh_token=None` -> `:2129` records an error audit row and **raises `SchwabApiError` before the DB is renamed**. This breaks logout on v3 -- and logout is step 1 of the L7 live-OAuth gate AND the §11 rollback recovery, so it MUST be fixed in the token-storage slice.

**Design (the v3 revoke path):**
- Read the refresh_token from the v3 SQLite DB: `SELECT refresh_token FROM schwabdev LIMIT 1`. **Unlike the status reader (§5.2), revoke NEEDS the actual token VALUE** -- so if Fernet is on (§6), revoke must DECRYPT it: strip the `enc:` prefix and `Fernet(key).decrypt(...)`. This is the ONE place the status-vs-revoke asymmetry matters: status needs presence only (no key); revoke needs the plaintext (the key). The shared v3 tokens-DB reader takes an optional `fernet_key` param -- status passes `None`, revoke passes the key.
- **Delete-without-revoke fallback (resilience):** logout's PRIMARY job is to clear LOCAL OAuth state. If the refresh_token cannot be read/decrypted (old-format DB, locked DB, missing/garbled Fernet key), logout should STILL rename the DB aside, emitting a WARNING that the token was not server-side revoked (it self-expires within the 7-day TTL anyway). Re-order the current logic: rename-aside FIRST (or in a `finally`), revoke best-effort SECOND. **Honest filesystem caveat (not an unconditional guarantee):** the rename itself can fail when the `.db` is locked / file-in-use (Windows `os.replace` raises `PermissionError`/`OSError`) -- `_rename_stale_tokens_db` already encodes the bounded-retry + audit-on-failure discipline. So the fallback is "best-effort rename with bounded retry; on a hard rename failure, surface a CLEAN actionable error ('close other swing processes and retry `swing schwab logout`'), never a silent partial state." Do NOT claim logout ALWAYS succeeds -- claim it never leaves a half-revoked/half-renamed silent state, and that a hard failure is reported clearly.
- The `/v1/oauth/revoke` endpoint is UNCHANGED (it is our own manual POST, not a schwabdev method) -- it is added to the §7 endpoint diff for completeness (it proves no NEW endpoint).
- Tests: logout on a fresh v3 DB (revoke fires, DB renamed); logout on an encrypted v3 DB (decrypt + revoke); logout on an old-format/missing-key DB (delete-without-revoke fallback + WARNING, DB still renamed); logout where the rename itself HARD-FAILS (locked/file-in-use) surfaces a clean actionable error after bounded retry, NOT a silent partial state. (Full enumeration in §10 T7.)

---

## §6 Fernet token-at-rest encryption design (OQ-1)

v3's `encryption=<key>` wraps the `access_token`/`refresh_token` columns with Fernet (installed `tokens.py:68,120-134`; `enc:` prefix; key must be `len > 16`, and Fernet keys are 44-char urlsafe-base64 -- pass a real `Fernet.generate_key()`). This retires the CLAUDE.md "plaintext OAuth at rest (V1)" gotcha. **Recommendation: INCLUDE in this arc** -- it is the stated pull-forward incentive.

**Key storage / derivation:**
- **Where the key lives (recommended): `~/swing-data/user-config.toml` `[integrations.schwab]` `encryption_key = "<fernet>"`** -- the same out-of-tree, gitignored, user-profile-ACL'd location as the Schwab CLIENT_ID/SECRET. `swing config show` MUST mask it (like client_secret). This is honest V1.5 security: it raises the bar from "tokens plaintext at rest" to "tokens encrypted at rest, key in a sibling file" -- it defeats casual disk/backup inspection and accidental Drive-sync exposure, though not an attacker who reads the whole `~/swing-data/` dir. Document that limitation explicitly (do not over-claim).
- **Key generation:** `swing schwab setup` (and a new `swing schwab encrypt-tokens` helper, optional) generates `Fernet.generate_key()` on first encrypted setup and writes it to user-config if absent. The construction sites then pass `encryption=<key>` to `Client(...)`.
- **Key-loss recovery:** losing the key = the tokens DB is unreadable (`_dec` raises). Recovery is the SAME `logout -> setup` (re-auth). Because re-auth is the universal recovery anyway (7-day TTL), key-loss is not catastrophic -- document it as "lost key => re-run setup".
- **`.gitignore`/ACL:** the tokens DB is already gitignored (`swing-data/schwab-tokens.*.db` + `-journal/-shm/-wal`, our `.gitignore:132-135`); `user-config.toml` is already out-of-tree. No new ignore needed; verify the `encryption_key` is masked by `swing config show`.
- **Migration interaction:** if Fernet ships, the §5.1 writer must `enc:`-wrap before INSERT, and the §5.2 status reader is UNAFFECTED (it reads only the unencrypted `*_issued` timestamps + `expires_in` + refresh-token *presence*). The ONE path that DOES need the key is `revoke_and_delete` (§5.5): revoke POSTs the plaintext refresh_token, so it must `Fernet(key).decrypt(...)` the column -- and its delete-without-revoke fallback covers the missing-key case (logout still clears local state). So the key is needed at: construction (`encryption=` to `Client(...)`), the writer (enc-wrap), and revoke (decrypt) -- NOT at status. Clean separation everywhere except revoke, which the §5.5 fallback de-risks.

**Simplification option:** ship the migration WITHOUT Fernet (encryption=None, plaintext as today) and add Fernet as an immediate follow-on slice. This de-risks the core token-storage rewrite (fewer moving parts in the first live-OAuth gate). **Flag as OQ-1 operator-binding:** include Fernet in this arc (recommended -- it is the incentive) vs defer one slice.

---

## §7 The L2 re-anchor design (rationale + sign-off + endpoint diff)

**Why the lock trips:** `test_l2_lock_source_grep.py` greps the literal `schwabdev.Client.` in `swing/` and Counter-compares HEAD vs baseline `bf7e071` (multiset subset: HEAD must be a subset). At `f1b008d` there are **42 matches across 8 files, and EVERY ONE is a comment, docstring, or type annotation** (verified `git grep -n "schwabdev.Client." HEAD -- swing/`); none is a method invocation (we call on instances). The 4 real construction sites match the `schwabdev.Client(` substring within `client = schwabdev.Client(`. The migration WILL rewrite many of these prose lines (e.g. `pipeline_steps.py:90-93` embeds the literal 2.5.1 `tokens_file=` signature; `auth.py` docstrings reference `tokens_file`) -> changed `line_text` keys -> NEW multiset keys -> the test FAILS. The test is doing its job (a doc/intent tripwire).

**The re-anchor mechanics:**
1. Land ALL migration churn first (the baseline can only be computed once the prose is final).
2. Bump `L2_LOCK_BASELINE_SHA` from `bf7e071` to the post-migration HEAD SHA.
3. Add an **audited rationale block** in the test docstring: the date, the arc (Phase 15 schwabdev v3), the reason (rename/storage/docstring churn -- NOT new endpoints), and an explicit "operator-signed baseline move on <date>".
4. Add a **manual endpoint-set diff** as a SEPARATE assertion/artifact (the grep alone is insufficient -- it counts prose lines, not endpoints). Enumerate the Schwab REST endpoints we invoke via wrapper methods, pre- and post-migration:

   | Wrapper call | 2.5.1 method | v3 method | REST endpoint | new? |
   |---|---|---|---|---|
   | linked accounts | `account_linked()` | `linked_accounts()` | `/trader/v1/accounts/accountNumbers` | NO (rename only) |
   | account details | `account_details(...)` | same | `/trader/v1/accounts/{hash}` | NO |
   | account orders | `account_orders(...)` | same | `/trader/v1/accounts/{hash}/orders` | NO |
   | transactions | `transactions(...)` | same | `/trader/v1/accounts/{hash}/transactions` | NO |
   | quotes | `quotes(...)` | same | `/marketdata/v1/quotes` | NO |
   | price history | `price_history(...)` | same | `/marketdata/v1/pricehistory` | NO |
   | OAuth token | `_post_oauth_token` (mirrored) | same | `/v1/oauth/token` | NO |
   | OAuth revoke | our manual POST (`revoke_and_delete`) | same (our POST) | `/v1/oauth/revoke` | NO (pre-existing; our `auth.py:2177`) |
   | OAuth authorize | the setup consent URL | same | `/v1/oauth/authorize` | NO (pre-existing; the setup paste flow) |

   **Conclusion: ZERO new endpoints** -- the migration renames one method (same path) and changes token storage (no API call). The two OAuth surfaces (`revoke`, `authorize`) are our own manual flows, pre-existing and unchanged. The lock's SPIRIT is preserved. The diff above is now the COMPLETE Schwab/OAuth endpoint set we consume pre- and post-migration.
5. **Operator sign-off gate (OQ-4):** the re-anchor is the FIRST-EVER baseline move; it requires an explicit operator approval recorded in the writing-plans/executing-plans gate (not a silent commit). The brief's escalation rule binds: **if the re-anchor would hide a genuinely-NEW endpoint, STOP + escalate.** The endpoint diff above is the proof it does not.

**The audited rationale block (illustrative -- lands in the test module):**

```python
# L2_LOCK_BASELINE_SHA re-anchored <post-migration-SHA> on 2026-06-?? (Phase 15,
# schwabdev v3 upgrade). FIRST-EVER baseline move. Reason: the 2.5.1->3.0.5
# migration rewrites docstrings/comments/type-annotations that embed the literal
# "schwabdev.Client(...)" (the tokens_file= signature, the account_linked
# reference) -> the Counter-subset multiset gains new (path, line_text) keys
# that are PROSE, not new call sites. A MANUAL endpoint-set diff (spec §7 table)
# proves ZERO new Schwab REST endpoints: account_linked->linked_accounts hits the
# SAME /trader/v1/accounts/accountNumbers path; all other endpoints unchanged;
# token storage changed (JSON->SQLite) involves no API call. Operator-signed at
# the writing-plans/executing-plans gate (OQ-4). The lock's SPIRIT (zero new
# endpoints) is preserved.
L2_LOCK_BASELINE_SHA = "<post-migration-SHA>"   # was "bf7e071"
```

**Design choice -- re-anchor vs whitelist:** an alternative is to keep `bf7e071` and add a per-line whitelist of the churned prose lines. Rejected: a 20+-line prose whitelist is more brittle and less honest than a clean baseline move + the endpoint-diff artifact. The re-anchor is the operator-visible, auditable action the test was designed to force.

**Post-re-anchor health:** add a test asserting the grep STILL FUNCTIONS after the re-anchor (greps run, returns a non-empty Counter, subset-check passes at the new baseline) -- so the lock is not silently disabled.

---

## §8 Schema impact (swing DB -- NO change) [L3]

**Confirmed NO swing-DB schema change.** schwabdev's tokens DB (`~/swing-data/schwab-tokens.{env}.db`, the `schwabdev` table) is schwabdev-internal SQLite, entirely separate from `swing.db` and its `migrations/*.sql`. The migration touches:
- the tokens DB's *format* (JSON file -> schwabdev's own SQLite) -- not our migration system;
- no `swing.db` table, column, or CHECK constraint;
- `EXPECTED_SCHEMA_VERSION` stays **23**; no `00NN` migration file is added.

Verify at writing-plans: grep that the migration adds no file under `swing/data/migrations/` and does not touch `EXPECTED_SCHEMA_VERSION`. The `schwab_api_calls` / `account_equity_snapshots` / `reconciliation_runs` tables (our audit/domain rows) are UNCHANGED -- the migration changes how we *construct* the client, not what we persist.

---

## §9 Sub-bundle decomposition recommendation

A focused 4-slice decomposition (each a brainstorm-derived plan slice; Codex convergence per slice or one chain at end per OQ-7):

- **Slice 1 -- Re-pin + mechanical renames + signature pins** (low risk, fully test-coverable). `pyproject.toml`; `account_linked->linked_accounts` (2 sites); `tokens_file->tokens_db` (all construction sites); the signature-pin test rename; the `__version__`-vs-distribution test (Note A). Green the suite minus the token-storage + L2 tests.
- **Slice 2 -- Token-storage rewrite** (the risky core; §5.1 + §5.2 + §5.4 + §5.5). The v3-SQLite writer; the v3-SQLite status reader + health-signal re-map; the locked-DB concurrency handling; the comprehensive non-setup loadability preflight before fetch/web/pipeline construction (§5.4 -- table+row+freshness+decryptability); the `revoke_and_delete` logout rewrite incl. the delete-without-revoke fallback (§5.5/C1 -- logout is step 1 of the live gate, so it must land here, not later); the operator re-setup detection (§5.4, U-A). Mock-based tests (T1-T8) + the construct-real-Client-against-our-DB load-back regression + the DDL-drift guard (T1b).
- **Slice 3 -- P14.N7 + F-1 reconciliation** (§5.3; ONE atomic task). Delete the wrapper + `app.py` install + CLI liveness block + the badge (D5-DELETE) + all 6 tests + the base-VM field + the template block.
- **Slice 4 -- Fernet (if OQ-1=include) + L2 re-anchor + the live-OAuth gate** (§6 + §7 + §10/G7). Fernet wiring; the L2 baseline bump + endpoint-diff artifact + operator sign-off; the binding operator live-OAuth re-setup smoke; CLAUDE.md refresh.

Rationale: Slice 1 de-risks by landing everything provable-by-test first; Slice 2 isolates the token-storage core; Slice 3 is independent (web/CLI deletion); Slice 4 carries the operator-binding gates (Fernet decision, L2 sign-off, live OAuth). If OQ-1 = defer Fernet, Slice 4 drops Fernet to a follow-on.

---

## §10 Test strategy + the operator LIVE-OAuth re-setup gate

**Per-gotcha re-validation (L4) -- one test each:**
- **G1 logger redaction:** assert `logging.getLogger("Schwabdev")` (capital-S) is still the schwabdev logger name on 3.0.5; re-run the sentinel-leak audit test (plant non-token sentinels, grep all surfaces). (installed `client.py:41`.)
- **G2 `update_tokens` post-state:** construct against a known-good DB; assert `client.tokens.access_token` populated; assert `update_tokens` returns bool and does NOT raise on a simulated network error (v3 is hardened, installed `tokens.py:336-339`) -- but our wrapper still verifies post-call state + raises `SchwabAuthError` on empty token.
- **G3 sandbox gate:** assert under `environment != 'production'` audit rows are written but domain rows (`record_snapshot`/`run_*_reconciliation`) are short-circuited (unchanged by the migration -- a regression guard).
- **G4 price_history daily discipline:** assert `get_price_history` passes all 4 period kwargs explicitly (the minute-default footgun; v3 defaults are all `None`, installed `client.py:472-474`).
- **G5 typed-error audit-row close:** assert every wrapper closes its `schwab_api_calls` row via `record_call_finish` before re-raising (`linked_accounts` path included).
- **G6 source-artifact shape:** assert `source_artifact_path="schwab_api:call/{id}"` shape is unchanged.

**Token-storage tests (Slice 2):**
- **T1 writer round-trip:** our v3-SQLite writer produces a DB that a REAL `schwabdev.Client(...)` constructs against with `tokens.access_token` loaded (the load-back regression -- bounds the DDL-copy drift risk).
- **T1b DDL-drift guard (the OQ-3 safety condition) -- NON-INTERACTIVELY + DETERMINISTIC LOCK RELEASE:** a real `Client` against an EMPTY DB would block on `input()`, so the test must NOT just construct-and-return. v3 runs `CREATE TABLE IF NOT EXISTS schwabdev` + `commit()` (installed `tokens.py:80,93`) BEFORE the auth flow's `BEGIN EXCLUSIVE` (`tokens.py:398`), so the table is durably committed before the guard fires. Test steps: construct the `Client` against a temp `tokens_db` WITH the §4 non-interactive guard; CATCH the raised `SchwabAuthError`; **then `del` the construction-frame locals + `gc.collect()` to deterministically close schwabdev's connection (which still holds the open `BEGIN EXCLUSIVE` -- without this the next read hits "database is locked" per R3-M1)**; THEN open a FRESH connection and `PRAGMA table_info(schwabdev)`, asserting the column set/order matches our pinned `_V3_SCHWABDEV_DDL`. Fails loudly if a future 3.x changes schwabdev's private schema -- the tripwire that makes the floored pin safe. (If construction order ever changes so the table is NOT committed before the guard fires, the PRAGMA returns empty -> assertion fails -> investigate.)
- **T2 reader shape:** the v3 status reader returns ONLY non-secret presence fields (no `access_token` bytes); add a test asserting the return carries no secret.
- **T3 health signals:** each DEGRADED signal (no row / empty refresh_token / missing-or-unparseable-or-expired `refresh_token_issued`) maps correctly off the v3 columns.
- **T4 locked-DB tolerance:** a `sqlite3.OperationalError (database is locked)` during the status read yields a graceful "tokens busy" message, not a crash.
- **T5 old-format detection:** a 2.x JSON file (or a SQLite with no `schwabdev` table) at the tokens path yields the actionable re-setup message (§5.4), not a traceback.
- **T6 7-day TTL:** assert `_REFRESH_TOKEN_TTL_SECONDS == 7*24*3600` AND that v3's `_refresh_token_timeout` is still `7*24*60*60` (a pin against a future v3 TTL change).
- **T7 logout/revoke on v3 (§5.5):** (a) logout on a fresh v3 DB reads the refresh_token from SQLite, fires `/v1/oauth/revoke` (mocked), and renames the DB aside; (b) logout on a Fernet-encrypted v3 DB decrypts the refresh_token before revoke; (c) logout on an old-format / missing-key DB takes the delete-without-revoke fallback -- DB still renamed aside + a WARNING that the token was not server-revoked; (d) logout when the rename itself HARD-FAILS (simulate `os.replace` raising `PermissionError`) surfaces a CLEAN actionable error after bounded retry, NOT a silent partial state. The recovery path must never leave a half-revoked/half-renamed silent state.
- **T8 preflight-before-construction (§5.4 / M1):** a 2.x JSON file at the tokens path makes `construct_authenticated_client` (the fetch path) raise a clean `SchwabAuthError` (run logout+setup), NOT an unwrapped `sqlite3.DatabaseError`. Assert the preflight runs before the `schwabdev.Client(...)` call (not after).
- **T9 preflight freshness + key-loss (§5.4 / R3-M1 / R4-M1):** (a) a v3 DB whose `refresh_token_issued` is older than `7d - 3630s` makes the non-setup construction raise a clean `SchwabAuthError` (refresh expiring) WITHOUT entering schwabdev's interactive path (assert no `input()`/browser, no open-tx lock left behind). (b) **Key-loss on the CONSTRUCTION path:** a DB with `enc:`-prefixed columns but NO configured Fernet key (or a wrong key) makes the preflight raise a clean key-loss `SchwabAuthError` BEFORE construction -- not only the logout missing-key case (T7c). (c) the residual-race guard, if it fires, leaves no locked DB (a follow-up tokens read succeeds after `gc.collect()`).

**L2 tests (Slice 4):** the re-anchored baseline subset-check passes; the grep-still-functions health test; the endpoint-diff artifact is present.

**Production-path discipline (gotcha #15):** the token-storage tests MUST exercise the real construction/read wiring (construct a real `Client` against a real on-disk DB), NOT stub-fixtures that bypass the derivation path. A byte-parity test on identical stubs is NOT a substitute for the live-OAuth gate.

**G7 -- THE BINDING GATE (L7): operator LIVE-OAuth re-setup smoke.** Mock tests are necessary but INSUFFICIENT for the auth/token path. The operator, on the v3 branch, runs:
1. `swing schwab logout` (renames the 2.x DB aside),
2. `swing schwab setup` (real Schwab OAuth round-trip; writes the v3 SQLite DB; if Fernet on, `enc:`-wrapped),
3. `swing schwab status` (reads the v3 DB; shows valid token + days-remaining; no DEGRADED),
4. a real `swing schwab fetch` / a `swing web` dashboard render that hits a live Schwab call (`linked_accounts` / market data),
5. (if D5-DELETE) witness the topbar has NO badge and no console error in normal `swing web` (the UNSEEDED default).

Merge is BLOCKED until the operator confirms G7. This mirrors the SB3/SB5 operator-witnessed gate discipline, adapted to a live-OAuth smoke.

---

## §11 Deploy cutover + rollback ordering (OQ-6)

(Schema impact already settled in §8 -- NO swing change.) The deploy concern is the **tokens-DB cutover**, since v3 cannot read the 2.x DB:

- **Cutover ordering (recommended):** the operator re-`setup` happens AT merge time, BEFORE the first v3 `swing web`/pipeline run. Sequence: merge -> `pip install -e` (pulls v3) -> `swing schwab logout` -> `swing schwab setup` -> verify `swing schwab status` -> resume normal ops. Document this in the merge/CLAUDE.md note so the operator does not run v3 against the stale 2.x DB (which would otherwise crash construction -- caught + reported cleanly by the §5.4 preflight, but the cutover avoids hitting it at all).
- **Rollback:** if v3 misbehaves post-merge, revert the pin to `<3.0.0`, `pip install -e`, and `swing schwab logout`->`setup` re-creates the 2.x JSON DB (the 2.x setup path is restored by the revert). The 2.x JSON DB renamed aside by `logout` is NOT auto-restored -- but re-`setup` is the universal recovery, so rollback = revert + re-setup. Low blast radius (no swing.db change to undo).
- **Pre-merge dev verification:** the throwaway-venv work for L5 already proved the 3.0.5 surface; the dev box's real cutover is the operator's G7 smoke on the branch before merge.

---

## §12 V1 simplifications + V2 candidates

**V1 simplifications (do the minimum that ships safely):**
- W-A writer (own the DDL with a load-back test) over W-B (`call_for_auth` web redesign).
- U-A force-re-setup over U-B auto-migrate (avoid touching secret bytes).
- D5-DELETE the badge over D5-REWIRE (no hot-path tokens-DB read; `status` is the health surface).
- Status reader returns presence-only (never holds the secret) -- simpler AND safer than the 2.x full-payload reader.

**V2 candidates (explicitly out of V1):**
- D5-REWIRE the badge to the `access_token_issued` freshness signal, if the operator later wants a persistent topbar health chip.
- Fernet key derivation from an OS keyring / DPAPI instead of user-config plaintext (true at-rest key protection) -- V1 is config-file + ACL.
- Schwab cassettes for the auth/token path (still V2 PLANNED per CLAUDE.md) -- V1 stays mock + the live-OAuth gate.
- Adopt `ClientAsync` (no current async need; explicitly not pursued).

---

## §13 Operator decision items (OQs) -- surface for triage at writing-plans

| OQ | Decision | Recommendation | Binding? |
|---|---|---|---|
| **OQ-1 Fernet** | include in this arc vs defer one slice | **Include** (it is the pull-forward incentive); §6 simplification offers defer | operator-binding (security posture) |
| **OQ-2 re-setup UX** | force re-setup (U-A) vs auto-migrate JSON (U-B) | **U-A force re-setup** | operator-binding (UX) |
| **OQ-3 pin** | `==3.0.5` vs `>=3.0.5,<4.0.0` (or conservative `<3.1.0`) | **`>=3.0.5,<4.0.0` ONLY WITH the DDL-drift guard test (§5.1/§10 T1b)**; else the conservative **`<3.1.0`**. We copy schwabdev's PRIVATE internal table DDL (W-A), so a future 3.x that changes the schema/encryption would silently desync our writer -- the guard test (introspect the live `schwabdev` table vs our pinned copy, fail loudly on drift) is what makes the floored range safe. | operator preference (security-patch latitude vs drift risk) |
| **OQ-4 L2 re-anchor** | the rationale + sign-off mechanics; FIRST-EVER baseline move | §7 design + explicit operator sign-off at the gate; endpoint-diff proves zero new endpoints | **operator-binding (the sign-off IS the gate)** |
| **OQ-5 P14.N7+F-1 disposition** | DELETE badge (D5-DELETE) vs REWIRE to v3 freshness | **D5-DELETE** + `status` as the health surface | operator-binding (UX) |
| **OQ-6 deploy cutover** | when the re-setup happens | at merge time, before first v3 run (§11) | operator-binding (ops) |
| **OQ-7 Codex chain count** at writing-plans/executing-plans | single vs per-slice | **single chain at end** of each phase | operator preference |

---

## §14 Cumulative discipline compliance (the Schwab gotcha checklist + L2 re-anchor)

- **Every Schwab gotcha** in the CLAUDE.md block maps to a §10 re-validation (G1-G6) -- logger-name redaction, `update_tokens` post-state, sandbox gate, price_history daily, typed-error audit close, source-artifact shape -- PLUS the `setup`-needs-clean-DB gotcha (re-validated for `.db` semantics, §5.4) and the plaintext-tokens gotcha (retired by §6 if Fernet ships).
- **Gotcha #11 (atomic consistency):** the P14.N7/F-1 reconciliation (§5.3) reconciles ALL sidecar readers/writers + the base-VM field + the template in ONE task. The `tokens_db` schema-DDL copy (W-A) is pinned to installed-3.0.5 with a load-back test.
- **Gotcha #15 (production-path tests):** §10 mandates real-construction token-storage tests + the live-OAuth gate; no stub-bypass "strong substitute" claims.
- **Gotcha #16/#32 (ASCII):** all CLI status strings + the L2 test module stay ASCII (the v3 status renderer must not introduce non-ASCII glyphs -- PowerShell cp1252).
- **Discipline #2 (signature/anchor re-grep):** every file:line in §3 is re-grepped at writing-plans (the findings doc + this spec cite f1b008d; line numbers shift).
- **Co-Authored-By / trailer hazard:** ZERO `Co-Authored-By`; NO `--no-verify`; the final `-m` paragraph of every commit is PLAIN PROSE (no `Word:` leading line); verify `git log -1 --format='%(trailers)'` is `[]` before any push (memory `feedback_commit_message_trailer_parse_hazard`).
- **L2 re-anchor:** §7 -- the FIRST sanctioned baseline move; audited + operator-signed + endpoint-diff-proven.

---

## §15 Position note

This is the **FIRST commissioned Phase-15 arc** (Phase 14 CLOSED 2026-06-02 at schema v23). It is a dependency migration on the L2-LOCKED Schwab surface. It:
- **REMOVES the now-SHIPPED P14.N7 daemon-checker resilience wrapper** (v3's sync `Client` eliminates the failure mode by construction);
- **RECONCILES the SHIPPED F-1 web checker-liveness badge** (recommend DELETE; `swing schwab status` becomes the single token-health surface);
- performs the **FIRST-EVER L2-LOCK baseline re-anchor** (audited, operator-signed, endpoint-diff-proven -- spirit = zero new endpoints preserved);
- optionally **retires the plaintext-OAuth-at-rest gotcha** via Fernet (OQ-1);
- changes **NO swing-DB schema** (v23 holds; the tokens DB is schwabdev-internal);
- is gated by an **operator LIVE-OAuth re-setup smoke** (mock tests insufficient for the auth/token path).

The exact-3.0.5 surface was confirmed against an installed throwaway venv (L5): the findings doc (`9d4f6a4`, which read GitHub `main`/3.0.4) is correct on every behavioral point; the only divergence is cosmetic (`schwabdev.__version__` reads `3.0.4` inside the 3.0.5 distribution -- Note A). After this lands, SB5.5's P14.N7 component is fully superseded; A-3 (web market-data) is untouched and remains shipped.

---

*End of design spec. Derive the implementation plan via copowers:writing-plans. Operator triage required on OQ-1 (Fernet), OQ-4 (L2 re-anchor sign-off), OQ-5 (P14.N7/F-1 disposition) before plan finalization.*
