# Research and Verification Branch

This directory contains the Research and Verification branch of the Swing Trading project's bifurcated architecture (see `../reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`, §V).

## What lives here

- `method-records/` — one file per method under research, production, or retired. Format per `method-records/_template.md`. Versioned in-place; major version bumps follow V2.1 §VII.F source-of-truth correction protocol.
- `studies/` — one file per study. Each references the method record it validates, documents baseline/variants/metrics/decision surface.
- `phase-0-tasks.md` — small task list for the current research phase, sized to the time budget (V2.1 §III.7).

## Posture

- Minimum viable governance (V2.1 §IX). Add governance machinery only when an active study or promotion requires it.
- Bootstrap-first data (V2.1 §V.E). Free sources only unless a specific study justifies a paid-data decision.
- Toleranced parity (V2.1 §VII.B). Fixture identity + toleranced vendor-backed equivalence.
- Read the rebuttal-response Anti-patterns list (`../reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md`) and apply it.

## Promotion boundary

No method in this directory drives primary operator recommendations unless its method-record `status` field is `production`. Methods in `shadow` status may run in production but do not drive primary decisions (V2.1 §IV.D, §VII.C).
