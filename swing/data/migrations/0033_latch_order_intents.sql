-- 0033_latch_order_intents.sql
-- Phase 21 Arc 21-B: the execution-parity ledger + the telemetry surface column.
-- Atomic via explicit BEGIN; ... COMMIT; per the executescript implicit-COMMIT
-- gotcha (#9). Bumps schema_version 32 -> 33.
--
-- TWO changes:
--   (1) latch_view_events is REBUILT to add `surface` (B4) + the THREE
--       actionability columns, and to re-key its UNIQUE onto the IMMUTABLE
--       BRIDGE KEY (candidate_id, view_session_date, surface). SQLite cannot
--       drop a table-level UNIQUE, so a rebuild is the only path. The rebuild
--       carries EXACTLY FIVE deltas off 0032 (plan section C.1) and one of them
--       -- the three-predicate date guard -- is a DELIBERATE, NAMED FIX riding
--       the rebuild, not a by-product of it (plan section C.1.1).
--   (2) latch_order_intents is created: APPEND-ONLY, audit-grade, one row per
--       operator DECISION about a prepared order (plan section C.2).
--
-- WHY THE DATE GUARD CHANGES (section C.1.1). A SQLite CHECK PASSES when its
-- expression evaluates to NULL, and date('2026-99-99') IS NULL -- so 0032's
-- `date(x) = x` evaluates to NULL and ACCEPTS a length-correct invalid date.
-- BOTH halves are required and neither is sufficient: round-trip equality
-- catches the NORMALISING case ('2026-02-30' -> '2026-03-02'), `IS NOT NULL`
-- catches the INVALID case, and a THIRD predicate -- the year range -- is
-- needed because SQLite round-trips year zero happily while Python's
-- date.fromisoformat RAISES on it (the DB holding a row the read path cannot
-- hydrate, the asymmetry the #11 discipline exists to stop). 0032's own comment
-- argued CAREFULLY for round-trip equality OVER `IS NOT NULL` and was correct
-- about normalisation -- it simply concluded normalisation was the whole
-- failure space. That is why the fix is pinned by tests rather than by a
-- corrected comment.

BEGIN;

-- =====================================================================
-- (1) THE latch_view_events REBUILD -- 0032 plus EXACTLY FIVE deltas.
-- =====================================================================
CREATE TABLE latch_view_events_new (
    view_event_id      INTEGER PRIMARY KEY AUTOINCREMENT,

    -- ===== LATCH IDENTITY BLOCK (columns 2-6, VERBATIM) =====
    candidate_id       INTEGER NOT NULL REFERENCES candidates(id) ON DELETE RESTRICT,
    evaluation_run_id  INTEGER NOT NULL,
    ticker             TEXT NOT NULL,
    detection_date     TEXT NOT NULL,
    pipeline_run_id    INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,

    -- ===== VIEW TELEMETRY =====
    surface            TEXT NOT NULL,          -- DELTA (a), B4
    view_session_date         TEXT NOT NULL,
    first_viewed_ts           TEXT NOT NULL,
    last_viewed_ts            TEXT NOT NULL,
    view_count                INTEGER NOT NULL,
    latch_state_at_first_view TEXT NOT NULL,
    latch_state_at_last_view  TEXT NOT NULL,

    -- DELTA (b): THREE FACTS, NAMED HONESTLY. A single `actionable` advanced by
    -- MAX() would let an 18:00 offered render retroactively upgrade an 09:00
    -- withheld one while first_viewed_ts still says 09:00; naming the MAX
    -- column `..._at_last_view` commits the mirror-image lie. The classifier's
    -- real question is "was it ever offered this session", so that fact gets
    -- its OWN honestly-named column and the first/last pair stay literally true
    -- of their own views.
    --   actionable_at_first_view -- set at INSERT, NEVER rewritten
    --   actionable_at_last_view  -- overwritten on every UPDATE (may FALL 1->0)
    --   actionable_ever_viewed   -- MAX(existing, new); monotonic 0 -> 1
    -- CLASSIFICATION reads `actionable_ever_viewed` and ONLY that one.
    actionable_at_first_view  INTEGER NOT NULL,
    actionable_at_last_view   INTEGER NOT NULL,
    actionable_ever_viewed    INTEGER NOT NULL,

    -- ===== 0032's CHECKS, PRESERVED =====
    CHECK (latch_state_at_first_view IN
        ('armed','order_resting','filled','invalidated','horizon_expired',
         'superseded')),
    CHECK (latch_state_at_last_view IN
        ('armed','order_resting','filled','invalidated','horizon_expired',
         'superseded')),
    CHECK (view_count >= 1),
    CHECK (evaluation_run_id > 0),
    CHECK (length(trim(ticker)) > 0),
    -- PRESERVED unchanged: an ORDERING guarantee, which neither SHAPE guard
    -- below implies.
    CHECK (last_viewed_ts >= first_viewed_ts),

    -- ===== DELTA (a): the surface enum =====
    CHECK (surface IN ('latch_panel')),

    -- ===== DELTA (b): the actionability bounds + the MONOTONE contract =====
    -- The contract runs `ever >= first` and `ever >= last` ONLY.
    -- `first=1, last=0` is DELIBERATELY LEGAL: it is the true record of an
    -- offered 09:00 render followed by a withheld 18:00 one, and forbidding it
    -- would reimpose the "last means ever" lie the third column ended.
    CHECK (actionable_at_first_view IN (0, 1)),
    CHECK (actionable_at_last_view  IN (0, 1)),
    CHECK (actionable_ever_viewed   IN (0, 1)),
    CHECK (actionable_ever_viewed >= actionable_at_first_view),
    CHECK (actionable_ever_viewed >= actionable_at_last_view),

    -- ===== DELTA (c): THE THREE-PREDICATE DATE GUARD (section C.1.1) =====
    -- The ONLY change to an existing CHECK. Used VERBATIM at every date column
    -- in this arc; if a fourth malformed shape is ever found it is added HERE
    -- and propagated, never patched at one site.
    CHECK (COALESCE(length(detection_date) = 10
           AND date(detection_date) IS NOT NULL
           AND date(detection_date) = detection_date
           AND CAST(substr(detection_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    CHECK (COALESCE(length(view_session_date) = 10
           AND date(view_session_date) IS NOT NULL
           AND date(view_session_date) = view_session_date
           AND CAST(substr(view_session_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),

    -- ===== DELTA (e): the ISO-seconds SHAPE guards on both view timestamps ==
    -- 0032 guarded these ONLY by `last >= first` -- an ORDERING constraint, not
    -- a SHAPE one -- so a raw append could store a malformed or absurd view
    -- timestamp that hydrates fine and renders as authoritative telemetry,
    -- which is B4's own recorded fact.
    CHECK (COALESCE(
           length(first_viewed_ts) = 19
           AND first_viewed_ts GLOB
               '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
           AND datetime(first_viewed_ts) IS NOT NULL
           AND date(substr(first_viewed_ts, 1, 10)) IS NOT NULL
           AND date(substr(first_viewed_ts, 1, 10)) = substr(first_viewed_ts, 1, 10)
           AND CAST(substr(first_viewed_ts, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
           AND CAST(substr(first_viewed_ts, 12, 2) AS INTEGER) <= 23
           AND CAST(substr(first_viewed_ts, 15, 2) AS INTEGER) <= 59
           AND CAST(substr(first_viewed_ts, 18, 2) AS INTEGER) <= 59, 0)),
    CHECK (COALESCE(
           length(last_viewed_ts) = 19
           AND last_viewed_ts GLOB
               '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
           AND datetime(last_viewed_ts) IS NOT NULL
           AND date(substr(last_viewed_ts, 1, 10)) IS NOT NULL
           AND date(substr(last_viewed_ts, 1, 10)) = substr(last_viewed_ts, 1, 10)
           AND CAST(substr(last_viewed_ts, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
           AND CAST(substr(last_viewed_ts, 12, 2) AS INTEGER) <= 23
           AND CAST(substr(last_viewed_ts, 15, 2) AS INTEGER) <= 59
           AND CAST(substr(last_viewed_ts, 18, 2) AS INTEGER) <= 59, 0)),

    -- ===== DELTA (d): the re-keyed UNIQUE =====
    -- KEYED ON candidate_id -- the declared IMMUTABLE BRIDGE KEY -- not on
    -- (evaluation_run_id, ticker). Those are equivalent today, so this is NOT a
    -- live aliasing bug; it is an architectural one, and free here because the
    -- table is being rebuilt anyway. The grain becomes per-(latch, session,
    -- SURFACE) so 21-F can record a dashboard view in a session the panel was
    -- also opened. Actionability is an ATTRIBUTE of the row, not part of its
    -- key: within one session a card can flip between withheld and offered.
    UNIQUE (candidate_id, view_session_date, surface)
);

-- THE COLUMN LIST IS WRITTEN OUT EXPLICITLY, never left positional: a bare
-- `INSERT INTO t SELECT ...` binds by POSITION, so a column added to the DDL
-- and not to the SELECT lands values in the wrong columns.
--
-- THE LEGACY BACKFILL IS `0`, NOT `1`. The old schema recorded no actionability
-- at all, so asserting those views WERE actionable manufactures evidence in the
-- flattering-to-the-instrument direction. `0` asserts strictly less -- "no
-- actionable presentation is RECORDED for this row" -- which is literally true
-- of a row written by a schema that recorded no such thing. On production this
-- is moot and that is VERIFIED, not assumed: latch_view_events held ZERO rows
-- on the live DB at this writing, so the copy moves nothing; the `0` exists for
-- a dev/test DB whose six-day-old telemetry has no downstream consumer.
INSERT INTO latch_view_events_new (
    view_event_id, candidate_id, evaluation_run_id, ticker, detection_date,
    pipeline_run_id, surface, view_session_date, first_viewed_ts, last_viewed_ts,
    view_count, latch_state_at_first_view, latch_state_at_last_view,
    actionable_at_first_view, actionable_at_last_view, actionable_ever_viewed)
    SELECT view_event_id, candidate_id, evaluation_run_id, ticker, detection_date,
           pipeline_run_id, 'latch_panel', view_session_date, first_viewed_ts,
           last_viewed_ts, view_count, latch_state_at_first_view,
           latch_state_at_last_view, 0, 0, 0
    FROM latch_view_events;

DROP TABLE latch_view_events;
ALTER TABLE latch_view_events_new RENAME TO latch_view_events;

CREATE INDEX ix_lve_ticker_detection_date ON latch_view_events(ticker, detection_date);
CREATE INDEX ix_lve_candidate_id          ON latch_view_events(candidate_id);
CREATE INDEX ix_lve_view_session_date     ON latch_view_events(view_session_date);

-- IDENTITY COHERENCE -- 0032's two triggers, VERBATIM apart from the table
-- name (which is unchanged) and recreated because DROP TABLE dropped them.
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
    SELECT RAISE(ABORT, 'latch_view_events pipeline_run_id is not this evaluation run''s twin')
    WHERE NEW.pipeline_run_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM pipeline_runs p
        WHERE p.id = NEW.pipeline_run_id
          AND p.evaluation_run_id = NEW.evaluation_run_id
    );
END;

-- =====================================================================
-- (2) latch_order_intents -- the execution-parity ledger (B3).
-- APPEND-ONLY. One row per operator DECISION. The classification and the
-- per-field delta are READS over these rows, never stored state.
-- =====================================================================
CREATE TABLE latch_order_intents (
    intent_id            INTEGER PRIMARY KEY AUTOINCREMENT,

    -- ===== LATCH IDENTITY BLOCK -- columns 2-6, VERBATIM per
    -- swing/latches/identity.py:LATCH_IDENTITY_COLUMNS (RD finding 4: BOTH id
    -- spaces). candidate_id is the IMMUTABLE BRIDGE KEY this ledger joins to
    -- latch_view_events on: ON a.candidate_id = b.candidate_id. NOT NULL +
    -- RESTRICT so a future pruner fails loudly instead of silently severing it.
    candidate_id         INTEGER NOT NULL REFERENCES candidates(id) ON DELETE RESTRICT,
    evaluation_run_id    INTEGER NOT NULL,
    ticker               TEXT NOT NULL,
    detection_date       TEXT NOT NULL,
    -- NO FK, DELIBERATELY. `pipeline_runs` IS genuinely pruned in this project,
    -- so RESTRICT would block that pruning forever -- but SET NULL is WORSE
    -- than either: a SET NULL cascade is an UPDATE, trg_loi_no_update aborts
    -- it, and nulling would DESTROY the detection identity RD's finding 4 asked
    -- to be stored on the very event this ledger exists to remember. So it is a
    -- PLAIN INTEGER: a denormalised copy exactly like evaluation_run_id /
    -- ticker / detection_date beside it, VALIDATED AT INSERT by the
    -- identity-coherence trigger (while the referent still exists) and then
    -- PRESERVED FOREVER. Validate at write; keep the fact after the referent is
    -- gone. Deliberately DIVERGENT from latch_view_events, which keeps its 0032
    -- SET NULL -- that table is not UPDATE-forbidden, so the cascade works
    -- there, and 21-A's shipped behaviour is not this arc's to change.
    pipeline_run_id      INTEGER,

    -- ===== THE EVENT =====
    idempotency_key      TEXT NOT NULL,          -- hazard (a); UNIQUE below
    -- THE MANDATE'S SESSION ON EVERY KIND -- three facts, three homes.
    -- `action_session_date` says WHICH SESSION'S MANDATE this row is about;
    -- `recorded_ts` says WHEN THE ANSWER HAPPENED (and is the only time axis
    -- the monthly report reads); `broker_snapshot_session` inside
    -- `validity_detail` says WHEN THE BROKER VIEW WAS TAKEN. Per kind:
    --   place / decline -- the VALIDATED session anchor.
    --   validity        -- SERVER-COPIED from the parent `place` row, NEVER
    --                      from the payload and NEVER the submitted anchor. An
    --                      aged prompt is the NORMAL case, so an anchor-derived
    --                      value would file a July mandate under August.
    --                      Enforced by trg_loi_validity_parent_insert.
    --   cancel / attest -- the VALIDATED session anchor.
    action_session_date  TEXT NOT NULL,
    recorded_ts          TEXT NOT NULL,          -- SERVER-STAMPED at POST
    surface              TEXT NOT NULL,
    intent_kind          TEXT NOT NULL,          -- place|decline|cancel|attest|validity
    decline_reason       TEXT,                   -- required iff intent_kind='decline'
    attested_disposition TEXT,                   -- required iff intent_kind='attest'
    -- THE VALIDITY PARENT LINK. A `validity` row answers for ONE specific
    -- `place` intent, not for "the latch": a latch can have more than one
    -- place/validity cycle (he places, it is rejected, he re-places), and a
    -- latest-by-latch read would attach a later answer to an earlier order and
    -- RETROACTIVELY change a reported outcome.
    validated_place_intent_id INTEGER
        REFERENCES latch_order_intents(intent_id) ON DELETE RESTRICT,

    -- ===== THE FRAMEWORK'S COMPUTED ORDER (stored VERBATIM) =====
    framework_order_type  TEXT,                  -- STOP_LIMIT | LIMIT
    framework_duration    TEXT,
    framework_stop_price  REAL,                  -- NULL in the pullback regime
    framework_limit_price REAL,
    framework_quantity    INTEGER,

    -- ===== THE DERIVATION INPUTS THAT CAN DRIFT =====
    derivation_zone_cap_pct         REAL,
    derivation_sizing_equity        REAL,
    derivation_max_risk_pct         REAL,
    derivation_position_pct_cap     REAL,
    -- A REAL FK, and RESTRICT not SET NULL: a SET NULL cascade is an UPDATE and
    -- trg_loi_no_update ABORTs every UPDATE on this table. RESTRICT is also the
    -- semantically right answer independently -- risk_policy rows are
    -- SUPERSEDED (effective_to + superseded_by_policy_id), never deleted -- so
    -- RESTRICT forbids only something production does not do.
    derivation_risk_policy_id       INTEGER
        REFERENCES risk_policy(policy_id) ON DELETE RESTRICT,
    derivation_sizing_basis         TEXT,        -- limit_price | pivot
    derivation_regime_close         REAL,        -- NULL = regime undeterminable
    derivation_regime_close_session TEXT,        -- the session that close is DATED
    -- RENDERED ON THE CARD, THEREFORE ANCHORED AND STORED. real_equity moves
    -- with every exit and cash movement while sizing_equity can stay pinned at
    -- the floor -- so without these the row records a derivation line the
    -- operator never saw. The nightly count is NULLABLE because the sizing-
    -- divergence note is absent when no daily_recommendations row exists.
    derivation_real_equity                   REAL,
    derivation_equity_floor                  REAL,
    derivation_nightly_recommendation_shares INTEGER,

    -- ===== THE OPERATOR'S ACTUAL PARAMS (nullable) =====
    actual_order_type      TEXT,
    actual_duration        TEXT,
    actual_stop_price      REAL,
    actual_limit_price     REAL,
    actual_quantity        INTEGER,
    actual_broker_order_id TEXT,                 -- hazards (c) + (d)

    -- ===== ORDER-VALIDITY OUTCOME (B3 item 5) =====
    -- Carried on `validity` ROWS ONLY. The table is APPEND-ONLY, so a `place`
    -- row can never be updated with an outcome learned later; a separate
    -- append-only `validity` intent is the only shape that both records the
    -- outcome and preserves the append-only property.
    validity_outcome TEXT,
    validity_detail  TEXT,

    CHECK (intent_kind IN ('place','decline','cancel','attest','validity')),
    CHECK (surface IN ('latch_panel')),
    CHECK (framework_order_type IS NULL OR framework_order_type IN ('STOP_LIMIT','LIMIT')),
    -- PROVENANCE COLUMNS ARE CONSTRAINED, not merely present: an audit-grade
    -- column that accepts anything will later look authoritative while holding
    -- a typo.
    CHECK (framework_duration IS NULL OR framework_duration = 'GOOD_TILL_CANCEL'),
    -- CANONICALISED BEFORE PERSISTENCE. Brokers render GTC where the framework
    -- stores GOOD_TILL_CANCEL, so an uncanonicalised actual would report a
    -- DURATION MISMATCH on a semantically identical order -- a false divergence
    -- in the one metric this ledger exists to compute.
    CHECK (actual_duration IS NULL OR actual_duration IN
           ('GOOD_TILL_CANCEL','DAY','FILL_OR_KILL','IMMEDIATE_OR_CANCEL',
            'END_OF_WEEK','END_OF_MONTH','NEXT_END_OF_MONTH','UNKNOWN')),
    -- The ACTUAL order type is an ENUM, not free text, and the stop leg is
    -- conditioned on it exactly as the framework side is.
    CHECK (actual_order_type IS NULL OR actual_order_type IN
           ('STOP_LIMIT','LIMIT','UNKNOWN')),
    -- A NON-ACCEPTED VALIDITY ROW CARRIES NO OBSERVED ORDER AT ALL. An outcome
    -- and its evidence must not be able to disagree: section G.4 tells a future
    -- reader that a broker order id on a validity row IS the exact linkage, so
    -- a `not_submitted` row beside an observed broker order id would sit in an
    -- append-only ledger carrying an authoritative-looking linkage that
    -- CONTRADICTS its own verdict. If a "visibly rejected order" evidence kind
    -- is ever wanted it gets its OWN outcome value, its own CHECKs and its own
    -- report bucket -- a different KIND of evidence, not a loosening of this one.
    CHECK (intent_kind <> 'validity'
           OR validity_outcome = 'accepted_by_broker'
           OR (actual_order_type IS NULL AND actual_duration IS NULL
               AND actual_stop_price IS NULL AND actual_limit_price IS NULL
               AND actual_quantity IS NULL
               AND actual_broker_order_id IS NULL)),
    CHECK (validity_outcome <> 'accepted_by_broker'
           OR actual_order_type <> 'STOP_LIMIT' OR actual_stop_price IS NOT NULL),
    CHECK (validity_outcome <> 'accepted_by_broker'
           OR actual_order_type <> 'LIMIT'      OR actual_stop_price IS NULL),
    CHECK (derivation_sizing_basis IS NULL
           OR derivation_sizing_basis IN ('limit_price','pivot')),
    CHECK (derivation_zone_cap_pct IS NULL OR derivation_zone_cap_pct > 0),
    -- `real_equity` may be ZERO or NEGATIVE and that is not an error -- it IS
    -- the account, and it is exactly why the floor exists. So it is bounded by
    -- NOTHING except being present; the floor and the nightly count are bounded
    -- positive like their siblings.
    CHECK (derivation_equity_floor IS NULL OR derivation_equity_floor > 0),
    CHECK (derivation_nightly_recommendation_shares IS NULL
           OR derivation_nightly_recommendation_shares > 0),
    CHECK (derivation_sizing_equity IS NULL OR derivation_sizing_equity > 0),
    CHECK (derivation_max_risk_pct IS NULL OR derivation_max_risk_pct > 0),
    CHECK (derivation_position_pct_cap IS NULL OR derivation_position_pct_cap > 0),
    -- PAIRED NULL. A close without the session it is DATED is exactly the
    -- provenance-free number 21-G exists to eliminate; a session without a
    -- close is a claim about a price that is not there.
    CHECK ((derivation_regime_close IS NULL) = (derivation_regime_close_session IS NULL)),
    CHECK (derivation_regime_close_session IS NULL
           OR COALESCE(length(derivation_regime_close_session) = 10
               AND date(derivation_regime_close_session) IS NOT NULL
               AND date(derivation_regime_close_session)
                   = derivation_regime_close_session
               AND CAST(substr(derivation_regime_close_session, 1, 4) AS INTEGER)
                   BETWEEN 1 AND 9999, 0)),
    CHECK (actual_quantity IS NULL OR actual_quantity > 0),
    -- EVERY PRICE IS POSITIVE. The price columns were shape-constrained (which
    -- kind may carry which leg) and never VALUE-constrained, so a raw append
    -- could store a negative or zero price -- including on an
    -- `accepted_by_broker` validity row, which then enters the agreement
    -- DENOMINATOR and reports a delta computed from a price that cannot exist.
    CHECK (framework_limit_price IS NULL OR framework_limit_price > 0),
    CHECK (framework_stop_price  IS NULL OR framework_stop_price  > 0),
    CHECK (actual_limit_price    IS NULL OR actual_limit_price    > 0),
    CHECK (actual_stop_price     IS NULL OR actual_stop_price     > 0),
    CHECK (framework_quantity IS NULL OR framework_quantity > 0),
    CHECK (attested_disposition IS NULL OR attested_disposition IN
           ('acted_manually','chose_not_to_act','was_away')),
    CHECK (validity_outcome IS NULL OR validity_outcome IN
           ('accepted_by_broker','rejected_by_broker','not_submitted','unknown')),
    -- the three-state contract, enforced in SQL rather than only in Python, and
    -- enforced in BOTH DIRECTIONS: a required field that is merely "required on
    -- its own kind" still lets every OTHER kind carry it, so a `place` row
    -- could ship a decline_reason and read as both.
    CHECK (intent_kind <> 'decline' OR (decline_reason IS NOT NULL
           AND length(trim(decline_reason)) > 0)),
    CHECK (intent_kind =  'decline' OR decline_reason IS NULL),
    CHECK (intent_kind =  'attest'  OR attested_disposition IS NULL),
    -- THE STOP LEG IS CONDITIONED ON THE ORDER TYPE. A STOP_LIMIT without its
    -- stop trigger is not the mandate; a LIMIT carrying one is the rejected
    -- FTRE shape. Neither should be storable.
    CHECK (framework_order_type <> 'STOP_LIMIT' OR framework_stop_price IS NOT NULL),
    CHECK (framework_order_type <> 'LIMIT'      OR framework_stop_price IS NULL),
    CHECK (intent_kind <> 'attest'  OR attested_disposition IS NOT NULL),
    -- An ACCEPTED-BY-BROKER validity row must carry a COMPLETE observed order,
    -- and "complete" means KNOWN and EXACTLY LINKED, not merely non-NULL: the
    -- agreement DENOMINATOR requires a known actual side and section G.4 claims
    -- exact linkage comes from validity rows, so an accepted row carrying a
    -- NULL broker order id or an UNKNOWN type/duration would look authoritative
    -- while satisfying neither claim. A row omitting actual_duration would make
    -- compute_order_delta return any_difference = None (UNKNOWN) rather than a
    -- clean quantity mismatch, and FTRE's worked example would still miss the
    -- metric it exists to feed.
    CHECK (validity_outcome <> 'accepted_by_broker' OR (
           actual_order_type IS NOT NULL AND actual_duration IS NOT NULL
       AND actual_limit_price IS NOT NULL AND actual_quantity IS NOT NULL
       AND actual_broker_order_id IS NOT NULL
       AND actual_order_type IN ('STOP_LIMIT','LIMIT')
       AND actual_duration <> 'UNKNOWN')),
    CHECK (intent_kind <> 'validity' OR (validity_outcome IS NOT NULL
           AND validated_place_intent_id IS NOT NULL
           -- SNAPSHOT CONTEXT IS STRUCTURALLY REQUIRED. Without a CHECK a row
           -- can be written with none of it, defeating the audit claim and
           -- making the staleness gate unverifiable after the fact.
           -- `validity_detail` carries a JSON object. THE ROSTER OF REQUIRED
           -- KEYS IS THE `json_remove(...)` PATH LIST BELOW -- that call is the
           -- MACHINE-READABLE source of truth, and LATCH_BROKER_SNAPSHOT_KEYS
           -- mirrors it under #11 (a test parses the path list out of this
           -- migration and asserts exact set equality with the constant). NO
           -- SITE STATES THE KEY COUNT: a cardinality is exactly the kind of
           -- fact that goes stale when an adjacent edit lands, and when it did,
           -- the fragment's emitted set and the row's required set disagreed by
           -- one -- which makes the audit row unwritable.
           AND validity_detail IS NOT NULL
           -- ===== THE NULL-PASS DEFENCE, AGAIN, ON JSON. The SAME class as the
           -- C.1.1 date defect one layer in: a MISSING key makes json_extract()
           -- return NULL, so `length(NULL) = 19` is NULL and a SQLite CHECK
           -- PASSES on NULL. Verified empirically: against the presence-and-
           -- shape chain written bare, the JSON object `{}` -- every key absent
           -- -- was ACCEPTED, and the whole audit claim was void. The fix is the
           -- two-part wrapper and it is not optional:
           --   * COALESCE(<chain>, 0) turns a NULL verdict into FALSE, so a
           --     missing key REJECTS instead of passing.
           --   * CASE WHEN json_valid(...) THEN ... ELSE 0 END gates the json_*
           --     calls, because SQLite does NOT guarantee AND-chain short-
           --     circuit: with a non-JSON value the bare chain raises
           --     OperationalError('malformed JSON') instead of rejecting, so a
           --     test asserting IntegrityError would fail against correct-
           --     looking DDL. CASE *does* short-circuit.
           AND CASE WHEN json_valid(validity_detail) THEN COALESCE(
               json_type(validity_detail) = 'object'
           -- EXACTLY THE ROSTER, NOT AT-LEAST-THE-ROSTER. The envelope carries
           -- EXACTLY the roster keys and is persisted VERBATIM, but a presence-
           -- and-shape chain only ever enforces AT LEAST -- so extra keys would
           -- ride into an append-only audit row unaudited, and since
           -- actual_digest covers only broker_snapshot_digest, two envelopes
           -- differing ONLY by extra content share an idempotency key, so the
           -- second is replayed and its extra content silently dropped instead
           -- of rejected. BOTH HALVES ARE REQUIRED, exactly as in C.1.1:
           -- json_remove closes EXTRA and is BLIND to MISSING (removing an
           -- absent path is a no-op, so `{}` passes it), while the shape chain
           -- closes MISSING and is blind to EXTRA.
           AND json_remove(validity_detail,
                   '$.broker_snapshot_ts', '$.broker_snapshot_branch',
                   '$.broker_snapshot_digest', '$.broker_snapshot_session',
                   '$.attributable_order_count', '$.exact_framework_match_count',
                   '$.indeterminate') = '{}'
           AND length(json_extract(validity_detail, '$.broker_snapshot_ts')) = 19
           AND json_extract(validity_detail, '$.broker_snapshot_ts') GLOB
               '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
           -- ALL THREE PREDICATES AT THIS SITE TOO. The IS NOT NULL leg was
           -- omitted here once and the site leaned on the outer COALESCE
           -- instead -- which happens to reject, but means "one mechanism,
           -- three predicates, every site" was not actually uniform.
           AND date(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),1,10))
               IS NOT NULL
           AND date(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),1,10))
               = substr(json_extract(validity_detail,'$.broker_snapshot_ts'),1,10)
           AND CAST(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),1,4)
                    AS INTEGER) BETWEEN 1 AND 9999
           AND CAST(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),12,2)
                    AS INTEGER) <= 23
           AND CAST(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),15,2)
                    AS INTEGER) <= 59
           AND CAST(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),18,2)
                    AS INTEGER) <= 59
           AND length(json_extract(validity_detail, '$.broker_snapshot_digest')) = 64
           AND json_extract(validity_detail, '$.broker_snapshot_digest')
               NOT GLOB '*[^0-9a-f]*'
           AND length(json_extract(validity_detail, '$.broker_snapshot_session')) = 10
           AND date(json_extract(validity_detail, '$.broker_snapshot_session'))
               IS NOT NULL
           -- ROUND-TRIP TOO, not IS NOT NULL alone -- the C.1.1 pair, applied
           -- here as well: without it '2026-02-30' NORMALISES and is accepted.
           AND date(json_extract(validity_detail, '$.broker_snapshot_session'))
               = json_extract(validity_detail, '$.broker_snapshot_session')
           AND CAST(substr(
                   json_extract(validity_detail,'$.broker_snapshot_session'),1,4)
                    AS INTEGER) BETWEEN 1 AND 9999
           -- A `validity` ROW MAY NOT CARRY AN `unavailable` SNAPSHOT. An
           -- UNKNOWN order book renders NO validity prompt in either direction,
           -- so a persisted validity row whose own snapshot says the book was
           -- unavailable is a row asserting an execution outcome it had no
           -- evidence for -- and this ledger is append-only, so it would assert
           -- it forever. The three-valued enum is the FRAGMENT's RENDER
           -- vocabulary; the ANSWER vocabulary is two-valued (the render status
           -- and the persisted answer are measured differently and do not share
           -- one enum). MIRRORED UNDER #11 LIKE EVERY OTHER ENUM CHECK -- this
           -- one escaped the mirror list purely because it is expressed as a
           -- json_extract predicate rather than a column CHECK, which is a
           -- difference in SYNTAX and not in kind.
           AND json_extract(validity_detail, '$.broker_snapshot_branch')
               IN ('presence','absence')
           AND json_type(validity_detail, '$.attributable_order_count') = 'integer'
           AND json_extract(validity_detail, '$.attributable_order_count') >= 0
           AND json_type(validity_detail, '$.exact_framework_match_count') = 'integer'
           AND json_extract(validity_detail, '$.exact_framework_match_count') >= 0
           AND json_type(validity_detail, '$.indeterminate')
               IN ('true','false'), 0) ELSE 0 END)),
    -- `validated_place_intent_id` is ALSO folded into the idempotency key, so
    -- two place intents on one latch cannot collide on an identical answer.
    -- Multiple validity rows for ONE parent stay LEGAL and are a feature: a
    -- CORRECTION (he answered "rejected", then learns it filled) is a NEW row,
    -- which is what append-only requires. Resolution is the LATEST by
    -- (recorded_ts, intent_id) FOR THAT PARENT.
    CHECK (intent_kind =  'validity' OR (validity_outcome IS NULL
           AND validity_detail IS NULL AND validated_place_intent_id IS NULL)),
    -- ===== SHAPE EXCLUSION: THREE CHECKS, ONE RULE =====
    -- Each intent kind carries exactly the columns its MEANING requires, so no
    -- row can read as two things at once and be counted twice by the report.
    --   place    -- a DECISION about a prepared order: framework + derivation,
    --               NO actual params, NO broker order id (it observed nothing).
    --   decline  -- also a DECISION about a prepared order, so it carries the
    --               SAME framework + derivation block. Erasing it would leave
    --               RD unable to audit WHAT was declined.
    --   validity -- an OBSERVATION: the actual params + the broker order id +
    --               the verdict, and NO framework/derivation block. It MUST be
    --               able to carry a DIVERGENT observed order (FTRE: framework
    --               LIMIT 18.89 / 9 sh vs actual LIMIT 18.89 / 10 sh) or the
    --               ledger could record agreements and never a divergence.
    --   cancel / attest -- neither. `actual_broker_order_id` IS allowed (a
    --               cancel REQUIRES it, hazard (c)).
    -- The first CHECK is keyed on the ORDER-BEARING kinds rather than on a list
    -- of the others, so a future intent kind is excluded BY DEFAULT.
    CHECK (intent_kind IN ('place','decline','validity') OR (
           framework_order_type IS NULL AND framework_duration IS NULL
       AND framework_stop_price IS NULL AND framework_limit_price IS NULL
       AND framework_quantity IS NULL
       AND derivation_zone_cap_pct IS NULL AND derivation_sizing_equity IS NULL
       AND derivation_max_risk_pct IS NULL AND derivation_position_pct_cap IS NULL
       AND derivation_risk_policy_id IS NULL AND derivation_sizing_basis IS NULL
       AND derivation_regime_close IS NULL
       AND derivation_regime_close_session IS NULL
       AND derivation_real_equity IS NULL AND derivation_equity_floor IS NULL
       AND derivation_nightly_recommendation_shares IS NULL
       AND actual_order_type IS NULL AND actual_duration IS NULL
       AND actual_stop_price IS NULL AND actual_limit_price IS NULL
       AND actual_quantity IS NULL)),
    -- `place` and `decline` carry NO actual params (a decision is not an
    -- observation).
    CHECK (intent_kind NOT IN ('place','decline') OR (
           actual_order_type IS NULL AND actual_duration IS NULL
       AND actual_stop_price IS NULL AND actual_limit_price IS NULL
       AND actual_quantity IS NULL)),
    -- ...and a `validity` row carries NO framework/derivation block: it reports
    -- an OBSERVATION, never a prepared order.
    CHECK (intent_kind <> 'validity' OR (
           framework_order_type IS NULL AND framework_duration IS NULL
       AND framework_stop_price IS NULL AND framework_limit_price IS NULL
       AND framework_quantity IS NULL
       AND derivation_zone_cap_pct IS NULL AND derivation_sizing_equity IS NULL
       AND derivation_max_risk_pct IS NULL AND derivation_position_pct_cap IS NULL
       AND derivation_risk_policy_id IS NULL AND derivation_sizing_basis IS NULL
       AND derivation_regime_close IS NULL
       AND derivation_regime_close_session IS NULL
       AND derivation_real_equity IS NULL AND derivation_equity_floor IS NULL
       AND derivation_nightly_recommendation_shares IS NULL)),
    -- A `place`/`decline` row must CARRY the whole drift-capable derivation
    -- block, not merely be permitted to: without this a place row can ship an
    -- authoritative-looking order with NULL sizing provenance -- the "four bare
    -- numbers" B1 exists to prevent, one layer down. The regime pair is
    -- included because the form is WITHHELD when the regime is undeterminable,
    -- so an OFFERED order always had one.
    --
    -- EXACTLY TWO DERIVATION COLUMNS ARE LEGITIMATELY NULLABLE HERE, and both
    -- have a REASON rather than an omission:
    --   derivation_nightly_recommendation_shares -- a fire with no
    --     daily_recommendations row has none, and the card renders no
    --     divergence note for it.
    --   derivation_risk_policy_id -- the RATE fed to compute_shares comes from
    --     cfg.risk.max_risk_pct, NOT from the policy row, so a prepared order is
    --     fully computable with no active policy row and the form is NOT
    --     withheld for one. The id is recorded for PROVENANCE, and the card
    --     renders an explicit "no active risk_policy row" line rather than a
    --     blank -- an unlabelled gap would be a quiet reduction.
    -- The two exempt columns are the ROSTER DERIVATION_NULLABLE_ON_DECISION in
    -- swing/latches/constants.py; the tests derive the required set as
    -- {every derivation_* column in the schema} - DERIVATION_NULLABLE_ON_DECISION
    -- and state no cardinality, so adding a derivation column extends the
    -- required set automatically and adding an EXEMPTION is a deliberate edit to
    -- a named constant with a reviewer.
    CHECK (intent_kind NOT IN ('place','decline') OR (
           derivation_zone_cap_pct IS NOT NULL
       AND derivation_sizing_equity IS NOT NULL
       AND derivation_max_risk_pct IS NOT NULL
       AND derivation_position_pct_cap IS NOT NULL
       AND derivation_sizing_basis IS NOT NULL
       AND derivation_regime_close IS NOT NULL
       AND derivation_regime_close_session IS NOT NULL
       AND derivation_real_equity IS NOT NULL
       AND derivation_equity_floor IS NOT NULL)),
    -- HAZARD (c) MADE STRUCTURAL: a cancel MUST name one broker order. There is
    -- no by-ticker cancel path anywhere and the schema makes one unwritable.
    CHECK (intent_kind <> 'cancel'  OR (actual_broker_order_id IS NOT NULL
           AND length(trim(actual_broker_order_id)) > 0)),
    -- ...and it is never BLANK when present, on any kind.
    CHECK (actual_broker_order_id IS NULL
           OR length(trim(actual_broker_order_id)) > 0),
    -- A broker order id is an OBSERVATION. `place` and `decline` are DECISIONS
    -- about a prepared order and have observed nothing, so allowing them a
    -- broker id blurs exact linkage against inference and would let a plain
    -- accept row read as broker-confirmed.
    CHECK (intent_kind NOT IN ('place','decline')
           OR actual_broker_order_id IS NULL),
    -- a `place` or `decline` records a complete order or it is not a record of
    -- a decision ABOUT an order
    CHECK (intent_kind NOT IN ('place','decline') OR (framework_order_type IS NOT NULL
           AND framework_limit_price IS NOT NULL AND framework_quantity IS NOT NULL
           AND framework_quantity > 0 AND framework_duration IS NOT NULL)),
    -- THE THREE-PREDICATE DATE GUARD (section C.1.1), verbatim.
    CHECK (COALESCE(length(detection_date) = 10
           AND date(detection_date) IS NOT NULL
           AND date(detection_date) = detection_date
           AND CAST(substr(detection_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    CHECK (COALESCE(length(action_session_date) = 10
           AND date(action_session_date) IS NOT NULL
           AND date(action_session_date) = action_session_date
           AND CAST(substr(action_session_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    -- `recorded_ts` DRIVES THE MONTHLY REPORT'S CUTOFF AND ORDERING, so an
    -- unconstrained TEXT column lets a raw insert or a repo bug silently
    -- misbucket a monthly parity read while looking authoritative. Local ISO
    -- seconds, exactly: YYYY-MM-DDTHH:MM:SS.
    --
    -- THE `datetime(x) = replace(x,'T',' ')` FORM DOES NOT ENFORCE THAT
    -- CONTRACT. Verified empirically, it ACCEPTS both '2026-07-28 12:00:00' (a
    -- SPACE separator -- replace() is a no-op, so it compares equal to itself)
    -- and '2026-07-28T24:00:00' (SQLite does NOT normalise hour 24 away). A
    -- space-separated stamp then sorts differently from a T-separated one in
    -- the exact ORDER BY the monthly report uses, and hour 24 is a stamp no
    -- clock produced. So the shape is pinned by GLOB (one expression fixing all
    -- 19 positions), the DATE HALF gets C.1.1's BOTH-halves pair, and each time
    -- component gets an explicit range. `datetime(x) IS NOT NULL` is a belt.
    CHECK (COALESCE(
           length(recorded_ts) = 19
           AND recorded_ts GLOB
               '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
           AND datetime(recorded_ts) IS NOT NULL
           AND date(substr(recorded_ts, 1, 10)) IS NOT NULL
           AND date(substr(recorded_ts, 1, 10)) = substr(recorded_ts, 1, 10)
           AND CAST(substr(recorded_ts, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
           AND CAST(substr(recorded_ts, 12, 2) AS INTEGER) <= 23
           AND CAST(substr(recorded_ts, 15, 2) AS INTEGER) <= 59
           AND CAST(substr(recorded_ts, 18, 2) AS INTEGER) <= 59, 0)),
    CHECK (evaluation_run_id > 0),
    CHECK (length(trim(ticker)) > 0),

    UNIQUE (idempotency_key)
);

CREATE INDEX ix_loi_candidate_id        ON latch_order_intents(candidate_id);
CREATE INDEX ix_loi_ticker_detection    ON latch_order_intents(ticker, detection_date);
CREATE INDEX ix_loi_action_session_date ON latch_order_intents(action_session_date);

-- IDENTITY COHERENCE -- 0032's pair, pointed at this table. The denormalised
-- identity copies must not be able to disagree with `candidate_id`, for the
-- same RD-finding-4 reason. `pipeline_run_id` carries no FK here, so this
-- trigger is the ONLY thing that validates it -- at INSERT, while the referent
-- still exists; afterwards the recorded fact is preserved forever.
CREATE TRIGGER trg_loi_identity_coherent_insert
BEFORE INSERT ON latch_order_intents
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'latch_order_intents identity block does not match its candidate_id')
    WHERE NOT EXISTS (
        SELECT 1 FROM candidates c
        JOIN evaluation_runs e ON e.id = c.evaluation_run_id
        WHERE c.id = NEW.candidate_id
          AND c.bucket = 'aplus'
          AND c.evaluation_run_id = NEW.evaluation_run_id
          AND c.ticker = NEW.ticker
          AND e.action_session_date = NEW.detection_date
    );
    SELECT RAISE(ABORT, 'latch_order_intents pipeline_run_id is not this evaluation run''s twin')
    WHERE NEW.pipeline_run_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM pipeline_runs p
        WHERE p.id = NEW.pipeline_run_id
          AND p.evaluation_run_id = NEW.evaluation_run_id
    );
END;

CREATE TRIGGER trg_loi_identity_coherent_update
BEFORE UPDATE OF candidate_id, evaluation_run_id, ticker, detection_date,
                 pipeline_run_id
ON latch_order_intents
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'latch_order_intents identity block does not match its candidate_id')
    WHERE NOT EXISTS (
        SELECT 1 FROM candidates c
        JOIN evaluation_runs e ON e.id = c.evaluation_run_id
        WHERE c.id = NEW.candidate_id
          AND c.bucket = 'aplus'
          AND c.evaluation_run_id = NEW.evaluation_run_id
          AND c.ticker = NEW.ticker
          AND e.action_session_date = NEW.detection_date
    );
    SELECT RAISE(ABORT, 'latch_order_intents pipeline_run_id is not this evaluation run''s twin')
    WHERE NEW.pipeline_run_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM pipeline_runs p
        WHERE p.id = NEW.pipeline_run_id
          AND p.evaluation_run_id = NEW.evaluation_run_id
    );
END;

-- THE VALIDITY PARENT LINK, ENFORCED. The self-FK only prevents a DANGLING
-- pointer -- on its own it happily accepts a `validity` row pointing at a
-- `decline`, a `cancel`, another `validity`, or a `place` row belonging to a
-- DIFFERENT latch, any of which attaches an execution outcome to the wrong
-- order and makes the ledger self-contradictory. A CHECK cannot reference
-- another row, so this is a trigger.
--
-- THE SESSION LEG IS ENFORCED RATHER THAN ASSERTED: section C.2 declares that a
-- `validity` row's action_session_date IS the parent place row's, and leaving
-- that leg to the repo would let a raw insert (or a handler that reached for
-- the submitted anchor, the ONE mistake most likely here) file an August answer
-- under an August mandate date while pointing at a July order -- and every
-- monthly read afterwards would attribute the mandate to the wrong month.
-- An aged prompt is answered in a LATER session, and that later session is
-- recorded in `recorded_ts`, not in `action_session_date`, so requiring the
-- copy is what makes the aged prompt recordable CORRECTLY rather than what
-- blocks it.
CREATE TRIGGER trg_loi_validity_parent_insert
BEFORE INSERT ON latch_order_intents
FOR EACH ROW WHEN NEW.validated_place_intent_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
        'latch_order_intents validity parent must be a place row on the same latch and the child must carry the parent''s action_session_date')
    WHERE NOT EXISTS (
        SELECT 1 FROM latch_order_intents parent
        WHERE parent.intent_id  = NEW.validated_place_intent_id
          AND parent.intent_kind = 'place'
          AND parent.candidate_id = NEW.candidate_id
          AND parent.action_session_date = NEW.action_session_date);
END;

CREATE TRIGGER trg_loi_validity_parent_update
BEFORE UPDATE OF validated_place_intent_id, candidate_id, action_session_date
ON latch_order_intents
FOR EACH ROW WHEN NEW.validated_place_intent_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
        'latch_order_intents validity parent must be a place row on the same latch and the child must carry the parent''s action_session_date')
    WHERE NOT EXISTS (
        SELECT 1 FROM latch_order_intents parent
        WHERE parent.intent_id  = NEW.validated_place_intent_id
          AND parent.intent_kind = 'place'
          AND parent.candidate_id = NEW.candidate_id
          AND parent.action_session_date = NEW.action_session_date);
END;

-- THE IMMUTABILITY BARRIER. For a ledger whose entire value is that HISTORY
-- DOES NOT MOVE, convention is not enough: one bug or one manual UPDATE
-- silently rewrites a month RD has already read. STRICTER than the in-tree
-- reconciliation_corrections precedent, deliberately -- that table needs UPDATE
-- for its superseded_by_correction_id chain and this one needs nothing of the
-- kind (every correction here is already a new row).
--
-- CONSEQUENCE, binding on every FK this table declares: on an UPDATE-forbidden
-- table `ON DELETE SET NULL` is UNIMPLEMENTABLE -- the cascade IS an UPDATE and
-- this trigger aborts it. So every FK here is ON DELETE RESTRICT, and a test
-- asserts no SET NULL appears in the table's DDL.
CREATE TRIGGER trg_loi_no_update BEFORE UPDATE ON latch_order_intents
BEGIN SELECT RAISE(ABORT, 'latch_order_intents is append-only: record a new row'); END;
CREATE TRIGGER trg_loi_no_delete BEFORE DELETE ON latch_order_intents
BEGIN SELECT RAISE(ABORT, 'latch_order_intents is append-only: rows are never deleted'); END;

UPDATE schema_version SET version = 33;

COMMIT;
