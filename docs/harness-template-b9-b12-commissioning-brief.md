# Commissioning Brief — Harness-Template Scaffold Revision: B-9 (genericity-guard REDESIGN) + B-12 (peer-director-add code)

**Commissioned by:** CHARC (Tool Development Director)
**Date:** 2026-06-22
**Arc:** G4 scaffold-revision — the CODE keystone. **B-9** (genericity-guard REDESIGN; supersedes the B-8 BLOCKER) **+ B-12** (peer-director-add code completeness), batched (coupled via the instance-surface model + the §8 checklist).
**Status:** COMMISSIONED — CHARC-owned harness architecture (CHARC authors the design; the §3 pass is inherent). Awaiting operator dispatch (swing orchestrator → implementer, working IN harness-template).
**⚠ CROSS-REPO — READ FIRST:** ALL edits + commits land in the SEPARATE repo **`C:\Users\rwsmy\harness-template`** (the scaffold; `master`, base HEAD `7f3f7c0` after the G4 doc/charter commits) — **NOT swing-trading.** The swing orchestrator coordinates but dispatches the implementer INTO harness-template. (This brief is a swing-tracked doc; the WORK is in harness-template.)

---

## §0 — Why + the design source (do NOT re-derive; all on disk)

B-9 is the first-live-germination (coa-chess) critique of the scaffold's template-integrity gates: legitimate in PURPOSE (keep the reusable thing reusable) but BLUNT, LEAKY, PERMANENT in realization — filling the seams turns a fresh germination RED on the very act the seams exist to enable (the B-8 blocker: 6 failures on coa-chess). The design is settled; sources:
- **Backlog B-9 entry** — `swing-trading/docs/harness-template-scaffold-backlog.md` (the 4-point design + the operator stdlib-instance-aware refinement).
- **coa-chess feedback** — `C:\Users\rwsmy\coa-chess\docs\template-feedback-genericity.md` (the authored critique).
- **Reference implementation (study + ADAPT, do NOT blind-copy):** coa-chess commits **`ec9856d`** (make the template-purity gates instance-aware + relocate the seam-3 fill) + **`9aee81d`** (scope vocab/ticker bans to the core; exempt the instance surface), in `C:\Users\rwsmy\coa-chess`. coa-chess may have diverged from the template's current gate code — adapt to harness-template `7f3f7c0`, don't transplant.

## §1 — B-9 design contract (the 4 points + the stdlib refinement)

1. **Instance-exemption (the B-8 blocker, properly fixed):** ship an `is_instance_surface()` predicate + scope the genericity scan + the manifest accounting so a FILLED instance surface (APPLICATION.md, the seam-2 cell fills, the seam-3 fill, the instance docs, `charc-state.md`/`<role>-state.md`) is **green-by-construction** — instances must NOT reverse-engineer the guards.
2. **Scope the vocab/ticker bans to the CORE; exempt the instance surface.** A word-ban has false negatives (app-coupling without the word) AND false positives (innocent/meta/legit-domain mentions). The guarantee with TEETH is STRUCTURAL (the dependency-posture test); the word-ban's lasting value is for CORE DOCS. Keep **CORE contamination FAILING**; exempt the instance surface.
3. **Retire the residue/ticker bans as a one-shot EXTRACTION artifact.** The `swing/finviz/SPY/QQQ` bans guard clean-room-extraction leakage — a one-time AUTHORING concern, no ongoing value once verified clean, yet shipped permanently + snagging plain English forever. A "generic" template hard-coding a prior project's tickers in its denylist carries that project's ghost. Run once at authoring, or CORE-only — not a permanent tree-wide gate.
4. **The concrete seam-3 fill needs its own doc.** The mechanism-agnostic-seam guard (correctly) forbids a concrete reviewer in `review-gate-seam.md`, so the instance's seam-3 FILL cannot live there. Ship a `docs/review-gate-<app>.md` pointer convention so instances don't trip the guard mid-fill (coa-chess relocated to `docs/review-gate-coa-chess.md`).

**+ OPERATOR REFINEMENT (2026-06-22, LOAD-BEARING):** the stdlib-only constraint is a property of the **TEMPLATE ITSELF** (keeps the reusable scaffold dependency-light); it **MUST NOT persist into the germinated IMPLEMENTATION** — a consumed project imports third-party freely. So `test_dependency_posture.py` must be made **instance-aware / CORE-scoped** exactly like the vocab guard: prove the reusable CORE stays stdlib-only, but **EXEMPT the instance surface.** Fold it into the instance-aware redesign (it is one of the structural guards the redesign must instance-scope, alongside `genericity_guard` / `manifest_accounting`).

**NET:** scope genericity to the CORE (structurally where possible) + a designed instance-surface seam → **green-by-construction, not red-by-default**, while CORE contamination still fails loud.

## §2 — B-12 design contract (the 3 gaps; coupled to B-9's instance-surface)

- **Gap 1 (silent runtime):** the unread-notice hook `.claude/hooks/user_prompt_submit.py` hardcodes its own role set (`COMMS_ROLES` + the `_inbox_for_role` singular branch) → after a new director is added to the mail role tuples, the notice NEVER fires for it (the new director is silently never told it has mail). **FIX (preferred):** single-source — the hook imports `SINGULAR_INBOX_ROLES` from `role_mail` (it already guarded-imports from `session_start`), so ONE mail-core edit covers delivery AND the notice. (Fallback: a §8 checklist line to edit both sites.)
- **Gap 2 (build-gate; DEPENDS on B-9):** a new director's `<role>-context.md` + `<role>-state.md` carry domain vocab → fail the genericity guard + manifest unless registered as instance surface. **GROUNDING CORRECTION (2026-06-22, post-writing-plans — a CHARC brief miss, owned):** the instance-surface mechanism does NOT pre-exist on harness-template `7f3f7c0` — there is NO `INSTANCE_SURFACE_RELPATHS` and NO `is_instance_surface()` (the live `genericity_lists.py` has only the FORBIDDEN / ALLOWED / SELF_EXCLUDE lists). `charc-state.md` passes the guard TODAY only because the shipped stub is EMPTY (no domain vocab to trip on), NOT via any exemption. **B-9 CREATES the mechanism;** the plan (`14f4062c`) realizes it as `is_instance_surface()` + a DISJOINT pair — `CORE_DOC_RELPATHS` (the reusable-kernel docs) and `INSTANCE_STUB_RELPATHS` (where `charc-state.md` lands). So Gap-2 = once B-9 ships the mechanism, register the new director's instance docs in it + add the §8 checklist line. (My original "`charc-state.md` already is" transcribed coa-chess's POST-fix state as the template's current state — the writing-plans grounding caught it.)
- **Gap 3 (§8 wording):** reword `charc-charter.md` §8 item 2 — split "the generic peer-director contract is already in the kernel (§6 routing/custody + §5.1 state)" vs "the new director's INSTANCE-specific authority lives in its own `<role>-context.md`, NOT the kernel charter (which stays generic/upstreamable)."

## §3 — CHARC architecture pass (inherent — this IS harness architecture)

B-9 redesigns the scaffold's OWN template-integrity self-validation. That is CHARC-owned harness architecture; CHARC commissions + owns the design (this brief) — there is no separate tripwire gate (CHARC IS the gate). **The contamination guard is PARAMOUNT:** the redesign changes WHAT is scoped (CORE vs instance surface), it must NEVER let a project term leak into a CORE file, and CORE contamination must keep FAILING loud. No new external dependency (the core stays stdlib-only — that is the very invariant being instance-scoped, not relaxed for CORE).

## §4 — Cross-repo execution contract (the orchestrator's defaults are swing-set-up — honor these)

- **Repo:** every edit + commit in `C:\Users\rwsmy\harness-template` (the implementer `cd`s there, or worktrees harness-template — NOT a swing worktree). Base off `master` @ `7f3f7c0`.
- **Accept gate:** `python -m unittest discover -s tests` (stdlib **unittest**, NOT pytest) from the harness-template root MUST stay green (currently **168 tests, OK**). This is the no-false-green gate — run it on the FINAL state.
- **Conventions (identical to swing):** conventional commits (`feat`/`fix`/`docs`/`test` scopes); **`trailers []` — ZERO `Co-Authored-By`**; NO `--no-verify`; final `-m` paragraph plain prose (the trailer-parse hazard).
- **Genericity / contamination guard:** the scaffold is application-AGNOSTIC. NO `swing`/`chess`/`coa`/`finviz`/`ticker` config or vocab in CORE files. The redesign changes the SCOPING, never leaks a project term into CORE.
- **Codex review (the WSL-native path):** generate the harness-template diff on Windows (`git -C C:/Users/rwsmy/harness-template diff 7f3f7c0..HEAD`), pre-write it to a file, and feed THAT to the WSL codex — tell Codex NOT to run git (the worktree `.git` is unreachable from WSL; memory `feedback_wsl_native_codex_invocation`). Review-strong (gpt-5.5/high) to convergence over the harness-template diff.
- **Reference impl:** `C:\Users\rwsmy\coa-chess` `ec9856d` + `9aee81d` — study the instance-aware pattern, adapt to harness-template's current gate code.
- **The `.ps1` caveat (B-12 touches no .ps1, but note for the suite):** the unittest greps `launch_role.ps1` content; if any `.ps1` is edited, syntax-check it via the PowerShell AST parser (the unittest does NOT execute PS).

## §5 — Test obligations (harness-template's unittest; TDD)

- **Green-by-construction (the binding B-9 artifact):** a test that simulates a FILLED instance surface (an instance doc with domain vocab + a filled APPLICATION.md + a seam-3 fill) → the gates PASS, where the PRE-redesign gates go RED (the B-8 blocker). This distinguishes the fix (it FAILS pre-redesign, PASSES post).
- **CORE contamination still FAILS:** a planted app-term OR residue in a CORE (non-instance-surface) file → the guard still RED. Distinguishes over-broad exemption (a redesign that exempts everything would pass this wrongly — it must FAIL).
- **Dependency-posture instance-aware (the stdlib refinement):** an instance-surface file importing third-party → dependency-posture PASSES; a CORE file importing third-party → still FAILS. Distinguishes the CORE-scoping.
- **B-12 Gap-1:** single-sourced `SINGULAR_INBOX_ROLES` — a test that the notice hook's role set IS the mail-core set (no drift); adding a role to the core makes the notice fire for it.
- **B-12 Gap-2:** instance docs registered in `INSTANCE_SURFACE_RELPATHS` pass the guard + manifest.
- **The full suite stays green** (168 + the new tests) on the final state.
- Per the regression-test-arithmetic discipline: each distinguishing test must FAIL pre-fix and PASS post-fix — reason both paths.

## §6 — Gates (all binding)

- **Codex review-strong to convergence** over the harness-template diff (+ codex-auto-review if the WSL path supports it on this repo).
- **harness-template unittest GREEN** on the final state (the accept gate; the no-false-green run).
- **CHARC QA on disk** — architecture (the instance-surface model is sound; CORE contamination still fails; NO project term leaked into CORE; the stdlib refinement landed instance-aware, not relaxed) + streaks (`trailers []`, gate green).
- **WITNESS:** the **green-by-construction** test IS the reality check (a scaffold-internal change has no operator browser/CLI surface). No separate operator live-witness required; the operator MAY witness a manual re-germination dry-run (fill the seams → green) if desired.

## §7 — Out of scope

- **B-16** (role-identity-lost-on-resume) — a SEPARATE fast-follow arc (distinct concern: `HARNESS_ROLE` persistence; touches launcher + hooks + bootstrap). NOT this batch.
- **B-11 / B-13 / B-14** (comms-UI re-sync + Stop-hook banking) — ride **G6** (comms-sync).
- **coa-chess's own copy** — coa-chess's CHARC pulls / re-applies as it sees fit; this arc edits the TEMPLATE only.
- **Splitting B-9 / B-12** — if writing-plans judges the batch too large, it MAY split (B-9 first, B-12 second); flag it to the operator, don't silently descope.

## §8 — Return report

The **ORCHESTRATOR** posts the return report to `charc` **AFTER its own QA gate**. The implementer reports to its orchestrator in chat; it NEVER posts to a director inbox (memory `feedback_implementer_never_posts_to_directors`).

## §9 — Dispatch model + effort recommendation

- **writing-plans → `implementer-opus-xhigh`** — the structural-redesign design, the green-by-construction / contamination-still-fails distinguishing-test arithmetic, and the cross-repo care.
- **executing → `implementer-opus-max`** — the keystone structural change to the harness's OWN self-validation, in a SEPARATE repo; highest care (a wrong scoping either re-blocks every future germination OR silently leaks contamination). Codex review-strong to convergence. Select + announce per `docs/implementer-dispatch-recipe.md`.
