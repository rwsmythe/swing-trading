# B-16 Codex review-strong findings transcript

Tier: review-strong (`-p review-strong` resolved at `~/.codex/review-strong.config.toml`; CODEX_HOME unset → default `~/.codex/`). Bundle = prompt + full diff (`-U8`) + full post-change `user_prompt_submit.py` + `session_start.py` (repo-access-equivalent: the registry-unchanged + store-isolation claims are verifiable against the surrounding un-changed code). Codex told NOT to run git; `--skip-git-repo-check`; `-s read-only`; stdin.

## Round 1

### Codex response (verbatim)

> **Major Finding**
>
> - `.claude/hooks/user_prompt_submit.py:197`: the unsafe-session warning is not byte-preserved for the degraded fallback path. If the hook payload lacks `session_id` but `CLAUDE_CODE_SESSION_ID` is present and unsafe, pre-B-16 warned with the fallback value:
>
>   ```text
>   refusing unsafe session_id '<fallback>'; not registering.
>   ```
>
>   The new code warns with `raw_session_id`, which is `None` or `""` in this path:
>
>   ```python
>   f"session_id {raw_session_id!r}; not registering."
>   ```
>
>   Side effects remain safe, but this violates the binding requirement that the orchestrator registry block's observable stderr behavior be byte-preserved. The fix is to retain the actual candidate that failed validation, e.g. track `unsafe_session_id = session_id` before nulling it and print that inside the orchestrator block.
>
> No critical findings.

### Adjudication

- **R1 Major (ACCEPTED + FIXED, commit 04df887).** Verified against the pre-fix code: the original orchestrator block resolved `session_id` (incl. the `_degraded_session_id` fallback) and then printed `refusing unsafe session_id {session_id!r}` with that RESOLVED value. My restructure printed `raw_session_id` (= `payload.get("session_id")`), which is `None` on the degraded-fallback-unsafe path → a real stderr divergence (`None` vs the fallback value). This violates the byte-preserve-the-orchestrator-stderr constraint. Fix: capture `unsafe_session_id = session_id if unsafe else None` BEFORE nulling, print that in the orchestrator block. Added `test_orch_degraded_fallback_unsafe_id_warns_with_the_fallback_value` pinning the fallback value (`'../../evil'`, not `None`) — distinguishes the bug (pre-fix prints `None`). Full suite 224 OK.
- No critical findings.

## Round 2

### Codex response (verbatim)

> Findings:
>
> **Minor: `read_session_role` contract drift**
> [session_start.py]: `read_session_role()` says invalid recovered role strings return `None`, but the implementation returns any non-empty string and leaves validation to `handle_user_prompt_submit()` via `recovered in COMMS_ROLES`. That matches the binding design, but the helper docstring and comments are inaccurate. Not critical/major because the acceptance gate is present at the hook boundary.
>
> **Minor: role-store write accepts unknown env roles**
> [user_prompt_submit.py]: when `HARNESS_ROLE` is set, the hook writes it to `comms/roles/<session_id>` without checking `env[ROLE_ENV] in COMMS_ROLES`. This does not cause acceptance of garbage on resume because recovery validates against `COMMS_ROLES`, and env role already controlled behavior pre-change. It can leave stale junk records, but not a registry or path-safety issue.
>
> No critical or major findings. The registry remains orchestrator-only, CHARC is not registered, unsafe session IDs are nulled before path use, env role wins over recovery, and the prompt-blocking guarantee is preserved through `main()`'s broad guard.
>
> NO_NEW_CRITICAL_MAJOR

### Adjudication

- **R2 Minor #1 (read_session_role contract drift) — ACCEPTED + FIXED (commit db644b4).** The docstring/comment claimed an unrecognized role string returns None, but the helper returns the non-empty string as-is and the known-role belt lives at the hook (`recovered in COMMS_ROLES`). Corrected the docstring + the section banner to state the helper returns the string and the validation belt is at the hook boundary (decoupling the store layer from COMMS_ROLES, per the plan's settled design). Docs-only; suite still 224 OK.
- **R2 Minor #2 (role-store write accepts unknown env roles) — ACCEPTED-AS-V1, NO CHANGE.** Codex itself classified it non-major/non-critical and "not a registry or path-safety issue." A garbage env role cannot become an active role on resume (the recovery belt rejects it). Pre-change, an unknown `HARNESS_ROLE` already controlled hook behavior identically (an unknown role just falls through every gate), so writing it changes nothing observable except a harmless stale record. Restricting the write to known roles would be an unrequested behavior change; the V1 store is explicitly NOT pruned (plan §0.1) and a stale record is harmless. Left as-is.
- Verdict: NO_NEW_CRITICAL_MAJOR (converged).

## Round 3 (re-confirm after the R2 docs fix)

### Codex response (verbatim)

> NO_NEW_CRITICAL_MAJOR
>
> I found no new critical or major issues against the stated B-16 constraints. The role-recovery store is separate from the orchestrator liveness registry, CHARC recovery does not create `comms/sessions/<id>.json`, and unsafe session IDs are nulled before any role-store or inbox path build. The env role wins over recovery, and the hook-side `recovered in COMMS_ROLES` check prevents garbage records from becoming active roles. The orchestrator registry path appears behavior-preserving, including the prior double-warning shape for unsafe IDs. Non-orchestrator roles do not gain the registry warnings from the session-id hoist.
>
> Only minor residual note: the recovery write catches `OSError` specifically, while `main()` still has the outer catch-all. In normal hook execution this preserves "never block," and direct testable helper behavior is intentionally allowed to surface non-OS programmer errors, so I would not classify it as a blocking finding.

### Adjudication

- **R3 — CONVERGED (NO_NEW_CRITICAL_MAJOR), second consecutive clean round.** The residual minor (OSError-specific catch in the hook's step-2 write vs main()'s catch-all) is BY DESIGN: the step-2 `try/except OSError` guards the expected write-failure mode while leaving programmer errors to surface in tests; `main()`'s outer catch-all is the ultimate never-block-a-prompt net (a non-OSError from the write would still be swallowed by main() in production). Non-blocking; no change. Converged.

## codex-auto-review (complementary second eye)

SUBSTITUTION NOTE: the worktree `.git` is a file WSL git cannot resolve, so `codex exec review --commit/--base` cannot resolve the worktree repo (the known constraint). Per recipe §3, ran codex-auto-review as `codex exec -c model_reasoning_effort=high` over the SAME bundle (prompt + full diff + full post-change hook files) — repo-access-equivalent via the bundled surrounding files. Effort=high (NOT effort=none).

### Codex response (verbatim)

> Findings: none at critical/major severity.
>
> The change keeps the liveness registry isolated under `comms/sessions/*.json`; CHARC writes only `comms/roles/<session_id>` and does not enter the registry path. The hoisted session-id resolution does not leak warnings to non-orchestrator roles, and unsafe ids are nulled before any session-keyed path build. Env role precedence is correct: `HARNESS_ROLE` is used first and refreshes the store; recovery is only used when env is absent and the recovered value is in `COMMS_ROLES`.
>
> The only residual edge is that the recovery record is written by `UserPromptSubmit`, so a session that crashes before its first prompt would not yet have a role record. Given the stated design explicitly places the write in that hook path, I'm treating that as out of scope rather than a B-16 blocker.
>
> NO_NEW_CRITICAL_MAJOR

### Adjudication

- **codex-auto-review — CONVERGED (NO_NEW_CRITICAL_MAJOR).** DISJOINT-but-confirmatory of review-strong; no new findings. The residual edge (a session crashing BEFORE its first prompt has no recovery record yet) is the explicit design — the launcher cannot pre-write the record (it knows the session NAME, not Claude Code's runtime session_id; plan §0.1), the HOOK owns the write at the first prompt, and the documented manual deliberate-resume command (`$env:HARNESS_ROLE='<role>'; claude --resume <id>`, Task 5) is the safety net for exactly that case. Out of scope for B-16; no change.

## Convergence summary

review-strong: R1 (1 Major, FIXED) -> R2 (NO_NEW_CRITICAL_MAJOR, 1 Minor FIXED + 1 Minor accepted-as-V1) -> R3 (NO_NEW_CRITICAL_MAJOR, clean re-confirm). codex-auto-review: NO_NEW_CRITICAL_MAJOR. Both eyes converged. Accept gate: 224 tests OK. PS AST: no parse errors.
