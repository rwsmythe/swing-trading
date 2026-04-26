# Watchlist Sort-By-Tags Brief

**Audience:** Fresh Claude Code instance with no prior conversation context. You are the implementer; the orchestrator drafted this brief and will receive your return report.

**Mission:** Replace the watchlist's purely-proximity-based sort with a three-key composite sort that elevates higher-quality candidates (more flag tags) above proximity-only candidates. The change applies uniformly to the dashboard top-5 and the standalone `/watchlist` page (both render rows from the same source list).

**Expected duration:** ~1.5–3 hours including TDD + adversarial review.

**Prerequisite:** This session runs **after** the QoL UI-polish bundle session (`docs/qol-ui-polish-bundle-brief.md`) returns clean. The bundle session does NOT touch sort logic, so working tree on dispatch is whatever the bundle session left.

---

## §0 — Read first

1. **`CLAUDE.md`** at repo root — particularly the gotcha about `_sort_by_proximity` not having tag context (relevant background).
2. **`swing/web/view_models/dashboard.py`** — read `_sort_by_proximity` (lines 558–563), `_flag_tags` (lines 566–581), and the order in which they're called inside `build_dashboard` (currently sort happens at line 361, flag_tags computed at line 427).
3. **`swing/web/view_models/watchlist.py`** — read `build_watchlist`. Same pattern: sort precedes flag_tags. Both need to be reordered.
4. **`swing/data/models.py`** — `WatchlistEntry` (lines 107–124) and `Candidate` (lines 17–32). Understand the `entry_target` field on watchlist and how candidates contribute the tags.
5. **`docs/orchestrator-context.md`** §"Recent decisions and framings" — the operator-confirmed sort behavior is recorded; do not re-litigate the design.

## §0 — Skill posture

- **Use** `superpowers:test-driven-development`.
- **Use** `copowers:adversarial-critic` after the change lands; iterate to `NO_NEW_CRITICAL_MAJOR`.
- **Do NOT use** `superpowers:brainstorming` — design is settled.
- **Do NOT use** `superpowers:writing-plans` — this brief IS the plan.

---

## Strategic context (compressed)

The watchlist currently sorts purely by `abs(last_close - entry_target) / entry_target` (proximity to pivot). This causes candidates with multiple framework tags (TT✓, VCP✓, A+) but slightly worse proximity to drop below pure-noise candidates with better proximity. With the hypothesis-investigation engine now operational and the operator selecting trades from this surface daily, higher-quality candidates need to surface higher.

The hypothesis-recommendations table on the dashboard is **explicitly out of scope** — its sort is hypothesis-aware (progress, target distance, tripwire) and operator decided to leave it alone for now.

---

## Scope

### In scope

- Replace `_sort_by_proximity(watchlist)` with a new sort that takes flag_tags into account.
- Reorder `build_dashboard` and `build_watchlist` so `flag_tags` is computed BEFORE the sort.
- Add tests for primary / secondary / tertiary sort keys + edge cases.
- Adversarial review on combined diff.

### Out of scope

- **Hypothesis-recommendations table sort.** Untouched per operator decision.
- **Watchlist UI changes** (collapse, columns, etc.) — the previous session covered those; this is sort-only.
- **`Candidate` model changes** or anything in `swing/data/`. Phase 2 isolation applies.
- **New tag types.** This brief uses the existing tags (`TT✓`, `VCP✓`, `A+`); future tag additions are a separate concern.

---

## Binding conventions

- **Branch:** `main`. No feature branches.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.** Likely one commit for the sort-function replacement + reorder, plus separate commits for tests if you split TDD cycles, plus adversarial-review-fix commits.
- **TDD:** failing test first → minimal implementation → green → commit.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green.
- **Phase 2 isolation:** `swing/trades/` and `swing/data/` are read-only.

---

## Sort specification

**Sort key (composite, descending priority):**

1. **Primary: tag count (DESC).** Number of flag tags on the row's ticker. More tags first.
2. **Secondary: tag precedence (DESC).** Operator-confirmed precedence: `A+` > `VCP✓` > `TT✓`. Encode as a numeric score where each tag contributes a position-weighted value; higher score sorts first.
3. **Tertiary: abs(% to pivot) (ASC).** Same as the existing proximity sort. Lower magnitude (closer to pivot) first.

**Tie-breaking:** at full equality across all three keys, sort by ticker (ASC, alphabetical) for determinism. This matches existing tests' implicit expectation that sort is stable.

**Tag precedence encoding:**

```python
# Higher value = higher precedence. A+ implies VCP✓ + TT✓ in practice
# (A+ bucket requires all criteria), but encoding A+=4 makes the order
# robust if framework definitions ever loosen.
_TAG_PRECEDENCE = {"A+": 4, "VCP✓": 2, "TT✓": 1}

def _tag_precedence_score(tags: tuple[str, ...]) -> int:
    return sum(_TAG_PRECEDENCE.get(t, 0) for t in tags)
```

**Why position-weighted (sum-of-values) instead of strict lexicographic?** The natural tag combinations on real candidates are:
- `(A+, VCP✓, TT✓)` — score 7 (full pass)
- `(VCP✓, TT✓)` — score 3 (near-A+ defensible)
- `(TT✓,)` — score 1 (foundational only)
- `()` — score 0
- `(VCP✓,)` — score 2 (degenerate, unlikely in practice)

The sum-of-precedence-values gives the right ordering across all combinations a candidate could realistically have AND survives gracefully if a future tag is added (just assign it a precedence value and the sort still works).

**Why not just sort by tag count alone?** Because count=2 has two possible sets — `(VCP✓, TT✓)` vs `(A+, TT✓)` (degenerate but well-defined). Precedence breaks this tie correctly: `A+` carries more weight than `VCP✓`.

---

## Implementation

### Task: replace `_sort_by_proximity` with `_sort_watchlist`

**File:** `swing/web/view_models/dashboard.py`

**New function** (replaces `_sort_by_proximity`):

```python
_TAG_PRECEDENCE = {"A+": 4, "VCP✓": 2, "TT✓": 1}


def _tag_precedence_score(tags: tuple[str, ...]) -> int:
    """Sum-of-precedence-values across a row's flag tags.

    Higher score sorts first. Used as the secondary sort key in
    `_sort_watchlist`. Position weights chosen so that the natural
    combinations (A+/VCP/TT, VCP/TT, TT alone, none) order correctly
    AND adding a new tag in the future requires only assigning a
    precedence value — the sort survives.
    """
    return sum(_TAG_PRECEDENCE.get(t, 0) for t in tags)


def _abs_proximity(w: WatchlistEntry) -> float:
    """abs(% to pivot). Returns +inf when pivot or close is missing so
    those rows sort last on the proximity key."""
    if w.entry_target is None or w.last_close is None:
        return float("inf")
    return abs(w.last_close - w.entry_target) / max(w.entry_target, 1e-6)


def _sort_watchlist(
    watchlist: list[WatchlistEntry],
    flag_tags: Mapping[str, tuple[str, ...]],
) -> list[WatchlistEntry]:
    """Three-key composite sort: tag count (DESC), tag precedence (DESC),
    abs(% to pivot) (ASC), then ticker (ASC) for determinism.

    Operator-confirmed precedence: A+ > VCP✓ > TT✓. Tickers without
    candidate data appear with empty tags tuple → score 0 → sort last
    among the no-tag group, ordered by proximity.
    """
    def key(w: WatchlistEntry):
        tags = flag_tags.get(w.ticker, ())
        return (
            -len(tags),                    # tag count DESC
            -_tag_precedence_score(tags),  # tag precedence DESC
            _abs_proximity(w),             # proximity ASC
            w.ticker,                      # ticker ASC (determinism)
        )
    return sorted(watchlist, key=key)
```

**Note:** Keep `_sort_by_proximity` exported for any external callers OR confirm by grep there are no external callers. Recommended: `git grep -n "_sort_by_proximity"` — if all references are inside `swing/web/`, replace fully. If any test or external module imports it directly, either retain it as a thin wrapper or update the import sites in the same commit.

### Task: reorder `build_dashboard` so flag_tags is computed before sort

**File:** `swing/web/view_models/dashboard.py`, function `build_dashboard`.

**Current order** (around lines 354–428):
1. `candidates_by_ticker = {c.ticker: c for c in candidates}` (line 354)
2. `watch_sorted = _sort_by_proximity(watchlist)` (line 361) ← sort BEFORE flag_tags
3. `top5 = watch_sorted[:5]` (line 362)
4. ... (price + OHLCV + open-trade VM build)
5. `flag_tags = _flag_tags(candidates_by_ticker)` (line 427) ← computed AFTER

**New order:**
1. `candidates_by_ticker = {c.ticker: c for c in candidates}`
2. `flag_tags = _flag_tags(candidates_by_ticker)` ← MOVED EARLIER
3. `watch_sorted = _sort_watchlist(watchlist, flag_tags)` ← uses flag_tags
4. `top5 = watch_sorted[:5]`
5. ... (rest unchanged)

The line-for-line move should be straightforward; verify no other code between the original positions of `_flag_tags` and the sort consumes `candidates_by_ticker` in a way that's order-sensitive (it shouldn't — `candidates_by_ticker` is a frozen dict from a frozen list).

### Task: reorder `build_watchlist` so flag_tags is computed before sort

**File:** `swing/web/view_models/watchlist.py`, function `build_watchlist`.

**Current order** (around lines 47–89):
1. Inside `with conn:` snapshot, `rows = _sort_by_proximity(list_active_watchlist(conn))` (line 49) ← sort BEFORE candidates
2. ... candidate loading ...
3. `by_ticker = {c.ticker: c for c in candidates}` (line 78)
4. `flag_tags=_flag_tags(by_ticker)` passed into VM construction (line 89)

**New order:**
1. Inside `with conn:` snapshot, load `rows = list_active_watchlist(conn)` first (no sort yet)
2. Load candidates (existing block)
3. After exiting `with conn:`, build `by_ticker = {c.ticker: c for c in candidates}` and `flag_tags = _flag_tags(by_ticker)`.
4. NOW sort: `rows = _sort_watchlist(list(rows), flag_tags)`.
5. Pass sorted `rows` into the VM construction.

**Snapshot integrity:** The original code had `rows = _sort_by_proximity(...)` inside the `with conn:` block. The sort doesn't actually need the connection — only the read of `list_active_watchlist(conn)` does. Moving the sort outside the `with conn:` block is safe and correct.

---

## Tests

Write failing tests first per TDD. Test discipline per `feedback_regression_test_arithmetic.md` — each test must distinguish pre-fix from post-fix.

**Location:** `tests/web/view_models/test_dashboard.py` (or wherever `_sort_by_proximity` is currently tested — find via grep first).

### Test cases (minimum)

1. **Primary key — tag count:** Two tickers with identical proximity (say both 5% from pivot), one with 3 tags, one with 1 tag. Assert 3-tag ticker comes first.
2. **Secondary key — tag precedence:** Two tickers with identical proximity AND identical tag count (both 2 tags), one tagged `(A+, TT✓)` and one tagged `(VCP✓, TT✓)`. Assert A+ ticker comes first. (Note: `(A+, TT✓)` is degenerate per current `_flag_tags` logic — A+ bucket implies all tags. Construct the test by directly providing a flag_tags mapping that has this asymmetry — bypass the default `_flag_tags` if needed.)
3. **Tertiary key — proximity:** Two tickers with identical tags (both `(TT✓,)`, count 1, score 1), one at 1% proximity, one at 8%. Assert 1% ticker comes first.
4. **Determinism — alphabetical tiebreaker:** Two tickers with identical tags, identical proximity. Assert sort is stable / alphabetical (e.g., AAPL before MSFT).
5. **No-tags fallback:** Tickers with empty tag tuples sort by proximity alone among themselves, AFTER any tagged ticker. Assert this.
6. **Missing entry_target / last_close:** `WatchlistEntry` with `entry_target=None` sorts last on the proximity key. Combine with tag presence — a no-tag entry with None proximity should sort after a no-tag entry with valid proximity, and both should sort after any tagged entries.

### Pre-fix vs post-fix discriminator (per memory file discipline)

For each test: confirm that the assertion fails when the file uses `_sort_by_proximity` (pre-fix) and passes when it uses `_sort_watchlist` (post-fix).

**Concrete example for test 1:**
- Pre-fix: `_sort_by_proximity([A, B])` returns `[A, B]` (or `[B, A]`) based on proximity alone — tag count not consulted.
- Construct fixtures so that A has higher proximity AND fewer tags, B has lower proximity AND more tags.
- Pre-fix sort: `[B, A]` (better proximity wins).
- Post-fix sort: `[B, A]` ALSO — wait, that's the same outcome.

**Better discriminator:** A has BETTER proximity (closer to pivot) AND FEWER tags; B has WORSE proximity AND MORE tags.
- Pre-fix sort: `[A, B]` (better proximity wins).
- Post-fix sort: `[B, A]` (more tags wins).

Verify your fixture explicitly produces this asymmetry.

### Update existing `_sort_by_proximity` tests

If existing tests assert specific orderings under the old sort, they'll break under the new sort — that's expected and correct. Either:
- Update them to use `_sort_watchlist` and assert the new ordering, OR
- Delete them if they're now redundant with new tests.

Document which existing tests you updated and why in the return report.

---

## Adversarial review

After commits land, run `copowers:adversarial-critic`. Iterate to `NO_NEW_CRITICAL_MAJOR`.

**Standing watch items:**

- Does each new test's arithmetic distinguish pre-fix from post-fix? Verify by mentally / explicitly running both.
- Is `_TAG_PRECEDENCE` keyed on the exact same tag strings that `_flag_tags` emits? (`TT✓`, `VCP✓`, `A+`. Note the tags use Unicode checkmark `✓`, not ASCII `v`.) Mismatched keys would silently score every tag at 0.
- Does `_sort_watchlist` survive a None or empty `flag_tags` mapping (e.g., when no candidates exist)? Defensive-default with `flag_tags.get(ticker, ())`.
- Does the reorder in `build_dashboard` and `build_watchlist` preserve the snapshot integrity of the read transaction (`with conn:`)? Sort doesn't need DB; it should be safe outside `with conn:`.
- Do any code paths OTHER than the dashboard/watchlist VMs consume `_sort_by_proximity` directly? Grep for callers; if external, either keep a wrapper or update call sites in the same commit.
- Does the determinism tiebreaker (sort by ticker) actually fire in any test? If never tested, the determinism claim is unverified.
- Does the new sort interact correctly with the `top5 = watch_sorted[:5]` slice on the dashboard? Tag-rich candidates should now occupy top-5 slots; verify by writing a test that asserts top-5 contents match expected ordering on a mixed input.

---

## Done criteria

- `_sort_watchlist` (and helpers) shipped, replacing `_sort_by_proximity` use sites.
- `build_dashboard` and `build_watchlist` reordered so flag_tags is computed before sort.
- Test count up by N (track this); fast suite green.
- `ruff check swing/` shows no NEW violations.
- Adversarial-review verdict: `NO_NEW_CRITICAL_MAJOR`.
- Manual verification documented in return report: visit `/` and `/watchlist` in a running `swing web` session; confirm tagged candidates appear above untagged candidates with worse proximity but better tag count.

---

## Return report format

```
## Watchlist Sort-By-Tags Return Report

### Commits
- <sha>: <conventional commit title>
- <sha>: <next>
- ...

### Sort behavior summary
- Sort key: [restate the three-key sort + tiebreaker]
- Tag precedence: [restate the encoding]

### Test count delta
Before: <N>; After: <N+M>; Delta: +M.

### Existing tests updated / removed
- <test_name>: <update reason / outcome>
- ...

### Adversarial review
- Round 1: <findings>; addressed in <sha>.
- Final verdict: NO_NEW_CRITICAL_MAJOR after R<N>.

### Manual-verification notes
[Browser observation: tagged-vs-untagged ordering on /watchlist and dashboard top-5.]

### Judgment calls / deviations
[Anything decided differently from the brief, with rationale.]

### Follow-ups flagged
[Anything noticed but out of scope. Goes to phase3e-todo.md at next housekeeping.]
```

---

## If you get stuck

- **A sort test passes pre-fix AND post-fix:** the fixture doesn't distinguish the two sort algorithms. Construct an asymmetric fixture (better-proximity-fewer-tags vs worse-proximity-more-tags). See "Pre-fix vs post-fix discriminator" above.
- **`_flag_tags` emits different tag strings than `_TAG_PRECEDENCE` expects:** read `_flag_tags` (dashboard.py:566–581) and verify the exact strings. Note the Unicode checkmark `✓`.
- **An existing call site of `_sort_by_proximity` lives outside `swing/web/`:** that's a discovery — flag in return report and decide whether to update or wrap.
- **A test for the determinism tiebreaker keeps failing:** Python's `sorted()` is stable, so identical keys preserve insertion order. If your fixture inserts the tickers in non-alphabetical order, the tiebreaker on ticker name in the key tuple is what gives alphabetical determinism. Verify the key tuple ends with `w.ticker`.
- **An adversarial-review finding is architecturally larger than this brief:** flag in return report; do not expand scope.
