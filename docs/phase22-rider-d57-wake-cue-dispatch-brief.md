# Phase 22 rider — D57: the mailbox wake CUE is a cross-session ping, not a timer (dispatch brief)

**From:** CHARC. **To:** the orchestrator (riders stage: executing directly, no plan loop; no reviewer B — no production code under `swing/`). **Operator pre-authorized 2026-09-15 ("let's get working on this") after the probe below.** **Cell:** `implementer-sonnet-high` (settled design; PowerShell + Python + docs, all small; the launcher test file is the only careful part). **Worktree:** `.worktrees/d57-wake-cue` off `main` at or above the commit that lands this brief. **Rules read from main:** `docs/implementer-dispatch-recipe.md`, `docs/harness-architecture.md` §3 — the cell names the SHA it read them at.

## §0 READ FIRST (pointers)

- The finding and the interim rule: `docs/harness-architecture.md` §3 WAKE-ON-MAIL (amended 2026-09-15, `d80f5f17`); register row D57 in `docs/tool-director-context.md`.
- The probe that settles the design (2026-09-15, CHARC → RD, thread `wake-on-mail-cost`): a cross-session `SendMessage` to an IDLE seat on build 2.1.272 started a new turn at the receiver within 6 s of the send (RD transcript `39bac9c3`: send 07:19:48Z, `cross-session-message` record 07:19:54Z, first assistant record 07:19:58Z, nothing else in the window; no Monitor armed, no hook fired). Delivery also crossed permission modes (sender auto, receiver `prompting`). So the cue costs ZERO while idle and ONE wake per real message, with no launcher change and no timer.
- Session naming today: `scripts/start_directors.ps1:New-SessionName` mints `director-<role>-<yyyyMMdd-HHmm>` / `orchestrator-<stamp>` and records `role -> session_name` in `comms/.sessions.json` (`Save-SessionMap`), overwritten on every fresh launch — so the map ALWAYS names the CURRENT generation of each seat, which is exactly what a sender needs across a rollover.
- The cross-project collision is real: coa-chess names its orchestrator `orchestrator-<stamp>` too (ListAgents on 2026-09-15 showed `orchestrator-20260914-1823` (ours) beside `orchestrator-20260914-1831` (theirs)). A bare-name send is refused when two rows share the name, and the `[ref]` fallback is a hand step — the D28 class.

## §1 THE CHANGE, exactly

**C1 — project-prefixed session names (launcher), OPERATOR-AMENDED 2026-09-15: the `director` segment goes.** `New-SessionName` returns `swing-<role>-<stamp>` for EVERY role — `swing-charc-<stamp>`, `swing-rd-<stamp>`, `swing-orchestrator-<stamp>` — one branch, no director/orchestrator special case (the orchestrator's non-`director-` carve-out becomes moot). Nothing else about the launcher changes. Until the live orchestrator rolls onto the new name, both projects' orchestrators are `orchestrator-<stamp>`; a sender pings ONLY the full dated name from `comms/.sessions.json` (ours: `orchestrator-20260914-1823`; coa-chess's is `-1831`), never a prefix. The tests in `tests/scripts/test_start_directors_orchestrator.py` that pin the literal strings (`:141`–`:177`: `'return "director-$role-$stamp"'`, `"session name 'director-charc-"`, `"director-orchestrator-" not in out`) are UPDATED to the prefixed forms in the SAME commit — this is a deliberate rename of the thing they pin, not a drift; the commit message says so. Verify by `-DryRun` for `charc`, `rd`, `orchestrator` (the DryRun path is already exercised by those tests).

**C2 — `role_mail post` prints the ping line (the mechanical nudge).** After each `posted -> …` line, `cmd_post` prints ONE line per recipient role, read from `<comms_root>/.sessions.json`:

    ping -> SendMessage to="<session_name>"      (a role with a recorded session)
    ping -> operator: no session (GUI/relay)     (the operator role, always)
    ping -> <role>: no session recorded          (a role absent from the map, or no map)

Read-only; a missing/malformed map NEVER fails the post (the post already succeeded — print the third form and continue). The `pipeline` automated sender gets the same lines (it cannot act on them; harmless). Tests on a `tmp_path` comms root: (i) map present → the exact line with the recorded name; (ii) no map → the third form, exit 0, the message still written; (iii) malformed JSON → same as (ii); (iv) `operator` recipient → the second form. No change to `post_message` (the single write path) — this is output only.

**C3 — the sender convention (docs; the cell edits the text VERBATIM as given here).** In `scripts/director_bootstrap_charc.md`, `scripts/director_bootstrap_rd.md`, `scripts/orchestrator_bootstrap.md`, the paragraph beginning `   Then WAKE-ON-MAIL (harness-architecture section 3; adopted 2026-09-07,` through the line ending `the cost is the harness WAKE, not the loop.` is REPLACED (not annotated) by:

    Then WAKE-ON-MAIL (harness-architecture section 3; adopted 2026-09-07,
    re-based 2026-09-15 on the cross-session cue): do NOT arm an inbox
    Monitor. The wake is a cross-session ping: after EVERY `role_mail post`,
    run the `ping ->` line(s) it prints -- one SendMessage per recipient seat,
    to the exact session name printed (it is read from comms/.sessions.json,
    which the launcher overwrites at each fresh start, so it always names the
    CURRENT generation), with a one-line body naming the project, your role
    and the subject, e.g. "swing-trading <role>: mail posted -- <subject>".
    A ping to you wakes you as a new turn at zero idle cost: drain with the
    read command above. Never put content in the ping -- the mailbox is the
    record, the ping is the cue. Do not use ListAgents to pick a target by
    eye: a bare role name is ambiguous across projects on this box (coa-chess
    seats share the scheme), which is why the printed name carries the
    `swing-` prefix. Idle mode is the UserPromptSubmit unread line, the Stop
    hook's continue-on-unread, and the operator's relay -- nothing else runs.

The following sentence (`ONE RULER PER ITEM binds you from your first drain: …`) is kept as is. The ROLLOVER block's act 3 (`TaskStop your inbox Monitor …`) in each bootstrap becomes: `3. If a Monitor of yours is still armed (a pre-2026-09-15 generation), TaskStop it and verify as before; a generation on the ping convention has nothing to stop.` — keep the existing verification text after that sentence unchanged.

**C4 — `docs/harness-architecture.md` §3** and **register D57**: CHARC lands these BEFORE dispatch (the commit that carries this brief); the cell does not touch them.

## §2 FORK CENSUS (the rulings are made; nothing is open)

- **Prefix placement:** PREFIX (`swing-…`), ruled 2026-09-15 — seats of one project cluster in a sorted listing and the mailbox is already scoped by repo. coa-chess adopts `coa-` on its side by the operator's relay; not this arc.
- **Ping content:** cue only; never the message. The mailbox stays the record (harness §3, transport-not-tracker).
- **Where the name comes from:** the launcher's map, printed by `role_mail post`; NEVER a hand-picked ListAgents row. The rollover overlap (outgoing seat still open in its pane after the successor launched) is closed by construction: the map already names the successor at act 4, and the outgoing seat stopped draining at act 2.
- **Cells:** a subagent's send goes out under its parent's address; cells never post to directors (return reports go through the orchestrator after QA), so the convention binds the three seats only.
- **Monitor on 2.1.266 seats:** the two live pre-update seats (CHARC, orchestrator) may keep their persistent Monitor until they roll; every seat launched from now on is on the ping convention. No transitional code.

## §3 SCOPE — exactly this, refuse the rest

`scripts/start_directors.ps1` (C1) + its test file · `scripts/role_mail.py` `cmd_post` output (C2) + tests under `tests/scripts/` · the three bootstrap docs (C3). NOTHING under `swing/`; no change to `post_message`, to the hooks in `.claude/settings.json`, or to the comms GUI. Suite: the fast suite on the final head (the inline-edit rule: a tracked script change gets a suite run, not a smoke test).

## §4 THE WITNESS

After merge, the operator launches ONE fresh seat with the new launcher (`-Role rd -DryRun` first, then for real, at RD's next rollover or on the operator's word) and: (1) the printed session name carries the `swing-` prefix and appears in another seat's `ListAgents`; (2) from that other seat, `role_mail post --to rd …` prints the `ping ->` line with that exact name; (3) the sender runs the ping; (4) the fresh seat wakes as a NEW TURN with no Monitor armed and drains — read off its transcript by the same method as the probe (the `cross-session-message` record's timestamp against the send). Step by step, one step per operator result.

## §5 RETURN

The ORCHESTRATOR posts the return report to `charc` after QA (the rider's own QA: tests green on the final head, the three DryRuns, the four C2 test cases named). CHARC closes D57 on the §4 witness, not on the merge.
