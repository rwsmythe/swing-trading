# Phase 22 arc 22-F -- the handler-escape + transaction-hygiene sweep: PLAN

**Branch:** `22-f-plan`, cut from main @ `79035d59` (schema v41). **Plan cell:** writing-plans, `implementer-opus-high`.
**Rules read from main by absolute path** (`C:\Users\rwsmy\swing-trading\docs\implementer-dispatch-recipe.md`, `docs\harness-architecture.md` §5.1) at main @ `79035d59`. The worktree's own copies are stale by design.
**Inputs (lifted, not re-derived):** the census `2026-09-25-phase22-arc-f-handler-escape-sweep.census.md` (row ids `C1-nn`, `C2-nn` are stable and used below), the ledger `...ledger.md` (the six rulings block-quoted, the orchestrator's composition note, the C1-27 disposition), the brief `docs/phase22-arc-i-f-sweeps-commissioning-brief.md` §0.2/§0.4, §2.7-§2.11, §3 F-F*, §4 "22-F", §5, §6.
**Where the argument lives:** the ledger and the brief. This file is a task ladder and a test roster (recipe plan-stage rule 2).

---

## 0. Envelope

### 0.1 What 22-F is
Two classes, one arc (brief §2.7): **class 1 (D34)** -- a typed exception escaping an operator path (web: the app-wide 500 page, `app.py:149`; CLI: a traceback); **class 2 (D39)** -- a transaction on an operator path whose cleanup is unsafe (F1 BEGIN outside the protecting `try`; F2 a rollback trigger narrower than `BaseException`; F3 a rollback failure suppressed or replacing the original; F4 a bare `close()` after a durable write). Plus the cp1252 row (§2.7a), D68 (§2.10), and the AL-7 docstring rider (F-F6).

### 0.2 The fix shapes are CITATIONS (brief §2.8), never re-designed here
| shape id | cited from | used by |
|---|---|---|
| **S-CLICK** | CLI boundary rule: `except <T> as exc: raise click.ClickException(<message>) from exc`; message through `ascii_safe`/`safe_text` (F-F5) | C1-02..06, C1-07 if RED, C1-16 read half |
| **S-DEGRADE** | the existing `kind="error"`/`operator_typed` result, `entry_auto_fill.py:383-395`, `exit_auto_fill.py:759-771` (RD F-F1 (a)) | C1-01, C1-25, C1-27 |
| **S-4XX** | the surface's own typed refusal fragment (e.g. `routes/trades.py:3137-3151`'s 400 re-render) | C1-24, C1-09 if RED |
| **S-D39** | the 22-A template, `swing/trades/cohort_provenance_correction.py:2388-2419`: rollback under `if conn.in_transaction`, `except BaseException as cleanup_error`, `log_contained_note(... "MUST BE DISCARDED" ...)`, `raise cleanup_error from <original>`; BEGIN inside the `try`; the rollback trigger is `BaseException` | C2-01..17, C2-21 |
| **S-B02** | 22-B RULING B item 2, `swing/cli.py:1669-1860` (`trade review`): two durability facts bound at each writer's own return; refusal in flight -> R8's chained refusal; durable -> WARN (`_echo_either_sink`, `cli.py:1094`) + exit 0; nothing durable and no refusal -> byte-unchanged bare close | CLI F4 roots, C2-21 (B-04), C2-22 |
| **S-R8** | RULING R8 (22-B exec ledger :603): `ClickException(f"{refusal}; the connection close also failed: {safe_text(exc)}") from close_exc` | C2-22, CLI F4 refusal branch |
| **S-CONTAIN** | the 22-A3 web post-commit guard, `routes/trades.py:1700-2376` (`result` bound -> `log_contained` + a degraded-success response naming the row, never a 500) | C1-26 (D68), web F4 roots |
| **S-503** / **S-GROUP** | CHARC F-F7 (ledger) | C1-14 |

### 0.3 Carve-out, tripwires (CHARC F-F6, verbatim file list)
- `swing/trades/`: `reconciliation_auto_correct.py`, `reconciliation.py`, `entry_date_correction.py`, `schwab_reconciliation.py`, `account_equity_snapshots.py`, `daily_management.py`, `hypothesis.py`, `risk_policy.py`, `exit_auto_fill.py`, `entry_auto_fill.py`. **Amended by the R1-gate rulings (CHARC, ledger "Round 1 gate -- rulings LANDED"), each with its bound:** `exit.py` (A-1: the one C1-24 price guard and its typed error; nothing else in the file moves), `cohort_provenance_correction.py` (A-2: message truth plus the `in_transaction` re-read at `:2388-2419` and `:3547-3560`; no control-flow change), `entry_intent_assignment.py` (A-3: the D39 shape on the in-try ROLLBACKs and the cleanup ROLLBACK of `assign`'s one try; R7's COMMIT at `:665` does not move). `swing/data/`: `db.py` (C2-21), `yfinance_audit.py` (C2-10), `repos/review_log.py` (C2-15). `audit_service.py` is not carve-out-governed.
- **Bounds:** guard-and-handler edits only (except tuples, typed translations, the D39 rollback-cleanup shape with both-verbs-fail proxies); NO schema; NO new module under `swing/`; NO dependency; NO standing process; NO behaviour change beyond the census rows. **A file outside this list is an AMENDMENT REQUEST to the orchestrator, never a self-grant** (§9 records the three granted).
- Not carve-out-governed and in the envelope: `swing/cli*.py`, `swing/web/**`, `swing/integrations/schwab/**`, `swing/latches/**`, `swing/metrics/**`, `swing/diagnostics/**`. New TEST modules are allowed (the proxy helpers below).
- **Out of envelope (tag, do not fix):** 22-G's surfaces (D35 `:139` render, D35 `:143`, BANK-4 `value="inf"`, D47, D71); D46's interface; D69 (the rider's, merged at `8c4c65ad`); RD 1(iii) (the exit POST re-render does not round-trip the submitted anchor -- orchestrator's queue); every pipeline-internal site (F-F3, census §5).

### 0.4 Shared test instruments (new test modules; none under `swing/`)
- `tests/_22f_proxies.py`:
  - `FailingVerbsConn(real, *, fail_sql_prefix=None, fail_rollback=False, fail_close=False, raise_on_sql=sqlite3.OperationalError)` -- delegates to a real connection; fails the named statement verb and/or `rollback()` and/or `close()`. Modeled on `tests/trades/test_cohort_provenance_write.py:1361` `_FailingCleanupConn` (a proxy, not a monkeypatched module function, so the production handler reacts to a real call). `execute("ROLLBACK")` is matched as a rollback too (§1.2 row 3).
  - **Post-`executescript` mode (R1-02):** `fail_after_executescript=(prefix, n)` fails ONLY the FIRST statement matching `prefix` issued AFTER the proxy's `n`-th `executescript` call has RETURNED; every earlier match passes. Needed because `_apply_migration` issues `PRAGMA foreign_keys` twice before the script (the read at `db.py:564`, the `=OFF` at `:571`) and the restore only in the `finally` (`:579-581`); a bare `fail_sql_prefix` fails the first read.
  - `patch_conn_opener(monkeypatch, target, proxy_factory)` (R3-01; replaces the R1 `connect_returning`) -- patches the dotted `target` (`"<module>.<name>"`), which MUST be the name the code under test resolves AT CALL TIME, read from its source: a module-level `from swing.data.db import connect` binds `<that module>.connect`; a FUNCTION-LOCAL `from swing.data.db import connect` re-reads `swing.data.db.connect` on every call; `open_connection` likewise. The proxy instances the factory built are returned to the test.
  - **Did-it-fire rule (R3-01, binding on EVERY proxy- or monkeypatch-driven test in this plan):** the proxy records its calls per verb (`close`, `rollback`, `execute` prefixes, `executescript`), and each test asserts the verb it fails (or, for a pass-through proxy, the verb it observes) was called at least once. A missed patch then fails RED instead of passing vacuously. A monkeypatched function (not a connection) is asserted called the same way (a counting wrapper). No exceptions (R4-01).
  - **Opener targets, measured** (a Python AST walk classifying each `connect(`/`open_connection(` call by whether the enclosing function imports the name locally): `swing/cli.py` -- 34 calls resolve `swing.data.db.<name>` (local import); 10 resolve the module global `swing.cli.<name>`, among them `pipeline force-clear` (`:5362`), `eval` (`:466`), `diagnose prune-chart-cache` (`:7462`), `db_migrate`'s probe (`:255`). `swing/cli_config.py` -- all 6 local (`swing.data.db.connect`). `swing/cli_schwab.py` -- all 8 module-global (`swing.cli_schwab.connect`). `swing/web/routes/`: `account`, `config`, `metrics`, `reconcile`, `schwab`, `watchlist` resolve `<module>.open_connection`; `charts`, `dashboard`, `health`, `journal`, `latches`, `patterns`, `pipeline`, `recommendations` resolve `<module>.connect`; `trades` resolves `swing.web.routes.trades.connect` EXCEPT `review_post` (`POST /trades/{id}/review`, `:3439`), which imports locally and resolves `swing.data.db.connect`.
  - `open_connection_returning(proxy_factory)` -- patches the MODULE GLOBAL `swing.data.db.open_connection`, the name `ensure_schema` resolves (`db.py:1054`). `cli.py` binds its own `open_connection` by import (`cli.py:41`), so `db_migrate`'s pre-version probe (`:270`) is untouched by the patch; the proxy wraps the connection AFTER `open_connection`'s own `PRAGMA foreign_keys=ON` (`db.py:156`), which it therefore never sees.
- `tests/_22f_ast.py`: the AST walkers the four closure tests share (handler enumeration with enclosing function + sibling handlers of the same `Try`; call-site enumeration with enclosing function; `ClickException` argument walk).
- Every RED test is run on the unmodified tree first and its failure text pasted into the commit message body (plain prose, no `Word:` final paragraph).

### 0.5 Executing cell, reviewers, gates
- **Executing cell: `implementer-opus-high`** (brief §0 preamble; reason: must-converge-Codex work across `swing/trades` transaction code on money-bearing paths). Sonnet is not recommended: the D39 rows are measurement-adjacent cleanup code where a wrong answer is confident and hard to detect.
- **Reviewer A: `strong`** (recipe §3; production code), repo read-access (the stdin bundle carries the diff PLUS the reference files named per task), to `NO_NEW_CRITICAL_MAJOR`, per-round assertions, copy-per-round to `C:\Users\rwsmy\swing-data\review-transcripts\22-f-exec\`. Reviewer B is the orchestrator's.
- **Suite gates:** `python -m pytest -m "not slow" -q` FULL, (G1) at the start (baseline, count recorded), (G2) after the last task and BEFORE the Codex loop, (G3) after convergence on the final head. `ruff check swing/` clean at G2 and G3. `git log 79035d59..HEAD --format='%H%n%(trailers)'` empty for every commit.
- **Merge:** code-only, no witness rung (brief §2.11); `--no-ff` if any ledger cites branch SHAs (recipe §1).

---

## 1. The ruling-condition -> task/test map (every condition has a row; a missing row is a defect)

| # | source | condition (condensed; the ledger holds the literal text) | discharged by |
|---|---|---|---|
| R1 | RD F-F1 1 | C1-01 DEGRADE (a) on `GET /trades/entry/form`, `GET /trades/{id}/exit/form`, both POST re-renders | T-A1 (A1-a..A1-h; the exit POST re-render is A1-e', R1-01) |
| R2 | RD 1(i) | nothing written on GET before the raise except the `schwab_api_calls` audit row, closed before raising; proven by a fresh-connection read | T-A1 A1-d |
| R3 | RD 1(ii) | PIN: validation-failed entry POST carrying a populated schwab anchor + re-fetch raising parity -> rendered hidden anchor == submitted, kind `populated` | T-A1 A1-e |
| R4 | RD 1(iii) | exit POST re-render does not round-trip the anchor -- OUT of 22-F | §10 AL-6 (orchestrator's queue; not fixed) |
| R5 | RD 1(iv) | one test per form that parity reaches `kind="error"` | T-A1 A1-a (entry), A1-b (exit) |
| R6 | RD 1(v) | degraded form SHOWS the advisory naming `SchwabSchemaParityError` | T-A1 A1-c, A1-c' |
| R7 | RD 2(i) | C1-25: NEW reason token `non_finite_quantity`, never folded into `no_quantity`/`sub_one_share_quantity` | T-A3 A3-a, A3-e |
| R8 | RD 2(ii) | `math.isfinite` precedes `int(quantity)` in the same chain; not a catch of `OverflowError` | T-A3 A3-a, A3-b, A3-f |
| R9 | RD 2(iii) | discriminators inf->token, nan->token, 1e18->NOT this token, 0.9->`sub_one_share_quantity` unchanged | T-A3 A3-a..A3-d |
| R10 | RD 3 (citation SUPERSEDED by RD, R1 gate) + orch. | C1-27 entry twin: refuse the candidate, named advisory, form proceeds. The None-guard condition is WITHDRAWN (both quantity fields are validated numbers); C1-27's real content is `[0,1)` -> the sub-one-share refusal | T-A2 (A2-b, A2-c; read in §1.2 row 4) |
| R11 | RD posture | degraded rows carry NULL auto-fill provenance exactly as today | T-A1 A1-f |
| R12 | CHARC F-F2 (1) | all 18 `SchwabApiError` handler sites READ, each in exactly one state WIDENED / COVERED / UNREACHABLE | §3 table |
| R13 | F-F2 (1) | WIDENED sites: message made true for a parity error where the text names transience | §3 table column "message" |
| R14 | F-F2 (2) | AST closure test; UNREACHABLE set spelled as the exemption list with reasons; a 19th handler goes RED | T-B1 (COVERED per R40) |
| R15 | F-F2 (3) | `entry_auto_fill.py:383`, `exit_auto_fill.py:759`, `cli_schwab.py:1478/:1490` WIDENED; landing = the `kind="error"` result (composition note) | T-A1, T-B2 |
| R16 | F-F2 RJFE | `ReservedJournalFieldError`: per-site `ClickException`, NO re-base | T-A5 |
| R17 | F-F2 RJFE | closure: each operator root reaching a raise site carries the translation | T-B3 |
| R18 | F-F4 (1) | one LOUD pin per declared class | T-D1..T-D4 |
| R19 | F-F4 (2) | each declared class cites its WRITE-SIDE constraint (quoted); a class with none is a FINDING, listed by name with its search | §5 table + T-D0 (INV-MODEL per member, R1-03) + §11 (FND-4) |
| R20 | F-F4 (3) | `NoActivePolicyError` CONVERTED on every root that reaches it; closure test | T-D5 |
| R21 | F-F4 + CHARC R1-gate 3(c), as sharpened at the R2 gate | read-path closes DECLARED for the 17 read roots; the per-root read confirms exactly one thing -- no OPERATOR-RECORD write in the root (CHARC's statement of record, R2 gate); a read root found to write one moves to the 41 | T-G3 |
| R22 | F-F5 (1) | premise CORRECTED, not deleted; RED discriminator stays the R3-1 form | §6 preamble; T-E1 |
| R23 | F-F5 (2) | `ascii_safe` stays at `swing/trades/entry.py:60` (or an existing module); no new module | T-E1/T-E2 (import from `swing.trades.entry`) |
| R24 | F-F5 (3) | AST closure: every `ClickException` argument referencing an exception variable or a message attribute passes through `ascii_safe`/`safe_text`; `cli.py:1950` joins `:1936` | T-E1 |
| R25 | F-F6 | the file list verbatim; nothing outside it; a new file is an amendment | §0.3, §9 |
| R26 | F-F6 AL-7 | ONE comment-only commit; re-verify EVERY claim against `:2194` onward incl. kept ones; delete the unimplemented branch; says what the code does TODAY; grep `tests/` for the docstring text first | T-H1 |
| R27 | F-F7 web | handler for `SchemaVersionMismatchError` inside `_register_exception_handlers` (`app.py:148`), typed 503 page, existing message | T-C1 |
| R28 | F-F7 CLI | `click.Group` subclass, `invoke` override in `cli.py`, catching ONLY `SchemaVersionMismatchError` -> `ClickException` | T-C2 |
| R29 | F-F7 (1) | `db-migrate` through the group against a stale-version fixture MIGRATES | T-C2 C2-c |
| R30 | F-F7 (2) | CliRunner wrong-version: exit 1 + message + NO traceback; TestClient: 503 + message; both RED-first | T-C1 C1-a, T-C2 C2-a |
| R31 | F-F7 tripwires | no new module / schema / dependency / standing process | T-Z1 gate check |
| R32 | brief §4 (1) | the census table on the plan | the census file (this directory) + §1.2 corrections |
| R33 | brief §4 (2) | per class-1 row: RED on main's behaviour, GREEN typed, status pinned | Part A/B/C/D tasks |
| R34 | brief §4 (3) | per D39 row: both-verbs-fail proxy; where durable precedes cleanup, the close-after-durable discriminator | Part F/G tasks |
| R35 | brief §4 (4) | D68: planted non-race exception after the exit commit -> 200 + degraded-success notice, exit durable | T-A7 |
| R36 | brief §4 (5) | RJFE and parity reach the operator typed on every path the census lists, by execution | T-A1, T-A5, T-B2, T-B3 |
| R37 | brief §4 (6) | F-F3 declared list verified by read | census §5 (verified) + T-Z1 re-check |
| R38 | brief §4 (7) | full fast suite green on the merged head with SHA; ruff; trailers | §0.5 gates (merged head = orchestrator) |
| R39 | brief §2.9 | a row whose fix changes whether a money-bearing entry/exit proceeds is a FORK to RD | only C1-01/C1-25/C1-27 (ruled); T-A6 C1-24 checked (§1.2 row 7; the guard is exactly the schema's refusal set, so `inf` is NOT refused -- A6-f) |
| R40 | CHARC R1-gate 1 | COVERED = an explicit clause naming `SchwabSchemaParityError` or its strict base `_RedactedMessageError`, in the SAME `Try`, ANY position; `Exception`/`BaseException` never COVER; the closure test's docstring records that order is load-bearing only if the type is ever re-based | §3.1 table; T-B1 |
| R41 | CHARC R1-gate 1 | `marketdata_ladder.py:337`/`:469` WIDENED (not COVERED-by-base); the widened clause's log carries `exc` as well as `type(exc).__name__`; fallback unchanged; pin = a planted parity raise inside each ladder try asserting the yfinance fallback AND the logged message; AL-3 removed | T-B4 |
| R42 | CHARC R1-gate 2 A-1 | `record_exit` refuses a price failing the `fills.price` CHECK's predicate with a TYPED error BEFORE the write; the route's existing 400 fragment delivers it; the CHECK stays the backstop; nothing else in `exit.py` moves; AL-4 void; `:139` stays 22-G's | T-A6 |
| R43 | CHARC R1-gate 2 A-2 | the two messages say what was observed (rollback raised `<cleanup_error>`), RE-READ `conn.in_transaction` after the failure and report that value, "discard this connection either way"; no control-flow change; the chained raise stays; AL-5 void | T-F9 |
| R44 | CHARC R1-gate 2 A-3 | BOTH `assign` ROLLBACK sites under D39: the cleanup ROLLBACK (`:667-668`) guarded (catch, log discard, raise chained from the original) AND the normal-path ROLLBACK (`:654`) whose failure reaches the same handler; the plan states which error the operator hears on the double failure; R7's COMMIT at `:665` stays | T-F8 (C2-16 rows) |
| R45 | CHARC R1-gate 3(a) | `NoActivePolicyError`: one app-level typed 503 (web), per-root `ClickException` (CLI), closure over the call sites; the page NAMES the config command that creates a policy; `routes/config.py:154` handling keeps precedence and is PINNED so the app handler cannot shadow it | T-D5 (step 0, D5-k) |
| R46 | CHARC R1-gate 3(b) | INV-TYPE's citation = the constant/typed argument at every caller, each caller line quoted; a caller passing a non-constant moves the member OUT of the declarable set (FND-4's roster or a conversion task), never a footnote | §5 INV-TYPE row; T-D2 |
| R47 | CHARC R1-gate 3(c) | the corrected counts 41 write / 17 read replace the census's 32/26 by replacement, with the method | §1.2 row 5; census §4.2 (edited by replacement) |
| R48 | CHARC R1-gate 3(d) | FND-1, FND-2, FND-4 are register rows written by CHARC at his next charter touch; the plan lists them, it does not write the register | §11 |
| R49 | RD supersession (R1 gate) | T-A2 states the inf mechanism (float overflow of the validated leg SUM, never a validated leg); the inf and NaN discriminators are GUARD tests planted at the resolver's return and labelled so; the None-guard is dropped; `[0,1)` -> the sub-one-share refusal; the plan reads `exit_auto_fill.py:1195`'s quantity source | T-A2, T-A3; §1.2 rows 4 and 10 |
| R50 | orch. R1-01 | the exit POST's `except ValueError` re-render with parity on the orders fetch: RED 500, GREEN 400 re-render naming `SchwabSchemaParityError`; NO anchor assertion (RD 1(iii)) | T-A1 A1-e' |
| R51 | orch. R1-02 | B-04 proxy on `swing.data.db.open_connection`, failing only the first `PRAGMA foreign_keys=` after `executescript` returns; the boundary is `cli.py db_migrate` (fresh plain-sqlite3 read-only re-read; WARN + exit 0 at target; re-raise otherwise); the pre-COMMIT CONTROL stays | §0.4; T-F10 |
| R53 | orch. R3-01 | `patch_conn_opener` at the name each root resolves at call time (read from its source); EVERY proxy-/monkeypatch-driven test asserts the proxy fired | §0.4 (helper, did-it-fire rule, measured targets); A1, A2/A3, A6-e, A7-a/b, B2-c, B4, C1-16, Part F delivery, T-F11, G1-a, G2-a |
| R54 | orch. R3-02 | C2-21's OWN site (`_apply_migration`'s rollback) driven: both-fail chained + one record, `KeyboardInterrupt` rolled back, single failure, CONTROL | T-F10 C2-21-a..d |
| R52 | orch. R1-03 | INV-MODEL as a committed roster plus an AST closure; each persisted-row member quotes its CHECK/trigger in the exec ledger; server-computed members become FND-4; AL-8 removed | T-D0; §11 FND-4 |

### 1.2 Intake corrections (a ruling's or the census's incidental FACT checked against the code; reported up with the encoding)
| # | the input said | the code has | encoded |
|---|---|---|---|
| 1 | census C1-16: `DecisionIntentsUnavailableError` is raised only when the repo IMPORT fails | `swing/latches/reader.py:280-287` ALSO raises it in strict mode on ANY exception from `list_intents_for_latch` (a DB read failure) | T-A8: the read-failure half is a RED attempt + S-CLICK/route refusal; the import half is a §11 finding |
| 2 | census C1-15: STATIC (the `:126` condition not read) | `record_view(... actionable=actionable)` is fed only the literals `1`/`0` by the comprehension at `routes/latches.py:350-352` | C1-15 DECLARED caller-prevented; no task |
| 3 | census C2-15/C2-16/C2-17: "none" for the rollback handler | `rb_census.py` counts `.rollback()` only; `execute("ROLLBACK")` sites exist at `repos/review_log.py:359`, `diagnostics/backfill_trades_sector_industry.py:130`, `entry_intent_assignment.py:644,654,668` (plus F-F3 `lease.py`/`runner.py`). By read: `review_log.py:248` BEGIN outside try, `except Exception: execute("ROLLBACK")` unguarded; `backfill...:115` same; `entry_intent_assignment.py:640` BEGIN INSIDE the try (F1 does NOT hold), `except BaseException:` unguarded `execute("ROLLBACK")` | C2-15/C2-17 FIX (F1+F2+F3); C2-16 FIX F3 only -- the read confirms a site, which is F-F6's stated condition for `entry_intent_assignment.py` (§9 A-3 records it) |
| 4 | RD 3: "the resolver has a return-None path (`mappers.py:428`)" -- **SUPERSEDED by RD at the R1 gate** (his correction accepts this row) | `_resolve_match_quantity` is `swing/trades/schwab_reconciliation.py:521`, typed `-> float`; it returns `sum(leg.quantity)` or `so.quantity`. `SchwabExecutionLeg.quantity` is `> 0` + finite (`integrations/schwab/models.py:216`); `SchwabOrderResponse.quantity` is non-negative finite, never None (`models.py:336-340`); the leg mapper DROPS a leg whose `float()` fails (`mappers.py:544-548`). `mappers.py:428` is `map_filled_quantity`'s return-None, not this resolver | None UNREACHABLE (the None-guard is dropped); NaN UNREACHABLE on validated models; **inf reachable ONLY by float overflow of the leg SUM** (every addend validated finite; no broker payload delivers inf past the validators); **`[0,1)` REACHABLE** (`so.quantity` in `[0,1)` with no executions -- `0` is admitted at `:336` -- or fractional legs). T-A2: A2-a/A2-d are GUARD tests planted at the resolver's return (labelled); A2-a' is the overflow mechanism on real models; A2-b/A2-c are C1-27's real content |
| 5 | census 4.2: "32 operator-record writes / 26 read paths" | its own listing names **41** operator-record roots (25 CLI + 16 web) and **17** read/cache roots (12 web + 5 CLI); 58 total matches `f4.txt` | T-G1/T-G2 roster = 41; T-G3 = 17. These REPLACE the census's 32/26 (census §4.2 edited by replacement, CHARC 3(c)); method: count of the root entries the census's own §4.2 listing names, cross-checked against `f4.txt`'s 58 lines |
| 6 | CHARC F-F2 COVERED = "an explicit parity clause PRECEDES it in the same try" -- **AMENDED BY REPLACEMENT at the R1 gate** (CHARC 1) | `marketdata.py:652`/`:675`: the parity clause FOLLOWS (disjoint MRO, order inert); `marketdata_ladder.py:337`/`:469` are reachable and reach only the same try's `except Exception` (`:345`/`:478`) | COVERED = a clause naming `SchwabSchemaParityError` or `_RedactedMessageError` in the same `Try`, any position; `Exception`/`BaseException` never COVER (R40). The ladder's two sites are WIDENED (R41, T-B4). `RuntimeError` (also a strict base) is not in the ruled COVER pair and is not counted as covering; no site depends on it (row 2 of §3.1 is UNREACHABLE on its own) |
| 7 | census C1-24: service twin "a price that rounds to 0.00" | `swing/trades/exit.py:152-171` validates reason, shares, trade, state, size -- NOT price; `routes/trades.py:2404` `exit_price: float = Form(...)` has no `> 0` check. `price=0` reaches `fills.price REAL NOT NULL CHECK (price > 0)` (`0014:14`). Measured on a scratch in-memory table with that DDL: NaN is refused (`NOT NULL constraint failed` -- sqlite3 binds NaN as NULL); **`inf` is ACCEPTED** | The guard's refusal set is EXACTLY the schema's: `not (price > 0)` refuses `<= 0` (the CHECK) and NaN (NOT NULL), each refused today via the 500, so no proceed/block outcome changes (R39 not engaged). `inf` is NOT refused: refusing it WOULD change whether an exit proceeds (a fork to RD) and it is BANK-4's surface (22-G). T-A6 A6-f pins it |
| 8 | 22-A3 S8 item 8 cites `cohort_provenance_correction.py:2284-2291`, `:3341-3348` | drifted to `:2388-2419` and `:3547-3560`; both still say "STILL OPEN" unconditionally after a rollback raise | T-F9 (A-2 GRANTED) |
| 9 | brief §2.7a names `trade assign-intent` `cli.py` ~`:1939` | `:1935-1936` (`except ValueError as exc: raise click.ClickException(str(exc))`) and `:1950` | T-E1 names both |
| 10 | RD (R1 gate): "the plan cell verifies ... by reading `:1195`'s source of `quantity`" | on this tree the line is `exit_auto_fill.py:1194`: `quantity = _resolve_match_quantity(o)`, the SAME resolver (`schwab_reconciliation.py:521`, imported at `exit_auto_fill.py:88-91`), over `o`, a `SchwabOrderResponse` from `trader.get_account_orders` filtered at `:808` and passed by `_build_candidate(o)` at `:873` | BANK-3's inf enters by leg-sum overflow of validated legs, never by a validated leg; a constructed candidate only in tests. T-A3's inf/NaN rows are guard tests planted at the resolver's return; A3-a' is the mechanism |
| 11 | orch. R1-03: "a closure test asserts the roster EQUALS the AST set (every `__post_init__`/`_require_*`/`_validate_*` in `swing/` whose body raises)" | measured at this cell (a Python AST walk over `swing/**/*.py`, utf-8: functions named `__post_init__` or `_require_*`/`_validate_*`, at module or class level, containing any `Raise` node, compared with the distinct INV-MODEL origin functions in `r0-measurements/triage.json`): the AST set is **168**; the roster is **118**; 115 in both; **3 roster-only** (`data.models._provenance_snapshot_dict`, `metrics.honesty._check_finite`, `monitoring.tool_health.worst_of` -- named explicitly by `triage.py:8`, not by the pattern); **53 AST-only** (no operator root reaches them in the census call graph) | Equality is false by construction. Encoded as the recipe's closure form: AST set == roster-pattern-members UNION a reasoned exclusion map (the 53, reason "no operator root reaches it in the census call graph"), with the 3 name-listed members carried on the roster by name (T-D0). The reasoning of R1-03 is unchanged |
| 12 | CHARC A-3 names two ROLLBACKs (`:654`, `:667`) | a THIRD in-try ROLLBACK of the same class sits at `:644` (the `EnvelopeIdentityDriftError` branch); its failure reaches the same `except BaseException` handler exactly as `:654`'s does | encoded as the class: every in-try ROLLBACK (`:644`, `:654`) plus the cleanup (`:668`); one guard in the handler covers all three, and the tests drive each (T-F8). No extra code |
| 13 | orch. R1-02: "WARN + exit 0 at target" | `db_migrate`'s post-`ensure_schema` tail (`cli.py:355-420`) carries two obligations: the gate-image check/alarm (`:356-371`) and the SINGLE-FIRE v17 ratification (`:373`, gated `pre_version <= 16`; it can never re-fire, CLAUDE.md "Phase 9 risk_policy ratification is single-fire"). Exiting at the WARN would skip both | the WARN branch does NOT return early: it opens a fresh `open_connection` and CONTINUES the tail (gate check, ratification, final echo), whose own refusals apply unchanged; exit 0 only if the tail completes. B-04-d pins it. Returning early would report exit 0 over a single-fire obligation that never ran and can never run again. **Flagged up**: the authorization did not address the tail; the early-return branch is not viable, so this is encoded rather than routed as a fork |

---

## 2. PART A -- class-1 typed rows (web + CLI)

Every task: RED test committed with the fix in ONE commit per task (the RED run's output in the body). Test paths follow the subsystem (`tests/web/test_routes/`, `tests/cli/`, `tests/trades/`).

### T-A1 -- C1-01 `SchwabSchemaParityError` on the entry/exit forms (RD F-F1 (a); CHARC F-F2 (3); composition note)
**Fix:** add `SchwabSchemaParityError` to the tuples at `entry_auto_fill.py:383` and `exit_auto_fill.py:759` (import from `swing.integrations.schwab.client`). Message unchanged: "Schwab fetch failed ({type(exc).__name__}); auto-fill unavailable. Please enter manually." -- names no transience, true for a parity error (R13 row in §3). Nothing else changes.
**Fixture:** reuse `tests/trades/test_entry_auto_fill.py`'s `patch_live_state`/`patch_credentials`/`patch_client_factory`/`patch_get_orders` (`state["raises"]`), and the exit twins in `tests/trades/test_exit_auto_fill.py`; for routes, the real `resolve_*_auto_fill` (NOT the wholesale stub in `test_entry_form_auto_fill.py:38`) with `trader.get_account_orders` raising `SchwabSchemaParityError("<orders: missing required key 'x'>")`. Patch target: `swing.integrations.schwab.trader.get_account_orders` -- both modules call it through the module attribute (`entry_auto_fill.py:375`, `exit_auto_fill.py:751`), so the attribute is resolved per call; a counting wrapper is asserted called >= 1 in every A1 test (the did-it-fire rule, §0.4).

| test | drive | pre-fix (computed) | post-fix |
|---|---|---|---|
| A1-a | `resolve_entry_auto_fill(...)`, orders raise parity | raises `SchwabSchemaParityError` | returns `kind="error"`, `fill_origin="operator_typed"`, `entry_price is None` |
| A1-b | `resolve_exit_auto_fill(...)`, same | raises | `kind="error"`, `operator_typed` |
| A1-c | `GET /trades/entry/form?ticker=AAPL` (production env cfg, seeded watchlist row) | **500**, body carries the generic error page | **200**, body contains `SchwabSchemaParityError` AND `auto-fill unavailable` |
| A1-c' | `GET /trades/{id}/exit/form` on an open seeded trade | **500** | **200**, same two strings |
| A1-d | after A1-c, a FRESH `sqlite3.connect` read | (n/a: pre-fix 500) | `schwab_api_calls`: exactly one new row, `status='error'`, `finished_ts IS NOT NULL`; `trades`/`fills` row counts unchanged. **Discriminator for "closed before raising":** assert `status != 'in_flight'` |
| A1-e' | POST `/trades/{id}/exit` on an open seeded trade with `exit_shares` > remaining (so `record_exit` raises `ValueError`, `routes/trades.py:3137`), orders raising parity on the re-render's `build_exit_form_vm` fetch (`:3139`) | **500** (the fetch raises out of the `except ValueError` branch) | **400** `partials/trade_exit_form.html.j2` re-render; body contains `SchwabSchemaParityError` AND the `record_exit` refusal text; FRESH read: `fills` count unchanged. Asserts NOTHING about the anchor round-trip (RD 1(iii), AL-6) |
| A1-e | POST `/trades/entry` with `rationale="not-a-rationale"` (fails `_validate_rationale`, `routes/trades.py:779-790`), `schwab_source_value_json=<populated envelope>`, `fill_origin_at_form_render="schwab_auto"`, orders raising parity on the re-fetch | **500** (the re-render's `build_entry_form_vm` fetch raises) | **400**; the rendered hidden `schwab_source_value_json` input value == the submitted string byte-for-byte; rendered kind `populated`; no parity advisory in the banner (the restore clears it, `:487-505`) |
| A1-f | A1-c's rendered form | 500 | hidden `schwab_source_value_json` empty, `fill_origin_at_form_render` = `operator_typed` (NULL provenance on submit, R11) |
| A1-g | CONTROL: orders raise `SchwabApiError(500, "x")` | 200 + kind error (today) | unchanged |
| A1-h | CONTROL: POST re-render with orders returning normally | 400 + anchor restored | unchanged |

### T-A2 -- C1-27 the entry twin of BANK-3 (RD 3 as superseded at the R1 gate; orchestrator disposition)
**Read result (R10, R49):** §1.2 row 4. No None-guard (withdrawn: both quantity fields are validated numbers). **inf mechanism:** float overflow of the leg SUM at `_resolve_match_quantity` -- each addend is validated finite `> 0` (`models.py:216`); no broker payload delivers inf past the validators. **C1-27's real content is `[0,1)`:** `int(0.5) == 0` shares. **Fix** in `entry_auto_fill.py` after `quantity = _resolve_match_quantity(chosen)` (`:445`) and BEFORE `shares = int(quantity)`: `if not math.isfinite(quantity):` return `kind="empty"`, `operator_typed`, advisory `"Schwab BUY fill for {ticker} carries a non-finite quantity; auto-fill unavailable (a data-quality alarm). Please enter manually."`; `elif int(quantity) < 1:` (the truncation spelled, as `exit_auto_fill.py:1206-1214` spells it) return `kind="empty"`, advisory `"Schwab BUY fill for {ticker} has an execution quantity below one whole share; please enter manually."`. Advisory strings ASCII.
**Refusal-token encoding (fact reported up):** RD names the entry refusal token `sub_one_share_quantity` "as on the exit side". `EntryAutoFillResult` carries NO reason-token field (its fields: `kind`, `fill_origin`, the value fields, `advisory_text`, `schwab_source_value_json`, `auto_fill_audit_at`); adding one is an interface change outside the guard-only bound. Encoded: the advisory text carries the exit side's operator text for that token verbatim (`_OMISSION_REASON_TEXT["sub_one_share_quantity"]` = "an execution quantity below one whole share", `exit_auto_fill.py:150-158`), and the two refusals stay distinct strings (the non-finite one never says "below one whole share", R7's no-fold rule on the entry side).

| test | drive (via `patch_get_orders` with a real `SchwabOrderResponse`) | pre-fix | post-fix |
|---|---|---|---|
| A2-a | **GUARD TEST, planted at the resolver's return** (the 18-B.1 raw-plant technique; NOT a claim the broker delivers it): monkeypatch `entry_auto_fill._resolve_match_quantity` -> `float("inf")`; a counting wrapper around the plant is asserted called >= 1 (R4-01) | `OverflowError` escapes (`int(inf)`) | `kind="empty"`, advisory contains `non-finite quantity`, NOT `below one whole share` |
| A2-a' | MECHANISM (the only validated path to inf): two legs of `1e308`, each a valid `SchwabExecutionLeg` | `OverflowError` escapes | same as A2-a |
| A2-b | FILLED, `price=10.0`, `executions=None`, `quantity=0.5` | `kind="populated"`, `shares == 0` | `kind="empty"`, advisory contains `below one whole share`, NOT `non-finite` |
| A2-c | same with `quantity=0.0` (admitted at `models.py:336`) | `populated`, `shares == 0` | `empty`, same advisory |
| A2-d | **GUARD TEST, planted at the resolver's return:** `_resolve_match_quantity` -> `float("nan")` (unreachable on validated models; labelled); a counting wrapper around the plant is asserted called >= 1 (R4-01) | `ValueError` escapes (`int(nan)`) | `empty`, `non-finite` advisory |
| A2-e | route: `GET /trades/entry/form` under A2-a' | **500** | **200**, advisory text rendered |
| A2-f | CONTROL `quantity=3.0` | populated, shares 3 | unchanged |

Patch target for A2-a/A2-d: `swing.trades.entry_auto_fill._resolve_match_quantity` (bound by the module-level import at `entry_auto_fill.py:85-89`, so the module attribute is what `:445` resolves). Did-it-fire: the counting wrapper around the plant, asserted called >= 1 in A2-a and A2-d (R4-01).

### T-A3 -- C1-25 BANK-3 `exit_auto_fill.py:1213` (RD 2)
**Fix:** in the reason chain at `:1202-1214`, insert `elif not math.isfinite(quantity): reasons.append("non_finite_quantity")` between the `quantity is None or quantity <= 0` test and `elif int(quantity) <= 0`; add `"non_finite_quantity": "a non-finite execution quantity from the broker (a data-quality alarm)"` to `_OMISSION_REASON_TEXT` (`:150-158`, the one place the reasons are listed). NOT a `try/except OverflowError`.

**Quantity source (R49, §1.2 row 10):** `:1194` `quantity = _resolve_match_quantity(o)` over a validated `SchwabOrderResponse`; inf arrives only by leg-sum overflow. The inf and NaN rows below are GUARD tests planted at the resolver's return (monkeypatch `exit_auto_fill._resolve_match_quantity`), labelled as such; A3-a' is the mechanism.

| test | quantity (`_build_candidate(o)` called directly with a real `SchwabOrderResponse`, then via `resolve_exit_auto_fill`) | pre-fix | post-fix |
|---|---|---|---|
| A3-a | GUARD TEST, planted at `swing.trades.exit_auto_fill._resolve_match_quantity` (module-level import at `exit_auto_fill.py:88-91`): `inf`; a counting wrapper around the plant is asserted called >= 1 (R4-01) | `OverflowError` | reasons `== ("non_finite_quantity",)` (plus `no_usable_date`/`no_execution_price` only if those also fail -- the fixture supplies date+price) |
| A3-a' | MECHANISM: two valid legs of `1e308` | `OverflowError` | `("non_finite_quantity",)` |
| A3-b | GUARD TEST, planted at the same target (unreachable on validated models): `nan`; a counting wrapper around the plant is asserted called >= 1 (R4-01) | `ValueError` (`int(nan)`) | `("non_finite_quantity",)` |
| A3-c | `1e18` (finite) | candidate built, `quantity=10**18` | unchanged -- NOT refused by this guard |
| A3-d | `0.9` | `("sub_one_share_quantity",)` | unchanged |
| A3-e | route `GET /trades/{id}/exit/form`, one inf candidate + one valid candidate | **500** | **200**; valid candidate listed; the omission advisory contains the new reason text |
| A3-f | source guard: the tokens `no_quantity` and `sub_one_share_quantity` are not appended for inf/nan (mutual exclusion kept, `:1186`) | n/a | asserted in A3-a/b |

### T-A4 -- C1-02/C1-03/C1-04 CLI tracebacks -> S-CLICK
- **C1-02** `trade exit` (`cli.py:1147-1170`): wrap `record_exit(...)` in `except ValueError as exc: raise click.ClickException(ascii_safe(str(exc))) from exc` (`InvalidStateTransition` is a `ValueError`).
- **C1-03** `trade stop-adjust` (`cli.py:1238-1261`): add `except ValueError` beside the existing `StopRegressionError` clause (order: `StopRegressionError` first -- check its MRO at execution; if it is a `ValueError` subclass it must stay first).
- **C1-04** `schwab purge-marketdata-archive` (`cli_schwab.py:989`), `schwab resolve-out-of-framework` (`:1019`): `except SchwabPipelineActiveError as exc: raise click.ClickException(ascii_safe(str(exc)))`, the same text the siblings at `:202/:366/:1387` give (read one, mirror it).

| test | drive | pre-fix | post-fix |
|---|---|---|---|
| A4-a | `swing trade exit 9999 ...` (no such trade) | `result.exception` is `ValueError`, exit code 1 with traceback in `result.exc_info` | `result.exception` is `SystemExit`, exit 1, output contains `Error: trade 9999 not found`, no `Traceback` |
| A4-b | `trade exit` shares > remaining | ValueError traceback | typed, message contains `exceeds remaining` |
| A4-c | A4-a then FRESH connection | -- | `fills`/`trades` unchanged (nothing written) |
| A4-d | `trade stop-adjust 9999 ...` | traceback | typed `not found` |
| A4-e | purge-marketdata-archive with a seeded `pipeline_runs` row `state='running'` | `SchwabPipelineActiveError` traceback | typed, exit 1 |
| A4-f | resolve-out-of-framework, same | traceback | typed |

### T-A5 -- C1-05/C1-06 `ReservedJournalFieldError`, `MultiRowCorrectionOverrideError` (CHARC F-F2 RJFE: per-site, NO re-base)
**Fix:** at `discrepancy override-correction` (`cli.py:4908-4932`) and `discrepancy resolve-ambiguity` (`:4599-4611`) add `except (ReservedJournalFieldError, MultiRowCorrectionOverrideError) as exc: raise click.ClickException(ascii_safe(str(exc))) from exc` as siblings of the existing clauses (both are `Exception` subclasses; order among the existing `ValueError` clause immaterial). **Web:** READ `routes/reconcile.py:1598-1768` first and record which clause catches each type on `POST /reconcile/discrepancy/{id}/resolve`; if neither is caught, add the route's existing 4xx refusal clause (S-4XX) and a web test; if caught, record the clause line in the commit and add the web test as a CONTROL.

| test | drive | pre-fix | post-fix |
|---|---|---|---|
| A5-a | resolve-ambiguity choosing a reserved field (a tier-2 world from `tests/_tier2_world_22a2.py` or the existing resolve-ambiguity CLI fixtures) so one of `:357,381,399,447,523,537` raises | traceback, `ReservedJournalFieldError` | exit 1, typed message, no traceback |
| A5-b | override-correction on a reserved field (`:2310`) | traceback | typed |
| A5-c | override-correction multi-row (`:1334`/`:1889`) | traceback | typed |
| A5-d | FRESH connection after A5-a/b/c | -- | `reconciliation_corrections` count unchanged |
| A5-e | web resolve POST with a reserved field | per the read | typed 4xx (or CONTROL) |

### T-A6 -- C1-24 `IntegrityError` past the exit POST's `except ValueError` (D35 half / BANK-1; AUTHORIZE-THEN-ABORT)
**Fix (A-1 GRANTED, R42):** in `swing/trades/exit.py`, define ONE typed error beside `record_exit`: `class ExitPriceRefusedError(ValueError)` (a `ValueError` subclass, so the route's existing `except ValueError` 400 fragment at `routes/trades.py:3137` and T-A4's CLI clause deliver it with no new clause). In `record_exit`, beside the `shares <= 0` check (`:154`) and BEFORE any statement: `if not (req.price > 0): raise ExitPriceRefusedError(f"exit price must be > 0; got {req.price!r}")`. The predicate is the `fills.price` column's refusal set EXACTLY (§1.2 row 7): it refuses `<= 0` (the CHECK) and NaN (the NOT NULL), and admits `inf` as the schema does (A6-f). The CHECK stays the backstop. Nothing else in `exit.py` moves (AUTHORIZE-THEN-ABORT).
**The D35 `:139` rounding half (a sub-half-cent price rendered `0.00`) is 22-G's and is NOT touched; so is BANK-4's `value="inf"`.**

| test | drive | pre-fix | post-fix |
|---|---|---|---|
| A6-a | `POST /trades/{id}/exit` `exit_price=0` | **500** (`sqlite3.IntegrityError: CHECK constraint failed`) | **400**, body contains `exit price must be > 0` |
| A6-b | CLI `trade exit ... --price 0` | traceback `IntegrityError` | exit 1, typed |
| A6-c | FRESH connection | -- | `fills` count and `trades.current_size` unchanged |
| A6-d | satisfiability (harness §5.1): the service refuses exactly what the column refuses, first -- `record_exit` with `price in (0, 0.0, -0.0, -1, float("nan"))` raises `ExitPriceRefusedError` BEFORE any statement (a `FailingVerbsConn` that raises on ANY `INSERT` records zero attempts; no counting wrapper needed -- R4-01's A6-d half REJECTED: the proxy is `record_exit`'s `conn` ARGUMENT, so there is no patch target to miss, and pre-fix the INSERT's `IntegrityError` fails this test) | `IntegrityError` at INSERT (CHECK for the first four, NOT NULL for NaN) | `ExitPriceRefusedError`, `isinstance(exc, ValueError)`, zero INSERT attempts |
| A6-e | CONTROL `price=0.01`, through the SAME counting proxy as A6-d (a pass-through this time) | exit recorded; the proxy counted >= 1 `INSERT` | unchanged -- this is what makes A6-d's "zero INSERT attempts" non-vacuous |
| A6-f | CONTROL (R39 guard): `record_exit` with `price=float("inf")` | exit recorded (the schema admits `inf`) | **unchanged** -- recorded; the guard does not refuse what the column admits (BANK-4, 22-G) |

### T-A7 -- C1-26 D68 + the exit route's F4 close (S-CONTAIN; brief §2.10, §4 (4))
**Fix:** restructure `exit_post` (`routes/trades.py:3133-3200`) to the 22-A3 outer-guard shape: bind `result` inside the guarded region; the `except ValueError` 400 branch unchanged; `finally: conn.close()` failure after a bound `result` is `log_contained` and recorded as a warning; ONE outer `except BaseException` over close + `build_dashboard` + renders: if `result is None` re-raise, else `log_contained` and return a degraded-success fragment at **200** naming the trade id and "the exit IS recorded; the page could not be refreshed" (a new small ASCII string; no new template -- an `HTMLResponse` built like `_entry_notice_html`'s fallback). **Not** `except Exception` (the 22-A3 reason: a durable row reported as a failure is the double-exit direction).

| test | drive | pre-fix | post-fix |
|---|---|---|---|
| A7-a | valid exit; monkeypatch `swing.web.routes.trades.build_dashboard` (module-level import at `trades.py:45`) with a counting wrapper raising `RuntimeError("planted non-race")`; asserted called once | **500**, exit durable | **200**, body contains the trade id and `IS recorded`; FRESH read shows the fill |
| A7-b | valid exit; `patch_conn_opener(..., "swing.web.routes.trades.connect", FailingVerbsConn(fail_close=True))` (`exit_post` resolves the module global) | **500** (close raise escapes `finally`) | 200 success fragment; one ERROR record naming the close failure. Both trees: the proxy recorded >= 1 `close()` |
| A7-c | CONTROL: `record_exit` raises `ValueError` | 400 | 400 unchanged |
| A7-d | CONTROL: `record_exit` raises `RuntimeError` BEFORE commit (`result` never bound) | 500 | 500 unchanged (nothing durable; the app handler is correct) |

### T-A8 -- the INSTRUMENT-ONLY class-1 rows (C1-07/08/09/15/16/18/22/23): first step decides
| row | first step (READ or RED attempt) | outcome -> action |
|---|---|---|
| C1-07 `InvalidOverrideComboError` (`reconciliation_auto_correct.py:813,825,837,1690,1705`) on `journal reconcile-tos` | READ the five raise conditions; RED attempt: CliRunner `journal reconcile-tos` with the override combination each names | RED -> S-CLICK beside `cli.py:3617` (typed, exit 1) + tests; not RED -> DECLARED-unreachable, the attempt (command + observed output) in the commit message and ledger |
| C1-08 `_SandboxAutoRedirectShortCircuit` (`:1729`) | READ at plan: raised only when `applied_by_override == "auto" and environment == "sandbox"` (`:1722`); caught at `schwab_reconciliation.py:1242` (pipeline pivot). Execution READ: the `applied_by_override` value `discrepancy resolve-ambiguity` passes | not `"auto"` -> DECLARED caller-prevented (cite the CLI line); `"auto"` -> S-CLICK + test |
| C1-09 `ImmutableJournalFieldError(ValueError)` (`:315`) on the web resolve POST | READ `routes/reconcile.py:1598..` for an enclosing `except ValueError` | caught -> CONFIRMED-HANDLED (cite clause) + a CONTROL test; not caught -> RED attempt -> S-4XX |
| C1-15 `ValueError` from `record_view` | DECIDED at plan (§1.2 row 2) | DECLARED caller-prevented; no task |
| C1-16 `DecisionIntentsUnavailableError` | DECIDED in part (§1.2 row 1). RED attempt: `POST /latches/view`, `POST /latches/intent`, CLI `latches parity` with `swing.data.repos.latch_order_intents.list_intents_for_latch` monkeypatched (a counting wrapper, asserted called; `reader.py:273` imports it function-locally, so the module attribute is read per call) to raise `sqlite3.OperationalError("database is locked")` | web 500 -> add the type to the route's existing fail-closed clause (`/latches/view` `:364` 409 degrade; `/intent`'s existing refusal); CLI traceback -> S-CLICK. The IMPORT half -> §11 finding FND-2 |
| C1-18 `LabelingDispatchError` (`patterns/labeling.py:326,501`) | READ the CLI call sites of `fire_claude_silver_label`/`fire_codex_review_for_silver_row` in `patterns label-exemplars` / `review-silver-with-codex` for the dispatch argument | always non-None -> DECLARED caller-prevented (cite line); None reachable -> S-CLICK naming the missing dispatcher |
| C1-22 `CallerHeld*` (9 classes) | none -- declared by class | §5 PROG-TX (T-D3 pin) |
| C1-23 pipeline internals on `pipeline run` | none | F-F3 DECLARED (census §5) |

---

## 3. PART B -- the F-F2 three-state list and the closures

### 3.1 The 18 `SchwabApiError` handler sites (READ at plan; method: AST enumeration of every `Try` whose handlers name `SchwabApiError`/`SchwabSchemaParityError`/`_RedactedMessageError`, then a read of each try body's callee for a mapper; 18 = CHARC's grep count)

| # | site | try body calls | reaches a parity raise? | state | message |
|---|---|---|---|---|---|
| 1 | `cli_schwab.py:304` `schwab_refresh` | `force_refresh` | no: `auth.py` contains no `Parity` token and no mapper (grep) | UNREACHABLE | n/a (names transience; unreachable so unchanged) |
| 2 | `cli_schwab.py:368` `schwab_logout` | `revoke_and_delete` | no (same grep); `:372 except RuntimeError` would catch it anyway | UNREACHABLE | n/a |
| 3 | `cli_schwab.py:1168` | `get_quotes_batch` | yes | COVERED (`:1164` explicit, precedes) | -- |
| 4 | `cli_schwab.py:1227` | `get_price_history` | yes | COVERED (`:1223` explicit, precedes) | -- |
| 5 | `cli_schwab.py:1478` `schwab fetch` snapshot | `_step_schwab_snapshot` | only until row 13 is widened (then contained there); widened per CHARC (3) | WIDENED | "Snapshot step failed: {exc}" -- true; `{exc}` -> `ascii_safe(str(exc))` (F-F5) |
| 6 | `cli_schwab.py:1490` orders | `_step_schwab_orders` | contained at row 14; widened per CHARC (3) | WIDENED | "Orders step failed: ..." true; `ascii_safe` |
| 7 | `auth.py:2194` `force_refresh` | token calls only | no | UNREACHABLE | n/a |
| 8 | `marketdata.py:565` `_call_endpoint` | `client_method()` (raw HTTP) | no | UNREACHABLE | -- |
| 9 | `marketdata.py:612` | `_extract_response_payload` | no: raises `SchwabApiError` only (`marketdata.py:161`) | UNREACHABLE | -- |
| 10 | `marketdata.py:652` | `mapper(payload)` | yes | COVERED (`:675` explicit, same try; it FOLLOWS, and order is inert under the disjoint MRO -- R40) | -- |
| 11 | `marketdata_ladder.py:337` | `get_quotes_batch` | yes | WIDENED (T-B4; the trailing `:345 except Exception` does NOT cover, R40) | "Schwab market-data quote fetch failed for %s (%s); falling back to yfinance" names no transience -- true; the widened line adds `exc` (`(%s: %s)`, `type(exc).__name__, exc`) |
| 12 | `marketdata_ladder.py:469` | `get_price_history` | yes | WIDENED (T-B4; `:478` does not cover) | "Schwab price_history failed for %s (%s)..." true; `exc` added the same way |
| 13 | `pipeline_steps.py:266` `_step_schwab_snapshot` | `get_account_details` -> `trader._call_endpoint` mapper (`trader.py:668`/`:700` re-raise parity) | yes | WIDENED | returns `"error": f"{type(exc).__name__}: api call failed"` -- names the type, no transience; kept |
| 14 | `pipeline_steps.py:586` `_step_schwab_orders` | orders + details + transactions | yes | WIDENED (ALREADY: the tuple names parity; precedent) | -- |
| 15 | `trader.py:575` | `client_method()` | no | UNREACHABLE | -- |
| 16 | `trader.py:626` | `_extract_response_payload` | no (`trader.py:145` raises `SchwabApiError` only) | UNREACHABLE | -- |
| 17 | `entry_auto_fill.py:383` | `trader.get_account_orders` | yes | WIDENED (T-A1) | "Schwab fetch failed (...)" true |
| 18 | `exit_auto_fill.py:759` | same | yes | WIDENED (T-A1) | true |

Tally: WIDENED 8 (5, 6, 11, 12, 13, 14, 17, 18), COVERED 3 (3, 4, 10), UNREACHABLE 7 (1, 2, 7, 8, 9, 15, 16). The five explicit parity handlers (`cli_schwab.py:1164,1223`, `mappers.py:919`, `marketdata.py:675`, `trader.py:668`) are unchanged.

### T-B1 -- the parity closure test (CHARC F-F2 (2)) -- `tests/integrations/schwab/test_22f_parity_handler_closure.py`
- Walk every `swing/**/*.py` (utf-8). For every `ExceptHandler` whose type names `SchwabApiError` (bare, dotted, or in a tuple): pass if (WIDENED) the same handler's tuple names `SchwabSchemaParityError`, or (COVERED, R40) another handler of the same `Try`, in ANY position, names `SchwabSchemaParityError` or `_RedactedMessageError` -- the COVER pair is typed exactly as ruled, and the test asserts the pair is a subset of `SchwabSchemaParityError.__mro__` (a re-base fails loudly); `Exception`, `BaseException` (and `RuntimeError`, not in the ruled pair) NEVER cover, so a broad tail cannot make a site vacuously covered; else the site's `(relative_path, enclosing_function, handler_line_text)` must be in `UNREACHABLE = {...: reason}` (the seven rows above, each reason one line: "try body is the raw HTTP call; no mapper", etc.).
- **Both directions:** an `UNREACHABLE` entry that matches no handler FAILS (a stale exemption is an open door).
- Keys use the handler's stripped source line, not a line number (line numbers drift).
- The test's docstring records the ordering fact (R40): with disjoint classes, clause order is inert; order becomes load-bearing only if `SchwabSchemaParityError` is ever re-based under `SchwabApiError`, which F-F2 refused.
- RED-first: on the pre-fix tree the test FAILS listing rows 5, 6, 11, 12, 13, 17, 18 (seven sites neither widened nor covered nor exempt). Post-fix: passes. Two synthetic checks inside the test (the walker is not vacuous): a parsed string with a 19th `except SchwabApiError:` in a new function is flagged; a parsed `try: ... except SchwabApiError: ... except Exception: ...` is flagged (a broad tail does not cover).

### T-B2 -- rows 5, 6, 13 widened (`cli_schwab.py:1478/:1490`, `pipeline_steps.py:266`)
| test | drive | pre-fix | post-fix |
|---|---|---|---|
| B2-a | `_step_schwab_snapshot` with `get_account_details` raising parity | parity escapes | returns `status="failed"`, `error` starts `SchwabSchemaParityError:` |
| B2-b | CliRunner `swing schwab fetch --snapshot` (production cfg, stub client) with `get_account_details` raising parity | traceback, exit 1 | exit 0 with the snapshot step reported `failed` (row 13 contains it; row 5 is the belt) |
| B2-c | `swing schwab fetch --snapshot` with `swing.integrations.schwab.pipeline_steps._step_schwab_snapshot` monkeypatched (a counting wrapper, asserted called once) to raise parity (the belt, row 5); `schwab_fetch` imports it FUNCTION-LOCALLY (`cli_schwab.py:1463-1466`), so the module attribute is read per call | traceback | exit 1, `Error: Snapshot step failed: ...` no traceback |
| B2-d | same for orders (row 6) | traceback | typed |

### T-B3 -- the `ReservedJournalFieldError` closure (CHARC F-F2 RJFE) -- `tests/cli/test_22f_reserved_field_closure.py`
- Static half: in `swing/trades/reconciliation_auto_correct.py`, compute the public (no leading `_`) functions from which a `raise ReservedJournalFieldError`/`MultiRowCorrectionOverrideError` is reachable through the module's own call graph (name resolution within the module, including the `_TIER2_HANDLERS` registry values, the census instrument's rule). Then enumerate every call site of those public functions in `swing/cli*.py` and `swing/web/routes/*.py`; each must sit inside a `Try` with a handler naming the type (or a base below `Exception` -- none exists, so by name), or be listed in an exemption map with a reason. RED-first: fails on the two CLI commands (and the web route if T-A5's read found it uncaught).
- Behavioural half: A5-a..A5-e are the per-root execution proof (brief §4 (5)).

### T-B4 -- rows 11, 12 widened (`marketdata_ladder.py:337`, `:469`; CHARC R1-gate 1, R41)
**Fix:** add `SchwabSchemaParityError` to both tuples (import from `swing.integrations.schwab.client`, the module's existing import block at `:64`); each widened `log.warning` carries `exc` beside the type: `"... for %s (%s: %s); falling back to yfinance", ticker, type(exc).__name__, exc`. Safe to log: `SchwabApiError.__str__` (`client.py:360-377`, status + body byte-count only) and `_RedactedMessageError.__str__` (`client.py:345-346`, `_redact_message`) are both engineered redacted, and the broad clause below has logged `exc` for months. Fallback behaviour unchanged.
| test | drive | pre-fix | post-fix |
|---|---|---|---|
| B4-a | `fetch_quote_via_ladder` with `swing.integrations.schwab.marketdata_ladder.get_quotes_batch` (bound by the module-level import at `:70-71`; B4-b patches `...marketdata_ladder.get_price_history` the same way) replaced by a counting wrapper, asserted called once, raising `SchwabSchemaParityError("<quotes: missing required key 'x'>")` | returns the yfinance entry; the ONE warning record is the broad clause's (`unexpected error from T-C.1 wrapper`) | returns the yfinance entry, source `"yfinance"`; the warning record is the NAMED clause's (`Schwab market-data quote fetch failed`) and contains `SchwabSchemaParityError` AND `str(exc)`; no `unexpected error` record |
| B4-b | `fetch_window_via_ladder`, price-history wrapper raising parity | yfinance window; broad-clause record | yfinance window persisted as today; the named clause's record (`Schwab price_history failed`) with type and `str(exc)` |
| B4-c | CONTROL: `SchwabApiError(500, "x")` on each | named clause, type only | named clause, message contains `SchwabApiError(status=500, body=<1 bytes>)`; fallback unchanged |
| B4-d | CONTROL: a planted `RuntimeError("boom")` | broad clause | broad clause, unchanged |

---

## 4. PART C -- F-F7 `SchemaVersionMismatchError` (C1-14)

### T-C1 -- web, `swing/web/app.py:_register_exception_handlers` (S-503)
**Fix:** register `@app.exception_handler(SchemaVersionMismatchError)` inside `_register_exception_handlers` (Starlette resolves the most-specific class; the `Exception` handler stays): render `error.html.j2` (HTMX: `partials/error_fragment.html.j2`; row target: `trade_form_error.html.j2` -- mirror `_handle_any`'s three-way branch) with `error_message=str(exc)` at **503**; log at ERROR once.
| test | drive | pre-fix | post-fix |
|---|---|---|---|
| C1-a | `with TestClient(create_app(cfg)) as c:` then set the DB's `schema_version` to 40 (raw sqlite3, after the app started -- the "migrated under a running server" shape reversed; any mismatch triggers) and `GET /journal` | **500**, generic page | **503**, body contains `swing db-migrate` |
| C1-b | same, HTMX header | 500 fragment | 503 fragment with the message |
| C1-c | CONTROL: `GET /journal` on a current DB | 200 | 200 |
| C1-d | CONTROL: an unrelated `RuntimeError` planted in a route | 500 | 500 (the generic handler still owns it) |

### T-C2 -- CLI, a `click.Group` subclass in `swing/cli.py` (S-GROUP)
**Fix:** `class _SchemaGuardGroup(click.Group)` with `invoke(self, ctx)` = `try: return super().invoke(ctx) except SchemaVersionMismatchError as exc: raise click.ClickException(ascii_safe(str(exc))) from exc`; `@click.group(cls=_SchemaGuardGroup)` on `main` (`cli.py:218`). Catches ONLY that type. Sub-groups inherit nothing (the exception propagates through `main.invoke` because Click's nested group invocation runs inside the root's `invoke`) -- test C2-b proves it for a nested group command.
| test | drive | pre-fix | post-fix |
|---|---|---|---|
| C2-a | CliRunner `trade list` (a `connect()`-bearing command; verify it calls `connect`) against a fixture DB at version 40 | `result.exception` is `SchemaVersionMismatchError`, traceback in `exc_info` | exit **1**, output `Error: ...swing db-migrate`, `result.exception` is `SystemExit` |
| C2-b | a nested-group command, e.g. `journal cash-void` args against the v40 fixture | traceback | exit 1 typed |
| C2-c | CliRunner `db-migrate` against a stale fixture (a fresh DB migrated to `target_version=40` via the migration test helper) | migrates to 41 | **still migrates to 41**, exit 0 (R29) |
| C2-d | CONTROL: a command raising `ValueError` escapes as before | traceback | traceback (the group catches nothing else) |
| C2-e | missing DB file (`connect` raises the same type, `db.py:1088`) | traceback | exit 1, `Run: swing db-migrate` |

---

## 5. PART D -- F-F4: declared classes, their write-side constraints, one LOUD pin each

| class | members | write-side constraint (quoted) | LOUD pin |
|---|---|---|---|
| **INV-MODEL (persisted-row subset)** (of 2446 triples = 516 distinct raise origins in 118 functions, measured from `triage.json`) | the roster members of T-D0 whose object is built from a DB row | PER MEMBER, the quoted CHECK or trigger it mirrors (gotcha #11), recorded in the exec ledger by T-D0; a persisted-row member with NO CHECK/trigger is not declared -- it goes to §11 FND-3 by name. Exemplar: `fills.fill_origin` `CHECK (fill_origin IN (` (`0020_phase13_charts_patterns_autofill_usability.sql:395`) mirrored by `Fill.__post_init__` `if self.fill_origin not in _FILL_ORIGIN_VALUES: raise ValueError(` (`swing/data/models.py:447-448`) | T-D1 (loudness pin for the persisted subset) |
| (NOT DECLARED) **INV-COMPUTED** | the roster's SERVER-COMPUTED members (view models, `metrics/*`, `config`, e.g. `r_multiple:33`, `PriceCache.get_many:360`, `replay_verdict:1309`, `net_cash_movements:33`, `metrics.honesty` guards) | none exists -- no schema constrains a computed value | **§11 FND-4**, listed by name from the T-D0 roster with the roster search (CHARC F-F4 (2)'s own clause, R1-03) |
| **INV-TYPE (caller-constant)** | `honesty._z_for_alpha:188` (alpha), `honesty.wilson_ci:147` (int k/n), `latched_origin._probe_guard_block:2331` | the constant/typed argument at every caller, each caller line quoted in the exec ledger (R46). A caller passing a NON-constant moves the member OUT of the declarable set -- into FND-4's roster (a named §11 row) or a conversion task (a typed translation at the reaching root) -- never a footnote | T-D2 |
| **PROG-TX** (`CallerHeld*`, 9 classes, 35 triples; C1-22) | `record_entry:1298`, `audit_service:154/:227/:300`, `pipeline_steps:164/:443`, `record_snapshot:96`, `update_hypothesis_status_with_audit:170`, `resolve_discrepancy:642`, `run_tos_reconciliation:293`, `resolve_out_of_framework_orphans:1652` | each operator root opens its own connection with a fresh `connect()` and holds no transaction when calling (execution cites the root's `connect` line per class member) | T-D3 |
| **C1-13 assign invariants** | `EnvelopeReadingMissingError` (`entry_intent_assignment.py:424`), `_set_trades_value` `RuntimeError` (`:608`), `LatchProbeInvariantError` (`latched_origin.py:2310,2515`) | SERVICE-prevented within one `BEGIN IMMEDIATE` (`entry_intent_assignment.py:641`): `ensure_entry_fill_identities` runs first (`:643`); `preflight` re-runs inside it; the probe's forced rung and horizon bound (`latched_origin.py:2302-2308`, `:2511-2513`). Service-prevention is WEAKER than schema-prevention; live incidence NOT measured (this cell does not open the live DB) -- the execution cell measures on a backup-API copy or the item goes to §11 | T-D4 |

### T-D0 -- the INV-MODEL roster and its AST closure (R1-03, R52; §1.2 row 11) -- `tests/data/test_22f_inv_model_roster.py`
- **Input, pinned (R2-01):** `C:\Users\rwsmy\swing-data\review-transcripts\22-f-plan\r0-measurements\triage.json`, sha256 `b18eb936b1ffe4bb81595aa16768351449915295ecc7f7f78c9158fde955cb13`. It lives in the durable evidence dir, NOT the checkout. The executing cell's FIRST step hashes the file's BYTES and STOPS on a mismatch; the derivation runs only on the pinned bytes. The derived roster and the `UNREACHED` map are then COMMITTED into the test module, so the landed test reads nothing outside the repository.
- **Roster (test data, committed in the test module):** the 118 distinct origin functions of the INV-MODEL triples in the pinned `triage.json` (read with `encoding="utf-8"`), each as `dotted.name: "persisted" | "computed"` -- `persisted` when the object is built from a DB row (a `_row_to_*` mapper or a repo reader constructs it), `computed` otherwise. The classification is a READ per member, recorded in the exec ledger with the constructing line.
- **Per-member citation:** every `persisted` member gets its quoted CHECK or trigger (migration file:line + the Python mirror line) in the exec ledger; a `persisted` member with none -> §11 FND-3 by name. Every `computed` member -> §11 FND-4 by name.
- **Closure (both directions):** an AST walk over `swing/**/*.py` computes P = every module- or class-level function named `__post_init__`/`_require_*`/`_validate_*` whose body contains a `Raise`. Assert P == (roster members matching the pattern) UNION `UNREACHED` (a committed exclusion map, 53 entries today, each reason "no operator root reaches it in the census call graph (`escape_census.py`)"), and every roster and `UNREACHED` key resolves to a real function (a stale entry FAILS). The 3 roster members named by `triage.py:8` rather than by the pattern (`_provenance_snapshot_dict`, `_check_finite`, `worst_of`) are carried by name and checked for existence only. A NEW raising validator lands in neither list -> RED, and its author must classify it.
- **Declared bound (limit, not an exemption):** the `UNREACHED` reasons are verified by the census instrument at commit time, not by the test (the call-graph walker lives outside the repo); the test proves membership, not reachability.
- Counts: 168 (P), 118 (roster), 115 (overlap), 53 (`UNREACHED`), measured by the method in §1.2 row 11; the execution cell re-measures on its base and reconciles any difference line by line in the ledger before committing.

### T-D1 -- INV-MODEL pin
Plant, under `PRAGMA ignore_check_constraints = ON` on a raw `sqlite3` connection to a test DB, a `fills` row with `fill_origin='bogus'` on a seeded closed trade; `GET /journal/trades/{id}` (execution verifies this route builds `Fill` models; else pick the route that does and record it). Pre and post: **500**, body contains `fill_origin must be one of`. The pin asserts loudness; it passes on both trees by design and is labelled a PIN, not a discriminator. Its falsifier (proving it can fail): a mutation that wraps the reader in `except ValueError: pass` turns it RED -- run once, recorded in the commit message.

### T-D2 -- INV-TYPE pin: call `wilson_ci(k=1, n=2, alpha=0.10)` (keyword-only signature, `honesty.py:132`); asserts `NotImplementedError` naming `alpha=0.05`.
### T-D3 -- PROG-TX pin: `record_snapshot(conn, ...)` with `conn.execute("BEGIN")` held -> `CallerHeldTransactionError`; a CliRunner-level variant is not constructible (roots open fresh connections -- that IS the constraint).
### T-D4 -- C1-13 pin: `_set_trades_value` on a trade whose `entry_intent` is already non-NULL (raw planted) -> `RuntimeError` with `touched 0 rows`; nothing committed on a fresh read.

### T-D5 -- `NoActivePolicyError` CONVERTED (CHARC F-F4 (3))
**Step 0:** prove the command the message will name ACTUALLY repairs a no-active-policy DB: on a test DB with `UPDATE risk_policy SET is_active = 0` (raw), run `swing config policy import-from-toml` (CliRunner) and assert an active row exists afterwards. If it does not repair, STOP: the refusal would name an impossible action (the D35 class) -- return to the orchestrator for CHARC.
**Fix:** web: a typed handler for `NoActivePolicyError` in `_register_exception_handlers` (same three-way template branch as T-C1) at **503**, message = the error text + "Run: swing config policy import-from-toml" (ASCII) -- the page NAMES the config command that creates a policy (CHARC 3(a), R45), the one step 0 proved. CLI roots (`config policy show`, `discrepancy override-correction`, `discrepancy resolve-ambiguity`, and any other CLI caller the closure finds): S-CLICK with the same text.
**Closure test** (`tests/web/test_22f_no_active_policy_closure.py`): enumerate every call site of `get_active_policy` and of `swing.metrics.policy`'s wrapper (`metrics/policy.py:46`) and of `trades/risk_policy.py:223` in `swing/`; each must be inside a `Try` with a handler naming `NoActivePolicyError`, or be in an exemption map whose reason names the converting boundary ("web: app handler", "CLI: <command> ClickException"). The exemption map's CLI entries are verified by the behavioural tests below.
| test | drive | pre-fix | post-fix |
|---|---|---|---|
| D5-a..h | `GET` each of the 8 `/metrics/*` pages with no active policy | **500** | **503**, body contains `import-from-toml` |
| D5-i | CliRunner `config policy show`, no active policy | traceback | exit 1 typed |
| D5-j | override-correction / resolve-ambiguity reaching `:108` | traceback | typed |
| D5-k | PRECEDENCE PIN (R45): `POST /config` with no active policy, reaching `routes/config.py:154`'s `except NoActivePolicyError: active_now = None` (and its twin `:236` on `POST /config/reset/{field}`) | the route's own response (its status and body marker, recorded at G1) | the same status and body marker; the status is not 503 and the body is not the app handler's error page (its template marker) -- the app-level handler cannot shadow the route's local handling |

---

## 6. PART E -- F-F5: `ascii_safe` on exception-text `ClickException`s

**Premise, CORRECTED (CHARC F-F5 (1)):** `cli.py:22-30` reconfigures stdout/stderr to UTF-8 `errors="replace"` inside `try/except (AttributeError, io.UnsupportedOperation)`, and the `except` branch PRESERVES the original encoding on embedded consoles and non-`TextIOWrapper` streams. So the encode-side crash is unreachable where reconfigure works and REACHABLE where it does not; "mojibake, not a crash" is a property of the console, not of the code. The fix is uniform.

### T-E1 -- the closure test FIRST (RED), `tests/cli/test_22f_clickexception_ascii_closure.py`
- Over `swing/cli.py`, `cli_schwab.py`, `cli_config.py`, `cli_latches.py` (utf-8): for every `Call` whose func is `click.ClickException`/`ClickException`, walk its arguments; a **tainted leaf** is (a) a `Name` bound by an enclosing `ExceptHandler ... as <name>`, or (b) an `Attribute` whose `attr == "message"`. Every tainted leaf must have an ancestor (inside the argument) that is a `Call` to `ascii_safe` or `safe_text`. Violations are reported as `path:line: <argument source>`.
- **Declared bound (limit, not an exemption):** a message assembled into a local variable before the call is not seen (census 3.4); the test also flags any `ClickException(<Name>)` whose `Name` was assigned from an f-string/`str()` containing a tainted leaf in the same function (one-level local-assignment follow), which closes the common case.
- RED-first: fails listing the 98 sites of `clickexc_7a.tsv` (the census roster; the test's own count is recorded in the commit -- if it differs from 98, both lists are reconciled line by line in the ledger before T-E2).
- Behavioural discriminators (R3-1 form, `64bae976`): `trade assign-intent` with `--reason "x \u2192 y \udc80"` driving the `:1935-1936` `ValueError` path and the `:1950` refused path: build the `Error:` line (`"Error: " + exc.format_message()`) and assert `.encode("cp1252")` succeeds. Pre-fix: `UnicodeEncodeError` (U+2192 and a lone surrogate are outside cp1252). Post-fix: encodes. (Input chosen OUTSIDE cp1252 -- cp1252 encodes the em-dash, `ascii_safe`'s docstring `entry.py:66-75`.)

### T-E2 -- the fix, per module, one commit each (cli.py; cli_schwab.py; cli_config.py; cli_latches.py)
Wrap each tainted leaf: `ascii_safe(str(exc))` / `ascii_safe(result.message)` (import `from swing.trades.entry import ascii_safe` at function scope, the existing idiom at `cli.py:1621`). `cli_config.py:353` `{raw!r}` is wrapped too (`repr` keeps printable non-ASCII). GREEN = T-E1 passes; the named candidates' existing tests stay green byte-for-byte on ASCII input.

---

## 7. PART F -- class 2 (D39): the explicit BEGIN sites (S-D39)

**Common test shape per SITE (the both-verbs-fail proxy, brief §4 (3)):** a `FailingVerbsConn` that raises on the site's first write statement (`fail_sql_prefix` = the INSERT/UPDATE the service issues first after BEGIN; the execution cell reads it) AND on `rollback()`/`execute("ROLLBACK")`.
- **Per SITE, not per row (SS-3):** every BEGIN/cleanup pair a row lists gets its own parametrized case (e.g. C2-09's four `audit_service.py` pairs, C2-01's `:889/:908`, `:965/:1083`, `:1106/:1119`).
- **In-try refusal-branch ROLLBACKs are sites too (SS-4):** a ROLLBACK issued between BEGIN and the handler on a refusal branch (the `entry_intent_assignment.py:644/:654` class; also `hypothesis.py:199`, `:205`, `:211` -- not-found, no-op, illegal transition) is driven by its OWN refusal input with the proxy failing `rollback()` once (single failure) and twice (double failure). Pre-fix: the double failure raises the handler's cleanup error with `__cause__` None and no record (the "unguarded" column below). Post-fix: that error is raised from the refusal-branch error, with one `MUST BE DISCARDED` record; a single failure re-raises the refusal-branch error. The executing cell enumerates each site's in-try ROLLBACKs by READING its try body and records the list per row in the exec ledger.
- **Delivery (SS-1):** a service taking `conn` receives the proxy as its argument; a CLI/web root receives it through `patch_conn_opener` at the target §0.4 names for that module; every case asserts the proxy recorded the failing verb (the did-it-fire rule).
| assertion | pre-fix (suppressed row) | pre-fix (unguarded row) | post-fix |
|---|---|---|---|
| raised exception | the WRITE error | the CLEANUP error, `__cause__ is None` (implicit `__context__` only) | the CLEANUP error |
| `exc.__cause__` | None | None | the WRITE error |
| ERROR record containing `MUST BE DISCARDED` | absent | absent | present, once |
| F2 twin: write verb raises `KeyboardInterrupt`, rollback works | `conn.in_transaction` True after (the `except Exception` does not run) | same | False (rolled back), `KeyboardInterrupt` re-raised |
| F1 twin (rows marked F1): BEGIN inside the `try`, asserted by the F2 twin reaching the rollback | -- | -- | covered by the F2 twin |
| CONTROL: write succeeds | commit | commit | commit, byte-identical rows on a fresh read |

| task | rows | files | notes |
|---|---|---|---|
| T-F1 | C2-01, C2-02, C2-03, C2-04 | `reconciliation_auto_correct.py:889/:908`, `:965/:1083`, `:1106/:1119`, `:752`, `:1142` | C2-04 has no production caller: fixed for uniformity, tested by direct call (decision recorded; the census left it to the plan) |
| T-F2 | C2-05 | `cli.py:4588/:4597` resolve-ambiguity `linked_correction` envelope | CLI-level proxy via `patch_conn_opener(..., "swing.data.db.connect", ...)` -- correct for this root: `discrepancy resolve-ambiguity` imports `connect` function-locally (§0.4 measurement); the case asserts the proxy recorded the failing verb |
| T-F3 | C2-06 | `reconciliation.py:418/:594`, `:669/:730` | |
| T-F4 | C2-07 | `entry_date_correction.py:1365/:1380` | |
| T-F5 | C2-08 | `schwab_reconciliation.py:1843` run tx (`:2773`, `:2794`) + the 7 `ROLLBACK TO SAVEPOINT` suppress sites (`:1175,1247,1263,1275,1295,1325,1330`) | **Savepoint facet:** a suppressed failed `ROLLBACK TO` lets the discrepancy's partial mutation COMMIT with the outer run (gotcha: SAVEPOINT-per-discrepancy). Fix: the savepoint rollback's failure is raised CHAINED from the per-discrepancy error (no suppress), so the OUTER template rolls the whole run back and logs discard. Extra discriminator, PARAMETRIZED over ALL SEVEN `ROLLBACK TO` sites (SS-5; each case driven by the discrepancy branch that reaches THAT site, read and recorded per site by the executing cell; a site no input reaches is recorded with the read, never silently dropped): proxy failing that discrepancy's write AND its `ROLLBACK TO` -> pre: the run COMMITS and a FRESH read shows the partial mutation; post: the run raises and a fresh read shows none of the run's rows. Behaviour change bounded to the double-failure case (declared in the commit) |
| T-F6 | C2-09 | `audit_service.py:164/:184,:187`; `:237/:259,:262`; `:307/:319`; `:367/:376` | not carve-out-governed |
| T-F7 | C2-10, C2-11, C2-12, C2-13, C2-14 (`:132` only) | `yfinance_audit.py:118/:127`, `:158/:167`; `account_equity_snapshots.py:133/:148`; `daily_management.py:823/:935`; `hypothesis.py:187/:284` (+ the three re-raise rollbacks `:199,:205,:211`); `risk_policy.py:132/:212` | one commit per file; C2-14 `:407` DECLARED (no caller) |
| T-F8 | C2-15, C2-16, C2-17 | `repos/review_log.py:248/:359`; `entry_intent_assignment.py:640/:644,:654,:668`; `diagnostics/backfill_trades_sector_industry.py:115/:130` | §1.2 row 3. **C2-16 (A-3 CONFIRMED, R44; §1.2 row 12): F3 on every ROLLBACK of `assign`'s one try.** The cleanup at `:667-668` becomes S-D39 (`try: conn.execute("ROLLBACK") except BaseException as cleanup_error: log_contained_note(... "MUST BE DISCARDED" ...); raise cleanup_error from <original>`). The in-try ROLLBACKs at `:644` and `:654` are NOT wrapped individually: a failure there IS the original error, enters the same handler, which re-reads `in_transaction` and attempts the cleanup ROLLBACK. **What the operator hears on the double failure** (in-try ROLLBACK raises E1, cleanup ROLLBACK raises E2): E2, with `__cause__` = E1 and one ERROR record `MUST BE DISCARDED`; via `trade assign-intent` that is a traceback, because `cli.py:1935` catches only `ValueError` and E2 is a `sqlite3` error (the class-2 posture: the cleanup error is raised, never the original alone). If the in-try ROLLBACK fails but the cleanup succeeds: E1 re-raised (today's behaviour). Tests: the proxy fails `execute("ROLLBACK")` on its first call only (single failure) and on both calls (double failure), driven through each of `:644` (identity drift planted), `:654` (a `dry_run=True` call) and a planted write error (the cleanup path); CONTROL: the success path's `assign` result equal pre/post. The COMMIT at `:665` and its position (RULING R7) are NOT moved; if the fix cannot avoid touching R7's shape, STOP and route to CHARC |
| T-F9 | S8 item 8 (A-2 GRANTED, R43) | `cohort_provenance_correction.py:2388-2419`, `:3547-3560` | MESSAGE TRUTH only, no control-flow change, the chained raise stays. Each message states what was observed: the rollback raised `<cleanup_error>`; then it RE-READS `conn.in_transaction` after the failure and reports THAT value: "... could not roll back (%s); `in_transaction` reads %s after the failed rollback; this connection MUST BE DISCARDED either way." Tests per site: a still-open posture (rollback raises, tx open) -> message contains `in_transaction reads True`; a took-effect-then-raised posture (a proxy that performs the real rollback then raises, modeled on `_RollbackAfterEffect`, `tests/trades/test_22a_task9_entry_wiring.py:3082`) -> pre: "STILL OPEN" (false); post: `in_transaction reads False`; both postures contain `MUST BE DISCARDED` and re-raise the cleanup error chained from the original |
| T-F10 | C2-21 | `db.py:576` `_apply_migration` rollback (S-D39) + **B-04** (the post-`COMMIT` `finally` PRAGMA restores at `db.py:579-585`) | **C2-21's OWN site (R3-02).** Fix: `_apply_migration`'s `except Exception: conn.rollback(); raise` (`db.py:572-577`) becomes S-D39 (`except BaseException as exc:`; `if conn.in_transaction:` rollback under `except BaseException as cleanup_error:` -> `log_contained_note(... "MUST BE DISCARDED" ...)`, `raise cleanup_error from exc`; then `raise`). Instrument: `open_connection_returning` (the name `ensure_schema` resolves, `db.py:1054`) with a proxy whose `executescript` first runs the real `executescript("BEGIN;")` (the migration scripts open their own transaction; this leaves one OPEN, as a mid-script failure does) and then raises; drive `ensure_schema` on a v40 fixture. **C2-21-a** both fail (`executescript` raises `sqlite3.OperationalError` E1; `rollback()` raises E2) -> pre: E2 escapes from inside the `except`, `__cause__ is None` (E1 only as implicit `__context__`), no `MUST BE DISCARDED` record; post: E2 raised, `__cause__ is E1`, exactly one record. **C2-21-b** F2 twin: `executescript` raises `KeyboardInterrupt` after the BEGIN, rollback works -> pre: `except Exception` does not run, so the proxy's `in_transaction` is True after the raise (the `finally` PRAGMAs are no-ops inside a transaction); post: `in_transaction` False (rolled back) and `KeyboardInterrupt` re-raised. **C2-21-c** single failure (E1, rollback works) -> E1 re-raised, fresh read `schema_version` 40, on BOTH trees (a PIN). **C2-21-d** CONTROL: pass-through proxy -> migrated to 41, on both trees. Every case asserts the proxy recorded >= 1 `executescript` (and a-c >= 1 `rollback()` attempt where the table says one runs). These stop before the post-COMMIT `finally`, which is B-04's. **B-04 fix (R1-02, R51), the boundary is `cli.py db_migrate`:** wrap `conn = ensure_schema(...)` (`cli.py:354`) in `except BaseException as exc:`; re-read `schema_version` on a FRESH plain-`sqlite3` read-only connection (`sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`, closed in its own `finally`; never `swing`'s `connect`); if it equals `EXPECTED_SCHEMA_VERSION` -> emit `WARN: the migration IS applied (schema version <v>); a post-commit step failed: <safe_text(exc)>` via `_echo_either_sink(..., prefer_err=True)`, then open a fresh `open_connection(db_path)` and CONTINUE the existing tail (gate-image check, the single-fire v17 ratification, the final echo; §1.2 row 13), exit 0 only if the tail completes; else (version below target, or the re-read itself fails) re-raise `exc`. Instrument: `open_connection_returning(lambda real: FailingVerbsConn(real, fail_after_executescript=("PRAGMA foreign_keys=", n)))` (§0.4), `n` = the number of migrations the fixture applies (the restore of the LAST one, so the version reaches target); every B-04 case asserts the proxy recorded the failing `PRAGMA foreign_keys=` (B-04-c: the failing script) -- the did-it-fire rule. Tests: **B-04-a** v40 fixture, `n=1` -> pre: exit != 0, traceback, a fresh read shows 41; post: exit 0, the WARN line, fresh read 41, the final `DB at ... - schema version 41` line printed. **B-04-b** the restore failure on the FIRST of two migrations (v39 fixture, `n=1`) -> the chain stops below target -> post: re-raised, exit != 0 (the re-raise branch). **B-04-c** CONTROL: a raise BEFORE the COMMIT (a proxy failing the script) -> exit != 0, version unchanged, no WARN. **B-04-d** tail continuation: a v16 fixture, `n` = the count of migrations 17..41 (the LAST restore fails), a spy on `swing.trades.risk_policy.ratify_seed_from_cfg_on_v17_landing` (imported at call time inside `db_migrate`, so the module attribute is the one resolved) -> pre: never called (the raise escapes first); post: called exactly once, and the WARN line precedes the final echo. The B-04 compensating control (the witness reads `schema_version`, never the exit code) stays binding until this merges |
| T-F11 | C2-22 | `cli.py` `trade entry` close handler, the pre-boundary branch (`result is None`) | READ `cli.py:960-1100` for the close handler; the proxy arrives through `patch_conn_opener` at `swing.data.db.connect` (`trade entry` imports `connect` function-locally, section 0.4) and the case asserts >= 1 `close()` recorded; RED: a typed pre-boundary refusal (e.g. `DuplicateOpenPositionError` -> its ClickException) with `close()` failing -> pre: the close error replaces the refusal text; post (S-R8): output contains the refusal text AND `the connection close also failed`, `__cause__` is the close error, exit 1, nothing written (fresh read) |

---

## 8. PART G -- F4 close-after-durable (41 operator-record roots; 17 read/cache roots)

### T-G0 -- two helpers, in EXISTING modules
- CLI: `swing/cli.py::_close_after_writes(conn, *, durable: bool, pending_refusal: click.ClickException | None) -> None` -- S-B02 exactly: nothing durable and no refusal -> bare `conn.close()` (byte-unchanged); refusal in flight -> S-R8; durable and no refusal -> `log_contained` + `_echo_either_sink("WARN: the write IS recorded; the connection close failed: " + safe_text(exc), prefer_err=True)`, return normally (exit 0). `cli_schwab.py`/`cli_config.py` import it at function scope (no module-level cycle).
- Web: `swing/web/routes/__init__.py::close_after_commit(conn, log, *, what: str) -> str | None` -- closes; on failure `log_contained` (ERROR) and returns the one-line notice text `"<what> IS recorded; the database connection could not be closed cleanly (see the log)."`; never raises.
- Unit tests for both helpers: each branch, with the closing proxy.

### T-G1 -- the 25 CLI roots (one commit per group; the `durable` flag bound at each writer's OWN return, never cached)
`trade exit` (`cli.py:1170`), `trade stop-adjust` (`:1261`), `journal cash/oof-buy/cash-void/correct-entry-date/correct-cohort-provenance/reconcile-tos` (`:2589,:2808,:3002,:3141,:3423,:3601`), `discrepancy resolve-ambiguity/override-correction/resolve` (`:4618,:4938,:5112`), `tos-import` (`:5254`), `pipeline force-clear` (`:5419`), `hypothesis update` (`:5651`), `finviz fetch` (`:5719`), `account snapshot` (`:5827`), `config set/reset`, `policy set/import-from-toml` (`cli_config.py:193,275,482,555`), `schwab resolve-out-of-framework/fetch/setup/refresh/logout` (`cli_schwab.py:1058,1512,211,311,379`).
**Per root, three tests (parametrized over a root table in `tests/cli/test_22f_close_after_durable.py`; each row carries its opener `target`, read from the root's source -- today: `pipeline force-clear` -> `swing.cli.connect`; the five `schwab` roots -> `swing.cli_schwab.connect`; every other root here -> `swing.data.db.connect` (function-local imports; section 0.4)):**
| test | drive | pre-fix | post-fix |
|---|---|---|---|
| G1-a | the root's success path; `patch_conn_opener` at the root's `target` (the root table column, from the section 0.4 measurement) returns `FailingVerbsConn(fail_close=True)`; asserts the proxy recorded >= 1 `close()` | exit **!= 0** (close raise escapes `finally`), traceback; write durable (fresh read) | exit **0**, `WARN: the write IS recorded`, write durable |
| G1-b | the root's typed refusal path + close failure (roots that have one) | the close error REPLACES the refusal text | refusal text + `the connection close also failed`, chained, exit 1, nothing written |
| G1-c | CONTROL: nothing durable, no refusal, close fails | traceback | traceback (byte-unchanged branch) |
Roots whose try body turns out on READ to write nothing durable move to T-G3 with the read cited.

### T-G2 -- the 16 web POST roots
`/account/snapshot` (`account.py:171`), `/config` (`config.py:186`), `/config/reset` (`:265`), `/latches/intent`, `/latches/orders`, `/latches/view` (`latches.py:1319,242,374`), `/patterns/exemplars/{id}/action` (`patterns.py:176`), `POST /patterns/{id}/review` (`:609`), `/pipeline/force-clear` (`pipeline.py:287`), `/reconcile/.../resolve` (`reconcile.py:1768`), `/trades/{id}/stop` (`trades.py:3303`), `/trades/{id}/review` (`:3688`), `/trades/{id}/daily-management/event` (`:4047`), `/watchlist/{ticker}/pin` (`watchlist.py:274`), `/dashboard/weather-chart/refresh` (`dashboard.py:176`); `/trades/{id}/exit` is T-A7. **Opener target per root (section 0.4):** `account`, `config` (both), `reconcile`, `watchlist` -> `<module>.open_connection`; `latches` (three), `patterns` (two), `pipeline`, `dashboard`, `trades` stop/daily-management -> `<module>.connect`; `POST /trades/{id}/review` -> `swing.data.db.connect` (`review_post` imports it locally).
| test | drive | pre-fix | post-fix |
|---|---|---|---|
| G2-a | success path, `patch_conn_opener` at the root's `target` (section 0.4: `<module>.connect`, `<module>.open_connection`, or `swing.data.db.connect` for `review_post`) -> `FailingVerbsConn(fail_close=True)`; asserts >= 1 `close()` recorded | **500** over a durable write | the route's own success status (200/204/303 as today); fresh read shows the write; one ERROR record; a body-bearing HTML response contains the helper's notice |
| G2-b | CONTROL: close fails with nothing written (the route's own 4xx path) | 500 | 500 unchanged (nothing durable; the app handler is correct) |

### T-G3 -- the 17 read/cache roots: DECLARED (R21, CHARC 3(c)), confirmed per root by READ
**The discriminator (CHARC's statement of record, R2 gate; it replaces his R1-gate "no durable write"):** a close-after-commit failure never loses data on ANY root, because the commit is already durable; what differs is what the operator DOES with the error. After a read or an audit/cache commit, a spurious failure report costs a retried read. After an operator-record write, the same report tells the operator the write failed and invites a retry against a durable row -- the D68 class. That is the line between DECLARED and CONVERTED. So the per-root read confirms exactly one thing -- that the root writes no OPERATOR RECORD -- and a read root found to write one moves to the 41 (T-G1/T-G2). The counts 41/17 replace the census's 32/26 (§1.2 row 5, method there).
GET `/charts/{t}.png`, `/health/tool`, `/health/research`, `/journal/trades/{id}` (+`/thumbnail`, `/chart`), `/patterns/{id}/review`, `/hyp-recs/refresh`, `/hyp-recs/{t}/expand`, `/trades/open/{id}/expand`, `/trades/{id}/review/chart`, `/trades/entry/sizing-hint`; CLI `eval`, `patterns label-exemplars`, `review-silver-with-codex`, `patterns-exemplars-backfill-labeler-evidence`, `diagnose prune-chart-cache`. **Per root the execution cell records in the ledger what the try body commits** (cache/audit rows only -> DECLARED with that citation; an operator record -> the root moves to T-G1/T-G2). No code change for a confirmed read root.

---

## 9. PART H + amendment requests

### T-H1 -- the AL-7 docstring (CHARC F-F6), ONE comment-only commit
Claims in `_resolve_affected_target`'s docstring (`reconciliation_auto_correct.py:2182-2192`) re-verified against `:2193-2205` AND each named symbol's consumers:
| claim | verdict by read | action |
|---|---|---|
| maps a discrepancy row to `(affected_table, affected_row_id)` per spec §5.4 step 2 | true of the code | keep (the spec citation is provenance; kept only if the executing cell finds §5.4 step 2 in the spec -- else drop the citation) |
| "Precedence (Codex R1 lock from C.B context)" | history, not code | drop the parenthetical; state the order |
| `fill_id` -> fills | true (`:2193`) | keep |
| `cash_movement_id` -> cash_movements | true (`:2195`) | keep |
| `equity_delta`/`snapshot_mismatch` -> `account_equity_snapshots`; "V1 returns the most recent matching row" | FALSE: no such branch | DELETE. Do not claim the snapshot table is unreachable elsewhere: `_read_journal_value` has an `_AFFECTED_TABLE_SNAPSHOTS` branch (`:2234`) -- the consumers of `_AFFECTED_TABLE_SNAPSHOTS` are grepped and counted in the commit message |
| `trade_id` -> trades | true (`:2197`) | keep |
| (unstated) raises `ValueError` when all three FKs are NULL | true (`:2199`) | ADD |
**Pre-commit gate:** `grep -rn "<each deleted docstring phrase>" tests/` empty (the clearance-attaches precondition), output in the commit message. `git diff --stat` shows the one file; an AST comparison of the module with docstrings stripped is identical (the commit states the method and that every changed line was read).

### Amendments (CHARC, R1-gate packet item 2 -- all three GRANTED; the text of record is the ledger block quote)
| id | file | status | bound | task |
|---|---|---|---|---|
| **A-1** | `swing/trades/exit.py` | GRANTED | the one price guard and its typed error (`ExitPriceRefusedError(ValueError)`); nothing else in the file moves | T-A6 |
| **A-2** | `swing/trades/cohort_provenance_correction.py` | GRANTED | message truth + the `in_transaction` re-read at `:2388-2419` and `:3547-3560`; no control-flow change | T-F9 |
| **A-3** | `swing/trades/entry_intent_assignment.py` | CONFIRMED | the D39 shape on `assign`'s ROLLBACKs (`:644`, `:654`, `:667-668`); R7's COMMIT at `:665` stays | T-F8 |

---

## 10. ACCEPTED LIMITATIONS (each with its reason; challenge explicitly invited -- a reason that does not hold is a finding)
AL-3 (removed: the ladder is WIDENED, R41), AL-4 and AL-5 (void: A-1 and A-2 granted), AL-8 (removed: T-D0 enumerates INV-MODEL, R52) were retired at the R1 gate; the ids are not reused.
| id | limitation | reason |
|---|---|---|
| AL-1 (k3) | a transaction leaked on a web route is assumed to die with its per-request connection; measured at `routes/latches.py:289-374` and `routes/trades.py:3133-3153` only | T-G2 converts every web write root's close; a leak can outlive the request only if a route shares a connection across requests, and `grep -rn "app.state.*conn\|global .*conn" swing/web` is the check the executing cell runs and records -- a hit becomes a task |
| AL-2 (k4) | no production stream was found that is non-reconfigurable AND cp1252-strict; the crash is not reproduced by execution | the fix (T-E) does not depend on it: `ascii_safe` is correct under every encoding, and CHARC's corrected premise makes the crash reachable where reconfigure fails; the discriminator is the R3-1 proxy |
| AL-6 | RD 1(iii): the exit POST re-render does not round-trip the submitted anchor (`routes/trades.py:3139`) | RD ruled it out of 22-F; the orchestrator's queue |
| AL-7 | web F4 routes whose success response carries no body (204/redirect) surface a close failure in the log only | the write is durable and nothing is operator-actionable; adding a notice channel to redirect responses is a UI change (22-G's lane) |
| AL-9 | the 58 implicit `with conn:` blocks are counted as a class, not rowed | sqlite3's context manager rolls back on any exception; its only facet is F3 (a raising rollback replacing the error with implicit chaining), and its connection-close boundary is the root's close, which Part G converts |

---

## 11. FINDINGS for CHARC's register (F-F4 (2): classes with NO write-side constraint -- NOT declared)
CHARC ACCEPTED FND-1, FND-2 and FND-4 as register rows (R1-gate 3(d)) and writes them at his next charter touch; this section lists them, it does not write the register.

| id | class | members | search that produced it |
|---|---|---|---|
| FND-1 | CONFIG-FILE-SHAPE | `config.load` `KeyError` (`config.py:791`, missing required section of the TRACKED `swing.config.toml`); `_normalize_out_of_framework_tickers` `TypeError` (`:387`, `:394`) on `POST /config/reset/{field_path}`, `config reset`, `policy import-from-toml` | `triage.json` INV-TYPE entries (6 origins), read; the user-config layer catches its twin (`config_overrides.apply_overrides`, docstring `config.py:783-787`), the tracked layer does not |
| FND-2 | INSTALL-STATE | `DecisionIntentsUnavailableError` import half (`latches/reader.py:274-279`) | read (§1.2 row 1) |
| FND-3 | (conditional) any PERSISTED-row INV-MODEL member, INV-TYPE member or C1-13 member whose write-side quote the execution cell cannot produce | named in the exec ledger when found | T-D0/T-D2/T-D4 reads |
| FND-4 | INV-COMPUTED: server-computed invariants with no write-side constraint (view models, `metrics/*`, `config`) -- 516 raise origins in 118 functions are the INV-MODEL roster; the `computed` members of it are this row | listed by name from T-D0's roster (`computed` classification), plus any INV-TYPE member moved out of the declarable set by a non-constant caller (R46) | `triage.json` INV-MODEL origins (distinct origin functions, utf-8 read) and the T-D0 per-member classification read |

---

## 12. Task order and commits
1. G1 baseline suite (count recorded). 2. T-B1, T-E1 closure tests land RED-first in the commits that fix them (never a red commit on the branch). 3. Part A (T-A1..T-A8). 4. T-B2, T-B3, T-B4. 5. Part C. 6. Part D (T-D0 first; T-D5 step 0 first within T-D5). 7. Part E. 8. Part F. 9. Part G (T-G0 first). 10. T-H1 alone in its commit. 11. **T-Z1 gate check:** `git diff 79035d59..HEAD --stat -- swing/` lists only envelope files (§0.3 + granted amendments); `git diff 79035d59..HEAD --name-status -- swing/ | grep '^A'` empty (no new module); no `migrations/` change; `pyproject.toml` unchanged; census §5's declared list re-read (R37). 12. G2 full suite + ruff. 13. Reviewer A (`strong`) to convergence. 14. G3 full suite on the final head. Commits conventional with the task id (`fix(web): T-A1 -- ...`), no trailers, no amend, no `--no-verify`.
