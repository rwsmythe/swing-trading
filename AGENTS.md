# Swing Trading — Codex Context

**The canonical, current project context is [`CLAUDE.md`](CLAUDE.md) — read it in full.**

`AGENTS.md` used to be a full parallel MIRROR of `CLAUDE.md`, maintained so
Codex/AGENTS-convention agents saw the same current-state, conventions, and the
§Gotchas catalog. Keeping two copies in sync failed in practice — the mirror
drifted behind the live phase and schema — so at the Phase-20 close (rider R2,
2026-07-15) it was collapsed to this thin pointer: **one source of truth, no
drift.** There is nothing Codex-specific to retain; everything a review needs
lives in the two docs below.

Read these, in order:

- **[`CLAUDE.md`](CLAUDE.md)** — current project state, conventions, architecture,
  invariants, and the full **§Gotchas** code/runtime/test failure-prevention
  catalog. This is the canonical context for Codex reviews as well as Claude.
- **[`docs/orchestrator-context.md`](docs/orchestrator-context.md)** — the
  process / review / brief-authoring disciplines + the pre-Codex "Expansion #N"
  catalog (the review meta-disciplines).

The former full-mirror body was a point-in-time snapshot; it is not retained here
(git history preserves it) so this file can never become a second drifting copy.
