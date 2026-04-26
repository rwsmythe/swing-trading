def test_module_imports():
    from swing.evaluation.patterns.flag_classifier import (
        FlagClassificationResult,
        classify_flag,
    )

    assert callable(classify_flag)
    assert FlagClassificationResult is not None
