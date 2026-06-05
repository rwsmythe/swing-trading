"""Provenance-by-origin filtering for pattern_evaluations rows.

The pool-widening arc (2026-06-04) admits watch-origin pattern_evaluations rows
into the nightly detect step. The 3 silent aggregate/queue consumers must stay
aplus-origin-only so the widen is invisible to operator-facing surfaces. There
is NO bucket column on pattern_evaluations (D4 -- no schema change); the origin
is reached by the PROVABLE-aplus ladder below.

CONTRACT: the consuming SELECT MUST alias pattern_evaluations as ``pe``. The
predicate references pe.pipeline_run_id, pe.ticker, pe.pattern_class and adds
NO bind parameters (all literals) -- interpolate it into a WHERE clause without
disturbing the consumer's ``?`` positions. Internal subquery aliases are
suffixed ``_pa``/``_w`` to avoid shadowing the consumer's own aliases.
"""
from __future__ import annotations

# TRUE iff the pe row is PROVABLY aplus-origin (see plan section 4).
PROVABLE_APLUS_PE_PREDICATE = """(
    EXISTS (
        SELECT 1 FROM pipeline_runs pr_pa
        JOIN candidates c_pa
          ON c_pa.evaluation_run_id = pr_pa.evaluation_run_id
         AND c_pa.ticker = pe.ticker
        WHERE pr_pa.id = pe.pipeline_run_id
          AND c_pa.bucket = 'aplus'
    )
    OR EXISTS (
        SELECT 1 FROM pattern_detection_events pde_pa
        WHERE pde_pa.pipeline_run_id = pe.pipeline_run_id
          AND pde_pa.ticker = pe.ticker
          AND pde_pa.pattern_class = pe.pattern_class
          AND json_extract(pde_pa.finviz_screen_state, '$.bucket') = 'aplus'
    )
    OR (
        NOT EXISTS (
            SELECT 1 FROM pipeline_runs pr_h
            JOIN candidates c_h
              ON c_h.evaluation_run_id = pr_h.evaluation_run_id
             AND c_h.ticker = pe.ticker
            WHERE pr_h.id = pe.pipeline_run_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM pattern_detection_events pde_h
            WHERE pde_h.pipeline_run_id = pe.pipeline_run_id
              AND pde_h.ticker = pe.ticker
              AND pde_h.pattern_class = pe.pattern_class
        )
        AND (
            -- No widen has shipped yet (no watch-origin PDE anywhere) =>
            -- every historical neither-cand-nor-PDE row is aplus => INCLUDE.
            NOT EXISTS (
                SELECT 1 FROM pattern_detection_events pde_w
                WHERE json_extract(pde_w.finviz_screen_state, '$.bucket') = 'watch'
            )
            -- Otherwise INCLUDE iff this row's run is strictly BEFORE the first
            -- widened SESSION. Boundary = MIN(detection_date) among watch-origin
            -- PDEs, compared to this PE's run action_session_date.
            -- DURABLE-COLUMN ordering (Codex R3 MAJOR): both detection_date (on
            -- the PDE) and action_session_date (on pipeline_runs) are NOT NULL
            -- and SURVIVE run pruning. The earlier MIN(pipeline_run_id) boundary
            -- was UNSOUND because PDE.pipeline_run_id is ON DELETE SET NULL
            -- (migration 0022:41-42): pruning the first widened run NULLs its
            -- surviving watch PDE's run id and silently ADVANCES the boundary to
            -- a later run, leaking unprovable watch rows from the gap runs. The
            -- durable detection_date does NOT move when a run is pruned. Date
            -- strings 'YYYY-MM-DD' compare chronologically. No first-run edge: a
            -- watch PE on the first widened session has action_session_date ==
            -- the boundary, so `< boundary` is false -> EXCLUDE (correct).
            OR (
                SELECT pr_s.action_session_date FROM pipeline_runs pr_s
                WHERE pr_s.id = pe.pipeline_run_id
            ) < (
                SELECT MIN(pde_w.detection_date)
                FROM pattern_detection_events pde_w
                WHERE json_extract(pde_w.finviz_screen_state, '$.bucket') = 'watch'
            )
        )
    )
)"""
