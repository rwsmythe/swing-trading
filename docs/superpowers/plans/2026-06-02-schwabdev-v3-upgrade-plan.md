# schwabdev 2.5.1 -> 3.0.5 Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **CLI in the worktree: `python -m swing.cli` (NOT bare `swing`).**

**Goal:** Migrate the project's only brokerage dependency from `schwabdev 2.5.1` to `3.0.5` -- the FIRST commissioned Phase-15 arc -- by re-pinning, fixing every breaking change (token storage JSON-file -> SQLite DB, `account_linked` -> `linked_accounts`, constructor kwarg `tokens_file=` -> `tokens_db=`), removing the now-dead P14.N7 daemon-checker wrapper + deleting the F-1 topbar badge, adding optional Fernet token-at-rest encryption, and performing the FIRST-EVER L2-LOCK baseline re-anchor -- all with NO swing-DB schema change.

**Architecture:** Four risk-ordered slices. Slice 1 lands the mechanical, fully-test-coverable changes (re-pin + renames + constructor kwarg + signature pins + the G1-G6 gotcha re-validations). Slice 2 is the risk-concentrated token-storage core: a v3-SQLite writer (W-A: we own a pinned 8-column DDL, bounded by a load-back regression + a DDL-drift guard), a presence-only v3-SQLite status reader, a COMPREHENSIVE non-setup preflight (the PRIMARY defense against v3's interactive-auth-at-construction hazard), the non-interactive construction guard (defense-in-depth with deterministic `del`+`gc.collect()` lock release), and the `revoke_and_delete` logout rewrite. Slice 3 deletes the P14.N7 wrapper + F-1 badge + full blast radius in ONE atomic task. Slice 4 ships Fernet, the audited L2 re-anchor (with an explicit operator-sign-off GATE), the binding operator LIVE-OAuth smoke (G7), and the CLAUDE.md refresh. Fernet plumbing is threaded through Slice 2 with `fernet_key=None` (encryption off); Slice 4 supplies the key source and turns it on.

**Tech Stack:** Python 3.14, schwabdev 3.0.5, `sqlite3`, `cryptography` (Fernet, transitive), FastAPI + Starlette 1.0, Jinja2, `importlib.metadata`, `gc`, pytest (`-m "not slow"`), ruff. CLI in worktree: `python -m swing.cli`.

---

## §A Goals / Non-goals

### §A.1 Goals (in scope)
1. **Re-pin** `pyproject.toml` from `schwabdev>=2.4.0,<3.0.0` to the OQ-3 floored range `>=3.0.5,<4.0.0` -- COUPLED to the T1b DDL-drift guard (the floored range is unsafe without it; see §C.1).
2. **`account_linked()` -> `linked_accounts()`** at the 2 real call sites + the signature-pin test rename + the `importlib.metadata` distribution-version test (Note A).
3. **Constructor kwarg `tokens_file=` -> `tokens_db=`** at the 4 real `schwabdev.Client(` sites (all in `auth.py`).
4. **Token-storage rewrite** (§C.3): the v3-SQLite writer (W-A), the presence-only v3-SQLite reader + the status DEGRADED-health re-map, the comprehensive non-setup preflight, the non-interactive construction guard, the `revoke_and_delete` logout rewrite + delete-without-revoke fallback.
5. **P14.N7 + F-1 reconciliation** (OQ-5 = DELETE): remove the daemon-checker wrapper + the badge + the full blast radius (the `schwab_checker_badge` field across ALL base-layout VMs + the 8 build call sites + the topbar block + the 6 checker tests) in ONE atomic task. The `/schwab/status` PAGE is PRESERVED (re-sourced via the Slice-2 reader).
6. **Fernet token-at-rest encryption** (OQ-1 = include): key in `~/swing-data/user-config.toml` `[integrations.schwab]` `encryption_key`, masked by `swing config show`, generated at setup; writer enc-wrap; revoke decrypt; preflight decryptability.
7. **L2-LOCK re-anchor** (OQ-4): bump `L2_LOCK_BASELINE_SHA` + audited rationale block + the endpoint-diff artifact (proves ZERO new endpoints) + a grep-still-functions health test + an EXPLICIT operator-sign-off GATE at executing-plans (the SHA is filled on the REAL post-migration HEAD; NOT a silent move).
8. **The binding operator LIVE-OAuth re-setup smoke (G7)** + CLAUDE.md refresh.
9. **G1-G6 Schwab-gotcha re-validation** (L4) -- one test each.

### §A.2 Non-goals (OUT of scope -- do NOT plan/implement)
- ANY new Schwab REST endpoint / feature / market-data source (the lock's SPIRIT holds through the re-anchor; the §G endpoint diff is the proof).
- ANY swing-DB schema change / migration / `EXPECTED_SCHEMA_VERSION` bump (L3 -- the tokens DB is schwabdev-internal SQLite under `~/swing-data/`).
- A-3 web market-data wiring / SB5.5 re-work (shipped; leave it) -- EXCEPT the F-1 badge DELETE + the `/schwab/status` re-source.
- D5-REWIRE the badge to v3 freshness (rejected; OQ-5 = DELETE) or a NEW `/schwab/status` widget (§C.5 -- the `last_success_at`/`last_failure_at`/days-remaining signals already exist).
- Option U-B auto-migrate the 2.x JSON secret bytes (rejected; OQ-2 = U-A force re-setup).
- Option W-B `call_for_auth` web-setup redesign (rejected; W-A preserves the SHIPPED two-phase paste flow).
- `ClientAsync` adoption; Schwab auth/token cassettes (V2 PLANNED -- V1 stays mock + the live-OAuth gate); OS-keyring/DPAPI Fernet-key storage (V2 -- V1 is user-config + ACL).
- A schwabdev 4.x jump.
- Constructing a `schwabdev.Client` for a version assertion (use `importlib.metadata.version("schwabdev")`, NOT `schwabdev.__version__` which reads `3.0.4` inside the 3.0.5 dist -- Note A).

---

## §B File map

All paths relative to repo root. **(N)** = new, **(M)** = modify, **(D)** = delete, **(R)** = reuse read-only. Line numbers re-grepped at `4975df6` (the dispatch HEAD); re-grep again at executing-plans (discipline #2).

### §B.1 Production -- modified
| File | Disp | Slice | Responsibility |
|------|------|-------|----------------|
| `pyproject.toml:20` | **(M)** | 1 | `schwabdev>=2.4.0,<3.0.0` -> `>=3.0.5,<4.0.0` (OQ-3; COUPLED to T1b). |
| `swing/integrations/schwab/trader.py:270` | **(M)** | 1 | `client.account_linked()` -> `client.linked_accounts()` (the internal mapper `map_account_linked_to_hash_set` name STAYS -- not a schwabdev call). |
| `swing/integrations/schwab/auth.py:653` (`_stub_call_account_linked`) | **(M)** | 1 | `client.account_linked()` -> `client.linked_accounts()`. The variable/audit-label names (`call_id_account_linked`, `_finalize_setup_account_linked`, endpoint label `accounts.linked`) STAY (internal naming, not schwabdev calls). |
| `swing/integrations/schwab/auth.py` (4 construction sites: **762, 901, 1684, 1864**) | **(M)** | 1 (rename) / 2 (guard) / 4 (encryption) | `tokens_file=str(tokens_path)` -> `tokens_db=str(tokens_path)`. Slice 2 adds `call_on_auth=_raise_on_auth` + `open_browser_for_auth=False` to the 2 NON-setup sites (762 fetch, 1864 force_refresh). Slice 4 adds `encryption=_resolve_fernet_key(cfg)` to all 4. |
| `swing/integrations/schwab/auth.py:1335` (`_write_schwabdev_tokens_file`) | **(M)** | 2 | JSON-mirror writer -> v3-SQLite writer (W-A). Rename to `_write_schwabdev_tokens_db`; keep a thin alias if any caller imports the old name (re-grep). |
| `swing/integrations/schwab/auth.py` (NEW `_raise_on_auth`, `_V3_SCHWABDEV_DDL`, `_assert_v3_tokens_db_loadable_or_raise`, `_read_v3_refresh_token`) | **(N)** | 2 | The guard callback, the pinned DDL, the comprehensive preflight, the revoke-side refresh-token reader (decrypts when `fernet_key` passed). |
| `swing/integrations/schwab/auth.py:2025` (`revoke_and_delete`) | **(M)** | 2 (rewrite) / 4 (decrypt) | Read refresh_token from v3 SQLite (not `json.load`); rename-first/best-effort-revoke; delete-without-revoke fallback; hard-rename-failure clean error. Slice 4 adds Fernet decrypt. |
| `swing/cli_schwab.py:469` (`_read_tokens_metadata`) | **(M)** | 2 | `json.load` -> v3-SQLite presence-only read (`mode=ro` URI; locked-DB tolerance; old-format detection). Returns NO secret bytes. |
| `swing/cli_schwab.py` DEGRADED-health predicate (`~:605-741`) | **(M)** | 2 | Re-map signals 3-7 from JSON `token_dictionary`/`refresh_token_issued` to v3 columns (no-row / empty-`refresh_token`-column / `refresh_token_issued`-column). |
| `swing/cli_schwab.py:834-842` (checker-liveness block) | **(D)** | 3 | The P14.N7 status liveness import + render. Deleted with the wrapper. |
| `swing/integrations/schwab/auth.py:21-23, 614, 889-890, 1780, 1803` (docstrings embedding `tokens_file=`) + `pipeline_steps.py:92` | **(M)** | 1 | Update the prose that embeds the literal 2.5.1 `tokens_file=` signature (drives the L2 re-anchor; land before computing the baseline). |
| `swing/config.py` + `swing/config_user.py` + `swing/cli.py` (`config show`) | **(M)** | 4 | Add `encryption_key` to `[integrations.schwab]` resolution + mask it in `config show` (mirror `client_secret`). `_resolve_fernet_key(cfg)` helper. |
| `swing/web/app.py:259-324` (`_install_web_marketdata_caches` checker block) | **(D)/(M)** | 3 | Delete the checker install + STARTING-sidecar seed + readback. The A-3 ladder install STAYS (re-grep the exact span to delete only the P14.N7 portion). |
| `CLAUDE.md` Schwab gotcha block + status-line | **(M)** | 4 | Retire the plaintext-tokens gotcha (Fernet ships), add the daemon-checker-deleted note, the `.db` setup-clean semantics, the L2 re-anchor record. |

### §B.2 Production -- deleted (Slice 3, ONE atomic task)
| File | Disp | What |
|------|------|------|
| `swing/integrations/schwab/checker_resilience.py` (255 LOC) | **(D)** | Dead on v3 (no daemon to wrap). |
| `swing/web/view_models/schwab_checker_badge.py` (63 LOC) | **(D)** | The F-1 badge VM module. |
| `swing/web/templates/base.html.j2:81-84` | **(M)** | Delete the topbar badge block. |
| `swing/web/view_models/*.py` -- the `schwab_checker_badge` field (~20 declarations across 12 modules) | **(M)** | Remove the field from EVERY base-layout VM in ONE task (gotcha #11 + shared-`base.html.j2`). See §C.4 for the full enumeration. |
| 8 `build_schwab_checker_badge(...)` call sites | **(M)** | dashboard.py:1533-1535, config.py:168-170, pipeline.py:71/80, watchlist.py:217/234, metrics/index.py:441/450, journal.py:251-257, schwab.py:563/580, routes/schwab.py:227/238. (**Spec §3 said "two" -- the live tree has EIGHT; see §C.4 divergence note.**) |

### §B.3 Reuse (read-only -- DO NOT modify)
| File | What is reused |
|------|----------------|
| `swing/integrations/schwab/auth.py:299` (`_rename_stale_tokens_db`) | The bounded-retry + audit-on-failure atomic rename-aside; reused by the logout rewrite's rename-first step and the U-A re-setup path. It renames ONLY the `.db` (no `-journal`/`-wal`/`-shm` sibling loop); v3 uses a rollback journal (no WAL) -- an orphaned `-journal` is inert (SQLite applies a journal only to a present same-named DB). See §C.6 (T-RENAME). |
| `swing/integrations/schwab/auth.py:611` (`_resolve_tokens_db_path`) | `~/swing-data/schwab-tokens.{env}.db` path resolution (UNCHANGED -- path value identical pre/post). |
| `swing/integrations/schwab/marketdata.py:378` (`get_price_history`) | The 8 explicit camelCase kwargs (G4 daily-bar discipline; identical on v3). |
| `swing/integrations/schwab/audit_service.py` | `record_call_start` / `record_call_finish` (the `schwab_api_calls` audit rows -- UNCHANGED). |
| `swing/web/view_models/schwab.py:365` (`build_schwab_status_vm`) | The `/schwab/status` PAGE builder -- consumes `_read_tokens_metadata` (Slice-2 reader) + `_compute_degraded_state` + `list_recent_calls`. PRESERVED; re-sourced transitively (§C.5). |
| `swing/data/db.py:51` (`EXPECTED_SCHEMA_VERSION = 23`) | Asserted UNCHANGED (L3). |
| `tests/integration/test_l2_lock_source_grep.py:26` | `L2_LOCK_BASELINE_SHA = "bf7e071"`; pattern `schwabdev.Client.` (line 30); re-anchored in Slice 4. |
| spec installed-3.0.5 anchors (L5, already verified) | `Client.__init__(app_key, app_secret, callback_url, tokens_db, encryption, timeout, call_on_auth, open_browser_for_auth)`; the 8-col `schwabdev` DDL (`tokens.py:80-91`); logger `"Schwabdev"` (`client.py:41`); `update_tokens(force_access_token, force_refresh_token) -> bool` (`client.py:142`); refresh TTL `7*24*60*60` (`tokens.py:64`); refresh threshold `3630s` (`tokens.py:293`); `enc:` prefix (`tokens.py:120-134`); construction calls `update_tokens()` (`client.py:43`); `_update_refresh_token` `BEGIN EXCLUSIVE` with NO try/finally around `call_for_auth` (`tokens.py:395-422`). |

### §B.4 Tests
| File | Disp | Covers |
|------|------|--------|
| `tests/integrations/test_schwab_trader_kwarg_signatures.py:31-42` | **(M)** | Slice 1: `test_account_linked_no_kwargs_required` -> `test_linked_accounts_no_kwargs_required` (inspect.signature(`linked_accounts`)). |
| `tests/integrations/schwab/test_schwabdev_version_pin.py` | **(N)** | Slice 1: `importlib.metadata.version("schwabdev")` is in `[3.0.5, 4.0.0)` (Note A; NOT `__version__`). |
| `tests/integrations/schwab/test_construct_client_kwargs.py` | **(N)** | Slice 1: each of the 4 construction sites passes `tokens_db=` (not `tokens_file=`); Slice 2 extends with the guard kwargs on the 2 non-setup sites. |
| `tests/integrations/schwab/test_gotcha_revalidation_v3.py` | **(N)** | Slice 1: G1-G6 (logger name `Schwabdev`; `update_tokens` post-state; sandbox `environment=='production'` gate; `price_history` 8-kwarg; typed-error audit close on the `linked_accounts` path; source-artifact shape). |
| `tests/integrations/schwab/test_v3_tokens_writer.py` | **(N)** | Slice 2: T1 writer load-back (real `Client` constructs against our-written DB; `tokens.access_token` loads); T1b DDL-drift guard (PRAGMA vs pinned DDL, `del`+`gc.collect()`). |
| `tests/cli/test_v3_tokens_reader.py` | **(N)** | Slice 2: T2 (no secret bytes returned); T3 (DEGRADED signal re-map); T4 (locked-DB tolerance); T5 (old-format detection); T6 (7-day TTL pin). |
| `tests/integrations/schwab/test_v3_preflight.py` | **(N)** | Slice 2: T8 (old-format -> clean `SchwabAuthError` BEFORE construct); T9a (stale refresh -> clean error, no `input()`); T9b (key-loss on construction path); T9c (residual-race guard leaves no locked DB). |
| `tests/integrations/schwab/test_v3_logout_revoke.py` | **(N)** | Slice 2: T7a (fresh DB -> read SQLite refresh_token, revoke, rename); T7c (old-format/missing-key -> delete-without-revoke fallback + WARNING, still renamed); T7d (hard rename failure -> clean actionable error after bounded retry, no silent partial state). Slice 4 adds T7b (encrypted DB decrypt). |
| `tests/integration/test_schwab_status_page_v3_reader.py` | **(N)** | Slice 2: `/schwab/status` renders token-health off the v3 reader (production-path, gotcha #15; §C.5 / §1.2). |
| `tests/web/test_checker_badge_deleted.py` | **(N)** | Slice 3: zero references to `checker_resilience` / `schwab_checker_badge` / `build_schwab_checker_badge` / `evaluate_liveness_state` remain in `swing/`; EVERY base-layout route renders 200 with no `UndefinedError`. |
| 6 checker test files (`tests/cli/test_schwab_status_checker_liveness.py`, `tests/integration/schwab/test_checker_liveness_state.py`, `tests/integration/schwab/test_checker_resilience.py`, `tests/web/test_checker_liveness_install_path.py`, `tests/web/test_schwab_checker_badge.py`, `tests/web/test_schwab_checker_badge_topbar.py`) | **(D)** | Slice 3: deleted with the wrapper/badge. |
| `tests/integrations/schwab/test_fernet_tokens.py` | **(N)** | Slice 4: key masking in `config show`; `_resolve_fernet_key` None/value; writer enc-wrap; real `Client(encryption=key)` load-back; revoke decrypt (T7b); key-loss preflight (cross-link T9b). |
| `tests/integration/test_l2_lock_source_grep.py` | **(M)** | Slice 4: re-anchored subset-check passes; grep-still-functions health test; endpoint-diff artifact present. |
| `tests/data/test_no_schema_change_v3.py` | **(N)** | Slice 4: `EXPECTED_SCHEMA_VERSION == 23`; no NEW file under `swing/data/migrations/` vs the dispatch HEAD (L3). |

### §B.5 Docs / artifacts
| File | Disp | What |
|------|------|------|
| `docs/schwab-v3-endpoint-diff.md` | **(N)** | Slice 4: the §G endpoint-set diff artifact (pre/post; ZERO new endpoints) referenced by the L2 rationale block. |
| `CLAUDE.md` | **(M)** | Slice 4: Schwab gotcha-block + status-line refresh. |

---

## §C Cross-cutting design notes (read before any task)

### §C.1 OQ-3 coupling: the floored pin is unsafe without T1b
We adopt W-A (we own a verbatim copy of schwabdev's PRIVATE 8-column `schwabdev` table DDL). A future 3.x that changes that private schema/encryption would silently desync our writer. The floored range `>=3.0.5,<4.0.0` (OQ-3) is therefore SAFE **only** once the T1b DDL-drift guard (Slice 2) introspects the LIVE installed `schwabdev` table (`PRAGMA table_info`) vs our pinned copy and fails loudly on drift.

**Executing-plans sequencing (BINDING):** Slice 1 Task 1.1 sets the floored range and installs 3.0.5 so the rest of the suite runs on v3. **T1b is the FIRST task of Slice 2** and the arc MUST NOT merge to `main` until T1b is green. If the executing implementer descopes T1b, REVERT the pin to the conservative `<3.1.0` (per OQ-3) in the same commit. The pin and the guard are COUPLED; do not merge a floored pin without its guard.

### §C.2 Preflight is PRIMARY; the construction guard is defense-in-depth
v3's `Client.__init__` calls `tokens.update_tokens()` at construction (`client.py:43`). On a missing/undecryptable/stale-refresh row it enters the INTERACTIVE auth flow (`input()` + default browser launch). In a headless context (`swing web`, the pipeline subprocess, `swing schwab fetch`) that BLOCKS on stdin forever or pops a browser -- a production hazard.

- **PRIMARY defense:** the COMPREHENSIVE preflight `_assert_v3_tokens_db_loadable_or_raise` (§C.3 / Task 2.6) reads the v3 DB directly (NOT by constructing a `Client`) and asserts (1) v3 `schwabdev` table present; (2) one token row; (3) refresh token FRESH (`rt_delta >= 3630s`) so construction won't force a refresh; (4) decryptability driven by the column `enc:` prefix, NOT the config flag (the key-loss gap). With (1)-(4) passing, construction's `update_tokens()` finds a fresh loadable row and never enters `_update_refresh_token` -> the callback never fires -> no open-tx hazard.
- **Defense-in-depth (the BELT):** `call_on_auth=_raise_on_auth` + `open_browser_for_auth=False` on the 2 non-setup sites. This catches ONLY the residual race (a refresh token that expires between the preflight read and the construct). It is NOT the primary defense: schwabdev's `_update_refresh_token` runs `BEGIN EXCLUSIVE` with NO try/finally around `call_for_auth` (`tokens.py:395-422`), so raising inside `call_on_auth` SKIPS schwabdev's rollback and holds the EXCLUSIVE lock until the partially-constructed object is collected. **When the guard fires, the caller MUST `del` the construction-frame locals + `gc.collect()`** to release the lock deterministically before any subsequent tokens-DB read (T9c).

The SETUP paths (901, 1684) do NOT need the preflight (setup calls `_rename_stale_tokens_db` then writes a fresh valid DB before constructing the load-back `Client`). Passing the guard kwargs there too is harmless and uniform, but the preflight is wired ONLY before the 2 non-setup sites (762, 1864).

### §C.3 The W-A writer + reader + preflight (token-storage core)
v3 tokens-DB schema (`tokens.py:80-91`), table `schwabdev`, single row (writer does `DELETE` then `INSERT`):

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

`_V3_SCHWABDEV_DDL` is a verbatim copy of the installed-3.0.5 DDL with a comment pinning the source. The writer preserves our atomic-write discipline (`mkstemp` in the DEST dir + `os.replace` -- never cross-volume). The reader returns ONLY non-secret presence fields (issued timestamps + `expires_in` + a boolean "refresh_token present") -- STRONGER than the 2.x reader (never holds the secret bytes). The `enc:` wrapping is applied IFF a `fernet_key` is passed (None in Slice 2 -> plaintext; Slice 4 supplies the key).

**Fernet threading (Slice 2 builds the plumbing OFF):** the writer, the preflight, and the revoke reader all take an optional `fernet_key` param defaulting to `None`. In Slice 2 every caller passes `None` (plaintext, exactly as 2.x behaved). Slice 4 wires `_resolve_fernet_key(cfg)` into those callers + the 4 construction sites' `encryption=`. This keeps Slice 2 and Slice 4 conflict-free: Slice 2 ships the param-threaded code paths; Slice 4 turns the key on.

### §C.4 Badge DELETE blast radius (gotcha #11 -- ONE atomic task)
**DIVERGENCE FROM SPEC (flagged per brief §7):** spec §3 says "the two `build_schwab_checker_badge(cfg)` call sites (`dashboard.py:1535`, `routes/schwab.py:238`)". The LIVE tree at `4975df6` has **EIGHT** call sites and **~20 field declarations across 12 VM modules**. The plan TRUSTS the live tree. Full enumeration (re-grep at executing-plans):

- **`schwab_checker_badge` field declarations (remove ALL):** dashboard.py:391; error.py:32; config.py:56; pipeline.py:31; watchlist.py:62; trades.py:1205,1428,1465,1707; metrics/shared.py:65; reconcile.py:216,889; journal.py:214,598; schwab.py:93,254,606.
- **`build_schwab_checker_badge(...)` call sites (remove ALL 8):** dashboard.py:1533-1535; config.py:168-170; pipeline.py:71/80; watchlist.py:217/234; metrics/index.py:441/450; journal.py:251-257 (dict form); schwab.py:563/580; routes/schwab.py:227/238.
- **Template:** base.html.j2:81-84 (the `{% if vm.schwab_checker_badge %}` topbar block).
- **Module:** swing/web/view_models/schwab_checker_badge.py (delete entirely).

All in ONE atomic commit so no intermediate state leaves a `base.html.j2` reference to a removed field (a Jinja `UndefinedError` on unrelated routes) or an orphan import.

### §C.5 `/schwab/status` PAGE is PRESERVED (NOT the badge)
The OQ-5 DELETE removes the topbar BADGE (`build_schwab_checker_badge`, the daemon-alive chip) -- a SEPARATE surface from the `/schwab/status` PAGE (`build_schwab_status_vm`, schwab.py:365). The page renders `vm.state`/`degraded_banner_active`, `vm.refresh_token_days_remaining`/`severity`/`expires_at`, **`vm.last_success_at`/`vm.last_failure_at`**, `vm.recent_calls` -- composed from `_compute_degraded_state` + `_read_tokens_metadata` + `list_recent_calls`. NONE of it is checker-liveness sidecar data. The page is kept fully working by the Slice-2 `_read_tokens_metadata` re-source (JSON -> v3 SQLite); the `schwab_api_calls`-fed fields are UNCHANGED. **Do NOT add a new "last successful call" widget -- it already exists; just keep it fed.** A production-path regression (`test_schwab_status_page_v3_reader.py`) asserts the page renders token-health off the v3 reader.

### §C.6 Reused-helper notes
- **T-RENAME:** `_rename_stale_tokens_db` renames only the `.db`. v3 sets `busy_timeout` only (NO `WAL` pragma -- `tokens.py:92`), so it uses a rollback journal; an orphaned `-journal` from a rename-aside is inert. The logout rewrite (Task 2.7) ASSERTS this inertness in a test rather than adding a sibling loop (minimal-delta; gotcha #11 atomic-consistency satisfied by the explicit assertion).
- **ASCII (#16/#32):** every new/edited CLI status string + the L2 test module stays ASCII (PowerShell cp1252).

---

## §D Slice 1 -- Re-pin + mechanical renames + signature pins + gotcha re-validation

**Risk:** LOW (fully test-coverable). **Codex convergence:** folded into the single end-of-phase chain. **Goal:** green the suite (minus the token-storage + L2 tests, which arrive in Slice 2/4) on v3 with every mechanical breaking-change fixed.

### Task 1.1: Re-pin schwabdev to the OQ-3 floored range + install 3.0.5

**Files:**
- Modify: `pyproject.toml:20`
- Test: `tests/integrations/schwab/test_schwabdev_version_pin.py` (Create)

- [ ] **Step 1: Write the failing test** (`test_schwabdev_version_pin.py`)

```python
"""Pin the installed schwabdev DISTRIBUTION version (Note A: schwabdev.__version__
reads '3.0.4' inside the 3.0.5 dist -- assert the distribution metadata, not __version__)."""
import importlib.metadata as md

from packaging.version import Version


def test_schwabdev_distribution_in_v3_floored_range() -> None:
    v = Version(md.version("schwabdev"))
    # Pre-fix path: installed 2.5.1 -> Version("2.5.1") -> FAILS the >=3.0.5 bound.
    # Post-fix path: installed 3.0.5 -> Version("3.0.5") -> passes both bounds.
    assert Version("3.0.5") <= v < Version("4.0.0"), (
        f"schwabdev distribution {v} outside the OQ-3 floored range [3.0.5, 4.0.0); "
        "re-pin pyproject.toml and `pip install -e \".[dev,web]\"`."
    )


def test_version_test_uses_distribution_not_dunder() -> None:
    # Guard against regressing to schwabdev.__version__ (reads 3.0.4 in the 3.0.5 dist).
    import schwabdev
    assert md.version("schwabdev") != getattr(schwabdev, "__version__", None) or True
    # The meaningful assertion is that the pin test above reads md.version, not __version__.
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd .worktrees/schwabdev-v3-upgrade-writing-plans && python -m pytest tests/integrations/schwab/test_schwabdev_version_pin.py -v`
Expected: FAIL -- installed `schwabdev` is still `2.5.1` (`Version("2.5.1") < Version("3.0.5")`).

- [ ] **Step 3: Re-pin + install**

Edit `pyproject.toml:20`:
```toml
    "schwabdev>=3.0.5,<4.0.0",
```
Then: `python -m pip install -e ".[dev,web]"` (re-resolves; pulls `cryptography` + `aiohttp` transitively -- Note B: a materially heavier tree; flagged, non-blocking).

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/integrations/schwab/test_schwabdev_version_pin.py -v`
Expected: PASS (installed `3.0.5`).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/integrations/schwab/test_schwabdev_version_pin.py
git commit -m "feat(schwab): re-pin schwabdev to the v3 floored range and install 3.0.5

The floored range is coupled to the Slice 2 T1b DDL-drift guard; the arc does not
merge until that guard is green or the pin falls back to the conservative ceiling."
```

> **SEQUENCING (BINDING, §C.1):** do NOT merge this floored pin to `main` until Slice 2 T1b is green. If T1b is descoped, revert this line to `schwabdev>=3.0.5,<3.1.0`.

### Task 1.2: Rename `account_linked()` -> `linked_accounts()` (2 real call sites) + signature-pin test

**Files:**
- Modify: `swing/integrations/schwab/auth.py:653` (`_stub_call_account_linked`); `swing/integrations/schwab/trader.py:270`
- Modify: `tests/integrations/test_schwab_trader_kwarg_signatures.py:31-42`

- [ ] **Step 1: Write the failing test** (rename in `test_schwab_trader_kwarg_signatures.py`)

```python
def test_linked_accounts_no_kwargs_required() -> None:
    """`Client.linked_accounts()` takes no parameters beyond self (v3 rename of
    account_linked; same REST path /trader/v1/accounts/accountNumbers)."""
    import inspect

    import schwabdev

    # Pre-fix path: on v3, schwabdev.Client.account_linked does not exist ->
    #   the OLD test raised AttributeError. linked_accounts exists (client.py:181).
    # Post-fix path: linked_accounts resolves; params beyond self == ().
    sig = inspect.signature(schwabdev.Client.linked_accounts)
    params = tuple(p for p in sig.parameters if p != "self")
    assert params == (), (
        f"Schwabdev linked_accounts signature changed; expected no params, got {params}."
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/integrations/test_schwab_trader_kwarg_signatures.py::test_linked_accounts_no_kwargs_required -v`
Expected: PASS at the signature level (v3 has `linked_accounts`) BUT the production call sites still call `account_linked()`. Add a second discriminating assertion that exercises the production seam:

```python
def test_stub_call_uses_linked_accounts(monkeypatch) -> None:
    """The setup seam invokes client.linked_accounts(), not the removed account_linked()."""
    from swing.integrations.schwab import auth

    class _FakeClient:
        def __init__(self) -> None:
            self.called = []
        def linked_accounts(self):
            self.called.append("linked_accounts")
            return "OK"
        def account_linked(self):  # pragma: no cover - must NOT be called on v3
            self.called.append("account_linked")
            raise AssertionError("account_linked is removed on v3")

    fake = _FakeClient()
    # Pre-fix: _stub_call_account_linked calls account_linked -> AssertionError.
    # Post-fix: calls linked_accounts -> returns "OK".
    assert auth._stub_call_account_linked(fake) == "OK"
    assert fake.called == ["linked_accounts"]
```

Run it: Expected FAIL (`_stub_call_account_linked` still calls `account_linked`).

- [ ] **Step 3: Rename the 2 call sites**

`auth.py:653`: `result = client.linked_accounts()`
`trader.py:270`: `client_method=lambda: client.linked_accounts(),`
(Leave `map_account_linked_to_hash_set`, `call_id_account_linked`, `_finalize_setup_account_linked`, endpoint label `accounts.linked` UNCHANGED -- internal names.)

- [ ] **Step 4: Run both tests -- verify pass**

Run: `python -m pytest tests/integrations/test_schwab_trader_kwarg_signatures.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/auth.py swing/integrations/schwab/trader.py tests/integrations/test_schwab_trader_kwarg_signatures.py
git commit -m "feat(schwab): rename account_linked to linked_accounts at the two call sites

Same REST endpoint, v3 method rename; internal mapper and audit-label names are unchanged."
```

### Task 1.3: Constructor kwarg `tokens_file=` -> `tokens_db=` (4 sites) + prose churn

**Files:**
- Modify: `swing/integrations/schwab/auth.py` (762, 901, 1684, 1864) + the docstrings at 21-23, 614, 889-890, 1780, 1803
- Modify: `swing/integrations/schwab/pipeline_steps.py:92`
- Test: `tests/integrations/schwab/test_construct_client_kwargs.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
"""Each schwabdev.Client construction site passes tokens_db= (v3), not tokens_file= (2.x)."""
from unittest.mock import patch

from swing.integrations.schwab import auth


def test_construct_authenticated_client_passes_tokens_db(monkeypatch, tmp_path) -> None:
    captured = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.tokens = type("T", (), {"access_token": "x"})()

    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: tmp_path / "schwab-tokens.production.db")
    # Bypass the Slice-2 preflight for this mechanical test (or assert it is a no-op pre-Slice-2).
    with patch.object(auth.schwabdev, "Client", _FakeClient):
        # construct against a path; the kwarg of interest is tokens_db=.
        try:
            auth.construct_authenticated_client(_FakeCfg(), "production", "id", "secret")
        except Exception:
            pass
    # Pre-fix path: captured has 'tokens_file'; 'tokens_db' absent -> FAIL.
    # Post-fix path: captured has 'tokens_db'; 'tokens_file' absent -> PASS.
    assert "tokens_db" in captured
    assert "tokens_file" not in captured
```

(`_FakeCfg` is a minimal cfg stub with `integrations.schwab.callback_url` + `timeout_seconds`; define it inline in the test module.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integrations/schwab/test_construct_client_kwargs.py -v`
Expected: FAIL (`tokens_file` captured, `tokens_db` absent).

- [ ] **Step 3: Rename the kwarg at all 4 sites + update the embedded-signature prose**

At auth.py 762, 901, 1684, 1864: `tokens_db=str(tokens_path),`
Update docstrings (auth.py 21-23, 614, 889-890, 1780, 1803; pipeline_steps.py:92) that embed the literal 2.5.1 `tokens_file=` signature to read `tokens_db=` (these are the L2-churn prose lines; landing them here lets Slice 4 compute the final baseline).

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/integrations/schwab/test_construct_client_kwargs.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/auth.py swing/integrations/schwab/pipeline_steps.py tests/integrations/schwab/test_construct_client_kwargs.py
git commit -m "feat(schwab): rename the tokens_file constructor kwarg to tokens_db at the four sites

Mechanical v3 kwarg rename plus the embedded-signature prose that the L2 re-anchor absorbs."
```

### Task 1.4: G1-G6 Schwab-gotcha re-validation on v3 (L4)

**Files:**
- Test: `tests/integrations/schwab/test_gotcha_revalidation_v3.py` (Create)

- [ ] **Step 1: Write the tests** (one per gotcha; all assert the gotcha SURVIVES on v3)

```python
"""L4: every Schwab gotcha re-validated against schwabdev 3.0.5."""
import importlib.metadata as md
import inspect
import logging

import schwabdev


def test_g1_logger_name_is_capital_s_schwabdev() -> None:
    # The redaction factory's prefix-check depends on the exact logger name.
    # Pre-fix risk: a v3 rename to 'schwabdev' (lowercase) would slip records past redaction.
    # Post-fix: v3 still uses getLogger("Schwabdev") (client.py:41).
    import swing.integrations.schwab.logging_redaction as red  # re-grep actual module
    assert "Schwabdev" in red._SCHWABDEV_LOGGER_NAMES  # the capital-S name still covered


def test_g2_update_tokens_signature_retained() -> None:
    sig = inspect.signature(schwabdev.Client.update_tokens)
    params = [p for p in sig.parameters if p != "self"]
    assert params == ["force_access_token", "force_refresh_token"]


def test_g3_sandbox_gate_unchanged() -> None:
    # Regression guard: under environment != 'production', domain rows short-circuit.
    from swing.integrations.schwab import marketdata_ladder as ml
    assert ml._is_ladder_active(_cfg(environment="sandbox")) is False
    assert ml._is_ladder_active(_cfg(environment="production")) is True


def test_g4_price_history_passes_eight_camelcase_kwargs() -> None:
    # The minute-default footgun: get_price_history must pass period kwargs explicitly.
    src = inspect.getsource(__import__("swing.integrations.schwab.marketdata", fromlist=["get_price_history"]).get_price_history)
    for kw in ("periodType", "period", "frequencyType", "frequency"):
        assert kw in src, f"get_price_history dropped explicit {kw} (daily-bar footgun)"


def test_g5_linked_accounts_path_closes_audit_row_before_raise(monkeypatch) -> None:
    # The renamed path still closes its schwab_api_calls row via record_call_finish before re-raise.
    ...  # exercise the trader linked_accounts wrapper with a raising client; assert finish-before-raise


def test_g6_source_artifact_shape_unchanged() -> None:
    from swing.integrations.schwab import audit_service
    assert audit_service.source_artifact_path(call_id=7) == "schwab_api:call/7"  # re-grep helper name
```

(Re-grep the exact module/helper names at executing-plans: the redaction logger-name set, `_is_ladder_active`, the source-artifact helper. The `_cfg(...)` builder is a small inline fixture.)

- [ ] **Step 2: Run to verify status**

Run: `python -m pytest tests/integrations/schwab/test_gotcha_revalidation_v3.py -v`
Expected: G2/G4/G6 likely PASS immediately (surface unchanged); G1/G3/G5 may need a one-line assertion fix to match the real symbol names. Fix the assertions to the live symbols (these are re-validation guards, not behavior changes).

- [ ] **Step 3: (n/a -- test-only task; no production change)**

- [ ] **Step 4: Confirm green**

Run: `python -m pytest tests/integrations/schwab/test_gotcha_revalidation_v3.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add tests/integrations/schwab/test_gotcha_revalidation_v3.py
git commit -m "test(schwab): re-validate the six Schwab gotchas against schwabdev 3.0.5

Logger name, update_tokens signature, sandbox gate, price_history kwargs, audit-row
close on the renamed path, and the source-artifact shape all survive the upgrade."
```

**Slice 1 done-when:** `python -m pytest -m "not slow" -q` is green EXCEPT the token-storage tests (Slice 2) and the L2 grep test (which will FAIL on prose churn -- expected; re-anchored in Slice 4). Note the L2 test failure is EXPECTED from Task 1.3's prose churn; do not chase it before Slice 4.

---

## §E Slice 2 -- Token-storage rewrite (the risk-concentrated core)

**Risk:** HIGH (live brokerage OAuth state at rest). **Codex convergence:** the heaviest review focus. **Goal:** the v3-SQLite writer + reader + the comprehensive preflight + the non-interactive guard + the logout rewrite, all with `fernet_key=None` plumbing threaded for Slice 4.

> **T1b is the FIRST Slice-2 task (§C.1) -- it makes the Slice-1 floored pin merge-safe.** Tasks 2.1 + 2.2 supply its prerequisites (`_raise_on_auth`, `_V3_SCHWABDEV_DDL`, the writer), so the ordering is 2.1 -> 2.2 -> 2.3(T1b) -> reader -> preflight -> logout.

### Task 2.1: The non-interactive construction guard (`_raise_on_auth`) on the 2 non-setup sites

**Files:**
- Modify: `swing/integrations/schwab/auth.py` (NEW `_raise_on_auth`; add guard kwargs at 762, 1864)
- Test: extend `tests/integrations/schwab/test_construct_client_kwargs.py`

- [ ] **Step 1: Write the failing test**

```python
def test_nonsetup_sites_pass_raise_on_auth_and_no_browser() -> None:
    captured = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.tokens = type("T", (), {"access_token": "x"})()

    # ... construct via construct_authenticated_client with Client patched ...
    # Pre-fix: captured lacks call_on_auth / open_browser_for_auth -> FAIL.
    # Post-fix: both present; open_browser_for_auth is False; call_on_auth is callable.
    assert captured.get("open_browser_for_auth") is False
    assert callable(captured.get("call_on_auth"))


def test_raise_on_auth_raises_schwab_auth_error() -> None:
    from swing.integrations.schwab.auth import _raise_on_auth, SchwabAuthError
    import pytest
    with pytest.raises(SchwabAuthError):
        _raise_on_auth("https://example/auth-url")  # never prompts; always raises
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integrations/schwab/test_construct_client_kwargs.py -v`
Expected: FAIL (kwargs absent; `_raise_on_auth` undefined).

- [ ] **Step 3: Implement**

```python
def _raise_on_auth(auth_url: str) -> None:
    """Injected as call_on_auth on NON-setup construction paths. v3 would otherwise
    prompt interactively (input()/browser) at construction; raise a clean catchable
    error instead. Defense-in-depth -- the §C.2 preflight is the primary defense."""
    raise SchwabAuthError(
        401,
        "<tokens expired/invalid; run `swing schwab logout` then `swing schwab setup`>",
    )
```
At sites 762 + 1864 add `call_on_auth=_raise_on_auth, open_browser_for_auth=False,`. (Sites 901 + 1684 are SETUP paths -- adding the kwargs is harmless/uniform but the preflight is NOT wired there.)

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/integrations/schwab/test_construct_client_kwargs.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/auth.py tests/integrations/schwab/test_construct_client_kwargs.py
git commit -m "feat(schwab): add the non-interactive construction guard on the fetch and force-refresh sites

A call_on_auth that raises plus open_browser_for_auth False converts v3's interactive
construction prompt into a clean catchable error on the headless paths."
```

### Task 2.2: The W-A v3-SQLite writer + load-back regression (T1)

**Files:**
- Modify: `swing/integrations/schwab/auth.py:1335` (`_write_schwabdev_tokens_file` -> `_write_schwabdev_tokens_db`; NEW `_V3_SCHWABDEV_DDL`)
- Test: `tests/integrations/schwab/test_v3_tokens_writer.py` (Create)

- [ ] **Step 1: Write the failing test (T1 load-back)**

```python
"""T1: our v3-SQLite writer produces a DB a REAL schwabdev.Client constructs against."""
from datetime import datetime, timezone
from pathlib import Path

import schwabdev

from swing.integrations.schwab import auth


def test_writer_produces_loadable_v3_db(tmp_path: Path) -> None:
    tokens_path = tmp_path / "schwab-tokens.production.db"
    token_dictionary = {
        "access_token": "AT-abc", "refresh_token": "RT-def", "id_token": "ID-ghi",
        "expires_in": 1800, "token_type": "Bearer", "scope": "api",
    }
    issued = datetime.now(timezone.utc)
    # Pre-fix path: _write_schwabdev_tokens_file writes JSON -> schwabdev.Client() opening
    #   it as SQLite raises DatabaseError -> FAIL.
    # Post-fix path: writer emits the 8-col schwabdev row -> Client loads tokens.access_token.
    auth._write_schwabdev_tokens_db(
        tokens_path=tokens_path, token_dictionary=token_dictionary,
        issued_at=issued, fernet_key=None,
    )
    client = schwabdev.Client(
        app_key="k" * 32, app_secret="s" * 16, callback_url="https://127.0.0.1",
        tokens_db=str(tokens_path), call_on_auth=auth._raise_on_auth,
        open_browser_for_auth=False, timeout=5,
    )
    try:
        assert client.tokens.access_token == "AT-abc"
    finally:
        del client
        import gc
        gc.collect()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integrations/schwab/test_v3_tokens_writer.py::test_writer_produces_loadable_v3_db -v`
Expected: FAIL (writer still emits JSON; `_write_schwabdev_tokens_db` undefined).

- [ ] **Step 3: Implement the W-A writer** (per spec §5.1)

```python
import contextlib
import os
import sqlite3
import tempfile

# Verbatim copy of installed schwabdev 3.0.5 tokens.py:80-91 (pin source in this comment).
_V3_SCHWABDEV_DDL = (
    "CREATE TABLE IF NOT EXISTS schwabdev ("
    "access_token_issued TEXT NOT NULL, refresh_token_issued TEXT NOT NULL, "
    "access_token TEXT NOT NULL, refresh_token TEXT NOT NULL, id_token TEXT NOT NULL, "
    "expires_in INTEGER, token_type TEXT, scope TEXT)"
)


def _write_schwabdev_tokens_db(*, tokens_path, token_dictionary, issued_at, fernet_key=None):
    cipher = _fernet_cipher(fernet_key) if fernet_key else None

    def _enc(v: str) -> str:  # mirror installed tokens.py:120-123
        return ("enc:" + cipher.encrypt(v.encode()).decode()) if cipher else v

    fd, tmp = tempfile.mkstemp(dir=str(tokens_path.parent), prefix=tokens_path.name + ".", suffix=".tmp")
    os.close(fd)
    try:
        conn = sqlite3.connect(tmp)
        conn.execute(_V3_SCHWABDEV_DDL)
        conn.execute("DELETE FROM schwabdev")
        conn.execute(
            "INSERT INTO schwabdev (access_token_issued, refresh_token_issued, access_token, "
            "refresh_token, id_token, expires_in, token_type, scope) VALUES (?,?,?,?,?,?,?,?)",
            (issued_at.isoformat(), issued_at.isoformat(),
             _enc(token_dictionary["access_token"]), _enc(token_dictionary["refresh_token"]),
             token_dictionary.get("id_token", ""), token_dictionary.get("expires_in", 1800),
             token_dictionary.get("token_type", "Bearer"), token_dictionary.get("scope", "api")),
        )
        conn.commit()
        conn.close()
        os.replace(tmp, str(tokens_path))  # intra-volume; Windows-safe (CLAUDE.md gotcha)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise
```

(**The two PURE cipher helpers `_generate_fernet_key()` + `_fernet_cipher(key)` land HERE in Slice 2** -- they have no config dependency and the Slice-2 preflight (Task 2.6) + its T9b test need them real. In Slice 2 every WRITER caller still passes `fernet_key=None`, so enc-wrap is off in practice until Slice 4 supplies the cfg key source; the helpers merely exist. Add a one-line Slice-2 test `test_generate_and_cipher_roundtrip` next to T1. Re-grep all callers of the old `_write_schwabdev_tokens_file` and update them to `_write_schwabdev_tokens_db(..., fernet_key=None)`.)

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/integrations/schwab/test_v3_tokens_writer.py::test_writer_produces_loadable_v3_db -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/auth.py tests/integrations/schwab/test_v3_tokens_writer.py
git commit -m "feat(schwab): rewrite the tokens writer to emit the v3 schwabdev SQLite row

W-A owns a pinned eight-column DDL with atomic os.replace; a load-back regression
constructs a real client against the written DB to bound the DDL-copy drift risk."
```

### Task 2.3: T1b -- the DDL-drift guard (the OQ-3 safety condition)

**Files:**
- Test: `tests/integrations/schwab/test_v3_tokens_writer.py` (extend)

- [ ] **Step 1: Write the failing test (T1b)**

```python
def test_v3_schwabdev_ddl_matches_live_install(tmp_path) -> None:
    """T1b: introspect the LIVE schwabdev table vs our pinned _V3_SCHWABDEV_DDL.
    NON-INTERACTIVE + deterministic lock release (R3-M1)."""
    import gc
    import sqlite3

    import schwabdev

    from swing.integrations.schwab import auth, SchwabAuthError

    db = tmp_path / "schwab-tokens.production.db"
    # Construct a real Client against an EMPTY tokens_db WITH the guard; v3 CREATEs +
    # commits the schwabdev table BEFORE the auth flow's BEGIN EXCLUSIVE (tokens.py:80,93,398),
    # then enters the interactive refresh path -> our _raise_on_auth fires.
    try:
        client = schwabdev.Client(
            app_key="k" * 32, app_secret="s" * 16, callback_url="https://127.0.0.1",
            tokens_db=str(db), call_on_auth=auth._raise_on_auth,
            open_browser_for_auth=False, timeout=5,
        )
        client = None  # pragma: no cover - guard should have raised
    except SchwabAuthError:
        pass
    # DETERMINISTIC lock release: schwabdev holds an open BEGIN EXCLUSIVE (no try/finally
    # around call_for_auth). Drop locals + gc so the next connection is not "database is locked".
    locals().pop("client", None)
    gc.collect()

    conn = sqlite3.connect(str(db))
    cols = [(r[1], r[2]) for r in conn.execute("PRAGMA table_info(schwabdev)").fetchall()]
    conn.close()
    expected = [
        ("access_token_issued", "TEXT"), ("refresh_token_issued", "TEXT"),
        ("access_token", "TEXT"), ("refresh_token", "TEXT"), ("id_token", "TEXT"),
        ("expires_in", "INTEGER"), ("token_type", "TEXT"), ("scope", "TEXT"),
    ]
    # Pre-fix risk this guards: a future 3.x silently changing the private schema.
    # Post-fix: the live table matches our pinned 8-col copy.
    assert cols == expected, (
        f"schwabdev private table DDL drifted: live={cols} pinned={expected}. "
        "The W-A writer copies this DDL; the OQ-3 floored pin is unsafe until reconciled."
    )
```

- [ ] **Step 2: Run to verify it passes on 3.0.5**

Run: `python -m pytest tests/integrations/schwab/test_v3_tokens_writer.py::test_v3_schwabdev_ddl_matches_live_install -v`
Expected: PASS on 3.0.5 (the guard is the tripwire for FUTURE 3.x drift). If the PRAGMA returns empty, the table was not committed before the guard fired -- investigate the construction order before proceeding.

- [ ] **Step 3: (n/a -- test-only; the guard asserts existing behavior)**

- [ ] **Step 4: Confirm green + that it makes the floored pin safe**

Run the writer test module: Expected PASS. Document in the commit that the Slice-1 floored pin is now merge-safe.

- [ ] **Step 5: Commit**

```bash
git add tests/integrations/schwab/test_v3_tokens_writer.py
git commit -m "test(schwab): add the DDL-drift guard that makes the v3 floored pin safe

The guard introspects the live schwabdev table against our pinned copy with deterministic
lock release, failing loudly the moment a future minor changes the private schema."
```

### Task 2.4: The presence-only v3-SQLite reader (T2, T4, T5)

**Files:**
- Modify: `swing/cli_schwab.py:469` (`_read_tokens_metadata`)
- Test: `tests/cli/test_v3_tokens_reader.py` (Create)

- [ ] **Step 1: Write the failing tests**

```python
"""T2/T4/T5: the v3 reader returns presence-only fields, tolerates a locked DB, and
detects the old format."""
import sqlite3
from pathlib import Path

from swing.cli_schwab import _read_tokens_metadata
from swing.integrations.schwab import auth


def _write_v3(tmp_path) -> Path:
    p = tmp_path / "schwab-tokens.production.db"
    from datetime import datetime, timezone
    auth._write_schwabdev_tokens_db(
        tokens_path=p,
        token_dictionary={"access_token": "AT", "refresh_token": "RT", "id_token": "ID",
                          "expires_in": 1800, "token_type": "Bearer", "scope": "api"},
        issued_at=datetime.now(timezone.utc), fernet_key=None)
    return p


def test_t2_reader_returns_no_secret_bytes(tmp_path) -> None:
    meta, err = _read_tokens_metadata(_write_v3(tmp_path))
    assert err is None
    # Post-fix: presence-only fields; NO access_token / refresh_token VALUE present.
    assert set(meta) == {"access_token_issued", "refresh_token_issued", "expires_in",
                         "refresh_token_present"}
    assert "AT" not in str(meta) and "RT" not in str(meta)
    assert meta["refresh_token_present"] is True


def test_t5_old_format_json_detected(tmp_path) -> None:
    p = tmp_path / "schwab-tokens.production.db"
    p.write_text('{"token_dictionary": {"refresh_token": "RT"}}')  # 2.x JSON
    meta, err = _read_tokens_metadata(p)
    # Pre-fix: json.load succeeded on JSON; on a v3 SQLite it would crash. Post-fix:
    # SQLite open of JSON -> DatabaseError -> actionable old-format message, meta None.
    assert meta is None and err is not None and "logout" in err


def test_t4_locked_db_tolerated(tmp_path) -> None:
    p = _write_v3(tmp_path)
    holder = sqlite3.connect(str(p))
    holder.execute("BEGIN EXCLUSIVE")
    try:
        meta, err = _read_tokens_metadata(p)
        # mode=ro read under an exclusive lock -> OperationalError -> "busy" message, no crash.
        assert meta is None and err is not None and "busy" in err.lower()
    finally:
        holder.rollback()
        holder.close()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/cli/test_v3_tokens_reader.py -v`
Expected: FAIL (reader still `json.load`s).

- [ ] **Step 3: Implement the v3 reader** (per spec §5.2)

```python
def _read_tokens_metadata(tokens_path: Path) -> tuple[dict | None, str | None]:
    """Read v3 SQLite tokens DB. Returns (meta, error) where meta carries ONLY
    non-secret presence fields (issued timestamps + expires_in + refresh_token_present).
    SECURITY: never SELECTs/returns the access_token/refresh_token VALUE."""
    if not tokens_path.exists():
        return None, None
    conn = None
    try:
        ro_uri = Path(tokens_path).as_uri() + "?mode=ro"  # as_uri escapes spaces/#/?
        conn = sqlite3.connect(ro_uri, uri=True)
        row = conn.execute(
            "SELECT access_token_issued, refresh_token_issued, expires_in, "
            "(refresh_token IS NOT NULL AND refresh_token != '') FROM schwabdev LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc):
            return None, "<tokens DB pre-v3 / foreign format; run `swing schwab logout` then setup>"
        return None, "<tokens DB busy (refresh in progress); retry>"
    except sqlite3.DatabaseError:
        return None, "<tokens DB pre-v3 (2.x JSON) format; run `swing schwab logout` then setup>"
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
    if row is None:
        return None, "<no token row; run `swing schwab setup`>"
    at_issued, rt_issued, expires_in, has_refresh = row
    return ({"access_token_issued": at_issued, "refresh_token_issued": rt_issued,
             "expires_in": expires_in, "refresh_token_present": bool(has_refresh)}, None)
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/cli/test_v3_tokens_reader.py -v`
Expected: PASS (T2, T4, T5).

- [ ] **Step 5: Commit**

```bash
git add swing/cli_schwab.py tests/cli/test_v3_tokens_reader.py
git commit -m "feat(schwab): read the v3 SQLite tokens DB presence-only in the status reader

The reader opens read-only, tolerates a locked DB during a refresh, detects the pre-v3
format with an actionable message, and never holds the secret token bytes."
```

### Task 2.5: Re-map the DEGRADED-health predicate to v3 columns (T3, T6)

**Files:**
- Modify: `swing/cli_schwab.py` (the multi-signal predicate `~:605-741`)
- Test: `tests/cli/test_v3_tokens_reader.py` (extend)

- [ ] **Step 1: Write the failing tests**

```python
def test_t3_degraded_signals_map_to_v3_columns(tmp_path) -> None:
    """Each DEGRADED signal maps off the v3 columns: no row / empty refresh_token /
    missing-or-expired refresh_token_issued."""
    from datetime import datetime, timedelta, timezone
    from swing.cli_schwab import _compute_integration_state  # re-grep the real name
    import sqlite3

    # (a) no row -> DEGRADED (was 'token_dictionary missing').
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(
        tokens_path=p, token_dictionary={"access_token": "AT", "refresh_token": "RT",
        "id_token": "ID", "expires_in": 1800, "token_type": "Bearer", "scope": "api"},
        issued_at=datetime.now(timezone.utc), fernet_key=None)
    c = sqlite3.connect(str(p)); c.execute("DELETE FROM schwabdev"); c.commit(); c.close()
    state, reason = _compute_integration_state(..., tokens_path=p, now=datetime.now(timezone.utc))
    assert state == "DEGRADED"

    # (b) expired refresh_token_issued (issued + 7d <= now) -> DEGRADED.
    old = datetime.now(timezone.utc) - timedelta(days=8)
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary={...}, issued_at=old, fernet_key=None)
    state, reason = _compute_integration_state(..., tokens_path=p, now=datetime.now(timezone.utc))
    assert state == "DEGRADED" and "expired" in reason


def test_t6_seven_day_ttl_pinned() -> None:
    from swing.cli_schwab import _REFRESH_TOKEN_TTL_SECONDS
    assert _REFRESH_TOKEN_TTL_SECONDS == 7 * 24 * 3600
    # Pin against a future v3 TTL change: installed schwabdev tokens.py:64 is 7*24*60*60.
    import inspect, schwabdev.tokens as t  # re-grep the attribute name
    assert "7 * 24 * 60 * 60" in inspect.getsource(t) or 7 * 24 * 60 * 60 == t._REFRESH_TIMEOUT  # re-grep
```

(Re-grep the predicate's real function name at `cli_schwab.py:~605` and the v3 TTL attribute. The `...` cfg/conn args are minimal inline stubs.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/cli/test_v3_tokens_reader.py -k "t3 or t6" -v`
Expected: FAIL (predicate still consults JSON `token_dictionary` keys).

- [ ] **Step 3: Implement the re-map** (spec §5.2 key-mapping)

Re-map the predicate signals 3-7: replace the `payload.get("token_dictionary")` block with the v3 reader's presence fields:
- Signal 3 (token_dictionary missing/non-dict) -> the v3 reader returned `(None, err)` (no row) -> DEGRADED with the actionable message.
- Signal 4 (refresh_token bytes missing) -> `meta["refresh_token_present"] is False` -> DEGRADED.
- Signals 5-7 (refresh_token_issued missing/unparseable/expired) -> read `meta["refresh_token_issued"]`; same `_parse_iso_datetime` + `_REFRESH_TOKEN_TTL_SECONDS` math, UNCHANGED.
Keep signals 1 (missing -> PROVISIONAL), 2 (parse_err -> DEGRADED), 8 (mtime), 9 (recent-call status) intact. `expires_in` now comes from the top-level column via the reader.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/cli/test_v3_tokens_reader.py -v`
Expected: PASS (T2-T6).

- [ ] **Step 5: Commit**

```bash
git add swing/cli_schwab.py tests/cli/test_v3_tokens_reader.py
git commit -m "feat(schwab): re-map the degraded-health signals to the v3 token columns

Signals that previously read the nested JSON token_dictionary now read the v3 reader's
presence fields, keeping the refresh-token expiry math and the seven-day TTL pin intact."
```

### Task 2.6: The comprehensive non-setup preflight (T8, T9a-c)

**Files:**
- Modify: `swing/integrations/schwab/auth.py` (NEW `_assert_v3_tokens_db_loadable_or_raise`; wire before sites 762 + 1864)
- Test: `tests/integrations/schwab/test_v3_preflight.py` (Create)

- [ ] **Step 1: Write the failing tests**

```python
"""T8/T9: the comprehensive preflight runs BEFORE non-setup construction and converts
old-format / stale-refresh / key-loss into a clean SchwabAuthError -- never a raw
DatabaseError, never an interactive prompt, never a leaked lock."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from swing.integrations.schwab import auth
from swing.integrations.schwab.auth import SchwabAuthError


def test_t8_old_format_raises_before_construct(tmp_path, monkeypatch) -> None:
    p = tmp_path / "schwab-tokens.production.db"
    p.write_text('{"token_dictionary": {}}')  # 2.x JSON
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    constructed = {"n": 0}
    monkeypatch.setattr(auth.schwabdev, "Client", lambda **k: constructed.__setitem__("n", 1))
    # Pre-fix: schwabdev.Client opens JSON-as-SQLite -> raw DatabaseError. Post-fix:
    # preflight raises SchwabAuthError BEFORE Client is constructed.
    with pytest.raises(SchwabAuthError):
        auth.construct_authenticated_client(_cfg(), "production", "id", "secret")
    assert constructed["n"] == 0  # never reached construction


def test_t9a_stale_refresh_raises_no_input(tmp_path, monkeypatch) -> None:
    p = tmp_path / "schwab-tokens.production.db"
    stale = datetime.now(timezone.utc) - timedelta(days=7)  # rt_delta < 3630s of the 7d window
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary={"access_token": "AT",
        "refresh_token": "RT", "id_token": "ID", "expires_in": 1800, "token_type": "Bearer",
        "scope": "api"}, issued_at=stale, fernet_key=None)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("interactive prompt fired"))
    with pytest.raises(SchwabAuthError):
        auth._assert_v3_tokens_db_loadable_or_raise(p, fernet_key=None)


def test_t9b_keyloss_on_construction_path(tmp_path) -> None:
    # enc:-prefixed columns but NO key configured -> clean key-loss SchwabAuthError.
    p = tmp_path / "schwab-tokens.production.db"
    # Write WITH a key (Slice 4 helper), then preflight with fernet_key=None.
    key = auth._generate_fernet_key()
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary={"access_token": "AT",
        "refresh_token": "RT", "id_token": "ID", "expires_in": 1800, "token_type": "Bearer",
        "scope": "api"}, issued_at=datetime.now(timezone.utc), fernet_key=key)
    with pytest.raises(SchwabAuthError):
        auth._assert_v3_tokens_db_loadable_or_raise(p, fernet_key=None)
```

(T9b uses `_generate_fernet_key` + `_fernet_cipher`, which LAND IN SLICE 2 Task 2.2 -- so T9b is REAL here, NOT xfailed. Slice 4 only wires the cfg key SOURCE (`_resolve_fernet_key` + the `encryption_key` config field). `_cfg()` is an inline cfg stub.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integrations/schwab/test_v3_preflight.py -v`
Expected: FAIL (`_assert_v3_tokens_db_loadable_or_raise` undefined; construction reached).

- [ ] **Step 3: Implement the preflight** (spec §5.4 (1)-(4)) + wire it

```python
def _assert_v3_tokens_db_loadable_or_raise(tokens_path: Path, fernet_key=None) -> None:
    """PRIMARY defense (§C.2). Read the v3 DB directly (NOT via Client) and assert:
    (1) schwabdev table present; (2) one row; (3) refresh FRESH (rt_delta >= 3630s);
    (4) decryptability driven by the column enc: prefix, NOT the config flag.
    Any failure -> clean SchwabAuthError. Never an unwrapped DatabaseError / input()."""
    if not tokens_path.exists():
        raise SchwabAuthError(401, "<no tokens DB; run `swing schwab setup`>")
    try:
        ro = Path(tokens_path).as_uri() + "?mode=ro"
        conn = sqlite3.connect(ro, uri=True)
    except sqlite3.DatabaseError:
        raise SchwabAuthError(401, "<tokens DB pre-v3/foreign; run `swing schwab logout` then setup>")
    try:
        try:
            row = conn.execute("SELECT refresh_token_issued, access_token, refresh_token "
                               "FROM schwabdev LIMIT 1").fetchone()
        except sqlite3.DatabaseError:
            raise SchwabAuthError(401, "<tokens DB pre-v3/foreign; run logout then setup>")
        if row is None:
            raise SchwabAuthError(401, "<no token row; run `swing schwab setup`>")
        rt_issued, at_val, rt_val = row
        # (3) freshness: now - rt_issued < 7d - 3630s  (else construction forces a refresh).
        issued = _parse_iso_datetime(rt_issued)
        if issued is None or (datetime.now(UTC) - issued).total_seconds() >= (7 * 24 * 3600 - 3630):
            raise SchwabAuthError(401, "<refresh token expired/expiring; run logout then setup>")
        # (4) decryptability by CONTENT, not config flag.
        for col in (at_val, rt_val):
            if isinstance(col, str) and col.startswith("enc:"):
                if not fernet_key:
                    raise SchwabAuthError(401, "<encrypted tokens but no key (key loss?); run logout then setup>")
                try:
                    _fernet_cipher(fernet_key).decrypt(col[len("enc:"):].encode())
                except Exception:
                    raise SchwabAuthError(401, "<encrypted tokens, key invalid (key loss?); run logout then setup>")
    finally:
        with contextlib.suppress(Exception):
            conn.close()
```

Wire it immediately before the `schwabdev.Client(...)` call at sites 762 + 1864 (the fetch + force_refresh paths). When the residual-race guard fires (the `SchwabAuthError` from `_raise_on_auth` during construction), the caller drops the client ref + `gc.collect()`s before any subsequent read (T9c).

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/integrations/schwab/test_v3_preflight.py -v`
Expected: PASS (T8, T9a, T9b; add T9c asserting a post-guard tokens read succeeds after `gc.collect()`).

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/auth.py tests/integrations/schwab/test_v3_preflight.py
git commit -m "feat(schwab): add the comprehensive non-setup preflight as the primary auth defense

The preflight reads the v3 DB directly and rejects old-format, stale-refresh, and
key-loss states with a clean error before construction, so the interactive path is unreachable."
```

### Task 2.7: The `revoke_and_delete` logout rewrite (T7a, T7c, T7d) + `/schwab/status` preservation

**Files:**
- Modify: `swing/integrations/schwab/auth.py:2025` (`revoke_and_delete`; NEW `_read_v3_refresh_token`)
- Test: `tests/integrations/schwab/test_v3_logout_revoke.py` (Create); `tests/integration/test_schwab_status_page_v3_reader.py` (Create)

- [ ] **Step 1: Write the failing tests**

```python
"""T7: logout reads the refresh_token from v3 SQLite, reorders to rename-first/
best-effort-revoke, falls back to delete-without-revoke, and surfaces a clean error
on a hard rename failure -- never a silent partial state."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from swing.integrations.schwab import auth


def _fresh_v3(tmp_path) -> Path:
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary={"access_token": "AT",
        "refresh_token": "RT-revoke-me", "id_token": "ID", "expires_in": 1800,
        "token_type": "Bearer", "scope": "api"}, issued_at=datetime.now(timezone.utc),
        fernet_key=None)
    return p


def test_t7a_fresh_db_revoke_and_rename(tmp_path, monkeypatch, conn) -> None:
    p = _fresh_v3(tmp_path)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    posted = {}
    with patch.object(auth, "requests") as rq:
        rq.post.return_value = type("R", (), {"status_code": 200})()
        auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
        posted["body"] = rq.post.call_args.kwargs["data"]
    # Pre-fix: json.load on the SQLite DB raised -> SchwabApiError, DB never renamed.
    # Post-fix: refresh_token read from SQLite -> revoke body carries RT-revoke-me; DB renamed.
    assert posted["body"]["token"] == "RT-revoke-me"
    assert not p.exists()  # renamed aside


def test_t7c_old_format_fallback_renames_with_warning(tmp_path, monkeypatch, conn, caplog) -> None:
    p = tmp_path / "schwab-tokens.production.db"
    p.write_text('{"legacy": true}')  # old/unreadable as SQLite
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
    # Delete-without-revoke fallback: DB STILL renamed aside + a WARNING (not server-revoked).
    assert not p.exists()
    assert any("not server-side revoked" in r.message or "not revoked" in r.message.lower()
               for r in caplog.records)


def test_t7d_hard_rename_failure_clean_error(tmp_path, monkeypatch, conn) -> None:
    p = _fresh_v3(tmp_path)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    # Simulate a locked/file-in-use rename failure through the bounded-retry path.
    with patch.object(auth.os, "replace", side_effect=PermissionError("file in use")):
        with pytest.raises(Exception) as ei:  # a CLEAN actionable error, not a silent partial state
            auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
    assert "retry" in str(ei.value).lower() or "close other" in str(ei.value).lower()
```

```python
"""C.5/§1.2: /schwab/status renders token-health off the v3 reader (production-path)."""
def test_status_page_renders_off_v3_reader(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from swing.web.app import create_app  # re-grep factory name
    # Seed a real v3 DB at the resolved tokens path; assert the page renders 200 and shows
    # refresh-token days-remaining + last_success/last_failure (fed by schwab_api_calls, unchanged).
    ...
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integrations/schwab/test_v3_logout_revoke.py tests/integration/test_schwab_status_page_v3_reader.py -v`
Expected: FAIL (logout still `json.load`s + raises before rename; status page may already pass once Task 2.4 lands -- if so, keep it as a regression guard).

- [ ] **Step 3: Implement the rewrite** (spec §5.5)

Add `_read_v3_refresh_token(tokens_path, fernet_key=None) -> str | None` (SELECT `refresh_token`; if `enc:`-prefixed and `fernet_key`, decrypt; else return raw or None). Rewrite `revoke_and_delete` step 4 to call it (not `json.load`). Re-order: rename-aside FIRST via `_rename_stale_tokens_db` (bounded retry; on hard failure raise a clean actionable error), then best-effort revoke SECOND; if the refresh_token could not be read/decrypted, take the delete-without-revoke fallback (DB still renamed; WARNING "token not server-side revoked; it self-expires within the 7-day TTL"). Keep the in-flight audit row + the `register_schwab_secrets`/`ensure_*` redaction call before the POST.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/integrations/schwab/test_v3_logout_revoke.py tests/integration/test_schwab_status_page_v3_reader.py -v`
Expected: PASS (T7a, T7c, T7d + status-page regression).

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/auth.py tests/integrations/schwab/test_v3_logout_revoke.py tests/integration/test_schwab_status_page_v3_reader.py
git commit -m "feat(schwab): rewrite logout to read the refresh token from the v3 SQLite DB

Logout now renames the DB aside first and revokes best-effort, falls back to delete
without revoke on an unreadable DB, and surfaces a clean error on a hard rename failure."
```

**Slice 2 done-when:** `python -m pytest -m "not slow" -q` is green EXCEPT the L2 grep test (still expected-fail until Slice 4). The token-storage core, the preflight, the guard, and logout all exercise real on-disk v3 DBs (gotcha #15 production-path).

---

## §F Slice 3 -- P14.N7 + F-1 badge reconciliation (ONE atomic task; OQ-5 = DELETE)

**Risk:** MEDIUM (broad mechanical deletion; the shared-`base.html.j2` Jinja hazard). **Goal:** remove the dead daemon-checker wrapper + the badge + the full blast radius in ONE atomic commit; `/schwab/status` PAGE untouched (already re-sourced in Slice 2).

### Task 3.1: Delete the checker wrapper + the F-1 badge + the full blast radius

**Files:** see §B.2 + §C.4 for the complete enumeration.

- [ ] **Step 1: Write the failing test** (`tests/web/test_checker_badge_deleted.py`)

```python
"""Slice 3: zero references to the deleted P14.N7/F-1 surfaces remain; every base-layout
route still renders (no Jinja UndefinedError from a removed VM field)."""
import pathlib

import pytest

SWING = pathlib.Path(__file__).resolve().parents[2] / "swing"


@pytest.mark.parametrize("needle", [
    "checker_resilience", "schwab_checker_badge", "build_schwab_checker_badge",
    "evaluate_liveness_state", "install_resilient_checker", "CheckerLiveness",
])
def test_no_deleted_symbol_references_remain(needle: str) -> None:
    hits = [str(p) for p in SWING.rglob("*.py") if needle in p.read_text(encoding="utf-8")]
    tpl = [str(p) for p in SWING.rglob("*.j2") if needle in p.read_text(encoding="utf-8")]
    # Pre-fix: many hits across view_models/app.py/cli_schwab/base.html.j2. Post-fix: zero.
    assert not (hits + tpl), f"{needle} still referenced in: {hits + tpl}"


@pytest.mark.parametrize("path", [
    "/", "/pipeline", "/journal", "/watchlist", "/config", "/metrics", "/schwab/status",
])  # re-grep the full base-layout route set
def test_base_layout_routes_render_without_badge(client, path: str) -> None:
    resp = client.get(path)
    assert resp.status_code in (200, 302)  # no 500 UndefinedError from a removed field
```

(Use `with TestClient(app) as client:` -- lifespan-entered -- because base-layout routes touch `app.state`.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/web/test_checker_badge_deleted.py -v`
Expected: FAIL (symbols still referenced).

- [ ] **Step 3: Delete atomically** (one commit; enumerate from §C.4)

1. Delete `swing/integrations/schwab/checker_resilience.py`.
2. Delete `swing/web/view_models/schwab_checker_badge.py`.
3. Remove the `schwab_checker_badge` field declaration from ALL modules in §C.4 (dashboard, error, config, pipeline, watchlist, trades x4, metrics/shared, reconcile x2, journal x2, schwab x3).
4. Remove all 8 `build_schwab_checker_badge(...)` call sites + their imports (dashboard, config, pipeline, watchlist, metrics/index, journal, schwab.py, routes/schwab).
5. Delete the `base.html.j2:81-84` topbar block.
6. Delete the `app.py:259-324` checker install/seed/readback (re-grep the exact span; keep the A-3 ladder install -- delete ONLY the P14.N7 portion + the `app.state.schwab_client` assignment comment that references P14.N7 if the client hold is no longer needed; KEEP the client hold if A-3 still uses it -- re-verify).
7. Delete the `cli_schwab.py:834-842` liveness import + render block.
8. Delete the 6 checker test files (§B.4).

- [ ] **Step 4: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: green except the L2 grep test (Slice 4). `test_checker_badge_deleted.py` PASS; no `UndefinedError` on any base-layout route.

- [ ] **Step 5: Commit (ONE atomic commit)**

```bash
git add -A
git commit -m "refactor(schwab): delete the P14.N7 checker wrapper and the F-1 topbar badge

v3's synchronous per-request refresh removes the daemon failure mode, so the wrapper,
the badge, the field across every base-layout view model, the topbar block, and the six
checker tests are removed together; the schwab status page is unaffected."
```

**Slice 3 done-when:** zero deleted-symbol references in `swing/`; every base-layout route renders; the `/schwab/status` page still renders (off the Slice-2 v3 reader). Operator witnesses the UNSEEDED no-badge default at G7 (§H.2 leg 5).

---

## §G Slice 4 -- Fernet + L2 re-anchor + L3 verify + live-OAuth gate + CLAUDE.md

**Risk:** MEDIUM (Fernet secret-handling) + the operator-binding gates. **Goal:** turn Fernet on, perform the audited L2 re-anchor behind an operator-sign-off GATE, verify L3, gate on the operator LIVE-OAuth smoke, refresh CLAUDE.md.

### Task 4.1: Fernet cfg key SOURCE -- `_resolve_fernet_key` + the `encryption_key` config field + masking

**Files:**
- Modify: `swing/config.py` + `swing/config_user.py` (resolution); `swing/cli.py` (`config show` mask); `swing/integrations/schwab/auth.py` (`_resolve_fernet_key`)
- Test: `tests/integrations/schwab/test_fernet_tokens.py` (Create)

> The pure cipher helpers `_generate_fernet_key` + `_fernet_cipher` ALREADY EXIST (landed in Slice 2 Task 2.2, with their round-trip test). This task adds ONLY the cfg key source + the config field + masking.

- [ ] **Step 1: Write the failing tests**

```python
"""OQ-1 Fernet cfg source: key resolution + masking (the cipher helpers are Slice-2)."""
from swing.integrations.schwab import auth


def test_resolve_fernet_key_none_when_absent(monkeypatch) -> None:
    assert auth._resolve_fernet_key(_cfg(encryption_key=None)) is None


def test_resolve_fernet_key_value_when_present() -> None:
    k = auth._generate_fernet_key()
    assert auth._resolve_fernet_key(_cfg(encryption_key=k)) == k


def test_config_show_masks_encryption_key(capsys) -> None:
    # swing config show MUST mask encryption_key like client_secret.
    from swing import cli
    # ... invoke config show with a key set; assert the raw key bytes are NOT in stdout.
    ...
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integrations/schwab/test_fernet_tokens.py -v`
Expected: FAIL (helpers/config field undefined).

- [ ] **Step 3: Implement**

Add `encryption_key` to `SchwabIntegrationConfig` (out-of-tree user-config `[integrations.schwab]`; resolution cascade env > cfg > None). Add `auth._generate_fernet_key()` (`Fernet.generate_key().decode()`), `auth._fernet_cipher(key)` (`Fernet(key.encode() if str else key)`), `auth._resolve_fernet_key(cfg)` (returns the key or None). Mask `encryption_key` in `swing config show` (mirror `client_secret`). Verify `.gitignore` already covers the tokens DB (it does -- `.gitignore:132-135`); `user-config.toml` is already out-of-tree.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/integrations/schwab/test_fernet_tokens.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/config.py swing/config_user.py swing/cli.py swing/integrations/schwab/auth.py tests/integrations/schwab/test_fernet_tokens.py
git commit -m "feat(schwab): add Fernet key storage, masking, and resolution helpers

The encryption key lives in the out-of-tree user config alongside the client secret and
is masked by config show; the cipher helpers back the writer enc-wrap and the revoke decrypt."
```

### Task 4.2: Turn Fernet on -- writer enc-wrap + `encryption=` at all 4 construction sites + revoke decrypt (T7b)

**Files:**
- Modify: `swing/integrations/schwab/auth.py` (pass `fernet_key=_resolve_fernet_key(cfg)` into the writer + `_read_v3_refresh_token`; `encryption=_resolve_fernet_key(cfg)` at the 4 construction sites; `fernet_key` into the preflight)
- Test: `tests/integrations/schwab/test_fernet_tokens.py` (extend)

- [ ] **Step 1: Write the failing tests**

```python
def test_writer_enc_wraps_when_key_present(tmp_path) -> None:
    import sqlite3
    from datetime import datetime, timezone
    key = auth._generate_fernet_key()
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary={"access_token": "AT",
        "refresh_token": "RT", "id_token": "ID", "expires_in": 1800, "token_type": "Bearer",
        "scope": "api"}, issued_at=datetime.now(timezone.utc), fernet_key=key)
    row = sqlite3.connect(str(p)).execute("SELECT access_token, refresh_token FROM schwabdev").fetchone()
    # Pre-fix (key threaded but ignored): plaintext 'AT'/'RT'. Post-fix: enc:-prefixed.
    assert row[0].startswith("enc:") and row[1].startswith("enc:")
    # And a real Client(encryption=key) loads it:
    import schwabdev, gc
    c = schwabdev.Client(app_key="k"*32, app_secret="s"*16, callback_url="https://127.0.0.1",
        tokens_db=str(p), encryption=key, call_on_auth=auth._raise_on_auth,
        open_browser_for_auth=False, timeout=5)
    try:
        assert c.tokens.access_token == "AT"
    finally:
        del c; gc.collect()


def test_t7b_logout_decrypts_encrypted_refresh(tmp_path, monkeypatch, conn) -> None:
    key = auth._generate_fernet_key()
    p = tmp_path / "schwab-tokens.production.db"
    auth._write_schwabdev_tokens_db(tokens_path=p, token_dictionary={"access_token": "AT",
        "refresh_token": "RT-secret", "id_token": "ID", "expires_in": 1800,
        "token_type": "Bearer", "scope": "api"}, issued_at=__import__("datetime").datetime.now(
        __import__("datetime").timezone.utc), fernet_key=key)
    monkeypatch.setattr(auth, "_resolve_tokens_db_path", lambda env: p)
    monkeypatch.setattr(auth, "_resolve_fernet_key", lambda cfg: key)
    from unittest.mock import patch
    with patch.object(auth, "requests") as rq:
        rq.post.return_value = type("R", (), {"status_code": 200})()
        auth.revoke_and_delete(_cfg(), "production", "id", "secret", conn, force=True)
        # revoke body carries the DECRYPTED plaintext, not the enc: ciphertext.
        assert rq.post.call_args.kwargs["data"]["token"] == "RT-secret"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integrations/schwab/test_fernet_tokens.py -k "enc_wraps or t7b" -v`
Expected: FAIL (writer not passed a key by callers; revoke not decrypting).

- [ ] **Step 3: Implement**

Thread `_resolve_fernet_key(cfg)` into: the writer callers (the setup write path), `_read_v3_refresh_token` (revoke), and `_assert_v3_tokens_db_loadable_or_raise`. Add `encryption=_resolve_fernet_key(cfg)` to the 4 construction sites. The writer's `_enc` + the preflight's decrypt branch are already coded (Slice 2) -- this task only supplies the key. Un-xfail T9b if it was xfailed.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/integrations/schwab/test_fernet_tokens.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/auth.py tests/integrations/schwab/test_fernet_tokens.py
git commit -m "feat(schwab): enable Fernet token-at-rest encryption end to end

The writer enc-wraps when a key is configured, the four construction sites pass encryption,
and logout decrypts the refresh token before revoke; status stays presence-only with no key."
```

### Task 4.3: L3 verification -- no swing schema change

**Files:**
- Test: `tests/data/test_no_schema_change_v3.py` (Create)

- [ ] **Step 1: Write the test**

```python
"""L3: the v3 migration changes NO swing-DB schema."""
import pathlib

from swing.data.db import EXPECTED_SCHEMA_VERSION

MIG = pathlib.Path(__file__).resolve().parents[2] / "swing" / "data" / "migrations"


def test_expected_schema_version_unchanged() -> None:
    assert EXPECTED_SCHEMA_VERSION == 23


def test_no_new_migration_file_added() -> None:
    # Highest existing migration is 00xx for v23; assert no 00(N+1) appeared.
    versions = sorted(int(p.name[:4]) for p in MIG.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    assert versions[-1] <= 23, f"a new migration file was added: {versions[-1]} (L3 violation)"
```

- [ ] **Step 2: Run -- verify pass**

Run: `python -m pytest tests/data/test_no_schema_change_v3.py -v`
Expected: PASS (no schema change anywhere in the arc).

- [ ] **Step 3-4: (n/a -- guard test)**

- [ ] **Step 5: Commit**

```bash
git add tests/data/test_no_schema_change_v3.py
git commit -m "test(data): assert the v3 upgrade adds no swing schema migration

The schwabdev tokens DB is schwabdev-internal SQLite; the swing schema version stays at 23."
```

### Task 4.4: The L2 re-anchor -- endpoint diff + rationale + grep-still-functions + the operator-sign-off GATE

**Files:**
- Create: `docs/schwab-v3-endpoint-diff.md`
- Modify: `tests/integration/test_l2_lock_source_grep.py:26` (the baseline SHA + rationale block + the health test)

> **OPERATOR-SIGN-OFF GATE (OQ-4 -- BINDING):** this is the FIRST-EVER L2 baseline move. The plan DESIGNS the re-anchor as a discrete task PLUS an explicit operator-sign-off checkpoint. The `L2_LOCK_BASELINE_SHA` value is filled with the REAL post-migration HEAD SHA at executing-plans, and the commit is made ONLY after the operator signs off on the endpoint diff. Do NOT silently move the baseline. If the endpoint diff ever shows a genuinely-NEW endpoint, STOP + escalate (it does not -- §G table).

- [ ] **Step 1: Author the endpoint-diff artifact** (`docs/schwab-v3-endpoint-diff.md`)

Enumerate the complete pre/post Schwab + OAuth endpoint set (spec §7 table): linked accounts (`account_linked` -> `linked_accounts`, SAME `/trader/v1/accounts/accountNumbers`); account details/orders/transactions; quotes; price history; OAuth token/revoke/authorize (our manual flows, pre-existing). **Conclusion: ZERO new endpoints** -- one method rename (same path) + token storage change (no API call).

- [ ] **Step 2: Write the failing test changes**

```python
# Re-anchor rationale block (illustrative; fill <post-migration-SHA> at executing-plans):
# L2_LOCK_BASELINE_SHA re-anchored <post-migration-SHA> on 2026-06-?? (Phase 15, schwabdev
# v3 upgrade). FIRST-EVER baseline move. Reason: the 2.5.1->3.0.5 migration rewrites
# docstrings/comments/type-annotations embedding "schwabdev.Client(" (the tokens_file=
# signature, the account_linked reference) -> new PROSE (path, line_text) keys, not new call
# sites. The manual endpoint-set diff (docs/schwab-v3-endpoint-diff.md) proves ZERO new
# Schwab REST endpoints. Operator-signed at the executing-plans gate (OQ-4). Spirit preserved.
L2_LOCK_BASELINE_SHA = "<post-migration-SHA>"   # was "bf7e071"


def test_l2_grep_still_functions_after_reanchor() -> None:
    # Health test: the grep runs, returns a non-empty Counter, and the subset-check passes
    # at the new baseline (the lock is not silently disabled).
    from tests.integration.test_l2_lock_source_grep import _count_call_sites, _PATTERN  # re-grep names
    head = _count_call_sites("HEAD", _PATTERN)
    assert sum(head.values()) > 0
```

- [ ] **Step 3: Re-anchor** (at executing-plans, on the real HEAD)

Replace `bf7e071` with the post-migration HEAD SHA AFTER the operator signs off on `docs/schwab-v3-endpoint-diff.md`. Keep the rationale block.

- [ ] **Step 4: Run -- verify pass**

Run: `python -m pytest tests/integration/test_l2_lock_source_grep.py -v`
Expected: PASS (subset-check at the new baseline + the grep-still-functions health test).

- [ ] **Step 5: Commit** (after operator sign-off)

```bash
git add docs/schwab-v3-endpoint-diff.md tests/integration/test_l2_lock_source_grep.py
git commit -m "test(schwab): re-anchor the L2 lock baseline to the post-v3-migration HEAD

The first sanctioned baseline move; the endpoint diff proves zero new Schwab endpoints and
the operator signed off on the rename-and-storage churn at the executing-plans gate."
```

### Task 4.5: CLAUDE.md Schwab-block + status-line refresh

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: (doc-only; no failing test)** Update the Schwab/schwabdev gotcha block:
  - RETIRE the "plaintext OAuth at rest (V1)" gotcha (Fernet ships -> "tokens encrypted at rest, key in sibling user-config; V1.5: defeats casual disk/backup inspection, not a full-dir attacker").
  - Note the schwabdev-2.5.1 logger-name gotcha still holds on 3.0.5 (`"Schwabdev"`).
  - ADD: the daemon-checker is DELETED on v3 (P14.N7 wrapper + F-1 badge gone; `swing schwab status` is the single token-health surface; `/schwab/status` page preserved).
  - UPDATE the `setup`-clean-DB gotcha for `.db` SQLite semantics (logout renames-aside the v3 SQLite DB; the pre-v3 JSON format triggers the U-A re-setup message).
  - RECORD the L2 re-anchor (the first baseline move; endpoint-diff-proven).
  - Update the status-line: Phase 15 first arc SHIPPED; schwabdev 3.0.5; L2 re-anchored once.

- [ ] **Step 2-4: (n/a)**

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): refresh the Schwab block for schwabdev v3

Retire the plaintext-tokens gotcha, record the daemon-checker deletion and the L2 re-anchor,
and update the setup-clean-DB semantics for the v3 SQLite tokens format."
```

### Task 4.6: G7 -- the binding operator LIVE-OAuth re-setup smoke (GATE; not a code task)

See §H.2. This is the merge-blocking operator gate. It is enumerated here so the executing-plans phase treats it as a discrete checkpoint, not an afterthought.

**Slice 4 done-when:** Fernet on + green; L3 verified; the L2 re-anchor committed AFTER operator sign-off on the endpoint diff; CLAUDE.md refreshed; G7 witnessed (§H.2). `python -m pytest -m "not slow" -q` FULLY green (including the re-anchored L2 test).

---

## §H Operator gates

### §H.1 The L2 sign-off GATE (Slice 4, Task 4.4) -- OQ-4
The FIRST-EVER L2 baseline move requires explicit operator approval recorded at the executing-plans gate, on the REAL post-migration HEAD SHA. The implementer presents `docs/schwab-v3-endpoint-diff.md` (ZERO new endpoints) + the rationale block; the operator signs off; ONLY THEN is `L2_LOCK_BASELINE_SHA` set + committed. The escalation rule binds: if the diff ever shows a genuinely-new endpoint, STOP + escalate.

### §H.2 G7 -- the binding operator LIVE-OAuth re-setup smoke (L7) -- merge-blocking
Mock tests are necessary but INSUFFICIENT for the auth/token path. On the v3 branch, the operator runs:
1. `python -m swing.cli schwab logout` (renames the 2.x DB aside).
2. `python -m swing.cli schwab setup` (real Schwab OAuth round-trip; writes the v3 SQLite DB; if Fernet on, `enc:`-wrapped).
3. `python -m swing.cli schwab status` (reads the v3 DB; shows a valid token + refresh-token days-remaining; no DEGRADED).
4. A real `python -m swing.cli schwab fetch` / a `swing web` dashboard render that hits a live Schwab call (`linked_accounts` / market data).
5. **Witness the UNSEEDED default** (memory `feedback_seeded_gate_masks_default_state`): in a NORMAL `swing web` run, the topbar has NO badge and NO console error. (NOT a seeded sidecar -- the seeded gate is exactly the gap that produced A-7.)

Merge is BLOCKED until the operator confirms G7. After G7, the orchestrator performs the merge (per memory `feedback_orchestrator_performs_merge`). NOTE the TaskStop/detached-server discipline: if any `swing web` is spawned for the smoke, free the port + verify no straggler before teardown (memory `feedback_taskstop_does_not_kill_detached_server`).

### §H.3 Cutover ordering (OQ-6)
At merge time, BEFORE the first v3 `swing web`/pipeline run: merge -> `pip install -e ".[dev,web]"` (pulls v3) -> `swing schwab logout` -> `swing schwab setup` -> verify `swing schwab status` -> resume ops. Rollback: revert the pin to `<3.0.0`, `pip install -e`, then `logout` -> `setup` re-creates the 2.x JSON DB (low blast radius; no swing.db change).

---

## §I Self-review -- spec-coverage matrix

| Spec section | Plan task(s) | Covered? |
|---|---|---|
| §3 pin (OQ-3) | 1.1 (+ §C.1 coupling, 2.3 T1b) | YES |
| §3 account_linked -> linked_accounts | 1.2 | YES |
| §3 tokens_file -> tokens_db (4 sites) | 1.3 | YES (4 sites, all auth.py; cli.py has none -- divergence noted) |
| §3 _rename_stale_tokens_db sibling review | §C.6 T-RENAME + 2.7 inertness assertion | YES |
| §3 Note A version test | 1.1 | YES |
| §4 non-interactive guard | 2.1 | YES |
| §5.1 writer (W-A) + DDL pin | 2.2 (+ 2.3 T1b) | YES |
| §5.2 reader + health re-map | 2.4 + 2.5 | YES |
| §5.3 P14.N7 + F-1 DELETE | 3.1 | YES (8 call sites + ~20 fields -- divergence noted) |
| §5.4 comprehensive preflight | 2.6 | YES (T8, T9a-c) |
| §5.5 logout/revoke rewrite | 2.7 | YES (T7a/c/d; T7b in 4.2) |
| §6 Fernet | 4.1 + 4.2 | YES |
| §7 L2 re-anchor + endpoint diff + sign-off | 4.4 + §H.1 | YES |
| §8 L3 no schema change | 4.3 | YES |
| §10 G1-G6 | 1.4 | YES |
| §10 T1-T9 | 2.2-2.7 | YES |
| §10 G7 live-OAuth gate | §H.2 | YES |
| §1.2 /schwab/status preserved | 2.7 status test + §C.5 | YES |
| ASCII (#16/#32) | §C.6 + per-task strings | YES |
| Co-Authored-By / trailer hazard | every commit stem (plain-prose final para) | YES |

**Placeholder scan:** every code/test step contains real code; the only deliberately-deferred literal is `<post-migration-SHA>` in Task 4.4 (filled at executing-plans on the real HEAD, behind the sign-off GATE -- by design, not a placeholder gap). The `...` markers in G5/status-page/config-show test bodies are explicitly flagged "re-grep + fill at executing-plans" where the exact symbol/route names must be confirmed live; the surrounding assertions are concrete.

**Type/name consistency:** `_write_schwabdev_tokens_db`, `_V3_SCHWABDEV_DDL`, `_raise_on_auth`, `_assert_v3_tokens_db_loadable_or_raise`, `_read_v3_refresh_token`, `_resolve_fernet_key`, `_generate_fernet_key`, `_fernet_cipher` are used consistently across Slices 2 + 4. `_read_tokens_metadata` keeps its name (signature/return-shape change only).

---

## §J Execution notes

**Task count:** Slice 1 = 4 tasks; Slice 2 = 7 tasks; Slice 3 = 1 atomic task; Slice 4 = 6 tasks. **Total = 18 tasks** (+ 2 operator GATE checkpoints: §H.1 L2 sign-off, §H.2 G7 live-OAuth smoke).

**Codex convergence (OQ-7):** SINGLE adversarial chain at the END of writing-plans (this plan), run to convergence (zero new criticals AND zero new majors; the ~5-round cap is suspended). Executing-plans runs its own single chain at the end.

**Slice sequencing recommendation:** 1 -> 2 -> 3 -> 4, strictly. The floored pin (1.1) is not merge-safe until T1b (2.3); the L2 re-anchor (4.4) can only be computed once ALL prose churn is final (after Slice 3). G7 (§H.2) is last. Do not chase the L2 grep-test failure between Slice 1 and Slice 4 -- it is EXPECTED-fail from the prose churn until the re-anchor.

**Line estimate:** this plan ~ 1100 lines (within the 900-1400 target).

*End of plan. Derive execution via superpowers:subagent-driven-development or superpowers:executing-plans. Two operator GATES bind: the L2 sign-off (Slice 4) and the live-OAuth smoke (G7).*
