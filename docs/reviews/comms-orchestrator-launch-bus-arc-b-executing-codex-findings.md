# Codex review findings — G6 Arc B orchestrator launch + GUI bus PLAN (writing-plans, review-fast tier)

Plan: docs/plans/comms-orchestrator-launch-bus-arc-b-plan.md
Tier: review-fast. Transport: WSL-native codex-cli 0.135.0. Profile: review-fast (model gpt-5.4-mini).
Mechanism: prompt (.codex-review-prompt.md) + full plan piped via stdin; -s read-only --skip-git-repo-check.

## Round 1 (-p review-fast; profile effort=low)
### Codex response (verbatim)
NO_NEW_CRITICAL_MAJOR
### Adjudication
Round 1 ran at the profile's default reasoning effort=low (gpt-5.4-mini) and returned the verdict with ZERO findings. A zero-findings low-effort pass is thin for an adversarial gate, so I re-ran at high reasoning effort (recipe permits forcing effort UP; the binding rule is NEVER effort=none + run to convergence) to obtain a credible adversarial read. See Round 2.

## Round 2 (-p review-fast -c model_reasoning_effort=high)
### Codex response (verbatim)
- **MAJOR** | **§1.3 / Task 3**: The bus helper is only specified to catch `OSError` after trusting `registry.is_valid_session_id(child.name)`. The stated contract for `per_generation_inbox(root, sid)` is that it raises `ValueError` for unsafe IDs, and the requirement here is "degrade to empty / skip bad entries, never 500." As written, a registry/helper mismatch or a validator failure can still bubble out of the child walk and 500 the pane. **Fix:** make the per-child resolution path self-contained and skip-safe: catch `ValueError` as well as `OSError` around the `is_valid_session_id` / `per_generation_inbox` sequence, and continue on any registry/path validation failure.

- **MINOR** | **§2, Task 1b**: The DryRun test is skip-gated on both `powershell` and `claude`, so it will often not run in CI, and the extra `assert "DRY RUN" in out` is not grounded in the documented dry-run contract. That makes it brittle and weak as a red->green distinguisher. **Fix:** assert only the documented outputs from the dry-run path (`$env:SWING_ROLE='orchestrator'`, exact claude command, bootstrap path, no launch/map write), and if you need coverage without environment-dependent skips, mock the preflight `claude` lookup instead of skipping the test.

VERDICT: NEW_CRITICAL_MAJOR_PRESENT
tokens used: 33,316

### Adjudication (Round 2)
- MAJOR (§1.3/Task 3) — ADOPTED. The plan relied on `is_valid_session_id` as the sole pre-guard + an `OSError`-only except. Broadened the per-child AND outer guards to catch `(OSError, ValueError)` so any registry-contract drift / validator disagreement (or a `per_generation_inbox` ValueError that slips the pre-guard) degrades to a SKIP / empty bus, never a 500. Defense-in-depth atop the pre-guard, honoring the brief's defensive-never-raises lock. Plan §1.3 updated.
- MINOR (§2 Task 1b) — PARTIALLY ADOPTED / clarified. Note: `assert "DRY RUN" in out` IS grounded — the launcher prints `Write-Info "DRY RUN -- no windows launched, session map not written."` (start_directors.ps1:291). Clarified the distinguisher-burden split: the always-runs static-content Test 1a is the deterministic CI distinguisher for the launcher delta; the skip-gated subprocess Test 1b is a BEHAVIORAL net that runs on the operator's box (where the merged-head no-false-green re-run executes — both `powershell` and `claude` are present there), so the skip is intentional and acceptable (Test 1a carries the distinguishing load). Mocking the `claude` preflight inside a spawned PowerShell subprocess is not practical; the skip-guard is the honest path. Permitted the executing implementer to drop the `"DRY RUN"` assert if it proves environment-fragile, keeping the load-bearing asserts. Plan §2 Task 1b updated.


## Round 3 (-p review-fast -c model_reasoning_effort=high; over the R2-revised plan)
### Codex response (verbatim)
- **MAJOR** | **§1.3 / Task 3b**: The ordering requirement is not actually distinguished. `test_orchestrator_bus_newest_active_generation_first` uses `gen-new` and `gen-old`, which already sort in the expected order lexicographically, so a buggy implementation that orders generations by directory name could still pass. The proposed implementation key also uses the newest message filename, which is not the same thing as "newest-active generation" and can misorder quiet-but-newer sessions behind older chatty ones. **Fix:** Make the ordering source authoritative and hard to fake. Use registry/session-start metadata for recency, and choose test fixtures whose lexical order conflicts with the intended order so an alphabetical sorter fails.

- **MAJOR** | **§1.3 / Task 3 implementation**: The plan enumerates generations by scanning `comms/orchestrator/<sid>/` on disk and explicitly keeps showing directories even if the session was pruned from `comms/sessions/`. That makes the bus reflect stale/orphaned directories instead of live registry state, which conflicts with the registry seam the brief already introduced and can surface generations that no longer exist. **Fix:** Treat the registry as the source of truth for generation enumeration. Use `read_entries` to find valid sessions, then derive inbox paths with `per_generation_inbox`; keep the defensive skip/empty fallback for missing inboxes or bad entries.

VERDICT: NEW_CRITICAL_MAJOR_PRESENT
tokens used: 32,560

### Adjudication (Round 3)
- MAJOR #1 (§1.3/Task 3b ordering) — PARTIALLY ADOPTED. The test-distinguishing defect is REAL and ADOPTED: the Test 3b fixtures (`gen-new`/`gen-old`) align ascending-sid order with the intended order, so a naive `sorted(iterdir())` (ascending-sid) sorter would coincidentally pass. FIXED the fixtures so the NEWEST-message gen has a lexically-LATER sid (`gen-aaa`=old msg, `gen-zzz`=new msg; assert `index("gen-zzz") < index("gen-aaa")`) — now an ascending-sid bug FAILS, only a recency sort PASSES. The semantic half (newest-message != newest-started generation) is REFRAMED, not changed: the ordering is now explicitly named "most-recently-MESSAGED generation first," which is the correct, precise semantic for a MAIL bus (the operator wants the gen with the freshest mail at the top) and is the only recency signal uniformly available across ALL disk-enumerated gens (including pruned ones with no registry entry). NOT coupled to registry started_ts — see MAJOR #2.
- MAJOR #2 (§1.3/Task 3 enumerate-from-registry) — REJECTED with citation. This CONTRADICTS the brief's explicit design. Brief §2 item 3: "a read-only `_orchestrator_inbox_messages(root)` that walks `comms/orchestrator/<sid>/inbox` across ALL generations." Reconciliation-notes lessons-learned guard #1: "newest_live == None is NOT 'window closed' -- the gen may be idle>45min (pruned) yet resumable ... Registry-pruned != gone." A generation pruned from `comms/sessions/` (idle >45min) is still RESUMABLE and its queued mail MUST stay visible -- that is the entire reason per-gen inboxes are durable across rotation. Enumerating from `read_entries` would HIDE messages queued for a pruned-but-resumable generation, a regression against the brief's intent. The "stale/orphaned directory" framing is wrong for this domain: the per-gen inbox is intentionally durable. Disk enumeration (with the `is_valid_session_id` pre-guard + the `(OSError, ValueError)` defensive skip) is the brief-mandated, correct behavior. Added an explicit note in §1.3 to preempt re-flagging.

## Round 4 (-p review-fast -c model_reasoning_effort=high; over the R3-revised plan)
### Codex response (verbatim)
- **MAJOR | 1.3 / Task 3 (enumeration)**: makes the filesystem walk the primary source of generation IDs and rejects `read_entries` on an "unverified pruned-but-resumable assumption"; can miss a registered-but-empty generation and admit stale/manual directories. **Fix:** use the registry as the source of session IDs; directory walk only as a defensive fallback.
- **MAJOR | Task 3b (ordering test)**: with `gen-zzz` (newer msg) and `gen-aaa` (older), a sort-by-sid-DESCENDING impl still passes; 2 gens can't distinguish recency from both name-sort directions. **Fix:** fixtures whose sid order conflicts with recency in BOTH directions, or assert the exact rendered header order.
- **MINOR | Task 3a / 3d (sid validity)**: seeded sids assumed valid without grounding in the real `is_valid_session_id` contract.

VERDICT: NEW_CRITICAL_MAJOR_PRESENT
tokens used: 16,902

### Adjudication (Round 4)
- MAJOR enumeration — REJECTED, now with LIVE-CODE verification (Codex lacks the brief; it reasons from general principles). Verified on disk: `comms_session_registry.prune_stale` unlinks ONLY `comms/sessions/<id>.json`, NEVER `comms/orchestrator/<sid>/` (the per-gen inbox persists across pruning); and the SessionStart hook calls `ensure_per_generation_inbox` (`comms_session_hook.py:111`, re-ensured on resume :133) which CREATES `comms/orchestrator/<sid>/{inbox,read}` at register time. Consequences: (a) a "registered-but-empty" gen HAS an inbox dir on disk -> the disk walk DOES show it (rendered "(empty)"), so Codex's "can miss a registered-but-empty generation" is unfounded; (b) a pruned gen's inbox + its queued mail PERSIST on disk and are invisible to `read_entries` -> enumerating from the registry would HIDE mail delivered to a pruned-but-resumable gen via role_mail's registry-INDEPENDENT `:<sid>` form, a regression against brief §2 item 3 + lessons-learned guard #1. Disk enumeration is the brief-mandated, live-code-correct behavior. Strengthened the §1.3 note with this evidence and added the binding constraint to the review prompt so it is not re-litigated.
- MAJOR Task 3b ordering — ADOPTED. Correct: 2 gens cannot distinguish recency from both name-sort directions. Switched to a 3-generation fixture whose recency order is NON-MONOTONIC in sid: gen-aaa=middle msg (2026-03), gen-bbb=newest msg (2026-06), gen-ccc=oldest msg (2026-01); assert `index("gen-bbb") < index("gen-aaa") < index("gen-ccc")`. Recency sort -> [bbb,aaa,ccc] PASS; ascending-sid -> [aaa,bbb,ccc] FAIL; descending-sid -> [ccc,bbb,aaa] FAIL. Distinguishes recency from BOTH name sorters.
- MINOR sid validity — ADOPTED as a clarifying note. Verified `is_valid_session_id` = `_SESSION_ID_RE = [A-Za-z0-9._-]+` fullmatch (comms_session_registry.py:53) + not "."/".." + no "/"/"\\". The fixture sids (`gen-aaa`, `gen-bbb`, `gen-ccc`, `gen-ok`) are all valid by that regex; noted the conformance + the bad-name skip fixture (`"bad name"`, a space) is correctly REJECTED by the regex.

## Round 5 (-p review-fast -c model_reasoning_effort=high; over the R4-revised plan + grounded prompt)
### Codex response (verbatim)
- **MINOR | Section 2, Task 1b**: The DryRun behavioral test is hard-skipped whenever either `powershell` or `claude` is missing, so on common CI/worker setups it never participates in the red->green loop -- weak distinguisher even though Task 1a covers the static edit. **Fix:** keep Task 1b as a manual smoke test, or mock the preflight/subprocess boundary.
- **MINOR | Section 1.3, Task 3b**: ordering uses `max(m.filename)` as the recency signal -- only correct if every mail file keeps the canonical timestamped filename shape; a renamed/malformed file can silently misorder the bus. **Fix:** state the filename-stamp invariant explicitly, or sort on an explicit timestamp field.

VERDICT: NO_NEW_CRITICAL_MAJOR  (CONVERGED -- zero new critical/major)
tokens used: 34,634

### Adjudication (Round 5) -- CONVERGED
The enumeration MAJOR was NOT re-raised (the binding-constraint note grounded the reviewer). Verdict NO_NEW_CRITICAL_MAJOR = convergence per recipe. Two residual MINORs:
- MINOR Task 1b (skip-gating) — NO PLAN CHANGE NEEDED; already adjudicated in R2. The DISTINGUISHING burden is on the always-runs static-content Test 1a; Test 1b is a behavioral net that runs on the OPERATOR'S box, which IS where the merged-head no-false-green re-run executes (both binaries present), so it provides real coverage where it runs. The plan already permits dropping a fragile assert while keeping the load-bearing asserts, and frames 1a as the distinguisher. Non-blocking; left as-is.
- MINOR Task 3b (filename-stamp recency invariant) — ADOPTED as a clarifying note. The `max(m.filename)` recency key relies on the canonical role_mail filename stamp `<yyyymmddTHHMMSSZ>-...`; this is the SAME convention the EXISTING `_history_ctx` already uses (`msgs.sort(key=lambda m: m.filename, reverse=True)`), so the approach is consistent with the live codebase. A malformed/renamed filename degrades to its lexical position (non-fatal; read-only display). Added the invariant note + the consistency citation to §1.3 / Test 3b. A post-convergence doc clarification of an accepted approach (no behavior change) -> does not reopen the gate (recipe: do not pad after convergence).

FINAL VERDICT: NO_NEW_CRITICAL_MAJOR (Round 5). Rounds run: R1 (effort=low, 0 findings -> re-run at high), R2 (1 MAJOR + 1 MINOR), R3 (2 MAJOR), R4 (2 MAJOR + 1 MINOR), R5 (CONVERGED, 2 MINOR residual/adjudicated).

---

# EXECUTING REVIEW (G6 Arc B implementation)

Base = plan commit 395de0d9. Three task commits: 24580e89 (T1 launcher), d480ab03 (T2 LAUNCH_ROLES), c2b7ffae (T3 bus). Full fast suite GREEN off the final head (8867 passed, 5 skipped); ruff swing/ clean.

## review-strong R1 (gpt-5.5 / effort=high, -p review-strong, repo-context bundled: diff + full comms_ui.py + start_directors.ps1 + comms_session_registry.py)

Carried the BINDING-CONSTRAINT note (disk-enumeration by design; do NOT re-litigate registry enumeration).

### Codex response (verbatim)
NO_NEW_CRITICAL_MAJOR (tokens used 32,274)

### Adjudication
CONVERGED round 1. The reviewer respected the binding-constraint note — the disk-enumeration design was NOT re-litigated (the R3/R4 writing-plans re-litigation was pre-empted). review-strong is the iterative binding gate; converged.

## codex-auto-review (complementary second eye; repo-access, cwd=worktree, -s read-only, effort=high)

SUBSTITUTION NOTE: native `codex exec review --base 395de0d9` FAILED — the worktree `.git` is a gitdir-FILE pointing at a Windows path WSL git cannot resolve ("is not a git repository"). Per recipe §3 I substituted the documented `codex exec @ effort=high` repo-access form (cwd at the worktree so it greps surrounding code itself), framed as the complementary second eye.

### Codex response (verbatim)
**Findings**

MAJOR: Fresh orchestrator launch points at a stale bootstrap that denies the new bus contract. start_directors.ps1:91 now maps `orchestrator` to `orchestrator_bootstrap.md`, but orchestrator_bootstrap.md:1 still says the session is "NOT launched by the director cold-start launcher," stays in VS Code, and that draining queued director mail is impossible because "there is no orchestrator inbox in V1" (line 36). That makes `/directors/launch` look successful while the launched orchestrator follows obsolete instructions and ignores the new per-generation inbox that the UI bus is surfacing.

MAJOR: The reused resume prompt gives orchestrator an invalid drain command. start_directors.ps1:109 formats every role as `python scripts/role_mail.py read --role {0} --all`, and Start-Resume (start_directors.ps1:270) now applies that to `orchestrator`. But role_mail requires `--session <session_id>` for orchestrator reads (role_mail.py:294), so resumed orchestrator sessions are instructed to run a command that fails before acking anything.

NEW_MAJOR_FINDINGS: stale orchestrator bootstrap breaks fresh launched-bus effectiveness; orchestrator resume prompt omits required `--session` and cannot drain inbox. (tokens used 101,748)

### Adjudication (verified against live code)
BOTH findings are REAL and VERIFIED on disk:
- F1: orchestrator_bootstrap.md:3-5 ("you are NOT launched by the director cold-start launcher; orchestrators stay in VS Code under manual operator relay") + :36-38 ("Drain anything the directors have queued for you is NOT possible -- there is no orchestrator inbox in V1"). This contradicts the Arc B capability (the launcher CAN now launch the orchestrator; there IS now a per-gen inbox the bus surfaces).
- F2: role_mail.py:295-297 raises MailError "reading an orchestrator inbox requires --session <session_id>" when sid is falsy; the role-generic $ResumePrompt (start_directors.ps1:109) emits `read --role orchestrator --all` with NO --session -> fails.

DISPOSITION: REAL but OUT-OF-ARC-B-SCOPE -> FLAGGED-NOT-FIXED (do NOT fix inline; the locked + CHARC-cleared plan deliberately scopes these out).
- F1 (bootstrap CONTENT) is not in the plan's 3-edit delta; the brief §1 + plan §0/§1.1 treat orchestrator_bootstrap.md as a GIVEN existing file (also the served "Copy orchestrator spin-up" button text). Rewriting its content is a redesign the dispatch forbids ("do not redesign"). It also reveals the brief premise ("the bootstrap already exists [and is suitable]") does NOT match live code -> recipe §5 STOP-and-flag.
- F2's fix would either (a) change role_mail (a comms-core change — Arc-A-DONE, explicitly OUT OF SCOPE, "Arc B only READS"), or (b) make $ResumePrompt orchestrator-specific — but the plan locks "Reuse ... Start-Resume / the resume prompt UNCHANGED," AND the launcher only has session_NAME (.sessions.json), not the session_ID that --session needs (the registry keys on session_id from the hook). This is a genuine DESIGN gap, not a 3-edit data change; fixing it crosses the boundary.

Both are flagged UP to the orchestrator for CHARC routing (likely a fast follow-up: amend the bootstrap text to the launched-with-per-gen-inbox world + decide the orchestrator resume-drain story). The SHIPPED launch+bus mechanics (the locked 3-part delta) are correct and faithfully implemented; these are stale-INSTRUCTIONS effectiveness gaps in surrounding un-changed code.

review-strong (binding iterative gate) = NO_NEW_CRITICAL_MAJOR converged. codex-auto-review majors = adjudicated + CITED as out-of-scope (boundary-crossing) + flagged-not-fixed per recipe §3 ("a B major is adjudicated + resolved-or-cited before merge").

---

## Task 4 — role-aware launch effort + role-aware session name

Base for the diff = `6c96560b` (HEAD after the bootstrap addendum). Task-4 commit = `af62af43`. Full fast suite GREEN off the final head (8871 passed, 5 skipped); ruff swing/ clean. Two fixes: Issue 1 role-aware `--effort` ($RoleEffort map + Get-LaunchArgs + preflight loop over distinct levels); Issue 2 role-aware New-SessionName (orchestrator -> `orchestrator-<stamp>`, directors unchanged).

### review-strong R1 (gpt-5.5 / effort=high, -p review-strong profile resolved; stdin bundle = prompt + Task-4 diff)

#### Codex response (verbatim)
No new critical or major defects found in the Task 4 diff.

Checked against the binding constraints:
- PowerShell 5.1 syntax is valid: no `&&`, ternary, or null-coalescing.
- Console/output strings remain ASCII-only.
- `$env:SWING_ROLE` is still set inside `Build-LaunchCommand`; the wt/new-tab spawn pattern is not changed.
- `Get-LaunchArgs` assembles role-aware effort without changing shared model/permission flags.
- Preflight now checks each distinct `$RoleEffort` value.
- `New-SessionName` preserves director names and gives orchestrator `orchestrator-<stamp>`.

Verdict: `NO_NEW_CRITICAL_MAJOR` (tokens used 13,320)

#### Adjudication
CONVERGED round 1. review-strong is the iterative binding gate; zero findings.

### codex-auto-review (complementary second eye; matched-high effort)

SUBSTITUTION NOTE: native `codex exec review --commit af62af43 -c model_reasoning_effort=high` FAILED to resolve git — the worktree `.git` is a gitdir-FILE pointing at a Windows path WSL git cannot resolve (`fatal: not a git repository: .../C:/Users/rwsmy/swing-trading/.git/worktrees/...`). Per recipe §3 I ran the documented `codex exec @ effort=high` substitution with the FULL post-change `start_directors.ps1` bundled via stdin (so the second eye reads the surrounding reference graph: preflight, Start-Fresh/Resume, New-SessionName, Build-LaunchCommand, Get-LaunchArgs, main) — the repo-access-equivalent for a non-resolvable worktree gitdir.

#### Codex response (verbatim)
I found no new critical or major Task-4 issues.

The changed call graph is consistent: `Start-Fresh` and `Start-Resume` now both use `(Get-LaunchArgs $role)`, and there is no remaining runtime `$LaunchArgs` dependency in the supplied script. `$RoleEffort` is defined before both `Get-LaunchArgs` and `Invoke-Preflight`, and PowerShell function lookup can resolve that script-scope variable.

The unknown-role `$RoleEffort[$role]` concern is not a Task-4 major in the normal entry path: `Role` is constrained by `ValidateSet`, `both` expands only to `charc`/`rd`, and `orchestrator` is explicit. A direct dot-sourced/internal call with an unknown role could yield a null effort, but the surrounding script already assumes known roles for bootstrap/title lookup too, so this is not a newly exposed supported-path break.

The preflight distinct enumeration looks PS 5.1-compatible: `$RoleEffort.Values | Sort-Object -Unique` is valid, and the values are simple regex-safe literals (`max`, `xhigh`). No ASCII or PS 5.1 syntax violations stood out. The `wt new-tab` / spawned-shell `$env:SWING_ROLE='role'` pattern is unchanged in `Build-LaunchCommand` and `Start-RoleWindow`.

Verdict: NO_NEW_CRITICAL_MAJOR (tokens used 16,889)

#### Adjudication (verified against live code)
NO findings to resolve. The reviewer's one noted edge (unknown-role -> `$null` effort) is NOT a Task-4 defect and NOT newly introduced: `[ValidateSet('charc','rd','orchestrator','both')]` constrains `-Role`; `both` expands to charc/rd only; and the surrounding script ALREADY indexes `$BootstrapFiles[$role]`/`$RoleTitles[$role]` on the same known-role assumption (a missing bootstrap throws first). It is consistent with pre-existing behavior, not a new exposed vector — out-of-scope per the same known-role contract. Both passes converged; nothing to fix.
