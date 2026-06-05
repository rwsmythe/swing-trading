# tests/web/test_topbar_cross_vm_consistency.py
"""Issue #5: at a single frozen `now`, same-kind base-layout pages agree on the
topbar session_date, and the naive date.today()/now().date() family is gone.
NOW is a post-close evening on a session day so forward != backward."""
import ast
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.config import load
from swing.data.db import ensure_schema
from swing.evaluation.dates import (
    PageKind,
    action_session_for_run,
    last_completed_session,
)

# Import every base-layout VM from its DEFINING module (the home modules verified
# on this checkout). The COMPLETENESS check below is pure-AST and import-
# independent; these imports only make PAGE_KIND readable + force module load.
from swing.web.view_models.account import AccountSnapshotFormVM
from swing.web.view_models.config import ConfigPageVM, build_config_vm
from swing.web.view_models.dashboard import DashboardVM
from swing.web.view_models.error import PageErrorVM
from swing.web.view_models.journal import JournalVM, TradeDrilldownVM
from swing.web.view_models.metrics.capital_friction import (
    CapitalFrictionVM,
    build_capital_friction_vm,
)
from swing.web.view_models.metrics.deviation_outcome import DeviationOutcomeVM
from swing.web.view_models.metrics.hypothesis_progress_card import HypothesisProgressCardVM
from swing.web.view_models.metrics.identification_funnel import (
    IdentificationFunnelVM,
    build_identification_funnel_vm,
)
from swing.web.view_models.metrics.index import MetricsIndexVM
from swing.web.view_models.metrics.maturity_stage import (
    MaturityStageVM,
    build_maturity_stage_vm,
)
from swing.web.view_models.metrics.process_grade_trend import ProcessGradeTrendVM
from swing.web.view_models.metrics.shared import BaseLayoutVM  # noqa: F401
from swing.web.view_models.metrics.tier_comparison import TierComparisonVM
from swing.web.view_models.metrics.trade_process_card import TradeProcessCardVM
from swing.web.view_models.patterns.exemplars import PatternExemplarsVM
from swing.web.view_models.patterns.outcomes_card import PatternOutcomesVM
from swing.web.view_models.patterns.queue import PatternQueueVM
from swing.web.view_models.patterns.review_form import PatternReviewFormVM
from swing.web.view_models.pipeline import PipelineVM, build_pipeline
from swing.web.view_models.reconcile import (
    ReconcileDiscrepancyErrorVM,
    ReconcileDiscrepancyResolveVM,
)
from swing.web.view_models.schwab import (
    SchwabSetupErrorVM,
    SchwabSetupVM,
    SchwabStatusVM,
)
from swing.web.view_models.trades import (
    CadenceCompleteVM,
    ReviewsPendingVM,
    ReviewVM,
    TradeDetailVM,
)
from swing.web.view_models.watchlist import WatchlistVM, build_watchlist

NOW = datetime(2026, 6, 4, 20, 0)  # post-close ET evening on a session day
WEB = Path(__file__).resolve().parents[2] / "swing" / "web"
# The abstract shared base carries the session_date field but is NOT a page;
# exclude it from discovery.
_DISCOVERY_EXCLUDE = {"BaseLayoutVM"}

# The AUTHORITATIVE manifest -- every base-layout VM + its declared PageKind.
# NO ellipsis: the completeness test below mechanically (AST) discovers every
# base-layout VM class in swing/web and asserts this manifest equals that set,
# so an incomplete manifest FAILS the suite (it cannot ship silently).
MANIFEST = {
    DashboardVM: PageKind.FORWARD_PLANNING,
    WatchlistVM: PageKind.FORWARD_PLANNING,
    JournalVM: PageKind.HISTORY_ANALYSIS,
    ConfigPageVM: PageKind.HISTORY_ANALYSIS,
    PipelineVM: PageKind.HISTORY_ANALYSIS,
    PageErrorVM: PageKind.HISTORY_ANALYSIS,
    ReviewVM: PageKind.HISTORY_ANALYSIS,
    ReviewsPendingVM: PageKind.HISTORY_ANALYSIS,
    CadenceCompleteVM: PageKind.HISTORY_ANALYSIS,
    TradeDetailVM: PageKind.HISTORY_ANALYSIS,
    TradeDrilldownVM: PageKind.HISTORY_ANALYSIS,
    ReconcileDiscrepancyResolveVM: PageKind.HISTORY_ANALYSIS,
    ReconcileDiscrepancyErrorVM: PageKind.HISTORY_ANALYSIS,
    SchwabSetupVM: PageKind.HISTORY_ANALYSIS,
    SchwabStatusVM: PageKind.HISTORY_ANALYSIS,
    SchwabSetupErrorVM: PageKind.HISTORY_ANALYSIS,
    AccountSnapshotFormVM: PageKind.HISTORY_ANALYSIS,
    MetricsIndexVM: PageKind.HISTORY_ANALYSIS,
    CapitalFrictionVM: PageKind.HISTORY_ANALYSIS,
    DeviationOutcomeVM: PageKind.HISTORY_ANALYSIS,
    HypothesisProgressCardVM: PageKind.HISTORY_ANALYSIS,
    IdentificationFunnelVM: PageKind.HISTORY_ANALYSIS,
    MaturityStageVM: PageKind.HISTORY_ANALYSIS,
    ProcessGradeTrendVM: PageKind.HISTORY_ANALYSIS,
    TierComparisonVM: PageKind.HISTORY_ANALYSIS,
    TradeProcessCardVM: PageKind.HISTORY_ANALYSIS,
    PatternExemplarsVM: PageKind.HISTORY_ANALYSIS,
    PatternOutcomesVM: PageKind.HISTORY_ANALYSIS,
    PatternQueueVM: PageKind.HISTORY_ANALYSIS,
    PatternReviewFormVM: PageKind.HISTORY_ANALYSIS,
}


def _discover_base_layout_vm_names() -> set[str]:
    """Pure-AST discovery (no imports) of EVERY base-layout VM class across
    swing/web -- BOTH populations: (a) classes whose bases include
    BaseLayoutVM (the metrics + account family); (b) classes that DECLARE a
    `session_date` annotated field (the standalone family). Import-independent,
    so an unimported module cannot hide a class."""
    names: set[str] = set()
    for path in WEB.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {b.id for b in node.bases if isinstance(b, ast.Name)} | \
                {b.attr for b in node.bases if isinstance(b, ast.Attribute)}
            declares_session_date = any(
                isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
                and s.target.id == "session_date" for s in node.body)
            if node.name in _DISCOVERY_EXCLUDE:
                continue  # the abstract shared base, not a page
            if "BaseLayoutVM" in base_names or declares_session_date:
                names.add(node.name)
    return names


def test_manifest_is_complete_and_exact():
    """Mechanical authority: the manifest must equal the AST-discovered set of
    base-layout VM classes -- no missing (an evading page) and no stale extras."""
    discovered = _discover_base_layout_vm_names()
    manifest_names = {c.__name__ for c in MANIFEST}
    assert discovered == manifest_names, (
        f"missing from MANIFEST: {discovered - manifest_names}; "
        f"stale in MANIFEST: {manifest_names - discovered}")


def test_every_vm_declares_matching_page_kind():
    for cls, kind in MANIFEST.items():
        assert getattr(cls, "PAGE_KIND", None) is kind, \
            f"{cls.__name__} PAGE_KIND != {kind}"


class _FakeCache:
    """Minimal PriceCache stand-in for build_watchlist on an empty universe."""

    def get_many(self, *args, **kwargs):
        return {}

    def degraded_until(self):
        return None

    def is_degraded(self):
        return False


# Per-VM builders wired to the project's real builders. Each value is a
# one-arg callable(cfg) returning a constructed VM at the monkeypatched `now`.
# This registry is the BEHAVIORAL proof: it catches a wrong PageKind ARGUMENT
# at a callsite (a metrics builder mistakenly calling
# topbar_session_date(PageKind.FORWARD_PLANNING, ...) would render `forward`,
# failing the assertion below even though its PAGE_KIND attr says backward).
# Covers both families + >=1 metrics VM + >=1 standalone VM.
_REPRESENTATIVES: dict = {
    WatchlistVM: lambda cfg: build_watchlist(
        cfg=cfg, cache=_FakeCache(), executor=MagicMock()),     # forward
    PipelineVM: lambda cfg: build_pipeline(cfg=cfg),            # backward (non-metrics)
    ConfigPageVM: lambda cfg: build_config_vm(cfg),            # backward (non-metrics)
    CapitalFrictionVM: lambda cfg: build_capital_friction_vm(cfg=cfg),     # backward metrics
    MaturityStageVM: lambda cfg: build_maturity_stage_vm(cfg=cfg),         # backward metrics
    IdentificationFunnelVM: lambda cfg: build_identification_funnel_vm(cfg=cfg),  # backward metrics
}


class _FrozenNow(datetime):
    """A datetime subclass whose .now() is pinned to NOW; preserves every other
    datetime behavior (construction, arithmetic) so patching it into a module is
    safe."""
    @classmethod
    def now(cls, tz=None):
        return NOW


def _freeze_web_clock(monkeypatch):
    """Deterministically freeze EVERY swing.web callsite's clock: VMs call
    `datetime.now()` in their OWN module then pass it into
    topbar_session_date(now_local), so patching swing.evaluation.dates does
    nothing. Patch each already-imported swing.web module's `datetime` symbol
    (the `from datetime import datetime` name) to _FrozenNow."""
    import sys
    for name, mod in list(sys.modules.items()):
        if not name.startswith("swing.web"):
            continue
        if getattr(mod, "datetime", None) is datetime:
            monkeypatch.setattr(mod, "datetime", _FrozenNow)


def test_representatives_registry_is_non_vacuous():
    """Guard: the behavioral test cannot pass with an empty/one-sided registry."""
    kinds = {MANIFEST[c] for c in _REPRESENTATIVES}
    assert len(_REPRESENTATIVES) >= 6, "wire at least 6 representative builders"
    assert kinds == {PageKind.FORWARD_PLANNING, PageKind.HISTORY_ANALYSIS}, \
        "representatives must cover BOTH PageKinds"
    metrics = {MetricsIndexVM, CapitalFrictionVM, DeviationOutcomeVM,
               HypothesisProgressCardVM, IdentificationFunnelVM, MaturityStageVM,
               ProcessGradeTrendVM, TierComparisonVM, TradeProcessCardVM}
    assert _REPRESENTATIVES.keys() & metrics, "include >=1 metrics VM"
    assert _REPRESENTATIVES.keys() - metrics, "include >=1 non-metrics VM"


@pytest.fixture
def rep_cfg(tmp_path):
    """A migrated, empty-DB cfg the representative builders can read."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    return cfg


@pytest.mark.parametrize("cls", list(_REPRESENTATIVES))
def test_representative_renders_its_declared_anchor(cls, monkeypatch, rep_cfg):
    """Build the VM at frozen NOW; its rendered session_date MUST equal the
    anchor for its DECLARED kind and DIFFER from the other kind -- catching a
    wrong PageKind argument at the construction callsite."""
    forward = action_session_for_run(NOW).isoformat()
    backward = last_completed_session(NOW).isoformat()
    assert forward != backward
    _freeze_web_clock(monkeypatch)   # freezes every swing.web callsite's now()
    vm = _REPRESENTATIVES[cls](rep_cfg)
    expected = forward if MANIFEST[cls] is PageKind.FORWARD_PLANNING else backward
    wrong = backward if MANIFEST[cls] is PageKind.FORWARD_PLANNING else forward
    assert vm.session_date in (forward, backward), \
        f"{cls.__name__} read an unfrozen clock"
    assert vm.session_date == expected, f"{cls.__name__} rendered the wrong anchor"
    assert vm.session_date != wrong
