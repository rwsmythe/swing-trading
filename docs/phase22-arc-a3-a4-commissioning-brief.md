# 22-A3 + 22-A4 — the `record_entry` contract's two halves (commissioning brief)

**Commissioned by CHARC 2026-09-02 on the operator's word ("let's get working on those in your
proposed order"). Two arcs, STRICTLY SEQUENCED: 22-A3 dispatches now; 22-A4 dispatches only after
22-A3 merges** — both touch `record_entry`'s result contract, and two arcs on one seam in parallel
is the composition class (harness-architecture §5.1). Origin: the R9-03 contract (CHARC, 2026-09-01)
and its split (2026-09-02) — clauses 1+3 shipped in 22-A; clause 1 stops at the service boundary
(B's R11-02); clause 2 was reverted because its precondition does not exist (R10-02/03).

**The governing contract, verbatim from `swing/trades/entry.py:203-206`:** *`EntryResult` is a
statement about the DURABLE STATE OF THE LEDGER, never about whether every subsequent step
succeeded.* Both arcs make that true one layer further out.

---

## 22-A3 — THE CALLER HALF: a contract with no reader is not yet a contract

### Premises, verified in code 2026-09-02

- `EntryResult.post_commit_warnings: tuple[str, ...] = ()` exists (`entry.py:215`) and is populated
  at `:522` / `:543`. **Grep across `swing/`: four hits, all inside `entry.py`. ZERO readers.**
- **`swing/web/routes/trades.py:1490` calls `record_entry(...)` with NO assignment** — the result is
  discarded (a Bug-fix-AB comment explains why `trade_id` was no longer needed; the warnings field
  did not exist then). **CORRECTED 2026-09-02 (orchestrator, verified at the source; the brief's
  original "inside the same `try`" was CHARC's wrong premise):** the `try` spans `:1483`–`:1959`
  and **`build_dashboard` sits at `:1992`, OUTSIDE every `try`** — so the fix must ADD a guard, not
  narrow an `except`. **And the consequence is worse than a bare 500:** `entry-form-` is in
  `_ROW_TARGET_PREFIXES`, the app-wide handler renders `trade_form_error` at status 500, and the
  HTMX config swaps 4xx/5xx — **a post-commit render failure paints the trade-form error INTO the
  entry form's OWN ROW, at the identical surface, class and position a duplicate/hard-cap REFUSAL
  uses. The operator cannot tell a refused entry from a durable one.** Retry-inviting; belt-mitigated
  only by `ux_trades_one_open_per_ticker`.
- `swing/cli.py:790` assigns `result` and never reads `post_commit_warnings`.
- **R11-03's twin:** the R9-05 cleanup-warning logs — `entry.py:748` region and the
  `cohort_provenance_correction.py` sites at `:2284`, `:2353`, **`:2445`** (the SIXTH — ERROR log +
  `raise cleanup_error` on the PREVIEW leg, success-path-reachable; found by the plan reading every
  `log.error(` in the module; **a roster in a brief is a FLOOR, ratified 2026-09-02**), `:2693`,
  `:2700`, `:3341` — need the same best-effort containment R10-04 established: **a failing
  logging handler must never change a function's result or which exception propagates.**

### What 22-A3 ships

1. **The web route CONSUMES the result.** After `record_entry` returns, the entry is durable by
   contract. (a) Assign the result. (b) **Any failure in the post-entry render path
   (`build_dashboard`, the OOB partials) becomes a DEGRADED-SUCCESS response naming the `trade_id`
   and the failure** — never a 500, never an error-form re-render that reads as "not entered".
   (c) `post_commit_warnings` are surfaced to the operator in the response (a banner/OOB partial
   naming each warning). The HTMX gotchas bind: the degraded-success response must be a valid swap
   shape (the `204` + `HX-Redirect` / OOB rules in CLAUDE.md), and **the operator-witnessed browser
   check is binding** for this surface.
2. **The CLI consumes the field:** warnings printed (ASCII), exit status stays SUCCESS — the entry
   is durable and the exit code is a statement about the ledger.
3. **R11-03 twin containment** at the five sites above: the cleanup log is wrapped so a raising
   handler is swallowed-and-noted and the ORIGINAL error (or result) is what propagates. Same shape
   as the R10-04 fix, applied by READING each site, not by grep.

### Discriminating tests (compute under BOTH paths per the regression-arithmetic rule)

- **(a)** Inject a post-commit warning → the web response is a success shape carrying the warning
  text; exactly ONE trade row; the pre-fix path (discarded result) FAILS by never rendering it.
- **(b)** Make `build_dashboard` raise after `record_entry` → response is DEGRADED SUCCESS naming
  `trade_id`, status not 5xx, row count ONE; the pre-fix path FAILS with a 500 over a durable row.
- **(c)** CLI: warnings present → printed, exit 0; pre-fix prints nothing.
- **(d)** R11-03, one per twin site: a logging handler that raises at the cleanup log must not change
  the function's return value or the exception class that escapes — assert the ORIGINAL propagates.
  A test asserting only "no crash" passes an implementation that swallows everything; assert the
  identity of what escapes.
- **(e)** The belt still holds: a retry against the durable entry is refused by
  `ux_trades_one_open_per_ticker` with a message naming the existing trade.

### Envelope and declared limitations

`swing/web/routes/trades.py` · `swing/cli.py` · `swing/trades/entry.py` (log containment, **plus — ruled
2026-09-02, Q1 — outcome-corrupting exception-formatting on the post-commit path of `record_entry`
wherever it occurs**: `entry.py:517`'s `{post_commit_error!r}` sits one line above the guard that
implements clause 1, and a raising `__repr__` there converts a durable success into a failure; the fix
is one token, `safe_text(post_commit_error)`) · **`swing/web/middleware/request_id.py` (ruled 2026-09-02,
Q2 — FOLD IN, BOUNDED to the plan's S8 item 6 correction + test shape ONLY, no middleware sweep):**
`RequestIdMiddleware` is OUTERMOST and access-logs AFTER `call_next`, so a raising log handler there
destroys the very degraded-success response this arc builds — the arc's claim would be false one frame
outside its own fix; further sites of the class are banked follow-ons ·
`swing/trades/cohort_provenance_correction.py` (log containment ONLY) · templates for the warning
partial if needed. **NO schema. NO change to `record_entry`'s transaction semantics** — the
commit-raises path keeps re-raising (that is 22-A4's). Declared, with reason: the belt covers only an
OPEN same-ticker retry; a ticker closed between attempts is unbelted until 22-A4.

### Process

Opus 5 / **high** for both writing-plans and executing (locked scope, no design fork). A-loop per
the recipe; **B at the orchestrator's gate on the tree being merged**, findings dispositioned under
introduced-vs-banked; declared envelope + accepted limitations WITH reasons in every prompt; plan on
`main` before its branch is deletable. The plan routes to CHARC only if it wants to touch anything
outside the envelope above.

---

## 22-A4 — THE ATTEMPT-IDENTITY PRIMITIVE, and clause 2's return on top of it

**Dispatches AFTER 22-A3 merges. Not before.**

### Why it exists (the precondition clause 2 lacked)

Clause 2 said: if `commit()` itself raises, resolve by READ. Implemented faithfully it opened two
false-success paths (R10-02, R10-03) because "a read can settle it" needs two things the code cannot
do today: **VISIBILITY** (a read on the writer's own connection inside an unresolved transaction is
the writer quoting itself) and **IDENTITY** (a rolled-back rowid is REUSABLE — `sqlite_sequence`
rolls back with the insert, `AUTOINCREMENT` does not pin it — so `WHERE id = ?` can confirm a
concurrent writer's row as ours). Both are CLAUDE.md gotchas now. The primitive supplies identity;
the read discipline supplies visibility.

### RD's three constraints — BINDING, verbatim (ruled 2026-09-02)

1. **CO-DURABLE:** the token is written IN THE SAME TRANSACTION as the row it identifies — its
   presence exactly co-committed with the row's. Anything else is a stamp (gotcha #30).
2. **UNIQUE PER ATTEMPT:** never reusable across attempts; survives rollback-and-retry without
   collision. Rowid fails by construction.
3. **DURABLE-VISIBILITY READ:** the confirming read runs where only committed state is visible — a
   FRESH connection, or after a PROVEN resolution. A failed rollback VOIDS the read.

### CHARC's preferred shape — for the plan to VERIFY, not inherit

`trades.attempt_id TEXT` (nullable — legacy rows NULL), a client-generated `uuid4` produced by the
service at the start of the attempt and written **in the same INSERT** as the row; `CREATE UNIQUE
INDEX ... ON trades(attempt_id) WHERE attempt_id IS NOT NULL`. **Migration 0038, ADDITIVE** — one
`ADD COLUMN` + one index + the version bump; no rebuild. Mirrors in ONE commit (#11): the `Trade`
dataclass field, the repo INSERT column list, the `_row_to_trade` reader, and **a static closure
check that the entry INSERT's column list CONTAINS `attempt_id`** (co-durability made mechanical: a
future INSERT path that omits it fails loudly). If the plan finds a better shape that satisfies the
three constraints, it says why; if it cannot satisfy all three, it STOPS and routes.

### Clause 2 returns — the ruled form

If `commit()` raises: (i) attempt a rollback; **if the rollback itself raises, the connection is
DISCARDED and NO read is attempted on it** (R10-02's exact hole, closed by assertion not comment);
(ii) open a FRESH connection; (iii) `SELECT ... WHERE attempt_id = ?`; present → return SUCCESS
with a `post_commit_warnings` entry stating the commit's own return was lost and durability was
confirmed by attempt identity; absent → re-raise the original. **Both `_entry_transaction` paths
(`immediate=True`/`False`) are bound.** The route/CLI from 22-A3 already consume the result, so the
warning reaches the operator with no further caller work — which is why 22-A3 goes first.

### Discriminating tests (RD's two + CHARC's three; each computed under both paths)

- **(RD-a)** rollback-raises-then-read must NOT return SUCCESS — kills R10-02 by assertion.
- **(RD-b)** a concurrent insert taking the same rowid must NOT be confirmed as ours — kills rowid
  identity; the fixture plants a same-id row with a different `attempt_id`.
- **(c)** `commit()` raises with the row landed → SUCCESS via the fresh-connection read, warning
  present, row count ONE.
- **(d)** `commit()` raises with the row absent → re-raises the ORIGINAL exception class.
- **(e)** CO-DURABILITY: a rolled-back attempt leaves NO `attempt_id` anywhere; a committed attempt's
  `attempt_id` is present exactly when its row is. And the static closure check fails when
  `attempt_id` is removed from the INSERT column list (the mutation test, run and shown red).

### §3 and routing

**New schema = §3 tripwire — the plan routes to CHARC.** **The token is admissibility machinery
(what makes a durability read EVIDENCE) — the plan routes to RD** for the three constraints'
encoding; his gate. Envelope: `swing/trades/entry.py`, `swing/data/` (migration 0038, models, repo),
tests. Nothing in `swing/web/` or `swing/cli.py` (22-A3 already did the caller side).

### Process

Writing-plans at Opus 5 / **xhigh** — stated reason: a wrong answer here is confident and hard to
detect (the whole class is "a read that LOOKS conclusive"), and the plan must prove three
constraints hold rather than assert them. Executing at Opus 5 / high. A-loop per the recipe; B at
the orchestrator's gate; declared limitations WITH reasons; plan on `main` before branch deletion.
**The 22-A precedent binds: a ruled mechanism carries its admissibility preconditions and names
which exist today** — the plan's §1 re-derives all three constraints against the code before
anything is designed.
