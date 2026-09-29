**Last overwritten:** 2026-09-28 (HST evening; 2026-09-29 UTC) by the 2026-09-25 17:26 generation (`swing-charc-20260925-1726`, session `0a221641`, build 2.1.280, Fable 5.1 medium) at **302,811** self-read (`cell_depth.py --sessions --live 1`), UNDER the 400K trigger — a normal session overwrite, NOT a rollover. Facts RE-VERIFIED at write time by method: main @ `48e008bb` before this generation's commit (`git log -1 main`); `## main...origin/main [ahead 330]` before the push (`git status -sb`) — **the operator directed the push on 2026-09-28 ("complete the remaining items on your list, then push"); this commit is followed by `git push origin main`**; `git worktree list` = main ONLY (both 22-F worktrees and the exit re-render worktree REMOVED; branches `22-f-exec`, `22-f-plan`, `exit-rerender-anchor` KEPT because the ledgers cite their SHAs); live DB **v41** (`SELECT version FROM schema_version`, `mode=ro`), last pipeline run **186** complete (`pipeline_runs` by `id`); `comms/.sessions.json` names `swing-orchestrator-20260928-0758`, `swing-rd-20260928-1659`, and this seat; no cell of mine (I dispatch none); no Monitor (ping convention). Charter **111,040** of 120,000 after the 09-28 compaction.

---

## #1 — WHERE THINGS STAND

**PHASE 22 ACTIVE; the book is FLAT.** Declared trading pause ~10-03..10-20; no witness rung inside it. Order of record: **the post-pause exit arc (commissioned) → 22-H after RD's October read**; 22-C/22-D on the live-case gate; 22-G banked with three items (register D78).

**22-F — CLOSED through merge.** Reviewer B pass 2 valid (one major B2-01 at the `schwab_reconciliation.py` preserve handler, DECLINED by my ruling as pre-arc behaviour unreachable in the envelope; a D39 facet banked; the false pre-arc comment replaced at `ccddb374`, no round). My code-only merge gate CLEARED at `ccddb374` (every item re-run at this seat: no added `swing/` files, no migration/dependency diff, trailers empty, 34 files inside F-F6 + A-1..A-4, bounds held by diff, merge-tree conflict-free, merged `cli.py` blob = branch's, census pin 2 passed). **Merged `58368c86` `--no-ff`; merged-head 15328/13/0.** The operator grant `d4f2cbed` is spent. Rulings block-quoted in the exec ledger (§"Reviewer B pass 2 gate -- CHARC's RULING", `33eaf31d`).

**Follow-ups (operator grant 2026-09-28, spent):** riders R-1..R-4 merged `4e412db9` (15347/13/0; tests/scripts only): R-1 census test keyed on call TEXT (the line-pin rot is closed), R-2 the D67 L1 follow-on, **R-3 `cell_depth --live` lists PARKED cells (my instrument)**, R-4 the 22-I probe INFO undercount. The exit re-render anchor fix (RD 1(iii) / 22-F AL-6, d2-strict) WITNESSED by the operator on both branches after re-auth and merged `c6640faf` (15360/13/0).

**Commissioned, operator-timed: THE POST-PAUSE EXIT ARC** (after ~10-20, before the first live exit) = the double-record guard (F2) + F1 (a non-default candidate pick keeps the default's date/price). Register **D79** carries the evidence (zero live instances of either), RD's identity semantics (a/b/c) that bind the brief, and the tripwires: it crosses the `swing/trades/exit.py` carve-out, and any backstop index is new schema keyed on (order id, signature) unless RD's case (b) is proven unreachable. **It routes through me at commissioning; verify that the brief tests case (b)'s reachability BEFORE either guard or index is specified.**

## #2 — WRITTEN THIS GENERATION (commit of this file)

- **Charter compaction:** D32, D51, D56, D57, D67, D69 archived verbatim with pointer rows (closure SHAs checked by `git log`); the §6 07-29→09-09 entry archived with a one-line pointer. Archive §"Archived 2026-09-28 (compaction)".
- **Register:** D36 (+22-I's three REPLACE/rowid facets), D39 (+B2-01 facet), and new **D72** FND-1..4 (home: the 22-F exec ledger's findings section) · **D73** interrupt-at-cleanup class + the OPEN S-D39 template question · **D74** order-dependent tests · **D75** `tos_import` binds `connect` at import · **D76** `seed_initial_policy` zero callers (RD's lane) · **D77** `force_clear` ignores rowcount · **D78** 22-G's three items · **D79** the exit arc · **D80** my own method row (a ruled text names only states the code measures). The three code claims (D75/D76/D77) were re-read against the code on 09-28.
- **Harness-architecture:** the round-gate depth paragraph and the rollover PRECONDITION replaced for R-3 — a `parked` cell is resumable work that dies with its session, so HOLD for it too; `parked` infers a live parent from transcript recency and can OVER-report a just-ended session's cells, never under-report. The same line replaced in all three bootstraps (charc, rd, orchestrator). `tests/scripts` 447 passed after the edits.

## #3 — OPEN ITEMS, OWNER NAMED

| item | owner | state |
|---|---|---|
| Post-pause exit arc (D79): brief → my carve-out/schema pass → execution → witness | operator (timing) · orchestrator · CHARC gate · RD semantics | commissioned for after ~10-20 |
| October read (before the 10-03 pause); the 10-02 Schwab setup reminder | RD | standing |
| 22-H after RD's October read; 22-C/22-D live-case gate; 22-G (D78) | RD · CHARC | standing |
| Gotchas compression (probe ATTENTION ×2: CLAUDE.md line-3 4,083 > 2,000; 23 bullets > 700) | orchestrator (CONTENT) | owed |
| D74 order-dependent tests; D77 `force_clear` rider; FND-1/FND-2 riders | orchestrator queue | banked |
| S-D39 template question (D73): interrupt vs cleanup failure on a double failure | CHARC to rule, before the D73 sweep | open |
| D33 (equity ≥ $7,500); schwabdev 4.0.0 DECLINED | banked | banked |

## #4 — BEHAVIORAL (charter §5 has the full text)

- **Read your own depth before every ruling packet** (`cell_depth.py --sessions --live 1`). This generation bootstrapped at 160K — the three role docs are ~330K chars; budget for it.
- **Verify a peer's closure claim against the census, not its word:** the orchestrator's "no cell in flight" at its rollover coincided with a cell written 0.0h ago; the transcript's last record (`end_turn`) settled it. Same for R-3's `parked`: a just-ended session's cells read `parked` — check before treating one as live.
- **A real-money flag gets a live-DB read before it gets an opinion:** both exit findings (F1, F2) were measured at zero live instances in minutes, which set the commissioning timing.
- **A witness in a degraded environment witnesses the degraded branch only** (the expired Schwab token would have left the d2-strict restore path unwitnessed while the witness read as passed; flagged, the operator re-authed, both branches driven).
- Pathspec commits with `-m` BEFORE `--`; `%(trailers)` prints `[]`; the role_mail subject cap is 80 (tripped TWICE this generation — count `${#s}` first); post from the MAIN repo dir with `--body-file`; the cwd silently moves after any `git -C` into a worktree — absolute paths; ping the names `role_mail` prints (the orchestrator's AND RD's names both changed this generation). A shell heredoc carrying a long script failed to parse — write scripts with the file tool; files here are CRLF, so an inserted break is `\r\n`. ZERO `Co-Authored-By` EVER.
