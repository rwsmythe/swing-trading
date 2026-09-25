# Phase 22 arc 22-F plan ledger (handler-escape + transaction-hygiene sweep)

**Branch:** `22-f-plan`, cut from main @ `79035d59`. **Census:** `2026-09-25-phase22-arc-f-handler-escape-sweep.census.md` (this directory). **Plan:** `2026-09-25-phase22-arc-f-handler-escape-sweep.md` (this directory), written by a FRESH plan cell off the committed census + rulings (the R0 cell ended over the cap). Its §1.2 carries the plan-authoring intake corrections (nine facts checked against the code; three are flagged up: §1.2 rows 1, 3 and 6).
**Evidence (durable, outside the repo):** `C:\Users\rwsmy\swing-data\review-transcripts\22-f-plan\`

## Round table

The DEPTH column is filled by the orchestrator from `scripts/cell_depth.py --agent <id>`. It is never filled by the cell.

| round | kind | tier / model | verdict | task-bearing findings | tokens used | depth (orchestrator) | notes |
|---|---|---|---|---|---|---|---|
| R0 | premise + fork census (no Codex) | - | - | - | 0 Codex | **405,207 — OVER the 400K cap** (`cell_depth --agent`, read at return 2026-09-25) | census committed; the cell does NOT resume -- the plan loop goes to a FRESH cell off this committed census + the evidence dir; fork packet F-F1..F-F7 routed via the orchestrator |
| R1 | Codex plan review, round 1, on plan `c4c035c3` (sha256 `cc2e43da...a266a`) | `fast` / `gpt-5.6-luna` (= `~/.codex/fast.config.toml` `model`), effort `medium` | `NEW_CRITICAL_MAJOR_FOUND` (anchored count 2 = the CLI's duplicated final message; the clean token 0) | 3 major, all task-bearing, 0 reopened; 0 critical; 0 minor | 134,901 | **348,615** (`cell_depth --agent`, read at the R1 gate); the cell does NOT resume -- fixes + R2 go to a FRESH cell | assertions: banner model == profile model; effort `medium` (not `none`); `^ERROR` = 0; `^tokens used` = 1; codex process exited (exit file `0`). No reach for prior-round files (grep of the transcript). Evidence: `review-transcripts\22-f-plan\r1\` -- `.codex-review-r1.txt` (207,129 B), `.codex-prompt-r1.md` (4,366 B), the reviewed plan (64,488 B) + ledger copies, `run_r1.sh`, `exit-r1.txt`. Returned at the gate, NO fix applied |

## Rulings

(None yet. Each ruling lands here as a literal block quote with its author, date and text-of-record pointer, and the plan loop opens only after every F-F item is ruled.)

### F-F1 -- RULED by RD (2026-09-25 07:29Z), (a) DEGRADE on both rows

Author: RD (seat `swing-rd-20260924-2100`). Courier: the orchestrator. Text of record: role-mail `20260925T072925Z-rd-f-f1-ruling-a-degrade-both-rows-entry-tw.md`. The literal block quote follows, the message body verbatim:

> F-F1 RULING (RD, sole ruler on this item): (a) DEGRADE, on both rows. Read on disk at 22-f-plan base 79035d59 = main; the sites are named below. Preconditions stated with which exist today; what the plan must pin follows each row.
>
> 1. C1-01 -- SchwabSchemaParityError on GET /trades/entry/form, GET /trades/{id}/exit/form, and the two POST re-renders.
>
> RULING: (a). ENTRY-vs-LABEL applied on the code, not on the census's word: on GET the request carries NO claim -- the operator has typed nothing -- so NULL discards nothing. The honest-unset row exists today: fill_origin='operator_typed' is the dataclass default (entry.py:546, exit.py:65) with the audit columns NULL. The named-warning surface exists today: the kind="error" result at entry_auto_fill.py:383-395 / exit_auto_fill.py:759-771, the exact branch every SchwabApiError sibling takes, whose advisory names the exception class on the form. A parity error says "the framework cannot read the broker's shape today"; it says nothing about whether the operator's fill happened. Refusing the ENTRY on it blocks a money-bearing record on bookkeeping -- the jurisdiction where NEVER means never.
>
> Preconditions and pins:
> (i) Nothing is written on GET before the raise except the schwab_api_calls audit row, which _call_endpoint closes before raising (the census's C1-01 "after its audit close"; I did NOT open trader.py:700). The plan proves it by a fresh-connection read, the way C1-02's row already does for its site.
> (ii) THE ONE PLACE A CLAIM IS CARRIED: the entry POST re-render RESTORES the submitted anchor over the fresh fetch (routes/trades.py:476-500). So a parity error on the re-fetch during a retry degrades the FRESH VM and the submitted schwab claim survives -- preserved by existing code the fix does not touch. PIN IT or (a) on the re-render is an assumption (gotcha #31's shape): a validation-failed POST carrying a populated schwab anchor, the re-render's fetch raising SchwabSchemaParityError, and the rendered hidden anchor equal to the submitted one with kind 'populated'.
> (iii) Read, not ruled, outside F-F1: the exit POST re-render (routes/trades.py:3139) rebuilds the VM fresh and does not round-trip the submitted anchor at all, parity error or not. Pre-existing; it does not change whether the exit proceeds; the orchestrator's queue.
> (iv) Independent of F-F2's shape: (A) widens the tuple, (B) makes the tuple catch it by MRO; under either the sibling branch fires. One test per form that the parity error reaches kind="error" covers both.
> (v) The degraded form must SHOW the advisory. The sibling does; pin that the rendered form text names SchwabSchemaParityError. A degraded form indistinguishable from a no-Schwab form is the asymmetric surface (harness 5.1, the negative-state rule).
>
> 2. C1-25 (BANK-3) -- OverflowError at exit_auto_fill.py:1213.
>
> RULING: (a): refuse the CANDIDATE with its own reason token; the form renders. Conditions:
> (i) A NEW token (non_finite_quantity or equivalent), never folded into no_quantity or sub_one_share_quantity. A missing quantity and an infinite one from the broker are different evidence kinds, and the second is a data-quality alarm the operator should read on the form.
> (ii) The finiteness test PRECEDES int(quantity) in the same chain, so the truncation is reached only on a finite value. The guard is math.isfinite, not a catch of OverflowError: int(nan) raises ValueError, same class, same fix.
> (iii) Discriminators: inf -> refused with the new token; nan -> same; 1e18 (finite, huge) -> NOT refused by this guard (pins finiteness, not magnitude); 0.9 -> sub_one_share_quantity unchanged.
>
> 3. FOUND BY READ, NOT IN THE CENSUS -- the ENTRY twin of BANK-3.
>
> entry_auto_fill.py:445-446: quantity = _resolve_match_quantity(chosen); shares = int(quantity). Bare truncation on the ENTRY form (GET /trades/entry/form): no finiteness guard, no <= 0 guard, and no None guard at the site although the resolver has a return-None path (mappers.py:428). OverflowError on inf, ValueError on nan, TypeError on None. BANK-3 as named covers the exit side only. The ruling above EXTENDS to it under F-F1 with the same answer: refuse the candidate, an "empty"/"error" result with a named advisory, the form proceeds on typed values. Bounded search stated: I read ONE site; I did not enumerate the candidate filter to know whether None is reachable there. The plan answers that by a read of _is_execution_bearing_candidate stated in the row, or by a RED attempt. Whether this becomes a C1 row is the orchestrator's; that its handling is (a) is mine.
>
> Posture: nothing the October read quotes moves. Degraded rows carry NULL auto-fill provenance exactly as today.

**Orchestrator disposition of RD's item 3 (the entry twin of BANK-3, `entry_auto_fill.py:445-446`):** it becomes census row **C1-27** (handling = RD's (a) above, bound). The plan states the `_is_execution_bearing_candidate` read or a RED attempt for None-reachability, per RD's bounded-search note. **RD's item 1(iii)** (the exit POST re-render at `routes/trades.py:3139` does not round-trip the submitted anchor) is OUT of 22-F and goes on the orchestrator's queue.

### F-F2, F-F4, F-F5, F-F6, F-F7 -- RULED by CHARC (2026-09-25 07:29Z)

Author: CHARC (seat `swing-charc-20260924-1903`). Courier: the orchestrator. Text of record: role-mail `20260925T072946Z-charc-ruled-22-f-r0-f-f2-a-closure-f-f4-a-f-f5.md`. The literal block quote follows, the message body verbatim:

> CHARC RULING PACKET -- 22-F round-0 census (census @ 39762d51 on 22-f-plan, section 6 read end to end at this seat; the cited code read on main @ f143020f). One ruling per item: F-F2, F-F4, F-F5, F-F6, F-F7. F-F1 is RD's and I say nothing on it. Courier: the orchestrator, block quotes into the 22-F ledger, then the fresh plan cell.
>
> READ AT THIS SEAT before ruling (method stated): client.py:336 _RedactedMessageError(RuntimeError), :360 SchwabApiError(RuntimeError), :401 SchwabSchemaParityError(_RedactedMessageError) -- NOT under SchwabApiError, as the census says. grep -rn 'except .*SchwabApiError' swing/ = 18 sites, the census's list exactly. Three handler bodies read: cli_schwab.py:304 raises ClickException 'Refresh failed (transient/network): ...'; pipeline_steps.py:266 returns status failed naming type(exc).__name__; entry_auto_fill.py:383 returns kind=error / operator_typed with the 'auto-fill unavailable' advisory. web/cli_cmd.py:47 already fail-fasts SchemaVersionMismatchError at swing web START (exit 1, names db-migrate) -- the running-server case is the uncovered one. cli.py:22-30: the utf-8 reconfigure is inside try/except and the except branch PRESERVES the original encoding on embedded consoles. ascii_safe is defined ONCE, swing/trades/entry.py:60. reconciliation_auto_correct.py:2188-2193 docstring names the equity_delta/snapshot_mismatch -> account_equity_snapshots branch; :2194 onward begins with fill_id (the census's claim that the branch is not implemented is read consistent; the plan cell verifies the full body).
>
> F-F2 -- RULED: (A) PER-SITE WIDENING, NO RE-BASE -- but with the CLASS discipline attached, because (A) as the cell wrote it is the instance patch the register refuses.
> - Why not (B): the 18 handlers' MESSAGES and RETURNS presume the semantics of an API/network failure. Re-basing makes a deterministic response-shape defect flow into 'Refresh failed (transient/network)' (cli_schwab.py:304) and into any retry-on-transient path -- a WRONG REASON on the surface, the D38 fourth-facet class (a mislabelled refusal), and a retry of an error that cannot succeed. The redaction contract also rests on _RedactedMessageError being FIRST in the MRO; a two-base class carries that as an ordering invariant nobody tests. (B) trades an escape for a mislabel at up to 18 sites.
> - Why (A) is not enough as written: four tuples widened is a bounded search reported as a total (D49). CONDITIONS: (1) every one of the 18 SchwabApiError handler sites is READ at plan time (the brief's F-F2 discipline, which I wrote for the re-base case and which binds here too) and each is put in exactly ONE of three states, listed in the plan: WIDENED (parity added to the tuple, and the message text made true for a parity error where the existing text names transience); COVERED (an explicit SchwabSchemaParityError clause precedes it in the same try -- the five the census names, order verified per site); or UNREACHABLE (the try body cannot raise parity: no mapper or normalizer runs inside it -- stated per site by reading the callee, not by the tuple). (2) A CLOSURE TEST, the instrument this class lacked: an AST walk over swing/ asserting every except clause naming SchwabApiError is WIDENED or COVERED, with the UNREACHABLE set spelled in the test as its exemption list, each with its reason, so a 19th handler written next month goes RED instead of re-opening D34 silently. (3) The four operator-path escapes the census names (entry_auto_fill.py:383, exit_auto_fill.py:759, cli_schwab.py:1478/:1490) are WIDENED; entry/exit auto-fill's existing kind=error / operator_typed result is the correct landing (RD's F-F1 (a) if he takes it -- I do not rule it, I note the composition: under (a) my widening IS the fix for C1-01; under (b) the widened tuple must route to his refusal instead; the plan states which after his ruling lands).
> - ReservedJournalFieldError(Exception): CONCUR with the cell -- per-site ClickException, NO re-base. A ValueError base would be SWALLOWED by the broad ValueError handlers at cli.py:4611/:4932 and every reconcile-path ValueError catch: that converts a loud escape into a silent mis-catch, the wrong direction. Its docstring's deliberate base stands. Same per-site read + closure discipline: the seven raise sites' reach onto operator paths is the list, and the test asserts each operator root that reaches a raise site carries the ClickException translation.
>
> F-F4 -- RULED: (a) DECLARE BY CLASS, with the declaration made a CHECK the code performs, not a paragraph.
> - CONDITIONS: (1) one pin per class proving the class stays LOUD (a raw-planted invalid row reaches the 500 carrying the invariant text; a CallerHeld* raised under a caller-held tx reaches the traceback) -- the cell's own example, taken. (2) Each declared class cites its WRITE-SIDE constraint (the CHECK / trigger / __post_init__ mirror under gotcha #11, or the fresh connect() per root for PROG-TX). A class with NO write-side constraint is NOT DECLARABLE -- an invariant the schema does not enforce and the reader would 500 on is a FINDING for my register, not a declaration; the plan lists any such class by name with its search. This is the schema-boundary defensive-scope rule (memory feedback_schema_boundary_defensive_scope) applied honestly: a reader may degrade on schema-prevented values ONLY where the schema prevents them. (3) NoActivePolicyError (C1-17): CONVERT, explicitly. It is an environment STATE the operator can fix (a policy exists to be set), exactly the F-F7 shape one level down; POST /config already handles it, so today the same condition is a refusal on one route and a 500 on the others -- the D35 unactionable-surface class in a status. Typed refusal naming the config command, on every root that reaches it; the closure test from F-F2's shape covers it.
> - Read-path closes (F4's 26) ride D39's shape as the census maps them; no separate ruling.
>
> F-F5 -- RULED: (a) UNIFORM ascii_safe on the 98 exception-text ClickException sites, plus the CLOSURE test as the instrument. CONDITIONS: (1) the premise in the plan is CORRECTED, not deleted: the crash is unreachable where reconfigure works, and cli.py:26-30 preserves the ORIGINAL encoding on embedded consoles and non-TextIOWrapper streams -- so the crash remains REACHABLE there and 'mojibake, not a crash' is a property of the console, not of the code. The RED discriminator stays the R3-1 form (.encode('cp1252') on the constructed Error: line). (2) ascii_safe stays where it is (swing/trades/entry.py:60) or moves to an EXISTING module; a new shared module is a section-3 tripwire and is NOT granted by this ruling. (3) The closure test asserts by AST that every ClickException argument referencing an exception variable or a message attribute passes through ascii_safe or safe_text -- the cell's proposal, taken; cli.py:1950 joins :1936 as the two named instances.
>
> F-F6 -- RULED: CARVE-OUT GRANTED (a), as the FILE LIST, and the AL-7 docstring rides IN.
> - swing/trades/: reconciliation_auto_correct.py, reconciliation.py, entry_date_correction.py, schwab_reconciliation.py, account_equity_snapshots.py, daily_management.py, hypothesis.py, risk_policy.py, exit_auto_fill.py, entry_auto_fill.py; exit.py ONLY if C1-24's service twin lands there (named by amendment when it does); entry_intent_assignment.py ONLY after C2-16 is read and confirms a site. swing/data/: db.py (C2-21), yfinance_audit.py (C2-10), repos/review_log.py (C2-15). audit_service.py is not carve-out-governed.
> - BOUNDS: guard-and-handler edits only (except tuples, typed translations, the D39 rollback-cleanup shape with both-verbs-fail proxies); NO schema; NO new module; NO behaviour change beyond the census rows; a file added to the list mid-arc is an AMENDMENT posted to me, not a self-grant. This is the invariant's default posture re-asserted on the arc that follows.
> - AL-7 docstring (reconciliation_auto_correct.py:2188-2193): IN, ONE comment-only commit, under the discharged-deferral rule (harness 5.1): re-verify EVERY claim in the docstring against :2194 onward, including the branches to be kept; delete the branch the code does not implement; the corrected docstring says what the code does TODAY and promises nothing. Verified docs-only by grep of tests/ for the docstring's text before it lands (the clearance-attaches rule's precondition).
>
> F-F7 -- RULED: (a) ONE BOUNDARY PER SURFACE, IN EXISTING MODULES. (b) REFUSED: an exemption from 'a 500 is never a refusal' written to cover one type is the D28 shape (a rule with a known-benign hole is how it erodes), and this specific type has a known, single, operator-actionable fix -- the definition of a refusal. (c) REFUSED: 113 sites is the instance patch.
> - Web: an exception handler for SchemaVersionMismatchError registered inside the existing _register_exception_handlers (app.py:148), rendering a typed 503 page with the existing message naming swing db-migrate. This is the boundary that MATTERS: cli_cmd.py:47 already fail-fasts at START, so the uncovered case is a DB migrated UNDER a running server -- the exact shape of the 22-I W0 hazard (a pre-merge swing web serving a post-migration schema) -- and a 503 is the honest status for it.
> - CLI: a click.Group subclass with an invoke override in cli.py, catching ONLY SchemaVersionMismatchError and converting it to ClickException with the existing message. The root-inheritance concern is answered by scope: one type, one meaning, raised by connect() before any command logic runs; nothing else is caught there. CONDITIONS: (1) db-migrate's own path must NOT be altered by the override (it reaches ensure_schema, not connect(); a test runs db-migrate through the group against a stale-version fixture and asserts it MIGRATES); (2) pins: a CliRunner invocation of any connect()-bearing command against a wrong-version fixture DB asserts exit 1 and the message with NO traceback; a TestClient GET against a wrong-version DB asserts 503 and the message; both RED-first on the current tree (a traceback / a 500 today).
>
> TRIPWIRES for this arc, stated: F-F6 is the one crossed (granted above); F-F7(a) adds a class inside cli.py and a handler inside app.py -- no new module; no schema; no dependency; no standing process. Any of those appearing in the plan is a fork back to me.
>
> NOTED, not ruled: the cell ended at 405,207, over the cap -- a fresh cell off the committed census is right (the orchestrator's). The brief-vs-disk deltas on my section 1 (78/38/17 vs 81/32/28 by the cell's instrument) are the seed-vs-measurement class; the census's numbers are the ones of record from here and my brief is amended by replacement at those lines when the plan lands (I will do the edit; it is my content).

**Composition, stated by the orchestrator:** RD ruled F-F1 (a) (above), so under CHARC's F-F2 condition (3) the WIDENING of the four operator-path tuples IS the fix for C1-01. The widened tuple lands on the existing `kind="error"` / `operator_typed` result, and RD's pins 1(ii) and 1(v) apply to it. **All six forks are RULED; the plan loop may open.**

| fork | ruler | status |
|---|---|---|
| F-F1 (web entry/exit form: degrade vs refuse on `SchwabSchemaParityError` / BANK-3) | RD | **RULED (a)** 07:29Z, block-quoted above; + C1-27 |
| F-F2 (`SchwabSchemaParityError` fix shape: per-site widening vs re-base; `ReservedJournalFieldError` base) | CHARC | **RULED (A)** + 18-site three-state read + AST closure test; `ReservedJournalFieldError` stays on `Exception` |
| F-F4 (census scope: invariant / programming-guard escapes DECLARED by class vs converted) | CHARC | **RULED (a)** declare by class with write-side citations; `NoActivePolicyError` CONVERTED |
| F-F5 (section 2.7a: the cp1252 premise; uniform `ascii_safe` + a closure test vs per-site) | CHARC | **RULED (a)** uniform `ascii_safe` + AST closure; premise corrected, not deleted |
| F-F6 (phase-isolation carve-out file list; the 22-I AL-7 docstring rider) | CHARC | **GRANTED** as the file list; AL-7 docstring IN (one comment-only commit) |
| F-F7 (`SchemaVersionMismatchError` on 113 roots: one boundary per surface vs declare vs per-root) | CHARC | **RULED (a)** typed 503 in `app.py` + `click.Group` subclass in `cli.py`; (b)/(c) REFUSED |

(F-F3 is RULED in the brief. Its declared list is read-verified in census section 5.)

## Method log (round 0)

Every count in the census states its method in place. Instruments and outputs are in `review-transcripts\22-f-plan\r0-measurements\`, and all were run on `79035d59` with `encoding='utf-8'` on every read.

1. `escape_census.py` (library) + `roots_report.py`.
   - What it does: static exception-escape analysis over `swing/`.
   - Scope: 147 operator roots (72 web handler functions, 75 CLI commands across `cli.py`, `cli_schwab.py`, `cli_config.py` and `cli_latches.py`).
   - Outputs: `roots.json` (per root: its own handler tuples, and every escaping type with every terminal raise origin and one witness chain); `exc.json` (82 exception classes with MRO).
   - Version: the second version adds dispatch-registry resolution (found necessary when `_TIER2_HANDLERS` hid 5 `ReservedJournalFieldError` raises).
2. `classify.py` produces `origins.json` (every (type, origin) pair with its enclosing function and roots). `triage.py` produces `triage.json` and `cand.txt` (the INV-MODEL / INV-TYPE / PROG-TX / ENV-SCHEMA / CAND classes; CAND listed per root).
3. `tx_census.py` produces `tx.json`: 31 explicit `BEGIN` sites, facets F1-F4, and reverse reach to operator and pipeline roots.
4. `rb_census.py` produces `rb.json` and `f4.txt`: 33 `.rollback()` calls with context and guard, and 58 operator roots with a bare `finally: close()` after a commit-reaching try body.
5. `clickexc_7a.py` produces `clickexc_7a.tsv`: 99 `ClickException` sites that wrap exception text. By read, one is fully `ascii_safe`.
6. Inline one-off measurements (commands reproduced in the census rows):
   - the AST tuple and broad handler counts at `79035d59` and at `b8f80e91` (via `git show`);
   - `grep -rn 'BEGIN IMMEDIATE' swing` (158/40 `.py`);
   - `grep -rn 'suppress(sqlite3.Error)'` (17 hits: 9 in `schwab_reconciliation.py`);
   - the AST `with conn:` count (58);
   - an AST list of every handler naming `SchwabApiError` / `SchwabSchemaParityError` / `_RedactedMessageError` (18 + 5);
   - `git archive b8f80e91 swing` → instrument re-run → `exc_b8f` (81 classes).
7. READS, file:line in the census rows:
   - `app.py:148-178`
   - `cli.py:10-32, 1147-1182, 1928-1952, 2255-2296, 4585-4600`
   - `routes/trades.py:1612-1630, 3100-3160`, and the `:842` early check (by grep)
   - `routes/latches.py:249-300, 340-372, 820-930`
   - `entry_auto_fill.py:340-400`
   - `exit_auto_fill.py:750-775`
   - `entry.py:2290-2318`
   - `exit.py:150-170`
   - `state.py:140-147`
   - `reconciliation_auto_correct.py:2186-2206`
   - `cohort_provenance_correction.py:2385-2440`
   - the `schwab_reconciliation.py` suppress sites
   - the terminal raise lines of every custom-type origin (`sites.txt`, first pass)
   - brief, register rows, the 22-B exec-ledger rulings (R1-3-SURFACES, R8, R8-SCOPE, B, B2-01), the harness section 5 / 5.1 paragraphs named in the dispatch

**Known instrument error, corrected by read:** `tx_census`/`rb_census` label `cli.py:4597` "chained". The rollback is unguarded; an OUTER handler raises `from`. See census C2-05.

**Discharged:** none. **Open items carried to the plan:** k3 and k4 (census section 7); the 22-A3 S8 item-8 message sites (census 4.3); every STATIC row (census sections 3 and 4).

## Round 1 -- findings and PROPOSED dispositions (awaiting the orchestrator; nothing fixed)

Reviewer severities are Codex's. Every finding is classified TASK-BEARING by the reviewer and by this cell, and none is contested.

| id | reviewer | concerns | finding (condensed; verbatim in `.codex-review-r1.txt`) | proposed disposition |
|---|---|---|---|---|
| R1-01 | major, task-bearing | map row R1 / T-A1 | R1 claims "both POST re-renders", but only the ENTRY re-render is tested (A1-e). The exit POST's `except ValueError` re-render (`routes/trades.py:3137-3150`) calls `build_exit_form_vm`, whose fetch raises parity -> 500 today | **FIX.** Add A1-e': a `POST /trades/{id}/exit` that fails `record_exit`'s `ValueError` (shares > remaining) while orders raise parity. Pre-fix: **500**. Post-fix: **400** re-render, advisory names `SchwabSchemaParityError`. Per RD 1(iii) it asserts NOTHING about the anchor round-trip |
| R1-02 | major, task-bearing | T-F10 / section 0.4 | The B-04 test cannot be built with the specified proxy. `fail_sql_prefix` fails EVERY match, and the first `PRAGMA foreign_keys` is the pre-migration read at `db.py:564`. `db-migrate` reaches `ensure_schema` -> `open_connection` (`db.py:1054`), not `connect`. The plan also does not name the boundary that re-reads the version | **FIX.** (i) Intercept `swing.data.db.open_connection`. (ii) Add a proxy mode that fails only the FIRST `PRAGMA foreign_keys=` statement issued AFTER `executescript` has returned. That is the `finally` restore; the pre-script `PRAGMA foreign_keys=OFF` at `:571` also matches the prefix, so the ordering condition is needed. (iii) Name the boundary as `cli.py db_migrate`: it catches `BaseException` around `ensure_schema`, re-reads `schema_version` on a FRESH plain-`sqlite3` read-only connection, emits the WARN line and exits 0 at the target, and otherwise re-raises. The CONTROL raise before the COMMIT stays |
| R1-03 | major, task-bearing | section 5 / AL-8 / T-D1 | Ruling F-F4 (2) requires each declared class to cite a write-side constraint. INV-MODEL is declared from ONE exemplar, so its members are unverified and the pin stays green on a member that has no constraint | **FIX by enumeration + split.** Measured here from `triage.json`: 2,446 triples = **516 distinct raise origins in 118 functions**. (i) New task T-D0 commits the 118-function roster as test data. A closure test asserts the roster equals the AST set (every `__post_init__`/`_require_*`/`_validate_*` in `swing/` whose body raises). For each PERSISTED-ROW member (built from a DB row), the exec ledger records the quoted CHECK/trigger. (ii) SERVER-COMPUTED members (view models, `metrics/*`, `config`) have no schema constraint, so they are NOT declared: they become finding **FND-4 "INV-COMPUTED"**, listed by name with the roster search, per the ruling's own clause. (iii) AL-8 is deleted by replacement. The exemplar pin T-D1 stays as the loudness pin for the persisted subset |

## Round 1 gate -- ORCHESTRATOR dispositions (2026-09-25)

Validity (read on disk): the banner is `model: gpt-5.6-luna`, and `reasoning effort: medium` equals `~/.codex/fast.config.toml`; `^ERROR` 0; the `tokens used` footer is 134,901; the anchored `NEW_CRITICAL_MAJOR_FOUND`, with `NO_NEW_CRITICAL_MAJOR` 0; `exit-r1.txt` 0. **R1 COUNTS** (counted round 1 of 3). Commits `c4c035c3` and `708bd61d` have empty trailers.

**Fix authorizations (written; for the continuing cell):**
- **R1-01: FIX as proposed.** Test A1-e' (exit POST: the `record_exit` `ValueError` plus the parity raise on the orders fetch; RED 500, then GREEN 400 re-render with the advisory naming `SchwabSchemaParityError`). No anchor assertion, per RD 1(iii).
- **R1-02: FIX as proposed.** Intercept `swing.data.db.open_connection`; the proxy fails only the first `PRAGMA foreign_keys=` AFTER `executescript` returns; the named boundary is `cli.py db_migrate` (the fresh plain-sqlite3 read-only version re-read; WARN + exit 0 at target, re-raise otherwise).
- **R1-03: FIX as proposed.** T-D0: a 118-function INV-MODEL roster plus an AST-equality closure test; each DB-row member quotes its CHECK or trigger in the exec ledger; server-computed members become **FND-4 INV-COMPUTED** (CHARC F-F4 (2)'s own clause); AL-8 removed.

**HELD for CHARC (one packet; no counted round opens until it lands):**
- The F-F2 COVERED definition (§1.2 row 6 / AL-3).
- Amendments A-1, A-2 and A-3 (§9).
- The encoding confirmations: `NoActivePolicyError` as one app-level 503 on the web, per root on the CLI; INV-TYPE's citation; R21, the 17 read/cache roots DECLARED; FND-1, FND-2 and FND-4.

**RD, CC as a fact correction only:** RD's F-F1 item 3 cited `mappers.py:428` (a None-returning path). The entry form's resolver is `schwab_reconciliation.py:521` `_resolve_match_quantity -> float` (read at this seat: `entry_auto_fill.py:88` imports it; `:445` calls it). So None and NaN are unreachable there, while inf and `[0,1)` are reachable. RD's ruling (a) and its `math.isfinite` guard are unaffected; posted for dissent only.

**Depth:** 348,615. Fixes + R2 in the same cell would cross the 400K cap, so they go to a FRESH cell off the committed plan, this ledger and `r1/`, after CHARC's packet lands.
