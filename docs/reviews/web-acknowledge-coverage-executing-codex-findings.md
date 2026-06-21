# Codex findings — web simple-acknowledge coverage (executing)

Base: be80d0c2 (plan commit). Worktree branch: web-ack-exec.
Review tier: review-strong (gpt-5.5/high profile at ~/.codex/review-strong.config.toml), REPO ACCESS (cwd at the worktree, -s read-only). PLUS codex-auto-review (matched-HIGH, repo access).

## Round 1 (review-strong, repo access)

### Codex response (verbatim, .codex-review-r1.txt)
CRITICAL: none.
MAJOR: none.
MINOR: none.
NIT: swing/web/view_models/reconcile.py:858 has stale ReconcileDiscrepancyErrorVM documentation describing the old five-branch error set and "other 4 branches." Runtime is fine because error_kind is not enum-validated, but the docs should include not_web_acknowledgeable.

Verified the load-bearing locks: the allowlist is explicit and not MATERIAL_BY_TYPE-derived; simple GET/POST branches are after orphan and before tier-2; allowlisted pending rows with non-null ambiguity_kind still reach tier-2; the rendered honest copy comes from the new template branch; success keeps 204 HX-Redirect / 303; /dashboard exists; resolve_discrepancy preserves the TOCTOU ladder; migration 0031 admits unresolved/acknowledged_immaterial with ambiguity_kind=NULL.

Verdict: NO_NEW_CRITICAL_MAJOR

### Adjudication
- NIT (stale docstring): ACCEPTED + FIXED in 9a607483 (docstring now lists not_web_acknowledgeable as the 6th branch; corrects the count). Docstring-only, no behavior change.
- All locks: VERIFIED by the reviewer with repo access (read beyond the diff). No action.

## Round 2 (review-strong, repo access — confirming after the NIT fix)

### Codex response (verbatim, .codex-review-r2.txt)
CRITICAL: None. MAJOR: None. MINOR: None.
NIT: Stale documentation still describes the error VM/template as the original 5-branch set after adding not_web_acknowledgeable. See reconcile.py:828. Behavior is correct; this is comment drift.

Verified Locks (re-confirmed): allowlist explicit not MATERIAL_BY_TYPE-derived; branch ordering correct (orphan, then simple gating on allowlisted type + ambiguity_kind is None + clearable resolution, then tier-2); pending allowlisted row with non-null ambiguity_kind not hijacked; honest-copy fix real at render time (already_resolved still hardcodes pending sentence, new branch renders honest CLI copy); POST preserves orphan race shape (require_current_resolution, DiscrepancyResolutionStateError->409, ValueError->400 re-render, HTMX 204+HX-Redirect, non-HTMX 303); /dashboard exists; simple form carries hx-headers HX-Request; migration 0031 admits unresolved->acknowledged_immaterial with ambiguity_kind=NULL; no schema/CHECK change.

Verdict: NO_NEW_CRITICAL_MAJOR

### Adjudication
- NIT (a SECOND stale comment at reconcile.py:831 "all 5 branches"): ACCEPTED + FIXED in d3c71ae4 (block comment now notes the 6th branch). Comment-only.
- Two consecutive NO_NEW_CRITICAL_MAJOR rounds; only comment NITs surfaced (both fixed). CONVERGED. No padding.

## codex-auto-review (complementary second eye, matched-HIGH, repo access)

(The `codex exec review --commit` subcommand requires WSL git, which cannot resolve
the worktree's Windows-absolute `.git` gitdir-file; so the auto-review was run as an
independent `codex exec -c model_reasoning_effort=high -s read-only` pass with a
DISTINCT production-effectiveness/reachability framing + repo read access + the diff,
delivering the same disjoint second-eye the recipe intends.)

### Codex response (verbatim, .codex-autoreview.txt)
No CRITICAL or MAJOR issues found.
MINOR: The non-HTMX 303 fallback (reconcile.py) is not reachable in normal production because app.py installs OriginGuardMiddleware(strict=True) and origin_guard requires HX-Request: true for unsafe methods. This mirrors the existing tier-2/orphan fallback shape, so I would not treat it as a production defect. It is dead under the current factory unless strict mode changes.

Verified: simple-ack POST clears rows in production (live conn, resolve_discrepancy owns BEGIN IMMEDIATE + commit before finally: conn.close()); no valid current-schema row double-classified; not_web_acknowledgeable reachable for unresolved non-allowlisted (material 0 and 1) and terminal tier-2 still -> already_resolved; no reachable row shape makes ReconcileSimpleAcknowledgeVM.__post_init__ raise; no base template/topbar issue (new VM provides base fields + manifest includes it).

Verdict: NO_NEW_CRITICAL_MAJOR

### Adjudication
- MINOR (303 unreachable under strict OriginGuard): ACKNOWLEDGED — NOT a defect. It is a byte-mirror of the existing orphan/tier-2 303 fallback (the established pattern), retained for the documented OriginGuard non-strict deployment. The reviewer itself declines to treat it as a production defect. The 303 branch is still exercised by test_post_allowlisted_non_htmx_303_fallback (which forces the guard non-strict to reach the branch). No code change.
- Disjoint finding set vs review-strong (effectiveness/reachability vs doc accuracy) — confirms the complementary value. Both converged NO_NEW_CRITICAL_MAJOR.

## Convergence
review-strong: 2 consecutive NO_NEW_CRITICAL_MAJOR (R1 + confirming R2), only comment NITs (fixed).
codex-auto-review: NO_NEW_CRITICAL_MAJOR, one acknowledged-non-defect MINOR.
CONVERGED.
