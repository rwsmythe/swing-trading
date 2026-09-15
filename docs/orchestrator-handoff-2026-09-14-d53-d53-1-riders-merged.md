# Orchestrator handoff — 2026-09-14 (evening HST) — D53, riders, D53.1 merged; D32+D50 is next

**Supersedes** `orchestrator-handoff-2026-09-14-post-22a4-housekeeping.md`.
**From:** the generation launched 2026-09-14 05:56 HST (`orchestrator-20260914-0556`).
**Rolled at:** 405,624 tokens (`cell_depth --sessions --live`), past the 400K trigger, at the clean boundary after
the D53.1 merge. **Precondition met: NO CELL IN FLIGHT** (`cell_depth --live` clean; all three dispatched cells
returned, QA'd, merged, worktrees removed).
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact below was re-derived from disk at write time. Re-derive; do not carry these numbers.**

---

## 1. STATE

- **`main` @ `a355b85a` (plus this handoff commit), ~65 commits AHEAD of origin, UNPUSHED.** Push was never
  authorized this generation — ask the operator. Before any push: trailer audit on the KEY
  (`git log --format='%(trailers:key=Co-Authored-By,valueonly)' origin/main..HEAD` → 0 lines; it was 0 at
  `a355b85a`). The range now carries `swing/` code (D53, D53.1), not just docs.
- Tree clean except `docs/cli-autoupdate-run-poisoning-finding-coa.md` (untracked coa-chess CHARC delivery; not
  ours to commit — it asks for `DISABLE_AUTOUPDATER=1` in our launcher; CHARC/operator's call).
- One worktree (main). No branches but `main`.
- **Live DB:** schema v38, 28 trades, `attempt_id` non-null 0. **Open trades:** 23 CADL (partial_exited), 24 RHI,
  25 OII, 26 NRIX, 28 PBF. Real money.
- **Merged-head suite `a355b85a`: 12,366 passed / 13 skipped / 0 failed** (`-n 4`, this seat's evidence; the
  binding `-n auto` is the operator's).

## 2. WHAT THIS GENERATION DID — all merged, all return reports posted

| Arc | Merge | Cell | Gates | Notes |
|---|---|---|---|---|
| **D53** DBW anchor alignment (`double_bottom_w@v1.1.0`) | `e311be8f` | opus-high | A 1 round clean; **B found a major** → CHARC ruling (c): split to D53.1 | m2/m3 test-only fixes `42595f04`/`5ec6f02b`. **CLOSED by CHARC on run 176** (`71191dd0`). RD QA both halves CLEAR. |
| **Harness riders** (D54 stale-name sweep + probe caps) | `721e1c8a` | sonnet-high | A fast tier converged R3; no B | **D54 CLOSED** (`f18fac23`). Probe now exits 1 on the live repo BY DESIGN (line-3 4,083 > 2,000; 24 gotchas > 700). Record gap: no round had a measured exit code. |
| **D53.1** DBW effective window start | `a355b85a` | opus-high | round-0 + 3 rulings; A converged R2; **B major** → CHARC ruling (i); **operator browser witness PASS, 6 steps** | Guard first; runner carries ONE effective start to slice + persist; anchors JSON frozen (RD 1a). |

**Run 176 (2026-09-14 17:30 HST, main at `e311be8f`+riders):** complete, **export_status=ok** (D42 half (1) CLOSED by
CHARC, `8bc68e7b`), **first non-zero DBW row ever: evaluation 7835 NESR, 0.6667**, persisted start = trough 2 (an
INTERIM row, as derived). Zero new warning classes vs 175.

**Live exemplar written this generation: ONE — id 35, ZETA, double_bottom_w, confirmed, closed_loop_review, start
2026-06-25 OPERATOR-TYPED, end 2026-09-11** (witness step 4; the operator's honest first-low read; RD recorded it as
the first review-route DBW exemplar). Steps 5 and 6 ran on DB COPIES by the operator's choice.

## 3. AUTHORITIES GRANTED BY CELL MESSAGE (state, not history)

All three cells are finished; no grant is open. For the record:
- D53 cell: post-ruling authorization for m2 (helper claim narrowed) + m3 (rename), no Codex round.
- D53.1 cell: (1) RESUME after CHARC's fork ruling with the ruled order (i)-(iv) and B2 scope; (2) one reload-first
  refusal-text commit after the B-gate ruling, no round, B not re-run.
- Riders cell: none beyond the dispatch.

## 4. QUEUE — owners named

1. **D32+D50 (the pre-migration backup gates) — ORCHESTRATOR, NEXT DISPATCH.** CHARC dispatch mail
   `20260914T170751Z`, brief `docs/phase22-arc-d32-d50-backup-gates-dispatch-brief.md` @ `4bb2b049`, **corrected at
   `9e18b642`** (`schema_version` table, not `PRAGMA user_version` — which reads 0 on this project's DBs). Operator
   pre-authorized; cell `implementer-opus-high` (CHARC's minimum); `swing/data` carve-out authorized by CHARC; Reviewer
   A strong; **Reviewer B required**; witness on a COPY per §4 (exclusive-lock proof first), step by step; ledger must
   say the production proof is the first real migration after merge (22-B). I sequenced it after the riders merge
   (same migration test files) and after D53.1's B-gate — both conditions are now met. **Confirm the cell choice with
   the operator before spawning (the handshake).** Round-0 premise census BEFORE the cell, as this generation did for
   D53.1 — it caught two real gaps there.
2. **D56 — ORCHESTRATOR, after D32+D50.** The pattern-review form's 4xx fragment replaces the form itself
   (pre-existing, every 400 on the route); fix = error region beside the form + **C3** (pre-fill the DBW correction
   start with trough 1 for non-zero rows). Tests + template rider, own browser witness. CHARC register row `637d12fc`.
3. **D53.1 forward close check (CHARC closes, RD reads) — the first run executing `a355b85a`, expected run 177
   (2026-09-15 17:30 HST):** its non-zero DBW rows must carry `window_start_date == evidence.trough_1_date`; the DBW
   outcomes-tile denominator moves at that run (RD 2a). The interim span is run 176 .. the run before it.
4. **D55 (CHARC's register):** the false-green DBW clipping test (`tests/patterns/test_double_bottom_w.py`
   `test_dbw_bar_clipping_future_bar_leak_rejected`, since `f3c21073`). Tests-only rider, not commissioned yet.
5. **CHARC's:** the Gotchas compression + line-3 trim (the probe now reads ATTENTION on every CHARC boot until it
   lands); the rmtree-ReadOnly `onexc` rider + its gotcha (D42 half (1) follow-on, "yours" per CHARC — i.e. the
   orchestrator's, riding the next gotcha commit); D42 half (2) (per-step status behind a run-level complete) stands.
6. Then B-2, `ReservedJournalFieldError`'s bare base, D46, D45, D44/D47, D39.

## 5. WHAT WILL BITE YOU

- **Stale sessions on the box (enumerated 2026-09-14 ~17:10 HST, reported to the operator, nothing of theirs killed):**
  predecessor orchestrator pane `orchestrator-20260914-0351` (pid 13776) **still runs an inbox monitor on
  `comms/orchestrator/inbox`** — if anyone drives that pane it can drain your mail; **two CHARC sessions**
  (`charc-20260913-2317` pid 32120 and `director-charc-20260913-2332` pid 13432) both watching `comms/charc/inbox`;
  opsdir's monitor uses the old forking `ls|wc` loop; two `comms_ui` servers (8765, 8770). Check whether the operator
  closed them before assuming.
- **The operator's `swing web` on 8080 (pid 26212, since 09-09) runs PRE-D53 code** — no D53.1 guard. The DBW
  review hold is lifted only for sessions on merged code; recommend a restart. It does not affect the scheduled run.
- **This generation's slips, so you don't repeat them:** (1) removed the riders worktree BEFORE sha256-reconciling two
  ignored files in it — reconcile, THEN remove; (2) posted a sequencing status one minute after an RD ruling landed —
  re-list the inbox immediately before every post; (3) a hand-written verdict-token prompt in the riders cell wrote the
  tokens line-initially and mapped severity ambiguously (2 of 3 rounds defective) — put the prompt-design constraint
  explicitly in every dispatch, as D53.1's did.
- **Two review-label semantics are now RD-ruled** (thread `dbw-detector-silence`): exemplar start provenance is
  derivable from the row (typed / trough-1 derived / generator-era); a W that COMPLETED before an evaluation's window
  is out of scope for that evaluation (reject it; label the W on an overlapping evaluation).
- **Witness mechanics that worked:** worktree code on a side port with `PYTHONPATH=.` (verify the import path
  resolves the worktree); a DB copy via the SQLite online-backup API from a `mode=ro` source + a throwaway
  `--config` whose `db_path` points at the copy; exemplar counts on BOTH DBs after each writing step; the operator
  chooses live-honest vs copy at every step that writes a label.
- **`pattern_evaluations` "1,563" is PER CLASS** (7,815 rows total before run 176). Say which.
- Everything in the prior handoff's §5 still applies (slow bash, cp1252 both sides, `-n auto` memory-killed in this
  seat, dotfile evidence, `role_mail` 80-char subjects / `--body-file` / cd main / verify on disk).

**The admitting gate stays open. Re-derive candidate and A+ counts before quoting them.**
