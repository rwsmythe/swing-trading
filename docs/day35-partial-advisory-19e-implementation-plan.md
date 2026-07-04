# Day-3-5 Calendar Partial-Trim Advisory (19-E) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a NEW, purely-additive stop-advisory rule that prompts a Day-3-5 (calendar/session window) 50% partial-trim into strength when the last completed session closed above the entry price and the trade has not yet been trimmed, so a standard-cohort operator can execute the same partial the shadow-expectancy engine measures under H1 (the VSTS-shape reason-to-exist: on wide-stop geometry the existing +1R trim never becomes reachable).

**Architecture:** One new pure advisory function `suggest_partial_day_window(trade, ctx)` in `swing/trades/advisory.py`, wired into BOTH existing aggregators (`compute_all_suggestions` + `compute_price_independent_suggestions`), plus three NEW `StopAdvisoryConfig` fields with `__post_init__` validation in `swing/config.py`. ZERO behavior change to `suggest_trim_into_strength` or any other existing rule (operator chose ADD-ALONGSIDE). The rule rides the existing `AdvisorySuggestion` render path via a new `rule="partial_day_window"` string — no new page, no VM field, no template change, no schema change (v31 unchanged).

**Tech Stack:** Python 3.14, dataclasses, `swing.evaluation.dates.sessions_behind` (existing pure NYSE-session helper, `exchange_calendars` XNYS), pytest. No new dependency.

## Global Constraints

- **E1 — PURELY ADDITIVE (binding).** A NEW advisory function + its aggregator wiring + NEW config fields with validation. NO behavior change to any existing advisory (`suggest_trim_into_strength` keeps its exact semantics). The carve-out touches `swing/trades/advisory.py` + `swing/config.py` ONLY — no other `swing/trades` file, no `swing/data`, no `swing/web` template/VM, no `swing/pipeline`.
- **E2 — defaults aligned with the ENGINE.** Window day 3-5 (entry day = day 1), 50% (`PARTIAL_PCT=0.5`), close>entry-price condition. Day-counting basis (sessions vs calendar) is an RD decision (see "RD Decision Points"); this plan proposes NYSE sessions with the parity rationale.
- **E3 — suppression + coexistence.** Reuse `ctx.has_been_trimmed` (any prior trim suppresses — same as +1R); the window CLOSES after day 5 (no stale nag). Simultaneous fire with the +1R `trim_into_strength` = both render as distinct labeled rules (this plan's proposal; RD rules — see "RD Decision Points").
- **E4 — existing render path.** New `rule` string through the existing `AdvisorySuggestion` plumbing; no new page, no base-VM field (the every-base-VM-or-500 gotcha), no template change.
- **Anchor contract (LOAD-BEARING, Codex R1-M2).** `ctx.as_of_date` is the FORWARD-looking action-session date string (`action_session_for_run(...)`) — the invariant EVERY production caller passes (open_positions_row / dashboard / trades VMs, runner briefing) and the SAME anchor the shipped `suggest_time_stop` already depends on (`advisory.py:123`). Under that contract, `day_num = sessions_behind(as_of_date, entry_date)` lands exactly on the LAST COMPLETED session's day number (entry = Day 1), which is the session whose close is `ctx.previous_close`. The rule is NOT correct if a caller passes a non-forward `as_of_date` (e.g. today's in-progress-session date) — but no production caller does; the CLI diagnostic (`cli.py`) passes an operator flag and is out of scope. This is the exact same anchor dependency `suggest_time_stop` ships with; the low boundary (`day_num == 0` when `as_of_date == entry_date`) is pinned by a Task-2 test.
- **Schema:** v31, ZERO migrations. NO new dependency. NO new module.
- **Commits:** conventional (`feat(trades):`, `test(trades):`, `feat(config):`). No `Co-Authored-By`, no `--no-verify`, no amend. TDD one red->green->commit per logical change.
- **Ruff gate:** `ruff check swing/` clean; introduce no new violations. Match `tests/trades/test_advisory.py` style (<=100-char lines, local `from swing.trades.advisory import ...` inside each test).
- **ASCII discipline (LOAD-BEARING here):** advisory `message` strings are echoed to CLI stdout via `swing/cli.py:1024` `click.echo(f"  [{s.rule}] {s.message}")`, which crashes on Windows cp1252 for non-ASCII glyphs. Sibling rules use `—`/`>=`/`x`; the NEW message MUST be pure ASCII (hyphen `-`, `>`, `$`, `%`, digits only) — a deliberate deviation from sibling em-dash style, justified by the recipe's ASCII discipline + the stdout echo path.

---

## RD Decision Points (routed to RD at plan-stage review; do NOT self-decide)

These are proposals WITH rationale. RD rules; the operator sees the outcome at the GUI witness (§4 gate 3).

### Decision A — Day-counting basis: NYSE sessions vs calendar days

**Proposal: count NYSE trading sessions via `swing.evaluation.dates.sessions_behind`, NOT calendar `.days`.**

- The engine counts SESSIONS: `research/harness/shadow_expectancy/simulator.py:119` `session_index = i + 1` over `forward_bars` (bars strictly after the entry bar; `run.py:178` `forward_bars = all_bars[entry_idx+1:]`), and the partial fires at `simulator.py:181` `session_index == params.partial_session_n` (`PARTIAL_SESSION_N=3`). Cohort parity — a live operator executing what the engine measures — is the arc's founding purpose (brief §1), so the basis should match.
- The in-file precedent `suggest_time_stop` (`advisory.py:123`) counts CALENDAR days (`(as_of - entry).days`). That is acceptable for a coarse ~10-day time stop where weekend drift is immaterial; it is NOT acceptable for a tight 3-day window, which is exactly where session-vs-calendar drift bites.
- **Concrete drift (calendar-verified against XNYS):** entry Mon 2026-06-08. The doctrine day-5 partial is due on the last-completed-session Fri 2026-06-12 (action_session Mon 2026-06-15). Calendar `(2026-06-15 - 2026-06-08).days == 7` -> a calendar-day window `[3,5]` would have CLOSED (7 > 5) exactly when the day-5 partial is due. Session count = 5 (correct). A single weekend already breaks the calendar basis.

**Day-number convention (fixed by the brief, restated for precision):** "Day N, entry day = Day 1." Under the sessions basis, the last completed session's day-number is:

```
day_num = sessions_behind(action_session, entry_date)   # entry = Day 1
```

This is calendar-verified (see "Arithmetic ledger" below): entry 2026-06-08, action_session 2026-06-11 -> `sessions_behind == 3` -> Day 3. Note `sessions_behind(reference, candidate)` returns the count of sessions `candidate` is behind `reference`, and `as_of_date` is the FORWARD-looking `action_session` (all production callers pass `action_session_for_run(...)`); this forward anchor makes `sessions_behind(action_session, entry)` land exactly on the LAST COMPLETED session's day-number — the session whose close is `ctx.previous_close`. This is the "Session-anchor read/write mismatch" gotcha handled correctly (a naive `sessions_behind(...) + 1` would over-count by one — a Task-2 boundary test pins this).

**Informational note for RD (engine/doctrine off-by-one — NOT an open decision, brief already fixed the window):** the engine's `PARTIAL_SESSION_N=3` fires at `session_index == 3` = the 3rd session AFTER entry = Day 4 under the strict "entry = Day 1" reading (the engine constant's `# Day-3 partial` comment is off-by-one vs the doctrine day-number). The brief's Day 3-5 window (`sessions_behind` in `{2,3,4}` -> wait, in `{3,4,5}`; see below) is the DST-verbatim operator-latitude window ("Day 3, 4, or 5 counting entry as Day 1", `reference/methodology/dst-take-profit-and-trail.md` D.2) and CONTAINS the engine's single execution point. This plan implements the doctrine Day 3-5 window as the brief specifies; RD need only confirm the window default (3-5) stands given this off-by-one is disclosed.

> Clarification on the window in `sessions_behind` terms: with `day_num = sessions_behind(action_session, entry)` and window `[start, end] = [3, 5]`, the rule fires when `day_num in {3, 4, 5}`. The engine partial (session_index 3 = Day 4) has `day_num == 4` -> inside the window. Confirmed contained.

### Decision B — close>entry definition

**Proposal: `ctx.previous_close > trade.entry_price` (strict `>`).**

- The engine compares the day-N SESSION CLOSE to the entry fill (`simulator.py:182` `bar.close > entry_fill`, strict). `ctx.previous_close` is the last completed session's daily close — the same session `day_num` identifies — matching the engine's close-based grain.
- This mirrors the established close-based precedent `suggest_exit_close_below_ma` (`advisory.py:89-104`), which fires on `ctx.previous_close` explicitly ("YESTERDAY'S DAILY CLOSE ... not on a live intraday tick"). Using `ctx.current_price` (a live intraday tick) would diverge from both the engine and the doctrine ("End of Day 3 ... I wait to see how it closes"). Strict `>` (equal close = no fire) matches the engine.

### Decision C — coexistence with the +1R `trim_into_strength`

**Proposal: distinct labeled rules — both fire, NO mutual suppression.**

- The established in-file precedent is independent, concurrently-firing rules: `suggest_maturity_stage_trail_ma_hint` explicitly does NOT suppress `trail_10ma`/`trail_20ma` (`advisory.py:272-276`), and `suggest_r_multiple_stop_tighten` explicitly does NOT suppress `breakeven` (`advisory.py:317-320`). Both new-vs-old pairs render together; the operator reads all and decides.
- Both rules recommend the SAME action (trim into strength); two concurrent prompts = a STRONGER signal, not a conflict. Both are gated on the trim state (`not ctx.has_been_trimmed` for +1R; identical gate here), so they can only co-fire in the pre-first-trim window and BOTH go silent after any trim.
- **Surfaced concern for RD/operator:** default trim percentages differ — +1R default is 25% (`trim_first_pct_default=0.25`), the calendar partial default is 50% (`partial_day_pct_default=0.5`, engine parity). If both fire, the operator sees "trim 25%" and "trim 50%" simultaneously. This is the one argument FOR an explicit precedence (show only one). This plan proposes distinct-labeled-rules (matches precedent, hides nothing); RD/operator may instead choose precedence (e.g. calendar-partial wins in-window). A Task-4 test asserts the CHOSEN behavior exactly.

---

## Arithmetic ledger (calendar-verified against XNYS, used by the tests below)

Entry `entry_date = 2026-06-08` (Mon). Sessions: `06-08, 06-09, 06-10, 06-11, 06-12, 06-15, 06-16` (06-13/06-14 weekend). `day_num = sessions_behind(action_session, 2026-06-08)`:

| last completed session | action_session (`as_of_date`) | `day_num` | in `[3,5]`? |
|---|---|---|---|
| 2026-06-08 (entry) | 2026-06-09 | 1 | no |
| 2026-06-09 | 2026-06-10 | 2 | no |
| 2026-06-10 | 2026-06-11 | **3** | **yes (opens)** |
| 2026-06-11 | 2026-06-12 | 4 | yes |
| 2026-06-12 | 2026-06-15 | **5** | **yes (closes)** |
| 2026-06-15 | 2026-06-16 | 6 | no (closed) |

Weekend check: last-completed Fri 06-12 -> action_session Mon 06-15 -> `day_num == 5` (session-correct); calendar `(06-15 - 06-08).days == 7` (would be out-of-window). This row is the Decision-A discriminator.

---

## File Structure

- **Modify `swing/config.py`** — add 3 fields to `StopAdvisoryConfig` (after the existing Bundle-2/3 fields, before `__post_init__`) + 3 validation blocks inside `__post_init__` (mirroring the existing finite/positive pattern). This file owns config dataclasses + their construction-time validation.
- **Modify `swing/trades/advisory.py`** — add `from swing.evaluation.dates import sessions_behind` import; add `suggest_partial_day_window(trade, ctx)`; wire it into `compute_all_suggestions` (append, position 14) AND `compute_price_independent_suggestions` (it is genuinely price-independent — see Task 3 rationale). This file owns the pure advisory rules + aggregators.
- **Modify `tests/trades/test_advisory.py`** — add config-validation tests + the `suggest_partial_day_window` unit tests + the aggregator-integration/coexistence/VSTS tests. Mirrors `swing/trades/advisory.py`.
- **Modify `tests/test_config.py` (or the existing config-validation test module)** — add the `StopAdvisoryConfig.__post_init__` rejection tests for the new fields. (If no such module exists, fold these into `tests/trades/test_advisory.py` under a clearly-labeled section — verify at execution time which module already holds `StopAdvisoryConfig` validation tests via `grep -rn "trim_first_r_trigger must be" tests/`.)

**No changes** to `swing/web/*`, `swing/pipeline/*`, `swing/cli.py`, `swing/data/*`, migrations, or `swing.config.toml` (the new fields default correctly; a TOML override is optional and out of scope).

---

## Task 1: New `StopAdvisoryConfig` fields + validation

**Files:**
- Modify: `swing/config.py:92-149` (the `StopAdvisoryConfig` dataclass + `__post_init__`)
- Test: `tests/trades/test_advisory.py` (or the config-validation module — see File Structure)

**Interfaces:**
- Produces: `StopAdvisoryConfig.partial_day_window_start: int = 3`, `partial_day_window_end: int = 5`, `partial_day_pct_default: float = 0.5`. Consumed by Task 2's `suggest_partial_day_window`.

- [ ] **Step 1: Write the failing tests** (add to the config-validation test module)

```python
def test_stop_advisory_config_partial_day_defaults():
    from swing.config import StopAdvisoryConfig
    c = StopAdvisoryConfig()
    assert c.partial_day_window_start == 3
    assert c.partial_day_window_end == 5
    assert c.partial_day_pct_default == 0.5


def test_stop_advisory_config_rejects_window_start_below_one():
    import pytest
    from swing.config import StopAdvisoryConfig
    with pytest.raises(ValueError, match="partial_day_window_start"):
        StopAdvisoryConfig(partial_day_window_start=0)


def test_stop_advisory_config_rejects_end_before_start():
    import pytest
    from swing.config import StopAdvisoryConfig
    with pytest.raises(ValueError, match="partial_day_window_end"):
        StopAdvisoryConfig(partial_day_window_start=5, partial_day_window_end=3)


def test_stop_advisory_config_rejects_pct_out_of_range():
    import pytest
    from swing.config import StopAdvisoryConfig
    with pytest.raises(ValueError, match="partial_day_pct_default"):
        StopAdvisoryConfig(partial_day_pct_default=0.0)
    with pytest.raises(ValueError, match="partial_day_pct_default"):
        StopAdvisoryConfig(partial_day_pct_default=1.5)
    with pytest.raises(ValueError, match="partial_day_pct_default"):
        StopAdvisoryConfig(partial_day_pct_default=float("nan"))
```

**Pre/post arithmetic:** pre-fix, `StopAdvisoryConfig()` has no such attributes -> `test_..._defaults` raises `AttributeError` (FAIL); the rejection tests pass a kwarg the frozen dataclass does not accept -> `TypeError` (FAIL, not the asserted `ValueError`). Post-fix, defaults exist (PASS) and each pathological value raises the asserted `ValueError` (PASS). A no-op impl that added the fields but skipped validation would FAIL the three rejection tests.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/trades/test_advisory.py -k "partial_day and config" -q`
Expected: FAIL (`AttributeError` / `TypeError`).

- [ ] **Step 3: Add the fields + validation to `swing/config.py`**

Add fields immediately after `tighten_at_r_multiple: float = 2.0` (line 113), before `def __post_init__`:

```python
    # 19-E (§2 E2) — Day-3-5 calendar partial-trim advisory. Engine-parity
    # defaults (research/harness/shadow_expectancy/constants.py:
    # PARTIAL_SESSION_N-window / PARTIAL_PCT=0.5). Window is a doctrine day
    # number (entry day = Day 1) measured in NYSE sessions; see
    # swing/trades/advisory.py:suggest_partial_day_window. Fires day 3..5
    # inclusive on close>entry, suppressed by any prior trim, closes after 5.
    partial_day_window_start: int = 3
    partial_day_window_end: int = 5
    partial_day_pct_default: float = 0.5
```

Add these blocks at the END of `__post_init__` (after the `tighten_at_r_multiple` block, still using the local `import math as _math` already present at the top of the method):

```python
        # 19-E (§2 E2) — validate the Day-3-5 window fields. Window bounds are
        # day numbers (entry = Day 1): start must be >= 1, end must not precede
        # start. Percentage mirrors trim_first_pct_default: finite in (0, 1].
        if self.partial_day_window_start < 1:
            raise ValueError(
                f"stop_advisory.partial_day_window_start must be >= 1 "
                f"(entry day = Day 1); got {self.partial_day_window_start!r}"
            )
        if self.partial_day_window_end < self.partial_day_window_start:
            raise ValueError(
                f"stop_advisory.partial_day_window_end must be >= "
                f"partial_day_window_start; got end="
                f"{self.partial_day_window_end!r}, start="
                f"{self.partial_day_window_start!r}"
            )
        if (
            not _math.isfinite(self.partial_day_pct_default)
            or not (0 < self.partial_day_pct_default <= 1)
        ):
            raise ValueError(
                f"stop_advisory.partial_day_pct_default must be a finite value "
                f"in (0, 1]; got {self.partial_day_pct_default!r}"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/trades/test_advisory.py -k "partial_day and config" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/config.py tests/trades/test_advisory.py
git commit -m "feat(config): Task 1 — StopAdvisoryConfig Day-3-5 partial fields + validation"
```

---

## Task 2: `suggest_partial_day_window` advisory function

**Files:**
- Modify: `swing/trades/advisory.py` (add import at top; add function after `suggest_trim_into_strength`, ~line 161)
- Test: `tests/trades/test_advisory.py`

**Interfaces:**
- Consumes: `StopAdvisoryConfig.partial_day_window_start/end/partial_day_pct_default` (Task 1); existing `AdvisoryContext` fields `as_of_date`, `previous_close`, `has_been_trimmed`, `config`; existing `Trade.entry_date`, `Trade.entry_price`; existing `swing.evaluation.dates.sessions_behind(reference: date, candidate: date) -> int`.
- Produces: `suggest_partial_day_window(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None` with `rule="partial_day_window"`. Consumed by Task 3's aggregator wiring.

- [ ] **Step 1: Write the failing tests**

Add a labeled section + a wide-stop trade helper + the unit tests. Note `_trade()` (line 663) and `_ctx()` (line 674) already exist; `_trade()` hard-codes `initial_stop=170.0`, `entry_price=180.0` (1R=$10). For the window tests use `entry_price=100.0` via a local helper so `previous_close` values read cleanly, and drive `as_of_date` from the Arithmetic ledger.

```python
# ----------------------------------------------------------------------
# 19-E — suggest_partial_day_window (Day-3-5 calendar partial-trim)
# Entry 2026-06-08 (Mon). day_num = sessions_behind(as_of, entry).
# 06-11 action -> Day 3 (opens); 06-15 action -> Day 5 (closes);
# 06-10 action -> Day 2; 06-16 action -> Day 6 (closed).
# ----------------------------------------------------------------------

def _trade_pw(entry: float = 100.0, initial_stop: float = 90.0) -> Trade:
    return Trade(
        id=1, ticker="AAPL", entry_date="2026-06-08", entry_price=entry,
        initial_shares=10, initial_stop=initial_stop, current_stop=initial_stop,
        state="entered", watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
    )


def _ctx_pw(*, as_of: str, prev_close: float | None,
            has_been_trimmed: bool = False) -> AdvisoryContext:
    return AdvisoryContext(
        as_of_date=as_of, current_price=(prev_close or 0.0),
        sma10=None, sma20=None, sma50=None, previous_close=prev_close,
        weather_status="Bullish", config=StopAdvisoryConfig(),
        has_been_trimmed=has_been_trimmed,
    )


def test_partial_day_window_day3_close_above_entry_fires():
    from swing.trades.advisory import suggest_partial_day_window
    s = suggest_partial_day_window(
        _trade_pw(), _ctx_pw(as_of="2026-06-11", prev_close=105.0))
    assert s is not None
    assert s.rule == "partial_day_window"
    assert "50%" in s.message
    assert "Day 3" in s.message


def test_partial_day_window_day2_does_not_fire():
    from swing.trades.advisory import suggest_partial_day_window
    # as_of 2026-06-10 -> day_num 2 -> below window start 3.
    s = suggest_partial_day_window(
        _trade_pw(), _ctx_pw(as_of="2026-06-10", prev_close=105.0))
    assert s is None


def test_partial_day_window_entry_day_does_not_fire():
    from swing.trades.advisory import suggest_partial_day_window
    # Anchor low-boundary (Codex R1-M2): as_of == entry_date -> sessions_behind
    # returns 0 (candidate >= reference) -> day_num 0 -> below window start.
    s = suggest_partial_day_window(
        _trade_pw(), _ctx_pw(as_of="2026-06-08", prev_close=105.0))
    assert s is None


def test_partial_day_window_day5_still_fires():
    from swing.trades.advisory import suggest_partial_day_window
    # as_of 2026-06-15 (Mon after weekend) -> day_num 5 -> window inclusive end.
    s = suggest_partial_day_window(
        _trade_pw(), _ctx_pw(as_of="2026-06-15", prev_close=105.0))
    assert s is not None
    assert "Day 5" in s.message


def test_partial_day_window_day6_window_closed():
    from swing.trades.advisory import suggest_partial_day_window
    # as_of 2026-06-16 -> day_num 6 -> past window end 5.
    s = suggest_partial_day_window(
        _trade_pw(), _ctx_pw(as_of="2026-06-16", prev_close=105.0))
    assert s is None


def test_partial_day_window_close_not_above_entry_does_not_fire():
    from swing.trades.advisory import suggest_partial_day_window
    # Day 3 but close == entry (100.0) -> strict > fails.
    s = suggest_partial_day_window(
        _trade_pw(), _ctx_pw(as_of="2026-06-11", prev_close=100.0))
    assert s is None


def test_partial_day_window_none_previous_close_does_not_fire():
    from swing.trades.advisory import suggest_partial_day_window
    s = suggest_partial_day_window(
        _trade_pw(), _ctx_pw(as_of="2026-06-11", prev_close=None))
    assert s is None


def test_partial_day_window_already_trimmed_suppressed():
    from swing.trades.advisory import suggest_partial_day_window
    s = suggest_partial_day_window(
        _trade_pw(),
        _ctx_pw(as_of="2026-06-11", prev_close=105.0, has_been_trimmed=True))
    assert s is None


def test_partial_day_window_message_is_ascii():
    from swing.trades.advisory import suggest_partial_day_window
    s = suggest_partial_day_window(
        _trade_pw(), _ctx_pw(as_of="2026-06-11", prev_close=105.0))
    assert s is not None
    # ASCII discipline: message is echoed to CLI stdout (cli.py:1024).
    s.message.encode("ascii")  # raises UnicodeEncodeError if any non-ASCII glyph
```

**Pre/post arithmetic (distinguishing tests):**
- `day3_close_above_entry_fires`: PRE-fix -> `ImportError` (function absent). POST-fix -> `sessions_behind(2026-06-11, 2026-06-08)=3` in `[3,5]`, `105.0 > 100.0`, not trimmed -> fires. Distinguishes absent-vs-present.
- `day2_does_not_fire` vs `day3_..._fires`: pins the exact window boundary. A naive `day_num = sessions_behind(...) + 1` impl would compute Day 3 at `as_of=2026-06-10` (`sessions_behind=2, +1=3`) and FIRE -> this test FAILS that off-by-one impl. The correct impl (no `+1`) gives Day 2 -> no fire. Distinguishes correct-vs-off-by-one.
- `entry_day_does_not_fire`: anchor low-boundary (Codex R1-M2). `as_of == entry_date` -> `sessions_behind` returns 0 (`candidate >= reference`) -> Day 0 -> below window. Pins that a non-forward/degenerate anchor cannot spuriously fire.
- `day5_still_fires` + `day6_window_closed`: pins the inclusive upper bound AND exercises the weekend-crossing (06-12 completed -> 06-15 action). A calendar-`.days` impl computes `(06-15 - 06-08).days = 7 > 5` -> would NOT fire on Day 5 -> FAILS this test. Distinguishes sessions-vs-calendar (Decision A).
- `close_not_above_entry` / `none_previous_close` / `already_trimmed`: guard tests (pass under both correct guards present/absent only if the fire path exists; they pin E2 close>entry, the None-guard, and E3 suppression).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/trades/test_advisory.py -k partial_day_window -q`
Expected: FAIL (`ImportError: cannot import name 'suggest_partial_day_window'`).

- [ ] **Step 3: Write the implementation**

Add to the imports at the top of `swing/trades/advisory.py` (after the existing `from swing.trades.equity import r_so_far`):

```python
from swing.evaluation.dates import sessions_behind
```

Add the function immediately after `suggest_trim_into_strength` (after line 160):

```python
def suggest_partial_day_window(
    trade: Trade, ctx: AdvisoryContext,
) -> AdvisorySuggestion | None:
    """19-E (§2 E2/E3) — Day-3-5 calendar partial-trim advisory (DST D.2).

    Fires when the LAST COMPLETED session's day number (entry day = Day 1,
    counted in NYSE sessions) is inside the [start, end] window (default
    3..5 inclusive), that session's close (``ctx.previous_close``) is above
    the entry price, and the trade has not yet been trimmed. Recommends a
    50% (``partial_day_pct_default``) partial into strength — the mechanical
    Day-3-5 trim the shadow-expectancy engine takes (constants
    ``PARTIAL_SESSION_N`` / ``PARTIAL_PCT``), so a standard-cohort operator
    can execute the ruleset H1 is measured under.

    ADD-ALONGSIDE (operator decision 2026-07-04): this does NOT alter or
    suppress ``suggest_trim_into_strength`` (+1R). Both are gated on
    ``not ctx.has_been_trimmed`` and render as distinct labeled rules when
    they co-fire (RD decision C).

    Day-number basis = NYSE sessions (RD decision A): ``sessions_behind``
    over the forward-looking ``as_of_date`` (= action_session) lands on the
    last COMPLETED session's day number, which is the session whose close
    is ``ctx.previous_close``. Calendar days mis-count across weekends for a
    tight window. Window CLOSES after ``partial_day_window_end`` (no stale
    nag). Silently no-ops when ``previous_close`` is None (price/bundle
    degraded — cannot evaluate the close condition).

    ANCHOR CONTRACT: ``ctx.as_of_date`` MUST be the forward-looking
    action-session date (every production caller passes
    ``action_session_for_run(...)``; the same anchor ``suggest_time_stop``
    depends on). When ``as_of_date == entry_date`` (or earlier),
    ``sessions_behind`` returns 0 -> day 0 -> below the window -> no fire.
    """
    if ctx.previous_close is None:
        return None
    if ctx.has_been_trimmed:
        return None
    cfg = ctx.config
    day_num = sessions_behind(
        date.fromisoformat(ctx.as_of_date),
        date.fromisoformat(trade.entry_date),
    )
    if not (cfg.partial_day_window_start <= day_num <= cfg.partial_day_window_end):
        return None
    if ctx.previous_close <= trade.entry_price:
        return None
    pct = cfg.partial_day_pct_default
    return AdvisorySuggestion(
        rule="partial_day_window",
        message=(
            f"Day {day_num} of the {cfg.partial_day_window_start}-"
            f"{cfg.partial_day_window_end} partial window - consider trimming "
            f"{pct * 100:.0f}% into strength "
            f"(close ${ctx.previous_close:.2f} > entry ${trade.entry_price:.2f}); "
            f"DST D.2 partial"
        ),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/trades/test_advisory.py -k partial_day_window -q`
Expected: PASS (all 9 unit tests).

- [ ] **Step 5: Commit**

```bash
git add swing/trades/advisory.py tests/trades/test_advisory.py
git commit -m "feat(trades): Task 2 — suggest_partial_day_window Day-3-5 partial advisory"
```

---

## Task 3: Aggregator wiring (both aggregators)

**Files:**
- Modify: `swing/trades/advisory.py:363-365` (`compute_price_independent_suggestions`) and `:368-392` (`compute_all_suggestions`)
- Test: `tests/trades/test_advisory.py`

**Interfaces:**
- Consumes: `suggest_partial_day_window` (Task 2).
- Produces: the rule appears in both aggregators' output lists.

**Rationale for wiring BOTH aggregators:** `suggest_partial_day_window` reads `as_of_date`, `previous_close`, `entry_date`, `entry_price`, `has_been_trimmed` — NOT `current_price`. It is genuinely price-independent. Wiring only `compute_all_suggestions` (the price-available path) would silently DROP the partial prompt whenever `PriceCache` is degraded and callers fall to `compute_price_independent_suggestions` (open_positions_row.py:213-217, runner.py briefing path) — the exact Bundle-3 Codex R1 Major #2 regression class ("DB-sourced advisory must fire even when PriceCache is degraded").

**Double-fire is impossible (verified on disk, Codex R1-M1):** this dual-wiring EXACTLY MIRRORS the already-shipped `suggest_maturity_stage_trail_ma_hint`, which is present in BOTH aggregators today (`advisory.py:364` in `compute_price_independent_suggestions` + `:390` in `compute_all_suggestions`). A grep of every caller — `swing/web/view_models/{open_positions_row,dashboard,trades}.py`, `swing/pipeline/runner.py`, `swing/cli.py` — confirms each site calls `compute_all_suggestions` XOR `compute_price_independent_suggestions` in an `if snapshot is not None: ... else: ...` branch; NONE concatenates both outputs. The XOR is a codebase-wide invariant the maturity hint already relies on; a hypothetical future caller that concatenates both lists owns its own dedup (same as it would for the maturity hint). **Execution-time verification step (below) re-greps this before shipping.**

**`previous_close` availability in the degraded path (verified on disk, Codex R1-M3):** `previous_close` is sourced from the OHLCV BUNDLE (`open_positions_row.py:202` `previous_close=bundle.previous_close if bundle else None`), a SEPARATE subsystem from the live price snapshot (`current_price`). A degraded live-price fetch (rate limit) with a fresh daily OHLCV archive is a real, common state -> `previous_close` IS present in the price-independent path there, so this wiring is NOT dead code. When the bundle is ALSO absent, `previous_close is None` and the rule no-ops via its None guard — that "silent no-fire" is CORRECT (the close>entry condition is unevaluable without a close), not a regression.

- [ ] **Step 1: Write the failing tests**

```python
def test_compute_all_suggestions_includes_partial_day_window():
    s = compute_all_suggestions(
        _trade_pw(), _ctx_pw(as_of="2026-06-11", prev_close=105.0))
    assert any(x.rule == "partial_day_window" for x in s)


def test_compute_price_independent_includes_partial_day_window():
    # Price-degraded path: sentinel current_price, previous_close still known.
    ctx = AdvisoryContext(
        as_of_date="2026-06-11", current_price=0.0,
        sma10=None, sma20=None, sma50=None, previous_close=105.0,
        weather_status="STALE", config=StopAdvisoryConfig(),
        has_been_trimmed=False,
    )
    s = compute_price_independent_suggestions(_trade_pw(), ctx)
    assert any(x.rule == "partial_day_window" for x in s)


def test_partial_day_window_does_not_alter_trim_into_strength():
    # ADD-ALONGSIDE guard (E1): a +1R trade OUTSIDE the day window still
    # fires trim_into_strength and does NOT fire partial_day_window.
    # entry 100 / stop 90 -> 1R = $10; prev_close 110 -> +1.0R.
    # as_of 2026-06-16 -> day_num 6 -> window closed.
    ctx = _ctx_pw(as_of="2026-06-16", prev_close=110.0)
    ctx = AdvisoryContext(  # override current_price to 110 so +1R is reached
        as_of_date="2026-06-16", current_price=110.0,
        sma10=None, sma20=None, sma50=None, previous_close=110.0,
        weather_status="Bullish", config=StopAdvisoryConfig(),
    )
    s = compute_all_suggestions(_trade_pw(), ctx)
    rules = {x.rule for x in s}
    assert "trim_into_strength" in rules
    assert "partial_day_window" not in rules
```

**Pre/post arithmetic:** PRE-fix (Task 2 landed, wiring absent) -> `compute_all_suggestions`/`compute_price_independent_suggestions` never include `partial_day_window` -> both `includes` tests FAIL. POST-fix -> present -> PASS. `does_not_alter_trim_into_strength` passes both pre and post (a guard that `trim_into_strength` semantics are untouched and the window is respected).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/trades/test_advisory.py -k "partial_day_window and (compute or alter)" -q`
Expected: FAIL on the two `includes` tests.

- [ ] **Step 3: Wire both aggregators**

In `compute_price_independent_suggestions`, before the `return`:

```python
    sugs.append(suggest_maturity_stage_trail_ma_hint(trade, ctx))
    # 19-E — Day-3-5 partial is price-independent (reads previous_close +
    # dates, not current_price); fire it even under PriceCache degradation
    # (Bundle-3 R1 M#2 class). Callers use this aggregator XOR
    # compute_all_suggestions, so no double-fire.
    sugs.append(suggest_partial_day_window(trade, ctx))
    return [s for s in sugs if s is not None]
```

In `compute_all_suggestions`, after the `suggest_r_multiple_stop_tighten` append (line 391), before the `return`:

```python
    sugs.append(suggest_r_multiple_stop_tighten(trade, ctx))
    # 19-E — Day-3-5 calendar partial advisory (ADD-ALONGSIDE; distinct
    # labeled rule, no suppression of trim_into_strength). Appended last.
    sugs.append(suggest_partial_day_window(trade, ctx))
    return [s for s in sugs if s is not None]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/trades/test_advisory.py -k "partial_day_window and (compute or alter)" -q`
Expected: PASS.

- [ ] **Step 4b: Re-verify the caller XOR invariant (Codex R1-M1 guard)**

Run: `grep -rn "compute_all_suggestions\|compute_price_independent_suggestions" swing/ --include=*.py | grep -v "def "`
Expected: every caller (`open_positions_row.py`, `dashboard.py`, `trades.py`, `runner.py`, `cli.py`) invokes exactly ONE of the two aggregators per code path (an `if snapshot is not None: compute_all_suggestions else compute_price_independent_suggestions` branch), and NONE concatenates both outputs. If a caller concatenating both is ever found, STOP and flag it — the dual-wiring assumption (matching the shipped `suggest_maturity_stage_trail_ma_hint` at `advisory.py:364`+`:390`) no longer holds and dedup is required at that call site.

- [ ] **Step 5: Commit**

```bash
git add swing/trades/advisory.py tests/trades/test_advisory.py
git commit -m "feat(trades): Task 3 — wire partial_day_window into both aggregators"
```

---

## Task 4: Reason-to-exist (VSTS wide-stop) + coexistence tests

**Files:**
- Test: `tests/trades/test_advisory.py`

**Interfaces:**
- Consumes: `suggest_partial_day_window`, `suggest_trim_into_strength`, `compute_all_suggestions` (Tasks 2-3).

- [ ] **Step 1: Write the tests**

```python
def test_partial_day_window_fires_where_plus1r_is_unreachable_vsts():
    # THE ARC'S REASON TO EXIST (brief §1 / VSTS trade 17).
    # Wide stop: entry 100, initial_stop 83 -> 1R = $17 (a +17% move).
    # prev_close 108 -> r_so_far = (108-100)/17 = 0.47R < 1.0 -> +1R DEAD.
    # Day 3 (as_of 2026-06-11), close 108 > entry 100 -> calendar partial FIRES.
    from swing.trades.advisory import (
        suggest_partial_day_window, suggest_trim_into_strength,
    )
    trade = _trade_pw(entry=100.0, initial_stop=83.0)
    ctx = AdvisoryContext(
        as_of_date="2026-06-11", current_price=108.0,
        sma10=None, sma20=None, sma50=None, previous_close=108.0,
        weather_status="Bullish", config=StopAdvisoryConfig(),
    )
    assert suggest_trim_into_strength(trade, ctx) is None      # +1R unreachable
    partial = suggest_partial_day_window(trade, ctx)
    assert partial is not None                                  # calendar fires
    assert partial.rule == "partial_day_window"
    # And through the aggregator the operator SEES the partial the old
    # surface stayed silent on:
    rules = {x.rule for x in compute_all_suggestions(trade, ctx)}
    assert "partial_day_window" in rules
    assert "trim_into_strength" not in rules


def test_partial_day_window_coexists_with_plus1r_when_both_fire():
    # RD DECISION C = distinct labeled rules (both fire, no suppression).
    # entry 100 / stop 90 -> 1R = $10. prev_close 112 -> +1.2R (>= 1.0R).
    # Day 3 (as_of 2026-06-11), close 112 > entry 100, not trimmed.
    trade = _trade_pw(entry=100.0, initial_stop=90.0)
    ctx = AdvisoryContext(
        as_of_date="2026-06-11", current_price=112.0,
        sma10=None, sma20=None, sma50=None, previous_close=112.0,
        weather_status="Bullish", config=StopAdvisoryConfig(),
    )
    rules = {x.rule for x in compute_all_suggestions(trade, ctx)}
    assert "trim_into_strength" in rules      # +1R fires (0.25 default)
    assert "partial_day_window" in rules       # calendar fires (0.50 default)
```

> **RD-decision-dependent assertion (execution-time note):** `test_..._coexists_...` encodes RD Decision C = *distinct labeled rules*. If RD instead rules an explicit **precedence** at plan review, this test MUST be rewritten to assert the ruled behavior (e.g. only `partial_day_window` in-window, `trim_into_strength` suppressed) AND `suggest_partial_day_window` gains the suppression logic (an `and not (r_so_far(...) >= cfg.trim_first_r_trigger)` guard on the +1R rule, or vice-versa). Do NOT ship this test as-is if RD rules precedence.

**Pre/post arithmetic:** `vsts` test: PRE-fix -> `suggest_partial_day_window` absent (`ImportError`); with the rule absent the operator surface is SILENT on this trade (the documented bug — +1R at 0.47R never fires). POST-fix -> `trim_into_strength` still `None` (0.47R < 1.0R, arithmetic exact), `partial_day_window` fires. Distinguishes the fix's whole purpose. `coexists` test: `r_so_far = (112-100)/10 = 1.2R >= 1.0` so `trim_into_strength` fires; Day 3 + close>entry so `partial_day_window` fires -> both present (distinguishes Decision-C distinct-rules from a suppression impl).

- [ ] **Step 2: Run tests to verify they pass** (Tasks 2-3 already landed)

Run: `python -m pytest tests/trades/test_advisory.py -k "vsts or coexist" -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/trades/test_advisory.py
git commit -m "test(trades): Task 4 — VSTS reason-to-exist + coexistence tests"
```

---

## Pre-review full-suite gate (recipe §2)

After Task 4, BEFORE the Codex review, run the WHOLE fast suite and fix any failure to green (cross-cutting/global-invariant tests are not exercised per-task):

```bash
python -m pytest -m "not slow" -q
ruff check swing/
```

Expected: green + ruff clean. If any cross-VM/config-manifest/enum-mirror test breaks (e.g. a test enumerating `StopAdvisoryConfig` fields, or a snapshot of `compute_all_suggestions` rule counts), fix it here so the Codex review converges on a green diff.

---

## Self-Review (run against the brief before Codex)

1. **E1 purely additive:** new function + new config fields + aggregator appends only; `suggest_trim_into_strength` body unchanged (Task 3 guard test proves it); touched files = `swing/config.py` + `swing/trades/advisory.py` + tests ONLY. PASS if no other `swing/` file is modified.
2. **E2 engine-aligned defaults:** window 3-5, 50%, close>entry — Tasks 1-2. Day-counting basis = sessions (Decision A). PASS.
3. **E3 suppression + window-close + coexistence:** `has_been_trimmed` gate (Task 2), window closes after day 5 (`day6_window_closed`), coexistence = distinct rules (Task 4, RD-decision-gated). PASS.
4. **E4 existing render path:** `rule="partial_day_window"` through `AdvisorySuggestion`; no VM/template/page change. PASS.
5. **§3 discriminating tests all present** with pre/post arithmetic, incl. the wide-stop VSTS reason-to-exist test. PASS.
6. **Gotchas:** ASCII message (stdout echo); session-anchor read (forward `as_of` -> last-completed day number, `previous_close` paired); no new base-VM field; no schema. PASS.
7. **Placeholder scan / type consistency:** field names `partial_day_window_start/end`, `partial_day_pct_default`, function `suggest_partial_day_window`, rule string `"partial_day_window"` used identically across all tasks. PASS.

---

## Execution Handoff

Plan complete. Recommended execution: **inline via superpowers:executing-plans** (4 small tasks, one file each on the production side). The executing dispatch MUST: (a) carry the RD plan-review rulings for Decisions A/B/C and adjust Task 4 (and, if precedence is ruled, Task 2) accordingly; (b) run the recipe §3 review-strong + codex-auto-review to convergence on production code; (c) prep the BINDING operator GUI witness (§4 gate 3) — witness BOTH a firing in-window state AND the unseeded default (the seeded-gate-masks-default-state memory).
