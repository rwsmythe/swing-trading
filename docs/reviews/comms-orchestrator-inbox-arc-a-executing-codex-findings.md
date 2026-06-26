# Codex review findings — G6 Arc A plan (writing-plans, review-fast)

Profile: `-p review-fast` (present at `~/.codex/review-fast.config.toml`); codex-cli 0.135.0; `-s read-only --skip-git-repo-check`; plan piped via stdin.

---

## Round 1

### Codex response (verbatim)

CRITICAL
- Explicit `orchestrator:<sid>` delivery is not actually bootstrapped. In §2.5 and Task 4c, the plan promises delivery to a pruned or never-registered generation, but nothing creates `comms/orchestrator/<sid>/{inbox,read}` on that send path. `SessionStart` only creates the directories when the orchestrator session itself starts, and `_ensure_tree()` explicitly does not touch orchestrator. A never-registered `orchestrator:<sid>` target will therefore fail at temp-file creation time, which contradicts the stated acceptance criterion. This needs an explicit mkdir/bootstrap step on the explicit-`sid` path, or the plan should narrow 4c to "previously registered but pruned" only.

MAJOR
- `role_mail` has no stated fallback for explicit per-generation inbox creation on direct send, so the "registry-independent delivery" contract is underspecified. Even if 4c is narrowed to pruned-but-known sessions, the plan still relies on directory state surviving pruning and does not say whether role_mail or the registry owns re-creating those directories after deletion or on first use. That ambiguity will produce brittle implementation choices and likely a test that passes only because of incidental prior state. The plan should define one owner for inbox bootstrap on explicit `orchestrator:<sid>` sends and have the tests enforce it.

MINOR
- `newest_live` selection semantics are slightly under-specified when `started_ts` is malformed on all live entries. The plan says malformed `started_ts` is "deprioritized," but does not define the all-bad case. That will matter for deterministic tie-breaking and for `bare --to orchestrator` error behavior.
- The registry "local copy" of atomic write logic is called out as a flagged adjudication point, but the plan does not require a test that fails if it accidentally regresses to a cross-volume-unsafe implementation. A narrow temp-dir test on Windows would strengthen the guarantee.
- Task 4g's grep-clean test can miss a second resolver copy if it is imported under another name or re-exported through a helper. It proves absence of obvious duplicate function definitions, but not absence of duplicate logic. The plan should prefer behavioral coverage for "single source" over source-text string checks.

(Codex also appended a trailing `NO_NEW_CRITICAL_MAJOR` line, but since it raised a CRITICAL + MAJOR in the same response, this round is treated as NOT converged — fixes applied, re-run round 2.)

### Adjudication (plan author)

- **CRITICAL (delivery bootstrap) — VALID-as-plan-gap, NOT a design flaw; FIXED in the plan.** Verified on disk: `scripts/role_mail.py:_write_temp:97` already does `final.parent.mkdir(parents=True, exist_ok=True)` BEFORE `mkstemp`. So the explicit-`:<sid>` send path DOES create `comms/orchestrator/<sid>/inbox` on first send (the same mechanism that bootstraps any singular inbox today). Codex lacked the `_write_temp` body (the prompt described it as "same-dir mkstemp + os.replace" without the mkdir). No design change — the delivery works; the PLAN was missing the fact. FIX: §2.5 + Task 4c now state the `_write_temp`-mkdir bootstrap explicitly, and 4c tests a NEVER-registered sid (no prior dir state).
- **MAJOR (ownership underspecified) — FIXED.** Single ownership now stated: `_write_temp`'s `final.parent.mkdir(parents=True)` owns inbox-dir bootstrap on the SEND path (idempotent); `ensure_per_generation_inbox` owns it on the REGISTER path (idempotent); both create the identical `comms/orchestrator/<sid>/inbox`. Task 4c asserts delivery against a never-registered sid (no incidental prior state), enforcing the send-path owner.
- **MINOR (newest_live all-malformed) — FIXED.** `newest_live` sort key extended with a deterministic final tiebreaker on `session_id` (lexical), so the all-malformed-`started_ts` case (and any tie) resolves deterministically.
- **MINOR (atomic-write regression test) — FIXED.** Task 1 now requires a structural test asserting the registry's `_atomic_write_text` stages its temp in the TARGET's own directory (no temp outside the target dir) — fails if it regresses to a cross-volume `gettempdir()` variant.
- **MINOR (grep-clean can miss renamed/re-exported logic) — FIXED.** Task 4g augmented: keep the cheap source-text grep AND add a BEHAVIORAL assertion — patch the loaded registry module's `newest_live` and assert role_mail's bare-orchestrator resolution reflects the patched value (proving delegation, not a private copy).

---

## Round 2 (repo-access; model gpt-5.4-mini)

### Codex response (verbatim)

MAJOR
- The plan violates its own "single-source guarantee" for session inbox resolution. Section 2.1 makes the registry the owner of `per_generation_inbox` / `ensure_per_generation_inbox`, but section 2.5 then adds separate role-mail resolvers (`_role_inbox_dir`, `_role_read_dir`, `_inbox_for_target`) that independently reconstruct `comms/orchestrator/<sid>/{inbox,read}`. That is a second resolver copy, exactly the drift risk the brief says to avoid. If one side changes, send/read can diverge silently. This is an internal inconsistency in the plan, not just an implementation detail.

MAJOR
- Section 2.5 under-specifies the orchestrator read path in a way that will likely break the first implementation pass. The plan says `cmd_read` should accept `--session` and that `ack_message` gains `session_id`, but it never explicitly says `cmd_read` must pass that session through when it calls `ack_message`. As written, a literal implementation can still end up calling `ack_message(root, args.role, path.name)` and fail for every orchestrator read even when `--session` is present. This is a concrete execution blocker.

MINOR
- The replacement test set in section 7 leans too hard on structural grep for "no `def newest_live` / no `def read_entry` / no `def is_valid_session_id`." That is brittle and can be bypassed by helper indirection or re-exported names. The behavioral stub-based delegation test is the one that actually proves single-source use; the structural assertions add noise and false-failure risk without much extra protection.

MINOR
- Section 2.5 and section 4 both describe session-id validation at multiple sites, but the plan never resolves whether `role_mail` should treat a missing/broken registry import as a hard failure for *all* orchestrator-related commands or only for the specific `orchestrator` recipient paths. The text says "fail loud," but the command-level blast radius is still underspecified.

### Adjudication (plan author)

- **MAJOR (second resolver copy for per-gen paths) — VALID; FIXED.** The registry is now the SINGLE owner of the per-gen path shape `comms/orchestrator/<sid>/{inbox,read}`: added `per_generation_read(root, sid)` (mirror of `per_generation_inbox`) to the registry; role_mail's orchestrator branches in `_inbox_for_target` / `_role_inbox_dir` / `_role_read_dir` now DELEGATE to `_registry().per_generation_inbox` / `_registry().per_generation_read` rather than rebuilding the path. role_mail still owns only the SINGULAR-role paths (`root/role/{inbox,read}`), which the registry does not manage.
- **MAJOR (cmd_read must thread --session to ack_message) — VALID; FIXED.** §2.5 now explicitly: `cmd_read` calls `ack_message(root, args.role, path.name, session_id=args.session)`; `cmd_list`/`cmd_peek`/`cmd_read` resolve the inbox via `_role_inbox_dir(root, role, args.session)`. Task 4f asserts the full orchestrator read→ack round-trip moves into `comms/orchestrator/<sid>/read/`.
- **MINOR (grep brittleness) — ACCEPTED (rebalanced).** Task 4g: the BEHAVIORAL stub-delegation test is now the PRIMARY single-source proof; the structural grep is narrowed to the load-bearing defs (`def newest_live`, `STALE_SECONDS =`) as a cheap backstop (the brief guard #4 mandates a grep-clean check; kept minimal to limit false-failure noise).
- **MINOR (registry-import blast radius) — ACCEPTED; CLARIFIED.** §2.5 now states: `_registry()` raises a hard MailError ONLY on an orchestrator-path operation that needs it (bare newest-live resolution; `:<sid>` validation; orchestrator read/list/peek/ack validation). SINGULAR-role operations NEVER call `_registry()`, so a broken/missing registry module can never break director/operator mail (bounded blast radius).

---

## Round 3 (repo-access; model gpt-5.4-mini)

### Codex response (verbatim)

MAJOR
- Section 2.1, 2.2, 2.5, and Task 4c/4f: the plan supports direct delivery to a never-registered or pruned orchestrator session (`--to orchestrator:<sid>`), but only `session-start` creates `comms/orchestrator/<sid>/read` via `ensure_per_generation_inbox`. That means the first direct message to a fresh session can land in `inbox/`, yet `read`/`ack` for that same session may fail because the read directory was never bootstrapped. The plan needs an explicit bootstrap rule for the read side on send or consume, otherwise the new explicit-target path is not actually round-trippable.
- send path currently bootstraps only `inbox/`; session-start bootstraps `inbox/` + `read/`; orchestrator read/list/peek/ack are specified to work for sessions that may never have run session-start. Fix by making the orchestrator read path create `read/` lazily, or guaranteeing `read/` creation whenever `inbox/` is created.

### Adjudication (plan author)

- **MAJOR (read-dir bootstrap for never-registered/pruned sessions) — VALID-as-plan-gap, NOT a design flaw; FIXED.** Verified on disk: `scripts/role_mail.py:ack_message:370` already does `read_dir.mkdir(parents=True, exist_ok=True)` BEFORE the rename — so the `read/` dir is bootstrapped LAZILY at ack time. The plan was missing the explicit statement. FIX: §2.5 `ack_message` now states the orchestrator branch resolves the read dir via `_registry().per_generation_read(root, sid)` and preserves the existing `read_dir.mkdir(parents=True, exist_ok=True)` lazy bootstrap — so the explicit-`:<sid>` send → list/peek → read+ack round-trip is fully round-trippable for a session that NEVER ran `session-start`. Task 4c now asserts the FULL round-trip (send to a never-registered sid over an empty registry → `read --session <sid> --all` moves the file into `comms/orchestrator/<sid>/read/`), proving both `inbox/` (send-path `_write_temp` mkdir) and `read/` (ack-path mkdir) bootstrap lazily with no `session-start`.

---

## Round 4 (repo-access; model gpt-5.4-mini)

### Codex response (verbatim)

CRITICAL — None.

MAJOR
- §2.1, §2.5, §7 Task 1: the registry write path is missing an explicit bootstrap for `comms/sessions/` before the first atomic write. `mkstemp(dir=path.parent)` will fail on a fresh tree if `sessions/` does not already exist, which means first session-start, heartbeat refresh, and the fresh-tree tests can all fail before any logic is exercised. The plan needs a concrete `mkdir(parents=True, exist_ok=True)` step for the registry root or an equivalent guarantee in `write_entry`/`touch_last_seen`.
- §0 IN, §2.1, §2.5: the plan is internally inconsistent about the single owner of the per-generation path shape. Early scope lists `per_generation_inbox` and `ensure_per_generation_inbox`, but the implementation later relies on a separate `per_generation_read` helper as well. The plan should state the full registry-owned path API up front and use it consistently.

MINOR
- §2.2, §2.4, §7 Task 2: the heartbeat seam is gate-free, but still depends on `SWING_ROLE` being set for an orchestrator session. State how an orchestrator session is identified in the live environment, or add a test that proves the env carries `SWING_ROLE=orchestrator`.
- §2.5, §7 Task 4f: whether `peek`/`list` require the same session validation path as `read` is implied, not pinned down.
- §7 Task 4g: the structural grep backstop is brittle; if kept, label it a sanity check only, not a required discriminator.

(Note: L1 ordering correctly preserved in §2.5 by parsing recipients before the decision_request lock.)

### Adjudication (plan author)

- **MAJOR (fresh-tree `sessions/` bootstrap) — VALID-as-plan-gap; FIXED.** coa-chess's `_atomic_write_text` does `path.parent.mkdir(parents=True, exist_ok=True)` before `mkstemp` (and `write_entry` mkdirs `sessions/`) — the plan's §2.1 omitted the explicit parent-mkdir. FIX: §2.1 `_atomic_write_text` now explicitly does `path.parent.mkdir(parents=True, exist_ok=True)` before `mkstemp` (mirroring role_mail `_write_temp:97`), so `comms/sessions/` (and any per-gen dir) bootstraps on first write; Task 1 sub-cycle 3 runs over a FRESH tree (no pre-made `sessions/`).
- **MAJOR (path-API consistency up front) — VALID; FIXED.** §0 IN item 1 now lists the FULL registry-owned path API including `per_generation_read` (and `ensure_per_generation_inbox`).
- **MINOR (orchestrator env identity) — ACCEPTED; SCOPED.** §2.4/Task 2 now state: the heartbeat refreshes WHEN `SWING_ROLE=orchestrator` is in the session env; HOW a live orchestrator session comes to carry that env var is the Arc-B launcher/bootstrap concern (deferred — same mechanism directors use today). Arc A tests the heartbeat with a synthetic `env={"SWING_ROLE":"orchestrator"}`; the §5.10 operator live-witness confirms the real env.
- **MINOR (peek/list session validation) — ACCEPTED; PINNED.** §2.5: `cmd_list`/`cmd_peek` for orchestrator REQUIRE `--session` and resolve via the SAME `_role_inbox_dir(root, role, args.session)` validation path as `read` (they are observational — no ack — but the session-id resolution + validation is identical).
- **MINOR (grep label) — ACCEPTED.** Task 4g: the structural grep is now explicitly labeled a non-blocking SANITY CHECK; the behavioral delegation test is the binding discriminator.

---

## Round 5 (repo-access; model gpt-5.4-mini) — CONVERGED

### Codex response (verbatim)

CRITICAL — None. MAJOR — None.

MINOR
- §2.2/Task 2: `session_id` env fallback variable is never named for swing — the implementer cannot wire/test the fallback deterministically without an explicit contract.
- Task 1.9 atomic-write test is brittle: "no leftover `.tmp` outside `target.parent`" keys on `mkstemp` naming rather than the safety property; a compliant impl could stage temps in the right dir without a `.tmp` prefix.
- §2.1/§5 `newest_live` lexicographic-greatest-`session_id` tiebreak is deterministic but arbitrary; call it out as a deliberate tie policy so it is not accidentally changed later (invalidating the test oracle).
- Task 4g structural grep is weaker than the stated policy and could miss a renamed-helper copy; the behavioral stub is the real discriminator — de-emphasize the grep.

### Verdict line: `NO_NEW_CRITICAL_MAJOR` (genuine — the prior rounds' trailing line was the prompt-instruction echo; this is the real convergence).

### Adjudication (plan author) — advisory MINOR polish applied post-convergence (no design change; non-blocking)

- **MINOR (env fallback var) — APPLIED.** §2.2/Task 2 now name the concrete degraded fallback env var (`CLAUDE_SESSION_ID` / coa-chess's `CLAUDE_CODE_SESSION_ID`) as a candidate, with an explicit instruction for the executing implementer to VERIFY the exact var against the live hook payload; the PRIMARY source stays `payload["session_id"]`.
- **MINOR (atomic-test brittleness) — APPLIED.** Task 1.9 reworded to assert the SAFETY PROPERTY (temp staged in `target.parent`; after a successful write the only artifact in the tree is `target` — no stray leftover ANYWHERE), not the `.tmp` suffix.
- **MINOR (tie policy) — APPLIED.** §2.1 `newest_live` now labels the trailing-`session_id` tiebreak a DELIBERATE, test-oracle-pinned tie policy (do not change without updating the test).
- **MINOR (grep de-emphasis) — already handled** in the R4 fix (Task 4g labels the grep a non-blocking sanity check; the behavioral stub is the binding discriminator). No further change.

**Convergence reached at Round 5 (zero new critical/major). The remaining MINORs were applied as advisory polish; they introduce no behavior change, so no additional Codex round is required.**

# EXECUTING REVIEW

## Round 1 — review-strong (gpt-5.5, reasoning effort=high; repo bundle: diff + full source of the 3 changed scripts)

### Codex response (verbatim, findings + verdict)
**Findings** — No new critical/major issues found.

**MINOR** `scripts/role_mail.py:548` — `ack_message()` uses `src.rename(dest)`; could fail cross-device if `root` is mapped through a junction/symlink/split storage (unlike the delivery path's explicit same-dir staging). Fix: use `os.replace`, or document ack is same-volume-only. "Lower risk because inbox/read are siblings under the same session root."

**MINOR** `scripts/comms_session_registry.py:239,266` — future-dated `last_seen`/`started_ts` accepted as live/newest; a corrupted/manually-edited entry with a future timestamp could win bare `--to orchestrator` longer than intended. Fix: clock-skew tolerance in `_age_seconds`; cap future `started_ts` in `_started_sort_key`.

"The core locks look satisfied: L1 fires before orchestrator inbox resolution for human senders, explicit `orchestrator:<sid>` remains registry-independent, path construction delegates through the registry validators, bare orchestrator resolution delegates to `newest_live`, and delivery staging happens only after all concrete inboxes are resolved."

### Verdict: NO_NEW_CRITICAL_MAJOR

### My per-finding adjudication
1. MINOR ack rename cross-device — **PRE-EXISTING, not introduced.** The original `ack_message` already used `src.rename(dest)` (role_mail.py prior line 372). inbox/read are siblings under the SAME session root (`comms/orchestrator/<sid>/{inbox,read}` or `comms/<role>/{inbox,read}`), so the rename is always same-dir / same-volume — exactly the case where `rename` is safe. Codex itself rates it lower-risk for this reason. Out-of-scope for Arc A (pre-existing behavior of the unchanged ack core; the brief lock §6 says reuse swing's existing helper). NOT FIXED — flagged.
2. MINOR future-dated timestamps — **writer-prevented / degrade-gracefully.** The ONLY writer of these fields is the hook, which always stamps `now.isoformat()`. A future-dated value is reachable ONLY by manual file corruption (the same trust boundary as any hand-edit of a `comms/sessions/*.json`). The schema-boundary corollary (recipe §3 adjudication): a value the write boundary prevents is non-blocking V1 for a reader; the registry already degrades gracefully (a malformed entry is skipped/pruned). Adding speculative clock-skew capping is unrequested hardening with its own regression surface. NOT FIXED — flagged as out-of-scope V1.

Both findings MINOR; neither blocks. review-strong converged round 1.

## codex-auto-review (recovery implementer; the missing CHARC-required complementary second eye)

**Transport / substitution note.** The native `codex exec review --base 6a2405e6 -c model_reasoning_effort=high` was attempted FIRST (cwd = the worktree, via WSL). It HUNG producing no output — the known worktree-`.git`-is-a-file constraint (WSL git cannot resolve the gitdir pointer). Substituted the recipe's stdin-bundle form WITH repo access: `codex exec -c model_reasoning_effort=high -s read-only --skip-git-repo-check -` run from cwd `/mnt/c/.../.worktrees/g6a-orchestrator-inbox`, stdin = review prompt + the full `6a2405e6..HEAD` diff (`.codex-autoreview-diff.txt`) + the FULL post-change source of all 3 changed scripts (`comms_session_registry.py`, `comms_session_hook.py`, `role_mail.py`) so the reviewer reads beyond the diff (the registry<->role_mail seam, the L1 matrix, the path-safety, the atomic-write twin). Codex ALSO had live read-only repo access from that cwd and exercised it — it ran `nl .claude/settings.json`, `python3 -m json.tool` (validated the wiring JSON), and attempted a targeted pytest (no pytest in the WSL env). Model: **gpt-5.5, reasoning effort high**. Full raw transcript: `.codex-autoreview-r1.txt`.

### Codex response (verbatim — findings + verdict)

> **MINOR** [`scripts/comms_session_registry.py:165`]: `read_entry()` returns any JSON object without enforcing embedded `session_id == path.stem`. `touch_last_seen()` then writes that object back unchanged at [line 214]. This does not create a path traversal or bare-orchestrator misroute because `newest_live()` goes through `read_entries()`, which does enforce identity. It is still a contract mismatch: a manually corrupted `sessions/g1.json` with embedded `session_id: "g2"` remains corrupted across heartbeat instead of being treated as missing/rebuilt/pruned.
>
> No critical/major issues found. L1 is checked before inbox resolution, explicit `orchestrator:<sid>` delivery is registry-independent, bare `orchestrator` has a clear no-live error, path construction delegates to the registry, and the hook remains exit-0.
>
> Verification: `.claude/settings.json` parses with `python3 -m json.tool`. Targeted pytest was not run because this shell has no `pytest` installed.

### Verdict: NO_NEW_CRITICAL_MAJOR

### My per-finding adjudication

1. **MINOR (read_entry / touch_last_seen do not enforce embedded `session_id == path.stem`) — WRITER-PREVENTED + already-degrade-graceful; NOT FIXED, out-of-scope V1 (recipe section-3 schema/writer-boundary corollary).** Verified on disk:
   - **No path traversal, no misroute (Codex concurs).** `touch_last_seen` reads via `read_entry(root, session_id)` and writes via `entry_path(root, session_id)` (`comms_session_registry.py:214,217`) — BOTH keyed on the validated `session_id` STEM passed by the hook (the hook only calls in after `is_valid_session_id`), NEVER on the embedded JSON field. So the write target filename is always path-safe. The security-relevant readers (`read_entries` -> `live_entries` -> `newest_live`) DO enforce the filename==embedded-id identity invariant (`read_entries:457-459`) and SKIP a mismatched file — so a crafted/corrupt embedded id can never mis-route a bare `--to orchestrator`.
   - **Writer-prevented.** The ONLY writer of `sessions/<sid>.json` is `write_entry`, which sets `payload["session_id"] = session_id` == the `entry_path` stem. An embedded-id != filename-stem state is reachable ONLY by a manual hand-edit of the JSON — the same trust boundary as any hand-edit of `comms/`. Per recipe section-3: a read-only-consumer finding premised SOLELY on a value the write boundary verifiably prevents is non-blocking V1, and the cited general degrade-gracefully path (the `read_entries` identity skip) is exactly the required defense (NOT a per-case branch).
   - The only residual is a corruption-RECOVERY nicety (a hand-corrupted mismatched file persists across heartbeat rather than being self-healed); the heartbeat still keys its own write on the safe stem, the security path still skips the bad file, and a `prune_stale` cycle removes it once `last_seen` ages out. Adding embedded-id re-validation to `read_entry`/`touch_last_seen` is unrequested hardening with its own regression surface (it would change the heartbeat self-heal contract). NOT FIXED — flagged as out-of-scope V1.

DISJOINT-but-no-new: codex-auto-review raised ZERO new critical/major (its single MINOR is a different blind-spot from review-strong's two MINORs, consistent with the 18-H.4 "complementary second eye" finding). No code change required; converged.
