# Implementation Plan — Harness-Template B-9 (genericity-guard REDESIGN) + B-12 (peer-director-add code)

**Target repo:** `C:\Users\rwsmy\harness-template` (the SCAFFOLD), branch `master`, base HEAD **`7f3f7c0`**.
**This doc lives in:** `swing-trading/docs/plans/` (the swing control repo — a project-term-laden artifact that must NOT contaminate the application-agnostic scaffold). The WORK targets harness-template.
**Source brief:** `swing-trading/docs/harness-template-b9-b12-commissioning-brief.md` (committed `9bfddd45`). Design is settled in brief §0–§3; this plan makes it executable + the distinguishing-test arithmetic airtight.
**Reference impl (study + ADAPT, do NOT transplant):** coa-chess `ec9856d` + `9aee81d`.
**Accept gate (NOT pytest):** `python -m unittest discover -s tests` from the harness-template root. Baseline verified **168 tests, OK** at `7f3f7c0` on disk.

---

## 0. Executive summary + the key reference-impl adaptation

B-9 redesigns the scaffold's OWN template-integrity self-validation so a FILLED germination is **green-by-construction** instead of red-by-default (the B-8 blocker: filling the seams turns the purity gates RED on the very act the seams exist to enable). The mechanism is a single shared **instance-surface model** (`is_instance_surface()` + `INSTANCE_SURFACE_RELPATHS`/`_PREFIXES`/`_PATTERNS` in `tests/genericity_lists.py`), to which the three structural guards (`genericity_guard`, `manifest_accounting`, `test_dependency_posture`) are scoped CORE-only. B-12 completes the peer-director-add code: single-source the hook's role set off `role_mail.SINGULAR_INBOX_ROLES` (Gap 1), register the new director's instance docs as instance surface (Gap 2, rides B-9), reword charter §8 item 2 (Gap 3).

**The load-bearing adaptation decision (which reference commit to follow).** coa-chess shipped TWO commits: `ec9856d` (narrow — exempt only the named `APP_EXAMPLE_TERMS` on the instance surface) then `9aee81d` (superseding — exempt the WHOLE instance surface from the vocab/ticker bans entirely; `APP_EXAMPLE_TERMS` deleted). **This plan adopts the `9aee81d` form** (the converged coa-chess design), because:
- It directly satisfies brief §1 point 2 ("scope vocab/ticker bans to the CORE; exempt the instance surface") and the coa-chess critique §2 (the word-ban has false POSITIVES — "trade"=a chess move, "ticker"=meta-discussion of the guard in a state doc; the instance surface is application content by design).
- It avoids shipping a project-term list (`APP_EXAMPLE_TERMS = ("chess","coa","trade",…)`) into the TEMPLATE — which would itself be contamination (the §3/point-3 "carrying a prior project's ghost" concern applies to app-example terms exactly as to tickers). The harness-template stays generic: it ships NO app-example exemption list at all; the instance simply has an exempt surface.

**Divergence of the live template from coa-chess (what to ADAPT, not copy):**
- Live `genericity_lists.py` at `7f3f7c0` already lists `chess`, `coa`, `course-of-action`, `course of action` in `FORBIDDEN_TERMS` (lines 55–58) AND already lists the finance terms (`finance`, `ticker`, `yfinance`) + tickers. These STAY forbidden tree-wide-minus-instance-surface — they are the example-app + residue terms the SHIPPED template must reject in CORE. We do NOT add an `APP_EXAMPLE_TERMS` list.
- Live `genericity_lists.py` has NO `is_instance_surface`/`INSTANCE_SURFACE_*` (coa-chess added them). We add them fresh, adapted to the template's generic state (instance-surface entries that EXIST as template stubs — `APPLICATION.md`, `docs/charc-state.md` — plus PATTERNS for not-yet-existing instance files — `docs/review-gate-<app>.md`, `<role>-state.md`, `<role>-context.md`, domain implementer cells, briefs).
- Live `test_dependency_posture.py` is ALREADY core-scoped via `tests/_corefiles.py::CORE_RELPATHS` (a closed 4-file list) — coa-chess did NOT touch it. The operator refinement (brief §1 +OPERATOR REFINEMENT) is therefore satisfied STRUCTURALLY in the template already; this plan ADDS the distinguishing test that PROVES the CORE-scoping (instance third-party import passes; core third-party import fails) and documents the invariant, rather than re-architecting a guard that is already correct.
- Live `test_doc_acceptance.py::ApplicationStubAcceptanceTest` still asserts "empty by design" (lines 100–108). coa-chess `ec9856d` converted it to accept BOTH bare-clone and instantiated states. We adapt that conversion.
- Live charter §8 already has item 4 (`<role>-state.md` state pointer) and item 1 (role sets incl. singular-inbox). We reword item 2 (Gap 3) and ADD a genericity-registration line (Gap 2); we do NOT duplicate item 1/4.

**Contamination self-cert (stated up front; re-asserted per task).** Every change in this plan alters WHAT is scoped (CORE vs instance surface), NEVER what a CORE file may contain. No CORE file gains a project term. CORE contamination (an app term OR extraction residue in a non-instance-surface file) keeps FAILING loud — proven by a dedicated distinguishing test in EACH affected guard. No external dependency is added: the core stays stdlib-only (that invariant is instance-SCOPED for the germinated layer, never relaxed for CORE). The instance-surface entries we ship are PATTERNS/placeholders (`<app>`, `<role>`) and template stubs that already exist — no concrete project name enters the template.

---

## 1. Instance-surface enumeration (the model B-9 + B-12 share)

The single predicate `gl.is_instance_surface(relpath)` returns True iff a tracked file is **application instantiation surface** (filled by germination) rather than reusable harness CORE. The enumeration (adapted from coa-chess `9aee81d` to the template's generic, no-concrete-app state):

**Exact relpaths (`INSTANCE_SURFACE_RELPATHS`)** — files that ship as template stubs and become instance content on fill:
- `APPLICATION.md` — seam-1 fill (what the project does; domain vocab by design).
- `docs/charc-state.md` — the §5.1 state pointer (overwritten each session with live, domain-laden state).

**Prefix/pattern matches (`INSTANCE_SURFACE_PREFIXES` + a small regex set)** — instance files that do NOT exist on a bare clone but appear on fill:
- `docs/briefs/` (prefix) — commissioning briefs (domain-laden by design).
- `docs/review-gate-<app>.md` (pattern) — the seam-3 concrete fill (B-9 point 4); ANY `docs/review-gate-*.md` EXCEPT the CORE `docs/review-gate-seam.md`.
- `<role>-state.md` (pattern) — any peer director's state pointer at the `docs/` level (B-12 Gap 2; the exact parallel of `docs/charc-state.md`). Realized as: any `docs/*-state.md`.
- `<role>-context.md` (pattern) — any peer director's instance-authority doc (B-12 Gap 2). Realized as: any `docs/*-context.md` EXCEPT the CORE `docs/orchestrator-context.md` (which is a shipped generic kernel doc — it must STAY core-scanned).
- Domain implementer cells: `.claude/agents/implementer-*.md` EXCEPT `.claude/agents/implementer-template.md` (the generic shipped cell — stays CORE). (Adapted verbatim from coa-chess `9aee81d`.)

> **Pattern precision (load-bearing — future-safe over-broad-exemption guard).** The `docs/*-context.md`/`docs/*-state.md`/`docs/review-gate-*.md` suffix patterns MUST NOT exempt a CORE doc that happens to match (e.g. `docs/orchestrator-context.md`, `docs/review-gate-seam.md`, or any FUTURE core doc named `docs/foo-context.md`). A hardcoded 2-item denylist is future-UNSAFE (a new core doc silently stops being scanned — Codex R4). Instead the patterns are gated by an EXPLICIT core-doc registry `gl.CORE_DOC_RELPATHS` (the shipped `docs/*.md` kernel set, single-sourced with the manifest via a cross-check test): a `docs/` file is instance surface ONLY if it matches a pattern AND is NOT registered as a core doc. Adding a new core doc is a deliberate, reviewed act (it must be added to `CORE_DOC_RELPATHS` + the manifest; the cross-check fails loud otherwise), so a core doc can never silently fall out of the scan. Distinguishing tests (Task 2 + Task 4) plant an app term in `docs/orchestrator-context.md`/`docs/review-gate-seam.md` and assert it STILL fails, AND iterate `CORE_DOC_RELPATHS` asserting none is exempted. This is the over-broad-exemption guard the brief §5 demands.

**How each of the three structural guards is scoped to CORE via this model:**
1. **`genericity_guard.scan_tree`** — a single early `if gl.is_instance_surface(norm): continue` BEFORE the forbidden-term/ticker loops, so the vocab + ticker bans apply only to CORE files. The substrate-seam sub-check (the `SUBSTRATE_FORBIDDEN_RELPATHS` block) targets `docs/review-gate-seam.md`, a CORE file never on the instance surface, so it is unaffected and stays.
2. **`manifest_accounting.test_every_tracked_file_is_manifest_or_support`** — a new accounting branch `if gl.is_instance_surface(rel): continue`, so an instantiated file (a brief, a `<role>-state.md`, the seam-3 fill) is accounted-for as instance surface rather than failing the "manifest OR support" partition.
3. **`test_dependency_posture`** — already CORE-scoped via `_corefiles.CORE_RELPATHS` (the AST belt + the subprocess probe both iterate `existing_core_files()` only). No instance-surface file is ever in `CORE_RELPATHS`, so an instance file importing third-party is structurally never scanned. The plan ADDS a distinguishing test proving this (instance third-party import passes; a core third-party import fails) and documents the invariant in `_corefiles.py`.

---

## 2. Split judgment

**Recommendation: BATCH (single executing pass), with a fixed internal task order.** Rationale:
- B-9 and B-12 Gap 2 are tightly coupled — Gap 2 IS a registration into B-9's `INSTANCE_SURFACE_*`. Splitting would force Gap 2 to either re-derive the model or wait, with no isolation benefit.
- B-12 Gap 1 (hook single-source) and Gap 3 (charter wording) are independent and small (one code module + one doc), low blast-radius, and naturally fall AFTER the B-9 model lands.
- Total surface: ~6 source/doc files + ~6 new/edited test methods. This is a moderate, cohesive arc — comparable to prior single-arc scaffold passes. The keystone risk is in B-9's scoping correctness (a wrong scoping re-blocks every germination OR leaks contamination); that risk is contained by the distinguishing tests, not by splitting.

If the executing implementer hits unexpected friction in B-9 (e.g. the pattern-matching introduces a real over-broad-exemption that resists a tight fix), it may land B-9 (Tasks 1–6) as a first mergeable unit and B-12 (Tasks 7–9) as a second — the task boundaries below are split-clean. Flag any such split to the orchestrator.

---

## 3. The ordered TDD tasks

Each task is red→green→commit. Run `python -m unittest discover -s tests` (or the named module for speed) to SEE red, then green. Ground every line anchor against live code at edit time (line numbers below are from `7f3f7c0` and may drift). Test files in harness-template are NOT ruff-gated (the scaffold ships no `swing/`); match each file's existing stdlib-`unittest` style.

### Task 1 — B-9 core: ship the instance-surface model (`is_instance_surface` + lists)

**File:** `tests/genericity_lists.py`. Append a new section "(d) INSTANCE customization: the instance surface (vocab bans are CORE-only)" after `SELF_EXCLUDE_RELPATHS` (after live line 142). Adapt coa-chess `9aee81d`'s block to the template's generic state:

```python
# --- (d) INSTANCE customization: the instance surface (vocab bans are CORE-only) -
# The template's vocabulary + ticker bans keep the reusable CORE application-
# agnostic and free of extraction residue, so they are scoped to the CORE. The
# instance SURFACE -- the files that ARE the germinated application (APPLICATION.md,
# the domain implementer cells, the briefs, the seam-3 fill, a peer director's
# state / context docs) -- is application content BY DESIGN and is EXEMPT from the
# vocabulary + ticker bans entirely (see scan_tree). The CORE keeps FULL teeth: an
# app term OR swing/finance residue in role_mail.py, the hooks, or the generic
# contract docs still FAILS (distinguishing test test_vocab_bans_are_core_only).
# These are PATTERNS (the template ships no concrete app/role name): <app> and
# <role> are filled at germination.
#
# FUTURE-SAFE SCOPING (R4 Major fix): the instance PATTERNS below
# (docs/<role>-state.md / docs/<role>-context.md / docs/review-gate-<app>.md) are
# gated by the EXPLICIT CORE-doc registry CORE_DOC_RELPATHS. A `docs/*.md` file is
# instance surface ONLY when it matches an instance pattern AND is NOT a shipped
# CORE doc. So adding a NEW core doc named, e.g., docs/comms-context.md does NOT
# silently stop being scanned -- a new core doc MUST be added to CORE_DOC_RELPATHS
# (a deliberate, reviewed act the manifest gate ALSO forces), and being registered
# keeps it CORE-scanned. The pattern matcher never exempts a registered core doc.
# Two DISJOINT sets, never blurred (R6 Major 1 fix):
#   CORE_DOC_RELPATHS    = the reusable-kernel docs/ files (NEVER instance surface).
#   INSTANCE_STUB_RELPATHS = docs/ files that ship as a template stub but ARE
#                            instance surface (filled/overwritten at germination).
# charc-state.md is an INSTANCE STUB, NOT core -- it lives in INSTANCE_STUB_RELPATHS
# only. The manifest cross-check (test_manifest_accounting) accounts for BOTH sets
# against the manifest's docs/*.md, so neither blurs the other.
CORE_DOC_RELPATHS: frozenset[str] = frozenset({
    "docs/charc-charter.md",
    "docs/charc-bootstrap.md",
    "docs/orchestrator-context.md",
    "docs/dispatch-recipe.md",
    "docs/review-gate-seam.md",
    "docs/codex-reviewer.md",
    "docs/comms-orchestrator-registry.md",
})

# docs/ files shipped as a template stub but that ARE instance surface once filled.
INSTANCE_STUB_RELPATHS: tuple[str, ...] = (
    "docs/charc-state.md",  # the §5.1 state pointer (overwritten with live state)
)

INSTANCE_SURFACE_RELPATHS: tuple[str, ...] = (
    "APPLICATION.md",
) + INSTANCE_STUB_RELPATHS
INSTANCE_SURFACE_PREFIXES: tuple[str, ...] = (
    "docs/briefs/",
)


def is_instance_surface(relpath: str) -> bool:
    """True iff relpath is germination instantiation surface (not harness core).

    Exempt from the vocabulary + ticker bans + counted as instance surface in the
    manifest. The explicit RELPATHS/PREFIXES are unconditional; the docs/ suffix
    PATTERNS are gated by CORE_DOC_RELPATHS so a registered core doc is NEVER
    exempted (future-safe -- a new core doc is added to CORE_DOC_RELPATHS, a
    deliberate reviewed act). PATTERNS cover instance files that do not exist on a
    bare clone:
      - docs/review-gate-<app>.md  (the seam-3 concrete fill; NOT review-gate-seam.md)
      - docs/<role>-state.md       (a peer director's state pointer; parallel of charc-state.md)
      - docs/<role>-context.md     (a peer director's instance-authority doc; NOT orchestrator-context.md)
      - .claude/agents/implementer-*.md  (domain cells; NOT implementer-template.md)
    """
    rel = relpath.replace("\\", "/")
    # Explicit instance relpaths (incl. the shipped charc-state.md stub) + prefixes.
    if rel in INSTANCE_SURFACE_RELPATHS:
        return True
    if any(rel.startswith(p) for p in INSTANCE_SURFACE_PREFIXES):
        return True
    # A registered CORE doc is NEVER instance surface, even if it matches a
    # suffix pattern below (the future-safe gate -- not a hardcoded 2-item denylist).
    if rel in CORE_DOC_RELPATHS:
        return False
    # docs/ suffix patterns (review-gate-<app> / <role>-state / <role>-context),
    # reached ONLY for a docs/ file that is NOT a registered core doc:
    if rel.startswith("docs/") and rel.endswith(".md") and (
            rel.startswith("docs/review-gate-")
            or rel.endswith("-state.md")
            or rel.endswith("-context.md")):
        return True
    # Domain implementer cells (seam-2 fills): every implementer-*.md EXCEPT the
    # shipped generic template.
    if (rel.startswith(".claude/agents/implementer-")
            and rel != ".claude/agents/implementer-template.md"):
        return True
    return False
```

**Note on ordering inside `is_instance_surface`:** `docs/charc-state.md` is an INSTANCE_STUB_RELPATH (folded into `INSTANCE_SURFACE_RELPATHS`), returning True at the first check. It is NOT in `CORE_DOC_RELPATHS` (the two sets are disjoint — R6 Major 1), so there is no blur: the stub is instance surface, full stop. Every registered core doc (`charc-charter.md`, `orchestrator-context.md`, `review-gate-seam.md`, …) is NOT in `INSTANCE_SURFACE_RELPATHS`, so it falls to the `CORE_DOC_RELPATHS` gate and returns False — never matching the suffix patterns. This is the explicit-registry design Codex R4 asked for: the suffix patterns can ONLY exempt a `docs/` file that the core registry does not claim.

> **Single-source the doc partition across the two gates (R4/R6 future-safe).** `test_manifest_accounting.py` imports `gl.CORE_DOC_RELPATHS` + `gl.INSTANCE_STUB_RELPATHS` and asserts their UNION equals the `docs/*.md` subset of `SHIPPED_MANIFEST`, with the two sets DISJOINT (a cross-check test — see Task 4). So the genericity guard's notion of "core docs vs instance stubs" and the manifest's notion cannot drift. Adding a new core doc means adding it to BOTH the manifest and `CORE_DOC_RELPATHS`; the cross-check FAILS if a new manifest doc is forgotten in either set, surfacing the over-broad-exemption risk at build time rather than silently.

**TDD:** This task ships the data + predicate with no behavior change yet (scan_tree/manifest still ignore it). Add a unit test asserting the predicate's classification directly. Create `tests/test_instance_surface.py`:

- `is_instance_surface("APPLICATION.md")` → True
- `is_instance_surface("docs/charc-state.md")` → True
- `is_instance_surface("docs/briefs/arc-1.md")` → True
- `is_instance_surface("docs/review-gate-myapp.md")` → True
- `is_instance_surface("docs/rd-state.md")` → True (peer director state)
- `is_instance_surface("docs/rd-context.md")` → True (peer director context)
- `is_instance_surface(".claude/agents/implementer-fast.md")` → True
- **Core-exclusion (over-broad guard):** `is_instance_surface("docs/review-gate-seam.md")` → **False**; `is_instance_surface("docs/orchestrator-context.md")` → **False**; `is_instance_surface(".claude/agents/implementer-template.md")` → **False**; `is_instance_surface("scripts/role_mail.py")` → **False**; `is_instance_surface("docs/charc-charter.md")` → **False**.
- **Future-safe registry gate (R4):** EVERY registered core doc stays core — assert `is_instance_surface(d)` is **False** for every `d in gl.CORE_DOC_RELPATHS`. (Now clean: the two sets are disjoint, so no exception is needed — `charc-state.md` is NOT in `CORE_DOC_RELPATHS`.) This proves the suffix patterns cannot exempt a registered core doc.
- **Executable pattern-vs-registry boundary (R6 Major 2):** fabricate a NEW core-like path that MATCHES a suffix pattern but is NOT in `CORE_DOC_RELPATHS`, and assert the model's behavior is the DESIGNED one — i.e. it IS exempt (treated as a germinated instance doc) UNTIL registered as core. Concretely:
  - `is_instance_surface("docs/comms-context.md")` → **True** (an UNregistered `docs/*-context.md` is instance surface — the intended new-instance-doc path).
  - The PROTECTION against a forgotten NEW CORE doc is the manifest cross-check (Task 4): a doc that SHOULD be core must be in BOTH the manifest and `CORE_DOC_RELPATHS`; the cross-check FAILS loud if a manifest `docs/*.md` is missing from `CORE_DOC_RELPATHS ∪ INSTANCE_STUB_RELPATHS`. So the boundary is: "a suffix-matching `docs/` doc is instance surface unless explicitly registered as a core doc, and the manifest gate forces a real core doc to be registered." Add an explicit assertion in `tests/test_instance_surface.py` that a fabricated unregistered `docs/foo-context.md` is instance surface AND that a registered core `docs/orchestrator-context.md` is not — the two sides of the boundary, executable.

**Arithmetic (FAIL-pre / PASS-post):** PRE-task the symbol `is_instance_surface` does not exist → the test file fails at import (`AttributeError`/`ImportError`) → RED. POST-task the predicate exists and classifies as asserted → GREEN. The core-exclusion assertions FAIL any implementation that matched `docs/review-gate-seam.md` or `docs/orchestrator-context.md` (or a future core doc) by bare prefix/suffix without the `CORE_DOC_RELPATHS` gate — distinguishing the future-safe scoping. The registry-gate iteration FAILS an impl that used a hardcoded 2-item denylist (it would wrongly exempt a third registered core doc). The pattern-vs-registry boundary assertion makes the "exempt-until-registered" semantic executable, not just documented (R6 Major 2).

**Commit:** `feat(guards): B-9 — ship the is_instance_surface model + INSTANCE_SURFACE lists`

**Contamination self-cert:** adds DATA + a predicate; no CORE file gains a term; the lists hold only patterns/placeholders + two existing template stubs.

---

### Task 2 — B-9 point 1+2: scope the genericity guard's vocab/ticker bans to CORE

**File:** `tests/test_genericity_guard.py`, `scan_tree` (live lines 69–120).

**TDD (write the distinguishing test FIRST — see it RED):** Replace the live `GuardSelfTest` self-test set as needed and ADD the binding distinguishing test `test_vocab_bans_are_core_only` (adapted from coa-chess `9aee81d`). The `_scan_fixture` helper (live lines 128–137) already builds a throwaway tree and calls `scan_tree` on its relpaths — reuse it:

```python
def test_vocab_bans_are_core_only(self) -> None:
    # The vocabulary + ticker bans protect the reusable CORE; the instance
    # surface is application content and is EXEMPT. Distinguishing:
    #   - an app term OR residue term in a CORE file FAILS (full teeth);
    #   - the SAME terms on the instance surface PASS (app content by design).
    core_app = self._scan_fixture(
        {"scripts/role_mail.py": "# a comment about chess strategy"})
    self.assertTrue(any("chess" in v for v in core_app),
                    "an app term leaking into a core file must STILL fail")
    core_residue = self._scan_fixture(
        {".claude/hooks/session_start.py": "# mentions swing trading"})
    self.assertTrue(any("swing" in v for v in core_residue),
                    "a residue term leaking into a core file must STILL fail")
    core_ticker = self._scan_fixture(
        {"docs/charc-charter.md": "the SPY benchmark"})
    self.assertTrue(any("SPY" in v for v in core_ticker),
                    "a residue ticker in a core file must STILL fail")
    surface = self._scan_fixture(
        {"APPLICATION.md": "this is about chess and even mentions swing and SPY"})
    self.assertEqual(surface, [],
                     "the instance surface is exempt from the vocabulary+ticker bans")

def test_over_broad_exemption_guard(self) -> None:
    # The registered CORE docs are NOT exempted even though some match an
    # instance suffix pattern: an app term in the mechanism-agnostic seam
    # contract, the generic orchestrator kernel, OR any other CORE_DOC_RELPATHS
    # member still FAILS (the future-safe registry gate, not a 2-item denylist).
    for core_doc in ("docs/review-gate-seam.md", "docs/orchestrator-context.md"):
        out = self._scan_fixture({core_doc: "about chess"})
        self.assertTrue(any("chess" in v for v in out),
                        f"{core_doc} is core (registered), not instance surface")
    # Every registered core doc stays core-scanned (the two sets are disjoint,
    # so no exception needed -- charc-state.md is an instance stub, not core).
    for core_doc in gl.CORE_DOC_RELPATHS:
        self.assertFalse(gl.is_instance_surface(core_doc),
                         f"{core_doc} is registered core, must stay scanned")
    # An UNregistered docs/ doc matching a suffix pattern IS instance surface
    # (the designed exempt-until-registered boundary -- R6 Major 2):
    self.assertTrue(gl.is_instance_surface("docs/comms-context.md"),
                    "an unregistered docs/*-context.md is instance surface")
```

Run → RED: with the un-modified `scan_tree`, the `surface` assertion FAILS (an `APPLICATION.md` with "chess"/"swing"/"SPY" currently produces violations — the whole-tree scan has no instance exemption).

**Implementation:** in `scan_tree`, after computing `norm = rel.replace("\\", "/")` (live line 98), insert BEFORE the `_FORBIDDEN_PATTERNS`/`_TICKER_PATTERNS` loops:

```python
        # Instance surface = application content; exempt from the vocabulary +
        # ticker bans entirely (those protect the reusable CORE). The CORE below
        # still carries the FULL ban; the substrate-seam check targets review-
        # gate-seam.md (core), never an instance-surface file.
        if gl.is_instance_surface(norm):
            continue
```

Also update the `scan_tree` docstring (live lines 71–84) to state the instance-surface exemption (adapt coa-chess `9aee81d`'s docstring edit). Run → GREEN: `surface` now returns `[]`; the core fixtures still trip; the seam/orchestrator-context fixtures still trip.

**Arithmetic (FAIL-pre / PASS-post):**
- `test_vocab_bans_are_core_only` — PRE: `surface` assertion expects `[]` but `scan_tree` returns `["APPLICATION.md: forbidden term 'chess'", …]` → RED. POST: the `continue` skips instance surface → `[]` → GREEN. The CORE fixtures (chess/swing/SPY in core files) trip in BOTH paths (the bans are unchanged for CORE) — so the test distinguishes ONLY the exemption, and a no-op "exempt nothing" impl FAILS the surface assertion while a too-broad "exempt everything" impl FAILS the core assertions.
- `test_over_broad_exemption_guard` — PRE: passes trivially (whole-tree scan trips both). POST: still passes because the core-exclusion set keeps the seam + orchestrator-context core-scanned. A regression that exempted `review-gate-*` or `*-context.md` WITHOUT the exclusion set would FAIL this → it is the over-broad guard.

**Note — WholeTreeGuardTest stays GREEN throughout (no regression):** the live tracked tree has no instance-surface files filled with domain vocab (the stubs `APPLICATION.md`/`charc-state.md` are empty-by-design), so exempting them changes nothing for the real tree. `test_whole_tracked_tree_is_clean` (live line 205) and `GuardSelfExclusionTest` remain green.

**Commit:** `refactor(guards): B-9 — scope genericity vocab/ticker bans to the core (instance surface exempt)`

**Contamination self-cert:** the CORE keeps the FULL ban (proven by `test_vocab_bans_are_core_only` + `test_over_broad_exemption_guard`); only application content on the designed instance surface is exempt; no term enters a core file.

---

### Task 3 — B-9 point 3: residue/ticker bans become CORE-only (one-shot extraction artifact, retired tree-wide)

**Premise check + decision.** Brief §1 point 3: "Run once at authoring, or CORE-only — not a permanent tree-wide gate." coa-chess `9aee81d` realized this via the SAME instance-surface exemption (residue/ticker terms stop tripping plain-English INSTANCE docs but stay caught in CORE as "a cheap upstream-hygiene belt"). **This plan adopts the CORE-only realization** delivered by Task 2 — there is NO separate mechanism. Task 2's `if gl.is_instance_surface(norm): continue` already exempts BOTH the `_FORBIDDEN_PATTERNS` (vocab) AND the `_TICKER_PATTERNS` (residue tickers SPY/QQQ/NDX/SPX/RUT) on the instance surface, while keeping them tree-wide on CORE.

**Why CORE-only, not "delete entirely / run-once-at-authoring":** removing the residue/ticker bans from the tracked suite altogether would lose the upstream-hygiene belt that catches a residue copy-paste into a CORE file (the very contamination the §3 contamination guard protects). The coa-chess-converged answer keeps them as a CORE belt. The brief offers "Run once at authoring OR CORE-only" — CORE-only is the lower-risk, reference-impl-validated choice and is what Task 2 delivers. **This task is therefore a NO-CODE confirmation task folded into Task 2** — but it carries one explicit assertion to lock the intent.

**TDD (the point-3 lock test):** in `tests/test_genericity_guard.py`, the `test_vocab_bans_are_core_only` test (Task 2) already asserts `SPY` trips in a CORE file and that an instance-surface file mentioning `SPY` passes — that IS the residue-ticker CORE-only proof. No additional code. (If the executing implementer prefers an explicit standalone test, add `test_residue_ticker_core_only` mirroring the ticker assertions; optional, same arithmetic.)

**Documentation:** update the module docstring of `tests/genericity_lists.py` (the section describing `FORBIDDEN_TICKERS`, live lines 65–75) to note the bans are now CORE-scoped (the clean-room extraction belt protects the core, not the application content layered on top). Adapt the WHY-CLOSED prose — it stays accurate; append one sentence that the bans are core-only post-B-9.

**Arithmetic:** covered by Task 2's `test_vocab_bans_are_core_only` (SPY-in-core FAILS pre+post since CORE is unchanged; SPY-on-surface FAILS pre, PASSES post). No new failing-then-passing cycle beyond Task 2.

**Commit:** folded into Task 2 (no separate commit) OR `docs(guards): B-9 point 3 — note residue/ticker bans are core-only` if a doc-only delta is made. The executing implementer SHOULD fold this into Task 2 to avoid an empty-delta commit.

**Contamination self-cert:** residue/ticker bans REMAIN on CORE (full teeth); only the application content layer is exempt. The template's denylist still carries the example-app + finance terms as DATA (the guard's contract), unchanged — but they now bind on CORE only, which is exactly "not a permanent tree-wide gate."

---

### Task 4 — B-9 point 1 (manifest half): scope manifest accounting to CORE

**File:** `tests/test_manifest_accounting.py`, `test_every_tracked_file_is_manifest_or_support` (live lines 78–94).

**TDD (the production test IS the distinguishing witness — R1 Major 1 fix).** A test that calls `gl.is_instance_surface()` directly, OR re-implements the partition logic inline, goes GREEN as soon as Task 1 lands EVEN IF the production method `test_every_tracked_file_is_manifest_or_support` is never edited — that is a false-green on the real gate (Codex R1 Major 1, accepted). The fix: drive the REAL production method with a simulated tracked set so the only way it passes is by EXECUTING its new `if gl.is_instance_surface(rel): continue` branch.

The production method (live lines 78–94) computes `unaccounted` from `_tracked()` (the module-level git-`ls-files` helper, live lines 51–55). Refactor the partition into a callable the test can drive, OR patch `_tracked`. Recommended: extract the partition into a small module-level helper `_unaccounted(tracked: set[str]) -> list[str]` that the production test calls (`self.assertEqual(_unaccounted(_tracked()), [])`), and have the new branch live INSIDE `_unaccounted`. Then the distinguishing test drives the SAME helper with a simulated instance file:

```python
def test_production_partition_accounts_instance_surface(self) -> None:
    # Drive the REAL partition helper (the one the production gate uses) with a
    # simulated filled-germination tracked set. It yields [] ONLY because the
    # helper executes `if gl.is_instance_surface(rel): continue`. WITHOUT that
    # branch the instance file is unaccounted (the pre-fix path), so this test
    # FAILS pre-fix and PASSES post-fix -- the production method is the witness.
    simulated = set(SHIPPED_MANIFEST) | SUPPORT_CONFIG | {
        "docs/briefs/arc-1.md", "docs/review-gate-myapp.md",
        ".claude/agents/implementer-fast.md",
    }
    self.assertEqual(_unaccounted(simulated), [],
                     "the production partition must account instance surface")
```

If the executing implementer prefers NOT to refactor a helper, the equivalent is to `mock.patch.object(mod, "_tracked", return_value=<simulated set>)` and call the bound production test method itself (`ManifestAccountingTest("test_every_tracked_file_is_manifest_or_support").debug()` or invoke its body) so the assertion runs over the simulated tree through the REAL branch. Either way the binding requirement is: **the test exercises the production code path, not a re-implementation or a bare `is_instance_surface()` call** (Codex R1 Major 1).

**Arithmetic (FAIL-pre / PASS-post — proven through the production path):** PRE-fix the production partition has no `is_instance_surface` clause, so over the simulated set `_unaccounted` returns `["docs/briefs/arc-1.md", "docs/review-gate-myapp.md", ".claude/agents/implementer-fast.md"]` (non-empty) → the test's `assertEqual(..., [])` FAILS → RED. POST-fix the branch skips them → `[]` → GREEN. Because the test calls the PRODUCTION helper, it cannot go green until the production branch is added (closing the false-green Codex flagged). The real-tree `test_every_tracked_file_is_manifest_or_support` stays GREEN both pre and post (no filled instance files on the real tree).

**Implementation:** add `import genericity_lists as gl` at the module top (live line 13 area — coa-chess added exactly this import). Then add the instance-surface branch to the partition (adapt coa-chess `ec9856d`):

```python
            if gl.is_instance_surface(rel):
                continue  # the instantiation surface (see genericity_lists.py)
```

placed after the `tests/` branch (live line 89). Update the method comment + the failure message to mention instance surface (coa-chess `ec9856d` did this verbatim).

**To make the production path testable (the R1 Major 1 fix), extract the partition into a module-level helper** so the distinguishing test drives the SAME code the gate runs:

```python
def _unaccounted(tracked: set[str]) -> list[str]:
    """The files in `tracked` that are neither manifest, support, nor instance
    surface (the partition the gate asserts is empty). The single accounting
    model -- the gate AND the distinguishing test both go through here."""
    out = []
    for rel in sorted(tracked):
        if rel in SHIPPED_MANIFEST or rel in SUPPORT_CONFIG:
            continue
        if rel.startswith("tests/"):
            continue
        if gl.is_instance_surface(rel):
            continue
        out.append(rel)
    return out
```

and have `test_every_tracked_file_is_manifest_or_support` call `self.assertEqual(_unaccounted(_tracked()), [], ...)`. The instance-surface branch lives ONLY inside `_unaccounted` (one place), so the simulated-set test and the real gate exercise identical logic.

**Add the CORE-doc single-source cross-check (R4 future-safe):** `gl.CORE_DOC_RELPATHS` (Task 1) is the genericity guard's notion of "which docs/ files are reusable kernel"; the manifest's `SHIPPED_MANIFEST` is the manifest's notion. They MUST NOT drift, or a new core doc could be manifest-tracked yet exempted by the suffix patterns. Add:

```python
def test_doc_partition_matches_manifest_docs(self) -> None:
    # Single-source: the guard's docs/ partition (CORE_DOC_RELPATHS +
    # INSTANCE_STUB_RELPATHS) must, as a DISJOINT union, equal the docs/*.md
    # subset of the shipped manifest. If a new manifest doc is added but
    # forgotten in BOTH guard sets, the suffix patterns could wrongly exempt it
    # -- this cross-check FAILS loud at build time (R4 + R6 Major 1 fix).
    import genericity_lists as gl
    manifest_docs = {m for m in SHIPPED_MANIFEST
                     if m.startswith("docs/") and m.endswith(".md")}
    core = set(gl.CORE_DOC_RELPATHS)
    stub = set(gl.INSTANCE_STUB_RELPATHS)
    self.assertEqual(core & stub, set(),
                     "CORE_DOC_RELPATHS and INSTANCE_STUB_RELPATHS must be disjoint")
    self.assertEqual(core | stub, manifest_docs,
                     "the docs/ partition (core + instance-stub) must equal the "
                     "manifest's docs/*.md set (single source; no drift)")
```

**Arithmetic for the cross-check:** at `7f3f7c0` the manifest's `docs/*.md` set is exactly the 8 docs (`charc-charter`, `charc-bootstrap`, `charc-state`, `orchestrator-context`, `dispatch-recipe`, `review-gate-seam`, `codex-reviewer`, `comms-orchestrator-registry`). Task 1 seeds `CORE_DOC_RELPATHS` with 7 of them and `INSTANCE_STUB_RELPATHS` with `charc-state.md`; their disjoint union = all 8 → GREEN. The test FAILS if a future arc adds a manifest doc to neither guard set (the drift Codex R4 warned about) OR puts the same path in both (the blur Codex R6 Major 1 flagged) — it is the future-safe + no-blur witness.

**Arithmetic (FAIL-pre / PASS-post):** the SIMULATED-tracked-set test computes `unaccounted` two ways — WITH `is_instance_surface` (post-fix logic) → `[]`; the pre-fix logic (no `is_instance_surface` clause) over the same simulated set → `["docs/briefs/arc-1.md", …]` (non-empty). The test asserts the post-fix `[]`, so it FAILS if the branch is absent and PASSES when present. The real-tree `test_every_tracked_file_is_manifest_or_support` stays GREEN both pre and post (no filled instance files on the real tree).

**Commit:** `refactor(guards): B-9 — account instance-surface files in the manifest partition`

**Contamination self-cert:** the manifest still requires the 19 CORE manifest files to exist (`test_every_shipped_manifest_file_exists`, `test_manifest_count_is_nineteen` unchanged); only INSTANTIATED files gain an accounting category. No CORE file is reclassified.

---

### Task 5 — B-9 point 1 (doc-acceptance half): APPLICATION.md accepts bare-clone AND instantiated

**File:** `tests/test_doc_acceptance.py`, `ApplicationStubAcceptanceTest` (live lines 89–108).

**TDD:** the live test hard-asserts "empty by design" (line 100–102) and only 3 fill markers (line 106). A FILLED `APPLICATION.md` (no longer empty-by-design, carrying real domain content) would FAIL `test_marked_empty_by_design`. Add a test simulating the instantiated state and prove the converted test accepts it. Adapt coa-chess `ec9856d`'s conversion (rename class → `ApplicationAcceptanceTest`):

```python
class ApplicationAcceptanceTest(unittest.TestCase):
    """A.3 -- APPLICATION.md: the seam-1 stub on a bare clone, the filled instance
    definition once the interview runs. Accepts BOTH states (via the shared
    application_acceptance_violations helper, below)."""

    def setUp(self) -> None:
        self.text = _read("APPLICATION.md")

    def test_carries_seam1_marker(self) -> None:
        self.assertIn("SEAM 1", self.text)

    def test_live_application_is_acceptable(self) -> None:
        # The LIVE APPLICATION.md (bare-clone stub or filled instance) is
        # acceptable -- routed through the SAME helper the simulated-payload
        # tests use, so the real tree stays green through identical logic.
        self.assertEqual(application_acceptance_violations(self.text), [],
                         "the live APPLICATION.md must be an acceptable state")
```

> **R2 Major fix — the conversion MUST be proven on a SIMULATED filled payload (not the live file).** `test_instantiated_is_not_the_stub` as written reads the LIVE `APPLICATION.md`; on the bare-clone tree the empty-by-design line IS present → `looks_instantiated` is False → the assertion is SKIPPED → the test trivially passes BOTH pre- and post-change. It NEVER exercises a filled `APPLICATION.md`, so it does NOT distinguish the conversion (Codex R2 Major 1+2, accepted). The acceptance-logic change is the most important part of Task 5 and must be witnessed against a filled document.
>
> **Refactor the acceptance assertions into a text-taking helper + drive it with a simulated filled doc.** Extract the dual-state acceptance into a module-level `_assert_application_acceptable(test, text)` (or a free function returning violations) that the live-file test AND a simulated-payload test both call:

```python
# Module-level, in test_doc_acceptance.py. Returns [] iff `text` is an
# acceptable APPLICATION.md (bare-clone stub OR filled instance); else the
# reasons. Two EXPLICIT valid states + reject the mixed/partial state (R3+R5
# Major fix: an explicit state model, not a residual-fragment heuristic that
# reviewers keep misreading). The stub MARKER is the full declaration sentence
# "this file is empty by design".
def application_acceptance_violations(text: str) -> list[str]:
    lower = text.lower()
    out = []
    if "SEAM 1" not in text:
        out.append("missing the seam-1 marker")

    stub_marker = "this file is empty by design"
    is_stub = stub_marker in lower
    fill_markers = ("what the project does", "domain", "success criteria")
    has_all_fill_sections = all(m in lower for m in fill_markers)

    if is_stub:
        # Valid STATE A -- the bare-clone stub. It legitimately carries the stub
        # marker AND the placeholder fill-section headings; that is acceptable.
        # No further checks (the stub is a complete, valid state). ACCEPTED.
        return out
    # Not the stub -> must be the INSTANTIATED state. Valid STATE B requires the
    # fill sections present (real content) AND no residual bare stub fragment.
    if not has_all_fill_sections:
        for m in fill_markers:
            if m not in lower:
                out.append(f"instantiated APPLICATION.md missing fill section {m!r}")
    if "empty by design" in lower:
        # The full stub sentence is gone but a residual "empty by design"
        # fragment remains -> the illegal half-edit / mixed state.
        out.append("instantiated APPLICATION.md leaves a residual 'empty by "
                   "design' fragment (the stub declaration was half-removed)")
    return out


class ApplicationSimulatedPayloadTest(unittest.TestCase):
    """The conversion is witnessed on simulated payloads (R2 Major fix)."""

    def test_filled_instance_payload_is_accepted(self) -> None:
        # A FILLED APPLICATION.md (no empty-by-design line, real domain content)
        # is accepted by the converted logic. The OLD stub-only gate
        # (assertIn "empty by design") would REJECT this exact payload -- that is
        # the pre/post witness the live-file test cannot provide.
        filled = ("<!-- SEAM 1 -->\n# MyApp\n"
                  "## What the project does\nA real thing.\n"
                  "## Domain\nThe domain.\n## Success criteria\nShips.\n"
                  "## Constraints\nNone.\n")
        self.assertEqual(application_acceptance_violations(filled), [],
                         "the converted acceptance must accept a filled instance")
        # Witness the distinguishing delta: the OLD gate required the line.
        self.assertNotIn("empty by design", filled.lower())  # OLD gate would FAIL here

    def test_bare_clone_stub_payload_is_accepted(self) -> None:
        # The bare-clone stub (still empty-by-design) stays acceptable -- the
        # conversion does NOT weaken the stub state.
        stub = ("<!-- SEAM 1 -->\n# APPLICATION (stub)\n"
                "This file is empty by design.\n"
                "## What the project does\n_(placeholder)_\n## Domain\n_()_\n"
                "## Success criteria\n_()_\n")
        self.assertEqual(application_acceptance_violations(stub), [],
                         "the bare-clone stub must still be accepted")

    def test_filled_doc_that_still_declares_stub_is_rejected(self) -> None:
        # A filled doc that LEAVES a residual 'empty by design' fragment is caught.
        bad = ("<!-- SEAM 1 -->\n# MyApp\nreal content but also: empty by design\n"
               "## What the project does\nx\n## Domain\nx\n## Success criteria\nx\n")
        # is_stub False (no full 'this file is empty by design' sentence) + a
        # residual bare 'empty by design' fragment present => a violation.
        self.assertTrue(application_acceptance_violations(bad),
                        "a filled doc still carrying empty-by-design must be caught")
```

> The live-file `ApplicationAcceptanceTest` then calls `self.assertEqual(application_acceptance_violations(self.text), [])` so the REAL tree (bare-clone stub) stays green through the same logic.

> **Grounding (VERIFIED on disk at `7f3f7c0`).** The live `APPLICATION.md` carries `<!-- SEAM 1: ... -->` (line 1), the full stub sentence "**This file is empty by design.**" (line 5), and all four fill sections ("What the project does" / "Domain" / "Success criteria" / "Constraints / invariants", lines 18/19/21/24). So the live file is the STUB state → the helper returns `[]` → `test_live_application_is_acceptable` is GREEN on the bare clone. The helper's `fill_markers` use the 3 markers the live `test_has_interview_fill_structure` already checks (`constraints` exists live as "Constraints / invariants" but is NOT in the live 3-marker check — keep the helper to the established 3 to avoid coupling the gate to a 4th marker; the simulated `filled` fixture may include a Constraints heading freely since it is authored). If a future template edit removes the stub sentence, re-confirm the keying phrase. The bare-clone green is binding.

**Arithmetic (FAIL-pre / PASS-post — proven on simulated payloads):**
- `test_filled_instance_payload_is_accepted` — the helper `application_acceptance_violations` does NOT exist pre-Task-5 → the test fails at call (`NameError`) → RED. Even with the helper, a stub-ONLY acceptance (the OLD `assertIn "empty by design"` logic ported into the helper) would return a violation for the filled payload (no empty-by-design line) → RED. Only the CONVERTED dual-state helper returns `[]` for the filled payload → GREEN. This is the witness the live-file test cannot give: a FILLED document is exercised.
- `test_bare_clone_stub_payload_is_accepted` — the stub payload has the full stub sentence → `is_stub` True → the helper returns early with `[]` → GREEN; proves the conversion did not weaken the stub state.
- `test_filled_doc_that_still_declares_stub_is_rejected` — `is_stub` False + a residual `empty by design` fragment → a violation → `assertTrue(violations)` GREEN; proves the dual-state logic still catches a half-converted doc (non-trivial).
- The live-file `ApplicationAcceptanceTest` stays GREEN on the real bare-clone tree (`is_stub` True → accepted). The OLD `test_marked_empty_by_design` is REMOVED (it would RED a filled tree); its protection (the stub must self-declare) is preserved by `test_bare_clone_stub_payload_is_accepted` + the live-file check.

**Note — `test_seam3_defaults.py` is NOT touched.** It parses `docs/review-gate-seam.md`'s SEAM3-DEFAULTS block + asserts the seam doc names no concrete mechanism (lines 66–72). Because the seam-3 concrete FILL relocates to `docs/review-gate-<app>.md` (Task 6), the agnostic `review-gate-seam.md` stays pristine and `test_seam3_defaults` stays green unchanged. (This is the whole point of B-9 point 4.)

**Commit:** `test(guards): B-9 — APPLICATION.md acceptance covers bare-clone AND instantiated`

**Contamination self-cert:** no CORE content changes; the test now accepts an instantiated state without weakening the bare-clone stub assertion (the empty-by-design line is still required ON a bare clone).

---

### Task 6 — B-9 point 4: the `docs/review-gate-<app>.md` pointer convention

**Goal:** ship the convention so an instance's CONCRETE seam-3 fill lives in `docs/review-gate-<app>.md` (instance surface, Task 1 pattern) instead of polluting the mechanism-agnostic `docs/review-gate-seam.md` (which `test_seam3_defaults` + `genericity_guard` forbid a concrete mechanism in). coa-chess relocated its fill to `docs/review-gate-coa-chess.md` and reverted `review-gate-seam.md` pristine. The TEMPLATE has no fill to relocate (it ships pristine already) — so this task is the CONVENTION (docs), not a relocation.

**Files (doc-only):**
1. `docs/charc-bootstrap.md` — the seam-3 step (live lines 68–70) + the 5-step checklist item 3 (live lines 86–87). Add: "The concrete seam-3 fill (naming the project's real reviewer/gate) goes in a NEW `docs/review-gate-<app>.md` (an instance doc), NOT in `docs/review-gate-seam.md` — the agnostic contract stays pristine. `review-gate-seam.md` keeps the generic contract + the replaceable defaults."
2. `README.md` — the four-seams section (live lines 60–74), seam 3 bullet: note the concrete fill lives in `docs/review-gate-<app>.md`.
3. `docs/review-gate-seam.md` — add a short pointer line in the contract body (NOT in the SEAM3-DEFAULTS block, NOT naming a concrete mechanism): "A project's CONCRETE fill of these extension points lives in its own `docs/review-gate-<app>.md` instance doc (so this contract stays mechanism-agnostic); accept the shipped defaults until then."

> **Contamination check on the seam doc edit (load-bearing).** The added pointer line MUST NOT name a substrate term (`codex`/`WSL`/`Codex`) or a substrate-named path (`codex-reviewer.md`) — `test_doc_acceptance.py::ReviewGateSeamAcceptanceTest::test_no_substrate_token_no_codex_path` (lines 204–208) + `genericity_guard`'s SUBSTRATE_FORBIDDEN_RELPATHS block forbid them in `review-gate-seam.md`. The string `review-gate-<app>.md` is fine (`<app>` is a placeholder, not an app name; "app" is not a forbidden term). Verify the added line trips NEITHER gate by running `test_genericity_guard` + `test_seam3_defaults` + `test_doc_acceptance` after the edit.

**TDD:** add `tests/test_doc_acceptance.py` assertions binding the convention:
- `BootstrapAcceptanceTest` (live lines 260–294) → add `test_names_review_gate_app_convention`: `self.assertIn("review-gate-<app>", self.text)` (or `review-gate-` + a note about the instance doc).
- `ReviewGateSeamAcceptanceTest` (live lines 186–211) → add `test_points_at_instance_fill_doc`: assert the seam doc references the `review-gate-<app>.md` instance-fill convention AND still passes `test_no_substrate_token_no_codex_path` (unchanged).

**Arithmetic (FAIL-pre / PASS-post):** PRE-task the bootstrap + seam docs do NOT mention `review-gate-<app>` → the new assertions FAIL → RED. POST-task the convention is documented → GREEN. The existing `test_no_substrate_token_no_codex_path` stays GREEN (the added line names no substrate) — distinguishing an edit that wrongly introduced a concrete mechanism (which would RED that existing test).

**Commit:** `docs(seam): B-9 point 4 — the review-gate-<app>.md concrete-fill convention`

**Contamination self-cert:** `review-gate-seam.md` stays mechanism-agnostic + substrate-free (verified by the unchanged substrate test); the convention uses the `<app>` placeholder, no concrete project name.

---

### Task 7 — B-12 Gap 1: single-source the notice hook's role set off `role_mail.SINGULAR_INBOX_ROLES`

**Import-seam confirmation (verified on disk):** `scripts/role_mail.py` line 72 defines `SINGULAR_INBOX_ROLES = ("charc", "operator")`. The hook `.claude/hooks/user_prompt_submit.py` already guarded-imports its siblings from `session_start` (lines 41–56) and puts the hooks dir on `sys.path` (line 40). `role_mail.py` lives in `scripts/`, NOT on the hook's `sys.path`. The IMPORT SEAM is feasible by the SAME pattern `role_mail` itself uses to load `session_start` (`importlib.util.spec_from_file_location` by absolute path — `role_mail.py:192–199`): resolve `scripts/role_mail.py` from `__file__` (`.claude/hooks/user_prompt_submit.py` → repo root is `parent.parent.parent`, then `/ "scripts" / "role_mail.py"`) and load it guarded. **CONFIRMED: single-source is feasible; no fallback to the §8 dual-edit checklist is needed.**

**Files:** `.claude/hooks/user_prompt_submit.py`.

**Implementation:**
1. After the guarded `session_start` import block (live lines 41–56), add a guarded load of `role_mail` to source `SINGULAR_INBOX_ROLES` (mirroring the resilient-import discipline — never block a prompt):

```python
# Single-source the singular-inbox role set from the mail core (role_mail.py),
# so adding a peer director to role_mail's SINGULAR_INBOX_ROLES also makes the
# unread notice fire for it (B-12 Gap 1: no drift between delivery + notice).
# Loaded by path (scripts/ is not on the hooks sys.path) and guarded -- a hook
# must NEVER block a prompt, so a missing/broken role_mail degrades to the
# shipped default below.
_DEFAULT_SINGULAR_INBOX_ROLES = ("charc", "operator")
try:
    import importlib.util as _ilu
    _rm_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "role_mail.py"
    # Load under a PRIVATE module name (R6 Minor 1) so this hook-local read of
    # role_mail's constant cannot collide with / reuse a stale-or-partially-
    # initialized "role_mail" already on sys.modules in the hook process.
    _spec = _ilu.spec_from_file_location("_role_mail_hook", _rm_path)
    _rm = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_rm)
    SINGULAR_INBOX_ROLES = tuple(_rm.SINGULAR_INBOX_ROLES)
except Exception:  # noqa: BLE001 -- never block a prompt; degrade to the default
    SINGULAR_INBOX_ROLES = _DEFAULT_SINGULAR_INBOX_ROLES
```

2. Replace the hardcoded `COMMS_ROLES` (live line 60) with a derived value:

```python
# The roles whose inbox the unread notice surfaces: the singular-inbox directors
# (sourced from role_mail) PLUS the per-generation orchestrator. Single-sourced
# so a new peer director added to role_mail.SINGULAR_INBOX_ROLES is auto-covered.
COMMS_ROLES = SINGULAR_INBOX_ROLES + (REGISTERED_ROLE,)
```

(`REGISTERED_ROLE` is already imported from `session_start`, live line 44, = `"orchestrator"`.)

3. Replace the singular branch in `_inbox_for_role` (live line 82): `if role in ("charc", "operator"):` → `if role in SINGULAR_INBOX_ROLES:`.

**TDD (distinguishing tests FIRST — in `tests/test_user_prompt_submit_hook.py`):**

```python
def test_comms_roles_single_sourced_from_role_mail(self) -> None:
    # The notice hook's singular-inbox set IS the mail-core set (no drift).
    import importlib.util as ilu
    from _loader import REPO_ROOT  # or resolve role_mail path directly
    spec = ilu.spec_from_file_location(
        "role_mail", REPO_ROOT / "scripts" / "role_mail.py")
    rm = ilu.module_from_spec(spec); spec.loader.exec_module(rm)
    self.assertEqual(tuple(ups.SINGULAR_INBOX_ROLES), tuple(rm.SINGULAR_INBOX_ROLES))
    # COMMS_ROLES = the singular set + orchestrator.
    self.assertEqual(set(ups.COMMS_ROLES),
                     set(rm.SINGULAR_INBOX_ROLES) | {"orchestrator"})

def test_added_director_role_fires_the_notice(self) -> None:
    # Simulate adding a peer director to the mail-core set: the notice must fire
    # for it. Monkeypatch the hook's resolved set + the singular branch consumer.
    from unittest import mock
    inbox = self.root / "newdir" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "a.md").write_text("---\ntype: fyi\n---\nx", encoding="utf-8")
    with mock.patch.object(ups, "SINGULAR_INBOX_ROLES", ("charc", "operator", "newdir")), \
         mock.patch.object(ups, "COMMS_ROLES", ("charc", "operator", "newdir", "orchestrator")):
        note = ups.unread_notice("newdir", self.root, None)
    self.assertIsNotNone(note)
    self.assertIn("[comms] 1 unread for newdir", note)
```

> **Test-design grounding (verify the seam at execution time).** `unread_notice` → `_inbox_for_role` resolves `role in SINGULAR_INBOX_ROLES` to `root/<role>/inbox`. For the "added director fires" test, `_inbox_for_role`'s singular branch reads the MODULE-LEVEL `SINGULAR_INBOX_ROLES` (after Task-7 step 3), so patching `ups.SINGULAR_INBOX_ROLES` is sufficient. Confirm `_inbox_for_role` references the module global (not a closed-over local) — it does in the planned edit. The `_loader.py` helper (`load_user_prompt_submit`) is the existing import path the test module uses; reuse `REPO_ROOT` from `_loader` or `_corefiles` to locate `role_mail.py`.

**Arithmetic (FAIL-pre / PASS-post):**
- `test_comms_roles_single_sourced_from_role_mail` — PRE: `ups.SINGULAR_INBOX_ROLES` does not exist (the hook has only hardcoded `COMMS_ROLES`) → `AttributeError` → RED. POST: the symbol exists + equals `role_mail`'s → GREEN. A regression that re-hardcodes the set (drift) would make `COMMS_ROLES` diverge from `role_mail.SINGULAR_INBOX_ROLES | {orchestrator}` once a director is added → caught by this test against the live `role_mail`.
- `test_added_director_role_fires_the_notice` — PRE: even if `SINGULAR_INBOX_ROLES` were patched, the live `_inbox_for_role` hardcodes `if role in ("charc","operator")` → `newdir` returns `None` → `unread_notice` returns `None` → RED. POST: `_inbox_for_role` consults `SINGULAR_INBOX_ROLES` → `newdir` resolves its inbox → notice fires → GREEN. This is the exact silent-runtime failure B-12 Gap 1 describes (a new director is never told it has mail).

**Update the role_mail §8-mirror comment.** `scripts/role_mail.py` lines 688–707 carry the peer-director-add checklist comment. Add a line under item 2 (or a new note): adding a director to `SINGULAR_INBOX_ROLES` ALSO auto-covers the UserPromptSubmit unread notice (single-sourced in `.claude/hooks/user_prompt_submit.py`) — no separate hook edit needed. (No code change in role_mail; comment only.)

**Commit:** `fix(comms): B-12 Gap 1 — single-source the notice hook role set off role_mail.SINGULAR_INBOX_ROLES`

**Contamination self-cert:** core-only change (the hook + role_mail are CORE, stdlib); no project term added; the guarded import preserves the never-block-a-prompt discipline (degrades to the shipped default on any failure); no new dependency (importlib is stdlib).

---

### Task 8 — B-12 Gap 2: register the peer-director instance docs as instance surface

**Goal:** a new peer director's `<role>-context.md` + `<role>-state.md` carry domain vocab → must be instance surface so they pass the genericity guard + manifest. Task 1's `is_instance_surface` ALREADY covers `docs/*-state.md` and `docs/*-context.md` (minus the core exclusions) via PATTERN. This task (a) PROVES the pattern covers the peer-director docs and (b) adds the §8 checklist line.

**Files:** `docs/charc-charter.md` §8 (the checklist) — add a registration step; `tests/test_doc_acceptance.py` or `tests/test_instance_surface.py` — the proving test.

**TDD:** in `tests/test_instance_surface.py` (Task 1) the assertions for `docs/rd-state.md` + `docs/rd-context.md` → True already prove Gap 2's surface coverage. Add a charter-checklist assertion in `test_doc_acceptance.py::CharterAcceptanceTest`:

```python
def test_peer_director_checklist_names_genericity_registration(self) -> None:
    # The §8 peer-director-add checklist must gain the genericity-registration
    # item. Assert a UNIQUE CONTIGUOUS substring from the NEW item 5 text -- a
    # loose `"instance surface"`/`"genericity"` check could false-pass on prose
    # elsewhere in the charter (Codex R1 Major 2). Use the shared normalization
    # helper (R6 Minor 2) so line-wrapping does not break the contiguous match:
    norm = _norm(self.text)
    self.assertIn("the new director's instance docs", norm.lower())
    self.assertIn("is_instance_surface", norm)
    self.assertIn("instance_surface_relpaths", norm.lower())
```

> **Shared normalization helper (R6 Minor 2).** Add ONE module-level helper in `test_doc_acceptance.py` — `def _norm(text): return " ".join(text.split())` — and use it in BOTH the Task-8 and Task-9 charter assertions (and any other contiguous-fragment doc check) so a contiguous phrase matches regardless of Markdown line-wrapping. This is the same `" ".join(...split())` collapse the live `ImplementerTemplateAcceptanceTest::test_never_post_to_mailbox_discipline` already uses inline (doc_acceptance.py:175–177); pinning it as a named helper standardizes it.

> **Author the §8 item 5 to CONTAIN the asserted fragments (the test drives the wording).** The new item 5 text below carries `the new director's instance docs`, `is_instance_surface`, and `INSTANCE_SURFACE_RELPATHS` verbatim — none of which appear in the live charter today (verified: `is_instance_surface`/`INSTANCE_SURFACE`/`instance docs` are absent at `7f3f7c0`; only the bare word `kernel` pre-exists). So the assertions FAIL pre-edit and PASS post-edit. The fragment `the new director's instance docs` is contiguous + unique; pick a different contiguous fragment only if the implementer rewords item 5 (keep the test and the text in lockstep).

**Charter §8 edit (add a checklist item):** after the current item 4 (state pointer, live lines 142–143), add:

```
5. **Genericity registration** -- the new director's instance docs
   (`docs/<role>-context.md` + `docs/<role>-state.md`) carry domain vocabulary,
   so they are INSTANCE SURFACE: the genericity guard + manifest exempt them via
   the `docs/*-context.md` / `docs/*-state.md` patterns in
   `tests/genericity_lists.py` (`is_instance_surface`). They pass by construction
   -- no per-file registration needed for the standard `docs/<role>-*.md` layout;
   a non-standard path must be added to `INSTANCE_SURFACE_RELPATHS`.
```

The phrase "the new director's instance docs" + the tokens `is_instance_surface` and `INSTANCE_SURFACE_RELPATHS` are the unique contiguous fragments the Task-8 distinguishing test asserts — keep the prose and the test in lockstep.

> **Charter is CORE — contamination check (load-bearing).** `docs/charc-charter.md` is a CORE manifest file, genericity-scanned. The added §8 text MUST NOT name a project term, a forbidden vocab token, or a ticker. The placeholder `<role>` is fine; `docs/*-context.md`, `INSTANCE_SURFACE_RELPATHS`, `is_instance_surface` are fine (no forbidden token). Verify by running `test_genericity_guard` after the edit. Do NOT write an example like "rd-state.md" in the charter (the role term `rd` is in `FORBIDDEN_ROLE_TERMS`, line 82 — it would TRIP the guard in this CORE file). Use only `<role>` placeholders in the charter prose.

**Arithmetic (FAIL-pre / PASS-post):**
- `test_peer_director_checklist_names_genericity_registration` — PRE: §8 has no genericity/instance-surface line → assertion FAILS → RED. POST: the line is added → GREEN.
- The instance-surface pattern proof (`docs/rd-state.md`/`docs/rd-context.md` → True) is in Task 1's test; it FAILS pre-Task-1 (predicate absent), PASSES post. The over-broad guard (`docs/orchestrator-context.md` → False) ensures the `-context.md` pattern does not wrongly exempt the CORE orchestrator kernel.

**Commit:** `docs(charter): B-12 Gap 2 — peer-director instance-doc genericity registration in §8`

**Contamination self-cert:** the charter (CORE) gains only generic `<role>` placeholder prose — verified non-tripping by `test_genericity_guard`; no `rd`/project term written into the charter; the instance-surface patterns hold only generic shapes.

---

### Task 9 — B-12 Gap 3: reword charter §8 item 2 (generic contract in kernel vs instance authority in `<role>-context.md`)

**File:** `docs/charc-charter.md` §8 item 2 (live lines 138–139).

**Current text:** "**This charter** -- add the new director's authority + the comms-routing / custody note (a director cannot bus-reply to a foreign role it does not own)."

**Problem (brief §2 Gap 3):** the charter is CORE (generic, upstreamable) — it CANNOT carry an instance-specific director's authority vocab. The generic peer-director contract already lives in the kernel (§6 routing/custody + §5.1 state pointer); the new director's INSTANCE authority belongs in its own `<role>-context.md`.

**Reword to (split the two):**

```
2. **The charter vs the instance doc** -- the generic peer-director contract is
   already in this kernel: comms routing + custody (§6: a director cannot
   bus-reply to a foreign role it does not own; route via the operator) and the
   state-pointer convention (§5.1). The new director's INSTANCE-specific authority
   goes in its own `docs/<role>-context.md` instance doc -- NOT this charter, which
   stays generic + upstreamable. (Do not add project-specific authority vocab to
   the kernel charter.)
```

**TDD (assert a UNIQUE CONTIGUOUS substring from the rewritten item 2 — R1 Major 3 fix):** a loose `"<role>-context.md"` + `"already"`/`"kernel"` check false-passes — `kernel` already appears 4× in the live charter (lines 1/4/33/75), and the words `already`/`<role>-context.md` could drift in elsewhere (Codex R1 Major 3, accepted). Assert verbatim phrases that exist ONLY in the rewritten item 2:

```python
def test_peer_director_checklist_splits_kernel_vs_instance_authority(self) -> None:
    # Gap 3: §8 item 2 must split "generic contract already in the kernel" vs
    # "instance authority in the new director's own context doc". Assert UNIQUE
    # contiguous fragments from the rewritten item 2 via the shared _norm helper
    # (a loose kernel/already check false-passes -- 'kernel' pre-exists 4x).
    norm = _norm(self.text)
    self.assertIn("the generic peer-director contract is already in this kernel", norm)
    self.assertIn("goes in its own `docs/<role>-context.md` instance doc", norm)
```

> **Lockstep (load-bearing).** The asserted fragments use the shared `_norm` helper (R6 Minor 2 — `" ".join(text.split())`) so Markdown line-wrapping in item 2 does not break the contiguous match. Keep the asserted fragments and the item-2 prose in lockstep: the rewritten item 2 must contain, after whitespace-collapse, `the generic peer-director contract is already in this kernel` and `goes in its own docs/<role>-context.md instance doc`. Both are verified absent from the live charter at `7f3f7c0` (FAIL-pre / PASS-post holds).

**Arithmetic (FAIL-pre / PASS-post):** the phrases `the generic peer-director contract is already in this kernel` and `goes in its own docs/<role>-context.md instance doc` do NOT exist in the live charter at `7f3f7c0` (verified: the live item 2 reads "add the new director's authority + the comms-routing / custody note") → the assertions FAIL pre-edit → RED. POST-edit the reworded item 2 carries them verbatim → GREEN. Because the asserted fragments are unique contiguous strings from the NEW text (not loose words that pre-exist), the test cannot false-pass on the old wording.

> **Contamination check:** same as Task 8 — `<role>-context.md` placeholder only; no project term; verify `test_genericity_guard` green after the edit. The `CharterAcceptanceTest::test_peer_director_add_checklist` (live line 256) asserts the phrase "peer-director-add checklist" stays present — keep it.

**Commit:** `docs(charter): B-12 Gap 3 — split kernel peer-director contract from instance authority in §8`

**Contamination self-cert:** the kernel charter stays generic + upstreamable (the WHOLE point of the reword); no instance authority vocab enters the charter.

---

## 4. Pre-review full-suite gate + the no-false-green run

After all task-commits land and BEFORE the Codex review (per recipe §2): run the FULL accept gate from the harness-template root:

```
python -m unittest discover -s tests
```

It must report **OK** at a count of **168 + the new tests** (Task 1: ~9 predicate assertions in 1 method or split; Task 2: 2 methods; Task 4: 1–2 methods; Task 5: converted class, net same/slightly more methods; Task 6: 2 methods; Task 7: 2 methods; Task 8: 1 method; Task 9: 1 method — exact count READ OFF THE FINAL HEAD, never carried forward). The binding facts: zero failures/errors; the WholeTreeGuardTest stays green (the real tree has no filled instance files); the genericity guard is green over the whole tracked tree (no CORE term added by any task — re-verify after every doc edit to the charter/seam/bootstrap, which are CORE).

**No-false-green discipline:** the green-by-construction TEST IS the reality check (brief §6 WITNESS — a scaffold-internal change has no operator browser/CLI surface). Do not claim convergence without reading the actual `unittest` tail on the final state.

---

## 5. Codex review (executing phase: review-strong to convergence)

This is the WRITING-PLANS plan; the EXECUTING implementer runs **review-strong** (gpt-5.5/high) to `NO_NEW_CRITICAL_MAJOR` over the harness-template diff, per recipe §3 and brief §4/§6:
- Generate the diff on Windows: `git -C C:/Users/rwsmy/harness-template diff 7f3f7c0..HEAD > .codex-diff.txt` (from the harness-template worktree dir). Tell Codex NOT to run git (`--skip-git-repo-check`); pipe the plan/diff via stdin; write output to a gitignored file (`.codex-*` — covered by harness-template `.gitignore`).
- Because B-9's correctness depends on un-changed surrounding code (the scan loop, the manifest partition, the existing tests it must not regress), give Codex repo read-access OR bundle the reference-graph files (`genericity_lists.py`, `test_genericity_guard.py`, `test_manifest_accounting.py`, `_corefiles.py`, the hook + `role_mail.py`) per recipe §3 "REPO ACCESS for PRODUCTION-CODE review."
- codex-auto-review alongside if the WSL path supports it on this repo (brief §6).
- Persist every round's verbatim response + per-finding adjudication to a gitignored `.copowers-findings.md`.

---

## 6. Acceptance criteria (the executing implementer's done-definition)

- All 9 tasks committed (some folded: Task 3 into Task 2) with conventional commits, ZERO `Co-Authored-By`, no `--no-verify`, no amend, final `-m` paragraph plain prose. Trailer-clean: `git log 7f3f7c0..HEAD --format='%H%n%(trailers)'` all empty.
- `python -m unittest discover -s tests` → OK on the final state (168 + new).
- The five brief-§5 distinguishing tests all FAIL-pre / PASS-post (proven by the arithmetic in each task):
  1. **green-by-construction** — Task 2 `test_vocab_bans_are_core_only` (surface clean) + Task 4 (instance file accounted) + Task 5 (instantiated APPLICATION.md accepted).
  2. **CORE-contamination-still-FAILS** — Task 2 `test_vocab_bans_are_core_only` (core fixtures trip) + `test_over_broad_exemption_guard` (seam + orchestrator-context core-scanned).
  3. **dependency-posture instance-aware** — Task 1 predicate + the documented `_corefiles` CORE-scoping (instance file never in CORE_RELPATHS; a core file importing third-party fails — proven by the existing `test_ast_belt_core_imports_are_stdlib_only` + a new assertion if the implementer adds one; the structural invariant is the deliverable).
  4. **B-12 Gap-1** — Task 7 `test_comms_roles_single_sourced_from_role_mail` + `test_added_director_role_fires_the_notice`.
  5. **B-12 Gap-2** — Task 1/Task 8 instance-doc pattern coverage + the manifest acceptance.
- Codex review-strong converged (`NO_NEW_CRITICAL_MAJOR`); findings persisted.
- CHARC QA-on-disk: instance-surface model sound; CORE contamination still fails; NO project term leaked into a CORE file; the stdlib refinement landed instance-aware (CORE stays stdlib-only), not relaxed.

---

## 7. Dependency-posture clarification (the operator refinement — explicit)

Brief §1's +OPERATOR REFINEMENT folds `test_dependency_posture.py` into the instance-aware redesign. The live implementation is ALREADY CORE-scoped (it iterates `_corefiles.CORE_RELPATHS`, a closed 4-file list of `role_mail.py` + the three hooks — no instance-surface file is ever in it). So the refinement is satisfied STRUCTURALLY without re-architecting the guard. This plan's obligations for it:
1. **Document the invariant** in `tests/_corefiles.py`: a sentence that `CORE_RELPATHS` is the reusable-core set whose stdlib-only posture is enforced; instance-surface files (the germinated project's own code) import third-party freely and are deliberately NOT listed here.
2. **Add the distinguishing proof** (optional but recommended, in `tests/test_dependency_posture.py`): a test that an instance-surface file path is NOT in `CORE_RELPATHS` (so it is never AST-scanned), while a core file IS — i.e. the stdlib-only ban is CORE-scoped. Arithmetic: `self.assertNotIn("APPLICATION.md", _corefiles.CORE_RELPATHS)` etc. (passes post-doc; documents the boundary). The binding mechanism (`test_ast_belt_core_imports_are_stdlib_only`, line 61) is unchanged — a core third-party import still FAILS.

> **If the executing implementer discovers the live `_corefiles.CORE_RELPATHS` somehow includes an instance-surface path (it does not at `7f3f7c0`):** STOP and flag — that would be a real CORE-scoping bug to fix in this arc.

---

## 8. Flagged for the orchestrator (verify-at-execution / ambiguities)

- **APPLICATION.md `constraints` marker (Task 5):** verify the LIVE template `APPLICATION.md` carries a `constraints` section before adding it to the fill-marker list; the live `test_has_interview_fill_structure` checks only 3 markers. If absent, drop `constraints` and flag (do NOT RED the bare-clone gate).
- **`rd` in the charter (Tasks 8/9):** `rd` is a `FORBIDDEN_ROLE_TERM` (genericity_lists.py:82). The charter is CORE — use ONLY `<role>` placeholders in §8 prose; never write a concrete example role like `rd-state.md` in the charter or it trips the guard.
- **Test count:** READ OFF THE FINAL HEAD; the per-task estimates above are guidance, not a target.
- **Split:** BATCHED is recommended (§2). Task boundaries are split-clean (B-9 = Tasks 1–6, B-12 = Tasks 7–9) if the executing pass judges otherwise — flag to the orchestrator, do not silently descope.
