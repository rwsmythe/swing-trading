# Generic Harness Scaffold — Design Spec

**Date:** 2026-06-16 · **Author:** CHARC (swing-trading harness), operator-directed · **Status:** design, pre-writing-plans.

**Deliverable:** a new, authored, clean-room repository — the reusable *empty harness scaffold*. This spec lives in the swing-trading repo as the design record; the scaffold itself is built in its own repo (Approach A), dogfooded by this harness (swing CHARC + orchestrator + implementers).

---

## 1. Purpose & scope

Extract swing-trading's multi-agent **construct** — the Director / Orchestrator / Implementer role model, the file-based comms system (including the orchestrator extension), and a self-bootstrapping flow — into a **minimal, application-agnostic scaffold**. A fresh instance ships one default Director, **CHARC**, who owns harness + application operation and performs the bootstrap (the same role the operator runs in swing-trading). After instantiation, that CHARC interviews the operator and *fills the application in*, turning the seed into a configured project. The interview fills the three **definition** seams (application, domain cells, review/gate mechanism); the fourth seam (launcher model/effort defaults) ships a working default the operator tunes anytime — not a bootstrap blocker.

### Hard constraints
- **Minimal + generic.** Ship the generic operating *model*, not invented application machinery.
- **Zero application contamination.** No domain content of any kind. (The operator's "COA-developing system, starting in chess" was an *example only* and must not appear anywhere in the scaffold; the new harness's own CHARC defines and builds its application later.)
- **Same substrate.** The scaffold targets the same execution substrate as swing-trading — Claude Code + the sub-agent dispatch model + the Windows/WSL comms tooling — so the comms infra, launcher, and hook lift with light genericization rather than a platform-neutral rewrite.

### Success criterion
After cloning the scaffold and launching CHARC, CHARC can immediately *operate the harness* (comms works; the role protocols + dispatch + review/gate shapes are present and runnable) and its first act is the application-definition interview that fills the three definition seams (1-3; seam 4 ships a tuned default). "Sufficient instructions to bootstrap itself" = the operating model is present; only the application + the domain-specific mechanisms are seams.

---

## 2. Approach (decided: A — authored clean-room repo)

**Authored fresh in a new repo**, not forked-and-stripped, not a config-driven engine. Rationale:
- *Faithful* — the swing harness has no "engine"; it is docs + comms scripts + agent-cell files operated by Claude. The scaffold mirrors that reality.
- *Clean decoupling* — authoring fresh (vs. fork-and-strip) leaves no swing residue and no swing git history; the new-repo boundary is itself the test (if it can't stand up without swing, the abstraction failed).
- *Minimal* — no invented runtime (rejected the config-engine approach as over-build).

Dogfooded: swing CHARC designs (this spec) → writing-plans → swing orchestrator + implementers produce the scaffold in the new repo.

---

## 3. The generic / specific split (the crux)

**Lifted-generic** (stripped of all swing-isms — no SQLite/pytest/Codex-as-the-gate/finance/schema/HTMX):
- the comms machinery (mailbox CLI, UI, hooks, launcher);
- the three role-protocol docs (director charter, orchestrator context, dispatch recipe);
- the review/gate *protocol shape* and the carry-over *disciplines*.

**Three definition seams** (1-3 — filled in the bootstrap interview) **+ one tunable default** (4):
1. **Application** (`APPLICATION.md`) — what the project *does*. Ships as a stub.
2. **Domain implementer cells** — only one generic template cell ships; CHARC authors domain-tuned cells.
3. **Review mechanism + gate criteria** — `review-gate-seam.md` defines the *shape* + a minimal generic *default* (§5.3), not a domain mechanism (Q2=b). A ready-to-use Codex reviewer reference is provided as an *optional* plug-in (§5.4).
4. **Launcher model/effort defaults** — ships a **working default**; the operator tunes it anytime. NOT a bootstrap must-fill.

**The kernel** = `charc-charter.md` + `charc-bootstrap.md`: a fresh CHARC reads the charter (its authority + disciplines), verifies comms, then runs the interview that fills seams 1–3.

---

## 4. Repo layout / file manifest (~14 files)

```
<harness-template>/                  ← new authored repo
  README.md                  what it is · how to instantiate · "launch CHARC, it takes over"
  APPLICATION.md             ⟦SEAM 1⟧ "CHARC defines the application here" — stub
  comms/                     mailbox root — a committed `.gitkeep`; role inboxes + the orchestrator registry auto-create at first use
  scripts/
    role_mail.py             ← swing role_mail.py · GENERIC (taxonomy → charc|orchestrator|operator)
    comms_ui.py              ← swing comms_ui.py · GENERIC, OPTIONAL (needs a [web] extra)
    launch_role.ps1          ← swing start_directors.ps1 · GENERIC role launcher: sets HARNESS_ROLE=<role> + model/effort (⟦SEAM 4⟧ default); launches BOTH charc AND orchestrator sessions
  .claude/
    settings.json            hook registration
    hooks/
      user_prompt_submit.*   ← swing unread hook · GENERIC (env gate SWING_ROLE → HARNESS_ROLE) + heartbeat + register
      session_start.*        NEW (registry: opportunistic prune)
      session_end.*          NEW (registry: best-effort tidy)
    agents/
      implementer-template.md  ⟦SEAM 2⟧ ONE generic cell template
  docs/
    charc-charter.md         ← tool-director-context.md · KERNEL — director owns harness+app; generic disciplines
    charc-bootstrap.md       ← director_bootstrap_charc.md · CHARC first-run (verify comms → app interview → fill seams → commission)
    orchestrator-context.md  ← orchestrator-context.md · GENERIC operating model
    dispatch-recipe.md       ← implementer-dispatch-recipe.md · GENERIC (isolated workspace, validation evidence, acceptance transfer, return rule)
    review-gate-seam.md      ⟦SEAM 3⟧ the (b) review/gate CONTRACT: protocol + extension points + disciplines, mechanism-agnostic
    codex-reviewer.md        OPTIONAL reference — "how to incorporate Codex as the REVIEWER" (plugs into seam 3)
    comms-orchestrator-registry.md   the orchestrator inbox + session-registry design (built, not deferred)
```

**Hard dependency posture:** the *core* (`role_mail.py` + the hooks) is pure stdlib — **zero hard runtime deps**. `comms_ui.py` (FastAPI/HTMX) is shipped but **optional** (a `[web]` extra).

---

## 5. Component design

### 5.1 Comms infra (one director + the orchestrator extension)
- **Taxonomy → one director.** `VALID_FROM = {charc, orchestrator, operator}`, `VALID_TO = {charc, orchestrator, operator}`. Everything else in `role_mail.py` is already generic and lifts verbatim: message types (`fyi|status|query|return_report|decision_request`), thread slugs, the single-write-path / role-custody locks, the unique-path idempotency. Implementers do not post (they report up in chat to the orchestrator — a discipline stated in the dispatch-recipe, not encoded in the enum).
- **Orchestrator extension (included, built — not deferred).** The orchestrator has an **inbox** (swing runs the V1 send-only orchestrator with Stage-2 deferred; the scaffold ships the extension *realized*). Because **multiple orchestrator generations can run concurrently**, "the orchestrator" is not a single target — so the scaffold builds the **session registry** (swing's `comms-stage2-orchestrator-inbox-design.md`, promoted from deferred spec to built infrastructure):
  - keyed by the hook-provided **`session_id`** (the documented one);
  - **liveness = a hook-written `last_seen` heartbeat** refreshed each `UserPromptSubmit` turn;
  - **opportunistic prune** of stale entries (reader-as-cleaner + at `SessionStart`) — no daemon;
  - **role-gated registration** via the launch-time `HARNESS_ROLE` env var (only orchestrators register); **recreate-if-missing self-healing** (the hook owns the full entry);
  - `SessionEnd` best-effort idempotent tidy (correctness does not depend on it firing).
  - **Addressing — DIRECTION-ASYMMETRIC (operator-decided 2026-06-16):** the two directions differ because the ambiguity is one-sided.
    - **Orchestrator → director: SHARED.** A director (charc/operator) has ONE inbox (`comms/charc/inbox`); any orchestrator generation posts to it. No ambiguity (the director is singular). `--to charc`. Unchanged.
    - **Director → orchestrator: PER-GENERATION (specific addressing).** Because multiple orchestrator generations can be live, "the orchestrator" is not a single target — a message to a specific generation MUST reach THAT generation. So each orchestrator generation owns `comms/orchestrator/<session_id>/inbox` (created when it registers). A director addresses a generation explicitly via `--to orchestrator:<session_id>`, OR via the convenience `--to orchestrator` = the **newest-live** generation (resolved against the registry at send time). The registry (session_id-keyed) is the source of truth for live generations + newest-live.
    - This **replaces** the shared-inbox-with-atomic-move-claim model: per-generation inboxes eliminate the double-drain race entirely (each inbox is drained by exactly its own generation — no claim contention, no handoff-stop-draining discipline). The registry resolution (newest-live / by-`session_id`) + the per-generation inbox layout are specified in `comms-orchestrator-registry.md`.
  - **Hook contract (Major-6 resolution):** the registry consumes the documented hook-JSON field **`session_id`** (the registry key) under three events — `UserPromptSubmit` (heartbeat + role-gated register + recreate-if-missing), `SessionStart` (prune), `SessionEnd` (tidy). If `session_id` is ABSENT from the payload (a substrate-version change), the registry **degrades** to a documented single-orchestrator assumption + logs an actionable warning — it never silently mis-keys; a last-resort fallback to the undocumented session env var is permitted but logged as degraded. The exact required fields + the degraded mode live in `comms-orchestrator-registry.md`. Orchestrator sessions are launched with `HARNESS_ROLE=orchestrator` via `launch_role.ps1` (the same launcher as CHARC, role-parameterized).
- **Adding a peer director later** touches a small **enumerated** set — the role sets (`VALID_FROM`/`VALID_TO`), the new inbox (auto-creates), any routing/custody note + authority in the charter, and optionally a launcher default — captured as a checklist in the charter, not built now. (Not literally "two lines.")
- **Hooks** lift with the env-gate rename (`SWING_ROLE` → `HARNESS_ROLE`); the wt.exe-new-tab env-inheritance wrapper fix and the `.claude/settings.json` minimal-tracked-file pattern carry over unchanged.

### 5.2 The three generic role protocols
- **`charc-charter.md`** (director) — CHARC's standing authority (owns harness + app operation) + the generic disciplines: director-as-peer push-back, verify-on-reality, the **tripwire / architecture-pass** concept (changes crossing the seams route through CHARC), the comms routing rules (directors↔directors allowed; the director cannot bus-reply to a foreign role it does not own — route via the operator). Stripped of all swing arc/phase content.
- **`orchestrator-context.md`** — the orchestrator operating model: coordinate implementers, the dispatch model, QA-the-implementer-product, own the merge/accept step, the comms routing. Generic.
- **`dispatch-recipe.md`** — the implementer protocol, framed around four GENERIC concepts with **no source-code assumption** (Major-4 resolution): an **isolated workspace** (parallel implementers don't collide), a **product** (whatever the cell produces), **validation evidence** (the build cycle: produce → validate → converge — the domain's equivalent of red-green-refactor), and **acceptance transfer** back to the orchestrator (the return-report). The disciplines carry as-is (honor locks, STOP-and-ask on a premise mismatch, ground-don't-guess, the review-to-convergence loop pointing at seam 3). The substrate's COMMON instantiation — a git **worktree** for isolation, a **diff/merge** for acceptance — is named as the *default on this substrate*, NOT assumed: a non-source-code domain supplies its own isolation + acceptance mechanism. The software-specific gate bits (pytest/ruff, the Codex transport) are NOT in the generic recipe — they live in seam 3 + the optional `codex-reviewer.md`.

### 5.3 The review/gate seam contract (`review-gate-seam.md`, Q2=b)
Three parts — two empty seams, one filled:
1. **Review-to-convergence protocol (shape fixed; mechanism seam):** product → adversarial **reviewer** → severity-classified findings → **adjudicate** each → **iterate to convergence** (zero new blocking). Extension points the new CHARC fills: `REVIEWER`, `PRODUCT_REPRESENTATION`, `SEVERITY_RUBRIC`, `CONVERGENCE_CRITERION` (default: zero-new-blocking).
2. **The gate (director-owned, before accept):** a checklist of pass/fail **checks**. Extension points: `GATE_CHECKS`, `WITNESS` (the irreducible reality/human check the automated reviewer can't replace), `ACCEPTANCE` (what merge/accept means).
3. **Carry-over disciplines (filled — generic wisdom):** the reviewer is fallible, the witness is the true net (review is a *filter*, never the gate); run to convergence — don't pad/stop early; adjudicate, don't blind-fix (a finding premised on something the system *verifiably prevents* is out-of-scope **with a cited constraint**; absent the citation it stays in-scope); verify on reality, not from the report; ground or STOP.

**A minimal generic DEFAULT (Major-5 resolution) — operable from minute one, replaceable at app-definition.** So a fresh CHARC can run the harness against its own bootstrap changes *before* customizing, the seam ships defaults: `SEVERITY_RUBRIC` = {blocking: critical, major · advisory: minor}; `CONVERGENCE_CRITERION` = zero-new-blocking; `GATE_CHECKS` = [the director's stated conditions hold AND the `WITNESS` confirms]; `WITNESS` = operator confirmation; `REVIEWER` = a self-review pass (CHARC or a fresh agent re-reads the product adversarially) until a domain reviewer is plugged. These are clearly marked **replaceable starters** — the interview's job is to swap in the domain's real rubric/gate/reviewer.

The doc names the extension points and points to the optional Codex reference for the `REVIEWER` slot; it never names a mechanism in the protocol itself.

### 5.4 The Codex-reviewer reference (`docs/codex-reviewer.md`, optional plug-in)
A stocked-toolbox reference for the `REVIEWER` extension point — the swing-proven Codex incorporation, extracted so a new CHARC need not relearn it. Framed as **one optional mechanism, not THE reviewer** (a non-software domain may plug a different reviewer and ignore it). Contents: the WSL-native invocation (the `export PATH="$HOME/.local/node22/bin:$PATH"` prefix is required) + the `codex --version` liveness probe; the review tiering (`-p <tier>` profiles, tiered by blast-radius of a missed finding); the staging (`--skip-git-repo-check`, pre-generate the diff because the worktree `.git` is WSL-unreachable, pipe via stdin, write output to a file for the cp1252 glyph issue); run-to-convergence (`NO_NEW_CRITICAL_MAJOR`, persist every response). Harness tooling, domain-agnostic; substrate-coupled (WSL/Windows/Codex), which is acceptable given the same-substrate constraint. `review-gate-seam.md` states explicitly that Codex is **one replaceable `REVIEWER` implementation, not part of the core protocol** — a non-software domain plugs a different reviewer and ignores this file.

### 5.5 The kernel — bootstrap first-run flow
- **`README.md`** (operator-facing): what it is + instantiate (copy the repo, set the `HARNESS_ROLE` convention, launch CHARC) → "launch CHARC; it takes over."
- **`charc-bootstrap.md`** (CHARC's literal first session): (1) read the charter; (2) verify comms (role_mail round-trip; the hook + UI; the orchestrator registry); (3) **the application-definition interview** with the operator — fill seams 1–3 (the app domain → `APPLICATION.md`; the domain cells → author from `implementer-template.md`; the review/gate mechanism → fill the `review-gate-seam.md` extension points or accept the §5.3 defaults, optionally adopting `codex-reviewer.md`); (4) commission the first arc(s).

**The bootstrap checklist (Major-2/3 + Minor-5 resolution) — every file CHARC touches, so the no-engine design carries no hidden coordination debt:**
1. `APPLICATION.md` — define the app domain (seam 1).
2. `.claude/agents/` — author the domain implementer cells from `implementer-template.md` (seam 2).
3. `review-gate-seam.md` — fill the extension points, or accept the §5.3 defaults, optionally adopting `codex-reviewer.md` (seam 3).
4. `launch_role.ps1` — (optional) tune the model/effort default (seam 4).
5. **Bring up the orchestrator** — launch an orchestrator session via `launch_role.ps1 orchestrator` (sets `HARNESS_ROLE=orchestrator` → it registers); CHARC verifies the registry shows it live before commissioning the first arc.

The bootstrap GUARANTEE is **staged**: **CHARC operation** (comms + charter) works on a bare clone; **orchestrator + implementer operation** works after step 5. The interview drives 1-3; 4-5 are mechanical.

---

## 6. Data flow — germination
Instantiate (copy repo) → launch CHARC → CHARC reads charter + verifies comms → CHARC runs the application-definition interview → the three definition seams are filled → the empty seed is now a configured project (its filled `APPLICATION.md` + domain cells + review/gate become the project's living context, the way swing's docs are) → the harness operates normally: CHARC architects → orchestrator dispatches → implementers produce → review-to-convergence → gate → accept.

---

## 7. Error handling / degradation
- **Comms is best-effort + self-healing.** `role_mail` is the stdlib core; the optional UI failing never blocks the core. The registry's correctness is independent of `SessionEnd` firing (the opportunistic prune + the `last_seen` liveness + recreate-if-missing handle crashes/window-close).
- **No domain failure modes ship** (there is no domain). The scaffold's only runtime behavior is comms + the registry.

---

## 8. Testing (validating the scaffold itself)
- **Comms round-trip:** post → read → ack across the three roles; the single-write-path / idempotency locks.
- **Registry:** register-on-prompt, `last_seen` heartbeat, opportunistic prune of a stale entry, recreate-if-missing self-heal, role-gated registration (only orchestrators register), `SessionEnd` idempotent tidy.
- **Bootstrap dry-run:** a fresh-clone walkthrough confirms CHARC can verify comms and reach the interview with no further setup.
- **Genericity guard (Major-7 resolution) — a grep-based test with three explicit lists:** (a) a **forbidden vocabulary** (swing, trading, finviz, schwab, SQLite, pytest, ruff, finance tickers — AND the example terms chess / COA / course-of-action) that must appear NOWHERE; (b) an **allowed substrate vocabulary** (Claude Code, WSL, Windows, PowerShell, Codex, git) permitted because the scaffold is substrate-coupled; (c) **file-scope exceptions** — Codex/WSL/git terms are allowed in `codex-reviewer.md` + `dispatch-recipe.md`'s substrate-default note, and FORBIDDEN in `review-gate-seam.md`'s protocol section (which must stay mechanism-agnostic). The test fails the build on any forbidden-vocab hit, or any substrate term outside its allowed file scope.

---

## 9. Decided choices
- Q1 = **B** (full generic operating model present; app/gate/cells as seams).
- Q2 = **b** (review/gate seam = generic protocol/contract with named extension points; mechanism-agnostic).
- Approach **A** (authored clean-room repo, dogfooded).
- **One director** (CHARC); no RD analog (peer-director-add documented).
- Orchestrator extension **included + built** (inbox + session registry); **DIRECTION-ASYMMETRIC addressing** (operator-decided 2026-06-16): shared orchestrator→director, **per-generation** director→orchestrator (`orchestrator:<session_id>` / newest-live).
- Codex reviewer **included as an optional reference**, not in the seam protocol.
- Core comms **zero hard deps** (stdlib); UI optional.

## 10. Out of scope
- Any application, domain, or example content (explicitly: no chess / COA / trading).
- A second director / RD analog (documented, not built).
- A config-driven harness "engine" (rejected).
- (Per-generation director→orchestrator addressing is now IN scope / SHIPPED — operator-decided 2026-06-16, §5.1 — no longer deferred.)
- Platform-neutral comms (same-substrate assumption).

## 11. Open sub-decisions (for writing-plans / build)
- Exact registry file format + the staleness threshold (the Stage-2 spec suggests 30–60 min; tune at build).
- (`comms_ui.py` ship/optional and the genericity-guard mechanism are resolved — §4 and §8 respectively.)
