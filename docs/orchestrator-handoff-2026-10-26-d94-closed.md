# Orchestrator handoff -- 2026-10-26 -- D94 (a)+(b) merged and witnessed; D84 is next and STOPS before executing

**Supersedes:** `orchestrator-handoff-2026-10-19-d79-packet-out.md`.
**From:** the generation bootstrapped 2026-10-19 (session `61e4dd1e`, Opus 5.5). This generation is OVER the cap:
- It never ran the self-read gauge, peaked at **965,155**, and was auto-compacted.
- It is rolling now on the operator's word: "roll over after the merge and checks".
- **Run `python scripts/cell_depth.py --sessions --live 1` at every arc boundary and before every dispatch. Roll at ~400K** (harness-architecture §"THE ROLLOVER SEQUENCE"; the rule is in orchestrator-context §"Anti-patterns", `ff0a0f01`).

**Re-derive every fact below. Each one carries its method.**

## 1. STATE (verified at write time)

- **`main`:**
  - `git rev-parse --short HEAD` gave `65c3ffdd` before this commit.
  - `git status -sb` gave `ahead 50` of `origin/main`. **NOT pushed; the push is the operator's.**
- **Schema v41.** Method: `SELECT max(version) FROM schema_version` on a `mode=ro` connection.
- **Merged this generation:**
  - **D87** (`501247a2`).
  - **The maintenance rider** (`29679b05`).
  - **D89** (`717e4ebe`).
  - **D90** (`baac5c20`).
  - **The wall-clock test fix** (`00d2d818`).
  - **D94 (a)+(b)** (`8008800a`):
    - merged-head suite 15559/13/0, read from `~/swing-data/review-transcripts/d94-cancel/merge/merged-head-suite.txt`;
    - census at `merge/census-merged.txt`;
    - CHARC cleared at `8bedfb7a`; RD's clearance is attached at `8008800a`;
    - the live witness PASSED, record posted `20261026T061628Z`. The operator recorded IMNM ...712's cancel as intent 14. No indeterminate tickers.
- **Worktrees:** ONE (main only). Method: `git worktree list`.
  - `.worktrees/d94-cancel` is removed.
  - Branch `d94-cancel` is KEPT, because both D94 ledgers cite it.
- **Cells:** none RUNNING. Method: `python scripts/cell_depth.py --live 2`.
  - Every `parked` cell listed belongs to a merged arc (D87, the maintenance rider, D79, D89, D90, D94), and its state is on main. **None will be resumed.**
- **Inbox Monitor:** none was running at roll time. Method: a `Win32_Process` CommandLine match on `orchestrator[/\\]inbox` returned nothing. **Arm one at bring-up** (harness-architecture §WAKE-ON-MAIL).
- **Directors:**
  - CHARC `swing-charc-20261021-2332`;
  - RD `swing-rd-20261025-1722`.
  - Trust the `ping ->` line.
- **Schwab:** re-authenticated 2026-10-25; the refresh token is valid to **2026-11-02T05:20Z**. The `accounts.orders.list` read timed out at 30 s twice in two days (`schwab_api_calls` 17540); a reload succeeded in 22 s. Treat it as transient unless it recurs.
- **The operator's `swing web`** on 8080 was restarted on `8008800a` code during the witness.

## 2. NEXT, owner = you: D84, the capital SOFT-STOP arc

- **Commissioning:** CHARC's dispatch `comms/orchestrator/read/20261025T164200Z-charc-d84-opens-hold-lifted-2026-10-25-plan-lo.md`. RD's proposal `docs/rd-proposal-soft-stop-arc-screen-widening-rider.md` @ `b266cc97`, sections 3 and 6. The register row is D84 in `docs/tool-director-context.md`.
- **The operator's words** (2026-10-25, AskUserQuestion): "Yes, hold is lifted"; for D84, "Stop before executing (Recommended)"; "D94 web fix first (Recommended)". CHARC carried that reading at `d9c9f149` (mail `20261026T025418Z`).
- **The authority covers:** brainstorm, writing-plans, and the plan-stage director review. Post ONE query covering CHARC's items F1-F6 and RD's population and cohort items.
- **Then STOP for the operator's word before any executing cell.**
- **NOT in D84:** the Finviz widening rider (proposal section 4). That is an operator config edit on the night AFTER the arc merges, with RD's boundary note.
- **F5 can turn into a SCHEMA tripwire:** does "H1 = aplus AND risk pass" change the sha256-pinned 0034 text? The plan must answer it.

## 3. AUTHORITIES (a grant is STATE)

- D84: brainstorm, plans and plan review only (section 2). **There is no executing grant.**
- D94 (a)+(b): SPENT at the merge. The operator's live-ledger click on ...712 was given per-action ("yes") and is SPENT.
- No authority was granted by cell message this generation that is not already in an arc ledger.

## 4. OPEN / OWED

- **Registered and not commissioned:**
  - D91, D92, D93, D95 (see the register rows);
  - D94 (c), the broker-history tier (the schema question);
  - the governing-child duplicate spellings, banked at the D94 R1-3 ruling (see the D94 exec ledger).
- **Push:** `main` is 50 ahead of origin, and pushing is the operator's call.

## 5. WHAT WILL BITE YOU

- **Context.** Command output goes to a FILE and is read with a bounded `tail`/`grep`. **Reviewer B is YOURS:** never give it to a cell. Route its output to the transcript file and read only the findings and the verdict line. Memory: `feedback_orchestrator_context_hygiene`.
- **The merged-head suite runs ~12 min at `-n 8`** (`-n auto` ran out of memory). Background it, with the head SHA on line 1 of the file.
- **A schema-free merge does NOT stop a running `swing web` from serving OLD code.** Stop it, verify the port is free (`Get-NetTCPConnection -LocalPort 8080`), and restart it before any witness.
- **The operator may ask you to drive the browser** (claude-in-chrome works here). Any WRITE click still needs his per-action word.
- **Every role_mail post goes from the MAIN repo cwd** with an explicit `--type`. The subject must be 80 characters or fewer. Drain with `role_mail.py read --role orchestrator --id <file>`.
