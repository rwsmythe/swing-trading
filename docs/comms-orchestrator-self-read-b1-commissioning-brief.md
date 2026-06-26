# Comms Orchestrator Self-Read — B.1 Commissioning Brief (G6 Finding 2)

**Owner/author:** CHARC (Tool Development Director). **Date:** 2026-06-26. **Status:** COMMISSIONED.
**Phase context:** Phase-18-close **G6**, **B.1** fast-follow (Arc A `94e8c7cb` + Arc B `1f8b8545` merged). Closes **Finding 2** (the Arc-B §5.10 witness gap).
**§3 verdict:** **SUB-TRIPWIRE** (a `role_mail` read-behavior change + a one-line launcher string — no schema / module / dependency / standing-process / `swing/` carve-out). CHARC-owned harness architecture; RD fyi (comms-user, not measurement). GO.
**Grounding (verified on disk 2026-06-26, main `d4c4f119`):** `scripts/role_mail.py` (the orchestrator-read require-session sites) + `scripts/start_directors.ps1:113` (`$ResumePrompt`) + `scripts/comms_session_registry.py:newest_live`.

---

## 0. Why

The Arc-B §5.10 witness surfaced Finding 2: a **resumed** orchestrator's `$ResumePrompt` (`start_directors.ps1:113`) emits `python scripts/role_mail.py read --role orchestrator --all`, which **ERRORS** — Arc A deliberately requires `--session <sid>` for orchestrator reads (`role_mail.py:297` "reading an orchestrator inbox requires --session <session_id>"). An orchestrator doesn't trivially know its own Claude `session_id` (the registry key), so it cannot self-drain. This blocks the last link of the director→orchestrator loop: a launched/resumed orchestrator reading its *own* inbox.

## 1. The fix

**(a) `role_mail` — the newest-live self-read (the core):** `read | list | peek --role orchestrator` with **NO `--session`** → resolve to the **newest-live** orchestrator generation's sid (via the registry's `newest_live`, exactly mirroring the SEND side's bare `--to orchestrator` resolution at `_inbox_for_target:275`), instead of erroring. If **no live orchestrator** → a **CLEAR error** (the read-side twin of `NoLiveOrchestratorError`), NOT the old "requires --session". Explicit `--session <sid>` is **UNCHANGED** (a specific gen, incl. a non-newest / pruned one). **This REVERSES the Arc-A require-session contract for the no-session case** — a deliberate, reviewed decision (the require-session rule was over-strict for the self-drain use case; newest-live is the natural default, symmetric with send).

- **Read+ack CONSISTENCY (load-bearing — the one real hazard):** `cmd_read` threads the session into the ack (`ack_message(root, role, name, session_id=...)`, `role_mail.py:622`→`533`). The newest-live-resolved sid MUST be used for BOTH the inbox READ and the ACK. Resolve the effective sid **ONCE** (a single helper — single-source, mirroring the send side) and thread it through `_role_inbox_dir`/`_role_read_dir`/`ack_message`. A read that resolves newest-live but acks a different (or `None`) sid would archive the WRONG generation's mail (or error on ack). Pin this with a discriminating test (the file moves from the resolved gen's `inbox/`→`read/`).
- **Validation belt:** re-validate the newest-live-resolved sid via `is_valid_session_id` before building any path (never trust a resolved value into a path — same belt the send side uses at `:283`).
- Single-source: the read-side newest-live resolution consumes the registry's `newest_live` — NO second resolver (guard #4).

**(b) `start_directors.ps1` — the resume-prompt wording (tiny):** `$ResumePrompt` (`:113`) says "Resuming your **director** session" — role-generic-but-wrong for a resumed orchestrator. Make it role-neutral (e.g. "Resuming your session"). Its `read --role {0} --all` drain now WORKS for orchestrator via the self-read (no command change beyond the wording). PS-5.1-safe (a string edit).

## 2. The edge (document, don't over-engineer)

With MULTIPLE live orchestrator generations at once, `read --role orchestrator` (no `--session`) reads the **newest**. For the self-drain use case the caller IS the newest-live (it just heartbeated on the prompt that ran the command), so this is correct. For an operator/director reading "the current orchestrator," newest-live is the natural default. A specific non-newest gen → explicit `--session`. Document in the `--session` help + a brief note; it is the SAME newest-live semantic the send side already carries (so it is not new surprise).

## 3. Tests (each distinguishes; TDD red→green)

- `read --role orchestrator` (no `--session`), one live gen → reads AND **acks that gen** (read+ack consistency — the `.md` moves from that gen's `inbox/`→`read/`).
- **No live orchestrator** → the CLEAR error (NOT "requires --session"), rc 1.
- Explicit `--session <sid>` still reads a SPECIFIC gen (incl. a non-newest one) — back-compat.
- `list` / `peek --role orchestrator` (no `--session`) → newest-live (observational, no ack).
- **FLIP the Arc-A "requires --session" tests** — they asserted the OLD contract; like the Arc-B effort test, they *codified the now-reversed rule* (TDD: flip them to assert newest-live resolution / the new clear-error, see them fail pre-fix, pass post-fix).
- Launcher static-content: the resume prompt is role-neutral (a resumed orchestrator is NOT told it's a "director session").
- stdlib-only preserved; the newest-live read resolution single-sources off the registry (grep-clean: no second `newest_live` in role_mail).

## 4. Locks / §3

- **Comms taxonomy + L1 UNCHANGED** — this is a READ-path convenience; no send/recipient/type change. (Confirm at writing-plans that nothing in the read path touches the L1 gate.)
- **Single-source** the newest-live resolution off the registry's `newest_live` (no second resolver — guard #4).
- **STDLIB-ONLY** comms core; **`__file__`-anchored** comms root — preserved.
- **SUB-TRIPWIRE** (role_mail read behavior + a launcher string). CHARC-owned; RD fyi, not merge-blocking.

## 5. Dispatch recommendation

- **Implementer cell:** `implementer-opus-high`. Rationale: small but comms-core, reverses a contract, and the read+ack consistency is a real correctness hazard — careful, not mechanical. Not measurement-chain (no `swing/`/schema) → not `-max`.
- **Orchestrator:** Opus xhigh. Worktree-isolated (`scripts/role_mail.py` + `scripts/start_directors.ps1` + `tests/scripts/`). review-strong + codex-auto-review.

## 6. Return report

**The ORCHESTRATOR posts the return report to `charc` (+ `operator` fyi) AFTER its own QA** — the implementer reports to its orchestrator in chat, never to a director inbox (memory `feedback_implementer_never_posts_to_directors`; charter §5.6). CHARC code-QAs the read+ack consistency + the contract reversal + the single-source on disk; RD fyi; the operator's **§5.10 CLI live-witness** is the binding gate: post to the newest-live orchestrator gen, then `role_mail read --role orchestrator` (no `--session`) **drains that gen** (proving the self-read + read+ack consistency); no-live-gen → the CLEAR error; explicit `--session` still targets a specific gen.
