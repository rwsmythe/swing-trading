# Maintenance rider (D82 + D83 + shadow 900 s): WRITING-PLANS continuation brief, cell 2

**Audience:** a fresh implementer cell with no prior conversation context.

Cell 1 ran Round 0, a premise and fork census with no Codex, and then went past the context cap. Both directors have ruled on that census. You write the plan from those rulings.

**Cell:** `implementer-opus-xhigh`.

**Read first, in full:**
1. `docs/maintenance-rider-d82-d83-plan-dispatch-brief.md` (main `4d6cea42`). It still binds: the envelope, the live-data rules, the plan form and the return format. This brief SUPERSEDES it where the two differ, as set out below.
2. **RD's Round-0 ruling:** `comms/orchestrator/read/20261020T004935Z-rd-maint-rider-r0-rd-rules-coverage-deferre.md` (main repo).
3. **CHARC's Round-0 ruling:** `comms/orchestrator/read/20261020T005222Z-charc-maint-rider-r0-ruled-f6-f12-my-d83-premi.md` (main repo).
4. **The orchestrator's census to both directors**, which carries cell 1's measurements and forks: `comms/charc/read/20261020T004708Z-orchestrator-maint-rider-round-0-d83-ruling-premises.md`. If that path has not moved to `read/` yet, look under `comms/charc/inbox/`.
5. **Cell 1's Round-0 evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\plan\round0\` (m01-m12 plus `plug\`). Reuse it, and re-measure anything the plan relies on that may have moved since.
6. **The register rows**, both amended by CHARC: D83 and the new D89, in `docs/tool-director-context.md` on main.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\maint-rider`, branch `maint-rider`. It has no commits yet and sits at base `4d6cea42`.
- Before you write, fast-forward the branch to main at the commit that carries this brief: `git merge --ff-only main` inside the worktree. Main moved only in docs.
- Run every probe from the worktree with `PYTHONPATH=.`.

## 1. Scope as ruled

The plan carries BOTH rulings block-quoted in a plan ledger beside the plan, with RD and CHARC named as authors.

**D82, invalid_ohlc: becomes a RATE (RD F5; CHARC F6).**
- **Bands, by integer cross-multiplication:**
  - green iff `count*20 <= unique_signals`;
  - red iff `count*10 > unique_signals`;
  - yellow otherwise.
- **Display:** 2 dp plus the band word, in RD's form.
- **Removed, with no count belt:**
  - `_INVALID_OHLC_BASELINE_COUNT`;
  - the CALIBRATION B block;
  - the over/excess_pct path;
  - the "baseline 23" text.
- **Kept:** `_is_nonneg_count`.
- **Unchanged:** the zero-signals branch and the corrupt-manifest branches.
- **Out of scope:** the 10/25 rules for the other excluded reasons.
- **Tests:**
  - The baseline-semantics tests are each classified SUPERSEDED BY NAME. They are replaced, not edited to pass.
  - RD's required discriminator: 77/1535 reads YELLOW.
  - Boundary pins on the same denominator: 76 green, 153 yellow, 154 red.
  - A display pin for the 2-dp text.
  - Today's 71/1535 reads GREEN.

**D82, coverage: DEFERRED (RD).**
- The count rule stands UNCHANGED, along with its tests.
- Coverage is now OUT of this rider's envelope.
- The plan records RD's pre-ruling and the condition that re-opens it, as text in the ledger only.

**Shadow timeout:** `SHADOW_EXPECTANCY_TIMEOUT_S` 300 -> 900. The pin at `tests/pipeline/test_step_shadow_expectancy.py:136` moves with it.

**D83, the warm cohort (CHARC F7-F12; the six conditions of the original brief bind as CHARC amended them).**
- **F9, the cohort selector.** The cohort list comes from observe's own selector:
  `list_observable_detections(conn, source="pipeline", observation_date=lease_data_asof(cfg, lease))`,
  then distinct uppercased tickers.
  - Never hand-written SQL; never `run_now`.
  - The discriminating test, RED first: the lease is dated 06-10, run_now's session is 06-12, and a detection is at 06-11.
- **F10, the helper.** It is built on four conditions:
  1. `_prewarm_evaluate_archives(..., lease)` takes `lease` as a required keyword. `_open_detection_warm_tickers(cfg, lease)` opens its own connection through `swing.data.db.connect`, calls the F9 selector, returns sorted distinct tickers, and closes in `finally`.
  2. Any reader exception produces a `log.warning`, a #27 run-warning (`step: evaluate_warm`, with the reason naming the read), and `open_det=n/a`. The warm then proceeds with the base set.
  3. The cohort is `[benchmark, *candidates, *universe, *open_det_added]`, with the base order preserved and the open-detection tickers appended after dedup. A test asserts the union, the order and the absence of duplicates.
  4. The seven warm unit tests take a lease stub.

  The caller edit at `runner.py:1596-1600` is inside the envelope.
- **F11, telemetry.** `open_det=` and `open_det_added=` are APPENDED to the existing cohort log line (`runner.py:1492-1498`), with `n/a` when the read fails, and are paired with the F10(2) warning.
- **F12, the window constant.**
  - ONE module constant replaces `window_days=400` at all THREE sites: `runner.py:2136`, `:2398` and `:3054`.
  - Closure check: `grep -rn "window_days=400" swing/` returns ZERO afterwards.
  - The depth test imports the constant and asserts condition (ii) against the LIVE config value of `archive_history_days`.
  - Source-text parsing is rejected.
- **F8, the witness.** The merge-report checklist carries it, defined exactly as CHARC wrote it, as items (a)-(d). The last pre-merge night and the first post-merge night are quoted side by side.
  - The run-194 baseline: 229 singles for the run, 216 inside observe, and a wall of 1,300,128 ms.
  - `observe_load` is written up as EXPECTED unchanged.
- **F7.** The merge report states, in these words: "the warm alone does not bring a run-194-sized night under 900 s; the per-detection term is D89." D89 is NOT this rider's work.
- **Condition (v), neutrality.** The merge report quotes the observation rows written for one fixture, with and without the warm, equal in count and values.
- **Condition (vi).** The single-ticker path stays `threads=False`.

**F14.** `swing/latches/service.py:393-394`: replace the "baselines invalid_ohlc at 23 of 77" sentence so it describes the rate rule. Change that docstring only.

**Envelope, final.** The original IN list, plus:
- the caller line;
- the three `window_days=400` sites;
- the `latches/service.py` docstring lines.

It no longer includes the coverage thresholds.

**Owner docs.** Listed in the plan for their owners, never edited:
- RD: watch-standard `:168-169`, which RD edits at merge;
- CHARC: already amended;
- orchestrator: `docs/orchestrator-context.md:94` and `CLAUDE.md:67`, which I edit after the merge.

## 2. Review protocol: SUPERSEDES the original brief's section 4 (the orchestrator's error, F13)

Follow `docs/implementer-dispatch-recipe.md` section 3, the PLAN-STAGE PROTOCOL, exactly:
- Round 0 is done. Cell 1's census is it.
- The plan is a task ladder and a test roster, capped at about 1,000 lines. The argument and the rulings live in the plan LEDGER.
- A blocking finding is TASK-BEARING only.
- Plan rounds run at the **`fast`** tier. The banner must show the fast profile's model; a `strong` banner is a mis-tiered round.
- At most THREE counted rounds. Stop at the first round with zero task-bearing findings. In any case, stop after round 3 and run the uncounted self-sweep.

Every other per-round assertion in recipe section 3 still applies:
- describe the verdict tokens; never write one line-initially;
- `^ERROR` 0;
- the footer;
- exactly one distinct anchored token, read from the model's region;
- the exit file written after codex returns;
- no prior-round reads;
- report any content-filter event.

Save each round to `C:\Users\rwsmy\swing-data\review-transcripts\maint-rider\plan\`.

**STOP AND RETURN at EVERY counted round gate with its ledger row.** Leave the depth column empty.

After the plan converges, it goes to CHARC for the plan-stage read and to RD for the F5 bands as planned. That routing is mine, not yours.

## 3. Gates and return

- Conventional, pathspec-only commits on the branch.
- `%(trailers)` empty after each commit.
- No final `-m` paragraph begins with `Word:`.
- No Co-Authored-By, no `--no-verify`, no amend.
- No `swing/` change: this is planning.

**Return in chat only.** You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return in the original brief's section 6 form.

**If anything does not fit, STOP and return.** Do not choose for yourself.
