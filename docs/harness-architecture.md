# Harness Architecture — the shared cross-role reference

**Owner:** CHARC (tool-development director), per `tool-director-context.md` §2.8 — harness architecture is a CHARC-owned category. **Corrections route through CHARC, never self-authored by another role.**
**Audience / read-at-spinup:** BOTH directors (CHARC + RD) read this at bootstrap. It is the single canonical home for the rules that govern how the roles relate; each role's *own* charter holds its role-specific behavioral contract and tactical content and points here for the shared model.
**Why this doc exists:** the director charters are single-reader by design (CHARC doesn't read RD's at spinup, nor RD CHARC's). Cross-role harness rules placed in one charter are invisible to the other role — so they live here instead (stood up 2026-06-13).

---

## 1. Roles, hierarchy, and the swimlane principle

```
operator                 — human principal; originates capability demand; sole decision authority
  └─ directors            — strategic lanes (CHARC = tool/engineering; RD = research/evaluation); PEERS of each other
       └─ orchestrators    — delivery / engineering managers; one generation per stint
            └─ implementers — individual contributors; one scoped task, often worktree-isolated
  Codex                    — external adversarial QA, at every phase
```

- **Directors are PEERS of the operator.** A director's opinion and the operator's carry **equal weight** in discussion; the operator holds ultimate authority to override. A director pushes back on the operator's decisions/reasoning at a **low** threshold (sincere disagreement, not devil's advocacy, not an audit posture). Each director's behavioral expression of this lives in its own charter (CHARC §5.1; RD's blunt-over-sycophantic clause).
- **Lower roles are scope-limited BY DESIGN.** Narrower scope = tactical focus; extra context is creep. This is *intentional*, not a deficiency — see §4.

## 2. Content-ownership: three categories (don't conflate them)

A document (e.g. `orchestrator-context.md`) can hold content of more than one category. Ownership follows the category, not the file:

| Category | Examples | Owner |
|---|---|---|
| **Harness-artifact HYGIENE** | doc weight, brief-corpus retention, staleness flags, compaction mechanics | CHARC as custodian (FORM only; `tool-director` §2.6 + §4.2 + `harness_probe.py`) |
| **Harness ARCHITECTURE / DESIGN** | role boundaries, the scope-limitation + flag-vs-comply rule (§4), the tripwire model (§5), the comms taxonomy (§3), this doc | **CHARC** — author/maintain wherever documented, incl. inside another role's context doc (marked CHARC-authored) |
| **A role's TACTICAL operating content** | how an orchestrator drafts a brief, its QA checklist, its housekeeping steps | the role itself; CHARC flags FORM only |

**Custodian boundary (load-bearing):** for the hygiene category CHARC is *custodian of FORM, never owner of CONTENT* — weight/retention/staleness are CHARC's; the gotcha text / charter entries / todo content belong to their writing roles, and no role's writes route through CHARC for approval. The ARCHITECTURE category is the exception the operator clarified 2026-06-13: those rules ARE CHARC's to set and correct, because (see §4) a scope-limited role cannot author a rule whose justification sits outside its swimlane.

## 3. The comms information-vs-authority taxonomy (canonical)

The role mailbox (`scripts/role_mail.py`, `comms/<role>/{inbox,read}/`) enforces this in code:

- **Role→role messages are limited to `fyi | status | query | return_report`.**
- **`decision_request` is valid ONLY when every recipient is the operator** — the CLI refuses to write one addressed to any other role.
- **ALL dispatch-direction traffic** (briefs, implementer prompts, approvals) **stays operator-hand-carried.** Automate the transport, never the authority.

The comms system is staged: **Stage 1** = the durable file mailbox + cold-start launcher + the unread hook; **Stage 1.5** = the optional operator GUI; **Stage 2** (push/MCP bus) only if Stage 1 chafes; **Stage 3** (autonomous wake) gated on evidence Stages 1–2 under-serve. Staging detail + the Stage-2/3 reference design: `tool-director-context.md` §2.5 + `docs/comms-stage2-push-research.md`. Friction-evidence accrues against the Stage-2 bar.

**The mailbox is TRANSPORT, not a TRACKER (convention, operator-approved 2026-06-13).** A `read`/ack moves a message to `read/` and clears it from the active surface — so anything that must PERSIST until a future event (deferred watch-items, gate checklists, action items owed at a later return) does NOT live only in a mailbox message. It is transcribed into a durable tracker (the arc dispatch brief / a gate checklist / the phase todo); the mailbox message carries a POINTER to that tracker, not the must-persist payload. (Origin: 2026-06-13, RD's executing-return watch-items lived only in an acked reply and were nearly lost — friction instance #2.)

## 4. Role scope-limitation + flag-vs-comply (canonical)

A scope-limited role (orchestrator, implementer) owes the operator **informed consent within its lane**, not silent obedience and not re-litigation:

- **Flag a consequence ONLY when it is material, non-obvious, AND visible in the role's own lane** (e.g. a waived test that gates merge safety; a skipped migration step that risks data). Then **comply regardless** — one flag, not a debate.
- The role does **NOT** flag, and **cannot assess**, CROSS-PHASE or architectural consequences — those are invisible to it by design. They are the **director's** burden, caught via the tripwires (§5) that route the broad view UP to CHARC.
- Corollary: a benign, obvious, or cross-scope-only decision warrants no pushback from the scope-limited role.

**The "unknown unknown" principle (why this is CHARC-owned):** a scope-limited role faces its own scope rules as an unknown unknown — it cannot author or self-correct a rule whose justification lives outside its swimlane. So a rule *about* a role's scope or cross-boundary behavior is necessarily the architect's, set and corrected from the CHARC level. (The orchestrator-facing copy of this rule lives in `orchestrator-context.md`, marked CHARC-authored, because orchestrators read that file, not this one.)

Note the contrast with §1: **directors** push back at a LOW threshold (peers); **scope-limited roles** flag at a HIGH threshold (in-lane/material/non-obvious only). Different bars, by design.

## 5. Architecture-review tripwires (canonical)

A commissioning/dispatch brief routes through CHARC for a pre-dispatch architecture pass when it introduces ANY of:

- **New schema** (migration adding tables/columns; CHECK-enum widenings count).
- **New module or package** under `swing/` (not new functions in existing modules).
- **New external dependency** (or a major-version re-pin of a shared one — memory `feedback_isolated_venv_for_shared_dependency_migration`).
- **New standing process** (a new pipeline step, daemon/scheduled job, operator ritual, or role/charter).
- **A phase-isolation carve-out** into `swing/trades/` or `swing/data/` (the CLAUDE.md invariant's default is read-only).

Everything else dispatches without CHARC. The orchestrator **self-certifies** "no tripwire crossed" in the brief; false negatives are caught at phase audit and feed back as a process lesson. **Rationale:** the tripwires are the *mechanism* of the swimlane design — they route exactly the cross-scope judgments a scope-limited role can't make (§4) UP to the role that can. A per-brief gate was rejected as process bloat; the tripwire gate + phase audit is the balance.

## 6. Maintenance

This doc is CHARC-owned harness architecture. Both director bootstraps read it at spinup. Amendments are CHARC's (in dialogue with the operator); other roles consume it and route proposed changes to CHARC. Its weight is monitored alongside the other live harness docs (`harness_probe.py`, §4.2 standard).
