# Token-efficiency TODO — post-22-A4 (CHARC, 2026-09-07; operator-commissioned)

**Premise, from the project's own history:** the implementer model was never the dominant spend —
**the review loops are.** 22-A ran 26 A-rounds + 2 B passes across planning/exec/fix; Demand C's
plan loop ran 11 rounds; per-round transcripts run 1–4 MB; the 22-A plan reached 3,947 lines and
110 findings before the operator stopped it. The dispatch-table change (`e0541109`: plans Opus/high,
coding Sonnet/high, measured via summed `tokens used`) is item 0. Items 1–7 are sequenced by
leverage. **Nothing here dispatches before 22-A4 merges** (one seam, one arc).

| # | item | mechanism (what lands) | done-criterion | owner |
|---|---|---|---|---|
| 0 | **Measure before tuning** (LANDED `e0541109`) | Return reports + merge requests carry the per-arc SUM of `tokens used` footers; rework (rounds-to-convergence, post-convergence findings) is the cost side | The orchestrator sums the preserved 22-A / 22-A3 transcripts into an **Opus-era baseline** BEFORE the first Sonnet arc returns | orchestrator |
| 1 | **Honor the existing tier rule: plan/doc rounds run at `fast`** | The recipe already says so; 22-A's plan loop ran 9 rounds and Demand C's 11 at `strong`. Add to assertion 1: **on a writing-plans round the banner must show the `fast` profile's model**, else the round is mis-tiered and reported | Every plan round's banner reads the fast model; a `strong` banner on a plan round is a flagged deviation with a stated reason | CHARC (recipe) |
| 2 | **Stop planning earlier — plan length is spend** | Two mechanical triggers in the round-5 ledger check-in: (a) a round whose findings are **majority INSTRUMENT** (ordering, anchors, prose precision) → stop reading, execute — tests find that class in seconds; (b) plan length **> ~1,500 lines** → stop and split. Review history lives in the LEDGER, never inline in the plan (the full diff hit the 1 MB transport cap) | The check-in template carries both triggers; a plan crossing either is reported with the trigger named | CHARC (recipe) + orchestrator (gate ruling) |
| 3 | **Drop per-leg Codex loops for locked-scope executing** | Binding convergence is the FULL diff (orchestrator-ruled). Per-leg rounds on a growing subset are early warning at `strong` prices. Replace with: full suite per leg (free) + ONE full-diff A round at the end + B at the gate. Keep per-leg loops only when the brief names the leg as design-bearing | The executing brief template says so; a per-leg loop carries a stated reason | CHARC (recipe) |
| 4 | **Apply the cascade remedy at the FIRST residual round** | The self-sweep + one-confirming-round rule exists; 22-A ran R7–R11 each finding residuals of the previous fix. Trigger: **the first round in which ≥ half the findings are residuals of the immediately preceding fix** → self-sweep, then one round | The ledger's per-round "residual-of-prior-fix" count is a column, and the rule fires on it | CHARC (recipe) + orchestrator |
| 5 | **Mail-body norm** | Subjects are capped in code; bodies are not. CHARC's average ~700 words, orchestrator's often more, each read by 2–3 roles at director context prices. Norm: **evidence + disposition, not narrative** — the finding, its method, the ruling, the file:line. Consider a soft cap (warn > N words) in `role_mail post` | Measured average body length halves over the next arc; the warn line exists | CHARC (comms) — CHARC is the worst offender |
| 6 | **Context discipline — keep what makes handoffs cheap** | The state-pointer overwrite + resume-record discipline made two orchestrator generational handoffs inside one arc cheap. The context sinks are re-reading multi-MB transcripts and multi-thousand-line plans (item 2 fixes most). Add: a director/orchestrator **re-derives from disk, never re-reads a transcript** unless a specific claim needs it | Pointer stays under ~16 K chars (probe check owed); handoffs cite the pointer, not the transcript | CHARC (probe) |
| 7 | **DO NOT CUT** | Reviewer B (3 of 3 passes found what A structurally could not, or confirmed a claim A couldn't) · premise re-derivation before authoring (caught 2 brief errors in Demand C, 3 in 22-A, before any code) · the five mechanical assertions · QA-on-disk | These stay; a proposal to cut any of them carries the evidence against the record above | both directors |

**The Sonnet-coding risk, and its measure.** The recipe's standing caution: this codebase's gotcha
density makes a too-weak implementer net-negative. The mitigation is that the gates are unchanged, so
weakness shows up as REWORK, not as shipped defects. Baselines on record: 22-A3 executing converged at
5 rounds; the 22-A fix leg took 11. If Sonnet arcs converge in a similar count, the trade held; a
Sonnet dispatch that stalls or oscillates is re-dispatched at Opus, never pushed.

**Cross-project:** the same findings are filed for coa-chess at
`coa-chess/docs/token-efficiency-findings-swing.md` so its CHARC can run the same comparison.
