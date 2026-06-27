# Commissioning Brief — Harness-Template B-16: role identity lost on session RESUME

**Commissioned by:** CHARC (Tool Development Director)
**Date:** 2026-06-22
**Arc:** G4 scaffold-revision — **B-16** (role-identity-lost-on-resume robustness). A fast-follow after B-9+B-12.
**Status:** COMMISSIONED — CHARC-owned harness architecture. **SEQUENCE AFTER B-9+B-12 MERGES** (both touch `.claude/hooks/user_prompt_submit.py`; B-12 single-sources the role set, B-16 adds the role fallback — sequencing avoids a conflict and lets B-16 build on B-12's single-sourced handling). Dispatch only once B-9+B-12 is on harness-template `master`.
**⚠ CROSS-REPO:** ALL work in `C:\Users\rwsmy\harness-template` (the scaffold), NOT swing-trading. Swing orchestrator coordinates; implementer works IN harness-template. Base = the post-B-9+B-12 `master` HEAD.

---

## §0 — The gap (verified on disk) + source

A session's role lives ONLY in the launch-time `HARNESS_ROLE` env var (`ROLE_ENV`), set by `launch_role.ps1`. **Verified:** `.claude/hooks/user_prompt_submit.py:122` — `role = env.get(ROLE_ENV, "")`. A RESUMED session that bypasses the launcher (`claude --resume <id>` run by hand, or a crash-recovery resume) has `HARNESS_ROLE` UNSET → `role = ""` → SILENTLY: (a) the unread-notice never fires (`role` not in `COMMS_ROLES`) — the director/operator stops being told about incoming mail; (b) for an orchestrator, the registry heartbeat + per-generation-inbox ensure are role-gated (`role == REGISTERED_ROLE`) → a resumed orchestrator stops registering. coa-chess hit this: a resumed CHARC (`HARNESS_ROLE` absent) silently missed an orchestrator message (the notice went dark).

**Source:** `C:\Users\rwsmy\coa-chess\docs\template-feedback-comms-hierarchy.md` (the "role identity is lost on session RESUME" section). This is a RECOMMENDATION — there is **no coa-chess reference impl** for B-16 (unlike B-9); design it fresh.

**Grounded asymmetry:** the registry (`comms/sessions/<session_id>.json`) records `role`, BUT registration is **orchestrator-only** (the deliberate "register only orchestrators" design). So a resumed ORCHESTRATOR's role is recoverable from the registry by `session_id`; a resumed CHARC's is NOT (CHARC is never registered).

## §1 — Design contract (the fix; two complementary parts)

**(a) Resolve role with a recoverable, SESSION-KEYED fallback when `HARNESS_ROLE` is absent.** Before the role gate, the hook resolves `role = env.get(ROLE_ENV)` OR a `session_id`-keyed lookup. The store must cover ALL roles (CHARC included), so a single repo-level `.harness-role` file is INSUFFICIENT (ambiguous when CHARC + an orchestrator run concurrently in one clone). 
- **CHARC's lean:** a thin hook-written `session_id -> role` store, written at the FIRST prompt of a session (when `HARNESS_ROLE` IS set, i.e. the original launch), read as the fallback when `HARNESS_ROLE` is absent — preserving the orchestrator-only *registry* (don't conflate role-recovery with liveness-registration). The launcher cannot pre-write it (the launcher knows the session NAME, not Claude Code's `session_id`), so the HOOK owns the write (it has both `session_id` from the payload AND `role` from the env at original launch).
- **Alternative (writing-plans may choose):** record `role` for all roles in a recovery store that the registry write reuses. Settle the exact mechanism at writing-plans with CHARC; the binding requirement is session-keyed, hook-written, covers CHARC, and degrades safely (no `session_id` → the existing degraded path).

**(b) Document the manual-resume command** that re-sets the env var — `$env:HARNESS_ROLE='<role>'; claude --resume <id>` — in `docs/charc-bootstrap.md` (a resume note) + the `launch_role.ps1` `.NOTES`. The simple deliberate-resume path; the fallback (a) is the safety net for a forgotten/crash resume.

**Safety:** the hook must STILL never block a prompt (always exit 0); the fallback is best-effort (a missing/unreadable store → the existing degraded behavior, logged, never a crash).

## §2 — CHARC architecture pass (inherent)

B-16 touches the registry/hook role-resolution — harness architecture the registry doc marks "changes route through CHARC's tripwire." CHARC commissions + owns the design (this brief). It does NOT relax the orchestrator-only registry (role-recovery is a SEPARATE concern from liveness-registration) and does NOT add a dependency (stdlib-only hooks).

## §3 — Cross-repo execution contract (honor these; the swing defaults don't apply)

- **Repo:** all edits + commits in `C:\Users\rwsmy\harness-template`. Base = the post-B-9+B-12 `master` HEAD (NOT `7f3f7c0` — B-9+B-12 lands first; both touch `user_prompt_submit.py`).
- **Accept gate:** `python -m unittest discover -s tests` (stdlib unittest) from the harness-template root MUST stay green. Run on the FINAL state.
- **Conventions (same as swing):** conventional commits; `trailers []` (ZERO `Co-Authored-By`); NO `--no-verify`; plain-prose final paragraph.
- **`.ps1` caveat:** B-16 edits `launch_role.ps1` (the `.NOTES` resume command) — the unittest greps it but does NOT execute it; syntax-check via the PowerShell AST parser after editing.
- **Codex:** generate the harness-template diff on Windows, pre-write it, feed to the WSL codex (tell it not to run git). Review-strong to convergence over the harness-template diff.

## §4 — Test obligations (harness-template unittest; TDD)

- **The binding artifact:** a resumed session with `HARNESS_ROLE` ABSENT but a recoverable `session_id->role` store → the role resolves → the unread notice fires (for `charc` AND orchestrator) + (orchestrator) the registry heartbeats. PRE-fix (no fallback) `role=""` → notice silent / no heartbeat. Distinguishes the fix (FAILS pre-fix, PASSES post).
- **CHARC recovery specifically:** a resumed CHARC (unregistered) recovers its role from the store (the registry alone would NOT serve CHARC — assert the fallback covers it).
- **Safe degrade:** no store + no `HARNESS_ROLE` → the existing degraded behavior, no crash, hook exits 0.
- **No concurrency ambiguity:** two roles in one clone resolve to their OWN roles (session-keyed, not a single shared file).
- The full suite stays green. Each distinguishing test FAILS pre-fix, PASSES post (reason both paths).

## §5 — Gates

- **Codex review-strong to convergence** over the harness-template diff (+ codex-auto-review if supported).
- **harness-template unittest GREEN** on the final state.
- **CHARC QA on disk** — the fallback is session-keyed + covers CHARC + preserves the orchestrator-only registry + degrades safely + never blocks a prompt; streaks (`trailers []`, gate green).
- **WITNESS:** the resume-recovers-role test is the reality check; the operator MAY witness a real manual resume (`claude --resume` without re-setting `HARNESS_ROLE`) confirming the notice still fires — a strong optional witness, not required.

## §6 — Out of scope

- B-9 / B-12 (the preceding arc) — B-16 sequences AFTER them.
- B-11 / B-13 / B-14 (comms-UI / Stop-hook) — ride G6.
- Changing the orchestrator-only registry design — role-recovery is a SEPARATE store; do NOT register CHARC for liveness.
- coa-chess's own copy — its CHARC pulls/re-applies; this edits the TEMPLATE only.

## §7 — Return report

The **ORCHESTRATOR** posts the return report to `charc` AFTER its QA. The implementer reports to its orchestrator in chat; never to a director inbox.

## §8 — Dispatch model + effort recommendation

- **writing-plans → `implementer-opus-xhigh`** — the fallback-mechanism design choice (session-keyed store vs registry reuse) + the resume/degrade distinguishing tests.
- **executing → `implementer-opus-high`** — a contained hook/launcher/bootstrap change (smaller + less structural than B-9; not a measurement mutation), so `-high` not `-max`. Codex review-strong to convergence. Select + announce per `docs/implementer-dispatch-recipe.md`.
