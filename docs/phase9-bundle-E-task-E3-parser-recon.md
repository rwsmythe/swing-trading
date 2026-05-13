# Phase 9 Sub-bundle E — Task E.3: Account Order History multi-line parser recon

**Purpose:** Document the multi-line order-group structure observed in operator's 4 real-world Schwab/TOS Account Statement exports + supersede spec §6.2's single-row assumption with the post-T-E.3 binding parser design. Per dispatch brief §0.5 #5 + plan §G T-E.3.

## §1 Problem statement

Phase 9 Sub-bundle B landed `extract_stop_orders` per spec §6.2 with a single-row matcher: each row's `Status`, `Side`, `Pos Effect`, `Type`, `Spread`, `Price` columns are inspected; matches with `Status starts with WORKING` + `Side contains SELL` + `Pos Effect contains CLOSE` + `Order Type/Type contains STP/STOP` + `Spread in ("", "STOCK")` are emitted. The synthetic test fixture used in `tests/journal/test_tos_import_reconciliation_extension.py` §5 (`_TOS_STOP_ORDER_TEMPLATE`) carries all of these signals on a single row.

Real-world Schwab/TOS Account Order History exports use **multi-line order groups** for working stop orders:

- The **header row** carries the dated `Time Placed`, the ticker, `Status=WORKING` (or `WAIT TRG`), `Side=SELL`, `Pos Effect=TO CLOSE`, `Spread=STOCK`, `Type=STOCK`, `Price=~`, AND the empty-key column (between `Notes` and `Time Placed`) holds the value `MKT` — not `STP`.
- The **continuation row(s)** that follow carry `Time Placed=""` (blank), `Status=""` (blank), `PRICE=<numeric>`, `TIF=STD`, the empty-key column holds `STP`, and `Spread` carries either `RE #<order_id>` (the original order id) or `TRG BY #<trigger_order_id>` (a conditional-order reference) — or blank.

The Bundle B parser sees these header rows as `Type=STOCK` (no STP marker) → skips them entirely. It sees the continuation rows as `Status=""` (no `WORKING` match) → skips those too. Result on the 2026-05-12 operator gate: **5 false-positive `stop_mismatch` discrepancies** (DHC / YOU / VSAT / CVGI / LAR) because the parser returned an empty `stop_orders` dict despite all 5 stops being placed at Schwab matching journal values exactly.

## §2 Observed multi-line patterns

Inspected via `parse_tos_export()` against the 4 sanitized fixtures under `tests/fixtures/tos/schwab-real-world-*.csv`. Verbatim CSV excerpts (header `Notes,Time Placed,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,PRICE,,TIF,Status` — note the empty-key column between `PRICE` and `TIF`):

### §2.A Simple absolute trigger with `RE #` (2026-05-12 CVGI; 2-line group)

```
,,5/11/26 23:09:41,STOCK,SELL,-20,TO CLOSE,CVGI,,,STOCK,~,MKT,GTC,WORKING
,,,RE #1006290692715,,,,,,,,4.36,STP,STD,
```

Continuation row: `Spread="RE #1006290692715"` carries the order id; `PRICE="4.36"` numeric; empty-key column = `STP`; `TIF="STD"`; `Status=""`.

### §2.B Absolute trigger without `RE #` (2026-05-12 LAR; 2-line group)

```
,,5/8/26 06:57:12,STOCK,SELL,-7,TO CLOSE,LAR,,,STOCK,~,MKT,GTC,WORKING
,,,,,,,,,,,7.00,STP,STD,
```

Continuation row: `Spread=""` (no order id); price `7.00`. Per spec §6.2 + dispatch brief §0.5 #5: order_id falls back to `None` — consistent with the single-row format's behavior when the dedicated columns are absent.

### §2.C Conditional `TRG BY` reference + absolute trigger (2026-04-30 DHC; 3-line group)

```
,,4/27/26 06:42:38,STOCK,SELL,-39,TO CLOSE,DHC,,,STOCK,~,MKT,GTC,WORKING
,,,RE #1006137040023,,,,,,,,7.06,STP,STD,
,,,TRG BY #1006137040022,,,,,,,,,,,
```

Two continuation rows: the first carries the `RE #` order id + numeric price `7.06`. The second is an orphan `TRG BY #...` reference (no STP marker, no price) → ignored. Parser stops after the first numeric STP price.

### §2.D Conditional `BASE-X.XX` + absolute trigger (2026-04-30 CC; 3-line group)

```
,,4/30/26 06:18:31,STOCK,SELL,-5,TO CLOSE,CC,,,STOCK,~,MKT,GTC,WORKING
,,,TRG BY #1006193131983,,,,,,,,BASE-6.74,STP,STD,
,,,,,,,,,,,20.51,STP,,
```

Two continuation rows. First has `PRICE="BASE-6.74"` (a conditional REFERENCE base, NOT the actual stop trigger) + `Spread="TRG BY #..."`. Second has `PRICE="20.51"` (the absolute trigger). **Parser MUST prefer the numeric (non-`BASE-`-prefixed) trigger** — otherwise it emits 6.74 which silently misrepresents the actual broker stop. Order-id fallback: the `TRG BY #...` reference is NOT a stop order id, so order_id = `None` here.

### §2.E `WAIT TRG` status (2026-05-08 DHC; 3-line group)

```
,,5/8/26 05:59:29,STOCK,SELL,-39,TO CLOSE,DHC,,,STOCK,~,MKT,GTC,WAIT TRG
,,,RE #1006250248363,,,,,,,,7.49,STP,STD,
,,,TRG BY #1006137040022,,,,,,,,,,,
```

`Status="WAIT TRG"` — the conditional order is placed at the broker but the trigger condition has not yet armed. Operationally still a working stop from the journal's reconciliation perspective — parser MUST include both `WORKING` AND `WAIT TRG`. `CANCELED` + `FILLED` rows remain excluded (historical artifacts).

### §2.F CANCELED rows interleaved (2026-05-12 + 2026-05-08)

Most exports contain CANCELED predecessors of currently-WORKING stops (e.g., 2026-05-12 has CANCELED CVGI / DHC / VSAT / SGML / YOU entries interleaved with WORKING entries; SGML has 5 CANCELED entries). Parser MUST skip these — same-ticker first-WORKING-wins logic + the broadened status filter combined ensure CANCELED rows never overwrite a WORKING entry.

### §2.G Empty section (2026-04-15)

The 2026-04-15 export has only the `Account Order History` section header row and no order rows. Parser MUST handle this gracefully — return an empty dict, no exceptions.

## §3 New parser binding design

The refactor introduces 4 small helpers + reshapes `extract_stop_orders` to a header-then-continuation scan. All in `swing/journal/tos_import.py`. Signatures (private — underscore-prefixed):

```python
def _is_qualifying_stop_header(row: dict) -> bool:
    """Status starts WORKING or WAIT TRG + Side contains SELL +
    Pos Effect contains CLOSE + Spread in ("", "STOCK"). NO check
    on Type/Order Type — that's the caller's job (single-row vs
    multi-line distinction)."""


def _has_stp_marker(row: dict) -> bool:
    """STP/STOP found in Order Type, Type, OR ANY positional unnamed-
    column slot (post-dedupe ``col_<idx>`` keys; Codex R1 Major #1)."""


def _clean_order_id(raw: str) -> str | None:
    """Strip Excel-style ="..." wrapper + leading 'RE #' / 'RE#' prefix.
    Returns None when nothing meaningful remains, when the value starts
    with ``TRG BY`` (trigger-order reference — NOT a stop order id;
    Codex R1 Major #2 + recon doc §2.D), or when the post-strip remainder
    is not a bare alphanumeric token."""


def _try_parse_stp_continuation_price(row: dict) -> float | None:
    """Numeric STP price on a continuation row, or None when row has
    no STP marker, no price, or a BASE-prefixed reference."""
```

`extract_stop_orders` algorithm:

1. Materialize rows to a list (for indexed look-ahead).
2. Walk rows with index `idx`.
3. **Skip continuation rows in the outer scan** — `Time Placed == ""` → continue.
4. **For each header row** (non-empty `Time Placed`):
   - If `_is_qualifying_stop_header(row)` is False → skip.
   - Extract `ticker`; if already in output dict → skip (first-match-wins).
   - **Single-row shape (Bundle B synthetic):** if `_has_stp_marker(row)` is True → the row itself carries the STP trigger. Read `Price` (or `PRICE`) directly, reject `BASE-` prefix, parse, emit `(price, order_id_from_dedicated_columns)`.
   - **Multi-line shape (real-world):** else scan continuation rows from `idx + 1` forward; stop at next dated header (`Time Placed != ""`) OR end of list. For each continuation, try `_try_parse_stp_continuation_price(cont)`; the FIRST numeric (non-BASE-) STP price wins. Order id comes from the matching continuation's `Spread` column (which carries `RE #<id>` or a `TRG BY #...` reference or blank); `_clean_order_id` returns `None` when no `RE #` prefix is present.
5. If no numeric STP trigger is found among continuations (e.g., only a `BASE-` reference with no absolute follow-up) → emit nothing for this header. The downstream `reconcile_tos` then routes this as the "no broker working stop" discrepancy path. **A wrong number is worse than the existing discrepancy emission**; falling back is the conservative safety net.

### §3.A Duplicate / empty CSV-header dedupe (Codex R1 Major #1)

Real-world Schwab/TOS Account Order History headers carry TWO unnamed columns: `Notes,,Time Placed,Spread,...,PRICE,,TIF,Status`. Bare `csv.DictReader` overwrites duplicate keys, so `row[""]` returns only the LAST unnamed column's value. If Schwab adds another blank header (column drift), the STP marker position shifts out of the slot the parser expects and `_has_stp_marker` silently regresses to the pre-T-E.3 false-positive behavior.

`parse_tos_export` now reads the header line via `csv.reader`, renames each duplicate / empty header to `col_<idx>` (preserving the ORIGINAL position), then `dict(zip(fieldnames, row))` constructs row dicts. Downstream `_has_stp_marker` + `_try_parse_stp_continuation_price` consult every `col_*` slot via a new `_iter_unnamed_column_values` helper. This robustness pattern survives arbitrary additional blank-column drift on the Schwab side.

### §3.B `TRG BY` rejection in `_clean_order_id` (Codex R1 Major #2)

Per §2.D the `TRG BY #...` reference identifies the TRIGGER order, NOT the stop's own order id. Pre-fix `_clean_order_id` only stripped `RE #` / `RE#` / `=` / `"` wrappers — a continuation whose `Spread` carried `TRG BY #999` AND a numeric STP price (no `BASE-` prefix) would have leaked the literal `"TRG BY #999"` as the stop's `order_id`. Post-fix the helper rejects `TRG BY` outright + requires the post-strip remainder be a bare alphanumeric token (digits/letters/`-`/`_`); anything else returns `None`. The §2.D 4/30 CC case (winning continuation has empty Spread) is unaffected at the price-extraction site but the existing test now also asserts `cc_order_id is None`.

## §4 Spec §6.2 supersession note

Per V2.1 §VII.F source-of-truth correction protocol: spec `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` §6.2's match criteria table reading "Order Type/Type contains 'STP' or 'STOP'" assumed a single-row export shape. Bundle E T-E.3 widens the parser to handle the real-world multi-line group shape AND broadens `Status` to include `WAIT TRG`. This recon doc carries the binding design until the next spec amendment cycle.

The single-row criteria still apply when the row qualifies on its own (Bundle B synthetic format + any future flat export); the multi-line shape adds the header-vs-continuation distinction described in §3. Backwards compatibility with Bundle B's `test_stop_mismatch_*` discriminating tests is preserved (single-row pathway).

## §5 Fixture corpus

Sanitized real-world Schwab/TOS exports under `tests/fixtures/tos/`:

| Fixture | Period | Account Order History rows | Notable patterns |
|---|---|---|---|
| `schwab-real-world-2026-04-15.csv` | 3/16/26 – 4/14/26 | 0 | Empty section (no orders) |
| `schwab-real-world-2026-04-30.csv` | 4/29/26 – 4/29/26 | 7 | CC `BASE-` + 20.51 absolute (§2.D); DHC `RE #` + orphan TRG BY (§2.C) |
| `schwab-real-world-2026-05-08.csv` | 5/2/26 – 5/8/26 | 30 | LAR no-`RE#` (§2.B); DHC + VSAT `WAIT TRG` (§2.E); 5 SGML CANCELED (§2.F) |
| `schwab-real-world-2026-05-12.csv` | 5/5/26 – 5/11/26 | 41 | 5 working stops covering §2.A/§2.B/§2.F (CVGI/DHC/VSAT/LAR/YOU + CANCELED noise) |

All 4 exports have account number `27097300SCHW` replaced with the literal `<account>` in the `Account Statement for ...` header line. No other PII observed in the first 30 lines of any export.

## §6 Test coverage

`tests/journal/test_tos_import_stop_extractor_real_world.py` — 9 discriminating tests:

| Test | Asserts |
|---|---|
| `test_extract_stop_orders_2026_05_12_five_working_stops` | Exact dict shape with 5 entries including LAR's `order_id=None` and YOU's `order_id='1006250248383'` |
| `test_extract_stop_orders_2026_04_15_empty_section` | Empty section → `{}` (no exceptions) |
| `test_extract_stop_orders_2026_04_30_base_prefix_skipped` | CC at 20.51 NOT 6.74 AND `cc_order_id is None` (Codex R1 Major #2 contract); DHC at 7.06 with `RE #` order id |
| `test_extract_stop_orders_2026_05_08_wait_trg_and_working` | Exact dict shape with LAR (WORKING) + DHC/VSAT (WAIT TRG) + CVGI/YOU (WORKING); CANCELED SGML absent |
| `test_extract_stop_orders_synthetic_single_row_format` | Bundle B synthetic single-row format still parses (backwards-compat) |
| `test_extract_stop_orders_extra_unnamed_column_drift` | Codex R1 Major #1 regression — Schwab-drift simulation with an EXTRA blank header column STILL extracts the STP price via the `col_<idx>` rename + multi-slot marker scan |
| `test_extract_stop_orders_trg_by_only_in_continuation_returns_none_order_id` | Codex R1 Major #2 regression — continuation row carrying ONLY `TRG BY #999` (no `RE #`) AND a numeric STP price emits the price but `order_id=None`; pre-fix the order_id would have leaked as `"TRG BY #999"` |
| `test_reconcile_2026_05_12_zero_stop_mismatch_when_stops_match` | Full reconciliation against fixture-DB journal seeded with 5 open trades matching the broker stops → ZERO `stop_mismatch` emits (pre-fix this emitted 5 false positives) |
| `test_reconcile_2026_04_30_cc_uses_absolute_trigger_not_base` | Full reconciliation against fixture-DB journal seeded with CC at $20.51 → ZERO `stop_mismatch` emits for CC (parser extracted 20.51 not 6.74) |

Existing Bundle B `test_stop_mismatch_*` family (in `tests/journal/test_tos_import_reconciliation_extension.py` §5) continues to pass — synthetic single-row pathway preserved.
