from swing.config import Config, PipelineConfig


def test_pipeline_observe_window_defaults():
    pc = PipelineConfig()
    assert pc.observe_max_pending_window_sessions == 30
    assert pc.observe_max_post_trigger_window_sessions == 60


def test_from_defaults_carries_observe_windows():
    cfg = Config.from_defaults()
    assert cfg.pipeline.observe_max_pending_window_sessions == 30
    assert cfg.pipeline.observe_max_post_trigger_window_sessions == 60
