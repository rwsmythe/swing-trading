# 22-A -- the 146 case-binding SEMANTIC re-audit: findings

**Branch:** `22-a-audit`, worktree `.worktrees/22-a-audit`, branched off `22-a-exec` at `403ea9ff`.  
**Governing brief:** [`docs/22-a-case-binding-audit-brief.md`](22-a-case-binding-audit-brief.md).  
**Machine-readable companion:** [`docs/22-a-case-binding-audit.json`](22-a-case-binding-audit.json) -- the same 146 rows, keys exactly as the brief's field list.

**Citation shorthand:** `PLAN` below abbreviates `docs/superpowers/plans/2026-08-24-phase22-arc-a-entry-path-order-mandate-binding.md`. The JSON companion spells every path in full.

**This is a measurement, not a repair.** No code, test or migration was changed: `git diff 22-a-exec..22-a-audit --stat` is `docs/` only.

## Method

Every row was produced **spec first**. For each case I located the plan's text for it -- S3.1-S3.6 for the six binding cases, the S3.7 omission lens for the clause-level cases, S4.3 / S4.3a / S4.5-replace / S4.5-epoch / S2.4d.1 for the schema cases, and S5.1's reason view where it assigns a decline reason to a case -- wrote the `specified_outcome` sentence from that text, and only then opened the test bound to the case. The order is the whole method: the tests are internally coherent and their docstrings tell consistent stories, so reading the test first anchors the reader into ratifying it. That is how fifteen review rounds passed over case 4.

**`READ`** means I read the plan's specification and the bound test and compared them. **`EXECUTED`** means I additionally ran something and observed the result: for the 25 `48*`/`49*` rows and the 11 `35*`/`51*`/twin rows, the parametrized node ids were enumerated and observed to pass one-per-case-id; for case 36 and for the gate finding below, purpose-built read-only probes were run. 43 rows carry `EXECUTED`, 103 carry `READ`. **No verdict was inferred from a test's name, its docstring, or its neighbours** -- that inference is the defect under audit.

**What this audit can establish:** whether the assertions in the bound test measure the outcome the plan specifies for that case. **What it cannot:** whether the specification is right (out of scope by the brief), whether the production code is right (a faithful test can still be green against a defect the case does not reach), and whether a case's fixture leaves a free dimension the plan's own S3.8 audit would catch. Where a test is faithful but a sibling property is unpinned I said so in the row's note rather than moving the verdict.

**Context, so the counts are not read as a suite verdict:** all twenty `test_22a_*.py` modules are green on this tree -- 101 + 126 + 394 = 621 tests across the three runs used here, zero failures. A `WEAKER` or `CONTRADICTS` verdict is a statement about what the test MEASURES, never about whether it passes.

## Counts

| verdict | cases |
|---|---|
| **FAITHFUL** | 124 |
| **WEAKER** | 20 |
| **CONTRADICTS** | 1 |
| **ABSENT** | 0 |
| **UNVERIFIABLE** | 1 |
| **total** | 146 |

| binding shape | cases |
|---|---|
| bound by a test FUNCTION NAME only | 93 |
| bound by BOTH a function name and a `*_CASE_IDS` list | 11 |
| **bound ONLY by list membership** | **42** |

The brief's measurement is confirmed: **42 cases have no named function at all.** Of those 42, **35 are FAITHFUL** -- `48a`-`48p` (16), `49a`-`49i` (9), the five `35*` and the five `51*` -- and **7 are the relocated `-pre` twins, every one WEAKER** (16+9+5+5+7 = 42). All 42 carry `EXECUTED`.

---

## THE `CONTRADICTS` ROW, IN FULL

One case asserts an outcome its specification excludes. There are **no `ABSENT` rows**: every one of the 146 bound tests contains at least one assertion that relates to its case's subject matter.

#### `4` -- task 4 -- **CONTRADICTS** (READ, named_function)

- **spec:** PLAN:1910 (S3.4 heading + body); PLAN:2102 (lens 3b); PLAN:3167 (S5.1 reason view: no_accepted_latch_order | 2, 4)
- **specified outcome:** RHI's real shape -- a place intent present, NO validity row and therefore NO link -- FALLS THROUGH: the persisted row is byte-identical to the pre-fix row (pipeline_watch_manual / 12518 / the watch label) and the decline reason is no_accepted_latch_order.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_an_armed_latch_admits_through_the_whole_ladder_case_4`
- **asserted outcome:** A broker-ACCEPTED order is built via _accept(...) and the ladder ADMITS: verdict.admitted is True, the link id matches, the tier is live_at_acceptance and all sixteen authorization entries read 'pass'.
- **note:** The exemplar. Opposite outcome, opposite world: the spec's fixture has NO validity row and no link and must DECLINE; the test builds an accepted link and asserts ADMISSION. It also inverts the lens clause it cites: lens 3b names case 4 as the case that FAILS an implementation matching on 'the ticker has an armed latch' -- and RHI is precisely the shape such an implementation would wrongly admit. As written the test passes under BOTH the correct and the omitting implementation, so it discriminates nothing. The no_accepted_latch_order reason IS asserted for the RHI-like shape elsewhere -- tests/trades/test_22a_task8_resolver.py::...case_18 (tests/trades/test_22a_task8_resolver.py:181) and tests/trades/test_22a_task9_entry_wiring.py::...case_2 -- but neither is bound to case 4.

---

## THE `UNVERIFIABLE` ROW, IN FULL -- this one needs a ruling

#### `4c-i` -- task 6a -- **UNVERIFIABLE** (READ, named_function)

- **spec:** PLAN:1936 (S3.4c bullet 4c-i); PLAN:2098 (lens 1)
- **specified outcome:** Two accepted links on one ticker, only one live at the fill session. The envelope naming the LIVE one ADMITS; THE SAME FIXTURE WITH THE ENVELOPE NAMING THE DEAD ONE refuses mandate_not_alive -- 'an implementation ignoring the order id cannot produce both verdicts'.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_a_dead_rival_is_dropped_and_its_own_leg_refuses_case_4c_i`
- **asserted outcome:** Leg 1 (live envelope): the ladder ADMITS and the scanned competitor list is exactly the rival's link id. Leg 2: mandate_alive_at is called DIRECTLY on the rival's order and returns mandate_not_alive / superseded -- the LADDER is not run on the dead order, and the docstring states the ladder would return ambiguous_ticker_orders instead.
- **note:** THE PLAN DETERMINES TWO OUTCOMES FOR THE SECOND LEG AND THEY DISAGREE. S3.4c (PLAN:1936-1940): 'Then the same fixture with the envelope naming the DEAD one -> refuse mandate_not_alive. An implementation ignoring the order id cannot produce both verdicts.' S2.4 rung 8 (PLAN:1277) + S2.4b: 'exactly ONE competitor-free accepted link on this TICKER' -> ambiguous_ticker_orders, and rung 8 runs BEFORE the probe. From the dead order's seat the subject is a live competitor, so the ladder emits ambiguous_ticker_orders and the specified mandate_not_alive is unreachable at the specified grain. The implementer resolved it by asserting at the PROBE grain and declared the divergence in the docstring, which is honest -- but the resolution is a ruling nobody made. Routing question for the directors: does 4c-i's second leg move to the probe grain (ratify the test) or does the plan sentence stand and the case need a fixture where rung 8 does not pre-empt it?

---

## THE `WEAKER` SET, BY PATTERN

Twenty rows. They fall into five patterns, and the patterns differ enough that the fix leg should not treat them as one bucket.

### Pattern A -- the `-pre` twin whose fixture is not its base case's (9 rows)

`8-pre`, `10-pre`, `24-pre`, `27-pre`, `28a-pre`, `28b-pre`, `28c-pre`, `22-pre`, `23-pre`.

The S3 twin convention (PLAN:1800) is explicit: *"Each such case then carries a `-pre` twin running the identical fixture with the REAL boundary, asserting `pre_barrier_unproven`."* Seven of these nine share ONE parametrized body:

```python
@pytest.mark.parametrize("twin", RELOCATED_TWIN_CASE_IDS)
def test_every_relocated_twin_refuses_at_rung_nine(tmp_path, twin) -> None:
    conn, cfg, candidate_id = build_world(
        tmp_path, twin.replace("-", "_"), pre_barrier=True)
```

`build_world`'s second argument is a DIRECTORY NAME. `closes` defaults to `BASE_CLOSES`, nothing base-case-specific is seeded, and the seven runs therefore execute byte-identical code -- and are byte-identical to `test_a_pre_barrier_link_refuses_outright_case_22_pre` three functions above them. The docstring's discriminating claim is **false on disk**:

> WHAT MAKES THIS DISCRIMINATING rather than seven copies of one assertion: each twin's world is the one its base case proved ADMITS

The bases are task-6 probe cases with specific worlds -- case 8's empty judging window, case 10's armed lapse geometry, case 24's counting archive stub, case 27's reconfirmation fire, 28a/28b/28c's terminal dated on the fill session -- and none of those dimensions is present. `22-pre` omits case 22's ordinary same-candidate trade (so the docstring's *"rung 9 refuses BEFORE the ordinary-trade question is even asked"* is not exercised: there is no ordinary trade to ask about); `23-pre` builds one of case 23's three rivals.

**The counter-examples are in the same tree and show the shape:** `29d-pre` reproduces case 29d's late cancel, `4c-i-pre` reproduces 4c-i's dead rival, and `5b-pre` reproduces 5b's breach geometry AND pins `clear_reason is None` and `probe_evidence is None` so that refuse-at-rung-9 is distinguished from refuse-after-probing. That is what the convention asks for.

### Pattern B -- the twin that asserts the ROW but not the REASON (2 rows)

`1-pre` and `6-pre`. (`22-pre` shows this too, but it is counted once, under Pattern A. 9 + 2 + 4 + 2 + 3 = 20.)

These reproduce their base case's fixture correctly and then assert only the persisted row `('manual_off_pipeline', None, None)`. That row is identical under EVERY refusal reason, so an implementation that refused for drift, coverage or an unreadable ledger passes them. `pre_barrier_unproven` -- the reason the twin convention exists to pin, and the reason S5.1's view routes to every twin -- is never named. `1-pre` is the important one: under Option C the plan makes it **trade 25's live outcome**, not a twin, and S9's operator gate is written around it.

### Pattern C -- the case whose specified END-TO-END outcome is not reached (4 rows)

`4b`, `15e`, `5a`, `1`.

Each asserts a genuine sub-property and stops short of the outcome the plan states. `4b` asserts the lookup returns `[]` and never reaches the decline the spec requires (the resume record's finding, confirmed). `15e` asserts the envelope reader degrades to `None` across eleven shapes and never reaches `no_envelope`, the reason S5.1 assigns it -- and cannot, because the task-1 ladder cell ships no resolver, which makes this an OWNERSHIP question as much as a coverage one. `5a` asserts the persisted row and the discarded-label WARNING but not `mandate_not_alive` / `clear_reason='invalidation'` / the clear session, so any refusal reason passes it. `1` asserts the three cohort keys and the drift variant but none of S3.1's resolution assertions (the two intent ids, the broker order id, `clear_reason`, `bars_through`/`horizon_session`, the freeze tier, the snapshot equality).

### Pattern D -- the assertion that cannot fail (2 rows)

`33` and `36`. **These are the two I would promote out of `WEAKER` if the brief had a sixth verdict**, because a reader auditing coverage reads them green and they are structurally unable to go red.

- **`33`** computes the freeze-tier comparison with a `CASE WHEN ? > (SELECT max_candidate_id_at_barrier ...)` expression **written inside the test**. The only production input is the epoch boundary. A `>=` in the 0037 minting trigger or in `freeze_tier_for_candidate` -- exactly the defect inherited finding 22A-R9-02 raises -- leaves it green. The property is genuinely established by case 38 and case 25 against production, so nothing is uncovered; case 33's own binding just does not do it.
- **`36`** asserts `name in body` where `body` is the whole `sqlite_master.sql`, which begins `CREATE TRIGGER <name>`. The clause cannot fail for any trigger. Probed: all six `trg_candidates*` triggers carry their name in the RAISE message today as well, so the intended property currently holds -- but the test could not tell you if it stopped. The `22-A` and `reversibility header` clauses are real.

### Pattern E -- the fixture the spec names is not the fixture built (3 rows)

`47c`, `6`, `21b`. In all three the test's OWN docstring or comment describes the shape it does not construct, which is what makes them findable by this method and invisible to a code-first read.

- **`47c`** is specified as *"naming a different ticker"* (lens 62 and S5.1 both). The test drifts the `detection_date` instead, while its docstring explains the ticker shape: *"a link whose ticker matches the request but NOT the candidate passes rung 1 and is caught only here."* That shape is constructible and is not built.
- **`6`** builds the exact-equality boundary but not S3.6's display-precision variant, which review 22A-R15-13 added precisely because the earlier one-operand variant did not discriminate. Measured by grep over all twenty arc modules: no test contains the `41.424` / `41.4199` pair. Lens rows 7 and 30 both point at that variant and at nothing else.
- **`21b`** asserts the write reservation is held, and its spy carries the comment *"and NOW the link arrives"* -- followed by a bare delegation to the real lookup. No link is ever planted; the world is built without `accept_and_link`. Case `37b` in the route module does exactly this correctly (it inserts the link from a second connection inside the spy), so the pattern to copy is one file over.

---

## The 34 exclusions

Each was checked against the plan text its reason cites. **No exclusion reason is factually wrong**; all 34 stand. Three observations:

1. **`15d-i-pre` / `30b-pre` / `30d-pre` are excluded on a reasoned ground that CONTRADICTS an explicit plan sentence, and the registry is right.** The plan's twin roster (PLAN:1848-1850) lists `15d-i`, `30b` and `30d` among the seventeen admitting cases and says *"`30d-pre` NEW with case 30d itself"*. The registry exempts all three because they are pure-function cases on `assert_fill_consistent_with_order` that never reach rung 9 -- which is the convention's OWN stated scope two paragraphs above the roster (*"resolver cases admitted through ordinary `latch_ladder` authority"*). Verified on disk: the task-1 tests call the pure function directly with a hand-built `AcceptedLatchOrder` and no connection. The exclusion is sound; it is recorded here because it OVERRIDES a plan sentence and a reader comparing the two documents will trip on it.
2. **`35g`'s exclusion reason describes it differently from one of the two plan sites.** The registry says *"CHARC's retirement case"*, matching PLAN:3975 (*"the retirement-window pair 35g/35h"*); PLAN:3056 calls `35f`/`35g` *"the spurious lower re-arm"*. The EXCLUSION GROUND (era behaviour, travels to 22-A2) is identical either way, so nothing is hidden -- this is a stale description inside the plan, not a wrong exclusion.
3. `28d`, `32f`/`32g`, `40a`-`40f`, `46a`-`46c`, `35d`-`35m`, `45a`-`45d`, `8b`/`8c`, `53b`, `1-tier2` and `54` each check out against the carve, strike or deletion the plan records at the cited site.

## The 4 aliases

All four expand to members that are live in `PLAN_CASES` and audited here:

| alias | members | both members audited |
|---|---|---|
| `4c` | `4c-i`, `4c-ii` | yes (UNVERIFIABLE, FAITHFUL) |
| `4d` | `4d(i)`, `4d(ii)` | yes (FAITHFUL, FAITHFUL) |
| `5` | `5a`, `5b` | yes (WEAKER, FAITHFUL) |
| `15d` | `15d-i`, `15d-ii` | yes (FAITHFUL, FAITHFUL) |

---

## The gate itself

Four findings about `implemented_case_ids()` (`tests/trades/test_22a_case_closure.py:172`), in descending order of consequence.

### G1. SIX of the nine `*_CASE_IDS` lists are DEAD LITERALS, and for TEN cases a dead literal is the ONLY binding

`COVERAGE_CASE_IDS`, `ROUNDING_CASE_IDS`, `TIE_BASIS_CASE_IDS`, `SERVICE_LIMIT_CASE_IDS`, `THE_51_CASE_IDS` and `THE_35_CASE_IDS` are assigned once and **never referenced again anywhere in `tests/`** (method: `grep -rn <NAME> tests/ --include=*.py`, all nine names, results in the audit trail). Only `OMISSION_CASE_IDS`, `FIDELITY_CASE_IDS` and `RELOCATED_TWIN_CASE_IDS` are consumed by the `parametrize` beside them.

For the first four the redundancy is harmless -- `34a`-`34g`, `39a`-`39c` and `49j` also have named functions. **For `35a`/`35b`/`35c`/`35n`/`35p` and `51a`-`51e` the dead literal is the ONLY binding**, and nothing ties it to the test that implements those cases. **Verified by execution:** an AST walk over `test_22a_task2_migration_0037.py` with `test_the_epoch_refuses_every_write_path` AND `test_the_conflict_scoped_insert_barrier` **deleted from the parsed module** still reports all ten as implemented -- `10 of 10`. Delete both tests and the closure gate stays green.

This is the same class the arc is already treating: a declaration standing in for the thing it declares. The cheapest repair is to make the parametrize CONSUME the list (as the two live sites do), so the binding is a reference rather than an assertion about one.

### G2. The walk is not restricted to module level, so a THIRD binding path exists

The docstring says *"a module-level literal list/tuple"*, but the code is `for node in ast.walk(tree)` with no scope test. An `Assign` to a name ending `_CASE_IDS` **inside a function body or a class body** binds its members just as well, and a nested `def test_..._case_X` inside another function binds too. Nothing in the arc exploits this today; it is a live hole in an instrument whose whole job is to be un-gameable.

### G3. Nothing checks that a case is bound in the module of its OWNING TASK

`_arc_test_files()` globs `tests/**/test_22a_*.py` and any match can bind any case. A task-11 module could satisfy a task-4 case. **Measured: zero cross-owner bindings exist today** (method: for each of the 146, the binding site's module name was parsed for its task id and compared with `PLAN_CASES` -- 0 mismatches). So this is an available hole, not a live one.

### G4. The count can be wrong in the other direction, and it is -- by design

`test_no_phantom_cases_in_the_arc_test_modules` closes the phantom direction and passes (0 phantoms). But **implemented-and-not-counted is real and deliberate**: the arc carries a substantial body of tests explicitly marked `NO CASE ID` in their docstrings -- rung 9's barrier-dropped test, rung 8's scanned-population contract, the five envelope-guard fidelity mutations (whose docstring says *"the family is covered here without inventing plan case ids for it"*), the three-reachable-tie-reasons acceptance baseline, RD's `test_a_recognised_and_refused_entry_is_written_not_refused`. Two of the gaps this audit reports (`1`'s `bars_through`, `15e`'s `no_envelope`) are in fact ASSERTED by tests bound to a different case or to none. **The 146 number understates what is tested and overstates what is bound.** Any restatement of it should say which of the two it means.

### What the gate would have to do to catch this class

Nothing in `implemented_case_ids()` can see an assertion, and no widening of it will -- the same reason the registry's own docstring gives for abandoning a parsed-prose closure instrument. The available mechanical step is narrower and worth stating: **make each binding a REFERENCE the interpreter would break on** (G1), **scope the walk to module level** (G2), and **require the binding module to be the owning task's** (G3). Fidelity itself stays a human read -- which is what this document is.

---

## The honest bound on this instrument (brief section 4.4)

**I am one reader applying judgment 146 times, and a fatigue-driven `FAITHFUL` is exactly the failure mode that produced the thing I am auditing.** Where my confidence differs, it differs like this:

- **Highest confidence: the 42 list-only bindings and the 11 `both` rows.** They were audited FIRST, per the brief's ordering, while the method was freshest, and all 42 are `EXECUTED`. For 25 of them (`48a`-`48p`, `49a`-`49i`) the per-member specification comes from a roster in CODE (`AUTHORIZATION_CLAUSES`) rather than from prose, and for the ten `35*`/`51*` rows it comes from two verification TABLES in the plan, so the spec-side reading is close to mechanical for 35 of the 42.
- **High confidence: task 6 (24 rows, all FAITHFUL) and task 6a.** The S3.7 lens gives each of these cases a one-line required outcome naming a reason, and the tests assert reasons by name. The comparison is nearly mechanical, which is why the block is uniform -- but a uniform block is also where a tired reader would coast, so treat task 6 as the first place to sample me.
- **Lower confidence: tasks 9 and 1, where the spec is a multi-bullet paragraph rather than a lens row.** S3.1's case 1 has eight required assertions and S3.5's case 5a states its result *"in FULL"*; deciding how much of a multi-part outcome must be asserted before a row stops being FAITHFUL is a judgment I made consistently but could have made one notch either way. If you disagree with my line, `1`, `5a`, `6` and `1-pre` are the rows it moves.
- **A named limit: I graded fidelity to the SPEC, not sufficiency of the FIXTURE.** The plan's own S3.8 free-dimension audit asks a different question -- which dimensions a synthetic leaves free -- and I did not run it. A test can assert exactly the specified outcome over a fixture that would pass under a defect, and I would have called it FAITHFUL. Case 22's docstring records one such correction the arc found by measurement; I did not look for others.
- **A named limit: `EXECUTED` never means I mutated production code to see the test go red.** I ran no counterfactual against `swing/`, because the brief forbids changing it. So for every row, 'this test would fail against the omitting implementation' is REASONED from the assertion, not demonstrated -- except where the test itself asserts the pre-fix value, which many of them do and which I credited.
- **A named limit: single-pass.** I did not re-audit my own FAITHFUL rows after the WEAKER patterns emerged. If the fix leg finds that Pattern C (the specified end-to-end outcome not reached) is more common than four rows, the most likely place I missed it is the block of task-6 rows where the lens sentence and the assertion agree on the REASON and I did not separately check the SESSION or the evidence fields.

**No case was left unaudited.** All 146 carry a verdict, a citation and a method; there is no NOT-YET-AUDITED list.

---

## Index of all 146

| case | task | shape | verdict | method |
|---|---|---|---|---|
| `15a` | 1 | named_function | FAITHFUL | READ |
| `15b` | 1 | named_function | FAITHFUL | READ |
| `15c` | 1 | named_function | FAITHFUL | READ |
| `15d-i` | 1 | named_function | FAITHFUL | READ |
| `15d-ii` | 1 | named_function | FAITHFUL | READ |
| `15e` | 1 | named_function | WEAKER | READ |
| `30a` | 1 | named_function | FAITHFUL | READ |
| `30b` | 1 | named_function | FAITHFUL | READ |
| `30c` | 1 | named_function | FAITHFUL | READ |
| `30d` | 1 | named_function | FAITHFUL | READ |
| `26` | 2 | named_function | FAITHFUL | READ |
| `33` | 2 | named_function | WEAKER | READ |
| `35a` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `35b` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `35c` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `35n` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `35p` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `36` | 2 | named_function | WEAKER | EXECUTED |
| `43` | 2 | named_function | FAITHFUL | READ |
| `44` | 2 | named_function | FAITHFUL | READ |
| `51a` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `51b` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `51c` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `51d` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `51e` | 2 | case_ids_list | FAITHFUL | EXECUTED |
| `25` | 3 | named_function | FAITHFUL | READ |
| `38` | 3 | named_function | FAITHFUL | READ |
| `50a` | 3 | named_function | FAITHFUL | READ |
| `50b` | 3 | named_function | FAITHFUL | READ |
| `50c` | 3 | named_function | FAITHFUL | READ |
| `50d` | 3 | named_function | FAITHFUL | READ |
| `50e` | 3 | named_function | FAITHFUL | READ |
| `4` | 4 | named_function | CONTRADICTS | READ |
| `4b` | 4 | named_function | WEAKER | READ |
| `4d(i)` | 4 | named_function | FAITHFUL | READ |
| `4d(ii)` | 4 | named_function | FAITHFUL | READ |
| `8-pre` | 4 | case_ids_list | WEAKER | EXECUTED |
| `10-pre` | 4 | case_ids_list | WEAKER | EXECUTED |
| `13` | 4 | named_function | FAITHFUL | READ |
| `14` | 4 | named_function | FAITHFUL | READ |
| `22` | 4 | named_function | FAITHFUL | READ |
| `22-pre` | 4 | named_function | WEAKER | READ |
| `22b` | 4 | named_function | FAITHFUL | READ |
| `24-pre` | 4 | case_ids_list | WEAKER | EXECUTED |
| `27-pre` | 4 | case_ids_list | WEAKER | EXECUTED |
| `28a-pre` | 4 | case_ids_list | WEAKER | EXECUTED |
| `28b-pre` | 4 | case_ids_list | WEAKER | EXECUTED |
| `28c-pre` | 4 | case_ids_list | WEAKER | EXECUTED |
| `29a` | 4 | named_function | FAITHFUL | READ |
| `29b` | 4 | named_function | FAITHFUL | READ |
| `29c` | 4 | named_function | FAITHFUL | READ |
| `29d` | 4 | named_function | FAITHFUL | READ |
| `29d-pre` | 4 | named_function | FAITHFUL | READ |
| `41a` | 4 | named_function | FAITHFUL | READ |
| `47a` | 4 | named_function | FAITHFUL | READ |
| `47b` | 4 | named_function | FAITHFUL | READ |
| `47c` | 4 | named_function | WEAKER | READ |
| `7` | 6 | named_function | FAITHFUL | READ |
| `7b` | 6 | named_function | FAITHFUL | READ |
| `8` | 6 | named_function | FAITHFUL | READ |
| `9` | 6 | named_function | FAITHFUL | READ |
| `9b` | 6 | named_function | FAITHFUL | READ |
| `10` | 6 | named_function | FAITHFUL | READ |
| `11` | 6 | named_function | FAITHFUL | READ |
| `11b` | 6 | named_function | FAITHFUL | READ |
| `11c` | 6 | named_function | FAITHFUL | READ |
| `16` | 6 | named_function | FAITHFUL | READ |
| `19` | 6 | named_function | FAITHFUL | READ |
| `20` | 6 | named_function | FAITHFUL | READ |
| `24` | 6 | named_function | FAITHFUL | READ |
| `27` | 6 | named_function | FAITHFUL | READ |
| `28a` | 6 | named_function | FAITHFUL | READ |
| `28b` | 6 | named_function | FAITHFUL | READ |
| `28c` | 6 | named_function | FAITHFUL | READ |
| `28d'` | 6 | named_function | FAITHFUL | READ |
| `28e` | 6 | named_function | FAITHFUL | READ |
| `28f` | 6 | named_function | FAITHFUL | READ |
| `41b` | 6 | named_function | FAITHFUL | READ |
| `41c` | 6 | named_function | FAITHFUL | READ |
| `41d` | 6 | named_function | FAITHFUL | READ |
| `41e` | 6 | named_function | FAITHFUL | READ |
| `4c-i` | 6a | named_function | UNVERIFIABLE | READ |
| `4c-i-pre` | 6a | named_function | FAITHFUL | READ |
| `4c-ii` | 6a | named_function | FAITHFUL | READ |
| `15f` | 6a | named_function | FAITHFUL | READ |
| `23` | 6a | named_function | FAITHFUL | READ |
| `23-pre` | 6a | named_function | WEAKER | READ |
| `23b` | 6a | named_function | FAITHFUL | READ |
| `23c` | 6a | named_function | FAITHFUL | READ |
| `23d` | 6a | named_function | FAITHFUL | READ |
| `5c` | 8 | named_function | FAITHFUL | READ |
| `18` | 8 | named_function | FAITHFUL | READ |
| `1` | 9 | named_function | WEAKER | READ |
| `1-pre` | 9 | named_function | WEAKER | READ |
| `2` | 9 | named_function | FAITHFUL | READ |
| `3` | 9 | named_function | FAITHFUL | READ |
| `5a` | 9 | named_function | WEAKER | READ |
| `5b` | 9 | named_function | FAITHFUL | READ |
| `5b-pre` | 9 | named_function | FAITHFUL | READ |
| `6` | 9 | named_function | WEAKER | READ |
| `6-pre` | 9 | named_function | WEAKER | READ |
| `12` | 9 | named_function | FAITHFUL | READ |
| `21` | 9 | named_function | FAITHFUL | READ |
| `21b` | 9 | named_function | WEAKER | READ |
| `37c` | 9 | named_function | FAITHFUL | READ |
| `37` | 10 | named_function | FAITHFUL | READ |
| `37b` | 10 | named_function | FAITHFUL | READ |
| `17` | 11 | named_function | FAITHFUL | READ |
| `31` | 11 | named_function | FAITHFUL | READ |
| `34a` | 11 | both | FAITHFUL | READ |
| `34b` | 11 | both | FAITHFUL | READ |
| `34c` | 11 | both | FAITHFUL | READ |
| `34d` | 11 | both | FAITHFUL | READ |
| `34e` | 11 | both | FAITHFUL | READ |
| `34f` | 11 | both | FAITHFUL | READ |
| `34g` | 11 | both | FAITHFUL | READ |
| `39a` | 11 | both | FAITHFUL | READ |
| `39b` | 11 | both | FAITHFUL | READ |
| `39c` | 11 | both | FAITHFUL | READ |
| `48a` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48b` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48c` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48d` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48e` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48f` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48g` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48h` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48i` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48j` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48k` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48l` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48m` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48n` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48o` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `48p` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49a` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49b` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49c` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49d` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49e` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49f` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49g` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49h` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49i` | 11 | case_ids_list | FAITHFUL | EXECUTED |
| `49j` | 11 | both | FAITHFUL | READ |
| `22c` | 11a | named_function | FAITHFUL | READ |

---

## The complete table

One block per case, in task order. Fields are the brief's section 4.1 list; the JSON companion carries the same ten keys for mechanical re-derivation.

### Task 1

#### `15a` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2120 (lens 17); PLAN:3166 (S5.1 reason view)
- **specified outcome:** An untrusted fill_origin on an otherwise-good fill refuses with untrusted_fill_origin.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_untrusted_fill_origin_refuses_case_15a`
- **asserted outcome:** operator_typed returns 'untrusted_fill_origin'; both trusted origins return None.

#### `15b` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2120 (lens 17); PLAN:3179 (S5.1 reason view)
- **specified outcome:** A fill priced outside the frozen zone refuses with fill_outside_frozen_zone.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_out_of_zone_price_refuses_case_15b`
- **asserted outcome:** price 52.00, below the frozen pivot, returns 'fill_outside_frozen_zone'; 53.98 returns None.

#### `15c` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2120 (lens 17); PLAN:3178 (S5.1 reason view)
- **specified outcome:** A ticker mismatch between the request and the order refuses with ticker_mismatch.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_ticker_mismatch_refuses_case_15c`
- **asserted outcome:** ticker='AMN' against an OII order returns 'ticker_mismatch'.
- **note:** A second shape (envelope-symbol mismatch) is covered by an adjacent test carrying no case id.

#### `15d-i` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2148 (lens 52); PLAN:1540
- **specified outcome:** A partial fill (shares=1 against actual_quantity=2) ADMITS; an equality implementation fails it.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_partial_fill_admits_case_15d_i`
- **asserted outcome:** shares=1 returns None (admit).

#### `15d-ii` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2148 (lens 52); PLAN:3170 (S5.1 reason view)
- **specified outcome:** An over-quantity fill (shares=3 against 2) refuses quantity_exceeds_order.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_over_quantity_refuses_case_15d_ii`
- **asserted outcome:** shares=3 and shares=0 both return 'quantity_exceeds_order'.

#### `15e` -- task 1 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:2120 (lens 17); PLAN:3165 (S5.1 reason view: no_envelope | 15e)
- **specified outcome:** A malformed or absent envelope declines with the reason no_envelope.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_malformed_or_absent_envelope_yields_no_order_id_case_15e`
- **asserted outcome:** Eleven unusable envelope shapes each make broker_order_id_from_envelope return None without raising; no decline reason is reached.
- **note:** The READER half only. S5.1's reason view assigns no_envelope to 15e and no assertion in the bound test reaches a decline reason. The reason IS asserted end-to-end, but inside CASE 18's test (tests/trades/test_22a_task8_resolver.py:167), which the gate binds to case 18. The task-1 ladder cell ships only the reader and the four shape guards, so the full outcome is not assertable at the owning task -- the registry's own ownership rule points at task 8.

#### `30a` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2162 (lens 35); PLAN:3179 (S5.1 reason view)
- **specified outcome:** A cap with a non-zero third decimal, filled at the round-UP cent, REFUSES; a round(zone_cap,2) implementation admits.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_round_up_cent_is_refused_case_30a`
- **asserted outcome:** pivot 16.90 (cap 17.407) with price 17.41 returns 'fill_outside_frozen_zone'; a premise test pins 17.41 > cap.

#### `30b` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2163 (lens 35b)
- **specified outcome:** ...and the FLOORED cent (17.40) is still inside the zone: ADMIT.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_floored_cent_is_admitted_case_30b`
- **asserted outcome:** price 17.40 returns None.

#### `30c` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2164 (lens 35c)
- **specified outcome:** A broker actual_limit_price below the framework cap with the fill priced between them: REFUSE plus a divergence WARNING.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_broker_limit_below_the_framework_cap_refuses_case_30c`
- **asserted outcome:** limit 17.20 with price 17.30 returns 'fill_outside_frozen_zone' and logs 'diverges from the framework cap'; 17.10 admits.

#### `30d` -- task 1 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1849 (twin roster); PLAN:4160 (R9-04); PLAN:4181 (S13.3(3))
- **specified outcome:** A NULL actual_limit_price is treated as 'no broker bound' rather than coerced to 0.0 or raising -- kept as a DEFENSIVE-HANDLING test with its schema-impossibility stated, plus a companion pinning the CHECK.
- **test:** `tests/trades/test_22a_task1_envelope_guards.py::test_null_broker_limit_admits_on_the_framework_bound_case_30d`
- **asserted outcome:** NULL limit admits at 17.40 and refuses at 17.41; a companion test asserts the 0033 CHECK that makes the shape impossible.

### Task 2

#### `26` -- task 2 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2133 (lens 29)
- **specified outcome:** A delete-and-reinsert of the same (id, evaluation_run_id, ticker) must ABORT AT THE DELETE.
- **test:** `tests/data/test_22a_task2_migration_0037.py::test_delete_and_reinsert_of_the_same_identity_aborts_at_the_delete_case_26`
- **asserted outcome:** The DELETE raises IntegrityError naming trg_candidates_no_delete; pivot/initial_stop are unchanged; the default pragma is asserted.

#### `33` -- task 2 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:3355 (S6, limitation-pinning); PLAN:4162 (R9-02)
- **specified outcome:** The low-id tier is CONSERVATIVE, not exact, and the BOUNDARY ROW ITSELF is pre-barrier (the comparison is strictly greater than).
- **test:** `tests/data/test_22a_task2_migration_0037.py::test_the_low_id_tier_is_conservative_not_exact_case_33`
- **asserted outcome:** Two SELECTs of a CASE expression WRITTEN INSIDE THE TEST return pre_barrier at the boundary and live above it.
- **note:** VACUOUS with respect to production. The comparison under test is a CASE expression the test itself authors; the only production input is max_candidate_id_at_barrier. A '>=' in the 0037 minting trigger or in freeze_tier_for_candidate leaves this row green. The property IS established elsewhere -- case 38 (both spellings at below/equal/above) and case 25 (the trigger's own mint) -- so the repair is to point 33 at the production reader, not to add coverage.

#### `35a` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2171 (lens 40); PLAN:2829 (S4.5-epoch)
- **specified outcome:** An UPDATE on candidates_immutability_epoch ABORTS, at the DEFAULT recursive_triggers pragma.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_35_CASE_IDS@344 -> tests/data/test_22a_task2_migration_0037.py::test_the_epoch_refuses_every_write_path[35a-UPDATE candidates_immutability_epoch SET max_candidate_id_at_barrier = 0]`
- **asserted outcome:** The UPDATE raises IntegrityError; the epoch row is byte-unchanged; the pragma default is asserted rather than set.

#### `35b` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2171 (lens 40); PLAN:2829 (S4.5-epoch)
- **specified outcome:** A DELETE on the epoch table ABORTS at the default pragma.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_35_CASE_IDS@344 -> tests/data/test_22a_task2_migration_0037.py::test_the_epoch_refuses_every_write_path[35b-DELETE FROM candidates_immutability_epoch]`
- **asserted outcome:** The DELETE raises; the row survives.

#### `35c` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2171 (lens 40); PLAN:2829 (S4.5-epoch)
- **specified outcome:** An INSERT OR REPLACE on the epoch table ABORTS -- half of the discriminator a two-trigger implementation fails.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_35_CASE_IDS@344 -> tests/data/test_22a_task2_migration_0037.py::test_the_epoch_refuses_every_write_path[35c-INSERT OR REPLACE INTO candidates_immutability_epoch VALUES (1, 0, 'x')]`
- **asserted outcome:** The statement raises; the row survives.

#### `35n` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2171 (lens 40); PLAN:2829 (S4.5-epoch)
- **specified outcome:** A plain second-row INSERT with epoch_id=2 ABORTS.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_35_CASE_IDS@344 -> tests/data/test_22a_task2_migration_0037.py::test_the_epoch_refuses_every_write_path[35n-INSERT INTO candidates_immutability_epoch VALUES (2, 0, 'x')]`
- **asserted outcome:** The statement raises; the row survives.

#### `35p` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2171 (lens 40); PLAN:2829 (S4.5-epoch)
- **specified outcome:** Bare REPLACE and INSERT OR IGNORE each ABORT -- the other half of the two-trigger discriminator.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_35_CASE_IDS@344 -> tests/data/test_22a_task2_migration_0037.py::test_the_epoch_refuses_every_write_path[35p-replace-...] and [35p-ignore-...]`
- **asserted outcome:** Both statements raise; the row survives; both run at the asserted default pragma.
- **note:** The only 35* member whose parametrize id is not the plan id -- it is split into two runs, both present and both passing.

#### `36` -- task 2 -- **WEAKER** (EXECUTED, named_function)

- **spec:** PLAN:2172 (lens 41)
- **specified outcome:** Every barrier abort MESSAGE contains its own trigger NAME, the string 22-A, and 'reversibility header' -- asserted as CONTENT, never as bytes.
- **test:** `tests/data/test_22a_task2_migration_0037.py::test_every_barrier_message_is_legible_case_36`
- **asserted outcome:** For each guarded trigger: name in body, '22-A' in body, 'reversibility header' in body -- where body is the WHOLE sqlite_master.sql.
- **note:** Two of the three clauses are real; the trigger-NAME clause is unfalsifiable. body is the full CREATE TRIGGER statement, which begins 'CREATE TRIGGER <name>', so `assert name in body` cannot fail for any trigger. Measured by probe over the six trg_candidates* triggers: every header contains the name AND every RAISE message also contains it today, so the intended property currently holds -- but an edit removing the name from the message leaves this row green. Fix: assert against the text after 'BEGIN'.

#### `43` -- task 2 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2153 (lens 61)
- **specified outcome:** For EVERY column the pre-0037 append-only trigger protected, a barred write must still fail post-migration, computed against the OLD guarantee.
- **test:** `tests/data/test_22a_task2_migration_0037.py::test_the_old_append_only_guarantee_survives_the_replacement_case_43`
- **asserted outcome:** The old roster is PARSED out of 0036 (>=25 columns) and a REAL UPDATE per column raises IntegrityError matching 'APPEND-ONLY'.
- **note:** Two columns are silently excluded from the loop -- entry_fill_id and risk_policy_id_at_correction (tests/data/test_22a_task2_migration_0037.py:604) -- with no stated reason. They are FK columns whose sentinel write would raise a FOREIGN KEY error rather than APPEND-ONLY, so the exclusion is plausibly test mechanics; but 'EVERY column' is then two short and the exclusion is undeclared. Not graded down because the roster DERIVATION -- the discriminating half -- is intact.

#### `44` -- task 2 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2154 (lens 61b)
- **specified outcome:** The migration file carries NO statement between a DROP and its CREATE, and the explicit BEGIN/COMMIT wraps both.
- **test:** `tests/data/test_22a_task2_migration_0037.py::test_no_statement_sits_between_a_drop_and_its_create_case_44`
- **asserted outcome:** On the comment-stripped text, the span between DROP and CREATE is empty for both named triggers and each pair sits inside the one BEGIN;/COMMIT;.

#### `51a` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2764 (S4.5-replace verification table, row 1)
- **specified outcome:** An ordinary INSERT on a NEW run with the SAME ticker must SUCCEED (the nightly's own shape), at the default pragma.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_51_CASE_IDS@272 -> tests/data/test_22a_task2_migration_0037.py::test_the_conflict_scoped_insert_barrier[51a-ordinary INSERT, new run, same ticker-False]`
- **asserted outcome:** The INSERT into run 999 for FTRE does not raise.

#### `51b` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2764 (S4.5-replace verification table, row 2)
- **specified outcome:** An ordinary INSERT of a NEW ticker on the SAME run must SUCCEED.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_51_CASE_IDS@272 -> tests/data/test_22a_task2_migration_0037.py::test_the_conflict_scoped_insert_barrier[51b-ordinary INSERT, new ticker, same run-False]`
- **asserted outcome:** The INSERT of ZZZZ into run 121 does not raise.

#### `51c` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2764 (S4.5-replace verification table, row 3)
- **specified outcome:** INSERT OR REPLACE conflicting on UNIQUE(evaluation_run_id, ticker) must ABORT.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_51_CASE_IDS@272 -> tests/data/test_22a_task2_migration_0037.py::test_the_conflict_scoped_insert_barrier[51c-INSERT OR REPLACE on the UNIQUE-True]`
- **asserted outcome:** Raises IntegrityError naming trg_candidates_no_replace; the pivot AND the candidate_criteria child row both survive.

#### `51d` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2764 (S4.5-replace verification table, row 4)
- **specified outcome:** Bare REPLACE conflicting on the rowid PK must ABORT.
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_51_CASE_IDS@272 -> tests/data/test_22a_task2_migration_0037.py::test_the_conflict_scoped_insert_barrier[51d-bare REPLACE on the rowid PK-True]`
- **asserted outcome:** Same assertions as 51c, on the PK-conflict path.

#### `51e` -- task 2 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2764 (S4.5-replace verification table, row 5)
- **specified outcome:** INSERT OR IGNORE on a duplicate must ABORT (a declared behaviour change, S8-L18).
- **test:** `tests/data/test_22a_task2_migration_0037.py:THE_51_CASE_IDS@272 -> tests/data/test_22a_task2_migration_0037.py::test_the_conflict_scoped_insert_barrier[51e-INSERT OR IGNORE on a duplicate-True]`
- **asserted outcome:** Same assertions as 51c, on the IGNORE path.

### Task 3

#### `25` -- task 3 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2132 (lens 28); PLAN:2144 (lens 67)
- **specified outcome:** A pre-0037 candidate accepted AFTER the migration mints pre_barrier_reconstructed, never live_at_acceptance.
- **test:** `tests/data/test_22a_task3_epoch_reader.py::test_a_pre_migration_fire_accepted_after_0037_mints_pre_barrier_case_25`
- **asserted outcome:** A fire seeded on v36, migrated to 37, then accepted: the TRIGGER-minted link carries pre_barrier_reconstructed and the reader agrees.

#### `38` -- task 3 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2177 (lens 45); PLAN:4162 (R9-02 fix direction)
- **specified outcome:** The SQL twin and the Python reader agree over single-state fixtures AND each asserts the EXPECTED TIER at below / equal / above.
- **test:** `tests/data/test_22a_task3_epoch_reader.py::test_the_sql_twin_and_the_python_reader_agree_at_below_equal_above_case_38`
- **asserted outcome:** boundary-1 and boundary read pre_barrier, boundary+1 reads live, for BOTH spellings.

#### `50a` -- task 3 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1400 (S2.4d.1 case table); PLAN:2146 (lens 69)
- **specified outcome:** Both barrier triggers canonical plus a post-barrier fire: ADMIT.
- **test:** `tests/data/test_22a_task3_epoch_reader.py::test_a_post_barrier_fire_reads_live_with_the_barrier_intact_case_50a`
- **asserted outcome:** freeze_tier_for_candidate returns (live_at_acceptance, True) for boundary+1.
- **note:** Asserted at the READER's (tier, barrier_installed) grain, which is where the registry's own R9_09 re-verification places 50a-50e; rung 9's ADMIT/REFUSE consequence is exercised by a no-case-id test in the task-4 module.

#### `50b` -- task 3 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1401 (S2.4d.1 case table); PLAN:2146 (lens 69)
- **specified outcome:** trg_candidates_no_update DROPPED: REFUSE barrier_not_installed EVEN FOR a post-barrier fire.
- **test:** `tests/data/test_22a_task3_epoch_reader.py::test_a_dropped_update_barrier_refuses_even_a_post_barrier_fire_case_50b`
- **asserted outcome:** After the DROP the tier is still live_at_acceptance and installed is False.

#### `50c` -- task 3 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1402 (S2.4d.1 case table); PLAN:2146 (lens 69)
- **specified outcome:** Both barrier triggers dropped: the same refusal.
- **test:** `tests/data/test_22a_task3_epoch_reader.py::test_both_barriers_dropped_refuses_case_50c`
- **asserted outcome:** barrier_installed(conn) is False.

#### `50d` -- task 3 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1403 (S2.4d.1 case table -- CHARC's ruled discriminator)
- **specified outcome:** A same-name NO-OP trigger re-created on the same table must REFUSE barrier_not_installed; a name-only implementation counts two and ADMITS.
- **test:** `tests/data/test_22a_task3_epoch_reader.py::test_a_same_name_no_op_trigger_does_not_satisfy_the_check_case_50d`
- **asserted outcome:** The name count is 2, candidates is demonstrably mutable (an UPDATE succeeds and is read back), and barrier_installed is False.

#### `50e` -- task 3 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1404 (S2.4d.1 case table -- the normalization bound)
- **specified outcome:** A same-name same-body trigger on a DIFFERENT table REFUSES; a body differing ONLY by whitespace ADMITS.
- **test:** `tests/data/test_22a_task3_epoch_reader.py::test_the_normalization_bound_holds_in_both_directions_case_50e`
- **asserted outcome:** Wrong-tbl_name variant: barrier_installed False. Whitespace variant: bytewise different, normalized equal, barrier_installed True.

### Task 4

#### `4` -- task 4 -- **CONTRADICTS** (READ, named_function)

- **spec:** PLAN:1910 (S3.4 heading + body); PLAN:2102 (lens 3b); PLAN:3167 (S5.1 reason view: no_accepted_latch_order | 2, 4)
- **specified outcome:** RHI's real shape -- a place intent present, NO validity row and therefore NO link -- FALLS THROUGH: the persisted row is byte-identical to the pre-fix row (pipeline_watch_manual / 12518 / the watch label) and the decline reason is no_accepted_latch_order.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_an_armed_latch_admits_through_the_whole_ladder_case_4`
- **asserted outcome:** A broker-ACCEPTED order is built via _accept(...) and the ladder ADMITS: verdict.admitted is True, the link id matches, the tier is live_at_acceptance and all sixteen authorization entries read 'pass'.
- **note:** The exemplar. Opposite outcome, opposite world: the spec's fixture has NO validity row and no link and must DECLINE; the test builds an accepted link and asserts ADMISSION. It also inverts the lens clause it cites: lens 3b names case 4 as the case that FAILS an implementation matching on 'the ticker has an armed latch' -- and RHI is precisely the shape such an implementation would wrongly admit. As written the test passes under BOTH the correct and the omitting implementation, so it discriminates nothing. The no_accepted_latch_order reason IS asserted for the RHI-like shape elsewhere -- tests/trades/test_22a_task8_resolver.py::...case_18 (tests/trades/test_22a_task8_resolver.py:181) and tests/trades/test_22a_task9_entry_wiring.py::...case_2 -- but neither is bound to case 4.

#### `4b` -- task 4 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:1936 (S3.4b); PLAN:2101 (lens 3)
- **specified outcome:** A NULL-candidate, in-zone, matching-quantity entry with NO validity row must DECLINE; it fails an implementation reusing the shipped windowed price heuristic.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_an_in_zone_fill_with_no_accepted_order_finds_nothing_case_4b`
- **asserted outcome:** find_accepted_latch_order(...) returns [] -- the lookup finds nothing. No resolver or authorizer call is made and no decline is asserted.
- **note:** Confirms the resume record's finding. The empty lookup is a necessary precondition for the specified decline, not the decline. The test's own docstring says so ('returning an EMPTY list is the whole assertion'). Cheapest fix: add a resolve_latched_provenance call on the same fixture asserting decline_reason == 'no_accepted_latch_order' and recognised_but_underivable is False.

#### `4d(i)` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1948 (S3.4d shape (i)); PLAN:2099 (lens 2); PLAN:3169 (S5.1 reason view)
- **specified outcome:** A rejected_by_broker validity row with a link planted by raw INSERT declines linked_validity_not_accepted, BY NAME.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_link_citing_a_rejected_validity_row_refuses_case_4d_i`
- **asserted outcome:** A forged link citing a genuinely rejected validity row returns decline_reason == 'linked_validity_not_accepted'.

#### `4d(ii)` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1948 (S3.4d shape (ii)); PLAN:2100 (lens 2b); PLAN:3172 (S5.1 reason view)
- **specified outcome:** An accepted_by_broker row later SUPERSEDED by a rejected child of the same place intent declines validity_superseded.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_superseded_validity_child_refuses_case_4d_ii`
- **asserted outcome:** A later validity child (recorded 15:00 the same session) makes the accepted one stale: decline_reason == 'validity_superseded'.

#### `8-pre` -- task 4 -- **WEAKER** (EXECUTED, case_ids_list)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2110 (lens 10, base case 8); PLAN:2170 (lens 39)
- **specified outcome:** CASE 8's IDENTICAL fixture -- a fill on the ANCHOR session with an EMPTY judging window -- run with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py:RELOCATED_TWIN_CASE_IDS@739 -> tests/trades/test_22a_task4_authorization_ladder.py::test_every_relocated_twin_refuses_at_rung_nine[8-pre]`
- **asserted outcome:** A DEFAULT pre-barrier world (BASE_CLOSES, FILL_SESSION, no case-8 seeding) refuses pre_barrier_unproven with the pre-barrier tier.
- **note:** Seven twins, one body, one world. build_world(tmp_path, twin.replace('-','_'), pre_barrier=True) uses the parametrized id ONLY as a directory name; closes defaults to BASE_CLOSES and no base-case seeding is performed, so all seven runs execute byte-identical code and are byte-identical to test_a_pre_barrier_link_refuses_outright_case_22_pre. The docstring's discriminating claim -- 'each twin's world is the one its base case proved ADMITS' -- is FALSE on disk. Case 8's own dimension (empty window / zero bars, fill on the anchor) is absent.

#### `10-pre` -- task 4 -- **WEAKER** (EXECUTED, case_ids_list)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2113 (lens 12, base case 10); PLAN:2170 (lens 39)
- **specified outcome:** CASE 10's IDENTICAL fixture -- criteria_lapse_armed=True over a lapse-qualifying latch -- run with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py:RELOCATED_TWIN_CASE_IDS@739 -> tests/trades/test_22a_task4_authorization_ladder.py::test_every_relocated_twin_refuses_at_rung_nine[10-pre]`
- **asserted outcome:** The same default pre-barrier world as every other twin.
- **note:** Same body as 8-pre; case 10's dimension (the armed lapse config and the lapse geometry) is absent.

#### `13` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2118 (lens 15); PLAN:1428 (S2.4a); PLAN:3180 (S5.1 reason view)
- **specified outcome:** One trade per mandate: another trade that has consumed THIS ORDER refuses mandate_already_consumed.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_second_trade_on_the_same_order_is_already_consumed_case_13`
- **asserted outcome:** Another trade whose entry fill envelope carries THIS broker order id returns 'mandate_already_consumed'.
- **note:** Lens 15's wording ('a second trade citing the same fire') is stale against S2.4a's order-linked definition, and lens 25 / case 22 explicitly forbid the fire-based reading. The test follows S2.4a, which is the governing text.

#### `14` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2119 (lens 16); PLAN:3168 (S5.1 reason view)
- **specified outcome:** Cardinality is by COUNT, not fetchone(): two links sharing one broker order id refuse ambiguous_accepted_orders.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_two_links_on_one_order_id_are_ambiguous_case_14`
- **asserted outcome:** The lookup returns two links AND the resolver refuses ambiguous_accepted_orders, recognised_but_underivable True, all three cohort keys None.

#### `22` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2129 (lens 25)
- **specified outcome:** An ordinary trade carrying the fire's candidate_id but NOT this broker order must NOT block admission; a COUNT(*) implementation falsely refuses.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_an_ordinary_trade_on_the_fire_does_not_block_admission_case_22`
- **asserted outcome:** With an envelope-less same-candidate trade dated after the fill, verdict.admitted is True.
- **note:** The docstring corrects the plan's S3.8 free-dimension claim by measurement (the other trade's session is PINNED after the fill, or the probe's own fill rung fires first).

#### `22-pre` -- task 4 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2170 (lens 39); PLAN:3187 (S5.1 reason view)
- **specified outcome:** CASE 22's IDENTICAL fixture with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_pre_barrier_link_refuses_outright_case_22_pre`
- **asserted outcome:** A bare pre-barrier world (no ordinary trade seeded) refuses pre_barrier_unproven with recognised_but_underivable True.
- **note:** Case 22's distinguishing seeding -- the ordinary same-candidate trade -- is absent, so the docstring's claim that rung 9 'refuses BEFORE the ordinary-trade question is even asked' is not exercised: there is no ordinary trade in the fixture. Same class as the seven relocated twins; milder, because the reason and the recognition flag are both pinned.

#### `22b` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2165 (lens 36); PLAN:3181 (S5.1 reason view)
- **specified outcome:** A prior trade whose entry fill went through split-into-partials (envelope stripped) refuses consumption_evidence_unavailable, never a silent admit.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_stripped_envelope_makes_consumption_unprovable_case_22b`
- **asserted outcome:** A prior trade with reconciliation_status='reconciled_discrepancy_resolved' and a NULL envelope returns 'consumption_evidence_unavailable'.

#### `24-pre` -- task 4 -- **WEAKER** (EXECUTED, case_ids_list)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2131 (lens 27, base case 24); PLAN:2170 (lens 39)
- **specified outcome:** CASE 24's IDENTICAL fixture -- coverage from the derivation's own bars, with a second read that would differ -- run with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py:RELOCATED_TWIN_CASE_IDS@739 -> tests/trades/test_22a_task4_authorization_ladder.py::test_every_relocated_twin_refuses_at_rung_nine[24-pre]`
- **asserted outcome:** The same default pre-barrier world as every other twin.
- **note:** Same body as 8-pre; case 24's dimension (the counting archive stub whose second read differs) is absent.

#### `27-pre` -- task 4 -- **WEAKER** (EXECUTED, case_ids_list)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2158 (lens 32, base case 27); PLAN:2170 (lens 39)
- **specified outcome:** CASE 27's IDENTICAL fixture -- an accepted order on a same-pivot RECONFIRMATION fire -- run with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py:RELOCATED_TWIN_CASE_IDS@739 -> tests/trades/test_22a_task4_authorization_ladder.py::test_every_relocated_twin_refuses_at_rung_nine[27-pre]`
- **asserted outcome:** The same default pre-barrier world as every other twin.
- **note:** Same body as 8-pre; case 27's dimension (the reconfirmation fire and candidate_set membership) is absent.

#### `28a-pre` -- task 4 -- **WEAKER** (EXECUTED, case_ids_list)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2135 (lens 31, base case 28a); PLAN:2170 (lens 39)
- **specified outcome:** CASE 28a's IDENTICAL fixture -- a horizon expiry dated exactly ON the fill session -- run with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py:RELOCATED_TWIN_CASE_IDS@739 -> tests/trades/test_22a_task4_authorization_ladder.py::test_every_relocated_twin_refuses_at_rung_nine[28a-pre]`
- **asserted outcome:** The same default pre-barrier world as every other twin.
- **note:** Same body as 8-pre; case 28a's dimension (horizon_sessions=5 so the expiry lands on the fill session) is absent.

#### `28b-pre` -- task 4 -- **WEAKER** (EXECUTED, case_ids_list)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2135 (lens 31, base case 28b); PLAN:2170 (lens 39)
- **specified outcome:** CASE 28b's IDENTICAL fixture -- a decline dated ON the fill session -- run with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py:RELOCATED_TWIN_CASE_IDS@739 -> tests/trades/test_22a_task4_authorization_ladder.py::test_every_relocated_twin_refuses_at_rung_nine[28b-pre]`
- **asserted outcome:** The same default pre-barrier world as every other twin.
- **note:** Same body as 8-pre; case 28b's dimension (the recorded decline on the fill session) is absent.

#### `28c-pre` -- task 4 -- **WEAKER** (EXECUTED, case_ids_list)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2135 (lens 31, base case 28c); PLAN:2170 (lens 39)
- **specified outcome:** CASE 28c's IDENTICAL fixture -- a supersession dated ON the fill session -- run with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py:RELOCATED_TWIN_CASE_IDS@739 -> tests/trades/test_22a_task4_authorization_ladder.py::test_every_relocated_twin_refuses_at_rung_nine[28c-pre]`
- **asserted outcome:** The same default pre-barrier world as every other twin.
- **note:** Same body as 8-pre; case 28c's dimension (the re-fire dated on the fill session) is absent.

#### `29a` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2159 (lens 33); PLAN:3173 (S5.1 reason view)
- **specified outcome:** An accepted old cycle plus a newer place with no validity refuses place_cycle_superseded.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_newer_place_cycle_retires_the_accepted_order_case_29a`
- **asserted outcome:** A later place intent on the same candidate returns 'place_cycle_superseded'.

#### `29b` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2160 (lens 34); PLAN:3175 (S5.1 reason view)
- **specified outcome:** A cancel recorded strictly BEFORE the fill refuses order_cancelled.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_cancel_before_the_fill_refuses_case_29b`
- **asserted outcome:** A cancel recorded on the accept session returns 'order_cancelled'.

#### `29c` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2160 (lens 34); PLAN:3176 (S5.1 reason view)
- **specified outcome:** A cancel recorded ON the fill session refuses with its OWN reason, cancel_ordering_ambiguous.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_cancel_on_the_fill_session_is_unorderable_case_29c`
- **asserted outcome:** A cancel recorded at 09:00 on the fill session returns 'cancel_ordering_ambiguous'.

#### `29d` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2161 (lens 34b)
- **specified outcome:** A cancel recorded AFTER the fill is not consulted: ADMIT. It fails an implementation refusing on any cancel at all.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_cancel_after_the_fill_is_not_consulted_case_29d`
- **asserted outcome:** A cancel recorded 2026-07-28 (after the 07-27 fill) leaves verdict.admitted True.

#### `29d-pre` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2170 (lens 39)
- **specified outcome:** CASE 29d's IDENTICAL fixture with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_pre_barrier_link_refuses_despite_a_late_cancel_case_29d_pre`
- **asserted outcome:** The pre-barrier world PLUS 29d's own late cancel returns 'pre_barrier_unproven'.
- **note:** The model twin in the task-4 module: the base case's own seeding is reproduced and only the boundary varies.

#### `41a` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2137 (lens 46); PLAN:3174 (S5.1 reason view)
- **specified outcome:** A raw link whose place_intent_id names a row that is not a place, OR names a place on a DIFFERENT candidate, refuses link_parent_incoherent.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_link_whose_parent_is_not_a_place_row_is_incoherent_case_41a`
- **asserted outcome:** BOTH shapes are built and each returns 'link_parent_incoherent'.

#### `47a` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2141 (lens 62); PLAN:3189 (S5.1 reason view)
- **specified outcome:** A raw link citing a GENUINE accepted validity row while SUBSTITUTING the broker order id refuses link_field_unbound.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_substituted_broker_order_id_is_unbound_case_47a`
- **asserted outcome:** A forged link carrying broker_order_id='9999999999' returns 'link_field_unbound'.

#### `47b` -- task 4 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2141 (lens 62); PLAN:3189 (S5.1 reason view)
- **specified outcome:** The same clause on an INFLATED quantity: link_field_unbound.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_an_inflated_quantity_is_unbound_case_47b`
- **asserted outcome:** A forged link carrying actual_quantity=999 returns 'link_field_unbound'.

#### `47c` -- task 4 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:2141 (lens 62); PLAN:3189 (S5.1 reason view: '...naming a different ticker')
- **specified outcome:** A raw link NAMING A DIFFERENT TICKER from the candidate's own refuses link_field_unbound.
- **test:** `tests/trades/test_22a_task4_authorization_ladder.py::test_a_mismatched_ticker_copy_is_unbound_case_47c`
- **asserted outcome:** A forged link carrying a drifted detection_date ('2026-07-21') returns 'link_field_unbound'. No ticker is mutated anywhere in the test.
- **note:** The clause is exercised on a SIBLING field, not the specified one. The test's own docstring describes the fixture it does not build -- 'a link whose ticker matches the request but NOT the candidate passes rung 1 and is caught only here' -- and that shape IS constructible (_forged_link(ticker='ZZZZ') with _authorize(ticker='ZZZZ')). As written the ticker half of rung 3c's binding set is unexercised.

### Task 6

#### `7` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2108 (lens 9); PLAN:3191 (S5.1 reason view)
- **specified outcome:** archive_status='unavailable' over a non-empty window is OUR IGNORANCE, not survival: refuse aliveness_unverifiable.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_an_unreadable_archive_is_not_a_survival_case_7`
- **asserted outcome:** With resolve_ohlcv_window raising, the probe refuses 'aliveness_unverifiable' and archive_status reads 'unavailable'.

#### `7b` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2109 (lens 9b); PLAN:3191 (S5.1 reason view)
- **specified outcome:** archive_status='ok' with a MISSING INTERIOR session refuses aliveness_unverifiable; omitting per-session completeness passes case 7 and fails only this one.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_an_ok_archive_with_an_interior_hole_is_not_covered_case_7b`
- **asserted outcome:** With 2026-07-22 removed from the closes, the probe refuses 'aliveness_unverifiable' with archive_status 'ok' and coverage.missing_sessions == ['2026-07-22'].

#### `8` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2110 (lens 10)
- **specified outcome:** A fill on the anchor session with zero bars is ADMITTED -- the empty window is alive by construction; a naive 'require bars' rule refuses exactly it.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_fill_on_the_anchor_session_needs_no_bars_case_8`
- **asserted outcome:** closes={} with fill_session=ANCHOR admits, window_empty is True and the coverage blob is {'window_empty': True}.

#### `9` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2111 (lens 11); PLAN:3186 (S5.1 reason view); PLAN:4165 (R9-08 fix direction)
- **specified outcome:** The fire's initial_stop mutated after minting refuses frozen_value_drift -- with the canonical barrier trigger restored BYTE-IDENTICALLY before the probe, or the fixture tests the integrity guard instead.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_moved_invalidation_refuses_case_9`
- **asserted outcome:** The stop is moved through candidates_barrier_lifted, barrier_installed(conn) is re-asserted True, and the probe refuses 'frozen_value_drift'.

#### `9b` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2111 (lens 11, the other operand); PLAN:3186 (S5.1 reason view)
- **specified outcome:** The same cross-check on the PIVOT: an implementation checking only the stop admits and looks correct.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_moved_pivot_refuses_case_9b`
- **asserted outcome:** The pivot is moved through the same barrier-lift helper, the barrier is re-asserted installed, and the probe refuses 'frozen_value_drift'.

#### `10` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2113 (lens 12)
- **specified outcome:** criteria_lapse_armed=True over a lapse-qualifying latch is STILL ADMITTED (the rung is forced off); with the force bypassed the reason arriving back RAISES LatchProbeInvariantError.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_the_lapse_rung_is_forced_off_and_a_lapse_arriving_anyway_raises_case_10`
- **asserted outcome:** The unforced derivation is asserted to lapse first (so the config really arms it), the probe then admits, and with the force bypassed LatchProbeInvariantError is raised.

#### `11` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2114 (lens 13)
- **specified outcome:** A declined latch and a criteria_lapsed latch -- both rendering state='horizon_expired' -- must be distinguishable by clear_reason, not by state.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_declined_and_criteria_lapsed_are_distinguished_by_reason_case_11`
- **asserted outcome:** The declined latch renders state='horizon_expired' with clear_reason='declined' and refuses; the same rendered state with clear_reason='criteria_lapsed' raises instead.

#### `11b` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2115 (lens 13b)
- **specified outcome:** A decline before the fill refuses at the resolver level, asserting non-admission AND the exact reason and session.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_decline_before_the_fill_refuses_case_11b`
- **asserted outcome:** admitted False, decline_reason 'mandate_not_alive', clear_reason 'declined', clear_session 2026-07-22.

#### `11c` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2116 (lens 13c)
- **specified outcome:** A supersession before the fill refuses, same shape.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_supersession_before_the_fill_refuses_case_11c`
- **asserted outcome:** admitted False, 'mandate_not_alive', clear_reason 'superseded', clear_session 2026-07-23.

#### `16` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2122 (lens 18)
- **specified outcome:** A fill dated past the horizon expiry is refused.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_fill_past_the_horizon_refuses_case_16`
- **asserted outcome:** With horizon_sessions=3 the expiry is asserted to precede the fill; the probe refuses 'mandate_not_alive' with clear_reason 'horizon' at the computed expiry.
- **note:** The window is 3 sessions rather than the lens's 30; the relation (expiry strictly before the fill) is asserted in the fixture, which is the property.

#### `19` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2126 (lens 22); PLAN:3192 (S5.1 reason view)
- **specified outcome:** An injected load_decision_intents failure refuses decision_evidence_unavailable; the case passes trivially against today's silent {}.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_an_unreadable_decision_ledger_refuses_case_19`
- **asserted outcome:** A control leg first asserts the same world ADMITS; the ledger read is then made to raise and the probe refuses 'decision_evidence_unavailable'.

#### `20` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2127 (lens 23); PLAN:3193 (S5.1 reason view)
- **specified outcome:** A place recorded AFTER the fill that outranks an earlier decline refuses decision_evidence_post_dates_fill; one recorded ON the fill session refuses decision_ordering_ambiguous.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_decisions_are_ordered_against_the_fill_by_recorded_ts_case_20`
- **asserted outcome:** Both branches are built and each returns its own reason, plus a third control leg recorded strictly before that ADMITS.

#### `24` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2131 (lens 27)
- **specified outcome:** Coverage is derived from derivation.archive_closes: a fixture whose SECOND read would differ must not change the verdict.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_coverage_comes_from_the_derivations_own_bars_case_24`
- **asserted outcome:** A counting stub returns a GAPPED frame first and a COMPLETE one after; the probe refuses 'aliveness_unverifiable' and the call counter is asserted to be exactly 1.

#### `27` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2158 (lens 32)
- **specified outcome:** An accepted order placed against a same-pivot RECONFIRMATION fire is found by candidate_set MEMBERSHIP; an identity-match implementation returns fire_not_derivable.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_an_order_on_a_reconfirmation_fire_is_found_by_membership_case_27`
- **asserted outcome:** The latch identity is asserted to be the OPENING fire while the reconfirmation is inside candidate_set; the probe on the reconfirmation's order ADMITS with clear_reason None.

#### `28a` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2135 (lens 31)
- **specified outcome:** A horizon expiry dated exactly ON the fill session ADMITS; a bare 'clear_reason is None' implementation refuses it.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_horizon_expiry_on_the_fill_session_admits_case_28a`
- **asserted outcome:** admitted True, clear_reason 'horizon' at the fill session, admission_basis 'subject_fill_wins_same_session_tie'.

#### `28b` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2135 (lens 31)
- **specified outcome:** A decline dated exactly ON the fill session ADMITS.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_decline_on_the_fill_session_admits_case_28b`
- **asserted outcome:** admitted True, clear_reason 'declined' at the fill session, admission_basis the tie.

#### `28c` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2135 (lens 31)
- **specified outcome:** A supersession dated exactly ON the fill session ADMITS.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_supersession_on_the_fill_session_admits_case_28c`
- **asserted outcome:** admitted True, clear_reason 'superseded' at the fill session.
- **note:** Alone among 28a-28c it does not also assert admission_basis; the verdict and the reason/session are pinned.

#### `28d'` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2136 (lens 31d)
- **specified outcome:** A fixture whose ONLY sub-stop close is dated ON the fill session yields clear_reason None -- it PINS AN ABSENCE, and fails loudly if bar_bound ever widens.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_sub_stop_close_on_the_fill_session_is_never_seen_case_28d_prime`
- **asserted outcome:** The latch's clear_reason is None, the fill session is asserted ABSENT from derivation.archive_closes, and the probe admits with admission_basis 'armed'.

#### `28e` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2156 (lens 31b)
- **specified outcome:** Each of the three reachable tie branches dated ONE session EARLIER must REFUSE, or 'admit on any terminal at-or-after the anchor' also passes 28a-28c.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_the_tie_does_not_widen_to_the_session_before_case_28e`
- **asserted outcome:** All three worlds are built and each refuses 'mandate_not_alive' with its own (clear_reason, clear_session) one session early.

#### `28f` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2157 (lens 31c)
- **specified outcome:** Another trade's fill terminal ON the fill session, that trade carrying a different or absent order id, REFUSES mandate_not_alive naming clear_reason='fill', the matched trade and its fill_link_basis.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_another_trades_fill_on_the_fill_session_still_refuses_case_28f`
- **asserted outcome:** Refuses 'mandate_not_alive' with clear_reason 'fill', and asserts probe_evidence fill_terminal_trade_id == 77 and fill_terminal_link_basis == 'windowed'.

#### `41b` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2138 (lens 47); PLAN:3182 (S5.1 reason view)
- **specified outcome:** req.entry_date on a Saturday refuses fill_session_not_a_session before any probe runs.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_weekend_fill_date_is_refused_before_any_probe_runs_case_41b`
- **asserted outcome:** fill_session=2026-07-25 (a Saturday) returns admitted False with 'fill_session_not_a_session'.

#### `41c` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2139 (lens 48); PLAN:3183 (S5.1 reason view)
- **specified outcome:** A probe whose horizon predates the fire's own action session refuses fire_not_derivable -- the CORRECT implementation producing the reason, which case 27 never asserted.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_probe_before_the_fires_own_session_is_not_derivable_case_41c`
- **asserted outcome:** fill_session=2026-07-17 against a 2026-07-20 fire returns 'fire_not_derivable'.

#### `41d` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2140 (lens 49); PLAN:3184 (S5.1 reason view)
- **specified outcome:** Two latches whose candidate_sets both contain the link's fire refuse ambiguous_fire_membership.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_two_latches_containing_one_fire_are_ambiguous_case_41d`
- **asserted outcome:** A doubled derivation is injected (declared unreachable in production, stated in the docstring) and the probe returns 'ambiguous_fire_membership'.

#### `41e` -- task 6 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2155 (lens 50); PLAN:3185 (S5.1 reason view)
- **specified outcome:** The junk-pivot link (minted with NULL frozen values, the ledger write NOT blocked) carried through to admission refuses frozen_value_unavailable at the RESOLVER.
- **test:** `tests/trades/test_22a_task6_mandate_alive_at.py::test_a_null_frozen_value_refuses_at_the_resolver_case_41e`
- **asserted outcome:** The minted link is asserted to carry frozen_invalidation None and the probe returns 'frozen_value_unavailable'.

### Task 6a

#### `4c-i` -- task 6a -- **UNVERIFIABLE** (READ, named_function)

- **spec:** PLAN:1936 (S3.4c bullet 4c-i); PLAN:2098 (lens 1)
- **specified outcome:** Two accepted links on one ticker, only one live at the fill session. The envelope naming the LIVE one ADMITS; THE SAME FIXTURE WITH THE ENVELOPE NAMING THE DEAD ONE refuses mandate_not_alive -- 'an implementation ignoring the order id cannot produce both verdicts'.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_a_dead_rival_is_dropped_and_its_own_leg_refuses_case_4c_i`
- **asserted outcome:** Leg 1 (live envelope): the ladder ADMITS and the scanned competitor list is exactly the rival's link id. Leg 2: mandate_alive_at is called DIRECTLY on the rival's order and returns mandate_not_alive / superseded -- the LADDER is not run on the dead order, and the docstring states the ladder would return ambiguous_ticker_orders instead.
- **note:** THE PLAN DETERMINES TWO OUTCOMES FOR THE SECOND LEG AND THEY DISAGREE. S3.4c (PLAN:1936-1940): 'Then the same fixture with the envelope naming the DEAD one -> refuse mandate_not_alive. An implementation ignoring the order id cannot produce both verdicts.' S2.4 rung 8 (PLAN:1277) + S2.4b: 'exactly ONE competitor-free accepted link on this TICKER' -> ambiguous_ticker_orders, and rung 8 runs BEFORE the probe. From the dead order's seat the subject is a live competitor, so the ladder emits ambiguous_ticker_orders and the specified mandate_not_alive is unreachable at the specified grain. The implementer resolved it by asserting at the PROBE grain and declared the divergence in the docstring, which is honest -- but the resolution is a ruling nobody made. Routing question for the directors: does 4c-i's second leg move to the probe grain (ratify the test) or does the plan sentence stand and the case need a fixture where rung 8 does not pre-empt it?

#### `4c-i-pre` -- task 6a -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2170 (lens 39)
- **specified outcome:** CASE 4c-i's IDENTICAL fixture with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_a_dead_rival_does_not_rescue_a_pre_barrier_link_case_4c_i_pre`
- **asserted outcome:** The pre-barrier world PLUS 4c-i's own dead rival returns 'pre_barrier_unproven' with the pre-barrier tier.
- **note:** The base case's own seeding is reproduced and only the boundary varies.

#### `4c-ii` -- task 6a -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1941 (S3.4c bullet 4c-ii); PLAN:3171 (S5.1 reason view)
- **specified outcome:** Two accepted links BOTH live at the fill session refuse ambiguous_ticker_orders regardless of which the envelope names.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_two_live_orders_on_one_ticker_are_ambiguous_case_4c_ii`
- **asserted outcome:** A same-pivot same-stop reconfirmation rival is accepted and authorizing the SUBJECT returns 'ambiguous_ticker_orders'.
- **note:** Only one of the two directions is run ('regardless of which the envelope names' is exercised for the subject only). The rivals are symmetric by construction, so this is a remark rather than a downgrade.

#### `15f` -- task 6a -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2121 (lens 17b); PLAN:3171 (S5.1 reason view)
- **specified outcome:** Two live accepted orders on one ticker refuse ambiguous_ticker_orders -- and the rival's acceptance is on a DIFFERENT session, so a scan scoped to one acceptance session or one run passes 4c-ii and fails this.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_a_later_refire_order_also_competes_case_15f`
- **asserted outcome:** The rival is accepted on 2026-07-23 (the subject on 07-21) and the subject returns 'ambiguous_ticker_orders'.

#### `23` -- task 6a -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2130 (lens 26)
- **specified outcome:** A valid target beside a rejected-superseded, a consumed and an invalidated competitor ADMITS, not ambiguous_ticker_orders.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_superseded_consumed_and_dead_rivals_all_drop_case_23`
- **asserted outcome:** All three rivals are built; the subject ADMITS and the SCANNED population is asserted to be exactly the dead one, distinguishing 'filtered out' from 'judged and dropped'.

#### `23-pre` -- task 6a -- **WEAKER** (READ, named_function)

- **spec:** PLAN:1800 (S3 twin convention); PLAN:2170 (lens 39)
- **specified outcome:** CASE 23's IDENTICAL fixture -- the dead, the superseded and the consumed rival -- with the REAL boundary refuses pre_barrier_unproven.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_a_filtered_population_does_not_rescue_a_pre_barrier_link_case_23_pre`
- **asserted outcome:** A pre-barrier world with ONLY the dead rival returns 'pre_barrier_unproven'.
- **note:** One of case 23's three rivals is built. The docstring says 'case 23's twin, same shape and same ruling'; the shape is a third of it, and two of the three filter paths the base case exists for are unexercised. Mildest instance of the twin-fixture class.

#### `23b` -- task 6a -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2167 (lens 37); PLAN:3171 (S5.1 reason view)
- **specified outcome:** An unconsumed authoritative competitor over an archive with archive_status='unavailable' (here an incomplete window) refuses competitor_liveness_unverifiable; an exclude-the-unresolved implementation admits.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_a_rival_over_an_incomplete_window_is_unverifiable_case_23b`
- **asserted outcome:** With an interior hole the subject refuses 'competitor_liveness_unverifiable' -- asserted on the REASON, because the shared hole would also refuse the subject's own probe with a different reason.

#### `23c` -- task 6a -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2167 (lens 37)
- **specified outcome:** A competitor whose decision ledger cannot be read refuses competitor_liveness_unverifiable.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_a_rival_whose_decision_ledger_cannot_be_read_is_unverifiable_case_23c`
- **asserted outcome:** A SELECTIVE ledger failure (the rival's candidate only) makes the subject refuse 'competitor_liveness_unverifiable'.

#### `23d` -- task 6a -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2167 (lens 37)
- **specified outcome:** A competitor with a NULL snapshot refuses competitor_liveness_unverifiable.
- **test:** `tests/trades/test_22a_task6a_competitor_liveness.py::test_a_rival_with_a_null_snapshot_is_unverifiable_case_23d`
- **asserted outcome:** A junk-pivot rival mints NULL frozen values (asserted) and the subject refuses 'competitor_liveness_unverifiable'; the docstring notes this is the cleanest of the three because the junk fire never joins the subject's latch.

### Task 8

#### `5c` -- task 8 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2107 (lens 8); PLAN:1622 (S2.4.2); PLAN:2088 (S3.5c)
- **specified outcome:** The fill session is req.entry_date and nothing else: two submissions differing ONLY in that field must reach different verdicts.
- **test:** `tests/trades/test_22a_task8_resolver.py::test_the_fill_session_is_req_entry_date_and_nothing_else_case_5c`
- **asserted outcome:** entry_date=2026-07-27 admits with horizon_session 07-27; entry_date=2026-09-15 refuses mandate_not_alive / horizon with horizon_session 09-15. Every other field is identical.

#### `18` -- task 8 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2125 (lens 21); PLAN:3164 (S5.1 reason view)
- **specified outcome:** cfg=None and an envelope without the key each decline with their OWN reason, not a shared one.
- **test:** `tests/trades/test_22a_task8_resolver.py::test_no_config_and_no_order_id_decline_with_their_own_reasons_case_18`
- **asserted outcome:** no_config (linked world, recognised) and no_config (no-link world, NOT recognised); no_order_id; plus no_envelope, origin_envelope_inconsistent and no_accepted_latch_order, each with its recognition flag.
- **note:** Broader than the spec asks: it also carries the only end-to-end assertion of no_envelope, which the reason view assigns to case 15e.

### Task 9

#### `1` -- task 9 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:1852 (S3.1, the whole case)
- **specified outcome:** OII's real geometry admits and the row carries the fire's three keys; AND the resolution NAMES validity_intent_id=2, place_intent_id=1, broker_order_id='1007523377009', clear_reason=None, bars_through='2026-08-14', horizon_session='2026-08-17', the freeze_tier and the snapshot equality; AND the drift variant (the 08-17 watch row removed) gives an identical result.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_a_latched_fill_labels_from_the_fire_case_1 ; tests/trades/test_22a_task9_entry_wiring.py::test_bucket_drift_is_not_death_case_1`
- **asserted outcome:** The persisted row is (pipeline_aplus, candidate_id, a label starting 'A+ baseline'), and with a completed drifted watch run present the row still carries the FIRE's keys and the fire-derived label -- with the ordinary chain first asserted to answer differently.
- **note:** The persisted-row half is asserted well (the drift leg is genuinely discriminating and its circularity was already repaired). The RESOLUTION half of S3.1 -- the two intent ids, the broker order id, clear_reason, bars_through/horizon_session, the freeze_tier and the snapshot equality -- is asserted by NO test bound to case 1. bars_through is asserted once in the arc, at tests/trades/test_22a_task6_mandate_alive_at.py:926, in a test carrying no case id. The fixture is also the synthetic probe world rather than trade 25's real OII rows; that substitution is DECLARED in the module docstring (tests/trades/test_22a_task9_entry_wiring.py:9-17) with its reasoning, so it is disclosed rather than hidden.

#### `1-pre` -- task 9 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:1876 (S3.1, CASE 1-pre); PLAN:1881 (Option C: no longer a twin -- trade 25's LIVE outcome); PLAN:3187 (S5.1 reason view)
- **specified outcome:** CASE 1's identical fixture with the REAL boundary: NOT admitted, decline reason pre_barrier_unproven, and the row lands manual_off_pipeline + NULL candidate + NULL label. Under Option C this is not a twin at all -- it is what the live entry path does on trade 25 the day 0037 lands.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_a_pre_barrier_fire_records_honest_unset_case_1_pre`
- **asserted outcome:** Case 1's fixture with pre_barrier=True and a NON-NULL submitted hypothesis_label: the persisted row is ('manual_off_pipeline', None, None). The decline reason is not asserted.
- **note:** The fixture IS case 1's, and seeding a non-NULL submitted label is the right discriminator -- but the named reason pre_barrier_unproven, which the spec states as part of the required outcome and which S5.1's reason view routes here, is never asserted. The persisted row is identical for every refusal reason, so an implementation refusing case 1 for drift or coverage passes this row. This matters more than the other twins: the plan makes 1-pre trade 25's LIVE outcome and the S9 operator gate is written around it. 5b-pre, in the same module, shows the shape (reason + clear_reason None + probe_evidence None + the row).

#### `2` -- task 9 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1885 (S3.2); PLAN:3167 (S5.1 reason view)
- **specified outcome:** AMN's no-latch shape falls through unchanged, and THE DISCRIMINATING ASSERTION IS THE DECLINE REASON no_accepted_latch_order (the origin alone would pass any broken implementation).
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_a_fill_with_no_latch_rows_falls_through_case_2`
- **asserted outcome:** decline_reason == 'no_accepted_latch_order', recognised_but_underivable False, and the written row is asserted equal to a CONTROL world's row.

#### `3` -- task 9 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1901 (S3.3)
- **specified outcome:** With no trade and no fill: no arc path is entered, no row is written to any table, and the latch derivation is byte-identical before and after (asdict comparison).
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_an_unfilled_mandate_is_untouched_by_the_arc_case_3`
- **asserted outcome:** The arc's read surfaces are DRIVEN first (the link is found, the mandate is alive, the barrier stands) so the null result is not vacuous; then every table count is unchanged, trades and fills are 0, and the asdict-compared derivation is identical.
- **note:** The docstring records that the first version of this test was vacuous and was proved so by execution; the rebuild is the stronger of the two shapes the spec asks for.

#### `5a` -- task 9 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:1981 (S3.5 case 5a); PLAN:2151 (lens 57b); PLAN:1957 (S3.5 required result, stated in FULL)
- **specified outcome:** A breach on a PRIOR session refuses mandate_not_alive with clear_reason='invalidation' and its clear_session, and the row lands manual_off_pipeline + NULL candidate + SQL-NULL label (never the submitted one), with the discarded label asserted in the WARNING SEPARATELY.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_a_breach_on_a_prior_session_refuses_case_5a ; tests/trades/test_22a_task9_entry_wiring.py::test_the_discarded_label_is_logged_not_persisted_case_5a`
- **asserted outcome:** The persisted row is ('manual_off_pipeline', None, None) with a NON-NULL submitted label seeded, and the WARNING is asserted to carry the discarded value. Neither test asserts the decline reason, the clear_reason or the clear_session.
- **note:** The invalidation-SPECIFIC half is missing. The persisted row is identical under ANY refusal reason, so a fixture that refused for an unrelated reason -- a coverage hole, an unreadable ledger -- passes both legs. The spec states the required result 'in FULL' precisely to prevent that. The label/WARNING split (harvest H4) is done exactly right and is not the gap.

#### `5b` -- task 9 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1984 (S3.5 case 5b); PLAN:2150 (lens 57)
- **specified outcome:** A breach close ON the fill session with the fill through the pivot intraday ADMITS (RD's uniform fill-wins, on the survivorship ground).
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_a_breach_on_the_fill_session_admits_case_5b`
- **asserted outcome:** With the breach moved onto the fill session the row lands (pipeline_aplus, candidate_id); the docstring states both the synthetic dimension and the survivorship ground.

#### `5b-pre` -- task 9 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1994 (S3.5 case 5b-pre, with its four explicit obligations)
- **specified outcome:** BYTE-IDENTICAL to 5b with exactly ONE dimension changed (the epoch boundary): refuse pre_barrier_unproven, row lands manual_off_pipeline + NULL + NULL, AND pin clear_reason None and that no aliveness evidence was recorded, so refuse-at-rung-9 is distinguished from refuse-after-probing.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_the_pre_barrier_twin_of_the_tie_refuses_case_5b_pre`
- **asserted outcome:** Same breach-on-fill-session closes as 5b with pre_barrier=True: decline_reason 'pre_barrier_unproven', clear_reason None, probe_evidence None, and the row lands ('manual_off_pipeline', None, None).
- **note:** The model twin of the whole arc: same fixture, one varied dimension, and all four of the spec's obligations asserted including the ORDER-pinning probe_evidence is None.

#### `6` -- task 9 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:2073 (S3.6); PLAN:2077 (required result); PLAN:2085 (the display-precision variant); PLAN:2106 (lens 7); PLAN:2134 (lens 30)
- **specified outcome:** A close EXACTLY EQUAL to the frozen invalidation ADMITS with case 1's three keys -- AND the display-precision variant varying BOTH operands (frozen stop 41.424 against a close of 41.4199, both rounding to 41.42) must also ADMIT, which is what fails close-only, stop-only and no-rounding implementations.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_a_close_exactly_at_the_invalidation_admits_case_6`
- **asserted outcome:** With one close set exactly to STOP the row lands (pipeline_aplus, candidate_id). The label is discarded and no display-precision variant is built.
- **note:** The strict-inequality half (lens 5) is asserted; the BOTH-OPERANDS rounding half (lens 7 and lens 30, and S3.6's own last bullet, added by review 22A-R15-13) is ABSENT from the arc. Measured: no test_22a_*.py file contains 41.424 or 41.4199 as a close/stop pair (grep over all twenty arc modules; the only 41.4* literal is task 1's frozen_invalidation constant). The plan gives the exact geometry and the exact failure directions, so the fix is a fixture, not a design.

#### `6-pre` -- task 9 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:2078 (S3.6, '...with its own -pre twin per the S3 convention'); PLAN:1800
- **specified outcome:** CASE 6's identical fixture with the REAL boundary refuses pre_barrier_unproven and the row lands honest-unset.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_the_pre_barrier_twin_of_the_boundary_refuses_case_6_pre`
- **asserted outcome:** Case 6's closes with pre_barrier=True: the row lands ('manual_off_pipeline', None, None). The decline reason is not asserted.
- **note:** The fixture IS the base case's, which is what 8-pre and its six siblings lack -- but the reason pre_barrier_unproven, the thing the twin convention exists to pin, is never named. The persisted row is identical for every refusal reason, so an implementation that refused case 6 for a coverage or drift reason passes this twin. 5b-pre, in the same module, shows the shape this should take.

#### `12` -- task 9 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2117 (lens 14); PLAN:3190 (S5.1 reason view)
- **specified outcome:** An accepted link with underivable keys, WITH the ticker aplus in the latest run, lands manual_off_pipeline + NULL + NULL -- suppression, never fallback.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_a_refused_link_suppresses_the_ordinary_chain_case_12`
- **asserted outcome:** A CURRENT completed aplus run for the ticker is seeded (so a fallback implementation would write pipeline_aplus plus today's candidate) and the row still lands ('manual_off_pipeline', None, None).

#### `21` -- task 9 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2128 (lens 24); PLAN:2168 (lens 38)
- **specified outcome:** BEGIN IMMEDIATE, not the deferred 'with conn:': a competing writer must not be able to commit between the authoritative read and the INSERT, and the written row reflects the INSIDE verdict.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_the_written_row_reflects_the_inside_verdict_case_21`
- **asserted outcome:** From a SECOND connection, BEGIN IMMEDIATE is observed to FAIL at the moment of authoritative authorization (so no competing writer could commit), and the row lands pipeline_aplus.
- **note:** The spec's literal experiment (mutate the ledger between recognition and INSERT) is unrunnable if the property holds; the test asserts the mechanism that makes it unrunnable and explains why in its docstring. Judged faithful to lens 38, which names the clause.

#### `21b` -- task 9 -- **WEAKER** (READ, named_function)

- **spec:** PLAN:2169 (lens 38b)
- **specified outcome:** A request whose recognition found NO link ACQUIRES ONE before the INSERT: an implementation reserving only on the recognised-latched path takes the ordinary path on a stale negative.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_a_no_link_preliminary_still_reserves_case_21b`
- **asserted outcome:** The write reservation is observed to be held at the lookup, and a trade row exists. NO LINK IS EVER PLANTED: the world is built without accept_and_link and the spy's 'and NOW the link arrives' comment is followed only by a delegation to the real lookup.
- **note:** The reservation half is asserted; the ARRIVAL half -- the event the case is named for -- is not built. The test's own inline comment describes a link landing inside the window and no code plants one, so the assertion that the row reflects the arrived link (as case 37b does at the route) has no counterpart here. Fix: insert the link inside the spy, as T10's case 37b already does.

#### `37c` -- task 9 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:3391 (S7 task-9 acceptance cell); PLAN:4164 (R9-03 context)
- **specified outcome:** A usable but UNMATCHED broker order id plus a pattern_evaluation_id anchor plus a manual latest-run origin must still be REFUSED -- the case that fails an implementation deferring the route guard without RELOCATING it.
- **test:** `tests/trades/test_22a_task9_entry_wiring.py::test_an_unmatched_order_id_with_a_pe_anchor_is_refused_case_37c`
- **asserted outcome:** derive_trade_origin is first asserted to answer manual_off_pipeline (so the fixture keys the guard), PatternEvaluationAnchorError is raised naming that origin, zero trades are written, and a control with no order id is asserted NOT to refuse in the service.
- **note:** Faithful to the plan as written. Out of scope but worth flagging: the resume record names 37c as one of the four instances of RD's 'cohort bookkeeping never blocks a money-bearing entry' class, so the SPECIFICATION here is under a live ruling. The audit judges test-to-spec fidelity, not the spec.

### Task 10

#### `37` -- task 10 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2175 (lens 43)
- **specified outcome:** The route must NOT reject a RECOGNISED-AND-REFUSED entry (branch c), or the service never writes the honest-unset row -- and a test covering only the ADMITTED branch passes an implementation that still rejects (c).
- **test:** `tests/web/test_routes/test_22a_task10_entry_route_ext2.py::test_an_admitted_latched_entry_passes_through_the_route_case_37 ; tests/web/test_routes/test_22a_task10_entry_route_ext2.py::test_a_recognised_and_refused_entry_passes_through_the_route_case_37`
- **asserted outcome:** BOTH branches are posted through the real route with a spy on record_entry: in each the spy records the call (the route reached the service), and the admitted branch's persisted row carries the fire's three keys.
- **note:** The spy is what distinguishes a route rejection from a service refusal, which the docstring states; the (c) branch is asserted exactly as the lens demands.

#### `37b` -- task 10 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2143 (lens 66)
- **specified outcome:** A link lands between the route's read and the service's transaction; the written row must reflect the INSIDE verdict.
- **test:** `tests/web/test_routes/test_22a_task10_entry_route_ext2.py::test_a_link_arriving_after_the_routes_decision_point_wins_case_37b`
- **asserted outcome:** The world is built WITHOUT a link; the link is inserted from a second connection inside the spy, immediately before record_entry; the response is 200 and the written row carries the fire's three keys.
- **note:** This is the shape case 21b's docstring describes and does not build.

### Task 11

#### `17` -- task 11 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2123 (lens 19, RE-BASED FOR OPTION C)
- **specified outcome:** On a POST-BARRIER synthetic (boundary seeded below the fire, the subject trade AND its fill planted) the correction still ADMITS at latch_ladder; omitting exclude_trade_ids returns clear_reason='fill' and refuses.
- **test:** `tests/trades/test_22a_task11_correction_dispatch.py::test_the_correction_admits_at_the_latch_ladder_case_17 ; tests/trades/test_22a_task11_correction_dispatch.py::test_omitting_the_exclusion_returns_clear_reason_fill_case_17 ; tests/trades/test_22a_task11_correction_dispatch.py::test_the_service_passes_the_subject_in_the_exclusion_set_case_17`
- **asserted outcome:** The applied correction carries admission_tier 'latch_ladder' with all four citations and a probe blob; the SAME world authorized WITHOUT the exclusion refuses mandate_not_alive / clear_reason 'fill' at the fill session; and a spy proves the SERVICE supplies the exclusion set.
- **note:** Both directions plus the service-supplies-it leg; pre-fix and post-fix values are both stated.

#### `31` -- task 11 -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:1693 (S2.6.5 case 31); PLAN:3355 (S6, limitation-pinning)
- **specified outcome:** A criterion edited between minting and admission moves the derived LABEL while the pivot/stop cross-check stays clean; the case asserts VISIBILITY in the recorded evidence, NOT a refusal, and says in its own docstring that it pins a limitation.
- **test:** `tests/trades/test_22a_task11_correction_dispatch.py::test_a_criterion_edited_after_minting_moves_the_label_case_31`
- **asserted outcome:** The baseline label is taken from the framework's own builder; one criterion row is edited; the stored evidence shows invalidation_equal_at_dp==1, pivot_equal_at_dp==1 and frozen==live raws, while the applied label has changed and is asserted != baseline. The docstring states the limitation.

#### `34a` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2400 (S4.3, raw-INSERT counterexamples); PLAN:2382 (S4.3 limit 1)
- **specified outcome:** Two identical FABRICATED non-empty coverage arrays are ACCEPTED -- the limit being pinned, and the docstring must say so.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:COVERAGE_CASE_IDS@61 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_two_identical_fabricated_coverage_arrays_are_accepted_case_34a`
- **asserted outcome:** Three fabricated 2001 sessions in both arrays insert; the row count is 1. The docstring states the trigger cannot enumerate a calendar and points at case 7b for the coverage FACT.

#### `34b` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2400 (S4.3, raw-INSERT counterexamples)
- **specified outcome:** Two EMPTY arrays with window_empty absent are ACCEPTED -- same limit, same labelling.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:COVERAGE_CASE_IDS@61 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_two_empty_coverage_arrays_without_window_empty_are_accepted_case_34b`
- **asserted outcome:** Empty expected/observed/missing arrays insert; the row count is 1; the docstring labels the acceptance as the limit.

#### `34c` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2400 (S4.3); PLAN:2173 (lens 42)
- **specified outcome:** A required evidence key OMITTED is REJECTED by the json_type presence assertion -- and it PASSES against a json_remove closure-only implementation, which is the discriminating point.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:COVERAGE_CASE_IDS@61 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_required_evidence_key_is_rejected_case_34c`
- **asserted outcome:** The unmutated baseline is asserted to insert; deleting evidence_version then raises IntegrityError matching 'citation graph'.

#### `34d` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2174 (lens 42b); PLAN:2400 (S4.3)
- **specified outcome:** A horizon_session not equal to entry_fill_session_date is REJECTED (the field is SQL-BOUND; bars_through deliberately is not).
- **test:** `tests/data/test_22a_task11_citation_evidence.py:COVERAGE_CASE_IDS@61 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_a_mismatched_horizon_session_is_rejected_case_34d`
- **asserted outcome:** Baseline inserts; horizon_session='2001-01-02' then raises 'citation graph'.

#### `34e` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2174 (lens 42b); PLAN:2397 (S4.3, the parent relation R3-10 found missing)
- **specified outcome:** A cited validity row whose validated_place_intent_id differs from the cited place intent is REJECTED.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:COVERAGE_CASE_IDS@61 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_a_mismatched_validity_parent_is_rejected_case_34e`
- **asserted outcome:** Baseline inserts; a REAL second place row on the same candidate is planted and cited, and the insert raises. The docstring declares that an isolating mutation is unconstructable and why.
- **note:** The mutation violates the parent relation AND the link's duplicated-field relation together; the impossibility of isolating them is declared rather than glossed.

#### `34f` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2646 (S4.3a, case 34f); PLAN:3471+ (S8-L16)
- **specified outcome:** Correct raw operands beside a FALSE invalidation_equal_at_dp = 1 are ACCEPTED -- the declared residual of the single-rounding-authority rule, pinned with a docstring saying it is a limit.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:ROUNDING_CASE_IDS@62 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_a_false_equality_verdict_over_correct_raws_is_accepted_case_34f`
- **asserted outcome:** Raws 6.20 / 7.90 are first asserted to DISAGREE at 2dp, are minted BOUND to their sources, the verdict 1 is planted, the insert succeeds, and the LANDED row is read back and asserted to carry (6.20, 7.90, 1).
- **note:** The docstring records that this test's first version contained no false verdict at all and was the vacuous-regression class; the current form reads the landed row back, which is what makes the residual real.

#### `34g` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2648 (S4.3a, case 34g); PLAN:4163 (R9-05); PLAN:4181 (S13.3(3): 'use 22.125 / 22.1249')
- **specified outcome:** A price pair EQUAL in Python and UNEQUAL in SQLite is ACCEPTED -- the case that would have caught the forbidden round(...)=round(...) comparator. S4.3a's literal geometry (frozen = live = 22.125) does NOT discriminate; the plan's own S13.3(3) directs the repaired pair.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:ROUNDING_CASE_IDS@62 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_an_eighths_price_pair_equal_in_python_is_accepted_case_34g`
- **asserted outcome:** 22.125 / 22.1249: BOTH arithmetics are asserted in-test (Python equal, SQLite unequal, the SQLite side computed by the live connection), the pair is minted bound to its sources, and the insert succeeds.
- **note:** Faithful to the plan's binding instruction (S13.3(3)) rather than to S4.3a's superseded literal geometry; the divergence is stated in the test's own docstring. A companion (case_34g_gate) carries the case-and-whitespace-normalized round( grep gate R9-05(c) asked for.

#### `39a` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2147 (lens 51); PLAN:2372 (S4.3, the tie matrix)
- **specified outcome:** A tie-basis row whose clear_session differs from the fill session is REJECTED (clear_session is REQUIRED and BOUND under the tie basis).
- **test:** `tests/data/test_22a_task11_citation_evidence.py:TIE_BASIS_CASE_IDS@63 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_a_tie_basis_row_whose_clear_session_is_not_the_fill_is_rejected_case_39a`
- **asserted outcome:** Baseline inserts; a tie-basis blob with clear_session='2001-01-02' raises 'citation graph'.

#### `39b` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2147 (lens 51); PLAN:2372 (S4.3, three REACHABLE reasons)
- **specified outcome:** A tie-basis row naming clear_reason='fill' is REJECTED -- fill is excluded by the rule and invalidation is unreachable by construction.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:TIE_BASIS_CASE_IDS@63 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_a_tie_basis_row_naming_fill_is_rejected_case_39b`
- **asserted outcome:** Baseline inserts; a tie-basis blob naming 'fill' raises.
- **note:** A companion with no case id asserts all THREE reachable reasons ADMIT, which is what keeps 39a-39c from passing against a trigger that rejected the basis outright.

#### `39c` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2147 (lens 51); PLAN:2372 (S4.3, under armed both fields are JSON null)
- **specified outcome:** An armed row carrying a non-null clear_reason is REJECTED.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:TIE_BASIS_CASE_IDS@63 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_an_armed_row_with_a_non_null_clear_reason_is_rejected_case_39c`
- **asserted outcome:** Baseline (admission_basis armed) inserts; setting clear_reason='horizon' without the tie basis raises.

#### `48a` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung1_link_ticker` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48a]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung1_link_ticker` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48b` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung2_link_parent` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48b]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung2_link_parent` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48c` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung3_validity_outcome` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48c]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung3_validity_outcome` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48d` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung3b_latest_validity_child` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48d]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung3b_latest_validity_child` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48e` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung3c_link_broker_order_id` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48e]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung3c_link_broker_order_id` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48f` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung4_governing_place_intent` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48f]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung4_governing_place_intent` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48g` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung5_cancel_intent_id` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48g]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung5_cancel_intent_id` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48h` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung6_consuming_trade_id` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48h]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung6_consuming_trade_id` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48i` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung7_consumption_scan_fill_ids` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48i]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung7_consumption_scan_fill_ids` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48j` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung8_competitor_link_ids` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48j]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung8_competitor_link_ids` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48k` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `rung9_stored_freeze_tier` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48k]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `rung9_stored_freeze_tier` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48l` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `guard_fill_origin` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48l]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `guard_fill_origin` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48m` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `guard_envelope_symbol` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48m]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `guard_envelope_symbol` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48n` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `guard_quantity` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48n]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `guard_quantity` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48o` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `guard_framework_price_bound` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48o]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `guard_framework_price_bound` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `48p` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2465 (S4.3, the 48a-48p bullet); PLAN:2142 (lens 63)
- **specified outcome:** An otherwise-valid latch_ladder admission with EXACTLY ONE $.authorization entry missing -- here `guard_broker_limit_bound` -- is REJECTED. Sixteen, not eleven: the eleven rungs plus the five separately enumerated envelope guards.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:OMISSION_CASE_IDS@54 -> tests/data/test_22a_task11_citation_evidence.py::test_an_omitted_authorization_entry_is_rejected[48p]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then exactly the `guard_broker_limit_bound` entry is deleted from the blob and the insert is asserted to raise IntegrityError matching 'citation graph'.

#### `49a` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung1_link_ticker` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49a]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung1_link_ticker`'s input is set to 'ZZZZ' (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49b` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung2_link_parent` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49b]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung2_link_parent`'s input is set to 987654 (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49c` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung3_validity_outcome` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49c]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung3_validity_outcome`'s input is set to 'rejected_by_broker' (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49d` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung3b_latest_validity_child` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49d]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung3b_latest_validity_child`'s input is set to 987654 (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49e` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung3c_link_broker_order_id` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49e]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung3c_link_broker_order_id`'s input is set to '9999999999' (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49f` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung4_governing_place_intent` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49f]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung4_governing_place_intent`'s input is set to 987654 (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49g` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung5_cancel_intent_id` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49g]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung5_cancel_intent_id`'s input is set to 987654 (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49h` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung6_consuming_trade_id` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49h]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung6_consuming_trade_id`'s input is set to 987654 (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49i` -- task 11 -- **FAITHFUL** (EXECUTED, case_ids_list)

- **spec:** PLAN:2469 (S4.3, the 49a-49i bullet)
- **specified outcome:** A COMPLETE $.authorization with every verdict still 'pass' and exactly one entry's `input` moved away from its source -- here `rung9_stored_freeze_tier` -- must be REJECTED by the binding subquery. Nine, one per SQL-BOUND rung; every one PASSES against a presence-only trigger.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:FIDELITY_CASE_IDS@58 -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_bound_rung_is_rejected[49i]`
- **asserted outcome:** The unmutated baseline is asserted to INSERT, then only `rung9_stored_freeze_tier`'s input is set to 'pre_barrier_reconstructed' (verdict untouched) and the insert is asserted to raise 'citation graph'.

#### `49j` -- task 11 -- **FAITHFUL** (READ, both)

- **spec:** PLAN:2470 (S4.3, the 49j bullet); PLAN:3471+ (S8-L17)
- **specified outcome:** A fabricated input on a SERVICE-VALIDATED clause is ACCEPTED by the trigger, and the case's docstring says so: SQL cannot reach a scan result or fold state, so this is a LIMIT and not a guarantee. The case DERIVES its scope from AUTHORIZATION_CLAUSES rather than naming members.
- **test:** `tests/data/test_22a_task11_citation_evidence.py:SERVICE_LIMIT_CASE_IDS@64 (dead literal) -> tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_service_validated_rung_is_accepted_case_49j`
- **asserted outcome:** The service-validated set is DERIVED from the roster and asserted to be exactly rungs 7 and 8 ('the service-validated set moved; 49j's scope moves with it'); fabricated inputs on both are then accepted and the latch_ladder row count is 1.

### Task 11a

#### `22c` -- task 11a -- **FAITHFUL** (READ, named_function)

- **spec:** PLAN:2166 (lens 36b)
- **specified outcome:** Splitting a Schwab-envelope fill into partials must leave EVERY partial carrying fill_origin and schwab_source_value_json, so the consumption scan still sees the order id.
- **test:** `tests/trades/test_22a_task11a_fill_identity.py::test_split_into_partials_preserves_fill_identity_case_22c`
- **asserted outcome:** Both replacement rows carry 'schwab_auto', the byte-identical envelope (compared as parsed JSON and by the order id) and the preserved audit stamp; pre-fix and post-fix values are both stated.
- **note:** A companion with no case id asserts the ordinary non-Schwab split is unchanged, so the fix could not have hard-coded schwab_auto onto every replacement.
