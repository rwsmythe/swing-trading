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

**PREMISE-SOURCING: SOURCE EVERY PREMISE FROM THE ROLE (OR ARTIFACT) THAT OWNS IT** (adopted 2026-07-28 — orchestrator-diagnosed, RD-generalized, CHARC-authored). §2 says who owns which CONTENT; this says where a claim must be sourced FROM. Three instances produced in a single day, each the same rule against a different premise-owner:

| Premise | Owned by | Failure when sourced elsewhere |
|---|---|---|
| A **FACT** about behavior | the CODE, not a doc | An untraced "~20 sessions" in a director doc became a plan input, then the plan cited that doc as evidence — a **circular citation**, broken only by reading `config.py`. (Also: a drifted stop quoted from a stale row.) |
| A **POSITION** | the role that HOLDS it, re-checked at POST time | Three crossings in one thread; a closure landed **6 seconds** after the reversal that reopened it. A stale position decays far faster than a stale fact. |
| **DISPATCH STATE** (what is in flight) | the ORCHESTRATOR, and ONLY it | Both directors inferred dispatch state from each other's messages; neither could observe it. The mailbox serialized nothing because the state change was in nobody's message. |

**The structural half (orchestrator commitment, 2026-07-28):** whenever it countermands, narrows, or re-instructs a live dispatch, it posts that as its own short status IMMEDIATELY, before anything else — dispatch state becomes something directors READ, not something they INFER. **The reciprocal obligation on directors:** when a ruling depends on what is currently in flight, rule against the orchestrator's LAST STATE STATEMENT (naming it, so a stale premise is visible in your own text), never against another director's message; if the state is unclear, ask rather than infer.

## 3. The comms information-vs-authority taxonomy (canonical)

The role mailbox (`scripts/role_mail.py`, `comms/<role>/{inbox,read}/`) enforces this in code:

- **UNIFORM SINGULAR ADDRESSING (arc 21-D, 2026-07-27).** EVERY role — `charc`, `rd`, `operator` AND `orchestrator` — has ONE fixed inbox `comms/<role>/{inbox,read}`. `--to orchestrator` is the only orchestrator address; the orchestrator inbox is drained by whichever generation is live (a handoff transfers the drain). The retired per-generation forms are **REJECTED, never ignored**: a `--to orchestrator:<session_id>` recipient and a `--session <id>` read flag each fail with an actionable message naming the singular replacement, so a stale caller LEARNS instead of silently misrouting. The `session_id` survives ONLY as a role-presence / recovery key in `comms_session_registry` — never as an addressing key. Historical per-generation trees were MOVED (never deleted) to `comms/orchestrator/_archive/<session_id>/` by `scripts/archive_comms_generations.py` (dry-run by default). *Origin: per-generation tracking produced only overhead in this repo — the F5 `newest_live` staleness class, the 2026-07-11 stray spin-ups, the R3 registry tidy, and two director misdeliveries — against zero occasions where two generations were meaningfully live at once.*
- **Role→role messages are limited to `fyi | status | query | return_report`.**
- **`decision_request` is valid ONLY when every recipient is the operator** — the CLI refuses to write one addressed to any other role.
- **Dispatch-direction traffic** (commissioning briefs, implementer dispatch prompts, approvals) carries AUTHORITY, which is the operator's alone. The V1 rule kept ALL such traffic operator-hand-carried; **amended 2026-06-26 (operator):** a director MAY post a dispatch (an action-bearing message) directly to the orchestrator's inbox (`comms/orchestrator/inbox`) **once the operator has PRE-AUTHORIZED the action** — the operator grants authority *before* the director sends, so a director's action-bearing inbox message carries the operator's IMPLIED approval, and the orchestrator acts on it as it would an operator-hand-carried prompt. The principle is unchanged — **automate the transport, never the authority**: the operator still grants the authority (pre-authorization); the director becomes the courier instead of the operator. (The operator reviews dispatched traffic via the comms GUI, not an inline pre-post check.) `decision_request` stays operator-recipient-only (the L1 lock).
- **An AUTOMATED / non-human SENDER (a process, not a role — e.g. a nightly pipeline emitting a status notify) must be TYPE-CONSTRAINED to the emit-only types it needs (`status`/`fyi`) at the sender gate, NOT granted the full type set.** The `decision_request` recipient-gate is INSUFFICIENT defense here: that gate PERMITS operator-addressed `decision_request`s, so an unconstrained automated sender could post authority traffic TO the operator. Constrain its TYPES upstream of the recipient-gate (an emit-only allowlist). **Tripwire-review corollary (§5):** a comms-taxonomy sender-widening review verifies the new sender's full TYPE-reach (what types, to whom — incl. the operator-addressed-authority vector), not just the recipient-gate. *(Origin 2026-06-22, 18-H.7: adding an automated `pipeline` sender; codex-auto-review caught it inherited the full types so `pipeline→operator decision_request` would have succeeded — CHARC's plan-stage review had checked only the sender-agnostic L1 recipient-gate. Fixed by an emit-only allowlist constraining `pipeline` to `status`.)*

The comms system is staged: **Stage 1** = the durable file mailbox + cold-start launcher + the unread hook; **Stage 1.5** = the optional operator GUI; **Stage 2** (push/MCP bus) only if Stage 1 chafes; **Stage 3** (autonomous wake) gated on evidence Stages 1–2 under-serve. Staging detail + the Stage-2/3 reference design: `tool-director-context.md` §2.5 + `docs/comms-stage2-push-research.md`. The orchestrator-inbox + session-registry design doc is `docs/comms-stage2-orchestrator-inbox-design.md` — **historical: its per-generation addressing half was retired by 21-D** (its own "a single shared `comms/orchestrator/inbox` … is simpler and likely sufficient" alternative is what the harness now runs). Friction-evidence accrues against the Stage-2 bar.

**SUPERSEDING messages declare it in the SUBJECT (convention, adopted 2026-07-28 — RD-proposed, CHARC-authored; harness architecture is CHARC's lane §2).** When a message REVERSES or SUPERSEDES an earlier position on the same question, the SUBJECT must say so and name what it supersedes — e.g. `SUPERSEDES my 15:32 ruling on X: …`. **Why the subject and not the body:** the inbox LISTING is where a reader decides "am I current?", and that decision must not require opening and diffing two messages. **Origin (2026-07-28, three crossings in ONE thread on one small question):** directors posted faster than the mail round-trips; each crossing was caught only by a reader comparing timestamps, and each cost a round — including CHARC declaring a question closed **six seconds** after RD's reversal re-opened it, and both directors then posting near-identical corrections that crossed *again*. Nobody erred; it is a cadence artifact of using an asynchronous mailbox synchronously. **A stale POSITION goes stale far faster than a stale FACT** — a claim about what a colleague has already decided should be re-checked at POST time, not at read time; a claim about code can be checked once. **Banked mechanization candidate (if the convention decays — the D21 class):** a `role_mail post --supersedes <message>` flag that stamps the subject automatically, making the signal structural rather than remembered.

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

## 6. Director current-state pointer (cold-start findability)

Each director keeps a single **`docs/<role>-state.md`** (e.g. `charc-state.md`, `rd-state.md`) — the **current-state pointer**, **OVERWRITTEN each session, never appended**. The director **bootstrap reads it FIRST** (deterministic, cheap), then the role charter for stable role/rules context.

The director context-doc **session log is APPEND-ONLY dated history** and must NOT carry "current state / read me first" blocks — current state lives ONLY in `<role>-state.md`.

**Rationale (origin 2026-06-16, a CHARC cold-start):** when the current-state snapshot is appended into the append-only log like history, successive context-exhaustion handoffs accrete duplicate "read me first" snapshots with no deterministic "latest" → the next instance hunts. Separating the mutable pointer (overwrite) from the immutable log (append) makes current state a single cheap deterministic read. This is harness ARCHITECTURE (§2) — it applies to ALL director roles and is baked into the harness-template scaffold (a generic `<role>-state.md`).

## 7. Maintenance

This doc is CHARC-owned harness architecture. Both director bootstraps read it at spinup. Amendments are CHARC's (in dialogue with the operator); other roles consume it and route proposed changes to CHARC. Its weight is monitored alongside the other live harness docs (`harness_probe.py`, §4.2 standard).
