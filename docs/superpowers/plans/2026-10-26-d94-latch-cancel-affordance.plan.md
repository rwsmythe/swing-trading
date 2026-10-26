# D94 (a)+(b) -- the latch validity prompt gate + the ledger-keyed cancel affordance: PLAN

**Brief:** `docs/d94-latch-cancel-affordance-plan-dispatch-brief.md` (@ `8acea975`).
**Ledger (rulings, census, intake corrections, kept claims, interpretations, rounds):**
`docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.plan.ledger.md`.
The argument lives in the ledger; this file is the task ladder and the test roster.
**Worktree / branch / base:** `.worktrees/d94-cancel`, `d94-cancel`, `main` @ `8acea975`.
**Executing cell:** writing-plans default handoff; executing is `implementer-sonnet-high` unless the
orchestrator names a reason (none is named here: no schema, no measurement-chain code).

## 0. Envelope (binding)

IN:
- `swing/latches/classification.py` -- the factored fill predicate `fill_vouches_for` and the
  rung's delegation to it. NOTHING else in that file moves (orchestrator ruling; CHARC form 1A).
- `swing/web/view_models/latches.py` -- the one gate function, both call sites, the short-circuit
  fix, the explained lines, the ledger-keyed cancel controls, the RD wordings, the #31 comment
  rewrites named in Task 5.
- `swing/web/templates/partials/latch_orders.html.j2` -- the explained block, the comment rewrite.
- New tests: `tests/latches/test_fill_vouches_for.py`,
  `tests/web/test_routes/test_latches_d94_cancel_gate.py`.

OUT (a finding that needs any of these is a FORK: stop and return):
- any route change (`swing/web/routes/latches.py` is read, never edited);
- any schema / migration / new `validity_outcome` value / new `intent_kind`;
- anything under `swing/data/` or `swing/trades/`;
- `compute_execution_parity`, the authorization chain's reads (0037/0039), `swing/cli_latches.py`;
- (c) the broker-history tier; the lifecycle bucket (orchestrator ruling: it rides with (c));
- the IMNM-13 parent question (RD item 7: a flag, no write);
- the childless displaced-cycle FIRST-ANSWER form (orchestrator ruling; RD item 3): untouched;
- edits to existing test files (the new module imports their helpers).

## 1. The rule, in one table (RD items 1-6, CHARC 1A/2A; ledger section 1)

For ONE place intent `P` on latch `L`, with `C` = P's governing validity child (latest by
`_order_key`, or none), `B` = `resting_order_ids`, the set of order ids in this render's RESTING book
(`to_resting_orders(raw)`, `latches.py:2094`; terminal statuses are dropped before the domain sees them,
`orders.py:74-75`, so "absent" means "not resting" -- CHARC C-1):

| # | condition (evaluated in this order) | gate kind | renders |
|---|---|---|---|
| G1 | `fill_vouches_for(L, P, intents)` and `C` is None | `fill_settled_childless` | NOTHING (CADL; today's behaviour) |
| G2 | `fill_vouches_for(L, P, intents)` and `C` exists | `explained_fill` | the read-only fill line; NO correction, NO cancel control (OII; the shipped short-circuit defect fixed) |
| G3 | `C` is None, or `C.validity_outcome != 'accepted_by_broker'` | `none` | today's path, unchanged |
| G4 | `C` accepted and `C.actual_broker_order_id in B` | `none` | today's path, unchanged (the order is resting or indeterminate) |
| G5 | `C` accepted, its id not in `B`, and >=1 `cancel` row in L's intents names that id | `explained_cancel` | the read-only cancel line (EARLIEST cancel by `_order_key`, count disclosed); NO correction, NO cancel control |
| G6 | `C` accepted, its id not in `B`, no cancel row names it | `unexplained` | the correction control with RD's headline (absence branch) + ONE ledger-keyed cancel control for that id |

- `fill_vouches_for` is FALSE for every place that is not the latch's latest place (the forward
  guard), so G1/G2 never fire on a displaced cycle while a later place exists.
- The same function `_accepted_row_gate` evaluates G1-G6 at BOTH sites: the current-cycle path
  in `_validity_prompts` and `_displaced_cycle_prompts`. Never two copies (CHARC 2A).
- A displaced place with NO validity child is never passed to the gate (its first-answer form is
  untouched, orchestrator ruling); a childless CURRENT place reaches the gate only to test G1.
- An UNKNOWN book never reaches `_validity_prompts` (the early return at `latches.py:2160-2164`
  is unchanged), so no line and no control is built on it (CHARC; RD item 6).

## 2. RD's wordings (verbatim claims; substitutions in angle brackets)

W1 -- the correction headline on an UNEXPLAINED accepted row, ABSENCE branch (replaces the
"NO matching resting order ... rejected?" headline on that branch only; ledger section 5, I-3):

> Recorded: the broker ACCEPTED order <id> on <accepted session>. That order is not in the
> current book. Correct this ONLY if the broker never accepted it as recorded; an order that you
> later cancelled, or that filled or expired, was still accepted -- do not change the answer for
> that.

W2 -- the ledger-keyed cancel control's status note (rendered in `latch-cancel-status`):

> Order <id> (accepted <session>) is not in the current book. If YOU cancelled it, record the
> cancel here. Do not record a cancel for an order that filled or expired; leave it unanswered --
> the broker-history tier records those.

W3 -- the explained lines (the core is RD's; the identity prefix is ours, ledger I-5):

> <TICKER> place intent <pid>, order <oid>: accepted <C.action_session_date>; cancelled by you
> <cancel.action_session_date>, intent <cancel.intent_id>

> <TICKER> place intent <pid>, order <oid>: accepted <C.action_session_date>; filled
> <L.clear_session>

- `, order <oid>` is omitted when `C` carries no broker id (a non-accepted child under G2).
- Count disclosure, appended to the cancel line only when 2+ cancel rows name the order:
  ` (<n> cancel rows name this order; the earliest is the record)`.
- `<accepted session>` / `<session>` / `<C.action_session_date>` are ALL the validity row's
  `action_session_date`, which the route server-copies from the parent place
  (`routes/latches.py:1233-1237`).

## 3. Task ladder

Every task: RED test written and SEEN failing for the stated reason, minimal code, GREEN, commit.
Conventional commits carrying the task id; pathspec-only `git add`; final `-m` paragraph plain
prose; no `Co-Authored-By`, no `--no-verify`, no amend.

### Task 1 -- `refactor(latches): D94 Task 1 -- the fill rung as ONE named predicate`

FIRST commit, alone (CHARC 1A form). Behaviour of the rung is byte-identical;
`tests/latches/test_classification.py` passes UNCHANGED (no edit to it).

1. RED: create `tests/latches/test_fill_vouches_for.py` with T1.1-T1.7 (section 4). Run it; it
   fails on `ImportError: cannot import name 'fill_vouches_for'`.
2. In `swing/latches/classification.py`, after `governing_intent` / before
   `resolve_execution_outcome` (today `:490-531`), add:

   ```python
   def fill_vouches_for(latch, place_intent, intents, *, place_view=None) -> bool:
       """THE ONE SPELLING of "the framework's order filled" for a place intent.

       True iff ALL THREE hold: the latch cleared by FILL; the fill session is on or
       after this place's session (the BACKWARD guard -- an older fill from a prior
       cycle cannot vouch for a newer intent); and this place IS the latch's latest
       place in `place_view` (default: `intents`) -- the FORWARD guard, an earlier
       cycle cannot borrow a later fill.

       The resolver's fill rung and the latch panel's explanation gate both CALL
       this; neither re-spells it (CHARC D94 1A, RD D94 item 2).
       """
       if place_intent is None:
           return False
       latest = governing_intent(
           intents if place_view is None else place_view, "place")
       if latest is None or latest.intent_id != place_intent.intent_id:
           return False
       return (latch.clear_reason == "fill" and latch.clear_session is not None
               and latch.clear_session
               >= date.fromisoformat(place_intent.action_session_date))
   ```
3. Rewrite `resolve_execution_outcome_for` (today `:533-566`) to call the predicate, keeping its
   docstring's guard prose and adding one line naming the predicate:

   ```python
   if place_intent is None:
       return "not_applicable"
   if fill_vouches_for(latch, place_intent, intents, place_view=place_view):
       return "accepted_by_broker"
   validity_rows = [i for i in intents if i.intent_kind == "validity"]
   children = [r for r in validity_rows
               if r.validated_place_intent_id == place_intent.intent_id]
   if children:
       return max(children, key=_order_key).validity_outcome
   return "unknown"
   ```
4. Reduce `resolve_execution_outcome(latch, governing_place, validity_rows)` to a documented
   delegation, so the rung has exactly ONE spelling:

   ```python
   if governing_place is None:
       return "not_applicable"
   # Its contract is that `governing_place` IS the latest place, so the one-place
   # view states that contract rather than re-checking it.
   return resolve_execution_outcome_for(
       latch, governing_place, [governing_place, *validity_rows])
   ```
   Keep its docstring (the rung-2-above-rung-3 argument) and replace the sentence describing the
   inline conditions with "the fill rung is `fill_vouches_for`".
5. Equivalence argument (recorded in the commit body, checked by T1.6/T1.7): old `_for` with
   `place == latest` ran the inner rung (date test) then children then `unknown`; with
   `place != latest` it ran children then `unknown`. New `_for` runs (latest AND date test), then
   children, then `unknown`. Identical on every input; `latest is None` is False in both.
6. GREEN: `python -m pytest tests/latches -q` (whole package; `test_classification.py` unchanged)
   plus `tests/cli -q -k latches`. `ruff check swing/`. Commit (pathspec: the two files).

### Task 2 -- `fix(web): D94 Task 2 -- the accepted-row gate; a FILL with a validity child explains, it does not re-prompt`

1. RED: in `tests/web/test_routes/test_latches_d94_cancel_gate.py`, write T2.1 (OII shape) and
   T2.2 (CADL guard), T2.3 (routes through the predicate). Run; T2.1 FAILS on the shipped tree
   because the fragment renders `CORRECT THE RECORDED OUTCOME` for the fill-cleared latch
   (the short-circuit at `latches.py:3275-3280` skips only a CHILDLESS place). T2.2 passes on
   both trees (guard). T2.3 fails (no explained block exists).
2. In `swing/web/view_models/latches.py` add, near `_intents_by_latch`:

   ```python
   _GATE_NONE = "none"
   _GATE_FILL_CHILDLESS = "fill_settled_childless"
   _GATE_EXPLAINED_FILL = "explained_fill"
   _GATE_EXPLAINED_CANCEL = "explained_cancel"
   _GATE_UNEXPLAINED = "unexplained"

   @dataclass(frozen=True)
   class _AcceptedRowGate:
       kind: str
       place: object
       child: object | None = None
       cancel: object | None = None      # the EARLIEST cancel row naming the id
       cancel_count: int = 0

   def _accepted_row_gate(latch, *, place, intents, book_order_ids) -> _AcceptedRowGate:
       """THE ONE GATE (CHARC D94 2A), called from BOTH the current-cycle path and
       `_displaced_cycle_prompts`. Plan section 1 is its table; G1..G6 in order."""
       from swing.latches.classification import _order_key, fill_vouches_for
       children = [i for i in intents if i.intent_kind == "validity"
                   and i.validated_place_intent_id == place.intent_id]
       child = max(children, key=_order_key) if children else None
       if fill_vouches_for(latch, place, intents):
           return _AcceptedRowGate(
               _GATE_EXPLAINED_FILL if child is not None else _GATE_FILL_CHILDLESS,
               place, child)
       if child is None or child.validity_outcome != "accepted_by_broker":
           return _AcceptedRowGate(_GATE_NONE, place, child)
       oid = child.actual_broker_order_id
       if oid in book_order_ids:
           return _AcceptedRowGate(_GATE_NONE, place, child)
       cancels = sorted((i for i in intents if i.intent_kind == "cancel"
                         and i.actual_broker_order_id == oid), key=_order_key)
       if cancels:
           return _AcceptedRowGate(_GATE_EXPLAINED_CANCEL, place, child,
                                   cancels[0], len(cancels))
       return _AcceptedRowGate(_GATE_UNEXPLAINED, place, child)
   ```
   (G5/G6 land in this task's code but are first exercised by Task 3's RED tests; Task 2's tests
   cover G1/G2/G3. The function is written whole once, never in two copies.)
3. Add `_explained_line(latch, gate) -> str` producing W3 exactly (section 2).
4. Change `_validity_prompts` to return a frozen `_ValidityRender(prompts, degraded,
   explained, ledger_cancels)` (all tuples / str), and its ONE caller in
   `build_latch_orders_vm` to unpack it. In the A6 `except` there, all four fall back to empty
   and the degraded string is unchanged.
5. In the current-cycle path of `_validity_prompts` (today `:3248-3302`): compute
   `book_order_ids = {o.order_id for o in orders or ()}` once per call. After the framework
   check, inside the SAME `try` that wraps `resolve_execution_outcome_for` (A6: a raise appends
   the ticker to `degraded` and continues), compute `gate = _accepted_row_gate(...)`. Then:
   - `gate.kind == _GATE_FILL_CHILDLESS` -> `continue` (replaces the proxy at `:3275-3280`,
     which is DELETED; equivalent for every childless place, ledger K-4);
   - `gate.kind == _GATE_EXPLAINED_FILL` -> append `_explained_line(latch, gate)` and
     `continue` (`_GATE_EXPLAINED_CANCEL` is routed in Task 3, so T3.1 is RED on this tree);
   - otherwise today's path.
6. Rewrite the comment block at `:3261-3273` to what the code now does (#31): a fill explains
   the place; childless -> nothing, with a child -> the read-only line; no testimony control is
   offered on a fill-settled place. Rewrite bullet 2 of the `_validity_prompts` docstring
   (`:3162-3167`) the same way.
7. Add `validity_explained: tuple[str, ...] = ()` to `LatchOrdersFragmentVM` (after
   `validity_prompt_degraded`), with a comment: read-only lines, one per accepted row whose
   absence a fill or a recorded cancel explains; EMPTY on every early return.
8. Template: inside `{% else %}` (available), immediately BEFORE the `validity_prompt_degraded`
   paragraph, render:

   ```jinja
   {% if vm.validity_explained %}
   <div class="latch-validity-explained">
     <h4 class="latch-validity-heading">RECORDED ORDER OUTCOMES (read-only)</h4>
     {% for line in vm.validity_explained %}
     <p class="latch-validity-explained-line">{{ line }}</p>
     {% endfor %}
   </div>
   {% endif %}
   ```
   Root stays the `<section>`; no `<tr>`; ASCII only.
9. GREEN: the new module, `tests/web/test_routes/test_latches_validity_prompt.py`,
   `tests/web/test_routes/test_latches_orders_fragment.py`. `ruff check swing/`. Commit.

### Task 3 -- `fix(web): D94 Task 3 -- a recorded cancel explains an accepted row, on EVERY cycle; RD's correction headline`

1. RED: T3.1 (DFTX shape), T3.2 (IMNM shape: links 3+4 and the childless current place),
   T3.3 (W1 verbatim), T3.4 (earliest cancel + count), T3.5 (a resting order is not gated).
   T3.1-T3.4 fail on the Task-2 tree for the reasons in section 4; T3.5 passes (guard).
2. Current-cycle path: route `_GATE_EXPLAINED_CANCEL` exactly as Task 2 step 5 routes
   `_GATE_EXPLAINED_FILL` (append `_explained_line`, `continue`). For
   `_GATE_UNEXPLAINED`, pass `accepted_gone=gate` into `_validity_prompt_for`; on its ABSENCE
   branch, when `accepted_gone` is set, the headline is W1 (with
   `<id> = accepted_gone.child.actual_broker_order_id`,
   `<accepted session> = accepted_gone.child.action_session_date`). The PRESENCE branch ignores
   `accepted_gone` (ledger I-3). Options, envelope, `is_correction`, `superseded_outcome`
   unchanged (ledger IC-2: the three non-accepted values).
3. Displaced site: `_displaced_cycle_prompts` gains keyword params `book_order_ids`, `explained`
   (a list it appends to) and `ledger_cancels` (a list it appends to), and receives `latch` as
   today. Inside its loop, AFTER the existing `answered is None and current is None: continue`
   and ONLY when `answered is not None`, call `_accepted_row_gate(latch, place=place,
   intents=intents, book_order_ids=book_order_ids)`:
   - explained (cancel, or fill per section 1) -> append `_explained_line`, `continue`;
   - `_GATE_UNEXPLAINED` -> headline W1 instead of the "correctable DOWNWARD" headline, and
     append the gate to `ledger_cancels`;
   - otherwise today's displaced prompt, unchanged.
   The childless branch (`answered is None`) never calls the gate.
4. The A6 seam: `_displaced_cycle_prompts` is today called OUTSIDE the per-latch `try`
   (`:3244`). Wrap the call in the same `try/except Exception` -> `degraded.append(ticker)`;
   `continue` pattern, so a gate raise degrades one latch, never the fragment.
5. In the current-cycle path append `gate` to `ledger_cancels` on `_GATE_UNEXPLAINED` (both
   branches, presence and absence).
6. GREEN + the two existing latch test files. `ruff check swing/`. Commit.

### Task 4 -- `feat(web): D94 Task 4 -- the cancel affordance keyed on the LEDGER's order id`

1. RED: T4.1 (EMPTY-book anti-vacuity), T4.2 (UNKNOWN book: no control), T4.3 (round trip),
   T4.4 (resting: exactly one control), T4.5 (presence with a different order), T4.6 (HTMX
   contract of the new control), T4.7 (failed ledger read). T4.1, T4.3, T4.5, T4.6 fail on the
   Task-3 tree (no ledger-keyed control exists); T4.2, T4.4, T4.7 are guards (green on both).
2. `LatchCancelControlVM`: add `source: str = "book"` (`"book" | "ledger"`). Rewrite its
   docstring (#31): the subject is still a broker order he holds or held; it is offered for
   every BUY order in the resting book attributed to a latch (`source="book"`, the shipped
   three conditions) AND for every accepted validity row whose order is absent from the book and
   unexplained (`source="ledger"`, keyed on the ledger's `actual_broker_order_id`, never on the
   live book). LOG-ONLY on both.
3. In `build_latch_orders_vm`: MOVE the `_validity_prompts` call (today `:2642-2654`) ABOVE the
   cancel-control build (today `:2604-2617`); it already needs only `derivation`, `joins`,
   `orders`, the anchor and `intents_by_latch`, all available there. Then:

   ```python
   resting_order_ids = validity.resting_order_ids  # the gate's ONE set, exposed on _ValidityRender (CHARC C-2)
   seen: set[tuple[int, str]] = set()
   ledger_controls = []
   for gate in validity.ledger_cancels:
       cid = gate.place.candidate_id
       oid = gate.child.actual_broker_order_id
       if oid in resting_order_ids or (cid, oid) in seen or cid in intents_read_failed:
           continue
       seen.add((cid, oid))
       ledger_controls.append(LatchCancelControlVM(
           order_id=oid, ticker=gate.place.ticker, latch_candidate_id=cid,
           status_note=<W2 with <id>=oid, <session>=gate.child.action_session_date>,
           prior_intent_id=_prior_intent_id(intents_by_latch.get(cid, ())),
           source="ledger"))
   cancel_controls = book_controls + tuple(
       sorted(ledger_controls, key=lambda c: (c.ticker, c.order_id)))
   ```
   `book_controls` is the shipped `for row in attribution` comprehension, unchanged.
4. Rewrite the `cancel_controls` field comment on `LatchOrdersFragmentVM` (`:1898-1907`) and the
   VM comment block at `:2593-2603` to name both sources (#31). Template: the cancel-log comment
   (`latch_orders.html.j2:39-53`) gains one sentence naming the ledger source; the form markup is
   UNCHANGED (it already renders `control.status_note` before the form, and posts
   `intent_kind=cancel`, `candidate_id`, `view_session_date`, `actual_broker_order_id`,
   `prior_intent_id` with `hx-target="this" hx-swap="outerHTML"` and `hx-headers`).
5. GREEN + the two existing latch test files. `ruff check swing/`. Commit.

### Task 5 -- `docs(web): D94 Task 5 -- #31 sweep of the gate's comments`

1. Self-sweep by READ (not token grep alone) of every comment/docstring in the three swing files
   that describes the fill short-circuit, the cancel control's source, or the absence headline.
   The minimum roster, each re-read on the final tree: `latches.py` `LatchCancelControlVM`
   docstring; `LatchOrdersFragmentVM.cancel_controls` / `.validity_explained` comments;
   `build_latch_orders_vm` cancel comment; `_validity_prompts` docstring; the `:3261-3273` block;
   `_validity_prompt_for` absence comment (`:2985-2989`); `_displaced_cycle_prompts` docstring;
   `classification.py` `resolve_execution_outcome` / `_for` docstrings; the template cancel-log
   comment. Then a closure grep, reported with its counts: `rg -n "fill short-circuit|short-circuit|for row in attribution|resting book|three conditions" swing/web swing/latches`.
2. No comment may promise what a later arc (c) will do to this code (#31); naming (c) as the
   tier that would close AL-1 is a statement about the limitation, not about this code.
3. Commit only if text changed.

### Task 6 -- the gates (no commit unless a fix is needed)

1. Full fast suite on the final head: `python -m pytest -m "not slow" -q`; read the tail.
2. `ruff check swing/`.
3. LIVE census probe (read-only; plain sqlite3 `mode=ro`, never `swing`'s `connect`): run the
   census script (ledger section 2 names it) with `PYTHONPATH=.` from the worktree against an
   EMPTY book and the current anchor, through the new `_validity_prompts` and the cancel-control
   build. Expected, row by row (ledger section 2.3):
   - DFTX (place 5): explained line `... order 1007682901503: accepted 2026-08-24; cancelled by
     you 2026-09-02, intent 11`; no prompt for place 5; no control.
   - IMNM place 6: explained line `... order 1007793713337: accepted 2026-09-02; cancelled by you
     2026-09-02, intent 10`.
   - IMNM place 7: W1 correction (order 1007804578712) + ONE ledger control for
     `1007804578712` with W2.
   - IMNM place 12: the first-answer absence prompt, unchanged.
   - OII (place 1): explained line `... order 1007523377009: accepted 2026-08-10; filled
     2026-08-17`; no prompt, no control.
   - RHI (place 4): the first-answer absence prompt only. CADL: nothing.
   Any mismatch STOPS the arc and returns to the orchestrator.
4. Trailer audit: `git log 8acea975..HEAD --format='%H%n%(trailers)'` all empty.
5. The executing Codex loop (strong tier, repo access) per the recipe; Reviewer B is the
   orchestrator's.

## 4. Test roster (RED first; pre/post computed for each)

Shared fixture notes for `test_latches_d94_cancel_gate.py`:
- Imports `_seed`, `_app`, `_log_place`, `_rows`, `_form_fields`, `_form_html`, `_fragment`,
  `_radio_values`, `_order`, `clocks`, `PLACE_NOW`, `PROMPT_NOW`, `PLACE_ANCHOR`,
  `PROMPT_ANCHOR`, `_HX` from `tests.web.test_routes.test_latches_validity_prompt`
  (`seeded_db` is the shared `tests/web/conftest.py:345` fixture).
- `book`: a module-local mutable list; `_app(..., orders=book)` captures it (the lambda reads
  `list(orders)` at call time), so one app serves several book states. Order ids are strings
  `"5001"`, `"5002"` built with `_order(order_id=...)` (FTRE's attributable geometry).
- `_section_for_parent(html, pid)`: the `latch-validity-prompt` section whose
  `validated_place_intent_id` input equals `pid` (works on pre- and post-fix trees).
- `_clone_intent(cfg, intent_id, **over)`: raw-SQL copy of an intent row with overrides
  (`idempotency_key`, `recorded_ts`, `action_session_date`); generalises the validity file's
  `_clone_place` without editing it.
- `_accept(client, pid)`: renders the fragment, takes `_section_for_parent(html, pid)`, posts its
  `latch-validity-confirm` form; asserts 200.
- `_cancel_forms(html)`: every `latch-cancel-form` as a dict of its hidden inputs (generalises
  the fragment file's `_cancel_form_fields`, which takes only the first).
- `_fill_cleared(monkeypatch, cid, clear_session)`: wraps `vm_mod.build_latch_derivation` so the
  latch `cid` is returned with `state="filled", clear_reason="fill", clear_session=...,
  clear_trade_id=7, fill_link_basis="candidate_id"` (the exact override set
  `test_latches_validity_prompt.py:606-611` already uses), via `dataclasses.replace` on the
  `LatchDerivation` and the `Latch`. Installed AFTER the place and validity rows are written.

`tests/latches/test_fill_vouches_for.py` (Task 1):

| id | case | expected | pre-refactor |
|---|---|---|---|
| T1.1 | latest place, `clear_reason='fill'`, clear 07-28 >= place 07-27 | True | ImportError (RED) |
| T1.2 | same, clear ON the place session | True | RED |
| T1.3 | clear BEFORE the place session | False | RED |
| T1.4 | the place is NOT the latest place | False | RED |
| T1.5 | `clear_reason='invalidation'` / `None`; and `place_intent=None` | False | RED |
| T1.6 | `place_view` excludes a later out-of-bound place -> True (item 3a's case, `classification.py:541-547`) | True | RED |
| T1.7 | `resolve_execution_outcome(latch, p, rows) == resolve_execution_outcome_for(latch, p, [p, *rows])` over a 4-case grid (fill/none x child/none) | equal | RED (import) then GREEN |

`tests/web/test_routes/test_latches_d94_cancel_gate.py`:

| id | task | fixture | asserts | shipped tree | fixed tree |
|---|---|---|---|---|---|
| T2.1 OII shape | 2 | place P1; book=[5001]; `_accept(P1)`; book=[]; `_fill_cleared(cid, 2026-07-28)`; render at PROMPT_ANCHOR | no `CORRECT THE RECORDED OUTCOME`; no `latch-validity-prompt`; no `latch-cancel-form`; the line `FTRE place intent <P1>, order 5001: accepted 2026-07-27; filled 2026-07-28` | RED: renders the correction control (the `:3275-3280` proxy lets a child through) | GREEN |
| T2.2 CADL guard | 2 | place P1, NO validity; book=[]; `_fill_cleared` | no prompt, no explained block, no cancel form | GREEN (proxy skips childless) | GREEN |
| T2.3 one spelling | 2 | T2.1's fixture rendered TWICE: once as is, once with `swing.latches.classification.fill_vouches_for` monkeypatched to `lambda *a, **k: False` | first render: the explained fill line present; second render: the line is GONE and `CORRECT THE RECORDED OUTCOME` is back for P1 -- the VM's decision follows the predicate, it does not re-spell it (the W1 headline on that branch is T3.3's, not this test's) | RED (the first render has no explained line) | GREEN |
| T3.1 DFTX shape | 3 | P1; book=[5001]; accept; post the BOOK cancel control for 5001; book=[] | the line `FTRE place intent <P1>, order 5001: accepted 2026-07-27; cancelled by you 2026-07-29, intent <C1>`; no prompt for P1; no cancel form | RED (correction prompt, no line) | GREEN |
| T3.2 IMNM shape | 3 | P1, accept 5001 (book=[5001]), cancel 5001 via book control; book=[]; P2=`_clone_intent(P1, idempotency_key='p2', recorded_ts='2026-07-29T23:59:58')`; book=[5002]; `_accept(P2)`; book=[]; P3=`_clone_intent(P1, idempotency_key='p3', recorded_ts='2026-07-29T23:59:59')` | (i) P1: the cancel line, no section for parent P1; (ii) P2: a section for parent P2 whose headline is W1 for 5002 and which does NOT contain `correctable DOWNWARD`; (iii) exactly one `latch-cancel-form` with `actual_broker_order_id=5002`; (iv) P3: a section `DID THIS ORDER REACH THE BROKER?` (first answer) | RED on (i) (a 2B implementation also fails (i)) | GREEN |
| T3.3 W1 verbatim | 3 | P1, accept 5001, book=[] (current cycle, absence) | the P1 section contains W1 with `5001` / `2026-07-27` byte-for-byte; NOT `NO matching resting order`; `_radio_values == {'not_submitted','rejected_by_broker','unknown'}`; heading `CORRECT THE RECORDED OUTCOME` kept | RED (old headline) | GREEN |
| T3.4 earliest + count | 3 | T3.1's fixture, then `_clone_intent(C1, idempotency_key='c2', recorded_ts=<later>, action_session_date='2026-07-30')` | line cites `cancelled by you 2026-07-29, intent <C1>` and ends `(2 cancel rows name this order; the earliest is the record)`; `2026-07-30` absent from the line | RED | GREEN; a latest-wins implementation shows `2026-07-30, intent <C2>` and fails |
| T3.5 resting guard | 3 | P1, accept 5001, book stays [5001] | the shipped PRESENCE correction for P1 (confirm label `YES - the broker accepted order 5001`); no explained block | GREEN | GREEN |
| T4.1 EMPTY book (anti-vacuity) | 4 | P1, accept 5001, book=[] | premise `No resting BUY orders at the broker.` present (attribution is EMPTY); exactly one `latch-cancel-form`, `actual_broker_order_id == "5001"`, `intent_kind == "cancel"`; the `latch-cancel-status` paragraph equals W2 for 5001 / 2026-07-27 | RED (no control: built `for row in attribution`) | GREEN |
| T4.2 UNKNOWN book | 4 | T4.1's DB; `vm_mod._fetch_account_orders` raises `SchwabApiError(500, "x")` | `UNKNOWN` in text; no `latch-cancel-form`, no `latch-cancel-log`, no explained block, no `latch-validity-prompt` | GREEN | GREEN (kills a build outside `available`) |
| T4.3 round trip | 4 | T4.1, then post the ledger control's fields exactly as rendered; re-render | POST 200, `HX-Redirect` NOT in headers (the shipped markup-swap contract); exactly ONE new row `('cancel', '5001')`; re-render shows the T3.1-shaped cancel line, no `latch-cancel-form`, no P1 section | RED | GREEN |
| T4.4 resting, no duplicate | 4 | P1, accept 5001, book=[5001] | exactly ONE `latch-cancel-form` naming 5001; no W2 text; no `latch-cancel-status` | GREEN | GREEN (kills a union without the book check) |
| T4.5 presence, other order | 4 | P1, accept 5001; book=[5002] (attributable, different id) | the PRESENCE correction offering `YES - the broker accepted order 5002` is kept; TWO cancel forms: `5002` (book, no note) and `5001` (ledger, W2) | RED (no 5001 control) | GREEN |
| T4.6 HTMX contract | 4 | T4.1 | the 5001 ledger form carries `hx-post="/latches/intent"`, `hx-target="this"`, `hx-swap="outerHTML"`, `hx-headers='{"HX-Request": "true"}'`; `prior_intent_id` == the latch's latest intent id (non-empty); `view_session_date == PROMPT_ANCHOR`; fragment root not `<tr` | RED | GREEN |
| T4.7 failed ledger read | 4 | T4.1's DB; patch `swing.data.repos.latch_order_intents.list_intents_for_latch` to raise `sqlite3.OperationalError` | no `latch-cancel-form`; the shipped degraded text `THE VALIDITY QUESTION COULD NOT BE BUILT` present | GREEN | GREEN |

Unchanged-and-must-stay-green (named so a regression is read, not assumed):
`test_latches_validity_prompt.py` -- `test_a_FILL_CLEARED_latch_renders_no_prompt_and_derives_acceptance`
(:573), `test_a_DISPLACED_cycles_answer_stays_correctable_DOWNWARD` (:912; its order 1001 stays
RESTING, so the gate is G4), `test_a_CHILDLESS_displaced_cycle_gets_a_FIRST_ANSWER_form` (:968),
`test_an_ANSWERED_prompt_becomes_a_CORRECTION_control_and_the_LATEST_governs` (:519; outcome
`not_submitted`, G3); `test_latches_orders_fragment.py` -- every cancel-control test (:2437-2833);
`tests/latches/test_classification.py` whole (Task 1's byte-identity proof).

## 5. Merge gate: the operator browser witness (BINDING; step by step, one step per reply)

TestClient cannot see the HTMX swap. After merge-integration and the merged-head suite, with
`swing web` restarted on the merged code against the LIVE DB:
1. Open `/latches`; let the order fragment load. Report what the fragment shows for DFTX, IMNM,
   OII, RHI (expected: section 3 Task 6 step 3, verbatim lines).
2. Confirm IMNM shows ONE "Log that I cancelled order 1007804578712" button with W2 above it,
   and the W1 correction beside it; no button for OII, DFTX or IMNM ...337.
3. ONLY IF he did cancel IMNM order 1007804578712 (RD item 1: the one go-flat row still owed, and
   only if true): click it. Expected: the form swaps in place (no navigation, no 403), and
   reloading the panel replaces the button and the W1 correction with the IMNM place-7 cancel
   line. If he did not cancel it, he leaves it unanswered and the click is witnessed instead on a
   scratch copy of the DB (orchestrator stands up the copy; the operator's live ledger is not
   written for a witness).
4. Confirm IMNM place 12 and RHI still show their first-answer prompts, which he leaves
   UNANSWERED (RD item 7).

## 6. Return

The executing return carries the per-task SHAs, the final-head suite tail, the live census
probe output, the trailer audit, the executing Codex ledger and spend line.
