"""22-F T-D5 (web half + the closure) -- `NoActivePolicyError` CONVERTED
(CHARC F-F4 (3); STOP-2 items 1-3 + the retype; STOP-3's discriminators).

CLOSURE (static).  Every call site in `swing/` of the policy readers and the
writer -- `get_active_policy`, the delegates `read_live_policy` /
`read_at_trade_time_policy` (`swing.metrics.policy`) and `read_active_policy`
(`swing.trades.risk_policy`), and `supersede_active_policy` (STOP-2 item 4:
"enumerates supersede_active_policy's callers beside get_active_policy's") --
sits in the BODY of a `Try` with a handler NAMING `NoActivePolicyError`, or is
in `EXEMPT` with a reason naming its converting boundary.  A delegate's own
call is exempt BECAUSE its callers are enumerated here too.  A stale `EXEMPT`
entry (matching no uncovered site) FAILS.  Keys are (path, enclosing
function, stripped call line) -- never a line number.

BEHAVIOURAL.  D5-a..g: each `/metrics/*` page that reaches a policy read on
the seeded DB (measured: 7 of the 10 GET routes; `/metrics/hypothesis-progress`
reaches `read_at_trade_time_policy` only through an in-cohort trade with a NULL
/ orphan stamp, which the seeded DB does not carry -- the handler is
type-generic).  PRE-FIX 500, POST-FIX 503 with the ruled text, both trees.
D5-k: the R45 precedence pin.  The two web CASCADE writers (STOP-3): 204 as
today, the override observed on a fresh read, the ordered cause-specific log
record, zero active rows; CONTROL: other causes keep today's hint.
"""
from __future__ import annotations

import ast
import html
import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app
from tests._22f_ast import (
    REPO_ROOT,
    enclosing_function,
    enclosing_try_handler_names,
    iter_sources,
    parent_map,
)
from tests.cli.test_22f_no_active_policy_cli import (
    RULED_TEXT,
    assert_names_no_swing_command,
)
from tests.web.test_config_route_risk_policy_cascade import (  # noqa: F401
    _form_payload,
    _post_form,
    app_client,
)

_NAMES = frozenset({"get_active_policy", "read_live_policy",
                    "read_at_trade_time_policy", "read_at_review_time_policy",
                    "read_active_policy", "supersede_active_policy"})
_WEB_503 = ("web: the app-level NoActivePolicyError handler (503, "
            "`swing/web/app.py`); reached only from the /metrics routes -- "
            "no CLI/pipeline module imports it (grep of importers outside "
            "swing/metrics + swing/web)")
_DELEGATE = "delegate: its own callers are enumerated by this closure"

EXEMPT: dict[tuple[str, str, str], str] = {
    ("metrics/policy.py", "read_live_policy",
     "return get_active_policy(conn)"): _DELEGATE,
    ("metrics/policy.py", "read_at_trade_time_policy",
     "return (read_live_policy(conn), True)"): _DELEGATE,
    ("metrics/policy.py", "read_at_review_time_policy",
     "return read_at_trade_time_policy(conn, policy_id_stamp=policy_id_stamp)"):
        _DELEGATE + " (measured: none in swing/)",
    ("trades/risk_policy.py", "read_active_policy",
     "return repo.get_active_policy(conn)"): _DELEGATE,
    ("metrics/capital.py", "compute_capital_friction",
     "live_policy = read_live_policy(conn)"): _WEB_503 + " (D5 capital-friction)",
    ("metrics/maturity.py", "compute_maturity_stage",
     "live_policy = read_live_policy(conn)"): _WEB_503 + " (D5 maturity-stage)",
    ("metrics/process.py", "compute_trade_process_metrics",
     "live_policy = read_live_policy(conn)"): _WEB_503 + " (D5 trade-process)",
    ("metrics/process.py", "_prepare_trade_inputs",
     "at_policy, is_legacy = read_at_trade_time_policy("): _WEB_503,
    ("metrics/process_grade_trend.py", "compute_process_grade_trend",
     "policy = read_live_policy(conn)"): _WEB_503
    + " (D5 process-grade-trend)",
    ("metrics/tier.py", "compute_tier_comparison",
     "live_policy = read_live_policy(conn)"): _WEB_503 + " (D5 tier-comparison)",
    ("metrics/tier.py", "_per_trade_realized_R",
     "at_policy, is_legacy = read_at_trade_time_policy("): _WEB_503,
    ("web/view_models/metrics/hypothesis_progress_card.py",
     "_per_trade_net_pnl_and_at_trade_time_policy",
     "at_policy, is_legacy = read_at_trade_time_policy(conn, "
     "policy_id_stamp=stamp)"): _WEB_503 + " (/metrics/hypothesis-progress)",
    ("web/view_models/patterns/outcomes_card.py", "build_pattern_outcomes_vm",
     "policy = get_active_policy(conn)"): _WEB_503 + " (D5 pattern-outcomes)",
    ("web/view_models/latches.py", "_sizing_inputs",
     "policy_id = get_active_policy(conn).policy_id"):
        "web: CONTAINED by the enclosing `except Exception` (A6; the id is "
        "provenance only) -- logged, `risk_policy_id=None`, never the app "
        "handler",
    ("trades/risk_policy.py", "ratify_seed_from_cfg_on_v17_landing",
     "return supersede_active_policy("):
        "migration-only (the v17 landing); the function's own "
        "`get_active_policy` read returns None first when no row is active, "
        "so this supersede is unreachable in that state",
}


def _sites(root: Path):
    for rel, tree, lines in iter_sources(root, ("**/*.py",)):
        parents = parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = (f.id if isinstance(f, ast.Name)
                    else f.attr if isinstance(f, ast.Attribute) else None)
            if name not in _NAMES:
                continue
            yield ((rel, enclosing_function(node, parents),
                    lines[node.lineno - 1].strip()),
                   enclosing_try_handler_names(node, parents))


def _violations(root: Path) -> tuple[list, list, int]:
    uncovered, matched, n = [], set(), 0
    for key, handled in _sites(root):
        n += 1
        if "NoActivePolicyError" in handled:
            continue
        if key in EXEMPT:
            matched.add(key)
            continue
        uncovered.append(key)
    return uncovered, sorted(set(EXEMPT) - matched), n


def test_every_policy_read_and_supersede_site_is_converted_or_exempt():
    uncovered, stale, _n = _violations(REPO_ROOT / "swing")
    assert uncovered == [], uncovered
    assert stale == [], f"stale EXEMPT entries (match no site): {stale}"


def test_the_walker_is_not_vacuous():
    """The six writer roots and the three CLI read roots are enumerated."""
    keys = {k for k, _h in _sites(REPO_ROOT / "swing")}
    fns = {(k[0], k[1]) for k in keys}
    assert {("cli_config.py", "config_set"), ("cli_config.py", "config_reset"),
            ("cli_config.py", "policy_set"),
            ("cli_config.py", "policy_import_from_toml"),
            ("cli_config.py", "policy_show"),
            ("cli.py", "discrepancy_resolve_ambiguity_cmd"),
            ("cli.py", "discrepancy_override_correction_cmd"),
            ("web/routes/config.py", "config_save"),
            ("web/routes/config.py", "config_reset")} <= fns
    assert len(keys) >= 28, len(keys)


# ---------------------------------------------------------------------------
# D5-a..g -- the /metrics pages
# ---------------------------------------------------------------------------

_PAGES = ("/metrics/trade-process", "/metrics/tier-comparison",
          "/metrics/deviation-outcome", "/metrics/capital-friction",
          "/metrics/maturity-stage", "/metrics/process-grade-trend",
          "/metrics/pattern-outcomes")


def _zero(db: Path) -> None:
    c = sqlite3.connect(str(db))
    try:
        c.execute("UPDATE risk_policy SET is_active = 0")
        c.commit()
    finally:
        c.close()


def _active(db: Path) -> int:
    c = sqlite3.connect(str(db))
    try:
        return c.execute("SELECT COALESCE(SUM(is_active), 0) "
                         "FROM risk_policy").fetchone()[0]
    finally:
        c.close()


@pytest.mark.parametrize("hx", [False, True], ids=["page", "htmx"])
@pytest.mark.parametrize("path", _PAGES)
def test_D5_metrics_page_no_active_policy_is_503_with_ruled_text(
        seeded_db, path, hx):
    cfg, cfg_path = seeded_db
    with TestClient(create_app(cfg, cfg_path),
                    raise_server_exceptions=False) as tc:
        _zero(cfg.paths.db_path)
        resp = tc.get(path, headers={"HX-Request": "true"} if hx else {})
    assert resp.status_code == 503, (resp.status_code, resp.text[:300])
    body = html.unescape(resp.text)
    assert RULED_TEXT in body
    assert_names_no_swing_command(body)
    assert ("<html" in resp.text.lower()) is (not hx)
    assert _active(cfg.paths.db_path) == 0


def test_D5_control_active_policy_pages_are_200(seeded_db):
    cfg, cfg_path = seeded_db
    with TestClient(create_app(cfg, cfg_path)) as tc:
        for path in _PAGES:
            assert tc.get(path).status_code == 200, path


# ---------------------------------------------------------------------------
# the web cascade writers + D5-k
# ---------------------------------------------------------------------------

def _override(home: Path) -> str:
    uc = home / "swing-data" / "user-config.toml"
    return uc.read_text(encoding="utf-8") if uc.exists() else ""


def _cascade_record(caplog) -> str:
    msgs = [r.getMessage() for r in caplog.records
            if r.name == "swing.web.routes.config"]
    assert len(msgs) == 1, msgs
    return msgs[0]


def _assert_ordered(msg: str, verb: str) -> None:
    a = msg.index(f"override {verb}")
    b = msg.index("the risk_policy cascade did NOT fire because no policy "
                  "row is active")
    c = msg.index(RULED_TEXT)
    assert a < b < c, msg
    assert_names_no_swing_command(msg)


def test_D5k_post_config_no_active_policy_keeps_route_response(
        app_client, tmp_path, caplog):
    """D5-k PRECEDENCE PIN (R45) + the STOP-3 cascade discriminator.  The
    route's own response (recorded at G1: 204, `HX-Redirect:
    /config?saved=1`, empty body) stands -- not 503, not the app handler's
    fragment.  PRE-FIX the contained log names `swing config policy
    import-from-toml` (D35); POST-FIX the ordered cause-specific record."""
    client, cfg, _cfg_path = app_client
    _zero(cfg.paths.db_path)
    payload = _form_payload(cfg, **{"account.risk_equity_floor": "8500.0"})
    payload["force"] = "true"
    with caplog.at_level(logging.INFO, logger="swing.web.routes.config"):
        resp = _post_form(client, payload)
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect") == "/config?saved=1"
    assert "banner-degraded" not in resp.text
    assert "risk_equity_floor = 8500.0" in _override(tmp_path / "home")
    _assert_ordered(_cascade_record(caplog), "written")
    assert _active(cfg.paths.db_path) == 0


def test_D5k_twin_post_reset_no_active_policy_keeps_route_response(
        app_client, tmp_path, caplog):
    client, cfg, _cfg_path = app_client
    payload = _form_payload(cfg, **{"account.risk_equity_floor": "8500.0"})
    payload["force"] = "true"
    assert _post_form(client, payload).status_code == 204
    _zero(cfg.paths.db_path)
    with caplog.at_level(logging.INFO, logger="swing.web.routes.config"):
        resp = client.post("/config/reset/account.risk_equity_floor",
                           headers={"HX-Request": "true"})
    assert resp.status_code == 204
    assert resp.headers.get("HX-Redirect") == "/config?saved=1"
    assert "risk_equity_floor" not in _override(tmp_path / "home")
    _assert_ordered(_cascade_record(caplog), "deleted")
    assert _active(cfg.paths.db_path) == 0


def test_web_cascade_other_cause_keeps_todays_hint(app_client, monkeypatch,
                                                   caplog):
    """CONTROL: another cascade failure cause keeps today's text.  The route
    imports `supersede_active_policy` function-locally, so the patched home
    module attribute is what it resolves per call."""
    from tests._22f_proxies import raising
    client, cfg, _cfg_path = app_client
    planted = raising(ValueError("planted other cause"))
    monkeypatch.setattr("swing.trades.risk_policy.supersede_active_policy",
                        planted)
    payload = _form_payload(cfg, **{"account.risk_equity_floor": "8500.0"})
    payload["force"] = "true"
    with caplog.at_level(logging.INFO, logger="swing.web.routes.config"):
        resp = _post_form(client, payload)
    assert planted.calls >= 1  # did-it-fire
    assert resp.status_code == 204
    msg = _cascade_record(caplog)
    assert msg.startswith("Phase 9 T-A.5: cfg-cascade to risk_policy failed; "
                          "overrides written successfully but policy NOT "
                          "updated.")
    assert RULED_TEXT not in msg
