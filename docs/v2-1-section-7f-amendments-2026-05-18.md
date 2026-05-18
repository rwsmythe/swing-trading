# V2.1 §VII.F Amendment Inventory — 2026-05-18 (Phase 12.5 #3 collation)

This doc indexes all pending V2.1 §VII.F amendments accumulated across Phase 9 / Phase 10 / Phase 11 / Phase 12 / Phase 12.5 return reports + plan + spec + recon docs as of Phase 12.5 #3 ship. Each entry carries an `A-<phase>.<bundle>.<index>` hash for cross-reference + a 1-sentence summary + the source-of-truth doc + the line ref (where determinable). Inline supersession notes live at each affected spec/plan doc (per T-3.7 precedent for Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104).

**Source roster** (canonical 34 return-report files inventoried at task time; plan §A T-3.4 baseline was 33 — the 34th file is `docs/phase12-5-bundle-3-project-hygiene-writing-plans-return-report.md` for this dispatch's own writing-plans, which contains the Phase 12.5 #3 T-3.7 amendment `A-12.5.3.H4-banner-clears` already indexed below under §1 Phase 12.5 #3; no new uncatalogued amendments surfaced from that 34th file). Total **86 amendment rows** indexed (62 in initial collation + 24 net after Codex R1 Major #3 expansion of Phase 11 grouped IDs into per-row entries: removed 3 grouped lines A-11.A/B/D + added 27 per-row Phase 11 entries = +24 net).

**V2.1 §VII.F is the source-of-truth methodology-correction protocol** (per `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`). Each amendment routes through this protocol when promoted to a methodology revision. This inventory is the orchestrator's working list; promotion is a separate operator action.

**Scope clarifications:**
- This inventory captures amendments banked in dispatch return reports + recon docs + CLAUDE.md status-line entries. Amendments banked inline in plan/spec bodies (e.g., recon docs already point at affected spec/plan paragraphs) are indexed once here.
- Amendments are NOT methodology revisions yet — promotion to a methodology revision proposal is a separate operator action per V2.1 §VII.F protocol.
- Methodology references in `reference/methodology/` are NEVER modified in-place per V2.1 §VII.F.

---

## Table of contents

- §1 Amendments by phase
- §2 Amendments by classification (text-only / cross-reference / wording / contract drift)
- §3 Promotion routing (V2.1 §VII.F protocol entry path)

---

## §1 Amendments by phase

### Phase 9 (2 amendments banked across Sub-bundles A-E)

- **A-9.D.1**: Spec §7 wording amendment — `sector_industry_evaluation_run_id` keyed on `(ticker, action_session_for_run(now))` vs shipped chart_pattern-mirror hidden-anchor pattern. Source: `docs/phase9-bundle-D-task-D0-recon.md` recon-doc-supersession + `docs/phase9-bundle-D-return-report.md` §6.3/§8 #1. Status: text-only; recon-doc-supersession applies.
- **A-9.E.1**: Spec §6.2 wording amendment — Account Order History multi-line parser pattern variants (4 patterns A-D + `WAIT TRG` status + `BASE-X.XX` conditional skip). Source: `docs/phase9-bundle-E-task-E3-parser-recon.md` recon-doc-supersession. Status: text-only; recon-doc-supersession applies.

### Phase 10 (22 amendments banked across Sub-bundles A-E)

- **A-10.A.1**: Wilson CI standard-vs-continuity-correction reference value. Plan §D Task A.1 reference value `[0.094, 0.901]` is continuity-form; implementation chose standard `[0.150, 0.850]`. Source: `docs/phase10-bundle-A-return-report.md` §8 #1. Status: text-only.
- **A-10.A.2**: `read_at_trade_time_policy` signature takes `policy_id_stamp: int | None` directly (Trade dataclass lacks `risk_policy_id_at_lock` column). Source: `docs/phase10-bundle-A-return-report.md` §8 #2. Status: contract drift; defer.
- **A-10.A.3**: `BaseLayoutVM.stale_banner: str | None = None` (not `bool = False`) to match existing base-layout pattern. Source: `docs/phase10-bundle-A-return-report.md` §8 #3. Status: text-only.
- **A-10.B.1**: T-B.1 `mistake_cost_R` always recomputes per-trade because `review_log` is cadence-grain with no per-trade FK. Source: `docs/phase10-bundle-B-return-report.md` §5. Status: cross-reference.
- **A-10.B.2**: T-B.2 `ALL_COHORTS_KEY='__all__'` sentinel avoids collision with legitimate cohort name containing "all". Source: `docs/phase10-bundle-B-return-report.md` §5. Status: text-only.
- **A-10.B.3**: T-B.4 `cumulative_R_pct_of_capital` rendered in PERCENT (not proportion) to match `absolute_loss_tripwire_pct` comparison. Source: `docs/phase10-bundle-B-return-report.md` §5. Status: wording precision.
- **A-10.B.4**: T-B.7 display-block placement (amendment assumed "existing mistake_cost_R display" but Phase 6 only had operator-input form; implementation added BOTH fields in new block for symmetry). Source: `docs/phase10-bundle-B-return-report.md` §5. Status: text-only.
- **A-10.B.5**: T-B.2 surfaces 7 cohort tabs not 5 (4 pre-registered + 2 orphan-label + "All"); production has orphan-labeled closed trades that would otherwise be hidden. Source: `docs/phase10-bundle-B-return-report.md` §5 (gate-surfaced). Status: contract drift.
- **A-10.C.1**: T-C.1 `cohort_relative_to_aplus` rendering (spec §3.3 delta proportion vs brief §0.9 raw-ratio percent — implementation follows brief). Source: `docs/phase10-bundle-C-return-report.md` §5. Status: wording precision.
- **A-10.C.2**: T-C.1 `cohort_doctrine_deviation_class` baseline enum (spec "0" vs implementation "baseline" string). Source: `docs/phase10-bundle-C-return-report.md` §5. Status: text-only.
- **A-10.C.3**: T-C.5 filter SQL predicate (amendment `IS NULL` vs schema `= 'unresolved'`; implementation matches Phase 9 Sub-bundle B). Source: `docs/phase10-bundle-C-return-report.md` §5. Status: wording precision.
- **A-10.C.4**: T-C.5 threading (amendment CohortFilter-enum-OR-bool — implementation bool throughout, filter applied at COMPUTE layer before suppression cascade). Source: `docs/phase10-bundle-C-return-report.md` §5. Status: contract drift.
- **A-10.C.5**: T-C.5 toggle href shape (amendment absolute path vs implementation relative query form). Source: `docs/phase10-bundle-C-return-report.md` §5. Status: text-only.
- **A-10.D.1**: D1 dispatch brief §0.8 PROVISIONAL/LIVE math wording (brief said `max(floor, equity)`; plan §A.6 + shipped code return raw equity). Source: `docs/phase10-bundle-D-return-report.md` §5. Status: wording precision.
- **A-10.D.2**: D2 plan §A.19 SQL references `criterion_results.criterion_name` but actual schema table is `candidate_criteria`. Source: `docs/phase10-bundle-D-return-report.md` §5. Status: cross-reference.
- **A-10.D.3**: D3 capital-friction trend window size not explicitly pinned in plan §G T-D.1 (implementation reused 30-session window from funnel for parity). Source: `docs/phase10-bundle-D-return-report.md` §5. Status: text-only.
- **A-10.D.4**: D4 `MaturityStageRow` gains `capital_denominator_dollars` + `capital_denominator_badge_text` fields not in plan §G T-D.3 acceptance. Source: `docs/phase10-bundle-D-return-report.md` §5. Status: contract drift.
- **A-10.D.5**: D5 `aplus_take_rate_per_run` NOT clamped to [0, 1] per Codex R1 M#3 (honest emit for data-quality anomaly surface). Source: `docs/phase10-bundle-D-return-report.md` §5. Status: contract drift.
- **A-10.E.1**: E1 T-E.3 `ConfigPageVM` (not `ConfigVM` per brief §0.11 — brief-author name mismatch). Source: `docs/phase10-bundle-E-return-report.md` §5. Status: text-only.
- **A-10.E.2**: E2 T-E.3 retrofitted 10 base-layout VMs (plan §H named 6; implementation added 4 more whose templates extend base.html.j2 per CLAUDE.md gotcha — defense-in-depth). Source: `docs/phase10-bundle-E-return-report.md` §5. Status: contract drift.
- **A-10.E.3**: E3 T-E.5 service function is `record_snapshot` (NOT `record_snapshot_with_audit` per brief §0.5 — Phase 9 Sub-bundle C ship-time naming preserved). Source: `docs/phase10-bundle-E-return-report.md` §5. Status: cross-reference.
- **A-10.E.4**: E4 T-E.1 confidence-floor warning never drops at production callsite by construction (N=10 < global_confidence_floor_n=20; discriminating test exercises window_size=20). Source: `docs/phase10-bundle-E-return-report.md` §5. Status: contract drift.
- **A-10.E.5**: E5 T-E.1 `mistake_cost_R_rolling_N_total` rolling LINE renders SUM not mean (Codex R1 M#1 fix). Source: `docs/phase10-bundle-E-return-report.md` §5. Status: wording precision (`render_class_d` underlying_class='point' semantic).
- **A-10.plan.1**: Plan §A.11 transition-history supersession — Phase 9 Sub-bundle C closed the audit-table capture gap. Source: `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` §A.11 inline note. Status: text-only.
- **A-10.plan.2**: Plan §A.21 sum-metric Class assignment (mistake_cost_R_rolling_N_total rendered point-only; sum-class with bootstrap CI deferred V2). Source: same plan §A.21 inline note. Status: contract drift.

### Phase 11 (Schwab API arc — 27 amendments banked across Sub-bundles A/B/C/D)

Sub-bundle A (13 amendments banked):

- **A-11.A.1**: schwabdev camelCase kwarg discipline (Client.account_orders + price_history + account_details + transactions). Source: `docs/schwab-bundle-A-return-report.md`. Status: promoted as CLAUDE.md gotcha; spec text pending.
- **A-11.A.2**: Typed `SchwabApiError` audit-row close discipline (`record_call_finish` before re-raise). Source: same. Status: promoted as gotcha.
- **A-11.A.3**: `Schwabdev` capital-S logger prefix correction (was lowercase in plan §H.8). Source: same. Status: text-only.
- **A-11.A.4**: schwabdev silent-failure-mode discipline — `update_tokens` print-and-return-silently semantics. Source: same. Status: contract drift.
- **A-11.A.5**: Tokens DB plaintext-at-rest (V1 ACL-only protection; V2 encryption=`<key>` candidate). Source: same. Status: contract drift.
- **A-11.A.6**: Sandbox short-circuit gating (`environment='sandbox'` writes audit row but NOT domain row). Source: same. Status: contract drift.
- **A-11.A.7**: `setLogRecordFactory` 3-layer redaction (level-suppression + content-redactor + record-factory). Source: same. Status: promoted as gotcha.
- **A-11.A.8**: Cassette runbook V2-PLANNED (V1 mock-based tests only). Source: same. Status: text-only.
- **A-11.A.9**: Schwab API source-artifact reference shape (`schwab_api:call/{call_id}` URI). Source: same. Status: contract drift.
- **A-11.A.10**: `swing schwab setup` requires clean tokens DB state (logout→setup recovery). Source: same. Status: promoted as gotcha; V2 self-healing.
- **A-11.A.11**: 7-day Schwab refresh-token clock + WARN/ERROR severity escalation. Source: same. Status: text-only.
- **A-11.A.12**: Schwab CLI sub-commands REFUSE while pipeline `state='running'` (mirror Finviz). Source: same. Status: promoted as gotcha.
- **A-11.A.13**: Force-refresh kwarg semantic asymmetry (`force_access_token=True` vs `force_refresh_token=True`). Source: same. Status: contract drift.

Sub-bundle B (2 amendments banked):

- **A-11.B.1**: Lease status fields V2-deferred (R2 M#2 + R3 M#2 ACCEPT-WITH-RATIONALE family — combined). Source: `docs/schwab-bundle-B-return-report.md`. Status: contract drift.
- **A-11.B.2**: `34be84e` gate-caught camelCase trader.py:362 fix (`max_results=` → `maxResults=`). Source: same. Status: cross-reference (matches A-11.A.1 family).

Sub-bundle C (no formally-banked amendments; defects all surfaced as Codex findings + resolved).

Sub-bundle D (12 amendments banked — all CLAUDE.md gotcha promotions at T-D.4):

- **A-11.D.1**: schwabdev camelCase kwarg gotcha (formalization of A-11.A.1). Source: `docs/schwab-bundle-D-return-report.md` §T-D.4.
- **A-11.D.2**: Typed `SchwabApiError` audit-row close gotcha (formalization of A-11.A.2). Source: same.
- **A-11.D.3**: `swing schwab setup` clean-state recovery gotcha (A-11.A.10 formalization). Source: same.
- **A-11.D.4**: 7-day refresh-token clock gotcha (A-11.A.11 formalization). Source: same.
- **A-11.D.5**: `Schwabdev` capital-S logger prefix gotcha (A-11.A.3 formalization). Source: same.
- **A-11.D.6**: schwabdev silent-failure-mode gotcha (A-11.A.4 formalization). Source: same.
- **A-11.D.7**: Tokens DB plaintext-at-rest gotcha (A-11.A.5 formalization). Source: same.
- **A-11.D.8**: Pipeline-active CLI exclusion gotcha (A-11.A.12 formalization). Source: same.
- **A-11.D.9**: Sandbox short-circuit gating gotcha (A-11.A.6 formalization). Source: same.
- **A-11.D.10**: `setLogRecordFactory` content-redaction gotcha (A-11.A.7 formalization). Source: same.
- **A-11.D.11**: Cassette runbook V2-PLANNED gotcha (A-11.A.8 formalization). Source: same.
- **A-11.D.12**: Source-artifact reference shape gotcha (A-11.A.9 formalization). Source: same.

### Phase 12 Sub-bundle A (Schwab operational pain — 0 amendments banked)

- ZERO V2.1 §VII.F amendments banked (operator-locked dispatch; brief played plan-role; ZERO Critical/Major surfaced).

### Phase 12 Sub-bundle B (Schwab web-UI-friendliness — banked 10 V2 candidates; some routable as amendments)

- **A-12.B.1**: `surface='cli'` audit-row at v18 — V2.1 §VII.F amendment banked to widen enum to `('pipeline', 'cli', 'web')` via 0019_*.sql migration. Source: `docs/phase12-bundle-B-return-report.md` + CLAUDE.md status-line entry. Status: schema-CHECK widening (separate routing — became consumer-side at v19 in Phase 12 C.A migration).

### Phase 12 Sub-bundle C arc (Auto-correct reconciliation — 18 amendments banked across C.A+C.B+C.C+C.D)

- **A-12.C.A.1**: Spec §3.1 column-count header drift (19 vs 20 rows). Source: `docs/phase12-bundle-C-A-return-report.md` §I.16. Status: text-only.
- **A-12.C.A.2**: Plan §A.12 Phase 11 backup-gate precedent claim (no such gate existed). Source: `docs/phase12-bundle-C-A-return-report.md`. Status: cross-reference.
- **A-12.C.A.3**: Plan §B.4 SHA256 byte-equality impossibility with SQLite Connection.backup (Codex R2 Minor #1 correction). Source: `docs/phase12-bundle-C-A-return-report.md`. Status: contract drift.
- **A-12.C.A.4**: Dispatch brief §0.5 `pre_version <= 18` vs `== 18` equality form. Source: `docs/phase12-bundle-C-A-return-report.md`. Status: wording precision (now promoted as CLAUDE.md gotcha).
- **A-12.C.A.5**: Plan §B.2 `_RESOLUTION_VALUES` widening fold-into T-A.2 (schema-CHECK + Python-constant atomic-consistency). Source: `docs/phase12-bundle-C-A-return-report.md`. Status: contract drift (promoted as CLAUDE.md gotcha).
- **A-12.C.B.1**: Spec §4.3.1 Shape A/B enumeration. Source: `docs/phase12-bundle-C-B-return-report.md`. Status: text-only.
- **A-12.C.B.2**: Spec §4.3.1 contradictory-date-evidence both sides. Source: `docs/phase12-bundle-C-B-return-report.md`. Status: contract drift.
- **A-12.C.B.3**: Plan §C.3 `:.2f` rendering pin. Source: `docs/phase12-bundle-C-B-return-report.md`. Status: text-only.
- **A-12.C.B.4**: Plan §C.9 cash_movement multi-field comparison vector. Source: `docs/phase12-bundle-C-B-return-report.md`. Status: contract drift.
- **A-12.C.B.5**: Spec §5.5 `functools.partial` composition documentation. Source: `docs/phase12-bundle-C-B-return-report.md`. Status: text-only.
- **A-12.C.B.6**: Spec §6.2.1 cross-reference completeness. Source: `docs/phase12-bundle-C-B-return-report.md`. Status: cross-reference.
- **A-12.C.C.1**: D1 pivot helper relocation candidate. Source: `docs/phase12-bundle-C-C-return-report.md`. Status: contract drift.
- **A-12.C.C.2**: D2 sentinel rule wording. Source: same. Status: wording precision.
- **A-12.C.C.3**: D3 test-side adjustments dependency on C.D filter widening. Source: same. Status: cross-reference.
- **A-12.C.C.4**: D4 SAVEPOINT-uniqueness test mechanic. Source: same. Status: contract drift.
- **A-12.C.C.5**: D5 inline SQL vs repo helpers. Source: same. Status: contract drift.
- **A-12.C.C.6**: D6 T-C.11 scope; D7 view_models.py touch. Source: same. Status: text-only.
- **A-12.C.D.1**: Plan §A.5 base-layout VM banner predicate widening count drift (plan said "14"; actual grep is 13). Source: `docs/phase12-bundle-C-D-return-report.md`. Status: cross-reference.

### Post-Phase-12 Schwab mapper arc (5 amendments banked across Sub-bundles 1/1.5/2)

- **A-pp12.1.1**: V2 OQ-F Pass-2 multi-leg tier-1 widening (deferred). Source: `docs/post-phase12-schwab-mapper-bundle-1-return-report.md` (if present) + spec §6.6. Status: contract drift — V2-DEFERRED.
- **A-pp12.2.1**: Spec §7.1 `SchwabStatusVM.state` triplet supersession (LIVE/PROVISIONAL/DEGRADED not CONFIGURED/PROVISIONAL/NOT_CONFIGURED). Source: `docs/post-phase12-schwab-mapper-bundle-2-return-report.md` §7.1 #1. Status: wording precision.
- **A-pp12.2.2**: Spec §7.1 `SchwabCallSummary.status` enum widening (4 → 6 schema CHECK values; adds `in_flight` + `concurrent_refresh`). Source: same return report §7.1 #2. Status: contract drift.
- **A-pp12.2.3**: Spec §7.1 `tokens_db_path` masking convention (`~/<relative-path-from-home>` POSIX shorthand). Source: same return report §7.1 #3. Status: wording precision.
- **A-pp12.2.4**: Spec §7.1 `SchwabCallSummary.error_excerpt` rendering scope (VM-only, not rendered under §7.4 OQ-D CLI 1:1 LOCK). Source: same return report §7.1 #4. Status: contract drift.

### Phase 12.5 #1 (OQ-F multi-leg tier-1 auto-redirect — 1 amendment banked)

- **A-12.5.1.1**: Plan §A T-1.5.B 3-line drift after Codex R2 Major #1 deletion (unreachable `auto_redirect_skipped_sandbox` backfill infrastructure deleted at `ebb05a8`). Source: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-executing-plans-return-report.md` §5. Status: text-only.

### Phase 12.5 #2 (Web Tier-2 discrepancy-resolution — 6 amendments banked)

- **A-12.5.2.J1**: Builder kwarg amendment (writing-plans §J — plan supersedes spec). Source: `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-writing-plans-return-report.md` §J1. Status: contract drift.
- **A-12.5.2.J2**: POST-service `ValueError` 14a/14b split (400 if re-read confirms pending; 409 if terminal state). Source: same return report §J2. Status: contract drift.
- **A-12.5.2.J3**: Parametric `valid_choices` (plan supersedes spec). Source: same return report §J3. Status: contract drift.
- **A-12.5.2.A1**: Plan §C.1 class-name drift in `trades.py` + `schwab.py:558` (4 names mis-labeled; line numbers correct). Source: `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-executing-plans-return-report.md` §7. Status: text-only.
- **A-12.5.2.A2**: Plan §K test projection +81 fast tests vs actual +135 (parametrize-granularity overshoot precedent). Source: same return report. Status: text-only (precedent).
- **A-12.5.2.A3**: Plan §A T-2.2 acceptance count "14 fields" for `ReconcilePreResolutionContext` vs spec §5.2 actual 15. Source: same return report. Status: cross-reference.

### Phase 12.5 #3 (Project hygiene maintenance pass — 1 amendment banked at T-3.7; this dispatch's own)

- **A-12.5.3.H4-banner-clears** (NEW; T-3.7): Phase 12.5 #1 plan §H.4 line 1071 + spec §9.3 S4 line 940 + spec §5 line 104 — banner CLEARS immediately on tier-3 override (NOT "stays present") per shipped helper SQL semantic. Source: amended inline this dispatch at `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md:1071` + `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md:104,940`. Status: text-only; superseded inline.

---

## §2 Amendments by classification

| Class | Approx Count | Notes |
|---|---|---|
| Text-only supersession | ~22 | inline notes + indexed here |
| Cross-reference drift | ~10 | doc-doc mismatch (e.g., plan/spec column-count drift, brief vs plan naming) |
| Wording precision | ~9 | binding contracts where wording diverges from shipped semantic |
| Contract drift | ~18 | shipped-vs-stated semantic where shipped is the authoritative behavior |

(Counts approximate; an individual amendment may overlap classifications.)

---

## §3 Promotion routing

When an amendment is promoted to a V2.1 §VII.F methodology revision, follow the protocol at `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` §VII.F. The orchestrator selects amendments from this inventory + drafts a single revision proposal. Methodology references in `reference/methodology/` are NEVER modified in-place per V2.1 §VII.F protocol.

**Promotion priority guidance** (orchestrator-judgement; not binding):

1. **Highest priority — contract drift on shipped-and-load-bearing semantics** (e.g., A-12.5.3.H4-banner-clears, A-pp12.2.1 state-triplet supersession, A-12.5.2.J2 ValueError 14a/14b split): these are the closest to actual production behavior diverging from documented intent + most likely to surface in future dispatches.
2. **Medium priority — schema-vs-Python-mirror consistency lessons** (e.g., A-12.C.A.4 backup-gate equality form, A-12.C.A.5 `_RESOLUTION_VALUES` atomic-consistency): already promoted as CLAUDE.md gotchas but the spec body still carries the original wording.
3. **Lower priority — text-only supersessions where the spec narrative is non-load-bearing** (e.g., A-10.B.2 sentinel-key convention, A-12.C.B.3 `:.2f` rendering pin): can be batched at the next methodology-revision cycle.

**OUT OF SCOPE here**: methodology-reference modifications (those route through `reference/methodology/` corrections protocol, not V2.1 §VII.F directly).

---

*End of inventory. Phase 12.5 #3 T-3.4 collation — 86 amendment rows indexed across Phase 9 + Phase 10 + Phase 11 + Phase 12 + post-Phase-12 + Phase 12.5 arcs (post Codex R1 Major #3 expansion of Phase 11 grouped IDs into per-row entries). Each amendment carries A-<phase>.<bundle>.<index> hash for cross-reference. Promotion is operator-paced via the V2.1 §VII.F protocol.*
