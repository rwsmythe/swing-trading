from pathlib import Path


def test_form_has_failure_mode_select_with_blank_default() -> None:
    src = Path(
        "swing/web/templates/partials/review_form.html.j2").read_text(encoding="utf-8")
    assert 'name="failure_mode"' in src
    # Default blank option persists NULL on an unattributed submit.
    assert '<option value="">' in src
    assert "vm.failure_mode_choices" in src


def test_form_failure_mode_strings_are_ascii() -> None:
    src = Path(
        "swing/web/templates/partials/review_form.html.j2").read_text(encoding="utf-8")
    # The new fieldset's legend + blank-option text use plain hyphens (spec §7.1 #8).
    legend = "Why did this trade fail? (outcome attribution - optional)"
    blank = "- not a loss / not attributed -"
    assert legend in src and blank in src
    assert legend.isascii() and blank.isascii()
