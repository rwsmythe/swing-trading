# Phase 21 Arc G — The Close-Provenance Asymmetry (the two joint false-all-clear fixes) + the `data_asof_date` survey — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the latch panel's mandate-FORM check obey ONE binding rule — *from a stale close, as from a run-level stamp, you MAY raise a MISMATCH alarm but you may NOT assert a MATCH* — by replacing the shipped binary freshness gate with a **close-provenance ladder** whose assertive rung requires per-bar corroboration at the derivation session and whose alarm rung requires per-bar corroboration at the close's own stamp. This closes BOTH routes to the same false all-clear (the stale close and the run-level stamp) with one mechanism, and recovers the check's value in the ~7-hour daily window in which it is currently inert.

**Architecture:** A new PURE classifier in `swing/latches/orders.py` (`classify_close_provenance`) consuming values the derivation already has; a per-ticker `{session -> close}` archive map surfaced on `LatchDerivation` (NO new `Latch` field, and decoupled from the invalidation walk); the view model consumes the classification and splits the single `expected_type` knob into an ALARM path (authorized only when the panel KNOWS it holds no dated evidence for that session and this ticker is as fresh as the whole system) and an ASSERT path (only on a corroborated close). No schema. No write-path change. No new I/O.

**Tech Stack:** Python 3.14 / SQLite (`sqlite3`) / FastAPI + Starlette 1.0 + Jinja2 + HTMX 2.x / pandas (parquet archive) / pytest.

**Base:** worktree `.worktrees/phase21-g-provenance`, branch `phase21-g-provenance`, BASELINE_SHA `1955aa59` (main, schema v32, 21-A merged).

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Commits:** conventional, carrying the task id (`fix(latches): Task 3 - ...`). **ZERO `Co-Authored-By`. No `--no-verify`. No amend.** Final `-m` paragraph plain prose (trailer-parse hazard).
- **TDD:** failing test -> SEE it fail -> minimal implementation -> SEE it pass -> commit. One red->green cycle per task. Every regression assertion is computed under BOTH the pre-fix and post-fix paths (see §H, which does that arithmetic).
- **Lint:** `ruff check swing/` stays clean. `line-length = 100`.
- **ASCII discipline:** no `§ -> <-> checkmark`, em-dash, or fractions in any string reaching stdout. **NO APOSTROPHES in any label detail string** — Jinja autoescaping renders one as `&#39;`, which silently breaks text assertions and operator search (the shipped `_build_form_check_notes` discipline).
- **Phase isolation:** NO `swing/trades/` edits. NO `swing/data/` edits. NO `swing/evaluation/` edits. **NO SCHEMA, NO MIGRATION** (schema stays v32).
- **The write path is UNTOUCHED.** `swing/evaluation/orchestration.py` is READ for the survey and NOT modified. If any task appears to need a write-path change or a column, **STOP and route to CHARC + RD** (brief §2.4, §7 hard stop).
- **A4 preserved:** every write this arc's surfaces perform stays on a POST. **NO new data source, NO network call, NO write.** It does WIDEN two existing read-only reads (Codex R5 MINOR): the archive load window gains at most one session for a ticker whose only fire is fresh (§B.1), and one additional single-row aggregate SELECT is issued per fragment build (§B.2.1). Both are read-only, both are on the POST path, and `GET /latches` still writes nothing at all.
- **A6 preserved:** every new branch degrades visibly; the fragment never 500s.
- **Suite:** run the FULL fast suite (`python -m pytest -m "not slow" -q`) to green BEFORE the Codex review, and again at the end.
- **Editable-install gotcha:** for CLI/runtime checks from the worktree use `PYTHONPATH=. python -m swing.cli ...`. `pytest` from the worktree cwd is unaffected.

---

## A. The rule, the two routes, and the honest empirical position

### A.1 The binding rule (RD; it is the whole design)

> **From a stale close — as from a run-level stamp — you MAY raise a MISMATCH ALARM but you may NOT assert a MATCH.**

Asymmetric **by design**, because the error costs are asymmetric. A false alarm is annoying, safe, and self-correcting (the operator opens the panel or the broker and sees). A false all-clear is this arc's dominant defect class: it tells the operator his entry is covered when it is not, and it does so on the one surface whose statements have to survive being believed.

### A.2 Route A — the stale close (observed, daily)

The shape check needs a derivation-session close. `derivation_session = session_offset(action_session_for_run(now), -1)`, verified live on this box:

| wall clock (HST) | action session | derivation session |
|---|---|---|
| 2026-07-28 08:00 | 2026-07-28 | 2026-07-27 |
| 2026-07-28 11:00 | **2026-07-29** | **2026-07-28** |
| 2026-07-28 14:00 | 2026-07-29 | 2026-07-28 |
| 2026-07-28 18:00 | 2026-07-29 | 2026-07-28 |

The action session rolls over AT the US close (~10:00-10:30 HST); the nightly pipeline writes the new session at 17:30 HST. So for **~7 hours of every trading day** — the operator's entire post-close review window — the derivation session has NO recorded close anywhere, the regime is UNKNOWN, and the FORM check is inert. That is exactly the window in which a regime change first becomes observable, because a pivot crossing happens during market hours.

**What the fix actually recovers (stated precisely, because the obvious claim is wrong).** A one-session-stale close CANNOT see a crossing that happened during the session that just closed — on the crossing day itself the stale close is still on the old side of the pivot. What it CAN do is keep a finding ALIVE. Today, a mismatch the operator saw at 18:00 on Monday evening **vanishes** from the panel at 10:30 on Tuesday morning and does not return until 17:30 Tuesday. Under the fix it persists through the window, labelled as stale-derived. The recovered value is *continuity of a true finding across the review window*, not clairvoyance about the current session.

### A.3 Route B — the run-level stamp (structural, latent)

`swing/evaluation/orchestration.py:229-231`:

```python
max_dates = [df.index.max() for df in ohlcv_by_ticker.values() if not df.empty]
if max_dates:
    data_asof = max(max_dates).date()          # <- a COHORT MAX
```

persisted at `:309` as `evaluation_runs.data_asof_date`, while `swing/evaluation/evaluator.py:56` takes `last_close = float(closes.iloc[-1])` from **that ticker's own** last bar, stored at `:94` as `candidates.close`. The stamp is therefore an **upper bound** on each row's close date, never a proof of it. `swing/latches/reader.py:258` reads them as a pair and `swing/web/view_models/latches.py:860-862` gates on the pair:

```python
last_close = (quote[0] if quote is not None and quote[1] == regime_session_iso else None)
```

A ticker whose archive lagged the cohort at evaluation time is persisted with an OLDER close under a FRESHER stamp, passes that gate, and gets a form asserted from a price the market had already left. This is gotcha **#30**, second instance.

**The two other `data_asof` branches must not be forgotten** (`orchestration.py:232-235`): `as_of_date` (a CLI-supplied date, which need not relate to ANY bar) and `last_completed_session(run_now)` (a clock value, reached only when no ticker had bars). Neither is a stronger provenance claim than the cohort max; the `as_of_date` branch is weaker. The design must therefore treat the stamp as an upper bound **regardless of which branch produced it** — which it does, because it never trusts the stamp for the assert direction at all.

### A.4 The honest empirical position (do NOT overstate this arc)

Measured read-only against the live DB + archive on 2026-07-28:

- Across the last 12 evaluation runs, **zero** tickers were observed carrying a close older than their run stamp (per-ticker close values were matched against dated archive bars; the single apparent hit, `PK` matching a 2023 bar, is a price coincidence, not a lag).
- Across the last 25 paired runs, `pipeline_runs.data_asof_date` (clock-derived, `runner.py:610`) and `evaluation_runs.data_asof_date` (bar-derived cohort max) **never diverged**.

So **Route B is a latent structural hazard, not an observed defect.** It is worth fixing because (a) the write path guarantees nothing, so the absence of a lag today is luck, not an invariant; (b) the failure mode is silent and the loss is the operator entering — or failing to enter — on a wrong order form; and (c) **the same mechanism that closes it is the mechanism that recovers Route A, which IS observed and daily.** Route A carries this arc's cost-justification; Route B rides the same fix. The plan must not be defended with a frequency claim it cannot support.

---

## B. The design: the close-provenance ladder

### B.1 Why a ladder, and why the archive is the witness

The persisted close carries no per-row date and the write path cannot be changed in this arc (hard stop). The ONLY read-side source that dates a close per row is the **on-disk OHLCV archive**, whose bars carry their own `asof_date` — and the derivation **already loads it** (`swing/latches/reader.py:152 load_bars` -> `resolve_ohlcv_window(..., migrate=False)`), per ticker, for the invalidation walk. This arc surfaces those bars as a per-ticker `{session -> close}` map on `LatchDerivation` and uses them to DATE the persisted close.

So the corroboration is **almost** free: for every ticker with a fire at-or-before the derivation session it compares numbers the panel ALREADY holds. The one exception is stated precisely because it is the exception the codex-auto-review caught: a ticker whose ONLY fire is fresh currently loads NO bars (the `reader.py:390-392` short-circuit), so widening the load window means that ticker gains one archive read of `[S, S]` where it previously had none. That is the whole of this arc's added I/O.

**The archive is used ONLY to DATE the close, never to replace it.** The number the check judges stays the number the cards render (`load_last_closes` -> `candidates.close`) — 21-A's shown-equals-judged invariant is preserved exactly. What changes is what the panel is willing to CLAIM about that number.

**Exactly what the corroboration proves, and what it does not (Codex R3 MINOR).** The archive is an **independently DATED** record, not an independently SOURCED one: `candidates.close` was itself derived from an archive read at evaluation time (`orchestration.py:197 fetcher.get`), so a match proves *the persisted close is the archive bar dated `X`* — it does NOT prove the archive bar is a faithful record of the market. If the archive itself carried stale content under a correct date, the ladder would be fooled. That residual is **out of this arc's model and is not newly introduced by it**: the panel's whole price picture (cards, invalidation walk, regime) already rests on the archive being an honest record, and the archive's own integrity is guarded upstream (the F6/#24/#26/18-A/18-B finiteness + trailing-ragged + write-through defenses). Stated here so no reader upgrades "corroborated" into "verified against the market".

**The witness lookup is DECOUPLED from the invalidation walk, and that decoupling is load-bearing (Codex R4 MAJOR 1).** The obvious implementation — take the newest bar of the invalidation's *eligible* set `[anchor, derivation_session]` — is **wrong for exactly the freshest latches**. A latch fires on the nightly for action session `T+1`, so its `anchor = T+1`, while that same evening `derivation_session = T`. The eligible set `{bar : T+1 <= s <= T}` is EMPTY, so the newest latch in the system — the one the operator is about to act on — could never be corroborated and could never reach an affirmative all-clear. Worse, `swing/latches/reader.py:389` short-circuits `bars_by_ticker[ticker] = []` when the earliest anchor is after the derivation session, so for a ticker whose ONLY fire is fresh, no bars are loaded at all. Therefore:

- `build_latch_derivation` widens the bar LOAD window start to `min(earliest_anchor, derivation_session)` and drops that short-circuit. **`_eligible_bars` is untouched**, so the invalidation walk, `bars_available` and `bars_through` stay bit-for-bit identical (a fresh latch still reports "invalidation NOT evaluated - no bars", which is correct: no session has elapsed since the fire). A dedicated test locks both halves (§H.T3b).
- The witness is read from the per-ticker `{session -> close}` map on `LatchDerivation`, which is anchor-independent by construction. **`Latch` gains NO field** — provenance is a fragment concern, not a latch attribute, and keeping it off `Latch` avoids duplicating the same fact in two places.

### B.2 The ladder

Let `P` = the persisted close (`quote[0]`), `D` = the run stamp (`quote[1]`), `S` = `derivation_session`, and `W(x)` = the archive close for that ticker dated exactly `x` (or `None`).

| rung | condition | meaning | may ALARM | may ASSERT |
|---|---|---|---|---|
| **A — `corroborated`** | `P` usable AND `D <= S` AND `W(S) is not None` AND `round(W(S),2) == round(P,2)` | the persisted close IS the derivation session's close | yes | **yes** |
| **B — `uncorroborated`** | `P` usable, `D <= S`, rung A does not hold | a close exists but it is not proven to be `S`'s | **only in B-continuity, §B.2.1** | no |
| **F — `future_stamp`** | `P` usable and `D > S`, or `D` unparseable/empty | the close belongs to a moment AFTER this page's own horizon, or cannot be placed in time at all | **no** | **no** |
| **C — `absent`** | no usable `P` | no price at all | no | no |

**Rung A is deliberately tight.** It requires a bar dated EXACTLY `S` whose close matches to the cent. Bar existence alone is NOT enough: the evaluation may have run before that bar landed, in which case the persisted close is older than a bar that now exists. It is the value agreement WITH the exact date that ties the two together. Coincidental agreement (two different sessions closing at the identical cent) cannot fabricate a rung-A claim, because the compared bar is pinned to `S`.

**Why rung F exists (Codex R5 MAJOR 3).** The shipped `quote[1] == regime_session_iso` gate incidentally rejected a close stamped AFTER the derivation session; removing it without replacement would let a FUTURE-stamped price decide or contest the regime. That is reachable: `load_last_closes` returns the GLOBALLY latest close per ticker, and the fragment POST deliberately rebuilds an OLDER render-time anchor (`horizon_session_override`), so a newer evaluation run can exist while the fragment describes `S`. The fragment's whole discipline is that every part of its picture describes ONE coherent moment — it is why a one-session-stale render anchor SUPPRESSES the alarms (`test_a_one_session_stale_anchor_suppresses_the_order_alarms`). A future-stamped close is held to the same standard. An UNPARSEABLE or EMPTY stamp lands here too, for the same reason the reader keeps an unplaceable fire visible rather than dropping it (`reader.py:235`): a value that cannot be placed in time cannot support a claim about a moment.

### B.2.1 The alarm rung: TWO independent conditions, each with one job

An unbounded rung-B alarm re-creates the drumbeat this codebase has paid for twice, and — worse — a carelessly bounded one re-commits **this arc's own defect inside its own fix**. Two Codex rounds each found one of those, and the resulting gate has exactly two conditions, which answer two different questions:

> **(1) DO WE KNOW WHEN THIS PRICE IS FROM?** — `round(W(D),2) == round(P,2)`: the archive holds a bar dated `D` whose close IS the persisted close. This is **the rung-A test applied at `D` instead of `S`**.
>
> **(2) IS THE GAP THE SYSTEM'S OR THE TICKER'S?** — `D == L`, where `L` = `latest_recorded_close_stamp` = `MAX(evaluation_runs.data_asof_date)` over runs holding at least one USABLE close (the same usability predicate `load_last_closes` and `count_session_recorded_closes` already share).

**Condition (1) is what stops the arc from re-committing gotcha #30 in the alarm direction (Codex R6 MAJOR).** A stamp comparison — `D == L` — is a comparison of two RUN-LEVEL values, so a ticker that lagged INSIDE the latest cohort satisfies it while its true close is a session older than `D` claims. Alarming from that price would be the exact stamp-standing-in-for-a-row-fact defect the arc exists to close, merely relocated from the assert direction to the alarm direction. Requiring the close to be corroborated **at its own stamp** removes the stamp from the reasoning entirely: the alarm runs from a close whose date is KNOWN, just earlier than `S`. Read together with rung A the whole design is one sentence — **never act on an undated price, in either direction**; assert only from a close dated `S`, alarm only from a close dated `D < S` that is proven to be dated `D`.

**Condition (2) is what stops the drumbeat (Codex R5 MAJOR 1).** Corroboration at `D` alone is not enough: a ticker that fell out of evaluation two months ago can still have its old close corroborated by the archive, and would then alarm every day forever. `D == L` says the system has nothing newer than this ticker has, so whatever staleness remains is the CLOCK's; `D < L` says the system moved on without this ticker, so it is the TICKER's. (An earlier draft used `count_session_recorded_closes(S) == 0` for this. That was wrong and Codex found it: `recorded(S) == 0` holds during EVERY daily post-close window, so a fallen-out ticker was authorized seven hours a day.)

| sub-rung | condition (all within rung B) | may ALARM |
|---|---|---|
| **B-conflict** | `W(S) is not None` (so rung A failed on VALUE) | **NO** (Codex R4 MAJOR 2) |
| **B-unavailable** | the archive read RAISED (`status == 'unavailable'`) | **NO** (Codex R5 MAJOR 2) |
| **B-continuity** | `status == 'ok'` AND `D < S` AND `round(W(D),2) == round(P,2)` AND `L` readable AND `D == L` | **YES** (labelled with its exact, PROVEN staleness) |
| **B-undated** | `status == 'ok'` AND `W(D)` is absent or disagrees | **NO** — we do not know when this price is from |
| **B-persistent** | `status == 'ok'`, `W(D)` corroborates, but `D < L` | **NO** — the system has newer closes than this ticker does |
| **B-unknown** | `L` could not be read | **NO** |

*(`status == 'ok'` means the archive READ COMPLETED. Within rung B, `W(S) is None` holds in every row except B-conflict — it is what makes them rung B — so it is not restated per row. The vocabulary is `{ok, unavailable}`; an earlier draft carried a third `missing` value, which the codex-auto-review caught as a stale internal term after the status and the map were separated.)*

**Why B-conflict must not alarm (Codex R4 MAJOR 2).** There the persisted close is not merely un-dated — it is *contradicted by dated evidence the panel is holding*. Raising a regime alarm from the older, contradicted number against an order that is correct for the dated bar would be a false alarm generated by our own inconsistency, and it can repeat daily whenever the archive refreshes ahead of the candidate rows. B-conflict is INERT for the regime and renders its own labelled note naming both numbers — strictly more useful than either an alarm or generic inert wording, because it reports a real data inconsistency in the operator's own system.

**Why `status` must be carried separately from "no witness" (Codex R5 MAJOR 2).** `load_bars` swallows every archive exception and returns `[]` (`reader.py:182`), so "the archive says there is no such bar" and "the archive could not be read" collapse into the same absence. Authorizing an alarm in the second case would be asserting from a stale price precisely when we could not check the one thing that would have settled it. The reader therefore carries a per-ticker `archive_status` in `{ok, unavailable}` alongside the close map: `unavailable` = the read RAISED; `ok` = it completed (a legacy-only Shape-A ticker or a genuinely empty archive is `ok` with an empty map, which is a FACT about the data rather than our ignorance of it).

**B-undated, B-persistent, B-unavailable and B-unknown all fall through to the SHIPPED rung-C classifier branches unchanged** (`permanent` / `unknown`), whose wording already fits them.

**An unreadable `L` withdraws ALARM AUTHORITY ONLY; it does not change the label (Codex R7 MINOR).** The two reads are independent and answer different questions: `latest_recorded_close_stamp` gates the alarm, `count_session_recorded_closes` selects the shipped `pending`-vs-`permanent` wording. If `L` fails but the count succeeds, the latch is inert (no alarm) and still renders whichever shipped branch the count supports — which remains a TRUE statement about the operator's data, so suppressing it in favour of a bare "unknown" would tell him less than we know. Only a failure of the COUNT read routes to the shipped `unknown` branch, exactly as today.

**B-conflict and rung F get new labelled branches**: `value_conflict` (warning tone, naming the recorded close, the archive close dated `S`, and that no mandate form will be picked while two sources disagree — with two wordings per Codex R5 MINOR: `D == S` reads as *two dated sources disagree about the same session*, `D < S` reads as *the archive holds a newer close for `S` than the recorded one*) and `future_stamp` (warning tone, naming the stamp and the derivation session).

**Read as one rule:** *alarm only from a price whose date we have PROVEN, when that date is genuinely earlier than the page's session, when the archive KNOWS it has nothing for that session, and when the whole system is no fresher than this ticker.*

**Worked check against the production shapes** (`S` = derivation session):

| shape | `D` | `L` | `W(D)` | `W(S)` | result |
|---|---|---|---|---|---|
| the ~7-hour window, healthy system | `S-1` | `S-1` | matches `P` | None | **B-continuity, alarm authorized** (the arc's purpose) |
| a ticker LAGGED inside the latest cohort, in the window | `S-1` | `S-1` | **disagrees** (its true close is `S-2`) | None | **B-undated, inert** (the R6 MAJOR hole, closed) |
| a ticker that fell out of evaluation, in the window | `2026-06-01` | `S-1` | matches | None | `D < L` -> **B-persistent, inert** (the R5 MAJOR-1 hole, closed) |
| the same ticker, after the nightly | `2026-06-01` | `S` | matches | None | `D < L` -> **B-persistent, inert** |
| a multi-day uniform outage (the T5 fixture) | `S-4` | `S-4` | matches | None | **B-continuity, alarm authorized** |
| Route B: lagging ticker, its own bar has since landed | `S` | `S` | n/a | disagrees | **B-conflict, inert** |
| healthy, post-nightly | `S` | `S` | n/a | matches | **rung A** |

**This is the principled answer to OQ-1's staleness bound**, and it beats both options originally offered RD: it is not unbounded, and it is not an invented constant. Two conditions, each traceable to a defect Codex actually constructed.


### B.3 What "may not assert a MATCH" concretely gates

Three consequences, all in `build_latch_orders_vm`:

1. **`form_check_ran_count`** (the page-level scoped all-clear, RD ruling 2026-07-28) counts **rung A only**. NO rung-B latch, of ANY sub-rung, and no rung-F or rung-C latch, ever contributes to an all-clear.
2. **The leg-expectation relaxation** is rung-A only. Today `expected_type == PULLBACK` sets `stop_leg_expected = False`, which EXCUSES an absent stop leg — an assertion that the order's shape is right. Under rung B (every sub-rung), rung F and rung C that relaxation is withheld and the code falls back to the shipped unknown-regime rule (`stop_leg_expected = join.order_stop_agrees is not None` — judge a stop the order actually carries, demand none it does not).
3. **Every disagreement line derived from a B-continuity regime carries an uncorroborated-provenance suffix** naming the run stamp and the archive's newest bar, so the operator can weigh it. An unlabelled stale-derived alarm would be a claim the data does not support in the other direction.
4. **Every non-authorized state — B-conflict, B-unavailable, B-undated, B-persistent, B-unknown, and rung F — feeds `expected_type = None` into every downstream consumer**, exactly as an absent close does today — so `mandate_shape_mismatch` runs in its shipped unknown-regime mode (it still catches a `TRAILING_STOP_LIMIT` or a `DAY` duration, which are wrong in EVERY regime) and nothing regime-derived is asserted or alarmed.

### B.4 What B-continuity may alarm on: commission, not omission

Within B-continuity the check **may contradict what an order SAYS; it does not demand what an order OMITS.**

- **Commission (alarmed):** the order's own `order_type` contradicts the B-continuity regime — e.g. a `STOP_LIMIT` while the newest close sits at or above the latched pivot (a buy stop below the market, broker-rejectable — the FTRE rejection class). This is a disagreement between two positive statements, and it fires only when a crossing has actually moved the regime or the order was already wrong. It is NOT a daily event, **and §B.2.1 bounds its lifetime to the data outage that produced the staleness.**
- **Omission (not alarmed):** an absent stop leg under a B-continuity `BREAKOUT` regime. Demanding it would flag the operator's situationally-correct stopless pullback LIMIT **every day, for seven hours**, which is precisely the drumbeat-false-RED pattern the shipped code warns about at `swing/web/view_models/latches.py:453-463` and the Phase-19 saga made expensive. The cap leg is still required in every regime (unchanged) — that is an omission check, but it already fires in the unknown regime today, so it adds no new noise.

This line is a NOISE CALIBRATION, not a logical necessity, and it is flagged to RD as **OQ-2** (§E).

### B.5 The rendering, and why the daily state must stay neutral

A **B-continuity** latch that finds NOTHING renders a **neutral status note** (severity `stale_regime`, reusing the existing `.latch-form-check-pending` CSS token — no new theme token, so the CSS no-raw-hex/token contract test is untouched), saying that the form check ran from an uncorroborated close dated `X` and that no all-clear is asserted for it. It must NOT be alarm-shaped: it renders on every live latch for ~7 hours of every trading day, and a warning-shaped label on a daily state trains the dismissal reflex. **It REPLACES the shipped `pending` note for that latch** (the two describe the same moment; emitting both would double-report it).

A **B-continuity** latch that finds a mismatch renders in the existing `disagreements` block (warning tone) with the provenance suffix, AND still emits its neutral note (the note says what was checked and from what; the disagreement says what was found). That block is a FINDING, so it already withholds every form of all-clear.

**B-persistent / B-unknown and rung C all route to the SHIPPED `_build_form_check_notes` classifier unchanged**, producing the shipped `permanent` / `unknown` / `pending` branches byte-for-byte. The only population that moves is the one the arc is for: a latch with a usable close during a system-wide data gap, which today renders `pending` (inert) and after the fix renders `stale_regime` (alarm-authorized).

**Exactly one shared list, so the wiring cannot fork (Codex R3 MINOR).** `form_check_skipped` keeps its shipped name and shape but its element becomes `(ticker, quote, tail, provenance)`; `_build_form_check_notes` receives the `CloseProvenance` and selects the branch. A latch is appended to it whenever `assertive` is False — i.e. for EVERY non-rung-A live latch, B-continuity included. There is no second list.

### B.6 The page-level sentence

`LatchOrdersFragmentVM.all_clear_note` gains a third term. Counts:

- `form_check_ran_count` — rung A (the field keeps its shipped name so the shipped tests do not churn; its meaning tightens to "asserted").
- `form_check_stale_count` — **B-continuity only** (new field, default 0). B-persistent and B-unknown are NOT counted here — they are indistinguishable from rung C in what the page can claim, and counting them separately would imply a check ran that did not.
- `len(mandate_form_check_skipped)` — every non-rung-A latch (so B-continuity appears in BOTH this list and `form_check_stale_count`; the list is the per-latch labels, the count is the sentence's scope term).

Sentences (display-ready, template holds no logic). Let `N = form_check_ran_count`, `M = form_check_stale_count`, `K = len(mandate_form_check_skipped) - M` (the genuinely-unchecked):

- `M == 0 and K == 0` -> `"Broker orders agree with the live latches. No alarms."` (**byte-identical to today** — the no-regression sentence.)
- `M == 0, K > 0` -> `"No alarms among the N latches form-checked. K not form-checked - see the labels below."` (**byte-identical to today** — the shipped scoped sentence, which several shipped tests assert verbatim.)
- `M > 0` -> **lead with the reduction, not the reassurance** (Codex R7 MINOR: a sentence beginning "No alarms" is skimmable as a page-level all-clear before the qualifying clause is read, on the one surface whose statements must survive being believed): `"M latches checked from an uncorroborated close - no all-clear is asserted for those. K not form-checked - see the labels below. No alarms among the N latches form-checked."`, with the `K` clause omitted when `K == 0`, and singular/plural handled as today.

---

## C. What this arc does NOT change (the 21-A invariants, stated so the review can check them)

- The number the check judges is still `candidates.close` via `load_last_closes` — shown equals judged (`view_models/latches.py:793-799`).
- `expected_mandate_order_type` and `mandate_shape_mismatch` (`swing/latches/orders.py:100`, `:134`) keep their signatures and semantics. The ladder decides what the CALLER may do with the answer.
- The two named alarms (`LATCH_ARMED_NO_RESTING_ORDER`, `ORDER_RESTING_LATCH_CLEARED`) do not consume the regime price at all — untouched.
- The multiplicity guard, the indeterminate short-circuit, the stray-order sweep, the cap-leg requirement, the GTC duration check, the stale-render-anchor suppression, the A6 degrade ladder, `count_session_recorded_closes` and its rung-C classifier: all unchanged.
- The panel GET still writes nothing; the fragment still POSTs.

---

## D. The deliberate reversal (RD must ratify this explicitly)

**This arc REVERSES a shipped, Codex-hardened, RD-ruled 21-A behavior — in one direction only.**

21-A shipped `test_a_stale_close_does_not_get_to_choose_the_mandate_regime` (`tests/web/test_routes/test_latches_orders_fragment.py:964`), whose rule is: *only a close stamped on the derivation session may pick a form; anything older leaves the regime UNKNOWN.* That was a single knob doing two jobs — it gated the ALARM direction and the ASSERT direction together, and it gated both on a stamp that is only an upper bound.

21-G splits the knob:

| direction | 21-A | 21-G |
|---|---|---|
| may a stale close raise a mismatch alarm? | **no** | **yes when the staleness is SYSTEM-WIDE** (§B.2.1), labelled with its exact age |
| may a stamp-dated close assert a match? | **yes** (the stamp was trusted) | **no** (the stamp is an upper bound; corroboration required) |

So the assert direction is **tightened**, not merely preserved, and the alarm direction is **loosened** exactly as far as RD's rule licenses. That test must be RE-EXPRESSED (§H.T5), not deleted: its subject becomes "a stale close does not get to assert a MATCH", and its stale-derived mismatch becomes an expected, labelled output.

**This is the one item that cannot be settled by an implementer.** It goes to RD at the plan-stage gate as the headline.

---

## E. Open questions for RD's plan-stage gate

**OQ-1 — the staleness bound on the alarm rung — RESOLVED IN THE PLAN, but RD should ratify the principle.** RD's rule states no bound, and the plan's first draft implemented none. Codex round 3 constructed the failure that forced one: a latched ticker that has fallen out of evaluation has a **permanently** stale close, so an unbounded alarm fires on the operator's correct order every review, forever, with no self-correction — the drumbeat class. Two further rounds then showed that a single bound is not enough. §B.2.1 now bounds the alarm rung with TWO principles rather than a constant: **(1) the price's date must be PROVEN, not inferred from a stamp** (`dated_at_stamp` — corroboration at the close's own stamp; without this the arc re-commits gotcha #30 inside its own fix, in the alarm direction), and **(2) the staleness must be the clock's fault, not the ticker's** (`D == L`, via the new `latest_recorded_close_stamp`). System-wide gap over a proven-dated price -> alarm authorized and self-limiting; anything else -> no regime-derived alarm, and a labelled inert note renders instead. (`count_session_recorded_closes` is NOT the gate — it continues to drive only the shipped `pending`-vs-`permanent` label, exactly as in 21-A.) **RD's ruling to confirm: is "the staleness must be system-wide" the right reading of his rule's scope?** The plan's position is that his rule *permits* an alarm from a stale close and does not *require* one, and that withholding is never a false all-clear while the reduction is labelled.

**OQ-2 — the commission-vs-omission line (§B.4).** Under rung B the plan alarms on a contradicting order TYPE but does not demand an absent stop leg. This is a noise calibration, not a logical consequence of RD's rule; the alternative (demand the leg too) is strictly more faithful to "may raise a mismatch alarm" and strictly noisier — it would flag the operator's correct stopless pullback LIMIT for seven hours of every trading day whenever the newest close is below the pivot. **Plan implements the calibrated line; RD may overrule.**

**OQ-3 — the card's `price_asof` label is the same shape, one level down, and is NOT fixed here.** `_build_row` (`view_models/latches.py:249`) renders `price_asof = quote[1]` — the run stamp — as the price's as-of date, and `_zone_position` computes IN ZONE / OUT OF ZONE from that price. It already renders `price_source="last_close"` and `price_is_stale=True` unconditionally, so it does not claim freshness the way the check did; but it does present a run-level stamp as a per-row date. The survey reports it (§S, hit 3); the plan does NOT fix it, because the brief scopes 21-G to the shape-check path and says anything beyond it comes back for scoping. It is named here because it is a one-string change on the same surface in the same cycle, and RD may fold it in at the gate rather than pay a second dispatch for it.

---

## F. File structure

**Create**

| path | responsibility |
|---|---|
| `docs/data-asof-date-consumer-survey-21g.md` | the §S survey, as a standalone citable artifact (committed) |

**Modify**

| path | change |
|---|---|
| `swing/latches/constants.py` | `CLOSE_PROVENANCE_CORROBORATED` / `_UNCORROBORATED` / `_FUTURE_STAMP` / `_ABSENT` + the `CLOSE_PROVENANCES` frozenset, and `ARCHIVE_STATUS_OK` / `_UNAVAILABLE` + the `ARCHIVE_STATUSES` frozenset (the domain owner, single declaration — the 21-A `LATCH_STATES` precedent; Codex R7 MINOR aligned this roster with §B.2 and Task 1) |
| `swing/latches/models.py` | `LatchDerivation` gains `archive_closes: Mapping[str, Mapping[date, float]]` and `archive_status: Mapping[str, str]` (per ticker, in `{ok, unavailable}`), both defaulting empty. **`Latch` is UNCHANGED.** |
| `swing/latches/service.py` | `derive_latches` accepts `bar_status_by_ticker` and passes both maps through onto `LatchDerivation`; the fold, `_eligible_bars` and `_finalize` are UNCHANGED |
| `swing/latches/reader.py` | (a) `build_latch_derivation` widens the bar LOAD start to `min(earliest_anchor, derivation_session)` and drops the `start > derivation_session -> []` short-circuit (`reader.py:389`); (b) NEW `load_bars_with_status(...) -> tuple[list[DailyBar], str]` returning `unavailable` on the except branch and `ok` otherwise, with the shipped `load_bars` kept as a thin delegate so its signature and its tests are untouched; (c) NEW `latest_recorded_close_stamp(conn) -> str | None` (one aggregate SELECT, the SAME usability predicate as `load_last_closes` / `count_session_recorded_closes`); (d) docstring: `load_last_closes` states that the returned session is the run STAMP (an upper bound), not the close's own date, and points at the classifier |
| `swing/latches/orders.py` | `CloseProvenance` frozen dataclass + `classify_close_provenance(...)` — PURE, no I/O |
| `swing/web/view_models/latches.py` | the ladder wiring: assert-gating of `stop_leg_expected` + `form_check_ran_count`, the provenance suffix on rung-B disagreements, the `stale_regime` note branch, `form_check_stale_count`, the three-term `all_clear_note` |
| `swing/web/templates/partials/latch_orders.html.j2` | the neutral tone extends to `stale_regime` (`severity in ('pending','stale_regime')`) |
| `tests/latches/test_orders.py` | the pure classifier truth table |
| `tests/latches/test_service_terminal.py` | the `Latch`-is-unchanged lock + the `LatchDerivation` map defaults |
| `tests/latches/test_reader.py` | the widened LOAD window, the fresh-latch witness, and the invalidation-walk lock |
| `tests/web/test_routes/test_latches_orders_fragment.py` | the discriminating tests (§H) + the fixture helper that writes the corroborating archive bar |

**NOT modified (and the review should verify it):** `swing/evaluation/**`, `swing/data/**`, `swing/trades/**`, any migration, `swing/latches/identity.py`.

---

## G. Tasks

### Task 1: the provenance vocabulary

- [ ] **RED** — in a new `tests/latches/test_close_provenance.py`, assert `CLOSE_PROVENANCES == frozenset({"corroborated","uncorroborated","future_stamp","absent"})` and `ARCHIVE_STATUSES == frozenset({"ok","unavailable"})`, and that the constants are importable from `swing.latches.constants`. In `tests/latches/test_service_terminal.py`, assert `LatchDerivation` defaults both new maps to empty and that a `Latch` built by the shipped fold is field-for-field unchanged (the no-churn lock).
- [ ] **GREEN** — add the constants to `swing/latches/constants.py` (zero-import pure-constants module; do NOT re-declare anywhere else) and the two defaulted maps to `LatchDerivation` in `swing/latches/models.py`.
- [ ] Commit: `feat(latches): Task 1 - close-provenance vocabulary + the LatchDerivation archive maps`

### Task 2: the derivation surfaces the per-ticker archive map, decoupled from the walk

- [ ] **RED** — three service/reader tests:
  1. bars at `S-2, S-1, S, S+1` with DISTINCT closes and `anchor = S-2` -> `derivation.archive_closes['T']` contains `S-2, S-1, S` AND the `S+1` look-ahead bar the archive legitimately holds is EXCLUDED (the load `end` is `S`);
  2. **the fresh-latch case (Codex R4 MAJOR 1):** `anchor = S+1` (a latch fired tonight for tomorrow) with an archive bar dated `S` -> `derivation.archive_closes['T'][S]` is present **while** that latch reports `bars_available is False` and `bars_through is None`. An implementation that leaves the `reader.py:389` short-circuit fails the first half; one that widens `_eligible_bars` instead of the LOAD window fails the second half;
  3. **the invalidation-walk lock:** with the widened load window, a latch whose anchor is after `derivation_session` still reports `bars_available is False`, and a normal latch's invalidation session is unchanged from the shipped value;
  4. **the status lock (Codex R5 MAJOR 2):** an archive read that RAISES yields `archive_status['T'] == "unavailable"` with an empty close map, while a readable-but-empty archive yields `"ok"` with an empty close map. An implementation that infers status from an empty map cannot pass both.
- [ ] **GREEN** — `swing/latches/reader.py`: add `load_bars_with_status` (the shipped `load_bars` becomes a one-line delegate, so its signature and tests are untouched) returning `"unavailable"` on the except branch and `"ok"` otherwise; in `build_latch_derivation` set `start = min(start, derivation_session)` and drop the `start > derivation_session -> []` short-circuit (keep the `start is None -> []` guard, status `"ok"`); build `archive_closes[ticker] = {b.session: b.close for b in bars}` and pass both maps into `derive_latches`, which sets them on `LatchDerivation`. **`_eligible_bars` and `_finalize` are not touched.**
- [ ] Commit: `fix(latches): Task 2 - surface the per-ticker archive close map + read status, decoupled from the invalidation eligible set`

### Task 3: the PURE classifier

- [ ] **RED** — `tests/latches/test_close_provenance.py`, the full truth table (§H.T1). Include: exact 2dp tolerance at BOTH `W(S)` and `W(D)` (a 0.004 difference corroborates, a 0.006 difference does not); a mismatching `W(S)` -> `uncorroborated` with `has_dated_conflict`; an absent `W(S)` -> `uncorroborated`; a stamp AFTER `S`, and an unparseable/empty stamp, -> `future_stamp` even when `W(S)` matches (rung F pre-empts rung A); no close -> `absent`; a non-finite / non-numeric / `bool` persisted close -> `absent`; `dated_at_stamp` True only when `W(D)` matches to the cent; `archive_unavailable` driven by the status, never by an empty map.
- [ ] **GREEN** — add to `swing/latches/orders.py`:

```python
@dataclass(frozen=True)
class CloseProvenance:
    """What the panel may CLAIM about the regime close (gotcha #30)."""
    price: float | None
    provenance: str                    # one of CLOSE_PROVENANCES
    stamp_session: str | None          # the run stamp: an UPPER BOUND on the close date
    stamp_date: date | None            # the parsed stamp, or None when unparseable
    session_close: float | None        # W(S): the archive close dated exactly S
    stamp_session_close: float | None  # W(D): the archive close dated exactly D
    archive_status: str                # one of ARCHIVE_STATUSES
    bars_through: date | None          # display/label context ONLY, never the witness
    derivation_session: date

    @property
    def may_assert(self) -> bool:
        return self.provenance == CLOSE_PROVENANCE_CORROBORATED

    @property
    def has_dated_conflict(self) -> bool:
        """B-conflict: a bar DATED S exists and disagrees with the recorded close."""
        return (self.provenance == CLOSE_PROVENANCE_UNCORROBORATED
                and self.session_close is not None)

    @property
    def archive_unavailable(self) -> bool:
        """B-unavailable: the archive read RAISED, so the absence of a witness
        is our ignorance rather than a fact about the data."""
        return self.archive_status == ARCHIVE_STATUS_UNAVAILABLE

    @property
    def dated_at_stamp(self) -> bool:
        """Condition (1): the close is corroborated AT ITS OWN STAMP, so its date
        is KNOWN rather than assumed. This is the rung-A test applied at D."""
        return (self.price is not None and self.stamp_session_close is not None
                and round(self.stamp_session_close, _PRICE_DP)
                == round(self.price, _PRICE_DP))


def classify_close_provenance(*, quote, derivation_session, bars_through,
                              archive_closes, archive_status) -> CloseProvenance:
    """`archive_closes` is that ticker's {session -> close} map (possibly empty)."""
```

  `quote` is the shipped `(close, stamp_iso)` tuple or `None`. The function performs NO I/O and NO exception-swallowing beyond the numeric coercion the shipped `expected_mandate_order_type` already does.
- [ ] Commit: `feat(latches): Task 3 - classify_close_provenance, the pure provenance ladder`

### Task 4: wire the ladder into the fragment

- [ ] **RED** — the discriminating fragment tests §H.T2, §H.T2b and §H.T4 (both halves). Run them and SEE each one fail against the shipped code, recording the pre-fix output in the failure. **§H.T3 is NOT in the RED set** — it is the regression lock and passes pre-fix by design (§H.T3 states what it does discriminate against).
- [ ] **GREEN** — in `build_latch_orders_vm`:
  - compute `prov = classify_close_provenance(quote=quote, derivation_session=derivation.derivation_session, bars_through=lat.bars_through, archive_closes=derivation.archive_closes.get(ticker, {}), archive_status=derivation.archive_status.get(ticker, ARCHIVE_STATUS_OK))`;
  - `expected_type = expected_mandate_order_type(latched_pivot=lat.latched_pivot, last_close=prov.price)`;
  - `assertive = prov.may_assert and expected_type is not None`;
  - leg rule: `stop_leg_expected = False` if `assertive and expected_type == PULLBACK`; `True` if `assertive and expected_type == BREAKOUT`; else `join.order_stop_agrees is not None`;
  - **the B-continuity gate**: `latest = latest_recorded_close_stamp(conn)` and `recorded = count_session_recorded_closes(conn, derivation_session)` are each read ONCE per fragment build (not per latch) and ONLY when at least one live latch is non-rung-A — same call site discipline as today; both are wrapped in the A6 try/except and degrade to `None`. Then:

```python
alarm_authorized = (
    prov.provenance == CLOSE_PROVENANCE_UNCORROBORATED
    and not prov.has_dated_conflict          # B-conflict
    and not prov.archive_unavailable         # B-unavailable
    and prov.dated_at_stamp                  # (1) we KNOW when this price is from
    and prov.stamp_date is not None
    and prov.stamp_date < derivation.derivation_session
    and latest is not None
    and prov.stamp_session == latest         # (2) the gap is the system's, not the ticker's
)
```
 When `alarm_authorized` is False and `assertive` is False, `regime_price = None` is fed downstream so every regime-derived consumer behaves exactly as it does today for an absent close;
  - `form_check_ran_count += 1` only when `assertive`; `form_check_stale_count += 1` only when `alarm_authorized`; EVERY non-assertive latch appends `(ticker, quote, tail, prov)` to the single `form_check_skipped` list (§B.5 — there is no second list);
  - `mandate_shape_mismatch(o, latched_pivot=..., last_close=<regime_price>)` — under `alarm_authorized` that price is `prov.price` and every line it produces gets `_uncorroborated_suffix(prov)` appended; the same suffix is appended to any leg-disagreement line produced in that state. ONE helper, so the wording cannot drift. Under B-persistent / B-unknown / rung C the price is `None` and the shipped unknown-regime behaviour is reproduced exactly;
  - **the note reason is computed ONCE, in the loop, and PASSED (Codex R6 MINOR).** The shared `form_check_skipped` element becomes `(ticker, quote, tail, prov, note_reason)` where `note_reason` is selected in the loop as `future_stamp` -> `value_conflict` -> `unavailable` -> `stale_regime` (iff `alarm_authorized`) -> `None` (defer to the shipped four). `_build_form_check_notes` then only FORMATS — it makes no classification decision of its own for the new branches, so the counts and the labels cannot drift apart and there is no second hidden classifier. A test asserts `form_check_stale_count` equals the number of rendered `stale_regime` notes on a mixed page;
  - `all_clear_note` gains the third term (§B.6).
- [ ] Commit: `fix(latches): Task 4 - the close-provenance asymmetry (alarm from a stale close, never assert a match)`

### Task 5: rendering tone + the re-expressed 21-A tests

- [ ] **RED/GREEN** — template: `{% if note.severity in ('pending', 'stale_regime') %}` for the neutral class (no new CSS token). Re-express `test_a_stale_close_does_not_get_to_choose_the_mandate_regime` per §H.T5 and update `_seed_close_at_the_derivation_session` to write the corroborating Shape-A archive bar (§H.T3) so the 11 shipped call sites keep reaching rung A unchanged.
- [ ] Commit: `test(latches): Task 5 - re-express the 21-A stale-close gate as the split assert/alarm rule`

### Task 6: the survey artifact

- [ ] Write `docs/data-asof-date-consumer-survey-21g.md` from §S (the same content; §S stays in the plan so the plan is self-contained).
- [ ] Commit: `docs(latches): Task 6 - the data_asof_date consumer survey (report-only; nothing beyond the shape check is fixed)`

**Proposed rider, NOT a task (orchestrator/CHARC call):** CLAUDE.md gotcha #30's `Fix:` clause could gain a one-clause pointer to the shipped read-side treatment (the close-provenance ladder) now that "treat the stamp as an UPPER BOUND" has a concrete implementation to cite. Flagged, not done.

---

## H. The tests, with pre-fix / post-fix arithmetic

**Two categories, deliberately separated (Codex R1 MAJOR).** T1, T2, T2b, T4 and T5 are **DISCRIMINATORS**: each fails under the shipped code and passes under the design, and the failing pre-fix value is stated. T3, T3b, T6, T7a/T7b, T8, T9 and T10 are **LOCKS**: they pass under the shipped code too, by design, and their adversary is a wrong POST-fix implementation (T3: rung A made unreachable; T3b: the witness taken from the invalidation eligible set, or fixed by widening that set; T6: a degradation path that raises or over-claims; **T7a+T7b: an alarm gate missing condition (2), freshness parity**; **T4a+T10: an alarm gate missing condition (1), corroboration at the close's own stamp**; T8: the shipped stamp gate dropped without replacement; T9: archive-unavailable inferred from archive-empty). The pairing is deliberate: each condition of the alarm gate has a two-test pair in which one member must alarm and the other must not, so an implementation that drops either condition fails a pair rather than silently passing. Each lock states its adversary in-line. A lock is not a weak discriminator — it defends the direction the discriminators cannot see, and every discriminator above only asserts that something is ABSENT, which is exactly the assertion an over-correcting implementation satisfies trivially.

Shared geometry (REAL, from the live corpus): FTRE, fire at evaluation run 121, `action_session_date = 2026-07-20`, **frozen** `pivot = 18.34`, `initial_stop = 14.88`; `zone_cap = round(18.34 * 1.03, 4) = 18.8902` (renders `18.89`). Frozen clock `NOW = 2026-07-25 12:00` -> `action_session = 2026-07-27`, `derivation_session = 2026-07-24` (all verified on this box). `2026-07-23`, `2026-07-24`, `2026-07-27`, `2026-07-28`, `2026-07-29` are all NYSE sessions.

### T1 — the pure classifier truth table (`tests/latches/test_close_provenance.py`)

`S = 2026-07-24` throughout. `archive` is that ticker's `{session -> close}` map; `status` is `ok` unless stated.

| `quote` | `archive` | `status` | rung | `has_dated_conflict` | `dated_at_stamp` |
|---|---|---|---|---|---|
| `(17.76, '2026-07-24')` | `{07-24: 17.76}` | ok | `corroborated` | False | True |
| `(17.76, '2026-07-24')` | `{07-24: 17.764}` | ok | `corroborated` (2dp) | False | True |
| `(17.76, '2026-07-24')` | `{07-24: 17.766}` | ok | `uncorroborated` | **True** | False |
| `(19.52, '2026-07-24')` | `{07-24: 17.76}` | ok | `uncorroborated` (**Route B**) | **True** | False |
| `(19.52, '2026-07-23')` | `{07-23: 19.52}` | ok | `uncorroborated` | False | **True** (the alarm rung's condition 1) |
| `(19.52, '2026-07-23')` | `{07-23: 18.10}` | ok | `uncorroborated` | False | **False** (the R6 lagged-ticker shape) |
| `(19.52, '2026-07-23')` | `{}` | ok | `uncorroborated` | False | False |
| `(19.52, '2026-07-23')` | `{}` | **unavailable** | `uncorroborated` | False | False (`archive_unavailable` True) |
| `(17.76, '2026-07-27')` | `{07-24: 17.76}` | ok | **`future_stamp`** | — | — (rung F PRE-EMPTS rung A) |
| `(17.76, 'not-a-date')` | `{07-24: 17.76}` | ok | **`future_stamp`** | — | — |
| `(17.76, '')` | `{07-24: 17.76}` | ok | **`future_stamp`** | — | — (the shipped empty-stamp shape, `reader.py:272`) |
| `None` | `{07-24: 17.76}` | ok | `absent` | False | False |
| `(float('nan'), '2026-07-24')` | `{07-24: 17.76}` | ok | `absent` | False | False |
| `(True, '2026-07-24')` | `{07-24: 17.76}` | ok | `absent` | False | False (`bool` is not a price) |

### T2 — **the false all-clear killer** (the load-bearing discriminator)

Seed: run 121 fire (as `_seed_ftre`); run 127 `data_asof_date='2026-07-24'` with `candidates.close = 19.52` for FTRE; Shape-A archive bars `2026-07-23 close 19.52` and `2026-07-24 close 17.76`. That is the real Route-B geometry: FTRE's evaluator fetch reached only 07-23 while another cohort ticker reached 07-24, so the run stamped 07-24 over a 07-23 close.
Resting order: the operator's REAL live FTRE pullback order — `GOOD_TILL_CANCEL` `LIMIT`, limit `18.89`, **no stop leg**.

- **Pre-fix arithmetic:** `quote = (19.52, '2026-07-24')`; `regime_session_iso = '2026-07-24'`; gate passes -> `last_close = 19.52`; `19.52 >= 18.34` -> `PULLBACK` -> `stop_leg_expected = False`; `order_limit_agrees is True`; `legs_disagree = False`; `mandate_shape_mismatch` -> `None` (LIMIT is the expected type); `form_check_ran_count = 1`; `mandate_form_check_skipped = ()` -> the page prints **`"Broker orders agree with the live latches. No alarms."`** — a MATCH asserted from a close the market had already left. (Truth at 07-24: close `17.76 < 18.34`, so the mandate is a STOP_LIMIT and this stopless LIMIT at 18.89 would fill IMMEDIATELY at ~17.76, an unintended entry below the pivot.)
- **Post-fix arithmetic:** `W(S) = 17.76` (a bar DATED `2026-07-24` exists) and `round(17.76,2) != round(19.52,2)` -> **rung B, `has_dated_conflict = True`** -> **B-conflict** -> `alarm_authorized = False` -> the regime price fed downstream is `None`, exactly as an absent close: no type mismatch; `stop_leg_expected = join.order_stop_agrees is not None` -> `False` (no stop carried) -> no leg disagreement; `form_check_ran_count = 0`, `form_check_stale_count = 0`; the latch renders the new **`value_conflict`** note naming both numbers (`19.52` recorded vs `17.76` in the archive bar dated `2026-07-24`).
- **Assertions:** `"Broker orders agree with the live latches. No alarms." not in r.text` (**fails pre-fix** — this is the discriminating assertion); the `value_conflict` headline and both numbers are present; `"No alarms among the 0 latches form-checked. 1 not form-checked" in r.text`.
- **Why the label is better than the alternative (Codex R3 MINOR 2, R4 MAJOR 2):** the shipped `permanent` string renders the STAMP as the close's date, and here BOTH the stamp and the archive bar are dated `2026-07-24` — the disagreement is in the VALUE, not the date, so that string would be actively misleading. The dedicated `value_conflict` branch says the true thing: two dated sources in the operator's own system disagree about the same session, so no mandate form will be picked. That is a genuine data-integrity report he can act on, and it is the only place in the design where the fix produces MORE information than either the pre-fix or the naive post-fix behaviour.

### T2b — Route B does not become an ALARM either (the paired half of T2)

Same seed as T2, but the resting order is a `GOOD_TILL_CANCEL` `STOP_LIMIT` (stop `18.34`, limit `18.89`) — i.e. the order form that the *uncorroborated* close would call wrong.

- **Pre-fix:** the stamp is trusted -> regime `PULLBACK` -> `mandate_shape_mismatch` reports `"order type is STOP_LIMIT, but the last close is AT OR ABOVE the latched pivot"` — an alarm raised **from an uncorroborated close and presented as a proven-regime finding**, and here it is raised against an order that is CORRECT for the `2026-07-24` bar the panel is holding (`17.76 < 18.34` -> BREAKOUT -> a STOP_LIMIT is right).
- **Post-fix:** B-conflict -> `alarm_authorized = False` -> regime price `None` -> **no type mismatch is reported**; the `value_conflict` label renders instead.
- **Assertion:** `"not the mandated order shape" not in r.text` and `"AT OR ABOVE" not in r.text` (**both fail pre-fix**).
- **Why this is the correct outcome and not a lost alarm:** the panel is holding a bar dated `S` that contradicts the recorded close, and the order agrees with THAT bar. Alarming from the contradicted number would be a false alarm manufactured by our own inconsistency, repeatable daily. The rule RD gave *permits* an alarm from a stale close; it does not require one, and withholding it is never a false all-clear so long as the reduction is labelled — which `value_conflict` does, in a warning tone, while naming the inconsistency itself. **Route B's fix is, and always was, the refusal to ASSERT.**

### T3 — **the regression lock** (byte-identical; passes pre-fix AND post-fix, by design)

Seed: run 121 fire; run 127 `data_asof_date='2026-07-24'`, `candidates.close = 17.76`; **and** a Shape-A archive bar `2026-07-24 close 17.76`. Resting order: `GOOD_TILL_CANCEL` `STOP_LIMIT` stop `18.34` limit `18.89` (the shipped `test_a_gtc_stop_limit_at_the_right_prices_IS_an_all_clear` geometry).

- Rung A -> `assertive` -> `17.76 < 18.34` -> `BREAKOUT` -> `stop_leg_expected = True`; stop agrees (18.34), limit agrees (18.89); no shape mismatch; `form_check_ran_count = 1`, `form_check_stale_count = 0`, skipped empty -> **`"Broker orders agree with the live latches. No alarms."`** — the exact shipped string.
- **Implementation note:** `_seed_close_at_the_derivation_session` (11 shipped call sites) is extended to write that corroborating archive bar via a `_write_archive`-style helper (the pattern already exists at `tests/latches/test_reader.py:256`), so every shipped all-clear test keeps reaching rung A with no per-test edits. The bar must be within `[anchor, derivation_session] = [2026-07-20, 2026-07-24]` and on a trading session, or `load_bars` drops it.
- **What T3 discriminates against (Codex R1 MAJOR — stated because it does NOT discriminate against the pre-fix code).** It fails any post-fix implementation in which **rung A is unreachable**, which is this design's own most likely defect and is not hypothetical: (a) the archive map never surfaced on `LatchDerivation` -> `W(S)` always None -> permanent rung B; (b) the corroboration compared at full float precision instead of 2dp -> a `17.759999` parquet round-trip fails equality -> permanent rung B; (c) the ladder wired so `may_assert` is never True. Any of those makes EVERY latch rung B forever, permanently kills the affirmative all-clear, and would otherwise ship green because every discriminator above only asserts that an all-clear is ABSENT. **The eleven shipped all-clear tests inherit that same protection through the shared fixture helper.**

### T3b — the FRESH-LATCH reachability lock (Codex R4 MAJOR 1)

The case T3 cannot see, because T3's anchor (`2026-07-20`) precedes its derivation session. Seed a latch fired for the CURRENT action session: `evaluation_runs.action_session_date = 2026-07-27` (== `action_session_for_run(NOW)`), so `anchor = 2026-07-27 > derivation_session = 2026-07-24`; `candidates.close = 17.76` stamped `2026-07-24`; a Shape-A archive bar `2026-07-24 close 17.76`. Resting order: `GOOD_TILL_CANCEL` `STOP_LIMIT` at the frozen pivot / cap.

- **The defect this forbids:** taking the witness from `_eligible_bars` (or leaving the `reader.py:389` `start > derivation_session -> []` short-circuit in place) leaves the ticker's archive map EMPTY -> `W(S) is None` -> rung B -> **the newest latch in the system, the one the operator is about to act on tonight, can never be corroborated and never prints an affirmative all-clear.**
- **Designed post-fix:** the load window starts at `min(anchor, derivation_session) = 2026-07-24`, the `S` bar is loaded, `W(S) = 17.76 == P` -> rung A -> `"Broker orders agree with the live latches. No alarms."`.
- **Paired assertion in the SAME test (the invalidation-walk lock):** `bars_available is False` and the rendered card still shows the shipped `invalidation NOT evaluated - no bars` text — proving the widened LOAD did not widen the ELIGIBLE set. An implementation that "fixes" reachability by widening `_eligible_bars` would silently let a pre-anchor bar invalidate a mandate that did not yet exist, which is RD constraint 6 territory; this assertion is what stops it.

### T4 — the ~7-hour window (both halves)

Frozen clock `NOW = 2026-07-28 12:00` -> `action_session = 2026-07-29`, `derivation_session = 2026-07-28`. Nothing is recorded for 07-28 (`count_session_recorded_closes(2026-07-28) == 0`), which is the real post-close state. Newest recorded close: run 127 `data_asof_date = '2026-07-27'`, `candidates.close = 19.52` (above the pivot). Shape-A archive bars through `2026-07-27 close 19.52`.

- **T4a (a true finding survives the window).** Resting order: `GOOD_TILL_CANCEL` `STOP_LIMIT` stop `18.34` limit `18.89`.
  - Pre-fix: `quote[1] = '2026-07-27' != '2026-07-28'` -> `last_close = None` -> regime UNKNOWN -> no shape mismatch; `recorded == 0` -> `pending`; `form_check_ran_count = 0` -> the page prints `"No alarms among the 0 latches form-checked. 1 not form-checked - see the labels below."` — a scoped all-clear over ZERO checking, with a real wrong-form order resting at the broker.
  - Post-fix: rung B from `19.52` -> `PULLBACK` -> a labelled type mismatch fires; the disagreements block is non-empty so EVERY form of all-clear is withheld.
  - Assertions: `"not the mandated order shape" in r.text` and `"No alarms" not in r.text` (**both fail pre-fix**), and the suffix names `2026-07-27` as the close date the reading came from.
- **T4b (never an all-clear).** Same seed, resting order = the correct stopless `GOOD_TILL_CANCEL` `LIMIT` at `18.89`.
  - Post-fix: B-continuity, no mismatch -> a NEUTRAL `stale_regime` note, and `"Broker orders agree with the live latches. No alarms."` is **absent**. Also assert the note renders with the neutral class, NOT `latch-alarm` (the anti-drumbeat lock).

**Both conditions of the alarm gate are satisfied and each is stated:** (1) the archive holds a `2026-07-27` bar whose close IS `19.52`, so `dated_at_stamp` is True — the price's date is PROVEN, not assumed — and `D = 2026-07-27 < S = 2026-07-28`; (2) `L = 2026-07-27 == D`, so the system is no fresher than this ticker. The archive read succeeds and holds no `2026-07-28` bar (`status == "ok"`, `W(S) is None`). **T4a is the arc's alarm-side discriminator; there is no other.**

### T7 — the sticky-false-RED lock (Codex R3 MAJOR)

The population Codex constructed: a latched ticker that has fallen OUT of evaluation, so its close is permanently stale and sits on the far side of the pivot from market truth, while the operator's order is CORRECT for market truth.

**T7a (post-nightly).** Seed: run 121 FTRE fire; a run stamped `2026-07-24` carrying a usable close for **a different ticker only** (so `L = 2026-07-24` and `recorded(2026-07-24) = 1`), and FTRE's newest usable close from `2026-07-20` at `19.52` (above the pivot). Resting order: the correct-for-truth `GOOD_TILL_CANCEL` `STOP_LIMIT` at `18.34` / `18.89`.

- **Naive post-fix (unbounded rung-B alarm) — what this forbids:** `PULLBACK` from the 07-20 close -> `"not the mandated order shape"` fires, and fires again on every review for as long as the ticker stays off the screen.
- **Designed post-fix:** `D = 2026-07-20 < L = 2026-07-24` -> B-persistent -> no regime-derived alarm; the shipped `permanent` warning renders.
- **Assertions:** `"not the mandated order shape" not in r.text`; `"MANDATE FORM CHECK INERT FOR THIS LATCH" in r.text`; `"Broker orders agree with the live latches" not in r.text`.

**T7b (the SAME latch inside the daily window) — the Codex R5 MAJOR-1 lock.** Identical seed, clock moved to `2026-07-28 12:00` so `S = 2026-07-28` and `count_session_recorded_closes(2026-07-28) == 0`.

- **What this forbids:** the FIRST version of the B-continuity gate keyed on `recorded(S) == 0`, which is TRUE here — so the fallen-out ticker would have been alarm-authorized on every post-close window, seven hours a day, forever. T7a alone cannot see this: it runs at a clock where `recorded(S) > 0`.
- **Designed post-fix:** `L = 2026-07-24` (the newest usable recorded close anywhere) and `D = 2026-07-20`, so `D < L` -> B-persistent -> inert.
- **Assertions:** identical to T7a. **The two together are the drumbeat lock**; either alone is defeated by an implementation that passes the other.

- **Discriminates against:** the naive unbounded-alarm implementations of this very design (both pass pre-fix, so they are DESIGN locks rather than pre/post discriminators — the same category as T3, and stated as such).

### T8 — the future-stamp lock (Codex R5 MAJOR 3)

Seed: run 121 FTRE fire; a close `17.76` stamped `2026-07-27` — i.e. AFTER the fragment's derivation session `2026-07-24`, the shape the fragment reaches whenever `load_last_closes` returns a globally-newer close than the posted render anchor describes. Archive bar at `2026-07-24` = `17.76` (so `W(S)` MATCHES and rung A would otherwise fire). Resting order: a `GOOD_TILL_CANCEL` `STOP_LIMIT` at `18.34` / `18.89` — chosen so the naive path ends in an ALL-CLEAR, not an alarm (Codex R6 MINOR corrected the earlier prose, which used a stopless LIMIT and would have produced a mismatch instead).

- **What this forbids:** an implementation that drops the shipped stamp gate without replacing it. Rung A would fire from the corroborating bar, `17.76 < 18.34` -> BREAKOUT -> both legs agree -> the page prints **`"Broker orders agree with the live latches. No alarms."`** — an affirmative all-clear asserted from a price belonging to a later moment than the page describes, breaking the coherent-moment invariant that the render-anchor suppression exists to protect.
- **Designed post-fix:** rung F pre-empts — neither assert nor alarm; the `future_stamp` note names the stamp `2026-07-27` and the derivation session `2026-07-24`.
- **Assertions:** `"Broker orders agree with the live latches" not in r.text`; the `future_stamp` note names both dates; `"not the mandated order shape" not in r.text`.

### T9 — the unreadable-witness lock (Codex R5 MAJOR 2)

Seed: the T4a 7-hour-window geometry (`S = 2026-07-28`, `D = L = 2026-07-27`, close `19.52` above the pivot, resting `GOOD_TILL_CANCEL` `STOP_LIMIT`), but the archive read for FTRE RAISES (monkeypatch `resolve_ohlcv_window`, or plant an unreadable parquet).

- **What this forbids:** inferring the archive status from an EMPTY close map. Under that inference this is indistinguishable from T4a and the type mismatch would fire — asserting from a stale price at exactly the moment we could not check the thing that would have settled it.
- **Designed post-fix:** `status == "unavailable"` -> B-unavailable -> inert; the shipped `unknown`-branch wording renders.
- **Assertions:** `"not the mandated order shape" not in r.text`; `"MANDATE FORM CHECK NOT RUN" in r.text`; no all-clear of any form; HTTP 200 (A6).
- **Paired with T4a**, which must still alarm: the two differ ONLY in the archive read's outcome.

### T10 — the lagged-inside-the-latest-cohort lock (Codex R6 MAJOR)

**The arc's own defect, in the alarm direction.** Seed the T4a 7-hour-window geometry EXCEPT that FTRE lagged inside the latest cohort: `S = 2026-07-28`; `L = D = 2026-07-27` (the run stamp says 07-27 for everybody); FTRE's persisted close `19.52` is actually its `2026-07-24` bar; the archive holds `2026-07-24 = 19.52` **and** `2026-07-27 = 17.10` (FTRE's real 07-27 close, which the evaluator never saw). Resting order: a `GOOD_TILL_CANCEL` `STOP_LIMIT` at `18.34` / `18.89` — CORRECT for the real 07-27 close (`17.10 < 18.34` -> BREAKOUT).

- **What this forbids:** the freshness-parity gate ALONE. `D == L == 2026-07-27` and `W(S) is None`, so a gate testing only stamp parity authorizes the alarm, computes `PULLBACK` from `19.52`, and reports the operator's CORRECT stop-limit as the wrong shape — daily, for as long as the ticker keeps lagging. That is gotcha #30 committed inside the fix for gotcha #30: a run-level stamp standing in for a per-row fact, merely relocated from the assert direction to the alarm direction.
- **Designed post-fix:** condition (1) fails — `W(D) = W(2026-07-27) = 17.10 != 19.52`, so `dated_at_stamp` is False -> **B-undated** -> inert; the shipped `permanent`-family label renders.
- **Assertions:** `"not the mandated order shape" not in r.text`; `"AT OR ABOVE" not in r.text`; no all-clear of any form; the label renders.
- **Paired with T4a**, which differs ONLY in that its archive `2026-07-27` bar AGREES with the persisted close. **T4a and T10 together are the condition-(1) lock**; T7a and T7b together are the condition-(2) lock. An implementation carrying only one condition fails one pair.

### T5 — the re-expressed 21-A gate test

`test_a_stale_close_does_not_get_to_choose_the_mandate_regime` (four-session-stale close 19.52 stamped 2026-07-20, derivation session 2026-07-24, `GOOD_TILL_CANCEL` `STOP_LIMIT`) is re-expressed as **`test_a_stale_close_may_alarm_but_may_not_assert_a_match`**.

**Verified arithmetic for the B-continuity gate in this fixture:** the shipped seeds are run 121 (stamped `2026-07-17`) and run 128 (stamped `2026-07-20`), both carrying usable FTRE closes, so `L = 2026-07-20`; FTRE's own newest close is the run-128 one, `D = 2026-07-20 < S = 2026-07-24`, so condition (2) `D == L` holds. **The re-expressed test must ALSO seed a `2026-07-20` archive bar at `19.52`** so condition (1) `dated_at_stamp` holds; without it the latch is B-undated and inert, which is the correct behaviour but not the behaviour this test is for. That added seed is the visible cost of condition (1), and it is the right cost: it is the arc refusing to alarm from a price whose date it has not proven. (This is a four-session system-wide gap — a multi-day pipeline outage — not a ticker-specific one, so §B.2.1 authorizes it and the outage bounds its lifetime.) Then:

- it now ASSERTS the shape mismatch IS reported (`"not the mandated order shape" in r.text`, `"AT OR ABOVE" in r.text`) — the inversion of the shipped assertion, and the concrete evidence of the §D reversal;
- it keeps `"Broker orders agree with the live latches" not in r.text` — the half that is preserved and tightened;
- it asserts the uncorroborated suffix names the four-session staleness (`2026-07-20` and `2026-07-24` both present, as the shipped test already required).

### T6 — the A6 regression lock (passes pre-fix and post-fix for the rung-C half, by design)

A latch whose archive read fails (no parquet at all) and whose close read succeeds must land in rung B (B-continuity or B-persistent per the count), never raise, and never print an all-clear. A latch with neither must land in rung C and reproduce the shipped `pending`/`permanent`/`unknown` wording byte-for-byte.

---

## I. Hard stops — checked, none hit

| hard stop | status |
|---|---|
| fix requires changing the WRITE path (per-ticker close provenance at write time) | **NOT hit.** The witness is the on-disk archive, already read by the derivation. `swing/evaluation/**` is read-only in this arc. |
| per-row provenance needs a schema column | **NOT hit.** No migration; schema stays v32. `candidates` gains nothing (verified it carries no per-row date column: `id, evaluation_run_id, ticker, bucket, close, pivot, initial_stop, adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, pattern_tag, notes, sector, industry`). |
| the survey authorizes fixing hits beyond the shape check | **NOT hit.** §S reports; nothing outside `swing/latches/**` + `swing/web/view_models/latches.py` + its template is touched. |
| new dependency | **NOT hit.** |
| L2 (new Schwab endpoint) | **NOT hit.** No integration change. |

---

## J. Gates

1. **RD plan-stage review — the PRIMARY gate** (his rulings, his lane). Headline: §D (the deliberate reversal) plus OQ-1/OQ-2/OQ-3 in §E.
2. `review-strong` Codex adversarial review, run to `NO_NEW_CRITICAL_MAJOR`, every response persisted verbatim in `.copowers-findings.md`.
3. **`codex-auto-review` — REQUIRED** (CHARC charter §2.9). On a worktree the canonical form is the COLD AUDIT (`codex exec -s read-only -c model_reasoning_effort=high` reading the changed files directly); `codex exec review` fails from a worktree with `Not inside a trusted directory` and has no `--skip-git-repo-check`. Verify the invocation at dispatch and report which form ran; never skip.
4. Full fast suite green + `ruff check swing/` clean, before the review and again at the end.
5. Orchestrator merged-head no-false-green re-run.
6. **RD merge-blocking QA.**
7. **Merge BEFORE 21-B's ledger lands (binding ordering).** A stale-price regime writes a wrong order TYPE into 21-B's execution-parity ledger, so a framework-vs-actual mismatch at RD's monthly read would be the framework's own defect masquerading as operator divergence, unattributable after the fact.
8. Operator browser witness only if a user-visible surface changes — it does (new label text + a new neutral note on the orders fragment), so a browser witness of BOTH the rung-A all-clear state and a rung-B stale state is recommended, seeded reversibly.

---

## S. The `data_asof_date` consumer survey

**RD's epistemic position, preserved verbatim and load-bearing:** *"I am not asserting it is a class — I am refusing to assume it is not."*

**This survey REPORTS. It does not authorize fixing any hit.** Everything below except hit 1 comes back for scoping.

### S.1 Method

1. `grep -rn "data_asof" --include=*.py --include=*.sql --include=*.j2 swing/ research/ scripts/` (tests excluded from the consumer census; they are not consumers).
2. Every `evaluation_runs` reader enumerated by `grep -rn "evaluation_runs"` and each JOIN site read in full.
3. Every `data_asof_date=` **write** site enumerated, to trace where a run-level stamp is COPIED onto per-row tables.
4. Each hit classified against the #30 trigger: *does this consumer treat a run/batch-level stamp as provenance for a per-ROW value?*
5. Each claim checked against the live DB / live archive (read-only), not against the code comments.

### S.2 There are FOUR distinct `data_asof_date` columns with TWO different semantics

| column | written by | semantics |
|---|---|---|
| `evaluation_runs.data_asof_date` | `swing/evaluation/orchestration.py:229-235` | **DATA-derived**: `max()` over per-ticker last bar dates (branch 1), or a CLI `as_of_date` (branch 2), or `last_completed_session(run_now)` (branch 3) |
| `pipeline_runs.data_asof_date` | `swing/pipeline/runner.py:610` -> `lease.py:271` | **CLOCK-derived**: `last_completed_session(run_now)`, computed BEFORE any bar is fetched |
| `daily_recommendations.data_asof_date` | `swing/recommendations/build.py:54,83` | a COPY of the evaluation run stamp onto PER-TICKER rows |
| `pattern_detection_events.data_asof_date` | `swing/pipeline/runner.py:2834` (from `lease_data_asof`) | a COPY of the CLOCK-derived pipeline stamp onto PER-TICKER detection rows |

Plus `chart_renders.data_asof_date` (per-ticker chart rows, migration 0020) and `watchlist.last_data_asof_date` (per-ticker streak key, `swing/watchlist/service.py:108-183`), both copies of a run-level value onto per-row records.

**Two different quantities share one name.** Empirically they have never diverged: across the last 25 paired runs, `pipeline_runs.data_asof_date == evaluation_runs.data_asof_date` in **25/25**. That is a coincidence of a healthy nightly, not an invariant — nothing enforces it, and the two are computed from different inputs at different times.

### S.3 The hits

**Hit 1 — `swing/latches/reader.py:258` + `swing/web/view_models/latches.py:860` (the latch shape check).** THE ARC'S SUBJECT. `(close, stamp)` read as a pair; the stamp gated a form assertion. **FIXED HERE.**

**Hit 2 — `swing/latches/reader.py:322` `count_session_recorded_closes`.** Filters `e.data_asof_date = ?` and counts tickers with a usable close, i.e. it counts closes DATED that session by stamp, not PROVEN from it. Already labelled honestly in 21-A ("closes DATED", never "closes FOR") and the shipped docstring records the limitation. **Unchanged; the label is already correct.** It feeds only rung C.

**Hit 3 — `swing/web/view_models/latches.py:249` `_build_row.price_asof`.** The card renders the run stamp as the price's as-of date and `_zone_position` derives IN ZONE / OUT OF ZONE from that price. Mitigated by `price_source="last_close"` and `price_is_stale=True` rendered unconditionally, so it does not claim freshness — but it is the same shape one level down. **REPORTED, not fixed** (see OQ-3).

**Hit 4 — `research/harness/aplus_v2_ohlcv_evaluator/context_builder.py:266-290, 348` and `ohlcv_reader.py`.** The V1<->V2 parity harness reads `er.data_asof_date` per candidate and slices EVERY ticker's OHLCV to `<= data_asof_date` — i.e. it slices at the COHORT MAX while V1's own close came from that ticker's OWN last bar. For a ticker that lagged the cohort at V1-eval time, V2 sees a bar V1 never had, and the resulting criterion-level difference is attributed to the evaluator. **This is a genuine second instance in the research measurement chain**, and it composes with the existing gotchas #24 (parallel-archive freshness desync) and #26 (archive bar-content temporal mutation) — a third member of the same freshness-desync family. **REPORTED. RD's lane to scope.** No parity claim is being re-opened by this survey; it is named so a future parity result is not read as clean when this term is unaccounted for.

**Hit 5 — `research/harness/backtest_v2_tightness/{run.py:64-79, patterns.py:76-91, walkforward.py:7}`.** The forward walk is anchored on `first_data_asof_date` — "trigger = first session AFTER `first_data_asof_date` where Close > pivot" — again the cohort max, not the ticker's own last bar. A lagging ticker's own boundary bar can therefore be included or skipped by one session. Same shape as hit 4, same lane. **REPORTED.**

**Hit 6 — `research/harness/{r2a_tightness_days_required, r2d_adr_min_pct, v2_orderliness_max_bar_ratio, v2_proximity_max_pct, v2_tightness_range_factor}/cohort_csv.py`.** These use `(ticker, data_asof_date)` as a DEDUPE / IDENTITY key. **Benign as identity** — a stamp is a perfectly good grouping key. They are listed because their emitted cohorts feed walk-forward code that inherits hit 5's anchoring. **REPORTED as inherited, not as an independent defect.**

**Hit 7 — `swing/data/repos/pattern_detection_events.py:119,150`.** The forward-observation gate `d.data_asof_date < observation_date` ("STRICT on the data") uses the CLOCK-derived pipeline stamp as the detection's data cutoff. If a ticker's actual last bar were older than that clock session, the gate is weaker than its own comment claims. **REPORTED. RD's lane (the temporal log is his measurement chain).** No evidence of an actual instance was sought or found; the point is that the guarantee is asserted, not enforced.

### S.4 Explicitly NOT hits (checked and cleared)

- `swing/web/price_cache.py:246-260 _last_close` — reads `candidates.close` ordered by `e.run_ts` and returns the bare float. It attaches NO date, so it makes no provenance claim. (It is an UNDATED price, which is a different and weaker concern.)
- `swing/patterns/foundation.py:767` — joins on `er.action_session_date` (forward-looking, not an aggregate over bars) purely to pick the latest candidate row at-or-before an as-of. No per-row value is dated by it.
- `swing/journal/analyze.py:139` — selects `er.action_session_date` and `c.close` together into `RecommendationContext(eval_run_action_session_date=..., close_at_eval=...)`. The field names do not claim the session dates the close, and the ordering key is `run_ts`. **Adjacent shape, no false claim.** Noted so a future reader does not add one.
- `swing/web/routes/trades.py:809` — sector/industry + `action_session_date`; no price.
- `swing/monitoring/research_health.py:1777`, `swing/web/chart_scope.py:256`, `view_models/dashboard.py:201`, `view_models/watchlist.py:382,395` — select run IDs only.
- `pipeline_runs.data_asof_date` used AS a run-level fact (lease, briefing header, CLI echo `swing/cli.py:477`) — a run-level stamp used for a run-level purpose is exactly what it is for.

### S.5 The survey's answer to RD's question

**It is not one bug, and it is not established to be a class of bugs.** It is one bug (hit 1, fixed here), one already-labelled limitation (hit 2), one same-shape display claim on the same surface (hit 3), and **three research-side instances of the same STRUCTURE (hits 4, 5, 7) whose consequences are unmeasured**. The structure is demonstrably repeated — a run/batch stamp copied onto per-row records and later read as those rows' own date — which is more than one bug and less than a proven class. Deciding whether hits 4/5/7 are defects requires measuring their effect on results RD owns, which is a scoping question, not an engineering one.

The write-side observation that makes all of them one family: **`evaluation_runs.data_asof_date` is an aggregate, and every table that copies it onto a per-ticker row inherits the gap.** Closing it at the source (per-ticker close provenance at write time) is the real fix for the whole family and is out of scope here by hard stop.
