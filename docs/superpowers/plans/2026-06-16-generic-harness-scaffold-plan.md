# Generic Harness Scaffold — Implementation Plan

**Date:** 2026-06-16 · **Author:** dispatched implementer (writing-plans), CHARC-commissioned · **Status:** plan, pre-executing.

**Input (binding):** [`docs/superpowers/specs/2026-06-16-generic-harness-scaffold-design.md`](../specs/2026-06-16-generic-harness-scaffold-design.md) — the adversarial-converged design. This plan **decomposes that spec**; it does not redesign. Section references below (`§N`) are to that spec.

**Commission:** [`docs/harness-scaffold-writing-plans-brief.md`](../../harness-scaffold-writing-plans-brief.md).

**Dogfooding sources (extract-from):** swing's live `scripts/role_mail.py`, `scripts/comms_ui.py`, `scripts/start_directors.ps1`, `scripts/comms_unread_hook.py`, `.claude/settings.json`, `docs/tool-director-context.md`, `docs/orchestrator-context.md`, `docs/implementer-dispatch-recipe.md`, `scripts/director_bootstrap_charc.md`, `scripts/orchestrator_bootstrap.md`, `.claude/agents/implementer-*.md`, and (the most substantial build piece) `docs/comms-stage2-orchestrator-inbox-design.md`.

---

## 0. What this plan IS and IS NOT

- **IS** a task-decomposed implementation plan for building the **generic harness scaffold** — a NEW, authored, clean-room repository (spec **Approach A**) — at the *executing-plans* phase.
- **IS NOT** the scaffold itself. **This plan is PLAN-ONLY: the executing phase creates the new repo and its files. Do NOT create the new repo or scaffold any of its files while producing/reviewing this plan.** This plan document lands in the *swing* repo at `docs/superpowers/plans/`.
- The scaffold is built in its OWN repo with **zero swing residue** (Approach A authored-fresh, not fork-and-strip) and **zero application/domain content** (no chess / COA / course-of-action / trading / finance — §10 + the §8 genericity guard).

### 0.1 Executing-plans REVIEW TIER (flag, load-bearing)

**Building the scaffold is `review-strong`, NOT `review-fast`.** Although THIS writing-plans phase is `review-fast` (a plan/doc defect is caught downstream), the *executing* phase ships harness **production code** — the comms CLI, the session registry + lifecycle hooks, and the genericity-guard build test. A missed major in any of those has real blast-radius (a broken registry mis-keys live orchestrator traffic; a hole in the genericity guard lets app/domain content leak into the "generic" scaffold). The executing dispatch MUST run `review-strong` (recipe §3), run-to-`NO_NEW_CRITICAL_MAJOR`, cap suspended. This is stated here so the executing orchestrator cannot tier it down by inertia.

### 0.2 The new-repo logistics — OPERATOR DECISIONS REQUIRED BEFORE EXECUTING

The plan assumes a NEW git repository, created BEFORE the first executing task runs. Two questions are **operator-owned and must be answered before the executing dispatch is cut** (flagged per brief §5; NOT decided here):

- **DECISION A — repo name + location.** This plan uses the placeholder **`harness-template/`** throughout (the §4 manifest root token). The operator picks the real name (e.g. `harness-template`, `harness-seed`, `agent-harness-scaffold`) and where it lives (a sibling dir of swing-trading, e.g. `C:/Users/rwsmy/harness-template`, vs elsewhere). Every `<harness-template>` token in the spec/plan resolves to that choice.
- **DECISION B — who runs `git init` and when.** Two options:
  - **B1 (recommended): the operator inits an empty repo first**, then dispatches the executing implementer pointed at it (the implementer's "isolated workspace" is a branch/worktree of that repo). This keeps the new-repo creation an explicit operator act and gives the implementer a real git root from task 1.
  - **B2: the executing implementer runs `git init`** as its task-0 (the plan's first task creates the repo). Simpler dispatch, but the implementer creates the repo boundary itself.
  - Either way, the executing implementer works in an **isolated workspace within the NEW repo** (its own branch / worktree there) — NOT in a swing-trading worktree, and NOT the swing `.worktrees/` path (that path is swing's convention; the new repo carries the same convention via its own copied `dispatch-recipe.md`).
- **DECISION C (deferred, NOT a bootstrap blocker) — shared-inbox vs per-generation orchestrator addressing.** The spec decides **shared-inbox** as the ship default (§5.1, §9). Per-generation addressing (`orchestrator-<session_id>`) is documented as the first-class upgrade. The plan builds shared-inbox; `comms-orchestrator-registry.md` documents both + the claim rule. No operator action needed unless the operator wants per-generation from day one (then flag back to CHARC — it changes Task Group D's addressing tasks).

**Until DECISION A + B land, the executing dispatch cannot start.** They are mechanical (a name + an init), but they gate the first task.

---

## 1. Approach to the task decomposition

The scaffold has **no runtime engine** — it is docs + comms scripts + agent-cell files operated by Claude (§2). So "TDD" applies cleanly only to the executable surface (the comms CLI, the hooks/registry, the genericity guard, the optional UI). For the **doc deliverables** (charter, bootstrap, orchestrator-context, dispatch-recipe, review-gate-seam, codex-reviewer, the registry design doc, README, APPLICATION stub, the implementer-template cell, settings.json) the equivalent of red-green is an **acceptance check**: a content checklist the doc must satisfy + the **genericity guard** (Task Group F) passing over it. Every task below carries one of:
- a **failing test → green** cycle (executable surface), or
- an **acceptance check** (docs) — an explicit, verifiable list, PLUS the genericity-guard gate.

**The genericity guard (Task Group F) is the spine.** It is authored EARLY (its forbidden/allowed/exception lists, before most content lands) so every subsequent doc/script task is written against a guard that will fail the build on a swing-ism or an app/domain term. Practically: F1 (the guard test + its three lists) ships first among the "content" groups; thereafter each doc task's acceptance check includes "the genericity guard passes over the new file."

**Test substrate (executable surface) — stdlib `unittest`, NOT pytest.** The new repo's core is **pure stdlib** (§4 hard-dependency posture), and the scaffold's OWN test suite is **stdlib `unittest`** — NOT pytest. This is REQUIRED, not a preference: the §8 genericity guard's forbidden-vocabulary list includes `pytest` (a swing-ism / "pytest-as-the-gate" term that must appear NOWHERE in the tracked tree), so a pytest dev-dep or a `pytest`-named test path would make the scaffold FAIL its own guard. The core comms/registry/guard tests run under `unittest` (zero hard deps, matching the spec's zero-hard-deps posture). The optional `comms_ui.py` tests use FastAPI's `TestClient` (which is just a client object — it works under `unittest`, no pytest needed) and are gated behind the `[web]` extra. **No `pytest` anywhere in the scaffold's tracked tree** (not in `pyproject.toml`, not in a test path, not in a doc) — the guard enforces it.

**Commit conventions (carried into the NEW repo):** conventional commits carrying the task id (`feat(comms): Task D.3 — ...`), **ZERO `Co-Authored-By`**, no `--no-verify`, no amend (new commit per fix), ASCII-only user-facing strings (Windows cp1252). These are the swing disciplines, which the new repo's own `dispatch-recipe.md` (Task C.3) restates generically.

---

## 2. Task groups (overview)

| Group | Theme | Tasks | Spec anchor |
|---|---|---|---|
| **A** | Repo skeleton + dependency posture + README | A.1–A.3 | §4, §5.5 |
| **B** | The generic comms CLI (`role_mail.py`) | B.1–B.4 | §5.1 |
| **C** | The three role-protocol docs + dispatch-recipe | C.1–C.4 | §5.2 |
| **D** | Orchestrator inbox + session registry (the build) | D.1–D.7 | §5.1, §5.5 step 5 |
| **E** | The launcher (`launch_role.ps1`) + hooks wiring | E.1–E.3 | §5.1 |
| **F** | The genericity guard (grep build test) | F.1–F.3 | §8 |
| **G** | Review/gate seam + Codex-reviewer reference | G.1–G.3 | §5.3, §5.4 |
| **H** | The kernel: charter + bootstrap + the 5-step checklist | H.1–H.3 | §5.5 |
| **I** | The optional mail UI (`comms_ui.py`, `[web]` extra) | I.1–I.2 | §4, §5.1 |
| **J** | Validation suite + bootstrap dry-run + final acceptance | J.1–J.3 | §8, §5.5 |

Ordering rationale (the EXACT task sequence — note F.1 runs BETWEEN A.1 and A.2, R16): **A.1** (repo skeleton) → **F.1** (the guard test + its three lists — authored IMMEDIATELY after A.1, BEFORE any content doc) → **A.2 + A.3** (README + APPLICATION stub — now gated by the already-existing F.1 guard) → **B** (comms core, the most-lifted piece) → **D** (the registry, the substantial build, depends on B's tree + the `HARNESS_ROLE` env contract) → **E** (launcher + hooks; D and E co-depend on the `HARNESS_ROLE` env contract, fixed in D.1) → **C/G/H** (docs; each gated by F) → **I** (optional UI) → **J** (the whole-scaffold validation + dry-run). **F.1 MUST land before A.2/A.3** (NOT merely "after Task Group A") — A.2's + A.3's acceptance checks require "the genericity guard passes," so the guard must exist first; this is why F.1 is sequenced after A.1 and before A.2 (the §2 group letters are for cohesion; the EXECUTION order is A.1 → F.1 → A.2 → A.3 → B → ...). F.2/F.3 (running it over the full tree + the build wiring) close at the end.

### 2.0 EXECUTION PRECONDITION (hard gate on the WHOLE task tree)

**DECISION A (repo name + location) and DECISION B (who runs `git init`, when) — §0.2 — are a HARD PRECONDITION for EVERY task below.** No task can run until the new repo exists, because every task's "Files (new repo)" line assumes a populated `<harness-template>` git root. The dependency is made unambiguous by splitting the tree:

- **Repo-bootstrap step (Task A.1):** creates the repo skeleton. Under option **B1** (recommended), the operator has already run `git init` on the empty repo and the executing implementer is dispatched pointed at it — A.1 populates it. Under option **B2**, A.1 itself runs `git init` as its first action. Either way, **A.1 is the boundary between "no repo" and "populated repo."**
- **Post-init implementation (Task B onward):** every subsequent task operates inside the now-populated repo (the implementer's own branch/worktree there). These tasks have NO meaning until A.1 has run.

So the ordering precondition chain is: **DECISION A + B (operator) → A.1 (repo-bootstrap) → all other tasks.** The executing dispatch states the resolved repo name/location + the chosen B-option in its brief; the implementer does NOT pick them.

### 2.1 The shipped-scaffold manifest (ONE exact file list) + a separate repository-support appendix

To avoid any accounting ambiguity, this section is ONE authoritative shipped-file list (matching the spec §4 manifest exactly), followed by a clearly-separated non-manifest appendix for the repository-support artifacts (tests + config). There is a SINGLE accounting model: a file is either **a §4 SHIPPED-MANIFEST file** OR **a repository-support artifact (appendix)** — nothing in between, no second "count."

**THE SHIPPED-SCAFFOLD MANIFEST (== the spec §4 list, EXACTLY — the operating surface a fresh CHARC uses):**

| # | Shipped file | Task |
|---|---|---|
| 1 | `README.md` | A.2 |
| 2 | `APPLICATION.md` | A.3 |
| 3 | `comms/.gitkeep` | A.1 |
| 4 | `scripts/role_mail.py` | B |
| 5 | `scripts/comms_ui.py` (the HTMX client is inlined as a string constant in this file by default — zero extra files) | I.1 |
| 6 | `scripts/launch_role.ps1` | E.1 |
| 7 | `.claude/settings.json` | E.2 |
| 8-10 | `.claude/hooks/user_prompt_submit.py` · `session_start.py` · `session_end.py` (the shared registry logic lives INSIDE `session_start.py`, imported by the other two — zero extra files) | D.1-D.4 |
| 11 | `.claude/agents/implementer-template.md` | C.3 |
| 12 | `docs/charc-charter.md` | H.1 |
| 13 | `docs/charc-bootstrap.md` (carries the orchestrator bring-up prompt as a step-5 fenced block — zero extra files) | H.2/H.3 |
| 14 | `docs/orchestrator-context.md` | C.1 |
| 15 | `docs/dispatch-recipe.md` | C.2 |
| 16 | `docs/review-gate-seam.md` | G.1 |
| 17 | `docs/codex-reviewer.md` | G.2 |
| 18 | `docs/comms-orchestrator-registry.md` | D.7 |

This is the §4 manifest (the spec's "~14" counting the comms/ root + the script/hook/agent/doc files; the count lands at these shipped files). **NO file outside this list is part of the scaffold surface.** Three implementation details are FOLDED into shipped files by default (the registry logic → `session_start.py`; the orchestrator bring-up → a `charc-bootstrap.md` section; the HTMX client → a string constant in `comms_ui.py`) so the DEFAULT build adds ZERO files beyond the list. (An implementer/CHARC MAY instead split any of the three into its own file — a named `registry.py`, a standalone `orchestrator_bootstrap.md`, a separate `htmx.min.js` — but that is an explicit, optional choice, NOT the shipped default; the default is the exact list above.)

**APPENDIX — repository-support artifacts (NOT scaffold-manifest files; tracked + guard-scanned):**
- `pyproject.toml` · `.gitignore` (a Python repo's standard config — task A.1).
- `tests/**` — the test modules + `tests/genericity_lists.py` (the guard's denylist constants) + the acceptance-spec `tests/*.md` walkthroughs. The spec §8 ("Testing") MANDATES this suite (comms round-trip, registry, bootstrap-dry-run, genericity guard). The genericity guard scans the tests too, EXCEPT `genericity_lists.py` + the planted-term fixtures are excluded from the SCAN (F.1).

These appendix artifacts are part of the deliverable REPOSITORY (every repo needs config + tests) but are NOT scaffold-manifest files — they are repository support, not the operating surface a fresh CHARC uses. **Every tracked file is either in the shipped-manifest list OR the support appendix — one accounting model, no dual count, no ambiguity.**

---

## TASK GROUP A — Repo skeleton, dependency posture, README

### A.1 — Repo skeleton + dependency manifest

**Files (new repo):**
- `<harness-template>/pyproject.toml` (or equivalent) — declares the package metadata; **core = zero hard runtime deps** (§4); a `[web]` optional extra = `fastapi`, `uvicorn[standard]`, `jinja2` (mirroring swing's `[project.optional-dependencies] web`). **NO `[dev]` test-runner dep** — the scaffold's tests run under stdlib `unittest` (the §8 guard forbids `pytest`; see §1 "Test substrate"); the only optional dev/test deps come transitively via `[web]` (FastAPI's `TestClient`).
- `<harness-template>/.gitignore` — generic version of swing's. **The comms-tree rule MUST use the ignore-glob + negation form so the anchor stays tracked:** `comms/*` (ignore all runtime mailbox + `sessions/` registry state) followed by `!comms/.gitkeep` (un-ignore the anchor). A bare directory-ignore `comms/` would ALSO ignore the `.gitkeep` child (a directory ignore cannot be negated for a contained path), defeating the tracked anchor — so the `comms/*` + `!comms/.gitkeep` two-line form is REQUIRED, not `comms/`. Also ignore the `.codex-*` / `.copowers-*` review/findings artifacts, `.worktrees/`, Python `__pycache__`/`*.pyc`.
- `<harness-template>/comms/.gitkeep` — the committed mailbox-root anchor (§4: "a committed `.gitkeep`; role inboxes + the orchestrator registry auto-create at first use"). Tracked because of the `!comms/.gitkeep` negation above.

**Acceptance check (TDD-equivalent):**
- A test (the dependency-posture test, runnable under `unittest`) proves the core is stdlib-only by **TWO complementary mechanisms** (so an in-function/lazy import cannot slip through — R11):
  1. **The strong runtime check (catches lazy imports):** run the core modules (`role_mail` + the hooks + `registry.py`) in a SUBPROCESS whose `sys.path` is stripped of site-packages (or under a sitecustomize that makes third-party packages unimportable), executing each module's full surface (import + a representative call) → it must succeed with ZERO third-party packages available. A lazy `import fastapi` inside a function WOULD fail here when that function runs, so the test exercises the core's public entry points, not just the module import. This is the real no-deps proof.
  2. **The AST belt (catches ALL import statements, not just top-level):** an AST walk over the core files collects EVERY `Import`/`ImportFrom` node anywhere in the file (module level AND inside functions/methods) and asserts each names only a stdlib module (against an allowlist of stdlib names). This catches a lazy import statically even if a test path doesn't execute it.
  - Together: the AST belt flags any third-party import statement anywhere; the subprocess check proves the core actually runs with no third-party packages present. Either alone is insufficient (top-level-only AST misses lazy imports — the R11 catch; subprocess-only misses an unexercised lazy path) — both ship.
- **The anchor-vs-runtime gitignore check (distinguishing):** `comms/.gitkeep` is actually TRACKED (committed) while a runtime mailbox file (`comms/charc/inbox/x.md`) is IGNORED. Mechanism — TWO assertions (R13): (1) the IGNORE-RULE behavior: `git check-ignore comms/charc/inbox/x.md` returns 0 (ignored) AND `git check-ignore comms/.gitkeep` returns non-zero (NOT ignored); (2) the actual TRACKING state: **`git ls-files --error-unmatch comms/.gitkeep` SUCCEEDS** (proves the anchor is committed/tracked — `check-ignore` alone only shows ignore-rule behavior, NOT committed tracking; an anchor that is unignored but never `git add`ed would pass (1) yet fail (2)). Together they prove the anchor is both unignored AND tracked, while runtime mailbox files stay ignored. This FAILS under a bare `comms/` ignore (which would ignore the anchor too) AND under a forgotten-to-commit anchor — both real failure modes.

**Commit:** `feat(scaffold): Task A.1 — repo skeleton, zero-hard-dep manifest, gitignored comms root`

### A.2 — README (operator-facing instantiation)

**Files:** `<harness-template>/README.md`.

**Content (acceptance checklist — §5.5):**
- What it is: a reusable empty multi-agent harness scaffold (Director / Orchestrator / Implementer model + file comms + self-bootstrap), application-agnostic.
- How to instantiate: copy the repo, adopt the `HARNESS_ROLE` env convention, launch CHARC.
- The germination one-liner: **"launch CHARC; it takes over."** (CHARC reads its charter, verifies comms, runs the application-definition interview that fills seams 1-3; seam 4 ships a tuned default.)
- A pointer to `docs/charc-bootstrap.md` (CHARC's literal first session) and `docs/charc-charter.md` (the kernel).
- The staged-guarantee note (§5.5): CHARC operation works on a bare clone; orchestrator+implementer operation works after the bootstrap's step-5 orchestrator bring-up.

**Acceptance check:** the README names all four seams, points at the kernel docs, and **passes the genericity guard** (Task F) — zero forbidden vocab, substrate terms only where allowed. (README is NOT a guard file-scope exception, so it must stay app/domain-clean and may name substrate terms only as the guard's allowed-substrate list permits — Claude Code, etc.)

**Commit:** `docs(scaffold): Task A.2 — README: what-it-is, instantiate, launch-CHARC`

### A.3 — `APPLICATION.md` stub (SEAM 1)

**Files:** `<harness-template>/APPLICATION.md`.

**Content:** a STUB (§3 seam 1, §4): a short marker doc — "CHARC defines the application here" — with the interview-fill placeholder structure (what the project does; its domain; success criteria) and an explicit note that it is empty-by-design until the bootstrap interview fills it. **No example app** (the §8 guard forbids chess/COA/trading even as an example).

**Acceptance check:** the stub contains the seam-1 marker, contains NO concrete application/domain content, and **passes the genericity guard** (this file is one the guard watches hardest — it must contain zero forbidden vocab AND zero placeholder example domain).

**Commit:** `docs(scaffold): Task A.3 — APPLICATION.md seam-1 stub`

---

## TASK GROUP B — The generic comms CLI (`role_mail.py`)

The single most-lifted piece. Swing's `role_mail.py` is **already generic** except the role taxonomy (§5.1). The lift is: change the role enums + strip swing-isms from docstrings/usage; everything else (the single write path, the atomic multi-recipient delivery, the `os.replace` same-dir temp, the ack-as-move inbox→read, the unique-path idempotency, the L1 information-vs-authority lock, the cp1252-safe `_ascii`) carries verbatim.

### B.1 — `role_mail.py` core: taxonomy + post/ack write path

**Files (new repo):** `scripts/role_mail.py`, `tests/test_role_mail.py` (or the chosen runner's path).

**The taxonomy change (§5.1):**
- `VALID_FROM = ("charc", "orchestrator", "operator")`
- `VALID_TO = ("charc", "orchestrator", "operator")` — **note: orchestrator IS a recipient here** (the scaffold ships the orchestrator inbox realized; swing's V1 had `orchestrator` send-only / not in `VALID_TO`). This is the spec-mandated divergence from swing (§5.1: "the orchestrator has an inbox … the scaffold ships the extension realized").
- `VALID_TYPES = ("fyi", "status", "query", "return_report", "decision_request")` — verbatim.

**TDD (red→green):**
1. Failing test: `post_message` with `--to charc` round-trips (post → file appears in `comms/charc/inbox/` with the frontmatter) → implement the taxonomy + the lifted write path → green.
2. Failing test: posting `--to orchestrator` succeeds (the new inbox recipient) — this test FAILS against a naive swing-copy where `orchestrator` is send-only, proving the divergence is implemented.
3. Failing test: the **L1 lock** — `decision_request` to any non-operator recipient (incl. `charc`, `orchestrator`) raises/exits-1; `decision_request` to `operator` succeeds. **This is a POLICY test on the EXISTING `VALID_TYPES` set (the information-vs-authority discipline), NOT a new semantic channel** — `decision_request` is one of the five existing types; the lock just restricts WHO it can address. No new message type / channel is introduced. (Distinguishing: compute under both the pre-fix path [no lock → write happens] and post-fix [refused] to prove the test bites.)
4. Failing test (DISTINCT from item 3): **the orchestrator-inbox accepts the info-only types but the discipline that briefs/approvals never route here is doc-enforced, not enum-enforced.** Assert the POSITIVE: `post_message` to `orchestrator` SUCCEEDS for each of `fyi`/`status`/`query`/`return_report` (the info-only taxonomy the orchestrator inbox is meant to carry — Stage-2 §6 "Taxonomy LOCK") and the file lands in `comms/orchestrator/inbox/`. This is distinct from item 3 (which asserts the NEGATIVE: `decision_request` to orchestrator is refused). Together items 3+4 fully characterize the orchestrator inbox: it carries the four info-only types, refuses `decision_request`. (The further "no briefs/approvals" rule is a human discipline stated in `dispatch-recipe.md` + `orchestrator-context.md`, NOT an enum — there is no message-type for "brief"; the L1 lock + the discipline doc together enforce info-only. No NEW enum needed.)

**Acceptance check (in addition to TDD green):** the file's module docstring + usage examples name only generic roles (charc/orchestrator/operator); **genericity guard passes** (no `swing`/`rd`/finance terms). Note the role `rd` is REMOVED (swing's research-director has no scaffold analog — §9 "one director"); a guard or grep asserts `rd` does not appear as a role.

**Commit:** `feat(comms): Task B.1 — generic role_mail taxonomy (charc|orchestrator|operator) + lifted write path`

### B.2 — `role_mail.py`: list / read / peek + ack-history-preservation

**Files:** `scripts/role_mail.py`, `tests/test_role_mail.py`.

**TDD (red→green):**
1. Failing test: `read --role <r> --all` drains the inbox (prints each, moves inbox→read), `list` shows unread+read counts, `peek` shows without acking → implement (lift verbatim) → green.
2. Failing test: **ack never overwrites history** — post two messages with the same stamp+sender+slug across an emptied inbox; assert the second ack lands as `-2.md` in `read/` (the `_unique_dest` suffix), nothing deleted.
3. Failing test: traversal rejection — `ack_message` with a non-basename filename (`../x`) is refused (L3 mail-custody lift).

**Acceptance check:** guard passes; ASCII console output preserved (a test posting a non-ASCII subject still `list`s without crashing — the `_ascii` backslashreplace).

**Commit:** `feat(comms): Task B.2 — list/read/peek + ack history-preservation + traversal guard`

### B.3 — `role_mail.py`: the atomic multi-recipient delivery + frontmatter-injection guard

**Files:** `scripts/role_mail.py`, `tests/test_role_mail.py`.

**TDD (red→green):**
1. Failing test: a multi-recipient post (`--to charc,orchestrator`) delivers all-or-nothing — both inboxes get the message; a simulated mid-delivery `os.replace` failure rolls back so NEITHER is left (the staged-temps-then-replace pattern; mock the failure). Distinguishing: under a naive per-recipient-write loop the failure leaves a partial; the test asserts zero partials.
2. Failing test: CR/LF in `subject`/`thread` is rejected (frontmatter injection) — nothing written.

**Acceptance check:** guard passes.

**Commit:** `feat(comms): Task B.3 — atomic multi-recipient delivery + frontmatter-injection guard`

### B.4 — `role_mail.py`: peer-director-add checklist note (forward seam)

**Files:** `scripts/role_mail.py` (docstring/comment only) + cross-ref in `docs/charc-charter.md` (authored in H.1; this task just reserves the note).

**Content (§5.1 "adding a peer director later"):** a comment block enumerating the small set a future peer-director add touches — `VALID_FROM`/`VALID_TO` (the role sets), the new inbox (auto-creates), the charter routing/custody + authority note, optionally a launcher default. Stated as a checklist, NOT built (§9: one director ships).

**Acceptance check:** the comment exists, names the enumerated touch-set, and does NOT introduce a second role into the enums (assert `VALID_TO` still has exactly the three roles). Guard passes.

**Commit:** `docs(comms): Task B.4 — peer-director-add checklist note (not built; §9 one-director)`

---

## TASK GROUP C — The three role-protocol docs + dispatch-recipe

These are lift-and-genericize of swing's `tool-director-context.md` (→ the charter, in H.1), `orchestrator-context.md` (→ `orchestrator-context.md`), and `implementer-dispatch-recipe.md` (→ `dispatch-recipe.md`). The charter is the KERNEL and is built in Task Group H with the bootstrap; this group builds the orchestrator-context + dispatch-recipe + the generic implementer-template cell.

### C.1 — `docs/orchestrator-context.md` (generic operating model)

**Files:** `<harness-template>/docs/orchestrator-context.md`.

**Content (acceptance checklist — §5.2):** the generic orchestrator operating model, STRIPPED of all swing arc/phase content:
- Role + operating pattern: coordinate implementers; the dispatch model (brief → inline/sub-agent dispatch → return report → QA → accept); **operator drives, orchestrator serves**.
- QA-the-implementer-product (don't trust the self-report; verify against reality).
- Own the **merge/accept** step (the orchestrator performs the accept across phases).
- The comms routing: the orchestrator HAS an inbox now (the scaffold realizes it); it posts status/return_report to CHARC; it receives direction from the operator; **the implementer never posts to a mailbox** (reports up in chat) — a discipline, not an enum.
- A pointer to `dispatch-recipe.md` (the implementer protocol) + `review-gate-seam.md` (the review/gate contract).
- The concurrent-generations note + a pointer to `comms-orchestrator-registry.md` (the registry is what makes "which orchestrator" addressable).

**Acceptance check:** the doc contains ZERO swing arc/phase content (no Phase-N, no finance, no schema); it names the orchestrator-inbox-realized model (NOT swing's "no orchestrator inbox in V1"); **genericity guard passes** (substrate terms allowed only per the guard's lists — note: this doc is NOT a substrate-exception file, so it must stay mechanism-agnostic about review tooling, deferring to seam 3).

**Commit:** `docs(scaffold): Task C.1 — generic orchestrator-context (operating model, orchestrator-inbox-realized)`

### C.2 — `docs/dispatch-recipe.md` (generic implementer protocol, no source-code assumption)

**Files:** `<harness-template>/docs/dispatch-recipe.md`.

**Content (acceptance checklist — §5.2, **Major-4 resolution**):** the implementer protocol framed around four GENERIC concepts, **no hard source-code assumption**:
- **Isolated workspace** — parallel implementers don't collide. The substrate's COMMON instantiation (a git **worktree** at `.worktrees/<name>`, branched from the base) is named as the **default on this substrate**, NOT assumed; a non-source-code domain supplies its own isolation mechanism.
- **A product** — whatever the cell produces (code, a plan, a doc, an artifact).
- **Validation evidence** — the build cycle: produce → validate → converge (the domain's equivalent of red-green-refactor).
- **Acceptance transfer** — the return-report back to the orchestrator. The substrate default (a **diff/merge** for acceptance) is named as the default, NOT assumed.
- The carry-over disciplines: honor the brief's locks; STOP-and-ask on a premise mismatch; ground-don't-guess; the **review-to-convergence loop pointing at seam 3** (NOT at Codex — Codex is one optional reviewer, named in `codex-reviewer.md`, plugged into seam 3); the implementer reports up in chat, never to a mailbox.
- **EXCLUDED from this generic recipe:** the software-specific gate bits (any test-runner/lint specifics, the Codex transport) — those live in **seam 3** (`review-gate-seam.md`) + the optional `codex-reviewer.md`. The recipe references the seam, never names the mechanism.

**Acceptance check:** the doc frames isolation/product/validation/acceptance generically; the worktree + diff/merge are named explicitly as *substrate defaults* (NOT as universal requirements); NO test-runner/lint/Codex mechanism appears in the protocol body. **Genericity guard:** this doc has a **file-scope exception** for the substrate-default NOTE (it may name git/worktree/WSL/Windows as the substrate default — §8 exception list) but must NOT name a domain mechanism elsewhere.

**Commit:** `docs(scaffold): Task C.2 — generic dispatch-recipe (isolated workspace / product / validation / acceptance; substrate defaults named, not assumed)`

### C.3 — `.claude/agents/implementer-template.md` (SEAM 2 — ONE generic cell)

**Files:** `<harness-template>/.claude/agents/implementer-template.md`.

**Content (acceptance checklist — §3 seam 2, §4):** ONE generic implementer cell template, modeled on swing's `implementer-<model>-<effort>.md` shape:
- Frontmatter: `name`, `description` (TASK-reasoning-density framing, not phase), `tools`, `model`/`effort` placeholders (the operator/CHARC tunes per-cell — seam 4-adjacent).
- Body: "You are a dispatched implementer for `<this harness's application>`. FIRST read `docs/dispatch-recipe.md` in full — it is your dispatch protocol. Then read your dispatch brief and execute it. Your FINAL message is the structured return report to the orchestrator — never post to a role mailbox."
- A marker that CHARC authors domain-tuned cells FROM this template at bootstrap (seam 2 fill).

**Acceptance check:** the cell points at `dispatch-recipe.md`, carries the never-post-to-mailbox discipline, names NO application (uses `<application>` placeholder), and **passes the genericity guard**.

**Commit:** `feat(scaffold): Task C.3 — implementer-template.md (seam-2 generic cell)`

### C.4 — (folded) — *No separate task; the charter (the third protocol doc) is Task Group H.* 

*(The §5.2 "three generic role protocols" = charter [H.1] + orchestrator-context [C.1] + dispatch-recipe [C.2]. The charter ships with the bootstrap in H because the kernel = charter + bootstrap, §3.)*

---

## TASK GROUP D — Orchestrator inbox + session registry (THE substantial build)

Built from `docs/comms-stage2-orchestrator-inbox-design.md` (promoted from deferred spec to built infrastructure — §5.1). The registry is **one-file-per-session** under `comms/sessions/<session_id>.json` (the no-shared-file-read-modify-write pattern from the Stage-2 design §2, which avoids the `.sessions.json` concurrency hazard swing's launcher has). Three lifecycle hooks consume the documented hook-JSON `session_id`.

**The env contract (fix here, consumed by E):** the registry's role arrives as the launch-time **`HARNESS_ROLE`** env var (renamed from swing's `SWING_ROLE` — §5.1). The hook reads it; the launcher sets it. Role-gated registration: **only `orchestrator` sessions register** (Stage-2 §3 role-gated; the unread-notice hook also gates on the role).

### D.1 — Registry module: data shape + write/read/prune (pure, testable)

**Files (new repo):** the shared registry logic + `tests/test_registry.py`. **DEFAULT placement (zero extra files): the write/touch/prune/read logic lives INSIDE `session_start.py` (one of the three §4 hook files) and is imported by the other two hooks** (`from session_start import write_entry, ...`) — so NO file beyond the §4 hook slot is added. The named `.claude/hooks/registry.py` helper is an OPTIONAL alternative the implementer may choose for cleaner separation/testability — but it is NOT the default and NOT a new manifest line either way (it sits in the §4 `*.py` hook slot). Either placement is spec-faithful; the default adds zero files.

**Data shape (Stage-2 §2):** `comms/sessions/<session_id>.json` = `{ session_id, role, transcript_path, started_ts, last_seen }`. **Staleness threshold:** a module constant `STALE_SECONDS` — the spec §11 open sub-decision says "30-60 min; tune at build." **Plan decision: default `STALE_SECONDS = 45 * 60` (45 min)**, a single named constant the operator/CHARC can tune (flagged as a tunable starter, like seam 4). The format is JSON one-file-per-session (NOT a shared map).

**TDD (red→green):**
1. Failing test: `write_entry(root, session_id, role, transcript_path, now)` creates `comms/sessions/<id>.json` with all five fields; `read_entries(root)` returns it → implement → green.
2. Failing test: `touch_last_seen(root, session_id, now)` updates only `last_seen` (heartbeat), leaves the rest; **recreate-if-missing** — if the file was pruned, `touch`/refresh rebuilds the FULL entry (the hook owns the full entry; needs role from env) → green. (Distinguishing: a naive "update only" leaves no file if pruned; the test asserts the file is rebuilt.)
3. Failing test: `prune_stale(root, now, STALE_SECONDS)` deletes entries whose `last_seen` age > threshold, keeps fresh ones; returns the pruned ids → green.
4. Failing test: a malformed/garbage `sessions/<id>.json` is skipped (read returns the good entries, never raises) — the degrade-gracefully posture.

**Acceptance check:** the module is stdlib-only (the dependency-posture test from A.1 covers it); guard passes; `STALE_SECONDS` is a single named constant.

**Commit:** `feat(registry): Task D.1 — session-registry data shape + write/touch/prune (stdlib, recreate-if-missing, malformed-safe)`

### D.2 — `UserPromptSubmit` hook: heartbeat + role-gated register + recreate-if-missing + the unread notice

**Files:** `.claude/hooks/user_prompt_submit.py`, `tests/test_user_prompt_submit_hook.py`.

**Contract (§5.1 + Stage-2 §2 table + the unread-hook lift):**
- Reads the hook-JSON from stdin → extracts `session_id` + `transcript_path` (the documented fields — Stage-2 §8). Reads `HARNESS_ROLE` from env.
- **Heartbeat + register:** on EVERY prompt, if `HARNESS_ROLE == "orchestrator"`, write/refresh the registry entry (heartbeat `last_seen`; recreate-if-missing rebuilds the full entry from env+payload) — **role-gated** (only orchestrators register).
- **The unread notice (the swing lift):** the same hook ALSO surfaces unread mailbox count for the session's role (charc OR orchestrator) — one ASCII `[comms] N unread … run: <drain cmd>` line, decision_request subset noted. Silent no-op if the role is unknown / not in the comms roles. ALWAYS exits 0 (a hook failure must never block a prompt — swallow all exceptions).
- **Degraded mode (§5.1 Major-6 / Stage-2 §8):** if `session_id` is ABSENT from the payload (a substrate-version change), the registry degrades to a documented single-orchestrator assumption + logs an actionable warning to stderr — never silently mis-keys; a last-resort fallback to the undocumented session env var is permitted but logged as degraded.

**TDD (red→green):**
1. Failing test: a JSON payload with `session_id`+`transcript_path` and `HARNESS_ROLE=orchestrator` → the registry entry is written/refreshed → green.
2. Failing test: `HARNESS_ROLE=charc` (a director, not orchestrator) → NO registry entry written (role-gated), but the unread notice still fires for `charc` → green. (Distinguishing: a register-everyone impl writes a charc entry; the test asserts none.)
3. Failing test: a payload with NO `session_id` → degraded mode (a warning to stderr; no crash; exit 0; the documented single-orchestrator fallback) → green.
4. Failing test: an internal exception (e.g. unreadable comms dir) → exit 0, prompt never blocked.
5. Failing test: the unread notice — N messages in `comms/orchestrator/inbox/` → the `[comms] N unread for orchestrator …` ASCII line printed.

**Acceptance check:** ALWAYS exits 0; degraded mode logged not silent; guard passes (`HARNESS_ROLE` not `SWING_ROLE`; no `rd`).

**Commit:** `feat(registry): Task D.2 — UserPromptSubmit hook (heartbeat + role-gated register + recreate-if-missing + degraded-mode + unread notice)`

### D.3 — `SessionStart` hook: create entry + opportunistic prune

**Files:** `.claude/hooks/session_start.py`, `tests/test_session_start_hook.py`.

**Contract (Stage-2 §2 table):** on `SessionStart` (fires + completes BEFORE the first prompt): if `HARNESS_ROLE == "orchestrator"`, **create** the entry (from `session_id`/`transcript_path` + env role). Carries a `source` field (`startup`/`resume`/`clear`/`compact`) — on `resume`, refresh the existing same-`session_id` entry rather than duplicate. ALSO run the **opportunistic prune** (new session prunes stale entries on entry). Exit 0 always.

**TDD (red→green):**
1. Failing test: `SessionStart` with `source=startup`, orchestrator role → entry created → green.
2. Failing test: `source=resume`, same `session_id` already present → refreshed not duplicated (one file, updated `last_seen`) → green.
3. Failing test: a pre-existing stale entry → pruned on this SessionStart (opportunistic prune) → green.
4. Failing test: non-orchestrator role → no entry created, prune still runs → green.

**Acceptance check:** prune runs regardless of role; create is role-gated; exit 0; guard passes.

**Commit:** `feat(registry): Task D.3 — SessionStart hook (create entry + opportunistic prune; resume-refresh-not-duplicate)`

### D.4 — `SessionEnd` hook: best-effort idempotent tidy

**Files:** `.claude/hooks/session_end.py`, `tests/test_session_end_hook.py`.

**Contract (Stage-2 §2 table):** `SessionEnd` (the termination hook — NOT `Stop`, which fires per-turn): best-effort idempotent tidy-delete of this session's entry. Correctness does NOT depend on it firing (the prune + liveness handle crashes/window-close). Idempotent: deleting an already-gone entry is a no-op, never raises. Exit 0.

**TDD (red→green):**
1. Failing test: `SessionEnd` deletes `comms/sessions/<id>.json` → green.
2. Failing test: `SessionEnd` on an already-pruned entry → no-op, no raise, exit 0 (idempotent).

**Acceptance check:** idempotent; exit 0; guard passes.

**Commit:** `feat(registry): Task D.4 — SessionEnd hook (best-effort idempotent tidy)`

### D.5 — Addressing + claim semantics (shared inbox + atomic-move claim)

**Files:** `tests/test_orchestrator_claim.py` (behavior over `role_mail` + the registry; no new module — this asserts the EXISTING atomic-move ack is the claim mechanism), and a doc contribution to `docs/comms-orchestrator-registry.md` (authored in D.7).

**Contract (§5.1 Major-1 resolution):**
- Messages to `orchestrator` land in a single shared `comms/orchestrator/inbox` (the **shared-inbox default**).
- The existing **atomic inbox→read move** (the `role_mail` ack, `src.rename(dest)`) is the claim rule: two live sessions cannot double-drain — one wins the rename, the other sees it gone (the `MailError` "no inbox message named …").
- "Current orchestrator" = the **newest-live** registry entry (by `started_ts` among non-stale entries).
- **The concurrent-generation HANDOFF-WINDOW rule (§5.1 — decomposed explicitly, R6):** in the rare window where an OUTGOING generation overlaps an INCOMING one, the OUTGOING generation **stops draining the shared `orchestrator` inbox once the incoming generation registers** (operator-mediated retirement, as in swing — the operator relays "the new generation is up" and retires the old one). This is a DISCIPLINE (a documented operating rule), NOT a code lock — there is no auto-fence; the registry's `newest_live` + the atomic-move claim make a stray double-drain HARMLESS (one wins the rename) even if the discipline lapses. The rule + its registry-state tie (the incoming entry becomes `newest_live` at its first register; the operator retires the outgoing) is documented in `comms-orchestrator-registry.md` (D.7) and named in `orchestrator-context.md` (C.1, the concurrent-generations note).

**TDD (red→green):**
1. Failing test: two simulated drains of the same orchestrator-inbox message — only ONE succeeds; the second gets the friendly already-gone path (no double-process). (This is the atomic-move claim; the test proves the ack's `rename` is the dedupe — and that a handoff-window double-drain is harmless.)
2. Failing test: `newest_live(root, now)` returns the most-recent-`started_ts` non-stale orchestrator entry; returns None when all are stale. (This is the "current = newest-live" selection the handoff rule keys on — the incoming generation becomes `newest_live` at register.)

**Acceptance check (incl. the handoff rule):** no new write path (the claim IS the existing atomic move — assert it, don't reimplement); the handoff-window stop-draining rule is DOCUMENTED in D.7 + C.1 (a discipline, with the registry-state transition — incoming-registers → becomes newest-live → operator retires outgoing — stated) and the double-drain-harmless property is the code backstop (test 1); guard passes.

**Commit:** `feat(registry): Task D.5 — shared-inbox addressing + atomic-move claim + newest-live + handoff-window stop-draining rule`

### D.6 — Self-heal integration (live-but-idle prune → re-register on next prompt)

**Files:** `tests/test_registry_selfheal.py`.

**Contract (Stage-2 §2 "Self-healing"):** a live-but-idle session pruned during a quiet period re-registers on its NEXT prompt (the D.2 `UserPromptSubmit` recreate-if-missing). End-to-end test of the self-heal: register → prune (simulate overnight) → a fresh `UserPromptSubmit` → entry rebuilt with the full shape.

**TDD (red→green):**
1. Failing test: register orchestrator → `prune_stale` removes it → a `UserPromptSubmit` payload for the same `session_id` → the entry is rebuilt (full five fields, fresh `last_seen`).

**Acceptance check:** the rebuilt entry carries the role (proving the hook owns the full entry via env, not a model-written token — Stage-2 §3); guard passes.

**Commit:** `test(registry): Task D.6 — self-heal: idle-prune then re-register on next prompt`

### D.7 — `docs/comms-orchestrator-registry.md` (the design doc — built, not deferred)

**Files:** `<harness-template>/docs/comms-orchestrator-registry.md`.

**Content (acceptance checklist — §4, §5.1):** the orchestrator-inbox + session-registry design, as BUILT (the realized version of swing's deferred Stage-2 spec):
- The registry file format (one-file-per-session, the five fields, `STALE_SECONDS=45min` default, the tune-at-build note).
- Liveness = the hook-written `last_seen` heartbeat; opportunistic prune (reader-as-cleaner + SessionStart); no daemon.
- Role-gated registration via `HARNESS_ROLE`; recreate-if-missing self-heal; the three hooks' contracts; the `SessionEnd` best-effort idempotent tidy.
- The hook `session_id` contract + the degraded mode (the required fields; what happens if `session_id` is absent; the logged-degraded last-resort env fallback).
- Addressing: **shared-inbox default** + the atomic-move claim rule; per-generation addressing (`orchestrator-<session_id>`) documented as the first-class upgrade the registry enables (DECISION C).
- **The concurrent-generation handoff-window rule (§5.1):** the outgoing generation stops draining once the incoming registers (operator-mediated retirement); the registry-state transition (incoming-registers → becomes `newest_live` → operator retires outgoing); the double-drain-harmless backstop (the atomic-move claim makes a lapse benign).
- The grounding facts (documented vs observed — Stage-2 §8): `session_id` documented; `CLAUDE_CODE_SESSION_ID` observed-only (last-resort fallback); no external live-session enumeration (the registry IS the enumeration).

**Acceptance check:** the doc fully specifies the built registry (not "deferred"); names both addressing options + the claim rule + the handoff-window stop-draining rule; **genericity guard passes** (substrate terms — Claude Code, hook event names — are allowed per the guard's substrate list; `swing`/`rd` absent).

**Commit:** `docs(registry): Task D.7 — comms-orchestrator-registry.md (the built design: registry, hooks, claim, addressing, degraded mode)`

---

## TASK GROUP E — The launcher + hooks wiring

### E.1 — `scripts/launch_role.ps1` (role-parameterized launcher; charc + orchestrator)

**Files (new repo):** `scripts/launch_role.ps1`, `tests/test_launch_role.ps1.md` (an acceptance-spec doc; PowerShell isn't unit-tested in the core runner — the acceptance is the `-DryRun` evidence + a content checklist).

**Content (§5.1, lift of `start_directors.ps1`, genericized):**
- `param([ValidateSet('charc','orchestrator','both')][string]$Role='both', [switch]$Resume, [switch]$NoWT, [switch]$DryRun)` — **roles are charc + orchestrator** (NOT swing's charc+rd). The launcher launches BOTH charc AND orchestrator sessions (§4: "launches BOTH charc AND orchestrator sessions").
- Sets **`HARNESS_ROLE=<role>`** in the spawned shell (the load-bearing env-inheritance fix: set it INSIDE the spawned shell via the EncodedCommand blob so the role reaches the hook regardless of how the window was spawned — swing's env-inheritance gotcha carries verbatim; the `;`-as-tab-delimiter EncodedCommand robustness fix carries verbatim). **The single shipped spawn path is the plain `powershell -NoExit` role window** — the spec-faithful §8 choice (PowerShell + Windows are in the §8 allowed-substrate list; `wt.exe` is not, so it is NOT lifted into the scaffold) per F.1(d). No bifurcation: one launcher surface, §8-clean.
- The model/effort default (**SEAM 4**): ships a working `--model`/`--effort`/`--permission-mode` default (a tuned starter, NOT a bootstrap blocker; the operator tunes anytime). The plan ships a sensible generic default (e.g. `--permission-mode auto` + a model/effort the operator sets) clearly marked SEAM-4-tunable.
- Preflight: verify the `claude` CLI + the flags it uses against `--help` (the verify-don't-assume lift), throw on a missing flag.
- Bootstrap-prompt dispatch: fresh mode reads the role's bootstrap file (`charc-bootstrap.md` for charc; an orchestrator bootstrap for orchestrator) and dispatches "read and follow it." Resume mode reopens the recorded named session (resume-by-display-name, the `-n`/`--resume` lift).
- **Registry interaction:** unlike swing's launcher (which wrote the non-concurrency-safe `.sessions.json`), this launcher does NOT own the registry — the **hooks** own it (the one-file-per-session registry is hook-written; §5.1). The launcher's job is to set `HARNESS_ROLE` so the hook can register. (This is a deliberate divergence from swing: the launcher's `.sessions.json` becomes the hook-owned `comms/sessions/` tree. The launcher may still keep a display-name map for resume, but it is NOT the liveness registry.)

**Acceptance check (`-DryRun` evidence + checklist):**
- `-DryRun -Role charc` and `-Role orchestrator` each print the computed `claude` command + the EncodedCommand spawn, set `HARNESS_ROLE` inside the inner command, and exit WITHOUT launching.
- The preflight verifies the flags it uses.
- **Genericity guard:** `launch_role.ps1` uses `HARNESS_ROLE` (not `SWING_ROLE`), roles charc/orchestrator (not rd). The single shipped spawn path is the plain `powershell -NoExit` window — PowerShell + Windows are in the §8 allowed-substrate list, `wt.exe` is NOT lifted (F.1(d)), so the launcher is §8-clean with no spec amendment. The guard passes over it as-is.
- The seam-4 model/effort default is clearly marked tunable.

**Commit:** `feat(launcher): Task E.1 — launch_role.ps1 (HARNESS_ROLE, charc+orchestrator, hooks-own-the-registry, seam-4 model/effort default)`

### E.2 — `.claude/settings.json` (hook registration — the three hooks)

**Files:** `<harness-template>/.claude/settings.json`.

**Content (§4, lift of swing's minimal-tracked-file pattern):** register the three hooks — `UserPromptSubmit` → `user_prompt_submit.py`, `SessionStart` → `session_start.py`, `SessionEnd` → `session_end.py`. Use a **relative or env-resolved path** (swing hard-codes an absolute `C:/Users/rwsmy/...` path; the scaffold must NOT — it ships to other machines). **Plan decision:** use a path resolved relative to the repo root (the hook command form Claude Code supports), OR document a one-line operator edit to point at the clone location. The acceptance check verifies the path is NOT a swing-machine-specific absolute path.

**Acceptance check:**
- All three hook events registered, each pointing at the matching hook script.
- The hook command path is portable (NOT a hard-coded `C:/Users/rwsmy/swing-trading/...` path). If Claude Code requires an absolute path, ship a placeholder + a documented operator substitution in README/bootstrap; the acceptance check asserts a placeholder marker, not a real machine path.
- **Genericity guard passes** (no `swing-trading` in the path).

**Commit:** `feat(scaffold): Task E.2 — .claude/settings.json (three hooks registered, portable path)`

### E.3 — Hooks portability + env-gate verification (integration)

**Files:** `tests/test_hooks_wiring.py`.

**Content:** an integration acceptance that the three hook scripts (a) resolve the comms root from `__file__` (NOT cwd — the swing lift; the recovery-command-from-any-cwd discipline), (b) read `HARNESS_ROLE` from env, (c) consume stdin JSON, (d) all exit 0 on any internal error.

**TDD (red→green):**
1. Failing test: each hook resolves the comms root from `__file__` and works when invoked from an arbitrary cwd → green.
2. Failing test: each hook exits 0 even on a malformed stdin payload.

**Acceptance check:** guard passes; no cwd-dependence.

**Commit:** `test(scaffold): Task E.3 — hooks portability (file-relative root, HARNESS_ROLE, stdin, always-exit-0)`

---

## TASK GROUP F — The genericity guard (the §8 grep build test)

**The spine.** F.1 (the test + its three lists) is authored EARLY — **immediately after A.1 and BEFORE A.2/A.3** (whose acceptance checks require the guard to pass) — so every content task, starting with the README + APPLICATION stub, is written against an existing guard. F.2/F.3 close it (run over the full tree + wire it into the build). Listed here as a group for cohesion, but **F.1 executes at A.1→F.1→A.2 in the §2 execution order** (NOT after the whole of Group A).

### F.1 — The genericity-guard test + the three explicit lists

**Files (new repo):** `tests/test_genericity_guard.py` + `tests/genericity_lists.py` (the three lists as module constants). **The list file holds the forbidden vocabulary as data, so it MUST be excluded from the scan target** (see the scan-scope acceptance below) — else the guard trips on its own denylist.

**Content (§8, Major-7 resolution — three explicit lists):**
- **(a) Forbidden vocabulary — the SPEC's exact set, PLUS the implementer's concrete enumeration of the spec's one open class ("finance tickers"). The split is labeled so nothing masquerades as a spec term.**
  - **The SPEC §8 literal forbidden set (verbatim, shipped as-is):** `swing`, `trading`, `finviz`, `schwab`, `sqlite`, `pytest`, `ruff`, `chess`, `coa`, `course-of-action` (+ `course of action`), and the class **"finance tickers."** These are the binding terms; the guard enforces exactly these.
  - **The CLOSED, AUTHORITATIVE realization of the spec's "finance tickers" CLASS (a fixed denylist with stable matching — NOT an approximation):** because a build test cannot match an unbounded class, the guard realizes "finance tickers" as a CLOSED, fixed constant in `tests/genericity_lists.py` — the named swing benchmark/universe tickers (`SPY`, `QQQ`, `NDX`, `SPX`, `RUT`) + the finance vocabulary `trade`/`trading`/`finance`/`ticker`/`yfinance`. **This list IS the authoritative guard contract as shipped — a single, closed, buildable denylist with the stable matching rule below; it is not "approximate" and is not editable-at-will.** (Like any tracked denylist it can be amended over the repo's life via a normal versioned change — but the SHIPPED list is the fixed, complete contract; the plan does not leave the matching open or defer it.) See the bounded-class rationale below for WHY this closed list is the complete, deterministic realization of §8's intent.
  - **`htmx`/`fastapi`/`jinja2`/`uvicorn` are NOT forbidden and were NEVER in the spec §8 list.** The spec §8 set above does not include them; `htmx` appears in spec §3 only as "the generic CORE is not COUPLED to HTMX," and the spec §4 explicitly SHIPS an htmx UI (`comms_ui.py`) in the `[web]` extra — so forbidding htmx would CONTRADICT the spec. Keeping these generic web libraries OFF the denylist is spec-fidelity. The list lives as a module constant in `tests/genericity_lists.py` (auditable + amendable); the executing implementer may EXTEND it (with a comment) but never leave it a vibe.
- **The "finance tickers" class (spec §8) — DELIBERATELY BOUNDED to the concrete swing-residue set; NO fuzzy uppercase-symbol matcher (a deterministic decision; the adjudication is grounded in §8's own stated PURPOSE, not convenience).** The spec §8 names "finance tickers" as forbidden. **The CONTAMINATION SURFACE this guards is bounded by the spec's own design:** the scaffold is **Approach A — authored clean-room, ZERO swing residue, zero swing git history** (spec §2). The ONLY vector by which a finance ticker could leak into an authored-fresh generic scaffold is a swing-residue copy-paste (an extracted artifact still carrying a swing ticker). That vector is FINITE + enumerable: the swing benchmark/universe tickers the extraction could carry. So the deterministic, COMPLETE coverage of the actual contamination surface is the named swing tickers (`SPY`, `QQQ`, `NDX`, `SPX`, `RUT` + any ticker the executing implementer's grep of the swing reference corpus surfaces) + the vendor/domain terms already enumerated. **A universal uppercase-symbol detector is REJECTED — and not merely for convenience:** the set of all tickers is unbounded (every 1-5-letter uppercase token), so such a matcher produces UNBOUNDED FALSE POSITIVES (it trips on `README`, `HTTP`, `JSON`, `CHARC` itself) — making the guard non-deterministic AND unusable, which would DEFEAT §8's purpose (a guard that cries wolf on every acronym gets disabled). The closed swing-residue set is therefore the faithful AND deterministic realization of §8's INTENT ("zero application contamination" = no SWING content; spec §1 + §10) — it COMPLETELY covers the real contamination surface (because the scaffold is authored CLEAN-ROOM, the only ticker-leak vector IS a swing-residue copy, which the named-ticker set + the swing-corpus grep fully enumerate) with zero false positives. This is the single, fixed guard contract the plan ships — a closed `tests/genericity_lists.py` denylist with the stable word-boundary matching rule (below). **A universal finance-symbol matcher is definitively REJECTED in the contract** (not deferred): it is unbounded (every uppercase token) → unbounded false positives (`README`/`HTTP`/`JSON`/`CHARC`) → non-deterministic + unusable → would DEFEAT §8 (a cry-wolf guard gets disabled). So the closed list is not an approximation of an ideal matcher — for the clean-room contamination surface it IS the complete matcher. (CHARC owns the guard's contract as harness architecture, so a future list amendment routes through CHARC like any §8 change — but the SHIPPED contract is fixed + closed, with no per-round re-litigation of the matching rule.)
- **False-positive handling (the matcher semantics):** the guard matches each term with word boundaries (`\bterm\b`, case-insensitive) so `swing` does not match inside an unrelated word; the bounded tickers (`SPY` etc.) are matched case-SENSITIVE-as-uppercase-whole-words to avoid tripping on lowercase English (`spy` the verb); a few terms are common English (`trade`, `trades`) — for those the executing implementer reviews each hit (the scaffold has no legitimate use of `trade`, so a hit is a real leak).
- **(b) Allowed substrate vocabulary** — permitted because the scaffold is substrate-coupled: `Claude Code`, `WSL`, `Windows`, `PowerShell`, `Codex`, `git` (the spec §8 list, verbatim). These do NOT fail the build (they are the same-substrate constraint, §1).
- **(c) File-scope exceptions — EXACTLY the spec §8 two named locations, no more.** Codex/WSL/git substrate VOCABULARY is ALLOWED only in `docs/codex-reviewer.md` + the substrate-default NOTE of `docs/dispatch-recipe.md`. **`docs/review-gate-seam.md` gets NO exception and contains NO substrate token at all** (no substrate word AND no substrate-named path — it does not reference `codex-reviewer.md`; the §5.3 pointer is carried by the dispatch-recipe + the bootstrap, see G.1). The test enforces the per-file scoping: a substrate token (word OR a substrate-named filename like `codex-reviewer.md`) appearing in `review-gate-seam.md` is a FAILURE; substrate tokens appear ONLY in the two spec-§8-named locations; everywhere else they are a failure.
- **(d) The `launch_role.ps1` spawn path — an IMPLEMENTATION CHOICE the plan makes within the spec, NOT a spec exclusion of wt.exe.** The spec does NOT say "wt.exe is forbidden"; it lifts the swing launcher generically and fixes the §8 allowed-substrate list (b) = `{Claude Code, WSL, Windows, PowerShell, Codex, git}` — which blesses PowerShell + Windows but does not NAME `wt.exe`. Given that, the plan makes a concrete IMPLEMENTATION CHOICE: ship a single spawn path = a plain `powershell -NoExit` role window (the swing launcher's existing `-NoWT` behavior, promoted to the default). **This is a plan-level implementation choice, not a claim that the spec excludes wt.exe** — it keeps the launcher inside the §8 allowed-substrate list with zero un-blessed tokens, so the launcher ships guard-clean and the plan stays deterministic. The swing launcher's wt.exe-tab path is simply not lifted by this choice. **If the operator/CHARC prefers the Windows-Terminal-tab surface, that is a fully reasonable alternative — it just requires CHARC to add `wt.exe`/Windows Terminal to the §8 allowed-substrate list (a small amendment, since the launcher is an explicitly-accepted Windows substrate lift) + scope it to `launch_role.ps1`. The plan ships the plain-window choice by default + flags the wt.exe alternative as a one-line CHARC call.** (The `EncodedCommand` env-inheritance robustness fix from swing applies to the plain-window path too.) Because the default ships no `wt.exe` token, the guard's denylist need not mention wt.exe at all — there is no guard-vs-launcher contradiction.

**TDD (red→green) — the test must DISTINGUISH:**
1. Failing test: plant a forbidden term (`swing`) in a temp tracked-tree fixture → the guard FAILS (reports the file+term). Remove it → passes. (The guard's own self-test, run over a fixture tree, proves it catches a hit.)
2. Failing test: a substrate term (`Codex`) in `review-gate-seam.md`'s protocol section → FAILS (out-of-scope); the SAME term in `codex-reviewer.md` → passes (in-scope exception). This proves the file-scoping works.
3. Failing test: an allowed substrate term (`WSL`) in a normally-substrate-OK file → passes (does not false-fail).
4. **Failing test (the self-exclusion — distinguishing): the guard, run over the REAL tree, must NOT trip on its OWN list file** `tests/genericity_lists.py` (which CONTAINS every forbidden term as data). The test asserts the scan EXCLUDES `tests/genericity_lists.py` (and any fixture file that plants forbidden terms for test 1) → green. A naive guard that scans the list file WOULD fail (its denylist contains `swing` etc.) — so this test FAILS against a guard with no self-exclusion, proving the exclusion is present + correct.

**Two DISTINCT scoping concepts — kept separate so the guard matches the spec §8 model exactly:**
- **The spec §8 file-scope EXCEPTIONS (content scoping — the ONLY substrate-vocab exceptions):** substrate terms (Codex/WSL/git) are allowed ONLY in `docs/codex-reviewer.md` + the substrate-default NOTE of `docs/dispatch-recipe.md`, and FORBIDDEN in `docs/review-gate-seam.md`'s protocol section. **This is exactly the spec §8 list — no broader ad-hoc allowances.** These are the only files where a substrate term is in-scope; everywhere else a substrate term is a build failure.
- **The TEST-INFRASTRUCTURE scan-EXCLUDE set (NOT a content exception — a "don't scan the test's own data" necessity):** the guard's scan target is the tracked tree MINUS `tests/genericity_lists.py` (the denylist-as-data — it CONTAINS every forbidden term BY DESIGN) and the guard-test fixture files that plant forbidden terms for the distinguishing self-tests. This is NOT a content allowance (those files carry no real app/domain content — they are the guard's own machinery); it is the unavoidable "a grep test cannot scan the file that holds its own grep patterns" exclusion (R5-MAJOR-1). The exclude set is a named constant in the test contract (auditable, cannot silently grow), and it does NOT widen the spec §8 substrate-vocab scoping (which stays exactly the two named content files + the forbidden protocol section above).

**Matching semantics (implementation detail the spec leaves to the build):** the guard matches each forbidden term as a case-insensitive word-boundary token (`\bterm\b`) so an unrelated word containing a forbidden substring does not false-fail; this is the mechanically-exact realization of the spec's "appear NOWHERE" — it does not relax the spec, it makes the grep precise.

**Acceptance check:** the three lists are explicit module-level constants in `tests/genericity_lists.py` (auditable + amendable); the forbidden list is the ENUMERATED denylist (a), NOT a category; the test fails the build on any forbidden hit OR any substrate term outside its file scope; the guard scans the TRACKED tree MINUS the named exclude set (the list file + the planted-term fixtures); the self-exclusion test (4) passes (the guard does not trip on its own data).

**Commit:** `feat(guard): Task F.1 — genericity guard (forbidden / allowed-substrate / file-scope-exception lists; self-tested to distinguish)`

### F.2 — Run the guard over the full authored tree (the binding gate)

**Files:** `tests/test_genericity_guard.py` (extend to scan the real repo tree, not just fixtures).

**Content:** the guard test, run over the ACTUAL tracked scaffold tree, MUST pass green at the end of the build. This task is the gate that every Group C/D/G/H/I doc must clear (each of those tasks' acceptance check already says "guard passes," but F.2 is the whole-tree run).

**TDD/acceptance:** the guard passes over the entire tracked tree (this is re-run as the LAST thing in J.2 — but F.2 establishes it as a standing test that fails the build if any later doc reintroduces a forbidden term).

**Commit:** `test(guard): Task F.2 — guard scans the full tracked tree (binding build gate)`

### F.3 — Wire the guard into the build/CI signal

**Files:** `<harness-template>/pyproject.toml` (or a `tests/` marker) + (optional) a minimal CI config note in `docs/comms-orchestrator-registry.md`/README is NOT the place — instead a short note in the README or a `Makefile`/`tox`-equivalent that the guard is part of the test run.

**Content:** ensure the guard test runs as part of the default test invocation (it's a normal test in the chosen runner; F.3 just confirms it's discovered + not skip-marked). If the operator wants a CI hook, document the one-liner; CI infra itself is out of scope (the scaffold is operated by Claude + the operator, not a CI server — §2). **Plan decision: NO CI server config ships** (out of scope, same-substrate-Claude-operated); the guard runs in the standard test invocation. F.3 documents how to run the full validation suite (incl. the guard) in the README.

**Acceptance check:** running the scaffold's test suite executes the genericity guard (not skipped); the README's "validate the scaffold" section names the command.

**Commit:** `docs(guard): Task F.3 — guard runs in the default test invocation; validation command documented`

---

## TASK GROUP G — Review/gate seam + Codex-reviewer reference

### G.1 — `docs/review-gate-seam.md` (SEAM 3 — the mechanism-agnostic contract)

**Files:** `<harness-template>/docs/review-gate-seam.md`.

**Content (acceptance checklist — §5.3, Q2=b):** three parts:
1. **Review-to-convergence protocol (shape fixed; mechanism seam):** product → adversarial **reviewer** → severity-classified findings → **adjudicate** each → **iterate to convergence** (zero new blocking). Extension points the new CHARC fills: `REVIEWER`, `PRODUCT_REPRESENTATION`, `SEVERITY_RUBRIC`, `CONVERGENCE_CRITERION` (default: zero-new-blocking).
2. **The gate (director-owned, before accept):** a checklist of pass/fail checks. Extension points: `GATE_CHECKS`, `WITNESS` (the irreducible reality/human check the automated reviewer can't replace), `ACCEPTANCE` (what merge/accept means).
3. **Carry-over disciplines (filled — generic wisdom):** the reviewer is fallible, the witness is the true net (review is a *filter*, never the gate); run to convergence (don't pad/stop early); **adjudicate, don't blind-fix** (a finding premised on something the system *verifiably prevents* is out-of-scope **WITH a cited constraint** — absent the citation it stays in-scope); verify on reality, not from the report; ground or STOP.

**The minimal generic DEFAULT (§5.3 Major-5 — operable minute-one, replaceable starters):**
- `SEVERITY_RUBRIC` = {blocking: critical, major · advisory: minor}
- `CONVERGENCE_CRITERION` = zero-new-blocking
- `GATE_CHECKS` = [the director's stated conditions hold AND the `WITNESS` confirms]
- `WITNESS` = operator confirmation
- `REVIEWER` = a self-review pass (CHARC or a fresh agent re-reads the product adversarially) until a domain reviewer is plugged.
- These are clearly marked **replaceable starters**; the interview swaps in the domain's real rubric/gate/reviewer.
- **The default block — the SPEC requires the five defaults + minute-one operability; the parse marker is an INTERNAL IMPLEMENTATION AID, not a spec requirement.** The spec §5.3 requires the minimal default (the five starters) + operability minute-one; it does NOT mandate any specific marker. To make G.3's check machine-verifiable, the IMPLEMENTER may couple the test to the doc via ANY stable extraction mechanism; the plan SUGGESTS a `<!-- SEAM3-DEFAULTS -->` ... `<!-- /SEAM3-DEFAULTS -->` fenced region (generic HTML-comment syntax, no substrate vocab) as a convenient default — but this marker is an implementation aid the implementer/CHARC may swap for any equivalent (a heading anchor, a fenced block, etc.). What is SPEC-REQUIRED is that the five defaults are present + the seam is operable minute-one; HOW the G.3 test extracts them to assert that is the implementer's choice.

**The doc names the extension points + it NEVER names a mechanism in the protocol itself** (no Codex, no test-runner — those are seam fills / the optional reference).

**`review-gate-seam.md` is kept COMPLETELY substrate-free — including paths. The `codex-reviewer.md` pointer is routed through OTHER docs, NOT the seam file.** To make `review-gate-seam.md` unambiguously §8-clean (no substrate WORDS and no substrate-named path tokens anywhere in the file), the seam doc does NOT reference `codex-reviewer.md` at all. It names the abstract `REVIEWER` extension point + the §5.3 default (a self-review pass) and, to keep the seam self-contained (the §5.3 "seam doc + optional plug-in" linkage), includes a **mechanism-agnostic DISCOVERY note** — a generic sentence in the seam doc stating *how* a domain plug-in for the `REVIEWER` slot is discovered: "the harness's optional `REVIEWER` plug-in references are catalogued in the `docs/` reference set and named in the bootstrap's seam-3 step." This names NO file + NO substrate token, yet tells the reader where to find the optional reviewer — preserving the seam→plug-in linkage WITHOUT a substrate reference. (The concrete `codex-reviewer.md` reference lives in `dispatch-recipe.md` + the bootstrap, the §8 exception locations.) The §5.3-required pointer to `codex-reviewer.md` is provided instead by **`dispatch-recipe.md` (a §8 exception file — its substrate-default note already references the optional reviewer reference) and `README.md`/`charc-bootstrap.md`'s seam-3 step** (which lists `codex-reviewer.md` as the optional `REVIEWER` plug-in). So §5.3's "the harness points at the optional Codex reference" is satisfied at the harness level (the bootstrap + the dispatch-recipe + the codex-reviewer file itself), while the mechanism-agnostic `review-gate-seam.md` stays 100% substrate-free. The guard's file-scope exceptions remain EXACTLY the spec §8 two (`docs/codex-reviewer.md` + the substrate-default note of `docs/dispatch-recipe.md`); `review-gate-seam.md` gets NO exception and contains NO substrate token (word OR path).

**Acceptance check:** the doc has the three parts; the FIVE defaults are present + marked replaceable-starters + extractable by SOME stable mechanism for the G.3 test (the suggested `<!-- SEAM3-DEFAULTS -->` marker OR an equivalent — an implementation aid, not a spec requirement); **the WHOLE `review-gate-seam.md` carries NO substrate token — no substrate WORD and no substrate-named PATH** (it does not reference `codex-reviewer.md`; it names the abstract `REVIEWER` slot generically); the §5.3 pointer to the optional reviewer reference is carried by `dispatch-recipe.md` + `README.md`/`charc-bootstrap.md` (NOT the seam doc); the guard's file-scope exceptions are EXACTLY the spec §8 two named files, with NO exception for `review-gate-seam.md`. The Codex mechanism prose lives ONLY in `codex-reviewer.md`.

**Commit:** `docs(scaffold): Task G.1 — review-gate-seam.md (mechanism-agnostic contract + the §5.3 minimal default + extension points)`

### G.2 — `docs/codex-reviewer.md` (OPTIONAL plug-in reference)

**Files:** `<harness-template>/docs/codex-reviewer.md`.

**Content (acceptance checklist — §5.4):** the swing-proven Codex incorporation, extracted as a stocked-toolbox reference for the `REVIEWER` extension point — **framed as ONE optional mechanism, not THE reviewer** (a non-software domain plugs a different reviewer and ignores this file):
- The WSL-native invocation (the `export PATH="$HOME/.local/node22/bin:$PATH"` prefix is required) + the `codex --version` liveness probe.
- The review tiering (`-p <tier>` profiles, tiered by blast-radius of a missed finding) + the fallback (omit `-p` if the profile is absent).
- The staging (`--skip-git-repo-check`; pre-generate the diff because the worktree `.git` is WSL-unreachable; pipe via stdin; write output to a file for the cp1252 glyph issue).
- Run-to-convergence (`NO_NEW_CRITICAL_MAJOR`; persist every response).
- An explicit sentence: **Codex is one replaceable `REVIEWER` implementation, not part of the core protocol** — a non-software domain plugs a different reviewer and ignores this file.

**Acceptance check:** the file is the substrate-coupled reference (WSL/Windows/Codex terms ALLOWED here — it's a §8 file-scope exception file); it explicitly frames Codex as optional/replaceable. **It is pointed at by `dispatch-recipe.md`'s substrate-default note + the `README.md`/`charc-bootstrap.md` seam-3 step (NOT by `review-gate-seam.md`, which stays substrate-free — G.1).** **Genericity guard:** this file is on the exception list (Codex/WSL/git allowed); `swing` is still forbidden (the recipe content is genericized — it describes the Codex mechanism, not swing).

**Commit:** `docs(scaffold): Task G.2 — codex-reviewer.md (optional REVIEWER reference; substrate-coupled, framed replaceable)`

### G.3 — Seam-3 defaults present + operable-minute-one (a concrete distinguishing check)

**Files (new repo):** `tests/test_seam3_defaults.py` + a documented minute-one dry-run section appended to `docs/review-gate-seam.md`.

**Content:** a CONCRETE, distinguishing acceptance artifact (NOT a vague checklist) that a fresh CHARC with ONLY the shipped defaults (no interview fill) can run the review/gate loop against its own bootstrap changes (§5.3 "operable from minute one"). Two parts:
1. **A machine-checkable test** (`tests/test_seam3_defaults.py`) that PARSES `review-gate-seam.md` and asserts ALL FIVE default extension points are present + non-empty in the doc's marked "minimal default" block: `SEVERITY_RUBRIC` = {blocking: critical, major · advisory: minor}; `CONVERGENCE_CRITERION` = zero-new-blocking; `GATE_CHECKS` = [director conditions hold AND WITNESS confirms]; `WITNESS` = operator confirmation; `REVIEWER` = self-review pass. The test extracts the default block via a stable marker (e.g. a `<!-- SEAM3-DEFAULTS -->` fenced region the doc carries) and asserts each key resolves to its §5.3 starter value.
2. **A documented minute-one dry-run** (a section IN `review-gate-seam.md`): the exact ordered steps to take ANY product (e.g. a CHARC bootstrap edit) through the default loop — product → self-review REVIEWER pass → classify findings by the default SEVERITY_RUBRIC → adjudicate each → iterate until CONVERGENCE_CRITERION (zero-new-blocking) → run GATE_CHECKS → WITNESS (operator) confirms → accept. No extension point is left undefined.

**TDD (red→green) — distinguishing:** the test FAILS before the §5.3 defaults are written into `review-gate-seam.md` (the default block / markers absent → assertion fails) and PASSES once G.1's default block exists with the five starters. (This proves the test bites — it would not pass against an empty or default-less seam doc.)

**Acceptance check:** all five defaults present + parseable from the doc; the dry-run section names every step with no missing extension point; **genericity guard passes** (the dry-run names NO mechanism — Codex absent; it's the generic loop). The test distinguishes (fails pre-default, passes post-default).

**Commit:** `test(scaffold): Task G.3 — seam-3 defaults present + minute-one dry-run (distinguishing acceptance)`

---

## TASK GROUP H — The kernel: charter + bootstrap + the 5-step checklist

The kernel (§3) = `charc-charter.md` + `charc-bootstrap.md`. The charter is the third role-protocol doc (the generic lift of swing's `tool-director-context.md`).

### H.1 — `docs/charc-charter.md` (the KERNEL director charter)

**Files:** `<harness-template>/docs/charc-charter.md`.

**Content (acceptance checklist — §5.2, lift of `tool-director-context.md` §1-5, stripped of ALL swing arc/phase content):**
- CHARC's standing authority: **owns harness + application operation** (the one default director who performs the bootstrap — the role the operator runs in swing).
- The generic disciplines: director-as-peer push-back (at a low threshold); verify-on-reality; the **tripwire / architecture-pass** concept (changes crossing the seams route through CHARC); the comms routing rules (directors↔directors allowed; a director cannot bus-reply to a foreign role it does not own — route via the operator; the implementer never posts to a mailbox).
- The **debt-register / phase-boundary-proposal** posture (generic: CHARC maintains a debt register, proposes paydown at phase boundaries; the operator commissions) — the CONCEPT, not swing's specific D1-D15 entries.
- The custodian-of-FORM / never-owner-of-CONTENT boundary (harness-hygiene custody — generic).
- The peer-director-add checklist (the §5.1 enumerated set — cross-ref B.4).
- **Stripped of:** all swing register entries, the swing session log, the swing phase history, any finance/trading content.

**Acceptance check:** the charter contains the generic role definition + disciplines + tripwire concept + debt-register concept + comms routing; contains ZERO swing arc/phase/finance content + ZERO swing debt-register entries; **genericity guard passes**.

**Commit:** `docs(kernel): Task H.1 — charc-charter.md (generic director kernel: authority, disciplines, tripwire, debt-register concept, comms routing)`

### H.2 — `docs/charc-bootstrap.md` (CHARC's literal first-run flow + the 5-step checklist)

**Files:** `<harness-template>/docs/charc-bootstrap.md`.

**Content (acceptance checklist — §5.5, Major-2/3 + Minor-5 resolution):** CHARC's literal first session:
1. Read the charter (`charc-charter.md`).
2. **Verify comms:** a `role_mail` round-trip (post → read → ack across charc/orchestrator/operator); verify the hook + the optional UI; **verify the orchestrator registry** (it auto-creates; check the `comms/sessions/` tree behavior).
3. **The application-definition interview** with the operator — fill seams 1-3:
   - the app domain → `APPLICATION.md` (seam 1).
   - the domain cells → author from `implementer-template.md` (seam 2).
   - the review/gate mechanism → fill the `review-gate-seam.md` extension points, or accept the §5.3 defaults, optionally adopting `codex-reviewer.md` (seam 3).
4. Commission the first arc(s).

**The 5-step bootstrap checklist (every file CHARC touches — so the no-engine design carries no hidden coordination debt):**
1. `APPLICATION.md` — define the app domain (seam 1).
2. `.claude/agents/` — author the domain implementer cells from `implementer-template.md` (seam 2).
3. `review-gate-seam.md` — fill the extension points, or accept the §5.3 defaults, optionally adopting `codex-reviewer.md` (seam 3).
4. `launch_role.ps1` — (optional) tune the model/effort default (seam 4).
5. **Bring up the orchestrator** — launch an orchestrator session via `launch_role.ps1 -Role orchestrator` (sets `HARNESS_ROLE=orchestrator` → it registers); CHARC verifies the registry shows it live before commissioning the first arc.

**The orchestrator bring-up prompt — a FENCED COPY-PASTE BLOCK inside this doc's step-5 section (the §2.1 default; NO separate file).** `charc-bootstrap.md` carries, in its step-5 section, the orchestrator bootstrap prompt as a fenced block the operator pastes into the orchestrator session (the realized-inbox content — see H.3 for the block's contents). This keeps the orchestrator bring-up INSIDE an existing manifest file (no new manifest file — the R5 fix), while still satisfying §5.5 step-5.

**The STAGED guarantee (§5.5):** CHARC operation (comms + charter) works on a bare clone; orchestrator + implementer operation works after step 5. The interview drives 1-3; 4-5 are mechanical. State this explicitly in the doc.

**Acceptance check:** the bootstrap names all 5 checklist steps + the staged guarantee; the "verify comms" step covers the round-trip + the registry; the interview fills seams 1-3 by name; the step-5 section CONTAINS the orchestrator bring-up prompt as a fenced block (H.3 content); **genericity guard passes** (no swing content; `HARNESS_ROLE` not `SWING_ROLE`).

**Commit:** `docs(kernel): Task H.2 — charc-bootstrap.md (first-run flow + 5-step checklist + staged guarantee + folded orchestrator bring-up block)`

### H.3 — The orchestrator bring-up prompt content (folded into H.2's step-5 by default; NO separate file)

**Files (DEFAULT):** NONE new — the orchestrator bring-up prompt is authored as a **fenced copy-paste block inside `charc-bootstrap.md`'s step-5 section** (Task H.2). This is the §2.1-default that keeps the shipped scaffold == the §4 manifest (no new file). *(OPTIONAL CHARC alternative, NOT the default: split the block into a standalone `scripts/orchestrator_bootstrap.md` matching swing — an explicit CHARC choice at execute-time, which would add one file beyond the §4 manifest; flagged, not shipped by default.)* H.3 is therefore the CONTENT spec for the block H.2 carries — not a separate deliverable file.

**Content (acceptance checklist — the orchestrator bring-up block, genericized + inbox-realized):**
- A new orchestrator generation: read `docs/orchestrator-context.md`; orient to live state; announce online to CHARC via `role_mail`.
- **The KEY divergence from swing:** swing's bootstrap says "there is no orchestrator inbox in V1 … you POST to directors and receive direction FROM the operator." The scaffold REALIZES the inbox — so the block says the orchestrator HAS an inbox (it can be addressed via the registry), drains it, and the registry registers it on first prompt (the hook). The concurrent-generations note carries (multiple generations can run; the newest-live is "current").
- Honor the binding conventions (conventional commits, no Co-Authored-By, no --no-verify) — generic.

**Acceptance check:** the bring-up block (inside `charc-bootstrap.md` step-5) reflects the REALIZED inbox (NOT swing's "no inbox in V1"); names `HARNESS_ROLE=orchestrator`; **genericity guard passes**. (No separate file ships by default — the block lives in H.2's deliverable; H.3 has no own commit unless CHARC elects the optional standalone-file alternative.)

**Commit:** *(folded into H.2 by default — no separate H.3 commit; if CHARC elects the optional standalone file: `docs(kernel): Task H.3 — standalone orchestrator_bootstrap.md (CHARC-elected; realized-inbox)`)*

---

## TASK GROUP I — The optional mail UI (`comms_ui.py`, `[web]` extra)

Shipped but OPTIONAL (§4: zero hard deps in the core; the UI is a `[web]` extra). Lift of swing's `comms_ui.py`, genericized (roles charc/orchestrator/operator; remove `rd`; the director-launch surface → role-launch surface; vendor htmx locally).

### I.1 — `comms_ui.py` core: inbox / compose / bus / history over the three roles

**Files (new repo):** `scripts/comms_ui.py`, `tests/test_comms_ui.py` (the UI tests run under `unittest` with FastAPI's `TestClient`, gated behind the `[web]` extra). **The vendored HTMX client: DEFAULT = inline it into `comms_ui.py` as a module string constant served from `/static/htmx.min.js` (ZERO extra files — keeps the scaffold surface == the §4 manifest's single `comms_ui.py` line).** The separate `scripts/comms_ui_assets/htmx.min.js` asset (matching swing's layout) is an OPTIONAL alternative the implementer/CHARC may choose if a separate asset file is preferred — NOT the default. Either way the client is served from THIS origin (no CDN — the loopback UI holds POST authority).

**Content (acceptance checklist — lift, genericized):**
- The single-file FastAPI + HTMX app: operator inbox (ack/ack-all over `comms/operator/inbox` ONLY — L3), compose (operator-stamped, `decision_request` ABSENT from the type allowlist — L1 belt), the bus view (read-only over the OTHER roles — now charc + orchestrator, NOT rd), history (read/ archive).
- Goes through `role_mail.post_message` / `ack_message` (L4 single write path).
- OriginGuard (loopback-only, DNS-rebinding defense) — verbatim lift.
- The role-launch surface: the swing UI launches directors; the scaffold's launches charc/orchestrator via `launch_role.ps1` (enum-validated fixed argv — L5).

**TDD (red→green):**
1. Failing test (with `TestClient`): `GET /` renders; the inbox pane shows `comms/operator/inbox` messages → green.
2. Failing test: `POST /compose` with `decision_request` → refused (L1 belt; not in the allowlist).
3. Failing test: `POST /ack` over a director (charc) inbox is impossible (the UI acks operator ONLY — L3).
4. Failing test: a cross-origin POST → 403 (OriginGuard).

**Acceptance check:** the UI is import-isolated from the core (the core stdlib test from A.1 still passes — `comms_ui.py` is NOT imported by `role_mail.py`); the `[web]` extra is required to run it; **genericity guard passes** (no `rd`, no swing; substrate terms not needed here). The bus roles are `("charc", "orchestrator")` not `("charc", "rd")`.

**Commit:** `feat(ui): Task I.1 — optional comms_ui (inbox/compose/bus/history; charc+orchestrator bus; L1-L5 locks; [web] extra)`

### I.2 — `comms_ui.py`: the role-launch + orchestrator-bring-up surface

**Files:** `scripts/comms_ui.py`, `tests/test_comms_ui.py`.

**Content:** the role-launch strip (launch charc/orchestrator via `launch_role.ps1`, L5 enum-validated fixed argv) + the "copy orchestrator bring-up" button (serves the `orchestrator_bootstrap.md` verbatim for the step-5 bring-up). Genericized from swing's directors-strip + the orchestrator-spin-up copy button.

**TDD (red→green):**
1. Failing test: `POST /launch` with an invalid role → 400 (L5 enum-validate before argv).
2. Failing test: the launch argv is the EXACT fixed `launch_role.ps1` invocation (no user-typed string reaches the command line).
3. Failing test: `GET /orchestrator-bootstrap` serves the bootstrap doc verbatim.

**Acceptance check:** L5 fixed-argv preserved; roles are charc/orchestrator; guard passes.

**Commit:** `feat(ui): Task I.2 — role-launch + orchestrator-bring-up surface (L5 fixed argv, charc+orchestrator)`

---

## TASK GROUP J — Validation suite + bootstrap dry-run + final acceptance

### J.1 — The comms round-trip validation (the §8 testing requirement)

**Files:** `tests/test_comms_roundtrip.py`.

**Content (§8):** post → read → ack across the three roles (charc/orchestrator/operator); the single-write-path + idempotency locks exercised end-to-end (an integration test over the real `role_mail` + a tmp comms root). This is the "comms works" half of the success criterion (§1).

**TDD (red→green):**
1. Failing test: operator→charc→ack, charc→orchestrator→ack, orchestrator→operator→ack — all round-trip; the ack moves inbox→read; nothing deleted.

**Acceptance check:** all three role pairs round-trip; guard passes.

**Commit:** `test(scaffold): Task J.1 — comms round-trip across the three roles`

### J.2 — The registry validation suite + the whole-tree genericity gate (re-run)

**Files:** `tests/test_registry_suite.py` (aggregates the D-group behaviors as a named suite) + re-run F.2 over the final tree.

**Content (§8):** register-on-prompt, `last_seen` heartbeat, opportunistic prune of a stale entry, recreate-if-missing self-heal, role-gated registration (only orchestrators register), `SessionEnd` idempotent tidy — as a cohesive validation suite. PLUS the genericity guard re-run over the FINAL tracked tree (the binding build gate, F.2) MUST be green.

**TDD/acceptance:** the registry suite is green; **the genericity guard passes over the entire final tree** (zero forbidden vocab; every substrate term in-scope). This is the no-app-contamination proof (§1 "zero application contamination").

**Commit:** `test(scaffold): Task J.2 — registry validation suite + whole-tree genericity gate green`

### J.3 — Bootstrap dry-run + final acceptance walkthrough

**Files:** `tests/test_bootstrap_dryrun.md` (an acceptance-spec doc) + a final README "validate the scaffold" section confirmation.

**Content (§8 "Bootstrap dry-run"):** a fresh-clone walkthrough confirms CHARC can verify comms and reach the interview with NO further setup (the staged guarantee's CHARC-operation half). Plus the orchestrator bring-up (step 5) brings the registry to a live-orchestrator state. The "test" is a documented walkthrough checklist (the bootstrap is a human/agent procedure), with the executable pieces (comms round-trip J.1, registry suite J.2) cited as the automated evidence.

**The step-5 EXECUTABILITY check (R6 — step 5 runs as written, not just reads as prose):** the dry-run includes an EXECUTABLE step-5 segment with concrete, runnable evidence: (a) `launch_role.ps1 -Role orchestrator -DryRun` prints the exact `claude` command with `HARNESS_ROLE=orchestrator` set in the inner command (an automatable assertion — the `-DryRun` output is machine-checkable); (b) the documented walkthrough states the post-launch verification: after a real orchestrator launch, the registry shows a live orchestrator entry (the `UserPromptSubmit` register fires on its first prompt — provable via the D.2/D.6 registry tests that the register path works); (c) the bring-up block in `charc-bootstrap.md` step-5 is the literal copy-paste the operator pastes into that orchestrator session. So step 5 is EXECUTABLE end-to-end: dry-run-verified launch command + a register path proven by the registry suite + a concrete paste block — not prose. (The fully-live launch is the operator's bootstrap-gate witness; the dry-run + registry-suite are the automatable evidence that the executable pieces work.)

**Acceptance check (the FINAL gate, mapping to §1 success criterion):**
- After cloning + launching CHARC: comms works (J.1 green); the role-protocol + dispatch + review/gate shapes are present + runnable (the docs exist + the seam defaults are operable, G.3); the bootstrap reaches the interview with no further setup.
- **Step 5 is executable as written:** `launch_role.ps1 -Role orchestrator -DryRun` produces the correct command (HARNESS_ROLE set), the register path is proven (D.2/D.6), the bring-up block exists in charc-bootstrap.md step-5 — not just prose.
- The three definition seams (1-3) are clearly marked + fillable; seam 4 ships a tuned default.
- The whole-tree genericity guard is green (J.2).
- Zero hard runtime deps in the core (A.1's dependency-posture test green); the UI is `[web]`-gated.
- **Manifest accounting is exact (cross-ref §2.1):** the SHIPPED-SCAFFOLD MANIFEST == the spec §4 list (the §2.1 18-row shipped-file list; the registry logic, the orchestrator bring-up, and the HTMX client are FOLDED into shipped files by default — zero extra files). The repository-support artifacts (`tests/**` + `pyproject.toml` + `.gitignore`) are the §2.1 APPENDIX — tracked + guard-scanned but NOT scaffold-manifest files. The final acceptance asserts EVERY tracked file is either in the §2.1 shipped-manifest list OR the support appendix (one accounting model, no dual count) — so an implementer knows exactly which files are scaffold surface vs repository support.
- **All four brief §4 locks honored** (see §3 below).

**Commit:** `docs(scaffold): Task J.3 — bootstrap dry-run walkthrough + final acceptance (success criterion mapped)`

---

## 3. Brief §4 locks — where each is honored in this plan

| Lock (brief §4 / spec) | Honored in |
|---|---|
| **Approach A** (authored new repo, NOT fork-and-strip; zero app/domain content) | §0 (stated); enforced by the genericity guard (F.1-F.3, J.2); every doc task's acceptance check |
| **The ~14-file manifest** (spec §4) | The §2.1 shipped-manifest list IS the §4 manifest exactly (the 18-row table): README (A.2), APPLICATION.md (A.3), comms/.gitkeep (A.1), role_mail.py (B), comms_ui.py (I — HTMX client inlined), launch_role.ps1 (E.1), settings.json (E.2), the 3 hooks (D.2-D.4 — registry logic inlined in session_start.py), implementer-template.md (C.3), charc-charter.md (H.1), charc-bootstrap.md (H.2 — orchestrator bring-up folded into step-5), orchestrator-context.md (C.1), dispatch-recipe.md (C.2), review-gate-seam.md (G.1), codex-reviewer.md (G.2), comms-orchestrator-registry.md (D.7). **The DEFAULT build adds ZERO files beyond the §4 list** (the 3 inline details fold into shipped files). The `tests/**` tree + `pyproject.toml` + `.gitignore` are the §2.1 repository-support APPENDIX — tracked + guard-scanned but NOT scaffold-manifest files (one accounting model; no dual count) |
| **The four seams** (spec §3) | Seam 1 = APPLICATION.md stub (A.3); Seam 2 = implementer-template.md (C.3) + the bootstrap cell-authoring step (H.2); Seam 3 = review-gate-seam.md contract + default (G.1) + the optional codex-reviewer (G.2); Seam 4 = launch_role.ps1 model/effort tuned default (E.1) — interview-filled 1-3, tuned-default 4 |
| **Genericity guard (spec §8)** — grep build test, three explicit lists | Task Group F (F.1 the test + the forbidden/allowed-substrate/file-scope-exception lists, self-tested to distinguish; F.2 whole-tree; F.3 wired into the test run); re-gated in J.2 |
| **Orchestrator inbox + session registry (spec §5.1, from the Stage-2 design)** — session_id-keyed, last_seen heartbeat, opportunistic prune (no daemon), role-gated HARNESS_ROLE registration, recreate-if-missing self-heal, SessionEnd idempotent tidy, shared-inbox default + atomic inbox→read claim, hook session_id contract + degraded mode | Task Group D in full (D.1 data shape + STALE_SECONDS; D.2 UserPromptSubmit heartbeat+register+recreate+degraded; D.3 SessionStart create+prune; D.4 SessionEnd idempotent; D.5 shared-inbox + atomic-move claim + newest-live; D.6 self-heal; D.7 the design doc) + the env contract in E.1 (HARNESS_ROLE) |
| **Review/gate seam (spec §5.3)** — mechanism-agnostic contract + minimal generic DEFAULT (operable minute-one) + optional codex-reviewer (§5.4) framed as ONE replaceable reviewer | G.1 (contract + the §5.3 SEVERITY_RUBRIC/CONVERGENCE_CRITERION/GATE_CHECKS/WITNESS/REVIEWER defaults, marked replaceable starters); G.2 (codex-reviewer optional, framed replaceable); G.3 (minute-one operability) |
| **The kernel + staged bootstrap (spec §5.5)** — charc-charter + charc-bootstrap + the 5-step checklist; the STAGED guarantee | H.1 (charter kernel); H.2 (bootstrap + the 5-step checklist + the staged guarantee); H.3 (the orchestrator bring-up prompt for step 5) |
| **Zero hard runtime deps** (core stdlib; UI optional `[web]` extra) | A.1 (the dependency-posture test asserting stdlib-only core); the registry + hooks are stdlib (D); comms_ui is `[web]`-gated + import-isolated (I.1 acceptance) |

---

## 4. Spec open sub-decisions (§11) — resolved-at-plan

- **Registry file format + staleness threshold (§11):** ONE-file-per-session JSON `comms/sessions/<session_id>.json` (the Stage-2 §2 no-shared-RMW pattern); `STALE_SECONDS = 45 * 60` (45 min) as a single tunable named constant (the spec's 30-60 min range; tune-at-build flagged). Resolved in D.1/D.7.
- **comms_ui ship/optional + the guard mechanism:** already resolved by the spec (§4 ship-optional, §8 the guard) — no plan decision needed.

## 5. Deviations from a naive swing-copy (called out so the executing implementer doesn't "fix" them back)

1. **`orchestrator` IS in `VALID_TO`** (swing's V1 had it send-only) — the scaffold ships the inbox realized (§5.1). B.1.
2. **`rd` role REMOVED** — one director ships (§9). B.1, E.1, I.1.
3. **The launcher does NOT own a `.sessions.json` liveness map** — the HOOKS own the one-file-per-session registry; the launcher only sets `HARNESS_ROLE` (and may keep a display-name map for resume, NOT the liveness registry). E.1. (Swing's launcher wrote the non-concurrency-safe `.sessions.json`; the scaffold's registry is hook-owned + concurrency-safe by the one-file pattern.)
4. **`SWING_ROLE` → `HARNESS_ROLE`** everywhere (hooks, launcher, settings). D.2, E.1, E.2.
5. **`.claude/settings.json` uses a portable path**, not swing's hard-coded `C:/Users/rwsmy/...` absolute. E.2.
6. **The orchestrator bootstrap reflects the realized inbox**, not swing's "no orchestrator inbox in V1." H.3, C.1.

## 6. Open questions / STOP-and-ask items for the orchestrator/operator

- **DECISION A (repo name + location)** and **DECISION B (who runs `git init`, when)** — §0.2. **These gate the executing dispatch and are operator-owned; the executing dispatch cannot start until they land.**
- **DECISION C (shared-inbox vs per-generation addressing)** — the spec decides shared-inbox as the ship default (§5.1, §9). The plan builds shared-inbox. If the operator wants per-generation from day one, flag back to CHARC (it changes D.5's addressing tasks). No action needed otherwise.
- **§8 launcher spawn path — RESOLVED IN-PLAN, spec-faithful, no open decision.** The launcher ships a single §8-compliant surface: the plain `powershell -NoExit` role window (PowerShell + Windows are in the §8 allowed-substrate list; `wt.exe` is not, so it is NOT lifted — F.1(d)). This is NOT a gate or an open question — it is the spec-faithful realization of §8. The ONLY future-awareness flag (NOT a blocker): if the operator later wants Windows-Terminal tabs, that is an explicit CHARC §8-list amendment + a follow-on launcher task, OUT of this plan's scope.
- **Test runner — RESOLVED to stdlib `unittest`** (NOT pytest). The §8 genericity guard forbids `pytest` in the tracked tree, so the scaffold's own suite MUST be `unittest`-based (no pytest dev-dep, no `pytest`-named path). Resolved in §1 "Test substrate"; not an open question — flagged here only so the executing implementer does not reintroduce pytest by habit.
- **`.claude/settings.json` portable-path mechanism** — whether Claude Code accepts a repo-root-relative hook command on this substrate, or requires an absolute path (→ ship a placeholder + a documented one-line operator substitution). E.2 handles both; the executing implementer verifies the substrate's hook-path requirement against the live Claude Code version (verify-don't-assume).

---

## 7. Executing-plans dispatch shape (for the next dispatch)

- **Tier:** `review-strong` (§0.1) — harness production code; run-to-`NO_NEW_CRITICAL_MAJOR`, cap suspended; persist every Codex response to `.copowers-findings.md`.
- **Cell recommendation:** `implementer-opus-xhigh` or `implementer-opus-high` — the registry build-from-a-deferred-spec + the genericity-guard regex tuning + the seam contracts are judgment-dense; the doc-lifts are mechanical. (CHARC/orchestrator selects per the cell rubric.)
- **Workspace:** the NEW repo (DECISION A/B), the implementer's own branch/worktree there — NOT a swing worktree.
- **Suite gate:** run the scaffold's full test suite to green BEFORE the Codex review (the before-AND-after full-suite discipline), and again after review fixes.
- **The genericity guard is the binding no-app-contamination gate** — it must be green over the whole tree at accept (J.2). A guard hole = a blocking major.
