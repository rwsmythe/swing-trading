"""PageErrorVM — base-layout-compatible context for page_error.html.j2."""
from __future__ import annotations


def test_page_error_vm_has_base_layout_fields():
    """Spec §3.2: base.html.j2 dereferences vm.session_date, vm.stale_banner,
    vm.price_source_degraded. PageErrorVM must provide all three plus
    status_code + detail."""
    from swing.web.view_models.error import PageErrorVM

    vm = PageErrorVM(
        session_date="2026-04-19",
        status_code=400,
        detail="Invalid input in query.period: value is not a valid member of enum",
    )
    assert vm.session_date == "2026-04-19"
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.status_code == 400
    assert "Invalid input" in vm.detail


def test_page_error_vm_defaults():
    """Defaults let a last-resort handler build the VM without every field."""
    from swing.web.view_models.error import PageErrorVM
    vm = PageErrorVM(session_date="n/a")
    assert vm.status_code == 400
    assert vm.detail == "Invalid request"
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
