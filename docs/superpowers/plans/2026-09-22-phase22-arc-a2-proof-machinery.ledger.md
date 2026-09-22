# Phase 22 arc 22-A2 (PROOF MACHINERY) -- plan ledger

- **Base SHA:** `78a395ed` (the commissioning brief's commit; worktree `.worktrees/22-a2-plan`, branch `22-a2-plan`).
- **Rules SHA:** read from MAIN by absolute path at `78a395ed` -- `docs/implementer-dispatch-recipe.md` (whole), `docs/harness-architecture.md` section 5.1 (whole), `CLAUDE.md`.
- **Brief:** `docs/phase22-arc-a2-commissioning-brief.md` @ `78a395ed` (CHARC-authored, operator-commissioned 2026-09-22).
- **Protocol:** recipe PLAN-STAGE PROTOCOL / harness 5.1 "DESIGN IS SETTLED BEFORE THE PLAN LOOP OPENS". This file is the committed ledger; the plan does not exist yet.

## Round table (cumulative)

| round | kind | Codex tier | findings | task-bearing | verdict token | tokens used | ctx depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|
| 0 | premise + fork census | none (no Codex, by protocol) | n/a | n/a | n/a | 0 | |

**STATUS: ROUND 0 CLOSED ON ROUTING. NO review round runs until every item in section R0.4 is LANDED below as a block quote.**

---

## ROUND 0 -- PREMISE + FORK CENSUS (2026-09-22)

### R0.0 Method, and what was NOT run

- Every live-DB read below used plain `sqlite3` on `file:%USERPROFILE%/swing-data/swing.db?mode=ro` (URI mode). Never `swing`'s `connect` / `ensure_schema`. Query scripts live in the session scratchpad (not committed).
- **The Demand-C `--dry-run` was NOT run against the live DB, because it is not provably read-only.** Its own docstring says so: `swing/trades/cohort_provenance_correction.py:2183-2201` -- *"NET-ZERO, and that is a weaker claim than write-free ... for the duration of the call the connection takes a WRITE LOCK"*; the shared `_authorize` WRITES a `fill_envelope_identity` reading via `record_identity` (`:1847-1862`) and unwinds it through a SAVEPOINT (`:2251-2468`); and the CLI opens the DB read-write through `swing.data.db.connect` (`swing/cli.py:2741`).
- **Instead it was run on a byte-consistent COPY:** `sqlite3.backup()` from a `mode=ro` source connection into the scratchpad (copy: v38, 28 trades, 1 provenance row, `integrity_check` = ok), with a scratch `swing.config.toml` whose every `[paths]` entry points into the scratchpad, invoked from the worktree as `PYTHONPATH=. python -m swing.cli --config <scratch> journal correct-cohort-provenance ...` (the worktree's `swing` resolved, `EXPECTED_SCHEMA_VERSION` 38). Live `swing.db` size/mtime identical before and after (`1635282944` / `1790105707`).
- **One SIMULATION was run, on a second disposable copy, to measure a premise no shipped path has ever computed (P26):** rung 9 forced to pass (the copy's link 1 `freeze_tier` edited after dropping the copy's `trg_loml_no_update`; `epoch_boundary` monkeypatched in-process to 12283), then `resolve_latched_provenance` over fill 48 with `prices_cache_dir` = the REAL archive. The archive read is `migrate=False` (`swing/latches/reader.py:676-698`, the A4 no-write property); OII's three archive files had identical mtime/size before and after.
- Counts are reported with the method that produced them. A token grep is reported as a LOWER BOUND, never a manifest.

### R0.1 Premise table (brief section 1 live state + section 0 pointers)

| # | fact (as the brief states it) | command / method | result | status |
|---|---|---|---|---|
| P1 | live schema v38 | `SELECT version FROM schema_version` (ro) | 38 | CONFIRMED |
| P2 | trade 19 FTRE 07-31 standard, Broad-watch / 11852 / `pipeline_watch_manual` | `SELECT ... FROM trades WHERE id IN (19,20,23,24,25,28)` (ro) | `2026-07-31`, `standard`, `'Broad-watch baseline (watch); failed: tightness'`, 11852, `pipeline_watch_manual`; state `reviewed`, size 0 | CONFIRMED (and CLOSED) |
| P3 | trade 24 RHI 08-14 standard, Broad-watch / 12518 / `pipeline_watch_manual` | same | `2026-08-14`, `standard`, `'Broad-watch baseline (watch); failed: proximity_20ma, tightness'`, 12518, `pipeline_watch_manual`; `reviewed` | CONFIRMED (CLOSED) |
| P4 | trade 25 OII 08-17 standard, NULL / NULL / `manual_off_pipeline` | same | exactly so; `reviewed` | CONFIRMED (CLOSED 09-17 -- rd-state header A; the horizon marker FIRED) |
| P5 | trade 28 PBF 09-01 `hypothesis_test_by_design`, NULL/NULL/`manual_off_pipeline` | same | exactly so; `reviewed` | CONFIRMED |
| P6 | trade 20 AMN 08-07, intent NULL, keys NULL | same | exactly so | CONFIRMED (OUT of scope) |
| P7 | RHI place intent 4 pre-dates the fill by two days | `SELECT * FROM latch_order_intents` (ro) | intent 4: `place`, candidate 12442, run 139, action 2026-08-13, `recorded_ts 2026-08-12T21:14:00`; fill 47 `2026-08-14T16:00:00` | CONFIRMED -- **and NO validity row exists for RHI (intents 1-13 read in full), so there is NO link** (see F1) |
| P8 | link 1 exists: intent 2, candidate 12284, run 136, order 1007523377009, `pre_barrier_reconstructed` | `SELECT * FROM latch_order_mandate_links` (ro) | exactly so; `frozen_pivot 53.97999954223633`, `frozen_invalidation 41.41999816894531`, qty 2 | CONFIRMED |
| P9 | pre-barrier admission REFUSES trade 25 today | Demand-C `--dry-run` on the COPY: `journal correct-cohort-provenance 25 --cited-candidate 12284 --cited-recommendation 169 --reason "census probe on a copy" --dry-run` | exit 1: *"Error: trade 25's entry fill names broker order 1007523377009, whose accepted latch mandate the 22-A ladder REFUSED (pre_barrier_unproven). A refused mandate does not fall back to the last-word ladder: correcting through the other authority would be citation shopping, which is what this surface exists to prevent. Nothing was written."* | CONFIRMED (on the copy) |
| P10 | `provenance_corrections` holds ONE row: id 1, trade 23 CADL, `last_word`, candidate 12341 | `SELECT ... FROM provenance_corrections` (ro) | exactly so; `applied_at 2026-08-13T16:02:16.022`, run 137 | CONFIRMED -- **so trades 19 and 24 have NO correction row** (F1 premise) |
| P11 | epoch row `(1, 13591, 2026-09-02T10:03:33Z)` | `SELECT * FROM candidates_immutability_epoch` (ro) | exactly so | CONFIRMED |
| P12 | four link rows, ALL `pre_barrier_reconstructed` (OII 12284, DFTX 12997, IMNM 13578 x2); no `live_at_acceptance` link | P8 query | exactly so | CONFIRMED. Also: `SELECT COUNT(*) FROM candidates WHERE bucket='aplus' AND id > 13591` = **0**; `MAX(id)` = 14456 |
| P13 | `fill_envelope_identity` has 6 rows | `SELECT COUNT(*)` (ro) | 6 (fills 54-59) | CONFIRMED. **NEW: none is for fill 48 (trade 25's entry)** -- the correction service writes it on demand inside its own transaction (`cohort_provenance_correction.py:1847-1862`) |
| P14 | the barrier has NEVER been retired | `barrier_installed(conn)` on a ro connection; `grep -n 'DROP TRIGGER' 0038` | `True` (six bodies byte-equal to the pinned 0037 copies after whitespace normalization); 0038 drops only its own `trg_trades_attempt_id_immutable` (header text) | CONFIRMED **as far as current state + migration files can show.** A hand-run DROP followed by a byte-identical CREATE is undetectable by construction (that is R6-02) -- "never" is bounded, not proven |
| P15 | "19 correctable NOW via the Demand-C surface" (rd-state line 59) | `--dry-run` on the COPY: `journal correct-cohort-provenance 19 --cited-candidate 11261 --cited-recommendation 142 --dry-run` | exit 1: *"Error: trade 19 already carries cohort provenance (hypothesis_label='Broad-watch baseline (watch); failed: tightness'; candidate_id=11852; trade_origin='pipeline_watch_manual'). This surface FILLS empty provenance; it does not re-decide provenance the framework already recorded. Nothing was written."* | **FALSIFIED** -- and on two further grounds the surface never reaches (F1 premises iii, iv) |
| P16 | "24 needs 22-A2 tier-2/attestation" | same dry-run for 24 (`--cited-candidate 12442 --cited-recommendation 183`) + P7 + P8 | refusal verbatim as P15 with RHI's values (*"trade 24 already carries cohort provenance (hypothesis_label='Broad-watch baseline (watch); failed: proximity_20ma, tightness'; candidate_id=12518; trade_origin='pipeline_watch_manual')..."*); no link for fill 47's order 1007574345138 | **FALSIFIED as a claim about tier-2 AS RULED** (tier-2 is a rung-9 escape on a matched LINK -- F1 premise iii) |
| P17 | F3: "a hyp-rec entry has a `watch` row and no recommendation row" | last-word query for PBF (`action_session_date <= '2026-09-01'`, ordered as `_assert_last_word_before_the_fill` ranks); `SELECT recommendation, COUNT(*) FROM daily_recommendations GROUP BY 1`; `SELECT * FROM latch_order_intents WHERE ticker='PBF'` | last word = **13477, bucket `skip`**, run 152, action 09-01; the most recent `watch` row is 13408 (08-31); D41's matching row 12836 (watch, 08-20) is quoted from the register, NOT re-measured (the H2 matcher was not run); `daily_recommendations` = 248 `near_trigger` + 16 `today_decision`, **0 name PBF**; 0 PBF intents; fill 53 `operator_typed`, envelope NULL | **PARTLY FALSIFIED** -- the framework's last pre-fill word on PBF is `skip`, not `watch` |
| P18 | section 0 pointer: `latched_origin.py` holds "the ONE epoch reader `freeze_tier_for_candidate` and its barrier-integrity check" | `grep -rn freeze_tier_for_candidate swing/` | the reader is **`swing/data/repos/candidates_immutability_epoch.py:237`** (`barrier_installed` `:181`, `epoch_boundary` `:215`); `latched_origin.py` CONSUMES it at `:1261`, `:1487`, `:1826`. SQL twins (declared): minting CASE 0037 `:727-730`, backfill CASE `:761-764`, citation-trigger rung-9 EXISTS `:2037-2039` | **CORRECTED (location)** -- the grep proves the three import sites; it does not prove there is no fourth SQL-side reader (read of 0037 found the three twins above) |
| P19 | the other section 0 pointers | read at each site | S12 at plan `:4057-4160`; struck seventh-column block `:2388-2401`; S4.3a `:2602`; `models.py:3021-3023` (`LATCH_FREEZE_TIERS`), `:3025-3031` (`PROVENANCE_ADMISSION_TIERS` + the comment naming `latch_ladder_tier2`); `correct_cohort_provenance` `cohort_provenance_correction.py:2625`; CLI `cli.py:2658`; tier DETECTED `cohort_provenance_correction.py:1963-1967`; `--cited-candidate` must be aplus (help `cli.py:2663-2668`, enforced at trigger 0037 `:900-903`, CHECK 0036 `:494-503`, model `models.py:3557-3562`); "ONCE ... no re-correction" `cli.py:2729-2730` + service `:2035-2037`; five-option pin `tests/cli/test_correct_cohort_provenance_command.py:71` | CONFIRMED. Wording note: 0037 adds SIX columns = ONE tier + FIVE citation columns (`0037:787-796`; `models.py:3350-3359`), not "six citation columns" |
| P20 | 0037 epoch: single state, `CHECK (epoch_id = 1)`, THREE triggers created after the seed | read `0037:121-161` | exactly so | CONFIRMED |
| P21 | `latch_order_mandate_links` append-only triple; `fill_envelope_identity` | read `0037:355-379`, `:518`, `:651-679` | exactly so | CONFIRMED |
| P22 | 0038 `trades.attempt_id` | read `0038` | exactly so | CONFIRMED |
| P23 | executing waits for D51; 22-A2's migration regenerates the D51 fixture | `git log --all --grep=D51`; `ls scripts/schema_manifest.py` on main | D51 commits live on branch `d51-schema-manifest` @ `05f9cc2c`; `scripts/schema_manifest.py` ABSENT on main | CONFIRMED (not merged) |
| P24 | trade 25 tier-2 evidence (S12.1 #10) | `git show -s --format=%aI%n%cI 9f315cc6`; `git show 9f315cc6:docs/rd-state.md` line 57; `git merge-base --is-ancestor 9f315cc6 origin/main` / `main`; `git rev-list --count`; candidate/run query | author = committer = `2026-08-10T02:41:33-10:00`; line 57 contains *"Frozen at fire: pivot 53.98 / `initial_stop` 41.42"* (and "OII A+ (pivot 53.98)", "the 08-10 fire row"); ancestor of the LOCAL `origin/main` ref (`348f126b`) AND of `main`; candidate 12284 `pivot 53.97999954223633`, `initial_stop 41.41999816894531` -> Python `round(.,2)` 53.98 / 41.42 (neither on the `.125/.625` divergent family); run 136 `run_ts 2026-08-07T17:30:02` (naive local), action session 2026-08-10; descendants 175 (at 08-24) -> **684 to `origin/main`, 688 to `main`** today | CONFIRMED. The uncovered window is a BRACKET (R8-01): 2.3830 d from run START, 2.3767 d from pipeline 150's `finished_ts 17:39:07` -- both 2.38 |
| P25 | the 0036 citation graph is satisfiable for trade 25 | rec / pipeline / status-history queries (ro) | `daily_recommendations` 169 = `today_decision`, run 136, OII, action 08-10; pipeline 150 `complete`, finished `2026-08-07T17:39:07`; H1 status-history row 1 `active` from 2026-04-25, `effective_to` NULL, `recorded_at` 2026-05-12 | CONFIRMED |
| P26 | "Trade 25 ADMITS on tier-2" (brief section 4.1) presupposes the envelope guards AND the aliveness probe admit on OII's real bars | read `latched_origin.py:1819-1863`; read `tests/trades/test_22a_task9_entry_wiring.py:168-226`; SIMULATION per R0.0 | shipped rung 9 returns `pre_barrier_unproven` at `:1845-1848`, BEFORE the guards (`:1853`) and the probe (`:1859`), so **no shipped path has ever computed the probe on trade 25**; 22-A's case-1 tests use a synthetic FTRE-shaped probe world (*"THE VALUES ARE THE PROBE WORLD'S, not OII's"*, `:181`). **Simulated: `admitted=True`, `admission_basis='armed'`, no terminal, horizon 2026-08-17, `bars_through` 2026-08-14, coverage 5/5 sessions (08-10..08-14), `archive_status='ok'`, raw frozen == live for pivot and invalidation, both `*_equal_at_dp = 1`** | **NEW PREMISE, MEASURED (simulation on a copy)** -- the acceptance case is reachable; it rests on rung 9's escape + the conjunction alone |
| P27 | witness step: "the H1 count re-read by RD (2/20 -> 3/20 by his count)" (brief section 5) | read `docs/rd-state.md` header (A) | rd-state's 09-22 header already reads *"23 CADL +0.43 ... H1 -> 3/20 by my count, reader to confirm"* BEFORE any trade-25 correction; section 1 of the same file still says 2/20 (carried forward from 09-07) | **INCONSISTENT between two docs; NOT MEASURED** (the H1 reader was not run). The witness must quote the reader's number, never a pinned expectation |
| P28 | the migration backup at the witness is "ONE backup, path echoed" (brief section 5) | read `swing/cli.py:263-360` | D32/D50 made it ONE backup per migration: a covering `db.py` gate writes the image and the CLI echoes it (`:356-359`); no gate -> the CLI's own snapshot | CONFIRMED against code. **Side-flag (not this arc's fix):** CLAUDE.md's gotcha *"`swing db-migrate` writes TWO backups, not one"* is now STALE against `cli.py:284-289`; and 0039 needs its own row in the gate table (`backup_gate_for_pre_version`) or the no-gate snapshot applies |

**Enum-member lower bound (NOT a manifest -- the plan's #11 task does the closure-checked READ, each member separately):** grepping each member separately across `swing/` (`*.py`, `*.sql`): `'last_word'` 6 lines/2 files, `"last_word"` 3/2, `'latch_ladder'` 4/1, `"latch_ladder"` 2/2, `PROVENANCE_ADMISSION_TIER` 21/4, `latch_ladder_tier2` 2/2 (comments only), `'pre_barrier_reconstructed'` 3/1, `"pre_barrier_reconstructed"` 1/1, `'live_at_acceptance'` 5/1, `"live_at_acceptance"` 1/1, `LATCH_FREEZE_TIERS` 6/3, `FREEZE_TIER_` 18/3. These bound the mirror family from BELOW; a paraphrase or a hard-coded single member elsewhere is invisible to them (the 22-A twelfth-site lesson).

### R0.2 The premise corrections that change the packet (read these before the forks)

1. **Tier-2 AS RULED reaches exactly ONE live trade: 25.** The carved design (22-A plan round-8 text, S2.7, preserved only in the transcript `~/swing-data/review-transcripts/22-a-plan/.codex-review-r8.txt`, 1,009,990 bytes, lines 1814-2010 and 2543-2610) makes tier-2 the escape AT RUNG 9 on a fill whose broker order resolves to exactly one accepted LINK; a tier-2 row carries all five latch citation columns PLUS the seventh (*"`latch_ladder_tier2` -> all six NON-NULL"*). Measured: of all entry fills with a valid envelope, exactly one names a linked order -- fill 48 / trade 25 (method: `json_extract(schwab_source_value_json, '$.schwab_order_id')` over `action = 'entry'` fills passing `json_valid`, intersected with `latch_order_mandate_links.broker_order_id`; a raw-envelope read, which approximates the authority's stored reading -- only 6 fills have one). FTRE has zero intent rows; RHI has a place intent but no validity row and so no link.
2. **Trades 19 and 24 have no `provenance_corrections` row.** Their keys were written by the ENTRY path. The brief's F1 branch (a) -- a supersession chain on "the row it supersedes" -- has no row to supersede.
3. **Writing a correction over NON-EMPTY keys is refused at three layers, the last structural:** service `_gate_on_unset_state` (P15's quoted refusal); model `_require_value_envelope("pre_value_json", ..., unset=True)` (`models.py:3518-3519`); and a TABLE-LEVEL CHECK pinning the pre-envelope to `manual_off_pipeline` / null / null (`0036:485-492`). **SQLite 3.50.4 cannot drop a table CHECK or a NOT NULL by ALTER** -- verified by execution: `ALTER TABLE t DROP CONSTRAINT` and `ALTER TABLE t ALTER COLUMN ... DROP NOT NULL` are syntax errors; `DROP COLUMN` of a CHECK-referenced column fails. So any branch that writes such rows INTO `provenance_corrections` is a **REBUILD of the audit table of record** (D30 class), not an additive `0039`.
4. **The same structural wall stands in front of F3(a):** `cited_daily_recommendation_id INTEGER NOT NULL` (`0036:68`), the candidate-snapshot CHECK `$.bucket = 'aplus'` (`0036:494-503`) and the applied-origin CHECK `= 'pipeline_aplus'` (`0036:479-480`) are all table-level.
5. **Trade 19 also fails the last-word guard, which the surface never reaches.** FTRE's last word before the 07-31 fill is 11852 (`watch`, run 130, action 07-31); the aplus fire 11261 (run 121, action 07-20, rec 142) is seven runs older. `cohort_provenance_correction.py:955-965`: *"... in which case the trade is UNCORRECTABLE through this surface and the case belongs to RD."* Trade 24 likewise: its last word is 12518 (`watch`, run 140, action 08-14), later than the fire 12442.
6. **The acceptance case is reachable** (P26): with rung 9 escaped, the shipped ladder admits trade 25 `armed` on real bars. Nothing but rung 9 and the conjunction stands between trade 25 and a `latch_ladder_tier2` row.

### R0.3 Kept claims -- the mechanic and the surface each was measured on

| kept claim | mechanic that makes it true | surface it was measured on |
|---|---|---|
| The tier is DETECTED, never chosen | `_Authorized.admission_tier` (`cohort_provenance_correction.py:1963-1967`) + the trigger's per-tier branches (`0037:1226-1333`) | code read |
| Under a latch the citation is FORCED to the link's fire | `:2069-2080` refuses any other `--cited-candidate` | code read |
| Pre-barrier refuses by default (S12.1 #1) | rung 9, `latched_origin.py:1845-1848` | P9 dry-run on the copy |
| Drift is not death for OII (the acceptance premise) | `mandate_alive_at` -> `derive_latches` over the Shape-A archive | P26 simulation on a copy (real archive, read-only) |
| The time anchor is practical, not cryptographic (S12.1 #7) | `git merge-base --is-ancestor <sha> origin/main` | P24: ancestor of the LOCAL `origin/main` ref `348f126b`, which is 4 commits BEHIND local `main` (`78a395ed`) at census time -- the ref's age is routinely non-zero |
| The uncovered window is 2.38 days | run 136 `run_ts` (naive local, run START per `runner.py:608`; candidates persist at `:1600-1603`) to the author instant | P24: a bracket 2.3767-2.3830 d |
| Descendants grow; growth is not divergence (S12.1 #6) | `git rev-list --count` | P24: 175 -> 684 in four weeks |
| No network inside `BEGIN IMMEDIATE` (S12.1 #9) | F5 as ruled makes the preflight network-free altogether | F5 landed text |
| The 0036 citation graph holds for trade 25 | the eight 0036 relations, re-created verbatim in 0037 | P25 |
| The 22-A six-case gate stays green byte-unchanged | the suite | NOT measured at census -- execution's first full run |

### R0.4 THE FORK CENSUS -- one PRIMARY ruler per item; no round runs while any is open

> Each item gives both branches concretely enough to rule on. The census does not decide. Where the census has a reading it says so and labels it a reading.

---

#### F1.1 -- TRADES 19 AND 24: DOES 22-A2 CARRY ANY ADMISSION PATH FOR THEM? PRIMARY RULER: **RD** (evidence semantics). Serialized ahead of F1.2.

Premises: R0.2 items 1, 2, 3, 5. The brief framed F1 as re-correction of a non-empty row with RD deciding whether 24's misfile is a tier-2 question. **Measured answer available to RD: under tier-2 as ruled, it structurally is not** -- tier-2 proves FROZEN VALUES of a LINKED mandate; 24's gap is ORDER IDENTITY (there is no link), and 19 has no latch record at all.

- **(a) YES -- 22-A2 carries a path, and RD names its evidence class, which is NEW (not an encoding of S12).**
  - For **24**: an ORDER-IDENTITY attestation binding broker order `1007574345138` (fill 47's envelope) to place intent 4 (the framework's prepared order: STOP_LIMIT 44.18 / 45.50 x 3, recorded 2026-08-12T21:14:00, append-only). The only pre-fill records are that place row and the fill's own 44.20 x 3 -- a VALUE-TUPLE match, which RD's standing rule refuses as identity (*"IDENTITY IS NEVER ASSERTED FROM A DATE ALONE ... anonymous value-tuple matches FLAG at either grain"*, rd-state 4-bis). No contemporaneous broker-order record is in the DB (`schwab_api_calls` has no payload column -- PRAGMA read). A retroactive validity row would be recorded after the outcome, failing the admissibility test's clause (a).
  - For **19**: a PRE-INSTRUMENT-LATCH class (an order placed against an A+ fire before the latch instrument existed; FTRE fire 11261, action 07-20; fill envelope order `1007308870656`). What contemporaneous record would carry it is NOT measured here.
  - Either class also needs the last-word guard SUPERSEDED for that authority (R0.2 item 5), exactly as the latch ladder supersedes it.
- **(b) NO -- 19 and 24 stay NAMED-PENDING.** The October read carries them exactly as rd-state designed ("Every read carries them NAMED, never silently uncounted"); 22-A2 ships tier-2 for the one row it reaches (25). If RD wants a new evidence class for 19/24 it is its own arc, commissioned with its evidence named.

#### F1.2 -- THE WRITE SHAPE FOR RELABELLING NON-EMPTY, ENTRY-DERIVED KEYS. PRIMARY RULER: **CHARC**. Live only if F1.1 = (a).

- **(a1) REBUILD `provenance_corrections`** relaxing the pre-envelope CHECK (and the applied-origin CHECK if the new class can land a non-`pipeline_aplus` origin), carrying row 1 and re-creating all four triggers (citation graph, append-only update, append-only delete, `trg_pc_no_replace`). D30 class on the audit table of record; a section-3 tripwire the brief's "migration 0039" did not anticipate.
- **(a2) A SIBLING append-only table** for relabels of entry-derived keys: its schema is the new evidence rule, pre-values recorded non-empty, one-head-per-trade defined there; 0036/0037 untouched. Additive.
- **Not a branch for 19/24, recorded so it is not re-proposed:** the brief's chain shape (`superseded_by_provenance_correction_id` on a prior row) answers a DIFFERENT question -- re-correcting a trade that already HAS a row (today only 23) -- and collides with `ux_provenance_corrections_trade` UNIQUE(`trade_id`) (`0036:526`; the 0036 header `:520-525` records *"a chain and this index are mutually exclusive"*) and with the append-only UPDATE trigger that permits only FK-driven nulling (`0037:2193-2290`). A backward pointer on the NEW row (`supersedes_provenance_correction_id`, UNIQUE; head = no successor) would avoid the UPDATE. **Census reading:** no live re-correction case exists, so it stays out of 22-A2 unless RD names one.

---

#### F2 -- THE ERA MODEL: BUILD NOW, OR DEFER TO `22-A2i`. PRIMARY RULER: **RD** (doctrine #8), CHARC's shape.

- **(a) BUILD NOW, as ruled:** a separate append-only `candidates_immutability_epoch_events` table (the seeded epoch row stays under its triple; the ONE reader consults both); three-valued `LATCH_FREEZE_TIERS` with `gap_era_reconstructed` at every mirror (the minting CASE becomes three-way); transitions ordered by a strictly-increasing integer enforced by a trigger, **never by `applied_at`** (R7-02, R8-02: `applied_at` is not monotone, unique, server-stamped or non-future); R6-03 and R7-03's three-valued halves land. Every era case is SYNTHETIC -- the barrier has never been retired (P14).
- **(b) DEFER (CHARC recommends):** the interval is still computed and recorded (F2.I); a pre-barrier gap fails closed to tier-2 as ruled; `LATCH_FREEZE_TIERS` stays two-valued; only `PROVENANCE_ADMISSION_TIERS` widens. **The cost, stated exactly from the code:** the single-state reader has NO time component -- `epoch_boundary` reads only `max_candidate_id_at_barrier` (`candidates_immutability_epoch.py:215-234`), and `grep -rn candidates_immutability_epoch swing/ --include=*.py` finds exactly ONE `SELECT` against the table (`:231`, that column); no Python reader reads `applied_at`. So under (b) the ONLY gap the interval can see is the PRE-barrier span. A post-barrier retire -> re-arm (R6-02: DROP in migration N, byte-identical CREATE in N+k) restores a barrier that passes the body check and is **invisible** to both the reader and the interval; it is covered only by the procedural half of 0037's reversibility header. RD says whether "any gap demotes" (S12.1 #8) is satisfied as ruled by that, or re-opened.

#### F2.T -- IF F2 = (b): MAKE THE PROCEDURAL HALF MECHANICAL? PRIMARY RULER: **CHARC**.

- **(t1)** A suite test that fails if any migration numbered above 0037 contains `DROP TRIGGER` naming one of the six `BARRIER_TRIGGER_NAMES` (`candidates_immutability_epoch.py:167`) without a same-migration era record -- converting R6-02's retire/re-arm from "remembered" to "fails CI". Cheap; catches only file-borne drops, never a hand-run one.
- **(t2)** No test; the reversibility header's procedural rule stands alone, and the residual is declared in the plan's accepted limitations.

#### F2.I -- THE CONTINUITY INTERVAL `[fire_session, read]`: ITS DEFINITION. PRIMARY RULER: **RD** (doctrine #8 is his), CHARC's shape. "Defining it is the plan's first design task" (brief section 2).

Constraints any definition must meet, from the inherited findings: the fire is a BRACKET, not a point (R8-01: `run_ts` is the run START, `runner.py:608`; candidates are inserted in `_persist`, `:1600-1603`, before `pipeline_runs.finished_ts`); four clock representations meet here -- `evaluation_runs.run_ts` naive LOCAL, the epoch `applied_at` UTC with `Z`, the correction `applied_at` naive UTC with ms (`_applied_at_now`, `cohort_provenance_correction.py:130-134`), a git author-date with an offset (R8-03 clock-domain half); and **a trigger cannot observe a Python return value** (R8-03), so SQL may bind ENDPOINTS to their source columns and nothing else.

- **(I-1) Single-state, id-classified (pairs with F2(b)).** Endpoints: `fire_lo` = the cited run's `run_ts`, `fire_hi` = its pipeline row's `finished_ts` (both local -> UTC); `barrier_armed_at` = epoch `applied_at`; `read_at` = the correction row's own `applied_at`. Segments: `[fire_lo, barrier_armed_at)` UNCOVERED iff `candidate_id <= boundary`; `[max(fire_lo, barrier_armed_at), read_at]` COVERED iff `barrier_installed()` at read. Recorded as one JSON object: every endpoint with its clock domain and source, the segment list. SQL binds `fire_lo`/`fire_hi` to `evaluation_runs` / `pipeline_runs`, `barrier_armed_at` to the epoch row, `read_at` to `NEW.applied_at`, and recomputes no duration. Residual: R6-02 (F2(b)'s cost). **Trade 25 under I-1:** fire 2026-08-08T03:30:02Z..03:39:07Z; uncovered to 2026-09-02T10:03:33Z = 25.27 d; covered thereafter.
- **(I-2) Era-event interval (pairs with F2(a)).** Same endpoints; covered segments = the union of ARMED eras from the events table (ordered by its integer sequence) intersected with `[fire_lo, read_at]`; any uncovered sub-span demotes; a link minted inside a retired era carries `gap_era_reconstructed`.
- **(I-3) Evidence-window only.** Record only criterion 4's window `[fire, evidence record)` (S12.1 #10's 2.38 d) and no `[fire_session, read]` object. **Listed for completeness: it contradicts the brief's section 2 IN bullet 3** ("the continuity interval ... as a computed, recorded fact on the correction row"); choosing it amends the brief.
- **SUB-QUESTION for RD under I-1 or I-2 (it changes what the row RECORDS, not trade 25's verdict):** the span `[evidence record, barrier_armed_at)` -- for trade 25, 2026-08-10T12:41:33Z to 2026-09-02T10:03:33Z, 22.89 d -- is protected by criterion 3's current-row match (NET-change evidence; a change-and-restore passes) and by nothing continuous. Is it (s1) a GAP recorded as such, or (s2) COVERED-BY-MATCH, recorded as a distinct coverage kind? The criterion-4 window `[fire, record)` = 2.38 d is `writer_absence_only` under both.

---

#### F3.1 -- PBF (28) / D41: HYP-REC CITATION. PRIMARY RULER: **RD**.

Premises: P17; R0.2 item 4. PBF's last pre-fill word is `skip` (13477); D41's H2-matching row is 12836 (`watch`, 08-20 -- register, not re-measured), six runs older; zero `daily_recommendations` rows and zero latch intents name PBF; fill 53 is `operator_typed` with no envelope. So branch (a) needs a NEW AUTHORITY as well as a widened citation: neither last-word (12836 is not the last word) nor latch (no intent row).

- **(a) WIDEN in 22-A2:** admission from a `watch` row whose criteria profile matches the registered H2 statement, recommendation citation optional-WITH-REASON (D41's stated generalization), origin `pipeline_watch_hyp_recs` (the value hyp-rec trades 21/22/26 carry today). Structurally this crosses the REBUILD wall (R0.2 item 4) or needs a sibling table -- see F3.2.
- **(b) DEFER:** PBF is adjudicated by doctrine at labeling (RD's stated disposition, rd-state line 59); D41 waits for its own arc; the October read carries 28 named-pending.

#### F3.2 -- IF F3.1 = (a): REBUILD OR SIBLING. PRIMARY RULER: **CHARC**.

- **(a1) REBUILD `provenance_corrections`** relaxing the NOT NULL recommendation citation and the two aplus-pinning CHECKs; the trigger's `ca.bucket = 'aplus'` / `dr.recommendation = 'today_decision'` clauses (`0037:900-919`) and the model (`models.py:3557-3562`) move with it.
- **(a2) A SIBLING append-only table** for hyp-rec corrections (its own schema-is-the-evidence-rule), 0036 untouched. If F1.2 is also (a2), CHARC says whether it is ONE sibling or two.

---

#### F4 -- WHERE THE PREFLIGHT LIVES. **LANDED (CHARC, ruled in the brief).**

> **F4 — WHERE THE PREFLIGHT LIVES. Ruler: CHARC.** Branch (a): a new module `swing/trades/frozen_value_evidence.py` (the conjunction, the git ancestry check via `subprocess` under a named timeout, attestation construction) — a §3 new-module tripwire, ruled IN ADVANCE: approved if the module has no DB write and is called only by the correction service's preflight. Branch (b): inside `cohort_provenance_correction.py` (already ~2,700 lines). **CHARC rules (a).**

Census note: `cohort_provenance_correction.py` is **3,414** lines at the base (`wc -l`), not ~2,700. The ruling's ground is unaffected (it strengthens it).

#### F5 -- THE TIME ANCHOR'S `origin/main` READ. **LANDED (CHARC, ruled in the brief).**

> **F5 — THE TIME ANCHOR'S `origin/main` READ. Ruler: CHARC.** Criterion 1 needs `git merge-base --is-ancestor <sha> origin/main` against a FETCHED remote ref. Branch (a): the preflight runs `git fetch origin main` itself (a network call — OUTSIDE the transaction per doctrine #9, under a timeout; failure REFUSES with a typed message). Branch (b): the preflight reads the local `origin/main` ref as-is and records its SHA + age; staleness is RECORDED never verdict-bearing (S12.1 #3's "depth and anchor-strength are recorded"). **CHARC rules (b) with the age recorded**, because a correction that cannot run offline is a correction that cannot run at the operator's gate, and the replay (doctrine #6) re-evaluates against whatever the remote says later.

Census note (measured, P24 / R0.3): the local `origin/main` ref was `348f126b`, 4 commits behind local `main`, at census time -- a recorded age of hours-to-days is the normal case, not the exception.

---

#### F6 -- R8-06: "ADMITS IFF ALL FOUR" vs THE THREE CONDITIONS THE PRE-CARVE PREFLIGHT ALSO ENFORCED. PRIMARY RULER: **RD** (the conjunction is his, S12.1 #3).

R8-06 (inherited, verbatim disposition "TRAVELS with the conjunction"): *"the plan cannot claim four and enforce six."* The three extra conditions, from the round-8 text and the 22-A findings ledger: (i) **local-`main` ancestry** beside `origin/main` (r8 case 32a); (ii) **the record post-dates the fire** -- `fire_run_ts <= record_ts` / `uncovered_seconds >= 0` (R5-05, r8 case 32h); (iii) **the record is ABOUT the cited candidate** -- quoted TICKER and ACTION SESSION bound to it (R5-05, R6-11, case 32j; the plan author's round-8 text says it states this reading *"so RD can correct it cheaply"* -- no RD ruling on it was found in the 22-A ledger, `grep` for R5-05/R6-11/32j).

- **(a) ABSORB -- the verdict stays exactly four:** (i) is DROPPED (F5 makes the local `origin/main` ref the only anchor; a commit ancestral to it but not to a behind/divergent local `main` is a local-branch state, not a tamper signal); (ii) is READ AS criterion 4 (a negative window is not a computed window); (iii) is READ AS criterion 3 ("the current candidate row" = the CITED row, and a record not about it cannot match it). Each reading carries its own per-clause discriminator.
- **(b) AMEND -- name the conditions:** RD states which of (i)-(iii) become criteria 5/6, each with its per-clause discriminator (harness 5.1), and the "four" language in S12.1 #3 is superseded by replacement.
- The branches can mix per condition; RD rules each of (i), (ii), (iii).

#### F7 -- CRITERION 2's CLOCK: WHAT "ITS RECORDED DATE STRICTLY PRECEDES THE FILL SESSION" COMPARES. PRIMARY RULER: **RD**.

A git author-date carries an offset (`9f315cc6`: `2026-08-10T02:41:33-10:00`); a fill session is an exchange DATE. The acceptance test's boundary twin ("a recorded date EQUAL to the fill session ... REFUSES", brief section 4.2) cannot be written until this is fixed.

- **(a)** the author INSTANT converted to America/New_York; its DATE strictly `<` the fill session date.
- **(b)** the author INSTANT strictly `<` the fill session's regular open, 09:30 ET (instant grain; admits a record made pre-open on the fill day).
- **(c)** the literal calendar date in the commit's OWN recorded offset (admits a record made 19:00-24:00 HST the evening before the fill session opens in ET).
- **Sub-choice, same ruler:** author-date or committer-date (both caller-settable, S12.1 #7; equal on `9f315cc6`).
- Trade 25 is unaffected under all three (seven days' margin).

#### F8 -- CRITERION 3's SQL ENCODING UNDER THE SINGLE ROUNDING AUTHORITY. PRIMARY RULER: **CHARC** (shape; the rounding principle is RD's and is LANDED).

Premise: the key roster as reviewed pre-carve (r8 lines 2562-2563) bound *"`quoted_pivot` and `quoted_invalidation`, each BOUND by subquery to the cited candidate's own `round(...,2)`"* -- a SQLite-side rounding binding, the exact form S4.3a (landed later, 22A-R8-10) forbids. The post-carve struck block (plan `:2388-2395`) names only "the `quoted_*` bindings", with no shape. S12.1 #4 permits two forms; S4.3a's three obligations select between them.

- **(a) The 0037 probe precedent.** The blob carries the numerals AS QUOTED (`quoted_pivot_text` "53.98", `quoted_invalidation_text` "41.42"), the `live_*_raw` operands bound to the candidate's REAL columns by plain `=` identity, the service's verdicts `*_equal_at_dp = 1` and `compare_dp = 2`; SQL never rounds; the S4.3a residual is declared (SQL cannot verify the verdict; a forger cannot cite a different candidate). Optional in (a): SQL asserts `instr(quoted_text, quoted_*_text) > 0` (a consistency check with no rounding).
- **(b) Canonical pre-rounded, compared bytewise.** The service stores a canonical 2dp text for the candidate and SQL compares it bytewise to the quoted text. SQL cannot bind that canonical text to the REAL column without rounding (`printf('%.2f')` IS a rounding), so the canonical value is UNBOUND -- strictly weaker than (a) on the identity axis.
- **Census reading:** (a). Routed because the struck text is silent and the choice fixes the key roster.

#### F9 -- THE `--frozen-value-evidence` INPUT CONTRACT. PRIMARY RULER: **CHARC**.

Round-8 S2.7 said the file carries three required fields -- `artifact` (path + commit SHA), `quoted_text`, `uncovered_window` (operator PROSE) -- while the same section says the service COMPUTES the window *"never from a duration the operator typed"*, and S4.3 demoted the prose to untrusted display text.

- **(a)** The file carries ONLY `{artifact_path, artifact_commit_sha, quoted_text}`; the service computes every number and renders `uncovered_window_prose` itself.
- **(b)** Round-8's three fields; the operator's prose is stored as untrusted display text beside the machine-computed numbers.
- **Sub-choice, same ruler:** `ruling_citation` (a required key of the struck roster) is operator-supplied, or a module constant naming S12.1 / RD 2026-08-24.
- Either way the CLI manifest pin moves five -> six in the same commit (brief section 2 IN).

#### F10 -- WHERE REPLAY RUNS, AND WHAT A FAILED REPLAY DOES TO A WRITTEN ROW. PRIMARY RULER: **RD** (doctrine #6).

The round-8 text defines replay's criteria and outcomes (re-evaluate the four; any failure refuses `tier2_evidence_stale`; grown descendants admit) and never its SITE; S12.1 #10 says "re-derived at each use". Two fixed facts collide: (1) CLAUDE.md -- *"SELECT-first idempotency MUST precede payload validation -- a terminal-state row must return its existing audit-row id"* -- and the apply's already-applied path returns before ANY check (`cohort_provenance_correction.py:2021-2029`); (2) an append-only row can be neither voided nor rewritten (`0036:708-713`; `0037:2193-2290`).

- **(a) Replay is a READ-TIME VERDICT.** The drift reader (`journal provenance-corrections`) re-evaluates the four criteria for every tier-2 row against the stored attestation and REPORTS `ADMIT` or `tier2_evidence_stale` beside it, with its own `evaluated_at`; the apply's already-applied path stays SELECT-first; the row is never touched. **RD sub-ruling needed:** does a row reading `stale` still count in cohort reads (H1)?
- **(b) Replay is the APPLY PATH.** An already-applied re-run re-evaluates and REFUSES on failure -- which breaks the SELECT-first contract for tier-2 rows and needs RD to say the gotcha yields here, and what a refusal means for a row that already exists.
- **(c) Both** (a)'s read verdict and (b)'s refusal.
- The acceptance test's section 4.3 ("REWRITTEN ... REFUSES; descendants GROWN ... ADMITS") is specifiable only once the site is ruled.

#### F11 -- HOW A TIER-2 ROW RECORDS RUNG 9, AND THE TRIGGER BRANCH'S SHAPE. PRIMARY RULER: **CHARC**.

Premise (P26): the tier-2 row's probe blob is the FULL latch blob (guards + probe run after the escape). Today the trigger's `latch_ladder` branch requires `rung9_stored_freeze_tier.input = 'live_at_acceptance'` AND `cited_candidate_id > boundary` (`0037:2022-2039`).

- **(a) Blob unchanged (`evidence_version '2026-08-25.1'`), rung 9 recorded truthfully:** `rung9_stored_freeze_tier.input = 'pre_barrier_reconstructed'`, `verdict = 'pass'`; a NEW trigger branch for `latch_ladder_tier2` = the `latch_ladder` branch with the rung-9 clause inverted (`input = 'pre_barrier_reconstructed'` AND `cited_candidate_id <= boundary`) PLUS the seventh-column schema; the tier column says why rung 9 passed.
- **(b) Blob version bumped; rung 9 gets its own verdict value** (e.g. `escaped_by_tier2`) so the probe blob itself states the escape; the `$.authorization` closure roster (L17 / AL-3, `tests/data/test_22a_al3_closure.py`) and the verdict vocabulary widen with it.
- Authorize-then-abort (brief section 4.4) applies to either: every predicate of the new branch maps to a named service check.

---

### R0.5 LANDED -- recorded, not re-opened

- **S12.1 #1-#10** (the settled doctrine), **S4.3a** (the single rounding authority, measured by execution), and **S12.2's dispositions** travel AS RULED (RD's binding condition). Where each inherited finding lands in this census: R6-02 -> F2/F2.T residual; R6-03 (three-valued half) -> F2(a) only; R6-04 -> LANDED (S12.1 #5; attestation keys in the roster); R7-01 -> F2.I; R7-02 -> F2(a) only (dormant under (b): `CHECK (epoch_id = 1)` + `trg_candidates_epoch_no_insert`); R7-03 (three-valued CASE) -> F2(a) only; R7-06 -> LANDED (`evaluated_at`, `verification_method`, `resolved_remote_ref_sha` are roster keys); R8-01 / R8-03 -> F2.I constraints; R8-02 -> F2(a) only; R8-06 -> F6.
- **Brief section 2 OUT:** the S12.2b items (`22A-R13-02/03/04/05`, `22A-R14-01/03/04/05/06`) -> `22-A2i`; 22-B; `trades.initial_stop` correction; any UI.
- **F4 and F5** -- block-quoted above.

### R0.6 Instrument notes for the plan (not forks; recorded so execution finds them in seconds)

- **Section 4.2's criterion-3 discriminator needs BOTH twins:** the five-cent REFUSE (quoted 53.98 vs a candidate at 53.93) and an eighth-dollar ADMIT (a candidate at `22.125` quoted "22.12": Python half-to-even says equal; a SQLite `round` would say 22.13) -- the second is what proves no rounding artefact can REFUSE a truthful row. S13's R9-05 correction applies (`22.125` / `22.1249`).
- **P27** -- the witness quotes the H1 reader's number at the gate; no expected count is pinned in the plan.
- **P28** -- 0039 needs a `backup_gate_for_pre_version` row or it takes the CLI's no-gate snapshot; the D32 production proof depends on which.
- **The fill-48 reading is written by the correction itself** (P13) -- the plan's witness reads `fill_envelope_identity` before and after.

### R0.7 RULINGS -- CHARC (round 0), LANDED 2026-09-22

**Author: CHARC. Courier: the orchestrator.** Transcribed BYTE-FOR-BYTE from `comms/orchestrator/read/20260922T231123Z-charc-22-a2-round-0-rulings-charc-f8-a-f9-a-f1.md` (posted 2026-09-22T23:11:23Z), the span from the F8 heading to the start of CHARC's non-ruling notes. The `—` sequences are as delivered by the mailbox and are left unexpanded so the copy stays literal. F1.2, F2.T and F3.2 are CONDITIONAL on RD's rulings on F1.1, F2 and F3.1 respectively, and are live only if those preconditions land. RD's items (F1.1, F2, F2.I, F3.1, F6, F7, F10) remain OPEN; no round runs while any is unruled.

---- RULING F8 (unconditional) ----

> **F8 — CRITERION 3's SQL ENCODING: (a), the 0037 probe precedent, with the consistency check REQUIRED, not optional.** The blob carries the numerals AS QUOTED (`quoted_pivot_text`, `quoted_invalidation_text`) and the service's verdicts (`*_equal_at_dp`, `compare_dp`); the `live_*_raw` operands are bound by the trigger to the cited candidate's REAL columns by plain `=` identity; SQL never rounds, never re-derives the verdict. REQUIRED: the trigger asserts `instr(quoted_text, quoted_pivot_text) > 0 AND instr(quoted_text, quoted_invalidation_text) > 0` — a no-rounding consistency check that a citation cannot claim a numeral its own quoted text does not contain. (b) is refused because a canonical text SQL cannot bind to the real column is an UNBOUND operand, and an unbound operand is what the identity axis exists to forbid. The S4.3a residual (SQL cannot verify the verdict) is DECLARED with its reason in the plan's accepted limitations; the discriminator pair in R0.6 (five-cent REFUSE, eighth-dollar ADMIT at 22.125 / 22.1249) is MANDATORY in the roster.

---- RULING F9 (unconditional) ----

> **F9 — THE `--frozen-value-evidence` INPUT CONTRACT: (a). The file carries ONLY `{artifact_path, artifact_commit_sha, quoted_text}`.** The operator supplies a SELECTION, never a value: the service reads the artifact at that SHA (`git show <sha>:<path>`, the preflight, outside any transaction) and REFUSES with a typed message if `quoted_text` is not a byte-substring of it; every number — the window, the interval, the descendant count, the ref age — is computed by the service, and `uncovered_window_prose` is rendered by the service, never typed. This is the Demand-C posture ("no value parameter at all, so free-typing is UNREPRESENTABLE") applied to evidence. Sub-choice: `ruling_citation` is a MODULE CONSTANT naming S12.1 and RD's 2026-08-24 ruling, not an operator input. The CLI manifest pin moves five → six in the same commit as the option.

---- RULING F11 (unconditional) ----

> **F11 — HOW A TIER-2 ROW RECORDS RUNG 9: (b). Rung 9 gets its own verdict value (`escaped_by_tier2`), the blob version bumps, and the vocabulary widens with it.** (a) is refused on doctrine #5: a stored grade is an ATTESTATION OF WHAT WAS VERIFIED — rung 9 did NOT pass on its own evidence for a pre-barrier input, so `verdict = 'pass'` there is a false attestation that reads true only after a join to the tier column. The blob must state the escape in its own voice. The bump is the DESIGNED mechanism for a vocabulary change (22A-R14-01's lesson is exactly a behaviour change without one). The new `latch_ladder_tier2` trigger branch requires ALL of: `rung9.input = 'pre_barrier_reconstructed'`, `rung9.verdict = 'escaped_by_tier2'`, `cited_candidate_id <= boundary`, the five latch citation columns AND the seventh NON-NULL. The existing `latch_ladder` branch gains the inverse clause: it REFUSES a blob whose rung-9 verdict is `escaped_by_tier2` — the per-clause discriminator that an escape cannot be laundered into a tier-1 row. Authorize-then-abort: every predicate of both branches maps to a named service check, closure-asserted both ways; the AL-3 `$.authorization` roster and the #11 drift test widen in the SAME commit, each new member grepped separately.

---- RULING F1.2 (CONDITIONAL — live only if RD rules F1.1 = (a)) ----

> **F1.2 — THE WRITE SHAPE FOR RELABELLING ENTRY-DERIVED KEYS: (a2), a SIBLING append-only table whose SCHEMA IS ITS OWN EVIDENCE RULE; `provenance_corrections` and 0036/0037 are NOT rebuilt.** A rebuild that relaxes 0036's pre-envelope CHECK weakens the evidence rule for EVERY row to admit ONE new class; the D36/AL-3 principle ("make the property a check the code performs") is served by a table whose CHECKs state the new class's admissibility, not by loosening the old table's. The sibling carries: the non-empty pre-value envelope recorded, the new class's citation columns with their own CHECK set, the append-only TRIPLE (`no_update` + `no_delete` + conflict-scoped `no_replace`, the 22-I convention), and a citation-graph trigger of its own. THE COST, which the plan must pay explicitly: ONE authoritative correction head per trade ACROSS tables — SQL cannot express a cross-table UNIQUE, so it is a `BEFORE INSERT` trigger with a cross-table `EXISTS` check on each sibling (the 0036 citation-graph guard's shape) plus its Python mirror, and every governed cohort reader (`cohort_intent.py`'s four, D29) reads the head across the union — the plan names the reader set with its search. The brief's chain shape is WITHDRAWN for 19/24 (the census is right: nothing to supersede; the UNIQUE(trade_id) collision is real) and is NOT re-proposed unless RD names a live re-correction case.

---- RULING F2.T (CONDITIONAL — live only if RD rules F2 = (b) defer) ----

> **F2.T — MAKE THE PROCEDURAL HALF MECHANICAL: (t1), the suite test, with two bindings.** (1) The six names are IMPORTED from `BARRIER_TRIGGER_NAMES` (`candidates_immutability_epoch.py:167`), never re-typed — a re-typed roster is the D21 decay class. (2) The test scans every migration file numbered above 0037 for a `DROP TRIGGER` naming any of the six and FAILS unless the same file carries an era record (the marker's exact form is the plan's to specify and pin). Composition note for the plan: D51's manifest fixture is BLIND to R6-02 by construction (a DROP in migration N and a byte-identical CREATE in N+k leaves HEAD's manifest unchanged), so (t1) is the only instrument that sees the file-borne retire; the hand-run DROP residual is DECLARED in the accepted limitations with its reason, exactly as P14 states it. (t2) is refused: a rule that lives only in a header is the D28 shape.

---- RULING F3.2 (CONDITIONAL — live only if RD rules F3.1 = (a)) ----

> **F3.2 — REBUILD OR SIBLING FOR HYP-REC CORRECTIONS: (a2), a sibling, on the same ground as F1.2.** The two aplus-pinning CHECKs and the NOT NULL recommendation citation are 0036's evidence rule for the A+ class; relaxing them for hyp-recs would let an A+ row cite a watch candidate. ONE SIBLING OR TWO (if F1.2 is also live): a sibling table is shared only if the two classes' CHECK SETS ARE IDENTICAL; they are not (relabel needs a non-empty pre-envelope, hyp-rec needs a nullable recommendation and a `watch` bucket with a registered-profile match), so TWO tables, each named for its class, each with its own citation-graph trigger, both under the cross-table one-head rule from F1.2. The trigger's `ca.bucket = 'aplus'` / `dr.recommendation = 'today_decision'` clauses in 0037 are UNTOUCHED.

**CHARC's notes carried (not rulings):** P27 is CHARC's error, owned. Brief section 5's "2/20 -> 3/20" is REPLACED for this arc by: the witness quotes the H1 reader's number, and the plan pins no expected count. The brief on main is not edited mid-arc. P28: 0039 adds its `backup_gate_for_pre_version` row; the plan states which backup fires.
