# 22-A3 -- The `record_entry` caller half (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** make `record_entry`'s result -- *a statement about the DURABLE STATE OF THE LEDGER* --
readable by the two callers that exist, so that **THE ROUTE AND THE CLI** stop presenting a failure
after a durable commit as an entry failure. *(The scope of that claim is narrowed deliberately and
stated at S2.0: one exposure lies outside both callers and outside the envelope, and it is flagged
rather than fixed.)*

**Architecture:** three edits and one shared idiom. (1) `swing/web/routes/trades.py` ASSIGNS the
`EntryResult` and puts **ONE CONTINUOUS guard around everything from the connection to the returned
response** -- the close, the warning assembly, the page refresh and the response construction -- so
that once `result` is bound nothing between there and the return can report a durable entry as a
failure; a failure inside it becomes a DEGRADED-SUCCESS 200 naming the `trade_id`, delivered as an
out-of-band swap into a notice container present on every page the entry form is reachable from.
(2) `swing/cli.py` takes the same single guard around its close AND its output, prints
`post_commit_warnings` ASCII-coerced, and keeps exit status 0. (3) an `ascii_safe` / `safe_text` / `log_contained` /
`log_contained_note` idiom in `swing/trades/entry.py`, applied at **the six CLEANUP-log sites** (the
brief names five; a sixth of the identical class is at `cohort_provenance_correction.py:2445` --
S1.4), so a raising logging handler can never change which exception escapes **from a cleanup
handler**. *(That scope is exact, not rhetorical: four other logging calls exist in `entry.py`, all
of them PRE-commit and of a different semantic class -- S1.4's closing note.)*

**Tech Stack:** Python 3.14 (`pyproject` targets >=3.11), FastAPI + Starlette `Jinja2Templates`
(autoescape forced ON, `swing/web/app.py:123-146`), HTMX 2.x with a `responseHandling` override,
`click` 8.3.1, `pytest` with `-n auto` in `addopts`, `ruff check swing/` (`E,F,W,I,N,UP,B,SIM`).

**Spec:** [`docs/phase22-arc-a3-a4-commissioning-brief.md`](../../phase22-arc-a3-a4-commissioning-brief.md)
(the 22-A3 half ONLY), which derives from
[`docs/22-a-merge-request.md`](../../22-a-merge-request.md) S4.4 -- the CHARC+RD split ruling of
2026-09-02. **Plan base:** `0698f3bb` (branch `22-a3-plan`).

> ## REVIEW STATUS: **NOT DECLARED CONVERGED. THE A-LOOP STOPPED AT THE MANDATED ROUND-5 GATE.**
>
> Five adversarial rounds ran at the binding `strong` tier (`gpt-5.6-sol` / effort `high`), all five
> mechanical assertions passing every round. **60 findings, 11 CRITICAL, 38 MAJOR, 11 MINOR; ZERO
> reopened and ZERO reverted across all five rounds; CRITICALs went 3 -> 4 -> 3 -> 1 -> 0.** Round
> 5's findings are adjudicated and FIXED, and a dedicated self-sweep (six uncounted `SS-N` items)
> has been run over the settled artifact.
>
> **What remains is ONE confirming round**, which the recipe's round-5 gate reserves for the
> orchestrator's approval. Full ledger with per-round assertions and per-finding dispositions:
> `.copowers-findings.md` at the worktree root; raw transcripts `.codex-review-r1..r5.txt`.

**Baseline measured at plan time on `0698f3bb`, before any change:**
`python -m pytest -m "not slow" -q` -> **12077 passed, 13 skipped** in 849s. The executing arc's
Task-8 run is compared against THAT number, not against a remembered one.

---

## Global Constraints

- **ENVELOPE, verbatim from the brief:** `swing/web/routes/trades.py` * `swing/cli.py` *
  `swing/trades/entry.py` (**log containment ONLY**) *
  `swing/trades/cohort_provenance_correction.py` (**log containment ONLY**) * templates for the
  warning partial if needed. **NO schema. NO change to `record_entry`'s transaction semantics** --
  the commit-raises path keeps re-raising; that is 22-A4's.
- **Branch:** all work on the arc branch; conventional commits (`feat(web):`, `fix(trades):`,
  `test(...)`). **ZERO `Co-Authored-By`. No `--no-verify`. No amend.**
- **TDD:** failing test -> see it fail -> minimal implementation -> see it pass -> commit, one
  red/green cycle per task. **Every regression assertion is computed under BOTH the pre-fix and the
  post-fix path** -- this plan states both values for every test it specifies.
- **ASCII in user-facing strings** reaching stdout/CLI (Windows cp1252; `pytest` `capsys` hides it).
  HTML output is UTF-8 and is not bound by this, but the added HTML copy is ASCII anyway for
  uniformity.
- **`ruff check swing/` clean.** Test-file lint is out of scope; match each test file's existing
  style.
- **The operator-witnessed browser check is BINDING for the HTMX surface** (S6). TestClient cannot
  see either browser-only failure mode.
- **Live DB is UNTOUCHED.** The migration set tops out at `0037_latch_order_mandate_links.sql`,
  whose last statement is `UPDATE schema_version SET version = 37` (read from the migration file --
  this plan deliberately did NOT open the operator's database, which carries real money-bearing
  trades). No task in this plan reads or writes it; every test builds its own `tmp_path` database.

---

## S0. THE HEADLINE -- what the operator sees today, measured rather than inferred

The brief says a post-entry render failure "presents as an entry failure over a durable trade -- a
500 the operator reads as *the entry did not happen*." **It is sharper than that, and the sharper
version is what makes this arc worth its cost.** Three facts, each read out of the code:

1. `swing/web/app.py:38-45` registers `entry-form-` in `_ROW_TARGET_PREFIXES`, and the entry form's
   root element is `<tr id="entry-form-{{ vm.ticker }}">`
   (`partials/trade_entry_form.html.j2:16`), so an HTMX submit from that form **is** a row-swap
   target.
2. `swing/web/app.py:149-172` -- the app-wide `@app.exception_handler(Exception)` -- renders
   **`partials/trade_form_error.html.j2` at `status_code=500`** for exactly that request shape.
3. `base.html.j2:60-64` overrides `htmx.config.responseHandling` with
   `{code: "[45]..", swap: true, error: true}`, so **a 5xx DOES swap into the target.**

Composed: a `build_dashboard` failure after a durable commit puts a red
`banner banner-degraded` alert **into the form's own row position** -- the *identical* surface, the
identical CSS class, and the identical location that `DuplicateOpenPositionError`, `HardCapError`
and the missing-pre-trade-fields refusal use at 400. **The operator cannot tell a post-entry render
failure from an entry REFUSAL.** The refusal reading is the retry-inviting one, and a retry is
belted only while the same ticker is still open (S1.5).

That is the whole arc: `record_entry` already tells the truth; nobody is listening.

---

## S0.1 THE ENVELOPE, AND THE ONE READING THIS PLAN MAKES OF IT

Every file this plan touches is named in the envelope, with ONE reading that deserves to be stated
rather than assumed:

**The brief's envelope clause "templates for the warning partial if needed" is read to include a
static, empty container `<div id="entry-notice"></div>` in `swing/web/templates/base.html.j2`.**
The reason it is needed is measured at S1.6: the entry form is reachable from `/watchlist`, and
`watchlist.html.j2` contains **none** of the four ids the success response swaps into. A notice
delivered into any of those ids is silently dropped on that surface -- which would ship the
arc's own failure mode (a warning with no reader) inside the fix for it. The container carries **no
VM field**, so the `base.html.j2` every-base-layout-VM-or-500 gotcha does not fire; it is inert
markup on every page.

**If the reviewing orchestrator or CHARC reads that as widening rather than as the clause's plain
meaning, the fallback is stated and costs one line:** put the same container in
`dashboard.html.j2` and `watchlist.html.j2` instead (the `trade-close-soft-warn` container at
`dashboard.html.j2:34` is exactly this shape, in exactly that file). The plan prefers base because
two copies of a container is the hand-maintained-roster failure in miniature. **This plan does not
otherwise touch a file outside the envelope, and it requests no extension.**

---

## S1. PREMISES, RE-DERIVED -- with the method that produced each, and three corrections

> The brief states its premises "verified in code 2026-09-02". Every one was re-derived here. **Two
> moved and one is incomplete.** Per the recipe's premise discipline they are REPORTED, not planned
> around silently -- and the two that moved make the case STRONGER, not weaker.

### S1.1 `post_commit_warnings` has ZERO readers outside `entry.py` -- **HOLDS**

    $ grep -rn "post_commit_warnings" --include=*.py --include=*.j2 . | grep -v "^./tests/"
    ./swing/trades/entry.py:207   (docstring)
    ./swing/trades/entry.py:215   (the field:  post_commit_warnings: tuple[str, ...] = ())
    ./swing/trades/entry.py:522   (population, the durable-warning path)
    ./swing/trades/entry.py:543   (population, the log-failed-too path)

Four hits, all inside `entry.py`. **Method note, because a grep bounds a family from BELOW and
nothing more:** the token here is a dataclass FIELD NAME, and a field read cannot be paraphrased --
any reader must spell `post_commit_warnings` or go through `dataclasses.asdict` / `astuple` /
`replace`. A grep for `asdict` and `astuple` across `swing/` returns no `EntryResult` consumer, and
the only two `record_entry` call sites in `swing/` are the two below. So the zero-reader claim is
**closed**, not merely un-hit. In `tests/` the field is read in exactly one file
(`tests/trades/test_22a_task9_entry_wiring.py`, 6 lines) -- the service's own contract tests.

### S1.2 `swing/web/routes/trades.py:1490` discards the result -- **HOLDS**; the brief's MECHANISM for what follows is **WRONG, and the truth is worse**

`record_entry(` at `:1490` has no assignment; the Bug-fix-AB comment at `:1486-1489` explains that
`result.trade_id` stopped being needed when the response became pure-OOB. That HOLDS.

**The brief then says: "The route then runs `build_dashboard` + template renders inside the same
`try`." It does not.** Measured structure of `entry_post` (the ONLY function-level `try`, by an
`awk` scan over lines 451-2059 for 4-space `try:` / `except` / `finally`):

    1482  conn = connect(cfg.paths.db_path)
    1483  try:
    1484      try:
    1490          record_entry(...)              <- no assignment
    1500      except MissingPreTradeFieldsException / SoftWarnError /
                     DuplicateOpenPositionError / HardCapError /
                     PatternEvaluationAnchorError / ValueError / sqlite3.IntegrityError
    1958  finally:
    1959      conn.close()
              # ---- NOTHING BELOW THIS LINE IS INSIDE ANY try ----
    1992  dashboard_vm = build_dashboard(...)
    1995  status_strip_html      = templates.get_template(...).render(...)
    1998  open_positions_html    = templates.get_template(...).render(...)
    2001  watchlist_section_html = templates.get_template(...).render(...)
    2039  hyp_recs_section_html  = templates.get_template(...).render(..., oob=True)
    2048  return HTMLResponse(Markup(...))

**Why the correction matters to the plan rather than being pedantry.** Two consequences:

- *Nothing local converts the render failure* -- so the fix cannot be "narrow an existing `except`";
  **it must ADD a guard around 1992-2056**, which is what Task 5 does.
- The conversion happens **one layer out**, in the app-wide handler, and that is what produces the
  refusal-shaped 500 fragment of S0. Had the failure been caught by the route's own
  `except ValueError` at `:1885`, it would have been re-raised anyway (that clause re-raises
  anything whose message lacks `chart_pattern`). **The brief's conclusion is right; its stated
  mechanism would have sent an implementer looking for the wrong edit.**

### S1.3 `swing/cli.py:790` assigns and never reads the field -- **HOLDS**

`result = record_entry(...)` at `:790`; after `finally: conn.close()` at `:833-834` the CLI reads
`result.warning` (`:836`), `result.watchlist_archived` (`:838`), `result.trade_id` (`:841`).
`post_commit_warnings` appears nowhere in `swing/cli.py` (grep: zero hits).

### S1.4 The R11-03 twin sites -- **THE FIVE ARE WHERE THE BRIEF SAYS. THERE ARE SIX.**

The brief's line anchors point at the MESSAGE STRING; the `log.error(` call is a few lines above
each. All five verified by READING each site, not by matching the anchor:

| # | site | the `log.error(` call | what escapes today | shape |
|---|---|---|---|---|
| 1 | `entry.py` write-path rollback | `:744` and `:752` (two branches of one `if conn.in_transaction`) | `raise cleanup_error from write_error` (`:759`) | except-inside-except |
| 2 | `cohort` preview savepoint, owned-tx branch | `:2284` | `raise cleanup_error from savepoint_error` (`:2291`) | except-inside-except |
| 3 | `cohort` preview savepoint, caller-held branch | `:2353` | `raise anomaly from savepoint_error` (`:2360`) | inside `except`; `anomaly` is a caught object |
| 4 | `cohort` apply-path rollback | `:2693` and `:2700` (two branches) | `raise cleanup_error from write_error` (`:2707`) | except-inside-except |
| 5 | `cohort` reader unwind | `:3341` | bare `raise` (`:3348`), re-raising `cleanup_error` | inside `finally`, inside `except` |

**AND A SIXTH, NOT IN THE BRIEF'S ROSTER:**

| 6 | `cohort` preview `finally` unwind | `:2445` | `raise cleanup_error` (`:2450`) | inside `finally`; `cleanup_error` is a variable holding a caught object |

It is the same class by construction -- `log.error(...)` immediately followed by a `raise` of a
specific exception object -- in the same file, in the same function family. **It was found by
reading every logging call in the module:** a grep for `log.` with the level alternation returns
exactly six call sites in `cohort_provenance_correction.py` -- `2284, 2353, 2445, 2693, 2700, 3341`
-- and the brief's roster names five of the six. Site 6 also reaches the class through a path the
others do not: **its `finally` runs on the function's SUCCESS path too**, so a failing sink there
converts a preview that otherwise returned into a raise of the wrong class.

**The brief's own instruction is what caught it:** *"applied by READING each of the five sites, not
by grep. This arc has been caught three times fixing one twin and leaving the other."* A
hand-enumerated roster is the same instrument as the count it replaced. **Site 6 is inside the
declared envelope** (`cohort_provenance_correction.py`, log containment only) -- including it does
not widen the envelope, it completes the class inside it. It is flagged in the return report so the
orchestrator can rule otherwise.

**SIX IS THE CLOSURE OF THE *CLEANUP* HANDLERS, NOT OF EVERY LOGGING CALL THAT CAN CHANGE
BEHAVIOUR -- and the difference is stated because the broader claim would be FALSE.** `entry.py`
carries four more logging calls at `:824`, `:892`, `:903` and `:918`, all inside
`_record_entry_inner`, i.e. **inside the transaction and BEFORE the commit**. A raising sink there
does propagate and does abort the operation -- but there is no durable row yet, the transaction
rolls back, and **reporting a failure is then the HONEST answer, not a wrong one.** They are a
different semantic class (an availability nuisance: a broken sink prevents entries) and they are
**declared at S7.11, not fixed** -- the brief scopes `entry.py` to the R11-03 cleanup-twin
containment, and widening to every logging call in the file would be a scope change this plan is not
authorised to make. Method: read every `log.` call in `entry.py` (seven: `:534`, `:744`, `:752`,
`:824`, `:892`, `:903`, `:918`) and classify each by whether a durable row can exist when it runs.

**THE MECHANISM, MEASURED BY EXECUTION** (not reasoned from the language reference) -- run at plan
time on this box's Python, with a `logging.Handler` whose `emit()` raises:

    PRE-FIX escapes:  RuntimeError  RuntimeError('sink is broken')      <- the LOG's exception
    POST-FIX escapes: KeyError      KeyError('cleanup_error')           <- the ORIGINAL
                      notes = ["log not emitted: RuntimeError('sink is broken')"]
                      cause = ValueError                               <- chaining preserved

**So the defect changes the IDENTITY of the escaping exception, and the `raise X from Y` chaining is
lost with it.** That is the property test (d) must assert. A test that asserts only "no crash"
passes an implementation that swallows everything, and the brief says so.

Third measured fact, which decides one design detail at S2.5:

    class NoNote(RuntimeError):
        def add_note(self, n): raise TypeError("refuses notes")
    -> add_note CAN raise: TypeError

`BaseException.add_note` is overridable, so the note-attach is itself a reachable failure and its
guard is NOT defensive dead code.

### S1.5 The belt -- **HOLDS, with the message narrower than the brief says**

`ux_trades_one_open_per_ticker` is currently defined in
`swing/data/migrations/0014_phase7_state_machine_and_fills.sql:230-231`:

    CREATE UNIQUE INDEX ux_trades_one_open_per_ticker
      ON trades(ticker) WHERE state IN ('entered','managing','partial_exited');

(migration `0004` created the original `WHERE status = 'open'` form and `0014:129` drops it -- cite
`0014`, not `0004`.) The service-level pre-check is `entry.py:345-348` and the race re-map is
`entry.py:1086-1091`.

**Correction:** the brief's test (e) asks for "a message naming the existing trade". The message is
`Already an open position in {req.ticker}` -- it names the **TICKER**, not a `trade_id`. Test (e)
asserts what the code does; **this plan does not change the message**, because widening the belt's
copy is 22-A4's neighbourhood and the brief locks `entry.py` to log containment.

### S1.6 Everything else this plan leans on

- **`Jinja2Templates` autoescape is forced ON for `.html.j2`** (`swing/web/app.py:123-146`,
  `autoescape=True` unconditional -- Starlette's default `select_autoescape()` would NOT cover the
  `.html.j2` suffix). Warning text contains `repr(<exception>)`; it is escaped by the template.
  **The one hand-built HTML string this plan adds (S2.2's last resort) interpolates nothing but an
  `int`.**
- **`/watchlist` carries none of the four OOB ids.** `watchlist.html.j2` is 21 lines: `extends
  base.html.j2`, an `<h1>`, and one `<table>` of `watchlist_row.html.j2` includes. The entry form IS
  reachable there (`watchlist_row.html.j2:51`). The other two entry affordances are
  `hypothesis_recommendations_row.html.j2:36` and `..._expanded.html.j2:77`, both dashboard-only.
- **The success response is pure-OOB with EMPTY primary content** (`:2048-2056`) and that is
  deliberate: Bug A (the new row landing in the source tbody) and Bug B (a leading `<tr>` making
  HTMX `makeFragment` synthesise a `<table>` wrap that DROPS `<table>`s inside OOB `<section>`
  chunks) are both documented at `:1961-1989` and in CLAUDE.md. **This plan puts no `<tr>` at
  fragment root on any path** (S2.1).
- **`hx-swap-oob` in this codebase is id-based only** -- every occurrence under `swing/web/` is
  `hx-swap-oob="true"`; the `<swapStyle>:<selector>` form appears nowhere. The plan stays on the
  established form.
- **`record_entry` has exactly two callers in `swing/`**: `swing/cli.py:790` and
  `swing/web/routes/trades.py:1490`.
- **`click` 8.3.1** -- `CliRunner().invoke(...)` gives `result.output` = stdout+stderr interleaved
  AND `result.stderr` = stderr only (measured at plan time; `mix_stderr` is gone in click 8.2+).
  Test (c) may assert against either.
- **No import cycle** is created by `cohort_provenance_correction.py` importing from `entry.py`:
  `entry.py`'s module-level imports are `swing.data.models`, `swing.data.repos.{fills,trades,
  watchlist}`, `swing.trades.origin`, `swing.trades.state`, none of which import the correction
  module (its only appearance in `entry.py` is a COMMENT at `:683`). A function-local precedent for
  this direction already exists at `cohort_provenance_correction.py:1444`.
- **`banner` and `banner-degraded` exist in `swing/web/static/app.css:256-258`.** The plan adds NO
  CSS, so the theme-token / no-raw-hex CSS contract tests cannot be perturbed. (`banner-info` is
  used by a template but is NOT defined in `app.css` -- pre-existing, out of scope, and a reason to
  reuse `banner-degraded` rather than reach for it.)

---


## S2. THE DESIGN DECISIONS, OWNED

### S2.0 THE SCOPE OF THE HEADLINE CLAIM -- narrowed twice, deliberately, before anything is designed

The arc's promise is *a durable entry is never reported as a failure.* **That absolute is FALSE at
THREE IDENTIFIED CODE-LOCAL BOUNDARIES this plan cannot move, and at a fourth that is not code-local
at all.** The qualifier is load-bearing and was earned: the count grew from two to three under
review (`A3-R3-03`), and then a fourth arrived that no code-reading enumeration would ever have
closed (`A3-R4-09`) -- **so the inventory is now written as "the ones we have identified", never as
"the ones that exist".** An exhaustive claim about failure boundaries is the same instrument as a
hand-enumerated roster, and it fails the same way.

**Boundary one -- OUTSIDE the callers.** `RequestIdMiddleware`
(`swing/web/middleware/request_id.py:22-34`) is registered LAST and is therefore OUTERMOST
(`swing/web/app.py:657-660`, and the comment there says so). Its `dispatch` receives the route's
finished response, stamps `X-Request-ID`, **calls `_access_log.info(...)`, and only then returns
it.** A raising access-log handler at that point destroys a correctly constructed degraded-success
200, and `ServerErrorMiddleware` hands it to the app-wide handler, which renders the refusal-shaped
500 of S0. **Route-local containment cannot reach it** -- the route has already returned.

**Boundary two -- BEFORE the caller can bind the result.** Python's CALL-to-STORE window is real:
`record_entry()` can return after committing and an asynchronous exception (a signal-derived
`KeyboardInterrupt`) can be delivered before the `STORE_FAST` that binds `result`. In that state the
ledger is durable, `result is None`, and this plan's own logic deliberately re-raises. **No
caller-only restructuring closes that window** -- it is one bytecode wide and it is on the far side
of the assignment every guard here keys on.

**Boundary three -- INSIDE `record_entry`, one line before the guard that protects it.**
`entry.py:516-519` builds its degraded warning with `f"...({post_commit_error!r})..."`. A legal
custom exception whose `__repr__` RAISES makes that formatting raise, over a committed row, before
any `EntryResult` exists to return -- so the caller never gets a result to bind and every guard in
this plan is downstream of the failure. **The one-token correction is
`{safe_text(post_commit_error)}`** and this plan does NOT make it: the envelope opens `entry.py` for
**log containment**, and that line is clause-1 WARNING-TEXT construction rather than a logging call.
Flagged at S8 item 7 with the exact diff, for the orchestrator to authorise or decline in one line.
*(Its sibling at `:545`, `{log_error!r}` INSIDE the log-failure handler, IS log containment and IS
fixed here -- Task 4. The line is drawn at "does a logging handler's failure reach it", and it is
drawn explicitly so a reviewer can move it rather than guess at it.)*

**So the claim this plan makes and tests is exactly:**

> **ONCE THE CALLER HAS BOUND THE RETURNED `EntryResult`, NEITHER THE ROUTE NOR THE CLI
> CONSTRUCTS A REPORTED FAILURE OVER A DURABLE ENTRY.**

*"Constructs", not "delivers"* -- boundary four is exactly the difference, and the word was chosen
after a reviewer showed that the stronger phrasing claimed something the route cannot know.

**Boundary four -- AFTER THE ROUTE RETURNS AT ALL: RESPONSE DELIVERY.** Returning an
`HTMLResponse` object is not delivery. ASGI send, middleware streaming, transport errors and client
disconnects all happen afterwards, and a failure there can leave the operator's browser with an
error -- or with nothing -- over a durable entry (`A3-R4-09`). **This is not code-local, it is not
fixable inside this envelope, and the plan does not attempt it.** It is why the guarantee below is
worded as a CONSTRUCTION guarantee: what the route BUILDS and RETURNS, not what the operator's
browser ends up rendering.

All four are declared (S7.3, S7.4, S7.13, S7.15); the two code-local ones outside the envelope are
flagged with their corrections (S8 items 6 and 7). The CALL-to-STORE residual's DIRECTION is the belt-covered one: the caller is told the
entry failed, retries, and `ux_trades_one_open_per_ticker` refuses -- a confusing error, not a
double position -- which is the same direction, and the same belt, as the declared clause-2 residual
this arc deliberately leaves to 22-A4.

### S2.1 HOW THE NOTICE REACHES THE OPERATOR -- decision: **one OOB swap into `#entry-notice`, identical on both paths, `<div>` at fragment root, never a `<tr>`**

The response must carry operator-facing text on two different occasions -- warnings after a
SUCCESSFUL refresh, and a degraded-success notice when the refresh FAILED -- and the two occasions
have opposite constraints. The success response already contains OOB chunks that contain `<table>`s;
the degraded response can contain nothing rendered from `dashboard_vm` at all.

**Decision: both paths deliver the notice as a single OOB chunk whose root element is
`<div id="entry-notice" hx-swap-oob="true">`, emitted by one partial, and neither path ever puts a
`<tr>` at fragment root.**

- **A `<div>` stays at fragment root on both paths,** so Bug B cannot fire. A `<tr>`-rooted notice
  would re-open it against the very OOB `<table>` chunks the pure-OOB architecture protects.
- **The degraded response needs nothing from `dashboard_vm`,** which is the thing that just failed.
- **One markup path, one browser behaviour to witness at S6.**

**Rejected alternatives, with the reason each was rejected:**

| alternative | rejected because |
|---|---|
| Prepend the notice INSIDE the existing `#status-strip` OOB chunk (no new container) | `/watchlist` has no `#status-strip`, so the warning is silently dropped on a surface the entry form is reachable from -- shipping this arc's own failure mode inside its fix. |
| `hx-swap-oob="afterbegin:body"` (no container at all) | The selector form of `hx-swap-oob` appears NOWHERE in this codebase; it is browser-only-verifiable and would make the one binding gate carry an unfamiliar mechanism as well as the change. |
| Primary content = a `<tr>` banner row replacing the form row | Correct-looking and the reason it is wrong is browser-only: on the success path it re-opens Bug B against the OOB `<table>` chunks. Splitting the shape by path doubles what the operator gate must witness. |
| `204` + `HX-Redirect: /` on the degraded path | The CLAUDE.md rule it invokes forbids `303` and prescribes `204`+`HX-Redirect` for form successes that NAVIGATE; this route's success is an in-place swap. Redirecting also DESTROYS the warning text unless it is carried in a query parameter, which would touch the dashboard route -- outside the envelope. |

**The container** is `<div id="entry-notice"></div>`, static and empty, in `base.html.j2` immediately
before `<main>` at `:137`. It carries **no VM field** -- the every-base-layout-VM gotcha needs a
`vm.` dereference to fire and there is none.

**The partial owns its own wrapper**, exactly as `partials/hypothesis_recommendations.html.j2:31`
does, so the route never hand-builds the OOB element and the "OOB partial drift" gotcha has no
surface. The swapped-in element carries the same `id`, so a second entry in the same page session
finds its target again.

### S2.2 THE DURABILITY BOUNDARY IS THE BINDING OF `result` -- **NOT the start of the render block**

**This is the correction Codex round 1 forced (`A3-R1`, CRITICAL), and it is the same defect
`22A-FIX-R10-01` fixed one layer in: a guard that opens one frame too late.** The route's
`finally: conn.close()` at `:1958-1959` runs AFTER `record_entry` has returned a durable result and
BEFORE any render guard could begin. `sqlite3.Connection.close()` can raise, and a
`KeyboardInterrupt` can land on it. On the web path that becomes the refusal-shaped 500 over a
durable row; on the CLI path -- where the interrupt IS deliverable, because the CLI runs on the main
thread and S2.5's threadpool argument does not apply -- it exits non-zero having printed nothing.

**Decision: EVERYTHING between the binding of `result` and the response/exit is inside a guard, and
that includes the connection close, the warning assembly, and (on the CLI) the OUTPUT ITSELF.**
Round 2 (`A3-R1`) showed the first version stopped short of the last of those: `click.echo` can raise
`BrokenPipeError`, which would leave a durable CLI entry exiting non-zero with no confirmation --
the arc's own failure mode at the last statement.

**AND THE GUARD IS ONE CONTINUOUS OUTER `try/except`, NOT TWO ADJACENT ONES** (`A3-R3-01`, then
`A3-R4-01` correcting the correction -- this is the third shape this paragraph has had, and each
revision moved the guard's START one frame earlier). Once `result` is bound, an asynchronous
exception can arrive at ANY point before the response is returned or the last line is printed. A
guard wrapping only `close()` misses the `finally`'s own tail. **And TWO ADJACENT guarded regions --
one for the connection, a second for the refresh/output -- leave an uncovered instruction boundary
BETWEEN their exception-table ranges**, which is precisely where a pending asynchronous exception
can land, and precisely on the CLI main thread where the plan says it matters most.

So the shape is **ONE outer `try:` opened before the connection is created and closed only after the
response is returned / the last line is printed**, with the connection's `try/finally` and the
refresh block NESTED INSIDE it. Mechanically, in BOTH callers:

- `result` and `close_error` are initialised to `None` before the outer `try`;
- the connection `finally` closes inside its own `try`, re-raising when `result is None` and
  recording `close_error` when it is bound;
- **the refresh/response construction (web) and the whole output block (CLI) live INSIDE THE SAME
  outer `try`** -- there is no second guard and therefore no gap between two;
- the single outer `except BaseException` re-raises when `result is None` and produces the
  degraded-success response / a silent exit 0 when it is bound;
- **if `result is None` the close failure RE-RAISES -- pre-durability semantics are BYTE-UNCHANGED**
  (every existing refusal path returns or raises out of the `try` with `result` still `None`);
- **if `result` is bound the close failure is CONTAINED** and recorded as one more post-commit
  warning;
- the warning assembly is a TOTAL function called from inside the guarded region on every branch --
  **in the CLI too**, where an earlier draft left it in front of the `try` and thereby contradicted
  this very paragraph (`A3-R3-01`);
- **on the CLI, the entire output block is inside a `try` that contains output failures and keeps
  exit status 0** (S7.9 declares what that costs).

The asymmetry is the whole point and it is the same asymmetry `record_entry` itself draws: before
the durable fact exists, an error is the honest answer; after it exists, an error is a wrong answer
in the expensive direction.

### S2.3 THE DEGRADED-SUCCESS RESPONSE -- decision: **200, notice-only, and a helper that CANNOT raise**

The invariant is *the route never reports a durable entry as a failure*. A guard that returns a
degraded response BY RENDERING A TEMPLATE has re-introduced the exposure one layer in: if the
template machinery is what broke, the guard raises and the app-wide 500 handler produces the
refusal-shaped fragment of S0.

**Decision: `_entry_notice_html(...)` is contractually TOTAL** -- it renders the partial, and on ANY
exception from that render it returns a hand-built HTML string. Four properties the review forced
onto it:

1. **It carries the warnings, HTML-escaped with `html.escape` from the stdlib** -- not Jinja, which
   is the machinery that just failed. A fallback that DROPS the warnings ships the arc's own failure
   mode (a warning with no reader) inside the fix for it. (`A3-R1-04`)
2. **It distinguishes "the refresh failed" from "only the notice render failed."** The reachable
   case is: the dashboard and all four partials render, `post_commit_warnings` is non-empty, and
   only `partials/entry_notice.html.j2` fails -- where a fixed "the page could not be refreshed"
   string is FALSE. (`A3-R1-04`)
3. **EVERY value it interpolates is ASCII by construction** (`ascii_safe` / `safe_text`, S2.6). A
   custom exception whose `__repr__` raises is constructible, and -- measured at plan time -- **a
   custom `__repr__` returning a string containing a LONE SURROGATE survives `html.escape` and then
   makes `HTMLResponse` raise `UnicodeEncodeError` while encoding the body as UTF-8**, one frame
   OUTSIDE every guard. (`A3-R2-03`, and it is the finding that disproved the first draft's reason
   for declining a second construction path.)
4. **The warnings are ASCII-coerced BEFORE they reach either renderer, not only in the fallback** --
   `record_entry` builds its warning strings with a raw `{exc!r}`, so a surrogate reaches the
   TEMPLATE path just as easily.

Status code: **200.** Not 204 (a 204 tells HTMX not to swap -- the notice would never land). Not
4xx/5xx (both read as refusals and both are what this arc exists to stop).

### S2.4 THE NOTICE CHUNK IS ALWAYS EMITTED, AND IT IS EMPTY ON AN ORDINARY ENTRY -- decision reversed by review

The first two drafts said the notice chunk is emitted ONLY when there is something to say, and
called the ordinary response "unchanged". **`A3-R3-04` showed that is a live operator-visible
defect, not a conservative choice: `#entry-notice` is STATEFUL.** A warning or degraded response
replaces the empty container with a visible banner and -- deliberately -- keeps the same `id` so the
next entry can find it. If the next ordinary entry then emits NO notice chunk, **the previous
trade's `Trade #N WAS RECORDED` banner stays on screen beside trade N+1's freshly rebuilt page.**
Stale, and specifically stale in the "a trade was recorded" direction.

**Decision: the `#entry-notice` OOB chunk is emitted on EVERY success response. On an ordinary entry
it renders EMPTY**, which clears any prior banner while preserving the target for the next one.

Consequences, stated because they change the arithmetic of a test:

- an ordinary entry's response now carries **five** OOB chunks, not four: the four refresh chunks
  plus an empty notice. **The notice is emitted FIRST in the body, so "the fifth chunk" means "the
  additional one", not "the last one"** (`A3-R5-10`); test (f) asserts the count and the four
  legacy chunks' RELATIVE order, and says nothing about the notice's position because nothing
  depends on it -- HTMX matches OOB chunks by id, not by position;
- the blast-radius commitment moves from "no fifth chunk" to **"the four refresh chunks are
  unchanged in identity, count and order, and the fifth carries NO banner content"** -- which is
  what test (f) now asserts, and which makes (f) a DISCRIMINATING test rather than an invariant
  (pre-fix there is no notice chunk at all);
- **a byte-golden is still not available** and the plan still does not claim one: the status-strip
  and open-positions partials embed live prices and timestamps (`A3-R1-06`).

### S2.5 THE GUARD CATCHES `BaseException`, NOT A ROSTER

The 22-A leg ruled this twice inside `entry.py` and once inside the correction module: *an exception
ROSTER standing in for the class* is how `KeyboardInterrupt` / `SystemExit` / `GeneratorExit` walk
past a cleanup. `record_entry`'s own post-commit guard is `except BaseException as
post_commit_error` (`entry.py:504`), and this route guard is that guard's continuation one frame out.

**Stated because it is the decision most likely to be challenged, and the challenge has a real
edge:** swallowing `SystemExit` in a request handler is normally wrong. Two reasons it is right
here. (a) `entry_post` is a SYNC `def` endpoint, so it runs in a threadpool worker where
signal-derived `KeyboardInterrupt` is not delivered and uvicorn's shutdown does not raise
`SystemExit` inside handlers -- the practically reachable set equals `Exception`'s. (b) Where they
ARE reachable, the contract's direction still governs: a durable money-bearing row reported as a
failed entry is the direction that causes a double entry. **The CLI is the case where (a) does NOT
hold** -- it is the main thread and `KeyboardInterrupt` is fully deliverable there -- which is
precisely why S2.2 contains the CLI's close AND its output, and why the CLI containment is not
merely symmetry.

### S2.6 THE CONTAINMENT IDIOM -- decision: **four small functions in `entry.py`, stated once**

The recipe's rule: state the class once, then re-grep the artifact for it. Six sites means the fix
is a shared idiom, not six local edits -- and a shared idiom makes "did site N get it" a mechanical
question. `ascii_safe` and `safe_text` are part of the idiom rather than adjacent to it: **a
containment guard that formats a value which can raise, or which produces a string that cannot be
encoded, is a containment guard that can raise.**

    # swing/trades/entry.py -- NEW, immediately after
    # `log = logging.getLogger(__name__)`.

    def ascii_safe(text: str) -> str:
        """ASCII-only, and NEVER an exception.

        Two independent reasons, both MEASURED at plan time rather than
        reasoned about:

        * Windows `cp1252` stdout raises on non-ASCII, and these strings reach
          `click.echo` (CLAUDE.md; `pytest`'s `capsys` hides it).
        * A custom `__repr__` may return a string containing a LONE SURROGATE.
          `html.escape` preserves it and `HTMLResponse` then raises
          `UnicodeEncodeError` encoding the body -- one frame OUTSIDE every
          guard in the degraded path, producing exactly the durable-row-plus-500
          outcome this arc exists to remove.

        `backslashreplace` is lossless-to-the-reader and cannot itself fail on
        a surrogate (measured: `'bad \\ud800 repr'` round-trips to the literal
        text `bad \\ud800 repr`).
        """
        try:
            return text.encode("ascii", "backslashreplace").decode("ascii")
        except BaseException:  # noqa: BLE001 -- the CLASS, not a roster
            return "<a value that could not be rendered as text>"


    def safe_text(value: object) -> str:
        """`repr(value)`, ASCII-coerced, and NEVER an exception.

        Measured: an exception class overriding `__repr__` (and `__str__`) to
        raise is constructible, and the values formatted by the containment
        idiom and by the web route's degraded notice are exceptions raised by
        arbitrary code.
        """
        try:
            return ascii_safe(repr(value))
        except BaseException:  # noqa: BLE001
            pass
        try:
            return ascii_safe(str(value))
        except BaseException:  # noqa: BLE001
            pass
        return "<an object whose repr() and str() both raised>"


    def log_contained(logger: logging.Logger, msg: str,
                      *args: object) -> BaseException | None:
        """Emit an ERROR record, containing a failure OF THE SINK.

        **A FAILING LOGGING HANDLER MUST NEVER CHANGE A FUNCTION'S RESULT OR
        WHICH EXCEPTION PROPAGATES** (Codex 22A-R11-03).  A logging sink is
        caller-installed infrastructure this package does not control, and
        every call site is a CLEANUP handler -- the place where an exception is
        already in flight and its identity is the caller's only evidence about
        what happened.  Measured pre-fix: a sink whose `emit()` raised replaced
        a `KeyError` cleanup error with its own `RuntimeError` and dropped the
        `raise ... from ...` chaining with it.

        Returns the sink's exception, or `None`.  It is RETURNED rather than
        swallowed because a silent `pass` trades one invisible failure for
        another (the R10-04 standard); each caller decides how to surface it.
        """
        try:
            logger.error(msg, *args)
        except BaseException as log_error:  # noqa: BLE001 -- the CLASS
            return log_error
        return None


    def log_contained_note(logger: logging.Logger, escaping: BaseException,
                           msg: str, *args: object) -> None:
        """`log_contained` for a site that is about to RAISE `escaping`.

        The sink's failure is attached as a NOTE, so it travels in the
        traceback while the exception's TYPE, its args, its `__cause__` and its
        `__context__` are untouched -- the property the six call sites are
        judged on.

        **The attach goes through `BaseException.add_note` EXPLICITLY, not
        through `escaping.add_note`.**  `add_note` is overridable, and an
        overriding subclass that raises would otherwise make this helper
        SWALLOW the sink failure entirely -- the invisible failure its own
        docstring forbids.  Measured: the base implementation lands the note on
        exactly such a subclass.

        **AND THE BASE IMPLEMENTATION ITSELF CAN RAISE** (measured: assigning a
        TUPLE to `__notes__` makes it raise `TypeError: Cannot add note:
        __notes__ is not a list`).  So a malformed `__notes__` is REPAIRED
        in place -- every existing note preserved -- and the attach retried
        once.  The residue after that is declared at S7.7.
        """
        log_error = log_contained(logger, msg, *args)
        if log_error is None:
            return
        note = (f"the ERROR log for this cleanup failure could not be emitted "
                f"({safe_text(log_error)}); the condition it described is "
                f"unchanged.")
        try:
            BaseException.add_note(escaping, note)
            return
        except BaseException:  # noqa: BLE001 -- the CLASS, not a roster
            pass
        try:
            existing = getattr(escaping, "__notes__", None)
            if isinstance(existing, list):
                repaired = list(existing)
            elif existing is None:
                repaired = []
            elif isinstance(existing, (tuple, set, frozenset)):
                repaired = list(existing)
            else:
                repaired = [safe_text(existing)]
            repaired.append(note)
            # **`BaseException.__setattr__`, NOT `escaping.__notes__ = ...`**
            # (Codex 22A3-R5-04).  A subclass overriding `__setattr__` to
            # raise would otherwise defeat the repair -- and the base slot
            # bypasses the override for exactly the reason
            # `BaseException.add_note` does one line up.  MEASURED on this
            # runtime: a class whose `__setattr__` always raises rejects
            # `add_note`, and the direct base `__setattr__` still installs the
            # repaired list.
            BaseException.__setattr__(escaping, "__notes__", repaired)
        except BaseException:  # noqa: BLE001
            return

**Where it lives:** `swing/trades/entry.py`, which the envelope opens for "log containment ONLY" --
all four functions ARE the containment (the two text helpers exist because the guards call them, and
for no other reason). They are NOT added to `__all__` (that list is the entry service's
caller-facing surface). `cohort_provenance_correction.py` imports **only** `log_contained_note` (all
six of its sites raise); `swing/web/routes/trades.py` imports `log_contained`, `safe_text` and
`ascii_safe`; `swing/cli.py` imports `ascii_safe` and `safe_text`. **Import exactly what each module
uses: `ruff`'s `F` rules make an unused import a hard failure.**

**Rejected alternative:** a new module `swing/trades/log_containment.py`. Tidier home, **outside the
declared envelope** (a new file in `swing/trades/`). The brief says a plan that wants something
outside the envelope stops and routes rather than widening; four small functions in `entry.py` need
no ruling, so none is asked for.

**Rejected alternative:** duplicate the guard inline at each of the six sites. The list-shaped fix
the recipe warns about -- the seventh site added later gets it or does not, and nothing notices.

### S2.7 THE CLI -- decision: **stderr, ASCII by construction, exit 0, output itself contained**

`post_commit_warnings` is a caveat ON a successful entry, so it goes to stderr with the existing
`WARN` prefix convention (`cli.py:836`), and the success line still prints to stdout. **The exit
code is not touched**: it is a statement about the ledger and the ledger has the row.

Two properties the review forced:

- **Every warning is passed through `ascii_safe` before `click.echo`** (`A3-R2-11`). The strings
  come from `record_entry`, which builds them with a raw `{exc!r}` -- so arbitrary Unicode from an
  arbitrary exception reaches the CLI, and Windows `cp1252` stdout raises on it. An ASCII SENTINEL
  in a test proves nothing about that; the coercion is in the production path and the test injects
  NON-ASCII.
- **The whole output block is inside a containment** (`A3-R2-01`). `click.echo` can raise
  `BrokenPipeError` (`swing trade entry | head`) or any other output error, and an uncontained
  failure there leaves a durable entry exiting non-zero with no confirmation -- the arc's own
  failure mode at the last statement. What that costs when the sink is genuinely gone is declared at
  S7.9.

### S2.8 WHAT THIS PLAN DELIBERATELY DOES NOT DO

- **It does not touch `record_entry`'s transaction semantics.** The commit-raises path keeps
  re-raising. That is 22-A4's, and the declared residual above `_entry_transaction`
  (`entry.py:578-637`) stays exactly as written.
- **It does not add an attempt identity, a schema column, or a migration.**
- **It does not widen the belt, its message, or its predicate.**
- **It does not change the four existing OOB chunks, the pure-OOB architecture, or any 4xx path.**
- **It does not touch `swing/web/middleware/request_id.py`** (S2.0, S8 item 6).
- **It does not contain the four PRE-COMMIT logging calls in `_record_entry_inner`** (S1.4's closing
  note, S7.11).

---

## S3. TEST DESIGN -- every assertion computed under BOTH paths

> **The rule this section exists to satisfy:** a test that passes under the pre-fix path AND the
> post-fix path is worse than no test, because it reads as coverage. Each entry states the value the
> assertion takes under BOTH, and the pre-fix value is the one that has to be wrong.
>
> **New files:** `tests/web/test_routes/test_22a3_entry_degraded_success.py`,
> `tests/cli/test_cli_trade_entry_post_commit_warnings.py`,
> `tests/trades/test_22a3_log_containment.py`.

### The full roster

| id | what it pins | PRE-fix value | POST-fix value |
|---|---|---|---|
| a | a post-commit warning reaches the web response | warning text **absent** from a 200 body | warning text **present**; 1 trade row |
| b | a `build_dashboard` failure is degraded success | **500** + refusal-shaped banner | **200** naming `Trade #<id>`; 1 trade row |
| b2 | a `conn.close()` failure AFTER a durable entry is degraded success (web) | **500** over 1 durable row | **200** naming the trade, warning names the close |
| l | a warning entry followed by an ORDINARY entry clears the banner | n/a (no notice exists) | the second response's notice chunk is present and EMPTY |
| c | the CLI prints the warnings, exit 0 | nothing printed, exit 0 | printed, exit **still** 0 |
| c2 | a `conn.close()` failure AFTER a durable entry (CLI) | **non-zero** exit, nothing printed, 1 durable row | **exit 0**, success line printed, warning names the close |
| c3 | a failing `click.echo` AFTER a durable entry | **non-zero** exit over 1 durable row | **exit 0** over 1 durable row |
| c4 | a NON-ASCII `--ticker` reaches the success line | stdout is **not** ASCII | stdout **is** ASCII; the ticker appears escaped |
| m | the ROUTE's own degraded-path `log_contained` is used | **500** | **200**, notice names the log that could not be emitted |
| d1..d6 | a raising log sink does not change the escaping exception | escapes `RuntimeError('sink')` | escapes the ORIGINAL object, chaining per the matrix |
| e | the belt still refuses a same-ticker retry | refuses | refuses -- a CONTROL, passes under both by design |
| f | an ordinary success carries an EMPTY notice chunk that clears prior state | **four** OOB chunks, no notice | **five** OOB chunks; notice present and EMPTY of banner content |
| g | the notice helper is total when ONLY the notice partial fails | **200 with FOUR chunks and NO sentinel** (pre-fix the route never asks for that template) | **200 with FIVE chunks**, warnings PRESENT, no false refresh claim |
| g2 | the notice helper is total when the whole template layer fails | **500** | **200** naming the trade, via the literal |
| g3 | ONLY the notice partial fails and there are NO warnings | **200**, ordinary body | **200** with a banner NAMING the trade and the notice failure, and an ERROR log |
| n | a lone surrogate IN A WARNING cannot break the SUCCESS response | **500** | **200**, the surrogate appears escaped |
| h | the notice container exists wherever the form is reachable | absent | present on `/` and `/watchlist`; static walk green |
| i | `ascii_safe` / `safe_text` / `log_contained` / `log_contained_note` unit properties | n/a | nine properties, below |
| k | a lone-surrogate `__repr__` cannot break the degraded response | **500** | **200**, a REAL `HTMLResponse` is constructed |
| j | the notice partial renders and escapes | n/a | renders, escapes metacharacters, right id + OOB attr |

### (a) A post-commit warning reaches the operator through the web response

**Injection:** monkeypatch `swing.web.routes.trades.record_entry` with a wrapper that calls the REAL
service and returns `dataclasses.replace(result, post_commit_warnings=(SENTINEL,))`. **This is the
load-bearing fixture choice** -- it produces a REAL durable row through the REAL production path and
adds only the field under test, so the test cannot pass because a stub fabricated a result.

    SENTINEL = "22-A3 PROBE: the entry is DURABLE -- do NOT retry."

- `resp.status_code == 200` -- true under BOTH; NOT the discriminator.
- `SENTINEL in resp.text` -- **PRE-fix FALSE** (the result is discarded at `:1490`); **POST TRUE**.
- `'id="entry-notice"' in resp.text` -- PRE FALSE, POST TRUE.
- **`resp.text.lstrip().startswith('<div id="entry-notice"')` -- POST TRUE.** This is the ONE path
  where the notice chunk travels beside OOB chunks containing `<table>`s, so it is the one path
  where a `<tr>` at fragment root would fire Bug B -- and test (b)'s `"<tr" not in resp.text` cannot
  be used here, because the OOB tables legitimately contain rows. Asserting the ROOT ELEMENT is the
  form of the check that works on this path (self-sweep SS-3: S2.1's decision was tested on the
  degraded path only).
- `SELECT COUNT(*) FROM trades` is `1` under both -- a CONTROL that the injection did not
  double-write.

### (b) A `build_dashboard` failure becomes a degraded success

**Injection:** `monkeypatch.setattr(swing.web.routes.trades, "build_dashboard", raiser)` where
`raiser` raises `RuntimeError("22-A3 PROBE: dashboard rebuild failed")`. The name is a module-level
import (`swing/web/routes/trades.py:41`), so this is the production symbol the route calls.

**Client:** `TestClient(app, raise_server_exceptions=False)` -- **required.** With the default
`True`, Starlette's `ServerErrorMiddleware` re-raises after the app's handler runs, so the PRE-fix
run would raise the probe out of `client.post(...)` and the test would assert on an exception rather
than a status. With `False` the same assertion is meaningful on both sides.

- `resp.status_code` -- **PRE `500`**; **POST `200`**.
- `f"Trade #{trade_id}" in resp.text` -- PRE FALSE; POST TRUE.
- `"do NOT" in resp.text` -- PRE FALSE; POST TRUE.
- `SELECT COUNT(*) FROM trades` is `1` **under both** -- the CONTROL that makes the test mean
  something: the row was durable in the pre-fix run too.
- `"<tr" not in resp.text` -- pins S2.1's no-`<tr>`-at-root decision on the degraded path.

### (b2) A connection-close failure after a durable entry -- the web half of `A3-R2`

**Injection:** patch `swing.web.routes.trades.connect` with a wrapper returning a forwarding proxy
over the REAL connection whose `close()` raises `sqlite3.OperationalError("22-A3 PROBE: close
failed")` (and which forwards `execute`, `commit`, `rollback`, `in_transaction`, `cursor`,
`__enter__`, `__exit__`). The real transaction still commits, so **the trade is genuinely durable**.

- `SELECT COUNT(*) FROM trades` is `1` **under both** -- the whole premise.
- `resp.status_code` -- **PRE `500`**; **POST `200`**.
- `f"Trade #{trade_id}" in resp.text` -- PRE FALSE; POST TRUE.
- `"close failed" in resp.text` -- POST TRUE (the contained close is reported, not swallowed).

**The refusal control that keeps S2.2's asymmetry honest:** a SECOND case in the same test file
submits a DUPLICATE ticker through the same close-raising proxy. `result` is `None` there, so the
close failure must still propagate: `resp.status_code == 500`, unchanged from today.

**On the WEB path that control genuinely DISCRIMINATES, and it is worth saying so because its CLI
twin does not** (see (c2)): the duplicate handler RETURNS a 400 from inside the `try`, so an
implementation containing the close UNCONDITIONALLY would swallow the close error and let that 400
stand. 400 versus 500 is the discriminator.

### (c) The CLI prints post-commit warnings and stays at exit 0

**Injection:** monkeypatch `swing.trades.entry.record_entry` (the CLI imports it function-locally at
`cli.py:657`, so the MODULE attribute is the binding one) with the same wrapper as (a).

- `result.exit_code == 0` -- true under BOTH; a CONTROL, and the point of the arc.
- **THE ASSERTION IS ON THE ESCAPED FORM, NOT THE RAW SENTINEL** (Codex 22A3-R5-05 -- an earlier
  draft asserted the raw non-ASCII sentinel AND `isascii()`, which cannot both hold):

      RAW      = "22-A3 PROBE: delta \u00e9 \u2014 \ud800"     # what is INJECTED
      EXPECTED = r"22-A3 PROBE: delta \xe9 \u2014 \ud800"      # what ascii_safe EMITS

  `EXPECTED in result.output` -- **PRE FALSE** (nothing is printed), POST TRUE.
  `EXPECTED in result.stderr` -- POST TRUE (pins the stream choice of S2.7).
  `RAW not in result.output` -- POST TRUE.
  *(The executor CONFIRMS `EXPECTED` by running `ascii_safe(RAW)` once and pasting its result rather
  than by predicting the escape forms -- `backslashreplace` renders a BMP char as `\xNN` or
  `\uNNNN` depending on width, and a hard-coded guess is exactly the kind of arithmetic this
  project requires to be computed rather than assumed.)*
- `f"Trade id {trade_id}" in result.output` -- true under both; the success line is not displaced.
- **ASCII gate, and THE INJECTED WARNING IS NON-ASCII** (`RAW`, above: an accented char, an
  em-dash, and a lone surrogate). Assert `result.output.isascii()` and `result.stderr.isascii()`. **`.encode("cp1252")`
  is NOT used** -- cp1252 accepts a large non-ASCII range and cannot establish the declared
  constraint (`A3-R1-11`). **And an ASCII sentinel could not establish it either** (`A3-R2-11`): the
  production strings come from `record_entry`'s raw `{exc!r}`, so the test must inject what
  production can actually receive. PRE-fix the assertion is unreachable (nothing is printed);
  POST-fix the output is ASCII because `ascii_safe` coerced it, and an implementation WITHOUT the
  coercion fails `isascii()`.

### (c4) A NON-ASCII TICKER reaches the success line

**Why it exists (`A3-R5-08`):** S2.7 says the whole line is coerced BECAUSE `--ticker` is
unrestricted text and `.upper()` does not make it ASCII -- and no test supplied one. **A half-fix
that coerces the warning lines and leaves the success and watchlist-archive lines raw passes (c),
(c2) and (c3).** A claim the plan makes must be a claim the plan tests.

Enter through the real CLI with `--ticker` set to a non-ASCII string (e.g. `"CAF\u00c9"`), no
injected warning, and a watchlist row seeded for that ticker so the archive line also fires.

- `result.exit_code == 0` -- true under both.
- `result.output.isascii()` -- **PRE FALSE** (the raw ticker reaches stdout); **POST TRUE**.
- the escaped ticker appears in the success line -- POST TRUE.
- the trade row exists -- under both.

### (c2) A connection-close failure after a durable entry -- the CLI half of `A3-R2`

Same forwarding close-raising proxy, patched over `swing.data.db.connect` as the CLI resolves it.

- the trade row exists -- **under both**.
- `result.exit_code` -- **PRE non-zero** (the `OperationalError` escapes `trade entry`);
  **POST `0`**.
- `f"Trade id {trade_id}" in result.output` -- PRE FALSE (it never printed); POST TRUE.
- `"close failed" in result.stderr` -- POST TRUE.
- **The refusal control, and it must assert the IDENTITY of what escapes -- "still fails" does NOT
  discriminate** (`A3-R2-09`). A duplicate-ticker CLI invocation through the same proxy exits
  non-zero under BOTH a correct conditional containment (the close error replaces the duplicate
  error) AND an incorrect unconditional one (the duplicate `ClickException` escapes instead). So the
  assertion is on the exception object: `type(result.exception) is sqlite3.OperationalError` **and**
  `"close failed" in str(result.exception)`. **Under unconditional containment the duplicate
  `ClickException` reaches Click's own top-level handling and `CliRunner` surfaces a
  `SystemExit(1)`, not the `ClickException` itself** (`A3-R3-08` -- an earlier draft said
  `ClickException` and that was inaccurate). Either way the assertion discriminates: `SystemExit`
  is not `sqlite3.OperationalError`. The exact-class assertion is what makes it work; "exits
  non-zero" would not.

### (c3) A failing `click.echo` after a durable entry -- the OUTPUT-containment discriminator

**Why it exists (`A3-R4-06`):** (c) and (c2) exercise warning printing and a close failure. **An
implementation that reads the warnings and contains the close but leaves the output block unguarded
passes both of them** -- and S2.2/S2.7 promise output containment explicitly, on a money-bearing
path.

**Injection:** monkeypatch `swing.cli.click.echo` (or `click.echo` as the CLI module resolves it)
with a wrapper that raises `BrokenPipeError("22-A3 PROBE: output failed")` on its FIRST post-commit
call and delegates afterwards. Seed no earlier echo in the fixture, so the first call is the one
under test.

- the trade row exists -- **under both**; the whole premise.
- `result.exit_code` -- **PRE non-zero** (the `BrokenPipeError` escapes); **POST `0`**.
- **The refusal control applies here too:** a duplicate-ticker invocation with the same echo probe
  must still exit non-zero, because `result is None` there.

### (m) The ROUTE's degraded path really uses `log_contained`

**Why it exists (`A3-R4-07`):** the degraded handler calls `log_contained(...)`, and the helper's
UNIT test says nothing about whether this CALL SITE uses it. **A half-fix that writes plain
`log.error(...)` there passes (a), (b), (b2), (f), (g), (g2) and (k)** -- and then a raising handler
converts the durable entry straight back into a 500, which is the arc's entire subject.

**Injection:** attach a raising `logging.Handler` specifically to the `swing.web.routes.trades`
logger, AND make `build_dashboard` raise.

- `resp.status_code` -- **PRE `500`**; **POST `200`**.
- `f"Trade #{trade_id}" in resp.text` -- PRE FALSE; POST TRUE.
- `"could not be emitted" in resp.text` -- **POST TRUE**: the log failure is surfaced as a second
  warning, not swallowed.
- `SELECT COUNT(*) FROM trades` is `1` under both.

### (d) R11-03 -- one test per site, asserting THE IDENTITY OF WHAT ESCAPES

**The shared fixture** (in `tests/trades/test_22a3_log_containment.py`):

    class _BrokenSink(logging.Handler):
        def emit(self, record):
            raise RuntimeError("22-A3 PROBE: logging sink failed")

    @pytest.fixture
    def broken_sink():
        sink = _BrokenSink(level=logging.ERROR)
        root = logging.getLogger()
        root.addHandler(sink)
        try:
            yield sink
        finally:
            root.removeHandler(sink)

**The shared assertion shape:**

    with pytest.raises(<ORIGINAL CLASS>) as excinfo:
        <call>
    assert excinfo.value is <the exact object the site raises>   # identity, not just class
    assert not isinstance(excinfo.value, RuntimeError)           # kills swallow-everything
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ()))  # noted, not swallowed
    <plus the CHAINING assertion from the matrix below -- it is NOT uniform>

**THE CHAINING MATRIX -- and it is NOT uniform, which round 1 caught (`A3-R7`).** The six sites use
three different chaining postures, and an executor copying one shape to all six writes a wrong test:

| test | site's raise statement | assert |
|---|---|---|
| d1 | `raise cleanup_error from write_error` (`entry.py:759`) | `__cause__ is` the body's error |
| d2 | `raise cleanup_error from savepoint_error` (`cohort:2291`) | `__cause__ is` the savepoint error |
| d3 | `raise anomaly from savepoint_error` (`cohort:2360`) | `__cause__ is` the savepoint error |
| d4 | `raise cleanup_error from write_error` (`cohort:2707`) | `__cause__ is` the inner error |
| d5 | bare `raise` (`cohort:3348`) re-raising `cleanup_error` | **`__cause__ is None`** -- there is no `from`, and on the SUCCESS posture no other exception is in flight |
| d6 | `raise cleanup_error` (`cohort:2450`) | **`__cause__ is None`**; on the failure posture **`__context__ is` the authorization error** (the declared R14-08 composition, which this arc must NOT change); on the success posture `__context__ is None` |

**PRE-fix, every one of the six:** `pytest.raises(<ORIGINAL>)` FAILS -- what escapes is
`RuntimeError("22-A3 PROBE: logging sink failed")` (measured at S1.4). **POST-fix:** the original
object escapes, its chaining is as the matrix says, and it carries the note.

**"No crash" is NOT asserted anywhere**, deliberately: an implementation wrapping the cleanup in
`try/except: pass` would satisfy a no-crash assertion and destroy the site.

**None of the six needs a seeded database world.** Each is driven through a narrow connection proxy
plus one targeted monkeypatch, in the `_CommitRaises` style already in
`tests/trades/test_22a_task9_entry_wiring.py:1327` (proxy ONLY the members the code under test
touches, so a stand-in cannot silently diverge from the real connection surface):

    class _Proxy:
        """execute() raises for SQL whose prefix matches `fail_on`, returns
        None otherwise; rollback() raises `rollback_error` when given;
        `in_transaction` is a SCRIPTED SEQUENCE consumed one value per read,
        with the last value repeating.

        The sequence is required by the sites that read `in_transaction` MORE
        THAN ONCE, where the reads mean DIFFERENT things (does this call own
        the transaction / did the failed cleanup leave it open); a single
        boolean cannot express those postures.  **d3 and d6 consume only the
        FIRST value** -- they enter caller-held, so `owns_read_tx` is False and
        the later ownership checks short-circuit (`A3-R5-12`).
        """
        def __init__(self, *, fail_on=(), rollback_error=None,
                     in_transaction=(False, True)):
            ...

| test | driven through | how the cleanup is made to fail |
|---|---|---|
| **d1** (`entry.py:744`/`:752`, both branches -- parametrized) | `_entry_transaction(proxy, immediate=True, outcome=_CommitOutcome())` with a body that raises | `rollback()` raises; `in_transaction` scripted True (`:744`) then False (`:752`) |
| **d2** (`cohort:2284`) | `preview_cohort_provenance_correction(proxy, ...)` | `in_transaction` False at entry (owns the tx), `SAVEPOINT` raises, `rollback()` raises |
| **d3** (`cohort:2353`) | same, `in_transaction` True at entry (caller-held) | `SAVEPOINT` raises; `ROLLBACK TO` raises something that is NOT "no such savepoint" |
| **d4** (`cohort:2693`/`:2700`, both branches -- parametrized) | `correct_cohort_provenance(proxy, ...)` with `_correct_cohort_provenance_inner` monkeypatched to raise | `rollback()` raises; `in_transaction` scripted per branch |
| **d5** (`cohort:3341`) | `read_provenance_corrections(proxy, ...)` with `_read_provenance_corrections_inner` monkeypatched to return `[]` | `rollback()` raises in the `finally`. **Runs on the function's SUCCESS path** |
| **d6** (`cohort:2445`, the site NOT in the brief's roster) -- **PARAMETRIZED OVER BOTH POSTURES** | `preview_cohort_provenance_correction(proxy, ...)`, entered CALLER-HELD | `SAVEPOINT` succeeds; `ROLLBACK TO` raises in the `finally`. **failure posture:** `_authorize` monkeypatched to raise `CohortProvenanceCorrectionError`. **success posture:** `_authorize` monkeypatched to RETURN `SimpleNamespace(already_applied=None, anchored=object(), derived=object(), latch=object(), admission_tier="probe")` -- the five attributes the `try` block reads |

**Why d6 is parametrized over both postures (round 1, `A3-R13`):** S1.4's argument for including the
sixth site is that its `finally` runs on the SUCCESS path too. A d6 that only ever drives the
failure posture reaches the same log call but leaves that specific claim untested -- the plan would
be asserting a property its test does not exercise. The success posture is cheap: the `finally` runs
before the `return CohortProvenanceCorrectionPreview(...)` statement, so `_authorize` only has to
return an object carrying five attributes; nothing downstream is constructed.

**The transaction postures each test must enter with:** d1 and d4 need `in_transaction` False at
entry (d4's `correct_cohort_provenance` REJECTS a caller-held transaction at `:2639-2644`) and True
inside the handler; d2 and d5 need False-then-True (the call owns the transaction); **d3 and d6 need
True at the first read** (caller-held), which routes d3 into the `else` branch at `:2312` and keeps
d6's `finally` off the outer `conn.rollback()`.

### (e) The belt is still the belt (a CONTROL, not a fix)

Enter `ZZZ` successfully, then POST the same form again. Under BOTH paths: `status_code == 400`,
`"Already an open position in ZZZ"` in the body, `SELECT COUNT(*) FROM trades` still `1`.

**This test passes under both paths on purpose** and is labelled a CONTROL in its own docstring. Its
job is to prove the arc did not perturb the one structural mitigation the declared residual leans
on. It is NOT counted as a discriminating test.

### (f) An ordinary success carries an EMPTY notice chunk -- and (l), the state it clears

Enter with no injected warning and no close failure. Assert:

- `resp.text.count('hx-swap-oob="true"')` -- **PRE `4`**; **POST `5`**. *(This flipped from an
  invariant into a discriminator when `A3-R3-04` showed the notice container is STATEFUL -- see
  S2.4.)*
- `'id="entry-notice"' in resp.text` -- **PRE FALSE**; **POST TRUE**.
- `"banner-degraded" not in <the entry-notice chunk>` and `"WAS RECORDED" not in resp.text` --
  **POST TRUE**: the chunk is present precisely so that it can be EMPTY.
- the four refresh ids appear exactly once each, in the order status-strip / open-positions /
  watchlist-top5 / hypothesis-recommendations -- **true under BOTH**, and this is the part that
  remains a pure blast-radius pin: the arc adds a chunk, it does not perturb the four.

**(l) THE TWO-REQUEST RESPONSE-CONTRACT TEST -- and what it CANNOT establish.** In one client: (1)
POST an entry with an injected `post_commit_warnings` sentinel; assert the banner text is present.
(2) POST a SECOND, ordinary entry for a different ticker; assert the second response's notice chunk
**is present and carries neither the sentinel nor `banner-degraded`**.

- **PRE-fix:** step 2's response contains no notice chunk at all -- `'id="entry-notice"' in
  resp.text` FAILS.
- **POST-fix:** present and empty.

**WHAT (l) DOES NOT PROVE, stated because an earlier draft claimed it did** (`A3-R4-04`): TestClient
does not apply HTMX swaps and holds no DOM, so (l) establishes only the SERVER-SIDE CONTRACT across
two requests -- that the second response carries a clearing chunk. **That the operator's browser
actually REPLACES the old banner is provable only by gate Step 5b**, and the plan says so at both
places rather than letting a response assertion stand in for a DOM one. (l) is still worth writing:
it is the only automated test that exercises the emit rule across a SEQUENCE, which is the shape the
defect lives in.

### (g) The notice helper is total when ONLY the notice partial fails -- the reachable case

**Injection:** wrap `app.state.templates.get_template` so it raises **only** for
`"partials/entry_notice.html.j2"` and delegates for everything else, and inject a
`post_commit_warnings` sentinel as in (a). This is the case the review named (`A3-R1-04`): the
refresh SUCCEEDED and only the notice render failed.

**THE PRE-FIX VALUE IS 200, NOT 500, AND AN EARLIER DRAFT HAD IT WRONG** (`A3-R2-08`). Pre-fix the
route never asks for `partials/entry_notice.html.j2` at all -- the result and its warning are
discarded at `:1490` -- so the raising wrapper NEVER FIRES and the response is an ordinary 200 with
four OOB chunks. Status code is therefore a CONTROL here, not a discriminator.

- `resp.status_code == 200` -- **CONTROL, true under both.**
- `resp.text.count('hx-swap-oob="true"')` -- **PRE `4`**; **POST `5`** (the four refresh chunks plus
  the literal notice). *Primary discriminator.*
- `SENTINEL in resp.text` -- **PRE FALSE**; **POST TRUE. The literal fallback must CARRY the
  warnings**, not drop them.
- `"could not be refreshed" not in resp.text` -- **POST TRUE.** The refresh did not fail, and a
  fallback that says it did is a false statement to the operator. *(Second discriminator: it fails
  against a fallback that emits a fixed refresh-failure string.)*
- `"&lt;" in resp.text` when the sentinel contains `<script>` -- the fallback escapes with
  `html.escape`, since Jinja is the machinery that just failed.
- **the INJECTED notice-render error's own text appears in the response** -- POST TRUE. The fallback
  NAMES what failed; an earlier draft printed only "This notice could not be rendered" and discarded
  the cause (`A3-R5-03`).

### (g3) ONLY the notice partial fails, and there is NOTHING ELSE TO SAY

The same injection as (g) but with **no** `post_commit_warnings` -- an ordinary entry whose only
problem is that the notice template broke.

**Why it exists (`A3-R5-03`):** an earlier draft returned an EMPTY wrapper in exactly this posture,
so a degraded event rendered as an ordinary success with no banner and no log -- the arc's own
failure mode, reached through its own fallback.

- `resp.status_code == 200` -- CONTROL.
- `f"Trade #{trade_id}" in resp.text` -- **POST TRUE**; the banner appears even with no warnings.
- the injected notice error's text appears -- POST TRUE.
- `"could not be refreshed" not in resp.text` -- POST TRUE; the refresh succeeded.
- **`caplog` carries the ERROR the helper emits** -- POST TRUE. The event is durable in the log as
  well as visible on screen (which is what keeps S7.8's "the ERROR log is the only durable trace"
  true rather than aspirational).

### (g2) The notice helper is total when the WHOLE template layer fails

**Injection:** `monkeypatch.setattr(app.state.templates, "get_template", raiser)` unconditionally.
The first refresh render fails, the guard runs, and `_entry_notice_html` hits the same broken
`get_template` and must fall through to the literal.

- `resp.status_code` -- **PRE `500`**; **POST `200`**.
- `f"Trade #{trade_id}" in resp.text` -- PRE FALSE; POST TRUE.
- `"this notice could not be rendered" in resp.text` -- **POST TRUE.** This phrase exists ONLY in
  the literal, so the assertion discriminates against a half-fix in which the guard exists but the
  helper is not total.

### (h) The container exists wherever the entry form is reachable -- a STATIC closure check

1. **Live:** `GET /` and `GET /watchlist` both contain `id="entry-notice"`.
2. **Static walk** over `swing/web/templates/`: build the set of partials whose source contains
   `"/trades/entry/form"`; walk `{% include %}` edges backwards to every PAGE template that reaches
   one; assert every such page `extends "base.html.j2"`. Today that set is
   `{dashboard.html.j2, watchlist.html.j2}` -- **and the assertion is the `extends` property, not
   the membership**, so a third entry surface added later is covered rather than merely counted.

A static walk is preferred to a runtime trace: a trace only sees the branches a fixture happened to
take, which is how a roster hole survives.

### (i) `ascii_safe` / `safe_text` / `log_contained` / `log_contained_note` unit properties

1. `log_contained` happy path: returns `None`, record emitted (assert via `caplog`).
2. `log_contained` broken sink: returns the sink's `RuntimeError`, raises nothing.
3. `log_contained_note` with a broken sink: `escaping.__notes__` gains one entry naming the sink
   error; `type(escaping)`, `escaping.args`, `__cause__` and `__context__` all unchanged.
4. **`add_note` overridden to raise: the note STILL LANDS** (`A3-R1-09`). With
   `class _RefusesNotes(RuntimeError): def add_note(self, n): raise TypeError(...)`, assert
   `log_contained_note` returns normally AND `"could not be emitted"` appears in that instance's
   `__notes__`. **Measured: `BaseException.add_note(e, note)` succeeds on such a subclass.** An
   earlier draft asserted only "returns normally", blessing the information loss it existed to
   detect.
5. **A malformed pre-existing `__notes__` is REPAIRED, not silently dropped** (`A3-R2-10`). Set
   `escaping.__notes__ = ("already", "a", "tuple")`; **measured: `BaseException.add_note` then
   raises `TypeError: Cannot add note: __notes__ is not a list`.** Assert `log_contained_note`
   returns normally and that `__notes__` is now a `list` carrying all three original entries PLUS
   the sink note. **Discriminating partner:** without the repair branch the sink note is absent.
6. `safe_text` on a normal object returns its ASCII-coerced `repr`; on an object whose `__repr__`
   raises returns its `str`; on an object whose `__repr__` AND `__str__` both raise returns the
   fixed literal and does not raise. (All three constructible; measured.)
7. **`ascii_safe` on a lone surrogate does not raise and returns ASCII** -- for the input
   `"bad \ud800 repr"` the result `.isascii()` is True and the surrogate appears as the literal
   text `\ud800`. Measured at plan time.
8. **`safe_text` of an exception whose `__repr__` RETURNS a lone surrogate is ASCII** -- the
   property that keeps `HTMLResponse` from raising (`A3-R2-03`). **Discriminating partner:** with
   `ascii_safe` removed from `safe_text`, `.isascii()` is False.
9. `log_contained_note` formats the sink error through `safe_text`, so a sink exception with a
   raising `__repr__` still produces a note. **Discriminating partner:** with `safe_text` replaced
   by `repr`, this test raises.

### (n) A lone surrogate IN A WARNING cannot break the SUCCESS response

**Why it exists, and why (k) does not cover it (`A3-R5-06`):** (k) drives a surrogate through the
`build_dashboard` exception, which exercises `safe_text(post_bind_error)` -- **not**
`_post_commit_warnings`. **A half-fix that drops `ascii_safe` from `_post_commit_warnings` passes
every other specified web test**, and then a warning carrying a lone surrogate makes the first
`HTMLResponse` raise, the outer handler rebuilds the SAME uncoerced warning, its `HTMLResponse`
raises again, and the durable-row-plus-500 outcome is back.

**Injection:** the (a)-style `record_entry` wrapper, with a warning containing `\ud800`. The refresh
SUCCEEDS -- this is the ordinary warning path, not the degraded one.

- `resp.status_code` -- **PRE `500`** (the response cannot be encoded); **POST `200`**.
- `"ud800" in resp.text` -- POST TRUE (the escape text `ascii_safe` produces).
- `SELECT COUNT(*) FROM trades` is `1` under both.
- **Its own mutation, recorded separately from (k)'s:** remove `ascii_safe` from
  `_post_commit_warnings` -- (n) goes red, (k) stays green. That separation is the point: two
  different call sites, two different mutations, neither one standing in for the other.

### (k) A lone-surrogate `__repr__` cannot break the degraded response -- the end-to-end proof

**Injection:** `monkeypatch.setattr(swing.web.routes.trades, "build_dashboard", raiser)` where the
raised exception's `__repr__` RETURNS `"bad \ud800 repr"` -- a legal custom `__repr__` returning a
string that contains a lone surrogate.

**Why this is end-to-end and not a unit test:** the failure it pins happens when Starlette ENCODES
the response body, inside `HTMLResponse`, which is OUTSIDE every guard in the route. Measured at
plan time: `html.escape` PRESERVES a lone surrogate, and encoding the result as UTF-8 raises
`UnicodeEncodeError`.

- `resp.status_code` -- **PRE `500`**; **POST `200`**.
- `f"Trade #{trade_id}" in resp.text` -- PRE FALSE; POST TRUE.
- `"ud800" in resp.text` -- POST TRUE (the surrogate arrives as the literal escape text, which is
  what `backslashreplace` produces).
- **Discriminating partner, and the executor RUNS it and records the red:** with `ascii_safe`
  removed from `safe_text`, this test returns 500. That mutation is what proves the coercion is
  load-bearing rather than decorative.

### (j) The notice partial renders, escapes, and carries its OOB contract

Render `partials/entry_notice.html.j2` directly through the app's `Jinja2Templates` environment with
`trade_id=7`, `warnings=["<script>alert(1)</script> & co"]`, `render_failure=None`. Assert: it
parses; the root element is a `<div>` with `id="entry-notice"` and `hx-swap-oob="true"`;
`"Trade #7"` is present; `"<script>"` is NOT present and `"&lt;script&gt;"` IS.

**Why this exists (round 1, `A3-R12`):** without it, Task 5's only test checks container presence
and would stay green over a partial with a Jinja syntax error, a wrong id, or a missing OOB
attribute -- defeating the "each task ends with an independently testable deliverable" rule.

---

## S4. FILE STRUCTURE

| file | create/modify | responsibility after this arc |
|---|---|---|
| `swing/trades/entry.py` | modify (`+~115` lines) | **containment ONLY**: `ascii_safe`, `safe_text`, `log_contained`, `log_contained_note` (the idiom, stated once), applied at the two branches of its own cleanup handler (`:744`, `:752`). Nothing else changes -- not the transaction semantics, not the declared residual, not `EntryResult`, and **not the four PRE-COMMIT logging calls at `:824`/`:892`/`:903`/`:918`** (S1.4, S7.11). |
| `swing/trades/cohort_provenance_correction.py` | modify (`+~12` lines) | **log containment ONLY**: import `log_contained_note`; apply it at all SIX cleanup-log sites. |
| `swing/web/routes/trades.py` | modify (`+~90` lines) | assign the `EntryResult`; CONTAIN the post-durability `conn.close()`; `_post_commit_warnings` (total warning assembly); `_entry_notice_html` (total, never raises, carries the warnings ASCII-coerced, distinguishes notice-failure from refresh-failure); the best-effort guard around the post-entry refresh; the degraded-success response. |
| `swing/web/templates/partials/entry_notice.html.j2` | **create** | the sole source of the notice markup, OOB wrapper included. |
| `swing/web/templates/base.html.j2` | modify (`+1` line + comment) | the static, empty `<div id="entry-notice"></div>` container. |
| `swing/cli.py` | modify (`+~30` lines) | CONTAIN the post-durability `conn.close()`; ASCII-coerce and print `post_commit_warnings` to stderr; CONTAIN the output block itself; exit status untouched. |
| `tests/trades/test_22a3_log_containment.py` | **create** | (i) the idiom's nine properties; (d1)-(d6) the identity-of-escape tests. |
| `tests/web/test_routes/test_22a3_entry_degraded_success.py` | **create** | (a), (b), (b2), (e), (f), (g), (g2), (g3), (h), (j), (k), (l), (m), (n). |
| `tests/cli/test_cli_trade_entry_post_commit_warnings.py` | **create** | (c), (c2), (c3), (c4). |

**No file outside the declared envelope is created or modified.**

---

## S5. TASK LADDER (TDD; one red -> green -> commit per task)

> Every task: write the failing test -> **run it and SEE it fail, for the stated reason** -> minimal
> implementation -> run it and see it pass -> `ruff check swing/` -> commit. The full fast suite runs
> at Task 10 (before the Codex loop) AND at Task 11 (on the final reviewed head); the binding browser
> gate is Task 9, ahead of both.
>
> Use `-n 0` on per-task runs (the `addopts` default is `-n auto`, whose output makes a single
> failure's text hard to read). **Reading the failure is a step, not a formality.**

### Task 1: the log-containment idiom

**Files:** Modify `swing/trades/entry.py` (after `log = logging.getLogger(__name__)` at `:25`, before
`__all__`). Test: create `tests/trades/test_22a3_log_containment.py`.

**Interfaces produced (later tasks rely on these exact names and types):**
- `ascii_safe(text: str) -> str`
- `safe_text(value: object) -> str`
- `log_contained(logger: logging.Logger, msg: str, *args) -> BaseException | None`
- `log_contained_note(logger: logging.Logger, escaping: BaseException, msg: str, *args) -> None`

- [ ] **Step 1: Write the failing test** -- the NINE properties of S3(i). The four below are the
ones whose exact shape matters; write properties 1-3, 6 and 9 from S3(i) in the same file.

```python
import logging
import pytest


class _BrokenSink(logging.Handler):
    def emit(self, record):
        raise RuntimeError("22-A3 PROBE: logging sink failed")


@pytest.fixture
def broken_sink():
    sink = _BrokenSink(level=logging.ERROR)
    root = logging.getLogger()
    root.addHandler(sink)
    try:
        yield sink
    finally:
        root.removeHandler(sink)


def test_log_contained_returns_None_when_the_sink_works(caplog):
    from swing.trades.entry import log_contained
    log = logging.getLogger("t22a3.ok")
    with caplog.at_level(logging.ERROR):
        assert log_contained(log, "hello %s", "world") is None
    assert "hello world" in caplog.text


def test_log_contained_RETURNS_the_sink_failure_instead_of_raising(broken_sink):
    from swing.trades.entry import log_contained
    out = log_contained(logging.getLogger("t22a3.broken"), "boom")
    assert isinstance(out, RuntimeError)
    assert "logging sink failed" in str(out)


def test_log_contained_note_leaves_the_escaping_exception_UNCHANGED(broken_sink):
    from swing.trades.entry import log_contained_note
    cause = ValueError("the original cause")
    escaping = KeyError("the cleanup failure")
    escaping.__cause__ = cause

    log_contained_note(logging.getLogger("t22a3.note"), escaping, "boom")

    assert type(escaping) is KeyError
    assert escaping.args == ("the cleanup failure",)
    assert escaping.__cause__ is cause
    assert escaping.__context__ is None
    notes = getattr(escaping, "__notes__", ())
    assert any("could not be emitted" in n for n in notes), notes
    assert any("logging sink failed" in n for n in notes), notes


def test_an_OVERRIDDEN_add_note_cannot_swallow_the_sink_failure(broken_sink):
    """`add_note` is overridable and CAN raise; going through
    `escaping.add_note` would then lose the logging failure entirely -- the
    invisible failure this helper exists to prevent. The base implementation
    cannot be overridden away."""
    from swing.trades.entry import log_contained_note

    class _RefusesNotes(RuntimeError):
        def add_note(self, note):
            raise TypeError("refuses notes")

    escaping = _RefusesNotes("x")
    log_contained_note(logging.getLogger("t22a3.nonote"), escaping, "boom")

    notes = getattr(escaping, "__notes__", ())
    assert any("could not be emitted" in n for n in notes), (
        "the sink failure was swallowed because add_note was overridden")


def test_a_MALFORMED_existing_notes_attribute_is_repaired(broken_sink):
    """MEASURED: assigning a TUPLE to `__notes__` makes even
    `BaseException.add_note` raise `TypeError: Cannot add note: __notes__ is
    not a list`. Without the repair branch the sink failure is lost, which is
    the same information loss the override case exists to prevent."""
    from swing.trades.entry import log_contained_note

    escaping = RuntimeError("cleanup")
    escaping.__notes__ = ("already", "a", "tuple")
    log_contained_note(logging.getLogger("t22a3.badnotes"), escaping, "boom")

    assert isinstance(escaping.__notes__, list)
    assert escaping.__notes__[:3] == ["already", "a", "tuple"]
    assert any("could not be emitted" in n for n in escaping.__notes__)


def test_ascii_safe_survives_a_lone_surrogate():
    from swing.trades.entry import ascii_safe
    out = ascii_safe("bad \ud800 repr")
    assert out.isascii()
    assert "ud800" in out


def test_safe_text_of_a_surrogate_repr_is_ascii():
    """The property that keeps `HTMLResponse` from raising: `html.escape`
    PRESERVES a lone surrogate and UTF-8 encoding of the body then fails, one
    frame outside every guard in the degraded path."""
    from swing.trades.entry import safe_text

    class _Surrogate(RuntimeError):
        def __repr__(self): return "bad \ud800 repr"

    assert safe_text(_Surrogate()).isascii()


def test_safe_text_never_raises():
    from swing.trades.entry import safe_text

    class _NoRepr(RuntimeError):
        def __repr__(self): raise ValueError("repr boom")

    class _NoReprNoStr(RuntimeError):
        def __repr__(self): raise ValueError("repr boom")
        def __str__(self): raise ValueError("str boom")

    assert safe_text(ValueError("plain")) == repr(ValueError("plain"))
    assert safe_text(ValueError("plain")).isascii()
    assert "repr boom" not in safe_text(_NoRepr("y"))       # fell through to str
    out = safe_text(_NoReprNoStr("z"))
    assert "raised" in out


def test_a_sink_error_with_a_RAISING_repr_still_produces_a_note():
    from swing.trades.entry import log_contained_note

    class _NoRepr(RuntimeError):
        def __repr__(self): raise ValueError("repr boom")

    class _WeirdSink(logging.Handler):
        def emit(self, record):
            raise _NoRepr("sink")

    sink = _WeirdSink(level=logging.ERROR)
    logging.getLogger().addHandler(sink)
    escaping = KeyError("cleanup")
    try:
        log_contained_note(logging.getLogger("t22a3.weird"), escaping, "boom")
    finally:
        logging.getLogger().removeHandler(sink)
    assert any("could not be emitted" in n
               for n in getattr(escaping, "__notes__", ()))
```

- [ ] **Step 2: Run it and see it fail**

Run: `python -m pytest tests/trades/test_22a3_log_containment.py -q -n 0`
Expected: `ImportError: cannot import name 'log_contained' ...` (and `ascii_safe`, `safe_text`) on
all nine.

- [ ] **Step 3: Minimal implementation** -- add the FOUR functions to `swing/trades/entry.py`
immediately after `log = logging.getLogger(__name__)`, EXACTLY as written at S2.6, docstrings
included: they carry the measured pre/post values and the reason each guard exists.

- [ ] **Step 4: Run it and see all nine pass.** Then `ruff check swing/`.

- [ ] **Step 5: Commit**

```
git add swing/trades/entry.py tests/trades/test_22a3_log_containment.py
git commit -m "feat(trades): 22-A3 Task 1 -- the log-containment idiom, stated once

A failing logging handler must never change a function's result or which
exception propagates (Codex 22A-R11-03). Measured pre-fix: a sink whose
emit() raised replaced a KeyError cleanup error with its own RuntimeError
and dropped the raise-from chaining with it.

log_contained RETURNS the sink's failure rather than swallowing it, per the
R10-04 standard. log_contained_note attaches it through BaseException.add_note
explicitly, because an overriding subclass that raises would otherwise make
the containment swallow the very failure it exists to surface. safe_text
formats through repr, then str, then a fixed literal, because an exception
whose repr raises is constructible and a formatter that can raise inside a
containment guard is a containment guard that can raise."
```

### Task 2: apply the idiom at `entry.py`'s own cleanup handler (BOTH branches)

**Files:** Modify `swing/trades/entry.py:735-760`. Test: append d1 to
`tests/trades/test_22a3_log_containment.py`.

**Interfaces consumed:** `log_contained_note` from Task 1.

- [ ] **Step 1: Write the failing test** -- parametrized over BOTH branches, because fixing one
branch and leaving the other is this arc's named repeat failure.

```python
import sqlite3


class _RollbackRaises:
    """Proxies ONLY the four members `_entry_transaction` touches, so a
    stand-in cannot silently diverge from the real connection surface
    (the `_CommitRaises` pattern, tests/trades/test_22a_task9_entry_wiring.py).

    `in_transaction` is SCRIPTED: the first read is the handler's entry gate
    (always True here); the second selects the message branch -- True is the
    "STILL OPEN" branch (entry.py:744), False the "rollback took effect then
    raised" branch (:752).
    """

    def __init__(self, *, in_transaction_after_rollback):
        self._reads = 0
        self._after = in_transaction_after_rollback
        self.rolled_back = False
        self.rollback_error = sqlite3.OperationalError(
            "22-A3 PROBE: rollback failed")

    def execute(self, sql, *a, **k):
        return None

    def commit(self):
        raise AssertionError("the body raises before any commit")

    def rollback(self):
        self.rolled_back = True
        raise self.rollback_error

    @property
    def in_transaction(self):
        self._reads += 1
        return True if self._reads == 1 else self._after


@pytest.mark.parametrize("still_open", [True, False],
                         ids=["still-open-branch", "took-effect-branch"])
def test_d1_a_broken_sink_cannot_change_what_escapes_the_entry_cleanup(
        broken_sink, still_open):
    from swing.trades.entry import _CommitOutcome, _entry_transaction

    proxy = _RollbackRaises(in_transaction_after_rollback=still_open)
    body_error = ValueError("22-A3 PROBE: the write failed")

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        with _entry_transaction(proxy, immediate=True,
                                outcome=_CommitOutcome()):
            raise body_error

    assert excinfo.value is proxy.rollback_error, (
        "the LOG SINK's exception escaped instead of the cleanup error -- "
        "the identity of what propagates was changed by a logging handler")
    assert not isinstance(excinfo.value, RuntimeError)
    assert excinfo.value.__cause__ is body_error
    assert any("could not be emitted" in n
               for n in getattr(excinfo.value, "__notes__", ())), (
        "the log failure was swallowed silently")
    assert proxy.rolled_back
```

- [ ] **Step 2: Run it and see it fail.** Expected on BOTH ids: the raised exception is
`RuntimeError: 22-A3 PROBE: logging sink failed`, so `pytest.raises(sqlite3.OperationalError)`
reports the `RuntimeError`. **Read the failure text and confirm it names the SINK's RuntimeError** --
that is the pre-fix value S1.4 measured; a different failure means the proxy is wrong, not the code.

- [ ] **Step 3: Minimal implementation.** In the `except BaseException as cleanup_error:` handler at
`entry.py:737-759`, replace each of the two `log.error(...)` calls with
`log_contained_note(log, cleanup_error, ...)` -- same message, same args, one added argument.
`raise cleanup_error from write_error` at `:759` is UNCHANGED. Add a one-line site comment naming
R11-03 and pointing at the idiom.

- [ ] **Step 4: Run and see both ids pass.** `ruff check swing/`.

- [ ] **Step 5: Commit** -- `fix(trades): 22-A3 Task 2 -- R11-03 containment at the entry cleanup log, both branches`.

### Task 3: cohort sites 2 and 3 (the preview savepoint handler)

**Files:** Modify `swing/trades/cohort_provenance_correction.py` -- the module-level import, plus
`:2284` and `:2353`. Test: append d2, d3.

- [ ] **Step 1: Write the failing tests d2 and d3** per the S3 tables, using the chaining matrix
(both are `__cause__ is` the savepoint error) and the postures named there.

- [ ] **Step 2: Run and see both fail** with the sink's `RuntimeError` escaping.

- [ ] **Step 3: Minimal implementation.** Add at module level, with the other `swing.trades` import:

```python
from swing.trades.entry import log_contained_note
```

**Only `log_contained_note`** -- all six cohort sites RAISE, so none of them wants the bare form, and
`ruff`'s `F` rules make an unused import a hard failure. Replace `:2284`'s `log.error(` with
`log_contained_note(log, cleanup_error,` and `:2353`'s with `log_contained_note(log, anomaly,` --
site 3's escaping object is `anomaly`, NOT `savepoint_error`; **the escaping exception is the one the
`raise` statement names.**

- [ ] **Step 4: Run and see both pass.** `ruff check swing/`.

- [ ] **Step 5: Commit** -- `fix(trades): 22-A3 Task 3 -- R11-03 containment at the preview savepoint handler (sites 2 + 3)`.

### Task 4: cohort sites 4, 5 and **6 -- the site the brief's roster does not name**

**Files:** Modify `swing/trades/cohort_provenance_correction.py` at `:2445`, `:2693`, `:2700`,
`:3341`. Test: append d4, d5, d6 (d6 parametrized over both postures).

- [ ] **Step 1: Write the failing tests d4, d5, d6** per the S3 tables and the chaining matrix --
note d5 and d6 assert `__cause__ is None`, and d6's failure posture additionally asserts
`__context__ is` the authorization error.

- [ ] **Step 2: Run and see all fail** with the sink's `RuntimeError` escaping. **d5's failure is
the one to read carefully: it fails on the function's SUCCESS path**, which is the clearest
statement of what the class costs.

- [ ] **Step 3: Minimal implementation.**

```python
# :2693 / :2700  -- both branches
                    log_contained_note(log, cleanup_error, "...", write_error, cleanup_error)
# :2445
            log_contained_note(log, cleanup_error, "...", cleanup_error)
# :3341
                log_contained_note(log, cleanup_error, "...", cleanup_error)
```

At `:2445` add the site comment recording WHY this site is here and the brief's roster did not name
it:

```python
            # R11-03 CONTAINMENT. **THIS SITE WAS NOT IN THE 22-A3 BRIEF'S
            # ROSTER OF FIVE.** It is the same class by construction -- an
            # ERROR log immediately followed by `raise <a specific object>` --
            # and it is reachable on this function's SUCCESS path as well as
            # its failure path, because this is a `finally`. Found by reading
            # every logging call in the module rather than by matching the
            # brief's line anchors; a hand-enumerated roster is the same
            # instrument as the count it replaced.
```

- [ ] **Step 4: Run and see all pass.** Then RE-READ all six sites and run the closure check:
`grep -n "log\.error(" swing/trades/cohort_provenance_correction.py` must return **zero hits**, and
the same grep on `entry.py` must return **exactly one** -- `:534`.

**`entry.py:534` is DELIBERATELY NOT converted to the idiom, and the reason belongs in the commit
message so a later reader does not "finish the job":** it is the post-commit guard's own ERROR log,
it is ALREADY contained by its own `try/except` at `:533-546`, and its containment is RICHER than
the idiom's -- on failure it appends a second entry to `post_commit_warnings`, i.e. it surfaces the
log failure to the CALLER, which is possible there because a result object exists. The six cleanup
sites have no result to attach to, which is why they get the note-on-the-exception form. Converting
`:534` would be a downgrade wearing a consistency costume.

**BUT ITS CONTAINMENT IS NOT TOTAL, AND THAT IS A ONE-TOKEN FIX THIS TASK ALSO MAKES**
(`A3-R3-02`, verified at source). `:545` builds the second warning with
`f"...could not be emitted ({log_error!r})..."` -- and if the logging handler's own exception has a
hostile `__repr__`, **that formatting raises INSIDE the `except` clause, over a durable row.** A
raising logging handler therefore still changes the function's result at the one site the plan had
declared safe. Replace `{log_error!r}` with `{safe_text(log_error)}`. **This IS log containment**
(the value being formatted is the logging handler's own failure, inside the log-failure handler), so
it is inside the envelope. Its sibling one line earlier -- `{post_commit_error!r}` at `:517` -- is
NOT, and is flagged rather than fixed (S8 item 7).

**Add the discriminating test alongside d1-d6** (same file). **It needs TWO injections, and an
earlier draft specified only one** (`A3-R4-10`): `entry.py:534` runs ONLY after a post-commit error
has already entered the degraded handler, so a broken sink alone never reaches it on an ordinary
successful entry and neither stated value could be produced.

1. **The primary post-commit failure** -- use the existing transaction-return injection helper
   (`_inject_after_the_commit(monkeypatch, KeyboardInterrupt("on the transaction's own return"))`,
   `tests/trades/test_22a_task9_entry_wiring.py:3342`), whose exception has an ORDINARY `repr`; this
   is what puts control inside the degraded handler at all.
2. **The hostile sink** -- a `logging.Handler` whose `emit()` raises an exception with BOTH a raising
   `__repr__` AND a raising `__str__`.

Assert: the injection FIRED; `record_entry` RETURNS its degraded `EntryResult`; it carries exactly
TWO warnings (the durable one and the log-failure one); exactly one durable row exists.
**PRE-fix the `{log_error!r}` formatting raises and the durable entry is reported as a failure;
POST-fix `safe_text` yields the fixed literal and the result returns.**

**State the count WITH the method** (the grep above), not as a bare number.

- [ ] **Step 5: Commit** -- `fix(trades): 22-A3 Task 4 -- R11-03 containment at the remaining cohort sites, including a SIXTH the brief's roster missed`.

### Task 5: the notice partial and its container

**Files:** Create `swing/web/templates/partials/entry_notice.html.j2`. Modify
`swing/web/templates/base.html.j2` (one line + comment, immediately before `<main>` at `:137`).
Test: create `tests/web/test_routes/test_22a3_entry_degraded_success.py` with tests (h) and (j).

- [ ] **Step 1: Write the failing tests (h) and (j)** -- (h)'s live assertion plus its static
template walk, and (j)'s direct render of the partial with HTML metacharacters in a warning.

- [ ] **Step 2: Run and see both fail** -- `id="entry-notice"` is in neither `/` nor `/watchlist`,
and (j) raises `TemplateNotFound`.

- [ ] **Step 3: Minimal implementation.**

`base.html.j2`, immediately before `  <main>`:

```jinja
  {#- 22-A3 -- the durable-entry notice target. STATIC AND EMPTY: it carries no
      `vm.` dereference, so the every-base-layout-VM-or-500 gotcha does not
      apply. It lives in BASE rather than in `dashboard.html.j2` because the
      entry form is reachable from `/watchlist` too, and `watchlist.html.j2`
      carries none of the four ids the entry response swaps into -- a notice
      delivered there would be silently dropped, which is the failure this arc
      exists to close. -#}
  <div id="entry-notice"></div>
```

`partials/entry_notice.html.j2`:

```jinja
{#- 22-A3 -- the durable-entry notice, delivered as an OOB swap into the
    `#entry-notice` container in base.html.j2.

    Expects:
      - trade_id (int)               REQUIRED
      - warnings (list[str])         post_commit_warnings; may be empty
      - render_failure (str | None)  safe_text() of the refresh failure, else
                                     None. When None, the refresh SUCCEEDED and
                                     this notice carries warnings only -- it
                                     must not claim otherwise. When BOTH are
                                     empty the partial renders the wrapper and
                                     NOTHING ELSE, which is how an ordinary
                                     entry CLEARS a previous banner.

    The partial owns its OWN OOB wrapper (the `hypothesis_recommendations`
    pattern) so the route never hand-builds this markup, and the swapped-in
    element keeps the id so a second entry in the same page session still
    finds its target.

    ASCII only. `<div>` at root, NEVER `<tr>`: on the success path this chunk
    travels beside OOB `<table>` chunks, and a `<tr>` at fragment root makes
    HTMX's makeFragment synthesise a table wrap that DROPS them (Bug B,
    swing/web/routes/trades.py:1970-1980). -#}
<div id="entry-notice" hx-swap-oob="true">
  {#- EMPTY WHEN THERE IS NOTHING TO SAY, AND THAT IS THE POINT. The container
      is STATEFUL: a prior warning response left a visible banner in it and
      kept this id, so an ordinary entry must emit the WRAPPER (to clear the
      old banner) and NO CONTENT (because nothing is wrong). Omitting the
      wrapper entirely would leave trade N's banner beside trade N+1. -#}
  {% if warnings or render_failure %}
  <div class="banner banner-degraded" role="alert">
    <strong>Trade #{{ trade_id }} WAS RECORDED.</strong>
    {% if render_failure %}
    The entry is durable. The page could not be refreshed afterwards
    ({{ render_failure }}). The entry EXISTS -- do NOT enter it again.
    Reload the page to see it.
    {% endif %}
    {% if warnings %}
    <ul>
      {% for w in warnings %}<li>{{ w }}</li>{% endfor %}
    </ul>
    {% endif %}
  </div>
  {% endif %}
</div>
```

- [ ] **Step 4: Run and see (h) and (j) pass.**

- [ ] **Step 5: Commit** -- `feat(web): 22-A3 Task 5 -- the durable-entry notice partial and its base-layout container`.

### Task 6: the web route consumes the result, and the durability boundary moves to the `record_entry` return

**Files:** Modify `swing/web/routes/trades.py` -- the import block (`:20-29`), a new
`_entry_notice_html` helper beside `_rerender_entry_form_with_error` (`:231`), `:1482-1497`,
`:1958-1959`, and `:1992-2056`. Test: append (a), (b), (b2), (f), (g), (g2), (g3), (k), (l), (m), (n).

**Interfaces consumed:** `log_contained`, `safe_text`, `ascii_safe` (Task 1),
`partials/entry_notice.html.j2` (Task 5).

**Interfaces produced:** `_post_commit_warnings(result, close_error) -> tuple[str, ...]` (TOTAL) and
`_entry_notice_html(templates, request, *, trade_id, warnings, render_failure) -> str` (TOTAL).

- [ ] **Step 1: Write the failing tests (a), (b), (b2), (f), (g), (g2), (g3), (k), (l), (m), (n)** per S3, including
(b2)'s duplicate-ticker REFUSAL CONTROL (an unconditional close containment must fail it, and it
discriminates because the duplicate path returns 400 rather than 500).

- [ ] **Step 2: Run and see them fail with the PRE-FIX values S3 states**, and note that they are
NOT uniform: (a) the sentinel absent from a 200; (b), (b2), (g2), (k), (m) all `500`; **(g) is a 200
with FOUR chunks and no sentinel -- NOT a 500**, because pre-fix the route never asks for the notice
template at all; **(f) FAILS pre-fix** on the 4-vs-5 chunk count and the missing notice -- only its
four-existing-refresh-chunk blast-radius sub-assertions pass pre-fix, and an earlier draft wrongly
said the whole test passed (`A3-R4-05`); **(l)** fails pre-fix on the second response's missing
notice; **(b2)'s refusal control PASSES already** -- confirm it is green BEFORE the change so its
post-change green means "unchanged", not "accidentally satisfied".

- [ ] **Step 3: Minimal implementation, in five parts.**

**(i) Imports.** Add `ascii_safe`, `log_contained` and `safe_text` to the existing
`from swing.trades.entry import (...)` block; add `import html` at module level. Run
`ruff check swing/` and take its `I`-rule ordering.

**(i-b) The TOTAL warning assembly**, beside the other module-level helpers. It exists as a function
so that NOTHING sits between the `finally` and the guarded region, and so the guard's `except`
branch can rebuild the same list without duplicating the string:

```python
def _post_commit_warnings(result, close_error) -> tuple[str, ...]:
    """The durable-entry warnings, ASCII-coerced, plus the contained close.

    TOTAL BY CONSTRUCTION: `ascii_safe` and `safe_text` cannot raise, tuple
    concatenation on strings cannot fail, and `trade_id` is an int.  It is a
    function rather than three inline statements so that nothing at all sits
    between the connection `finally` and the guarded refresh region, and so
    the guard's own `except` branch can rebuild the identical list.

    **THE WORDING IS OBSERVATION-ONLY** (Codex 22A3-R5-07): it says the close
    RAISED, never that the connection "could not be closed".  Because the
    guard catches asynchronous `BaseException`, `close()` can TAKE EFFECT and
    then raise as control returns -- the same after-effect fallacy this
    project already corrected for rollback messages at `entry.py:735-758` and
    `cohort_provenance_correction.py:2687-2706`.  A cleanup warning that is
    WRONG about the state teaches an operator to distrust the right ones.

    THE COERCION IS NOT COSMETIC: `record_entry` builds its warning strings
    with a raw `{exc!r}`, so a custom `__repr__` returning a lone surrogate
    reaches the TEMPLATE path as readily as the literal one, and
    `html.escape` preserves it until `HTMLResponse` raises `UnicodeEncodeError`
    encoding the body -- outside every guard.
    """
    warnings = tuple(ascii_safe(w) for w in result.post_commit_warnings)
    if close_error is not None:
        warnings = warnings + (
            f"the entry is DURABLE (trade {result.trade_id}) and CLOSING the "
            f"database connection afterwards RAISED "
            f"({safe_text(close_error)}); the ledger is unaffected.",)
    return warnings
```

**(ii) The helper**, beside the other module-level render helpers:

```python
def _entry_notice_html(templates, request, *, trade_id: int,
                       warnings: tuple[str, ...],
                       render_failure: str | None) -> str:
    """The durable-entry notice, as an OOB chunk.

    **THIS FUNCTION MAY NOT RAISE.**  It runs on the path that has just
    confirmed a durable money-bearing row, and a guard that produces its
    degraded response BY RENDERING A TEMPLATE re-introduces the exposure one
    layer in: if the template machinery is what failed, the guard raises, the
    app-wide handler at `swing/web/app.py:149` renders a `banner-degraded`
    alert into the form's own row at 500, and the operator reads a durable
    entry as a refusal.

    THE FALLBACK NAMES ITS OWN FAILURE, CARRIES THE WARNINGS, AND DOES NOT
    INVENT A REFRESH FAILURE.
    The reachable case is: the dashboard and all four partials rendered, the
    result carries post-commit warnings, and only THIS partial failed.  A
    fallback that dropped the warnings would ship this arc's own failure mode
    -- a warning with no reader -- inside the fix for it, and one that said
    "the page could not be refreshed" would be telling the operator something
    false.  Escaping is `html.escape` from the stdlib, deliberately: Jinja is
    the machinery that just failed.
    """
    try:
        return templates.get_template(
            "partials/entry_notice.html.j2"
        ).render(request=request, trade_id=trade_id,
                 warnings=list(warnings), render_failure=render_failure)
    except BaseException as notice_error:  # noqa: BLE001 -- the CLASS
        # **THE NOTICE'S OWN FAILURE IS NAMED AND LOGGED, NEVER SILENT**
        # (Codex 22A3-R5-03). An earlier draft returned an EMPTY wrapper when
        # there were no warnings, so a render failure on an ordinary entry
        # looked exactly like an ordinary entry: a degraded event with no
        # banner and no log. The commissioning clause says an OOB-partial
        # failure becomes a degraded success NAMING the trade and the failure,
        # and "no warnings" does not exempt it.
        log_contained(
            log,
            "22-A3: trade %s IS DURABLE and its operator notice could not be "
            "rendered (%s); the literal fallback was used.",
            trade_id, notice_error)
        parts = [
            f'<div id="entry-notice" hx-swap-oob="true">'
            f'<div class="banner banner-degraded" role="alert">'
            f'<strong>Trade #{html.escape(safe_text(trade_id))} WAS '
            f'RECORDED.</strong> This notice could not be rendered '
            f'({html.escape(safe_text(notice_error))}).'
        ]
        # Every interpolated value below is already ASCII (`ascii_safe` /
        # `safe_text`), which is what keeps `HTMLResponse` from raising
        # `UnicodeEncodeError` on a lone surrogate one frame outside this
        # guard.  MEASURED: `html.escape` PRESERVES a lone surrogate.
        if render_failure is not None:
            parts.append(
                f' The page could not be refreshed afterwards '
                f'({html.escape(render_failure)}). The entry EXISTS -- do NOT '
                f'enter it again. Reload the page.')
        else:
            parts.append(
                ' The entry EXISTS and the page was refreshed. Do NOT enter '
                'it again.')
        if warnings:
            parts.append('<ul>')
            for warning in warnings:
                parts.append(f'<li>{html.escape(ascii_safe(warning))}</li>')
            parts.append('</ul>')
        parts.append('</div></div>')
        return "".join(parts)
```

**(iii)-(v) `:1482-2056` -- ONE restructured block.** The three edits are shown together because
their correctness is a property of the SHAPE, and an executor reading them as three separate
snippets is how the two-adjacent-guards defect got written in the first place (`A3-R4-01`).

```python
    # 22-A3: bound BEFORE the outer try so the `finally` and the outer handler
    # can tell "the entry is durable" from "nothing landed".
    result = None
    close_error = None
    # ================= ONE CONTINUOUS OUTER GUARD =================
    #
    # It opens BEFORE the connection and closes only after the response has
    # been returned. TWO ADJACENT guarded regions would leave an uncovered
    # instruction boundary between their exception-table ranges -- exactly
    # where a pending asynchronous exception can land (Codex 22A3-R4-01,
    # correcting 22A3-R3-01, correcting 22A3-R1-02: the guard's start has
    # moved one frame earlier at each round of review).
    #
    # `BaseException`, not a roster: this is `record_entry`'s own post-commit
    # guard (`entry.py:504`) continued one frame out, and the contract's
    # direction governs -- a durable money-bearing row reported as a failed
    # entry is the direction that causes a DOUBLE ENTRY.
    try:
        conn = connect(cfg.paths.db_path)
        try:
            try:
                # Bug-fix-AB made the response pure-OOB and the trade_id
                # stopped being needed. **22-A3 RESTORES THE ASSIGNMENT**, for
                # a different reason: `EntryResult` is a statement about the
                # DURABLE STATE OF THE LEDGER, the refresh below is
                # best-effort, and the degraded response must NAME the trade.
                result = record_entry(
                    ...unchanged args, including cfg=cfg...
                )
            except MissingPreTradeFieldsException as exc:
                ...unchanged; returns a 400 fragment...
            except SoftWarnError:
                ...unchanged; returns the confirm fragment...
            except DuplicateOpenPositionError as exc:
                ...unchanged; returns a 400 fragment...
            except HardCapError as exc:
                ...unchanged; returns a 400 fragment...
            except PatternEvaluationAnchorError as exc:
                ...unchanged; returns `_reject_pe_anchor(...)`...
            except ValueError as exc:
                ...unchanged; returns a 400 fragment or re-raises...
            except sqlite3.IntegrityError as exc:
                ...unchanged; returns a 400 fragment or re-raises...
        finally:
            # **THE DURABILITY BOUNDARY IS THE BINDING OF `result`.**
            # `close()` can raise, and the pre-arc code ran it AFTER a durable
            # result existed and BEFORE anything could catch it -- so a
            # failing close became the refusal-shaped 500 over a durable row.
            #
            # THE ASYMMETRY IS THE POINT: before the durable fact exists an
            # error is the honest answer, so `result is None` RE-RAISES and
            # every pre-existing refusal path is byte-unchanged. After it
            # exists, an error is a wrong answer in the expensive direction.
            try:
                conn.close()
            except BaseException as exc:  # noqa: BLE001 -- the CLASS
                if result is None:
                    raise
                close_error = exc

        # ============ POST-DURABILITY, INSIDE THE SAME OUTER TRY ============
        #
        # `record_entry` HAS RETURNED, so the entry is DURABLE by contract
        # (`docs/22-a-merge-request.md` S4.4, clause 1). Everything below is a
        # PAGE REFRESH. Before 22-A3 a failure here reached the app-wide
        # handler at `swing/web/app.py:149` which -- because `entry-form-` is
        # a row-swap target (`app.py:38-45`) and `base.html.j2:60-64` makes
        # 5xx SWAP -- put a `banner-degraded` alert in the form's OWN ROW at
        # 500: the same surface, class and position the duplicate-position and
        # hard-cap REFUSALS use. The operator could not tell a refused entry
        # from a durable one, and the refusal reading is retry-inviting.
        #
        # TWO EXPOSURES REMAIN AND BOTH ARE OUTSIDE THIS ROUTE:
        # `RequestIdMiddleware` (`swing/web/middleware/request_id.py:22-34`)
        # is OUTERMOST and access-logs AFTER this response is built; and
        # response DELIVERY (ASGI send / transport / client disconnect)
        # happens after the route returns at all. Flagged, not fixed --
        # neither is in 22-A3's envelope (S2.0 boundaries one and four).
        post_commit_warnings = _post_commit_warnings(result, close_error)
        dashboard_vm = build_dashboard(...)          # unchanged
        status_strip_html = ...                      # unchanged
        open_positions_html = ...                    # unchanged
        watchlist_section_html = ...                 # unchanged
        hyp_recs_section_html = ...                  # unchanged
        # **ALWAYS EMITTED** (Codex 22A3-R3-04). `#entry-notice` is STATEFUL:
        # a prior warning response replaced the empty container with a visible
        # banner and kept the id. Emitting nothing here would leave trade N's
        # "WAS RECORDED" banner on screen beside trade N+1. An ordinary entry
        # therefore emits the chunk EMPTY, which clears it.
        notice_html = _entry_notice_html(
            templates, request, trade_id=result.trade_id,
            warnings=post_commit_warnings, render_failure=None)
        return HTMLResponse(Markup(
            f'{notice_html}'
            f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
            f'<div id="open-positions" hx-swap-oob="true">'
            f'{open_positions_html}'
            f'</div>'
            f'<section id="watchlist-top5" hx-swap-oob="true">'
            f'{watchlist_section_html}'
            f'</section>'
            f'{hyp_recs_section_html}'
        ))
    # THE SINGLE OUTER HANDLER. It covers the connection block and its
    # `finally`'s tail, the warning assembly, the refresh, the four renders
    # and the response construction, with NO GAP anywhere between them.
    except BaseException as post_bind_error:  # noqa: BLE001 -- the CLASS
        if result is None:
            raise
        log_error = log_contained(
            log,
            "22-A3: trade %s IS DURABLE and a step AFTER the entry failed "
            "(%s). A DEGRADED-SUCCESS response is returned naming the trade; "
            "reporting a durable write as a failure is what causes a double "
            "entry.",
            result.trade_id, post_bind_error)
        notice_warnings = _post_commit_warnings(result, close_error)
        if log_error is not None:
            notice_warnings = notice_warnings + (
                f"the ERROR log for this degraded response could not be "
                f"emitted ({safe_text(log_error)}); the ledger is "
                f"unaffected.",)
        return HTMLResponse(Markup(_entry_notice_html(
            templates, request, trade_id=result.trade_id,
            warnings=notice_warnings,
            render_failure=safe_text(post_bind_error))))
```

**`result` CANNOT BE `None` at the post-durability marker**, and the reason is structural rather
than hopeful: every `except` clause in the inner block RETURNS, so a refusal never reaches it;
anything the inner block raises and no clause catches propagates through the `finally` into the
OUTER handler, which re-raises on `result is None`; and the `finally` itself re-raises on
`result is None`. The only way to arrive at the marker is the inner block completing normally, which
binds `result`. *(The one window this does not cover is Python's CALL-to-STORE gap -- an
asynchronous exception between `record_entry` returning and `STORE_FAST`. One bytecode wide, not
closable by any caller-only restructuring, DECLARED at S7.4.)*

**EVERY EXISTING STATEMENT IN `:1484-2046` MOVES VERBATIM** -- the seven `except` clauses gain one
indentation level from the new outer `try`, the refresh statements gain one and lose their old
position, and the Bug-fix-AB and hyp-recs comment blocks travel with them. **No content changes.**
**Verify that mechanically before moving on:** `git diff -w -- swing/web/routes/trades.py` must show
content changes ONLY on the genuinely new lines (the two `result`/`close_error` initialisations, the
outer `try:`, the close containment, the `_post_commit_warnings` call, the `notice_html` call, the
outer `except` block, and the comments this task adds). If `-w` shows a content change inside a
moved statement, something was retyped rather than moved.

- [ ] **Step 4: Run and see (a), (b), (b2), (f), (g), (g2), (g3), (k), (l), (m), (n) pass.** Then run the whole
web package -- `python -m pytest tests/web -q` -- because (f)'s blast-radius half is only worth what
the pre-existing route tests confirm.

- [ ] **Step 4b: RUN THE (k) MUTATION AND RECORD THE RED** (`A3-R4-13` -- S3(k) claimed this evidence
and no step ordered it). Delete the `ascii_safe(...)` call from `safe_text`'s first branch; run
`python -m pytest tests/web/test_routes/test_22a3_entry_degraded_success.py -q -n 0 -k lone_surrogate`;
**see it FAIL with a 500**; restore the call; re-run and see it pass. Record both results. Without
this the coercion is decorative as far as the evidence goes.

- [ ] **Step 5: Commit** -- `feat(web): 22-A3 Task 6 -- the entry route consumes the EntryResult; a post-entry render or close failure becomes a degraded SUCCESS naming the trade`.

### Task 7: the CLI consumes the field, and contains its own post-durability close

**Files:** Modify `swing/cli.py` -- the function-local import block at `:650-660`, `:666-667`,
`:833-834`, and the echo block at `:835`. Test: create
`tests/cli/test_cli_trade_entry_post_commit_warnings.py` with (c), (c2), (c3) and (c4).

- [ ] **Step 1: Write the failing tests (c), (c2), (c3) and (c4)** per S3 -- (c) with a NON-ASCII injected
warning and the `.isascii()` gate, and (c2) with its duplicate-ticker control asserting the exact
ESCAPING EXCEPTION (`type(result.exception) is sqlite3.OperationalError`), because "still fails"
does not discriminate on this surface -- and (c3), the OUTPUT-containment discriminator, without
which an implementation that reads the warnings and contains the close but leaves `click.echo`
unguarded passes everything else (`A3-R4-06`).

- [ ] **Step 2: Run and see them fail** -- (c): the sentinel is printed nowhere while `exit_code` is
already 0 (the control); (c2): `exit_code` is non-zero and the success line never printed.

- [ ] **Step 3: Minimal implementation.**

Add `ascii_safe` and `safe_text` to the function-local
`from swing.trades.entry import (...)` block at `:650-660`. Then:

```python
    # 22-A3: bound before the outer try, exactly as in Task 6, and for the
    # same reason. THE CLI IS THE CASE WHERE `KeyboardInterrupt` IS FULLY
    # DELIVERABLE -- this is the main thread, so S2.5's threadpool argument
    # does not apply here and the guard is not symmetry, it is necessity.
    result = None
    close_error = None
    # ONE CONTINUOUS OUTER GUARD, opened before the connection and closed only
    # after the LAST line is printed. Two adjacent guards would leave an
    # uncovered instruction boundary between them (Codex 22A3-R4-01).
    try:
        conn = connect(cfg.paths.db_path)
        try:
            ...unchanged: the request assembly, `record_entry`, and the two
            existing `except` clauses that raise UsageError / ClickException...
        finally:
            try:
                conn.close()
            except BaseException as exc:  # noqa: BLE001 -- the CLASS
                if result is None:
                    raise
                close_error = exc

        # ---- POST-DURABILITY OUTPUT, INSIDE THE SAME OUTER TRY ----
        #
        # **THE FIELD FINALLY HAS A READER.** `post_commit_warnings` carries
        # what went wrong AFTER the entry became durable, so it is a caveat ON
        # a success: stderr, and the EXIT CODE IS NOT TOUCHED. The exit status
        # is a statement about the ledger and the ledger has the row; a
        # non-zero exit here would be the failure-conversion this arc closes,
        # reintroduced at the shell.
        #
        # **`ascii_safe` WRAPS THE WHOLE CONSTRUCTED LINE, NOT SELECTED
        # FIELDS** (Codex 22A3-R4-08). `--ticker` is unrestricted text and
        # `.upper()` does not make it ASCII, so a non-ASCII TICKER reaches
        # these lines just as a non-ASCII warning does -- and Windows cp1252
        # stdout raises on either (CLAUDE.md; pytest's `capsys` hides it).
        # Coercing the warning but not the line around it is a half-fix.
        post_commit_warnings = result.post_commit_warnings
        if close_error is not None:
            post_commit_warnings = post_commit_warnings + (
                f"the entry is DURABLE (trade {result.trade_id}) and CLOSING "
                f"the database connection afterwards RAISED "
                f"({safe_text(close_error)}); the ledger is unaffected.",)
        for post_commit_warning in post_commit_warnings:
            click.echo(
                ascii_safe(f"WARN (post-commit): {post_commit_warning}"),
                err=True)
        if result.warning:
            click.echo(ascii_safe(f"WARN: {result.warning}"), err=True)
        if result.watchlist_archived:
            click.echo(ascii_safe(
                f"Watchlist row for {ticker} archived (reason: entered)"))
        click.echo(ascii_safe(
            f"Trade id {result.trade_id}: {ticker} {shares} sh @ "
            f"${entry_price:.2f}, stop ${initial_stop:.2f}"))
    except BaseException:  # noqa: BLE001 -- the CLASS
        if result is None:
            raise
        # DURABLE. `click.echo` can raise `BrokenPipeError`
        # (`swing trade entry | head`) or any other output error, and an
        # uncontained failure here would leave a durable entry exiting
        # NON-ZERO with no confirmation -- this arc's own failure mode, at the
        # last statement. What the containment costs is declared at S7.9:
        # there is nowhere left to write, so the exit code becomes the only
        # remaining signal, which is exactly why it must be the TRUE one.
        return
```

**This REPLACES the existing structure at `:666-843`.** The three existing `click.echo` calls move
INSIDE the containment -- that is the point of the change -- and each is wrapped WHOLE in
`ascii_safe`. Preserve their text and order exactly; the only edits are the coercion, the enclosing
guard, and the two initialisations.



- [ ] **Step 4: Run and see (c), (c2), (c3) and (c4) pass.** `ruff check swing/`.

- [ ] **Step 5: Commit** -- `feat(cli): 22-A3 Task 7 -- print post_commit_warnings ASCII-coerced, contain the post-durability close AND the output itself; the exit code stays a statement about the ledger`.

### Task 8: the belt control

**Files:** Test only -- append (e) to `tests/web/test_routes/test_22a3_entry_degraded_success.py`.

- [ ] **Step 1: Write test (e)** -- the CONTROL of S3(e), with `CONTROL` in its docstring and the
statement that it passes under both paths by design.
- [ ] **Step 2: Run it -- it passes immediately.** That is expected and it is why it is labelled.
- [ ] **Step 3: Commit** -- `test(web): 22-A3 Task 8 -- the ux_trades_one_open_per_ticker control`.

### Task 9: THE OPERATOR-WITNESSED BROWSER GATE (S6) -- **a TASK, ordered, not an appendix**

> **This task exists because round 3 found the ladder had none** (`A3-R3-06`): S6 was binding and
> S6's own teardown implied it ran before the review, but no task ordered it or recorded its result,
> so it could be skipped without anything noticing. It runs HERE -- after the code is green per-task
> and BEFORE the pre-review suite and the Codex loop -- because its observations can change the
> design, and a design changed after its review has not been reviewed.

- [ ] **Step 1: Run S6 in full, step by step**, with the operator: setup S6.0 (1-6), then Steps 1
      through 8. **One step, his result, then the next.** A batched runbook collapses the gate into
      a self-report.
- [ ] **Step 2: Record every observation**, including the two the plan explicitly does NOT assert:
      the form row's fate on `/watchlist` (S6 Step 2) and on the degraded path (S6 Step 5 item 6).
- [ ] **Step 3: IF ANY OBSERVATION FAILS, STOP AND ROUTE.** Do not fix at the gate. Amend S2/S3 and
      the affected tests first, then re-run the per-task tests, the suite, THIS gate, and the
      adversarial review against the amended design. **A `<tr>` primary stub in particular is NOT
      pre-authorised** -- it contradicts S2.1, test (b) and Task 6.
- [ ] **Step 4: Confirm the teardown** -- probes reverted, `git status --short` empty, port free,
      scratch root deleted, a fresh shell for anything after.

### Task 10: the PRE-REVIEW full-suite gate

- [ ] **Step 1:** `python -m pytest -m "not slow" -q` from the worktree. Compare against the
**12077 passed / 13 skipped** baseline measured on `0698f3bb` (plan header). Fix any failure to
green BEFORE the Codex loop -- cross-cutting invariants (VM manifests, CSS contracts, template
walks) are not exercised per-task, and the review must converge on a green diff.
- [ ] **Step 2:** `ruff check swing/` -- clean.
- [ ] **Step 3:** `git status --short` empty; `git log <base>..HEAD --format='%H%n%(trailers)'`
shows empty trailers on every commit.
- [ ] **Step 4:** Run the Codex adversarial loop to convergence per the dispatch recipe S3. **The
gate's observations (Task 9) are part of the tree under review** -- if any of them changed the
design, the loop reviews the CHANGED design, not the one the gate was run against.

### Task 11: the POST-CONVERGENCE final-head gate

> **This task exists because the recipe requires the full suite at BOTH points** (before the review,
> and again on the final head): review fixes can invalidate the pre-review evidence, and a
> pre-review pass count carried forward as the post-review result is the false-green failure this
> project has a standing rule against (Codex round 1, `A3-R10`).

- [ ] **Step 1:** After the last review-fix commit, `python -m pytest -m "not slow" -q` on the FINAL
head. **READ the tail and record the actual numbers** -- never carry Task 10's forward.
- [ ] **Step 2:** `ruff check swing/` on the final head.
- [ ] **Step 3:** Re-run the trailer audit on the full range.
- [ ] **Step 4:** Record in the return report: the final commit SHA, the pass/skip counts read off
THAT head, and the delta against the 12077/13 baseline with the new tests accounted for.
- [ ] **Step 5:** Confirm the browser gate (Task 9) was run against THIS design -- if any review fix
changed the response shape, the notice partial, or the notice-emit rule, **the gate is re-run.**

---

## S6. THE OPERATOR-WITNESSED BROWSER GATE -- **BINDING for this surface**

TestClient asserts BYTES; it cannot see a swap land, a table get dropped by HTML5 nested-table parse
rules, or an OriginGuard 403. CLAUDE.md makes the operator browser check binding for HTMX work, and
this arc changes the response of the money-bearing entry form. **The gate is STEP BY STEP: one step,
the operator's result, then the next.** A batched runbook collapses the gate into a self-report.

### S6.0 THE GATE RUNS IN A FULLY ISOLATED HOME -- non-negotiable, and "scratch DB" is NOT enough

**Two review rounds each found this section unsafe, and the second found the first fix
insufficient.** Round 1 (`A3-R1-01`): the gate launched `swing web` with no `--config`, resolving
`swing-data/swing.db` under the operator's home -- the LIVE money-bearing ledger -- and then told
him to create probe entries in it. Round 2 (`A3-R2-04`): redirecting `[paths]` alone is still not
isolation, because **`web_cmd` calls `apply_overrides()`, which reads the operator's real
`~/swing-data/user-config.toml`** -- and those overrides can carry live Schwab credentials, after
which startup resolves and may refresh the real `~/swing-data/schwab-tokens.<env>.db` and make
network calls. A refusal check on `cfg.paths.db_path` proves nothing about either.

**So the isolation is at the HOME level, and CLAUDE.md already names this exact trap** in the
neighbouring rule that tests touching `write_user_overrides` must monkeypatch **BOTH `USERPROFILE`
AND `HOME`**, because `_user_home()` reads them directly.

**Setup, in order. Do not start the server until step 5 has printed and verified three paths.**

**1. Create a UNIQUE scratch root and a redirected config.** Not a fixed directory name: a fixed one
collides between runs and an `rmtree` of it can destroy retained evidence (`A3-R2-13`).

```python
python - <<'PY'
import pathlib, tempfile
src = pathlib.Path("swing.config.toml")
scratch = pathlib.Path(tempfile.mkdtemp(prefix="22a3-gate-"))
(scratch / "swing-data").mkdir(parents=True)
REDIRECT = {
    "db_path": "swing-data/swing.db",
    "data_dir": "swing-data",
    "logs_dir": "swing-data/logs",
    "charts_dir": "swing-data/charts",
    "backups_dir": "swing-data/backups",
    "prices_cache_dir": "swing-data/prices-cache",
    "exports_dir": "exports",
}
out = []
for line in src.read_text(encoding="utf-8").splitlines(True):
    for key, sub in REDIRECT.items():
        if line.startswith(key + " ="):
            line = f'{key} = "{(scratch / sub).as_posix()}"\n'
            break
    out.append(line)
cfg = scratch / "swing.config.toml"
cfg.write_text("".join(out), encoding="utf-8")
print("SCRATCH ROOT:", scratch)
print("SCRATCH CONFIG:", cfg)
PY
```

Record BOTH printed paths; every later step uses them and the teardown deletes **only** the recorded
root. `finviz_inbox_dir` and `rs_universe_path` stay project-relative: they are READ paths the gate
never writes to. `exports_dir` is redirected so nothing lands in the repo tree and dirties step 8's
`git status`.

**2. REDIRECT THE HOME *AND* CLEAR THE SCHWAB ENV CHANNEL for every subsequent command.** Round 3
(`A3-R3-05`) found that the home redirect alone is still not isolation: `SchwabConfig` defaults to
`environment = "production"` and `marketdata_ladder_enabled = True` (`swing/config.py:460-464`), and
credential resolution reads **`SCHWAB_CLIENT_ID` / `SCHWAB_CLIENT_SECRET` FROM THE ENVIRONMENT
FIRST** (`swing/integrations/schwab/auth.py:177-186`). If those are already exported in the
operator's shell, an empty scratch home changes nothing: the production ladder stays active and
startup attempts an authenticated client against the live service.

So, in the same shell: **(a)** unset both variables, **(b)** set
`marketdata_ladder_enabled = false` in the SCRATCH config (never the tracked one), **(c)** redirect
both home variables:

```
PowerShell:  Remove-Item Env:SCHWAB_CLIENT_ID -EA SilentlyContinue
             Remove-Item Env:SCHWAB_CLIENT_SECRET -EA SilentlyContinue
             $env:HOME="<SCRATCH ROOT>"; $env:USERPROFILE="<SCRATCH ROOT>"; $env:PYTHONPATH="."
Bash:        unset SCHWAB_CLIENT_ID SCHWAB_CLIENT_SECRET
             export HOME="<SCRATCH ROOT>"; export USERPROFILE="<SCRATCH ROOT>"; export PYTHONPATH=.
```

and split the two Schwab settings across the two files, **because `load()` DELETES
`environment` from a tracked-style config** (`swing/config.py:813-819` pops `environment`,
`account_hash`, `lookback_days` and `callback_url` -- they are user-config-only). A draft that put
`environment = "sandbox"` in the scratch `swing.config.toml` and then asserted it would have made
the gate's own refusal script FAIL EVERY TIME (`A3-R4-02`):

**In the SCRATCH `swing.config.toml`** (tracked-style; `marketdata_ladder_enabled` IS read from
here):

```toml
[integrations.schwab]
marketdata_ladder_enabled = false
```

**In `<SCRATCH ROOT>/swing-data/user-config.toml`** (created by the gate; this is the file
`apply_overrides()` reads, and the scratch home makes it empty unless the gate writes it):

```toml
[integrations.schwab]
environment = "sandbox"
```

**BOTH variables, for the reason CLAUDE.md already records:** `_user_home()` reads them
unmonkeypatched, and setting only one lets the override reader find the operator's real file. Every
`python -m swing.cli ...` below runs in THIS shell.

**3. Migrate the scratch database:**
`python -m swing.cli --config "<SCRATCH CONFIG>" db-migrate`

**4. SEED one watchlist row PER GATE ENTRY.** There is no `swing watchlist` CLI command; this is the
shape `tests/web/conftest.py:272-299` uses. **EIGHT tickers, counted against the steps rather than
guessed** (`A3-R2-05` found the soft-warn collision, `A3-R4-03` then found the count two short):
Steps 1-5 consume `GATE1`-`GATE5`, **Step 5b needs TWO more** (`GATE6` for its warning entry and
`GATE7` for the ordinary entry that must clear the banner), and the CLI Step 7 needs `GATE8`. With
`soft_warn_open = 4` and the tracked limits, the run would also walk into a `SoftWarnError` confirm
fragment partway through and the degraded-path observation would never happen -- hence the raised
scratch-only limits below. Seed `GATE1`..`GATE8`:

```python
python - "<SCRATCH CONFIG>" <<'PY'
import pathlib, sys
from swing.config import load
from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
cfg = load(pathlib.Path(sys.argv[1]))
conn = connect(cfg.paths.db_path)
try:
    for n in range(1, 9):
        upsert_watchlist_entry(conn, WatchlistEntry(
            ticker=f"GATE{n}", added_date="2026-09-02",
            last_qualified_date="2026-09-02", status="watch",
            qualification_count=1, not_qualified_streak=0,
            last_data_asof_date="2026-09-01",
            entry_target=100.0, initial_stop_target=90.0,
            last_close=99.0, last_pivot=None, last_stop=None,
            last_adr_pct=2.0, missing_criteria=None, notes=None))
    conn.commit()
finally:
    conn.close()
print("SEEDED GATE1..GATE8")
PY
```

**AND RAISE THE SCRATCH-ONLY POSITION LIMITS** so the soft-warn confirm never pre-empts the response
under test -- edit the scratch config (never the tracked one):
`[position_limits] soft_warn_open = 50`, `hard_cap_open = 60`. **Then assert the open count before
each probe step** (`SELECT COUNT(*) FROM trades WHERE state IN ('entered','managing',
'partial_exited')`) so a surprise soft-warn is caught as a gate error rather than mistaken for the
behaviour under test.

**5. PROVE all three isolation properties, and REFUSE otherwise:**

```python
python - "<SCRATCH CONFIG>" "<SCRATCH ROOT>" <<'PY'
import os, pathlib, sys
from swing.config import load
cfg_path, root = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]).resolve()
db = pathlib.Path(load(cfg_path).paths.db_path).resolve()
home = pathlib.Path(os.environ.get("HOME", "")).resolve()
prof = pathlib.Path(os.environ.get("USERPROFILE", "")).resolve()
# **`apply_overrides(load(...))`, NOT bare `load(...)`** -- the running web
# command uses `apply_overrides` (`swing/cli.py:4597`), so the proof must
# measure the SAME effective config the server will use (A3-R4-02).
from swing.config_overrides import apply_overrides
cfg = apply_overrides(load(cfg_path))
print("RESOLVED DB      :", db)
print("HOME             :", home)
print("USERPROFILE      :", prof)
print("user-config would be:", home / "swing-data" / "user-config.toml")
print("schwab env       :", cfg.integrations.schwab.environment)
print("ladder enabled   :", cfg.integrations.schwab.marketdata_ladder_enabled)
assert root in db.parents, f"REFUSING: db {db} is not under {root}"
assert home == root, f"REFUSING: HOME {home} is not the scratch root"
assert prof == root, f"REFUSING: USERPROFILE {prof} is not the scratch root"
assert "SCHWAB_CLIENT_ID" not in os.environ, "REFUSING: SCHWAB_CLIENT_ID is set"
assert "SCHWAB_CLIENT_SECRET" not in os.environ, (
    "REFUSING: SCHWAB_CLIENT_SECRET is set")
assert cfg.integrations.schwab.marketdata_ladder_enabled is False, (
    "REFUSING: the market-data ladder is still enabled")
assert cfg.integrations.schwab.environment != "production", (
    "REFUSING: the scratch config still says production")
print("OK -- db, HOME, USERPROFILE, env credentials and ladder are all safe")
PY
```

**Do not copy, open, or read the operator's live database or user-config at any point** -- not to
seed, not to compare. The seed above builds its world from nothing. With the scratch home empty AND
the two environment variables cleared AND the ladder disabled in the scratch config, no Schwab
credentials resolve through ANY tier of the cascade (env > cfg > prompt), so no authenticated client
is constructed and no token database is touched. **The three-channel check above is what establishes
that, rather than the sentence you are reading**: an earlier draft asserted the same conclusion from
the home redirect alone and it was FALSE.

**6. Start the server on a NON-DEFAULT port**, in the redirected shell:
`python -m swing.cli --config "<SCRATCH CONFIG>" web --port 8099`, then browse to
`http://127.0.0.1:8099/`. (Running from inside the worktree matters: the `swing` entry point is
editable-installed from the MAIN tree and would serve the wrong code -- hence `PYTHONPATH=.` plus
`python -m`.)

### The steps

**Step 1 -- THE ORDINARY ENTRY IS UNCHANGED (the regression check, first on purpose).** Enter
`GATE1` from the dashboard watchlist row. Expect: the form row disappears; open positions, the
status strip, watchlist top-5 and hyp-recs all rebuild; **NO notice banner appears anywhere.**
*(Pins S2.4. A notice on an ordinary entry means the emit gating is wrong.)*

**Step 2 -- THE SAME, FROM `/watchlist`, AND FORM REMOVAL IS BINDING HERE.** Enter `GATE2` from the
standalone watchlist page. Expect: no notice; no HTMX console error; **and REPORT whether the form
row disappears.**

> **Why this one is binding and S7.10 changed because of it (`A3-R2-07`):** `/watchlist` carries NONE
> of the four OOB targets, so on THAT page the ordinary and warning responses rely on the empty
> primary swap for form removal exactly as the degraded path does. An earlier draft said only the
> degraded path had that uncertainty and proposed a degraded-only `<tr>` correction -- which would
> not have helped here. **If removal fails on this step it is a PRE-EXISTING defect this arc merely
> surfaced** (the pure-OOB response predates it), and it is out of envelope: report it, do not fix
> it inside this arc.

**Step 3 -- THE WARNING PATH.** Apply this UNCOMMITTED probe to `swing/web/routes/trades.py`. **The
probe matches the indentation of the `result = record_entry(` statement it follows** (`A3-R2-06`
first found the snippet unanchored; `A3-R5-01` then found the anchor itself stale after Task 6's
restructure -- **SS-2 swept the artifact for every other indentation claim afterwards**):

**The indentation is SIXTEEN spaces, not twelve** (`A3-R5-01`): after Task 6 the nesting is outer
guard -> connection `try` -> refusal-handler `try`, so `result = record_entry(` sits three levels in.
An earlier draft's twelve-space snippet was written against the pre-restructure shape and would not
have parsed:

```python
                result = record_entry(                   # <- existing, 16 spaces
                    ...                                  # <- existing
                )                                        # <- existing
                from dataclasses import replace as _probe_replace   # PROBE, 16
                result = _probe_replace(                            # PROBE
                    result, post_commit_warnings=(                  # PROBE
                        "GATE PROBE: the entry is DURABLE -- do NOT retry.",))
```

Restart, enter `GATE3` from the dashboard. Expect, all four:
1. the notice banner appears at the top of the page, naming the trade and carrying the probe text;
2. **open positions, watchlist top-5 and hyp-recs ALL still render their tables** -- *this is the
   binding one.* It is the only occasion where the notice chunk travels beside OOB `<table>` chunks,
   so it is the only occasion Bug B could fire; if any section comes back as a bare heading with no
   rows, the notice must move out of that response;
3. the form row disappears;
4. no HTMX error in the browser console.

**Step 4 -- THE WARNING PATH FROM `/watchlist`.** Same probe, enter `GATE4` from `/watchlist`.
Expect the notice banner to appear, and again REPORT the form row's fate. *(This is what the
base-template container buys; if the notice does not appear here, the container is in the wrong
file.)*

**Step 5 -- THE DEGRADED PATH.** Replace the Step-3 probe with a raise placed **immediately before
`dashboard_vm = build_dashboard(...)`, at that statement's own EIGHT-space indentation**.

**Do NOT look for "the `try` that opens the refresh region" -- there is not one** (`A3-R5-01`).
After Task 6 there is exactly ONE outer `try`, and it opens before `connect()`; a probe placed at
ITS start would raise before any entry exists and the gate would observe nothing:

```python
        # ... the connection block and its finally have completed ...
        post_commit_warnings = _post_commit_warnings(result, close_error)
        raise RuntimeError("GATE PROBE: dashboard rebuild failed")   # PROBE, 8
        dashboard_vm = build_dashboard(...)              # <- existing
```

Restart, enter `GATE5`. Expect, all six:
1. **no red refusal-looking banner in the form's row** -- the pre-arc behaviour, and what this arc
   exists to remove;
2. the notice banner appears, naming the trade id and saying the entry EXISTS and do NOT re-enter;
3. **the dashboard's other sections keep their PRE-SUBMIT content** (stale, not blank -- nothing was
   OOB-swapped, so nothing was overwritten);
4. the network tab shows **200**, not 500;
5. reloading shows the trade in open positions -- i.e. the notice told the truth;
6. **REPORT the form row's fate here too.** If it REMAINS on the DASHBOARD (where Step 1 showed the
   OOB rebuild removes it), the operator can resubmit over a durable entry. **DO NOT apply a fix at
   the gate.** A `<tr>` primary stub is the obvious candidate and it is exactly what an earlier
   draft pre-authorised -- but it CONTRADICTS S2.1's "never a `<tr>` at fragment root", test (b)'s
   `"<tr" not in resp.text`, and Task 6's specified response, and applying it here would mutate the
   design AFTER the evidence for it was collected (`A3-R3-06`). **STOP and route:** the observation
   goes in the return report, S2.1/S3(b)/Task 6 are amended by whoever owns the decision, and the
   suite, this gate and the adversarial review are re-run against the amended design.

**Step 5b -- THE NOTICE CLEARS ITSELF (the STATEFUL-container check, `A3-R3-04`).** With the
Step-3 warning probe RE-APPLIED, enter `GATE6` and confirm the banner appears. Then REMOVE the
probe, restart, and enter `GATE7` **without reloading the page in between**.
Expect: **the previous trade's `WAS RECORDED` banner DISAPPEARS**, the new entry rebuilds the page
normally, and no banner remains. *(This is the only step that can see the defect S2.4 was rewritten
for: a single-request check cannot.)*

**Step 6 -- THE BELT, WITH THE OPERATOR'S OWN EYES -- AND IT NEEDS A FORM PREPARED IN ADVANCE.**

**Read this before Step 5, because it changes what you do there** (`A3-R5-02`): after `GATE5` is
entered, the dashboard's entry affordances no longer offer it -- open positions are filtered out of
the watchlist/hyp-recs surfaces -- so "submit GATE5 again" has NO FORM TO SUBMIT. **Before Step 5,
open `GATE5`'s entry form in a SECOND BROWSER TAB and leave it there untouched.** After the probes
are removed, submit that stale form.

Expect the familiar `Already an open position in GATE5` 400 rendered into the form's row. *(The
control: nothing about the refusal surface moved. Note the message names the TICKER, not a trade id
-- S1.5.)*

**Step 7 -- THE CLI HALF.** `swing trade entry` refuses without the full pre-trade field set
(`swing/trades/state.py` `OPERATION_REQUIRED_FIELDS`, surfaced as `MissingPreTradeFieldsException`),
so the abbreviated form an earlier draft gave would have died at validation before ever reaching
`record_entry` (`A3-R3-07`). **The complete command, with every required flag** (the eleven in
`tests/conftest.py:cli_entry_pre_trade_args()` plus the six positional-value ones):

```
python -m swing.cli --config "<SCRATCH CONFIG>" trade entry \
  --ticker GATE8 --entry-date 2026-09-02 --entry-price 100.0 --shares 1 \
  --initial-stop 90.0 --rationale aplus-setup \
  --thesis test-thesis --why-now test-why-now --invalidation stop-hit \
  --expected-scenario win --premortem-technical tech-risk \
  --premortem-market-sector market-risk --premortem-execution execution-risk \
  --emotional-state calm --manual-entry-confidence normal \
  --market-regime Bullish --catalyst technical_only
```

**The CLI probe's exact placement** -- immediately after the `result = record_entry(...)` call in
`swing/cli.py`, which sits at SIXTEEN spaces after Task 7 adds its outer guard (`A3-R5-01`), so the
probe matches it:

```python
                result = record_entry(                          # <- existing, 16
                    ...                                         # <- existing
                )                                               # <- existing
                from dataclasses import replace as _probe_replace   # PROBE, 16
                result = _probe_replace(                            # PROBE
                    result, post_commit_warnings=(                  # PROBE
                        "GATE PROBE: the entry is DURABLE -- do NOT retry.",))
```

Expect the `WARN (post-commit):` line on stderr, the `Trade id N:` line on stdout, and
`$LASTEXITCODE` / `echo $?` = **0**.

**Step 8 -- TEARDOWN, and it is part of the gate.**
1. Revert every probe. Confirm `git status --short` is EMPTY and `git diff` is empty **before** the
   review diff is generated -- a probe left in the tree would be reviewed as the deliverable.
2. Stop the server and **verify the port is actually free** -- `Get-NetTCPConnection -LocalPort 8099`
   / `Stop-Process -Force`, then re-check. A detached `swing web` survives a task stop.
3. Delete **only the recorded scratch root** printed at step 1.
4. Open a FRESH shell (or unset `HOME`/`USERPROFILE`) before doing anything else -- the redirected
   environment must not outlive the gate.

---

## S7. ACCEPTED LIMITATIONS -- each with its reason, challenge explicitly invited

> These are DECISIONS, not oversights. **A finding that re-raises one of these without engaging its
> stated reason is out of scope; a finding that shows a reason is UNSOUND -- that the argument does
> not hold, that the limitation is larger than declared, or that a cheaper alternative was
> mis-rejected -- is in scope and is what this review is for.** Round 2 did exactly that to entry 5
> below and the entry was rewritten rather than defended.

1. **The belt covers only an OPEN same-ticker retry.** A ticker CLOSED between the two attempts is
   unbelted, and this arc does not change that. *Reason:* the uncovered direction needs the
   attempt-identity primitive, which is 22-A4's whole subject; the ruling at
   `docs/22-a-merge-request.md` S4.4 item 3 assigns it. **This arc reduces the FREQUENCY of the
   retry rather than the belt's coverage** -- the operator is now told the entry exists.
2. **`record_entry`'s clause-2 residual is UNTOUCHED.** A commit whose own return is lost still
   re-raises over a row that may be durable. *Reason:* envelope-forbidden, and it needs the
   primitive. 22-A3 is the PRECONDITION for 22-A4 rather than a partial version of it.
3. **THE CLAIM IS ROUTE-AND-CLI-LOCAL: `RequestIdMiddleware` runs OUTERMOST and access-logs AFTER
   the response is built**, so a raising access-log sink still converts a degraded-success 200 into
   a 500. *Reason:* `swing/web/middleware/request_id.py` is outside the envelope; the brief says an
   out-of-scope defect is flagged, never fixed inline. Flagged at S8 item 6 with its correction.
   **Everything this plan CLAIMS, it tests; what it cannot reach, it names.**
4. **THE CLAIM STARTS AT THE BINDING OF `result`, NOT AT THE `record_entry` RETURN.** Python's
   CALL-to-STORE window is real: the function can return after committing and an asynchronous
   exception can be delivered before the `STORE_FAST` that binds `result`, leaving the ledger
   durable, `result is None`, and this plan's logic re-raising. *Reason:* **no caller-only
   restructuring closes it** -- it is one bytecode wide and it sits on the far side of the
   assignment every guard here keys on. Closing it needs a service/caller protocol, i.e. work
   outside this envelope. **The direction is the belt-covered one** (told-failed over a durable row
   -> retry -> `ux_trades_one_open_per_ticker` refuses), the same direction and the same belt as the
   declared clause-2 residual.
5. **The literal fallback duplicates the partial's banner.** *Reason:* totality (S2.3). The
   OOB-partial-drift gotcha's subject is markup duplicating a FULL-PAGE surface; this duplicates a
   handful of elements and escapes every interpolated value with `html.escape` over ASCII-coerced
   text. **This entry has been narrowed TWICE by review and both narrowings are kept visible:** its
   first version also dropped the warnings and asserted a refresh failure that had not happened
   (`A3-R1-04`), and its second version claimed `HTMLResponse` receives an "already-built ASCII str"
   as a reason to decline a second construction path -- **which round 2 DISPROVED** (`A3-R2-03`) by
   naming a legal custom `__repr__` returning a lone surrogate, measured to survive `html.escape`
   and then raise `UnicodeEncodeError` inside `HTMLResponse`. The response is not a second
   constructor path but `ascii_safe` in the production path plus test (k) end-to-end. **The
   remaining declared item is the duplication only.**
6. **The degraded response leaves the page STALE.** Open positions, status strip, watchlist and
   hyp-recs keep their pre-submit content. *Reason:* the refresh is exactly what failed; the notice
   says reload. An automatic client-side reload was rejected -- it would re-enter the broken render
   and could loop, and a loop over a money-bearing surface is worse than a stale page with an
   accurate banner.
7. **`log_contained_note` loses the sink failure only against an object that is not a
   `BaseException` at all.** *Reason -- and THIS ENTRY'S PREVIOUS REASON WAS DISPROVED BY REVIEW
   (`A3-R5-04`), which is why the declaration shrank rather than being defended:* the earlier
   version accepted information loss against a subclass overriding `__setattr__` to raise, claiming
   attachment was impossible. It is not. **MEASURED on this runtime:** for a class overriding BOTH
   `add_note` and `__setattr__` to raise, `BaseException.add_note` fails (it sets the attribute
   through the type) but **`BaseException.__setattr__(escaping, "__notes__", repaired)` SUCCEEDS** --
   the same base-slot bypass the helper already uses one line up. The repair branch now uses it.
   **THREE reachable cases are handled and measured** (an overriding `add_note`, a `__notes__` that
   is not a list, an overriding `__setattr__`); what remains is an object outside the type entirely,
   which cannot reach these call sites at all, and the outer guard exists because containment with
   one uncontained step is not containment.
8. **Nothing PERSISTS the fact that a degraded response was shown.** The ERROR log is the only
   durable trace. *Reason:* **NO schema** is in the envelope; a persisted degraded-response record
   is a table. If the orchestrator or CHARC wants it, it is a separate arc with a migration.
9. **When the CLI's OUTPUT SINK is itself unavailable, the operator gets no confirmation.** The
   output block is contained and the exit code stays 0. *Reason:* there is nowhere left to write --
   containing the failure does not lose information the operator could otherwise have had, and the
   exit code then becomes the ONLY remaining signal, which is exactly why it must be the TRUE one
   (the ledger has the row). The alternative -- exiting non-zero because the pipe closed -- reports
   a durable write as a failure over a broken `| head`.
10. **WHETHER THE ENTRY FORM DISAPPEARS IS NOT ASSERTED, AND THE UNCERTAINTY IS WIDER THAN THE
    DEGRADED PATH.** On the dashboard the route attributes removal to the watchlist/hyp-recs OOB
    rebuild (`trades.py:1987-1989`), not to the empty primary swap -- but **on `/watchlist` NONE of
    the four OOB targets exist, so the ordinary and warning paths rely on the empty primary swap
    there exactly as the degraded path does** (`A3-R2-07`; an earlier draft scoped this to the
    degraded path and proposed a degraded-only `<tr>` correction that would not have covered it).
    *Reason:* browser-only; TestClient cannot answer it. S6 Steps 2, 4 and 5 resolve it by
    observation. **A failure on the `/watchlist` ordinary path would be PRE-EXISTING** -- the
    pure-OOB response predates this arc -- and therefore out of envelope: reported, not fixed here.
11. **The four PRE-COMMIT logging calls in `_record_entry_inner` (`entry.py:824`, `:892`, `:903`,
    `:918`) are NOT contained.** *Reason:* they are a different semantic class. They run INSIDE the
    transaction, so a raising sink there aborts the write, the transaction rolls back, and **no
    durable row exists -- reporting a failure is then the HONEST answer.** The cost is availability
    (a broken sink prevents entries), not a wrong report. The brief scopes `entry.py` to the R11-03
    cleanup-twin containment; widening to every logging call in the file is a scope change this plan
    is not authorised to make. **The claim in S1.4 and the header is worded to match** -- "six
    CLEANUP handlers", never "every logging call" (`A3-R2-12`).
12. **The route guard catches `BaseException`,** so a `SystemExit`/`KeyboardInterrupt` during the
    refresh returns 200 instead of propagating. *Reason:* S2.5 -- `entry_post` is a sync endpoint in
    a threadpool worker where neither is signal-delivered, and where they ARE reachable the
    contract's direction governs. The CLI is DIFFERENT: there `KeyboardInterrupt` IS deliverable,
    which is why S2.2 contains the CLI close AND its output rather than treating them as symmetry.
13. **A THIRD unclosed boundary lives INSIDE `record_entry`, at `entry.py:516-519`**, where the
    degraded warning text is built with `{post_commit_error!r}`: a post-commit failure whose
    `__repr__` raises makes that formatting raise over a committed row, before any `EntryResult`
    exists to return (`A3-R3-03`, verified at source). *Reason for declaring rather than fixing:*
    the envelope opens `entry.py` for **log containment**, and that line is clause-1 warning-text
    construction, not a logging call -- its sibling at `:545` IS inside the log-failure handler and
    IS fixed (Task 4). **The one-token correction is `{safe_text(post_commit_error)}`** and it is
    flagged with that exact diff at S8 item 7. This plan does not make scope calls for the
    orchestrator; it makes them visible.
14. **THE OUTER POST-BIND GUARD'S EXCLUSIVE WINDOW IS NOT DETERMINISTICALLY TESTABLE.** Tests (b2)
    and (c2) cover the reachable, injectable part (a raising `close()`); what the outer `except`
    adds beyond that is coverage of an interval containing NO STATEMENTS -- an asynchronous
    exception between bytecodes. *Reason:* there is nothing to monkeypatch there. The guard is still
    correct and cheap, and the honest statement is that its added coverage is argued from the
    language's delivery semantics rather than demonstrated by a test. **Stated rather than left for
    a reviewer to notice that (b2)/(c2) do not reach it** (`A3-R3-01` made exactly that point).
15. **RESPONSE DELIVERY IS OUTSIDE THE GUARANTEE ENTIRELY.** The route's promise is about what it
    CONSTRUCTS and RETURNS. ASGI send, middleware streaming, transport errors and client
    disconnects all happen afterwards, and a failure there can leave the operator's browser with an
    error or with nothing, over a durable entry (`A3-R4-09`). *Reason:* it is not code-local, not in
    the envelope, and not solvable by a route. **It is also why S2.0's inventory says "three
    IDENTIFIED CODE-LOCAL boundaries" rather than "three boundaries"** -- an exhaustive claim about
    failure boundaries is a hand-enumerated roster and fails the same way.
16. **The static template walk (test h.2) is a declared heuristic.** It follows `{% include %}`
    edges and the literal string `/trades/entry/form`; an entry affordance added through a
    route-composed fragment, a computed URL, or a macro is invisible to it. *Reason:* the standing
    declare-versus-widen ruling. The LIVE half of (h) covers today's two surfaces by execution, and
    the walk asserts the `extends`-base PROPERTY rather than a membership count.

---

## S8. FLAGGED, NOT FIXED -- and where each goes

Per the brief's locks: a defect or gap outside scope is FLAGGED in the return report, never fixed
inline and never silently absorbed.

1. **The brief's R11-03 roster names five sites; there are six** (S1.4). The sixth is INSIDE the
   declared envelope, so this plan includes it and reports it. Independently confirmed by both
   review rounds. **Route: the return report, for the orchestrator to ratify or strike.**
2. **The brief's premise "`build_dashboard` + template renders inside the same `try`" is false**
   (S1.2) -- they sit after `finally: conn.close()`, outside every `try`. The conclusion holds; the
   mechanism does not. Independently confirmed by both review rounds. **Route: the return report.**
3. **`DuplicateOpenPositionError`'s message names the TICKER, not the trade** (S1.5), where the
   brief's test (e) says "naming the existing trade". The test asserts reality; the message is not
   changed. **Route: the return report.**
4. **`banner-info` is used by `partials/trade_entry_form.html.j2:26` but is not defined in
   `swing/web/static/app.css`** -- the Schwab auto-fill advisory renders unstyled. Pre-existing,
   cosmetic, outside the envelope. **Flagged only.**
5. **`#trade-close-soft-warn` lives ONLY in `dashboard.html.j2:34`** while the route that fills it
   (`trades.py:2849`) does not check for it -- the same silently-dropped-notice class this arc
   closes for entry, one surface over. **Not a live defect today**: the exit affordance is
   `partials/open_positions_row.html.j2:63`, reached only through `partials/open_positions.html.j2`,
   included by `dashboard.html.j2:40` and by `partials/prices_refresh_container.html.j2` -- and that
   container is the OOB payload of `POST /prices/refresh` (`swing/web/routes/pipeline.py:372`),
   whose three swap targets exist only on the dashboard. **Flagged as a LATENT instance.**
6. **`RequestIdMiddleware` can destroy a completed response** (S2.0, S7.3). `dispatch` at
   `swing/web/middleware/request_id.py:22-34` calls `_access_log.info(...)` after `call_next`
   returns and before it returns the response, and `app.py:657-660` makes it OUTERMOST. A raising
   `swing.web.access` handler therefore converts a correct 200 -- including this arc's
   degraded-success 200 -- into the refusal-shaped 500. **This is the SAME R11-03 class this arc
   fixes six times, at a SEVENTH site OUTSIDE the envelope.** Correction, for whoever owns it: wrap
   that `info(...)` in the same containment (the idiom will be available), and pin it with a test
   that enters a trade with a raising `swing.web.access` handler installed. **Route: the return
   report, for the orchestrator to commission or bank.**
7. **`entry.py:516-519` formats its degraded warning with `{post_commit_error!r}`, which can
   RAISE over a committed row** (S2.0 boundary three, S7.13; verified at source). A post-commit step
   failing with an exception whose `__repr__` raises makes the warning-text construction raise
   BEFORE the degraded `EntryResult` is built -- so `record_entry` reports a failure over a durable
   entry, which is precisely clause 1's subject, one line above the guard that implements it.
   **The correction is one token:**

   ```diff
   -            f"AFTER the commit failed ({post_commit_error!r}). The entry "
   +            f"AFTER the commit failed ({safe_text(post_commit_error)}). The entry "
   ```

   `safe_text` exists after Task 1, in the same module, so the change costs nothing beyond the
   authorisation. **NOT MADE HERE** because the envelope opens `entry.py` for LOG containment and
   this is clause-1 warning-text construction. **Route: the return report -- the orchestrator can
   authorise it into Task 4 in one line, or decline it and leave S7.13 standing.**

8. **TWO COHORT CLEANUP MESSAGES STATE A TRANSACTION CONDITION THEY DID NOT OBSERVE**
   (`A3-R5-13`, tagged out-of-envelope by the reviewer and verified here).
   `cohort_provenance_correction.py:2284-2291` says the transaction "is STILL OPEN" merely because
   `rollback()` raised, and `:3341-3348` says the same of the read transaction. **A rollback can
   TAKE EFFECT and then raise** -- which is exactly why `entry.py:743-758` and the cohort APPLY path
   at `:2692-2706` re-read `conn.in_transaction` and branch the message. These two sites were left
   out of that correction. **This arc makes their logging CONTAINED but does not make it TRUE**, and
   tests d2/d5 exercise only the still-open posture, so nothing here detects it.

   *Correction, for a separately authorised change:* re-read `conn.in_transaction` after the
   rollback failure and branch the message as the two corrected sites already do, with BOTH a
   still-open and a took-effect-then-raised test.

   **NOT MADE HERE:** the envelope opens `cohort_provenance_correction.py` for LOG CONTAINMENT, and
   rewriting what a message CLAIMS is a different change from making its emission harmless. **Route:
   the return report -- BANK it or authorise it in one line.** *(Note the shape: this is the same
   after-effect fallacy the plan itself had to fix in its own close-warning copy at `A3-R5-07`, one
   round earlier. The class is live in this codebase and worth a sweep of its own.)*

9. **The four PRE-COMMIT logging calls at `entry.py:824`/`:892`/`:903`/`:918` are uncontained**
   (S7.11). Not a durability defect -- no row exists yet when they run -- but a broken sink there
   PREVENTS entries. **Flagged as an availability item, not fixed:** containing them is a scope
   change and their correct behaviour today is to fail loudly.

---

## S9. SELF-REVIEW (run against the brief, before each Codex round)

**Spec coverage** -- every clause of the brief's "What 22-A3 ships", mapped to a task:

| brief clause | task |
|---|---|
| 1(a) the web route ASSIGNS the result | Task 6 (iii), `:1490` |
| 1(b) any post-entry render failure becomes DEGRADED SUCCESS naming the `trade_id`, never a 500, never an error-form re-render | Task 6 (iii)-(v); tests (b), (b2), (g), (g2), (k), (m); gate Step 5 |
| 1(c) `post_commit_warnings` surfaced in the response | Tasks 5 + 6; tests (a), (g), (h), (j); gate Steps 3-4 |
| 1 the HTMX gotchas bind; the operator browser check is binding | S2.1, S2.3, S6 |
| 2 the CLI consumes the field, ASCII, exit stays SUCCESS | Task 7; tests (c), (c2) |
| 3 R11-03 twin containment at the named sites, applied by READING | Tasks 1-4; tests (d1)-(d6); S1.4 |
| tests (a)-(e), each computed under both paths | S3, plus (b2), (c2), (c3), (c4), (f)-(n) |
| NO schema, NO change to `record_entry`'s transaction semantics | S2.8; no task touches a migration, `_entry_transaction`, or the declared residual |
| declared limitations WITH reasons | S7 (sixteen), every one carrying its reason; three of them had a reason DISPROVED by review and were narrowed rather than defended (S7.5, S7.7, S7.10) |

**Placeholder scan:** no `TBD`, no "add appropriate error handling", no "similar to Task N", no
"write tests for the above". Every code step carries its code; every test step carries its
assertions and both of its computed values. The `...unchanged...` markers in Tasks 6 and 7 refer to
EXISTING lines that must be preserved verbatim, and Task 6 makes that mechanically checkable with
`git diff -w`.

**Type consistency:** `ascii_safe(text: str) -> str`, `safe_text(value: object) -> str`,
`log_contained(logger, msg, *args) -> BaseException | None` and `log_contained_note(logger,
escaping, msg, *args) -> None` are defined in Task 1 and used with those exact signatures in Tasks
2, 3, 4, 6 and 7. `_post_commit_warnings(result, close_error) -> tuple[str, ...]` and
`_entry_notice_html(templates, request, *, trade_id: int, warnings: tuple[str, ...], render_failure:
str | None) -> str` are defined in Task 6 and used only there. `result` is `EntryResult | None`,
carried unannotated on purpose (Task 6 (iii)).

**Three consistency notes an executor must not get wrong:**

1. **At cohort site 3 the object passed to `log_contained_note` is `anomaly`, NOT
   `savepoint_error`. The escaping exception is the one the `raise` statement names.** Getting this
   wrong shows up as a failed identity assertion, which is why every (d) test asserts
   `excinfo.value is <the exact object>` and not merely its class.
2. **The chaining assertion is NOT uniform across the six** -- d1-d4 assert `__cause__`, d5 and d6
   assert `__cause__ is None`, and d6's failure posture additionally asserts `__context__`. The
   matrix in S3(d) is the contract; the shared assertion shape deliberately excludes chaining.
3. **The PRE-fix values are NOT uniform either, and this note has itself been corrected once.**
   (g)'s is a 200 with FOUR chunks, not a 500, because pre-fix the route never asks for the notice
   template. **(f) FAILS pre-fix** on the 4-vs-5 count and the missing notice -- only its
   four-existing-refresh-chunk sub-assertions pass, and an earlier draft of this very note said the
   whole test passed (`A3-R4-05`). (e) and (b2)'s refusal control DO pass pre-fix, by design and
   labelled as controls. An executor who assumes "pre-fix means 500" writes several wrong tests.

---

## S10. WHAT AN EXECUTOR MUST READ BEFORE TOUCHING ANYTHING

- `docs/phase22-arc-a3-a4-commissioning-brief.md` -- the 22-A3 half ONLY. **22-A4 is a different
  arc; do not build any part of it.**
- `docs/22-a-merge-request.md` S4.4 -- the ruling that produced this arc.
- `CLAUDE.md` -- the whole Gotchas section, and the **Web / HTMX / templates / forms** subsection
  twice.
- `swing/trades/entry.py:200-215` (the contract) and `:490-546` (the guard the route is extending).
- The declared residual at `swing/trades/entry.py:578-637` -- **read it so you do not accidentally
  fix it; that is 22-A4's.**
- This plan's **S7 before writing any test**, so a limitation is not re-litigated as a bug, and
  **S9's three consistency notes before writing any (d) test.**
