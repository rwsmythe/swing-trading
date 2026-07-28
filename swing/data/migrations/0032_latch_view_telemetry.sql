-- 0032_latch_view_telemetry.sql
-- Phase 21 Arc 21-A: ONE view-telemetry fact per (latch, action session).
-- Atomic via explicit BEGIN; ... COMMIT; per the executescript implicit-COMMIT
-- gotcha (#9). Bumps schema_version 31 -> 32.
--
-- Columns 2-6 are the SHARED LATCH IDENTITY BLOCK that 21-B's order-intent
-- ledger copies VERBATIM (single source of truth:
-- swing/latches/identity.py:LATCH_IDENTITY_COLUMNS).
--
-- THE TWO FKs ARE DELIBERATELY DIFFERENT:
--   candidate_id     NOT NULL ... ON DELETE RESTRICT  -- the IMMUTABLE BRIDGE
--       KEY (the OPENING fire's candidates.id). It is the join between this
--       ledger and 21-B's, so it must never be nullable and must never be
--       silently severed: RESTRICT makes a future pruner fail loudly. Mirrors
--       0022's pattern_forward_observations.detection_id RESTRICT.
--   pipeline_run_id  NULLABLE ... ON DELETE SET NULL   -- an AUDIT LINKAGE, not
--       a key. pipeline_runs IS pruned; the record must survive that with its
--       identity intact (the 0022 / 0030 audit-linkage convention). It is also
--       legitimately NULL for every pre-June-2026 fire (the latch corpus starts
--       2026-04-20; pattern_detection_events starts 2026-06-05), so a NULL twin
--       is the NORMAL case and never an error.
--
-- V1 INVALIDATION SCOPE (RD gate ruling G.5): a latch's invalidation is
-- evaluated on CLOSES BELOW THE FIRE-TIME STOP LEVEL **ONLY**. Structural
-- base-break invalidation is NOT implemented in V1 -- the structural anchor is
-- not carried on `candidates` (it lives in
-- pattern_detection_events.structural_anchors_json, a different id space with
-- ZERO rows for the April/May fires). A future reader of this ledger must NOT
-- assume base-break coverage that is not here.
--
-- first_viewed_ts + latch_state_at_first_view are IMMUTABLE after insert;
-- last_viewed_ts + latch_state_at_last_view + view_count advance monotonically
-- via UPDATE-in-place (NEVER INSERT OR REPLACE).

BEGIN;

CREATE TABLE latch_view_events (
    view_event_id      INTEGER PRIMARY KEY AUTOINCREMENT,

    -- ===== LATCH IDENTITY BLOCK =====
    candidate_id       INTEGER NOT NULL REFERENCES candidates(id) ON DELETE RESTRICT,
    evaluation_run_id  INTEGER NOT NULL,
    ticker             TEXT NOT NULL,
    detection_date     TEXT NOT NULL,
    pipeline_run_id    INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,

    -- ===== VIEW TELEMETRY =====
    view_session_date         TEXT NOT NULL,
    first_viewed_ts           TEXT NOT NULL,
    last_viewed_ts            TEXT NOT NULL,
    view_count                INTEGER NOT NULL,
    latch_state_at_first_view TEXT NOT NULL,
    latch_state_at_last_view  TEXT NOT NULL,

    CHECK (latch_state_at_first_view IN
        ('armed','order_resting','filled','invalidated','horizon_expired',
         'superseded')),
    CHECK (latch_state_at_last_view IN
        ('armed','order_resting','filled','invalidated','horizon_expired',
         'superseded')),
    CHECK (view_count >= 1),
    CHECK (evaluation_run_id > 0),
    CHECK (length(trim(ticker)) > 0),
    -- ROUND-TRIP equality, NOT merely `date(...) IS NOT NULL`. SQLite's
    -- date() NORMALISES an out-of-range day: date('2026-02-30') returns
    -- '2026-03-02' (non-NULL, length 10), so the weaker form ACCEPTS a value
    -- that `date.fromisoformat` in LatchViewEvent.__post_init__ REJECTS. That
    -- is the dangerous asymmetry direction -- the DB holding rows the read path
    -- cannot hydrate.
    CHECK (length(detection_date) = 10 AND date(detection_date) = detection_date),
    CHECK (length(view_session_date) = 10
           AND date(view_session_date) = view_session_date),
    CHECK (last_viewed_ts >= first_viewed_ts),

    UNIQUE (evaluation_run_id, ticker, view_session_date)
);

CREATE INDEX ix_lve_ticker_detection_date ON latch_view_events(ticker, detection_date);
CREATE INDEX ix_lve_candidate_id          ON latch_view_events(candidate_id);
CREATE INDEX ix_lve_view_session_date     ON latch_view_events(view_session_date);

-- IDENTITY COHERENCE. `candidate_id` is a real FK, but `evaluation_run_id`,
-- `ticker` and `detection_date` are denormalised COPIES, so nothing above stops
-- a row pointing `candidate_id` at one fire while carrying another fire's
-- evaluation identity -- which would make the 21-A <-> 21-B join disagree with
-- itself about which latch a record describes. The production writer
-- (`repos/latch_view_events.record_view`) cannot produce that shape (it takes a
-- LatchIdentity built from ONE fire row), but RD's finding 4 asks for the
-- linkage to be EXACT rather than by convention, so it is enforced here too.
-- A trigger is required because a CHECK cannot reference another table.
CREATE TRIGGER trg_lve_identity_coherent_insert
BEFORE INSERT ON latch_view_events
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'latch_view_events identity block does not match its candidate_id')
    WHERE NOT EXISTS (
        SELECT 1 FROM candidates c
        JOIN evaluation_runs e ON e.id = c.evaluation_run_id
        WHERE c.id = NEW.candidate_id
          -- A latch only ever describes an A+ FIRE.
          AND c.bucket = 'aplus'
          AND c.evaluation_run_id = NEW.evaluation_run_id
          AND c.ticker = NEW.ticker
          AND e.action_session_date = NEW.detection_date
    );
    -- The DETECTION twin, when present, must be THIS evaluation run's pipeline
    -- run -- the exact linkage `swing/latches/reader.py` derives it from
    -- (LEFT JOIN pipeline_runs ON evaluation_run_id). A NULL twin stays legal:
    -- it is the NORMAL case for every pre-June-2026 fire, not an error.
    -- Deliberately NOT also asserting pipeline_runs.action_session_date =
    -- detection_date: it holds for all 111 linked pairs on the live DB today,
    -- but it is not the linkage the reader uses, so enforcing it would add a
    -- failure mode without adding safety.
    SELECT RAISE(ABORT, 'latch_view_events pipeline_run_id is not this evaluation run''s twin')
    WHERE NEW.pipeline_run_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM pipeline_runs p
        WHERE p.id = NEW.pipeline_run_id
          AND p.evaluation_run_id = NEW.evaluation_run_id
    );
END;

CREATE TRIGGER trg_lve_identity_coherent_update
BEFORE UPDATE OF candidate_id, evaluation_run_id, ticker, detection_date,
                 pipeline_run_id
ON latch_view_events
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'latch_view_events identity block does not match its candidate_id')
    WHERE NOT EXISTS (
        SELECT 1 FROM candidates c
        JOIN evaluation_runs e ON e.id = c.evaluation_run_id
        WHERE c.id = NEW.candidate_id
          -- A latch only ever describes an A+ FIRE.
          AND c.bucket = 'aplus'
          AND c.evaluation_run_id = NEW.evaluation_run_id
          AND c.ticker = NEW.ticker
          AND e.action_session_date = NEW.detection_date
    );
    -- The DETECTION twin, when present, must be THIS evaluation run's pipeline
    -- run -- the exact linkage `swing/latches/reader.py` derives it from
    -- (LEFT JOIN pipeline_runs ON evaluation_run_id). A NULL twin stays legal:
    -- it is the NORMAL case for every pre-June-2026 fire, not an error.
    -- Deliberately NOT also asserting pipeline_runs.action_session_date =
    -- detection_date: it holds for all 111 linked pairs on the live DB today,
    -- but it is not the linkage the reader uses, so enforcing it would add a
    -- failure mode without adding safety.
    SELECT RAISE(ABORT, 'latch_view_events pipeline_run_id is not this evaluation run''s twin')
    WHERE NEW.pipeline_run_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM pipeline_runs p
        WHERE p.id = NEW.pipeline_run_id
          AND p.evaluation_run_id = NEW.evaluation_run_id
    );
END;

UPDATE schema_version SET version = 32;

COMMIT;
