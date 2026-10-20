**Last overwritten:** 2026-10-20 (~07:20 UTC) by the 2026-10-20 successor generation (session `1c07b715`, build 2.1.300, Fable 5.1 at medium) at **~368K** self-read (`cell_depth.py --sessions --live 1`) — a **ROLLOVER** at a clean boundary: D89 is MERGED and its row closed, no ruling of mine is owed, no cell of mine is in flight (`cell_depth.py --live 2`: the only live cell is the orchestrator's D90 writing-plans cell, `agent-a762a2aae…`, 126K; four `parked` cells are the orchestrator's finished ones), and the next packet (the D90 plan-stage read, ~30-40K) would carry this seat past the 400K trigger mid-ruling. Facts RE-VERIFIED at write time by method: main @ `ce802670` (`git log -1`; the D89 row-close commit atop the orchestrator's D90 brief `e7f91d80`); `## main...origin/main [ahead 30+]` — the operator pushes (`git status -sb`); `git worktree list` = main + `.worktrees/d90-detach` @ `e7f91d80` (the orchestrator's D90 writing-plans worktree, no commits); live DB **v41**, last pipeline run **195** (the first post-D89 nightly has NOT run); `comms/.sessions.json` names `swing-orchestrator-20261018-1515`, `swing-rd-20261018-1519` and this seat (the launcher overwrites it at act 4); no Monitor (ping convention). Charter **~108K** after this generation's second compaction (`6dc96420`; target under 100K lands when the D89/D90 rows compress at their ledger landings — D89's can compress NOW that the plan ledger holds the rulings; D90's after its plan).

---

## #1 — WHERE THINGS STAND

**PHASE 22 ACTIVE; the book is FLAT** (0 open trades). The operator's attention eases over the coming weeks (his statement 2026-10-19).

**D89 (observe's per-step read memo) — MERGED 2026-10-20 at `717e4ebe`** (parents `a938f416` + `9258b295`; CONVERGED at A round 1 strong 0/0/2 both minors ruled; B on the tree being merged 0/0/0; merged-head suite 15518/0 exit 0; replay on copies 7,139 → 248 reads, rows byte-equal to round 0; M1 red 3/5). Gated at this seat with every item re-run on disk (`a938f416`); plan-stage cleared on form at `e1e1b442` (`1ffd5b95`; one roster correction: NINE test files patch the resolver, six exercise observe). **OWED at the first post-merge nightly (RD reads first, CHARC re-reads `mode=ro` + `pipeline.log`): W1–W7 against run 195** (wall 541,691 ms; audited fetch term 97,350 ms; 7,139 iterations; 62.24 ms/iteration upper bound, ~6-7 projected); **W5 (iii) the live `resolve_reads`** (~248) beside the replay; the ladder state as the `schwab_api_calls` count; H3's re-open trigger (observe wall > 1,800 s) and H4's width (per ticker per step) in the ruled words. The orchestrator posts the addendum after the operator's nightly.

**D90 (detach the ladder from observe's populate) — APPROVED by name, DISPATCHED to writing-plans by the orchestrator (brief `e7f91d80`; worktree `d90-detach`).** Its premise check first: CHARC's `use_ladder` form; the warm writes the ARCHIVE not the `_bars_store`; **the shared `_bars_store` ordering hazard** (a detect-time ladder store makes observe's `use_ladder=False` call an in-memory hit — the populate under the flag is only reached on a store MISS, so the flag's effect depends on what ran earlier in the run; the plan must state whether the Schwab leg's cost actually leaves on a night where detect/charts already stored the ticker, and the W witness is the `schwab_api_calls` count INSIDE observe's window). It stops on any fork. **THE SUCCESSOR'S FIRST JOB: the D90 plan-stage read on form** — the D90 row (form ruled, admissibility (1)-(3) stated, RD's answer to (2) recorded, the operator's approval quoted) is the authority; read the plan against `ohlcv_cache.py:175-245, 270-310` and `runner.py:3110` (the populate call, now `:3129` after D89 — re-grep), never against the census. RD rules neutrality.

**After D90: the SOFT-STOP ARC + Finviz widening rider (D84)** — approved 2026-10-19, not planned; plan-stage director review BINDS (RD: population + H1/H4 cohort amendment; CHARC: the 21-B zero-share composition, bucket enum mirrors, `watchlist/service.py:28`'s criteria roster, `capital.py` semantics). D91 after D84 unless the widening multiplies the stuck set.

## #2 — WRITTEN THIS GENERATION (`git log -- docs/tool-director-context.md docs/charc-state.md`)

D89 round 0 ruled + D90/D91 opened (`4c6664e4`) · the second compaction (`6dc96420`) · D90 approved by name (`28b55219`) · D90 admissibility (2) answered (`e0d1c595`) · D89 plan-stage cleared (`1ffd5b95`) · D89 merge gate cleared (`a938f416`) · D89 merged, row closed (`ce802670`). No code, no dispatch, no cell of mine.

## #3 — OPEN ITEMS, OWNER NAMED

| item | owner | state |
|---|---|---|
| **D90 plan-stage read (form)** | **CHARC (successor)** | the plan arrives by mail from the orchestrator's live cell |
| D89 first-nightly witness W1–W7 + live `resolve_reads` | RD first, CHARC re-read | after the operator's next nightly |
| D90 merge gate; D91 form when scoped | CHARC | after the D90 plan |
| Soft-stop arc + widening rider (D84) plan-stage review | CHARC · RD | after D90 |
| Charter under 100K: compress the D89 row now (its rulings are in the plan ledger on main), D90's after its plan | CHARC | at the next charter touch |
| D85, D86, D88 (banked; triggers in the rows) | CHARC | banked |
| First live exit = the D79 witness (RD reads the fill row first) | RD | awaits a live exit |
| CLAUDE.md line-3 4,083 chars (cap 2,000) + 22 gotcha bullets over 700 chars (probe ATTENTION); the "2m20s" stale by 10× | orchestrator (CONTENT) | flagged |
| The operator pushes main (ahead 30+ at this write) | operator | housekeeping |

## #4 — BEHAVIORAL (charter §5 has the full text)

- **Count the subject in the guarded command** (`[ ${#s} -le 80 ] && post`): refused twice this generation (88, 83). 80 is shorter than it looks.
- **The Bash tool's heredoc strips one backslash level:** `"\\|"` in a Python heredoc arrived as `"\|"`; a lookbehind regex died at position 0 before any write. Write bodies and scripts with the Write tool; keep heredoc text backslash-free.
- **A gate is run against DISK, not the report:** this generation re-ran every item on two D89 gates (name-status, four-dir stat, `%(trailers)` per commit, the diff read in full, both transcripts' `^ERROR`/verdict/footer/exit, the suite file's first-line sha + tail, the tests by name, the mutation output file, the replay compare file, `merge-tree --write-tree`, quote fidelity by script). The reports were right every time; that is the finding, not the premise. Reviewer A's transcript lives in `exec/round1/review.txt`, not the exec root.
- **A ruling that prescribes a mechanism states its admissibility preconditions and names which exist today** (D90's three). **A register row needs an observable signal** (G declined, not registered). **Existence ≠ completeness:** "six files patch the resolver" was nine — grep the claim, not the name.
- `--type decision_request` is operator-only. Read the LINE you cite. Pathspec commits, `-m` before `--`; `%(trailers)` prints empty; post from the MAIN repo dir; LF files; ZERO `Co-Authored-By` EVER; read `cell_depth --sessions --live 1` before every ruling packet; roll at a clean boundary, never mid-ruling.
