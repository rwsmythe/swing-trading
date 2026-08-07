# 3b resume state — paused pre-Codex, 2026-08-07

**Why this file exists:** the operator shut the laptop down mid-arc, which ends the orchestrator session and the implementer agent with it. The WORK is safe (all committed); the agent's CONTEXT is not. This is what a successor needs to resume without re-deriving it.

**Delete this file when 3b merges.** It is a resume aid, not a durable record.

---

## State at pause

| | |
|---|---|
| Branch | `criteria-lapsed-report-only` |
| Worktree | `.worktrees/criteria-lapsed-report-only` |
| Head | `5f0bbcae` |
| Commits ahead of main | **10** |
| Working tree | **CLEAN — nothing uncommitted** |
| Base | `main` @ `63a330b8` |
| Codex | **NOT STARTED** — no `.copowers-findings.md` exists |

**Where it stopped:** the recipe §2 pre-review full-suite gate is **PASSED** — the implementer reported **10445 passed / 7 skipped / 0 failed** on this head (baseline 10322/7/0, so **+123 tests**), `ruff check swing/` clean. All task commits are in. **The entire remaining gate is the §3 Codex loop + codex-auto-review, then the post-convergence suite re-run and the trailer audit.**

> That suite number is the IMPLEMENTER's, reported at pause. It has not been re-run by the orchestrator. Treat it as a strong checkpoint, not as a QA'd result — re-run before relying on it.

```
5f0bbcae feat(web): Task 7 -- the off-screen UNVERIFIABLE render and the calibration read
c7a027bb feat(latches): Task 5c -- the report-only arm flag, gating the terminal and nothing else
cb8c3b3a feat(latches): Task 6 -- framework_withdrawn, excluded from the discipline signal and the away rate
0c1c0c4d feat(latches): Task 5b -- the lapse hypothetical and its diagnostics (no terminal yet)
0d3ce06d feat(latches): Task 4 -- per-session structural verdicts, roster-validated
085b0c34 feat(config): Task 3 -- the four latch calibrations, arm flag included, bound not literal
78680ed3 refactor(evaluation): Task 2 -- extract the A+ structural gate as the ONE authority
73b1df10 test(evaluation): Task 2 -- the bucket_for characterization table, before the refactor
d88435b9 feat(latches): Task 1 -- criteria_lapsed joins the clear-reason vocabulary with every Python mirror
7e615f04 fix(latches): Task R6 -- a different-pivot re-fire ON the expiry session supersedes, not horizon
```

## To resume

1. **Run the pre-review full suite** from inside the worktree (`python -m pytest -m "not slow" -q`). Baseline on main at dispatch was **10322 passed / 7 skipped / 0 failed**. Fix to green *before* Codex — that gate exists because cross-cutting invariant tests aren't exercised per-task.
2. **Then run the §3 Codex loop** to `NO_NEW_CRITICAL_MAJOR`, plus codex-auto-review (production code).
3. **Re-read `docs/implementer-dispatch-recipe.md` §3 first** — it changed on 2026-08-06 and is stricter than the last arc: anchored `grep -c '^ERROR'`, the `tokens used` footer as a fourth numbered assertion, and verify the redirect target is non-empty. `bash -lc` was the working cold-audit form; explicit `encoding="utf-8"` on prompt read/write; no `pgrep -f` polls.

## Two things the implementer flagged at the pause — carry them to QA

1. **A commit-message blemish in `085b0c34` (Task 3).** A backtick pair in its heredoc caused bash to swallow the word `token`, so a line reads *"...and was handed to LatchesConfig."* Cosmetic, the paragraph still parses, and the no-amend rule forbids the implementer fixing it. **The ORCHESTRATOR may amend at merge** (same authority used for the 21-B trailer) — but this is a missing word, not a trailer-audit pollution, so amending is optional and probably not worth the history churn. Flagged, not hidden.

2. **A scope call worth confirming rather than reversing.** Plan test **T7.8** asked that the DECLINE control survive a withheld prepared-order form. The shipped template puts that button inside `{% if po.offered %}`, so today it does not. **3a built exactly that affordance, reverted it, and RD signed off routing the render/route half to wave item 4.** The implementer therefore declined to fix it here — judging that doing so would re-open a scope a director had closed — and instead **pinned the current shape with a test naming what flips when item 4 ships.** That reasoning looks right: item 4 owns the declined surface, and flag B's write half is already assigned there. Confirm at QA rather than re-open.

## Rulings this arc is built against (do not re-litigate)

- **The plan, on main:** `docs/superpowers/plans/2026-08-06-phase21-item3-criteria-lapsed.md`. 3b is the `criteria_lapsed` half.
- **RD's thirteen rulings:** `comms/orchestrator/read/20260806T114306Z-rd-item-3-all-thirteen-ruled-framing-first.md`
- **RD banked the R6 tie fix here** (shipped as `7e615f04`): `comms/orchestrator/read/20260807T030757Z-rd-3a-gate-pass-cleared-flag-c-confirmed-pr.md`
- **CHARC's split ruling:** `comms/orchestrator/read/20260806T222427Z-charc-split-ruled-3a-declined-armed-first-then.md`

**Binding constraints:**
- **Report-only** — the countdown, streak, UNVERIFIABLE render, disposition machinery and alarm all ship; only the automatic **clear** is behind a config arm flag, default OFF.
- **Both-modes testing (RD, binding):** every negative test asserts the **counterfactual fields**, and the FTRE founding case runs **armed AND unarmed** — a test asserting only "it did not clear" passes under default-OFF regardless of the conjuncts.
- **Tripwire CLOSED.** Option B: no new `LATCH_STATES` member (it has four SQL CHECK mirrors — touching them is a **condition-4 STOP**). `criteria_lapsed` is the REASON, reusing `horizon_expired`, with a dedicated label branch.
- **R4:** derived fields suffice. A **durable would-clear series is a new table and a condition-4 STOP**.
- **Gotcha #11:** `LATCH_CLEAR_REASONS` 5 → 6 with every Python mirror in ONE commit (landed in `d88435b9` — verify it held).
- The **projection pin** (`set(_CLEAR_REASON_RANK) == set(LATCH_CLEAR_REASONS)`, `tests/latches/test_declined_terminal.py`) must re-assert over **six** members.
- **Artifact-scale watch (CHARC):** if findings cluster as INTERACTIONS between pieces rather than defects within them, propose the split — an available outcome, not a failure.

## Gates after convergence

Orchestrator QA on disk → **RD merge-blocking** (measurement) → **operator witness** on the latch surface. **VSTS is the worked example and it demonstrates the UNVERIFIABLE state, not a clear** — its newest `candidates` row is 2026-07-30 against a newest evaluation run of 2026-08-07, so it has been off-screen eight days.

## Wave state

Items 1 (D29), 2 (sizing-basis), `coverage_gaps`, and 3a (`declined`) are **merged**. The recipe window is taken and closed. **Remaining after 3b:** item 4 — cancel decoupling · the declined surface (render/route **+ flag B's server-computed session**, its write half) · `_PRICE_DP` ×4 · the below-pivot refusal with the **equality-preservation** refinement.
