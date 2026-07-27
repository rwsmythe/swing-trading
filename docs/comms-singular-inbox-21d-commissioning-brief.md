# Commissioning Brief — 21-D: comms simplification (retire per-generation orchestrator tracking)

**From:** CHARC. **To:** the Phase-21 orchestrator. **Arc:** 21-D ([`phase21-scope-charc.md`](phase21-scope-charc.md)). **Committed:** 2026-07-27, operator-approved. **Parallel with 21-A** (file-disjoint: comms/scripts/docs vs web).
**§3 verdict: STANDING-PROCESS CHANGE (a comms addressing convention) → this brief IS the CHARC architecture pass; conditions D1–D5 BINDING. Harness architecture is CHARC's lane (§2.8).** NO schema, NO L2, no `swing/` production code expected.

## §0 References

- **The operator's demand (07-27):** per-generation orchestrator tracking is "pure noise — I only use one at a time, realistically." He has **already implemented the simplification in coa-chess**; this ports it.
- **The coa-chess design (CHARC-verified on disk 2026-07-27):** `comms/orchestrator/{inbox,read,_archive}` — a **singular** inbox; `scripts/role_mail.py` **REJECTS** a `:<session_id>` suffix with an actionable message ("Every role is a singular inbox — address …") rather than silently ignoring it; `_inbox_for_target` keeps `session_id` in the signature but ignores it; **`comms/sessions/` retired**; the session_id survives ONLY as a role-recovery key.
- **What this repo carries today:** `comms/orchestrator/<session_id>/{inbox,read}` × 5 historical gens (`1a0ae071`, `2eb28653`, `3ebd6c5b`, `be363355`, `d67f7279`), `comms/sessions/*.json`, the legacy `comms/.sessions.json` singleton (gitignored), and newest-live resolution in `role_mail.py`.

## §1 Why (the accumulated evidence — all from this repo's own history)

Per-gen tracking produced **only** overhead here: **F5** (`newest_live` staleness on a prompt-idle gen → the standing "always use an explicit `:<sid>`" discipline every director had to remember) · the **2026-07-11 stray spin-ups** (two accidental partial gens registered, one CLOBBERING the live gen's entry in the singleton via the launcher's read-modify-write) · the **R3 registry-tidy** rider · and **two director misdeliveries RD reports hitting personally**. Against that: zero occasions where two orchestrator generations were meaningfully live at once. The convention costs attention at every dispatch and buys nothing.

## §2 Requirements

1. **D1 — Singular inbox.** `comms/orchestrator/{inbox,read}`, exactly as the directors have always had.
2. **D2 — REJECT, don't ignore.** A `:<session_id>` suffix must fail with an actionable message (the coa-chess behavior). A stale caller must LEARN, not silently misroute — this is the whole reason the convention change is safe to make mid-flight.
3. **D3 — HISTORY IS NEVER DELETED (BINDING).** The five existing per-gen trees move to `comms/orchestrator/_archive/<session_id>/…` (the coa-chess layout). This is the same binding that governed the R3 tidy. Verify the archived trees are intact and readable after the move.
4. **D4 — Registry retired.** `comms/sessions/` and the legacy `.sessions.json` singleton: retire or reduce to a role-presence/recovery key only. **Reconcile the consumers BEFORE touching** (the extended-D21 discipline applies — this is tracked-adjacent config): `scripts/role_mail.py`, `scripts/comms_ui.py` (`_recorded_sessions` reads director-role PRESENCE), `scripts/start_directors.ps1` (the writer), the comms Stop/unread hooks, and any test that references the per-gen shape.
5. **D5 — The doc sweep is part of the arc, not a follow-up.** The convention is documented in several places and a stale copy is the D21 decay class: **`docs/harness-architecture.md` §3 + §6** (CHARC-owned — the canonical comms taxonomy + the state-pointer convention), the role bootstraps (`scripts/*_bootstrap*.md`), `docs/orchestrator-context.md`, and both director charters/state docs where the explicit-`:<sid>` discipline is written. **CHARC will update `charc-state.md`'s behavioral list itself** (it currently says "explicit `:<sid>` ALWAYS" — obsolete after this arc); flag RD's equivalent to him rather than editing his docs.

## §3 Tests + verification

- Grep `tests/` for the per-gen shape **before** changing anything (D21 extension: tracked-config/path changes get the tests-grep first, the suite after).
- Discriminating tests: a bare `--to orchestrator` routes to the singular inbox; a `:<sid>`-suffixed address **RAISES with the actionable message** (not a silent success, not a silent drop); the archived trees remain readable; `comms_ui` still resolves director presence.
- Full suite after the change (tracked-config discipline).

## §4 Gates

CHARC pass = this brief. review-fast is sufficient (scripts/docs, no production `swing/` code) — orchestrator's call to escalate. Suite + ruff. **Operator witness: a dispatch round-trips end-to-end after the change** (a post to the singular orchestrator inbox arrives and is readable) **and** a `:<sid>` address fails loudly. The ORCHESTRATOR posts the return to `charc,rd` after its QA.

## §5 A note on doing this to ourselves mid-phase

This arc changes the addressing the *other* live arc (21-A) is being dispatched over. Sequence accordingly: land 21-D's change at a moment when no dispatch is in flight to a per-gen address, or ensure the rejection path is in place before the old addresses disappear. The rejection-not-silence requirement (D2) is what makes a mistimed dispatch safe — it fails visibly instead of vanishing.

## §6 Sizing + cells

Small-medium; mechanical but touching a live communication path. CHARC recommendation: **`implementer-opus-high`** for a single executing dispatch (the design is settled by the coa-chess reference implementation; the work is the port + the consumer/doc sweep). Orchestrator selects + announces.
