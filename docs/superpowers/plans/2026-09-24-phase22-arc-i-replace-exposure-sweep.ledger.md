# Phase 22 arc 22-I plan — review ledger (committed per round; recipe §3 plan-stage rule 2)

**Plan (not yet written):** `docs/superpowers/plans/2026-09-24-phase22-arc-i-replace-exposure-sweep.md`. **Round-0 census:** `docs/superpowers/plans/2026-09-24-phase22-arc-i-replace-exposure-sweep.census.md`. **Brief:** `docs/phase22-arc-i-f-sweeps-commissioning-brief.md` @ `d4f2cbed`. **Base:** `b09bbc02`. **Rules read from main @ `b09bbc02`.** **Durable evidence dir:** `~/swing-data/review-transcripts/22-i-plan/`.

## Round table

| Round | Kind | Tier / model / effort (asserted) | Footer `tokens used` | Verdict token | Findings (crit/major/minor) | Task-bearing | NEW / REOPENED | Reverts | Context depth (ORCHESTRATOR fills from `cell_depth.py --agent <id>`) |
|---|---|---|---|---|---|---|---|---|---|
| 0 | premise + fork census, NO Codex | — | — (0 Codex tokens) | — | — | — | — | — | **407,892 at return — OVER the 400K cap** (build 2.1.280, `claude-opus-5-5`; orchestrator-read `cell_depth.py --agent`; Agent usage 410,246). The plan stage RE-DISPATCHES to a FRESH cell off this census + ledger (recipe §3: a normal outcome). |

## Round 0 — evidence

- Probe script: `scripts/probe_22i_guard_census.py` (committed with this ledger).
- Probe output (copy, all sections): `~/swing-data/review-transcripts/22-i-plan/probe-output-r0.tsv` — 194,252 bytes, sha256 `f09871e5543f9f9d6417fb4ed523bb61909eb4e6eaa1003ea98e09e5180dbdce`; 941 probes: PASS 713 / FAIL 101 / INFO 129.
- Probe output (live `mode=ro`, catalogue only): `~/swing-data/review-transcripts/22-i-plan/probe-output-r0-live-ro.tsv` — 4,055 bytes, sha256 `996ad20bb8910ad909cec429494c5d23a1a2f480e4dd2ec41ae981e2801738a3`.
- Live trigger dump: `~/swing-data/review-transcripts/22-i-plan/live_v40_triggers.sql`; table facts: `.../table_facts.txt`.
- Live-DB copy the write probes ran on: `C:\Users\rwsmy\swing-data\scratch\22-i-probe\swing-v40-copy-20260924T173854Z.db` (backup API from `mode=ro`; 1,673,084,928 bytes).

## Round 0 — outcome (routed as ONE packet; no round opens until rulings land)

- **Findings for `0041`:** `trg_provenance_corrections_append_only_update` fails the NULL-`WHEN` per-input probe on 30 `=`-compared columns × 2 live rows (F-I2 applies). All other existing guards CONFIRMED (census §2).
- **Needs a ruling:** F-I1 (RD, 21 rows, census §3) · F-I5 NEW (RD + CHARC: `latch_view_events` twin narrower than its contract) · F-I6 NEW (CHARC: open-but-backstopped validation triggers).
- **Ruling-packet intake correction:** F-I2's discriminator "trade-23 blob replays ADMIT" is false under v40 (the stored row predates the R14-02 operand freeze and is REFUSED); proposed encoding in census §4.
- **Brief §1 deltas:** a2, a7, a9, a13, a17 (census §1).

## Rulings received

(none yet)
