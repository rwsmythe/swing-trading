**Last overwritten:** 2026-10-20 (~05:40 UTC) by the 2026-10-20 successor generation (session `1c07b715`, build 2.1.300, Fable 5.1 at medium) — NOT a rollover; a mid-generation refresh after the D89 round-0 ruling and the charter's second compaction, so a successor bootstrapping off this file is current. Facts RE-VERIFIED at write time by method: main @ `6dc96420` (`git log -1`), ahead of origin by 10 doc commits (`git status -sb`; the operator pushes); `git worktree list` = main + `.worktrees/d89-memo` @ `31a293b4` (the orchestrator's D89 writing-plans worktree, no commits); live DB **v41**, last pipeline run **195** complete (2026-10-19 17:44 HST); `comms/.sessions.json` names `swing-orchestrator-20261018-1515`, `swing-rd-20261018-1519` and this seat; `cell_depth --sessions` shows the 10-18 orchestrator OVER the 400K cap (its rollover, not mine). Charter **108,085 chars** after this generation's compaction (`6dc96420`; was 136,706 after the D89/D90/D91 rows); the under-100K target lands when the D89/D90 rulings are block-quoted into the plan ledger and those rows compress (~5K).

---

## #1 — WHERE THINGS STAND

**PHASE 22 ACTIVE; the book is FLAT** (0 open trades). The operator's attention eases over the coming weeks (his statement 2026-10-19).

**D89 (observe's per-detection read cost) — round 0 RULED at this seat 2026-10-20** (`4c6664e4`; mail `20261020T052004Z-charc-d89-r0-*` to orchestrator,rd, both pinged). CHARC: D1 · B1 (memoize the `(df, provenance)` pair after a non-raising populate) · key `(ticker, observation_date)` · H (ii) no production knob · W5 (iii) `resolve_reads` on `observe_load` beside the replay · G declined and not registered · envelope `runner.py` only · the `_bar_for_date` docstring (`:3077-3079`, "zero Schwab") is FALSE and D89 rewrites it to what the code does. RD (`20261020T041614Z`): C3 with the memo condition as a literal; P12 yes on the N-V set; H3 accepted (re-open at observe wall > 1,800 s); H4 at its per-ticker-per-step width. Premise corrections applied to the row. **NEXT at this seat: the D89 plan-stage read (the plan is written by a FRESH cell on the rulings; no review round while a ruling is outstanding — none is), then the merge gate (W1–W7 in F8's form; T-H1/T-H2/T-C3; one mutation quoted; B transcript on the tree being merged).**

**D90 OPENED on the operator's word 2026-10-20** ("Yes, I want the O1 ladder-detach registered now"): observe's Schwab leg never carries the observation-date bar (RD's mechanism `20261020T041759Z`, verified at `runner.py:481-495`, `marketdata.py:402`, the spec `:350`, `marketdata_ladder.py:505-530`). RD's call binds: detach the ladder from observe's populate, NO explicit `endDate`. CHARC FORM ruled in the row: `use_ladder: bool = True` keyword on `OhlcvCache.get_or_fetch`, threaded to `_fetch_bars_window`; observe passes False; the bundle worker untouched; the store shared safely (both branches store the same archive read). Admissibility (2) is OWED from RD before the D90 plan: name any reader of PRIOR-date rows for observe-only tickers (their `schwab_api` parquet stops advancing). Sequence: after D89, before D84. **D91 OPENED** (never-expiring no-bar detections; RD semantics, CHARC form; a terminal transition without an OHLC row is a schema tripwire when scoped).

**After D89/D90 (operator-sequenced): the SOFT-STOP ARC + Finviz widening rider (D84)** — approved 2026-10-19, not planned; plan-stage director review BINDS (RD: population + H1/H4 cohort amendment; CHARC: the 21-B zero-share composition, bucket enum mirrors, `watchlist/service.py:28`'s criteria roster, `capital.py` semantics).

## #2 — WRITTEN THIS GENERATION (`git log -- docs/tool-director-context.md`)

`4c6664e4` D89 ruled + D90/D91 opened · `6dc96420` the second compaction (D79/D82/D83/D87 merged rows, D73/D86/D85/D88, D59/D81 stubs, D1/D15/D16, §2.11, §4.3 bullets, the 10-18..10-20 §6 entries and the pre-06-18 §6 block → the archive §"Archived 2026-10-20 (compaction)", compressed forms with pointers remain). No code, no dispatch, no cell.

## #3 — OPEN ITEMS, OWNER NAMED

| item | owner | state |
|---|---|---|
| D89 plan-stage read, then merge gate | CHARC | awaits the orchestrator's plan (fresh cell) |
| D90 admissibility (2): readers of prior-date rows for observe-only tickers | RD | owed before the D90 plan |
| D90 plan-stage read + merge gate; D91 form when scoped | CHARC | after D89 |
| Soft-stop arc + widening rider (D84) plan-stage review | CHARC · RD | after D89/D90 |
| Charter under 100K | CHARC | at the D89/D90 ledger landing |
| D85, D86, D88 (banked; triggers in the rows) | CHARC | banked |
| First live exit = the D79 witness (RD reads the fill row first) | RD | awaits a live exit |
| CLAUDE.md line-3 4,083 chars (cap 2,000) + 22 gotcha bullets over 700 chars (probe ATTENTION); the "2m20s" stale by 10× | orchestrator (CONTENT) | flagged |
| The operator pushes main (ahead 10 at this write) | operator | housekeeping |

## #4 — BEHAVIORAL (charter §5 has the full text)

- **Count the subject in the guarded command** (`[ ${#s} -le 80 ] && post`): refused at 88 on my first post this generation. 80 is shorter than it looks.
- **The Bash tool's heredoc strips one backslash level:** `"\\|"` in a Python source heredoc arrived as `"\|"` and a lookbehind regex died at position 0. Write bodies and scripts with the Write tool, or avoid backslashes in heredoc text.
- **A ruling that prescribes a mechanism states its admissibility preconditions and names which exist today** (D90's three, stated in the row). **A register row needs an observable signal** — G was declined and NOT registered on that rule.
- `--type decision_request` is operator-only; role-to-role is `fyi|status|query|return_report`. A gate is run against DISK, not the report. Read the LINE you cite. Pathspec commits, `-m` before `--`; `%(trailers)` prints empty; post from the MAIN repo dir; LF files; ZERO `Co-Authored-By` EVER; read `cell_depth --sessions --live 1` before every ruling packet; roll at a clean boundary, never mid-ruling.
