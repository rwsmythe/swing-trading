# Phase 22 arc 22-F: round-0 census (premise re-verification and fork packet)

**Cell:** 22-F writing-plans, ROUND 0 only. No Codex, no plan text, no code.
**Tree measured:** branch `22-f-plan` @ `79035d59` (main at dispatch; schema v41; 22-I merged at `530132d5`; D67/D69 at `8c4c65ad`).
**Rules read from main** @ `79035d59` by absolute path: `C:\Users\rwsmy\swing-trading\docs\implementer-dispatch-recipe.md` (section 3 plan-stage protocol, section 4, section 5) and `docs\harness-architecture.md` section 5 / 5.1.
**Authority:** `docs/phase22-arc-i-f-sweeps-commissioning-brief.md` (the brief) sections 0.2, 0.4, 1 "Handlers (22-F)", 2 items 7-11, 3 F-F1..F-F3, 4 "22-F", 5, 6; register rows D34, D35, D39, D46, D68, D69, D70 (`docs/tool-director-context.md` section 4); precedents in `docs/superpowers/plans/2026-09-23-phase22-arc-b-unintended-execution.exec-ledger.md` (RULING R1-3-SURFACES, RULING R8, R8-SCOPE, RULING B item 2 = B-02, B2-01).
**Evidence:** every instrument and its output is in `C:\Users\rwsmy\swing-data\review-transcripts\22-f-plan\r0-measurements\`. Row ids below (`C1-nn`, `C2-nn`) are stable for the plan.

---

## 0. How to read this census

A row is one of:

- **FIX.** An escape or transaction facet reachable on an operator path. It carries the ruled fix shape as a citation.
- **DECLARED.** Present in the code but not reachable from the operator path, or excluded by rule. It carries the reason.
- **FORK.** The fix needs a ruling. Section 6 lists these.

Each row also has a verification tag:

- **READ:** I read the raise site, the handler, and the path.
- **STATIC:** the instrument found a call chain and I did not read it. A STATIC row is unverified. The plan's first step for that row is a RED attempt: a row that cannot be driven RED becomes DECLARED-unreachable with the attempt as its evidence.

The manifest is complete to the instrument's limits (section 2). Per-row reading is PARTIAL: the READ rows are the ones listed. Section 3.3 and `cand.txt` list every STATIC candidate so that nothing is silently dropped.

---

## 1. Premise re-verification: section 1 deltas (the brief's numbers were seeds; each is re-measured here)

| # | Brief section 1 (seed, v40, `b8f80e91`) | Measured now (`79035d59`, v41) | Method, and its bound | Delta and why |
|---|---|---|---|---|
| 1 | 78 custom exception classes | **82** (81 at `b8f80e91`) | AST: every `ClassDef` in `swing/**/*.py` whose resolved MRO reaches builtin `BaseException` (`escape_census.py`, `exc.json`). Bound: classes built dynamically (`type(...)`) are not seen; none were found by grep. | +1 since the brief: `ReviewAlreadyCompletedError(ValueError)`, `swing/data/repos/review_log.py` (22-I). The brief's 78 does not reproduce at its own base (81); its method is not stated. By direct base: 27 `Exception`, 27 `RuntimeError`, 16 `ValueError`, 3 `_RedactedMessageError`, 3 `SchwabApiError`, 6 nested deeper (the brief said 26 / 27 / 13). |
| 2 | 38 `except (...)` tuple sites across `swing/web/routes/` + `swing/cli.py` | **32** (32 at `b8f80e91`) | AST `ExceptHandler` whose `type` is a `Tuple`, over those 16 files. A grep for `except\s*\(` gives 33. | The brief's 38 is not reproducible by either method. The modal tuple `(TypeError, ValueError)` ×19 **does** reproduce. With all four CLI modules the count is 37 tuple sites, `(TypeError, ValueError)` ×22. |
| 3 | 45 broad `except Exception`/`BaseException` | **46** (45 at `b8f80e91`) | AST: bare handler, `Exception`, or `BaseException`, same file set | +1 is the D69 rider's `except BaseException` in `trade backfill-intent` (`git diff b8f80e91..HEAD -- swing/cli.py`, one added line). |
| 4 | `swing/web/app.py:149` app-level `@app.exception_handler(Exception)` | **CONFIRMED** at `app.py:149` | read `app.py:148-178` | None. An escape renders `error.html.j2` (HTMX: `partials/error_fragment.html.j2`; row target: `trade_form_error.html.j2`) at **500** with `str(exc)` in the body. `HTTPException` is passed to the default handler. |
| 5 | CLI escape = traceback | **CONFIRMED**, with one qualifier | `pyproject.toml:64` `swing = "swing.cli:main"`; `main` is a plain `@click.group()` (`cli.py:218`); `grep 'cls=\|def invoke'` in `cli.py` finds 0 hits | Click standalone mode renders `ClickException` / `Abort` and nothing else, so any other exception is a traceback. **Qualifier:** `cli.py:22-24` reconfigures stdout and stderr to UTF-8 with `errors="replace"` at import. See 3.4 and fork F-F5. |
| 6 | CLI modules: `cli.py`, `cli_schwab.py`, `cli_config.py` | **FOUR**: plus `swing/cli_latches.py` (`swing latches parity`, registered at `cli.py:249`) | `grep add_command swing/`. 75 `@<group>.command` roots (AST) across the four modules and 18 groups. | The brief's operator-path list omits `cli_latches.py`. Its one command is in the census (`latches_group:parity`). |
| 7 | routes = every route in `swing/web/routes/` | **73 decorators, 72 handler functions** | `grep -E '^@router\.'` = 73; AST roots = 72 | `/` and `/dashboard` stack onto one function (`dashboard.py:44-46`). |
| 8 | `ReservedJournalFieldError`: 7 raise sites, 0 `except` | **CONFIRMED 7 / 0** | `grep -rn ReservedJournalFieldError swing` read line by line: raises at `reconciliation_auto_correct.py:357,381,399,447,523,537,2310`. The AST handler scan finds no handler naming it. | None. |
| 9 | `BEGIN IMMEDIATE` in 39 files, 157 occurrences, prose included | **158 in 40 `.py` files**, or 159 in 41 counting all file types (158 / 40 at `b8f80e91`) | literal `grep -rn 'BEGIN IMMEDIATE' swing` | +1 is 22-I's `0041` SQL text. **The string count is not the site count.** Only **31** executable `.execute("BEGIN...")` calls exist (AST, `tx_census.py`). Section 4 counts the SHAPE. |
| 10 | 17 rollback-in-`except` sites | **33 `.rollback()` calls; 28 inside an `except` handler**, plus 7 `ROLLBACK TO SAVEPOINT` executes under `suppress(sqlite3.Error)` | AST `rb_census.py`. `grep '\.rollback()'` = 36, including prose. | The brief's 17 is not reproducible, and its method is not stated. |
| 11 | D39's named sites "still carry the string" | They carry the string. Their SHAPE differs from the row's description; see 4.3 | read | `routes/latches.py:855,914` hold NO transaction. They are reads inside `try/except sqlite3.Error` that raise the typed `_GovernanceUnknownError`, so they have no D39 shape. `:364` is a `with conn:` block with a narrow `except sqlite3.Error`, which is a CLASS-1 shape (C1-15), not a CLASS-2 one. `cli.py:6722` is not a BEGIN line on any tree I read. `cli.py`'s one executable BEGIN is `:4588`. `schwab_reconciliation.py` "9 sites" = its **9 `contextlib.suppress(sqlite3.Error)` occurrences** (7 savepoint rollbacks + 2 transaction rollbacks). |
| 12 | Schema v40 | **v41** (22-I merged `530132d5`). 22-F touches no schema. | dispatch brief; `git log` | None for 22-F. |
| 13 | D69 `backfill-intent` open | **Owned by the D67/D69 rider, fixed @ `8c4c65ad`** | read `cli.py:2255-2296`: the close is wrapped `except BaseException`, a contained WARN goes through `log_contained`, and `safe_text`/`ascii_safe` is used (`cli.py:2242`, `SAFE`) | Not a 22-F target. |
| 14 | 22-I introduced `ReviewAlreadyCompletedError`, a CLI refusal, and a web 409 | **Both paths catch it**: CLI `cli.py:2387`, web `routes/trades.py:3820`. The instrument finds zero escapes of the type on any root. | handler AST + `roots.json` | CONFIRMED-HANDLED. It is a census row with no fix (C1-20). |

---

## 2. Method and limits (stated once; every count below inherits them)

- **CLASS-1 instrument:** `escape_census.py` + `roots_report.py`.
  - Parses all of `swing/` (utf-8).
  - Resolves calls by name: local and nested defs; `from m import f`; `mod.f`; `Class(...)` resolved to `__init__` and `__post_init__`; `self.`/`cls.` resolved through the class and its bases; `obj.m()` resolved only when exactly one swing method is named `m` (a common-name denylist applies); and dispatch registries (module-level containers of function names, called as `REG[k](...)`, `REG.get(k)(...)`, or a local bound from either — this is how the `_TIER2_HANDLERS` path at `reconciliation_auto_correct.py:1753` is followed).
  - An escape set is propagated to a fixpoint and filtered by every enclosing `try`, using the MRO. A re-raising handler passes its types through.
  - Output: one row per (root, type), with every terminal raise origin (`roots.json`, `origins.json`) and one witness chain.
  - **Limits:**
    - Implicit raises are not raise sites. That covers the sqlite CHECK or trigger aborts, `int(inf)`, stdlib and third-party raises.
    - Callables passed as arguments, executors and hooks are not followed.
    - Value flow is invisible. A guard in the caller that makes a raise unreachable is not seen: C1-10's `routes/trades.py:842` early check is the proof that the instrument over-reports.
    - A static chain is necessary for reachability and not sufficient.
- **CLASS-2 instruments:**
  - `tx_census.py` covers every `.execute/executescript` whose first argument is a string constant or f-string starting `BEGIN`. It measures facets F1-F4 on the AST and reverse-reaches the call graph to operator and pipeline roots.
  - `rb_census.py` covers every `.rollback()` (with its handler type and guard) and every operator root with a bare `finally: <x>.close()` whose try body reaches a `.commit()` or a `with conn:` block.
  - **Limits:**
    - Implicit deferred transactions from the default `isolation_level` and `with conn:` blocks are not sites. They are counted as a class: 58 `with <conn-name>:` blocks, name-bounded to `conn`/`connection`/`db`/`ro_conn`/`rw_conn`/`c`.
    - A transaction opened in one function and closed in another is reported at the opener.
    - The instrument's F3 label was WRONG once on read: `cli.py:4597` reads "chained" because an OUTER handler raises `from`. The inner rollback is unguarded. The READ correction is in C2-05.
- **Triage classes** (`triage.py`; the (root, type, origin) triples are counted in `triage.json`):
  - `ENV-SCHEMA` 225: `SchemaVersionMismatchError`.
  - `PROG-TX` 35: the `CallerHeld*` guards.
  - `INV-MODEL` 2446: origins in `__post_init__`, `_require_*` or `_validate_*`, over persisted or server-computed values.
  - `INV-TYPE` 20: `TypeError`, `NotImplementedError` or `KeyError` programming guards.
  - `CAND` 400: everything else, listed in full in `cand.txt`.
  - This triage is a naming rule applied to origin function names. It is NOT a read. F-F4 asks CHARC whether the INV and PROG classes are declared by rule.

---

## 3. CLASS 1 (D34): the handler-escape census

### 3.1 Custom typed exceptions that escape an operator path

| id | type (MRO) | raise origin(s) | operator paths (instrument; READ where tagged) | handler at the path | today | verif. | disposition |
|---|---|---|---|---|---|---|---|
| C1-01 | `SchwabSchemaParityError` → `_RedactedMessageError` → `RuntimeError` | `integrations/schwab/trader.py:700` (`_call_endpoint`, after its audit close) | `GET /trades/entry/form` (`routes/trades.py:642` → `view_models/trades.py:624` → `entry_auto_fill.py:375`) · `GET /trades/{id}/exit/form` (`:2391` → `exit_auto_fill.py:751`) · `POST /trades/entry` via the error re-render (`routes/trades.py:781` → `:464`) · `POST /trades/{id}/exit` via the `ValueError` re-render (`:3139`) · CLI `schwab fetch` · `pipeline run` | `entry_auto_fill.py:383` and `exit_auto_fill.py:759` catch `(SchwabAuthError, SchwabRateLimitError, SchwabApiError)`, which does not include it. The CLI's `schwab fetch` catches `SchwabApiError` at `cli_schwab.py:1478,1490`. | web: 500 page; CLI: traceback | READ (both tuples, both raise sites, and the entry re-render chain) | **FIX.** The shape is fork **F-F2**. Whether the web form DEGRADES (so the entry/exit can proceed) is fork **F-F1**. `pipeline run` falls under F-F3. |
| C1-02 | `ValueError` family on `trade exit` (+ `InvalidStateTransition(ValueError)`) | `trades/exit.py:153,155,159,161,168` (bad reason, `shares<=0`, trade not found, not active, shares exceed remaining); `trades/state.py:142,145` | CLI `trade exit` (`cli.py:1147-1170`) | none. `cli.py:1160-1170` is `try: ... record_exit(...) finally: conn.close()`. | traceback on a mistyped id or share count | READ | **FIX**: `click.ClickException` at the boundary (brief section 2.8). Nothing is written before the raise, so this does not engage F-F1: the exit is refused either way. The plan pins "nothing written" by a fresh-connection read. |
| C1-03 | `ValueError` family on `trade stop-adjust` (+ `InvalidStateTransition`) | `trades/stop_adjust.py:127,134,101,103`; `data/repos/trades.py:680,690`; `trades/state.py:142,145` | CLI `trade stop-adjust` (`cli.py:1238`) | `cli.py:1258` catches `StopRegressionError` only | traceback | READ (`:127` "trade not found"; handler list) | **FIX**: `ClickException`. |
| C1-04 | `SchwabPipelineActiveError` → `_RedactedMessageError` | `cli_schwab.py:979` (`_check_pipeline_not_running`) | CLI `schwab purge-marketdata-archive` (`:989`), `schwab resolve-out-of-framework` (`:1019`) | none on either command | traceback while a pipeline run is live | READ | **FIX**: `ClickException`, the same text (the sibling commands at `:202`/`:366`/`:1387` already do this). |
| C1-05 | `ReservedJournalFieldError(Exception)` | 7 raises (row 8 of section 1) | CLI `discrepancy override-correction` (`:447`, `:2310`); CLI `discrepancy resolve-ambiguity` (all 7, through the `_TIER2_HANDLERS` registry) | override-correction catches only `CallerHeld`, `AlreadySuperseded`, `ValidatorRejected` and `ValueError` (`cli.py:4908-4932`); resolve-ambiguity `:4599-4611` catches the same set | traceback on an operator-chosen reserved field | READ (raise sites, handler tuples, and the registry dispatch at `:1753`) | **FIX**: `ClickException` at both commands. The web `POST /reconcile/discrepancy/{id}/resolve` is NOT in the escape set. Its handler chain `routes/reconcile.py:1598..` must be read in the plan to CONFIRM it catches the type, and in which clause. |
| C1-06 | `MultiRowCorrectionOverrideError(Exception)` | `reconciliation_auto_correct.py:1334,1352,1889` | CLI override-correction; CLI resolve-ambiguity | as C1-05 | traceback | READ (`:1334` `:1889`) | **FIX**: `ClickException`. |
| C1-07 | `InvalidOverrideComboError(ValueError)` | `reconciliation_auto_correct.py:813,825,837,1690,1705` | CLI `journal reconcile-tos` | `cli.py:3617` catches `(ValueError, TypeError)`, but around a narrower block | traceback (instrument) | STATIC | **FIX if RED**, otherwise DECLARED. |
| C1-08 | `_SandboxAutoRedirectShortCircuit(Exception)` (internal control flow) | `reconciliation_auto_correct.py:1729` | CLI resolve-ambiguity | - | - | STATIC | DECLARED-if-caught. It is an internal sentinel. The plan reads `apply_tier2_resolution` (`:847`) for its catch. |
| C1-09 | `ImmutableJournalFieldError(ValueError)` | `reconciliation_auto_correct.py:315` | `POST /reconcile/discrepancy/{id}/resolve` | the route's handler chain from `:1598` | 500 (instrument) | STATIC | **FIX if RED**: the route's existing 4xx refusal fragment. |
| C1-10 | `EntryIntentSeamError(ValueError)` / `ValueError` from `EntryRequest.__post_init__` | `trades/entry.py:579,584` | `POST /trades/entry` (`routes/trades.py:1621` builds `EntryRequest` outside a `ValueError` handler) | - | - | READ | **DECLARED, caller-prevented**: the route validates `entry_intent` first at `routes/trades.py:842-852` (typed 4xx). The CLI is prevented by `EntryIntentParam` (`cli.py:577`); the instrument lists no CLI escape. |
| C1-11 | `WatchlistEntryNotFoundError(Exception)` | `data/repos/watchlist.py:84` | `POST /trades/entry`, CLI `trade entry` | - | - | READ | **DECLARED, service-prevented within one transaction**: `entry.py:2309-2310` calls `get_watchlist_entry` and archives only when it finds a row, inside `_entry_transaction`'s `BEGIN IMMEDIATE` (`entry.py:1879`). A concurrent delete is excluded by the write lock. |
| C1-12 | `PatternEvaluationAnchorError(ValueError)` | `trades/entry.py:2118` | CLI `trade entry` | `cli.py:954` catches SoftWarn, HardCap and Duplicate | - | READ | **DECLARED, caller-prevented**: the CLI builds `EntryRequest` without `pattern_evaluation_id`. The awk read of `cli.py:640-1100` shows no such option, so the `req.pattern_evaluation_id is not None` precondition is False. |
| C1-13 | `EnvelopeReadingMissingError(RuntimeError)`, `LatchProbeInvariantError(RuntimeError)`, `RuntimeError` (`assign`/`_set_trades_value`) | `entry_intent_assignment.py:424,608,636`; `latched_origin.py:2310,2515` | CLI `trade assign-intent` | `cli.py:1935` catches `ValueError`; the `:1940` close handler is RULING R8's | traceback | READ (comments at `entry_intent_assignment.py:421-424` "`assign` ran ensure first"; `latched_origin.py:2512-2514` "RAISED, NOT BRANCHED ON") | **DECLARED by rule** (invariant raises by design, whose loud failure is the point), under **F-F4**. |
| C1-14 | `SchemaVersionMismatchError(RuntimeError)` | `data/db.py:1088` (`connect`), `:1062` | **113 roots** (every root that calls `connect`) | none, apart from `db-migrate` | web 500 page; CLI traceback; the message names `swing db-migrate` | READ (`db.py:1088`) | **FORK F-F7.** Reachable in the known merge-to-migrate window (CLAUDE.md, the 2026-09-08 amendment) and on any stale checkout. |
| C1-15 | `ValueError` from `record_view` inside `with conn:` guarded only by `except sqlite3.Error` | `data/repos/latch_view_events.py:126` | `POST /latches/view` (`routes/latches.py:356-364`) | `:364` `except sqlite3.Error` | 500 (instrument) | STATIC (read of `:356-371` shows the narrow clause; the `:126` condition was not read) | **FIX if RED**: the route's own 409 degrade (`:368-371`). This is where D39's `latches.py:364` string lands: it is a class-1 shape. |
| C1-16 | `DecisionIntentsUnavailableError(RuntimeError)` (strict mode) | `latches/reader.py:276,286` | `POST /latches/intent`, `POST /latches/view`, CLI `latches parity` | `/intent` has `except Exception` at `:991` around a different block | 500 / traceback (instrument) | STATIC | Raised only when the repo IMPORT fails (`reader.py:274-276`, the A6 comment). That is a broken install, so the proposal is **DECLARED under F-F4**. |
| C1-17 | `NoActivePolicyError(RuntimeError)` | `data/repos/risk_policy.py:108` | 8 `/metrics/*` pages, CLI `config policy show`, CLI override-correction and resolve-ambiguity | `POST /config` handles it (`routes/config.py:154,236`), as do CLI `config set` and `reset` (`cli_config.py:164,242`) | 500 / traceback on a schema without an active policy row | READ (`:108`) | Service-maintained invariant: `supersede_active_policy` flips the active row inside one `BEGIN IMMEDIATE` (`trades/risk_policy.py:132`). **F-F4** (DECLARED by rule), or FIX by the existing `POST /config` idiom. The handling is inconsistent across paths today, and that is the question put to CHARC. |
| C1-18 | `LabelingDispatchError(RuntimeError)` | `patterns/labeling.py:328,501` | CLI `patterns label-exemplars`, `review-silver-with-codex` | - | traceback | STATIC | Programming guard (the dispatch callable is `None`). **F-F4**. |
| C1-19 | `DuplicateOpenTradesError`, `RuntimeError("schema_version did not reach")` | `data/db.py:602,1039` | CLI `db-migrate` | `cli.py:403` `except Exception` around the seed step only | traceback | READ (`:602` is the 0004 preflight) | **DECLARED**: the 0004 preflight fires only at `pre_version < 4`, and no extant DB is below v41. `:1039` is the runner's own post-condition, which belongs to the B-04 compensating control (the witness reads `schema_version` and the manifest, never the exit code). |
| C1-20 | `ReviewAlreadyCompletedError(ValueError)` (22-I) | `data/repos/review_log.py` | CLI `review complete`, `POST /reviews/{id}/complete` | `cli.py:2387`; `routes/trades.py:3820` | typed refusal / 409 | READ (handlers) + instrument (zero escapes) | **CONFIRMED-HANDLED**, no fix. |
| C1-21 | `CohortReadRacedError`, `AttestedIntentError` (22-B) | - | every consumer | contained per R1-3-SURFACES / N4 | - | instrument (zero escapes) | **CONFIRMED-HANDLED.** |
| C1-22 | `CallerHeld*` family (9 distinct classes, 35 triples) | `in_transaction` guards | e.g. `GET /trades/entry/form` → `audit_service.py:154` | - | - | STATIC | **F-F4** (programming guards; each root opens its own connection). |
| C1-23 | `LeaseRevokedError`, `NoFilesError`, `EvalRunResolutionError`, `promote_staging` `RuntimeError`, and the rest on `pipeline run` | `pipeline/*`, `data/repos/pipeline.py` | CLI `pipeline run` only | step_guard / lease (not followed by the instrument) | - | STATIC | **F-F3 declared** (section 5). |

### 3.2 Implicit raises: the named instances (the instrument cannot see these; established by read)

| id | what | site | today | disposition |
|---|---|---|---|---|
| C1-24 (D35 half / BANK-1) | `sqlite3.IntegrityError` from `fills.price CHECK(price > 0)` escapes the exit POST's `except ValueError` | `routes/trades.py:3135-3151` (the handler is now at `:3137`; D35 said `:2680`) | 500, and no exit written | **FIX**: the route's typed 400 fragment. Per AUTHORIZE-THEN-ABORT (harness 5.1), the service-side twin check comes first (a price that rounds to 0.00 is refused with a typed message), so the trigger/CHECK stays a backstop. The `:139` render half is D35's unactionable-surface class and belongs to 22-G, not here. |
| C1-25 (BANK-3) | `int(inf)` raises `OverflowError` on a leg-sum quantity | `trades/exit_auto_fill.py:1213` (the `int(quantity) <= 0` test) | 500 on `GET /trades/{id}/exit/form` | **FIX**: a finiteness refusal of the candidate, so the form renders degraded. This is **F-F1** (the exit form becomes usable). BANK-4 (`value="inf"`) is 22-G's. |
| C1-26 (D68) | the exit route's post-commit `build_dashboard` rebuild is uncontained for any exception | `routes/trades.py:3155-3160`, after `finally: conn.close()` at `:3153` | 500 over a durable exit | **FIX, already ruled** (brief section 2.10): the R1-3-SURFACES contain shape. Discriminator (brief section 4.4): a planted non-race exception after the commit gives 200 with the degraded-success notice, and the exit is durable. |

### 3.3 Builtin-type escapes (ValueError / TypeError / KeyError / NotImplementedError / RuntimeError)

- **Totals**, as (root, type, origin) triples:
  - INV-MODEL 2446 and INV-TYPE 20. Both are proposed DECLARED by rule (F-F4).
  - PROG-TX 35.
  - CAND 400, over 56 roots. The full per-root listing is `cand.txt`.
- **READ among CAND:** C1-02 and C1-03 above.
- **Named STATIC candidates the plan must RED-attempt first.** These are operator-input shaped by origin name. The complete list is in `cand.txt`.

  | root | candidate origin(s) |
  |---|---|
  | `POST /config`, CLI `config set` | `config_validation.get_spec` / `coerce_value` (`:177`, `:191-202`) |
  | `POST /config/reset/{field_path}`, CLI `config reset` | `config_user.delete_user_override:96` |
  | CLI `config show`, `GET /config` | `config_overrides.get_field_source:247` |
  | `POST /reviews/{id}/complete`, CLI `review complete` | `review_log.complete_review_atomic:236-257` (`duration_minutes <= 0`) |
  | `POST /trades/{id}/review` | `update_entry_intent`, `update_trade_review_fields`, `complete_trade_review:627,629`, `state_transition` |
  | `POST /reconcile/discrepancy/{id}/resolve` | the tier-2 handlers' `ValueError`s (`:1732-1747`, `:2108-2343`, `:3050-3514`) |
  | CLI `schwab resolve-out-of-framework` | `reconciliation.resolve_discrepancy:648-672` |
  | CLI `journal correct-entry-date` | `update_entry_date`, `update_fill_datetime`, `update_archive_removed_date` |
  | CLI `journal correct-cohort-provenance` | `update_cohort_provenance:1169-1182` |
  | CLI `journal oof-buy` | `_build_oof_ref:285`, `_oof_ref_with_seq:310` |
  | `POST /latches/intent` | `build_idempotency_key:214`, `encode_derivation_value:84`, `session_offset:103`, `parse_session_date:42,46` |
  | `POST /dashboard/weather-chart/refresh` | `OhlcNormalizationError` and `_assert_*` raises (`web/charts.py:182-504`) |
  | CLI `rs-universe refresh` | `rs_refresh:22,45,62,99` |
  | CLI `logs cleanup` | `logs_maintenance:134,146,168` |
  | CLI `eval`, `weather` | `rs.load_universe:38`, `classify_weather:55` |
  | CLI `hypothesis list` / `status`, and 5 web roots | `compute_tripwire_status:550` (`hypothesis {id} not found`) |

- **Read-path invariants proposed for DECLARED by rule (F-F4)**, even though they are named CAND:
  - `derived_metrics.r_multiple:33` (22 roots)
  - `PriceCache.get_many:360` ("executor is required", 17 roots)
  - `frozen_value_evidence.replay_verdict:1309`
  - `equity.net_cash_movements:33` (an unknown cash kind in stored rows)
  - the `metrics.honesty` `wilson_ci` / `bootstrap_ci_mean` / `_class_threshold` / `render_class_*` guards
  - `audit_service.record_call_start:132` (a surface literal outside its CHECK set, which callers pass as constants)

### 3.4 Section 2.7a: typed refusals whose message embeds exception text (the cp1252 row)

- **Manifest (AST):** 99 `click.ClickException(...)` calls across the four CLI modules have an argument that mentions an exception variable (`exc`, `e`, `err` or `error`). The instrument tags 97 RAW and 2 SAFE. **By read, only 1 is fully SAFE** (`cli.py:2242`, D69's `ascii_safe(str(exc))`). The second SAFE tag, `cli.py:1950`, applies `safe_text` to the close error only, so its `result.message` segment is RAW. That makes 98 sites that carry un-coerced text.
  - Method: AST over the call arguments.
  - Bound: a message assembled into a local variable before the call is missed.
  - Evidence: `r0-measurements/clickexc_7a.py` and `clickexc_7a.tsv` (site, tag, wrapped handler type, command, argument).
- **Named instance CONFIRMED by read:** `trade assign-intent`, `cli.py:1935-1936`: `except ValueError as exc: raise click.ClickException(str(exc))`.
  - **A second site on the same command:** `cli.py:1950`, `f"REFUSED ({result.refusal_code}): {result.message}; ..."`. `result.message` is the service's refusal text and can embed the operator's `--reason`. The brief named only `:1939`.
- **Candidates whose wrapped message can carry operator free or stored text.** Found by the wrapped service; the message composition was NOT read per site:
  - `trade review` `:1712,:1738,:1769,:1807`
  - `journal cash-void` `:2951`
  - `journal oof-buy` `:2700`
  - `journal correct-entry-date` `:3095,:3139`
  - `journal correct-cohort-provenance` `:3339,:3421`
  - `discrepancy resolve` `:5108,:5110`
  - `discrepancy resolve-ambiguity` `:4415,:4606,:4608`
  - `discrepancy override-correction` `:4929`
  - `hypothesis update` `:5647,:5649`
  - `config policy set` / `import-from-toml` `:480,:553`
  - `cli_config.py:353` (`{raw!r}`: `repr` keeps printable non-ASCII)
- **Premise qualifier** (put to CHARC as F-F5):
  - `cli.py:22-24` reconfigures stdout and stderr to UTF-8 with `errors="replace"` at import. Wherever the stream supports `reconfigure` (a real console, a redirected file or a pipe), Click's `Error:` line cannot raise `UnicodeEncodeError`. The residual is mojibake on a cp1252 console, which is a legibility defect.
  - A crash needs a stream that is non-reconfigurable and cp1252-strict. I did not find one in production. That is an absence claim from reading `cli.py:22-28`, not a measurement.
  - The R3-1 rider's discriminator (`64bae976`) asserted `.encode("cp1252")` on the one constructed line. That is an ASCII-ness proxy. It is not a reproduced crash.

---

## 4. CLASS 2 (D39): transaction hygiene, measured on the SHAPE

Facet key:
- **F1**: BEGIN outside the protecting `try`.
- **F2**: the handler type that triggers the rollback. Anything narrower than `BaseException` lets `KeyboardInterrupt` and similar skip the rollback.
- **F3**: rollback-failure handling. `suppressed` means the double failure leaks the transaction and reports only the first error. `unguarded` means a raising rollback REPLACES the in-flight error: it is chained implicitly through `__context__`, with no discard log. `chained` is the 22-A template.
- **F4**: a bare `close()` after a durable commit.

"Ops" means reached from these operator roots (via `tx.json`).

### 4.1 Explicit BEGIN sites (31) and their rollback handling

| id | site (function) | F1 | F2 | F3 | operator roots | verif. | disposition |
|---|---|---|---|---|---|---|---|
| C2-01 | `trades/reconciliation_auto_correct.py:889` `apply_tier2_resolution` (rollback `:908`) | yes | `Exception` | suppressed `suppress(sqlite3.Error)` | web resolve POST, CLI resolve-ambiguity | READ (suppress at `:907`) | **FIX** (22-A template) |
| C2-02 | `…:965` `apply_source_direction_resolution` (`:1083`) | yes | `Exception` | suppressed | same 2 | READ (`:1082`) | **FIX** |
| C2-03 | `…:1106` `apply_tier3_override` (`:1119`) | yes | `Exception` | suppressed | CLI override-correction | READ (`:1118`) | **FIX** |
| C2-04 | `…:752` `apply_tier1_correction`, `…:1142` `stamp_pending_ambiguity` | yes | `Exception` | suppressed | **none**: no production caller (grep of both names returns only docstrings and `reconciliation.py:199-200` prose) | READ (grep) | **DECLARED**: no operator path. The same fix is recommended for uniformity; the plan decides (it is not a fork). |
| C2-05 | `cli.py:4588` resolve-ambiguity `linked_correction` envelope (rollback `:4597`) | yes | `Exception` | **unguarded** (READ corrects the instrument's "chained") | CLI resolve-ambiguity | READ `:4585-4598` | **FIX** |
| C2-06 | `trades/reconciliation.py:418` `run_tos_reconciliation` (`:594`), `:669` `resolve_discrepancy` (`:730`) | no | `Exception` | suppressed | reconcile-tos; web resolve, CLI resolve, resolve-ambiguity, resolve-out-of-framework | READ (suppress lines) | **FIX** (both). The D39 row's "reconciliation.py (2 sites)". |
| C2-07 | `trades/entry_date_correction.py:1365` `correct_entry_date` (`:1380`) | yes | `Exception` | suppressed | CLI correct-entry-date | READ (`:1379`) | **FIX** |
| C2-08 | `trades/schwab_reconciliation.py:1843` `run_schwab_reconciliation` (`:2773`, `:2794`) + 7 `ROLLBACK TO SAVEPOINT` under `suppress(sqlite3.Error)` at `:1175,1247,1263,1275,1295,1325,1330` | no | `Exception` / `sqlite3.Error` | suppressed ×9 | CLI `schwab fetch` (+ pipeline) | READ (the 9 suppress lines) | **FIX**: the D39 row's "9 sites". The savepoint rollbacks sit inside the outer run transaction, so the discard-the-connection message applies at the OUTER site. |
| C2-09 | `integrations/schwab/audit_service.py:164` `record_call_start` (`:184`,`:187`), `:237` `record_call_finish` (`:259`,`:262`), `:307` `link_snapshot…` (`:319`), `:367` `link_reconciliation_run` (`:376`) | `:164`/`:237` no; `:307`/`:367` yes | `Exception` (+ `OperationalError`) | unguarded | 10 roots (entry/exit forms and POSTs, `/latches/orders`, `/schwab/setup`, schwab CLIs) + pipeline | STATIC (facets by instrument) | **FIX** |
| C2-10 | `data/yfinance_audit.py:118` `record_call_start` (`:127`), `:158` `record_call_finish` (`:167`) | yes | `Exception` | unguarded | 5 web GET roots (charts, thumbnails, review charts) + pipeline | STATIC | **FIX** |
| C2-11 | `trades/account_equity_snapshots.py:133` `record_snapshot` (`:148`) | yes | `Exception` | unguarded | `POST /account/snapshot`, CLI `account snapshot`, `schwab fetch` | STATIC | **FIX** |
| C2-12 | `trades/daily_management.py:823` `record_event_log` (`:935`) | yes | `Exception` | unguarded | `POST /trades/{id}/daily-management/event` | STATIC | **FIX** |
| C2-13 | `trades/hypothesis.py:187` `update_hypothesis_status_with_audit` (`:284`; plus three re-raise rollbacks `:199,:205,:211`) | yes | `Exception` | unguarded | CLI `hypothesis update` | STATIC | **FIX** |
| C2-14 | `trades/risk_policy.py:132` `supersede_active_policy` (`:212`); `:407` `seed_initial_policy` (`:452`) | no | `Exception` | unguarded | 7 roots (`POST /config`, `/config/reset`, config/policy CLIs, `db-migrate`); `:407` has no caller | STATIC | **FIX** `:132`; DECLARED `:407` (no caller) |
| C2-15 | `data/repos/review_log.py:248` `complete_review_atomic` (22-I-touched) | yes | **none** (no rollback handler) | - | `POST /reviews/{id}/complete`, CLI `review complete` | STATIC | **FIX if the facet is confirmed on read.** The file changed in 22-I (`git diff b8f80e91..HEAD --stat`: 47 lines), so the plan reads its current shape before writing the row's test. |
| C2-16 | `trades/entry_intent_assignment.py:640` `assign` | yes | none in-function | - | CLI `assign-intent` | STATIC | **Read at plan.** 22-B R7/R8/B-01 ruled this command's durability boundary, and AL-7 is DECLARED. Any F1 fix must not move R7's ruled boundary. If a fix is needed, route it to CHARC (it touches a ruled shape). |
| C2-17 | `diagnostics/backfill_trades_sector_industry.py:115` `run_backfill` | yes | none | - | CLI `diagnose backfill-trades-sector-industry`, `journal reconcile-backfill` | STATIC | **FIX** (an operator maintenance path) |
| C2-18 | `trades/entry.py:1879` `_entry_transaction` (`:1929`); `trades/cohort_provenance_correction.py:2379`/`:2828` (`:2407`/`:2861`) | no | `BaseException` | chained | entry POST/CLI; correct-cohort-provenance | instrument + READ of the template at `:2388-2417` | **CONFIRMED-TEMPLATE**: these ARE the 22-A shape. No fix. |
| C2-19 | `trades/cohort_provenance_correction.py:3544` `read_provenance_corrections` (deferred read transaction) | - | `finally` re-raise | - | CLI provenance-corrections | instrument | CONFIRMED (a read transaction whose `finally` rollback re-raises). No fix. |
| C2-20 | `pipeline/lease.py:215` `fenced_write`, `:258` `acquire_lease`; `pipeline/runner.py:3294` `_step_charts` | yes | none | - | reached ONLY through `pipeline run` (zero non-pipeline roots in `tx.json`) | instrument | **F-F3 DECLARED** (section 5) |
| C2-21 | `data/db.py:576` `_apply_migration` (`except Exception: rollback`, unguarded) + **22-B B-04** (after the script's own `COMMIT`, the `finally` PRAGMA restores (`foreign_keys`, `legacy_alter_table`), the close and the echo can each raise, so `db-migrate` exits nonzero over a durable version) | - | `Exception` | unguarded | CLI `db-migrate` | READ of RULING B item 4 (22-B exec ledger) | **FIX**: banked to this sweep as INTRODUCED-BY-EXTENSION with a compensating control. The fix shape is the two-durability-facts close handler (B-02) applied runner-wide: a WARN and exit 0 when the target version is durable. The B-04 compensating control stays binding until this lands. |
| C2-22 | 22-A3's entry command, the c2 pre-boundary re-raise (RULING R8: "banked as a sibling for the D39 sweep") | - | - | - | CLI `trade entry` (`cli.py:964`/`:1018`/`:1059` `BaseException` handlers) | named by the ruling; STATIC on shape | **FIX** under R8's chained-refusal shape. The plan reads which handler is the c2 site. |

### 4.2 F4: close-after-commit (58 operator roots carry the shape)

- The shape: a bare `finally: <x>.close()` whose try body reaches a commit. The list is in `f4.txt`.
- **Operator-record writes (41; corrected from 32 by replacement at the 22-F R1 gate, CHARC 3(c) -- method: the count of root entries this listing names, 25 CLI + 16 web, cross-checked against the 58 lines of `f4.txt`):**
  - CLI: `trade exit` (`cli.py:1170`), `trade stop-adjust` (`:1261`), `journal cash` / `oof-buy` / `cash-void` / `correct-entry-date` / `correct-cohort-provenance` / `reconcile-tos` (`:2589`, `:2808`, `:3002`, `:3141`, `:3423`, `:3601`), `discrepancy resolve-ambiguity` / `override-correction` / `resolve` (`:4618`, `:4938`, `:5112`), `tos-import` (`:5254`), `pipeline force-clear` (`:5419`), `hypothesis update` (`:5651`), `finviz fetch` (`:5719`), `account snapshot` (`:5827`), `config set` / `reset`, `policy set` / `import-from-toml` (`cli_config.py:193,275,482,555`), and `schwab resolve-out-of-framework` / `fetch` / `setup` / `refresh` / `logout` (`cli_schwab.py:1058,1512,211,311,379`).
  - Web POSTs: `/account/snapshot` (`account.py:171`), `/config` (`config.py:186`), `/config/reset` (`:265`), `/latches/intent` / `orders` / `view` (`latches.py:1319,242,374`), `/patterns/exemplars/{id}/action` (`patterns.py:176`), `/patterns/{id}/review` (`:609`), `/pipeline/force-clear` (`pipeline.py:287`), `/reconcile/.../resolve` (`reconcile.py:1768`), `/trades/{id}/exit` (`trades.py:3153`), `/trades/{id}/stop` (`:3303`), `/trades/{id}/review` (`:3688`), `/trades/{id}/daily-management/event` (`:4047`), `/watchlist/{ticker}/pin` (`watchlist.py:274`), `/dashboard/weather-chart/refresh` (`dashboard.py:176`).
  - **FIX**: the two-durability-facts handler, citing 22-B B-02 (`trade review`) as the reference implementation. A refusal in flight takes R8's chained shape. With everything durable, the result is the 22-A3 WARN and exit 0 (CLI), or the committed response with the degraded notice (web, per R1-3-SURFACES).
- **Read paths whose "commit" is a cache or audit row only (17; corrected from 26 by replacement, same method: 12 web + 5 CLI):**
  - GET `/charts/{t}.png`, `/health/tool`, `/health/research`, `/journal/trades/{id}` (+ `/thumbnail`, `/chart`), `/patterns/{id}/review`, `/hyp-recs/refresh`, `/hyp-recs/{t}/expand`, `/trades/open/{id}/expand`, `/trades/{id}/review/chart`, `/trades/entry/sizing-hint`.
  - CLI `eval`, `patterns label-exemplars`, `review-silver-with-codex`, `patterns-exemplars-backfill-labeler-evidence`, `diagnose prune-chart-cache`.
  - No operator verdict rides on a GET's close. **Proposed DECLARED under F-F4 (b).** The split between the two lists is my reading of the labels; the plan confirms each one by what its try body writes.
- **Implicit `with conn:` transactions:** 58 blocks (36 web, 10 `cli.py`, 5 pipeline, 4 trades, 3 others).
  - sqlite3's context manager rolls back on ANY exception, including `BaseException`, so F2 does not apply.
  - A raising rollback in `__exit__` replaces the error with implicit chaining. That is F3 in its "unguarded" form.
  - Web connections are per request and closed in `finally`, so a leaked transaction dies with the connection. This is **mechanic k3** (section 7). It bounds the leak, not the wrong-error message.
  - **Proposed: counted as a class, not rowed.** The rows are the explicit sites above.

### 4.3 The D39 row's named sites, mapped (string → shape)

| D39 row names | shape found | row |
|---|---|---|
| `swing/trades/entry.py` "BEGIN IMMEDIATE outside try" | `_entry_transaction` is now the 22-A template (BEGIN inside, `BaseException`, chained) | C2-18 CONFIRMED. The sibling that remains is the R8 c2 re-raise (C2-22). |
| `entry_date_correction.py` | F1 + suppressed | C2-07 |
| `reconciliation.py` (2 sites) | `:418`, `:669`, both suppressed | C2-06 |
| `reconciliation_auto_correct.py` | 5 BEGIN sites, all suppressed (3 on operator paths, 2 with no caller) | C2-01..04 |
| `schwab_reconciliation.py` (9 sites) | 9 `suppress(sqlite3.Error)` | C2-08 |
| `cli.py:6722` | not a BEGIN on any tree read. `cli.py`'s single executable BEGIN is `:4588`. | C2-05 (mapped by uniqueness, not by line) |
| `web/routes/latches.py:364,855,914` | `:364`: class-1 (C1-15). `:855`/`:914`: reads holding no transaction that raise the typed `_GovernanceUnknownError`. **No D39 shape.** | C1-15; `:855`/`:914` DECLARED (no transaction) |
| + 22-A3 plan S8 item 8: two cohort messages that assert an unobserved transaction state | **not located in this round.** The row names no file:line. | **OPEN**: the plan locates them by reading the 22-A3 plan's S8 item 8. |

---

## 5. F-F3: the declared list, read-verified against the census

**The declared set: pipeline-internal and research-harness.**

| site | why it is declared | verified by |
|---|---|---|
| `pipeline/lease.py:215` `fenced_write` | pipeline-internal | `tx.json`: reverse reach finds only `pipeline_group:run` (zero other roots) |
| `pipeline/lease.py:258` `acquire_lease` | same | same |
| `pipeline/runner.py:3294` `_step_charts` (`BEGIN`) | same | same |
| the pipeline's internal escapes on `pipeline run` (C1-23) | "no operator reads their exit code live; the runner's step_guard contains them" (brief F-F3) | the instrument does not follow `step_guard`'s callable, so this is **the brief's reason, not measured here** |
| `research/` | contains no transaction site: `grep -rn 'execute("BEGIN\|\.rollback()' research` returns empty | grep |
| `scripts/probe_22i_guard_census.py:134`, `scripts/probe_22i_plan_measurements.py:134` | witness and probe instruments over a COPY; not operator paths | grep + read of the file names (22-I's instruments) |

**What the seed would have mis-declared** (existence ≠ completeness):
- The audit writers `audit_service.py` (C2-09), `yfinance_audit.py` (C2-10), `record_snapshot` (C2-11) and `run_schwab_reconciliation` (C2-08) all run in the pipeline. They are ALSO reached from operator roots (10, 5, 3 and 1 roots respectively; `tx.json`). They are therefore IN the arc, not declared.

**Caveat on "pipeline run" itself:**
- `swing pipeline run` is a CLI command, so its ENTRY is an operator path.
- The declaration covers the runner's internals. Escapes before the lease (config load, `connect`) are C1-14 / F-F7.

---

## 6. FORK PACKET: one ruler per item. No review round opens while any item is outstanding.

**F-F1: RD.** Typed handling that CHANGES whether a money-bearing entry or exit can proceed on the web.

- **Rows:**
  - C1-01: `SchwabSchemaParityError` on `GET /trades/entry/form` and `GET /trades/{id}/exit/form`, and on the two POST re-renders.
  - C1-25: BANK-3 `OverflowError` on `GET /trades/{id}/exit/form`.
- **Current behaviour:** a 500 page. The web form is unavailable, so the operator cannot record the entry or exit on the web (the CLI path remains). Nothing is written.
- **Branch (a), DEGRADE.** The auto-fill returns its existing `kind="error"` result, the same one its `SchwabApiError` siblings produce (`entry_auto_fill.py:383-395`, `exit_auto_fill.py:759-771`): `fill_origin="operator_typed"` and the advisory "auto-fill unavailable. Please enter manually". For BANK-3 the non-finite candidate is refused with a reason. The form renders and the entry or exit PROCEEDS on operator-typed values.
- **Branch (b), REFUSE.** A typed refusal page or fragment (4xx or 200 with the refusal text, and no form). The web entry or exit stays blocked, as today, but legibly.
- **ENTRY-vs-LABEL** (harness section 5.1): *could the row be written honestly with the disputed keys NULL plus a named warning?* **YES.** `fill_origin='operator_typed'` with no Schwab source is the honest-unset row, and the refusal is of the auto-fill LABEL, not the ENTRY. The test therefore points to (a).
- **Cell's recommendation: (a).**

**F-F2: CHARC.** The fix shape for C1-01 (`SchwabSchemaParityError` escaping the Schwab tuples). No NEW exception type is proposed anywhere in this census.

- **Branch (A), per-site widening.** Add `SchwabSchemaParityError` to the escaping tuples: `entry_auto_fill.py:383`, `exit_auto_fill.py:759`, and the CLI `schwab fetch` snapshot and orders handlers (`cli_schwab.py:1478,1490`).
  - The MRO is unchanged.
  - Precedent: `pipeline_steps.py:586` already names it beside `SchwabApiError`.
- **Branch (B), re-base.** `class SchwabSchemaParityError(_RedactedMessageError, SchwabApiError)`.
  - MRO: `SchwabSchemaParityError → _RedactedMessageError → SchwabApiError → RuntimeError`. Both bases derive from `RuntimeError`, so the C3 linearization is consistent. The redaction base comes first.
  - Every existing `SchwabApiError` handler becomes a catcher. By AST there are **18**: `cli_schwab.py:304,368,1168,1227,1478,1490`; `integrations/schwab/auth.py:2194`; `marketdata.py:565,612,652`; `marketdata_ladder.py:337,469`; `pipeline_steps.py:266,586`; `trader.py:575,626`; `entry_auto_fill.py:383`; `exit_auto_fill.py:759`.
  - The 5 explicit `SchwabSchemaParityError` handlers (`cli_schwab.py:1164,1223`; `mappers.py:919`; `marketdata.py:675`; `trader.py:668`) must keep their precedence. `cli_schwab.py:1164`/`:1223` sit BEFORE their `SchwabApiError` siblings `:1168`/`:1227`, so the order holds.
  - Under (B), each of the 18 is READ at plan time for a behaviour change. `trader.py:575,626` especially: it catches `SchwabApiError` inside the wrapper that closes the audit rows.
- **Cell's recommendation: (A).** It is smaller, it leaves the audit-close paths in `trader.py` untouched, and it has an in-tree precedent.
- **The same question for `ReservedJournalFieldError(Exception)` (C1-05).** A re-base under `ValueError` would be caught by the CLI's `except ValueError` at `cli.py:4611`/`:4932` (and by every other `ValueError` handler on the reconcile paths). Its own docstring says the `Exception` base is deliberate: `reconciliation_auto_correct.py:121-127` names `ImmutableJournalFieldError(ValueError)` as its sibling, "not a member". **Recommendation: per-site `ClickException`, no re-base.** It is listed under this fork only so that CHARC can say otherwise.

**F-F4: CHARC.** Census scope: which builtin and invariant escapes are DECLARED by rule rather than converted one by one.

- **Rows:** INV-MODEL (2446 triples: row-shape `__post_init__` / `_require_*` / `_validate_*` over persisted or server-computed values), INV-TYPE (20), PROG-TX (35 `CallerHeld*`), C1-13, C1-16, C1-17, C1-18, the read-path invariants in 3.3, and F4's 17 read-path closes (4.2; corrected from 26).
- **Branch (a), DECLARE by class.**
  - The reason: these are invariant or programming guards, not refusals. The loud 500 or traceback IS the correct report of a violated invariant.
  - The recipe's schema/service-prevented rule governs READ-only consumers (section 3 of the recipe). The citation per class is the write-side constraint (the model's CHECK mirror under gotcha #11). For `CallerHeld*` it is the fresh `connect()` at each root.
  - One pin per class. Example: a raw-planted invalid row reaches the 500 page carrying the invariant text, so the class's loudness is asserted.
- **Branch (b), CONVERT.** Every reachable row becomes a typed refusal: a 4xx on the web, `ClickException` on the CLI.
- **Cell's recommendation: (a)**, with C1-17 (`NoActivePolicyError`) as the one exception to decide explicitly. `POST /config` already handles it (`routes/config.py:154`), so the inconsistency is visible to the operator.

**F-F5: CHARC.** Section 2.7a, the cp1252 row: its premise and its shape.

- **Premise (3.4):** `cli.py:22-24` makes the crash unreachable wherever `reconfigure` works. What remains is mojibake.
- **Branch (a), UNIFORM.** `ascii_safe` on all 98 exception-text `ClickException` sites that carry un-coerced text, plus a CLOSURE test: a static walk asserting that every `ClickException` argument mentioning an exception variable passes through `ascii_safe` or `safe_text` (the recipe's "the fix is the closure check, not the list").
  - RED discriminator per the R3-1 precedent (`64bae976`): `.encode("cp1252")` on the constructed `Error:` line, fed non-ASCII operator text.
- **Branch (b), PER-SITE.** Only the sites whose message is READ to carry stored or free text: at least `cli.py:1936` and `:1950`, plus the candidates in 3.4 after reading.
- **Cell's recommendation: (a).** It is cheaper than proving per-site composition, and the closure test stops the class re-growing.

**F-F6: CHARC.** Phase-isolation carve-out (a section 5 tripwire). The brief does not state it in words.

- **Needed because:** the fixes touch `swing/trades/` and `swing/data/`.
- **The files, from this census:**
  - `swing/trades/`: `reconciliation_auto_correct.py`, `reconciliation.py`, `entry_date_correction.py`, `schwab_reconciliation.py`, `account_equity_snapshots.py`, `daily_management.py`, `hypothesis.py`, `risk_policy.py`, `exit_auto_fill.py`, `entry_auto_fill.py`, `exit.py` (only if the service twin for C1-24 lands there), and possibly `entry_intent_assignment.py` (C2-16, read first).
  - `swing/data/`: `db.py` (C2-21), `yfinance_audit.py` (C2-10), `repos/review_log.py` (C2-15).
  - Also `swing/integrations/schwab/audit_service.py` (not carve-out-governed, listed for completeness).
- **Branch (a):** CHARC states the carve-out as this file list; guard-and-handler edits only, no schema, no behaviour change beyond the rows.
- **Branch (b):** the arc stays out of `swing/trades` / `swing/data` and fixes only at the boundary (routes and CLI). That leaves C2-01..17 unfixed, which contradicts the brief's section 2.7.
- **Included in the same ruling:** whether the banked 22-I AL-7 docstring correction (`reconciliation_auto_correct.py:2188-2193` names an `equity_delta`/`snapshot_mismatch` → `account_equity_snapshots` precedence branch that the code at `:2194-2205` does not implement; comment-only; the gotcha-#31 class) rides this carve-out. The alternatives are a rider or DECLINED.
- **Cell's recommendation: (a)**, with the AL-7 docstring IN, as one comment-only commit.

**F-F7: CHARC.** C1-14, `SchemaVersionMismatchError` on 113 roots.

- **Branch (a), ONE boundary per surface, in EXISTING modules:**
  - Web: `@app.exception_handler(SchemaVersionMismatchError)` inside `_register_exception_handlers` (`swing/web/app.py:148`). It renders a typed page at 503 with the existing message, which names `swing db-migrate`.
  - CLI: `main`'s group converts it to `click.ClickException`. The mechanism is a `click.Group` subclass with an `invoke` override in `cli.py`: no new module, and one class in an existing one.
- **Branch (b), DECLARE.** The guard is a by-design refusal, and its text already names the fix. A 500 or traceback carrying it is accepted, with the reason "an environment state, not an operator input".
- **Branch (c):** per-root handling (113 sites). Not recommended.
- **Tension:** R1-3-SURFACES rules "a 500 is never a refusal (D34)". Under (b) that clause needs an explicit exemption.
- **Cell's recommendation: (a).**

**No other new forks found.**
- Brief section 2.9: apart from F-F1, no row's fix changes behaviour the operator relies on. C1-02/C1-03/C1-04/C1-05/C1-06 convert a traceback into the same refusal with the same outcome (nothing written).
- No new module is proposed. F-F7(a) adds a class inside `cli.py`.

---

## 7. Kept claims: the mechanic that makes each one true and the surface it was measured on (recipe rule 1)

| # | claim the plan will carry forward | mechanic | measured on |
|---|---|---|---|
| k1 | a web escape presents as the generic 500 page carrying `str(exc)` | `app.py:149` `@app.exception_handler(Exception)` → `error.html.j2` / `error_fragment.html.j2` / `trade_form_error.html.j2` at 500 | code read of `app.py:148-178`. Not measured by TestClient in this round. |
| k2 | a CLI escape presents as a traceback | a plain `@click.group()` `main` (`cli.py:218`); no `cls=` / `invoke` override (grep = 0) | code read |
| k3 | a transaction leaked on a web route dies with its connection | a per-request `connect()` plus `finally: conn.close()` | READ at `routes/latches.py:289-374` and `routes/trades.py:3133-3153` only. **Not measured for all 72 routes: OPEN ITEM** (the plan confirms per route in the C2 rows it touches). |
| k4 | a non-ASCII `ClickException` message does not crash the CLI | the `cli.py:22-24` reconfigure | code read. Not reproduced by execution. **OPEN ITEM** (F-F5). |
| k5 | the web entry POST validates `entry_intent` before building `EntryRequest` | `routes/trades.py:842-852` | code read (C1-10) |
| k6 | `EntryRequest` from the CLI never carries `pattern_evaluation_id` | no such option in `trade entry` | awk over `cli.py:640-1100`. Bounded by that line range, which is the command body. |

---

## 8. What I believe the brief got wrong (evidence in the row cited)

1. The section 1 handler counts (78 / 38 / 17) do not reproduce by AST or by grep at the brief's own base (section 1 rows 1, 2, 10). The modal-tuple and broad counts do reproduce (±1, explained).
2. The operator-path list omits `swing/cli_latches.py` (section 1 row 6).
3. Section 2.7a presents the cp1252 crash as reachable. `cli.py:22-24` makes it unreachable wherever the streams reconfigure (3.4, F-F5).
4. D39's named sites are partly not D39 shapes: `latches.py:855/914` hold no transaction, `:364` is class-1, and `cli.py:6722` does not exist as a BEGIN (4.3). Two of the named files are already the template (`entry.py`; C2-18).
5. F-F3's declared reason assumes the pipeline sites are pipeline-only. Four shared writers are reached from operator roots (section 5).
6. No phase-isolation carve-out is stated for a sweep whose fixes live in `swing/trades` and `swing/data` (F-F6).
7. "Every row with reachability evidence": the builtin escape manifest is 2,900+ (root, type, origin) triples, and reading them all is out of reach for one cell. This census READS the typed rows and the named rows, and puts the rest to CHARC by rule (F-F4). The plan's RED-first step settles the STATIC rows.
