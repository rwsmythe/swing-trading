# D79 executing -- CONTINUATION brief (cell 8): the Reviewer B fixes (doc and test only)

**Audience:** a fresh implementer cell with no prior conversation context. The D79 review loop is CLOSED: stopped-and-routed at round 7. The orchestrator's Reviewer B ran on `a6519295`, and every finding is dispositioned. You land four small changes, none of them production code, and run the full suite. **There is NO Reviewer A round and NO Reviewer B round for you to run.**

**These bind:**
1. `C:\Users\rwsmy\swing-trading\docs\d79-exec-dispatch-brief.md` (main `6aef92a4`), sections 2 (TDD, commits, the envelope) and 5 (your return goes to chat only; you NEVER post to a mailbox or run role_mail.py).
2. The exec ledger, sections "Reviewer B" and "RD's rulings on Reviewer B items B-01 and B-02" (from line ~760): `docs/superpowers/plans/2026-10-19-d79-exit-identity.exec-ledger.md` in your worktree. RD's AL texts there are BINDING VERBATIM. Never edit the ledger's block-quoted sections or the orchestrator's sections; append only your cell record.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d79-exec`, branch `d79-exec`, HEAD `61a6fb61`. Diff base `618d7b04`. **Cell:** `implementer-sonnet-high`.

**Stash:** the stash stack is SHARED. Never use a bare `pop`, and never touch the `SB5.5-exec CORRUPTED...` entry. Prefer a temporary WIP commit.

**Commits:** conventional; pathspec commits; no Co-Authored-By; no `--no-verify`; no amend. **No final `-m` paragraph may begin with `Word:`** (git parses it as a trailer). Check `git log -1 --format='%(trailers)'` after EACH commit. If one slips while it is the tip, STOP and return.

## 1. The changes, one commit each

1. **AL-5, its reason restated by replacement** (plan `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md:39`). AL-5's last sentence currently reads "Live incidence is 0 of 19, and after K7.3 nothing produces the shape." Replace it with RD's text from the ledger, verbatim, beginning "Live incidence is 0 of 19. The retention rule produces the shape by design whenever two map entries share an order id ...". Keep the rest of AL-5 unchanged.
2. **AL-13, added after AL-12** in the plan's accepted-limitations list. Use RD's text verbatim, beginning "AL-13, on a one-entry map the sole entry IS the selection (RD K3 precondition (4)) ...". Then add a "Why accepted:" sub-bullet that names RD's ruling (Reviewer B, B-01) and the bank (the signed envelope, AL-6's).
3. **B-05: one test pinning AL-13's width as a fact** (in `tests/web/test_routes/test_d79_exit_identity.py`, near the T5 tests).
   - A claimed POST whose envelope has a one-entry `candidates_map`.
   - The sole entry names order `o9`, while the envelope's top level names `o2` with different values.
   - The radio is omitted, and the typed values are `o9`'s.
   - Assert: the POST records one fill, and its persisted envelope's top-level `schwab_order_id` is `o9`.
   - The docstring says this pins AL-13's accepted width, and that the signed-envelope arc turns it red.
   - It is green on arrival, by design. Prove that it discriminates: temporarily delete the bare one-entry branch at `routes/trades.py` ~:3062-3074 (the `else:` that stamps `selected_index = 0` from the sole entry), and the index-0 inference just above it if the form under test carries per-candidate inputs. Show the test go red, then restore the route byte-for-byte (`git diff` empty for `swing/`). Record both results in the commit body.
   - Build the fixture the way the existing T5 tests build theirs.
4. **B-06:** `tests/trades/test_d79_exit_flags.py::test_t4f_no_second_spelling_of_the_grain` patches `eaf.derives_from` but never asserts it fired.
   - Make the patch a counting stub that still returns False, and assert it was called at least once.
   - Prove it discriminates by mutation: temporarily make `anonymous_fill_matches` skip the `derives_from` call. The test must go red. Restore byte-for-byte.

## 2. Then

1. The FULL fast suite on your final head, backgrounded and read off the saved output: `PYTHONPATH=. python -m pytest -m "not slow" -q -n auto -p no:cacheprovider`.
   - Expected: 15496 passed plus your one new test, 13 skipped.
   - The orchestrator's run on `a6519295` had ONE red under heavy load: `tests/research/test_l2_lock_sys_modules_isolation_regression.py::test_research_l2lock_del_does_not_break_web_route_exception_identity`, a subprocess `TimeoutExpired` at 300 s. That module passes with `-n 0` (5 passed).
   - If any test reds, re-run it in isolation with `-n 0`, and report both results and the run time. Do NOT classify a red you have not reproduced in isolation.
2. `ruff check swing/` clean; `%(trailers)` empty across `618d7b04..HEAD`; `git diff --stat 618d7b04..HEAD -- swing/` unchanged from `a6519295` (you change NO file under `swing/`).
3. Append your cell record to the exec ledger, and commit it.
4. **RETURN** with the commits, the suite counts read off the output, and the two mutation results.

## 3. If anything does not fit

STOP and return. Do not choose for yourself.
