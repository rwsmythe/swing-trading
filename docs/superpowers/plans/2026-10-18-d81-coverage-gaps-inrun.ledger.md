# D81 rider -- the in-run coverage_gaps monitor sees its own run -- ledger

**Commissioned:** operator, 2026-10-18, "concur with the fix" (RD courier `20261018T235613Z`).
**Brief:** CHARC's dispatch brief `docs/phase22-rider-d81-coverage-gaps-inrun-dispatch-brief.md` @ `b9fb92d3`. The orchestrator's duplicate draft was retired at `eab23a95`.
**Worktree:** `.worktrees/d81-coverage-gaps`, branch `d81-coverage-gaps`, base `eab23a95`.
**Cell:** `implementer-sonnet-high`. Depth 228,902, including the B-minor resume.
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d81-coverage-gaps\`.

## Execution

| commit | what | RED on the unmodified code |
|---|---|---|
| `484e9fd7` | C1 + C3 (monitor): `live_run` threaded into both ledger readers through one filter body `_skip_pairs_for_run`; helper `pipeline_run_asof` | `TypeError: ... unexpected keyword argument 'live_run'` |
| `1f4614d5` | C2 + C3 (step): the step reads its own row's asof by `run_id` and passes `live_run=(asof, run_warnings)` | the spy recorded `"ABSENT"` for `live_run` |
| `834b2790` | tests only: Reviewer B minors B-1 (asof selected by `run_id`) and B-2 (`run_warnings` passed by identity) | mutations: asof from the first warning (4 tests fail); asof from the latest row (1 fails); a `list()` copy (1 fails) |

- **Premise:** the cell re-derived runs 191 and 194 as 391 and 205 tied skips (`mode=ro`).
- **Suites:**
  - 15379/13/0 before Reviewer A and after it (`1f4614d5`);
  - 15380/13/0 on `834b2790` (`suite-post-B.txt`).

**Cell deviations, accepted by CHARC:**
- the `pipeline_run_asof` helper, with its sibling's degrade contract;
- two docstring sentences replaced in place in `_latest_moved_past_session`;
- brief test 5's fixture corrected. `"20261016"` canonicalizes on Python 3.14; CHARC owns this as a sixth D80 instance.

## Reviews

| reviewer | reviewed head | model / effort | `^ERROR` | verdict (line) | footer | exit | findings |
|---|---|---|---|---|---|---|---|
| A (cell), `r1/` | `1f4614d5` | gpt-5.6-sol / high | 0 | NO_NEW_CRITICAL_MAJOR (:3229) | 49,023 | 0 | none |
| B (orchestrator), `rB/` | `1f4614d5` | gpt-5.6-sol / high | 0 | NO_NEW_CRITICAL_MAJOR (:7994) | 101,118 | 0 | 3 minor: B-1 and B-2 fixed in `834b2790`; B-3 ruled below |

Production code is unchanged after B (`git diff 1f4614d5..834b2790 -- swing/` is empty).

## Gates

**RD gate item: CLEARED** on `834b2790` (`20261019T010008Z`). RD verified by read that the clause-1/2a/2b text and the accepted-historical surfacing are unchanged.

**CHARC merge gate: CLEARED** on `834b2790` (`20261019T010159Z`). The B-3 ruling, block-quoted, with CHARC as author and the orchestrator as courier only:

> B-3 RULING: option (a) -- ACCEPT, by extending the limitation's wording in the merge record. Reason, so it is not re-litigated: a force-clear landing between step_guard entry and the `pipeline_run_asof` read makes a run whose state is already `force_cleared` count its in-memory warnings as live. The cost is the SAME bounded interval the brief section 6 already trades (one artifact, overwritten by the next run; `lease.step("complete")` then raises LeaseRevokedError so the run never completes and its warnings never reach the ledger), and the next nightly's own live skips move the drumbeat past the hole, so it self-heals in one night. Option (b) is REFUSED on the merits, not only on cost: a `state='running'` qualifier on the asof read narrows a TOCTOU window without closing it (the force-clear can land after the read), so it would be a check that cannot fail for the case it names -- the 33/36 class -- bought with a counted round. Record the limitation as: "a run that fails, OR IS FORCE-CLEARED, after the step has read its own warnings yields at most one false-GREEN artifact/night".

**Accepted limitation, as recorded:** a run that fails, OR IS FORCE-CLEARED, after the step has read its own warnings yields at most one false-GREEN artifact/night.
