"""Exporter writes briefing.html (+ briefing.md transition) + per-ticker chart copies."""
from __future__ import annotations

from pathlib import Path

from swing.rendering.exporter import export_briefing, ExportResult
from swing.rendering.view_models import (
    AccountTileVM, BriefingViewModel, PipelineTileVM, StatusStripVM,
    TodaysDecisionVM, WeatherTileVM,
)


def _vm(*, with_inline_chart: bool = False) -> BriefingViewModel:
    chart = "data:image/png;base64,iVBORw0KGgo=" if with_inline_chart else None
    return BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="r", sizing_implication="OK"),
            account=AccountTileVM(equity=1284.50, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="2026-04-15T21:49:00",
                                    is_stale=False, current_session_match=True),
        ),
        todays_decisions=[
            TodaysDecisionVM(ticker="NVDA", action_text="Buy-stop $850 \u00b7 2 sh",
                             entry_target=850.0, stop_target=820.0, shares=2,
                             risk_dollars=60.0, risk_pct=4.7, rationale="r",
                             tt_score="7/8", vcp_score="10/10", chart_b64=chart),
        ],
        open_positions=[], watchlist=[], expansions=[],
    )


def test_writes_html_and_md(tmp_path: Path):
    out = tmp_path / "exports" / "2026-04-16"
    result = export_briefing(
        vm=_vm(), out_dir=out,
        chart_files={"NVDA": tmp_path / "missing.png"},
        size_cap_kb=500, retain_markdown_sibling=True,
    )
    assert (out / "briefing.html").exists()
    assert (out / "briefing.md").exists()
    assert result.html_size_kb < 500


def test_size_cap_delinks_charts(tmp_path: Path):
    big_b64 = "data:image/png;base64," + ("A" * 800_000)
    out = tmp_path / "exports" / "2026-04-16"
    vm = BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="t",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="r", sizing_implication="OK"),
            account=AccountTileVM(equity=1.0, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="t", is_stale=False, current_session_match=True),
        ),
        todays_decisions=[TodaysDecisionVM(
            ticker="X", action_text="t", entry_target=1.0, stop_target=1.0,
            shares=1, risk_dollars=1.0, risk_pct=1.0, rationale="r",
            tt_score="", vcp_score="", chart_b64=big_b64)],
        open_positions=[], watchlist=[], expansions=[],
    )
    result = export_briefing(
        vm=vm, out_dir=out, chart_files={},
        size_cap_kb=500, retain_markdown_sibling=False,
    )
    html = (out / "briefing.html").read_text(encoding="utf-8")
    assert big_b64 not in html
    assert result.charts_delinked is True
    assert 'href="charts/X.png"' in html or "charts/X.png" in html


def test_delinked_href_points_to_real_file_on_disk(tmp_path: Path):
    """Adversarial review Round 1 Major: a link without a backing file was a bug.
    When size cap triggers delinking and caller provided inline b64 (no chart_files
    entry), the exporter must extract the b64 to a real PNG and link to it."""
    import base64
    # Small but valid PNG bytes — base64-encoded
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 100
    b64 = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    # Pad with a big buffer so total HTML exceeds 500 KB
    padding = "X" * 800_000
    out = tmp_path / "exports" / "2026-04-16"
    vm = BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="t",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="r" + padding,
                                  sizing_implication="OK"),
            account=AccountTileVM(equity=1.0, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="t", is_stale=False, current_session_match=True),
        ),
        todays_decisions=[TodaysDecisionVM(
            ticker="NVDA", action_text="t", entry_target=1.0, stop_target=1.0,
            shares=1, risk_dollars=1.0, risk_pct=1.0, rationale="r",
            tt_score="", vcp_score="", chart_b64=b64)],
        open_positions=[], watchlist=[], expansions=[],
    )
    result = export_briefing(
        vm=vm, out_dir=out, chart_files={},  # no source file provided
        size_cap_kb=500, retain_markdown_sibling=False,
    )
    assert result.charts_delinked is True
    # PNG extracted to disk from the inline b64
    extracted = out / "charts" / "NVDA.png"
    assert extracted.exists()
    assert extracted.read_bytes() == png_bytes
    # HTML references the extracted file (no broken link)
    html = (out / "briefing.html").read_text(encoding="utf-8")
    assert 'href="charts/NVDA.png"' in html


def test_delink_drops_link_when_b64_malformed_and_no_file(tmp_path: Path):
    """If inline b64 can't be decoded AND there's no source file, delink emits
    NEITHER inline image NOR broken link — rather than a 404 href."""
    malformed = "not-a-data-url " + ("Q" * 800_000)  # large but invalid data URL
    out = tmp_path / "exports" / "2026-04-16"
    vm = BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="t",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="r",
                                  sizing_implication="OK"),
            account=AccountTileVM(equity=1.0, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="t", is_stale=False, current_session_match=True),
        ),
        todays_decisions=[TodaysDecisionVM(
            ticker="BAD", action_text="t", entry_target=1.0, stop_target=1.0,
            shares=1, risk_dollars=1.0, risk_pct=1.0, rationale="r",
            tt_score="", vcp_score="", chart_b64=malformed)],
        open_positions=[], watchlist=[], expansions=[],
    )
    result = export_briefing(
        vm=vm, out_dir=out, chart_files={},
        size_cap_kb=500, retain_markdown_sibling=False,
    )
    assert result.charts_delinked is True
    html = (out / "briefing.html").read_text(encoding="utf-8")
    # No broken link
    assert 'href="charts/BAD.png"' not in html
    assert malformed not in html
