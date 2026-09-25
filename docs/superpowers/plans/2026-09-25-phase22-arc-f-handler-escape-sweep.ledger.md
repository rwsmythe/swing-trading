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

| fork | ruler | status |
|---|---|---|
| F-F1 (web entry/exit form: degrade vs refuse on `SchwabSchemaParityError` / BANK-3) | RD | OPEN |
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
