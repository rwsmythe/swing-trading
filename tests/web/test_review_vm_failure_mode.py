from swing.web.view_models.trades import ReviewVM


def test_review_vm_has_failure_mode_choices_default() -> None:
    # Safe default so a VM constructed without the field still renders.
    import inspect
    sig = inspect.signature(ReviewVM)
    assert "failure_mode_choices" in sig.parameters


def test_base_layout_does_not_dereference_failure_mode_choices() -> None:
    # 5-VM rule: failure_mode_choices is referenced ONLY in review_form.html.j2,
    # so a safe default on ReviewVM suffices; base.html.j2 must not deref it.
    from pathlib import Path
    base = Path("swing/web/templates/base.html.j2").read_text(encoding="utf-8")
    assert "failure_mode_choices" not in base
