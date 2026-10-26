"""D84 T9 step 3 -- the briefing expansion renders the risk row and the
RISK FLAG marker (RD (2), CHARC P1 (c)).

The briefing is a pipeline-rendered FILE with no route, so the pin is a RENDER
assertion on the production renderer (`render_briefing_html`) over the
production view-model builder (`build_briefing_view_model`), never TestClient.
"""
from __future__ import annotations

import html as _html
import re

from swing.data.models import Candidate, CriterionResult, DailyRecommendation
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.html_renderer import render_briefing_html


def _candidate(ticker: str, risk: str | None) -> Candidate:
    crit = [CriterionResult("TT1_above_150_200", "trend_template", "pass"),
            CriterionResult("adr", "vcp", "pass")]
    if risk == "fail":
        crit.append(CriterionResult(
            "risk_feasibility", "risk", "fail", "0 sh, $0.00 risk",
            ">= 1 share fits in 0.5% of equity ($37.50)"))
    elif risk == "pass":
        crit.append(CriterionResult(
            "risk_feasibility", "risk", "pass", "1 sh, $4.00 risk",
            ">= 1 share fits in 0.5% of equity ($37.50)"))
    return Candidate(
        ticker=ticker, bucket="aplus", close=98.46, pivot=104.0,
        initial_stop=29.81, adr_pct=6.0, tight_streak=None, pullback_pct=None,
        prior_trend_pct=None, rs_rank=None, rs_return_12w_vs_spy=None,
        rs_method="universe", pattern_tag=None, notes=None,
        criteria=tuple(crit),
    )


def _rec(ticker: str) -> DailyRecommendation:
    return DailyRecommendation(
        id=None, evaluation_run_id=1, data_asof_date="2026-10-22",
        action_session_date="2026-10-23", ticker=ticker,
        recommendation="today_decision", action_text="seeded",
        entry_target=104.0, stop_target=29.81, shares=0, risk_dollars=0.0,
        risk_pct=0.0, rationale="A+ setup")


def _expansion_html(out: str, ticker: str) -> str:
    """One ticker's A+ Detail block: from its heading to the next block."""
    m = re.search(rf"<h3>{ticker}\b", out)
    assert m, f"no expansion for {ticker}"
    nxt = out.find('<div style="margin-bottom: 1.5em;">', m.start())
    return out[m.start():nxt if nxt != -1 else len(out)]


def test_the_briefing_expansion_renders_the_risk_row_and_the_marker():
    """R-E3(2)a. The KOD-shaped risk-fail A+ renders `RISK FLAG` and the risk
    grid row `risk_feasibility` FAIL with its persisted value; the risk-pass
    candidate renders its risk row and NO marker; a candidate with NO risk row
    renders no marker (E-d, the briefing consumer)."""
    inputs = BriefingInputs(
        action_session_date="2026-10-23", data_asof_date="2026-10-22",
        generated_at="2026-10-22T17:45:00", weather=None,
        weather_is_stale=False, equity=1200.0, open_count=0, soft_warn=4,
        hard_cap=6, last_pipeline_ts="2026-10-22T17:45:00",
        pipeline_is_stale=False, current_session_match=True,
        recommendations=[_rec("KOD"), _rec("PAS"), _rec("EMP")],
        open_trades=[],
        candidates_by_ticker={"KOD": _candidate("KOD", "fail"),
                              "PAS": _candidate("PAS", "pass"),
                              "EMP": _candidate("EMP", None)},
    )
    out = _html.unescape(render_briefing_html(build_briefing_view_model(inputs)))
    kod = _expansion_html(out, "KOD")
    assert "RISK FLAG" in kod
    assert re.search(
        r"<td>risk_feasibility</td><td class=\"fail\">FAIL</td>"
        r"<td>0 sh, \$0\.00 risk</td>", kod)
    pas = _expansion_html(out, "PAS")
    assert "risk_feasibility" in pas and "RISK FLAG" not in pas
    emp = _expansion_html(out, "EMP")
    assert "RISK FLAG" not in emp
