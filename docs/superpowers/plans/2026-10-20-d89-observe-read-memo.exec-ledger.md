# D89 (observe's per-step read memo) -- executing ledger

**Plan:** `docs/superpowers/plans/2026-10-20-d89-observe-read-memo.plan.md` (cleared at `e1e1b442` plus the K-8 correction at `6bd6e347`).
**Brief:** `docs/d89-observe-read-memo-exec-dispatch-brief.md` (main `4cf52e35`).
**Branch:** `d89-memo`, executing from `6bd6e347`.
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d89-memo\exec\` (`round<N>\` = the Reviewer A rounds; `mutations\`; the `t1_*`, `suite_*` and `w07_*` files).

## 1. Commits

| sha | subject | `%(trailers)` |
|---|---|---|
| `20405b66` | `feat(pipeline): T1 -- observe's per-step read memo after a non-raising populate (D89)` | empty |
| `7cdfaeb8` | `style(tests): T1 -- D89 memo tests take the shared fixture by module attribute and sort imports (ruff I001, F811)` | empty |

The second commit is a deviation from the plan's ONE T1 commit: the brief's ruff gate (zero NEW findings on touched test files) found seven in the new test file (I001 once, F811 at six test parameters, because the file imported `tmp_db_at_head` by name). No amend is allowed, so it is a new commit. It changes no assertion.

## 2. T1, RED then GREEN (read off the saved output)

RED (`exec\t1_red.txt`, before any `runner.py` edit): `8 failed in 7.92s`.

| test | RED line, as saved |
|---|---|
| T-H1 | `test_observe_read_memo.py:144` `assert 3 == 2` (reads 3) |
| T-H2 | `:166` `assert 3 == 2` (reads 3) |
| T-C3 | `:188` `assert 3 == 1` (reads 3) |
| T-E | `:212` `assert 9.9 == 9.0` (d2 re-reads 9.9: the declared difference) |
| T-key | `:226` `TypeError: _bar_for_date() got an unexpected keyword argument 'memo'` |
| T-lifetime | `:246` `KeyError: 'resolve_reads'` |
| T-load | `:268` the key set lacks `'resolve_reads'` |
| N-V | `test_observe_read_memo_neutrality.py:220` `KeyError: 'resolve_reads'`, at assertion (3); (1), (2) and the no-memo read count 8 passed before it |

GREEN (`exec\t1_green.txt`): `8 passed in 6.59s`. Then `tests/pipeline` (`exec\t1_pipeline_dir.txt`): `449 passed, 32 warnings in 112.72s`.

Two instrument notes from writing the harness:
- The scripted `_fetch_bars_window` runs inside the populate's `except Exception`, so a raise there would be swallowed. A script overrun is therefore recorded on the cache and asserted by `_drive` after the step.
- N-V pops `resolve_reads` with a default, so that pre-fix (2) holds and the RED lands at (3), as the plan states. (3) asserts the key's presence.

The two comment lines the plan adds were wrapped onto two lines each (E501 at 100 columns). Their text is unchanged.

## 3. Gates before Reviewer A

**Full fast suite** (`python -m pytest -m "not slow" -q -n 8 -p no:cacheprovider`, at `20405b66`; `exec\suite_pre_review.txt`): `15518 passed, 13 skipped, 1322 warnings in 859.06s (0:14:19)`, `rc=0`. The style commit `7cdfaeb8` came after; the two new files re-ran `8 passed` on it. The suite runs again on the final head.

**Ruff:** `ruff check swing/` -> `All checks passed!`. The two new test files -> `All checks passed!` (after `7cdfaeb8`).

**Closure greps** (at `7cdfaeb8`):
- `grep -n -i "zero schwab" swing/pipeline/runner.py` -> no output, rc 1.
- `grep -rn --include=*.py "observe_load" swing/` -> `runner.py:3242` (the entry-reset comment) and `runner.py:3361` (the entry). Two lines, as K-6 states.
- `grep -n "memo" swing/pipeline/runner.py` -> AT ITS STATED FORM THE CLAIM DOES NOT HOLD LITERALLY. Five hits sit outside the three functions: `:1364`, `:1992`, `:1999`, `:2696`, `:4723`. Each is the substring `memo` inside `in-memory`, and all five exist on the base (`git show eed4bb2d:swing/pipeline/runner.py | grep -n memo` returns the same five plus `in_memory_hit` at :3317 and :3325). The grep that tests the plan's property, `grep -nE "memo([^r]|$)"`, returns 20 lines (corrected at the round-1 gate: this line first said 22, a miscount; section 6 holds the output), all inside `_observe_memo_key` (:3073-3076), `_bar_for_date` (:3079-3171) or `_step_pattern_observe` (:3192-3366). Reported, not chosen around.
- `git diff --stat main...HEAD -- swing/data swing/web swing/trades` -> empty. `git diff --stat main...HEAD -- swing` -> `swing/pipeline/runner.py | 64 +++++++++++++++++++++++++++++++++++++++---------` only.
- `git diff --stat 31a293b4..HEAD -- swing/data swing/trades swing/web scripts research` -> empty.

**Mutations** (`exec\mutations\run_mutations.py`, output `mutations.out.txt`). Each is a scratch edit of `runner.py`, run over the two new files, then `git checkout -- swing/pipeline/runner.py`. `git diff --exit-code swing` returned 0 after every one, and again at the end.

| id | scratch edit | RED (required in bold) |
|---|---|---|
| M1 | `if memo is not None and populate_ok:` -> `if memo is not None:` | **T-H1**, **T-H2**, **N-V (3)** |
| M2 | `memo = _D89_M2_MEMO` (a module-level dict) | **T-lifetime**; also T-H2, T-E, T-load (cross-test carry-over within the process) |
| M3 | the populate runs only when `memo is None or key not in memo` | **T-load**, **N-V**; also T-H1, T-C3, T-E |
| M4 | `memo[key] = (df, {})` | **N-V**; also T-H1, T-H2, T-E, T-lifetime, T-load |
| M5 | `_observe_memo_key` returns `(ticker,)` | **T-key** only |
| C2 (T1 table) | write only when `observation_date in provenance` | **T-C3**; also T-lifetime, N-V |
| E2 (T1 table) | `key in memo and populate_ok` | **T-E** only |

M1 quoted for the merge report (T-H1 RED, `mutations.out.txt`):

```
-        if memo is not None and populate_ok:
+        if memo is not None:
E   ValueError: not enough values to unpack (expected 1, got 0)
tests\pipeline\test_observe_read_memo.py:140: ValueError
E   assert (9.0 == 9.5)
tests\pipeline\test_observe_read_memo.py:167
E   assert 3 == 4
tests\pipeline\test_observe_read_memo_neutrality.py:221
FAILED tests/pipeline/test_observe_read_memo.py::test_raise_then_heal_later_detections_observe
FAILED tests/pipeline/test_observe_read_memo.py::test_raise_over_archived_yfinance_then_schwab_write_outranks
FAILED tests/pipeline/test_observe_read_memo_neutrality.py::test_observation_rows_identical_with_and_without_the_memo
3 failed, 5 passed
```

T-H1's line 140 is `(row,) = _rows(conn, d)` for d2: under M1, d1's empty pair is memoized and d2 gets no row.

**W5 (ii) replay and W7 byte-equality** (`exec\w07_replay.py` = `round0\p07_replay.py` plus two modes; run over `round0\iters195.json` and the p03 snapshot copied fresh into the scratchpad per mode):

| mode | resolve calls | rows / skips | telemetry |
|---|---|---|---|
| `merged_nomemo` (`R._bar_for_date(cfg, oc, t, OBS)`) | 7,139 | 6,934 / 205 | `in_memory_hit` 7,139, `fetch_window` 0 |
| `merged_memo` (`memo=memo`, ONE dict) | **248** | 6,934 / 205 | `in_memory_hit` 7,139, `fetch_window` 0 |

Expected: 7,139 against 248. Measured: the same. `round0\p11_compare_rows.py` (`exec\w07_compare.out.txt`): `merged_memo` byte-equal to `merged_nomemo` (0 differing lines of 7,139), and both byte-equal to round 0's pre-merge `p07_rows_today.jsonl`. The walls (539,339 ms and 29,499 ms) were taken under a concurrent Codex round and are not a W4 measurement.

## 4. Round table (Reviewer A, `strong`)

| round | tier / model / effort | `tokens used` | verdict token | `^ERROR` | crit / major / minor | new / reopened | reverts | depth (orchestrator fills) | transcript (path, bytes) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `strong` / `gpt-5.6-sol` / `high` (both equal `~/.codex/strong.config.toml`'s declared values) | 349,841 | clean token, anchored count 2 (codex-cli 0.162.1 prints the final message twice); found token 0 | 0 | 0 / 0 / 2 | 2 / 0 | 0 |  | `C:/Users/rwsmy/swing-data/review-transcripts/d89-memo/exec/round1/review.txt`, 880,952 bytes |

Spend, Reviewer A: 349,841.

## 5. Rounds

### Round 1 (counted; `strong`)

**Invocation.** `exec\round1\run_r1.sh` (LF, checked with `file`), run as `wsl.exe bash -lc 'bash /mnt/c/.../run_r1.sh'`: `cd` into the worktree, then `cat prompt.md bundle.md | codex exec -p strong -s read-only --skip-git-repo-check -`, output and exit code to pre-created files. Codex-cli 0.162.1. REPO ACCESS: the working directory was the worktree (`-s read-only`).

Inputs: `prompt.md` (8,038 bytes: the envelope, L-1 to L-4 with their reasons and challenge invited, the nine-item checklist, the two verdict tokens DESCRIBED inline, the content-filter clause) and `bundle.md` (177,912 bytes: the plan; the plan ledger CUT at line 201, before its round table, plus its section "Plan-stage director reads" (lines 294-341); the plan's executing-review excerpts, line-numbered; the diff `31a293b4..HEAD -- swing tests` at `7cdfaeb8`). `grep -cE "^(NO_NEW_CRITICAL_MAJOR|NEW_CRITICAL_MAJOR_FOUND)"` = 0 on both files. `grep -c "Round table\|### Round 1\|Codex response"` on the bundle = 0. `.copowers-findings.md` was moved out of the worktree for the round and restored after it.

**The five assertions:**
1. Banner `model: gpt-5.6-sol`, equal to the `strong` profile's declared `model`.
2. Banner `reasoning effort: high`.
3. `grep -c '^ERROR'` = 0.
4. `grep -c '^tokens used'` = 1 (349,841). The process had exited: `exit.txt` reads `rc=0`, written by the runner after codex returned, and `pgrep -af 'codex exec'` in WSL found no process.
5. Clean token, anchored count 2 (the duplicated final message); found token 0.

**No-prior-read check.** Method: every command line following an `exec` marker in the transcript was listed (`awk '/^exec$/{getline; print}'`, 20 commands). They read `CLAUDE.md`, `docs/orchestrator-context.md`, `swing/` and `tests/` files, and one `rg` over the whole tree that EXCLUDED `docs/superpowers/plans/**`, `comms/**`, `swing-data/**`, `review-transcripts/**`, `.codex*` and `.copowers*` by glob. None read a forbidden path. The `grep` for `copowers|.codex|docs/superpowers/plans|comms/|swing-data|review-transcripts|ledger` after the echoed input hits only text echoed from `CLAUDE.md` and `docs/orchestrator-context.md`.

**Content filter:** the response states none.

**Codex response** (the final message, transcript lines 7490-7531, verbatim; block-quoted so that no verdict token is line-initial in a repo file):

> codex
> ## Findings
>
> - **Minor — NEW:** `resolve_reads` is not exact on a pre-resolve exception. The step increments on a predicted miss before calling `_bar_for_date` ([runner.py:3290](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3290)), but the completed-session guard can raise before `resolve_ohlcv_window` is reached ([runner.py:3111](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3111), [runner.py:3148](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3148)). The local counter would be 1 while actual resolver calls are 0. In the production runner the whole step then aborts and no `observe_load` entry is emitted, limiting impact, but checklist item 6’s “every path” claim is false. No new test exercises this path; moreover T-load discards its independent counter ([test_observe_read_memo.py:267](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:267)) despite the module’s every-test counter claim ([test_observe_read_memo.py:10](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:10)).
>
> - **Minor — NEW:** Most new memo tests use the live clock instead of pinning the completed-session clock. `_drive` patches only `lease_data_asof` ([test_observe_read_memo.py:104](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:104)), while the exercised production path calls `last_completed_session(datetime.now())` ([runner.py:3111](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3111)). This violates the project’s frozen-clock convention for newly added date/session tests. The fixed 2026 dates are already historical, so practical flake risk is low. N-V correctly pins this dependency ([test_observe_read_memo_neutrality.py:129](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo_neutrality.py:129)).
>
> ## Checklist
>
> 1. **Holds.** `populate_ok` starts true, is cleared only by a caught populate exception, and gates the write of the unmodified pair before any bar/provenance selection ([runner.py:3128](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3128), [runner.py:3152](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3152)). Empty, missing-date, and missing-provenance results are therefore memoized after every non-raising populate.
>
> 2. **Holds.** `get_or_fetch` precedes the memo lookup and is unconditionally attempted on every completed-date call, including memo hits ([runner.py:3129](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3129), [runner.py:3145](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3145)).
>
> 3. **Holds.** A present key selects the stored pair regardless of `populate_ok`; the resolver exists only in the `else` branch ([runner.py:3145](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3145)).
>
> 4. **Holds.** The shared helper returns the raw `(ticker, observation_date)` tuple and is used by both `_bar_for_date` and the step pre-check ([runner.py:3073](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3073), [runner.py:3144](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3144), [runner.py:3290](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3290)).
>
> 5. **Holds.** The memo is an ordinary local initialized inside `_step_pattern_observe`; there is no default, module, or cache-attached state ([runner.py:3238](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3238)).
>
> 6. **Fails**, narrowly, for the pre-resolve exception described above. It is exact on normal completion, memo hits/misses, populate raises, shed/idempotency skips, and the wrapper-created `memo=None` world ([runner.py:3257](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3257), [runner.py:3290](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3290), [test_observe_read_memo_neutrality.py:162](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo_neutrality.py:162)).
>
> 7. **Holds.** The docstring accurately covers TTL hits, the installed ladder, the no-client `read_or_fetch_archive` branch, and the memo rule ([runner.py:3081](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:3081)). The dependencies agree: ladder hook installation at [runner.py:509](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:509), ladder-less construction at [runner.py:861](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/pipeline/runner.py:861), TTL hit at [ohlcv_cache.py:219](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/web/ohlcv_cache.py:219), and no-ladder archive read at [ohlcv_cache.py:283](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/web/ohlcv_cache.py:283).
>
> 8. **Holds for archive content.** Every default resolver call invokes migration ([ohlcv_archive.py:1020](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/data/ohlcv_archive.py:1020)); old-only converges by copying once, while both-exist converges through the content-equality return ([ohlcv_archive.py:1264](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/data/ohlcv_archive.py:1264), [ohlcv_archive.py:1336](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/data/ohlcv_archive.py:1336)). With no intervening writer, removing later resolver calls does not change archive content.
>
> 9. **Holds by code-path and arithmetic review.**
>
>    - T-H1 fails pre-change on missing `resolve_reads`; M1 memoizes the first empty pair and suppresses both healed rows ([test_observe_read_memo.py:127](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:127)).
>    - T-H2 fails pre-change on the missing metric; M1/C1 retain yfinance 9.0 instead of Schwab 9.5 ([test_observe_read_memo.py:150](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:150)).
>    - T-C3 kills C2 through the required one-versus-three read count ([test_observe_read_memo.py:172](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:172)).
>    - T-E’s negative TTL makes both lookups miss under the real cache comparison; E2 rereads 9.9 and fails ([ohlcv_cache.py:221](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/swing/web/ohlcv_cache.py:221), [test_observe_read_memo.py:194](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:194)).
>    - T-key kills ticker-only M5 because the first date-anchored frame cannot supply the second date ([test_observe_read_memo.py:221](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:221)).
>    - T-lifetime kills module-level M2 with the externally added 05-29 row ([test_observe_read_memo.py:235](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:235)).
>    - T-load kills M3 because skipping the second AAA populate changes `in_memory_hit` from 1 to 0 ([test_observe_read_memo.py:258](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:258)).
>    - N-V has correct arithmetic: no-memo 8; memo `AAA 1 + NOB 1 + RSE 2 = 4`. It kills M1 at 3 reads, M3 through cache telemetry, and M4 through the AAA row count ([test_observe_read_memo_neutrality.py:201](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo_neutrality.py:201)).
>    - The swallowed-assertion hazard is handled for script overruns: `_fetch` records the overrun and returns `None`, and `_drive` asserts the side channel after the step ([test_observe_read_memo.py:73](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:73), [test_observe_read_memo.py:110](/mnt/c/Users/rwsmy/swing-trading/.worktrees/d89-memo/tests/pipeline/test_observe_read_memo.py:110)).
>
> I found no neutrality break outside H3/H4, no mutation or aliasing of the memoized pair, and no unsoundness in the accepted-limitation reasoning. I did not execute tests because the review explicitly granted read access and prohibited writes; the assessment above is static. No provider safety layer refused or rewrote any part of the prompt or response.
>
> NO_NEW_CRITICAL_MAJOR
> tokens used
> 349,841

**Adjudication (dispositions PROPOSED; the orchestrator rules):**
- **R1-01 (minor), `resolve_reads` on a pre-resolve exception.** The finding is correct about the counter and agrees on impact. The only pre-resolve raise in `_bar_for_date` is the L3 completed-session guard (`runner.py:3111-3117`). A raise there propagates out of `_step_pattern_observe` before the `observe_load` entry is appended (`:3359-3366`), so no over-count reaches the record. CHARC's plan-stage read states exactly this. A raise inside `resolve_ohlcv_window` itself has the same effect. Proposed: **DECLINED** for code, on that ground. Any code change here would go beyond the cleared plan.
  - Its sub-point is a real gap against the plan: T-load does not assert the independent counter, while AL-8 says every test does. Proposed: **FIX** without a round. In `test_observe_load_gains_resolve_reads_and_loses_nothing`, bind `reads = _count_resolve(monkeypatch)` and assert `reads["n"] == 2`. It is test-only and brings the test to the plan as written.
- **R1-02 (minor), the live clock in the memo tests.** The memo tests rely on `_OBS = 2026-05-29` being a completed session under the real clock. They also rely on it being at or before `_write_archive_atomic`'s cutoff. Both hold for any clock after that date. The same unpinned shape is in `test_observe_load_instrumentation.py`, the plan's named precedent for the populate stub; that test patches `lease_data_asof` only. The plan's harness does not pin the clock. Proposed: **DECLINED**, on the ground that the dates are historical and the plan's harness is followed as written. If the orchestrator prefers to pin, the shape is `test_observe_remediation.py:35-38`: patch `arch._last_completed_session_today` and `runner.last_completed_session` to a fixed date at or after `_OBS`. That is a test-only change.

**Verdict:** clean at round 1, the first round. Under the executing criterion the loop ENDS here. Post-verdict minors are fixed without another round, and the full suite on the final head is their verification.

## 6. Orchestrator rulings at the round-1 gate (author: the orchestrator)

> R1-01: the CODE change is DECLINED. The L3 guard's raise propagates out of the step before the observe_load entry is appended, so the pre-call count can never reach the record; CHARC's plan-stage read says the same, and a code change would go beyond the cleared plan. The TEST fix is ACCEPTED, test-only, with no new round: T-load binds `reads = _count_resolve(...)` and asserts `reads["n"] == 2`, which pins the independent counter AL-8 names.
> R1-02: DECLINED. `_OBS` is historical, the named precedent `test_observe_load_instrumentation.py` has the same unpinned shape, and the plan does not pin the clock. Recorded as a known test-shape choice.
> The `memo` closure grep: the narrowed form `grep -nE "memo([^r]|$)"` is ACCEPTED as the instrument correction. The plan's literal form matches the pre-existing substring "in-memory" at 5 sites on base. Record both outputs.
> Round 1 counts as CONVERGED: the first clean verdict, with post-verdict minors fixed and no new round.

### The `memo` closure grep, both outputs (at `7cdfaeb8`; `runner.py` is unchanged after it)

The plan's literal form, `grep -n "memo" swing/pipeline/runner.py`:

```
1364:    ``data_asof_date`` read by ``run_id``, plus the in-memory ``run_warnings``),
1992:            # Test-stub path: single-connection in-memory test fixtures
1999:                # in-memory test stub -- not a production path.
2696:        #   - candidate_by_ticker = the in-memory candidate rows (ZERO new
3073:def _observe_memo_key(ticker: str, observation_date: str) -> tuple[str, str]:
3074:    """The observe step's per-step read-memo key (D89): the ticker exactly as
3080:                  memo: dict | None = None):
3096:    ``memo`` (D89): the observe step passes one dict per step call, keyed by
3097:    ``_observe_memo_key``. When the key is present, step 2 selects from the
3098:    memoized ``(df, provenance)`` pair and does not read the archive, whatever
3101:    or no bar). ``memo=None`` reads on every call and stores nothing.
3127:    #    without raising (the D89 memo write condition).
3141:    # With a memo (D89): a present key is selected from, never re-read; an
3144:    key = _observe_memo_key(ticker, observation_date)
3145:    if memo is not None and key in memo:
3146:        df, provenance = memo[key]
3152:        if memo is not None and populate_ok:
3153:            memo[key] = (df, provenance)
3238:    # D89 per-step read memo: _observe_memo_key -> the (df, provenance) pair
3240:    memo: dict = {}
3290:        if _observe_memo_key(det.ticker, observation_date) not in memo:
3291:            _resolve_reads += 1  # a memo miss: this call reads the archive
3293:                            memo=memo)
3355:    # archive/network; in_memory_hit = TTL hits.
3356:    # resolve_reads = resolve_ohlcv_window calls this step made (memo misses, D89).
3364:        "in_memory_hit": _tele.get("in_memory_hit", 0),
4723:      2. _finviz_fetch_core (in-memory fetch + normalize + signature).
```

The accepted narrowed form, `grep -nE "memo([^r]|$)" swing/pipeline/runner.py`, returns 20 lines:

```
3073:def _observe_memo_key(ticker: str, observation_date: str) -> tuple[str, str]:
3074:    """The observe step's per-step read-memo key (D89): the ticker exactly as
3080:                  memo: dict | None = None):
3096:    ``memo`` (D89): the observe step passes one dict per step call, keyed by
3097:    ``_observe_memo_key``. When the key is present, step 2 selects from the
3098:    memoized ``(df, provenance)`` pair and does not read the archive, whatever
3101:    or no bar). ``memo=None`` reads on every call and stores nothing.
3127:    #    without raising (the D89 memo write condition).
3141:    # With a memo (D89): a present key is selected from, never re-read; an
3144:    key = _observe_memo_key(ticker, observation_date)
3145:    if memo is not None and key in memo:
3146:        df, provenance = memo[key]
3152:        if memo is not None and populate_ok:
3153:            memo[key] = (df, provenance)
3238:    # D89 per-step read memo: _observe_memo_key -> the (df, provenance) pair
3240:    memo: dict = {}
3290:        if _observe_memo_key(det.ticker, observation_date) not in memo:
3291:            _resolve_reads += 1  # a memo miss: this call reads the archive
3293:                            memo=memo)
3356:    # resolve_reads = resolve_ohlcv_window calls this step made (memo misses, D89).
```

Every one is inside `_observe_memo_key` (:3073-3076), `_bar_for_date` (:3079-3171) or `_step_pattern_observe` (:3192-3366). On base `eed4bb2d` the literal form returns the five `in-memory` sites plus `in_memory_hit` at :3317 and :3325.

### Post-verdict fix

- `a12abd16` `test(pipeline): D89 R1-01 -- T-load asserts the independent resolve counter`, test-only: `_count_resolve(monkeypatch)` becomes `reads = _count_resolve(monkeypatch)`, and `assert reads["n"] == 2` is added. The two new files: `8 passed`. `ruff check` on the file and on `swing/`: `All checks passed!`. Trailers empty.
- R1-02: no change, per the ruling.

### Final-head suite

`python -m pytest -m "not slow" -q -n 8 -p no:cacheprovider` at `a12abd16` (the file's first line records the sha; `exec\suite_final_head.txt`): `15518 passed, 13 skipped, 1322 warnings in 799.64s (0:13:19)`, `rc=0`. This ledger commit, which follows, is docs-only.

## 7. Outcome

**CONVERGED at round 1.** One counted Reviewer A round (`strong`, 349,841 tokens): the first clean verdict, two minors, R1-01's test half fixed after the verdict, no new round. Reviewer B is the orchestrator's.
