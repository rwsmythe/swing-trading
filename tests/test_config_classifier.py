def test_classifier_config_default_thresholds():
    from swing.config import ClassifierConfig, Config
    c = ClassifierConfig()
    assert c.flag_pole_gain_min == 0.30
    assert c.flag_pullback_depth_max == 0.15
    assert c.flag_tightness_ratio_max == 0.6
    assert c.flag_volume_ratio_max == 0.7


def test_root_config_exposes_classifier_field():
    """Discriminating: assert Config has a `classifier` field of the right
    type. Catches the case where ClassifierConfig is defined but not wired
    onto Config (which would break `cfg.classifier` at use sites)."""
    import dataclasses
    from swing.config import Config, ClassifierConfig
    fields = {f.name: f for f in dataclasses.fields(Config)}
    assert "classifier" in fields, (
        "Config must expose a `classifier` field; spec §3.1.4/§3.8 + "
        "Task 3.2's classify_flag(bars, cfg=cfg.classifier) call"
    )
    assert fields["classifier"].type in (ClassifierConfig, "ClassifierConfig"), (
        f"Expected classifier field typed ClassifierConfig, got {fields['classifier'].type}"
    )
