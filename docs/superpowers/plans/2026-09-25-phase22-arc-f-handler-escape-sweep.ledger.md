# Phase 22 arc 22-F plan ledger (handler-escape + transaction-hygiene sweep)

**Branch:** `22-f-plan`, cut from main @ `79035d59`. **Census:** `2026-09-25-phase22-arc-f-handler-escape-sweep.census.md` (this directory). **Plan:** not yet written. Round 0 does not produce one.
**Evidence (durable, outside the repo):** `C:\Users\rwsmy\swing-data\review-transcripts\22-f-plan\`

## Round table

The DEPTH column is filled by the orchestrator from `scripts/cell_depth.py --agent <id>`. It is never filled by the cell.

| round | kind | tier / model | verdict | task-bearing findings | tokens used | depth (orchestrator) | notes |
|---|---|---|---|---|---|---|---|
| R0 | premise + fork census (no Codex) | - | - | - | 0 Codex | **405,207 — OVER the 400K cap** (`cell_depth --agent`, read at return 2026-09-25) | census committed; the cell does NOT resume -- the plan loop goes to a FRESH cell off this committed census + the evidence dir; fork packet F-F1..F-F7 routed via the orchestrator |

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

| fork | ruler | status |
|---|---|---|
| F-F1 (web entry/exit form: degrade vs refuse on `SchwabSchemaParityError` / BANK-3) | RD | **RULED (a)** 07:29Z, block-quoted above; + C1-27 |
| F-F2 (`SchwabSchemaParityError` fix shape: per-site widening vs re-base; `ReservedJournalFieldError` base) | CHARC | OPEN |
| F-F4 (census scope: invariant / programming-guard escapes DECLARED by class vs converted) | CHARC | OPEN |
| F-F5 (section 2.7a: the cp1252 premise; uniform `ascii_safe` + a closure test vs per-site) | CHARC | OPEN |
| F-F6 (phase-isolation carve-out file list; the 22-I AL-7 docstring rider) | CHARC | OPEN |
| F-F7 (`SchemaVersionMismatchError` on 113 roots: one boundary per surface vs declare vs per-root) | CHARC | OPEN |

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
