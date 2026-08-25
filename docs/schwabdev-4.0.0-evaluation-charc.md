# schwabdev 4.0.0 — Phase-22 candidacy evaluation (CHARC, 2026-08-25)

**Verdict: DECLINE for Phase 22. Bank for the Phase-22 close / Phase-23 boundary window with
named triggers.** Evaluated at the operator's request; released **2026-08-09** (16 days old).
Current: pin `schwabdev>=3.0.5,<4.0.0` (pyproject:21), installed 3.0.5 — **4.0.0 is excluded by
the pin BY CONSTRUCTION**, so nothing breaks by not moving.

## What 4.0.0 is (changelog, read in full)

1. "Schwabdev Trader Context" optional submodule (an LLM-context add-on — unused by us)
2. `save_env_global` app-key storage (we store keys in `user-config.toml` — unused)
3. **Session retries** on requests (marginal for us; we already carry breakers + audit rows,
   and library-internal retries slightly change failure semantics under our audit accounting)
4. **`validate_params=True` (new default): client-side parameter validation on every request** —
   the one genuinely new behavior on our path
5. Public pytest test suite · "various other bugfixes and enhancements" (**unenumerated** — on a
   MAJOR bump this bucket must be read as a source diff, not trusted)

## The pinned surfaces, checked against 4.0 SOURCE (method: read the files, not the notes)

| our dependency | 4.0 state | verdict |
|---|---|---|
| **T1b DDL-drift guard** (`_V3_SCHWABDEV_DDL`, auth.py:1519) | tokens DDL **byte-compatible** — same 8 columns, same types (`tokens.py:108-117`); adds only `PRAGMA busy_timeout=30000` | guard would PASS |
| **Logger name `"Schwabdev"`** (redaction factory prefix check) | unchanged (`client.py:48`, `tokens.py:57`) | holds |
| **Construction-at-init hazard** (`__init__` → `update_tokens()`) | **unchanged** (`client.py:51`) — our preflight + `call_on_auth` belt remain necessary AND compatible (`call_on_auth`, `open_browser_for_auth`, `encryption` kwargs all present) | defenses carry over |
| **kwarg surface** | superset — `validate_params` added, nothing removed/renamed (unlike 3.0.0's four renames) | discriminating tests would pass |

**Caveat recorded:** the reads above are `main`-branch source, which can post-date the 4.0.0 tag;
an upgrade arc's diff MUST run against the tag. The surfaces checked are stable ones, but the
caveat is the method rule, not a formality.

## Why DECLINE for Phase 22

- **Near-zero gain on our operational surface.** 3.0.5 shows ZERO schema-parity failures across
  7,795+ audited production calls. Every 4.0 feature is either unused (submodule, env keys) or
  marginal (retries), and `validate_params` is **marginal-to-negative**: a new client-side
  rejection layer that can diverge from the live API — a false-refusal source we would be
  adopting, not a defense.
- **Real cost, known shape.** The Phase-15 precedent (2.5.1→3.0.5) is the binding template:
  isolated venv, GATE A/B, operator-witnessed live cutover against a 7-day refresh-token TTL,
  L2-lock re-anchor evaluation. The token machinery is the crown jewels; a cutover regression
  locks the operator out until `logout → setup`.
- **Phase-22 composition hazard.** 22-A's acceptance mechanism hangs off broker-order state
  through the validity flow; swapping the broker library UNDER that arc is the 21-D
  self-modification class. Phase 22's calendar (September read; October 22-A2 horizon) has no
  slack for an orthogonal integration arc.
- **16 days old on a major.** 3.0.0 needed five patch releases over five months. Let 4.0.x age.

## BANKED, with the triggers named

Revisit at the **Phase-22 close / Phase-23 boundary** (no in-flight integration-adjacent arcs),
preferring **4.0.2+**. **Escalate immediately** (do not wait for the boundary) on any of: a
security advisory against 3.x · a Schwab-side API change that 3.0.5 mishandles ·
`schwab_api_calls` schema-parity failures departing from zero. **When taken, the arc shape is
Phase-15 verbatim**, with two additions: task 1 is a tag-to-tag source diff over the pinned
surfaces above, and `validate_params` is set EXPLICITLY after a deliberate decision — never
inherited as a default.
